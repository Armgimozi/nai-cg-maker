#!/usr/bin/env python3
"""9번 라운드 밸런스 (2026-09-30): "자동 굴림 빠르게" — AUTO 속도 = 서버 굴림 간격(여행사·빠른 굴림).

8번 라운드의 AUTO 짧은 연출(이미 발견한 명소를 3등급 길이로)도 왕복 포함 약 1.35초라 굴림 간격(1.2초, 여행사 최대
0.6초, 빠른 굴림까지 0.42초)보다 길어서, 빠른 굴림(199 R$)·여행사가 AUTO 속도를 거의 못 바꿨음(sim_results.md 8e).
게임을 이렇게 바꿈: AUTO 중 이미 발견한 명소는 결과 카드만 퐁(Hud.luau quickReveal, Config.AUTO_QUICK_REVEAL) 하고
Hud.reveal 이 기다리지 않음 → 이미 발견한 명소의 AUTO 1회 = max(굴림 간격, 왕복 + 루프 대기 0.18초) = 굴림 간격.
그만큼 게임이 빨라져서 환생 코인(필요하면 별 보너스)과 속보·홀로그램 기준을 다시 맞춤. 명소 확률은 그대로(스토어 그림).

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/tune_quick.py --round speed    # 짧은 연출(8번) vs 빠른 결과: 무료 / 빠른 굴림 / 여행사 최대 / 둘 다
  python3 tools/balance/tune_quick.py --round coins    # 빠른 결과 + 환생 코인·별 보너스 후보(무료·유료)
  python3 tools/balance/tune_quick.py --round final    # 최종안(balance/variant_rec.json) + 다른 시드·greedy·부스트 많이
  옵션: --sims 400 --workers 4 --only tag1,tag2 --extra '{"tag": {"scale": 1.3}}'
결과 표(마크다운)는 표준 출력 → balance/sim_results.md 9번에 옮겨 적음. 모델·가정은 tools/balance/sim.py 그대로
(온라인 시간만, AUTO, 업그레이드 정책 ready, 왕복 0.12초 가정).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim as S  # noqa: E402
import tune_final as TF  # noqa: E402

DAY = S.DAY
GACHA = TF.GACHA
IMPLEMENTED_COINS = list(TF.APPROVED_COINS)  # 8번 라운드는 환생 코인을 안 바꿈


def implemented_variant() -> dict:
    """8번 라운드 최종안(빠른 결과 전, 커밋 7bcd362): 3등급 길이의 AUTO 짧은 연출, 세계수 1/100억, 속보 1억,
    홀로그램 3.75억, 가챠식 별 +30%, 환생 코인 30만 ~ 1,400억."""
    v = TF.approved_variant()
    v["landmarks"]["worldtree"] = 10_000_000_000
    v["announceOneIn"] = 100_000_000
    v["hologramOneIn"] = 375_000_000
    v["starThresholds"] = list(GACHA)
    v["starIncomeBonus"] = 0.3
    v["rules"] = {"autoDiscoverBelowLuck": True, "shortRevealKnown": True, "shortRevealRank": 3, "quickRevealKnown": False}
    return v


def variant(
    quick=True, coins=None, scale=None, bonus=None, news=None, holo=None, tier_income=None, agency_max=None, base="implemented"
) -> dict:
    """8번 최종안(base "final" 이면 지금 최종안 balance/variant_rec.json) 위에 바꿀 것만.
    quick False = 8번의 3등급 짧은 연출. coins: {단계: 코인} 또는 10개 목록, scale: 2~10단계 코인 × scale."""
    v = final_variant() if base == "final" else implemented_variant()
    if quick:
        v["rules"] = dict(v["rules"], shortRevealKnown=False, quickRevealKnown=True)
    else:
        v["rules"] = dict(v["rules"], shortRevealKnown=True, shortRevealRank=3, quickRevealKnown=False)
    steps = v["rebirth"]["steps"]
    if scale:
        for k in range(1, len(steps)):
            steps[k]["coins"] = float(S._round_sig(steps[k]["coins"] * scale, 2))
    if coins:
        items = enumerate(coins, 1) if isinstance(coins, list) else ((int(k), c) for k, c in coins.items())
        for k, c in items:
            steps[k - 1]["coins"] = c
    if bonus is not None:
        v["starIncomeBonus"] = bonus
    if news:
        v["announceOneIn"] = news
    if holo:
        v["hologramOneIn"] = holo
    if tier_income:
        v["tierIncome"] = list(tier_income)
    if agency_max is not None:  # 여행사를 못 사게(0) — "여행사 없음" 비교용
        v["upgrades"] = {"Agency": {"maxLevel": agency_max}}
    return v


def final_variant() -> dict:
    return json.loads(TF.REC.read_text(encoding="utf-8"))


# AUTO 굴림 수 비교: (태그, 변형 kwargs, 게임패스) — 모두 무료 플레이어(부스트 없음)에 게임패스만 바꿈
SPEED = {
    "short3 · 없음(여행사 못 삼)": (dict(quick=False, agency_max=0), []),
    "short3 · 빠른 굴림(여행사 못 삼)": (dict(quick=False, agency_max=0), ["FastRoll"]),
    "short3 · 여행사 최대": (dict(quick=False), []),
    "short3 · 여행사 최대 + 빠른 굴림": (dict(quick=False), ["FastRoll"]),
    "quick · 없음(여행사 못 삼)": (dict(agency_max=0), []),
    "quick · 빠른 굴림(여행사 못 삼)": (dict(agency_max=0), ["FastRoll"]),
    "quick · 여행사 최대": (dict(), []),
    "quick · 여행사 최대 + 빠른 굴림": (dict(), ["FastRoll"]),
}

ROUNDS = {
    # 1) 빠른 결과만 넣고 숫자는 그대로 -> 얼마나 빨라지나
    "coins": {
        "short3 (8번 최종안)": dict(quick=False),
        "quick, 숫자 그대로": dict(),
    },
}


def run_specs(specs: list[dict], workers: int) -> dict:
    with Pool(workers) as pool:
        outs = pool.map(TF.job, specs, chunksize=1)
    return {(o["tag"], o["kind"]): o for o in outs}


def speed_report(jobs: dict) -> str:
    L = ["| AUTO (이미 발견한 명소) | 게임패스 | 굴림 간격 (후반) | AUTO 굴림/시간 run 0 | run 5 | run 10 | run 10 ÷ 없음 |", "|---|---|---|---|---|---|---|"]
    base = {}
    for tag, (kw, passes) in SPEED.items():
        j = jobs[(tag, "free")]
        mode = tag.split(" · ")[0]
        rph = j["rolls_per_h"]
        if "없음" in tag:
            base[mode] = rph[10]
        cd = 1.2 * (1 if kw.get("agency_max") == 0 else 0.5) * (0.7 if passes else 1)
        L.append(
            f"| {'3등급 짧은 연출(8번)' if mode == 'short3' else '빠른 결과(9번)'} | {tag.split(' · ')[1]} | {cd:.2f} s |"
            f" {rph[0]:,.0f} | {rph[5]:,.0f} | {rph[10]:,.0f} | ×{rph[10] / base[mode]:.2f} |"
        )
    return "\n".join(L) + "\n"


def news_report(jobs: dict, tags: list[str]) -> str:
    """속보·홀로그램 기준 후보마다 판별 1인 시간당 횟수(무료 / 유료)와 무료 첫 자기 속보. 기준은 굴림을 안 바꿔서 같은 실행에서 셈."""
    L = ["| scenario | 1 in ≥ (명소) | run 4 | 6 | 8 | 9 | 10 | first own (free) |", "|---|---|---|---|---|---|---|---|"]
    names = {"100000000": "사하라 신기루 성·샹그릴라·세계수", "375000000": "샹그릴라·세계수", "10000000000": "세계수"}
    for tag in tags:
        f, p = jobs.get((tag, "free")), jobs.get((tag, "paid"))
        if not f or not p:
            continue
        for thr, label in names.items():
            a, b = f["rare_by_threshold"][thr], p["rare_by_threshold"][thr]
            first = TF.fd(f["first_news"][thr]) if thr in f["first_news"] else "—"
            cells = [f"{TF.rate(a[r])} / {TF.rate(b[r])}" for r in (4, 6, 8, 9, 10)]
            L.append(f"| {tag} | {int(thr):,} ({label}) | " + " | ".join(cells) + f" | {first} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", default="final", choices=["speed", *ROUNDS, "final"])
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--horizon-days", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--extra", default="", help="JSON {tag: variant kwargs} added to the round")
    ap.add_argument("--players", default="free,paid")
    ap.add_argument("--base", default="final", choices=["final", "implemented"], help="speed 라운드의 바탕 숫자")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    horizon = args.horizon_days * DAY
    t0 = time.time()
    if args.round == "speed":
        # 후반(run 10) 굴림 수는 환생 코인과 상관없음(행운·굴림 간격만) — 숫자는 지금 최종안(--base implemented 면 8번 최종안)
        specs = [
            dict(tag=tag, kind="free", sims=args.sims, seed=args.seed, horizon=horizon, variant=variant(base=args.base, **kw), passes=passes)
            for tag, (kw, passes) in SPEED.items()
        ]
        jobs = run_specs(specs, args.workers)
        print(f"<!-- tune_quick.py --round speed --sims {args.sims} --seed {args.seed}: {time.time() - t0:.0f} s -->\n")
        print(speed_report(jobs))
        return
    if args.round == "final":
        fin = final_variant()
        scen = {
            "final": dict(variant=fin),
            "final_seed2": dict(variant=fin, seed=args.seed + 1),
            "final_greedy": dict(variant=fin, policy="greedy"),
            "final_heavy": dict(variant=fin, boosts=3.0, server_luck=0.05),
        }
    else:
        scen = {tag: dict(variant=variant(**kw)) for tag, kw in ROUNDS[args.round].items()}
    if args.only:  # 라운드의 기본 후보 중 이것만(--extra 후보는 늘 포함)
        keep = set(args.only.split(","))
        scen = {k: v for k, v in scen.items() if k in keep}
    if args.extra:
        for tag, kw in json.loads(args.extra).items():
            scen[tag] = dict(variant=variant(**kw))
    specs = []
    for tag, kw in scen.items():
        for kind in [x.strip() for x in args.players.split(",") if x.strip()]:
            spec = dict(tag=tag, kind=kind, sims=args.sims, seed=args.seed, horizon=horizon)
            spec.update(copy.deepcopy(kw))
            specs.append(spec)
    jobs = run_specs(specs, args.workers)
    print(f"<!-- tune_quick.py --round {args.round} --sims {args.sims} --seed {args.seed}: {time.time() - t0:.0f} s -->\n")
    print(TF.report(jobs, list(scen)))
    print("News / hologram per player-hour of rolling by run (pooled, free / paid):\n")
    print(news_report(jobs, list(scen)))
    if args.json:
        Path(args.json).write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in jobs.items()}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
