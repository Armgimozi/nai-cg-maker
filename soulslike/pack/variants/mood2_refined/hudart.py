"""
mood2_refined 의 HUD 그림 글자 (souls:hud) 와 사망 띠, 조준점. 기본 팩의 그림 글자 이름·문자 번호는 그대로 두고 (플러그인
hud/Hud.java 가 이름과 폭으로 짠다) 그림만 4배 해상도로 다시 그린다. glyphs.yml 의 폭을 새 그림에 맞춰 다시 쓴다.

막대 셋 (왼쪽 위, 다크 소울 3 차례: 체력 · 마나 · 스태미나)
  몸: [금빛 머리카락 선][먹 테][채움 (안쪽 베벨: 맨 윗줄 밝게, 아래 석 줄 어둡게)][먹 테][흐린 금빛 선]. 위·아래의 금빛 선과
  먹 테가 "가는 두 겹 선" 이다. 체력 채움 3 GUI 픽셀, 마나·스태미나 2.
  색: 체력 짙은 진홍 (crimson), 마나 깊고 조금 바랜 쪽빛 (mana, 팔레트의 마나 전용 계열: 사용자 결정 2026-10-08, 파랑 금지의 예외),
      스태미나 누른 풀빛 (sap). 잃은 체력은 옅은 금빛 흰색 (glim) 으로 잠깐 남는다 (기본 팩 Hud.java 그대로).
  마구리: 막대 끝의 금빛 세로 꺾쇠 (몸보다 반 픽셀씩 위아래로 나오고 끝에 작은 발) + 그 바깥의 작은 마름모와 덩굴 한 가닥.
  조각: 폭 1·2·4…64 GUI 픽셀 (256 텍셀 판에 들어가는 데까지). 128 은 glyphs.yml 에서 64 + (-1) + 64 를 이은 한 글자열로 둔다
  (플러그인은 글자열 그대로 붙인다).
소울 상자 (오른쪽 아래): 65% 먹 띠 (양 끝으로 옅어진다), 위·아래 금빛 선 (양 끝으로 사라진다), 양 끝 작은 마름모. 넋 표식은
  4배로 다시 그린 뼈빛 넋 (속에 희미한 불씨, 빛 허용 그림 soul_mark), 숫자는 본문 명조 (EB Garamond) 의 숫자 (고정 폭 6).
보스 막대 (아래 가운데): 체력 막대와 같은 몸, 그 밑에 가는 자세 줄, 양 끝 마구리는 몸과 자세 줄을 한 묶음으로 닫는다. 이름은
  플러그인 사본이 제목 글꼴 (로마 대문자 Cinzel / 굵은 명조) 로 막대 왼쪽 위에 쓴다 (java_hook).
사망 띠: 기본 팩의 먹 띠 (YOU DIED 뒤) 에 위·아래 금빛 머리카락 선. 글자 그림은 그대로.
조준점: 가운데 작은 점 하나와 네 방위의 아주 짧은 눈금 (바닐라처럼 뒤 색을 뒤집어 섞인다).
"""
import json
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import ornament as orn
import palette
import style
from ornament import Canvas, RES

HUD_TOP = 8                  # 기본 팩 hud.py 와 같은 값 (셰이더가 이 자리를 왼쪽 위로 옮긴다)
BOSS_LINE_TOP = 3
ACTION_LINE_UP = 72
SOUL_BOX_BOTTOM, SOUL_BOX_H, SOUL_BOX_W = 8, 13, 64
RUNS = (1, 2, 4, 8, 16, 32, 64)
CELL = 64                    # 조각 칸 폭 (GUI 픽셀) = 256 텍셀

# 막대: 이름 → (맨 위 (GUI, 막대 셋의 맨 위에서), 몸 높이 (텍셀), 채움 색 (위 → 아래), 마름모 반 대각선)
BARS = {
    "hp": (0, 16, ["crimson3"] + ["crimson2"] * 8 + ["crimson1"] * 3, 3),
    "fp": (6, 12, ["mana3"] + ["mana2"] * 4 + ["mana1"] * 3, 2),
    "st": (11, 12, ["sap3"] + ["sap2"] * 5 + ["sap1"] * 2, 2),
}
TRAIL = "glim0"
FRAME = ("ink0", 235)
TROUGH = ("ink0", 205)
TROUGH_TOP = ("ink0", 245)
CAP_W = 12                   # 마구리 폭 (텍셀) = 3 GUI 픽셀
BOSS_CAP_W = 8               # 보스 막대 마구리 (플러그인 Hud.bossLine 이 왼쪽 마구리 폭 2 를 셈에 넣는다)


