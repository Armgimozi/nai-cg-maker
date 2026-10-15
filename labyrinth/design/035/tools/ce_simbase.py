#!/usr/bin/env python3
"""
미궁 라비린스 초반 밸런스 시뮬레이터 (솔로, 지하 1~3층).

repo 의 yml 을 읽기 전용으로 읽어 실제 수치를 쓴다:
  classes.yml / mobs.yml / bosses.yml / floors.yml / items.yml / loot.yml / config.yml / dungeon.yml
코드 공식 (StatCalculator / DamageFormula / MobAi / MobStats / InstanceContext / Boss / PatternScheduler / MechanicScaling) 을 옮겼다.

시간 간격 0.05초의 몬테카를로. 플레이어 실력은 두 프로필(novice=보통 실력, skilled=숙련)로 근사한다.
결과: 방 1개당 받는 피해(최대 HP 대비), 방 처치 시간, 층 1 완주(전투방 6 + 엘리트 + 보물방 미믹 + 보스) 생존율, 보스전 시간·피해.

사용:  /opt/packvenv/bin/python run_all.py   (이 파일은 모델 라이브러리)
"""
import argparse
import copy
import json
import math
import os
import random
import sys

import yaml

REPO = os.environ.get("LAB_REPO", "/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources")
DT = 0.05


def load(p):
    with open(os.path.join(REPO, p), encoding="utf-8") as f:
        return yaml.safe_load(f)


CLASSES = load("content/classes.yml")["classes"]
MOBS = load("content/mobs.yml")["mobs"]
BOSSES = load("content/bosses.yml")["bosses"]
FLOORS = load("content/floors.yml")["floors"]
ITEMS = load("content/items.yml")["items"]
LOOT = load("content/loot.yml")["tables"]
CONFIG = load("config.yml")
DUNGEON = load("dungeon.yml")

WEAPON_AS = CONFIG["weapon_attack_speed"]
DAMAGE_SCALE = {"sword_shield": 1.00, "greatsword": 1.55, "bow": 1.30, "staff": 1.10, "scepter": 0.95, "dagger": 0.62}
STARTER = {"guardian": "corridor_longsword", "berserker": "rootcutter_greatsword", "hunter": "corridor_longbow",
           "arcanist": "lantern_staff", "priest": "acolyte_scepter", "shadow": "moss_dirk"}
# 레벨업 5점 분배 (실제 플레이어가 흔히 하는 '주 스탯 3 : 체력 2')
ALLOC = {"guardian": {"VIT": 3, "STR": 2}, "berserker": {"STR": 3, "VIT": 2}, "hunter": {"DEX": 3, "VIT": 2},
         "arcanist": {"INT": 3, "VIT": 2}, "priest": {"WIS": 3, "VIT": 2}, "shadow": {"DEX": 3, "VIT": 2}}
STYLE = {"guardian": "melee", "berserker": "melee", "hunter": "kite", "arcanist": "melee", "priest": "melee", "shadow": "melee"}

PROFILES = {
    # uptime: 공격 기회 중 실제로 때리는 비율 / e_*: 근접 몹 공격 시도가 실제로 닿는 비율(위치 잡기·뒷걸음)
    # dodge_max: 1초 이상 경고를 피하는 비율 (경고가 짧을수록 줄어듦) / proj_hit: 원거리 기본 투사체 명중
    "novice": dict(uptime=0.70, e_melee=0.85, e_kite=0.60, dodge_max=0.45, proj_hit=0.85, potion_thr=0.30,
                   target="random", full_draw=0.70, back_rate=0.15, pillar=0.35, boss_e_melee=0.90, boss_e_kite=0.55,
                   traps=2.0),
    "average": dict(uptime=0.78, e_melee=0.75, e_kite=0.50, dodge_max=0.65, proj_hit=0.70, potion_thr=0.35,
                    target="random", full_draw=0.80, back_rate=0.25, pillar=0.55, boss_e_melee=0.80, boss_e_kite=0.42,
                    traps=1.0),
    "skilled": dict(uptime=0.85, e_melee=0.65, e_kite=0.40, dodge_max=0.85, proj_hit=0.55, potion_thr=0.40,
                    target="lowest", full_draw=0.90, back_rate=0.40, pillar=0.75, boss_e_melee=0.70, boss_e_kite=0.30,
                    traps=0.5),
}

LEGACY_DIFFS = {"easy": dict(hp=0.7, damage=0.6, drop=0.8, xp=0.8, telegraph=1.3),
                "normal": dict(hp=1.0, damage=1.0, drop=1.0, xp=1.0, telegraph=1.0),
                "hard": dict(hp=1.5, damage=1.4, drop=1.3, xp=1.3, telegraph=0.85),
                "nightmare": dict(hp=2.4, damage=2.0, drop=1.8, xp=1.7, telegraph=0.7)}
DIFFS = LEGACY_DIFFS
# MechanicScaling (보스 패턴): 쿨다운 배율, 추가 개수, 속도
MECH = {"easy": (1.15, 0), "normal": (1.0, 0), "hard": (0.9, 0), "nightmare": (0.8, 1)}


# ───────────────────────────── 시나리오 (현재 / 제안) ─────────────────────────────

def baseline():
    return dict(
        name="현재",
        ramp={},                      # difficulty id → {from_floor, full_floor, start:{hp,damage,telegraph}}
        mech_ramp=False,              # 보스 패턴 쿨다운·추가 개수도 램프를 따라가는가
        party_mob_count={},           # 인원 → 몹 수 배율
        mob_count_per_member=DUNGEON["mob_count_per_member"],
        rest_heal=DUNGEON["rest_heal"],
        room_clear_heal=0.0,
        starter_armor=False,
        starter_potions=0,
        attack_interval={},           # floor → 기본 공격 간격(초) (mobs.yml attack_interval)
        mob_damage_mult={},           # floor → mobs.yml damage 배율 (직접 수정 시)
        potion_drop_mult=1.0,         # 몹 potions_t1 확률 배율
        minor_heal=0.25,
        elite_variant=CONFIG["mobs"]["elite_variant_chance"],
        trap_mult=1.0,
        solo_hp=1.0,                  # 솔로(n=1)일 때 몹·보스 HP 배율 (config party.solo_hp)
        solo_damage=1.0,              # 솔로일 때 몹·보스 피해 배율 (config party.solo_damage)
        class_base_hp={},             # 직업 → base_hp 덮어쓰기
        class_skill_mult={},          # 직업 → 1번 스킬 damage 배율
        boss_attack_interval=2.0,     # 보스 기본 공격 간격(초) (Boss.java 40틱 고정)
        solo_reward_comp=False,       # 몹 수를 줄인 만큼 한 마리당 경험치·골드 보정 (방 보상 유지)
        first_clear_xp=0.0,           # 층 첫 클리어 보너스 = 그 층 level_range 구간 필요 경험치 × 이 값
        weapon_as={},                 # 무기 종류 → 초당 공격 (config weapon_attack_speed 덮어쓰기)
    )


STARTER_ARMOR = {  # 제안: 수련생 방어구 4종 (공용, common, Lv1, pool:false, sources [starter])
    "novice_cap": {"defense": 1, "VIT": 1, "hp": 4},
    "novice_tunic": {"defense": 2, "VIT": 1, "hp": 8},
    "novice_trousers": {"defense": 1, "VIT": 1, "hp": 6},
    "novice_boots": {"defense": 1, "VIT": 1, "move_speed": 0.01},
}


STARTER_SLOT = {"novice_cap": "head", "novice_tunic": "chest", "novice_trousers": "legs", "novice_boots": "feet"}


