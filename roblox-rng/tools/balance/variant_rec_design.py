#!/usr/bin/env python3
"""추천안(variant_rec) 만들기 — 변형 A 를 바탕으로 목표 진행 속도에 맞게 다듬은 밸런스.

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/variant_rec_design.py            # balance/variant_rec.json 다시 쓰기
  python3 tools/balance/sim.py --variant balance/variant_rec.json          # 자세한 진행표 balance/sim_rec.md
  python3 tools/balance/compare.py                        # 지금 / A / B / 추천안 나란히 balance/sim_results.md

바탕: balance/variant_a.json (환생 행운 x2^r, 1~3등급 확률 그대로, N >= 1,000 은 log 공간에서 늘림, 가장 희귀 1/50억).
A 에서 바꾼 것(모두 sim.py 로 반복 측정해서 고름 — balance/sim_results.md 의 "반복 기록" 참고):
  1. 환생 1단계 코인 5,000 -> 100,000: 첫 환생 4분 -> 약 10분. 명소 조건(에펠탑·자유의 여신상)은 그대로.
     목표표의 "15~30분"과 "초반이 지금보다 느려지면 안 됨(첫 환생 시간 비슷하게)"이 서로 부딪혀서, 5·15·20·30·60분에
     찾은 명소 수가 모두 지금 이상으로 남는 가장 큰 값(10만)을 골랐음. 25만이면 약 15분이지만 15~20분 무렵 발견 수가
     지금보다 3~4개 적음(84 vs 88).
  2. 환생 5단계 코인 20억 -> 15억: 5번째 환생 29시간 -> 약 25시간("하루쯤" 목표 가운데).
  3. 환생 10단계 명소 샹그릴라(1/3.75억) -> 사하라 신기루 성(1/1.1억): 마지막 관문 하나의 기대 대기가
     무료 약 7.7일 -> 약 2.3일. 중앙값은 그대로(코인이 시계)지만 p90 이 31일 -> 24일로 줄어 "운 나쁜 사람만 한참 막힘"이
     사라짐. 샹그릴라·세계수는 선택 목표(꿈)로 남음.
  4. 뉴스 1,000,000 -> 25,000,000, 홀로그램 8,000,000 -> 100,000,000: 지금 클라 기준 플레이어 1명·1시간당 뉴스가
     후반 무료 약 0.3회 / 유료 약 0.6회(A 는 10 / 19회 — 서버 10명이면 1분에 몇 번).
  5. rules.autoDiscoverBelowLuck = true (코드 수정 필요): 영구 행운 >= N 인 미발견 명소는 발견 처리.
     A 의 JSON 에는 빠져 있었음(없으면 VIP 구매자 여권 도장 중앙값 0/5).
그대로 둔 것: 150개 명소 확률(A), 등급 경계 1/10/100/1,000/12,500/250,000/8,000,000, 등급 수입 1/2/5/12/35/120/500,
  환생 수입 +50%/회, 업그레이드·게임패스·상품(지구본 가격을 낮춰 보는 것도 시험했지만 15분 발견 수가 거의 안 바뀌어 뺌).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "balance" / "variant_a.json"
OUT = ROOT / "balance" / "variant_rec.json"

STEP_COINS = {1: 100_000, 5: 1_500_000_000}  # 환생 단계(1부터) -> 코인
STEP_LANDMARKS = {10: ["skyisland"]}  # 환생 단계 -> 필요한 명소
ANNOUNCE_ONE_IN = 25_000_000
HOLOGRAM_ONE_IN = 100_000_000
RULES = {"autoDiscoverBelowLuck": True}

NOTES = (
    "추천안 = 변형 A(환생 행운 x2^r, 1~3등급 확률 그대로, 1/1,000 이상은 희귀할수록 더 늘림, 가장 희귀 세계수 1/50억) + "
    "진행 속도 다듬기. 바꾼 것: 환생 1단계 코인 5천 -> 10만(첫 환생 약 10분, 초반 발견 속도는 지금 이상 — 15분을 원하면 25만), "
    "5단계 20억 -> 15억(5번째 약 하루), "
    "10단계 명소 샹그릴라 -> 사하라 신기루 성(1/1.1억, 마지막 관문 운 편차 줄임 — 샹그릴라·세계수는 꿈으로 남김), "
    "뉴스 >= 2,500만 / 홀로그램 >= 1억(후반 플레이어 1명당 뉴스 시간당 약 0.3회). "
    "같이 필요한 코드 수정: (1) PlayerState.luck 의 환생 배율 = 2^환생 수(+ '+20%' 표시 문구, 테스트). "
    "(2) 영구 행운(부스트 제외) >= N 인 미발견 명소 자동 발견(rules.autoDiscoverBelowLuck) — 없으면 VIP 구매자는 "
    "흔한 명소를 영영 못 얻어 여권 도장이 막힘. (3) Config/Landmarks 숫자(확률표·등급 경계·등급 수입·환생 표·뉴스/홀로그램). "
    "권장: AUTO 에서 이미 발견한 명소는 짧은 연출(후반 굴림이 4배 빨라짐 — 넣으면 세계수를 1/100억으로 올리고 뉴스 기준도 1억으로). "
    "근거·표: balance/sim_results.md, 재현: tools/balance/variant_rec_design.py + tools/balance/compare.py"
)


def build() -> dict:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    v = copy.deepcopy(base)
    v["name"] = "추천안 (A 바탕): 환생 행운 x2^r, 첫 환생 약 10분, 10번째 약 3주, 가장 희귀 1/50억"
    steps = v["rebirth"]["steps"]
    for k, coins in STEP_COINS.items():
        steps[k - 1]["coins"] = coins
    for k, ids in STEP_LANDMARKS.items():
        steps[k - 1]["landmarks"] = list(ids)
    v["announceOneIn"] = ANNOUNCE_ONE_IN
    v["hologramOneIn"] = HOLOGRAM_ONE_IN
    v["rules"] = dict(RULES)
    v["notes"] = NOTES
    # 순서: 읽기 좋게 이름 -> 규칙 -> 나머지
    ordered = {"name": v.pop("name"), "rules": v.pop("rules")}
    ordered.update(v)
    return ordered


def main() -> None:
    v = build()
    OUT.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    steps = v["rebirth"]["steps"]
    print(f"wrote {OUT.relative_to(ROOT)}")
    for k, st in enumerate(steps, 1):
        print(f"  step {k:2d}: {st['coins']:>16,} coins + {', '.join(st['landmarks'])}")


if __name__ == "__main__":
    main()
