# Silent Hill Fog + Snow + Rain + Night + Flashlight PoC — GLTF-native edition (v23)

> **v23 — THE R2 (SELF) CAMERA VIEW + the native HUD + the Cutscene Loader
> design**: the engine's SELF_VIEW system, verbatim from vc_main.c — hold
> **V** (the view button, configurable `--r2-key`) to look around from
> Harry's-eye perspective with the engine's RESTRICTED pan (dead zone 4 deg +
> 1/8 slope: an 82-deg head sweep — the bound from the actual ripped
> HB_BASE.ANM LookAround data — compresses to ~14 deg of view pan; NOT a
> 360-deg free look), the 0.18 m head offset at +140 deg, the far-watch
> target, the engine angle dynamics and the handheld noise wobble; **Y**
> toggles the Extra View Mode, arrows pan, the HUD shows the state + limits;
> the THR restricted zone disables it exactly like the engine. The HUD is
> re-formatted for the native 320x224 40-column text grid (the v22 lines
> overflowed the 320-px framebuffer). CUTSCENE_LOADER_DESIGN.md documents the
> complete .ANM/.DMS binary formats (validated against the rip) for the
> separate cutscene loader PoC. The non-R2 render is BYTE-IDENTICAL to v22.
> See CHANGES_v23.md.

> **v22 — THE AUTHENTIC 30 fps PRESENTATION LOCK (+ the disc-rip
> 23.01-vs-27.45 root cause + camtrack v11)**: the realtime window now
> presents at strictly 30 fps (one present per engine tick,
> `g_IntervalVBlanks = 2`) and the FPS meter measures the true wall-clock
> presentation rate — it reads **30.0**, fixing the reported "111 FPS"
> (the v20/v21 meter sampled busy render time only, before the limiter
> slept). The tick content is BYTE-IDENTICAL to v21: the lock is
> presentation-only, zero rendering math touched. The flicker complaint
> was root-caused against the user's own disc rip: the engine draws the
> fence SOLID OPAQUE + scattered punch-through holes in night mode (code
> 0x3C, stp ignored — verified in Gfx_MeshDraw __block1530 + DuckStation
> + the rip's CLUT row 14, and the GLB was verified pixel-exact against
> the rip), and the close-up fence "boil" at the camdat's 1-1.5 m camera
> distance is MOTION (proven: the modern perspective-correct renderer
> boils identically) — presented at the engine's even 33.33 ms cadence it
> reads as coherent motion (VLM: AUTHENTIC PS1 BEHAVIOR). camtrack v11
> advances its preview on the same 30 Hz tick grid. See CHANGES_v22.md.

> **v21 — THE MISSING VERBATIM FIXES (native raster + GPU-verbatim UV +
> far cull + lazy mode)**: the default render resolution is now the
> engine-native **320x224 progressive** raster; texture sampling in the
> ps1 path is the DuckStation-verbatim fixed-point DDA (integer-position
> evaluation, +0.5-texel Init bias, truncating Q12 gradients, u8 texcoord
> wrap) — reproducing the engine's own fence wire/hole crawl rate; the
> far cull is `0x79C << 3` (the outdoor WorldGfx_Draw(1) otShift chain);
> and the camtrack `lazy` merged look mode is parsed + simulated (the
> inner rate-limited heading quat). See CHANGES_v21.md. Everything else
> (the v20 30Hz tick lockstep, the v17 billboard color path, the v16 OT
> layers, the flashlight math, dithering/wobble defaults) is untouched —
> all suites re-run, zero regressions.

