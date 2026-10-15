#!/usr/bin/env python3
"""
피해 종류 꼬리표: 직업 스킬 24개 + 무기 스킬 전부(무기id:입력) + 상태이상 + 고유 효과 26개.
  physical = STR 로 커짐 · magic = INT 로 커짐 · hybrid = 부분마다 자기 종류(한 번의 피해가 hybrid 면 (STR+INT)/2)
  none = 피해 없음(회복·보호막·버프·도발) · fixed = 최대 HP 비율·되돌림처럼 스탯과 무관한 피해
→ ce_kinds.json
"""
import json
import os

import ce_core as C

HERE = os.path.dirname(os.path.abspath(__file__))

CLASS_SKILLS = {
    # 수호기사
    "shield_bash": ("physical", "부채꼴 타격 1.2 + 기절"),
    "taunting_roar": ("none", "도발 + 받는 피해 감소"),
    "guardian_oath": ("none", "피해 대신 받기(되돌린 몫은 fixed) + 보호막"),
    "bulwark_citadel": ("none", "방벽: 피해 감소·밀림 면역·적 둔화"),
    # 광전사
    "spin_slash": ("physical", "원형 1.4 + 출혈(물리 지속)"),
    "ground_cleaver": ("physical", "직선 1.8 + 띄우기"),
    "blood_frenzy": ("none", "HP 바쳐 공속·피해·흡혈 버프"),
    "ruinous_leap": ("physical", "도약 3.5 + 받는 피해 +15%"),
    # 사냥꾼
    "piercing_arrow": ("physical", "관통 화살 2.0"),
    "hunters_mark": ("none", "표식: 받는 피해 +20%"),
    "evasive_trap": ("physical", "덫 1.0 + 속박"),
    "arrow_storm": ("physical", "화살비 0.6 × 8틱"),
    # 비전술사
    "arcane_bolt": ("magic", "마력탄 2.0"),
    "frost_nova": ("magic", "서리 고리 1.2 + 빙결"),
    "phase_blink": ("magic", "잔상 폭발 1.0"),
    "meteor_fall": ("magic", "운석 5.0 + 불태움(마법 지속)"),
    # 사제
    "healing_light": ("none", "치유 (WIS 치유력)"),
    "purifying_wave": ("magic", "파동 0.8 + 정화·회복"),
    "sacred_ward": ("none", "보호막 + 피해 +10%"),
    "resurrection_hymn": ("none", "부활·회복"),
    # 그림자
    "shadow_strike": ("physical", "돌진 찌르기 1.8 / 등 뒤 3.0"),
    "smoke_veil": ("none", "연막: 회피·은신 (다음 공격 +50%)"),
    "venom_blades": ("physical", "독날: 독 중첩(물리 지속)"),
    "shadow_execution": ("physical", "순회 베기 2.2"),
}

PASSIVES = {
    "iron_will": "none", "bloodrage": "multiplier (모든 종류)", "keen_eye": "physical (끝까지 당긴 화살 +30%)",
    "arcane_resonance": "multiplier (모든 종류)", "grace": "magic (+10% 마법 피해 — 새 줄)", "vital_point": "multiplier (치명·공속)",
}

# 상태이상 지속 피해 종류 (부여할 때 굳는 위력 = 스킬 위력 × (1+0.01×STR 또는 INT) × 비율)
STATUS_KINDS = {"bleed": "physical", "poison": "physical", "venom": "physical", "wither": "physical",
                "burn": "magic", "shock": "magic", "frost": "none (둔화·빙결만, 피해 없음)"}

UNIQUE_KINDS = {
    "rend": ("physical", "출혈 지속 — 스킬 위력 기준"), "hemorrhage": ("none", "치명 보정"),
    "leech": ("none", "회복 (한 방 피해 비율)"), "feast": ("none", "회복"),
    "thorns": ("fixed", "받은 피해 비율 되돌림 — 스탯 무관"), "shield_bash": ("physical", "한 방 공격력 40% + 기절"),
    "steadfast": ("none", "받는 피해 감소"), "cleave": ("physical", "한 방 공격력 30% (무기 종류 따라: 시전 무기면 magic)"),
    "chain_spark": ("magic", "번개 — 한 방 공격력 45% × INT 배율"), "death_burst": ("physical", "처치 폭발 — 스킬 위력 80% (시전 무기면 magic)"),
    "execute": ("none", "곱하기 보정"), "bloodrush": ("none", "곱하기 보정"), "momentum": ("none", "공속"),
    "flurry": ("physical", "한 방 공격력 70% 추가 타격 (무기 종류 따름)"), "counterstep": ("none", "치명·곱하기"),
    "siphon": ("none", "MP·재사용"), "overcharge": ("magic", "폭발 — 스킬 위력 120%"),
    "sanctify": ("none", "치유 = 한 방 공격력 × 비율 + 치유력"), "ward_aura": ("none", "보호막"),
    "imbue": ("element", "burn/shock = magic, poison = physical, frost = 피해 없음 — 스킬 위력 기준"),
    "exploit": ("none", "곱하기"), "first_strike": ("none", "곱하기"), "backstab": ("none", "곱하기"),
    "longshot": ("none", "곱하기"), "berserk": ("none", "곱하기"), "armor_break": ("none", "방어 깎기"),
}

