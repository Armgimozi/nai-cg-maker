#!/usr/bin/env python3
"""
TASK P — PvP 밸런스: 공통 데이터 (읽기 전용).

  repo yml (items/classes/config) + design2/combat_spec.json(무기 237개 한 방·간격·스킬 위력·계수)
  + gear_spec.json(새 무기 106 · 기존 무기 바꿈 · 방어구 요구치 · 새 방어구 6세트) + unique_spec.json(기존 무기 고유 효과)
  + lk_core(겉모습 효과: 판금·가죽·천, TASK B 안).

  weapon(wid)        무기 하나를 새 모델로 합친 dict (style·kind·interval·per_hit·sp·stats·requires·skills·unique)
  parse_skill(ws)    무기 스킬 하나 → 피해 배율(한 대상)·최대 HP 비율 피해·상태이상(CC) 목록·자기 버프
  CLASS_KIT          직업 스킬 24개를 PvP 시뮬레이터가 쓰는 꼴로
"""
import json
import math
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
REPO = "/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources"


def _load(p):
    with open(os.path.join(REPO, p), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _j(name):
    with open(os.path.join(D2, name), encoding="utf-8") as f:
        return json.load(f)


_items = _load("content/items.yml")
ITEMS = _items["items"]
CLASSES = _load("content/classes.yml")["classes"]
CONFIG = _load("config.yml")
COMBAT = _j("combat_spec.json")
GEAR = _j("gear_spec.json")
UNIQUE = _j("unique_spec.json")

import lk_core as LK  # noqa: E402  (겉모습 효과 · look_of · 새 방어구 포함 ALL_ITEMS)

RANK = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5}
STATS = ("STR", "DEX", "INT", "VIT", "WIS", "LUK")
CONST = COMBAT["formulas"]["constants"]
CLASS_VALUES = COMBAT["formulas"]["class_values"]
SKILL_SCALE = CLASS_VALUES["skill_scale"]
COOLDOWN_MULT = CLASS_VALUES["cooldown_mult"]          # 0.9 (옛 추천 무기 −10% 를 모든 직업 스킬에)


def mid(r):
    return (r[0] + r[1]) / 2 if isinstance(r, (list, tuple)) else float(r)


def K_style(style, interval):
    if style == "ranged":
        return 1.413
    if style == "caster":
        return 1.22
    return 1.47 - 0.143 * max(0.0, 1.0 / interval - 1.5)


# ───────────────────────────── 무기 (새 모델) ─────────────────────────────
CW = COMBAT["weapons"]


def weapon(wid):
    c = CW[wid]
    if c["src"] == "existing":
        base = ITEMS[wid]
        ch = GEAR["existing_changes"].get(wid, {})
        stats = {k: v for k, v in base.get("stats", {}).items()}
        for a, b in (ch.get("stats_rename") or {}).items():
            if a in stats:
                stats[b] = stats.pop(a)
        req = ch.get("requires") if "requires" in ch else (base.get("requires") or {})
        if ch.get("requires_any"):
            req = {"any": ch["requires_any"]}
        skills = base.get("weapon_skills") or []
        factor = c.get("weapon_skill_factor") or 1.0
        ua = UNIQUE["assignments"].get(wid)
        unique = dict(id=ua["effect"], name=ua["name"], **ua["params"]) if ua else None
        name = base["name"]
        lore = base.get("lore", "")
    else:
        g = GEAR["weapons"][wid]
        stats = dict(g["stats"])
        req = g.get("requires") or {}
        if g.get("requires_any"):
            req = {"any": g["requires_any"]}
        skills = g.get("weapon_skills") or []
        factor = 1.0          # gear_spec 새 무기의 스킬 숫자는 이미 계수를 곱했다
        unique = g.get("unique")
        name = g["name"]
        lore = g.get("lore", "")
    stats = dict(stats)
    stats["damage"] = list(c["per_hit"])
    return dict(id=wid, name=name, style=c["style"], kind=c["kind"], interval=c["interval"], level=c["level"],
                rarity=c["rarity"], per_hit=c["per_hit"], sp=c["skill_power"], stats=stats, requires=req,
                skills=[parse_skill(s, factor, c["style"], c["kind"]) for s in skills], unique=unique, lore=lore,
                shape=c["shape"])


def all_weapons():
    return list(CW.keys())


