# SH1X — Silent Hill 1 IPD→glTF extras schema v2.0

Status: DRAFT (this session). Implementation: `tools/ipd2gltf.py` emits it.

## Goal

Carry **every bit of the source IPD (+ embedded PLM) data** in the GLB so:

1. A **stock glTF viewer** renders the room (with the usual z-buffer artifacts —
   documented, unavoidable in pure glTF; geometry is emitted at authored
   positions with NO separation offsets).
2. A **special software renderer** (fog_poc / wallpaper / camtrack) reads
   `extras.SH1X` and reproduces the PS1 engine's painter's-algorithm composite
   **byte-identically** to the game's necessary inputs — no name tables, no
   hacks, no inferred values: the renderer logic matches
   `shdecompilations/silent-hill-decomp` exactly.

## Placement

```
scene.extensions.SH1X (top-level scene extension on scene 0? NO — glTF forbids
                       custom top-level keys; we use scene.extras.SH1X)
```

glTF 2.0 allows `extras` on: scenes, nodes, meshes, materials, accessors...
We use:

- `scenes[0].extras.SH1X` — the room-level verbatim container (header,
  modelInfos, modelBuffers incl. instances/billboards/subchunkRanges,
  subcell table, modelOrder, collision, embedded PLM, texture list,
  file identity). **Byte-identical** reconstruction is possible from this
  node alone.
