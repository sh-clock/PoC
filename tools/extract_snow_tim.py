#!/usr/bin/env python3
"""Extract the snow particle sprite + distance-gradient CLUTs from the original
BG_ETC.TIM (PSX 4bpp TIM) and emit them as a C header (snow_tim_data.h) for
embedding directly into the fog_poc executable.

Ground truth (silent-hill-decomp):
  - world_draw.c GameFs_BgEtcGfxLoad: BG_ETC.TIM loads at VRAM (768, 0)
    (s_FsImageDesc { tPage {0,12}, u 0, v 0, clutX 192 } -> x = 12*64 = 768)
  - maps/particle.c Particle_SnowDraw: snow flakes are POLY_FT3 with tpage 44
    (0x2C: x page bits -> VRAM 768, ABR bits 5-6 = 1 additive):
      sprite: VRAM (768, u 0..7, v 112..116) 4bpp indices   -> snowSprite[5][8]
      cluts:  0x1830 = (768, 96)   ... near  (<2m, 4x4 sprite u3..7 v112..116)
              ((z>>5)+96)<<6|0x30 = (768, 96+(z>>5))  mid (2..8m, 3x3 sprite)
              0x19F0 = (768, 103)  ... far   (>=8m, 1x1 sprite)
    -> 8 CLUTs of 16 halfwords at VRAM (768, 96..103)      -> snowClut[8][16]
      (these CLUTs physically live inside the BG_ETC texture page itself,
       stored as pixel data rows 96..103, halfword columns 0..15)

TIM 4bpp pixel (x,y) maps to VRAM (768 + x, 0 + y); each VRAM halfword packs
4 consecutive 4bpp pixels: hw = p0 | p1<<4 | p2<<8 | p3<<12.

Cross-checks against the previous agent's verified scene.bin v2 section are
performed when assets/scene.bin exists (byte-identical requirement)."""

import struct
import sys
import os


def parse_tim(data):
    if len(data) < 8:
        raise ValueError("TIM too small")
    magic, flag = struct.unpack_from("<II", data, 0)
    if magic != 0x10:
        raise ValueError("not a TIM (magic %08x)" % magic)
    # TIM PMODE bits 0-1: 0 = 4bpp, 1 = 8bpp, 2 = 16bpp, 3 = mixed
    bpp = 4 if (flag & 0x03) == 0x00 else 8 if (flag & 0x03) == 0x01 \
        else 16 if (flag & 0x03) == 0x02 else None
    has_clut = bool(flag & 0x08)
    off = 8
    clut = None
    if has_clut:
        (blen,) = struct.unpack_from("<I", data, off)
        cx, cy, cw, ch = struct.unpack_from("<HHHH", data, off + 4)
        clut = []
        for r in range(ch):
            row = struct.unpack_from("<%dH" % cw, data, off + 12 + r * cw * 2)
            clut.append(list(row))
        off += 8 + blen - 8  # block len includes its own 4-byte len field? no:
        # TIM block: u32 len (includes the 4 len bytes + 12 header bytes for clut)
        off = 8 + blen
    (blen2,) = struct.unpack_from("<I", data, off)
    px, py, pw, ph = struct.unpack_from("<HHHH", data, off + 4)
    pix_off = off + 12
    nwords = pw * ph
    pixels = []  # 4bpp: rows of pw*4 indices
    for y in range(ph):
        words = struct.unpack_from("<%dH" % pw, data, pix_off + y * pw * 2)
        row = []
        for w in words:
            row.append(w & 0xF)
            row.append((w >> 4) & 0xF)
            row.append((w >> 8) & 0xF)
            row.append((w >> 12) & 0xF)
        pixels.append(row)
    return {
        "bpp": bpp,
        "has_clut": has_clut,
        "clut": clut,
        "vram": (px, py),
        "size": (pw * (4 if bpp == 4 else 2 if bpp == 8 else 1), ph),
        "pixels": pixels,
    }


def halfword_from_pixels(pixels, row, hwcol):
    """VRAM halfword at pixel row `row`, halfword column `hwcol` (4 4bpp px)."""
    p = pixels[row][hwcol * 4: hwcol * 4 + 4]
    return p[0] | (p[1] << 4) | (p[2] << 8) | (p[3] << 12)


