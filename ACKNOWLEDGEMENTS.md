# Acknowledgements & Sources

This project stands on the shoulders of the Silent Hill reverse-engineering
and PS1 emulation communities. All engine behaviour in the renderer was
derived from the sources below — cited function-by-function in
[AUDIT.md](AUDIT.md).

> **This project is 100% AI Slop / Vibe Coded and is non-commercial**
>
> **This project's **CODE** is licenced under the GPL but any included assets **ARE NOT**. Assets are copyrighted by Konami. Using any assets for commercial use is **strictly prohibited** and must be removed immediately** — see
> [Konami's copyright notice](https://eu-support.konami.com/hc/en-gb/articles/9648771731479-Copyrights-Career-Opportunities-Goodies).

## Projects

* **[silent-hill-decomp](https://github.com/shdecompilations/silent-hill-decomp)**
  (shdecompilations) — the Silent Hill 1 (PS1) decompilation. The single
  most important source: the fog ramp, weather/particle systems, env preset
  tables, night pairs, per-vertex flashlight and camera behaviour in this
  renderer were replicated from its C sources (e.g. `world_effects.c`,
  `load_screen.c`, `bodyprog_80056D8C.c`, `vw_calc.c`, `map0_s00`
  particle code). Its `tools/silentassets/extract.py` is the recommended
  disc extractor for your own copy
  ([direct link](https://github.com/shdecompilations/silent-hill-decomp/raw/refs/heads/master/tools/silentassets/extract.py)).
* **[SwanStation](https://github.com/libretro/swanstation)** (libretro) —
  the GPL-3.0 hard fork of DuckStation's libretro core (maintained after
  upstream DuckStation moved away from GPL licensing) — the PS1 emulator
  used as the hardware ground truth for GPU/GTE behaviour: the
  ordering-table raster model (`gpu_sw_rasterizer.inl` pure command-order
  painting — no depth buffer), GTE fixed-point projection and truncation
  semantics (`gte.cpp`), the UNR reciprocal-division table, the dither
  pattern, and 15-bit RGB quantization. The emulation behaviour this
  project validated against descends from DuckStation's original
  GPL-licensed core; SwanStation is the maintained GPL derivative.
* **[glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)**
  (Khronos Group) — the container format the room converter targets.
* **[Zig](https://ziglang.org/)** (Zig Software Foundation) — the
  cross-compilation toolchain used to build the Windows release binary
  (`zig cc -target x86_64-windows-gnu`).

## Konami

Silent Hill was developed by **Konami / Team Silent**. This is a
non-commercial fan research project; all rights to the game and its assets
belong to Konami. Per their
[copyright notice](https://eu-support.konami.com/hc/en-gb/articles/9648771731479-Copyrights-Career-Opportunities-Goodies),
the included sample assets are for non-commercial testing only and must be
removed from any commercial use.

## In-repo audit trail

* [AUDIT.md](AUDIT.md) — function-by-function mapping renderer ↔ decomp.
* [MODES_GUIDE.md](MODES_GUIDE.md) — the 21-preset environment inventory.
* [docs/SH1X_EXTRAS_SCHEMA.md](docs/SH1X_EXTRAS_SCHEMA.md) — the lossless
  IPD→glTF extras schema.
* [docs/archive/](docs/archive/) — the full per-version change history.
