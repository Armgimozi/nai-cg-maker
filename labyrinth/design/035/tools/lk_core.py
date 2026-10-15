#!/usr/bin/env python3
"""
TASK B — 방어구 겉모습(판금·가죽·천) 장단점: 공통 데이터·규칙.

읽기 전용: repo items.yml / classes.yml / config.yml, design2/gear_spec.json(새 방어구 6세트 안), combat_spec(ce_core·ce_model·ce_sim).
  LOOKS            겉모습마다 부위 하나의 숨은 효과(implicit) + 4부위 '온전한 겉모습' 효과
  look_of(item)    아이템 → heavy | light | cloth | plain | any
  SET_REQ          세트(또는 단품)마다 요구 능력치 짝 (정체성 따라) → new_requires(item)
  STATS_RENAME     요구 짝에 맞춰 이름만 바꾸는 스탯 줄 (값은 그대로)
"""
import json
import math
import os

import yaml

REPO = "/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources"
HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)


def _load(p):
    with open(os.path.join(REPO, p), encoding="utf-8") as f:
        return yaml.safe_load(f)


_items = _load("content/items.yml")
ITEMS = _items["items"]
SETS = _items["sets"]
CLASSES = _load("content/classes.yml")["classes"]
CONFIG = _load("config.yml")
with open(os.path.join(D2, "gear_spec.json"), encoding="utf-8") as f:
    GEAR = json.load(f)

# gear_spec 의 새 방어구 6세트(24부위) — '안'(아직 repo 에 없음). 같은 규칙을 받는다.
NEW_SETS = {}
NEW_ITEMS = {}
for sid, s in GEAR["armor_sets"].items():
    NEW_SETS[sid] = dict(name=s["name"], look=s["look"], pieces=s["pieces"], bonuses=s["bonuses"], proposed=True)
    for iid, it in s["pieces_items"].items():
        NEW_ITEMS[iid] = dict(it, proposed=True)

ALL_SETS = dict(SETS)
ALL_SETS.update(NEW_SETS)
ALL_ITEMS = dict(ITEMS)
ALL_ITEMS.update(NEW_ITEMS)

STATS = ("STR", "DEX", "INT", "VIT", "WIS", "LUK")
SLOTS = ("head", "chest", "legs", "feet")
RANK = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5}

# ───────────────────────────── 겉모습 효과 (최종안) ─────────────────────────────
# 부위 하나(머리·몸·다리·발 어느 칸이든 같은 값, 방패 = 판금 한 부위)의 숨은 효과.
#   defense_pct : 최종 방어 × (1 + 합)          hp_pct : 최대 HP × (1 + 합)
#   mana_regen_pct : 초당 MP 재생 × (1 + 합)     cooldown_pct : 스킬 재사용 대기 시간 × (1 + 합) (재사용 감소 스탯 뒤에)
#   나머지 키는 지금 StatBlock 키 그대로(더하기)
LOOKS = {
    "heavy": dict(
        name="판금",
        piece={"defense_pct": 0.04, "damage_reduction": 0.005, "move_speed": -0.02, "evasion": -0.01,
               "cooldown_pct": 0.02},
        full=dict(id="steadfast", name="버팀", knockback_resist=0.60, cc_resist=0.40),
    ),
    "light": dict(
        name="가죽",
        piece={"evasion": 0.015, "crit_chance": 0.01, "attack_speed": 0.015, "move_speed": 0.01, "defense_pct": -0.06},
        full=dict(id="tumble", name="구르기", distance=3.5, iframe=0.4, cooldown=8.0),
    ),
    "cloth": dict(
        name="천",
        piece={"skill_damage": 0.02, "cooldown_pct": -0.015, "mana_regen_pct": 0.06, "hp_pct": -0.02},
        full=dict(id="mana_shield", name="마나 보호막", absorb=0.20, damage_per_mp=2.0, off_below=0.20),
    ),
}
# 곱하는 키 (StatBlock 에 더하지 않고 따로): 방어 · 최대 HP · MP 재생 · 직업·무기 스킬 재사용 대기 시간
MULT_KEYS = ("defense_pct", "hp_pct", "mana_regen_pct", "cooldown_pct")
FULL_PIECES = 4