> **v16 — THE OT MODEL LAYERS + THE gte_NormalClip BACKFACE CULL (engine-verbatim)**:
> TWO engine mechanisms v15 was missing, both derived 1:1 from the
> decompilation and DuckStation: (1) the per-model OT SECTION BASE
> (func_80057090 -> func_800571D0(field_B_1): bases 0/2/4/33/66/99 —
> the IPD's layer classes; mesh quads bucket at BASE + OTZ>>3, the
> billboard/flake section keeps base 0) — the missing layering made
> cross-model overlaps (fence/bush/overlay/sign) resolve by raw depth
> and flip frame-to-frame; (2) the Gfx_MeshDraw gte_NormalClip dual
> backface cull (nclip on the SNAPPED screen coords; MASK/billboard
> quads never culled) — v15 painted BOTH windings, so every
> backfacing wall/bush/fence quad piled dark wrong-side copies over
> visible geometry. Night bush blob shrinks ~65%, the fence/bush
> layering is VLM-verified correct and temporally STABLE ("only the
> expected PS1-style vertex snapping and texture wobble"). All
> previous fixes retained: v15's OT raster + default-ON dither, the
> verbatim per-vertex flashlight, fog/weather/snow/rain. GLB inputs
> untouched. See CHANGES_v16.md.

> **v15 — THE ORDERING-TABLE RASTER (engine-verbatim) + HARDWARE-DEFAULT DITHER**:
> ALL quads (opaque + MASK + BLEND) now draw through the engine's single
> per-quad OT walk (Gfx_MeshDraw MAX-vertex-SZ buckets, far->near, LIFO;
> the engine far cull per QUAD) — the per-pixel float depth TEST is gone
> because the PSX has NO depth buffer (DuckStation gpu_sw_rasterizer.inl:
> pure command-order painting). This removes the true depth-comparison
> z-fighting (the reported texture/model flicker). DITHER now defaults ON
> (the DTE hardware behavior; D key / --no-dither toggle). The flashlight
> / fog / weather / snow / rain pipelines re-audited line-by-line this
> session — verbatim, no changes (CHANGES_v15.md §5). The remaining
> temporal "flicker" measured on both renderers = the authentic 15-bit
> band-crawl + texel motion aliasing the PSX itself had (CHANGES_v15.md §3).
> See CHANGES_v15.md.


> **v14 — THE TRANSPARENT-PASS LAYERING FIX (FENCE & BUSH, engine-verbatim)**:
> the transparent pass now replicates the PSX engine's ordering table
> PER QUAD (Gfx_MeshDraw: OTZ = MAX vertex SZ Q8, bucket Q8>>3, far->near,
> LIFO within a bucket; Gfx_BillboardDraw: CENTER-depth bucket; flakes ride
> the same buckets and tie above quads like the engine's add order) instead
> of v13's per-mesh average-depth sort — the root cause of bushes painting
> over nearer fences and of the multi-frame layer flipping (most visible at
> night; present in every mode, fog masked it). The per-texel rule is now
> DuckStation-verbatim: ONLY a 0x0000 texel (alpha 0) is a hole; alpha-127
> STP texels render OPAQUE (the engine draws room STP quads ST-clear —
> proven by parsing THRF9FD.IPD: all 32 objects have field_B_0=0, so the
> 0x3C|isTransparent*2 ST path is unreachable for room meshes). The
> camtrack_v3 editor/preview applies the same per-texel rule (its WebGL
> preview was already immune to the ordering bug: opaque-pass alpha-tested
> rendering). ZERO REGRESSIONS: verify.sh 30 PASS / 0 fail (goldens
> regenerated after VLM confirmed the day-reference diffs are vegetation
> re-layering only); camdat parser 45/45; fxoff suite 35/35; env0 JS-C++
> pixel match unchanged; 21-mode sweep 21/21; snow/rain verified; VLM
> confirms correct + stable fence/bush occlusion over multiple frames in
> night/day/fog. GLB UNMODIFIED (md5 c7183184d20a2508ce41af2702629a33).
> See CHANGES_v14.md.

> **v13 — THE CAMTRACK_V2 CAMDAT ENV OBJECT (strictly additive)**: fog_poc now
> parses the per-model `env` object written by the camtrack_v2 editor (the
> World & Weather panel): `pair [A,B]`, `weatherTarget`, `bootWeather`,
> `lensFlare`, `flashlightOn`, `psxWobble`, `dither`, `particles`, `engine` —
> with the editor's sanitizeEnv semantics VERBATIM (strict booleans, exact
> clamps) and the boot priority **CLI flags > camdat env > camdat legacy
> flags > engine defaults**. The boot-weather recipe is applied
> unconditionally like the editor's setBootWeather (recipe 2 included — the
> `--weather` CLI keeps its v8 `!= 2` quirk). ZERO REGRESSIONS, PROVEN:
> legacy camdat renders byte-identical to v12 (md5-equal) AND all 21
> `--envpair k,k` modes are byte-identical mode-for-mode; the parser unit
> test is 45/45; env == equivalent-CLI boots are byte-identical; verify.sh
> passes in full (30 PASS lines). Acceptance file:
> input/camdat_v2_test.json (an authentic editor export). The v2 editor's
> temporary "Effects Off (env 0)" preview toggle is session-only and never
> serialized; its C++ equivalent view is `--envpair 0,0 --weather 0`.
> GLB UNMODIFIED (md5 c7183184d20a2508ce41af2702629a33). See CHANGES_v13.md.

# Silent Hill Fog + Snow + Rain + Night + Flashlight PoC — GLTF-native edition (v12)

> **v12 — THE ULTIMATE VERBATIMNESS & FAITHFULNESS AUDIT**: full-repository
> line-by-line audit of the whole v11 source against the decompilation and
> DuckStation. 9 discrepancies found and continuously corrected (not just
> the first): the Q12(1/6)=682 blend-ramp off-by-one, DuckStation's
> unsigned TruncateRGB semantics, the complete weather-transition state
> machine (the field_234A lock, the 800DD592 snow-spawn-type switch with
> the ParticleType_Unk1 movement, the field_2349 density rule, the engine's
> tail zeroing, the verbatim RNG order), plus TWO engine/package defects
> discovered and documented (the D0B18(6) bank-count overrun latent in the
> shipped game; the stale goldens in the v11 zip). ALL NINE runtime weather
> states (D0B18 args 0..8, wind machinery live) now exposed via the W key
> and --weather-target N for multi-map testing. ZERO REGRESSIONS: 45/45
> mode configs byte-identical to v11, full verify.sh pass, VLM-verified
> fog. One literal engine reading (the STP-hole veil) was tested and
> REVERTED — it contradicted the user-verified v3 fog ground truth (+33
> mean RGB; VLM: "washed-out"); the analysis is preserved in-code. GLB
> UNMODIFIED (md5 c7183184d20a2508ce41af2702629a33). See CHANGES_v12.md.


