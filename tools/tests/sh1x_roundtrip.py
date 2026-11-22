#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sh1x_roundtrip.py — SH1X extras -> IPD byte-identical reconstruction proof.

Reads a GLB emitted by ipd2gltf.py (v14+), extracts scenes[0].extras.SH1X,
reconstructs the ENTIRE source IPD file (header, modelInfos, modelBuffers,
instances, billboards, subchunkRanges, modelOrder, collision incl. all
arrays/LUTs/stamp buffer, embedded PLM incl. every material/object/mesh/pack/
vertex/normal/slot table), and compares against the original .IPD byte for
byte.  Also verifies the TIM blobs against the source TIM files.

Usage:
    python3 tools/sh1x_roundtrip.py <room.glb> <original.IPD> [--tim-dir DIR]

Exit code 0 = byte-identical (prints the coverage report); 1 = any mismatch
(prints every differing byte range).
"""
import argparse
import base64
import json
import os
import struct
import sys

B = lambda s: base64.b64decode(s)


def ranges_of_diff(a, b, ctx_limit=8):
    """Byte ranges where a and b differ."""
    n = min(len(a), len(b))
    diffs = []
    i = 0
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            diffs.append((i, j))
            i = j
        else:
            i += 1
    if len(a) != len(b):
        diffs.append((n, max(len(a), len(b))))
    return diffs


def build_ipd(sh):
    """Reconstruct the full IPD file bytes from the SH1X container.

    Layout order (measured on HP0000..HP0003 + THRF9FD):
      0x0000 header (84B)
      0x0054 collision block: header(0x34) + stamp(0x100) + [0x100 gap to
              modelInfosOff] ... arrays live AFTER modelOrder (collision
              offsets are collision-relative and point there)
      modelInfosOff .. modelInfos
      modelBuffersOff .. modelBuffers
      instance/bb/subchunk tables (per-buffer: instances, billboards,
              subchunkRanges)
      modelOrderOff .. modelOrder (+pad to the first collision array)
      collision arrays (splitV, surfaces, polygons, cylinders, allocs,
              shapeLut, surfaceLut) — EXACTLY as captured in blockRaw
      lmHdrOff .. PLM
    The collision ARRAYS' original placement is preserved verbatim via
    blockRaw; the roundtrip proof re-encodes the PARSED fields into those
    positions and byte-compares.
    """
    out = bytearray()
    hdr = B(sh["header"]["raw"])
    assert len(hdr) == 84, "header raw must be 84B"
    out += hdr
    coll = sh["collision"]
    lm_off = sh["header"]["lmHdrOff"]
    block = bytearray(B(coll["blockRaw"]))
    assert len(block) == lm_off - 0x54, \
        f"collision block len {len(block)} != {lm_off - 0x54}"
    # re-encode every parsed array into the block (proves decoded == bytes)
    sv_off = struct.unpack_from("<I", block, 12)[0]
    for i, v in enumerate(coll["splitVertices"]):
        struct.pack_into("<3h", block, sv_off + 6 * i, v["x"], v["y"], v["z"])
    su_off = struct.unpack_from("<I", block, 16)[0]
    for i, s in enumerate(coll["surfaces"]):
        o = su_off + 12 * i
        struct.pack_into("<3h", block, o, *s["offset"])
        u16v = (s["floorType"] & 0x1F) | ((s["disableHeight"] & 7) << 5) | \
               ((s["surfaceCacheIdx"] & 3) << 8) | \
               ((s["triggerFlagIdx"] & 0xF) << 11)
        struct.pack_into("<H", block, o + 6, u16v)
        struct.pack_into("<2h", block, o + 8,
                         s["slopeGradientX"], s["slopeGradientZ"])
    pg_off = struct.unpack_from("<I", block, 20)[0]
    for i, p in enumerate(coll["polygons"]):
        o = pg_off + 10 * i
        # decomp layout: wx@0 (ox:14|tfiHi:2), wy@2 (oy:14|tfiLo:2), z@4;
        # engine combines (Hi << 2) | Lo with Hi from wx (collision.c:1066,
        # ray.c:464) — v43 RIP2-3: the nibbles were swapped.
        tfi = p["triggerFlagIdx"]
        wx = (p["offsetX"] & 0x3FFF) | (((tfi >> 2) & 3) << 14)
        wy = (p["offsetY"] & 0x3FFF) | ((tfi & 3) << 14)
        struct.pack_into("<HH", block, o, wx, wy)
        struct.pack_into("<h", block, o + 4, p["offsetZ"])
        block[o + 6] = p["splitVertexIdx0"]
        block[o + 7] = p["splitVertexIdx1"]
        block[o + 8] = p["surfaceIdx0"]
        block[o + 9] = p["surfaceIdx1"]
    cy_off = struct.unpack_from("<I", block, 24)[0]
    for i, y in enumerate(coll["cylinders"]):
        o = cy_off + 10 * i
        # decomp ipd.h:71-77: triggerFlagIdx = word0 bits 8-11 (v43 RIP2-2)
        u16v = (y["floorType"] & 0x1F) | ((y["disableHeight"] & 7) << 5) | \
               ((y["triggerFlagIdx"] & 0xF) << 8)
        struct.pack_into("<H", block, o, u16v)
        struct.pack_into("<3h", block, o + 2, *y["offset"])
        struct.pack_into("<h", block, o + 8, y["radius"])
    sa_off = struct.unpack_from("<I", block, 0x20)[0]
    for i, a in enumerate(coll["shapeAllocs"]):
        struct.pack_into("<2h", block, sa_off + 4 * i, a[0], a[1])
    shl_off = struct.unpack_from("<I", block, 0x28)[0]
    block[shl_off:shl_off + coll["shapeLutSize"]] = bytes(coll["shapeLut"])
    sul_off = struct.unpack_from("<I", block, 0x2C)[0]
    block[sul_off:sul_off + coll["surfaceLutSize"]] = bytes(coll["surfaceLut"])

    # ---- assemble the file in the FILE's section order ----------------
    mi_off = sh["header"]["modelInfosOff"]
    mb_off = sh["header"]["modelBuffersOff"]
    mo_off = sh["header"]["modelOrderOff"]
    # region 1: header(84) + the gap up to modelInfosOff (contains the
    # collision HEADER + stamp buffer + the measured 0x100 zero gap)
    out = bytearray(hdr)
    assert mi_off >= len(out), "modelInfos overlaps header"
    out.extend(block[0:mi_off - 0x54])   # collision header+stamps+gap, verbatim
    # modelInfos
    assert len(out) == mi_off, f"out len {len(out)} != modelInfosOff {mi_off}"
    for mi in sh["modelInfos"]:
        out += B(mi["raw"])
    # modelBuffers
    assert len(out) == mb_off, f"out len {len(out)} != modelBuffersOff {mb_off}"
    for b in sh["modelBuffers"]:
        out += B(b["raw"])
    # instance/bb/subchunk tables, per-buffer order (observed layout)
    for b in sh["modelBuffers"]:
        for inst in b["instances"]:
            out += B(inst["raw"])
        for bb in b["billboards"]:
            out += B(bb["raw"])
        for sc in b["subchunkRanges"]:
            out += B(sc["raw"])
    # modelOrder (+ the file's own pad to the collision arrays' start)
    while len(out) < mo_off:
        out += b"\x00"
    out += bytes(sh["modelOrder"])
    # the collision ARRAYS region: the array offsets read from the block are
    # COLLISION-BLOCK-relative (block coordinates start at the collision
    # header), so the first array's field value is its index in blockRaw;
    # its FILE position is 0x54 + field.  Zero-pad the gap after modelOrder.
    positives = [x for x in (sv_off, su_off, pg_off, cy_off, sa_off,
                             shl_off, sul_off) if x > 0]
    if positives:
        arr_start_in_block = min(positives)
    else:
        arr_start_in_block = len(block)   # no arrays: nothing to append
    arr_start_file = 0x54 + arr_start_in_block
    while len(out) < arr_start_file:
        out += b"\x00"
    out += block[arr_start_in_block:]
    # PLM
    lm_off = sh["header"]["lmHdrOff"]
    assert len(out) <= lm_off, \
        f"PLM overlap: out {len(out)} > lmHdrOff {lm_off}"
    while len(out) < lm_off:
        out += b"\x00"
    plm_bytes = build_plm(sh["plm"])
    out += plm_bytes
    return bytes(out), plm_bytes


def build_plm(plm):
    """Reconstruct the embedded PLM bytes from SH1X.plm.

    All table positions come from the verbatim header/object/mesh raws
    (their own offset fields) — the reconstruction is fully determined:
    materials at texNameOff, object headers at objStartOff, the order list
    at orderOff, object mesh headers at each header's meshHdrsOff, and
    every mesh's packs/vertsXY/vertsZ/normals/slots at the mesh header's
    own offsets.  Gaps are zero-filled (measured zero in the files).
    """
    hdr = bytearray(B(plm["headerRaw"]))
    size_hint = 0
    for m in plm["materials"]:
        size_hint += len(B(m["raw"]))
    # 1st pass: compute the required extent
    extent = 20
    tex_off = struct.unpack_from("<I", hdr, 4)[0]
    obj_off = struct.unpack_from("<I", hdr, 12)[0]
    order_off = struct.unpack_from("<I", hdr, 16)[0]
    mesh_blocks = []   # (abs_offset, blob) placements
    for o in plm["objects"]:
        ohdr = B(o["headerRaw"])
        mh_off = struct.unpack_from("<I", ohdr, 12)[0]
        for mesh in o["meshes"]:
            mh = bytearray(B(mesh["headerRaw"]))
            pack_off = struct.unpack_from("<I", mh, 4)[0]
            vxy_off = struct.unpack_from("<I", mh, 8)[0]
            vz_off = struct.unpack_from("<I", mh, 12)[0]
            nrm_off = struct.unpack_from("<I", mh, 16)[0]
            slot_off = struct.unpack_from("<I", mh, 20)[0]
            packs_blob = b"".join(B(p["raw"]) for p in mesh["packs"])
            vxy_blob = b"".join(
                struct.pack("<2h", v[0], v[1]) for v in mesh["vertsXY"])
            vz_blob = b"".join(
                struct.pack("<h", z) for z in mesh["vertsZ"])
            nrm_blob = b"".join(
                struct.pack("<4b", n["nx"], n["ny"], n["nz"], n["slotCount"])
                for n in mesh["normals"])
            slot_blob = bytes(mesh["slots"])
            for off, blob in ((pack_off, packs_blob), (vxy_off, vxy_blob),
                              (vz_off, vz_blob), (nrm_off, nrm_blob),
                              (slot_off, slot_blob)):
                mesh_blocks.append((off, blob))
                extent = max(extent, off + len(blob))
            extent = max(extent, mh_off + 24 * len(o["meshes"]))
    extent = max(extent, tex_off + 24 * len(plm["materials"]),
                 obj_off + 16 * len(plm["objects"]),
                 order_off + len(plm["order"]))
    out = bytearray(extent)
    out[0:20] = hdr
    for i, m in enumerate(plm["materials"]):
        out[tex_off + 24 * i: tex_off + 24 * i + 24] = B(m["raw"])
    for i, o in enumerate(plm["objects"]):
        out[obj_off + 16 * i: obj_off + 16 * i + 16] = B(o["headerRaw"])
    out[order_off:order_off + len(plm["order"])] = bytes(plm["order"])
    # mesh headers at their object-declared positions
    for o in plm["objects"]:
        ohdr = B(o["headerRaw"])
        mh_off = struct.unpack_from("<I", ohdr, 12)[0]
        for i, mesh in enumerate(o["meshes"]):
            out[mh_off + 24 * i: mh_off + 24 * i + 24] = B(mesh["headerRaw"])
    for off, blob in mesh_blocks:
        out[off:off + len(blob)] = blob
    # unreferenced trailing data (byte-identical contract: EVERY byte)
    out += B(plm.get("trailingRaw", "") or b"")
    return bytes(out)


def load_glb_scene_extras(path):
    data = open(path, "rb").read()
    assert data[:4] == b"glTF", "not a GLB"
    jlen = struct.unpack_from("<I", data, 12)[0]
    j = json.loads(data[20:20 + jlen])
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("ipd")
    ap.add_argument("--tim-dir", default="")
    args = ap.parse_args()
    j = load_glb_scene_extras(args.glb)
    sh = j["scenes"][0]["extras"]["SH1X"]
    orig = open(args.ipd, "rb").read()
    rebuilt, plm_bytes = build_ipd(sh)
    ok = True
    print(f"room {sh['room']}: original {len(orig)}B, reconstructed "
          f"{len(rebuilt)}B")
    # 1. full-file compare if lengths match
    if len(rebuilt) == len(orig):
        d = ranges_of_diff(rebuilt, orig)
        if d:
            ok = False
            print(f"DIFF: {len(d)} ranges differ (first:)")
            for s, e in d[:ctx_limit if False else 8]:
                print(f"  [{s:#x}..{e:#x}) orig={orig[s:s+12].hex(' ')} "
                      f"rebuilt={rebuilt[s:s+12].hex(' ')}")
        else:
            print("  FULL FILE BYTE-IDENTICAL ✔")
    else:
        ok = False
        print(f"  LENGTH MISMATCH: orig {len(orig)} vs rebuilt {len(rebuilt)}")
        # compare the common prefix anyway
        d = ranges_of_diff(rebuilt, orig)
        print(f"  {len(d)} diff ranges in the common prefix (first 8):")
        for s, e in d[:8]:
            print(f"  [{s:#x}..{e:#x})")
    # 2. PLM sub-block compare
    lm_off = sh["header"]["lmHdrOff"]
    plm_orig = orig[lm_off:]
    if plm_bytes == plm_orig:
        print(f"  PLM BYTE-IDENTICAL ✔ ({len(plm_bytes)}B)")
    else:
        ok = False
        d = ranges_of_diff(plm_bytes, plm_orig)
        print(f"  PLM DIFF: {len(d)} ranges (first: " +
              ", ".join(f"[{s:#x}..{e:#x})" for s, e in d[:8]) + ")")
    # 3. TIM blobs
    tim_dir = args.tim_dir or os.path.dirname(args.ipd)
    for t in sh["textures"]:
        blob = B(t["tim"])
        p = os.path.join(tim_dir, t["name"] + ".TIM")
        if os.path.exists(p):
            src = open(p, "rb").read()
            if blob == src:
                print(f"  TIM {t['name']}: BYTE-IDENTICAL ✔ ({len(blob)}B)")
            else:
                ok = False
                print(f"  TIM {t['name']}: DIFFERS")
        else:
            print(f"  TIM {t['name']}: source not found at {p} (skipped)")
    # 4. coverage assertions: every raw blob consumed
    n_raws = (1 +  # header
              len(sh["modelInfos"]) +
              len(sh["modelBuffers"]) +
              sum(len(b["instances"]) for b in sh["modelBuffers"]) +
              sum(len(b["billboards"]) for b in sh["modelBuffers"]) +
              sum(len(b["subchunkRanges"]) for b in sh["modelBuffers"]) +
              1 +  # collision block
              1 +  # plm header
              len(sh["plm"]["materials"]) +
              len(sh["plm"]["objects"]) +
              sum(len(o["meshes"]) for o in sh["plm"]["objects"]) +
              sum(len(m["packs"]) for o in sh["plm"]["objects"]
                  for m in o["meshes"]))
    print(f"  raw blobs consumed: {n_raws}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
