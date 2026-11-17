# SH1 WORLD EFFECT MODES — THE DEFINITIVE FACT-BASED GUIDE (PoC v17 — the engine billboard color path)

> **v23 note**: at the native 320x224 resolution the mode browser and the
> status HUD use the compact 40-column layout (every line fits the 320-px
> framebuffer); the 640x360 presentation keeps the full columns. The R2
> (self) view status line (R2 state, head offsets, limits) is part of the
> status HUD. All 21 presets + 24 authentic pairs are unchanged — every
> mode change still routes through the verbatim Gfx_MapEnvSet port.

> **v21 note — THE NATIVE RASTER + GPU-VERBATIM SAMPLING:**
> the default render resolution is now the engine-native **320x224**
> progressive raster (SCREEN_WIDTH / FRAMEBUFFER_HEIGHT_PROGRESSIVE,
> game.h; Screen_Init(SCREEN_WIDTH,false) at game_main.c:82; both the
> drawing clip and the display window are 224 rows — screen_draw.c:45-46;
> SetGeomScreen(gsScreenHeight)=224). The Y vertex-snap lattice is
> fb_h/224 (exactly 1.0 at native). ps1-mode texture sampling is the
> DuckStation-verbatim fixed-point DDA (integer-position evaluation,
> +0.5-texel Init bias, truncating Q12 ATTRIB_STEP gradients, the u8
> texcoord wrap) — the engine's own wire/hole crawl rate on the fence.
> The far cull is 0x79C<<3 (the outdoor WorldGfx_Draw(1) otShift chain —
> 60.9 m in fog-off modes). `--res 640x360` remains as a NON-ENGINE
> presentation mode. All 21 modes re-swept at native: no failures, night
> darkness / fog stability / dither+wobble defaults all verified. See
> CHANGES_v21.md.

> **v22 note — THE AUTHENTIC 30 fps PRESENTATION LOCK:** the realtime
> window now PRESENTS at strictly 30 fps (one present per engine tick —
> `--fps` defaults to 30; the meter measures the true wall-clock
> presentation rate, so it reads ~30.0, not the v20/v21 busy-throughput
> "111"). The tick content is byte-identical to v21; `--fps 60` remains
> the 60 Hz display-duplicate presentation, `--fps 0` is unlimited for
> benchmarking. See CHANGES_v22.md sections 1 and 4 for the full
> root-cause chain (meter bug + uneven pacing -> perceived flicker).

> **v20 note — THE 30 Hz TICK LOCKSTEP (the night+flashlight flicker fix):**
> every render path (realtime window, benchmark, --shot) now advances the
> camera+turn-filter, the env/light pose and the snow TOGETHER on the
> engine's whole 30 Hz game ticks (`g_IntervalVBlanks = 2` in-game —
> game_sys_states.c:93); output frames between ticks duplicate the tick
> state (F(2k)==F(2k+1), the real game's 30 fps content on a 60 Hz
> display). The v4-v19 60 Hz camera stepping against the 30 Hz light grid
> was the night+flashlight bush-strobe root cause (see CHANGES_v20.md).
> No rendering/lighting math changed — all 21 modes below are visually
> identical per tick; only the update cadence is engine-exact now.

> **v17 note — the Gfx_BillboardDraw NCT/NCS color path:** the MASK leaf
> billboard items (TREE_CANOPY/TREE_BUSH clusters) now take the engine's
> per-cluster color computation (billboard_draw.c NormalColor3/NormalColor
> with the func_8005A478 flashlight cone / func_8005A838 directional light,
> the light-magnitude rescale and the per-QUAD fog veil) instead of the
> MESH per-vertex light — the bush color flicker fix. All 21 presets re-run
> (the enum-0 day billboards are now the flat worldTint*wLI*fogAlpha color;
> see CHANGES_v17.md).

> **v16 note — the per-model OT LAYER BASES + the backface cull:** mesh
> quads (OPAQUE + BLEND) now bucket at `BASE + OTZ>>3` where BASE is the
> model's OT section from `func_80057090`/`func_800571D0(field_B_1)`
> (0/2/4/33/66/99 — the THRF9FD.IPD layer classes; the B-overlays,
> doors and chain-1 models ride 33/66/99 and are forced on top, the
> N-signs/NOTICE/chain-3 models ride base 0 below the standard base-2
> mesh layer, the billboard leaf diamonds + snow/rain flakes keep the
> base-0 section like Gfx_BillboardDraw/Particle_SnowDraw). MESH quads
> also pass the engine's `gte_NormalClip` dual backface cull (nclip on
> the snapped screen coords — `nclip(v0,v1,v2) <= 0 && nclip(v3,v1,v2)
> >= 0 -> skip`); MASK/billboard quads are never culled. All 21 modes
> below render through the same OT walk as v15 plus these two verbatim
> engine rules — re-verified 21/21 this session (fence/bush coherence
> VLM-checked in day/night/nightmare/dusk; see CHANGES_v16.md).

