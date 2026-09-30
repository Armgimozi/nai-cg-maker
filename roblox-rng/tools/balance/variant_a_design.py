#!/usr/bin/env python3
"""변형 A "순한 안" — 확률표·환생 단계 만들기 + 빠른 진행 속도 점검(몬테카를로).

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/variant_a_design.py                 # balance/variant_a.json 다시 쓰기 + 표 요약
  python3 tools/balance/variant_a_design.py --sim 12        # 무료/유료 플레이어 시드 12개씩
  python3 tools/balance/variant_a_design.py --sim 12 --baseline   # 지금 규칙(기준)도 같이

게임 코드는 읽기만 합니다(src/shared/Landmarks.luau 에서 명소 Id·N·대륙).
시뮬레이터는 PlayerState/RollLogic 규칙을 파이썬으로 옮긴 것(굴림 판정·별·공원 36칸·업그레이드·여권 도장·
환생 초기화·게임패스·부스트) + AUTO 굴림 간격 모형(쿨타임과 결과 연출 시간 중 긴 쪽).
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import random
import re
import statistics
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_JSON = os.path.join(ROOT, "balance", "variant_a.json")


# ----------------------------------------------------------------------------- 지금 게임 값


def load_landmarks() -> list[dict]:
    src = open(os.path.join(ROOT, "src/shared/Landmarks.luau"), encoding="utf-8").read()
    rows = re.findall(r'\{ "(\w+)", "([^"]*)", "[^"]*", (\d+), "(\w+)"', src)
    assert len(rows) == 150, len(rows)
    return [dict(id=i, name=nm, n=int(n), region=r) for i, nm, n, r in rows]


CURRENT = load_landmarks()
OLD_N = {lm["id"]: lm["n"] for lm in CURRENT}
REGION = {lm["id"]: lm["region"] for lm in CURRENT}
NAME = {lm["id"]: lm["name"] for lm in CURRENT}
OLD_TIERS = [1, 10, 100, 1000, 10000, 100000, 1000000]
TIER_NAMES = ["일반 명소", "도시 명소", "국가 명소", "세계 명소", "불가사의", "잃어버린 유산", "전설"]


def rank_of(n: int, mins: list[int]) -> int:
    rank = 1
    for i, m in enumerate(mins):
        if n >= m:
            rank = i + 1
    return rank


OLD_RANK = {i: rank_of(n, OLD_TIERS) for i, n in OLD_N.items()}

BASELINE = {
    "name": "현재 규칙(기준)",
    "landmarks": dict(OLD_N),
    "tiers": [{"rank": i + 1, "minOneIn": m} for i, m in enumerate(OLD_TIERS)],
    "tierIncome": [1, 2, 5, 12, 30, 80, 250],
    "rebirth": {
        "luck": "linear",
        "luckBonus": 0.2,
        "incomeBonus": 0.5,
        "steps": [
            {"coins": 5000, "landmarks": ["eiffel", "liberty"]},
            {"coins": 30000, "landmarks": ["colosseum", "tajmahal"]},
            {"coins": 150000, "landmarks": ["sphinx", "greatwall"]},
            {"coins": 600000, "landmarks": ["pyramid", "chichen", "machupicchu"]},
            {"coins": 2500000, "landmarks": ["petra", "moai", "stonehenge"]},
            {"coins": 10000000, "landmarks": ["alexandria", "reef"]},
            {"coins": 40000000, "landmarks": ["babylon", "rhodes", "nanmadol"]},
            {"coins": 160000000, "landmarks": ["babel"]},
            {"coins": 640000000, "landmarks": ["atlantis", "eldorado"]},
            {"coins": 2560000000, "landmarks": ["yonggung"]},
        ],
    },
    "announceOneIn": 1000,
    "hologramOneIn": 10000,
    "discoveryBonusMult": 5,
}

# ----------------------------------------------------------------------------- 변형 A: 확률 늘이기

KEEP_BELOW = 1000  # 1~3등급(N < 1,000)은 그대로
OLD_RAREST = 40_000_000  # 세계수(지금)
NEW_RAREST = 5_000_000_000  # 세계수(변형 A) — 50억

# log10 공간에서 x = log10(N / 1000) 을 y = x + a·x² 로 늘림(1,000 에서 기울기 1 로 이어짐 → 세계 명소는 거의 그대로,
# 희귀할수록 더 많이 늘어남). a 는 지금 가장 희귀한 4천만이 50억이 되게 풂.
_X_TOP = math.log10(OLD_RAREST / KEEP_BELOW)
STRETCH_A = (math.log10(NEW_RAREST / KEEP_BELOW) - _X_TOP) / (_X_TOP * _X_TOP)


def stretch(n: float) -> float:
    if n < KEEP_BELOW:
        return float(n)
    x = math.log10(n / KEEP_BELOW)
    return KEEP_BELOW * 10 ** (x + STRETCH_A * x * x)


# "친절한" 숫자: 1 in 1,100 / 2,500 / 40,000,000 처럼 앞자리가 깔끔한 수.
# 먼저 굵은 격자(앞 두 자리)에서 가장 가까운 수, 앞 명소와 겹치면 고운 격자(간격 5% 이하)에서 고름
MANTISSAS = [1, 1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 1.7, 1.75, 1.8, 1.9,
             2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5]
FINE = sorted(set([round(1 + 0.05 * i, 2) for i in range(20)] + [round(2 + 0.1 * i, 1) for i in range(30)]
                  + [round(5 + 0.25 * i, 2) for i in range(20)]))
GRID = sorted({int(round(m * 10 ** k)) for k in range(3, 11) for m in MANTISSAS})
FINE_GRID = sorted({int(round(m * 10 ** k)) for k in range(3, 11) for m in FINE} | set(GRID))


def nearest(grid: list[int], v: float) -> int:
    i = bisect.bisect_left(grid, v)
    cands = [grid[j] for j in (i - 1, i) if 0 <= j < len(grid)]
    return min(cands, key=lambda g: abs(math.log(g / v)))


def friendly(v: float) -> int:
    return nearest(GRID, v)


def build_odds() -> dict[str, int]:
    """모든 명소의 새 N. 순서(희귀도 순위)는 그대로, 겹치면 고운 격자 → 그래도 겹치면 바로 위 수."""
    ordered = sorted(CURRENT, key=lambda lm: (lm["n"], CURRENT.index(lm)))
    result: dict[str, int] = {}
    prev = 0
    for lm in ordered:
        if lm["n"] < KEEP_BELOW:
            v = lm["n"]
        else:
            raw = stretch(lm["n"])
            v = nearest(GRID, raw)
            if v <= prev:
                v = nearest(FINE_GRID, raw)
            if v <= prev:
                v = FINE_GRID[bisect.bisect_right(FINE_GRID, prev)]
        assert v > prev or (v == prev and lm["n"] < KEEP_BELOW), lm
        result[lm["id"]] = v
        prev = v
    result[ordered[-1]["id"]] = NEW_RAREST
    return result


NEW_N = build_odds()


def build_tiers(odds: dict[str, int]) -> list[int]:
    mins = [1, 10, 100, 1000]
    for old_min in OLD_TIERS[4:]:
        mins.append(friendly(stretch(old_min)))
    # 등급 소속은 지금과 똑같아야 함(여권 도장·테스트의 등급 경계·이름의 뜻이 그대로 유지)
    for i, n in odds.items():
        assert rank_of(n, mins) == OLD_RANK[i], (i, n, rank_of(n, mins), OLD_RANK[i])
    return mins


NEW_TIERS = build_tiers(NEW_N)

VARIANT_A = {
    "name": "A 순한 안 (moderate): 환생 행운 x2^r, 1~3등급 그대로, 가장 희귀 1/50억",
    "landmarks": NEW_N,
    "tiers": [{"rank": i + 1, "name": TIER_NAMES[i], "minOneIn": m} for i, m in enumerate(NEW_TIERS)],
    "tierIncome": [1, 2, 5, 12, 30, 80, 250],
    "rebirth": {
        "luck": "x2",
        "luckBase": 2,
        "incomeBonus": 0.5,
        "steps": [
            {"coins": 5_000, "landmarks": ["eiffel", "liberty"]},
            {"coins": 300_000, "landmarks": ["sphinx", "pyramid"]},
            {"coins": 3_000_000, "landmarks": ["petra", "moai", "stonehenge"]},
            {"coins": 30_000_000, "landmarks": ["alexandria", "babylon", "artemis"]},
            {"coins": 200_000_000, "landmarks": ["rhodes", "zeus", "mausoleum"]},
            {"coins": 1_500_000_000, "landmarks": ["babel", "trojanhorse", "libraryalex"]},
            {"coins": 8_000_000_000, "landmarks": ["atlantis", "eldorado"]},
            {"coins": 30_000_000_000, "landmarks": ["fountainofyouth", "hwangnyongsa"]},
            {"coins": 100_000_000_000, "landmarks": ["yonggung", "mu"]},
            {"coins": 300_000_000_000, "landmarks": ["shangrila"]},
        ],
    },
    "announceOneIn": 1000,
    "hologramOneIn": 10000,
    "discoveryBonusMult": 5,
    "notes": "",
}

# ----------------------------------------------------------------------------- 시뮬레이터

UPGRADES = [  # Config.Upgrades 그대로: id, 기본 가격, 증가율, 최대 레벨, 레벨당
    ("Globe", 400, 1.7, 20, 0.10),
    ("Agency", 300, 1.8, 10, 0.05),
    ("Park", 250, 2.0, 10, 3),
    ("Ticket", 500, 1.9, 15, 0.20),
]
STAR_T = [1, 3, 10, 30, 100]
STAR_BONUS = 0.5
BASE_SLOTS = 6
REGION_LUCK = 0.25
STAMP_MAX_RANK = 5
ROLL_COOLDOWN = 1.2
REVEAL = [0.9, 1.1, 1.5, 2.1, 2.7, 3.1, 3.3]  # Hud.REVEAL_SECONDS
RTT = 0.15  # 요청 왕복 + 0.05 초 자동 굴림 폴링


def stars(c: int) -> int:
    s = 0
    for i, th in enumerate(STAR_T):
        if c >= th:
            s = i + 1
    return s


def auto_reveal(rank: int) -> float:
    """AUTO(Fast) 에서 Hud.reveal 이 끝나기까지 걸리는 시간(초)."""
    if rank < 4:
        return max(0.35, REVEAL[rank - 1] * 0.5) + 0.2 + 0.2
    return REVEAL[rank - 1] + 0.4 + (0.9 if rank >= 5 else 0) + 1.8


PLAYERS = {
    "free": dict(vip=False, fast=False, dbl=False, boost=0.0, server=0.0),
    # 게임패스 3개 + 가끔 부스트: 15분 칸마다 개인 행운 부스트 8%, 서버 행운(누가 산 것) 10% 확률로 켜짐
    "payer": dict(vip=True, fast=True, dbl=True, boost=0.08, server=0.10),
}


def luck_mult(reb: dict, r: int) -> float:
    if reb["luck"] == "linear":
        return 1 + reb["luckBonus"] * r
    return reb["luckBase"] ** r


class Sim:
    def __init__(self, v: dict, player: str, model: str, seed: int, max_days: float = 200):
        self.v = v
        self.p = PLAYERS[player]
        self.model = model  # "code": 지금 연출 시간 / "fix": 이미 발견한 명소는 짧은 연출
        self.rng = random.Random(seed)
        self.max_t = max_days * 86400
        mins = [t["minOneIn"] for t in v["tiers"]]
        self.order = sorted(v["landmarks"].items(), key=lambda kv: -kv[1])  # 희귀한 것부터
        self.rank = {i: rank_of(n, mins) for i, n in v["landmarks"].items()}
        self.n = dict(v["landmarks"])
        self.inc_tier = v["tierIncome"]
        self.steps = v["rebirth"]["steps"]
        self.reb = v["rebirth"]
        self.bonus_mult = v.get("discoveryBonusMult", 5)
        self.stamp_need = {}
        for i, n in self.n.items():
            if self.rank[i] <= STAMP_MAX_RANK:
                self.stamp_need.setdefault(REGION[i], set()).add(i)
        self.dist_cache: dict[float, list[float]] = {}

    # -- 굴림 분포(RollLogic.probabilities 와 같은 식)
    def cdf(self, luck: float) -> list[float]:
        key = round(luck, 9)
        c = self.dist_cache.get(key)
        if c is None:
            c = []
            rem, acc = 1.0, 0.0
            for idx, (_, n) in enumerate(self.order):
                if idx == len(self.order) - 1:
                    p = rem
                else:
                    q = min(1.0, luck / n)
                    p = rem * q
                    rem *= 1 - q
                acc += p
                c.append(acc)
            c[-1] = 1.0
            if len(self.dist_cache) > 4000:
                self.dist_cache.clear()
            self.dist_cache[key] = c
        return c

    def run(self) -> dict:
        p = self.p
        rng = self.rng
        t = 0.0
        coins = 0.0
        inv: dict[str, int] = {}
        disc: set[str] = set()
        up = {u[0]: 0 for u in UPGRADES}
        r = 0
        stamps = 0
        boost_on = server_on = False
        next_block = 0.0
        income = 0.0
        income_dirty = True
        rolls = 0
        run_rolls = 0
        run_start = 0.0
        lm_met_at = None
        events = {"rebirth": [], "first_rank": {}, "first": {}, "runs": []}
        n_steps = len(self.steps)
        while t < self.max_t:
            if t >= next_block:
                boost_on = rng.random() < p["boost"]
                server_on = rng.random() < p["server"]
                next_block += 900
            luck = (1 + 0.1 * up["Globe"]) * (1 + REGION_LUCK * stamps) * luck_mult(self.reb, r)
            if p["vip"]:
                luck *= 2
            if boost_on:
                luck *= 2
            if server_on:
                luck *= 2
            cd = ROLL_COOLDOWN * (1 - 0.05 * up["Agency"]) * (0.7 if p["fast"] else 1)
            c = self.cdf(luck)
            idx = bisect.bisect_right(c, rng.random())
            if idx >= len(self.order):
                idx = len(self.order) - 1
            lid, n = self.order[idx]
            rk = self.rank[lid]
            rolls += 1
            run_rolls += 1
            before = inv.get(lid, 0)
            inv[lid] = before + 1
            is_new = lid not in disc
            if is_new:
                disc.add(lid)
                coins += math.ceil(self.bonus_mult * n ** 0.5)
                events["first"][lid] = t
                if rk not in events["first_rank"]:
                    events["first_rank"][rk] = t
                if rk <= STAMP_MAX_RANK:
                    stamps = sum(1 for need in self.stamp_need.values() if need <= disc)
            if before == 0 or stars(before + 1) != stars(before):
                income_dirty = True
            if income_dirty:
                slots = BASE_SLOTS + 3 * up["Park"]
                total = 0.0
                for oid, _ in self.order:
                    cnt = inv.get(oid, 0)
                    if cnt:
                        total += self.inc_tier[self.rank[oid] - 1] * (1 + STAR_BONUS * (stars(cnt) - 1))
                        slots -= 1
                        if slots == 0:
                            break
                income = total * (1 + 0.2 * up["Ticket"]) * (1 + self.reb["incomeBonus"] * r)
                if p["dbl"]:
                    income *= 2
                income_dirty = False
            if self.model == "fix" and not is_new:
                rev = auto_reveal(min(rk, 3))
            else:
                rev = auto_reveal(rk)
            dt = max(cd, RTT + rev)
            t += dt
            coins += income * dt

            # 환생 (가능하면 바로)
            if r < n_steps:
                step = self.steps[r]
                lm_ok = all(inv.get(x, 0) > 0 for x in step["landmarks"])
                if lm_ok and lm_met_at is None:
                    lm_met_at = t
                if lm_ok and coins >= step["coins"]:
                    events["rebirth"].append(t)
                    events["runs"].append(dict(
                        start=run_start, end=t, rolls=run_rolls, lm_met=lm_met_at - run_start,
                        luck_end=luck, income_end=income, coins_bound=(lm_met_at < t - 1e-9),
                    ))
                    r += 1
                    coins = 0.0
                    inv.clear()
                    for k in up:
                        up[k] = 0
                    run_rolls = 0
                    run_start = t
                    lm_met_at = None
                    income_dirty = True
                    if r == n_steps:
                        events["end_state"] = dict(t=t, disc=set(disc), stamps=stamps)
                        break
                    continue
            else:
                lm_ok = False

            # 업그레이드: 가장 싼 것부터, 살 수 있으면 삼. 환생 명소를 다 모았으면 환생 코인 밑으로는 안 씀
            reserve = self.steps[r]["coins"] if (r < n_steps and lm_ok) else 0
            while True:
                best = None
                for uid, base, growth, mx, _ in UPGRADES:
                    lv = up[uid]
                    if lv >= mx:
                        continue
                    price = math.floor(base * growth ** lv)
                    if best is None or price < best[1]:
                        best = (uid, price)
                if best is None or coins - best[1] < reserve or coins < best[1]:
                    break
                coins -= best[1]
                up[best[0]] += 1
                if best[0] in ("Park", "Ticket"):
                    income_dirty = True
        events["t_end"] = t
        events["rebirths"] = r
        events["disc"] = disc
        return events


def endgame(v: dict, player: str, model: str, globe: int = 20, stamps: int = 5) -> dict:
    """10번 환생 뒤 지구본 20레벨·도장 5개 상태에서 전설 명소마다 기대 발견 시간(일)."""
    p = PLAYERS[player]
    luck = (1 + 0.1 * globe) * (1 + REGION_LUCK * stamps) * luck_mult(v["rebirth"], len(v["rebirth"]["steps"]))
    if p["vip"]:
        luck *= 2
    sim = Sim(v, player, model, 0)
    c = sim.cdf(luck)
    # 평균 굴림 간격(발견한 뒤 = 새 명소 아님)
    mean_dt = 0.0
    prev = 0.0
    cd = ROLL_COOLDOWN * 0.5 * (0.7 if p["fast"] else 1)
    for (lid, _), acc in zip(sim.order, c):
        pr = acc - prev
        prev = acc
        rk = sim.rank[lid]
        rev = auto_reveal(min(rk, 3) if model == "fix" else rk)
        mean_dt += pr * max(cd, RTT + rev)
    per_day = 86400 / mean_dt
    out = {"luck": luck, "rolls_per_day": per_day, "items": {}}
    boost_avg = (1 + p["boost"]) * (1 + p["server"])  # 평균 부스트 배율(대략)
    for lid, n in sim.order:
        if sim.rank[lid] < 6:
            break
        out["items"][lid] = n / (luck * boost_avg) / per_day
    return out


def _run(args):
    v, player, model, seed = args
    ev = Sim(v, player, model, seed).run()
    ev.pop("disc", None)
    if "end_state" in ev:
        ev["end_state"].pop("disc", None)
    return ev


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def fmt_h(sec: float) -> str:
    h = sec / 3600
    if h < 1:
        return f"{h * 60:.0f}m"
    if h < 48:
        return f"{h:.1f}h"
    return f"{h / 24:.1f}d"


def report(v: dict, player: str, model: str, seeds: int, pool: Pool) -> dict:
    evs = pool.map(_run, [(v, player, model, s) for s in range(seeds)])
    n_steps = len(v["rebirth"]["steps"])
    print(f"\n== {v['name']} | {player} | roll model={model} | seeds={seeds}")
    print(" rb  cum-median   (p10..p90)    run-median  rolls/run   lm-met(run)  coins-bound  luck@end   income/s@end")
    summary = {"rebirth": []}
    for k in range(n_steps):
        cum = [e["rebirth"][k] for e in evs if len(e["rebirth"]) > k]
        runs = [e["runs"][k] for e in evs if len(e["runs"]) > k]
        if not cum:
            print(f" {k + 1:2d}  (none reached within cap)")
            summary["rebirth"].append(None)
            continue
        run_len = [x["end"] - x["start"] for x in runs]
        print(
            f" {k + 1:2d}  {fmt_h(statistics.median(cum)):>9}   ({fmt_h(pct(cum, .1)):>6}..{fmt_h(pct(cum, .9)):>6})"
            f"  {fmt_h(statistics.median(run_len)):>9}  {statistics.median([x['rolls'] for x in runs]):>9.0f}"
            f"   {fmt_h(statistics.median([x['lm_met'] for x in runs])):>9}   {sum(x['coins_bound'] for x in runs):>3}/{len(runs):<3}"
            f"   {statistics.median([x['luck_end'] for x in runs]):>8.0f}  {statistics.median([x['income_end'] for x in runs]):>10.0f}"
            + (f"  [{len(cum)}/{seeds} reached]" if len(cum) < seeds else "")
        )
        summary["rebirth"].append(dict(median_h=statistics.median(cum) / 3600, p10_h=pct(cum, .1) / 3600,
                                       p90_h=pct(cum, .9) / 3600))
    fr = {}
    for rk in range(1, 8):
        ts = [e["first_rank"][rk] for e in evs if rk in e["first_rank"]]
        if ts:
            fr[rk] = statistics.median(ts)
    print(" first discovery by tier (median): " + ", ".join(f"T{rk} {fmt_h(t)}" for rk, t in fr.items()))
    # 전설 개별 첫 발견
    legend = [lid for lid, n in sorted(v["landmarks"].items(), key=lambda kv: kv[1])
              if rank_of(n, [t["minOneIn"] for t in v["tiers"]]) == 7]
    parts = []
    for lid in legend:
        ts = [e["first"][lid] for e in evs if lid in e["first"]]
        parts.append(f"{lid} {len(ts)}/{seeds}" + (f" med {fmt_h(statistics.median(ts))}" if ts else ""))
    print(" legends found before 10th rebirth: " + "; ".join(parts))
    summary["first_rank_h"] = {rk: t / 3600 for rk, t in fr.items()}
    return summary


def print_table(v: dict):
    mins = [t["minOneIn"] for t in v["tiers"]]
    print(f"stretch a = {STRETCH_A:.4f}; tiers minOneIn = {mins}")
    by_rank: dict[int, list] = {}
    for lid, n in sorted(v["landmarks"].items(), key=lambda kv: kv[1]):
        by_rank.setdefault(rank_of(n, mins), []).append((lid, OLD_N[lid], n))
    for rk in range(4, 8):
        rows = by_rank[rk]
        print(f"T{rk} {TIER_NAMES[rk - 1]} ({len(rows)}): " + ", ".join(f"{i} {o:,}->{n:,}" for i, o, n in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", type=int, default=0)
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--models", default="code,fix")
    ap.add_argument("--players", default="free,payer")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    print_table(VARIANT_A)
    if not args.no_write:
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(VARIANT_A, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("wrote", OUT_JSON)
    if args.sim:
        with Pool() as pool:
            variants = ([BASELINE] if args.baseline else []) + [VARIANT_A]
            for v in variants:
                for model in args.models.split(","):
                    for player in args.players.split(","):
                        report(v, player, model, args.sim, pool)
                        eg = endgame(v, player, model)
                        print(f" endgame luck {eg['luck']:.0f}, {eg['rolls_per_day']:.0f} rolls/day; expected days: "
                              + ", ".join(f"{k} {d:.1f}" for k, d in eg["items"].items()))


if __name__ == "__main__":
    main()
