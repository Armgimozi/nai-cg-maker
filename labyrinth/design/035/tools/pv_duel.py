#!/usr/bin/env python3
"""
TASK P — 1:1 끝까지 (0.1초 단위 몬테카를로). 같은 레벨 두 빌드가 서로 보고 시작한다(기습 아님).

모델 (근사):
  · 기본 공격: 무기 간격(공속 반영)마다 한 번. 근접(시전 무기 휘두르기 포함)은 '닿는 비율' u 를 곱한다 —
    근접끼리 0.85 · 근접 → 사냥꾼(활) 0.55 · 상대가 기절·빙결·속박이면 1.0 · 내가 속박이면 ×0.4 · 둔화 s 면 ×(1 − 0.5 s)(활 상대).
    활은 0.85 (움직이는 사람 맞히기), 상대가 묶이면 1.0. 실명이면 ×0.6.
  · 스킬: 재사용·MP 가 되면 우선순위(위급 회복 → 방어 버프 → 공격 버프 → 제어 → 피해)로 0.25초에 하나. 맞을 확률 = 스킬마다.
  · 상태이상: pvp_spec 규칙 그대로 (PvP 배율 → 상한 → 같은 종류 줄어듦 → 기절 뒤 면역, 판금 4부위 −40%, WIS 감소).
  · 회복: 사제 치유·정화, 물약(HP 40% 아래, 12초, 5개), 흡혈(장비·피의 갈망·leech), 보호막(맹세·가호·은총 넘친 치유·무기 스킬).
  · 겉모습 4부위: 판금 = 제어 −40%·밀림 −60% · 가죽 = 구르기(8초마다 큰 스킬 하나 50% 확률로 피함) · 천 = 마나 보호막(피해 20% 를 MP 로).
  · 고유 효과: 1:1 에서 의미 있는 것만 (execute·berserk·first_strike·backstab·flurry·rend·leech·thorns·shield_bash·steadfast·
    momentum·counterstep·imbue·exploit·armor_break·hemorrhage·overcharge·sanctify·ward_aura·longshot). 처치·여러 명 효과는 0.
"""
import math
import random

import pv_core as V
import pv_sim as S

DT = 0.1
MAX_T = 90.0
U_MELEE = 0.85
U_MELEE_VS_RANGED = 0.55
U_RANGED = 0.85
POTION = {5: 0.25, 10: 0.25, 20: 0.40, 35: 0.60, 50: 0.60}
POTIONS = 5
CC_CAT = {"stun": "control", "frozen": "control", "root": "root", "silence": "silence", "blind": "blind",
          "slow": "slow", "cooldown_slow": "slow"}