def proposal():
    """최종 제안 (balance_spec.json 과 같은 숫자)."""
    s = baseline()
    s.update(
        name="제안",
        # A. 난이도 층 램프 (어려움 4층, 악몽 6층에서 원래 배율 도달) + 보스 기믹 배율도 램프를 따름
        ramp={
            "hard": {"from_floor": 1, "full_floor": 4, "start": {"hp": 1.2, "damage": 1.15, "telegraph": 0.95}},
            "nightmare": {"from_floor": 1, "full_floor": 6, "start": {"hp": 1.8, "damage": 1.6, "telegraph": 0.85}},
        },
        mech_ramp=True,
        # B. 솔로 보정
        solo_hp=0.85,
        solo_damage=0.85,
        # C. 솔로·2인 전투방 몹 수 (+ 정예방 호위 수) + 줄어든 만큼 한 마리당 경험치·골드 보정
        party_mob_count={1: 0.7, 2: 0.9},
        elite_adds_scaled=True,
        solo_reward_comp=True,
        # D. 시작 꾸러미
        starter_armor=True,
        starter_potions=5,
        # E. 1~2층 몹 기본 공격 간격
        attack_interval={1: 1.5, 2: 1.35},
        # F. 전투방·정예방 정리 회복
        room_clear_heal=0.15,
        # G. 1~3층 정예 소환 수를 인원 비례로 (솔로 값)
        summon_solo={"moss_crawler_alpha": {"count": 1, "max_alive": 2}, "foreman_gorrak": {"count": 1, "max_alive": 2},
                     "spore_mother": {"count": 2, "max_alive": 3}},
    )
    return s


def proposal_plus_class():
    """선택 H: 솔로가 특히 힘든 두 직업 보정 (그림자·비전술사 기본 HP·VIT, 마력탄 피해)."""
    s = proposal()
    s.update(name="제안+직업보정", class_base_hp={"arcanist": 110, "shadow": 115},
             class_base_stats={"shadow": {"VIT": 5}, "arcanist": {"VIT": 4}}, skill_params={"arcanist": {"damage": 2.0}})
    return s


def proposal_plus_fcx():
    """선택 I: 층 첫 클리어 보너스 경험치 (그 층 level_range 구간 필요량 × 0.4)."""
    s = proposal()
    s.update(name="제안+첫클리어XP", first_clear_xp=0.4)
    return s


def diff_at(scn, diff_id, floor):
    """InstanceContext 의 층별 실효 난이도 (제안: ramp)."""
    d = dict(scn.get("diffs", DIFFS)[diff_id])
    r = scn["ramp"].get(diff_id)
    t = 1.0
    if r:
        a, b = r["from_floor"], r["full_floor"]
        t = 1.0 if b <= a else max(0.0, min(1.0, (floor - a) / (b - a)))
        for k in ("hp", "damage", "telegraph"):
            if k in r["start"]:
                d[k] = r["start"][k] + (d[k] - r["start"][k]) * t
    cd, extra = scn.get("mech", MECH)[diff_id]
    if scn["mech_ramp"] and r:
        cd = 1.0 + (cd - 1.0) * t
        extra = extra if t >= 0.5 else 0
    d["cd_mult"], d["extra"], d["t"] = cd, extra, t
    return d


# ───────────────────────────── 플레이어 ─────────────────────────────

def item_avg_stats(item_id):
    st = ITEMS[item_id]["stats"]
    return {k: (v[0] + v[1]) / 2 if isinstance(v, list) else v for k, v in st.items()}


class Player:
    def __init__(self, cls_id, level, scn, extra_gear=None):
        self.cls_id = cls_id
        self.c = copy.deepcopy(CLASSES[cls_id])
        if cls_id in scn["class_base_hp"]:
            self.c["base_hp"] = scn["class_base_hp"][cls_id]
        for st, v in scn.get("class_base_stats", {}).get(cls_id, {}).items():
            self.c["base_stats"][st] = v
        self.skill_mult = 1.0
        self.weapon_as = scn.get("weapon_as", {})
        self.level = level
        self.points = {k: 0 for k in ("STR", "DEX", "INT", "VIT", "WIS", "LUK")}
        self.alloc_points(CONFIG["level"]["start_points"] + CONFIG["level"]["points_per_level"] * (level - 1))
        self.weapon_id = STARTER[cls_id]
        slots = {"weapon": item_avg_stats(self.weapon_id)}
        if scn["starter_armor"]:
            for k, v in STARTER_ARMOR.items():
                slots[STARTER_SLOT[k]] = dict(v)
        acc = 0
        for g in extra_gear or []:
            it = ITEMS[g]
            if it["type"] == "weapon":
                self.weapon_id = g
                slots["weapon"] = item_avg_stats(g)
            elif it["type"] == "armor":
                slots[it.get("armor_slot", "chest")] = item_avg_stats(g)
            else:
                acc += 1
                slots[f"acc{acc}"] = item_avg_stats(g)
        self.weapon_type = ITEMS[self.weapon_id]["weapon_type"]
        self.gear = list(slots.values())
        self.recompute()
        self.hp = self.max_hp
        self.mp = self.max_mp

    def alloc_points(self, n):
        a = ALLOC[self.cls_id]
        per = sum(a.values())
        for i in range(n):
            # 5점 묶음 단위로 비율대로
            k = list(a.keys())
            idx = i % per
            acc = 0
            for key in k:
                acc += a[key]
                if idx < acc:
                    self.points[key] += 1
                    break

    def level_up(self, n=1):
        for _ in range(n):
            self.level += 1
            self.alloc_points(CONFIG["level"]["points_per_level"])
        self.recompute()
        self.hp = self.max_hp      # LevelService.applyLevel: 최대 HP 로 회복
        # MP 는 그대로 (레벨업 MP 회복 없음)

    def recompute(self):
        bonus = {}
        for g in self.gear:
            for k, v in g.items():
                bonus[k] = bonus.get(k, 0) + v
        c = self.c
        s = {}
        for st in ("STR", "DEX", "INT", "VIT", "WIS", "LUK"):
            s[st] = max(0, c["base_stats"].get(st, 0) + self.points[st] + round(bonus.get(st, 0)))
        self.s = s
        cid = self.cls_id
        mix = {"guardian": 0.6 * s["STR"] + 0.4 * s["VIT"], "berserker": s["STR"], "hunter": s["DEX"],
               "arcanist": s["INT"], "priest": 0.5 * s["INT"] + 0.5 * s["WIS"],
               "shadow": 0.7 * s["DEX"] + 0.3 * s["LUK"]}[cid]
        weapon = bonus.get("damage", 0) or 3.0
        self.ap = weapon * (1 + 0.02 * mix)
        lv = self.level
        self.max_hp = c["base_hp"] + c["per_level"]["hp"] * (lv - 1) + s["VIT"] * 8 + bonus.get("hp", 0)
        self.max_mp = c["base_mp"] + c["per_level"]["mp"] * (lv - 1) + s["INT"] * 3 + s["WIS"] * 2 + bonus.get("mp", 0)
        self.defense = s["VIT"] * 0.5 + bonus.get("defense", 0)
        self.crit = min(0.75, 0.05 + s["DEX"] * 0.0015 + s["LUK"] * 0.0025 + bonus.get("crit_chance", 0))
        self.crit_dmg = 1.5 + bonus.get("crit_damage", 0)
        self.atk_speed = max(-0.5, min(0.6, s["DEX"] * 0.004 + bonus.get("attack_speed", 0)))
        self.mana_regen = c["mana_regen"] + s["WIS"] * 0.05 + bonus.get("mana_regen", 0)
        self.heal_power = s["WIS"] * 1.5 + bonus.get("heal_power", 0)
        self.hp_regen = bonus.get("hp_regen", 0)
        self.dr = 0.10 if cid == "guardian" else 0.0
        self.block = bonus.get("block_chance", 0)
        self.hp = min(getattr(self, "hp", 0) or 0, self.max_hp)

    def summary(self):
        return dict(cls=self.cls_id, level=self.level, max_hp=round(self.max_hp), max_mp=round(self.max_mp),
                    ap=round(self.ap, 2), defense=round(self.defense, 1), crit=round(self.crit, 3),
                    basic_dps=round(self.basic_dps_nominal(), 1), stats=dict(self.s))

    def basic_period(self):
        if self.weapon_type == "bow":
            return 1.15                     # 끝까지 당김 1초 + 발사 간격
        base = self.weapon_as.get(self.weapon_type, WEAPON_AS[self.weapon_type])
        return 1.0 / (base * (1 + self.atk_speed))

    def basic_mult_nominal(self):
        if self.weapon_type == "bow":
            return 1.25 * 1.15              # 치명 화살 ×1.25, 매의 눈 ×1.15
        return 1.0

    def basic_dps_nominal(self):
        crit = 1 + self.crit * (self.crit_dmg - 1)
        return self.ap * self.basic_mult_nominal() * crit / self.basic_period()


