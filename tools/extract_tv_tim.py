#!/usr/bin/env python3
"""Extract TV1/TV2/TV3.TIM -> embedded C arrays for fog_poc.c (the TV paint).

Emits src/tv_tim_data.h:
  g_tv1Idx[256][128] / g_tv2Idx[256][128] / g_tv3Idx[128][128]  (u8 texel
  indices, 8bpp) + g_tv{1,2,3}Clut[rows][16] (u16 BGR555).

Ground truth (decomp):
 - func_800D7450 (map4_s03.c:415-465) loads the three TIMs:
     case 0: TV1.TIM -> D_800DB91C {tPage[1]=29, u=0, v=0,   clutY=0}
     case 1: TV2.TIM -> D_800DB91C {tPage[1]=12, u=32, v=0,  clutY=5}
     case 2: TV3.TIM -> D_800DB91C {tPage[1]=28, u=0, v=128, clutY=10}
 - Fs_QueuePostLoadTim (src/main/fs_queue.c:643-682) relocates the pixel
   rect to (u + (tPage[1]&0xF)<<6, v + ((tPage[1]<<4)&0x100)) and the CLUT
   rect to (clutX, clutY) with the static D_800DB91C clutX=448 (USA).
   => TV1 pixels at VRAM halfwords (832..863, rows 256..511)
      TV2 pixels at VRAM halfwords (800..863, rows 0..255)
      TV3 pixels at VRAM halfwords (768..831, rows 384..511)
      CLUT rows (16 entries wide) at (448, 0..2 / 5..6 / 10..11).
 - func_800D88C8 (map4_s03.c:1252-1409) paints the screen quads with
   tpage (field_0 & 0x1F) | 0x20 (8bpp), clut = field_2, UV windows
   (field_4..9 + the LCG); SwanStation's Palette8Bit sampler
   (src/core/gpu_sw_backend.cpp ShadePixel) resolves
   texel(u,v) -> halfword(tpBase + u/2, tpY + v) -> index -> VRAM
   (448 + index, clutRow).
"""
import struct

TIM_DIR = '/home/z/my-project/sh1_assets/TIM'

def parse_tim(name):
    d = open(f'{TIM_DIR}/{name}.TIM', 'rb').read()
    magic, flags = struct.unpack_from('<II', d, 0)
    assert magic == 0x10
    assert (flags & 8) and ((flags >> 3) & 3) == 1, 'expected 8bpp CLUT TIM'
    o = 8
    clen = struct.unpack_from('<I', d, o)[0]; o += 4
    cx, cy, cw, ch = struct.unpack_from('<4H', d, o); o += 8
    raw = d[o:o + clen - 12]; o += clen - 12
    rows = [struct.unpack_from(f'<{cw}H', raw, r * cw * 2) for r in range(ch)]
    plen = struct.unpack_from('<I', d, o)[0]; o += 4
    px, py, pw, ph = struct.unpack_from('<4H', d, o); o += 8
    pix = d[o:o + plen - 12]
    # 8bpp: each halfword (pw per row) = 2 texels
    texels = []
    for y in range(ph):
        row = []
        for hw in range(pw):
            w = struct.unpack_from('<H', pix, (y * pw + hw) * 2)[0]
            row.append(w & 0xFF)
            row.append((w >> 8) & 0xFF)
        texels.append(row)
    return dict(name=name, clut_rows=rows, texels=texels, w=pw * 2, h=ph,
                pix_rect=(px, py, pw, ph))

def emit():
    out = []
    out.append('/* v36: TV1/TV2/TV3.TIM (TIM dir) — the town-center TV screen')
    out.append(' * textures, VERBATIM 8bpp texel indices + CLUT rows. Upload')
    out.append(' * (engine): func_800D7450 (map4_s03.c:415-465) +')
    out.append(' * Fs_QueuePostLoadTim (fs_queue.c:643-682) with the static')
    out.append(' * D_800DB91C clutX=448: TV1 -> pixels (832..863, rows')
    out.append(' * 256..511), CLUT rows 0..2; TV2 -> pixels (800..863, rows')
    out.append(' * 0..255), CLUT rows 5..6; TV3 -> pixels (768..831, rows')
    out.append(' * 384..511), CLUT rows 10..11. Sampled by func_800D88C8')
    out.append(' * (map4_s03.c:1252-1409) through the SwanStation Palette8Bit')
    out.append(' * path (gpu_sw_backend.cpp ShadePixel). */')
    for tv, n in (('tv1', 'TV1'), ('tv2', 'TV2'), ('tv3', 'TV3')):
        t = parse_tim(n)
        h, w = t['h'], t['w']
        out.append(f'static const unsigned char g_{tv}Idx[{h}][{w}] = {{')
        for y in range(h):
            out.append('    {' + ','.join('%d' % v for v in t['texels'][y]) + '},')
        out.append('};')
        rows = t['clut_rows']
        out.append(f'static const unsigned short g_{tv}Clut[{len(rows)}][16] = {{')
        for r in rows:
            out.append('    {' + ','.join('0x%04X' % v for v in r) + '},')
        out.append('};')
    open('/home/z/my-project/repos/PoC/src/tv_tim_data.h', 'w').write('\n'.join(out) + '\n')
    print('wrote src/tv_tim_data.h', len(out), 'lines')
    for tv, n in (('tv1', 'TV1'), ('tv2', 'TV2'), ('tv3', 'TV3')):
        t = parse_tim(n)
        print(f"  {n}: {t['w']}x{t['h']} texels, clut {len(t['clut_rows'])} rows")

if __name__ == '__main__':
    emit()
