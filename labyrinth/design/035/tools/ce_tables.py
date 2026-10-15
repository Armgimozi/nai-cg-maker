#!/usr/bin/env python3
"""
무기 표: 기존 131 + gear_spec 새 106 — 간격·새 한 방 피해·DPS 등가·스킬 위력·무기 스킬 배율 계수.
요구 능력치 세금 표, PvP 확인 표, 미래 무기 공식 표.  →  ce_tables.json (combat_spec.json 이 읽음)
"""
import json
import math
import os

import ce_core as C
import ce_model as M
import ce_sim as X

HERE = os.path.dirname(os.path.abspath(__file__))
P = X.P_FINAL


def old_type_of(wid):
    w = C.WEAPONS.get(wid)
    return w["weapon_type"] if w else None


def ws_factor_existing(wid):
    """무기 스킬 배율 옮김 계수: 새 배율 = 옛 배율 × K(방식, 간격) ÷ (옛 종류 주기 × 스킬 위력 배수)."""
    w = C.WEAPONS[wid]
    st = C.style_of(w["model"]["shape"])
    iv = C.interval_of(wid)
    spm = M.CASTER_SP_MULT if st == "caster" else 1.0
    return C.K_style(st, iv) / (C.old_rate(w["weapon_type"]) * spm)


def weapon_rows():
    rows = {}
    for wid, w in C.WEAPONS.items():
        st = C.style_of(w["model"]["shape"])
        iv = C.interval_of(wid)
        ph = C.new_per_hit(wid, P)
        mid_new = (ph[0] + ph[1]) / 2
        old_mid = C.mid(w["stats"]["damage"])
        dps_old = C.old_weapon_dps(wid)
        dps_new = mid_new / iv
        c = C.rebase_factor(w["level_req"], P, "magic" if st == "caster" else "physical")
        sp = C.skill_power(mid_new, iv, st, M.CASTER_SP_MULT if st == "caster" else 1.0)
        rows[wid] = dict(src="existing", name=w["name"], shape=w["model"]["shape"], style=st,
                         kind="magic" if st == "caster" else "physical", level=w["level_req"], rarity=w["rarity"],
                         old_type=w["weapon_type"], old_damage=w["stats"]["damage"], old_rate=round(C.old_rate(w["weapon_type"]), 3),
                         interval=iv, per_hit=ph, rate_per_s=round(1 / iv, 2), dps_old=round(dps_old, 2),
                         dps_new=round(dps_new, 2), dps_target=round(dps_old * c, 2), rebase_c=round(c, 3),
                         per_hit_factor=round(mid_new / old_mid, 4), skill_power=round(sp, 2),
                         weapon_skill_factor=round(ws_factor_existing(wid), 3) if w.get("weapon_skills") else None,
                         n_weapon_skills=len(w.get("weapon_skills") or []))
    for wid, w in C.NEW_WEAPONS.items():
        st = C.style_of(w["model"]["shape"])
        iv = C.interval_of(wid)
        ph = C.new_per_hit_newweapon(wid, P)
        mid_new = (ph[0] + ph[1]) / 2
        sp = C.skill_power(mid_new, iv, st, M.CASTER_SP_MULT if st == "caster" else 1.0)
        sp_old = w["attack"]["speed"]
        rows[wid] = dict(src="gear_spec_new", name=w["name"], shape=w["model"]["shape"], style=st,
                         kind="magic" if st == "caster" else "physical", level=w["level_req"], rarity=w["rarity"],
                         gear_spec_damage=w["stats"]["damage"], gear_spec_speed=sp_old, interval=iv, per_hit=ph,
                         rate_per_s=round(1 / iv, 2), dps_new=round(mid_new / iv, 2), skill_power=round(sp, 2),
                         weapon_skill_factor=None, n_weapon_skills=len(w.get("weapon_skills") or []))
    return rows


def band_spread(rows):
    """5레벨 구간마다 스킬 위력 최고÷최저 (신화 제외) — 느린 무기가 스킬을 독차지하지 않는지."""
    out = {}
    for lo in range(1, 50, 5):
        hi = lo + 4
        b = [r for r in rows.values() if lo <= r["level"] <= hi and r["rarity"] != "mythic"]
        if not b:
            continue
        sps = [r["skill_power"] for r in b]
        ph = [(r["per_hit"][0] + r["per_hit"][1]) / 2 for r in b]
        dps = [r.get("dps_new") for r in b]
        out[f"{lo}-{hi}"] = dict(n=len(b), skill_power=[round(min(sps), 1), round(max(sps), 1), round(max(sps) / min(sps), 2)],
                                 per_hit=[round(min(ph), 1), round(max(ph), 1), round(max(ph) / min(ph), 2)],
                                 dps=[round(min(dps), 1), round(max(dps), 1)])
    return out


def future_formula_table():
    out = {}
    for L in (1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50):
        Pw = 7 + 0.25 * (L - 1) + 0.0195 * (L - 1) ** 2
        c = C.rebase_factor(L, P)
        out[L] = dict(P_old=round(Pw, 2), c=round(c, 3), TP_new_common=round(Pw * c, 2))
    return out


