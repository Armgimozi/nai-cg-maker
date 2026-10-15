import random, ce_sim as X, ce_simbase as S
orig = X.FightX.hit_mob
def share(cls, fl, m, n=60, seed=7, kw=None):
    scn = X.scenario(m, **(kw or {}))
    st = {"b": 0.0, "s": 0.0, "t": 0.0, "all": 0.0}
    def hm(self, mob, mult, skill=False, guaranteed_crit=False, crit_bonus=0.0):
        h0 = mob.hp
        orig(self, mob, mult, skill, guaranteed_crit, crit_bonus)
        st["s" if skill else "b"] += h0 - mob.hp
    X.FightX.hit_mob = hm
    random.seed(seed)
    for i in range(n):
        r = X.RunX(cls, X.entry_level(fl), "skilled", "normal", scn, fl, potions=0, extra_gear=X.gear_list(cls, fl))
        mobs = S.make_room_mobs(fl, scn, r.ctx_hp, r.ctx_dmg, 'combat', 1)
        f = S.Fight(r.pl, mobs, r.prof, r.diff, scn, fl, r.ctx_hp, r.ctx_dmg, 0, immortal=True); f.prof_id = "skilled"
        f.run(max_t=600); st["t"] += f.t; st["all"] += f.dealt
    X.FightX.hit_mob = orig
    return st
if __name__ == "__main__":
    for c in ("hunter", "shadow", "berserker", "arcanist"):
        for fl in (1, 5, 10):
            o = share(c, fl, "old")
            print(f"{c:9} F{fl:<2} old: basic {o['b']/o['t']:.0f}/s skill {o['s']/o['t']:.0f}/s other {(o['all']-o['b']-o['s'])/o['t']:.0f}/s  skill share {o['s']/o['all']:.0%}", flush=True)
