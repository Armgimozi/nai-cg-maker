"""10채 집 구역 배치 검사 (0.3.7 계획) — 배포 월드 좌표.

usage: python3 -I check_layout10.py <plots10_spec.json> <labyrinth-village.yml> <plugin resources/village> <out.json>

보는 것
 1. 집터 10채: 14×14, 서로 안 겹침, 사이 1칸(생울타리) 이상
 2. 공용 칸(이음 칸·골목·받는 칸·가운데 골목·등불길·우물길): 마을 길 1 첫 칸(-137, 26..27)에서 4방향 BFS 로
    모든 대문 바깥 칸에 닿는가 · 대문 칸이 집터 바로 바깥 울타리 줄인가
 3. 집터·공용 칸 vs 마을 보호 상자·마을 길 칸 (겹침 0)
 4. 집터·공용 칸 vs 광산 구역 east·south_east 마스크 (조각(+slack)·길 칸 + R + B, 실제 jar mine.json)
 5. PvP: 구역 보호 상자(공용 칸·울타리 줄) + safe_margin 8 이 집터 안을 모두 덮는가
 6. 국경 (WildBorder.compute 규칙): 마을 + 광산(east|south_east) + 집 구역 보호 상자 + 30
 7. 걸음 수: 광장 스폰 → 이음 칸 (맨해튼) + 공용 칸 BFS → 대문
"""
import sys, json, math
from collections import deque
import yaml

SPEC, VYML, RES, OUT = sys.argv[1:5]
S = json.load(open(SPEC))
V = yaml.safe_load(open(VYML))
MINE = json.load(open(RES + "/districts/mine.json"))


def box2(b):
    if len(b) == 6:
        return (min(b[0], b[3]), min(b[2], b[5]), max(b[0], b[3]), max(b[2], b[5]))
    return (min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3]))


def cells(b):
    x0, z0, x1, z1 = box2(b)
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


res = {"problems": []}
P = res["problems"]
plots = S["plots"]
site = S["site"]

# ── 1. 집터 ──
pc = {p["id"]: cells(p["box"]) for p in plots}
for p in plots:
    x0, z0, x1, z1 = box2(p["box"])
    if (x1 - x0 + 1, z1 - z0 + 1) != (14, 14):
        P.append("집터 %d 크기 %dx%d" % (p["id"], x1 - x0 + 1, z1 - z0 + 1))


def ring(cs):
    out = set()
    for (x, z) in cs:
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                out.add((x + dx, z + dz))
    return out - cs


ids = sorted(pc)
for i in ids:
    for j in ids:
        if i < j and (pc[i] & pc[j] or ring(pc[i]) & pc[j]):
            P.append("집터 %d · %d 겹침 또는 사이 0칸" % (i, j))
res["plots"] = len(plots)

# ── 2. 공용 칸 ──
pub = set()
lane = site["lane"]
for b in lane["cells_box"]:
    pub |= cells(b)
pub |= cells(site["landing"])
pub |= cells([site["alley"]["x"][0], site["alley"]["z"][0], site["alley"]["x"][1], site["alley"]["z"][1]])
for st in site["streets"]:
    pub |= cells(st["box"])
for i in ids:
    if pc[i] & pub:
        P.append("집터 %d 가 공용 칸과 겹침: %s" % (i, sorted(pc[i] & pub)[:3]))
start = [c for c in pub if c in ((-138, 26), (-138, 27))]
seen = {c: 0 for c in start}
q = deque(start)
while q:
    c = q.popleft()
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (c[0] + d[0], c[1] + d[1])
        if n in pub and n not in seen:
            seen[n] = seen[c] + 1
            q.append(n)
