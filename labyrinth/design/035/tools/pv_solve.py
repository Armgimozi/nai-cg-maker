import statistics as st, pv_sim as S, pv_tune as T
GG, GD = 1.20, 0.62
def mets(P, L):
    m = T.rot_metrics(P, L)
    return m['gg_dmg_med'], m['gd_dmg_med'], m
def solve_level(base, L):
    # B 를 바꾸며 비율 gg/gd = GG/GD 가 되게, 그 다음 dmg 로 gg 맞춤 (gg 는 dmg 에 정비례)
    lo, hi = 0.0, 60000.0
    for _ in range(30):
        B = (lo + hi) / 2
        P = dict(base, buffer=dict(per_level=B / L, per_level_sq=0.0), dmg=1.0)
        gg, gd, _ = mets(P, L)
        if gg / gd > GG / GD: lo = B
        else: hi = B
    P = dict(base, buffer=dict(per_level=B / L, per_level_sq=0.0), dmg=1.0)
    gg, gd, m = mets(P, L)
    dmg = GG / gg
    P['dmg'] = dmg
    gg, gd, m = mets(P, L)
    return B, dmg, gg, gd, m
if __name__ == '__main__':
    import sys
    for dw in (0.0, 0.25, 0.5):
      for cs in (0.5, 0.7, 1.0):
        for ult, ws in ((1.0,1.0),(0.6,0.6),(0.5,0.5),(0.4,0.5)):
            base = dict(S.PVP_NOCAP, def_weight=dw, crit_scale=cs, ult=ult, wskill=ws)
            out=[]
            for L in (20,35,50):
                B,dmg,gg,gd,m = solve_level(base,L)
                out.append(f"L{L} B {B:7.0f} dmg {dmg:5.2f} hitmax {m['hit_max'][0]*100:4.1f} hitmed {m['hit_med_gg']*100:4.1f} dg {m['dg_med']*100:3.0f} dd {m['dd_med']*100:3.0f}")
            print(f"dw {dw} cs {cs} ult {ult} ws {ws} :: " + " || ".join(out))
