"""
mood2_gothic 의 HUD 그림 글자 (souls:hud). 기본 팩 (pack/hud.py) 과 같은 이름·같은 자리 셈 (플러그인 Hud.java 그대로) 에
그림만 다시 그린다. 그림은 GUI 한 픽셀에 2 텍셀 (숫자는 4 텍셀) 이고 글꼴 셰이더가 넓이 평균으로 읽는다 (shaders.py).

  막대 셋 (왼쪽 위, 체력·마나·스태미나): 위에서 비친 단조 쇠 테 (윗날에 청동빛 한 줄), 안쪽 홈은 위가 가장 어둡고 아래에
               녹슨 입술 (안으로 꺼진 베벨), 채움은 윗줄이 한 단 밝고 아래로 어두워진다. 체력은 짙은 진홍, 마나는 다크 소울 FP
               처럼 깊고 바랜 쪽빛 (palette 의 mana, 마나 막대 전용 예외), 스태미나는 누른 풀빛. 잃은 체력은 옅은 금빛 흰색.
               끝 마구리: 왼쪽은 마름모 창끝과 위아래로 말린 덩굴 (단조 장식), 오른쪽은 작은 창끝. 막대보다 위·아래로 2 픽셀
               나온다 (체력 막대의 마구리가 가장 크다).
  소울 수 (오른쪽 아래): 검은 옻칠 상자, 윗날에 촛불 기운 (가운데가 따뜻하다), 금실 윗줄과 양 끝 마름모, 위 가운데 작은
               꽃 장식. 넋 표식은 위로 꼬리가 선 옅은 뼈빛 불꽃, 숫자는 가라몽 라이닝 숫자 (고정 폭).
  보스 막대 (아래 가운데): 체력 막대와 같은 말씨에 더 큰 마구리, 그 밑 반 픽셀 상아빛 자세 줄. 이름 (로마 대문자,
               제목 글꼴) 은 플러그인 사본이 입힌다.
"""
import os

import numpy as np
from PIL import Image

import draw
from draw import Img, Mask

S = 2                       # 텍셀 / GUI 픽셀 (막대·마구리·상자)
NS = "souls"
HUD_FONT = NS + ":hud"
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)

# 막대: 이름 → (맨 위 (GUI 픽셀, 막대 셋의 맨 위에서), 채움 색 (위 → 아래, 텍셀 줄))
FILL = {
    "hp": ("crimson3", "crimson2", "crimson2", "crimson2", "crimson2", "crimson1", "crimson1", "crimson0"),
    "fp": ("mana3", "mana2", "mana2", "mana2", "mana1", "mana0"),
    "st": ("sap3", "sap2", "sap2", "sap2", "sap1", "sap0"),
}
TOP = {"hp": 0, "fp": 11, "st": 21}          # 막대 셋의 맨 위에서 (GUI). 마구리는 위·아래로 2 씩 나온다
TRAIL = (("glim0", 0.92),) * 6 + (("parch3", 0.92), ("parch2", 0.92))
RIM = ("bronze2", 0.85)                     # 윗날: 촛불이 비친 청동 한 줄 (반 픽셀)
FRAME = ("ink0", 0.95)
DROP = ("ink0", 0.40)                       # 막대 밑 그늘 반 픽셀


def trough(n):
    """빈 몫 (홈) n 줄: 위가 가장 어둡고 아래에 녹슨 입술."""
    rows = [("ink0", 0.97), ("ink0", 0.88)] + [("ink0", 0.82)] * max(0, n - 4) + [("rust0", 0.80), ("rust1", 0.55)]
    return rows[:n]


def column(bar, kind):
    """막대 한 칸 세로 줄 (텍셀, 위 → 아래): [(이름, 알파)]."""
    fill = FILL[bar]
    n = len(fill)
    body = {"fill": [(x, 1.0) for x in fill],
            "trail": list(TRAIL[-n:]) if bar == "hp" else [("glim0", 0.9)] * n,
            "empty": trough(n)}[kind]
    return [RIM, FRAME] + body + [FRAME, DROP]


def run_sheet(col):
    """폭 1, 2, 4 … 128 GUI 픽셀 조각을 256 텍셀 칸 간격으로 (bitmap 글꼴 한 공급자 = 한 그림, 칸 폭이 같다)."""
    cell = RUN_STEPS[-1] * S
    img = Img(cell * len(RUN_STEPS), len(col))
    for i, n in enumerate(RUN_STEPS):
        for x in range(n * S):
            for y, (nm, a) in enumerate(col):
                img.put(i * cell + x, y, nm, a)
    return img.image()


