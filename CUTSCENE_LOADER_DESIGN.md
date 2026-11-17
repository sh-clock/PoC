# CUTSCENE LOADER PoC — Architecture & Format Identification

Status: DESIGN DOCUMENT ONLY (architecture + binary-format identification phase;
no implementation yet, per the directive). Every structure, constant and formula
below is sourced verbatim from the silent-hill-decomp sources and validated
against the actual ripped files from `/sh1/sh1rip` on the CDN.

Ground-truth sources:
- `silent-hill-decomp/src/bodyprog/dms.c` + `include/bodyprog/dms.h` (the DMS cutscene system)
- `silent-hill-decomp/src/bodyprog/world/bodyprog_anim_800445A4.c` (the ANM skeletal system)
- `silent-hill-decomp/include/bodyprog/formats/anm.h` + `docs/file_formats/anm.ksy`
- `silent-hill-decomp/src/bodyprog/sys/chara_data_info.c` (`CHARA_FILE_INFOS` — the file inventory)
- `silent-hill-decomp/src/bodyprog/player_control.c` (`HARRY_BASE_ANIM_INFOS` — anim status -> keyframe ranges)
- `silent-hill-decomp/src/maps/map0_s00/map0_s00_2.c:180-330` (a complete real cutscene driver)
- `silent-hill-decomp/src/bodyprog/game_boot/fs_chara_anim.c` (ANM streaming/buffering)
- Rip files validated: `ANIM/HB_BASE.ANM` (89088 B, full), `ANIM/OPEN.DMS` (CDN copy truncated
  at 2048 B — header + entries + first keyframes present; full parse below)

---

## 1. What a Silent Hill 1 cutscene IS (engine architecture)

A cutscene is NOT a single data file. It is a **map event state machine** (compiled
C code in the SLUS, per-map `sysStateSteps` switches) that orchestrates, per 30 Hz tick:

1. **DMS data** (`ANIM/*.DMS`) — the camera track + character BLOCKING (world positions
   and rotations of each actor), keyframed on a 30 FPS playback-frame index.
2. **ANM data** (`ANIM/*.ANM`) — the SKELETAL animation of each actor (the walk cycle,
   head turns etc.), selected by anim STATUS numbers via `Event_CharaAnimCmdExecute
   (CharaAnimCmd_SetState, &chara, N, false)`.
3. **Character models + textures** — `CHARA/*.ILM` models + `CHARA/*.TIM` textures in
   the rip. **This PoC replaces them with GLTF exports** (the user directive: models
   are GLTF; the .ANM/.DMS binaries are decoded by the loader).
4. **Map messages** (`MAP_MESSAGES` — subtitle text with timing codes), screen fades
   (`Event_ScreenFadeCmd`), SFX/BGM triggers, and control freezes
   (`Player_ControlFreeze`).
5. **A cutscene timer driven at variable rates**: `g_Cutscene_Timer += g_DeltaTime *
   Q12(rate)` — the opening cutscene uses rates 10x, 8x and 4x on different steps
   (map0_s00_2.c:216-247) — i.e. the DMS playback frame advances at rate*30 fps of
   wall time. THIS is the "cutscene speed" knob and it is per-event-step data, not
   per-file.

Real driver example (map0_s00, the opening cutscene `MapEvent` at 0x800D9C0C):

```c
case EventState_Initialize:
    Player_ControlFreeze();
    Fs_QueueStartRead(FILE_ANIM_OPEN_DMS, FS_BUFFER_16);   // async load OPEN.DMS
    ...
case EventState_2:
    Dms_HeaderFixOffsets((s_DmsHeader*)FS_BUFFER_16);       // fixup relative ptrs
    Chara_Load(0, Chara_Cheryl, ...);                       // load the actor
    g_Cutscene_Timer = Q12(0.0f);
case EventState_3:
    Event_CharaAnimCmdExecute(CharaAnimCmd_SetState, &playerChara, 53, false); // anim status 53
case EventState_4:
    g_Cutscene_Timer = MIN(g_Cutscene_Timer + Q12_MULT_PRECISE(g_DeltaTime, Q12(10.0f)), Q12(22.0f));
    ...
// EVERY TICK while the timer runs:
Dms_CharacterTransformGet(&playerChara.position, &playerChara.rotation, "HERO",
                          g_Cutscene_Timer, (s_DmsHeader*)FS_BUFFER_16);
vcChangeProjectionValue(Dms_CameraTargetsGet(&g_CameraPositionTarget,
                        &g_CameraLookAtTarget, NULL, g_Cutscene_Timer, hdr));
vcUserCamTarget(&g_CameraPositionTarget, NULL, true);       // warp=true camera target
vcUserWatchTarget(&g_CameraLookAtTarget, NULL, true);       // warp=true look target
```

