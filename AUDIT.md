# AUDIT — fog_poc v2 (GLTF-native) vs silent-hill-decomp + camdat.html

Every rendering-relevant behavior in this PoC is traced to its ground truth.
Format: **PoC location → decomp / camdat.html reference → fidelity notes.**
## AUDIT v8 (this release — the complete world-effect audit)

| feature | PoC location | ground truth (file:line / function) | notes |
|---|---|---|---|
| ALL 21 presets embedded | `SH_MAP_EFFECTS_INFOS[21]` (decomp-indexed) | `map_info.c` `MAP_EFFECTS_INFOS[21]` — read COMPLETELY | values verbatim incl. Q12 truncation (Q12(x) = (s32)(x*4096), TO_FIXED trunc-toward-zero); maxB 0x50/0x92/0x38/0xC4 carried; the 5 v7 presets keep their exact values/indices (regression-pinned) |
| any-pair Gfx_MapEnvSet | `--envpair A,B` (boot override) | `world_effects.c:277` | the 14 game pair modes + the D_800A9F80..A4 map-default table all reachable |
| WorldEnv_MapPresetSet | `--worldstage N` | `world_effects.c:197` (field_16 switch; exterior → hasActiveChunk=false) | 1→{1,1} 2→{6,3} 3→{9,9} |
| RAIN spawn/warm-up | `rain_spawn` / `rain_spawn_movement_apply` | `Particle_Spawn` case 1 / `Particle_SpawnMovementApply` case 1 (particle.c) | type Rain(2), vy=-6m+Q12(Rng_GenerateInt(0,2)), speed Q12(0.03675)=150, gravity 30, ±6m box, pos1C tail tracking |
| RAIN movement | `rain_movement_update` | `Particle_MovementUpdate` case 1 | Vectors1-view delta anchor, wrap/randomize, ground snap, splash transition; groundType-11 drip branch documented-unreachable (no collision materials in the rip) |
| RAIN draw | `rain_blit_streak/splash` + the render collection | `Particle_RainDraw` (particle.c:2701-3096, read COMPLETELY) | streak UV (10,112)-(13,128) 1px quad; splash (x±c,z±c) diamond, c=state<<sp64, color 0x80-(c>>(sp64-3)), sp64=3/4/5 by E32D0; drip c+0x18; cluts 0x1A30/((z>>5)+0x68); prim = field_25 - fog(OTZ)>>5 u8-wrap (>>5 for rain vs >>2 snow!) |
| rain assets | `src/rain_tim_data.h` | BG_ETC.TIM tpage 44 (768,0) | streak 3x16 + splash 16x16 + 8 CLUTs rows 104..111 extracted VERBATIM (tools/extract_rain_tim.py from the original TIM) |
| weather dispatcher | `particle_environment_set` | `Particle_EnvironmentSet` (particle.c:3717) | args 0/1/2/5/6; arg1==2→3 quirk; E0CB0 packing; DFB6C/DFB70; E32D0=135000 for rain |
| weather transition | `sh_particle_weather_tick` + `sh_particle_weather_target_set` | Particle_SystemUpdate default-case sine block (particle.c:387-571) + `sharedFunc_800D0B18_0_s00` | VERBATIM transcription incl. the 0xE38 bit alchemy; counts follow the case table; verified snow = 2·(sin(180°+t·2)·150+150) EXACTLY; W key = the map0_s00_2.c:1679 recipe (D0B18 alone) |
| sine LUT | `src/sh_sine_table.h` | `libkmath.s` `g_SineTable` (5120 entries) | extracted VERBATIM; Math_Sin/Cos = raw lookup, no interpolation |
| enum-2 N.L light | `sh_gte_ll_buggy` + the SHENUM_2 branch in `transform_item2` | `func_80057A3C` + `gte_ll` = 0x4A4A6412 = MVMVA{LLM,V0,tx=FC,sf=1,lm=1} | the FC-translation hardware bug DROPS M[0][0]·Vx (DuckStation MulMatVecBuggy byte-accurate); value = IR1+wLI>>5, >0xFF clamp, u8 write (negative wraps) |
| lens-flare light dirs | `sh_env_update_pose` enum-2 branch | `func_8003F4DC` (world_effects.c:468-546) | coord0==NULL → world-fixed direction; Default → lightWeight 0; the 5 preset angle tables verbatim (Q12_ANGLE truncation + LUT sin/cos) |
| dynamic fog (field_E=3) | `sh_env_tick` slot-84 write | Gfx_EffectsUpdate lines 405-410 | HERO=camera → the bone's view matrix is IDENTITY → fogDistance = Q12(0.12) = 491 CONSTANT; the per-tick env1C=env84 re-copy (PrimitiveType_None) added verbatim |
| lightning flashEffect | `sh_env_tick` flash block + K_L/--lightning | Gfx_EffectsUpdate lines 434-447 + func_8003EDA8 | dark env → one-tick preset-8 overwrite (Gfx_FogParametersSet verbatim); flashlight env → +Q12(0.3); env-dump-verified (spot 1433/maxB 80/fog 32768/wLI 1638) |
| IR0/dp clamp | `sh_mesh_light_vertex` | DuckStation gte.cpp:41-42 IR0_MAX_VALUE=0x1000 | [0,0x1000] (was 0x7FFF); no pixel change for real presets (max dp 1280) |
| beam constants | `SH_SIN_M15/SH_COS_M15` | libkmath.s LUT: sin/cos(Q12_ANGLE(-15)=-170) = -1056/3958 | was true-math -1061/3957 (0.4% error); engine angle quantization wins |
| shot-path fog | `R.fog = &Es.fog` in the --shot loop | (PoC-internal correctness) | latent v7 bug: the shot path rendered with the boot-state fog; invisible for all v7 pairs (black fog), required for the new colored/dynamic modes; all v7 goldens re-verified byte-identical |
| snow rest handler | `snow_rest_handler(S,p,dx,dz,pass)` | `sharedFunc_800CFFF8_0_s00` | pass param (threshold pass+5m: snow 5m, rain 6m), wind drift (E0CAC==3, engine-inert), HeavyWindy/243 pos1C tracking |
| snow init generalization | `snow_reset` (weatherSettings class) | `Particle_SnowInitialize` (particle.c:637-779) | class 1 (snow: density 3, SnowType_Light types, Heavy spawnMult) / class 2 (rain: density 10, type 2) — the v7 map0_s00 boot RNG order UNCHANGED |
| snow tick pass-1 | `snow_tick` rain bank loop | `Particle_Update` two-pass loop (particle.c:1266-1400) | shared spawn budget, pass-1 policing (type∉[2,3]→2), the E32D0 ramp, the folded RainDraw state resets (splash≥17, drip≥49), Vectors1 update |

v8 exclusions (documented, data-absent): the lightning BOLT sprite actor
(func_80063A50 — overlay unkTable1_4C table data not in the room rip; the ENV
flash IS ported), the groundType-11 puddle drip branch (IPD collision
materials absent from the GLB), the map0_s00 drifting-mist/flashlight-cone
extras (spawn tables live in the overlay script — as v7), wind (map-header
field_17 3/4/7/8 only — engine-identically inert), rain sound (no audio
system), lighter flame (preset 10's UseLighter — actor bone required).

## AUDIT v7 (this release)

| fix | PoC location | ground truth (file:line / function) | notes |
|---|---|---|---|
| realtime window never ticked the env (ROOT CAUSE of "flashlight lights snow, not geometry") | `sh_env_sync_live()` now called in `run_window_win32`, `run_window_sdl`, `run_window_x11` (per rendered frame, after `playback_step`/`snow_sync_live`) | `game_sys_states.c:167` — `Gfx_EffectsUpdate()` runs EVERY frame from the main state dispatcher (inside the not-paused block, before `particleSystemUpdate:171` and `WorldGfx_Draw:189`); it advances `flashlightIntensity` (Q12_MULT_FLOAT_PRECISE(dt,4.0), world_effects.c:395-402), the preset blend (func_8003F838) and the light pose (Gfx_FlashlightPositionUpdate 0x800554C4) | v4-v6 called it only in `run_benchmark`/`--shot`; the window froze the env at boot: light at world origin, `spot` = weighted(0,5324,weight=0) = 0, `fi` = 0 -> func_80057658 yields ambient-only. Snow still flipped because `func_8003EDB8` (world_effects.c:288) selects `field_1C[isFlashlightOn].field_21` by BOOLEAN, not by the blend. Proof: Xvfb window run + `--env-dump` (121 ticks, fi->4096, spot->5324, fog OFF at full intensity, light P= tracks camera); mid-run screenshot A/B v6-vs-v7 (identical camera/scene): +14.22% pixels, max +108; VLM verdict: old "pitch black unlit geometry, only particles", new "ground and fence bases illuminated". |
| light-mode gate used the renderer debug fog flag | `transform_item2`: `lightMode = env ? env->field_0 : SHENUM_0` | `Gfx_MeshDraw` 0x8005801C (bodyprog_80056D8C.c:677/692): the enum-0 DPCS pre-pass and the enum-1/2 light paths dispatch on `g_WorldEnvWork.field_0` ONLY | the prior agent's fog-gate hypothesis was engine-correct but could NOT fix the window symptom alone (env never ticked there); both layers are now engine-exact. `--nofog` debug only gates the fog ramp/veil/clear (fogOn), never the light mode |
| wobble rounded instead of truncating; y grid wrong; default OFF | `gte_snap_screen` (floorf truncation, scaleX=fb_w/320, scaleY=fb_h/240); `opts.ps1 = 1` default | DuckStation `src/core/gte.cpp`: RTPS `Sx = result*IR1 + OFX` (line 779, aspect None) -> `PushSXY(s32(Sx >> 16), s32(Sy >> 16))` (line 786) — arithmetic >>, NO rounding; engine raster 320x240 (SCREEN_WIDTH/HEIGHT, game.h; vcInitCamera sets SetGeomScreen(gsScreenHeight)) | flake centers use the same snap (engine Particle_SnowDraw: gte_rtps + gte_stsxy -> integer sXY2). Verified: fp-dump grid check (0 off-grid vertices), default-vs-modern 17.48% pixel delta, determinism byte-identical |
| preset 1 wLI 4504 -> 4505 | `SH_PRESET_1` | `map_info.c`: worldLightIntensity = Q12(1.1f); TO_FIXED = (s32)(x * 4096) -> 4505 | zero pixel delta (sub->>12), engine-exact constant |
| enum-0 fog-off quad color 128 -> tintEff | `transform_item2` fog-off branch | `Gfx_MeshDraw` `__block19CC` (bodyprog_80056D8C.c:1336-1423): flat `field_8` color (the enum-0 DPCS pre-pass output) copied to every prim | debug-path only (--nofog/camdat fogon=false day) |
| (verified, unchanged) flashlight RTPS OFX semantics | `sh_mesh_light_vertex`: sx = unr*ir1 - (1024<<16) then >>16, clamp [-1024,1023], +1024 | DuckStation gte.cpp:779/786 + include/psyq/inline_c.h:274 `gte_SetGeomOffset` = `sll $12,%0,16; ctc2 $12,$24` — OFX is written as pixels<<16 | the v6 code was ALREADY exact (engine SetGeomOffset(-1024,-1024) -> OFX = -1024<<16, then screenPos += 1024 s16) |

v7 regression proofs (all in `verify.sh`): camera audit 30 tracks x 401 rows
== camtrack.html JS (0 mismatches); env math grid 539 samples == decomp
reference (0 mismatches); v7 night flashlight `--shot` BYTE-IDENTICAL to the
v6 reference; v7 `--modern` day render BYTE-IDENTICAL to a freshly-built v6
binary; night/nightmare pair statistics; window env-tick live check (Xvfb).
The v6 PACKAGED `reference_shots/day_t*.png` were proven stale during this
audit (a fresh v6 binary does not reproduce them either) — the golden set is
now regenerated self-consistently by `verify.sh`.

---


v2 is a rewrite of the pipeline around the previous agent's Wine-verified
renderer: the fog math, snow logic, PS1 rasterizer semantics and window
backends are carried over (re-verified line-by-line against the decomp
during this audit); the GLB loading, camdat camera (incl. the turn filter),
PSX wobble and embedded snow assets are new.

## 0. Fixed during this audit (loud, per the regression protocol)

| bug | root cause | fix | detection |
|---|---|---|---|
| scene progressively vanished for t>6 s (100% empty fog at t>=9) | `mat4_view_from_quat` stored the camera rotation **R** instead of its transpose **R^T** (view matrix); with the track's 2° yaw the effective camera origin was displaced ~18 m (R vs R^T applied inconsistently to `pos`), walking the view off the street as t advanced | rows of the view rotation = camera basis axes (X,Y,Z), translation = -axis·pos — identical to the previous verified `mat4_lookat` | hand-computed view_z of a known-visible point from the `--fp-dump` matrices: +8.28 (behind) before fix, -9.97 (in front) after; full render suite re-verified |
| `--shot` rendered the *exact* (snapped) orientation, defeating the turn filter at turnarounds | the deterministic shot path ended with an extra `playback_step(dt=0)` — the editor's *paused* semantics | the shot now renders the camera pose of the LAST playing step (60 fps session semantics = live window = benchmark) | yaw measured at 20.5..23.0 s: before fix the 180° flip was already complete at t=21.0; after fix it sweeps at exactly 160°/s and completes at ~22.1 s |
| `--benchmark --duration D>10` saved a wrong `--save-final` frame (forward-looking camera mid-turn, mostly fog) | TWO defects: (a) `run_benchmark` capped the run at the 600-frame default instead of running to the duration, leaving the turn filter at t=10 when the final frame jumped to D; (b) `live_save_final` re-derived the camera via `cam_update_track(dt=0)`, SNAPPING the orientation to exact instead of rendering the current turn state | (a) `--duration` now drives the benchmark run end-to-end; (b) new `live_current_pose()` renders the CURRENT turn.quat without advancing or snapping, and the benchmark clamps its final step to the duration so its step sequence equals the `--shot` simulation | mid-turn bridge test `--benchmark --duration 21.5 --save-final` vs `--shot t=21.5`: differed in 103k pixels before, byte-identical after; t=6 bridge kept byte-identical |

All three regressions were introduced by v2's new code (not present in the
previous verified build) and are covered by `verify.sh` (determinism,
t=6 bridge, 160°/s turn rate) plus the manual mid-turn bridge test.

