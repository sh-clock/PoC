# fog_PoC v19 — THE QUAD GROUPING (the bush color flicker, ACTUALLY root-caused)

v19 fixes the bush/foliage color flicker the previous three versions chased
through the lighting system. v17 moved the leaf billboards to the engine's
NCS/NCT color path (correct, kept), v18 put the light pose on the engine's
30 Hz game-loop cadence (correct, kept) — but the flicker survived both
because it was never a lighting bug at all: **it was a geometry-visibility
bug**. Whole hedge quads were flipping drawn/culled frame-to-frame, and the
"dark" state was the BACKGROUND showing through where a quad had vanished.

## 1. THE ROOT CAUSE (measured, with IPD ground truth)

The engine's room meshes are QUADS (IPD packs with 4 corner indices;
THRF9FD.IPD: 890 quads + 105 degenerate-quads-turned-triangles, 0 `0xFF`).
`Gfx_MeshDraw` treats each pack as ONE primitive: the dual `gte_NormalClip`
test

    nclip(v0,v1,v2) <= 0  AND  nclip(v3,v1,v2) >= 0   ->  skip the QUAD

plus a per-QUAD OTZ (max of all 4 vertex SZ) and the per-quad far cull.

`v10ipd2gltf.py` triangulates each pack exactly as the PS1 GPU does, with
the winding reversed for glTF:

    tri1 = (f2, f1, f0)    tri2 = (f2, f3, f1)

so one pack's GLB index group is `[f2, f1, f0, f2, f3, f1]` — a FAN around
the shared corner pair (f2, f1), and the converter's per-material corner
cache dedups the shared corners to the SAME vertex indices, guaranteeing
`idx[k+3] == idx[k] && idx[k+5] == idx[k+1]` for every real quad.

The PoC's quad detector (v16) tested a STRIP pattern
(`idx[k+3]==idx[k+1] && idx[k+5]==idx[k+2]`) that matches **nothing** in
this GLB (26/1636 accidental hits — all crossed pack boundaries). Every
engine quad was therefore walked as TWO INDEPENDENT triangles:

* the dual nclip cull ran with a GARBAGE 4th vertex (`vi[3] = 0` = the
  item's vertex 0) — the second cross product was a coin flip that changed
  with every camera step;
* the OTZ bucket and the far cull saw only 3 of the 4 corners;
* the two halves of one engine quad could flip culled/drawn INDEPENDENTLY
  every frame — the reported two-state bush flicker (the "dark" phase is
  the sky/background color where the quad vanished).

The evidence chain (all measured this session, see worklog): the light<8
cliff is quiet (3 boundary sitters, ±1 color unit), billboard NCS/NCT
colors are stable, `--modern` (no snap) and 30 Hz-grid sampling BOTH still
flicker (so neither the wobble lattice nor the 60 fps cadence was the
cause), the dark-phase pixels equal the background clear color, and a
per-quad cull audit (FOGPOC_QUADDUMP) shows the flapping quads' second
nclip oscillating around 0 on the hedge models (7201_x_H / 7206_x_H).

## 2. THE VERBATIM FIX (src/fog_poc.c — the quad walk)

1. **Quad detection = the converter's actual fan pattern**:
   `idx[k+3]==idx[k] && idx[k+5]==idx[k+1]` with `idx[k+4]` distinct from
   the other three corners (the converter's own quad rule; the distinctness
   blocks false matches that span a lone triangle + the next pack's head).
   With A=idx[k](f2), B=idx[k+1](f1), C=idx[k+2](f0), D=idx[k+4](f3), the
   existing dual nclip test and the 4-vertex OTZ/far cull become EXACTLY
   the engine's per-quad behavior (the n1/n2 sign mapping was already
   right since v16 — only the grouping never fired on real data).
2. **Lone triangles** (IPD degenerate quads, f3 == f2): the engine's second
   test degenerates to `outer(f2,f1,f2) = 0 >= 0` — the plain front-face
   rule. Replicated verbatim with `vi[3] = vi[0]` (D = A -> the second
   cross is exactly 0). v16-v18 instead used `vi[3] = 0` (the item's
   vertex 0) — a random unrelated vertex.

VERIFICATIONS:
* **Tokenizer vs IPD ground truth**: the fan walk tokenizes the ENTIRE
  shipped GLB 100% exactly — 1636 quads + 369 triangles, per-primitive Q/T
  sequences byte-identical to the IPD pack structure grouped by the
  converter's (tex, cba, stp) material key. 68/68 meshes, 0 mismatches.
* **Cull mapping vs the engine formula**: 200,000 random quads — the PoC's
  `n1 >= 0 && n2 >= 0` decision agrees with the engine's
  `outer(v0,v1,v2) <= 0 && outer(v3,v1,v2) >= 0` on every single one.

## 3. Acceptance (the mandated repro: updated_test_camdat.json @ 23.16)

* bush-crop lit-green pixel counts over the 9-frame 60 fps window:
  13919, 13599, 13605, 15614, 15986, 14184, 12068, 12364, 12732 — smooth
  evolution (v18: 13652, 12634, 12888, 14513, 13325, **6808, 5496, 5331**,
  12480 — a full lit->dark->lit strobe). Crop mean luma 53.4..52.0 (v18:
  51.7 -> 41.0 cliff).
* A->B->A two-state toggle amplitudes: **ZERO pixels >= 128** without snow
  (v18: thousands at ~146). The residual is median-33/41 texel shimmer on
  high-contrast foliage texels — the authentic PS1 noise, sub-threshold,
  same class as the reference captures' shimmer.
* Wide window (25 frames @ 30 Hz, t=23.0..23.8): luma stays 51.9..56.3 —
  no dark phase at any tick boundary; the >=128 events (12 px total) are
  snowflakes (the --nosnow window has none).
* VLM verdict on the fixed window: "The violent flickering between
  lit-green and dark states is completely gone... rendering is stable."

## 4. The JS camtrack (camtrack_v9) — TWO real bugs fixed

The shipped camtrack_v8 threw `ReferenceError: shR is not defined` on
EVERY frame from `perVertexPass` (the bbVeil fog-veil computation used the
bare helper name instead of the `SC.` accessor — the SHCore IIFE exports
its helpers as properties, not globals). The exception aborted the
per-vertex pass mid-mesh, so MASK (billboard) meshes never got their
engine colors — the RT showed stale/unlit bushes ("the posA-scope bug":
same function, same class). Fixed: `SC.shR(...)`.

Second, the "track selection clearing": v8's `restoreAutosave` restores
`saved.selection`, but `selectTrack` never WROTE it (the autosave only
fired on markDirty = document edits), so a select-then-reload still landed
with the selection null and the PiP hidden. Fixed: `selectTrack` calls
`doAutosave()` directly (selection is UI state — no dirty flag). Verified
headless: select -> reload -> selection + PiP restored; zero page errors
across GLB load, camdat import, seeks (incl. across the wrap), playback,
mode/env toggles.

## 5. Regression proof (all re-run after the quad fix)

* verify.sh — V2 determinism/bridge/turn filter, V3 camera audit
  (30 tracks x 401 rows, 0 mismatches), V4 env/light 539-sample 0-mismatch
  + blend audit + night determinism/bridge + day flashlight gate, V5
  camdat boot == explicit flags + night/nightmare states, V7 wobble
  DEFAULT ON + snap grid, V8 (all 21 presets, listmodes, rain, weather
  ticks, lensflare, dynamic fog {6,5}, lightning), V7-window live env tick
  — ALL PASS.
* The V5 day goldens were REGENERATED (the fix legitimately changes the
  cull: backfacing copies that randomly survived now correctly vanish).
  Deltas vs the v18 goldens: t=0: 2 px, t=10.5: 1368 px (>64: 0),
  t=20.5/31.5/41.5: < 100 px of 230,400 — confined, correct-direction
  changes; VLM: "no defects, holes, or missing geometry".
* tools/v10_bug_repro.py + tools/v10_stress_test.py — ALL PASS.
* 21-mode render sweep — 21/21 OK.
* New forensics: FOGPOC_QUADDUMP (per-quad cull-reason audit; env-gated,
  zero effect when unset).

## 6. Build & toggles

* Linux: gcc -O2 -std=c99 -Wall -Wextra -Wno-unused-parameter — zero
  warnings. Windows: zig cc -target x86_64-windows-gnu — PE32+,
  GDI32/USER32/KERNEL32 only.
* Hardware defaults unchanged: wobble ON, dither ON, particles ON,
  engine ON.
