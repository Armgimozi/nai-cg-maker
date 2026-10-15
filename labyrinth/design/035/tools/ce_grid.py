import sys, io, contextlib
import ce_core as C, ce_model as M, ce_explore as E
def grid(P, opt=False, levels=(10,25,45)):
    C.USE_GEAR_REQUIRES = False
    with contextlib.redirect_stdout(io.StringIO()):
        rows = E.table(P, levels=levels, opt=opt)
    out = {}
    for L, cls, o, n, frac in rows:
        out[(cls, L)] = (n["dps"]/o["dps"]-1, n["ehp"]/o["ehp"]-1, frac, n, o)
    return out
def show(P, label="", opt=False):
    g = grid(P, opt)
    print(label, " ".join(f"{k}={v}" for k,v in P.items() if not callable(v) and k in ("k_phys","dex_crit","dex_speed","dex_evasion","cap_speed","keen_eye")))
    for cls in C.CLASSES:
        cells = []
        for L in (10,25,45):
            d,e,f,n,o = g[(cls,L)]
            cells.append(f"L{L}: dps {d:+4.0%} ehp {e:+4.0%}")
        print(f"  {cls:9} " + " | ".join(cells))
    return g
if __name__ == "__main__":
    P = dict(C.P_DEFAULT)
    for a in sys.argv[1:]:
        if a == "split":
            C.REQ_SPLIT = {"DEX": ("STR", 0.4)}; continue
        k, v = a.split("="); P[k] = float(v)
    show(P)
