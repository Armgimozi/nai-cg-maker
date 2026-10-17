"""광산 6층 수확 모델 (순수 함수) — design036/tools/mine_model.py 를 섞인 층·등급 규칙·여러 층 돌기로 고친 것.

블록 하나에 드는 시간 = 캐는 초(광석 등급, 곡괭이) + 조준 AIM_S + 무더기 사이 걷기 CLUSTER_S / CLUSTER_SIZE.
한 층을 한 번 도는 시간 = LOOP_S + LIFT_TRIP_S + 그 층에서 캐기로 한 블록들의 시간.
광맥은 R(L) 분 뒤 다시 찬다 (0.3.7: 사람 수와 관계 없음) → 층 L 의 광석 o 공급 = n(L,o) / R(L) 블록/분 (혼자일 때).
여러 층 돌기: 층 묶음 S 를 고르면 1분에 쓰는 시간 몫 u = Σ (한 번 도는 초) / (60·R). u > 1 이면 다 못 따라가서 공급이 1/u 로 준다.
수확 = 블록 × (1 + 곡괭이 덤) × 풍부 (1 + 0.04×2). 보석 = 같은 등급 광석 블록 × 2.2% + 보석 노드 (30분, 등급 ≤ 곡괭이 + 1).
0.3.6.1: 곡괭이는 한 단계 위 광석·보석도 캔다 (params.can_mine · 느림 STRETCH_FACTOR).
0.3.7: 광맥은 사람 수와 관계 없이 R 분 뒤 다시 찬다 — n 명이 같은 층 묶음을 함께 돌면 한 사람 몫은 블록·노드 1/n (plan_rates n).
  골드 (표 E): 금속 부분집합 × 층 묶음 중 G/분 최대 = 값싼 광석을 건너뛰는 가장 잘 아는 사람 (gold_plan).
  "노드 먼저" (tour): 보석 노드를 먼저 챙기고, 노드만 걷으러 다른 층에도 들르는 사람 (한도 검사용, plan_rates_tour).
"""
import itertools
import json
from pathlib import Path

import params as P

HERE = Path(__file__).resolve().parent
RICH_F = 1 + P.RICH['chance'] * (P.RICH['multiplier'] - 1)
LEVELS = {L['n']: L for L in P.LEVELS}
RANK = {m['key']: m['rank'] for m in P.METALS}


def counts():
    """층 → {금속: 광맥 블록 수} (layout6 결과가 있으면 그것, 없으면 무게로 나눔)."""
    p = HERE / 'out/layout.json'
    if p.exists():
        lay = json.loads(p.read_text(encoding='utf-8'))
        return {int(k): dict(v['counts']) for k, v in lay.items()}, {int(k): [g[3] for g in v['gem_nodes']] for k, v in lay.items()}
    import layout6
    return ({L['n']: layout6.split_counts(L['veins'], L['ore_w']) for L in P.LEVELS},
            {L['n']: sum(([g] * k for g, k in layout6.split_counts(L['gem_nodes'], L['gem_w']).items()), []) for L in P.LEVELS})


N, NODES = counts()


def block_s(metal, pick):
    s = P.mine_seconds(RANK[metal], pick)
    return None if s is None else s + P.AIM_S + P.CLUSTER_S / P.CLUSTER_SIZE


def yield_per_block(pick):
    return (1 + P.PICK_BONUS[pick]) * RICH_F


def visit(L, pick, metals):
    """층 L 을 한 번 돌며 metals 중 캘 수 있는 것을 다 캔다 → (초, {금속: 블록}, {보석: 노드})."""
    secs = P.LOOP_S + P.LIFT_TRIP_S
    blocks = {}
    for m, k in N[L].items():
        if m not in metals:
            continue
        b = block_s(m, pick)
        if b is None:
            continue
        secs += k * b
        blocks[m] = k
    nodes = {}
    for g in NODES[L]:
        r = P.GEM[g]['rank']
        if P.can_mine(r, pick):
            nodes[g] = nodes.get(g, 0) + 1
    return secs, blocks, nodes


