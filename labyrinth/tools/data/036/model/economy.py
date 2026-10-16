#!/usr/bin/env python3
"""0.3.6 경제 다시 재기 (6층 섞인 광산) — design036/tools/mat_balance.py + rv_balance.py 를 고친 것.

  python3 -B economy.py            # proto036.py 를 먼저 돌린다 (run_all.py 가 순서대로)

재는 것:
  A. 곡괭이 × 층: 한 층에 머물며 캘 수 있는 것을 다 캘 때 1분당 광석 (금속별)
  B. 금속 하나만 노리고 여러 층을 돌 때 1분당 광석 (곡괭이별)
  C. 단계별 대표 한 벌(무기 1 + 방어구 4부위) 제작 총시간 (솔로 / 4인, 던전 분 + 광산 분) — 0.3.5 와 비교, +5 까지도
  D. 곡괭이 준비 (0.3.6.1: 앞 곡괭이로 제 금속·같은 등급 보석을 한 단계 위라 느리게 캐는 분)
  E. 골드: 광산 다 팔기 G/분 ÷ 던전 G/분 (그 단계 곡괭이, ≤ 0.20) + 친구가 준 가장 좋은 곡괭이로 낮은 단계에서
  F. (기력 없음 — 계약 §0-1)
  G. 한 단계 위 광석 (0.3.6.1): 앞 곡괭이로 캐는 초 · 제 곡괭이와 1분당 광석 견줌
결과: out/economy.json · out/economy.md (CONTRACT.md 표)
"""
import collections
import json
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import params as P  # noqa: E402
import mine6 as M  # noqa: E402
import proto036 as PR  # noqa: E402

GE = PR.GE
OLD = PR.CONTENT
NEW = HERE / 'out/proto/content'
RANK = M.RANK
ESS_KO = {'dim_essence': '희미한 미궁 정수', 'labyrinth_essence': '미궁 정수', 'radiant_essence': '찬란한 미궁 정수', 'primordial_essence': '태고의 미궁 정수'}


def load_old_new():
    import yaml
    old = GE.load_content(OLD)
    old['floors'] = {int(k): v for k, v in old['floors'].items()}
    new = GE.load_content(NEW)
    new['floors'] = {int(k): v for k, v in new['floors'].items()}
    old_enh = (GE.load_yaml(OLD / 'enhance.yml').get('items') or {})
    new_enh = (GE.load_yaml(HERE / 'out/proto/enhance.yml').get('items') or {})
    return old, new, old_enh, new_enh


def dungeon_gold(c):
    out = {}
    for f, fd in c['floors'].items():
        roots = GE.floor_roots(f, fd, c['tables'], c['mobs'], c['bosses'])
        g = 0.0
        normal = [m for m in (fd.get('mobs') or []) if m in c['mobs']]
        if normal:
            g += GE.MOBS_RUN.get(f, 40) * statistics.mean(sum(c['mobs'][m].get('gold') or [0, 0]) / 2 for m in normal)
        if fd.get('elite') in c['mobs']:
            g += (fd.get('rooms') or {}).get('elite', 1) * sum(c['mobs'][fd['elite']].get('gold') or [0, 0]) / 2
        if fd.get('boss') in c['bosses']:
            g += sum(c['bosses'][fd['boss']].get('gold') or [0, 0]) / 2
        for tid, n, _ in roots:
            t = c['tables'].get(tid) or {}
            if t.get('gold'):
                g += n * sum(t['gold']) / 2
        out[f] = g
    return out


def material_sale(c, sup):
    """1회 던전에서 줍는 재료를 다 팔 때 골드 (SellPrices 기본표: 희귀도 × (1 + 0.15 × (층 − 1)), 장비 드롭은 빼서 보수적)."""
    table = {'common': 2, 'uncommon': 5, 'rare': 15, 'epic': 40, 'legendary': 120, 'mythic': 300}
    out = {}
    for f, s in sup.items():
        g = 0.0
        for i, n in s.items():
            v = c['items'].get(i) or {}
            if v.get('type') != 'material' or i in PR.ORES or i in PR.INGOTS or i in PR.GEM_IDS:
                continue
            g += n * round(table.get(v.get('rarity', 'common'), 2) * (1 + 0.15 * max(0, int(v.get('floor') or 1) - 1)))
        out[f] = g
    return out