def look_totals(counts):
    """{look: 부위 수} → 숨은 효과 합 (StatBlock 키)."""
    out = {}
    for lk, n in counts.items():
        if lk not in LOOKS:
            continue
        for k, v in LOOKS[lk]["piece"].items():
            out[k] = out.get(k, 0.0) + v * n
    return out


# ───────────────────────────── 겉모습 판정 ─────────────────────────────
HELM_LOOK = {"helm_knight": "heavy", "helm_horned": "heavy", "helm_winged": "heavy", "hood": "light",
             "half_mask": "light", "circlet": "cloth", "crown": "cloth", "wizard_hat": "cloth"}
# 세트 look 을 덮어쓰는 것: 수련생·길잡이 = 평상복(겉모습 효과 없음, 1층 장비)
SET_LOOK_OVERRIDE = {"novice": "plain", "wayfarer": "plain"}
# 단품(세트 없음) 투구: items.yml 에 look 을 직접 적는다
ITEM_LOOK = {"grove_mossguard_helm": "heavy", "silkqueen_veil": "light", "mycelking_spore_crown": "cloth",
             "osric_sluice_helm": "heavy", "nightmare_crown": "any"}


def look_of(iid):
    it = ALL_ITEMS[iid]
    if it.get("type") != "armor":
        return None
    if it.get("armor_slot") == "offhand":
        return "heavy"
    if iid in ITEM_LOOK:
        return ITEM_LOOK[iid]
    sid = it.get("set_bonus")
    if sid:
        if sid in SET_LOOK_OVERRIDE:
            return SET_LOOK_OVERRIDE[sid]
        return ALL_SETS[sid].get("look", "light")
    return HELM_LOOK.get(it["model"]["shape"], "plain")


# ───────────────────────────── 요구 능력치 ─────────────────────────────

def R(L):
    """0.3.4 단독 요구치."""
    v = math.ceil(2.5 * (L - 1))
    return 0 if v <= 2 else v


REQ_TOTAL_MULT = 1.10     # 두 능력치로 나누면 합은 0.3.4 단독 요구치의 1.1배 (겹치면 싸지고, 안 겹치면 조금 비싸다)


def T(L):
    r = R(L)
    return 0 if r == 0 else math.ceil(r * REQ_TOTAL_MULT)


def split(total, shares):
    """합 total 을 비율 shares(앞이 큰 쪽)로 나눈다. 첫 칸은 올림, 나머지는 반올림, 끝 칸이 남은 몫 (합 = total)."""
    if total <= 0:
        return {}
    keys = list(shares)
    vals = []
    left = total
    for i, k in enumerate(keys):
        if i == len(keys) - 1:
            v = left
        elif i == 0:
            v = math.ceil(total * shares[k])
        else:
            v = round(total * shares[k])
        v = max(1, min(v, left - (len(keys) - 1 - i)))
        vals.append(v)
        left -= v
    return dict(zip(keys, vals))


