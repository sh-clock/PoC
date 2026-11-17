# fog_PoC v14 — the transparency/layering fix (FENCE & BUSH)

v14 fixes the reported visual bug on models with a mix of transparent and
opaque texels — most visible at the **FENCE** (`7201_*`, `THR7204`,
`7222_1_B`, `7203_18_/30_/31_`, `THR7203`, `THR7207` — the `_STP`
materials) and the **BUSH** billboards (`BILLBOARDS_*`, `BILLBOARD_LEAF`)
— primarily in night sequences, but present in EVERY mode (fog merely
masked it). The fix is derived VERBATIM from the engine decompilation and
DuckStation; no manual patches, no per-model conditionals.

## Root cause (with evidence)

**The transparent pass was sorted per MESH, the engine sorts per QUAD.**

* v13 collected every `alphaMode != OPAQUE` **DrawItem** (one glTF mesh =
  one sort key) and ordered the whole transparent pass by the mesh's
  **average vertex depth** (a float; behind-camera vertices contributed
  1e9).
* The engine (`Gfx_MeshDraw`, bodyprog_80056D8C.c:705-717) computes ONE
  OTZ **per quad** = MAX of its four vertex SZs (Q8), applies
  `<=0 -> skip`, `<=32 -> 32`, `> field_1C -> skip`, and inserts the quad
  (+ its fog G4) with `addPrim(&tag[(OTZ >> otShift) >> 2])`. Room draws
  run at `WorldGfx_Draw(1)` (game_sys_states.c:189 — the only call site),
  so the bucket is `Q8 >> 3` = 32 buckets per metre, OT size 2048
  (game.h:27), walked **far bucket -> near bucket** (the background 2D
  effects sit at `org[ORDERING_TABLE_SIZE-1]`, bodyprog_80055028.c:127,
  and paint first). Within one bucket `addPrim` is a head insertion
  (libgpu.h:247) — the **last-added quad draws first** (LIFO).
* `Gfx_BillboardDraw` (billboard_draw.c:268-300) inserts each billboard
  quad at the bucket of its projected **CENTER** depth (Q6>>1 = the same
  Q8>>3 space), culling `<= 32` Q6 (0.5 m).

A fence mesh holds ~30 quads spanning ~2.7 m of Z; a bush ring holds 4+
quads. One average key per mesh meant their interleaved quads layered
WRONG wherever they overlapped on screen (a bush behind a fence painted
OVER the fence), and the wrong-winner regions **flipped** as the mesh
averages crossed while the camera moved — the multi-frame flicker. At
night the flashlight-lit silhouettes against darkness made it obvious;
fog washed it out in other modes.

## The fix (engine-verbatim, systemic)

Pass 2 now replicates the OT exactly:

1. **Per-quad entries.** Quads are reconstructed from the converter's
   index pattern `(v0,v1,v2)+(v1,v3,v2)` (`idx[k+3]==idx[k+1] &&
   idx[k+5]==idx[k+2]`; degenerate quads still match and their second
   triangle rasterizes to zero area, exactly like a GT4 on hardware).
2. **Bucket rules per engine path** — `BLEND` (STP) materials: OTZ =
   MAX vertex SZ (Q8), `<=0 -> no entry`, `<=32 -> 32`, bucket `OTZ>>3`;
   `MASK` (billboard leaf) materials: CENTER depth, `cQ6 <= 32 (0.5 m)
   -> no entry`, bucket `cQ6>>1`. Both land in the same Q8>>3 space.
3. **OT walk** — sort by bucket DESC (far first), then seq DESC (LIFO
   within a bucket, the addPrim order: item order × quad order).
4. **Flakes** — snow/rain entries ride the same buckets (`zHalf` is
   already Q8>>3) and are seq-assigned BEFORE quads, because the engine
   adds particles during the map update (game_sys_states.c:172) before
   `WorldGfx_Draw` (:189). On ties: quads below, flakes on top — the
   same tie behavior v13 had.
5. **Rasterization untouched** — the per-triangle culls (near 0.05 m,
   far cull, index guards), the per-texel holes and the v11 fog
   composite are byte-for-byte the v13 code. ONLY the order changed.

