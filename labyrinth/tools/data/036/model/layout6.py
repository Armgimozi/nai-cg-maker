#!/usr/bin/env python3
"""광산 6층 청사진 시안 (광석이 섞인 층) + 손 닿는 범위 검사 — design036/tools/mine_layout.py 를 6층·섞임으로 고친 것.

층마다: 가운데 승강기 홀 11×9 + 갱도 3갈래(폭 3, 높이 4) + 곁방 + 끝 채굴장 (5·6층은 둥근 굴).
광맥 = 벽 블록 무더기 3~5칸, 무더기 하나는 광석 한 종류. 층의 광석 수 = 광맥 수 × 섞임 무게 (가장 큰 나머지).
손 닿는 범위 (R §2-8 바른 방식): 발 = 바닥+1, 눈 = 바닥+2.62, 선 자리 아무 곳(0.1칸 격자, 몸 폭 0.6),
눈 → 블록 상자의 가장 가까운 점 ≤ 4.5. 한도 REACH_MAX = 12.
서버 한도 (보강): 바닐라 서버는 5.5 까지 받으므로 광산이 4.5 + 0.25 를 넘는 부수기는 수확하지 않는다 → 그 거리(4.75)에서도 ≤ 12 인지 잰다.
결과: out/L<n>.txt (ASCII) · out/layout.json (Q1 tools/mine/ 이 최종 청사진을 만들 때의 출발점).

  python3 -B layout6.py
"""
import json
import math
import random
import sys
from collections import deque
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import params as P  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
SZ = 61
C = SZ // 2
REACH = P.REACH_CLIENT
REACH_SERVER = P.REACH_CLIENT + P.REACH_SERVER_SLACK
REACH_MAX = 12
EYE = 2.62
LETTER = {'copper': 'c', 'iron': 'i', 'silver': 's', 'gold': 'g', 'mithril': 'm', 'orichalcum': 'o'}
SHAPE = {1: 'drifts', 2: 'drifts', 3: 'drifts', 4: 'fault', 5: 'geode', 6: 'cavern'}
SEED = {1: 11, 2: 22, 3: 33, 4: 44, 5: 55, 6: 66}


def split_counts(total, weights):
    """가장 큰 나머지 — 합이 total 이 되게 정수로."""
    tw = sum(weights.values())
    raw = {k: total * w / tw for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    rest = total - sum(out.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - out[k]), k))[:rest]:
        out[k] += 1
    return {k: v for k, v in out.items() if v > 0}


def carve(g, x0, z0, x1, z1):
    for z in range(min(z0, z1), max(z0, z1) + 1):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            if 1 <= x < SZ - 1 and 1 <= z < SZ - 1:
                g[z][x] = '.'


def disc(g, cx, cz, r):
    for z in range(SZ):
        for x in range(SZ):
            if (x - cx) ** 2 + (z - cz) ** 2 <= r * r and 1 <= x < SZ - 1 and 1 <= z < SZ - 1:
                g[z][x] = '.'


def build(n):
    g = [['#'] * SZ for _ in range(SZ)]
    carve(g, C - 5, C - 4, C + 5, C + 4)                     # 승강기 홀 11×9 (관리소 칸 = 1층 홀 북쪽 벽감)
    carve(g, C - 24, C - 1, C - 6, C + 1)
    carve(g, C + 6, C - 1, C + 24, C + 1)
    carve(g, C - 1, C + 5, C + 1, C + 20)
    carve(g, C - 1, C - 7, C + 1, C - 5)                      # 북쪽 벽감 (표지판·관리소)
    carve(g, C - 17, C - 6, C - 13, C - 2)
    carve(g, C + 13, C + 2, C + 17, C + 6)
    carve(g, C + 2, C + 11, C + 6, C + 15)
    shape = SHAPE[n]
    if shape == 'geode':
        disc(g, C, C + 19, 7.5)
        carve(g, C - 28, C - 4, C - 22, C + 4)
        carve(g, C + 22, C - 4, C + 28, C + 4)
    elif shape == 'cavern':
        disc(g, C, C + 20, 8.0)
        disc(g, C - 25, C, 5.5)
        disc(g, C + 25, C, 5.5)
    elif shape == 'fault':                                    # 비스듬한 단층: 끝 채굴장을 어긋나게
        carve(g, C - 28, C - 6, C - 22, C + 2)
        carve(g, C + 22, C - 2, C + 28, C + 6)
        carve(g, C - 3, C + 20, C + 5, C + 27)
    else:
        carve(g, C - 28, C - 4, C - 22, C + 4)
        carve(g, C + 22, C - 4, C + 28, C + 4)
        carve(g, C - 4, C + 20, C + 4, C + 27)
    g[C][C] = 'L'
    return g


