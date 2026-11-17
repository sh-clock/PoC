# tools/tests — audit & regression harnesses

Everything here is **developer tooling**: it assumes a repo checkout and
(in some cases) reference binaries or Node.js. Nothing in this folder is
needed to build or run the renderer.

| Harness | What it proves |
|---|---|
| `sh1x_roundtrip.py` | GLB → IPD rebuild is **byte-identical** to the source `.IPD` (usage: `python3 sh1x_roundtrip.py <room.glb> <orig.IPD>`) |
| `camtrack_audit.js` | extracts the camtrack.html playback math and dumps per-track CSV ground truth (Node.js; `node camtrack_audit.js ../camtrack.html camtest_tracks.json /tmp/js_` — writes `/tmp/js_<i>.csv`; `camera_audit_run.sh` consumes them as `/tmp/camaudit/js_${i}.csv`) |
| `camera_audit_run.sh` | the C-side of the same audit: `fog_poc --cam-dump` CSVs vs the JS ground truth, numerically compared (30 tracks × 401 samples) |
| `v10_stress_test.py` | infinite mode-cycling + post-wrap flashlight ramp stress (240 mode changes, 4 wraps) |
| `v10_bug_repro.py` | minimal reproductions for the v10 bug class (env freeze at wrap) |
| `v10_ab_regression.sh` | pristine-v9 vs v10 A/B byte-identity sweep (set `V9_BIN`/`V10_BIN`) |
| `env_audit.py` | independent Python reference for the env/light math (light grid dump + compare) |
| `glb_attr_audit.py` / `glb_normal_stats.py` | GLB attribute/normal sanity statistics |
| `pngstat.py` | PNG luminance/color statistics for render comparisons |
| `camtest_tracks.json` | the 30-track corpus (all 8 types × look modes) used by the camera audits |

The engine's own deterministic self-test is simply running the binary:
`./fog_poc --shot t=0` must produce a byte-identical PNG across runs —
that is what CI checks on every push.
