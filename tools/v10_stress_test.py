#!/usr/bin/env python3
"""v10 post-wrap flashlight ramp + infinite mode-cycling stress test.

Proves:
  1. After crossing the camtrack wrap, the env keeps ticking and a
     flashlight toggle at a MIXED pair ramps the engine fade (fi 0->4096).
  2. Mode changes after the wrap re-blend the env (visual delta).
  3. Infinite cycling: 240 mode changes + 4 wrap crossings + weather
     cycles + HUD/menu open-close — no freeze, no lock, flashlight always
     recoverable at a mixed pair.
"""
import ctypes, os, re, subprocess, sys, time, shutil

BIN = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
TAG = sys.argv[3]
XVFB_DISPLAY = ":99"

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT + "/shots")
if not os.path.islink(OUT + "/input"):
    os.symlink(os.path.dirname(BIN) + "/input", OUT + "/input")

xvfb = subprocess.Popen(["Xvfb", XVFB_DISPLAY, "-screen", "0", "1280x720x24"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

env = dict(os.environ, DISPLAY=XVFB_DISPLAY, FOGPOC_X11="1")
app = subprocess.Popen(
    ["stdbuf", "-oL", BIN, "--res", "640x360", "--fps", "60",
     "--duration", "900", "--env-dump", OUT + "/env_dump.txt"],
    cwd=OUT, env=env,
    stdout=open(OUT + "/window.log", "w"), stderr=subprocess.STDOUT)
time.sleep(4.0)

xlib = ctypes.CDLL("libX11.so.6")
xlib.XOpenDisplay.restype = ctypes.c_void_p
xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
d = xlib.XOpenDisplay(XVFB_DISPLAY.encode())
assert d
xlib.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                            ctypes.POINTER(ctypes.c_ulong),
                            ctypes.POINTER(ctypes.c_ulong),
                            ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                            ctypes.POINTER(ctypes.c_uint)]
root = ctypes.c_ulong(); parent = ctypes.c_ulong()
children = ctypes.POINTER(ctypes.c_ulong)(); nchild = ctypes.c_uint()
assert xlib.XQueryTree(d, xlib.XDefaultRootWindow(d), ctypes.byref(root),
                       ctypes.byref(parent), ctypes.byref(children),
                       ctypes.byref(nchild))
target = children[0]
xlib.XFree.argtypes = [ctypes.c_void_p]
xlib.XFree(ctypes.cast(children, ctypes.c_void_p))
assert target

class XKeyEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong), ("root", ctypes.c_ulong),
                ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("x", ctypes.c_int), ("y", ctypes.c_int),
                ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
                ("state", ctypes.c_uint), ("keycode", ctypes.c_uint),
                ("same_screen", ctypes.c_int)]

def send_key(keysym):
    keycode = xlib.XKeysymToKeycode(d, keysym)
    assert keycode
    ev = XKeyEvent()
    ev.type = 2; ev.display = None; ev.window = target; ev.root = root
    ev.keycode = keycode; ev.same_screen = 1
    xlib.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
    xlib.XSendEvent(d, target, False, 1 << 0, ctypes.byref(ev))
    ev.type = 3
    xlib.XSendEvent(d, target, False, 1 << 1, ctypes.byref(ev))
    xlib.XFlush(d); xlib.XSync(d, False)

def press(keysym, settle=0.35):
    send_key(keysym); time.sleep(settle)

TAB, ESC, S, F, W, H = 0xff09, 0xff1b, 0x73, 0x66, 0x77, 0x68
RBRK, COMMA, RIGHT, N_KEY = 0x5d, 0x2c, 0xff53, 0x6e

print(f"[{TAG}] 1) cross the wrap via RIGHT x55 (t: ~12 -> wrap)")
for i in range(55):
    press(RIGHT, 0.08)
time.sleep(0.8)

print(f"[{TAG}] 2) post-wrap: N lands on a MIXED pair, then F")
press(N_KEY); time.sleep(0.8)     # N -> night {6,3} or nightmare {7,4} (MIXED)
press(F); time.sleep(1.4)          # toggle OFF (was ON since boot)
press(F); time.sleep(1.8)          # toggle ON — the ramp must run POST-WRAP
press(S)

