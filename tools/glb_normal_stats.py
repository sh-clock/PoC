#!/usr/bin/env python3
"""Full per-primitive normal statistics: detect degenerate/garbage normals
(all-up walls, zero normals, non-unit clusters) that would break N.L."""
import json, struct, sys, collections, math

path = "/home/z/my-project/poc_v5/input/THRF9FD.glb"
data = open(path, "rb").read()
jlen = struct.unpack("<I", data[12:16])[0]
j = json.loads(data[20:20 + jlen].decode("utf-8"))
bin_len = struct.unpack("<I", data[20 + jlen:24 + jlen])[0]
bin_data = data[28 + jlen:28 + jlen + bin_len]

accs = j["accessors"]; views = j["bufferViews"]
mats = j.get("materials", [])

def acc_off(i):
    a = accs[i]; v = views[a["bufferView"]]
    return a, v.get("byteOffset", 0) + a.get("byteOffset", 0)

print("%-10s %-8s %6s  %s" % ("mesh/prim", "alpha", "verts", "normal summary"))
degenerate = 0
for mi, m in enumerate(j.get("meshes", [])):
    for pi, p in enumerate(m["primitives"]):
        attrs = p.get("attributes", {})
        if "NORMAL" not in attrs:
            continue
        a, off = acc_off(attrs["NORMAL"])
        if a.get("componentType") != 5126:
            print("m%d/%d NON-FLOAT normals ct=%d" % (mi, pi, a["componentType"]))
            continue
        n = a["count"]
        vals = struct.unpack_from("<" + "f" * (3 * min(n, 4000)), bin_data, off)
        triples = [tuple(vals[i * 3:i * 3 + 3]) for i in range(min(n, 4000))]
        zeros = sum(1 for t in triples if t == (0.0, 0.0, 0.0))
        nonunit = sum(1 for t in triples if abs(math.sqrt(sum(c * c for c in t)) - 1) > 0.01)
        # cluster dominant direction
        buckets = collections.Counter()
        for t in triples:
            # quantize to 45-degree buckets
            b = tuple(int(round(c * 2)) for c in t)
            buckets[b] += 1
        dom, cnt = buckets.most_common(1)[0]
        amode = "OPAQUE"
        if "material" in p:
            amode = mats[p["material"]].get("alphaMode", "OPAQUE")
        flag = ""
        if zeros > n * 0.5: flag += " ZERO-NORMALS!"
        if nonunit > n * 0.5: flag += " NON-UNIT!"
        if cnt > n * 0.95 and abs(dom[0]) + abs(dom[1]) + abs(dom[2]) == 2:
            flag += " FLAT(single-dir)"
        if zeros > n * 0.5 or nonunit > n * 0.5:
            degenerate += 1
        if mi < 40 or flag:
            print("m%-4d/%-3d %-8s %6d  dom=%s(%d%%) zeros=%d nonunit=%d%s" %
                  (mi, pi, amode, n, dom, 100 * cnt // max(n, 1), zeros, nonunit, flag))
print("\ndegenerate primitives:", degenerate)