# ───────────────────────────── 무기 스킬 파싱 ─────────────────────────────
# 한 대상(움직이는 플레이어)에게 들어가는 기대 피해 배율. 맞을 확률은 모양에 따라 (플레이어는 몹보다 잘 피한다).
HIT = dict(cone=0.85, nova=0.85, dash=0.85, leap=0.8, target=0.95, chain=0.9, projectile=0.8, strike=0.6, beam=0.6,
           zone=0.45, rain=0.45, vortex=0.8, orbit=0.5, summon=0.5, blink=0.85, self=1.0, party=1.0)
CC_IDS = ("stun", "root", "freeze", "silence", "blind", "slow", "knockback", "pull", "launch", "taunt", "glow",
          "cooldown_slow", "weaken", "vulnerable", "mark", "frost", "frozen")


def _eff_list(effs):
    """[{"damage": 1.6}, {"slow": 2}, …] → [(type, value, params)]."""
    out = []
    for e in effs or []:
        if not isinstance(e, dict) or not e:
            continue
        (t, v), = list(e.items())[:1]
        params = {}
        if isinstance(v, dict):
            params = dict(v)
            amt = v.get("amount", v.get("seconds"))
        else:
            amt = v
        out.append((t, amt, params))
    return out


def _part_hits(part):
    """한 부품이 같은 대상을 몇 번 때리나 (기대값, 맞을 확률 포함)."""
    t = part.get("type")
    base = HIT.get(t, 0.8)
    if t == "rain" and "count" in part:
        n = int(part.get("count", 6))
        r = float(part.get("radius", 4))
        ir = float(part.get("impact_radius", 1.5))
        return n * min(0.9, 1.5 * (ir / max(ir, r)) ** 2)
    if t == "strike" and not part.get("targets"):
        n = int(part.get("count", 1))
        r = float(part.get("radius", 0) or 0)
        ir = float(part.get("impact_radius", 1.5))
        return n * (base if r <= ir else min(0.9, 1.5 * (ir / r) ** 2))
    if t in ("zone", "rain"):
        dur = float(part.get("duration", 4))
        iv = max(1, int(part.get("interval", 10)))
        return base * dur * 20 / iv
    if t == "beam":
        if "duration" not in part:
            return base
        dur = float(part.get("duration", 2))
        iv = max(1, int(part.get("interval", 5)))
        return base * dur * 20 / iv
    if t == "vortex":
        dur = float(part.get("duration", 2))
        iv = max(1, int(part.get("interval", 10)))
        return base * dur * 20 / iv * 0.6
    if t in ("orbit", "summon"):
        dur = float(part.get("duration", 5))
        iv = max(1, int(part.get("interval", 20)))
        return base * dur * 20 / iv
    if t == "strike":
        n = int(part.get("count", 1))
        return n * (0.75 if part.get("targets") else base)
    if t == "projectile":
        n = int(part.get("count", 1))
        return base * (1 + (n - 1) * 0.25)
    if t == "repeat":
        return int(part.get("count", 3))
    return base


def _walk(parts, acc, scale=1.0, depth=0):
    for part in parts or []:
        if not isinstance(part, dict):
            continue
        t = part.get("type")
        hits = _part_hits(part) * scale
        rep = 1
        if t == "repeat":
            _walk(part.get("mechanics"), acc, scale * int(part.get("count", 3)), depth + 1)
            continue
        if t == "delay":
            _walk(part.get("mechanics"), acc, scale, depth + 1)
            continue
        for (et, amt, prm) in _eff_list(part.get("effects")):
            _effect(et, amt, prm, hits, part, acc)
        for (et, amt, prm) in _eff_list(part.get("ally_effects")):
            if et in ("heal",):
                acc["ally_heal"] += float(amt or 0.1) * min(hits, 6)
        ex = part.get("explode")
        if isinstance(ex, dict):
            for (et, amt, prm) in _eff_list(ex.get("effects")):
                _effect(et, amt, prm, 0.7 * scale, dict(type="nova", radius=ex.get("radius", 2)), acc)
        for key in ("land", "end", "on_end", "on_impact", "mechanics"):
            if part.get(key):
                _walk(part.get(key), acc, scale * (0.85 if key == "on_impact" else 1.0), depth + 1)
        if t == "self":
            for (et, amt, prm) in _eff_list(part.get("effects")):
                if et == "absorption":
                    acc["self_shield"] += float(prm.get("amount", amt or 0.1))
                elif et == "buff":
                    acc["self_buff"].update({k: v for k, v in prm.items() if k not in ("seconds", "duration")})
                elif et in ("heal", "heal_caster"):
                    acc["self_heal"] += float(amt or 0.05)


