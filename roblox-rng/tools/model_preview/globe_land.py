#!/usr/bin/env python3
# 지구본(Models BUILDERS.globe)의 땅 덩어리 표 만들기 → src/shared/Models/GlobeLand.luau
#
# 진짜 세계 지도(Natural Earth 1:110m 육지, world-atlas 패키지의 land-110m.json)를 구 위의 점으로 바꾸고,
# 땅 점들을 "살짝 튀어나온 공"(돔) 여러 개로 덮습니다. 공 하나 = { 위도, 경도, 돔 반지름(도), 색 종류 }.
#   - 돔 반지름은 그 점에서 바다(또는 다른 색 땅)까지 거리 + 조금 → 해안선이 둥글둥글 굽이진 모양
#   - 색 종류(땅 색): 초록(기본), 모래색(사막), 눈(그린란드·남극·북극 섬) = 바탕 공 색
#   - 탐욕 덮기: 아직 안 덮인 땅 점을 가장 많이 덮는 공부터 고름(작은 섬도 하나씩은). 공 색 = 공 안쪽 점들의 많은 색
#   - 좁은 바다(홍해·아덴만·페르시아만)는 KEEP_WATER 선에서 돔이 멈춰서 물길이 남음
#   - 덧칠 공(바탕 돔 위로 살짝 더 솟은 공): 바탕 색에 묻힌 사막(이란 등) 자동 + 손으로 정한 사슬(ACCENTS) —
#     중앙아시아 마른 띠(카스피해 → 카자흐 초원 → 고비, 모래색), 히말라야 눈 띠, 짙은 초록 열대림(아마존·콩고·동남아)
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
SLACK = 2.5  # 돔이 바다 쪽으로 넘어가도 되는 폭(도)
CAP_MIN = 3.4  # 가장 작은 돔(도) — 작은 섬
CAP_MIN_STRAIT = 1.0  # 좁은 바다 곁에서는 이만큼 작은 돔까지 씀(그보다 작아야 하면 그 자리엔 공을 두지 않음)
CAP_MAX = {"green": 20, "ice": 24}
CORE = 0.8  # 돔 반지름의 이 비율 안쪽 점만 "덮였다"고 셈(가장자리는 얇아서)
COVER_TARGET = 0.92  # 땅 점을 이만큼 덮으면 멈춤
MIN_COMPONENT = 3  # 이보다 점이 적은 섬은 버림(아래 KEEP 은 예외)
KEEP = [(20.5, -157.0)]  # 하와이(태평양이 너무 비지 않게)
# 꼭 덮을 곳(탐욕 덮기가 남긴 가느다란 끝): 인도 남쪽 끝(북위 약 8도), 그리고 좁은 바다 곁 해안
# (수에즈·시나이, 예멘, 에리트레아, 사우디 홍해 쪽, 요르단·타북, 아랍에미리트) — 물길을 지키느라 작은 돔만
# 쓸 수 있는 곳이라 덮기 목표(COVER_TARGET)에 먼저 닿으면 빠져서, 아프리카가 아시아와 떨어져 보였음
MUST_COVER = [
    (8.6, 77.4),
    (30.6, 33.4),
    (29.3, 33.9),
    (14.4, 44.3),
    (13.4, 43.6),
    (13.6, 42.2),
    (21.8, 40.2),
    (27.8, 36.9),
    (24.6, 54.9),
]
RADIUS = 4  # 모형의 지구 반지름(Models/init.luau globe 의 radius)
# 돔 높이 = clamp(DOME_SLOPE * 반지름 * 돔 반지름(라디안), DOME_MIN, DOME_MAX) — 모형 코드와 같은 값이어야 함.
# 큰(내륙) 돔은 낮고 넓게(겹친 자리의 골·주름이 얕음), 가장 낮아도 광장 크기(2.6배)에서 0.1 스터드 넘게 솟음
DOME_SLOPE, DOME_MIN, DOME_MAX = 0.1, 0.04, 0.05
ACCENT_MAX = 4  # 자동 색 덧칠 공(사막) 최대 개수
ACCENT_MIN_POINTS = 12  # 자동 덧칠 공 하나가 이만큼은 고쳐야 얹음
ACCENT_CAP_MAX = 10
ACCENT_SPILL = 1.5  # 자동 덧칠 공이 다른 색 자리로 넘어가도 되는 폭(도)
# 덧칠 공 높이 = 그 자리 윗면 + LIFT. 덧칠 공은 넓고 낮게(보이는 반지름의 약 2배 돔이 바탕 속에서 살짝만 솟음)
ACCENT_LIFT = {"desert": 0.012, "forest": 0.012, "ice": 0.018}

