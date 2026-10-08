"""
막대 채움 말씨 (2026-10-08 사용자 결정: 막대는 한 가지 색이 아니라 거무칙칙한 여러 색 조합, 색 이름은 그대로 읽히게).
hud.py 가 나중에 읽을 자료와 그리기 도우미만 둔다 (아직 hud.py 에 잇지 않았다). 팔레트 이름만 쓴다 (palette.py, artlint).

그림 글자에 들어가는 방식 (hud.py, plugin hud/Hud.java)
  막대 한 칸의 세로 줄 = [윗날 RIM][테 FRAME][몸 n 줄][테 FRAME][그늘 DROP] (텍셀, GUI 한 픽셀에 S = 2 텍셀).
  몸: 체력 8 · 마나 6 · 스태미나 6 · 보스 8 텍셀 줄. 채움·잃은 몫·빈 몫이 저마다 폭 1, 2, 4 … 128 GUI 픽셀 조각 (run) 이고
  플러그인은 128 → 1 큰 조각부터 놓는다. 그래서 폭 s 조각은 늘 그 몫의 시작에서 (n − n mod 2s) GUI 픽셀에서 시작한다:
  채움 안에서 가로 무늬의 주기가 2 GUI 픽셀 (PERIOD = 4 텍셀) 이하이면 조각마다 같은 그림 (위상 0) 으로 이음매 없이 잇는다.
  잃은 몫과 빈 몫은 채움이 끝난 아무 자리에서 시작하므로 가로 무늬를 넣지 않는다 (넣으면 채움이 줄 때 무늬가 기어간다):
  줄 (가로로 고른 띠) 만 쓴다. 보스 막대는 셰이더가 가운데를 축으로 1 ~ 2.5 배 늘인다 (자동 GUI 배율인 1920×1080 GUI 4,
  1280×720 GUI 3 에서는 1 배): 채움 무늬도 그만큼 넓어질 뿐 이음매는 생기지 않는다 (막대 왼쪽 끝이 무늬 0 번 칸 그대로).
  GUI 배율 3 에서 텍셀 하나는 화면 1.5 픽셀이라 (글꼴 셰이더의 넓이 평균) 한 텍셀짜리 줄은 반쯤 섞인다: 띠는 되도록 짝수
  텍셀 (GUI 한 픽셀) 로 잡고, 한 텍셀 줄은 윗날 빛처럼 흐려져도 되는 곳에만.

줄 표기 (ROW)
  (이름, 알파)                      한 색 줄
  ((이름, 이름, 이름, 이름), 알파)   주기 PERIOD 텍셀 무늬 줄 (조각의 왼쪽 끝이 무늬 0 번 칸). 채움에만
  (None, 0)                         빈 줄 (자세 줄 그림의 위·아래)

말씨 (STYLES): 'flat' 은 지금 그림 (대조용), 'c1' 'c2' 'c3' 이 시안 셋. 시안은 모두 팔레트 안의 색만 쓴다 (새 색 없음).
  셋 다 막대 높이·테 (RIM·FRAME·DROP)·초안 마구리는 그대로 두고 몸 줄만 바꾼다. 색 이름은 윗부분이 정한다 (체력 진홍,
  마나 쪽빛, 스태미나 누른 풀), 나머지 줄이 그것을 거무칙칙하게 만든다 (그을음 rust0, 흑갈 bronze0, 재 ash1, 이끼 moss).
  c1 겹띠      위 절반은 막대 색, 아래는 다른 계열의 어두운 띠 (체력: 진홍 위에 흑갈·그을음, 마나: 쪽빛 위에 재·그을음,
               스태미나: 풀빛 위에 이끼·흑갈). 잃은 몫도 같은 짜임 (황토 위에 흑갈), 빈 몫에는 막대 색의 앙금 한 줄.
  c2 검은 심   유리관처럼: 몸은 거의 검은 심 (그을음 줄 하나), 위에서 둘째 줄에 흐린 빛 한 줄, 맨 아래에 비친 빛 한 줄.
               빈 몫도 같은 높이에 어두운 빛 줄 (빈 유리관).
  c3 녹 빗금   위는 막대 색, 아래 절반에 녹 (흑갈·그을음) 빗금이 45° 로 새겨진다 (2 텍셀 금, 주기 4 텍셀 = 2 GUI 픽셀,
               채움에서만). 자세 줄은 두 가닥 꼰 끈. artlint 의 repeat 경고 (같은 4×4 조각) 가 72 건 난다 (오류는 아니다):
               주기 PERIOD 의 채움 무늬는 찍어 늘어놓은 무늬가 아니라 깔린 결이라 artlint 에서 hud_*_fill 의 x 주기 반복을
               빼 주는 것이 맞다 (곧은 줄을 빼 주는 것과 같은 까닭).
쓰는 법 (hud.py 에 이을 때): column(style, bar, kind) 가 hud.py 의 column() 자리를, run_sheet(col) 이 run_sheet() 자리를
  갈음한다 (막대 높이·자리·마구리는 그대로). check(style) 은 팔레트·제한 계열 (마나는 hud_fp_ 그림에만) 을 본다.
"""
import numpy as np
from PIL import Image