def tax_table():
    """요구 능력치 종류별 피해 손해 — 같은 무기·같은 레벨, '피해 스탯 요구'(STR/INT) 대비. 판금(VIT) 또는 가죽(DEX)을 입은 물리,
    천(INT|WIS)을 입은 마법. 분배 = 요구치 채우고 남은 것: 피해 스탯 3 : VIT 2 비율로."""
    res = {}
    for L in (10, 25, 45):
        R = C.req_value(L)
        n = M.points(L)
        for armor, arm_stat in (("heavy", "VIT"), ("light", "DEX")):
            for req in ("STR", "DEX", "VIT", "WIS", "LUK"):
                for split in (False, True):
                    need = {arm_stat: R}
                    if split and req != "STR":
                        need[req] = max(need.get(req, 0), math.ceil(0.6 * R))
                        need["STR"] = max(need.get("STR", 0), math.ceil(0.4 * R))
                    else:
                        need[req] = max(need.get(req, 0), R)
                    base = 3
                    a = {k: max(0, v - base) for k, v in need.items()}
                    left = n - sum(a.values())
                    if left < 0:
                        res[f"L{L}|{armor}|{req}|{'split' if split else 'single'}"] = None
                        continue
                    want = {"STR": 0.6 * n, "VIT": 0.4 * n}
                    while left > 0:
                        k = max(("STR", "VIT"), key=lambda s: want[s] - a.get(s, 0))
                        a[k] = a.get(k, 0) + 1
                        left -= 1
                    s = {k: base + a.get(k, 0) for k in ("STR", "DEX", "VIT", "WIS", "LUK")}
                    dps = (1 + P["k_phys"] * s["STR"]) * (1 + min(P["cap_speed"], P["dex_speed"] * s["DEX"])) * \
                          (1 + 0.5 * min(0.75, 0.05 + P["dex_crit"] * s["DEX"] + P["luk_crit"] * s["LUK"]))
                    hp = s["VIT"]
                    res[f"L{L}|{armor}|{req}|{'split' if split else 'single'}"] = dict(stats=s, dps_index=round(dps, 3), vit=hp)
        # 기준 = 같은 방어구 + STR 요구
    out = {}
    for k, v in res.items():
        if v is None:
            out[k] = None
            continue
        L, armor, req, sp = k.split("|")
        ref = res[f"{L}|{armor}|STR|single"]
        out[k] = dict(v, dps_vs_str=round(v["dps_index"] / ref["dps_index"] - 1, 3), vit_vs_str=v["vit"] - ref["vit"])
    return out


def pvp_table():
    """같은 레벨 광전사(대검) → 사냥꾼(가죽) 기본 공격 한 대 = 상대 최대 HP 의 몇 %, 쓰러뜨리는 데 걸리는 초 (배율 0.7, 상한 35%)."""
    C.USE_GEAR_REQUIRES = False
    out = {}
    for L in (1, 10, 20, 30, 44):
        for atk, vic in (("berserker", "hunter"), ("shadow", "guardian"), ("hunter", "arcanist")):
            o_a, o_v = M.old_player(atk, L), M.old_player(vic, L)
            n_a, n_v = M.new_player(atk, L, P), M.new_player(vic, L, P)
            def one(a, v, new):
                dfac = 100 / (100 + v["d"]["defense"])
                hit = a["ap"] * dfac * 0.7
                if a.get("wtype") == "bow" or a.get("style") == "ranged":
                    hit *= (1.25 * (1.15 if a["cls"] == "hunter" else 1)) if not new else (P["keen_eye"] if a["cls"] == "hunter" else 1)
                hit = min(hit, v["hp"] * 0.35)
                per_s = a["basic"] / max(1e-9, a["ap"] * (1 + a["crit"] * (a["d"]["crit_dmg"] - 1)))
                return hit / v["hp"], v["hp"] / (hit * per_s * (1 + a["crit"] * 0.5))
            ho, to = one(o_a, o_v, False)
            hn, tn = one(n_a, n_v, True)
            out[f"L{L} {atk}->{vic}"] = dict(old_hit_pct=round(ho, 3), new_hit_pct=round(hn, 3), old_ttk_s=round(to, 1), new_ttk_s=round(tn, 1))
    return out


if __name__ == "__main__":
    rows = weapon_rows()
    ex = [r for r in rows.values() if r["src"] == "existing"]
    err = [abs(r["dps_new"] / r["dps_target"] - 1) for r in ex]
    data = dict(weapons=rows, band_spread=band_spread(rows), future=future_formula_table(), tax=tax_table(), pvp=pvp_table(),
                check=dict(existing=len(ex), new=len(rows) - len(ex), dps_rounding_err_mean=round(sum(err) / len(err), 4),
                           dps_rounding_err_max=round(max(err), 4)))
    with open(os.path.join(HERE, "ce_tables.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(data["check"])
    for k, v in data["band_spread"].items():
        print(k, v)
    for k, v in data["pvp"].items():
        print(k, v)
