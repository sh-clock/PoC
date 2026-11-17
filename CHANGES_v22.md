# CHANGES_v22 — the authentic 30 fps presentation lock (+ camtrack v11 tick-grid preview)

This release fixes the two issues the user reported against v20/v21:

1. **"The FPS meter reports 111 FPS"** — v20/v21 measured the BUSY render
   time only (the t1-t0 sample was taken BEFORE the frame limiter slept),
   so the title bar reported the render throughput (111 fps at ~9 ms/frame)
   while the actual presentation was capped at 60 with UNEVEN pacing.
   The original game NEVER ran above 30 fps in-world: `g_IntervalVBlanks
   = 2` (game_sys_states.c:93) — one game tick per TWO VBlanks on the
   60 Hz NTSC field rate. The live window now PRESENTS at strictly 30 fps
   (one present per engine tick) and the meter reports the TRUE wall-clock
   presentation rate: **30.0**.

2. **"Flickering is STILL present and very noticeable"** — root-caused with
   the new disc-rip ground truth and a motion/flicker separation analysis
   (see CHANGES sections 2-4). The rendering was already engine-exact
   (byte-identical tick content to v21 — verified); the perceived flicker
   came from the irregular uncapped/60-cap presentation of a legitimately
   fast-moving close-up surface. Locked to the engine's own 30 fps cadence
   the same frames read as coherent motion (VLM verdict: AUTHENTIC PS1
   BEHAVIOR).

## 1. The 30 fps presentation lock (fog_poc.c live_pace + the 3 window loops)

- `--fps` default 60 -> **30** (the engine's in-game cadence). `--fps 60`
  remains available as the documented 60 Hz display-duplicate presentation;
  `--fps 0` = unlimited (benchmarking).
- `live_pace` now holds the FULL frame budget: 1 ms sleeps, then yields,
  then a sub-0.5 ms spin (the old code broke 0.4 ms early, running ~1.2%
  fast and drifting against the tick grid).
- The FPS meter (Win32 / SDL2 / X11 loops) measures render + present +
  pace — the true presentation rate. FOGPOC_FPSDBG prints it to stderr.
- Measured under Xvfb+SDL2: an 8 s track-duration live run takes 8.303 s
  wall (v21 would finish in ~2.5 s); the meter prints
  `presented=30.0 fps (cap 30)` for the whole run.
- **The tick content is BYTE-IDENTICAL to v21** (same-tick renders compare
  max-diff 0): the lock is presentation-only, zero rendering math touched.
- The benchmark label now reads "sim throughput, NOT the 30 fps
  presentation" (it simulates as fast as possible by design).

## 2. Disc-rip investigation: 23.01 vs 27.45 root cause

Downloaded the user's own rip from /sh1/sh1rip (BG/THRF9FD.IPD,
BG/THR_GLB.PLM, BG/THR0004F.TIM, THR0001F.TIM, THR7201F.TIM) — the IPD and
PLM are md5-identical to the files the GLB was converted from (the
extractor's input data is authentic).

- **Both timestamps are the SAME room (THRF9FD)** — the difference is
  LOCAL geometry, parsed from the rip (scripts/analyze_ipd_zones.py):
  - t=23.01 (return leg, pos (-256.25, 1.29, 99.66), looking +z): the
    frustum contains the THR0004F fence (stp=1) AND full-height
    THR7201F-stp=1 walls (THR7203 / 7203_30_ / 7203_18_, 3.4-5 m, the
    full right side of the screen).
  - t=27.45 (pos (-256.32, 1.17, 107.19)): the fence ONLY — no stp=1
    walls in view at all.
- Zone measurement of the old-verified reference pair (23.11->23.16):
  changes concentrate exactly where the walls + fence-overlap project
  (right half big8 39.8%; clean sky ~0.6%). The real game's "minor flicker
  at 23.01" is the wall/parallax zone; the fence-only view at 27.45 has no
  such term. NOTE: live_00023.*.png carry the old PoC's own HUD text —
  they are old-PoC captures (the user-approved v3-era look), not
  real-game frames; all real-game conclusions here come from the engine
  code + the rip data.

## 3. The engine's fence semantics — CONFIRMED EXACT (no rendering change needed)

- ALL 27 objects placed in THRF9FD route to Gfx_MeshDraw (model-header
  byte @11: field_B_0=0, field_B_4=0 for every object — the stp-honoring
  func_8005AC50 path is never taken in this room).
- In the night+flashlight fog-OFF mode (pair {6,3}, the camdat's
  fogon=false) Gfx_MeshDraw's __block1530 draws EVERY quad as code 0x3C
  OPAQUE GT4 — the pack's stp bit is IGNORED (setSemiTrans only appears
  in the colored-fog composite paths). DuckStation confirms: texel ==
  0x0000 -> not drawn (punch-through); blending needs the primitive ST bit
  AND the texel STP bit — for 0x3C, STP texels render fully opaque.