DMG_EFFECTS = {"damage", "execute", "lightning", "explosion"}
DOT_EFFECTS = {"ignite": "magic", "poison": "physical", "bleed": "physical", "wither": "physical"}


def default_kind(wid):
    st = C.style_of(C.weapon_shape(wid))
    return "magic" if st == "caster" else "physical"


def type_to_kind(t, dflt):
    if t is None:
        return dflt
    t = str(t).lower()
    return {"melee": "physical", "ranged": "physical", "magic": "magic", "true": "fixed"}.get(t, dflt)


def walk_mechanics(node, dflt, parts):
    if isinstance(node, dict):
        if "effects" in node and isinstance(node["effects"], list):
            for e in node["effects"]:
                if not isinstance(e, dict):
                    continue
                k0 = next(iter(e))
                if k0 in DMG_EFFECTS:
                    if k0 == "lightning":
                        parts.add("magic")
                    elif e.get("magic"):
                        parts.add("magic")
                    else:
                        parts.add(type_to_kind(e.get("damage_type"), dflt))
                elif k0 in DOT_EFFECTS:
                    parts.add(DOT_EFFECTS[k0])
                elif k0 == "percent":
                    parts.add("fixed")
        for v in node.values():
            walk_mechanics(v, dflt, parts)
    elif isinstance(node, list):
        for x in node:
            walk_mechanics(x, dflt, parts)


def weapon_skill_kind(wid, s):
    dflt = default_kind(wid)
    sid = s["id"]
    p = s.get("params") or {}
    parts = set()
    if sid == "mechanics":
        walk_mechanics(s.get("mechanics"), dflt, parts)
    elif sid in ("mend", "empower"):
        pass
    elif sid == "sanctuary":
        if p.get("damage"):
            parts.add(type_to_kind(p.get("damage_type"), "magic"))
    elif sid == "riposte":
        parts.add(type_to_kind(p.get("damage_type"), dflt))
        if p.get("reflect"):
            parts.add("fixed")
    else:   # slash_wave, missile, shadow_step, beam, chain_bolt, vortex, rain_zone, blade_orbit
        base = {"slash_wave": "physical", "beam": "magic", "chain_bolt": "magic", "vortex": "magic"}.get(sid, dflt)
        if p.get("damage") or p.get("counter_damage"):
            parts.add(type_to_kind(p.get("damage_type"), base))
        eff = p.get("effect")
        if eff in ("burn",):
            parts.add("magic")
        elif eff in ("poison", "bleed"):
            parts.add("physical")
    dmg = parts - {"fixed"}
    if not dmg:
        kind = "fixed" if "fixed" in parts else "none"
    elif dmg == {"physical"}:
        kind = "physical"
    elif dmg == {"magic"}:
        kind = "magic"
    else:
        kind = "hybrid"
    return kind, sorted(parts)


if __name__ == "__main__":
    ws = {}
    detail = {}
    for wid, w in C.WEAPONS.items():
        for s in w.get("weapon_skills") or []:
            key = f"{wid}:{s['input']}"
            k, parts = weapon_skill_kind(wid, s)
            ws[key] = k
            detail[key] = dict(name=s["name"], impl=s["id"], parts=parts, weapon_default=default_kind(wid))
    for wid, w in C.NEW_WEAPONS.items():
        for s in w.get("weapon_skills") or []:
            key = f"{wid}:{s['input']}"
            k, parts = weapon_skill_kind(wid, s)
            ws[key] = k
            detail[key] = dict(name=s["name"], impl=s["id"], parts=parts, weapon_default=default_kind(wid), src="gear_spec_new")
    from collections import Counter
    print("weapon skills", len(ws), Counter(ws.values()))
    out = dict(class_skills={k: v[0] for k, v in CLASS_SKILLS.items()},
               class_skill_notes={k: v[1] for k, v in CLASS_SKILLS.items()},
               weapon_skills=ws, weapon_skill_detail=detail, passives=PASSIVES, status=STATUS_KINDS,
               unique_effects={k: v[0] for k, v in UNIQUE_KINDS.items()}, unique_notes={k: v[1] for k, v in UNIQUE_KINDS.items()})
    with open(os.path.join(HERE, "ce_kinds.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    hy = [k for k, v in ws.items() if v == "hybrid"]
    print("hybrid:", hy[:40])