---

## 2. Required files from the rip (`sh1rip/` folder structure)

| Rip path | Purpose | Notes |
|---|---|---|
| `ANIM/*.DMS` | Cutscene camera + actor blocking | 16 DMS files (AMUSE1/2/2B, AQRM, AQSH1, CAFE, CAFE2, CHRC, DRIVR, OPEN, ...) — one per scripted scene; loaded into `FS_BUFFER_n` and pointer-fixed at runtime |
| `ANIM/*.ANM` | Skeletal animation of every character | 113 files; per-character mapping in `CHARA_FILE_INFOS` (e.g. Harry = `HB_BASE.ANM`, Cheryl = `SRL.ANM`, Cybil = `SBL.ANM`, Lisa = `LS.ANM`) |
| `CHARA/*.ILM` + `CHARA/*.TIM` | Legacy models/textures | NOT used by this PoC — replaced by GLTF exports of the same characters (the GLB binding must match the ANM bone order, see §5) |
| `MISC/DEMO*.DAT`, `MISC/PLAY*.DAT` | Attract-mode demo scripts (controller input replays) | Out of scope for the cutscene loader proper (demo.c system) |
| `VIN/MAP*.BIN` | Map overlay data (camera road paths, per-map event tables) | Optional: only needed if the loader also reproduces the map camera system; the DMS camera overrides it during cutscenes anyway |
| `BG/*.BIN`, `TIM/*` | Backgrounds/misc textures | Not needed for character cutscenes |

**Minimum viable file set for the first loader PoC:** one `.DMS` (e.g. `OPEN.DMS`),
the `.ANM` of each actor it references (`HB_BASE.ANM` for HERO), and the GLTF
exports of those actors. The DMS character entries are identified by 4-char names
(`"HERO"` in OPEN.DMS — `Dms_CharacterGetIdxByName` does `strncmp(name, entry->name, 4)`).

---

## 3. The `.ANM` binary format (fully decoded)

### 3.1 Header (`s_AnmHeader`, 20 bytes) then bind poses

```c
/* 0x0  */ u16 dataOffset;        // offset of the keyframe array (bytes)
/* 0x2  */ u8  rotationBoneCount; // bones with animated rotation
/* 0x3  */ u8  translationBoneCount; // bones with animated translation (usually 1: the root)
/* 0x4  */ u16 keyframeDataSize;  // == rotationBoneCount*9 + translationBoneCount*3
/* 0x6  */ u8  boneCount;         // bind-pose array size (Harry = 18)
/* 0x7  */ s8  __pad_7;
/* 0x8  */ u32 activeBones;       // bitfield of bones to update (0xFFFFFFFF for Harry)
/* 0xC  */ u32 fileSize;          // == dataOffset + keyframeDataSize * keyframeCount
/* 0x10 */ u16 keyframeCount;     // Harry HB_BASE.ANM = 568
/* 0x12 */ u8  scaleLog2;         // translations are stored << scaleLog2 (Harry = 2)
/* 0x13 */ u8  rootYOffset;       // subtracted from bone-0 translation Y (Harry = 255 = -1 Q8)
/* 0x14 */ s_AnmBindPose bindPoses[boneCount];  // 6 bytes each:
          //   s8 parentBone; s8 rotationDataIdx; s8 translationDataIdx; s8 translationInitial[3];
```

Validated on the rip: `HB_BASE.ANM` = 89088 bytes, dataOffset 0x194, 17 rotation
bones + 1 translation bone, keyframeDataSize 156, boneCount 18, fileSize 89012 =
0x194 + 156×568, activeBones 0xFFFFFFFF, scaleLog2 2. The bone order matches the
`HarryBone` enum exactly (harry.h: Root=0, Torso=1, Head=2, ..., RightFoot=17).