- THR0004F's CLUT: rows 0-13,15 are all-STP entries (no 0x0000 anywhere);
  the fence packs' cba selects ROW 14 — the only row with a 0x0000 entry.
  The fence is therefore a SOLID PAINTED OPAQUE surface with scattered
  punch-through holes (6.01% of the texture, 10.9-43% inside the pack UV
  windows). The v21+ raster (`ta == 0 -> skip; ta > 0 -> opaque`)
  implements exactly this.
- The extractor was verified PIXEL-EXACT against the rip: the GLB's
  THR0004F_pal14 texture hole map is IDENTICAL to the rip's row-14 decode
  and 2054 spot-checked texels match the BGR555 + PS1 DAC bit replication.
  v10ipd2gltf.py is accurate — no extractor changes were required.

## 4. The flicker/motion separation (why the lock is the fix)

- Temporal measurement (ticks 690-699 / 820-829, native 320x224): the
  fence close-up changes ~51%/tick — and it does so IDENTICALLY with
  `--modern` (perspective-correct float, no snap/affine/dither). The
  "boil" is MOTION-driven: the camdat camera passes 1-1.5 m from the
  fence at 1.7012 m/s, sweeping the 1-2 px texel pattern by 3-9 px/tick —
  any faithful renderer (including the real hardware at that camera path)
  decorrelates the sampled pattern every tick.
- The engine-exact question is therefore PRESENTATION: the real game
  presents these frames at a strict, even 33.33 ms cadence (2 VBlanks per
  tick), where the sweep reads as coherent directional motion. The v20/v21
  meter/pacing bugs (111 fps report, 0.4 ms-early frames at a 60 fps cap)
  presented the SAME frames at irregular intervals — reading as chaotic
  flicker. v22 locks the presentation to the engine's own cadence.
- Per-vertex light dump (FOGPOC_LIGHTDUMP): 17/1762 vertices show small
  (±1-4) non-monotonic steps — the flashlight lighting itself is
  essentially monotonic, not an oscillation source.

## 5. camtrack v11 (the editor preview respects the 30 fps cadence)

camtrack_v10 -> v11 (APP_VERSION 1.2.1 -> 1.3.0):

- `tickPlayback` now advances the session on the ENGINE 30 Hz TICK GRID
  (fog_poc.c live_advance, verbatim): state.t steps only on whole 1/30 s
  boundaries, the pending accumulator clamps at 2 ticks (V_BLANKS_MAX),
  per tick t += (1/30)*rate, and between boundaries the preview HOLDS the
  tick state (F(2k) == F(2k+1) on 60 Hz displays — the engine renders no
  intermediate camera positions).
- The turn filter steps on tick time only (the PoC's playback_step feeds
  cam_update_track the unscaled 1/30 tick dt); while playing it HOLDS
  between ticks instead of taking the paused-path exact snap.
- 8/8 unit tests pass (scripts/test_camtrack_tickgrid.js): 1/30
  quantization, frame duplication, tickFire alternation, stall recovery,
  rate scaling, wrap, once-stop, paused reset. Browser-verified: clean
  load (no console errors — the v9 `shR` fix holds), GLB load, playback,
  Night {6,3} env, camdat import, lazy look mode present with the 25
  deg/s default, playbar/HUD non-overlap.

## REGRESSIONS (all pass)

- 21-preset sweep at native: all modes render; night dark (mode 6 mean
  25.75 / mode 7 mean 25.08) vs day bright (mode 1: 77.98 / mode 5:
  104.29 / mode 17: 87.24); heavy-fog modes ultra-stable (0.90% / 0.57%
  per tick); no state leaks; max change 35% (mode 0, the fog-off ambient
  with the full 60.875 m draw distance).
- Static zones vs the old user-approved reference (640x360): fence 1.041,
  ground 0.991-1.001, bush 0.991, clean sky 0.997-1.000 (the top-band
  deltas are the reference's own HUD text overlay).
- Dither DEFAULT ON (27.93% pixels differ vs --no-dither); PSX wobble +
  15-bit DEFAULT ON (42.96% differ vs --modern).
- GLB (md5 c7183184...) and IPD (8c8cd3b4...) byte-identical to the CDN
  originals — unmodified.
- lazy lookMode parses/renders/benchmarks; `lookMode: "path"` behavior
  unchanged (same-tick goldens byte-identical to v21).
- VLM multi-frame acceptance (6-frame sequences at t=23.0 and t=27.4):
  flashlight hotspot STABLE, motion SMOOTH and DIRECTIONAL, no wholesale
  region flips, "typical PS1 texture crawl, not objectionable flicker" —
  VERDICT: AUTHENTIC PS1 BEHAVIOR.
- Windows build: zig cc -target x86_64-windows-gnu, static — the exe
  imports only USER32/GDI32/KERNEL32 + the OS UCRT (no external DLLs).
