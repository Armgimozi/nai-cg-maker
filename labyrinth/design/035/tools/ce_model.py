#!/usr/bin/env python3
"""
직업 × 레벨 기대값 모델 (몬테카를로 없이): 기본 공격 DPS · 직업 스킬 DPS · 유효 HP.

  old_player(cls, L)            0.3.4 (주스탯 혼합, 종류 공속, 게이지 꽉 참)
  new_player(cls, L, P, plan)   새 모델 (STR=물리, INT=마법, 무기마다 간격, 스킬 위력)

장비 = 그 레벨에 흔한 장비 (r4 unify.gear_for 와 같은 규칙: 그 레벨 이하 · 깊은 층(6+)은 영웅까지 · 직업 추천 무기 종류 ·
       방어구는 직업 대표 스탯 줄이 있는 것 · 장신구 2개). 새 모델도 같은 물건 (무기 숫자만 새 값).
"""
import math

import ce_core as C

RANK = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5}
LOOK = {"guardian": "VIT", "berserker": "VIT", "hunter": "DEX", "shadow": "DEX", "arcanist": "INT", "priest": "INT"}
STATS = ("STR", "DEX", "INT", "VIT", "WIS", "LUK")
# 0.3.4 분배 (sim.ALLOC 와 같음): 주 스탯 3 : VIT 2
OLD_ALLOC = {"guardian": {"VIT": 3, "STR": 2}, "berserker": {"STR": 3, "VIT": 2}, "hunter": {"DEX": 3, "VIT": 2},
             "arcanist": {"INT": 3, "VIT": 2}, "priest": {"WIS": 3, "VIT": 2}, "shadow": {"DEX": 3, "VIT": 2}}
SKILL_SCALE = {"guardian": 1.00, "berserker": 1.55, "hunter": 1.55, "arcanist": 1.05, "priest": 0.90, "shadow": 0.62}
CASTER_SP_MULT = 1.05
OLD_PLAN = "v2"     # "ratio" = 0.3.4 비율만 (요구치 무시), "v2" = 요구치 채움
NEW_PLAN = "v2"


def points(L):
    return C.CONFIG["level"]["start_points"] + C.CONFIG["level"]["points_per_level"] * (L - 1)


def floor_of_level(L):
    for f, v in sorted(C.FLOORS.items()):
        a, b = v["level_range"]
        if a <= L <= b:
            return f
    return 10


def avg_stats(item_id):
    it = C.ITEMS[item_id]
    return {k: C.mid(v) for k, v in it["stats"].items()}


def gear_for(cls, L, weapon_override=None):
    """그 레벨에 흔한 장비 (무기 1 + 방어구 4 + 장신구 2). 수호기사는 방패도."""
    fl = floor_of_level(L)
    cap = 3 if fl >= 6 else 2
    wt = C.RECOMMENDED[cls]

    def best(pred):
        c = [(v.get("level_req", 1), RANK[v.get("rarity", "common")], k) for k, v in C.ITEMS.items()
             if pred(v) and v.get("level_req", 1) <= L and RANK[v.get("rarity", "common")] <= cap and "stats" in v]
        return max(c)[2] if c else None

    weapon = weapon_override or best(lambda v: v.get("type") == "weapon" and v.get("weapon_type") == wt)
    out = []
    for slot in ("head", "chest", "legs", "feet"):
        g = best(lambda v, slot=slot: v.get("type") == "armor" and v.get("armor_slot") == slot
                 and LOOK[cls] in v.get("stats", {}))
        if g:
            out.append(g)
    if cls == "guardian":
        g = best(lambda v: v.get("type") == "armor" and v.get("armor_slot") == "offhand")
        if g:
            out.append(g)
    accs = sorted([(v.get("level_req", 1), RANK[v.get("rarity")], k) for k, v in C.ITEMS.items()
                   if v.get("type") == "accessory" and v.get("level_req", 1) <= L and RANK[v.get("rarity")] <= cap
                   and "stats" in v], reverse=True)
    out += [a[2] for a in accs[:2]]
    return weapon, out


