#!/usr/bin/env python3
"""TASK P — 모든 표를 계산해 pv_results.json 에 둔다 (pv_spec.py 가 읽어 md/json 을 쓴다).

  python3 pv_run.py            # 최종안 n=40, 비교안 n=24 (몇 분)
"""
import json
import os
import statistics as st
import sys
import time

import pv_build as B
import pv_cc as CC
import pv_core as V
import pv_final as F
import pv_matrix as MX
import pv_sim as S
import pv_tune as T

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pv_results.json")
KEYS = [(c, k) for c in V.CLASS_ORDER for k in ("burst", "guard")]


def kk(t):
    return f"{t[0]}|{t[1]}"


def build_rows(bl, L):
    out = {}
    for (c, k) in KEYS:
        b = bl[(c, L, k)]
        out[f"{c}|{k}"] = dict(weapon=b["weapon"], weapon_name=b["weapon_name"], look=b["look"], full=b["full"],
                               armor=b["armor"], shield=b["shield"], accs=b["accs"], stats=b["s"],
                               alloc={s: v for s, v in b["alloc"].items() if v}, hp=round(b["max_hp"]),
                               mp=round(b["max_mp"]), defense=round(b["defense"], 1), dr=round(b["dr"], 3),
                               evasion=round(b["evasion"], 3), block=round(b["block"], 3) if b.get("shield") else 0.0,
                               crit=round(b["crit"], 3), crit_dmg=round(b["crit_dmg"], 3), atk_speed=round(b["atk_speed"], 3),
                               per_hit=round(b["ap"], 1), period=round(b["period"], 3), skill_power=round(b["sp"], 1),
                               interval=b["w"]["interval"], style=b["w"]["style"], kind=b["w"]["kind"])
    return out


def rot_tables(P, bl, L):
    rot, rot_all, hit, crit = {}, {}, {}, {}
    for a in KEYS:
        A = bl[(a[0], L, a[1])]
        for b in KEYS:
            Bb = bl[(b[0], L, b[1])]
            r, parts = S.rotation(A, Bb, P)
            ra, _ = S.rotation(A, Bb, P, mode="all")
            h, c = S.basic_hit(A, Bb, P)
            key = kk(a) + ">" + kk(b)
            rot[key] = round(r, 3)
            rot_all[key] = round(ra, 3)
            hit[key] = round(h, 4)
            crit[key] = round(c, 4)
    # 한 바퀴 구성 (같은 레벨 유리 사냥꾼 상대)
    parts = {}
    for c in V.CLASS_ORDER:
        A = bl[(c, L, "burst")]
        r, ps = S.rotation(A, bl[("hunter", L, "burst")], P)
        parts[c] = [(n, round(p, 3)) for n, p in ps]
    return dict(rotation=rot, rotation_all_crit=rot_all, basic_hit=hit, basic_crit=crit, parts=parts)


def duel_tables(P, L, n, bl):
    M = MX.matrix(P, L, n=n, builds={(c, k): bl[(c, L, k)] for c, k in KEYS})
    s = MX.summary(M)
    win = {kk(a) + ">" + kk(b): round(M[(a, b)]["win_a"] + 0.5 * M[(a, b)]["draw"], 3) for a in KEYS for b in KEYS}
    ttk = {kk(a) + ">" + kk(b): round(M[(a, b)]["ttk"], 1) for a in KEYS for b in KEYS}
    draw = {kk(a) + ">" + kk(b): round(M[(a, b)]["draw"], 3) for a in KEYS for b in KEYS}
    left = {kk(a) + ">" + kk(b): round(M[(a, b)]["left_a"], 3) for a in KEYS for b in KEYS}
    summ = {k: v for k, v in s.items() if k not in ("class", "class_all")}
    summ["class"] = {kk(k): round(v, 3) for k, v in s["class"].items()}
    summ["class_all"] = {k: round(v, 3) for k, v in s["class_all"].items()}
    return dict(win=win, ttk=ttk, draw=draw, left=left, summary=summ)


def targets(P, L):
    m = T.rot_metrics(P, L)
    return dict(hit_max=round(m["hit_max"][0], 4), hit_max_pair=list(m["hit_max"][1:]), crit_max=round(m["crit_max"][0], 4),
                crit_max_pair=list(m["crit_max"][1:]), hit_med_gg=round(m["hit_med_gg"], 4),
                gg=round(m["gg_dmg_med"], 3), gg_all=round(m["gga_dmg_med"], 3), gd=round(m["gd_dmg_med"], 3),
                dg=round(m["dg_med"], 3), dd=round(m["dd_med"], 3),
                gg_by_class={k: round(v, 3) for k, v in m["gg"].items()},
                gd_by_class={k: round(v, 3) for k, v in m["gd"].items()})