def visit_n(L, pick, metals, n=1):
    """visit 와 같되 n 명이 같은 층을 함께 돌 때 한 사람 몫 (블록 k/n — 한 바퀴에 캐는 블록 시간도 k/n)."""
    secs = P.LOOP_S + P.LIFT_TRIP_S
    blocks = {}
    for m, k in N[L].items():
        if m not in metals:
            continue
        b = block_s(m, pick)
        if b is None:
            continue
        secs += (k / n) * b
        blocks[m] = k / n
    nodes = {}
    for g in NODES[L]:
        if P.can_mine(P.GEM[g]['rank'], pick):
            nodes[g] = nodes.get(g, 0) + 1.0 / n
    return secs, blocks, nodes


def plan_rates(pick, metals, levels, n=1):
    """층 묶음 levels 를 돌 때 1분당 {금속: 광석}, {보석: 개}, 블록/분, 시간 몫 u (n = 같은 묶음을 함께 도는 사람 수, 한 사람 몫)."""
    u = 0.0
    ore, gem = {}, {}
    bpm = 0.0
    for L in levels:
        secs, blocks, nodes = visit_n(L, pick, metals, n)
        R = LEVELS[L]['regen']
        u += secs / (60.0 * R)
        # 노드는 30분마다 — 그 층을 도는 길에 캔다 (노드 시간도 더함)
        for g, k in nodes.items():
            node_s = P.mine_seconds(P.GEM[g]['rank'], pick, node=True) + 5.0
            u += k * node_s / (60.0 * P.GEM_NODE_REGEN)
            gem[g] = gem.get(g, 0.0) + k / P.GEM_NODE_REGEN
        for m, k in blocks.items():
            per = k / R
            bpm += per
            ore[m] = ore.get(m, 0.0) + per * yield_per_block(pick)
            g = P.GEM_BY_RANK[RANK[m]]['id']
            gem[g] = gem.get(g, 0.0) + per * P.GEM_CHANCE
    scale = 1.0 / max(1.0, u)
    return ({m: v * scale for m, v in ore.items()}, {g: v * scale for g, v in gem.items()}, bpm * scale, u)


def best_plan(pick, need, metals=None):
    """need = {금속 또는 보석: 개수}. 층 묶음 63개 중 걸리는 분이 가장 짧은 것 → (분, 묶음, 광석/분, 보석/분, 블록/분)."""
    metals = set(metals or [k for k in need if k in RANK])
    best = None
    for r in range(1, 7):
        for S in itertools.combinations(sorted(LEVELS), r):
            ore, gem, bpm, u = plan_rates(pick, metals, S)
            t = 0.0
            ok = True
            for k, v in need.items():
                if v <= 0:
                    continue
                rate = ore.get(k, gem.get(k, 0.0))
                if rate <= 1e-9:
                    ok = False
                    break
                t = max(t, v / rate)
            if not ok:
                continue
            if best is None or t < best[0] - 1e-9:
                best = (t, S, ore, gem, bpm)
    return best


def best_plan_fresh(pick, need, metals=None):
    """best_plan 과 같되 처음 들어간 사람 기준: 도는 층의 보석 노드가 다 차 있다 (그 층 노드 수만큼 바로 캠).
    걸리는 분 = max(그 층 묶음 한 바퀴, 남은 것 ÷ 1분당). → (분, 묶음)"""
    metals = set(metals or [k for k in need if k in RANK])
    best = None
    for r in range(1, 7):
        for S in itertools.combinations(sorted(LEVELS), r):
            ore, gem, bpm, u = plan_rates(pick, metals, S)
            stock = {}
            for L in S:
                for g in NODES[L]:
                    if P.can_mine(P.GEM[g]['rank'], pick):
                        stock[g] = stock.get(g, 0) + 1
            t = sum(visit(L, pick, metals)[0] for L in S) / 60.0
            ok = True
            for k, v in need.items():
                left = v - stock.get(k, 0)
                if left <= 0:
                    continue
                rate = ore.get(k, gem.get(k, 0.0))
                if rate <= 1e-9:
                    ok = False
                    break
                t = max(t, left / rate)
            if ok and (best is None or t < best[0] - 1e-9):
                best = (t, S)
    return best