## 1. Fog (unchanged from the verified v1; re-audited against the decomp)

| PoC | decomp | notes |
|---|---|---|
| `FOG_CURVE[17]` | `D_800AE1C0` in `src/bodyprog/gfx/bodyprog_80055028.c` | identical 17-entry curve |
| `engine_fog_set_distances()` | `WorldEnv_FogDistanceSet()` (0x80055840) | 1:1: Q12→Q8 near/far, `depthShift = 0x20 - Lzc(near-1)`, `temp = (0x10<<(shift+1))/near`, 128-entry ramp with the first-segment special case, 0xFF tail. near=Q8(13.5) → depthShift=12, intensity=48/4096 |
| `engine_fog_ramp_lookup_q12()` | `func_800559A8()` | 1:1 interpolation incl. idx 0x7F edge case |
| `engine_fog_update_intensity()` | `func_80055814()` via `Gfx_EffectsUpdate()` | intensity = 4096 − rampLookup(fogDistance) |
| `engine_fog_vertex(zQ8)` | `func_80057B7C()` inline lookup | `z < (1<<shift) ? ramp[(z<<7)>>shift] : 0xFF`, z = GTE SZ (Q8 = 256/m view depth) |
| per-vertex fog in `transform_item2()` | `Gfx_MeshDraw()` path B (field_0==0, isFogEnabled) | `T = clamp(4096 − ramp*16 − intensity, 0)`; textured vcolor = `tintEff*T` (DPCS toward black); overlay = `fogColor*(4096−T)`; pixel = `(texel*vcolor)>>7 + overlay` (additive veil — the only blend consistent with fully-fogged geometry == the fog background quad) |
| clear color = fogColor | `WorldGfx_2dEffectsDraw()` | full-screen fogColor G4 at the farthest OT slot = effective clear |
| tintEff = (121,128,138)*(1.1) = (133,140,151) | `WorldEnv_WorldLightingParamSet` + `Gfx_MeshDraw` pre-pass dpcs (DP = 4096−field_20) | preset worldLightIntensity Q12(1.1) |
| preset values | `MAP_EFFECTS_INFOS[1]` (`src/bodyprog/sys/map_info.c`); THR outdoor per `D_800A9F80={1,1}` | field_E=1, fogDistance Q12(13.5), fogColor {108,100,116}, worldTint Q12(0.95/1.00/1.08); far = near+Q12(1.0) |
| fog enable default | camdat.json `models[].fogon` (true for THRF9FD) | the camdat contract: the flag "rides with each models[] entry for the consuming program (e.g. enabling its fog for that room)"; `--nofog/--fog` override |

Verification: sky-region colorimetry vs the previous VLM-verified reference
(mean RGB within ~1.6 of {108,100,116} in both), near-ground patch within
~2; t=20.5 and t=41.5 renders differ from the previous references by mean
0.33/0.45 RGB (snow-flake noise only) — camera + fog byte-equivalent away
from the (now leaf-bearing) trees.

## 2. Snow (logic unchanged from the verified v1; re-audited; assets now embedded)

Ground truth: `src/maps/particle.c` read COMPLETELY (all 4364 lines) during
this audit — not grep-snippets. Configuration for this scene (map0_s00 =
THR outdoor street): `Particle_EnvironmentSet(field_17=2, field_16=1)` →
SnowType_Heavy, spawnMult 2, density 3/tick, wind 0, 800DD592=1 (type Snow),
800DD591=0 (plain draw path), D_800C39A0=1.

| PoC | decomp | notes |
|---|---|---|
| warm-up (150 iters, dt=Q12(0.1/3)) | `Particle_SnowInitialize` | 1:1 incl. `SNOW_REST_TICKS_MAX=16` (init) vs 32 (update) quirk |
| `snow_tick()` | `Particle_Update` pass 0 | 1:1: type%=0xF0, type>=2 policing, Spawn/Active/Rest state machine, spawn throttle, `g_ParticlesAddedCount` growth |
| `snow_spawn()` | `Particle_Spawn` case 0 | vy=Q12(-6), movement=(0,0,Q12(0.0245)), `Particle_PositionRandomize(rand,part,5)`, state→Active |
| `snow_position_randomize()` | `Particle_PositionRandomize` | 1:1 L1-box randomization (x from two rands, z from r−|x|) |
| `snow_movement_update()` | `Particle_MovementUpdate` case 0 | 1:1: GEN(−7..7)/GEN(−7..7)/GEN(−1..3) random walk (vz and vy share ONE rand value — engine order), TS30((mv<<2)+wind+camDelta), y-fall (mv.y>>1)<<2, box wrap → negate+type+=240 (u8) or re-randomize on camera jump, ground gate vy>=0 → surface query → snap + (−0.2,0) drift-flatten band → rest |
| `snow_rest_handler()` | `sharedFunc_800CFFF8_0_s00` | 1:1 world anchor + `ABS_ADD(|z|,|x|) > Q12(5)` respawn |
| one-frame hide fold | `Particle_SnowDraw` type>=240 branch | engine: draw does `type += 16` (u8 wrap 240→0) and skips the prim once; folded into the tick post-fixup so >30 Hz rendering stays pure |
| draw gates | `Particle_SnowDraw` | state 0 not drawn; fade `prim -= prim*state>>5`; state>=31 → reset+invisible |
| prim color | `Particle_SnowDraw` D_800C39A0==1 branch | `prim = 48 − (func_80055A50(raw OTZ) >> 2)` with exact u8 wrap (in-room ≈ constant 48 — the engine feeds the raw OTZ, not the Q12-scaled depth) |
| sizes/CLUTs | `Particle_SnowDraw` branches | zHalf=OTZ>>1: <2 m 4×4 sprite u3..7/v112..116 clut 0x1830 (768,96); 2–8 m 3×3 u0..3/v112..115 clut row 96+(z>>5); >=8 m 1×1 clut 0x19F0 (768,103); row 97 unreachable (engine quirk) |
| blend | tpage 44 (0x2C) → VRAM 768, ABR=1 | additive B+F in 5-bit with 5→8 replication, `F5 = min(31, texel5*prim>>7)`, CLUT entry 0x0000 skipped |
| **assets** | BG_ETC.TIM via `GameFs_BgEtcGfxLoad` → VRAM (768,0) | **EMBEDDED**: `src/snow_tim_data.h` generated by `tools/extract_snow_tim.py`; sprite (u0..7,v112..116 4bpp indices) + 8 CLUTs (pixel rows 96..103, halfword cols 0..15) — cross-checked **byte-identical** against the previous agent's verified scene.bin section |
| RNG | `src/main/rng.c` | LCG `seed*1664525+1013904223`, Rand16=seed>>17, consumption order 1:1; fixed seed 1 (boot seed not in decomp sources), `--snow-seed` override |
| 30 Hz ticking | `g_IntervalVBlanks=2`, `g_DeltaTime=Q12(1/30)` | ticks at k/30 boundaries; per-tick scale = 1 |
| ground probe | `Collision_SurfaceGet` | rip has no IPD collision mesh → render-mesh heightfield proxy (0.25 m grid, opaque up-facing tris, datum = camera-track walkway median = +0.148 m, band datum−2..+0.5, no-data → Q12(8.0) engine fallback, 1-cell max-dilate); **documented deviation**: resting flakes sit +2 cm proud (z-buffer visibility; engine rests flush and relies on OT ordering) |
| **live camera source (new)** | `vwGetViewPosition/Angle` | the engine ticks snow against its ACTUAL view camera — during playback our ticks sample the turn-filter camera; deterministic seeks/backward jumps re-simulate with the exact track camera (matching the editor's turn-filter snap on seek) |

## 3. Camera — camdat.html (READ COMPLETELY; the full reference implementation)

| PoC | camdat.html |
|---|---|
| `cam_phase01()/tri01()` | `phase01()/tri01()` bit-identical |
| `cam_angle_at()` | `angleAt()` incl. free-rotation, loop/once/pingPong branches |
| `catmull_rom()/catmull_rom_tangent()` | `catmullRom()/catmullRomTangent()` |
| `curve_lut_build()` | `curveLUT()` — CURVE_SAMPLES=64 (format constant), chord table, exact per-sample slopes `K/|d'(u)|` with chord-secant fallback |
| `curve_param_at()` | `curveParamAt()` — binary search + monotone cubic Hermite with Fritsch-Carlson clamp (M0+M1<=3) |
| `curve_pos_at()/curve_tangent_at()` | `curvePosAt()/curveTangentAt()` incl. degenerate-tangent chord fallback |
| `cam_normal_from_tangent()` | `normalFromTangent()` — cross(T,+Y) with +Z/+X fallback chain, backward = −N |
| `camtrack_eval()` | `evalTrack()` — ALL track types (line/circle/curve/fixed), ALL look modes (path/point/normal/fixed YXZ), returning-leg rule for pingPong |
| `camtrack_cycle_duration()` | `cycleDuration()` |
| `cam_ev_target_quat()` | `evTargetQuat()` — three.js `Matrix4.lookAt(eye,target,up=(0,1,0))` (incl. eye==target and parallel-up z-perturb fallbacks) or `Euler(pitch,yaw,0,'YXZ')` |
| `turn_step_limited()` | `turnStepLimited()` — `angleTo = 2*acos(clamp(|dot|))`, `maxStep = 160°*dt`, slerp ratio `min(maxStep/ang,1)` |
| `quat_slerp()` | three.js `Quaternion.slerp` (sign fix + EPSILON lerp branch) |
| `cam_update_track()` | `updateTrackCam()` — jump check `trackId!=tr || !prevPos || dist>max(diag*0.5,0.5)` (diag=54.54 from the loaded GLB bbox = camdat `activeModelInfo`), paused/scrubbed → exact, position ALWAYS exact |
| `playback_step()` | editor `frame()` — `dt = min(delta,0.1)`, `t += dt*rate`, `t %= cycleDuration`, then `updateTrackCam(tr, playing?dt:0)` |
| `mat4_view_from_quat()` | three.js `matrixWorldInverse` (R^T, t=−R^T·pos) — **fixed during this audit** (had stored R) |
| projection | `pipCam = PerspectiveCamera(fov=track.fovDeg, 16:9, 0.05, 100)`; `mat4_perspective` = three.js `updateProjectionMatrix` |

Verified: yaw sweeps +2.05° → −177.95° across the pingPong turnaround at
exactly 160°/s (measured (164.72−12.72)/0.95 s); mid-turn t=21.4 yaw=84.7°
(side view — VLM-confirmed); t=20.5/41.5 renders byte-match the previous
exact-orientation references (no rotation in progress there).

## 4. PSX wobble (new) — authentic GTE mechanism

| PoC | reference |
|---|---|
| `gte_snap_screen()` when `--ps1`/P | PS1 GTE RTPS/RTPT: the fixed-point projection result is truncated to 16-bit INTEGER screen coordinates (round-to-nearest via the +0x8000 pre-shift) on the console framebuffer grid, `SCREEN_WIDTH=320` (game.h). Wobble = vertices snapping between integer pixels as the camera moves. Implemented as round-to-nearest on the 320-wide grid scaled to the render resolution (square engine pixels; the engine screen is 320-wide — the height follows the render aspect) |
| affine UV + 15-bit + `(texel*color)>>7` | PS1 GPU: no perspective divide for UVs, 5-5-5 framebuffer, texture modulation 128=neutral (bundled with the snap as one authentic GTE/GPU package; P toggles all three, default OFF per the task) |

## 5. GLTF pipeline (new — replaces the old pre-extracted scene.bin)

| behavior | notes |
|---|---|
| in-app GLB load | GLB container (JSON+BIN chunks) → mini JSON DOM parser (self-contained) → accessors (FLOAT VEC3/VEC2, u16/u32 indices, byteStride-aware) → node graph walk with TRS/matrix composition → draw items; materials: alphaMode OPAQUE vs MASK/BLEND (engine STP prims; per-texel binary alpha <128 = hole, MASK cutoff 0.5 semantics) |
| textures | embedded PNGs decoded in-app: self-contained RFC-1951 inflate (fixed+dynamic Huffman, stored blocks) + PNG defilter (all 5 filters, RGBA/RGB/palette/gray 8-bit) — **no zlib dependency, no external files** |
| no extraction | the app never writes scene data out; room renders purely from the GLB (150 draw items, 10572 verts, 27 textures; bounds match camdat.json exactly, diag 54.54 m) |
| sampling | nearest + REPEAT wrap (PS1 GPU has no filtering; glTF samplers are LINEAR but engine-identical sampling is nearest) |

## 6. Realtime subsystem

| PoC | reference / rationale |
|---|---|
| playback timing | editor `frame()` 1:1 (see §3); live dt from QPC/CLOCK_MONOTONIC, clamped 0.1 s |
| frame clock / pacing | unchanged from the Wine-verified v1 (QPC / CLOCK_MONOTONIC, sleep>4 ms/yield>0.4 ms/spin, present cap `--fps`) |
| Windows backend | native Win32 + GDI `StretchDIBits` (user32/gdi32 only) — carried over verbatim from the previous Wine-verified build; the v2 changes (GLB load, camera, snow source) are platform-independent and verified on Linux |
| Linux backends | SDL2 dlopen → raw X11 dlopen (unchanged) |
| controls | ESC quit, SPACE pause, R restart, +/- speed, Left/Right scrub, F fog, **P PSX wobble**, N snow, S screenshot |
| determinism bridge | `--benchmark --duration D --save-final F` == `--shot t=D,file=F` **byte-identical** (verified); two `--shot` runs byte-identical |

## 7. Verification performed for this release

1. Snow TIM embed byte-identical to the verified baseline (script cross-check).
2. Render suite t = 0 / 10.5 / 20.5 / 31.5 / 41.5 vs the previous VLM-verified
   references: camera + fog match (t=20.5/41.5 mean diff 0.33/0.45); mid-track
   frames differ only where the GLB's tree leaves are visible (the old
   pre-extractor dropped them; v2 renders the full GLB — VLM-confirmed
   "trees now have full green leaf textures", i.e. the GLF content).