### 3.2 Keyframes

Each keyframe is `keyframeDataSize` bytes at `dataOffset + keyframeDataSize * k`:
- `translationBoneCount` × 3 × s8 — the per-bone translation deltas FIRST
- `rotationBoneCount` × 9 × s8 — the per-bone 3×3 rotation matrices AFTER

Bone-to-slot mapping via the bind pose: `bindPoses[i].rotationDataIdx` (−1 = static,
use `translationInitial`/identity), `bindPoses[i].translationDataIdx` (−1 = static).

### 3.3 Decoding + interpolation (Anim_BoneUpdate 0x800446D8, VERBATIM)

```
translation: t[i] = (f0[i] << scaleLog2) + (((f1[i] - f0[i]) * alpha) >> (12 - scaleLog2))
rotation m[i][j] = (f0 << 5) + (((f1 - f0) * alpha) >> 7)     // results in Q12
root extra: if translationDataIdx == 0: t[1] -= rootYOffset
```
`alpha` = the Q12 fractional keyframe position. Rotations are stored as s8 fractions
of unity (±127 ≈ ±0.99); `<<5` puts them on the engine's Q12 grid (±4064).

### 3.4 Playback rates (the s_AnimInfo tables)

- `Anim_PlaybackLoop/Once`: `timestep = animInfo.duration * g_DeltaTime` — the anim
  time advances `duration` keyframes per second (g_DeltaTime = Q12(1/30) per tick
  at the in-game rate). LookAround duration = 7 kf/s over kf 248..320 = 10.4 s sweep;
  Still = 30 kf/s.
- `Anim_BlendLinear`: alpha += duration*dt; at Q12(50 kf/s) the blend completes in
  ~0.6 s; picks the nearest endpoint keyframe while blending.
- `Anim_BlendEaseOut`: ease via `sin(alpha/2 - 0.25)/2 + 0.5`.
- Player upper/lower-body masking: `activeBones & ~extra.disabledAnimBones`
  (HARRY_UPPER_BODY_BONE_MASK = bones 0..10) — the loader should implement the mask
  to reproduce torso/leg compositing.

### 3.5 Anim STATUS tables (required to play the right keyframe ranges)

`HARRY_BASE_ANIM_INFOS[57]` (player_control.c:152) maps status -> {playback func,
startKeyframeIdx, endKeyframeIdx, duration}. Map-specific Harry anims live in the
per-map overlay (statuses ≥ mapAnimStatusStart) — for the town that is
`HB_M0S00.ANM` (54784 B on the CDN rip). The loader embeds the decompiled table
verbatim (it is engine data, not rip data) and the same pattern applies to NPC
anims via each character's own status tables in the decomp.

---

## 4. The `.DMS` cutscene format (fully decoded + validated on OPEN.DMS)

### 4.1 Structures (dms.h, verbatim)

```c
typedef struct _DmsKeyframeCharacter {  // 12 bytes
    SVECTOR3 position;      // Q7.8 (validated: z 14.05 -> 3597 raw)
    SVECTOR3 rotation;      // Q3.12 (validated: 180deg -> 2048)
} s_DmsKeyframeCharacter;

typedef struct _DmsKeyframeCamera {     // 16 bytes
    SVECTOR3 positionTarget; // Q7.8
    SVECTOR3 lookAtTarget;   // Q7.8
    q3_12    unusedAngle;    // lerped but unused (always 0 in OPEN.DMS)
    q3_12    projectionDistance; // -> vcChangeProjectionValue (GeomScreen)
} s_DmsKeyframeCamera;

typedef struct _DmsHoldRange {          // 6 bytes
    s16 startFrameIdx, endFrameIdx, keyframeIdx;  // playback-frame compression
} s_DmsHoldRange;

typedef struct _DmsEntry {              // 16 bytes
    s16 keyframeCount; u8 holdRangeCount; u8 __pad_3;
    char name[4];                        // "HERO", "CHRY"... (camera: "%CAM")
    s_DmsHoldRange* holdRanges;          // RELATIVE pointer (fix at load)
    union { s_DmsKeyframeCharacter* character; s_DmsKeyframeCamera* camera; } keyframes;
} s_DmsEntry;

typedef struct _DmsSegment {            // 4 bytes
    s16 startFrameIdx; s16 frameCount;   // playback frames AT 30 FPS
} s_DmsSegment;

typedef struct _DmsHeader {             // 44 bytes
    u8 isLoaded; u8 characterEntryCount; u8 segmentCount; u8 field_3;
    u32 field_4;                         // correlates with file size (unused)
    s_DmsSegment* segments;              // RELATIVE pointers, fixed by
    VECTOR3 origin;                      //   Dms_HeaderFixOffsets at load:
    s_DmsEntry* characterEntries;        //   ptr = (u8*)ptr + (u32)header
    s_DmsEntry cameraEntry;
} s_DmsHeader;
```

