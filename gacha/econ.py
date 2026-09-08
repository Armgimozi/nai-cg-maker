"""재화·뽑기 배너·상점·스테이지·미션 정의.

확률형 아이템 확률은 전부 여기에 상수로 두고, 클라이언트 확률 공시 화면
(`/api/game/banners` 의 `disclosure`)이 같은 값을 그대로 읽어서 보여준다.
게임산업법상 확률 공시는 실제 적용값과 일치해야 하므로 출처를 하나로 유지한다.
"""

from __future__ import annotations

from .content import BY_ID

# ─────────────────────────────────────────────────────────── 재화
# stardust  별가루 : 무료 재화. 미션·전투·이벤트로 획득. 뽑기에 사용.
# essence   별정수 : 유료 재화. 상점 결제로만 획득. 별가루보다 먼저 소모되지 않는다.
# ticket    소환권 : 뽑기 1회 교환권.
# gold      골드   : 캐릭터 레벨업 재화.
PULL_COST = 160          # 뽑기 1회당 별가루
PULL_COST_10 = 1600      # 10연차(할인 없음 — 대신 4★ 이상 1개 보장)

STAMINA_MAX = 120
STAMINA_REGEN_SEC = 300   # 5분당 1
STAMINA_REFILL_COST = 50  # 별정수 → 스태미나 60
STAMINA_REFILL_AMOUNT = 60

# ─────────────────────────────────────────────────────────── 뽑기 확률
# 기본 확률 (소프트 천장 진입 전)
RATE_5 = 0.006      # 0.6%
RATE_4 = 0.051      # 5.1%
# 소프트 천장: 74회차부터 5★ 확률이 회차당 +6%p 씩 가파르게 상승
SOFT_PITY_START = 74
SOFT_PITY_STEP = 0.06
HARD_PITY = 90       # 90회차에 5★ 확정
PITY_4 = 10          # 10회 안에 4★ 이상 확정
PICKUP_RATE_5 = 0.5  # 5★ 당첨 시 픽업일 확률(실패하면 다음 5★는 픽업 확정)
PICKUP_RATE_4 = 0.5

# 종합 확률(천장·보장까지 반영한 실제 기댓값). 마르코프 연쇄 정상분포로 계산한
# 값이며 tools/verify_rates.py 가 같은 값을 재계산해 검증한다. 확률 공시에는
# 기본 확률과 이 종합 확률을 함께 표시한다.
EFFECTIVE_RATE_5 = 0.016052
EFFECTIVE_RATE_4 = 0.117916


def _banner(bid, name, subtitle, kind, p5, p4, art_hint):
    return {"id": bid, "name": name, "subtitle": subtitle, "kind": kind,
            "pickup5": p5, "pickup4": p4, "art_hint": art_hint}


BANNERS = [
    _banner("dawn", "새벽의 검성", "세라핀 확률 UP", "limited",
            ["seraphine"], ["miyu", "sora", "noelle"], "seraphine"),
    _banner("moonshadow", "달그림자의 맹세", "카구야 확률 UP", "limited",
            ["kaguya"], ["hazel", "tsuki", "yuki"], "kaguya"),
    _banner("standard", "별빛의 서약", "상시 소환 · 모든 소녀 등장", "standard",
            [], [], "linette"),
]
BANNER_BY_ID = {b["id"]: b for b in BANNERS}


def disclosure(banner: dict) -> dict:
    """확률 공시용 표 — 화면에 그대로 노출되는 값."""
    p5, p4 = banner["pickup5"], banner["pickup4"]
    rows = []
    if p5:
        rows.append({"label": f"5★ 픽업 ({', '.join(BY_ID[c]['name'] for c in p5)})",
                     "rate": f"{RATE_5 * PICKUP_RATE_5 * 100:.3f}%"})
        rows.append({"label": "5★ 그 외", "rate": f"{RATE_5 * (1 - PICKUP_RATE_5) * 100:.3f}%"})
    else:
        rows.append({"label": "5★ 전체", "rate": f"{RATE_5 * 100:.3f}%"})
    if p4:
        rows.append({"label": f"4★ 픽업 ({', '.join(BY_ID[c]['name'] for c in p4)})",
                     "rate": f"{RATE_4 * PICKUP_RATE_4 * 100:.3f}%"})
        rows.append({"label": "4★ 그 외", "rate": f"{RATE_4 * (1 - PICKUP_RATE_4) * 100:.3f}%"})
    else:
        rows.append({"label": "4★ 전체", "rate": f"{RATE_4 * 100:.3f}%"})
    rows.append({"label": "3★", "rate": f"{(1 - RATE_5 - RATE_4) * 100:.3f}%"})
    return {
        "rows": rows,
        "notes": [
            f"{SOFT_PITY_START}회차부터 5★ 확률이 회차마다 크게 상승합니다(소프트 천장).",
            f"{HARD_PITY}회 안에 5★ 이상이 반드시 나옵니다(천장).",
            f"{PITY_4}회 안에 4★ 이상이 반드시 나옵니다.",
            "5★ 획득 시 50% 확률로 픽업이며, 픽업이 아니었다면 다음 5★는 픽업이 확정됩니다.",
            "천장 횟수는 배너별로 따로 쌓이며, 같은 종류의 한정 배너끼리는 이어집니다.",
        ],
        "effective": [
            {"label": "5★ 종합(천장 포함)", "rate": f"{EFFECTIVE_RATE_5 * 100:.3f}%"},
            {"label": "4★ 종합(보장 포함)", "rate": f"{EFFECTIVE_RATE_4 * 100:.3f}%"},
            {"label": "3★ 종합",
             "rate": f"{(1 - EFFECTIVE_RATE_5 - EFFECTIVE_RATE_4) * 100:.3f}%"},
        ],
        "expected": _expected_pulls(),
    }


