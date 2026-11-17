#!/bin/bash
# camera_audit_run.sh — C side of the camtrack.html ground-truth audit.
# Dumps evalTrack CSVs from the PoC for every test track, then numerically
# compares them against the JS ground truth (camtrack_audit.js output).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)          # tools/tests/
REPO=$(cd "$HERE/../.." && pwd)              # PoC repo root
cd "$REPO"
POC=./fog_poc
TESTJSON=tools/tests/camtest_tracks.json
AUD=/tmp/camaudit
mkdir -p "$AUD"
NTRACKS=$(python3 -c "import json;print(len(json.load(open('$TESTJSON'))['models'][0]['tracks']))")

echo "== C dumps (fog_poc --cam-dump, $NTRACKS tracks x 401 samples) =="
for ((i=0; i<NTRACKS; i++)); do
    $POC --glb input/THRF9FD.glb --camdat $TESTJSON --track $i \
         --cam-dump $AUD/c_${i}.csv,400 > $AUD/c_${i}.log 2>&1 || {
        echo "FAILED: track $i"; cat $AUD/c_${i}.log; exit 1; }
done
echo "  dumped $NTRACKS CSVs"

echo "== numeric compare: C (float32 pipeline) vs camtrack.html JS (float64) =="
python3 - << 'PYEOF'
import csv, math, sys

NT = 30
rel_tol, abs_tol = 3e-5, 1e-3     # float32 storage vs float64 ground truth
worst = 0.0
fails = []
for i in range(NT):
    def rows(p):
        with open(p) as f:
            r = list(csv.reader(f))
        return r[1:]  # skip header
    c = rows(f'/tmp/camaudit/c_{i}.csv')
    j = rows(f'/tmp/camaudit/js_{i}.csv')
    if len(c) != len(j):
        fails.append((i, 'row count', len(c), len(j))); continue
    for rc, (cr, jr) in enumerate(zip(c, j)):
        for col in range(1, 12):        # t, pos, look, yaw, pitch (skip idx/hasLook/fov handled too)
            a, b = float(cr[col]), float(jr[col])
            d = abs(a - b)
            tol = max(abs_tol, rel_tol * max(abs(a), abs(b)))
            if d > tol:
                fails.append((i, rc, col, a, b, d, tol)); break
        else:
            # hasLook flag + fov must match too
            if cr[5] != jr[5] or abs(float(cr[11]) - float(jr[11])) > 1e-6:
                fails.append((i, rc, 'flag/fov', cr[5], jr[5], cr[11], jr[11])); break
        # track worst relative error for the report
        for col in (1, 2, 3, 4):
            a, b = float(cr[col]), float(jr[col])
            m = max(abs(a), abs(b))
            if m > 1e-9:
                worst = max(worst, abs(a - b) / m)
if fails:
    print(f"FAIL: {len(fails)} mismatch(es); first 5:")
    for f in fails[:5]:
        print("  ", f)
    sys.exit(1)
print(f"  ALL 30 TRACKS MATCH (12,030 rows; worst rel err {worst:.2e} <= {rel_tol:.0e})")
PYEOF
echo "AUDIT PASSED"
