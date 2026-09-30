#!/usr/bin/env python3
"""변형 B "과감한 안 (bold)" — 확률표·환생 단계 만들기 + 점검.

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/variant_b_design.py                  # balance/variant_b.json 다시 쓰기 + 등급별 표
  python3 tools/balance/variant_b_design.py --no-write --table        # 150개 전체 지금 → 변형 B 표(markdown)
  python3 tools/balance/variant_b_design.py --no-write --stages       # 단계별 굴림 모습·뉴스 빈도·굴림 속도
  python3 tools/balance/variant_b_design.py --no-write --sim 200      # tools/balance/sim.py 로 진행 속도(지금 클라)
  python3 tools/balance/variant_b_design.py --no-write --sim 200 --fix   # + 권장 수정(이미 발견한 명소는 짧은 연출)

게임 코드는 읽기만 합니다(src/shared/Landmarks.luau 에서 명소 Id·N·대륙). 기준은 "변형 전" 확률(세계수 40,000,000)이라
변형 B 를 게임에 넣은 뒤에는 다시 늘리지 않도록 멈춥니다. 진행 속도는 독립 시뮬레이터 tools/balance/sim.py 가 계산합니다
(PlayerState/RollLogic 규칙 그대로 + AUTO 굴림 간격 = 결과 연출 시간).

변형 B 규칙 요약
  * 환생 행운 x2^r (10번 = x1,024). 환생 수입 +50%/회(선형, 지금 그대로).
  * 확률표: 일반 명소(N < 10)는 그대로. 10 <= N < 10,000 (도시·국가·세계 명소) 은 N^2 / 10 ("자릿수 두 배"),
    N >= 10,000 (불가사의·잃어버린 유산·전설) 은 N x 1,000. 두 식은 10,000 -> 10,000,000 에서 만납니다.
    앞자리가 깔끔한 수로 반올림, 희귀도 순서·대륙·등급 소속은 150개 모두 그대로(스크립트가 검사).
  * 등급 경계 1 / 10 / 1,000 / 100,000 / 10,000,000 / 100,000,000 / 1,000,000,000 (이름 그대로).
  * 행운원 보강: 지구본 +10%/레벨 -> +25%/레벨(최대 x3 -> x6), 여권 도장 +25% -> +50%/대륙(최대 x2.25 -> x3.5).
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_JSON = os.path.join(ROOT, "balance", "variant_b.json")
SIM = os.path.join(ROOT, "tools", "balance", "sim.py")

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
REGION_KO = {"Asia": "아시아", "Europe": "유럽", "Africa": "아프리카", "Americas": "아메리카", "Oceania": "오세아니아"}
if max(OLD_N.values()) != 40_000_000:
    raise SystemExit(
        f"Landmarks.luau 의 가장 희귀한 N 이 {max(OLD_N.values()):,} — 이 스크립트는 변형 전 확률(세계수 40,000,000)을 "
        "기준으로 늘립니다. 변형 B 가 이미 들어갔다면 balance/variant_b.json 을 그대로 쓰세요."
    )


def rank_of(n: float, mins: list[float]) -> int:
    rank = 1
    for i, m in enumerate(mins):
        if n >= m:
            rank = i + 1
    return rank


OLD_RANK = {i: rank_of(n, OLD_TIERS) for i, n in OLD_N.items()}

# ----------------------------------------------------------------------------- 변형 B: 확률 늘이기

KINK_LOW = 10  # 이보다 흔하면 그대로(일반 명소 1/2 ~ 1/9)
KINK_HIGH = 10_000  # 여기까지 N^2/10, 위로는 N x 1,000 (10,000 -> 10,000,000 에서 이어짐)


def stretch(n: float) -> float:
    if n < KINK_LOW:
        return float(n)
    if n < KINK_HIGH:
        return n * n / KINK_LOW
    return n * (KINK_HIGH / KINK_LOW)


# "친절한" 숫자: 앞자리가 깔끔한 수(1 in 12 / 250 / 4,500 / 1,600,000 / 40,000,000,000).
# 굵은 격자에서 가장 가까운 수, 앞 명소와 겹치면 고운 격자(간격 5% 안팎), 그래도 겹치면 바로 위 수.
MANTISSAS = [1, 1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 1.7, 1.75, 1.8, 1.9,
             2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5]
FINE = sorted(set([round(1 + 0.05 * i, 2) for i in range(20)] + [round(2 + 0.1 * i, 1) for i in range(30)]
                  + [round(5 + 0.25 * i, 2) for i in range(20)]))


def _grid(mants: list[float]) -> list[int]:
    out = set()
    for k in range(1, 12):
        for m in mants:
            v = m * 10 ** k
            if abs(v - round(v)) < 1e-9:
                out.add(int(round(v)))
    return sorted(out)


GRID = _grid(MANTISSAS)
FINE_GRID = sorted(set(_grid(FINE)) | set(GRID) | set(range(10, 100)))


def nearest(grid: list[int], v: float) -> int:
    i = bisect.bisect_left(grid, v)
    cands = [grid[j] for j in (i - 1, i) if 0 <= j < len(grid)]
    return min(cands, key=lambda g: (abs(math.log(g / v)), g))


def build_odds() -> dict[str, int]:
    """모든 명소의 새 N. 순서(희귀도 순위)는 그대로, 겹치면 고운 격자 → 그래도 겹치면 바로 위 수."""
    ordered = sorted(CURRENT, key=lambda lm: (lm["n"], CURRENT.index(lm)))
    result: dict[str, int] = {}
    prev = 0
    for lm in ordered:
        if lm["n"] < KINK_LOW:
            v = lm["n"]
        else:
            raw = stretch(lm["n"])
            v = nearest(GRID, raw)
            if v <= prev:
                v = nearest(FINE_GRID, raw)
            if v <= prev:
                v = FINE_GRID[bisect.bisect_right(FINE_GRID, prev)]
        assert v > prev, lm
        result[lm["id"]] = v
        prev = v
    return result


NEW_N = build_odds()
NEW_TIERS = [1, 10, 1_000, 100_000, 10_000_000, 100_000_000, 1_000_000_000]
for _id, _n in NEW_N.items():  # 등급 소속 그대로(여권 도장 대상·테스트의 등급 이름·색이 그대로 맞음)
    assert rank_of(_n, NEW_TIERS) == OLD_RANK[_id], (_id, _n)

# ----------------------------------------------------------------------------- 나머지 숫자

TIER_INCOME = [1, 3, 10, 40, 150, 600, 2500]
UPGRADES = {  # Config.Upgrades 에서 바뀌는 값만 (가격 = floor(BasePrice * Growth ^ 레벨))
    "Globe": {"basePrice": 100, "growth": 1.5, "maxLevel": 20, "perLevel": 0.3},
}
REGION_LUCK_BONUS = 0.5
STEPS = [
    {"coins": 250_000, "landmarks": ["eiffel", "liberty"]},
    {"coins": 2_000_000, "landmarks": ["colosseum", "niagara"]},
    {"coins": 20_000_000, "landmarks": ["tajmahal", "angkor"]},
    {"coins": 200_000_000, "landmarks": ["sphinx", "pyramid", "greatwall"]},
    {"coins": 1_000_000_000, "landmarks": ["chichen", "machupicchu", "grandcanyon"]},
    {"coins": 5_000_000_000, "landmarks": ["petra", "moai", "stonehenge"]},
    {"coins": 15_000_000_000, "landmarks": ["alexandria", "babylon"]},
    {"coins": 50_000_000_000, "landmarks": ["rhodes", "nanmadol", "babel"]},
    {"coins": 150_000_000_000, "landmarks": ["atlantis", "zealandia"]},
    {"coins": 400_000_000_000, "landmarks": ["yonggung"]},
]
ANNOUNCE_ONE_IN = 100_000_000
HOLOGRAM_ONE_IN = 1_000_000_000
DISCOVERY_BONUS_MULT = 5

NOTES = (
    "변형 B(과감한 안). 환생 행운 x2^r (10번 = x1,024), 환생 수입은 지금처럼 +50%/회(선형). "
    "확률표: 일반 명소(N<10)는 그대로, 도시·국가·세계 명소(10<=N<10,000)는 N^2/10('자릿수 두 배': 1/100 -> 1/1,000, "
    "1/1,000 -> 1/100,000), 불가사의 이상(N>=10,000)은 N x 1,000(두 식은 1/10,000 -> 1/10,000,000 에서 만남). "
    "앞자리가 깔끔한 수로 반올림, 희귀도 순서·대륙·등급 소속은 150개 모두 그대로. 가장 희귀: 세계수 1 in 40,000,000,000(400억). "
    "등급 경계 1/10/1,000/100,000/10,000,000/100,000,000/1,000,000,000(이름 그대로). 요청 안의 위쪽 경계(10억/1,000억, 가장 희귀 1조)는 "
    "환생 x2 로 늘어나는 행운(최대 무료 약 2.5만, VIP 약 5만)과 AUTO 굴림 수(하루 2만~6만)로는 10번 환생한 VIP 도 첫 전설 약 5주, "
    "1조짜리 약 3년이라 불가사의 위로는 x1,000 으로 줄였음. 행운원 보강(초반이 덜 느려지게): 지구본 +10%/레벨 400*1.7^L -> +30%/레벨 100*1.5^L(20레벨, 최대 x3 -> x7), "
    "여권 도장 +25% -> +50%/대륙(최대 x2.25 -> x3.5). 등급 수입 1/3/10/40/150/600/2500. 발견 보너스 배율 5 그대로. "
    "환생 코인 250K/2M/20M/200M/1B/5B/15B/50B/150B/400B, 요구 명소는 그 판 길이의 31~74% 지점에서 모이게 고름(1단계 첫 명소는 여전히 eiffel). "
    "sim.py 400명(무료, 지금 클라): 1번째 23분, 3번째 2.8시간, 5번째 22시간, 10번째 24.8일, 첫 전설 6.1일(7번째 판), 10번 환생 뒤 세계수 기대 81일(VIP 44일). "
    "유료(패스 3개+부스트 하루 1번): 11분 / 85분 / 11시간 / 13.3일. 뉴스 >= 100,000,000(잃어버린 유산 이상), 홀로그램 >= 1,000,000,000(= 전설). "
    "초반 발견 수는 줄어듦(5/15/60분 40/52/72, 지금 64/88/114): 국가 명소가 1/1,000부터라 피할 수 없음(처음 20개까지는 지금과 같은 속도). "
    "같이 필요한 코드 수정: (1) PlayerState.luck 환생 배율 = 2^환생 수. (2) 영구 행운(부스트 제외) >= N 인 미발견 명소 자동 발견(이 JSON 의 rules). "
    "(3) Config: 지구본 Description '+30%', REGION_LUCK_BONUS 0.5, Landmarks.Tiers MinOneIn, 테스트 숫자(지구본 가격·행운 1.1). "
    "권장: (4) AUTO 에서 이미 발견한 명소는 짧은 연출 — 후반 굴림이 1/3 로 느려지는 것을 막음(세계수 기대 81일 -> 25일, VIP 44일 -> 12일, 10번째 환생 24.8일 -> 20.6일). "
    "자세한 근거: balance/variant_b.md, 재현: tools/balance/variant_b_design.py, tools/balance/sim.py --variant balance/variant_b.json"
)


def variant() -> dict:
    return {
        "name": "B 과감한 안 (bold): 환생 행운 x2^r, 자릿수 두 배(N^2/10), 가장 희귀 1/400억",
        "landmarks": dict(NEW_N),
        "tiers": [{"rank": i + 1, "name": TIER_NAMES[i], "minOneIn": m} for i, m in enumerate(NEW_TIERS)],
        "tierIncome": list(TIER_INCOME),
        "rebirth": {"luck": "x2", "luckBase": 2, "incomeBonus": 0.5, "steps": STEPS},
        "announceOneIn": ANNOUNCE_ONE_IN,
        "hologramOneIn": HOLOGRAM_ONE_IN,
        "discoveryBonusMult": DISCOVERY_BONUS_MULT,
        "upgrades": UPGRADES,
        "regionLuckBonus": REGION_LUCK_BONUS,
        "rules": {"autoDiscoverBelowLuck": True},
        "notes": NOTES,
    }


# ----------------------------------------------------------------------------- 점검


def check(v: dict):
    lms = v["landmarks"]
    assert len(lms) == 150 and set(lms) == set(OLD_N)
    old_order = sorted(OLD_N, key=lambda i: (OLD_N[i], [c["id"] for c in CURRENT].index(i)))
    new_order = sorted(lms, key=lambda i: (lms[i], old_order.index(i)))
    assert old_order == new_order, "희귀도 순서가 바뀜"
    assert len(set(lms.values())) == 150, "겹치는 N"
    mins = [t["minOneIn"] for t in v["tiers"]]
    for i, n in lms.items():
        assert rank_of(n, mins) == OLD_RANK[i], i
    prev = 0
    for k, st in enumerate(v["rebirth"]["steps"]):
        assert st["coins"] > prev, k
        prev = st["coins"]
        for x in st["landmarks"]:
            assert x in lms, x
    assert v["rebirth"]["steps"][0]["landmarks"][0] == "eiffel"
    assert max(lms.values()) < 2 ** 53


def probs(order: list[tuple[str, int]], luck: float) -> list[float]:
    out, rem = [], 1.0
    for idx, (_, n) in enumerate(order):
        if idx == len(order) - 1:
            out.append(rem)
        else:
            q = min(1.0, luck / n)
            out.append(rem * q)
            rem *= 1 - q
    return out


# AUTO(Fast) 한 번의 시간(초, 쿨타임 제외) — tools/balance/sim.py 의 auto_overhead 값(지금 Hud.luau)
AUTO_S = [1.32, 1.42, 1.35, 4.76, 6.04, 6.47, 6.69]


def stage_rows(v: dict, stages: list[tuple[str, float]]):
    mins = [t["minOneIn"] for t in v["tiers"]]
    order = sorted(v["landmarks"].items(), key=lambda kv: -kv[1])
    rows = []
    for name, luck in stages:
        p = probs(order, luck)
        pt = [0.0] * 7
        ann = holo = 0.0
        dt_code = dt_fix = 0.0
        for (lid, n), pr in zip(order, p):
            rk = rank_of(n, mins)
            pt[rk - 1] += pr
            ann += pr if n >= v["announceOneIn"] else 0
            holo += pr if n >= v["hologramOneIn"] else 0
            dt_code += pr * AUTO_S[rk - 1]
            dt_fix += pr * AUTO_S[min(rk, 3) - 1]
        rows.append(dict(stage=name, luck=luck, tiers=pt, ann=ann, holo=holo,
                         rph_code=3600 / dt_code, rph_fix=3600 / dt_fix))
    return rows


# 무료 플레이어가 판 r 후반에 보통 갖는 여권 도장 수(시뮬 중앙값: 불가사의까지 다 모아야 도장이라 6~7판에 몰려서 받음)
TYPICAL_STAMPS = [0, 0, 0, 0, 0, 0, 4, 5, 5, 5, 5]


def stage_luck(v: dict) -> list[tuple[str, float]]:
    """판 r 후반의 대표 행운(무료): 2^r × 지구본 최대 × 그때쯤 도장. R0 은 지구본 10레벨쯤."""
    up = v.get("upgrades", {}).get("Globe", {})
    per = up.get("perLevel", 0.1)
    globe_max = 1 + per * up.get("maxLevel", 20)
    bonus = v.get("regionLuckBonus", 0.25)
    out = [("R0", 1 + per * 10)]
    for r in range(1, 11):
        out.append((f"R{r}", 2 ** r * globe_max * (1 + bonus * TYPICAL_STAMPS[r])))
    top = 2 ** 10 * globe_max * (1 + bonus * 5)
    out.append(("R10 + VIP", top * 2))
    out.append(("R10 + VIP + 부스트 2개", top * 8))
    return out


def fmt_n(x: float) -> str:
    return f"{x:,.0f}"


def print_tables(v: dict, full: bool):
    mins = [t["minOneIn"] for t in v["tiers"]]
    by_rank: dict[int, list] = {}
    for lid, n in sorted(v["landmarks"].items(), key=lambda kv: kv[1]):
        by_rank.setdefault(rank_of(n, mins), []).append((lid, OLD_N[lid], n))
    step_of = {}
    for k, st in enumerate(v["rebirth"]["steps"]):
        for x in st["landmarks"]:
            step_of[x] = k + 1
    if not full:
        for rk in range(1, 8):
            rows = by_rank[rk]
            print(f"T{rk} {TIER_NAMES[rk - 1]} ({len(rows)}): " + ", ".join(f"{i} {o:,}->{n:,}" for i, o, n in rows))
        return
    for rk in range(1, 8):
        rows = by_rank[rk]
        print(f"\n#### {rk}등급 {TIER_NAMES[rk - 1]} ({len(rows)}개)\n")
        print("| 명소 | Id | 대륙 | 지금 | 변형 B | 배 | 환생 |")
        print("|---|---|---|---:|---:|---:|---|")
        for lid, o, n in rows:
            ratio = n / o
            rs = f"x{ratio:,.0f}" if ratio >= 10 else f"x{ratio:.3g}"
            print(f"| {NAME[lid]} | `{lid}` | {REGION_KO[REGION[lid]]} | {o:,} | **{n:,}** | {rs} | "
                  + (f"{step_of[lid]}단계" if lid in step_of else "") + " |")


def print_stages(v: dict):
    rows = stage_rows(v, stage_luck(v))
    print("| 단계 | 행운 | 1 일반 | 2 도시 | 3 국가 | 4 세계 | 5 불가사의 | 6 유산 | 7 전설 | 굴림/시간 지금 클라 \\| 연출 개선 | 뉴스/시간 | 홀로그램/시간 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|")

    def pc(x):
        if x < 5e-6:
            return "—"
        if x >= 0.1:
            return f"{x * 100:.0f}%"
        if x >= 0.01:
            return f"{x * 100:.1f}%"
        return f"{x * 100:.2g}%"

    for r in rows:
        print(f"| {r['stage']} | {r['luck']:,.0f} | " + " | ".join(pc(x) for x in r["tiers"])
              + f" | {r['rph_code']:,.0f} \\| {r['rph_fix']:,.0f} | {r['ann'] * r['rph_code']:.2g} \\| {r['ann'] * r['rph_fix']:.2g}"
              + f" | {r['holo'] * r['rph_code']:.2g} \\| {r['holo'] * r['rph_fix']:.2g} |")


def run_sim(v: dict, sims: int, fix: bool, extra: list[str]) -> dict:
    vv = json.loads(json.dumps(v))
    if fix:
        vv.setdefault("rules", {})["shortRevealKnown"] = True
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "variant_b.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(vv, f, ensure_ascii=False)
        out = os.path.join(tmp, "sim_b.md")
        cmd = [sys.executable, SIM, "--variant", path, "--no-sensitivity", "--sims", str(sims), "--out", out, *extra]
        subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
        md = open(out, encoding="utf-8").read()
        js = json.load(open(out[:-3] + ".json", encoding="utf-8"))
    print(md[md.index("## Pacing vs targets"):md.index("## Roll rate")])
    i = md.index("## Rebirth timeline")
    j = md.index("## Server announcements") if "## Server announcements" in md else len(md)
    print(md[i:j])
    return js


def early_rhythm(v: dict, sims: int = 200, hours: float = 3.0):
    """초반 흐름: k 번째 새 명소를 발견한 시각(중앙값)과 시각별 발견 수 — 지금 게임 vs 변형 B (무료, AUTO)."""
    sys.path.insert(0, os.path.dirname(SIM))
    import numpy as np
    import sim as S

    base = S.load_current("auto")
    rows = []
    for label, cfg in (("지금", base), ("변형 B", S.apply_variant(base, v))):
        game = S.Game(cfg)
        prof = S.make_profile(game, "free", 0.0, 0.0, 0.0)
        res = S.simulate(game, prof, sims, 7, hours * 3600, 0.02, "ready", "auto")
        dt = np.sort(np.where(np.isnan(res["disc_t"]), np.inf, res["disc_t"]), axis=1)
        kth = {k: float(np.median(dt[:, k - 1])) for k in (10, 20, 30, 40, 50, 60, 70, 80)}
        cnt = {m: float(np.median((dt <= m * 60).sum(1))) for m in (1, 5, 15, 30, 60, 120, 180)}
        rows.append((label, kth, cnt))

    def t(s):
        if not math.isfinite(s):
            return f"> {hours:g}시간"
        return f"{s:.0f}초" if s < 90 else (f"{s / 60:.0f}분" if s < 5400 else f"{s / 3600:.1f}시간")

    print("| | " + " | ".join(f"{k}번째" for k in rows[0][1]) + " |")
    print("|---|" + "---|" * len(rows[0][1]))
    for label, kth, _ in rows:
        print(f"| {label} | " + " | ".join(t(x) for x in kth.values()) + " |")
    print()
    print("| 발견한 명소 수 | " + " | ".join(f"{m}분" for m in rows[0][2]) + " |")
    print("|---|" + "---|" * len(rows[0][2]))
    for label, _, cnt in rows:
        print(f"| {label} | " + " | ".join(f"{x:.0f}" for x in cnt.values()) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--early", action="store_true", help="초반 발견 흐름: 지금 vs 변형 B")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--table", action="store_true", help="150개 전체 표(markdown)")
    ap.add_argument("--stages", action="store_true", help="단계별 굴림 모습·뉴스 빈도")
    ap.add_argument("--sim", type=int, default=0, help="sim.py 몬테카를로 인원")
    ap.add_argument("--fix", action="store_true", help="이미 발견한 명소는 AUTO 에서 짧은 연출(권장 수정)")
    ap.add_argument("--sim-args", default="", help="sim.py 에 넘길 추가 인자")
    args = ap.parse_args()
    v = variant()
    check(v)
    print_tables(v, args.table)
    if not args.no_write:
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("wrote", OUT_JSON)
    if args.stages:
        print_stages(v)
    if args.early:
        early_rhythm(v)
    if args.sim:
        run_sim(v, args.sim, args.fix, args.sim_args.split())


if __name__ == "__main__":
    main()
