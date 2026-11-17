# fog_PoC v18 — THE 30 Hz LIGHT-POSE CADENCE (the bush color flicker, root-caused)

v18 fixes the remaining **mesh (hedge/tree) color flickering** the
previous agent wrongly certified "engine-authentic". The v17 billboard
NCS/NCT path (the leaf clusters), the v16 OT raster + backface cull
(the fence fix), the flashlight per-vertex math, the fog/weather/snow/
rain pipelines, and the dithering/wobble defaults are all untouched
(all suites re-run: zero regressions; day renders byte-identical).

## 1. THE ROOT CAUSE (with decomp evidence)

The v15-v17 PoC updated the flashlight light pose EVERY 60 fps session
frame (`sh_env_sync_live` ended with a per-frame `sh_env_update_pose`
call, commented "the engine updates the light every frame"). That
comment is FALSE. The engine's game loop:

  game_main.c:271-276  `while (g_VBlanks < g_IntervalVBlanks) VSync(SyncMode_Wait);`
  game_sys_states.c:93 `g_IntervalVBlanks = 2;`

waits TWO VBlanks per iteration -> the ENTIRE update+render pipeline —
Gfx_EffectsUpdate -> Gfx_FlashlightPositionUpdate (the light pose) ->
WorldEnv_LightTransform (per model) -> WorldGfx_Draw — runs at 30 Hz.
The light pose (position, direction, field_28, field_30, DQA) is env
state that only ever changes on those 30 Hz game frames. The v15-v17
per-frame refresh injected 60 Hz half-step light positions the engine
NEVER computes — and never renders.

The visible consequence (measured with FOGPOC_LIGHTDUMP, the new
per-vertex light dump): with smoothly-moving inputs (dx/dy/dz stepping
~7 Q8 per frame, the light direction CONSTANT) the integer cone product

  sxC = (UNR * IR1) >> 16        (UNR = the GTE reciprocal staircase,
                                  IR1 = (field_28 . delta) >> 12)

hovered around the sxC = 16 threshold — UNR steps +1 while IR1 steps
-9, so the product oscillated across 16<<16 every other frame. Since

  light = max(0, (sxC*syC + syC*(dp>>4))>>5 - 16) + wliAmb
          + min((sxC>>1) + (dp>>2), 48)

sits at 7..8 exactly there, and the fog-off Gfx_MeshDraw branch
(bodyprog_80056D8C.c __block1530) hard-cuts `light < 8 -> 0x3C000000`
(BLACK vertex), whole hedge/tree polygons flipped BLACK <-> lit — the
reported two-state bush color flicker. 55 vertices crossed the cliff
back and forth within a 19-frame window at t=23.0..23.3 on
updated_test_camdat.json.

## 2. THE VERBATIM FIX (fog_poc.c sh_env_sync_live)

The per-frame `sh_env_update_pose` call is REMOVED. The light pose is
now updated ONLY inside `sh_env_tick` — the 30 Hz Gfx_EffectsUpdate
cadence, using the tick-time camera exactly like the engine — plus
once before the first tick (`ticksDone == 0`) to model the engine's
first-frame Gfx_EffectsUpdate (which runs before any 30 Hz boundary
elapses). NO engine math is altered; only the update CADENCE becomes
engine-exact. The same fix is mirrored in camtrack_v8.html
(`ShEnv.syncLive`).

Result on the mandated repro: cliff multi-crossers 55 -> 13 (the 13
remaining are boundary-sitters the engine itself produces — their
amplitude is <= 9 luma, invisible under the 24-level brightness floor);
once-crossers 127 (the monotonic cone sweep — correct engine motion).

## 3. What the remaining temporal signal IS (measured, not guessed)

  * THE CULL FLAP: ~190 mesh quads flip the engine gte_NormalClip
    backface cull state >= 2 times over the window. The engine computes
    the SAME nclip on the SAME RTPT SXY lattice values (1 px at 320 =
    the PoC's 2 px at 640), at the same real-time lattice-crossing
    rate; at 30 Hz sampling 159 quads still flap — engine-verbatim
    behavior ( skinny edge-on quads: a single 2 px snap step swings the
    cross product by +-2*arm ~ +-258). The JS reference does not cull
    at all (three.DoubleSide) — which is why it flaps less; that is a
    JS deviation, not engine truth.
  * THE FAR-FENCE SHIMMER: thin-line aliasing at the snap lattice —
    present in the reference captures too (its lower-right bush-crop
    big-alt count ~1750 px vs our ~2170; the delta is the cull above).
  * The 5-bit dither crawl and the snow field: authentic PSX/hardware.

The JS's own listed bugs are fixed in camtrack_v8.html:
  1. the same 30 Hz light-pose cadence (ShEnv.syncLive);
  2. the faithful RT now renders whenever a track is active (v7 gated
     it on the PiP box being visible — a hidden panel left the RT
     STALE across seeks: the "RT render issues during seeks");
  3. the track selection survives reloads/model re-registration
     (restoreAutosave + setActiveModel preserve it — the "track
     selection clearing" that cascaded into the PiP toggling off).
The v7 "posA scope" report does not reproduce in the shipped v7 file
(the perVertexPass posA/pX usage is in-scope and error-free; verified
headless with zero page errors across mode switches and seeks).

## 4. Regression proof (all re-run this session)

  * verify.sh — V2 determinism/bridge/turn filter, V3 camera audit
    (30 tracks x 401 rows, 0 mismatches), V4 env/light 539-sample
    0-mismatch + blend audit + night determinism/bridge + day
    flashlight gate, V5 camdat boot == explicit flags + day goldens
    BYTE-IDENTICAL, V7 wobble default ON + snap grid, V8 (all 21
    presets, listmodes, rain, weather ticks, lensflare, dynamic fog
    {6,5}, lightning), V7-window live env tick — ALL PASS.
  * tools/v10_bug_repro.py + tools/v10_stress_test.py — ALL PASS.
  * 21-mode render sweep — all OK.
  * v17 vs v18 pixel deltas: DAY byte-identical; night at ON-TICK
    times (t=5, 7, 10.5) byte-identical; night at OFF-TICK times
    (t=23.16) mean 0.32 / max 9 — exactly the intended pose-hold
    change and nothing else.
  * FOGPOC_LIGHTDUMP (new): per-frame light-pose + per-vertex light
    dump for audits (gated by the env var, zero effect when unset).

## 5. Build & toggles

  * Linux: gcc -O2 -std=c99 -Wall -Wextra -Wno-unused-parameter —
    zero warnings. Windows: zig cc -target x86_64-windows-gnu — PE32+,
    GDI32/USER32/KERNEL32 only.
  * Hardware defaults unchanged: wobble ON, dither ON, particles ON,
    engine ON — every PSX quirk toggleable, authentic behavior default.
