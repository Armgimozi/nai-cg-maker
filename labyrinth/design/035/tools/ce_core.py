#!/usr/bin/env python3
"""
TASK E — 전투 모델 공통 모듈 (게이지 없애기 · 무기마다 공격 간격 · STR=물리 / INT=마법).

읽기 전용으로 repo 의 yml 과 gear_spec.json(새 무기 106개·요구 능력치 바꿈)을 읽는다.
  OLD = 0.3.4 공식 (StatCalculator.primaryMix, 무기 종류 공속, 공격 게이지)
  NEW = 이 명세의 공식 (P 파라미터로 바꿔 가며 탐색)
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


ITEMS = _load("content/items.yml")["items"]
CLASSES = _load("content/classes.yml")["classes"]
MOBS = _load("content/mobs.yml")["mobs"]
BOSSES = _load("content/bosses.yml")["bosses"]
FLOORS = _load("content/floors.yml")["floors"]
CONFIG = _load("config.yml")
# 입력 = 옛 장비 명세(gear-c1). gear_spec.json 은 gear-c2(attack.interval·tier)로 바뀌었으므로 옛 판 사본을 읽는다.
_GEAR_IN = os.path.join(HERE, "_bak", "gear_spec_c1.json")
if not os.path.exists(_GEAR_IN):
    _GEAR_IN = os.path.join(D2, "gear_spec.json")
with open(_GEAR_IN, encoding="utf-8") as f:
    GEAR = json.load(f)

WEAPONS = {k: v for k, v in ITEMS.items() if v.get("type") == "weapon"}
NEW_WEAPONS = GEAR["weapons"]                      # 106 (gear_spec, 아직 repo 에 없음)
EXISTING_CHANGES = GEAR["existing_changes"]        # 131 (attack style, requires 바꿈 등)

# ───────────────────────────── 0.3.4 (OLD) ─────────────────────────────
OLD_AS = dict(CONFIG["weapon_attack_speed"])       # 종류 → 초당 공격 (게이지 꽉 참 주기의 역수)
OLD_SCALE = {"sword_shield": 1.00, "greatsword": 1.55, "bow": 1.30, "staff": 1.10, "scepter": 0.95, "dagger": 0.62}
BOW_PERIOD_OLD = 1.15        # 끝까지 당김 1초 + 놓고 다시 메기기
BOW_FULL_MULT_OLD = 1.25     # 끝까지 당긴 화살 = 바닐라 치명 화살 ×1.25 (CombatListener.rangedMult)
KEEN_EYE = 1.15              # 사냥꾼 매의 눈: 끝까지 당긴 화살 +15% (활 아닌 무기에는 없음)
STYLE_OF_TYPE = {"sword_shield": "melee", "greatsword": "melee", "dagger": "melee", "bow": "ranged",
                 "staff": "caster", "scepter": "caster"}
RECOMMENDED = {c: v["weapon_types"][0] for c, v in CLASSES.items()}


def mid(r):
    return (r[0] + r[1]) / 2 if isinstance(r, list) else float(r)


def old_rate(wtype):
    """0.3.4 기본 공격 '초당 피해 배율' (무기 피해 1 당, 게이지 꽉 차게 쳤을 때, 스탯·DEX 제외)."""
    if wtype == "bow":
        return BOW_FULL_MULT_OLD / BOW_PERIOD_OLD
    return OLD_AS[wtype]


def primary_mix(cls_id, s):
    return {"guardian": 0.6 * s["STR"] + 0.4 * s["VIT"], "berserker": s["STR"], "hunter": s["DEX"],
            "arcanist": s["INT"], "priest": 0.5 * s["INT"] + 0.5 * s["WIS"],
            "shadow": 0.7 * s["DEX"] + 0.3 * s["LUK"]}[cls_id]


# ───────────────────────────── 공격 방식 · 무기 간격 (NEW) ─────────────────────────────
BOW_SHAPES = {"longbow", "recurve_bow", "composite_bow", "horn_bow", "blade_bow", "bone_bow", "twin_bow"}
CASTER_SHAPES = {"staff_orb", "staff_crystal", "staff_ring", "staff_spiral", "staff_fork", "scepter", "sun_scepter",
                 "bell_scepter", "chalice_scepter", "censer_staff", "antler_staff", "lamp_crook", "thurible_rod",
                 "chime_rod"}

# 모양별 기본 공격 간격(초). 활은 '한 발 주기' = 끝까지 당기는 시간 + 0.15초(놓고 다시 메기기).
SHAPE_INTERVAL = {
    # 무거움 (~1.0초)
    "great_axe": 1.10, "executioner_axe": 1.15, "great_maul": 1.15, "greatsword": 1.00, "flamberge": 1.00,
    "war_scythe": 1.00, "glaive": 0.95, "cleaver": 0.90, "war_spear": 0.85,
    # 중간 (~0.67초)
    "warhammer": 0.75, "morning_star": 0.75, "mace": 0.72, "broadsword": 0.70, "longsword": 0.67,
    "falchion": 0.62, "sabre": 0.60, "rapier": 0.55,
    # 가벼움 (~0.45초)
    "tanto": 0.50, "sickle": 0.50, "kris": 0.48, "fang_blade": 0.47, "dagger": 0.45, "katar": 0.45, "stiletto": 0.43,
    # 시전 (휘두르기, 마법 피해)
    "staff_orb": 0.95, "antler_staff": 0.95, "staff_crystal": 0.90, "staff_ring": 0.90, "staff_spiral": 0.90,
    "staff_fork": 0.90, "lamp_crook": 0.90, "censer_staff": 0.85, "sun_scepter": 0.80, "bell_scepter": 0.80,
    "thurible_rod": 0.80, "scepter": 0.77, "chalice_scepter": 0.75, "chime_rod": 0.70,
    # 활 (한 발 주기)
    "longbow": 1.25, "composite_bow": 1.20, "blade_bow": 1.15, "bone_bow": 1.15, "recurve_bow": 1.10,
    "twin_bow": 1.05, "horn_bow": 1.00,
}

# 설명(lore)이 무게·속도를 말하는 무기는 모양 값에서 조금 옮긴다 (무기마다 다른 손맛).
LORE_TWEAK = {
    "mossvine_hornbow": -0.05,       # "작아서 … 재빨리 당길 수 있다"
    "slagedge_bladebow": +0.10,      # "묵직해서 당기기 힘들지만"
    "ore_splitter_axe": +0.05,       # 광맥 쪼개개 — 광부 도끼, 무거움
    "drowned_anchor_cleaver": +0.10,  # 닻 — 가장 무거운 참마도
    "osric_drowned_axe": +0.05,
    "doomclock_executioner": +0.05,
    "bloodmoon_reaver": +0.05,
    "geode_sunderer": +0.05,
    "silkspan_glaive": -0.05,        # 은실 — 가벼운 장대
    "silkguard_falchion": -0.04,
    "brine_falchion": -0.02,
    "eel_kris": -0.03,
    "mainspring_dagger": -0.03,      # 태엽 — 튕기듯 빠름
    "springloaded_bow": -0.10,       # 용수철 활 — 빨리 당겨짐
    "quicksilver_longbow": -0.10,    # 수은 — 빠름
    "galewing_bow": -0.05,           # 바람이 화살을 밀어 줌
    "tempest_bow": -0.05,
    "clockguard_mace": -0.04,
    "regulator_greatsword": -0.05,   # 조율기 — 정확한 박자
    "pendulum_censer": -0.05,
    "inkquill_hornbow": 0.0,
    "index_keeper_sword": +0.03,
    "abyss_sentinel_longsword": +0.03,
    "celestial_oathkeeper": 0.0,
    "eclipse_blade": -0.02,
    "viper_fang": -0.02,
    "nightshade_dagger": 0.0,
    "tidecaller_bow": 0.0,
    "frostbone_longbow": +0.05,      # 얼음뼈 — 뻣뻣함
    "rime_reaper_scythe": 0.0,
    "void_scythe": +0.03,
    "voidheart_staff": 0.0,
    "lantern_staff": 0.0,
}

MIN_INTERVAL = 0.25          # 하한 (5틱) — DEX·공속을 다 쌓아도 이보다 빠르지 않다
BOW_NOCK = 0.15              # 활: 놓은 뒤 다시 메기는 시간 (한 발 주기 − 당김 시간)


def style_of(shape):
    if shape in BOW_SHAPES:
        return "ranged"
    if shape in CASTER_SHAPES:
        return "caster"
    return "melee"


def weapon_shape(wid):
    w = WEAPONS.get(wid) or NEW_WEAPONS.get(wid)
    return w["model"]["shape"]


def interval_of(wid):
    """무기 하나의 기본 공격 간격(초, 소수 둘째 자리). 기존 131개 + gear_spec 새 106개."""
    shape = weapon_shape(wid)
    base = SHAPE_INTERVAL[shape]
    iv = base + LORE_TWEAK.get(wid, 0.0)
    if wid in NEW_WEAPONS:
        # 새 무기는 gear_spec 의 attack.speed(초당)를 존중하되 모양 값과 크게 다르면 모양 값 쪽으로 (±15% 안)
        sp = NEW_WEAPONS[wid]["attack"]["speed"]
        if style_of(shape) == "ranged":
            want = base  # 활: gear_spec 은 1.2 일괄 → 모양 값
        else:
            want = 1.0 / sp
        iv = min(base * 1.15, max(base * 0.85, want))
    return round(iv, 2)


# ───────────────────────────── 새 공식 파라미터 (기본값 = 명세 최종안) ─────────────────────────────
P_DEFAULT = dict(
    k_phys=0.02,           # STR 1점당 물리 공격력 +k
    k_mag=0.02,            # INT 1점당 마법 공격력 +k
    dex_crit=0.0015,       # DEX → 치명타 확률
    dex_speed=0.004,       # DEX → 공격 속도 (간격 단축, 활은 당김 단축)
    dex_evasion=0.0,       # DEX → 회피
    luk_crit=0.0025,
    cap_speed=0.60,        # 공격 속도 상한 (+60% → 간격 ÷1.6)
    ref_stat=lambda L: 8 + 3.6 * (L + 3),  # 무기 재기준 스탯 = 그 무기를 쓰는 동안(무기 레벨 +3) 정렬된 주 스탯 (3:2 분배 + 장비 줄)
    rebase_k=True,         # k 를 0.02 에서 바꾸면 무기 피해를 ref_stat 기준으로 보정
    keen_eye=KEEN_EYE,
    shadow_crit_dmg=0.0,   # 그림자 패시브 '급소 찌르기' 치명 피해 가산
    shadow_speed=0.0,      # 그림자 패시브 공격 속도 가산
    priest_magic=0.0,      # 사제 패시브 '은총' 마법 피해 가산
)


def rebase_factor(L, P, kind="physical"):
    """k 가 0.02 와 다를 때 무기 피해 보정 c(L) = (1+0.02·S_ref)/(1+k·S_ref). k=0.02 면 1."""
    if not P.get("rebase_k", True):
        return 1.0
    s = P["ref_stat"](L)
    k = P["k_mag"] if kind == "magic" else P["k_phys"]
    return (1 + 0.02 * s) / (1 + k * s)


def K_style(style, interval):
    """스킬 위력 정규화 상수 = 같은 단계(티어 위력 1)의 '설계 초당 피해'.
    근접은 빠를수록 조금 낮다(적중 훅이 더 자주 켜져서) — gear_spec K 와 같은 식, 공속 = 1/간격."""
    if style == "ranged":
        return OLD_SCALE["bow"] * old_rate("bow")          # 1.30 × 1.087 = 1.413
    if style == "caster":
        return 1.22
    sp = 1.0 / interval
    return 1.47 - 0.143 * max(0.0, sp - 1.5)


def old_weapon_dps(wid):
    """0.3.4 무기 하나의 설계 초당 피해 (무기 피해 가운데값 × 종류 주기, 스탯 제외)."""
    w = WEAPONS[wid]
    return mid(w["stats"]["damage"]) * old_rate(w["weapon_type"])


def tier_power_old(wid):
    w = WEAPONS[wid]
    return mid(w["stats"]["damage"]) / OLD_SCALE[w["weapon_type"]]


def new_per_hit(wid, P=P_DEFAULT):
    """기존 무기의 새 한 방 피해 [lo, hi] (정수). DPS 등가 = 0.3.4 숙련 DPS × c(L)."""
    w = WEAPONS[wid]
    lo, hi = w["stats"]["damage"]
    iv = interval_of(wid)
    rate = old_rate(w["weapon_type"])
    c = rebase_factor(w["level_req"], P, "magic" if style_of(w["model"]["shape"]) == "caster" else "physical")
    f = rate * iv * c
    return round_range(lo * f, hi * f)


def new_per_hit_newweapon(wid, P=P_DEFAULT):
    """gear_spec 새 무기: 그쪽 피해(공속 기준)를 같은 DPS 등가로 새 간격에 옮긴다."""
    w = NEW_WEAPONS[wid]
    lo, hi = w["stats"]["damage"]
    shape = w["model"]["shape"]
    st = style_of(shape)
    sp = w["attack"]["speed"]
    if st == "ranged":
        rate = BOW_FULL_MULT_OLD / BOW_PERIOD_OLD    # gear_spec 은 옛 활과 같은 공식(1.2) → 옛 활 실제 주기
        rate = rate * (1.0)  # 같은 값
    else:
        rate = sp
    iv = interval_of(wid)
    c = rebase_factor(w["level_req"], P, "magic" if st == "caster" else "physical")
    f = rate * iv * c
    return round_range(lo * f, hi * f)


def round_range(nlo, nhi):
    """정수 [a, b]: 가운데값이 목표에 가장 가깝고(±0.25 안이면 폭도 맞춤), a < b."""
    m, w = (nlo + nhi) / 2, (nhi - nlo)
    best = None
    for a in range(max(1, int(nlo) - 2), int(nlo) + 3):
        for b in range(a + 1, int(nhi) + 4):
            err = abs((a + b) / 2 - m) + 0.15 * abs((b - a) - w)
            if best is None or err < best[0]:
                best = (err, a, b)
    return [best[1], best[2]]


def skill_power(per_hit_mid, interval, style, mult=1.0):
    """스킬 위력 = DPS 등가 ÷ K(방식, 간격) × skill_power_mult  (= 티어 위력 × c(L))."""
    return per_hit_mid / interval / K_style(style, interval) * mult


USE_GEAR_REQUIRES = True   # False = 0.3.4 items.yml 요구치 (직업 비교용: 스탯 역할 변화만 보기)
# 피해 스탯이 아닌 능력치 '하나만' 요구하는 물리 무기의 요구치 나누기: {요구 스탯: (함께 요구할 피해 스탯, 그 몫)}
#   예 DEX R 단독 → DEX ceil(0.6R) + STR ceil(0.4R)  (합은 R 그대로)
REQ_SPLIT = {}


def requires_of(wid):
    """무기 요구 능력치 (gear_spec 바꿈 반영). {stat: n} 또는 {"any": {..}}."""
    if not USE_GEAR_REQUIRES and wid in WEAPONS:
        return WEAPONS[wid].get("requires") or {}
    ch = EXISTING_CHANGES.get(wid, {})
    if wid in NEW_WEAPONS:
        w = NEW_WEAPONS[wid]
        if w.get("requires_any"):
            return {"any": w["requires_any"]}
        return w.get("requires") or {}
    if ch.get("requires_any"):
        return {"any": ch["requires_any"]}
    if ch.get("requires"):
        return ch["requires"]
    return WEAPONS[wid].get("requires") or {}


def split_requires(req, L, kind="physical"):
    """REQ_SPLIT 적용 (단독 요구만). req = {stat: n}."""
    if len(req) != 1 or not REQ_SPLIT:
        return req
    (st, v), = req.items()
    if st not in REQ_SPLIT or kind != "physical":
        return req
    other, share = REQ_SPLIT[st]
    R = v
    a = math.ceil(R * (1 - share))
    b = math.ceil(R * share)
    return {st: a, other: b}


def req_value(L):
    v = math.ceil(2.5 * (L - 1))
    return 0 if v <= 2 else v