def _save(img, pack, name):
    p = os.path.join(pack, "assets", "souls", "textures", "font", name + ".png")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p)
    return p


def advance(img, x0, cell_w, height_gui):
    """클라이언트 bitmap 글꼴과 같은 진행 폭."""
    a = np.asarray(img)[:, x0:x0 + cell_w, 3]
    cols = np.where(a.max(axis=0) > 0)[0]
    width = int(cols[-1]) + 1 if len(cols) else 0
    return int(0.5 + width * (height_gui / img.height)) + 1


# ─────────────────────────── 막대 ───────────────────────────

def bar_body(cv, x0, x1, top, H, kind, fill_rows, trail=TRAIL):
    """막대 몸 (x0..x1 텍셀, top 텍셀 줄에서 H 줄). kind: fill / trail / empty."""
    cv.hline(x0, x1, top, orn.GOLD)
    cv.hline(x0, x1, top + 1, FRAME)
    rows = H - 4
    for i in range(rows):
        y = top + 2 + i
        if kind == "fill":
            c = (fill_rows[i], 255)
        elif kind == "trail":
            c = (trail, 235) if i < rows - 3 else ("parch2", 235)
        else:
            c = TROUGH_TOP if i == 0 else TROUGH
        cv.hline(x0, x1, y, c)
    cv.hline(x0, x1, top + H - 2, FRAME)
    cv.hline(x0, x1, top + H - 1, orn.GOLD_SOFT)


def run_sheet(H, kind, fill_rows, pad_top=RES, pad_bottom=RES, extra=None):
    """조각 일곱 (1..64 GUI) 을 칸 폭 256 텍셀로 한 줄에. 몸은 pad_top 텍셀 아래에서."""
    h = pad_top + H + pad_bottom
    cv = Canvas(CELL * RES * len(RUNS), h)
    for i, n in enumerate(RUNS):
        x0 = i * CELL * RES
        bar_body(cv, x0, x0 + n * RES - 1, pad_top, H, kind, fill_rows)
        if extra:
            extra(cv, x0, x0 + n * RES - 1)
    return cv.image()


def cap_sheet(H, r, w=CAP_W, pad_top=RES, pad_bottom=RES, below=0):
    """
    왼쪽·오른쪽 마구리 두 칸 (칸 폭 w 텍셀). 금빛 세로 꺾쇠는 몸 위아래로 2 텍셀씩 나오고 (below 만큼 더 아래로), 끝에 바깥쪽
    1 텍셀 발. 그 바깥에 마름모 (반 대각선 r) 와 덩굴.
    """
    h = pad_top + H + pad_bottom
    cv = Canvas(w * 2, h)
    y0, y1 = pad_top - 2, pad_top + H + 1 + below
    cy = pad_top + H // 2 - (1 if H % 2 == 0 else 0)
    for side in (0, 1):
        left = side == 0
        bx = w - 1 if left else w          # 꺾쇠 열 (왼쪽 칸의 맨 오른쪽, 오른쪽 칸의 맨 왼쪽)
        out = -1 if left else 1             # 바깥 방향
        cv.vline(bx, y0, y1, orn.GOLD_PALE)
        cv.put(bx + out, y0, orn.GOLD)
        cv.put(bx + out, y1, orn.GOLD)
        # 몸의 위아래 줄이 꺾쇠에 닿는 자리는 몸과 같은 색 (꺾쇠가 몸을 닫는다)
        gx = bx + out * (r + 2)
        if 0 <= gx - r and gx + r < w * 2:
            cv.lozenge(gx, cy, r)
            # 꺾쇠와 마름모를 잇는 짧은 선, 마름모 바깥의 덩굴
            for x in range(min(bx, gx) + 1, max(bx, gx)):
                if abs(x - gx) > r:
                    cv.put(x, cy, orn.GOLD)
            cv.whisker(gx + out * (r + 1), cy, out, max(2, w - (r * 2 + 4)), orn.GOLD_PALE)
    return cv.image()


# ─────────────────────────── 소울 상자 ───────────────────────────

