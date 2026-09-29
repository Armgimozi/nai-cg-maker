#!/usr/bin/env python3
# 지구본(Models BUILDERS.globe)의 땅 덩어리 표 만들기 → src/shared/Models/GlobeLand.luau
#
# 진짜 세계 지도(Natural Earth 1:110m 육지, world-atlas 패키지의 land-110m.json)를 구 위의 점으로 바꾸고,
# 땅 점들을 "살짝 튀어나온 공"(돔) 여러 개로 덮습니다. 공 하나 = { 위도, 경도, 돔 반지름(도), 색 종류 }.
#   - 돔 반지름은 그 점에서 바다(또는 다른 색 땅)까지 거리 + 조금 → 해안선이 둥글둥글 굽이진 모양
#   - 색 종류(땅 색): 초록(기본), 짙은 초록(숲·산맥), 모래색(사막), 눈(그린란드·남극·북극 섬)
#   - 탐욕 덮기: 아직 안 덮인 땅 점을 가장 많이 덮는 공부터 고름(작은 섬도 하나씩은). 공 색 = 공 안쪽 점들의 많은 색
# 모형 코드는 이 표로 공 크기·높이를 계산합니다(Models/init.luau 의 globe). 표를 바꾸려면 이 스크립트를 다시 돌림:
#   (cd /tmp && npm pack world-atlas@2.0.2 && tar xzf world-atlas-2.0.2.tgz)   # package/land-110m.json
#   python3 tools/model_preview/globe_land.py /tmp/package/land-110m.json src/shared/Models/GlobeLand.luau
# numpy + Pillow 만 씀.
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw

LAND_JSON = sys.argv[1]
OUT = sys.argv[2]
PREVIEW = sys.argv[3] if len(sys.argv) > 3 else None

N_POINTS = 26000  # 구 위 표본 점(간격 약 1.25도)
SLACK = 2.2  # 돔이 바다 쪽으로 넘어가도 되는 폭(도)
CAP_MIN = 3.4  # 가장 작은 돔(도) — 작은 섬
CAP_MAX = {"green": 20, "ice": 24}
CORE = 0.8  # 돔 반지름의 이 비율 안쪽 점만 "덮였다"고 셈(가장자리는 얇아서)
COVER_TARGET = 0.94  # 땅 점을 이만큼 덮으면 멈춤
MIN_COMPONENT = 3  # 이보다 점이 적은 섬은 버림(아래 KEEP 은 예외)
KEEP = [(20.5, -157.0)]  # 하와이(태평양이 너무 비지 않게)
RADIUS = 4  # 모형의 지구 반지름(Models/init.luau globe 의 radius)
ACCENT_MAX = 6  # 색 덧칠 공 최대 개수(색 종류마다)
ACCENT_MIN_POINTS = 12  # 덧칠 공 하나가 이만큼은 고쳐야 얹음
ACCENT_CAP_MAX = 10
ACCENT_SPILL = 1.5  # 덧칠 공이 다른 색 자리로 넘어가도 되는 폭(도)
ACCENT_LIFT = 0.03  # 덧칠 공 = 그 자리 바탕 돔 윗면 + 이만큼

# 색 종류 구역: (위도 최소, 최대, 경도 최소, 최대). 앞에 있는 것이 먼저.
# 사막은 크고 한눈에 알아보는 곳만(고비·칼라하리·미국 남서부처럼 작은 곳은 동그란 점처럼 보여서 뺌)
TONES = [
    ("ice", [(59, 84, -75, -10), (-90, -60, -180, 180), (74, 90, -180, 180)]),
    (
        "mountain",
        [
            (27, 38, 73, 100),  # 히말라야·티베트
            (-40, -16, -76, -66),  # 안데스(남)
            (-16, 9, -80, -72),  # 안데스(북)
            (36, 58, -124, -108),  # 로키
        ],
    ),
    (
        "desert",
        [
            (15, 31, -17, 33),  # 사하라
            (13, 31, 35, 58),  # 아라비아
            (25, 36, 55, 68),  # 이란·파키스탄
            (-31, -20, 117, 141),  # 오스트레일리아 가운데
        ],
    ),
    (
        "forest",
        [
            (-14, 5, -76, -46),  # 아마존
            (-6, 5, 9, 31),  # 콩고
            (-10, 24, 94, 152),  # 동남아시아·인도네시아·뉴기니
            (52, 64, 60, 135),  # 시베리아 숲
            (48, 60, -125, -62),  # 캐나다 숲
        ],
    ),
]