> **v15 note — the Ordering-Table raster + hardware defaults:** ALL quads
> (opaque + MASK + BLEND) now ride the engine's per-quad OT walk
> (Gfx_MeshDraw MAX-vertex-SZ Q8>>3 buckets, far->near, LIFO within a
> bucket; the engine's per-QUAD far cull `> field_1C`) — the PSX has NO
> depth buffer (DuckStation gpu_sw_rasterizer.inl), so per-pixel depth
> testing between quads is gone entirely; the only reported true
> z-fighting (float depth-comparison flips) is eliminated. DITHER is now
> ON by default (the DTE hardware behavior; D key / --no-dither /
> camdat env `dither` override). Wobble stays ON by default (P/--modern).
> Every mode below renders identically to v14 except where overlapping
> quads resolve by the engine's OT order instead of the z-buffer
> (verified: the day-reference diff is a thin distant edge object now
> correctly culled past the 30.4 m field_1C boundary).

> **v12 note — ALL weather conditions exposed + the transition state
> machine completed:** the W key now cycles the COMPLETE runtime weather
> domain (sharedFunc_800D0B18 args 0..8: none; snow wind 0-3; rain wind
> 0-3 — v11 reached only 3 of them), and `--weather-target N` boots the
> same transition recipe the game's own snow→rain street event uses
> (map0_s00_2.c:1679, arg 6). The 512-tick sine cross-fade now runs with
> the engine's FULL verbatim state machine: the g_SysWork.field_234A
> transition lock (switches REFUSED mid-fade, particle.c:3870), the
> 800DD592 snow-spawn-type switch (Unk1 particles spawn below the
> bank-count thresholds during ramps, particle.c:465-545), the
> field_2349 density selector, the tail zeroing (:583-586), and the live
> wind ramp for wind >= 2 (g_Particle_SpeedX/Z). All 21 env presets, 24
> authentic pairs, night/nightmare, lightning and lens-flare types remain
> fully selectable — every mode renders byte-identically to v11 (v12/v13;
> v14 changes ONLY the transparent-pass ordering — the fixed layering).


> **v14 note — the transparent-pass ordering + per-texel STP rule
> (VERBATIM):** the blend/MASK pass (the `_STP` fences and the
> billboard-leaf bushes) now replicates the engine ordering table PER QUAD:
> Gfx_MeshDraw inserts every quad at `addPrim(&tag[(MAX-vertex-SZ Q8 >>
> otShift) >> 2])` — bucket Q8>>3 at the room's `WorldGfx_Draw(1)` — and
> Gfx_BillboardDraw at the projected-CENTER bucket; the OT (2048 entries)
> is walked far bucket -> near, LIFO within a bucket (addPrim head
> insertion); snow/rain flakes ride the same buckets (zHalf = Q8>>3) and
> tie ABOVE quads (particles are added before WorldGfx_Draw,
> game_sys_states.c:172 vs :189). v13 sorted whole meshes by average
> vertex depth — the root cause of bushes over nearer fences and the
> multi-frame layer flipping. Per texel, ONLY a 0x0000 (alpha 0) texel is
> a hole; alpha-127 STP texels write OPAQUE (the room's STP quads are
> ST-clear — Gfx_MeshDraw's STP branch never calls setSemiTrans on the
> textured quad, and func_8005AC50's ST-bit path needs a field_B_0 model,
> which THRF9FD.IPD's 32 objects all lack) — DuckStation
> gpu_sw_rasterizer.inl:88. All 21 modes render with the fixed layering;
> see CHANGES_v14.md.

> **v11 note — the fog veil compositing (Gfx_MeshDraw, VERBATIM):** for EVERY
> textured prim (STP or not) in a fog-enabled env with fogColor != 0, the
> engine emits TWO quads at the same OT bucket (bodyprog_80056D8C.c:1005-1189
> enum-0; :694-883 enum-1/2):
> * NON-STP prims: `setSemiTrans(poly3, 1)` — the TEXTURED GT4 is
>   semi-transparent; addPrim order poly3-then-poly2 + OT head insertion
>   (LIFO) = the OPAQUE fog G4 (poly2, per-vertex `fogColor*f` via
>   `dpcs(DP=T, RGB=fogColor, FC=0)`) draws FIRST as the base, the textured
>   quad composites ON TOP (tpage ABR=1 additive):
>   `final pixel = fogColor*f + (texel * tintEff * (1-f)) >> 7`
> * STP prims: opaque textured GT4 + the semi-trans fog G4
>   (`setSemiTrans(poly2, 1)`) ON TOP — the SAME composite formula.
> v5-v10 gated the veil on the STP flag (a misreading of the OT order) which
> broke the normal fog (distant opaque geometry faded to black). v11 applies
> it to all prims — engine-exact, and byte-identical to the v3 ground-truth
> fog renders (mean RGB within ~1 unit).

Every value in this guide is transcribed DIRECTLY from the Silent Hill 1
decompilation (`shdecompilations/silent-hill-decomp`). Zero guessing, zero
VLM impressions: every claim carries a file/line or function citation.
Where the decomp itself annotates uncertainty (e.g. `field_21`/`field_25`
semantics), that uncertainty is stated verbatim.

Source files read in full for this guide:
- `src/bodyprog/sys/map_info.c`  (lines 1-486 — the whole preset table)
- `src/bodyprog/world/world_effects.c`  (lines 1-887 — the whole env engine)
- `src/bodyprog/gfx/bodyprog_80055028.c`  (fog ramp, 2D effects, env state)
- `include/game.h`  (s_MapEffectsInfo, s_StructUnk3, s_SysWork_2388, enums)
- `include/bodyprog/map/terrain.h`  (CHUNK_SIZE)
- 52 `Gfx_MapEnvSet` / `Gfx_MapEnvUpdate` call sites across `src/maps/**`

--------------------------------------------------------------------------------
## 1. THE DATA STRUCTURE (include/game.h)

```c
typedef struct s_MapEffectsInfo {           // 44 bytes
    union { u8 field_00[4]; } flags;         // [0]=e_SpecialEnvEventFlags
                                             // [1]=maxBrightness
                                             // [2]=e_UnkGfxEnum (light path)
                                             // [3]=0 (unused)
    s32 spotLightIntensity;                  // Q12 flashlight beam weight
    s32 worldLightIntensity;                 // Q12 ambient/world light
    s32 worldTintR, worldTintG, worldTintB;  // Q12 world tint
    u8  field_E;                             // fog mode: 0/1/2/3 (see below)
    s32 fogDistance;                         // Q12 metres
    u8  fogColor[4];                         // r,g,b,0
    u8  enableTintLightOverlap;
    u8  pointLightTint[4];
    u8  worldTint[4];
    u8  field_21[4];                         // particle base color (decomp's own comment)
    u8  field_25[4];                         // particle secondary color
} s_MapEffectsInfo;
```

Flag bits (include/game.h:291-299):
| bit | name | engine effect (citation) |
|----|------|--------------------------|
| 1<<0 | `SpecialEnvEventFlags_DarkEnvironment` ("Double check." — decomp's own note) | `Gfx_EffectsUpdate` 439-441: on a lightning flash, a DARK env swaps the whole live env to `MAP_EFFECTS_INFOS[8]` for one tick |
| 1<<1 | `SpecialEnvEventFlags_FlashlightAllowed` | v10 CORRECTION (decomp-verified across ALL use sites): this flag gates BGM layers (`Map_RoomBgmInit_*`), monster AI (stalker/nurse/romper/creeper/larval/...), `particle.c:4293`, `map5_s00` draw, and `Gfx_EffectsUpdate` 443-445 (on flash: `spotLightIntensity += Q12(0.3)`). It does NOT gate the player flashlight toggle — the toggle (inventory On/Off) is refused exactly when `isFlashlightUnavailable` (identical preset pair; item_screens_2.c:1267), and the flashlight is force-turned-off while a pair stays identical in gameplay state (`bodyprog_effects_8005E0DC.c:650`) |
| 1<<2 | `SpecialEnvEventFlags_EnableBrightness` | `Gfx_FogParametersSet` 344-351: brightnessIntensity := Q12(1.0) else Q12(0.0); feeds `WorldEnv_FogLightingParamsUpdate`'s screen-brightness poly |
| 1<<3 | `SpecialEnvEventFlags_UseLighter` | `Gfx_EffectsUpdate` 459-462: calls `func_8003E740()` (lighter flame overlay) every tick |
| 1<<4 | `SpecialEnvEventFlags_EnableLensflare` | `Gfx_FogParametersSet` 353-360: flashlightLensFlareIntensity := Q12(1.0) else 0; drives `func_8003F4DC`/`WorldGfx_2dEffectsDraw` 93-96 lens flare draw |

`field_E` fog modes — `Gfx_FogParametersSet` (world_effects.c:362-376):
| value | fogDistance slot gets | isFogEnabled (`WorldEnv_FogLightingParamsUpdate` 881: `field_E != 0`) |
|-------|-----------------------|-----------|
| 0 | the preset's fogDistance | **false — fog OFF** |
| 1 | the preset's fogDistance | true |
| 2 | Q12(0.0) (zero-distance total wash) | true |
| 3 | dynamic: rewritten every tick by `Gfx_EffectsUpdate` 405-410 to `lightViewZ + Q8_TO_Q12(viewMat.t[2])` | true |

`e_UnkGfxEnum` (flags[2]) — the per-vertex light dispatch used by
`Gfx_MeshDraw` (0x8005801C, bodyprog_80056D8C.c:677/692):
- 0 = no per-vertex world light (DPCS color pre-pass path)
- 1 = flashlight beam per-vertex light (`func_80057658`)
- 2 = directional N.L light (`func_80057A3C`) — modulated by lens-flare
  presets via `func_8003F4DC` (world_effects.c:468-546: Default = rot
  (0,-90,0) with lightWeight forced to 0; Preset1..4 = (-20,195,0),
  (-20,-75,0), (-20,15,0), (-20,105,0) Q12 angle tables)

`maxBrightness` (flags[1]): passed as the `flags.field_00[1]` argument of
`WorldEnv_WorldLightingParamSet` (world_effects.c:880) and blended between
presets by `func_8003F838` 670-691 with DarkEnvironment-aware weights.
During load-screen blends between two DARK presets it ramps; otherwise it
snaps with the plain weight.

Q12 = fixed 12-bit fraction: value = (s32)(x * 4096) — float truncation
semantics verified (Q12(1.1f)=4505, Q12(9.29987f)=38092, Q12(1.05f)=4300
via float rounding of the product).

--------------------------------------------------------------------------------
## 2. HOW A MODE IS APPLIED (world_effects.c, verbatim pipeline)

```
Gfx_MapEnvSet(idx0, idx1)                    // :277  the ONLY entry point
  -> Gfx_MapEnvUpdate(idx0, idx1, PrimitiveType_None, NULL, 0, 0)   // :311
       -> Gfx_MapEnvStepUpdate(&MAP_EFFECTS_INFOS[idx0],
                               &MAP_EFFECTS_INFOS[idx1], ...)       // :316
            - isFlashlightUnavailable = (preset0 == preset1)        // :319-326
              (POINTER equality: identical pairs make the flashlight
               unavailable — engine auto-off rule)
            - field_EC[0..1] = field_1C[0..1]   (previous live env)  // :333-334
            - Gfx_FogParametersSet(&field_84[0], preset0)           // :336
            - Gfx_FogParametersSet(&field_84[1], preset1)           // :337
                 (copies the preset; sets brightness/lensflare Q12
                  flags; field_E fog-distance switch — see section 1)
  -> Gfx_EffectsUpdate()                                          // :280/:379
       - flashlightIntensity += / -= dt*4, clamped [0,4096]        // :393-402
       - field_E==3 dynamic fog tick (light view-space z)          // :405-410
       - PrimitiveType_None: field_1C = field_84 (instant swap)    // :412-416
         else: load-screen blend into field_1C via func_8003F6F0
         progress alpha + func_8003F838                            // :417-428
       - field_154 = blend(field_1C[0], field_1C[1],
                           flashlightIntensity)                    // :430
         (the LIVE env = slot0/slot1 cross-fade driven by the
          flashlight fade — func_8003F838, section 5)
       - flashEffect one-tick lightning (section 7)                // :434-447
       - field_10 = func_8003FEC0 (fog-off fallback distance)      // :449
       - WorldEnv_FogLightingParamsUpdate(&field_154)              // :450/:871
            * brightness = clamp(brightnessIntensity *
                (config.brightness*8+4), 0, Q8(1.0))               // :877-878
            * WorldEnv_WorldLightingParamSet(enum, wLI, maxB,
                tintR/G/B, brightness)                             // :880
            * WorldEnv_FogParamsSet(field_E != 0, fogColor r/g/b)  // :881
            * WorldEnv_FogDistanceSet(fd, fd + Q12(1.0))           // :883-885
            * WorldEnv_WorldLightTintSet(overlap, pointLightTint,
                worldTint)                                         // :886
       - light pose: func_8003F4DC lens flare + Gfx_FlashlightPositionUpdate  // :452-456
       - func_80055814(field_154.fogDistance)                      // :457
            fog.intensity = Q12(1.0) - rampLookup(fogDistance)
       - UseLighter -> func_8003E740() flame overlay               // :459-462
```

Slot semantics: slot 0 (`field_84[0]`) is the base env, slot 1
(`field_84[1]`) is the flashlight-on env; `field_154` cross-fades them with
the flashlight fade weight. Pairs like {6,3} are therefore "night street
(fog 14 m) that transitions to flashlight (fog off) as the beam fades in".

--------------------------------------------------------------------------------
## 3. THE 21 PRESETS — MAP_EFFECTS_INFOS (map_info.c:5-342, VERBATIM)

Legend: spot/wLI/tint are Q12 (÷4096 for the float). "fog" shows
field_E semantics + fogDistance. maxB = flags[1] (maxBrightness).
enum = flags[2] light path. f21/f25 = particle colors (decomp's own field
names; consumed by `func_8003EDB8` world_effects.c:288-292 which selects
`field_1C[isFlashlightOn].field_21/25` by flashlight BOOLEAN for the
weather particle banks).

| # | flags (bits) | maxB | enum | spot | wLI | tint R/G/B | fog E | fogDist | fogColor | overlap | f21 | f25 | source line |
|---|--------------|------|------|------|-----|------------|-------|---------|----------|---------|-----|-----|--------------|
| 0 | none | 0xFF | 0 | 0 | 4710 (1.15) | 4096/4096/4096 (1.0) | 0 OFF | 409600 (100 m) | 60,60,68 | no | 64,64,64 | 12,12,28 | 6 |
| 1 | none | 0xFF | 0 | 0 | 4505 (1.1) | 3891/4096/4423 (.95/1/1.08) | 1 ON | 55296 (13.5 m) | 108,100,116 | no | 48,48,48 | 14,14,30 | 22 |
| 2 | none | 0xFF | 2 | 2457 (0.6) | 2457 (0.6) | 3686/4096/4300 (.9/1/1.05) | 1 ON | 57344 (14 m) | 100,92,108 | no | 48,48,48 | 13,13,29 | 38 |
| 3 | FL+BRIGHT+LF | 0xFF | 1 | 5324 (1.3) | 0 | 3891/4096/4423 | 0 OFF | 163840 (40 m) | 0,0,0 | no | 48,48,48 | 12,12,12 | 54 |
| 4 | FL+BRIGHT+LF | 0xFF | 1 | 2867 (0.7) | 0 | 3686/4096/4300 | 0 OFF | 163840 (40 m) | 0,0,0 | no | 48,48,48 | 12,12,12 | 70 |
| 5 | FL+BRIGHT+LF | 0xFF | 1 | 5324 (1.3) | 409 (0.1) | 3891/4096/4423 | 3 DYN | 55296 (13.5 m base) | 68,60,76 | YES | 32,32,40 | 12,12,28 | 86 |
| 6 | DARK+FL+BRIGHT | 0xFF | 0 | 0 | 1802 (0.44) | 1638/2867/4096 (.4/.7/1) | 1 ON | 57344 (14 m) | 0,0,0 | no | 16,16,24 | 8,8,20 | 102 |
| 7 | DARK+FL+BRIGHT | 0xFF | 0 | 0 | 1802 (0.44) | 1638/2867/4096 | 1 ON | 38092 (9.29987 m) | 0,0,0 | no | 16,16,24 | 8,8,20 | 118 |
| 8 | FL+BRIGHT | 0x50 | 1 | 1433 (0.35) | 1638 (0.4) | 2867/3276/4096 (.7/.8/1) | 1 ON | 163840 (40 m) | 0,0,0 | no | 64,64,64 | 12,12,12 | 134 |
| 9 | FL+BRIGHT | 0xFF | 1 | 7372 (1.8) | 614 (0.15) | 4096/2867/2457 (1/.7/.6) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 64,32,16 | 24,12,12 | 150 |
| 10 | FL+BRIGHT+LIGHTER | 0x92 | 1 | 2048 (0.5) | 0 | 4096/3276/2457 (1/.8/.6) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 32,24,16 | 18,8,8 | 166 |
| 11 | FL+BRIGHT | 0xFF | 1 | 7372 (1.8) | 614 (0.15) | 5324/1638/819 (1.3/.4/.2) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 64,32,16 | 24,12,12 | 182 |
| 12 | FL+BRIGHT+LF | 0xFF | 1 | 5324 (1.3) | 409 (0.1) | 3891/4096/4423 | 0 OFF | 163840 (40 m) | 0,0,0 | no | 48,48,48 | 12,12,12 | 198 |
| 13 | none | 0xFF | 0 | 0 | 3194 (0.78) | 3031/3481/4096 (.74/.85/1) | 1 ON | 55296 (13.5 m) | 92,84,100 | no | 16,16,24 | 8,8,20 | 214 |
| 14 | FL+BRIGHT+LF | 0x38 | 1 | 2867 (0.7) | 204 (0.05) | 4505/2457/2662 (1.1/.6/.65) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 48,48,48 | 12,12,12 | 230 |
| 15 | FL+BRIGHT | 0xC4 | 1 | 4915 (1.2) | 819 (0.2) | 2867/1843/1843 (.7/.45/.45) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 64,32,16 | 24,12,12 | 246 |
| 16 | FL+BRIGHT | 0xFF | 1 | 5734 (1.4) | 204 (0.05) | 3481/2457/2457 (.85/.6/.6) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 64,32,16 | 24,12,12 | 262 |
| 17 | none | 0xFF | 0 | 0 | 4096 (1.0) | 3891/3686/3686 (.95/.9/.9) | 1 ON | 26624 (6.5 m) | 108,100,100 | no | 48,48,48 | 14,14,30 | 278 |
| 18 | FL+BRIGHT+LF | 0xFF | 1 | 10240 (2.5) | 614 (0.15) | 4096/2867/2867 (1/.7/.7) | 0 OFF | 163840 (40 m) | 0,0,0 | no | 64,32,16 | 24,12,12 | 294 |
| 19 | DARK+FL+BRIGHT | 0xFF | 0 | 0 | 2252 (0.55) | 2048/3604/5120 (.5/.88/1.25) | 1 ON | 61440 (15 m) | 0,0,0 | no | 16,16,24 | 8,8,20 | 310 |
| 20 | FL+BRIGHT+LF | 0xFF | 1 | 3276 (0.8) | 819 (0.2) | 3891/4096/4423 | 0 OFF | 163840 (40 m) | 0,0,0 | no | 48,48,48 | 12,12,12 | 326 |

Additional per-preset fields that are non-zero ONLY in preset 5
(map_info.c:96-98): `enableTintLightOverlap = true`,
`pointLightTint = (24,16,32)`, `worldTint = (85,75,75)`. Every other
preset has overlap=false and all-zero pointLightTint/worldTint.

### What each preset DOES (facts only)

**[0] fog-off ambient room.** No special flags; enum-0 (no per-vertex
light); world light 1.15 (the BRIGHTEST ambient in the table); fog
DISABLED (field_E=0) with the 100 m distance value as the fallback;
fogColor (60,60,68) — a dark slate that only shows if the veil is drawn.
Particle colors f21 (64,64,64) / f25 (12,12,28) — grey flakes with a
dark-blue secondary.

**[1] THR day street (the outdoor street default).** No flags; enum-0;
ambient 1.1; fog ON at 13.5 m with the iconic sepia-grey fogColor
(108,100,116); tint (.95, 1.0, 1.08) — slightly cool in blue, slightly
warm... no: R .95 (slightly darkened red), B 1.08 (slightly boosted
blue) — a cool morning cast. This is D_800A9F80, the WorldEnv default
pair {1,1} (world_effects.c:22 + WorldEnv_MapPresetSet).

**[2] interior day with the ENUM-2 DIRECTIONAL light.** The ONLY preset
using enum-2: the N.L directional path (func_80057A3C) with spot 0.6
acting as the light weight, wLI 0.6. Fog ON at 14 m, color
(100,92,108). Lens-flare presets
(func_8003F4DC) modulate this light: Default drops the weight to 0;
Preset1..4 aim it at (-20,195/…/105) degrees. (The PoC exposes this as
`--lensflare N`.)

**[3] night street + FLASHLIGHT (slot-1 of the night pair).**
FlashlightAllowed|EnableBrightness|EnableLensflare; enum-1 per-vertex
beam weight 1.3; ambient 0; fog OFF (field_E=0, 40 m fallback); black
fog. With the flashlight fade at full, the world is lit ONLY by the beam
(functions 80057658/80057A3C interplay via func_8003F838's enum-1<->2
ramp). Paired as {6,3} (D_800A9F88; map0_s01_events.c:920 — the street
where the flashlight is picked up).

**[4] nightmare flashlight (slot-1 of the nightmare pair).** Same flag
set as [3] but beam 0.7 and the (.9,1,1.05) tint; fog OFF (40 m).
Paired as {7,4} (D_800A9F8C; map0_s02_events.c:102; also map4_s01_2.c:834,
map1_s06.c:203/507, map2_s04.c:162, map3_s01.c:380, map3_s05.c:573,
map3_s02_2.c:91).

**[5] interior flashlight with DYNAMIC fog — the field_E=3 preset.**
While the flashlight is fading, `Gfx_EffectsUpdate` rewrites the active
slot's fogDistance EVERY tick to the flashlight's view-space depth
(world_effects.c:405-410: `sp48.vz + Q8_TO_Q12(viewMat.t[2])`), so the
fog wall tracks the beam. It is the ONLY preset with
enableTintLightOverlap=true, pointLightTint (24,16,32) and worldTint
(85,75,75) — the overlap overlay drawn by `WorldGfx_2dEffectsDraw`
(bodyprog_80055028.c:88-91 via func_80041074). Fog base 13.5 m, color
(68,60,76). Paired as {6,5} (D_800A9F94) and {5,5} (D_800A9FA4).

**[6] night street (slot-0 of the night pair).** DarkEnvironment +
FlashlightAllowed + EnableBrightness; enum-0; NO beam; ambient 0.44;
tint (.4,.7,1.0) — strongly blue; fog ON at 14 m, BLACK. Particle
colors (16,16,24)/(8,8,20) — dim blue-ish night flakes. Paired as {6,3}
and alone {6,6} (D_800A9F9C; map2_s00.c:1352 blend).

**[7] night THICK.** Identical to [6] except fogDistance 38092 =
9.29987 m — the thickest outdoor black fog. The decomp's odd float
9.29987 encodes the exact retail value (Q12 38092). Paired as {7,4}.

**[8] LIGHTNING flash environment.** FL+BRIGHT, maxBrightness 0x50 (a
LOW cap — the flash does not blow out), enum-1 beam 0.35, ambient 0.4,
tint (.7,.8,1), fog ON at 40 m black. This preset is never a map pair:
the engine injects it for exactly ONE tick when `flashEffect` fires on a
DarkEnvironment env (world_effects.c:434-447). Trigger:
`func_8003EDA8` sets `flashEffect = true` (:283-286).

**[9] nowheres rust.** FL+BRIGHT, enum-1 beam 1.8, ambient 0.15, tint
(1.0, 0.7, 0.6) — the rust/flesh cast of Nowhere (map7_s03). Fog OFF
(40 m). Paired {9,9} (D_800A9F98; map7_s03_3.c:3109, 3184, 3394).

**[10] lighter-equipped environment.** The ONLY UseLighter preset:
`func_8003E740()` runs every tick to draw the lighter's flame
(GameFs_FlameGfxLoad TIM). maxBrightness 0x92, beam 0.5, ambient 0,
tint (1.0, 0.8, 0.6), fog OFF (40 m). Paired {6,10} (D_800A9F90) and
blend target {10,10} (map0_s00_2.c:1022 with Q12(0.5) progress).

**[11] red darkness.** FL+BRIGHT, beam 1.8, ambient 0.15, the EXTREME
red tint (1.3, 0.4, 0.2), fog OFF (40 m). Blend target {11,11}
(map4_s01_2.c:744, PrimitiveType_S32 progress Q12(100.0)).

**[12] interior flashlight.** FL+BRIGHT+LF, beam 1.3, ambient 0.1,
tint (.95,1,1.08), fog OFF (40 m). Slot-1 of pair {6,12}
(map4_s05.c:511).

**[13] dusk street.** No flags, enum-0, ambient 0.78, tint
(.74,.85,1.0), fog ON at 13.5 m with the blue-grey (92,84,100). Pair
{13,13} (map0_s02_events.c:173; map2_s00.c:2337; map3_s01.c:391).

**[14] rust/brown flashlight.** FL+BRIGHT+LF with the LOWEST
maxBrightness cap 0x38; beam 0.7, ambient 0.05, tint (1.1, 0.6, 0.65);
fog OFF (40 m). Pair {14,14} (map4_s01_2.c:1077).

**[15] dark red flashlight.** FL+BRIGHT with the HIGHEST maxBrightness
cap 0xC4; beam 1.2, ambient 0.2, tint (.7,.45,.45); fog OFF (40 m).
Pair {15,15} (map4_s04_2.c:262).

**[16] dim flashlight.** FL+BRIGHT, beam 1.4, ambient 0.05, tint
(.85,.6,.6), fog OFF (40 m). Pair {16,16} (map3_s02_2.c:267;
map6_s01_2.c:190 — BOTH call sites set the identical pair, so the
flashlight is engine-unavailable there).

**[17] THICK fog room.** No flags, enum-0, ambient 1.0 (full),
tint (.95,.9,.9), fog ON at 6.5 m — the THICKEST fog in the table —
with the warm grey (108,100,100). Blend target {17,17}
(map7_s03_3.c:3083, 3185, 3395).

**[18] bright spotlight.** FL+BRIGHT+LF, THE strongest beam 2.5,
ambient 0.15, tint (1,.7,.7), fog OFF (40 m). Pair {18,18}
(map7_s03_3.c:953).

**[19] blue night.** DARK+FL+BRIGHT, enum-0, ambient 0.55, THE most
saturated blue tint (.5,.88,1.25 — B above 1.0!), fog ON at 15 m black.
Slot-0 of pair {19,4} (map1_s06.c:68).

**[20] map1_s06 flashlight.** FL+BRIGHT+LF, beam 0.8, ambient 0.2,
tint (.95,1,1.08), fog OFF (40 m). Slot-1 of pair {6,20}
(map4_s03.c:1830) and of {19,4}.

--------------------------------------------------------------------------------
## 4. THE 24 AUTHENTIC PAIRS (every real call site)

Slot 0 = base env, slot 1 = flashlight-on env (section 2). kind:
0 = world_effects.c map-default table D_800A9F80..A4 (lines 22-31);
1 = direct `Gfx_MapEnvSet` event call;
2 = `Gfx_MapEnvUpdate(..., PrimitiveType_S32, ...)` LOAD-SCREEN BLEND
target — the engine ramps into it via `func_8003F6F0` progress over the
room-load primitive, then `primitiveType` falls back to None at weight
Q12(1.0) (world_effects.c:412-428).

| pair | name | citation | kind |
|------|------|----------|------|
| {1,1} | day street | D_800A9F80 (WorldEnv default; map2_s01_2.c:452, map2_s00.c:2370) | 0 |
| {2,2} | interior day (enum-2) | D_800A9F84; map3_s01.c:401/452/461, map1_s06.c:520, map3_s02_2.c:308 | 0 |
| {6,3} | night street | D_800A9F88; map0_s01_events.c:920, map2_s00.c:1388/2317/2329/2375, map4_s03.c:165 | 0 |
| {7,4} | nightmare street | D_800A9F8C; map0_s02_events.c:102 + 8 more sites | 0 |
| {6,10} | night + lighter | D_800A9F90 | 0 |
| {6,5} | night + dynamic fog | D_800A9F94 (field_E=3 slot) | 0 |
| {9,9} | nowheres rust | D_800A9F98; map7_s03_3.c:3109/3184/3394 | 0 |
| {6,6} | pure night | D_800A9F9C; map2_s00.c:1352, map0_s00_2.c:1669/1791 | 0 |
| {3,3} | flashlight pair | D_800A9FA0 | 0 |
| {5,5} | dynamic-fog pair | D_800A9FA4 | 0 |
| {18,18} | bright spotlight pair | map7_s03_3.c:953 | 1 |
| {4,4} | nightmare flashlight | map6_s02_2.c:1061, map3_s01.c:412 | 1 |
| {16,16} | dim flashlight pair | map3_s02_2.c:267, map6_s01_2.c:190 | 1 |
| {13,13} | dusk street | map0_s02_events.c:173, map2_s00.c:2337, map3_s01.c:391 | 1 |
| {6,12} | night + interior flashlight | map4_s05.c:511 | 1 |
| {15,15} | dark red flashlight | map4_s04_2.c:262 | 1 |
| {19,4} | blue night + nightmare flashlight | map1_s06.c:68 | 1 |
| {6,20} | night + s06 flashlight | map4_s03.c:1830 | 1 |
| {14,14} | rust/brown flashlight | map4_s01_2.c:1077 | 1 |
| {11,11} | red darkness | map4_s01_2.c:744 (blend, Q12(100) progress) | 2 |
| {17,17} | THICK fog room | map7_s03_3.c:3083/3185/3395 (blend, Q12(100)) | 2 |
| {10,10} | lighter-equipped | map0_s00_2.c:1022 (blend, Q12(0.5)) | 2 |
| {7,9} | thick -> rust mix | map3_s05.c:414 (blend, 0x64000 = Q12(100)) | 2 |
| {7,7} | night THICK pair | map3_s02_2.c:309 (blend, Q12(100)) | 2 |

Map-default dispatch (WorldEnv_MapPresetSet, world_effects.c:197-243):
each map header's `field_16` selects one of the ten D_800A9F80..A4 pairs —
1 -> {2,2} interior / {1,1} street (by interior flag + active chunks),
2 -> {7,4} / {6,3}, 3 -> {9,9}, default {1,1}.

--------------------------------------------------------------------------------
## 5. THE BLEND MACHINERY (func_8003F838, world_effects.c:636-794)

- weight0 = clamp(w*2), weight1 = clamp((w-0.5)*2)  (:643-647)
- flags[0] copied from slot0 below w=0.5 else slot1 (:650-657)
- f21/f25 particle colors: LoadAverageCol linear blend (:799-806)
- lensflareIntensity: if slot0's is 0, blend 0->slot1 with weight1 (the
  flare only fades in during the second half); else weight0 (:661-668)
- maxBrightness flags[1]: DarkEnvironment-aware — both dark: plain
  weight; only slot0 dark: weight1; only slot1 dark: weight0 (:670-691)
- field_E selection (:694-724): e0==0 && e1!=0 -> e1; e0!=0 && e1==0 ->
  keep e0 until weight1 >= Q12(1.0); both non-zero -> e1. The fog
  distance then blends via func_8003FD38 (:811-827):
  target.fogDistance = wavg(e0.fogDistance, e1.fogDistance, weightA)
  effectsInfo.fogDistance = wavg(..., weightB) — the weight slots
  depend on the field_E case (see the decomp call args :699-723)
- worldTint R/G/B and wLI: plain weighted average (:726-728, :824)
- fogColor: LoadAverageCol linear (:826)
- enum-1 <-> enum-2 transitions get a PIECEWISE spot ramp (:730-763):
  1->2: below w=5/6, spot scales 1.2*w toward 0; above, ramps 0->slot1's
  spot with (w-5/6)*6. 2->1: below w=1/6 ramps slot0's spot to 0, above
  scales (w-1/6)*1.2 up to slot1's spot. (This is why flashlight fades
  feel "alive": the beam dies before the directional light takes over.)
- Math_WeightedAverageGet = a*(1-w) + b*w in 64-bit Q12 (:628-631)

--------------------------------------------------------------------------------
## 6. THE FOG RENDERING PIPELINE (bodyprog_80055028.c)

- `WorldEnv_FogDistanceSet(near, far=near+Q12(1))` (:332-389): nearDist
  Q12->Q8; depthShift = 0x20 - Lzc(nearDist-1); builds the 128-entry
  `fogRamp` LUT by stepping `(0x10 << (depthShift+1)) / nearDist` over
  [0, Q12(1.0)) and piecewise-linearly interpolating the FIXED 17-entry
  curve D_800AE1C0 = {0, 0, 0x26, 0x4C, 0x5E, 0x70, 0x85, 0x99, 0xB0,
  0xBD, 0xD1, 0xDC, 0xE6, 0xF0, 0xF5, 0xFA, 0xFF} (:21-39); remaining
  entries = 0xFF.
- `func_80055814(fogDistance)` (:327-330): fog.intensity = Q12(1.0) -
  rampLookup(fogDistance) — the fullscreen veil strength.
- `WorldEnv_FogParamsSet(isFogEnabled, r, g, b)` — the veil color and
  the master fog switch (field_E != 0, section 1).
- `WorldGfx_2dEffectsDraw` (:76-124+): draws, in OT order: the
  tint-light-overlap overlay (only when enableTintLightOverlap),
  the lens flare (enum-1 + lensFlareIntensity != 0), the
  screenBrightness semi-transparent POLY_G4 quad covering
  (-180,-120)..(180,120) (screen space), and the fog.color fullscreen
  quad at the OT end.
- `func_8003FEC0` (:848-869): when fog is DISABLED the "distance" used
  by the mesh pipeline is: fog enabled -> effectsInfo.fogDistance;
  enum-1 -> vwOresenHokan over Y_ARRAY {1.75, 6.0, 9.5, 12.5, 15.0} m
  indexed by spotLightIntensity over [0, Q12(2.0)]; otherwise
  Q12(20.0). (The flashlight beam ITSELF thins the "air" with
  distance — the brighter the beam, the deeper the visible range,
  1.75 m .. 15 m.)
- `WorldEnv_Init` (:47-74): defaults — enum-0, wLI Q12(1.0),
  worldTintColor 128/128/128, fog OFF, fog.color 255/255/255, then
  FogDistanceSet(Q12(32), Q12(34)).

--------------------------------------------------------------------------------
## 7. SPECIAL ONE-TICK / OVERLAY BEHAVIORS

- **Lightning** (`func_8003EDA8` + `Gfx_EffectsUpdate` :434-447): sets
  flashEffect; on the next tick, if the LIVE env has DarkEnvironment,
  the ENTIRE live env is overwritten by Gfx_FogParametersSet with
  MAP_EFFECTS_INFOS[8] (beam 0.35, maxB 0x50, fog 40 m, wLI 0.4) for
  exactly one tick; else if FlashlightAllowed, spot += Q12(0.3) for one
  tick. The engine's trigger is the overlay-script lightning-bolt actor
  (func_80063A50); the PoC binds it to the L key / --lightning.
- **Lighter** (UseLighter, preset 10): func_8003E740 every tick — the
  hand lighter's flame sprite (GameFs_FlameGfxLoad TIM, tpage 12,
  u32/v0, clut 800,64).
