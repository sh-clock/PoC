#!/usr/bin/env python3
"""Extract WATER.TIM -> embedded C arrays for fog_poc.c (the school water).
Emits: g_waterTimIdx[128][128] (u8 nibbles) + g_waterTimClut[2][16] (u16 5bit).
Layout (from the decomp):
 - upload: s_FsImageDesc D_800A908C {tPage {0,13} (x832,y0), u0, v0,
   clut(224,0)} (src/bodyprog/screen/data.c:118 NTSC; PAL (928,432)
   data.c:95 + CLUT_BASE env_effects.c:107) -> page-relative u 0..127,
   v 0..127 (one 4bpp texture page quadrant).
 - sampled by water.c with tpage 45 (0x2D: page-13, ABR-1 ADDITIVE,
   4bpp) + clut words 0xE (row 0)/0x4E (row 1): the stream strip
   u 64..95 v 64..127, the droplet sprites u 64..95/96..127
   v 0..63/64..127, the map1_s03 spray frames u 0..63 v 32*frame..+31.
 - the waterTex EXTRAs (v39 ripper, _room_water_tex) re-embed the same
   sheet per SU room and OVERRIDE these compiled-in defaults at load.

Provenance (V41 audit D-5): src/water_tim_data.h was committed at v39
(ea07754) from the CDN upload (sh1_assets/TIM/WATER.TIM); THAT commit
message claimed an extract_water_tim.py that was never committed
(git ls-tree ea07754 tools/ — the documented-intent gap this script
closes). WATER.TIM is NOT in the repo: default input/WATER.TIM, or
pass the path (the GLB waterTex extras are a second source).

Run:  python3 tools/extract_water_tim.py [WATER.TIM] [src/water_tim_data.h]
"""
import os
import struct
import sys

TIM = sys.argv[1] if len(sys.argv) > 1 else 'input/WATER.TIM'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'src/water_tim_data.h'

if not os.path.exists(TIM):
    raise SystemExit(
        "WATER.TIM not found: " + TIM + "\n"
        "The committed src/water_tim_data.h was extracted at v39 from the\n"
        "CDN upload (sh1_assets/TIM/WATER.TIM), which is not in this repo.\n"
        "Place the file at input/WATER.TIM or pass its path as the first\n"
        "argument (the GLB SH1X.waterTex extras are a second source).")

data = open(TIM, 'rb').read()

magic, flags = struct.unpack_from('<II', data, 0)
assert magic == 0x10, 'not a TIM'
assert (flags & 8) and (flags & 3) == 0, \
    'expected 4bpp CLUT TIM (PMODE bits 0-1 == 0, CLT bit 3)'

off = 8
clen, cx, cy, cw, ch = struct.unpack_from('<IHHHH', data, off); off += 12
clut = data[off:off + clen - 12]; off += clen - 12
blen, bx, by, bw, bh = struct.unpack_from('<IHHHH', data, off); off += 12
W, H = bw * 4, bh
assert (W, H) == (128, 128) and (cw, ch) == (16, 2), \
    f'unexpected WATER.TIM geometry: clut {cw}x{ch}, pixels {W}x{H}'

px = []
p = off
for y in range(H):
    row = []
    for hw in range(bw):
        w = struct.unpack_from('<H', data, p)[0]; p += 2
        for k in range(4):
            row.append((w >> (k * 4)) & 0xF)
    px.append(row)

out = []
out.append('/* v39: WATER.TIM (sh1_assets/TIM, the CDN upload) — the school')
out.append(' * water sheet, VERBATIM pixel data (128x128 4bpp + 2 CLUT')
out.append(' * rows). Upload (engine): s_FsImageDesc D_800A908C')
out.append(' * {tPage {0,13}, u 0, v 0, clut (224,0)} (screen/data.c:118')
out.append(' * NTSC; PAL (928,432) data.c:95 + CLUT_BASE env_effects.c:107).')
out.append(' * Sampled by water.c with tpage 45 (0x2D: page-13, ABR-1')
out.append(' * ADDITIVE, 4bpp) + clut words 0xE (row 0)/0x4E (row 1):')
out.append(' * the stream strip u 64..95 v 64..127, the droplet sprites')
out.append(' * u 64..95/96..127 v 0..63/64..127, the map1_s03 spray frames')
out.append(' * u 0..63 v 32*frame..+31. The waterTex EXTRAs (v39 ripper)')
out.append(' * OVERRIDE these compiled-in defaults at load. */')
out.append('static const unsigned char g_waterTimIdx[128][128] = {')
for y in range(H):
    out.append('    {' + ','.join('%d' % v for v in px[y]) + '},')
out.append('};')
out.append('static const unsigned short g_waterTimClut[2][16] = {')
for r in range(2):
    vals = []
    for c in range(16):
        w = struct.unpack_from('<H', clut, (r * cw + c) * 2)[0]
        vals.append('0x%04X' % w)
    out.append('    {' + ','.join(vals) + '},')
out.append('};')

open(OUT, 'w').write('\n'.join(out) + '\n')
print('wrote', OUT, '—', len(out), 'lines')
# sanity: the sheet's nonzero nibble population (the stream/droplet/spray
# windows live in u 0..127; an all-zero sheet means a wrong source file)
nz = sum(1 for y in range(H) for x in range(W) if px[y][x])
print('nonzero texels: %d of %d' % (nz, W * H))
