import math, pv_final as F, pv_tune as T, pv_matrix as MX
GG = {20: 1.10, 35: 1.15, 50: 1.15}
def fit_curve(P):
    ms = {}
    for L in (20, 35, 50):
        Q = dict(P, dmg=1.0, level_curve=None)
        m = T.rot_metrics(Q, L)
        ms[L] = GG[L] / m['gg_dmg_med']
    q = math.log(ms[20] / ms[50]) / math.log(2.5)
    return ms, ms[20], q
def run(B20, p, n=20, show=True, **kw):
    coef = B20 / 20 ** p
    P = F.make(buffer=dict(coef=coef, exp=p), **kw)
    ms, m0, q = fit_curve(P)
    P['dmg'] = round(m0, 2); P['level_curve'] = dict(ref=20, exp=round(q, 2))
    if show:
        print(f"B20 {B20} p {p} → m0 {m0:.2f} q {q:.2f} (m35 {ms[35]:.2f} fit {m0*(20/35)**q:.2f})")
        MX.show(P, n=n)
    return P
if __name__ == '__main__':
    import sys
    base = dict(heal=0.6, potion=0.6, lifesteal=0.5, dampening=dict(start=20, per_s=0.02, floor=0.3))
    for B20, p in ((900, 0.6), (900, 0.45), (1000, 0.5)):
        run(B20, p, **base)