def soul_box():
    W, H = SOUL_BOX_W * RES, SOUL_BOX_H * RES
    cv = Canvas(W, H)
    fade = 6 * RES
    for x in range(W):
        d = min(x, W - 1 - x)
        k = 1.0 if d >= fade else (d + 1) / (fade + 1)
        for y in range(H):
            e = min(y, H - 1 - y)
            ky = 0.55 if e == 0 else (0.8 if e == 1 else 1.0)
            cv.put(x, y, ("ink0", 168 * k * ky))
    top, bot = 3, H - 4                      # 머리카락 선 (텍셀 줄 3, 48: GUI 픽셀의 끝 텍셀)
    cv.hline(10, W - 11, top, orn.GOLD, fade=(36, 36))
    cv.hline(10, W - 11, bot, orn.GOLD_SOFT, fade=(36, 36))
    # 양 끝 작은 마름모: 세로 가운데, 상자 끝에서 1 GUI 안
    cy = H // 2 - 1
    for gx, out in ((5, -1), (W - 6, 1)):
        cv.lozenge(gx, cy, 2)
        cv.whisker(gx - out * 3, cy, -out, 5, orn.GOLD_SOFT)
    return cv.image()


def soul_mark():
    """
    넋 표식 8×9 GUI (32×36 텍셀): 아래가 둥글고 위로 가늘게 휘어 오르는 넋 (불꽃처럼 보이지 않게 끝이 한 번 꺾인다).
    바깥 옅은 뼈빛 → 뼈빛 → 속 밝은 뼈빛, 속 아래쪽에 아주 작은 불씨 한 점 (빛 허용 그림 soul_mark).
    """
    W, H = 32, 36
    cv = Canvas(W, H)
    cx, cy, R = 15.0, 26.0, 6.5
    tip_y = 1.5

    def inside(x, y, grow=0.0):
        if (x - cx) ** 2 + ((y - cy) * 1.08) ** 2 <= (R + grow) ** 2:
            return True
        if tip_y - grow <= y < cy:
            t = min(1.0, (cy - y) / (cy - tip_y))       # 0 아래 → 1 끝
            xc = cx + 4.2 * np.sin(t * np.pi * 1.15) * t ** 0.8
            w = R * max(0.0, 1 - t) ** 1.6 + grow
            return abs(x - xc) <= max(w, 0.0)
        return False

    for y in range(H):
        for x in range(W):
            px, py = x + 0.5, y + 0.5
            if inside(px, py, -2.8):
                cv.put(x, y, ("bone3", 255))
            elif inside(px, py, -1.2):
                cv.put(x, y, ("bone2", 255))
            elif inside(px, py, 0.0):
                cv.put(x, y, ("bone1", 220))
            elif inside(px, py, 1.1):
                cv.put(x, y, ("bone0", 110))
    for y in range(H):
        for x in range(W):
            d = (x + 0.5 - cx) ** 2 + (y + 0.5 - (cy + 1.5)) ** 2
            if d <= 1.3 ** 2:
                cv.put(x, y, ("ember3", 255))
            elif d <= 2.3 ** 2:
                cv.put(x, y, ("parch3", 255))
    cv.put(W - 1, H - 1, ("ink0", 1))
    return cv.image()


def digits_sheet(font_path):
    """숫자 열 장 (칸 6×8 GUI = 24×32 텍셀): 본문 명조의 숫자, 뼈빛, 오른쪽 아래 2 텍셀 먹 그림자. 바탕선은 칸 아래에서 3 텍셀 위."""
    cw, ch = 6 * RES, 8 * RES
    cv = Canvas(cw * 10, ch)
    font = ImageFont.truetype(font_path, 40)
    for d in range(10):
        mask = Image.new("L", (cw * 2, ch * 2), 0)
        dr = ImageDraw.Draw(mask)
        bbox = dr.textbbox((0, 0), str(d), font=font, anchor="ls")
        gw = bbox[2] - bbox[0]
        ox = (cw - gw) / 2 - bbox[0]
        dr.text((round(ox), ch - 3), str(d), font=font, fill=255, anchor="ls")
        m = np.asarray(mask)[:ch, :cw]
        for y in range(ch):
            for x in range(cw):
                if m[y, x] > 8 and x + 2 < cw and y + 2 < ch:
                    cv.put(d * cw + x + 2, y + 2, ("ink0", 0.55 * m[y, x]), under=True)
        for y in range(ch):
            for x in range(cw):
                if m[y, x] > 8:
                    cv.put(d * cw + x, y, ("bone2", m[y, x]))
        cv.put(d * cw + cw - 1, ch - 1, ("ink0", 1))
    return cv.image()


# ─────────────────────────── 보스 막대 ───────────────────────────

def boss_post_sheet(kind):
    """자세 줄 조각 (높이 1 GUI = 4 텍셀, 줄은 텍셀 1..2)."""
    cv = Canvas(CELL * RES * len(RUNS), RES)
    c = ("glim0", 225) if kind == "fill" else ("ink0", 170)
    for i, n in enumerate(RUNS):
        x0 = i * CELL * RES
        cv.hline(x0, x0 + n * RES - 1, 1, c)
        cv.hline(x0, x0 + n * RES - 1, 2, c if kind == "fill" else ("ink0", 120))
    return cv.image()