P64 = (0.6, 0.4)
# 세트·단품마다 요구 짝 (정체성). 판금 = VIT 이 앞, 가죽 = DEX 이 앞, 천 = INT 또는 WIS 이 앞.
# (짝, 정체성 이름, 왜)
SET_REQ = {
    # 판금
    "pit_foreman": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "광부 감독관 — 힘으로 버티는 판금"),
    "mycel_carapace": ({"VIT": 0.6, "WIS": 0.4}, "regen", "균사가 금을 메우는 갑각 — 회복·정신 (gear_spec 안)"),
    "verdigris_guard": ({"VIT": 0.6, "WIS": 0.4}, "templar", "수문 신전 경비 — 정신 판금: 사제·탱커 겸용"),
    "emberforged": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "용광로 담금질 — 힘 판금"),
    "forge_warden": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "모루왕 친위대 (보스) — 힘 판금"),
    "geode_bastion": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "정동 거한의 껍질 — 힘 판금"),
    "index_bulwark": ({"VIT": 0.6, "INT": 0.4}, "runeplate", "금서 서가 수호자 — 지능 판금 (gear_spec 안)"),
    "clockwork_juggernaut": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "태엽 거신 — 힘 판금"),
    # 가죽
    "webrunner": ({"DEX": 0.6, "STR": 0.4}, "bleed_crit", "거미줄 잠행자 — 힘 가죽: 피하며 베는 전사도"),
    "hypha_stalker": ({"DEX": 0.6, "LUK": 0.4}, "ambush", "소리 없는 균사 사냥꾼 — 행운 가죽"),
    "sluice_diver": ({"DEX": 0.6, "VIT": 0.4}, "survivor", "잠수부 — 체력 가죽: 오래 버티는 사수 (gear_spec 안)"),
    "rimefang": ({"DEX": 0.6, "STR": 0.4}, "bleed_crit", "송곳니 사냥복 — 힘 가죽"),
    "rime_stalker": ({"DEX": 0.6, "LUK": 0.4}, "ambush", "발자국 하나로 쫓는 추적자 — 행운 가죽 (gear_spec 안)"),
    "shard_dancer": ({"DEX": 0.6, "STR": 0.4}, "bleed_crit", "빛으로 눈을 속이고 베어 드는 무희 — 힘 가죽"),
    "inkveil": ({"DEX": 0.6, "INT": 0.4}, "spellblade", "먹물 분신 (보스) — 지능 가죽: 빠른 마법 검사"),
    "abyss_walker": ({"DEX": 0.6, "LUK": 0.4}, "ambush", "빛을 삼키는 가죽, 윤곽조차 안 보인다 — 행운 가죽"),
    # 천
    "silkweaver": ({"INT": 0.6, "WIS": 0.4}, "mana_flow", "마력이 실을 타고 — 지능 천"),
    "spore_sage": ({"WIS": 0.6, "VIT": 0.4}, "support", "포자 현자 — 정신·체력 천: 버티는 지원"),
    "cinder_cantor": ({"INT": 0.6, "WIS": 0.4}, "mana_flow", "잿불 성가자 (gear_spec 안)"),
    "crypt_mourner": ({"INT": 0.6, "WIS": 0.4}, "mana_flow", "묘역 애도자 — 지능 천 (사제에게도 지능은 피해)"),
    "frost_regalia": ({"INT": 0.6, "WIS": 0.4}, "mana_flow", "얼음관 여제 (보스) — 지능 천"),
    "lorekeeper": ({"INT": 0.6, "VIT": 0.4}, "battlemage", "서고지기 — 지능·체력 천: 스킬로 싸우는 누구나"),
    "clock_astrologer": ({"WIS": 0.6, "INT": 0.4}, "mana_flow", "태엽 점성술사 (gear_spec 안)"),
    "starless_choir": ({"WIS": 0.6, "INT": 0.4}, "support", "별 없는 성가대 — 정신 천"),
    # 평상복 (1층)
    "novice": ({}, "plain", "시작 지급 — 요구 없음"),
    "wayfarer": ({"VIT": 0.6, "DEX": 0.4}, "plain", "모든 직업 — 직업 기본 능력치로 거의 다 찬다"),
}
ITEM_REQ = {
    # 방패 (판금 한 부위)
    "oak_round_shield": ({}, "bulwark", "Lv1 — 요구 없음"),
    "ironbound_kite_shield": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "갱도 철판"),
    "sporecap_round_shield": ({"VIT": 0.6, "WIS": 0.4}, "regen", "포자갓 — 회복"),
    "verdigris_tower_shield": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "집게 등딱지"),
    "anvil_face_shield": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "모루 윗면"),
    "frostgrave_tower_shield": ({"VIT": 0.6, "WIS": 0.4}, "templar", "묘비 — 정신"),
    "prism_aegis": ({"VIT": 0.6, "INT": 0.4}, "runeplate", "빛과 어둠의 껍질 (보스) — 지능"),
    "inkbound_kite_shield": ({"VIT": 0.6, "INT": 0.4}, "runeplate", "금서 표지 — 지능 (재사용 감소 줄)"),
    "clockwork_bastion": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "대시계 문짝 (보스)"),
    "void_bulwark_shield": ({"VIT": 0.6, "WIS": 0.4}, "templar", "공허의 문 — 정신"),
    # 단품 투구
    "grove_mossguard_helm": ({"VIT": 0.6, "WIS": 0.4}, "regen", "이끼 석관 (보스, 모든 직업) — 회복"),
    "silkqueen_veil": ({"DEX": 0.6, "LUK": 0.4}, "ambush", "여왕의 면사포 (보스)"),
    "mycelking_spore_crown": ({"INT": 0.6, "WIS": 0.4}, "mana_flow", "균사왕의 관 (보스)"),
    "osric_sluice_helm": ({"VIT": 0.6, "STR": 0.4}, "bulwark", "수문 망령의 투구 (보스)"),
    "nightmare_crown": ({"VIT": 0.5, "LUK": 0.3, "WIS": 0.2}, "any", "악몽의 왕관 (칭호 보상, 모든 직업) — 세 능력치"),
}