# 좁은 바다의 가운데 선(위도, 경도): 돔 가장자리가 이 선에서 WATER_MARGIN(도) 안으로 들어오지 못함
KEEP_WATER = [
    # 홍해 → 바브엘만데브 → 아덴만(1:110m 지도에서는 해협이 막혀 있어서 선이 해협을 뚫음)
    [(27.0, 34.4), (25.5, 35.6), (23.5, 37.0), (21.5, 38.3), (19.5, 39.3), (17.5, 40.3), (15.5, 41.3)]
    + [(13.5, 42.6), (12.6, 43.4), (12.0, 45.0), (12.3, 47.5), (13.0, 50.0)],
    # 페르시아만 → 호르무즈 해협 → 오만만
    [(28.8, 49.6), (28.2, 50.2), (27.0, 51.5), (26.2, 53.5), (25.9, 55.0), (26.4, 56.4), (25.3, 57.6)],
]
WATER_MARGIN = 0.2

# 바탕 공 색 구역: (위도 최소, 최대, 경도 최소, 최대). 앞에 있는 것이 먼저.
# 사막은 크고 한눈에 알아보는 곳만(고비·칼라하리·미국 남서부처럼 작은 곳은 동그란 점처럼 보여서 뺌 — 고비는 아래 사슬)
TONES = [
    ("ice", [(59, 84, -75, -10), (-90, -60, -180, 180), (74, 90, -180, 180)]),
    (
        "desert",
        [
            (15, 31, -17, 33),  # 사하라
            (13, 31, 35, 58),  # 아라비아
            (25, 36, 55, 68),  # 이란·파키스탄
            (-31, -20, 117, 141),  # 오스트레일리아 가운데
        ],
    ),
]

