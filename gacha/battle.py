"""자동 전투 시뮬레이션.

전투는 전부 서버에서 돌리고 클라이언트에는 재생용 로그만 내려간다.
(클라이언트가 승패를 주장할 수 없게 해서 보상 조작을 막는다.)

규칙 요약
  · 라운드마다 살아있는 모든 유닛이 속도 내림차순으로 1회 행동
  · 행동할 때마다 기력 +25, 100이 되면 스킬 사용 후 0으로
  · 피해 = 공격력 × 배율 × 상성 × 방어경감 × 난수(0.92~1.08), 치명타 12% ×1.5
  · 방어경감 = 300 / (300 + 방어력)
  · 20라운드 안에 적을 전멸시키지 못하면 패배
"""

from __future__ import annotations

import random

from . import econ
from .content import ADVANTAGE, DISADVANTAGE, ELEMENTS, BY_ID
from .state import unit_stats

MAX_ROUNDS = 20
DEF_K = 300
CRIT_RATE = 0.12
CRIT_MULT = 1.5


def elem_mult(att: str, dfn: str) -> float:
    if ELEMENTS.get(att, {}).get("beats") == dfn:
        return ADVANTAGE
    if ELEMENTS.get(dfn, {}).get("beats") == att:
        return DISADVANTAGE
    return 1.0


class Unit:
    def __init__(self, uid, name, element, stats, skill, side, portrait=None):
        self.uid = uid
        self.name = name
        self.element = element
        self.max_hp = stats["hp"]
        self.hp = stats["hp"]
        self.atk = stats["atk"]
        self.dfn = stats["def"]
        self.spd = stats["spd"]
        self.skill = skill
        self.side = side
        self.portrait = portrait
        self.energy = 0
        self.shield = 0
        self.atk_buff = 0.0
        self.buff_turns = 0
        self.slow_turns = 0
        self.burn = 0        # 남은 화상 턴
        self.burn_dmg = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def eff_atk(self) -> int:
        return int(self.atk * (1 + self.atk_buff))

    @property
    def eff_spd(self) -> int:
        return int(self.spd * (0.8 if self.slow_turns > 0 else 1.0))

    def take(self, dmg: int) -> int:
        absorbed = min(self.shield, dmg)
        self.shield -= absorbed
        real = dmg - absorbed
        self.hp = max(0, self.hp - real)
        return dmg

    def snapshot(self) -> dict:
        return {"uid": self.uid, "hp": self.hp, "max": self.max_hp,
                "shield": self.shield, "energy": self.energy}


def build_team(st: dict) -> list[Unit]:
    units = []
    for cid in st["team"][:4]:
        entry = st["roster"].get(cid)
        if not entry:
            continue
        c = BY_ID[cid]
        units.append(Unit(f"a_{cid}", c["name"], c["element"],
                          unit_stats(cid, entry), c["skill"], "ally", cid))
    return units


def build_enemies(stage: dict, seed: int) -> list[Unit]:
    r = random.Random(seed ^ 0x5EED)
    ch = next(c for c in econ.CHAPTERS if c["id"] == stage["chapter"])
    p = ch["power"] * (1 + 0.16 * (stage["stage"] - 1))
    el = stage["element"]
    skill = {"name": "포효", "kind": "nuke", "power": 1.6, "desc": ""}
    out = []
    if stage["boss"]:
        out.append(Unit("e_boss", stage["name"], el,
                        {"hp": int(2600 * p), "atk": int(96 * p),
                         "def": int(58 * p ** 0.7), "spd": 100},
                        {"name": "붕괴의 일격", "kind": "aoe", "power": 1.15,
                         "desc": ""}, "enemy"))
        n = 2
    else:
        n = 3
    for i in range(n):
        out.append(Unit(f"e_{i}", r.choice(econ.ENEMY_NAMES), el,
                        {"hp": int(820 * p), "atk": int(74 * p),
                         "def": int(40 * p ** 0.7), "spd": 88 + r.randint(0, 18)},
                        skill, "enemy"))
    return out


def _damage(src: Unit, tgt: Unit, mult: float, r: random.Random,
            pierce: float = 0.0) -> tuple[int, bool]:
    dfn = tgt.dfn * (1 - pierce)
    mit = DEF_K / (DEF_K + dfn)
    crit = r.random() < CRIT_RATE
    dmg = src.eff_atk * mult * elem_mult(src.element, tgt.element) * mit
    dmg *= r.uniform(0.92, 1.08)
    if crit:
        dmg *= CRIT_MULT
    return max(1, int(dmg)), crit


def _pick_target(units: list[Unit], r: random.Random, lowest=False) -> Unit | None:
    alive = [u for u in units if u.alive]
    if not alive:
        return None
    if lowest:
        return min(alive, key=lambda u: u.hp / u.max_hp)
    return r.choice(alive)


