# fog_PoC v15 — the engine Ordering-Table raster + hardware-default dither

v15 fixes the reported **Z-fighting / texture-model flickering** by
replicating the engine's raster architecture VERBATIM, and turns **ordered
dithering ON by default** (the PSX hardware behavior). The flashlight,
fog, weather, snow and rain pipelines were re-audited line-by-line against
the decompilation and DuckStation this session — **no changes were needed
there** (see the verdicts below).

## 1. The C++ Z-fighting fix — the engine's Ordering Table, not a z-buffer

### Root cause (with evidence)

The PSX GPU has **NO depth buffer**. DuckStation — the hardware source of
truth — rasterizes every primitive in pure GP0 command order
(`src/core/gpu_sw_rasterizer.inl`: no depth test anywhere; the only
"depth" machinery on the whole console is the software Ordering Table).
The SH1 engine exploits exactly that: `Gfx_MeshDraw`
(bodyprog_80056D8C.c:854–873, 991, 1163–1179, 1327, 1419) `addPrim`s
**every quad — STP or not, in every fog/enum branch — into the same
per-quad OT bucket**

```
tag[(MAX_vertex_SZ_Q8 >> otShift) >> 2]        (otShift = 1 via WorldGfx_Draw(1),
                                                 game_sys_states.c:189)
```

and `GsDrawOt` walks the buckets **far → near**, with `addPrim` head
insertion (libgpu.h:247) giving **LIFO within a bucket** (the last-added
prim draws first, so the earlier-added prim paints on top).

The PoC v11–v14 instead resolved quad visibility with a **per-pixel float
depth comparison** (`z >= fb->z[pi]` in `raster_tri`, both passes). Two
overlapping quads whose interpolated z values crossed under the GTE vertex
snap alternated their per-pixel winner frame-to-frame — the reported
"flickering/fighting within the textures". Measured on the shipped
sequence: clean two-state alternation (24↔107-style) on the road seams and
thin overhead features; on the updated camdat's low street track the
true z-fighting component measured ~0.3–2% of pixels (the rest of the
temporal signal is the authentic band-crawl described in §3).

### The fix (engine-verbatim, no manual patches)

* `raster_tri`: the per-pixel depth **test is gone**. Visibility is decided
  by the draw sequence alone — the painter's algorithm the PSX actually
  performs. The OPAQUE depth **write** remains but is now unconditional
  (last-drawn covering quad wins) and serves *only* as the snow/rain
  occlusion reference — the v4-era documented refinement (the engine's
  flakes ride the OT buckets alone; keeping the reference preserves the
  v14-verified snow layering while nothing is ever depth-*gated*).
* `render_frame`: the z-buffered opaque pass (drawn in GLTF node order)
  is **removed**. All quads — opaque, MASK and BLEND — are collected as
  per-quad OT entries exactly like the engine:
  * OPAQUE + BLEND → the `Gfx_MeshDraw` rule: bucket = (MAX vertex SZ Q8
    >> 1) >> 2, with `<=0 → skip`, `<=32 → 32`, and the per-**quad** far
    cull `> field_1C → skip` now applied at entry creation exactly like
    `bodyprog_80056D8C.c:729–731` (v13/v14 applied it per-triangle, which
    could still draw the near triangle of a far quad — the engine never
    does);
  * MASK → the `Gfx_BillboardDraw` rule: bucket from the quad **center**
    depth (billboard_draw.c:255–326), `> 32` gate + far cull.
* The single OT walk draws far→near, LIFO within a bucket, with the
  engine's add order (particles first — game_sys_states.c:172 before
  WorldGfx_Draw :189 — then quads in item/prim order).

**No per-model conditionals. No depth bias. No polygon offset.** The only
visible day-render difference vs v14 (VLM-verified): a thin distant edge
object beyond the 30.4 m `field_1C` boundary now drops out entirely —
which is precisely what the engine's own far cull does.

## 2. Dithering and wobble DEFAULT ON (the hardware behavior)

