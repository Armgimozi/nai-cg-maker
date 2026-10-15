#!/usr/bin/env python3
"""
TASK E — 난이도 시뮬레이터 (0.3.4 r4 sim 위에 새 전투 모델을 얹음).

  ce_simbase.py = design/r4/sim.py 복사본 (REPO = 지금 repo, 0.3.4 config 값 그대로) — 고치지 않는다.
  여기서 바꾸는 것 (OLD·NEW 둘 다에 똑같이 — 비교가 공정하게):
    · 직업 스킬 2~4번(Lv8·18·30)과 버프·지속 피해  (r4 는 1번 스킬만 → 깊은 층에서 플레이어를 과소평가)
    · 회피(장비 evasion + 새 DEX 회피) — 보스 패턴은 회피 불가라 80%만 친다
    · 2층 이후 보스: 일반형 보스 컨트롤러 (bosses.yml HP·피해·방어 + 경고 패턴·광역·연사·큰 한 방·소환)
    · 3인 파티 (방 몹을 나눠 맡고, 보스는 HP 를 나눠 친다 — 보스 기본 공격은 탱커가 받음)
  NEW 만:
    · 무기 = 새 한 방 피해 + 무기마다 간격 (ce_core), 게이지 없음 → 숙련 아닌 사람의 '이른 클릭 손실'이 사라짐 (GAUGE_EFF)
    · 공격력 = 한 방 × (1 + k·STR 또는 k·INT), 직업 스킬 = 스킬 위력 × 직업 배율 × (1 + k·스탯)
    · DEX: 치명·공속(활은 당김)·회피, 사냥꾼 매의 눈 +30%, 그림자 급소 찌르기 치명 피해 +30%·공속 +10%
    · 분배 = '알맞은 분배' (무기 요구치 채움 · VIT 는 0.3.4 와 같은 개수 · 나머지 피해 스탯, 사제는 WIS 요구치만)

  python3 ce_sim.py smoke
"""
import copy
import math
import os
import random
import sys

import ce_core as C
import ce_model as M

os.environ.setdefault("LAB_REPO", C.REPO)
C.USE_GEAR_REQUIRES = False   # 난이도 비교는 0.3.4 요구 능력치 (+ 새 DEX 나누기 규칙)
import ce_simbase as S  # noqa: E402

DT = S.DT
# 게이지가 있을 때 '꽉 차기 전에 누른' 손실 (r4 uptime 안에 들어 있던 몫). 새 모델은 이른 클릭을 한 번 기억했다가
# 간격이 끝나는 순간 넣으므로 이 손실이 없다 → NEW 의 기본 공격 기회 = uptime ÷ GAUGE_EFF (활은 당기기라 그대로).
GAUGE_EFF = {"novice": 0.85, "average": 0.92, "skilled": 1.00}

P_FINAL = dict(C.P_DEFAULT)
P_FINAL.update(k_phys=0.01, k_mag=0.01, dex_crit=0.0025, dex_speed=0.005, dex_evasion=0.001, cap_speed=0.60,
               keen_eye=1.30, shadow_crit_dmg=0.40, shadow_speed=0.0, priest_magic=0.10, sp_speed=0.5)
REQ_SPLIT_FINAL = {"DEX": ("STR", 0.4)}


def current_diffs():
    d = {k: dict(v) for k, v in S.CONFIG["difficulties"].items()}
    for v in d.values():
        v.pop("name", None)
    return d


def scenario(model="old", P=None, **kw):
    s = S.proposal()
    s.update(name=model, ramp={}, mech_ramp=False, starter_potions=10, mana_potions=5, first_clear_xp=0.4,
             diffs=current_diffs(), mech=dict(S.MECH))
    s["model"] = model
    s["P"] = P or P_FINAL
    s["req_split"] = REQ_SPLIT_FINAL if model == "new" else {}
    s["party_hp_per_member"] = S.CONFIG["party"]["hp_per_member"]
    s["party_dmg_per_member"] = S.CONFIG["party"]["dmg_per_member"]
    s["mob_hp_mult"] = {}       # 층 → 몹·보스 HP 배율 (재조정 후보)
    s["mob_dmg_mult_all"] = {}  # 층 → 몹·보스 피해 배율
    s["extra_skills"] = True
    s.update(kw)
    return s


# ───────────────────────────── 플레이어 ─────────────────────────────