from palette import C, c, family

S = 2                                       # 텍셀 / GUI 픽셀
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)   # 조각 폭 (GUI 픽셀)
PERIOD = 4                                  # 채움 가로 무늬의 주기 (텍셀) = 2 GUI 픽셀: 큰 조각부터 놓는 한 이음매가 없다
BODY = {"hp": 8, "fp": 6, "st": 6, "boss": 8}

# 테 (초안·지금 그대로): 촛불이 비친 청동 윗날 반 픽셀, 먹 테, 밑 그늘 반 픽셀
RIM = ("bronze2", 0.85)
FRAME = ("ink0", 0.95)
DROP = ("ink0", 0.40)
POST_H, POST_ROW = 16, 13                   # 자세 줄 그림 높이 (텍셀, 보스 막대와 같은 위) 와 줄 자리 (막대 밑 그늘 다음)


def _post(rows):
    """자세 줄 그림 한 칸 (POST_H 줄): POST_ROW 부터 rows."""
    out = [(None, 0)] * POST_H
    for i, r in enumerate(rows):
        out[POST_ROW + i] = r
    return out


def _trough(n, mid=("ink0", 0.82), top=(("ink0", 0.97), ("ink0", 0.88)), lip=(("rust0", 0.80), ("rust1", 0.55))):
    """빈 몫 n 줄: 위가 가장 어둡고 (top), 가운데 mid, 아래에 녹슨 입술 (lip)."""
    rows = list(top) + [mid] * max(0, n - len(top) - len(lip)) + list(lip)
    return rows[:n]


# ─────────────────────────── 말씨 ───────────────────────────
#
# 열쇠: fill / trail / empty 는 막대 (hp, fp, st, boss) → 몸 줄 목록 (위 → 아래, BODY 줄), post 는 fill / empty → 자세 줄 그림.
# 잃은 몫은 체력 (hp) 과 보스 (boss) 만 (마나·스태미나는 잃은 몫을 그리지 않는다).

def _rot(t, k):
    """무늬 줄 t 를 k 텍셀 오른쪽으로 민 것 (빗금: 줄마다 한 텍셀씩)."""
    k %= len(t)
    return tuple(t[-k:] + t[:-k]) if k else tuple(t)


def _hatch(line, ground, n):
    """빗금 n 줄: 2 텍셀 폭 금 (line) 이 줄마다 한 텍셀씩 오른쪽으로 밀려 45° 로 내려간다 (주기 PERIOD, 바탕 ground)."""
    return [(_rot((line, line, ground, ground), k), 1) for k in range(n)]


_FLAT_TRAIL = (("cinder2", 0.8),) + (("cinder1", 0.84),) * 5 + (("cinder0", 0.84),) * 2