# 손으로 정한 덧칠 공 사슬: (색, [(위도, 경도, 보이는 반지름(도)), ...]). 겹친 공이 이어져 띠·덩어리가 됨
# (공 하나짜리 동그란 점은 물방울무늬처럼 보여서 늘 사슬로)
ACCENTS = [
    # 중앙아시아 마른 띠: 이란 사막에서 카스피해 동쪽 → 카자흐 초원 → 타림 → 고비
    ("desert", [(40.5, 58.5, 5.0), (45.5, 56.5, 5.0), (47.5, 63.5, 5.0), (47.0, 71.0, 5.0), (45.5, 78.5, 5.0)]),
    ("desert", [(40.0, 84.5, 4.6), (43.5, 91.0, 5.0), (43.5, 98.5, 5.0), (43.0, 106.0, 5.0)]),
    # 히말라야 눈 띠(가늘게): 카라코람 → 네팔 → 부탄
    ("ice", [(33.6, 76.2, 3.2), (30.3, 80.4, 3.2), (28.3, 85.2, 3.2), (27.9, 90.2, 3.2)]),
    # 짙은 초록 열대림
    ("forest", [(-4.0, -62.0, 4.2), (-7.0, -57.5, 3.8), (-7.5, -66.5, 3.8)]),  # 아마존
    ("forest", [(0.5, 22.5, 3.6), (-2.0, 18.5, 3.2), (2.0, 17.5, 3.0)]),  # 콩고
    ("forest", [(16.5, 102.5, 3.0), (12.5, 105.5, 2.8), (0.8, 114.0, 2.6)]),  # 인도차이나 · 보르네오
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


def dome_height(cap):
    """바탕 돔 높이(모형 단위). Models/init.luau 의 globe 와 같은 식"""
    return min(max(DOME_SLOPE * RADIUS * math.radians(cap), DOME_MIN), DOME_MAX)


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

    # 바탕 색 종류
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
    # 좁은 바다 가운데 선(0.3도 간격 점)까지 거리 → 돔 반지름 한도
    water = []
    for line in KEEP_WATER:
        for (la0, lo0), (la1, lo1) in zip(line, line[1:]):
            steps = max(1, int(math.hypot(la1 - la0, lo1 - lo0) / 0.3))
            for t in np.arange(steps) / steps:
                water.append((la0 + (la1 - la0) * t, lo0 + (lo1 - lo0) * t))
        water.append(line[-1])
    W = unit(np.array([p[0] for p in water]), np.array([p[1] for p in water]))
    cap_water = min_angle(P, W) - WATER_MARGIN

    def fit_cap(idx, want):
        """점 idx 에 둘 돔 반지름: want 를 좁은 바다 한도로 줄임. 너무 작아지면 0(그 자리엔 공 없음)"""
        near = want > cap_water[idx]
        cap = np.where(near, cap_water[idx], want)
        return np.where(near & (cap < CAP_MIN_STRAIT), 0.0, cap)

    def greedy(sel, cap, target, found):
        """sel(땅 점 번호들)을 cap(도) 돔으로 탐욕 덮기 → found 에 (점 번호, 돔 반지름) 추가"""
        Q = P[sel]
        cover = []
        for s in range(0, len(sel), 1000):
            d = Q[s : s + 1000] @ Q.T
            lim = np.cos(np.radians(cap[s : s + 1000] * CORE))[:, None]
            for k_, row_ in enumerate(d > lim):
                cover.append(np.nonzero(row_)[0] if cap[s + k_] > 0 else np.zeros(0, int))
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
        # 꼭 덮을 곳: 그 점을 (돔 안쪽으로) 덮는 후보 중 새로 덮는 점이 가장 많은 것
        for la, lo in MUST_COVER:
            target_pt = unit(np.array(la), np.array(lo))
            if any(P[i] @ target_pt > math.cos(math.radians(cp * CORE)) for i, cp in found):
                continue
            cand = [m for m in range(len(sel)) if Q[m] @ target_pt > math.cos(math.radians(cap[m] * CORE))]
            if cand:
                best = max(cand, key=lambda m: np.count_nonzero(~covered[cover[m]]))
                covered[cover[best]] = True
                found.append((sel[best], cap[best]))
        return covered

    # 1) 바탕: 색과 상관없이 모든 땅을 덮음(해안까지 거리로 돔 크기). 공 색 = 돔 안쪽 점들의 많은 색
    sel = np.nonzero(keep)[0]
    cap_max = np.where(tone[sel] == "ice", CAP_MAX["ice"], CAP_MAX["green"])
    cap = fit_cap(sel, np.clip(d_ocean[sel] + SLACK, CAP_MIN, cap_max))
    base = []
    greedy(sel, cap, COVER_TARGET, base)
    balls = []
    for idx, cp in base:
        near = (P @ P[idx] > math.cos(math.radians(cp * CORE))) & keep
        names, counts = np.unique(tone[near].astype(str), return_counts=True)
        name = str(names[np.argmax(counts)]) if len(names) else str(tone[idx])
        balls.append((plat[idx], plon[idx], cp, name))
    n_base = len(balls)

    def surface(V):
        """방향 V 들의 맨 위 돔 윗면 높이·색(지금까지 얹은 공 모두)"""
        best = np.full(len(V), -np.inf)
        shown = np.array(["ocean"] * len(V), dtype=object)
        for la, lo, cp, name, *rest in balls:
            hgt = profile(unit(np.array(la), np.array(lo)), cp, rest[0] if rest else dome_height(cp), V)
            upd = hgt > best
            best[upd] = hgt[upd]
            shown[upd] = name
        return best, shown

    # 덧칠 공 크기 재기용 촘촘한 점(간격 약 0.4도)
    kf = np.arange(260000) + 0.5
    FINE = unit(np.degrees(np.arcsin(1 - 2 * kf / len(kf))), (np.degrees(np.pi * (1 + 5**0.5) * kf) % 360) - 180)

    def accent(la, lo, visible, name, cap_limit=None):
        """(la, lo) 에 보이는 반지름 visible(도)쯤인 덧칠 공 하나. 높이 = 가운데 윗면 + LIFT(낮게 솟음),
        돔 반지름 = 지금 윗면 위로 드러나는 넓이가 반지름 visible 원과 같아지는 크기(바다·좁은 바다 한도로 줄임)"""
        c = unit(np.array(la), np.array(lo))
        local = FINE[FINE @ c > math.cos(math.radians(min(visible * 5, 60)))]
        heights, _ = surface(local)
        centre = local @ c > math.cos(math.radians(visible * 0.5))
        top = float(np.max(heights[centre])) if np.isfinite(heights[centre]).any() else DOME_MIN
        hgt = top + ACCENT_LIFT[name]
        goal = np.count_nonzero(local @ c > math.cos(math.radians(visible)))
        lo_, hi_ = visible * 0.5, visible * 5
        for _ in range(30):
            mid = (lo_ + hi_) / 2
            shown = np.count_nonzero(profile(c, mid, hgt, local) > heights)
            lo_, hi_ = (mid, hi_) if shown < goal else (lo_, mid)
        near = int(np.argmax(P @ c))  # 가장 가까운 땅 점
        cap_ = min(hi_, d_ocean[near] + SLACK, cap_water[near])
        if cap_limit is not None:
            cap_ = min(cap_, cap_limit)
        balls.append((la, lo, cap_, name, hgt))

    # 2) 자동 덧칠: 큰 바탕 공 색에 묻힌 사막(이란·오스트레일리아 동쪽 등)
    heights, shown = surface(P)
    wrong = np.nonzero(keep & (tone == "desert") & (shown != "desert"))[0]
    if len(wrong):
        others = np.nonzero(keep & (tone != "desert"))[0]
        d_other = min_angle(P[wrong], P[others])
        cap = np.clip(np.minimum(d_ocean[wrong] + SLACK, d_other + ACCENT_SPILL), CAP_MIN, ACCENT_CAP_MAX)
        cap = np.minimum(cap, cap_water[wrong])
        Q = P[wrong]
        covered = np.zeros(len(wrong), bool)
        cover = [np.nonzero(Q @ Q[k_] > math.cos(math.radians(cap[k_] * CORE)))[0] for k_ in range(len(wrong))]
        for _ in range(ACCENT_MAX):
            gains = np.array([np.count_nonzero(~covered[c]) for c in cover])
            best = int(np.argmax(gains))
            if gains[best] < ACCENT_MIN_POINTS:
                break
            covered[cover[best]] = True
            idx = wrong[best]
            accent(plat[idx], plon[idx], cap[best] * CORE, "desert", cap_limit=cap[best] * 1.6)
    n_auto = len(balls) - n_base

    # 3) 손으로 정한 사슬(마른 띠 → 눈 띠 → 열대림 순: 나중 것이 위)
    for name, chain in ACCENTS:
        for la, lo, visible in chain:
            accent(la, lo, visible, name)

    heights, shown = surface(P)
    print(f"base {n_base}, auto accents {n_auto}, chain accents {len(balls) - n_base - n_auto}", file=sys.stderr)
    for name in ["ice", "green", "forest", "desert"]:
        print(f"{name}: balls {sum(1 for b in balls if b[3] == name)}", file=sys.stderr)
    print(f"total balls {len(balls)}, land covered {np.isfinite(heights[keep]).mean():.3f}", file=sys.stderr)
    print(f"tone match {(keep & (shown == tone)).sum() / keep.sum():.3f}", file=sys.stderr)
    hw, _ = surface(W)
    print(f"water line points under land {np.isfinite(hw).sum()} / {len(W)}", file=sys.stderr)

    order = {"ice": 1, "green": 2, "forest": 3, "desert": 4}
    lines = [
        "-- 자동 생성: tools/model_preview/globe_land.py (Natural Earth 1:110m 육지 → 겹친 돔 공). 손으로 고치지 말 것",
        "-- 한 줄 = { 위도, 경도, 돔 반지름(도), 색 종류[, 높이] } — 색 1 눈, 2 초록, 3 짙은 초록(열대림), 4 사막",
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
        yy, xx = np.mgrid[0:H2, 0:W2]
        glat = 90 - (yy + 0.5) / H2 * 180
        glon = (xx + 0.5) / W2 * 360 - 180
        G = unit(glat, glon).reshape(-1, 3)
        best_h, shown_g = surface(G)
        out = np.tile(np.array([30, 95, 200]), (len(G), 1))
        for name, rgb in colors.items():
            out[shown_g == name] = rgb
        # 윗면 기울기(음영): 경계·주름이 보이게 살짝
        hh = np.where(np.isfinite(best_h), best_h, 0).reshape(H2, W2)
        shade = np.clip(1 + (np.roll(hh, 1, 1) - hh) * 60 + (np.roll(hh, 1, 0) - hh) * 60, 0.7, 1.3)
        out = (out.reshape(H2, W2, 3) * shade[..., None]).clip(0, 255)
        m2 = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize((W2, H2))) > 127
        edge = m2 ^ np.roll(m2, 1, 0) | m2 ^ np.roll(m2, 1, 1)
        out[edge] = (0, 0, 0)
        Image.fromarray(out.astype(np.uint8)).save(PREVIEW)


main()
