# CHANGES — PoC v10 (fog fix / flashlight gate / env freeze)

Three runtime defects reported against the v9 build, each fixed with
100% decompilation-derived logic. **No manual patches. No engine math
altered. No GLB/GLTF modification.** Every fix below names its engine
source; every claim below was reproduced, fixed, and re-tested with
hard evidence (log + per-tick env dump + byte-level A/B renders).

--------------------------------------------------------------------------------
## 1. THE BROKEN NORMAL FOG (MAJOR) — FIXED

### Symptom
Any DAY-stage boot (`--day`, `--worldstage 1`, or a camdat with
`nighton:false`) rendered a black, unlit, fogless scene: mean RGB
[24.6, 28.5, 21.6] at t=10.5 versus the working PoC v3 baseline
[91.5, 86.2, 97.0]. The v8 binary reproduced the identical broken
render — the defect shipped since v5 and was surfaced by v9's new mode
browser (day modes finally reachable with one keypress).

### Root cause (fog_poc.c boot, v5-v9)
```c
int fogEnabled = fogForced >= 0 ? fogForced
                                : ((nightBoot || cd.fogon) ? 1 : 0);
```
The renderer's fog flag was keyed on the camdat `fogon` hint OR'd with
the night-boot hack. The shipped camdat.json carries `fogon:false`
(md5 3c7bee91..., unchanged since v8), so every day-stage boot got
`fogEnabled = 0`, which:
- skipped the ENTIRE per-vertex light+fog block (`if (R->fogEnabled)`),
  leaving neutral vcol=128 "raw unlit" geometry, and
- swapped the clear color to (16,16,16).

Why the test suite never caught it: the v5 day goldens are generated
with an explicit `--fog` (fogForced=1), and the v8 "21 presets render"
check only asserts the PNG exists. The v9 A/B compared the v8 binary to
the v9 binary — both identically broken on day boots, so they compared
byte-equal. BLACK == BLACK is not a pass; it hid the defect.

### Engine truth (the fix, 100% decomp-derived)
`WorldEnv_FogLightingParamsUpdate` (world_effects.c:881):
```c
WorldEnv_FogParamsSet(arg0->effectsInfo.field_E != 0,
                      arg0->effectsInfo.fogColor.r, ...);
```
The engine has NO global fog flag. Fog presence is ALWAYS the current
preset's `field_E`, recomputed by every `Gfx_EffectsUpdate`. The PoC's
env side already implemented this verbatim
(`env->isFogEnabled = cur->effectsInfo.field_E != 0`); only the renderer
flag's boot default diverged.

### The change
```c
int fogEnabled = fogForced >= 0 ? fogForced : 1;
```
The renderer fog flag defaults ON; `--nofog` and the M key remain the
ONLY debug overrides (the documented raw-unlit-textures look). The
camdat `fogon` flag (a CamTrack-Editor per-model consumer hint) is now
informational: `nighton`/`flashlighton` still pick the BOOT env pair /
flashlight state, `fogon` no longer gates anything — exactly the
engine's division of concerns.