res["public_cells"] = len(pub)
res["public_reached"] = len(seen)
sp = V["spawn"]
to_join = abs(sp[0] - (-137)) + abs(sp[2] - 26)
walk = {}
for p in plots:
    gx, gz = p["gate"]
    pb = box2(p["box"])
    # 대문 = 집터 바로 바깥 줄 (앞쪽)
    front_ok = (p["front"] == "S" and gz == pb[3] + 1) or (p["front"] == "N" and gz == pb[1] - 1)
    if not front_ok or not (pb[0] <= gx <= pb[2]):
        P.append("집터 %d 대문 %s 가 앞 울타리 줄이 아님" % (p["id"], p["gate"]))
    out = (gx, gz + (1 if p["front"] == "S" else -1))
    if out not in seen:
        P.append("집터 %d 대문 바깥 칸 %s 가 이음 칸에서 안 닿음" % (p["id"], out))
    else:
        walk[p["id"]] = round(to_join + seen[out] + 1)
    hx, hz = p["home"]["x"], p["home"]["z"]
    if (math.floor(hx), math.floor(hz)) not in pub:
        P.append("집터 %d 집 가기 칸 (%s, %s) 이 공용 칸이 아님" % (p["id"], hx, hz))
res["walk_spawn_to_gate"] = walk

# ── 3. 마을 ──
vprot = [box2(b) for b in V["protect"]]
vpath = set()
for pth in V["paths"]:
    for c in pth["cells"].split(";"):
        x, z, y = map(int, c.split(","))
        vpath.add((x, z))
vcells = set()
for b in vprot:
    vcells |= cells(b)
hit = {i: len(pc[i] & (vcells | vpath)) for i in ids}
res["plots_vs_village"] = {k: v for k, v in hit.items() if v}
if any(hit.values()):
    P.append("집터가 마을 보호 상자·길과 겹침: %s" % res["plots_vs_village"])
ph = pub & (vcells | vpath)
res["public_vs_village"] = len(ph)
if ph:
    P.append("공용 칸이 마을 보호 상자·길과 겹침 %d칸 (예 %s)" % (len(ph), sorted(ph)[:3]))
res["junction_touches_path1"] = (-137, 26) in vpath and (-137, 27) in vpath

# ── 4. 광산 마스크 (실제 jar mine.json) ──
CX, CZ = MINE["shipped"]["center"]
T = MINE["shipped"]["turns"]
DT = {"north": 0, "east": 1, "south": 2, "west": 3}


def around(x, z, t):
    t %= 4
    return [(x, z), (-z, x), (-x, -z), (z, -x)][t]


def dims(w, d, t):
    return (d, w) if t % 2 else (w, d)


def to_w(vx, vz):
    a = around(vx, vz, T)
    return (CX + a[0], CZ + a[1])


R, B = MINE["mask"]["R"], MINE["mask"]["B"]


def mine_mask(site_id):
    s = [x for x in MINE["sites"] if x["id"] == site_id][0]
    sx, sz = s.get("shift", [0, 0])
    drop = set(s.get("drop", []))
    seeds = set()
    for i, e in enumerate(MINE["pieces"]):
        if i in drop:
            continue
        bp = json.load(open(RES + "/pieces/" + e["piece"] + ".json"))
        w, _, d = bp["size"]
        vd = dims(w, d, DT[e["front"]])
        ax, az = e["at"][0] + sx, e["at"][1] + sz
        lx0, lz0 = ax - vd[0] // 2, az - vd[1] // 2
        a, c = to_w(lx0, lz0), to_w(lx0 + vd[0] - 1, lz0 + vd[1] - 1)
        sl = e.get("slack", bp.get("slack", 3 if bp.get("deco") else 2))
        seeds |= cells([min(a[0], c[0]) - sl, min(a[1], c[1]) - sl, max(a[0], c[0]) + sl, max(a[1], c[1]) + sl])
    rep = {int(k): v for k, v in s.get("replace_paths", {}).items()}
    for i, pth in enumerate(MINE["paths"]):
        pts = rep[i] if i in rep else [[q[0] + sx, q[1] + sz] for q in pth["points"]]
        pts = [to_w(*q) for q in pts]
        h = pth.get("width", 3) // 2 + 1
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            n = int(max(abs(x1 - x0), abs(z1 - z0)) * 4) + 1
            for k in range(n + 1):
                x = round(x0 + (x1 - x0) * k / n)
                z = round(z0 + (z1 - z0) * k / n)
                seeds |= cells([x - h, z - h, x + h, z + h])
    xs = [c[0] for c in seeds]
    zs = [c[1] for c in seeds]
    grow = R + B
    mask = set()
    for (x, z) in seeds:
        pass
    # 체비셰프 R+B 넓히기 (열 단위 — 칸 수가 작아 그대로)
    for (x, z) in seeds:
        for dx in range(-grow, grow + 1):
            for dz in range(-grow, grow + 1):
                mask.add((x + dx, z + dz))
    return seeds, mask, (min(xs), min(zs), max(xs), max(zs))


