#!/usr/bin/env python3
"""Verify the v32 SH1X extras landed in the ripped GLBs (scene-level
propAnims — the ripper emits them on the scene root SH1X)."""
import json, struct, sys

def scene_anims(path):
    d = open(path, 'rb').read()
    clen, ctype = struct.unpack_from('<II', d, 12)
    js = json.loads(d[20:20+clen].decode('utf-8', 'replace'))
    sh = js.get('scenes', [{}])[0].get('extras', {}).get('SH1X', {})
    pa = sh.get('propAnims', [])
    return pa if isinstance(pa, list) else []

CHECKS = [
    ('APUFFFE.glb', lambda a: a.get('object') == 'WHEEL_BA' and
        a.get('eventGatePolarity') == 'clear', 'WHEEL_BA polarity=clear'),
    ('HP0100.glb', lambda a: a.get('driver') == 'slideDoor' and
        isinstance(a.get('slideIdx'), int), 'slideDoor+slideIdx'),
    ('HP0100.glb', lambda a: a.get('driver') == 'slideDoor' and
        a.get('slideIdx') == 0, 'slideIdx 0 = DR1L'),
    ('HP0100.glb', lambda a: a.get('driver') == 'slideDoor' and
        a.get('slideIdx') == 5, 'slideIdx 5 = DR2R'),
    ('ERFCFC.glb', lambda a: a.get('driver') == 'stoneChoreo', 'stoneChoreo'),
    ('ERFCFC.glb', lambda a: a.get('driver') == 'binSpin', 'binSpin'),
    ('ER02FC.glb', lambda a: a.get('driver') == 'scrollBelt' and
        a.get('count') == 3, 'scrollBelt count3'),
    ('DRFD00.glb', lambda a: a.get('driver') == 'waterRipple', 'waterRipple'),
    ('SUFFFE.glb', lambda a: a.get('driver') == 'particles', 'waterfall'),
    ('SU0203.glb', lambda a: a.get('object') == 'BOX_HIDE', 'BOX_HIDE'),
    ('SU0203.glb', lambda a: a.get('driver') == 'particles', 'waterfall in school'),
    ('THRF9FD.glb', lambda a: a.get('object', '').startswith('CHAIN1'), 'CHAIN1 set'),
    ('ER01FC.glb', lambda a: a.get('object') in
        ('DR1R_HID', 'DR1L_HID', 'DR2R_HID', 'DR2L_HID'), 'map7_s00 4 doors'),
    ('APU0002.glb', lambda a: a.get('object') == 'CHAIR_HI', 'CHAIR_HI'),
    ('THRF905.glb', lambda a: a.get('object') == 'WHEEL1_H', 'wheelchair'),
    ('SPU0100.glb', lambda a: a.get('driver') == 'fanArray', 'fanArray'),
    ('DRU0100.glb', lambda a: a.get('driver') == 'rngWalk', 'corpse'),
    ('SU00FF.glb', lambda a: a.get('object') == 'SPHERE_H', 'boiler sphere'),
    ('SCFE00.glb', lambda a: a.get('object') == 'TOBIRA00', 'rattle door'),
    ('SPU0301.glb', lambda a: a.get('driver') == 'tvNoise', 'TV state machine'),
]

base = '/home/z/my-project/repos/PoC/glbs_out/v32/'
fails = []
cache = {}
for fn, pred, desc in CHECKS:
    if fn not in cache:
        cache[fn] = scene_anims(base + fn)
    found = any(pred(a) for a in cache[fn])
    print(('PASS' if found else 'FAIL') + f' {fn:14s} {desc}')
    if not found:
        fails.append((fn, desc))

print()
for fn in sorted(cache):
    print(f'  {fn:14s} {len(cache[fn]):2d} scene propAnims')
sys.exit(1 if fails else 0)