IRON = ["ink0", "rust2", "bronze3", "parch3"]    # 단조 쇠: 아랫날 → 몸 → 윗날 밑 → 윗날 (촛불이 위에서)
GOLD = ["rust1", "bronze3", "parch2", "glim0"]
EXT = 6                                          # 마구리가 막대 위·아래로 나오는 텍셀 (3 GUI 픽셀)


def cap_left(hb, big=False, ext=EXT):
    """
    왼쪽 마구리 (텍셀): 높이 hb + 2 EXT, 폭 26 (보스 30). 막대 끝의 세운 기둥 (위·아래 끝에 둥근 꼭지), 기둥에 붙은 단조 고리,
    고리에서 왼쪽으로 뻗은 마름모 창끝, 기둥 꼭지에서 고리로 말려 내려오는 덩굴 둘. 획은 2 텍셀 (1 GUI 픽셀) 이상이라
    윗날 (촛불 빛) 과 아랫날 (그늘) 이 갈린다.
    """
    w = 30 if big else 26
    h = hb + 2 * ext
    cy = h / 2.0
    m = Mask(w, h)
    px = w - 3.0
    m.rect(w - 5, 2, w - 1, h - 2)                  # 기둥 4 텍셀
    m.disc(px, 2.4, 2.4)
    m.disc(px, h - 2.4, 2.4)
    rc = w - 13.0                                  # 고리 가운데
    ro = 5.2 if not big else 5.8
    m.ring(rc, cy, ro - 2.2, ro)
    m.rect(rc + ro - 1, cy - 1.2, w - 4, cy + 1.2)  # 고리 → 기둥
    tip = 0.6
    m.poly([(tip, cy), (rc - ro - 3.6, cy - 3.4), (rc - ro + 1.0, cy), (rc - ro - 3.6, cy + 3.4)])
    m.rect(rc - ro - 1.5, cy - 1.0, rc - ro + 1.0, cy + 1.0)
    # 덩굴: 기둥 꼭지에서 왼쪽으로 휘어 고리 위·아래에 닿는 반원
    rr = (h / 2.0 - ro) / 2.0 + 1.6
    m.ring(px - rr - 0.6, 2.4 + rr, rr - 2.0, rr, 180, 360)
    m.ring(px - rr - 0.6, h - 2.4 - rr, rr - 2.0, rr, 0, 180)
    hole = Mask(w, h).poly([(tip + 4.2, cy), (rc - ro - 3.6, cy - 1.4), (rc - ro - 1.2, cy), (rc - ro - 3.6, cy + 1.4)])
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    return draw.lit(cov, IRON, light_rows=1, dark_rows=1)


def cap_right(hb, big=False, ext=EXT):
    """오른쪽 마구리: 둥근 꼭지의 기둥과 작은 마름모 창끝 (폭 14, 보스 16)."""
    w = 16 if big else 14
    h = hb + 2 * ext
    cy = h / 2.0
    m = Mask(w, h)
    m.rect(0, 2, 4, h - 2)
    m.disc(2.0, 2.4, 2.4)
    m.disc(2.0, h - 2.4, 2.4)
    m.rect(3, cy - 1.0, 7, cy + 1.0)
    m.poly([(5.5, cy), (9.5, cy - 3.2), (w - 0.4, cy), (9.5, cy + 3.2)])
    hole = Mask(w, h).poly([(8.2, cy), (9.8, cy - 1.1), (w - 3.4, cy), (9.8, cy + 1.1)])
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    return draw.lit(cov, IRON)


def caps_sheet(hb, big=False, ext=EXT):
    """마구리 둘을 한 그림에 (칸 폭 같게): [왼쪽][오른쪽]. 돌려주는 값: (그림, 칸 폭 텍셀)."""
    l, r = cap_left(hb, big, ext), cap_right(hb, big, ext)
    cw = max(l.w, r.w)
    sheet = Img(cw * 2, l.h)
    sheet.over(l, 0, 0)
    sheet.over(r, cw, 0)
    return sheet.image(), cw


# ─────────────────────────── 소울 상자 ───────────────────────────

BOX_W, BOX_H = 72, 15           # GUI 픽셀
BOX_BOTTOM = 8                  # 화면 아래에서 (셰이더 없이, 기본 팩과 같다)