Per-texel rule corrected to DuckStation-verbatim
(gpu_sw_rasterizer.inl:88 `if (texture_color == 0) return` — the ONLY
per-texel skip): `ta == 0 -> hole; ta > 0 -> opaque`. The engine draws
room STP quads and billboard quads with the **ST bit clear**
(`Gfx_MeshDraw`'s STP branch adds no `setSemiTrans` to the textured
quad — only the fog G4 veil is semi-trans; `func_8005AC50`'s
`0x3C|isTransparent*2` ST-bit path is reachable only from `field_B_0`
models, and ALL 32 objects of THRF9FD.IPD have `field_B_0 = 0` —
verified by parsing the IPD), so a texel's STP bit is IGNORED: every
non-0x0000 texel — including the converter's alpha-127 STP texels —
writes OPAQUE. v13's `ta < 128` wrongly vanished alpha-127 texels;
identical output for this GLB (its textures are binary {0,255}), correct
for any asset that has them. The opaque-pass depth write moved below
the hole check (a hole texel must not leave an invisible depth wedge).

`MaterialInfo.alphaMode` is now 3-way — 0 OPAQUE, 1 MASK
(Gfx_BillboardDraw class), 2 BLEND (Gfx_MeshDraw STP class) — driving
the two bucket rules. The pass split (both classes in the transparent
pass) is unchanged.

## camtrack_v3 (the HTML editor/preview)

The JS preview does **not** have the ordering bug: its scene meshes are
`three.ShaderMaterial` without `transparent:true`, i.e. they render in
the **opaque pass with depth write** and per-texel discard — per-pixel
order-independent (the same property that makes alpha-tested rendering
immune to painter's-order errors). One discrepancy remained: the
`SH_FRAG` threshold `texel.a < 0.5` discarded alpha-127 STP texels.
v3 changes it to `texel.a < 0.002` — only a true 0x0000 texel (alpha 0)
is a hole; alpha-127 renders opaque, the same engine rule as the C++.
A no-op for binary {0,255} textures (this GLB), engine-exact otherwise.

## Verification summary

* VLM side-by-side (night): v13 "bushes in front of the fence — an
  error" -> v14 "fence clearly in front of the bushes — correct; fixes
  the depth sorting problem".
* VLM multi-frame (5 consecutive frames, night / day / thick fog):
  layering consistent, no popping/flipping in any frame.
* 21-mode sweep: 21/21 render (v13->v14 diffs 1.6-9.0%, localized to
  blend areas; mode tones unchanged — VLM-verified for mode 5).
* Snow / rain / snow+wind: coherent particles, natural depth layering
  vs fences/bushes (VLM).
* verify.sh (the v12/v13 suite): **30 PASS, 0 failures** (golden day
  references regenerated with v14 after VLM confirmed the diffs are
  vegetation re-layering, "not corruption").
* camdat v2 env parser unit test: **45/45 PASS** (recompiled vs the v14
  source).
* Synthetic STP test GLB (test-only asset; THRF9FD.glb untouched):
  v13 renders only the alpha-255 stripe; v14 renders 255 **and** 127
  stripes with identical opaque color, hole stripe stays background —
  in the C++ AND in the browser JS (137 visible px in both).
* camtrack_v3 JS suites: fxoff **35/35 PASS** (incl. export isolation),
  env0 JS-vs-C++ pixel stats identical to the v13-verified baseline
  (median |diff| 3.00, 60.4% within +-4).
* GLB integrity: `input/THRF9FD.glb` md5
  `c7183184d20a2508ce41af2702629a33` — never modified.

## Using v14

Everything from v13 works exactly as before (same CLI, same camdat v1/v2
formats, same 21 modes and 24 pairs, effects-off toggle, PSX wobble,
dither). The updated `updated_test_camdat.json` (night pair {6,3},
flashlight, rain target) renders the fixed layering out of the box:

```
./fog_poc --camdat updated_test_camdat.json          # night pair {6,3}
./fog_poc --camdat updated_test_camdat.json --envpair k,k   # any mode
```
