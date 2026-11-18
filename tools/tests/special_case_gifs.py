#!/usr/bin/env python3
"""v32 (S18): the special-case GIF driver — deterministic shot replay ->
PNG frames -> ffmpeg palette GIF + pixel-diff motion evidence (NO VLM).

Per case: render N ticks (t=k/30) with a FIXED camera, sample every 3rd
frame (10 fps GIF), encode with palettegen/paletteuse, then numpy-diff
consecutive sampled frames + first/last as the MOTION PROOF for manual
analysis. Cameras from the GLB anim positions (engine -> glTF: x,-y,-z).
Note: --shot file=F.png writes under <cwd>/shots/F.png (the engine's
prefix rule) — frames are moved into the case dir after each render."""
import json, os, subprocess, sys, shutil

POC = '/home/z/my-project/repos/PoC'
GLB = POC + '/glbs_out/v32'
OUT = '/home/z/my-project/download/session18_evidence/special_cases'
WORK = POC + '/shots/special_cases'

# key: (glb, envpair, demo, cam "x y z tx ty tz fov", ticks)
CASES = {
    # ---- engine-fresh LIVE (engine-true, no demo) ----
    'fan_school':        ('SU0203.glb',   '7,4', 0, '99.5 -0.9 -141.5 100 1.4 -144.5 55', 90),
    'fan_array_hospital':('SPU0100.glb', '2,2', 0, '53.2 -2.0 34.5 53.2 2.3 30.0 55', 60),
    'wheelchair_wheels': ('THRF906.glb',  '6,3', 0, '-266.0 1.5 -243.0 -268.4 0.4 -245.7 55', 60),
    'door_rattle_reception': ('SCFE00.glb', '2,2', 0, '-58.8 0.8 -14.5 -58.8 1.3 -18.0 55', 90),
    'door_rattle_locker':('SUFE00.glb',   '2,2', 0, '-58.8 0.8 -14.5 -58.8 1.4 -18.0 55', 90),
    'boiler_spins':      ('SU00FF.glb',   '2,2', 0, '19.7 0.3 22.0 19.7 -1.58 19.1 55', 60),
    'ferris_wheel':      ('APU00FF.glb',  '1,1', 0, '8.7 6.0 6.0 8.7 9.0 28.0 60', 120),
    'balloons':          ('APUFFFE.glb',  '1,1', 0, '-8.0 4.0 64.0 -16.0 1.5 64.0 55', 90),
    'corpse_walk':       ('DRU0100.glb',  '6,3', 0, '75.0 0.8 -16.5 75.0 -0.5 -19.7 55', 90),
    # ---- demo-gated (cutscene/event-driven; --anims-demo stands in) ----
    'carousel':          ('APU0002.glb',  '1,1', 1, '30.0 2.0 -93.0 20.0 -1.0 -100.0 55', 120),
    'elevator_doors':    ('HP0100.glb',   '2,2', 1, '59.1 0.8 -13.5 59.1 0.0 -19.1 55', 120),
    'stone_levitate':    ('ERFCFC.glb',   '2,2', 1, '-136.0 2.5 136.0 -139.5 1.4 140.6 55', 150),
    'bin_spin':          ('ER03FD.glb',   '2,2', 1, '137.0 1.5 97.0 140.0 0.0 100.0 55', 60),
    'belt_scroll':       ('ER02FC.glb',   '2,2', 1, '100.0 6.0 127.0 100.0 0.0 140.0 60', 90),
    'door_swing_streets':('THRF9FD.glb',  '6,3', 1, '-263.0 1.2 99.5 -263.0 0.5 104.0 55', 120),
    'waterfall':         ('SUFFFE.glb',   '2,2', 1, '-15.5 1.8 47.0 -15.5 -0.2 51.5 55', 90),
    'fence_fall':        ('SPU03FD.glb',  '2,2', 1, '127.0 2.0 88.0 130.5 0.0 93.0 55', 90),
    # ---- water FX ----
    'water_ripples':     ('DRFD00.glb',   '2,2', 0, '-88.5 0.8 -4.5 -92.0 -0.5 -8.0 55', 90),
    # ---- TV (state machine LIVE; screen paint data-blocked, documented) ----
    'tv_room':           ('SPU0301.glb',  '2,2', 0, '19.0 1.0 -57.0 19.5 1.2 -60.0 55', 60),
}

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def render_case(key):
    glb, pair, demo, cam, ticks = CASES[key]
    d = f'{WORK}/{key}'
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    cmd = [POC + '/fog_poc', '--glb', f'{GLB}/{glb}', '--envpair', pair]
    if demo:
        cmd += ['--anims-demo']
    if key in ('corpse_walk', 'door_swing_streets'):
        cmd += ['--flashlight']
    if cam:
        cmd += ['--cam'] + cam.split()
    for k in range(1, ticks + 1):
        t = k / 30.0
        c = cmd + ['--shot', f't={t:.4f},file={key}_f{k:03d}.png']
        r = subprocess.run(c, capture_output=True, text=True, cwd=POC)
        src = f'{POC}/shots/{key}_f{k:03d}.png'
        if not os.path.exists(src):
            print(f'[{key}] RENDER FAIL t={t}: {r.stderr[-300:]}')
            return None
        os.replace(src, f'{d}/f_{k:03d}.png')
    # sample every 3rd frame at 10fps + palette GIF
    sh(f'cd {d} && rm -f g_*.png palette.png; i=0; for k in $(seq 3 3 {ticks}); do '
       f'i=$((i+1)); cp f_$(printf %03d $k).png g_$(printf %03d $i).png; done')
    gif = f'{OUT}/{key}.gif'
    r = sh(f'cd {d} && ffmpeg -y -loglevel error -framerate 10 -i g_%03d.png '
           f'-vf "palettegen=stats_mode=diff" palette.png && '
           f'ffmpeg -y -loglevel error -framerate 10 -i g_%03d.png '
           f'-i palette.png -lavfi "paletteuse=dither=bayer:bayer_scale=2" '
           f'-loop 0 {gif}')
    if r.returncode != 0 or not os.path.exists(gif):
        print(f'[{key}] GIF encode FAILED: {r.stderr[-300:]}')
        return None
    return d, gif

