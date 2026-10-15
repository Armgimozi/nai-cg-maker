"""1:1 승률 표 (같은 레벨, 직업 6 × 빌드 2 → 12×12)."""
import statistics as st
import sys

import pv_build as B
import pv_core as V
import pv_duel as D

KINDS = ("burst", "guard")


def matrix(P, L, n=40, seed=7, builds=None):
    bl = builds or {(c, k): B.build(c, L, k) for c in V.CLASS_ORDER for k in KINDS}
    keys = [(c, k) for c in V.CLASS_ORDER for k in KINDS]
    M = {}
    for i, a in enumerate(keys):
        for j, b in enumerate(keys):
            if j < i:
                r = M[(b, a)]
                M[(a, b)] = dict(win_a=r["win_b"], win_b=r["win_a"], draw=r["draw"], ttk=r["ttk"], left_a=r["left_b"],
                                 left_b=r["left_a"], cc_a=r["cc_b"], cc_b=r["cc_a"], chain=r["chain"], chain_med=r["chain_med"])
                continue
            M[(a, b)] = D.duel(bl[a], bl[b], P, n=n, seed=seed + i * 31 + j)
    return M


def summary(M):
    keys = sorted({a for a, _ in M})
    out = {}
    bg = [M[((ca, "burst"), (cb, "guard"))]["win_a"] + 0.5 * M[((ca, "burst"), (cb, "guard"))]["draw"]
          for ca in V.CLASS_ORDER for cb in V.CLASS_ORDER]
    out["burst_vs_guard"] = st.mean(bg)
    out["bvg_min"] = min(bg)
    out["bvg_max"] = max(bg)
    out["ttk_bb"] = st.median(M[((ca, "burst"), (cb, "burst"))]["ttk"] for ca in V.CLASS_ORDER for cb in V.CLASS_ORDER)
    out["ttk_bg"] = st.median(M[((ca, "burst"), (cb, "guard"))]["ttk"] for ca in V.CLASS_ORDER for cb in V.CLASS_ORDER)
    out["ttk_gg"] = st.median(M[((ca, "guard"), (cb, "guard"))]["ttk"] for ca in V.CLASS_ORDER for cb in V.CLASS_ORDER)
    out["draw_gg"] = st.mean(M[((ca, "guard"), (cb, "guard"))]["draw"] for ca in V.CLASS_ORDER for cb in V.CLASS_ORDER)
    out["cc_per_fight"] = st.mean((v["cc_a"] + v["cc_b"]) / 2 for v in M.values())
    out["chain_max"] = max(v["chain"] for v in M.values())
    out["chain_med"] = st.median(v["chain_med"] for v in M.values())
    cls = {}
    for c in V.CLASS_ORDER:
        for k in KINDS:
            cls[(c, k)] = st.mean(M[((c, k), b)]["win_a"] + 0.5 * M[((c, k), b)]["draw"] for b in keys)
    out["class"] = cls
    out["class_all"] = {c: (cls[(c, "burst")] + cls[(c, "guard")]) / 2 for c in V.CLASS_ORDER}
    return out


def show(P, levels=B.LEVELS, n=30):
    res = {}
    for L in levels:
        M = matrix(P, L, n=n)
        s = summary(M)
        res[L] = (M, s)
        print(f"L{L}: burst→guard 승률 {s['burst_vs_guard']*100:4.0f}% (최저 {s['bvg_min']*100:3.0f} 최고 {s['bvg_max']*100:3.0f}) | "
              f"시간 중앙 b-b {s['ttk_bb']:4.1f}s b-g {s['ttk_bg']:4.1f}s g-g {s['ttk_gg']:4.1f}s (g-g 무승부 {s['draw_gg']*100:3.0f}%) | 묶임/판 {s['cc_per_fight']:.1f}s 최장 연속 {s['chain_max']:.1f}s (중앙 {s['chain_med']:.1f})")
        print("     직업(둘 평균) " + " ".join(f"{c[:4]} {v*100:3.0f}" for c, v in s["class_all"].items()) +
              " | burst " + " ".join(f"{c[:4]} {s['class'][(c,'burst')]*100:3.0f}" for c in V.CLASS_ORDER) +
              " | guard " + " ".join(f"{c[:4]} {s['class'][(c,'guard')]*100:3.0f}" for c in V.CLASS_ORDER))
    return res


if __name__ == "__main__":
    import pv_final as F
    show(F.PVP_NEW)
