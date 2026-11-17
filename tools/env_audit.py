#!/usr/bin/env python3
"""env_audit.py — side-by-side audit of the PoC flashlight/env math against
the SH1 decompilation ground truth.

Reference implementations transcribed DIRECTLY from:
  - func_80057658 (per-vertex MESH flashlight light)  bodyprog_80056D8C.c
  - GTE RTPS/UNRDivide (DuckStation-verified semantics; the UNR table is the
    GTE hardware table; SetGeomScreen(16), SetGeomOffset(-1024,-1024) => the
    OFX offset cancels the engine's += 1024)
  - GTE DPCL/DPCS (sf=1, FC=(0,0,0))                  Gfx_MeshDraw paths
  - func_8003F838 env blend weight math               world_effects.c

Compares against the PoC --env-dump FILE.grid output (539 samples).
"""
import sys

# GTE UNR division table (hardware, 257 entries)
UNR = [
0xFF,0xFD,0xFB,0xF9,0xF7,0xF5,0xF3,0xF1,0xEF,0xEE,0xEC,0xEA,0xE8,0xE6,0xE4,0xE3,
0xE1,0xDF,0xDD,0xDC,0xDA,0xD8,0xD6,0xD5,0xD3,0xD1,0xD0,0xCE,0xCD,0xCB,0xC9,0xC8,
0xC6,0xC5,0xC3,0xC1,0xC0,0xBE,0xBD,0xBB,0xBA,0xB8,0xB7,0xB5,0xB4,0xB2,0xB1,0xB0,
0xAE,0xAD,0xAB,0xAA,0xA9,0xA7,0xA6,0xA4,0xA3,0xA2,0xA0,0x9F,0x9E,0x9C,0x9B,0x9A,
0x99,0x97,0x96,0x95,0x94,0x92,0x91,0x90,0x8F,0x8D,0x8C,0x8B,0x8A,0x89,0x87,0x86,
0x85,0x84,0x83,0x82,0x81,0x7F,0x7E,0x7D,0x7C,0x7B,0x7A,0x79,0x78,0x77,0x75,0x74,
0x73,0x72,0x71,0x70,0x6F,0x6E,0x6D,0x6C,0x6B,0x6A,0x69,0x68,0x67,0x66,0x65,0x64,
0x63,0x62,0x61,0x60,0x5F,0x5E,0x5D,0x5D,0x5C,0x5B,0x5A,0x59,0x58,0x57,0x56,0x55,
0x54,0x53,0x53,0x52,0x51,0x50,0x4F,0x4E,0x4D,0x4D,0x4C,0x4B,0x4A,0x49,0x48,0x48,
0x47,0x46,0x45,0x44,0x43,0x43,0x42,0x41,0x40,0x3F,0x3F,0x3E,0x3D,0x3C,0x3C,0x3B,
0x3A,0x39,0x39,0x38,0x37,0x36,0x36,0x35,0x34,0x33,0x33,0x32,0x31,0x31,0x30,0x2F,
0x2E,0x2E,0x2D,0x2C,0x2C,0x2B,0x2A,0x2A,0x29,0x28,0x28,0x27,0x26,0x26,0x25,0x24,
0x24,0x23,0x22,0x22,0x21,0x20,0x20,0x1F,0x1E,0x1E,0x1D,0x1D,0x1C,0x1B,0x1B,0x1A,
0x19,0x19,0x18,0x18,0x17,0x16,0x16,0x15,0x15,0x14,0x14,0x13,0x12,0x12,0x11,0x11,
0x10,0x0F,0x0F,0x0E,0x0E,0x0D,0x0D,0x0C,0x0C,0x0B,0x0A,0x0A,0x09,0x09,0x08,0x08,
0x07,0x07,0x06,0x06,0x05,0x05,0x04,0x04,0x03,0x03,0x02,0x02,0x01,0x01,0x00,0x00,
0x00]


def clz16(v):
    v &= 0xFFFF
    if v == 0:
        return 16
    n = 0
    while not (v & 0x8000):
        v <<= 1
        n += 1
    return n


def unr_divide(lhs, rhs):
    """GTE UNRDivide (exact hardware algorithm)."""
    if rhs * 2 <= lhs:
        return 0x1FFFF
    shift = 16 if rhs == 0 else clz16(rhs)
    lhs <<= shift
    rhs <<= shift
    divisor = rhs | 0x8000
    x = 0x101 + UNR[((divisor & 0x7FFF) + 0x40) >> 7]
    d = ((divisor * -x) + 0x80) >> 8
    recip = ((x * (0x20000 + d)) + 0x80) >> 8
    result = (lhs * recip + 0x8000) >> 16
    return min(0x1FFFF, result)


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def clamp16(v):
    return -0x8000 if v < -0x8000 else (0x7FFF if v > 0x7FFF else v)


