#!/usr/bin/env bash
# package_release.sh — build the batteries-included one-click test zips.
#
# Layout (identical for both platforms, so testing instructions match):
#   sh1x-poc-<tag>-linux.zip / sh1x-poc-<tag>-win.zip
#     RUN_THR.sh / RUN_THR.bat      — one-click: the THR street demo
#     RUN_HP0003.sh / RUN_HP0003.bat — one-click: the hospital corridor demo
#     fog_poc / fog_poc.exe         — the engine binary
#     input/THRF9FD.glb + camdat.json   (GLBs are REGENERATED from the
#     input/HP0003.glb + hp_camdat.json  repo's base IPD/TIM/PLM files by
#                                        the CURRENT tools/ipd2gltf.py, so
#                                        the release always matches the
#                                        converter in the repo)
#     README.txt TESTING.md ACKNOWLEDGEMENTS.md (from the repo, if present)
#
# Base files required in input/ (the ONLY game data the repo tracks):
#   THRF9FD.IPD THR_GLB.PLM BG_ETC.TIM THR000{1..4}F.TIM THR7201F/H.TIM
#   HP0003.IPD  HP1F011.TIM HP1F012.TIM HP1F01H.TIM
#
# The Windows zip ships BOTH scripts (.bat calls the exe; .sh kept for
# Git-Bash/WSL users). In the Linux zip the .bat files are dropped.
#
# Usage: bash tools/package_release.sh <tag> <out-dir> <linux-bin> [<win-bin>]
#        (LINUX_BIN=NONE for a windows-only package.)
# (from the repo root; safe in CI — needs coreutils + zip + python3.)
set -euo pipefail

TAG="${1:?usage: package_release.sh TAG OUTDIR LINUX_BIN [WIN_BIN]}"
OUT="${2:?missing out dir}"
LINUX_BIN="${3:?missing linux binary}"
WIN_BIN="${4:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# absolutize OUT up front: the zip steps run inside subshells that cd into
# the staging dir, so a relative out-dir would resolve INSIDE the staging
# tree (or fail to create the zip at all).
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

TMP="$OUT/pkg"
rm -rf "$TMP"
mkdir -p "$TMP/input"

# --- regenerate the GLBs from the repo's BASE files with the CURRENT
# converter (deterministic emission; roundtrip-proven byte-identity to the
# source IPDs). Working copies go to a scratch dir, never into input/. ---
GLB_DIR="$OUT/glbs"
rm -rf "$GLB_DIR"
mkdir -p "$GLB_DIR"
python3 "$ROOT/tools/ipd2gltf.py" --input "$ROOT/input" \
    --output "$GLB_DIR" --rooms THRF9FD,HP0003 >/dev/null
for r in THRF9FD HP0003; do
    [ -f "$GLB_DIR/$r.glb" ] || {
        echo "package_release.sh: converter produced no $r.glb" >&2; exit 1; }
done

# --- batteries: the two sample scenes (THR street + HP0003 hospital) ---
install -m 644 "$GLB_DIR/THRF9FD.glb" "$TMP/input/"
install -m 644 "$ROOT/input/camdat.json" "$TMP/input/"
install -m 644 "$GLB_DIR/HP0003.glb" "$TMP/input/"
install -m 644 "$ROOT/input/hp_camdat.json" "$TMP/input/"

# --- the engine ---
if [ "$LINUX_BIN" = "NONE" ] || [ ! -f "$LINUX_BIN" ]; then
    :   # windows-only packaging: no linux binary/zip
else
    install -m 755 "$LINUX_BIN" "$TMP/fog_poc"
fi

# --- one-click runners (THR: shipped camdat; HP0003: hospital camdat) ---
write_run_thr_sh() {
cat > "$TMP/RUN_THR.sh" <<'EOF'
#!/bin/sh
# One-click: the outdoor street scene (fog/snow/night/flashlight demo).
# Deterministic self-test:  ./RUN_THR.sh --test  (writes shots/SELFTEST_THR.png)
cd "$(dirname "$0")"
if [ "${1:-}" = "--test" ]; then
    exec ./fog_poc --glb input/THRF9FD.glb --camdat input/camdat.json \
        --input input --shot t=10.5,file=SELFTEST_THR.png
fi
exec ./fog_poc --glb input/THRF9FD.glb --camdat input/camdat.json --input input
EOF
chmod 755 "$TMP/RUN_THR.sh"
}
write_run_hp_sh() {
cat > "$TMP/RUN_HP0003.sh" <<'EOF'
#!/bin/sh
# One-click: the hospital corridor (interior day env, no particles).
# Deterministic self-test:  ./RUN_HP0003.sh --test  (writes shots/SELFTEST_HP0003.png)
cd "$(dirname "$0")"
if [ "${1:-}" = "--test" ]; then
    exec ./fog_poc --glb input/HP0003.glb --camdat input/hp_camdat.json \
        --input input --shot t=6,file=SELFTEST_HP0003.png
fi
exec ./fog_poc --glb input/HP0003.glb --camdat input/hp_camdat.json --input input
EOF
chmod 755 "$TMP/RUN_HP0003.sh"
}
write_run_bats() {
cat > "$TMP/RUN_THR.bat" <<'EOF'
@echo off
rem One-click: the outdoor street scene (fog/snow/night/flashlight demo).
rem Deterministic self-test:  RUN_THR.bat --test  (writes shots\SELFTEST_THR.png)
cd /d "%~dp0"
if "%1"=="--test" goto test
fog_poc.exe --glb input\THRF9FD.glb --camdat input\camdat.json --input input
goto :eof
:test
fog_poc.exe --glb input\THRF9FD.glb --camdat input\camdat.json --input input --shot t=10.5,file=SELFTEST_THR.png
EOF
cat > "$TMP/RUN_HP0003.bat" <<'EOF'
@echo off
rem One-click: the hospital corridor (interior day env, no particles).
rem Deterministic self-test:  RUN_HP0003.bat --test  (writes shots\SELFTEST_HP0003.png)
cd /d "%~dp0"
if "%1"=="--test" goto test
fog_poc.exe --glb input\HP0003.glb --camdat input\hp_camdat.json --input input
goto :eof
:test
fog_poc.exe --glb input\HP0003.glb --camdat input\hp_camdat.json --input input --shot t=6,file=SELFTEST_HP0003.png
EOF
}

