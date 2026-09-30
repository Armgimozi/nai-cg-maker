#!/usr/bin/env python3
"""Side-by-side balance comparison: current game / variant A / variant B / recommended (balance/sim_results.md).

Runs tools/balance/sim.py's Monte-Carlo model (same loader, rules and AUTO timing) for every variant and player
profile, then adds the checks the single-variant report does not have: pacing targets side by side, early-game
feel, news (server announcement) rate per player-hour pooled over players, first own news, and an edge-case table
of every rebirth gate (can the required landmark still be rolled at that stage, expected wait vs the run length,
share of players held up by the landmark instead of the coins).

  python3 tools/balance/compare.py                 # 400 players per profile, ~4-6 min on 4 cores
  python3 tools/balance/compare.py --sims 150      # quicker
  python3 tools/balance/compare.py --out balance/sim_results.md

Variants (paths relative to roblox-rng): current = the Luau sources on disk; A = balance/variant_a.json with the
auto-discover rule its author lists as required (the JSON itself leaves it out; the as-published A is also run
for the stamp table); B = balance/variant_b.json; rec = balance/variant_rec.json.

Since the 2026-09-30 implementation round the game on disk IS the recommendation (plus the short AUTO reveal and
gacha stars), so a re-run compares the implemented game with A / B. Section 8 of balance/sim_results.md (written from
tools/balance/tune_final.py) is kept when this script rewrites the file.
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

VARIANTS = {
    "current": dict(label="current", path=None, rules=None),
    "A_raw": dict(label="A as published", path="balance/variant_a.json", rules=None),
    "A": dict(label="A (+rule)", path="balance/variant_a.json", rules={"auto_discover_below_luck": True}),
    "B": dict(label="B", path="balance/variant_b.json", rules=None),
    "rec": dict(label="recommended", path="balance/variant_rec.json", rules=None),
    # the recommended numbers if the optional short-reveal fix ships too: World Tree x2 rarer, news threshold x4
    "rec_fix": dict(
        label="recommended + short-reveal fix (World Tree 1 in 10B, news ≥ 100M)",
        path="balance/variant_rec.json",
        rules={"short_reveal_known": True},
        patch={"landmarks": {"worldtree": 10_000_000_000}, "announceOneIn": 100_000_000},
    ),
}
MAIN = ["current", "A", "B", "rec"]
EARLY_GROUP_MARKS = (5, 10, 15, 20, 30, 60)  # minutes


PREFACE = """
## 0. Recommendation and how it was reached

**Recommended = `balance/variant_rec.json`.** It starts from A because A already met the 3rd, 5th and 10th rebirth
targets and kept the early game. B met the targets too, but it finds 40 / 52 / 72 landmarks by minute 5 / 15 / 60
instead of 64 / 88 / 114 today. Tiers 1–3 stay at today's odds; the extra digits start at 1 in 1,000, so tier 7
becomes 1 in 8M–5B (today 1M–40M).

What the recommended variant changes from A:

| change | A | recommended | why |
|---|---|---|---|
| step 1 coins | 5k (4 min) | **300k (~17 min, p10–p90 15–19)** | inside the 15–30 min target; common/uncommon finds (tiers 1–2) are exactly as fast as today, only 2–3 tier-3/4 finds come later around minutes 15–20 (section 4) |
| step 5 coins | 2B (5th at ~29 h) | **1.5B (~25 h)** | puts the 5th rebirth nearer "about a day" |
| step 10 landmark | shangrila (1 in 375M) | **skyisland (1 in 110M)** | same median, but the free p90 for the 10th drops from ~33 d to ~25 d (the last gate alone was 7.4 days expected); shangrila and World Tree stay optional goals |
| news / hologram | ≥ 1M / ≥ 8M | **≥ 25M / ≥ 100M** | A gave ~10 (free) and ~19 (paid) news per endgame player-hour; now ~0.3 / 0.6 |
| auto-discover rule | missing from the JSON | **`rules.autoDiscoverBelowLuck: true`** | without it paying players end with 0/5 passport stamps (section 7) |

**The targets contradict each other on the 1st rebirth.** Today's first rebirth takes 4 minutes, so "15–30 min" and
"first-rebirth time stays similar" can't both hold. The recommended **300k** meets the 15–30 min number and keeps the
common/uncommon cadence (tiers 1–2, 1 in 1–99) identical to today: 37 of 38 by minute 5, all 38 by minute 10, for
every step-1 value tried. What it costs is 2–3 tier-3/4 finds around minutes 15–20 (85 vs 88 at 15 min, 91 vs 94 at
20 min, 101 vs 102 at 30 min, 114 = 114 at 60 min), because today's early rebirth gives +20 % luck sooner. One number
switches it: **5k** keeps today's 4-minute first rebirth, **100k** (~10 min) loses no find at any minute. Nothing after
the 3rd rebirth changes.

