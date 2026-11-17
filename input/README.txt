Sample inputs the renderer loads (the executable looks for these in
./input/ or next to itself). All sample assets are Konami-copyrighted,
non-commercial testing only — produce your own via TOOLS.md.

  THRF9FD.glb     - ipd2gltf rip of the original BG/THRF9FD.IPD room
                    (Cafe 5->2 alley street, filetable USA index 1291).
                    Loaded directly - no extraction step, no external
                    assets; textures are embedded in the GLB.
  THRF9FD.IPD     - the source room (for tools/tests/sh1x_roundtrip.py
                    byte-identity verification of the GLB above).
  camdat.json     - CamTrack Editor camera track ("Line 1", pingPong,
                    49.88s, y=3.43 street-cam) + per-model flags
                    fogon=false, nighton=true, flashlighton=true and the
                    env object (pair [6,3], flashlight on, wobble, dither).
  camdat_eye.json - DEMO: the SAME track at eye height (y=1.75, +1.60m
                    over the 0.148m walkway datum). The engine flashlight
                    (func_80057658, ~1/d^2 falloff) puts its visible road
                    pool at 4-6m from an eye-height anchor:
                    ./fog_poc --camdat input/camdat_eye.json --night --flashlight
  HP0003.glb      - hospital interior room (ipd2gltf, byte-roundtrip-proven
                    against HP0003.IPD). Interior scene: the engine runs no
                    weather particles indoors (load_screen.c per-map
                    weather), and its camdat sets particles:false to match.
  HP0003.IPD      - the source room (roundtrip verification).
  hp_camdat.json  - the hospital corridor camera track ("HP corridor",
                    line, pingPong, 12s).

Optional (debug only, NOT required by the app):
  BG_ETC.TIM / FLAME.TIM / WATER.TIM - viewable with --tim-file.
  camdat_v2_test.json - an authentic CamTrack Editor v2 export (env object
                    showcase).
  updated_test_camdat.json - the v2 camdat from the CDN (Sept 20): the
                    "Line 1" track with the v14 fence/bush layering fix
                    showcase:
                    ./fog_poc --camdat input/updated_test_camdat.json