class F:
    """싸우는 사람 하나."""

    def __init__(self, b, P, rng):
        self.b = b
        self.P = P
        self.rng = rng
        self.cls = b["cls"]
        self.L = b["L"]
        self.hp = b["max_hp"]
        self.mp = b["max_mp"]
        self.next_basic = rng.random() * b["period"]
        self.cd = {}
        self.buffs = []          # (key, value, until, src)
        self.shields = []        # [amount, until]
        self.st = {}             # id → until (stun, frozen, root, silence, blind)
        self.slow = (0.0, 0.0)
        self.debuff = {}         # mark/vulnerable/weaken → (value, until)
        self.dots = []           # [per_s, until, next_tick, kind, src]
        self.venom = [0, 0.0]
        self.drt = {}            # 분류 → (count, last)
        self.immune_until = 0.0
        self.potion_ready = 0.0
        self.potions = POTIONS
        self.iron_ready = 0.0
        self.tumble_ready = 0.0
        self.stealth = (0.0, 0.0)  # until, bonus
        self.lock_until = 0.0
        self.hits = 0
        self.mom = [0, 0.0]
        self.first_hit = True
        self.counter = 0.0
        self.overcharge = 0.0
        self.ab_stacks = [0, 0.0]
        self.ward_next = 4.0
        self.dealt = 0.0
        self.healed = 0.0
        self.cc_time = 0.0
        self.kit = [k for k in V.class_kit(self.cls) if k["unlock"] <= self.L]
        self.wsk = [s for s in b["w"]["skills"] if not (s["input"] == "LEFT" and s["cooldown"] <= 2.0)]
        self.swing = S._swing_extra(b)
        self.swing_ready = 0.0
        self.u = b["w"].get("unique") or {}
        self.cdmult = (1 - b["cdr"]) * b["cd_look"]

    # ── 상태 ──
    def buff(self, key, now):
        return sum(v for k, v, u, _s in self.buffs if k == key and u > now)

    def stunned(self, now):
        return self.st.get("stun", 0) > now or self.st.get("frozen", 0) > now

    def rooted(self, now):
        return self.st.get("root", 0) > now or self.stunned(now)

    def silenced(self, now):
        return self.st.get("silence", 0) > now or self.stunned(now)

    def pool(self):
        return self.b["max_hp"]

    def hp_frac(self):
        return self.hp / self.b["max_hp"]

    def atk_speed(self, now):
        a = self.b["atk_speed"] + self.buff("attack_speed", now)
        if self.u.get("id") == "momentum" and self.mom[1] > now:
            a += self.u.get("as", 0.03) * self.mom[0]
        return max(-0.5, min(0.6, a))

    def period(self, now):
        w = self.b["w"]
        spd = 1 + self.atk_speed(now)
        if w["style"] == "ranged":
            return max(0.25, (w["interval"] - 0.15) / spd) + 0.15
        return max(0.25, w["interval"] / spd)

    def dmg_buff(self, now, tgt):
        d = self.buff("damage", now)
        w = self.debuff.get("weaken")
        if w and w[1] > now:
            d -= w[0]
        if self.cls == "berserker":
            f = self.hp_frac()
            if f < 0.5:
                d += 0.25 * min(1.0, (0.5 - f) / 0.5)
        u = self.u
        pv = 0.5  # unique_spec PvP 규칙: 곱하기 보정 +피해 ×0.5 (그대로 둔다)
        if u.get("id") == "berserk":
            d += pv * u.get("pct", 0.025) * math.floor((1 - self.hp_frac()) * 10)
        if u.get("id") == "execute" and tgt.hp_frac() <= u.get("thr", 0.3):
            d += pv * u.get("pct", 0.25)
        if u.get("id") == "exploit" and tgt.has_debuff(now):
            d += pv * u.get("pct", 0.15)
        return d

    def has_debuff(self, now):
        return any(u > now for u in self.st.values()) or self.slow[1] > now or bool(
            [1 for v in self.debuff.values() if v[1] > now]) or bool([1 for x in self.dots if x[1] > now])

    def taken(self, now):
        t = 0.0
        for k in ("mark", "vulnerable"):
            v = self.debuff.get(k)
            if v and v[1] > now:
                t += v[0]
        return t

    def dr(self, now):
        d = self.b["dr"] + self.buff("damage_reduction", now)
        if self.u.get("id") == "steadfast" and self.hp_frac() >= self.u.get("thr", 0.7):
            d += self.u.get("dr", 0.08)
        return min(0.9, d)

    def evasion(self, now):
        return min(0.4, self.b["evasion"] + self.buff("evasion", now)) if self.buff("evasion", now) <= 0 else \
            min(0.75, self.b["evasion"] + self.buff("evasion", now))


def cc_duration(P, tgt, cid, base, now):
    """PvP 상태이상 시간: (정신 감소) → (판금 4부위) → PvP 배율 → 상한 → 같은 분류 줄어듦 → 기절 뒤 면역."""
    d = base
    if cid not in ("stun", "frozen"):
        d *= 1 - tgt.b["debuff_red"]
    if cid in ("stun", "root", "frozen") and tgt.b.get("full") == "heavy":
        d *= 1 - 0.40
    d *= P["cc_mult"].get(cid, 1.0)
    cap = P["cc_cap"].get(cid)
    if cap:
        d = min(d, cap)
    cat = CC_CAT.get(cid)
    if P.get("dr") and cat in P["dr"]["cats"]:
        cnt, last = tgt.drt.get(cat, (0, -99))
        if now - last > P["dr"]["window"]:
            cnt = 0
        steps = P["dr"]["steps"]
        f = steps[min(cnt, len(steps) - 1)]
        d *= f
        if f > 0:
            tgt.drt[cat] = (cnt + 1, now)
    if cat == "control" and tgt.immune_until > now:
        return 0.0
    return d if d >= 0.2 else 0.0