def kit_metals(ing):
    return {PR.INGOTS[m]['key']: n for m, n in ing.items()}


def block(c, enh, cfg, sup, refine, t, party, goal, old=False):
    kit, need = PR.kit_need(c, enh, cfg, t, goal)
    dun, ing, gem = PR.split_need(need)
    runs, which, runs_stone = PR.dungeon_runs(dun, sup[t], refine)
    rt = P.RUN_MINUTES[t] * (P.PARTY_TIME if party else 1.0)
    res = {'kit': kit, 'runs': round(runs, 2), 'bottleneck': which, 'runs_stone': round(runs_stone, 2), 'dungeon_min': round(runs * rt, 1)}
    if old:
        res['total_min'] = res['dungeon_min']
        return res
    metals = kit_metals(ing)
    ore_need = {}
    from_dungeon = {}
    for k, n in metals.items():
        got = sup[t].get(P.METAL[k]['ore'], 0) * runs
        from_dungeon[k] = round(got, 1)
        ore_need[k] = max(0.0, n * P.ORE_PER_INGOT - got)
    pick = max(RANK[k] for k in metals) if metals else 1
    need = {k: v for k, v in ore_need.items() if v > 0}
    for g, n in gem.items():
        need[g] = n
    if need:
        plan = M.best_plan(pick, need)
        mine_min, levels, bpm = plan[0], plan[1], plan[4]
    else:
        mine_min, levels, bpm = 0.0, (), 0.0
    res.update({'ingots': metals, 'ore_from_dungeon': from_dungeon, 'ore_to_mine': {k: round(v, 1) for k, v in ore_need.items()},
                'pickaxe': P.BY_RANK[pick]['pickaxe'], 'mine_levels': list(levels), 'mine_min': round(mine_min, 1),
                'mine_bpm': round(bpm, 2), 'total_min': round(runs * rt + mine_min, 1),
                'share_mine': round(mine_min / max(1e-9, mine_min + runs * rt), 3)})
    return res


def pickaxe_prep():
    """곡괭이마다 (0.3.6.1): 앞 곡괭이로 제 금속 주괴·같은 등급 보석을 캐는 분 (한 단계 위라 느림).
    minutes = 계약 모델 (보석 노드도 1분당 몫으로만), fresh = 처음 들어간 사람 (도는 층 노드가 다 차 있음)."""
    out = {}
    for pid, d in P.PICK_RECIPES.items():
        m = P.METAL[pid.replace('_pickaxe', '')]
        prev = m['rank'] - 1
        ing_id, k = d['ingot']
        gid, g = d['gem']
        need = {m['key']: k * P.ORE_PER_INGOT, gid: g}
        plan = M.best_plan(prev, need)
        fresh = M.best_plan_fresh(prev, need)
        out[pid] = {'with': P.BY_RANK[prev]['pickaxe'], 'ingot': ing_id, 'ingots': k, 'gem': gid, 'gems': g,
                    'essence': {d['essence'][0]: d['essence'][1]},
                    'minutes': round(plan[0], 1), 'levels': list(plan[1]), 'fresh_minutes': round(fresh[0], 1), 'fresh_levels': list(fresh[1]),
                    'gold': d['gold'] + k * m['smelt_gold']}
    return out


def stretch_table():
    """표 G (0.3.6.1): 한 단계 위 광석 — 앞 곡괭이(느림) 와 제 곡괭이의 초 · 그 금속만 노려 여러 층을 돌 때 1분당 광석."""
    out = {}
    for m in P.METALS[1:]:
        r = m['rank']
        a, sa = M.focused_rate(r - 1, m['key'])
        b, sb = M.focused_rate(r, m['key'])
        out[m['key']] = {'slow_pickaxe': P.BY_RANK[r - 1]['pickaxe'], 'slow_seconds': round(P.mine_seconds(r, r - 1), 2),
                         'own_seconds': round(P.mine_seconds(r, r), 2), 'slow_per_min': round(a, 2), 'own_per_min': round(b, 2),
                         'gain': round(b / a, 3) if a else None}
    return out


