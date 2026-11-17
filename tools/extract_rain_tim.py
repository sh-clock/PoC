#!/usr/bin/env python3
"""Extract the RAIN particle assets from the original BG_ETC.TIM (PSX 4bpp TIM)
and emit them as a C header (rain_tim_data.h) for embedding into fog_poc.

Ground truth (silent-hill-decomp, maps/particle.c Particle_RainDraw):
  - tpage 44 (VRAM 768, ABR=1 additive), same texture page as the snow flakes
    (GameFs_BgEtcGfxLoad: BG_ETC.TIM -> VRAM (768, 0)).
  - FALLING STREAK (state 1, and the type-3 drip):
      setUV4(poly, 10,112, 10,128, 13,112, 13,128)
      -> sprite = VRAM (768, u 10..13, v 112..128): 3 wide x 16 tall, 4bpp
  - SPLASH (type 2 / 242, the landing diamond):
      setUV4(poly, 16,112, 16,127, 31,112, 31,127)
      -> sprite = VRAM (768, u 16..31, v 112..127): 16x16, 4bpp
  - CLUTs (both paths):
      far:  poly->clut = 0x1A30                        = (768, 104)
      mid:  poly->clut = (((depth>>5) + 0x68) << 6) | 0x30
                                     = (768, 104 + (depth>>5)) rows 104..111
    -> 8 CLUTs of 16 halfwords at VRAM (768, 104..111), stored physically as
       pixel-data rows 104..111, halfword columns 0..15 of the texture page
       (same convention as the snow CLUTs at rows 96..103).

Run:  python3 tools/extract_rain_tim.py [input/BG_ETC.TIM] [src/rain_tim_data.h]
"""

import struct
import sys


def parse_tim(data):
    if len(data) < 8:
        raise ValueError("TIM too small")
    magic, flag = struct.unpack_from("<II", data, 0)
    if magic != 0x10:
        raise ValueError("not a TIM (magic %08x)" % magic)
    bpp = 4 if (flag & 0x03) in (0x00, 0x01) else 8 if (flag & 0x03) in (0x02, 0x03) else None
    off = 8
    clut = None
    if flag & 0x08:
        (blen,) = struct.unpack_from("<I", data, off)
        cx, cy, cw, ch = struct.unpack_from("<HHHH", data, off + 4)
        clut = []
        for r in range(ch):
            row = struct.unpack_from("<%dH" % cw, data, off + 12 + r * cw * 2)
            clut.append(list(row))
        off = 8 + blen
    (blen2,) = struct.unpack_from("<I", data, off)
    px, py, pw, ph = struct.unpack_from("<HHHH", data, off + 4)
    pix_off = off + 12
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
    return {"bpp": bpp, "clut": clut, "vram": (px, py),
            "size": (pw * (2 if bpp == 4 else 1), ph), "pixels": pixels}


def halfword_from_pixels(pixels, row, hwcol):
    p = pixels[row][hwcol * 4: hwcol * 4 + 4]
    return p[0] | (p[1] << 4) | (p[2] << 8) | (p[3] << 12)


def main():
    tim_path = sys.argv[1] if len(sys.argv) > 1 else "input/BG_ETC.TIM"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "src/rain_tim_data.h"

    data = open(tim_path, "rb").read()
    tim = parse_tim(data)
    pixels = tim["pixels"]
    W, H = tim["size"]
    print("TIM: %s vram=(%d,%d) pixels=%dx%d" % (tim_path, tim["vram"][0], tim["vram"][1], W, H))
    assert W >= 32 and H >= 128, "TIM too small for rain assets"

    # streak sprite: rows 112..127, cols 10..12 (u 10..13)
    streak = [[pixels[112 + r][c] for c in range(10, 13)] for r in range(16)]
    # splash sprite: rows 112..127, cols 16..31 (u 16..31)
    splash = [[pixels[112 + r][c] for c in range(16, 32)] for r in range(16)]
    # cluts: VRAM (768, 104..111) -> TIM pixel rows 104..111, hw cols 0..15
    cluts = [[halfword_from_pixels(pixels, 104 + r, c) for c in range(16)]
             for r in range(8)]

    with open(out_path, "w") as f:
        f.write("/* ====================================================================\n")
        f.write(" * rain_tim_data.h — RAIN particle assets EMBEDDED in the executable.\n")
        f.write(" * --------------------------------------------------------------------\n")
        f.write(" * Generated from the ORIGINAL BG_ETC.TIM by tools/extract_rain_tim.py\n")
        f.write(" * — do not edit by hand.\n")
        f.write(" *\n")
        f.write(" * Engine placement (silent-hill-decomp maps/particle.c):\n")
        f.write(" *   GameFs_BgEtcGfxLoad: BG_ETC.TIM -> VRAM (768, 0) (tpage 44)\n")
        f.write(" *   Particle_RainDraw:\n")
        f.write(" *     - streak sprite  = VRAM (768, u 10..13, v 112..128) 4bpp\n")
        f.write(" *       (state 1 falling + type 3 drip: setUV4(10,112,10,128,13,112,13,128))\n")
        f.write(" *     - splash sprite  = VRAM (768, u 16..31, v 112..127) 4bpp\n")
        f.write(" *       (type 2/242 landing diamond: setUV4(16,112,16,127,31,112,31,127))\n")
        f.write(" *     - 8 rain CLUTs   = VRAM (768, 104..111), 16 halfwords each\n")
        f.write(" *       (clut 0x1A30 far / ((depth>>5)+0x68)<<6|0x30 rows 104+(depth>>5))\n")
        f.write(" * ==================================================================== */\n")
        f.write("#ifndef FOG_POC_RAIN_TIM_DATA_H\n")
        f.write("#define FOG_POC_RAIN_TIM_DATA_H\n\n")
        f.write("/* 4bpp streak sprite indices, [row 112..127][col 10..12] */\n")
        f.write("static const unsigned char kRainStreak[16][3] = {\n")
        for r in range(16):
            f.write("    { %s },\n" % ", ".join("0x%X" % streak[r][c] for c in range(3)))
        f.write("};\n\n")
        f.write("/* 4bpp splash sprite indices, [row 112..127][col 16..31] */\n")
        f.write("static const unsigned char kRainSplash[16][16] = {\n")
        for r in range(16):
            f.write("    { %s },\n" % ", ".join("0x%X" % splash[r][c] for c in range(16)))
        f.write("};\n\n")
        f.write("/* 8 rain CLUTs (PSX 15-bit halfwords, STP in bit 15),\n")
        f.write(" * [VRAM row 104..111][CLUT entry 0..15] */\n")
        f.write("static const unsigned short kRainClut[8][16] = {\n")
        for r in range(8):
            f.write("    { %s },\n" % ", ".join("0x%04X" % cluts[r][c] for c in range(16)))
        f.write("};\n\n")
        f.write("#endif /* FOG_POC_RAIN_TIM_DATA_H */\n")
    print("wrote %s (streak 16x3, splash 16x16, 8x16 CLUT halfwords)" % out_path)


if __name__ == "__main__":
    main()
