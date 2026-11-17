# TOOLS.md — using the tools on **your own copy of the game**

This project ships sample base rips (`input/THRF9FD.IPD` + its textures,
`input/HP0003.IPD`, + camdat tracks) for testing only. This guide shows
how to produce the same files from **your own legally obtained disc copy**
of Silent Hill 1 (PS1).

> **This project is 100% AI Slop / Vibe Coded and is non-commercial**
>
> **This project's **CODE** is licenced under the GPL but any included assets **ARE NOT**. Assets are copyrighted by Konami. Using any assets for commercial use is **strictly prohibited** and must be removed immediately** — see
> [Konami's copyright notice](https://eu-support.konami.com/hc/en-gb/articles/9648771731479-Copyrights-Career-Opportunities-Goodies).

## What you need

* A PC copy of **Silent Hill 1** (PS1) you legally own — a raw dump of your
  disc (a `.bin/.cue` or `.iso` image works), with its data track intact.
* **Python 3.9+ with `numpy` and `Pillow`** (`pip install numpy pillow`) —
  `ipd2gltf.py` uses numpy for TIM decoding and Pillow for PNG texture
  embedding (both are required whenever textures are embedded, which is
  the default).
* The **file extractor from the decompilation project**:
  `tools/silentassets/extract.py` in
  [shdecompilations/silent-hill-decomp](https://github.com/shdecompilations/silent-hill-decomp) —
  direct link:
  <https://github.com/shdecompilations/silent-hill-decomp/raw/refs/heads/master/tools/silentassets/extract.py>.
* This repo's `tools/ipd2gltf.py` and `tools/camtrack.html`.
* Optionally an emulator (e.g. SwanStation, the GPL DuckStation core) to cross-check your rip against the
  real game, the way this project's audit trail was built.

## Step 1 — extract the game files from your disc dump

`extract.py` does **not** read the ISO directly: it reads the main
executable from the disc image and uses its embedded file table to pull the
data files out of the image. So first get the executable out of your dump:

1. Mount your `.iso` (or open the `.bin` at the filesystem level — the
   executable is a file in the ISO9660 filesystem, e.g. `SLUS_007.07`).
   With a `.bin/.cue` dump, converting to `.iso` first (any standard tool)
   is the simplest route.
2. Copy the executable out (the biggest `SLUS_*` / `SLES_*` / `SLPM_*`
   file at the disc root). On Linux you can mount loopback:
   `sudo mount -o loop game.iso /mnt/game` — or use `7z x game.iso` /
   `isoinfo` to pull files without mounting.
3. Also copy the two big data files `SILENT` and `HILL` from the disc root
   (they hold the room/texture data and the XA audio container).
4. Run the extractor (the output folder is the first positional argument;
   the tool identifies your release by the executable's CRC):

```
python3 extract.py --executable SLUS_007.07 --silentFile SILENT --hillFile HILL ./extracted
```

`--silentFile` takes the `SILENT` file, `--hillFile` takes `HILL`; both are
optional but recommended (without `--hillFile` the XA audio tracks are not
extracted). To just check which release your executable is:

```
python3 extract.py --executable SLUS_007.07 --exeChecksum
```

The tool recognizes, by checksum: the final **NTSC-U 1.1 (`SLUS-00707`)**,
**NTSC-J Rev 0 / Rev 1+2 (`SLPM-86192`)**, **PAL (`SLES-01514`)**, the
preview/review/trade/beta builds, and several demo discs. This project's
reference rip (`THRF9FD` = filetable index 1291) comes from the NTSC
release; PAL and NTSC-J 1.1 have the same room set with a handful of
late-fix audio swaps.

After extraction you have the familiar tree, e.g.:

```
extracted/BG/THRF9FD.IPD      ← the street room your PoC copy uses
extracted/BG/HP0003.IPD       ← hospital interiors (same BG folder)
extracted/BG/HP1F031.TIM ...  ← textures, also under BG/ (embedded into the GLB for you)
```

## Step 2 — convert a room to GLB

`ipd2gltf.py` converts one or more `.IPD` rooms to a self-contained
`.glb` (textures discovered recursively, embedded, lossless roundtrip):

```
python3 tools/ipd2gltf.py --input ./extracted/BG --output ./glbs --rooms THRF9FD,HP0003
```

Never set `--output` to the same folder as the input: the converter always
excludes the output directory from texture scanning, so an in-place
conversion silently drops every texture reference (degraded, textureless
GLB — the mesh count drops and `0 images` appears in the log).

Point `--input` at the folder that holds the room's `.IPD` **and its
textures** (the tool scans the whole tree, including inside ZIP archives).
`--rooms` limits the export; without it every `.IPD` found is converted.
Use `--whole-map` to export one combined GLB per map instead of per-room
GLBs. Each conversion round-trips **byte-identically** back to the source
`.IPD` (verify with `tools/tests/sh1x_roundtrip.py glbs/HP0003.glb
extracted/BG/HP0003.IPD`) — the GLB is a lossless, engine-complete
container (see `docs/SH1X_EXTRAS_SCHEMA.md`).

## Step 3 — author a camera track

Open `tools/camtrack.html` in a browser, drop your `.glb` onto it, and
author a track (line/circle/curve/polyline/spiral/zigzag/figure8/fixed;
look modes path/normal/point/center/fixed; day/night environment, weather,
wobble, dither). Export → `camdat.json`. The editor's World & Weather panel
writes the same `env` object the renderer consumes verbatim.

## Step 4 — run

```
./fog_poc --glb glbs/THRF9FD.glb --camdat camdat.json --input glbs
```

(or place the GLB + camdat in `input/` and run bare `./fog_poc`). Every
engine mechanism — fog ramp, presets, night pairs, flashlight, snow, rain,
turn filter, PSX wobble — is driven from the GLB + camdat exactly as with
the shipped samples.

## Ready-made one-click test releases

Each release tag ships **batteries-included** zips with the engine and its
sample inputs (the THR street + HP0003 hospital camdat/GLB pairs), laid
out so you can unzip and immediately run — see [TESTING.md](TESTING.md).
Those sample assets are Konami-copyrighted and for non-commercial testing
only; replace them with your own extractions for anything else.

## Tool reference

| Tool | Purpose |
|---|---|
| `extract.py` (decomp repo) | disc executable → full game file tree |
| `tools/ipd2gltf.py` | `.IPD` room (+ embedded PLM/TIMs) → `.glb` |
| `tools/camtrack.html` | camera-track editor → `camdat.json` |
| `tools/tests/sh1x_roundtrip.py` | byte-identity proof GLB ↔ IPD |
| `tools/extract_snow_tim.py` / `extract_rain_tim.py` | embed the engine's TIM sprites into `src/*.h` (build-time only) |
| `tools/extract_sine_table.py`, `tools/gen_font8.py` | regenerate embedded sine/font data |