3. Turn filter: exactly 160°/s across the turnaround; mid-turn side view
   VLM-confirmed ("clearly rotated approximately 90 degrees").
4. VLM final pass (6-frame grid): coherent street, consistent fog, snow in
   every frame, no white blocks / z-fighting / missing geometry / alpha errors.
5. Determinism: repeat-run byte-identical; benchmark↔shot bridge byte-identical.
6. Performance: 640x360 ≈ 48 fps, 320x180 ≈ 161 fps (x86 container) —
   fill-rate bound; RK3326 should use 320x180–480x270.

## 8. Documented deviations (complete list)

1. Snow RNG boot seed unknown (not in decomp sources) → fixed seed 1
   (`--snow-seed` to change); statistics unaffected.
2. Ground heights from the render mesh (rip has no IPD collision data);
   datum anchored to the camera-track walkway (+0.148 m).
3. Resting flakes sit +2 cm proud of the surface (z-buffer visibility;
   engine rests flush and relies on OT draw order).
4. Far-geometry cull at fog.farDistance omitted — fully-fogged output is
   byte-identical to the fog background, so the cull is visually a no-op.
5. GTE snap grid is the engine's 320-wide grid scaled to the 16:9 render
   framebuffer (square engine pixels; the console screen is 320 wide).
6. `--shot` renders the playing-session (turn-filtered) camera at a fixed
   60 fps simulation; the editor's paused/scrubbed frames show the exact
   orientation (equivalent to `--shot` before turnarounds, where both match).

---

# V3 AUDIT — Camera Logic Update (camtrack.html integration)

## 9. camtrack.html deep analysis (single source of truth)

The updated `camtrack.html` (182,849 bytes, 3,665 lines) was read COMPLETELY.
Byte-level diff against the old `camdat.html` proved these functions
UNCHANGED (so the v2 ports stay exact): tri01, phase01, angleAt, catmullRom,
catmullRomTangent, curveLUT, curveParamAt, curvePosAt, curveTangentAt,
normalFromTangent, evTargetQuat, turnStepLimited, updateTrackCam,
tickPlayback, the frame loop (dt = min(getDelta, 0.1)), updatePipCam.

The delta: (a) 4 NEW track types — polyline, spiral, zigzag, figure8 — with
evalTrack branches, cycleDuration branches, sanitizeTrack clamps and the
pointsLUT/polyParamAt/polyPosAt/polyTangentAt/zigzagPoints math; (b) per-type
lookMode pick-lists incl. the new 'center' mode; (c) loopMode default now
(line|polyline|spiral|zigzag) ? pingPong : loop; (d) per-model strict-boolean
flags nighton + flashlighton riding with fogon in camdat.json.

## 10. C++ changes (fog_poc.c)

* CamTrack: + TRK_POLYLINE/SPIRAL/ZIGZAG/FIGURE8 enums, LOOK_CENTER, the
  spiral/zigzag/figure8 fields, nighton/flashlighton in Camdat.
* Loader: per-type lookMode pick-lists + defaults, new loopMode default rule,
  4 new sanitize branches (every clamp verbatim), `--track N` selector.
* evalTrack: 4 new branches verbatim; circle branch fixed to the exact JS
  (center/point/path-tangent/normal/fixed).
* cycleDuration: 4 new branches verbatim.
* snow_ground_build: for the 4 new types the walkway datum samples the ACTUAL
  evalTrack path (they have no start/end); line/circle/curve/fixed keep the
  exact v2 code (zero regression risk).
* New `--cam-dump FILE[,STEPS]` audit mode: dumps evalTrack over one cycle
  (t, pos, lookAt/yaw/pitch, fov) as CSV, then exits.

## 11. Latent bugs found & fixed (loud, per protocol)

1. **circle lookMode 'path' was evaluated as a center-look** — the v2 loader
   had no 'center' case (parsed it as LOOK_PATH) and the v2 eval treated
   LOOK_PATH on a circle as lookAt-point (correct only by accident for the
   default 'center' lookAt). Fixed with the typed pick-list + exact JS branch.
2. **arcBounds/yawBounds/pitchBounds read a nonexistent JSON field** — the
   camdat FORMAT stores only arcMinDeg/arcMaxDeg (and yaw/pitch Min/Max);
   sanitizeTrack RECONSTRUCTS the booleans (`min != null && max != null &&
   num(max,1) > num(min,0)`). The v2 loader read `jbool(raw,"arcBounds")`
   which is always absent → bounded arcs/yaws silently became free rotation.
   Both are now reconstructed exactly as sanitizeTrack does.
3. **spiral pos.y catastrophic cancellation** — computed in float; now double
   (same op order as the JS), cast once at storage.
   Bugs 1+2 never manifested in v2 (its input is a single line track) —
   found by the v3 ground-truth audit below, fixed, re-verified.

## 12. Ground-truth audit (C++ vs camtrack.html JS — the actual file's code)

`tools/tests/camtrack_audit.js` extracts the pure playback math VERBATIM from the
downloaded camtrack.html (utils, phase01/angleAt, curve/polyline/zigzag LUTs,
normalFromTangent, evalTrack, cycleDuration, sanitizeTrack) and runs it over
`tools/tests/camtest_tracks.json` — 30 tracks covering all 8 types x all 5 look
modes x all 3 loop modes + per-type defaults + degenerate inputs (zero-length
line, zero-length polyline segments, bad values, lanes rounding, turns
clamping). The PoC dumps the same 401 samples/track via `--cam-dump`.

RESULT: **ALL 30 TRACKS MATCH — 12,030 rows, worst relative error 8.4e-07**
(pure float32-storage rounding; tolerance 3e-5 rel / 1e-3 abs).

## 13. Regression audit (fog / snow / wobble / old camera)

* Reference shots t=0/10.5/20.5/31.5/41.5 (960x540) + t=21.4 mid-turn
  (640x360): **BYTE-IDENTICAL** to the v2 references (6/6).
* verify.sh: determinism byte-identical; benchmark↔shot bridge
  byte-identical; turn rate measured **exactly 160.0 deg/s** mid-turn.
* VLM pass on the 4 new track types (polyline/spiral/zigzag/figure8 grid):
  coherent street scenes, consistent fog, snow visible, no glitches —
  PASS x4. Snow datum for the new types samples the actual track path
  (0.148 m — same walkway level as the line track).

## 14. Builds

* Linux: `make` — clean (no warnings), x86-64.
* Windows: `zig cc -target x86_64-windows-gnu -O2 -std=c99 -o fog_poc.exe
  src/fog_poc.c -luser32 -lgdi32` — PE32+ x64, imports only
  USER32/GDI32/KERNEL32 + the Windows Universal CRT (OS component on
  Win10/11): standalone. (Wine unavailable in this environment; the Win32
  present backend is unchanged from the Wine-verified v2 build and all v3
  changes are platform-independent C99 verified on Linux.)

---

# AUDIT v4 — Night Sequence + Flashlight vs silent-hill-decomp

Scope: the env preset system (world_effects.c), the per-vertex flashlight
(bodyprog_80056D8C.c func_80057658 + Gfx_MeshDraw DPCL path), the light
tables (bodyprog_80055028.c func_80055648/func_80055D78), and the snow↔env
interaction (particle.c + func_8003EDB8). GTE opcode semantics (DPCS/DPCL/
RTPS/UNRDivide, sf flags, IR clamps, the OFX 16.16 encoding) verified
against SwanStation/DuckStation's cycle-accurate implementation (SwanStation is the GPL-3.0 maintained fork of the DuckStation core).

## 1. Env presets + blend (world_effects.c)

| PoC | decomp | fidelity |
|---|---|---|
| `SH_PRESET_1/6/3` | `MAP_EFFECTS_INFOS[1/6/3]` (map_info.c) | verbatim fields incl. flags, spot, wLI, tints, field_E, fogColor, field_21/25 |
| `sh_env_set_pair` | `Gfx_MapEnvSet`→`Gfx_MapEnvStepUpdate`→`Gfx_FogParametersSet` | identical slot logic; `isFlashlightUnavailable = (pair equal)`; field_E fogDistance cases |
| day pair `{1,1}` / night pair `{6,3}` | `WorldEnv_MapPresetSet` case 1 / `map0_s01_events.c:920` | exact indices (exterior street → no active chunks → D_800A9F80) |
| `sh_env_blend` | `func_8003F838` + `func_8003FCB0/FD38/FE04` | verbatim: weight0/weight1, flags[0] switch at 0.5, field_E transitions, LoadAverageCol colors, worldTint/spot sweeps incl. the enum-1↔2 special ramps |
| `load_average_col` | libgte `gte_LoadAverageCol` (gpf12+gpl12, MAC<<12 restore) | exact two-step fixed point |
| `sh_env_tick` fade | `Gfx_EffectsUpdate` | flashlightIntensity ±Q12_MULT_FLOAT_PRECISE(dt,4.0) (dt=136/tick → 544 steps → 0.25 s), auto-off when unavailable (bodyprog_effects_8005E0DC.c:650) |
| `sh_env_flashlight_allowed` | `game_sys_states.c:236-240` | FlashlightAllowed on the CURRENT env gates the toggle |
| screenBrightness | `WorldEnv_FogLightingParamsUpdate` + `WorldGfx_2dEffectsDraw` | CLAMP(Q12_MULT(brightnessIntensity, 3*8+4)) = 28; additive 15-bit full-screen lift, drawn at the OT front (over snow) |
| `sh_env_snow_base` | `func_8003EDB8` | `field_1C[isFlashlightOn].field_21` — instant boolean flip, not blended |

