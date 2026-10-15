#!/usr/bin/env python3
"""
TASK B — 겉모습 시뮬레이션 (combat_spec 의 ce_sim 위에 겉모습만 얹는다).

  · 플레이어 능력치 = lk_model.build (같은 장비·분배·세트 효과·겉모습 숨은 효과) — 레벨이 오르면 같은 장비로 다시 계산
  · 이동 속도: 겉모습이 바꾼 몫 Δ(판금 −, 가죽 +)만큼 경고 피하기 창을 늘이고 줄인다 (w' = 0.3 + (w − 0.3)(1 + 1.0·Δ)),
              거리를 벌리는 직업(사냥꾼)은 근접 몹이 닿는 비율 × (1 − 1.5·Δ)
  · 4부위: 가죽 '구르기' = 8초마다 한 번, 피하지 못한 경고 공격을 실력만큼(초보 30% · 보통 50% · 숙련 70%) 굴러서 피함
           천 '마나 보호막' = 받는 피해 20% 를 MP 로 (피해 2 = MP 1), MP 25% 아래면 꺼짐
           판금 '버팀' = 밀려남·기절 (시뮬레이터에 플레이어 기절·밀려남이 없어 0 으로 봄 — 보수적)
  · 비교 기준(base) = combat_spec 그대로: 직업 대표 방어구, 겉모습 효과 없음, 0.3.4 방어구 요구치. 같은 시드.
  · 기준·변형 모두 세트 효과, 장비 받는 피해 감소·재사용 감소·스킬 피해 줄을 넣는다 (ce_sim 은 뺐던 것 — 비교는 같은 조건).

  python3 lk_sim.py smoke | full
"""
import json
import multiprocessing as mp
import os
import random
import sys

import ce_core as C
import ce_model as M
import ce_sim as X
import ce_simbase as S
import lk_core as K
import lk_model as LM

HERE = os.path.dirname(os.path.abspath(__file__))
DASH_P = {"novice": 0.30, "average": 0.50, "skilled": 0.70}
MS_K = 1.0
KITE_K = 1.5
CUR = {}
BASE_FIGHT = X.FightX.__bases__[0]   # ce_simbase.Fight (ce_sim 이 S.Fight 를 FightX 로 바꿔 둠)


def gear_for(cls, L, look, looks=True, new_req=True, include_new=False):
    wid, _ = M.gear_for(cls, L)
    accs = LM.accessories(cls, L)
    if look == "native":
        armor = LM.native_armor(cls, L)
    else:
        armor = LM.pick_armor(cls, L, look, include_new, looks=looks, new_req=new_req, wid=wid)
    return dict(wid=wid, armor=armor, accs=accs, look=look, looks=looks, new_req=new_req)


class PlayerL(X.PlayerX):
    def __init__(self, cls_id, level, scn, extra_gear=None):
        self.lk = scn["lk_gear"][cls_id]
        self._cd0 = None
        super().__init__(cls_id, level, scn, [self.lk["wid"]])

    def recompute(self):
        scn = self.scn
        g = self.lk
        if self._cd0 is None:
            self._cd0 = [s["cooldown"] for s in self.c["skills"]]
        b = LM.build(self.cls_id, self.level, {"_fixed": g["armor"]}, looks=g["looks"], new_req=g["new_req"],
                     sets=True, wid=g["wid"], accs=g["accs"])
        d = b["d"]
        self.b = b
        self.s = b["stats"]
        self.points = b["alloc"]
        self.ap = b["ap"]
        self.skill_ap = b["skill_ap"]
        self._sp_base = b["skill_ap"]
        self.style, self.interval = b["style"], b["interval"]
        self.max_hp = d["max_hp"]
        self.max_mp = d["max_mp"]
        self.defense = d["defense"]
        self.crit = d["crit"]
        self.crit_dmg = d["crit_dmg"]
        self.atk_speed = d["atk_speed"]
        self.evasion = d["evasion"]
        self.mana_regen = d["mana_regen"]
        self.heal_power = d["heal_power"]
        self.hp_regen = b["bonus"].get("hp_regen", 0)
        self.dr = d["dr"]
        self.block = b["bonus"].get("block_chance", 0)
        self.lifesteal = d["lifesteal"]
        P = X.P_FINAL
        self.bow_full = P["keen_eye"] if self.cls_id == "hunter" else 1.0
        self.magic_bonus = P.get("priest_magic", 0.0) if self.cls_id == "priest" else 0.0
        self.bow_partial = 0.6
        self.skill_mult = 1.0 + d["skill_dmg"]
        for s, c0 in zip(self.c["skills"], self._cd0):
            s["cooldown"] = c0 * (1 - d["cdr"]) * d["cd_mult"]
        imp = b["imp"]
        self.move_delta = imp.get("move_speed", 0.0)
        self.full = b["full"] if g["looks"] else None
        self.hp = min(getattr(self, "hp", 0) or 0, self.max_hp)


class FightL(X.FightX):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.dash_ready = 0.0
        self.ms_absorbed = 0.0
        self.dashes = 0
        pl = self.pl
        md = getattr(pl, "move_delta", 0.0)
        if md and S.STYLE[pl.cls_id] == "kite":
            self.prof = dict(self.prof)
            for k in ("e_kite", "boss_e_kite"):
                self.prof[k] = max(0.05, min(0.95, self.prof[k] * (1 - KITE_K * md)))

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
        if getattr(pl, "full", None) == "cloth":
            f = K.LOOKS["cloth"]["full"]
            m = (1.0 if true else 100.0 / (100.0 + pl.defense)) * (1 - min(0.9, pl.dr))
            cost = f["absorb"] * raw * m / f["damage_per_mp"]
            if pl.mp - cost >= f["off_below"] * pl.max_mp:
                pl.mp -= cost
                self.ms_absorbed += f["absorb"] * raw * m
                raw *= 1 - f["absorb"]
        BASE_FIGHT.hurt(self, raw, true, frontal)

    def run(self, max_t=600, boss_ctl=None):
        CUR["f"] = self
        try:
            return super().run(max_t, boss_ctl)
        finally:
            CUR.pop("f", None)