def _effect(et, amt, prm, hits, part, acc):
    if et == "damage":
        v = float(amt if amt is not None else 1.0)
        acc["damage"] += v * hits
        dt = prm.get("damage_type")
        if prm.get("magic") or dt == "magic":
            acc["kinds"].add("magic")
        elif dt in ("melee", "ranged"):
            acc["kinds"].add("physical")
        else:
            acc["kinds"].add("default")
    elif et == "lightning":
        acc["damage"] += float(amt or 0) * hits
        acc["kinds"].add("magic")
    elif et == "explosion":
        acc["damage"] += float(prm.get("damage", amt or 0) or 0) * hits
    elif et == "execute":
        acc["execute"] += float(prm.get("amount", amt or 2.0)) * min(1.0, hits)
    elif et == "percent":
        acc["percent"] += float(amt or 0.05) * hits
    elif et == "lifesteal":
        acc["lifesteal"] = max(acc["lifesteal"], float(amt or 0.2))
    elif et in ("ignite", "poison", "bleed", "wither"):
        acc["dot"].append((et, float(amt or (3 if et == "ignite" else 4)), float(prm.get("potency", 0) or 0)))
    elif et == "freeze":
        st = int(prm.get("stacks", 1) or 1)
        acc["cc"].append(dict(id="frost", seconds=float(amt if amt is not None else 3), stacks=st, part=part.get("type"),
                              repeats=round(hits / HIT.get(part.get("type"), 0.8), 1)))
    elif et in ("stun", "root", "slow", "knockback", "pull", "launch", "taunt", "glow"):
        sec = float(amt) if amt is not None else {"stun": 1, "root": 1.5, "slow": 2, "knockback": 0.8, "pull": 0.8,
                                                   "launch": 0.6, "taunt": 3, "glow": 4}[et]
        pot = prm.get("potency")
        if et == "slow" and pot is None:
            pot = 0.35
        acc["cc"].append(dict(id={"glow": "mark"}.get(et, et), seconds=sec, potency=pot, part=part.get("type"),
                              repeats=round(hits / HIT.get(part.get("type"), 0.8), 1)))
    elif et == "effect":
        i = prm.get("id", "weaken")
        acc["cc"].append(dict(id=i, seconds=float(prm.get("seconds", amt or 3)), potency=prm.get("potency"),
                              part=part.get("type"), repeats=round(hits / HIT.get(part.get("type"), 0.8), 1)))
    elif et == "absorption":
        acc["self_shield"] += float(prm.get("amount", amt or 0.1))
    elif et in ("heal_caster",):
        acc["self_heal"] += float(amt or 0.05)


LEGACY_DAMAGE = {
    # 옛 구현(params) 기본값: 한 대상 기대 피해 배율 (게이지 기준 숫자, 계수 곱하기 전)
    "riposte": lambda p: 0.8 * float(p.get("counter_damage", 1.2)) * (1 + 2 * float(p.get("per_block", 0.2))),
    "missile": lambda p: 0.8 * float(p.get("damage", 1.0)) * (1 + 0.25 * (int(p.get("count", 1)) - 1)),
    "slash_wave": lambda p: 0.85 * float(p.get("damage", 1.0)),
    "shadow_step": lambda p: 0.95 * float(p.get("damage", 1.5)),
    "sanctuary": lambda p: 0.45 * float(p.get("damage", 0.0)) * float(p.get("duration", 6)) / float(p.get("tick", 1.0)),
    "mend": lambda p: 0.0,
    "empower": lambda p: 0.0,
}