def soul_box():
    W, H = BOX_W * S, BOX_H * S
    img = Img(W, H)
    cx = W / 2.0
    # 옻칠 몸 (3..26): 양 끝 8 텍셀은 알파 계단으로 옅어진다. 윗날 아래 네 줄은 촛불 기운 (가운데일수록 따뜻한 색)
    for y in range(3, H - 3):
        for x in range(W):
            d = min(x, W - 1 - x)
            k = 1.0 if d >= 8 else (d + 1) / 9.0
            dx = abs(x + 0.5 - cx) / cx
            name = "ink0"
            if y == 3 and dx < 0.75:
                name = "bronze1" if dx < 0.35 else "bronze0"
            elif y == 4 and dx < 0.6:
                name = "bronze0" if dx < 0.3 else "rust0"
            elif y == 5 and dx < 0.45:
                name = "rust0"
            img.put(x, y, name, 0.80 * k)
    # 금실 윗줄 (2): 가운데 밝은 금 → 끝으로 어두운 금, 끝 10 텍셀 알파 계단. 아랫줄 (H-3): 녹슨 쇠
    for x in range(W):
        d = min(x, W - 1 - x)
        k = 1.0 if d >= 10 else (d + 1) / 11.0
        dx = abs(x + 0.5 - cx) / cx
        img.put(x, 2, "parch2" if dx < 0.3 else ("parch1" if dx < 0.65 else "parch0"), 0.95 * k)
        img.put(x, H - 3, "rust1", 0.85 * k)
        img.put(x, H - 2, "ink0", 0.35 * k)
    # 양 끝 마름모 (윗줄 위) 와 위 가운데 꽃 장식
    orn = Mask(W, H)
    for ex in (11.0, W - 11.0):
        orn.poly([(ex - 2.6, 2.5), (ex, 0.2), (ex + 2.6, 2.5), (ex, 4.8)])
    orn.poly([(cx - 4.5, 2.6), (cx, -0.5), (cx + 4.5, 2.6), (cx, 5.6)])
    orn.disc(cx - 6.2, 2.5, 1.1)
    orn.disc(cx + 6.2, 2.5, 1.1)
    hole = Mask(W, H).poly([(cx - 1.6, 2.6), (cx, 1.2), (cx + 1.6, 2.6), (cx, 4.0)])
    cov = np.clip(orn.cov() - hole.cov(), 0, 1)
    img.over(draw.lit(cov, GOLD))
    return img.image()


def soul_mark():
    """넋 표식 (빛 허용 그림 soul_mark): 위로 꼬리가 선 불꽃 모양, 옅은 뼈빛, 속에 희미한 불씨. 22×22 텍셀 (11 GUI)."""
    W = H = 22
    outer = Mask(W, H)
    outer.ellipse(11.0, 15.0, 5.4, 5.6)
    outer.poly([(6.2, 13.0), (9.0, 6.0), (12.5, 1.2), (12.6, 6.5), (15.8, 12.0)])
    outer.line(12.5, 1.5, 14.8, 4.2, 1.4)
    inner = Mask(W, H)
    inner.ellipse(11.0, 15.6, 3.4, 3.6)
    inner.poly([(8.6, 14.0), (11.0, 8.0), (13.2, 14.0)])
    core = Mask(W, H).ellipse(11.0, 16.4, 1.6, 1.8)
    img = Img(W, H)
    img.over(draw.lit(outer.cov(), ["bone0", "bone0", "bone1", "bone2"]))
    img.fill(inner.cov(), "bone2", 0.95)
    img.fill(core.cov(), "bone3", 1.0)
    img.fill(Mask(W, H).disc(11.0, 16.8, 0.8).cov(), "ember3", 0.9)
    return img.image()