_orig_dodge = S.dodge_p


def dodge_p(w, prof):
    f = CUR.get("f")
    if f is None:
        return _orig_dodge(w, prof)
    pl = f.pl
    md = getattr(pl, "move_delta", 0.0)
    w2 = 0.3 + (w - 0.3) * (1 + MS_K * md) if w > 0.3 else w
    p = _orig_dodge(w2, prof)
    if getattr(pl, "full", None) == "light" and f.t >= f.dash_ready:
        pd = DASH_P.get(getattr(f, "prof_id", "average"), 0.5)
        if random.random() < (1 - p) * pd:
            f.dash_ready = f.t + K.LOOKS["light"]["full"]["cooldown"]
            f.dashes += 1
            return 1.0
    return p


S.dodge_p = dodge_p
S.Player = PlayerL
S.Fight = FightL


def scenario(gear):
    scn = X.scenario("new")
    scn["lk_gear"] = gear
    return scn


def solo(scn, cls, prof, diff, floor, runs, seed):
    random.seed(seed)
    cleared = 0
    died = {}
    room_t, boss_t, taken = [], [], []
    for _ in range(runs):
        pots = None if floor == 1 else 10
        r = X.RunX(cls, X.entry_level(floor), prof, diff, scn, floor, potions=pots, extra_gear=[scn["lk_gear"][cls]["wid"]])
        out = r.run_floor()
        if out["cleared"]:
            cleared += 1
            if r.times["boss"] is not None:
                boss_t.append(r.times["boss"])
        else:
            died[out["died_at"]] = died.get(out["died_at"], 0) + 1
        room_t += r.times["combat"]
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    return dict(clear=round(cleared / runs, 3), room_t=avg(room_t), boss_t=avg(boss_t),
                deaths=sorted(((k, round(v / runs, 3)) for k, v in died.items()), key=lambda x: -x[1])[:2])


def room(scn, cls, floor, prof, n=60, seed=7):
    """방 전투 1개(죽지 않게) — 초당 피해·받은 피해(최대 HP 비율)."""
    tot = tt = taken = ms = 0.0
    dash = 0
    for i in range(n):
        r = X.RunX(cls, X.entry_level(floor), prof, "normal", scn, floor, potions=0, extra_gear=[scn["lk_gear"][cls]["wid"]])
        random.seed(seed * 100003 + i)
        mobs = S.make_room_mobs(floor, scn, r.ctx_hp, r.ctx_dmg, "combat", 1)
        random.seed(seed * 7919 + i + 17)
        f = S.Fight(r.pl, mobs, r.prof, r.diff, scn, floor, r.ctx_hp, r.ctx_dmg, 0, immortal=True)
        f.prof_id = prof
        f.run(max_t=600)
        tot += f.dealt
        tt += f.t
        taken += f.taken / r.pl.max_hp
        ms += f.ms_absorbed / r.pl.max_hp
        dash += f.dashes
    return dict(dps=round(tot / tt, 1), taken=round(taken / n, 3), ms=round(ms / n, 3), dash=round(dash / n, 2))


VARIANTS = ["base", "native_noimp", "native", "heavy", "light", "cloth"]


def gear_table(floor, variant):
    L = X.entry_level(floor)
    out = {}
    for cls in LM.CLASSES:
        if variant == "base":
            out[cls] = gear_for(cls, L, "native", looks=False, new_req=False)
        elif variant == "native":
            out[cls] = gear_for(cls, L, LM.NATIVE[cls])
        elif variant == "native_noimp":
            g = gear_for(cls, L, LM.NATIVE[cls])
            out[cls] = dict(g, looks=False, new_req=False)
        else:
            out[cls] = gear_for(cls, L, variant)
    return out


def job(a):
    kind, floor, variant, cls, prof, diff, runs = a
    scn = scenario(gear_table(floor, variant))
    if kind == "solo":
        return a, solo(scn, cls, prof, diff, floor, runs, seed=1000 + floor)
    return a, room(scn, cls, floor, prof)


def main(mode):
    floors = [3, 6, 10] if mode == "full" else [3]
    runs = 40 if mode == "full" else 8
    jobs = []
    for fl in floors:
        for v in VARIANTS:
            for cls in LM.CLASSES:
                jobs.append(("room", fl, v, cls, "skilled", "normal", 0))
                for prof, diff in (("average", "normal"), ("skilled", "normal"), ("skilled", "hard")):
                    jobs.append(("solo", fl, v, cls, prof, diff, runs))
    if mode == "full":
        for v in ("native_noimp", "native", "heavy"):
            for cls in LM.CLASSES:
                for prof in ("novice", "average"):
                    jobs.append(("solo", 2, v, cls, prof, "normal", runs))
                jobs.append(("solo", 2, v, cls, "skilled", "hard", runs))
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    out = {"|".join(str(x) for x in a[:6]): r for a, r in res}
    with open(os.path.join(HERE, f"lk_sim_{mode}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    for k, r in out.items():
        print(k, r)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "smoke")
