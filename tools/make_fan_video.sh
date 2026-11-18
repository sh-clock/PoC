#!/bin/bash
# make_fan_video.sh — render the SU0203 nightmare-school FAN demo video.
#
# Two 6-second segments at the engine-native 320x224 @ 30 fps:
#   seg 1: the AUTHENTIC nightmare school env pair {7,4} (map1_s02 header
#          field_16=2 + SU MapFlag_Interior|TwoActiveChunks -> D_800A9F8C,
#          verbatim) — Harry's flashlight lights the fan in the dark;
#   seg 2: interior day pair {2,2} (field_16=1 interior -> D_800A9F84) —
#          brighter view of the spinning fan; the flashlight auto-off
#          day-mode gating (aim 3) rides the identical-pair rule.
# The fan itself is the FAN_HIDE x2 spinRng driver (map1_s02.c:1564-1591,
# verbatim: vz += dt * (Q12_ANGLE(-180/-205deg) - (Rng_Rand16() & 0x1FF)),
# chunk gate (2,3)) — the deterministic --shot replay (fixed RNG seed 1)
# makes every frame a continuous simulation, so the fan spins smoothly.
#
# Output: <outdir>/SU0203_fan_demo.mp4 (640x448 = 2x nearest upscale).
#
# Usage (from anywhere; resolves the repo root from this script's path):
#   tools/make_fan_video.sh <glb> <camdat> <input-dir> <outdir>
#   e.g. tools/make_fan_video.sh glbs/SU0203.glb input/fan_camdat.json \
#           input dist/video
# Requires: the built ./fog_poc in the repo root + ffmpeg on PATH.
set -euo pipefail

GLB="${1:?glb}"; CAMDAT="${2:?camdat}"; INDIR="${3:?input dir}"; OUT="${4:?out dir}"
FPS=30
N=180            # frames per segment (6.0 s)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT/frames_night" "$OUT/frames_day"
cd "$ROOT"

render_seg() {   # render_seg <subdir> <prefix> <extra-args...>
    local dir="$1" pre="$2"; shift 2
    local i t
    i=0
    while [ "$i" -lt "$N" ]; do
        t=$(awk -v i="$i" -v f="$FPS" 'BEGIN { printf "%.6f", i/f }')
        ./fog_poc --glb "$GLB" --camdat "$CAMDAT" --input "$INDIR" "$@" \
            --shot "t=$t,file=${pre}_f$(printf %04d "$i").png" >/dev/null 2>&1
        mv -f "shots/${pre}_f$(printf %04d "$i").png" "$OUT/$dir/"
        i=$((i + 1))
    done
}

render_seg frames_night night
render_seg frames_day   day --envpair 2,2

ffmpeg -y -loglevel error -framerate "$FPS" -i "$OUT/frames_night/night_f%04d.png" \
    -vf "scale=640:448:flags=neighbor" \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$OUT/seg_night.mp4"
ffmpeg -y -loglevel error -framerate "$FPS" -i "$OUT/frames_day/day_f%04d.png" \
    -vf "scale=640:448:flags=neighbor" \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$OUT/seg_day.mp4"
ffmpeg -y -loglevel error -i "$OUT/seg_night.mp4" -i "$OUT/seg_day.mp4" \
    -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" -map "[v]" \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart \
    "$OUT/SU0203_fan_demo.mp4"
echo "video: $OUT/SU0203_fan_demo.mp4"
ffprobe -v error -show_entries format=duration -show_entries stream=width,height,nb_frames \
    -of default=nw=1 "$OUT/SU0203_fan_demo.mp4"
