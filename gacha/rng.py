"""뽑기 판정.

천장 카운터는 배너 "계열"별로 쌓인다(한정끼리 공유 / 상시 별도).
판정 순서는 확률 공시 화면과 동일하다: 5★ → 4★(10회 보장 포함) → 3★.
"""

from __future__ import annotations

import random

from . import econ
from .content import BY_RARITY


def pity_key(banner: dict) -> str:
    return "limited" if banner["kind"] == "limited" else "standard"


def new_pity() -> dict:
    return {"c5": 0, "c4": 0, "g5": False}


def _pick(pool: list[str], rng: random.Random) -> str:
    return pool[rng.randrange(len(pool))]


def draw_one(banner: dict, pity: dict, rng: random.Random) -> dict:
    """한 번 뽑고 pity 를 제자리에서 갱신한다."""
    pity["c5"] += 1
    pity["c4"] += 1

    p5 = econ.pity_rate5(pity["c5"])
    roll = rng.random()

    if roll < p5:
        rarity = 5
        pity["c5"] = 0
        pity["c4"] = 0
    elif pity["c4"] >= econ.PITY_4 or roll < p5 + econ.RATE_4:
        rarity = 4
        pity["c4"] = 0
    else:
        rarity = 3

    pickup = False
    if rarity == 5:
        pool_up = banner["pickup5"]
        if pool_up:
            if pity["g5"] or rng.random() < econ.PICKUP_RATE_5:
                cid, pickup = _pick(pool_up, rng), True
                pity["g5"] = False
            else:
                rest = [c for c in BY_RARITY[5] if c not in pool_up]
                cid = _pick(rest or pool_up, rng)
                pity["g5"] = True
        else:
            cid = _pick(BY_RARITY[5], rng)
    elif rarity == 4:
        pool_up = banner["pickup4"]
        if pool_up and rng.random() < econ.PICKUP_RATE_4:
            cid, pickup = _pick(pool_up, rng), True
        else:
            rest = [c for c in BY_RARITY[4] if c not in pool_up]
            cid = _pick(rest or BY_RARITY[4], rng)
    else:
        cid = _pick(BY_RARITY[3], rng)

    return {"char": cid, "rarity": rarity, "pickup": pickup}


def draw(banner: dict, pity: dict, count: int, rng: random.Random) -> list[dict]:
    return [draw_one(banner, pity, rng) for _ in range(count)]
