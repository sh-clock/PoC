# CHANGES_v20 — THE NIGHT+FLASHLIGHT FLICKER FIX (the engine 30 Hz tick lockstep)

## THE REPORTED BUG

Severe bush/vegetage color strobing — **only** with the flashlight
equipped in NIGHT mode (no flicker in fog modes, none in night without
the flashlight). The prior v17 agent attributed the residue to an
"engine-authentic `light < 8 -> BLACK` cliff" — **rejected by the user**:
the real game does not flicker like this.

## THE INVESTIGATION (decomp + DuckStation + measurement)

1. **The cliff is real but NOT the driver.** Gfx_MeshDraw `__block1530`
   (bodyprog_80056D8C.c:1281-1317) really does write `0x3C000000`
   (BLACK vertex color) when the per-normal u8 light < 8 on the
   fog-off/enum-1 path — but a 19-frame lightdump shows only 13 of 5209
   mesh vertices strobe across the 7/8 boundary. The cliff is authentic;
   the strobe amplitude came from elsewhere.
2. **The engine cadence, verified in the decomp (the full chain):**
   - `game_main.c` MainLoop: one iteration = one game tick; gameplay
     waits `g_IntervalVBlanks` VBlanks.
   - `GameState_InGame_Update` (game_sys_states.c:93) sets
     **g_IntervalVBlanks = 2** -> the IN-GAME state runs 30 fps in
     lockstep (menus use the screen_data.c:71 default 1 = 60 fps).
   - Per tick: `vcMoveAndSetCamera` (camera), `Gfx_EffectsUpdate` ->
     `Gfx_FlashlightPositionUpdate` (light pose — **no 30 Hz sub-gate,
     no 60 Hz update**), `particleSystemUpdate` (snow), then the OT
     build + `GsDrawOt` — ALL on the same tick state. The engine never
     renders an intermediate camera position.
