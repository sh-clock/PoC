# CHANGES — PoC v11 (the normal-fog veil fix; v10's incomplete fog work completed)

One runtime defect remained after v10 (its own boot-flag fix was correct but
insufficient — the fog itself was still broken), fixed with 100%
decompilation-derived logic. **No manual patches. No engine math altered. No
GLB/GLTF modification.** Every fix names its engine source; every claim was
reproduced and re-tested with hard evidence (pixel statistics, VLM visual
verification, byte-level A/B renders across all 45 mode configurations, an
Xvfb synthetic-key infinite-cycling stress test, and a DuckStation GTE
line-level audit).

--------------------------------------------------------------------------------
## 1. THE STILL-BROKEN NORMAL FOG (MAJOR) — FIXED (the regression v10 missed)

### Symptom
After v10's boot-flag fix, a day boot (`--day` / `{1,1}`) rendered with the
correct fog BACKGROUND (sky ≈ fogColor {108,100,116}) but all distant OPAQUE
geometry faded toward BLACK instead of the fog color: mean RGB
(72.22, 68.74, 77.24) at t=10.5 versus the v3 working-fog ground truth
(91.49, 86.24, 96.98) — 19.3 units too dark. The scene read as "darkness
with a gray sky", not Silent Hill fog. This is exactly the user report:
"the normal fog mode HAS NOT BEEN FIXED."

### Root cause (the v5-v10 `isStpPrim` fog-veil gate)
`fog_poc.c` (v5-v10), the per-vertex fog tail:

```c
/* v5-v10 */
if (fogOn && fogColNZ && isStpPrim) {          /* <-- WRONG GATE */
    o->ocol[0] = (R->fog->fogColor[0] * fq12) >> 12;
    ...
} else {
    o->ocol[0] = o->ocol[1] = o->ocol[2] = 0;  /* opaque prims: NO veil */
}
```

with the comment: *"The additive fog veil (fogColor * f): the engine emits
it as a semi-trans G4 ON TOP of STP prims only ...; OPAQUE prims get it
BELOW the textured quad — invisible for hole-free materials."*

That comment MISREADS the decompilation in two independent ways:

1. **The OT draw order.** In `Gfx_MeshDraw`'s fog paths
   (bodyprog_80056D8C.c:1175-1183, enum-0; :868-877, enum-1/2), the
   NON-STP branch is:

   ```c
   setSemiTrans(poly3, 1);              /* the TEXTURED GT4 is SEMI-TRANS  */
   addPrim(&tag[...], poly3);           /* added FIRST                     */
   addPrim(&tag[...], poly2);           /* added SECOND -> drawn FIRST    */
   ```

   Psy-Q `AddPrim` inserts at the HEAD of the OT bucket list, so the GPU
   draws the list LIFO: **poly2 — the OPAQUE fog G4 (per-vertex
   `fogColor*f`) — is the BASE layer, and the semi-transparent textured
   quad composites ON TOP of it** (tpage ABR=1 additive). The fog G4 is not
   "below and invisible": the textured quad is semi-trans, so the base IS
   visible through it. The v5-v10 author assumed the textured quad stayed
   opaque and that add order was draw order.

2. **The veil is not STP-only.** The STP branch (lines 1157-1174) emits the
   same dual-quad structure with the veil ON TOP (`setSemiTrans(poly2,1)`)
   of an opaque textured quad — the SAME compositing formula. Both branches
   produce:

   ```
   final pixel = fogColor * f  +  (texel * tintEff * (1 - f)) >> 7
   ```

   which is exactly the v3 single-formula implementation the user accepted
   as WORKING FOG (v3 `raster_tri`: `r = ((tr * vr) >> 7) + orr` for BOTH
   the OPAQUE and RP_BLEND_TEX passes).

Dropping `fogColor*f` from every opaque prim made distant geometry converge
to `tintEff*T -> 0` = black, instead of the fog color — the broken fog.

