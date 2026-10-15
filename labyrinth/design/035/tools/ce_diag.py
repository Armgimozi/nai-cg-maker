import random, sys, ce_sim as X, ce_simbase as S
def diag(cls, fl, prof="skilled", diff="normal", n=20, scn_kw=None):
    out = {}
    for m in ("old", "new"):
        scn = X.scenario(m, **(scn_kw or {}) if m == "new" else {})
        L = X.entry_level(fl)
        tot = tt = taken = 0
        random.seed(3)
        for i in range(n):
            r = X.RunX(cls, L, prof, diff, scn, fl, potions=0, extra_gear=X.gear_list(cls, fl))
            mobs = S.make_room_mobs(fl, scn, r.ctx_hp, r.ctx_dmg, 'combat', 1)
            f = S.Fight(r.pl, mobs, r.prof, r.diff, scn, fl, r.ctx_hp, r.ctx_dmg, 0, immortal=True); f.prof_id = prof
            f.run(max_t=600); tot += f.dealt; tt += f.t; taken += f.taken / r.pl.max_hp
        pl = r.pl
        out[m] = (tot / tt, taken / n, pl.max_hp)
    o, nw = out["old"], out["new"]
    print(f"{cls:9} F{fl:<2} room dps {o[0]:6.1f}->{nw[0]:6.1f} ({nw[0]/o[0]-1:+.0%})  taken/room {o[1]:.2f}->{nw[1]:.2f}  hp {o[2]:.0f}->{nw[2]:.0f}")
if __name__ == "__main__":
    for c in X.M.STATS and ["guardian","berserker","hunter","arcanist","priest","shadow"]:
        for fl in (5, 10):
            diag(c, fl)