# ───────────────────────────── 몹 ─────────────────────────────

class Mob:
    __slots__ = ("id", "d", "hp", "max_hp", "dmg", "defense", "ai", "interval", "next_attack", "skills", "ready",
                 "gready", "busy", "stun", "shield_until", "shield_red", "enraged", "first_hit", "xp", "is_add",
                 "summons", "ranged", "boss")

    def __init__(self, mob_id, hp_mult, dmg_mult, scn, floor, t, elite=False, is_add=False):
        d = MOBS[mob_id]
        self.id, self.d = mob_id, d
        fm = scn["mob_damage_mult"].get(floor, 1.0) if d.get("rank") != "add" else 1.0
        hp = d["hp"] * hp_mult
        dmg = d["damage"] * dmg_mult * fm
        de = d.get("defense", 0)
        xp = d.get("xp", 0)
        if elite:
            hp, dmg, de, xp = hp * 3.0, dmg * 1.35, de * 1.25, xp * 3.0
        self.hp = self.max_hp = max(1, round(hp))
        self.dmg, self.defense, self.xp = dmg, de, xp
        self.ai = d.get("ai", "melee")
        base_int = d.get("attack_interval", scn["attack_interval"].get(d.get("floor"), 1.2))
        iv = round(base_int * 20)
        if self.ai == "swarm":
            iv = int(iv * 0.85)
        self.interval = max(8, iv) / 20.0
        self.ranged = self.ai in ("ranged", "caster", "turret")
        if self.ranged:
            self.interval = max(30 / 20.0, self.interval + 16 / 20.0)
        self.next_attack = t + random.uniform(0.3, 1.2)
        self.skills = d.get("skills", [])
        self.ready = [t + s.get("cooldown", 0) * (0.3 + 0.4 * random.random()) for s in self.skills]
        self.gready = t
        self.busy = 0.0
        self.stun = 0.0
        self.shield_until = 0.0
        self.shield_red = 0.0
        self.enraged = False
        self.first_hit = any(s["type"] == "ambush" for s in self.skills)
        self.is_add = is_add
        self.summons = 0
        self.boss = False


PASSIVE = {"explode_on_death", "split_on_death", "enrage", "ambush", "aura"}


def dodge_p(w, prof):
    return prof["dodge_max"] * max(0.0, min(1.0, (w - 0.3) / 0.7))


# ───────────────────────────── 전투 (방 하나) ─────────────────────────────

