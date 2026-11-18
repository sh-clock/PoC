# Silent Hill 1 — Fog / Snow / Rain / Night / Flashlight PoC

A self-contained C99 **software renderer** that loads a modern GLB (glTF 2.0)
**directly in-app** and reproduces the authentic Silent Hill PS1 engine
**fog**, **snow**, **rain**, **night sequence** and **per-vertex flashlight**,
replicated line-for-line from the
[silent-hill-decomp](https://github.com/shdecompilations/silent-hill-decomp)
sources. No OpenGL, no external assets at runtime: presentation is GDI on
Windows, SDL2/X11 on Linux, ANativeWindow on Android.

> **This project is 100% AI Slop / Vibe Coded and is non-commercial**
>
> **This project's **CODE** is licenced under the GPL but any included assets **ARE NOT**. Assets are copyrighted by Konami. Using any assets for commercial use is **strictly prohibited** and must be removed immediately** — see
> [Konami's copyright notice](https://eu-support.konami.com/hc/en-gb/articles/9648771731479-Copyrights-Career-Opportunities-Goodies).

**Use your own legally-obtained copy of the game**: the repo ships sample
inputs for testing only. See [TOOLS.md](TOOLS.md) for the full
disc-copy → GLB → camera-track pipeline.

## What it renders

* **Rooms** — any `.IPD` room converted to `.glb` by `tools/ipd2gltf.py`
  (the repo ships the base rip files of an outdoor street scene and a
  hospital interior in `input/`; the release zips carry the converted
  GLBs). Textures are embedded in the GLB and decoded in-app with a
  built-in inflate; nothing is extracted to external files.
* **Camera** — `camdat.json` tracks, played by the complete
  `tools/camtrack.html` reference implementation: all 8 track types
  (line / circle / curve / polyline / spiral / zigzag / figure8 / fixed),
  all look modes, the live 160°/s turn filter and the editor's exact
  playback timing. Per-model `nighton` / `flashlighton` / `env` objects
  are parsed with the editor's `sanitizeEnv` semantics verbatim.
* **Fog / snow / rain / night / flashlight** — the engine's own math:
  `MAP_EFFECTS_INFOS` presets, the `WorldEnv_FogDistanceSet` fogRamp LUT,
  the map0_s00 particle system, the `Gfx_MapEnvSet` night pairs and the
  `func_80057658` per-vertex beam. The full function-by-function mapping
  to the decompilation is in [AUDIT.md](AUDIT.md); the 21-mode inventory is
  in [MODES_GUIDE.md](MODES_GUIDE.md).
* **PSX presentation** — the engine-native **320×224 progressive** raster,
  GTE integer-coordinate vertex snapping (the authentic wobble), affine
  texture mapping, 15-bit framebuffer quantization, ordered 4×4 dither and
  a strict 30 fps tick lockstep. `--modern` opts out; `--res 640x360` gives
  a non-engine 16:9 presentation.

## Build

Linux / POSIX (no dependencies beyond libc/libm):

```
make
```

Windows (cross-compile — either classic MinGW-w64 or Zig):

```
make -f Makefile.mingw          # needs x86_64-w64-mingw32-gcc
# or with Zig (bundled MinGW-w64 CRT, no toolchain install):
zig cc -target x86_64-windows-gnu -O2 -std=c99 \
    -o fog_poc.exe src/fog_poc.c -luser32 -lgdi32
```

The Windows exe imports only USER32 / GDI32 / KERNEL32 plus the Windows
Universal CRT — standalone, no external DLL downloads.

## Run

From a repo checkout, first convert the sample scene, then run with
**no arguments** — the realtime window opens and plays the camtrack camera
live against the engine-exact weather:

```
python3 tools/ipd2gltf.py --input input --output glbs --rooms THRF9FD
./fog_poc --glb glbs/THRF9FD.glb --camdat input/camdat.json --input input                                          # realtime window (native 320x224)
./fog_poc --window-size 1920x1080                  # bigger window
./fog_poc --res 640x360                            # NON-ENGINE 16:9 mode
./fog_poc --modern                                  # opt OUT of the wobble
./fog_poc --listmodes                               # the full mode inventory
```

Realtime window keys: `ESC` quit · `SPACE` pause · `R` restart · `+/-` speed
×0.125–×8 · `Left/Right` scrub 1 s · `N` night/nightmare cycle ·
`F` flashlight · `W` weather · `L` lightning · `M` fog · `B` snow ·
`P` PSX wobble · `S` screenshot · `Tab` mode browser · `[` `]` presets ·
`,` `.` authentic pairs · `H` HUD · `V` R2 self-view.

### v33: the room's ORIGINAL environment + animations ON by default

GLBs ripped with the v33 ripper carry `SH1X.env` — the room's own WorldEnv
pair (the map overlay header's `field_16`/`field_17` resolved through
`WorldEnv_MapPresetSet` + `D_800A9F80..A98`, both presets verbatim). Load
such a GLB **without an explicit `--camdat`** and the boot env / boot
weather / flashlight default come FROM THE ROOM — e.g. `SU0203.glb` boots
the nightmare-school pair `{7,4}` with the flashlight ON, `DR0100.glb`
boots the sewer `{6,3}` + the rain recipe. An explicit camdat's `env`
(still) overrides; `--envpair`/`--worldstage`/`--night` still override.

Embedded animations now play BY DEFAULT (the GLB carries them; the players
play them — the user-facing contract). `--no-anims` opts out for the
engine-fresh regression state (event-gated drivers idle at their authored
rot0). The water floor of the sewer rooms (the `DWAVE` materials) renders
the LIVE animated DR_WAVE tile (the `func_8008E5B4` scroll) while the
light is inside the water zone.

Deterministic stills (bit-exact, VLM-verifiable). Each shot simulates a
60 fps playback session from t=0 — turn filter and 30 Hz snow included —
then renders, so it is byte-identical to the realtime benchmark path:

```
./fog_poc --shot t=10.5,file=shot.png
./fog_poc --benchmark --duration 6 --fps 60 --save-final f.png
```

Rendering is fully deterministic: two runs with the same arguments produce
byte-identical PNGs, and `--benchmark --save-final` is bit-identical to
`--shot` at the same track time.

## Tools

* **`tools/ipd2gltf.py`** — converts Silent Hill 1 `.IPD` room files to
  per-room glTF 2.0 `.glb` with embedded textures. Run
  `python3 tools/ipd2gltf.py --help` for options.
* **`tools/camtrack.html`** — the CamTrack Editor: author camera tracks
  (day/night environments, per-track weather) and export `camdat.json`.
  Open it directly in a browser.

See [TOOLS.md](TOOLS.md) for the full pipeline from your own game disc to a
running renderer.

## Known not implemented (by design)

* **Tree leaves as particles** — leaves are baked into the GLB and render
  through the GLTF pipeline; no particle system is added on top.
* **Rain / windy snow variants** — code paths replicated but inert for this
  map's engine preset (wind stays 0, engine-identical).
* **Fog particle sprites** (drifting mist) — the engine spawn table lives in
  the map overlay script, which is not part of the room rip.

## Repository layout

| Path | What it is |
|---|---|
| `src/fog_poc.c` | the engine — single-file C99 software rasterizer |
| `src/*.h` | embedded engine data (snow/rain TIM sprites, font, sine table) |
| `input/` | sample base rip files (IPD/TIM/PLM) + camdat tracks the converter turns into the shipped GLBs |
| `tools/` | `ipd2gltf.py`, `camtrack.html` + asset-prep utilities |
| `tools/tests/` | audit & regression harnesses (see `tools/tests/README.md`) |
| `reference_shots/` | deterministic reference renders for regression comparison |
| `docs/` | SH1X extras schema, cutscene loader design, changelog archive |
| `MODES_GUIDE.md`, `AUDIT.md` | mode inventory, engine audit trail |
| [TOOLS.md](TOOLS.md) | how to use the tools on your own copy of the game |
| [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) | sources, projects and references |

## CI / Releases

`.github/workflows/poc.yml` runs on every push/PR/manual dispatch:

- **Linux build** (`make`) + headless smoke test — `--shot` renders a
  deterministic PNG, proving the binary actually runs, not just links.
- **Windows build** cross-compiled with Zig (imports only
  USER32/GDI32/KERNEL32 + the Universal CRT).

Push a tag `v*` (e.g. `v25.0`) to publish a **GitHub Release** with
**batteries-included one-click test zips** — the engine plus its sample
inputs, structured so you can unzip and immediately run
(see [TESTING.md](TESTING.md)). Releases are used instead of workflow
artifacts — release assets do not count against the Actions artifact
storage quota, and they give downloadable, checksummed, permanent builds.