## 2. Flashlight math (the per-vertex light)

| PoC | decomp | fidelity |
|---|---|---|
| `sh_mesh_light_vertex` | `func_80057658` | exact: s64 dot MACs >>12, IR clamp16, SZ3 clamp, `UNRDivide(16, SZ3)` (hardware table + algorithm), Sx/Sy with OFX=-1024<<16 then the engine's `+= 1024` (they cancel — the net is `(UNR*IR)>>16` with the -1024..1023 s16 clamp), dp = clamp((UNR*DQA)>>12, 0, 0x7FFF), value formula incl. the -16 clamp, wLI>>5 ambient, min(sx'/2+dp/4, 48), maxB clamp |
| `GTE_UNR_TABLE` + `gte_unr_divide` | GTE hardware UNR (DuckStation-verified) | 257 entries byte-identical; clz normalization; 0x1FFFF saturation |
| `gte_dpcl_fc0` | GTE DPCL sf=1, FC=(0,0,0) | in_MAC=(tint*IR)<<4; IR'=clamp16(-in_MAC>>12); MAC=(IR'*IR0+in_MAC)>>12; out=clamp(MAC>>4) — the Gfx_MeshDraw enum-1 vertex color |
| `gte_dpcs_fc0` | GTE DPCS sf=1, FC=(0,0,0) | same chain; NEGATIVE IR0 (raw s16, no clamp on register writes) extrapolates → the x1.1 day tint reproduced exactly (133,140,151 — matching v2/v3 references bit-for-bit) |
| `sh_light_build_table` / `sh_light_query_pos` | `func_80055648` / `func_80055D78` | verbatim (position-query light — characters/effects path; exposed for audits + the env dump probe) |
| beam dir / offsets | `Game_FlashlightAttributesFix` + `func_8003F4DC` (Custom branch) | (-0.08,-0.28,0.12) offsets, -15° tilt, sin/cos at libgte Q12 resolution |
| `WorldEnv_LightTransform` equivalent | bodyprog_80056D8C.c | field_28 = clamp16(dir)*intensity>>12 with the RAW spot (1.3 → 5324; overbright enters via DQA=20), field_30 = pos Q8; worldMat = identity (room chunks) |

**Coordinate adaptation** (documented, math-preserving): engine y-down →
glTF y-up handled by doing the entire light computation in glTF world space
with the beam/offset mapped once from the player frame to the camera frame
(reflections preserve dot products). Engine mesh normals point INTO the
surface (verified against both enum-1 and enum-2 lighting being correct
only under that convention) — glTF normals are NEGATED at the boundary and
quantized to s8 (127 = 1.0, <<5). The engine s16 Δ truncation is kept.

**Light anchor**: the engine rides the light on Harry's torso (~1.02 m +
0.28 offset); the viewer anchors a virtual player on the snow system's
walkway datum at the camera XZ. A camera-height anchor would land the beam
at ~11 m — beyond the 8 m flashlight fog range (invisible) — the datum
anchor lands it at the game-authentic ~5 m.

## 3. v4 verification (all PASS)

* **Math audit** (`tools/tests/env_audit.py`, independent Python reference
  transcribed from the decomp): 539/539 samples — func_80057658 grid
  (384: 4 beams x 4 normals x 8 deltas x 3 DQA), DPCL (100), DPCS+veil
  (40), UNRDivide (15). **0 mismatches.**
* **Env blend audit**: 181/181 ticks of the 0.25 s night fade — fi ramp
  (544/tick), fogDistance 14 m→8 m sweep, wLI 1802→0, tint (51,89,128)→
  (121,128,138), spot 0→5324, fog OFF flip exactly at fi=4096. **0 mismatches.**
* **Regressions**: all 6 day references (t=0/10.5/20.5/31.5/41.5 @960x540,
  t=21.4 @640x360) **byte-identical** to v3 — zero regressions in fog,
  snow, wobble, camera.
* **Determinism**: night+flashlight two runs byte-identical;
  benchmark↔shot bridge at t=20.5 byte-identical.
* **Engine gates**: day pair refuses the flashlight (auto-off,
  "flashlight unavailable"); night toggles with the 0.25 s fade.
* **VLM visual passes**: (1) day vs night vs night+flashlight — dark night
  street with black fog; clear directional beam on the ground/fence ahead;
  PS1-plausible look; no glitches. (2) 4-shot grid incl. PSX-wobble night
  — consistent, clean.

## 4. v4 scope exclusions (documented, engine-inactive here)

* lens flare / water glint (`func_8008D470`, water.c): THR has NO water
  zones; the 1-px flare dot requires light altitude > 0x354 — a
  camera-level light fails the gate → the engine draws nothing.
* map6 cutscene 16x16 darkness grid (`func_80055ECC` user): one-off
  cutscene overlay for a different map.
* tint-light-overlap radial overlay (bodyprog_80040B74.c): only active for
  `enableTintLightOverlap` presets (e.g. 5) — presets 1/6/3 have it off.
* lightning `flashEffect` one-shot (func_8003EDA8 → preset 8 swap):
  event-scripted, not part of the N/F toggles.

---

# AUDIT v5 — Night Fog Deep Dive + HERO Flashlight vs silent-hill-decomp

Scope: the full night-street env system (`world_effects.c` env pairs, `map_info.c`
MAP_EFFECTS_INFOS[21] — the COMPLETE table, v4 embedded only 3 of 21 presets),
the room (IPD) render path in full (`bodyprog_80056D8C.c` func_80057344 /
func_80057658 / func_80057B7C / Gfx_MeshDraw ALL branches / Gfx_FogOverlayQuadDraw /
func_8005A21C), the night street events (map0_s01/s02, map6_s01), and DuckStation
(gte.cpp RTPS/UNRDivide/PushSXY semantics, dma.cpp linked-list OT order) + the
PSY-Q headers (inline_no_dmpsx.h: gte_rtps = `.word 0x4A180001` → sf=1, lm=0).

## 1. What was actually wrong in v4 (root causes, all verified)

| # | v4 defect | engine truth | evidence |
|---|---|---|---|
| 1 | **Beam pointed 15° UP**: `SH_LIGHT_DIR_CAM_Q12 = {0,-SH_SIN_M15,-SH_COS_M15}` double-negated `SH_SIN_M15(-1061)` → {0,+1061,-3957} in glTF (up) | engine beam = forward-DOWN (func_8003F4DC: vy = -sin(Q12_ANGLE(-15°)) = +1060 in y-down = DOWN); glTF camera-local = {0,-1061,-3957} | env dump v4: L=(38,**+1379**,5142); v5: L=(20,**-743**,2769) |
| 2 | **camdat fogon=false bypassed the whole env pipeline** (`R.fogEnabled = cd.fogon`): the new camdat (fogon=false, nighton=true) rendered a BRIGHT raw scene | the engine has no user fog toggle — fog on/off comes from the env preset field_E; camdat fogon is the DAY-fog consumer flag only | v5: fogEnabled = nightBoot ∥ fogon; boot(camdat flags) == `--night --flashlight --fog` byte-identical |
| 3 | **fog-OFF flashlight used DPCL + a fresh 8m fog ramp** → the beam was fogged to black beyond ~8m even where it pointed | Gfx_MeshDraw fog-off path: `dpcs(tint, 4096 - light<<5)` = tint*light/128, NO fog factor; light<8 → BLACK (0x3C000000) | bodyprog_80056D8C.c __block1530 (lines 1195-1334) |
| 4 | **enum-1 only ran when spot intensity ≠ 0** → flashlight-off night fell back to the enum-0 tint path | the blend sets flags[2]=enum-1 for the whole {7,4}/{6,3} blend (es0=enum-0,es1=enum-1 → target=es1 ALWAYS); with spot=0 func_80057658 yields light = wLI>>5 — the ambient path | func_8003F838 flags[2] else-branch; value formula terms |

## 2. The night street pairs (grep across ALL map events + WorldEnv_MapPresetSet)