# ─────────────────────────── 사망 띠, 조준점 ───────────────────────────

def death_band():
    """띠 조각 셋 (왼쪽 끝, 가운데, 오른쪽 끝), 칸 64×22 글꼴 픽셀을 4배 (256×88). 먹 띠 + 위·아래 금빛 머리카락 선."""
    t, h = 64 * RES, 22 * RES
    cv = Canvas(t * 3, h)
    edge = 16                                   # 위·아래 옅어지는 텍셀 줄
    for y in range(h):
        e = min(y, h - 1 - y)
        ra = 190 if e >= edge else 190 * ((e + 1) / (edge + 1)) ** 1.3
        for i in range(3):
            for x in range(t):
                d = x if i == 0 else (t - 1 - x if i == 2 else t)
                k = 1.0 if d >= 64 else 0.2 + 0.8 * d / 64
                cv.put(i * t + x, y, ("ink0", ra * k))
    for y, c in ((10, orn.GOLD), (h - 11, orn.GOLD_SOFT)):
        for i in range(3):
            x0 = i * t
            if i == 0:
                cv.hline(x0, x0 + t - 1, y, (c[0], c[1] * 0.85), fade=(t - 8, 0))
            elif i == 2:
                cv.hline(x0, x0 + t - 1, y, (c[0], c[1] * 0.85), fade=(0, t - 8))
            else:
                cv.hline(x0, x0 + t - 1, y, (c[0], c[1] * 0.85))
    return cv.image()


def crosshair():
    """15×15 GUI → 60×60 텍셀: 가운데 2×2 점, 네 방위에 2 텍셀 눈금 (가운데에서 5 텍셀)."""
    cv = Canvas(15 * RES, 15 * RES)
    c = 15 * RES // 2
    cv.rect(c - 1, c - 1, c, c, ("parch2", 255))
    for d in (5, 6):
        cv.put(c - 1 - d, c - 1, ("parch0", 255))
        cv.put(c + d, c - 1, ("parch0", 255))
        cv.put(c - 1, c - 1 - d, ("parch0", 255))
        cv.put(c - 1, c + d, ("parch0", 255))
    return cv.image()


# ─────────────────────────── glyphs.yml ───────────────────────────

LINE_RE = re.compile(r'^([a-z0-9_]+): \{char: "((?:\\u[0-9a-f]{4})+)", width: (-?\d+), font: "([^"]+)"\}$')


def parse_glyphs(text):
    out = {}
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if m:
            chars = bytes(m.group(2), "ascii").decode("unicode_escape")
            out[m.group(1)] = {"char": chars, "width": int(m.group(3)), "font": m.group(4)}
    return out


def esc(s):
    return "".join("\\u%04x" % ord(ch) for ch in s)


def write_glyphs(text, changes):
    """기본 glyphs.yml 글 (text) 에서 이름이 changes 에 든 줄의 char·width 를 바꾼다. 새 이름은 layout 줄 앞에 더한다."""
    lines = text.splitlines()
    done = set()
    for i, line in enumerate(lines):
        m = LINE_RE.match(line)
        if m and m.group(1) in changes:
            ch = changes[m.group(1)]
            lines[i] = f'{m.group(1)}: {{char: "{esc(ch["char"])}", width: {ch["width"]}, font: "{ch["font"]}"}}'
            done.add(m.group(1))
    extra = [f'{n}: {{char: "{esc(v["char"])}", width: {v["width"]}, font: "{v["font"]}"}}'
             for n, v in changes.items() if n not in done]
    idx = next((i for i, l in enumerate(lines) if l.startswith("layout:")), len(lines))
    lines[idx:idx] = extra
    return "\n".join(lines) + "\n"


# ─────────────────────────── 빌드 ───────────────────────────

def _ascent_boss(top):
    return BOSS_LINE_TOP + 7 - top


def _ascent_line(r):
    return 7 - r


def _ascent_action(from_bottom):
    return 7 - (ACTION_LINE_UP - from_bottom)