3. **The PoC's defect (the actual flicker root cause):** the render
   paths stepped the CAMERA every 60 fps output frame
   (`playback_step dt = 1/60`) while the env/light/snow tick on the
   30 Hz grid. The odd frames rendered an interpolated camera against
   the STALE tick light pose — a light-camera offset oscillating by up
   to 1/60 s of camera motion. Measured: bush 16x16 block-MEAN changes
   of median 2.4 / p90 12.0 per **16.7 ms** — as large as FULL 33 ms
   tick changes = pure 60 Hz oscillation, not motion crawl. That
   oscillation modulated the per-cluster billboard colors and the
   per-vertex mesh light at 15-30 Hz = the visible strobing (VLM 9/10
   "violent strobing, clusters invert between dark and bright
   lime-green").

## THE FIX (verbatim engine update model — NO rendering math touched)

`live_advance()` + `playback_current_pose()` (fog_poc.c, v20):
- The playback session (camera + turn filter) advances ONLY on whole
  30 Hz tick boundaries (`playback_step dt = 1/30` — the engine tick
  dt), each tick syncing the snow + env with the tick camera.
- Output frames rendered before the next boundary re-render the LAST
  tick state — at 60 fps output each engine frame displays twice
  (`F(2k) == F(2k+1)` byte-identical), exactly the real game's 30 fps
  content on a 60 Hz display.
- The pending accumulator is capped at 2 ticks (the engine's
  V_BLANKS_MAX = 4 catch-up clamp, game_main.c).
- All render paths converted: the three realtime loops (Win32/SDL/X11),
  `run_benchmark`, and the `--shot` fast-forward (whole ticks only; a
  shot at a non-boundary time renders the tick state the engine would
  still be displaying — the frame drawn at tick k displays for the
  whole `[k/30, (k+1)/30)` interval).
- `K_R` restart resets the tick grid; scrub/wrap keep the established
  v10 semantics (orientation continuity, env/snow carry-over guards).

## THE PROOF (multi-frame, `updated_test_camdat.json` @ t=23.0..23.3)

| metric | v19 (before) | v20 (after) | real game (ref pair) |
|---|---|---|---|
| frame-pair big24 pattern | ~10% every frame (60 Hz oscillation) | **0.0% / ~13-16% alternating** | 14.1% (50 ms) |
| intra-tick drift (bush block-mean) | up to 12 per 16.7 ms | **0.000** | — (no intra-tick frames exist) |
| inter-tick change magnitude | — | **13.6% median** | 14.1% |
| change-blob structure (median/p90/mean) | — | **1 / 15 / 11.6 px** | 1 / 15 / 12.1 px |
| ground block-match displacement | — | **identical vectors** | (reference vectors) |
| mesh L sequence per tick | oscillating (v18 grid jitter) | **monotonic** 68,68,70,70,73,73... | — |
| VLM temporal rating | 9/10 violent strobing | **"moderate per-pixel shimmer typical of PS1; NO whole-cluster toggling"** | — |
| VLM acceptance @23.16 vs live_00023.16.png | — | **"PASS / FAITHFUL REPRODUCTION"** | — |

Static zone ratios vs `live_00023.16.png` (flashlight ON): ground center
1.014, left ground 0.994, fence 0.975, bush 1.076 — the flashlight math
(whose hotspot radial profile matches to 1.008) is untouched.

## THE v19 GRID/LATTICE FIXES (kept, this cycle)

- **The 30 Hz tick grid** (integer boundary counting — no float drift):
  the env ticks fire exactly at t = k/30 (the double-accumulator drift
  of v18 produced double ticks on consecutive frames).
- **The engine pixel lattice** at wide outputs: uniform
  `enginePixScale = w/320` with `enginePixScaleY = h/240` — the
  DuckStation "stretch" presentation lattice of the 320x240 engine
  buffer (a 2 px uniform crop lattice was tested and rejected: static
  diff 27.3% -> 33.0%, temporal identical).

## REGRESSIONS (all pass — scripts/regress_v20.sh)

- 21 presets render clean; dither + wobble default ON (flags verifiably
  active); night darkness (25.1 vs day 82.8); fence stability with the
  flashlight OFF (worst per-tick big24 2.10%); the flashlight verbatim
  math unchanged (hotspot radial identical); fog modes unchanged
  (fog-off/DPCL/DPCS/veil paths untouched — only the update CADENCE
  changed); benchmark smoke (300 frames).

## KNOWN OPEN ITEMS (the Discrepancy Ledger)

- **Distant lamp glow specks**: the reference shows 5-8 STATIC bright
  (224,224,232) 2 px specks in the far scene (distant streetlights) where
  the PoC renders ~24-107. No mesh vertices exist there (lightdump); not
  the dust/ash system (func_800CD8E8 anchors ~320 m away — not drawn);
  not the road-data lens flare (camera system). Explains most of the
  far-center 0.737 static ratio. Small but real; left open.
- **Bush zone +7.6% static brightness**: attributed to the
  camdat-vs-reference camera difference (block-matching measured the
  reference session camera at ~1.12 m/s vs the camdat's 1.70 m/s; the
  flashlight-cone gradient position depends on the camera; with the
  60 Hz camera at exactly 23.16 the ratio was 1.11, with the tick
  camera 1.076 — converging toward the reference as the camera
  matches).
- **Snow flake brightness**: the NORMAL flakes match the reference
  exactly (66-107 both; counts 75/64). The earlier "ref 255 vs PoC
  181" note was measuring the distant-lamp specks (see above), not snow.

## CAMDAT / EDITOR INTEROP

The camdat env object (`pair`, `weatherTarget`, `bootWeather`,
`lensFlare`, `flashlightOn`, `psxWobble`, `dither`, `particles`,
`engine`) is unchanged; the playback now consumes it at the engine's
30 Hz cadence (the camtrack_v9/v10 editor applies the same lockstep in
its faithful RT preview).