class PlayerX(S.Player):
    def __init__(self, cls_id, level, scn, extra_gear=None):
        self.scn = scn
        self.item_ids = [g for g in (extra_gear or []) if S.ITEMS[g]["type"] != "weapon"]
        super().__init__(cls_id, level, scn, extra_gear)

    def _alloc(self, model):
        tgt = (self.scn.get("P") or {}).get("target", {}).get(self.cls_id) if model == "new" else None
        a, _ = M.plan_v2(self.cls_id, self.level, [self.weapon_id] + self.item_ids, model, self.scn.get("P"), target=tgt)
        return a

    def recompute(self):
        scn = self.scn
        if scn.get("model") != "new":
            if hasattr(self, "item_ids") and hasattr(self, "weapon_type"):
                self.points = self._alloc("old")
            super().recompute()
            bonus = {}
            for g in self.gear:
                for k, v in g.items():
                    bonus[k] = bonus.get(k, 0) + v
            self.evasion = min(0.40, bonus.get("evasion", 0))
            self.skill_ap = self.ap
            self.bow_full = (1.25 * 1.15) if self.cls_id == "hunter" else 1.25
            self.bow_partial = 0.75
            self.lifesteal = min(0.25, bonus.get("lifesteal", 0))
            return
        P = scn["P"]
        C.REQ_SPLIT = scn.get("req_split", {})
        wid = self.weapon_id
        ph = C.new_per_hit(wid, P)
        gear = [dict(g) for g in self.gear]
        gear[0]["damage"] = C.mid(ph)
        bonus = {}
        for g in gear:
            for k, v in g.items():
                bonus[k] = bonus.get(k, 0) + v
        c = self.c
        alloc = self._alloc("new")
        s = {st: max(0, c["base_stats"].get(st, 0) + alloc.get(st, 0) + round(bonus.get(st, 0))) for st in M.STATS}
        self.s = s
        self.points = alloc
        kind = M.weapon_kind(wid)
        kp = {"physical": P["k_phys"] * s["STR"], "magic": P["k_mag"] * s["INT"]}
        weapon = bonus.get("damage", 0) or 3.0
        self.ap = weapon * (1 + kp[kind])
        style = C.style_of(C.weapon_shape(wid))
        iv = C.interval_of(wid)
        sp = C.skill_power(weapon, iv, style, M.CASTER_SP_MULT if style == "caster" else 1.0)
        sc = P.get("skill_scale", {}).get(self.cls_id, M.SKILL_SCALE[self.cls_id])
        self.skill_ap = sp * sc * (1 + kp[M.CLASS_SKILL_KIND[self.cls_id]])
        self._sp_base = self.skill_ap
        self.style, self.interval = style, iv
        lv = self.level
        self.max_hp = c["base_hp"] + c["per_level"]["hp"] * (lv - 1) + s["VIT"] * 8 + bonus.get("hp", 0)
        self.max_mp = c["base_mp"] + c["per_level"]["mp"] * (lv - 1) + s["INT"] * 3 + s["WIS"] * 2 + bonus.get("mp", 0)
        self.defense = s["VIT"] * 0.5 + bonus.get("defense", 0)
        self.crit = min(0.75, 0.05 + s["DEX"] * P["dex_crit"] + s["LUK"] * P["luk_crit"] + bonus.get("crit_chance", 0))
        self.crit_dmg = 1.5 + bonus.get("crit_damage", 0)
        spd = s["DEX"] * P["dex_speed"] + bonus.get("attack_speed", 0)
        if self.cls_id == "shadow":
            self.crit_dmg += P.get("shadow_crit_dmg", 0)
            spd += P.get("shadow_speed", 0)
        self.atk_speed = max(-0.5, min(P["cap_speed"], spd))
        self.skill_ap = self._sp_base * (1 + P.get("sp_speed", 0.0) * max(0.0, self.atk_speed))
        self.evasion = min(0.40, s["DEX"] * P["dex_evasion"] + bonus.get("evasion", 0))
        self.mana_regen = c["mana_regen"] + s["WIS"] * 0.05 + bonus.get("mana_regen", 0)
        self.heal_power = s["WIS"] * 1.5 + bonus.get("heal_power", 0)
        self.hp_regen = bonus.get("hp_regen", 0)
        self.dr = 0.10 if self.cls_id == "guardian" else 0.0
        self.block = bonus.get("block_chance", 0)
        self.lifesteal = min(0.25, bonus.get("lifesteal", 0))
        self.bow_full = P["keen_eye"] if self.cls_id == "hunter" else 1.0
        self.magic_bonus = P.get("priest_magic", 0.0) if self.cls_id == "priest" else 0.0
        self.bow_partial = 0.6
        self.hp = min(getattr(self, "hp", 0) or 0, self.max_hp)

    def level_up(self, n=1):
        for _ in range(n):
            self.level += 1
        self.recompute()
        self.hp = self.max_hp

    def basic_period(self):
        if self.scn.get("model") != "new":
            return super().basic_period()
        spd = 1 + self.atk_speed
        if self.style == "ranged":
            return max(C.MIN_INTERVAL, (self.interval - C.BOW_NOCK) / spd + C.BOW_NOCK)
        return max(C.MIN_INTERVAL, self.interval / spd)


