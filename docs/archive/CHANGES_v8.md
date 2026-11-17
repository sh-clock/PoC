# poc_v8 — the COMPLETE world-effect audit release (read this first)

v8 completes the world-effect coverage against the decompilation. Everything
below is ported VERBATIM from `silent-hill-decomp`; the GLB/GLTF assets are
UNMODIFIED (SHA256 unchanged); every v7 golden render is still BYTE-IDENTICAL
(full `verify.sh` suite re-run: 22/22 PASS, including the camera ground-truth
audit and the byte-identical day references).

## What v8 adds

1. **ALL 21 MAP_EFFECTS_INFOS presets** (map_info.c) embedded verbatim — v7
   carried 5 (1/6/3/7/4); v8 adds 0, 2, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16,
   17, 18, 19, 20 (incl. every non-0xFF maxBrightness, the red/rust/blue
   tints, the only enum-2 preset, the dynamic-fog preset, the lightning env).
   `--listmodes` prints the whole table; `--envpair A,B` sets ANY pair via
   the verbatim Gfx_MapEnvSet; `--worldstage N` applies WorldEnv_MapPresetSet
   (1 day {1,1} / 2 night {6,3} / 3 {9,9}); `--nightpair` now accepts all 21.
2. **RAIN** (maps/particle.c, the whole pass-1 bank): spawn (type Rain,
   y=-6m+rand(0..2)m, speed Q12(0.03675), gravity 30/tick), movement (the
   Vectors1 view-delta anchoring, ±6m L1 box, ground contact), the THREE
   draw states — falling streak (3x16 sprite u10..13 v112..128, clut rows
   104+(z>>5)/0x1A30, prim = field_25 - fog>>5 u8-wrap), landing splash
   (16x16 sprite u16..31, the state<<sp64 ground diamond, color 0x80-c,
   sp64 = 3/4/5 by rain intensity), roof/puddle drip (c+0x18 blue streak) —
   all sprites/CLUTs extracted VERBATIM from the original BG_ETC.TIM
   (src/rain_tim_data.h, tools/extract_rain_tim.py). The rain intensity
   ramps with the bank count (E32D0, clamp 135000).
3. **The weather state machine**: Particle_EnvironmentSet (args 0/1/2/5/6,
   the arg1==2→3 quirk, the E0CB0 bit packing) + sharedFunc_800D0A60 +
   sharedFunc_800D0B18 (the E0CB4 target re-pack, transcribed verbatim incl.
   the 0xE38 bit alchemy) + the Particle_SystemUpdate SINE TRANSITION driver
   (512-tick bank cross-fade, Math_Sin from the VERBATIM g_SineTable LUT
   extracted from libkmath.s — src/sh_sine_table.h). The W key cycles
   snow→rain→none exactly like map0_s00_2.c:1679 (the intro street's own
   weather event); `--weather N` boots the map-load recipe instantly.
   Verified: the snow bank follows 2·(sin(180°+t·2)·150+150) EXACTLY.
4. **enum-2 directional light** (func_80057A3C) — the interior-day N.L path,
   including the engine's `gte_ll` = MVMVA{LLM, V0, tx=FC} encoding whose
   FC-translation hardware BUG drops the M[0][0]·Vx term (byte-accurate
   DuckStation MulMatVecBuggy). The light direction comes from
   func_8003F4DC's lens-flare preset table (--lensflare 0..5; the engine
   reads road data absent from the room rip — Default = lightWeight 0, the
   authentic ambient-only interior).
