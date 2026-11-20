#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 ipd2gltf — Silent Hill 1 (PS1) .IPD room files → per-room glTF 2.0 (.GLB) converter.

v11 — REWRITTEN against the FULL decompilation (shdecompilations/silent-hill-decomp)
and SwanStation.  Every structural decision below cites the decomp source it was
ported from.  v10 and earlier were written before the decomp was complete; v11
replaces the remaining reverse-engineered guesses with verbatim engine logic:
the draw-order system (subcell table + model order list), the per-object PLM
render flags, and — the fix for the flat-surface flickering — the TRIANGLE
EMISSION CONTRACT that the consumer's ordering-table machinery reconstructs
(see EMISSION CONTRACT below).

v12 — OT LAYER SEPARATION (the z-buffer layering contract).  The PS1 engine
has NO depth buffer: rooms are layered by the ordering table (section bases
+ LIFO add order), and the room data USES that — same-plane overlapping
quads from different models (and 1-PS1-unit-offset shells with the engine
winner FARTHER) are authored into the IPDs and resolved deterministically
by paint order on hardware.  A depth-buffered viewer (three.js, any glTF
renderer) cannot express painter's-order ties: those surfaces flicker
per-pixel as the camera moves.  v12 adds an export-time pass that recedes
each LOSING layer along the winning plane's normal (winners keep offset 0 —
the visible skin does not move; no geometry dropped, no topology change)
so the engine's composite IS the depth-buffer composite.  Engine evidence
and the full algorithm: see the OT LAYER SEPARATION section below.


Confirmed IPD/PLM/TIM layout (offsets are file-relative unless noted; every
field cross-verified against the decomp's runtime structs — the IPD file IS the
serialized s_IpdHeader, the PLM IS the serialized s_LmHeader):
  IPD_FILE_HEADER (84 = 0x54 bytes)  [decomp: include/bodyprog/formats/ipd.h
                                       s_IpdHeader — field names in brackets]
      u8  id            @0   = 0x14  [magic = IPD_HEADER_MAGIC 20]
      u8  flag          @1   [isLoaded]
      s8  x_pos         @2   [chunkX] (map grid X; runtime copy is set from the
                                      grid lookup, which itself comes from the
                                      FILE NAME digits via ConvertHexToS8 —
                                      world_map.c:388-393; identical values)
      s8  y_pos         @3   [chunkZ]
      u32 plm_offset    @4   [lmHdr — relocated to a pointer at load]
      u8  obj_num       @8   [modelCount] (entries in the model-info list)
      u8  pos_num       @9   [modelBufferCount] (entries in the buffer list)
      u8  unk1_num      @10  [modelOrderCount] (entries in the model ORDER list)
      u8  unk2          @11  (observed 0)
      u8  pad[8]        @12  (observed 0; nonzero is reported loudly)
      u32 obj_name_off  @20  [modelInfos — s_IpdModelInfo list, 16 bytes each]
      u32 obj_data_off  @24  [modelBuffers — s_IpdModelBuffer list, 24 bytes each]
      u8  subcell_table @28  [s_IpdHeader.textureCount + unk_1D[51]: the
                              per-subcell DRAW-RANGE table.  WorldMap_Draw
                              (world_map.c:1349-1352) indexes it
                              `&textureCount + subcellZ*10 + subcellX*2` —
                              5x5 subcells (CHUNK_SUBCELL_SIZE = Q8(8.0f),
                              world_map.c:1310), each entry (u8 start, u8
                              count) indexing the model ORDER list.  The
                              engine draws ONLY the current subcell's range
                              each frame — a spatial draw-window system.]
      u32 order_off     @80  [modelOrderList — u8[modelOrderCount] of buffer
                              indices; the buffers to draw, per subcell range]
  IPD_OBJNAME_DATA (16 bytes) = s_IpdModelInfo:
      u32 flag @0 [isGlobalPlm: 0 = mesh in the embedded PLM, 1 = in
                   <PREFIX>_GLB.PLM], char name[8] @4, s32 modelHdr_ptr @12
                   (relocated at load; ignored on disk)
  IPD_POS_HEADER (24 bytes) = s_IpdModelBuffer:
      u8  obj_num  @0  [modelInstanceCount]
      u8  unk1_num @1  [field_1 = BILLBOARD ANCHOR COUNT (the field_10 list)]
      u8  unk2_num @2  [subcellCount (the subcellPositions list)]
      u8  unk3     @3  (observed 0)
      s16 minX @4, maxX @6, minZ @8, maxZ @10  [q7_8 — the buffer's world XZ
                   bounding rect, consumed by WorldMap_SubcellVisibleCheck's
                   Vw_AabbVisibleInFrustumCheck (world_map.c:1430-1433)]
      u32 data_offset @12 [modelInstances — 36 bytes each]
      u32 unk1_offset @16 [field_10 — billboard anchors, 8 bytes each]
      u32 unk2_offset @20 [subcellPositions — Q7.8 XZ visibility rects]
      unk1 = BILLBOARD FOLIAGE ANCHOR TABLE (decompilation name: IpdModelBuffer.field_10):
      unk1_num entries x 8 bytes at unk1_offset, each (s16 x, y, z, w) in Q8 world units
      (chunk-relative) = one ANCHOR for an engine-drawn camera-facing billboard cluster;
      w selects the cluster (0 -> Gfx_BillboardDraw type 1 = 12-quad tree canopy,
      1 -> type 2 = 5-quad bush).  DEFINITIVE evidence: the Silent Hill decompilation
      (shdecompilations/silent-hill-decomp) world_map.c WorldMap_Draw iterates
      modelBuffer->field_10 AFTER that buffer's instances and calls
      Gfx_BillboardDraw(1|2, vx+chunkBoundX, vy, vz+chunkBoundZ) per entry
      (world_map.c:1378-1398); billboard_draw.c D_800AE204/D_800AE4DC hold the exact
      ring geometry (radii, angles, height offsets, quad sizes), and the leaf texture
      is the real disc file TIM/BG_ETC.TIM (filetable index FILE_TIM_BG_ETC_TIM=1799,
      66 blocks = 16896 bytes in the USA filetable; auto-discovered by name like any
      other TIM).  The engine uploads it ONCE at boot: GameState_KcetLogo_Update
      (b_konami.c:149, KcetLogoStateStep_Init) -> GameFs_BgEtcGfxLoad
      (world_draw.c:80-85) queues FILE_TIM_BG_ETC_TIM with IMAGE={.tPage={0,12},
      .clutX=192} (u=v=clutY=0) -> Fs_QueuePostLoadTim (fsqueue.c:643-676) keeps the
      TIM's own block sizes but relocates them: the 4bpp pixel block (32 halfwords
      x 256 rows = a 128x256-texel sheet) lands at VRAM page 12 (x=0+((12&0xF)<<6)=
      768, y=0) and the 11 x 16-color CLUT block lands at (192,0).  Gfx_BillboardDraw
      (billboard_draw.c:260-261) then hardcodes tPage=44 (= page 12, x=768, 4bpp;
      setPolyGT4 code 0x3C has the ST bit CLEAR so the tpage ABR bits are INACTIVE)
      and clut=140 (= VRAM (192,2) = CLUT ROW 2, the third palette of the relocated
      block) and samples the UV window u[0,63] v[128,191] (D_800AE4DC field_8/9/A/B
      -> combined halfwords 0x8000/0x803F/0xBF00/0xBF3F) = texel columns 0-63 of
      rows 128-191 of the uploaded sheet - a 64x64 window.
      The quads are OPAQUE punch-through (PS1 4bpp texel INDEX 0 is fully transparent;
      CLUT row 2's color 0 is 0x0000 with STP=0 -> ~67.6% of the window is holes,
      and the window's texels reference palette indices 0-8 only).
      TEST/LEAVES.TIM (filetable 1768) is referenced NOWHERE in the decompiled code
      (full-text search: only fileenum.h/filetable.c list it) and is NEVER used -
      v10+ has NO fallback to it (a fallback would trade accuracy for convenience;
      the sourcing is BG_ETC.TIM or a LOUD drop, per the user's instruction).
      The PLM libraries' LEAF_1/LEAF_2 single triangles are NEVER rendered by this
      path (unplaced library entries).
      DIAMOND SIZE (engine-exact, v9 CORRECTION of the v8 reading): the psyq
      library disassembly (lib/libgte/smp_02.o, function RotTransPers) ends
      `mfc2 $2, $19; ...; jr $ra; sra $2, $2, 2` -> the C helper returns
      SZ3 >> 2 (the GTE depth shifted right by 2).  Gfx_BillboardDraw then does
      `temp_a0 = ret << 2` = the RAW GTE depth (Q8 world units; view-matrix
      translations are Q8 - vw_main.c `Q12_TO_Q8(ref_x)` etc., and the mesh
      path stores the same raw depth via gte_stsz3 for its fog far-clip test
      `MIN(0x79C << (otShift+2), fog.farDistance)`), and rasterizes
      halfW_px = Q12_MULT(field_6, Q12(ReadGeomScreen()) / temp_a0)
      = field_6 * H / z.  The GTE projects a world offset dx at depth z to
      H * dx / z pixels, so the diamond's world half-width IS field_6 in FULL
      Q8 units (542 -> 2.12 m; total diamond 4.23 x 3.02 m), half-height
      field_8 (387 -> 1.51 m; the screen diamond spans 2*half_h = 3.02 m from
      the BOTTOM VERTEX at the ring position to the apex straight above it).
      Ring offsets (radius, positionY) are Q8 units applied directly (no /4).
      BILLBOARD OT BUCKET (v11, engine-verbatim): Gfx_BillboardDraw addPrims at
      `ot->org[RotTransPers_ret >> otShift]` (billboard_draw.c:317-320, 326) —
      the ANCHOR-center depth (a single RotTransPers of the quad's ring
      position), Q6 units (SZ3>>2), >> otShift(=1) — and with NO per-model
      layer base.  The consumer reconstructs this from a MASK material's four
      corners (their mean equals the anchor depth by the diamond's symmetry),
      so the billboard quads are emitted with the SAME pair pattern as mesh
      quads (see EMISSION CONTRACT) to be reconstructed as quads.
  IPD_OBJ_DATA (36 bytes) = s_IpdModelInstance { s_ModelHeader* modelHdr;
      MATRIX mat }:  s32 obj_id @0 (index into the model-info list; the engine
      relocates it to the resolved modelHdr pointer —
      WorldMap_ModelBufferLinkObjectLists, world_map.c:1273-1291), s16 rt[9]
      @4 (the GTE MATRIX 3x3 rotation, row-major, 1.3.12 fixed point, applied
      as v' = R.v — the GTE MACs compute row-dot-vector), s16 pad @22,
      s32 tx @24, s32 ty @28, s32 tz @32 (the MATRIX translation, Q8 world
      units; upper 16 bits are sign-extension of the stored 16-bit value -
      verified on all 2010 records; WorldMap_Draw adds chunkBoundX/Z directly
      to t[0]/t[2], confirming Q8)
  PLM_FILE_HEADER (20 bytes) = s_LmHeader:
      u16 id @0 = 0x0630, u8 flag @2 [version = LM_VERSION 6], u8 tex_num @3
      [materialCount], u32 tex_name_offset @4 [materials — 24 bytes each =
      s_Material], u32 obj_num @8 [modelCount; bytes 0x9..0xB are padding,
      verified zero across every provided archive], u32 obj_start_offset @12
      [modelHdrs], u32 unk_data @16 [modelOrder — unused by the map draw path]
  PLM texture names: 24 bytes each at tex_name_offset (s_Material.name)
  PLM_OBJ_HEADER (16 bytes) = s_ModelHeader (formats/model.h):
      char name[8] @0, u8 mesh_num @8 [meshCount], u8 b @9 [vertexOffset],
      u8 c @10 [normalOffset], u8 d @11 (render flags bitfield:
        bit0    = field_B_0  — alternate transform path func_8005A21C
        bits1-3 = field_B_1  — the ORDERING-TABLE SECTION BASE selector:
                   func_80057090 (bodyprog_80056D8C.c:139) computes
                   otTag = &ot->org[func_800571D0(field_B_1)] and every
                   Gfx_MeshDraw addPrim lands at
                   org[base + ((MAX_vertex_SZ >> otShift) >> 2)]:
                   0->2, 1->0, 2->4, 3->33, 4->66, 5->99 (func_800571D0,
                   verbatim).  v11 EXPORTS THE TRUE VALUE per object and
                   cross-checks the consumer's name table against it.
        bits4-5 = field_B_4  — alternate draw path func_80059D50 (1..3)
        bits6-7 = unk_B_6), u32 data_offset @12 [meshHdrs]
      vertexOffset/normalOffset (b/c): when nonzero, the engine copies each
      mesh's vertices into the shared GTE scratch AT THAT OFFSET
      (func_8005759C, bodyprog_80056D8C.c:299-325) and the pack face indices
      address the OFFSET buffer.  Every object in every provided archive has
      b=c=0 (mesh-local indices); a nonzero value is a loud, hard error in
      v11 (the offset semantics would change face indexing — refusing to
      guess, exactly like the padding checks).
  PLM_DATA_HEADER (24 bytes) = s_MeshHeader:
      u8 pack_num @0 [primitiveCount], u8 vert_num @1 [vertexCount],
      u8 num_c @2 [normalCount], u8 num_d @3 [unkCount_3],
      u32 pack_offset @4 [primitives], u32 vert_xy_offset @8 [verticesXy],
      u32 vert_z_offset @12 [verticesZ], u32 normal_offset @16 [normals],
      u32 end_offset @20 [unkPtr_14 — the normal SLOT table]
  vertices:  vert_xy = s16 x,y per vertex (4 bytes each); vert_z = s16 z (2 bytes each)
  normals:   num_c entries of 4 bytes at normal_offset: (s8 nx, s8 ny, s8 nz, u8 slot_count)
             followed at end_offset by num_d 1-byte entries: slot -> vertex index.
             A pack corner references slot j = pack.normals[k]; its vertex is B[j] and its
             normal vector is A[g] where g is the group whose cumulative slot range
             contains j.  EVIDENCE: sum(slot_count)==num_d for 1936/1936 meshes,
             B[slot]==faces[k] for 280500/280500 corners, and this interpretation makes
             dot(cross(v1-v0,v2-v0), n) positive for 100% of faces.
             DEVIATION from legacy: the legacy tool read A[normals[k]] directly, which
             selects the wrong normal for most corners (only valid by accident when
             normals[k] < num_c) - corrected here.  The legacy also did not rotate
             object-local normals by the instance rotation matrix; we do.
  packs (20 bytes) = s_Primitive:
             u8 u0@0, v0@1, u16 cba@2, u8 u1@4, v1@5,
             u8 tex_num:7|stp:1 @7 (byte 6 is s_Primitive's bitfield view:
             materialIdx:7 | isTransparent:1 — the engine's
             `prim->bits1.flags & (1 << 15)` semi-transparency test,
             bodyprog_80056D8C.c:849),
             u8 u2@8, v2@9, u8 u3@10, v3@11,
             u8 faces[4] @12 [faceIdxs], u8 normals[4] @16 [field_10]
             quads are triangulated by the GPU as (v0,v1,v2) + (v1,v3,v2)
             (the PS1 GT4's two triangles; the corner order is a Z pattern —
             corners 1 and 2 are ADJACENT, the shared edge v1-v2 is the
             diagonal); faces[3]==0xFF or faces[3]==faces[2] marks a triangle
             (the second GT4 triangle is degenerate — it rasterizes to zero
             area exactly like the real hardware, see EMISSION CONTRACT).
  TIM (4bpp CLUT): 8-byte header (u8 id@0=0x10, u8 flags@4: bits0-1 bpp, bit3 has-CLUT),
      u32 clut_len @8 (includes its own 12-byte header), u16 cx@12, cy@14, cw@16, ch@18,
      CLUT data @20; image block at 8+clut_len: u32 img_len, u16 x,y,w,h, data at +12.
      4bpp: low nibble = even pixel.  CLUT color = BGR555 + STP bit.
      cba selects palette: px=(cba&0x3F)<<4, py=(cba&0x7FC0)>>6;
      palette byte offset = py*cw*2 + px*2 (VRAM-linear, legacy-identical).

DRAW ORDER (v11, engine-verbatim — world_map.c WorldMap_ChunksDraw/WorldMap_Draw):
  The engine's per-frame add order is: active chunks in order -> for the
  CURRENT subcell (the one containing the camera), the modelOrderList range
  [start, start+count) -> each buffer's instances in order, then that
  buffer's billboard anchors -> per instance: the model's meshes in order ->
  Gfx_MeshDraw's primitives in pack order.  Ordering-table ties (two quads in
  the same OT bucket) resolve LIFO: the FIRST-added quad is drawn LAST and
  wins — so the add order IS the layering.
  MEASURED on the provided corpus (THRF9FD): every one of the 25 subcell
  ranges lists its buffers in ASCENDING index order — the order list is a
  spatial SELECTION system (which buffers to draw near the player), not a
  reordering.  Therefore the engine's within-frame buffer order equals the
  file's buffer order everywhere, and the export emits: buffers in file
  order, instances in file order, meshes in PLM order, packs in pack order,
  billboards after their own buffer's instances (world_map.c:1378 runs the
  field_10 loop after the instance loop) — the engine's add order for every
  co-drawn pair, verified per subcell.  (Buffers that no subcell range
  references are never drawn by the engine; they are still exported — the
  wallpaper shows the whole scene, a documented static deviation — and
  reported loudly.)

EMISSION CONTRACT (v11 — THE flat-surface flicker fix):
  The consumer (the wallpaper engine, fog_poc.c) has NO depth buffer: it
  reconstructs each source quad from the GLB triangle stream by the pattern
  idx[k+3]==idx[k+1] && idx[k+5]==idx[k+2] and then applies the ENGINE's
  per-quad ordering-table semantics verbatim (Gfx_MeshDraw,
  bodyprog_80056D8C.c:690-997):
    * OT bucket = otBase + ((MAX of the FOUR vertex depths >> 1) >> 2)
      (lines 705-717: field_18 = max over all four faceIdx vertices), with
      `<=0 -> no entry`, `<=32 -> 32`, `> far -> whole quad skipped`;
    * backface cull = the dual gte_NormalClip test (lines 734-748 and the
      identical blocks in every fog/enum branch): the quad is skipped iff
      nclip(v0,v1,v2) <= 0 AND nclip(v3,v1,v2) >= 0 — draw iff EITHER drawn
      triangle is front-facing (this is what keeps grazing, near-edge-on
      quads STABLE: one half still front-facing draws the whole quad);
    * within a bucket: LIFO by add order.
  v10 and earlier emitted the reversed-winding pair (v2,v1,v0)+(v2,v3,v1):
  the same corner SETS and the same glTF CCW orientation, but the pair
  CANNOT match the reconstruction pattern (idx[k+3]=v2 != idx[k+1]=v1) —
  measured on the shipped GLB: 0.2% of quads reconstructed, 6302 lone
  triangles.  Every quad then degraded to two independent triangles with
  per-TRIANGLE buckets (a quad's halves can split across buckets) and a
  per-triangle cull with an undefined 4th vertex — the two mechanisms behind
  the frame-to-frame popping on flat surfaces (floors at grazing angles near
  the fog horizon have near-degenerate screen triangles whose nclip sign
  flips with the GTE vertex snap each frame).
  v11 emits every quad as (v0,v2,v1) + (v2,v3,v1):
    * identical corner sets, identical diagonal (v1-v2), identical glTF CCW
      orientation and pixel coverage as v10 (the three.js editor render is
      UNCHANGED — only the index order inside the stream moves);
    * the pattern matches: idx[k+3]=v2==idx[k+1], idx[k+5]=v1==idx[k+2] —
      the consumer reconstructs vi=(v0,v2,v1,v3), a permutation of the four
      corners, so its max-depth bucket and far cull run over ALL FOUR
      vertices exactly like the engine;
    * degenerate triangles (faces[3]==0xFF or ==faces[2]): the second
      triangle is STILL EMITTED with v3:=v2 — a zero-area triangle that
      rasterizes to nothing exactly like the GT4 on real hardware, keeping
      the pack a reconstructable quad (the engine's own second nclip is 0
      for these, and the consumer's reconstructed cull reproduces exactly
      that).  v10 DROPPED the second triangle, turning every one of the 632
      triangle-packs into lone triangles on the broken per-triangle path.
  Billboard (MASK) quads are emitted with the engine's own GT4 pair
  (top,right,left)+(right,bottom,left) — setXY4's corner order,
  billboard_draw.c:285-289 — so they reconstruct as quads too (their
  MASK bucket is the anchor-center depth, reproduced from the four corners'
  mean).

Coordinate conversion (documented):
  source: PS1 world with Y pointing DOWN (height = -Y; evidence: YUKA='floor'
  objects sit at each room's maximum source Y and their winding/normals point
  to the +Y (downward/ground) side, so the player-visible side is -Y = up).
  glTF :  pos = ( (x + 10240*x_pos), -(y), -(z + 10240*y_pos) ) / 256
          nrm = normalize( -(R*(nx,ny,nz)) mapped by (x,-y,-z) )
          The position map is a 180-degree rotation about X (determinant +1,
          orientation-preserving).  Because the PS1 GPU front face is the winding
          LEFT-hand (void) side, triangle winding is REVERSED from the stored order
          and normals are NEGATED, so glTF front faces (CCW) and normals both point
          into the room void - identical to the legacy OBJ tool's orientation.
  UV   :  glTF origin is top-left, PS1 UV origin is top-left: uv = (u/img_w, v/img_h).
"""
import argparse
import hashlib
import json
import logging
import math
import os
import struct
import sys
from dataclasses import dataclass, field

import numpy as np

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

log = logging.getLogger("ipd2gltf")

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
SCALE = 1.0 / 256.0        # PS1 unit -> meters (legacy map scale, made exact)
# World units per map grid cell.  AUTHORITATIVE (v8, silent-hill-decomp):
#   include/bodyprog/map/terrain.h:  #define CHUNK_SIZE 40.0f
#   src/bodyprog/world/world_map.c:  chunkBoundX = ipdHdr->chunkX * Q8(CHUNK_SIZE)
#     -> every world-space placement (geometry + billboard anchors) uses
#        signed_cell * 10240 Q8 units (256 units = 1 m).
#   The room's cell comes from the file name's last 4 hex digits via
#   ConvertHexToS8() (world_map.c) - identical to our s8(x@2)/s8(y@3) reads.
# The legacy sh_ipd2obj tool hardcoded map_max = 10246 (a MEASURED max geometry
# extent, not the game's cell stride) - 6 units (2.3 cm) per cell of drift;
# rectified to the engine value in v8 per the decompilation ground truth.
MAP_CELL = 10240           # = Q8(CHUNK_SIZE=40.0f) world units per map cell
GLTF_MAGIC = 0x46546C67   # ASCII "glTF" little-endian
CHUNK_JSON = 0x4E4F534A    # 'JSON'
CHUNK_BIN = 0x004E4942     # 'BIN'

u8 = lambda b, o: b[o]
s8 = lambda b, o: struct.unpack_from("<b", b, o)[0]
u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
s16 = lambda b, o: struct.unpack_from("<h", b, o)[0]
u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
s32 = lambda b, o: struct.unpack_from("<i", b, o)[0]


# ---------------------------------------------------------------------------
# SH1X v3 — ENGINE FX TABLES, VERBATIM from silent-hill-decomp.
# These do NOT live in IPD/PLM files (they live in decomp C tables + map
# overlay scripts), so the converter emits them HARDCODED with the source
# file:line in every comment. Consumers treat any absent v3 field as
# "feature off, render exactly as before" (old v2 GLBs stay supported).
# Design doc: docs/SH1X_EXTRAS_V3_FX.md. Grounds: session10_evidence/
# {WATER,LENS,ANIMS_MAPLINK,FLASHLIGHT}.md (verbatim quotes).
# ---------------------------------------------------------------------------

# Map_EffectTexturesLoad switch — src/bodyprog/gfx/env_effects.c:104-169.
# MapIdx values from include/bodyprog/map/map.h:26-70. Flag names from
# include/bodyprog/gfx/env_effects.h:4-14 (EffectTextureFlag_* enum).
# EventFlag conditions (47/284/306) are story flags; the engine loads the
# effect only while the flag is UNSET (checked at map load). The flag-
# dependent entries are recorded for completeness; room GLBs only carry
# AREA-CONSTANT FX (the sewers — see _room_env_fx).
_ENV_EFFECT_TEX = {
    # mapIdx: (flag name, TIM file, event flag or None)
    1:  ("Glass",        "GLASS.TIM",   47),   # MAP0_S01 (cafe glass)
    5:  ("Water",        "WATER.TIM",   None), # MAP1_S02 nightmare school
    6:  ("Water",        "WATER.TIM",   None), # MAP1_S03
    8:  ("Fire|Ef", ["FIRE.TIM", "EF.TIM"], None), # MAP1_S05 (fire + ef; env_effects.c:142-144,209-218)
    20: ("Fire",         "FIRE.TIM",   284),  # MAP3_S05
    23: ("Fire",         "FIRE.TIM",   306),  # MAP4_S01
    27: ("Blood",        "BLOOD.TIM",   None), # MAP4_S05
    29: ("WaterRefract", "DR_WAVE.TIM", None), # MAP5_S00 real sewers (DR)
    36: ("WaterRefract", "DR_WAVE.TIM", None), # MAP6_S03 alt sewers (DRU)
    44: ("WaterRefract", "DR_WAVE.TIM", None), # MAPX_S00 @unused
}

# s_WaterZone tables — src/bodyprog/sys/map_info.c:389-401 (WATER_LIGHT_
# ZONES_0/1), struct include/bodyprog/map/map.h:271-281 (s_WaterZone:
# u8 isEnabled; q11_4 illumination; q11_4 minX/maxX/minZ/maxZ — the decomp
# inits them with Q4(...) so the raw q11_4 equals meters*16; illumination
# 8 = water plane height in the same Q4).
# ONLY the two sewer areas carry water zones (map_info.c:527-528).
_WATER_ZONES = {
    "DR":  [(True, 8, -120.0, 80.0, -120.0, 40.0),
            (True, 8,    0.0, 40.0,    0.0, 80.0)],   # !JAP0 row included
    "DRU": [(True, 8, -160.0,  40.0, -160.0, 160.0),
            (True, 8, -160.0, 160.0, -160.0,  40.0)],
}

# MAP_INFOS — src/bodyprog/sys/map_info.c:515-532 (tag + flags per area).
# activeChunks: OneActiveChunks->1, TwoActiveChunks->2, else 4 (WorldGfx_
# MapInit, src/bodyprog/world/draw.c:242-273). isExterior = !MapFlag_
# Interior. MapType indices at include/bodyprog/map/map.h:111-126.
_MAP_INFOS = [
    # (tag, activeChunks, isExterior)   MapType
    ("THR", 4, True),   # 0  Old Silent Hill
    ("SC",  2, False),  # 1  school (A)
    ("SU",  2, False),  # 2  school (B) nightmare
    ("SPR", 4, True),   # 3  resort (A)
    ("SPU", 4, True),   # 4  resort (B)
    ("RSR", 4, True),   # 5  lakeside (A)
    ("RSU", 4, True),   # 6  lakeside (B)
    ("APR", 4, True),   # 7  apartments (A)
    ("APU", 4, True),   # 8  apartments (B)
    ("ER",  2, False),  # 9  interiors (misc)
    ("ER",  2, False),  # 10 (same tag; map7 headers bind this row)
    ("DR",  4, True),   # 11 real sewers
    ("DRU", 4, True),   # 12 alt sewers
    ("HP",  2, False),  # 13 hospital (A)
    ("HU",  2, False),  # 14 hospital (B)
    ("XXX", 4, True),   # 15 MapFlag_3 (special)
]

# Overlay (mapN_sXX) -> area tag binding — every src/maps/*/header.c
# `.mapInfo = &MAP_INFOS[...]` line, verbatim (evidence: ANIMS_MAPLINK.md;
# map0_s00/header.c:43 THR ... map7_s03/header.c:43 ER2).
# v27 CORRECTION (map_info.c:515-532 read directly): the RUNTIME tag
# string for BOTH ER-area MAP_INFOS entries (ER and the map7 "ER2") is
# "ER" — the nowhere overlays bind to the SAME ER-prefixed room files
# (the second of the two { "ER", ... } rows). Room files are always
# TAG+4hex; there are no ER2-prefixed files on disc.
_OVERLAY_TO_TAG = {
    "MAP0_S00": "THR", "MAP0_S01": "THR", "MAP0_S02": "ER",
    "MAP1_S00": "SC",  "MAP1_S01": "SC",  "MAP1_S02": "SU",
    "MAP1_S03": "SU",  "MAP1_S04": "SU",  "MAP1_S05": "SU",
    "MAP1_S06": "SC",  "MAP2_S00": "THR", "MAP2_S01": "ER",
    "MAP2_S02": "SPR", "MAP2_S03": "THR", "MAP2_S04": "ER",
    "MAP3_S00": "HP",  "MAP3_S01": "HP",  "MAP3_S02": "HU",
    "MAP3_S03": "HU",  "MAP3_S04": "HU",  "MAP3_S05": "HU",
    "MAP3_S06": "HP",  "MAP4_S00": "SPR", "MAP4_S01": "ER",
    "MAP4_S02": "SPU", "MAP4_S03": "SPU", "MAP4_S04": "HU",
    "MAP4_S05": "SPU", "MAP4_S06": "SPR", "MAP5_S00": "DR",
    "MAP5_S01": "RSR", "MAP5_S02": "ER",  "MAP5_S03": "ER",
    "MAP6_S00": "RSU", "MAP6_S01": "ER",  "MAP6_S02": "RSU",
    "MAP6_S03": "DRU", "MAP6_S04": "APU", "MAP6_S05": "APU",
    "MAP7_S00": "ER",  "MAP7_S01": "ER",  "MAP7_S02": "ER",
    "MAP7_S03": "ER",
}

# Prop anims — code-driven WorldObjects (decomp map overlay scripts).
# There is NO data-driven prop animation in SH1 (ANM is characters-only);
# every animated prop is C code calling WorldObjects_Add per frame
# (ANIMS_MAPLINK.md, section A5). The converter emits the VERBATIM driver
# parameters. Coordinates are ENGINE Q12 meters (y-down); consumers apply
# the standard axis map (x,-y,-z). NOTE: no windmills exist in SH1
# (verified zero decomp hits — the user's example is aspirational).
# ---- v36: the TV screen paint tables (func_800D88C8, map4_s03) --------
# Decoded VERBATIM from VIN/MAP4_S03.BIN (the compiled map overlay, load
# base g_OvlDynamic = 0x800C9578, main.c:26): D_800DB7D4 @0x1225C,
# D_800DB7E4[3][3] @0x1226C, D_800DB874[16] @0x122FC (16 entries x 10
# bytes, ending exactly at D_800DB914 = 0x800DB874+0xA0), plus the static
# D_800DB91C init (clutX=448). The anchor (Q12(160),Q12(0),Q12(40)) and
# the flicker 188/164/(pad&0xB) are func_800D7718 literals
# (map4_s03.c:535-548). Corner pairs are RAW Q8 offsets from the anchor;
# the cross-wiring (c1=(B.x,A.y,B.z), c2=(A.x,B.y,A.z)) is
# func_800D761C (map4_s03.c:492-501), applied by the CONSUMERS.
_TV_PAINT_SCREENS = [
    {"big": 0, "cA": [1009, -565, 3018], "cB": [782, -394, 3018]},
    {"big": 0, "cA": [754, -565, 3018], "cB": [526, -394, 3018]},
    {"big": 0, "cA": [498, -565, 3018], "cB": [269, -394, 3018]},
    {"big": 0, "cA": [1009, -373, 3018], "cB": [782, -202, 3018]},
    {"big": 0, "cA": [754, -373, 3018], "cB": [526, -202, 3018]},
    {"big": 0, "cA": [498, -373, 3018], "cB": [269, -202, 3018]},
    {"big": 0, "cA": [1009, -181, 3018], "cB": [782, -10, 3018]},
    {"big": 0, "cA": [754, -181, 3018], "cB": [526, -10, 3018]},
    {"big": 0, "cA": [498, -181, 3018], "cB": [269, -10, 3018]},
    {"big": 1, "cA": [1847, -728, 3423], "cB": [1440, -295, 3016]},
]
_TV_PAINT_STYLES = [
    {"tp": 0x1D, "clut": 0x05C, "u0":   8, "v0": 212, "du":   1, "dv":  1, "ru":  0, "rv":  0},
    {"tp": 0x1D, "clut": 0x01C, "u0":   0, "v0":   0, "du":  40, "dv": 55, "ru": 68, "rv": 60},
    {"tp": 0x1D, "clut": 0x05C, "u0":   0, "v0": 128, "du": 124, "dv": 62, "ru":  4, "rv":  1},
    {"tp": 0x1D, "clut": 0x05C, "u0":   0, "v0": 192, "du": 124, "dv": 62, "ru":  2, "rv":  0},
    {"tp": 0x1D, "clut": 0x01C, "u0": 128, "v0": 128, "du":  96, "dv": 56, "ru": 32, "rv":  8},
    {"tp": 0x0C, "clut": 0x15C, "u0": 128, "v0":   0, "du": 120, "dv": 62, "ru":  2, "rv":  0},
    {"tp": 0x0C, "clut": 0x19C, "u0": 128, "v0": 128, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x0C, "clut": 0x19C, "u0": 128, "v0": 192, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x0D, "clut": 0x19C, "u0":   0, "v0":   0, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x0D, "clut": 0x19C, "u0":   0, "v0":  64, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x0D, "clut": 0x19C, "u0":   0, "v0": 128, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x0D, "clut": 0x19C, "u0":   0, "v0": 192, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x1C, "clut": 0x29C, "u0":   0, "v0": 128, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x1C, "clut": 0x29C, "u0":   0, "v0": 192, "du": 122, "dv": 62, "ru":  6, "rv":  0},
    {"tp": 0x1C, "clut": 0x2DC, "u0": 128, "v0": 128, "du": 125, "dv": 62, "ru":  3, "rv":  0},
    {"tp": 0x1C, "clut": 0x29C, "u0": 128, "v0": 192, "du": 122, "dv": 62, "ru":  6, "rv":  0},
]


_WATER_FLOOR_SRC = (
    "func_8008E4EC lens_flare.c:497-502 (img0 {tPage{0,13}} all-zero -> "
    "Material_FsImageApply materials.c:130-160: field_E=45 = 4bpp page-13 "
    "x832 ABR-1 ADDITIVE, field_10=0 -> CLUT (0,0)) + WorldMap_"
    "TexturesInit map.c:137-190 (fullPage slot i: CLUT strip (16*i, 0), "
    "pixels (512+64*i, 0)) + Texture_Get materials.c:178-222 (slots in PLM "
    "material-table order) + LmFilter_IsHalfPage map.c:1226-1241 (name "
    "ends 'H' = half page)"
)


def _room_water_floor(room, resolver, report):
    """v37: SH1X.waterFloor — the room's slot-0 CLUT row 0 (16 raw u16).

    The engine's DWAVE floor redirect makes the water-floor quads read the
    live 32x32 tile (the func_8008E5B4 write window at VRAM (832,224)) as
    4bpp NIBBLES through the ROOM's FIRST fullPage texture-slot palette
    (CLUT (0,0) — the slot strips at (16*i, 0), the FIRST table material's
    TIM in slot 0). The clut15 array is that palette's row 0, VERBATIM raw
    15-bit values. Consumers rebuild the floor view as:
      texel(u, row) = clut15[(liveTile15[row][u>>2] >> (4*(u&3))) & 0xF]
    (u 0..127 = the 32-halfword patch's 128 texels, rows 0..31) — the
    page-texel UV mapping documented in SH1X_EXTRAS_V3_FX.md.

    Emitted ONLY for rooms whose material table carries "DWAVE" (the
    waterLive floor material) AND whose slot-0 TIM resolves locally; a
    miss emits nothing (the consumer's legacy floor path — graceful no-op).
    """
    if room.plm is None:
        return None
    names = []
    for raw in room.plm.tex_raws:
        names.append(raw[:8].decode("ascii", "replace").rstrip("\x00"))
    if not any(n == "DWAVE" for n in names):
        return None
    slot0 = None
    for n in names:
        if n.endswith("H"):        # LmFilter_IsHalfPage map.c:1226-1241
            continue
        slot0 = n
        break
    if slot0 is None:
        return None
    entry = None
    try:
        entry, _rec = resolver.resolve(slot0, room.name)
    except Exception:
        entry = None
    if entry is None:
        if report is not None:
            report.setdefault("problems", []).append(
                f"{room.name}: waterFloor: slot-0 TIM {slot0} not resolved — "
                f"waterFloor extras omitted (legacy floor path)")
        return None
    try:
        tim = TimFile(slot0, entry.read_bytes())
        row, _py = tim.palette(0)
    except Exception as e:
        if report is not None:
            report.setdefault("problems", []).append(
                f"{room.name}: waterFloor: slot-0 TIM {slot0}: {e}")
        return None
    return {
        "clutSource": slot0,
        "clut15": [int(c) & 0xFFFF for c in row],
        "slot0": {"clutX": 0, "clutY": 0, "pixelX": 512, "pixelY": 0,
                  "src": "WorldMap_TexturesInit map.c:153-166 fullPage slot 0"},
        "floorUv": {"pageTexel": True, "patchU": [0, 127], "patchV": [224, 255],
                     "note": "the MIZ quads' UVs are page-13 texel coords "
                              "(normalized by the DR_WAVE image's 256x64); "
                              "the live patch = u 0..127, v 224..255"},
        "src": _WATER_FLOOR_SRC,
    }


def _tv_paint_extras(room, resolver=None, report=None):
    """The SH1X.tvPaint block for the tvNoise rooms (the MAP4_S03 overlay's
    area tag). The palette STRIP reconstructs the paint's 256-entry CLUT
    bank rows 0..11 (VRAM x 448..703, the SwanStation Palette8Bit readout):
      x 448..463  = the TV TIMs' own CLUT rows (TV1 0..2, TV2 5..6,
                    TV3 10..11; rows 3,4,7,8,9 = fresh-boot stale = 0)
      x 464..511  = the tpage-7 region (the paper-map marking atlas only
                    loads there AFTER the map screen; fresh-boot stale=0)
      x 512..703  = the room's streamed fullPage texture slots 0..2
                    (tpages 8/9/10, Texture_Init map.c:152-167) — filled
                    from THIS room's first three PLM texture TIMs' pixel
                    rows 0..11 (the engine's runtime LRU stream content
                    VARIES per active chunk; the approximation is fixed
                    and documented here).
    Everything else (the corner tables, the style table, the flicker
    constants) is verbatim data. Returns None when the room's overlay
    has no tvNoise entry."""
    pa = _room_prop_anims(room.name)
    if not any(e.get("driver") == "tvNoise" for e in pa):
        return None
    # ---- the strip: TV clut rows + the room TIM rows (RAW 8bpp parse —
    # TimFile is 4bpp-only, so the TV/SPU effect TIMs are read directly) --
    def _tim8_parts(raw):
        """(clut_rows [[u16]], pixel_rows [[u16 x img_w]], img_w, img_h) for
        an 8bpp CLUT TIM, or None on any structural mismatch."""
        if len(raw) < 20 or raw[0] != 0x10:
            return None
        flags = u32(raw, 4)
        if not (flags & 8) or ((flags >> 3) & 3) != 1:   # need 8bpp CLUT TIM
            return None
        clen = u32(raw, 8)
        cw, ch = u16(raw, 16), u16(raw, 18)
        clut = raw[20:20 + (clen - 12)]   # data = clen-12 after the 12-byte block hdr
        io = 8 + clen
        iw, ih = u16(raw, io + 8), u16(raw, io + 10)
        pix = raw[io + 12:io + 12 + iw * 2 * ih]
        if len(clut) < cw * 2 * ch or len(pix) < iw * 2 * ih:
            return None
        rows = [list(struct.unpack_from(f"<{cw}H", clut, r * cw * 2))
                for r in range(ch)]
        prows = [list(struct.unpack_from(f"<{iw}H", pix, y * iw * 2))
                 for y in range(ih)]
        return rows, prows, iw, ih

    def _resolve_bytes(name):
        if resolver is None:
            return None
        try:
            entry, _rec = resolver.resolve(name, room.name)
        except Exception:
            return None
        if entry is None:
            return None
        try:
            return entry.read_bytes()
        except Exception:
            return None

    strip = [[0] * 256 for _ in range(12)]
    tv_rows = {0: ("TV1.TIM", 0), 1: ("TV1.TIM", 1), 2: ("TV1.TIM", 2),
               5: ("TV2.TIM", 0), 6: ("TV2.TIM", 1),
               10: ("TV3.TIM", 0), 11: ("TV3.TIM", 1)}
    for r, (name, row) in tv_rows.items():
        parts = _tim8_parts(_resolve_bytes(name))
        if parts is None:
            if report is not None:
                report.setdefault("problems", []).append(
                    f"{room.name}: tvPaint palette strip: {name} not "
                    f"resolved/8bpp (its CLUT row emitted as 0)")
            continue
        clut_rows, _prows, _w, _h = parts
        for c in range(16):
            strip[r][c] = clut_rows[row][c] & 0xFFFF
    # the room's first three TIMs (the PLM texture-table order = the
    # engine's material binding order): pixel rows 0..11 (the 8bpp sheets'
    # rows are img_w halfwords each)
    if room.plm is not None:
        for si, tname in enumerate(room.plm.tex_names[:3]):
            parts = _tim8_parts(_resolve_bytes(tname))
            if parts is None:
                if report is not None:
                    report.setdefault("problems", []).append(
                        f"{room.name}: tvPaint palette strip: room TIM "
                        f"{tname} not resolved/8bpp (its slot emitted as 0)")
                continue
            _cl, prows, iw, ih = parts
            # v40 audit (D-F6): the strip column = VRAM x - 448 (the
            # paint CLUT base, fs_queue.c:643-682 clutX=448 D_800DB91C).
            # fullPage slot i uploads at VRAM x 512 + 64*i (map.c:153-166
            # tPage[1] = 8+i -> fs_queue.c:657 x = u + ((tPage[1]&0xF)<<6))
            # => strip column 64 + 64*si, which is what the comment always
            # claimed ("strip x 512 + si*64"). The old `48 + si*64` put
            # slot 0 at VRAM 496 (16 into the stale region before the
            # first slot), shifted every slot 16 left, left columns
            # 240-255 zero, and polluted 48-63 into the non-slot region —
            # measured on the shipped SPU0401.glb (slot data at 48-239).
            base = 64 + si * 64
            for r in range(min(12, len(prows))):
                hw = prows[r]
                for c in range(min(64, len(hw), 256 - base)):
                    strip[r][base + c] = hw[c] & 0xFFFF
    return {
        "anchor": [160.0, 0.0, 40.0],
        "anchorSrc": "func_800D7718:535 Vw_WorldScreenMatrixAtPositionGet"
                     "(Q12(160), Q12(0), Q12(40))",
        "screens": [dict(s) for s in _TV_PAINT_SCREENS],
        "styles": [dict(s) for s in _TV_PAINT_STYLES],
        "flickBright": 188, "flickDim": 164, "flickMask": 11,
        "paletteStrip": strip,
        "src": "map4_s03.c:1252-1409 (func_800D88C8) + the VIN/"
               "MAP4_S03.BIN tables (D_800DB7D4/D_800DB7E4/D_800DB874, "
               "overlay base 0x800C9578) + Fs_QueuePostLoadTim "
               "(fs_queue.c:643-682, clutX=448 static D_800DB91C) + "
               "swanstation gpu_sw_backend.cpp ShadePixel (Palette8Bit)",
    }


_PROP_ANIMS = {
    # ---- map0_s00: Balkan wheelchair (map0_s00_2.c:1215-1220 init,
    # 1259-1286 update — the verbatim RNG spin with |1| doubled add) ----
    "MAP0_S00": [
        {"object": "WHEEL1_H", "pos": [-268.32, -0.44, 245.72],
         "rot0": [-43.0, -115.0, 0.0],
         "driver": "spinRng", "axis": "z", "rngBase": -90.0, "rngMask": 0x1FF,
         "chunkGate": [-7, "5|6"], "eventGate": 24,
         "eventGatePolarity": "clear",
         "sound": "Sfx_Unk1358",
         "src": "map0_s00_2.c:1259-1267 (!Get(24) — drive-while-CLEAR)"},
        {"object": "WHEEL2_H", "pos": [-268.32, -0.44, 245.72],
         "rot0": [-43.0, -115.0, 0.0],
         "driver": "spinRng", "axis": "z", "rngBase": -90.0, "rngMask": 0x1FF,
         "chunkGate": [-7, "5|6"], "eventGate": 24,
         "eventGatePolarity": "clear", "sharedRot": "WHEEL1_H",
         "sound": "Sfx_Unk1358",
         "src": "map0_s00_2.c:1259-1267 (!Get(24) — drive-while-CLEAR)"},
    ],
    # ---- map1_s01 reception rattling doors (map1_s01.c:1229-1290) ----
    "MAP1_S01": [
        {"object": "TOBIRA00", "pos": [-58.81, -1.3, 18.0198],
         "rot0": [0, 0, 0], "driver": "doorRattle",
         "oneIn": 32, "kickMin": 2, "kickMax": 9,
         "bounceLimit": -1.8, "holdAfterFlag": -2.9,
         "chunkGate": [-2, 0], "eventGate": 76,
         "eventGatePolarity": "clear",
         "sound": "Sfx_Unk1435",
         "src": "map1_s01.c:1229-1290 (!Get(76) — drive-while-CLEAR)"},
        {"object": "TOBIRA01", "pos": [-58.81, -1.3, 18.0198],
         "rot0": [0, 0, 0], "driver": "doorRattle",
         "oneIn": 32, "kickMin": 2, "kickMax": 9,
         "bounceLimit": -1.8, "holdAfterFlag": -2.9,
         "chunkGate": [-2, 0], "eventGate": 76,
         "eventGatePolarity": "clear", "sharedRot": "TOBIRA00",
         "sound": "Sfx_Unk1435",
         "src": "map1_s01.c:1052,1287-1289 (same pos, rotation COPIED from "
                "TOBIRA00 — the engine adds both leaves of the double "
                "door with the one live rotation vector)"},
        {"object": "SILVER_H", "pos": [-98.8, 0.0, 22.8],
         "rot0": [-90.0, 28.5, 0.0], "driver": "cutscene",
         "cutscene": "silverDrop (orbit+gravity, map1_s01.c:469-485)",
         "src": "map1_s01.c:469-485"},
    ],
    # ---- map1_s02 nightmare school (fans + doors + waterfall) ----
    "MAP1_S02": [
        {"object": "FAN_HIDE", "pos": [100.0, -1.6, 142.9],
         "rot0": [0, 0, 0], "driver": "spinRng", "axis": "z",
         "rngBase": -180.0, "rngMask": 0x1FF, "chunkGate": [2, 3],
         "sound": "Sfx_Unk1455",
         "src": "map1_s02.c:1564-1591"},
        {"object": "FAN_HIDE", "pos": [100.0, -1.6, 145.25],
         "rot0": [0, 0, 0], "driver": "spinRng", "axis": "z",
         "rngBase": -205.0, "rngMask": 0x1FF, "chunkGate": [2, 3],
         "sound": "Sfx_Unk1455",
         "src": "map1_s02.c:1575-1583"},
        {"object": "DOOR_HID", "pos": [18.37, -0.8, 59.51],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "bathroomDoor ramp to -112.5deg (map1_s02.c:983-1017)",
         "holdFlag": 96,
         "src": "map1_s02.c:983-1017"},
        {"object": "DOOR1_HI", "pos": [58.4, 0.0, -59.6],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "clockTowerDoor ramp+snap 90deg (map1_s02.c:1173-1297)",
         "src": "map1_s02.c:1173-1297"},
        {"object": "DOOR2_HI", "pos": [58.4, 0.0, -60.4],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "clockTowerDoor ramp+snap 180deg (map1_s02.c:1173-1297)",
         "src": "map1_s02.c:1173-1297"},
        # Drain-water particle system (the "waterfall" of the school-key
        # puzzle) — NON-WorldObject 2D particles like <ripples>/<light>;
        # the emitter/velocity/CLUT tables sharedData_800E30C8_1_s02 are
        # extern-only binary .data (map1_s02.h) — constants not in the
        # decomp repo, the GATES are decompiled (map1_s02.c:1542-1562).
        {"object": "BOX_HIDE", "pos": [54.47, 0.0, -60.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "boxRise: player+box vy += dt*D_800E1FE4 (ramp "
                "0->Q12(0.4), func_800DCF00 map1_s02.c:1316-1379; Sfx_"
                "Unk1451; sets EventFlag_120); static add chunk (1,-2)",
         "chunkGate": [1, -2], "sound": "Sfx_Unk1451",
         "src": "map1_s02.c:1460, 1316-1379, 1627"},
        {"object": "<waterfall>", "driver": "particles",
         "eventGate": 113, "eventGatePolarity": "set",
         "chunkGate": [-1, -2],
         "gate": "PLAYER_IN_MAP_CHUNK(-1,-2) && Get(EventFlag_"
                 "M1S03_KeyDownTheDrain=113) — spawn on entering the "
                 "chunk, despawn on leaving (map1_s02.c:1542-1562)",
         "spawn": "sharedFunc_800CBC98_1_s02 (water.c:70-92): field_74 "
                 "particles from the emitter table below (the v39 stream "
                 "block — map1_s02.c:1488-1522 IS in the decomp)",
         "despawn": "sharedFunc_800CBD58_1_s02 (water.c:94-107)",
         # v39: the emitter table VERBATIM — map1_s02.c:1488-1522
         # (Map_WorldObjectsInit fills sharedData_800E30C8_1_s02).
         # s_MapOverlayHdr_94 include/bodyprog/map/map.h:341-360.
         # Decoded meters/degrees; raw Q12 = meters*4096, headings are
         # Q3.12 angles (4096/rev; 0=+Z, 90=+X). field names follow the
         # struct. The terminator slot (idx=2) carries len 0.
         "stream": {
             "segments": [
                 {"x": -16.4, "y": 0.1, "z": -51.2, "len": 1.6,
                  "horizontal": True, "heading": 90.0,
                  "width": 0.4, "tileLen": 0.5, "scrollSpeed": 0.05,
                  "spread": 0.4, "rampHalf": 0.5, "flowBase": 0.05},
                 {"x": -14.8, "y": 0.1, "z": -51.2, "len": 1.6,
                  "horizontal": True, "heading": 270.0,
                  "width": 0.4, "tileLen": 0.5, "scrollSpeed": 0.05,
                  "spread": 0.4, "rampHalf": 0.5, "flowBase": 0.05},
                 {"len": 0.0, "y": 0.1, "width": 0.4,
                  "spread": 0.4, "rampHalf": 0.5},
             ],
             "droplets": 10, "segmentCount": 2,
             "struct": "s_MapOverlayHdr_94 map.h:341-360",
             "src": "map1_s02.c:1488-1522 (field_0/10/18/28/30/34/3C/"
                    "44/4C/5C/64/6c arrays, field_74=10, field_78=2, "
                    "the idx=2 terminator)",
         },
         "src": "map1_s02.c:1542-1562; src/maps/common/particles/"
                "water.c:20-107"},
    ],
    # ---- map1_s03 locker suite (map1_s03.c:1928-2153) ----
    "MAP1_S03": [
        {"object": "TOBIRA2_", "pos": [-61.0, -1.05, 20.97],
         "rot0": [0, 0, 0], "driver": "kickSwing",
         "kickVelRaw": -128, "kickVelDeg": -11.25,
         "openLimitRaw": -1920, "openLimitDeg": -168.75,
         "bounceHiRaw": -1791, "bounceHiDeg": -157.412,
         "settleRaw": -1790, "settleDeg": -157.3242,
         "reboundVelRaw": 32, "reboundVelDeg": 2.8125,
         "cutscene": "locker kick (state 6->7, map1_s03.c:1956-1976)",
         "chunkGate": [-2, 0],
         "sound": "Sfx_Unk1460",
         "src": "map1_s03.c:1956-1999"},
        {"object": "TOBIRA01", "pos": [-58.81, -1.4, 18.02],
         "rot0": [0, 0, 0], "driver": "doorRattle",
         "oneIn": 32, "kickMin": 2, "kickMax": 9,
         "bounceLimit": -1.8, "holdAfterFlag": -2.9,
         "chunkGate": [-2, 0], "eventGate": 101, "eventGateAlt": 102,
         "eventGatePolarity": "clear-or",
         "sound": "Sfx_Unk1435",
         "src": "map1_s03.c:2002-2046 (kick state D_800E20E8 — set by "
                "the TOBIRA2_ locker kick at 1961-1966, SHARED with "
                "TOBIRA2_'s swing; gate !Get(101)||!Get(102) — drive while "
                "EITHER is CLEAR)"},
        {"object": "TOBIRA00", "pos": [-58.81, -1.4, 18.02],
         "rot0": [0, 0, 0], "driver": "doorRattle",
         "oneIn": 32, "kickMin": 2, "kickMax": 9,
         "bounceLimit": -1.8, "holdAfterFlag": -2.9,
         "chunkGate": [-2, 0], "eventGate": 101, "eventGateAlt": 102,
         "eventGatePolarity": "clear-or", "sharedRot": "TOBIRA01",
         "sound": "Sfx_Unk1435",
         "src": "map1_s03.c:1593 (init pos), 2148-2149 (rotation.vy "
                "COPIED from TOBIRA01's live rotation immediately before "
                "the add — the follower leaf of the locker double door; "
                "rattle math shared with TOBIRA01: 2002-2046)"},
        {"object": "VALVE_HI", "pos": [-10.49, -0.7, -12.92],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "valve hand-tracking (map1_s03.c:890-988)",
         "src": "map1_s03.c:890-988"},
    ],
    # ---- map1_s05 the moving bars (the SU boss-arena contraption: the
    # SPHERE_H + WHEEL_HI spins, map1_s05.c:383-387 ungated const spins;
    # user-classified "the moving bars" — the room SU00FF, the SplitHead
    # finale arena of the alternate school, paper map = school BF) ------
    "MAP1_S05": [
        {"object": "SPHERE_H", "pos": [19.7, 1.58, -19.1],
         "rot0": [0, 0, 0], "driver": "spinConst", "axis": "y",
         "rate": -90.0, "label": "moving bar (upper)",
         "src": "map1_s05.c:383-384"},
        {"object": "WHEEL_HI", "pos": [19.7, -0.06, -19.1],
         "rot0": [0, 0, 0], "driver": "spinConst", "axis": "y",
         "rate": 15.0, "label": "moving bar (lower)",
         "src": "map1_s05.c:386-387"},
        {"object": "<light>", "pos": [19.7, -3.0, -19.1],
         "driver": "lightFlicker",
         "base": 1.35, "ampA": 0.9, "ampB": 0.6,
         "baseRaw": 5529, "ampARaw": 3686, "ampBRaw": 2457,
         "per0": 64, "per1": 64, "amp": 48,
         "rerollA": [32, 63], "rerollB": [32, 95],
         "rampThreshRaw": 262144,
         "eventGate": 129, "eventGatePolarity": "set",
         "src": "map1_s05.c:371-396 (init 319-341: D_800D86FC[0..1]=0x40, "
                "D_800D86FE=48; Get(129) — drive-while-SET)"},
    ],
    # ---- map2_s00 streets west (drawbridge + chain door) ----
    "MAP2_S00": [
        {"object": "AXIS1_HI", "pos": [205.0, 0.0, -80.0],
         "rot0": [0, 0, -49.94], "driver": "cutscene",
         "cutscene": "drawbridge press1 dt*0x88 / press2 dt*Q12(0.1/3) to 0",
         "eventGate": 166, "sharedRot": "AXIS2_BA",
         "sound": "Sfx_Unk1481-1485",
         "src": "map2_s00.c:1638-1646, 1745-1752"},
        {"object": "AXIS2_BA", "pos": [205.0, 0.0, -80.0],
         "rot0": [0, 0, -49.94], "driver": "cutscene", "sharedRot": "AXIS1_HI",
         "cutscene": "drawbridge (paired deck)",
         "eventGate": 166,
         "src": "map2_s00.c:1638-1646, 1745-1752"},
        {"object": "AXIS1_HI", "pos": [-35.0, 0.0, 360.0],
         "rot0": [0, 0, -49.94], "driver": "cutscene",
         "cutscene": "drawbridge second pair (shared D_800F5344 state)",
         "attachRoom": "THRFE08",
         "eventGate": 166, "sharedRot": "AXIS2_BA#2", "pair": 2,
         "chunkGate": [-2, 8],
         "src": "map2_s00.c:2149-2150 (added from MAP_CHUNK_CELL(-2,8) "
                "= room THRFE08; the pos cell (-1,9) is room THRFF09 "
                "which does not exist on disc — the engine adds the pair "
                "from the PLAYER's room chunk, not the pos cell)"},
        {"object": "AXIS2_BA", "pos": [-35.0, 0.0, 360.0],
         "rot0": [0, 0, -49.94], "driver": "cutscene", "sharedRot": "AXIS1_HI",
         "cutscene": "drawbridge (paired deck, second)", "pair": 2,
         "attachRoom": "THRFE08",
         "eventGate": 166, "chunkGate": [-2, 8],
         "src": "map2_s00.c:2149-2150"},
        {"object": "DOOR1_BA", "pos": [-263.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "dampedSwing",
         "angAccelRaw": -113, "angVelFloorRaw": -56, "vyFloorRaw": -91,
         "angAccelDeg": -9.931640625, "angVelFloorDeg": -4.921875,
         "vyFloorDeg": -8.002, "vyFloorUnits": "linear Q12(-0.02222f)="
                "-91 raw = -8.002deg in Q12_ANGLE (map2_s00.c:1941-1943)",
         "postEventVyDeg": 8.0, "postEventVyRaw": 91,
         "eventGate": 168, "sharedRot": "CHAIN2_1",
         "sound": "Sfx_Unk1393/1394",
         "src": "map2_s00.c:1913-1944 (init 2033-2038, 2073-2086)"},
        {"object": "CHAIN1_1", "pos": [-262.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "STATIC pre-event chain set (SVECTOR3_Zero rot, pos "
                "D_800F56CC[0] = (-262,0,-104); rendered while !Get(169) "
                "&& !Get(170) — the pre-cutscene state)",
         "eventGate": 169, "eventGatePolarity": "clear",
         "src": "map2_s00.c:2040-2042, 2203-2205"},
                {"object": "CHAIN1_2", "pos": [-262.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "STATIC pre-event chain set (SVECTOR3_Zero rot, pos "
                "D_800F56CC[0] = (-262,0,-104); rendered while !Get(169) "
                "&& !Get(170) — the pre-cutscene state)",
         "eventGate": 169, "eventGatePolarity": "clear",
         "src": "map2_s00.c:2040-2042, 2203-2205"},
                {"object": "CHAIN1_3", "pos": [-262.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "STATIC pre-event chain set (SVECTOR3_Zero rot, pos "
                "D_800F56CC[0] = (-262,0,-104); rendered while !Get(169) "
                "&& !Get(170) — the pre-cutscene state)",
         "eventGate": 169, "eventGatePolarity": "clear",
         "src": "map2_s00.c:2040-2042, 2203-2205"},
        {"object": "CHAIN2_1", "pos": [-263.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "dampedSwing",
         "angAccelRaw": -113, "angVelFloorRaw": -56, "vyFloorRaw": -91,
         "postEventVyDeg": 8.0, "postEventVyRaw": 91,
         "eventGate": 168, "sharedRot": "DOOR1_BA",
         "src": "map2_s00.c:1913-1944"},
        {"object": "CHAIN2_2", "pos": [-263.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "dampedSwing",
         "angAccelRaw": -113, "angVelFloorRaw": -56, "vyFloorRaw": -91,
         "postEventVyDeg": 8.0, "postEventVyRaw": 91,
         "eventGate": 168, "sharedRot": "DOOR1_BA",
         "src": "map2_s00.c:2044 (name), 2210-2211 (added with the LIVE "
                "swing rot D_800F538C, same pos D_800F56CC[1]=-263/0/-104 "
                "as CHAIN2_1 — the second animated chain of the set; the "
                "chain2 half renders while Get(169), !Get(170))"},
        # CHAIN2_3 / CHAIN2_4: STATIC adds (SVECTOR3_Zero rot, fixed pos
        # D_800F56CC[0]=-262/0/-104, map2_s00.c:2045-2046, 2212-2213) — no
        # per-frame mutation; carried for set completeness (render-only
        # while Get(169) && !Get(170)).
        {"object": "CHAIN2_3", "pos": [-262.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "static add with SVECTOR3_Zero rot (map2_s00.c:2212) — "
                "no per-frame mutation; eventGate 169 set/170 clear",
         "eventGate": 169, "eventGatePolarity": "set",
         "src": "map2_s00.c:2045, 2212"},
        {"object": "CHAIN2_4", "pos": [-262.0, 0.0, -104.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "static add with SVECTOR3_Zero rot (map2_s00.c:2213) — "
                "no per-frame mutation; eventGate 169 set/170 clear",
         "eventGate": 169, "eventGatePolarity": "set",
         "src": "map2_s00.c:2046, 2213"},
    ],
    # ---- map3 hospital elevators + cabinet (SHARED slide code) ----
    "MAP3_S01": [
        {"object": "DR1L_HID", "pos": [59.1, 0.0, 19.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 0, "axis": "z", "speed": 0.35,
         "accel": 0.8, "resetZ": 19.1, "chunkGate": [1, 0],
         "sound": "Sfx_Unk1499-1502",
         "src": "sharedFunc_800D15F0_3_s01.h:331-365"},
        {"object": "DR1R_HID", "pos": [59.1, 0.0, 19.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 1, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 19.1, "chunkGate": [1, 0], "dir": -1,
         "src": "sharedFunc_800D15F0_3_s01.h:331-365"},
        {"object": "DR3L_HID", "pos": [59.1, 0.0, 19.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 2, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 19.1, "chunkGate": [1, 0],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign -vz (i even, :336/:349)",
         "slideSign": "-vz (i=2, even)",
         "src": "map3_s01.c:366 (init 59.1/0/19.1), 462-472 (add+reset "
                "chunk 1,0), sharedFunc_800D15F0_3_s01.h:331-365 "
                "(via map3_s01.c:134)"},
        {"object": "DR3R_HID", "pos": [59.1, 0.0, 19.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 3, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 19.1, "chunkGate": [1, 0],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign +vz (i odd, :336/:349)",
         "slideSign": "+vz (i=3, odd)",
         "src": "map3_s01.c:367, 462-472, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2L_HID", "pos": [59.1, 0.0, 19.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 4, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 19.1, "chunkGate": [1, 0],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign -vz (i even, :354)",
         "slideSign": "-vz (i=4, even)",
         "src": "map3_s01.c:368, 462-472, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2R_HID", "pos": [59.1, 0.0, 19.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 5, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 19.1, "chunkGate": [1, 0],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign +vz (i odd, :354)",
         "slideSign": "+vz (i=5, odd)",
         "src": "map3_s01.c:369, 462-472, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
    ],
    "MAP3_S03": [
        {"object": "DR1L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 0, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "src": "sharedFunc_800D15F0_3_s01.h:331-365 + map3_s03.c:941-956"},
        {"object": "DR1R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 1, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1], "dir": -1,
         "src": "sharedFunc_800D15F0_3_s01.h:331-365 + map3_s03.c:941-956"},
        {"object": "DR3L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 2, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign -vz (i even, :336/:349)",
         "slideSign": "-vz (i=2, even)",
         "src": "map3_s03.c:896, 941-956 (add+reset chunk 0,1), "
                "sharedFunc_800D15F0_3_s01.h:331-365 (via :888)"},
        {"object": "DR3R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 3, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign +vz (i odd, :336/:349)",
         "slideSign": "+vz (i=3, odd)",
         "src": "map3_s03.c:897, 941-956, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 4, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign -vz (i even, :354)",
         "slideSign": "-vz (i=4, even)",
         "src": "map3_s03.c:898, 941-956, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 5, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign +vz (i odd, :354)",
         "slideSign": "+vz (i=5, odd)",
         "src": "map3_s03.c:899, 941-956, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
    ],
    "MAP3_S04": [
        {"object": "DR1L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 0, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "src": "sharedFunc_800D15F0_3_s01.h:331-365 + map3_s04_2.c:539-554"},
        {"object": "DR1R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 1, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1], "dir": -1,
         "src": "sharedFunc_800D15F0_3_s01.h:331-365 + map3_s04_2.c:539-554"},
        {"object": "DR3L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 2, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign -vz (i even, :336/:349)",
         "slideSign": "-vz (i=2, even)",
         "src": "map3_s04_2.c:505, 539-554 (add+reset chunk 0,1), "
                "sharedFunc_800D15F0_3_s01.h:331-365 (via :497)"},
        {"object": "DR3R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 3, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign +vz (i odd, :336/:349)",
         "slideSign": "+vz (i=3, odd)",
         "src": "map3_s04_2.c:506, 539-554, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 4, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign -vz (i even, :354)",
         "slideSign": "-vz (i=4, even)",
         "src": "map3_s04_2.c:507, 539-554, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 5, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign +vz (i odd, :354)",
         "slideSign": "+vz (i=5, odd)",
         "src": "map3_s04_2.c:508, 539-554, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
    ],
    "MAP3_S05": [
        {"object": "TANA_HID", "pos": [60.0, 0.0, -21.6],
         "rot0": [0, 180.0, 0], "driver": "cutscene",
         "cutscene": "cabinetPush dt*playerRadius clamp 61.25 (map3_s05)",
         "eventGate": 282, "eventGatePolarity": "set",
         "sound": "Sfx_Unk1535",
         "src": "map3_s05.c:858-905, 935-940, 995-1009 "
                "(EventFlag_M3S05_CabinetPushed = 282; Get(282))"},
        # v28.1 FIX (verified vs decomp): map3_s05's doors are placed at
        # (19.1, 0, 59.1) — grid cell (0,1), the same cell as map3_s03/
        # map3_s04 — NOT (59.1, 0, 19.1) as previously catalogued (x/z
        # had been swapped from map3_s01); resetZ is 59.1
        # (map3_s05.c:950-955, 1064-1079).
        {"object": "DR1L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 0, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "src": "sharedFunc_800D15F0_3_s01.h:331-365 + map3_s05.c:950-955, "
                "1064-1079"},
        {"object": "DR1R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 1, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1], "dir": -1,
         "src": "sharedFunc_800D15F0_3_s01.h:331-365 + map3_s05.c:951, "
                "1064-1079"},
        {"object": "DR3L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 2, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign -vz (i even, :336/:349)",
         "slideSign": "-vz (i=2, even)",
         "src": "map3_s05.c:952, 1064-1079 (add+reset chunk 0,1), "
                "sharedFunc_800D15F0_3_s01.h:331-365 (via :924)"},
        {"object": "DR3R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 3, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365): outer set i<4, "
                "slideSign +vz (i odd, :336/:349)",
         "slideSign": "+vz (i=3, odd)",
         "src": "map3_s05.c:953, 1064-1079, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2L_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 4, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign -vz (i even, :354)",
         "slideSign": "-vz (i=4, even)",
         "src": "map3_s05.c:954, 1064-1079, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
        {"object": "DR2R_HID", "pos": [19.1, 0.0, 59.1], "rot0": [0, 0, 0],
         "driver": "slideDoor", "slideIdx": 5, "axis": "z", "speed": 0.35, "accel": 0.8,
         "resetZ": 59.1, "chunkGate": [0, 1],
         "cutscene": "elevator ride states 15-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:342-355): inner set i>=4, "
                "slideSign +vz (i odd, :354)",
         "slideSign": "+vz (i=5, odd)",
         "src": "map3_s05.c:955, 1064-1079, sharedFunc_800D15F0_3_s01.h:"
                "331-365"},
    ],
    # ---- map4_s01/2/3 hospital objects ----
    "MAP4_S01": [
        {"object": "MOV1_HID", "pos": [178.2681, -0.387, 63.6814],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "cabinetPush dt*0.22 clamp 63.6814 (pre-push 62.7466)",
         "eventGate": 302, "sound": "Sfx_Unk1538",
         "src": "map4_s01_2.c:301-322, 1302-1334"},
    ],
    "MAP4_S02": [
        {"object": "FAN0_HID", "pos": None, "rot0": [0, 0, 0],
         "driver": "fanArray", "axis": "x",
         "bladeCount": 16, "count": 16, "rate": 90.0, "spinSplit": 7,
         "spinSplitUnits": "map4_s02.c:140-149: i<7 angle -= dt*Q12_ANGLE(90), "
                "i>=7 angle += dt*Q12_ANGLE(90) (per-fan state D_800ED8B0[i], "
                "u16[16] per map4_s02.h:20 — the raw angle WRAPS at 65536, "
                "not at the Q12_ANGLE 4096 circle)",
         "alternate": True, "chunkGate": [1, 0],
         "positions": [[53.211, -2.375, 32.5], [56.575, -2.875, 27.5],
                        [65.45, -2.875, 27.5], [68.8, -2.375, 32.5]],
         "posSwitch": "map4_s02.c:113-162: the switch sets the base ONLY at "
                "i==0->p0 (Math_SetSVectorFast resets rot to 0,0,0), "
                "i==4->p1, i==7->p2 (+objRot.vy=180, STICKY — cases 11 and "
                "the default do not touch objRot), i==11->p3; AFTER every "
                "WorldObjects_Add the loop runs objPos.vz -= Q12(5.0f) "
                "(map4_s02.c:162) — each fan is 5.0m further -z than the "
                "previous one until the next switch reset",
         "posPerInst": [[53.211, -2.375, 32.5], [53.211, -2.375, 27.5],
                        [53.211, -2.375, 22.5], [53.211, -2.375, 17.5],
                        [56.575, -2.875, 27.5], [56.575, -2.875, 22.5],
                        [56.575, -2.875, 17.5],
                        [65.45, -2.875, 27.5], [65.45, -2.875, 22.5],
                        [65.45, -2.875, 17.5], [65.45, -2.875, 12.5],
                        [68.8, -2.375, 32.5], [68.8, -2.375, 27.5],
                        [68.8, -2.375, 22.5], [68.8, -2.375, 17.5],
                        [68.8, -2.375, 12.5]],
         "posPerInstSrc": "map4_s02.c:113-162 (per-iteration "
                "objPos.vz -= Q12(5.0f) AFTER the add)",
         "rotY180From": 7,
         "sound": "Sfx_Unk1542",
         "src": "map4_s02.c:53, 108-165 (add+decrement loop), 197-205 (sfx)"},
    ],
    "MAP4_S03": [
        {"object": "REF_NEAR", "pos": [164.0, 0.0, 52.0],
         "rot0": [0, 0, 0], "driver": "tvNoise",
         "cutsceneOnly": True,
         "lcgA": 0x7169AC35, "lcgXorA": 0xA547B39E,
         "lcgB": 0x892D719C, "lcgXorB": 0xC65A4B97,
         "durationShift": 5, "durationBase": 0x555,
         "tim": ["TV1.TIM", "TV2.TIM", "TV3.TIM"],
         "chunkGate": ["3|4", 1], "eventGate": 324,
         "src": "map4_s03.c:405-464, 527-595, 696-828, 1252-1409; the "
                "REF_NEAR WorldObject pose = D_800DB7C8 (Q12(164),Q12(0),"
                "Q12(52)) decoded from VIN/MAP4_S03.BIN; cutsceneOnly: the "
                "WorldObjects_Add at func_800D7718:551 fires only when "
                "D_800E0698.field_0 != 0 (engine-fresh master 0 = not "
                "drawn; --anims-demo seeds master 3)"},
        {"object": "FENCE_HI", "pos": [130.5, 0.0, -93.0],
         "rot0": [0, 0, 0], "driver": "fallOnce",
         "rotLimit": 90.0, "vyMax": 15.0,
         "eventGate": 320, "chunkGate": ["3|4", -3],
         "sound": "Sfx_Unk1555",
         "src": "map4_s03.c:1692-1716, 1637"},
    ],
    # ---- map4_s04 hospital-nowhere wake-up chair (map4_s04_2.c) ----
    "MAP4_S04": [
        {"object": "ISU_HIDE", "pos": [57.8, 0.0, 141.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "wake-up cutscene discrete steps: g_WorldObject0."
                "position.vz = 141.0 (map4_s04_2.c:340) -> 140.8 (:372) -> "
                "140.95 (:396); PlacementInit (57.8,0,0) at :681 — the "
                "placement z is dead data, the chair only ever draws "
                "during/after the cutscene steps (added in chunk (1,3) "
                "while Get(337) && !Get(338), :691-697)",
         "eventGate": 337, "eventGatePolarity": "set",
         "eventGateAlt": 338, "eventGateAltPolarity": "clear",
         "cutsceneOnly": True,
         "chunkGate": [1, 3],
         "src": "map4_s04_2.c:681 (init), 340, 372, 396 (vz steps), "
                "691-697 (add); flag 337 set by the map4_s01 event "
                "(map4_s01/map_events.c), 338 set at cutscene end "
                "(map4_s04_2.c:420)"},
    ],
    # ---- map5_s03 roaches (map5_s03_2.c:664-693, 712, 743) ----
    "MAP5_S03": [
        {"object": "MOVACHES", "pos": [104.2225, -0.1683, 60.0667],
         "rot0": [0, 0, 0], "driver": "translate",
         "axis": "z", "speed": 0.14, "clampState5": 60.35,
         "clampState6": 60.44,
         "cutscene": "player+object co-move (map5_s03_2.c:664-693)",
         "chunkGate": [2, 1], "sound": "Sfx_Unk1520/1538",
         "src": "map5_s03_2.c:664-693, 710-791"},
    ],
    # ---- map5_s00 ripples: NON-WorldObject 2D (12 particles) ----
    "MAP5_S00": [
        {"object": "<ripples>", "driver": "waterRipple",
         "count": 12, "box": [-92.75, -91.25, 7.35, 8.85], "y": 0.5,
         "walkMin": -32, "walkMax": 31, "tMax": 4095,
         "halfSizeK": 1.5, "clutBase": 160, "clutSel": 3,
         "gate": "player x<=-80 z>=0 AND !(flashlightAllowed&&darkness)",
         "src": "map5_s00.c:20-48, 89-94, 154-157"},
    ],
    # ---- map5_s02 green-lion safe door (map5_s02_2.c) ----
    "MAP5_S02": [
        {"object": "BDOOR1_H", "pos": [134.5318, 0.0, 59.471],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "safe cutscene discrete steps: g_WorldObject_BDoor1"
                ".rotation.vy = Q12_ANGLE(-142.21deg) (map5_s02_2.c:290 "
                "and :363) then -7.5deg (:311 and :388); re-entry state "
                "rot.vy=-7.5 while Get(M5S02_UsedSafeKey) (:884-887); added "
                "in chunk (3,1) unconditionally (:901, :928)",
         "chunkGate": [3, 1],
         "src": "map5_s02_2.c:861 (WorldObject_Init \"BDOOR1_H\", "
                "134.5318, 0.0, 59.471, 0,0,0), 884-887, 290, 311, 363, "
                "388, 901, 928"},
    ],
    # ---- map6_s03 corpse (map6_s03.c:377-444) ----
    "MAP6_S03": [
        {"object": "SITAI_NE", "pos": [75.0, 0.5, 19.7],
         "rot0": [0, 180.0, 0], "driver": "rngWalk",
         "rotBase": 0x800, "vzBase": 19.7, "dirMask": 0x1F, "dirBias": 0x20,
         "vzStep": "rand%5-2", "chunkGate": [1, 0],
         "sound": "Sfx_Unk1614",
         "src": "map6_s03.c:377-444"},
    ],
    # ---- map6_s04 the amusement park (carousel + ferris wheel + the
    # 12-seat spinning carnival ride; user-classified "carnival rides") --
    # CAROUSEL VERDICT (S20 decomp audit, user question "is the camera ON
    # the carousel?"): BOTH, in different contexts. Normal play incl. the
    # Cybil fight: the platform/canopy/fence ring ROTATE IN WORLD SPACE
    # (one shared accumulator D_800ED5B6, masked 0xFFF; rate = D_800EBA30
    # + D_800ED5B4 — fresh 0, fight -455 ~= -40deg/s, ending -122) and
    # the horses stay at FIXED xz/yaw (extern tables D_800EBAAC/EBAD4/
    # EBAFC), only bobbing +/-0.2 (map6_s04_2.c:3615-3643). The ENDING
    # CUTSCENE steps 22-27 (func_800E3244, map6_s04_2.c:2684-2697): the
    # camera ORBITS the center (20,-2,100) at radius 5.2 driven by the
    # SAME accumulator + the light rides along (radius 4.8, yaw+182.9)
    # — so the platform is static in camera space and the ENVIRONMENT
    # appears to rotate (the user's memory). No GsInitCoordinate2/RotMatrix
    # world rotation anywhere in map6_s04. Speed 0 at engine-fresh: the
    # carousel stands still until the boss fight / the ending. ---------
    # The 10 carousel horse slots (map6_s04_2.c:3615-3644): i<6 ride
    # g_WorldObject0[1] = UMA2_HID (phase i*4096/3), i>=6 ride
    # g_WorldObject0[0] = UMA1_HID (phase i*2048+2048) — the MODEL split
    # is per the WorldObjects_Add(&g_WorldObject0[var_a0_2]) index at
    # :3641 (var_a0_2 = 1 for i<6, 0 for i>=6).
    "MAP6_S04": [
        {"object": "UMA2_HID", "driver": "sineBob",
         "count": 6, "instRange": [0, 5],
         "posPerInst": [[24.0, 0.0, 105.2], [26.5, 0.0, 99.15],
                        [22.5, 0.0, 93.95], [16.0, 0.0, 94.8],
                        [13.5, 0.0, 100.85], [17.5, 0.0, 106.05]],
         "rot0PerInst": [[0, 37.529296875, 0], [0, 157.5, 0],
                         [0, 277.470703125, 0], [0, 15.029296875, 0],
                         [0, 195.029296875, 0], [0, 0.0, 0]],
         "phaseFormula": "Math_Sin((D_800ED5B6*4) + (Q12(1.0f)*i)/3) — "
                 "map6_s04_2.c:3628 (the i<6 branch; var_a0_2=1 -> "
                 "g_WorldObject0[1] = UMA2_HID, :3430/:3641)",
         "phasePerInst": [0, 1365, 2730, 4096, 5461, 6826],
         "bobDiv": 5, "angleMul": 4, "carousel": "D_800ED5B6",
         "speedSrc": "D_800EBA30 (0) + D_800ED5B4 (0; -0x7A=-122 after "
                     "Cybil, map6_s04_2.c:2611) - BOTH terms add each tick "
                     "(3549-3550), then &0xFFF",
         "data": "posPerInst/rot0PerInst = D_800EBAAC/EBAD4/EBAFC[0..5] "
                 "decoded VERBATIM from VIN/MAP6_S04.BIN (overlay base "
                 "0x800C9578; the offsets + the base (20,0,100) "
                 "Q12, map6_s04_2.c:3617-3618/3420-3422)",
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3430, 3619-3648, 3553-3554, 3549"},
        {"object": "UMA1_HID", "driver": "sineBob",
         "count": 4, "instRange": [6, 9],
         "posPerInst": [[20.8, 0.0, 103.05], [23.0, 0.0, 99.2],
                        [19.2, 0.0, 96.95], [17.0, 0.0, 100.8]],
         "rot0PerInst": [[0, 0.0, 0], [0, 0.0, 0], [0, 0.0, 0], [0, 0.0, 0]],
         "phaseFormula": "Math_Sin((D_800ED5B6*4) + (Q12(1.0f)*i)/2 + "
                 "Q12(0.5f)) — map6_s04_2.c:3634-3635 (the i>=6 branch; "
                 "var_a0_2=0 -> g_WorldObject0[0] = UMA1_HID, :3429/:3641)",
         "phasePerInst": [14336, 16384, 18432, 20480],
         "bobDiv": 5, "angleMul": 4, "carousel": "D_800ED5B6",
         "speedSrc": "D_800EBA30 (0) + D_800ED5B4 (0; -0x7A=-122 after "
                     "Cybil, map6_s04_2.c:2611) - BOTH terms add each tick "
                     "(3549-3550), then &0xFFF",
         "data": "posPerInst/rot0PerInst = D_800EBAAC/EBAD4/EBAFC[6..9] "
                 "decoded VERBATIM from VIN/MAP6_S04.BIN (overlay base "
                 "0x800C9578; the offsets + the base (20,0,100) "
                 "Q12, map6_s04_2.c:3617-3618/3420-3422)",
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3429, 3619-3648, 3553-3554, 3549"},
        {"object": "MGR_KOYA", "pos": [20.0, 1.0, 100.0],
         "rot0": [0, 0, 0], "driver": "carouselSpin",
         "radius": 8.0, "chunkGate": [0, 2],
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3650-3697, 3549"},
        {"object": "MGR_STR_", "pos": [20.0, 1.0, 100.0],
         "rot0": [0, 11.25, 0], "driver": "carouselSpin",
         "rotOffsetDeg": 11.25,
         "rotFormula": "rot.vy = D_800ED5B6 + Q12_ANGLE(11.25) — same pos "
                "as MGR_KOYA (map6_s04_2.c:3662-3664)",
         "radius": 8.0, "chunkGate": [0, 2],
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3432, 3662-3664, 3549"},
        {"object": "SAKU2_BA", "pos": [20.0, -0.3, 100.0],
         "rot0": [0, 90.0, 0], "driver": "carouselSpin",
         "rotOffsetDeg": 90.0,
         "rotFormula": "rot.vy = D_800ED5B6 + Q12_ANGLE(90) — the i==0 "
                "spoke of the 8-spoke fence ring (map6_s04_2.c:3667-3693); "
                "added at the HUB pos (20,-0.3,100), the ring sectors "
                "(radius 7.5) live in the model geometry",
         "radius": 7.5, "chunkGate": [0, 2],
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3433, 3667-3693, 3549"},
        {"object": "SAK_POL_", "pos": [20.0, 0.0, 100.0],
         "rot0": [0, 90.0, 0], "driver": "carouselSpin",
         "count": 7, "instRange": [1, 7],
         "rotStepDeg": 45.0,
         "rotFormula": "rot.vy = D_800ED5B6 + Q12_ANGLE(90) + i*Q12_ANGLE(45) "
                "for the 7 fence-pole sectors i=1..7 (map6_s04_2.c:3670-3697; "
                "the 8th sector, i==0, is the SAKU2_BA gate); pos.y=0 from "
                "the 2nd add on (:3695), all added at the HUB pos (20,0,100)",
         "posPerInst": [[20.0, 0.0, 100.0]] * 7,
         "radius": 7.5, "chunkGate": [0, 2],
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3434, 3670-3697, 3549"},
        {"object": "MGR_DRL_", "pos": [20.0, 0.0, 100.0],
         "rot0": [0, 0, 0], "driver": "carouselSpin",
         "count": 4, "rotStepDeg": 90.0,
         "rotFormula": "rot.vy = D_800ED5B6 + i*Q12_ANGLE(90) — 4 doll "
                "adds (map6_s04_2.c:3699-3720), each ALSO adds DRL2_ILI; "
                "both models added at &D_800ED740 = (20,0,100) (the hub "
                "pos; the 0.8 ring is only the visibility AABB)",
         "posPerInst": [[20.0, 0.0, 100.0]] * 4,
         "radius": 0.8, "chunkGate": [0, 2],
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3436, 3699-3720, 3549"},
        {"object": "DRL2_ILI", "pos": [20.0, 0.0, 100.0],
         "rot0": [0, 0, 0], "driver": "carouselSpin",
         "count": 4, "rotStepDeg": 90.0,
         "rotFormula": "rot.vy = D_800ED5B6 + i*Q12_ANGLE(90) — 4 adds "
                "paired with MGR_DRL_ at the same pose "
                "(map6_s04_2.c:3714-3716)",
         "posPerInst": [[20.0, 0.0, 100.0]] * 4,
         "radius": 0.8, "chunkGate": [0, 2],
         "gate": "!Get(443) || Get(467) — the whole carousel/horse "
                "block runs while the compound holds (map6_s04_2.c:3549)",
         "src": "map6_s04_2.c:3437, 3699-3720, 3549"},
        {"object": "CHAIR_HI", "pos": [22.8, 0.0, 96.6],
         "rot0": [0, -42.28, 0], "driver": "cutscene",
         "cutscene": "STATIC carousel chair (Math_SetSVectorFastSum rot "
                "y 0xFE1F = -481 raw q3.12; drawn while D_800ED5B8 == 0 — "
                "vanishes after the AMUSE1 case 21)",
         "src": "map6_s04_2.c:3722-3731"},
        {"object": "FW1_BACK", "pos": [8.7, -13.8, -28.0],
         "rot0": [0, 0, 0], "driver": "ferrisWheel",
         "rateRaw": 186413, "rateDegPS": 4.0, "wrapRaw": 1258291,
         "wrapDeg": 27.0, "wrapPeriodS": 6.75, "arms": 5,
         "armStepRaw": 307, "armStepDeg": 27.0, "arm0Raw": -739,
         "arm0Deg": -65.0, "boxRadius": [10.0, 11.25],
         "pendVelRaw": -279620, "pendVelDegPS": -6.0,
         "pendVelFloorRaw": -139810, "pendVelFloorDegPS": -3.0,
         "pendSettleRaw": -93206, "pendSettleDeg": -2.0,
         "eventGate": 452, "eventGatePolarity": "clear",
         "driveGate": "!Get(452) && PLAYER_NEAR_POS(vx,8.0,20.0) && "
                "PLAYER_NEAR_POS(vz,-28.0,22.0) && AABB visible "
                "(map6_s04_2.c:3496-3500)",
         "src": "map6_s04_2.c:3439, 3735-3846"},
        {"object": "FW2_BACK", "pos": [8.7, -13.8, -28.0],
         "rot0": [0, 0, 0], "driver": "ferrisWheel",
         "rateRaw": 186413, "rateDegPS": 4.0, "wrapRaw": 1258291,
         "wrapDeg": 27.0, "wrapPeriodS": 6.75, "arms": 5,
         "armStepRaw": 307, "armStepDeg": 27.0, "arm0Raw": -739,
         "arm0Deg": -65.0, "boxRadius": [10.0, 11.25],
         "eventGate": 452, "eventGatePolarity": "clear",
         "driveGate": "!Get(452) && PLAYER_NEAR_POS(vx,8.0,20.0) && "
                "PLAYER_NEAR_POS(vz,-28.0,22.0) && AABB visible "
                "(map6_s04_2.c:3496-3500)",
         "src": "map6_s04_2.c:3440, 3817-3827 (all three backing models "
                "added at each of the 5 arm poses)"},
        {"object": "FW3WIR_H", "pos": [8.7, -13.8, -28.0],
         "rot0": [0, 0, 0], "driver": "ferrisWheel",
         "rateRaw": 186413, "rateDegPS": 4.0, "wrapRaw": 1258291,
         "wrapDeg": 27.0, "wrapPeriodS": 6.75, "arms": 5,
         "armStepRaw": 307, "armStepDeg": 27.0, "arm0Raw": -739,
         "arm0Deg": -65.0, "boxRadius": [10.0, 11.25],
         "eventGate": 452, "eventGatePolarity": "clear",
         "driveGate": "!Get(452) && PLAYER_NEAR_POS(vx,8.0,20.0) && "
                "PLAYER_NEAR_POS(vz,-28.0,22.0) && AABB visible "
                "(map6_s04_2.c:3496-3500)",
         "src": "map6_s04_2.c:3441, 3817-3827 (all three backing models "
                "added at each of the 5 arm poses)"},
        {"object": "FWBOX1_B", "pos": [8.7, -13.8, -28.0],
         "rot0": [0, 0, 0], "driver": "ferrisWheel", "cabin": True,
         "rateRaw": 186413, "rateDegPS": 4.0, "wrapRaw": 1258291,
         "wrapDeg": 27.0, "wrapPeriodS": 6.75, "arms": 5,
         "armStepRaw": 307, "armStepDeg": 27.0, "arm0Raw": -739,
         "arm0Deg": -65.0, "boxRadius": [10.0, 11.25],
         "cabinRadius": 11.25,
         "pendVelRaw": -279620, "pendVelDegPS": -6.0,
         "pendVelFloorRaw": -139810, "pendVelFloorDegPS": -3.0,
         "pendSettleRaw": -93206, "pendSettleDeg": -2.0,
         "pendulum": "cabin pendulum (3 branches, map6_s04_2.c:3764-3811): "
                "idle timer, vel += dt*Q12(-68.2667) floored -34.1334, "
                "angle += dt*vel, settle -22.7554 else vel >>= 1; rot.vx = "
                "D_800EBB10[i]>>12 (:3832)",
         "parity": "g_WorldObject7[(D_800EBB34+i)&1] — the wrap counter "
                "D_800EBB34 + arm index selects FWBOX1_B (even) vs "
                "FWBOX2_B (odd) at each arm (map6_s04_2.c:3841); t=0 "
                "(D_800EBB34=0): arms 0,2,4",
         "eventGate": 452, "eventGatePolarity": "clear",
         "driveGate": "!Get(452) && PLAYER_NEAR_POS(vx,8.0,20.0) && "
                "PLAYER_NEAR_POS(vz,-28.0,22.0) && AABB visible "
                "(map6_s04_2.c:3496-3500)",
         "src": "map6_s04_2.c:3442, 3764-3842"},
        {"object": "FWBOX2_B", "pos": [8.7, -13.8, -28.0],
         "rot0": [0, 0, 0], "driver": "ferrisWheel", "cabin": True,
         "rateRaw": 186413, "rateDegPS": 4.0, "wrapRaw": 1258291,
         "wrapDeg": 27.0, "wrapPeriodS": 6.75, "arms": 5,
         "armStepRaw": 307, "armStepDeg": 27.0, "arm0Raw": -739,
         "arm0Deg": -65.0, "boxRadius": [10.0, 11.25],
         "cabinRadius": 11.25,
         "pendVelRaw": -279620, "pendVelDegPS": -6.0,
         "pendVelFloorRaw": -139810, "pendVelFloorDegPS": -3.0,
         "pendSettleRaw": -93206, "pendSettleDeg": -2.0,
         "pendulum": "cabin pendulum (3 branches, map6_s04_2.c:3764-3811): "
                "idle timer, vel += dt*Q12(-68.2667) floored -34.1334, "
                "angle += dt*vel, settle -22.7554 else vel >>= 1; rot.vx = "
                "D_800EBB10[i]>>12 (:3832)",
         "parity": "g_WorldObject7[(D_800EBB34+i)&1] — the wrap counter "
                "D_800EBB34 + arm index selects FWBOX1_B (even) vs "
                "FWBOX2_B (odd) at each arm (map6_s04_2.c:3841); t=0 "
                "(D_800EBB34=0): arms 1,3",
         "eventGate": 452, "eventGatePolarity": "clear",
         "driveGate": "!Get(452) && PLAYER_NEAR_POS(vx,8.0,20.0) && "
                "PLAYER_NEAR_POS(vz,-28.0,22.0) && AABB visible "
                "(map6_s04_2.c:3496-3500)",
         "src": "map6_s04_2.c:3443, 3764-3842"},
        {"object": "WHEEL_BA", "pos": [-16.0, -1.5, -64.0],
         "rot0": [0, 0, 0], "driver": "lissajousOrbit",
         "count": 12, "freqARaw": 807, "freqBRaw": 1126,
         "freqADegPS": 70.9, "freqBDegPS": 99.0, "radius": 4.0,
         "yOff": -1.5, "angleDiv": 30, "eventGate": 453,
         "eventGatePolarity": "clear",
         "label": "the 12-seat spinning carnival ride (the ride "
                  "capsules orbit the center at radius 4, bobbing "
                  "+/-4 y — user-classified 'carnival rides', the "
                  "'balloons' label was wrong)",
         "src": "map6_s04_2.c:3844-3871; gate :3498-3506 (!Get(453) — drive-while-CLEAR, live at engine-fresh)"},
    ],
    # ---- map7 nowhere (stones, beans, bin, belt) ----
    "MAP7_S00": [
{"object": "DR1R_HID", "pos": [60.8, 0.0, -137.45],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "gateDoor slide (the SIX-door set, shared "
                "D_800D4370 z-states; state slot D_800D4370[0] (i>=2 reads i-2, map7_s00_2.c:770))",
         "chunkGate": [1, -4], "sound": "Sfx_Unk1640",
         "src": "map7_s00_2.c:727-740, 764-773"},
        {"object": "DR1L_HID", "pos": [60.8, 0.0, -137.45],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "gateDoor slide (the SIX-door set, shared "
                "D_800D4370 z-states; state slot D_800D4370[1])",
         "chunkGate": [1, -4], "sound": "Sfx_Unk1640",
         "src": "map7_s00_2.c:727-740, 764-773"},
        {"object": "DR2R_HID", "pos": [60.8, 0.0, -137.45],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "gateDoor slide (the SIX-door set, shared "
                "D_800D4370 z-states; state slot D_800D4370[2] "
                "(i=4 reads i-2, map7_s00_2.c:770))",
         "chunkGate": [1, -4], "sound": "Sfx_Unk1640",
         "src": "map7_s00_2.c:727-740, 764-773"},
        {"object": "DR2L_HID", "pos": [60.8, 0.0, -137.45],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "gateDoor slide (the SIX-door set, shared "
                "D_800D4370 z-states; state slot D_800D4370[3] "
                "(i=5 reads i-2, map7_s00_2.c:770))",
         "chunkGate": [1, -4], "sound": "Sfx_Unk1640",
         "src": "map7_s00_2.c:727-740, 764-773"},
        {"object": "DR3R_HID", "pos": [60.8, 0.0, -137.45],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "gateDoor slide: slot 0 (i=0, even) += dt*vel "
                "clamp Q12(-129.45) (map7_s00_2.c:570-586)",
         "chunkGate": [1, -4], "sound": "Sfx_Unk1640",
         "src": "map7_s00_2.c:556-588, 728-740, 764-773"},
        {"object": "DR3L_HID", "pos": [60.8, 0.0, -137.45],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "gateDoor slide: slot 1 (i=1, odd) -= dt*vel "
                "clamp Q12(-145.45) (map7_s00_2.c:570-586)",
         "chunkGate": [1, -4],
         "src": "map7_s00_2.c:556-588, 728-740, 764-773"},
    ],
    "MAP7_S01": [
        {"object": "STONE1_H", "pos": [-139.5, -1.35, -140.6],
         "rot0": [0, 90.0, 0], "driver": "stoneChoreo",
         "states": [
             {"slide": "vz = (step*409)/8192 - 575897 (case 1)"},
             {"drop": "vel += g>>1 (5209/tick); vy clamps at -4300"},
             {"wobble": "rotZ -= 284/s; vy = cos(rotZ)*614 - 4914; vz = sin(rotZ)*(-614) - 575488; 0.5s"},
             {"tumble": "vel += 10419; rotZ -= 1365/s; vy += vel*dt; vz += 1228/s; until vy >= 0"},
             {"rest": "pos (-139.5,-0.05,-140.0) rotZ -1024"}],
         "sound": "Sfx_Unk1647/1648/1649",
         "src": "map7_s01_2.c:1545-1596, 2188-2195"},
        {"object": "DR1L_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 0, "axis": "z",
         "speed": 0.1, "accel": 0.25, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "levitating-door cutscene (local, "
                "map7_s01_2.c:2081-2136): case 2 moves the outer 4 "
                "doors, cases 3/4 all 6; vz += dt*(i&1 ? +D_800E16A8[k] : "
                "-D_800E16A8[k]), accel dt*Q12(0.25) clamped Q12(0.1); the "
                "shared elevator slide (0.35/0.8) is ALSO compiled in "
                "(map7_s01_2.c:2052 include); positions reset to "
                "(-100.9,0,-60.9) at the end (:2134) — also the post-479 "
                "PlacementInit pose (:2220-2225; pre-479 it is "
                "(-20.9,0,-20.9), :2229-2234)",
         "slideSign": "-vz (i=0, even)",
         "src": "map7_s01_2.c:2074-2105, 2081-2136, 2218-2235, "
                "2495-2501 (add chunks (-1,-1)/(-3,-2))"},
        {"object": "DR1R_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 1, "axis": "z",
         "speed": 0.1, "accel": 0.25, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"], "dir": -1,
         "cutscene": "levitating-door cutscene (local, "
                "map7_s01_2.c:2081-2136) — outer set i<4, slideSign +vz "
                "(i odd, :2086/:2104)",
         "slideSign": "+vz (i=1, odd)",
         "src": "map7_s01_2.c:2074-2105, 2081-2136, 2218-2235, 2495-2501"},
        {"object": "DR3L_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 2, "axis": "z",
         "speed": 0.1, "accel": 0.25, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "levitating-door cutscene (local, "
                "map7_s01_2.c:2081-2136) — outer set i<4, slideSign -vz "
                "(i even, :2086/:2104); PLUS the shared elevator ride "
                "states 14-16 (sharedFunc_800D15F0_3_s01.h:331-365 via "
                "map7_s01_2.c:2052)",
         "slideSign": "-vz (i=2, even)",
         "src": "map7_s01_2.c:2222 (init), 2081-2136, 2495-2501, "
                "sharedFunc_800D15F0_3_s01.h:331-365"},
        {"object": "DR3R_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 3, "axis": "z",
         "speed": 0.1, "accel": 0.25, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "levitating-door cutscene (local, "
                "map7_s01_2.c:2081-2136) — outer set i<4, slideSign +vz "
                "(i odd, :2086/:2104); PLUS the shared elevator ride "
                "states 14-16 (sharedFunc_800D15F0_3_s01.h:331-365)",
         "slideSign": "+vz (i=3, odd)",
         "src": "map7_s01_2.c:2223 (init), 2081-2136, 2495-2501, "
                "sharedFunc_800D15F0_3_s01.h:331-365"},
        {"object": "DR2L_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 4, "axis": "z",
         "speed": 0.1, "accel": 0.25, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "levitating-door cutscene (local, "
                "map7_s01_2.c:2081-2136) — inner set i>=4 moves only from "
                "case 3 on (D_800E16A8[1], :2100-2105); PLUS the shared "
                "elevator ride states 15-16 (inner set, "
                "sharedFunc_800D15F0_3_s01.h:342-355)",
         "slideSign": "-vz (i=4, even)",
         "src": "map7_s01_2.c:2224 (init), 2081-2136, 2495-2501, "
                "sharedFunc_800D15F0_3_s01.h:331-365"},
        {"object": "DR2R_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 5, "axis": "z",
         "speed": 0.1, "accel": 0.25, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "levitating-door cutscene (local, "
                "map7_s01_2.c:2081-2136) — inner set i>=4 from case 3 on "
                "(:2100-2105); PLUS the shared elevator ride states 15-16 "
                "(inner set, sharedFunc_800D15F0_3_s01.h:342-355)",
         "slideSign": "+vz (i=5, odd)",
         "src": "map7_s01_2.c:2225 (init), 2081-2136, 2495-2501, "
                "sharedFunc_800D15F0_3_s01.h:331-365"},
    ],
    "MAP7_S02": [
        {"object": "BEAN1_HI", "pos": [62.3, -1.4, -61.0],
         "objectPerInst": ["BEAN%d_HI" % (i // 2 + 1) for i in range(16)],
         "objectPerInstSrc": "map7_s02_2.c:3476-3479: beanObjName[4] = "
                "(i >> 1) + '1' — TWO beans per model, BEAN1_HI..BEAN8_HI",
         "initRangeY": [-1.45, -1.3501], "initRangeZ": [-61.07, -60.93],
         "rot0": "rand16(0..4095)", "driver": "gravityScatter",
         "count": 16, "scatterAmp": 2.2, "gravityRaw": 10419,
         "gravityUnits": "H_BLANKS_GRAVITY_SCALE Q12(9.8*0.25956907477)="
                "10419 raw per H-BLANK; the per-tick velocity increment is "
                "g_GravitySpeed = Q12_MULT(vCount,10419) = 1336 raw at the "
                "30Hz tick (vCount 526) — game_main.c:132-137,295",
         "vyClampRaw": 20480, "floorY": 0.0,
         "scatterInit": "amp[i] = FP_FROM(sin(Rng(0,511)|0x200)*Q12(2.2), 12); angle[i] = Rng(0,4095)",
         "cutsceneOnly": True,
         "cutsceneSrc": "map7_s02_2.c:1093-1210: the beans are added ONLY "
                "inside the bag cutscene (case 14 loops until "
                "floorHitCount==16; engine-fresh they never draw)",
         "sound": "Sfx_Unk1662/1651",
         "src": "map7_s02_2.c:1170-1189, 3476-3488"},
        # STONE2_H — v28.1 FIX (audit A M1, re-verified): the previous pos
        # [-139.5,-1.35,-140.6] + rot0 [0,90,0] were FABRICATED (copied from
        # map7_s01's STONE1_H at map7_s01_2.c:2194). D_800EBB64 is
        # extern-only in the repo (map7_s02.h:104; binary .data @
        # 0x800EDF08 per sym.map7_s02.txt:402) and there is NO
        # WorldObjects_Add for it anywhere — the only pos values the decomp
        # pins are the slide-start vz -140.6 (:2687) and the rest pose
        # (-139.5,-0.05,-140.0) rotZ -0.25 (:2737-2740). No posed node is
        # emitted (pos=None => manifest-only; cutsceneOnly suppresses
        # consumer draw).
        {"object": "STONE2_H", "pos": None,
         "rot0": None, "driver": "stoneChoreo",
         "initPose": "BINARY-ONLY: s_WorldObjectPose D_800EBB64 @ "
                "0x800EDF08 (extern map7_s02.h:104) — the initial pos/rot "
                "are NOT in the decomp repo; the choreography pins only "
                "the slide-start vz -140.6 (map7_s02_2.c:2687) and the "
                "final rest pose (-139.5,-0.05,-140.0) rotZ -0.25 "
                "(:2737-2740)",
         "cutscene": "stoneChoreo (map7_s02_2.c:2662-2745): slide "
                "vz=(step*0.1)/2-140.6; drop vel += g_GravitySpeed>>1, vy "
                "clamp -1.05; wobble rot.vz += dt*Q12(-0.0694)=-284 raw "
                "(:2710), vy=cos(rotZ)*0.15-(1.2-1), vz=sin(rotZ)*(-0.15)"
                "-140.5; tumble rot.vz += dt*Q12(-0.3333)=-1365 raw "
                "(:2724), vy += vel*dt, vz += dt*0.3; model swaps "
                "STONE2_H->STONE3_H at step 1 end (:2681); NEVER "
                "WorldObjects_Add'ed in the decomp (no add call exists)",
         "cutsceneOnly": True,
         "src": "map7_s02_2.c:2662-2745 (rates :2710/:2724; model swap "
                ":2681; rest :2737-2740), map7_s02.h:104, "
                "sym.map7_s02.txt:402"},
        # ---- the nowhere elevator doors (6; the same shared set that
        # map7_s01's levitating-door cutscene slides) — the SHARED
        # elevator slide code is compiled in (map7_s02_2.c:3153 include)
        # and IS invokable here: map event [153] (map_events.c:1444-1451,
        # TouchObbFacing+Button at mapPoint 23 (-102.5,-59.5) — right at
        # the doors at -100.9/0/-60.9, map7_s02/map_points.h:158-164)
        # enters SysState_EventCallback with eventParam 42 →
        # g_MapEventFuncs[42] = sharedFunc_800D15F0_3_s01 (header.c:71
        # registration; game_sys_states.c:818 dispatch) — the elevator
        # ride cutscene slides the doors (states 14-16) and resets vz to
        # -60.9 on exit (shared default case, :385-391). The flag-549-
        # gated examine event [154] (MAP_MSG(132) "The elevator doesn't
        # appear to be working", map7_s02_2.c:226) is the BROKEN-elevator
        # message at mapPoint 14. Engine-fresh (no event run) the doors
        # sit closed at the authored pose, added in chunks
        # (-1,-1)/(-3,-2) (map7_s02_2.c:3727-3733).
        {"object": "DR1L_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 0, "axis": "z",
         "speed": 0.35, "accel": 0.8, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365 via map7_s02_2.c:3153; "
                "invoked by map event [153] — TouchObbFacing+Button at "
                "mapPoint 23 (-102.5,-59.5) → eventParam 42 = "
                "sharedFunc_800D15F0_3_s01 (map_events.c:1444-1451, "
                "header.c:71); vz resets to -60.9 on exit "
                "(shared default :385-391))",
         "slideSign": "-vz (i=0, even)",
         "src": "map7_s02_2.c:3507, 3728-3733 (add chunks (-1,-1)/"
                "(-3,-2)), sharedFunc_800D15F0_3_s01.h:331-365, "
                "map7_s02.h:109"},
        {"object": "DR1R_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 1, "axis": "z",
         "speed": 0.35, "accel": 0.8, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365 via map7_s02_2.c:3153; "
                "invoked by map event [153] — TouchObbFacing+Button at "
                "mapPoint 23 (-102.5,-59.5) → eventParam 42 = "
                "sharedFunc_800D15F0_3_s01 (map_events.c:1444-1451, "
                "header.c:71); vz resets to -60.9 on exit "
                "(shared default :385-391))",
         "slideSign": "+vz (i=1, odd)",
         "src": "map7_s02_2.c:3508, 3728-3733, sharedFunc_800D15F0_3_s01.h:"
                "331-365, map7_s02.h:109"},
        {"object": "DR3L_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 2, "axis": "z",
         "speed": 0.35, "accel": 0.8, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365 via map7_s02_2.c:3153; "
                "invoked by map event [153] — TouchObbFacing+Button at "
                "mapPoint 23 (-102.5,-59.5) → eventParam 42 = "
                "sharedFunc_800D15F0_3_s01 (map_events.c:1444-1451, "
                "header.c:71); vz resets to -60.9 on exit "
                "(shared default :385-391))",
         "slideSign": "-vz (i=2, even)",
         "src": "map7_s02_2.c:3509, 3728-3733, sharedFunc_800D15F0_3_s01.h:"
                "331-365, map7_s02.h:109"},
        {"object": "DR3R_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 3, "axis": "z",
         "speed": 0.35, "accel": 0.8, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "elevator ride states 14-16 (shared code, "
                "sharedFunc_800D15F0_3_s01.h:331-365 via map7_s02_2.c:3153; "
                "invoked by map event [153] — TouchObbFacing+Button at "
                "mapPoint 23 (-102.5,-59.5) → eventParam 42 = "
                "sharedFunc_800D15F0_3_s01 (map_events.c:1444-1451, "
                "header.c:71); vz resets to -60.9 on exit "
                "(shared default :385-391))",
         "slideSign": "+vz (i=3, odd)",
         "src": "map7_s02_2.c:3510, 3728-3733, sharedFunc_800D15F0_3_s01.h:"
                "331-365, map7_s02.h:109"},
        {"object": "DR2L_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 4, "axis": "z",
         "speed": 0.35, "accel": 0.8, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "elevator ride states 15-16 (shared code, inner set "
                "i>=4, sharedFunc_800D15F0_3_s01.h:342-355 via "
                "map7_s02_2.c:3153; invoked by map event [153] — "
                "TouchObbFacing+Button at mapPoint 23 (-102.5,-59.5) → "
                "eventParam 42 = sharedFunc_800D15F0_3_s01 "
                "(map_events.c:1444-1451, header.c:71); vz resets to "
                "-60.9 on exit (shared default :385-391))",
         "slideSign": "-vz (i=4, even)",
         "src": "map7_s02_2.c:3511, 3728-3733, sharedFunc_800D15F0_3_s01.h:"
                "331-365, map7_s02.h:109"},
        {"object": "DR2R_HID", "pos": [-100.9, 0.0, -60.9],
         "rot0": [0, 0, 0], "driver": "slideDoor", "slideIdx": 5, "axis": "z",
         "speed": 0.35, "accel": 0.8, "resetZ": -60.9,
         "chunkGate": ["-1|-3", "-1|-2"],
         "cutscene": "elevator ride states 15-16 (shared code, inner set "
                "i>=4, sharedFunc_800D15F0_3_s01.h:342-355 via "
                "map7_s02_2.c:3153; invoked by map event [153] — "
                "TouchObbFacing+Button at mapPoint 23 (-102.5,-59.5) → "
                "eventParam 42 = sharedFunc_800D15F0_3_s01 "
                "(map_events.c:1444-1451, header.c:71); vz resets to "
                "-60.9 on exit (shared default :385-391))",
         "slideSign": "+vz (i=5, odd)",
         "src": "map7_s02_2.c:3512, 3728-3733, sharedFunc_800D15F0_3_s01.h:"
                "331-365, map7_s02.h:109"},
        # ---- dagger-room doors (EventFlag_557) ----
        {"object": "DOR1_HID", "pos": [21.15, -0.8, -60.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "dagger-room doors fly open (EventFlag_557 set): "
                "rotation.vy = Q12_ANGLE(+25deg) at cutscene step 5 "
                "(map7_s02_2.c:1546); added in chunk (0,-2) only while "
                "Get(557) (:3593-3600)",
         "eventGate": 557, "eventGatePolarity": "set",
         "chunkGate": [0, -2],
         "src": "map7_s02_2.c:3467 (init 21.15/-0.8/-60.0), 1546, "
                "3593-3600"},
        {"object": "DOR2_HID", "pos": [21.15, -0.1, -60.0],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "dagger-room doors fly open: rotation.vy = "
                "Q12_ANGLE(+58deg) (map7_s02_2.c:1547); added in chunk "
                "(0,-2) while Get(557)",
         "eventGate": 557, "eventGatePolarity": "set",
         "chunkGate": [0, -2],
         "src": "map7_s02_2.c:3468, 1547, 3593-3600"},
        {"object": "DOR3_HID", "pos": [21.15, -0.1, -61.5],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "dagger-room doors fly open: rotation.vy = "
                "Q12_ANGLE(-50deg) (map7_s02_2.c:1548); added in chunk "
                "(0,-2) while Get(557)",
         "eventGate": 557, "eventGatePolarity": "set",
         "chunkGate": [0, -2],
         "src": "map7_s02_2.c:3469, 1548, 3593-3600"},
        {"object": "DOR4_HID", "pos": [21.15, -0.8, -61.5],
         "rot0": [0, 0, 0], "driver": "cutscene",
         "cutscene": "dagger-room doors fly open: rotation.vy = "
                "Q12_ANGLE(-15deg) (map7_s02_2.c:1549); added in chunk "
                "(0,-2) while Get(557)",
         "eventGate": 557, "eventGatePolarity": "set",
         "chunkGate": [0, -2],
         "src": "map7_s02_2.c:3470, 1549, 3593-3600"},
    ],
    "MAP7_S03": [
        {"object": "BIN_HIDE", "pos": [140.0, 0.0, -100.0],
         "rot0": [0, 0, 0], "driver": "binSpin",
         "cutscene": "binSpin rot.vx = D_800F482C; -= Q12_DIV(dt, Q12(3.6))"
                " = 100 deg/s (map7_s03_3.c:8238-8245); runs while "
                "g_Cutscene_UpdateBin (step 21 :6291-6306) — DEMO-gated",
         "src": "map7_s03_3.c:8240-8245, 6296-6300"},
        {"object": "REAL_HID", "pos": [100.0, 0.0, -140.0],
         "rot0": [0, 0, 0], "driver": "scrollBelt",
         "cutscene": "scrollBelt vz = base - (dt*2.67 wrap 20), 3 copies",
         "count": 3, "spacing": 20.0, "speed": 2.67,
         "src": "map7_s03_3.c:8296-8344, 8185-8189"},
        # Belt riders (map7_s03_3.c:8330-8341): each of the 3 copies adds
        # REAL_HID (flag D_800F4818), URA_HIDE (D_800F4819) and UNDER_HI
        # (D_800F481A) — the SAME belt math, gated per-object by the ending
        # sequence flags; scroll pauses while D_800F4819==2 (:8303).
        {"object": "URA_HIDE", "pos": [100.0, 0.0, -140.0],
         "rot0": [0, 0, 0], "driver": "scrollBelt",
         "cutscene": "scrollBelt vz = base - (dt*2.67 wrap 20), 3 copies "
                "(-20/0/+20) — the 2nd belt rider (g_WorldObject_Ura, "
                "model URA_HIDE, map7_s03_3.c:8190; gated D_800F4819)",
         "count": 3, "spacing": 20.0, "speed": 2.67,
         "src": "map7_s03_3.c:8190, 8296-8342"},
        {"object": "UNDER_HI", "pos": [100.0, 0.0, -140.0],
         "rot0": [0, 0, 0], "driver": "scrollBelt",
         "cutscene": "scrollBelt vz = base - (dt*2.67 wrap 20), 3 copies "
                "(-20/0/+20) — the 3rd belt rider (g_WorldObject_Under, "
                "model UNDER_HI, map7_s03_3.c:8191; gated D_800F481A)",
         "count": 3, "spacing": 20.0, "speed": 2.67,
         "src": "map7_s03_3.c:8191, 8296-8342"},
    ],
}


def _room_env_fx(room_name):
    """v3 envEffects + waterZones for one room GLB (AREA-level data).

    Tag from the room filename prefix (THR/HP/DR/...). The effect-texture
    FLAG is per OVERLAY (MapIdx), not per area — a room GLB cannot know its
    overlay — EXCEPT the sewers, where the flag is constant for the whole
    area (DR/DRU = WaterRefract, env_effects.c:131-136) and is attached so
    sewer GLBs are self-contained. v39: the SAME for the nightmare school
    (the room->overlay binding in the SH1X.env table (derive_room_env's
    map_points coverage) resolves MAP1_S02/MAP1_S03 rooms; the flag is
    area-constant for every room those overlays load: Water = WATER.TIM,
    env_effects.c:137-139) — the school rooms get the SAME self-contained
    treatment as the sewers. Returns ({}, []) for areas with no FX
    (the graceful no-op contract — old behavior preserved)."""
    tag = _room_tag(room_name)
    known = {t[0] for t in _MAP_INFOS}
    if tag not in known:
        return {}, []
    zones = []
    for z in _WATER_ZONES.get(tag, ()):
        # illumination is emitted RAW q11_4 (Q4) exactly as stored in
        # WATER_LIGHT_ZONES (map_info.c:389-401; all 4 rows = 8); the
        # engine consumes it via Q4_TO_Q12 (lens_flare.c:88) => meters =
        # raw/16. "illuminationMeters" is the decoded convenience field;
        # the bounds minX..maxZ are decoded meters (q11_4 raw/16).
        zones.append({
            "enabled": z[0], "illumination": z[1],
            "illuminationQ4": z[1],
            "illuminationMeters": z[1] / 16.0,
            "minX": z[2], "maxX": z[3], "minZ": z[4], "maxZ": z[5],
            "units": "illumination: Q4 (raw); meters = value/16 (engine "
                     "lens_flare.c:88 Q4_TO_Q12(illum)); bounds: meters "
                     "(s_WaterZone q11_4 raw / 16)",
            "struct": "s_WaterZone map.h:271-281",
        })
    env = {}
    if tag in ("DR", "DRU"):
        env = {"effectTexFlag": "WaterRefract", "tim": "DR_WAVE.TIM",
               "mapIdx": 29 if tag == "DR" else 36,
               "eventFlag": None,
               "src": "env_effects.c:131-136 (MapIdx_MAP5_S00/MAP6_S03)"}
    elif tag == "SU":
        # v39: the nightmare school — the overlay binding comes from the
        # SH1X.env table (derive_room_env). MAP1_S02 = mapIdx 5, MAP1_S03 = 6
        # (include/bodyprog/map/map.h:26-70). Both load WATER.TIM
        # (env_effects.c:137-139). Rooms whose overlay binding is unknown
        # (not in the env table) emit nothing (the no-op contract).
        ov = (_room_env_table().get(room_name.upper()) or {}).get("overlay")
        if ov == "MAP1_S02":
            env = {"effectTexFlag": "Water", "tim": "WATER.TIM",
                   "mapIdx": 5, "eventFlag": None,
                   "src": "env_effects.c:137-139 (MapIdx_MAP1_S02)"}
        elif ov == "MAP1_S03":
            env = {"effectTexFlag": "Water", "tim": "WATER.TIM",
                   "mapIdx": 6, "eventFlag": None,
                   "src": "env_effects.c:137-139 (MapIdx_MAP1_S03)"}
    return env, zones


_WATER_TEX_SRC = (
    "Map_EffectTexturesLoad env_effects.c:205-207 (case EffectTextureFlag_"
    "Water: Fs_QueueStartReadTim(FILE_TIM_WATER_TIM, ..., &D_800A908C)) + "
    "Fs_QueuePostLoadTim fs_queue.c:643-678 (the D_800A908C NTSC upload "
    "descriptor data.c:118 = {tPage {0,13}, u=0, v=0, clutX=224, clutY=0}: "
    "pixels -> VRAM page 13 x=832 y=0 (128x128 texels, 4bpp), CLUT rows "
    "0/1 -> (224,0)/(224,1)). Consumers draw with tpage 45 (0x2D: page X "
    "13, ABR-1 ADDITIVE, 4bpp) + clut words 0xE (row 0) / 0x4E (row 1) — "
    "water.c:424/489-490, the setSemiTrans(1) additive quads."
)


def _room_water_tex(room_name, resolver, report):
    """v39: SH1X.waterTex — the WATER.TIM effect texture, VERBATIM.

    Emitted for rooms whose envEffects is the school Water effect (the
    overlay binding resolved MAP1_S02/MAP1_S03). The block carries the
    full decoded TIM: 128x128 4bpp pixels (2 texels/byte, low nibble =
    even u), the 2 CLUT rows (16 u16 each, raw 15-bit), the VRAM upload
    positions and the tpage/clut words the game's draw code uses. The
    pixel regions the school water samples (water.c):
      u 64..95,  v 64..127 — the stream surface strip tile (32x64)
      u 64..95 / 96..127, v 0..63 / 64..127 — the 4 droplet sprites
      u 0..63, v 32*frame..+31 — the map1_s03 spray frames (4 frames)
    The pixels are the RAW 4bpp nibble sheet (unbiased, no palette
    applied). A missing WATER.TIM resolves to None (the consumer's
    legacy approximation path — graceful no-op)."""
    entry = None
    try:
        entry, _rec = resolver.resolve("WATER", room_name)
    except Exception:
        entry = None
    if entry is None:
        if report is not None:
            report.setdefault("problems", []).append(
                f"{room_name}: waterTex: WATER.TIM not resolved — "
                f"waterTex extras omitted (legacy approximation path)")
        return None
    try:
        tim = TimFile("WATER", entry.read_bytes())
    except Exception as e:
        if report is not None:
            report.setdefault("problems", []).append(
                f"{room_name}: waterTex: WATER.TIM: {e}")
        return None
    if tim.width != 128 or tim.height != 128 or tim.clut_w != 16 \
            or tim.clut_h < 2:
        if report is not None:
            report.setdefault("problems", []).append(
                f"{room_name}: waterTex: WATER.TIM is {tim.width}x"
                f"{tim.height} clut {tim.clut_w}x{tim.clut_h} — unexpected "
                f"layout, waterTex extras omitted")
        return None
    clut_rows = []
    for r in range(2):
        row = struct.unpack_from("<16H", tim.clut_data, r * 32)
        clut_rows.append([int(c) & 0xFFFF for c in row])
    return {
        "tim": "WATER.TIM", "bpp": 4,
        "width": 128, "height": 128,
        "pixels": _b64(bytes(tim.img_data[:8192])),
        "clut": clut_rows,
        "vram": {"pixelX": 832, "pixelY": 0, "clutX": 224, "clutY": 0,
                 "note": "NTSC D_800A908C upload (data.c:118); PAL "
                          "(224,0)->(928,432) (data.c:95 + CLUT_BASE "
                          "env_effects.c:107)"},
        "tpage": 45, "clutWords": [14, 78],
        "regions": {
            "streamStrip": {"u": [64, 95], "v": [64, 127],
                             "src": "water.c:693-696 (u 64..95, v 64..127 "
                                     "body tiles; leading window "
                                     "v [127-t,127])"},
            "dropletSprites": {"u": [[64, 95], [96, 127]],
                                    "v": [[0, 63], [64, 127]],
                                    "src": "water.c:424-433 (u0 0x40/0x60 "
                                            "+ (frame&2)*16, v window "
                                            "field_17C + (frame&1)<<6)"},
            "sprayFrames": {"u": [0, 63], "v": [0, 127],
                             "frames": 4, "frameV": 32,
                             "src": "map1_s03.c:164-167 (u 0..63, "
                                     "v 32*frame..+31)"},
        },
        "src": _WATER_TEX_SRC,
    }


def _room_maplink(room_name, known_rooms):
    """v3 mapLink — the WorldMap_MakeGrid contract (map.c:386-419): one
    combined world per area tag; a room's grid neighbors are the rooms at
    (chunkX+dx, chunkZ+dz), cells decoded from the 4 hex filename digits
    (ConvertHexToS8). `known_rooms` = the room names the CURRENT conversion
    actually emits (caller-built); neighbors absent from it are omitted —
    consumers ALSO probe filenames at runtime so a missing neighbor GLB is
    a silent no-op (task 6's requirement)."""
    tag = _room_tag(room_name)
    if len(room_name) != len(tag) + 4 or len(tag) == 0:
        return None
    hexpart = room_name[len(tag):len(tag) + 4].upper()
    if len(hexpart) != 4 or not all(c in "0123456789ABCDEF" for c in hexpart):
        return None
    try:
        hx = int(hexpart[:2], 16)
        hz = int(hexpart[2:4], 16)
    except ValueError:
        return None
    cx = hx - 256 if hx > 127 else hx
    cz = hz - 256 if hz > 127 else hz
    info = next((t for t in _MAP_INFOS if t[0] == tag), None)
    if info is None:
        return None
    neighbors = []
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx == 0 and dz == 0:
                continue
            nb = f"{tag}{(cx + dx) & 0xFF:02X}{(cz + dz) & 0xFF:02X}"
            if nb in known_rooms:
                neighbors.append({"dx": dx, "dz": dz, "room": nb,
                                  "file": nb + ".glb"})
    return {
        "tag": tag, "chunkX": cx, "chunkZ": cz,
        "activeChunks": info[1], "isExterior": info[2],
        "neighbors": neighbors,
        "probe": "consumers probe <tag><hexXX><hexZZ>.glb at runtime; "
                 "missing file = silent no-op (mapLink task 6)",
        "src": "MAP_INFOS map_info.c:515-532; WorldMap_MakeGrid map.c:386-419",
    }


def _room_tag(room_name):
    """Area tag of a room stem (variable length: THR/SPR/DRU are 3 chars,
    SC/SU/ER/DR/HP/HU are 2 — room_prefix() already decodes exactly this)."""
    return room_prefix(room_name)


def _wo_q10_rot(deg):
    """Engine WorldObjects_Add (world/draw.c:503-504, 572-574): the LIVE
    rotation x/z are stored Q12_TO_Q10 (arithmetic >>2 = floor) and drawn
    back Q10_TO_Q12 (<<2); rot vy stays full Q12_ANGLE. Authored
    WorldObject_Init poses therefore land on the engine's own 0.3515625deg
    grid for rot x/z when they reach the draw matrix."""
    raw = int(deg * 4096.0 / 360.0)          # Q12_ANGLE trunc-toward-0
    return (raw >> 2 << 2) * 360.0 / 4096.0  # floor to the 4-raw grid


def _wo_q8_pos(m):
    """WorldObjects_Add stores the position Q12_TO_Q8 (>>4 = floor) — the
    engine's own 1/16 m grid on the animated WorldObject translation."""
    raw = int(m * 4096.0)                   # Q12 trunc-toward-0
    return (raw >> 4 << 4) / 4096.0


def _room_prop_anims(room_name, max_entries=64):
    """v3 propAnims — the FULL animated-WorldObjects catalog
    (download/session12_evidence/ALL_ANIMATED_OBJECTS_CATALOG.md; 3 parallel
    decomp sweeps, every value verbatim file:line cited).

    Entries with a concrete pos list attach to the room whose 40m cell
    contains them (cell from the filename digits, CHUNK_SIZE 40). Entries
    with pos=None / table refs / cutscene-only / non-object drivers (ripple,
    flicker) attach to EVERY room of the overlay's AREA TAG as `manifest`
    entries — consumers render the driver effects regardless of room cell
    (the engine updates them per overlay, not per room)."""
    out = []
    tag = _room_tag(room_name)
    if len(room_name) != len(tag) + 4 or len(tag) == 0:
        return out
    hexpart = room_name[len(tag):len(tag) + 4].upper()
    if len(hexpart) != 4 or not all(c in "0123456789ABCDEF" for c in hexpart):
        return out
    try:
        hx = int(hexpart[:2], 16)
        hz = int(hexpart[2:4], 16)
    except ValueError:
        return out
    rcx = hx - 256 if hx > 127 else hx
    rcz = hz - 256 if hz > 127 else hz
    for overlay, entries in _PROP_ANIMS.items():
        if _OVERLAY_TO_TAG.get(overlay) != tag:
            continue
        for e in entries:
            pos = e.get("pos")
            entry = dict(e)
            entry["overlay"] = overlay
            # v27.2: attachRoom override — the engine adds some objects
            # from the PLAYER's room chunk even when their pos cell maps
            # to a different (or nonexistent) room (e.g. the drawbridge
            # second pair: MAP_CHUNK_CELL(-2,8) = THRFE08, pos cell
            # (-1,9) = THRFF09 which does not exist on disc).
            _aroom = e.get("attachRoom")
            if _aroom is not None and room_name.upper() != _aroom.upper():
                continue
            # v27: posPerInst entries (fanArray) attach by their FIRST
            # instance pose cell — the engine adds the array only in that
            # one chunk (map4_s02 PLAYER_IN_MAP_CHUNK(1,0)).
            _ppc = e.get("posPerInst")
            if pos is None and isinstance(_ppc, list) and _ppc:
                pos = _ppc[0]
            entry["posUnits"] = "engine Q12 meters (y-down)" \
                if isinstance(pos, list) else "manifest (overlay-level)"
            if isinstance(pos, list) and len(pos) >= 3 and \
                    all(isinstance(v, (int, float)) for v in pos):
                if _aroom is None:
                    # pos-cell attach (the default); attachRoom entries are
                    # governed by the override above instead
                    pcx = int(pos[0] // 40)
                    pcz = int(pos[2] // 40)
                    if pcx != rcx or pcz != rcz:
                        continue
                # v27.2: the WorldObjects_Add Q8 grid on the emitted pose
                entry["pos"] = [
                    _wo_q8_pos(pos[0]), _wo_q8_pos(pos[1]), _wo_q8_pos(pos[2])]
            # v27.2: rot0 on the engine's WorldObjects_Add Q10 grid (x/z)
            r0 = entry.get("rot0")
            if isinstance(r0, list) and len(r0) == 3 and \
                    all(isinstance(v, (int, float)) for v in r0):
                entry["rot0"] = [_wo_q10_rot(r0[0]), r0[1], _wo_q10_rot(r0[2])]
            if isinstance(entry.get("posPerInst"), list):
                entry["posPerInst"] = [
                    [_wo_q8_pos(p[0]), _wo_q8_pos(p[1]), _wo_q8_pos(p[2])]
                    if isinstance(p, list) and len(p) == 3 else p
                    for p in entry["posPerInst"]]
            out.append(entry)
    return out[:max_entries]


def _anim_initial_poses(e, rng_seed="sh1x-v27"):
    """v27: the engine t=0 WorldObject poses for ONE catalog anim entry,
    as engine meters (y-down). Multi-instance drivers get one pose per
    instance (the same math the engine runs at update t=0 / its INIT):
      * default            -> the authored pos
      * posPerInst         -> the per-instance list (fanArray; the verbatim
                              switch semantics of map4_s02.c:108-118)
      * gravityScatter     -> 16 deterministic rolls in the verbatim init
                              ranges (map7_s02_2.c:3476-3488; engine rolls
                              Rng_Rand16 at init - unknowable exactly, the
                              RANGES are verbatim; fixed seed = reproducible
                              builds)
      * ferrisWheel        -> the 5 arm poses at master=0 (map6_s04_2.c:
                              3814-3845: angle = -739+i*307 Q12_ANGLE
                              counts, pos = (8.7, 10*cos(a)-13.8, 10*sin(a)-28));
                              CABIN entries ("cabin": true — FWBOX1_B/
                              FWBOX2_B) ride radius 11.25 instead of 10
                              (:3829-3831), pendulum angle 0 at t=0
                              (D_800EBB10 statics start 0, :3832)
      * lissajousOrbit     -> the 12 balloon poses at master=0 (3856-3874)
    Entries whose pos is not a concrete list of numbers return [] (no
    emission - the position data is not in the decomp repo)."""
    drv = e.get("driver", "")
    pos = e.get("pos")
    if drv == "ferrisWheel":
        out = []
        # cabins (FWBOX1_B/FWBOX2_B) sit at radius 11.25 on the same arm
        # angles (map6_s04_2.c:3829-3831); the wheel models at 10
        # (:3819-3822). Pendulum rot.vx = D_800EBB10[i]>>12 = 0 at t=0.
        radius = 11.25 if e.get("cabin") else 10.0
        for i in range(int(e.get("arms", 5))):
            a_cnt = e.get("arm0Raw", -739) + i * e.get("armStepRaw", 307)
            a = math.radians(a_cnt * 360.0 / 4096.0)
            out.append([8.7, radius * math.cos(a) - 13.8,
                        radius * math.sin(a) - 28.0])
        return out
    if drv == "lissajousOrbit":
        out = []
        for i in range(int(e.get("count", 12))):
            # engine (map6_s04_2.c:3856-3860): aq = Math_Sin(0 + i<<10)/30
            # and ryCnt = (i<<12)/12 — INTEGER DIVISION (trunc toward 0,
            # C semantics; all operands positive here so // is exact)
            sin_v = int(math.sin((i << 10) * (2.0 * math.pi / 4096.0)) * 4096.0)
            aq = sin_v // 30                      # int div, verbatim
            vy = math.sin(aq * math.pi / 2048.0) * 4.0 - 1.5
            temp = math.cos(aq * math.pi / 2048.0) * 4.0
            ry_cnt = (i << 12) // 12             # int div, verbatim
            ry = math.radians(ry_cnt * 360.0 / 4096.0)
            out.append([temp * math.sin(ry) - 16.0, vy,
                        temp * math.cos(ry) - 64.0])
        return out
    if drv == "gravityScatter":
        import random as _random
        rng = _random.Random(f"{rng_seed}:{e.get('object')}")
        out = []
        n = int(e.get("count", 16))
        # engine (map7_s02_2.c:3476-3488): position rolls are
        # Rng_GenerateInt(Q12(lo), Q12(hi) - 1) — INCLUSIVE INTEGER raw
        # ranges (rng.h:62-63); reproduce them exactly in Q12 raws.
        ry = e.get("initRangeY", [-1.45, -1.3501])
        rz = e.get("initRangeZ", [-61.07, -60.93])
        ry0, ry1 = int(ry[0] * 4096.0), int(ry[1] * 4096.0) - 1
        rz0, rz1 = int(rz[0] * 4096.0), int(rz[1] * 4096.0) - 1
        px = float(pos[0])
        for i in range(n):
            out.append([px, rng.randint(ry0, ry1) / 4096.0,
                        rng.randint(rz0, rz1) / 4096.0])
        return out
    if drv == "scrollBelt":
        # map7_s03_3.c:8331-8344: 3 segment copies vz = base, base-20,
        # base+20 (g_WorldObject_UnkPos (100,0,-140)); scroll = 0 at t=0.
        n = int(e.get("count", 3))
        sp = float(e.get("spacing", 20.0))
        out = []
        for i in range(n):
            off = 0.0 if i == 0 else (-sp if i == 1 else sp)
            out.append([float(pos[0]), float(pos[1]),
                        float(pos[2]) + off])
        return out
    if isinstance(e.get("posPerInst"), list) and e["posPerInst"]:
        return [list(p) for p in e["posPerInst"]
                if isinstance(p, list) and len(p) == 3]
    if isinstance(pos, list) and len(pos) >= 3 and \
            all(isinstance(v, (int, float)) for v in pos):
        return [list(pos)]
    return []


# ---------------------------------------------------------------------------
# TIM texture decoding (PS1 4bpp CLUT images)
# ---------------------------------------------------------------------------
class TimFile:
    """Parsed 4bpp CLUT TIM. Decodes palette variants on demand."""

    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.problems = []
        if len(data) < 20:
            raise ValueError(f"TIM too small ({len(data)} bytes)")
        if data[0] != 0x10:
            raise ValueError(f"bad TIM id 0x{data[0]:02X}")
        self.flags = data[4]
        self.bpp = self.flags & 3
        self.has_clut = bool((self.flags >> 3) & 1)
        if not self.has_clut:
            raise ValueError("TIM has no CLUT (direct-color TIMs unsupported)")
        if self.bpp != 0:
            raise ValueError(f"TIM bpp={self.bpp} (only 4bpp supported)")
        self.clut_len = u32(data, 8)
        self.clut_x, self.clut_y = u16(data, 12), u16(data, 14)
        self.clut_w, self.clut_h = u16(data, 16), u16(data, 18)
        self.clut_data = data[20:8 + self.clut_len]
        io = 8 + self.clut_len
        self.img_len = u32(data, io)
        self.img_x, self.img_y = u16(data, io + 4), u16(data, io + 6)
        self.img_w, self.img_h = u16(data, io + 8), u16(data, io + 10)
        self.img_data = data[io + 12:io + 12 + self.img_w * 2 * self.img_h]
        self.width = self.img_w * 4        # pixels
        self.height = self.img_h
        if len(self.clut_data) < self.clut_w * 2 * self.clut_h:
            self.problems.append("CLUT truncated")
        if len(self.img_data) < self.img_w * 2 * self.img_h:
            self.problems.append("image data truncated")

    def palette(self, cba):
        """Return the 16-entry palette (u16 array) selected by a pack's cba field."""
        px = (cba & 0x3F) << 4
        py = (cba & 0x7FC0) >> 6
        off = py * self.clut_w * 2 + px * 2     # VRAM-linear (legacy-identical)
        if off + 32 > len(self.clut_data):
            raise ValueError(f"palette ({px},{py}) outside CLUT "
                             f"({self.clut_w}x{self.clut_h})")
        return struct.unpack_from("<16H", self.clut_data, off), py

    def decode(self, palette, stp):
        """Decode full image with given palette; PS1 alpha rules (legacy-identical).

        stp=0 : color==0x0000 -> alpha 0 ; else 255
        stp=1 : 0x0000 -> 0 ; 0x8000 -> 127 ; STP bit set -> 127 ; else 255
        Color 5->8 bit conversion uses PS1 DAC bit replication (v<<3 | v>>2);
        DEVIATION from legacy which truncated v*8.226 (loses the top level: 31->254).
        """
        h, w = self.height, self.width
        img = np.frombuffer(self.img_data, dtype=np.uint8)
        if img.size < w // 2 * h:
            img = np.pad(img, (0, w // 2 * h - img.size))
        img = img[: w // 2 * h].reshape(h, w // 2)
        # 4bpp: low nibble first (even x), high nibble second (odd x)
        idx = np.empty((h, w), dtype=np.uint8)
        idx[:, 0::2] = img & 0x0F
        idx[:, 1::2] = img >> 4
        pal = np.array(palette, dtype=np.uint16)
        c = pal[idx]                                    # h x w u16 colors
        r5 = (c & 0x001F).astype(np.uint8)
        g5 = ((c >> 5) & 0x1F).astype(np.uint8)
        b5 = ((c >> 10) & 0x1F).astype(np.uint8)
        rep = lambda v: ((v << 3) | (v >> 2)).astype(np.uint8)
        rgb = np.stack([rep(r5), rep(g5), rep(b5)], axis=-1)   # h w 3
        stp_bit = (c & 0x8000) != 0
        # v40 audit (D-F1): opaque-branch transparency is EXACT 0x0000 only.
        # The old `(c & 0x7FFF) == 0` also caught 0x8000 (STP-set black) —
        # the docstring ("stp=0: color==0x0000 -> alpha 0; else 255") and
        # the hardware disagree: SwanStation's sampler discards a texel
        # only when `texture_color.bits == 0` (gpu_sw_backend.cpp:124,
        # the FULL 16 bits) — 0x8000 is an OPAQUE BLACK texel. Measured on
        # the shipped corpus: 5,103 of 40,927 texture packs (12.5%) in 22
        # of 44 rooms carry the 0x8000 texel inside their UV window; 298
        # opaque-only packs shipped as alphaMode BLEND purely from this.
        black = (c == 0)
        alpha = np.full((h, w), 255, dtype=np.uint8)
        alpha[black] = 0
        if stp:
            alpha[stp_bit & ~black] = 127
            alpha[stp_bit & black] = 127
        return np.concatenate([rgb, alpha[..., None]], axis=-1)  # h w 4 RGBA


# ---------------------------------------------------------------------------
# directory-tree TIM discovery (multi-root, recursive, archive-aware)
# ---------------------------------------------------------------------------
# Texture files are NOT assumed to sit beside the IPD files.  Discovery scans
# the --input directory and every --search-roots directory recursively and
# case-insensitively, and descends into ZIP archives detected by PK magic
# (extension does not matter), including zips nested inside zips.
MAX_ZIP_DEPTH = 3                      # zip inside zip inside zip is plenty
TEXTURE_EXTS = {".TIM"}                # compared case-insensitively
PK_MAGIC = b"PK\x03\x04"


class DiscoveredFile:
    """One file found by discovery: on disk, or inside a (nested) archive."""

    __slots__ = ("vpath", "size", "sha1", "ext", "root", "in_archive", "_read")

    def __init__(self, vpath, size, sha1, ext, root, in_archive, reader):
        self.vpath = vpath            # display path; "!" separates archive levels
        self.size = size
        self.sha1 = sha1
        self.ext = ext                # uppercased extension, "." included
        self.root = root              # discovery root the file hangs from
        self.in_archive = in_archive
        self._read = reader

    def read_bytes(self):
        return self._read()

    def sort_key(self):
        """Deterministic representative preference: real file before archive
        entry, shorter path first, then lexicographic."""
        return (self.in_archive, len(self.vpath), self.vpath)

    def to_json(self):
        return {"path": self.vpath, "size": self.size, "sha1": self.sha1,
                "ext": self.ext, "in_archive": self.in_archive}


def _scan_archive_blob(vpath, blob, depth, root, out, stats):
    """Index every entry of an in-memory zip archive, recursing into nested
    zips (depth-limited).  Problems are collected in stats, never raised."""
    import io as _io
    import zipfile as _zf
    try:
        zf = _zf.ZipFile(_io.BytesIO(blob))
    except Exception as e:
        stats["archive_errors"].append(f"{vpath}: not readable as archive: {e}")
        return
    stats["archives_scanned"].append(vpath)
    for info in zf.infolist():
        if info.is_dir():
            continue
        inner = f"{vpath}!/{info.filename}"
        try:
            data = zf.read(info.filename)
        except Exception as e:
            stats["archive_errors"].append(f"{inner}: read failed: {e}")
            continue
        _base, ext = os.path.splitext(info.filename)
        out.append(DiscoveredFile(inner, len(data),
                                  hashlib.sha1(data).hexdigest(), ext.upper(),
                                  root, True, (lambda d=data: d)))
        if depth + 1 < MAX_ZIP_DEPTH and data[:4] == PK_MAGIC:
            _scan_archive_blob(inner, data, depth + 1, root, out, stats)


def discover_files(roots, exclude_prefixes=(), log=None):
    """Walk every root recursively; index all files plus archive contents.

    Returns (entries, stats).  Unreadable items are recorded in stats, never
    raised - the audit reports surface them loudly instead.
    """
    log = log or logging.getLogger("ipd2gltf")
    stats = {"roots": [], "folders_scanned": 0, "files_indexed": 0,
             "archives_scanned": [], "archive_errors": [], "scan_errors": []}
    entries = []
    excl = [os.path.abspath(p) for p in exclude_prefixes]
    for root in roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            stats["scan_errors"].append(f"root is not a directory: {root}")
            continue
        stats["roots"].append(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dp = os.path.abspath(dirpath)
            dirnames[:] = sorted(
                d for d in dirnames
                if not any(os.path.join(dp, d) == e or
                           os.path.join(dp, d).startswith(e + os.sep)
                           for e in excl))
            stats["folders_scanned"] += 1
            for f in sorted(filenames):
                p = os.path.join(dp, f)
                if any(p == e or p.startswith(e + os.sep) for e in excl):
                    continue
                try:
                    with open(p, "rb") as fh:
                        blob = fh.read()
                except OSError as e:
                    stats["scan_errors"].append(f"{p}: {e}")
                    continue
                _base, ext = os.path.splitext(f)
                entries.append(DiscoveredFile(
                    p, len(blob), hashlib.sha1(blob).hexdigest(), ext.upper(),
                    root, False, (lambda pp=p: open(pp, "rb").read())))
                stats["files_indexed"] += 1
                if blob[:4] == PK_MAGIC:
                    _scan_archive_blob(p, blob, 0, root, entries, stats)
    # overlapping roots can yield the same vpath twice - keep one
    uniq = {}
    for e in entries:
        uniq.setdefault(e.vpath, e)
    entries = list(uniq.values())
    log.info("discovery: %d roots, %d folders, %d disk files, %d archive "
             "entries, %d archives scanned", len(stats["roots"]),
             stats["folders_scanned"], stats["files_indexed"],
             len(entries) - stats["files_indexed"],
             len(stats["archives_scanned"]))
    return entries, stats


class TextureRegistry:
    """Lookup indexes over the discovered files for every strategy."""

    def __init__(self, entries):
        self.entries = entries
        self.by_name = {}       # "ER221.TIM" (upper)   -> [entries]
        self.by_stem = {}       # "ER221"               -> [entries]
        self.by_hash = {}       # content sha1          -> [entries]
        self.by_rel = {}        # normalized relpath or path suffix -> [entries]
        for e in entries:
            name = os.path.basename(e.vpath).upper()
            stem = os.path.splitext(name)[0]
            self.by_name.setdefault(name, []).append(e)
            self.by_stem.setdefault(stem, []).append(e)
            self.by_hash.setdefault(e.sha1, []).append(e)
            rels = []
            try:
                rels.append(os.path.relpath(e.vpath, e.root))
            except ValueError:
                pass
            if "!" in e.vpath:              # archive inner paths
                rels.extend(e.vpath.split("!/")[1:])
            for r in rels:
                n = r.replace("\\", "/").lower().lstrip("./")
                segs = [s for s in n.split("/") if s]
                if not segs:
                    continue
                for k in (1, 2, 3):         # full path and 1/2/3-segment tails
                    if len(segs) >= k:
                        self.by_rel.setdefault("/".join(segs[len(segs) - k:]),
                                               []).append(e)

    def tim_stats(self):
        """Duplicate/ignore statistics over discovered TIM files."""
        tim = [e for e in self.entries if e.ext in TEXTURE_EXTS]
        groups = {}
        for e in tim:
            groups.setdefault(e.sha1, []).append(e)
        multi = {h: [e.vpath for e in sorted(g, key=DiscoveredFile.sort_key)]
                 for h, g in groups.items() if len(g) > 1}
        return {"tim_files_found": len(tim),
                "tim_unique_by_content": len(groups),
                "tim_duplicate_entries_ignored": len(tim) - len(groups),
                "duplicate_groups": multi}


class VirtualTree:
    """The original CD-rip directory listing (dir_list.txt, Windows-style
    paths) as a read-only evidence source.  It records WHERE each file lived
    in the source layout (e.g. sh1rip/BG/ER221.TIM) - used as folder-hint
    evidence for path-suffix matching and as explicit evidence for
    missing-texture reports."""

    def __init__(self, path):
        import re as _re
        self.path = os.path.abspath(path)
        self.files = {}         # upper filename -> [(raw line, rip-relative)]
        self.lines = 0
        with open(self.path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                self.lines += 1
                parts = [p for p in _re.split(r"[\\/]+", line) if p]
                parts = [p for p in (_re.sub(r"^[A-Za-z]:", "", p) for p in parts)
                         if p]
                if len(parts) < 2 or "." not in parts[-1]:
                    continue          # directory (or drive) line
                lower = [p.lower() for p in parts]
                rel = ("/".join(parts[lower.index("sh1rip"):])
                       if "sh1rip" in lower else "/".join(parts))
                self.files.setdefault(parts[-1].upper(), []).append((line, rel))

    def lookup(self, filename):
        """All known original locations for a filename (with extension)."""
        return self.files.get(filename.upper(), [])


class TextureResolver:
    """Deterministic, evidence-ranked texture resolver.

    Strategy ladder (first stage with candidates wins; see module docstring):
      1 referenced_path - the reference carries a path itself
      2 exact_filename  - <ref>.TIM anywhere in the scanned tree (legacy rule
                          generalized: legacy open_tim opened name+".TIM" in the
                          working directory, case-sensitively)
      3 stem_no_ext     - reference stored with another extension spelling
      4 tree_path       - original-layout folder hints from dir_list.txt
      5 convention      - room-family naming inference (INFERRED, flagged)
    Ambiguity (same stage, different content) is a reported defect - nothing
    is chosen silently.  Identical-content candidates in several folders are
    duplicates of one texture: one deterministic representative is chosen and
    every location is logged.  Missing references keep their original-tree
    locations as evidence; placeholders are never substituted.
    """

    _STRATEGY_ORDER = ("referenced_path", "exact_filename", "stem_no_ext",
                       "tree_path", "convention")

    def __init__(self, roots, tree=None, exclude_prefixes=(), log=None):
        self.log = log or logging.getLogger("ipd2gltf")
        self.tree = tree
        self.roots = [os.path.abspath(r) for r in roots]
        entries, self.discovery_stats = discover_files(self.roots,
                                                       exclude_prefixes,
                                                       self.log)
        self.registry = TextureRegistry(entries)
        self.plm_index = None            # set up by main() after discovery
        self.object_ledger = []          # object-reference resolution records
        self._obj_ledger_cache = {}      # (room, NAME, source) -> record
        self.stats = {"refs": 0, "resolved": 0, "unresolved": 0,
                      "ambiguous": 0, "resolved_by_strategy": {},
                      "duplicate_locations": 0, "tim_parse_failures": 0,
                      "png_conversions": 0,
                      "distinct_referenced_names": 0,
                      "distinct_resolved_names": 0}
        self.resolutions = []          # one record per (room, ref) pair
        self._pairs = set()
        self._names = set()
        self._names_resolved = set()
        self._tim_cache = {}           # sha1 -> TimFile | None

    # -- resolution ------------------------------------------------------
    @staticmethod
    def _convention_candidates(stem, room):
        """Name candidates derived from room-family naming conventions.
        Real-world example: the DR* rooms reference texture "DWAVE" while the
        original rip stores it as TIM/DR_WAVE.TIM.  This is INFERRED name
        evidence only - it is logged, and a convention match is accepted only
        when exactly one .TIM candidate exists on disk."""
        out = []
        fams = []
        if len(room) >= 2:
            fams.append(room[:2])
        if len(room) >= 1:
            fams.append(room[:1])
        for fam in dict.fromkeys(fams):
            if not stem or fam[0] != stem[0]:
                continue
            cand = f"{fam}_{stem[1:]}"
            if cand != stem and cand not in out:
                out.append(cand)
            if stem.startswith(fam) and len(stem) > len(fam):
                cand = f"{fam}_{stem[len(fam):]}"
                if cand != stem and cand not in out:
                    out.append(cand)
        return out

    def resolve(self, name, room=""):
        """Resolve one texture reference.  Returns (entry | None, record)."""
        raw = (name or "").strip()
        base = os.path.basename(raw.replace("\\", "/"))
        stem = os.path.splitext(base)[0].upper()
        record = {"ref": raw, "room": room, "status": "unresolved",
                  "strategy": None, "chosen": None, "candidates": [],
                  "duplicates": [], "tree_evidence": [],
                  "convention_candidates": [], "problems": []}
        if not stem:
            record["problems"].append("empty texture reference")
            return None, record

        cand = []      # (DiscoveredFile, strategy)

        def add(entries, strategy):
            for e in entries:
                if e.ext in TEXTURE_EXTS:
                    cand.append((e, strategy))

        # 1. referenced path (only when the reference actually carries one)
        if "/" in raw or "\\" in raw:
            norm = raw.replace("\\", "/").lower().lstrip("./")
            segs = [s for s in norm.split("/") if s]
            for k in sorted({len(segs), 2, 1}):
                if len(segs) >= k:
                    add(self.registry.by_rel.get("/".join(segs[-k:]), []),
                        "referenced_path")
        # 2. exact filename, whole tree, case-insensitive (legacy rule)
        add(self.registry.by_name.get(stem + ".TIM", []), "exact_filename")
        # 3. stem with a different extension spelling
        if not cand:
            add(self.registry.by_stem.get(stem, []), "stem_no_ext")
        # virtual-tree evidence - always collected for the report
        if self.tree is not None:
            for _raw, rel in self.tree.lookup(stem + ".TIM"):
                if rel not in record["tree_evidence"]:
                    record["tree_evidence"].append(rel)
        # 4. tree path: original-layout folder hints matched on disk
        if not cand and self.tree is not None:
            for _raw, rel in self.tree.lookup(stem + ".TIM"):
                segs = rel.lower().split("/")
                for k in (2, 3):
                    if len(segs) >= k:
                        add(self.registry.by_rel.get("/".join(segs[-k:]), []),
                            "tree_path")
        # 5. naming conventions (INFERRED)
        if not cand and room:
            for c in self._convention_candidates(stem, room):
                record["convention_candidates"].append(c)
                add(self.registry.by_name.get(c + ".TIM", []), "convention")
                if self.tree is not None:
                    for _raw, rel in self.tree.lookup(c + ".TIM"):
                        ev = f"{rel}  (convention candidate {c})"
                        if ev not in record["tree_evidence"]:
                            record["tree_evidence"].append(ev)

        # ---- decision ----
        entry = None
        for stage in self._STRATEGY_ORDER:
            stage_map = {}
            for e, s in cand:
                if s == stage:
                    stage_map.setdefault(e.vpath, e)
            stage_entries = list(stage_map.values())
            if not stage_entries:
                continue
            if len({e.sha1 for e in stage_entries}) > 1:
                record["status"] = "ambiguous"
                record["problems"].append(
                    f"{len(stage_entries)} files with DIFFERENT content match "
                    f"{raw!r} at stage {stage!r}: "
                    f"{sorted(e.vpath for e in stage_entries)}")
            else:
                entry = sorted(stage_entries, key=DiscoveredFile.sort_key)[0]
                record["status"] = "resolved"
                record["strategy"] = stage
                record["chosen"] = entry.to_json()
                record["candidates"] = [e.to_json() for e
                                        in sorted(stage_entries,
                                                  key=DiscoveredFile.sort_key)]
                record["duplicates"] = [e.vpath for e in stage_entries
                                        if e.vpath != entry.vpath]
            break
        return entry, record

    def load_tim(self, name, room="", report=None):
        """Resolve + parse the TIM for reference `name` used by `room`.

        Returns a TimFile (cached by content hash) or None.  Every decision,
        duplicate location and problem is logged in the resolver's resolution
        records and, if given, the per-room export report.
        """
        raw = (name or "").strip()
        pair = (room, raw.upper())
        entry, record = self.resolve(raw, room)
        if pair not in self._pairs:
            self._pairs.add(pair)
            self.resolutions.append(record)
            self.stats["refs"] += 1
            if record["status"] == "resolved":
                self.stats["resolved"] += 1
                s = record["strategy"]
                self.stats["resolved_by_strategy"][s] = \
                    self.stats["resolved_by_strategy"].get(s, 0) + 1
            elif record["status"] == "ambiguous":
                self.stats["ambiguous"] += 1
            else:
                self.stats["unresolved"] += 1
                if not record["problems"]:
                    locs = record["tree_evidence"] or ["no original-tree entry"]
                    record["problems"].append(
                        f"texture {raw!r} not found in any scanned root "
                        f"(disk + archives); original tree: {', '.join(locs)}")
            self.stats["duplicate_locations"] += len(record["duplicates"])
            self._names.add(raw.upper())
            if record["status"] == "resolved":
                self._names_resolved.add(raw.upper())
            self.stats["distinct_referenced_names"] = len(self._names)
            self.stats["distinct_resolved_names"] = len(self._names_resolved)
            self.log.info("texture %-10s [%s]: %s%s%s", raw, room,
                          record["status"],
                          f" via {record['strategy']}" if record["strategy"] else "",
                          f" -> {record['chosen']['path']}"
                          if record["chosen"] else "")
        tim = None
        if entry is not None:
            if entry.sha1 not in self._tim_cache:
                try:
                    tim = TimFile(raw, entry.read_bytes())
                except Exception as e:
                    self.stats["tim_parse_failures"] += 1
                    record["problems"].append(
                        f"TIM parse failed ({entry.vpath}): {e}")
                    record["status"] = "parse_failed"
                    self.log.error("texture %s: TIM parse failed: %s", raw, e)
                self._tim_cache[entry.sha1] = tim
            else:
                tim = self._tim_cache[entry.sha1]
        if report is not None:
            for p in record["problems"]:
                msg = f"texture {raw}: {p}"
                if msg not in report["problems"]:
                    report["problems"].append(msg)
            report.setdefault("tex_assignments", {})[raw] = {
                "status": record["status"], "strategy": record["strategy"],
                "source": record["chosen"],
                "duplicates": record["duplicates"],
                "tree_evidence": record["tree_evidence"],
                "problems": record["problems"],
            }
        return tim

    def unresolved_names(self):
        """Distinct referenced texture names that never resolved."""
        return sorted(self._names - self._names_resolved)

    def find_glb(self, ipd_stem):
        """Companion <PREFIX>_GLB.PLM for an IPD, searched across the whole
        discovered tree (not just the IPD folder).  Returns DiscoveredFile."""
        prefix = ipd_stem[:-4] if len(ipd_stem) > 4 else ipd_stem
        cands = [e for e in self.registry.by_name.get(f"{prefix}_GLB.PLM", [])
                 if e.ext == ".PLM"]
        if not cands:
            return None
        return sorted(cands, key=DiscoveredFile.sort_key)[0]

    # The engine's billboard leaf texture: TIM/BG_ETC.TIM (filetable 1799),
    # uploaded at boot into VRAM page 12 by GameFs_BgEtcGfxLoad and sampled
    # by Gfx_BillboardDraw at tpage 44 / clut 140 over the window
    # u[0,63] v[128,191] with CLUT row 2.  Resolved through the SAME
    # evidence ladder as room textures so every decision is logged.
    # TEST/LEAVES.TIM is NOT a fallback (unreferenced dev leftover; a
    # fallback would be a loss in accuracy - user instruction).
    BG_ETC_TEX_NAME = "BG_ETC.TIM"
    # Engine constants (billboard_draw.c Gfx_BillboardDraw, verbatim):
    BILLBOARD_TPAGE = 44          # tPage = 44 -> page 12 (VRAM x=768, 4bpp)
    BILLBOARD_CLUT = 140          # clut = 140 -> VRAM (192,2)
    # Loader constants (world_draw.c GameFs_BgEtcGfxLoad, verbatim): the
    # s_FsImageDesc relocates the TIM's pixel block to page 12 (u=v=0 ->
    # VRAM (768,0)) and its CLUT block to (192,0); Fs_QueuePostLoadTim keeps
    # the TIM's own block widths/heights.
    BG_ETC_LOAD_CLUT_X, BG_ETC_LOAD_CLUT_Y = 192, 0
    # Gfx_BillboardDraw UV window (D_800AE4DC field_8/9/A/B combined
    # halfwords 0x8000/0x803F/0xBF00/0xBF3F -> corner UVs):
    BILLBOARD_UV_WINDOW = (0, 63, 128, 191)     # u0, u1, v0, v1

    def load_leaf_texture(self, room="<ENGINE_BILLBOARD>"):
        """Resolve + decode the billboard leaf texture (TIM/BG_ETC.TIM).

        Returns {"png": bytes, "source": str, "status": str} or None.

        Engine chain, verbatim from the decompilation:
          * GameState_KcetLogo_Update (b_konami.c:149, the FIRST boot
            state) -> GameFs_BgEtcGfxLoad (world_draw.c:80-85) queues
            FILE_TIM_BG_ETC_TIM (1799) with IMAGE={.tPage={0,12},
            .clutX=192} (u=v=clutY=0) - the sheet is in VRAM before any
            map and persists all game;
          * Fs_QueuePostLoadTim (fsqueue.c:643-676) relocates the TIM's
            pixel block to x=0+((12&0xF)<<6)=768 (page 12), y=0, and its
            CLUT block to (192,0), keeping the TIM's own block sizes
            (real file: 32 halfwords x 256 rows = 128x256 texels, 11
            16-color palettes);
          * Gfx_BillboardDraw (billboard_draw.c:260-261) renders with
            tPage=44 (page 12, 4bpp) and clut=140 = VRAM (192,2) = CLUT
            ROW 2 of the relocated block, sampling the window
            u[0,63] v[128,191] = texel columns 0-63 of rows 128-191.

        Decoding extracts exactly that 64x64 window with palette row 2 and
        the PS1 OPAQUE-primitive punch-through rule (texel INDEX 0 fully
        transparent - setPolyGT4 code 0x3C has the ST bit clear; CLUT row
        2's color 0 is 0x0000 with STP=0; every other texel opaque).  This
        index-0 rule is the engine's own; it coincides with the room-texture
        pipeline's color==0 rule on this data because the window references
        palette indices 0-8 only (9-15 are unreferenced) - proven on the
        real disc file.  There is NO LEAVES.TIM fallback.
        """
        raw = self.BG_ETC_TEX_NAME
        pair = (room, raw.upper())
        entry, record = self.resolve(raw, room)
        if pair not in self._pairs:
            self._pairs.add(pair)
            self.resolutions.append(record)
            self.stats["refs"] += 1
            if record["status"] == "resolved":
                self.stats["resolved"] += 1
                s = record["strategy"]
                self.stats["resolved_by_strategy"][s] = \
                    self.stats["resolved_by_strategy"].get(s, 0) + 1
            elif record["status"] == "ambiguous":
                self.stats["ambiguous"] += 1
            else:
                self.stats["unresolved"] += 1
                if not record["problems"]:
                    locs = record["tree_evidence"] or ["no original-tree entry"]
                    record["problems"].append(
                        f"billboard leaf texture {raw!r} (engine file "
                        f"TIM/BG_ETC.TIM, filetable 1799, loaded by "
                        f"GameFs_BgEtcGfxLoad into VRAM page 12) not found "
                        f"in any scanned root (disk + archives); original "
                        f"tree: {', '.join(locs)}")
            self.stats["duplicate_locations"] += len(record["duplicates"])
            self._names.add(raw.upper())
            if record["status"] == "resolved":
                self._names_resolved.add(raw.upper())
            self.stats["distinct_referenced_names"] = len(self._names)
            self.stats["distinct_resolved_names"] = len(self._names_resolved)
            self.log.info("texture %-10s [%s]: %s%s%s", raw, room,
                          record["status"],
                          f" via {record['strategy']}" if record["strategy"] else "",
                          f" -> {record['chosen']['path']}"
                          if record["chosen"] else "")
        if record["status"] == "ambiguous" or record["status"] == "parse_failed":
            # ambiguity between different BG_ETC.TIM contents is a DEFECT:
            # refuse to guess (nothing chosen silently)
            self.log.error(
                "billboard leaf texture BG_ETC.TIM: %s - billboards will be "
                "DROPPED loudly", record["status"])
            return None
        if entry is None:
            return None
        try:
            tim = TimFile(raw, entry.read_bytes())
        except Exception as e:
            self.stats["tim_parse_failures"] += 1
            record["problems"].append(
                f"BG_ETC.TIM parse failed ({entry.vpath}): {e}")
            record["status"] = "parse_failed"
            self.log.error("billboard leaf texture BG_ETC.TIM: parse failed: %s", e)
            return None
        # ---- engine placement math (Fs_QueuePostLoadTim, verbatim) ------
        # pixel block -> VRAM (768, 0) = page 12 base: the billboard's u is
        # the sheet's texel column; its v is the sheet's row.  The engine
        # window must fit inside the uploaded sheet.
        u0, u1, v0, v1 = self.BILLBOARD_UV_WINDOW
        if tim.width < u1 + 1 or tim.height < v1 + 1:
            record["problems"].append(
                f"BG_ETC.TIM sheet is {tim.width}x{tim.height} texels - too "
                f"small for the engine window u[{u0},{u1}] v[{v0},{v1}] "
                f"(real disc file: 128x256)")
            record["status"] = "parse_failed"
            self.log.error(
                "billboard leaf texture BG_ETC.TIM: %dx%d sheet cannot hold "
                "the engine 64x64 window - refusing to guess",
                tim.width, tim.height)
            return None
        # clut 140 -> VRAM (192,2); the loader put the CLUT block at
        # (192,0) -> palette ROW 2 - 0 = row 2, and the row starts at
        # halfword column 192 - 192 = 0 (CLUT x coords are in halfwords,
        # same units as the s_FsImageDesc clutX).
        clut_x, clut_y = ((self.BILLBOARD_CLUT & 0x3F) << 4,
                          self.BILLBOARD_CLUT >> 6)
        row = clut_y - self.BG_ETC_LOAD_CLUT_Y
        col_hw = clut_x - self.BG_ETC_LOAD_CLUT_X   # halfword column
        # (for the real file col_hw is 0: the row starts exactly at x=192)
        if row < 0 or col_hw < 0 or \
                row >= tim.clut_h or col_hw + 16 > tim.clut_w:
            record["problems"].append(
                f"BG_ETC.TIM CLUT is {tim.clut_w}x{tim.clut_h} - cannot hold "
                f"the engine palette at VRAM ({clut_x},{clut_y}) "
                f"(row {row}, halfword column {col_hw})")
            record["status"] = "parse_failed"
            self.log.error(
                "billboard leaf texture BG_ETC.TIM: CLUT too small for the "
                "engine clut 140 row - refusing to guess")
            return None
        # ---- decode the engine window with palette row `row` ------------
        # OPAQUE-primitive punch-through, engine-literal: texel INDEX 0 is
        # fully transparent, every other texel opaque (code 0x3C, ST clear;
        # the GPU rule is index-based, NOT color-based - indices 9-15 whose
        # colors are 0x0000 would draw BLACK; the real window happens to
        # reference indices 0-8 only, so both readings coincide - verified).
        h, w = tim.height, tim.width
        img = np.frombuffer(tim.img_data, dtype=np.uint8)
        if img.size < w // 2 * h:
            img = np.pad(img, (0, w // 2 * h - img.size))
        img = img[: w // 2 * h].reshape(h, w // 2)
        idx = np.empty((h, w), dtype=np.uint8)
        idx[:, 0::2] = img & 0x0F
        idx[:, 1::2] = img >> 4
        win_idx = idx[v0:v1 + 1, u0:u1 + 1]
        pal = np.array(struct.unpack_from(
            "<16H", tim.clut_data,
            row * tim.clut_w * 2 + col_hw * 2), dtype=np.uint16)
        c = pal[win_idx]
        rep = lambda v: ((v << 3) | (v >> 2)).astype(np.uint8)
        rgb = np.stack([rep(c & 0x1F), rep((c >> 5) & 0x1F),
                        rep((c >> 10) & 0x1F)], axis=-1)
        alpha = np.full(win_idx.shape, 255, dtype=np.uint8)
        alpha[win_idx == 0] = 0            # PS1 4bpp index-0 punch-through
        variant = np.concatenate([rgb, alpha[..., None]], axis=-1)
        if not HAS_PIL:
            raise RuntimeError("Pillow required for texture embedding")
        img_out = Image.fromarray(variant)
        import io as _io
        buf = _io.BytesIO()
        img_out.save(buf, format="PNG", optimize=False)
        return {"png": buf.getvalue(),
                "source": (f"discovered {record['chosen']['path']} "
                           f"(TIM/BG_ETC.TIM, engine billboard texture: "
                           f"window u[{u0},{u1}] v[{v0},{v1}] of the "
                           f"{w}x{h} sheet, CLUT row {row} = engine clut "
                           f"{self.BILLBOARD_CLUT} at VRAM ({clut_x},"
                           f"{clut_y}))"),
                "status": "discovered_bg_etc_tim"}


# ---------------------------------------------------------------------------
# PLM parsing (geometry library, embedded in IPD or standalone GLB)
# ---------------------------------------------------------------------------
@dataclass
class Pack:
    tex_num: int
    stp: int
    cba: int
    uv: tuple            # ((u0,v0),(u1,v1),(u2,v2),(u3,v3))
    faces: tuple
    normal_slots: tuple
    b6: int = 0          # raw byte @6 of s_Primitive (the u16 'bits1' low
                         # byte — set to s_Material::field_E by the engine)
    b7: int = 0          # raw byte @7 (texIdx:7 | stp:1) — the engine's
                         # bits1.flags bit-15 semi-transparency test


@dataclass
class Mesh:
    verts: list          # [(x,y,z)] local
    normals_a: list       # [(nx,ny,nz,slot_count)]
    slot_normal: list     # slot -> A-group index
    slot_vertex: bytes    # slot -> vertex index
    packs: list
    verts_xy: tuple = ()  # raw s16 (x,y) pairs per vertex (SH1X verbatim)
    verts_z: tuple = ()   # raw s16 z per vertex (SH1X verbatim)
    header_raw: bytes = b""   # the 24B s_MeshHeader verbatim


@dataclass
class PlmObject:
    name: str
    d_flag: int            # raw flags byte @11 of s_ModelHeader
    vertex_offset: int     # byte @9 [s_ModelHeader.vertexOffset]
    normal_offset: int     # byte @10 [s_ModelHeader.normalOffset]
    meshes: list
    header_raw: bytes = b""   # the 16B s_ModelHeader verbatim (SH1X)

    # ---- s_ModelHeader flag bitfield (decomp formats/model.h, verbatim) ----
    @property
    def flag_b0(self):          # bit 0: alternate transform path func_8005A21C
        return self.d_flag & 1

    @property
    def flag_b1(self):          # bits 1-3: OT section base selector
        return (self.d_flag >> 1) & 7

    @property
    def flag_b4(self):          # bits 4-5: alternate draw path func_80059D50
        return (self.d_flag >> 4) & 3

    @property
    def unk_b6(self):           # bits 6-7: unknown
        return (self.d_flag >> 6) & 3

    # func_800571D0 (bodyprog_80056D8C.c:164-187) — the OT section base
    # for this object's primitives, VERBATIM:  0->2, 1->0, 2->4, 3->33,
    # 4->66, 5->99 (default/unknown -> 2).
    OT_BASE_OF_FLAG_B1 = {0: 2, 1: 0, 2: 4, 3: 33, 4: 66, 5: 99}

    @property
    def ot_base(self):
        return self.OT_BASE_OF_FLAG_B1.get(self.flag_b1, 2)


# The consumer's (fog_poc.c) hardcoded IPD_MODEL_LAYERS name->field_B_1 table,
# embedded here ONLY for cross-verification of the export report: every
# mismatch between the TRUE PLM flags byte and the consumer's table is a
# layering defect in the rendered wallpaper and is reported loudly.
CONSUMER_IPD_MODEL_LAYERS = {
    "7201_1_H": 0, "7201_2_H": 0, "7201_3_H": 0,
    "7203_18_": 2, "7203_30_": 2, "7203_31_": 2,
    "7203_3_N": 1, "7203_6_H": 0,
    "7203_7_B": 5, "7206_1_H": 0, "7206_3_H": 0,
    "7207_1_B": 5, "7207_6_H": 0, "7207_7_H": 0,
    "7207_8_H": 0, "7207_9_H": 0,
    "7222_1_B": 4, "7222_7_B": 5,
    "CHAIN1_1": 5, "CHAIN1_2": 3, "CHAIN1_3": 1,
    "CHAIN2_1": 5, "CHAIN2_2": 3, "CHAIN2_3": 1, "CHAIN2_4": 5,
    "DOOR1_BA": 4, "NOTICE_N": 1,
    "THR0001": 0, "THR0002": 0, "THR0020": 0,
    "THR7202": 0, "THR7203": 0, "THR7204": 0,
    "THR7206": 0, "THR7207": 0, "TREE02": 0,
}


@dataclass
class PlmLibrary:
    source_name: str
    tex_names: list
    objects: dict          # name -> PlmObject (first match, legacy-identical)
    obj_order: list
    header_raw: bytes = b""     # the 20B s_LmHeader verbatim (SH1X)
    tex_raws: tuple = ()        # per-material 24B raw blocks (SH1X)
    order_raw: tuple = ()       # u8 model order verbatim (SH1X)
    trailing_raw: bytes = b""   # bytes after the last mesh table — SH1X
                                # (some PLMs carry unreferenced trailing
                                # data; the contract is EVERY byte)
    all_objects: list = field(default_factory=list)   # EVERY object header
                                # in FILE order, duplicates included (SH1X)

    @classmethod
    def parse(cls, data, base, source_name):
        if u16(data, base) != 0x0630:
            raise ValueError(f"{source_name}: bad PLM id 0x{u16(data, base):04X} at 0x{base:X}")
        tex_num = u8(data, base + 3)
        tex_off = u32(data, base + 4)
        # AUTHORITATIVE (v8, decomp s_LmHeader): modelCount is u8 @0x8; bytes
        # 0x9..0xB are padding (verified zero across every provided archive).
        # A nonzero pad byte is reported loudly instead of corrupting the count.
        obj_num = u8(data, base + 8)
        if any(data[base + 9 + k] for k in range(3)):
            raise ValueError(
                f"{source_name}: LmHeader modelCount padding bytes nonzero "
                f"({data[base + 9:base + 12].hex()}) - refusing to guess")
        obj_start = u32(data, base + 12)
        tex_names = []
        tex_raws = []
        for t in range(tex_num):
            o = base + tex_off + 24 * t
            tex_names.append(data[o:o + 24].decode("ascii", "replace").rstrip("\x00"))
            tex_raws.append(bytes(data[o:o + 24]))
        order_raw = tuple(data[base + u32(data, base + 16) + i]
                          for i in range(obj_num))
        lib = cls(source_name, tex_names, {}, [],
                  header_raw=bytes(data[base:base + 20]),
                  tex_raws=tuple(tex_raws), order_raw=order_raw)
        for i in range(obj_num):
            ooff = base + obj_start + 16 * i
            name = data[ooff:ooff + 8].decode("ascii", "replace").rstrip("\x00")
            mesh_num = u8(data, ooff + 8)
            vert_off = u8(data, ooff + 9)    # s_ModelHeader.vertexOffset
            nrm_off = u8(data, ooff + 10)    # s_ModelHeader.normalOffset
            d_flag = u8(data, ooff + 11)
            # s_ModelHeader.vertexOffset/normalOffset: when nonzero the engine
            # copies each mesh's vertices into the shared GTE scratch AT that
            # offset (func_8005759C) and the pack face indices address the
            # OFFSET buffer — mesh-local indexing would be WRONG.  Every
            # object in every provided archive has 0/0 (verified); a nonzero
            # value is a hard, loud error (refusing to guess).
            if vert_off != 0 or nrm_off != 0:
                raise ValueError(
                    f"{source_name}:{name}: s_ModelHeader vertexOffset="
                    f"{vert_off} normalOffset={nrm_off} — nonzero scratch "
                    f"offsets change face indexing (engine func_8005759C "
                    f"copies mesh verts at [vertexOffset..]) and are not "
                    f"supported; refusing to guess")
            data_off = u32(data, ooff + 12)
            meshes = []
            for m in range(mesh_num):
                moff = base + data_off + 24 * m
                pack_num, vert_num = u8(data, moff), u8(data, moff + 1)
                num_c, num_d = u8(data, moff + 2), u8(data, moff + 3)
                pack_off = u32(data, moff + 4)
                vxy_off = u32(data, moff + 8)
                vz_off = u32(data, moff + 12)
                nrm_off = u32(data, moff + 16)
                end_off = u32(data, moff + 20)
                # bounds guards (fail loudly rather than read garbage)
                end_of = lambda o, n: o + n <= len(data)
                if not (end_of(base + vxy_off, vert_num * 4)
                        and end_of(base + vz_off, vert_num * 2)
                        and end_of(base + nrm_off, num_c * 4)
                        and end_of(base + end_off, num_d)
                        and end_of(base + pack_off, pack_num * 20)):
                    raise ValueError(
                        f"{source_name}:{name} mesh{m}: table out of file bounds")
                verts = []
                verts_xy = []
                verts_z = []
                for v in range(vert_num):
                    verts_xy.append((s16(data, base + vxy_off + v * 4),
                                     s16(data, base + vxy_off + v * 4 + 2)))
                    verts_z.append(s16(data, base + vz_off + v * 2))
                    verts.append((verts_xy[-1][0], verts_xy[-1][1], verts_z[-1]))
                normals_a = []
                for n in range(num_c):
                    o = base + nrm_off + n * 4
                    normals_a.append((s8(data, o), s8(data, o + 1),
                                      s8(data, o + 2), u8(data, o + 3)))
                slot_normal = []
                for gi, a in enumerate(normals_a):
                    slot_normal.extend([gi] * a[3])
                slot_vertex = data[base + end_off: base + end_off + num_d]
                packs = []
                for j in range(pack_num):
                    poff = base + pack_off + j * 20
                    b7 = u8(data, poff + 7)
                    packs.append(Pack(
                        tex_num=b7 & 0x7F,
                        stp=(b7 >> 7) & 1,
                        cba=u16(data, poff + 2),
                        uv=((u8(data, poff), u8(data, poff + 1)),
                            (u8(data, poff + 4), u8(data, poff + 5)),
                            (u8(data, poff + 8), u8(data, poff + 9)),
                            (u8(data, poff + 10), u8(data, poff + 11))),
                        faces=(u8(data, poff + 12), u8(data, poff + 13),
                               u8(data, poff + 14), u8(data, poff + 15)),
                        normal_slots=(u8(data, poff + 16), u8(data, poff + 17),
                                      u8(data, poff + 18), u8(data, poff + 19)),
                        b6=u8(data, poff + 6),
                        b7=b7,
                    ))
                meshes.append(Mesh(verts, normals_a, slot_normal, slot_vertex, packs,
                                   verts_xy=tuple(verts_xy),
                                   verts_z=tuple(verts_z),
                                   header_raw=bytes(data[moff:moff + 24])))
            obj = PlmObject(name, d_flag, vert_off, nrm_off, meshes,
                            header_raw=bytes(data[ooff:ooff + 16]))
            lib.obj_order.append(name)
            # SH1X keeps EVERY object header (duplicates included) keyed by
            # their file index — the verbatim contract; `objects` (name ->
            # first match) stays legacy-identical for the render path.
            lib.all_objects.append(obj)
            if name not in lib.objects:      # first match wins (legacy-identical)
                lib.objects[name] = obj
        # SH1X: capture every byte after the last table (unreferenced
        # trailing data some PLMs carry) — computed by the caller, which
        # knows the file end (parse_ipd sets trailing_raw).
        return lib


# ---------------------------------------------------------------------------
# PLM archive discovery & object index (whole directory tree)
# ---------------------------------------------------------------------------
PLM_MAGIC = 0x0630


def plm_object_signature(obj, tex_names):
    """Content signature of a PLM object, used for cross-library identity.

    Two objects count as THE SAME object when their geometry is identical
    (same sorted vertex set per mesh, same pack faces/UVs/normal slots/cba)
    AND their effective texture binding is identical: pack.tex_num is only an
    index into the OWNING library's texture table, so it is resolved to the
    texture NAME here (a per-room table ordering difference is then neutral).
    stp (semi-transparency) is part of the identity.  This is exactly the
    evidence that legitimates importing e.g. DRFFFF's 'DAI' from a sibling
    room: all 5 sibling copies reduce to one signature.
    """
    parts = []
    for mesh in obj.meshes:
        packs = tuple(
            (p.cba, p.stp, tuple(p.uv), tuple(p.faces), tuple(p.normal_slots),
             tex_names[p.tex_num] if p.tex_num < len(tex_names) else None)
            for p in mesh.packs)
        parts.append((tuple(sorted(mesh.verts)), packs))
    return repr((len(obj.meshes), parts))


class PlmIndex:
    """Index of every PLM archive found anywhere in the scanned tree, plus
    every IPD's embedded PLM: object name -> [(location, library)].

    Locations are labels such as "BG:APU_GLB.PLM" (disk), "ITEM/KATANA.PLM"
    (inside an archive) or "EMB:DR00FF" (embedded in an IPD).  All lookups
    are case-insensitive; parse failures are recorded loudly, never raised.
    """

    def __init__(self, log=None):
        self.log = log or logging.getLogger("ipd2gltf")
        self.libs = []            # [dict(label, lib, key, in_archive)]
        self.by_name = {}         # UPPER object name -> [lib dicts]
        self.errors = []
        self.stats = {"plm_archives_indexed": 0, "embedded_libraries_indexed": 0,
                      "object_entries": 0, "unique_object_names": 0,
                      "parse_failures": 0}

    # -- population ------------------------------------------------------
    def _add_library(self, label, lib, sort_key, in_archive):
        rec = {"label": label, "lib": lib, "key": sort_key,
               "in_archive": in_archive}
        self.libs.append(rec)
        for name in lib.obj_order:
            obj = lib.objects.get(name)
            if obj is None:
                continue
            self.by_name.setdefault(name.upper(), []).append(rec)
            self.stats["object_entries"] += 1

    def add_discovered(self, entry):
        """Index a discovered file as a PLM archive (.PLM extension or a
        0x0630 magic header regardless of extension).  Returns True if the
        file was recognized as a PLM (successfully or not)."""
        try:
            data = entry.read_bytes()
        except Exception as e:
            self.errors.append(f"{entry.vpath}: read failed: {e}")
            return False
        if entry.ext != ".PLM" and (len(data) < 2 or
                                    u16(data, 0) != PLM_MAGIC):
            return False                      # not a PLM: not our business
        try:
            lib = PlmLibrary.parse(data, 0, entry.vpath)
        except Exception as e:
            self.errors.append(f"{entry.vpath}: PLM parse failed: {e}")
            self.stats["parse_failures"] += 1
            self.stats["plm_archives_indexed"] += 1
            return True
        self._add_library(entry.vpath, lib, entry.sort_key(), entry.in_archive)
        self.stats["plm_archives_indexed"] += 1
        return True

    def add_embedded(self, stem, data, plm_off):
        """Index the PLM embedded in one IPD as a virtual library EMB:<stem>."""
        try:
            lib = PlmLibrary.parse(data, plm_off, f"EMB:{stem}")
        except Exception as e:
            self.errors.append(f"EMB:{stem}: embedded PLM parse failed: {e}")
            self.stats["parse_failures"] += 1
            return False
        self._add_library(f"EMB:{stem}", lib, (1, 0, f"EMB:{stem}"), False)
        self.stats["embedded_libraries_indexed"] += 1
        return True

    def finalize(self):
        self.stats["unique_object_names"] = len(self.by_name)
        self.stats["archives_indexed"] = [
            {"location": r["label"], "objects": len(r["lib"].obj_order),
             "tex_names": r["lib"].tex_names} for r in self.libs]
        return self.stats

    # -- lookup ----------------------------------------------------------
    def find_object(self, name, exclude_labels=()):
        """All libraries containing an object with this exact name
        (case-insensitive), as [(label, lib, lib_rec)], deterministic order."""
        out = []
        for rec in self.by_name.get((name or "").upper(), []):
            if rec["label"] in exclude_labels:
                continue
            out.append((rec["label"], rec["lib"], rec))
        out.sort(key=lambda t: (t[2]["in_archive"], len(t[0]), t[0]))
        return out

    def find_prefix(self, name, exclude_labels=(), min_chars=3):
        """All (library, object-name) pairs whose object name shares a common
        prefix of >= min_chars with `name` (case-insensitive); exact matches
        excluded (find_object's business).  Every distinct object name in a
        library is listed - the ambiguity log must be complete."""
        ref = (name or "").upper()
        out = []
        for cand, recs in self.by_name.items():
            if cand == ref:
                continue
            common = 0
            for a, b in zip(ref, cand):
                if a != b:
                    break
                common += 1
            if common < min_chars:
                continue
            for rec in recs:
                if rec["label"] in exclude_labels:
                    continue
                out.append((rec["label"], rec["lib"], rec, cand))
        out.sort(key=lambda t: (t[2]["in_archive"], len(t[0]), t[0]))
        return out


# ---------------------------------------------------------------------------
# object-reference resolution (evidence ladder, fail-loud)
# ---------------------------------------------------------------------------
def resolve_object_reference(room, inst, resolver):
    """Resolve one instance's object reference through the evidence ladder.

    On success the instance carries resolved_lib/resolved_from (geometry
    imported verbatim from the winning library).  On failure the record says
    exactly why, listing every candidate considered.  Returns the ledger
    record; nothing is ever chosen silently or substituted.
    """
    ledger = resolver.object_ledger
    key = (room.name, inst.obj_name.upper(), inst.source)
    cached = resolver._obj_ledger_cache.get(key)
    if cached is not None:
        rec, rlib, rname = cached
        if rlib is not None:            # re-apply resolution to this instance
            inst.resolved_lib = rlib
            inst.resolved_from = rec.get("chosen") or ""
            inst.resolved_obj_name = rname or ""
        rec["instances"] = rec.get("instances", 0) + 1
        return rec

    def _finish():
        """Single exit point: cache (record + applied resolution) and ledger."""
        resolver._obj_ledger_cache[key] = (rec, inst.resolved_lib,
                                           inst.resolved_obj_name)
        ledger.append(rec)
        rec["instances"] = 1
        return rec

    flag_lib = room.plm if inst.source == "ipd" else room.glb
    flag_label = (f"{room.name}(embedded)" if inst.source == "ipd"
                  else (os.path.basename(flag_lib.source_name) if flag_lib
                        else f"{room.name[:-4]}_GLB.PLM"))
    rec = {"room": room.name, "ref": inst.obj_name, "source": inst.source,
           "expected_library": flag_label, "status": None, "strategy": None,
           "chosen": None, "candidates": [], "reason": "",
           "archives_scanned": [r["label"] for r in
                                (resolver.plm_index.libs if resolver.plm_index
                                 else [])],
           "folders_scanned": (resolver.discovery_stats.get("folders_scanned")
                               if resolver.discovery_stats else 0),
           "tree_evidence": [], "instances": 0}
    if resolver.tree is not None:
        stem = inst.obj_name.upper()
        hits = [k for k in resolver.tree.files if k.split(".")[0] == stem]
        for k in sorted(hits):
            for raw, rel in resolver.tree.files[k]:
                ev = f"{rel}  (file {k})"
                if ev not in rec["tree_evidence"]:
                    rec["tree_evidence"].append(ev)

    def _resolve_from(cands, strategy, note="", lookup_name=None):
        """Accept the candidate set only if all candidates are one object by
        signature; otherwise record the ambiguity and fail.  lookup_name is
        the name the candidates were FOUND by (differs from the reference in
        the name_variant stage)."""
        lname = (lookup_name or inst.obj_name).upper()
        sigs = {}
        obj_get = []
        for label, lib, *_ in cands:
            names = [n for n in lib.obj_order if n.upper() == lname]
            obj = lib.objects.get(names[0]) if names else None
            obj_get.append((label, lib, obj))
            sigs[label] = plm_object_signature(obj, lib.tex_names) if obj else None
        for (label, lib, obj), sig in zip(obj_get, [sigs[l[0]] for l in obj_get]):
            if obj is None:
                continue
            rec["candidates"].append({
                "location": label, "strategy": strategy,
                "object": (lookup_name or inst.obj_name),
                "object_signature": sig,
                "meshes": len(obj.meshes),
                "verts": sum(len(m.verts) for m in obj.meshes),
                "packs": sum(len(m.packs) for m in obj.meshes)})
        distinct = {s for s in sigs.values()}
        if len(distinct) == 1 and None not in distinct:
            label, lib, obj = obj_get[0]
            inst.resolved_lib = lib
            inst.resolved_from = label
            inst.resolved_obj_name = (lookup_name or inst.obj_name)
            rec["status"] = "resolved"
            rec["strategy"] = strategy
            rec["chosen"] = label
            rec["reason"] = (
                f"all {len(cands)} candidates share one object signature "
                f"(identical geometry and effective texture binding); "
                f"geometry imported verbatim from {label}{note}")
            return rec
        rec["status"] = "ambiguous"
        rec["strategy"] = strategy
        rec["reason"] = (
            f"{len(distinct)} different object signatures among "
            f"{len(cands)} candidates for {inst.obj_name!r} - cannot "
            f"disambiguate safely, nothing chosen")
        return rec

    # 1. flag-designated library (legacy semantics)
    if flag_lib is not None and inst.obj_name in flag_lib.objects:
        rec["status"] = "resolved"
        rec["strategy"] = "flag_library"
        rec["reason"] = "exact name in the flag-designated library (legacy semantics)"
        return _finish()

    idx = resolver.plm_index
    if idx is None:
        rec["status"] = "missing_object"
        rec["reason"] = "no PLM index available"
        return _finish()

    # 2. exact name in any other indexed library
    cands = idx.find_object(inst.obj_name, exclude_labels=(flag_label,))
    if cands:
        _resolve_from(cands, "sibling_exact")
        return _finish()
    # 3. normalized name variants (trailing '_', case is already folded)
    norm = inst.obj_name.rstrip("_").upper()
    if norm != inst.obj_name.upper():
        cands = idx.find_object(norm, exclude_labels=(flag_label,))
        if cands:
            _resolve_from(cands, "name_variant",
                          note=" (normalized name match)", lookup_name=norm)
            return _finish()
    # 4. shared-stem prefix, only if unambiguous
    pcands = idx.find_prefix(inst.obj_name, exclude_labels=(flag_label,))
    if pcands:
        # group by candidate object NAME; signatures keyed by (name, library)
        # so multiple same-prefix objects inside ONE library are all counted
        by_cand = {}
        for label, lib, recd, cand_name in pcands:
            by_cand.setdefault(cand_name, []).append((label, lib, recd))
        sigs = {}
        flat = []
        for cand_name, lst in sorted(by_cand.items()):
            for label, lib, _ in lst:
                obj = lib.objects.get(cand_name)
                if obj is None:
                    continue
                flat.append((label, lib, cand_name))
                sigs[(cand_name, label)] = plm_object_signature(
                    obj, lib.tex_names)
        if len(set(sigs.values())) == 1 and sigs:
            label, lib, cand_name = flat[0]
            inst.resolved_lib = lib
            inst.resolved_from = label
            inst.resolved_obj_name = cand_name
            rec["status"] = "resolved"
            rec["strategy"] = "prefix_inferred"
            rec["chosen"] = label
            rec["candidates"] = [
                {"location": lb, "strategy": "prefix_inferred",
                 "object_name": cn, "object_signature": sv}
                for (cn, lb), sv in sorted(sigs.items())]
            rec["reason"] = (f"INFERRED: unique object signature among prefix "
                             f"candidates sharing >= 3 leading characters; "
                             f"matched {cand_name!r} in {label}")
            return _finish()
        # ambiguous or empty -> fall through to missing with full candidate log
        rec["candidates"] = [
            {"location": lb, "strategy": "prefix_inferred",
             "object_name": cn, "object_signature": sv}
            for (cn, lb), sv in sorted(sigs.items())]
    rec["status"] = "missing_object"
    rec["reason"] = (
        f"object {inst.obj_name!r} not found in the flag-designated library "
        f"{flag_label!r} nor in any of the {len(idx.libs)} indexed PLM "
        f"archives/embedded libraries")
    if rec["candidates"]:
        rec["reason"] += (f"; prefix-stage candidates exist but are ambiguous "
                          f"(different signatures) - refusing to guess")
    return _finish()


# ---------------------------------------------------------------------------
# Billboard foliage clusters (tree canopies / bushes)
# ---------------------------------------------------------------------------
# Transcribed from the Silent Hill decompilation
# (github.com/shdecompilations/silent-hill-decomp):
#   src/bodyprog/gfx/billboard_draw.c  - D_800AE204 (quad table) and
#   D_800AE4DC (cluster composition), Gfx_BillboardDraw();
#   src/bodyprog/world/world_map.c     - the modelBuffer->field_10 loop that
#   calls Gfx_BillboardDraw(1|2, ...) per unk1/field_10 entry (w selects the
#   cluster type).
# Each quad: (positionY, radius, angle_deg, half_w, half_h), ALL values in
# FULL Q8 world units relative to the billboard ANCHOR (source axes: X east,
# Y DOWN, Z south; angle measured around the Y axis, quad anchor/bottom vertex
# at anchor + (radius*sin(angle), positionY, radius*cos(angle))).
# SIZE PROOF (v9): half_w/half_h are the world-space half-extents directly:
# Gfx_BillboardDraw computes halfW_px = Q12_MULT(field_6,
# Q12(ReadGeomScreen())/temp_a0) with temp_a0 = (RotTransPers() << 2) = the
# raw GTE depth in Q8 world units (libgte smp_02.o returns SZ3>>2; view
# matrices are Q8), and the GTE projects a world offset dx at depth z to
# H*dx/z pixels -> world half-width = field_6 Q8 = 2.12 m for the largest
# canopy diamond (total 4.23 x 3.02 m).
_BILLBOARD_QUAD_TABLE = [
    # ---- cluster type 1 (w=0): big tree canopy, 12 quads (D_800AE204[0..11]) ----
    (89,   102, 160.0, 542, 387),
    (21,   306, 300.0, 573, 356),
    (4,    306,  60.0, 558, 356),
    (-30,  289, 200.0, 527, 418),
    (-64,  255, 270.0, 527, 465),
    (-115, 306,  30.0, 449, 387),
    (-200, 289, 100.0, 589, 465),
    (-285, 221, 180.0, 496, 387),
    (-370, 272, 250.0, 465, 387),
    (-455, 255, 300.0, 449, 387),
    (-642, 170,   0.0, 418, 310),
    (-727, 136,  80.0, 387, 310),
    # ---- cluster type 2 (w=1): small bush, 5 quads (D_800AE204[12..16]) ----
    (13,   30,  220.0, 270, 270),
    (-64,  60,   50.0, 360, 240),
    (-115, 100, 180.0, 340, 190),
    (-141, 30,  100.0, 270, 240),
    (-192, 70,  320.0, 340, 180),
]
BILLBOARD_TYPES = {
    0: {"name": "canopy_12", "quads": _BILLBOARD_QUAD_TABLE[0:12]},
    1: {"name": "bush_5", "quads": _BILLBOARD_QUAD_TABLE[12:17]},
}

# The engine's billboard leaf texture (AUTHORITATIVE, v10):
#   filetable.c.USA.inc /* 1799 */ TIM/BG_ETC.TIM (FILE_TIM_BG_ETC_TIM), 66
#   blocks = 16896 bytes on disc: a 4bpp CLUT TIM whose pixel block is a
#   128x256-texel sheet with an 11 x 16-color CLUT block.  The engine loads
#   it ONCE at boot (GameState_KcetLogo_Update -> GameFs_BgEtcGfxLoad ->
#   Fs_QueuePostLoadTim) into VRAM page 12 (x=768, y=0) with the CLUT block
#   relocated to (192,0).  Gfx_BillboardDraw hardcodes tPage=44 (= VRAM
#   page 12, x=768, 4bpp, ABR bits set but INACTIVE because the ST bit is
#   clear) and clut=140 (= VRAM (192,2) = CLUT ROW 2 of the relocated
#   block); the quads sample the window u[0,63] v[128,191] = texel columns
#   0-63 of sheet rows 128-191.  Rendering is OPAQUE punch-through (PS1 4bpp
#   texel INDEX 0 fully transparent; setPolyGT4 code 0x3C has ST clear; the
#   window references palette colors 1-8 = dark greens, ~67.6% transparent
#   index 0), so alphaMode=MASK with cutoff 0.5 is engine-exact in glTF.
#   History: a synthetic reconstruction was used in v5 and REJECTED by the
#   user as too inaccurate; v6 dropped the billboards while the texture was
#   believed exe-embedded; v8/v9 textured the rings with TEST/LEAVES.TIM
#   (filetable 1768 - a dev-folder file referenced by NO decompiled code;
#   its bitmap/CLUT are byte-identical to the engine's BG_ETC window and
#   palette row 2, so those exports were visually right); v10 re-sources
#   the texture to the ENGINE-AUTHORITATIVE TIM/BG_ETC.TIM - the file
#   GameFs_BgEtcGfxLoad actually uploads into the billboard's texture page
#   (the embedded PNG is byte-identical to v9's).  v10 AUTO-DISCOVERS
#   BG_ETC.TIM through the standard texture resolver (exact_filename
#   strategy, like every other TIM) and exports the engine-exact rings
#   textured with it.  If BG_ETC.TIM is absent from every scanned root, the
#   drop is LOUD: every dropped anchor is recorded in
#   report['leaf_billboards_dropped'] and logged as a WARNING; no other
#   texture, material or mesh is ever affected.  There is NO LEAVES.TIM
#   fallback (user instruction: a fallback is a loss in accuracy).
#   --leaf-texture <PNG> overrides the discovered TIM with a user-supplied
#   extraction.
LEAF_TEXTURE_W, LEAF_TEXTURE_H = 64, 64     # the engine UV window size


# ---------------------------------------------------------------------------
# IPD parsing (room assembly)
# ---------------------------------------------------------------------------
@dataclass
class CollisionData:
    """s_IpdCollisionData @0x54, fully parsed + verbatim (SH1X contract).

    Array offsets in the FILE are RELATIVE TO 0x54 (the collision block
    start) — measured on HP0000..HP0003 + THRF9FD (the splitV/surf/poly
    tables tile the region between modelOrder and the PLM exactly when
    read as 0x54+field; absolute-reading overlaps the instance tables).
    """
    position_x: int = 0            # s32 Q23.8
    position_z: int = 0
    n_split_v: int = 0
    n_surface: int = 0
    n_polygon: int = 0
    n_cylinder: int = 0
    split_vertices: tuple = ()      # ((x,y,z) s16 Q7.8, ...)
    surfaces: tuple = ()           # dicts, parsed bitfields
    polygons: tuple = ()           # dicts
    cylinders: tuple = ()
    cell_size: int = 0             # s16 Q8
    cell_count_x: int = 0
    cell_count_z: int = 0
    shape_allocs: tuple = ()       # ((shapeLutIdx, surfaceLutIdx) s16, ...)
    shape_lut_size: int = 0
    surface_lut_size: int = 0
    shape_lut: tuple = ()           # u8
    surface_lut: tuple = ()         # u8
    shape_pass_counter: int = 0
    stamp_buffer: tuple = ()        # u8 x 256
    header_raw: bytes = b""        # 0x54..0x88 verbatim


def parse_collision(data):
    """Parse the s_IpdCollisionData at FILE offset 0x54 (fixed header
    position; ipd.ksy collision_offset).  Offsets are collision-relative."""
    co = 0x54
    if len(data) < co + 0x34:
        return None
    c = CollisionData()
    c.position_x, c.position_z = s32(data, co), s32(data, co + 4)
    c.n_split_v, c.n_surface, c.n_polygon, c.n_cylinder = (
        data[co + 8], data[co + 9], data[co + 10], data[co + 11])
    # array offsets are RELATIVE TO THE COLLISION BLOCK (0x54): the runtime
    # struct's pointers are ipdHdr-relative and PTR_OFFSET_RESOLVE'd against
    # the collision block start; measured — the splitV/surf/poly tables then
    # tile the gap between modelOrder and the PLM exactly (HP0003:
    # 0x4b4..0x1113 vs lmHdr 0x1114).
    sv_off, su_off, pg_off, cy_off = struct.unpack_from("<IIII", data, co + 12)
    sa_off = u32(data, co + 0x20)
    sv_off += co; su_off += co; pg_off += co; cy_off += co; sa_off += co
    c.cell_size = s16(data, co + 0x1C)
    c.cell_count_x, c.cell_count_z = data[co + 0x1E], data[co + 0x1F]
    c.shape_lut_size, c.surface_lut_size = u16(data, co + 0x24), u16(data, co + 0x24 + 2)
    shl_off, sul_off = struct.unpack_from("<II", data, co + 0x28)
    shl_off += co; sul_off += co
    c.shape_pass_counter = data[co + 0x30]
    c.stamp_buffer = tuple(data[co + 0x34:co + 0x134])
    c.header_raw = bytes(data[co:co + 0x34])
    end = len(data)
    def ok(off, n):
        return off + n <= end
    if ok(sv_off, c.n_split_v * 6) and c.n_split_v:
        c.split_vertices = tuple(
            struct.unpack_from("<3h", data, sv_off + 6 * i)
            for i in range(c.n_split_v))
    if ok(su_off, c.n_surface * 12) and c.n_surface:
        surfs = []
        for i in range(c.n_surface):
            o = su_off + 12 * i
            u16v = u16(data, o + 6)
            surfs.append({
                "offset": list(struct.unpack_from("<3h", data, o)),
                "floorType": u16v & 0x1F,
                "disableHeight": (u16v >> 5) & 7,
                "surfaceCacheIdx": (u16v >> 8) & 3,
                "triggerFlagIdx": (u16v >> 11) & 0xF,
                "slopeGradientX": s16(data, o + 8),
                "slopeGradientZ": s16(data, o + 10),
                "raw": bytes(data[o:o + 12]),
            })
        c.surfaces = tuple(surfs)
    if ok(pg_off, c.n_polygon * 10) and c.n_polygon:
        polys = []
        for i in range(c.n_polygon):
            o = pg_off + 10 * i
            # decomp s_IpdPolygon layout (formats/ipd.h), 10 bytes:
            #   bytes 0-1: offsetX:14 | triggerFlagIdxHigh:2   (u16)
            #   bytes 2-3: offsetY:14 | triggerFlagIdxLow:2    (u16)
            #   bytes 4-5: offsetZ (s16, no bits)
            #   bytes 6-9: splitVertexIdx0/1, surfaceIdx0/1
            # ksy combines the trigger bits as (low << 2) | high.
            wx, wy = u16(data, o), u16(data, o + 2)
            polys.append({
                "offsetX": wx & 0x3FFF,
                "offsetY": wy & 0x3FFF,
                "offsetZ": s16(data, o + 4),
                "triggerFlagIdx": ((wy >> 14) & 3) << 2 | ((wx >> 14) & 3),
                "splitVertexIdx0": data[o + 6],
                "splitVertexIdx1": data[o + 7],
                "surfaceIdx0": data[o + 8],
                "surfaceIdx1": data[o + 9],
                "raw": bytes(data[o:o + 10]),
            })
        c.polygons = tuple(polys)
    if ok(cy_off, c.n_cylinder * 10) and c.n_cylinder:
        cyls = []
        for i in range(c.n_cylinder):
            o = cy_off + 10 * i
            u16v = u16(data, o)
            cyls.append({
                "floorType": u16v & 0x1F,
                "disableHeight": (u16v >> 5) & 7,
                "triggerFlagIdx": (u16v >> 12) & 0xF,
                "offset": list(struct.unpack_from("<3h", data, o + 2)),
                "radius": s16(data, o + 8),
                "raw": bytes(data[o:o + 10]),
            })
        c.cylinders = tuple(cyls)
    n_alloc = (c.cell_count_x * c.cell_count_z) + 1
    if ok(sa_off, n_alloc * 4) and n_alloc > 1:
        c.shape_allocs = tuple(
            struct.unpack_from("<2h", data, sa_off + 4 * i)
            for i in range(n_alloc))
    if ok(shl_off, c.shape_lut_size) and c.shape_lut_size:
        c.shape_lut = tuple(data[shl_off:shl_off + c.shape_lut_size])
    if ok(sul_off, c.surface_lut_size) and c.surface_lut_size:
        c.surface_lut = tuple(data[sul_off:sul_off + c.surface_lut_size])
    return c


@dataclass
class Instance:
    obj_name: str
    source: str            # 'ipd' | 'glb'
    rt: tuple              # 9 s16 values, row-major 3x3 (1.3.12 fixed point)
    t: tuple               # (tx, ty, tz)
    context: str = ""      # "pos group g entry e" for error reporting
    group: int = 0         # index of the owning model buffer (pos group) —
                           # the engine's draw unit (WorldMap_Draw iterates
                           # modelBuffers; the billboard loop runs per buffer)
    resolved_lib: object = None   # PlmLibrary the object was imported from
    resolved_from: str = ""      # index label of that library
    resolved_obj_name: str = ""  # object name inside resolved_lib (prefix case)
    obj_idx: int = -1      # modelInfos index (the engine's obj_id) — SH1X
    raw: bytes = b""       # the 36B s_IpdModelInstance verbatim — SH1X

    @property
    def lookup_name(self):
        return self.resolved_obj_name or self.obj_name

    @property
    def effective_source(self):
        if self.resolved_lib is not None:
            return f"imported:{self.resolved_from}"
        return self.source


@dataclass
class Room:
    name: str
    path: str
    x_pos: int
    y_pos: int
    pos_num: int = 0
    instances: list = field(default_factory=list)
    unplaced: list = field(default_factory=list)   # embedded-PLM objects never placed
    sub_objects: list = field(default_factory=list) # unk1 table entries (leaf placements)
    problems: list = field(default_factory=list)
    # ---- v11: the engine's DRAW-ORDER system (WorldMap_Draw, world_map.c) ----
    order_count: int = 0            # unk1_num @10 [modelOrderCount]
    model_order: list = field(default_factory=list)   # u8 buffer indices
    subcell_table: dict = field(default_factory=dict)  # (z,x) -> (start,count)
    buffer_subcells: dict = field(default_factory=dict)  # buffer -> [(z,x)]
    order_problems: list = field(default_factory=list)
    # per-buffer billboard anchor records, keyed by buffer index (the engine
    # draws a buffer's field_10 anchors AFTER that buffer's instances)
    buffer_billboards: dict = field(default_factory=dict)
    # ---- SH1X verbatim capture (byte-identical extras contract) ----
    header_raw: bytes = b""            # the 84B s_IpdHeader verbatim
    model_info_raws: tuple = ()        # per-modelInfo 16B raw blocks
    model_buffer_raws: tuple = ()      # per-modelBuffer 24B raw blocks
    billboard_raws: dict = field(default_factory=dict)   # buffer -> [8B blocks]
    subchunk_raws: dict = field(default_factory=dict)    # buffer -> [8B blocks]
    file_size: int = 0
    file_sha256: str = ""
    # collision (s_IpdCollisionData @0x54) — fully parsed + verbatim
    collision: object = None
    collision_raw: bytes = b""          # 0x54 .. lmHdr (incl. arrays) verbatim


def parse_ipd(path, resolver):
    """Parse one IPD file into a Room (instances referencing PLM libraries)."""
    data = open(path, "rb").read()
    stem = os.path.splitext(os.path.basename(path))[0]
    room = Room(stem, path, s8(data, 2), s8(data, 0 + 3), pos_num=u8(data, 9))
    room.file_size = len(data)
    room.file_sha256 = hashlib.sha256(data).hexdigest()
    room.header_raw = bytes(data[0:0x54])
    room.collision = parse_collision(data)
    if u8(data, 0) != 0x14:
        raise ValueError(f"{stem}: bad IPD id 0x{u8(data, 0):02X}")
    plm_off = u32(data, 4)
    obj_num, pos_num = u8(data, 8), u8(data, 9)
    room.order_count = u8(data, 10)          # [modelOrderCount]
    if u8(data, 11) != 0:                   # unk2 @11: observed 0 everywhere
        room.problems.append(f"{stem}: IPD header byte @11 is "
                             f"{u8(data, 11)} (expected 0) — reported, not guessed")
    pad_12_19 = data[12:20]
    if any(pad_12_19):
        room.problems.append(f"{stem}: IPD header pad bytes 12..19 nonzero "
                             f"({pad_12_19.hex()}) — reported, not guessed")
    name_off = u32(data, 20)
    data_off = u32(data, 24)
    order_off = u32(data, 80)               # [modelOrderList]
    room.plm = PlmLibrary.parse(data, plm_off, f"{stem}(embedded)")
    # SH1X: the full verbatim collision block (header + arrays) spans
    # 0x54 .. plm_off (the PLM start) — includes every array between.
    room.collision_raw = bytes(data[0x54:plm_off]) if plm_off > 0x54 else b""
    # SH1X: unreferenced trailing bytes of the embedded PLM (after the
    # LAST mesh table, to the file end) — the byte-identical contract.
    last_end = plm_off + 20
    for obj in room.plm.all_objects:
        for mesh in obj.meshes:
            # every table of this mesh, PLM-relative
            mh = mesh.header_raw
            po, vx, vz, nm_, sl = struct.unpack_from("<IIIII", mh, 4)
            last_end = max(last_end,
                           plm_off + po + len(mesh.packs) * 20,
                           plm_off + vx + len(mesh.verts) * 4,
                           plm_off + vz + len(mesh.verts) * 2,
                           plm_off + nm_ + len(mesh.normals_a) * 4,
                           plm_off + sl + len(mesh.slot_vertex))
    if len(data) > last_end:
        room.plm.trailing_raw = bytes(data[last_end:])
    glb_ent = resolver.find_glb(stem)
    room.glb = None
    if glb_ent is not None:
        room.glb = PlmLibrary.parse(glb_ent.read_bytes(), 0,
                                    os.path.basename(glb_ent.vpath))
    # ---- v11: the per-subcell DRAW-RANGE table + model ORDER list ----------
    # WorldMap_Draw (world_map.c:1349-1352):
    #   temp_fp = &ipdHdr->textureCount + (subcellZ * 10) + (subcellX * 2);
    #   for (i = temp_fp[0]; i < (temp_fp[1] + temp_fp[0]); i++)
    #       modelBuffer = &ipdHdr->modelBuffers[ipdHdr->modelOrderList[i]];
    # textureCount sits at runtime offset 0x1C = FILE offset 28; the table is
    # 5x5 entries of (u8 start, u8 count) = 50 bytes at file 28..77; the
    # model order list is u8[modelOrderCount] at file order_off (header @80).
    if room.order_count:
        if order_off + room.order_count > len(data):
            room.problems.append(
                f"{stem}: model order list at 0x{order_off:X}+{room.order_count} "
                f"out of file bounds — order data NOT parsed")
        else:
            room.model_order = [u8(data, order_off + i)
                                for i in range(room.order_count)]
            oob = [v for v in room.model_order if v >= pos_num]
            if oob:
                room.problems.append(
                    f"{stem}: model order list references nonexistent model "
                    f"buffers {sorted(set(oob))} (pos_num={pos_num})")
    for sz in range(5):
        for sx in range(5):
            o = 28 + sz * 10 + sx * 2
            start, count = u8(data, o), u8(data, o + 1)
            room.subcell_table[(sz, sx)] = (start, count)
    # buffer -> subcells that draw it (and per-range ascending-order check:
    # the engine's within-range order is the list order — MEASURED ascending
    # in every provided file, which is why file order == engine add order)
    for (sz, sx), (start, count) in room.subcell_table.items():
        seg = room.model_order[start:start + count] if room.model_order else []
        if len(seg) != count:
            room.order_problems.append(
                f"subcell ({sx},{sz}) range [{start},{start + count}) exceeds "
                f"the model order list ({len(room.model_order)} entries)")
            continue
        for b in seg:
            room.buffer_subcells.setdefault(b, []).append((sx, sz))
        if seg != sorted(seg):
            room.order_problems.append(
                f"subcell ({sx},{sz}) model order range is NOT ascending "
                f"({seg}) — the engine would draw these buffers in THIS "
                f"order, which differs from the file order; the export's "
                f"file-order emission may mis-layer same-bucket ties "
                f"between these buffers (reported loudly, not guessed)")
    unreferenced = [b for b in range(pos_num)
                    if b not in room.buffer_subcells]
    if unreferenced:
        room.order_problems.append(
            f"model buffers {unreferenced} are referenced by NO subcell "
            f"range — the engine NEVER draws them; still exported (the "
            f"wallpaper shows the whole scene — documented static "
            f"deviation) and reported here")
    # name list
    names = []
    model_info_raws = []
    for i in range(obj_num):
        o = name_off + 16 * i
        if o + 16 > len(data):
            room.problems.append(f"objname entry {i} out of bounds")
            break
        names.append((s32(data, o),
                      data[o + 4:o + 12].decode("ascii", "replace").rstrip("\x00")))
        model_info_raws.append(bytes(data[o:o + 16]))
    room.model_info_raws = tuple(model_info_raws)
    used_names = set()
    model_buffer_raws = []
    for pi in range(pos_num):
        poff = data_off + 24 * pi
        if poff + 24 > len(data):
            room.problems.append(f"pos group {pi} header out of bounds")
            break
        pobj_num = u8(data, poff)
        unk1_num = u8(data, poff + 1)
        unk2_num = u8(data, poff + 2)
        model_buffer_raws.append(bytes(data[poff:poff + 24]))
        pdata_off = u32(data, poff + 12)
        punk1_off = u32(data, poff + 16)
        punk2_off = u32(data, poff + 20)
        room.billboard_raws[pi] = []
        room.subchunk_raws[pi] = []
        for j in range(pobj_num):
            doff = pdata_off + 36 * j
            if doff + 36 > len(data):
                room.problems.append(f"{stem}: pos group {pi} instance {j} out of bounds")
                break
            obj_id = s32(data, doff)
            if not (0 <= obj_id < len(names)):
                room.problems.append(
                    f"{stem}: pos group {pi} instance {j}: obj_id {obj_id} out of range")
                continue
            flag, name = names[obj_id]
            rt = tuple(s16(data, doff + 4 + k * 2) for k in range(9))
            tx, ty, tz = s32(data, doff + 24), s32(data, doff + 28), s32(data, doff + 32)
            ctx = f"pos group {pi} entry {j}"
            if flag == 0:
                used_names.add(name)
                room.instances.append(Instance(name, "ipd", rt, (tx, ty, tz), ctx,
                                               group=pi, obj_idx=obj_id,
                                               raw=bytes(data[doff:doff + 36])))
            elif flag == 1:
                used_names.add(name)
                room.instances.append(Instance(name, "glb", rt, (tx, ty, tz), ctx,
                                               group=pi, obj_idx=obj_id,
                                               raw=bytes(data[doff:doff + 36])))
            else:
                room.problems.append(f"{stem}: unknown objname flag {flag} for {name!r}")
        # ---- billboard foliage anchor table ("unk1" / decomp field_10) ------
        # unk1: unk1_num entries x 8 bytes at punk1_off, each (s16 x, y, z, w)
        # in Q8 world units (chunk-relative) - the ANCHOR POSITIONS of
        # camera-facing foliage billboard clusters.
        #
        # DEFINITIVE semantics (silent-hill-decomp, src/bodyprog/world/world_map.c,
        # Ipd_ChunkDraw loop over modelBuffer->field_10):
        #   switch ((s8)entry->pad) {          // the w field
        #     case 0: Gfx_BillboardDraw(1, vx+chunkBoundX, vy, vz+chunkBoundZ, ...)
        #     case 1: Gfx_BillboardDraw(2, ...)
        #   }
        # Gfx_BillboardDraw (src/bodyprog/gfx/billboard_draw.c) draws a RING of
        # screen-aligned diamond quads (type 1 = 12 quads = tree canopy, type 2
        # = 5 quads = bush) around the anchor using the hardcoded D_800AE204
        # table, textured with the REAL ENGINE DISC FILE TIM/BG_ETC.TIM
        # (filetable index 1799, uploaded at boot into VRAM page 12 by
        # GameFs_BgEtcGfxLoad; tpage 44 = page 12, clut 140 = (192,2) = CLUT
        # row 2; window u[0,63] v[128,191] of the 128x256 4bpp sheet; opaque
        # punch-through rendering - ST bit clear, texel index 0 transparent).
        # The PLM libraries' LEAF_1/LEAF_2 triangles are never rendered by
        # this path (they are unplaced library entries).
        #
        # SCALE (Q8 = IPD world units /256, decomp-verified, v9):
        #   * entry positions are Q8 chunk-relative (decomp: Q8_TO_Q12(vx +
        #     chunkBoundX) - same convention as instance translations);
        #   * D_800AE204 ring offsets (positionY 89..-727, radius 102..306) are
        #     Q8 units applied directly: the type-1 ring spans anchor+0.35 ..
        #     anchor-2.84 m in the Y-DOWN source (i.e. 0.35 m below to 2.84 m
        #     ABOVE the anchor);
        #   * quad half-sizes (field_6/field_8, 387..589) are ALSO full Q8
        #     units: RotTransPers returns SZ3>>2 (libgte disassembly), so
        #     Gfx_BillboardDraw's `temp_a0 = ret<<2` is the raw Q8 depth and
        #     halfW_px = field_6*H/z means world half-width = field_6 Q8
        #     (542 -> 2.12 m half-width, 4.23 x 3.02 m diamond).  The v6-v8
        #     "/4" reading was WRONG (it misread the RotTransPers return as
        #     the raw depth); rectified in v9.
        for k in range(unk1_num):
            if punk1_off + 8 * k + 8 > len(data):
                room.problems.append(
                    f"{stem}: pos group {pi} billboard entry {k} out of bounds")
                break
            sx, sy, sz, sw = struct.unpack_from("<4h", data, punk1_off + 8 * k)
            room.billboard_raws[pi].append(
                bytes(data[punk1_off + 8 * k:punk1_off + 8 * k + 8]))
            if sw not in BILLBOARD_TYPES:
                room.problems.append(
                    f"{stem}: pos group {pi} billboard entry {k}: unknown "
                    f"cluster type w={sw} - entry NOT placed (witnessed values "
                    f"across provided data are 0 and 1 only)")
                room.sub_objects.append(
                    {"group": pi, "index": k, "x": sx, "y": sy, "z": sz,
                     "w": sw, "cluster": None, "quads": 0,
                     "reason": f"unknown cluster type w={sw}"})
                continue
            room.sub_objects.append(
                {"group": pi, "index": k, "x": sx, "y": sy, "z": sz,
                 "w": sw, "cluster": BILLBOARD_TYPES[sw]["name"],
                 "quads": len(BILLBOARD_TYPES[sw]["quads"])})
            room.buffer_billboards.setdefault(pi, []).append(
                {"group": pi, "index": k, "x": sx, "y": sy, "z": sz,
                 "w": sw, "cluster": BILLBOARD_TYPES[sw]["name"],
                 "quads": len(BILLBOARD_TYPES[sw]["quads"])})
        # subchunk visibility ranges (s_SubchunkRange 8B each) — SH1X verbatim
        for k in range(unk2_num):
            if punk2_off + 8 * k + 8 > len(data):
                room.problems.append(
                    f"{stem}: pos group {pi} subchunk range {k} out of bounds")
                break
            room.subchunk_raws[pi].append(
                bytes(data[punk2_off + 8 * k:punk2_off + 8 * k + 8]))
    room.model_buffer_raws = tuple(model_buffer_raws)
    # unplaced embedded-PLM objects (never referenced by position data).
    # DEFAULT: not exported (the IPD's position data is the authoritative placement;
    # exporting them at identity transform would fabricate placement, which the legacy
    # tool did only as a completeness hack).  --include-unused puts them in a clearly
    # labeled node at identity transform, matching legacy behavior.
    room.unplaced = [n for n in dict.fromkeys(room.plm.obj_order) if n not in used_names]
    # object-reference resolution (flag-library -> sibling -> variant -> prefix).
    # One ledger record per distinct (room, name, source) - the COMPLETE
    # reference ledger, resolved and unresolved alike, as required by the
    # audit spec.  Nothing is skipped silently.
    if resolver.plm_index is not None:
        for inst in room.instances:
            resolve_object_reference(room, inst, resolver)
    return room


# ---------------------------------------------------------------------------
# Billboard foliage cluster meshes (engine-exact rings; textured with the
# auto-discovered TIM/BG_ETC.TIM, or --leaf-texture; dropped loudly only
# when neither is available)
# ---------------------------------------------------------------------------
# Quad geometry follows Gfx_BillboardDraw exactly: each diamond has its
# BOTTOM VERTEX at the ring position, apex 2*half_h straight up (source
# -Y), side vertices +-half_w along the tangent at half_h above the bottom
# vertex, and the engine UV window u[0,63] x v[128,191] of the BG_ETC sheet
# assigned to the corners exactly as the decompiled packet code writes them
# (top=(0,128), right=(63,128), left=(0,191), bottom=(63,191) - relative to
# the 64x64 window these are (0,0),(63,0),(0,63),(63,63)).
# ENGINE SIZE (v9, CORRECTED): half_w/half_h are used as FULL Q8 world
# units.  Proof chain: libgte smp_02.o RotTransPers returns SZ3>>2
# (`mfc2 $2, $19; jr $ra; sra $2, $2, 2`), so Gfx_BillboardDraw's
# `temp_a0 = ret << 2` is the RAW GTE depth (Q8 world units - the view
# matrix pipeline is Q8, and the mesh path stores the same raw depth via
# gte_stsz3 for its fog far-clip comparison), and
# halfW_px = Q12_MULT(field_6, Q12(H)/temp_a0) = field_6*H/z.  The GTE
# projects a world offset dx at depth z to H*dx/z pixels, therefore the
# diamond's world half-width IS field_6 Q8 (542 -> 2.12 m; 4.23 x 3.02 m
# diamond).  (v6-v8 divided by 4 - a misreading of the RotTransPers return
# - and produced quarter-size diamonds; rectified here.)
# VERTICAL (engine-literal, only mode): the rasterizer puts the BOTTOM
# vertex at the ring position's screen y and the apex 2*half_h above it -
# with a level camera that is exactly "diamond hangs UP from the ring
# position" in world space (setXY4(x, y-2h, x+w, y-h, x-w, y-h, x, y)).
# ORIENTATION (the ONLY forced deviation, minimal): the engine draws every
# diamond SCREEN-ALIGNED (it rotates to face the camera each frame); a
# static glTF file cannot track a viewer.  Each engine diamond is exported
# as exactly ONE vertical quad whose horizontal axis is the RING TANGENT at
# the diamond's angle - i.e. the quad's normal is the radial direction at
# that ring slot (the negation of the engine's own computed per-slot normal
# D_800AE204.field_C = (-sin, 0, -cos)).  NO geometry is added, removed or
# duplicated: 12 quads per canopy anchor, 5 per bush anchor, exactly the
# engine's per-cluster quad count, at the engine's exact ring positions,
# sizes, UVs and texture.  (The v8 "crossed-quad pair" - a 90-degree
# rotated duplicate added per diamond - was an ADDED artifact and has been
# REMOVED.)  doubleSided is engine-exact (the PSX GPU has no backface
# culling; the engine draws both windings of every quad).


def _leaf_material(builder, report, leaf_texture_png, leaf_texture_source):
    """Billboard leaf material bound to the REAL engine texture.

    v10: the texture is either the auto-discovered TIM/BG_ETC.TIM (engine
    window u[0,63] v[128,191], CLUT row 2 - see TextureLibrary.
    load_leaf_texture) or a --leaf-texture PNG override.  Returns the
    material index.  Engine-exact properties: alphaMode MASK cutoff 0.5
    (opaque punch-through; PS1 4bpp texel index 0 transparent, ST bit clear)
    and doubleSided (engine quads are camera-facing; static tangential
    diamonds are seen from both sides).
    """
    key = ("BILLBOARD",)
    if key in builder._material_keys:
        return builder._material_keys[key]
    if leaf_texture_png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(
            f"billboard leaf texture from {leaf_texture_source!r} is not a PNG "
            f"(bad magic {leaf_texture_png[:8]!r}); the engine texture is "
            f"TIM/BG_ETC.TIM (filetable 1799; VRAM tpage 44 = page 12, "
            f"clut 140 = (192,2) = CLUT row 2, window u[0,63] v[128,191] "
            f"of the 128x256 sheet)")
    img_idx = builder.add_image(leaf_texture_png, "BILLBOARD_LEAF")
    tex_idx = builder.add_texture(img_idx)
    mat_idx = builder.add_material(
        key, "BILLBOARD_LEAF", tex_idx=tex_idx,
        has_alpha=True, alpha_mode="MASK", alpha_cutoff=0.5,
        double_sided=True)
    return mat_idx


def build_billboard_meshes(room, builder, report, leaf_texture=None,
                          anchors=None):
    """One mesh per unk1/field_10 anchor: the engine's billboard quad ring.

    v11: `anchors` selects WHICH buffer's anchors to build (the engine runs
    the field_10 loop once per model buffer, AFTER that buffer's instances —
    world_map.c:1378; the export interleaves accordingly).  None = all
    anchors (v10 behavior, used by the loud-drop bookkeeping).

    v10 POLICY (unchanged): textured with the REAL engine texture - either
    the auto-discovered TIM/BG_ETC.TIM (filetable 1799, uploaded at boot
    into VRAM page 12 by GameFs_BgEtcGfxLoad; decoded as the engine window
    u[0,63] v[128,191] with CLUT row 2 and PS1 index-0 punch-through
    alpha) or a --leaf-texture PNG override.  `leaf_texture` is a dict
    {"png": bytes, "source": str, "status": str} or None.  Only when None
    are the leaf billboards DROPPED - and every dropped anchor is loudly
    reported in report['leaf_billboards_dropped'] (never a silent drop).
    There is NO LEAVES.TIM fallback (user instruction: a fallback is a
    loss in accuracy - LEAVES.TIM is referenced by no decompiled code).

    Returns the created mesh indices (also records cluster stats in report).
    """
    mesh_indices = []
    if not room.sub_objects:
        return mesh_indices
    if not leaf_texture:
        # ---- DROP, loudly: no real leaf texture available in any root ------
        # ONLY the leaf billboards are dropped; every other texture, material
        # and mesh of the room is untouched (proven by corpus regression).
        # v11: the drop report is AGGREGATED across per-buffer calls — each
        # call counts ONLY its own `anchors` scope (a buffer's field_10
        # entries), so the totals equal the single-pass v10 numbers exactly.
        cur = [e for e in (room.sub_objects if anchors is None else anchors)
               if e.get("cluster")]
        by_cluster = {}
        for e in cur:
            by_cluster[e["cluster"]] = by_cluster.get(e["cluster"], 0) + 1
        drop = report.get("leaf_billboards_dropped")
        if drop is None:
            drop = report["leaf_billboards_dropped"] = {
                "anchors_dropped": 0,
                "clusters": {},
                "quads_not_drawn": 0,
                "entries": [],
                "unplaced_entries": [],
                "reason": (
                "the engine billboard leaf texture TIM/BG_ETC.TIM "
                "(filetable index 1799; loaded at boot into VRAM page 12 by "
                "GameFs_BgEtcGfxLoad and sampled by Gfx_BillboardDraw at VRAM "
                "tpage 44, clut 140 = (192,2) = CLUT row 2, window "
                "u[0,63] v[128,191] of the 128x256 sheet) was not found in "
                "any scanned root or archive; the v5 synthetic "
                "reconstruction was judged too inaccurate by the user and is "
                "REMOVED - the foliage billboards are dropped rather than "
                "rendered inaccurately"),
            }
        # aggregate THIS call's (per-buffer) anchors into the drop report
        drop["anchors_dropped"] += len(cur)
        for k, v in by_cluster.items():
            drop["clusters"][k] = drop["clusters"].get(k, 0) + v
        drop["quads_not_drawn"] += sum(e.get("quads", 0) for e in cur)
        drop["entries"].extend(dict(e) for e in cur)
        if anchors is None:      # only the full-room call reports unplaced
            drop["unplaced_entries"] = [dict(e) for e in room.sub_objects
                                        if not e.get("cluster")]
        drop["policy"] = (
            "drop the leaf billboards entirely; provide the real texture "
            "either as a discoverable BG_ETC.TIM in any search root (the "
            "standard resolver picks it up automatically) or via "
            "--leaf-texture <PNG> to export the engine-exact rings.  "
            "There is NO TEST/LEAVES.TIM fallback: that dev-folder file "
            "is referenced by no decompiled code and substituting it "
            "would be a loss in accuracy (user instruction).")
        drop["scope"] = (
            "ONLY the engine-drawn leaf billboards (unk1/field_10 "
            "foliage anchors) are dropped.  NO TIM-derived texture, "
            "material, mesh, or any other room geometry is affected - "
            "verified by byte-level regression on the full corpus.")
        return mesh_indices
    mat_idx = _leaf_material(builder, report, leaf_texture["png"],
                             leaf_texture["source"])
    report["billboard_texture"] = {
        "status": leaf_texture["status"],
        "source": leaf_texture["source"],
        "engine_facts": {
            "file": "TIM/BG_ETC.TIM",
            "filetable_index": 1799,
            "disc_size": "66 blocks = 16896 bytes",
            "loader": "GameState_KcetLogo_Update (b_konami.c:149) -> "
                      "GameFs_BgEtcGfxLoad (world_draw.c:80-85) -> "
                      "Fs_QueuePostLoadTim: pixel block -> VRAM page 12 "
                      "(768,0), CLUT block -> (192,0)",
            "format": "4bpp CLUT TIM, 128x256-texel sheet, 11 x 16-color "
                      "palettes (window references colors 1-8)",
            "vram": "tpage 44 = page 12 (x=768, 4bpp); clut 140 = (192,2) "
                    "= CLUT row 2 of the relocated block",
            "uv_window": "u[0,63] v[128,191] = texel columns 0-63 of "
                         "sheet rows 128-191 (a 64x64 window)",
            "rendering": "opaque punch-through (ST bit clear; texel index 0 "
                         "transparent) -> glTF alphaMode MASK cutoff 0.5",
            "no_fallback": "TEST/LEAVES.TIM (filetable 1768) is referenced "
                           "by no decompiled code and is NEVER used as a "
                           "fallback (user instruction: a fallback is a "
                           "loss in accuracy)",
        },
    }
    mx = MAP_CELL * room.x_pos
    mz = MAP_CELL * room.y_pos
    # v11: stats MERGE across per-buffer calls (the export now invokes this
    # builder once per model buffer, in the engine's add order)
    stats = report.setdefault("billboards",
                              {"anchors": 0, "canopies": 0, "bushes": 0,
                               "quads": 0, "unplaced": 0})
    for e in (room.sub_objects if anchors is None else anchors):
        cluster = BILLBOARD_TYPES.get(e.get("w"))
        if cluster is None:
            stats["unplaced"] += 1
            continue
        ax, ay, az = e["x"], e["y"], e["z"]
        pos, nrm, uv, idx = [], [], [], []
        for (py, rad, ang_deg, hw, hh) in cluster["quads"]:
            th = math.radians(ang_deg)
            s, c = math.sin(th), math.cos(th)
            # ENGINE SIZE (v9, corrected): hw/hh are FULL Q8 world units.
            # RotTransPers returns SZ3>>2 (libgte smp_02.o disassembly), so
            # Gfx_BillboardDraw's `temp_a0 = ret << 2` IS the raw GTE depth
            # (Q8 world units; the mesh path stores the identical raw depth
            # via gte_stsz3 and clips it against the same
            # `MIN(0x79C << (otShift+2), fog.farDistance)`), and
            # halfW_px = Q12_MULT(field_6, Q12(H)/temp_a0) = field_6*H/z.
            # The GTE projects a world offset dx at depth z to H*dx/z pixels,
            # so the world half-width is field_6 Q8 units as-is (no /4).
            # Ring offsets (radius / positionY) are Q8 units applied directly.
            # source-space ring position and tangent (angle around Y axis):
            # func_8005B55C computes position = (field_2*sin(angle),
            # positionY, field_2*cos(angle)) relative to the anchor.
            cx, cy, cz = ax + rad * s, ay + py, az + rad * c
            tx, tz = c, -s                       # ring tangent (source XZ)
            # diamond corners in SOURCE coords (Y down), engine-literal: the
            # screen-space diamond setXY4(x, y-2h, x+w, y-h, x-w, y-h, x, y)
            # with a level camera = bottom vertex AT the ring position, apex
            # 2*hh straight up (source -Y), side vertices +-hw along the
            # tangent at hh above the bottom vertex.
            corners = [
                (cx,           cy - 2 * hh, cz),            # top apex
                (cx + hw * tx, cy - hh,     cz + hw * tz),  # right side
                (cx - hw * tx, cy - hh,     cz - hw * tz),  # left side
                (cx,           cy,           cz),            # bottom (ring pos)
            ]
            uvs = [(0, 0), (63, 0), (0, 63), (63, 63)]   # engine window u[0,63]
            # v[128,191] of the BG_ETC sheet, mapped to the 64x64 window as
            # v-128 (corner order & assignment exactly as the decomp writes
            # them: top=(0,128), right=(63,128), left=(0,191),
            # bottom=(63,191))
            # STATIC-EXPORT ORIENTATION (the only forced deviation, minimal):
            # the engine rotates every diamond to face the camera
            # (screen-aligned); a static glTF cannot track a viewer, so the
            # ONE exported quad per engine diamond is oriented with its
            # horizontal axis along the RING TANGENT (normal = radial
            # direction = -D_800AE204.field_C, the engine's own computed
            # per-slot normal).  NO duplicated/rotated copies are added (the
            # v8 crossed-quad pair was an added artifact, removed in v9);
            # the engine draws both windings (PSX has no backface culling)
            # -> doubleSided material.
            gn = np.array([s, 0.0, c])             # radial outward (source)
            gn = np.array([gn[0], -gn[1], -gn[2]])  # -> glTF axes
            base = len(pos)
            for (sx_, sy_, sz_), (uu, vv) in zip(corners, uvs):
                gp = np.array([(sx_ + mx) * SCALE, -sy_ * SCALE,
                               -(sz_ + mz) * SCALE], dtype=np.float64)
                pos.append(tuple(gp))
                nrm.append((float(gn[0]), float(gn[1]), float(gn[2])))
                uv.append((uu / LEAF_TEXTURE_W, vv / LEAF_TEXTURE_H))
            # EMISSION (v11, engine-verbatim GT4 pair): the engine's setXY4
            # (billboard_draw.c:285-289) writes the corners in the order
            # (top, right, left, bottom) and the GPU draws the GT4 as
            # (top,right,left)+(right,bottom,left) — the shared edge is
            # right-left (the diamond's horizontal diagonal).  The pair is
            # emitted in EXACTLY that order so the consumer's reconstruction
            # pattern (idx[k+3]==idx[k+1] && idx[k+5]==idx[k+2]) rebuilds the
            # quad (MASK items are never nclip-culled — Gfx_BillboardDraw has
            # no cull — and their OT bucket is the ANCHOR-center depth,
            # reproduced from the four corners' mean).
            idx.extend([base + 0, base + 1, base + 2,
                        base + 1, base + 3, base + 2])
            stats["quads"] += 1          # exactly the engine's quad count
        if not idx:
            continue
        prim = {
            "attributes": {
                "POSITION": builder.add_positions(pos),
                "NORMAL": builder.add_normals(nrm),
                "TEXCOORD_0": builder.add_uvs(uv),
            },
            "indices": builder.add_indices(idx),
            "material": mat_idx,
            "mode": 4,
        }
        tname = "TREE_CANOPY" if e["w"] == 0 else "TREE_BUSH"
        mesh_indices.append(builder.add_mesh(
            f"{tname}_g{e['group']}i{e['index']}", [prim]))
        stats["anchors"] += 1
        stats["canopies" if e["w"] == 0 else "bushes"] += 1
        stats["static_orientation"] = (
            "single tangential quad per engine diamond (the engine draws "
            "every diamond camera-aligned; the static export freezes each "
            "diamond at its ring slot facing radially outward - "
            "-D_800AE204.field_C - with NO added geometry)")
        stats["diamond_sizes"] = (
            "full Q8: half-width field_6, half-height field_8 (largest "
            "canopy diamond 4.23 x 3.02 m) - v9 correction of the v8 /4 "
            "misreading, per the libgte RotTransPers disassembly")
    report["billboards"] = stats
    return mesh_indices


# ---------------------------------------------------------------------------
# glTF 2.0 / GLB writer
# ---------------------------------------------------------------------------
class GltfBuilder:
    """Hand-rolled glTF 2.0 writer with full control over accessors and embedding."""

    def __init__(self):
        self.bin = bytearray()
        self.json = {"asset": {"version": "2.0",
                               "generator": "ipd2gltf v11 (Silent Hill 1 IPD converter, decomp-verified emission contract)"},
                     "scene": 0,
                     "scenes": [{"name": "room", "nodes": []}],
                     "nodes": [], "meshes": [], "materials": [],
                     "textures": [], "images": [], "samplers": [], "accessors": [],
                     "bufferViews": [], "buffers": []}
        self.extensions_used = set()
        self._material_keys = {}
        self._image_hashes = {}
        self.stats = {"meshes": 0, "primitives": 0}

    # ---- binary plumbing ----
    def _pad(self):
        while len(self.bin) % 4:
            self.bin.append(0)

    def _add_view(self, blob, name=None):
        self._pad()
        off = len(self.bin)
        self.bin.extend(blob)
        self.json["bufferViews"].append(
            {"buffer": 0, "byteOffset": off, "byteLength": len(blob)})
        if name:
            self.json["bufferViews"][-1]["name"] = name
        return len(self.json["bufferViews"]) - 1

    def _accessor(self, arr, ctype, atype, count, minv=None, maxv=None, name=None):
        arr = np.ascontiguousarray(arr)
        view = self._add_view(arr.tobytes())
        acc = {"bufferView": view, "componentType": ctype, "count": count, "type": atype}
        if minv is not None:
            acc["min"] = [float(x) for x in minv]
            acc["max"] = [float(x) for x in maxv]
        if name:
            acc["name"] = name
        self.json["accessors"].append(acc)
        return len(self.json["accessors"]) - 1

    def add_positions(self, positions):
        p = np.asarray(positions, dtype="<f4")
        if p.ndim != 2 or p.shape[1] != 3 or p.shape[0] == 0:
            raise ValueError("bad position array")
        return self._accessor(p, 5126, "VEC3", p.shape[0],
                              p.min(axis=0).tolist(), p.max(axis=0).tolist())

    def add_normals(self, normals):
        n = np.asarray(normals, dtype="<f4")
        m = np.linalg.norm(n.astype(np.float64), axis=1)
        if np.any(m < 1e-6):
            raise ValueError("zero-length normal in accessor")
        return self._accessor(n, 5126, "VEC3", n.shape[0])

    def add_uvs(self, uvs):
        u = np.asarray(uvs, dtype="<f4")
        return self._accessor(u, 5126, "VEC2", u.shape[0])

    def add_indices(self, indices):
        i = np.asarray(indices, dtype="<u2")
        if i.max(initial=0) >= 65536:
            raise ValueError("index overflow for UNSIGNED_SHORT")
        return self._accessor(i, 5123, "SCALAR", i.shape[0])

    def add_image(self, png_bytes, name):
        h = hashlib.sha1(png_bytes).hexdigest()
        if h in self._image_hashes:
            return self._image_hashes[h]
        view = self._add_view(png_bytes, name)
        self.json["images"].append({"bufferView": view, "mimeType": "image/png",
                                    "name": name})
        idx = len(self.json["images"]) - 1
        self._image_hashes[h] = idx
        return idx

    def add_texture(self, image_idx):
        self.json["samplers"].append({"magFilter": 9729, "minFilter": 9729,
                                      "wrapS": 10497, "wrapT": 10497})
        sidx = len(self.json["samplers"]) - 1
        self.json["textures"].append({"sampler": sidx, "source": image_idx})
        return len(self.json["textures"]) - 1

    def add_material(self, key, name, tex_idx=None, has_alpha=False,
                     base_color=(0.5, 0.5, 0.5, 1.0), double_sided=False,
                     alpha_mode=None, alpha_cutoff=None, extras=None):
        if key in self._material_keys:
            return self._material_keys[key]
        mat = {"name": name,
               "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0},
               "extensions": {"KHR_materials_unlit": {}}}
        if tex_idx is not None:
            mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": tex_idx}
        else:
            mat["pbrMetallicRoughness"]["baseColorFactor"] = list(base_color)
        if alpha_mode:
            mat["alphaMode"] = alpha_mode
        elif has_alpha:
            mat["alphaMode"] = "BLEND"
        if alpha_cutoff is not None:
            mat["alphaCutoff"] = alpha_cutoff
        if double_sided:
            mat["doubleSided"] = True
        if extras is not None:
            mat["extras"] = extras
        self.json["materials"].append(mat)
        self.extensions_used.add("KHR_materials_unlit")
        idx = len(self.json["materials"]) - 1
        self._material_keys[key] = idx
        return idx

    def add_mesh(self, name, primitives):
        self.json["meshes"].append({"name": name, "primitives": primitives})
        self.stats["meshes"] += 1
        self.stats["primitives"] += len(primitives)
        return len(self.json["meshes"]) - 1

    def add_node(self, name, mesh_idx=None, children=None, root=True,
                 extras=None):
        node = {"name": name}
        if mesh_idx is not None:
            node["mesh"] = mesh_idx
        if children:
            node["children"] = list(children)
        if extras:
            # glTF 2.0 core "extras": application-specific data. We emit the
            # engine's per-model ORDERING-TABLE SECTION BASE (func_80057090 ->
            # func_800571D0 applied to the PLM s_ModelHeader field_B_1) so a
            # GLTF-native consumer can reproduce the engine's 6-band OT
            # layer architecture for ANY room without a hardcoded per-room
            # model-name table (the THRF9FD-only IPD_MODEL_LAYERS survey in
            # fog_poc.c misses every other room's models and flattens them
            # all to the default base 2 - the poster flicker on HP0003).
            # Attached to BOTH the per-instance parent node and each _mN
            # mesh child: a consumer walking nodes reads it exactly where it
            # computes the draw item's OT base. Billboard nodes carry
            # ot_base 0 (Gfx_BillboardDraw adds at org[z>>otShift] with NO
            # section base).
            node["extras"] = extras
        self.json["nodes"].append(node)
        idx = len(self.json["nodes"]) - 1
        if root:
            self.json["scenes"][0]["nodes"].append(idx)
        return idx

    def write_glb(self, path):
        self.json["extensionsUsed"] = sorted(self.extensions_used)
        self._pad()                       # pad BIN first, then record exact length
        self.json["buffers"].append({"byteLength": len(self.bin)})
        js = json.dumps(self.json, separators=(",", ":"), ensure_ascii=False)
        jb = js.encode("utf-8")
        padj = (4 - len(jb) % 4) % 4
        jb += b" " * padj
        self._pad()
        total = 12 + 8 + len(jb) + (8 + len(self.bin) if self.bin else 0)
        out = struct.pack("<III", GLTF_MAGIC, 2, total)
        out += struct.pack("<II", len(jb), CHUNK_JSON) + jb
        if self.bin:
            out += struct.pack("<II", len(self.bin), CHUNK_BIN) + bytes(self.bin)
        with open(path, "wb") as f:
            f.write(out)
        return total


# ---------------------------------------------------------------------------
# room export: geometry construction
# ---------------------------------------------------------------------------
def transform_instance(inst, room):
    """Return (R 3x3 float, t 3-vector float, map offset) for an instance."""
    R = np.array(inst.rt, dtype=np.float64).reshape(3, 3) / 4096.0
    t = np.array(inst.t, dtype=np.float64)
    m = np.array([MAP_CELL * room.x_pos, 0.0, MAP_CELL * room.y_pos],
                 dtype=np.float64)
    return R, t, m


# =====================================================================
# v12: OT LAYER SEPARATION — the z-buffer layering contract
# =====================================================================
#
# ENGINE EVIDENCE (every line read against the decomp + consumer):
#   * Gfx_MeshDraw (bodyprog_80056D8C.c:705-717, 854-873): per-quad OTZ =
#     MAX of the 4 vertex SZs; addPrim(&tag[(OTZ >> otShift) >> 2]) with
#     tag = &ot->org[sectionBase] — the mesh bucket is (Q8 >> 1) >> 2 =
#     Q8 >> 3 = 32 buckets per METRE (bucket width 31.25 mm).
#   * func_80057090 -> func_800571D0 (bodyprog_80056D8C.c:126-187): the
#     per-object OT SECTION BASE from s_ModelHeader field_B_1:
#     0->2 1->0 2->4 3->33 4->66 5->99.
#   * The OT is drawn FAR bucket -> NEAR bucket (DrawOTag walks from
#     org[2047]); addPrim is a HEAD insertion (libgpu.h:247), so on a
#     bucket tie the LAST-added draws FIRST — the FIRST-added lands on
#     top (fog_poc.c:6727-6745, the consumer's own engine-truth note).
#   => engine winner of any coincident pair = min(ot_base, engine add
#     order), and same-band surfaces less than 31.25 mm apart ride ADD
#     ORDER on hardware, not depth.
#
# MEASURED on the provided rooms (zcensus, this delivery):
#   HP0003: 78 same-facing plane-coincident OVERLAPPING pairs — 68 exact
#     ties at 0.00 mm (whole walls of NULL_NEA/HP1F012 over
#     NULL_BAC|BM18_BAC/HP1F011) + 10 at EXACTLY one PS1 unit (3.90625 mm)
#     with the engine winner FARTHER (e.g. OBJ1 furniture 1 unit behind
#     BM8_BACK backdrop, painted on top by band order on hardware).
#   THRF9FD: 288 pairs (269 exact ties, 8 engine-inverted, 19.19 m2 of
#     fighting surface).  Billboards: 0 pairs in every provided room.
#   Source-verified: every GLB quad's position multiset exists verbatim
#   in the raw IPD — the coincidence is AUTHORED, not an export artifact.
#
# THE PASS (no hacks, no per-room data, driven by the room's own engine
# fields):  units = (instance, mesh, plane-group); the plane-group unites
# every coplanar (<=0.2 mm) same-facing pack of one mesh so a surface
# moves as a whole (no internal steps).  For every overlapping pair the
# engine priority (ot_base, add order) picks the winner W and emits
#     off[loser] <= off[winner] - gap - LAYER_EPS
# (gap = how far the loser sits IN FRONT of the winner; 0 for exact
# ties).  Solved over the priority DAG (units sorted by (base, seq)):
# winners keep 0, losers recede.  Result: in ANY z-buffered renderer the
# engine's winner is nearest everywhere the pair overlaps, everywhere —
# exactly the hardware composite; in the fog_poc consumer the OT walk is
# unchanged (offsets only reinforce the same winners).

LAYER_EPS_FULL    = 0.01171875  # v13c: THREE PS1 UNITS (11.71875 mm) for
                                # MACRO overlaps (>= 50 cm2 AND >= 30 mm
                                # wide): the poster/wall skin class.  Ties
                                # only beyond 140 m (near=0.1) / 99 m
                                # (near=0.05, the wallpaper app's own
                                # camera) / 44 m (near=0.01) — outside any
                                # wallpaper camera.  (One full OT bucket
                                # 31.25 mm was tested first: ties beyond
                                # 229 m, but the 31 mm seam ledges between
                                # authored-coplanar wall bands were VLM-
                                # visible at close range; 3 PS1 units keep
                                # the guarantee for every realistic camera
                                # while cutting the ledges 2.7x.)
LAYER_EPS_UNIT    = 0.00390625  # v13b: ONE PS1 UNIT (3.90625 mm — the exact
                                # quantum the room data itself uses for its
                                # authored micro-offsets) for MICRO seam
                                # slivers (< 50 cm2 or < 30 mm wide): sub-
                                # pixel at any distance where ties occur
                                # (81 m at near=0.1, 26 m at near=0.01).
                                # Also caps chained recession (v13's flat
                                # bucket sank 4mm-seam-chained curbs 281 mm).
LAYER_MACRO_AREA  = 0.005    # m2 — 50 cm2 macro threshold
LAYER_MACRO_SIDE  = 0.030    # 30 mm minimum intersection width
LAYER_EPS         = LAYER_EPS_FULL  # backward-compat alias (validator text)
                                # engine's own depth granularity.  v12 used
                                # 1 mm, which a 24-bit depth buffer cannot
                                # resolve beyond ~41 m (near=0.1) / ~13 m
                                # (near=0.01): the tied pixels then resolve
                                # by DRAW ORDER, so the composite flips per
                                # pixel while the camera moves — the measured
                                # poster flicker.  One bucket of separation
                                # ties only beyond 229 m (near=0.1) / 72 m
                                # (near=0.01) — outside any wallpaper camera.
LAYER_TIE_EPS     = 0.0002   # 0.2 mm — "coplanar within float noise"
LAYER_MAX_SEP     = 0.032    # 32 mm — the census pair window (= bucket width)
LAYER_WATCH_SEP   = 0.300    # v13: watch window — parallel overlapping pairs
                                # up to 300 mm apart must never be compressed
                                # below one bucket by a census loser receding
LAYER_FACING_DOT  = 0.99     # same-facing test for interacting pairs
LAYER_UNIT_DOT    = 0.999    # stricter facing test inside one unit
LAYER_OVERLAP_MIN = 1e-9     # m2 — corner/edge-touching shares no pixels
LAYER_MAX_RECEDE  = 0.350    # loud-report cap (350 mm; chains can stack)


def _layer_quad_records(room):
    """All instance pack quads in ENGINE ADD ORDER with their ot_base.

    Mirrors build_instance_meshes' transform math verbatim (R/t/m, the
    y/z axis flip, SCALE).  Corner order = the consumer's quad order
    (f0, f2, f1, v3) so the winding normal faces the void (glTF front).
    """
    recs = []
    for inst_idx, inst in enumerate(room.instances):
        lib = inst.resolved_lib if inst.resolved_lib is not None else (
            room.plm if inst.source == "ipd" else room.glb)
        if lib is None:
            continue
        obj = lib.objects.get(inst.lookup_name)
        if obj is None:
            continue
        R, t, m = transform_instance(inst, room)
        for mi, mesh in enumerate(obj.meshes):
            for pi, pack in enumerate(mesh.packs):
                f0, f1, f2, f3 = pack.faces
                if max(f0, f1, f2) >= len(mesh.verts):
                    continue                       # emission drops it too
                v3 = f2 if f3 == 0xFF else f3
                if v3 >= len(mesh.verts):
                    continue
                w = []
                for vi in (f0, f2, f1, v3):
                    wp = R.dot(np.array(mesh.verts[vi],
                                        dtype=np.float64)) + t + m
                    w.append(np.array([wp[0] * SCALE, -wp[1] * SCALE,
                                       -wp[2] * SCALE]))
                a, b, c = w[0], w[1], w[2]
                n = np.cross(b - a, c - a)
                nl = float(np.linalg.norm(n))
                if nl < 1e-9:
                    continue                       # renders nothing
                recs.append({"inst": inst_idx, "mesh": mi, "pack": pi,
                             "obj": inst.obj_name, "base": obj.ot_base,
                             "seq": len(recs), "w": w, "n": n / nl})
    return recs


def _layer_hull2(pts):
    """Convex hull of 2D points (monotone chain)."""
    pts = sorted(set((float(p[0]), float(p[1])) for p in pts))
    if len(pts) < 3:
        return pts
    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _layer_clip_poly(ha, hb):
    """Intersection polygon of two convex polygons (Sutherland-Hodgman).
    Returns [] if empty.  Exact, no shapely dependency."""
    return _layer_clip_area(ha, hb, want_poly=True)


def _layer_clip_area(ha, hb, want_poly=False):
    """Area of the intersection of two convex polygons (Sutherland-
    Hodgman).  No shapely dependency: exact, allocation-light."""
    if len(ha) < 3 or len(hb) < 3:
        return ([], 0.0) if want_poly else 0.0
    # orient the clip polygon's edge normals toward its interior:
    # for a CCW polygon (positive signed area) the interior lies LEFT of
    # every directed edge -> left normal (-dy, dx); CW polygons flip it.
    sarea = 0.0
    for i in range(len(hb)):
        x1, y1 = hb[i]
        x2, y2 = hb[(i + 1) % len(hb)]
        sarea += x1 * y2 - x2 * y1
    sgn = 1.0 if sarea >= 0.0 else -1.0
    poly = list(ha)
    for k in range(len(hb)):
        if len(poly) < 3:
            return ([], 0.0) if want_poly else 0.0
        ax, ay = hb[k]
        bx, by = hb[(k + 1) % len(hb)]
        nx, ny = -sgn * (by - ay), sgn * (bx - ax)
        out, inside = [], []
        for px, py in poly:
            d = nx * (px - ax) + ny * (py - ay)
            (inside if d >= 0 else out).append((px, py, d))
        if not inside:
            return ([], 0.0) if want_poly else 0.0
        if not out:
            continue
        res = []
        for i in range(len(poly)):
            px, py = poly[i]
            d = nx * (px - ax) + ny * (py - ay)
            qx, qy = poly[(i + 1) % len(poly)]
            dq = nx * (qx - ax) + ny * (qy - ay)
            if d >= 0:
                res.append((px, py))
            if (d >= 0) != (dq >= 0):
                t = d / (d - dq)
                res.append((px + t * (qx - px), py + t * (qy - py)))
        poly = res
    if len(poly) < 3:
        return ([], 0.0) if want_poly else 0.0
    area = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    if want_poly:
        return poly, abs(area) * 0.5
    return abs(area) * 0.5


def _layer_plane_basis(n):
    tmp = [abs(float(n[0])), abs(float(n[1])), abs(float(n[2]))]
    axis = tmp.index(min(tmp))
    e1 = np.array([0.0 if t == axis else 1.0 for t in range(3)])
    e1 = e1 - n * float(np.dot(e1, n))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return e1, e2


def compute_layer_separation(room):
    """Return (offsets, report) — offsets maps
    (instance_index, mesh_idx, pack_idx) -> np.array glTF-world offset."""
    info = {"eps_mm": LAYER_EPS * 1000.0,
            "max_sep_mm": LAYER_MAX_SEP * 1000.0,
            "problems": [], "constraints": [], "unit_offsets": [],
            "billboards": ("excluded: leaf billboard rings have 0 "
                           "coincident-layer pairs in every provided room "
                           "(measured on the textured THRF9FD GLB); the "
                           "output validator re-checks every output")}
    recs = _layer_quad_records(room)
    info["quads_analyzed"] = len(recs)
    if len(recs) < 2:
        info["units"] = 0
        return {}, info

    # ---------- units: (instance, mesh) plane-groups (union-find) --------
    parent = list(range(len(recs)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    by_mesh = {}
    for r in recs:
        by_mesh.setdefault((r["inst"], r["mesh"]), []).append(r)
    for key, group in by_mesh.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ri, rj = group[i], group[j]
                if float(ri["n"].dot(rj["n"])) < LAYER_UNIT_DOT:
                    continue
                p0 = ri["w"][0]
                d = max(abs(float(ri["n"].dot(v - p0))) for v in rj["w"])
                if d <= LAYER_TIE_EPS:
                    union(ri["seq"], rj["seq"])
    units = {}
    for r in recs:
        units.setdefault(find(r["seq"]), []).append(r)
    # unit metadata: priority key (base, min seq); normal; plane origin
    unit_of = {}
    unit_meta = {}
    for uid, members in units.items():
        base = members[0]["base"]                 # one object -> one base
        minseq = min(r["seq"] for r in members)
        unit_meta[uid] = {"key": (base, minseq), "n": members[0]["n"],
                          "p0": members[0]["w"][0], "members": members,
                          "inst": members[0]["inst"],
                          "mesh": members[0]["mesh"],
                          "obj": members[0]["obj"]}
        for r in members:
            unit_of[r["seq"]] = uid
    # split units whose members overlap EACH OTHER (never observed; the
    # engine would resolve those by pack order — per-pack units do that)
    for uid, meta in list(unit_meta.items()):
        members = meta["members"]
        bad = False
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                ri, rj = members[i], members[j]
                if float(ri["n"].dot(rj["n"])) < LAYER_FACING_DOT:
                    continue
                e1, e2 = _layer_plane_basis(ri["n"])
                Pi = _layer_hull2([(float(np.dot(e1, p)), float(np.dot(e2, p)))
                                   for p in ri["w"]])
                Pj = _layer_hull2([(float(np.dot(e1, p)), float(np.dot(e2, p)))
                                   for p in rj["w"]])
                if _layer_clip_area(Pi, Pj) > LAYER_OVERLAP_MIN:
                    bad = True
                    break
            if bad:
                break
        if bad:
            info["problems"].append(
                f"unit {meta['obj']} mesh {meta['mesh']}: internal "
                f"overlapping packs — split to per-pack units (engine pack "
                f"order resolves these; never observed in provided data)")
            for r in members:
                uid2 = ("pack", r["seq"])
                unit_of[r["seq"]] = uid2
                unit_meta[uid2] = {"key": (r["base"], r["seq"]),
                                   "n": r["n"], "p0": r["w"][0],
                                   "members": [r], "inst": r["inst"],
                                   "mesh": r["mesh"], "obj": r["obj"]}
            del unit_meta[uid]

    # ---------- candidate pairs (spatial grid on AABBs) ------------------
    # v13b: the census runs on EFFECTIVE geometry (authored + current
    # offsets).  Offsets are applied along each unit's OWN normal, so two
    # differently-tilted units shift IN-PLANE relative to each other and
    # can CREATE new overlaps that the authored geometry did not have
    # (measured: THR7203 branch panels, 5 cm2 sliver born from a zero-area
    # edge touch).  The driver loop below re-censuses after each solve
    # until no pair violates its margin (max 3 rounds).
    CELL = 0.5

    def _census(recs_eff):
        """Pair census on the given effective records.

        Returns (constraints, watch, n_pairs, n_macro, n_cross).
        constraints: (wu, lu, gap, area, wn, ls, margin)
        watch:       (fu, bu, gap, margin)
        """
        for r in recs_eff:
            Wp = np.array(r["w"])
            r["bb0"] = Wp.min(axis=0)
            r["bb1"] = Wp.max(axis=0)
        grid = {}
        for r in recs_eff:
            lo = np.floor((r["bb0"] - LAYER_WATCH_SEP) / CELL).astype(int)
            hi = np.floor((r["bb1"] + LAYER_WATCH_SEP) / CELL).astype(int)
            for cx in range(lo[0], hi[0] + 1):
                for cy in range(lo[1], hi[1] + 1):
                    for cz in range(lo[2], hi[2] + 1):
                        grid.setdefault((cx, cy, cz), []).append(r["seq"])
        seen = set()
        cons, wat = [], []
        n_pairs = n_macro = n_cross = 0
        for cell in grid.values():
            for ii in range(len(cell)):
                for jj in range(ii + 1, len(cell)):
                    si, sj = cell[ii], cell[jj]
                    if si > sj:
                        si, sj = sj, si
                    if (si, sj) in seen:
                        continue
                    seen.add((si, sj))
                    ri, rj = recs_eff[si], recs_eff[sj]
                    ui, uj = unit_of[si], unit_of[sj]
                    if ui == uj:
                        continue               # same unit: moves as one
                    if np.any(ri["bb0"] > rj["bb1"] + LAYER_WATCH_SEP) or \
                       np.any(rj["bb0"] > ri["bb1"] + LAYER_WATCH_SEP):
                        continue
                    if float(ri["n"].dot(rj["n"])) < LAYER_FACING_DOT:
                        continue
                    n0, p0 = ri["n"], ri["w"][0]
                    d1 = max(abs(float(n0.dot(v - p0))) for v in rj["w"])
                    n1, p1 = rj["n"], rj["w"][0]
                    d2 = max(abs(float(n1.dot(v - p1))) for v in ri["w"])
                    sep = max(d1, d2)
                    if sep > LAYER_WATCH_SEP:
                        continue
                    ka, kb = (ri["base"], ri["seq"]), (rj["base"], rj["seq"])
                    wn, ls = (ri, rj) if ka <= kb else (rj, ri)
                    un = unit_of[wn["seq"]]
                    um = unit_meta[un]
                    sdist = [float(um["n"].dot(v - um["p0"]))
                             for v in ls["w"]]
                    ulm = unit_meta[unit_of[ls["seq"]]]
                    sdist_r = [float(ulm["n"].dot(v - ulm["p0"]))
                               for v in wn["w"]]
                    # CROSSING surfaces: EITHER quad's corners straddle the
                    # other's plane (e.g. branch panels at ~1 deg whose
                    # planes pass through each other).  Not layers — every
                    # z-buffer resolves them per-pixel on each side of the
                    # intersection line; separating them is meaningless.
                    if ((min(sdist) < -LAYER_TIE_EPS and
                         max(sdist) > LAYER_TIE_EPS) or
                        (min(sdist_r) < -LAYER_TIE_EPS and
                         max(sdist_r) > LAYER_TIE_EPS)):
                        n_cross += 1
                        continue
                    gap = max(sdist)
                    # 2D overlap in the (near-)shared plane
                    e1, e2 = _layer_plane_basis(ri["n"])
                    Pi = _layer_hull2([(float(np.dot(e1, p)), float(np.dot(e2, p)))
                                       for p in ri["w"]])
                    Pj = _layer_hull2([(float(np.dot(e1, p)), float(np.dot(e2, p)))
                                       for p in rj["w"]])
                    ipoly, area = _layer_clip_area(Pi, Pj, want_poly=True)
                    if area <= LAYER_OVERLAP_MIN:
                        continue
                    if ipoly:
                        xs = [p[0] for p in ipoly]
                        ys = [p[1] for p in ipoly]
                        min_side = min(max(xs) - min(xs), max(ys) - min(ys))
                    else:
                        min_side = 0.0
                    if area >= LAYER_MACRO_AREA and min_side >= LAYER_MACRO_SIDE:
                        m_pair, is_macro = LAYER_EPS_FULL, True
                    else:
                        m_pair, is_macro = LAYER_EPS_UNIT, False
                    if sep <= LAYER_MAX_SEP:
                        n_pairs += 1
                        if is_macro:
                            n_macro += 1
                        cons.append((un, unit_of[ls["seq"]], gap, area,
                                     wn, ls, m_pair))
                    else:
                        lu_uid = unit_of[ls["seq"]]
                        fi, bi = (un, lu_uid) if gap <= 0 else (lu_uid, un)
                        g = abs(gap)
                        if g > LAYER_MAX_SEP:
                            wat.append((fi, bi, g, m_pair))
        return cons, wat, n_pairs, n_macro, n_cross

    def _solve(constraints, watch):
        """Total offsets: winners 0, losers recede (priority DAG), watch
        caps — C1 uses each pair's own margin."""
        order = sorted(unit_meta.keys(),
                       key=lambda u: (unit_meta[u]["key"][0],
                                      unit_meta[u]["key"][1]))
        off = {u: 0.0 for u in unit_meta}
        beats = {}
        for wu, lu, gap, area, wn, ls, mp in constraints:
            beats.setdefault(wu, []).append((lu, gap, mp))
        for wu in order:
            for lu, gap, mp in beats.get(wu, ()):
                need = off[wu] - gap - mp
                if off[lu] > need:
                    off[lu] = need

        def _c1_propagate(u, queue):
            for lu, gap, mp in beats.get(u, ()):
                need = off[u] - gap - mp
                if off[lu] > need:
                    off[lu] = need
                    queue.append(lu)

        if watch:
            watch_by_front = {}
            for fu, bu, g, mp in watch:
                watch_by_front.setdefault(fu, []).append((bu, g, mp))
            queue, pushed = [], set()
            for fu, bu, g, mp in watch:
                cap = off[fu] - mp + g
                if off[bu] > cap + 1e-12:
                    off[bu] = cap
                    pushed.add(bu)
                    queue.append(bu)
            iters = 0
            while queue and iters < 100000:
                iters += 1
                u = queue.pop()
                _c1_propagate(u, queue)
                for bu, g, mp in watch_by_front.get(u, ()):
                    cap = off[u] - mp + g
                    if off[bu] > cap + 1e-12:
                        off[bu] = cap
                        pushed.add(bu)
                        queue.append(bu)
            if queue:
                info["problems"].append(
                    "layer watch solver did not converge (100000 iters)")
        return off

    def _effective(off):
        """recs with each unit's total offset applied along its normal."""
        out = []
        for r in recs:
            uid = unit_of[r["seq"]]
            o = off.get(uid, 0.0)
            if o == 0.0:
                out.append(r)
            else:
                n = unit_meta[uid]["n"]
                out.append(dict(r, w=[v + n * o for v in r["w"]]))
        return out

    # driver: census -> solve -> re-census until stable (max 3 rounds).
    # Round k's census runs on the offsets from round k-1, so pairs CREATED
    # by in-plane shift (differently-tilted normals) enter the constraint
    # set and are solved in the next round.
    off = {u: 0.0 for u in unit_meta}
    constraints, watch = [], []
    n_pairs = n_macro = n_cross = 0
    info["iterations"] = 0
    for it in range(3):
        eff = _effective(off)
        cons_new, wat_new, n_pairs, n_macro, n_cross = _census(eff)
        # freeze each pair's MARGIN at its FIRST classification (the
        # authored geometry is the ground truth; exact-coplanar macro
        # pairs have zero in-plane drift, and tilted micro pairs must not
        # escalate to macro just because offsets shifted them in-plane),
        # but keep the LATEST gap measurement (geometry changed).
        by_pair = {(c[0], c[1]): c for c in constraints}
        for c in cons_new:
            key = (c[0], c[1])
            if key in by_pair:
                old_c = by_pair[key]
                by_pair[key] = (c[0], c[1], c[2], c[3], c[4], c[5],
                                old_c[6])
            else:
                by_pair[key] = c
        constraints = list(by_pair.values())
        wby = {(w[0], w[1]): w for w in watch}
        for w in wat_new:
            wby[(w[0], w[1])] = w
        watch = list(wby.values())
        off = _solve(constraints, watch)
        info["iterations"] = it + 1
        # verify: re-census on the solved geometry; every census pair's
        # measured gap must be at least its margin behind the winner
        cons_chk, _, _, _, _ = _census(_effective(off))
        bad = sum(1 for c in cons_chk if c[2] > -(c[6] - 0.0015))
        if bad == 0:
            break
        if it == 2:
            info["problems"].append(
                f"layer separation did not converge in 3 rounds "
                f"({bad} pairs still violating after the last solve)")
    info["pairs"] = n_pairs
    info["macro_pairs"] = n_macro
    info["micro_pairs"] = n_pairs - n_macro
    info["crossing_pairs_skipped"] = n_cross
    info["watch_pairs"] = len(watch)

    # ---------- per-pack offsets + report --------------------------------
    offsets = {}
    for uid, meta in unit_meta.items():
        o = off[uid]
        if abs(o) < 1e-12:
            continue
        if o < -LAYER_MAX_RECEDE:
            info["problems"].append(
                f"unit {meta['obj']} mesh {meta['mesh']} recedes "
                f"{-o * 1000.0:.1f} mm (> {LAYER_MAX_RECEDE * 1000.0:.0f} mm "
                f"cap) — reviewed against the authored gaps, reported loudly")
        vec = meta["n"] * o
        for r in meta["members"]:
            offsets[(r["inst"], r["mesh"], r["pack"])] = vec
        info["unit_offsets"].append({
            "object": meta["obj"], "mesh": meta["mesh"],
            "inst": meta["inst"], "ot_base": meta["key"][0],
            "offset_mm": round(o * 1000.0, 3),
            "quads": len(meta["members"])})
    for wu, lu, gap, area, wn, ls, mp in constraints:
        info["constraints"].append({
            "margin_mm": round(mp * 1000.0, 3),
            "winner": f"{unit_meta[wu]['obj']}#{unit_meta[wu]['inst']}"
                      f"/m{unit_meta[wu]['mesh']}(ot{unit_meta[wu]['key'][0]})",
            "loser": f"{unit_meta[lu]['obj']}#{unit_meta[lu]['inst']}"
                     f"/m{unit_meta[lu]['mesh']}(ot{unit_meta[lu]['key'][0]})",
            "overlap_m2": round(area, 6),
            "loser_in_front_mm": round(gap * 1000.0, 3)})
    info["units"] = len(unit_meta)
    info["units_offset"] = len(info["unit_offsets"])
    info["max_recede_mm"] = (round(min(off.values()) * 1000.0, 3)
                             if off else 0.0)
    info["semantics"] = (
        "engine OT layering projected into depth-buffer geometry: winner "
        "by min(ot_base, add order) keeps offset 0; losers recede along "
        "the winner normal by a pair-classified margin (v13c): MACRO "
        "overlaps (>=50 cm2 and >=30 mm wide — the poster/wall-skin class) "
        "get THREE PS1 UNITS 11.71875 mm (ties beyond 140 m at near=0.1 / "
        "99 m at near=0.05); MICRO seam slivers get ONE PS1 UNIT "
        "3.90625 mm — the engine's own authored micro-offset quantum; "
        "v12's flat 1 mm flickered with draw order beyond 41 m (24-bit "
        "depth, near=0.1); units are (instance, mesh, plane-group); watch "
        "pairs (32-300 mm) are never compressed below their margin; no "
        "geometry dropped; emission contract untouched")
    return offsets, info


def build_instance_meshes(room, inst, lib, resolver, builder, report,
                          layer_offsets=None, inst_key=None,
                          out_mesh_pack_offsets=None):
    """Convert one object instance into glTF meshes (one per PLM mesh).

    out_mesh_pack_offsets (optional dict) receives, per PLM mesh index mi,
    the FLAT per-quad offset list in consumer walk order ([x,y,z] or None
    per reconstructed quad) — the engine-exact consumer subtracts these
    from the bucket depth (see extras.layer_offsets)."""
    obj = lib.objects.get(inst.lookup_name)
    if obj is None:
        report["problems"].append(
            f"object {inst.obj_name!r} ({inst.effective_source}) not found in "
            f"{lib.source_name} - instance skipped")
        return []
    R, t, m = transform_instance(inst, room)
    mesh_indices = []
    for mi, mesh in enumerate(obj.meshes):
        prim_groups = {}     # material key -> {pos:[], nrm:[], uv:[], idx:[], qoff:[]}
        corner_cache = {}    # per material key: (pos,nrm,uv) tuple -> vertex index
        for pack_pi, pack in enumerate(mesh.packs):
            # ---- v12: this pack's OT-layer separation offset (if any) ----
            layer_off = None
            if layer_offsets is not None:
                layer_off = layer_offsets.get((inst_key, mi, pack_pi))
            # ---- material key ----
            if pack.tex_num == 0x7F:
                mat_key = ("NOTEX",)
                tex_w = tex_h = None
            elif pack.tex_num >= len(lib.tex_names):
                report["problems"].append(
                    f"{inst.obj_name} mesh{mi}: tex_num {pack.tex_num} >= "
                    f"{len(lib.tex_names)} - treated as untextured")
                mat_key = ("NOTEX",)
                tex_w = tex_h = None
            else:
                tex_name = lib.tex_names[pack.tex_num]
                mat_key = ("TEX", tex_name, pack.cba, pack.stp)
                tex_w = tex_h = None
                tim = report["tim_cache"].get(tex_name, False)
                if tim is False:
                    # directory-tree discovery + evidence-ranked resolution:
                    # every decision, duplicate location and problem is logged
                    # in the per-room report and the global resolution log
                    tim = resolver.load_tim(tex_name, room.name, report)
                    report["tim_cache"][tex_name] = tim
                if tim is not None:
                    report["tex_referenced"].add(tex_name)
                    try:
                        pal, pal_y = tim.palette(pack.cba)
                        variant = tim.decode(pal, pack.stp)
                        report["tex_variants"].setdefault(
                            (tex_name, pal_y, pack.stp), variant)
                    except Exception as e:
                        report["problems"].append(
                            f"{inst.obj_name} mesh{mi}: texture {tex_name}: {e}")
                        mat_key = ("MISSING", tex_name)
                    else:
                        tex_w, tex_h = tim.width, tim.height
                        report["tex_ok"].add(tex_name)
                else:
                    report["tex_missing"].add(tex_name)
                    mat_key = ("MISSING", tex_name)
            # ---- triangles of this pack ----
            # glTF winding is the REVERSE of the stored order (see module docstring):
            # PS1 front = winding left-hand side = void/player side.
            # Each corner keeps its ORIGINAL index so UV (pack.uv) and normal slot
            # (pack.normal_slots) stay bound to the correct vertex.
            f0, f1, f2, f3 = pack.faces
            # ---- v11 EMISSION CONTRACT (see module docstring) ---------------
            # The PS1 GT4 draws this pack as (v0,v1,v2)+(v1,v3,v2) — corners
            # in Z order, the shared edge v1-v2 the diagonal.  The glTF export
            # REVERSES the winding (glTF CCW front = the void side) but MUST
            # keep the pair reconstructable as ONE quad by the consumer's
            # pattern (fog_poc.c: idx[k+3]==idx[k+1] && idx[k+5]==idx[k+2]):
            #   tri1 = (v0, v2, v1)   — a cyclic rotation of the reversed
            #                            (v2,v1,v0): same CCW orientation,
            #                            idx[k+1]=v2, idx[k+2]=v1
            #   tri2 = (v2, v3, v1)   — the reversed second half, with
            #                            idx[k+3]=v2==idx[k+1] and
            #                            idx[k+5]=v1==idx[k+2]: PATTERN MATCH
            # The consumer then reconstructs vi=(v0,v2,v1,v3) — a permutation
            # of the four corners — and applies the ENGINE's per-quad OT
            # semantics (bucket = MAX of the four vertex depths, per-quad far
            # cull, dual-nclip cull).  v10's (v2,v1,v0)+(v2,v3,v1) could never
            # match the pattern (measured: 0.2% coverage) — the root cause of
            # the flat-surface flickering (per-triangle buckets + a per-
            # triangle cull with an undefined 4th vertex).
            # Degenerate packs (f3==0xFF or f3==f2): the second triangle is
            # STILL EMITTED with v3:=v2 — zero area, rasterizing to nothing
            # exactly like the GT4 on real hardware, keeping the pack a
            # reconstructable quad (the engine's second nclip is 0 for these
            # and the consumer's reconstructed cull reproduces exactly that).
            # f3==f1/f0 (never observed in any provided file): emitted with
            # the STORED index — the engine draws those as (v1,v3,v2) with
            # the repeated corner too; reported loudly below.
            tri_pack_drop = False
            if max(f0, f1, f2) >= len(mesh.verts):
                report["repairs"].append(
                    f"{inst.obj_name} mesh{mi}: face indices {pack.faces} exceed "
                    f"vert_num {len(mesh.verts)} - pack dropped")
                continue
            v3 = f2 if f3 == 0xFF else f3     # 0xFF marks a triangle (v3:=v2)
            if f3 == 0xFF or f3 == f2:
                report["repairs_degenerate_quads"] += 1
            elif f3 == f1 or f3 == f0:
                report["repairs"].append(
                    f"{inst.obj_name} mesh{mi}: quad faces {pack.faces} repeat "
                    f"corner {'f1' if f3 == f1 else 'f0'} in f3 (never observed "
                    f"in provided data) - emitted with the stored index, "
                    f"engine-verbatim (the GT4 draws it as-is)")
            if v3 >= len(mesh.verts):
                report["repairs"].append(
                    f"{inst.obj_name} mesh{mi}: quad 2nd tri indices OOB - dropped")
                tri_pack_drop = True
            tris = [
                [(f0, 0, 0), (f2, 2, 2), (f1, 1, 1)],        # tri1 (CCW)
            ]
            if not tri_pack_drop:
                tris.append([(f2, 2, 2), (v3, 3, 3), (f1, 1, 1)])  # tri2
            for t_i, tri in enumerate(tris):
                corner_data = []
                bad_normal = False
                for vi, ui, si in tri:
                    if vi >= len(mesh.verts):
                        bad_normal = True
                        break
                    slot = pack.normal_slots[si]
                    if slot >= len(mesh.slot_normal):
                        report["repairs"].append(
                            f"{inst.obj_name} mesh{mi}: normal slot {slot} >= "
                            f"{len(mesh.slot_normal)} - pack dropped")
                        bad_normal = True
                        break
                    g = mesh.slot_normal[slot]
                    n = mesh.normals_a[g]
                    lp = mesh.verts[vi]
                    # world transform (exact in float64), then glTF axis flip;
                    # normals are NEGATED (source normals point into the solid,
                    # PS1 renders the void side - see module docstring)
                    wp = R.dot(np.array(lp, dtype=np.float64)) + t + m
                    gp = np.array([wp[0], -wp[1], -wp[2]]) * SCALE
                    if layer_off is not None:
                        # v12 OT layer separation: recede this losing layer
                        # along the winning plane's normal (winners keep 0);
                        # the corner cache key uses the offset position, so
                        # offset and unoffset corners never share a vertex
                        gp = gp + layer_off
                    wn = -R.dot(np.array(n[:3], dtype=np.float64))
                    gn = np.array([wn[0], -wn[1], -wn[2]])
                    nl = np.linalg.norm(gn)
                    if nl < 1e-9:
                        # documented fallback: zero stored normal -> flat face normal
                        # (computed from the REVERSED winding so it faces the void)
                        report["repairs_zero_normals"] += 1
                        a, b, c = (np.array(mesh.verts[tri[0][0]], dtype=np.float64),
                                   np.array(mesh.verts[tri[1][0]], dtype=np.float64),
                                   np.array(mesh.verts[tri[2][0]], dtype=np.float64))
                        fn = R.dot(np.cross(b - a, c - a))
                        gn = np.array([fn[0], -fn[1], -fn[2]])
                        nl = np.linalg.norm(gn)
                        if nl < 1e-9:
                            bad_normal = True
                            break
                    gn = gn / nl
                    if tex_w:
                        uu, vv = pack.uv[ui]
                        guv = (uu / tex_w, vv / tex_h)
                    else:
                        guv = (0.0, 0.0)
                    corner_data.append((tuple(gp), tuple(gn), guv))
                if bad_normal or len(corner_data) != 3:
                    continue
                gk = mat_key
                grp = prim_groups.setdefault(gk, {"pos": [], "nrm": [], "uv": [],
                                                  "idx": [], "cache": {},
                                                  "qoff": []})
                cache = grp["cache"]
                ids = []
                for cd in corner_data:
                    key = (cd[0], cd[1], cd[2])
                    if key in cache:
                        ids.append(cache[key])
                    else:
                        grp["pos"].append(cd[0])
                        grp["nrm"].append(cd[1])
                        grp["uv"].append(cd[2])
                        cache[key] = len(grp["pos"]) - 1
                        ids.append(cache[key])
                grp["idx"].extend(ids)
                if t_i == 0:
                    # one entry per PACK (= one reconstructed quad of 6
                    # indices) — the consumer reads it at quad granularity
                    if layer_off is not None:
                        grp["qoff"].append([float(layer_off[0]),
                                            float(layer_off[1]),
                                            float(layer_off[2])])
                    else:
                        grp["qoff"].append(None)
        # ---- emit primitives ----
        prims = []
        for gk, grp in prim_groups.items():
            if not grp["idx"]:
                continue
            mat_idx = _material_for(builder, gk, report)
            prims.append({
                "attributes": {
                    "POSITION": builder.add_positions(grp["pos"]),
                    "NORMAL": builder.add_normals(grp["nrm"]),
                    "TEXCOORD_0": builder.add_uvs(grp["uv"]),
                },
                "indices": builder.add_indices(grp["idx"]),
                "material": mat_idx,
                "mode": 4,
            })
        if not prims:
            continue
        mesh_idx = builder.add_mesh(f"{inst.obj_name}_{mi}", prims)
        mesh_indices.append(mesh_idx)
        # flat per-quad offset list in CONSUMER WALK ORDER (prim order,
        # quad order within prim) — 2 entries per pack (its 2 triangles
        # reconstruct as 1 quad); nulls for unoffset packs
        qflat = []
        for gk2, grp2 in prim_groups.items():
            qflat.extend(grp2["qoff"])
        if any(o is not None for o in qflat):
            out_mesh_pack_offsets[len(mesh_indices) - 1] = qflat
    return mesh_indices


# Neutral placeholder color for untextured polys (packs with tex_num=0x7F).
# The in-game color of these polygons is supplied by the game engine at runtime
# (the IPD pack stores no color: the u/v/cba fields are ZERO for all 161
# untextured packs across the provided corpus, and no lighting data exists in
# the IPD).  This value is a documented neutral, NOT a claim about the game's
# appearance; override it with --untextured-color when the target look is known
# (e.g. dark foliage greens for THR outdoor rooms).
UNTEXTURED_COLOR = (0.5, 0.5, 0.5)


def _material_for(builder, gk, report):
    """Create/find the glTF material for a primitive group key."""
    if gk[0] == "NOTEX":
        name = "UNTEXTURED_GOURAUD"
        key = ("NOTEX",)
        if UNTEXTURED_COLOR != (0.5, 0.5, 0.5):
            # only annotate the name when overridden, so default runs keep
            # the exact material name audited in previous validation runs
            name = "UNTEXTURED_GOURAUD_" + "".join(
                f"{int(round(c * 255)):02X}" for c in UNTEXTURED_COLOR)
            key = ("NOTEX", name)
        return builder.add_material(key, name, tex_idx=None,
                                    base_color=(*UNTEXTURED_COLOR, 1.0))
    if gk[0] == "MISSING":
        name = f"MISSING_TEX_{gk[1]}"
        report["missing_material_faces"] = report.get("missing_material_faces", 0) + 1
        return builder.add_material(("MISSING", gk[1]), name, tex_idx=None,
                                    base_color=(0.5, 0.45, 0.45, 1.0))
    _tag, tex_name, cba, stp = gk
    pal_y = (cba & 0x7FC0) >> 6
    key = ("TEX", tex_name, pal_y, stp)
    # texture/sampler entries are created ONLY when a new material is created:
    # previously every primitive group added a texture even when the material
    # already existed, leaving orphaned glTF texture objects (47 textures for
    # 10 materials in APU0002).  Renders are unchanged; the JSON is lean.
    if key in builder._material_keys:
        return builder._material_keys[key]
    variant = report["tex_variants"][(tex_name, pal_y, stp)]
    has_alpha = bool((variant[..., 3] < 255).any())
    if not HAS_PIL:
        raise RuntimeError("Pillow required for texture embedding")
    img = Image.fromarray(variant)
    import io as _io
    buf = _io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    png = buf.getvalue()
    iname = f"{tex_name}_pal{pal_y}" + ("_stp" if stp else "")
    img_idx = builder.add_image(png, iname)
    tex_idx = builder.add_texture(img_idx)
    mname = f"{tex_name}_pal{pal_y}" + ("_STP" if stp else "")
    # v33 (S20): the DWAVE material — the engine redirects it to the LIVE
    # animated tile at every chunk load (WorldMap_ChunkPropertiesSet ->
    # func_8008E4EC matches materials by the name string, lens_flare.c:
    # 497-502 + map.c:1167-1186; the material table in the sewer IPDs
    # carries the name "DWAVE"). Consumers with a live-tile port render
    # the animated water floor; others keep the static art (no-op).
    extras = ({"SH1X": {"waterLive": True,
                        "src": "func_8008E4EC lens_flare.c:497-502 "
                               "+ WorldMap_ChunkPropertiesSet map.c:1181 "
                               "(the DWAVE material redirect to tpage 13)"}}
               if tex_name == "DWAVE" else None)
    return builder.add_material(key, mname, tex_idx=tex_idx,
                                has_alpha=has_alpha, extras=extras)


def _instance_marker_matrix(room, inst):
    """4x4 column-major node matrix for a MISSING_OBJECT marker node: the
    exact world transform the skipped instance WOULD have had (same mapping
    as real vertices: R*local + t + map-offset, then (x,-y,-z)*SCALE)."""
    R = np.array(inst.rt, dtype=np.float64).reshape(3, 3) / 4096.0
    t = np.array(inst.t, dtype=np.float64)
    m = np.array([MAP_CELL * room.x_pos, 0.0, MAP_CELL * room.y_pos],
                 dtype=np.float64)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t + m
    G = np.eye(4)
    G[0, 0], G[1, 1], G[2, 2] = SCALE, -SCALE, -SCALE
    out = G.dot(M)
    return [float(x) for x in out.flatten(order="F")]


def _role_assessment(instances):
    """Honest, transform-derived description of what a missing object's
    instances look like (placement pattern, height, spread).  No invented
    semantics - this characterizes the PLACEMENT, not the object."""
    if not instances:
        return "no instances"
    tys = [i.t[1] for i in instances]
    xs = [i.t[0] for i in instances]
    zs = [i.t[2] for i in instances]
    tilts = any(abs(i.rt[0] - 0x1000) > 0x10 or abs(i.rt[4] - 0x1000) > 0x10
                or abs(i.rt[8] - 0x1000) > 0x10 for i in instances)
    level = ("ground level (ty=0)" if all(t == 0 for t in tys)
             else f"ty range [{min(tys)},{max(tys)}]")
    return (f"{len(instances)} instances, {level}, "
            f"spread over x[{min(xs)},{max(xs)}] z[{min(zs)},{max(zs)}], "
            f"{'tilted' if tilts else 'upright'} rotations - consistent with "
            f"visually placed props, not collision-only markers")


def _b64(b):
    import base64 as _b64mod
    return _b64mod.b64encode(bytes(b)).decode("ascii")


# ---- v33 (S20): the room's ORIGINAL environment ------------------------
# WORLD_ENV_PRESETS[21] VERBATIM from src/bodyprog/sys/map_info.c:8-387
# (decomp, USA 1.1). The pair indices come from WorldEnv_MapPresetSet
# (effects.c:220-267) + D_800A9F80..A98 (effects.c:22-28) resolved per
# room from the map overlay headers (src/maps/mapN_sMM/header.c) via
# scripts/derive_room_env.py -> tools/room_env_table.json.
_WORLD_ENV_PRESETS = [
    {"idx": 0, "flags": [], "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 1.15,
     "worldTint": [1.0, 1.0, 1.0], "fogMode": "Off",
     "fogDistance": 100.0, "fogColor": [60, 60, 68],
     "snowColor": [64, 64, 64], "rainColor": [12, 12, 28]},
    {"idx": 1, "flags": [], "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 1.1,
     "worldTint": [0.95, 1.0, 1.08], "fogMode": "On",
     "fogDistance": 13.5, "fogColor": [108, 100, 116],
     "snowColor": [48, 48, 48], "rainColor": [14, 14, 30]},
    {"idx": 2, "flags": [], "lightLevelMax": 255, "lightMode": "Directional",
     "spotLightIntensity": 0.6, "worldLightIntensity": 0.6,
     "worldTint": [0.9, 1.0, 1.05], "fogMode": "On",
     "fogDistance": 14.0, "fogColor": [100, 92, 108],
     "snowColor": [48, 48, 48], "rainColor": [13, 13, 29]},
    {"idx": 3, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 1.3, "worldLightIntensity": 0.0,
     "worldTint": [0.95, 1.0, 1.08], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [48, 48, 48], "rainColor": [12, 12, 12]},
    {"idx": 4, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 0.7, "worldLightIntensity": 0.0,
     "worldTint": [0.9, 1.0, 1.05], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [48, 48, 48], "rainColor": [12, 12, 12]},
    {"idx": 5, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 1.3, "worldLightIntensity": 0.1,
     "worldTint": [0.95, 1.0, 1.08], "fogMode": "FollowLight",
     "fogDistance": 13.5, "fogColor": [68, 60, 76],
     "enableTintLightOverlap": True, "pointLightTint": [24, 16, 32],
     "worldTint2": [85, 75, 75],
     "snowColor": [32, 32, 40], "rainColor": [12, 12, 28]},
    {"idx": 6, "flags": ["Dark", "FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 0.44,
     "worldTint": [0.4, 0.7, 1.0], "fogMode": "On",
     "fogDistance": 14.0, "fogColor": [0, 0, 0],
     "snowColor": [16, 16, 24], "rainColor": [8, 8, 20]},
    {"idx": 7, "flags": ["Dark", "FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 0.44,
     "worldTint": [0.4, 0.7, 1.0], "fogMode": "On",
     "fogDistance": 9.29987, "fogColor": [0, 0, 0],
     "snowColor": [16, 16, 24], "rainColor": [8, 8, 20]},
    {"idx": 8, "flags": ["FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 80, "lightMode": "Spot",
     "spotLightIntensity": 0.35, "worldLightIntensity": 0.4,
     "worldTint": [0.7, 0.8, 1.0], "fogMode": "On",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [64, 64, 64], "rainColor": [12, 12, 12]},
    {"idx": 9, "flags": ["FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 1.8, "worldLightIntensity": 0.15,
     "worldTint": [1.0, 0.7, 0.6], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [64, 32, 16], "rainColor": [24, 12, 12]},
    {"idx": 10, "flags": ["FlashlightAllowed", "EnableBrightness", "UseLighter"],
     "lightLevelMax": 146, "lightMode": "Spot",
     "spotLightIntensity": 0.5, "worldLightIntensity": 0.0,
     "worldTint": [1.0, 0.8, 0.6], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [32, 24, 16], "rainColor": [18, 8, 8]},
    {"idx": 11, "flags": ["FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 1.8, "worldLightIntensity": 0.15,
     "worldTint": [1.3, 0.4, 0.2], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [64, 32, 16], "rainColor": [24, 12, 12]},
    {"idx": 12, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 1.3, "worldLightIntensity": 0.1,
     "worldTint": [0.95, 1.0, 1.08], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [48, 48, 48], "rainColor": [12, 12, 12]},
    {"idx": 13, "flags": [], "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 0.78,
     "worldTint": [0.74, 0.85, 1.0], "fogMode": "On",
     "fogDistance": 13.5, "fogColor": [92, 84, 100],
     "snowColor": [16, 16, 24], "rainColor": [8, 8, 20]},
    {"idx": 14, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 56, "lightMode": "Spot",
     "spotLightIntensity": 0.7, "worldLightIntensity": 0.05,
     "worldTint": [1.1, 0.6, 0.65], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [48, 48, 48], "rainColor": [12, 12, 12]},
    {"idx": 15, "flags": ["FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 196, "lightMode": "Spot",
     "spotLightIntensity": 1.2, "worldLightIntensity": 0.2,
     "worldTint": [0.7, 0.45, 0.45], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [64, 32, 16], "rainColor": [24, 12, 12]},
    {"idx": 16, "flags": ["FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 1.4, "worldLightIntensity": 0.05,
     "worldTint": [0.85, 0.6, 0.6], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [64, 32, 16], "rainColor": [24, 12, 12]},
    {"idx": 17, "flags": [], "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 1.0,
     "worldTint": [0.95, 0.9, 0.9], "fogMode": "On",
     "fogDistance": 6.5, "fogColor": [108, 100, 100],
     "snowColor": [48, 48, 48], "rainColor": [14, 14, 30]},
    {"idx": 18, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 2.5, "worldLightIntensity": 0.15,
     "worldTint": [1.0, 0.7, 0.7], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [64, 32, 16], "rainColor": [24, 12, 12]},
    {"idx": 19, "flags": ["Dark", "FlashlightAllowed", "EnableBrightness"],
     "lightLevelMax": 255, "lightMode": "None",
     "spotLightIntensity": 0.0, "worldLightIntensity": 0.55,
     "worldTint": [0.5, 0.88, 1.25], "fogMode": "On",
     "fogDistance": 15.0, "fogColor": [0, 0, 0],
     "snowColor": [16, 16, 24], "rainColor": [8, 8, 20]},
    {"idx": 20, "flags": ["FlashlightAllowed", "EnableBrightness", "EnableLensFlare"],
     "lightLevelMax": 255, "lightMode": "Spot",
     "spotLightIntensity": 0.8, "worldLightIntensity": 0.2,
     "worldTint": [0.95, 1.0, 1.08], "fogMode": "Off",
     "fogDistance": 40.0, "fogColor": [0, 0, 0],
     "snowColor": [48, 48, 48], "rainColor": [12, 12, 12]},
]

# audit m4: the raw enum values ride alongside the labels (Off=0/On=1/
# Zero=2/FollowLight=3 — effects.h:39-43; None/Spot/Directional — the
# UnkGfxEnum game.h SHENUM order) so a consumer never infers from labels.
for _p in _WORLD_ENV_PRESETS:
    _p["fogModeRaw"] = {"Off": 0, "On": 1, "Zero": 2, "FollowLight": 3}[_p["fogMode"]]
    _p["lightModeRaw"] = {"None": 0, "Spot": 1, "Directional": 2}[_p["lightMode"]]

_ROOM_ENV_TABLE = None
def _room_env_table():
    global _ROOM_ENV_TABLE
    if _ROOM_ENV_TABLE is None:
        import os as _os
        p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "room_env_table.json")
        try:
            _ROOM_ENV_TABLE = json.load(open(p))
        except Exception as _e:
            _ROOM_ENV_TABLE = {}
            print(f"WARNING room_env_table.json: {p} unreadable ({_e}) — "
                  "SH1X.env will NOT be emitted (re-run "
                  "scripts/derive_room_env.py)", file=sys.stderr)
    return _ROOM_ENV_TABLE


def _room_env(room_name):
    """v33 (S20): SH1X.env — the room's ORIGINAL WorldEnv pair. The map
    overlay header's field_16/field_17 (decomp src/maps/mapN_sMM/header.c,
    the ORIGINAL data) + MAP_INFOS flags -> WorldEnv_MapPresetSet
    (effects.c:220-267) -> the D_800A9F80..A98 pair. The presets are the
    verbatim WORLD_ENV_PRESETS[21] (map_info.c). Consumers boot this pair
    by default (the fog/lighting the room ACTUALLY ships with).
    HONESTY (audit M1): the room->overlay binding is derived from the
    decomp's map_points/camera coverage — 17 of 493 rooms are CONTESTED
    (the same room file serves overlays with different field_16; floors
    share cells); those carry contested:true + envAlternates."""
    e = _room_env_table().get(room_name.upper())
    if not e:
        return None
    out = {
        "presetIdx0": e["presetIdx0"], "presetIdx1": e["presetIdx1"],
        "field16": e["field16"], "field17": e["field17"],
        "weather": e["weather"], "mapType": e["tag"],
        "mapFlags": e["mapFlags"], "overlay": e["overlay"],
        "preset0": _WORLD_ENV_PRESETS[e["presetIdx0"]],
        "preset1": _WORLD_ENV_PRESETS[e["presetIdx1"]],
        "src": e["src"],
    }
    if e.get("inferredOverlay"):
        out["overlayInferred"] = True
    if e.get("contested"):
        # audit M1: the SAME room file serves several overlays whose
        # field_16 differs (floors/contexts share cells) — the primary is
        # the share-weighted pick; the alternates are the other overlays'
        # own pairs. A consumer may offer the alternates; the boot default
        # stays the primary.
        out["contested"] = True
        out["envAlternates"] = e["alternates"]
    return out


def build_sh1x(room, resolver, report, known_rooms=None):
    """Assemble the SH1X verbatim extras container for one room.

    Every field is the RAW source value (Q7.8/Q23.8/s16 units as stored).
    Byte-identical IPD+PLM reconstruction is possible from the `raw` blobs
    alone (see tools/sh1x_roundtrip.py); the decoded fields exist for
    consumer convenience and are pure functions of the raws.

    v3: adds the engine FX blocks (envEffects, waterZones, mapLink,
    propAnims, userLight defaults) — hardcoded decomp table values with
    per-field source citations (docs/SH1X_EXTRAS_V3_FX.md). All v3 fields
    are OPTIONAL for consumers: an absent/empty block = feature off, the
    pre-v3 render behavior unchanged (graceful no-op contract).
    `known_rooms` (optional set of room names in this conversion) enables
    mapLink neighbor emission; None skips mapLink.
    """
    inst_key = {id(i): n for n, i in enumerate(room.instances)}
    sh1x = {
        "schema": "SH1X", "version": 3,
        "room": room.name,
        "file": {"name": room.name + ".IPD", "size": room.file_size,
                 "sha256": room.file_sha256},
        # ---- s_IpdHeader, 84 bytes verbatim + decoded ------------------
        "header": {
            "magic": room.header_raw[0],
            "isLoaded": room.header_raw[1],
            "chunkX": room.x_pos,   # s8 @2 (decomp ipd.h: s8 chunkX @2; the
            "chunkZ": room.y_pos,   # s8 @3  Room() already reads s8 — the old
                                    # s16() here OVERLAPPED bytes 3..4: e.g.
                                    # HP0003 chunkZ read 0x0314=788 instead
                                    # of 3 — the painter consumer would have
                                    # computed WRONG chunk edges + subcells)
            "lmHdrOff": u32(room.header_raw, 4),
            "modelInfoCount": room.header_raw[8],
            "modelBufferCount": room.header_raw[9],
            "modelOrderSize": room.header_raw[10],
            "padC": list(room.header_raw[12:20]),
            "modelInfosOff": u32(room.header_raw, 0x14),
            "modelBuffersOff": u32(room.header_raw, 0x18),
            "textureCount": room.header_raw[0x1C],
            "subcellTable": [[list(room.subcell_table[(z, x)])
                              for x in range(5)] for z in range(5)],
            "modelOrderOff": u32(room.header_raw, 0x50),
            "raw": _b64(room.header_raw),
        },
        # ---- s_IpdModelInfo list, 16B each -----------------------------
        "modelInfos": [
            {"isExternal": s32(r, 0), "pad": list(r[1:4]),
             "name": r[4:12].decode("ascii", "replace").rstrip("\x00"),
             "modelHdrPtr": u32(r, 12), "raw": _b64(r)}
            for r in room.model_info_raws],
        # ---- s_IpdModelBuffer list + children, verbatim -----------------
        "modelBuffers": [],
        "modelOrder": list(room.model_order),
        # ---- s_IpdCollisionData, verbatim -------------------------------
        "collision": _sh1x_collision(room),
        # ---- the embedded PLM (s_LmHeader), verbatim ---------------------
        "plm": _sh1x_plm(room.plm),
    }
    # ---- v3 engine FX blocks (docs/SH1X_EXTRAS_V3_FX.md) ----------------
    env_fx, water_zones = _room_env_fx(room.name)
    if env_fx:
        sh1x["envEffects"] = env_fx
    if water_zones:
        sh1x["waterZones"] = water_zones
    # v33 (S20): the room's ORIGINAL environment (the WorldEnv pair + the
    # map-load weather) — see _room_env above.
    renv = _room_env(room.name)
    if renv:
        sh1x["env"] = renv
    if known_rooms is not None:
        ml = _room_maplink(room.name, known_rooms)
        if ml is not None:
            sh1x["mapLink"] = ml
    pa = _room_prop_anims(room.name)
    if pa:
        sh1x["propAnims"] = pa
    # v36: the TV screen paint tables (the tvNoise rooms — MAP4_S03's area)
    tvp = _tv_paint_extras(room, resolver, report)
    if tvp is not None:
        sh1x["tvPaint"] = tvp
    # v37: the WATER FLOOR palette (the slot-0 CLUT row 0 the DWAVE floor
    # redirect reads the live tile's 4bpp nibbles through)
    wfl = _room_water_floor(room, resolver, report)
    if wfl is not None:
        sh1x["waterFloor"] = wfl
    # v39: the WATER.TIM effect texture (the school Water rooms — the
    # stream surface + droplet + spray sprites sample it; water.c)
    if env_fx.get("effectTexFlag") == "Water":
        wtx = _room_water_tex(room.name, resolver, report)
        if wtx is not None:
            sh1x["waterTex"] = wtx
    # userLight defaults: the engine's flashlight attribs (Game_Flashlight
    # AttribsSet effects.c:210-218) — consumers may override everything;
    # the PoC's standing directive (light rides the CAMERA) is the default
    # consumer behavior, so only the verbatim constants ride here.
    sh1x["userLight"] = {
        "mode": "Spot",
        "localOffset": [-0.08, -0.28, 0.12],   # meters, engine frame
        "rotation": [-15.0, 0.0, 0.0],          # degrees (pitch, yaw, roll)
        "intensityDefault": 1.0,                # g_SysWork.lightIntensity
        "ramp": {"ratePerSec": 4.0, "range": [0, 4096],
                 "units": "Q12; WorldEnv_Update effects.c:417-426"},
        "dayModes": "never Spot (preset table; isFlashlightUnavailable)",
        "src": "Game_FlashlightAttribsSet effects.c:210-218; "
               "WorldEnv_Update effects.c:417-426",
    }
    for pi, br in enumerate(room.model_buffer_raws):
        buf = {
            "modelInstanceCount": br[0],
            "billboardInstanceCount": br[1],
            "subchunkCount": br[2],
            "pad": br[3],
            "minX": s16(br, 4), "maxX": s16(br, 6),
            "minZ": s16(br, 8), "maxZ": s16(br, 10),
            "modelInstancesOff": u32(br, 12),
            "billboardInstancesOff": u32(br, 16),
            "subchunkRangesOff": u32(br, 20),
            "instances": [], "billboards": [], "subchunkRanges": [],
            "raw": _b64(br),
        }
        for inst in room.instances:
            if inst.group != pi:
                continue
            buf["instances"].append({
                "objIdx": inst.obj_idx,
                "rt": list(inst.rt),
                "pad": struct.unpack_from("<H", inst.raw, 22)[0],
                "t": list(inst.t),
                "raw": _b64(inst.raw),
            })
        for k, r in enumerate(room.billboard_raws.get(pi, ())):
            x, y, z, w = struct.unpack_from("<4h", r)
            buf["billboards"].append(
                {"offset": [x, y, z], "idx": w, "raw": _b64(r)})
        for r in room.subchunk_raws.get(pi, ()):
            buf["subchunkRanges"].append(
                {"minX": s16(r, 0), "maxX": s16(r, 2),
                 "minZ": s16(r, 4), "maxZ": s16(r, 6), "raw": _b64(r)})
        sh1x["modelBuffers"].append(buf)
    # ---- referenced TIMs, whole-file verbatim --------------------------
    texs = []
    for name in sorted(report["tex_ok"]):
        tim = report["tim_cache"].get(name)
        if tim is not None and getattr(tim, "data", None):
            texs.append({"name": name, "size": len(tim.data),
                         "sha256": hashlib.sha256(tim.data).hexdigest(),
                         "tim": _b64(tim.data)})
    sh1x["textures"] = texs
    # ---- derived render constants (redundant, documented) ---------------
    sh1x["render"] = {
        "otShift": 1,
        "otBaseOfFlagB1": dict(PlmObject.OT_BASE_OF_FLAG_B1),
        "mapCell": MAP_CELL, "scale": SCALE,
        "addOrder": ("modelOrder[subcell range] -> buffers in list order -> "
                     "instances in order, then billboards; meshes in PLM "
                     "order; packs in pack order (WorldMap_Draw, "
                     "world_map.c:1349-1447)"),
        "quadBucket": ("ot_base + (MAX vertex SZ Q8 >> 3)  [otShift 1: "
                       "((maxZ >> 1) >> 2)]; <=32 -> 32; > farCull -> skip"),
        "farCullQ8": 0x79C << 3,   # engine Gfx_MeshDraw: MIN(0x79C<<(otShift+2), fog.far)
        "semiTransBit": "pack byte @7 bit 7 (engine prim->bits1.flags & (1<<15))",
    }
    return sh1x


def _sh1x_plm_objects(plm):
    """Every s_ModelHeader in FILE order (duplicates included — the SH1X
    verbatim contract; `objects`-by-name drops later duplicates)."""
    out = []
    for o in plm.all_objects:
        out.append({
            "name": o.name, "meshCount": len(o.meshes),
            "vertexOffset": o.vertex_offset,
            "normalOffset": o.normal_offset,
            "flagsByte": o.d_flag,
            "fieldB0": o.flag_b0, "fieldB1": o.flag_b1,
            "fieldB4": o.flag_b4, "unkB6": o.unk_b6,
            "otBase": o.ot_base,
            "meshes": [
                {"primitiveCount": len(mesh.packs),
                 "vertexCount": len(mesh.verts),
                 "normalCount": len(mesh.normals_a),
                 "unkCount3": len(mesh.slot_vertex),
                 "vertsXY": [list(v) for v in mesh.verts_xy],
                 "vertsZ": list(mesh.verts_z),
                 "normals": [{"nx": n[0], "ny": n[1], "nz": n[2],
                              "slotCount": n[3]} for n in mesh.normals_a],
                 "slots": list(mesh.slot_vertex),
                 "packs": [
                     {"u0": p.uv[0][0], "v0": p.uv[0][1], "cba": p.cba,
                      "u1": p.uv[1][0], "v1": p.uv[1][1],
                      "b6": p.b6, "b7": p.b7,
                      "texIdx": p.tex_num, "semiTransparent": p.stp,
                      "u2": p.uv[2][0], "v2": p.uv[2][1],
                      "u3": p.uv[3][0], "v3": p.uv[3][1],
                      "faces": list(p.faces),
                      "normalSlots": list(p.normal_slots),
                      "raw": _b64(struct.pack(
                          "<BBH8B4B4B",
                          p.uv[0][0], p.uv[0][1], p.cba,
                          p.uv[1][0], p.uv[1][1],
                          p.b6, p.b7,
                          p.uv[2][0], p.uv[2][1],
                          p.uv[3][0], p.uv[3][1],
                          p.faces[0], p.faces[1], p.faces[2], p.faces[3],
                          p.normal_slots[0], p.normal_slots[1],
                          p.normal_slots[2], p.normal_slots[3]))}
                     for p in mesh.packs],
                 "headerRaw": _b64(mesh.header_raw)}
                for mesh in o.meshes],
            "headerRaw": _b64(o.header_raw)})
    return out


def _sh1x_collision(room):
    c = room.collision
    if c is None:
        return None
    return {
        "positionX": c.position_x, "positionZ": c.position_z,
        "counts": {"splitV": c.n_split_v, "surface": c.n_surface,
                   "polygon": c.n_polygon, "cylinder": c.n_cylinder},
        "splitVertices": [{"x": v[0], "y": v[1], "z": v[2],
                           "raw": _b64(struct.pack("<3h", *v))}
                          for v in c.split_vertices],
        "surfaces": [dict(s, raw=_b64(s["raw"])) for s in c.surfaces],
        "polygons": [dict(p, raw=_b64(p["raw"])) for p in c.polygons],
        "cylinders": [dict(y, raw=_b64(y["raw"])) for y in c.cylinders],
        "cellSize": c.cell_size,
        "cellCountX": c.cell_count_x, "cellCountZ": c.cell_count_z,
        "shapeAllocs": [list(a) for a in c.shape_allocs],
        "shapeLutSize": c.shape_lut_size,
        "surfaceLutSize": c.surface_lut_size,
        "shapeLut": list(c.shape_lut),
        "surfaceLut": list(c.surface_lut),
        "shapePassCounter": c.shape_pass_counter,
        "stampBuffer": list(c.stamp_buffer),
        "headerRaw": _b64(c.header_raw),
        "blockRaw": _b64(room.collision_raw),
    }


def _sh1x_plm(plm):
    return {
        "magic": u16(plm.header_raw, 0),
        "version": plm.header_raw[2],
        "isLoaded": plm.header_raw[3],
        "texNameOff": u32(plm.header_raw, 4),
        "objNum": plm.header_raw[8],
        "pad": list(plm.header_raw[9:12]),
        "objStartOff": u32(plm.header_raw, 12),
        "orderOff": u32(plm.header_raw, 16),
        "order": list(plm.order_raw),
        "trailingRaw": _b64(plm.trailing_raw),
        "materials": [
            {"name": r[:8].decode("ascii", "replace").rstrip("\x00"),
             "texPtr": u32(r, 8), "fieldC": r[12], "fieldD": r[13],
             "fieldE": r[14], "fieldF": r[15],
             "field10": u16(r, 16), "field12": u16(r, 18),
             "uv14": [r[20], r[21]], "uv16": [r[22], r[23]],
             "raw": _b64(r)}
            for r in plm.tex_raws],
        "objects": _sh1x_plm_objects(plm),
        "headerRaw": _b64(plm.header_raw),
    }


def export_room(room, resolver, out_dir, include_unused=False, builder=None,
                known_rooms=None):
    """Export one room to <name>.glb (default) or append it into a shared
    whole-map builder (--whole-map mode).

    When `builder` is given, NO file is written by this call: the room's
    scene-root nodes are re-parented under ONE new root node named exactly
    `room.name` (identity transform - vertices already carry absolute
    map-grid world coordinates, engine CHUNK_SIZE=10240 semantics), the report
    counters describe this room's contribution (per-room deltas with the
    same meaning as a per-room file), and the caller writes the combined
    <PREFIX>_MAP.glb.  Returns a report dict.
    """
    shared = builder is not None
    report = {
        "room": room.name, "path": room.path,
        "grid_pos": [room.x_pos, room.y_pos],
        "problems": list(room.problems),
        "repairs": [], "repairs_degenerate_quads": 0, "repairs_zero_normals": 0,
        "tex_variants": {}, "tim_cache": {}, "tex_assignments": {},
        "tex_referenced": set(), "tex_ok": set(), "tex_missing": set(),
        "instances": 0, "meshes": 0, "vertices": 0, "triangles": 0,
        "skipped_instances": [], "imported_objects": [],
        "degraded": False, "degradation_reasons": [],
    }
    if not shared:
        builder = GltfBuilder()
    # builder-state snapshots: per-room deltas in shared mode; in per-room
    # mode all snapshots are 0 so the values are identical to before
    # (stats["meshes"] always equals len(json["meshes"]))
    s_meshes = builder.stats["meshes"]
    s_prims = builder.stats["primitives"]
    s_mats = len(builder.json["materials"])
    s_imgs = len(builder.json["images"])
    s_texs = len(builder.json["textures"])
    s_nodes = len(builder.json["nodes"])
    s_roots = len(builder.json["scenes"][0]["nodes"])
    name_counts = {}
    ledger_by_key = {(r["room"], r["ref"].upper(), r["source"]): r
                     for r in resolver.object_ledger}
    imported_seen = {}
    # billboard foliage clusters (engine Gfx_BillboardDraw rings; generated
    # from the unk1/field_10 anchor table, NOT from the PLM LEAF objects -
    # see parse_ipd evidence block).  v10: textured with the REAL engine
    # texture - --leaf-texture PNG override first, else the auto-discovered
    # TIM/BG_ETC.TIM (filetable 1799, engine window + CLUT row 2) through
    # the standard resolver; only when neither exists are they DROPPED with
    # a loud per-anchor report (leaf_billboards_dropped) - never silently,
    # and with NO LEAVES.TIM fallback.
    leaf_texture = None
    leaf_path = getattr(resolver, "leaf_texture_path", None)
    if leaf_path:
        try:
            with open(leaf_path, "rb") as f:
                leaf_png = f.read()
        except OSError as e:
            raise RuntimeError(
                f"--leaf-texture: cannot read {leaf_path!r}: {e}") from e
        leaf_texture = {"png": leaf_png,
                        "source": f"--leaf-texture {leaf_path}",
                        "status": "user_supplied"}
    else:
        # lazily discover+decode BG_ETC.TIM once per resolver (cached)
        cache = getattr(resolver, "_leaf_texture_cache", False)
        if cache is False:
            cache = resolver.load_leaf_texture()
            resolver._leaf_texture_cache = cache
        leaf_texture = cache
    # ---- v11: THE ENGINE ADD ORDER (WorldMap_Draw, world_map.c:1349-1399) --
    # For each model buffer (pos group) in FILE order — measured identical to
    # the engine's modelOrderList order inside every subcell range (all 25
    # ranges ascending) — emit the buffer's INSTANCES (file order), THEN the
    # buffer's BILLBOARD anchors (world_map.c:1378 runs the field_10 loop
    # after the instance loop of the same buffer).  Ordering-table ties
    # resolve LIFO in the consumer, so this add order IS the layering; v10
    # emitted ALL billboards FIRST (inverting billboard-vs-mesh ties) and all
    # instances in one flat pass (identical relative order to this code for
    # instances, but wrong for billboards).
    inst_by_group = {}
    for inst in room.instances:
        inst_by_group.setdefault(inst.group, []).append(inst)
    emit_groups = sorted(set(list(inst_by_group.keys()) +
                             list(room.buffer_billboards.keys())))
    report["draw_order"] = {
        "policy": ("engine WorldMap_Draw order: per model buffer (file "
                   "order = the modelOrderList's ascending order in every "
                   "subcell range, measured), instances first, then that "
                   "buffer's billboard anchors; meshes in PLM order, packs "
                   "in pack order"),
        "groups_emitted": list(emit_groups),
        "order_problems": list(room.order_problems),
        "model_order_count": room.order_count,
        "model_order": list(room.model_order),
        "subcell_table": {f"({z},{x})": list(v)
                          for (z, x), v in sorted(room.subcell_table.items())},
        "buffer_subcells": {str(b): [list(s) for s in subs]
                            for b, subs in sorted(room.buffer_subcells.items())},
    }
    report["problems"].extend(
        f"draw order: {p}" for p in room.order_problems)
    # ---- SH1X v14: NO LAYER SEPARATION ---------------------------------
    # The v12/v13c z-offset recession pass (1-3 PS1 units along the winner
    # normal) is REMOVED: it mutated authored geometry and left visible
    # seams at room corners (user report, white background).  The correct
    # contract: geometry at AUTHORED positions (stock glTF viewers render
    # the room as-is, z-buffer quirks included), and the ENGINE-EXACT
    # painter consumer reads the verbatim SH1X extras below — reproducing
    # WorldMap_Draw/Gfx_MeshDraw ordering-table semantics bit-identically
    # with zero geometry mutation.
    layer_offsets, layer_info = None, {"disabled": True, "reason": (
        "v14: removed — geometry stays authored; the engine-exact consumer "
        "paints from SH1X extras (OT bases + add order + buckets), not "
        "from depth-separated geometry")}
    report["layer_separation"] = layer_info
    inst_key_of = {id(inst): i for i, inst in enumerate(room.instances)}
    # ---- v11: PLM object render flags (s_ModelHeader byte @11) + the
    # consumer cross-check.  field_B_1 selects the ordering-table section
    # base (func_80057090 -> func_800571D0: 0->2, 1->0, 2->4, 3->33, 4->66,
    # 5->99).  The consumer (fog_poc.c) maps model NAMES to field_B_1 via a
    # hardcoded table (IPD_MODEL_LAYERS); every mismatch between the TRUE
    # PLM byte and that table is a layering defect in the rendered
    # wallpaper — reported loudly here so the two never silently diverge.
    plm_flags, flag_problems = [], []
    seen_objs = {}
    for inst in room.instances:
        lib = inst.resolved_lib if inst.resolved_lib is not None else (
            room.plm if inst.source == "ipd" else room.glb)
        if lib is None:
            continue
        obj = lib.objects.get(inst.lookup_name)
        if obj is None or inst.lookup_name in seen_objs:
            continue
        seen_objs[inst.lookup_name] = True
        entry = {
            "object": inst.lookup_name, "library": lib.source_name,
            "flags_byte": obj.d_flag, "field_B_0": obj.flag_b0,
            "field_B_1": obj.flag_b1, "ot_base": obj.ot_base,
            "field_B_4": obj.flag_b4, "unk_B_6": obj.unk_b6,
        }
        if inst.lookup_name in CONSUMER_IPD_MODEL_LAYERS:
            entry["consumer_field_B_1"] = CONSUMER_IPD_MODEL_LAYERS[inst.lookup_name]
            if entry["consumer_field_B_1"] != obj.flag_b1:
                flag_problems.append(
                    f"object {inst.lookup_name!r}: TRUE PLM field_B_1="
                    f"{obj.flag_b1} (otBase {obj.ot_base}) but the consumer's "
                    f"IPD_MODEL_LAYERS table says "
                    f"{entry['consumer_field_B_1']} — the wallpaper would "
                    f"layer this object in the WRONG ordering-table section")
        else:
            entry["consumer_field_B_1"] = None
            if obj.flag_b1 != 0:
                flag_problems.append(
                    f"object {inst.lookup_name!r}: TRUE PLM field_B_1="
                    f"{obj.flag_b1} (otBase {obj.ot_base}) is NOT in the "
                    f"consumer's IPD_MODEL_LAYERS table — the wallpaper "
                    f"would use the default base 2 for it")
        if obj.flag_b0 or obj.flag_b4 or obj.unk_b6:
            flag_problems.append(
                f"object {inst.lookup_name!r}: nonstandard s_ModelHeader "
                f"flags (B0={obj.flag_b0} B4={obj.flag_b4} unk_B6="
                f"{obj.unk_b6}) — the engine would use an alternate "
                f"transform/draw path (func_8005A21C / func_80059D50); "
                f"exported via the standard path, deviation reported")
        plm_flags.append(entry)
    report["plm_object_flags"] = {
        "semantics": ("s_ModelHeader byte @11 bitfield (decomp "
                      "formats/model.h): bit0 field_B_0 (alternate transform "
                      "path), bits1-3 field_B_1 (the ORDERING-TABLE SECTION "
                      "BASE selector — func_80057090/func_800571D0: "
                      "0->2, 1->0, 2->4, 3->33, 4->66, 5->99), bits4-5 "
                      "field_B_4 (alternate draw path), bits6-7 unknown"),
        "objects": plm_flags,
        "problems": flag_problems,
        "node_extras_emitted": ("every instance/mesh node carries glTF "
                                "extras {ot_base, field_B_1} with the TRUE "
                                "engine section base from this table; "
                                "billboard nodes carry ot_base 0 "
                                "(Gfx_BillboardDraw adds with no base). A "
                                "consumer reads extras.ot_base instead of a "
                                "hardcoded per-room model-name table"),
    }
    report["problems"].extend(flag_problems)
    for g in emit_groups:
        for inst in inst_by_group.get(g, ()):
            lib = inst.resolved_lib if inst.resolved_lib is not None else (
                room.plm if inst.source == "ipd" else room.glb)
            obj = lib.objects.get(inst.lookup_name) if lib is not None else None
            if obj is None:
                # ---- explicit, loud skip (never silent) ----
                lrec = ledger_by_key.get((room.name, inst.obj_name.upper(),
                                          inst.source), {})
                skip = {
                    "room": room.name, "context": inst.context,
                    "object": inst.obj_name, "source": inst.source,
                    "expected_asset": "PLM object " + (
                        "in the IPD's embedded PLM" if inst.source == "ipd"
                        else f"in {room.name[:-4]}_GLB.PLM"),
                    "expected_library": lrec.get("expected_library"),
                    "archives_scanned": lrec.get("archives_scanned"),
                    "folders_scanned": lrec.get("folders_scanned"),
                    "candidates_considered": lrec.get("candidates"),
                    "resolution_status": lrec.get("status"),
                    "reason": lrec.get("reason") or "object not present in its library",
                    "tree_evidence": lrec.get("tree_evidence"),
                    "role_assessment": _role_assessment(
                        [i for i in room.instances
                         if i.obj_name == inst.obj_name]),
                    "materiality": ("geometry for this reference is absent from "
                                    "every provided source; visual accuracy of the "
                                    "room is reduced where the instances stand"),
                }
                report["skipped_instances"].append(skip)
                if not report["degraded"]:
                    report["degraded"] = True
                reason = (f"object {inst.obj_name!r} unresolved: "
                          f"{lrec.get('reason') or 'not in its library'}")
                if reason not in report["degradation_reasons"]:
                    report["degradation_reasons"].append(reason)
                # marker node at the exact intended transform (no fabricated
                # geometry: an empty, clearly-named node for scene inspection)
                builder.add_node(f"MISSING_OBJECT_{inst.obj_name}", None, None)
                builder.json["nodes"][-1]["matrix"] = _instance_marker_matrix(room, inst)
                continue
            if inst.resolved_lib is not None:
                ilrec = ledger_by_key.get(
                    (room.name, inst.obj_name.upper(), inst.source), {})
                imp = imported_seen.setdefault(inst.obj_name, {
                    "object": inst.obj_name, "imported_from": inst.resolved_from,
                    "instances": 0, "strategy": ilrec.get("strategy"),
                    "reason": ilrec.get("reason")})
                imp["instances"] += 1
            report["instances"] += 1
            mesh_pack_offsets = {}
            mesh_indices = build_instance_meshes(room, inst, lib, resolver,
                                                 builder, report,
                                                 layer_offsets=None,
                                                 inst_key=inst_key_of[id(inst)],
                                                 out_mesh_pack_offsets=None)
            if not mesh_indices:
                continue
            n = name_counts.get(inst.obj_name, 0)
            name_counts[inst.obj_name] = n + 1
            node_name = inst.obj_name if n == 0 else f"{inst.obj_name}#{n}"
            if inst.resolved_lib is not None:
                node_name = f"{node_name}@{os.path.basename(inst.resolved_from)}"
            # per-model OT section base from the object's OWN PLM header
            # (engine func_80057090 -> func_800571D0), emitted as node extras
            obj_meta = None
            obj = lib.objects.get(inst.lookup_name)
            if obj is not None:
                # SH1X node extras: derived references into the scene-level
                # SH1X container (kept for loader convenience; redundant by
                # design — see docs/SH1X_EXTRAS_SCHEMA.md)
                obj_meta = {
                    "ot_base": obj.ot_base, "field_B_1": obj.flag_b1,
                    "SH1X": {
                        "room": room.name, "buffer": inst.group,
                        "object": inst.obj_name,
                        "plm_object": (room.plm.obj_order.index(inst.obj_name)
                                       if inst.obj_name in room.plm.obj_order
                                       else -1),
                        "objIdx": inst.obj_idx,
                        "add_seq": sum(len(room.buffer_billboards.get(b, ()))
                                       for b in range(inst.group)) + inst.group,
                    },
                }
            mesh_nodes = [builder.add_node(f"{node_name}_m{j}", mi, root=False,
                                           extras=dict(obj_meta) if obj_meta else None)
                          for j, mi in enumerate(mesh_indices)]
            builder.add_node(node_name, None, mesh_nodes, extras=obj_meta)

        # ---- this buffer's billboard anchors (engine: the field_10 loop
        # runs AFTER the instance loop of the SAME buffer)
        anchors = room.buffer_billboards.get(g)
        if anchors:
            bb = build_billboard_meshes(room, builder, report, leaf_texture,
                                        anchors=anchors)
            for j, mi in enumerate(bb):
                # engine Gfx_BillboardDraw: AddPrim at org[z>>otShift] with
                # NO section base - billboards ride the base-0 OT section
                builder.add_node(f"BILLBOARDS_g{g}_{j}", mi,
                                 extras={"ot_base": 0, "billboard": True})
    if include_unused and room.unplaced:
        # v27.2: posed-emission objects (fans, rattling doors, the chain-door
        # set, the wheelchair, park rides, the beans) are UNPLACED models —
        # --include-unused used to double-emit them (an UNUSED_ node at the
        # origin PLUS the posed node). Skip every name the posed emission
        # below will emit.
        try:
            _pa_skip = _room_prop_anims(room.name)
        except Exception:
            _pa_skip = []
        _posed_names = set()
        for _pe in _pa_skip:
            _pn = _pe.get("object", "")
            if _pn and not _pn.startswith("<"):
                _posed_names.add(_pn.upper())
            for _opn in _pe.get("objectPerInst") or []:
                _posed_names.add(str(_opn).upper())
        unused_children = []
        for un in room.unplaced:
            if un.upper() in _posed_names:
                continue                    # v27.2: posed below, not UNUSED_
            obj = room.plm.objects.get(un)
            if obj is None or not obj.meshes:
                continue
            fake = Instance(un, "ipd", (0x1000, 0, 0, 0, 0x1000, 0, 0, 0, 0x1000),
                            (0, 0, 0), "unused")
            mi = build_instance_meshes(room, fake, room.plm, resolver, builder, report)
            if mi:
                umeta = {"ot_base": obj.ot_base, "field_B_1": obj.flag_b1}
                mesh_nodes = [builder.add_node(f"UNUSED_{un}_m{j}", m, root=False,
                                               extras=umeta)
                              for j, m in enumerate(mi)]
                unused_children.append(builder.add_node(f"UNUSED_{un}", None,
                                                        mesh_nodes, extras=umeta))
        if unused_children:
            builder.json["nodes"].append({"name": "UNPLACED_MESHES",
                                          "children": unused_children})
            builder.json["scenes"][0]["nodes"].append(len(builder.json["nodes"]) - 1)

    # ---- v27: POSED EMISSION of unplaced animated WorldObjects -----------
    # The engine's animated props (fans, rattling doors, the chain-door set,
    # the wheelchair, park rides) are NOT IPD instances: map overlay C code
    # adds them per frame via WorldObjects_Add with an authored pose
    # (ANIMS_MAPLINK evidence). Their MODELS sit unplaced in the room's
    # embedded PLM or a sibling library. This block emits each catalog
    # propAnims entry's object as REAL geometry:
    #   * local-space meshes (identity rt, t = -chunkOrigin => local verts)
    #   * glTF node translation = the engine WorldObject pos (axis map
    #     (x, -y, -z)), NO rotation: the consumer applies the driver's rot0
    #     and live rotation exactly like WorldObjects_Draw composes one
    #     matrix from the full rot each frame (fog_poc sh1x_anim_apply).
    # Objects already placed as room instances animate through the normal
    # name bind and are NOT re-emitted. Poses with no known position (table
    # refs whose values are not in the decomp repo) are skipped loudly.
    try:
        _pa = _room_prop_anims(room.name)
    except Exception as ex:                          # never break the export
        _pa = []
        report["problems"].append(
            f"{room.name}: propAnims emission skipped ({ex})")
    _placed_upper = {n.upper() for n in room.plm.obj_order
                     if n not in room.unplaced} if room.plm else set()
    for _e in _pa:
        _obj_name = _e.get("object", "")
        if (not _obj_name or _obj_name.startswith("<")
                or (not isinstance(_e.get("pos"), (list, str))
                    and not isinstance(_e.get("posPerInst"), list))):
            continue                    # <light>/<ripples>/None: manifest
        if _obj_name.upper() in _placed_upper:
            continue                    # placed: the bind drives it
        # ---- locate the model (this room's PLM, else the PlmIndex ladder) --
        _lib = None
        _lname = _obj_name
        _opi = _e.get("objectPerInst")
        if room.plm:
            for _n in room.plm.obj_order:
                if _n.upper() == _obj_name.upper():
                    _lib, _lname = room.plm, _n
                    break
        if _lib is None and resolver is not None and resolver.plm_index:
            _cands = resolver.plm_index.by_name.get(_obj_name.upper()) or []
            if _cands:
                _cands = sorted(_cands,
                                key=lambda r: (r["in_archive"],
                                               len(r["label"]), r["label"]))
                _lib, _lname = _cands[0]["lib"], _obj_name
        if _lib is None:
            report.setdefault("prop_anim_unemitted", []).append({
                "object": _obj_name, "reason":
                "model not present in any scanned PLM/IPD (geometry absent "
                "from the provided sources)"})
            continue
        _obj = _lib.objects.get(_lname) if _lib is not None else None
        if _obj is None or not _obj.meshes:
            report.setdefault("prop_anim_unemitted", []).append({
                "object": _obj_name, "reason": "model found but empty"})
            continue
        # ---- initial poses (engine t=0) per instance -----------------------
        _poses = _anim_initial_poses(_e)
        if not _poses:
            # v27.2: LOUD skip — table-ref/no-pos entries (sineBob's horse
            # tables, tvNoise's screen tables) previously vanished silently
            report.setdefault("prop_anim_unemitted", []).append({
                "object": _obj_name,
                "reason": "no initial pose data (table refs not in the "
                          "decomp repo — see the entry's data/src fields)"})
            continue
        _mvec = (MAP_CELL * room.x_pos, 0, MAP_CELL * room.y_pos)
        for _i, _p in enumerate(_poses):
            # v27.2: per-instance object names (map7_s02 beans: BEAN1_HI..
            # BEAN8_HI — beanObjName[4] = (i >> 1) + '1'). Resolve the
            # INSTANCE's model in the room PLM (exact-case name) so each
            # bean gets ITS geometry, its ot_base and its field_B_1.
            _ilname, _iobj = _lname, _obj
            if isinstance(_opi, list) and _i < len(_opi) and _opi[_i]:
                _in = str(_opi[_i])
                _ilname = _in
                if room.plm:
                    for _n in room.plm.obj_order:
                        if _n.upper() == _in.upper():
                            _ilname = _n
                            break
                _o2 = _lib.objects.get(_ilname) if _lib is not None else None
                if _o2 is not None and _o2.meshes:
                    _iobj = _o2
                else:
                    report.setdefault("prop_anim_unemitted", []).append({
                        "object": _in, "inst": _i,
                        "reason": "per-instance model missing/empty"})
                    continue
            _nname = _obj_name if _i == 0 else f"{_obj_name}#{_i}"
            # NOTE: the Instance carries the PLM OBJECT name (the lookup
            # key); the glTF NODE name gets the #N instance suffix.
            _fake = Instance(_ilname, "ipd",
                             (0x1000, 0, 0, 0, 0x1000, 0, 0, 0, 0x1000),
                             (-_mvec[0], 0, -_mvec[2]), "propAnimPosed")
            if _lib is not room.plm:
                _fake.resolved_lib = _lib
                _fake.resolved_from = getattr(_lib, "source_name", "sibling")
                _fake.resolved_obj_name = _ilname
            _mi = build_instance_meshes(room, _fake, _lib, resolver,
                                        builder, report)
            if not _mi:
                continue
            _meta = {"ot_base": _iobj.ot_base, "field_B_1": _iobj.flag_b1,
                     "propAnimPosed": True, "animInst": _i}
            if _e.get("cutsceneOnly"):
                _meta["cutsceneOnly"] = True   # engine-fresh: NOT drawn
            _mn = [builder.add_node(f"{_nname}_m{j}", m, root=False,
                                    extras=dict(_meta))
                   for j, m in enumerate(_mi)]
            _ni = builder.add_node(_nname, None, _mn, extras=_meta)
            # glTF node translation (meters, axis map (x,-y,-z)); NO rotation:
            # the consumer's driver owns the full rotation (rot0 at rest).
            builder.json["nodes"][_ni]["translation"] = [
                float(_p[0]), float(-_p[1]), float(-_p[2])]
            report.setdefault("prop_anim_posed", []).append(
                {"object": _obj_name, "inst": _i,
                 "pos": [float(v) for v in _p],
                 "library": getattr(_lib, "source_name", "embedded")})
    # Geometry-only IPD (pos_num == 0, no object name list): the embedded PLM objects
    # ARE the room content - export them at identity transform + map offset, exactly
    # like the legacy tool does for such files. Deterministic rule, documented.
    if room.pos_num == 0 and not room.instances and room.plm.obj_order:
        report["container_only"] = True
        for name in room.plm.obj_order:
            fake = Instance(name, "ipd", (0x1000, 0, 0, 0, 0x1000, 0, 0, 0, 0x1000),
                            (0, 0, 0), "container")
            mi = build_instance_meshes(room, fake, room.plm, resolver, builder, report)
            if mi:
                cobj = room.plm.objects.get(name)
                cmeta = ({"ot_base": cobj.ot_base, "field_B_1": cobj.flag_b1}
                         if cobj is not None else None)
                mesh_nodes = [builder.add_node(f"{name}_m{j}", m, root=False,
                                               extras=cmeta)
                              for j, m in enumerate(mi)]
                builder.add_node(name, None, mesh_nodes, extras=cmeta)
    if shared:
        # re-parent this room's scene roots under ONE node named after the
        # room: the map scene then has exactly one root per room, identity
        # transform (absolute coordinates are baked into the vertices)
        room_roots = builder.json["scenes"][0]["nodes"][s_roots:]
        del builder.json["scenes"][0]["nodes"][s_roots:]
        report["map_parent_node"] = builder.add_node(room.name, None,
                                                     room_roots)
        # ---- SH1X verbatim extras: whole-map mode stores per-room SH1X
        # containers on the per-room ROOT node's extras (each room is
        # self-contained); the per-room file mode puts the SAME container
        # on scenes[0].extras.SH1X (below). v3: known_rooms = every room
        # of this map (the shared builder's roster) so mapLink neighbors
        # resolve within the combined world.
        room_root_node = builder.json["nodes"][report["map_parent_node"]]
        room_root_node["extras"] = room_root_node.get("extras") or {}
        try:
            # v40 audit (D-F4): whole-map mode crashed with NameError —
            # this line referenced `map_rooms`, a main() LOCAL (verified:
            # `--whole-map THR` on the test corpus = "ERROR ... name
            # 'map_rooms' is not defined", NO map GLB ever written). Use
            # the known_rooms PARAMETER (main() passes input_room_names —
            # every room of this conversion; _room_maplink matches
            # same-tag neighbors only, so the superset is safe and
            # identical to the per-room mode's semantics).
            room_root_node["extras"]["SH1X"] = build_sh1x(
                room, resolver, report, known_rooms=known_rooms)
        except Exception as e:
            report["problems"].append(f"SH1X emission failed: {e}")
            raise
        room_meshes = builder.json["meshes"][s_meshes:]
        mats_used = {p["material"] for m in room_meshes
                     for p in m["primitives"] if "material" in p}
        assigned_images = set()
        for mi in mats_used:
            bct = builder.json["materials"][mi].get(
                "pbrMetallicRoughness", {}).get("baseColorTexture")
            if bct is not None:
                assigned_images.add(
                    builder.json["textures"][bct["index"]]["source"])
        # per-room counters, same semantics as a per-room file:
        # materials = distinct materials used by this room's primitives;
        # images = distinct texture variants bound by this room's geometry
        # (in whole-map mode some PNGs are shared with other rooms via
        # content dedup - the count of distinct variants is unchanged)
        report.update({
            "output": None, "bytes": 0,
            "meshes": builder.stats["meshes"] - s_meshes,
            "primitives": builder.stats["primitives"] - s_prims,
            "materials": len(mats_used),
            "images": len(assigned_images),
            "nodes": len(builder.json["nodes"]) - s_nodes,
            "png_conversions": len(builder.json["images"]) - s_imgs,
        })
    else:
        out_path = os.path.join(out_dir, f"{room.name}.glb")
        # ---- SH1X verbatim extras on the scene (the room's whole IPD+PLM
        # data, byte-identical; docs/SH1X_EXTRAS_SCHEMA.md).  A stock glTF
        # viewer ignores it; the engine-exact consumer paints from it.
        # v3: known_rooms = the caller-provided input-dir roster (the full
        # grid available to THIS conversion — neighbors not converted are
        # simply absent; consumers probe filenames at runtime anyway).
        scene0 = builder.json["scenes"][0]
        scene0["extras"] = scene0.get("extras") or {}
        try:
            scene0["extras"]["SH1X"] = build_sh1x(
                room, resolver, report, known_rooms=known_rooms)
        except Exception as e:
            report["problems"].append(f"SH1X emission failed: {e}")
            raise
        size = builder.write_glb(out_path)
        report.update({"output": out_path, "bytes": size,
                       "meshes": builder.stats["meshes"],
                       "primitives": builder.stats["primitives"],
                       "materials": len(builder.json["materials"]),
                       "images": len(builder.json["images"]),
                       "nodes": len(builder.json["nodes"]),
                       "png_conversions": len(builder.json["images"])})
    # imported objects (verbatim cross-library geometry) into the report
    report["imported_objects"] = list(imported_seen.values())
    # tex_variants_struct is needed by the reconciliation below - build first
    report["tex_variants_struct"] = [
        {"tex": k[0], "pal_y": k[1], "stp": k[2],
         "h": int(v.shape[0]), "w": int(v.shape[1])}
        for k, v in report["tex_variants"].items()]
    # ---- billboard foliage (unk1 / field_10) table report ----
    # Every unk1 entry of every pos group, its cluster type, and the engine
    # semantics (decomp-verified Gfx_BillboardDraw ring).
    placed = {}
    for e in room.sub_objects:
        if e.get("cluster"):
            placed[e["cluster"]] = placed.get(e["cluster"], 0) + 1
    report["sub_objects"] = {
        "semantics": (
            "unk1 table of IPD_POS_HEADER (decompilation name: "
            "IpdModelBuffer.field_10): unk1_num entries x 8 bytes, each "
            "(s16 x, y, z, w) = one Q8 world-space ANCHOR for an engine-drawn "
            "camera-facing billboard foliage cluster; w selects the cluster "
            "(0 -> Gfx_BillboardDraw type 1: 12-quad tree canopy, 1 -> type 2: "
            "5-quad bush).  Verified against the Silent Hill decompilation "
            "(world_map.c WorldMap_Draw + gfx/billboard_draw.c D_800AE204: "
            "diamond size field_6/field_8 in FULL Q8 units - world half-width "
            "= field_6, per the libgte RotTransPers disassembly - ring "
            "offsets in Q8; bottom vertex at the ring position, apex "
            "2*half_h above).  The PLM libraries' LEAF_1/LEAF_2 triangles are "
            "NOT rendered by this path.  Legacy deviation: the legacy tool "
            "placed one LEAF_1 per TREE02 at the FIRST entry only.  Export "
            "policy (v10): the billboard rings are textured with the REAL "
            "engine texture TIM/BG_ETC.TIM (filetable 1799, loaded at boot "
            "into VRAM page 12 by GameFs_BgEtcGfxLoad; window u[0,63] "
            "v[128,191], CLUT row 2), auto-discovered "
            "by the standard resolver, or a --leaf-texture PNG override; only "
            "when neither is available are the foliage billboards DROPPED and "
            "every dropped anchor reported in leaf_billboards_dropped (there "
            "is NO LEAVES.TIM fallback)."),
        "pos_groups_with_table": sorted({e["group"] for e in room.sub_objects}),
        "entries": [dict(e) for e in room.sub_objects],
        "clusters_by_type": placed,
        # True only when the table had valid entries AND they were exported
        # (False either for empty tables or for the v6 drop policy - the
        # distinguishing evidence is the leaf_billboards_dropped block).
        "billboards_exported": bool(placed) and
        "leaf_billboards_dropped" not in report,
        "unplaced_entries": [e for e in room.sub_objects if not e.get("cluster")],
    }
    # ---- texture count reconciliation: what 'images' vs 'tex ok' MEAN ----
    # (meshes are scoped to THIS room's contribution: [s_meshes:] is all
    #  meshes in per-room mode, so default behavior is byte-identical; in
    #  whole-map mode materials may be shared with earlier rooms - their
    #  indices are correctly included via the material set)
    mats_used = set()
    for mesh in builder.json["meshes"][s_meshes:]:
        for prim in mesh["primitives"]:
            if "material" in prim:
                mats_used.add(prim["material"])
    assigned_images = set()
    for mi in mats_used:
        bct = builder.json["materials"][mi].get(
            "pbrMetallicRoughness", {}).get("baseColorTexture")
        if bct is not None:
            assigned_images.add(
                builder.json["textures"][bct["index"]]["source"])
    img_names = {i: builder.json["images"][i].get("name", "")
                 for i in sorted(assigned_images)}
    rec = report["texture_reconciliation"] = {
        "counters": {
            "tex_ok_distinct_tim_files": len(report["tex_ok"]),
            "tex_missing_distinct_names": len(report["tex_missing"]),
            "images_embedded": len(img_names),
            "images_actively_assigned": len(assigned_images & set(img_names)),
            "images_unused": sorted(img_names[i] for i in
                                     set(img_names) - assigned_images),
            "textures_created": len(builder.json["textures"]) - s_texs,
            "materials_created": len(builder.json["materials"]) - s_mats,
            "materials_used_by_primitives": len(mats_used),
        },
        "explanation": (
            "'tex ok' counts distinct source TIM files resolved and bound; "
            "'images' counts embedded PNGs, one per distinct (texture, "
            "palette row, stp) decoding used by geometry - one TIM can "
            "yield several images when several CLUT rows are referenced; "
            "an image named BILLBOARD_LEAF (present when billboard foliage "
            "anchors exist) is the real engine leaf texture TIM/BG_ETC.TIM "
            "(engine window u[0,63] v[128,191], CLUT row 2; auto-discovered) "
            "or the --leaf-texture override (not a room "
            "TIM); without either, the leaf billboards are dropped and no "
            "such image exists"
            + ("  WHOLE-MAP MODE: materials and PNGs are content-deduplicated "
                "across rooms, so materials_created/images here count THIS "
                "room's contribution; the distinct variant set is identical "
                "to a per-room file."
               if shared else "")),
        "texture_tables": {
            ("embedded" if lib is room.plm else lib.source_name): lib.tex_names
            for lib in ([room.plm, room.glb] if room.glb is not None
                        else [room.plm])},
        "referenced_texture_names": sorted(report["tex_referenced"]),
        "resolved_tim_files": sorted(report["tex_ok"]),
        "missing_tim_files": sorted(report["tex_missing"]),
        "images": [],
    }
    for i, name in img_names.items():
        parts = name.rsplit("_pal", 1)
        tex = parts[0] if parts else name
        pal = parts[1] if len(parts) > 1 else ""
        m_pal = None
        m_stp = False
        dims = None
        if pal:
            tail = pal.split("_")
            try:
                m_pal = int(tail[0])
            except ValueError:
                pass
            m_stp = "stp" in tail
        for v in report.get("tex_variants_struct", []):
            if (v["tex"] == tex and v["pal_y"] == m_pal
                    and bool(v["stp"]) == m_stp):
                dims = [v["w"], v["h"]]
                break
        rec["images"].append({
            "image": name, "source_tim": tex, "pal": m_pal, "stp": m_stp,
            "assigned": i in assigned_images, "dims": dims})
    # tex_variants_struct already built above; record the variant table
    report["texture_reconciliation"]["variants"] = [
        {**v, "image": f"{v['tex']}_pal{v['pal_y']}" + ("_stp" if v["stp"] else "")}
        for v in report["tex_variants_struct"]]
    report["tex_variants"] = {str(k): list(v.shape)
                              for k, v in report["tex_variants"].items()}
    for s in ("tex_referenced", "tex_ok", "tex_missing"):
        report[s] = sorted(report[s])
    report["tim_cache"] = {k: ("ok" if v is not None else "missing")
                           for k, v in report["tim_cache"].items()}
    if report["meshes"] == 0:
        report["problems"].append("empty room: no geometry exported")
    if report["degraded"]:
        report["problems"].append(
            f"{room.name}: {len(report['skipped_instances'])} instance(s) "
            f"skipped because referenced objects are unresolvable - export "
            f"DEGRADED (see skipped_instances)")
    return report


# ---------------------------------------------------------------------------
# whole-map export (--whole-map PREFIX): assembly, overlap & coverage proof
# ---------------------------------------------------------------------------
def room_prefix(stem):
    """Map prefix of a room stem: room names are PREFIX + 4 hex digits
    (signed-cell coordinates), e.g. APU0002 -> APU, THRF9FD -> THR, SC0304
    -> SC.  A stem without a 4-hex-digit tail is its own prefix."""
    if len(stem) > 4 and all(c in "0123456789abcdefABCDEF" for c in stem[-4:]):
        return stem[:-4].upper()
    return stem.upper()


# Max extent (meters) of world-AABB contact between rooms in ADJACENT map
# cells that is still classified as the expected shared-wall / threshold /
# lintel case rather than a suspicious overlap.  Cells are 10240 source
# units = 40.02 m; walls/thresholds are thin structures hugging the cell
# boundary.  Measured on the APU map (see whole-map report): all adjacent-
# cell contacts are below this value.
MAP_BOUNDARY_CONTACT_TOL_M = 1.0


def map_room_aabb(builder, node_idx):
    """Union world AABB (glTF meters) and mesh/prim counts of a room's node
    subtree.  All geometry nodes carry identity transforms (absolute
    map-grid coordinates are baked into the vertices; marker nodes have
    matrices but no mesh), so POSITION accessor min/max ARE world AABBs."""
    nodes = builder.json["nodes"]
    lo = hi = None
    meshes = prims = 0
    stack = [node_idx]
    while stack:
        n = nodes[stack.pop()]
        if "mesh" in n:
            meshes += 1
            for prim in builder.json["meshes"][n["mesh"]]["primitives"]:
                prims += 1
                acc = builder.json["accessors"][prim["attributes"]["POSITION"]]
                mn, mx = acc["min"], acc["max"]
                if lo is None:
                    lo, hi = list(mn), list(mx)
                else:
                    for k in range(3):
                        lo[k] = min(lo[k], mn[k])
                        hi[k] = max(hi[k], mx[k])
        stack.extend(n.get("children", ()))
    return lo, hi, meshes, prims


def analyze_map_overlap(prefix, rooms, room_reports, builder, validation):
    """'NO OVERLAPS' correctness proof for a whole-map export.

    (a) cell occupancy: every room must sit on its own signed map cell
        (x_pos, y_pos from the IPD header == file-name digits); two rooms
        on one cell would be STACKED - a loud validation error.
    (b) pairwise world AABBs: for rooms in ADJACENT cells the decisive
        metric is the PENETRATION along the cell-separation axes (x for
        horizontal neighbors, z for vertical, both for diagonal) - i.e. how
        deep the geometry crosses the shared cell boundary.  A shared
        boundary wall/threshold is thin in that direction (measured on the
        APU map: max 0.55 m) while its extent ALONG the wall (up to 36 m)
        is NOT an overlap; penetration beyond MAP_BOUNDARY_CONTACT_TOL_M,
        touching/overlap between NON-adjacent cells, or same-cell stacking
        is flagged loudly with the measured overlap box.
    (c) containment evidence: each room's geometry is expressed in its own
        cell-local source coordinates (corner-origin convention: local
        [0..~10246] per cell - measured geometry extent; the CELL STRIDE is
        the engine's 10240 = Q8(CHUNK_SIZE 40.0f), so rooms may legitimately
        poke a few units into neighbors) with the per-axis poke distances
        beyond the nominal cell, and must live predominantly (>= 50% per
        axis) inside its own cell - a room placed in the wrong cell lands
        almost entirely outside and is flagged.
    Returns the analysis dict (JSON-serializable)."""
    cells = {r.name: (int(r.x_pos), int(r.y_pos)) for r in rooms}
    occupancy = {}
    for name in sorted(cells):
        occupancy.setdefault(cells[name], []).append(name)
    stacked = {f"{c[0]},{c[1]}": names
               for c, names in sorted(occupancy.items()) if len(names) > 1}
    aabbs, local_ext, containment = {}, {}, {}
    cell_m = MAP_CELL * SCALE
    for rep in room_reports:
        lo, hi, _m, _p = map_room_aabb(builder, rep["map_parent_node"])
        aabbs[rep["room"]] = (lo, hi)
        cx, cy = cells[rep["room"]]
        # cell-local source extents (undo the map offset + axis flip):
        # gltf x = (x_local + cell*cx)/256, gltf z = -(z_local + cell*cy)/256
        if lo is not None:
            lx = [lo[0] * 256 - cx * MAP_CELL, hi[0] * 256 - cx * MAP_CELL]
            lz = [-hi[2] * 256 - cy * MAP_CELL, -lo[2] * 256 - cy * MAP_CELL]
            local_ext[rep["room"]] = {
                "x_units": [round(v, 1) for v in lx],
                "z_units": [round(v, 1) for v in lz],
            }
            # containment: majority of each axis' extent inside the own
            # cell rect [0..MAP_CELL] (corner-origin convention; measured
            # room geometry spans up to ~10246 units > the 10240 stride,
            # hence small legitimate pokes);
            # poke = how far geometry reaches beyond the nominal cell
            def _frac(rng):
                inter = min(rng[1], MAP_CELL) - max(rng[0], 0.0)
                return max(0.0, inter) / max(rng[1] - rng[0], 1e-9)
            containment[rep["room"]] = {
                "inside_fraction_x": round(_frac(lx), 4),
                "inside_fraction_z": round(_frac(lz), 4),
                "poke_units": {
                    "x_neg": round(min(lx[0], 0.0), 1),
                    "x_pos": round(max(lx[1] - MAP_CELL, 0.0), 1),
                    "z_neg": round(min(lz[0], 0.0), 1),
                    "z_pos": round(max(lz[1] - MAP_CELL, 0.0), 1)},
            }
    names = sorted(aabbs)
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            (lo1, hi1), (lo2, hi2) = aabbs[names[i]], aabbs[names[j]]
            if lo1 is None or lo2 is None:
                continue
            dims = [min(hi1[k], hi2[k]) - max(lo1[k], lo2[k])
                    for k in range(3)]
            if any(d < -1e-9 for d in dims):
                continue          # strictly disjoint
            # boxes touch or overlap (a zero-dim intersection = touching,
            # including fully coincident flat geometry - still a placement
            # fact to classify, never silently ignored)
            touch_only = any(d <= 1e-9 for d in dims)
            c1, c2 = cells.get(names[i]), cells.get(names[j])
            dc = (abs(c1[0] - c2[0]), abs(c1[1] - c2[1]))
            # penetration = overlap along the cell-separation axes only:
            # x (axis 0) for horizontal separation, z (axis 2) for vertical;
            # the extent along a shared boundary WALL (the other axes) is
            # not an overlap (a 36 m long, 0.02 m thick wall is a wall)
            sep_axes = [k for k, d in ((0, dc[0]), (2, dc[1])) if d]
            penetration = max((dims[k] for k in sep_axes), default=0.0)
            extent = max(dims)
            if dc == (0, 0):
                cls, verdict = "STACKED_SAME_CELL", "defect"
            elif touch_only:
                cls = ("ADJACENT_CELL_TOUCH" if max(dc) == 1
                       else "NON_ADJACENT_TOUCH")
                verdict = ("expected-boundary" if max(dc) == 1 else "flagged")
            elif max(dc) == 1:
                if penetration <= MAP_BOUNDARY_CONTACT_TOL_M:
                    cls, verdict = "ADJACENT_CELL_CONTACT", "expected-boundary"
                else:
                    cls, verdict = "ADJACENT_CELL_LARGE_OVERLAP", "flagged"
            else:
                cls, verdict = "NON_ADJACENT_OVERLAP", "flagged"
            pairs.append({
                "room_a": names[i], "room_b": names[j],
                "cell_a": list(c1), "cell_b": list(c2),
                "overlap_dims_m": [round(d, 4) for d in dims],
                "max_extent_m": round(extent, 4),
                "penetration_m": round(penetration, 4),
                "separation_axes": ["x" if k == 0 else "z" for k in sep_axes],
                "class": cls, "verdict": verdict,
            })
    n_contact = sum(1 for p in pairs
                    if p["class"] in ("ADJACENT_CELL_CONTACT",
                                      "ADJACENT_CELL_TOUCH"))
    n_flag = sum(1 for p in pairs if p["verdict"] == "flagged")
    result = {
        "cell_size_m": round(cell_m, 4),
        "tolerance_m": MAP_BOUNDARY_CONTACT_TOL_M,
        "room_cells": {n: list(cells[n]) for n in sorted(cells)},
        "cell_occupancy": {f"{c[0]},{c[1]}": names
                           for c, names in sorted(occupancy.items())},
        "stacked_cells": stacked,
        "room_world_aabbs_m": {n: {"min": [round(v, 3) for v in aabbs[n][0]],
                                    "max": [round(v, 3) for v in aabbs[n][1]]}
                               for n in names if aabbs[n][0] is not None},
        "room_local_extents_source_units": local_ext,
        "room_containment": containment,
        "pairwise_overlaps": pairs,
        "summary": {
            "rooms": len(names),
            "distinct_cells": len(occupancy),
            "stacked_cells": len(stacked),
            "touching_or_overlapping_pairs": len(pairs),
            "adjacent_boundary_contact_pairs": n_contact,
            "flagged_pairs": n_flag,
            "disjoint_pairs": len(names) * (len(names) - 1) // 2 - len(pairs),
            "verdict": (
                "NO OVERLAPS: every room on its own map cell, no stacked "
                "rooms, no flagged pairwise geometry overlaps (touching "
                "or thin contacts only at adjacent-cell boundaries)"
                if not stacked and not n_flag
                else "OVERLAP DEFECTS PRESENT - see stacked_cells / "
                     "pairwise_overlaps"),
        },
    }
    if stacked:
        validation["errors"].append(
            f"{prefix} map: rooms STACKED on shared map cells: {stacked}")
    for p in pairs:
        if p["verdict"] == "flagged":
            validation["warnings"].append(
                f"{prefix} map: {p['class']} between {p['room_a']} "
                f"(cell {p['cell_a']}) and {p['room_b']} (cell {p['cell_b']}): "
                f"overlap {p['overlap_dims_m']} m, boundary penetration "
                f"{p['penetration_m']} m along {p['separation_axes']}")
    for n, c in sorted(containment.items()):
        if c["inside_fraction_x"] < 0.5 or c["inside_fraction_z"] < 0.5:
            validation["warnings"].append(
                f"{prefix} map: {n} (cell {cells.get(n)}) geometry lives "
                f"mostly OUTSIDE its own map cell (inside fractions "
                f"x={c['inside_fraction_x']}, z={c['inside_fraction_z']}) "
                f"- placement suspect")
    return result


def map_coverage(prefix, rooms, tree):
    """Which rooms of this map exist in the input vs the original rip
    (--tree listing).  A partial map is documented loudly, never silently
    presented as complete."""
    have = sorted(r.name for r in rooms)
    orig = []
    if tree is not None:
        for fname in tree.files:
            stem, ext = os.path.splitext(fname)
            if ext.upper() != ".IPD":
                continue
            if room_prefix(stem) == prefix:
                orig.append(stem.upper())
        orig = sorted(set(orig))
    missing = sorted(set(orig) - set(have))
    extra = sorted(set(have) - set(orig))
    if tree is None:
        note = ("completeness unknown: no --tree original-rip listing given "
                f"({len(have)} room(s) exported)")
        complete = None            # unknown, honestly reported as null
    elif not orig:
        note = ("no rooms of this map prefix in the original rip listing "
                "(prefix unknown to the tree) - completeness unknown")
        complete = None
    elif not missing and not extra:
        note = f"complete: all {len(orig)} original-rip rooms present"
        complete = True
    else:
        note = (f"PARTIAL map: {len(missing)} of {len(orig)} original-rip "
                f"rooms are absent from the input directory - the exported "
                f"map covers only the provided material (never silently "
                f"passed off as complete)")
        complete = False
    return {
        "rooms_in_input": have,
        "rooms_in_original_rip": orig,
        "missing_from_input": missing,
        "present_but_not_in_rip_listing": extra,
        "complete": complete,
        "note": note,
        "tree_evidence": ("dir_list.txt (original rip layout)"
                         if tree is not None else
                         "none (--tree not given): completeness unknown"),
    }


# ---------------------------------------------------------------------------
# validation harness (self-audit)
# ---------------------------------------------------------------------------
def validate_glb(path, tex_aliases=None):
    """Structural + semantic self-validation of a GLB file. Returns checks dict.

    tex_aliases: optional mapping {TIM stem UPPER -> set of TIM stems whose
    FILE CONTENT is byte-identical}.  Content-identical TIMs discovered
    under different names (e.g. APU01F.TIM == APUMGR2F.TIM, sha1-equal)
    legitimately share ONE embedded PNG in whole-map exports, so a material
    named after one alias may be bound to an image named after another -
    the binding is still exact.  Without the alias map (per-room default)
    the material-image name check is strict, exactly as in previous
    audited versions."""
    checks = {"path": path, "errors": [], "warnings": []}
    ok = lambda name: checks.setdefault("passed", []).append(name)
    data = open(path, "rb").read()
    if len(data) < 12:
        checks["errors"].append("file < 12 bytes")
        return checks
    magic, ver, total = struct.unpack_from("<III", data, 0)
    if magic != GLTF_MAGIC:
        checks["errors"].append(f"bad magic 0x{magic:X}")
        return checks
    if ver != 2:
        checks["errors"].append(f"glTF version {ver}")
    if total != len(data):
        checks["errors"].append(f"header length {total} != file size {len(data)}")
    ok("container header")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    if jtype != CHUNK_JSON:
        checks["errors"].append("first chunk not JSON")
        return checks
    js = data[20:20 + jlen]
    try:
        doc = json.loads(js.decode("utf-8"))
    except Exception as e:
        checks["errors"].append(f"JSON parse: {e}")
        return checks
    ok("JSON parse")
    bin_data = b""
    off = 20 + jlen
    if off + 8 <= len(data):
        blen, btype = struct.unpack_from("<II", data, off)
        if btype != CHUNK_BIN:
            checks["errors"].append("second chunk not BIN")
        else:
            bin_data = data[off + 8: off + 8 + blen]
            if off + 8 + blen != len(data):
                checks["errors"].append("BIN chunk length mismatch")
            if blen % 4:
                checks["warnings"].append("BIN length not multiple of 4")
    ok("chunks")
    buf = doc.get("buffers", [])
    if not buf or buf[0].get("byteLength") != len(bin_data):
        checks["errors"].append("buffer[0].byteLength != BIN size")
    ok("buffer")
    views = doc.get("bufferViews", [])
    for i, v in enumerate(views):
        if v["buffer"] != 0:
            checks["errors"].append(f"bufferView {i}: buffer != 0")
        if v["byteOffset"] + v["byteLength"] > len(bin_data):
            checks["errors"].append(f"bufferView {i}: out of buffer")
        if v["byteOffset"] % 4:
            checks["warnings"].append(f"bufferView {i}: byteOffset not 4-aligned")
    ok("bufferViews")
    accs = doc.get("accessors", [])
    sizes = {5126: 4, 5123: 2, 5121: 1, 5125: 4}
    ncomps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    for i, a in enumerate(accs):
        csz = sizes.get(a["componentType"], 0)
        nc = ncomps.get(a["type"], 0)
        if csz == 0 or nc == 0:
            checks["errors"].append(f"accessor {i}: bad type")
            continue
        need = a["count"] * csz * nc
        v = views[a["bufferView"]]
        if a.get("byteOffset", 0) % csz:
            checks["errors"].append(f"accessor {i}: byteOffset misaligned")
        if v["byteOffset"] + a.get("byteOffset", 0) + need > v["byteOffset"] + v["byteLength"]:
            checks["errors"].append(f"accessor {i}: exceeds bufferView")
        if a.get("byteOffset", 0) and a.get("bufferView") is None:
            checks["errors"].append(f"accessor {i}: sparse/byteOffset without view")
        # verify min/max for POSITION
        if a["type"] == "VEC3" and a["componentType"] == 5126 and "min" in a:
            arr = np.frombuffer(bin_data, dtype="<f4", count=a["count"] * 3,
                                offset=views[a["bufferView"]]["byteOffset"] +
                                a.get("byteOffset", 0)).reshape(-1, 3)
            if (np.abs(arr.min(axis=0) - np.array(a["min"])).max() > 1e-6 or
                    np.abs(arr.max(axis=0) - np.array(a["max"])).max() > 1e-6):
                checks["errors"].append(f"accessor {i}: min/max mismatch")
        if a["type"] == "VEC3" and a["componentType"] == 5126 and "min" not in a \
                and i in [p["attributes"].get("POSITION", -1) for m in doc.get("meshes", [])
                          for p in m["primitives"]]:
            checks["errors"].append(f"accessor {i}: POSITION without min/max")
    ok("accessors")
    # indices < vertex count; degenerate faces
    for mi, m in enumerate(doc.get("meshes", [])):
        for pi, p in enumerate(m["primitives"]):
            if p.get("mode", 4) != 4:
                checks["errors"].append(f"mesh {mi} prim {pi}: mode != 4")
            pos_acc = p["attributes"].get("POSITION")
            nrm_acc = p["attributes"].get("NORMAL")
            uv_acc = p["attributes"].get("TEXCOORD_0")
            if pos_acc is None:
                checks["errors"].append(f"mesh {mi} prim {pi}: no POSITION")
                continue
            nv = accs[pos_acc]["count"]
            if nrm_acc is None:
                checks["warnings"].append(f"mesh {mi} prim {pi}: no NORMAL")
            else:
                n = np.frombuffer(bin_data, dtype="<f4", count=accs[nrm_acc]["count"] * 3,
                                  offset=views[accs[nrm_acc]["bufferView"]]["byteOffset"] +
                                  accs[nrm_acc].get("byteOffset", 0)).reshape(-1, 3)
                mag = np.linalg.norm(n.astype(np.float64), axis=1)
                if np.any(np.abs(mag - 1) > 0.01):
                    checks["errors"].append(
                        f"mesh {mi} prim {pi}: non-unit normals (max dev "
                        f"{np.abs(mag - 1).max():.4f})")
            if uv_acc is not None:
                u = np.frombuffer(bin_data, dtype="<f4", count=accs[uv_acc]["count"] * 2,
                                  offset=views[accs[uv_acc]["bufferView"]]["byteOffset"] +
                                  accs[uv_acc].get("byteOffset", 0)).reshape(-1, 2)
                if u.size and (u.min() < -1e-6 or u.max() > 1 + 1e-6):
                    checks["warnings"].append(
                        f"mesh {mi} prim {pi}: UV out of [0,1] "
                        f"[{u.min():.3f},{u.max():.3f}]")
            iacc = p["indices"]
            idx = np.frombuffer(bin_data, dtype="<u2", count=accs[iacc]["count"],
                                offset=views[accs[iacc]["bufferView"]]["byteOffset"] +
                                accs[iacc].get("byteOffset", 0))
            if idx.size and idx.max() >= nv:
                checks["errors"].append(f"mesh {mi} prim {pi}: index >= vertex count")
            # ---- v11: the EMISSION CONTRACT self-check -------------------
            # Walk this primitive's index stream with the consumer's exact
            # quad reconstruction (fog_poc.c: isQuad iff
            # idx[k+3]==idx[k+1] && idx[k+5]==idx[k+2]) and count what the
            # consumer would reconstruct.  A v11 export must show ZERO lone
            # triangles (every IPD pack — real quad, f3==0xFF triangle or
            # f3==f2 degenerate — is emitted as a reconstructable pair).
            # Engine-degenerate second triangles (the f3==f2 GT4 case) are
            # detected by POSITION equality of the D and C corners (their
            # indices differ — the shared vertex carries its own UV corner
            # slot, exactly as the GT4 assigns attributes per corner).
            posacc = accs[pos_acc]
            pos_arr = np.frombuffer(
                bin_data, dtype="<f4", count=posacc["count"] * 3,
                offset=views[posacc["bufferView"]]["byteOffset"] +
                posacc.get("byteOffset", 0)).reshape(-1, 3)
            k = 0
            n_quad = n_degen_quad = n_lone = 0
            while k + 2 < idx.size:
                is_quad = (k + 5 < idx.size and
                           idx[k + 3] == idx[k + 1] and idx[k + 5] == idx[k + 2])
                if is_quad:
                    n_quad += 1
                    # engine-degenerate (f3==f2): the D corner (idx[k+4],
                    # the f2 vertex with uv corner 3) sits at the SAME
                    # POSITION as the B corner (idx[k+1], the f2 vertex with
                    # uv corner 2) — the second triangle is zero-area
                    if (idx[k + 4] < nv and idx[k + 1] < nv and
                            np.allclose(pos_arr[idx[k + 4]],
                                        pos_arr[idx[k + 1]], atol=1e-9)):
                        n_degen_quad += 1   # engine f3==f2: zero-area tri2
                    k += 6
                else:
                    n_lone += 1
                    k += 3
            checks.setdefault("emission_contract", {"quads": 0,
                                                    "degenerate_quads": 0,
                                                    "lone_triangles": 0})
            checks["emission_contract"]["quads"] += n_quad
            checks["emission_contract"]["degenerate_quads"] += n_degen_quad
            checks["emission_contract"]["lone_triangles"] += n_lone
            if n_lone:
                checks["errors"].append(
                    f"mesh {mi} prim {pi}: {n_lone} LONE triangles the "
                    f"consumer's quad reconstruction CANNOT match — the "
                    f"ordering-table per-quad semantics (bucket = max of 4 "
                    f"vertex depths, per-quad far cull, dual-nclip cull) "
                    f"degrade to the flickering per-triangle path for them")
            # repeated-index degenerates are NEVER intentional in v11 (the
            # engine-degenerate second triangle uses a distinct index)
            tri = idx.reshape(-1, 3)
            deg = int(np.sum((tri[:, 0] == tri[:, 1]) | (tri[:, 1] == tri[:, 2]) |
                             (tri[:, 0] == tri[:, 2])))
            if deg:
                checks["warnings"].append(
                    f"mesh {mi} prim {pi}: {deg} repeated-index degenerate "
                    f"tris (not the engine's f3==f2 pattern, which uses a "
                    f"distinct index at the same position)")
    ok("meshes")
    ec = checks.get("emission_contract")
    if ec is not None:
        total = ec["quads"] + ec["lone_triangles"]
        if total:
            ok(f"emission contract: {ec['quads']}/{total} quads reconstruct "
               f"({100.0 * ec['quads'] / total:.1f}%), "
               f"{ec['degenerate_quads']} engine-degenerate, "
               f"{ec['lone_triangles']} lone")
    # ---- v12: the LAYERING CONTRACT self-check ----------------------------
    # Walk the node graph (consumer order, extras.ot_base inherited down),
    # rebuild every quad in WORLD space, find all same-facing plane-
    # coincident OVERLAPPING pairs (sep <= 32 mm = the engine's OT bucket
    # width), and require the ENGINE winner (min(ot_base, add order)) to be
    # strictly NEAREST for every pair — the depth-buffer composite must
    # equal the engine's painter composite.  Ties/inversions here are
    # exactly the "flickering in and out of existence" surfaces in stock
    # z-buffered viewers (three.js).
    if doc.get("scenes") and doc.get("nodes"):
        lq = []

        def _vl_node_local(nd):
            if "matrix" in nd:
                return np.array(nd["matrix"], dtype=np.float64).reshape(4, 4).T
            tr = nd.get("translation", [0, 0, 0])
            qv = nd.get("rotation", [0, 0, 0, 1])
            sc = nd.get("scale", [1, 1, 1])
            x, y, z, w = qv
            rm = np.array([
                [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]],
                dtype=np.float64)
            for c in range(3):
                rm[:, c] *= sc[c]
            M = np.eye(4)
            M[:3, :3] = rm
            M[:3, 3] = tr
            return M

        def _vl_walk(ni, parent, base):
            nd = doc["nodes"][ni]
            ex = nd.get("extras")
            if isinstance(ex, dict) and isinstance(ex.get("ot_base"), int):
                base = ex["ot_base"]
            M = parent @ _vl_node_local(nd)
            if "mesh" in nd:
                msh = doc["meshes"][nd["mesh"]]
                for p in msh.get("primitives", []):
                    pa = p["attributes"].get("POSITION")
                    if pa is None or "indices" not in p:
                        continue
                    pv = np.frombuffer(
                        bin_data, dtype="<f4", count=accs[pa]["count"] * 3,
                        offset=views[accs[pa]["bufferView"]]["byteOffset"] +
                        accs[pa].get("byteOffset", 0)).reshape(-1, 3)
                    iv = np.frombuffer(
                        bin_data, dtype="<u2", count=accs[p["indices"]]["count"],
                        offset=views[accs[p["indices"]]["bufferView"]]
                        ["byteOffset"] + accs[p["indices"]].get("byteOffset", 0))
                    k = 0
                    while k + 5 < len(iv):
                        if not (iv[k + 3] == iv[k + 1] and
                                iv[k + 5] == iv[k + 2]):
                            k += 3
                            continue
                        vi = (iv[k], iv[k + 1], iv[k + 2], iv[k + 4])
                        wp = [M[:3, :3] @ pv[v] + M[:3, 3] for v in vi]
                        a, b, c = wp[0], wp[1], wp[2]
                        nq = np.cross(b - a, c - a)
                        nl = float(np.linalg.norm(nq))
                        if nl > 1e-9:
                            lq.append({"w": wp, "n": nq / nl, "base": base,
                                       "seq": len(lq),
                                       "node": nd.get("name", "")})
                        k += 6
            for ch in nd.get("children", []):
                _vl_walk(ch, M, base)

        for rn in doc["scenes"][0].get("nodes", []):
            _vl_walk(rn, np.eye(4), None)
        n_tie = n_bad = 0
        bad_pairs = []
        for i in range(len(lq)):
            for j in range(i + 1, len(lq)):
                qi, qj = lq[i], lq[j]
                if float(qi["n"].dot(qj["n"])) < 0.99:
                    continue
                n0, p0 = qi["n"], qi["w"][0]
                d1 = max(abs(float(n0.dot(v - p0))) for v in qj["w"])
                n1, p1 = qj["n"], qj["w"][0]
                d2 = max(abs(float(n1.dot(v - p1))) for v in qi["w"])
                if max(d1, d2) > 0.032:
                    continue
                e1, e2 = _layer_plane_basis(qi["n"])
                Pi = _layer_hull2([(float(np.dot(e1, p)), float(np.dot(e2, p)))
                                   for p in qi["w"]])
                Pj = _layer_hull2([(float(np.dot(e1, p)), float(np.dot(e2, p)))
                                   for p in qj["w"]])
                if _layer_clip_area(Pi, Pj) <= 1e-9:
                    continue
                ka, kb = (qi["base"], qi["seq"]), (qj["base"], qj["seq"])
                wn, ls = (qi, qj) if ka <= kb else (qj, qi)
                # CROSSING surfaces (EITHER quad's corners straddle the
                # other's plane) are per-pixel-resolved by any z-buffer —
                # not a layering pair (measured: THR7203 branch panels).
                sdist = [float(wn["n"].dot(v - wn["w"][0])) for v in ls["w"]]
                sdist_r = [float(ls["n"].dot(v - ls["w"][0])) for v in wn["w"]]
                if ((min(sdist) < -0.0002 and max(sdist) > 0.0002) or
                        (min(sdist_r) < -0.0002 and max(sdist_r) > 0.0002)):
                    continue
                n_tie += 1
                # v14 CONTRACT CHANGE: with the layer-separation pass
                # REMOVED (geometry stays authored — the z-offset recession
                # caused corner seams, user report), coincident pairs in a
                # z-buffered viewer are EXPECTED, not errors.  The
                # engine-exact composite is produced by the SH1X painter
                # consumer (OT bases + add order), NOT by depth.  This
                # check now only counts and DOCUMENTS them (informational).
                gap = max(sdist)
                if gap > 0:
                    checks.setdefault("layering_inverted_stable", []).append(
                        f"{wn['node']} over {ls['node']}: "
                        f"{gap * 1000.0:+.2f} mm (stable, no flicker)")
                checks.setdefault("layering_coincident_documented", []).append(
                    f"{wn['node']}(ot{wn['base']}) over "
                    f"{ls['node']}(ot{ls['base']}): {gap * 1000.0:+.2f} mm "
                    f"— resolved by the SH1X painter, depth-ambiguous only "
                    f"in stock z-buffer viewers (expected, documented)")
        checks["layering_contract"] = {
            "coincident_overlapping_pairs": n_tie, "violations": 0,
            "note": ("v14: coincident pairs are EXPECTED — geometry is "
                     "authored (no separation); the engine composite is "
                     "reproduced by the SH1X painter consumer from extras, "
                     "not by depth.  Pairs are documented in "
                     "layering_coincident_documented.")}
        ok(f"layering contract (v14): {n_tie} coincident pairs documented — "
           f"authored geometry, SH1X painter resolves them")

    # images are PNG
    for i, im in enumerate(doc.get("images", [])):
        v = views[im["bufferView"]]
        blob = bin_data[v["byteOffset"]: v["byteOffset"] + v["byteLength"]]
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            checks["errors"].append(f"image {i}: not a PNG")
        if im.get("mimeType") != "image/png":
            checks["errors"].append(f"image {i}: wrong mimeType")
    ok("images")
    # embedded texture validation: decode every PNG, record dims/alpha, and
    # verify each textured material is bound to an image of the SAME texture
    if HAS_PIL:
        import io as _io2
        emb = checks.setdefault("embedded_images", [])
        for i, im in enumerate(doc.get("images", [])):
            v = views[im["bufferView"]]
            blob = bin_data[v["byteOffset"]: v["byteOffset"] + v["byteLength"]]
            try:
                img = Image.open(_io2.BytesIO(blob))
                img.load()
            except Exception as e:
                checks["errors"].append(f"image {i}: PNG decode failed: {e}")
                emb.append({"name": im.get("name", ""), "error": str(e)})
                continue
            rec = {"name": im.get("name", ""), "width": img.size[0],
                   "height": img.size[1], "mode": img.mode}
            arr = np.asarray(img)
            if arr.ndim == 3 and arr.shape[-1] == 4:
                rec["has_partial_alpha"] = bool((arr[..., 3] < 255).any())
                rec["fully_transparent"] = bool((arr[..., 3] == 0).all())
            emb.append(rec)
        ok("embedded texture decode")
        for mi, m in enumerate(doc.get("materials", [])):
            bct = m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
            if bct is None:
                continue
            im_i = doc["textures"][bct["index"]]["source"]
            iname = doc["images"][im_i].get("name", "")
            mname = m.get("name", "")
            if mname.startswith("BILLBOARD_LEAF"):
                # user-supplied real engine billboard texture (not a
                # TIM-derived material): alpha presence still applies below
                pass
            else:
                tex_img = iname.split("_pal")[0].lower()
                tex_mat = mname.split("_pal")[0].lower()
                alias_ok = (tex_aliases is not None and
                            tex_img.upper() in tex_aliases.get(
                                tex_mat.upper(), ()))
                if tex_img != tex_mat and not alias_ok:
                    checks["errors"].append(
                        f"material {mi} ({mname!r}) bound to image {im_i} "
                        f"({iname!r}) of a DIFFERENT texture")
                elif tex_img != tex_mat:
                    checks.setdefault("tex_alias_bindings", []).append(
                        f"material {mi} ({mname!r}) -> image {im_i} "
                        f"({iname!r}): content-identical TIM alias "
                        f"(byte-equal source files, verified)")
            if m.get("alphaMode") == "BLEND":
                if im_i >= len(emb) or not emb[im_i].get("has_partial_alpha"):
                    checks["errors"].append(
                        f"material {mi} ({mname!r}): BLEND alphaMode but "
                        f"image {im_i} has no partial alpha")
            if m.get("alphaMode") == "MASK":
                if im_i >= len(emb) or not (
                        emb[im_i].get("has_partial_alpha")
                        or emb[im_i].get("fully_transparent")):
                    checks["errors"].append(
                        f"material {mi} ({mname!r}): MASK alphaMode but "
                        f"image {im_i} has no alpha variation")
        ok("material-image binding")
    # texture/image count reconciliation: every texture must be referenced by
    # a material, every image by a texture, and every material by a primitive
    ref_tex = set()
    for m in doc.get("materials", []):
        bct = m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
        if bct is not None:
            ref_tex.add(bct["index"])
    unused_tex = [i for i in range(len(doc.get("textures", [])))
                  if i not in ref_tex]
    if unused_tex:
        checks["warnings"].append(
            f"{len(unused_tex)} texture entries not referenced by any material: "
            f"{unused_tex}")
    ref_imgs = {tx["source"] for tx in doc.get("textures", [])}
    unused_img = [i for i in range(len(doc.get("images", [])))
                  if i not in ref_imgs]
    if unused_img:
        checks["warnings"].append(
            f"{len(unused_img)} images not referenced by any texture: {unused_img}")
    mats_in_use = set()
    for m in doc.get("meshes", []):
        for p in m.get("primitives", []):
            if "material" in p:
                mats_in_use.add(p["material"])
    orphan_mats = sorted(set(range(len(doc.get("materials", [])))) - mats_in_use)
    if orphan_mats:
        checks["warnings"].append(
            f"{len(orphan_mats)} materials not used by any primitive: {orphan_mats}")
    checks["texture_reconciliation"] = {
        "images": len(doc.get("images", [])),
        "textures": len(doc.get("textures", [])),
        "samplers": len(doc.get("samplers", [])),
        "materials": len(doc.get("materials", [])),
        "materials_used_by_primitives": len(mats_in_use),
        "images_referenced_by_textures": len(ref_imgs),
    }
    ok("texture reconciliation")
    # scene graph reachability
    nodes = doc.get("nodes", [])
    scene_nodes = set(doc["scenes"][doc["scene"]]["nodes"])
    seen = set()

    def walk(ni):
        if ni in seen:
            checks["errors"].append(f"node cycle at {ni}")
            return
        seen.add(ni)
        for c in nodes[ni].get("children", []):
            walk(c)
    for n in scene_nodes:
        walk(n)
    for ni, n in enumerate(nodes):
        if ni not in seen:
            checks["warnings"].append(f"node {ni} unreachable from scene")
        if "mesh" in n:
            if not (0 <= n["mesh"] < len(doc["meshes"])):
                checks["errors"].append(f"node {ni}: mesh index OOB")
    ok("scene graph")
    return checks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Convert Silent Hill 1 .IPD room files to per-room glTF/GLB "
                    "with embedded textures.  Textures are discovered by "
                    "recursively scanning the --input directory and every "
                    "--search-roots directory (case-insensitive, including "
                    "inside ZIP archives, nested zips included).")
    ap.add_argument("--input", required=True, help="directory containing .IPD files")
    ap.add_argument("--output", required=True, help="output directory for GLB files")
    ap.add_argument("--search-roots", action="append", default=[], metavar="DIR",
                    help="additional directory root scanned RECURSIVELY for TIM "
                         "textures (repeatable; every archive found inside is "
                         "scanned too; the --input dir is always scanned)")
    ap.add_argument("--textures", action="append", default=[], metavar="DIR",
                    help=argparse.SUPPRESS)      # legacy alias for --search-roots
    ap.add_argument("--tree", default="", metavar="FILE",
                    help="directory listing (dir_list.txt) of the original rip, "
                         "used as virtual-tree resolution evidence: folder "
                         "hints for path matching and original locations for "
                         "missing-texture reporting")
    ap.add_argument("--exclude", action="append", default=[], metavar="PATH",
                    help="path excluded from texture scanning (repeatable; the "
                         "output directory is always excluded)")
    ap.add_argument("--rooms", default="", help="comma-separated room names to process")
    ap.add_argument("--whole-map", action="append", default=[], metavar="PREFIX",
                    help="export ONE combined GLB per map instead of per-room "
                         "GLBs (NOT the default).  PREFIX is the exact map "
                         "prefix of room names (rooms are named PREFIX + 4 "
                         "hex digits = the map's room sequence, e.g. SC0000.."
                         "SC0304 for the SC map, APU0000..APUFFFF for the "
                         "apartment/AP map); every room of that map is placed "
                         "at the ENGINE map-grid world position (CHUNK_SIZE "
                         "10240 * signed cell, decomp terrain.h) in a single "
                         "<PREFIX>_MAP.glb, one "
                         "identity-transform root node per room.  Overlap and "
                         "coverage proofs are computed and recorded (no two "
                         "rooms may share a map cell; original-rip room "
                         "coverage via --tree).  Repeatable and comma-"
                         "separated.  The DEFAULT (without this flag) is "
                         "unchanged: one self-contained GLB per room.")
    ap.add_argument("--include-unused", action="store_true",
                    help="also export unplaced PLM meshes under UNPLACED_MESHES node")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and report only, write no GLB files")
    ap.add_argument("--report", default="", help="write JSON audit report to this path")
    ap.add_argument("--texture-report", default="",
                    help="write the JSON texture discovery + resolution report")
    ap.add_argument("--untextured-color", default="", metavar="RRGGBB",
                    help="override the neutral placeholder color of untextured "
                         "polys (pack tex_num=0x7F: ladders, foliage leaves, "
                         "table legs...). The in-game color is engine-supplied "
                         "and absent from the provided files; default 808080. "
                         "Example: --untextured-color 2A3A22 for dark foliage.")
    ap.add_argument("--plm-report", default="",
                    help="write the JSON PLM archive index + object-reference "
                         "resolution report (archives scanned, entries "
                         "indexed, resolved/unresolved references, skipped "
                         "instances with justification)")
    ap.add_argument("--leaf-texture", default="", metavar="PNG",
                    help="OPTIONAL override for the billboard foliage texture: "
                         "a PNG extraction of the engine texture.  By default "
                         "(v10) the converter AUTO-DISCOVERS the real engine "
                         "file TIM/BG_ETC.TIM (filetable 1799; loaded at boot "
                         "into VRAM page 12 by GameFs_BgEtcGfxLoad; sampled "
                         "by Gfx_BillboardDraw at tpage 44, clut 140 = CLUT "
                         "row 2, window u[0,63] v[128,191] of the 128x256 "
                         "sheet) through the standard texture resolver and "
                         "textures the engine-exact rings with it; this flag "
                         "replaces the discovered TIM.  If NEITHER is "
                         "available the leaf billboards are DROPPED and "
                         "loudly reported (NO TEST/LEAVES.TIM fallback - "
                         "that file is referenced by no decompiled code).")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    # --untextured-color: parse RRGGBB into the module-level neutral
    if getattr(args, "untextured_color", ""):
        h = args.untextured_color.strip().lstrip("#")
        if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
            ap.error(f"--untextured-color must be 6 hex digits (got {h!r})")
        global UNTEXTURED_COLOR
        UNTEXTURED_COLOR = tuple(int(h[k:k + 2], 16) / 255.0
                                 for k in (0, 2, 4))
        logging.getLogger("ipd2gltf").info(
            "untextured polys placeholder color overridden: %s", h.upper())

    in_dir = os.path.abspath(args.input)
    out_dir = os.path.abspath(args.output)
    os.makedirs(out_dir, exist_ok=True)
    roots = [in_dir] + list(args.search_roots) + list(args.textures)
    roots = list(dict.fromkeys(os.path.abspath(r) for r in roots if r))
    excludes = list(dict.fromkeys(
        [out_dir] + [os.path.abspath(e) for e in args.exclude if e]))
    tree = None
    if args.tree:
        tree = VirtualTree(args.tree)
        log.info("virtual tree loaded: %s (%d lines, %d files indexed)",
                 tree.path, tree.lines, len(tree.files))
    resolver = TextureResolver(roots, tree=tree, exclude_prefixes=excludes)
    if getattr(args, "leaf_texture", ""):
        resolver.leaf_texture_path = args.leaf_texture
    tims = resolver.registry.tim_stats()
    log.info("TIM discovery: %d TIM entries, %d unique by content, "
             "%d duplicate entries ignored, %d folders scanned, %d archives",
             tims["tim_files_found"], tims["tim_unique_by_content"],
             tims["tim_duplicate_entries_ignored"],
             resolver.discovery_stats["folders_scanned"],
             len(resolver.discovery_stats["archives_scanned"]))
    # content-identical TIM alias groups: byte-equal TIM files discovered
    # under different names (e.g. APU01F.TIM == APUMGR2F.TIM in the provided
    # pack - same sha1).  Whole-map image dedup then legitimately binds a
    # material named after one alias to an image named after another; the
    # binding is still content-exact.  Groups feed validate_glb and the
    # embedded-image dimension cross-checks.
    tex_aliases = {}
    for _sha, ents in resolver.registry.by_hash.items():
        stems = {os.path.splitext(os.path.basename(e.vpath))[0].upper()
                 for e in ents if e.ext == ".TIM"}
        if len(stems) > 1:
            for s in stems:
                tex_aliases.setdefault(s, set()).update(stems)
    if tex_aliases:
        log.info("TIM content aliases: %d group(s) of byte-identical TIM "
                 "files under different names (%s)", len(tex_aliases),
                 "; ".join(sorted("=".join(sorted(v)) for v in
                               {frozenset(v) for v in tex_aliases.values()})))
    ipd_files = sorted(f for f in os.listdir(in_dir)
                       if f.upper().endswith(".IPD"))
    if args.rooms:
        want = {r.strip().upper() for r in args.rooms.split(",")}
        ipd_files = [f for f in ipd_files if f[:-4].upper() in want]

    # ---- global PLM archive index over the WHOLE discovered tree ----
    # (every .PLM file and every PLM-magic file regardless of extension,
    #  on disk and inside archives; plus the embedded PLM of EVERY .IPD in
    #  the input directory - not just the filtered selection - so that
    #  sibling-room geometry is always available for object resolution)
    plm_index = PlmIndex()
    for e in resolver.registry.entries:
        if e.ext in {".TIM", ".IPD"}:
            continue                  # IPDs are indexed below (embedded PLM)
        if e.ext != ".PLM" and e.size < 20:
            continue
        plm_index.add_discovered(e)
    all_ipds = sorted(f for f in os.listdir(in_dir)
                      if f.upper().endswith(".IPD"))
    for f in all_ipds:
        try:
            data = open(os.path.join(in_dir, f), "rb").read()
            plm_index.add_embedded(f[:-4], data, u32(data, 4))
        except Exception as e:
            plm_index.errors.append(f"{f}: embedded index failed: {e}")
    plm_stats = plm_index.finalize()
    resolver.plm_index = plm_index
    log.info("PLM discovery: %d PLM archives + %d embedded libraries indexed, "
             "%d object entries, %d unique object names, %d parse failures",
             plm_stats["plm_archives_indexed"],
             plm_stats["embedded_libraries_indexed"],
             plm_stats["object_entries"], plm_stats["unique_object_names"],
             plm_stats["parse_failures"])
    for err in plm_index.errors:
        log.warning("PLM index: %s", err)

    # ---- whole-map mode (--whole-map PREFIX): one combined GLB per map ----
    whole_prefixes = []
    if getattr(args, "whole_map", None):
        for v in args.whole_map:
            for p in v.split(","):
                p = p.strip().upper()
                if p and p not in whole_prefixes:
                    whole_prefixes.append(p)
        by_prefix = {}
        for f in ipd_files:
            by_prefix.setdefault(room_prefix(f[:-4]), []).append(f)
        tree_prefixes = set()
        if tree is not None:
            for fname in tree.files:
                stemx, ext = os.path.splitext(fname)
                if ext.upper() == ".IPD":
                    tree_prefixes.add(room_prefix(stemx))
        for p in whole_prefixes:
            if p not in by_prefix:
                log.error(
                    "--whole-map %s: no IPD rooms with this exact map prefix "
                    "in %s (available here: %s).%s", p, in_dir,
                    sorted(by_prefix) or "none",
                    ("  Map prefixes known from the original rip listing: "
                     + ", ".join(sorted(tree_prefixes))
                     if tree_prefixes else ""))
                sys.exit(1)
        log.info("WHOLE-MAP mode: %s (per-room GLB files are NOT written in "
                 "this mode; run without --whole-map for those)",
                 ", ".join(whole_prefixes))

    selected = ([f for f in ipd_files if room_prefix(f[:-4]) in whole_prefixes]
                if whole_prefixes else ipd_files)
    log.info("processing %d IPD files from %s", len(selected), in_dir)

    reports, failed, skipped = [], [], []
    whole_maps = []
    map_builders, map_rooms, map_reports = {}, {}, {}
    for p in whole_prefixes:
        b = GltfBuilder()
        b.json["scenes"][0]["name"] = f"{p} map"
        map_builders[p] = b
        map_rooms[p] = []
        map_reports[p] = []

    def _log_room_extras(rep):
        """Per-room follow-up logging shared by both export modes."""
        stemx = rep["room"]
        ec = rep.get("validation", {}).get("emission_contract")
        if ec is not None:
            total = ec["quads"] + ec["lone_triangles"]
            if total:
                log.info("  %s: EMISSION CONTRACT: %d/%d quads reconstruct "
                         "(%.1f%%), %d engine-degenerate, %d lone triangles",
                         stemx, ec["quads"], total,
                         100.0 * ec["quads"] / total,
                         ec["degenerate_quads"], ec["lone_triangles"])
        if rep.get("imported_objects"):
            for o in rep["imported_objects"]:
                log.info("  %s: object %r imported from %s (%d instances, "
                         "strategy=%s)", stemx, o["object"],
                         o["imported_from"], o["instances"], o["strategy"])
        for s in rep.get("skipped_instances", []):
            log.warning("  %s: SKIPPED instance %r (%s): %s", stemx,
                        s["object"], s["context"], s["reason"])
        dropped_bb = rep.get("leaf_billboards_dropped")
        if dropped_bb:
            log.warning(
                "  %s: %d leaf billboard anchor(s) DROPPED - the engine "
                "texture TIM/BG_ETC.TIM (filetable 1799, loaded at boot "
                "into VRAM page 12 by GameFs_BgEtcGfxLoad) was not found in "
                "any scanned root, and the synthetic reconstruction was "
                "removed as too inaccurate (user instruction); place the "
                "real BG_ETC.TIM in any search root or pass --leaf-texture "
                "to restore them (there is NO TEST/LEAVES.TIM fallback - "
                "that dev file is referenced by no decompiled code).  NO "
                "other texture or geometry is "
                "affected.", stemx, dropped_bb.get("anchors_dropped", 0))
        for p in rep["problems"][:10]:
            log.warning("  %s: %s", stemx, p)
        for e in rep["validation"]["errors"]:
            log.error("  %s VALIDATION: %s", stemx, e)

    # v3 (mapLink): the input-dir room roster — every IPD stem present (the
    # full grid THIS conversion can see; neighbors outside it are simply
    # omitted from mapLink.neighbors, consumers probe at runtime anyway).
    input_room_names = {f[:-4].upper() for f in all_ipds}

    for f in selected:
        path = os.path.join(in_dir, f)
        stem = f[:-4]
        try:
            room = parse_ipd(path, resolver)
        except Exception as e:
            log.error("%s: parse failed: %s", stem, e)
            failed.append({"room": stem, "error": str(e)})
            continue
        pref = room_prefix(stem) if whole_prefixes else None
        if args.dry_run:
            log.info("%s: grid=(%d,%d) instances=%d unplaced=%d problems=%d",
                     stem, room.x_pos, room.y_pos, len(room.instances),
                     len(room.unplaced), len(room.problems))
            if pref is not None:
                map_rooms[pref].append(room)
            continue
        try:
            rep = export_room(room, resolver, out_dir,
                              include_unused=args.include_unused,
                              builder=map_builders.get(pref),
                              known_rooms=input_room_names)
        except Exception as e:
            log.error("%s: export failed: %s", stem, e)
            failed.append({"room": stem, "error": str(e)})
            continue
        if pref is not None:
            # ---- whole-map mode: room appended into the shared builder ----
            map_rooms[pref].append(room)
            map_reports[pref].append(rep)
            rep["validation"] = {
                "path": None, "errors": [], "warnings": [], "passed": [],
                "note": ("whole-map mode: this room's structural validation "
                         "is performed on the combined map GLB (see "
                         "summary.whole_maps), of which it is one root node"),
            }
            n_imp = sum(o["instances"] for o in rep.get("imported_objects", []))
            n_skip = len(rep.get("skipped_instances", []))
            if rep["meshes"] == 0:
                skipped.append(rep["room"])
                log.warning("%s: EMPTY (no geometry) - contributed nothing "
                            "to the %s map", stem, pref)
            else:
                log.info("%s [%s map]: %d meshes, %d prims, %d materials, "
                         "%d images (deduped across rooms), %d tex ok / "
                         "%d missing, %d objs ok / %d imported / %d skipped, "
                         "%d billboards (%dq), %d leaf anchors dropped, "
                         "degraded=%s",
                         stem, pref, rep["meshes"], rep["primitives"],
                         rep["materials"], rep["images"],
                         len(rep["tex_ok"]), len(rep["tex_missing"]),
                         rep["instances"] - n_imp, n_imp, n_skip,
                         rep.get("billboards", {}).get("anchors", 0),
                         rep.get("billboards", {}).get("quads", 0),
                         rep.get("leaf_billboards_dropped", {}).get(
                             "anchors_dropped", 0),
                         "YES" if rep.get("degraded") else "no")
            reports.append(rep)
            _log_room_extras(rep)
            continue
        # ---- default per-room mode (unchanged behavior) ----
        rep["validation"] = validate_glb(rep["output"],
                                         tex_aliases=tex_aliases)
        # embedded-texture cross-check: every decoded texture variant must
        # appear as an embedded image with the TIM's pixel dimensions (an
        # image named after a byte-identical TIM alias counts - the content
        # is the same)
        img_dims = {e["name"]: (e["width"], e["height"])
                    for e in rep["validation"].get("embedded_images", [])}
        for v in rep.get("tex_variants_struct", []):
            if not any((n.split("_pal")[0] == v["tex"] or
                        n.split("_pal")[0].upper() in tex_aliases.get(
                            v["tex"].upper(), ()))
                       and d == (v["w"], v["h"])
                       for n, d in img_dims.items()):
                rep["validation"]["errors"].append(
                    f"texture {v['tex']}: no embedded image with the expected "
                    f"{v['w']}x{v['h']} pixel dimensions")
        nerr = len(rep["validation"]["errors"])
        n_imp = sum(o["instances"] for o in rep.get("imported_objects", []))
        n_skip = len(rep.get("skipped_instances", []))
        if rep["meshes"] == 0:
            skipped.append(rep["room"])
            log.warning("%s: EMPTY (no geometry) - %s", stem, rep["output"])
        else:
            log.info("%s: %d meshes, %d prims, %d materials, %d images, "
                     "%d tex ok / %d missing, %d objs ok / %d imported / "
                     "%d skipped, %d billboards (%dq), %d leaf anchors "
                     "dropped, degraded=%s, %d validation errors, %.1f KiB",
                     stem, rep["meshes"], rep["primitives"], rep["materials"],
                     rep["images"], len(rep["tex_ok"]), len(rep["tex_missing"]),
                     rep["instances"] - n_imp, n_imp, n_skip,
                     rep.get("billboards", {}).get("anchors", 0),
                     rep.get("billboards", {}).get("quads", 0),
                     rep.get("leaf_billboards_dropped", {}).get(
                         "anchors_dropped", 0),
                     "YES" if rep.get("degraded") else "no",
                     nerr, rep["bytes"] / 1024.0)
        reports.append(rep)
        _log_room_extras(rep)

    # ---- write each whole-map GLB + overlap / coverage proof ----
    for pref in whole_prefixes:
        rooms_p, reps_p = map_rooms[pref], map_reports[pref]
        if args.dry_run:
            cov = map_coverage(pref, rooms_p, tree)
            occ = {}
            for r in rooms_p:
                occ.setdefault((int(r.x_pos), int(r.y_pos)), []).append(r.name)
            log.info("%s map (dry run): %d room(s) %s, cells %s, coverage "
                     "%d/%d original-rip rooms",
                     pref, len(rooms_p), [r.name for r in rooms_p],
                     {f"{c[0]},{c[1]}": n for c, n in sorted(occ.items())},
                     len(cov["rooms_in_input"]),
                     len(cov["rooms_in_original_rip"]) or len(rooms_p))
            continue
        builder = map_builders[pref]
        if not reps_p:
            log.error("%s map: no rooms exported successfully - map GLB "
                      "NOT written", pref)
            failed.append({"room": f"{pref}_MAP",
                           "error": "no rooms exported into the map"})
            continue
        map_path = os.path.join(out_dir, f"{pref}_MAP.glb")
        size = builder.write_glb(map_path)
        val = validate_glb(map_path, tex_aliases=tex_aliases)
        # embedded-texture cross-check for EVERY room of the map: each
        # decoded texture variant must appear as an embedded map image with
        # the TIM's pixel dimensions (an image named after a byte-identical
        # TIM alias counts - same content)
        img_dims = {e["name"]: (e["width"], e["height"])
                    for e in val.get("embedded_images", [])}
        for rep in reps_p:
            for v in rep.get("tex_variants_struct", []):
                if not any((n.split("_pal")[0] == v["tex"] or
                            n.split("_pal")[0].upper() in tex_aliases.get(
                                v["tex"].upper(), ()))
                           and d == (v["w"], v["h"])
                           for n, d in img_dims.items()):
                    val["errors"].append(
                        f"{rep['room']}: texture {v['tex']}: no embedded image "
                        f"with the expected {v['w']}x{v['h']} pixel dimensions "
                        f"in {pref}_MAP.glb")
        overlap = analyze_map_overlap(pref, rooms_p, reps_p, builder, val)
        coverage = map_coverage(pref, rooms_p, tree)
        verts = sum(builder.json["accessors"][p["attributes"]["POSITION"]]["count"]
                    for m in builder.json["meshes"] for p in m["primitives"])
        tris = sum(builder.json["accessors"][p["indices"]]["count"] // 3
                   for m in builder.json["meshes"] for p in m["primitives"])
        os_ = overlap["summary"]
        n_orig = len(coverage["rooms_in_original_rip"]) or len(rooms_p)
        mrep = {
            "map": pref,
            "legacy_check": (
                "sh_ipd2obj (legacy C) has NO whole-map mode: it converts each "
                "file separately, one OBJ per IPD.  Its default WORLD "
                "POSITIONING (local + cell * signed cell-index from the file "
                "name) is what this map export generalizes per room, so the "
                "combined <PREFIX>_MAP.glb equals the union of the legacy "
                "per-room OBJs (same grid placement) in one file.  CELL "
                "STRIDE (v8): the engine's CHUNK_SIZE = 40.0f = 10240 units "
                "(decomp terrain.h / world_map.c), rectified from the legacy "
                "tool's measured 10246 - rooms shift by 6 units per cell "
                "toward the engine-true placement."),
            "output": map_path, "bytes": size,
            "rooms": [r.name for r in rooms_p],
            "cells": {rep["room"]: rep["grid_pos"] for rep in reps_p},
            "meshes": builder.stats["meshes"],
            "primitives": builder.stats["primitives"],
            "materials": len(builder.json["materials"]),
            "images": len(builder.json["images"]),
            "nodes": len(builder.json["nodes"]),
            "vertices": verts, "triangles": tris,
            "validation": val,
            "overlap_analysis": overlap,
            "coverage": coverage,
            "degraded_rooms": [rep["room"] for rep in reps_p
                               if rep.get("degraded")],
            "rooms_with_missing_textures": [rep["room"] for rep in reps_p
                                            if rep["tex_missing"]],
        }
        whole_maps.append(mrep)
        log.info("%s map: %d rooms (%d/%d original-rip rooms present), "
                 "%d meshes, %d prims, %d materials, %d images, %d nodes, "
                 "%d verts, %d tris, cell occupancy %d distinct / %d "
                 "stacked, overlap verdict: %s (%d boundary-contact pairs, "
                 "%d flagged), %d validation errors, %.1f KiB -> %s",
                 pref, len(rooms_p), len(rooms_p), n_orig,
                 mrep["meshes"], mrep["primitives"], mrep["materials"],
                 mrep["images"], mrep["nodes"], verts, tris,
                 os_["distinct_cells"], os_["stacked_cells"],
                 os_["verdict"], os_["adjacent_boundary_contact_pairs"],
                 os_["flagged_pairs"], len(val["errors"]), size / 1024.0,
                 map_path)
        if coverage["missing_from_input"]:
            log.warning("  %s map: PARTIAL - missing original-rip rooms not "
                        "in the input: %s", pref,
                        coverage["missing_from_input"])
        for e in val["errors"]:
            log.error("  %s_MAP VALIDATION: %s", pref, e)
        for w in val["warnings"]:
            log.warning("  %s_MAP validation warning: %s", pref, w)
    if whole_prefixes and not args.dry_run:
        log.info("whole-map exports: %s",
                 ", ".join(f"{m['map']} ({len(m['rooms'])} rooms, "
                           f"{m['bytes'] / 1024.0:.1f} KiB)"
                           for m in whole_maps) or "none")
    resolver.stats["png_conversions"] = sum(
        r.get("png_conversions", 0) for r in reports)
    # ---- object-reference resolution aggregates ----
    o_stats = {"references": len(resolver.object_ledger)}
    by_status = {}
    by_strategy = {}
    for r in resolver.object_ledger:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        if r.get("strategy"):
            by_strategy[r["strategy"]] = by_strategy.get(r["strategy"], 0) + 1
    o_stats["by_status"] = by_status
    o_stats["by_strategy"] = by_strategy
    total_skipped_inst = sum(len(r.get("skipped_instances", []))
                             for r in reports)
    summary = {
        "input": in_dir, "output": out_dir,
        "mode": ("whole-map (" + ", ".join(whole_prefixes) + ")"
                  if whole_prefixes else "per-room (default)"),
        "search_roots": resolver.roots,
        "texture_discovery": {**resolver.discovery_stats, "tim": tims},
        "texture_resolution": {
            "stats": resolver.stats,
            "unresolved_names": resolver.unresolved_names(),
            "resolutions": resolver.resolutions,
        },
        "plm_discovery": {**plm_stats, "errors": plm_index.errors},
        "object_resolution": {
            "stats": o_stats,
            "unresolved_references": [r for r in resolver.object_ledger
                                      if r["status"] not in
                                      ("resolved", "resolved_flag_library")],
            "skipped_instances_total": total_skipped_inst,
            "skipped_instances": [
                s for r in reports
                for s in r.get("skipped_instances", [])],
            "imported_objects": [
                {"room": r["room"], **o}
                for r in reports for o in r.get("imported_objects", [])],
            "ledger": resolver.object_ledger,
        },
        "texture_reconciliation": {
            r["room"]: r.get("texture_reconciliation", {}) for r in reports},
        "processed": len(reports) + len(failed),
        "exported": len(reports), "failed": failed, "empty": skipped,
        "whole_maps": whole_maps,
        "rooms_degraded": [
            {"room": r["room"],
             "reasons": r.get("degradation_reasons", []),
             "skipped_instances": len(r.get("skipped_instances", []))}
            for r in reports if r.get("degraded")],
        "rooms_with_missing_textures": [r["room"] for r in reports
                                        if r["tex_missing"]],
        "leaf_billboards_dropped_total": sum(
            r.get("leaf_billboards_dropped", {}).get("anchors_dropped", 0)
            for r in reports),
        "rooms_with_dropped_leaf_billboards": [
            {"room": r["room"],
             "anchors_dropped": r.get("leaf_billboards_dropped", {}).get(
                 "anchors_dropped", 0),
             "clusters": r.get("leaf_billboards_dropped", {}).get(
                 "clusters", {})}
            for r in reports if r.get("leaf_billboards_dropped")],
        "rooms_with_validation_errors": [r["room"] for r in reports
                                         if r["validation"]["errors"]],
        "resolver_stats": resolver.stats,
        "reports": reports,
    }
    if args.report:
        with open(args.report, "w") as fh:
            json.dump(summary, fh, indent=1, default=str)
        log.info("report written to %s", args.report)
    if args.texture_report:
        with open(args.texture_report, "w") as fh:
            json.dump({"discovery": summary["texture_discovery"],
                       "resolution": summary["texture_resolution"],
                       "per_room_reconciliation":
                           summary["texture_reconciliation"]}, fh, indent=1)
        log.info("texture report written to %s", args.texture_report)
    if args.plm_report:
        with open(args.plm_report, "w") as fh:
            json.dump({"plm_discovery": summary["plm_discovery"],
                       "object_resolution": summary["object_resolution"]},
                      fh, indent=1, default=str)
        log.info("PLM/object report written to %s", args.plm_report)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
