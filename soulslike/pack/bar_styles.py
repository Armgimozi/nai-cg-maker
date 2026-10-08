"""
HUD 막대의 몸 (채움·잃은 몫·빈 몫·보스 자세 줄) 의 색 짜임 (DESIGN.md 10.1, 10.2). hud.py 가 막대 조각 그림을 만들 때 쓴다.

2026-10-08 사용자 결정: 막대 (체력·마나·스태미나·보스) 는 한 가지 색으로 칠하지 말고 거무칙칙한 여러 색 조합으로, 색 이름은
그대로 읽히게 (체력 붉은 계열, 마나 푸른 계열, 스태미나 초록 계열). 시안 셋 (c1 겹띠, c2 검은 심, c3 녹 빗금,
dist/screenshots/bars/) 가운데 사용자가 c2 "검은 심" 을 골랐다. 견주던 셋의 짜임은 git 의 2026-10-08 판 (커밋 7cc0b28)
pack/bar_styles.py 에 있다. 여기에는 고른 하나만 둔다.

검은 심 (dark core, dim sheen)
  유리관 속의 탁한 물처럼: 몸은 거의 검은 심 (막대 색의 가장 어두운 단, 마른 핏빛·그을음 줄), 위에서 둘째 줄에 흐린 빛 한 줄
  (sheen), 맨 아래 줄에 바닥에서 비친 빛 한 줄. 색 이름은 빛 줄과 심이 정한다 (체력 진홍, 마나 쪽빛, 스태미나 누른 풀·이끼).
  잃은 몫은 같은 관을 탁한 황토로 (흑갈 심, 잉걸 빛 줄), 빈 몫은 빈 유리관 (먹, 빛 줄 자리에 어두운 빛 한 줄, 아래 그을음 입술).
  손으로 정한 줄 (줄마다 한 색, 가로로 고르다). 무늬·점·잡티는 없다: 채움이 줄어도 그림이 기어가지 않고 조각 (1, 2, 4 … 128
  GUI 픽셀) 사이에 이음매가 생기지 않는다 (가로로 고르니 어떤 조각을 어디에 이어도 같다).
  고른 그림 (비교판) 에서 색은 그대로 두고 고친 것 셋 (실제 화면에서 우연히 달라지는 것만 막는다):
    잃은 몫 알파 0.92 → 1     반투명이면 밝은 하늘·벽 모서리가 황토 속에 우연한 꼴로 비친다 (채움은 이미 불투명)
    빈 몫 입술 알파 0.7 → 0.9  밝은 하늘 위에서 그을음 입술이 하늘을 30% 비쳐, 채움 끝 너머에 밝은 줄이 생겼다
    자세 줄 텍셀 13·14 → 14·15 GUI 한 픽셀 경계에 맞춘다: GUI 배율 3 (텍셀 = 화면 1.5 픽셀) 에서 반 픽셀 걸친 줄이 4 픽셀로
                              번졌다. 막대 밑 그늘과 1 GUI 픽셀 띈다

그림 글자에 들어가는 방식 (hud.py, plugin hud/Hud.java)
  막대 한 칸의 세로 줄 = [윗날 RIM][테 FRAME][몸 n 줄][테 FRAME][그늘 DROP] (텍셀, GUI 한 픽셀에 S = 2 텍셀).
  몸: 체력 8 · 마나 6 · 스태미나 6 · 보스 8 텍셀 줄. 채움·잃은 몫·빈 몫이 저마다 폭 1, 2, 4 … 128 GUI 픽셀 조각.
  잃은 몫과 빈 몫은 채움이 끝난 아무 자리에서 시작하므로 가로 무늬를 넣으면 채움이 줄 때 기어간다: 모든 줄이 가로로 고르다.
  보스 자세 줄은 따로 POST_H 텍셀 그림 (보스 막대와 같은 위): POST_ROW 줄부터. 보스 줄 위에서 +17 GUI 를 넘으면 셰이더가 다음
  보스 줄로 읽으므로 그림은 16 텍셀 (8 GUI) 을 넘지 않는다.

쓰는 법: column(bar, kind) 가 막대 한 칸의 세로 줄, run_sheet(col) 이 조각 그림. check() 는 팔레트·제한 계열 (마나는 hud_fp_
그림에만) 과 빈 몫이 채움보다 어두운지를 본다. recipe() 는 줄마다 색·알파 (문서·알림용). python3 bar_styles.py 가 둘을 찍는다.
"""
import numpy as np
from PIL import Image