def apply_cc(P, src, tgt, cid, base, now, pot=1.0):
    if cid in ("launch", "knockback", "pull", "taunt"):
        if cid == "launch" and P.get("launch_lock", 0) > 0:
            tgt.lock_until = max(tgt.lock_until, now + P["launch_lock"] * (0.4 if tgt.b.get("full") == "heavy" else 1))
        return
    if cid == "mark":
        tgt.debuff["mark"] = (max(pot or 0.1, tgt.debuff.get("mark", (0, 0))[0]), now + base)
        return
    if cid in ("vulnerable", "weaken"):
        tgt.debuff[cid] = (pot or 0.1, now + base * (1 - tgt.b["debuff_red"]))
        return
    if cid == "frost":
        return  # 서리 중첩은 아래 frost() 에서
    d = cc_duration(P, tgt, cid, base, now)
    if d <= 0:
        return
    if cid == "slow":
        pot = min(pot or 0.35, P.get("slow_cap", 0.85))
        tgt.slow = (max(pot, tgt.slow[0] if tgt.slow[1] > now else 0), max(tgt.slow[1], now + d))
        return
    prev = tgt.st.get(cid, 0)
    tgt.st[cid] = max(prev, now + d)
    tgt.cc_time += max(0.0, tgt.st[cid] - max(prev, now))
    if cid in ("stun", "frozen", "root", "silence"):
        hard_until = max(tgt.st.get(x, 0) for x in ("stun", "frozen", "root", "silence"))
        if getattr(tgt, "chain_end", -1) < now:
            tgt.chain_start = now
        tgt.chain_end = hard_until
        tgt.max_chain = max(getattr(tgt, "max_chain", 0.0), hard_until - tgt.chain_start)
    if cid in ("stun", "frozen"):
        tgt.immune_until = max(tgt.immune_until, tgt.st[cid] + P.get("stun_immune", 0.0))


def frost(P, src, tgt, stacks, now, frozen_s=4.0):
    n, until = getattr(tgt, "frost", (0, 0))
    if until < now:
        n = 0
    n += stacks
    if n >= 5:
        tgt.frost = (0, 0)
        apply_cc(P, src, tgt, "frozen", frozen_s, now)
    else:
        tgt.frost = (n, now + 6)


def deal(P, a, t, raw, now, kind, skill=False, dot=False, can_crit=True, crit_bonus=0.0, cd_bonus=0.0, evadable=True,
         big=False, tag=None, lifesteal_extra=0.0, src_mult=1.0):
    """피해 한 건 (pvp_spec 파이프라인). 반환 = 실제 HP 피해."""
    if t.hp <= 0 or raw <= 0:
        return 0.0
    rng = a.rng
    m = raw * P["dmg"] * S.level_mult(max(a.L, t.L), P) * src_mult * (1 + a.dmg_buff(now, t)) * \
        P.get("class_mult", {}).get(a.cls, 1.0)
    if skill:
        m *= 1 + a.b["skill_dmg"]
    if a.stealth[0] > now and not dot:
        m *= 1 + a.stealth[1]
        a.stealth = (0.0, 0.0)
    if evadable and not dot:
        if big and t.b.get("full") == "light" and t.tumble_ready <= now and rng.random() < 0.5:
            t.tumble_ready = now + 8.0
            return 0.0
        if rng.random() < t.evasion(now):
            if t.u.get("id") == "counterstep":
                t.counter = now + 3.0
            return 0.0
    crit = False
    if can_crit and not dot:
        cc = a.b["crit"] + crit_bonus
        if a.u.get("id") == "hemorrhage" and any(x[3] == "bleed" and x[1] > now for x in t.dots):
            cc += a.u.get("cc", 0.1)
            cd_bonus += a.u.get("cd", 0.2) * 0.5
        if a.counter > now:
            cc = 1.0
            m *= 1 + 0.5 * a.u.get("pct", 0.3)
            a.counter = 0.0
        if rng.random() < min(1.0, cc):
            crit = True
            m *= 1 + (a.b["crit_dmg"] + cd_bonus - 1) * P["crit_scale"]
    if not dot:
        de = t.b["defense"] * P.get("def_weight", 1.0)
        if a.u.get("id") == "armor_break" and t.ab_stacks[1] > now:
            de *= 1 - a.u.get("pct", 0.04) * t.ab_stacks[0]
        m *= 100.0 / (100.0 + max(0.0, de))
    m *= 1 - t.dr(now)
    m *= 1 + t.taken(now)
    if not dot and t.b.get("shield") and t.b["block"] > 0 and rng.random() < t.b["block"] * 0.6:
        m *= 0.4
    m *= S.buffer_factor(t.b, P)
    m *= 1 - S.resilience(t.b, P)
    if P["max_hit"] < 1.0:
        m = min(m, t.pool() * P["max_hit"])
    # 보호막 → 마나 보호막 → HP
    left = m
    for sh in t.shields:
        if sh[1] > now and left > 0:
            x = min(sh[0], left)
            sh[0] -= x
            left -= x
    t.shields = [s for s in t.shields if s[0] > 0.01 and s[1] > now]
    if t.b.get("full") == "cloth" and left > 0 and t.mp > 0.2 * t.b["max_mp"]:
        ab = left * 0.20
        cost = ab / 2.0
        if t.mp - cost < 0.2 * t.b["max_mp"]:
            cost = max(0.0, t.mp - 0.2 * t.b["max_mp"])
            ab = cost * 2
        t.mp -= cost
        left -= ab
    left = max(0.0, left)
    # 수호기사 강철 의지 비상 (30% 아래, 60초에 한 번)
    t.hp -= left
    a.dealt += left
    if t.cls == "guardian" and t.hp > 0 and t.hp_frac() < 0.30 and t.iron_ready <= now:
        t.iron_ready = now + 60
        t.buffs.append(("damage_reduction", 0.20, now + 5, "iron"))
    # 흡혈 (장비·버프 + 무기 스킬·고유)
    ls = 0.0 if dot else min(0.25, a.b["lifesteal"] + a.buff("lifesteal", now)) + lifesteal_extra
    if ls > 0 and left > 0:
        heal(P, a, left * ls * P["lifesteal"], now, lifesteal=True)
    # 가시
    if t.u.get("id") == "thorns" and not dot and kind == "physical" and a.b["w"]["style"] != "ranged" and not skill:
        r = raw * P["dmg"] * t.u.get("pct", 0.3) * 0.5
        deal(P, t, a, r, now, "fixed", dot=True, can_crit=False, evadable=False, src_mult=1.0)
    return left