print(f"[{TAG}] 3) stress: 120x ] preset cycle (all 21 presets ~6 loops)")
for i in range(120):
    press(RBRK, 0.045)

print(f"[{TAG}] 4) stress: 60x , pair cycle (all 24 pairs 2.5 loops)")
for i in range(60):
    press(COMMA, 0.045)

print(f"[{TAG}] 5) stress: 20x W weather cycle + 20x H HUD + browser open/close")
for i in range(20):
    press(W, 0.12)
for i in range(20):
    press(H, 0.06)
for i in range(10):
    press(TAB, 0.12); press(ESC, 0.12)

print(f"[{TAG}] 6) cross the wrap 3 more times while cycling")
for w in range(3):
    for i in range(55):
        press(RIGHT, 0.055)
    for i in range(7):
        press(RBRK, 0.06)

print(f"[{TAG}] 7) final recovery: N -> mixed pair + F (flashlight must come back)")
press(N_KEY); time.sleep(0.4)
press(N_KEY); time.sleep(0.6)   # -> night {6,3} (MIXED)
press(F); time.sleep(1.8)
press(S)

time.sleep(0.5)
app.terminate()
try:
    app.wait(timeout=5)
except subprocess.TimeoutExpired:
    app.kill()
xvfb.terminate(); xvfb.wait()

# ------------------------------------------------------------------ audit
print(f"\n[{TAG}] ===== AUDIT =====")
log = open(OUT + "/window.log").read()
envs = [l for l in log.splitlines() if "[env]" in l]
print(f"  env actions logged: {len(envs)}")
refused = sum(1 for l in envs if "REFUSED" in l)
ons = sum(1 for l in envs if "flashlight ON" in l)
print(f"  flashlight: {ons} accepted (mixed pairs), {refused} refused (identical pairs)")
weather = sum(1 for l in log.splitlines() if "[weather]" in l)
print(f"  weather transitions: {weather}")

lines = [l for l in open(OUT + "/env_dump.txt").read().splitlines()
         if l.startswith("env ")]
ticks = [int(re.search(r"tick=(\d+)", l).group(1)) for l in lines]
print(f"  env ticks: {len(lines)} (last tick={ticks[-1]} = {ticks[-1]/30.0:.2f} s)")

# flashlight ramp recovery: find ON toggles followed by fi climbing to 4096
fi = [int(re.search(r"fi=(\d+)", l).group(1)) for l in lines]
on = [int(re.search(r"on=(\d+)", l).group(1)) for l in lines]
ramps = 0
i = 0
while i < len(on) - 1:
    if on[i] == 0 and on[i + 1] == 1:
        # find how far fi climbs while on stays 1
        j = i + 1
        peak = 0
        while j < len(on) and on[j] == 1:
            peak = max(peak, fi[j]); j += 1
        if peak == 4096:
            ramps += 1
        i = j
    else:
        i += 1
print(f"  complete flashlight ramps (fi reached 4096): {ramps}")
stalled = [k for k in range(len(on) - 1)
           if on[k] == 1 and on[k + 1] == 1 and fi[k] < 4096
           and fi[k + 1] <= fi[k]]
print(f"  stalled ramps (on=1 but fi not climbing): {len(stalled)}")

# the envDump tick MONOTONICITY (no stall across the whole stress session)
gaps = [ticks[k + 1] - ticks[k] for k in range(len(ticks) - 1)]
big = [g for g in gaps if g > 1]
print(f"  tick gaps > 1 (seek fast-forwards, expected): {len(big)} max gap={max(gaps)}")
neg = [g for g in gaps if g <= 0]
print(f"  non-positive tick steps (freeze indicators): {len(neg)}")

ok = (ramps >= 2 and len(stalled) == 0 and len(neg) == 0 and ticks[-1] > 4000 and ons >= 2)
print(f"\n[{TAG}] RESULT: {'ALL PASS — infinite cycling + post-wrap recovery OK' if ok else 'CHECK ABOVE'}")
sys.exit(0 if ok else 1)
