#!/usr/bin/env python3
"""Extract the verbatim 4096-entry sine LUT (g_SineTable) from the
silent-hill-decomp libkmath.s assembly and emit it as a C header
(sh_sine_table.h) for embedding into fog_poc.

Ground truth (silent-hill-decomp src/bodyprog/libkmath/libkmath.s):
  q19_12 Math_Sin(q19_12 angle):  idx = angle & 0xFFF; return g_SineTable[idx]
  q19_12 Math_Cos(q19_12 angle):  idx = angle & 0xFFF; return g_SineTable[idx+0x400]
  (NO interpolation; raw s16 LUT entries, Q3.12 values; the table physically
   carries 4096+1024 entries so the Cos window never wraps)

Run: python3 tools/extract_sine_table.py <libkmath.s> [src/sh_sine_table.h]
"""

import re
import sys


def main():
    asm_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "src/sh_sine_table.h"
    src = open(asm_path).read()
    m = re.search(r"dlabel g_SineTable\n(.*?)enddlabel g_SineTable", src, re.S)
    if not m:
        raise SystemExit("g_SineTable not found in " + asm_path)
    vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4})", m.group(1))]
    vals = [v - 0x10000 if v >= 0x8000 else v for v in vals]
    assert len(vals) >= 4096, "table too small: %d" % len(vals)
    vals = vals[:4096 + 1024]  # keep the cos window if present
    n = len(vals)

    with open(out_path, "w") as f:
        f.write("/* ====================================================================\n")
        f.write(" * sh_sine_table.h — the engine's VERBATIM sine LUT (g_SineTable),\n")
        f.write(" * extracted from silent-hill-decomp src/bodyprog/libkmath/libkmath.s\n")
        f.write(" * by tools/extract_sine_table.py — do not edit by hand.\n")
        f.write(" *\n")
        f.write(" * Math_Sin(angle) = kSineTable[angle & 0xFFF]        (s16, Q3.12)\n")
        f.write(" * Math_Cos(angle) = kSineTable[(angle & 0xFFF) + 0x400] (4096+1024\n")
        f.write(" * entries: the extra 1024 are the engine's no-wrap Cos window)\n")
        f.write(" * NO interpolation — raw lookup, exactly like the hardware code.\n")
        f.write(" * ==================================================================== */\n")
        f.write("#ifndef FOG_POC_SH_SINE_TABLE_H\n")
        f.write("#define FOG_POC_SH_SINE_TABLE_H\n\n")
        f.write("/* %d entries (4096 sin + 1024 cos window), s16 Q3.12 */\n" % n)
        f.write("static const short kSineTable[%d] = {\n" % n)
        for i in range(0, n, 16):
            f.write("    " + ", ".join("%6d" % v for v in vals[i:i + 16]) + ",\n")
        f.write("};\n\n")
        f.write("static int sh_math_sin(int angle) { return kSineTable[angle & 0xFFF]; }\n")
        f.write("static int sh_math_cos(int angle) { return kSineTable[(angle & 0xFFF) + 0x400]; }\n\n")
        f.write("#endif /* FOG_POC_SH_SINE_TABLE_H */\n")
    print("wrote %s (%d entries)" % (out_path, n))


if __name__ == "__main__":
    main()