def heal(P, f, amount, now, lifesteal=False, flat=0.0):
    """amount = 최대 HP 비율로 정해진 회복(그대로), flat = 고정량 회복(치유력·흡혈·재생 — PvP 체력 비율로 줄임)."""
    if f.hp <= 0 or (amount <= 0 and flat <= 0):
        return
    bfac = S.buffer_factor(f.b, P) if P.get("flat_heal_scaled", True) else 1.0
    damp = dampening(P, now)
    if lifesteal:
        amount = amount * bfac * damp
    else:
        amount = (amount + flat * bfac) * P["heal"] * damp
    before = f.hp
    f.hp = min(f.b["max_hp"], f.hp + amount)
    over = amount - (f.hp - before)
    if f.cls == "priest" and over > 0 and not lifesteal:
        cap = f.b["max_hp"] * 0.10
        cur = sum(s[0] for s in f.shields if s[1] > now)
        if cur < cap:
            f.shields.append([min(cap - cur, over) * P["shield"], now + 5])
    f.healed += f.hp - before


def add_shield(P, f, amount, dur, now):
    f.shields.append([amount * P["shield"] * dampening(P, now), now + dur])


def dampening(P, now):
    """긴 싸움: PvP 전투가 start 초 넘게 이어지면 받는 회복·보호막이 초마다 per_s 씩 줄어든다 (최소 floor)."""
    d = P.get("dampening")
    if not d:
        return 1.0
    return max(d["floor"], 1.0 - d["per_s"] * max(0.0, now - d["start"]))