Validated on `OPEN.DMS` (the map0_s00 opening): 1 character entry `HERO`
(67 keyframes, 2 hold ranges), camera entry 73 keyframes, 1 segment
{start 0, count 73} = **2.43 s at 30 FPS**, origin (−0.80, 0, +140.43) m Q23.8,
camera `projectionDistance` ≈ 205 (≈ 50° vertical FOV via `Dms_FovScaleGet`).

### 4.2 Sampling at time t (the verbatim pipeline)

```
frameIdx = floor(t)                        // t in playback-frame units (Q12)
segment state: Dms_SegmentStateGet — if frameIdx == segment.end-1:
    frameCount > 1 -> Ending   (prev = frameIdx-1, next = frameIdx, alpha = fract+1)
    frameCount == 1 -> SingleFrame (prev == next, alpha = 0)
  else Interpolating (prev = frameIdx, next = frameIdx+1, alpha = fract(t))
keyframe index: Dms_KeyframeIdxGet — walk the hold ranges:
    frame < range.start -> break
    frame <= range.end  -> kf = range.keyframeIdx (freeze)
    else kf -= (range.end - range.start)          // compress the timeline
  clamp kf to [0, keyframeCount-1]
character: pos = lerp(kf0.position, kf1.position, alpha) + origin   (low-precision Q12 lerp)
           rot = Dms_AngleLerp (normalized Q3.12 shortest-arc lerp)
camera:    posT/lookT = lerp + origin; projDist = lerp  (Dms_CameraKeyframeLerp)
```

### 4.3 Applying the camera (vc_main/vw_system interface)

