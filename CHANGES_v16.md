# fog_PoC v16 — the engine's OT MODEL LAYERS + the gte_NormalClip backface cull

v16 fixes the reported **fence and bush flickering** with TWO verbatim
engine mechanisms that v15 was missing. Everything else — the v15 OT
raster, the flashlight math, the fog/weather/snow/rain pipelines, the
dithering/wobble defaults — is untouched (all suites re-run: zero
regressions).

## 1. THE PER-MODEL OT SECTION BASE (func_80057090 / func_800571D0)

### Root cause (with evidence)

The engine does NOT put every model's quads in the same OT section.
Every model draw goes through

```c
func_80057090 (bodyprog_80056D8C.c:126-162):
    otTag = &arg1->org[func_800571D0(modelHdr->field_B_1)];
    ... func_80057344 / Gfx_MeshDraw(otTag, ...)
func_800571D0 (bodyprog_80056D8C.c:164-187):
    field_B_1: 0 -> 2, 1 -> 0, 2 -> 4, 3 -> 33, 4 -> 66, 5 -> 99
Gfx_MeshDraw (all branches, e.g. :854-873):
    addPrim(&tag[(OTZ >> otShift) >> 2], poly)   // tag = org + BASE
```

so a mesh quad's OT bucket is **BASE + (OTZ >> 3)** with the per-model
BASE taken from the `s_ModelHeader::field_B_1` bits of the room's IPD.
`field_B_1` is a LAYER class: base-99/66/33 models (the "B" overlays,
the doors, the second chain segments) are forcibly drawn ON TOP of
everything within 2.6 m; base-0 models (the N-signs, the third chain
segments, NOTICE_N) are held BELOW the standard base-2 mesh layer
within 16 cm; `Gfx_BillboardDraw` adds the leaf diamonds at
`org[z >> otShift]` with NO base (billboards and snow flakes ride the
base-0 section — billboard_draw.c:317-326, particle.c).

The field_B_1 values of THRF9FD.IPD were surveyed from the actual
archive (every `s_ModelHeader` parsed — see the table in fog_poc.c
`IPD_MODEL_LAYERS`):

```
base 0 : 7203_3_N, NOTICE_N, CHAIN1_3, CHAIN2_3
base 2 : 7201_1/2/3_H (the FENCES), 7203_6_H, 7206_1/3_H (the HEDGES/
         BUSHES), 7207_6/7/8/9_H, TREE02, THR0001/0002/0020/7202/7203/
         7204/7206/7207 (the standard layer — field_B_1 = 0)
base 4 : 7203_18_, 7203_30_, 7203_31_
base 33: CHAIN1_2, CHAIN2_2
base 66: 7222_1_B, DOOR1_BA
base 99: 7203_7_B, 7207_1_B, 7222_7_B, CHAIN1_1, CHAIN2_1, CHAIN2_4
```

The PoC v15 bucketed ALL mesh quads at plain `OTZ >> 3` (the base-0
section): cross-layer overlaps (fence/hedge/bush quads vs the forced-
top B-overlays vs the forced-bottom N-signs) resolved by raw depth and
**flipped frame-to-frame** — the reported fence/bush flickering. The
v16 PoC resolves each item's layer from its GLTF node name through the
verbatim `func_800571D0` table and buckets mesh quads at
`BASE + (OTZ >> 3)`; MASK (billboard) quads and snow/rain flakes keep
the base-0 section exactly like the engine.

## 2. THE gte_NormalClip BACKFACE CULL (Gfx_MeshDraw, every branch)

### Root cause (with evidence)

Every Gfx_MeshDraw branch culls each quad before addPrim
(bodyprog_80056D8C.c:734-748, and the identical blocks at
923-939 / 1046-1062 / 1235-1251 / 1375-1391):

```c
gte_NormalClip(x0y0, x1y1, x2y2, &sp10);   // NCLIP of (v0, v1, v2)
if (sp10 <= 0) {
    gte_ldsxy0(x3y3); gte_nclip(); gte_stopz(&sp10); // NCLIP of (v3, v1, v2)
    if (sp10 >= 0) continue;                // BOTH backfacing -> SKIP
}
```

The GTE NCLIP is the signed double area of the triangle in SCREEN
space, computed on the SNAPPED integer SXY coords (DuckStation
gte.cpp:900-911: `SX0*(SY1-SY2) + SX1*(SY2-SY0) + SX2*(SY0-SY1)`).
A quad is drawn iff `nclip(v0,v1,v2) > 0` OR `nclip(v3,v1,v2) < 0`
(the dual test keeps a quad whose second triangle is front-facing
while the first is degenerate — func_8005AC50 uses the plain
`r4 <= 0 -> skip` form of the same rule).