- **Lens flare** (EnableLensflare + enum-1): func_8003F4DC's five
  presets (Default: weight forced 0, rot (0,-90,0); Custom: the bone's
  rotation; Preset1..4: (-20, 195/-75/15/105, 0) degrees) and
  func_8008D470's flare draw (WorldGfx_2dEffectsDraw :93-96).
- **Flashlight pose**: Game_FlashlightAttributesFix anchors the beam at
  the Torso bone with offset (-0.08, -0.28, 0.12) and -15 deg tilt;
  Game_SpotlightLoadScreenAttribsFix anchors the load-screen spotlight
  at the Root bone, offset (0, -0.2, -2.0), +10 deg. In this PoC the
  camera eye (Harry/HERO) is the light origin, per the fixed directive.
- **isFlashlightUnavailable** (Gfx_MapEnvStepUpdate :319-326): identical
  pairs (pointer-equal presets) make the game's flashlight toggle
  REFUSE (the inventory On/Off command gate, item_screens_2.c:1267) AND
  the engine force-turns the flashlight off while the pair stays
  identical in gameplay state (bodyprog_effects_8005E0DC.c:650) — the
  PoC's v10 F key implements exactly this rule (mixed pair: toggle
  works; identical pair: refused up front with the engine's reason).

--------------------------------------------------------------------------------
## 8. v9 CORRECTION NOTE (LOUD — what changed vs the v8 PoC and WHY)

