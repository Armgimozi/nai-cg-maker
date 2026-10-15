import itertools
import ce_core as C, ce_model as M
C.USE_GEAR_REQUIRES = False
def evalc(cls, P, target, levels=(10,25,45)):
    M.TARGET_NEW[cls] = target
    out = []
    for L in levels:
        o = M.old_player(cls, L); n = M.new_player(cls, L, P, "sensible", o["weapon"])
        out.append((n["dps"]/o["dps"]-1, n["ehp"]/o["ehp"]-1))
    return out
base = dict(C.P_DEFAULT); base.update(k_phys=0.01, k_mag=0.01, dex_crit=0.0025, dex_speed=0.005, keen_eye=1.3, shadow_crit_dmg=0.35, shadow_speed=0.1, priest_magic=0.10)
for ev in (0.001,):
    P = dict(base); P["dex_evasion"] = ev
    for cls, dmg in (("hunter","STR"),("shadow","STR"),("priest","INT")):
        best = None
        for s in [x/10 for x in range(4, 21)]:
            v = 3.0 - s if cls != "priest" else 2.5 - s
            if v <= 0: continue
            tgt = {"DEX": 2.0, "STR": s, "VIT": v} if cls != "priest" else {"WIS": 2.5, "INT": s, "VIT": v}
            r = evalc(cls, P, tgt)
            score = max(max(abs(a), abs(b)) for a, b in r)
            if best is None or score < best[0]: best = (score, s, v, r)
        print(f"ev {ev} {cls}: best {dmg} {best[1]} VIT {best[2]:.1f} worst {best[0]:+.0%} ", " ".join(f"({a:+.0%},{b:+.0%})" for a,b in best[3]))