- `nodes[i].extras.SH1X` — per-instance references for renderer convenience:
  `{ room: <room name>, buffer: <idx>, instance: <idx>, object: <name>,
     plm_object: <idx into SH1X.plm.objects>, ot_base: <int>,
     field_B_1: <int>, add_seq: <int — global engine add order> }`.
  (Derived data, *redundant* by design: every value is derivable from the
  scene-level container; the C engine's loader is simpler this way.)
- `meshes[i].extras.SH1X` — per-mesh engine view: `{ plm_object, plm_mesh,
     vertexOffset, normalOffset, flagsByte }` + `packs` array (see below).

## Scene-level container (the verbatim payload)

```
SH1X = {
  schema: "SH1X",  version: 2,
  room: "HP0003",
  file: { name: "HP0003.IPD", size: 47104, sha256: "..." },

  header: {          // s_IpdHeader, FILE bytes 0x00..0x54 (84 bytes)
    magic: 20, isLoaded: 0, chunkX: 0, chunkZ: 3,
    lmHdrOff: 4372,                    // 0x1114
    modelInfoCount: 9, modelBufferCount: 9, modelOrderSize: 54,
    padC: [0,...8 zeros],              // bytes 0x0C..0x14, verbatim
    modelInfosOff: 0x188, modelBuffersOff: 0x218,
    textureCount: 0,                   // u8 @0x1C
    subcellTable: [ [ [start,count] x5 ] x5 ],   // bytes 0x1D..0x51 verbatim
    modelOrderOff: 0x47C,
    raw: "<base64 of the 84 header bytes>"
  },

  modelInfos: [ {     // 9 x s_IpdModelInfo (16B each), verbatim
    isExternal: 0, pad: [0,0,0], name: "BM11_FAR", modelHdrPtr: 0,
    raw: "<base64 16B>"
  } ],

  modelBuffers: [ {   // 9 x s_IpdModelBuffer (24B), verbatim
    modelInstanceCount: 1, billboardInstanceCount: 0, subchunkCount: 1, pad: 0,
    minX: 5427, maxX: 5529, minZ: 3481, maxZ: 6040,     // raw s16 Q7.8
    modelInstancesOff: 0x2F0, billboardInstancesOff: 0x314, subchunkRangesOff: 0x314,
    instances: [ {     // 36B each, verbatim
      objIdx: 0, rt: [4096,0,0, 0,4096,0, 0,0,4096], pad: 0,
      t: [5939, -461, 5530],            // s32 Q8 raw
      raw: "<base64 36B>"
    } ],
    billboards: [ { offset: [s16 x3], idx: s8, pad: s8, raw } ],  // 8B each
    subchunkRanges: [ { minX,maxX,minZ,maxZ, raw } ],              // 8B each
    raw: "<base64 24B>"
  } ],

  modelOrder: [0,1,2,...],            // u8 x modelOrderSize, verbatim

  collision: {          // s_IpdCollisionData @0x54, verbatim
    positionX: 0, positionZ: 30720,   // s32 Q23.8
    counts: {splitV: 75, surf: 9, poly: 75, cyl: 0},
    splitVertices: [ {x,y,z, raw} x75 ],       // s16 Q7.8, 6B each
    surfaces: [ { offset:[3], floorType, disableHeight, surfaceCacheIdx,
                   triggerFlagIdx, slopeGradientX, slopeGradientZ, raw } x9 ],
    polygons: [ { offsetX, offsetY, offsetZ (Q7.8 decoded), triggerFlagIdx,
                   splitVertexIdx0/1, surfaceIdx0/1, raw } x75 ],  // 10B each
    cylinders: [ {...} x0 ],
    cellSize: 512, cellCountX: 20, cellCountZ: 20,
    shapeAllocs: [ {shapeLutIdx, surfaceLutIdx} x401 ],
    shapeLut: [u8 x226], surfaceLut: [u8 x25],
    shapePassCounter: 0, stampBuffer: [u8 x256],
    raw: "<base64 of the whole collision block>"
  },

  plm: {              // the embedded LM (s_LmHeader), verbatim
    magic: 0x0630, version: 6, isLoaded: 0,
    materialCount: 3, modelCount: 11,
    order: [0..10],
    materials: [ { name: "HP1F012", texPtr: 0, fieldC:0, fieldD:0,
                   fieldE:0, fieldF:0, field10:0, field12:0,
                   uv14: [0,0], uv16: [0,0], raw: "<base64 24B>" } ],
    objects: [ {      // s_ModelHeader 16B, verbatim
      name: "NULL", meshCount: 9, vertexOffset: 0, normalOffset: 0,
      flagsByte: 0,       // bit0 B0, bits1-3 B1, bits4-5 B4, bits6-7 B6
      meshes: [ {     // s_MeshHeader 24B, verbatim
        primitiveCount, vertexCount, normalCount, unkCount3,
        packs: [ {   // s_Primitive 20B, VERBATIM — the renderer's raw input
          u0,v0, cba, u1,v1, b6, b7, u2,v2, u3,v3,
          faces: [4], normalSlots: [4],
          // v40 audit (D-F5): texIdx/stp decode from B7, not b6 — the
          // decomp's s_Primitive bits1 union (model.h): byte 0x6 = field_6
          // (runtime-only, set to s_Material::field_E at load), byte 0x7 =
          // materialIdx:7 | isTransparent:1 (the u16 flags bit 15 the
          // engine tests, bodyprog_80056D8C.c:850/1152). The ripper has
          // always parsed b7 (ipd2gltf.py _Primitive b7 comment); b6 is
          // 0x00 in ALL 4,771 packs of the shipped archives — the old
          // doc decode bound material 0 for 737/1310 HP0003 packs.
          texIdx: b7&0x7F, semiTransparent: (b7>>7)&1,
          raw: "<base64 20B>"
        } ],
        vertsXY: [ [s16,s16] xN ], vertsZ: [ s16 xN ],
        normals: [ {nx,ny,nz,slotCount} xN ],
        slots: [ u8 xN ],
        raw: "<base64 24B>"
      } ],
      raw: "<base64 16B>"
    } ]
  },

  textures: [ { name: "HP1F012", tim: "<base64 of the whole TIM file>",
                clutX:.., clutY:.., ... } ],   // the referenced TIMs verbatim

  render: {          // derived, redundant, for consumer convenience (verified
                     // to be pure functions of the verbatim data above)
    otShift: 1,
    otBaseOfFlagB1: {0:2, 1:0, 2:4, 3:33, 4:66, 5:99},   // func_800571D0
    mapCell: 10240, scale: 1/256,
    farCullQ8: ...,   // engine far plane
    addOrder: "buffers(file order) -> instances -> billboards; meshes in PLM order; packs in order"
  }
}
```

## Coverage matrix (every IPD/PLM byte → SH1X field)

| Source bytes | SH1X location | Verbatim raw | Decoded fields |
|---|---|---|---|
| IPD header 0x00–0x54 (84B) | header | ✔ raw b64 | magic, isLoaded, chunkX/Z, lmHdrOff, counts, padC[8], modelInfosOff, modelBuffersOff, textureCount, subcellTable[5][5][2], modelOrderOff |
| modelInfos 9x16B | modelInfos[] | ✔ | isExternal, pad3, name, modelHdrPtr |
| modelBuffers 9x24B | modelBuffers[] | ✔ | counts, AABB Q7.8 raw s16, offsets |
| instances 9x36B | modelBuffers[].instances[] | ✔ | objIdx, rt[9], pad, t[3] |
| billboards n x8B | modelBuffers[].billboards[] | ✔ | offset[3], idx, pad |
| subchunkRanges n x8B | modelBuffers[].subchunkRanges[] | ✔ | minX/maxX/minZ/maxZ |
| modelOrder 54B | modelOrder[] | ✔ (array) | — |
| collision header 0x54–0x88 (52B) | collision | ✔ (inside raw) | posX/Z, counts, offsets, cellSize, cells, LUT sizes, passCounter |
| stampBuffer 256B | collision.stampBuffer | ✔ | — |
| splitV 75x6B | collision.splitVertices[] | ✔ | x,y,z |
| surfaces 9x12B | collision.surfaces[] | ✔ | offset, floorType, disableHeight, cacheIdx, trigIdx, gradients |
| polygons 75x10B | collision.polygons[] | ✔ | offsets, trigIdx, split/surface indices |
| cylinders n x10B | collision.cylinders[] | ✔ | floorType, disableHeight, trigIdx, offset, radius |
| shapeAllocs 401x4B | collision.shapeAllocs[] | ✔ | lut index pairs |
| shapeLut 226B | collision.shapeLut | ✔ | — |
| surfaceLut 25B | collision.surfaceLut | ✔ | — |
| PLM header 20B | plm | ✔ | magic, version, counts, offsets |
| PLM order | plm.order | ✔ | — |
| materials 3x24B | plm.materials[] | ✔ | all 9 fields incl. texPtr |
| objects 11x16B | plm.objects[] | ✔ | name, meshCount, vertexOffset, normalOffset, flagsByte |
| meshes n x24B | plm.objects[].meshes[] | ✔ | counts + 5 offsets |
| packs n x20B | ...meshes[].packs[] | ✔ | u/v x4, cba, b6, faces[4], normalSlots[4] |
| vertsXY n x4B | ...meshes[].vertsXY | ✔ | — |
| vertsZ n x2B | ...meshes[].vertsZ | ✔ | — |
| normals n x4B | ...meshes[].normals[] | ✔ | nx,ny,nz,slotCount |
| slots n x1B | ...meshes[].slots | ✔ | — |
| TIM files | textures[] | ✔ whole-file b64 | parsed dims for reference |

**Nothing is dropped, reinterpreted, or replaced.** Unknown/pad bytes ride along
in the `raw` base64 blobs AND as explicit arrays where their layout is known.

## Renderer contract (the consumer side — decomp-verbatim)

1. Read `SH1X` from `scenes[0].extras` (fallback: per-node extras).
2. Rebuild in memory: `modelInfos`, `modelBuffers` (with instance transforms),
   `modelOrder`, the subcell table, and the PLM object/mesh/pack tables.
3. Per frame (decomp `WorldMap_Draw`):
   - subcell (z,x) from camera → range `[start, start+count)` of modelOrder;
   - for each buffer index in range: `WorldMap_SubchunkVisibleCheck`;
   - for each instance: set `modelCoord.workm = rt,t` (+chunkEdge), walk
     meshes; `Gfx_MeshDraw` semantics:
     - quad depth = MAX of 4 vertex SZ (Q8), `<=32→32`, `>far→skip`;
     - bucket = `ot_base + (maxZ >> 3)` (otShift 1);
     - backface cull = dual gte_NormalClip test;
     - semi-transparency from pack b6 bit 7 (engine bit15 of the u16);
   - billboards after the buffer's instances.
4. OT walk far→near, LIFO within bucket. No z-buffer anywhere.

## v33 additions (S20)

### `sh1x["env"]` — the room's ORIGINAL environment (optional)

Present on v33+ room GLBs. Resolved at rip time from the decomp map
overlay headers (`src/maps/mapN_sMM/header.c` field_16/field_17 — the
original data) + `MAP_INFOS` flags + the `WorldEnv_MapPresetSet` switch
(effects.c:220-267) + the `D_800A9F80..A98` table (effects.c:22-28).
Both presets are the verbatim `WORLD_ENV_PRESETS[21]` (map_info.c:8-387)
— decoded floats (Q12 macros evaluated) + 3-component colors, with the
raw enums alongside the labels (`fogModeRaw`/`lightModeRaw`).

```
"env": {
  "presetIdx0": 7, "presetIdx1": 4,     // the pair (off / flashlight-on)
  "field16": 2, "field17": 0,           // the map header's own fields
  "weather": "none",                    // field_17 as the boot recipe
  "mapType": "SU", "mapFlags": "TwoActiveChunks|Interior",
  "overlay": "MAP1_S02",
  "preset0": { ...full preset... }, "preset1": { ... },
  "src": "<the derivation citation>",
  "contested": true,                    // ONLY when the room cell is
  "envAlternates": [ ... ]              // claimed by overlays with
                                        // different field_16 (floors
                                        // share cells — 17 of 493 rooms)
}
```
Consumers boot `presetIdx0/1` by default (the PoC v33 + the wallpaper
v10.2 do; CLI/camdat envs still override). `contested` rooms: the
primary is the share-weighted pick — offer the alternates if desired.

### material `extras.SH1X.waterLive` — the live DR_WAVE tile

The sewer IPDs carry a material named `"DWAVE"`; the engine redirects
it at EVERY chunk load (`WorldMap_ChunkPropertiesSet` →
`func_8008E4EC`, lens_flare.c:497-502 + map.c:1167-1186) to tpage 13
(x=832) — the region `func_8008E5B4` rewrites per frame (the 32x32
two-quad composite at (832,224)). The ripper flags such materials:

```
"materials[i]": { ..., "extras": { "SH1X": { "waterLive": true,
  "src": "func_8008E4EC lens_flare.c:497-502 + ..." } } }
```
The PoC v33+ samples the ANIMATED tile for these materials (u/v wrap
mod 32); other consumers keep the static art (no-op contract).

## v45 additions (S22 — the water-texture audit)

The v33..v44 water encoding was BROKEN for every non-PoC consumer: the
MIZ floor prims' engine UVs are 15-bit page-texel coords (u 0..31,
v 224..255 — the 32x32 live tile at tpage base (832,0)), but the ripper
normalized them against the DR_WAVE sheet (128x64) — `v` landed at
3.5..3.98, OUT of glTF range, and the material texture was the raw
sheet decode. v45:

### the DWAVE material texture = the LIVE TILE (32x32)

`DWAVE_TILE0` — the ctr=0 composite of `func_8008E5B4`'s two quads
(exactly the first-frame tile the engine builds; byte-verified against
the PoC's engine-exact composite). The floor prims' `TEXCOORD_0` are
now TILE-relative: `(u/32, (v-224)/32)` — in [0,1] like every other
material. The old GLBs' UVs are distinguished by the extras: the v45
material carries the `"floor"` spec (below) — its absence marks the
legacy sheet-normalized form.

```
"materials[i]": { ..., "extras": { "SH1X": {
  "waterLive": true,
  "tileImage": "DWAVE_TILE0",
  "tile":   { "content": "...", "regen": "..." },
  "floor": {
    "draw": "func_80059E34 arg0==1 ...", "tpage": "(prim->u1&0x1FFFFF)|(0x140<<16)",
    "mode": "15-bit DIRECT color", "abr": "B-F SUBTRACTIVE",
    "flatColor": [56,56,56], "otBucket": 640, "fogVeil": "none",
    "farCull": "MIN(Q8(7.61) << (otShift+2), fog.farDistance)",
    "uvUnits": "engine prims: page-texel u 0..31 / v 224..255; glTF TEXCOORD_0 = (u/32, (v-224)/32)"
  } } }
```

### `envEffects.waterRefract` — the full DR_WAVE payload

Every DR/DRU room's `envEffects` block now carries the verbatim
DR_WAVE.TIM: `"pixels"` (b64 of the 4096 4bpp img_data bytes — the same
encoding as `SH1X.waterTex`), `"clut"` (the 2 rows, 16 u16 each), the
VRAM upload rects (`Fs_QueuePostLoadTim` + the `D_800A908C` descriptor),
and the `liveTile` spec: `vramRect [832,224,32,32]`, the two layer
windows (poly[0] opaque `u 0..32, v (ctr>>1)&0x1F..+32`; poly[1] ABR-1
additive `u ((ctr+1)>>2)&0x1F..+32, v 8..40`), the ctr advance rule
(`D_800AFDAC` ++ per frame with dt != 0 while the light stands inside a
water zone) and the STP note (every CLUT entry >= 0x8000 -> every
composite texel STP-set — only blue-field saturation bA+bB>31 clears bit
15, unreachable by the shipped art). Consumers regenerate the animated
tile from this payload alone — no hardcoded asset needed (the PoC v45
overrides its compiled-in defaults with it; absent = the defaults).

## v46-2 additions (S24/V47 — the field_B_4==2 additive-water class)

The corpus sweep (every IPD embedded PLM + every archive) found the
THIRD water-family class the v45 audit missed: objects with
`s_ModelHeader` byte-11 `field_B_4 == 2` — the engine dispatch
(`func_80057090`, bodyprog_80056D8C.c:136-164) sends them to
`func_80059D50(2)` -> `func_80059E34` **case 2** (:1469-1471):
`packedColor 0x2E808080` (semi ALWAYS ON, flat 128,128,128 = UNITY
modulate), tpage `(prim->u1 & 0x1FFFFF) | (0x20<<16)` (the pack's own
4bpp page X bits | bit 5: **ABR-1 ADDITIVE**, page Y = 0,
`gpu_types.h:158-161`), z-sorted OT bucket
`tag[MAX vertex SZ >> (otShift+2)]` (:1552-1559 — the arg0==2/3 branch,
NOT the fixed 640). Corpus: APU0002 `DRL2_ILI`, RSU01FF `FLOOR4_I`,
SC00FF `G_HIDE_I`/`R_HIDE_I`, SPU0401 `REF_NEAR` (5 objects, 4 rooms).

### material `extras.SH1X.waterAdd` — the additive-water class

```
"materials[i]": { ..., "alphaMode": "BLEND", "extras": { "SH1X": {
  "waterAdd": true,
  "floor": {
    "draw": "func_80059E34 arg0==2 ...", 
    "tpage": "(prim->u1 & 0x1FFFFF) | (0x20<<16) — own bits 0..4 | bit5",
    "mode": "4-bit CLUT (tpage bits 7-8 = 0), page Y = 0",
    "abr": "B+F ADDITIVE saturating (BackgroundPlusForeground, gpu_sw_backend.cpp:171-178)",
    "flatColor": [128, 128, 128],
    "otBucket": "z-sorted: tag[MAX vertex SZ >> (otShift+2)]",
    "fogVeil": "none", "farCull": "same as the water family (Q8(7.61) fog-gated MIN)",
    "uvUnits": "page-texel in-sheet u,v; glTF TEXCOORD_0 = (u/tim_w, v/tim_h) — STANDARD normalization"
  } } }
```

- The pack's own `stp` bit is NOT consulted on this path (0x2E
  unconditional); the per-texel blend gate is the CLUT entry's STP bit
  (gpu_sw_backend.cpp:139-156) — exactly what the `_STP` texture
  variant's alpha marks. So the class export = the stp=1 decode +
  BLEND for EVERY pack of the object, stp=0 packs included. A CLUT row
  with no STP entries yields has_alpha=false -> OPAQUE (engine-exact:
  no texel blends — verified: SPUM103F row 3 = 0/16 STP, so REF_NEAR
  draws fully opaque in the engine).