STYLES = {
    # 지금 그림 (2026-10-08 고딕 촛불 다듬기 판, 대조용): 윗줄 한 단 밝고 나머지는 거의 한 색
    "flat": {
        "name": "지금 (한 색, 대조)",
        "fill": {
            "hp": [("crimson3", 1), ("crimson2", 1), ("crimson2", 1), ("crimson2", 1), ("crimson2", 1),
                   ("crimson1", 1), ("crimson1", 1), ("crimson0", 1)],
            "fp": [("mana3", 1), ("mana2", 1), ("mana2", 1), ("mana2", 1), ("mana1", 1), ("mana0", 1)],
            "st": [("sap3", 1), ("sap2", 1), ("sap2", 1), ("sap2", 1), ("sap1", 1), ("sap0", 1)],
            "boss": [("crimson3", 1), ("crimson2", 1), ("crimson2", 1), ("crimson2", 1), ("crimson2", 1),
                     ("crimson1", 1), ("crimson1", 1), ("crimson0", 1)],
        },
        "trail": {"hp": list(_FLAT_TRAIL), "boss": list(_FLAT_TRAIL)},
        "empty": {b: _trough(n) for b, n in BODY.items()},
        "post": {"fill": _post([("bronze3", 0.95)]), "empty": _post([("bronze1", 0.6)])},
    },
    "c1": {
        "name": "겹띠", "en": "layered murk bands",
        "fill": {
            "hp": [("blood2", 1), ("crimson1", 1), ("crimson1", 1), ("crimson1", 1), ("blood1", 1), ("bronze0", 1),
                   ("bronze0", 1), ("rust0", 1)],
            "fp": [("mana2", 1), ("mana1", 1), ("mana1", 1), ("ash1", 1), ("rust0", 1), ("mana0", 1)],
            "st": [("sap1", 1), ("sap0", 1), ("sap0", 1), ("moss1", 1), ("bronze0", 1), ("rust0", 1)],
            "boss": [("blood2", 1), ("crimson1", 1), ("crimson1", 1), ("crimson1", 1), ("blood1", 1), ("bronze0", 1),
                     ("bronze0", 1), ("rust0", 1)],
        },
        "trail": {"hp": [("cinder1", .9), ("cinder0", .9), ("cinder0", .9), ("cinder0", .9), ("cinder0", .9),
                         ("bronze0", .9), ("bronze0", .9), ("rust0", .9)]},
        "empty": {b: _trough(n, mid=("ink0", 0.85), lip=((t, 0.85), ("rust0", 0.8), ("rust1", 0.55)))
                  for b, n, t in (("hp", 8, "blood0"), ("fp", 6, "mana0"), ("st", 6, "moss0"), ("boss", 8, "blood0"))},
        "post": {"fill": _post([("bronze3", .95), ("bronze1", .95)]), "empty": _post([("bronze0", .7), ("ink0", .5)])},
    },
    "c2": {
        "name": "검은 심", "en": "dark core, dim sheen",
        "fill": {
            "hp": [("crimson0", 1), ("crimson2", 1), ("crimson1", 1), ("crimson0", 1), ("blood0", 1), ("rust0", 1),
                   ("crimson0", 1), ("blood2", 1)],
            "fp": [("mana0", 1), ("mana2", 1), ("mana1", 1), ("mana0", 1), ("rust0", 1), ("mana1", 1)],
            "st": [("moss0", 1), ("sap1", 1), ("sap0", 1), ("moss0", 1), ("rust0", 1), ("sap0", 1)],
            "boss": [("crimson0", 1), ("crimson2", 1), ("crimson1", 1), ("crimson0", 1), ("blood0", 1), ("rust0", 1),
                     ("crimson0", 1), ("blood2", 1)],
        },
        "trail": {"hp": [("bronze0", .92), ("cinder1", .92), ("cinder0", .92), ("bronze0", .92), ("rust0", .92),
                         ("rust0", .92), ("bronze0", .92), ("cinder0", .92)]},
        "empty": {b: _trough(n, mid=("ink0", 0.9), top=(("ink0", 0.97), ("ink1", 0.9)), lip=(("ink0", 0.9), ("rust0", 0.7)))
                  for b, n in BODY.items()},
        "post": {"fill": _post([("bronze3", .95), ("rust0", .7)]), "empty": _post([("bronze0", .7), ("ink0", .4)])},
    },
    "c3": {
        "name": "녹 빗금", "en": "etched tarnish hatch",
        "fill": {
            "hp": [("blood2", 1), ("crimson1", 1), ("crimson1", 1)] + _hatch("bronze0", "crimson1", 4) + [("blood0", 1)],
            "fp": [("mana2", 1), ("mana1", 1)] + _hatch("rust0", "mana1", 3) + [("mana0", 1)],
            "st": [("sap1", 1), ("sap0", 1)] + _hatch("bronze0", "sap0", 3) + [("moss0", 1)],
            "boss": [("blood2", 1), ("crimson1", 1), ("crimson1", 1)] + _hatch("bronze0", "crimson1", 4) + [("blood0", 1)],
        },
        "trail": {"hp": [("cinder1", .9), ("cinder0", .9), ("cinder0", .9), ("bronze1", .9), ("bronze1", .9),
                         ("bronze0", .9), ("bronze0", .9), ("rust0", .9)]},
        "empty": {b: _trough(n) for b, n in BODY.items()},
        "post": {"fill": _post([(("bronze3", "bronze3", "bronze1", "bronze1"), .95),
                                (_rot(("bronze3", "bronze3", "bronze1", "bronze1"), 1), .95)]),
                 "empty": _post([("bronze0", .7), ("ink0", .5)])},
    },
}