### The change (v11)
```c
if (fogOn && fogColNZ) {                       /* v11: ALL prims            */
    o->ocol[0] = (R->fog->fogColor[0] * fq12) >> 12;
    ...
}
```
The `fq12 = ramp*16 + fogIntensity` (clamped 4096) veil factor, the
`fogColor==0` skip (a zero veil is a no-op — the dark fog presets 6/7/19
are untouched by construction), and every other fog value are UNCHANGED.
The now-unused `isStpPrim` local was removed (the raster pass split uses
`sc->mat[].alphaMode` directly — verified independent).

### Proof
- Day t=10.5 render: mean RGB (92.33, 87.32, 98.77) vs v3 ground truth
  (91.49, 86.24, 96.98) — within ~1 unit (v10: 72.22, 68.74, 77.24).
- VLM (glm-5v-turbo) on the 3-way side-by-side: v3 = correct gray-blue
  mist; v10 = "distant geometry extremely dark, almost black"; v11 =
  "closely matches the LEFT reference ... proper luminosity ... smooth
  transition to the foggy horizon re-established". PASS.
- 45/45 mode regression matrix (21 presets + 24 authentic pairs, v10 vs
  v11): the 6 configurations whose ACTIVE preset has fog ON + fogColor!=0
  changed (the fix); the other 39 are BYTE-IDENTICAL — including every
  night, nightmare, and flashlight configuration (zero regressions on the
  v9/v10-excellent dark rendering).
- DuckStation GTE audit (unchanged code, verified anyway): UNR table
  257/257 entries byte-identical to `src/core/gte.cpp`; UNRDivide math
  200,512 randomized cases, 0 mismatches; RTPS `PushSXY(s32(Sx>>16))`
  truncation semantics == `gte_snap_screen` floor. The PSX wobble path is
  untouched by the fix (byte-identical night renders prove it).

--------------------------------------------------------------------------------
## 2. FLASHLIGHT GATE & ENV FREEZE (v10's fixes — verified, kept, re-tested)

v10's two state-machine fixes were verified against the decompilation line
by line and are retained unchanged:

- **Flashlight gate** = `!isFlashlightUnavailable` (identical-preset pairs
  refuse up front): verified `item_screens_2.c:1267` (OnOff command shown
  iff `!isFlashlightUnavailable || item != Flashlight`),
  `bodyprog_effects_8005E0DC.c:650` (auto-off while unavailable),
  `world_effects.c:316-326` (unavailable = pointer-equal presets). Live
  Xvfb key test: 3x F on `{1,1}` REFUSED; 7x F on mixed pairs all accepted,
  4 complete ramps to 4096, 0 stalled; toggleable after mode switches.
- **Env freeze** = monotonic session clock + backward-time resync in
  `sh_env_sync_live` (the camtrack phase wraps at T=49.8787 s). Live stress
  test: 7758 env ticks across 258 s, 4 wrap crossings, 120 preset changes +
  60 pair changes + 20 weather cycles + browser open/close, 0 freeze
  indicators, flashlight recovers post-wrap. ALL PASS.

--------------------------------------------------------------------------------
## 3. TESTING SUMMARY (all evidence reproducible)

| Check | Result |
|---|---|
| Day fog pixel stats vs v3 ground truth | within ~1 RGB unit (v10 was 19.3 off) |
| VLM 3-way fog visual audit | v11 == v3 reference; v10 broken — PASS |
| 21-preset + 24-pair byte A/B (v10 vs v11) | 45/45 — only fog+color configs changed |
| Night / night+flashlight A/B | BYTE-IDENTICAL |
| Infinite cycling stress (Xvfb synthetic keys) | ALL PASS (7758 ticks, 0 stalls) |
| Flashlight gate live test | ALL PASS (3 refused, 4 ramps, 0 stalls) |
| DuckStation GTE UNR table + UNRDivide + RTPS | PASS (byte/line-identical) |
| GLB/GLTF modification check | md5 c7183184d20a2508ce41af2702629a33 — UNCHANGED |
| verify.sh determinism suite | ALL PASS |