> **v11 — THE NORMAL-FOG VEIL FIX (completes v10's fog work)**: v10 fixed the
> boot flag but the fog itself was STILL broken — distant opaque geometry
> faded to BLACK instead of the fog color (mean RGB 19.3 units under the v3
> ground truth). Root cause: v5-v10 gated the additive fog veil
> (`fogColor * f`) on the STP-prim flag, misreading `Gfx_MeshDraw`'s OT order
> (the non-STP branch calls `setSemiTrans(poly3, 1)` — the textured quad is
> SEMI-TRANSPARENT, so the opaque fog G4 base IS visible through it; LIFO
> addPrim draws it FIRST as the base layer). The veil now applies to every
> textured prim exactly as the engine does:
> `final = fogColor*f + (texel * tintEff * (1-f)) >> 7` — the v3 formula,
> 100% decomp-derived, ZERO manual patches. Verified: day render within ~1
> RGB unit of the v3 ground truth + VLM visual audit PASS; 45/45 mode A/B
> (only the 6 fog+color configs changed, night/flashlight BYTE-IDENTICAL);
> infinite-cycling stress + flashlight-gate live tests ALL PASS; DuckStation
> GTE UNR/UNRDivide/RTPS audit byte-identical (wobble path untouched).
> GLB UNMODIFIED (md5 c7183184d20a2508ce41af2702629a33). See CHANGES_v11.md.


> **v10 — THE FOG / FLASHLIGHT-GATE / ENV-FREEZE FIX RELEASE**: three
> long-standing runtime defects fixed with 100% decompilation-derived
> logic, ZERO manual patches, ZERO regressions:
> **(1) NORMAL FOG FIXED** — v5-v9 keyed the renderer fog flag on the
> camdat `fogon` hint (OR nightBoot); with the shipped camdat
> (`fogon:false`) every day-stage boot rendered a black, unlit, fogless
> scene. The engine has NO global fog flag — fog presence is ALWAYS the
> current preset's `field_E` (world_effects.c:881), which the env already
> applies verbatim; the renderer now follows it (day renders are
> byte-identical to the old `--fog` goldens, the known-correct look).
> **(2) FLASHLIGHT GATE FIXED** — the F key now uses the ENGINE's toggle
> rule: refused exactly when the two current presets are identical
> (`isFlashlightUnavailable`, item_screens_2.c:1267), NOT the
> FlashlightAllowed flag (which gates BGM/monster-AI/lightning — never
> the toggle). F works on every mixed pair; identical pairs refuse up
> front instead of accepting and silently auto-off-ing 33 ms later.
> **(3) ENV FREEZE FIXED** — the 30 Hz env clock stalled for a full ~50 s
> camtrack cycle at EVERY track wrap (mode changes and the flashlight
> appeared dead); plus the `--shot t>49.88 s` / `--duration>49.88 s`
> paths looped forever. A monotonic session clock + a backward-time
> resync (mirroring the snow system's guard) fix all of it — infinite
> mode cycling PROVEN (240+ mode changes across 4 wraps, 7758 env ticks,
> flashlight ramps complete, zero stalls). Pristine-v9 A/B: 55/55 renders
> BYTE-IDENTICAL. verify.sh ALL PASS. GLB UNMODIFIED (md5
> c7183184d20a2508ce41af2702629a33). See CHANGES_v10.md.

> **v9 — MODE SELECTION + FACT-BASED DOCUMENTATION + TABLE CORRECTION**:
> ALL 21 presets + 24 authentic pairs are now selectable IN THE RUNNING
> WINDOW — **Tab** opens the on-screen WORLD MODE BROWSER, **[ ]** cycles
> presets, **, .** cycles the authentic pairs, **H** toggles the status
> HUD, `--preset N --menu --no-hud` on the CLI. **MODES_GUIDE.md** is the
> definitive fact-based documentation of every mode (every value cited to
> the decomp, zero VLM guesses). The documentation pass exposed two v8
> transcription errors — now corrected with byte-level proofs: the twelve
> Q12(CHUNK_SIZE) fogDistances are **40 m (163840, terrain.h:7), not 8 m**,
> and entries [16..20] were re-ordered to the decomp's raw order
> [dim, THICK, spotlight, blue-night, s06]. Pristine-v8 A/B: 16/25 renders
> BYTE-IDENTICAL (incl. day/night/nightmare with and without flashlight),
> 9/25 differ exactly as the decomp predicts; full verify.sh suite ALL
> PASS. GLB UNMODIFIED (md5 c7183184d20a2508ce41af2702629a33). See
> CHANGES_v9.md.

> **v8 — THE COMPLETE WORLD-EFFECT AUDIT RELEASE**: ALL 21 MAP_EFFECTS_INFOS
> presets (was 5), the full RAIN weather system (Particle_RainDraw streaks/
> splashes/drips + the sine cross-fade weather transitions), the enum-2
> directional light (func_80057A3C incl. the MVMMA FC hardware bug), preset
> 5's DYNAMIC fog, the one-frame LIGHTNING flashEffect, and two GTE
> byte-accuracy fixes (IR0 clamp [0,0x1000]; the LUT-exact beam constants
> -1056/3958). GLB UNMODIFIED; every v7 golden render still BYTE-IDENTICAL
> (verify.sh 22/22). See CHANGES_v8.md; `--listmodes` prints the whole
> preset table. New keys: `W` weather, `L` lightning.



A self-contained C99 **software renderer** that loads a modern GLB (glTF 2.0)
**directly in-app** and applies the authentic Silent Hill PS1 engine **fog**
and **snow** effects, replicated line-for-line from the
[silent-hill-decomp](https://github.com/shdecompilations/silent-hill-decomp)
sources, the **exact CamTrack Editor camera** (`camtrack.html` v2 —
supersedes `camdat.html`) with its live turn-rate filter, the **Night
Sequence** env system (both authentic night pairs), and the original
**per-vertex flashlight** anchored to HERO (the virtual camera).

## v7 — REALTIME-WINDOW FLASHLIGHT + BYTE-ACCURATE WOBBLE (read this first)

v7 fixes the long-standing "flashlight lights the snow but not the
environment" defect in the **interactive realtime window**:

1. **ROOT CAUSE (decomp-cited)**: the engine runs `Gfx_EffectsUpdate()`
   **every frame** from the main state dispatcher
   (`game_sys_states.c:167`, right before `particleSystemUpdate` and
   `WorldGfx_Draw`) — it advances the flashlight ramp, the env-preset blend
   and the light position/direction on the game clock. v4-v6 only ran that
   update in the benchmark/`--shot` paths; the Win32/SDL/X11 window loops
   never ticked it, so the interactive window froze the env at its boot
   state: the light sat at the world origin with `spotLightIntensity 0`
   (ambient only — no beam), while the snow base color still flipped via the
   *slot boolean* (`func_8003EDB8`) — exactly the reported "snow responds,
   geometry does not" asymmetry. v7 calls `sh_env_sync_live` in all three
   window loops, exactly like `run_benchmark`. Verified live: 121 env ticks
   over a 4 s window run, `fi` 0→4096, `spot` 5324 (Q12(1.3)), fog OFF at
   full intensity, DQA 20, and the light position tracking the camera every
   tick (env-dump A/B, plus VLM-judged mid-run frames: old build = "pitch
   black unlit geometry, only particles lit"; new build = "ground and fence
   bases illuminated").
2. **Engine-exact light-mode gate**: `Gfx_MeshDraw` (0x8005801C) selects the
   per-vertex light pipeline on `g_WorldEnvWork.field_0` ALONE (lines 677/692
   of `bodyprog_80056D8C.c`). v4-v6 additionally gated it on the renderer's
   debug fog flag — removed; the debug `--nofog` only disables the fog
   ramp/veil/clear now (the engine has no such toggle).
3. **PSX wobble is DuckStation-byte-accurate and ON BY DEFAULT**: the GTE
   screen coordinate is `Sx = UNR*IR1 + OFX` truncated by
   `PushSXY(s32(Sx >> 16))` (DuckStation `gte.cpp:786`) — **truncation, no
   rounding**. v7 snaps with `floorf` (the old build rounded), x on the
   engine 320-column raster (`fb_w/320`) and y on the 240-row raster
   (`fb_h/240`). `--modern` still opts out; `P` toggles.
4. Engine constant fix: preset 1 `worldLightIntensity` = Q12(1.1f) = **4505**
   (was 4504); enum-0 fog-off quads use the flat `tintEff` color
   (`__block19CC`) instead of neutral 128.

Night sequence, fog, snow, camera (camtrack 1:1), alpha/STP blending and
all deterministic renders are **unchanged from v6** — the v7 night
flashlight `--shot` output is byte-identical to the v6 reference, and the
v7 `--modern` day render is byte-identical to a freshly-built v6 binary
(`verify.sh` pins both).

## v6 — FLASHLIGHT ANCHOR & VISIBILITY (historical)

v6 implements the controlled non-verbatim exception for the GLTF flashlight:

1. **Light origin = the camera position EXACTLY** (user directive): the
   engine's 0.31m hand offset (`Game_FlashlightAttributesFix` → torso bone +
   `(-0.08, -0.28, +0.12)`) is documented but NOT applied. The origin tracks
   the active `camdat.json` camera every frame. Beam direction stays engine
   verbatim (view-forward tilted 15 degrees DOWN; `func_8003F4DC`).
2. **Fixed-camera session-clock bug fixed**: under `--cam`, v5 froze the
   playback clock — the flashlight ramp/snow never advanced and `--cam
   --shot` looped forever. The engine runs `Gfx_EffectsUpdate` on the game
   clock regardless of the camera pose source; v6 does the same.
3. **Illumination is fully working and measured** (flashlight ON minus OFF,
   same camera, `reference_shots/`):

   | Camera | Height over walkway | Brightened px | Gain > +30 | Max gain |
   |---|---|---|---|---|
   | camdat street-cam (y=3.43) | 3.28 m | 7-20% | 0.7-1.4k | +74..+107 (fence/wall bases) |
   | `input/camdat_eye.json` (y=1.75) | 1.60 m | 27-33% | 11-14k | +91..+99 (road pool) |
   | road-level fixed cam (`--cam`) | 1.45 m | **51.3%** | **63k** | **+156 (road pool)** |

   **Why the pool can look invisible on a high track**: the engine's
   `func_80057658` falloff is ~1/d^2 in the light value (the GTE fake
   perspective divide over |delta|^2 with `SetGeomScreen(16)`), with the
   verbatim fog-off rule `light < 8 -> BLACK` and preset 3's `wLI = 0`
   (flashlight ON trades ambient for the beam — `map_info.c` [3]). The
   engine anchors the light at **Harry's torso bone ~1.2-1.5 m above the
   street** (`player_control.c:6938` roots the skeleton at the grounded
   player position), so the beam's floor ellipse lands 4-6 m ahead — inside
   the visible range. A camera track at 3.43 m pushes the same ellipse to
   ~12 m, where the authentic value is ~13/255: the core goes black and only
   the beam periphery (fence/wall bases) glows. That is engine-exact
   behavior for a high camera, not a broken light. To see the classic pool:

       ./fog_poc --camdat input/camdat_eye.json --night --flashlight

   (`input/camdat_eye.json` = the supplied track at eye height; VLM verdict
   on that view: **9/10 — "bright elliptical pool on the road, fence and NO
   OUTLET sign clearly illuminated"**.) For the pool to appear on a
   3.43 m track the anchor must drop to the engine's actor height (~1.3 m
   above the street) — a constant that exists only in Harry's actor model
   binary (absent from the decomp repo and the room-only GLB), so it is NOT
   invented here; see AUDIT.md v6 for the full analysis and options.

## What it renders

* **Room**: `THRF9FD.glb` — loaded straight from the GLB at runtime (embedded
  PNG textures decoded with a built-in inflate; **nothing is extracted from
  the GLTF to external files — the room renders purely through the GLTF
  pipeline**). The GLB contains the full room, tree leaves included — they
  render because they are in the data (the old PoC's pre-extractor silently
  dropped them; nothing is added or removed here).
* **Camera**: the `camdat.json` track — the **complete camtrack.html reference
  implementation**: `evalTrack()` for **all 8 track types** — line / circle /
  curve (64-sample Catmull-Rom chord table + monotone cubic Hermite
  Fritsch-Carlson refinement) / fixed / **polyline** (exact straight-segment
  walk, piecewise-constant tangent) / **spiral** (radius+height interpolation,
  analytic d(pos)/df tangent) / **zigzag** (auto-generated lawnmower waypoints,
  same segment walk as polyline) / **figure8** (Gerono lemniscate bounded to
  one full 360-degree period) — all look modes (path / normal / point /
  fixed YXZ Euler / **center**), all loop modes, the per-type lookMode/loopMode
  defaults and every `sanitizeTrack` clamp, plus the live **turn filter**
  (`updateTrackCam` / `turnStepLimited`: bounded-rate **160 deg/s slerp**
  toward the exact track orientation while playing; snap on seek / track
  jump / pause) and the editor's exact playback timing
  (`t += min(dt, 0.1) * rate`, `t %= cycleDuration`). At the pingPong
  turnaround the camera performs the authentic smooth 180-degree sweep
  (measured at exactly 160 deg/s), and the snow box follows the *live*
  (turn-filtered) view exactly like the engine samples its real view camera.
  The per-model `fogon` / `nighton` / `flashlighton` camdat flags are parsed
  and reported (camtrack.html defines them as consumer data). v10:
  `nighton`/`flashlighton` pick the BOOT env pair/flashlight; `fogon` is
  informational ONLY — the engine has no global fog flag, so fog presence
  follows the current preset's `field_E` (world_effects.c:881) exactly.
  New-camera audit: `--cam-dump F[,N]`
  dumps `evalTrack` over one cycle as CSV; `--track N` selects a track.
* **Fog**: the THR outdoor preset `MAP_EFFECTS_INFOS[1]` (fogColor
  {108,100,116}, full fog at 13.5 m) applied with the engine's own math:
  `WorldEnv_FogDistanceSet` fogRamp LUT + depthShift, per-vertex fog on
  Q8 view depth, Gouraud-interpolated `Gfx_MeshDraw` path-B colors
  (`(texel*tintEff*T)>>7 + fogColor*f`), fog background clear color.
* **Snow**: `src/maps/particle.c` (map0_s00 build) 1:1 — 300 flakes,
  SnowType_Heavy, 30 Hz ticks, camera-anchored +-5 m L1 box 3 m ahead,
  spawn y=-6 m (engine y-down), random-walk drift, world anchoring, box
  wrap + one-frame hide, ground contact via a `Collision_SurfaceGet`-
  equivalent probe, rest fade, RNG LCG + consumption order. The flake
  sprite + 8 distance-gradient CLUTs from the original `BG_ETC.TIM` are
  **embedded in the executable** (`src/snow_tim_data.h`, generated by
  `tools/extract_snow_tim.py`, cross-checked byte-identical against the
  previously verified baseline).
* **PSX wobble** (authentic GTE vertex jitter) — **keybind `P`, DEFAULT ON**: the PS1 GTE truncates its fixed-point projection to 16-bit INTEGER screen coordinates (`PushSXY(s32(Sx>>16))` — DuckStation `gte.cpp:786`; no rounding), so vertices land on the integer raster of the console's **320x224 progressive** framebuffer (`SCREEN_WIDTH` / `FRAMEBUFFER_HEIGHT_PROGRESSIVE`, game.h; the drawing clip AND display window are both 224 rows — screen_draw.c:45-46) and snap between pixels as the camera moves — the classic PS1 polygon wobble. When enabled (the default), projected vertices truncate onto that same engine raster (x on the fb_w/320 grid, y on the fb_h/224 grid, mapped to the render resolution; at the native default this is exactly 1:1). Affine texture mapping + 15-bit framebuffer quantization are part of the same authentic GTE/GPU package (the PS1 always does all three together). `--modern` opts out.

## Target-hardware constraint (RK3326 / Mali-G31 / GL 2.1 / GLES 1.0)

The renderer is a **pure-C software pipeline that uses no OpenGL at all** —
presentation is GDI on Windows, SDL2/X11 (dlopen, optional) on Linux. It
therefore cannot depend on any GL 3+ core-profile feature and runs anywhere,
including GLES-1.0-only targets. All engine math is integer/fixed-point
exactly like the PS1 GTE/GPU. **v21: the default render resolution is the
engine-native 320x224** (SCREEN_WIDTH / FRAMEBUFFER_HEIGHT_PROGRESSIVE,
game.h; Screen_Init(SCREEN_WIDTH, false) at game_main.c:82 — accuracy over
framerate/resolution). Performance is fill-rate bound: 320x224 at ~150 fps
on a fast x86 core; the old 640x360 16:9 presentation remains available as
a NON-ENGINE mode (`--res 640x360`, ~48 fps).

## Build

Linux / POSIX (no dependencies beyond libc/libm):

    make

Windows (cross-compile — either classic MinGW-w64 or Zig):

    make -f Makefile.mingw          # needs x86_64-w64-mingw32-gcc
    # or with Zig (bundled MinGW-w64 CRT, no toolchain install):
    zig cc -target x86_64-windows-gnu -O2 -std=c99 \
        -o fog_poc.exe src/fog_poc.c -luser32 -lgdi32

The Windows exe imports only USER32 / GDI32 / KERNEL32 plus the Windows
Universal CRT (an OS component on Windows 10/11) — standalone, no external
DLL downloads.

## Run

Put `THRF9FD.glb` + `camdat.json` next to the executable (or in `input/`),
then run with **no arguments** — the realtime window opens and plays the
camtrack camera live against the engine-exact fog + snow:

    ./fog_poc                                          # realtime window (native 320x224)
    ./fog_poc --window-size 1920x1080                  # bigger window
    ./fog_poc --res 640x360                            # NON-ENGINE 16:9 mode
    ./fog_poc --modern                                  # opt OUT of the wobble
                                                       # (default: PSX look ON)
    ./fog_poc --nofog --cam x y z tx ty tz 60          # live fixed camera

Realtime window keys: `ESC` quit · `SPACE` pause · `R` restart · `+/-` speed
x0.125–x8 · `Left/Right` scrub 1 s · `N` **night/nightmare cycle** ·
`F` flashlight · `M` fog · `B` snow · `P` **PSX wobble** · `S` screenshot.

Deterministic stills (bit-exact, VLM-verifiable). Each shot simulates a
60 fps playback session from t=0 — turn filter and 30 Hz snow included —
then renders, so it is byte-identical to the realtime benchmark path:

    ./fog_poc --shot t=10.5,file=shot.png
    ./fog_poc --benchmark --duration 6 --fps 60 --save-final f.png
    ./fog_poc --shot t=6,file=g.png                    # == f.png (bit-exact)

    ./fog_poc --modern --shot t=10.5,file=clean.png     # without wobble
    ./fog_poc --nosnow --shot t=5,file=plain.png       # snow off
    ./fog_poc --tim-file BG_ETC.TIM --tim 0            # inspect a TIM page
    FOGPOC_SNOWDUMP=dump.txt ./fog_poc --shot t=6,file=f.png   # flake dump

## Determinism

Rendering is fully deterministic: two runs with the same arguments produce
byte-identical PNGs, and the realtime benchmark's `--save-final` frame is
bit-identical to `--shot` at the same track time (verified). Live-window
frames follow wall-clock dt like the camdat editor's rAF loop; the
deterministic paths simulate the same session at a fixed 60 fps.

## Engine math — audit trail

See `AUDIT.md` for the function-by-function mapping to silent-hill-decomp
and to camdat.html, including the full list of documented adaptations.

## Known not implemented (by design)

* **Tree leaves as particles** — the leaves are baked into the GLB and render
  through the GLTF pipeline; no particle system is added on top.
* **Rain / windy snow variants** — code paths replicated but inert: this
  map's engine preset is non-windy SnowType_Heavy (wind stays 0,
  engine-identical).
* **Flashlight / point-light paths** (`g_WorldEnvWork.field_0 != 0`) — not
  active for the THR outdoor preset.
* **Fog particle sprites** (drifting mist) — the engine spawn table lives in
  the map overlay script, which is not part of the room rip.

## v4 — Night Sequence + Flashlight (engine-verbatim)

* **Night Sequence (keybind `N`, `--night` / `--day`)** — the env preset-pair
  system from `world_effects.c`: the day street is the map-default pair
  `{1,1}` (`WorldEnv_MapPresetSet` case 1 → `D_800A9F80`); pressing `N`
  performs the authentic night transition `Gfx_MapEnvSet(6, 3)` — the exact
  call the street's event script makes (`map0_s01_events.c:920`). Preset 6 =
  the dark street (fogColor **(0,0,0)**, 14 m black fog, worldLightIntensity
  0.44, blue-ish tint 0.4/0.7/1.0); preset 3 = the flashlight env
  (spotLightIntensity 1.3, fog **off**, enum-1 per-vertex lighting). The
  switch is INSTANT (engine behavior — the smooth blend driver is the
  load-screen path only), and the `EnableBrightness` screen lift
  (+14/channel with the default config 3) is applied at night.
* **Flashlight (keybind `F`, `--flashlight` / `--no-flashlight`)** — the
  original **per-vertex** PSX flashlight, NOT a modern spotlight:
  * `func_80057658` (the MESH light): per-vertex GTE emulation —
    rows `[beam*intensity, normal<<5, delta-Q8]`, `rtps` with
    `SetGeomScreen(16)`, the **hardware UNR reciprocal division** (257-entry
    table, exact algorithm), `stdp` depth-cue via `DQA = Q12_TO_Q4(spot)`,
    value = `((sx'*sy' + sy'*(dp>>4))>>5) - 16` clamped, `+ worldLight>>5`,
    `+ min(sx'/2 + dp/4, 48)`, clamped to the preset's max brightness.
  * `DPCL` (the Gfx_MeshDraw enum-1 vertex color): `in_MAC=(tint*light<<5)<<4`,
    the two-step IR interpolation toward FC=(0,0,0) — exact GTE semantics
    (sf=1), giving the authentic overbright hotspot (lit surfaces reach
    ~2x tint).
  * the 0.25 s on/off **fade** (`flashlightIntensity` ±`dt*4.0`) blends the
    whole atmosphere between the two night presets (`func_8003F838`:
    weighted averages + `LoadAverageCol`, `field_E` transition rules, the
    fogColor/fogDistance/wLI/tint/spot sweeps, fog switching **off** at full
    intensity).
  * **engine gates kept**: the toggle is refused on envs without
    `FlashlightAllowed` (the day street — `game_sys_states.c:236`), and the
    flashlight auto-forces-off when the preset pair is identical
    (`bodyprog_effects_8005E0DC.c:650`). `camdat.json` `nighton` /
    `flashlighton` model flags set the startup defaults.
  * **snow interaction** (as the decomp does): the flake base color follows
    `func_8003EDB8` = `field_1C[isFlashlightOn].field_21` (16→48 at night,
    instant boolean flip, NOT blended). The decomp's
    `Game_FlashlightIsOn()` branches in `Particle_SnowDraw` are dead
    optimized-out code — no per-flake lighting (verified, documented).
  * documented adaptation: the engine rides the light on Harry's torso bone
    (~1 m, offsets `(-0.08, -0.28, 0.12)`, -15° tilt); the viewer has no
    player model, so the light anchors to a virtual player on the walkway
    datum (the snow system's ground datum) at the camera's XZ aiming where
    the camera looks — every offset/tilt/falloff stays verbatim, and the
    beam lands at the game-authentic ~5 m.
* **Excluded with documentation** (out of scope, engine-inactive in this
  configuration): the lens-flare/water-glint system (THR has no water zones;
  the 1-px flare dot's altitude gate fails for a camera-level light), the
  map6 cutscene darkness grid, the tint-light-overlap radial overlay (only
  for `enableTintLightOverlap` presets — not 6/3), and the event-scripted
  lightning `flashEffect`. See `worklog.md` v4 scope notes.

**Keybind change (v4)**: `F` = flashlight, `N` = night sequence (per the
task spec); the previous `F` fog toggle moved to **`M`**, the snow toggle
moved to **`B`**. CLI flags `--nofog`/`--fog`/`--nosnow`/`--snow` unchanged.

## v5 — Night Fog Deep Dive + HERO flashlight (engine-verbatim)

* **Night cycle (keybind `N`, `--night` / `--day`, `--nightpair A,B`)** — N now
  cycles through the engine's authentic night street env pairs:
  **day {1,1} → night {6,3} → nightmare {7,4} → day**.
  * `{6,3}` — `Gfx_MapEnvSet(6,3)` (map0_s01_events.c:920): the first night
    street where the flashlight is picked up. Preset 6: fog **14 m BLACK**,
    worldLightIntensity 0.44, blue-night tint 0.4/0.7/1.0. Preset 3: the
    flashlight env — **spot 1.3**, fog OFF at full flashlight.
  * `{7,4}` — `Gfx_MapEnvSet(7,4)` (map0_s02_events.c:102; the nightmare
    resume in map6_s01_2.c:479 — `Game_TurnFlashlightOn()` + `Gfx_MapEnvSet(7,4)`
    + `Game_FlashlightAttributesFix()`): preset 7 = fog **9.3 m black** (the
    THICK enveloping night — Q12(9.29987 m) verbatim); preset 4 = flashlight
    env with **spot 0.7** (the game dims the beam in the nightmare).
  * `--nightpair 7,4` starts the cycle at the nightmare pair instead.
  * The fog-on/fog-off flip at full flashlight, the 0.25 s
    `flashlightIntensity` fade, the fogColor blend and the `EnableBrightness`
    +28 screen lift are all engine-exact (`Gfx_EffectsUpdate`/`func_8003F838`).
* **Flashlight (keybind `F`)** — the original per-vertex IPD room light
  (func_80057658 + the Gfx_MeshDraw DPCL/DPCS paths), now **anchored to HERO:
  the virtual camera** (per the task spec): light pos = camera + the engine
  torso offsets (-0.08,-0.28,0.12), beam = camera-forward tilted **15° DOWN**
  (v4 had the beam tilted UP — fixed against func_8003F4DC). With fog OFF the
  engine's fog-off formula `dpcs(tint, 4096 - light<<5)` = tint·light/128 is
  used (NO fog factor — v4 applied an 8 m fog ramp there and blacked the beam
  out). The light's authentic 1/δ falloff: full ~1–2 m, ~27% at 3 m.
* **Engine-exact fog veil structure** (the v5 correction): the additive
  fogColor veil is drawn ON TOP of STP prims only (fences/foliage — glTF
  MASK/BLEND materials); OPAQUE prims fade via vertex-color modulation and
  drop at the engine's far cull (fog ? min(30.4 m, fogFar) : 30.4 m) — verified
  via addPrim head-insertion + DuckStation's linked-list DMA order. The day
  renders changed accordingly (distant geometry darkens into the fog instead
  of washing to the fog color — VLM-judged MORE authentic PS1).
* **camdat.json flags**: `nighton`/`flashlighton` boot the night env with the
  flashlight on (byte-identical to `--night --flashlight`); `fogon` is
  informational only since v10 — the fog follows the current preset's
  `field_E` exactly like the engine (v5-v9 keyed the renderer fog flag on
  `fogon || nightBoot`, which broke every day-stage boot when the camdat
  carried `fogon:false`; v4 tied the whole pipeline to fogon and rendered a
  bright scene when it was false).
* The new camdat's line track (pingPong, 49.88 s) turns around at t≈24.94 s —
  during the 160°/s sweep the camera briefly looks off the end of the street
  (the model ends at z=120.05; the camera reaches z=120.69) — engine-faithful.

**Keybinds (v5)**: `N` night/nightmare cycle · `F` flashlight · `M` fog ·
`B` snow · `P` PSX wobble · `S` screenshot (unchanged from v4 otherwise).

---

## Repository layout

| Path | What it is |
|---|---|
| `src/fog_poc.c` | the engine — single-file C99 software rasterizer (v23) |
| `src/*.h` | embedded engine data (snow/rain TIM sprites, font, sine table) |
| `input/` | the GLB + camdat camera tracks the renderer loads |
| `tools/` | dev toolchain: `ipd2gltf.py` (IPD→GLB converter), `camtrack.html` (CamTrack Editor v13) + audit/regression tooling |
| `reference_shots/` | deterministic reference renders for regression comparison |
| `CHANGES_v*.md` | per-version change log |
| `MODES_GUIDE.md`, `AUDIT.md`, `CUTSCENE_LOADER_DESIGN.md` | mode inventory, engine audit trail, cutscene loader design |

### Tools (this repo's additions)

- **`tools/ipd2gltf.py`** (v11/r2) — converts Silent Hill 1 (PS1) `.IPD` room
  files to per-room glTF 2.0 (.GLB), rewritten against the full
  [shdecompilations/silent-hill-decomp](https://github.com/shdecompilations/silent-hill-decomp)
  decompilation. Run `python3 tools/ipd2gltf.py --help` for options.
- **`tools/camtrack.html`** — CamTrack Editor v13, the `camdat.json` recorder
  (day/night environments, per-track weather). Open it directly in a browser;
  camera tracks export as JSON the renderer consumes.

## CI / Releases

`.github/workflows/poc.yml` runs on every push/PR/manual dispatch:

- **Linux build** (`make`) + headless smoke test — `--shot` renders a
  deterministic PNG, proving the binary actually runs, not just links.
- **Windows build** cross-compiled with Zig (imports only
  USER32/GDI32/KERNEL32 + the Universal CRT — the Makefile.mingw option B
  command, no toolchain install needed).

Push a tag `v*` (e.g. `v23.0`) to publish a **GitHub Release** with
`fog_poc` (Linux), `fog_poc.exe` (Windows) and a source tarball attached.
Releases are used instead of workflow artifacts — release assets do not
count against the Actions artifact storage quota, and they give
downloadable, checksummed, permanent builds for testing.