S.Player = PlayerX


# ───────────────────────────── 전투 ─────────────────────────────

def _extra_skills(cls_id, level):
    return [s for s in S.CLASSES[cls_id]["skills"][1:] if s["unlock_level"] <= level]


class FightX(S.Fight):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.ally_regen = 0.0       # 파티 사제가 살아 있으면 다른 파티원이 받는 초당 회복 (RunX 가 채움)
        self.xready = {}
        self.gcd = 0.0
        self.frenzy_until = 0.0
        self.dr_until = []          # (until, dr)
        self.shield = 0.0
        self.vuln_all_until = 0.0
        self.marked = {}            # mob → until
        self.veil_until = 0.0
        self.stealth_hit = False
        self.ward_until = 0.0
        self.venom_until = 0.0
        self.venom_stacks = {}      # mob → stacks
        self.burn_zone = None       # (until, dps)
        self.storm = None           # (until, next_tick, mult)

    # 받는 피해: 회피 · 보호막 · 추가 피해 감소
    def hurt(self, raw, true=False, frontal=True):
        pl = self.pl
        if raw <= 0 or self.dead:
            return
        if not true:
            ev = pl.evasion + (0.5 if self.t < self.veil_until else 0.0)
            if ev > 0 and random.random() < min(0.9, ev) * 0.8:
                return
            extra = sum(d for u, d in self.dr_until if self.t < u)
            if extra > 0:
                raw *= 1 - min(0.8, extra)
            if self.shield > 0:
                a = min(self.shield, raw * 100.0 / (100.0 + pl.defense))
                self.shield -= a
                raw -= a * (100.0 + pl.defense) / 100.0
                if raw <= 0:
                    return
        super().hurt(raw, true, frontal)

    def hit_mob(self, m, mult, skill=False, guaranteed_crit=False, crit_bonus=0.0):
        pl = self.pl
        dmg = (pl.skill_ap if skill else pl.ap) * mult
        if self.t < self.weaken_until:
            dmg *= 0.8
        if pl.cls_id == "berserker":
            f = pl.hp / pl.max_hp
            if f < 0.5:
                dmg *= 1 + 0.25 * (0.5 - f) / 0.5
        if self.t < self.frenzy_until:
            dmg *= 1.2
        if self.t < self.ward_until:
            dmg *= 1.10
        if not skill and self.stealth_hit:
            dmg *= 1.5
            self.stealth_hit = False
        if skill:
            dmg *= pl.skill_mult
        if guaranteed_crit or random.random() < pl.crit + crit_bonus:
            dmg *= pl.crit_dmg
        dmg *= 100.0 / (100.0 + m.defense)
        if self.t < m.shield_until:
            dmg *= 1 - m.shield_red
        if m.boss and self.boss_ctl and self.t < self.boss_ctl.vuln_until:
            dmg *= 1.5
        if self.t < self.marked.get(id(m), 0):
            dmg *= 1.20
        if getattr(pl, "magic_bonus", 0) and (skill or pl.weapon_type in ("staff", "scepter")):
            dmg *= 1 + pl.magic_bonus
        if self.t < self.vuln_all_until:
            dmg *= 1.15
        m.hp -= dmg
        self.dealt += dmg
        if pl.lifesteal > 0:
            self.heal(dmg * pl.lifesteal)
        if pl.cls_id == "shadow" and self.t < self.venom_until and not skill:
            self.venom_stacks[id(m)] = min(5, self.venom_stacks.get(id(m), 0) + 1)
        if m.hp <= 0:
            self.on_death(m)

    def _aoe(self, tgt, mult, frac, kind="skill"):
        self.hit_mob(tgt, mult, skill=True)
        for m in self.others(tgt):
            if random.random() < frac:
                self.hit_mob(m, mult, skill=True)

    def extra_skill(self):
        """직업 스킬 2~4번 (재사용·마나·전역 0.5초)."""
        pl, t = self.pl, self.t
        if not self.scn.get("extra_skills") or t < self.gcd:
            return False
        tgt = self.pick_target()
        if tgt is None:
            return False
        for sk in _extra_skills(pl.cls_id, pl.level):
            sid, p = sk["id"], sk.get("params", {})
            if t < self.xready.get(sid, 0) or pl.mp < sk["mana"]:
                continue
            boss_fight = any(m.boss for m in self.mobs)
            alive = len([m for m in self.mobs if m.hp > 0])
            used = True
            if sid == "taunting_roar":
                if pl.hp > pl.max_hp * 0.8 and alive < 2:
                    continue
                self.dr_until.append((t + p["dr_duration"], p["damage_reduction"]))
            elif sid == "guardian_oath":
                self.shield = max(self.shield, pl.max_hp * p["self_shield"])
            elif sid == "bulwark_citadel":
                self.dr_until.append((t + p["duration"], p["damage_reduction"]))
            elif sid == "ground_cleaver":
                self._aoe(tgt, p["damage"], 0.4)
                for m in self.mobs:
                    if not m.boss and m.hp > 0 and random.random() < 0.4:
                        m.stun = max(m.stun, t + 1.0)
            elif sid == "blood_frenzy":
                pl.hp -= pl.hp * p["hp_cost"]
                self.frenzy_until = t + p["duration"]
            elif sid == "ruinous_leap":
                self._aoe(tgt, p["damage"], 0.7)
                self.vuln_all_until = t + p["vuln_duration"]
            elif sid == "hunters_mark":
                self.marked[id(tgt)] = t + p["duration"]
            elif sid == "evasive_trap":
                if random.random() < 0.5:
                    self.hit_mob(tgt, p["trap_damage"], skill=True)
                    if not tgt.boss:
                        tgt.stun = max(tgt.stun, t + p["trap_root"])
            elif sid == "arrow_storm":
                self.storm = (t + p["duration"], t + p["tick"], p["damage"])
            elif sid == "frost_nova":
                self._aoe(tgt, p["damage"], 0.6)
                for m in self.mobs:
                    if not m.boss and m.hp > 0:
                        m.stun = max(m.stun, t + p["root"] * 0.6)
            elif sid == "phase_blink":
                self._aoe(tgt, p["echo_damage"] * 0.6, 0.4)
            elif sid == "meteor_fall":
                self._aoe(tgt, p["damage"], 0.75)
                self.burn_zone = (t + p["burn_duration"], p["burn_dps"])
            elif sid == "purifying_wave":
                self._aoe(tgt, p["damage"], 0.8)
                self.heal(pl.max_hp * p["heal"])
            elif sid == "sacred_ward":
                self.shield = max(self.shield, pl.max_hp * p["shield"])
                self.ward_until = t + p["duration"]
            elif sid == "resurrection_hymn":
                if pl.hp > pl.max_hp * 0.4:
                    continue
                self.heal(pl.max_hp * p["heal"])
            elif sid == "smoke_veil":
                if alive == 0:
                    continue
                self.veil_until = t + p["duration"]
                self.stealth_hit = True
            elif sid == "venom_blades":
                self.venom_until = t + p["duration"]
            elif sid == "shadow_execution":
                targets = [m for m in self.mobs if m.hp > 0][: p["max_targets"]]
                if len(targets) == 1:
                    targets = targets * p["boss_hits"]
                for m in targets:
                    if m.hp <= 0:
                        continue
                    mult = p["damage"] * (1 + p["execute_bonus"] if m.hp < m.max_hp * p["execute_threshold"] else 1)
                    self.hit_mob(m, mult, skill=True)
            else:
                used = False
            if used:
                pl.mp -= sk["mana"]
                self.xready[sid] = t + sk["cooldown"] * 0.9
                self.gcd = t + 0.5
                return True
        return False

    def tick_effects(self):
        pl, t = self.pl, self.t
        # 독날 중첩 지속 피해 (중첩당 초당 스킬 기준 × 0.10)
        if self.venom_stacks:
            for m in list(self.mobs):
                st = self.venom_stacks.get(id(m), 0)
                if st and m.hp > 0 and t < self.venom_until + 6:
                    d = pl.skill_ap * 0.10 * st * DT
                    m.hp -= d
                    self.dealt += d
                    if m.hp <= 0:
                        self.on_death(m)
        if self.burn_zone and t < self.burn_zone[0]:
            for m in list(self.mobs):
                if m.hp > 0 and (m.boss or random.random() < 0.7):
                    d = pl.skill_ap * self.burn_zone[1] * DT
                    m.hp -= d
                    self.dealt += d
                    if m.hp <= 0:
                        self.on_death(m)
        if self.storm and t < self.storm[0] and t >= self.storm[1]:
            until, nt, mult = self.storm
            self.storm = (until, nt + 0.5, mult)
            tgt = self.pick_target()
            if tgt is not None:
                self._aoe(tgt, mult * 0.7, 0.6)

    def player_act(self):
        pl, prof, t = self.pl, self.prof, self.t
        if self.ally_regen > 0:
            self.heal(self.ally_regen * DT)
        self.tick_effects()
        if self.dead:
            return
        if self.extra_skill():
            return
        new = self.scn.get("model") == "new"
        if not new and not hasattr(pl, "bow_full"):
            return super().player_act()
        # 아래는 S.Fight.player_act 와 같고 활 배율·게이지·광전사 공속 버프만 다르다
        pl.mp = min(pl.max_mp, pl.mp + pl.mana_regen * DT)
        self.heal((0.25 + pl.hp_regen) * DT)
        for i in range(len(self.dots) - 1, -1, -1):
            dps, until = self.dots[i]
            if t >= until:
                self.dots.pop(i)
            else:
                self.hurt(dps * DT, true=True)
        if self.potions > 0 and t >= self.pot_ready and pl.hp < pl.max_hp * prof["potion_thr"]:
            self.potions -= 1
            self.potions_used += 1
            self.heal(pl.max_hp * (self.heal_frac or self.scn["minor_heal"]))
            self.pot_ready = t + 12
        sk0 = pl.c["skills"][0]
        if self.mana_potions > 0 and t >= self.mpot_ready and pl.mp < sk0["mana"] and self.mobs:
            self.mana_potions -= 1
            pl.mp = min(pl.max_mp, pl.mp + pl.max_mp * (self.heal_frac or 0.25))
            self.mpot_ready = t + 12
        tgt = self.pick_target()
        if tgt is None:
            return
        cid = pl.cls_id
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
                        self.mob_dots.append((m, pl.skill_ap * p["bleed_ratio"], t + p["bleed_duration"]))
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
        if t >= self.next_hit:
            period = pl.basic_period()
            if t < self.frenzy_until:
                period /= 1.3
            self.next_hit = t + period
            up = prof["uptime"]
            bow = pl.weapon_type == "bow"
            if new and not bow:
                up = min(0.95, up / GAUGE_EFF[self.prof_id])
            if S.STYLE[pl.cls_id] == "kite" and not bow:
                up *= 0.45
            if random.random() < up:
                if bow:
                    full = random.random() < prof["full_draw"]
                    mult = pl.bow_full if full else pl.bow_partial
                    far = 0.08 if random.random() < 0.3 else 0.0
                    self.hit_mob(tgt, mult, crit_bonus=far)
                    if full:
                        pl.mp = min(pl.max_mp, pl.mp + 3)
                else:
                    cb = 0.20 if (pl.cls_id == "shadow" and random.random() < prof["back_rate"]) else 0.0
                    self.hit_mob(tgt, 1.0, crit_bonus=cb)
                    if pl.cls_id == "berserker":
                        pl.mp = min(pl.max_mp, pl.mp + 3)


