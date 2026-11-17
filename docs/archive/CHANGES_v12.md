# CHANGES — v12 (Ultimate Verbatimness & Faithfulness Audit)

## Scope

v12 is a full-repository audit release: the ENTIRE v11 source (8,202 lines),
the decompilation weather/effects/lighting core (map_info.c, world_effects.c,
bodyprog_80055028.c, bodyprog_80056D8C.c, particle.c, rng.c, fixed_point.h)
and DuckStation's GTE (gte.cpp) + software rasterizer (gpu_sw_rasterizer.inl)
were read COMPLETELY and compared line-by-line. Every discrepancy found was
fixed in one pass (continuous correction), with the exception of one case
where the literal engine reading contradicts the user-verified v3 fog ground
truth (documented below, behavior deliberately preserved).

## Audit result

### Verified VERBATIM (no action needed)

* All 21 `MAP_EFFECTS_INFOS` presets — field-for-field vs `map_info.c`.
* The fog LUT chain (`WorldEnv_FogDistanceSet`, `func_800559A8`,
  `func_80055814`, `func_80055A50`) and the dual-quad veil compositing.
* The flashlight pipeline: `Gfx_EffectsUpdate` ramp, `func_8003F4DC` light
  directions, `WorldEnv_LightTransform`, `func_80057658` (mesh light),
  `func_80057A3C` (enum-2 N.L with the MVMVA FC bug), `func_80055648`
  (position-query table), `func_80055D78`.
* The snow/rain particle system: spawn, warm-up, movement, rest, draws
  (streak/splash/drip), `Particle_EnvironmentSet`, `D0A60`, the `D0B18`
  bit alchemy, the sine transition driver counts.
* DuckStation: `UNRDivide` (byte-exact), `RTPS`/`PushSXY` truncation, the
  IR0 `[0,0x1000]` clamp, `DPCS`/`DPCL` `InterpolateColor` two-step, the
  `MulMatVecBuggy` FC-bug drop, the texture modulation `T*C/128`, the
  black-texel hole rule, ABR=1 per-5-bit saturating add, the dither matrix.

### Fixed in v12 (all decomp/DuckStation-cited)

1. **`weight - 683` → `weight - 682`** (`sh_env_blend`, enum-2→enum-1 ramp).
   The engine computes `Q12_MULT(weight - Q12(1.0f/6.0f), Q12(1.2f))` and
   `Q12(1.0f/6.0f) = (s32)(0.16666667f * 4096) = 682` (TO_FIXED truncates).
   v11 was off by one Q12 unit. No reachable visual change (no shipped pair
   mixes enum-2 and enum-1 slots — preset 2 is the only enum-2 preset and
   its authentic pairs are {2,2}).
2. **DPCS/DPCL final clamp** — DuckStation `TruncateRGB` reinterprets
   `MAC>>4` unsigned, so a negative MAC saturates to 255, not 0. Made
   byte-exact (unreachable for k ≤ 4096, i.e. every engine-reachable input).
3. **The `800DD592` snow-spawn-type switch** (SystemUpdate i==0 block,
   particle.c:465-545) — now ported verbatim: during weather transitions the
   snow spawn type flips to `ParticleType_Unk1` below the bank-count
   thresholds (76 for target fields 4/6/32/48, 151 for 5/7/40/56), and
   `Particle_Spawn`/`Particle_MovementUpdate` carry the Unk1 branches
   (the separate vy ramp with a fresh RNG draw, no xz drift).
4. **RNG draw order in `snow_tick`** — the engine draws the per-tick rand
   BEFORE the wind ramp; v11 drew it after. Inert while the wind ramp
   consumes no RNG, but windy weather (now exposed) makes 2 draws/tick —
   the order is now engine-exact.
5. **Tail zeroing** (SystemUpdate:583-586) — particles beyond both banks
   get `state = 0` after every update, so grown banks don't resurrect
   stale particles.
6. **`field_234A` transition lock** (`sharedFunc_800D0B18` gate,
   particle.c:3870) — the runtime weather switch is REFUSED while a
   512-tick cross-fade is in flight (re-arms at completion). Also its side
   effects: `field_2349 = arg0` (the snow density selector) and
   `g_Particle_PrevPosition.vy = 2/0` (the Unk1 ramp feed).
