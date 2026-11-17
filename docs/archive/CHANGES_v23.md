# CHANGES — v23

## The three directives

1. **HUD scaling for the native 320x224 viewport** — the v22 status HUD lines
   ran up to 66 chars x 8 px = 528 px wide and ran off the right edge of the
   320-px native framebuffer (only ~28 of 66 columns visible).
2. **The authentic R2 "camera view"** — the engine's SELF_VIEW system,
   verbatim from the decompilation, with data-derived pan bounds.
3. **The Cutscene Loader PoC design** — `CUTSCENE_LOADER_DESIGN.md` (this
   release): the complete `.ANM` + `.DMS` binary-format identification and
   the loader architecture, validated against the actual ripped files.

No engine math was modified: the fog/snow/GTE/render paths are untouched and
the non-R2 render is BYTE-IDENTICAL to v22 (verified by md5 on the
deterministic shots).

## 1. HUD scaling (the native 40-column text grid)

The PS1's own screens never exceed 40 columns of 8x8 glyphs at 320 wide (the
options/save screens wrap within that grid). The v23 HUD adapts to the
framebuffer width:

- At native (`fb->w <= 400`): a compact 5-line panel, every line <= 39 cols:
  `ENV{6,3} night st` / `FOG OFF 40.0m (0,0,0)` / `LI 0.44 SP 1.30 E1 FL ON` /
  `R2 OFF Y+00.0 P+0.0 L82/7` / `TAB menu H hud Y r2 V + arrows`.
  62 px tall = 28% of 224 (the options screen's own panel share).
- The Tab mode browser rows reformat to <= 37 cols (name + fog + spot; the
  full columns and the call-site citations remain in the 640x360 layout).
- The 640x360 non-engine presentation keeps the full v22 layout + the R2
  status appended.

VLM-verified at native: 5 lines, zero overflow, top-quarter only, legible.

## 2. The R2 camera view — the engine SELF_VIEW system (vc_main.c, verbatim)

What the feature IS in the engine: holding the VIEW button (the options
"Extra View Mode: Self_View" ON) enters `VC_MV_SELF_VIEW` — the camera moves
to Harry's head and looks where the head/eye look, with restricted angles.
The PoC binds the view button to a configurable key (default V; the user
briefing calls it R2) and the D-pad to the pan input.

Every constant is the engine's own fixed point (Q19.12 lengths, Q3.12 angles
4096=360deg, g_DeltaTime=136):

- **Position** (`vcMakeIdealCamPosByHeadPos` 0x800839CC): cam = head +
  0.18 m at (eyeYaw+140deg), 0.07 m below the head; the SELF_VIEW warp flags
  glue it there every tick.
- **Far-watch target** (`vcMakeFarWatchTgtPos` 0x800832B4): 10 m ahead
  (VC_AREA_WIDE town) at root+0.8 m (the head minus 0.9 m).
- **THE RESTRICTED PAN** (`vcMixSelfViewEffectToWatchTgtPos` 0x80082DF8,
  Idle branch — the plain-standing town behavior): yaw correction = dead zone
  4 deg then 1/8 slope; pitch = headPitch - 8 deg + vertical/2; vertical
  clamp +/-70 deg; FINAL pitch clamp +/-80 deg. An 82-deg head sweep
  compresses to ~14 deg of view pan — the authentic "look around slightly".
- **Head pan bounds from the RIP (data, not invented)**: HB_BASE.ANM
  HarryAnim_LookAround kf 248..320 head sweep = yaw [-81.81, +18.86] deg
  (magnitude 82), pitch [-7.7, +7.7] deg (scripts/anm_head_bounds.py).
  Input beyond the bounds CLAMPS (200-deg request -> +81.91 deg achieved).
- **Pan rate**: 22 q3_12/tick (~58 deg/s) — the engine's own held-button
  camera-angle pan (`g_VBlanks * V_BLANKS_MULT(11)`, vc_util.c:216).
- **Interpolation**: `vwRetNewAngSpdToTargetAng` with the effect-rate blend of
  `self_view_watch_mv_prm` {1.68, 3.08, 0.44, 1.4} into `deflt_watch_mv_prm`
  {1.2, 2.2, 0.22, 0.7} (`vcGetUseWatchAndCamMvParam` 0x80084A34).
