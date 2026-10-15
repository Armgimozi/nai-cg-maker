import sys, multiprocessing as mp
import lk_core as K, lk_sim as LS
def job(a):
    absorb, dpm, fl, cls, prof, diff = a
    K.LOOKS["cloth"]["full"]["absorb"] = absorb
    K.LOOKS["cloth"]["full"]["damage_per_mp"] = dpm
    scn = LS.scenario(LS.gear_table(fl, "cloth"))
    return a, LS.solo(scn, cls, prof, diff, fl, 40, 1000 + fl)["clear"]
jobs = [(ab, dpm, fl, c, p, d) for ab, dpm in ((0.10, 2.0), (0.15, 2.0), (0.20, 1.5), (0.15, 1.5)) for fl in (6, 10) for c in ("arcanist", "shadow") for p, d in (("average", "normal"), ("skilled", "hard"))]
with mp.Pool(4) as pool:
    for a, r in pool.map(job, jobs):
        print(a, r)
