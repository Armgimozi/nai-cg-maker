#!/usr/bin/env python3
"""balance/REVENUE.md 용 예상 수익 모델 + 그림(balance/revenue_chart.png).

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/revenue_model.py                  # 표 출력 + balance/revenue_results.json
  python3 tools/balance/revenue_model.py --chart --font-regular R.ttf --font-bold B.ttf   # + 그림
  python3 tools/balance/revenue_model.py --pass-value     # sim.py 로 상품별 진행 속도(약 2분) → balance/revenue_pass_value.json

상품·가격은 src/shared/Config.luau 에서 읽음(가격을 바꾸면 다시 돌리면 됨). 나머지 숫자는 아래 FACTS(출처 있는 사실)와
SCENARIOS·RETENTION·그 밖의 [가정] 값. 출처 목록은 balance/REVENUE.md 끝.

모델(한 달 = 30일, 안정 상태 — 매달 같은 DAU 가 유지된다고 봄):
  * 시나리오(비관·기본·낙관) = 리텐션 + 수익화 한 묶음(좋은 게임은 둘 다 좋고 나쁜 게임은 둘 다 나쁨 — 섞지 않음).
  * 수명 활동일 L = 1 + Σ_{d=1..180} R(d). R(d) 는 D1·D7·D30 을 지나는 거듭제곱 곡선(구간별), 30일 뒤는 7→30 기울기로 이어감.
  * 새 사용자/달 = DAU × 30 / L (DAU 를 유지하려면 이만큼 들어와야 함).
  * 수익화 값(평생 결제 전환 · 결제자 1인 개발자 상품 개수)은 기준 수명 L_REF(= S7 중앙값 리텐션)에서의 값이고 수명에 따라
    늘어남: 전환 × (L/L_REF)^CONV_EXP, 상품 개수 × (L/L_REF)^PRODUCT_EXP. 패스(한 번만 삼)는 결제자 1인 구매 확률 그대로.
    → DAU 당 수익이 리텐션과 함께 줄지 않음(예전 모델은 새 사용자 수에만 비례해 리텐션이 좋을수록 DAU 당 수익이 줄었음).
  * 총 Robux(플레이어가 쓴 것) = Σ 개수 × 가격 × 실현율. 패스는 지역 가격(Managed Pricing)이 기본으로 켜져 있어 실현율 < 100%,
    개발자 상품은 직접 켜야 해서 지금은 100% [S5 creator-docs regional-pricing.md].
  * 개발자 몫 = 총 Robux × 70% (게임 안 판매 수수료 30%).
  * Creator Rewards(일일 참여 보상) = DAU × Active Spender 비율 × 자격(10분+ · 그날 첫 3개 게임) × 5 R$ × 30일. 수수료 없음,
    60일 보류 뒤 Earned R$.
  * USD = (개발자 몫 + Creator Rewards) × DevEx $0.0038 (미국 18+ 인증 구매분 $0.0054 는 기본 0% — 가정).
  * 대시보드 지표(라이브 뒤 비교용): 전환율 = 그날 결제한 사람 / DAU, ARPPU = 하루 결제액 / 그날 결제자, ARPDAU = 하루 결제액 / DAU.
    결제자 1인의 결제한 날 수 = 1 + 0.5 × (산 개수 - 1) [가정: 여러 개를 같은 날 사기도 함].
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # roblox-rng
CONFIG = ROOT / "src" / "shared" / "Config.luau"
OUT_JSON = ROOT / "balance" / "revenue_results.json"
OUT_PNG = ROOT / "balance" / "revenue_chart.png"
PASS_VALUE_JSON = ROOT / "balance" / "revenue_pass_value.json"

# ---------------------------------------------------------------------------------------------
# 사실(출처: balance/REVENUE.md "출처" — S 번호)
FACTS = {
    "dev_share": 0.70,  # 게임 안 판매(패스·개발자 상품)에서 제작자 몫 70% [S1]
    "devex": 0.0038,  # 1 Earned Robux = $0.0038 (2025-09-05 이후 번 것) [S2]
    "devex_us18": 0.0054,  # 미국 18+ 연령 인증 구매분(패스·개발자 상품, 자격 있는 게임만 — R15 등, 2026-06-08~) [S3]
    "devex_min": 30000,  # DevEx 최소 인출 30,000 Earned Robux (= $114) [S2]
    "creator_reward": 5,  # Active Spender 1명이 그날 첫 3개 게임 중 하나로 10분+ 하면 5 R$ (60일 보류) [S4]
    "creator_reward_hold_days": 60,
    "robux_asp": 0.01,  # [가정] 플레이어가 1 Robux 를 사는 평균 가격 약 $0.01 (400 R$ = $4.99 정가 $0.0125, 큰 묶음·Premium 은 더 쌈)
    "days": 30,
}

# [가정] 리텐션(D1, D7, D30). S7 = GameAnalytics 2026: MAU 100만을 넘긴(= 성공한) 게임 500여 개의 중앙값 10.3% / 1.6% / 0.5%,
# 상위 1% 22.2% / 9.1% / 4.7%. 한국어 전용 · 평가 단계 새 게임에는 중앙값도 후한 편이라 기본 = 중앙값, 비관 = 그 아래,
# 낙관 = 중앙값과 상위 1% 사이
RETENTION = {
    "pess": (0.06, 0.008, 0.002),
    "base": (0.103, 0.016, 0.005),
    "opt": (0.16, 0.045, 0.02),
}
REF_RETENTION = RETENTION["base"]  # 수익화 값(전환 · 상품 개수)을 정한 기준 리텐션 → L_REF

# [가정] 수익화 시나리오(기준 수명 L_REF 에서). passes = 결제자 중 그 패스를 사는 비율, products = 결제자 1인 평생 구매 횟수.
# 전환은 높게·1인 결제액은 낮게(결제자 대부분은 한두 개): S7 의 "1년 동안 결제한 플레이어 3.80%"(성공한 게임) 쪽 모양.
# 새 사용자 1명당 결제(= 전환 × 1인 결제액)는 기본에서 약 2.7 R$ ≈ S7 3.80% × $0.70 을 $0.01/R$ 로 본 값
PASS_REALIZED = {"pess": 0.75, "base": 0.85, "opt": 0.95}  # 패스 지역 가격 실현율(평균 판매가 / 정가) — Managed Pricing 기본 켜짐
SCENARIOS = {
    "pess": {
        "label": "비관",
        "payer_conv": 0.005,
        "passes": {"DoubleIncome": 0.15, "LuckVIP": 0.10, "FastRoll": 0.08},
        "products": {"LuckBoost": 0.8, "ServerLuck": 0.05, "CoinPack": 0.15},
        "price_realized": PASS_REALIZED["pess"],
        "products_realized": 1.0,  # 개발자 상품은 지역 가격이 기본으로 꺼져 있음
        "active_spender": 0.05,
        "cr_qualify": 0.15,
    },
    "base": {
        "label": "기본",
        "payer_conv": 0.010,
        "passes": {"DoubleIncome": 0.25, "LuckVIP": 0.20, "FastRoll": 0.15},
        "products": {"LuckBoost": 1.0, "ServerLuck": 0.15, "CoinPack": 0.3},
        "price_realized": PASS_REALIZED["base"],
        "products_realized": 1.0,
        "active_spender": 0.08,
        "cr_qualify": 0.30,
    },
    "opt": {
        "label": "낙관",
        "payer_conv": 0.020,
        "passes": {"DoubleIncome": 0.35, "LuckVIP": 0.30, "FastRoll": 0.20},
        "products": {"LuckBoost": 1.5, "ServerLuck": 0.3, "CoinPack": 0.5},
        "price_realized": PASS_REALIZED["opt"],
        "products_realized": 1.0,
        "active_spender": 0.11,
        "cr_qualify": 0.50,
    },
}
SCEN_ORDER = ("pess", "base", "opt")

DAU_TIERS = (10, 50, 500, 5000, 50000)
PLAYTIME_MIN_PER_DAU = 20.0  # [가정] 하루 플레이 시간(분) — CCU 환산용. GameAnalytics 세션 중앙값 9.8분 [S7], 하루 1~2번 + AUTO 굴림이라 조금 더
CPP_USD = (0.05, 0.45)  # [가정·제3자] 광고 1플레이당 비용: 잘 되는 경우 / 평균 [S9] (전 연령 기준 — 16+ 만 노리면 더 비쌀 수 있음)
# 새 게임 평가(2026-05-19~): 나이 확인한 16+ "highly engaged"(계정 기간 + 이 게임 플레이 시간 + 최근 60일 로블록스 어디서든 결제)
# 250번의 고유 플레이 / 60일 [S10]
EVAL_PLAYS = 250
HE_SHARE = (0.15, 0.05)  # [가정] 16+ 방문 중 highly engaged 로 세는 비율: 잘 되면 / 보통 (최근 60일 결제한 사람만 — Active Spender 8% 가정과 맞춤)
PRICE_ELASTICITY = 1.3  # [가정] 가격 +1% → 결제자 -1.3%. 1 에 가까워 가격을 바꿔도 수익이 거의 안 변하게 정해 둔 값(S6 +4% 로는 못 정함)
# [가정] 수명이 길면(L ↑) 결제 전환·반복 구매도 늘어남: 전환 ∝ (L/L_REF)^0.8(첫날에 조금 몰림), 개발자 상품 개수 ∝ (L/L_REF)^0.7
CONV_EXP, PRODUCT_EXP = 0.8, 0.7
SAME_DAY_SHARE = 0.5  # [가정] 두 번째부터의 구매 중 앞 구매와 같은 날인 비율 → 결제한 날 = 1 + 0.5 × (개수 - 1)
HORIZON_DAYS = 180
# 개발자 상품 지역 가격 켜기(제안): 할인 지역 결제자 비율 [가정], 그곳 결제자 증가 +13.8~44.8% (패스, 멕시코~필리핀 [S5])
RP_DISCOUNTED_SHARE = 0.35
RP_PAYER_UPLIFT = (0.138, 0.448)


# ---------------------------------------------------------------------------------------------
# 상품(Config.luau)


def load_products() -> dict:
    """Config.luau 의 GamePasses / Products 에서 Id·Name·Price·번호를 읽음(순서 유지)."""
    text = CONFIG.read_text(encoding="utf-8")
    out = {}
    for block_name, kind in (("GamePasses", "pass"), ("Products", "product")):
        m = re.search(block_name + r"\s*=\s*\{(.*?)\}\s*::", text, re.S)
        if not m:
            raise SystemExit(f"Config.luau 에서 {block_name} 를 못 찾음")
        body = m.group(1)
        # 항목 하나 = Id = "..." 부터 다음 Id 전까지
        parts = re.split(r'(?=Id\s*=\s*")', body)
        for part in parts:
            mid = re.search(r'Id\s*=\s*"(\w+)"', part)
            if not mid:
                continue
            name = re.search(r'Name\s*=\s*"([^"]+)"', part)
            price = re.search(r"Price\s*=\s*(\d+)", part)
            num = re.search(r"(PassId|ProductId)\s*=\s*(\d+)", part)
            out[mid.group(1)] = {
                "kind": kind,
                "name": name.group(1) if name else mid.group(1),
                "price": int(price.group(1)) if price else 0,
                "active": bool(num and int(num.group(2)) > 0),
            }
    need = {"LuckVIP", "FastRoll", "DoubleIncome", "LuckBoost", "ServerLuck", "CoinPack"}
    missing = need - set(out)
    if missing:
        raise SystemExit(f"Config.luau 에 없는 상품: {sorted(missing)}")
    return out


# ---------------------------------------------------------------------------------------------
# 모델


def retention_curve(d1: float, d7: float, d30: float, horizon: int = HORIZON_DAYS) -> list[float]:
    """R(d), d = 1..horizon. 1~7일과 7~30일은 각각 거듭제곱(로그-로그 직선), 30일 뒤는 7→30 기울기 그대로."""
    b1 = math.log(d1 / d7) / math.log(7)
    b2 = math.log(d7 / d30) / math.log(30 / 7)
    out = []
    for d in range(1, horizon + 1):
        out.append(d1 * d**-b1 if d <= 7 else d7 * (d / 7) ** -b2)
    return out


def lifetime_days(ret: tuple[float, float, float], horizon: int = HORIZON_DAYS) -> float:
    return 1.0 + sum(retention_curve(*ret, horizon=horizon))


def tail_share(ret: tuple[float, float, float]) -> float:
    """첫날을 뺀 수명 중 31~180일에서 오는 몫(30일 뒤 곡선을 이어 붙인 가정이 얼마나 큰지)."""
    curve = retention_curve(*ret)
    return sum(curve[30:]) / sum(curve)


def scaled(mon: dict, L: float, L_ref: float) -> dict:
    """수익화 값을 수명 L 에 맞춤(기준 L_ref 에서 정한 전환·상품 개수 → L 일 때)."""
    k = L / L_ref
    m = copy.deepcopy(mon)
    m["payer_conv"] = min(1.0, m["payer_conv"] * k**CONV_EXP)
    m["products"] = {pid: n * k**PRODUCT_EXP for pid, n in m["products"].items()}
    return m


def payer_items(mon: dict) -> float:
    return sum(mon["passes"].values()) + sum(mon["products"].values())


def realized_rate(mon: dict, kind: str) -> float:
    return mon["price_realized"] if kind == "pass" else mon.get("products_realized", 1.0)


def payer_gross(mon: dict, products: dict) -> dict:
    """결제자 1인 평생 총 Robux(실현율 반영) — 상품별."""
    out = {}
    for pid, share in mon["passes"].items():
        out[pid] = share * products[pid]["price"] * realized_rate(mon, products[pid]["kind"])
    for pid, n in mon["products"].items():
        out[pid] = n * products[pid]["price"] * realized_rate(mon, products[pid]["kind"])
    return out


def sales_usd(robux: float, us18_share: float = 0.0) -> float:
    """게임 안 판매 Robux(플레이어가 쓴 것) → 개발자가 받는 USD."""
    rate = FACTS["devex"] * (1 - us18_share) + FACTS["devex_us18"] * us18_share
    return robux * FACTS["dev_share"] * rate


def monthly(
    dau: float,
    mon: dict,
    products: dict,
    ret: tuple = REF_RETENTION,
    us18_share: float = 0.0,
    horizon: int = HORIZON_DAYS,
) -> dict:
    """DAU 가 한 달 내내 유지될 때 그 달의 수익. mon 은 L_REF 기준 값 — 여기서 ret 의 수명에 맞춰 늘리거나 줄임."""
    days = FACTS["days"]
    L = lifetime_days(ret, horizon)
    L_ref = lifetime_days(REF_RETENTION, horizon)
    m = scaled(mon, L, L_ref)
    new_users = dau * days / L
    payers = new_users * m["payer_conv"]
    by_product = {pid: payers * v for pid, v in payer_gross(m, products).items()}
    gross = sum(by_product.values())
    dev = gross * FACTS["dev_share"]
    cr = dau * m["active_spender"] * m["cr_qualify"] * FACTS["creator_reward"] * days
    earned = dev + cr
    items = payer_items(m)
    pay_days = 1 + (1 - SAME_DAY_SHARE) * max(0.0, items - 1)
    daily_payers = payers * pay_days / days
    gross_day = gross / days
    passes = sum(v for pid, v in by_product.items() if products[pid]["kind"] == "pass")
    usd_sales = sales_usd(gross, us18_share)
    usd_cr = cr * FACTS["devex"]  # Creator Rewards 는 게임 판매가 아니라 18+ 환율 대상 아님
    return {
        "dau": dau,
        "lifetime_days": L,
        "payer_conv": m["payer_conv"],
        "payer_items": items,
        "payer_gross_robux": gross / payers if payers else 0.0,
        "new_users": new_users,
        "payers": payers,
        "gross_robux": gross,
        "passes_robux": passes,
        "products_robux": gross - passes,
        "by_product_robux": by_product,
        "dev_robux": dev,
        "dev_passes_robux": passes * FACTS["dev_share"],
        "dev_products_robux": (gross - passes) * FACTS["dev_share"],
        "creator_rewards_robux": cr,
        "earned_robux": earned,
        "usd": usd_sales + usd_cr,
        "usd_sales": usd_sales,
        "usd_creator_rewards": usd_cr,
        "player_spend_usd": gross * FACTS["robux_asp"],
        # 플레이어가 낸 돈 ÷ 개발자가 받은 판매분(Creator Rewards 빼고)
        "spend_to_sales_ratio": (gross * FACTS["robux_asp"]) / usd_sales if usd_sales else 0.0,
        "months_to_devex": FACTS["devex_min"] / earned if earned > 0 else math.inf,
        "ccu": dau * PLAYTIME_MIN_PER_DAU / 1440,
        "dash_conversion": daily_payers / dau,
        "dash_arppu_robux": gross_day / daily_payers if daily_payers else 0.0,
        "dash_arpdau_robux": gross_day / dau,
        "new_user_payment_robux": gross / new_users,
        "ltv_new_user_usd": (usd_sales + usd_cr) / new_users,
    }


def scenario(dau: float, s: str, products: dict, **kw) -> dict:
    """시나리오 = 리텐션 + 수익화 한 묶음."""
    return monthly(dau, SCENARIOS[s], products, RETENTION[s], **kw)


def with_changes(
    mon: dict,
    conv=1.0,
    spend=1.0,
    products_mult=1.0,
    price=1.0,
    realized=None,
    products_realized=None,
    qualify=None,
) -> dict:
    m = copy.deepcopy(mon)
    m["payer_conv"] *= conv * price**-PRICE_ELASTICITY
    m["passes"] = {k: min(1.0, v * spend) for k, v in m["passes"].items()}
    m["products"] = {k: v * spend * products_mult for k, v in m["products"].items()}
    m["price_realized"] *= price
    m["products_realized"] = m.get("products_realized", 1.0) * price
    if realized is not None:
        m["price_realized"] = realized
    if products_realized is not None:
        m["products_realized"] = products_realized
    if qualify is not None:
        m["cr_qualify"] = qualify
    return m


def fixed_inflow(new_per_day: float, mon: dict, products: dict, ret: tuple, horizon: int = HORIZON_DAYS) -> dict:
    """새 사용자 유입(하루)을 고정하고 리텐션을 바꿈: DAU = 유입 × L (전환·반복 구매는 monthly 가 L 에 맞춤)."""
    return monthly(new_per_day * lifetime_days(ret, horizon), mon, products, ret, horizon=horizon)


def sensitivity(products: dict, dau: float = 5000) -> list[dict]:
    """기본 시나리오, DAU 5,000 기준으로 한 가지씩 바꿨을 때 월 USD 변화(리텐션은 유입 고정)."""
    base = SCENARIOS["base"]
    ret = RETENTION["base"]
    ref = monthly(dau, base, products, ret)["usd"]
    inflow = dau / lifetime_days(ret)
    ref30 = monthly(dau, base, products, ret, horizon=30)["usd"]
    inflow30 = dau / lifetime_days(ret, 30)
    rows = [
        (
            "리텐션 D1·D7·D30 (유입 고정)",
            "비관",
            "낙관",
            fixed_inflow(inflow, base, products, RETENTION["pess"])["usd"] / ref,
            fixed_inflow(inflow, base, products, RETENTION["opt"])["usd"] / ref,
        ),
        (
            "리텐션, 수명을 30일까지만 셀 때",
            "비관",
            "낙관",
            fixed_inflow(inflow30, base, products, RETENTION["pess"], 30)["usd"] / ref30,
            fixed_inflow(inflow30, base, products, RETENTION["opt"], 30)["usd"] / ref30,
        ),
        (
            "결제 전환율",
            "×0.5",
            "×2",
            monthly(dau, with_changes(base, conv=0.5), products, ret)["usd"] / ref,
            monthly(dau, with_changes(base, conv=2.0), products, ret)["usd"] / ref,
        ),
        (
            "결제자 1인 구매 개수",
            "×0.6",
            "×1.6",
            monthly(dau, with_changes(base, spend=0.6), products, ret)["usd"] / ref,
            monthly(dau, with_changes(base, spend=1.6), products, ret)["usd"] / ref,
        ),
        (
            "10분+ 플레이(Creator Rewards)",
            "15%",
            "50%",
            monthly(dau, with_changes(base, qualify=0.15), products, ret)["usd"] / ref,
            monthly(dau, with_changes(base, qualify=0.50), products, ret)["usd"] / ref,
        ),
        (
            "패스 지역 가격 실현율",
            "75%",
            "95%",
            monthly(dau, with_changes(base, realized=0.75), products, ret)["usd"] / ref,
            monthly(dau, with_changes(base, realized=0.95), products, ret)["usd"] / ref,
        ),
        (
            "모든 가격(탄력성 1.3 가정)",
            "+25%",
            "-25%",
            monthly(dau, with_changes(base, price=1.25), products, ret)["usd"] / ref,
            monthly(dau, with_changes(base, price=0.75), products, ret)["usd"] / ref,
        ),
    ]
    out = []
    for name, lo_txt, hi_txt, lo, hi in rows:
        out.append(
            {"name": name, "low_label": lo_txt, "high_label": hi_txt, "low_pct": lo - 1, "high_pct": hi - 1, "ref_usd": ref}
        )
    return out


def per_dau_by_retention(products: dict, dau: float = 1000) -> dict:
    """DAU 를 고정하고 리텐션만 바꿈(수익화 기본): DAU 당 수익이 리텐션과 함께 줄지 않는지 확인용."""
    base = SCENARIOS["base"]
    return {k: monthly(dau, base, products, RETENTION[k])["usd"] for k in SCEN_ORDER}


def levers(products: dict, dau: float = 1000) -> list[dict]:
    """제안별 대략 효과(기본 시나리오, 1,000 DAU). 효과 크기는 모두 [가정].
    lo = 새로 결제하게 된 사람은 제안한 그 상품 하나만 삼(하한), hi = 새 결제자도 평균 결제자처럼 삼(상한)."""
    base = SCENARIOS["base"]
    ret = RETENTION["base"]
    ref = monthly(dau, base, products, ret)
    inflow = dau / lifetime_days(ret)
    out = []

    def add(name, lo, hi, note):
        lo, hi = min(lo, hi), max(lo, hi)
        out.append(
            {
                "name": name,
                "usd_lo": lo,
                "usd_hi": hi,
                "pct_lo": lo / ref["usd"] - 1,
                "pct_hi": hi / ref["usd"] - 1,
                "note": note,
            }
        )

    # 스타터 팩 99 R$(한 번만): 결제 전환 ×1.25, 원래 결제자의 40% 도 삼
    sp = copy.deepcopy(products)
    sp["StarterPack"] = {"kind": "product", "name": "스타터 팩", "price": 99, "active": True}
    m = copy.deepcopy(base)
    m["products"]["StarterPack"] = 0.4
    hi = monthly(dau, with_changes(m, conv=1.25), sp, ret)["usd"]  # 상한: 새 결제자도 평균 결제자처럼 + 팩
    # 하한: 팩을 산 원래 결제자는 행운 부스트 하나를 덜 삼(잠식), 새 결제자는 팩 하나만
    m_lo = copy.deepcopy(m)
    m_lo["products"]["LuckBoost"] = max(0.0, m_lo["products"]["LuckBoost"] - 0.4)
    old = monthly(dau, m_lo, sp, ret)
    extra_payers = old["payers"] * 0.25
    lo = old["usd"] + sales_usd(extra_payers * 99 * base.get("products_realized", 1.0))
    add(
        "첫 구매 스타터 팩(99 R$, 한 번만)",
        lo,
        hi,
        "결제 전환 ×1.25, 원래 결제자 40% 도 삼. 하한 = 그 40% 는 행운 부스트 하나 대신 · 새 결제자는 팩만",
    )
    # 상황별 제안(수입 2배 · 코인 팩 · 행운 부스트): 결제 전환 ×1.2, 하한 = 새 결제자는 제안받은 것 하나만(세 가지 평균 값)
    extra_payers = ref["payers"] * 0.2
    offered = [
        products["DoubleIncome"]["price"] * base["price_realized"],
        products["CoinPack"]["price"] * base.get("products_realized", 1.0),
        products["LuckBoost"]["price"] * base.get("products_realized", 1.0),
    ]
    lo = ref["usd"] + sales_usd(extra_payers * sum(offered) / len(offered))
    hi = monthly(dau, with_changes(base, conv=1.2), products, ret)["usd"]
    add("상황별 구매 제안(첫 환생 뒤·코인 모자랄 때)", lo, hi, "결제 전환 ×1.2")
    rep = monthly(dau, with_changes(base, products_mult=1.6), products, ret)["usd"]
    add("반복 상품을 쓸모 있게(수입 부스트·큰 코인 팩)", rep, rep, "결제자 1인 개발자 상품 구매 ×1.6")
    better = (ret[0] + 0.02, ret[1] + 0.006, ret[2] + 0.002)
    ret_up = fixed_inflow(inflow, base, products, better)["usd"]
    add("일일 보상·연속 접속·오프라인 수입(시간 상한 있음)", ret_up, ret_up, "D1 +2%p, D7 +0.6%p, D30 +0.2%p (유입 고정)")
    # 개발자 상품 지역 가격: 할인 지역(결제자 35%)은 패스와 같은 평균 할인, 그곳 개발자 상품 구매 +13.8~44.8%
    discount = (1 - base["price_realized"]) / RP_DISCOUNTED_SHARE
    rp = []
    for up in RP_PAYER_UPLIFT:
        factor = (1 - RP_DISCOUNTED_SHARE) + RP_DISCOUNTED_SHARE * (1 + up) * (1 - discount)
        rp.append(monthly(dau, with_changes(base, products_realized=factor), products, ret)["usd"])
    add(
        "개발자 상품 지역 가격 켜기(패스는 이미 켜짐)",
        rp[0],
        rp[1],
        f"할인 지역 결제자 {RP_DISCOUNTED_SHARE:.0%}, 평균 할인 {discount:.0%}, 그곳 구매 +14~45%",
    )
    us = monthly(dau, base, products, ret, us18_share=0.05)["usd"]
    add("미국 18+ DevEx $0.0054 자격(이미 R15 — 나머지 조건은 확인 필요)", us, us, "판매분의 5% 가 미국 18+ 인증 구매라고 가정")
    return out


def results(products: dict) -> dict:
    tiers = {s: [scenario(d, s, products) for d in DAU_TIERS] for s in SCEN_ORDER}
    per1k = {s: scenario(1000, s, products) for s in SCEN_ORDER}
    ret_info = {
        k: {
            "d": v,
            "lifetime_days": lifetime_days(v),
            "lifetime_days_30": lifetime_days(v, 30),
            "tail_share_31_180": tail_share(v),
        }
        for k, v in RETENTION.items()
    }
    ads = []
    L = ret_info["base"]["lifetime_days"]
    L30 = ret_info["base"]["lifetime_days_30"]
    for i, d in enumerate(DAU_TIERS):
        steady = d / L
        first = d / L30  # 첫 달 끝에 이 DAU 가 되려면(30일 안에 들어온 사람만 남아 있음)
        ads.append(
            {
                "dau": d,
                "new_per_day": steady,
                "new_per_day_first_month": first,
                "ccu": d * PLAYTIME_MIN_PER_DAU / 1440,
                "ads_usd_month": [steady * c * FACTS["days"] for c in CPP_USD],
                "ads_usd_first_month": [first * c * FACTS["days"] for c in CPP_USD],
                "base_usd": tiers["base"][i]["usd"],
            }
        )
    plays = [EVAL_PLAYS / h for h in HE_SHARE]
    evaluation = {
        "plays_needed": plays,
        "ads_usd": [plays[0] * CPP_USD[0], plays[1] * CPP_USD[1]],
    }
    ltv = {s: per1k[s]["ltv_new_user_usd"] for s in SCEN_ORDER}
    return {
        "facts": FACTS,
        "retention": ret_info,
        "scenarios": SCENARIOS,
        "products": products,
        "dau_tiers": DAU_TIERS,
        "tiers": tiers,
        "per_1000_dau": per1k,
        "per_dau_by_retention": per_dau_by_retention(products),
        "ads": ads,
        "cpp_usd": CPP_USD,
        "ad_payback": {s: [ltv[s] / c for c in CPP_USD] for s in SCEN_ORDER},
        "evaluation": evaluation,
        "sensitivity": sensitivity(products),
        "levers": levers(products),
        "assumptions": {
            "playtime_min_per_dau": PLAYTIME_MIN_PER_DAU,
            "price_elasticity": PRICE_ELASTICITY,
            "conv_exp": CONV_EXP,
            "product_exp": PRODUCT_EXP,
            "same_day_share": SAME_DAY_SHARE,
            "horizon_days": HORIZON_DAYS,
            "he_share": HE_SHARE,
            "rp_discounted_share": RP_DISCOUNTED_SHARE,
            "rp_payer_uplift": RP_PAYER_UPLIFT,
        },
    }


# ---------------------------------------------------------------------------------------------
# 출력


def usd(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    if v >= 10:
        return f"${v:.0f}"
    if v >= 1:
        return f"${v:.1f}"
    return f"${v:.2f}"


def usd_chart(v: float) -> str:
    return usd(v)


def rbx(v: float) -> str:
    if v >= 1e6:
        return f"{v / 1e6:.2f}M"
    if v >= 1e4:
        return f"{v / 1e3:.0f}K"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:.0f}"


def months_text(m: float) -> str:
    if m <= 1:
        return "바로" if m <= 0.25 else f"{m * 30:.0f}일"
    if m >= 24:
        return f"{m / 12:.0f}년({m:.0f}달)"
    return f"{m:.1f}달"


def print_tables(res: dict) -> None:
    p = res["products"]
    print("상품:", ", ".join(f"{k} {v['price']} R$" for k, v in p.items()))
    print(
        "수명 활동일 L (180일 / 30일 / 31~180일 몫):",
        {k: (round(v["lifetime_days"], 2), round(v["lifetime_days_30"], 2), f"{v['tail_share_31_180']:.0%}") for k, v in res["retention"].items()},
    )
    print("\n## DAU별 월 수익 (시나리오 = 리텐션 + 수익화)")
    print("| DAU | 시나리오 | 플레이어가 쓴 Robux | 개발자 몫(70%) | Creator Rewards | 합계 Earned R$ | USD(DevEx) | DevEx 최소까지 |")
    print("|---|---|---|---|---|---|---|---|")
    for i, d in enumerate(DAU_TIERS):
        for s in SCEN_ORDER:
            r = res["tiers"][s][i]
            print(
                f"| {d:,} | {SCENARIOS[s]['label']} | {rbx(r['gross_robux'])} | {rbx(r['dev_robux'])} | {rbx(r['creator_rewards_robux'])} |"
                f" {rbx(r['earned_robux'])} | {usd(r['usd'])} | {months_text(r['months_to_devex'])} |"
            )
    print("\n## 1,000 DAU 당 (한 달)")
    for s in SCEN_ORDER:
        r = res["per_1000_dau"][s]
        print(
            f"{SCENARIOS[s]['label']}: L {r['lifetime_days']:.2f} · 새 사용자 {r['new_users']:,.0f} · 평생 전환 {r['payer_conv']:.2%} · 결제자 {r['payers']:.1f}"
            f" · 1인 {r['payer_items']:.2f}개 {r['payer_gross_robux']:.0f} R$ · 총 {rbx(r['gross_robux'])} R$"
            f" (패스 {rbx(r['passes_robux'])} / 상품 {rbx(r['products_robux'])}) · 개발자 {rbx(r['dev_robux'])} + CR {rbx(r['creator_rewards_robux'])}"
            f" = {rbx(r['earned_robux'])} R$ = {usd(r['usd'])} (판매 {usd(r['usd_sales'])} + CR {usd(r['usd_creator_rewards'])})"
            f" · 대시보드 전환율 {r['dash_conversion']:.2%} · ARPPU {r['dash_arppu_robux']:.0f} R$ · ARPDAU {r['dash_arpdau_robux']:.2f} R$"
            f" · 새 사용자 1명 결제 {r['new_user_payment_robux']:.2f} R$ · 가치 ${r['ltv_new_user_usd']:.4f}"
            f" · 쓴 돈/판매 몫 {r['spend_to_sales_ratio']:.2f}배"
        )
        print("   상품별(총 R$):", {k: round(v) for k, v in r["by_product_robux"].items()})
    print("\n## DAU 1,000 고정, 리텐션만 바꿈(수익화 기본):", {k: usd(v) for k, v in res["per_dau_by_retention"].items()})
    print("\n## 트래픽 티어와 광고비(기본 리텐션)")
    for a in res["ads"]:
        print(
            f"DAU {a['dau']:,}: 새 사용자 {a['new_per_day']:,.1f}/일(안정) · 첫 달 {a['new_per_day_first_month']:,.1f}/일 · CCU ≈ {a['ccu']:.2f}"
            f" · 광고 월 {usd(a['ads_usd_month'][0])}~{usd(a['ads_usd_month'][1])} (첫 달 {usd(a['ads_usd_first_month'][0])}~"
            f"{usd(a['ads_usd_first_month'][1])}) vs 기본 수익 {usd(a['base_usd'])}"
        )
    print("광고 회수(새 사용자 가치 ÷ 1플레이 비용 $0.05 / $0.45):", {SCENARIOS[s]["label"]: [round(x, 3) for x in v] for s, v in res["ad_payback"].items()})
    ev = res["evaluation"]
    print(
        f"평가 통과(16+ highly engaged {EVAL_PLAYS}번): 방문 {ev['plays_needed'][0]:,.0f}~{ev['plays_needed'][1]:,.0f}번"
        f" · 전부 광고로면 {usd(ev['ads_usd'][0])}~{usd(ev['ads_usd'][1])}"
    )
    print("\n## 민감도 (기본, DAU 5,000, 월 USD 대비)")
    for r in res["sensitivity"]:
        print(f"{r['name']}: {r['low_label']} {r['low_pct']:+.0%} / {r['high_label']} {r['high_pct']:+.0%}")
    print("\n## 제안별 효과 (기본, 1,000 DAU)")
    for r in res["levers"]:
        rng = f"{r['pct_lo']:+.0%}" if abs(r["pct_lo"] - r["pct_hi"]) < 0.005 else f"{r['pct_lo']:+.0%} ~ {r['pct_hi']:+.0%}"
        print(f"{r['name']}: {usd(r['usd_lo'])}~{usd(r['usd_hi'])} ({rng}) — {r['note']}")


# ---------------------------------------------------------------------------------------------
# 상품별 진행 속도(sim.py)


def pass_value(sims: int, horizon_days: float, seed: int) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sim  # noqa: E402

    cfg = sim.load_current("auto")
    game = sim.Game(cfg)
    passes = cfg["passes"]

    def prof(owned: list[str], boosts: float = 0.0, coinpacks: float = 0.0) -> dict:
        p = sim.make_profile(game, "free", boosts, 0.0, coinpacks)
        p["passes"] = owned
        for key, field in (("luck_mult", "luck_mult"), ("cd_mult", "cooldown_mult"), ("income_mult", "income_mult")):
            p[key] = float(math.prod(passes[o].get(field, 1) for o in owned)) if owned else 1.0
        return p

    profiles = [
        ("무료", prof([])),
        ("수입 2배", prof(["DoubleIncome"])),
        ("행운 VIP", prof(["LuckVIP"])),
        ("빠른 굴림", prof(["FastRoll"])),
        ("패스 3종", prof(["DoubleIncome", "LuckVIP", "FastRoll"])),
        # sim 의 "하루" = 온라인 24시간. 하루 20분 하는 사람이 매일 하나씩 사면 = 온라인 20분마다 하나(72개/온라인 하루).
        # 행운 부스트는 15분짜리라 72개 = 75% 켜짐, 96개(15분마다) = 늘 켬
        ("무료 + 행운 부스트 온라인 24시간마다 1번", prof([], boosts=1.0)),
        ("무료 + 행운 부스트 매일 1개(하루 20분 플레이 = 온라인 20분마다, 75% 켜짐)", prof([], boosts=72.0)),
        ("무료 + 행운 부스트 늘 켬(온라인 15분마다 1번 = 하루 96번)", prof([], boosts=96.0)),
        ("무료 + 코인 팩 온라인 24시간마다 1번", prof([], coinpacks=1.0)),
        ("무료 + 코인 팩 매일 1개(하루 20분 플레이 = 온라인 20분마다)", prof([], coinpacks=72.0)),
    ]
    out = []
    for name, p in profiles:
        r = sim.simulate(game, p, sims, seed, horizon_days * sim.DAY, 0.02, "ready", "auto")
        s = sim.summarize(game, r)
        reb = {x["k"]: x for x in s["rebirths"]}
        out.append(
            {
                "name": name,
                "rebirth_s": {k: reb[k]["median_s"] for k in (1, 2, 3, 4, 5)},
                "found_60min": s["early_distinct"]["60min"],
            }
        )
        print(f"[pass-value] {name}: " + ", ".join(f"#{k} {v / 60:.0f}분" for k, v in out[-1]["rebirth_s"].items() if v), file=sys.stderr)
    return {"sims": sims, "horizon_days": horizon_days, "seed": seed, "profiles": out}


# ---------------------------------------------------------------------------------------------
# 그림


def chart(res: dict, out: Path, font_regular: str | None, font_bold: str | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    # 색: dataviz 기본 팔레트(밝은 바탕). 범주 1~3 = 파랑·주황·청록(validate_palette.js 통과), 발산 = 파랑↔빨강
    SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3de"
    BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
    BAND = "#cde2fb"  # 파랑 순차 100

    fallback = ROOT / "tools/store/cache/fonts/NotoSansKR-Black.ttf"
    props = []
    for path in (font_regular, font_bold):
        p = Path(path) if path else (fallback if fallback.exists() else None)
        props.append(font_manager.FontProperties(fname=str(p)) if p and p.exists() else font_manager.FontProperties())
    reg, bold = props
    if font_regular or fallback.exists():
        font_manager.fontManager.addfont(str(reg.get_file()))
        plt.rcParams["font.family"] = reg.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["text.parse_math"] = False  # "$114 (3만 R$)" 처럼 $ 가 둘인 글자를 수식으로 읽지 않게

    fig = plt.figure(figsize=(15.5, 9.6), dpi=150, facecolor=SURFACE)
    fig.text(0.045, 0.955, "LANDMARK RNG! 예상 월 수익", fontsize=20, color=INK, fontproperties=bold, va="top")
    fig.text(
        0.045,
        0.915,
        "개발자가 받는 돈(USD) = (패스·상품 판매 × 70% + Creator Rewards) × DevEx $0.0038.  DAU 가 한 달 내내 유지된다고 볼 때. "
        "시나리오 = 리텐션 + 수익화 한 묶음 — 기본 리텐션은 성공한 게임 중앙값(D1 10.3%·D7 1.6%·D30 0.5%).",
        fontsize=10.5,
        color=INK2,
        va="top",
    )

    # 1) DAU → 월 USD (로그-로그) --------------------------------------------------------------
    ax = fig.add_axes([0.06, 0.12, 0.40, 0.66], facecolor=SURFACE)
    xs = list(DAU_TIERS)
    lo = [r["usd"] for r in res["tiers"]["pess"]]
    mid = [r["usd"] for r in res["tiers"]["base"]]
    hi = [r["usd"] for r in res["tiers"]["opt"]]
    ax.fill_between(xs, lo, hi, color=BAND, linewidth=0, zorder=1)
    ax.plot(xs, mid, color=BLUE, linewidth=2, zorder=3)
    ax.plot(xs, mid, linestyle="none", marker="o", markersize=8, markerfacecolor=BLUE, markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    for x, y, a, b in zip(xs, mid, lo, hi):
        ax.text(x * 1.12, y, usd(y), fontsize=12, color=INK, fontproperties=bold, va="center", ha="left", zorder=5)
        ax.text(x * 1.12, y / 1.9, f"{usd_chart(a)}~{usd_chart(b)}", fontsize=9.5, color=INK2, va="center", ha="left", zorder=5)
    # 지금 · 현실적인 구간 설명(격자선 10,000 과 1,000 사이 한 칸 안 — 격자선을 가리지 않게 배경 없음)
    ax.text(7, 8200, "지금(2026-09-30): 방문 0 · DAU 0", fontsize=11, color=INK, fontproperties=bold, va="top", ha="left")
    ax.text(
        7,
        4300,
        "공개 3일째, 아직 16+ 에게만 보이는 평가 단계. 지금처럼\n한국어 전용이면 DAU 0~10(왼쪽 첫 점)이 현실적",
        fontsize=9.5,
        color=INK2,
        va="top",
        ha="left",
        linespacing=1.4,
        zorder=6,
    )
    # DevEx 최소 인출 = 한 달에 $114 이상이면 매달 인출 가능
    ax.axhline(FACTS["devex_min"] * FACTS["devex"], color=MUTED, linewidth=1, zorder=2)
    ax.text(
        7, FACTS["devex_min"] * FACTS["devex"] * 1.12, "DevEx 최소 인출 $114 (3만 R$)", fontsize=9, color=INK2, va="bottom", ha="left"
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(6, 150000)
    ax.set_ylim(0.15, 40000)
    ax.set_xticks(xs)

    def ccu_label(d: float) -> str:
        c = d * PLAYTIME_MIN_PER_DAU / 1440
        return f"{d:,}\nCCU≈{c:.0f}" if c >= 10 else f"{d:,}\nCCU≈{c:.1f}"

    ax.set_xticklabels([ccu_label(d) for d in xs])
    yt = [1, 10, 100, 1000, 10000]
    ax.set_yticks(yt)
    ax.set_yticklabels([f"${v:,}" for v in yt])
    ax.minorticks_off()
    ax.set_xlabel("하루 활성 사용자(DAU)", color=INK2, fontsize=10.5)
    ax.set_title("DAU별 월 수익", loc="left", fontsize=13.5, color=INK, fontproperties=bold, pad=34)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=10, length=0)
    ax.legend(
        handles=[
            Line2D([], [], color=BLUE, linewidth=2, marker="o", markersize=7, markeredgecolor=SURFACE, label="기본"),
            Rectangle((0, 0), 1, 1, facecolor=BAND, edgecolor="none", label="비관 ~ 낙관(리텐션 + 수익화)"),
        ],
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0),
        frameon=False,
        ncol=2,
        fontsize=10,
        labelcolor=INK,
        borderaxespad=0.2,
    )

    # 2) 1,000 DAU 당 구성(가로 누적 막대) -------------------------------------------------------
    ax2 = fig.add_axes([0.60, 0.60, 0.36, 0.22], facecolor=SURFACE)
    cats = [("dev_passes_robux", "게임패스", BLUE), ("dev_products_robux", "개발자 상품", ORANGE), ("creator_rewards_robux", "Creator Rewards", AQUA)]
    ys = list(range(len(SCEN_ORDER)))[::-1]
    for yi, s in zip(ys, SCEN_ORDER):
        r = res["per_1000_dau"][s]
        left = 0.0
        total_usd = r["usd"]
        for key, _, color in cats:
            w = r[key] * FACTS["devex"]
            ax2.barh(yi, w, left=left, height=0.56, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
            left += w
        ax2.text(left + total_usd * 0.02 + 4, yi, usd(total_usd), va="center", ha="left", fontsize=11, color=INK, fontproperties=bold)
    ax2.set_yticks(ys)
    ax2.set_yticklabels([SCENARIOS[s]["label"] for s in SCEN_ORDER])
    ax2.set_xlim(0, max(res["per_1000_dau"]["opt"]["usd"] * 1.22, 10))
    ax2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax2.set_title("1,000 DAU 당 한 달 — 어디서 나오나", loc="left", fontsize=13.5, color=INK, fontproperties=bold, pad=30)
    ax2.grid(axis="x", color=GRID, linewidth=1)
    ax2.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax2.spines[side].set_visible(False)
    ax2.spines["bottom"].set_color(MUTED)
    ax2.tick_params(colors=INK2, labelsize=10, length=0)
    ax2.legend(
        handles=[Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="none", label=lab) for _, lab, c in cats],
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0),
        frameon=False,
        ncol=3,
        fontsize=10,
        labelcolor=INK,
        borderaxespad=0.2,
    )

    # 3) 민감도(토네이도) ------------------------------------------------------------------------
    ax3 = fig.add_axes([0.60, 0.12, 0.36, 0.34], facecolor=SURFACE)
    sens = sorted(res["sensitivity"], key=lambda r: max(abs(r["low_pct"]), abs(r["high_pct"])))
    for i, r in enumerate(sens):
        for pct, lab in ((r["low_pct"], r["low_label"]), (r["high_pct"], r["high_label"])):
            color = BLUE if pct >= 0 else RED
            ax3.barh(i, pct * 100, height=0.56, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
            ha = "left" if pct >= 0 else "right"
            off = 3 if pct >= 0 else -3
            ax3.text(pct * 100 + off, i, f"{lab} → {pct:+.0%}", va="center", ha=ha, fontsize=9, color=INK2)
    ax3.axvline(0, color=MUTED, linewidth=1, zorder=4)
    ax3.set_yticks(range(len(sens)))
    ax3.set_yticklabels([r["name"] for r in sens])
    span = max(max(abs(r["low_pct"]), abs(r["high_pct"])) for r in sens) * 100
    ax3.set_xlim(-span * 0.95, span * 1.55)
    ax3.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0"))
    ax3.set_title(
        f"무엇이 가장 크게 움직이나 (기본 · DAU 5,000 = 월 {usd(res['sensitivity'][0]['ref_usd'])})",
        loc="left",
        fontsize=13.5,
        color=INK,
        fontproperties=bold,
        pad=10,
    )
    ax3.grid(axis="x", color=GRID, linewidth=1)
    ax3.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax3.spines[side].set_visible(False)
    ax3.spines["bottom"].set_color(MUTED)
    ax3.tick_params(colors=INK2, labelsize=10, length=0)

    fig.text(
        0.045,
        0.035,
        "민감도의 리텐션은 유입(새 사용자/일)을 고정하고 바꿈 — DAU 도 함께 변함(추천 알고리즘이 더 보여 주는 효과는 뺌). "
        "결제 전환·상품 개수는 수명에 따라 늘어남(∝ L^0.8 · L^0.7). "
        "숫자·가정·출처: balance/REVENUE.md · 다시 만들기: python3 tools/balance/revenue_model.py --chart",
        fontsize=8.5,
        color=MUTED,
    )
    fig.savefig(out, facecolor=SURFACE)
    print(f"wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chart", action="store_true", help="balance/revenue_chart.png 도 만듦")
    ap.add_argument("--font-regular")
    ap.add_argument("--font-bold")
    ap.add_argument("--out-png", default=str(OUT_PNG))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--pass-value", action="store_true", help="sim.py 로 상품별 진행 속도 → balance/revenue_pass_value.json")
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--horizon-days", type=float, default=3.0, help="--pass-value: 온라인 시간(일)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    if args.pass_value:
        pv = pass_value(args.sims, args.horizon_days, args.seed)
        PASS_VALUE_JSON.write_text(json.dumps(pv, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {PASS_VALUE_JSON.relative_to(ROOT)}")
        return
    products = load_products()
    res = results(products)
    print_tables(res)
    Path(args.out_json).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"\nwrote {args.out_json}")
    if args.chart:
        chart(res, Path(args.out_png), args.font_regular, args.font_bold)


if __name__ == "__main__":
    main()
