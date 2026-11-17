# CHANGES_v21 — the missing verbatim fixes (native raster, GPU-verbatim UV, far cull, lazy mode)

This release completes the work the v20 crash interrupted: the v20 zip on
the CDN did NOT actually contain the "engine-native raster default", the
"GPU-verbatim UV/texel sampling", or the far-cull otShift fix that were
reported — all three were re-derived from the decompilation + DuckStation
and implemented here, alongside the C++ side of the camtrack `lazy` look
mode. Every change below is decomp/DuckStation-evidence-driven; no
thresholds, no smoothing, no manual patches.

## 1. Engine-native 320x224 default (accuracy over framerate/resolution)

`--res` now defaults to **320x224** (window 960x672, 3x). Evidence:

- `include/game.h`: `SCREEN_WIDTH 320`, `FRAMEBUFFER_HEIGHT_PROGRESSIVE 224`
  (`FRAMEBUFFER_HEIGHT_INTERLACED = 448` is the interlaced path only).
- `game_main.c:82`: `Screen_Init(SCREEN_WIDTH, false)` — the main game
  boots **320 progressive** → `gsScreenHeight = 224`.
- `screen_draw.c:45-46`: `GsDISPENV.screen.h = GsDRAWENV.clip.h = 224` —
  BOTH the display window and the drawing clip are 320x224.
- `vc_util.c:20`: `SetGeomScreen(g_GameWork.gsScreenHeight)` = 224.

The old 640x360 16:9 presentation remains available as a documented
NON-ENGINE mode (`--res 640x360`). Measurement: at 640x360 the supersampled
presentation doubles the measured texel-crawl density (41.9% sustained
fence toggling vs 23% at native); the engine's own raster density is where
the crawl is authentic.

## 2. The vertical snap lattice is h/224 (was h/240)

`enginePixScaleY = fb_h / 224.0f`. At native this is exactly 1.0 — one
output row per GTE screen row (the previous h/240 gave 0.933 at native: a
snap lattice COARSER than the actual raster, wrong at the engine's own
density). Evidence for 224 over 240:

- The engine's raster is 320x224 progressive (above).
- A fresh vertical cross-correlation of the PoC vs the 640x360 reference
  capture is flat within ±2 px of dy=0 — the reference's 3D content fills
  the whole frame with NO letterbox border, i.e. the capture stretched the
  224-row display area, not a 240-line field.
- A/B render at 640x360 (h/240 vs h/224) is a statistical tie
  (full-frame MAD 7.8163 vs 7.8253; fence 15.387/15.407; ground 7.85/7.30;
  bush 1.85/2.21) — engine truth decides, and the engine truth is 224.

## 3. GPU-verbatim UV/texel sampling (the DuckStation rasterizer DDA)

`raster_tri`'s ps1/affine path now samples textures exactly like
DuckStation's software rasterizer (`gpu_sw_rasterizer.inl`):

- **Integer-position evaluation**: the attribute is evaluated at the
  pixel's own coordinate (DuckStation's `DrawSpan` steps `current_x` and
  reads the accumulator AT `current_x` — the cell's left/top edge), not at
  a +0.5 pixel center. At native scale 1.0 this is exactly (x, y).
- **Q24 fixed-point accumulation** with the `UVStepper::Init`
  **+0.5-texel bias** (`(u << 12) + (1 << 11)`, all `<< 12`).
- **ATTRIB_STEP gradient quantization**: `(u32)(det_attr * 4096 / det) << 12`
  — truncating division toward zero, negative gradients wrap through u32,
  exactly like the hardware stepper. Axis assignment per DuckStation:
  `dudx = ATTRIB_STEP(u, y)`, `dudy = ATTRIB_STEP(x, u)` (verified by
  solving the attribute plane directly).
- **Truncate8 texcoord**: the u8 texcoord wrap at 256 (`u >> 24`), then the
  texture-window fold (the converter's standalone textures → `% tw`).
- The vertex texel UVs are recovered as integers (`lrintf(u * tw)`) — the
  engine's polygon packet UVs ARE integers and the converter wrote
  `u_norm = u_texel / tex_w`.

This is what kills the ~2x-rate wire↔hole sampling flips on the
high-frequency binary-alpha fence texture. Two implementation bugs were
found and fixed during bring-up (both by measurement):
(a) `(int64_t)u32` widening read wrapped negative gradients as huge
positives — distant leaves smeared into solid blobs; fixed with
`(int64_t)(int32_t)` two's-complement widening (the final `uint32_t` cast
keeps the mod-2^32 stepper wrap).
(b) the X/Y gradient axes were initially swapped; the FOGPOC_XCHK
cross-check harness went from 54,700 mismatching pixels to 1,865 (all
small, expected position/bias deltas).

The modern (opt-out) path keeps float perspective-correct sampling.

## 4. Far cull otShift correction (0x79C << 3)

