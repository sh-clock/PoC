Base rip files + camera tracks. All sample assets are Konami-copyrighted,
non-commercial testing only — produce your own via TOOLS.md.

The repo tracks ONLY the base files; the GLBs are not committed. Convert
them with the current tools/ipd2gltf.py (the release zips do exactly this):

  python3 tools/ipd2gltf.py --input input --output input --rooms THRF9FD,HP0003

THRF9FD (outdoor street scene, filetable USA index 1291):
  THRF9FD.IPD     - the room (embedded PLM + collision + render data)
  THR_GLB.PLM     - the shared THR map geometry library (trees etc.)
  THR0001F.TIM    - the 4 street textures the room references
  THR0002F.TIM
  THR0003F.TIM
  THR0004F.TIM
  THR7201F.TIM    - the fence/sign textures
  THR7201H.TIM
  BG_ETC.TIM      - the engine's billboard/weather sprite sheet
  camdat.json     - CamTrack Editor camera track ("Line 1", pingPong,
                    49.88s, y=3.43 street-cam) + per-model flags
                    fogon=false, nighton=true, flashlighton=true and the
                    env object (pair [6,3], flashlight on, wobble, dither).

HP0003 (hospital interior):
  HP0003.IPD      - the room (roundtrip-proven converter output).
                    Interior scene: the engine runs no weather particles
                    indoors (load_screen.c per-map weather), and its camdat
                    sets particles:false to match.
  HP1F011.TIM     - the 3 room textures it references
  HP1F012.TIM
  HP1F01H.TIM
  hp_camdat.json  - the hospital corridor camera track ("HP corridor",
                    line, pingPong, 12s).

Both conversions reconstruct their source IPDs byte-identically
(tools/tests/sh1x_roundtrip.py) and are deterministic across runs.

Optional debug flag (no file needed): --tim-file views any TIM, e.g.
BG_ETC.TIM above.