from palette import C, c, family, luma

S = 2                                       # 텍셀 / GUI 픽셀
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)   # 조각 폭 (GUI 픽셀)
BODY = {"hp": 8, "fp": 6, "st": 6, "boss": 8}

# 테 (초안 그대로): 촛불이 비친 청동 윗날 반 픽셀, 먹 테, 밑 그늘 반 픽셀
RIM = ("bronze2", 0.85)
FRAME = ("ink0", 0.95)
DROP = ("ink0", 0.40)
POST_H, POST_ROW = 16, 14                   # 자세 줄 그림 높이 (텍셀) 와 줄 자리: 막대 밑 그늘 (텍셀 11) 아래 1 GUI 띄고 GUI 7


def _solid(*names, a=1.0):
    return [(n, a) for n in names]


def _post(rows):
    out = [(None, 0)] * POST_H
    for i, r in enumerate(rows):
        out[POST_ROW + i] = r
    return out


def _trough(n):
    """빈 몫 n 줄 (빈 유리관): 먹 (맨 위가 가장 짙다), 채움의 빛 줄 자리에 어두운 빛 한 줄 (ink1), 먹, 그을음 입술."""
    rows = [("ink0", 0.97), ("ink1", 0.90)] + [("ink0", 0.90)] * (n - 3) + [("rust0", 0.90)]
    assert len(rows) == n
    return rows


# 몸 줄 (위 → 아래). 둘째 줄이 흐린 빛, 맨 아래 줄이 비친 빛, 그 사이가 검은 심
FILL = {
    # 진홍 심 / 진홍 빛 / 진홍 / 진홍 심 / 마른 핏빛 심 / 그을음 / 진홍 심 / 마른 핏빛 비친 빛
    "hp": _solid("crimson0", "crimson2", "crimson1", "crimson0", "blood0", "rust0", "crimson0", "blood2"),
    # 푸른 먹 / 쪽빛 빛 / 쪽빛 / 푸른 먹 / 그을음 / 쪽빛 비친 빛 (마나 계열은 hud_fp_ 그림에만, palette.MANA_ART)
    "fp": _solid("mana0", "mana2", "mana1", "mana0", "rust0", "mana1"),
    # 이끼 / 누른 풀 빛 / 누른 풀 / 이끼 / 그을음 / 누른 풀 비친 빛
    "st": _solid("moss0", "sap1", "sap0", "moss0", "rust0", "sap0"),
}
FILL["boss"] = FILL["hp"]
# 잃은 몫 (체력·보스): 같은 관을 탁한 황토로. 흑갈 / 잉걸 빛 / 잉걸 / 흑갈 / 그을음 둘 / 흑갈 / 잉걸 비친 빛. 불투명
TRAIL = _solid("bronze0", "cinder1", "cinder0", "bronze0", "rust0", "rust0", "bronze0", "cinder0")
POST = {
    # 자세 줄 1 GUI 픽셀: 흐린 금 한 줄 + 그을음 그늘
    "fill": _post([("bronze3", 0.95), ("rust0", 0.70)]),
    # 빈 길: 흑갈 한 줄 + 옅은 먹
    "empty": _post([("bronze0", 0.70), ("ink0", 0.40)]),
}


def body(bar, kind):
    """몸 줄 목록 (BODY[bar] 줄). kind: fill, trail, empty."""
    n = BODY[bar]
    rows = {"fill": FILL[bar], "trail": TRAIL, "empty": _trough(n)}[kind]
    assert len(rows) == n, f"{bar} {kind}: 몸 줄 {len(rows)} != {n}"
    return list(rows)


def column(bar, kind):
    """막대 한 칸 세로 줄 (텍셀, 위 → 아래): [(이름, 알파)]. kind: fill, trail, empty, post_fill, post_empty (post_* 는 bar = boss)."""
    if kind.startswith("post_"):
        return list(POST[kind[5:]])
    return [RIM, FRAME] + body(bar, kind) + [FRAME, DROP]