def main():
    old, new, old_enh, new_enh = load_old_new()
    cfg = GE.enhance_config()
    sup_old, sup_new = PR.supplies(old), PR.supplies(new)
    sup_old4, sup_new4 = PR.supplies(old, True), PR.supplies(new, True)
    ref_old, ref_new = GE.refined_from(old['recipes']), GE.refined_from(new['recipes'])
    gold_new = dungeon_gold(new)
    sale_new = material_sale(new, sup_new)
    price_ore = {m['key']: P.sell_value('ore', m['rank']) for m in P.METALS}
    price_gem = {g['id']: P.sell_value('gem', g['rank']) for g in P.GEMS}

    # A. 곡괭이 × 층 (한 층에 머묾)
    table_a = {}
    for p in range(1, 7):
        for L in range(1, 7):
            ore, bpm, cyc = M.single_level(L, p)
            table_a[f'{p}:{L}'] = {'ore_per_min': round(sum(ore.values()), 2), 'by_metal': {k: round(v, 2) for k, v in ore.items()},
                                   'blocks_per_min': round(bpm, 2), 'loop_min': round(cyc, 1)}
    # B. 금속만 노리고 여러 층
    table_b = {}
    for p in range(1, 7):
        for m in P.METALS:
            if not P.can_mine(m['rank'], p):
                continue
            r, S = M.focused_rate(p, m['key'])
            table_b[f"{p}:{m['key']}"] = {'ore_per_min': round(r, 2), 'levels': list(S)}
    gem_b = {}
    for p in range(1, 7):
        for g in P.GEMS:
            if not P.can_mine(g['rank'], p):
                continue
            b = M.best_plan(p, {g['id']: 10.0}, [P.BY_RANK[g['rank']]['key']])
            gem_b[f"{p}:{g['id']}"] = round(10.0 / b[0], 3) if b else 0.0

    # C. 대표 한 벌
    rows = []
    for t in range(1, 11):
        row = {'tier': t}
        for tag, goal in (('craft', None), ('plus5', 5)):
            o1 = block(old, old_enh, cfg, sup_old, ref_old, t, False, goal, old=True)
            o4 = block(old, old_enh, cfg, sup_old4, ref_old, t, True, goal, old=True)
            n1 = block(new, new_enh, cfg, sup_new, ref_new, t, False, goal)
            n4 = block(new, new_enh, cfg, sup_new4, ref_new, t, True, goal)
            row[tag] = {'old_solo': o1, 'old_4p': o4, 'new_solo': n1, 'new_4p': n4,
                        'delta_solo': round(n1['total_min'] / max(1e-9, o1['total_min']) - 1, 3),
                        'delta_4p': round(n4['total_min'] / max(1e-9, o4['total_min']) - 1, 3)}
        # E. 골드
        pick = RANK[P.METAL[row['craft']['new_solo']['pickaxe'].replace('_pickaxe', '')]['key']]
        gp = M.gold_plan(pick, price_ore, price_gem)
        top = M.gold_plan(6, price_ore, price_gem)
        dpm = gold_new[t] / P.RUN_MINUTES[t]
        dpm_sale = (gold_new[t] + sale_new[t]) / P.RUN_MINUTES[t]
        row['gold'] = {'dungeon_per_run': round(gold_new[t]), 'dungeon_per_min': round(dpm, 1), 'band_pickaxe': P.BY_RANK[pick]['pickaxe'],
                       'dungeon_with_sale_per_min': round(dpm_sale, 1), 'ratio_with_sale': round(gp[0] / dpm_sale, 3),
                       'mine_per_min': round(gp[0], 1), 'mine_levels': list(gp[1]), 'ratio': round(gp[0] / dpm, 3),
                       'gift_top_pickaxe_per_min': round(top[0], 1), 'gift_ratio': round(top[0] / dpm, 3)}
        rows.append(row)

    prep = pickaxe_prep()

    res = {'table_a_single_level': table_a, 'table_b_focused': table_b, 'gem_focused': gem_b, 'rows': rows,
           'pickaxe_prep': prep, 'stretch': {'factor': P.STRETCH_FACTOR, 'reach_above': P.REACH_ABOVE, 'by_metal': stretch_table()},
           'assumptions': {'run_minutes': P.RUN_MINUTES, 'party_time': P.PARTY_TIME, 'party_bonus': P.PARTY_BONUS,
                           'aim_s': P.AIM_S, 'cluster_s': P.CLUSTER_S, 'loop_s': P.LOOP_S, 'lift_trip_s': P.LIFT_TRIP_S,
                           'ing_share': P.ING_SHARE}}
    (HERE / 'out/economy.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    md = render_md(res)
    (HERE / 'out/economy.md').write_text(md, encoding='utf-8')
    print(md)


def pct(x):
    return f"{x * 100:+.0f}%"


def render_md(res):
    L = []
    names = {m['key']: m['ko'] for m in P.METALS}
    picks = {m['rank']: m['ko'] for m in P.METALS}
    L.append('### 표 A. 곡괭이 × 층 — 한 층에 머물며 캘 수 있는 것을 다 캘 때 1분당 광석 (괄호: 많이 나오는 금속)')
    L.append('')
    L.append('| 곡괭이 \\ 층 | ' + ' | '.join(f"{lv['name']}" for lv in P.LEVELS) + ' |')
    L.append('|---|' + '---|' * len(P.LEVELS))
    for p in range(1, 7):
        cells = []
        for lv in P.LEVELS:
            a = res['table_a_single_level'][f"{p}:{lv['n']}"]
            top = sorted(a['by_metal'].items(), key=lambda kv: -kv[1])[:2]
            cells.append(f"{a['ore_per_min']:.1f} ({'·'.join(names[k] for k, _ in top)})" if a['ore_per_min'] else '0')
        L.append(f"| {picks[p]} | " + ' | '.join(cells) + ' |')
    L.append('')
    L.append('### 표 B. 금속 하나만 노리고 여러 층을 돌 때 1분당 광석 (괄호: 도는 층)')
    L.append('')
    L.append('| 곡괭이 | ' + ' | '.join(names[k] for k in P.OWNER['metal_order']) + ' |')
    L.append('|---|' + '---|' * 6)
    for p in range(1, 7):
        cells = []
        for k in P.OWNER['metal_order']:
            b = res['table_b_focused'].get(f'{p}:{k}')
            cells.append(f"{b['ore_per_min']:.1f} ({''.join(map(str, b['levels']))})" if b else '—')
        L.append(f"| {picks[p]} | " + ' | '.join(cells) + ' |')
    L.append('')
    L.append('### 표 C. 대표 한 벌 제작 총시간 (던전 분 + 광산 분) — 0.3.5 와 비교')
    L.append('')
    L.append('| 단계 | 0.3.5 솔로 | 0.3.6 솔로 = 던전 + 광산 | 변화 | 0.3.5 4인 | 0.3.6 4인 | 변화 | 쓰는 금속 (주괴) | 곡괭이 |')
    L.append('|---|---|---|---|---|---|---|---|---|')
    for r in res['rows']:
        c = r['craft']
        o1, n1, o4, n4 = c['old_solo'], c['new_solo'], c['old_4p'], c['new_4p']
        ings = ' · '.join(f"{names[k]} {v}" for k, v in sorted(n1['ingots'].items(), key=lambda kv: RANK[kv[0]]))
        L.append(f"| {r['tier']} | {o1['total_min']:.0f}분 | {n1['dungeon_min']:.0f} + {n1['mine_min']:.0f} = {n1['total_min']:.0f}분 | {pct(c['delta_solo'])} | "
                 f"{o4['total_min']:.0f}분 | {n4['dungeon_min']:.0f} + {n4['mine_min']:.0f} = {n4['total_min']:.0f}분 | {pct(c['delta_4p'])} | {ings} | {picks[RANK[n1['pickaxe'].replace('_pickaxe', '')]]} |")
    L.append('')
    L.append('+5 까지 (제작 + 강화, 솔로):')
    L.append('')
    L.append('| 단계 | 0.3.5 | 0.3.6 = 던전 + 광산 | 변화 |')
    L.append('|---|---|---|---|')
    for r in res['rows']:
        c = r['plus5']
        L.append(f"| {r['tier']} | {c['old_solo']['total_min']:.0f}분 | {c['new_solo']['dungeon_min']:.0f} + {c['new_solo']['mine_min']:.0f} = "
                 f"{c['new_solo']['total_min']:.0f}분 | {pct(c['delta_solo'])} |")
    L.append('')
    L.append('### 표 D. 곡괭이 준비 (0.3.6.1 — 앞 곡괭이로 제 금속 주괴·같은 등급 보석을 한 단계 위라 느리게 캐는 분, 한 번)')
    L.append('')
    L.append('| 곡괭이 | 재료 | 광산 분 (모델) | 처음 온 사람 (노드 다 참) | 골드 (제련 포함) |')
    L.append('|---|---|---|---|---|')
    for pid, d in res['pickaxe_prep'].items():
        m = P.METAL[pid.replace('_pickaxe', '')]
        prev = P.BY_RANK[m['rank'] - 1]
        L.append(f"| {m['pick_name']} | {prev['pick_name']} · {m['ingot_name']} {d['ingots']} · {P.GEM[d['gem']]['ko']} {d['gems']} · "
                 f"{'·'.join(f'{ESS_KO.get(k, k)} {v}' for k, v in d['essence'].items())} | {d['minutes']:.0f}분 | {d['fresh_minutes']:.0f}분 | {d['gold']:,}G |")
    L.append('')
    st = res['stretch']
    L.append(f"### 표 G. 한 단계 위 광석 (곡괭이 tier t 는 tier ≤ t + {st['reach_above']} 을 캠, 한 단계 위는 제 곡괭이 빠르기 × {st['factor']})")
    L.append('')
    L.append('| 광석 | 앞 곡괭이로 (초) | 제 곡괭이로 (초) | 그 금속만 노릴 때 1분당 (앞 → 제 곡괭이) |')
    L.append('|---|---|---|---|')
    for k, d in st['by_metal'].items():
        L.append(f"| {P.METAL[k]['ore_name']} | {P.METAL[P.BY_RANK[P.METAL[k]['rank'] - 1]['key']]['pick_name']} {d['slow_seconds']:.2f} | "
                 f"{d['own_seconds']:.2f} | {d['slow_per_min']:.1f} → {d['own_per_min']:.1f} (×{d['gain']:.2f}) |")
    L.append('')
    L.append('### 표 E. 골드 — 광산에서 캔 것을 다 팔 때 G/분 ÷ 던전 G/분')
    L.append('')
    L.append('| 단계 | 던전 G/분 (드롭 골드만) | + 재료 판매 | 그 단계 곡괭이 | 광산 G/분 | 비율 (드롭만 / 판매 포함) | 가장 좋은 곡괭이를 받았을 때 | 비율 (드롭만) |')
    L.append('|---|---|---|---|---|---|---|---|')
    for r in res['rows']:
        g = r['gold']
        L.append(f"| {r['tier']} | {g['dungeon_per_min']} | {g['dungeon_with_sale_per_min']} | {picks[RANK[g['band_pickaxe'].replace('_pickaxe', '')]]} | {g['mine_per_min']} | "
                 f"{g['ratio'] * 100:.0f}% / {g['ratio_with_sale'] * 100:.0f}% | {g['gift_top_pickaxe_per_min']} | {g['gift_ratio'] * 100:.0f}% |")
    L.append('')
    L.append('기력은 없다 (계약 §0-1) — 표 F 는 쓰지 않는다.')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    main()
