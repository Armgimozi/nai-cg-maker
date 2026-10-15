import sys, json, copy, multiprocessing as mp
import ce_sim as X, ce_diag2 as D
def job(a):
    cls, fl, label, Pover, seed = a
    P = copy.deepcopy(X.P_FINAL); P.update(Pover)
    o = D.run(cls, fl, "old", n=100, seed=seed)
    n = D.run(cls, fl, "new", n=100, seed=seed, kw=dict(P=P))
    return a[:3], (n[0]/o[0]-1, n[1]/max(1e-9,o[1])-1)
if __name__ == "__main__":
    variants = json.loads(sys.argv[2])
    cls = sys.argv[1]
    fls = tuple(int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,5,10").split(","))
    T = [(cls, fl, lab, v, 21) for lab, v in variants.items() for fl in fls]
    with mp.Pool(4) as pool:
        for (c, fl, lab), (d, t) in pool.imap(job, T):
            print(f"{c} {lab:28} F{fl:<2} dps {d:+.0%} taken {t:+.0%}", flush=True)