def parse_skill(ws, factor, style, kind):
    acc = dict(damage=0.0, percent=0.0, execute=0.0, lifesteal=0.0, dot=[], cc=[], kinds=set(), self_shield=0.0,
               self_buff={}, self_heal=0.0, ally_heal=0.0)
    impl = ws.get("id")
    p = ws.get("params") or {}
    if impl == "mechanics":
        _walk(ws.get("mechanics"), acc)
    else:
        acc["damage"] = LEGACY_DAMAGE.get(impl, lambda q: 0.85 * float(q.get("damage", 0) or 0))(p)
        eff = p.get("effect")
        if eff:
            acc["cc"].append(dict(id=eff, seconds=float(p.get("effect_duration", 2.0)), potency=p.get("amount"),
                                  part=impl, repeats=1))
        if p.get("enemy_slow"):
            # SupportSkills.sanctuary: 틱마다 (틱 + 0.5초) 둔화를 다시 건다
            acc["cc"].append(dict(id="slow", seconds=float(p.get("tick", 1.0)) + 0.5, potency=p["enemy_slow"], part=impl,
                                  repeats=round(float(p.get("duration", 6)) / float(p.get("tick", 1.0)), 1)))
        if p.get("stun"):
            acc["cc"].append(dict(id="stun", seconds=float(p["stun"]), part=impl, repeats=1))
        for k in ("launch", "knockback", "pull"):
            if p.get(k):
                acc["cc"].append(dict(id=k, seconds=float(p[k]), part=impl, repeats=1))
        if p.get("taunt"):
            acc["cc"].append(dict(id="taunt", seconds=float(p["taunt"]), part=impl, repeats=1))
        if impl == "riposte":
            acc["self_buff"]["damage_reduction"] = float(p.get("reduction", 0.5))
            acc["guard_seconds"] = float(p.get("duration", 2.0))
        if impl in ("sanctuary",):
            acc["self_heal"] += float(p.get("heal", 0.02)) * float(p.get("duration", 6)) / float(p.get("tick", 1.0))
            if p.get("shield"):
                acc["self_shield"] += float(p["shield"])
            if p.get("ally_buff"):
                acc["self_buff"].update(p["ally_buff"])
        if impl == "mend":
            acc["self_heal"] += float(p.get("heal", 0.15))
        if impl == "empower":
            acc["self_buff"].update({k: v for k, v in p.items() if k in ("damage", "attack_speed", "crit_chance",
                                                                           "lifesteal", "damage_reduction")})
        dt = p.get("damage_type")
        acc["kinds"].add("magic" if dt == "magic" else "physical" if dt in ("melee", "ranged") else "default")
    kinds = {kind if k == "default" else k for k in acc["kinds"]} or {kind}
    skind = "hybrid" if len(kinds) > 1 else next(iter(kinds))
    return dict(name=ws.get("name"), input=ws.get("input"), impl=impl, cooldown=float(ws.get("cooldown", 12)),
                mana=float(ws.get("mana", 15)), damage=acc["damage"] * factor, execute=acc["execute"] * factor,
                percent=acc["percent"], lifesteal=acc["lifesteal"], dot=acc["dot"], cc=acc["cc"], kind=skind,
                self_shield=acc["self_shield"], self_buff=acc["self_buff"], self_heal=acc["self_heal"],
                guard=acc.get("guard_seconds", 0.0), description=ws.get("description", ""))