* **{6,3}** — map0_s01_events.c:920 (`EventFlag_159 && !EventFlag_134`): the first
  night street (flashlight pickup at (267.28,-1.0,111.0), "There_is_a_ ~C2
  Flashlight ~C7 . ~N Take_it?"): preset 6 = fog **14.0 m black**, wLI 0.44,
  tint 0.4/0.7/1.0; preset 3 = flashlight env (spot **1.3**, wLI 0, fog OFF).
* **{7,4}** — map0_s02_events.c:102 AND map6_s01_2.c:479 (the nightmare resume:
  `Game_TurnFlashlightOn(); Gfx_MapEnvSet(7,4); func_8008D448();
  Game_FlashlightAttributesFix(); lightIntensity=Q12(1.0)`): preset 7 = fog
  **Q12(9.29987 m)** black (the THICK night), same tint/wLI as 6; preset 4 =
  flashlight env (spot **0.7**, wLI 0, tint 0.9/1.0/1.05, fog OFF).
* Presets embedded verbatim (5 of 21: 1,6,3,7,4 incl. the Q12(9.29987f)=38092
  truncation). v5 default: N cycles **day {1,1} → night {6,3} → nightmare {7,4}**;
  `--nightpair 7,4` swaps the cycle order. VLM evidence drove the default: the
  {6,3} spot-1.3 beam reads as a clear ground pool (8/10) at the track camera
  height; the authentic {7,4} spot-0.7 beam is the game's dimmer nightmare light.
* **field_E=3 DYNAMIC fog** (Gfx_EffectsUpdate: fogDistance := the flashlight's
  VIEW-SPACE DEPTH — the fog wall rides at Harry): preset 5 only (interior pair
  {6,5}). NOT the exterior street; with HERO≡camera it would compute ~0.3 m
  (total blackout). EXCLUDED, documented.

## 3. Gfx_MeshDraw — engine-exact restructure (the big correction)

Verified via `addPrim` = HEAD INSERTION (psyq libgpu.h:247:
`setaddr(p,getaddr(ot)),setaddr(ot,p)`) + DuckStation dma.cpp SyncMode::LinkedList
(the chain walks from the HEAD = the LAST-added packet = transferred FIRST =
drawn FIRST = BELOW) + the OT drawn high-index-first (the fog BG G4 lives at
org[SIZE-1], the brightness overlay at org[0]):

* fog ON + fogColor≠0 → DUAL quads per prim: textured GT4 (DPCL/DPCS vcolor)
  + G4 veil (fogColor*f). **STP prims: veil semi-trans ON TOP (additive ABR1);
  OPAQUE prims: veil BELOW** (visible only through per-texel holes — none in
  glTF OPAQUE materials → skipped).
* fog ON + fogColor==(0,0,0) → textured GT4 with DPCL colors ONLY, NO veil
  (the engine skips the veil entirely — preset 7's black-fog case).
* fog OFF + enum-1 → textured GT4 with **dpcs(tint, 4096−light<<5)** = tint*light/128,
  NO fog factor, light<8 → BLACK; no veil.
* fog OFF + enum-0 → flat-tint FT4 (__block19CC; our --nofog keeps the raw debug view).
* **FAR CULL implemented** (v4 omitted it): prim dropped when max-vertex SZ > 
  field_1C = fog ? MIN(0x79C<<2, farQ8) : 0x79C<<2 (room otShift=0 → 30.4 m OT limit).
* LOUD CORRECTION: v2–v4 applied the additive veil over OPAQUE prims too —
  a misreading of the draw order. The engine fades opaque geometry via vertex-color
  modulation (distant walls darken, then drop at the far cull); STP prims (fences,
  foliage) get the additive veil and fade to fogColor. The DAY reference renders
  CHANGED accordingly (pinned byte-identical by verify.sh v5). VLM verdict on the
  corrected day look: "more like authentic Silent Hill 1 — distant geometry
  darkening into the fog rather than washing to the fog color."

## 4. HERO flashlight (per task spec: HERO == the virtual camera)

* Light pos = camPos + camQuat*offset, offset = engine (-0.08,-0.28,0.12) →
  glTF (-0.08,+0.28,-0.12) (Game_FlashlightAttributesFix + Gfx_FlashlightPositionUpdate:
  bone matrix × Q8 offset); beam = camQuat × (0,-1061,-3957) (15° DOWN, func_8003F4DC);
  field_28 = clamp16(beam)×intensity>>12, field_30 = pos Q8, DQA = intensity>>8 — all verbatim.
* func_80057658 per-vertex math: unchanged (v4-verified 539/539 vs the decomp
  transcription; RTPS opcode 0x4A180001 → sf=1/lm=0, TR=0 via gte_ldtr_0,
  PushSXY clamp [-1024,1023], depth-cue clamp [0,0x7FFF], UNRDivide exact —
  re-verified against DuckStation this session).
* The IPD normals: engine into-surface convention (glTF normals NEGATED, s8
  127=1.0, <<5) — unchanged, re-derived: the syC term (N̂·δ/|δ|²) only lights
  faces whose into-surface normal has positive dot with light→vertex.
* The 1/δ falloff is authentic and short-range: full brightness ~1-2 m from the
  light, ~27% at 3 m (game: Harry's light at 1.3 m), ~5-12% at the 6-14 m floor
  band visible from the 3.43 m track camera. The {6,3} spot-1.3 beam reads as a
  clear pool (VLM 8/10, 8.0% of pixels illuminated vs flashlight-off); the {7,4}
  spot-0.7 nightmare beam is authentically dimmer (0.7% of pixels).

## 5. v5 verification (all PASS — verify.sh)

* Determinism byte-identical; benchmark↔shot bridge byte-identical (day + night).
* Turn rate measured **exactly 160.0 deg/s** across the new track's pingPong
  turnaround (t=25.0→25.9, yaw +169.78→+25.78).
* Camera audit: 30 tracks × 401 rows vs the camtrack.html JS ground truth — 0 mismatches.
* Math audit: 539/539 (func_80057658 grid + DPCL + DPCS + UNRDivide); env blend
  fade audit: 181/181 ticks.
* Day references (t=0/10.5/20.5/31.5/41.5 @960x540 + t=21.4 @640x360) pinned
  byte-identical after the veil/far-cull correction.
* Boot(camdat nighton/flashlighton) == `--night --flashlight --fog` **byte-identical**.
* Night/nightmare pixel-verified: night-off max=54, nightmare-off max=51 (enveloping
  darkness); {6,3} flashlight = visible pool; {7,4} = authentic dim beam;
  night vs nightmare fog differ 7.03%@thresh2 (9.3 m vs 14 m).
* VLM passes: 9-shot grid — day row PASS (coherent fog, no glitches); night row
  PASS (flashlight clearly visible in {6,3}+fl; enveloping darkness in both off
  states — nightmare 10/10 "total enveloping darkness"); PSX-wobble night clean;
  the t=25 "empty" frame is the pingPong turnaround (the camera sits past the
  model end z=120.05 looking off-street mid-sweep — engine-faithful).

## 6. v5 scope exclusions (documented, engine-inactive or inapplicable)

* field_E=3 dynamic fog (preset 5, interior {6,5}) — see §2.
* Lens flare (func_8008D470): gate requires light view-depth > GeomScreen/2 —
  impossible with HERO≡camera (light ~0.3 m from the eye).
* Character silhouette fog overlay (Gfx_FogOverlayQuadDraw, bone file) — no
  characters in the viewer.
* func_8005A21C CLUT-animated model path (modelHdr->field_B_0) — the flag is
  not present in the GLTF rip; plain room models take the func_80057344 path.
* tintLightOverlap radial overlay — presets 6/3/7/4 all have it OFF.
* Water zones/lens flare (water.c) — THR has no water zones.

---

# v6 — GLTF Flashlight Illumination Fix (Controlled Non-Verbatim Exception)

## 1. Task premise vs measured reality

The tasking stated the flashlight "does not illuminate anything" due to a
modern-format limitation. Exhaustive audit result: **the illumination
pipeline was already complete and engine-exact; nothing in the GLTF path was
disconnected.** The perceived failure is a light-anchor GEOMETRY effect,
proven below with measured A/B deltas.

## 2. The full audit chain (every link verified)

| Link | Evidence |
|---|---|
| GLB normals | present on ALL 150 primitives, FLOAT, unit length (len=1.0000 sampled); roads (0,1,0), walls (0,0,±1), fences horizontal diagonals, foliage smooth; zero degenerate/zero normals (`tools`-side probe over every accessor) |
| Normal binding | `glb_walk_node` loads NORMAL per vertex into the 8-float vertex stream; `transform_item2` transforms by the model matrix (identity for this rip — no node transforms in the GLB) |
| Normal convention | `n_engine = -(n_glTF * 127) << 5` = into-surface s8 normal — matches `func_80057658` row 1 (`s_Normal.nx << 5`, s8); only into-surface normals give positive `syC` for lit surfaces (floor: engine y-down +y into the ground; glTF up-normal negated = same vector) |
| Delta | `vertex - light`, Q8 s16 — matches `mat->m[2] = screenXy[v] - field_3AC` (decomp line 380-382) |
| GTE constants | `SetGeomOffset(-1024,-1024)` → OFX = -1024<<16 (PSY-Q `gte_SetGeomOffset` = `sll 16` + `ctc2 $24/$25`, inline_c.h:274); `SetGeomScreen(16)` → H = 16 raw (`ctc2 $26`, inline_c.h:283); `UNRDivide` = DuckStation gte.cpp:531 line-for-line; DQA = `Q12_TO_Q4(intensity)` (bodyprog_80055028.c:264) |
| Value formula | `sh_mesh_light_vertex` = func_80057658 verbatim: RTPS rows [beam*I; normal<<5; delta], v0=delta, Sx=(UNR*IR1+OFX)>>16, PushSXY clamp ±1024, +1024 offset cancel, dp=IR0 depth cue, value = ((sx*sy)+sy*(dp>>4))>>5 -16, +wLI>>5, +min(sx/2+dp/4,48), clamp maxB (decomp lines 400-454) |
| Color path | fog-off: DPCS(tint, 4096-light<<5), light<8 → black; fog-on: DPCL(tint, light<<5, fog<<4) — Gfx_MeshDraw paths, engine-exact (verified by the 539-sample math audit, 0 mismatches) |
| Raster | `texel * vcolor >> 7` (PS1 modulate) applied to both OPAQUE and STP passes |
| Empirical | `--fp-dump` shows enum-1 values live (vcol 7-9 at 15-19 m — the exact formula output at those distances) |

## 3. The measured A/B proof (flashlight ON minus OFF, same camera)

| Camera | Height | Brightened px | >+30 | Max gain | Where |
|---|---|---|---|---|---|
| camdat track (y=3.43) t=5 | 3.28 m | 20.2% | 3,308 | +83 | fence/wall bases (frame edges) |
| camdat track t=10.5 | 3.28 m | 14.1% | 972 | +74 | fence/wall bases |
| camdat track t=20 | 3.28 m | 7.1% | 687 | +107 | fence/wall bases |
| eye-height track t=10.5 | 1.60 m | **29.7%** | **11,369** | **+91** | road pool (bottom-center) |
| eye-height track t=5/20 | 1.60 m | 32.7% / 27.2% | ~14k / ~11.5k | +91 / +99 | road pool |
| road-level fixed cam | 1.45 m | **51.3%** | **63,055** | **+156** | road pool (dead center) |

VLM verdict on the eye-height pair: **9/10** — "bright elliptical pool of
light on the road directly ahead, the chain-link fence and NO OUTLET sign
clearly illuminated, grassy bank and tree trunk partially illuminated"; no
holes/z-fighting/geometry errors (the "white square particles" = the
engine-authentic tpage-44 additive snow flakes; banding = the 15-bit PS1
quantize). VLM on the 3.43 m pair: "distinct bright cone down the center of
the street, pavement and fence bases lit" — noticeable, but the beam CORE is
out of effective range.

## 4. Root cause of "does not illuminate anything" on the supplied track

1. `func_80057658` divides by |delta|^2 in the fake perspective
   (H=16/Q8 units) → the light value falls ~1/d^2 with distance, and the
   fog-off path blacks out below light=8. The engine light anchor is
   Harry's TORSO bone ~1.2-1.5 m above the street (`Game_Flashlight-
   AttributesFix` + `Gfx_FlashlightPositionUpdate`; `player_control.c:6900`
   clamps the player to the ground surface, :6938 roots the skeleton there),
   so the beam ellipse lands 4-6 m ahead — inside the visible range, on
   camera.
2. The GLB is a ROOM-ONLY rip: no Harry, no skeleton (the actual
   "modern-format limitation"). The camera became the anchor substitute
   (user directive: light origin = camera EXACTLY).
3. The supplied camdat track rides at y=3.43 (3.28 m above the 0.148 walkway
   datum — a classic SH1 high street-cam). From there the beam ellipse lands
   ~12 m out where the authentic value is ~13/255 → the core is black; only
   the beam periphery (fences/wall bases, 4-7 m) glows (+74..+107 measured).
   Preset 3's verbatim `wLI = 0` also means fl-ON drops the ambient swap:
   beyond ~5 m the fl-OFF ambient (wLI 0.44) is brighter than the beam.
   Net perception at 3.43 m: "the flashlight does nothing" — which matches
   the user report exactly.

## 5. The v6 changes (all traceable; zero modernisation)

1. **Anchor = camera EXACTLY** (user directive): `sh_env_update_pose` sets
   `light.pos = camPos * Q12` directly. The engine chain (torso bone +
   (-0.08,-0.28,+0.12) offset) stays cited in the source comments; the
   0.31 m offset is sub-perceptual at street scale. Beam = camQuat *
   (0,-sin15,-cos15) — engine verbatim, unchanged.
2. **Fixed-camera session clock** (`playback_step`): the clock advance was
   moved BEFORE the fixed-cam early-return so `--cam` sessions advance the
   env/snow simulation like the engine's game clock (v5 froze them; also
   hung `--cam --shot` forever). Engine-faithful bug fix; the track path is
   bit-identical (same operations, same order for track cameras).
3. `input/camdat_eye.json` — the supplied track at eye height (y=1.75,
   +1.60 m over the walkway datum) shipped as the visibility demo.

NOT changed: presets, pairs, blend, fog, snow, wobble, camera, GTE math,
DPCS/DPCL, raster. Day references and all flashlight-OFF renders are
byte-identical to v5 (verified); only flashlight-ON frames change (by the
0.31 m anchor shift: the {6,3} fl contribution moved 8.0%→7.5% of pixels at
the audit track time).

## 6. The one open item (NOT invented — decision requested)

To show the classic pool ON the supplied 3.43 m track, the light anchor
must drop to the engine's actor height (~1.2-1.5 m above the street). That
constant lives in Harry's ACTOR MODEL binary: the decomp repo's `rom/` is
empty (game data not distributed), and the GLB contains no actor. Options:
(a) author camdat tracks at eye/actor height (zero code change — v6 already
renders the authentic pool, see the table above); (b) supply Harry's model
or a documented light height, and v7 will anchor a virtual actor at
(camera XZ, datum + h) with everything else verbatim. No height constant
was guessed in v6.

## 7. Regression verification (v6, full suite)

* verify.sh: ALL GREEN — determinism, benchmark<->shot bridge (day + night),
  turn rate exactly 160 deg/s, camera audit 30 tracks x 401 rows = 0
  mismatches vs camtrack.html JS, env math audit 539/539 vs decomp, env
  blend audit 181/181, day-gate refusal, boot == explicit flags.
* Day references t=0/10.5/20.5/31.5/41.5 + mid-turn: BYTE-IDENTICAL to v5.
* Flashlight-OFF night renders: byte-identical (the anchor only enters the
  enum-1 path; with spot=0 the light value collapses to wliAmb=56,
  position-independent — verified).
* Fog / Snow / PSX wobble / Camtrack camera: code untouched (fog math,
  snow system, snap, turn filter) + byte-identical renders.

## AUDIT v11 (this release — the fog veil fix)

| feature | PoC location | ground truth (file:line / function) | notes |
|---|---|---|---|
| FOG VEIL (all prims) | `transform_item2` fog tail: `if (fogOn && fogColNZ)` | `Gfx_MeshDraw` bodyprog_80056D8C.c:1005-1189 (enum-0) and :694-883 (enum-1/2) | v11 FIX: the additive veil (fogColor*f) applies to EVERY textured prim. NON-STP branch (1175-1183): setSemiTrans(poly3,1) + addPrim(poly3) then addPrim(poly2) — OT head insertion = LIFO draw order: the OPAQUE fog G4 (poly2, fogColor*f via dpcs DP=T) is the BASE, the semi-trans textured GT4 composites ON TOP (ABR=1): final = fogColor*f + (texel*tintEff*T)>>7. STP branch (1157-1174): opaque textured GT4 + semi-trans fog G4 on top — SAME formula. v5-v10 gated the veil on isStpPrim (misread: "below, invisible") — broke the normal fog (distant opaque geometry -> black). Fixed; verified vs v3 ground truth (mean RGB within ~1 unit) + VLM audit PASS. |
| veil factor | `fq12 = ramp*16 + fogIntensity` (clamp 4096) | Gfx_MeshDraw var_t3 = Q12(1)-field_252[v]*16-field_4 (clamp >=0); dpcs(DP=var_t3, RGB=fogColor, FC=0) -> fogColor*(1-var_t3/4096) | identical math (T-clamp == fq12-clamp); fogColor==0 skip is a no-op (dark presets unchanged) |
| DuckStation GTE (wobble) | `gte_snap_screen` (floor), `gte_unr_divide`, `GTE_UNR_TABLE[257]` | duckstation src/core/gte.cpp: RTPS :754-786, UNRDivide :531-573 | UNR table 257/257 byte-identical; UNRDivide 200,512 randomized cases 0 mismatches; PushSXY(s32(Sx>>16)) truncation == floorf snap. UNTOUCHED by the v11 fix (byte-identical night renders prove end-to-end). |


## AUDIT v12 (this release — the ultimate verbatimness audit)

Whole-repository line-by-line comparison: the ENTIRE v11 fog_poc.c (8,202
lines) vs the decomp weather/effects/lighting core (map_info.c, world_effects.c,
bodyprog_80055028.c, bodyprog_80056D8C.c, particle.c, rng.c, fixed_point.h)
and DuckStation (gte.cpp: UNR/RTPS/DPCS/DPCL/MVMVA-FCbug; gpu_sw_rasterizer.inl:
modulation / black-texel / ABR=1 / dither). 9 discrepancies corrected; 2
engine/package defects discovered; ZERO visual regressions (45/45 mode
configs byte-identical to v11 + verify.sh all-pass + VLM fog check).

| feature | PoC location | ground truth (file:line / function) | notes |
|---|---|---|---|
| enum2->1 blend ramp | `sh_env_blend` weight2 else-branch | world_effects.c:759 `Q12_MULT(weight - Q12(1.0f/6.0f), Q12(1.2f))` | v12 FIX: 683 -> 682 (Q12 truncation); no reachable pair mixes the enums |
| DPCS/DPCL output clamp | `gte_dpcs_fc0` / `gte_dpcl_fc0` | DuckStation gte.cpp TruncateRGB (u32)(MAC>>4) > 0xFF -> 0xFF | v12 FIX: unsigned semantics (negative MAC -> 255; unreachable for k<=4096) |
| 800DD592 snow-spawn-type | `sh_particle_weather_tick` i==0 block + `snow_spawn` + `snow_movement_update` Unk1 branch | particle.c:465-545 / :3501-3508 / :3192-3200 | v12 FIX: verbatim switch (count>=76 fields 4/6/32/48, >=151 fields 5/7/40/56); Unk1 vy ramp = 12 - prevPosY - 2*prevPosY - (count>>4) + GEN(rand,-2,2), limitRange(5,1000), fresh RNG draw |
| per-tick RNG order | `snow_tick` rand draw before the wind ramp | particle.c:868 vs :872-913 | v12 FIX: engine order (matters once wind >= 2 draws 2/tick) |
| tail zeroing | `snow_tick` post-bank loop | particle.c:583-586 | v12 FIX: state=0 beyond addedCount[0]+addedCount[1] |
| field_234A transition lock | `sh_particle_weather_target_set` gate + completion set | particle.c:3870 / :551 / :3926-3929 | v12 FIX: D0B18 refused mid-fade; side effects field_2349=arg0, prevPosY=(wind 0 or 2)?2:0 |
| snow density selector | `snow_reset` / `snow_tick` pass 0 | particle.c:676 / :1273 `(field_2349 == 1) ? 1 : 3` | v12 FIX: tracked (boot BSS 0; D0B18 sets =arg0) |
| wind in snow movement | `snow_movement_update` +windX/+windZ | particle.c:3202-3204 | v12 FIX: verbatim (v11 hardcoded 0; wind now reachable) |
| ALL weather exposure | W key 0..8 + `--weather-target N` | sharedFunc_800D0B18 full arg domain; map0_s00_2.c:1679 (arg 6) | v12: all NINE runtime states selectable; wind machinery live |
| bank-count clamp | `sh_particle_weather_tick` post-switch clamps | engine has NO clamp (latent overrun: D0B18(6) fields 40/5 -> temp*2 up to 600 > 300) | v12: verbatim math + lawful clamps (D10 documented) |
| STP-hole veil | `raster_tri` AUDIT NOTE (behavior kept) | Gfx_MeshDraw:1157-1174 literal reading vs the v3 user-verified ground truth | analyzed + tested + REVERTED (+33 mean RGB; VLM: washed-out); v3 == ground truth per the task book |
| v11 package goldens | `reference_shots/` regenerated | the shipped v11 set was not reproducible by the v11 binary (D11) | v12: full golden set regenerated from this binary; nightoff uses --no-flashlight |

## V40 audit round (2026-11-20) — the QA fleet's verified findings + PR index

Six-agent parallel audit fleet (A: water, B: camtrack, C: drivers/lighting,
D: ripper/EXTRAs, E: dynamic stress, F: wallpaper sync) + a 4-agent targeted
verification wave (V-a..V-d) + coordinator re-verification of every headline
finding with runnable A/B repros. **21 confirmed bugs, 1 refuted false
positive, 0 shipped false positives.** All fixes land as one-PR-per-bug on
`audit-v40/*` branches (the user's PR-based reporting directive); the
integration branch `v40-integration` carries all of them together with the
full test battery green (3 self-test goldens byte-identical, camera parity
30/30, roundtrip byte-identical, whole-map functional).

| ID | Sev | Bug (one line) | PR |
|----|-----|----------------|----|
| A-F1 | MAJOR | glint blit: packed-nibble fetch on the UNPACKED DR_WAVE sheet = wrong half + forced index 0 on odd columns | #1 `audit-v40/fix-glint-texel-nibble` |
| A-F3 | MINOR | scroll tick omits shLensFlareExec Gate-2 (scroll advanced in an engine-impossible state; NOTE: verbatim gate freezes camera-mounted-light floors — maintainer decision) | #3 |
| A-F4 | MINOR | ripple mesh reads sprite 0's selector; the mesh's own RNG draw missing (stream off by one) | #4 |
| A-F5 | MINOR | ripple sprite cull `((z+128)>>3)>=1024` vs engine `(z>>3)>=2048` (drops 31.5-64m sprites) | #5 |
| A-F6 | MINOR | droplet backward taper leaks into vertical droplets (latent on shipped streams) | #6 |
| B-B1 | MAJOR | `once` loopMode wrapped endlessly in the engine; the editor holds at the end pose | #7 |
| B-B2 | MINOR | camtrack waterfall tick: one camera pose for all catch-up ticks vs the engine's per-tick poses | #20 |
| B-B4 | MINOR | editor num()/vec3()/pair coerce where the engine's JV_NUM is strict (silent preview-vs-engine divergence) | #18 |
| B-B5 | MINOR | editor exports models with `tracks: []` that make BOTH C consumers hard-fail (now warns) | #21 |
| B-B9 | MINOR | authored `tileLen: 0` hangs the surface-scroll while loop (C + JS) | #8 |
| B-B10 | MINOR | fixed-track position default `[0,1,0]` vs the C's `{1,1,0}` | #19 |
| C-F1 | MAJOR | g_SysWork.lightIntensity multiply only in the enum-2 branch; the decomp applies it for EVERY light mode (effects.c:476) — the boiler-room Spot light never flickered | #9 |
| C-F2 | MINOR | multi-shot reset lacks sh1x_anims_bind_invalidate (driver 9 zeroed live state on shots 2+) | #10 |
| C-F3 | MINOR | live_save_final re-calls the water pair at the held tick time (save-final != shot on water rooms) | #11 |
| D-F1 | CRITICAL | ripper TIM decode: opaque-branch transparency caught 0x8000 (STP-set black) — 12.5% of shipped packs affected; SwanStation: only exact 0x0000 | #14 |
| D-F2 | CRITICAL | waterFloor clut15 parse `&0x7FFF` destroyed the STP bit the floor builder's own alpha classes need (DR0100/DRFD00 all-16-STP palettes rendered opaque-replace) | #2 |
| D-F4 | MAJOR | `--whole-map` 100% broken since inception (NameError: map_rooms — a main() local) | #15 |
| D-F5 | MAJOR(doc) | SH1X schema doc decoded texIdx/semiTransparent from b6; the decomp's bits1 union uses b7 (737/1310 HP0003 packs mis-bound per the doc) | #17 |
| D-F6 | MINOR | tvPaint strip column base 48 vs 64 (VRAM 512+64*si - clut base 448) | #16 |
| E-F1 | MAJOR | `--cam nan inf...` exited 0 with a flat frame + 8 UBSAN reports; `--t nan` hangs the realtime window | #12 |
| E-F3 | MINOR | `--track -1` silently fell back to track 0 | #13 |
| — | FIX | camera_audit_run.sh pointed at input/THRF9FD.glb (removed in v25) — the parity harness was dead | #22 `audit-v40/tools-camera-audit-path` |
| F-F2/WP | CRITICAL | the wallpaper's `93a3aa0` "v39 engine sync" predated the PoC's v39-audit fixes by 96 minutes: ALL SIX draw-path corrections (A1-A6) + the A7 cleanup missing; LIVE on the shipped SUFFFE/SU0203 waterfall scenes | wallpaper#1 `audit-v40/v39-audit-sync` (verbatim port of 597f6ee) |

**Refuted (no PR):** F-F10 "asset commits should bump MINOR not PATCH" — the
CI's asset=PATCH bump matches the user's own worked example
(`1.7.30 -> 1.7.31` = last-segment bump). The wording-vs-example ambiguity is
the user's to adjudicate; no change made.

**Follow-up observations (recorded, not PR'd — primary agent's judgment):**
the shot path binds driver 9 after its fast-forward (a gravityScatter never
visibly falls in `--shot` mode even after C-F2); the R-restart rebind re-seeds
driver 9 from the fallen pose, not the authored heights; `engine_fog_80055A50`'s
`(temp << 7)` is latent UB for negative OTZ; the wallpaper's `sh1_hw_render.c`
GPU backends walk a pre-v24 render_frame (no propAnims/flare/water on the
opt-in GPU path — default software backend unaffected); the committed
`sh1.keystore` signs official CI releases (user's own repo, noted); the
wallpaper engine twin still needs the other V40 engine fixes at the next sync
(glint nibble, waterFloor STP, scroll Gate-2, ripple selector/depth,
once-mode, lightFlicker — the PoC PRs #2-#13 are the canonical hunks).

## V41 audit round (2026-11-21) — the QA fleet's verified findings + PR index

*Reimplemented by the maintainer from PR #50 (audit-v41/findings-map): the
branch's own table was verified clean row-by-row, but its HEADLINE counts
("42 findings: 3 CRITICAL, 10 MAJOR, 22 MINOR, 7 INFO") contradicted that
table (mechanical recount: 2 CRITICAL, 10 MAJOR, 28 MINOR, 1 doc, 9 INFO, 56
IDs counting grouped rows; no third CRITICAL exists anywhere) and it omitted
wallpaper#6 from its index — a findings-map misstating its own map is the
exact failure class it exists to prevent, so per the gate protocol the PR
was rejected and this corrected section landed instead.*

A fresh 6-agent audit fleet (A: water re-audit incl. the maintainer's 333f1b1
reimplementations, B: camtrack editor, C: render pipeline + lighting, D:
TIM/texture/VRAM data, E: CLI/runtime stress, F: the 7 aims' wiring across
all four programs) + a 5-agent targeted verification wave (a..e, one per
report) + coordinator re-verification of every headline finding. **Confirmed
findings per the maintainer's recount: 2 CRITICAL, 10 MAJOR, 28 MINOR,
1 doc, 9 INFO — 0 refuted, 0 shipped false positives.** The maintainer's V40
reimplementations (333f1b1's gate chain, mesh selector, light.ahead mode-2)
were re-audited and verified CORRECT (AUDIT_V41_A Part 1).

| ID | Sev | Bug (one line) | PR |
|----|-----|----------------|----|
| E-1 | CRITICAL | `--weather` (no value) read argv[argc] — SIGSEGV exit 139; the ONLY unguarded value-flag of 33 | #24 |
| D-1 | CRITICAL | TV-noise paint sampled 8bpp (`u>>1`, byte idx) but the engine draws 4bpp (tpage mode bits 7-8=0; TV TIMs are 4bpp 0x08) — LIVE on the shipped wallpaper SPU0401.glb (style-1 ~99.5% texels wrong, style-4 100% unmodeled) | #38 + wallpaper#5 |
| E-4 | MAJOR | `--r2shot t=inf` hangs (timeout-kill), `t=nan` silent t=0 — the E-F1 gap | #25 |
| E-3 | MAJOR | K_R restart misses ALL five v40-A4 water globals (restart != fresh; RNG stream, scroll phase, tile gate, belt, TV pad carried) | #26 |
| E-2 | MAJOR | g_flaresys.nowEffRate in no reset list (multi-shot != solo: nowRate 1015 vs 1523, 100/146 px diffs, runtime-proven on shipped sewer/TV) | #27 |
| E-5 | MAJOR | tim_load had no bounds checks (crafted 40-byte TIM = SIGSEGV + 8.6GB alloc attempt, ASAN-proven) | #28 (REIMPLEMENTED — see gate note) |
| A-3 | MAJOR | ripple spawn (the 49 RNG draws) ran under the flashlight-darkness draw gate; the engine spawns at Map_WorldObjectsInit unconditionally (map5_s00.c:1247-1250) | #29 |
| C-1 | MAJOR | flare angle math fed the WORLD-space L->dir into view-space math (engine ApplyRotMatrix's it first, lighting.c:228) — engine-true 82.01° constant vs 77.7..89.1° wobble; LIVE on sewer/TV + 7 authored-light camdats | #33 |
| D-2 | MAJOR | TV1 VRAM model clipped x<864 but the upload spans 832..895 (fs_queue.c:657) — style-4 windows read garbage | #39 |
| F-2 | MAJOR | wallpaper ASSETS array copied only 4 files — 43/44 bundled scenes unreachable; the v11.2 dynamic copy lost in the base reset | wallpaper#4 |
| F-1 | MAJOR | the twin missed ALL the V40 fixes (18 hunk groups; quantified: 37 hunks/~199 lines) — split into the fleet-canonical sync + the maintainer-parity port | wallpaper#2 + wallpaper#3 |
| F-3 | MAJOR | the wallpaper's shipped GLB corpus is a pre-v39/v40 rip (D-F1 baked in live: 1,559 alpha-0 holes on SU1FTE2_pal3; 0/44 rooms carry stream/waterTex/statics) | workflow re-rip (maintainer) — see follow-ups |
| A-4 | MINOR | mesh depth cull used the 4-corner average; engine culls on corner [i][j] (map5_s00.c:204) | #30 |
| A-5 | MINOR | ripple sel==2 read g_waterTileRGB without the lazy first-composite gate (black tile on the mode-0 anchor, stale on multi-shot) | #31 |
| A-6 | MINOR | fx_blit_water_quad UV solve axis-aligned (u from screen-x); engine POLY_FT4 interpolates along quad edges — oblique shear (2,983 px removed in the A/B) | #32 |
| C-2 | MINOR | occluded-branch core quads 1-2 painted over everything; engine routes them depth_ot / depth_ot+7 (7 buckets FARTHER = +0.21875 m) — REJECTED-INERT at the gate (see gate note) | #34 |
| C-3 | MINOR | ring/glint occlusion gates 19.53/19.47 m inverted the RIPPLE rule; the mesh rule (SZ>>3, bucket far edges) gives 20.0625/20.0 m — a 0.5 m band missed | #35 |
| C-4 | MINOR | MASK far cull `cq8 <= farCull` vs engine strict `(cq8 & ~3) < farCullQ8` (billboard.c:263-266) | #36 |
| C-5 | MINOR | flare probe lacked the ang_z >= 75° tile bound (lens_flare.c:103) + MASK leaves never occluded — with C-1, sewer/TV engine-true show NO flare (ang_z 27.07°) | #37 |
| D-3 | MINOR | the "8bpp" gate `((flags>>3)&3)==1` is a no-op (passes 4bpp/8bpp/16bpp); correct = `(flags & 3)` per the project's own TimFile | #40 |
| D-4 | MINOR | extract_rain/snow mislabel PMODE bits (1=8bpp, 2=16bpp) + wrong width multiplier (64x256 -> 128x256) | #40 |
| D-5 | MINOR | stale extractor paths + the extract_water_tim.py that ea07754 claimed but never committed (provenance gap; the new script round-trips water_tim_data.h byte-identically) | #40 |
| B-1 | MINOR | circle speedDegS parse lacked the >=0.001 clamp (editor parity; spiral/figure8 had it) | #41 |
| B-2 | MINOR | editor DROPPED malformed points[] entries; the C coerces to [0,1,0] and counts RAW (path shape, >64 truncation, --track N indexing all diverge) | #42 |
| B-3 | MINOR | 7 remaining isFinite(+v) gates accept strings/bools (weatherTarget, envDay/Night, sanitizeLight pos/rot/offset/ahead) vs the C's strict JV_NUM | #43 |
| B-5 | MINOR | duplicate track ids leak one undisposed THREE.Group per visuals-Map rebuild | #44 |
| B-6 | MINOR | snow ground datum for circle/curve/fixed was a NaN probe (t=0/0 -> lrintf(NaN)=0 garbage grid ALWAYS; THRF9FD: 21,714 cells vs the editor's true datum) | #45 |
| B-7 | MINOR | editor snow backward-seek re-simulated with the END-frame camera (C: per-tick eval — 300/300 flakes differ, the B-B2 class in the snow twin) | #46 |
| B-9 | MINOR | Shift+F fired BOTH the flashlight toggle and the frame-model handler | #47 |
| E-6 | MINOR | stale tracked binaries + dead .gitignore pattern + the poc.yml:90 make race | #48 |
| E-7 | MINOR | Makefiles list 2 of 8 headers as deps (touch dr_wave_data.h -> "Nothing to be done") | #48 |
| E-8 | MINOR | ~12 numeric flags accepted trailing garbage (2abc = 2) — strict end-pointer parses now | #49 |
| E-9 | MINOR | >64 --shot args silently dropped (66 -> 64 files) — hard error now | #49 |
| E-10 | MINOR | explicit `--lensflare 0` lost to the camdat (0 conflated with CLI-silent) — -1 sentinel | #49 |
| E-12 | MINOR | negative --t/--shot/--r2shot silently rendered t=0; huge t = hours of CPU — reject + 3600s cap | #49 |
| E-11 | doc | --help said 1280x720; the code default is 960x672 | #49 |
| E-13 | INFO | benchmark duration int-overflow cast UB ("0 frames") — clamped before the cast | #49 |
| F-4 | MINOR | light.ahead dead in the twin (subsumed by the maintainer-parity port) | wallpaper#3 |
| F-6 | MINOR | twin lacked the `static` driver + v40 statics parse — a v40 re-rip would SILENTLY drop all static scenery on Android (subsumed by the parity port) | wallpaper#3 |
| F-10 | MINOR | CUSTOM.md describes a WebView editor that is actually native (doc fix) | wallpaper#6 |
| C-6 | INFO | DPCL negative-MAC saturates 255; THIS swanstation returns 0 — 17,639/16.7M triples differ, unreachable on shipped rooms via the wLI floor (proof needs rewrite before any fix) | follow-up |
| F-5 | MINOR | camtrack renders no flare sprites/shimmer (the conformance table's "preview toggle" unimplemented — a feature decision) | follow-up |
| F-8 | INFO | mapLink boot-merge vs the engine's 4.5 m Q8 streaming (deliberate simplification; WORKLOG:850/902 still promise the edge probe — doc drift) | follow-up |
| F-11 | INFO | effectTexFlag parsed but never used (dead parse, both engines) | follow-up |
| A-7/8 | INFO | the engine's g_DeltaTime!=0 counter guard is unreachable in PoC discipline; inhibit flags never settable (structural fidelity notes) | follow-up |
| D-6 | INFO | DR_WAVE docstring "blank at v 32..63" inaccurate (2/2048 non-zero texels) | follow-up |
| D-7 | INFO | kFlareGhost3 duplicates kFlareCore (correct per lens_flare.c:484; ~4KB redundancy) + ghost3's additive blend is ~2x hardware ABR-2 strength | follow-up |
| B-4 | MINOR | r4(±Infinity) exports JSON null — round-trip mutates hand-edited 1e999 fields (needs a DESIGN decision: visible normalization vs documented garbage-in) | follow-up |
| B-8 | INFO | SMOOTH filter integrates per-rAF + snaps when paused vs the C's per-30Hz-tick + hold (documented editor semantic; the C banner's "snap on pause" overstates — the branch is unreachable while paused) | follow-up |
| E-14..18 | INFO | SDL-only test facilities; unchecked fwrite/malloc + unclosed g_lightDump + hardcoded shots/ in K_S; silent flag precedence; glb_accessor negative byteOffset wrap (harden all five sites or none); --weather 2 boot no-op quirk | follow-ups |
| E-2 | INFO | tick-grid easing residual: the live tick's D_800AFDAC advance can sit one tick off the shot grid (needs an easing-model audit before touching) | follow-up |

**Refuted/verified-correct (no PR):** the maintainer's 333f1b1 gate chain +
mesh selector + mode-2 selection (AUDIT_V41_A Part 1 — verbatim-verified);
the sine table (5120/5120 == decomp == round(sin(i/4096*2pi)*4096)); all BG_ETC/
DR_WAVE/WATER tables byte-identical to sources; the V40 glint A-F1 unpacked-sheet
indexing; F-9 (the wallpaper CI version scheme already matches the user's
directive — 1.0.0 renumbering + asset->PATCH bump); 40+ further refuted
candidates documented per report in download/v41_evidence/.

**MAINTAINER GATE (2026-11-21, sole-merger review of the 32 PRs):** a
7-agent verification fleet (V41-A..F + RC) re-verified every PR against the
decomp/swanstation + probed on main. Outcome: 24 PoC PRs MERGED as-is (#24-#33,
#35-#49 — each verified, conflict resolutions documented in the merge commits);
**#28 REIMPLEMENTED** (its 95%-correct hunks + the missing zero-dimension
guard: a crafted ph=0 TIM still OOB-read up to 256 KB — ASan-proven by the
gate, committed as the maintainer's own commit per the user's protocol);
**#34 REJECTED-INERT** (the occluded-branch fix is decomp-faithful but its
symptom does not exist on main: the core quads rasterize 0 texels due to a
DEEPER bug the gate found — see below — re-land after that lands);
**#50 REJECTED+REIMPLEMENTED** (this section: corrected recount + the
wallpaper#6 index fix). Wallpaper: #2-#6 all verified faithful and merged.

**NEW ENGINE BUGS THE GATE FOUND (not covered by any PR — follow-up work):**
1. **fx_blit_sprite_quad's point-in-quad test rejects the quad INTERIOR**
   (fog_poc.c — the `!(neg&&pos)` sign convention accepts only outside
   strips): ALL flare core quads + the 3 ghosts have painted ZERO texels
   since v26 — the PoC flare has been streaks-only; this is why C-2 is
   inert. Fix spec: the fx_blit_gouraud_tri edge-function convention; then
   re-land #34; then re-shoot the flare goldens.
2. **--snow-seed is dead** (snow_reset at fog_poc.c:6914 clobbers
   S->rngSeed = SNOW_SEED_DEFAULT after all 3 CLI sites assign it —
   probed: --snow-seed 999999 renders byte-identical to default).
3. **R-restart weather-transition carry** (snow_reset never resets
   weatherCurrent/Target/weatherTick — post-restart renders differ from
   fresh on DRU0100; probed via the --nosnow asymmetry).
4. pr_47's Ctrl+F variant (the frame-model handler has no ctrl/meta guard).
5. The editor's registerModel hooks go stale after camdat import (the snow
   grid/flake rest silently degrade to the live-cam behavior in that flow).

**Battery re-baselines to expect when these merge:** C-1+C-5 remove the
sewer/TV flare entirely (engine-true ang_z 27.07° < 75°); D-1+D-2 recolor the
TV static + wake style-4 windows (TV A/B 6.55% -> 8.88% with #38, 10.15% with
both); A-3 changes dark+flashlight rooms' RNG-affected output; A-6 changes
oblique water views (no shipped golden); B-6 removes the garbage resting-snow
grid on fixed-track snow scenes.

**Wallpaper follow-ups (workflow, not code):** (1) the corpus re-rip (F-3)
needs the CDN /sh1 corpus + WATER.TIM — do it AFTER wallpaper#2/#3 merge
(the statics driver must land first or the re-rip silently drops static
scenery); (2) the wallpaper twin still needs the remaining V41 engine fixes
(C-1..C-5, A-3..A-6, E-2/E-3 at the next sync after their PoC merges —
D-1/D-2 landed as wallpaper#5).

Full evidence: the six AUDIT_V41_* reports + five VERIFY_V41_* reports +
per-fix FIX_V41_* reports (branch, diff, verification transcripts) at
/home/z/my-project/download/v41_evidence/ (mirrored in the audit fleet's
sandbox; the PR bodies carry the per-bug essentials).

---

# V42 audit (2026-11-21) — "Rinse and Repeat" wave 2

The V41-gate follow-up round: 6 finder agents (A engine-fresh-code,
B camtrack, C water/env/lighting, D CLI/determinism, E wallpaper/lively,
F aims/ripper) → 2 verifier agents (V-1 rasterizer family, V-2 camtrack
family) + 1 fixer (V-4 lively re-port) + the coordinator's own
re-verification of every shipped fix (each A/B reproduced independently).
Evidence: `download/v42_evidence/` (AUDIT_V42_A-F, VERIFY_V42_a/b,
FIX_V42_d_lively + probes/harnesses/crafted inputs).

## Headline counts (mechanically recounted from the table below)

**40 unique findings: 1 CRITICAL, 1 CRASH, 12 MAJOR, 16 MINOR, 10 INFO.**
(F-3 == D-5 deduplicated; the C-2 re-land is a V41 follow-up, not a new
finding.) **0 shipped false positives** — every PR's A/B was reproduced
by the coordinator before opening. **17 PoC PRs (#51–#67), 1 Wallpaper
PR (#7), 1 lively PR (#1)** = 19 PRs; 13 findings left as documented
follow-ups (below) — most need the primary agent's design/re-rip calls.

## Findings table

| ID | Sev | Finding | PR / status |
|---|---|---|---|
| E-2 | CRITICAL | the lively repo shipped the v39 engine (every V40/V41/V42 fix missing, in the released v1.0.4-sh1 exe) — full re-port + parity 65/65, render-parity 5/5 md5-identical | lively#1 |
| D-5 | CRASH | GLB accessor negative byteOffset wraps size_t past the bounds sum → OOB read/SEGV (E-18 live; two finders' ASan proofs; same class as fe9a034) | PoC#64 (=F-3) |
| A-1 | MAJOR | fx_blit_water_quad still the pre-5e9489d broken inside-test — ripple quads paint mirrored garbage strips (DRFD00 live; DR0000/DR0100 driver-present but player-gate-blocked) | PoC#52 |
| A-2 | MAJOR | fx_blit_sprite_quad UV solve axis-aligned — rotated streak kites mis-textured / dead at ±45° (swanstation CalcIDeltas is per-triangle 2D affine) | PoC#53 (A2c) |
| B-10 | MAJOR | camtrack authored-beam dir transcribed wrong (x/z swap + dropped negation) — 0/108 grid match, every authored light renders sideways | PoC#55 |
| B-11 | MAJOR | camtrack tvEmitQuad never divides V by 256 — TV screens tile vertically (LIVE on shipped SPU0401) | PoC#56 |
| B-12 | MAJOR | castHandles early-return — light spheres undraggable on trackless models (the SPU0401 first-impression flow) | PoC#57 |
| C-1 | MAJOR | gte_dpcl_fc0/dpcs negative-MAC saturates 255; hardware (swanstation TruncateRGB signed, psx-spx) clamps 0 — REACHABLE in the night fade (the V41 wLI-floor claim refuted); sub-visual on the shipped battery | PoC#63 (+the C-2 doc misquote folded) |
| D-1 | MAJOR | K_R never re-armed the boot/camdat weatherTarget cross-fade — restart locks at the room recipe (restart != fresh) | PoC#66 |
| D-2 | MAJOR | the window --duration/--save-final overshot the tick grid by one tick (181 vs 180; the E-2 residual, NOT the easing model) | PoC#67 |
| E-1 | MAJOR | copyAssetsIfNeeded never refreshed existing data-dir files on APK update — upgraders stuck on stale assets (blocks the F-1 re-rip from reaching upgraders) | Wallpaper#7 |
| E-3 | MAJOR | lively bundle camdat pre-9d42961 (7 SPU/DR models still dayEnv=1) + 2.zip repack + freshness gate | lively#1 |
| F-1 | MAJOR | shipped corpora stale: 0/44 statics (28 expected), WP SU0203 waterfall lacks the v39 stream block, SPU0401 tvPaint strip pre-D-F6 — the V41 F-3 re-rip never ran (the statics driver has now landed) | follow-up (primary's re-rip) |
| F-2 | MAJOR | aim 5 "ALL of them": FIRE (+Ef) and smoke ambient particles unencoded + unported (env_effects.c:142-158, fire.c:28-30, map1_s05.c:333 — live on 8+/44 scenes); waterfall is the ported precedent | follow-up (primary's port decision) |
| A-3 | MINOR | the C-5 occlusion probe reads the UNSCALED engine px — wrong pixel at every --res != 320x224 (phantom flare with the C-2 gate: 3372 px @640x448) | PoC#54 |
| B-13 | MINOR | invisible light spheres stay raycast-grabbable (three r170 Raycaster ignores .visible) — phantom grabs rewrite l.rot | PoC#58 |
| B-14 | MINOR | dev-toggle label fires change twice on its own padding — dead toggle | PoC#59 |
| B-15 | MINOR | line/fixed light modes clobber the authored rot | PoC#60 |
| B-16 | MINOR | __camtrack.fog/night/flashInfo dereference ids that never existed (TypeError) | PoC#61 |
| B-17 | MINOR | TV_MAX_QUADS 13 vs the C's 24 (latent 2-big-screen drop) | PoC#62 |
| D-3 | MINOR | --userlight family accepted NaN/Inf (silent garbage frame; the E-F1 gates missed these sites) | PoC#65 |
| D-4 | MINOR | --cam argc guard demanded a 7th value — the 6-mandatory form at argv end was "unknown arg" | PoC#65 |
| D-6 | MINOR | --tim-file demands camdat discovery first + --tim N page number dead | follow-up |
| E-4 | MINOR | false "REMOVED" commit message (the stale Livesly tree still existed) | lively#1 (tree now actually deleted) |
| E-5 | MINOR | Android opt-in GPU backends still walk a stale render_frame (no propAnims/TV/flare/water-FX; gap grew since V40) | follow-up |
| F-4 | MINOR | mapLink probe quiet-contract violated: 3 stderr sites not quiet-gated (logcat noise on present-but-invalid neighbors) | follow-up |
| F-5 | MINOR | camtrack previews no flare/shimmer/waterFloor while SH1X_EXTRAS_V3_FX.md still promises them | follow-up (V41 F-5 re-confirmed) |
| F-6 | MINOR | the doc/WORKLOG promise the 4.5 m Q8 edge-probe streaming; actual = boot-merge (both engines) and PoC does NOT ignore mapLink | follow-up (doc-vs-code decision) |
| F-7 | MINOR | SH1X_EXTRAS_V3_FX.md inverts the version scheme (the CI's asset→PATCH matches the owner's 1.7.30→1.7.31) | follow-up (doc) |
| F-8 | MINOR | ripper problem log truncated at [:10] — content-loss warnings can vanish from derivation logs | follow-up |
| A-4 | INFO | probe/water-quad occlusion gates use the exact depth, not the OT-bucket far edge (≤0.03125 m band; the C-3 class) | follow-up |
| A-5 | INFO | claim-accuracy: 5e9489d "proper kite coverage" (33% real), 461d0bd 76.25%, 4467f41 "glint realigns" overstate | recorded |
| B-I1 | INFO | the LINE light travel (start/end/speedMS/loopMode) is editor-preview-only — the C's camdat parse reads none of it | follow-up (schema decision) |
| B-I2 | INFO | r4(x) overflows finite x ≥ 1.8e304 to Infinity→JSON null — a new sub-case of the registered B-4 design decision | follow-up (B-4) |
| C-3 | INFO | the V41 17,639 divergent-triple count CONFIRMED; the old cL≤255 cell restriction + wLI-floor argument refuted | recorded (in #63) |
| D-7 | INFO | --maplink abc silent 0 (bare atoi); --snow-seed -1 wraps to ULONG_MAX | follow-up |
| E-6 | INFO | derive_wallpaper_envs.py (credited by 9d42961) committed nowhere — provenance gap | follow-up |
| F-9 | INFO | the ENTIRE envEffects block is a dead parse in both engines (hasEnvEffects never read); shimmer actually gates on waterZones | follow-up (V41 F-11 broader) |
| F-10 | INFO | 40 stale false-alarm warnings per corpus rip (CONSUMER_IPD_MODEL_LAYERS claims wrong OT bases pre-v24) | follow-up |
| F-11 | INFO | sh1x_roundtrip.py expects DWAVE.TIM but the repo carries DR_WAVE.TIM (DRU0100 TIM skipped) | follow-up |

## The C-2 re-land (the maintainer's V41 instruction, executed)

PR #51 — re-derived on current main (not a cherry-pick): the 3-way OT
branch for core quads 1-2 (front_ot / own bucket / own+7) via the
fx_blit_gouraud_tri depthM convention. Regression 7/7 byte-identical;
positive occluded-center repro 273 px (the walkway case). NOTE: A-3's
visible effect rides this gate (stated precisely in #54's body).

## Verified-correct / passed (no action)

- The 21-preset table verbatim vs decomp (27 fields × 21); the N-cycle
  order; K_R's other state resets (C-4/C-5/C-6a PASS).
- The Android twin vs PoC main: **CLEAN — 0 missing engine hunks** (42
  diff hunks all benign: comments/harness/twin-only feature).
- tim_load fe9a034 hardening HOLDS: 149 crafted TIMs × 5 views = 745
  ASan runs, 0 hits.
- Determinism 17/17, multi-shot==solo 17/17, shot==benchmark bit-exact.
- The maintainer's reimplementations (fe9a034, c5631de, the gate chain):
  all re-verified sound.
- evalTrack C-vs-JS parity 30/30 (worst rel err 8.4e-07) pre/post the
  B-batch fixes; export round-trip fixpoint over 16 stress tracks.
- Refuted: --weather 3/4 as "engine values" (the decomp switch is
  0/1/2/5/6 only); the shared-edge double-paint; PR #32's parallelogram
  solve itself; the C-5 missing vz≥0 term.

## Wallpaper twin sync note (for the primary agent's next gate)

The twin needs these V42 hunks at the next sync: C-2 (#51), A-1 (#52),
A-2c (#53), A-3 (#54), C-1 (#63), D-5 (#64), D-1 (#66), D-2 (#67) —
all engine-logic, all port verbatim like ca23c26.

## Follow-up priorities (coordinator's read)

1. F-1 corpora re-rip (unblocked: the statics driver landed both engines;
   do it AFTER E-1 merges so upgraders actually receive it).
2. F-2 fire/smoke port (aim 5's completeness; the finder mapped the
   decomp sources precisely — a feature port, the primary's call).
3. E-5 GPU backend render_frame refresh (grew since V40).
4. The doc batch F-6/F-7 (+F-4/F-8 tooling hygiene).
5. D-6 (--tim-file standalone), D-7/E-6/F-9/F-10/F-11 hygiene.