def load_mask(path, width=1440, height=720):
    topo = json.load(open(path))
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(indices):
        out = []
        for i in indices:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(a if not out else a[1:])
        return out

    def unwrap(r):
        out = [r[0]]
        for lon, lat in r[1:]:
            prev = out[-1][0]
            while lon - prev > 180:
                lon -= 360
            while lon - prev < -180:
                lon += 360
            out.append((lon, lat))
        return out

    img = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(img)

    def px(p, off):
        return ((p[0] + off + 180) / 360 * width, (90 - p[1]) / 180 * height)

    geometry = topo["objects"]["land"]["geometries"][0]
    for polygon in geometry["arcs"]:
        rings = [unwrap(ring(r)) for r in polygon]
        outer = rings[0]
        if abs(outer[-1][0] - outer[0][0]) > 1:  # 남극: 경도 한 바퀴를 도는 열린 고리 → 남극점으로 닫음
            outer = outer + [(outer[-1][0], -90), (outer[0][0], -90)]
        for off in (-360, 0, 360):
            draw.polygon([px(p, off) for p in outer], fill=255)
            for hole in rings[1:]:
                draw.polygon([px(p, off) for p in hole], fill=0)
    return np.array(img) > 127


def unit(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


def dome_height(cap, name):
    """돔 높이(모형 단위). Models/init.luau 의 globe 와 같은 식"""
    h = min(max(0.15 * RADIUS * math.radians(cap), 0.045), 0.12)
    return h * 0.6 if name == "ice" else h


def profile(center, cap, height, V):
    """방향 V(단위 벡터들) 쪽 돔 윗면의 지표 위 높이. 돔 밖이면 -inf"""
    top = RADIUS + height
    cos_cap = math.cos(math.radians(cap))
    r = (RADIUS * RADIUS + top * top - 2 * RADIUS * top * cos_cap) / (2 * (top - RADIUS * cos_cap))
    c = top - r
    cos_phi = V @ center
    disc = r * r - c * c * (1 - cos_phi**2)
    t = c * cos_phi + np.sqrt(np.maximum(disc, 0))
    return np.where((disc > 0) & (cos_phi > 0) & (t > RADIUS), t - RADIUS, -np.inf)


def main():
    mask = load_mask(LAND_JSON)
    h, w = mask.shape
    k = np.arange(N_POINTS) + 0.5
    lat = np.degrees(np.arcsin(1 - 2 * k / N_POINTS))
    lon = (np.degrees(np.pi * (1 + 5**0.5) * k) % 360) - 180
    col = np.clip(((lon + 180) / 360 * w).astype(int), 0, w - 1)
    row = np.clip(((90 - lat) / 180 * h).astype(int), 0, h - 1)
    land = mask[row, col]
    xyz = unit(lat, lon)

    li = np.nonzero(land)[0]
    oi = np.nonzero(~land)[0]
    P = xyz[li]
    plat, plon = lat[li], lon[li]
    n = len(li)

    # 색 종류
    tone = np.array(["green"] * n, dtype=object)
    assigned = np.zeros(n, bool)
    for name, boxes in TONES:
        for la0, la1, lo0, lo1 in boxes:
            sel = (~assigned) & (plat >= la0) & (plat <= la1) & (plon >= lo0) & (plon <= lo1)
            tone[sel] = name
            assigned |= sel

    # 섬(연결 성분): 이웃 거리 2도 안이면 같은 섬
    cos_link = math.cos(math.radians(2.0))
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for s in range(0, n, 2000):
        d = P[s : s + 2000] @ P.T
        ii, jj = np.nonzero(d > cos_link)
        for a, b in zip(ii + s, jj):
            if a < b:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
    comp = np.array([find(a) for a in range(n)])
    sizes = {c: int((comp == c).sum()) for c in set(comp.tolist())}
    keep_pts = unit(np.array([p[0] for p in KEEP]), np.array([p[1] for p in KEEP]))
    keep = np.zeros(n, bool)
    for c, size in sizes.items():
        members = comp == c
        near_keep = (P[members] @ keep_pts.T > math.cos(math.radians(3))).any()
        if size >= MIN_COMPONENT or near_keep:
            keep |= members
    print(f"land points {n}, components {len(sizes)}, kept points {keep.sum()}", file=sys.stderr)

    # 거리: 바다까지, 다른 색 땅까지(각도, 도)
    def min_angle(A, B):
        out = np.full(len(A), 180.0)
        for s in range(0, len(A), 1500):
            d = A[s : s + 1500] @ B.T
            out[s : s + 1500] = np.degrees(np.arccos(np.clip(d.max(1), -1, 1)))
        return out

    d_ocean = min_angle(P, xyz[oi])

    def greedy(sel, cap, target, found):
        """sel(땅 점 번호들)을 cap(도) 돔으로 탐욕 덮기 → found 에 (점 번호, 돔 반지름) 추가"""
        Q = P[sel]
        cover = []
        for s in range(0, len(sel), 1000):
            d = Q[s : s + 1000] @ Q.T
            lim = np.cos(np.radians(cap[s : s + 1000] * CORE))[:, None]
            for row_ in d > lim:
                cover.append(np.nonzero(row_)[0])
        covered = np.zeros(len(sel), bool)
        while covered.mean() < target:
            gains = np.array([np.count_nonzero(~covered[c]) for c in cover])
            best = int(np.argmax(gains))
            if gains[best] == 0:
                break
            covered[cover[best]] = True
            found.append((sel[best], cap[best]))
        # 덮이지 않은 섬이 남으면(탐욕이 목표에 먼저 닿아서) 그 섬에 하나씩
        comp_sel = comp[sel]
        for c in sorted(set(comp_sel.tolist())):
            members = np.nonzero(comp_sel == c)[0]
            if covered[members].mean() < 0.4:
                gains = np.array([np.count_nonzero(~covered[cover[m]]) for m in members])
                best = int(members[np.argmax(gains)])
                covered[cover[best]] = True
                found.append((sel[best], cap[best]))
        return covered

    # 1) 바탕: 색과 상관없이 모든 땅을 덮음(해안까지 거리로 돔 크기). 공 색 = 돔 안쪽 점들의 많은 색
    sel = np.nonzero(keep)[0]
    cap_max = np.where(tone[sel] == "ice", CAP_MAX["ice"], CAP_MAX["green"])
    cap = np.clip(d_ocean[sel] + SLACK, CAP_MIN, cap_max)
    base = []
    greedy(sel, cap, COVER_TARGET, base)
    balls = []
    for idx, cp in base:
        near = (P @ P[idx] > math.cos(math.radians(cp * CORE))) & keep
        names, counts = np.unique(tone[near].astype(str), return_counts=True)
        name = str(names[np.argmax(counts)]) if len(names) else str(tone[idx])
        if name == "mountain":
            name = "forest"  # 산맥은 숲과 같은 짙은 초록(따로 솟게 하면 혹처럼 보임)
        balls.append((plat[idx], plon[idx], cp, name))

    # 2) 색 덧칠: 큰 바탕 공의 색에 묻힌 사막(이란·오스트레일리아 동쪽)·숲/산맥(티베트·캐나다) 자리에 조금 더 높은 공을 얹음
    #    (바탕 돔 윗면보다 ACCENT_LIFT 높게 — 모형 코드는 다섯째 칸 높이를 그대로 씀)
    desired = np.where(tone == "mountain", "forest", tone)

    def shown_tone():
        best = np.full(n, -np.inf)
        shown = np.array(["ocean"] * n, dtype=object)
        for la, lo, cp, name, *rest in balls:
            hgt = profile(unit(np.array(la), np.array(lo)), cp, rest[0] if rest else dome_height(cp, name), P)
            upd = hgt > best
            best[upd] = hgt[upd]
            shown[upd] = name
        return best, shown

    for name in ["desert", "forest"]:
        heights, shown = shown_tone()
        wrong = np.nonzero(keep & (desired == name) & (shown != name))[0]
        if len(wrong) == 0:
            continue
        others = np.nonzero(keep & (desired != name))[0]
        d_other = min_angle(P[wrong], P[others])
        cap = np.clip(np.minimum(d_ocean[wrong] + SLACK, d_other + ACCENT_SPILL), CAP_MIN, ACCENT_CAP_MAX)
        Q = P[wrong]
        covered = np.zeros(len(wrong), bool)
        cover = [np.nonzero(Q @ Q[k] > math.cos(math.radians(cap[k] * CORE)))[0] for k in range(len(wrong))]
        for _ in range(ACCENT_MAX):
            gains = np.array([np.count_nonzero(~covered[c]) for c in cover])
            best = int(np.argmax(gains))
            if gains[best] < ACCENT_MIN_POINTS:
                break
            covered[cover[best]] = True
            inside = P @ P[wrong[best]] > math.cos(math.radians(cap[best] * CORE))
            lift = float(np.max(heights[inside])) + ACCENT_LIFT
            idx = wrong[best]
            balls.append((plat[idx], plon[idx], cap[best], name, max(lift, dome_height(cap[best], name))))
    heights, shown = shown_tone()
    right = keep & (shown == desired)
    print(f"tone match {right.sum() / keep.sum():.3f}", file=sys.stderr)

    for name in ["ice", "green", "forest", "desert"]:
        print(f"{name}: balls {sum(1 for b in balls if b[3] == name)}", file=sys.stderr)
    print(f"total balls {len(balls)}", file=sys.stderr)

    order = {"ice": 1, "green": 2, "forest": 3, "desert": 4}
    lines = [
        "-- 자동 생성: tools/model_preview/globe_land.py (Natural Earth 1:110m 육지 → 겹친 돔 공). 손으로 고치지 말 것",
        "-- 한 줄 = { 위도, 경도, 돔 반지름(도), 색 종류[, 높이] } — 색 1 눈, 2 초록, 3 숲·산맥, 4 사막",
        "-- 높이(모형 단위)가 있는 줄 = 색 덧칠 공(바탕 돔 위로 조금 더 솟음). 없으면 모형 코드가 돔 반지름으로 정함",
        "-- stylua: ignore",
        "return {",
    ]
    for la, lo, cp, name, *rest in sorted(balls, key=lambda b: (len(b), order[b[3]], -b[2])):
        extra = f", {rest[0]:.3f}" if rest else ""
        lines.append(f"\t{{ {la:.1f}, {lo:.1f}, {cp:.1f}, {order[name]}{extra} }},")
    lines.append("}")
    open(OUT, "w").write("\n".join(lines) + "\n")
    print(OUT, file=sys.stderr)

    if PREVIEW:
        colors = {"ice": (240, 246, 252), "green": (96, 190, 80), "forest": (46, 140, 70), "desert": (236, 200, 120)}
        W2, H2 = 1080, 540
        img = Image.new("RGB", (W2, H2), (30, 95, 200))
        yy, xx = np.mgrid[0:H2, 0:W2]
        glat = 90 - (yy + 0.5) / H2 * 180
        glon = (xx + 0.5) / W2 * 360 - 180
        G = unit(glat, glon).reshape(-1, 3)
        best_h = np.full(len(G), -np.inf)
        out = np.array(img).reshape(-1, 3).copy()
        for la, lo, cp, name, *rest in balls:
            hgt = profile(unit(np.array(la), np.array(lo)), cp, rest[0] if rest else dome_height(cp, name), G)
            upd = hgt > best_h
            best_h[upd] = hgt[upd]
            out[upd] = colors[name]
        m2 = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize((W2, H2))) > 127
        out = out.reshape(H2, W2, 3)
        edge = m2 ^ np.roll(m2, 1, 0) | m2 ^ np.roll(m2, 1, 1)
        out[edge] = (0, 0, 0)
        Image.fromarray(out.astype(np.uint8)).save(PREVIEW)


main()
