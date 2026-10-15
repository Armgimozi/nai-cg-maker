#!/usr/bin/env python3
"""
TASK P — PvP 빌드 (직업 6 × Lv20·35·50 × 두 갈래) — 새 전투 모델(combat_spec) + 겉모습 효과(TASK B 안) 그대로.

  burst  '유리 대포'  : 가죽(물리) 또는 천(마법) 4부위, 남은 포인트 = 피해 스탯 3 : DEX 1.4 : VIT 0.6 (마법은 INT 위주)
  guard  '수비'       : 판금 4부위 + 방패, 남은 포인트 = VIT 3 : 피해 스탯 2 (사제는 VIT·WIS·INT)

  둘 다 무기·방어구 요구 능력치를 먼저 채운다(요구치는 gear_spec 새 값). 무기는 직업이 쓰는 공격 방식 안에서
  그 레벨에 들 수 있는 가장 센 것(스킬 위력 기준) — 수비 빌드는 VIT·HP·피해 감소 줄이 있는 무기를 먼저 고른다.
  등급 상한: Lv20 영웅 · Lv35 전설 · Lv50 전설 (신화는 따로 보지 않는다 — 한 사람만 가지는 물건).
"""
import math

import pv_core as V

LK = V.LK
LEVELS = (20, 35, 50)
CAP = {5: 2, 10: 2, 20: 3, 35: 4, 50: 4}
POINTS = lambda L: V.CONFIG["level"]["start_points"] + V.CONFIG["level"]["points_per_level"] * (L - 1)  # noqa: E731

# 직업이 기본으로 쓰는 공격 방식 (무기 종류는 없다 — 공격 방식·간격으로만 고른다)
STYLE = {"guardian": ("melee", 0.55, 0.80), "berserker": ("melee", 0.85, 1.30), "hunter": ("ranged", 0, 9),
         "arcanist": ("caster", 0.84, 1.30), "priest": ("caster", 0.0, 0.86), "shadow": ("melee", 0.0, 0.52)}
DMG_STAT = {"guardian": "STR", "berserker": "STR", "hunter": "STR", "arcanist": "INT", "priest": "INT", "shadow": "STR"}
TARGET = {
    "burst": {"guardian": {"STR": 3, "DEX": 1.4, "VIT": 0.6}, "berserker": {"STR": 3, "DEX": 1.4, "VIT": 0.6},
              "hunter": {"STR": 3, "DEX": 1.4, "VIT": 0.6}, "shadow": {"STR": 3, "DEX": 1.4, "VIT": 0.6},
              "arcanist": {"INT": 3.6, "DEX": 0.6, "VIT": 0.6}, "priest": {"INT": 2.6, "WIS": 1.2, "DEX": 0.4, "VIT": 0.6}},
    "guard": {"guardian": {"VIT": 3, "STR": 2}, "berserker": {"VIT": 3, "STR": 2}, "hunter": {"VIT": 3, "STR": 1.6, "DEX": 0.4},
              "shadow": {"VIT": 3, "STR": 1.6, "DEX": 0.4}, "arcanist": {"VIT": 3, "INT": 2},
              "priest": {"VIT": 2.6, "WIS": 1.4, "INT": 1.0}},
}
LOOK = {"burst": {"guardian": "light", "berserker": "light", "hunter": "light", "shadow": "light", "arcanist": "cloth",
                  "priest": "cloth"},
        "guard": {c: "heavy" for c in V.CLASS_ORDER}}
# 장신구 두 칸 (앞이 먼저) — 그 레벨·등급 상한 안에서 첫 두 개
ACC_PREF = {
    "burst_phys": ["slayer_fang_amulet", "abyssal_eye_amulet", "mainspring_bracelet", "anvil_king_brand", "ember_heart_amulet",
                   "pioneer_signet", "brine_pearl_ring", "silk_queen_bracelet", "miners_lucky_charm", "moss_band"],
    "burst_magic": ["abyssal_eye_amulet", "dyad_twin_orb", "orbel_quill_charm", "resonance_ring", "empress_frozen_tear",
                    "floodwarden_signet", "pioneer_signet", "sporelight_amulet", "moss_band"],
    "guard": ["master_smith_charm", "anvil_king_brand", "mourning_bell_charm", "lone_star_ring", "symbiosis_ring",
              "pioneer_signet", "grove_heartwood_charm", "moss_band"],
}
DEF_LINES = ("VIT", "hp", "damage_reduction", "defense", "block_chance", "hp_regen")


def _ok(item, L, cap):
    return item.get("level_req", 1) <= L and V.RANK.get(item.get("rarity", "common"), 0) <= cap


def _requires_item(iid):
    it = LK.ALL_ITEMS.get(iid) or {}
    ch = V.GEAR["armor_changes"].get(iid)
    if ch is not None and "requires" in ch:
        return dict(ch["requires"] or {})
    return dict(it.get("requires") or {})