The v8 PoC's embedded table had two transcription errors, both fixed in
v9 with byte-level proofs:

1. **CHUNK_SIZE mis-read.** v8 defined fogDistance 32768 = Q12(8.0) for
   the twelve flashlight presets whose decomp value is
   `Q12(CHUNK_SIZE)`. The decomp's `include/bodyprog/map/terrain.h:7`
   defines `#define CHUNK_SIZE 40.0f` (the terrain streaming chunk size
   — cross-confirmed by 15+ Q8(CHUNK_SIZE) grid computations in
   `src/bodyprog/world/world_map.c`). Correct value: 163840 = 40 m.
   Affected presets: 3, 4, 8, 9, 10, 11, 12, 14, 15, 16, 18, 20.
   Visual effect of the fix: those presets' fog was already OFF
   (field_E=0), so steady-state renders are unchanged; the FLASHLIGHT
   FADE now sweeps fog 14 m -> 40 m (engine-exact) instead of v8's
   14 m -> 8 m, and preset 8's lightning fog is 40 m. The night pair's
   env-dump blend audit (181 ticks) now matches the decomp reference
   with 0 mismatches.

2. **Entries 16-20 were ROTATED one slot.** v8's [16..20] read THICK,
   spotlight, blue-night, s06, dim; the decomp's raw table order
   (map_info.c lines 262-341) is [16]=dim(1.4) [17]=THICK(6.5 m)
   [18]=spotlight(2.5) [19]=blue-night(15 m) [20]=s06(0.8). Proven by
   the call-site literals: {16,16}@map3_s02_2.c:267 + map6_s01_2.c:190,
   {18,18}@map7_s03_3.c:953, {17,17} blends@map7_s03_3.c:3083/3185/3395,
   {19,4}@map1_s06.c:68, {6,20}@map4_s03.c:1830.

