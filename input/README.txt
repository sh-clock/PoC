Drop the app inputs here:

  THRF9FD.glb    - ipd2gltf rip of the original BG/THRF9FD.IPD room
                   (filetable USA index 1291). The app loads this GLB
                   DIRECTLY - no extraction step, no external assets.
  camdat.json    - CamTrack Editor 1.0.0 camera track ("Line 1",
                   pingPong, 49.88s, y=3.43 street-cam) + per-model flags:
                   fogon=false, nighton=true, flashlighton=true.
  camdat_eye.json - v6 DEMO: the SAME track at eye height (y=1.75, i.e.
                   +1.60m over the 0.148m walkway datum). The engine's
                   flashlight (func_80057658, ~1/d^2 value falloff, anchor
                   ~1.2-1.5m above the street on Harry's torso bone) puts
                   its visible road pool at 4-6m from an eye-height anchor:
                   run  ./fog_poc --camdat input/camdat_eye.json --night --flashlight
                   to see the classic SH1 pool (VLM 9/10). At the 3.43m
                   street-cam height the same authentic math places the
                   beam core ~12m out (value ~13/255 -> black) and only
                   fence/wall bases glow (+74..+107 measured) - engine-
                   exact behavior for a high camera. See README.md v6 section + CHANGES_v7.md (v7: the realtime window now ticks Gfx_EffectsUpdate every frame, so the flashlight beam is live in the interactive window at ANY camera height).

The executable looks for these in ./input/ or next to itself.
Optional (debug only, NOT required by the app):
  BG_ETC.TIM / FLAME.TIM / WATER.TIM - viewable with --tim-file.
  updated_test_camdat.json - the UPDATED v2 camdat from the CDN (Sept 20):
                   model THRF9FD.glb with env { pair [6,3] (night street ->
                   flashlight), weatherTarget 4, flashlightOn, psxWobble,
                   dither, particles, engine } + the line track
                   "Line 1" pingPong (-256.347,1.1169,110.9005) ->
                   (-256.1334,1.5052,85.7087), speedMS 1.7012, lookMode
                   path, fov 60. The v14 showcase for the FENCE/BUSH
                   layering fix:
                   ./fog_poc --camdat input/updated_test_camdat.json