def basic(P, a, t, now):
    b = a.b
    w = b["w"]
    style = w["style"]
    if style == "ranged":
        u = U_RANGED
    else:
        u = U_MELEE_VS_RANGED if t.b["w"]["style"] == "ranged" else U_MELEE
        if a.rooted(now):
            u *= 0.4
        if t.b["w"]["style"] == "ranged" and a.slow[1] > now:
            u *= 1 - 0.5 * a.slow[0]
    if t.rooted(now):
        u = 1.0
    if a.st.get("blind", 0) > now:
        u *= 0.6
    if a.rng.random() > u:
        return
    ap = b["ap"]
    mult = 1.0
    if a.cls == "hunter" and style == "ranged":
        mult *= 1 + V.CLASS_VALUES["keen_eye_full_draw"]
        a.mp = min(b["max_mp"], a.mp + 3)
    crit_bonus = 0.0
    if a.cls == "hunter":
        crit_bonus += 0.08 * 0.5          # 12칸 밖 치명 +8% (절반쯤)
    if a.cls == "shadow" and a.rng.random() < 0.25:
        crit_bonus += 0.20                # 등 뒤 (1:1 에서는 4번에 1번쯤)
    uid = a.u.get("id")
    if uid == "backstab" and a.rng.random() < 0.25:
        mult *= 1 + 0.5 * a.u.get("pct", 0.25)
    if uid == "first_strike" and a.first_hit:
        mult *= 1 + 0.5 * a.u.get("pct", 0.8)
        crit_bonus += a.u.get("cc", 0.2)
    if uid == "longshot" and style == "ranged" and a.rng.random() < 0.5:
        mult *= 1 + 0.5 * a.u.get("pct", 0.2)
    a.first_hit = False
    dmg = deal(P, a, t, ap * mult, now, w["kind"], crit_bonus=crit_bonus)
    a.hits += 1
    if a.cls == "berserker":
        a.mp = min(b["max_mp"], a.mp + 3)
    if uid == "momentum":
        a.mom = [min(a.u.get("max_stacks", 5), a.mom[0] + 1 if a.mom[1] > now else 1), now + a.u.get("decay", 3)]
    if uid == "flurry" and a.hits % int(a.u.get("n", 4)) == 0:
        deal(P, a, t, ap * a.u.get("pct", 0.7) * 0.5, now, w["kind"], evadable=False)
    if uid == "shield_bash" and a.hits % int(a.u.get("n", 5)) == 0:
        deal(P, a, t, ap * a.u.get("pct", 0.4), now, "physical", evadable=False)
        apply_cc(P, a, t, "stun", a.u.get("stun", 0.8), now)
    if uid == "leech" and dmg > 0:
        heal(P, a, dmg * a.u.get("pct", 0.06) * P["lifesteal"], now, lifesteal=True)
    if uid == "rend" and dmg > 0 and a.rng.random() < b["crit"]:
        add_dot(P, a, t, b["sp"] * b["power"]["physical"] * a.u.get("pct", 0.06) * 0.5, a.u.get("duration", 4), "bleed", now)
    if uid == "imbue" and a.rng.random() < a.u.get("chance", 0.25) * min(1.5, b["w"]["interval"] / 0.67):
        el = a.u.get("element", "burn")
        if el == "frost":
            frost(P, a, t, 1, now, frozen_s=1.0)
        else:
            add_dot(P, a, t, b["sp"] * b["power"]["magic" if el == "burn" else "physical"] * a.u.get("pct", 0.1) * 0.5,
                    a.u.get("duration", 3), el, now)
    if uid == "armor_break":
        t.ab_stacks = [min(3, t.ab_stacks[0] + 1 if t.ab_stacks[1] > now else 1), now + a.u.get("duration", 5)]
    if uid == "overcharge" and a.overcharge > now:
        a.overcharge = 0.0
        deal(P, a, t, b["sp"] * b["power"]["magic"] * a.u.get("pct", 1.2) * 0.5, now, "magic", evadable=False)
    if uid == "sanctify":
        heal(P, a, 0.0, now, flat=(ap * a.u.get("pct", 0.12) + b["heal_power"] * 0.3) * 0.5)
    if a.swing and a.swing_ready <= now:
        a.swing_ready = now + a.swing["cooldown"]
        deal(P, a, t, b["sp"] * b["power"][w["kind"]] * a.swing["damage"] * P["wskill"], now, w["kind"], skill=True)
    # 독날 (그림자)
    if a.buff("venom", now) > 0 and dmg > 0:
        a.venom_hit(t, now)


def add_dot(P, a, t, per_s, dur, kind, now):
    if per_s <= 0:
        return
    if kind != "burn":
        dur *= 1 - t.b["debuff_red"]
    t.dots.append([per_s, now + dur, now + 1.0, kind, a])


def _venom_hit(self, t, now):
    vb = next(k for k in self.kit if k["id"] == "venom_blades")["venom"]
    n, until = t.venom
    if until < now:
        n = 0
    n = min(vb["max"], n + 1)
    t.venom = [n, now + vb["dur"]]
    if n >= vb["max"]:
        t.debuff["weaken"] = (vb["weaken"], now + 6)


F.venom_hit = _venom_hit


