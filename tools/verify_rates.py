"""뽑기 확률 검증 — 공시값(econ.EFFECTIVE_RATE_*)이 실제 구현과 일치하는지 확인.

  python tools/verify_rates.py

마르코프 연쇄 정상분포로 종합 확률을 계산하고, 별도로 몬테카를로
시뮬레이션을 돌려 두 값이 일치하는지 본다. 확률 공시는 실제 적용값과
같아야 하므로(게임산업법), 배너·확률 상수를 바꾸면 이 스크립트를 다시 돌린다.
"""

from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gacha import econ, rng  # noqa: E402

TOL = 0.0005  # 허용 오차(절대값, 확률 단위)


def markov() -> tuple[float, float]:
    """상태 (5★ 카운터, 4★ 카운터) 위의 정상분포에서 종합 확률을 구한다."""
    dist = {(0, 0): 1.0}
    r5 = r4 = 0.0
    for _ in range(4000):
        nxt: dict[tuple[int, int], float] = {}
        r5 = r4 = 0.0
        for (c5, c4), w in dist.items():
            p5 = econ.pity_rate5(c5 + 1)
            p4 = 1.0 if c4 + 1 >= econ.PITY_4 else econ.RATE_4
            p4 = max(0.0, min(p4, 1.0 - p5))
            p3 = 1.0 - p5 - p4
            r5 += w * p5
            r4 += w * p4
            n5 = min(c5 + 1, econ.HARD_PITY - 1)
            for key, p in (((0, 0), p5), ((n5, 0), p4),
                           ((n5, min(c5 + 1, c4 + 1)), p3)):
                if p > 0:
                    nxt[key] = nxt.get(key, 0.0) + w * p
        total = sum(nxt.values())
        dist = {k: v / total for k, v in nxt.items()}
    return r5, r4


def monte_carlo(n: int = 400_000, seed: int = 20260908) -> tuple[float, float, int]:
    banner = econ.BANNER_BY_ID["standard"]
    pity = rng.new_pity()
    r = random.Random(seed)
    c = Counter()
    since = worst = 0
    for _ in range(n):
        res = rng.draw_one(banner, pity, r)
        c[res["rarity"]] += 1
        since += 1
        if res["rarity"] == 5:
            worst = max(worst, since)
            since = 0
    return c[5] / n, c[4] / n, worst


def main() -> int:
    m5, m4 = markov()
    s5, s4, worst = monte_carlo()
    ok = True

    print("종합 확률 (천장·보장 포함)")
    for label, declared, exact, sim in (
        ("5★", econ.EFFECTIVE_RATE_5, m5, s5),
        ("4★", econ.EFFECTIVE_RATE_4, m4, s4),
    ):
        good = abs(declared - exact) <= TOL and abs(exact - sim) <= 3 * TOL
        ok &= good
        print(f"  {label}  공시 {declared * 100:7.4f}%   "
              f"이론 {exact * 100:7.4f}%   시뮬 {sim * 100:7.4f}%   "
              f"{'OK' if good else '불일치!'}")

    print(f"\n5★ 최대 미획득 구간: {worst}회 (하드 천장 {econ.HARD_PITY})")
    if worst > econ.HARD_PITY:
        print("  ! 천장을 넘겼습니다. 천장 로직을 확인하세요.")
        ok = False
    print(f"5★ 1개당 평균: {1 / m5:.2f}회 "
          f"(별가루 {int(1 / m5) * econ.PULL_COST:,})")
    print(f"\n{'검증 통과' if ok else '검증 실패 — 공시값을 수정하세요'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