def _expected_pulls() -> str:
    """천장 구조까지 반영한 5★ 1개당 평균 소요 횟수(참고값)."""
    surv, total = 1.0, 0.0
    for i in range(1, HARD_PITY + 1):
        p = pity_rate5(i)
        total += surv * p * i
        surv *= (1 - p)
    return f"5★ 1개당 평균 약 {total:.1f}회 (별가루 {int(total) * PULL_COST:,})"


def pity_rate5(pull_index: int) -> float:
    """이번이 (배너 천장 카운터 기준) pull_index 번째 뽑기일 때의 5★ 확률."""
    if pull_index >= HARD_PITY:
        return 1.0
    if pull_index >= SOFT_PITY_START:
        return min(1.0, RATE_5 + (pull_index - SOFT_PITY_START + 1) * SOFT_PITY_STEP)
    return RATE_5


# ─────────────────────────────────────────────────────────── 상점 (모의 결제)
# price_krw 는 표시용. 실제 결제는 붙어있지 않으며, 출시 시 이 자리에
# Google Play Billing / Stripe 등의 검증된 영수증 처리로 교체해야 한다.
SHOP_PACKAGES = [
    {"id": "gem_s", "name": "작은 별주머니", "price_krw": 1100,
     "essence": 60, "bonus": 0, "tag": ""},
    {"id": "gem_m", "name": "별주머니", "price_krw": 5500,
     "essence": 300, "bonus": 30, "tag": ""},
    {"id": "gem_l", "name": "큰 별주머니", "price_krw": 11000,
     "essence": 600, "bonus": 60, "tag": ""},
    {"id": "gem_xl", "name": "별상자", "price_krw": 33000,
     "essence": 1800, "bonus": 260, "tag": "인기"},
    {"id": "gem_xxl", "name": "큰 별상자", "price_krw": 55000,
     "essence": 3280, "bonus": 600, "tag": ""},
    {"id": "gem_max", "name": "은하 상자", "price_krw": 119000,
     "essence": 6480, "bonus": 1600, "tag": "최대 혜택"},
]
FIRST_PURCHASE_MULT = 2  # 상품별 최초 1회 구매 시 별정수 2배

MONTHLY_PASS = {
    "id": "monthly", "name": "달빛 통행증", "price_krw": 5500,
    "instant_essence": 300, "daily_stardust": 90, "days": 30,
    "desc": "구매 즉시 별정수 300, 이후 30일간 매일 접속 시 별가루 90.",
}

# 별정수 → 별가루 교환 (유료 재화로 뽑기를 하려면 이 교환을 거친다)
ESSENCE_TO_STARDUST = 1

# ─────────────────────────────────────────────────────────── 스테이지
CHAPTERS = [
    {"id": 1, "name": "별이 떨어진 들판", "element": "질풍", "stages": 6, "power": 1.0},
    {"id": 2, "name": "잠긴 해안 성채", "element": "해류", "stages": 6, "power": 1.9},
    {"id": 3, "name": "잿빛 화산 회랑", "element": "화염", "stages": 6, "power": 3.4},
    {"id": 4, "name": "달 없는 첨탑", "element": "심연", "stages": 6, "power": 6.0},
]
STAMINA_COST = 12
ENEMY_NAMES = ["떠도는 잔영", "부서진 수호기", "굶주린 그림자", "잿빛 파수꾼",
               "심연의 조각", "무너진 성상"]
BOSS_NAMES = {1: "들판의 폭풍핵", 2: "성채의 수문장", 3: "화산의 태동", 4: "첨탑의 주인"}


def stage_list() -> list[dict]:
    out = []
    for ch in CHAPTERS:
        for s in range(1, ch["stages"] + 1):
            boss = (s == ch["stages"])
            out.append({
                "key": f"{ch['id']}-{s}",
                "chapter": ch["id"], "chapter_name": ch["name"], "stage": s,
                "name": (BOSS_NAMES[ch["id"]] if boss else f"{ch['name']} {s}구역"),
                "boss": boss, "element": ch["element"],
                "stamina": STAMINA_COST + (6 if boss else 0),
                "reward": {
                    "gold": int(120 * ch["power"] * (1 + 0.15 * s)) * (3 if boss else 1),
                    "exp": int(40 * ch["power"] * (1 + 0.2 * s)) * (2 if boss else 1),
                    "stardust_first": (300 if boss else 60),
                },
            })
    return out


STAGES = {s["key"]: s for s in stage_list()}

# ─────────────────────────────────────────────────────────── 일일 미션 / 출석
DAILY_MISSIONS = [
    {"id": "pull1", "name": "소환 1회", "goal": 1, "reward": 60},
    {"id": "battle3", "name": "전투 3회 승리", "goal": 3, "reward": 80},
    {"id": "levelup", "name": "캐릭터 레벨업 1회", "goal": 1, "reward": 60},
]
LOGIN_REWARDS = [
    {"day": 1, "stardust": 100},
    {"day": 2, "gold": 2000},
    {"day": 3, "ticket": 1},
    {"day": 4, "stardust": 160},
    {"day": 5, "gold": 5000},
    {"day": 6, "stardust": 200},
    {"day": 7, "ticket": 3, "stardust": 300},
]