class Fight:
    def __init__(self, pl, mobs, prof, diff, scn, floor, ctx_hp, ctx_dmg, potions, immortal=False, on_kill=None, n=1,
                 mana_potions=0, heal_frac=None):
        self.n = n
        self.mana_potions = mana_potions
        self.mpot_ready = 0.0
        self.heal_frac = heal_frac
        self.immortal = immortal
        self.on_kill = on_kill
        self.min_hp = pl.hp
        self.pl, self.mobs, self.prof, self.diff, self.scn, self.floor = pl, mobs, prof, diff, scn, floor
        self.ctx_hp, self.ctx_dmg = ctx_hp, ctx_dmg
        self.t = 0.0
        self.taken = 0.0
        self.dealt = 0.0
        self.potions = potions
        self.potions_used = 0
        self.pot_ready = 0.0
        self.skill_ready = 0.5
        self.next_hit = 0.3
        self.weaken_until = 0.0
        self.dead = False
        self.xp = 0.0
        self.kills = 0
        self.emergency_ready = 0.0
        self.emergency_until = 0.0
        self.dots = []              # (mob, dps, until)
        self.boss_ctl = None
        self.pending = []           # (time, fn)

    # 플레이어가 받는 피해
    def hurt(self, raw, true=False, frontal=True):
        pl = self.pl
        if raw <= 0 or self.dead:
            return
        dmg = raw
        if not true:
            dmg *= 100.0 / (100.0 + pl.defense)
        dr = pl.dr
        if pl.cls_id == "guardian" and self.t < self.emergency_until:
            dr += 0.20
        dmg *= 1 - min(0.9, dr)
        if not true and pl.block > 0 and frontal and random.random() < 0.7 and random.random() < pl.block:
            dmg *= 0.4
        pl.hp -= dmg
        self.taken += dmg
        if pl.hp < self.min_hp:
            self.min_hp = pl.hp
        if pl.cls_id == "guardian" and pl.hp < pl.max_hp * 0.30 and self.t >= self.emergency_ready:
            self.emergency_until = self.t + 5
            self.emergency_ready = self.t + 60
        if pl.hp <= 0 and not self.immortal:
            self.dead = True

    def heal(self, amt):
        pl = self.pl
        if pl.hp < pl.max_hp:
            pl.hp = min(pl.max_hp, pl.hp + amt)

    def windup(self, w):
        return max(0.5, w * self.diff["telegraph"])

    def hit_mob(self, m, mult, skill=False, guaranteed_crit=False, crit_bonus=0.0):
        pl = self.pl
        dmg = pl.ap * mult
        if self.t < self.weaken_until:
            dmg *= 0.8
        if pl.cls_id == "berserker":
            f = pl.hp / pl.max_hp
            if f < 0.5:
                dmg *= 1 + 0.25 * (0.5 - f) / 0.5
        if skill:
            dmg *= pl.skill_mult
        if guaranteed_crit or random.random() < pl.crit + crit_bonus:
            dmg *= pl.crit_dmg
        dmg *= 100.0 / (100.0 + m.defense)
        if self.t < m.shield_until:
            dmg *= 1 - m.shield_red
        if m.boss and self.boss_ctl and self.t < self.boss_ctl.vuln_until:
            dmg *= 1.5
        m.hp -= dmg
        self.dealt += dmg
        if m.hp <= 0:
            self.on_death(m)

    def on_death(self, m):
        if m not in self.mobs:
            return
        self.mobs.remove(m)
        self.kills += 1
        self.xp += m.xp
        if self.on_kill:
            self.on_kill(m, self)
        for s in m.skills:
            if s["type"] == "explode_on_death":
                p = s.get("params", {})
                w = self.windup(p.get("delay", 0.6))
                if random.random() >= dodge_p(w, self.prof) and (STYLE[self.pl.cls_id] == "melee" or random.random() < 0.4):
                    self.hurt(m.dmg * p.get("damage", 1.0))
                    if p.get("effect") == "poison":
                        self.dots.append((1.0, self.t + p.get("effect_duration", 3)))
        if m.boss:
            self.boss_dead = True

    def pick_target(self):
        alive = [m for m in self.mobs if m.hp > 0]
        if not alive:
            return None
        if self.prof["target"] == "lowest":
            # 보스가 있으면 쫄 먼저
            return min(alive, key=lambda m: (m.boss, m.hp))
        if not hasattr(self, "_tgt") or self._tgt not in alive or random.random() < 0.01:
            self._tgt = random.choice(alive)
        return self._tgt

    def others(self, tgt):
        return [m for m in self.mobs if m is not tgt and m.hp > 0]

    # ── 플레이어 행동 ──
    def player_act(self):
        pl, prof, t = self.pl, self.prof, self.t
        pl.mp = min(pl.max_mp, pl.mp + pl.mana_regen * DT)
        self.heal((0.25 + pl.hp_regen) * DT)    # 바닐라 자연 회복 1HP/4초 + hp_regen
        # 지속 피해
        for i in range(len(self.dots) - 1, -1, -1):
            dps, until = self.dots[i]
            if t >= until:
                self.dots.pop(i)
            else:
                self.hurt(dps * DT, true=True)
        # 물약
        if self.potions > 0 and t >= self.pot_ready and pl.hp < pl.max_hp * prof["potion_thr"]:
            self.potions -= 1
            self.potions_used += 1
            self.heal(pl.max_hp * (self.heal_frac or self.scn["minor_heal"]))
            self.pot_ready = t + 12
        # 마나 물약 (시작 꾸러미 5병): 스킬 마나가 모자라면
        sk0 = pl.c["skills"][0]
        if self.mana_potions > 0 and t >= self.mpot_ready and pl.mp < sk0["mana"] and self.mobs:
            self.mana_potions -= 1
            pl.mp = min(pl.max_mp, pl.mp + pl.max_mp * (self.heal_frac or 0.25))
            self.mpot_ready = t + 12
        tgt = self.pick_target()
        if tgt is None:
            return
        cid = pl.cls_id
        # 직업 스킬 (Lv1 스킬만 — 이 구간은 Lv1~7 이라 2번째 스킬은 Lv8)
        sk = pl.c["skills"][0]
        cd = sk["cooldown"] * 0.9
        if t >= self.skill_ready and pl.mp >= sk["mana"]:
            p = dict(sk["params"])
            p.update(self.scn.get("skill_params", {}).get(cid, {}))
            used = True
            if cid == "guardian":
                hits = [tgt] + [m for m in self.others(tgt) if random.random() < 0.35]
                for m in hits:
                    self.hit_mob(m, p["damage"], skill=True)
                    if not m.boss:
                        m.stun = max(m.stun, t + p["stun"])
            elif cid == "berserker":
                hits = [tgt] + [m for m in self.others(tgt) if random.random() < 0.5]
                for m in hits:
                    self.hit_mob(m, p["damage"], skill=True)
                    if m.hp > 0:
                        self.mob_dots.append((m, pl.ap * p["bleed_ratio"], t + p["bleed_duration"]))
            elif cid == "hunter":
                hits = [tgt] + [m for m in self.others(tgt)[:3] if random.random() < 0.3]
                for i, m in enumerate(hits):
                    self.hit_mob(m, p["damage"] * (1 - p["falloff"]) ** i, skill=True)
            elif cid == "arcanist":
                self.hit_mob(tgt, p["damage"], skill=True)
            elif cid == "priest":
                if pl.hp < pl.max_hp * 0.75:
                    self.heal(pl.max_hp * p["heal"] + pl.heal_power)
                    pl.mp += 2
                else:
                    used = False
            elif cid == "shadow":
                back = random.random() < prof["back_rate"]
                self.hit_mob(tgt, p["back_damage"] if back else p["damage"], skill=True, guaranteed_crit=back)
            if used:
                pl.mp -= sk["mana"]
                self.skill_ready = t + cd
                return
        # 기본 공격
        if t >= self.next_hit:
            self.next_hit = t + pl.basic_period()
            up = prof["uptime"]
            if STYLE[pl.cls_id] == "kite" and pl.weapon_type != "bow":
                up *= 0.45          # 근접 무기로 거리 벌리며 싸우면 평타 기회가 절반 이하
            if random.random() < up:
                if pl.weapon_type == "bow":
                    full = random.random() < prof["full_draw"]
                    mult = 1.25 * 1.15 if full else 0.75
                    far = 0.08 if random.random() < 0.3 else 0.0
                    self.hit_mob(tgt, mult, crit_bonus=far)
                    if full:
                        pl.mp = min(pl.max_mp, pl.mp + 3)
                else:
                    cb = 0.20 if (pl.cls_id == "shadow" and random.random() < prof["back_rate"]) else 0.0
                    self.hit_mob(tgt, 1.0, crit_bonus=cb)
                    if pl.cls_id == "berserker":
                        pl.mp = min(pl.max_mp, pl.mp + 3)

    # ── 몹 행동 ──
    def mob_act(self, m):
        t, prof, pl = self.t, self.prof, self.pl
        if m.hp <= 0 or t < m.stun:
            return
        if m.boss:
            return
        dmg = m.dmg * (1.3 if m.enraged else 1.0)
        for s in m.skills:
            if s["type"] == "enrage" and not m.enraged and m.hp < m.max_hp * s["params"].get("threshold", 0.3):
                m.enraged = True
        if t < m.busy:
            return
        kite = STYLE[pl.cls_id] == "kite"
        # 스킬
        if t >= m.gready and int(t / DT) % 4 == 0:
            for i, s in enumerate(m.skills):
                ty = s["type"]
                if ty in PASSIVE or t < m.ready[i]:
                    continue
                if not self.cast(m, s, dmg, kite):
                    continue
                m.ready[i] = t + max(1.0, s.get("cooldown", 1))
                m.gready = t + 1.0
                return
        # 기본 공격
        if t >= m.next_attack:
            m.next_attack = t + m.interval
            if m.ranged:
                if random.random() < prof["proj_hit"]:
                    self.hurt(dmg * 0.75)
            else:
                e = prof["e_kite"] if kite else prof["e_melee"]
                if random.random() < e:
                    mult = 1.8 if m.first_hit else 1.0
                    m.first_hit = False
                    self.hurt(dmg * mult)
        # 오라
        for s in m.skills:
            if s["type"] == "aura":
                p = s["params"]
                if p.get("effect") == "damage" and int(t / DT) % int(p.get("interval", 2) / DT) == 0:
                    if not kite or random.random() < 0.3:
                        self.hurt(m.dmg * p.get("amount", 0.25), true=True)

    def cast(self, m, s, dmg, kite):
        ty, p = s["type"], s.get("params", {})
        t, prof = self.t, self.prof
        w = self.windup(p.get("windup", 0.6))
        m.busy = t + w + 0.4
        if ty in ("leap", "cleave", "charge", "slam", "snare", "dive", "burrow", "pull"):
            if ty == "cleave" and kite and random.random() < 0.6:
                return True
            if random.random() >= dodge_p(w, prof):
                self.pending.append((t + w, lambda d=dmg * p.get("damage", 1.0): self.hurt(d)))
                if ty == "dive" and p.get("effect") == "weaken":
                    self.weaken_until = t + w + p.get("effect_duration", 4)
            if ty == "charge" and p.get("stun", 0) == 0:
                m.busy += 1.0
            return True
        if ty == "projectile":
            cnt = p.get("count", 1)
            exp_hits = 1 + (cnt - 1) * 0.3
            hit = random.random() >= dodge_p(w + 0.3, prof)
            if hit:
                d = dmg * p.get("damage", 1.0) * exp_hits
                if "blast_damage" in p and random.random() >= dodge_p(self.windup(p.get("blast_delay", 0.9)), prof):
                    d += dmg * p["blast_damage"]
                self.pending.append((t + w + 0.4, lambda d=d: self.hurt(d)))
                if p.get("effect") == "poison":
                    self.dots.append((1.0, t + w + p.get("effect_duration", 3)))
            return True
        if ty in ("breath", "beam"):
            ticks = p.get("duration", 1.5) / p.get("tick", 0.5)
            frac = 1 - 0.7 * dodge_p(w, prof)
            if kite and ty == "breath":
                frac *= 0.5
            d = dmg * p.get("damage_per_tick", 0.4) * ticks * frac
            self.pending.append((t + w, lambda d=d: self.hurt(d)))
            m.busy = t + w + p.get("duration", 1.5)
            return True
        if ty == "life_drain":
            ticks = p.get("duration", 3) / p.get("tick", 0.5)
            frac = 1 - 0.5 * prof["dodge_max"]
            d = dmg * p.get("damage", 0.5) * ticks * frac
            self.pending.append((t + 0.5, lambda d=d: self.hurt(d)))
            m.hp = min(m.max_hp, m.hp + d * p.get("heal_ratio", 1.0) * 0.5)
            m.busy = t + p.get("duration", 3)
            return True
        if ty == "summon":
            ov = self.scn.get("summon_solo", {}).get(m.id)
            if ov:
                p = dict(p)
                p.update(ov)
            if self.n == 1 and ("solo_count" in p or "solo_max_alive" in p):   # mobs.yml solo_count (현재 코드)
                p = dict(p)
                p["count"] = p.get("solo_count", p.get("count", 2))
                p["max_alive"] = p.get("solo_max_alive", p.get("max_alive", 4))
            alive = sum(1 for x in self.mobs if x.is_add and x.hp > 0)
            if alive >= p.get("max_alive", 4):
                return False
            for _ in range(min(p.get("count", 2), p.get("max_alive", 4) - alive)):
                self.mobs.append(Mob(p["mob"], self.ctx_hp, self.ctx_dmg, self.scn, self.floor, t, is_add=True))
            m.busy = t + 1.0
            return True
        if ty == "shield":
            m.shield_until = t + p.get("duration", 3)
            m.shield_red = p.get("reduction", 0.6)
            m.busy = t + 0.5
            return True
        if ty == "heal_allies":
            hurt = [x for x in self.mobs if x.hp < x.max_hp * 0.8]
            if not hurt:
                return False
            for x in self.mobs:
                x.hp = min(x.max_hp, x.hp + x.max_hp * p.get("amount", 0.1))
            return True
        if ty == "buff_allies":
            for x in self.mobs:
                x.dmg *= 1.0  # 근사: 무시 (지속 8초 +20%) → 아래에서 평균 효과 반영 안 함
            return True
        if ty == "debuff":
            if random.random() >= dodge_p(w, prof):
                if p.get("effect") == "weaken":
                    self.weaken_until = t + w + p.get("duration", 5)
            return True
        if ty == "blink":
            m.busy = t + 0.3
            return True
        return False

    def run(self, max_t=600, boss_ctl=None):
        self.mob_dots = []
        self.boss_ctl = boss_ctl
        self.boss_dead = False
        while self.t < max_t:
            self.t += DT
            t = self.t
            # 예약된 피해
            if self.pending:
                due = [x for x in self.pending if x[0] <= t]
                if due:
                    self.pending = [x for x in self.pending if x[0] > t]
                    for _, fn in due:
                        fn()
            # 몹 출혈
            for i in range(len(self.mob_dots) - 1, -1, -1):
                m, dps, until = self.mob_dots[i]
                if t >= until or m.hp <= 0:
                    self.mob_dots.pop(i)
                else:
                    m.hp -= dps * DT
                    self.dealt += dps * DT
                    if m.hp <= 0:
                        self.on_death(m)
            self.player_act()
            if boss_ctl:
                boss_ctl.tick(self)
            for m in list(self.mobs):
                self.mob_act(m)
            if self.dead:
                return False
            if boss_ctl:
                if self.boss_dead:
                    return True
            elif not self.mobs:
                # 남은 예약 피해 처리
                for _, fn in self.pending:
                    fn()
                self.pending = []
                return not self.dead
        return not self.dead