def digits(face_role, k=4, ink="bone2"):
    """
    소울 수 숫자 열 장 (fonts.Role 로 그린 가라몽 라이닝 숫자, k 텍셀/GUI). 칸 폭 같게, 모든 숫자의 진행 폭이 같도록 같은 열에
    알파 1 점. 색은 팔레트 한 색, 덮임은 알파. 돌려주는 값: (그림, 칸 높이 텍셀, 바탕선 위 GUI 줄 수, 진행 폭 GUI).
    """
    gl = {str(d): face_role.glyphs[str(d)] for d in range(10)}
    up = max(g["top"] for g in gl.values())
    down = max(g["a"].shape[0] - g["top"] for g in gl.values())
    wid = max(g["a"].shape[1] for g in gl.values())
    asc = int(np.ceil((up + 1) / k))
    desc = int(np.ceil((down + 1) / k))
    ch = (asc + desc) * k
    adv = int(np.ceil((wid + 1 + 3) / k)) + 1           # 숫자 폭 + 사이 1 GUI 픽셀
    cw = adv * k
    arr = np.zeros((ch, cw * 10, 4), np.uint8)
    from palette import c
    r, g, b, _ = c(ink)
    for d in range(10):
        a = gl[str(d)]["a"]
        x0 = d * cw + (cw - k - a.shape[1]) // 2
        y0 = asc * k - gl[str(d)]["top"]
        al = np.clip(np.rint(a * 255), 0, 255).astype(np.uint8)
        sub = arr[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
        sub[..., 0], sub[..., 1], sub[..., 2] = r, g, b
        sub[..., 3] = np.maximum(sub[..., 3], al)
        sent = d * cw + (adv - 1) * k - 1
        if arr[ch - 1, sent, 3] == 0:
            arr[ch - 1, sent] = (r, g, b, 1)
    arr[..., 3][(arr[..., 3] >= 250) & (arr[..., 3] <= 252)] = 249
    return Image.fromarray(arr, "RGBA"), ch, asc, adv


# ─────────────────────────── 엮기: souls:hud 공급자, glyphs.yml ───────────────────────────

HUD_LINE_TOP = 3            # 첫 보스 막대 이름 줄의 위 (HUD 막대 셋이 쓰는 줄, pack/hud.py BOSS_LINE_TOP)
HUD_TOP = 8                 # 막대 셋의 맨 위 (셰이더 없이 GUI y, pack/hud.py HUD_TOP)
ACTION_LINE_UP = 72         # 행동 막대 줄의 위 = 화면 아래 - 72 (pack/hud.py)
BOSS_BAR_ROW = 9            # 보스 이름 줄 위에서 체력 막대 맨 위 (GUI). 마구리는 7..17, 자세 줄은 15.5 (반 픽셀)
BOSS_FILL = ("crimson3", "crimson2", "crimson2", "crimson2", "crimson2", "crimson1", "crimson1", "crimson0")


def _adv(img, x0, cw, scale):
    """클라이언트 bitmap 글꼴 진행 폭: 알파가 0 이 아닌 가장 오른쪽 열 + 1, (int)(0.5 + 폭 × 배율) + 1."""
    a = np.asarray(img)[..., 3][:, x0:x0 + cw]
    cols = np.nonzero(a.max(0) > 0)[0]
    w = int(cols[-1]) + 1 if len(cols) else 0
    return int(0.5 + w * scale) + 1


def build(pack, digit_role):
    """
    HUD 그림을 쓰고 (공급자 목록, [(이름, 문자, 진행 폭)]) 를 돌려준다. 문자는 U+E040 부터 (기본 팩과 같은 구역).
    """
    providers, glyphs = [], []
    code = [0xE040]

    def add(fname, img, ascent, names, scale=1.0 / S, cells=None):
        path = os.path.join(pack, "assets", NS, "textures", "font", fname + ".png")
        draw.save(img, path)
        n = len(names)
        cw = img.width // n
        chars = ""
        for i, nm in enumerate(names):
            ch = chr(code[0])
            code[0] += 1
            chars += ch
            glyphs.append((nm, ch, _adv(img, i * cw, cw, scale)))
        h = img.height * scale
        assert abs(h - round(h)) < 1e-6, f"{fname}: 높이가 GUI 픽셀 정수가 아니다 ({img.height} 텍셀)"
        providers.append({"type": "bitmap", "file": f"{NS}:font/{fname}.png", "height": int(round(h)), "ascent": ascent,
                          "chars": [chars]})

    def asc_hud(top_gui):
        return HUD_LINE_TOP + 7 - top_gui

    for bar in ("hp", "fp", "st"):
        top = HUD_TOP + TOP[bar]
        kinds = ("fill", "trail", "empty") if bar == "hp" else ("fill", "empty")
        for kind in kinds:
            add(f"hud_{bar}_{kind}", run_sheet(column(bar, kind)), asc_hud(top), [f"hud_{bar}_{kind}_{n}" for n in RUN_STEPS])
        hb = len(column(bar, "fill"))
        sheet, _ = caps_sheet(hb)
        add(f"hud_{bar}_cap", sheet, asc_hud(top - EXT // S), [f"hud_{bar}_cap_l", f"hud_{bar}_cap_r"])

    box_top = BOX_BOTTOM + BOX_H
    add("hud_soulbox", soul_box(), box_top - 65, ["hud_soulbox"])
    mark = soul_mark()
    add("soul_mark", mark, (box_top - 2) - 65, ["soul_mark"])
    dimg, dch, dasc, dadv = digits(digit_role)
    base_from_bottom = BOX_BOTTOM + 4                          # 숫자 바탕선: 상자 아래에서 4 위
    add("hud_digits", dimg, (base_from_bottom + dasc) - 65, [f"hud_digit_{d}" for d in range(10)], scale=1.0 / 4)

    # 보스 막대 (보스 이름 줄 안): 체력 (윗날·테·채움 여덟·테·그늘), 자세 (반 픽셀 줄), 마구리
    col = [RIM, FRAME] + [(x, 1.0) for x in BOSS_FILL] + [FRAME, DROP]
    for kind in ("fill", "trail", "empty"):
        c_ = col if kind == "fill" else ([RIM, FRAME] + (list(TRAIL) if kind == "trail" else trough(8)) + [FRAME, DROP])
        add(f"hud_boss_hp_{kind}", run_sheet(c_), 7 - BOSS_BAR_ROW, [f"boss_hp_{kind}_{n}" for n in RUN_STEPS])
    # 자세 줄: 막대 밑 그늘 줄 (텍셀 11) 다음, 텍셀 13 (GUI 15.5) 에 1 텍셀. 그림은 막대와 같은 위에서 (2 GUI = 4 텍셀 높이)
    post_fill = [(None, 0)] * 13 + [("bone3", 0.95)] + [(None, 0)] * 2
    post_empty = [(None, 0)] * 13 + [("ink0", 0.55)] + [(None, 0)] * 2
    for kind, cl in (("fill", post_fill), ("empty", post_empty)):
        add(f"hud_boss_post_{kind}", _run_sheet_opt(cl), 7 - BOSS_BAR_ROW, [f"boss_post_{kind}_{n}" for n in RUN_STEPS])
    # 보스 마구리는 위·아래 2 GUI 픽셀만 (이름 줄 위 -1 .. +17 안: 셰이더가 꼭짓점 y 로 보스 줄을 고른다)
    sheet, _ = caps_sheet(len(col), big=True, ext=4)
    add("hud_boss_cap", sheet, 7 - (BOSS_BAR_ROW - 2), ["boss_cap_l", "boss_cap_r"])
    return providers, glyphs


def _run_sheet_opt(col):
    cell = RUN_STEPS[-1] * S
    img = Img(cell * len(RUN_STEPS), len(col))
    for i, n in enumerate(RUN_STEPS):
        for x in range(n * S):
            for y, (nm, a) in enumerate(col):
                if nm:
                    img.put(i * cell + x, y, nm, a)
    return img.image()


def yaml_str(s):
    out = []
    for ch in s:
        if ch in ('"', "\\"):
            out.append("\\" + ch)
        elif 0x20 <= ord(ch) < 0x7f:
            out.append(ch)
        else:
            out.append(f"\\u{ord(ch):04x}")
    return '"' + "".join(out) + '"'


HUD_NAMES = ("hud_", "boss_", "soul_mark")


def glyphs_yml(base_text, glyphs):
    """기본 팩 glyphs.yml 에서 HUD 그림 글자 줄을 시안 것으로 바꾸고, layout 의 soul_box 를 시안 상자 폭으로."""
    out = []
    for line in base_text.split("\n"):
        name = line.split(":", 1)[0]
        if line and not line.startswith("#") and name.startswith(HUD_NAMES):
            continue
        if line.startswith("layout:"):
            line = line.replace("soul_box: 64", f"soul_box: {BOX_W}")
            for nm, ch, w in glyphs:
                out.append(f"{nm}: {{char: {yaml_str(ch)}, width: {w}, font: {yaml_str(HUD_FONT)}}}")
        out.append(line)
    return "\n".join(out)


def write_font(pack, providers):
    """souls:hud = 기본 팩의 빈칸·제목 YOU DIED 공급자 + 시안 HUD 공급자."""
    import json
    path = os.path.join(pack, "assets", NS, "font", "hud.json")
    with open(path, encoding="utf-8") as f:
        base = json.load(f)
    keep = [p for p in base["providers"] if p["type"] == "space" or "you_died" in p.get("file", "")]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"providers": keep + providers}, f, ensure_ascii=True, indent=1)
        f.write("\n")