```
projDist = Dms_CameraTargetsGet(&posTarget, &lookAtTarget, NULL, t, hdr);
vcChangeProjectionValue(projDist);        // = the GeomScreen distance (FOV)
vcUserCamTarget(&posTarget, NULL, true);  // camera position target, warp
vcUserWatchTarget(&lookAtTarget, NULL, true);
```
The render camera then moves toward `posTarget` and looks toward `lookAtTarget`
through the SAME camera velocity/angle system as gameplay (`cam_mv_prm_user`
{accel 10/3 m/s², max 6/2 m/s} + `deflt_watch_mv_prm` angle dynamics — already
ported in the fog PoC's R2 module). FOV conversion: the engine's
`Dms_FovScaleGet(fov) = 96·cos(fov/2)/sin(fov/2)` — i.e. the projectionDistance
is `96/tan(fov/2)`; invert as `fov = 2·atan(96/projDist)` for a GLTF camera.

---

## 5. GLTF model binding (the loader's bridge)

The GLTF exports must expose the SAME skeleton the ANM drives:
1. **Node order = the engine bone order** (HarryBone enum: 0..17). The GLTF
   node hierarchy can differ (parent links come from `bindPoses[].parentBone`),
   but the INDEX a bind-pose slot refers to must resolve to the right GLTF node.
   Recommended: export with the bone names matching the decomp enum names
   (Root, Torso, Head, LeftShoulder, ...).
2. **Bind pose**: `Anim_BoneInit` — for static bones the translation is
   `translationInitial << scaleLog2` and the rotation is identity; the GLTF's
   own bind pose must MATCH this (the extractor's export is the reference).
3. **Per-tick update**: `Anim_BoneUpdate` writes local translation + local 3×3
   rotation per active bone; the GLTF loader converts the 3×3 (Q12, y-down
   engine convention) to a glTF node TRS (y-up: (x, −y, −z) axis mapping and
   matrix transpose per the engine's `Math_RotMatrixZxyNeg` convention — the
   same mapping the fog PoC already uses for the light direction).
4. **Compositing**: upper/lower body split via `disabledAnimBones` masking —
   run `Anim_BoneUpdate` per active anim on masked bone sets, then compose.

---

## 6. Proposed PoC architecture (when implementation is green-lit)

```
sh1rip/                       <- the PoC operates directly here
  ANIM/OPEN.DMS               <- parsed by dms.c port
  ANIM/HB_BASE.ANM            <- parsed by anm.c port
  CHARA/*.GLB (user-provided) <- gltf2 loader (reuse the fog PoC's GLB reader)

cutscene_poc (C99, single file like fog_poc.c)
  ├── anm.h/anm.c     — s_AnmHeader parse + Anim_BoneInit/Anim_BoneUpdate +
  │                     Anim_PlaybackLoop/Once/BlendLinear/BlendEaseOut (verbatim)
  ├── dms.h/dms.c     — s_DmsHeader parse (with the relative->absolute fixup)
  │                     + Dms_KeyframeInterpGet/KeyframeIdxGet/SegmentStateGet +
  │                     Character/Camera keyframe lerp + AngleLerp (verbatim)
  ├── animtables.h    — HARRY_BASE_ANIM_INFOS + NPC status tables (engine data)
  ├── gltf_bind.c     — GLB scene -> engine bone indices; ANM -> node TRS apply
  ├── camvc.c         — the camera target/velocity/angle system (already proven
  │                     in fog_poc.c's R2 module: vwRetNewAngSpdToTargetAng etc.)
  └── main loop       — 30 Hz tick lockstep (g_IntervalVBlanks=2 cadence):
        tick: timer += dt*rate;  DMS sample -> actor TRS + camera targets;
              ANM advance per actor (Anim_*);  camera vc update;
        render: software rasterizer (reuse fog_poc.c's PSX-accurate path:
              GTE integer snap, 15-bit color, dither, affine UV) OR a GL
              presentation of the same matrices.
```

Playback controls to expose: play/pause, scrub on the DMS frame index, the
event-step rates (1x/4x/8x/10x), per-actor anim-status override, wireframe/
skeleton debug view, and the `--dump` audit (CSV: frame, actor TRS, camera
pos/look/projDist — mirroring fog_poc.c's `--cam-dump` practice).

Verification battery (the fog PoC discipline): golden stills at pinned frame
indices; byte-identity between the headless `--frame N` render and the live
window's Nth presented frame; ANM decode cross-checked against the extractor's
GLB bind poses; DMS decode cross-checked against the hold-range walk (unit
tests over synthetic ranges); FPS lock 30; native 320×224.

---

## 7. Known gaps / risks (to resolve during implementation)

1. **CDN rip truncation**: the stored `OPEN.DMS` is only 2048 of ~36 KB (the
   header + entries + first keyframes parse fine; the CDN copy is cut). The
   user must re-upload the full file (or the loader is validated on another
   DMS that is complete — check the other 15 `.DMS` files' sizes first).
2. **Map-specific Harry anims**: statuses ≥ mapAnimStatusStart come from
   `HB_M0S00.ANM` etc.; the first PoC should pin ONE map (map0_s00 town) and
   embed only its tables.
3. **NPC status tables**: the decomp's NPC anim tables (per character) need
   porting per actor; start with HERO-only cutscenes (OPEN.DMS is HERO-only).
4. **Engine y-down vs glTF y-up**: every structural port already handles the
   mapping at the boundaries (the fog PoC's light/camera code is the template);
   the ANM rotation matrices need the same explicit conversion + tests.
5. **projectionDistance**: verify against DuckStation's SetGeomScreen behavior
   for values != 224 (the fog PoC pins 224 for rooms; cutscenes change it
   dynamically — the first PoC can render with the equivalent glTF FOV instead
   of the PSX screen-space projection, documented as such).