# 요구 짝과 맞추려고 이름만 바꾸는 스탯 줄 (값 그대로). 세트 id → {옛 키: 새 키}
STATS_RENAME = {
    "verdigris_guard": {"STR": "WIS"},
    "index_bulwark": {"STR": "INT"},
    "rimefang": {"LUK": "STR"},
    "shard_dancer": {"LUK": "STR"},
    "inkveil": {"LUK": "INT"},
    "spore_sage": {"INT": "VIT"},
    "lorekeeper": {"WIS": "VIT"},
    "mycel_carapace": {"STR": "WIS"},
    "sluice_diver": {"LUK": "VIT"},
}
ITEM_RENAME = {
    "prism_aegis": {}, "inkbound_kite_shield": {},
}


def req_spec(iid):
    it = ALL_ITEMS[iid]
    if iid in ITEM_REQ:
        return ITEM_REQ[iid]
    sid = it.get("set_bonus")
    return SET_REQ.get(sid, ({}, "?", ""))


def new_requires(iid):
    it = ALL_ITEMS[iid]
    shares, _, _ = req_spec(iid)
    if not shares:
        return {}
    return split(T(it["level_req"]), shares)


def old_requires(iid):
    it = ALL_ITEMS[iid]
    r = dict(it.get("requires") or {})
    return r, dict(it.get("requires_any") or {})


def renamed_stats(iid):
    it = ALL_ITEMS[iid]
    st = {k: list(v) if isinstance(v, list) else v for k, v in it["stats"].items()}
    ren = STATS_RENAME.get(it.get("set_bonus"), {})
    ren = dict(ren, **ITEM_RENAME.get(iid, {}))
    out = {}
    for k, v in st.items():
        out[ren.get(k, k)] = v
    return out


def armor_items(include_new=True):
    src = ALL_ITEMS if include_new else ITEMS
    return {k: v for k, v in src.items() if v.get("type") == "armor"}


def mid(r):
    return (r[0] + r[1]) / 2 if isinstance(r, list) else float(r)


if __name__ == "__main__":
    import collections
    cnt = collections.Counter()
    for k, v in sorted(armor_items().items(), key=lambda kv: (kv[1]["level_req"], kv[1].get("armor_slot"))):
        lk = look_of(k)
        cnt[lk] += 1
        print(f"L{v['level_req']:<3} {v['rarity'][:4]:4} {v.get('armor_slot'):7} {k:30} {lk:6} old={old_requires(k)} new={new_requires(k)} {'(안)' if v.get('proposed') else ''}")
    print(cnt)
