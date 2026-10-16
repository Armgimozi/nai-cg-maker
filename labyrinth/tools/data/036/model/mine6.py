"""광산 6층 수확 모델 (순수 함수) — design036/tools/mine_model.py 를 섞인 층·등급 규칙·여러 층 돌기로 고친 것.

블록 하나에 드는 시간 = 캐는 초(광석 등급, 곡괭이) + 조준 AIM_S + 무더기 사이 걷기 CLUSTER_S / CLUSTER_SIZE.
한 층을 한 번 도는 시간 = LOOP_S + LIFT_TRIP_S + 그 층에서 캐기로 한 블록들의 시간.
광맥은 사람마다 따로 재생 R 분 → 층 L 의 광석 o 공급 = n(L,o) / R(L) 블록/분.
여러 층 돌기: 층 묶음 S 를 고르면 1분에 쓰는 시간 몫 u = Σ (한 번 도는 초) / (60·R). u > 1 이면 다 못 따라가서 공급이 1/u 로 준다.
수확 = 블록 × (1 + 곡괭이 덤) × 풍부 (1 + 0.04×2). 보석 = 같은 등급 광석 블록 × 2.2% + 보석 노드 (30분, 등급 ≤ 곡괭이 + 1).
0.3.6.1: 곡괭이는 한 단계 위 광석·보석도 캔다 (params.can_mine · 느림 STRETCH_FACTOR).
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


def plan_rates(pick, metals, levels):
    """층 묶음 levels 를 돌 때 1분당 {금속: 광석}, {보석: 개}, 블록/분, 시간 몫 u."""
    u = 0.0
    ore, gem = {}, {}
    bpm = 0.0
    for L in levels:
        secs, blocks, nodes = visit(L, pick, metals)
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


def gold_plan(pick, price_ore, price_gem):
    """다 팔 때 1분당 골드가 가장 큰 층 묶음 (캘 수 있는 것은 모두 캠)."""
    best = None
    for r in range(1, 7):
        for S in itertools.combinations(sorted(LEVELS), r):
            ore, gem, bpm, u = plan_rates(pick, set(RANK), S)
            g = sum(v * price_ore[m] for m, v in ore.items()) + sum(v * price_gem[k] for k, v in gem.items())
            if best is None or g > best[0]:
                best = (g, S, bpm, ore, gem)
    return best


def macro_spot(reach_max, L, pick):
    """한 자리 매크로: 손 닿는 광맥 reach_max 개를 재생마다 → 블록/분."""
    return reach_max / LEVELS[L]['regen']