def tick_dots(P, f, now):
    for x in f.dots:
        if x[1] > now and x[2] <= now:
            x[2] += 1.0
            deal(P, x[4], f, x[0], now, "dot", dot=True, can_crit=False, evadable=False)
    f.dots = [x for x in f.dots if x[1] > now]
    n, until = f.venom
    if n > 0 and until > now and int(now * 10) % 10 == 0:
        src = getattr(f, "_venom_src", None)
        if src is not None:
            vb = next(k for k in src.kit if k["id"] == "venom_blades")["venom"]
            deal(P, src, f, vb["dps"] * n * V.SKILL_SCALE["shadow"] * src.b["sp"] * src.b["power"]["physical"], now, "dot",
                 dot=True, can_crit=False, evadable=False)


def class_skill_dmg(a, k):
    cls = a.cls
    return a.b["class_unit"] * k["dmg"]


def use_skill(P, a, t, k, now):
    """직업 스킬 하나. 쓰면 True."""
    sid = k["id"]
    if a.cd.get(sid, 0) > now or a.mp < k["mana"]:
        return False
    hpf = a.hp_frac()
    # ── 쓸지 말지 ──
    if sid == "healing_light" and hpf > 0.75:
        return False
    if sid == "resurrection_hymn" and hpf > 0.5:
        return False
    if sid in ("taunting_roar", "guardian_oath") and hpf > 0.85:
        return False
    if sid == "bulwark_citadel" and hpf > 0.6:
        return False
    if sid == "smoke_veil" and hpf > 0.9 and now > 1.0:
        return False
    if sid == "blood_frenzy" and hpf < 0.35:
        return False
    a.mp -= k["mana"]
    a.cd[sid] = now + k["cooldown"] * a.cdmult
    ultm = P["ult"] if k["ult"] else 1.0
    sm = P.get("skill_mult", {}).get(sid, 1.0) * ultm
    hit = k["hit"]
    if t.rooted(now):
        hit = max(hit, 0.95)
    if a.st.get("blind", 0) > now:
        hit *= 0.7
    if k.get("buff"):
        bf = k["buff"]
        for key in ("damage_reduction", "attack_speed", "damage", "lifesteal", "evasion", "venom"):
            if key in bf:
                a.buffs.append((key, bf[key], now + bf["seconds"], sid))
    if k.get("hp_cost"):
        a.hp -= a.hp * k["hp_cost"]
    if k.get("shield"):
        add_shield(P, a, a.b["max_hp"] * k["shield"], k.get("shield_s", 6), now)
    if k.get("heal"):
        heal(P, a, a.b["max_hp"] * k["heal"], now, flat=a.b["heal_power"] * k.get("heal_scale", 0))
        if a.cls == "priest":
            a.mp = min(a.b["max_mp"], a.mp + 2)
    if k.get("cleanse"):
        for c in ("root", "silence", "blind"):
            a.st.pop(c, None)
        a.slow = (0, 0)
        a.dots = [x for x in a.dots if x[3] not in ("bleed", "poison", "burn")]
    if sid == "smoke_veil":
        a.stealth = (now + k["stealth"], k["stealth_bonus"])
    if sid == "hunters_mark":
        if a.rng.random() < hit:
            t.debuff["mark"] = (k["debuff"][2], now + k["debuff"][1])
            t.stealth = (0.0, 0.0)
        return True
    if k["dmg"] > 0:
        if a.rng.random() < hit:
            raw = class_skill_dmg(a, k)
            crit_bonus = 0.0
            if sid == "shadow_strike":
                if a.stealth[0] > now or a.rng.random() < 0.3:
                    raw = a.b["class_unit"] * k["back_dmg"]
                    crit_bonus = 1.0
            if sid == "shadow_execution" and t.hp_frac() <= k["execute"][0]:
                raw *= 1 + k["execute"][1]
            if sid == "arcane_bolt" or sid == "frost_nova" or sid == "phase_blink" or sid == "meteor_fall":
                pass
            got = deal(P, a, t, raw, now, k["kind"], skill=True, crit_bonus=crit_bonus, big=k["ult"] or k["dmg"] >= 2.0,
                       src_mult=sm)
            if got > 0 or True:
                for (cid, dur, pot) in k["cc"]:
                    apply_cc(P, a, t, cid, dur, now, pot)
                if k.get("debuff"):
                    t.debuff[k["debuff"][0]] = (k["debuff"][2], now + k["debuff"][1])
                if k.get("dot"):
                    _, dur, ratio = k["dot"]
                    add_dot(P, a, t, ratio * V.SKILL_SCALE[a.cls] * a.b["sp"] * a.b["power"][V.CLASS_SKILL_KIND[a.cls]] * sm,
                            dur, "burn" if k["kind"] == "magic" else "bleed", now)
        if a.u.get("id") == "overcharge":
            a.overcharge = now + 5
    elif k["cc"] and sid == "bulwark_citadel":
        apply_cc(P, a, t, "slow", k["cc"][0][1], now, k["cc"][0][2])
    return True


