#!/usr/bin/env python3
"""pngstat.py — correct minimal PNG reader + brightness stats (v5 audit tool)."""
import struct, zlib, sys

def rd(p):
    d = open(p, 'rb').read()
    pos = 8; idat = b''; w = h = 0
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos+4])[0]; t = d[pos+4:pos+8]
        if t == b'IHDR':
            w, h = struct.unpack('>II', d[pos+8:pos+16])
        if t == b'IDAT':
            idat += d[pos+8:pos+8+ln]
        pos += 12 + ln
    raw = zlib.decompress(idat)
    st = w*3 + 1
    px = []
    prev = bytearray(w*3)
    for y in range(h):
        f = raw[y*st]
        line = bytearray(raw[y*st+1:(y+1)*st])
        if f == 1:
            for i in range(3, len(line)):
                line[i] = (line[i] + line[i-3]) & 255
        elif f == 2:
            for i in range(len(line)):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(len(line)):
                line[i] = (line[i] + ((line[i-3] if i >= 3 else 0) + prev[i])//2) & 255
        elif f == 4:
            for i in range(len(line)):
                a = line[i-3] if i >= 3 else 0
                b = prev[i]
                c = prev[i-3] if i >= 3 else 0
                pp = a+b-c
                pa, pb, pc = abs(pp-a), abs(pp-b), abs(pp-c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        prev = line
        px.append(bytes(line))
    return w, h, px

def stats(p):
    w, h, px = rd(p)
    mx = 0; s = 0; n = 0; over60 = 0; over100 = 0
    for y in range(h):
        for x in range(w):
            v = (px[y][x*3] + px[y][x*3+1] + px[y][x*3+2]) // 3
            mx = max(mx, v); s += v; n += 1
            if v > 60: over60 += 1
            if v > 100: over100 += 1
    print(f'{p.split("/")[-1]:28s} {w}x{h} max={mx:3d} mean={s/n:6.1f} '
          f'>60:{100.0*over60/n:5.1f}% >100:{100.0*over100/n:5.1f}%')

def diff(pa, pb):
    w, h, a = rd(pa); w, h, b = rd(pb)
    n8 = 0; mx = 0
    for y in range(h):
        for x in range(w):
            va = (a[y][x*3]+a[y][x*3+1]+a[y][x*3+2])//3
            vb = (b[y][x*3]+b[y][x*3+1]+b[y][x*3+2])//3
            dd = abs(va-vb); mx = max(mx, dd)
            if dd > 8: n8 += 1
    print(f'diff {pa.split("/")[-1]} vs {pb.split("/")[-1]}: '
          f'{100.0*n8/(w*h):5.1f}% >8, max {mx}')

if __name__ == '__main__':
    for p in sys.argv[1:]:
        stats(p)
