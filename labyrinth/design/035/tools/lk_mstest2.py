import multiprocessing as mp
import lk_core as K, lk_sim as LS
def job(a):
    absorb, seed, prof, diff = a
    K.LOOKS["cloth"]["full"]["absorb"] = absorb
    scn = LS.scenario(LS.gear_table(10, "native"))
    return a, LS.solo(scn, "arcanist", prof, diff, 10, 50, seed)["clear"]
jobs = [(ab, sd, p, d) for ab in (0.0, 0.10, 0.20) for sd in (11, 22) for p, d in (("average", "normal"), ("skilled", "hard"))]
with mp.Pool(4) as pool:
    res = pool.map(job, jobs)
agg = {}
for (ab, sd, p, d), r in res:
    agg.setdefault((ab, p, d), []).append(r)
for k, v in sorted(agg.items()):
    print(k, round(sum(v) / len(v), 3), v)
