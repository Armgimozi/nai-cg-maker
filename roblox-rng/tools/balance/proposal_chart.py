#!/usr/bin/env python3
"""balance/proposal_table.png — 지금 vs 추천안 환생 진행 속도 그림(제안서 PROPOSAL.md 용).

쓰는 법 (roblox-rng 폴더에서):
  python3 tools/balance/proposal_chart.py
  python3 tools/balance/proposal_chart.py --font-regular 경로.ttf --font-bold 경로.ttf

숫자는 balance/sim_results.json(tools/balance/compare.py 결과)에서 읽음: 400명 몬테카를로 중앙값, 온라인 시간만.
필요: matplotlib. 한글 글꼴(Noto Sans KR 등)을 --font-regular/--font-bold 로 주면 그 글꼴을 씀.
안 주면 tools/store/cache/fonts/NotoSansKR-Black.ttf, 그것도 없으면 matplotlib 기본 글꼴(한글이 네모로 나올 수 있음).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "balance" / "sim_results.json"
OUT = ROOT / "balance" / "proposal_table.png"

# 색: dataviz 기본 팔레트 1·2번(파랑·주황) — validate_palette.js 로 확인(밝은 바탕 전부 통과)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e4e3de"
BAND = "#ecebe6"
REC = "#2a78d6"  # 추천안
CUR = "#eb6834"  # 지금

MIN, HOUR, DAY = 60.0, 3600.0, 86400.0
TARGETS = {1: (15 * MIN, 30 * MIN), 3: (2 * HOUR, 4 * HOUR), 5: (16 * HOUR, 36 * HOUR), 10: (14 * DAY, 42 * DAY)}
TARGET_TEXT = {1: "15~30분", 3: "2~4시간", 5: "약 하루", 10: "2~6주"}


def kdur(s: float) -> str:
    """초 -> '4분' / '2.9시간' / '22.7일' (sim_results.md 와 같은 경계: 90분, 48시간)."""
    if s < 90 * MIN:
        return f"{s / MIN:.0f}분"
    if s < 48 * HOUR:
        return f"{s / HOUR:.1f}시간"
    return f"{s / DAY:.1f}일"


def load() -> dict:
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    out = {}
    for key, label in (("current", "cur"), ("rec", "rec")):
        for kind in ("free", "paid"):
            s = data[f"{key}|{kind}|"]["summary"]
            reb = {r["k"]: r for r in s["rebirths"]}
            tier7 = next(t for t in s["tiers"] if t["rank"] == 7)
            out[(label, kind)] = {
                "median": [reb[k]["median_s"] for k in range(1, 11)],
                "p10": [reb[k]["p10_s"] for k in range(1, 11)],
                "p90": [reb[k]["p90_s"] for k in range(1, 11)],
                "legend_s": tier7["median_s"],
                "legend_run": int(round(tier7["at_rebirth_median"])),
                "rarest_s": s["endgame_max"]["rarest_s"],
                "news_h": data[f"{key}|{kind}|"]["news_by_run"][10],  # 10번째 환생 뒤 판, 1인·1시간
            }
    return out


def setup_fonts(regular: str | None, bold: str | None):
    """(보통, 굵게) FontProperties. 파일로 직접 지정해서 두 굵기가 같은 글꼴 이름이어도 섞이지 않게."""
    fallback = ROOT / "tools/store/cache/fonts/NotoSansKR-Black.ttf"
    props = []
    for path in (regular, bold):
        p = Path(path) if path else (fallback if fallback.exists() else None)
        props.append(font_manager.FontProperties(fname=str(p)) if p and p.exists() else font_manager.FontProperties())
    if regular or fallback.exists():
        font_manager.fontManager.addfont(str(props[0].get_file()))
        plt.rcParams["font.family"] = props[0].get_name()
    return props[0], props[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-regular")
    ap.add_argument("--font-bold")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    reg, bold = setup_fonts(args.font_regular, args.font_bold)
    d = load()

    fig = plt.figure(figsize=(12.8, 9.8), dpi=150, facecolor=SURFACE)
    fig.text(0.055, 0.955, "환생 진행 속도 — 지금 vs 추천안", fontsize=19, color=INK, fontproperties=bold, va="top")
    fig.text(
        0.055,
        0.918,
        "누적 온라인 시간 중앙값(AUTO 굴림, 업그레이드 바로 구매, 조건이 되면 바로 환생). "
        "유료 = 게임패스 3개 + 하루 1번 행운 부스트 15분.",
        fontsize=10.5,
        color=INK2,
        va="top",
    )

    # 위: 선 그래프 ----------------------------------------------------------------------------
    ax = fig.add_axes([0.085, 0.455, 0.70, 0.435], facecolor=SURFACE)
    xs = list(range(1, 11))
    for k, (lo, hi) in TARGETS.items():
        ax.add_patch(Rectangle((k - 0.3, lo), 0.6, hi - lo, facecolor=BAND, edgecolor="none", zorder=0))
        ax.text(k, hi * 1.25, TARGET_TEXT[k], ha="center", va="bottom", fontsize=9, color=INK2)
    # 추천안 무료 p10~p90 (얇은 띠)
    rf = d[("rec", "free")]
    ax.fill_between(xs, rf["p10"], rf["p90"], color=REC, alpha=0.12, linewidth=0, zorder=1)
    series = [
        (("cur", "free"), CUR, "-", "o", SURFACE),
        (("cur", "paid"), CUR, (0, (4, 3)), "o", CUR),
        (("rec", "free"), REC, "-", "o", SURFACE),
        (("rec", "paid"), REC, (0, (4, 3)), "o", REC),
    ]
    for key, color, ls, marker, face in series:
        ys = d[key]["median"]
        ax.plot(xs, ys, color=color, linestyle=ls, linewidth=2, zorder=3)
        ax.plot(
            xs, ys, linestyle="none", marker=marker, markersize=6.5, markerfacecolor=face,
            markeredgecolor=color, markeredgewidth=2, zorder=4,
        )
    # 오른쪽 끝 직접 라벨
    labels = [
        (d[("rec", "free")]["median"][-1], f"추천안 · 무료  {kdur(d[('rec', 'free')]['median'][-1])}", REC),
        (d[("rec", "paid")]["median"][-1], f"추천안 · 유료  {kdur(d[('rec', 'paid')]['median'][-1])}", REC),
        (
            (d[("cur", "free")]["median"][-1] * d[("cur", "paid")]["median"][-1]) ** 0.5,
            f"지금 · 무료/유료  {kdur(d[('cur', 'free')]['median'][-1])} / {kdur(d[('cur', 'paid')]['median'][-1])}",
            CUR,
        ),
    ]
    for y, text, color in labels:
        ax.text(10.35, y, text, va="center", ha="left", fontsize=10, color=INK, fontproperties=bold)
        ax.plot([10.12, 10.28], [y, y], color=color, linewidth=2, clip_on=False)

    ax.set_yscale("log")
    ticks = [MIN, 10 * MIN, HOUR, 4 * HOUR, DAY, 7 * DAY, 28 * DAY]
    ax.set_yticks(ticks)
    ax.set_yticklabels(["1분", "10분", "1시간", "4시간", "1일", "1주", "4주"])
    ax.minorticks_off()
    ax.set_ylim(50, 60 * DAY)
    ax.set_xlim(0.5, 10.5)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{k}번째" for k in xs])
    ax.set_xlabel("환생", color=INK2, fontsize=10)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=10, length=0)
    ax.tick_params(axis="x", pad=6)

    legend = [
        Line2D([], [], color=CUR, linewidth=2, marker="o", markerfacecolor=SURFACE, markeredgewidth=2, label="지금 · 무료"),
        Line2D([], [], color=CUR, linewidth=2, linestyle=(0, (4, 3)), marker="o", markeredgewidth=2, label="지금 · 유료"),
        Line2D([], [], color=REC, linewidth=2, marker="o", markerfacecolor=SURFACE, markeredgewidth=2, label="추천안 · 무료"),
        Line2D([], [], color=REC, linewidth=2, linestyle=(0, (4, 3)), marker="o", markeredgewidth=2, label="추천안 · 유료"),
        Rectangle((0, 0), 1, 1, facecolor=BAND, edgecolor="none", label="목표 범위(무료)"),
        Rectangle((0, 0), 1, 1, facecolor=REC, alpha=0.12, edgecolor="none", label="추천안 무료 p10~p90"),
    ]
    ax.legend(
        handles=legend, loc="upper left", frameon=False, fontsize=9.5, ncol=3, labelcolor=INK,
        bbox_to_anchor=(0.0, 1.0), handlelength=2.6, columnspacing=1.4,
    )

    # 아래: 표 ---------------------------------------------------------------------------------
    cf, cp, rf, rp = d[("cur", "free")], d[("cur", "paid")], d[("rec", "free")], d[("rec", "paid")]

    def at(v, k):
        return kdur(v["median"][k - 1])

    def legend_cell(v):
        return f"{kdur(v['legend_s'])} (환생 {v['legend_run']}번 뒤)"

    rows = [
        ("1번째 환생", "15~30분", at(cf, 1), at(cp, 1), at(rf, 1), at(rp, 1)),
        ("3번째 환생", "2~4시간", at(cf, 3), at(cp, 3), at(rf, 3), at(rp, 3)),
        ("5번째 환생", "약 하루", at(cf, 5), at(cp, 5), at(rf, 5), at(rp, 5)),
        ("10번째 환생 (마지막)", "2~6주", at(cf, 10), at(cp, 10), at(rf, 10), at(rp, 10)),
        ("첫 전설 등급 발견", "중·후반 환생", legend_cell(cf), legend_cell(cp), legend_cell(rf), legend_cell(rp)),
        (
            "세계수 기대 대기 (환생 10 뒤)",
            "며칠~몇 주",
            f"{cf['rarest_s'] / DAY:.0f}일",
            f"{cp['rarest_s'] / DAY:.0f}일",
            f"{rf['rarest_s'] / DAY:.0f}일",
            f"{rp['rarest_s'] / DAY:.0f}일",
        ),
        (
            "서버 속보 / 1인·1시간 (환생 10)",
            "특별하게",
            f"{cf['news_h']:.0f}회",
            f"{cp['news_h']:.0f}회",
            f"{rf['news_h']:.1f}회",
            f"{rp['news_h']:.1f}회",
        ),
    ]
    head = ("", "목표 (무료)", "지금 · 무료", "지금 · 유료", "추천안 · 무료", "추천안 · 유료")
    col_x = [0.055, 0.315, 0.44, 0.565, 0.69, 0.835]
    top, step = 0.315, 0.034
    fig.text(col_x[0], top + 0.045, "숫자로 보면", fontsize=13, color=INK, fontproperties=bold, va="center")
    for i, h in enumerate(head):
        color = CUR if "지금" in h else REC if "추천" in h else INK2
        fig.text(col_x[i], top, h, fontsize=10, color=color if i else INK2, fontproperties=bold, va="center")
    fig.add_artist(Line2D([0.055, 0.965], [top - step * 0.55] * 2, color=MUTED, linewidth=1))
    for r, row in enumerate(rows):
        y = top - step * (r + 1.1)
        if r % 2 == 1:
            fig.add_artist(Rectangle((0.05, y - step / 2), 0.92, step, color="#f3f2ee", zorder=0))
        for i, cell in enumerate(row):
            fig.text(
                col_x[i], y, cell, fontsize=10.5 if i else 10.5, va="center",
                color=INK if i != 1 else INK2, fontproperties=bold if i >= 4 else reg,
            )
    fig.text(
        0.055,
        0.025,
        "근거: tools/balance/sim.py (400명 몬테카를로, 온라인 시간만, AUTO 1회 ≈ 1.4초·희귀 연출 4.8~6.7초). "
        "표·반복 기록: balance/sim_results.md · 추천안 숫자: balance/variant_rec.json",
        fontsize=8.5,
        color=MUTED,
    )
    fig.savefig(args.out, facecolor=SURFACE)
    print(f"wrote {Path(args.out).relative_to(ROOT) if Path(args.out).is_relative_to(ROOT) else args.out}")


if __name__ == "__main__":
    main()