# ───────────────────────────── 직업 스킬 (PvP 시뮬레이터용) ─────────────────────────────
# hit = 움직이는 플레이어에게 맞을 확률(1v1), dmg = 스킬 위력 배율 (× 직업 skill_scale), kind = 피해 종류.
# cc = (id, 초, 세기) — 지금 classes.yml 값. delay = 시전부터 피해까지(초).
def _cp(cls, sid):
    for s in CLASSES[cls]["skills"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def class_kit(cls):
    out = []
    for s in CLASSES[cls]["skills"]:
        p = s.get("params", {})
        sid = s["id"]
        d = dict(id=sid, name=s["name"], unlock=s["unlock_level"], cooldown=s["cooldown"] * COOLDOWN_MULT,
                 mana=s["mana"], dmg=0.0, kind="none", hit=1.0, cc=[], delay=0.0, ult=s["unlock_level"] >= 30,
                 dot=None, buff=None, shield=0.0, heal=0.0)
        if sid == "shield_bash":
            d.update(dmg=p["damage"], kind="physical", hit=0.9, cc=[("stun", p["stun"], 1)])
        elif sid == "taunting_roar":
            d.update(buff=dict(damage_reduction=p["damage_reduction"], seconds=p["dr_duration"]))
        elif sid == "guardian_oath":
            d.update(shield=p["self_shield"], shield_s=p["duration"])
        elif sid == "bulwark_citadel":
            d.update(buff=dict(damage_reduction=p["damage_reduction"], seconds=p["duration"], knockback_immune=1),
                     cc=[("slow", p["duration"], p["enemy_slow"])], hit=0.6)
        elif sid == "spin_slash":
            d.update(dmg=p["damage"], kind="physical", hit=0.9, dot=("bleed", p["bleed_duration"], p["bleed_ratio"]))
        elif sid == "ground_cleaver":
            d.update(dmg=p["damage"], kind="physical", hit=0.8, cc=[("launch", 0, p["launch"])])
        elif sid == "blood_frenzy":
            d.update(buff=dict(attack_speed=p["attack_speed"], damage=p["damage"], lifesteal=p["lifesteal"],
                               seconds=p["duration"]), hp_cost=p["hp_cost"])
        elif sid == "ruinous_leap":
            d.update(dmg=p["damage"], kind="physical", hit=0.85, debuff=("vulnerable", p["vuln_duration"], p["vulnerability"]))
        elif sid == "piercing_arrow":
            d.update(dmg=p["damage"], kind="physical", hit=0.8)
        elif sid == "hunters_mark":
            d.update(debuff=("mark", p["duration"], p["damage_taken"]), hit=0.95)
        elif sid == "evasive_trap":
            d.update(dmg=p["trap_damage"], kind="physical", hit=0.45, cc=[("root", p["trap_root"], 1)])
        elif sid == "arrow_storm":
            d.update(dmg=p["damage"] * p["duration"] / p["tick"], kind="physical", hit=0.5, cc=[("slow", 0.8, p["slow"])])
        elif sid == "arcane_bolt":
            d.update(dmg=p["damage"], kind="magic", hit=0.85, delay=0.4)
        elif sid == "frost_nova":
            d.update(dmg=p["damage"], kind="magic", hit=0.85, cc=[("root", p["root"], 1)])
        elif sid == "phase_blink":
            d.update(dmg=p["echo_damage"], kind="magic", hit=0.5, delay=p["echo_delay"])
        elif sid == "meteor_fall":
            d.update(dmg=p["damage"], kind="magic", hit=0.7, delay=p["delay"],
                     dot=("burn", p["burn_duration"], p["burn_dps"]))
        elif sid == "healing_light":
            d.update(heal=p["heal"], heal_scale=p["heal_power_scale"])
        elif sid == "purifying_wave":
            d.update(dmg=p["damage"], kind="magic", hit=0.9, heal=p["heal"], cleanse=True)
        elif sid == "sacred_ward":
            d.update(shield=p["shield"], shield_s=p["duration"], buff=dict(damage=p["damage_buff"], seconds=p["duration"]))
        elif sid == "resurrection_hymn":
            d.update(heal=p["heal"], channel=p["channel"])
        elif sid == "shadow_strike":
            d.update(dmg=p["damage"], back_dmg=p["back_damage"], kind="physical", hit=0.9)
        elif sid == "smoke_veil":
            d.update(buff=dict(evasion=p["evasion"], seconds=p["duration"]), stealth=p["stealth"],
                     stealth_bonus=p["stealth_bonus"])
        elif sid == "venom_blades":
            d.update(buff=dict(venom=1, seconds=p["duration"]), venom=dict(dps=p["dps_per_stack"], max=p["max_stacks"],
                                                                              dur=p["stack_duration"],
                                                                              weaken=p["weaken_at_max"]))
        elif sid == "shadow_execution":
            d.update(dmg=p["damage"] * p["boss_hits"], kind="physical", hit=0.95,
                     execute=(p["execute_threshold"], p["execute_bonus"]),
                     buff=dict(evasion=0.4, seconds=p["boss_hits"] * p["interval"] + 0.5))
        out.append(d)
    return out


CLASS_SKILL_KIND = {"guardian": "physical", "berserker": "physical", "hunter": "physical", "arcanist": "magic",
                    "priest": "magic", "shadow": "physical"}
CLASS_NAME = {k: v["name"] for k, v in CLASSES.items()}
CLASS_ORDER = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]


if __name__ == "__main__":
    import collections
    n = 0
    c = collections.Counter()
    for wid in all_weapons():
        w = weapon(wid)
        for s in w["skills"]:
            n += 1
            for x in s["cc"]:
                c[x["id"]] += 1
    print("weapon skills", n, dict(c))
    w = weapon("celestial_oathkeeper")
    print(w["name"], w["sp"], [(s["name"], round(s["damage"], 2), s["kind"], s["cc"]) for s in w["skills"]])
    print(class_kit("shadow")[3])