# ─────────────────────────── 그리기 ───────────────────────────

def body(style, bar, kind):
    """몸 줄 목록 (BODY[bar] 줄). kind: fill, trail, empty."""
    st = STYLES[style] if isinstance(style, str) else style
    rows = st[kind].get(bar)
    if rows is None and kind == "trail" and bar == "boss":
        rows = st[kind]["hp"]               # 보스의 잃은 몫은 체력 막대와 같은 줄 (몸 높이가 같다)
    assert len(rows) == BODY[bar], f"{bar} {kind}: 몸 줄 {len(rows)} != {BODY[bar]}"
    return list(rows)


def column(style, bar, kind):
    """막대 한 칸 세로 줄 (텍셀, 위 → 아래). kind: fill, trail, empty, post_fill, post_empty (post_* 는 bar = boss)."""
    st = STYLES[style] if isinstance(style, str) else style
    if kind.startswith("post_"):
        return list(st["post"][kind[5:]])
    return [RIM, FRAME] + body(st, bar, kind) + [FRAME, DROP]


def _rgba(row, x):
    """한 줄의 x 번째 텍셀 (조각 왼쪽 끝이 0) → (r, g, b, a 0..255) 또는 None."""
    nm, a = row
    if nm is None or a <= 0:
        return None
    if isinstance(nm, tuple):
        nm = nm[x % len(nm)]
    r, g, b, _ = c(nm)
    al = int(round(min(1.0, a) * 255))
    if 250 <= al <= 252:                    # 발광 알파는 빛 허용 그림만 (artlint glowalpha)
        al = 249
    return r, g, b, al


def strip(col, n_gui):
    """길이 n_gui GUI 픽셀 조각 하나 (무늬 위상 0): RGBA uint8 배열 (줄 수, n_gui × S)."""
    w = n_gui * S
    out = np.zeros((len(col), w, 4), np.uint8)
    for y, row in enumerate(col):
        for x in range(w):
            v = _rgba(row, x)
            if v:
                out[y, x] = v
    return out


def run_sheet(col):
    """폭 1, 2, 4 … 128 GUI 픽셀 조각을 256 텍셀 칸 간격으로 한 그림에 (bitmap 글꼴 한 공급자, hud.py run_sheet 과 같은 꼴)."""
    cell = RUN_STEPS[-1] * S
    arr = np.zeros((len(col), cell * len(RUN_STEPS), 4), np.uint8)
    for i, n in enumerate(RUN_STEPS):
        arr[:, i * cell:i * cell + n * S] = strip(col, n)
    return Image.fromarray(arr, "RGBA")