`farCullQ8 = 0x79C << 3` (was `<< 2`). The outdoor world path is
`WorldGfx_Draw(1)` (game_sys_states.c:189) and the `1` flows UNCHANGED:
`WorldMap_ChunksDraw(1)` → `WorldMap_Draw` → `func_80057090` →
`func_80057344` → `Gfx_MeshDraw(otShift=1)` (and `Gfx_BillboardDraw`
receives the same 1, world_map.c:1383/1391). The engine culls at
`0x79C << (otShift+2)` = 15584 Q8 = 60.875 m in fog-off modes
(bodyprog_80056D8C.c:656, billboard_draw.c:124) — not the 30.4 m a room
draw (otShift 0) would use. The PoC's OT bucket shift was already `>>3`
(otShift 1 semantics); the cull now matches the SAME call. Fog modes are
unaffected (the MIN keeps fog.far, always the smaller).

## 5. lookMode 'lazy' — the camtrack v9/v10 merged mode, C++ side

The camtrack v9/v10 editor's merged "path-following + hold-direction"
look mode is now parsed and simulated by the PoC:

- `lookMode: "lazy"` accepted for every track type (the camtrack v10
  per-type pick lists), `lazyRateDegS` parsed with clamp [1,720],
  default 25 (the editor's v9.1 makeTrack default).
- `camtrack_eval` evaluates 'lazy' exactly like 'path' (the path tangent).
- The playback keeps an inner lazy quat (TurnFilter::lazyQ) that
  approaches the exact tangent target along the shortest arc at
  <= lazyRateDegS and HOLDS when aligned; turnarounds read as gentle head
  turns and the heading turns back smoothly after a pingPong reversal;
  seeks / track switches / big jumps resync to the exact target; paused /
  scrubbed it freezes. The outer SMOOTH turn filter still applies on top.
- Verified numerically (FOGPOC_LAZYDBG): hold = 0 drift while aligned;
  reversal turn-back = exactly 25.0 deg/s with the configured limit.

camdat files with `lookMode: "path"` or any earlier mode are unaffected.

## 6. The v20 open items — resolved with evidence

- **"Distant lamp glow specks"**: the reference's top-band bright specks
  are the SUBTITLE MESSAGE BOX overlay — dialogue text glyphs in
  (224,224,232) with a frame at y=4/41, x=4..531, present in both
  reference frames with the dialogue advancing between them (the "5-8
  static specks" were glyph clusters). It is a 2D UI overlay drawn after
  the 3D scene, not a pipeline discrepancy. The MAP0_S00 dust/ash system
  (func_800CD8E8, 20 particles anchored at (-258,-1.4,244.1)±2.5 m, drawn
  only within 40 m of the player) is confirmed NOT drawn in this scene —
  the scene bounds are z 78..120 vs anchor z 244.
- **Bush +7.6% static**: unchanged attribution (camdat camera speed
  1.70 m/s vs the reference session's ~1.12 m/s; the flashlight cone
  gradient position follows the camera).

## THE MEASUREMENTS (updated_test_camdat.json @ t=23.16, flashlight ON)

Static zones vs `live_00023.16.png` (subtitle box excluded), 640x360:

| zone | v20 | v21 |
|---|---|---|
| sky-right | 0.991 | 0.986 |
| sky-top-clean | 1.003 | 1.006 |
| ground-left | 0.987 | 0.984 |
| fence | 1.060 | 1.055 |
| ground-center | 0.994 | 0.996 |
| bush | 1.007 | 1.014 |
| far-center | 1.002 | 1.002 |

Temporal (native 320x224, ticks 690-699): fence per-tick big24 10-20% vs
the reference pair's (50 ms) 21.6%; change-blob structure PoC median 1 /
p90 8 / 10.2% blobs>=8px vs REFERENCE median 2 / p90 17 / 19.7% — the
PoC's crawl is FINER-grained than the authentic engine crawl (the engine's
own fence flips in LARGER blobs). Bush sustained 0.05-0.14%. Intra-tick
frames byte-identical (60 Hz output duplicates the 30 Hz tick state).

VLM acceptance: static 640x360 **PASS** (all criteria), static native
(upscaled) **PASS**, temporal 6-frame sequence **VERDICT: AUTHENTIC**
("no violent strobing; mild per-pixel crawl typical of PS1; bushes
stable; flashlight hotspot stable").

## REGRESSIONS

- 21-preset sweep at native: all modes render, no failures; night
  darkness (mode 6 mean 25.5) vs day (mode 1 mean 75.4); heavy-fog modes
  stable at 0.02% per tick; per-mode fence crawl at parity with v20
  (e.g. mode 0: 11.67% → 12.45%, mode 3: 13.67% → 15.26% — within the
  authentic crawl band, structurally per-pixel).
- dither + wobble default ON (byte-diffs vs --no-dither / --modern).
- GLB/IPD byte-identical to the CDN originals (md5 c7183184…,
  8c8cd3b4…).
- Benchmark smoke: 300 frames, 6.55 ms/frame at native.
- camdat `lookMode: "path"` behavior unchanged (all existing goldens
  re-rendered identically except through the DDA/lattice/cull fixes).
