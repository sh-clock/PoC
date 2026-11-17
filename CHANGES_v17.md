# fog_PoC v17 — THE ENGINE BILLBOARD COLOR PATH (Gfx_BillboardDraw NCT/NCS)

v17 fixes the reported **bush color flickering** (parts of the bush
alternating between a darker colour and its normal color — strongest with
the flashlight, also present in fog) by routing the MASK (leaf billboard)
items through the engine's REAL color path. Everything else — the v16 OT
raster + backface cull (the fence fix), the flashlight per-vertex math,
the fog/weather/snow/rain pipelines, the dithering/wobble defaults — is
untouched (all suites re-run: zero regressions).

## 1. THE ROOT CAUSE (with evidence)

The engine does NOT light the leaf billboards with the MESH per-vertex
flashlight path. Every MASK item (an unk1/field_10 foliage anchor —
`TREE_CANOPY_*` / `TREE_BUSH_*` meshes in the GLB) is drawn by
`Gfx_BillboardDraw` (billboard_draw.c:81-334), which computes ONE set of
four colors for the whole cluster:

```c
NormalColor3(&D_800AE500[0], &D_800AE500[1], &D_800AE500[2],
             &colors[0], &colors[1], &colors[2]);   /* GTE NCT */
NormalColor(&D_800AE500[3], &colors[3]);            /* GTE NCS */
```

— a light-matrix x color-matrix x background-color GTE computation
(`NormalColor`/`NormalColor3` = gtemac.h `gte_ncs`/`gte_nct`, instruction
words `0x4AC8041E`/`0x4AD80420`: **sf=1, lm=1**) over the FOUR FIXED
view-space leaf normals `D_800AE500 = SVECTOR(Q12_ANGLE(255.65°))` =
(0,2909,2909)/(-2909,0,2909)/(2909,0,2909)/(0,-2909,2909).

The v15/v16 PoC routed the leaf quads through the MESH light
(`func_80057658`) instead — whose `light < 8 -> BLACK` cliff
(Gfx_MeshDraw fog-off path, the verbatim `0x3C000000` prim) alternated
whole gouraud regions between black and lit as the wobble snapped the
raster: the reported two-state bush color flicker. The engine's billboard
path has NO cliff: the L-value feeds a smooth light-source vector.

The flicker was concentrated on the leaf clusters: over the 24-frame
60 fps sequence at t=23.0 the 3326 billboard-affected pixels measured
mean |dlum|/step 2.985 -> **1.583**, p95 11.7 -> 6.0 and the two-state
count 105 -> 76 (the residual whole-frame signal is camera motion + the
AUTHENTIC mesh-hedge cliff + wobble crawl — engine behavior).

## 2. THE VERBATIM IMPLEMENTATION (fog_poc.c `sh_billboard_colors`)

Per frame, per cluster, exactly as the engine computes it:

* **fogAlpha** = `4096 - Q8_TO_Q12(min(func_80055A50(Q12 view depth), 1))`
  (billboard_draw.c:131-138) — the CLUSTER anchor's depth.
* **enum-0 (day)**: flat `colors = Q12_MULT(worldTint, wLI)` (x fogAlpha)
  (billboard_draw.c:146-163) — no per-vertex light at all.
* **WorldEnv_LightTransform** with worldMat = [R_view | anchor]:
  `gte_SetRotMatrix_custom` (include/gpu.h:348-374, verified
  register-by-register) loads the matrix **TRANSPOSED** — so the engine
  computes `field_28`/`field_30` in VIEW space:
  `field_28 = clamp16(R*dir)*intensity>>12`, `field_30 = R*(light.pos/16
  - anchor)`. (Cross-confirmed by the stereo-balance consumer
  vc_util.c:383-384 which dots world vectors with the view coord's world
  matrix columns.) The PoC computes the glTF camera-local vectors with
  the view matrix rows quantized Q12 s16, then reflects (x,-y,-z) into
  the engine view frame — orthogonal, dot-preserving.
* **enum-1 (flashlight, func_8005A478)**: the rtps cone over
  [field_28; (anchor-light) unit; (anchor-light) Q8] (tr=0, OFX/OFY =
  Q8(-4), H=16, DQA = light.field_0) producing the billboard L-value —
  note the **`>>= 1` halving** unique to this path and the field_3 clamp
  BEFORE the alpha multiply — then the light source vector
  `clamp(row1 * var_a2 >> 7, ±Q12(1.4))` and
  `BK = Q12_MULT(field_24 + worldTint*var_a1>>7, fogAlpha)`.
* **enum-2 (directional, func_8005A838)**: light source =
  `field_28 * fogAlpha / 2`, `BK = field_24 * fogAlpha`.
* **The magnitude rescale** (billboard_draw.c:191-239): light vector
  scaled to `(mag-0.25)*0.3+0.25` capped at 1.0 via the s32 division
  `temp_lo = Q12(min(target,1)) / mag`; enum-1 additionally scales
  `BK = BK*temp_lo` (the `gpf12` MAC `(IR*IR0)>>12` read back by
  `ldmac_stir` — DuckStation gte.cpp:1227-1238).
* **LLM rows 1-2** rebuilt from the scaled light vector:
  row1 = `(-lZ>>4, lY>>4, lX>>4)`, row2 = `(lZ>>4, lY>>4, -lX>>4)`.