S.Fight = FightX


# ───────────────────────────── 2층 이후 일반형 보스 ─────────────────────────────

class GenericBossCtl:
    """bosses.yml 의 HP·피해·방어 + 흔한 패턴 묶음. 1층 그로브(GroveCtl)와 같은 틀(최소 간격 1.2초, 페이즈, 기본 공격 2초)."""
    PATS = {
        # 이름: (쿨, 경고, 피해 배율, 페이즈부터)
        "strike": (8.0, 1.0, 1.5, 1),
        "area": (11.0, 1.2, 1.2, 1),
        "barrage": (14.0, 0.8, 0.6, 1),
        "summon": (35.0, 0.0, 0.0, 1),
        "big": (24.0, 1.6, 2.5, 2),
    }

    def __init__(self, fight, diff, scn, floor, dmg_share=1.0):
        self.fight = fight
        self.diff = diff
        self.cd_mult = diff["cd_mult"]
        self.extra = diff["extra"]
        self.floor = floor
        self.mob = None
        self.ready = {k: 2.0 + v[0] * self.cd_mult * 0.5 for k, v in self.PATS.items()}
        self.busy = 0.0
        self.next_allowed = 0.0
        self.next_attack = 1.0
        self.stun_until = 0.0
        self.vuln_until = 0.0
        self.dmg_share = dmg_share
        self.stats = dict(patterns=0, basic_hits=0)

    def tick(self, f):
        m = self.mob
        t = f.t
        if m.hp <= 0:
            return
        frac = m.hp / m.max_hp
        ph = 1 if frac > 0.6 else (2 if frac > 0.25 else 3)
        dmg = m.dmg * (1.15 if ph >= 3 else 1.0)
        cdm = self.cd_mult * (0.9 if ph >= 3 else 1.0)
        prof = f.prof
        kite = S.STYLE[f.pl.cls_id] == "kite"
        if t >= self.busy and t >= self.next_allowed:
            cands = [k for k, v in self.PATS.items() if t >= self.ready[k] and ph >= v[3]]
            if cands:
                k = random.choice(cands)
                cd, w0, mult, _ = self.PATS[k]
                self.ready[k] = t + cd * cdm
                w = f.windup(w0) if w0 > 0 else 0
                busy = w + 0.5
                self.stats["patterns"] += 1
                if k == "summon":
                    # 소환체 = 그 층 몹 HP 40% (보스 소환체는 rank add). 파티는 HP 를 나눠 맡은 사본마다 1마리
                    alive = sum(1 for x in f.mobs if x.is_add and x.hp > 0)
                    cnt = 1 + (self.extra if f.n == 1 else 0)
                    for _ in range(max(0, min(cnt, 3 - alive))):
                        mid = random.choice(S.FLOORS[self.floor]["mobs"])
                        a = S.Mob(mid, f.ctx_hp * 0.4, f.ctx_dmg, f.scn, self.floor, t, is_add=True)
                        f.mobs.append(a)
                    busy = 1.2
                elif k == "barrage":
                    shots = 3 + self.extra
                    for i in range(shots):
                        if random.random() >= S.dodge_p(w + 0.3, prof) * (1.1 if kite else 1.0):
                            f.pending.append((t + w + 0.2 * i, lambda d=dmg * mult * self.dmg_share: f.hurt(d)))
                else:
                    n_hits = 1 + (self.extra if k == "area" else 0)
                    pd = S.dodge_p(w, prof) ** (1 + 0.25 * (n_hits - 1))
                    if k == "strike" and kite:
                        pd = max(pd, 0.6)
                    if random.random() >= pd:
                        f.pending.append((t + w, lambda d=dmg * mult * self.dmg_share: f.hurt(d)))
                self.busy = t + busy
                self.next_allowed = t + max(busy, 1.2)
                return
        if t >= self.busy and t >= self.next_attack:
            self.next_attack = t + f.scn["boss_attack_interval"]
            e = prof["boss_e_kite"] if kite else prof["boss_e_melee"]
            if self.dmg_share < 1.0:       # 파티: 기본 공격은 탱커가 받는다
                e *= 0.25
            if random.random() < e:
                self.stats["basic_hits"] += 1
                f.pending.append((t + 0.15, lambda d=dmg: f.hurt(d)))