def use_wskill(P, a, t, s, now):
    key = "w:" + s["name"]
    if a.cd.get(key, 0) > now or a.mp < s["mana"]:
        return False
    hpf = a.hp_frac()
    dmg = s["damage"] + s["execute"] * (1 if t.hp_frac() <= 0.3 else 0)
    if dmg <= 0 and s["percent"] <= 0:
        if (s["self_shield"] > 0 or s["self_heal"] > 0 or s.get("guard")) and hpf > 0.7:
            return False
        if not (s["self_shield"] > 0 or s["self_heal"] > 0 or s["self_buff"] or s.get("guard")):
            return False
    a.mp -= s["mana"]
    a.cd[key] = now + s["cooldown"] * (1 - a.b["cdr"]) * a.b["cd_look"]
    sm = P.get("skill_mult", {}).get(a.b["weapon"] + ":" + str(s["input"]), 1.0) * P["wskill"]
    if s["self_shield"] > 0:
        add_shield(P, a, a.b["max_hp"] * s["self_shield"], 5, now)
    if s["self_heal"] > 0:
        heal(P, a, a.b["max_hp"] * s["self_heal"], now)
    for k2, v in (s["self_buff"] or {}).items():
        if k2 in ("damage", "attack_speed", "crit_chance", "lifesteal", "damage_reduction"):
            try:
                a.buffs.append((k2, float(v), now + (s.get("guard") or 6.0), key))
            except (TypeError, ValueError):
                pass
    if dmg > 0 or s["percent"] > 0:
        kind = s["kind"] if s["kind"] in ("physical", "magic") else a.b["w"]["kind"]
        raw = a.b["sp"] * a.b["power"][kind] * dmg
        hitm = 1.0 if not t.rooted(now) else 1.15   # 파싱한 배율에 맞을 확률이 이미 들어 있다
        if a.st.get("blind", 0) > now:
            hitm *= 0.7
        got = deal(P, a, t, raw * min(1.25, hitm), now, kind, skill=True, big=dmg >= 2.0, src_mult=sm,
                   lifesteal_extra=s["lifesteal"])
        if s["percent"] > 0 and t.hp > 0:
            x = t.b["max_hp"] * s["percent"] * P["dmg"] * S.level_mult(max(a.L, t.L), P) * sm * S.buffer_factor(t.b, P) * (1 - S.resilience(t.b, P))
            t.hp -= x
            a.dealt += x
        for c in s["cc"]:
            cid = c["id"]
            reps = max(1, int(round(c.get("repeats", 1) or 1)))
            if cid == "frost":
                frost(P, a, t, int(c.get("stacks", 1)) * min(reps, 5), now)
                continue
            for i in range(min(reps, 3)):
                apply_cc(P, a, t, cid, c["seconds"], now + 0.05 * i, c.get("potency"))
        for (dt, dur, pot) in s["dot"]:
            ratio = pot if 0 < pot < 1 else (0.2 if dt == "ignite" else 0.15)
            add_dot(P, a, t, ratio * a.b["sp"] * a.b["power"]["magic" if dt == "ignite" else "physical"] * sm, dur,
                    "burn" if dt == "ignite" else "bleed", now)
        if a.u.get("id") == "overcharge":
            a.overcharge = now + 5
    return True


PRIO = {"healing_light": 0, "resurrection_hymn": 0, "bulwark_citadel": 1, "guardian_oath": 1, "taunting_roar": 1,
        "sacred_ward": 2, "smoke_veil": 2, "blood_frenzy": 2, "hunters_mark": 2, "venom_blades": 2,
        "shield_bash": 3, "frost_nova": 3, "evasive_trap": 4, "purifying_wave": 4}