The PoC's raster accepted BOTH windings ("the glTF converter emits
either order, matching the engine's dual gte_nclip test which accepts
a quad either way" — a v5-era MISREADING of the dual test). Every
backfacing wall/hedge/bush/fence quad was still painted, piling dark
wrong-side copies over visible geometry — the "dark pileup" behind
the night bushes and part of the fence shimmer. v16 applies the
verbatim dual nclip test on the (snapped) screen coords for MESH
quads (OPAQUE + BLEND), translated to the converter's reversed
winding:

```
GLB quad verts A=v2, B=v1, C=v0, D=v3  (converter emits (v2,v1,v0)+(v2,v3,v1))
cull iff  cross(B-A, C-A) >= 0  AND  cross(D-A, B-A) >= 0     (screen space)
```

MASK (billboard leaf) quads are NOT culled — Gfx_BillboardDraw has no
nclip test (the converter marks BILLBOARD_LEAF doubleSided for
exactly this reason). Day-mode verification: 4996 of 6529 quads are
backfacing at the t=10.5 camera and were already buried under nearer
geometry in v15 — the day look changes by 0.0-1.3% of pixels (the
wrongly-visible backfaces); the night bush region gains its missing
front foliage (the v15 "clipped bushes" — VLM-verified before/after).

## 3. What was checked and deliberately NOT changed

* **The night {6,3} fog state**: verified engine-verbatim — the
  flashlight intensity ramps the pair blend weight to 1
  (Gfx_EffectsUpdate, world_effects.c:393-430), and the LIVE env
  becomes preset 3: enum-1, field_E=0 (fog OFF), wLI 0.0, spot 1.3.
  The PoC's fogstate probe confirmed env_isFog=0, lightMode=1.
* **The flashlight per-vertex math**: re-audited against
  func_80057658 and DuckStation's GTE (RTPS: MAC3 = (TR<<12 + R·V),
  SZ3 = MAC3>>12 = Q8 view depth; UNRDivide; the sxC/syC clamps; the
  DQA/IR0 saturation [0, 0x1000]) — unchanged, still 100% verbatim
  (the 539-sample env audit: 0 mismatches).
* **The STP/BLEND raster semantics**: holes = texel 0x0000 only
  (DuckStation ShadePixel `texture_color == 0 -> return`), visible
  texels opaque + the fog veil — unchanged (the v12 D2 verdict).
* **The remaining temporal signal** (measured over dense 60 fps
  sequences at t=5.0/6.5/12.0/20.0 on updated_test_camdat.json):
  the two-state pixel count drops (night nosnow 16252 -> 14114,
  snow-on 20542 -> 17383 at t=5; the concentrated bottom-left
  bush/fence blob shrinks ~65%), and the VLM verdict on the fixed
  sequence: *"fence mesh highly coherent, no z-fighting or geometry
  popping, bushes stay solid, only the expected PS1-style vertex
  snapping and texture wobble — STABLE"*. The residual is the
  authentic PSX texture wobble/crawl (the affine UV mapping wobbling
  under multi-vertex snapping — the engine/GPU has exactly this),
  the STP hole crawl on the fence/bush overlays, the far-edge
  pop-in at the fog boundary (the engine's own `> field_1C` per-quad
  far cull) and the snow field — all engine/hardware characteristics
  at the PoC's 2x resolution, NOT port bugs.
* **JS (camtrack v5)**: untouched — no HTML modification was needed
  (the C++ is the byte-exact reference; the JS stays the preview
  approximation with its bucket-quantized depth buffer). Parity
  re-measured (night t=5.2, 80x45 grid): v16-vs-JS median 25.0 vs
  v15-vs-JS 24.0 — unchanged within noise.

## 4. Regression suite (all re-run this session)

* `verify.sh` — V2 (determinism, bridge, turn filter), V3 camera
  audit, V4 (env/light 539-sample 0-mismatch, blend fade, night
  determinism/bridge, day-flashlight gate), V5 (camdat boot ==
  explicit flags, night/nightmare, goldens regenerated — the only
  day --modern golden delta is 1 pixel at t=0), V7 (wobble default
  ON + snap grid), V8 (all 21 presets, listmodes, rain, weather
  ticks, lensflare, dynamic fog {6,5}, lightning) — **ALL PASS**.
* `tools/v10_bug_repro.py` + `tools/v10_stress_test.py` — ALL PASS
  (flashlight ramps, wrap recovery, no tick gaps).
* The 21-mode render sweep on updated_test_camdat.json — 21/21 with
  content, VLM-checked fence/bush coherence across day/night/
  nightmare/dusk.

## 5. Build & toggles

* Linux: `gcc -O2 -std=c99 -Wall -Wextra -Wno-unused-parameter` —
  **zero warnings**. Windows: `zig cc -target x86_64-windows-gnu` —
  PE32+, GDI32/USER32/KERNEL32 only.
* Hardware defaults unchanged: wobble ON, dither ON, particles ON,
  engine ON — every PSX quirk toggleable, authentic behavior default.