def sum_bonus(items, weapon_stats):
    b = {}
    for st in [weapon_stats] + [avg_stats(i) for i in items]:
        for k, v in st.items():
            b[k] = b.get(k, 0) + v
    return b


def alloc_ratio(n, ratio):
    """n 점을 ratio 비율로 (5점 묶음 단위 반복, sim.alloc_points 와 같은 순서)."""
    pts = {k: 0 for k in STATS}
    per = sum(ratio.values())
    keys = list(ratio.keys())
    for i in range(n):
        idx = i % per
        acc = 0
        for key in keys:
            acc += ratio[key]
            if idx < acc:
                pts[key] += 1
                break
    return pts


# ───────────────────────────── 공통 파생 능력치 ─────────────────────────────

def derive(cls, L, alloc, bonus, P=None, new=False):
    c = C.CLASSES[cls]
    s = {st: max(0, c["base_stats"].get(st, 0) + alloc.get(st, 0) + round(bonus.get(st, 0))) for st in STATS}
    d = dict(s=s)
    d["max_hp"] = c["base_hp"] + c["per_level"]["hp"] * (L - 1) + s["VIT"] * 8 + bonus.get("hp", 0)
    d["max_mp"] = c["base_mp"] + c["per_level"]["mp"] * (L - 1) + s["INT"] * 3 + s["WIS"] * 2 + bonus.get("mp", 0)
    d["defense"] = s["VIT"] * 0.5 + bonus.get("defense", 0)
    dex_crit = (P or {}).get("dex_crit", 0.0015) if new else 0.0015
    luk_crit = (P or {}).get("luk_crit", 0.0025) if new else 0.0025
    d["crit"] = min(0.75, 0.05 + s["DEX"] * dex_crit + s["LUK"] * luk_crit + bonus.get("crit_chance", 0))
    d["crit_dmg"] = 1.5 + bonus.get("crit_damage", 0)
    dex_speed = (P or {}).get("dex_speed", 0.004) if new else 0.004
    cap = (P or {}).get("cap_speed", 0.60) if new else 0.60
    d["atk_speed"] = max(-0.5, min(cap, s["DEX"] * dex_speed + bonus.get("attack_speed", 0)))
    dex_ev = (P or {}).get("dex_evasion", 0.0) if new else 0.0
    d["evasion"] = max(0.0, min(0.40, s["DEX"] * dex_ev + bonus.get("evasion", 0)))
    d["dr"] = min(0.5, bonus.get("damage_reduction", 0) + (0.10 if cls == "guardian" else 0.0))
    d["block"] = min(0.4, bonus.get("block_chance", 0))
    d["mana_regen"] = c["mana_regen"] + s["WIS"] * 0.05 + bonus.get("mana_regen", 0)
    d["heal_power"] = s["WIS"] * 1.5 + bonus.get("heal_power", 0)
    d["cdr"] = min(0.40, min(0.20, s["INT"] * 0.002) + bonus.get("cooldown_reduction", 0))
    d["skill_dmg"] = bonus.get("skill_damage", 0)
    d["lifesteal"] = min(0.25, bonus.get("lifesteal", 0))
    return d


def ehp(d):
    """유효 HP: HP × (100+방어)/100 ÷ (1−피해 감소) ÷ (1−회피×0.8: 보스 패턴은 회피 불가라 80%만) ÷ 막기(정면 70%·×0.4)."""
    e = d["max_hp"] * (100 + d["defense"]) / 100 / (1 - d["dr"])
    e /= 1 - 0.8 * d["evasion"]
    e /= 1 - 0.7 * d["block"] * 0.6
    return e


def crit_factor(d):
    return 1 + d["crit"] * (d["crit_dmg"] - 1)


# ───────────────────────────── 직업 스킬 (한 대상, 지속) ─────────────────────────────

