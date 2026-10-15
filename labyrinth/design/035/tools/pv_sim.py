#!/usr/bin/env python3
"""
TASK P — PvP 시뮬레이터 (새 전투 모델 위).

  PVP_034    지금(0.3.4) 설정 = 배율 0.7 · 한 방 상한 35% · 그 밖은 없음
  PVP_NOCAP  상한만 없앤 것 (1.0)
  PVP_NEW    이 명세 최종안 (pvp_spec)

  rotation(a, b, P)   a 의 '한 바퀴'(버프 → 모든 스킬 → 그 사이 기본 공격, 재사용 대기 없음)가 b 최대 HP 의 몇 %
  basic_hit(a, b, P)  기본 공격 한 대 (치명 아님 / 치명) = b 최대 HP 의 몇 %
  duel(a, b, P, n)    1:1 끝까지 (0.1초 단위 몬테카를로) — 승률·걸린 시간·남은 HP
"""
import copy
import math
import random

import pv_core as V
import pv_build as B

# ───────────────────────────── PvP 설정 ─────────────────────────────
CC_IDS = ("stun", "frozen", "root", "silence", "blind", "slow", "cooldown_slow")
PVP_034 = dict(name="0.3.4", dmg=0.7, max_hit=0.35, crit_scale=1.0, res=None, heal=1.0, lifesteal=1.0, shield=1.0,
               ult=1.0, wskill=1.0, cc_mult={k: 1.0 for k in CC_IDS}, cc_cap={}, dr=None, stun_immune=0.0)
PVP_NOCAP = dict(PVP_034, name="상한만 없앰", max_hit=1.0)


def buffer_hp(L, P):
    """PvP 완충 체력 B(L) — 모두에게 같은 양. PvP 피해 × H / (H + B)."""
    bf = P.get("buffer")
    if not bf:
        return 0.0
    if "coef" in bf:
        return bf["coef"] * L ** bf["exp"]
    if "low_per_level" in bf:
        knee = bf.get("knee", 20)
        return bf["low_per_level"] * min(L, knee) + bf["per_level"] * max(0, L - knee)
    if "base" in bf:
        return bf["base"] + bf["per_level"] * L
    return bf["per_level"] * L + bf.get("per_level_sq", 0.0) * L * L


def buffer_factor(d, P):
    B = buffer_hp(d["L"], P)
    return d["max_hp"] / (d["max_hp"] + B) if B > 0 else 1.0


def resilience(d, P):
    """PvP 강인함 R = 상한 × S ÷ (S + k × 레벨),  S = 체력(VIT) + 방어.  받는 PvP 피해 × (1 − R)."""
    r = P.get("res")
    if not r:
        return 0.0
    if callable(r):
        return r(d)
    S_ = d["s"]["VIT"] + d["defense"]
    return r["cap"] * S_ / (S_ + r["k"] * d["L"])


def level_mult(L, P):
    """PvP 피해 배율의 레벨 곡선: 기준 레벨 이하 1, 그 위 (기준 ÷ 레벨)^지수."""
    c = P.get("level_curve")
    if not c:
        return 1.0
    return min(1.0, (c["ref"] / L) ** c["exp"])


# ───────────────────────────── 피해 한 건 (기대값) ─────────────────────────────

def mitig(a, b, P, kind="physical", skill=False, dot=False, facing=0.6, extra_taken=0.0, dmg_buff=0.0):
    """원피해 1 이 b 에게 실제로 몇이 되는가 (치명 제외, 회피 제외)."""
    m = P["dmg"] * level_mult(max(a["L"], b["L"]), P) * (1 + dmg_buff) * P.get("class_mult", {}).get(a["cls"], 1.0)
    if skill:
        m *= 1 + a["skill_dmg"]
    if not dot:
        m *= 100.0 / (100.0 + b["defense"] * P.get("def_weight", 1.0))
    m *= 1 - b["dr"]
    m *= 1 + extra_taken
    if not dot and b["block"] > 0 and b.get("shield"):
        m *= 1 - b["block"] * facing * (1 - 0.4)
    m *= buffer_factor(b, P)
    m *= 1 - resilience(b, P)
    return m


def crit_mult(a, P, extra_cc=0.0, extra_cd=0.0, mode="exp"):
    cd = 1 + (a["crit_dmg"] + extra_cd - 1) * P["crit_scale"]
    cc = min(1.0, a["crit"] + extra_cc)
    if mode == "all":
        return cd
    if mode == "none":
        return 1.0
    return 1 + cc * (cd - 1)


def basic_hit(a, b, P):
    """기본 공격 한 대 (치명 아님, 치명) — b 최대 HP 비율. 사냥꾼 매의 눈(끝까지 당김) 포함."""
    w = a["w"]
    ap = a["ap"] * (1 + V.CLASS_VALUES["keen_eye_full_draw"] if (a["cls"] == "hunter" and w["style"] == "ranged") else 1)
    m = mitig(a, b, P, w["kind"], facing=0.6)
    hit = ap * m
    crit = hit * (1 + (a["crit_dmg"] - 1) * P["crit_scale"])
    cap = b["max_hp"] * P["max_hit"]
    return min(hit, cap) / b["max_hp"], min(crit, cap) / b["max_hp"]


