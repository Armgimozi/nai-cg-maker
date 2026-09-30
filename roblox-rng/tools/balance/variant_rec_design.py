#!/usr/bin/env python3
"""추천안(variant_rec) 만들기 — 변형 A 를 바탕으로 목표 진행 속도에 맞게 다듬은 밸런스.

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/variant_rec_design.py            # balance/variant_rec.json 다시 쓰기
  python3 tools/balance/sim.py --variant balance/variant_rec.json          # 자세한 진행표 balance/sim_rec.md
  python3 tools/balance/compare.py                        # 지금 / A / B / 추천안 나란히 balance/sim_results.md

바탕: balance/variant_a.json (환생 행운 x2^r, 1~3등급 확률 그대로, N >= 1,000 은 log 공간에서 늘림, 가장 희귀 1/50억).
A 에서 바꾼 것(모두 sim.py 로 반복 측정해서 고름 — balance/sim_results.md 의 "반복 기록" 참고):
  1. 환생 1단계 코인 5,000 -> 300,000: 첫 환생 4분 -> 약 17분(p10~p90 15~19분, 목표 15~30분 안). 명소 조건
     (에펠탑·자유의 여신상)은 그대로. 흔함·보통(1·2등급, 1/1~1/99) 발견 속도는 어느 값이든 지금과 똑같음(5분에 37개,
     10분에 38개 전부). 줄어드는 건 1/100 이상(3·4등급) 몇 개뿐: 15분 85 vs 88, 20분 91 vs 94, 30분 101 vs 102, 60분 114 = 114.
     (앞선 반복에서는 10만(약 10분, 어느 분에도 발견 수가 안 줄어듦)을 골랐지만, 그 값은 "15~30분"도 "지금과 비슷"도
     못 맞춰서 숫자 목표 쪽으로 옮김. 지금처럼 4분이 더 중요하면 5,000, 아무것도 안 줄이려면 100,000.)
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

구현 라운드(2026-09-30, 승인된 선택 — tools/balance/tune_final.py, balance/sim_results.md 8번):
  6. "자동 굴림 빠르게": AUTO 에서 이미 발견한 명소는 3등급처럼 짧은 연출(rules.shortRevealKnown, shortRevealRank 3
     = Config.AUTO_KNOWN_REVEAL_RANK). 후반 AUTO 가 시간당 약 600 -> 2,660번으로 빨라져서
     세계수 1/50억 -> 1/100억(최대 상태 기대 대기 무료 22.7일 / 유료 11.2일), 속보 2,500만 -> 1억,
     홀로그램 1억 -> 3.75억(후반 1인 시간당 속보 0.22 / 0.44, 홀로그램 0.05 / 0.1 = 승인안과 같은 빈도).
  7. 가챠식 별: 처음 발견 = 별 0, 중복마다 +1(최대 5) -> STAR_THRESHOLDS {2, 3, 4, 5, 6}, 별 1개마다 수입 +30%
     (5성 = ×2.5). +50% 는 5번째 환생 15시간·10번째 13.9일로 목표보다 빨라서 낮춤. 환생 코인은 그대로.

9번 라운드(2026-09-30, "자동 굴림 빠르게"를 제대로 — tools/balance/tune_quick.py, balance/sim_results.md 9번):
  8. 3등급 짧은 연출도 왕복 포함 약 1.35초라 굴림 간격보다 길어서 여행사·빠른 굴림이 AUTO 를 못 빠르게 했음 ->
     AUTO 중 이미 발견한 명소는 결과 카드만 퐁(rules.quickRevealKnown = Config.AUTO_QUICK_REVEAL, 기다리지 않음) ->
     AUTO 속도 = 굴림 간격(후반 시간당 3,000 / 4,286 / 6,000 / 8,571번 = 없음 / 빠른 굴림 / 여행사 최대 / 둘 다).
     숫자 그대로면 3번째 1.8시간·5번째 15시간(목표보다 빠름) -> 환생 코인 다시: 1단계 30만 -> 40만(첫 환생 약 17분),
     2~5단계 약 ×2~2.7(3번째 약 2.8시간, 5번째 약 26시간), 6~10단계 약 ×1.4(10번째 약 23일) — 승인안의 진행 속도와 같음.
     속보 1억 -> 3.75억(샹그릴라·세계수 = 홀로그램과 같음. 1억이면 후반 1인 시간당 0.49 / 1.4번 — 승인안 0.22 / 0.44 의 2~3배).
     별 보너스·등급 수입·명소 확률(세계수 1/100억 — 스토어 그림)은 그대로.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "balance" / "variant_a.json"
OUT = ROOT / "balance" / "variant_rec.json"

# 환생 단계(1부터) -> 코인. 9번 라운드(빠른 결과): 30만·150만·2,500만·2.5억·15억·60억·130억·280억·650억·1,400억 에서
STEP_COINS = {
    1: 400_000,
    2: 4_000_000,
    3: 60_000_000,
    4: 500_000_000,
    5: 3_000_000_000,
    6: 9_000_000_000,
    7: 18_000_000_000,
    8: 40_000_000_000,
    9: 90_000_000_000,
    10: 200_000_000_000,
}
STEP_LANDMARKS = {10: ["skyisland"]}  # 환생 단계 -> 필요한 명소
ANNOUNCE_ONE_IN = 375_000_000  # 구현 라운드: 2,500만 -> 1억, 9번 라운드(빠른 결과): 1억 -> 3.75억(= 홀로그램)
HOLOGRAM_ONE_IN = 375_000_000  # 구현 라운드: 1억 -> 3.75억(샹그릴라·세계수)
LANDMARKS = {"worldtree": 10_000_000_000}  # 구현 라운드: 1/50억 -> 1/100억
# 9번 라운드: AUTO 에서 이미 발견한 명소 = 결과 카드만 퐁(Config.AUTO_QUICK_REVEAL). 예전 3등급 짧은 연출(shortReveal)은 끔
RULES = {"autoDiscoverBelowLuck": True, "shortRevealKnown": False, "quickRevealKnown": True}
STAR_THRESHOLDS = [2, 3, 4, 5, 6]  # 가챠식: 처음 = 별 0, 중복마다 +1
STAR_INCOME_BONUS = 0.3

NOTES = (
    "추천안 = 변형 A(환생 행운 x2^r, 1~3등급 확률 그대로, 1/1,000 이상은 희귀할수록 더 늘림, 가장 희귀 세계수 1/50억) + "
    "진행 속도 다듬기. 바꾼 것: 환생 1단계 코인 5천 -> 30만(첫 환생 약 17분 — 흔함·보통 발견 속도는 지금과 같고 15~20분 무렵 1/100 이상 명소가 2~3개 덜 나옴. 지금처럼 4분이면 5천, 아무것도 안 줄이려면 10만(약 10분)), "
    "5단계 20억 -> 15억(5번째 약 하루), "
    "10단계 명소 샹그릴라 -> 사하라 신기루 성(1/1.1억, 마지막 관문 운 편차 줄임 — 샹그릴라·세계수는 꿈으로 남김), "
    "뉴스 >= 2,500만 / 홀로그램 >= 1억(후반 플레이어 1명당 뉴스 시간당 약 0.3회). "
    "같이 필요한 코드 수정: (1) PlayerState.luck 의 환생 배율 = 2^환생 수(+ '+20%' 표시 문구, 테스트). "
    "(2) 영구 행운(부스트 제외) >= N 인 미발견 명소 자동 발견(rules.autoDiscoverBelowLuck) — 없으면 VIP 구매자는 "
    "흔한 명소를 영영 못 얻어 여권 도장이 막힘. (3) Config/Landmarks 숫자(확률표·등급 경계·등급 수입·환생 표·뉴스/홀로그램). "
    "권장: AUTO 에서 이미 발견한 명소는 짧은 연출(후반 굴림이 4배 빨라짐 — 넣으면 세계수를 1/100억으로 올리고 뉴스 기준도 1억으로). "
    "근거·표: balance/sim_results.md, 재현: tools/balance/variant_rec_design.py + tools/balance/compare.py. "
    "구현 라운드(승인 뒤): AUTO 에서 이미 발견한 명소는 짧은 연출(shortRevealKnown, 3등급처럼) -> 세계수 1/100억, "
    "속보 >= 1억, 홀로그램 >= 3.75억(후반 1인 시간당 속보 약 0.22 / 0.44회). 가챠식 별(처음 발견 별 0, 중복마다 +1, "
    "최대 5) + 별 1개마다 수입 +30%. 환생 코인 그대로. 첫 환생 약 16분, 3번째 2.4시간, 5번째 18시간, 10번째 약 18일(무료). "
    "근거: balance/sim_results.md 8번, 재현: tools/balance/tune_final.py. "
    "9번 라운드(자동 굴림 빠르게): AUTO 에서 이미 발견한 명소는 결과 카드만 퐁 하고 기다리지 않음(quickRevealKnown = "
    "Config.AUTO_QUICK_REVEAL) -> AUTO 속도 = 굴림 간격(여행사·빠른 굴림이 AUTO 도 빠르게, 후반 시간당 3,000~8,571번). "
    "환생 코인 40만·400만·6,000만·5억·30억·90억·180억·400억·900억·2,000억(첫 환생 약 17분, 3번째 2.8시간, 5번째 약 26시간, "
    "10번째 약 23일 — 승인안과 같은 속도), 속보 >= 3.75억(= 홀로그램, 후반 1인 시간당 약 0.11 / 0.33회). "
    "근거: balance/sim_results.md 9번, 재현: tools/balance/tune_quick.py"
)


def build() -> dict:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    v = copy.deepcopy(base)
    v["name"] = "최종안 (추천안 + 구현 라운드 + 빠른 결과): 환생 행운 x2^r, 첫 환생 약 17분, 10번째 약 23일, 가장 희귀 1/100억, 가챠식 별"
    steps = v["rebirth"]["steps"]
    for k, coins in STEP_COINS.items():
        steps[k - 1]["coins"] = coins
    for k, ids in STEP_LANDMARKS.items():
        steps[k - 1]["landmarks"] = list(ids)
    v["announceOneIn"] = ANNOUNCE_ONE_IN
    v["hologramOneIn"] = HOLOGRAM_ONE_IN
    v["landmarks"].update(LANDMARKS)
    v["rules"] = dict(RULES)
    v["starThresholds"] = list(STAR_THRESHOLDS)
    v["starIncomeBonus"] = STAR_INCOME_BONUS
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