def choose_weapon(cls, L, kind, cap):
    style, lo, hi = STYLE[cls]
    cands = []
    for wid in V.all_weapons():
        c = V.CW[wid]
        if c["style"] != style or not (lo <= c["interval"] <= hi):
            continue
        if c["level"] > L or V.RANK[c["rarity"]] > cap:
            continue
        w = V.weapon(wid)
        defl = sum(1 for k in w["stats"] if k in DEF_LINES)
        nsk = len(w["skills"])
        score = c["skill_power"] * (1 + 0.04 * nsk)
        if kind == "guard":
            score *= 1 + 0.06 * defl
        cands.append((score, wid))
    cands.sort(reverse=True)
    return cands[0][1]


def choose_armor(look, L, cap):
    out = {}
    for slot in ("head", "chest", "legs", "feet"):
        best = None
        for k, v in LK.ALL_ITEMS.items():
            if v.get("type") != "armor" or v.get("armor_slot") != slot or not _ok(v, L, cap) or "stats" not in v:
                continue
            if LK.look_of(k) != look:
                continue
            key = (v.get("level_req", 1), V.RANK[v.get("rarity", "common")], k)
            if best is None or key > best:
                best = key
        if best:
            out[slot] = best[2]
    return out


def choose_shield(L, cap):
    best = None
    for k, v in LK.ALL_ITEMS.items():
        if v.get("type") == "armor" and v.get("armor_slot") == "offhand" and _ok(v, L, cap) and "stats" in v:
            key = (v.get("level_req", 1), V.RANK[v.get("rarity", "common")], k)
            if best is None or key > best:
                best = key
    return best[2] if best else None


def choose_acc(pref, L, cap):
    out = []
    for iid in ACC_PREF[pref]:
        it = V.ITEMS.get(iid)
        if it and _ok(it, L, cap):
            out.append(iid)
        if len(out) == 2:
            break
    return out


def set_bonus(pieces):
    by = {}
    for iid in pieces:
        it = LK.ALL_ITEMS.get(iid) or {}
        sid = it.get("set_bonus") or it.get("armor_set")
        if sid:
            by[sid] = by.get(sid, 0) + 1
    out = {}
    for sid, n in by.items():
        s = LK.ALL_SETS.get(sid)
        if not s:
            continue
        for need, b in (s.get("bonuses") or {}).items():
            if n >= int(need):
                for k, v in b.items():
                    out[k] = out.get(k, 0) + V.mid(v)
    return out


def alloc(cls, L, need, target):
    n = POINTS(L)
    base = V.CLASSES[cls]["base_stats"]
    a = {k: max(0, need.get(k, 0) - base.get(k, 0)) for k in V.STATS}
    left = n - sum(a.values())
    tot = sum(target.values())
    want = {k: n * target.get(k, 0) / tot for k in V.STATS}
    while left > 0:
        k = max(V.STATS, key=lambda s: (want[s] - a[s]) if want[s] > 0 else -1e9)
        a[k] += 1
        left -= 1
    return a, left


def build(cls, L, kind):
    cap = CAP[L]
    wid = choose_weapon(cls, L, kind, cap)
    w = V.weapon(wid)
    look = LOOK[kind][cls]
    armor = choose_armor(look, L, cap)
    shield = choose_shield(L, cap) if kind == "guard" else None
    pref = "guard" if kind == "guard" else ("burst_magic" if DMG_STAT[cls] == "INT" else "burst_phys")
    accs = choose_acc(pref, L, cap)
    pieces = list(armor.values()) + ([shield] if shield else [])
    # 요구 능력치 (스탯마다 가장 큰 값)
    need = {}
    wreq = dict(w["requires"])
    if "any" in wreq:
        opts = wreq["any"]
        st = DMG_STAT[cls] if DMG_STAT[cls] in opts else next(iter(opts))
        wreq = {st: opts[st]}
    for st, v in wreq.items():
        need[st] = max(need.get(st, 0), v)
    for iid in pieces + accs:
        for st, v in _requires_item(iid).items():
            need[st] = max(need.get(st, 0), v)
    a, left = alloc(cls, L, need, TARGET[kind][cls])
    # 장비 줄 합
    bonus = {}

    def add(st):
        for k, v in st.items():
            bonus[k] = bonus.get(k, 0) + V.mid(v)

    wst = {k: v for k, v in w["stats"].items() if k != "damage"}
    add(wst)
    for iid in pieces + accs:
        add(LK.ALL_ITEMS[iid].get("stats", {}))
    add(set_bonus(pieces))
    # 겉모습 숨은 효과 (부위마다) + 4부위
    counts = {}
    for iid in pieces:
        lk = LK.look_of(iid)
        counts[lk] = counts.get(lk, 0) + 1
    lt = LK.look_totals(counts)
    full = None
    for lk in ("heavy", "light", "cloth"):
        n4 = sum(1 for s in ("head", "chest", "legs", "feet") if s in armor and LK.look_of(armor[s]) == lk)
        if n4 >= 4:
            full = lk
    d = derive(cls, L, a, bonus, lt, full, w)
    d.update(cls=cls, L=L, kind=kind, weapon=wid, weapon_name=w["name"], armor=armor, shield=shield, accs=accs, look=look,
             full=full, alloc=a, need=need, left=left, w=w)
    return d