def build(pack, base_glyphs_text):
    """HUD 그림 글자를 다시 그려 souls:hud 를 다시 쓰고 (기본 팩의 빈칸·제목 공급자는 그대로), 사망 띠·조준점 그림을 바꾼다.
    돌려주는 값: (minecraft:default 에 더할 공급자 [], 새 glyphs.yml 글)."""
    g = parse_glyphs(base_glyphs_text)
    hud_json = os.path.join(pack, "assets", "souls", "font", "hud.json")
    with open(hud_json, encoding="utf-8") as f:
        hud = json.load(f)
    hud_files = {"hud_hp", "hud_fp", "hud_st", "hud_soulbox", "soul_mark", "hud_digits", "hud_boss"}
    keep = [p for p in hud["providers"]
            if not (p.get("type") == "bitmap" and any(p["file"].startswith(f"souls:font/{h}") for h in hud_files))]
    providers = []
    changes = {}
    neg1 = g["space_neg1"]["char"]

    def add(file_name, img, height_gui, ascent, names):
        _save(img, pack, file_name)
        cw = img.width // len(names)
        chars = ""
        for i, n in enumerate(names):
            ch = g[n]["char"][0]
            chars += ch
            changes[n] = {"char": ch, "width": advance(img, i * cw, cw, height_gui), "font": "souls:hud"}
        providers.append({"type": "bitmap", "file": f"souls:font/{file_name}.png", "height": height_gui,
                          "ascent": ascent, "chars": [chars]})

    def runs(prefix, file_name, img, height_gui, ascent):
        add(file_name, img, height_gui, ascent, [f"{prefix}{n}" for n in RUNS])
        c64 = changes[f"{prefix}64"]
        changes[f"{prefix}128"] = {"char": c64["char"] + neg1 + c64["char"], "width": 2 * c64["width"] - 1,
                                   "font": "souls:hud"}

    # 막대 셋
    for bar, (off, H, fill_rows, r) in BARS.items():
        hg = 1 + H // RES + 1
        asc = _ascent_boss(HUD_TOP + off - 1)
        kinds = ("fill", "trail", "empty") if bar == "hp" else ("fill", "empty")
        for kind in kinds:
            runs(f"hud_{bar}_{kind}_", f"hud_{bar}_{kind}", run_sheet(H, kind, fill_rows), hg, asc)
        add(f"hud_{bar}_cap", cap_sheet(H, r), hg, asc, [f"hud_{bar}_cap_l", f"hud_{bar}_cap_r"])

    # 소울 상자·표식·숫자
    box_top = SOUL_BOX_BOTTOM + SOUL_BOX_H
    add("hud_soulbox", soul_box(), SOUL_BOX_H, _ascent_action(box_top), ["hud_soulbox"])
    add("soul_mark", soul_mark(), 9, _ascent_action(box_top - 2), ["soul_mark"])
    font_path = os.path.join(pack, "assets", "souls", "font", "body_la.ttf")
    add("hud_digits", digits_sheet(font_path), 8, _ascent_action(box_top - 3), [f"hud_digit_{d}" for d in range(10)])

    # 보스 막대: 몸 (줄 위 8 부터 6 GUI, 몸은 9..12.75), 자세 줄 (14), 마구리 (8..15)
    H = 16
    crim = ["crimson3"] + ["crimson2"] * 8 + ["crimson1"] * 3
    for kind in ("fill", "trail", "empty"):
        runs(f"boss_hp_{kind}_", f"hud_boss_hp_{kind}", run_sheet(H, kind, crim, pad_top=RES, pad_bottom=RES), 6,
             _ascent_line(8))
    for kind in ("fill", "empty"):
        runs(f"boss_post_{kind}_", f"hud_boss_post_{kind}", boss_post_sheet(kind), 1, _ascent_line(14))
    add("hud_boss_cap", cap_sheet(H, 2, w=BOSS_CAP_W, pad_top=RES, pad_bottom=3 * RES, below=8), 8, _ascent_line(8),
        ["boss_cap_l", "boss_cap_r"])

    hud["providers"] = keep + providers
    with open(hud_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(hud, f, ensure_ascii=True, indent=2)
        f.write("\n")

    # 사망 띠 (minecraft:default 의 그림 그대로 자리, 높이 22 글꼴 픽셀): 4배 그림으로 바꾼다. 진행 폭은 같다 (65)
    band = death_band()
    band.save(os.path.join(pack, "assets", "souls", "textures", "font", "hud_death_band.png"))
    for n, i in (("death_band_l", 0), ("death_band_m", 1), ("death_band_r", 2)):
        w = advance(band, i * 64 * RES, 64 * RES, 22)
        assert w == g[n]["width"], f"{n} 진행 폭 {w} != {g[n]['width']}"
    # 조준점
    ch = os.path.join(pack, "assets", "minecraft", "textures", "gui", "sprites", "hud", "crosshair.png")
    crosshair().save(ch)

    text = write_glyphs(base_glyphs_text, changes)
    return [], text
