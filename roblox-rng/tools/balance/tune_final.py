#!/usr/bin/env python3
"""구현 라운드 밸런스 조정 (2026-09-30): 승인된 추천안(balance/variant_rec.json) + 승인된 선택 두 가지.

  1. "자동 굴림 빠르게": AUTO 에서 이미 발견한 명소는 짧은 연출(rules.short_reveal_known, 3등급처럼).
     -> 후반 AUTO 가 굴림 간격(여행사·빠른 굴림)만큼 빨라짐. 세계수 확률 · 속보/홀로그램 기준을 다시 고름.
  2. 가챠식 별: 처음 발견 = 별 0, 중복마다 +1 (STAR_THRESHOLDS = {2, 3, 4, 5, 6}), 수입 = 기본 × (1 + 보너스 × 별).
     -> 흔한 명소는 몇 분 만에 5성, 희귀 명소는 거의 0성. STAR_INCOME_BONUS 와 (필요하면) 환생 코인을 다시 맞춤.

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/tune_final.py --round reveal      # 1: 짧은 연출 + 세계수/속보/홀로그램 후보
  python3 tools/balance/tune_final.py --round stars       # 2: 별 보너스 후보 (+ 환생 코인 후보)
  python3 tools/balance/tune_final.py --round final       # 최종안(balance/variant_rec.json) 400명 + 흔들어 보기
  python3 tools/balance/tune_final.py --round flash       # (참고) 이미 발견한 명소를 굴림 간격 안의 번쩍 연출로 보이면
  옵션: --sims 400 --workers 4 --only tag1,tag2
결과 표(마크다운)는 표준 출력으로 나오고, balance/sim_results.md 의 "8. Implementation round" 에 옮겨 적음.
최종 선택: 세계수 1/100억, 속보 >= 1억, 홀로그램 >= 3.75억, 별 +30%/개, 환생 코인 그대로(tools/balance/variant_rec_design.py).
모델·가정은 tools/balance/sim.py 그대로(온라인 시간만, AUTO, 업그레이드 정책 ready).
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim as S  # noqa: E402

ROOT = S.ROOT
MINUTE, HOUR, DAY = S.MINUTE, S.HOUR, S.DAY
REC = ROOT / "balance" / "variant_rec.json"

# 승인 전 추천안(이 라운드의 출발점). variant_rec.json 을 최종안으로 고쳐 쓴 뒤에도 같은 출발점을 재현하려고 고정
APPROVED = {
    "worldtree": 5_000_000_000,
    "announceOneIn": 25_000_000,
    "hologramOneIn": 100_000_000,
    "rules": {"autoDiscoverBelowLuck": True, "shortRevealKnown": False},
    "starThresholds": [1, 3, 10, 30, 100],
    "starIncomeBonus": 0.5,
}
FIX = {"rules": {"shortRevealKnown": True, "shortRevealRank": 3}}
GACHA = [2, 3, 4, 5, 6]


def merge(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            out[k] = merge(base.get(k), v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(patch)


def approved_variant() -> dict:
    v = json.loads(REC.read_text(encoding="utf-8"))
    v["landmarks"] = dict(v["landmarks"])
    v["landmarks"]["worldtree"] = APPROVED["worldtree"]
    v["announceOneIn"] = APPROVED["announceOneIn"]
    v["hologramOneIn"] = APPROVED["hologramOneIn"]
    v["rules"] = dict(APPROVED["rules"])
    v["starThresholds"] = list(APPROVED["starThresholds"])
    v["starIncomeBonus"] = APPROVED["starIncomeBonus"]
    # 승인 전 환생 표(최종안이 코인을 바꿨어도 출발점은 그대로)
    v["rebirth"] = dict(v["rebirth"])
    v["rebirth"]["steps"] = [dict(st) for st in v["rebirth"]["steps"]]
    for st, coins in zip(v["rebirth"]["steps"], APPROVED_COINS):
        st["coins"] = coins
    return v


APPROVED_COINS = [300e3, 1.5e6, 25e6, 250e6, 1.5e9, 6e9, 13e9, 28e9, 65e9, 140e9]


def scenario(fix: bool = True, worldtree=None, stars=None, bonus=None, coins=None, news=None, holo=None, flash=None) -> dict:
    """승인 추천안 위에 바꿀 것만 덧붙인 변형 JSON. flash: 이미 발견한 명소의 AUTO 1회 시간(초, 왕복 포함)."""
    v = approved_variant()
    if fix:
        v = merge(v, FIX)
    if flash:
        v = merge(v, {"rules": {"shortRevealKnown": True, "shortRevealSeconds": flash}})
    if worldtree:
        v["landmarks"]["worldtree"] = worldtree
    if stars:
        v["starThresholds"] = list(stars)
    if bonus is not None:
        v["starIncomeBonus"] = bonus
    if coins:
        for k, c in coins.items():  # 단계(1부터) -> 코인
            v["rebirth"]["steps"][k - 1]["coins"] = c
    if news:
        v["announceOneIn"] = news
    if holo:
        v["hologramOneIn"] = holo
    return v


def final_variant() -> dict:
    return json.loads(REC.read_text(encoding="utf-8"))


ROUNDS = {
    # 1) 짧은 연출: 지금 별 규칙 그대로, 세계수 후보. 속보/홀로그램 기준은 게임을 안 바꿔서 같은 실행에서 뒤에 셈
    "reveal": {
        "approved": dict(fix=False),
        "fix_wt5B": dict(fix=True),
        "fix_wt10B": dict(fix=True, worldtree=10_000_000_000),
        "fix_wt20B": dict(fix=True, worldtree=20_000_000_000),
    },
    # 2) 가챠식 별(짧은 연출·세계수 1/100억 포함): 보너스 후보
    "stars": {
        "fix_wt10B": dict(fix=True, worldtree=10_000_000_000),
        "gacha_b50": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.5),
        "gacha_b30": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.3),
        "gacha_b25": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.25),
        "gacha_b20": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.2),
    },
    # 3) 3등급 짧은 연출도 1.3~1.4초라 굴림 간격(1.2초 -> 여행사 최대 0.6, 빠른 굴림까지 0.42)보다 길어서 여행사·빠른 굴림이
    #    AUTO 속도를 못 바꿈. 이미 발견한 명소를 굴림 간격 안에 끝나는 번쩍 연출(왕복 포함 0.35초)로 보여 주면 어떻게 되나
    "flash": {
        "gacha_b30": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.3),
        "flash_b30": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.3, flash=0.35),
        "flash_b30_wt20B": dict(worldtree=20_000_000_000, stars=GACHA, bonus=0.3, flash=0.35),
        "flash_b20": dict(worldtree=10_000_000_000, stars=GACHA, bonus=0.2, flash=0.35),
    },
}


def load(spec: dict) -> S.Game:
    cfg = S.load_current("auto")
    v = final_variant() if spec.get("final") else scenario(**spec["scenario"])
    return S.Game(S.apply_variant(cfg, v))


def job(spec: dict) -> dict:
    game = load(spec)
    kind = spec["kind"]
    boosts = spec.get("boosts", 1.0) if kind == "paid" else 0.0
    prof = S.make_profile(game, kind, boosts, spec.get("server_luck", 0.0) if kind == "paid" else 0.0, 0.0)
    t0 = time.time()
    res = S.simulate(game, prof, spec["sims"], spec["seed"], spec["horizon"], 0.02, spec.get("policy", "ready"), "auto")
    sm = S.summarize(game, res)
    R = game.max_reb
    secs = res["run_seconds"]
    out = dict(tag=spec["tag"], kind=kind, summary=sm, seconds=time.time() - t0)
    out["rolls_per_h"] = [float(res["run_rolls"][:, r].sum() / secs[:, r].sum() * 3600) if secs[:, r].sum() > 0 else None for r in range(R + 1)]
    # 가장 희귀한 12개의 판별 뽑힌 수 -> 기준 N 마다 속보/홀로그램 시간당 횟수(모두 합 / 모두 시간)
    n_rare = res["rare_draws"].shape[2]
    rare_n = game.N[:n_rare]
    out["rare_by_threshold"] = {}
    for thr in (8e6, 25e6, 45e6, 100e6, 375e6, 1e9):
        mask = rare_n >= thr
        out["rare_by_threshold"][str(int(thr))] = [
            float(res["rare_draws"][:, r, mask].sum() / secs[:, r].sum() * 3600) if secs[:, r].sum() > 0 else None for r in range(R + 1)
        ]
    # 첫 자기 속보(기준마다): 그 기준 이상 명소를 처음 발견한 시각
    out["first_news"] = {}
    for thr in (25e6, 45e6, 100e6):
        cols = np.flatnonzero(game.N >= thr)
        dt = res["disc_t"][:, cols]
        has = ~np.isnan(dt)
        first = np.where(has.any(1), np.nanmin(np.where(has, dt, np.inf), axis=1), np.nan)
        out["first_news"][str(int(thr))] = S.cq(first, 0.5)
    out["stamps_all"] = float((res["final_stamps"] == int((game.region_required > 0).sum())).mean())
    out["star_mult"] = [float(np.nanmedian(res["reb_star_mult"][:, k])) if np.isfinite(res["reb_star_mult"][:, k]).any() else None for k in range(R + 1)]
    early = {}
    for m in (5, 10, 15, 20, 30, 60):
        found = res["disc_t"] <= m * MINUTE
        early[m] = float(np.median(found.sum(1)))
    out["early"] = early
    # 필요한 명소가 환생을 늦춘 비율(코인보다 명소가 나중)
    bound = []
    for k in range(1, R + 1):
        start, end, ready = res["reb_t"][:, k - 1], res["reb_t"][:, k], res["ready_t"][:, k - 1]
        ok = np.isfinite(end) & np.isfinite(start)
        run = end - start
        b = ok & np.isfinite(ready) & (end - ready <= 0.02 * np.maximum(run, 1))
        bound.append(float(b[ok].mean()) if ok.any() else None)
    out["landmark_bound"] = bound
    out["rarest"] = dict(id=game.ids[0], n=float(game.N[0]))
    return out


def fd(x) -> str:
    return S.fmt_dur(x) if x is not None and np.isfinite(x) else "—"


def rate(x) -> str:
    if x is None:
        return "—"
    if x == 0:
        return "0"
    return f"{x:.2g}" if x < 10 else f"{x:,.0f}"


def cell(r: dict) -> str:
    if r["median_s"] is None or not np.isfinite(r["median_s"]):
        return "—"
    return f"**{fd(r['median_s'])}** ({fd(r['p10_s'])}–{fd(r['p90_s'])})"


def verdict(v, lo, hi) -> str:
    if v is None or not np.isfinite(v):
        return "✗"
    return "✓" if lo <= v <= hi else ("fast" if v < lo else "slow")


def report(jobs: dict, tags: list[str]) -> str:
    L = []
    L.append("| scenario | player | #1 | #2 | #3 | #4 | #5 | #6 | #7 | #8 | #9 | #10 | targets 1/3/5/10 |")
    L.append("|---|---|" + "---|" * 11)
    tmap = {k: (lo, hi) for _, k, lo, hi in S.TARGETS}
    for tag in tags:
        for kind in ("free", "paid"):
            j = jobs.get((tag, kind))
            if not j:
                continue
            r = j["summary"]["rebirths"]
            cells = [cell(r[k]) if k < 3 or k in (4, 9) else fd(r[k]["median_s"]) for k in range(10)]
            ver = "/".join(verdict(r[k - 1]["median_s"], *tmap[k]) for k in (1, 3, 5, 10)) if kind == "free" else ""
            L.append(f"| {tag} | {kind} | " + " | ".join(cells) + f" | {ver} |")
    L.append("")
    L.append("| scenario | player | found 5/15/60 min | first legendary (run) | rarest wait at max | AUTO rolls/h run 0 / 5 / 10 | stamps 5/5 | park star mult at rebirth 1 / 3 / 5 / 10 | landmark-bound runs (max) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for tag in tags:
        for kind in ("free", "paid"):
            j = jobs.get((tag, kind))
            if not j:
                continue
            sm = j["summary"]
            t7 = {x["rank"]: x for x in sm["tiers"]}.get(7)
            leg = f"{fd(t7['median_s'])} ({t7['at_rebirth_median']:.0f})" if t7 and t7["at_rebirth_median"] is not None else "—"
            e = j["early"]
            rph = j["rolls_per_h"]
            sm_ = j["star_mult"]
            lb = [x for x in j["landmark_bound"] if x is not None]
            L.append(
                f"| {tag} | {kind} | {e[5]:.0f} / {e[15]:.0f} / {e[60]:.0f} | {leg} | {fd(sm['endgame_max']['rarest_s'])} (1 in {j['rarest']['n']:,.0f}) |"
                f" {rph[0]:,.0f} / {rph[5]:,.0f} / {rph[10]:,.0f} | {j['stamps_all']:.0%} |"
                f" ×{sm_[1]:.2f} / ×{sm_[3]:.2f} / ×{sm_[5]:.2f} / ×{sm_[10]:.2f} | {max(lb):.0%} |"
            )
    L.append("")
    L.append("News/hologram per player-hour of rolling by run (pooled), for each 1-in threshold (free / paid):\n")
    L.append("| scenario | 1 in ≥ | run 0 | 2 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | first own (free) |")
    L.append("|---|---|" + "---|" * 10)
    for tag in tags:
        f, p = jobs.get((tag, "free")), jobs.get((tag, "paid"))
        if not f or not p:
            continue
        for thr in ("25000000", "45000000", "100000000", "375000000"):
            a, b = f["rare_by_threshold"][thr], p["rare_by_threshold"][thr]
            first = fd(f["first_news"].get(thr)) if thr in f["first_news"] else ""
            cells = [f"{rate(a[r])} / {rate(b[r])}" for r in (0, 2, 4, 5, 6, 7, 8, 9, 10)]
            L.append(f"| {tag} | {int(thr):,} | " + " | ".join(cells) + f" | {first} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", default="final", choices=[*ROUNDS, "final"])
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--horizon-days", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--extra", default="", help='JSON {tag: scenario kwargs} added to the round')
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    if args.round == "final":
        # 최종안 + 흔들어 보기: 다른 시드, 업그레이드를 먼저 다 사는 정책, 부스트를 많이 사는 유료
        scen = {
            "final": None,
            "final_seed2": {"final": True, "seed": args.seed + 1},
            "final_greedy": {"final": True, "policy": "greedy"},
            "final_heavy": {"final": True, "boosts": 3.0, "server_luck": 0.05},
        }
    else:
        scen = dict(ROUNDS[args.round])
    if args.extra:
        for tag, kw in json.loads(args.extra).items():
            scen[tag] = {k: ({int(a): b for a, b in v.items()} if k == "coins" else v) for k, v in kw.items()}
    if args.only:
        keep = set(args.only.split(","))
        scen = {k: v for k, v in scen.items() if k in keep}
    specs = []
    for tag, kw in scen.items():
        for kind in ("free", "paid"):
            spec = dict(tag=tag, kind=kind, sims=args.sims, seed=args.seed, horizon=args.horizon_days * DAY)
            if kw is None:
                spec["final"] = True
            elif kw.get("final"):
                spec.update(kw)
            else:
                spec["scenario"] = kw
            specs.append(spec)
    t0 = time.time()
    with Pool(args.workers) as pool:
        outs = pool.map(job, specs, chunksize=1)
    jobs = {(o["tag"], o["kind"]): o for o in outs}
    print(f"<!-- tune_final.py --round {args.round} --sims {args.sims} --seed {args.seed}: {time.time() - t0:.0f} s -->\n")
    print(report(jobs, list(scen)))
    if args.json:
        Path(args.json).write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in jobs.items()}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