### Proof
- v10 default day boot == v9 `--day --fog` render, BYTE-IDENTICAL (the
  lineage's known-correct fog reference, which all v5+ goldens used).
- Day render now shows the authentic preset-1 fog: color {108,100,116},
  full fog at 13.5 m; the 21-preset matrix and night/flashlight paths
  are untouched (see section 4 — 55/55 byte-identical A/B).
- verify.sh ALL PASS (day goldens included).

--------------------------------------------------------------------------------
## 2. THE FLASHLIGHT GATE ("permanently off") — FIXED

### Symptom
After changing environment modes, the flashlight could end up
permanently off: F pressed, "[env] flashlight ON" printed, yet the beam
never appeared.

### Root causes (two, compounding)
(a) **Wrong gate.** v5-v9 gated the F key on the preset flag
    `SpecialEnvEventFlags_FlashlightAllowed`
    (`cur.effectsInfo.flags[0] & SHENV_FLAG_FLASHLIGHT`). On
    flag-bearing IDENTICAL pairs ({3,3}, {9,9}, {16,16}, {18,18}, ...)
    F was ACCEPTED and then silently auto-off'd by the engine rule
    within one 30 Hz tick (<=33 ms) — the flashlight could never light.
    Reproduced: envDump shows `isFlashlightOn` 1->0 at tick 154 right
    after an accepted toggle.

(b) **Frozen ramp.** With the env clock stalled (bug 3 below), a
    toggled-on flashlight never ramped: `flashlightIntensity` stayed 0
    because `Gfx_EffectsUpdate` never ran.

### Engine truth (the fix, 100% decomp-derived)
The player-facing flashlight toggle is the inventory On/Off command,
refused EXACTLY when the two current presets are pointer-equal:
- item_screens_2.c:1267:
  `if (!g_SysWork.field_2388.isFlashlightUnavailable || ...id != InvItemId_Flashlight)`
- `isFlashlightUnavailable = (preset0 == preset1)` — Gfx_MapEnvStepUpdate
  (world_effects.c:316-326).
- The auto-off while a pair stays identical in gameplay state:
  bodyprog_effects_8005E0DC.c:650
  `if (isFlashlightUnavailable && sysState == 0) Game_TurnFlashlightOff();`

`SpecialEnvEventFlags_FlashlightAllowed` (game.h bit 1) gates BGM layers
(Map_RoomBgmInit_*), monster AI (stalker/nurse/romper/creeper/larval/...),
particle.c:4293, map5_s00 draw, and the lightning +0.3 spot
(world_effects.c:443-445) — verified across EVERY use site in the decomp:
it NEVER gates the player toggle. (The v9 MODES_GUIDE repeated the old
wrong claim; corrected in v10 with the full use-site list.)

### The change
```c
static int sh_env_flashlight_allowed(const ShEnv *env) {
    return !env->isFlashlightUnavailable;
}
```
F now works on EVERY mixed pair and is refused UP FRONT (with the
engine's reason and citations in the message) on identical pairs — the
verbatim inventory rule. The auto-off rule itself is unchanged and
engine-exact.

### Proof
- Repro log: `flashlight REFUSED — identical env pair: the engine marks
  the flashlight unavailable (item_screens_2.c:1267; ...)` at {3,3};
  `flashlight ON` accepted at mixed {7,4} and the fade ramps 0->4096.
- Stress test: 2 complete ramps to fi=4096 including AFTER crossing the
  track wrap; 0 stalled ramps across 240+ mode changes.

--------------------------------------------------------------------------------
## 3. THE ENVIRONMENT FREEZE ("stuck after too many changes") — FIXED

### Symptom
After running a while (and changing modes), the environment appeared
stuck: mode changes stopped affecting the render, the flashlight stayed
dead, and nothing recovered until restart.

### Root cause (fog_poc.c `sh_env_sync_live`, v8+v9)
```c
while (t - env->lastTickT >= 1.0 / 30.0 - 1e-12) { ... }
```
The camtrack session clock WRAPS at the cycle boundary
(`playback_step`: `if (P->t >= T) P->t = fmod(P->t, T)`, T = 49.8787 s
for the shipped track). After any wrap (or backward scrub), `t -
lastTickT` goes NEGATIVE and the 30 Hz tick loop never fires again until
t re-advances past lastTickT — a FULL ~50 s freeze, repeating at EVERY
wrap. During the freeze: `Gfx_MapEnvSet` still updates the pair slots
(the log even prints the mode change) but `field_154` (the live blend)
never re-blends and `flashlightIntensity` never ramps — the env looks
dead. Reproduced: envDump tick counter stalled at 1468 (48.93 s, the
wrap boundary) while frames kept rendering.

The SNOW system already had the correct backward-jump guard
(`snow_sync_live`: `t < S->lastTickT - 1e-9` -> reset); the env system
lacked its mirror. The engine's game clock is monotonic
(`g_DeltaTime >= 0`) and its env state is persistent game state — the
PoC's session clock wrap is a playback-layer artifact.

### The change
```c
if (t < env->lastTickT - 1e-9)
    env->lastTickT = t;   /* resync the tick boundary; carry ALL env
                             state (pair slots, blend, flashlight ramp)
                             over untouched */
```
Mirrors the snow system's guard. NO engine tick math altered.

### Related wrap-family bugs found & fixed in the same pass
- **`--shot t>49.88 s` never terminated** (v9: infinite loop — the shot
  fast-forward keyed its terminator on the WRAPPING phase, `tCur = P.t`;
  confirmed: v9 killed by timeout after 20 s with no PNG, v10 writes the
  shot). Fixed with a monotonic session accumulator (`tSim`) driving the
  loop; identical step sequence for all existing shot times (< T), so
  every golden stays byte-identical.
- **`--duration > 49.88 s` never self-terminated** (`live_done` compared
  the wrapping phase to the duration). Fixed: `Playback.sessionT`, a
  monotonic session clock advanced in `playback_step` (never wrapped),
  now drives `live_done`, the benchmark end-clamp, and the save-final
  boundary phase (`fmod(duration, T)` beyond one cycle — the same phase
  `--shot` renders).
- `--shot`/`--benchmark` env simulations crossing the wrap previously
  froze mid-simulation (same while-loop root cause) — also fixed.

### Proof
- Repro (post-fix): envDump runs 2370 ticks through the wrap (was: dead
  at 1468); post-wrap mode changes re-blend; post-wrap flashlight ramps.
- Stress test: 240+ mode changes + 4 wrap crossings + 20 weather
  transitions + browser/HUD cycling in ONE session -> 7758 env ticks,
  zero non-positive tick steps, zero stalled ramps, flashlight recovery
  at a mixed pair works at the very end. INFINITE CYCLING PROVEN.

--------------------------------------------------------------------------------
## 4. ZERO-REGRESSION PROOF (v9 baseline preserved)

Pristine v9 shipped binary vs v10 build, same args, byte-compared PNGs:

- **55/55 BYTE-IDENTICAL**: default boot (camdat nighton/flashlighton),
  night {6,3} and nightmare {7,4} each with flashlight ON and OFF, ALL
  21 presets (self-pairs 0..20), ALL 24 authentic pairs ({6,10} {6,5}
  {6,6} {19,4} {6,12} {6,20} {7,9} {7,7} {14,14} {11,11} {17,17}
  {10,10} {15,15} {16,16} {18,18} {4,4} {3,3} {13,13} {5,5} {9,9}),
  rain (--weather 6), snow+ (--weather 2), enum-2 lens flare
  (--envpair 2,2 --lensflare 3), lightning, modern (no-wobble) day and
  night, worldstage 3, the 6 s benchmark<->shot bridge, and the
  720-frame realtime bridge (t=12, mid-playback).
- The only two intended divergences: the `--day` boot (v9 black/broken
  vs v10 correct engine fog — THE fix) and `--shot t=60` (v9
  infinite-loops, v10 renders).
- verify.sh: ALL SUITES PASS (36 PASS/IDENTICAL assertions, 0 failures)
  — determinism, camera bridge, turn filter, wobble grid, day goldens,
  night states, boot equivalence, 21-preset render matrix, listmodes,
  rain, env ticking, lens flare presets, dynamic fog, lightning, window
  env tick.
- GLB UNMODIFIED: input/THRF9FD.glb md5 c7183184d20a2508ce41af2702629a33
  == the locked baseline (also identical inside v3/v8/v9 trees).

--------------------------------------------------------------------------------
## 5. FILES CHANGED

- `src/fog_poc.c` — the four fixes (fog boot default, flashlight gate,
  env backward-time resync, monotonic session clock family) + comments
  citing the engine sources; help/banner text updated. NO engine-math
  functions touched (Gfx_* ports, blend machinery, snow/rain, camera,
  GTE all byte-identical code paths).
- `MODES_GUIDE.md` — FlashlightAllowed fact corrected (full use-site
  list); F-key rule updated; v10 stability note added.
- `README.md` — v10 banner; camdat flag semantics updated.
- `CHANGES_v10.md` — this file.
- `RUN_ME.bat` — title comment bumped to v10.

Everything else (Makefile, verify.sh, tools/, input/ assets,
reference_shots/) is the verified v9 set, unchanged.