def pixel_evidence(key, d, ticks):
    import numpy as np
    from PIL import Image
    frames = [f'{d}/f_{k:03d}.png' for k in range(3, ticks + 1, 3)]
    arrs = [np.asarray(Image.open(f).convert('RGB'), dtype=np.int16) for f in frames]
    diffs = []
    for i in range(1, len(arrs)):
        diffs.append(int((np.abs(arrs[i] - arrs[i - 1]) > 12).sum()))
    total = int((np.abs(arrs[-1] - arrs[0]) > 12).sum())
    px = int(arrs[0].shape[0]) * int(arrs[0].shape[1])
    mean = sum(diffs) / max(1, len(diffs))
    return {'case': key, 'frames': len(frames), 'pixels': px,
            'consecutive_diffs_gt12': diffs,
            'mean_consecutive': round(mean, 1),
            'first_last_diff': total,
            'moving': mean > 50 or total > 500}

if __name__ == '__main__':
    keys = sys.argv[1:] or list(CASES)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    all_ev = []
    for key in keys:
        print(f'=== {key} ===', flush=True)
        res = render_case(key)
        if not res:
            all_ev.append({'case': key, 'error': 'render/encode failed'})
            continue
        d, gif = res
        ev = pixel_evidence(key, d, CASES[key][4])
        ev['gif'] = os.path.basename(gif)
        ev['gif_bytes'] = os.path.getsize(gif)
        all_ev.append(ev)
        print(f"  gif={ev['gif_bytes']}B frames={ev['frames']} "
              f"meanDiff={ev['mean_consecutive']}px "
              f"firstLast={ev['first_last_diff']}px moving={ev['moving']}", flush=True)
    with open(f'{OUT}/pixel_evidence.json', 'w') as f:
        json.dump(all_ev, f, indent=1)
    bad = [e for e in all_ev if e.get('error') or not e.get('moving')]
    print(f'\nDONE {len(all_ev)} cases; {len(bad)} NOT MOVING/FAILED:')
    for e in bad:
        print('  ', e['case'], e.get('error') or 'no significant pixel motion')
