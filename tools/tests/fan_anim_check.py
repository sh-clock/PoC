#!/usr/bin/env python3
"""fan_anim_check.py — CI proof that the SH1X propAnims actually tick.

Compares two deterministic --shot renders taken ONE ENGINE TICK (1/30 s)
apart with a FIXED camera (--cam override): with the camera frozen, any
pixel change can only come from the animated prop (the SU0203 nightmare
school FAN_HIDE spinRng driver, verbatim map1_s02.c:1564-1591).

Usage: fan_anim_check.py A.png B.png [min_diff_px]
Exit 0  if >= min_diff_px pixels differ (default 500),
Exit 1  otherwise (animation frozen / broken render).
"""
import sys

import numpy as np
from PIL import Image


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    a = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(int)
    b = np.asarray(Image.open(sys.argv[2]).convert("RGB")).astype(int)
    if a.shape != b.shape:
        print(f"shape mismatch {a.shape} vs {b.shape}")
        return 1
    diff = int((a != b).sum())
    # PNG stores packed RGB rows; (a != b) is an (h,w,3) bool -> pixel count
    # needs the per-pixel any() reduction:
    diff_px = int((a != b).any(axis=2).sum())
    need = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    print(f"diff pixels: {diff_px} ({diff_px / (a.shape[0] * a.shape[1]) * 100:.2f}%), "
          f"channel diffs: {diff}, threshold: {need}")
    return 0 if diff_px >= need else 1


if __name__ == "__main__":
    sys.exit(main())