# ───────────────────────────── 보스 1층 그로브 ─────────────────────────────

class GroveCtl:
    def __init__(self, fight, diff, scn, n=1):
        d = BOSSES["floor01_moss_warden"]
        self.d = d
        self.fight = fight
        self.mob = None
        self.diff = diff
        self.pats = d["patterns"]
        self.cd_mult = diff["cd_mult"]
        self.extra = diff["extra"]
        self.ready = {}
        self.busy = 0.0
        self.last = None
        self.next_allowed = 0.0
        self.next_attack = 1.0
        self.stun_until = 0.0
        self.vuln_until = 0.0
        self.pillars = d["patterns"]["moss_pillars"]["count"]
        self.phase = 1
        self.set_phase(1, 0.0)
        self.n = n
        self.stats = dict(stuns=0, charges_hit=0, basic_hits=0)

    def set_phase(self, ph, t):
        self.phase = ph
        for k in self.d["rotation"][ph]:
            if k not in self.ready:
                cd = self.pats[k].get("cooldown", 10)
                self.ready[k] = t + cd * self.cd_mult * 0.5

    def tick(self, f):
        m = self.mob
        t = f.t
        if m.hp <= 0:
            return
        frac = m.hp / m.max_hp
        ph = 1 if frac > 0.6 else (2 if frac > 0.25 else 3)
        if ph != self.phase:
            self.set_phase(ph, t)
        if t < self.stun_until:
            return
        enrage = 1.3 if (self.phase >= 3 and self.pillars <= 0) else 1.0
        dmg = m.dmg * enrage
        cdm = self.cd_mult * (0.9 if self.phase >= 3 else 1.0)
        prof = f.prof
        kite = STYLE[f.pl.cls_id] == "kite"
        if t >= self.busy and t >= self.next_allowed:
            cands = [k for k in self.d["rotation"][self.phase] if t >= self.ready[k]]
            if len(cands) > 1 and self.last in cands:
                cands.remove(self.last)
            if cands:
                k = random.choice(cands)
                p = self.pats[k]
                self.ready[k] = t + p.get("cooldown", 10) * cdm
                self.last = k
                busy = self.pattern(f, k, p, dmg, kite)
                self.busy = t + busy
                self.next_allowed = t + max(busy, 1.2)
                return
        if t >= self.busy and t >= self.next_attack:
            self.next_attack = t + f.scn["boss_attack_interval"]
            e = prof["boss_e_kite"] if kite else prof["boss_e_melee"]
            if random.random() < e:
                self.stats["basic_hits"] += 1
                f.pending.append((t + 0.15, lambda d=dmg: f.hurt(d)))

    def pattern(self, f, k, p, dmg, kite):
        t, prof = f.t, f.prof
        w = f.windup(p.get("windup", 1.0))
        if k == "vine_lash":
            if random.random() >= dodge_p(w, prof) and not (kite and random.random() < 0.5):
                f.pending.append((t + w, lambda d=dmg * p["damage"]: f.hurt(d)))
            return w + 0.4
        if k == "root_snare":
            cnt = p.get("count_base", 2) + self.extra
            # 솔로: 원 여러 개 중 하나라도 밟으면. 개수가 늘수록 피하기 어렵다
            pd = dodge_p(w, prof) ** (1 + 0.25 * (cnt - 2))
            if random.random() >= pd:
                f.pending.append((t + w, lambda d=dmg * p["damage"]: f.hurt(d)))
            return 0.8
        if k == "rampage_charge":
            mark = max(0.5, p.get("mark_time", 2.0) * self.diff["telegraph"])
            n_charges = 2 if self.phase >= 3 else 1
            total = 0.0
            for i in range(n_charges):
                at = t + mark + i * 1.0
                if random.random() >= dodge_p(mark, prof) * 0.95:
                    self.stats["charges_hit"] += 1
                    f.pending.append((at + 0.8, lambda d=dmg * p["damage"]: f.hurt(d)))
                elif self.pillars > 0 and random.random() < prof["pillar"]:
                    self.pillars -= 1
                    self.stats["stuns"] += 1
                    st = p.get("stun", 4.0)
                    self.stun_until = max(self.stun_until, at + 0.8 + st)
                    self.vuln_until = max(self.vuln_until, at + 0.8 + st)
                    total = max(total, mark + 0.8 + st)
                    break
            return max(total, mark + 0.8 + p.get("wall_recover", 1.0) + (1.0 if n_charges > 1 else 0))
        if k == "spore_burst":
            pd = dodge_p(w, prof) * (1.0 if kite else 0.85)
            if kite:
                pd = max(pd, 0.8)
            if random.random() >= pd:
                f.pending.append((t + w, lambda d=dmg * p["damage"]: f.hurt(d)))
                f.dots.append((1.0, t + w + p.get("effect_duration", 4)))
            return w + 0.5
        if k == "sproutling_call":
            alive = sum(1 for x in f.mobs if x.is_add and x.hp > 0)
            cnt = p.get("count_base", 2) + self.extra
            for _ in range(max(0, min(cnt, p.get("max_alive", 8) - alive))):
                f.mobs.append(Mob(p["add"], f.ctx_hp, f.ctx_dmg, f.scn, 1, t, is_add=True))
            return 1.5
        return 1.0