SHEETS = (  # (그림 이름, 막대, 종류) — hud.py 의 그림 이름과 같다
    ("hud_hp_fill", "hp", "fill"), ("hud_hp_trail", "hp", "trail"), ("hud_hp_empty", "hp", "empty"),
    ("hud_fp_fill", "fp", "fill"), ("hud_fp_empty", "fp", "empty"),
    ("hud_st_fill", "st", "fill"), ("hud_st_empty", "st", "empty"),
    ("hud_boss_hp_fill", "boss", "fill"), ("hud_boss_hp_trail", "boss", "trail"), ("hud_boss_hp_empty", "boss", "empty"),
    ("hud_boss_post_fill", "boss", "post_fill"), ("hud_boss_post_empty", "boss", "post_empty"),
)


def sheets(style):
    """{그림 이름: 그림} (막대 조각 그림 전부, 마구리 빼고)."""
    return {fname: run_sheet(column(style, bar, kind)) for fname, bar, kind in SHEETS}


def colours(style):
    """{그림 이름: 쓰는 팔레트 이름 집합}."""
    out = {}
    for fname, bar, kind in SHEETS:
        names = set()
        for nm, a in column(style, bar, kind):
            if nm is None:
                continue
            names |= set(nm) if isinstance(nm, tuple) else {nm}
        out[fname] = names
    return out


def check(style):
    """팔레트 밖의 이름, 마나 계열을 마나 그림 (hud_fp_) 밖에 쓴 것, 가로 무늬를 채움 밖에 쓴 것. 돌려주는 값: 문제 목록."""
    bad = []
    st = STYLES[style] if isinstance(style, str) else style
    for fname, names in colours(style).items():
        for nm in names:
            if nm not in C:
                bad.append(f"{fname}: 팔레트에 없는 색 {nm}")
            elif family(nm) == "mana" and not fname.startswith("hud_fp_"):
                bad.append(f"{fname}: 마나 계열 {nm} 은 hud_fp_ 그림에만")
    for kind in ("trail", "empty"):
        for bar, rows in st[kind].items():
            if any(isinstance(r[0], tuple) for r in rows):
                bad.append(f"{bar} {kind}: 가로 무늬는 채움에만 (시작 자리가 아무 데나라 기어간다)")
    for bar, rows in st["fill"].items():
        for r in rows:
            if isinstance(r[0], tuple) and (len(r[0]) > PERIOD or PERIOD % len(r[0])):
                bad.append(f"{bar} fill: 무늬 주기 {len(r[0])} 가 {PERIOD} 텍셀의 약수가 아니다")
    return bad


def hexes(style):
    """말씨가 쓰는 색 {이름: #rrggbb} (알림·문서용)."""
    names = set().union(*colours(style).values())
    return {n: "#%02x%02x%02x" % C[n][:3] for n in sorted(names)}


def _row_text(row):
    nm, a = row
    if nm is None:
        return "-"
    if isinstance(nm, tuple):
        return f"x mod {len(nm)} -> [{' '.join(nm)}] a{a:g}"
    return f"{nm} #{'%02x%02x%02x' % C[nm][:3]} a{a:g}"


def recipe(style):
    """구현용 글: 막대·종류마다 텍셀 줄 (위 → 아래) 과 색·알파. 무늬 줄은 조각 왼쪽 끝에서 x mod 주기."""
    st = STYLES[style] if isinstance(style, str) else style
    out = [f"{style}: {st.get('name', '')} / {st.get('en', '')}",
           "  frame rows (every bar, every kind): RIM " + _row_text(RIM) + " | FRAME " + _row_text(FRAME)
           + " | ...body... | FRAME | DROP " + _row_text(DROP)]
    for bar in ("hp", "fp", "st", "boss"):
        for kind in ("fill", "trail", "empty"):
            if kind == "trail" and bar not in ("hp", "boss"):
                continue
            rows = body(st, bar, kind)
            out.append(f"  {bar} {kind} ({len(rows)} body rows): " + "; ".join(f"r{i} {_row_text(r)}"
                                                                         for i, r in enumerate(rows)))
    for kind in ("fill", "empty"):
        rows = st["post"][kind]
        lit = [(i, r) for i, r in enumerate(rows) if r[0] is not None]
        out.append(f"  boss posture {kind} ({POST_H}-row glyph, bar top = row 0): "
                   + "; ".join(f"row {i} {_row_text(r)}" for i, r in lit))
    return "\n".join(out)
