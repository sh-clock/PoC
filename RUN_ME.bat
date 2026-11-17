@echo off
rem Silent Hill PoC v12 - standalone Windows runner
rem (the exe needs input\ next to it: THRF9FD.glb + camdat.json - included)
if not exist fog_poc.exe echo fog_poc.exe missing! & pause & exit /b
fog_poc.exe --res 640x360
rem Try the modes (v12: ALL NINE weather states + the transition lock live;
rem all 21 env modes cycle infinitely without freezing):
rem   fog_poc.exe --day                     (DAY street fog 13.5m, the v3-verified look)
rem   fog_poc.exe --night --flashlight      (NIGHT street + flashlight)
rem   fog_poc.exe --weather-target 6        (the game's own snow->rain event)
rem   fog_poc.exe --weather-target 3        (SNOW + live wind machinery)
rem   fog_poc.exe --listmodes               (the full mode inventory)
rem Keys: N night cycle  F flashlight  W weather 0..8  L lightning
rem       Tab browser  [ ] presets  , . pairs  P PSX wobble  H hud
pause
