import random, sys, ce_sim as X, ce_simbase as S
def run(cls, fl, m, n=40, seed=5, prof="skilled", kw=None):
    scn = X.scenario(m, **(kw or {}))
    tot = tt = taken = 0
    for i in range(n):
        r = X.RunX(cls, X.entry_level(fl), prof, "normal", scn, fl, potions=0, extra_gear=X.gear_list(cls, fl))
        random.seed(seed * 100003 + i)          # 방 구성은 두 판이 똑같게
        mobs = S.make_room_mobs(fl, scn, r.ctx_hp, r.ctx_dmg, 'combat', 1)
        random.seed(seed * 7919 + i + 17)       # 전투 난수도 같은 출발점
        f = S.Fight(r.pl, mobs, r.prof, r.diff, scn, fl, r.ctx_hp, r.ctx_dmg, 0, immortal=True); f.prof_id = prof
        f.run(max_t=600); tot += f.dealt; tt += f.t; taken += f.taken / r.pl.max_hp
    return tot / tt, taken / n
if __name__ == "__main__":
    for c in ["guardian","berserker","hunter","arcanist","priest","shadow"]:
        for fl in (1, 5, 10):
            o = run(c, fl, "old"); nw = run(c, fl, "new")
            print(f"{c:9} F{fl:<2} dps {o[0]:7.1f}->{nw[0]:7.1f} ({nw[0]/o[0]-1:+.0%})  taken/room {o[1]:.2f}->{nw[1]:.2f} ({nw[1]/max(1e-9,o[1])-1:+.0%})", flush=True)