- The UV basis stays the STANDARD sheet normalization (verified:
  the five objects' prim UVs are all in-sheet, e.g. FLOOR4_I u
  128..255 v 0..127 on the 256-wide RSULH3 sheet).
- The static BLEND is the established ABR-approximation convention
  (the same `_STP` + alphaMode BLEND the stp=1 packs already get); the
  EXTRAS carry the verbatim engine contract for the accurate consumers.

### the DWAVE static-polish (glTF-native, contract-neutral)

The DWAVE (waterLive) material gains `pbrMetallicRoughness.
baseColorFactor [0.4375, 0.4375, 0.4375, 1]` — the glTF-native carrier
of the engine's flat modulate (0x2E383838 -> 56/128) — and the
DWAVE_TILE0 texture's sampler switches to NEAREST (9728/9728): stock
viewers now show the dark dapple at the subtract-term brightness with
texel-1:1 sampling instead of a smeared bright-gray plane. The PNG
stays the documented ctr=0 composite; the extras contract is
unchanged; the PoC ignores baseColorFactor for textured materials
(fog_poc.c:3119 — untextured-only) so its engine-exact water path is
untouched (A/B-verified: DR01FE renders byte-identical).

### the billboard leaf punch-through (comment + rule fix)

The leaf decode's punch-through rule is the FETCHED-COLOR rule
(`texture_color.bits == 0` -> not drawn, swanstation
gpu_sw_backend.cpp:124 — the same rule the room-texture decode
applies), NOT the 4bpp index-0 rule the old comment asserted. Output
identical on the shipped asset (the real window references indices
0-8 and row-2 entry 0 is 0x0000); the rule + comment are now
hardware-exact.