def strip(col, n_gui):
    """길이 n_gui GUI 픽셀 조각 하나: RGBA uint8 배열 (줄 수, n_gui × S). 줄마다 한 색."""
    out = np.zeros((len(col), n_gui * S, 4), np.uint8)
    for y, (nm, a) in enumerate(col):
        if nm is None or a <= 0:
            continue
        r, g, b, _ = c(nm)
        al = int(round(min(1.0, a) * 255))
        if 250 <= al <= 252:                # 발광 알파는 빛 허용 그림만 (artlint glowalpha)
            al = 249
        out[y, :] = (r, g, b, al)
    return out


def run_sheet(col):
    """폭 1, 2, 4 … 128 GUI 픽셀 조각을 256 텍셀 칸 간격으로 한 그림에 (bitmap 글꼴 한 공급자 = 한 그림, 칸 폭이 같다)."""
    cell = RUN_STEPS[-1] * S
    arr = np.zeros((len(col), cell * len(RUN_STEPS), 4), np.uint8)
    for i, n in enumerate(RUN_STEPS):
        arr[:, i * cell:i * cell + n * S] = strip(col, n)
    return Image.fromarray(arr, "RGBA")


SHEETS = (  # (그림 이름, 막대, 종류): hud.py 가 쓰는 그림 이름
    ("hud_hp_fill", "hp", "fill"), ("hud_hp_trail", "hp", "trail"), ("hud_hp_empty", "hp", "empty"),
    ("hud_fp_fill", "fp", "fill"), ("hud_fp_empty", "fp", "empty"),
    ("hud_st_fill", "st", "fill"), ("hud_st_empty", "st", "empty"),
    ("hud_boss_hp_fill", "boss", "fill"), ("hud_boss_hp_trail", "boss", "trail"), ("hud_boss_hp_empty", "boss", "empty"),
    ("hud_boss_post_fill", "boss", "post_fill"), ("hud_boss_post_empty", "boss", "post_empty"),
)


def check():
    """팔레트 밖의 이름, 마나 계열을 hud_fp_ 밖에 쓴 것, 빈 몫이 채움보다 어둡지 않은 막대 (검은 바탕 위 밝기 평균). 문제 목록."""
    bad = []
    for fname, bar, kind in SHEETS:
        for nm, a in column(bar, kind):
            if nm is None:
                continue
            if nm not in C:
                bad.append(f"{fname}: 팔레트에 없는 색 {nm}")
            elif family(nm) == "mana" and not fname.startswith("hud_fp_"):
                bad.append(f"{fname}: 마나 계열 {nm} 은 hud_fp_ 그림에만")
    for bar in BODY:
        fill = sum(luma(C[nm][:3]) * a for nm, a in body(bar, "fill")) / BODY[bar]
        empty = sum(luma(C[nm][:3]) * a for nm, a in body(bar, "empty")) / BODY[bar]
        if empty >= fill:
            bad.append(f"{bar}: 빈 몫 (밝기 평균 {empty:.3f}) 이 채움 ({fill:.3f}) 보다 어둡지 않다")
    return bad


def _row_text(row):
    nm, a = row
    if nm is None:
        return "-"
    return f"{nm} #{'%02x%02x%02x' % C[nm][:3]} a{a:g}"


def recipe():
    """줄마다 색·알파 (위 → 아래)."""
    out = ["frame rows (every bar, every kind): RIM " + _row_text(RIM) + " | FRAME " + _row_text(FRAME)
           + " | ...body... | FRAME | DROP " + _row_text(DROP)]
    for bar in ("hp", "fp", "st", "boss"):
        for kind in ("fill", "trail", "empty"):
            if kind == "trail" and bar not in ("hp", "boss"):
                continue
            rows = body(bar, kind)
            out.append(f"{bar} {kind} ({len(rows)} body rows): " + "; ".join(_row_text(r) for r in rows))
    for kind in ("fill", "empty"):
        lit = [(i, r) for i, r in enumerate(POST[kind]) if r[0] is not None]
        out.append(f"boss posture {kind} ({POST_H}-row glyph, bar top = row 0): "
                   + "; ".join(f"row {i} {_row_text(r)}" for i, r in lit))
    return "\n".join(out)


if __name__ == "__main__":
    print(recipe())
    print("check:", check() or "ok")
