"""
mood_serif 장식과 글꼴 정의.

  글꼴 정의   minecraft:default 에 [제목 밑 실선 그림 글자, 빈칸 글자, 본문 TTF 둘, 개인 영역 Cinzel] 을 덧붙인다 (팩의 같은 글꼴
              파일은 위 팩의 공급자가 앞에 온다. 바닐라 비트맵·유니폰트는 TTF 에 없는 글자에만 쓰인다). souls:title = Cinzel +
              굵은 명조, 나머지는 minecraft:default 로
  실선        제목 밑 금빛 실선 한 줄. 가운데 작은 마름모, 양 끝은 길게 옅어진다. 실선은 GUI 픽셀의 4배 해상도로 그려
              (height 로 줄인다) 획이 GUI 반 픽셀 굵기다 (배율 4 에서 2 화면 픽셀). 둘:
                SEP_TITLE  가운데 맞춤 제목 밑 (일시 정지·휴식 창): 글 아래 GUI 3 에 그린다
                SEP_ITEM   설명 칸 이름 밑 (무기 설명 첫 줄 앞에 붙여 이름 줄과 첫 줄 사이 틈에 그린다): 왼쪽 끝에 작은 마름모,
                           오른쪽으로 옅어진다
  빈칸 글자   U+E200+k 는 -k/4, U+E600+k 는 +k/4 GUI 픽셀 (k 1..1023). 언어 파일에서 실선을 제자리에 놓는다
  창          컨테이너 그림 (inventory, generic_54, crafting_table) 을 4배로 키워 (가장 가까운 점, 1배 그림과 같게 보인다)
              판 몸에 옅은 비네트 (가운데 58% → 가장자리 82%), 창 제목 밑에 짧은 실선
  소울 숫자   HUD 소울 상자의 숫자 그림 (souls:hud hud_digits) 을 EB Garamond 숫자로 (4배 해상도, 같은 진행 폭 7)
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

import palette
import style

SUPER = 4                      # 창 그림의 해상도 (GUI 픽셀당 텍셀)
SEP_RES = 2                    # 실선 그림 글자의 해상도. 글꼴 그림 한 장은 256 텍셀 판에 들어가야 해서 (넘으면 빈 네모) 2배
SEP_TITLE = ""
SEP_ITEM = ""
SEP_TITLE_W = 120              # GUI 픽셀 (그림 폭. 진행 폭은 +1)
SEP_ITEM_W = 104
SEP_H = 4                      # 실선 그림 높이 (GUI 픽셀): 마름모 3.5, 줄은 가운데 (위에서 2)
SEP_TITLE_TOP = 9              # 가운데 제목 밑 실선 그림의 위 = 제목 줄 위 + 9 (줄은 + 11, 명조 글자 아래 + 7.5 에서 3.5 아래)
NEG0, POS0 = 0xE200, 0xE600

LINE = "parch2"               # 실선의 긴 몫: 흐린 옛 금빛 (끝으로 갈수록 옅어진다)
GEM = "parch3"                # 마름모 테
GEM_CORE = "bronze3"          # 마름모 속

PANEL_RGBA = palette.c("ash0", 185)


def _rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _wj(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=True, indent=2)
        f.write("\n")


def space(px):
    """GUI px (1/4 단위로 반올림) 만큼 펜을 옮기는 빈칸 글자열."""
    q = int(round(px * 4))
    out = ""
    base = NEG0 if q < 0 else POS0
    q = abs(q)
    while q > 0:
        k = min(q, 1023)
        out += chr(base + k)
        q -= k
    return out


def space_provider():
    adv = {}
    for k in range(1, 1024):
        adv[chr(NEG0 + k)] = -k / 4
        adv[chr(POS0 + k)] = k / 4
    return {"type": "space", "advances": adv}


# ─────────────────────────── 실선 그림 ───────────────────────────

def _put(px, x, y, name, a):
    if a <= 0:
        return
    r, g, b, _ = palette.c(name)
    old = px[x, y]
    if old[3] >= a:
        return
    px[x, y] = (r, g, b, min(255, int(a)))


def _gem(px, cx, cy, half):
    """가운데 (cx, cy) 의 마름모 (텍셀). half = 반 대각선. 테는 GEM, 속은 GEM_CORE."""
    for y in range(cy - half, cy + half + 1):
        for x in range(cx - half, cx + half + 1):
            d = abs(x - cx) + abs(y - cy)
            if d <= half:
                _put(px, x, y, GEM if d >= half - 1 else GEM_CORE, 255)


def separator(width, kind):
    """실선 한 장 (폭 width GUI 픽셀, 높이 SEP_H, SUPER 배 해상도). kind = "title" (가운데 마름모, 양 끝 옅게) 또는
    "item" (왼쪽 끝 마름모, 오른쪽으로 옅게). 맨 오른쪽 열에 거의 투명한 점 (알파 1) 을 두어 진행 폭을 그림 폭 + 1 로 고정."""
    R = SEP_RES
    W, H = width * R, SEP_H * R
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    cy = H // 2                          # 줄: 한 텍셀 = GUI 반 픽셀
    if kind == "title":
        cx = W // 2
        for x in range(W):
            t = abs(x - cx) / (W / 2)       # 0 가운데 → 1 끝
            a = 235 * (1 - t ** 2.2) if t < 1 else 0
            _put(px, x, cy, LINE, a)
        # 마름모 양옆의 짧은 밝은 날개, 그 바깥의 작은 점 둘
        for s in (-1, 1):
            for i in range(5, 18):
                _put(px, cx + s * i, cy, GEM, 255 * (1 - (i - 5) / 13))
            _put(px, cx + s * 20, cy, GEM, 230)
            _put(px, cx + s * 20 - (1 if s < 0 else 0), cy, GEM, 230)
        _gem(px, cx, cy, 3)
        _gem(px, cx - 1, cy, 3)
    else:
        x0 = 3
        for x in range(x0, W):
            t = (x - x0) / (W - x0)
            a = 235 * (1 - t ** 1.6)
            _put(px, x, cy, LINE, a)
        for i in range(4, 16):
            _put(px, x0 + i, cy, GEM, 255 * (1 - (i - 4) / 12))
        _gem(px, x0, cy, 3)
    _put(px, W - 1, H - 1, LINE, 1)
    return img


def sep_advance(width):
    return width + 1


# ─────────────────────────── 창 그림 ───────────────────────────

CONTAINERS = {
    # 이름: (판 크기, 제목 자리 [(x, y, 실선 폭)])
    "inventory": ((176, 166), [(97, 6, 66)]),
    "crafting_table": ((176, 166), [(29, 6, 84)]),
    "generic_54": ((176, 222), [(8, 6, 84)]),
}
TITLE_RULE_Y = 9.5            # 제목 줄 위에서 실선까지 (GUI 픽셀): 명조 글자 아래 (줄 위 + 7.5) 와 칸 테 (줄 위 + 12) 사이


def vignette_alpha(x, y, w, h):
    """판 몸 알파 (가운데 옅고 가장자리 진하게). x, y 는 GUI 픽셀 (실수)."""
    dx = (x - w / 2) / (w / 2)
    dy = (y - h / 2) / (h / 2)
    r = min(1.0, math.sqrt(dx * dx * 0.55 + dy * dy * 0.45))
    a = 148 + (210 - 148) * (r ** 1.8)
    return int(round(a))


def container(path, size, titles):
    src = Image.open(path).convert("RGBA")
    big = src.resize((src.width * SUPER, src.height * SUPER), Image.NEAREST)
    px = big.load()
    w, h = size
    for y in range(h * SUPER):
        for x in range(w * SUPER):
            if px[x, y] == PANEL_RGBA:
                a = vignette_alpha((x + 0.5) / SUPER, (y + 0.5) / SUPER, w, h)
                px[x, y] = PANEL_RGBA[:3] + (a,)
    for tx, ty, rw in titles:
        # 창 제목 (왼쪽 맞춤) 밑 실선: 왼쪽 끝 작은 마름모, 오른쪽으로 옅어진다. 칸 테 (줄 위 + 11) 위 GUI 반 픽셀 자리
        sep = separator(rw, "item")
        k = SUPER // SEP_RES
        sep = sep.resize((sep.width * k, sep.height * k), Image.NEAREST)
        y = int((ty + TITLE_RULE_Y) * SUPER)
        big.alpha_composite(sep, (tx * SUPER - 2 * k, y - sep.height // 2))
    big.save(path)


# ─────────────────────────── 소울 숫자 ───────────────────────────

def digits_sheet(font_path, out_path):
    """hud_digits.png (10 칸, 칸 6×8 GUI) 를 SUPER 배로: EB Garamond 숫자, 뼈빛, 오른쪽 아래 GUI 반 픽셀 먹 그림자."""
    cw, ch = 6 * SUPER, 8 * SUPER
    img = Image.new("RGBA", (cw * 10, ch), (0, 0, 0, 0))
    font = ImageFont.truetype(font_path, int(ch * 1.18))
    ink = palette.c("bone2")
    shadow = palette.c("ink0", 150)
    for d in range(10):
        glyph = Image.new("L", (cw * 2, ch * 2), 0)
        dr = ImageDraw.Draw(glyph)
        bbox = dr.textbbox((0, 0), str(d), font=font)
        gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        ox = (cw - gw) // 2 - bbox[0]
        oy = (ch - 2 - gh) - bbox[1]          # 바탕선이 칸 아래에서 2 텍셀 위
        dr.text((ox, oy), str(d), font=font, fill=255)
        mask = glyph.crop((0, 0, cw, ch))
        cell = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        sh = Image.new("RGBA", (cw, ch), shadow)
        sh.putalpha(mask.point(lambda v: v * shadow[3] // 255))
        cell.alpha_composite(sh, (2, 2))
        fg = Image.new("RGBA", (cw, ch), ink)
        fg.putalpha(mask)
        cell.alpha_composite(fg)
        cpx = cell.load()
        if cpx[cw - 1, ch - 1][3] == 0:
            cpx[cw - 1, ch - 1] = palette.c("ink0", 1)
        img.alpha_composite(cell, (d * cw, 0))
    img.save(out_path)


def _hud_digits(pack, info):
    hud_json = os.path.join(pack, "assets", "souls", "font", "hud.json")
    d = _rj(hud_json)
    for p in d["providers"]:
        if p.get("file") == "souls:font/hud_digits.png":
            path = os.path.join(pack, "assets", "souls", "textures", "font", "hud_digits.png")
            digits_sheet(info["files"]["serif_la"]["path"], path)
            p["height"] = 8          # 그림 칸 32 텍셀을 8 GUI 픽셀로 (진행 폭 = 24 × 1/4 + 1 = 7, 1배 그림과 같다)
    _wj(hud_json, d)


# ─────────────────────────── 빌드 ───────────────────────────

def build(pack, info):
    font_dir = os.path.join(pack, "assets", "souls", "textures", "font")
    os.makedirs(font_dir, exist_ok=True)
    separator(SEP_TITLE_W, "title").save(os.path.join(font_dir, "serif_sep_title.png"))
    separator(SEP_ITEM_W, "item").save(os.path.join(font_dir, "serif_sep_item.png"))
    # 실선 그림 글자. ascent 는 줄 위 (바탕선 위 7) 기준: 그림 위 = 줄 위 + 7 - ascent
    seps = [
        {"type": "bitmap", "file": "souls:font/serif_sep_title.png", "height": SEP_H,
         "ascent": 7 - SEP_TITLE_TOP, "chars": [SEP_TITLE]},
        # 설명 칸: 이름 줄 (제목 글꼴, 줄 위 - 0.5 .. + 8.5) 과 첫 줄 사이 틈의 가운데에 줄이 오게 (실제 클라이언트에서 첫 줄 위
        # - 1.75). ascent 는 높이보다 클 수 없어 그림 아래를 비운 키 큰 그림 (13) 으로
        {"type": "bitmap", "file": "souls:font/serif_sep_item_tall.png", "height": 13, "ascent": 12, "chars": [SEP_ITEM]},
    ]
    tall = Image.new("RGBA", (SEP_ITEM_W * SEP_RES, 13 * SEP_RES), (0, 0, 0, 0))
    tall.alpha_composite(separator(SEP_ITEM_W, "item"), (0, 1))
    tall.save(os.path.join(font_dir, "serif_sep_item_tall.png"))

    dpath = os.path.join(pack, "assets", "minecraft", "font", "default.json")
    d = _rj(dpath)
    d["providers"] += seps + [space_provider(), {"type": "space", "advances": {" ": style.SPACE}}] \
        + info["providers_body"] + [style.ttf("title_la", style.TITLE[0][1], style.TITLE[0][2])]
    _wj(dpath, d)
    _wj(os.path.join(pack, "assets", "souls", "font", "title.json"),
        {"providers": [{"type": "space", "advances": {" ": style.SPACE}}] + info["providers_title"]
         + [{"type": "reference", "id": "minecraft:default"}]})

    gui = os.path.join(pack, "assets", "minecraft", "textures", "gui", "container")
    for name, (size, titles) in CONTAINERS.items():
        container(os.path.join(gui, name + ".png"), size, titles)
    _hud_digits(pack, info)