for sid in ("east", "south_east"):
    seeds, mask, bb = mine_mask(sid)
    hp = {i: len(pc[i] & mask) for i in ids}
    hpub = pub & mask
    gap = min(min(abs(x - mx) + 0 for (mx, mz) in mask for (x, z) in [(box2(p["box"])[2], 0)]) for p in plots) if False else None
    mx0 = min(c[0] for c in mask)
    res["mine_" + sid] = {"seed_bbox": bb, "mask_xmin": mx0, "plots_hit": {k: v for k, v in hp.items() if v}, "public_hit": len(hpub),
                          "east_plot_gap_x": mx0 - max(box2(p["box"])[2] for p in plots) - 1}
    if any(hp.values()):
        P.append("집터가 광산 %s 마스크와 겹침: %s" % (sid, res["mine_" + sid]["plots_hit"]))
    if hpub:
        P.append("공용 칸이 광산 %s 마스크와 겹침 %d칸 (예 %s)" % (sid, len(hpub), sorted(hpub)[:3]))

# ── 5. PvP: 구역 보호 상자 = 공용 칸 + 울타리 줄(집터 둘레) ──
prot = set(pub)
for i in ids:
    prot |= ring(pc[i])
cov = {}
for i in ids:
    m = 8
    need = pc[i]
    ok = 0
    for (x, z) in need:
        if any(abs(x - a) <= m and abs(z - b) <= m for (a, b) in prot if abs(x - a) <= m and abs(z - b) <= m):
            ok += 1
    cov[i] = "%d/%d" % (ok, len(need))
    if ok != len(need):
        P.append("집터 %d PvP 안전 칸 %s" % (i, cov[i]))
res["pvp_cover"] = cov

# ── 6. 국경 ──
def border(boxes, margin=30):
    c = V["center"]
    r = V["radius"]
    x0, x1, z0, z1 = c[0] - r, c[0] + r, c[2] - r, c[2] + r
    for b in boxes:
        x0, z0, x1, z1 = min(x0, b[0]), min(z0, b[1]), max(x1, b[2]), max(z1, b[3])
    minX, maxX, minZ, maxZ = x0, x1 + 1, z0, z1 + 1
    half = max(maxX - minX, maxZ - minZ) / 2 + margin
    cx, cz = (minX + maxX) / 2, (minZ + maxZ) / 2
    return (cx - half, cz - half, cx + half, cz + half)


hx = [c[0] for c in prot]
hz = [c[1] for c in prot]
hb = (min(hx), min(hz), max(hx), max(hz))
res["homes_protect_bbox"] = hb
for sid in ("east", "south_east", None):
    boxes = list(vprot) + [hb]
    if sid:
        boxes.append(res["mine_" + sid]["seed_bbox"])
    B4 = border(boxes)
    inside = all(B4[0] <= box2(p["box"])[0] and box2(p["box"])[2] + 1 <= B4[2] and B4[1] <= box2(p["box"])[1] and box2(p["box"])[3] + 1 <= B4[3] for p in plots)
    res["border_" + (sid or "no_mine")] = {"x": [B4[0], B4[2]], "z": [B4[1], B4[3]], "size": B4[2] - B4[0], "plots_inside": inside}
    if not inside:
        P.append("집터가 국경 밖 (%s)" % sid)

res["ok"] = not P
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(0 if res["ok"] else 1)
