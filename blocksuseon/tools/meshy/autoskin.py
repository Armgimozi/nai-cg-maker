#!/usr/bin/env python3
"""autoskin.py in.glb out.glb  -- rule-based quadruped auto-rig for Meshy GLBs (pure python, no numpy).
Assumes: single mesh/primitive, Y up, body length along Z, head at +Z (Meshy/glTF convention), standing pose.
Adds 12 joints (Root, Spine, Head, Tail, 4 legs x Upper/Lower) + JOINTS_0/WEIGHTS_0 + skin."""
import json, struct, sys, math

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
jl = struct.unpack("<I", b[12:16])[0]
J = json.loads(b[20:20 + jl])
off = 20 + jl
bl = struct.unpack("<I", b[off:off + 4])[0]
BIN = bytearray(b[off + 8:off + 8 + bl])

prim = J["meshes"][0]["primitives"][0]
acc = J["accessors"][prim["attributes"]["POSITION"]]
bv = J["bufferViews"][acc["bufferView"]]
st = bv.get("byteStride", 12)
o0 = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
V = [struct.unpack_from("<3f", BIN, o0 + i * st) for i in range(acc["count"])]
N = len(V)
xs, ys, zs = [v[0] for v in V], [v[1] for v in V], [v[2] for v in V]
ymin, ymax, zmin, zmax = min(ys), max(ys), min(zs), max(zs)
H, L = ymax - ymin, zmax - zmin
xc = sum(xs) / N