def derive(cls, L, a, bonus, lt, full, w):
    c = V.CLASSES[cls]
    s = {st: max(0, c["base_stats"].get(st, 0) + a.get(st, 0) + round(bonus.get(st, 0))) for st in V.STATS}
    d = dict(s=s)
    hp = c["base_hp"] + c["per_level"]["hp"] * (L - 1) + s["VIT"] * 8 + bonus.get("hp", 0)
    d["max_hp"] = hp * (1 + lt.get("hp_pct", 0))
    d["max_mp"] = c["base_mp"] + c["per_level"]["mp"] * (L - 1) + s["INT"] * 3 + s["WIS"] * 2 + bonus.get("mp", 0)
    d["defense"] = max(0, s["VIT"] * 0.5 + bonus.get("defense", 0)) * (1 + lt.get("defense_pct", 0))
    d["crit"] = min(0.75, 0.05 + 0.0025 * s["DEX"] + 0.0025 * s["LUK"] + bonus.get("crit_chance", 0) + lt.get("crit_chance", 0))
    d["crit_dmg"] = 1.5 + bonus.get("crit_damage", 0) + (V.CLASS_VALUES["vital_point_crit_damage"] if cls == "shadow" else 0)
    d["atk_speed"] = max(-0.5, min(0.6, 0.005 * s["DEX"] + bonus.get("attack_speed", 0) + lt.get("attack_speed", 0)))
    d["evasion"] = max(0.0, min(0.40, 0.001 * s["DEX"] + bonus.get("evasion", 0) + lt.get("evasion", 0)))
    d["dr"] = min(0.5, bonus.get("damage_reduction", 0) + lt.get("damage_reduction", 0) + (0.10 if cls == "guardian" else 0))
    d["block"] = min(0.4, bonus.get("block_chance", 0))
    d["mana_regen"] = (c["mana_regen"] + s["WIS"] * 0.05 + bonus.get("mana_regen", 0)) * (1 + lt.get("mana_regen_pct", 0))
    d["heal_power"] = s["WIS"] * 1.5 + bonus.get("heal_power", 0)
    d["cdr"] = min(0.40, min(0.20, s["INT"] * 0.002) + bonus.get("cooldown_reduction", 0))
    d["cd_look"] = 1 + lt.get("cooldown_pct", 0)
    d["skill_dmg"] = bonus.get("skill_damage", 0) + lt.get("skill_damage", 0)
    d["lifesteal"] = min(0.25, bonus.get("lifesteal", 0))
    d["hp_regen"] = bonus.get("hp_regen", 0)
    d["debuff_red"] = min(0.30, s["WIS"] * 0.005)
    d["move_speed"] = max(-0.6, min(0.3, bonus.get("move_speed", 0) + lt.get("move_speed", 0)))
    d["kb_resist"] = min(0.5, s["STR"] * 0.003)
    # 무기
    W = V.mid(w["per_hit"])
    kind = w["kind"]
    power = {"physical": 1 + 0.01 * s["STR"], "magic": 1 + 0.01 * s["INT"]}
    d["power"] = power
    d["W"] = W
    d["ap"] = W * power[kind]
    iv = w["interval"]
    spd = 1 + d["atk_speed"]
    if w["style"] == "ranged":
        draw = max(0.25, (iv - 0.15) / spd)
        d["period"] = draw + 0.15
    else:
        d["period"] = max(0.25, iv / spd)
    d["sp"] = w["sp"] * (1 + 0.5 * d["atk_speed"])
    skind = V.CLASS_SKILL_KIND[cls]
    d["class_unit"] = d["sp"] * V.SKILL_SCALE[cls] * power[skind] * (1 + (0.10 if cls == "priest" else 0))
    d["full"] = full
    return d


def all_builds():
    return {(c, L, k): build(c, L, k) for L in LEVELS for c in V.CLASS_ORDER for k in ("burst", "guard")}


if __name__ == "__main__":
    for L in LEVELS:
        for c in V.CLASS_ORDER:
            for k in ("burst", "guard"):
                b = build(c, L, k)
                s = b["s"]
                print(f"L{L} {c:9} {k:5} {b['weapon']:26} {b['look']:5} full={b['full']} left={b['left']:3} hp {b['max_hp']:6.0f} def {b['defense']:5.0f} "
                      f"dr {b['dr']:.2f} ev {b['evasion']:.2f} blk {b['block']:.2f} crit {b['crit']:.2f}/{b['crit_dmg']:.2f} as {b['atk_speed']:.2f} "
                      f"ap {b['ap']:6.1f} per {b['period']:.2f} sp {b['sp']:6.1f} STR{s['STR']} DEX{s['DEX']} INT{s['INT']} VIT{s['VIT']} WIS{s['WIS']}")
