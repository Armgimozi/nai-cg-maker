import sys, json, multiprocessing as mp
import ce_run as R, ce_sim as X
CL = R.CLASSES
def work(t):
    name, c, p, d, fl, runs, seed = t
    return t, X.solo_floor(R.make(name), c, p, d, fl, runs, seed)
if __name__ == "__main__":
    names = sys.argv[1].split(";"); runs = int(sys.argv[2])
    floors = [int(x) for x in sys.argv[3].split(",")]; diffs = sys.argv[4].split(",")
    profs = sys.argv[5].split(",") if len(sys.argv) > 5 else ["average", "skilled"]
    T = []
    for nm in names:
        s = 500
        for d in diffs:
            for fl in floors:
                for p in profs:
                    for c in CL:
                        s += 1; T.append((nm, c, p, d, fl, runs, s))
    with mp.Pool(4) as pool:
        res = pool.map(work, T, chunksize=1)
    agg = {}
    for t, r in res:
        agg.setdefault((t[0], t[3], t[4], t[2]), []).append((t[1], r))
    for k, v in agg.items():
        cl = [r["clear"] for _, r in v]
        bt = [r["boss_t"] for _, r in v if r["boss_t"]]
        print(f"{k[0][:60]:60} {k[1]:9} F{k[2]:<2} {k[3]:7} avg {sum(cl)/len(cl):4.0%} | " + " ".join(f"{c[:4]}:{r['clear']:.0%}" for c, r in v) + f" | boss {sum(bt)/max(1,len(bt)):.0f}s", flush=True)