def _wskill_list(a):
    out = []
    for s in a["w"]["skills"]:
        if s["input"] == "LEFT" and s["cooldown"] <= 2.0:
            continue          # 휘두를 때마다 나가는 덧 공격 — 기본 공격 쪽에서 셈
        if s["damage"] <= 0 and s["percent"] <= 0 and s["execute"] <= 0:
            continue
        out.append(s)
    return out


def _swing_extra(a):
    for s in a["w"]["skills"]:
        if s["input"] == "LEFT" and s["cooldown"] <= 2.0 and s["damage"] > 0:
            return s
    return None


def rotation(a, b, P, mode="exp", window=3.0, land=1.0, opener=True):
    """한 바퀴: 버프 → 직업 스킬(해금된 것) + 무기 스킬 전부 + 그 사이 기본 공격.
    mode: exp = 치명 기대값 · all = 모두 치명 (운 좋은 한 바퀴). land = 스킬이 맞는 비율 (1 = 다 맞음).
    방어 쪽 즉시 반응(보호막·물약)은 넣지 않는다 — '살아남아 되받아칠 수 있나'를 보는 값."""
    L = a["L"]
    cls = a["cls"]
    kit = [k for k in V.class_kit(cls) if k["unlock"] <= L]
    dmg_buff = 0.0
    taken = 0.0
    atk_speed = a["atk_speed"]
    cc_bonus = 0.0
    total = 0.0
    parts = []
    for k in kit:
        if k["id"] == "blood_frenzy":
            dmg_buff += k["buff"]["damage"]
            atk_speed = min(0.6, atk_speed + k["buff"]["attack_speed"])
        if k["id"] == "sacred_ward":
            dmg_buff += k["buff"]["damage"]
        if k["id"] == "hunters_mark":
            taken += k["debuff"][2]
    # 광전사 피의 분노(HP 50% 아래 최대 +25%) — 한 바퀴 시작은 HP 가득 → 0. 비전 공명(서로 다른 스킬 2개 4초 안) +10%
    combo = 0.10 if cls == "arcanist" else 0.0
    unit = a["class_unit"]
    hp = b["max_hp"]
    vuln = 0.0
    first = opener and cls == "shadow"
    for k in kit:
        if k["dmg"] <= 0:
            continue
        kind = k["kind"]
        dm = k["dmg"]
        cm = crit_mult(a, P, mode=mode)
        if k["id"] == "shadow_strike" and first:
            dm = k["back_dmg"] * (1 + 0.5)          # 연막 은신 → 등 뒤 확정 치명 + 첫 공격 +50%
            cm = crit_mult(a, P, mode="all")
            first = False
        if k["id"] == "shadow_execution":
            dm = k["dmg"] * (1 + 0.5 * k["execute"][1])  # 3연타 중 일부가 처형 구간
        ultm = (P["ult"] if k["ult"] else 1.0) * P.get("skill_mult", {}).get(k["id"], 1.0)
        dot = 0.0
        if k.get("dot"):
            _, dur, ratio = k["dot"]
            dot = ratio * dur * V.SKILL_SCALE[cls] * a["sp"] * a["power"][V.CLASS_SKILL_KIND[cls]] * ultm
        x = unit * dm * cm * ultm * land * k["hit"] ** 0 * mitig(a, b, P, kind, True, extra_taken=taken + vuln,
                                                                    dmg_buff=dmg_buff + combo * 0.5)
        x += dot * land * mitig(a, b, P, kind, True, dot=True, extra_taken=taken + vuln, dmg_buff=dmg_buff)
        total += x
        parts.append((k["id"], x / hp))
        if k.get("debuff") and k["debuff"][0] == "vulnerable":
            vuln = k["debuff"][2]
    if cls == "shadow" and L >= 18:
        # 독날: 한 바퀴(3초) 동안 쌓이는 독 — 초당 SP×0.10×중첩×skill_scale
        vb = next(k for k in kit if k["id"] == "venom_blades")["venom"]
        hits = min(vb["max"], window / a["period"])
        x = vb["dps"] * (hits / 2) * window * V.SKILL_SCALE[cls] * a["sp"] * a["power"]["physical"] * \
            mitig(a, b, P, "physical", True, dot=True, extra_taken=taken + vuln)
        total += x
        parts.append(("venom_blades", x / hp))
    for s in _wskill_list(a):
        cm = crit_mult(a, P, mode=mode)
        sm = P["wskill"] * P.get("skill_mult", {}).get(a["weapon"] + ":" + str(s["input"]), 1.0)
        x = a["sp"] * a["power"][s["kind"] if s["kind"] != "hybrid" else a["w"]["kind"]] * s["damage"] * cm * land * \
            sm * mitig(a, b, P, s["kind"], True, extra_taken=taken + vuln, dmg_buff=dmg_buff)
        x += s["percent"] * hp * P["dmg"] * level_mult(max(a["L"], b["L"]), P) * land * sm * (1 - resilience(b, P)) * buffer_factor(b, P)
        total += x
        parts.append((s["name"], x / hp))
    # 기본 공격 (스킬 하나마다 0.25초를 쓴다)
    nsk = sum(1 for k in kit if k["dmg"] > 0 or k.get("buff")) + len(_wskill_list(a))
    t = max(0.0, window - 0.25 * nsk)
    w = a["w"]
    period = a["period"] * (1 + a["atk_speed"]) / (1 + atk_speed)
    n = t / period
    ap = a["ap"] * (1 + V.CLASS_VALUES["keen_eye_full_draw"] if (cls == "hunter" and w["style"] == "ranged") else 1)
    cm = crit_mult(a, P, mode=mode)
    x = n * ap * cm * mitig(a, b, P, w["kind"], extra_taken=taken + vuln, dmg_buff=dmg_buff)
    ex = _swing_extra(a)
    if ex:
        x += min(n, t / ex["cooldown"]) * a["sp"] * a["power"][w["kind"]] * ex["damage"] * cm * P["wskill"] * \
            mitig(a, b, P, w["kind"], True, extra_taken=taken + vuln, dmg_buff=dmg_buff)
    total += x
    parts.append(("basic", x / hp))
    if P["max_hit"] < 1.0:
        total = sum(min(p * hp, hp * P["max_hit"]) for _n, p in parts)
    return total / hp, parts