* **Dither** now defaults ON: DuckStation `gpu.cpp:2988–2994` — polygon
  dithering follows the draw-mode DTE bit for every shaded or
  texture-modulated polygon (all SH1 mesh quads), while sprites never
  dither (the PoC's flake/rain blitters match); the 4×4 matrix
  (`gpu_types.h:269 DITHER_MATRIX`) is byte-identical to the PoC's
  `DITHER4`, and the application math (`(value + offset) >> 3` clamped —
  `gpu_sw_rasterizer.cpp:20–32`) matches the PoC's clamp-then-truncate.
  `--no-dither` opts out; the camdat env `dither` field and the **D**
  keybind toggle it live.
* **Wobble** was already default ON since v7 (GTE `PushSXY(s32(Sx>>16))`
  truncation — gte.cpp:786); unchanged, `--modern`/P remain the opt-outs.

## 3. What the remaining "flicker" actually is (measured, not guessed)

With the correct (updated) camdat on **both** renderers the temporal
profile is *identical* between the C++ and the JS preview:

| renderer | strong 2nd-diff px | two-state px |
|----------|--------------------|--------------|
| C++ v14  | 55.1%              | 21.6%        |
| C++ v15  | 54.9%              | 21.3%        |
| JS  v3   | 51.4%              | 22.7%        |
| JS  v5   | 51.7%              | 22.1%        |

The dominant signal is the **15-bit quantization band-crawl**: pixel time
series walk adjacent 5-bit levels (24/33/41/49/57/66) as content moves —
the authentic PSX framebuffer behavior (the console's 15-bit VRAM +
dither produced exactly this crawl), amplified in visibility by the PoC's
2× render resolution (640×360 vs the console's 320×240 raster). The
alpha-holed fence/bush texel patterns add motion aliasing at the same
scale. **These are hardware characteristics, not port bugs** — "fixing"
them (smoothing, biasing, blurring) would be a manual patch, which the
task explicitly forbids. The true depth-comparison z-fighting (§1) is the
port bug, and it is gone.

## 4. The JS flickering fix (camtrack v5 — separate investigation, as mandated)

Investigated completely independently from the C++ issue:

* **Pipeline stability**: paused, the preview renders **bit-identical**
  frames (30/30) — no canvas/framebuffer management, sorting, buffer
  upload or frame-timing instability exists.
* **Engine math**: the JS `shMeshLightVertex`/GTE ports produce
  **identical** results to the C++ on a 384-point input grid (0
  mismatches); the env state chain matches.
* **Renderer semantics** (the two engine deviations fixed in v5):
  1. **OT bucket depth** — the preview rasterized all quads through the
     GPU depth buffer with per-pixel comparisons (the PSX has none). The
     vertex depth now quantizes onto the engine's bucket grid
     (`floor(viewDepth*32)/32 + 1/64`); comparisons resolve BY BUCKET and
     exact ties by draw order with `depthFunc: LessDepth` == the engine's
     within-bucket LIFO (the prim submission order inside a mesh is the
     converter's = the engine's add order).
  2. **Affine varying interpolation** — the PSX GPU interpolates UV and
     gouraud colors screen-space linearly, with NO perspective correction
     (DuckStation `gpu_sw_rasterizer.inl` `dudx/dvdx/dudy/dvdy` steps —
     the classic PSX texture warp). The WebGL perspective-correct
     interpolation was replaced with the noperspective emulation
     (pre-multiply by the bucket w, unwrap by the interpolated w).
* After the fixes the JS↔C++ env0 parity **improved** (median per-pixel
  |diff| 1.67 vs the v13-verified baseline's 3.00; 84.2% within ±4 vs
  60.4%), and the multi-frame VLM verdict: *"highly coherent, no
  z-fighting, smooth light cone, discrete drifting snow, no tearing or
  corruption"*.

## 5. Flashlight verdict — VERBATIM (proven, not patched)

The user questioned whether the flashlight looks "too modern". The audit
result: **the port is verbatim** — no changes were made, and none were
invented:

* `sh_mesh_light_vertex` == `func_80057658` (bodyprog_80056D8C.c:327–459)
  line-for-line: `SetGeomOffset(-1024,-1024)` + `SetGeomScreen(16)`,
  `ir1 = clamp16((field_28 · Δ)>>12)`, `ir2 = clamp16((normal<<5 · Δ)>>12)`,
  `sz3 = clamp(|Δ|²>>12)`, `UNRDivide(16, sz3)`,
  `sxC/syC = clamp((UNR·IR − 1024<<16)>>16, −1024, 1023) + 1024`,
  `dp = clamp((UNR·DQA)>>12, 0, 0x1000)`,
  `light = ((sxC·syC + syC·(dp>>4))>>5 − 16) + (field_20>>5) +
  min((sxC>>1)+(dp>>2), 48)`, clamped to `field_3`.
* The light direction/position chain == `Gfx_EffectsUpdate` →
  `func_8003F4DC` (the −15° beam with the RAW sine-LUT values) →
  `Gfx_FlashlightPositionUpdate` → `WorldEnv_LightTransform`
  (field_28/field_30/DQA).
* The lighting is applied **per vertex** and gouraud-interpolated across
  the triangle — exactly the GPU's affine vertex-color interpolation the
  engine used; the "jagged triangles" are inherent to that per-vertex
  math on this mesh density.
* Cross-check: a 384-point light grid through the C++ and the JS produces
  **0 mismatches**, and a hand-computed engine evaluation of a live scene
  vertex (light 64 → vcol [54,58,62]) matches the running renderers.
* **The ONE documented deviation** (unchanged, user-directed): the v6
  directive anchors the light at the **camera eye** rather than Harry's
  torso bone + the (−0.08, −0.28, 0.12) offset
  (Game_FlashlightAttributesFix, world_effects.c:187–196). This, plus the
  2× render resolution, accounts for the "smoother than the real game"
  impression; the math itself is the engine's.

## 6. Fog / weather / snow / rain — re-audited, no changes needed

* Fog LUT chain: `WorldEnv_FogDistanceSet` / `func_800559A8` /
  `func_80055A50` / `func_80055814` (bodyprog_80055028.c:327–455) —
  verified verbatim against the ports (the prior sessions' 539-sample
  env audit re-run this session: 0 mismatches).
* Weather sine cross-fade (`particle.c:385–560`) and the
  `Particle_SnowDraw` OT insertion (`org[zHalf]`, `setSemiTrans`,
  tpage 44) — verified against the ports.
* The regression suites all pass: `verify.sh` (all sections), the 21-mode
  sweep (21/21), the camdat v2 parser (45/45), the JS fxoff suite
  (35/35 incl. export isolation).

## 7. Build & toggles

* Linux: `gcc -O2 -std=c99 -Wall -Wextra -Wno-unused-parameter` —
  **zero warnings**. Windows: `zig cc -target x86_64-windows-gnu` —
  PE32+, GDI32/USER32/KERNEL32 only.
* Hardware defaults: wobble ON (P/--modern toggles), dither ON
  (D/--no-dither toggles), particles ON (B/--nosnow), engine ON
  (M/--nofog) — every PSX quirk is toggleable with the authentic
  behavior as the default, exactly as mandated.