Regression proof (pristine v8 binary A/B, 25 render cases): 16/25
byte-identical — including day, night (with AND without flashlight),
nightmare (with AND without flashlight), dynamic fog {6,5}, pure night,
rain, modern, and the camera turn — and 9/25 differ EXACTLY in the
decomp-predicted way (the rotated indices' content swaps + preset 8's
fog distance). The v8 look everybody approved is preserved byte-for-byte
everywhere the table content was already correct; the changed renders
ARE the corrections. Engine math, blend state machines, snow, rain,
camera, GTE jitter: untouched.

--------------------------------------------------------------------------------
## 9. SELECTING MODES IN THE PoC (v10)

Interactive window (Win32 GDI / SDL2 / X11 backends):
- **Tab** — open/close the on-screen WORLD MODE BROWSER: 21 preset rows
  + 24 authentic-pair rows, Up/Down to move, **Enter** to apply,
  **0-9** to jump+apply preset rows, Esc closes.
- **[ / ]** — cycle all 21 presets (Gfx_MapEnvSet(k,k)).
- **, / .** — cycle the 24 authentic pairs.
- **H** — toggle the status HUD (live pair, fog, wLI, spot, fade).
- v8 keys unchanged: N (day/night/nightmare cycle), F flashlight
  (v10: the ENGINE inventory rule — works on every mixed pair, refused
  on identical pairs exactly like item_screens_2.c:1267), M fog debug
  (--nofog look), B snow, P PSX wobble, W weather (snow->rain->none),
  L lightning one-shot, S screenshot, R restart, SPACE pause, +/-
  speed, L/R scrub, ESC quit.