if __name__ == "__main__":
    import sys
    P = PVP_NOCAP
    builds = B.all_builds()
    for L in B.LEVELS:
        print(f"=== L{L}  (rotation % of target max HP, exp crits | all crits) — {P['name']}")
        hdr = "attacker\\target " + " ".join(f"{c[:4]}-{k[0]}" for c in V.CLASS_ORDER for k in ('burst', 'guard'))
        print(hdr)
        for ca in V.CLASS_ORDER:
            a = builds[(ca, L, "burst")]
            row = []
            for cb in V.CLASS_ORDER:
                for kb in ("burst", "guard"):
                    b = builds[(cb, L, kb)]
                    r, _ = rotation(a, b, P)
                    row.append(f"{r*100:6.0f}")
            print(f"{ca:9} burst  " + " ".join(row))
        for ca in V.CLASS_ORDER:
            a = builds[(ca, L, "burst")]
            b = builds[(ca, L, "burst")]
            h, hc = basic_hit(a, b, P)
            r, parts = rotation(a, b, P)
            print(ca, f"basic {h*100:.1f}% crit {hc*100:.1f}%", " | ".join(f"{n} {p*100:.0f}" for n, p in parts))


# ───────────────────────────── 스킬마다 PvP 배율 (규칙) ─────────────────────────────

def class_coef(cls, k):
    """직업 스킬 한 번이 한 사람에게 주는 피해 계수 (스킬 위력 단위, 직업 skill_scale 포함, 맞을 확률 빼고)."""
    c = k["dmg"]
    if k["id"] == "shadow_execution":
        c = k["dmg"] * (1 + 0.5 * k["execute"][1])
    if k["id"] == "shadow_strike":
        c = k["back_dmg"]            # 등 뒤 3배 (확정 치명은 이 스킬의 개성이라 계수에 넣지 않는다)
    if k.get("dot"):
        c += k["dot"][2] * k["dot"][1]
    return c * V.SKILL_SCALE[cls]


def weapon_coef(s):
    return s["damage"] + s["execute"] * 0.5 + s["percent"] * 10.0 + sum(
        (pot if 0 < pot < 1 else 0.15) * dur for (_t, dur, pot) in s["dot"])


def skill_mults(cap, round_to=0.05, only_below=0.9):
    """스킬마다 PvP 배율 = min(1, cap ÷ 계수), 0.05 단위 내림. 직업 스킬 id · 무기 스킬 '무기:입력'."""
    out = {}
    for cls in V.CLASS_ORDER:
        for k in V.class_kit(cls):
            if k["dmg"] <= 0:
                continue
            c = class_coef(cls, k)
            if c > cap:
                v = max(0.1, math.floor(cap / c / round_to + 1e-9) * round_to)
                if v <= only_below + 1e-9:
                    out[k["id"]] = round(v, 2)
    for wid in V.all_weapons():
        w = V.weapon(wid)
        for s in w["skills"]:
            if s["input"] == "LEFT" and s["cooldown"] <= 2.0:
                continue
            c = weapon_coef(s)
            if c > cap:
                v = max(0.1, math.floor(cap / c / round_to + 1e-9) * round_to)
                if v <= only_below + 1e-9:
                    out[wid + ":" + str(s["input"])] = round(v, 2)
    return out
