#!/usr/bin/env python3
"""README.md 의 "명소 목록과 확률" 표(150줄)를 실제 Luau 모듈(tools/balance/dump.luau) 숫자로 다시 씁니다.

  python3 tools/balance/readme_table.py            # README.md 표 고쳐 쓰기
  python3 tools/balance/readme_table.py --check    # 표가 게임과 같은지만 확인(다르면 종료 코드 1)

칸: 명소 · 영문 · 지역 · 등급 · 표기 확률(Format.oneIn) · 실제 확률(행운 1, RollLogic.probabilities —
1/1,000 보다 흔하면 %, 아니면 1/N) · 발견 보너스(ceil(DISCOVERY_BONUS_MULT·√N)) · 기본 수입/초(별 0 기준 등급 수입).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim as S  # noqa: E402

README = S.ROOT / "README.md"
HEADER = "| 명소 | 영문 | 지역 | 등급 | 표기 확률 | 실제 확률 (행운 x1) | 발견 보너스 | 기본 수입/초 |"


def rows() -> list[str]:
    cfg = S.load_current("luaurun")
    game = S.Game(cfg)
    p = game.probs(np.array([1.0]))[0]
    by_id = {lm["id"]: lm for lm in cfg["landmarks"]}
    tiers = {t["rank"]: t["name"] for t in cfg["tiers"]}
    out = []
    for lm_id in reversed(game.ids):  # 흔한 것 -> 희귀한 것 (Landmarks.List)
        lm = by_id[lm_id]
        i = game.index[lm_id]
        n = int(lm["one_in"])
        region = cfg["region_info"][lm["region"]]
        real = f"{100 * p[i]:.2f}%" if n < 1000 else f"1/{round(1 / p[i]):,}"
        bonus = math.ceil(cfg["discovery_bonus_mult"] * n**0.5)
        income = cfg["tier_income"][int(lm["rank"]) - 1]
        out.append(
            f"| {lm['name']} | {lm['subtitle']} | {region['emoji']} {region['name']} | {tiers[int(lm['rank'])]} | 1 in {n:,} | {real} | {bonus:,} | {income:g} |"
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    lines = README.read_text(encoding="utf-8").split("\n")
    start = lines.index(HEADER) + 2  # 머리줄 + |---| 줄 다음
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    new = rows()
    if lines[start:end] == new:
        print("README 표 = 게임 숫자")
        return
    if args.check:
        print(f"README 표가 게임과 다름 ({sum(a != b for a, b in zip(lines[start:end], new))}줄)")
        sys.exit(1)
    lines[start:end] = new
    README.write_text("\n".join(lines), encoding="utf-8")
    print(f"README 표 {len(new)}줄 고쳐 씀")


if __name__ == "__main__":
    main()
