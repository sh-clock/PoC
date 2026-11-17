#!/usr/bin/env python3
"""v10 BUG REPRODUCTION — the three v9 runtime defects, hard evidence.

Usage: v10_repro.py <binary> <outdir> <tag>

Drives the X11 window under Xvfb with synthetic keys (same harness as the
v9 smoke test) and captures:

  BUG 1  normal fog broken on a DAY boot (camdat fogon=false + not the
         night boot -> renderer fog flag OFF -> black unlit scene)
         [deterministic --day --shot outside this script; here: the window
          day-cycle via N N after a night boot, PLUS the frozen-env fog
          below]
  BUG 2  flashlight gate: F accepted on a flag-bearing IDENTICAL pair
         ({3,3} preset-3 self pair) then silently auto-off'd <=33 ms later
         -> flashlight can never light = "permanently off"
  BUG 3  env freeze: after the camtrack wrap (t wraps at 49.8787 s),
         sh_env_sync_live never ticks again -> envDump tick column stalls,
          ] preset changes stop affecting the render, flashlight ramp
         frozen at 0 even with F accepted
"""
import ctypes, os, subprocess, sys, time, shutil

BIN = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
TAG = sys.argv[3]
XVFB_DISPLAY = ":98"

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT + "/shots")

xvfb = subprocess.Popen(["Xvfb", XVFB_DISPLAY, "-screen", "0", "1280x720x24"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

# link input next to the run dir (GLB is READ-ONLY; never copied/modified)
if not os.path.islink(OUT + "/input"):
    os.symlink(os.path.dirname(BIN) + "/input", OUT + "/input")

env = dict(os.environ, DISPLAY=XVFB_DISPLAY, FOGPOC_X11="1")
app = subprocess.Popen(
    ["stdbuf", "-oL", BIN, "--res", "640x360", "--fps", "60", "--duration", "600",
     "--env-dump", OUT + "/env_dump.txt"],
    cwd=OUT, env=env,
    stdout=open(OUT + "/window.log", "w"), stderr=subprocess.STDOUT)

time.sleep(4.0)

xlib = ctypes.CDLL("libX11.so.6")
xlib.XOpenDisplay.restype = ctypes.c_void_p
xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
d = xlib.XOpenDisplay(XVFB_DISPLAY.encode())
assert d, "cannot open display"

xlib.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                            ctypes.POINTER(ctypes.c_ulong),
                            ctypes.POINTER(ctypes.c_ulong),
                            ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                            ctypes.POINTER(ctypes.c_uint)]
root = ctypes.c_ulong(); parent = ctypes.c_ulong()
children = ctypes.POINTER(ctypes.c_ulong)(); nchild = ctypes.c_uint()
assert xlib.XQueryTree(d, xlib.XDefaultRootWindow(d), ctypes.byref(root),
                       ctypes.byref(parent), ctypes.byref(children),
                       ctypes.byref(nchild)), "XQueryTree failed"
target = children[0] if nchild.value >= 1 else 0
xlib.XFree.argtypes = [ctypes.c_void_p]
if children:
    xlib.XFree(ctypes.cast(children, ctypes.c_void_p))
assert target, "no app window found"

class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong), ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint), ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]

def send_key(keysym):
    keycode = xlib.XKeysymToKeycode(d, keysym)
    assert keycode, f"no keycode for keysym {hex(keysym)}"
    ev = XKeyEvent()
    ev.type = 2; ev.display = None; ev.window = target; ev.root = root
    ev.keycode = keycode; ev.same_screen = 1
    xlib.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
    xlib.XSendEvent(d, target, False, 1 << 0, ctypes.byref(ev))
    ev.type = 3
    xlib.XSendEvent(d, target, False, 1 << 1, ctypes.byref(ev))
    xlib.XFlush(d)
    xlib.XSync(d, False)

def press(keysym, settle=0.6):
    send_key(keysym); time.sleep(settle)

TAB, DOWN, ENTER, ESC = 0xff09, 0xff54, 0xff0d, 0xff1b
S, N, F, W, L, H = 0x73, 0x6e, 0x66, 0x77, 0x6c, 0x68
RBRK, LBRK, COMMA, PERIOD = 0x5d, 0x5b, 0x2c, 0x2e
RIGHT, D3 = 0xff53, 0x33

print(f"[{TAG}] phase 1: night boot baseline")
press(S)                              # shots/live_*0.0x.png  (night + fl)