def focused_rate(pick, metal):
    """그 금속만 노리고 여러 층을 돌 때 1분당 광석 (가장 좋은 묶음)."""
    b = best_plan(pick, {metal: 100.0}, [metal])
    return (100.0 / b[0], b[1]) if b else (0.0, ())


def single_level(L, pick):
    """한 층에 머물며 캘 수 있는 것을 다 캘 때: 1분당 {금속: 광석}, 블록/분, 한 바퀴 분."""
    secs, blocks, _ = visit(L, pick, set(RANK))
    cyc = max(LEVELS[L]['regen'], secs / 60.0)
    ore = {m: k * yield_per_block(pick) / cyc for m, k in blocks.items()}
    return ore, sum(blocks.values()) / cyc, secs / 60.0


TOUR_S = P.LIFT_TRIP_S + P.LOOP_S / 2.0     # 보석 노드만 걷으러 다른 층에 들르는 길 (승강기 + 반 바퀴)
LEVEL_SETS = [S for r in range(1, 7) for S in itertools.combinations(sorted(LEVELS), r)]


def plan_rates_tour(pick, metals, levels, tours=(), n=1):
    """plan_rates 와 같되 보석 노드를 먼저 챙긴다 (값이 커서 — 바쁜 사람도 노드는 걷음).
    levels = 광석을 캐는 층 (그 층 노드도 걷음) · tours = 노드만 걷으러 들르는 층 (노드 재생마다 한 번).
    시간 몫: 노드 u_n (먼저) + 광석 u_o. 합이 1 을 넘으면 광석만 (1 − u_n) / u_o 로 줄어든다."""
    yb = yield_per_block(pick)
    u_o, u_n = 0.0, 0.0
    ore, gem_o, gem_n = {}, {}, {}
    bpm = 0.0
    for L in levels:
        secs, blocks, _ = visit_n(L, pick, metals, n)
        R = LEVELS[L]['regen']
        u_o += secs / (60.0 * R)
        for m, k in blocks.items():
            per = k / R
            bpm += per
            ore[m] = ore.get(m, 0.0) + per * yb
            g = P.GEM_BY_RANK[RANK[m]]['id']
            gem_o[g] = gem_o.get(g, 0.0) + per * P.GEM_CHANCE
    for L in sorted(set(levels) | set(tours)):
        any_node = False
        for g in NODES[L]:
            s = P.mine_seconds(P.GEM[g]['rank'], pick, node=True)
            if s is None:
                continue
            any_node = True
            u_n += (s + 5.0) / (60.0 * P.GEM_NODE_REGEN * n)
            gem_n[g] = gem_n.get(g, 0.0) + 1.0 / (P.GEM_NODE_REGEN * n)
        if any_node and L not in levels:
            u_n += TOUR_S / (60.0 * P.GEM_NODE_REGEN)
    if u_n >= 1.0:
        sn, so = 1.0 / u_n, 0.0
    elif u_o + u_n <= 1.0:
        sn, so = 1.0, 1.0
    else:
        sn, so = 1.0, (1.0 - u_n) / u_o
    gem = {g: v * so for g, v in gem_o.items()}
    for g, v in gem_n.items():
        gem[g] = gem.get(g, 0.0) + v * sn
    return {m: v * so for m, v in ore.items()}, gem, bpm * so, u_o + u_n