def main(n_final=40, n_cmp=24):
    t0 = time.time()
    bl = {}
    for L in (5, 10) + B.LEVELS:
        for c in V.CLASS_ORDER:
            for k in ("burst", "guard"):
                bl[(c, L, k)] = B.build(c, L, k)
    T._BUILDS = bl
    configs = {"0.3.4": S.PVP_034, "nocap": S.PVP_NOCAP, "new": F.PVP_NEW}
    res = dict(levels=list(B.LEVELS), low_levels=[5, 10], builds={}, configs={}, cc_rows=CC.rows(),
               skill_mult=F.PVP_NEW["skill_mult"])
    for L in (5, 10) + B.LEVELS:
        res["builds"][L] = build_rows(bl, L)
    for name, P in configs.items():
        R = dict(targets={}, rot={}, duel={})
        for L in (5, 10) + B.LEVELS:
            R["targets"][L] = targets(P, L)
            if L in B.LEVELS:
                R["rot"][L] = rot_tables(P, bl, L)
            if name == "new" or L in B.LEVELS:
                R["duel"][L] = duel_tables(P, L, n_final if name == "new" else n_cmp, bl)
            print(f"{name} L{L} done {time.time()-t0:.0f}s", flush=True)
        res["configs"][name] = R
    # 상태이상 규칙만 0.3.4 (새 설정 위) — 묶인 시간 비교
    P0 = F.make(cc_mult={k: 1.0 for k in F.CC_MULT}, cc_cap={}, dr=None, stun_immune=0.0, slow_cap=0.85)
    res["cc_compare"] = {}
    for L in B.LEVELS:
        a = duel_tables(F.PVP_NEW, L, 24, bl)["summary"]
        b = duel_tables(P0, L, 24, bl)["summary"]
        res["cc_compare"][L] = dict(new=dict(cc=round(a["cc_per_fight"], 2), chain=round(a["chain_max"], 2),
                                             chain_med=round(a["chain_med"], 2)),
                                    old=dict(cc=round(b["cc_per_fight"], 2), chain=round(b["chain_max"], 2),
                                             chain_med=round(b["chain_med"], 2)))
    # 직업 보정 없이 (새 설정에서 class_damage 만 뺀 것)
    Pnc = F.make(class_mult={})
    res["class_before"] = {}
    for L in B.LEVELS:
        sm = duel_tables(Pnc, L, 24, bl)["summary"]
        res["class_before"][L] = dict(class_all=sm["class_all"], burst_vs_guard=round(sm["burst_vs_guard"], 3))
    # 레벨 사이 싸움 (같은 직업·빌드)
    res["cross"] = {}
    import pv_duel as D
    for La, Lb in ((20, 35), (35, 50), (20, 50)):
        w = []
        for c in V.CLASS_ORDER:
            for k in ("burst", "guard"):
                r = D.duel(bl[(c, La, k)], bl[(c, Lb, k)], F.PVP_NEW, n=12)
                w.append(r["win_a"] + 0.5 * r["draw"])
        res["cross"][f"{La}-{Lb}"] = round(st.mean(w), 3)
    # 레벨별 기준 배율 · 완충 · 강인함 예시
    res["curves"] = {L: dict(m=round(S.level_mult(L, F.PVP_NEW) * F.PVP_NEW["dmg"], 3), buffer=round(S.buffer_hp(L, F.PVP_NEW)))
                     for L in (1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)}
    res["net"] = {}
    for L in B.LEVELS:
        for (c, k) in KEYS:
            b = bl[(c, L, k)]
            f = S.buffer_factor(b, F.PVP_NEW)
            R_ = S.resilience(b, F.PVP_NEW)
            res["net"][f"{L}|{c}|{k}"] = dict(hp=round(b["max_hp"]), pool=round(b["max_hp"] + S.buffer_hp(L, F.PVP_NEW)),
                                              buffer_factor=round(f, 3), resilience=round(R_, 3),
                                              S=round(b["s"]["VIT"] + b["defense"], 1), dr=round(b["dr"], 3))
    res["elapsed_s"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=0, default=str)
    print("wrote", OUT, res["elapsed_s"], "s")


if __name__ == "__main__":
    n1 = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    n2 = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    main(n1, n2)