cat > "$TMP/README.txt" <<'EOF'
Silent Hill 1 PoC — one-click test build (see TESTING.md).
  Linux/macOS :  ./RUN_THR.sh        (street demo)   ./RUN_HP0003.sh
  Windows     :  RUN_THR.bat                          RUN_HP0003.bat
Deterministic self-test (renders a PNG, no window):
  ./RUN_THR.sh --test ; ./RUN_HP0003.sh --test
This project is 100% AI Slop / Vibe Coded and is non-commercial.
CODE is GPL; included assets are NOT — they are copyrighted by Konami,
non-commercial use only. See ACKNOWLEDGEMENTS.md.
EOF

for f in TESTING.md ACKNOWLEDGEMENTS.md TOOLS.md; do
    [ -f "$ROOT/$f" ] && install -m 644 "$ROOT/$f" "$TMP/"
done

write_run_thr_sh
write_run_hp_sh
write_run_bats

# --- the Linux zip (sh runners + binary + docs; .bat dropped) ---
if [ "$LINUX_BIN" != "NONE" ] && [ -f "$LINUX_BIN" ]; then
    rm -f "$OUT/sh1x-poc-$TAG-linux.zip"
    ( cd "$TMP" && zip -q -r "$OUT/sh1x-poc-$TAG-linux.zip" \
        README.txt TESTING.md ACKNOWLEDGEMENTS.md TOOLS.md \
        RUN_THR.sh RUN_HP0003.sh fog_poc input )
fi
rm -f "$TMP/RUN_THR.sh" "$TMP/RUN_HP0003.sh"

if [ -n "$WIN_BIN" ] && [ -f "$WIN_BIN" ]; then
    install -m 755 "$WIN_BIN" "$TMP/fog_poc.exe"
    # Windows zip keeps the .bat runners and .sh companions for
    # Git-Bash/WSL users (they invoke fog_poc.exe); rebuild the .sh
    # (the linux zip step consumed them) pointing at the exe:
    cat > "$TMP/RUN_THR.sh" <<'EOF'
#!/bin/sh
# Git-Bash/WSL runner for the Windows build.
cd "$(dirname "$0")"
if [ "${1:-}" = "--test" ]; then
    exec ./fog_poc.exe --glb input/THRF9FD.glb --camdat input/camdat.json --input input --shot t=10.5,file=SELFTEST_THR.png
fi
exec ./fog_poc.exe --glb input/THRF9FD.glb --camdat input/camdat.json --input input
EOF
    chmod 755 "$TMP/RUN_THR.sh"
    cat > "$TMP/RUN_HP0003.sh" <<'EOF'
#!/bin/sh
# Git-Bash/WSL runner for the Windows build.
cd "$(dirname "$0")"
if [ "${1:-}" = "--test" ]; then
    exec ./fog_poc.exe --glb input/HP0003.glb --camdat input/hp_camdat.json --input input --shot t=6,file=SELFTEST_HP0003.png
fi
exec ./fog_poc.exe --glb input/HP0003.glb --camdat input/hp_camdat.json --input input
EOF
    chmod 755 "$TMP/RUN_HP0003.sh"
    ( cd "$TMP" && zip -q -r "$OUT/sh1x-poc-$TAG-win.zip" \
        README.txt TESTING.md ACKNOWLEDGEMENTS.md TOOLS.md \
        RUN_THR.bat RUN_HP0003.bat RUN_THR.sh RUN_HP0003.sh \
        fog_poc.exe input )
fi

echo "=== zips ==="
ls -la "$OUT"/sh1x-poc-$TAG-*.zip 2>/dev/null || echo "(no zips produced: no linux binary, no windows binary)"
if [ -f "$OUT/sh1x-poc-$TAG-linux.zip" ]; then
    echo "=== contents (linux) ==="
    unzip -l "$OUT/sh1x-poc-$TAG-linux.zip"
fi
if [ -f "$OUT/sh1x-poc-$TAG-win.zip" ]; then
    echo "=== contents (win) ==="
    unzip -l "$OUT/sh1x-poc-$TAG-win.zip"
fi
