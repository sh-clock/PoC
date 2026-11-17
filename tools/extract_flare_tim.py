#!/usr/bin/env python3
"""Extract the LENS FLARE sprites + CLUT rows from the original BG_ETC.TIM
(PSX 4bpp TIM) and emit them as a C header (flare_tim_data.h) for embedding
directly into the fog_poc executable — the exact pattern of the verified
snow/rain extractors.

Ground truth (silent-hill-decomp src/bodyprog/gfx/lens_flare.c):
  - GameFs_BgEtcGfxLoad (world/draw.c:78-90) loads BG_ETC.TIM into
    tpage {0,12} clut (192,0) NTSC — VRAM page base (768,0), CLUT rows
    at x=192.
  - shLensFlareEffect_Draw (lens_flare.c:270-277): CLUT_X 192, CLUT_Y 0
    (NTSC). Sprites sample CLUT rows +5, +6, +7 at x=192:
      * core quads + 3rd quad + ghost3 (tpage 44):  clut (192, 6)
      * streaks (tpage 0x2C=44):                    clut (192, 5)
      * ghosts 1+2 (tpage 44), ghost3 (tpage 76):   clut (192, 7)
  - Sprite UV windows (setUV4 calls, lens_flare.c:326-487):
      * core quads:    u 0..63  v 0..63   (64x64, clut+6)
      * streaks:        u 0x20..0x3F v 0x40..0x5F  (32x32, clut+5)
      * ghosts 1+2:     u 0x40..0x7F v 0..0x3F    (64x64, clut+7)
      * ghost3:         u 0..0x3F v 0..0x3F       (64x64, clut+6, tpage 76)
  - WATER shimmer sprites (sewer DR/DRU; lens_flare.c:525-680):
      tpage 45 = VRAM page 13 base (832,0)?? NO — tpage 45 is page 13
      (bits: tpage = 45 -> tp 13 -> VRAM x 13*64=832); the engine loads
      DR_WAVE.TIM via s_FsImageDesc D_800A908C { tPage{0,13}, clut 224,0 }
      (NTSC screen/data.c). Windows:
      * wave tiles:  u 0..32 v (ctr&0x1F)..+32 and u ((ctr+1)>>2)&0x1F..+32
                    v 8..40 (32x32 tiles, clut (224,0))
      * light glint: u 64..127 v 0..31 (64x32, clut (224,1))
      The WATER.TIM/DR_WAVE.TIM FILES ARE NOT PRESENT locally (sewer rip
      not provided) — so this extractor emits ONLY the BG_ETC flare
      sprites; water pixels come from the consumer-side resolver (silent
      no-op if absent).

TIM 4bpp pixel (x,y) maps to VRAM (768 + x, y); each halfword packs 4
consecutive 4bpp pixels."""

import struct
import sys
import os


def parse_tim(data):
    if len(data) < 8:
        raise ValueError("TIM too small")
    magic, flag = struct.unpack_from("<II", data, 0)
    if magic != 0x10:
        raise ValueError("not a TIM")
    has_clut = bool(flag & 0x08)
    off = 8
    clut = None
    if has_clut:
        clen = struct.unpack_from("<I", data, off)[0]
        cx, cy, cw, ch = struct.unpack_from("<HHHH", data, off + 4)
        clut = data[off + 12: off + 12 + cw * 2 * ch]
        off += clen
    ilen = struct.unpack_from("<I", data, off)[0]
    ix, iy, iw, ih = struct.unpack_from("<HHHH", data, off + 4)
    img = data[off + 12: off + 12 + iw * 2 * ih]
    return {"cx": cx, "cy": cy, "cw": cw, "ch": ch, "clut": clut,
            "ix": ix, "iy": iy, "iw": iw, "ih": ih, "img": img}