5. **field_E=3 DYNAMIC FOG** (Gfx_EffectsUpdate lines 405-410) — preset 5's
   fog wall rides at the light's view-space depth. With HERO == the camera
   the engine value is the CONSTANT Q12(0.12) = 491 (the bone-local offset
   z; the camera's own view matrix is identity): total fog, engine-exact for
   the camera-anchored light. `--envpair 6,5 --flashlight` shows it.
6. **LIGHTNING flashEffect** (Gfx_EffectsUpdate lines 434-447 +
   func_8003EDA8): the L key / `--lightning` arms the one-frame env flash —
   dark envs swap to preset 8 for exactly one tick (verified in the env
   dump: spot 1433, maxB 80, fog 8m, wLI 1638), flashlight envs get
   +Q12(0.3) spot. (The bolt SPRITE actor needs overlay-script data absent
   from the room rip — documented exclusion.)
7. **GTE corrections (byte-accuracy)**:
   - IR0/`dp` clamp fixed to DuckStation's [0, 0x1000] (was [0, 0x7FFF];
     no pixel change for any real preset — max dp = 1280).
   - Flashlight beam constants fixed to the LUT-exact sin/cos(-170) =
     -1056/3958 (was true-math -1061/3957 — a 0.4% direction error; the
     engine quantizes the angle to -170/4096 turn first). Flashlight-ON
     night renders change microscopically; all day / night-off / wobble
     renders are byte-identical.
8. **Shot-path fog fix (latent v7 bug)**: `--shot` rendered with the
   boot-state fog ramp while the env simulated on a copy — invisible for
   every v7-reachable pair (all black-fog), but wrong for the new colored/
   dynamic modes. R.fog now follows the simulated env; all v7 goldens stay
   byte-identical (re-verified).

## Keys added

`W` weather cycle (snow → rain → none, the sine cross-fade) · `L` lightning
flash. All v7 keys unchanged (`N` env cycle, `F` flashlight, `M` fog, `B`
snow, `P` PSX wobble, `S` screenshot).

## Verification (v8 suite additions)

* v7 full suite re-run: **22/22 PASS** — day references t=0/10.5/20.5/31.5/
  41.5 + mid-turn BYTE-IDENTICAL; camera ground truth 30 tracks × 401 rows,
  0 mismatches; env math 539/539; env blend 181/181; wobble default ON,
  0 off-grid vertices; window env ticks live.
* Rain renders: 217/300 drops collected in-frame; rain vs no-weather pixel
  delta 0.699% (authentic subtle day rain, base field_25 = 14/14/30); VLM:
  "thin vertical rain streaks clearly visible, no glitches".
* Weather transition: snow bank follows the engine sine EXACTLY
  (300→218→192→166→142 over 90..240 ticks = 2·(sin(180°+t·2)·150+150));
  rain ramps 0→300; intensity 272→712→1454→2564.
* Lightning: env dump shows the one-tick preset-8 swap (spot 1433, maxB 80,
  fog 32768, wLI 1638 — MAP_EFFECTS_INFOS[8] verbatim).
* enum-2: lf0 vs lf3 differ 10.65% of pixels (the directional light works);
  VLM confirms visibly different light directions, no glitches.
* Dynamic fog {6,5}: cur.fogDistance blends 57344→491 at full flashlight
  (the engine constant); the render shows the plum wash (68,60,76)+28.
* 12-mode gallery (rain day/night, enum-2, dynamic fog, dusk, thick,
  nowheres, red, interior, {19,4}, lightning) — all coherent, VLM-verified.

## Build & run

Linux:      `make` → `./fog_poc` (or `./fog_poc --listmodes` first)
Windows:    `zig cc -target x86_64-windows-gnu -O2 -std=c99 -o fog_poc.exe
            src/fog_poc.c -luser32 -lgdi32` (or MinGW-w64 via Makefile.mingw)
Run:        no arguments = the v7 default (NIGHT + flashlight + snow + PSX
            wobble ON). Try: `--weather 6` (rain), `--envpair 2,2
            --lensflare 3` (enum-2), `--envpair 6,5 --flashlight` (dynamic
            fog), `--night --lightning` (L for more), `--worldstage 3`.

GLB/GLTF assets: UNMODIFIED — input/THRF9FD.glb SHA256
74624abcb72ae0e65a4b3b53a5816a5543b7baadd1d25ea85f1c116fa7e4023d (identical
to the v7/v6/v4/agent_upload baselines).