# --- feet from the lowest band, split front/back by the biggest z gap
lowb = [v for v in V if v[1] < ymin + 0.06 * H]
zz = sorted(v[2] for v in lowb)
gi = max(range(len(zz) - 1), key=lambda i: zz[i + 1] - zz[i])
zsplit = (zz[gi] + zz[gi + 1]) / 2
def core(g):
    # drop stray low verts (tail tip, chin) far from the group's median z
    m = sorted(v[2] for v in g)[len(g) // 2]
    dev = sorted(abs(v[2] - m) for v in g)[len(g) // 2]
    return [v for v in g if abs(v[2] - m) < max(3 * dev, 0.02 * L)]
ff = core([v for v in lowb if v[2] > zsplit])
bf = core([v for v in lowb if v[2] <= zsplit])
zf_in, zb_in = min(v[2] for v in ff), max(v[2] for v in bf)
xw = max(xs) - min(xs)
# belly = lowest central vertex between the front and back feet
gz = zf_in - zb_in
mid = [v for v in V if zb_in + 0.2 * gz < v[2] < zf_in - 0.2 * gz and abs(v[0] - xc) < 0.06 * xw]
belly = min(v[1] for v in mid) if mid else ymin + 0.5 * H
belly = max(belly, ymin + 0.12 * H)

legs = {}
FOOTR = 0.0
for name, grp, sx in (("FL", ff, 1), ("FR", ff, -1), ("BL", bf, 1), ("BR", bf, -1)):
    cl = [v for v in grp if (v[0] - xc > 0) == (sx > 0)] or grp
    fx = sum(v[0] for v in cl) / len(cl)
    fzc = sum(v[2] for v in cl) / len(cl)
    dd = sorted(math.hypot(v[0] - fx, v[2] - fzc) for v in cl)
    r = dd[int(0.9 * (len(dd) - 1))]
    FOOTR = max(FOOTR, r)
    band = [v for v in V if belly - 0.3 * (belly - ymin) < v[1] < belly and math.hypot(v[0] - fx, v[2] - fzc) < 4 * r]
    band = [v for v in band if (v[0] - xc > 0) == (sx > 0)] or band or cl
    hx = sum(v[0] for v in band) / len(band)
    hz = sum(v[2] for v in band) / len(band)
    torso_mid = belly + 0.35 * (ymax - belly)
    hip = (hx, torso_mid, hz)
    foot = (fx, ymin, fzc)
    knee = ((hip[0] + foot[0]) / 2, ymin + 0.45 * (belly - ymin), (hip[2] + foot[2]) / 2)
    legs[name] = dict(hip=hip, knee=knee, foot=foot)

zf = (legs["FL"]["hip"][2] + legs["FR"]["hip"][2]) / 2
zb = (legs["BL"]["hip"][2] + legs["BR"]["hip"][2]) / 2
ty = belly + 0.45 * (ymax - belly)
root = (xc, ty, zb)
spine = (xc, ty, zf)
neckz = zf + 0.35 * (zmax - zf)
head = (xc, ty + 0.1 * H, neckz)
tailz = zb - 0.35 * (zb - zmin)
tail = (xc, ty, tailz)

# joint list: name, parent index, global pos
JN = [("Root", -1, root), ("Spine", 0, spine), ("Head", 1, head), ("Tail", 0, tail)]
for name in ("FL", "FR", "BL", "BR"):
    parent = 1 if name[0] == "F" else 0
    JN.append((name + "_Upper", parent, legs[name]["hip"]))
    JN.append((name + "_Lower", len(JN) - 1, legs[name]["knee"]))
idx = {n: i for i, (n, _, _) in enumerate(JN)}

def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

# --- weights
W = []
LEGK = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
blend = 0.08 * H
for (x, y, z) in V:
    w = {}
    name, lg = None, None
    if y < belly + blend:
        # nearest leg by horizontal distance to its hip->foot line at this height
        best = 1e9
        for nm, l in legs.items():
            t = (l["hip"][1] - y) / max(1e-6, l["hip"][1] - l["foot"][1])
            t = max(0.0, min(1.0, t))
            cx = l["hip"][0] + (l["foot"][0] - l["hip"][0]) * t
            cz = l["hip"][2] + (l["foot"][2] - l["hip"][2]) * t
            d = math.hypot(x - cx, z - cz)
            if d < best:
                best, name, lg = d, nm, l
        t = max(0.0, min(1.0, (y - ymin) / max(1e-6, belly - ymin)))
        if best > LEGK * FOOTR * (1.6 + 2.2 * t):
            name, lg = None, None
    if lg is not None:
        front = name[0] == "F"
        kt = smooth((y - (lg["knee"][1] - 0.5 * blend)) / blend)  # 0 below knee, 1 above
        legw = 1 - smooth((y - belly) / blend)  # 1 inside leg, fades into body
        bodyj = "Spine" if front else "Root"
        w[name + "_Lower"] = legw * (1 - kt)
        w[name + "_Upper"] = legw * kt
        w[bodyj] = w.get(bodyj, 0) + (1 - legw)
    else:
        # torso: root<->spine by z, head and tail bands
        hz = smooth((z - (neckz - 0.06 * L)) / (0.12 * L))
        tz = smooth(((tailz + 0.05 * L) - z) / (0.1 * L))
        sp = smooth((z - zb) / max(1e-6, zf - zb))
        rest = 1 - hz - tz
        if rest < 0:
            s = hz + tz; hz, tz, rest = hz / s, tz / s, 0
        w["Head"] = hz
        w["Tail"] = tz
        w["Spine"] = rest * sp
        w["Root"] = rest * (1 - sp)
    items = sorted(((v, k) for k, v in w.items() if v > 1e-4), reverse=True)[:4]
    s = sum(v for v, _ in items) or 1
    items = [(v / s, k) for v, k in items]
    while len(items) < 4:
        items.append((0.0, "Root"))
    W.append(items)

# --- write buffers
def pad4(ba):
    while len(ba) % 4:
        ba.append(0)
pad4(BIN)
def add_view(data, target=None):
    pad4(BIN)
    o = len(BIN)
    BIN.extend(data)
    v = {"buffer": 0, "byteOffset": o, "byteLength": len(data)}
    if target:
        v["target"] = target
    J["bufferViews"].append(v)
    return len(J["bufferViews"]) - 1
jd = bytearray()
wd = bytearray()
for items in W:
    jd.extend(struct.pack("<4B", *[idx[k] for _, k in items]))
    wd.extend(struct.pack("<4f", *[v for v, _ in items]))
jv = add_view(bytes(jd), 34962)
wv = add_view(bytes(wd), 34962)
J["accessors"].append({"bufferView": jv, "componentType": 5121, "count": N, "type": "VEC4"})
prim["attributes"]["JOINTS_0"] = len(J["accessors"]) - 1
J["accessors"].append({"bufferView": wv, "componentType": 5126, "count": N, "type": "VEC4"})
prim["attributes"]["WEIGHTS_0"] = len(J["accessors"]) - 1
ibm = bytearray()
for _, _, p in JN:
    m = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -p[0], -p[1], -p[2], 1]  # column-major translate(-p)
    ibm.extend(struct.pack("<16f", *m))
iv = add_view(bytes(ibm))
J["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(JN), "type": "MAT4"})
ibm_acc = len(J["accessors"]) - 1

base = len(J["nodes"])
for i, (n, par, p) in enumerate(JN):
    pp = JN[par][2] if par >= 0 else (0, 0, 0)
    J["nodes"].append({"name": n, "translation": [p[0] - pp[0], p[1] - pp[1], p[2] - pp[2]]})
for i, (n, par, p) in enumerate(JN):
    if par >= 0:
        J["nodes"][base + par].setdefault("children", []).append(base + i)
meshnode = next(i for i, n in enumerate(J["nodes"]) if "mesh" in n)
J["nodes"][meshnode]["skin"] = 0
J["nodes"][meshnode]["name"] = J["nodes"][meshnode].get("name") or "Body"
J["skins"] = [{"joints": [base + i for i in range(len(JN))], "inverseBindMatrices": ibm_acc, "skeleton": base, "name": "Armature"}]
sc = J["scenes"][J.get("scene", 0)]
sc["nodes"] = list(sc["nodes"]) + [base]
J["buffers"][0]["byteLength"] = len(BIN)

js = json.dumps(J, separators=(",", ":")).encode()
while len(js) % 4:
    js += b" "
out = bytearray()
out += struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(BIN))
out += struct.pack("<I4s", len(js), b"JSON") + js
out += struct.pack("<I4s", len(BIN), b"BIN\x00") + BIN
open(dst, "wb").write(out)
print(json.dumps({"verts": N, "belly": round(belly, 3), "zsplit": round(zsplit, 3), "ymin": round(ymin, 3), "ymax": round(ymax, 3),
                  "joints": {n: [round(c, 3) for c in p] for n, _, p in JN}}, indent=0))
