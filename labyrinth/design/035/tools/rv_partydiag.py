#!/usr/bin/env python3
"""review2 — 3인 파티 B(광전사·비전술사·그림자)가 보통 1층에서도 거의 못 깨는 까닭 찾기."""
import os, sys, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import ce_sim as X
import ce_simbase as S


def diag(comp, prof, diff, floor, runs=20, seed=77, model='new'):
    scn = X.scenario(model)
    random.seed(seed)
    members = X.PARTIES[comp]; n = len(members)
    where = collections.Counter(); boss_res = collections.Counter()
    for _ in range(runs):
        mem = [X.RunX(c, X.entry_level(floor), prof, diff, scn, floor, potions=10 if floor > 1 else None,
                      extra_gear=X.gear_list(c, floor), n=n) for c in members]
        alive = [True] * n
        order = mem[0].order()
        dps_acc = [[0.0, 0.0] for _ in range(n)]
        for i, kind in enumerate(order):
            live = [k for k in range(n) if alive[k]]
            if not live: break
            if i > 0:
                for k in live:
                    mem[k].walk(30)
                    if i % 3 == 2 and not mem[k].traps():
                        alive[k] = False; where[(members[k], 'trap')] += 1
            live = [k for k in range(n) if alive[k]]
            if not live: break
            r0 = mem[live[0]]
            if kind in ('C', 'E'):
                mobs = S.make_room_mobs(floor, scn, r0.ctx_hp, r0.ctx_dmg, 'combat' if kind == 'C' else 'elite', n)
                share = {k: [] for k in live}
                if kind == 'E':
                    lead = mobs[0]; lead.hp = lead.max_hp = max(1, round(lead.max_hp / len(live)))
                    share[live[0]].append(lead); rest = mobs[1:]
                else:
                    random.shuffle(mobs); rest = mobs
                for j, m in enumerate(rest):
                    share[live[j % len(live)]].append(m)
                for k in live:
                    if share[k]:
                        ok, rec = mem[k].fight(share[k])
                        dps_acc[k][0] += rec['dealt']; dps_acc[k][1] += rec['t']
                        if not ok:
                            alive[k] = False; where[(members[k], kind)] += 1
                for k in range(n):
                    if alive[k]:
                        p = mem[k].pl; p.hp = min(p.max_hp, p.hp + p.max_hp * scn['room_clear_heal'])
            elif kind == 'B':
                dps = {k: (dps_acc[k][0] / dps_acc[k][1]) if dps_acc[k][1] > 0 else 1.0 for k in live}
                tot = sum(dps.values()) or 1.0
                for idx, k in enumerate(live):
                    ok, rec = mem[k].fight([], boss=True, boss_hp_share=dps[k] / tot, boss_dmg_share=1.0 if idx == 0 else 0.6)
                    boss_res[(members[k], 'ok' if ok else 'dead', round(dps[k] / tot, 2))] += 1
    return where, boss_res


if __name__ == '__main__':
    for comp in ('B', 'A'):
        w, b = diag(comp, 'average', 'normal', 1)
        print(comp, 'deaths', dict(w))
        print(comp, 'boss', sorted(b.items())[:12])
    # 솔로 같은 조건
    scn = X.scenario('new')
    for c in ('berserker', 'arcanist', 'shadow'):
        print('solo', c, X.solo_floor(scn, c, 'average', 'normal', 1, 20, 77))
