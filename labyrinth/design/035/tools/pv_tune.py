#!/usr/bin/env python3
"""TASK P — 목표값 재기 (같은 레벨): 기본 공격 한 대 · 한 바퀴(유리↔유리, 유리→수비) · (선택) 1:1 승률."""
import statistics as st
import sys

import pv_build as B
import pv_core as V
import pv_sim as S

DMG_CLASSES = ("berserker", "hunter", "arcanist", "shadow")
_BUILDS = None


def builds():
    global _BUILDS
    if _BUILDS is None:
        _BUILDS = B.all_builds()
    return _BUILDS


def rot_metrics(P, L):
    bl = builds()
    out = {}
    hits, crits = [], []
    for ca in V.CLASS_ORDER:
        for ka in ("burst", "guard"):
            a = bl[(ca, L, ka)]
            for cb in V.CLASS_ORDER:
                for kb in ("burst", "guard"):
                    h, c = S.basic_hit(a, bl[(cb, L, kb)], P)
                    hits.append((h, ca, ka, cb, kb))
                    crits.append((c, ca, ka, cb, kb))
    hits.sort(reverse=True)
    crits.sort(reverse=True)
    out["hit_max"] = hits[0]
    out["crit_max"] = crits[0]
    # 같은 빌드끼리(유리 → 유리) 기본 공격 한 대 중앙값
    out["hit_med_gg"] = st.median(h for h, ca, ka, cb, kb in hits if ka == "burst" and kb == "burst")
    gg, gga, gd, dg, dd = {}, {}, {}, {}, {}
    for ca in V.CLASS_ORDER:
        a = bl[(ca, L, "burst")]
        ad = bl[(ca, L, "guard")]
        gg[ca] = st.median(S.rotation(a, bl[(cb, L, "burst")], P)[0] for cb in V.CLASS_ORDER)
        gga[ca] = st.median(S.rotation(a, bl[(cb, L, "burst")], P, mode="all")[0] for cb in V.CLASS_ORDER)
        gd[ca] = st.median(S.rotation(a, bl[(cb, L, "guard")], P)[0] for cb in V.CLASS_ORDER)
        dg[ca] = st.median(S.rotation(ad, bl[(cb, L, "burst")], P)[0] for cb in V.CLASS_ORDER)
        dd[ca] = st.median(S.rotation(ad, bl[(cb, L, "guard")], P)[0] for cb in V.CLASS_ORDER)
    out.update(gg=gg, gga=gga, gd=gd, dg=dg, dd=dd)
    out["gg_dmg_med"] = st.median(gg[c] for c in DMG_CLASSES)
    out["gga_dmg_med"] = st.median(gga[c] for c in DMG_CLASSES)
    out["gd_dmg_med"] = st.median(gd[c] for c in DMG_CLASSES)
    out["dg_med"] = st.median(dg.values())
    out["dd_med"] = st.median(dd.values())
    return out


def show(P, levels=B.LEVELS):
    for L in levels:
        m = rot_metrics(P, L)
        h = m["hit_max"]
        c = m["crit_max"]
        print(f"L{L}: hit max {h[0]*100:5.1f}% ({h[1]}-{h[2][0]}→{h[3]}-{h[4][0]}) crit max {c[0]*100:5.1f}% "
              f"| hit med g→g {m['hit_med_gg']*100:4.1f}% | rot g→g dmg-med {m['gg_dmg_med']*100:5.0f}% (all-crit {m['gga_dmg_med']*100:5.0f}%) "
              f"g→d {m['gd_dmg_med']*100:4.0f}% | d→g {m['dg_med']*100:4.0f}% d→d {m['dd_med']*100:4.0f}%")
        print("      g→g " + " ".join(f"{k[:4]} {v*100:4.0f}" for k, v in m["gg"].items()) +
              " | g→d " + " ".join(f"{k[:4]} {v*100:4.0f}" for k, v in m["gd"].items()))


if __name__ == "__main__":
    show(S.PVP_NOCAP)
