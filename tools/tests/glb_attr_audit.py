#!/usr/bin/env python3
"""GLB attribute audit for the flashlight-illumination diagnosis."""
import json, struct, sys, collections

path = sys.argv[1] if len(sys.argv) > 1 else "../../input/THRF9FD.glb"
data = open(path, "rb").read()
magic, ver, total = struct.unpack("<III", data[:12])
assert magic == 0x46546C67, "not a GLB"
jlen, jtype = struct.unpack("<II", data[12:20])
j = json.loads(data[20:20 + jlen].decode("utf-8"))

bin_len, bin_type = struct.unpack("<II", data[20 + jlen:28 + jlen])
assert bin_type == 0x004E4942, "BIN chunk magic mismatch"
bin_data = data[28 + jlen:28 + jlen + bin_len]

accs = j["accessors"]
views = j["bufferViews"]

def acc_off(aidx):
    a = accs[aidx]
    v = views[a["bufferView"]]
    return a, v.get("byteOffset", 0) + a.get("byteOffset", 0)

attr_counter = collections.Counter()
mat_alpha = collections.Counter()
prim_details = []

print("GLB: %d bytes, %d meshes, %d accessors, %d materials, %d images" % (
    len(data), len(j.get("meshes", [])), len(accs),
    len(j.get("materials", [])), len(j.get("images", []))))

for mi, m in enumerate(j.get("meshes", [])):
    for pi, p in enumerate(m["primitives"]):
        attrs = p.get("attributes", {})
        for k in attrs:
            attr_counter[k] += 1
        mat = j["materials"][p["material"]] if "material" in p else None
        amode = (mat or {}).get("alphaMode", "OPAQUE(default)")
        mat_alpha[amode] += 1
        ninfo, nsample = None, None
        if "NORMAL" in attrs:
            a, off = acc_off(attrs["NORMAL"])
            ct = a.get("componentType")
            ninfo = "ct=%d norm=%s cnt=%d" % (ct, a.get("normalized", False), a["count"])
            if ct == 5122:  # SHORT
                vals = struct.unpack_from("<" + "hhh" * 3, bin_data, off)
                tri = [tuple(vals[i * 3:i * 3 + 3]) for i in range(3)]
                mags = [int(round((x * x + y * y + z * z) ** 0.5)) for x, y, z in tri]
                nsample = "%s %s" % (tri, ["len=%d" % mm for mm in mags])
            elif ct == 5126:  # FLOAT
                vals = struct.unpack_from("<fff fff fff", bin_data, off)
                tri = [tuple(round(vals[i * 3 + c], 4) for c in range(3)) for i in range(3)]
                mags = [round(sum(c * c for c in t) ** 0.5, 4) for t in tri]
                nsample = "%s %s" % (tri, ["len=%.4f" % mm for mm in mags])
        vc = accs[attrs["POSITION"]]["count"] if "POSITION" in attrs else 0
        prim_details.append((mi, pi, amode, vc, ninfo, nsample))

print("\n=== attribute usage across primitives ===")
for k, c in attr_counter.most_common():
    print("  %-12s : %d primitives" % (k, c))
print("\n=== alpha modes ===")
for k, c in mat_alpha.most_common():
    print("  %-24s: %d" % (k, c))
print("\n=== first 30 primitives: (mesh/prim, alphaMode, verts, normalInfo, normalSample) ===")
for d in prim_details[:30]:
    print("  m%d/%d %-18s v=%-4d %s %s" % d)
if len(prim_details) > 30:
    print("  ... %d more" % (len(prim_details) - 30))

pa = accs[j["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
print("\nPOSITION accessor[0]: componentType=%d (5126=float,5122=short) count=%d min=%s max=%s" % (
    pa.get("componentType"), pa["count"], pa.get("min"), pa.get("max")))

n_with = sum(1 for d in prim_details if d[4])
print("\n>>> PRIMITIVES WITH NORMAL ATTRIBUTE: %d / %d" % (n_with, len(prim_details)))
c_with = sum(1 for d in prim_details if any(a.startswith("COLOR") for a in [d[4]]))
print(">>> (color check via attrs counter above)")

print("\n=== nodes with transforms ===")
for i, n in enumerate(j.get("nodes", [])):
    t = {k: n[k] for k in ("rotation", "scale", "matrix", "translation") if k in n}
    if t:
        print("  node %d: %s (mesh=%s)" % (i, t, n.get("mesh")))