# ───────────────────────────── 층 완주 ─────────────────────────────

def roll_density(floor):
    a, b = FLOORS[floor]["mob_density"]
    return random.randint(a, b)


def room_count(floor, scn, n=1):
    base = roll_density(floor)
    mult = scn["party_mob_count"].get(n, 1.0)
    c = int(math.floor(base * mult * (1 + scn["mob_count_per_member"] * (n - 1)) + 0.5))
    return max(1, min(DUNGEON["max_mobs_per_room"], c))


def make_room_mobs(floor, scn, ctx_hp, ctx_dmg, kind="combat", n=1):
    fl = FLOORS[floor]
    t = 0.0
    mobs = []
    if kind == "combat":
        for _ in range(room_count(floor, scn, n)):
            mid = random.choice(fl["mobs"])
            elite = random.random() < scn["elite_variant"]
            mobs.append(Mob(mid, ctx_hp, ctx_dmg, scn, floor, t, elite=elite))
    elif kind == "elite":
        mobs.append(Mob(fl["elite"], ctx_hp, ctx_dmg, scn, floor, t))
        adds = 2 + random.randint(0, 1)
        if scn.get("elite_adds_scaled"):
            adds = int(math.floor(adds * scn["party_mob_count"].get(n, 1.0) + 0.5))
        for _ in range(adds):
            mobs.append(Mob(random.choice(fl["mobs"]), ctx_hp, ctx_dmg, scn, floor, t))
    elif kind == "mimic":
        for _ in range(DUNGEON["treasure"]["mimic_mobs"]):
            mobs.append(Mob(random.choice(fl["mobs"]), ctx_hp, ctx_dmg, scn, floor, t))
    return mobs


def heal_frac(level, scn):
    """그 레벨에 흔히 들고 다니는 치유 물약 회복량: 하급 25% · 치유(Lv15) 40% · 상급(Lv30) 60%."""
    if level >= 30:
        return 0.6
    if level >= 15:
        return 0.4
    return scn["minor_heal"]


def xp_curve(lv):
    L = CONFIG["level"]
    return round(L["xp_a"] * lv ** L["xp_exp"] + L["xp_b"])


def avg_mob_xp(floor):
    return sum(MOBS[m]["xp"] for m in FLOORS[floor]["mobs"]) / len(FLOORS[floor]["mobs"])


def potion_expect(table_chance, drop_mult):
    """potions_t1 하위 테이블 한 번: 치유 물약 개수 기대값을 정수로 굴림."""
    if random.random() < min(1.0, table_chance * drop_mult):
        if random.random() < min(1.0, 0.65 * drop_mult):
            return random.randint(1, 2)
    return 0