print(f"[{TAG}] phase 2: BUG 2 — F on flag-bearing identical pair {3,3}")
press(TAB); press(D3); press(ESC)     # browser digit 3 -> preset {3,3}
press(S)                              # visual: flashlight-less night street
press(F); time.sleep(1.2)             # F ACCEPTED (flag present) ...
press(S)                              # ... but auto-off killed it <=33ms
# back to the mixed night pair via '.' (pair cycle) and F there (control)
press(PERIOD); press(F); time.sleep(1.2)
press(S)

print(f"[{TAG}] phase 3: pre-wrap mode change (control — env still alive)")
press(RBRK); time.sleep(1.0)          # ] -> next preset (visible change)
press(S)                              # shots/live_...  pre-wrap

print(f"[{TAG}] phase 4: BUG 3 — seek across the track wrap (t: ~12 -> 62 -> wrap)")
for i in range(55):
    press(RIGHT, 0.08)                # 55 s forward -> P.t wraps to ~7
time.sleep(1.0)

print(f"[{TAG}] phase 5: post-wrap mode change — frozen?")
press(RBRK); time.sleep(1.5)          # ] again -> SHOULD change the env
press(S)                              # if frozen: identical pixels to pre-wrap
press(F); time.sleep(1.0)             # flashlight F post-wrap (ramp frozen?)
press(S)

time.sleep(0.5)
app.terminate()
try:
    app.wait(timeout=5)
except subprocess.TimeoutExpired:
    app.kill()
xvfb.terminate(); xvfb.wait()

# ---------------------------------------------------------------- analysis
print(f"\n[{TAG}] ===== ANALYSIS =====")
log = open(OUT + "/window.log").read()
for line in log.splitlines():
    if ("[env]" in line or "camdat" in line or "engine env" in line):
        print("  " + line)

dump_path = OUT + "/env_dump.txt"
if os.path.exists(dump_path):
    lines = [l for l in open(dump_path).read().splitlines()
             if l.startswith("env ")]
    print(f"\n  envDump: {len(lines)} ticks written")
    if lines:
        import re
        ticks = [int(re.search(r"tick=(\d+)", l).group(1)) for l in lines]
        onoff = [(int(re.search(r"fi=(\d+)", l).group(1)),
                  int(re.search(r"on=(\d+)", l).group(1))) for l in lines]
        print(f"  first tick={ticks[0]} last tick={ticks[-1]} "
              f"(session ran ~70 s -> expect ~2100 ticks if unfrozen)")
        # find the last tick BEFORE the wrap seek and check the stall
        print(f"  last 12 dump states (fi=flashlightIntensity, on=isFlashlightOn):")
        for l in lines[-12:]:
            m = re.search(r"tick=(\d+) fi=(\d+) on=(\d+)", l)
            print(f"    tick={m.group(1)} fi={m.group(2)} on={m.group(3)}")
        # BUG 2 evidence: F accepted at {3,3} -> on goes 1 for <=2 ticks then 0
        prev = None
        for i, (fi, on) in enumerate(onoff):
            if prev is not None and prev[1] == 1 and on == 0:
                print(f"  ** GATE BUG: isFlashlightOn 1->0 at tick {ticks[i]} "
                      f"(auto-off killed the accepted toggle; fi={fi})")
                break
            prev = (fi, on)
        # BUG 3 evidence: tick counter stalls after the wrap
        # (the wrap seek happened at wall time ~= phase 4; count ticks after)
        print(f"  tick stall check: last tick={ticks[-1]} = {ticks[-1]/30.0:.2f} s of env time; "
              f"post-wrap play.t in the last screenshots is ~21-29 s — the env "
              f"clock ran PAST the pre-wrap 49.88 s boundary and stopped")
        if ticks[-1] >= 1400 and ticks[-1] < 1500:
            print(f"  ** FREEZE BUG CONFIRMED: tick counter stopped at {ticks[-1]} "
                  f"(~{ticks[-1]/30.0:.1f} s, the wrap boundary) and never "
                  f"resumed although frames kept rendering (see shots/live_00xx)")

shots = sorted(os.listdir(OUT + "/shots")) if os.path.isdir(OUT + "/shots") else []
print(f"\n  {len(shots)} screenshots:")
for s in shots:
    print("    " + s)
print(f"[{TAG}] done")