* **The color matrix** = `g_WorldEnvWork.colorMat` (every entry of row i
  = the world tint Q12 — WorldEnv_WorldLightingParamSet:165-176).
* **NCT/NCS** (DuckStation gte.cpp:963-996): IR = clamp((LLM row . N)>>
  12, 0, 0x7FFF); MAC = ((BK<<12) + LCM row . IR) >> 12 (IR clamp
  again); RGB = clamp(MAC>>4, 0, 255). All four corners share the
  cluster colors; corner j of every quad gets colors[j] (the engine's
  own cross-wiring: top<-N0, right<-N1, left<-N2, bottom<-N3).
* **The fog veil** (fog ON): the per-QUAD flat semi-trans G4 color
  `DPCS(fog.color, 4096 - min(ramp*16 + intensity, 4096))` computed at
  the quad's ring-position (bottom vertex = curPtr->position) depth —
  the same fogColor*f formula as the mesh veil, applied at the
  billboard's own depth reference.
* **The cluster anchor** is recovered at runtime (GLB read-only) from
  quad 0's bottom vertex minus the verbatim D_800AE204 slot-0 ring
  offset (the converter loops the table in order; SCALE = 1/256) —
  verified consistent across all 27 clusters x all ring slots (< 8 mm).

`field_24` (the Q7 CVECTOR ambient `(tintQ12*wLI)>>17`) was added to the
env apply — `WorldEnv_WorldLightingParamSet` (0x80055330) verbatim.

## 3. The JS (camtrack_v7.html) — the same path, byte-exact

`shBillboardColors` ports the computation 1:1 (`shGteNcs`, the anchor
recovery, the per-quad veil). Cross-verified against the C++ at t=23.11:
the billboard colors are **byte-identical** (e.g. BILLBOARDS_0 =
(3,3,4)(2,3,3)(5,5,5)(4,4,4) in both), and stable frame-over-frame
(±1 quantization steps — no cliff). The JS `alphaMode` conflation
(MASK vs BLEND) was fixed with an explicit `isMaskBB` flag at
registration (MASK = the engine's Gfx_BillboardDraw leaf clusters; BLEND
= the engine's STP prims). One JS bug found and fixed during
verification: the light-position Q8 was s16-clamped BEFORE subtracting
the anchor (the engine computes the small delta first —
billboard_draw.c:169).

## 4. What was checked and deliberately NOT changed

* **The remaining temporal signal**: the mesh hedges (7206_H etc.) still
  show the authentic `light < 8 -> BLACK` cliff — that IS the engine
  (func_80057658 verbatim, 539-sample audit 0 mismatches; the JS shows
  the same cliff, softer). The wobble/dither crawl and the snow field
  are engine/hardware characteristics (the v16 verdict stands).
* **The 86-path mesh draw** (func_8005A21C -> func_8005AA08's gte_nct
  for mesh normals): only reachable via `field_B_0` models — THRF9FD.IPD
  has field_B_0 = 0 for ALL 32 objects (v16 parse) — not taken.
* **The MASK OT bucketing** (center-depth Q6>>1, gates >32 and the far
  cull): unchanged v16 behavior.
* **The STP/BLEND raster semantics**: unchanged (the v12 D2 verdict).
* **live_00023.11.png** is a PoC-era capture of the BUG state (the
  shots/live_%08.2f.png naming) — v17 legitimately differs from it in
  the leaf regions: the leaf clusters now match the ENGINE (near-black
  beyond the tight billboard cone — the engine's leaves dim FASTER than
  mesh geometry: the L-value has the extra >>1 halving).
* **Day goldens**: regenerated (the enum-0 billboard flat color +
  per-cluster fogAlpha replaces the per-vertex mesh formula on leaves —
  deltas mean 0.3-1.2, max 15-25, leaf regions only).

## 5. Regression suite (all re-run this session)

* `verify.sh` — V2 (determinism, bridge, turn filter), V3 camera audit,
  V4 (env/light 539-sample 0-mismatch, blend fade, night
  determinism/bridge, day-flashlight gate), V5 (camdat boot == explicit
  flags, night/nightmare, goldens regenerated), V7 (wobble default ON +
  snap grid), V8 (all 21 presets, listmodes, rain, weather ticks,
  lensflare, dynamic fog {6,5}, lightning) — **ALL PASS**.
* `tools/v10_bug_repro.py` + `tools/v10_stress_test.py` — ALL PASS.
* 21-mode render sweep + enum-2/enum-0/day/dusk/pure-night billboard
  color dumps — correct (enum-2 full-fog = veil-only leaves, the
  verbatim fogAlpha -> 0 behavior).
* The JS (camtrack_v7.html): load/import/seek (forward+backward)/play/
  pip/faithful-RT extraction all exercised headless — zero page errors.

## 6. Build & toggles

* Linux: `gcc -O2 -std=c99 -Wall -Wextra -Wno-unused-parameter` —
  **zero warnings**. Windows: `zig cc -target x86_64-windows-gnu` —
  PE32+, GDI32/USER32/KERNEL32 only.
* Hardware defaults unchanged: wobble ON, dither ON, particles ON,
  engine ON — every PSX quirk toggleable, authentic behavior default.
* New debug env var: `FOGPOC_BBDUMP=1` appends the per-cluster billboard
  color dump to `bbdump.txt` (audits; same pattern as FOGPOC_SNOWDUMP).