class Run:
    """층 하나를 솔로로 처음부터 끝까지."""

    def __init__(self, cls_id, level, prof_id, diff_id, scn, floor=1, potions=None, extra_gear=None, n=1):
        self.pl = Player(cls_id, level, scn, extra_gear)
        self.pl.skill_mult = scn["class_skill_mult"].get(cls_id, 1.0)
        self.prof = PROFILES[prof_id]
        self.diff = diff_at(scn, diff_id, floor)
        self.diff_id = diff_id
        self.scn = scn
        self.floor = floor
        self.n = n
        party_hp = 1 + CONFIG["party"]["hp_per_member"] * (n - 1)
        party_dmg = 1 + CONFIG["party"]["dmg_per_member"] * (n - 1)
        if n == 1:
            party_hp *= scn["solo_hp"]
            party_dmg *= scn["solo_damage"]
        self.ctx_hp = self.diff["hp"] * party_hp
        self.ctx_dmg = self.diff["damage"] * party_dmg
        self.potions = scn["starter_potions"] if potions is None else potions
        self.mana_potions = scn.get("mana_potions", 0)
        self.xp = 0
        self.log = []
        self.rested = False
        self.gold = 0.0
        self.time = 0.0

    def gain_xp(self, amount):
        self.xp += amount * self.diff["xp"]
        while self.xp >= xp_curve(self.pl.level):
            self.xp -= xp_curve(self.pl.level)
            self.pl.level_up()
            self.log.append(("levelup", self.pl.level))

    def walk(self, seconds=30):
        self.time += seconds
        pl = self.pl
        pl.hp = min(pl.max_hp, pl.hp + (0.25 + pl.hp_regen) * seconds)
        pl.mp = min(pl.max_mp, pl.mp + pl.mana_regen * seconds)

    def traps(self):
        # 복도 함정: 1층 종류 평균 기준 9% (가시 12·화살 10·독안개 ~6·경보 0) × (1+3%×(층−1)) × 난이도 damage
        n = self.prof["traps"]
        k = int(n) + (1 if random.random() < n - int(n) else 0)
        for _ in range(k):
            pct = min(0.5, 0.09 * (1 + 0.03 * (self.floor - 1)) * self.diff["damage"] * self.scn["trap_mult"])
            self.pl.hp -= self.pl.max_hp * pct
            if self.pl.hp <= 0:
                return False
        return True

    def fight(self, mobs, boss=False):
        f = Fight(self.pl, mobs, self.prof, self.diff, self.scn, self.floor, self.ctx_hp, self.ctx_dmg, self.potions,
                  on_kill=self.kill_reward, n=self.n, mana_potions=self.mana_potions, heal_frac=heal_frac(self.pl.level, self.scn))
        ctl = None
        if boss:
            ctl = GroveCtl(f, self.diff, self.scn, self.n)
            d = BOSSES["floor01_moss_warden"]
            bm = Mob("moss_crawler", 1, 1, self.scn, 1, 0)  # 틀만 빌림
            bm.id, bm.boss = "boss", True
            bm.hp = bm.max_hp = d["hp"] * self.ctx_hp
            bm.dmg, bm.defense, bm.xp, bm.skills = d["damage"] * self.ctx_dmg, d["defense"], d["xp"], []
            ctl.mob = bm
            f.mobs.insert(0, bm)
        hp0 = self.pl.hp
        ok = f.run(max_t=900, boss_ctl=ctl)
        self.time += f.t
        self.potions = f.potions
        self.mana_potions = f.mana_potions
        rec = dict(ok=ok, t=round(f.t, 1), taken=round(f.taken), taken_pct=round(f.taken / self.pl.max_hp, 3),
                   hp_before=round(hp0), hp_after=round(max(0, self.pl.hp)), pots=f.potions_used, lv=self.pl.level,
                   mobs=len(mobs))
        if ctl:
            rec.update(ctl.stats)
        return ok, rec

    def kill_reward(self, m, f):
        """처치 즉시: 경험치(레벨업이면 그 자리에서 최대 HP 회복) · 골드 · 물약 드롭."""
        comp = 1.0
        if self.scn.get("solo_reward_comp") and not m.boss and not m.is_add:
            comp = 1.0 / self.scn["party_mob_count"].get(self.n, 1.0)
        self.gain_xp(m.xp * comp)
        if m.boss:
            g = BOSSES["floor01_moss_warden"]["gold"]
        else:
            g = m.d.get("gold", [0, 0])
        self.gold += comp * (g[0] + g[1]) / 2 * (2.5 if (m.max_hp > m.d.get("hp", 0) * self.ctx_hp * 2 and not m.boss) else 1)
        if not m.boss and not m.is_add:
            f.potions += potion_expect(0.03 * self.scn["potion_drop_mult"], self.diff["drop"])

    def run_floor(self):
        """반환: dict(cleared, died_at, rooms[], boss{})"""
        rc = FLOORS[self.floor]["rooms"]
        order = ["C"] * rc.get("combat", 6)
        order.insert(2, "T")
        order.insert(4, "G")
        order.insert(len(order) // 2 + 1, "R")
        for _ in range(rc.get("elite", 1)):
            order.insert(len(order) - 1, "E")
        order.append("B")
        rooms = []
        for i, kind in enumerate(order):
            if i > 0:
                self.walk(30)
                if i % 3 == 2 and not self.traps():
                    return dict(cleared=False, died_at=f"함정({i})", rooms=rooms, level=self.pl.level)
            if kind == "C":
                ok, rec = self.fight(make_room_mobs(self.floor, self.scn, self.ctx_hp, self.ctx_dmg, "combat", self.n))
                rec["kind"] = "전투"
                rooms.append(rec)
                if not ok:
                    return dict(cleared=False, died_at=f"전투방{i}", rooms=rooms, level=self.pl.level)
                if self.scn["room_clear_heal"] > 0:
                    self.pl.hp = min(self.pl.max_hp, self.pl.hp + self.pl.max_hp * self.scn["room_clear_heal"])
            elif kind == "E":
                ok, rec = self.fight(make_room_mobs(self.floor, self.scn, self.ctx_hp, self.ctx_dmg, "elite", self.n))
                rec["kind"] = "엘리트"
                rooms.append(rec)
                if not ok:
                    return dict(cleared=False, died_at="엘리트방", rooms=rooms, level=self.pl.level)
                self.potions += potion_expect(0.25, self.diff["drop"])
                if self.scn["room_clear_heal"] > 0:
                    self.pl.hp = min(self.pl.max_hp, self.pl.hp + self.pl.max_hp * self.scn["room_clear_heal"])
            elif kind == "T":
                for _ in range(DUNGEON["treasure"]["chests"]):
                    if random.random() < DUNGEON["treasure"]["mimic_chance"]:
                        ok, rec = self.fight(make_room_mobs(self.floor, self.scn, self.ctx_hp, self.ctx_dmg, "mimic"))
                        rec["kind"] = "미믹"
                        rooms.append(rec)
                        if not ok:
                            return dict(cleared=False, died_at="보물방 미믹", rooms=rooms, level=self.pl.level)
                    self.gold += 30
                    for _ in range(2):
                        self.potions += potion_expect(0.45, self.diff["drop"])
                # 미로 상자 2~3개 (나무 위주)
                for _ in range(2):
                    self.gold += 23
                    self.potions += potion_expect(0.5, self.diff["drop"])
            elif kind == "G":
                self.gain_xp(avg_mob_xp(self.floor) * 10)
                self.gold += 48
                for _ in range(2):
                    self.potions += potion_expect(0.35, self.diff["drop"])
            elif kind == "R":
                pl = self.pl
                pl.hp = min(pl.max_hp, pl.hp + pl.max_hp * self.scn["rest_heal"])
                pl.mp = min(pl.max_mp, pl.mp + pl.max_mp * self.scn["rest_heal"])
            elif kind == "B":
                if self.floor != 1:
                    return dict(cleared=True, died_at=None, rooms=rooms, level=self.pl.level, boss=None)
                ok, rec = self.fight([], boss=True)
                rec["kind"] = "보스"
                if not ok:
                    return dict(cleared=False, died_at="보스", rooms=rooms, level=self.pl.level, boss=rec)
                return dict(cleared=True, died_at=None, rooms=rooms, level=self.pl.level, boss=rec)
        return dict(cleared=True, died_at=None, rooms=rooms, level=self.pl.level)


# ───────────────────────────── 실험 ─────────────────────────────

def single_room_stats(cls_id, level, prof_id, diff_id, scn, floor, runs, extra_gear=None, kind="combat"):
    """만피 상태에서 전투방 하나: 받는 피해 % 분포, 시간, 사망률(물약 없이)."""
    taken, times, deaths, counts, net = [], [], 0, [], []
    for _ in range(runs):
        r = Run(cls_id, level, prof_id, diff_id, scn, floor, potions=0, extra_gear=extra_gear)
        mobs = make_room_mobs(floor, scn, r.ctx_hp, r.ctx_dmg, kind)
        counts.append(len(mobs))
        # 죽지 않게 해서 '받는 피해 총량' 을 잰다 (만피 시작, 물약 없음, 자연 회복만)
        f = Fight(r.pl, mobs, r.prof, r.diff, scn, floor, r.ctx_hp, r.ctx_dmg, 0, immortal=True)
        f.run(max_t=900)
        pct = f.taken / r.pl.max_hp
        taken.append(pct)
        net.append((r.pl.max_hp - r.pl.hp) / r.pl.max_hp)
        times.append(f.t)
        if f.min_hp <= 0:
            deaths += 1
    taken.sort()
    net.sort()
    return dict(mean_taken_pct=round(sum(taken) / runs, 3), mean_net_loss_pct=round(sum(net) / runs, 3),
                p90_net_loss_pct=round(net[int(runs * 0.9)], 3),
                death_rate_fullhp=round(deaths / runs, 3), mean_time=round(sum(times) / runs, 1),
                mean_mobs=round(sum(counts) / runs, 2))


def boss_stats(cls_id, level, prof_id, diff_id, scn, runs, potions, extra_gear=None):
    res = []
    for _ in range(runs):
        r = Run(cls_id, level, prof_id, diff_id, scn, 1, potions=potions, extra_gear=extra_gear)
        r.pl.hp = r.pl.max_hp
        ok, rec = r.fight([], boss=True)
        res.append(rec)
    win = sum(1 for x in res if x["ok"]) / runs
    wins = [x for x in res if x["ok"]] or res
    return dict(win_rate=round(win, 3), mean_time=round(sum(x["t"] for x in wins) / len(wins), 1),
                mean_taken_pct=round(sum(x["taken_pct"] for x in res) / runs, 2),
                mean_pots=round(sum(x["pots"] for x in res) / runs, 2),
                stuns=round(sum(x.get("stuns", 0) for x in res) / runs, 2))


def floor_stats(cls_id, prof_id, diff_id, scn, runs, floor=1, level=1, potions=None, extra_gear=None):
    cleared, died = 0, {}
    lv_end, boss_t, pots_left = [], [], []
    for _ in range(runs):
        r = Run(cls_id, level, prof_id, diff_id, scn, floor, potions=potions, extra_gear=extra_gear)
        out = r.run_floor()
        if out["cleared"]:
            cleared += 1
            if out.get("boss"):
                boss_t.append(out["boss"]["t"])
            pots_left.append(r.potions)
        else:
            died[out["died_at"]] = died.get(out["died_at"], 0) + 1
        lv_end.append(out["level"])
    top = sorted(died.items(), key=lambda x: -x[1])[:3]
    return dict(clear_rate=round(cleared / runs, 3), level_end=round(sum(lv_end) / runs, 1),
                boss_time=round(sum(boss_t) / len(boss_t), 1) if boss_t else None,
                deaths_top=[(k, round(v / runs, 3)) for k, v in top])


def campaign(cls_id, prof_id, diff_id, scn, max_attempts=15, stock=8, price=20, floor=1):
    """처음 접속(Lv1, 0골드)부터 1층을 깰 때까지 반복 도전. 죽어도 레벨·경험치·골드는 남는다(GDD §2.6).
    도전 사이에 마을 상인에게서 하급 치유 물약(20골드)을 stock 개까지 산다."""
    level, xp, gold = 1, 0.0, 0.0
    potions = scn["starter_potions"]
    total_t = 0.0
    for attempt in range(1, max_attempts + 1):
        while potions < stock and gold >= price:
            gold -= price
            potions += 1
        r = Run(cls_id, level, prof_id, diff_id, scn, floor, potions=potions)
        r.xp = xp
        out = r.run_floor()
        level, xp, potions = r.pl.level, r.xp, r.potions
        gold += r.gold
        total_t += r.time + 60       # 마을 왕복·정비 1분
        if out["cleared"]:
            return dict(cleared=True, attempts=attempt, level=level, minutes=round(total_t / 60, 1))
    return dict(cleared=False, attempts=max_attempts, level=level, minutes=round(total_t / 60, 1))


# 층 진입 때 '그쯤이면 흔히 갖춘' 장비 (드롭·제작 기준 가정): 2층 = 1층 Lv3 일반 무기 + 이끼 반지,
# 3층 = 2층 Lv8 고급 무기 + 나그네 방어구 4종(2층 고급) + 이끼 반지
GEAR_BY_FLOOR = {
    1: {},
    2: {"guardian": ["mossback_warhammer", "moss_band"], "berserker": ["rootbound_scythe", "moss_band"],
        "hunter": ["mossvine_hornbow", "moss_band"], "arcanist": ["wayfarer_spiral_staff", "moss_band"],
        "priest": ["grove_chalice", "moss_band"], "shadow": ["corridor_katar", "moss_band"]},
    3: {c: [w, "moss_band", "wayfarer_helm", "wayfarer_chest", "wayfarer_legs", "wayfarer_boots"] for c, w in
        {"guardian": "silkguard_falchion", "berserker": "silkspan_glaive", "hunter": "skitter_bladebow",
         "arcanist": "miners_fork_staff", "priest": "miners_bell_scepter", "shadow": "silk_sickle"}.items()},
}


def campaign_floors(cls_id, prof_id, diff_id, scn, floors=(1, 2, 3), max_attempts=15, stock=8, price=20):
    """1층부터 차례로: 층마다 깰 때까지 반복 (2·3층 보스는 방 전투만 근사 — 보스 미포함)."""
    level, xp, gold = 1, 0.0, 0.0
    potions = scn["starter_potions"]
    rec = []
    for fl in floors:
        total_t = 0.0
        lv_in = level
        for attempt in range(1, max_attempts + 1):
            while potions < stock and gold >= price:
                gold -= price
                potions += 1
            r = Run(cls_id, level, prof_id, diff_id, scn, fl, potions=potions,
                    extra_gear=GEAR_BY_FLOOR[fl].get(cls_id))
            r.xp = xp
            out = r.run_floor()
            level, xp, potions = r.pl.level, r.xp, r.potions
            gold += r.gold
            total_t += r.time + 60
            if out["cleared"]:
                if scn.get("first_clear_xp", 0) > 0:
                    lo, hi = FLOORS[fl]["level_range"]
                    need = sum(xp_curve(l) for l in range(lo, hi))
                    r.gain_xp(need * scn["first_clear_xp"] / r.diff["xp"])
                    level, xp = r.pl.level, r.xp
                break
        else:
            rec.append(dict(floor=fl, cleared=False, attempts=max_attempts, level_in=lv_in, level_out=level,
                            minutes=round(total_t / 60, 1)))
            return rec
        rec.append(dict(floor=fl, cleared=True, attempts=attempt, level_in=lv_in, level_out=level,
                        minutes=round(total_t / 60, 1)))
    return rec


def campaign_floors_stats(cls_id, prof_id, diff_id, scn, runs):
    res = [campaign_floors(cls_id, prof_id, diff_id, scn) for _ in range(runs)]
    out = {}
    for fl in (1, 2, 3):
        rows = [r[fl - 1] for r in res if len(r) >= fl]
        if not rows:
            out[fl] = dict(reached=0.0)
            continue
        ok = [x for x in rows if x["cleared"]]
        att = sorted(x["attempts"] for x in rows)
        out[fl] = dict(reached=round(len(rows) / runs, 2), cleared=round(len(ok) / runs, 2),
                       median_attempts=att[len(att) // 2],
                       level_in=round(sum(x["level_in"] for x in rows) / len(rows), 1),
                       level_out=round(sum(x["level_out"] for x in ok) / len(ok), 1) if ok else None,
                       minutes=round(sum(x["minutes"] for x in ok) / len(ok), 1) if ok else None)
    return out


def campaign_stats(cls_id, prof_id, diff_id, scn, runs, max_attempts=15):
    res = [campaign(cls_id, prof_id, diff_id, scn, max_attempts) for _ in range(runs)]
    ok = [x for x in res if x["cleared"]]
    att = sorted(x["attempts"] for x in res)
    return dict(clear_within=round(len(ok) / runs, 3), median_attempts=att[len(att) // 2],
                first_try=round(sum(1 for x in res if x["cleared"] and x["attempts"] == 1) / runs, 3),
                level_at_clear=round(sum(x["level"] for x in ok) / len(ok), 1) if ok else None,
                minutes=round(sum(x["minutes"] for x in ok) / len(ok), 1) if ok else None)


def main():
    print("전체 실험은 run_all.py 로 돌린다 (병렬, results.json / results.md 생성).", file=sys.stderr)


if __name__ == "__main__":
    main()