7. **Snow density rule** — pass-0 spawn density is
   `(field_2349 == 1) ? 1 : 3` (Particle_Update:1273), not a hardcoded 3.
8. **Wind is now live** — the snow movement uses `g_Particle_SpeedX/Z`
   verbatim (v11 hardcoded 0 because wind was unreachable).

### EXPOSED: ALL weather conditions (multi-map testing)

* **W key now cycles ALL NINE runtime weather states** (was 3):
  `0 none · 1-4 snow wind 0-3 · 5-8 rain wind 0-3` — the complete
  `sharedFunc_800D0B18` argument domain. Wind ≥ 2 activates the engine's
  wind machinery (ramped speeds, windy rest drift).
* **`--weather-target N`** (0..8) boots the RUNTIME transition recipe —
  the same path as the game's own snow→rain street event (`D0B18(6)`,
  map0_s00_2.c:1679) — with the 512-tick sine cross-fade, the 800DD592
  spawn-type switch and the field_234A lock all live.
* (v8's `--weather N` map-load recipe, all 21 env presets, all 24 authentic
  pairs, night/nightmare, lightning and lens-flare types were already
  exposed and remain.)

### Discovered engine/package defects (documented, worked around)

* **D10 — engine latent array overrun**: the game's own `D0B18(6)` target
  packs snow field 40 / rain field 5; both drive bank counts to
  `temp*2` (up to 600 > `PARTICLE_COUNT_MAX` = 300), walking 300 entries
  past `g_Particles[299]` (self-masked in the engine: the driver rewrites
  the counts each tick). v12 keeps the verbatim count math but clamps the
  stored banks to the array bound; v11 had the same latent overrun
  reachable through the W key.
* **D11 — stale goldens in the shipped v11 package**: the v11
  `reference_shots/` documentation set is not reproducible by the shipped
  v11 binary via the `verify.sh` flags (regenerated after the final verify
  run with different flags). v12 regenerates the whole golden set from
  this binary (`nightoff` now correctly uses `--no-flashlight` —
  `--night --fog` and `--night --fog --flashlight` both boot the
  flashlight ON via the camdat default).

### The D2 resolution — engine literalism vs the verified ground truth

A literal reading of `Gfx_MeshDraw`'s STP branch (the semi-trans fog G4 is
added LAST = drawn ON TOP of the textured quad, and DuckStation blends
untextured semi-trans prims on every pixel) implies STP fence HOLES should
also receive the additive veil. Implemented, tested, and REJECTED:

* day street mean RGB: v3 (user-verified ground truth) **93.10**,
  v11 **92.33**, v12-with-hole-veil **125.81** (+33 — washed out);
* VLM (glm-5v-turbo) on the 3-way: LEFT/MIDDLE "essentially identical",
  RIGHT "noticeably brighter and washed-out … breaks the atmospheric
  immersion" — LEFT/MIDDLE best match the classic Silent Hill fog.

The task book designates v3 as the fog ground truth and forbids ANY visual
regression vs v11; the literal reading's premise (which room prims carry
`bits1.flags & 0x8000`) is unverifiable from the GLB (the alpha channel is
the converter's encoding, not the engine's prim flags). The v11/v3 hole
treatment is therefore KEPT, with the full analysis preserved as an audit
note in `raster_tri`.

## Regression proof (v11 → v12)

* 21 presets × t=10.5: **21/21 byte-identical**.
* 24 authentic pairs × t=10.5: **24/24 byte-identical**.
* `--modern` / `--day --fog` / default paths: byte-identical (isolated).
* `verify.sh`: ALL SECTIONS PASS (determinism, bridge, 160 deg/s turn,
  30×401-row camera audit, 539-sample env math audit, wobble grid snap,
  dynamic fog, one-frame lightning, window env ticks).
* Weather stress (live key injection): rapid W×10 → 1 accepted + 9 REFUSED
  (the field_234A lock); slow W → all accepted; all 9 states render and
  cross-fade distinctly; no freeze.
* GLB UNMODIFIED (md5 `c7183184d20a2508ce41af2702629a33`, read-only).
