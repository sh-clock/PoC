#!/usr/bin/env python3
"""Extract DR_WAVE.TIM -> embedded C arrays for fog_poc.c (the water tile).
Emits: g_drWaveIdx[64][128] (u8 nibbles) + g_drWaveClut[2][16] (u16 5bit).
Layout (from the decomp):
 - upload: s_FsImageDesc D_800A908C {tPage 13 (x832,y0), u0, v0, clut(224,0)}
   (src/bodyprog/screen/data.c:118 NTSC) -> page-relative u 0..127, v 0..63.
 - left 64x64 (u 0..63) = the func_8008E5B4 scroll SOURCE (two 32x32
   windows: (u 0..31, v (ctr>>1)&31..+31) and (u ((ctr+1)>>2)&31..+31,
   v 8..39)) -- verified periodic rows 0/32, 8/40 identical.
 - right half (u 64..127): content tiles at v 0..31, blank at v 32..63.
 - clut row 0 = grayscale ramp (0,29,42,5A,63,73); row 1 = purple-tint.
"""
import struct

TIM = '/home/z/my-project/gamefiles/TIM/DR_WAVE.TIM'
data = open(TIM, 'rb').read()

off = 8
clen, cx, cy, cw, ch = struct.unpack_from('<IHHHH', data, off); off += 12
clut = data[off:off + clen - 12]; off += clen - 12
blen, bx, by, bw, bh = struct.unpack_from('<IHHHH', data, off); off += 12
W, H = bw * 4, bh

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
out.append('/* v32: DR_WAVE.TIM (gamefiles/TIM) — the sewer water tile, VERBATIM')
out.append(' * pixel data. Upload (engine): s_FsImageDesc D_800A908C')
out.append(' * {tPage 13, u 0, v 0, clut (224,0)} (screen/data.c:118 NTSC);')
out.append(' * left 64x64 = the func_8008E5B4 scroll source; clut row 0 = the')
out.append(' * WATER_CLUT (224,0) grayscale ramp used by the two scroll polys. */')
out.append('static const unsigned char g_drWaveIdx[64][128] = {')
for y in range(H):
    out.append('    {' + ','.join('%d' % v for v in px[y]) + '},')
out.append('};')
out.append('static const unsigned short g_drWaveClut[2][16] = {')
for r in range(2):
    vals = []
    for c in range(16):
        w = struct.unpack_from('<H', clut, (r * cw + c) * 2)[0]
        vals.append('0x%04X' % w)
    out.append('    {' + ','.join(vals) + '},')
out.append('};')

open('/home/z/my-project/repos/PoC/src/dr_wave_data.h', 'w').write('\n'.join(out) + '\n')
print('wrote src/dr_wave_data.h —', len(out), 'lines')
# sanity: periodicity check of the left scroll source
same = all(px[y] == px[y + 32] for y in range(32))
print('left-half 32-row periodicity:', same)
