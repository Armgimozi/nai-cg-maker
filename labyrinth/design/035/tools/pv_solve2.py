import math, pv_sim as S, pv_tune as T
GG, GD = 1.15, 0.60
def solve(base, L):
    lo, hi = 0.0, 40000.0
    for _ in range(28):
        B = (lo + hi) / 2
        P = dict(base, buffer=dict(per_level=B / L), dmg=1.0)
        m = T.rot_metrics(P, L)
        if m['gg_dmg_med'] / m['gd_dmg_med'] > GG / GD: lo = B
        else: hi = B
    P = dict(base, buffer=dict(per_level=B / L), dmg=1.0)
    m = T.rot_metrics(P, L)
    return B, GG / m['gg_dmg_med'], m
if __name__ == '__main__':
    import sys
    cap = float(sys.argv[1]) if len(sys.argv) > 1 else 2.5
    sm = S.skill_mults(cap)
    for rc in (0.0, 0.4, 0.5, 0.6):
        for k in ((4, 8) if rc else (4,)):
            for cs in (0.6,):
                base = dict(S.PVP_NOCAP, def_weight=0.0, crit_scale=cs, ult=1.0, wskill=1.0, skill_mult=sm,
                            res=dict(cap=rc, k=k) if rc else None)
                row = []; Bs = []; ms = []
                for L in (20, 35, 50):
                    B, dmg, m = solve(base, L)
                    Bs.append(B); ms.append(dmg)
                    row.append(f"L{L} B {B:6.0f} ({B/L/L:4.2f}L²) dmg {dmg:4.2f} hit {m['hit_max'][0]*dmg*100:4.1f}/{m['hit_med_gg']*dmg*100:4.1f} dg {m['dg_med']*dmg*100:3.0f} dd {m['dd_med']*dmg*100:3.0f}")
                q = math.log(ms[0] / ms[2]) / math.log(50 / 20)
                print(f"rc {rc} k {k} cs {cs}: q≈{q:4.2f} :: " + " | ".join(row))
