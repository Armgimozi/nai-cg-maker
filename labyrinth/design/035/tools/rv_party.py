#!/usr/bin/env python3
"""review2 — 3인 파티를 '몹을 나눠 맡기' 대신 '같이 친다'로 다시 근사한다 (ce_sim.party_floor 는 각자 1/3 의 몹을
3인 배율(HP ×2.2, 피해 ×1.16) 그대로 혼자 상대해 파티가 솔로보다 어렵게 나온다).
  방·정예: 파티원마다 방 전체의 사본과 싸우되 몹 HP × (그 사람 초당 피해 몫), 받는 피해 × (맨 앞 0.6 · 나머지 0.4÷(n−1))
  보스: ce_sim 과 같음 (HP 몫, 맨 앞 1.0 · 나머지 0.6) · 사제 치유 몫도 같음. 한 명이라도 보스까지 잡으면 클리어."""
import os, sys, random, json, multiprocessing as mp, copy
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import ce_sim as X
import ce_simbase as S


def party(scn, comp, prof, diff, floor, runs, seed):
    random.seed(seed)
    members = X.PARTIES[comp]; n = len(members)
    cleared = 0; boss_t = []; room_t = []
    for _ in range(runs):
        mem = [X.RunX(c, X.entry_level(floor), prof, diff, scn, floor, potions=10 if floor > 1 else None,
                      extra_gear=X.gear_list(c, floor), n=n) for c in members]
        alive = [True] * n
        share = [1.0 / n] * n
        pi = members.index('priest') if 'priest' in members else -1
        ok_boss = False
        for i, kind in enumerate(mem[0].order()):
            live = [k for k in range(n) if alive[k]]
            if not live: break
            for k in range(n):
                mem[k].ally_regen = 0.0
                if pi >= 0 and alive[pi] and k != pi:
                    pr = mem[pi].pl
                    mem[k].ally_regen = 0.5 * (0.18 * mem[k].pl.max_hp + pr.heal_power) / 2.7 / (n - 1)
            if i > 0:
                for k in live:
                    mem[k].walk(30)
                    if i % 3 == 2 and not mem[k].traps():
                        alive[k] = False
            live = [k for k in range(n) if alive[k]]
            if not live: break
            tot = sum(share[k] for k in live) or 1.0
            if kind in ('C', 'E'):
                base = S.make_room_mobs(floor, scn, mem[live[0]].ctx_hp, mem[live[0]].ctx_dmg, 'combat' if kind == 'C' else 'elite', n)
                dps = {}
                ts = []
                for idx, k in enumerate(live):
                    mobs = copy.deepcopy(base)
                    f_hp = share[k] / tot
                    f_dmg = 0.6 if idx == 0 else (0.4 / max(1, len(live) - 1))
                    if len(live) == 1: f_dmg = 1.0
                    for m in mobs:
                        m.hp = m.max_hp = max(1, m.max_hp * f_hp)
                        m.dmg *= f_dmg
                    ok, rec = mem[k].fight(mobs)
                    ts.append(rec['t'])
                    dps[k] = rec['dealt'] / max(0.1, rec['t'])
                    if not ok: alive[k] = False
                if kind == 'C' and ts: room_t.append(max(ts))
                s = sum(dps.values()) or 1.0
                for k in dps: share[k] = 0.5 * share[k] + 0.5 * dps[k] / s
                for k in range(n):
                    if alive[k]:
                        p = mem[k].pl; p.hp = min(p.max_hp, p.hp + p.max_hp * scn['room_clear_heal'])
            elif kind == 'R':
                for k in live:
                    p = mem[k].pl; p.hp = min(p.max_hp, p.hp + p.max_hp * scn['rest_heal']); p.mp = min(p.max_mp, p.mp + p.max_mp * scn['rest_heal'])
            elif kind == 'G':
                for k in live: mem[k].gain_xp(S.avg_mob_xp(floor) * 10)
            elif kind == 'B':
                ts, oks = [], []
                for idx, k in enumerate(live):
                    ok, rec = mem[k].fight([], boss=True, boss_hp_share=share[k] / tot, boss_dmg_share=1.0 if idx == 0 else 0.6)
                    ts.append(rec['t']); oks.append(ok)
                ok_boss = any(oks)
                if ok_boss:
                    okt = [t for t, o in zip(ts, oks) if o]
                    boss_t.append(max(okt))
        cleared += ok_boss
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa
    return dict(clear=round(cleared / runs, 3), room_t=avg(room_t), boss_t=avg(boss_t))


def job(a):
    model, comp, prof, diff, fl = a
    return a, party(X.scenario(model), comp, prof, diff, fl, 30, 9000 + fl)


if __name__ == '__main__':
    jobs = [(m, c, p, d, fl) for m in ('old', 'new') for c in ('A', 'B') for d in ('normal', 'nightmare')
            for p in ('average', 'skilled') for fl in (1, 5, 10)]
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    out = {'|'.join(map(str, a)): r for a, r in res}
    json.dump(out, open(os.path.join(HERE, 'rv_party.json'), 'w'), ensure_ascii=False, indent=0)
    for d in ('normal', 'nightmare'):
        for p in ('average', 'skilled'):
            for c in ('A', 'B'):
                row = []
                for fl in (1, 5, 10):
                    o, nw = out[f'old|{c}|{p}|{d}|{fl}'], out[f'new|{c}|{p}|{d}|{fl}']
                    row.append(f"F{fl} {o['clear']:.0%}→{nw['clear']:.0%} 보스 {o['boss_t']}→{nw['boss_t']}s")
                print(f'{d:9s} {p:8s} 파티{c}: ' + ' | '.join(row))