- **Handheld noise** (`vcSetDataToVwSystem` 0x80085884 + `vcCamMatNoise`
  0x80085A7C): vy w2 [cos 40deg/s + cos -160deg/s]/2, vx w4 [cos 50deg/s +
  cos 80deg/s]/2 on vcSelfViewTimer; the six w12 matrix-element terms are
  applied to the camera basis rows before orthonormalization (documented
  approximation: the rotational content is exact, the pure-shear part is
  sub-GTE-pixel at 320x224 and has no quaternion equivalent).
- **Entry**: warp snap (the engine sets WARP_CAM/CAM_TGT/WATCH on the
  transition edge). **Release**: the `vcReturnPreAutoCamWork(true)` warp snap
  (the engine's exit-from-view path; the plain-road chase glide has no PoC
  equivalent — the engine's own deceleration model caps the closing speed
  below a 1.7 m/s moving target inside ~0.53 m, so the 0.1 m arrival radius
  is unreachable against the moving track eye).
- **extraViewCtrl Normal/Reverse** (savegame.h:100): Normal = view while
  held; Reverse = view unless held (both engine modes, `--r2ctrl` + HUD).
- **Vc_IsInSelfViewRestrictedZone** 0x8008150C: the THR zone
  x[201.8, 230.0] z[-92, -68] disables the view — implemented verbatim
  (the PoC room IS THR); the map switch structure is the hook for other
  maps' overrides.
- **While active** the env light + snow anchor to the self-view camera (the
  engine's light follows the active camera); on the 30 Hz tick grid.

Controls: **V** (configurable `--r2-key K`) hold = the view button;
**Y** = the "Extra View Mode" toggle; **arrows** = the pan input while
engaged (they keep the scrub function when the view is off). The HUD shows
the state + the current head offsets + the limits (`R2 ON Y+61.9 P-3.9
L82/7`). KeyUp events were added to all three window backends (Win32
WM_KEYUP, SDL KEYUP, X11 KeyRelease) — hold semantics require them.

Deterministic verification: `--r2shot t=S,pan=Y,P,file=F.png` (the view held
from t=0, the pan input driven to the target at the engine rate) prints the
restriction proof. Interactive verification: `FOGPOC_R2TEST=1` drives the
real live_action path with a scripted key sequence. `FOGPOC_HUDSNAP=N`
captures the Nth presented frame with the HUD overlay.

## 3. Cutscene Loader design

`CUTSCENE_LOADER_DESIGN.md` — the complete `.ANM` format (header, bind poses,
keyframes, the Anim_BoneUpdate interpolation formulas, the 30 Hz playback
rates and the anim-status tables), the complete `.DMS` cutscene format
(segments @ 30 FPS playback frames, hold-range compression, character
Q7.8/Q3.12 keyframes, the camera posTarget/lookAtTarget/projectionDistance
keyframes and the `Dms_FovScaleGet` FOV relation), the file inventory
(`CHARA_FILE_INFOS` -> the rip's ANIM/CHARA/TIM files), a real cutscene
driver walkthrough (map0_s00 OPEN.DMS), the GLTF binding rules, and the
proposed architecture + verification battery. Validated against the ripped
`HB_BASE.ANM` (full parse) and `OPEN.DMS` (header + entries + keyframes; the
CDN's copy of OPEN.DMS is stored truncated at 2048 bytes — documented as a
known gap: the full file must be re-uploaded before implementation).

## Verification battery (all PASS)

- v22 byte-identity on the deterministic shots (the non-R2 path untouched)
- 21-mode sweep at native 320x224; day/night luminance semantics
- dither (27.9% pixels differ when off) + PSX wobble (42.4%) default ON
- R2: yaw/pitch clamps at the ANM bounds; view pan ~14 deg max (not 360);
  THR zone disables; Normal/Reverse/feature-off modes
- 30 fps presentation meter; native 320x224 render
- GLB byte-identical (md5 c7183184d20a2508ce41af2702629a33)
- fence stability: identical band luminance across ticks, VLM-confirmed no
  dark/bright alternation (byte-identity to v22 by construction)