def main():
    tim_path = sys.argv[1] if len(sys.argv) > 1 else "input/BG_ETC.TIM"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "src/snow_tim_data.h"
    scene_bin = sys.argv[3] if len(sys.argv) > 3 else None

    data = open(tim_path, "rb").read()
    tim = parse_tim(data)
    print("TIM: %s bpp=%d clut=%s vram=(%d,%d) pixels=%dx%d" %
          (tim_path, tim["bpp"],
           ("%d palettes x %d colors" % (len(tim["clut"]), len(tim["clut"][0]))) if tim["clut"] else "none",
           tim["vram"][0], tim["vram"][1], tim["size"][0], tim["size"][1]))

    pixels = tim["pixels"]
    W = tim["size"][0]
    assert W >= 8 and len(pixels) >= 117, "TIM too small for snow assets"

    # sprite: rows 112..116, cols 0..7 (4bpp indices)
    sprite = [[pixels[112 + r][c] for c in range(8)] for r in range(5)]
    # cluts: VRAM (768, 96..103) -> TIM pixel rows 96..103, halfword cols 0..15
    cluts = [[halfword_from_pixels(pixels, 96 + r, c) for c in range(16)]
             for r in range(8)]

    # cross-check with previous verified scene.bin v2 if available
    if scene_bin and os.path.exists(scene_bin):
        sb = open(scene_bin, "rb").read()
        u32 = struct.unpack_from
        # header: magic(1) counts(8) track(12) fog(8) then snow section
        # layout (u32 units): magic, texC,matC,itemC,vertC,idxC,texB,timC,timB,
        #   type, s(3), e(3), speed, fov, loop, look, fogDist, fogRGB, tint(3), f6,
        #   snowPresent, clut(128), sprite rows(10 u32s), pad(2)
        p = 1 + 8 + 1 + 6 + 2 + 2 + 1 + 1 + 1 + 1 + 3 + 1 + 1
        # header layout (u32 units) per scene_load() in fog_poc.c:
        #   [0] magic, [1] (skipped), [2..9] counts(8), [10] track.type,
        #   [11..13] start, [14..16] end, [17] speed, [18] fov, [19] loop,
        #   [20] look, [21] fogDist, [22] fogRGB, [23..25] tint, [26] field6,
        #   [27] snowPresent, [28..155] clut(128), [156..165] sprite(10), pad
        p = 27
        snow_present = u32("<I", sb, p * 4)[0]
        assert snow_present == 1, "scene.bin snow section missing"
        p += 1
        ref_clut = [[0] * 16 for _ in range(8)]
        for r in range(8):
            for c in range(16):
                ref_clut[r][c] = u32("<I", sb, p * 4)[0]
                p += 1
        ref_sprite = [[0] * 8 for _ in range(5)]
        for r in range(5):
            w0 = u32("<I", sb, p * 4)[0]; w1 = u32("<I", sb, p * 4 + 4)[0]; p += 2
            for c in range(4):
                ref_sprite[r][c] = (w0 >> (c * 8)) & 0xFF
                ref_sprite[r][4 + c] = (w1 >> (c * 8)) & 0xFF
        ok_c = ref_clut == cluts
        ok_s = ref_sprite == sprite
        print("cross-check vs scene.bin: clut %s, sprite %s" %
              ("IDENTICAL" if ok_c else "MISMATCH!", "IDENTICAL" if ok_s else "MISMATCH!"))
        if not (ok_c and ok_s):
            for r in range(8):
                for c in range(16):
                    if ref_clut[r][c] != cluts[r][c]:
                        print("  clut[%d][%d]: ref=%04x mine=%04x" % (r, c, ref_clut[r][c], cluts[r][c]))
            for r in range(5):
                for c in range(8):
                    if ref_sprite[r][c] != sprite[r][c]:
                        print("  sprite[%d][%d]: ref=%d mine=%d" % (r, c, ref_sprite[r][c], sprite[r][c]))
            sys.exit(1)

    with open(out_path, "w") as f:
        f.write("/* ====================================================================\n")
        f.write(" * snow_tim_data.h — snow particle assets EMBEDDED in the executable.\n")
        f.write(" * --------------------------------------------------------------------\n")
        f.write(" * Generated from the ORIGINAL BG_ETC.TIM (Silent Hill BG/THRF9FD room\n")
        f.write(" * data) by tools/extract_snow_tim.py — do not edit by hand.\n")
        f.write(" *\n")
        f.write(" * Engine placement (silent-hill-decomp):\n")
        f.write(" *   GameFs_BgEtcGfxLoad (world_draw.c): BG_ETC.TIM -> VRAM (768, 0)\n")
        f.write(" *   Particle_SnowDraw   (maps/particle.c):\n")
        f.write(" *     - flake sprite   = VRAM (768, u 0..7, v 112..116), 4bpp indices\n")
        f.write(" *     - 8 distance CLUTs = VRAM (768, 96..103), 16 halfwords each\n")
        f.write(" *       (clut 0x1830 near <2m / rows 96+(z>>5) mid / 0x19F0 far >=8m)\n")
        f.write(" * ==================================================================== */\n")
        f.write("#ifndef FOG_POC_SNOW_TIM_DATA_H\n")
        f.write("#define FOG_POC_SNOW_TIM_DATA_H\n\n")
        f.write("/* 4bpp sprite indices, [row 112..116][col 0..7] */\n")
        f.write("static const unsigned char kSnowSprite[5][8] = {\n")
        for r in range(5):
            f.write("    { %s },\n" % ", ".join("0x%X" % sprite[r][c] for c in range(8)))
        f.write("};\n\n")
        f.write("/* 8 distance-gradient CLUTs (PSX 15-bit halfwords, STP in bit 15),\n")
        f.write(" * [VRAM row 96..103][CLUT entry 0..15] */\n")
        f.write("static const unsigned short kSnowClut[8][16] = {\n")
        for r in range(8):
            f.write("    { %s },\n" % ", ".join("0x%04X" % cluts[r][c] for c in range(16)))
        f.write("};\n\n")
        f.write("#endif /* FOG_POC_SNOW_TIM_DATA_H */\n")
    print("wrote %s (sprite 5x8 indices, 8x16 CLUT halfwords)" % out_path)


if __name__ == "__main__":
    main()