def walkable(g, x, z):
    return 0 <= x < SZ and 0 <= z < SZ and g[z][x] in '.L'


def wall_faces(g):
    out = []
    for z in range(1, SZ - 1):
        for x in range(1, SZ - 1):
            if g[z][x] != '#':
                continue
            if any(g[z + dz][x + dx] in '.L' for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out.append((x, z))
    return out


def in_hall(x, z):
    return abs(x - C) <= 6 and abs(z - C) <= 5


def near_box(e, b):
    return math.sqrt(sum((max(b[i], min(e[i], b[i] + 1)) - e[i]) ** 2 for i in range(3)))


def stand_points(g, x, z, fine):
    """그 바닥 칸에서 눈이 있을 수 있는 점 (몸 폭 0.6 → 벽 쪽 0.3 안쪽)."""
    lo_x = x + (0.3 if not walkable(g, x - 1, z) else 0.0)
    hi_x = x + (0.7 if not walkable(g, x + 1, z) else 1.0)
    lo_z = z + (0.3 if not walkable(g, x, z - 1) else 0.0)
    hi_z = z + (0.7 if not walkable(g, x, z + 1) else 1.0)
    k = 10 if fine else 4
    for i in range(k + 1):
        for j in range(k + 1):
            yield (lo_x + (hi_x - lo_x) * i / k, EYE, lo_z + (hi_z - lo_z) * j / k)


def reach_at(g, x, z, veins, fine, reach=REACH):
    best = 0
    for e in stand_points(g, x, z, fine):
        n = sum(1 for (px, py, pz, _) in veins if near_box(e, (px, py, pz)) <= reach)
        best = max(best, n)
    return best


def place(L):
    n = L['n']
    rnd = random.Random(SEED[n])
    g = build(n)
    faces = [f for f in wall_faces(g) if not in_hall(*f) and not (abs(f[0] - C) <= 2 and f[1] < C - 4)]
    rnd.shuffle(faces)
    face_set = set(faces)
    need = split_counts(L['veins'], L['ore_w'])
    veins, used = [], set()

    def ok(cells):
        pts = veins + cells
        for (vx, _, vz, _) in cells:
            for sz in range(vz - 5, vz + 6):
                for sx in range(vx - 5, vx + 6):
                    if walkable(g, sx, sz) and reach_at(g, sx, sz, pts, False) > REACH_MAX - 2:
                        return False
        return True

    guard = 0
    while any(v > 0 for v in need.values()) and guard < 40000:
        guard += 1
        x, z = faces[guard % len(faces)]
        if (x, z) in used:
            continue
        ore = max((o for o in need if need[o] > 0), key=lambda o: (need[o], o))
        size = min(need[ore], rnd.choice([3, 4, 4, 5]))
        nb = [(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
              if (x + dx, z + dz) in face_set and (x + dx, z + dz) not in used]
        cols = [(x, z)] + nb[:1]
        cells = [(cx, y, cz, ore) for (cx, cz) in cols for y in (1, 2, 3)][:size]
        if len(cells) < min(3, need[ore]) or not ok(cells):
            continue
        veins += cells
        need[ore] -= len(cells)
        for dz in range(-2, 3):
            for dx in range(-2, 3):
                used.add((x + dx, z + dz))
    # 보석 노드: 끝 채굴장 벽 가운데 + 곁방 벽 (층마다 gem_nodes 개, 종류 = gem_w 가장 큰 나머지)
    spots = [(C - 29, C), (C + 29, C), (C, C + 28), (C - 15, C - 7), (C + 15, C + 7), (C + 4, C + 16)]
    gem_types = []
    for gid, k in sorted(split_counts(L['gem_nodes'], L['gem_w']).items(), key=lambda kv: P.GEM[kv[0]]['rank']):
        gem_types += [gid] * k
    gems = []
    for (gx, gz) in spots:
        if len(gems) >= len(gem_types):
            break
        # 그 자리에서 가장 가까운 벽 칸 (바닥과 맞닿음)
        cand = sorted((f for f in faces if (f[0], f[1]) not in {(a, b) for a, b, _, _ in gems}),
                      key=lambda f: (abs(f[0] - gx) + abs(f[1] - gz), f))
        if cand:
            fx, fz = cand[0]
            gems.append((fx, 2, fz, gem_types[len(gems)]))
    return g, veins, gems, need


def lint(g, veins):
    seen = {(C, C)}
    q = deque([(C, C)])
    dist = {(C, C): 0}
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if walkable(g, nx, nz) and (nx, nz) not in seen:
                seen.add((nx, nz))
                dist[(nx, nz)] = dist[(x, z)] + 1
                q.append((nx, nz))
    floor = [(x, z) for z in range(SZ) for x in range(SZ) if walkable(g, x, z)]
    worst, at, worst_srv = 0, None, 0
    for (x, z) in floor:
        r = reach_at(g, x, z, veins, True)
        if r > worst:
            worst, at = r, (x - C, z - C)
        worst_srv = max(worst_srv, reach_at(g, x, z, veins, True, REACH_SERVER))
    ends = [min(seen, key=lambda p: (p[0], p[1])), max(seen, key=lambda p: (p[0], -p[1])), max(seen, key=lambda p: (p[1], p[0]))]
    loop = sum(2 * dist.get(e, 0) for e in ends)
    return {'floor_cells': len(floor), 'unreached': len(floor) - len(seen), 'reach_max': worst, 'reach_max_at': at,
            'reach_max_server': worst_srv, 'loop_blocks': loop}


def ascii_map(g, veins, gems):
    m = [row[:] for row in g]
    for (x, _, z, ore) in veins:
        ch = LETTER[ore]
        m[z][x] = ch.upper() if m[z][x] in (ch, ch.upper()) else ch
    for (x, _, z, gid) in gems:
        m[z][x] = str(P.GEM[gid]['rank'])
    return [''.join(r) for r in m]


def main():
    res = {}
    for L in P.LEVELS:
        g, veins, gems, short = place(L)
        li = lint(g, veins)
        counts = {}
        for v in veins:
            counts[v[3]] = counts.get(v[3], 0) + 1
        clusters = {}
        cols = {}
        for (x, _, z, o) in veins:
            cols.setdefault(o, set()).add((x, z))
        for o, s in cols.items():
            clusters[o] = len(s)
        n = L['n']
        res[n] = {'id': L['id'], 'name': L['name'], 'floor_y': L['floor_y'], 'shape': SHAPE[n], 'counts': counts,
                  'target': split_counts(L['veins'], L['ore_w']), 'short': {k: v for k, v in short.items() if v > 0},
                  'columns': clusters, 'gem_nodes': [[x - C, L['floor_y'] + y, z - C, gid] for (x, y, z, gid) in gems], **li,
                  'veins': [[x - C, L['floor_y'] + y, z - C, o] for (x, y, z, o) in veins],
                  'lift': [0, L['floor_y'] + 1, 0], 'landing': [0.5, L['floor_y'] + 1, 3.5, 0.0]}
        hdr = [f"광산 {L['name']} ({L['id']}, 바닥 y={L['floor_y']}, 61×61, 가운데 L = 승강기 (월드 0,{L['floor_y'] + 1},0))",
               '# 바위  . 바닥  L 승강기  1~6 보석 노드(보석 등급)  소문자 = 광맥 무더기 칸(1~2블록), 대문자 = 같은 칸 3블록',
               '글자: ' + ' '.join(f"{v}={k}" for k, v in LETTER.items()) + f"  ·  블록 {counts}  ·  손 닿는 최대 {li['reach_max']} (한도 {REACH_MAX})"
               + f"  ·  한 바퀴 {li['loop_blocks']}칸"]
        (OUT / f"L{n}.txt").write_text('\n'.join(hdr + ascii_map(g, veins, gems)) + '\n', encoding='utf-8')
        print(n, L['name'], counts, 'short', res[n]['short'], 'gems', [x[3] for x in res[n]['gem_nodes']], 'reach', li['reach_max'],
              li['reach_max_at'], 'reach@server', li['reach_max_server'], 'loop', li['loop_blocks'], 'unreached', li['unreached'])
    (OUT / 'layout.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
