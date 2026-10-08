"""
HUD 막대의 몸 (채움·잃은 몫·빈 몫·보스 자세 줄) 의 색 짜임 (DESIGN.md 10.1, 10.2). hud.py 가 막대 조각 그림을 만들 때 쓴다.

2026-10-08 사용자 결정: 막대 (체력·마나·스태미나·보스) 는 한 가지 색으로 칠하지 말고 거무칙칙한 여러 색 조합으로, 색 이름은
그대로 읽히게 (체력 붉은 계열, 마나 푸른 계열, 스태미나 초록 계열). 시안 셋 (c1 겹띠, c2 검은 심, c3 녹 빗금) 을 그려 견주고
c1 "겹띠" 를 골라 다듬었다 (비교판과 셋의 짜임은 git 의 2026-10-08 판 pack/bar_styles.py, dist/screenshots/bars/).

겹띠 (layered murk bands)
  막대 색은 윗부분만 정한다. 아래는 다른 계열의 어두운 띠 (흑갈 bronze0, 그을음 rust0, 이끼 moss0) 가 같은 밝기에서 색만
  바꿔 받친다: 어두운 줄무늬가 아니라 "그을린 홈에 고인 탁한 물" 처럼 색이 바뀐다. 잃은 몫도 같은 자리에서 같은 흑갈로 갈려
  채움과 한 물로 읽힌다. 빈 몫은 막대 색 없이 먹 (위가 가장 짙고) 과 녹·흑갈 입술 셋 (한 색 판이 아니다): 막대 색 앙금을
  빈 몫에 깔면 바닥 근처에서 아직 남은 것처럼 보였다.
  손으로 정한 띠 (줄마다 한 색, 가로로 고르다). 무늬·점·잡티는 없다: 채움이 줄어도 그림이 기어가지 않고 조각 (1, 2, 4 … 128
  GUI 픽셀) 사이에 이음매가 생기지 않는다 (가로로 고르니 어떤 조각을 어디에 이어도 같다).

그림 글자에 들어가는 방식 (hud.py, plugin hud/Hud.java)
  막대 한 칸의 세로 줄 = [윗날 RIM][테 FRAME][몸 n 줄][테 FRAME][그늘 DROP] (텍셀, GUI 한 픽셀에 S = 2 텍셀).
  몸: 체력 8 · 마나 6 · 스태미나 6 · 보스 8 텍셀 줄. 채움·잃은 몫·빈 몫이 저마다 폭 1, 2, 4 … 128 GUI 픽셀 조각.
  GUI 배율 3 에서 텍셀 하나는 화면 1.5 픽셀이라 (글꼴 셰이더의 넓이 평균) 홀수 텍셀 경계는 반쯤 섞인다: 색이 바뀌는 큰 경계
  (체력의 붉음 → 흑갈, 몸 줄 4 = 텍셀 6) 와 자세 줄 (텍셀 14·15) 은 GUI 픽셀 경계에 둔다.
  보스 자세 줄은 따로 POST_H 텍셀 그림 (보스 막대와 같은 위): POST_ROW 줄부터. 보스 줄 위에서 +17 GUI 를 넘으면 셰이더가 다음
  보스 줄로 읽으므로 그림은 16 텍셀 (8 GUI) 을 넘지 않는다.

쓰는 법: column(bar, kind) 가 막대 한 칸의 세로 줄, run_sheet(col) 이 조각 그림. check() 는 팔레트·제한 계열 (마나는 hud_fp_ 그림에만)
과 빈 몫이 채움보다 어두운지를 본다. recipe() 는 줄마다 색·알파 (문서·알림용).
"""
from PIL import Image

import numpy as np

from palette import C, c, family, luma

S = 2                                       # 텍셀 / GUI 픽셀
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)   # 조각 폭 (GUI 픽셀)
BODY = {"hp": 8, "fp": 6, "st": 6, "boss": 8}

# 테 (초안 그대로): 촛불이 비친 청동 윗날 반 픽셀, 먹 테, 밑 그늘 반 픽셀
RIM = ("bronze2", 0.85)
FRAME = ("ink0", 0.95)
DROP = ("ink0", 0.40)
POST_H, POST_ROW = 16, 14                   # 자세 줄 그림 높이 (텍셀) 와 줄 자리: 막대 밑 그늘 (텍셀 11) 아래 1 GUI 띄고 GUI 7


def _trough(n):
    """
    빈 몫 n 줄: 먹 (위가 가장 짙고, 가운데 90% 라 뒤 풍경이 비치지 않는다), 아래 입술은 그을음 → 흑갈 (채움 아랫줄과 같은 계열,
    빈 자리에서 밝은 회색 선이 되지 않게). 막대 색은 넣지 않는다.
    """
    rows = [("ink0", 0.97), ("ink0", 0.92)] + [("ink0", 0.90)] * max(0, n - 4) + [("rust0", 0.85), ("bronze0", 0.85)]
    return rows[:n]


def _solid(*names):
    return [(n, 1.0) for n in names]


def _post(rows):
    out = [(None, 0)] * POST_H
    for i, r in enumerate(rows):
        out[POST_ROW + i] = r
    return out


# 몸 줄 (위 → 아래). 잃은 몫은 체력과 보스만 (마나·스태미나는 그리지 않는다)
FILL = {
    # 마른 핏빛 윗날 한 줄, 진홍 셋, 흑갈 셋, 그을음 (붉음 → 흑갈 경계는 몸 줄 4 = GUI 픽셀 경계)
    "hp": _solid("blood2", "crimson1", "crimson1", "crimson1", "bronze0", "bronze0", "bronze0", "rust0"),
    # 쪽빛 셋, 흑갈, 그을음, 맨 아래 푸른 먹 (밝기가 아래로 고르게 내려간다: 쪽빛 줄 밑에 밝은 회색 줄이 생기지 않게)
    "fp": _solid("mana2", "mana1", "mana1", "bronze0", "rust0", "mana0"),
    # 누른 풀 셋, 이끼, 흑갈, 그을음
    "st": _solid("sap1", "sap0", "sap0", "moss0", "bronze0", "rust0"),
}
FILL["boss"] = FILL["hp"]
# 잃은 몫: 탁한 황토 넷 위에 채움과 같은 자리의 흑갈 셋, 그을음. 불투명 (반투명이면 뒤 풍경이 우연한 꼴로 비친다)
TRAIL = _solid("cinder1", "cinder0", "cinder0", "cinder0", "bronze0", "bronze0", "bronze0", "rust0")
POST = {
    # 자세 줄 1 GUI 픽셀: 위에서 비친 흐린 금 + 청동 그늘
    "fill": _post([("bronze3", 0.95), ("bronze1", 0.95)]),
    # 빈 길: 옅은 청동 한 줄 (어두운 곳에서도 자세 줄 길이가 보인다) + 먹
    "empty": _post([("bronze1", 0.60), ("ink0", 0.50)]),
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