def idx_plane(tim):
    """Decode the 4bpp sheet into a per-pixel index array.

    The real BG_ETC.TIM's CLUT block is 16x11 halfwords (x=0!) but the
    IMAGE block is 32 halfwords x 256 rows = 128x256 texels: the CLUT
    x-coordinates are the UPLOAD DESCRIPTOR's (0), not VRAM — the loader
    (s_FsImageDesc clutX=192) relocates them. Window v (row) indexes the
    image rows directly; window u indexes texel columns 0..127.
    """
    w, h = tim["iw"] * 4, tim["ih"]   # 128 x 256 texels
    n = tim["iw"] * 2 * tim["ih"]     # byte size (iw halfwords per row)
    img = tim["img"]
    if len(img) < n:
        img = img + b"\x00" * (n - len(img))
    out = bytearray(w * h)
    for y in range(h):
        row = img[y * tim["iw"] * 2:(y + 1) * tim["iw"] * 2]   # bytes
        for hw_i in range(len(row) // 2):
            b = struct.unpack_from("<H", row, hw_i * 2)[0]
            x = hw_i * 4
            out[y * w + x] = b & 0x0F
            out[y * w + x + 1] = (b >> 4) & 0x0F
            out[y * w + x + 2] = (b >> 8) & 0x0F
            out[y * w + x + 3] = (b >> 12) & 0x0F
    return w, h, bytes(out)


def clut_rows(tim, x_base, y_base, rows):
    """Extract consecutive CLUT rows of 16 halfwords at (x_base, y_base+i).
    In the TIM's own CLUT block coordinates: the loaded VRAM x maps to
    clut-relative x = x_base - 192 (BG_ETC's clut sits at VRAM 192)."""
    rel_x = (x_base - 192) // 2   # halfword columns (VRAM x is in halfwords)
    out = []
    for r in range(rows):
        off = (y_base + r) * tim["cw"] * 2 + rel_x * 2
        out.append(struct.unpack_from("<16H", tim["clut"], off))
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "input/BG_ETC.TIM"
    dst = sys.argv[2] if len(sys.argv) > 2 else "src/flare_tim_data.h"
    if not os.path.exists(src):
        print(f"BG_ETC.TIM not found at {src} — flare sprites cannot be "
              f"extracted (the feature no-ops in consumers)", file=sys.stderr)
        return 1
    tim = parse_tim(open(src, "rb").read())
    w, h, idx = idx_plane(tim)

    # windows (u0, v0, u1, v1) — engine setUV4 corners
    wins = {
        "kFlareCore":   (0, 0, 63, 63),     # clut+6 (192,6)
        "kFlareStreak": (0x20, 0x40, 0x3F, 0x5F),   # clut+5 (192,5)
        "kFlareGhost":  (0x40, 0, 0x7F, 0x3F),     # clut+7 (192,7)
        "kFlareGhost3": (0, 0, 0x3F, 0x3F),        # clut+6 (192,6) tpage76
    }
    # CLUT rows at VRAM x=192: rel_x = 0
    cluts = {
        "kFlareClutStreak": clut_rows(tim, 192, 5, 1)[0],   # row +5
        "kFlareClutCore":   clut_rows(tim, 192, 6, 1)[0],   # row +6
        "kFlareClutGhost":  clut_rows(tim, 192, 7, 1)[0],   # row +7
    }

    with open(dst, "w") as f:
        f.write("/* ====================================================================\n")
        f.write(" * flare_tim_data.h — LENS FLARE sprites + CLUTs from the original\n")
        f.write(" * BG_ETC.TIM (engine filetable 1799), extracted by\n")
        f.write(" * tools/extract_flare_tim.py — do not edit by hand.\n")
        f.write(" *\n")
        f.write(" * Ground truth (decomp lens_flare.c): sprites are POLY_FT4 tpage 44/76\n")
        f.write(" * sampling BG_ETC sheet windows with CLUT rows at VRAM (192,5/6/7)\n")
        f.write(" * NTSC. Core 64x64 clut+6; streaks 32x32 clut+5; ghosts 64x64 clut+7\n")
        f.write(" * (+ghost3 64x64 clut+6 tpage 76). All SemiTrans mode-1.\n")
        f.write(" * ==================================================================== */\n")
        f.write("#ifndef FOG_POC_FLARE_TIM_DATA_H\n#define FOG_POC_FLARE_TIM_DATA_H\n\n")
        for name, (u0, v0, u1, v1) in wins.items():
            ww, wh = u1 - u0 + 1, v1 - v0 + 1
            f.write(f"/* {name}: window u[{u0},{u1}] v[{v0},{v1}] = {ww}x{wh} indices */\n")
            f.write(f"static const unsigned char {name}[{wh}][{ww}] = {{\n")
            for y in range(v0, v1 + 1):
                f.write("    {")
                f.write(",".join(str(idx[y * w + u]) for u in range(u0, u1 + 1)))
                f.write("},\n")
            f.write("};\n\n")
        for name, row in cluts.items():
            f.write(f"/* {name}: 16 halfwords, VRAM (192,{5 if 'Streak' in name else 6 if 'Core' in name else 7}) */\n")
            f.write(f"static const unsigned short {name}[16] = {{\n    ")
            f.write(",".join(f"0x{v:04X}" for v in row))
            f.write(",\n};\n\n")
        f.write("#endif /* FOG_POC_FLARE_TIM_DATA_H */\n")
    print(f"wrote {dst} (sheet {w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