def skill_list(cls, L):
    """(배율 합, cd, mana, 종류, 이름) — 한 대상에게 들어가는 피해 배율 (공격력·스킬 위력 1 기준)."""
    sk = C.CLASSES[cls]["skills"]
    out = []
    for s in sk:
        if s["unlock_level"] > L:
            continue
        p = s.get("params", {})
        sid = s["id"]
        m = 0.0
        if sid == "shield_bash":
            m = p["damage"]
        elif sid == "spin_slash":
            m = p["damage"] + p["bleed_ratio"] * p["bleed_duration"]
        elif sid == "ground_cleaver":
            m = p["damage"]
        elif sid == "ruinous_leap":
            m = p["damage"]
        elif sid == "piercing_arrow":
            m = p["damage"]
        elif sid == "evasive_trap":
            m = p["trap_damage"] * 0.5     # 밟을 때만
        elif sid == "arrow_storm":
            m = p["damage"] * p["duration"] / p["tick"] * 0.7
        elif sid == "arcane_bolt":
            m = p["damage"]
        elif sid == "frost_nova":
            m = p["damage"]
        elif sid == "phase_blink":
            m = p["echo_damage"] * 0.6
        elif sid == "meteor_fall":
            m = p["damage"] + p["burn_dps"] * p["burn_duration"]
        elif sid == "purifying_wave":
            m = p["damage"]
        elif sid == "shadow_strike":
            m = p["damage"] * 0.75 + p["back_damage"] * 0.25    # 등 뒤 25%
        elif sid == "venom_blades":
            # 8초 동안 5중첩까지 → 평균 3.5중첩 × 0.10 × (8 + 6 남은 지속)
            m = 0.10 * 3.5 * (p["duration"] + p["stack_duration"] * 0.5)
        elif sid == "shadow_execution":
            m = p["damage"] * p["boss_hits"] * 1.15   # 처형 구간 일부
        if m > 0:
            out.append((m, s["cooldown"], s["mana"], sid))
    return out


def skill_dps(cls, L, d, unit, mana_income, cd_mult, fight_s=60.0):
    """스킬 지속 DPS = Σ 배율 × unit ÷ 재사용 — 마나가 모자라면 비율로 줄임. unit = 스킬 1배율 피해(치명·skill_damage 포함)."""
    lst = skill_list(cls, L)
    if not lst:
        return 0.0
    dem = sum(mn / (cd * cd_mult * (1 - d["cdr"])) for _m, cd, mn, _ in lst)
    inc = mana_income + d["max_mp"] / fight_s
    use = 1.0 if dem <= 1e-9 else min(1.0, inc / dem)
    return sum(m * unit / (cd * cd_mult * (1 - d["cdr"])) for m, cd, _mn, _ in lst) * use


def buff_mult(cls, L):
    """직업 버프가 기본 공격에 주는 평균 배율 (광전사 피의 갈망, 사냥꾼 표식)."""
    if cls == "berserker" and L >= 18:
        return 1 + (8 / (24 * 0.9)) * (1.3 * 1.2 - 1)
    if cls == "hunter" and L >= 8:
        return 1 + min(1.0, 10 / (14 * 0.9)) * 0.20
    return 1.0


# ───────────────────────────── OLD ─────────────────────────────