**Code changes the variant needs** (the simulator applies them; the game doesn't have them yet):
1. `PlayerState.luck`: rebirth multiplier `2^rebirths` instead of `1 + 0.2 × rebirths`, plus the "+20%" texts and 2 tests.
2. Auto-discover: an undiscovered landmark whose 1-in ≤ the player's permanent luck (boosts excluded) counts as
   discovered. RollLogic can never roll it again, so without this, stamps get stuck. Required landmarks are not
   affected: section 6 shows every gate stays ≥ 5× above the luck a boosted paying player has at that stage.
3. Config/Landmarks numbers: odds table (A's), tier minimums 1 / 10 / 100 / 1k / 12.5k / 250k / 8M, tier income
   1 / 2 / 5 / 12 / 35 / 120 / 500, the rebirth table, `ANNOUNCE_ONE_IN` 25M and `HOLOGRAM_ONE_IN` 100M.

**Recommended, optional:**
- Short reveal in AUTO for already-discovered landmarks. Today every tier-4+ result holds AUTO for 4.8–6.7 s, which
  makes FastRoll and Agency worthless late in the game. If this ships, also set World Tree to 1 in 10B and news to
  ≥ 100M (the `rec_fix` rows in section 7).
- Hybrid news rule: announce at ≥ 25M, **or** when the find is ≥ 20,000 × the player's luck (and ≥ 12.5k). New
  players then get their own news about every 1–2 hours of rolling instead of never (section 5).

**Monetization note:** coins set the pace, so LuckBoost purchases barely move the rebirth timeline (a heavy spender
reaches the 10th rebirth only a few hours sooner). The paid player is about 2× faster mostly because of DoubleIncome.
VIP mainly shortens the landmark hunts and the World Tree wait.

### Iteration log

Quick runs used 150–300 players per profile; the tables below use 400.

| # | tried | result | kept |
|---|---|---|---|
| 0 | current, A as published, B | current 4 min / 33 min / 2.5 h / 4.1 d (1st / 3rd / 5th / 10th); A 4 min / 2.7 h / 29 h / 23 d, paid stamps 0/5, 10–19 news per endgame player-hour; B 23 min / 2.8 h / 22 h / 25 d but early finds 40 / 52 / 72 | start from A |
| 1 | A + rule + news 8M; step 1 = 100k / 150k / 250k | 1st 10 / 12 / 16 min; found by 15 min 88.5 / 86 / 84 (today 88); later rebirths unchanged | step 1 raised |
| 2 | Globe base price 400 → 250 (step 1 200k–250k) | found by 15 min still 85–86 | no |
| 3 | Globe growth 1.7 → 1.5–1.55, or +15 %/level | 15-min finds 85–86; +15 %/level also cuts the World Tree wait from 51 to 38 d | no |
| 4 | step 10 landmark: skyisland vs shangrila (± short-reveal fix) | median 10th 22.9 vs 23.1 d; p90 24.4 vs 31.7 d (free), 12.3 vs 17.1 d (paid); with the fix both ~18.4 d | skyisland |
| 5 | step 5 coins 2B → 1.5B / 1.25B | 5th 29.2 h → 25.2 / 23.2 h; 10th ~22.7 d | 1.5B |
| 6 | step 1 fine grid, 400 players, landmarks found at 5/10/15/20/30/60 min | today 64/80/88/94/102/114; 80k (9 min) 64/78.5/89/96/104/116; **100k (10 min) 64/78/88/95/104/116**; 125k (11 min) 64/78/87/95/103/116; 250k (16 min) 64/78/85/92/101/114.5 | 100k (replaced in #8) |
| 7 | news: fixed 2M / 8M / 25M / 100M; luck-relative ×10k / ×20k / ×30k; hybrid | per endgame player-hour (free / paid): 2M 4.1 / 8.2, 8M 0.82 / 1.6, 25M 0.31 / 0.61, 100M 0.05 / 0.1; a relative rule alone falls from ~0.7 (run 0) to ~0.01 (run 10) | 25M, hybrid as option |
| 8 | step 1 = 100k / 150k / 200k / 250k / 300k / 350k, finds split into tiers 1–2 vs tier 3+ (400 players) | 1st 10 / 12 / 14 / 15.5 / 17 / 18.5 min (today 4); tiers 1–2 found by 5 / 10 min = 37 / 38 for every value and today; tier 3+ by 15 min 51 / 49 / 47 / 47 / 47 for 100k–300k (today 50); 3rd rebirth 2.75 h (100k) → 2.87 h (300k); 250k's p10 is 14 min | 300k (p10–p90 inside 15–30 min) |
"""


def merge(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            out[k] = merge(base.get(k), v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(patch)


def load_game(key: str, extra_rules: dict | None = None, extra_cfg: dict | None = None) -> S.Game:
    spec = VARIANTS[key]
    cfg = S.load_current("auto")
    if spec["path"]:
        v = json.loads((ROOT / spec["path"]).read_text(encoding="utf-8"))
        v = merge(v, spec.get("patch") or {})
        rules = dict(v.get("rules") or {})
        rules.update(spec["rules"] or {})
        rules.update(extra_rules or {})
        if rules:
            v["rules"] = rules
        cfg = S.apply_variant(cfg, v)
    elif extra_rules:
        cfg = copy.deepcopy(cfg)
        cfg["rules"] = dict(extra_rules)
    if extra_cfg:
        cfg = copy.deepcopy(cfg)
        cfg.update(copy.deepcopy(extra_cfg))
    return S.Game(cfg)


# ---------------------------------------------------------------------------------------------- one job


def job(spec: dict) -> dict:
    key, kind, sims, seed, horizon = spec["key"], spec["kind"], spec["sims"], spec["seed"], spec["horizon"]
    game = load_game(key, spec.get("extra_rules"), spec.get("extra_cfg"))
    prof = S.make_profile(game, kind, spec.get("boosts", 1.0 if kind == "paid" else 0.0), spec.get("server_luck", 0.0), 0.0)
    t0 = time.time()
    res = S.simulate(game, prof, sims, seed, horizon, 0.02, spec.get("policy", "ready"), "auto")
    sm = S.summarize(game, res)
    R = game.max_reb
    out = dict(key=key, kind=kind, tag=spec.get("tag", ""), summary=sm, seconds=time.time() - t0)
    # news per player-hour by run, pooled (sum of announcements / sum of seconds) — unbiased for rare events
    secs, ann = res["run_seconds"], res["run_announce"]
    out["news_by_run"] = [float(ann[:, r].sum() / secs[:, r].sum() * 3600) if secs[:, r].sum() > 0 else None for r in range(R + 1)]
    out["rolls_per_h_by_run"] = [
        float(res["run_rolls"][:, r].sum() / secs[:, r].sum() * 3600) if secs[:, r].sum() > 0 else None for r in range(R + 1)
    ]
    # first own news = first discovery of any landmark at/above the news threshold (auto-discovery never reaches it)
    cols = np.flatnonzero(game.announce)
    if cols.size:
        dt = res["disc_t"][:, cols]
        has = ~np.isnan(dt)
        first = np.where(has.any(1), np.nanmin(np.where(has, dt, np.inf), axis=1), np.nan)
        arg = np.argmin(np.where(has, dt, np.inf), axis=1)
        rb = np.array([res["disc_reb"][s, cols[a]] if has[s].any() else -1 for s, a in enumerate(arg)])
        out["first_news"] = dict(
            median_s=S.cq(first, 0.5), reached=float(np.isfinite(first).mean()), run=float(np.median(rb[rb >= 0])) if (rb >= 0).any() else None
        )
    else:
        out["first_news"] = dict(median_s=None, reached=0.0, run=None)
    out["stamps_all_share"] = float((res["final_stamps"] == int((game.region_required > 0).sum())).mean())
    # early feel split by tier group: common/uncommon (tiers 1-2) vs 1 in >= tier-3 minimum
    early = {}
    for m in EARLY_GROUP_MARKS:
        found = res["disc_t"] <= m * MINUTE
        early[m] = dict(
            total=float(np.median(found.sum(1))),
            common=float(np.median(found[:, game.rank <= 2].sum(1))),
            rare=float(np.median(found[:, game.rank >= 3].sum(1))),
        )
    out["early_groups"] = early
    out["n_common"] = int((game.rank <= 2).sum())
    # rebirth gates: how often the landmarks (not the coins) decided the rebirth, and median hunt share
    gates = []
    for k in range(1, R + 1):
        start, end, ready = res["reb_t"][:, k - 1], res["reb_t"][:, k], res["ready_t"][:, k - 1]
        ok = np.isfinite(end) & np.isfinite(start)
        run = end - start
        bound = ok & np.isfinite(ready) & (end - ready <= 0.02 * np.maximum(run, 1))
        gates.append(
            dict(
                k=k,
                landmark_bound=float(bound[ok].mean()) if ok.any() else None,
                hunt_share=float(np.median(((ready - start) / np.maximum(run, 1))[ok])) if ok.any() else None,
                luck_end=float(np.nanmedian(res["reb_luck"][:, k])) if ok.any() else None,
                run_median_s=S.cq(run, 0.5),
            )
        )
    out["gates"] = gates
    out["final_luck"] = float(np.median(res["final_luck"]))
    return out


# ---------------------------------------------------------------------------------------------- analytics


def period_vector(game: S.Game, luck: float, prof_mix, cd: float, known: bool = True) -> tuple[np.ndarray, float]:
    p = sum(game.probs(np.array([luck * m]))[0] * w for m, w in prof_mix)
    ov = game.overhead_known if (known and game.short_reveal_known) else game.overhead
    period = np.maximum(cd, ov)
    return p, float((p * period).sum())


def gate_table(key: str, jobs: dict) -> list[dict]:
    """For every rebirth step: required landmarks, luck at that stage, expected wait, rollable under paid boosts."""
    game = load_game(key)
    free, paid = jobs.get((key, "free", "")), jobs.get((key, "paid", ""))
    rows = []
    passes = game.cfg["passes"]
    vip = float(np.prod([p.get("luck_mult", 1) for p in passes.values()]))
    boosts = float(np.prod([p.get("luck_mult", 1) for p in game.cfg["products"].values() if p.get("seconds")]))
    g_max = 1 + game.up_per[S.G] * game.up_max[S.G]
    for k in range(1, game.max_reb + 1):
        step = game.cfg["rebirths"][k - 1]
        r = k - 1  # run in which this step is earned
        stamps_max = int((game.region_required > 0).sum())
        # luck at the start of that run (Globe 0, stamps as simulated at the previous rebirth) and at its end
        luck_hi = free["gates"][k - 1]["luck_end"] if free else None
        if luck_hi is None or not np.isfinite(luck_hi):
            luck_hi = game.cfg["base_luck"] * g_max * (1 + game.cfg["region_luck_bonus"] * stamps_max) * game.RL[r]
        luck_lo = game.cfg["base_luck"] * game.RL[r]
        paid_end = paid["gates"][k - 1]["luck_end"] if paid else None
        if paid_end is None or not np.isfinite(paid_end):
            paid_end = game.cfg["base_luck"] * g_max * (1 + game.cfg["region_luck_bonus"] * stamps_max) * game.RL[r] * vip
        paid_max = paid_end * boosts  # simulated end-of-run paid luck with LuckBoost and ServerLuck running
        cd = game.cfg["roll_cooldown"]
        _, spr_hi = period_vector(game, luck_hi, [(1.0, 1.0)], cd)
        p_hi = game.probs(np.array([luck_hi]))[0]
        items = []
        for lm_id in step["landmarks"]:
            i = game.index[lm_id]
            n = float(game.N[i])
            exp_rolls = 1.0 / p_hi[i] if p_hi[i] > 0 else math.inf
            items.append(dict(id=lm_id, n=n, exp_rolls=exp_rolls, exp_s=exp_rolls * spr_hi, rollable_paid_boosted=n > paid_max))
        # expected time until ALL required are owned (independent geometric waits in rolls; per-roll probs p_i)
        ps = np.array([p_hi[game.index[x]] for x in step["landmarks"]])
        if (ps > 0).all():
            # E[max of geometrics] via inclusion-exclusion over subsets
            m = len(ps)
            e_all = 0.0
            for mask in range(1, 1 << m):
                sub = [ps[j] for j in range(m) if mask >> j & 1]
                q = 1 - np.prod([1 - x for x in sub])
                e_all += (-1) ** (len(sub) + 1) / q
        else:
            e_all = math.inf
        run_med = free["gates"][k - 1]["run_median_s"] if free else None
        rows.append(
            dict(
                k=k,
                coins=float(step["coins"]),
                items=items,
                luck_lo=float(luck_lo),
                luck_hi=float(luck_hi),
                paid_max=float(paid_max),
                all_exp_s=float(e_all * spr_hi),
                run_median_s=run_med,
                free_bound=free["gates"][k - 1]["landmark_bound"] if free else None,
                paid_bound=paid["gates"][k - 1]["landmark_bound"] if paid else None,
                hunt_share=free["gates"][k - 1]["hunt_share"] if free else None,
            )
        )
    return rows


def early_feel(key: str) -> dict:
    game = load_game(key)
    p = game.probs(np.array([1.0]))[0]
    share = [float(p[game.rank == r].sum()) for r in range(1, game.n_tiers + 1)]
    spr = float((p * np.maximum(game.cfg["roll_cooldown"], game.overhead)).sum())
    return dict(tier_share=share, s_per_roll=spr, tier_min=[float(x) for x in game.tier_min], rarest=float(game.N[0]))


# ---------------------------------------------------------------------------------------------- report


def fd(x) -> str:
    return S.fmt_dur(x) if x is not None else "—"


def cell(r: dict) -> str:
    if r is None or r.get("median_s") is None or not np.isfinite(r["median_s"]):
        return "—"
    hi = fd(r["p90_s"]) if np.isfinite(r["p90_s"]) else ">horizon"
    return f"**{fd(r['median_s'])}** ({fd(r['p10_s'])}–{hi})"


def verdict(v, lo, hi) -> str:
    if v is None or not np.isfinite(v):
        return "not reached"
    if v < lo:
        return f"too fast ×{lo / v:.1f}"
    if v > hi:
        return f"too slow ×{v / hi:.1f}"
    return "✓"


def rate(x) -> str:
    if x is None:
        return "—"
    if x == 0:
        return "0"
    if x >= 10:
        return f"{x:,.0f}"
    return f"{x:.2g}"


def build_report(jobs: dict, args, elapsed: float) -> str:
    L = []
    lab = {k: VARIANTS[k]["label"] for k in VARIANTS}
    L.append("# Landmark RNG — balance comparison: current / A / B / recommended\n")
    L.append(
        f"Generated by `tools/balance/compare.py` on {time.strftime('%Y-%m-%d')} with the `tools/balance/sim.py` model "
        f"({args.sims} Monte-Carlo players per profile, seed {args.seed}, {args.horizon_days:g} days of online play, "
        f"AUTO rolling, upgrade policy `ready`, current client timings; {elapsed:.0f} s). Only online time counts.\n"
    )
    L.append(
        "- **current** = the game as it is in `src/` today. **A** = `balance/variant_a.json` plus the auto-discover rule "
        "that A's author lists as required; the JSON leaves the rule out. **B** = `balance/variant_b.json`. "
        "**recommended** = `balance/variant_rec.json`, built by `tools/balance/variant_rec_design.py`.\n"
        "- **free** = no passes. **paid** = all 3 passes from minute 0 plus one 15-minute LuckBoost per day of play.\n"
        "- Cells show the **median** of cumulative online time, with p10–p90 in brackets.\n"
    )
    L.append(PREFACE)

    # --- targets ---
    L.append("## 1. Pacing targets (free player)\n")
    L.append("| target | range | " + " | ".join(lab[k] for k in MAIN) + " |")
    L.append("|---|---|" + "---|" * len(MAIN))
    for name, k, lo, hi in S.TARGETS:
        row = f"| {name} | {fd(lo)}–{fd(hi)} |"
        for key in MAIN:
            r = jobs[(key, "free", "")]["summary"]["rebirths"]
            v = r[k - 1]["median_s"] if len(r) >= k else None
            row += f" {fd(v)} {verdict(v, lo, hi)} |"
        L.append(row)
    for mark in ("5min", "15min", "60min"):
        base = jobs[("current", "free", "")]["summary"]["early_distinct"][mark]
        row = f"| landmarks found by {mark} | ≥ current ({base:.0f}) |"
        for key in MAIN:
            v = jobs[(key, "free", "")]["summary"]["early_distinct"][mark]
            row += f" {v:.0f} {'✓' if v >= base - 0.5 else f'({v - base:+.0f})'} |"
        L.append(row)
    base_c = jobs[("current", "free", "")]["early_groups"]
    row = "| common/uncommon (tiers 1–2) found by 5 / 10 min | = current (" + f"{base_c[5]['common']:.0f} / {base_c[10]['common']:.0f}) |"
    for key in MAIN:
        e = jobs[(key, "free", "")]["early_groups"]
        ok = e[5]["common"] >= base_c[5]["common"] - 0.5 and e[10]["common"] >= base_c[10]["common"] - 0.5
        row += f" {e[5]['common']:.0f} / {e[10]['common']:.0f} {'✓' if ok else '✗'} |"
    L.append(row)
    row = "| first legendary (tier 7) | mid/late rebirths |"
    for key in MAIN:
        t = {x["rank"]: x for x in jobs[(key, "free", "")]["summary"]["tiers"]}.get(7)
        row += f" {fd(t['median_s'])}, run {t['at_rebirth_median']:.0f} |" if t and t["at_rebirth_median"] is not None else " — |"
    L.append(row)
    row = "| rarest, expected wait at rebirth 10 (free / paid, maxed) | days–weeks |"
    for key in MAIN:
        f_ = jobs[(key, "free", "")]["summary"]["endgame_max"]["rarest_s"]
        p_ = jobs[(key, "paid", "")]["summary"]["endgame_max"]["rarest_s"]
        row += f" {fd(f_)} / {fd(p_)} |"
    L.append(row)
    row = "| passport stamps at the horizon, paid (median, all 5) | 5/5 |"
    for key in MAIN:
        j = jobs[(key, "paid", "")]
        row += f" {j['summary']['final']['stamps']:.0f}/5, {j['stamps_all_share']:.0%} |"
    L.append(row)
    row = "| news per player-hour at the horizon (free / paid) | special, not spammy |"
    for key in MAIN:
        f_ = jobs[(key, "free", "")]["news_by_run"][-1]
        p_ = jobs[(key, "paid", "")]["news_by_run"][-1]
        row += f" {rate(f_)} / {rate(p_)} |"
    L.append(row)
    L.append("")

    # --- timelines ---
    for kind in ("free", "paid"):
        L.append(f"## 2{'a' if kind == 'free' else 'b'}. Rebirth timeline, {kind} player (cumulative online time)\n")
        L.append("| # | target (free) | " + " | ".join(lab[k] for k in MAIN) + " |")
        L.append("|---|---|" + "---|" * len(MAIN))
        tmap = {k: (lo, hi) for _, k, lo, hi in S.TARGETS}
        for k in range(1, 11):
            tg = f"{fd(tmap[k][0])}–{fd(tmap[k][1])}" if (k in tmap and kind == "free") else ""
            row = f"| {k} | {tg} |"
            for key in MAIN:
                r = jobs[(key, kind, "")]["summary"]["rebirths"]
                row += f" {cell(r[k - 1]) if len(r) >= k else '—'} |"
            L.append(row)
        L.append("")
        if kind == "free":
            L.append("Rebirth requirements (coins + landmarks owned in that run):\n")
            L.append("| # | " + " | ".join(lab[k] for k in MAIN) + " |")
            L.append("|---|" + "---|" * len(MAIN))
            games = {key: load_game(key) for key in MAIN}
            for k in range(1, 11):
                row = f"| {k} |"
                for key in MAIN:
                    st = games[key].cfg["rebirths"][k - 1]
                    row += f" {S.fmt_num(st['coins'])} + {', '.join(st['landmarks'])} |"
                L.append(row)
            L.append("")

    # --- tiers ---
    L.append("## 3. First discovery per tier (free / paid): time, run it happened in\n")
    L.append("Tier boundaries differ between variants (B moved them), so the row is the tier rank, not a fixed 1-in.\n")
    L.append("| tier | " + " | ".join(lab[k] for k in MAIN) + " |")
    L.append("|---|" + "---|" * len(MAIN))
    for rank in range(4, 8):
        row = f"| {rank} |"
        for key in MAIN:
            parts = []
            for kind in ("free", "paid"):
                t = {x["rank"]: x for x in jobs[(key, kind, "")]["summary"]["tiers"]}.get(rank)
                if t and t["median_s"] is not None and np.isfinite(t["median_s"]):
                    rb = t["at_rebirth_median"]
                    parts.append(f"{fd(t['median_s'])} (r{rb:.0f})" if rb is not None else fd(t["median_s"]))
                else:
                    parts.append("—")
            row += " " + " / ".join(parts) + " |"
        L.append(row)
    row = "| tier 7 range |"
    for key in MAIN:
        g = load_game(key)
        row += f" 1 in {S.fmt_num(g.tier_min[6])}–{S.fmt_num(g.N[0])} |"
    L.append(row)
    L.append("")

    # --- early feel ---
    L.append("## 4. Early game: do the first rolls feel the same?\n")
    L.append("Share of rolls by tier at luck 1 (first roll of a new player), AUTO seconds per roll at luck 1, landmarks found.\n")
    L.append("| | " + " | ".join(lab[k] for k in MAIN) + " |")
    L.append("|---|" + "---|" * len(MAIN))
    feels = {key: early_feel(key) for key in MAIN}
    for rank in range(1, 8):
        row = f"| tier {rank} share (1 in ≥ …) |"
        for key in MAIN:
            f_ = feels[key]
            row += f" {f_['tier_share'][rank - 1]:.3g} (≥{S.fmt_num(f_['tier_min'][rank - 1])}) |"
        L.append(row)
    row = "| AUTO s/roll at luck 1 |"
    for key in MAIN:
        row += f" {feels[key]['s_per_roll']:.2f} |"
    L.append(row)
    for mark in ("5min", "15min", "60min"):
        for kind in ("free", "paid"):
            row = f"| landmarks found by {mark}, {kind} |"
            for key in MAIN:
                row += f" {jobs[(key, kind, '')]['summary']['early_distinct'][mark]:.0f} |"
            L.append(row)
    for m in EARLY_GROUP_MARKS:
        row = f"| found by {m} min, free: tiers 1–2 + tier 3 and rarer = total |"
        for key in MAIN:
            e = jobs[(key, "free", "")]["early_groups"][m]
            row += f" {e['common']:.0f} + {e['rare']:.0f} = {e['total']:.0f} |"
        L.append(row)
    for rank in (4, 5):
        row = f"| first tier {rank}, free |"
        for key in MAIN:
            t = {x["rank"]: x for x in jobs[(key, "free", "")]["summary"]["tiers"]}.get(rank)
            row += f" {fd(t['median_s']) if t else '—'} |"
        L.append(row)
    L.append("")

    # --- news ---
    L.append("## 5. Server news (announcement) per player-hour of rolling, by run\n")
    L.append(
        "Pooled over all simulated players (total announcements ÷ total hours in that run). Multiply by the number of "
        "players in a server for the rate everyone sees. The news threshold is the fixed `ANNOUNCE_ONE_IN` of each "
        "variant.\n"
    )
    L.append("| run (rebirths done) | " + " | ".join(f"{lab[k]} free / paid" for k in MAIN) + " |")
    L.append("|---|" + "---|" * len(MAIN))
    for r in range(0, 11):
        row = f"| {r} |"
        for key in MAIN:
            f_ = jobs[(key, "free", "")]["news_by_run"]
            p_ = jobs[(key, "paid", "")]["news_by_run"]
            row += f" {rate(f_[r] if r < len(f_) else None)} / {rate(p_[r] if r < len(p_) else None)} |"
        L.append(row)
    row = "| threshold (1 in ≥) |"
    for key in MAIN:
        row += f" {S.fmt_num(load_game(key).cfg['announce_one_in'])} |"
    L.append(row)
    row = "| first own news, free (time, run) |"
    for key in MAIN:
        fn = jobs[(key, "free", "")]["first_news"]
        if fn["median_s"] is not None and np.isfinite(fn["median_s"]):
            row += f" {fd(fn['median_s'])}, run {fn['run']:.0f} |"
        else:
            row += f" — ({fn['reached']:.0%} ever) |"
    L.append(row)
    L.append("")
    if ("rec", "free", "fix") in jobs:
        L.append("With the optional short-reveal fix, AUTO rolls up to 4× faster late in the game, so news gets more frequent:\n")
        L.append("| run | " + " | ".join(str(r) for r in range(11)) + " |")
        L.append("|---|" + "---|" * 11)
        for kind in ("free", "paid"):
            nb = jobs[("rec", kind, "fix")]["news_by_run"]
            L.append(f"| recommended + fix, news ≥ 25M, {kind} | " + " | ".join(rate(x) for x in nb) + " |")
        for kind in ("free", "paid"):
            if ("rec_fix", kind, "") in jobs:
                nb = jobs[("rec_fix", kind, "")]["news_by_run"]
                L.append(f"| recommended + fix, news ≥ 100M, {kind} | " + " | ".join(rate(x) for x in nb) + " |")
        L.append("")
    news_opts = [k for k in jobs if k[0] == "rec" and k[2].startswith("news")]
    if news_opts:
        L.append("Other news rules tried on the recommended variant (per player-hour, free / paid):\n")
        L.append("| rule | run 0 | run 1 | run 3 | run 5 | run 7 | run 9 | run 10 |")
        L.append("|---|---|---|---|---|---|---|---|")
        tags = sorted({k[2] for k in news_opts})
        for tag in tags:
            f_ = jobs[("rec", "free", tag)]["news_by_run"]
            p_ = jobs[("rec", "paid", tag)]["news_by_run"]
            L.append(f"| {NEWS_LABELS.get(tag, tag)} | " + " | ".join(f"{rate(f_[r])} / {rate(p_[r])}" for r in (0, 1, 3, 5, 7, 9, 10)) + " |")
        L.append("")

    # --- edge cases ---
    L.append("## 6. Edge cases: can every rebirth gate be done at its stage?\n")
    L.append(
        "For each rebirth step: the required landmarks, the free player's luck in that run (start with no Globe → "
        "simulated median at the rebirth), and the paying player's simulated luck at the end of that run with LuckBoost "
        "and ServerLuck both running (the most luck they realistically reach there). A landmark whose 1-in is at or below the current luck can't be rolled, so a "
        "gate is impossible while luck is that high; the auto-discover rule does not add it to the inventory. The "
        "expected wait is for the free player at the end-of-run luck with the current AUTO speed. \"Held up by landmark\" "
        "is the share of simulated players whose rebirth came right after the last landmark instead of after the coins.\n"
    )
    for key in MAIN:
        rows = gate_table(key, jobs)
        L.append(f"### {lab[key]}\n")
        L.append(
            "| # | coins | landmarks (1 in N) | free luck in run | paid max luck (boosted) | N ÷ paid max | expected wait for all (free) | free run (median) | held up by landmark free / paid |"
        )
        L.append("|---|---|---|---|---|---|---|---|---|")
        for g in rows:
            lms = ", ".join(f"{i['id']} ({S.fmt_num(i['n'])})" for i in g["items"])
            ratio = min(i["n"] for i in g["items"]) / g["paid_max"]
            flag = " ⚠" if ratio <= 1 else ""
            fb = "—" if g["free_bound"] is None else f"{g['free_bound']:.0%}"
            pb = "—" if g["paid_bound"] is None else f"{g['paid_bound']:.0%}"
            L.append(
                f"| {g['k']} | {S.fmt_num(g['coins'])} | {lms} | {g['luck_lo']:.3g}→{g['luck_hi']:.3g} | {g['paid_max']:.3g} |"
                f" {ratio:.3g}{flag} | {fd(g['all_exp_s'])} | {fd(g['run_median_s'])} | {fb} / {pb} |"
            )
        L.append("")
    return "\n".join(L)


NEWS_OPTIONS = {
    "news_1_8M": ("fixed 1 in ≥ 8M (every legendary)", {"announce_one_in": 8_000_000}, None),
    "news_2_100M": ("fixed 1 in ≥ 100M", {"announce_one_in": 100_000_000}, None),
    "news_3_rel": (
        "only rare for the player: 1 in ≥ 12.5k and ≥ 20,000 × luck (code change)",
        {"announce_one_in": 1e30},
        {"announce_luck_ratio": 20_000, "announce_min_one_in": 12_500},
    ),
    "news_4_hybrid": (
        "**hybrid**: 1 in ≥ 25M, or 1 in ≥ 12.5k and ≥ 20,000 × luck (code change)",
        {"announce_one_in": 25_000_000},
        {"announce_luck_ratio": 20_000, "announce_min_one_in": 12_500},
    ),
}
NEWS_LABELS = {k: v[0] for k, v in NEWS_OPTIONS.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--horizon-days", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "balance" / "sim_results.md"))
    ap.add_argument("--no-extra", dest="extra", action="store_false", help="skip the rec sensitivity / news-rule runs")
    args = ap.parse_args()
    horizon = args.horizon_days * DAY
    specs = []
    for key in MAIN + ["A_raw"]:
        for kind in ("free", "paid"):
            specs.append(dict(key=key, kind=kind, sims=args.sims, seed=args.seed, horizon=horizon))
    if args.extra:
        n2 = max(100, args.sims // 2)
        for kind in ("free", "paid"):
            specs.append(dict(key="rec", kind=kind, tag="fix", sims=n2, seed=args.seed + 7, horizon=horizon, extra_rules={"short_reveal_known": True}))
            specs.append(dict(key="A", kind=kind, tag="fix", sims=n2, seed=args.seed + 7, horizon=horizon, extra_rules={"short_reveal_known": True}))
            specs.append(dict(key="B", kind=kind, tag="fix", sims=n2, seed=args.seed + 7, horizon=horizon, extra_rules={"short_reveal_known": True}))
        for kind in ("free", "paid"):
            specs.append(dict(key="rec_fix", kind=kind, sims=n2, seed=args.seed + 7, horizon=horizon))
        specs.append(dict(key="rec", kind="paid", tag="heavy", sims=n2, seed=args.seed + 11, horizon=horizon, boosts=3.0, server_luck=0.05))
        specs.append(dict(key="rec", kind="free", tag="greedy", sims=n2, seed=args.seed + 13, horizon=horizon, policy="greedy"))
        for tag, (_, patch, rules) in NEWS_OPTIONS.items():
            for kind in ("free", "paid"):
                r = {"auto_discover_below_luck": True}
                r.update(rules or {})
                specs.append(dict(key="rec", kind=kind, tag=tag, sims=n2, seed=args.seed + 17, horizon=horizon, extra_cfg=patch, extra_rules=r))
    started = time.time()
    with Pool(args.workers) as pool:
        outs = pool.map(job, specs, chunksize=1)
    jobs = {(o["key"], o["kind"], o["tag"]): o for o in outs}
    elapsed = time.time() - started
    md = build_report(jobs, args, elapsed)
    md += ("\n" + sensitivity_section(jobs)) if args.extra else ""
    out = Path(args.out)
    if out.exists():  # keep the hand-written implementation round (section 8, tools/balance/tune_final.py)
        old = out.read_text(encoding="utf-8")
        cut = old.find("\n## 8. ")
        if cut >= 0:
            md = md.rstrip("\n") + "\n" + old[cut:]
    out.write_text(md, encoding="utf-8")
    Path(args.out).with_suffix(".json").write_text(
        json.dumps({f"{k[0]}|{k[1]}|{k[2]}": v for k, v in jobs.items()}, ensure_ascii=False, indent=1, default=float), encoding="utf-8"
    )
    print(md)
    print(f"[compare] {elapsed:.0f} s", file=sys.stderr)


def sensitivity_section(jobs: dict) -> str:
    L = ["## 7. Sensitivity\n"]
    L.append("| scenario | #1 | #3 | #5 | #10 | first legendary | rarest at max state |")
    L.append("|---|---|---|---|---|---|---|")

    def row(label, j):
        r = j["summary"]["rebirths"]
        t7 = {x["rank"]: x for x in j["summary"]["tiers"]}.get(7)
        return (
            f"| {label} | {fd(r[0]['median_s'])} | {fd(r[2]['median_s'])} | {fd(r[4]['median_s'])} | {cell(r[9])} |"
            f" {fd(t7['median_s']) if t7 else '—'} | {fd(j['summary']['endgame_max']['rarest_s'])} |"
        )

    for key in ("rec", "A", "B"):
        lab = VARIANTS[key]["label"]
        for kind in ("free", "paid"):
            L.append(row(f"{lab}, {kind}", jobs[(key, kind, "")]))
            if (key, kind, "fix") in jobs:
                L.append(row(f"{lab}, {kind}, + short-reveal fix", jobs[(key, kind, "fix")]))
    for kind in ("free", "paid"):
        if ("rec_fix", kind, "") in jobs:
            L.append(row(f"{VARIANTS['rec_fix']['label']}, {kind}", jobs[("rec_fix", kind, "")]))
    if ("rec", "paid", "heavy") in jobs:
        L.append(row("recommended, heavy spender (3 boosts/day + server luck 5% of the time)", jobs[("rec", "paid", "heavy")]))
    if ("rec", "free", "greedy") in jobs:
        L.append(row("recommended, free, policy greedy (buys every cheaper upgrade first)", jobs[("rec", "free", "greedy")]))
    raw = jobs.get(("A_raw", "paid", ""))
    if raw:
        L.append("")
        L.append(
            f"A as published (JSON without the auto-discover rule): paid stamps median {raw['summary']['final']['stamps']:.0f}/5 "
            f"({raw['stamps_all_share']:.0%} get all 5), paid 10th rebirth {fd(raw['summary']['rebirths'][9]['median_s'])}; "
            f"free: {jobs[('A_raw', 'free', '')]['stamps_all_share']:.0%} get all 5 stamps."
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
