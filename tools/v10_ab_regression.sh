#!/usr/bin/env bash
# v10 zero-regression A/B: PRISTINE v9 shipped binary vs v10 build.
# The praised v9 paths (night/flashlight/dark, every preset/pair, weather,
# modern, turn, benchmark bridge) must render BYTE-IDENTICAL.
# The two INTENTIONAL divergences (the fixes) are asserted separately:
#   - --day boot: v9 black/broken vs v10 correct fog
#   - shot t>49.88 (track wrap): v9 frozen env vs v10 live env
set -u
V9="${V9_BIN:-./fog_poc}"
V10="${V10_BIN:-./fog_poc}"
OUT=/home/z/my-project/scripts/v10_tests/ab
mkdir -p "$OUT"
cd "$(dirname "$0")/.."   # both read the same input/ via --glb
GLB=input/THRF9FD.glb
CAM=input/camdat.json

PASS=0; FAIL=0
ab() {  # ab <name> <args...>
    local name="$1"; shift
    "$V9"  --glb "$GLB" --camdat "$CAM" "$@" --out "$OUT" --shot t=10.5,file="v9_${name}.png" >/dev/null 2>&1
    "$V10" --glb "$GLB" --camdat "$CAM" "$@" --out "$OUT" --shot t=10.5,file="v10_${name}.png" >/dev/null 2>&1
    if cmp -s "$OUT/v9_${name}.png" "$OUT/v10_${name}.png"; then
        echo "  IDENTICAL  $name"; PASS=$((PASS+1))
    else
        echo "  **DIFFERS  $name"; FAIL=$((FAIL+1))
    fi
}

echo "== A/B: default + night family (the praised v9 rendering) =="
ab default
ab night_fl        --night --flashlight
ab night_off       --night --no-flashlight
ab nightmare_fl    --nightpair 7,4 --night --flashlight
ab nightmare_off   --nightpair 7,4 --night --no-flashlight

echo "== A/B: all 21 presets (self-pairs) =="
for p in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    ab "p${p}" --envpair $p,$p
done

echo "== A/B: the 24 authentic pairs =="
ab pair_6_10   --envpair 6,10
ab pair_6_5    --envpair 6,5 --flashlight
ab pair_6_6    --envpair 6,6
ab pair_19_4   --envpair 19,4 --flashlight
ab pair_6_12   --envpair 6,12
ab pair_6_20   --envpair 6,20
ab pair_7_9    --envpair 7,9
ab pair_7_7    --envpair 7,7
ab pair_14_14x --envpair 14,14 --flashlight
ab pair_11_11x --envpair 11,11
ab pair_17_17x --envpair 17,17
ab pair_10_10x --envpair 10,10
ab pair_15_15x --envpair 15,15
ab pair_16_16x --envpair 16,16 --flashlight
ab pair_18_18x --envpair 18,18 --flashlight
ab pair_4_4x   --envpair 4,4 --flashlight
ab pair_3_3x   --envpair 3,3 --flashlight
ab pair_13_13x --envpair 13,13
ab pair_5_5x   --envpair 5,5 --flashlight
ab pair_9_9x   --envpair 9,9

echo "== A/B: weather / lensflare / lightning / modern / turn =="
ab rain         --weather 6
ab snow2        --weather 2
ab lensflare3   --envpair 2,2 --lensflare 3
ab lightning    --night --flashlight --lightning
ab modern       --night --flashlight --modern
ab modern_day_f --day --fog --modern
ab worldstage3  --worldstage 3

echo "== A/B: benchmark bridge (the window<->deterministic equality) =="
"$V9"  --glb "$GLB" --camdat "$CAM" --night --flashlight --duration 6 --save-final "$OUT/v9_bridge.png" --out "$OUT" >/dev/null 2>&1
"$V10" --glb "$GLB" --camdat "$CAM" --night --flashlight --duration 6 --save-final "$OUT/v10_bridge.png" --out "$OUT" >/dev/null 2>&1
if cmp -s "$OUT/v9_bridge.png" "$OUT/v10_bridge.png"; then
    echo "  IDENTICAL  benchmark bridge t=6"; PASS=$((PASS+1))
else
    echo "  **DIFFERS  benchmark bridge t=6"; FAIL=$((FAIL+1))
fi
"$V9"  --glb "$GLB" --camdat "$CAM" --night --flashlight --duration 12 --save-final "$OUT/v9_midturn.png" --out "$OUT" >/dev/null 2>&1
"$V10" --glb "$GLB" --camdat "$CAM" --night --flashlight --duration 12 --save-final "$OUT/v10_midturn.png" --out "$OUT" >/dev/null 2>&1
if cmp -s "$OUT/v9_midturn.png" "$OUT/v10_midturn.png"; then
    echo "  IDENTICAL  mid-turn t=12 (720-frame realtime bridge)"; PASS=$((PASS+1))
else
    echo "  **DIFFERS  mid-turn t=12 (720-frame realtime bridge)"; FAIL=$((FAIL+1))
fi

echo ""
echo "== A/B RESULT: $PASS identical, $FAIL differ =="
echo ""
echo "== THE TWO INTENTIONAL FIX DIVERGENCES (must DIFFER) =="
"$V9"  --glb "$GLB" --camdat "$CAM" --day --out "$OUT" --shot t=10.5,file=v9_dayboot.png >/dev/null 2>&1
"$V10" --glb "$GLB" --camdat "$CAM" --day --out "$OUT" --shot t=10.5,file=v10_dayboot.png >/dev/null 2>&1
if cmp -s "$OUT/v9_dayboot.png" "$OUT/v10_dayboot.png"; then
    echo "  UNEXPECTED same day boot (fix failed?)"
else
    echo "  DIFFERS (correct): --day boot — v9 broken black vs v10 engine fog"
fi
timeout 20 "$V9"  --glb "$GLB" --camdat "$CAM" --night --flashlight --out "$OUT" --shot t=60,file=v9_wrap60.png >/dev/null 2>&1
timeout 20 "$V10" --glb "$GLB" --camdat "$CAM" --night --flashlight --out "$OUT" --shot t=60,file=v10_wrap60.png >/dev/null 2>&1
if [ -f "$OUT/v10_wrap60.png" ] && [ ! -f "$OUT/v9_wrap60.png" ]; then
    echo "  CONFIRMED: v9 --shot t=60 INFINITE-LOOPED (killed by timeout, no PNG); v10 wrote it (loop fixed)"
elif cmp -s "$OUT/v9_wrap60.png" "$OUT/v10_wrap60.png"; then
    echo "  UNEXPECTED same wrap shot (fix failed?)"
else
    echo "  DIFFERS (correct): shot t=60 (past the 49.88 s wrap) — v9 frozen env vs v10 live env"
fi
exit $FAIL
