# SH1X extras v3 — engine FX extensions (water / lens flare / prop anims / mapLink / userLight)

Status: DESIGN (session 10/11, 2026-11). Grounds ALL four programs (ripper
`tools/ipd2gltf.py`, PoC `src/fog_poc.c`, wallpaper `app/src/main/cpp/fog_poc.c`,
camtrack editor `tools/camtrack.html`). Extends `SH1X_EXTRAS_SCHEMA.md` v2
(the IPD/PLM verbatim container) — v3 ADDS engine FX data that does NOT live
in IPD/PLM files (it lives in decomp C tables/code), so the ripper must
hardcode-EMIT the verbatim decomp values (cited per field). Consumers must
treat absence of any v3 field as "feature off, render exactly as before"
(graceful no-op) — old v2 GLBs stay 100% supported.

THE RULE: every value below is VERBATIM from silent-hill-decomp
(file:line cited). Where the decomp stores the value in C, the ripper copies
the C value; where the decomp computes it, the consumer computes it with the
same fixed-point math. Nothing is invented.

## Scene-level container addition

`scenes[0].extras.SH1X` gains (per-room GLB mode) / each room root node's
`extras.SH1X` gains (whole-map mode — same object build_sh1x already emits):

```
SH1X = { ...,                    # v2 fields unchanged
  "version": 3,
  "envEffects": {                 # Map_EffectTexturesLoad (env_effects.c:104-169)
    "effectTexFlag": "Water" | "WaterRefract" | "Glass" | "Fire" | "Ef"
                    | "Blood" | "Fire|Ef" | null,   # per-map flag, null=None
    "tim": "WATER.TIM" | "DR_WAVE.TIM" | ...     # file to load (only when flag)
  },
  "waterZones": [                  # s_WaterZone (map.h:271-281) — ONLY DR/DRU
    {"enabled": true, "illumination": 8,           # RAW q11_4/Q4 (all 4 rows = 8,
                                                 # map_info.c:389-401); meters = raw/16
                                                 # (engine lens_flare.c:88
                                                 # Q4_TO_Q12(illum) → 0.5 m)
     "illuminationQ4": 8, "illuminationMeters": 0.5,
     "minX": -120.0, "maxX": 80.0, "minZ": -120.0, "maxZ": 40.0,
     "units": "illumination: Q4 (raw); meters = value/16 "}
  ],                               # bounds decoded Q4 meters; consumers keep
                                   # the RAW value under "illumination"
                                   # (fog_poc divides by 16 itself)
  "mapLink": {                     # WorldMap_MakeGrid (map.c:386-419) contract
    "tag": "THR",                  # 3-char area tag (MAP_INFOS row, map_info.c:515-532)
    "activeChunks": 4,             # MapFlag_One/Two/FourActiveChunks -> 1/2/4
    "isExterior": true,            # !MapFlag_Interior
    "neighbors": [                  # derived by filename-grid: tag + hexXX + hexZZ
      {"dx": -1, "dz": 0, "room": "THRF8FD", "file": "THRF8FD.glb"}, ...
    ]                               # only cells that EXIST in the grid; consumer
                                    # ALSO probes (tag + hex(dx+x) + hex(dz+z)) at
                                    # runtime so missing neighbor GLBs = no-op
  },
  "propAnims": [                   # code-driven WorldObjects (decomp map scripts)
    {"object": "FAN_HIDE", "pos": [100.0, -1.6015625, 142.8984375],  # Q12 m,
     "rot0": [0,0,0],              # then WorldObjects_Add Q8/Q10 grid (draw.c)
     "driver": "spinRng", "axis": "z", "rngBase": -180.0,
     "rngMask": 511, "chunkGate": [2,3], "sound": "Sfx_Unk1455",
     "src": "map1_s02.c:1564-1591"},   # every field verbatim file:line cited
    {"object": "FW1_BACK", "driver": "ferrisWheel", "arms": 5, ...},   # v3 catalog:
    {"object": "FAN0_HID", "driver": "fanArray", "count": 16,
     "posPerInst": [[53.2109375,-2.375,32.5], ...]}   # 16 per-instance poses
  ],                               # full catalog: ~90 animated WorldObjects
                                   # + <ripples>/<light>/<waterfall> systems
  "userLight": { ... }             # defaults only — see below; users author overrides
}
```