CLI: `--preset N` (boot at preset N), `--envpair A,B` (any pair),
`--worldstage N`, `--nightpair A,B`, `--menu` (browser open at boot),
`--no-hud`, `--listmodes` (prints this whole inventory),
`--lensflare N`, `--lightning`, `--weather N`.

Every interactive/CLI mode change routes through the same verbatim
`sh_env_set_pair` == `Gfx_MapEnvSet` port — no engine math was added or
altered to implement the selection UI.

v10 stability: modes can be cycled INDEFINITELY — the 30 Hz env clock
survives every camtrack wrap (backward-time resync, the same guard the
snow system has), and the flashlight fade always ramps (no frozen
state). Stress-proven: 240+ mode changes across 4 track wraps + 20
weather transitions + browser/HUD cycling in one session, 7758 env
ticks, both flashlight ramps completing to 4096, zero stalls.

## 10. v13 — THE CAMDAT v2 ENV OBJECT (camtrack_v2 editor files)

The camtrack_v2 editor (the World & Weather panel) saves a per-model `env`
object in camdat.json alongside the legacy derived booleans:

    models[].env {
      pair:[A,B] 0..20, weatherTarget 0..8, bootWeather -1..6,
      lensFlare 0..5, flashlightOn/psxWobble/dither/particles/engine
      (strict booleans, all optional)
    }