def simulate(allies: list[Unit], enemies: list[Unit], seed: int) -> dict:
    r = random.Random(seed)
    log: list[dict] = []

    def ev(**kw):
        log.append({**kw, "state": [u.snapshot() for u in allies + enemies]})

    ev(kind="start", text="전투 시작")

    for rnd in range(1, MAX_ROUNDS + 1):
        order = sorted([u for u in allies + enemies if u.alive],
                       key=lambda u: -u.eff_spd)
        for u in order:
            if not u.alive:
                continue
            foes = enemies if u.side == "ally" else allies
            friends = allies if u.side == "ally" else enemies
            if not any(f.alive for f in foes):
                break

            u.energy = min(100, u.energy + 25)
            use_skill = u.energy >= 100
            sk = u.skill
            kind = sk["kind"] if use_skill else "attack"

            if use_skill:
                u.energy = 0

            if kind == "attack":
                t = _pick_target(foes, r)
                dmg, crit = _damage(u, t, 1.0, r)
                t.take(dmg)
                ev(kind="attack", round=rnd, src=u.uid, tgt=t.uid, dmg=dmg,
                   crit=crit, text=f"{u.name} → {t.name} {dmg:,}")
            elif kind in ("nuke",):
                lowest = u.portrait in ("kaguya", "hazel")
                t = _pick_target(foes, r, lowest=lowest)
                pierce = 0.3 if u.portrait == "sylphid" else 0.0
                dmg, crit = _damage(u, t, sk["power"], r, pierce)
                if u.portrait == "hazel" and t.hp / t.max_hp <= 0.5:
                    dmg = int(dmg * 1.3)
                t.take(dmg)
                ev(kind="skill", round=rnd, src=u.uid, tgt=t.uid, dmg=dmg,
                   crit=crit, skill=sk["name"],
                   text=f"⚡ {u.name}「{sk['name']}」 → {t.name} {dmg:,}")
                if u.portrait == "miyu":
                    u.atk_buff += 0.10
            elif kind == "aoe":
                hits = []
                for t in [f for f in foes if f.alive]:
                    dmg, crit = _damage(u, t, sk["power"], r)
                    t.take(dmg)
                    hits.append({"tgt": t.uid, "dmg": dmg})
                if u.portrait == "ignis":
                    for t in [f for f in foes if f.alive]:
                        t.burn, t.burn_dmg = 2, int(u.eff_atk * 0.25)
                ev(kind="skill", round=rnd, src=u.uid, hits=hits,
                   skill=sk["name"],
                   text=f"⚡ {u.name}「{sk['name']}」 전체 "
                        f"{sum(h['dmg'] for h in hits):,}")
            elif kind == "heal":
                amount = int(u.eff_atk * sk["power"])
                targets = [f for f in friends if f.alive]
                weakest = min(targets, key=lambda x: x.hp / x.max_hp) if targets else None
                healed = []
                for t in targets:
                    a = amount * (2 if (u.portrait == "noelle" and t is weakest) else 1)
                    before = t.hp
                    t.hp = min(t.max_hp, t.hp + a)
                    healed.append({"tgt": t.uid, "heal": t.hp - before})
                ev(kind="skill", round=rnd, src=u.uid, heals=healed,
                   skill=sk["name"],
                   text=f"✚ {u.name}「{sk['name']}」 회복 "
                        f"{sum(h['heal'] for h in healed):,}")
            elif kind == "buff":
                for t in [f for f in friends if f.alive]:
                    t.atk_buff += sk["power"]
                    t.buff_turns = 3
                ev(kind="skill", round=rnd, src=u.uid, skill=sk["name"],
                   text=f"↑ {u.name}「{sk['name']}」 아군 공격력 "
                        f"{int(sk['power'] * 100)}% 상승")
            elif kind == "shield":
                amount = int(u.max_hp * sk["power"] * 0.45)
                for t in [f for f in friends if f.alive]:
                    t.shield += amount
                ev(kind="skill", round=rnd, src=u.uid, skill=sk["name"],
                   text=f"◇ {u.name}「{sk['name']}」 보호막 {amount:,}")

            if not any(f.alive for f in foes):
                break

        # 라운드 종료 처리: 화상 · 버프 지속시간
        for u in allies + enemies:
            if u.alive and u.burn > 0:
                u.burn -= 1
                u.take(u.burn_dmg)
                if not u.alive:
                    ev(kind="burn", round=rnd, tgt=u.uid, dmg=u.burn_dmg,
                       text=f"🔥 {u.name} 화상으로 쓰러짐")
            if u.buff_turns > 0:
                u.buff_turns -= 1
                if u.buff_turns == 0:
                    u.atk_buff = 0.0
            if u.slow_turns > 0:
                u.slow_turns -= 1

        if not any(e.alive for e in enemies) or not any(a.alive for a in allies):
            break

    win = any(a.alive for a in allies) and not any(e.alive for e in enemies)
    ev(kind="end", text="승리!" if win else "패배…")
    return {
        "win": win,
        "rounds": rnd,
        "log": log,
        "units": [{"uid": u.uid, "name": u.name, "side": u.side,
                   "element": u.element, "portrait": u.portrait,
                   "max": u.max_hp, "hp": u.hp}
                  for u in allies + enemies],
    }