def old_player(cls, L, gauge_eff=1.0):
    wid, items = gear_for(cls, L)
    w = C.WEAPONS[wid]
    wst = {k: C.mid(v) for k, v in w["stats"].items()}
    bonus = sum_bonus(items, wst)
    alloc = alloc_ratio(points(L), OLD_ALLOC[cls]) if OLD_PLAN == "ratio" else plan_v2(cls, L, [wid] + items, "old")[0]
    d = derive(cls, L, alloc, bonus)
    mix = C.primary_mix(cls, d["s"])
    ap = wst["damage"] * (1 + 0.02 * mix)
    wt = w["weapon_type"]
    cf = crit_factor(d)
    if wt == "bow":
        per_s = (C.BOW_FULL_MULT_OLD * (C.KEEN_EYE if cls == "hunter" else 1.0)) / C.BOW_PERIOD_OLD
    else:
        per_s = C.OLD_AS[wt] * (1 + d["atk_speed"])
    basic = ap * per_s * cf * gauge_eff * buff_mult(cls, L)
    # 마나 수입: 회복 + 광전사 적중당 3 · 사냥꾼 끝까지 당김 3
    hits = per_s
    inc = d["mana_regen"] + (3 * hits if cls == "berserker" else 0) + (3 / C.BOW_PERIOD_OLD if cls == "hunter" else 0)
    unit = ap * cf * (1 + d["skill_dmg"])
    sk = skill_dps(cls, L, d, unit, inc, 0.9)
    return dict(cls=cls, L=L, weapon=wid, wtype=wt, stats=d["s"], ap=ap, basic=basic, skill=sk, dps=basic + sk,
                ehp=ehp(d), hp=d["max_hp"], mp=d["max_mp"], heal_power=d["heal_power"], crit=d["crit"],
                speed=d["atk_speed"], d=d)


# ───────────────────────────── NEW ─────────────────────────────

def weapon_kind(wid):
    """기본 공격 피해 종류: 근접·원거리 = 물리, 시전 = 마법 (무기 attack.kind 로 바꿀 수 있음)."""
    st = C.style_of(C.weapon_shape(wid))
    return "magic" if st == "caster" else "physical"


CLASS_SKILL_KIND = {"guardian": "physical", "berserker": "physical", "hunter": "physical", "arcanist": "magic",
                    "priest": "magic", "shadow": "physical"}


def plan_alloc(cls, L, wid, plan, P):
    """새 분배. plan:
       'old'      = 0.3.4 비율 그대로 (초기화 안 한 사람)
       'sensible' = 무기 요구 능력치를 채우고(직업 기본 포함), VIT 는 0.3.4 와 같은 개수, 나머지 = 피해 스탯
                    (사제: WIS 요구 + VIT 같게 + 나머지 INT 와 WIS 반반, 수호기사: VIT 같게 + 나머지 STR)
       dict       = 직접 비율"""
    n = points(L)
    if plan == "old":
        return alloc_ratio(n, OLD_ALLOC[cls])
    if isinstance(plan, dict):
        return alloc_ratio(n, plan)
    base = C.CLASSES[cls]["base_stats"]
    old = alloc_ratio(n, OLD_ALLOC[cls])
    a = {k: 0 for k in STATS}
    a["VIT"] = old["VIT"]
    req = C.requires_of(wid)
    if "any" in req:
        req = dict([next(iter(req["any"].items()))])
    req = C.split_requires(dict(req), C.WEAPONS[wid]["level_req"] if wid in C.WEAPONS else C.NEW_WEAPONS[wid]["level_req"],
                           weapon_kind(wid))
    for st, v in req.items():
        a[st] = max(a[st], v - base.get(st, 0))
    dmg_stat = "INT" if CLASS_SKILL_KIND[cls] == "magic" or weapon_kind(wid) == "magic" else "STR"
    left = n - sum(a.values())
    if left < 0:     # 요구치가 VIT 몫을 먹는 경우 — VIT 를 줄인다
        a["VIT"] += left
        left = 0
    if cls == "priest":
        # 사제: WIS 는 max(요구치, 포인트의 40%) — 치유력을 지키고, 나머지 INT (피해)
        want = int(0.4 * n) - base.get("WIS", 0)
        if a["WIS"] < want and left > 0:
            mv = min(left, want - a["WIS"])
            a["WIS"] += mv
            left -= mv
        a["INT"] += left
    elif plan == "sensible_dex" and cls in ("hunter", "shadow"):
        a["DEX"] += left // 3
        a[dmg_stat] += left - left // 3
    else:
        a[dmg_stat] += left
    return a