def tour_sets(pick, levels):
    """노드만 걷으러 들를 층 후보 (광석 층 밖, 그 곡괭이로 캘 노드가 있는 층) 의 부분집합 모두."""
    cand = [L for L in sorted(LEVELS) if L not in levels and any(P.can_mine(P.GEM[g]['rank'], pick) for g in NODES[L])]
    return [c for r in range(0, len(cand) + 1) for c in itertools.combinations(cand, r)]


def metal_subsets(pick):
    """그 곡괭이로 캘 수 있는 금속의 빈 아닌 부분집합 모두 (값싼 광석 건너뛰기)."""
    reach = [m['key'] for m in P.METALS if P.can_mine(m['rank'], pick)]
    return [frozenset(c) for r in range(1, len(reach) + 1) for c in itertools.combinations(reach, r)]


def gold_value(ore, gem, price_ore, price_gem):
    return sum(v * price_ore[m] for m, v in ore.items()) + sum(v * price_gem[k] for k, v in gem.items())


_GOLD = {}


def gold_plan(pick, price_ore, price_gem, n=1, tour=False):
    """다 팔 때 1분당 골드가 가장 큰 계획 — 층 묶음 63 × 캘 금속 부분집합 (값싼 광석 건너뛰기, 가장 잘 아는 사람).
    price_ore = 광석 한 개를 파는 가장 좋은 값 (그대로 · 녹여서 (주괴 − 제련) / 2) · tour = 노드 먼저 (노드만 들르는 층 포함).
    → (G/분, 층 묶음, 블록/분, 광석/분, 보석/분, 금속, 노드만 들르는 층)"""
    key = (pick, n, tour, tuple(sorted(price_ore.items())), tuple(sorted(price_gem.items())))
    if key in _GOLD:
        return _GOLD[key]
    best = None
    for mets in metal_subsets(pick):
        for S in LEVEL_SETS:
            for tours in (tour_sets(pick, S) if tour else [()]):
                if tour:
                    ore, gem, bpm, u = plan_rates_tour(pick, mets, S, tours, n)
                else:
                    ore, gem, bpm, u = plan_rates(pick, mets, S, n)
                g = gold_value(ore, gem, price_ore, price_gem)
                if best is None or g > best[0] + 1e-9:
                    best = (g, S, bpm, ore, gem, sorted(mets, key=RANK.get), tours)
    _GOLD[key] = best
    return best


def _partitions(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for p in _partitions(rest):
        for i in range(len(p)):
            yield p[:i] + [[first] + p[i]] + p[i + 1:]
        yield [[first]] + p


def group_split(pick, price_ore, price_gem, players=4):
    """players 명 (같은 곡괭이) 이 층을 나눠 맡거나 함께 돌 때 한 사람 평균 G/분의 최대 → (값, [(층 묶음, 사람 수)]).
    G[k][S] = k 명이 층 묶음 S 를 함께 돌 때 한 사람 G/분 (금속 부분집합 중 최대)."""
    subs = metal_subsets(pick)
    G = {k: {S: max(gold_value(*plan_rates(pick, mets, S, k)[:2], price_ore, price_gem) for mets in subs) for S in LEVEL_SETS}
         for k in range(1, players + 1)}
    best = (0.0, None)
    for part in _partitions(sorted(LEVELS)):
        blocks = [tuple(sorted(b)) for b in part]

        def rec(i, left, acc, plan):
            nonlocal best
            if i == len(blocks):
                if left == 0 and acc / players > best[0] + 1e-9:
                    best = (acc / players, list(plan))
                return
            for k in range(0, left + 1):
                plan.append((blocks[i], k))
                rec(i + 1, left - k, acc + (k * G[k][blocks[i]] if k else 0.0), plan)
                plan.pop()
        rec(0, players, 0.0, [])
    return best


def macro_spot(reach_max, L, pick):
    """한 자리 매크로: 손 닿는 광맥 reach_max 개를 재생마다 → 블록/분."""
    return reach_max / LEVELS[L]['regen']


