# fog_PoC v13 — the camtrack_v2 camdat env object + the editor's Effects-Off view

v13 is a **strictly additive** release over the v12 ground truth: every new
code path is gated on the presence of the per-model `env` object in
camdat.json, so **legacy camdat.json files parse and render byte-identically
to v12** (proven: md5-equal deterministic renders on the shipped camdat AND
on all 21 `--envpair k,k` modes).

## What v13 adds

### 1. The v2 camdat format — `models[].env`

The camtrack_v2 editor's World & Weather panel saves the full world
selection alongside the legacy flags (which it DERIVES from it):

```json
{
  "format": "camdat", "version": 1,
  "models": [{
    "file": "THRF9FD.glb",
    "fogon": true, "nighton": true, "flashlighton": true,   /* legacy, derived */
    "env": {
      "pair": [7, 4],          /* MAP_EFFECTS_INFOS indices, 0..20 (slot A/B) */
      "weatherTarget": 6,      /* sharedFunc_800D0B18 arg, 0..8 (runtime)      */
      "bootWeather": 5,        /* Particle_EnvironmentSet recipe, -1..6        */
      "lensFlare": 2,          /* enum-2 light source, 0..5                    */
      "flashlightOn": true,    /* strict boolean                               */
      "psxWobble": false,      /* strict boolean (false = --modern)            */
      "dither": true,          /* strict boolean                               */
      "particles": false,      /* strict boolean (false = --nosnow)            */
      "engine": true           /* strict boolean (false = --nofog look)        */
    },
    "tracks": [ ... unchanged v1 track format ... ]
  }]
}
```

All `env` fields are optional (per-field presence). The parser mirrors the
editor's `sanitizeEnv()` whitelist verbatim: strict JSON booleans (numbers /
strings / null are rejected as absent), clamps `pair` 0..20,
`weatherTarget` 0..8, `bootWeather` -1..6, `lensFlare` 0..5, and float
values truncate toward zero like the editor's `| 0`.

### 2. Boot priority — CLI flags > camdat env > camdat legacy flags > defaults

| env field      | boot effect (when the CLI is silent)                     |
|----------------|-----------------------------------------------------------|
| `pair`         | `Gfx_MapEnvSet(A,B)` at boot — supersedes the `nighton`-derived pair (exactly like an explicit `--envpair A,B`; the night flag reads 0). `--night`/`--day`/`--worldstage`/`--envpair`/`--preset` still win. |
| `flashlightOn` | the boot flashlight state (over `flashlighton`; `--flashlight`/`--no-flashlight` win). The engine auto-off rule still applies on identical pairs. |
| `bootWeather`  | `Particle_EnvironmentSet(N, 1)` at load — the INSTANT map-load recipe, applied **unconditionally including recipe 2** ("snow + wind flag") exactly like the editor's `setBootWeather` (the v8 CLI's `!= 2` guard is a CLI-only quirk; there recipe 2 stays the map0 default). |
| `weatherTarget`| `sharedFunc_800D0B18(N)` at boot — the RUNTIME transition recipe (the 512-tick sine cross-fade; `--weather-target` wins). |
| `lensFlare`    | the enum-2 directional light source (`--lensflare` wins). |
| `psxWobble`    | false = the `--modern` look (no GTE snap, perspective-correct); `--ps1`/`--modern` win. |
| `dither`       | the ordered dither flag (`--dither`/`--no-dither` win). |
| `particles`    | false = `--nosnow` (snow/rain disabled; `--snow`/`--nosnow` win). |
| `engine`       | false = the `--nofog` raw-unlit look (`--fog`/`--nofog` win). |

### 3. Verification highlights (see the worklog for the full battery)

- **Parser unit test** (`tools_test_camdat_env.c`, includes the real
  `fog_poc.c`): 45/45 — full/partial/absent fields, all clamps,
  strict-boolean rejections, truncation, both shipped files.
- **Zero regressions**: v13 + legacy camdat render == v12 render
  (byte-identical, md5 `c5147d54…`); the full 21-mode sweep
  (`--envpair k,k`, k=0..20) == v12 mode-for-mode (21/21 byte-identical).
- **Env == CLI equivalence**: v13 + the v2 camdat renders byte-identically
  to v13 + legacy camdat with the equivalent CLI flags
  (`--envpair 7,4 --flashlight --weather-target 6 --weather 5 --lensflare 2
  --modern --dither --nosnow`).
- **CLI priority**: `--envpair 2,2` beats the env pair while the env's other
  fields still apply (byte-identical to the full-CLI run).
- **`engine:false` == `--nofog`**, **`psxWobble:false` == `--modern`**
  (byte-identical pairs).
- **Boot recipe parity**: env `bootWeather` 1 / 2 / 5 produce three distinct
  deterministic renders (snow / snow+wind / rain) — recipe 2 is honored from
  camdat even though the v8 CLI skips it.
- **JS-preview cross-verification** (env mode 0 — the editor's Effects-Off
  state): the camtrack_v2 TRACK CAM readback vs the C++
  `--envpair 0,0 --weather 0` golden at t=10.5 — per-pixel median |diff|
  3.00, 60.4% within ±4 (in family with the v1-verified day match), VLM:
  same scene/camera/tone, no fog, no particles, no structural differences.

### 4. The camtrack_v2 editor's temporary "Effects Off" toggle (context)

The v2 editor adds a **session-only** preview override ("Effects Off (env
0)", key `0`) that switches the preview viewport to **env mode 0** — the
decomp's `MAP_EFFECTS_INFOS[0]` (map_info.c:5): the fog-off ambient room
(`field_E=0` → fog OFF, flags None → no flashlight / no brightness overlay /
no lens flare, `SHENUM_0` flat ambient with `tintEff` = DPCS(128, -614) =
147, fogColor {60,60,68}) — plus instant weather none
(`Particle_EnvironmentSet(0,1)`). The toggle is **never serialized** to
camdat.json (isolation proven at the `m.env`, `docToJSON` and localStorage
autosave layers), and the session's World & Weather selection is shadowed
and fully restored on toggle-off.

## Files

- `src/fog_poc.c` — the v13 parser + boot integration (all changes gated on
  `cd.hasEnv`; header comment documents the format and priority).
- `tools_test_camdat_env.c` — the parser unit test harness.
- `input/camdat_v2_test.json` — an authentic v2-format camdat exported by
  the camtrack_v2 editor (pair {7,4}, weatherTarget 6, bootWeather 5,
  lensFlare 2, flashlight on, modern, dither, no particles) with the shipped
  line track — the v13 acceptance test file.
- `input/camdat.json`, `input/camdat_eye.json`, `input/THRF9FD.glb` —
  unchanged (GLB strictly read-only, md5 `c7183184d20a2508ce41af2702629a33`).

## Build

Unchanged from v12: `make` (Linux), `make -f Makefile.mingw` (Windows
cross-compile, MinGW-w64). No new dependencies.
