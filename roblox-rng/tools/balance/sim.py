#!/usr/bin/env python3
"""Landmark RNG progression simulator (balance tool, numpy only).

Loads the CURRENT game numbers straight from the Luau sources (src/shared/Config.luau,
src/shared/Landmarks.luau via tools/balance/dump.luau + the repo's luaurun; regex fallback if the
runner is missing; client reveal timings from src/client/Hud.luau), optionally applies a variant
JSON patch, and Monte-Carlo simulates free / paying players who AUTO-roll non-stop, buy upgrades
and rebirth as soon as they can. Writes a markdown timeline (and optionally JSON).

Run from anywhere (paths resolve relative to the roblox-rng folder):

  python3 tools/balance/sim.py                         # current game -> balance/sim_current.md (+ .json)
  python3 tools/balance/sim.py --check                 # + validation vs the real Luau code
  python3 tools/balance/sim.py --variant balance/variant_x.json --out balance/sim_x.md
  python3 tools/balance/sim.py --sims 200 --horizon-days 60 --players free
  python3 tools/balance/sim.py --mode ideal            # ignore the AUTO reveal animation (period = cooldown)
  python3 tools/balance/sim.py --policy greedy         # never save for rebirth (see POLICY below)
  python3 tools/balance/sim.py --dump-config           # print the normalised config JSON (the variant base)

MODEL (one Monte-Carlo run = one player; S runs vectorised with numpy)
  * Rolls: exact RollLogic probabilities for the current luck (rarest first, success = min(1, luck/N),
    fallback = most common). Counts per window ~ Multinomial(K, p) (vectorised), windows are
    adaptive: K = min(frac * rolls-this-run, rolls until the next purchase / rebirth coins, horizon),
    so purchases and rebirths land at the right roll and long hunts for 1-in-millions take O(log) steps.
  * Roll period (AUTO): the client only sends the next roll after the reveal animation finished
    (init.client.luau roll(): invoke -> Hud.reveal(Fast) -> task.wait(0.05) loop), so
    period = max(cooldown, rtt + reveal(rank of the result) + loop wait). cooldown = ROLL_COOLDOWN *
    (1 - Agency) * FastRoll. `--mode ideal` uses period = cooldown (what the upgrades promise).
  * Luck = BASE * (1 + Globe) * (1 + REGION_LUCK_BONUS * stamps) * rebirthLuck(r) * VIP * boosts.
    Stamps are exact: a continent counts once every landmark of rank <= STAMP_MAX_RANK in it was ever
    discovered (Discovered survives rebirths). Boosts = duty cycle (fraction of play time under x2),
    mixed into the per-roll probability vector.
  * Income/s = sum over the park (AutoPark: rarest owned landmarks, `slots` of them) of
    TIER_INCOME[rank] * (1 + STAR_INCOME_BONUS * (stars - 1)) * (1 + Ticket) * rebirthIncome(r) * 2x pass.
    Coins also get the first-ever discovery bonus ceil(DISCOVERY_BONUS_MULT * sqrt(N)). Online only.
  * Rebirth: as soon as the coins AND the step's landmarks (owned this run) are there. Resets coins,
    upgrades, inventory; keeps discoveries (stamps).
  POLICY (upgrades, "cheapest useful first"):
    ready  (default) while the next rebirth's landmarks are still missing: buy the cheapest useful
           upgrade whenever affordable (Park only if an owned landmark is not on display; Globe,
           Agency, Ticket always). Once the landmarks are owned: only buy an upgrade that makes the
           rebirth coins arrive sooner (Ticket/Park payback test), otherwise save and rebirth.
           After the last rebirth: plain greedy.
    greedy always buy the cheapest useful affordable upgrade; rebirth only when coins >= requirement
           after buying (= buys every upgrade cheaper than the rebirth price first).

VARIANT JSON (balance/variant_*.json) = a patch over the normalised config (see --dump-config):
  plain keys deep-merge (dicts merge, lists/scalars replace), e.g.
    "roll_cooldown", "base_luck", "announce_one_in", "hologram_one_in", "discovery_bonus_mult",
    "base_slots", "park_grid", "tier_income": [7], "star_thresholds", "star_income_bonus",
    "stamp_max_rank", "region_luck_bonus",
    "upgrades": {"Globe": {"base_price", "growth", "max_level", "per_level"}, "Agency", "Park", "Ticket"},
    "rebirths": [{"coins": 5000, "landmarks": ["eiffel", "liberty"]}, ...]  (max_rebirths follows its length
               unless "max_rebirths" is given),
    "rebirth_luck" / "rebirth_income": {"type": "linear", "per": 0.2} | {"type": "mult", "base": 2}
               | {"type": "table", "values": [m0, m1, ..., m_max]},
    "passes": {"LuckVIP": {"luck_mult"}, "FastRoll": {"cooldown_mult"}, "DoubleIncome": {"income_mult"}},
    "products": {"LuckBoost": {"seconds", "luck_mult"}, "ServerLuck": {...}, "CoinPack": {...}},
    "tiers": [{"rank", "name", "min_one_in"}] or shortcut "tier_min_one_in": [1, 10, ...],
    "client": {"rtt", "loop_wait", "reveal_seconds": [7], "land_seconds", "suspense_seconds", ...}
  special keys (applied in this order):
    "landmark_formula": {"type": "power", "exponent": e, "scale": s}      N' = s * N^e
                      | {"type": "scale", "factor": f}                    N' = f * N
                      | {"type": "tier_scale", "factors": [f1..f7]}       by the CURRENT tier of N
                      | {"type": "loglinear", "points": [[N_old, N_new], ...]}  log-log interpolation
                      optional "round_sig": 2 (significant digits, default 2), "min": 2
    "landmark_one_in": {"eiffel": 5000, ...}        explicit per-landmark overrides
    "landmarks_extra": [{"id", "name", "one_in", "region"}]
    "name", "notes": free text (shown in the report)
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]  # roblox-rng
LUAURUN = ROOT / "tools" / "luaurun" / "target" / "release" / "luaurun"
DUMP = "tools/balance/dump.luau"
MINUTE, HOUR, DAY = 60.0, 3600.0, 86400.0
UPGRADE_IDS = ("Globe", "Agency", "Park", "Ticket")  # effects are hard-coded by Id in PlayerState
G, A, P, T = range(4)

# ---------------------------------------------------------------------------------------------
# loading


def _run_luau(*args: str) -> dict:
    out = subprocess.run([str(LUAURUN), DUMP, *args], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"luaurun failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def _num_expr(expr: str) -> float:
    value = 1.0
    for part in expr.split("*"):
        value *= float(part.strip())
    return value


def parse_luau_regex() -> dict:
    """Fallback loader: reads Config.luau / Landmarks.luau with regexes (same normalised schema)."""
    conf = (ROOT / "src/shared/Config.luau").read_text(encoding="utf-8")
    lms = (ROOT / "src/shared/Landmarks.luau").read_text(encoding="utf-8")

    def num(name: str) -> float:
        m = re.search(rf"\b{name}\s*=\s*([\d.]+(?:\s*\*\s*[\d.]+)*)", conf)
        if not m:
            raise ValueError(f"Config.{name} not found")
        return _num_expr(m.group(1))

    def arr(name: str) -> list:
        m = re.search(rf"\b{name}\s*=\s*\{{([^}}]*)\}}", conf)
        return [float(x) for x in m.group(1).split(",") if x.strip()]

    up_block = conf[conf.index("Upgrades = {") : conf.index("REBIRTHS = {")]
    upgrades, order = {}, []
    for m in re.finditer(
        r'Id\s*=\s*"(\w+)".*?BasePrice\s*=\s*([\d.]+).*?Growth\s*=\s*([\d.]+).*?MaxLevel\s*=\s*(\d+).*?PerLevel\s*=\s*([\d.]+)',
        up_block,
        re.S,
    ):
        order.append(m.group(1))
        upgrades[m.group(1)] = dict(
            base_price=float(m.group(2)), growth=float(m.group(3)), max_level=int(m.group(4)), per_level=float(m.group(5))
        )
    rebirths = [
        {"coins": float(m.group(1)), "landmarks": re.findall(r'"(\w+)"', m.group(2))}
        for m in re.finditer(r"\{\s*Coins\s*=\s*(\d+),\s*Landmarks\s*=\s*\{([^}]*)\}", conf)
    ]

    def fields(body: str) -> dict:
        return {k: v for k, v in re.findall(r"(\w+)\s*=\s*([\w.]+)", body)}

    passes = {}
    for m in re.finditer(r'\{\s*Id\s*=\s*"(\w+)",\s*Name\s*=\s*"[^"]*",\s*PassId\s*=\s*\d+(.*?)\}', conf, re.S):
        f = fields(m.group(2))
        passes[m.group(1)] = dict(
            luck_mult=float(f.get("LuckMult", 1)),
            cooldown_mult=float(f.get("CooldownMult", 1)),
            income_mult=float(f.get("IncomeMult", 1)),
        )
    products = {}
    for m in re.finditer(r'\{\s*Id\s*=\s*"(\w+)",\s*Name\s*=\s*"[^"]*",\s*ProductId\s*=\s*\d+(.*?)\}', conf, re.S):
        f = fields(m.group(2))
        products[m.group(1)] = dict(
            seconds=float(f.get("Seconds", 0)),
            luck_mult=float(f.get("LuckMult", 1)),
            server_wide=f.get("ServerWide") == "true",
            income_seconds=float(f.get("IncomeSeconds", 0)),
            min_coins=float(f.get("MinCoins", 0)),
        )
    tiers = [
        {"rank": int(m.group(1)), "name": m.group(2), "min_one_in": float(m.group(3))}
        for m in re.finditer(r'Rank\s*=\s*(\d+),\s*Name\s*=\s*"([^"]*)",\s*MinOneIn\s*=\s*(\d+)', lms)
    ]
    regions = re.findall(r'\{\s*Id\s*=\s*"(\w+)",\s*Name\s*=\s*"[^"]*",\s*Emoji', lms)
    landmarks = [
        {"id": m.group(1), "name": m.group(2), "one_in": float(m.group(4)), "region": m.group(5)}
        for m in re.finditer(r'^\s*\{\s*"(\w+)",\s*"([^"]*)",\s*"([^"]*)",\s*(\d+),\s*"(\w+)"', lms, re.M)
    ]
    landmarks.sort(key=lambda x: x["one_in"])
    return dict(
        source="regex",
        roll_cooldown=num("ROLL_COOLDOWN"),
        cooldown_tolerance=num("COOLDOWN_TOLERANCE"),
        base_luck=num("BASE_LUCK"),
        announce_one_in=num("ANNOUNCE_ONE_IN"),
        hologram_one_in=num("HOLOGRAM_ONE_IN"),
        discovery_bonus_mult=num("DISCOVERY_BONUS_MULT"),
        base_slots=num("BASE_SLOTS"),
        park_grid=num("PARK_GRID"),
        tier_income=arr("TIER_INCOME"),
        star_thresholds=arr("STAR_THRESHOLDS"),
        star_income_bonus=num("STAR_INCOME_BONUS"),
        stamp_max_rank=num("STAMP_MAX_RANK"),
        region_luck_bonus=num("REGION_LUCK_BONUS"),
        upgrades=upgrades,
        upgrade_order=order,
        rebirths=rebirths,
        max_rebirths=int(num("MAX_REBIRTHS")),
        rebirth_luck={"type": "linear", "per": num("REBIRTH_LUCK_BONUS")},
        rebirth_income={"type": "linear", "per": num("REBIRTH_INCOME_BONUS")},
        passes=passes,
        products=products,
        max_boost_seconds=num("MAX_BOOST_SECONDS"),
        tiers=tiers,
        regions=regions,
        landmarks=landmarks,
    )


def parse_client_timing() -> dict:
    """AUTO-roll timing from src/client/Hud.luau (reveal animation) + defaults for the network."""
    client = dict(
        reveal_seconds=[0.9, 1.1, 1.5, 2.1, 2.7, 3.1, 3.3],
        land_seconds=0.4,
        suspense_seconds=0.9,
        fast_min=0.35,  # Fast (AUTO): spin = max(fast_min, reveal * fast_factor) below rare_rank
        fast_factor=0.5,
        rare_rank=4,  # rank >= this: full-length spin + long hold even in AUTO
        suspense_rank=5,
        hold_fast=0.2,
        hold_fast_rare=1.8,
        spin_base=0.05,  # spin loop: task.wait(spin_base + t^2 * spin_growth)
        spin_growth=0.22,
        loop_wait=0.05,  # init.client.luau AUTO loop task.wait(0.05)
        rtt=0.12,  # RemoteFunction round trip incl. server frame (assumption)
        frame=1 / 60,  # every task.wait overshoots ~half a frame on average
    )
    try:
        hud = (ROOT / "src/client/Hud.luau").read_text(encoding="utf-8")
        m = re.search(r"REVEAL_SECONDS\s*=\s*\{([^}]*)\}", hud)
        if m:
            client["reveal_seconds"] = [float(x) for x in m.group(1).split(",") if x.strip()]
        for key, name in (("land_seconds", "LAND_SECONDS"), ("suspense_seconds", "SUSPENSE_SECONDS")):
            m = re.search(rf"\b{name}\s*=\s*([\d.]+)", hud)
            if m:
                client[key] = float(m.group(1))
        m = re.search(r"math\.max\(([\d.]+),\s*duration\s*\*\s*([\d.]+)\)", hud)
        if m:
            client["fast_min"], client["fast_factor"] = float(m.group(1)), float(m.group(2))
        m = re.search(r"if info\.Fast then ([\d.]+) else [\d.]+\) else \(if info\.Fast then ([\d.]+)", hud)
        if m:
            client["hold_fast_rare"], client["hold_fast"] = float(m.group(1)), float(m.group(2))
        m = re.search(r"local interval = ([\d.]+) \+ t \* t \* ([\d.]+)", hud)
        if m:
            client["spin_base"], client["spin_growth"] = float(m.group(1)), float(m.group(2))
    except OSError:
        pass
    return client


def load_current(source: str = "auto") -> dict:
    if source in ("auto", "luaurun") and LUAURUN.exists():
        cfg = _run_luau("config")
    elif source == "luaurun":
        raise FileNotFoundError(f"{LUAURUN} missing (cargo build --release in tools/luaurun)")
    else:
        cfg = parse_luau_regex()
    cfg["client"] = parse_client_timing()
    return cfg


def _deep_merge(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            out[k] = _deep_merge(base.get(k), v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(patch)


def _round_sig(x: float, sig: int) -> float:
    if x <= 0:
        return x
    d = math.floor(math.log10(x))
    step = 10 ** (d - sig + 1)
    return float(round(x / step) * step)


SPECIAL = ("landmark_formula", "landmark_one_in", "landmarks_extra", "tier_min_one_in", "name", "notes")


def apply_variant(cfg: dict, variant: dict) -> dict:
    out = _deep_merge(cfg, {k: v for k, v in variant.items() if k not in SPECIAL})
    out["variant_name"] = variant.get("name", "variant")
    out["variant_notes"] = variant.get("notes", "")
    if "rebirths" in variant and "max_rebirths" not in variant:
        out["max_rebirths"] = len(out["rebirths"])
    if "tier_min_one_in" in variant:
        tiers = copy.deepcopy(out["tiers"])
        for tier, v in zip(tiers, variant["tier_min_one_in"]):
            tier["min_one_in"] = v
        out["tiers"] = tiers
    landmarks = copy.deepcopy(out["landmarks"])
    formula = variant.get("landmark_formula")
    if formula:
        old_tiers = sorted(cfg["tiers"], key=lambda t: t["rank"])
        sig = int(formula.get("round_sig", 2))
        lo = float(formula.get("min", 2))
        for lm in landmarks:
            n = float(lm["one_in"])
            kind = formula["type"]
            if kind == "power":
                new = formula.get("scale", 1.0) * n ** formula["exponent"]
            elif kind == "scale":
                new = formula["factor"] * n
            elif kind == "tier_scale":
                rank = max(t["rank"] for t in old_tiers if n >= t["min_one_in"])
                new = formula["factors"][rank - 1] * n
            elif kind == "loglinear":
                pts = np.array(formula["points"], dtype=float)
                new = float(np.exp(np.interp(np.log(n), np.log(pts[:, 0]), np.log(pts[:, 1]))))
            else:
                raise ValueError(f"unknown landmark_formula type {kind}")
            lm["one_in"] = max(lo, _round_sig(new, sig) if sig > 0 else new)
    for lm_id, n in (variant.get("landmark_one_in") or {}).items():
        hits = [lm for lm in landmarks if lm["id"] == lm_id]
        if not hits:
            raise KeyError(f"landmark_one_in: unknown id {lm_id}")
        hits[0]["one_in"] = float(n)
    for extra in variant.get("landmarks_extra") or []:
        landmarks.append(dict(extra))
    for lm in landmarks:
        lm.pop("rank", None)  # recomputed from tiers
    out["landmarks"] = sorted(landmarks, key=lambda x: x["one_in"])
    return out


# ---------------------------------------------------------------------------------------------
# game model (arrays, rarest first like Landmarks.RarestFirst)


def _rule_table(rule: dict, n: int) -> np.ndarray:
    r = np.arange(n + 1, dtype=float)
    kind = rule.get("type", "linear")
    if kind == "linear":
        return 1.0 + rule["per"] * r
    if kind == "mult":
        return float(rule["base"]) ** r
    if kind == "table":
        vals = [float(v) for v in rule["values"]]
        return np.array([vals[min(int(i), len(vals) - 1)] for i in r])
    raise ValueError(f"unknown rebirth rule {rule}")


def auto_overhead(client: dict, rank: int) -> float:
    """Seconds from sending a roll to sending the next one in AUTO (Fast reveal), cooldown aside."""
    half = client["frame"] / 2
    dur = client["reveal_seconds"][min(rank, len(client["reveal_seconds"])) - 1]
    fast = rank < client["rare_rank"]
    if fast:
        dur = max(client["fast_min"], dur * client["fast_factor"])
    el = 0.0
    while el < dur:
        t = el / dur
        el += client["spin_base"] + t * t * client["spin_growth"] + half
    total = el + (client["land_seconds"] * 0.5 if fast else client["land_seconds"]) + half
    if rank >= client["suspense_rank"]:
        total += client["suspense_seconds"] + half
    total += (client["hold_fast"] if fast else client["hold_fast_rare"]) + half
    return client["rtt"] + total + client["loop_wait"] + half


class Game:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        lms = sorted(cfg["landmarks"], key=lambda x: -float(x["one_in"]))  # rarest first
        self.ids = [lm["id"] for lm in lms]
        self.names = [lm.get("name", lm["id"]) for lm in lms]
        self.index = {i: k for k, i in enumerate(self.ids)}
        self.N = np.array([float(lm["one_in"]) for lm in lms])
        self.M = len(lms)
        tiers = sorted(cfg["tiers"], key=lambda t: t["rank"])
        self.tier_names = [t["name"] for t in tiers]
        self.tier_min = np.array([float(t["min_one_in"]) for t in tiers])
        self.n_tiers = len(tiers)
        self.rank = np.array([1 + max(k for k in range(self.n_tiers) if n >= self.tier_min[k] or k == 0) for n in self.N])
        self.tier_onehot = np.zeros((self.M, self.n_tiers))
        self.tier_onehot[np.arange(self.M), self.rank - 1] = 1
        ti = list(cfg["tier_income"])
        self.item_income = np.array([float(ti[r - 1]) if r - 1 < len(ti) else 0.0 for r in self.rank])
        self.bonus = np.ceil(cfg["discovery_bonus_mult"] * self.N**0.5)
        self.regions = list(cfg["regions"])
        reg = np.array([self.regions.index(lm["region"]) for lm in lms])
        stamp = self.rank <= cfg["stamp_max_rank"]
        self.region_members = np.stack([(reg == r) & stamp for r in range(len(self.regions))]).astype(np.int32)
        self.region_required = self.region_members.sum(1)
        self.star_thr = np.array(cfg["star_thresholds"], dtype=float)
        self.star_bonus = float(cfg["star_income_bonus"])
        self.max_slots = int(cfg["park_grid"]) ** 2
        up = cfg["upgrades"]
        self.up = [up[u] for u in UPGRADE_IDS]
        self.up_max = np.array([u["max_level"] for u in self.up], dtype=int)
        self.up_per = np.array([u["per_level"] for u in self.up], dtype=float)
        width = int(self.up_max.max()) + 2
        self.price = np.full((4, width), np.inf)
        for k, u in enumerate(self.up):
            for lvl in range(int(u["max_level"])):
                self.price[k, lvl] = math.floor(u["base_price"] * u["growth"] ** lvl)
        self.max_reb = int(cfg["max_rebirths"])
        steps = cfg["rebirths"][: self.max_reb]
        self.reb_coins = np.full(self.max_reb + 1, np.inf)
        self.reb_req = np.zeros((self.max_reb + 1, self.M), dtype=bool)
        for k, step in enumerate(steps):
            self.reb_coins[k] = float(step["coins"])
            for lm_id in step["landmarks"]:
                self.reb_req[k, self.index[lm_id]] = True
        self.RL = _rule_table(cfg["rebirth_luck"], self.max_reb)
        self.RI = _rule_table(cfg["rebirth_income"], self.max_reb)
        self.client = cfg["client"]
        self.overhead_rank = np.array([auto_overhead(self.client, r) for r in range(1, self.n_tiers + 1)])
        self.overhead = self.overhead_rank[self.rank - 1]
        self.announce = self.N >= cfg["announce_one_in"]
        self.hologram = self.N >= cfg["hologram_one_in"]

    # --- pure formulas (vectorised over players) -------------------------------------------
    def probs(self, luck: np.ndarray) -> np.ndarray:
        """RollLogic.probabilities for each luck value -> (len(luck), M)."""
        luck = np.atleast_1d(np.asarray(luck, dtype=float))
        q = np.minimum(1.0, luck[:, None] / self.N[None, :])
        q[:, -1] = 1.0  # the most common one is the fallback
        surv = np.cumprod(1.0 - q, axis=1)
        p = q.copy()
        p[:, 1:] *= surv[:, :-1]
        return p

    def stamps(self, disc: np.ndarray) -> np.ndarray:
        missing = (~disc).astype(np.int32) @ self.region_members.T
        return ((missing == 0) & (self.region_required > 0)[None, :]).sum(1)

    def slots(self, lvl_park: np.ndarray) -> np.ndarray:
        return np.minimum(self.cfg["base_slots"] + self.up_per[P] * lvl_park, self.max_slots)

    def luck(self, lvl: np.ndarray, stamps: np.ndarray, reb: np.ndarray, luck_mult: float) -> np.ndarray:
        return (
            self.cfg["base_luck"]
            * (1 + self.up_per[G] * lvl[:, G])
            * (1 + self.cfg["region_luck_bonus"] * stamps)
            * self.RL[reb]
            * luck_mult
        )

    def cooldown(self, lvl: np.ndarray, cd_mult: float) -> np.ndarray:
        return self.cfg["roll_cooldown"] * (1 - self.up_per[A] * lvl[:, A]) * cd_mult

    def park_income(self, cnt: np.ndarray, slots: np.ndarray) -> np.ndarray:
        """Sum of landmark incomes on display (before Ticket / rebirth / pass multipliers)."""
        owned = cnt > 0
        shown = owned & (np.cumsum(owned, axis=1) <= slots[:, None])
        stars = np.searchsorted(self.star_thr, cnt, side="right")
        per = self.item_income[None, :] * (1 + self.star_bonus * (stars - 1))
        return np.where(shown, per, 0.0).sum(1)

    def income(self, cnt, lvl, reb, income_mult: float) -> np.ndarray:
        return (
            self.park_income(cnt, self.slots(lvl[:, P]))
            * (1 + self.up_per[T] * lvl[:, T])
            * self.RI[reb]
            * income_mult
        )


# ---------------------------------------------------------------------------------------------
# player profiles


def make_profile(game: Game, kind: str, boost_per_day: float | None, server_luck_duty: float, coinpacks_per_day: float):
    passes = game.cfg["passes"]
    products = game.cfg["products"]
    owned = list(passes) if kind == "paid" else []
    luck_mult = float(np.prod([passes[p].get("luck_mult", 1) for p in owned])) if owned else 1.0
    cd_mult = float(np.prod([passes[p].get("cooldown_mult", 1) for p in owned])) if owned else 1.0
    inc_mult = float(np.prod([passes[p].get("income_mult", 1) for p in owned])) if owned else 1.0
    if boost_per_day is None:
        boost_per_day = 1.0 if kind == "paid" else 0.0
    personal = [p for p in products.values() if p.get("seconds") and not p.get("server_wide")]
    server = [p for p in products.values() if p.get("seconds") and p.get("server_wide")]
    boost_duty = min(1.0, boost_per_day * (personal[0]["seconds"] if personal else 0) / DAY)
    boost_mult = personal[0]["luck_mult"] if personal else 1.0
    server_mult = server[0]["luck_mult"] if server else 1.0
    coin = products.get("CoinPack", {"income_seconds": 0, "min_coins": 0})
    # mixture over (personal boost on/off) x (server luck on/off)
    mix = []
    for b, wb in ((boost_mult, boost_duty), (1.0, 1 - boost_duty)):
        for s, ws in ((server_mult, server_luck_duty), (1.0, 1 - server_luck_duty)):
            if wb * ws > 0:
                mix.append((b * s, wb * ws))
    return dict(
        kind=kind,
        passes=owned,
        luck_mult=luck_mult,
        cd_mult=cd_mult,
        income_mult=inc_mult,
        boost_per_day=boost_per_day,
        boost_duty=boost_duty,
        server_luck_duty=server_luck_duty,
        mix=mix,
        coinpacks_per_day=coinpacks_per_day,
        coinpack_seconds=float(coin.get("income_seconds", 0)),
        coinpack_min=float(coin.get("min_coins", 0)),
    )


# ---------------------------------------------------------------------------------------------
# vectorised Monte-Carlo


def simulate(game: Game, prof: dict, sims: int, seed: int, horizon: float, frac: float, policy: str, mode: str) -> dict:
    rng = np.random.default_rng(seed)
    S, M, R = sims, game.M, game.max_reb
    cnt = np.zeros((S, M), dtype=np.int64)
    disc = np.zeros((S, M), dtype=bool)
    disc_t = np.full((S, M), np.nan)
    disc_reb = np.full((S, M), -1, dtype=np.int64)
    lvl = np.zeros((S, 4), dtype=np.int64)
    coins = np.zeros(S)
    reb = np.zeros(S, dtype=np.int64)
    t = np.zeros(S)
    rolls = np.zeros(S, dtype=np.int64)
    run_rolls = np.zeros(S, dtype=np.int64)
    run_start = np.zeros(S)
    done = np.zeros(S, dtype=bool)
    reb_t = np.full((S, R + 1), np.nan)
    reb_t[:, 0] = 0.0
    reb_rolls = np.full((S, R + 1), np.nan)
    reb_rolls[:, 0] = 0
    ready_t = np.full((S, R + 1), np.nan)  # time the step's landmarks were all owned (this run)
    reb_luck = np.full((S, R + 1), np.nan)  # luck (no boosts) right before the rebirth
    reb_income = np.full((S, R + 1), np.nan)
    reb_stamps = np.full((S, R + 1), np.nan)
    reb_lvl = np.full((S, R + 1, 4), np.nan)
    spr_log = np.zeros((S, R + 1))  # seconds / rolls per run (effective roll period)
    roll_log = np.zeros((S, R + 1))
    announce_log = np.zeros((S, R + 1))
    lm = prof["luck_mult"]
    cdm = prof["cd_mult"]
    im = prof["income_mult"]
    period_is_auto = mode == "auto"
    iters = 0

    def all_probs(luck):
        p = None
        for mult, w in prof["mix"]:
            q = game.probs(luck * mult) * w
            p = q if p is None else p + q
        return p

    while True:
        act = np.flatnonzero(~done)
        if act.size == 0:
            break
        iters += 1
        c, d_, l_, r_ = cnt[act], disc[act], lvl[act], reb[act]
        st = game.stamps(d_)
        luck = game.luck(l_, st, r_, lm)
        p = all_probs(luck)
        cd = game.cooldown(l_, cdm)
        period = np.maximum(cd[:, None], game.overhead[None, :]) if period_is_auto else np.repeat(cd[:, None], M, 1)
        spr = (p * period).sum(1)
        inc = game.income(c, l_, r_, im)
        # coin target: next purchase or rebirth coins (so windows stop right there)
        prices = game.price[np.arange(4)[None, :], l_]
        owned_n = (c > 0).sum(1)
        slots = game.slots(l_[:, P])
        prices[:, P] = np.where((owned_n > slots) & (slots < game.max_slots), prices[:, P], np.inf)
        req = game.reb_req[r_]
        req_ok = ~(req & (c <= 0)).any(1)
        # a price already <= coins was declined by the policy (saving for rebirth) -> not a target
        prices = np.where(prices > coins[act][:, None], prices, np.inf)
        target = np.minimum(prices.min(1), np.where(req_ok, game.reb_coins[r_], np.inf))
        rate = inc * spr  # coins per roll
        with np.errstate(divide="ignore", invalid="ignore"):
            k_coin = np.where((rate > 0) & np.isfinite(target), np.ceil((target - coins[act]) / rate), np.inf)
        k_frac = np.maximum(1, np.floor(frac * run_rolls[act]))
        k_hor = np.ceil(np.maximum(horizon - t[act], 0) / spr) + 1
        K = np.minimum(np.minimum(k_frac, np.maximum(k_coin, 1)), k_hor).astype(np.int64)
        K = np.maximum(K, 1)
        draws = rng.multinomial(K, p)
        dt = (draws * period).sum(1)
        new = (draws > 0) & ~d_
        bonus = (new * game.bonus[None, :]).sum(1)
        t0 = t[act]
        when = t0 + dt * (K + 1) / (2 * K)
        if new.any():
            rows, cols = np.nonzero(new)
            disc_t[act[rows], cols] = when[rows]
            disc_reb[act[rows], cols] = r_[rows]
        c = c + draws
        d_ = d_ | (draws > 0)
        inc_end = game.income(c, l_, r_, im)
        coin_gain = 0.5 * (inc + inc_end) * dt + bonus
        if prof["coinpacks_per_day"] > 0:
            coin_gain += prof["coinpacks_per_day"] * dt / DAY * np.maximum(prof["coinpack_min"], inc_end * prof["coinpack_seconds"])
        co = coins[act] + coin_gain
        tt = t0 + dt
        spr_log[act, r_] += dt
        roll_log[act, r_] += K
        announce_log[act, r_] += (draws * game.announce[None, :]).sum(1)
        rolls[act] += K
        run_rolls[act] += K

        # --- purchases -----------------------------------------------------------------------
        req_ok = ~(req & (c <= 0)).any(1)
        need_ready = np.isnan(ready_t[act, r_]) & req_ok & (r_ < R)
        if need_ready.any():
            ready_t[act[need_ready], r_[need_ready]] = tt[need_ready]
        saving = req_ok & (r_ < R) if policy == "ready" else np.zeros(act.size, dtype=bool)
        C = game.reb_coins[r_]
        for _ in range(200):
            prices = game.price[np.arange(4)[None, :], l_]
            owned_n = (c > 0).sum(1)
            slots = game.slots(l_[:, P])
            park_useful = (owned_n > slots) & (slots < game.max_slots)
            prices[:, P] = np.where(park_useful, prices[:, P], np.inf)
            if saving.any():
                # only buys that bring the rebirth coins sooner (payback before rebirth)
                s_idx = np.flatnonzero(saving)
                i0 = game.income(c[s_idx], l_[s_idx], r_[s_idx], im)
                gap = C[s_idx] - co[s_idx]
                lt = l_[s_idx].copy()
                lt[:, T] += 1
                i_t = game.income(c[s_idx], lt, r_[s_idx], im)
                lp = l_[s_idx].copy()
                lp[:, P] += 1
                i_p = game.income(c[s_idx], lp, r_[s_idx], im)
                with np.errstate(divide="ignore", invalid="ignore"):
                    base_wait = gap / i0
                    ok_t = (gap > 0) & ((gap + prices[s_idx, T]) / i_t < base_wait)
                    ok_p = (gap > 0) & ((gap + prices[s_idx, P]) / i_p < base_wait)
                sub = prices[s_idx]
                sub[:, G] = np.inf
                sub[:, A] = np.inf
                sub[:, T] = np.where(ok_t, sub[:, T], np.inf)
                sub[:, P] = np.where(ok_p, sub[:, P], np.inf)
                prices[s_idx] = sub
            choice = prices.argmin(1)
            cost = prices[np.arange(act.size), choice]
            buy = cost <= co
            if not buy.any():
                break
            co = np.where(buy, co - np.where(buy, cost, 0), co)
            l_[buy, choice[buy]] += 1

        # --- rebirth ---------------------------------------------------------------------
        can = (r_ < R) & req_ok & (co >= C)
        if can.any():
            ci = act[can]
            rr = r_[can]
            nr = rr + 1
            reb_t[ci, nr] = tt[can]
            reb_rolls[ci, nr] = rolls[ci]
            reb_luck[ci, nr] = game.luck(l_[can], game.stamps(d_[can]), rr, lm)
            reb_income[ci, nr] = game.income(c[can], l_[can], rr, im)
            reb_stamps[ci, nr] = game.stamps(d_[can])
            reb_lvl[ci, nr] = l_[can]
            c[can] = 0
            l_[can] = 0
            co[can] = 0.0
            r_ = r_.copy()
            r_[can] = nr
            run_rolls[ci] = 0
            run_start[ci] = tt[can]
        cnt[act], disc[act], lvl[act], reb[act] = c, d_, l_, r_
        coins[act] = co
        t[act] = tt
        done[act] = tt >= horizon

    return dict(
        profile=prof,
        policy=policy,
        mode=mode,
        sims=S,
        horizon=horizon,
        iterations=iters,
        reb_t=reb_t,
        reb_rolls=reb_rolls,
        ready_t=ready_t,
        reb_luck=reb_luck,
        reb_income=reb_income,
        reb_stamps=reb_stamps,
        reb_lvl=reb_lvl,
        disc_t=disc_t,
        disc_reb=disc_reb,
        run_seconds=spr_log,
        run_rolls=roll_log,
        run_announce=announce_log,
        final_luck=game.luck(lvl, game.stamps(disc), reb, lm),
        final_reb=reb,
        final_lvl=lvl,
        final_stamps=game.stamps(disc),
    )


# ---------------------------------------------------------------------------------------------
# reference per-roll simulator (independent scalar implementation, for --check)


def reference_sim(game: Game, prof: dict, seed: int, until_reb: int, policy: str, max_rolls: int = 400000) -> list:
    """Plain loop, one roll at a time; returns the times of rebirths 1..until_reb."""
    rng = np.random.default_rng(seed)
    cfg = game.cfg
    M = game.M
    cnt = [0] * M
    disc = [False] * M
    lvl = [0, 0, 0, 0]
    coins, reb, t = 0.0, 0, 0.0
    times = []
    stamp_members = [np.flatnonzero(game.region_members[r]) for r in range(len(game.regions))]
    thr = list(game.star_thr)

    def luck_now():
        stamps = sum(1 for mem in stamp_members if len(mem) and all(disc[i] for i in mem))
        return (
            cfg["base_luck"]
            * (1 + game.up_per[G] * lvl[G])
            * (1 + cfg["region_luck_bonus"] * stamps)
            * game.RL[reb]
            * prof["luck_mult"]
        )

    def income_now(lv=None):
        lv = lv or lvl
        slots = min(cfg["base_slots"] + game.up_per[P] * lv[P], game.max_slots)
        total, shown = 0.0, 0
        for i in range(M):  # rarest first
            if cnt[i] > 0:
                if shown >= slots:
                    break
                shown += 1
                stars = sum(1 for x in thr if cnt[i] >= x)
                total += game.item_income[i] * (1 + game.star_bonus * (stars - 1))
        return total * (1 + game.up_per[T] * lv[T]) * game.RI[reb] * prof["income_mult"]

    cache_key, cdf, n_rolls = None, None, 0
    inc = 0.0
    u = rng.random(max_rolls)
    ub = rng.random(max_rolls)
    while reb < until_reb and n_rolls < max_rolls:
        L = luck_now()
        key = (round(L, 12),)
        if key != cache_key:
            ps = [(game.probs(np.array([L * m]))[0], w) for m, w in prof["mix"]]
            cache_key = key
            cdfs = [(np.cumsum(pp), w) for pp, w in ps]
        # choose boost state then outcome
        acc, cdf = 0.0, cdfs[-1][0]
        for cc, w in cdfs:
            acc += w
            if ub[n_rolls] < acc:
                cdf = cc
                break
        i = int(np.searchsorted(cdf, u[n_rolls] * cdf[-1], side="right"))
        i = min(i, M - 1)
        n_rolls += 1
        cd = cfg["roll_cooldown"] * (1 - game.up_per[A] * lvl[A]) * prof["cd_mult"]
        dt = max(cd, game.overhead[i])
        coins += inc * dt  # income during this roll's period (state before the result)
        t += dt
        if not disc[i]:
            coins += game.bonus[i]
            disc[i] = True
        cnt[i] += 1
        inc = income_now()
        # purchases
        C = game.reb_coins[reb]
        req = np.flatnonzero(game.reb_req[reb])
        req_ok = all(cnt[j] > 0 for j in req)
        saving = policy == "ready" and req_ok and reb < game.max_reb
        while True:
            owned_n = sum(1 for x in cnt if x > 0)
            slots = min(cfg["base_slots"] + game.up_per[P] * lvl[P], game.max_slots)
            options = []
            for k in range(4):
                price = game.price[k, lvl[k]]
                if not np.isfinite(price):
                    continue
                if k == P and not (owned_n > slots and slots < game.max_slots):
                    continue
                if saving:
                    if k in (G, A) or coins >= C:
                        continue
                    lv2 = list(lvl)
                    lv2[k] += 1
                    if not ((C - coins + price) / income_now(lv2) < (C - coins) / inc):
                        continue
                options.append((price, k))
            if not options:
                break
            price, k = min(options)
            if price > coins:
                break
            coins -= price
            lvl[k] += 1
            inc = income_now()
        if reb < game.max_reb and req_ok and coins >= C:
            reb += 1
            times.append(t)
            cnt = [0] * M
            lvl = [0, 0, 0, 0]
            coins = 0.0
            inc = 0.0
    return times


# ---------------------------------------------------------------------------------------------
# reporting helpers


def fmt_dur(sec: float) -> str:
    if sec is None or not np.isfinite(sec):
        return "—"
    if sec < 90:
        return f"{sec:.0f} s"
    if sec < 90 * MINUTE:
        return f"{sec / MINUTE:.0f} min"
    if sec < 48 * HOUR:
        return f"{sec / HOUR:.1f} h"
    return f"{sec / DAY:.1f} d"


def fmt_num(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "—"
    for unit, v in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(x) >= v:
            return f"{x / v:.3g}{unit}"
    return f"{x:.3g}"


def cq(x: np.ndarray, q: float) -> float:
    """Quantile treating NaN (not reached within the horizon) as +inf."""
    v = np.where(np.isnan(x), np.inf, x)
    v = np.sort(v)
    k = min(len(v) - 1, max(0, int(math.ceil(q * len(v))) - 1))
    return float(v[k])


def dur_cell(x: np.ndarray, horizon: float) -> str:
    med, lo, hi = cq(x, 0.5), cq(x, 0.1), cq(x, 0.9)
    if not np.isfinite(med):
        reached = np.isfinite(x).mean()
        return f">{fmt_dur(horizon)} ({reached:.0%} reach)"
    tail = fmt_dur(hi) if np.isfinite(hi) else f">{fmt_dur(horizon)}"
    return f"**{fmt_dur(med)}** ({fmt_dur(lo)}–{tail})"


def summarize(game: Game, res: dict) -> dict:
    """Numbers for JSON / comparisons."""
    R = game.max_reb
    out = {"rebirths": [], "tiers": []}
    for k in range(1, R + 1):
        x = res["reb_t"][:, k]
        prev = res["reb_t"][:, k - 1]
        out["rebirths"].append(
            dict(
                k=k,
                median_s=cq(x, 0.5),
                p10_s=cq(x, 0.1),
                p90_s=cq(x, 0.9),
                reached=float(np.isfinite(x).mean()),
                run_median_s=cq(x - prev, 0.5),
                rolls_median=cq(res["reb_rolls"][:, k], 0.5),
                luck_median=float(np.nanmedian(res["reb_luck"][:, k])) if np.isfinite(x).any() else None,
            )
        )
    for r in range(game.n_tiers):
        cols = game.rank == r + 1
        first = np.nanmin(np.where(np.isnan(res["disc_t"][:, cols]), np.inf, res["disc_t"][:, cols]), axis=1)
        first = np.where(np.isinf(first), np.nan, first)
        out["tiers"].append(dict(rank=r + 1, name=game.tier_names[r], median_s=cq(first, 0.5), reached=float(np.isfinite(first).mean())))
    return out


def tier_first(game: Game, res: dict, rank: int):
    cols = np.flatnonzero(game.rank == rank)
    dt = res["disc_t"][:, cols]
    has = ~np.isnan(dt)
    first = np.where(has.any(1), np.nanmin(np.where(has, dt, np.inf), axis=1), np.nan)
    arg = np.where(has.any(1), np.argmin(np.where(has, dt, np.inf), axis=1), -1)
    rb = np.array([res["disc_reb"][s, cols[a]] if a >= 0 else -1 for s, a in enumerate(arg)])
    return first, rb


def report(game: Game, results: dict, args, validation: str | None, elapsed: float) -> str:
    cfg = game.cfg
    lines = []
    title = cfg.get("variant_name") if cfg.get("variant_name") else "current game"
    lines.append(f"# Landmark RNG — progression simulation ({title})\n")
    lines.append(
        f"Generated by `tools/balance/sim.py` on {time.strftime('%Y-%m-%d')} — config source: `{cfg.get('source')}`"
        + (f", variant `{args.variant}`" if args.variant else " (src/shared/*.luau as committed)")
        + f". {args.sims} Monte-Carlo players per profile, seed {args.seed}, horizon {fmt_dur(args.horizon_days * DAY)} of"
        f" online play, window frac {args.frac}, policy `{args.policy}`, roll mode `{args.mode}`; {elapsed:.0f} s.\n"
    )
    if cfg.get("variant_notes"):
        lines.append(f"> {cfg['variant_notes']}\n")
    lines.append("Re-run: `python3 tools/balance/sim.py" + (f" --variant {args.variant}" if args.variant else "") + " --check`\n")
    lines.append("Cells: **median** (p10–p90) of cumulative online play time. `—` = not reached within the horizon.\n")

    # --- roll rate ---
    c = game.client
    lines.append("## Roll rate (AUTO)\n")
    lines.append(
        "AUTO sends the next roll only after the Fast reveal animation (Hud.reveal) and a 0.05 s loop wait, so the real period is "
        f"`max(cooldown, rtt + reveal(rank) + wait)` with rtt = {c['rtt']:.2f} s assumed and ~half a frame per `task.wait`.\n"
    )
    lines.append("| result rank | " + " | ".join(f"{r}" for r in range(1, game.n_tiers + 1)) + " |")
    lines.append("|---|" + "---|" * game.n_tiers)
    lines.append("| AUTO time per roll (s, cooldown aside) | " + " | ".join(f"{v:.2f}" for v in game.overhead_rank) + " |\n")
    p1 = game.probs(np.array([1.0]))[0]
    rows = []
    for lvl_a in (0, 2, 4, 6, 10):
        for fast, name in ((1.0, "no pass"), (cfg["passes"].get("FastRoll", {}).get("cooldown_mult", 1), "FastRoll")):
            cd = cfg["roll_cooldown"] * (1 - game.up_per[A] * lvl_a) * fast
            auto = float((p1 * np.maximum(cd, game.overhead)).sum())
            rows.append(f"| {lvl_a} | {name} | {cd:.2f} | {auto:.2f} | {3600 / auto:.0f} |")
    lines.append("| Agency lvl | pass | cooldown (s) | AUTO s/roll @luck 1 | rolls/h |")
    lines.append("|---|---|---|---|---|")
    lines.extend(rows)
    lines.append("")

    # --- timeline ---
    profiles = list(results)
    R = game.max_reb
    lines.append("## Rebirth timeline\n")
    for name in profiles:
        res = results[name]
        prof = res["profile"]
        passes = ", ".join(prof["passes"]) or "none"
        lines.append(
            f"### {name} player — passes: {passes}; LuckBoost {prof['boost_per_day']:g}/day"
            f" ({prof['boost_duty']:.1%} of time); server luck {prof['server_luck_duty']:.0%} of time"
            + (f"; CoinPack {prof['coinpacks_per_day']:g}/day" if prof["coinpacks_per_day"] else "")
            + "\n"
        )
        lines.append(
            "| # | needs | cumulative time | this run | of which hunting landmarks | rolls (cum.) | luck at rebirth | income/s at rebirth | stamps |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for k in range(1, R + 1):
            step = cfg["rebirths"][k - 1]
            needs = f"{fmt_num(step['coins'])} + " + ", ".join(step["landmarks"])
            x = res["reb_t"][:, k]
            prev = res["reb_t"][:, k - 1]
            run = x - prev
            hunt = res["ready_t"][:, k - 1] - prev
            ok = np.isfinite(x)
            lines.append(
                f"| {k} | {needs} | {dur_cell(x, res['horizon'])} | {fmt_dur(cq(run, 0.5))} | {fmt_dur(cq(hunt, 0.5))} |"
                f" {fmt_num(cq(res['reb_rolls'][:, k], 0.5))} |"
                f" {np.nanmedian(res['reb_luck'][ok, k]) if ok.any() else float('nan'):.2f} |"
                f" {fmt_num(np.nanmedian(res['reb_income'][ok, k])) if ok.any() else '—'} |"
                f" {np.nanmedian(res['reb_stamps'][ok, k]) if ok.any() else float('nan'):.0f} |"
            )
        final_luck = np.median(res["final_luck"])
        lines.append(
            f"\nAt the horizon: median rebirths {np.median(res['final_reb']):.0f}, luck (no boost) {final_luck:.1f},"
            f" stamps {np.median(res['final_stamps']):.0f}/{len(game.regions)}, Globe lvl {np.median(res['final_lvl'][:, G]):.0f}."
            f" Simulation took {res['iterations']} vector steps.\n"
        )

    # --- tiers ---
    lines.append("## First discovery per tier (ever)\n")
    head = "| tier | 1-in range | p(roll) @luck 1 |" + "".join(f" {n}: time | {n}: at rebirth # |" for n in profiles)
    lines.append(head)
    lines.append("|---|---|---|" + "---|---|" * len(profiles))
    for r in range(1, game.n_tiers + 1):
        cols = game.rank == r
        if not cols.any():
            continue
        rng_txt = f"{fmt_num(game.N[cols].min())}–{fmt_num(game.N[cols].max())}"
        cells = ""
        for name in profiles:
            first, rb = tier_first(game, results[name], r)
            med_rb = np.median(rb[rb >= 0]) if (rb >= 0).any() else float("nan")
            cells += f" {dur_cell(first, results[name]['horizon'])} | {med_rb:.0f} |" if np.isfinite(med_rb) else f" {dur_cell(first, results[name]['horizon'])} | — |"
        lines.append(f"| {r} {game.tier_names[r - 1]} ({cols.sum()}) | {rng_txt} | {p1[cols].sum():.3g} |{cells}")
    lines.append("")
    rare_idx = 0  # rarest landmark
    for name in profiles:
        res = results[name]
        got = np.isfinite(res["disc_t"][:, rare_idx]).mean()
        lines.append(f"- {name}: rarest `{game.ids[rare_idx]}` (1 in {fmt_num(game.N[rare_idx])}) found within the horizon by {got:.0%} of players.")
    lines.append("")

    # --- endgame analytic ---
    lines.append("## Endgame odds (analytic from a state)\n")
    lines.append(
        "`simulated` = each player's state at the horizon (median over players); `max` = theoretical cap"
        " (last rebirth, Globe and Agency maxed, every stamp). Expected online time until the first such roll.\n"
    )
    lines.append("| profile | state | luck | AUTO s/roll | rolls/day | tier 6 any | tier 7 any | rarest | announce/h |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    max_stamps = int((game.region_required > 0).sum())
    for name in profiles:
        res = results[name]
        prof = res["profile"]
        states = {
            "simulated": (res["final_luck"], res["final_lvl"][:, A]),
            "max": (
                np.array([cfg["base_luck"] * (1 + game.up_per[G] * game.up_max[G]) * (1 + cfg["region_luck_bonus"] * max_stamps)
                          * game.RL[R] * prof["luck_mult"]]),
                np.array([game.up_max[A]]),
            ),
        }
        for label, (luck, lvl_a) in states.items():
            p = sum(game.probs(luck * m) * w for m, w in prof["mix"])
            cd = cfg["roll_cooldown"] * (1 - game.up_per[A] * lvl_a) * prof["cd_mult"]
            period = np.maximum(cd[:, None], game.overhead[None, :]) if args.mode == "auto" else cd[:, None]
            spr = (p * period).sum(1)
            cells = []
            for mask in (game.rank == 6, game.rank == 7, np.arange(game.M) == 0):
                pr = p[:, mask].sum(1)
                cells.append(fmt_dur(float(np.median(np.where(pr > 0, spr / np.maximum(pr, 1e-300), np.inf)))))
            ann = float(np.median(p[:, game.announce].sum(1) * 3600 / spr))
            lines.append(
                f"| {name} | {label} | {np.median(luck):.1f} | {np.median(spr):.2f} | {fmt_num(DAY / np.median(spr))} |"
                f" {cells[0]} | {cells[1]} | {cells[2]} | {ann:.0f} |"
            )
    lines.append("")

    # --- stamp blockers ---
    stamp_cols = np.flatnonzero(game.rank <= cfg["stamp_max_rank"])
    lines.append("## Passport-stamp blockers (landmarks never discovered by the horizon)\n")
    lines.append(
        "A roll never reaches a landmark once luck ≥ the 1-in of a rarer one (RollLogic tests rarest first and stops at the first"
        " success), so commons whose 1-in is below the player's luck become unobtainable — and a continent stamp needs *every*"
        f" landmark of rank ≤ {cfg['stamp_max_rank']} in it.\n"
    )
    any_row = False
    for name in profiles:
        res = results[name]
        missing = np.isnan(res["disc_t"][:, stamp_cols]).mean(0)
        bad = [(stamp_cols[i], missing[i]) for i in np.argsort(-missing) if missing[i] >= 0.05]
        if bad:
            any_row = True
            txt = ", ".join(
                f"`{game.ids[i]}` (1 in {fmt_num(game.N[i])}, {game.regions[int(np.argmax(game.region_members[:, i]))]}) {m:.0%}"
                for i, m in bad[:10]
            )
            lines.append(f"- {name}: {txt}")
        stamps = res["final_stamps"]
        lines.append(
            f"- {name}: stamps at the horizon — median {np.median(stamps):.0f}/{max_stamps}, all {max_stamps}: {(stamps == max_stamps).mean():.0%} of players."
        )
    if not any_row:
        lines.append("- every stamp landmark was found by ≥95% of players.")
    lines.append("")

    # --- announce rate by stage ---
    lines.append("## Server announcements (1 in ≥ %s) per hour of this player's rolling, by run\n" % fmt_num(cfg["announce_one_in"]))
    lines.append("| run (rebirths done) | " + " | ".join(profiles) + " |")
    lines.append("|---|" + "---|" * len(profiles))
    for k in range(0, R + 1):
        cells = []
        for name in profiles:
            res = results[name]
            sec = res["run_seconds"][:, k]
            ok = sec > 0
            cells.append(f"{np.median(res['run_announce'][ok, k] / sec[ok] * 3600):.2f}" if ok.any() else "—")
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    lines.append("")

    if validation:
        lines.append("## Validation\n")
        lines.append(validation)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------
# validation (--check)


def python_state_values(game: Game, st: dict) -> dict:
    cfg = game.cfg
    cnt = np.zeros((1, game.M), dtype=np.int64)
    inv = st["inventory"] if isinstance(st["inventory"], dict) else {}
    for k, v in inv.items():
        cnt[0, game.index[k]] = v
    disc = cnt > 0
    for k in st["discovered"] if isinstance(st["discovered"], dict) else {}:
        disc[0, game.index[k]] = True
    lvl = np.array([[st["upgrades"].get(u, 0) for u in UPGRADE_IDS]], dtype=np.int64)
    reb = np.array([st["rebirths"]])
    passes = st["passes"] if isinstance(st["passes"], dict) else {}
    luck_mult = cd_mult = inc_mult = 1.0
    for pid, pv in cfg["passes"].items():
        if passes.get(pid):
            luck_mult *= pv["luck_mult"]
            cd_mult *= pv["cooldown_mult"]
            inc_mult *= pv["income_mult"]
    boosts = st["boosts"] if isinstance(st["boosts"], dict) else {}
    for pid, pv in cfg["products"].items():
        if pv.get("seconds"):
            if pv.get("server_wide"):
                if st["server_luck"]:
                    luck_mult *= pv["luck_mult"]
            elif boosts.get(pid, 0) > 0:
                luck_mult *= pv["luck_mult"]
    stamps = game.stamps(disc)
    slots = game.slots(lvl[:, P])
    owned = np.flatnonzero(cnt[0] > 0)[: int(slots[0])]
    return dict(
        luck=float(game.luck(lvl, stamps, reb, luck_mult)[0]),
        cooldown=float(game.cooldown(lvl, cd_mult)[0]),
        income=float(game.income(cnt, lvl, reb, inc_mult)[0]),
        slots=float(slots[0]),
        park=[game.ids[i] for i in owned],
        stamps=int(stamps[0]),
    )


def validate(game: Game, args) -> str:
    out = []
    if not LUAURUN.exists():
        return "luaurun not built — Luau cross-checks skipped.\n"
    v = _run_luau("validate", "60", "300000")
    # 1) formulas vs PlayerState
    worst = 0.0
    mism = 0
    for st in v["states"]:
        py = python_state_values(game, st)
        for key in ("luck", "cooldown", "income", "slots"):
            a, b = py[key], float(st[key])
            rel = abs(a - b) / max(1e-12, abs(b))
            worst = max(worst, rel)
            mism += rel > 1e-9
        if py["park"] != list(st["park"]):
            mism += 1
        if py["stamps"] != len(st["completed_regions"]):
            mism += 1
    stamp_states = sum(1 for st in v["states"] if len(st["completed_regions"]) > 0)
    out.append(
        f"- **Formula port vs Luau `PlayerState`** ({len(v['states'])} random states incl. {stamp_states} with passport stamps,"
        f" passes, boosts, server luck): luck / cooldown / incomePerSecond / slots / park order / completedRegions —"
        f" {mism} mismatches, worst relative error {worst:.1e}."
    )
    # 2) probabilities vs RollLogic.probabilities
    worst = 0.0
    for entry in v["probabilities"]:
        py = game.probs(np.array([entry["luck"]]))[0]
        lua = np.array([entry["p"][i] for i in game.ids])
        worst = max(worst, float(np.abs(py - lua).max()))
    out.append(f"- **Roll probabilities vs `RollLogic.probabilities`** at luck 1, 3.7, 50, 1234, 250000: max abs diff {worst:.1e}.")
    # 3) Luau RollLogic.roll Monte Carlo vs analytic, per tier
    out.append("- **First-roll distribution**: Luau `RollLogic.roll` Monte Carlo (math.random) vs analytic, by tier:\n")
    out.append("  | luck | tier | analytic | Luau MC | z |")
    out.append("  |---|---|---|---|---|")
    for entry in v["monte_carlo"]:
        n = entry["rolls"]
        py = game.probs(np.array([entry["luck"]]))[0]
        counts = np.array([entry["counts"].get(i, 0) for i in game.ids]) if isinstance(entry["counts"], dict) else np.zeros(game.M)
        for r in range(1, game.n_tiers + 1):
            cols = game.rank == r
            pa = py[cols].sum()
            obs = counts[cols].sum() / n
            z = (obs - pa) / math.sqrt(max(pa * (1 - pa) / n, 1e-300))
            out.append(f"  | {entry['luck']:g} | {r} | {pa:.5f} | {obs:.5f} | {z:+.1f} |")
    bonus_ok = all(game.bonus[game.index[k]] == b for k, b in v["discovery_bonus"].items())
    out.append(f"\n- **Discovery bonus** ceil({game.cfg['discovery_bonus_mult']}·√N) matches `PlayerState.discoveryBonus` for all {len(v['discovery_bonus'])}: {bonus_ok}.")
    # 4) regex loader agrees with luaurun loader
    try:
        rx = parse_luau_regex()
        cur = _run_luau("config")
        same = (
            [(x["id"], float(x["one_in"]), x["region"]) for x in rx["landmarks"]]
            == [(x["id"], float(x["one_in"]), x["region"]) for x in cur["landmarks"]]
            and rx["rebirths"] == [{"coins": float(s["coins"]), "landmarks": s["landmarks"]} for s in cur["rebirths"]]
            and all(rx["upgrades"][u] == {k: float(v) if k != "max_level" else int(v) for k, v in cur["upgrades"][u].items()} for u in UPGRADE_IDS)
            and rx["passes"] == {k: {kk: float(vv) for kk, vv in v_.items()} for k, v_ in cur["passes"].items()}
        )
        out.append(f"- **Regex fallback loader == luaurun loader** (landmarks, rebirth steps, upgrades, passes): {same}.")
    except Exception as exc:  # noqa: BLE001
        out.append(f"- Regex fallback loader failed: {exc}")
    # 5) windowed sim vs per-roll reference (early game, where windows are most delicate)
    n_ref = args.check_ref_sims
    until = 3
    prof = make_profile(game, "free", 0.0, 0.0, 0.0)
    t0 = time.time()
    ref = [reference_sim(game, prof, 1000 + s, until, args.policy) for s in range(n_ref)]
    ref = np.array([x + [np.nan] * (until - len(x)) for x in ref])
    ref_s = time.time() - t0
    fast = simulate(game, prof, max(200, n_ref), args.seed + 7, 40 * DAY, args.frac, args.policy, "auto")
    fine = simulate(game, prof, max(200, n_ref), args.seed + 8, 40 * DAY, args.frac / 4, args.policy, "auto")
    out.append(
        f"\n- **Windowed Monte Carlo vs exact per-roll loop** (free player, policy `{args.policy}`; reference = {n_ref} players"
        f" simulated one roll at a time, {ref_s:.0f} s), median time to rebirth k:\n"
    )
    out.append(f"  | k | per-roll reference | sim (frac {args.frac}) | sim (frac {args.frac / 4:g}) |")
    out.append("  |---|---|---|---|")
    for k in range(1, until + 1):
        out.append(
            f"  | {k} | {fmt_dur(cq(ref[:, k - 1], 0.5))} | {fmt_dur(cq(fast['reb_t'][:, k], 0.5))} | {fmt_dur(cq(fine['reb_t'][:, k], 0.5))} |"
        )
    out.append(
        f"\n  Later rebirths, window-size sensitivity (frac {args.frac} vs {args.frac / 4:g}): "
        + ", ".join(
            f"#{k} {fmt_dur(cq(fast['reb_t'][:, k], 0.5))} vs {fmt_dur(cq(fine['reb_t'][:, k], 0.5))}"
            for k in range(4, game.max_reb + 1)
            if np.isfinite(cq(fine["reb_t"][:, k], 0.5)) or np.isfinite(cq(fast["reb_t"][:, k], 0.5))
        )
        + "."
    )
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", help="variant JSON patch (see docstring)")
    ap.add_argument("--source", default="auto", choices=["auto", "luaurun", "regex"])
    ap.add_argument("--sims", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--horizon-days", type=float, default=120.0, help="online play time simulated per player")
    ap.add_argument("--frac", type=float, default=0.02, help="window = frac * rolls this run (adaptive)")
    ap.add_argument("--policy", default="ready", choices=["ready", "greedy"])
    ap.add_argument("--mode", default="auto", choices=["auto", "ideal"])
    ap.add_argument("--players", default="free,paid", help="comma list of free,paid")
    ap.add_argument("--paid-boosts-per-day", type=float, default=1.0, help="15-min LuckBoosts per day of play (paid)")
    ap.add_argument("--server-luck-duty", type=float, default=0.0, help="fraction of time a ServerLuck is running")
    ap.add_argument("--paid-coinpacks-per-day", type=float, default=0.0)
    ap.add_argument("--rtt", type=float, default=None, help="override network round trip (s)")
    ap.add_argument("--out", default=None, help="markdown output (default balance/sim_current.md or sim_<variant>.md)")
    ap.add_argument("--json", default=None, help="summary JSON output (default next to --out)")
    ap.add_argument("--check", action="store_true", help="run validation against the Luau code")
    ap.add_argument("--check-ref-sims", type=int, default=40)
    ap.add_argument("--dump-config", action="store_true")
    args = ap.parse_args()

    cfg = load_current(args.source)
    if args.variant:
        with open(args.variant, encoding="utf-8") as fh:
            cfg = apply_variant(cfg, json.load(fh))
    if args.rtt is not None:
        cfg["client"]["rtt"] = args.rtt
    if args.dump_config:
        print(json.dumps(cfg, ensure_ascii=False, indent=1))
        return
    game = Game(cfg)
    started = time.time()
    results = {}
    for kind in [x.strip() for x in args.players.split(",") if x.strip()]:
        prof = make_profile(
            game,
            kind,
            args.paid_boosts_per_day if kind == "paid" else 0.0,
            args.server_luck_duty,
            args.paid_coinpacks_per_day if kind == "paid" else 0.0,
        )
        t0 = time.time()
        results[kind] = simulate(game, prof, args.sims, args.seed, args.horizon_days * DAY, args.frac, args.policy, args.mode)
        print(f"[sim] {kind}: {time.time() - t0:.1f} s, {results[kind]['iterations']} steps", file=sys.stderr)
    validation = validate(game, args) if args.check else None
    elapsed = time.time() - started
    md = report(game, results, args, validation, elapsed)
    if args.out is None:
        stem = "sim_current" if not args.variant else "sim_" + Path(args.variant).stem.replace("variant_", "")
        args.out = str(ROOT / "balance" / f"{stem}.md")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md, encoding="utf-8")
    json_path = args.json or str(Path(args.out).with_suffix(".json"))
    summary = {
        "variant": cfg.get("variant_name", "current"),
        "args": vars(args),
        "profiles": {k: summarize(game, v) for k, v in results.items()},
    }
    Path(json_path).write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