## 1. Water (`WATER.md` evidence)

What the engine ACTUALLY does (no geometry mirroring!):
- **THE FLOOR CONSUMPTION (v37 — `SH1X.waterFloor`)**: the DWAVE material
  redirect (func_8008E4EC, img0 `{tPage{0,13}}` ALL-ZERO ->
  Material_FsImageApply materials.c:130-160) makes the water-floor prims
  4bpp on page 13 (x 832) with **CLUT (0,0)** — the ROOM's slot-0
  palette (WorldMap_TexturesInit map.c:137-190: fullPage slot i's CLUT
  strip at (16*i,0), pixels (512+64*i,0); Texture_Get materials.c:178-222
  assigns slots in PLM material-table order; LmFilter_IsHalfPage
  map.c:1226-1241 = the 'H'-name split). The floor quads' PAGE-texel UVs
  (u 0..62, v 224..255) read the func_8008E5B4 live 32x32 patch as 4bpp
  NIBBLES: `texel(u,row) = clut15[(liveTile15[row][u>>2] >> (4*(u&3))) & 0xF]`
  (u 0..127, rows 0..31) — the 15-bit composite's nibbles indexing the
  ROOM palette. The ripper emits the palette VERBATIM as
  `SH1X.waterFloor = {clut15:[16 x u16], clutSource:"DRG04", floorUv:{pageTexel:true, patchU:[0,127], patchV:[224,255]}, src:...}`
  (only for rooms with a DWAVE material + a locally resolved slot-0 TIM;
  absent = the consumer's legacy path, graceful no-op). Texel classes
  (a semi-trans prim, DuckStation gpu_sw_rasterizer): STP-set (0x8xxx)
  → ABR-1 ADDITIVE B+F; STP-clear → OPAQUE write; 0x0000 → the hole.
  NOTE the v2/v33 pre-v37 consumers sampled a 32x32 RGB tile 1:1 with
  mod-32 wrap — WRONG scale, WRONG palette (audit W1-6).
- **Sewer shimmer (DR/DRU)** = (a) an offscreen VRAM 32x32 rect whose UV
  window scrolls: v0 = `(ctr>>1)&0x1F`, poly2 u0 = `((ctr+1)>>2)&0x1F`,
  counter ++ per non-zero dt (lens_flare.c:536-599; NTSC CLUT (224,0),
  tpage 45, SemiTrans mode-1, color (128,128,128)); (b) ONE light-glint
  quad: mirrored light position `vy = posY*2 - pos.vy`, brightness
  `sin(clamp(angle-40°, ≤90°))` → r=sin>>6, g=(sin*7)>>9, b=(sin*5)>>9,
  tpage 45 CLUT (224,1), UV 64..127 x 0..31, ±24 x ±48 px around the
  projected point, OT bucket 641 (lens_flare.c:610-681). THE GLINT IS A
  TEXTURED FT4 blended ADDITIVE (F5 = T5*C8>>7, dst5 = B5+F5 clamped) —
  subtle by engine design (≤ +6/31); the v32 untextured AVERAGE-blend
  quad was WRONG (audit W1-2/W1-3, fixed v37). It paints ON TOP of the
  caustic ring (both ride bucket 641; the engine's AddPrim chain inserts
  the glint FIRST = head = drawn LAST — audit W1-13, fixed v37); (c) the
  8-caustic ring around the light: per 45° step, g4[0] (20,18,12 / 4,4,4)
  @641 + g3[0] (24,22,12/20,18,12) @641 + semi-trans g4[1] (4,8,4/0,0,0)
  + g3[1] (8,8,4/4,8,4) @639 (lens_flare.c:683-825). Ring quad corners:
  inner r=0.2 at +1.2m fwd, outer r=2.2 at +1.5m fwd, in the light's yaw
  frame. v37 (W1-5): glint/ring/ripple prims are OT-BUCKET OCCLUDED by
  nearer opaque geometry (bucket 641 = zQ8 5000 → 19.53 m; 639 →
  19.47 m; the ripples at their own (zQ8+128)>>3 bucket).
- Gate: `!water_inhibit_f` AND the LIGHT in a waterZone box (X/Z inclusive
  bounds) AND zone.enabled (lens_flare.c:78-93, 504-523).
- **Sewer ripples (map5_s00)**: 12 RNG ripples in box x[-92.75,-91.25]
  z[7.35,8.85], y=0.5, half-size = 1.5 * t, t random-walks ±32 clamped
  [0,4095], CLUT row = 160+(r<<5), 3 rows (map5_s00.c:20-48, 89-94,
  154-157). Only when NOT (flashlightAllowed && darkness) — the CURRENT
  BLENDED preset flags (effects.h:41-58): with the sewer pair {6,3}
  flashlight-ON → preset 3 (NO Dark) → the ripples DRAW; flashlight-OFF
  → preset 6 (Dark) → skip. (The v32 gate on the Spot light mode was
  INVERTED — audit W1-1, fixed v37.) The walk runs per GAME FRAME
  (moved to the tick discipline — audit W1-4, fixed v37); the mesh's
  brightness = !(func_80055D78(Q12(-92.0),Q12(0.5),Q12(8.1)) < 129) * 8
  (the VERBATIM light probe, map5_s00.c:197 — the hardcoded 8 was audit
  W1-7, fixed v37); the spawn base Q12(7.35)=30105 truncated (W1-8);
  the sprite screen culls |x3|>200 |y3|>160 + the OT bucket bound
  (map5_s00.c:135-143 — W1-11, added v37).
- WATER.TIM/DR_WAVE.TIM VRAM: NTSC (0,13)+CLUT(224,0) (screen/data.c
  descriptors). Both sheets are embedded: DR_WAVE.TIM (dr_wave_data.h,
  v32) and WATER.TIM (water_tim_data.h, v39 — the 128x128 4bpp sheet +
  2 CLUT rows, extracted by tools/extract_water_tim.py). The waterTex
  EXTRAs (v39 ripper) OVERRIDE the compiled-in defaults at load.
  Consumers without the TIM resolve it by name through the standard
  resolver; without it the feature no-ops (same ladder as BG_ETC).

## 2. Lens flare (`LENS.md` evidence) — the flashlight glow, Spot mode ONLY

Gates (all must hold): lightMode==Spot(1); preset flag EnableLensFlare
(= flashlightLensFlareIntensity Q12(1.0) ≠ 0); light z > proj/2; on-screen
±512; ang_z ≥ 75°; NOT chase-cam; !flare_inhibit_f.
- rate easing: `now += (tgt-now)/2` or decay to 0 when occluded; occlusion =
  probe pixel == 0x7FFF (the 1x1 TILE + DR_MOVE scheme; consumer:
  framebuffer readback at the light's projected center).
- tgt = vwOresenHokan tables (pow[2]={0,1}; dist[7]={4,1.3,.9,.7,.5,.35,.2}
  over z 204..3328; angZ[7]={.15,.2,.25,.3,.35,.5,1.3} over 75°..167°),
  product, MIN 1.5 (lens_flare.c:225-250).
- Sprites (tpage 44/76 from BG_ETC.TIM — WE HAVE BG_ETC.TIM locally:
  gamefiles/thr/BG_ETC.TIM): 2 core quads UV 0..63 (grey
  `((rate+3)>>2)*40` / fixed 0x10), 3rd quad grey min(rate*2,1)*48;
  16 streaks (UV 0x20..0x3F, 0x40..0x5F, CLUT+5, grey
  `(rate*_rate)>>18` where `_rate = (cos(ang-angXY)+1.7)*(cos(ang*12+mask)+1)>>1`
  cap 1.5, ang from ang_dat[16], add_flare_ang = (-angZ>>1)+((x+y)*4)+60°,
  add_mask_ang = z*4+((x+y)*16)); 3 ghosts (CLUT+7, tpage 44/44/76, on the
  center-light line at 0.2/-0.3/1.0 scale). All SemiTrans mode-1.
- BG_ETC decode windows (NTSC CLUT_X=192, CLUT_Y=0): core quad CLUT+6,
  streak CLUT+5, ghosts CLUT+6/+7; each sprite UV window as quoted.

## 3. Prop anims (`ANIMS_MAPLINK.md` + session 17 audit evidence)

NO windmills exist in SH1 (verified zero hits — user's example is
aspirational; the catalog covers every REAL animated WorldObject found in
the 42-overlay sweep — ~95 entities, `AUDIT_F_DecompSweep.md`):
- nightmare school fans FAN_HIDE x2 (map1_s02.c:1446-1583): spin vz,
  rng = -180° - (Rng_Rand16()&0x1FF) per frame * dt, chunk gate (2,3).
- hospital fans FAN0_HID (map4_s02.c:108-165): 16 instances
  D_800ED8B0[i] ±= dt*Q12_ANGLE(90°), split at i=7, gate (1,0); the loop
  runs `objPos.vz -= Q12(5.0)` after every add (:162) so each fan sits
  5 m further -z until the next switch reset (i==0/4/7/11) — the catalog
  carries the 16 `posPerInst` poses verbatim.
- resort park rides (map6_s04_2.c): ferris wheel = FW1_BACK + FW2_BACK +
  FW3WIR_H (all 3 models added at each of the 5 arm poses, :3817-3827)
  + FWBOX1_B/FWBOX2_B cabins (5 gondolas, parity (D_800EBB34+i)&1,
  radius 11.25, 3-branch pendulum); carousel = UMA1/UMA2 horses (10
  slots; the i<6 ride UMA2_HID phase i*4096/3, i>=6 ride UMA1_HID phase
  i*2048+2048, :3619-3648), MGR_KOYA/MGR_STR_ hub+roof, SAKU2_BA gate +
  SAK_POL_ x7 fence poles (radius 7.5 ring), MGR_DRL_ + DRL2_ILI x4
  dolls (radius 0.8), all `rot.vy = master D_800ED5B6 (+offset)`.
- hospital/nowhere elevators: 36 slideDoor entries (DR1L/R, DR2L/R,
  DR3L/R per overlay — map3_s01/s03/s04/s05 + map7_s01 + map7_s02),
  shared slide code sharedFunc_800D15F0_3_s01.h:331-365 (speed 0.35,
  accel 0.8, ±vz by i-parity; map7's local levitating-door cutscene uses
  0.1/0.25, map7_s01_2.c:2082-2105; post-ride vz reset -60.9 :385-391).
- cutscene-discrete objects (driver `cutscene`, `cutsceneOnly: true`
  where engine-fresh they never draw): DOR1-4_HID dagger-room doors
  (vy +25/+58/-50/-15, map7_s02_2.c:1546-1549), BDoor1 safe door
  (-142.21° → -7.5°, map5_s02_2.c:290/311/363/388), ISU_HIDE wake-up
  chair (vz 141.0/140.8/140.95, map4_s04_2.c:340/372/396), STONE2_H
  (init pose binary-only 0x800EDF08 — no WorldObjects_Add exists),
  URA_HIDE/UNDER_HI belt riders (scrollBelt, map7_s03_3.c:8296-8342).
- town TVs (map4_s03.c:405-799): TV1-3.TIM slots + LCG noise
  `s16 = (((s32)(s2*0x7169AC35)>>3)^0xA547B39E; s2 = (((u32)(s1*0x892D719C)>>3)^0xC65A4B97)`
  channel state machine, durations `(noise>>5)+0x555`.
- MOVACHES (map5_s03_2.c:664-743): translate vz += dt*0.14.
- falling fence (map4_s03.c:1705-1734): rot.vx + vy drop (one-shot).
- non-WorldObject systems: `<ripples>` (map5_s00), `<light>` boiler
  flicker (map1_s05), `<waterfall>` drain-water particles (map1_s02,
  gates map1_s02.c:1542-1562; emitter table binary-only).
Ripper emits `propAnims[]` with VERBATIM driver params (numbers, not
names, where math is needed); consumers implement the driver families:
`spinRng|spinConst|fanArray|tvNoise|translate|doorRattle|dampedSwing|`
`kickSwing|gravityScatter|stoneChoreo|lightFlicker|sineBob|carouselSpin|`
`ferrisWheel|lissajousOrbit|slideDoor|rngWalk|fallOnce|binSpin|`
`scrollBelt` + `cutscene`/`particles`/`waterRipple` manifests, each
gated by `chunkGate`/`eventGate(+Polarity)` where the engine gates.
Positions in ENGINE meters (Q12-decoded, then the engine's own
WorldObjects_Add Q8/Q10 grid), consumers convert with the standard axis
map (x, -y, -z). Unplaced animated objects are ALSO emitted as posed
geometry nodes (one node per instance, t=0
engine pose; v48 RIP-9: the write-only `propAnimPosed` extras key is
dropped — `animInst` carries the instance identity) when the model
exists in a scanned PLM.

## 4. mapLink (`ANIMS_MAPLINK.md` B-part evidence)

Adjacency = filename grid. The ripper emits tag+chunkX/Z (already in
v2 `header`) + `neighbors` (derived at build time from the rooms it
ACTUALLY converted). Consumer rule (WorldMap_ChunkLoad, map.c:740-807):
load neighbor room GLB when camera within 4.5m Q8 of the chunk edge
(WorldMap_NextChunkLoadCheck :1045-1080) — wallpaper ONLY; PoC/camtrack
ignore mapLink (their scenes are single-room by design). If the neighbor
GLB file is absent → no load, no error, edge renders exactly as before.

## 5. userLight (FLASHLIGHT.md evidence — the engine recipe)

Defaults (all overridable per program): mode Spot(1); position follows the
CONSUMING camera (the PoC's standing directive; engine anchor torso bone +
(-0.08,-0.28,0.12) documented, unused); direction from rotation
(-15°,0,0) → `vy=-sin(rx); vx=cos(rx)sin(ry); vz=cos(rx)cos(ry)`;
intensity spotLightIntensity (1.3 flashlight preset 3); ramp
fi ±= dt*4.0/s Q12 [0,4096] (0.25s full sweep); toggle only when
FlashlightAllowed; auto-off when both env presets equal (day modes);
per-vertex math = the EXISTING sh_mesh_light_vertex (already verbatim);
day suppression = preset table has no Spot/FlashlightAllowed. Angle
distinction = normal row + SetLightSourceXYZ (already in the PoC paths).

## Consumer conformance (all four programs)

| Field | ripper | PoC | wallpaper | camtrack |
|---|---|---|---|---|
| envEffects+waterZones | emit (hardcoded decomp tables) | shimmer+glint+caustic playback | same as PoC | preview toggle |
| waterFloor (slot-0 CLUT) | emit clut15 (v37) | nibble-CLUT floor playback | same as PoC | floor preview |
| lens flare spec | emit (tables are consumer-side constants; ripper emits flag only) | full sprite draw (BG_ETC embedded like snow) | same | preview toggle |
| propAnims | emit catalog + posed nodes | 14 live driver ticks + cutscene/idle scaffolds | same | preview + authoring notes |
| mapLink | emit tag/grid/neighbors | ignored (single-room) | load neighbors ≤4.5m edge | ignored |
| userLight | emit defaults | full impl (already 90% present) | same | authoring fields |

## Version bump (task 7)

Releases move from vN tags to semver `1.MINOR.PATCH` (start 1.7.30 →
next asset-change 1.7.31); CI bumps MINOR by +1 whenever anything under
app/src/main/assets/ or the scene GLBs changes on main; PATCH for code-only
changes. android.yml gains a `bump` step; the vN tag scheme is retired.