# ───────────────────────────── 층 진행 ─────────────────────────────

def entry_level(floor):
    return 1 if floor == 1 else S.FLOORS[floor]["level_range"][0]


def gear_list(cls, floor):
    if floor == 1:
        return None
    L = entry_level(floor)
    w, items = M.gear_for(cls, L)
    return [w] + items


class RunX(S.Run):
    def __init__(self, cls_id, level, prof_id, diff_id, scn, floor=1, potions=None, extra_gear=None, n=1):
        super().__init__(cls_id, level, prof_id, diff_id, scn, floor, potions, extra_gear, n)
        self.prof_id = prof_id
        hpm = 1 + scn["party_hp_per_member"] * (n - 1)
        dmm = 1 + scn["party_dmg_per_member"] * (n - 1)
        if n == 1:
            hpm *= scn["solo_hp"]
            dmm *= scn["solo_damage"]
        self.ctx_hp = self.diff["hp"] * hpm * scn["mob_hp_mult"].get(floor, scn["mob_hp_mult"].get("all", 1.0))
        self.ctx_dmg = self.diff["damage"] * dmm * scn["mob_dmg_mult_all"].get(floor, scn["mob_dmg_mult_all"].get("all", 1.0))
        self.times = dict(combat=[], elite=[], boss=None)

    def fight(self, mobs, boss=False, boss_hp_share=1.0, boss_dmg_share=1.0):
        f = S.Fight(self.pl, mobs, self.prof, self.diff, self.scn, self.floor, self.ctx_hp, self.ctx_dmg, self.potions,
                    on_kill=self.kill_reward, n=self.n, mana_potions=self.mana_potions,
                    heal_frac=S.heal_frac(self.pl.level, self.scn))
        f.prof_id = self.prof_id
        f.ally_regen = getattr(self, "ally_regen", 0.0)
        ctl = None
        if boss:
            if self.floor == 1:
                ctl = S.GroveCtl(f, self.diff, self.scn, self.n)
                d = S.BOSSES["floor01_moss_warden"]
            else:
                ctl = GenericBossCtl(f, self.diff, self.scn, self.floor, boss_dmg_share)
                d = next(v for v in S.BOSSES.values() if v.get("floor") == self.floor)
            bm = S.Mob("moss_crawler", 1, 1, self.scn, 1, 0)
            bm.id, bm.boss = "boss", True
            bm.hp = bm.max_hp = d["hp"] * self.ctx_hp * boss_hp_share
            bm.dmg, bm.defense, bm.xp, bm.skills = d["damage"] * self.ctx_dmg, d["defense"], d["xp"], []
            ctl.mob = bm
            f.mobs.insert(0, bm)
        hp0 = self.pl.hp
        ok = f.run(max_t=1200, boss_ctl=ctl)
        self.time += f.t
        self.potions = f.potions
        self.mana_potions = f.mana_potions
        rec = dict(ok=ok, t=round(f.t, 1), taken=round(f.taken), taken_pct=round(f.taken / self.pl.max_hp, 3),
                   hp_before=round(hp0), hp_after=round(max(0, self.pl.hp)), pots=f.potions_used, lv=self.pl.level,
                   mobs=len(mobs), dealt=f.dealt)
        return ok, rec

    def order(self):
        rc = S.FLOORS[self.floor]["rooms"]
        order = ["C"] * rc.get("combat", 6)
        order.insert(2, "T")
        order.insert(4, "G")
        order.insert(len(order) // 2 + 1, "R")
        for _ in range(rc.get("elite", 1)):
            order.insert(len(order) - 1, "E")
        order.append("B")
        return order

    def run_floor(self):
        for i, kind in enumerate(self.order()):
            if i > 0:
                self.walk(30)
                if i % 3 == 2 and not self.traps():
                    return dict(cleared=False, died_at="함정", level=self.pl.level)
            if kind in ("C", "E"):
                mobs = S.make_room_mobs(self.floor, self.scn, self.ctx_hp, self.ctx_dmg,
                                        "combat" if kind == "C" else "elite", self.n)
                ok, rec = self.fight(mobs)
                (self.times["combat"] if kind == "C" else self.times["elite"]).append(rec["t"])
                if not ok:
                    return dict(cleared=False, died_at="전투방" if kind == "C" else "정예방", level=self.pl.level)
                if kind == "E":
                    self.potions += S.potion_expect(0.25, self.diff["drop"])
                self.pl.hp = min(self.pl.max_hp, self.pl.hp + self.pl.max_hp * self.scn["room_clear_heal"])
            elif kind == "T":
                for _ in range(S.DUNGEON["treasure"]["chests"]):
                    if random.random() < S.DUNGEON["treasure"]["mimic_chance"]:
                        ok, rec = self.fight(S.make_room_mobs(self.floor, self.scn, self.ctx_hp, self.ctx_dmg, "mimic"))
                        if not ok:
                            return dict(cleared=False, died_at="미믹", level=self.pl.level)
                    for _ in range(2):
                        self.potions += S.potion_expect(0.45, self.diff["drop"])
                for _ in range(2):      # 미로 상자 2~3개 (r4 와 같게)
                    self.potions += S.potion_expect(0.5, self.diff["drop"])
            elif kind == "G":
                self.gain_xp(S.avg_mob_xp(self.floor) * 10)
                for _ in range(2):
                    self.potions += S.potion_expect(0.35, self.diff["drop"])
            elif kind == "R":
                pl = self.pl
                pl.hp = min(pl.max_hp, pl.hp + pl.max_hp * self.scn["rest_heal"])
                pl.mp = min(pl.max_mp, pl.mp + pl.max_mp * self.scn["rest_heal"])
            elif kind == "B":
                ok, rec = self.fight([], boss=True)
                self.times["boss"] = rec["t"]
                if not ok:
                    return dict(cleared=False, died_at="보스", level=self.pl.level, boss_t=rec["t"])
        return dict(cleared=True, died_at=None, level=self.pl.level)


def solo_floor(scn, cls, prof, diff, floor, runs, seed=0):
    random.seed(seed)
    cleared, died = 0, {}
    room_t, elite_t, boss_t = [], [], []
    for _ in range(runs):
        pots = None if floor == 1 else 10
        r = RunX(cls, entry_level(floor), prof, diff, scn, floor, potions=pots, extra_gear=gear_list(cls, floor))
        out = r.run_floor()
        if out["cleared"]:
            cleared += 1
            if r.times["boss"] is not None:
                boss_t.append(r.times["boss"])
        else:
            died[out["died_at"]] = died.get(out["died_at"], 0) + 1
        room_t += r.times["combat"]
        elite_t += r.times["elite"]
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    return dict(clear=round(cleared / runs, 3), room_t=avg(room_t), elite_t=avg(elite_t), boss_t=avg(boss_t),
                deaths=sorted(((k, round(v / runs, 3)) for k, v in died.items()), key=lambda x: -x[1])[:3])


PARTIES = {"A": ["guardian", "hunter", "priest"], "B": ["berserker", "arcanist", "shadow"]}


def party_floor(scn, comp, prof, diff, floor, runs, seed=0):
    """3인 — 방 몹을 산 파티원에게 나눠 각자 싸움(정예는 탱커가 맡고 HP 를 나눔), 보스는 HP 를 나눠 각자 침
    (보스 기본 공격은 맨 앞 파티원(탱커)이 받는다). 한 명이라도 보스까지 살아서 잡으면 클리어."""
    random.seed(seed)
    members = PARTIES[comp]
    n = len(members)
    cleared, all_alive, surv = 0, 0, 0.0
    room_t, boss_t = [], []
    for _ in range(runs):
        mem = [RunX(c, entry_level(floor), prof, diff, scn, floor, potions=10 if floor > 1 else None,
                    extra_gear=gear_list(c, floor), n=n) for c in members]
        alive = [True] * n
        order = mem[0].order()
        boss_ok = False
        pi = members.index("priest") if "priest" in members else -1
        dps_acc = [[0.0, 0.0] for _ in range(n)]
        for i, kind in enumerate(order):
            live = [k for k in range(n) if alive[k]]
            if not live:
                break
            # 사제가 살아 있으면 다른 파티원에게 치유의 빛 몫 (절반은 사제 자신·광역에 쓴다고 보고)
            for k in range(n):
                mem[k].ally_regen = 0.0
                if pi >= 0 and alive[pi] and k != pi:
                    pr = mem[pi].pl
                    mem[k].ally_regen = 0.5 * (0.18 * mem[k].pl.max_hp + pr.heal_power) / 2.7 / (n - 1)
            if i > 0:
                for k in live:
                    mem[k].walk(30)
                    if i % 3 == 2 and not mem[k].traps():
                        alive[k] = False
            live = [k for k in range(n) if alive[k]]
            if not live:
                break
            r0 = mem[live[0]]
            if kind in ("C", "E"):
                mobs = S.make_room_mobs(floor, scn, r0.ctx_hp, r0.ctx_dmg, "combat" if kind == "C" else "elite", n)
                share = {k: [] for k in live}
                if kind == "E":
                    lead = mobs[0]
                    lead.hp = lead.max_hp = max(1, round(lead.max_hp / len(live)))
                    share[live[0]].append(lead)
                    rest = mobs[1:]
                else:
                    random.shuffle(mobs)
                    rest = mobs
                for j, m in enumerate(rest):
                    share[live[j % len(live)]].append(m)
                ts = []
                for k in live:
                    if share[k]:
                        ok, rec = mem[k].fight(share[k])
                        ts.append(rec["t"])
                        dps_acc[k][0] += rec["dealt"]
                        dps_acc[k][1] += rec["t"]
                        if not ok:
                            alive[k] = False
                if kind == "C" and ts:
                    room_t.append(max(ts))
                for k in range(n):
                    if alive[k]:
                        p = mem[k].pl
                        p.hp = min(p.max_hp, p.hp + p.max_hp * scn["room_clear_heal"])
            elif kind == "R":
                for k in live:
                    p = mem[k].pl
                    p.hp = min(p.max_hp, p.hp + p.max_hp * scn["rest_heal"])
                    p.mp = min(p.max_mp, p.mp + p.max_mp * scn["rest_heal"])
            elif kind == "G":
                for k in live:
                    mem[k].gain_xp(S.avg_mob_xp(floor) * 10)
            elif kind == "B":
                # 보스 HP 를 방에서 잰 각자의 초당 피해 비율로 나눠 맡는다 → 사본마다 거의 같은 시간 = 파티 처치 시간
                dps = {k: (dps_acc[k][0] / dps_acc[k][1]) if dps_acc[k][1] > 0 else 1.0 for k in live}
                tot = sum(dps.values()) or 1.0
                ts, oks = [], []
                for idx, k in enumerate(live):
                    ok, rec = mem[k].fight([], boss=True, boss_hp_share=dps[k] / tot,
                                           boss_dmg_share=1.0 if idx == 0 else 0.6)
                    ts.append(rec["t"])
                    oks.append(ok)
                    if not ok:
                        alive[k] = False
                boss_ok = any(oks)
                if boss_ok:
                    okt = [t for t, o in zip(ts, oks) if o]
                    boss_t.append(len(okt) / sum(1.0 / max(1e-6, t) for t in okt))
        a = sum(alive)
        if boss_ok:
            cleared += 1
        if a == n and boss_ok:
            all_alive += 1
        surv += a / n
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    return dict(clear=round(cleared / runs, 3), all_alive=round(all_alive / runs, 3), surv=round(surv / runs, 3),
                room_t=avg(room_t), boss_t=avg(boss_t))


if __name__ == "__main__":
    if sys.argv[1:] == ["smoke"]:
        import time
        for model in ("old", "new"):
            scn = scenario(model)
            for fl in (1, 3, 5, 7, 10):
                t0 = time.time()
                r = solo_floor(scn, "berserker", "skilled", "normal", fl, 6, seed=1)
                print(model, fl, r, f"{time.time() - t0:.1f}s")
            t0 = time.time()
            print(model, "party", party_floor(scn, "A", "skilled", "normal", 5, 4, seed=2), f"{time.time() - t0:.1f}s")