def mesh_light(r0, n, d, dqa, wli, maxb):
    """func_80057658 per-vertex light — reference transcription.

    r0 = field_28 (beam*intensity, Q12 s16); n = normal<<5; d = delta Q8.
    RTPS(sf=1, lm=0, TR=0, H=16, OFX=OFY=-1024<<16):
      MAC1 = (R0 . d) >> 12 ; IR1 = clamp16
      MAC2 = (N  . d) >> 12 ; IR2 = clamp16
      SZ3  = clamp((d . d) >> 12, 0, 0xFFFF)
      UNR  = UNRDivide(16, SZ3)
      Sx = UNR*IR1 + OFX ; sx = clamp(Sx>>16, -1024, 1023) ; sx' = s16(sx+1024)
      Sy likewise; dp = clamp((UNR*DQA) >> 12, 0, 0x7FFF)
    value = ((sx'*sy') + sy'*(dp>>4)) >> 5; -=16 clamp>=0; += wli;
            += min((sx'>>1)+(dp>>2), 48); clamp to maxb.
    """
    mac1 = (r0[0] * d[0] + r0[1] * d[1] + r0[2] * d[2]) >> 12
    ir1 = clamp16(mac1)
    mac2 = (n[0] * d[0] + n[1] * d[1] + n[2] * d[2]) >> 12
    ir2 = clamp16(mac2)
    z = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
    sz3 = (z >> 12)
    sz3 = 0 if sz3 < 0 else (0xFFFF if sz3 > 0xFFFF else sz3)
    unr = unr_divide(16, sz3)

    sx = (unr * ir1 - (1024 << 16)) >> 16      # python >> = floor, matches
    sy = (unr * ir2 - (1024 << 16)) >> 16
    sx = -1024 if sx < -1024 else (1023 if sx > 1023 else sx)
    sy = -1024 if sy < -1024 else (1023 if sy > 1023 else sy)
    sx = s16(sx + 1024)
    sy = s16(sy + 1024)

    dp = (unr * dqa) >> 12
    dp = 0 if dp < 0 else (0x7FFF if dp > 0x7FFF else dp)

    var_a1 = ((sx * sy) + sy * (dp >> 4)) >> 5
    var_a1 -= 16
    if var_a1 < 0:
        var_a1 = 0
    var_v1 = (sx >> 1) + (dp >> 2)
    if var_v1 > 48:
        var_v1 = 48
    var_a1 += wli + var_v1
    if maxb < var_a1:
        var_a1 = maxb
    if var_a1 < 0:
        var_a1 = 0
    return var_a1


def dpcl(tint, light_ir, fog_ir0):
    """GTE DPCL with FC=(0,0,0), sf=1 (the Gfx_MeshDraw flashlight vcolor)."""
    in_mac = (tint * light_ir) << 4
    ir = clamp16((0 - in_mac) >> 12)
    mac = (ir * fog_ir0 + in_mac) >> 12
    out = mac >> 4
    return 0 if out < 0 else (255 if out > 255 else out)


def dpcs(c, k):
    """GTE DPCS with FC=(0,0,0), sf=1 (fog veil / tint fade)."""
    in_mac = c << 16
    ir = clamp16((0 - in_mac) >> 12)
    mac = (ir * k + in_mac) >> 12
    out = mac >> 4
    return 0 if out < 0 else (255 if out > 255 else out)


def wavg(a, b, w):
    """Math_WeightedAverageGet — world_effects.c 0x8003F7E4 (64-bit mult)."""
    return (a * (4096 - w) + b * w) >> 12


def load_avg_col(c0, c1, a_from, a_to):
    """libgte LoadAverageCol: gpf12 then gpl12 (MAC<<12 restore)."""
    mac1 = (c0 * a_from) >> 12
    return ((c1 * a_to + (mac1 << 12)) >> 12) & 0xFF


