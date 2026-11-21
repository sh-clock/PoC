@echo off
REM SH1 animation testbed — one launcher per driver family.
cd /d "%~dp0"

echo == fanArray — the nightmare-school ceiling fan (SU0203) ==
fog_poc.exe --glb glbs_anim\SU0203.glb --cam 100.000 2.802 -139.420 100.000 1.602 -142.920 %*

echo == fanArray — the SPU fan array (SPU0100) ==
fog_poc.exe --glb glbs_anim\SPU0100.glb --cam 53.666 3.575 -29.030 53.211 2.375 -32.500 %*

echo == ferrisWheel — the amusement-park ferris (APU00FF) ==
fog_poc.exe --glb glbs_anim\APU00FF.glb --cam 7.861 11.172 28.287 8.700 9.972 39.255 %*

echo == lissajousOrbit — the 12-seat spinning carnival ride (APUFFFE) ==
fog_poc.exe --glb glbs_anim\APUFFFE.glb --cam -18.663 3.470 57.101 -15.971 2.270 59.338 %*

echo == carouselSpin — the carousel (APU0002) ==
fog_poc.exe --glb glbs_anim\APU0002.glb --cam 20.000 0.200 -96.500 20.000 -1.000 -100.000 %*

echo == tvNoise — the town-center TV wall (the static paints) (SPU0401) ==
fog_poc.exe --glb glbs_anim\SPU0401.glb --cam 164.800 3.073 -55.038 163.498 1.873 -51.789 %*

echo == spinRng — the rng spin (the distant windmill wheels) (THRF906) ==
fog_poc.exe --glb glbs_anim\THRF906.glb --cam -265.361 1.641 -247.587 -268.320 0.441 -245.719 %*

echo == dampedSwing — the drawbridge door (THRF9FD) ==
fog_poc.exe --glb glbs_anim\THRF9FD.glb --cam -260.252 1.200 101.832 -263.000 -0.000 104.000 %*

echo == doorRattle — the rattling reception doors (SCFE00) ==
fog_poc.exe --glb glbs_anim\SCFE00.glb --cam -55.39859339961122 2.50078125 -17.248012148602033 -58.8125 1.30078125 -18.01953125 %*

echo == kickSwing — the kicked door (SUFE00) ==
fog_poc.exe --glb glbs_anim\SUFE00.glb --cam -57.735 2.251 -19.708 -61.000 1.051 -20.969 %*

echo == slideDoor — the hospital elevators (ERFDFE) ==
fog_poc.exe --glb glbs_anim\ERFDFE.glb --cam -104.361 1.200 61.437 -100.902 -0.000 60.902 %*

echo == slideDoor — HP0100 (HP0100) ==
fog_poc.exe --glb glbs_anim\HP0100.glb --cam 55.639 1.200 -18.563 59.098 -0.000 -19.098 %*

echo == scrollBelt — the conveyor belt (ER02FC) ==
fog_poc.exe --glb glbs_anim\ER02FC.glb --cam 101.490 -0.001 139.998 104.990 0.000 140.000 %*

echo == stoneChoreo — the floating stones (ERFCFC) ==
fog_poc.exe --glb glbs_anim\ERFCFC.glb --cam -142.150 -0.724 137.051 -142.150 -1.924 140.551 %*

echo == binSpin — the spinning bin (ER03FD) ==
fog_poc.exe --glb glbs_anim\ER03FD.glb --cam 138.889 1.200 96.681 140.000 -0.000 100.000 %*

echo == gravityScatter — the falling beans (ER01FE) ==
fog_poc.exe --glb glbs_anim\ER01FE.glb --cam 65.031 2.602 58.815 62.297 1.402 61.000 %*

echo == fallOnce — the falling fence (SPU03FD) ==
fog_poc.exe --glb glbs_anim\SPU03FD.glb --cam 129.781 1.200 96.425 130.500 -0.000 93.000 %*

echo == translate — the moving shelf (ER0201) ==
fog_poc.exe --glb glbs_anim\ER0201.glb --cam 100.859 1.372 -61.047 104.219 0.172 -60.066 %*

echo == rngWalk — the wandering corpse (DRU0100) ==
fog_poc.exe --glb glbs_anim\DRU0100.glb --cam 71.501 0.700 -19.769 75.000 -0.500 -19.699 %*

echo == waterRipple — the sewer ripple sprites (DR0000) ==
fog_poc.exe --glb glbs_anim\DR0000.glb --cam 18.192 1.200 -0.188 -20.000 0.000 40.000 %*

echo == lightFlicker — the flickering light (SU00FF) ==
fog_poc.exe --glb glbs_anim\SU00FF.glb --cam 19.699 -0.378 15.602 19.699 -1.578 19.102 %*

echo == spinConst — the constant spin (SU00FF) ==
fog_poc.exe --glb glbs_anim\SU00FF.glb --cam 19.699 -0.378 15.602 19.699 -1.578 19.102 %*

echo == particles — the school waterfall (SUFFFE) ==
fog_poc.exe --glb glbs_anim\SUFFFE.glb --cam -13.5 -0.5 51.2 -16.0 -0.1 51.2  %*

echo == cutscene — the gated poses (demo gates open) (ER00FE) ==
fog_poc.exe --glb glbs_anim\ER00FE.glb --cam 18.603 2.001 62.402 21.148 0.801 60.000 %*

echo == waterFloor — the live DR_WAVE water floor (DR01FE) ==
fog_poc.exe --glb glbs_anim\DR01FE.glb --cam 52.000 3.454 48.500 52.000 2.254 52.000 %*