def new_player(cls, L, P=None, plan="sensible", wid=None, gauge_eff=1.0, alloc=None):
    P = P or C.P_DEFAULT
    wid0, items = gear_for(cls, L)
    wid = wid or wid0
    if wid in C.WEAPONS:
        w = C.WEAPONS[wid]
        ph = C.new_per_hit(wid, P)
    else:
        w = C.NEW_WEAPONS[wid]
        ph = C.new_per_hit_newweapon(wid, P)
    wst = {k: C.mid(v) for k, v in w["stats"].items()}
    # gear_spec 의 주 스탯 줄 이름 바꿈(STR→VIT 등)
    ren = C.EXISTING_CHANGES.get(wid, {}).get("stats_rename", {}) if C.USE_GEAR_REQUIRES else {}
    for a_, b_ in ren.items():
        if a_ in wst:
            wst[b_] = wst.pop(a_)
    wst["damage"] = C.mid(ph)
    bonus = sum_bonus(items, wst)
    if alloc is None:
        alloc = plan_alloc(cls, L, wid, plan, P) if NEW_PLAN == "v1" else plan_v2(cls, L, [wid] + items, "new", P)[0]
    d = derive(cls, L, alloc, bonus, P, new=True)
    if cls == "shadow":
        d["crit_dmg"] += P.get("shadow_crit_dmg", 0.0)
        d["atk_speed"] = min(P.get("cap_speed", 0.6), d["atk_speed"] + P.get("shadow_speed", 0.0))
    if cls == "priest":
        d["magic_bonus"] = P.get("priest_magic", 0.0)
    s = d["s"]
    kind = weapon_kind(wid)
    k_of = {"physical": P["k_phys"] * s["STR"], "magic": P["k_mag"] * s["INT"]}
    ap_basic = wst["damage"] * (1 + k_of[kind])
    style = C.style_of(C.weapon_shape(wid))
    iv = C.interval_of(wid)
    cf = crit_factor(d)
    spd = 1 + d["atk_speed"]
    if style == "ranged":
        draw = (iv - C.BOW_NOCK) / spd
        period = max(C.MIN_INTERVAL, draw + C.BOW_NOCK)
        per_s = (P["keen_eye"] if cls == "hunter" else 1.0) / period
    else:
        period = max(C.MIN_INTERVAL, iv / spd)
        per_s = 1.0 / period
    mb = 1 + (d.get("magic_bonus", 0.0) if kind == "magic" else 0.0)
    basic = ap_basic * per_s * cf * gauge_eff * buff_mult(cls, L) * mb
    # 스킬 위력
    sp = C.skill_power(wst["damage"], iv, style, CASTER_SP_MULT if style == "caster" else 1.0) * \
        (1 + P.get("sp_speed", 0.0) * max(0.0, d["atk_speed"]))
    skind = CLASS_SKILL_KIND[cls]
    unit = sp * SKILL_SCALE[cls] * (1 + k_of[skind]) * cf * (1 + d["skill_dmg"]) * (1 + (d.get("magic_bonus", 0.0) if skind == "magic" else 0.0))
    hits = per_s
    inc = d["mana_regen"] + (3 * hits if cls == "berserker" else 0) + (3 * per_s / P["keen_eye"] if cls == "hunter" and style == "ranged" else 0)
    sk = skill_dps(cls, L, d, unit, inc, 0.9)
    return dict(cls=cls, L=L, weapon=wid, style=style, kind=kind, interval=iv, per_hit=ph, stats=s, alloc=alloc,
                ap=ap_basic, sp=sp, basic=basic, skill=sk, dps=basic + sk, ehp=ehp(d), hp=d["max_hp"], mp=d["max_mp"],
                heal_power=d["heal_power"], crit=d["crit"], speed=d["atk_speed"], d=d)


