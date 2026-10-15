#!/usr/bin/env python3
"""review2 — '직업 × 무기 간격' 지배 검사. 설계자 시뮬레이터는 직업마다 옛 추천 종류 무기만 들렸다.
같은 단계(같은 레벨·희귀도·대장간 묶음) 무기를 직업마다 바꿔 들려 방 초당 피해 · 솔로 클리어 · 보스 시간을 잰다.
  5층(Lv20): L19 희귀 대장간 6종 · 10층(Lv45): L41 영웅 대장간 6종. 고유 효과는 넣지 않는다(설계자 시뮬과 같음)."""
import json, os, sys, random, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import ce_sim as X
import ce_simbase as S
import ce_model as M
import ce_core as C
SETS = {5: ['eelfin_sickle', 'brine_falchion', 'drowned_glaive', 'brine_bladebow', 'brine_bell_scepter', 'tide_fork_staff'],
        10: ['mainspring_dagger', 'clockguard_mace', 'regulator_greatsword', 'springloaded_bow', 'pendulum_censer', 'orrery_staff']}
CLASSES = ['guardian', 'berserker', 'hunter', 'arcanist', 'priest', 'shadow']
REQ = os.environ.get('RV_REQ', '034')     # 034 = 0.3.4 요구치(+DEX 나눔, 설계자 기준) · none = 무기 요구 없음 · c2 = gear_spec 2판 요구치
_orig_req = C.requires_of
_GS = json.load(open(os.path.join(os.path.dirname(HERE), 'gear_spec.json')))


def _req(wid):
    if wid in C.WEAPONS or wid in C.NEW_WEAPONS:
        if REQ == 'none':
            return {}
        if REQ == 'c2':
            src = _GS['existing_changes'].get(wid) or _GS['weapons'].get(wid) or {}
            return dict(src.get('requires') or {})
    return _orig_req(wid)


C.requires_of = _req
if REQ == 'c2':
    C.USE_GEAR_REQUIRES = True


def gl(cls, floor, wid):
    L = X.entry_level(floor)
    w, items = M.gear_for(cls, L, weapon_override=wid)
    return [w] + items


def room_dps(scn, cls, floor, wid, n=40, seed=11):
    tot = tt = taken = 0.0
    for i in range(n):
        r = X.RunX(cls, X.entry_level(floor), 'skilled', 'normal', scn, floor, potions=0, extra_gear=gl(cls, floor, wid))
        random.seed(seed * 100003 + i)
        mobs = S.make_room_mobs(floor, scn, r.ctx_hp, r.ctx_dmg, 'combat', 1)
        random.seed(seed * 7919 + i + 17)
        f = S.Fight(r.pl, mobs, r.prof, r.diff, scn, floor, r.ctx_hp, r.ctx_dmg, 0, immortal=True)
        f.prof_id = 'skilled'
        f.run(max_t=600)
        tot += f.dealt; tt += f.t; taken += f.taken / r.pl.max_hp
    return round(tot / tt, 1), round(taken / n, 3)


def solo(scn, cls, floor, wid, prof, runs=40, seed=3):
    random.seed(seed)
    cl, bt = 0, []
    for _ in range(runs):
        r = X.RunX(cls, X.entry_level(floor), prof, 'normal', scn, floor, potions=10, extra_gear=gl(cls, floor, wid))
        out = r.run_floor()
        if out['cleared']:
            cl += 1
            if r.times['boss']:
                bt.append(r.times['boss'])
    return round(cl / runs, 3), (round(sum(bt) / len(bt)) if bt else None)


def job(a):
    cls, floor, wid = a
    scn = X.scenario('new')
    d, tk = room_dps(scn, cls, floor, wid)
    ca, _ = solo(scn, cls, floor, wid, 'average')
    cs, bts = solo(scn, cls, floor, wid, 'skilled')
    return a, dict(room_dps=d, taken=tk, clear_avg=ca, clear_skilled=cs, boss_t_skilled=bts,
                   interval=C.interval_of(wid), style=C.style_of(C.weapon_shape(wid)), kind=M.weapon_kind(wid))


if __name__ == '__main__':
    jobs = []
    for fl, ws in SETS.items():
        for c in CLASSES:
            for w in ws:
                k = M.weapon_kind(w)
                if (c in ('arcanist', 'priest')) != (k == 'magic'):
                    continue
                jobs.append((c, fl, w))
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    out = {}
    for (c, fl, w), r in res:
        out.setdefault(f'{c}|{fl}', {})[w] = r
    json.dump(out, open(os.path.join(HERE, f'rv_interval_{REQ}.json'), 'w'), ensure_ascii=False, indent=1)
    for key, ws in out.items():
        best = max(v['room_dps'] for v in ws.values())
        print(key)
        for w, v in sorted(ws.items(), key=lambda kv: kv[1]['interval']):
            print(f"   {w:22s} {v['style']:6s} {v['interval']:.2f}s  방DPS {v['room_dps']:7.1f} ({v['room_dps']/best:4.0%})  받은피해 {v['taken']:.2f}"
                  f"  클리어 보통 {v['clear_avg']:.0%} 숙련 {v['clear_skilled']:.0%}  보스 {v['boss_t_skilled']}s")