def act(P, a, t, now):
    if a.stunned(now) or a.hp <= 0:
        return
    if a.lock_until > now:
        return
    # 물약
    if a.hp_frac() < 0.40 and a.potion_ready <= now and a.potions > 0:
        a.potions -= 1
        a.potion_ready = now + 12
        heal(P, a, a.b["max_hp"] * POTION[a.L] * P.get("potion", 1.0), now)
    if not a.silenced(now) and a.cast_ready <= now:
        order = sorted(a.kit, key=lambda k: (PRIO.get(k["id"], 5), -k["dmg"]))
        done = False
        for k in order:
            if use_skill(P, a, t, k, now):
                done = True
                break
        if not done:
            for s in sorted(a.wsk, key=lambda s: -(s["damage"] + s["percent"] * 10)):
                if use_wskill(P, a, t, s, now):
                    done = True
                    break
        if done:
            a.cast_ready = now + 0.25
            a.next_basic = max(a.next_basic, now + 0.15)
            return
    if now >= a.next_basic:
        basic(P, a, t, now)
        a.next_basic = now + a.period(now)


F.cast_ready = 0.0


def duel(ba, bb, P, n=60, seed=1):
    wins = [0, 0]
    draws = 0
    times = []
    left = [[], []]
    cc = [0.0, 0.0]
    chains = []
    for i in range(n):
        rng = random.Random(seed * 1000003 + i)
        a = F(ba, P, rng)
        b = F(bb, P, rng)
        a._venom_src = None
        b._venom_src = None
        if a.cls == "shadow":
            b._venom_src = a
        if b.cls == "shadow":
            a._venom_src = b
        now = 0.0
        while now < MAX_T and a.hp > 0 and b.hp > 0:
            hp_regen_a = a.b["hp_regen"] * DT * P["heal"] * S.buffer_factor(a.b, P)
            hp_regen_b = b.b["hp_regen"] * DT * P["heal"] * S.buffer_factor(b.b, P)
            a.hp = min(a.b["max_hp"], a.hp + hp_regen_a)
            b.hp = min(b.b["max_hp"], b.hp + hp_regen_b)
            a.mp = min(a.b["max_mp"], a.mp + a.b["mana_regen"] * DT)
            b.mp = min(b.b["max_mp"], b.mp + b.b["mana_regen"] * DT)
            first, second = (a, b) if rng.random() < 0.5 else (b, a)
            act(P, first, second, now)
            if second.hp > 0:
                act(P, second, first, now)
            tick_dots(P, a, now)
            tick_dots(P, b, now)
            # 수호 기운 (자신)
            for f in (a, b):
                if f.u.get("id") == "ward_aura" and now >= f.ward_next:
                    f.ward_next = now + f.u.get("period", 8)
                    add_shield(P, f, f.b["max_hp"] * f.u.get("pct", 0.04), f.u.get("duration", 6), now)
            now += DT
        cc[0] += a.cc_time
        cc[1] += b.cc_time
        chains.append(max(getattr(a, "max_chain", 0.0), getattr(b, "max_chain", 0.0)))
        if a.hp > 0 and b.hp <= 0:
            wins[0] += 1
            left[0].append(a.hp_frac())
            times.append(now)
        elif b.hp > 0 and a.hp <= 0:
            wins[1] += 1
            left[1].append(b.hp_frac())
            times.append(now)
        else:
            draws += 1
    times.sort()
    med = times[len(times) // 2] if times else MAX_T
    return dict(win_a=wins[0] / n, win_b=wins[1] / n, draw=draws / n, ttk=med,
                left_a=sum(left[0]) / max(1, len(left[0])), left_b=sum(left[1]) / max(1, len(left[1])),
                cc_a=cc[0] / n, cc_b=cc[1] / n, chain=max(chains) if chains else 0.0,
                chain_med=sorted(chains)[len(chains) // 2] if chains else 0.0)


if __name__ == "__main__":
    import pv_build as B
    import sys
    P = S.PVP_NOCAP
    L = int(sys.argv[1]) if len(sys.argv) > 1 else 35
    bl = {(c, k): B.build(c, L, k) for c in V.CLASS_ORDER for k in ("burst", "guard")}
    for ca in V.CLASS_ORDER:
        row = []
        for cb in V.CLASS_ORDER:
            r = duel(bl[(ca, "burst")], bl[(cb, "guard")], P, n=30)
            row.append(f"{r['win_a']*100:4.0f}/{r['ttk']:4.1f}")
        print(f"{ca:9} burst vs guard: " + " ".join(row))