fog_PoC v13 parses it with the editor's sanitizeEnv semantics VERBATIM and
applies it at boot with the priority **CLI flags > camdat env > camdat
legacy flags > engine defaults** (the editor's own documented precedence:
URL/CLI params override the saved selection):

- `pair` boots `Gfx_MapEnvSet(A,B)` (supersedes the nighton-derived pair;
  identical pairs still engine-disable the flashlight).
- `flashlightOn` is the boot flashlight (the auto-off rule still applies).
- `bootWeather` is the INSTANT map-load recipe — applied unconditionally
  INCLUDING recipe 2 ("snow + wind flag"), exactly like the editor's
  setBootWeather (the `--weather` CLI keeps its v8 `!= 2` quirk).
- `weatherTarget` boots the RUNTIME transition (D0B18 — the 512-tick sine
  cross-fade; lock armed at map load, so the boot call is accepted).
- `lensFlare` selects the enum-2 light source.
- `psxWobble:false` = the `--modern` look; `dither` = the ordered dither;
  `particles:false` = `--nosnow`; `engine:false` = the `--nofog` look.

Legacy camdat.json WITHOUT `env` parses byte-exactly as v12 (proven by
md5-identical deterministic renders on the shipped camdat and on all 21
`--envpair k,k` modes).

The v2 editor's temporary "Effects Off (env 0)" preview toggle (key 0) is
SESSION-ONLY and NEVER serialized: it drives the JS preview to env mode 0
(MAP_EFFECTS_INFOS[0] — the fog-off ambient room: fog OFF, flat ambient
tintEff 147, no flashlight/brightness/lensflare) + weather none, while the
session's real selection is shadowed and restored. The C++ equivalent of
that view: `./fog_poc --envpair 0,0 --weather 0`.