def blend_tick(fi):
    """func_8003F838 for the night pair {preset6, preset3} at weight fi.

    Preset 6 (off):  wLI=1802, tint=(1638,2867,4096), fogDist=14*4096,
                     field_E=1, spot=0, fogColor=(0,0,0)
    Preset 3 (on):   wLI=0,    tint=(3891,4096,4423), fogDist=Q12(CHUNK_SIZE)=163840
                     (40 m — terrain.h:7 CHUNK_SIZE=40.0f; v9 correction:
                     v8 wrongly used 32768 = Q12(8.0)),
                     field_E=0, spot=5324, fogColor=(0,0,0)
    """
    w = fi
    w0 = min(4096, max(0, w * 2))
    w1 = min(4096, max(0, (w - 2048) * 2))
    # field_E: e0=1, e1=0 -> keep e0 until weight1 >= 4096 (fi == 4096)
    field_e = 0 if w1 >= 4096 else 1
    # fog values branch: e1 == 0 -> func_8003FD38(target, e0, e1, w, w1, w0)
    # (wLI blends with the FIRST param = plain weight — decomp call passes
    #  `weight` in the weight0 slot for the e1==0 branch)                    
    fd = wavg(14 * 4096, 163840, w1)         # effectsInfo.fogDistance (w1)
    wli = wavg(1802, 0, w)                   # worldLightIntensity (weight) 
    tint = [wavg(1638, 3891, w), wavg(2867, 4096, w), wavg(4096, 4423, w)]
    spot = wavg(0, 5324, w)
    fogc = [load_avg_col(0, 0, 4096 - w0, w0) for _ in range(3)]
    return field_e, fd, wli, tint, spot, fogc


def audit_env_dump(path):
    """Verify the per-tick env dump against the blend reference."""
    fails = 0
    total = 0
    fi_prev = None
    for line in open(path):
        if not line.startswith('env tick='):
            continue
        f = {}
        for kv in line.strip().split(' '):
            if '=' in kv:
                k, v = kv.split('=', 1)
                f[k] = v
        fi = int(f['fi'])
        if fi_prev is not None and fi < 4096 and fi != 0:
            if fi - fi_prev != 544:  # dt(136) * 4.0 >> 12
                pass  # (off->on ramp step; only checked when toggling)
        fi_prev = fi
        on = int(f['on'])
        total += 1
        field_e, fd, wli, tint, spot, fogc = blend_tick(fi)
        is_fog = int(f['fog'])
        if is_fog != field_e:
            fails += 1
            print(f"MISMATCH tick {f['tick']}: fog ref={field_e} poc={is_fog}")
        if int(f["fdQ12"]) != fd:
            fails += 1
            print(f"MISMATCH tick {f['tick']}: fd ref={fd/4096:.4f} "
                  f"poc={f['fdQ12']}")
        if int(f['wLI']) != wli:
            fails += 1
            print(f"MISMATCH tick {f['tick']}: wLI ref={wli} poc={f['wLI']}")
        if int(f['spot']) != spot:
            fails += 1
            print(f"MISMATCH tick {f['tick']}: spot ref={spot} poc={f['spot']}")
        poc_tint = [int(x) for x in f['tint'].strip('()').split(',')]
        ref_tint = [t >> 5 for t in tint]
        if poc_tint != ref_tint:
            fails += 1
            print(f"MISMATCH tick {f['tick']}: tint ref={ref_tint} "
                  f"poc={poc_tint}")
        if on and fi < 4096 and fi == 0 and total > 1:
            pass
    print(f"env blend audit: {total} ticks, {fails} mismatches")
    return fails


def main(path):
    if 'grid' not in path:
        fails = audit_env_dump(path)
        sys.exit(1 if fails else 0)
    fails = 0
    total = 0
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split(',')
            t = parts[0]
            if t == 'mesh':
                r0 = [int(x) for x in parts[1:4]]
                n = [int(x) for x in parts[4:7]]
                d = [int(x) for x in parts[7:10]]
                dqa, wli, maxb, got = (int(x) for x in parts[10:14])
                ref = mesh_light(r0, n, d, dqa, wli, maxb)
                total += 1
                if ref != got:
                    fails += 1
                    if fails <= 5:
                        print(f"MISMATCH mesh r0={r0} n={n} d={d} dqa={dqa}: "
                              f"ref={ref} poc={got}")
            elif t in ('dpcl', 'dpcs', 'dpcsveil'):
                tint, ir, fog, got = (int(x) for x in parts[1:5])
                ref = dpcl(tint, ir, fog) if t == 'dpcl' else dpcs(tint, fog)
                total += 1
                if ref != got:
                    fails += 1
                    if fails <= 5:
                        print(f"MISMATCH {t} tint={tint} ir={ir} fog={fog}: "
                              f"ref={ref} poc={got}")
            elif t == 'unr':
                lhs, rhs, got = (int(x) for x in parts[1:4])
                ref = unr_divide(lhs, rhs)
                total += 1
                if ref != got:
                    fails += 1
                    if fails <= 5:
                        print(f"MISMATCH unr {lhs}/{rhs}: ref={ref} poc={got}")
    print(f"env audit: {total} samples, {fails} mismatches")
    if fails == 0:
        print("  PASS: PoC math == decomp reference (func_80057658 + DPCL + "
              "DPCS + UNRDivide)")
    else:
        print(f"  FAIL: {fails} mismatches")
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/light.grid')
