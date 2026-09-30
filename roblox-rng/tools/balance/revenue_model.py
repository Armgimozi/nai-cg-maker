#!/usr/bin/env python3
"""balance/REVENUE.md 용 예상 수익 모델 + 그림(balance/revenue_chart.png).

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/revenue_model.py                  # 표 출력 + balance/revenue_results.json
  python3 tools/balance/revenue_model.py --chart --font-regular R.ttf --font-bold B.ttf   # + 그림
  python3 tools/balance/revenue_model.py --pass-value     # sim.py 로 상품별 진행 속도(약 1분) → balance/revenue_pass_value.json

상품·가격은 src/shared/Config.luau 에서 읽음(가격을 바꾸면 다시 돌리면 됨). 나머지 숫자는 아래 FACTS(출처 있는 사실)와
SCENARIOS·RETENTION·그 밖의 [가정] 값. 출처 목록은 balance/REVENUE.md 끝.

모델(한 달 = 30일, 안정 상태 — 매달 같은 DAU 가 유지된다고 봄):
  * 수명 활동일 L = 1 + Σ_{d=1..180} R(d). R(d) 는 D1·D7·D30 을 지나는 거듭제곱 곡선(구간별), 30일 뒤는 7→30 기울기로 이어감.
  * 새 사용자/달 = DAU × 30 / L (DAU 를 유지하려면 이만큼 들어와야 함).
  * 결제자/달 = 새 사용자 × 평생 결제 전환율. 결제자 1인 = 패스별 구매 확률 + 개발자 상품별 평생 구매 횟수.
  * 총 Robux(플레이어가 쓴 것) = Σ 개수 × 가격 × 지역 가격 실현율(지역 가격 30~100%).
  * 개발자 몫 = 총 Robux × 70% (게임 안 판매 수수료 30%).
  * Creator Rewards(일일 참여 보상) = DAU × Active Spender 비율 × 자격(10분+ · 그날 첫 3개 게임) × 5 R$ × 30일. 수수료 없음.
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
    "devex": 0.0038,  # 1 Earned Robux = $0.0038 (2025-09-05 이후 번 것) [S3]
    "devex_us18": 0.0054,  # 미국 18+ 연령 인증 구매분(패스·개발자 상품, R15 전용 게임만, 2026-06-08~) [S3][S4]
    "devex_min": 30000,  # DevEx 최소 인출 30,000 Earned Robux (= $114) [S3]
    "creator_reward": 5,  # Active Spender 1명이 그날 첫 3개 게임 중 하나로 10분+ 하면 5 R$ [S5]
    "robux_asp": 0.01,  # 플레이어가 1 Robux 를 사는 평균 가격 $0.01 (2025) [S1]
    "days": 30,
}

# [가정] 리텐션(D1, D7, D30). 참고: GameAnalytics 2026 Roblox 벤치마크 중앙값 10.3% / 1.6% / 0.5%, 상위 1% 22.2% / 9.1% / 4.7% [S13]
RETENTION = {
    "pess": (0.07, 0.012, 0.003),
    "base": (0.12, 0.03, 0.01),
    "opt": (0.22, 0.09, 0.045),
}

# [가정] 수익화 시나리오. passes = 결제자 중 그 패스를 사는 비율, products = 결제자 1인 평생 구매 횟수
SCENARIOS = {
    "pess": {
        "label": "비관",
        "payer_conv": 0.002,
        "passes": {"DoubleIncome": 0.35, "LuckVIP": 0.25, "FastRoll": 0.15},
        "products": {"LuckBoost": 1.0, "ServerLuck": 0.1, "CoinPack": 0.2},
        "price_realized": 0.75,
        "active_spender": 0.05,
        "cr_qualify": 0.15,
    },
    "base": {
        "label": "기본",
        "payer_conv": 0.006,
        "passes": {"DoubleIncome": 0.5, "LuckVIP": 0.4, "FastRoll": 0.3},
        "products": {"LuckBoost": 2.0, "ServerLuck": 0.3, "CoinPack": 0.5},
        "price_realized": 0.85,
        "active_spender": 0.08,
        "cr_qualify": 0.30,
    },
    "opt": {
        "label": "낙관",
        "payer_conv": 0.012,
        "passes": {"DoubleIncome": 0.6, "LuckVIP": 0.5, "FastRoll": 0.4},
        "products": {"LuckBoost": 3.0, "ServerLuck": 0.6, "CoinPack": 1.0},
        "price_realized": 0.95,
        "active_spender": 0.11,
        "cr_qualify": 0.50,
    },
}
SCEN_ORDER = ("pess", "base", "opt")

DAU_TIERS = (50, 500, 5000, 50000)
PLAYTIME_MIN_PER_DAU = 20.0  # [가정] 하루 플레이 시간(분) — CCU 환산용. GameAnalytics 중앙값 9.8분 × 1.56번 ≈ 15분 [S13], AUTO 굴림이라 조금 더
CPP_USD = (0.20, 0.45)  # [가정·제3자] 광고 1플레이당 비용: 잘 되는 경우 / 평균 [S14]
PRICE_ELASTICITY = 1.3  # [가정] 가격 +1% → 결제자 -1.3% (가격 최적화 중앙값 +4% [S15] = 지금 가격대가 크게 틀리지 않음)
# [가정] 리텐션이 좋아지면(수명 L ↑) 결제 전환·반복 구매도 늘어남: 전환 ∝ (L/L0)^0.5, 개발자 상품 횟수 ∝ (L/L0)^0.7
RET_CONV_EXP, RET_PRODUCT_EXP = 0.5, 0.7
SAME_DAY_SHARE = 0.5  # [가정] 두 번째부터의 구매 중 앞 구매와 같은 날인 비율 → 결제한 날 = 1 + 0.5 × (개수 - 1)
HORIZON_DAYS = 180


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


def lifetime_days(ret: tuple[float, float, float]) -> float:
    return 1.0 + sum(retention_curve(*ret))


def payer_items(mon: dict) -> float:
    return sum(mon["passes"].values()) + sum(mon["products"].values())


def payer_gross_list(mon: dict, products: dict) -> dict:
    """결제자 1인 평생 총 Robux(정가) — 상품별."""
    out = {pid: share * products[pid]["price"] for pid, share in mon["passes"].items()}
    out.update({pid: n * products[pid]["price"] for pid, n in mon["products"].items()})
    return out


def monthly(dau: float, mon: dict, products: dict, ret=RETENTION["base"], us18_share: float = 0.0) -> dict:
    """DAU 가 한 달 내내 유지될 때 그 달의 수익."""
    days = FACTS["days"]
    L = lifetime_days(ret)
    new_users = dau * days / L
    payers = new_users * mon["payer_conv"]
    per_item_list = payer_gross_list(mon, products)
    realized = mon["price_realized"]
    by_product = {pid: payers * v * realized for pid, v in per_item_list.items()}
    gross = sum(by_product.values())
    dev = gross * FACTS["dev_share"]
    cr = dau * mon["active_spender"] * mon["cr_qualify"] * FACTS["creator_reward"] * days
    earned = dev + cr
    rate = FACTS["devex"] * (1 - us18_share) + FACTS["devex_us18"] * us18_share
    # 대시보드 지표(하루 평균)
    items = payer_items(mon)
    pay_days = 1 + (1 - SAME_DAY_SHARE) * max(0.0, items - 1)
    daily_payers = payers * pay_days / days
    gross_day = gross / days
    passes = sum(v for pid, v in by_product.items() if products[pid]["kind"] == "pass")
    return {
        "dau": dau,
        "lifetime_days": L,
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
        "usd": dev * rate + cr * FACTS["devex"],  # Creator Rewards 는 게임 판매가 아니라 18+ 환율 대상 아님
        "player_spend_usd": gross * FACTS["robux_asp"],
        "months_to_devex": FACTS["devex_min"] / earned if earned > 0 else math.inf,
        "ccu": dau * PLAYTIME_MIN_PER_DAU / 1440,
        "dash_conversion": daily_payers / dau,
        "dash_arppu_robux": gross_day / daily_payers if daily_payers else 0.0,
        "dash_arpdau_robux": gross_day / dau,
        "ltv_new_user_usd": (dev / new_users + cr / new_users) * FACTS["devex"],
    }


def with_changes(mon: dict, conv=1.0, spend=1.0, products_mult=1.0, price=1.0, realized=None, qualify=None) -> dict:
    m = copy.deepcopy(mon)
    m["payer_conv"] *= conv * price**-PRICE_ELASTICITY
    m["passes"] = {k: v * spend for k, v in m["passes"].items()}
    m["products"] = {k: v * spend * products_mult for k, v in m["products"].items()}
    m["price_realized"] *= price
    if realized is not None:
        m["price_realized"] = realized
    if qualify is not None:
        m["cr_qualify"] = qualify
    return m


def fixed_inflow(new_per_day: float, mon: dict, products: dict, ret: tuple) -> dict:
    """새 사용자 유입(하루)을 고정하고 리텐션을 바꿈: DAU = 유입 × L, 전환·반복 구매는 L 에 따라 늘어남."""
    L0 = lifetime_days(RETENTION["base"])
    L = lifetime_days(ret)
    m = copy.deepcopy(mon)
    m["payer_conv"] *= (L / L0) ** RET_CONV_EXP
    m["products"] = {k: v * (L / L0) ** RET_PRODUCT_EXP for k, v in m["products"].items()}
    return monthly(new_per_day * L, m, products, ret)


def sensitivity(products: dict, dau: float = 5000) -> list[dict]:
    """기본 시나리오, DAU 5,000(= 유입 고정) 기준으로 한 가지씩 바꿨을 때 월 USD 변화."""
    base = SCENARIOS["base"]
    ref = monthly(dau, base, products)["usd"]
    inflow = dau / lifetime_days(RETENTION["base"])
    rows = [
        (
            "리텐션 D1·D7·D30",
            "7%·1.2%·0.3%",
            "22%·9%·4.5%",
            fixed_inflow(inflow, base, products, RETENTION["pess"])["usd"],
            fixed_inflow(inflow, base, products, RETENTION["opt"])["usd"],
        ),
        (
            "결제 전환율",
            "×0.5 (0.3%)",
            "×2 (1.2%)",
            monthly(dau, with_changes(base, conv=0.5), products)["usd"],
            monthly(dau, with_changes(base, conv=2.0), products)["usd"],
        ),
        (
            "결제자 1인 구매 개수",
            "×0.6",
            "×1.6",
            monthly(dau, with_changes(base, spend=0.6), products)["usd"],
            monthly(dau, with_changes(base, spend=1.6), products)["usd"],
        ),
        (
            "10분+ 플레이 비율(Creator Rewards)",
            "15%",
            "50%",
            monthly(dau, with_changes(base, qualify=0.15), products)["usd"],
            monthly(dau, with_changes(base, qualify=0.50), products)["usd"],
        ),
        (
            "지역 가격 실현율",
            "75%",
            "95%",
            monthly(dau, with_changes(base, realized=0.75), products)["usd"],
            monthly(dau, with_changes(base, realized=0.95), products)["usd"],
        ),
        (
            "모든 가격",
            "-25%",
            "+25%",
            monthly(dau, with_changes(base, price=0.75), products)["usd"],
            monthly(dau, with_changes(base, price=1.25), products)["usd"],
        ),
    ]
    out = []
    for name, lo_txt, hi_txt, lo, hi in rows:
        out.append(
            {"name": name, "low_label": lo_txt, "high_label": hi_txt, "low_pct": lo / ref - 1, "high_pct": hi / ref - 1, "ref_usd": ref}
        )
    return out


def levers(products: dict, dau: float = 1000) -> list[dict]:
    """제안별 대략 효과(기본 시나리오, 1,000 DAU). 효과 크기는 모두 [가정]."""
    base = SCENARIOS["base"]
    ref = monthly(dau, base, products)
    inflow = dau / lifetime_days(RETENTION["base"])
    out = []

    def add(name, res, note):
        out.append({"name": name, "usd": res["usd"], "pct": res["usd"] / ref["usd"] - 1, "note": note})

    # 스타터 팩 99 R$: 결제 전환 ×1.25, 결제자 40% 가 삼
    sp = copy.deepcopy(products)
    sp["StarterPack"] = {"kind": "product", "name": "스타터 팩", "price": 99, "active": True}
    m = with_changes(base, conv=1.25)
    m["products"]["StarterPack"] = 0.4
    add("첫 구매 스타터 팩(99 R$, 한 번만)", monthly(dau, m, sp), "결제 전환 ×1.25 + 결제자 40% 구매")
    add("상황별 구매 제안(첫 환생 뒤·코인 모자랄 때)", monthly(dau, with_changes(base, conv=1.2), products), "결제 전환 ×1.2")
    add("반복 상품을 쓸모 있게(수입 부스트·큰 코인 팩)", monthly(dau, with_changes(base, products_mult=1.6), products), "개발자 상품 구매 ×1.6")
    better = (
        RETENTION["base"][0] + 0.03,
        RETENTION["base"][1] + 0.01,
        RETENTION["base"][2] + 0.004,
    )
    add("일일 보상·연속 접속·오프라인 수입(상한)", fixed_inflow(inflow, base, products, better), "D1 +3%p, D7 +1%p, D30 +0.4%p (유입 고정)")
    add("R15 전용 → 미국 18+ DevEx $0.0054", monthly(dau, base, products, us18_share=0.05), "개발자 몫의 5% 가 미국 18+ 인증 구매라고 가정")
    return out


def results(products: dict) -> dict:
    tiers = {s: [monthly(d, SCENARIOS[s], products) for d in DAU_TIERS] for s in SCEN_ORDER}
    per1k = {s: monthly(1000, SCENARIOS[s], products) for s in SCEN_ORDER}
    ret_L = {k: lifetime_days(v) for k, v in RETENTION.items()}
    ads = []
    for d in DAU_TIERS:
        new_day = d / ret_L["base"]
        ads.append(
            {
                "dau": d,
                "new_per_day": new_day,
                "ccu": d * PLAYTIME_MIN_PER_DAU / 1440,
                "ads_usd_month": [new_day * c * FACTS["days"] for c in CPP_USD],
                "base_usd": tiers["base"][DAU_TIERS.index(d)]["usd"],
            }
        )
    return {
        "facts": FACTS,
        "retention": {k: {"d": v, "lifetime_days": ret_L[k]} for k, v in RETENTION.items()},
        "scenarios": SCENARIOS,
        "products": products,
        "dau_tiers": DAU_TIERS,
        "tiers": tiers,
        "per_1000_dau": per1k,
        "ads": ads,
        "cpp_usd": CPP_USD,
        "sensitivity": sensitivity(products),
        "levers": levers(products),
        "assumptions": {
            "playtime_min_per_dau": PLAYTIME_MIN_PER_DAU,
            "price_elasticity": PRICE_ELASTICITY,
            "ret_conv_exp": RET_CONV_EXP,
            "ret_product_exp": RET_PRODUCT_EXP,
            "same_day_share": SAME_DAY_SHARE,
            "horizon_days": HORIZON_DAYS,
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
    return f"${v:.3f}"


def rbx(v: float) -> str:
    if v >= 1e6:
        return f"{v / 1e6:.2f}M"
    if v >= 1e4:
        return f"{v / 1e3:.0f}K"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:.0f}"


def print_tables(res: dict) -> None:
    p = res["products"]
    print("상품:", ", ".join(f"{k} {v['price']} R$" for k, v in p.items()))
    print("수명 활동일 L:", {k: round(v["lifetime_days"], 2) for k, v in res["retention"].items()})
    print("\n## DAU별 월 수익 (리텐션 기본)")
    print("| DAU | 시나리오 | 플레이어가 쓴 Robux | 개발자 몫(70%) | Creator Rewards | 합계 Earned R$ | USD(DevEx) | DevEx 최소까지 |")
    print("|---|---|---|---|---|---|---|---|")
    for i, d in enumerate(DAU_TIERS):
        for s in SCEN_ORDER:
            r = res["tiers"][s][i]
            mt = r["months_to_devex"]
            print(
                f"| {d:,} | {SCENARIOS[s]['label']} | {rbx(r['gross_robux'])} | {rbx(r['dev_robux'])} | {rbx(r['creator_rewards_robux'])} |"
                f" {rbx(r['earned_robux'])} | {usd(r['usd'])} | {mt:.1f}달 |"
            )
    print("\n## 1,000 DAU 당 (한 달)")
    for s in SCEN_ORDER:
        r = res["per_1000_dau"][s]
        print(
            f"{SCENARIOS[s]['label']}: 새 사용자 {r['new_users']:,.0f} · 결제자 {r['payers']:.0f} · 총 {rbx(r['gross_robux'])} R$ "
            f"(패스 {rbx(r['passes_robux'])} / 상품 {rbx(r['products_robux'])}) · 개발자 {rbx(r['dev_robux'])} + CR {rbx(r['creator_rewards_robux'])}"
            f" = {rbx(r['earned_robux'])} R$ = {usd(r['usd'])} · 대시보드 전환율 {r['dash_conversion']:.2%} · ARPPU {r['dash_arppu_robux']:.0f} R$"
            f" · ARPDAU {r['dash_arpdau_robux']:.2f} R$ · 새 사용자 1명 가치 {usd(r['ltv_new_user_usd'])}"
        )
        print("   상품별(총 R$):", {k: round(v) for k, v in r["by_product_robux"].items()})
    print("\n## 트래픽 티어와 광고비(기본 리텐션)")
    for a in res["ads"]:
        print(
            f"DAU {a['dau']:,}: 새 사용자 {a['new_per_day']:,.0f}/일 · CCU ≈ {a['ccu']:.1f} · 전부 광고로면 월 "
            f"{usd(a['ads_usd_month'][0])}~{usd(a['ads_usd_month'][1])} vs 기본 수익 {usd(a['base_usd'])}"
        )
    print("\n## 민감도 (기본, DAU 5,000, 월 USD 대비)")
    for r in res["sensitivity"]:
        print(f"{r['name']}: {r['low_label']} {r['low_pct']:+.0%} / {r['high_label']} {r['high_pct']:+.0%}")
    print("\n## 제안별 효과 (기본, 1,000 DAU)")
    for r in res["levers"]:
        print(f"{r['name']}: {usd(r['usd'])} ({r['pct']:+.0%}) — {r['note']}")


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
        ("무료 + 행운 부스트 하루 1번", prof([], boosts=1.0)),
        ("무료 + 코인 팩 하루 1번", prof([], coinpacks=1.0)),
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

    fig = plt.figure(figsize=(15.5, 9.6), dpi=150, facecolor=SURFACE)
    fig.text(0.045, 0.955, "LANDMARK RNG! 예상 월 수익", fontsize=20, color=INK, fontproperties=bold, va="top")
    fig.text(
        0.045,
        0.915,
        "개발자가 받는 돈(USD) = (패스·상품 판매 × 70% + Creator Rewards) × DevEx $0.0038.  DAU 가 한 달 내내 유지된다고 볼 때. "
        "리텐션은 기본(D1 12%·D7 3%·D30 1%).",
        fontsize=10.5,
        color=INK2,
        va="top",
    )

    # 1) DAU → 월 USD (로그-로그) --------------------------------------------------------------
    ax = fig.add_axes([0.06, 0.12, 0.42, 0.72], facecolor=SURFACE)
    xs = list(DAU_TIERS)
    lo = [r["usd"] for r in res["tiers"]["pess"]]
    mid = [r["usd"] for r in res["tiers"]["base"]]
    hi = [r["usd"] for r in res["tiers"]["opt"]]
    ax.fill_between(xs, lo, hi, color=BAND, linewidth=0, zorder=1)
    ax.plot(xs, mid, color=BLUE, linewidth=2, zorder=3)
    ax.plot(xs, mid, linestyle="none", marker="o", markersize=8, markerfacecolor=BLUE, markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    for x, y, a, b in zip(xs, mid, lo, hi):
        ax.text(x * 1.12, y, usd(y), fontsize=12, color=INK, fontproperties=bold, va="center", ha="left", zorder=5)
        ax.text(x * 1.12, y / 1.9, f"{usd(a)}~{usd(b)}", fontsize=9.5, color=INK2, va="center", ha="left", zorder=5)
    # DevEx 최소 인출 = 한 달에 $114 이상이면 매달 인출 가능
    ax.axhline(FACTS["devex_min"] * FACTS["devex"], color=MUTED, linewidth=1, zorder=2)
    ax.text(
        38, FACTS["devex_min"] * FACTS["devex"] * 1.12, "DevEx 최소 인출 $114 (3만 R$)", fontsize=9, color=INK2, va="bottom", ha="left"
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(35, 150000)
    ax.set_ylim(0.5, 60000)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{d:,}\nCCU≈{d * PLAYTIME_MIN_PER_DAU / 1440:.0f}" if d >= 500 else f"{d:,}\nCCU≈1" for d in xs])
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
            Rectangle((0, 0), 1, 1, facecolor=BAND, edgecolor="none", label="비관 ~ 낙관"),
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
            ax3.text(pct * 100 + off, i, f"{lab}  {pct:+.0%}", va="center", ha=ha, fontsize=9, color=INK2)
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
        "리텐션은 유입(새 사용자/일)을 고정하고 바꿈 — DAU 도 함께 변함(추천 알고리즘이 더 보여 주는 효과는 뺌). "
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
