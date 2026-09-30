#!/usr/bin/env python3
"""balance/variant_rec.json(최종안)의 명소 확률·등급 경계를 src/shared/Landmarks.luau 에 옮겨 적고, 게임 숫자가
최종안과 같은지 확인합니다. 150개 확률을 손으로 옮기지 않으려고 만든 스크립트.

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/apply_rec.py            # Landmarks.luau 의 N(DEFINITIONS 4번째 값)·Tiers.MinOneIn 고쳐 쓰기 + 확인
  python3 tools/balance/apply_rec.py --check    # 쓰지 않고 확인만

확인하는 것:
  1. 150개 명소가 모두 최종안에 있고, 확률(N) 순서가 예전과 같음(동점 없음) — 굴림 순서·도감 순서가 그대로.
  2. 모든 명소의 등급이 예전과 같음(예전 N·예전 경계 vs 새 N·새 경계) — 색·수입 등급·여권 도장 대상이 그대로.
  3. (--check 또는 쓴 뒤) 실제 Luau 모듈을 불러온 게임 숫자(tools/balance/dump.luau)가 최종안을 적용한 숫자와 같음:
     명소 확률, 등급 경계, 등급 수입, 환생 표·행운 규칙, 속보/홀로그램 기준, 별 기준·보너스, 규칙(자동 발견·짧은 연출).
     Config.luau 는 손으로 고친 뒤 여기서 대조합니다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim as S  # noqa: E402

ROOT = S.ROOT
LANDMARKS = ROOT / "src" / "shared" / "Landmarks.luau"
REC = ROOT / "balance" / "variant_rec.json"

ROW = re.compile(r'^(\s*\{\s*"(\w+)",\s*"[^"]*",\s*"[^"]*",\s*)(\d+)(,\s*"\w+")', re.M)
TIER = re.compile(r'(\{\s*Rank\s*=\s*(\d+),\s*Name\s*=\s*"[^"]*",\s*MinOneIn\s*=\s*)(\d+)')


def tier_of(n: float, mins: list[float]) -> int:
    rank = 1
    for i, m in enumerate(mins, 1):
        if n >= m:
            rank = i
    return rank


def rewrite(text: str, rec: dict) -> tuple[str, list[str]]:
    new_n = {k: int(v) for k, v in rec["landmarks"].items()}
    new_min = {int(t["rank"]): int(t["minOneIn"]) for t in rec["tiers"]}
    old_n = {m.group(2): int(m.group(3)) for m in ROW.finditer(text)}
    old_min = {int(m.group(2)): int(m.group(3)) for m in TIER.finditer(text)}
    problems = []
    if set(old_n) != set(new_n):
        problems.append(f"명소 Id 가 다름: 게임에만 {sorted(set(old_n) - set(new_n))}, 최종안에만 {sorted(set(new_n) - set(old_n))}")
        return text, problems
    if sorted(old_min) != sorted(new_min):
        problems.append(f"등급 수가 다름: {sorted(old_min)} vs {sorted(new_min)}")
        return text, problems
    # 1) 순서
    by_old = sorted(old_n, key=lambda i: old_n[i])
    by_new = sorted(new_n, key=lambda i: new_n[i])
    if by_old != by_new:
        moved = [i for i, (a, b) in enumerate(zip(by_old, by_new)) if a != b]
        problems.append(f"확률 순서가 바뀜 (처음 다른 자리 {moved[:5]}: {by_old[moved[0]]} vs {by_new[moved[0]]})")
    if len(set(new_n.values())) != len(new_n):
        problems.append("같은 확률(N)이 둘 이상 — 굴림 순서가 정렬에 따라 달라질 수 있음")
    # 2) 등급
    om = [old_min[r] for r in sorted(old_min)]
    nm = [new_min[r] for r in sorted(new_min)]
    for lm_id in by_old:
        a, b = tier_of(old_n[lm_id], om), tier_of(new_n[lm_id], nm)
        if a != b:
            problems.append(f"{lm_id}: 등급 {a} -> {b} (N {old_n[lm_id]:,} -> {new_n[lm_id]:,})")
    text = ROW.sub(lambda m: f"{m.group(1)}{new_n[m.group(2)]}{m.group(4)}", text)
    text = TIER.sub(lambda m: f"{m.group(1)}{new_min[int(m.group(2))]}", text)
    return text, problems


def compare_game(rec: dict) -> list[str]:
    """실제 Luau 모듈(dump.luau) 숫자 vs 최종안을 적용한 숫자."""
    game = S.load_current("luaurun")
    want = S.apply_variant(S.load_current("luaurun"), rec)
    problems = []

    def same(label, a, b):
        if a != b:
            problems.append(f"{label}: 게임 {a} / 최종안 {b}")

    have = {x["id"]: float(x["one_in"]) for x in game["landmarks"]}
    need = {x["id"]: float(x["one_in"]) for x in want["landmarks"]}
    diff = [f"{i} {have.get(i, 0):,.0f} (최종안 {need.get(i, 0):,.0f})" for i in sorted(set(have) | set(need)) if have.get(i) != need.get(i)]
    if diff:
        problems.append(f"명소 확률 {len(diff)}개 다름: " + ", ".join(diff[:8]) + (" …" if len(diff) > 8 else ""))
    same("등급 경계", [float(t["min_one_in"]) for t in game["tiers"]], [float(t["min_one_in"]) for t in want["tiers"]])
    same("등급 수입", [float(x) for x in game["tier_income"]], [float(x) for x in want["tier_income"]])
    same(
        "환생 표",
        [(float(s["coins"]), list(s["landmarks"])) for s in game["rebirths"]],
        [(float(s["coins"]), list(s["landmarks"])) for s in want["rebirths"]],
    )
    same("환생 수", game["max_rebirths"], want["max_rebirths"])
    same("환생 행운", {k: float(v) if k != "type" else v for k, v in game["rebirth_luck"].items()}, want["rebirth_luck"])
    same("환생 수입", {k: float(v) if k != "type" else v for k, v in game["rebirth_income"].items()}, want["rebirth_income"])
    same("속보 기준", float(game["announce_one_in"]), float(want["announce_one_in"]))
    same("홀로그램 기준", float(game["hologram_one_in"]), float(want["hologram_one_in"]))
    same("별 기준", [float(x) for x in game["star_thresholds"]], [float(x) for x in want["star_thresholds"]])
    same("별 보너스", float(game["star_income_bonus"]), float(want["star_income_bonus"]))
    same("발견 보너스", float(game["discovery_bonus_mult"]), float(want["discovery_bonus_mult"]))
    for key in ("auto_discover_below_luck", "short_reveal_known", "short_reveal_rank"):
        same(f"규칙 {key}", game["rules"].get(key), want["rules"].get(key, game["rules"].get(key)))
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="쓰지 않고 확인만")
    args = ap.parse_args()
    rec = json.loads(REC.read_text(encoding="utf-8"))
    text = LANDMARKS.read_text(encoding="utf-8")
    new_text, problems = rewrite(text, rec)
    changed = sum(1 for a, b in zip(ROW.finditer(text), ROW.finditer(new_text)) if a.group(3) != b.group(3))
    if problems and not args.check:
        print("\n".join(["고쳐 쓰지 않음:"] + problems))
        sys.exit(1)
    if not args.check and new_text != text:
        LANDMARKS.write_text(new_text, encoding="utf-8")
        print(f"Landmarks.luau: 명소 확률 {changed}개, 등급 경계 고쳐 씀")
    elif args.check:
        print(f"Landmarks.luau 와 최종안이 다른 명소 확률: {changed}개")
    ok = not problems
    print(f"순서·등급 확인 ({len(list(ROW.finditer(text)))}개): " + ("같음" if ok else "\n  " + "\n  ".join(problems)))
    game_problems = compare_game(rec)
    print("게임 숫자 vs 최종안: " + ("모두 같음" if not game_problems else "\n  " + "\n  ".join(game_problems)))
    sys.exit(0 if ok and not game_problems else 1)


if __name__ == "__main__":
    main()