if __name__ == "__main__":
    import sys
    P = dict(C.P_DEFAULT)
    for a in sys.argv[1:]:
        k, v = a.split("=")
        P[k] = float(v)
    print("P:", {k: v for k, v in P.items() if not callable(v)})
    for L in (1, 10, 25, 45):
        for cls in C.CLASSES:
            o = old_player(cls, L)
            n = new_player(cls, L, P)
            print(f"L{L:<2} {cls:9} {o['weapon']:24} old dps {o['dps']:7.1f} (b {o['basic']:6.1f} s {o['skill']:6.1f}) ehp {o['ehp']:7.0f}"
                  f" | new dps {n['dps']:7.1f} (b {n['basic']:6.1f} s {n['skill']:6.1f}) ehp {n['ehp']:7.0f}"
                  f" | dps {n['dps']/o['dps']-1:+.0%} ehp {n['ehp']/o['ehp']-1:+.0%}  alloc {dict((k,v) for k,v in n['alloc'].items() if v)}")


# ───────────────────────────── 분배 v2: 무기·방어구 요구 능력치를 모두 채운다 ─────────────────────────────
# 0.3.4 규칙: 판금 VIT · 가죽 DEX · 천 INT|WIS · 방패 VIT, 무기는 종류 스탯 — 요구치 = ceil(2.5(L−1)) (L = 아이템 레벨).
# 요구치를 먼저 채우고, 남은 포인트는 '목표 비율'에 모자란 스탯부터 채운다(물 채우기).
TARGET_OLD = {"guardian": {"VIT": 3, "STR": 2}, "berserker": {"STR": 3, "VIT": 2}, "hunter": {"DEX": 3, "VIT": 2},
              "arcanist": {"INT": 3, "VIT": 2}, "priest": {"WIS": 3, "VIT": 2}, "shadow": {"DEX": 3, "VIT": 2}}
TARGET_NEW = {"guardian": {"VIT": 3, "STR": 2}, "berserker": {"STR": 3, "VIT": 2},
              "hunter": {"DEX": 2.0, "STR": 1.3, "VIT": 1.7}, "arcanist": {"INT": 3, "VIT": 2},
              "priest": {"WIS": 2.5, "INT": 0.55, "VIT": 1.95}, "shadow": {"DEX": 2.0, "STR": 1.4, "VIT": 1.6}}
ANY_PREF = {"guardian": ["VIT", "STR"], "berserker": ["STR", "VIT"], "hunter": ["DEX", "STR"], "arcanist": ["INT", "WIS"],
            "priest": ["WIS", "INT"], "shadow": ["DEX", "STR"]}


def item_requirements(cls, item_id, model, P=None):
    it = C.ITEMS.get(item_id) or C.NEW_WEAPONS.get(item_id)
    out = {}
    if it.get("type") == "weapon":
        req = C.requires_of(item_id) if model == "new" else (it.get("requires") or {})
        if "any" in req:
            opts = req["any"]
            st = next((s for s in ANY_PREF[cls] if s in opts), next(iter(opts)))
            req = {st: opts[st]}
        if model == "new":
            req = C.split_requires(dict(req), it.get("level_req", 1), weapon_kind(item_id))
        out.update(req)
        return out
    r = it.get("requires") or {}
    out.update(r)
    ra = it.get("requires_any") or {}
    if ra:
        st = next((s for s in ANY_PREF[cls] if s in ra), next(iter(ra)))
        out[st] = max(out.get(st, 0), ra[st])
    return out


def plan_v2(cls, L, items, model, P=None, target=None):
    n = points(L)
    base = C.CLASSES[cls]["base_stats"]
    need = {}
    for i in items:
        for st, v in item_requirements(cls, i, model, P).items():
            need[st] = max(need.get(st, 0), v)
    a = {k: max(0, need.get(k, 0) - base.get(k, 0)) for k in STATS}
    left = n - sum(a.values())
    tgt = target or (TARGET_NEW if model == "new" else TARGET_OLD)[cls]
    tot = sum(tgt.values())
    want = {k: n * tgt.get(k, 0) / tot for k in STATS}
    while left > 0:
        k = max(STATS, key=lambda s: (want[s] - a[s]) if want[s] > 0 else -1e9)
        a[k] += 1
        left -= 1
    return a, left
