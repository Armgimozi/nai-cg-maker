"""
미리보기 그림 (pack/preview/). 사람이 눈으로 보고 "AI 같은지" 가리는 데 쓴다 (10.7). 팩에는 들어가지 않는다.

  you_died.png      제목을 6배로 (그림자 없이 / 바닐라 그림자까지)
  death_screen.png  사망 화면 흉내 (GUI 배율 3, 바닐라의 붉은 덧칠과 글자 그림자까지)
  hud.png           다크 소울 HUD 네 장면 (hud.preview_hud: 왼쪽 위 막대 셋과 오른쪽 아래 소울 상자)
  pack_icon.png     팩 그림을 4배로
  gui_*.png         gui_skin 이 다시 그린 HUD·창·단추 (gui_skin.write_previews)
  align_*.png       우리 창·단축 슬롯 그림을 바닐라 그림과 겹쳐 칸 자리가 같음을 보인다 (gui_skin.align_proof)
실제 1.21.11 클라이언트(가상 화면)에서 찍은 그림은 여기 두지 않는다: dist/screenshots/m0/ (tools/client/m0_shots.sh)

바닐라 단추·단축 슬롯·하트 그림은 클라이언트 jar 에서 읽는다 (환경 변수 SOULS_CLIENT_JAR, 없으면 단순한 상자로 대신한다).
한글 단추 글은 unifont 가 있으면 그것으로 쓴다 (마인크래프트도 한글을 unifont 로 그린다).
"""
import io
import os
import zipfile

from PIL import Image, ImageDraw, ImageFont

UNIFONT = ("/usr/share/fonts/opentype/unifont/unifont.otf", "/usr/share/fonts/opentype/unifont/unifont_jp.otf",
           "/usr/share/fonts/truetype/unifont/unifont.ttf")


class Vanilla:
    """
    GUI 그림을 꺼낸다. 만든 팩 폴더(pack/resourcepack)에 있으면 그것을 (gui_skin 이 다시 그린 단추·단축 슬롯·하트),
    없으면 클라이언트 jar 의 바닐라 그림을. 둘 다 없으면 None 을 돌려준다.
    """

    PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resourcepack")

    def __init__(self, jar):
        self.z = zipfile.ZipFile(jar) if jar and os.path.exists(jar) else None

    def sprite(self, path):
        own = os.path.join(self.PACK, "assets", "minecraft", "textures", "gui", "sprites", path + ".png")
        if os.path.exists(own):
            return Image.open(own).convert("RGBA")
        if not self.z:
            return None
        try:
            return Image.open(io.BytesIO(self.z.read("assets/minecraft/textures/gui/sprites/" + path + ".png"))).convert("RGBA")
        except KeyError:
            return None


def enlarge(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def unifont_text(text, scale):
    """마인크래프트처럼 unifont 를 8 GUI 픽셀 높이로 그린다 (scale = GUI 배율). 글꼴이 없으면 None."""
    path = next((p for p in UNIFONT if os.path.exists(p)), None)
    if not path:
        return None
    f = ImageFont.truetype(path, 16)
    w = int(f.getlength(text)) + 2
    im = Image.new("L", (w, 16), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((0, 0), text, font=f, fill=255)
    return im.resize((max(1, w * scale // 2), 8 * scale), Image.NEAREST)


# 바닐라 옛 색 부호 (§0..§f) 가운데 미리보기에 쓰는 것
LEGACY_COLORS = {"7": (170, 170, 170), "8": (85, 85, 85), "f": (255, 255, 255)}


def legacy(text, color=(224, 224, 224)):
    """글 앞의 § 색 부호를 떼고 그 색을 돌려준다 (사망 화면 단추 글, gen_pack.DEATH_LANG)."""
    while len(text) >= 2 and text[0] == "\u00a7":
        color = LEGACY_COLORS.get(text[1].lower(), color)
        text = text[2:]
    return text, color


def paste_text(canvas, text, cx, y, scale, color=(224, 224, 224), shadow=True):
    m = unifont_text(text, scale)
    if m is None:
        return
    x = cx - m.width // 2
    if shadow:
        canvas.paste(Image.new("RGBA", m.size, (56, 56, 56, 255)), (x + scale, y + scale), m)
    canvas.paste(Image.new("RGBA", m.size, color + (255,)), (x, y), m)


def nine_slice(sprite, w, h, border=3):
    """단추 그림을 9조각으로 늘인다 (바닐라 button.png 와 같은 방식)."""
    out = Image.new("RGBA", (w, h))
    sw, sh = sprite.size
    b = border
    out.paste(sprite.crop((0, 0, b, b)), (0, 0))
    out.paste(sprite.crop((sw - b, 0, sw, b)), (w - b, 0))
    out.paste(sprite.crop((0, sh - b, b, sh)), (0, h - b))
    out.paste(sprite.crop((sw - b, sh - b, sw, sh)), (w - b, h - b))
    out.paste(sprite.crop((b, 0, sw - b, b)).resize((w - 2 * b, b), Image.NEAREST), (b, 0))
    out.paste(sprite.crop((b, sh - b, sw - b, sh)).resize((w - 2 * b, b), Image.NEAREST), (b, h - b))
    out.paste(sprite.crop((0, b, b, sh - b)).resize((b, h - 2 * b), Image.NEAREST), (0, b))
    out.paste(sprite.crop((sw - b, b, sw, sh - b)).resize((b, h - 2 * b), Image.NEAREST), (w - b, b))
    out.paste(sprite.crop((b, b, sw - b, sh - b)).resize((w - 2 * b, h - 2 * b), Image.NEAREST), (b, b))
    return out


def dusk_scene(w, h):
    """잿빛 저녁 (시간 13000) 의 대충 그린 배경: 어두운 하늘, 먼 성벽 윤곽, 돌바닥. 미리보기 전용."""
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(46 - 20 * t), int(48 - 20 * t), int(60 - 24 * t), 255))
    base = int(h * 0.62)
    xs = list(range(0, w + 40, 40))
    for i, x in enumerate(xs):
        top = base - (18 + (i * 37) % 30) * h // 270
        d.rectangle([x, top, x + 34, base], fill=(28, 27, 30, 255))
    d.rectangle([0, base, w, h], fill=(38, 36, 34, 255))
    return im


def death_overlay(w, h):
    """바닐라 사망 화면 덧칠: 위 0x60500000 → 아래 0xA0803030."""
    ov = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(ov)
    for y in range(h):
        t = y / max(1, h - 1)
        a = int(0x60 + (0xA0 - 0x60) * t)
        col = (int(0x50 + (0x80 - 0x50) * t), int(0x30 * t), int(0x30 * t), a)
        d.line([(0, y), (w, y)], fill=col)
    return ov


def draw_glyph_string(canvas, sheet, cell_w, glyphs, chars, x, y, unit, height_units, shadow=True):
    """
    글꼴 픽셀 단위로 문자열을 그린다. unit = 글꼴 1픽셀이 화면 몇 픽셀인지 (사망 화면 제목은 GUI 배율 × 2).
    그림자는 바닐라처럼 1 글꼴 픽셀 아래·오른쪽에 색 × 0.25.
    """
    by_char = {g.char: g for g in glyphs}
    order = {ch: i for i, ch in enumerate(sorted(g.char for g in glyphs if g.kind == "bitmap" and g.font == "minecraft:default"
                                                     and g.name.startswith("you_died_")))}
    cell_h = sheet.height
    tex_scale = unit * height_units / cell_h      # 그림 1칸 = 화면 몇 픽셀
    passes = ((1, 0.25), (0, 1.0)) if shadow else ((0, 1.0),)
    for off, mul in passes:
        cx = x
        for ch in chars:
            g = by_char[ch]
            if g.kind == "bitmap" and ch in order:     # 글자만 그린다 (사망 화면 띠는 미리보기에서 건너뛴다)
                i = order[ch]
                cell = sheet.crop((i * cell_w, 0, (i + 1) * cell_w, cell_h))
                if mul != 1.0:
                    r, gg, b, a = cell.split()
                    cell = Image.merge("RGBA", [c.point(lambda v: int(v * mul)) for c in (r, gg, b)] + [a])
                big = cell.resize((int(cell_w * tex_scale), int(cell_h * tex_scale)), Image.NEAREST)
                canvas.alpha_composite(big, (int(cx + off * unit), int(y + off * unit)))
            cx += g.width * unit
    return cx


def string_width(glyphs, chars):
    by_char = {g.char: g for g in glyphs}
    return sum(by_char[ch].width for ch in chars)


def death_screen(out_dir, sheet, cell_w, glyphs, title, height_units, ascent, lang, vanilla, gui=3):
    W, H = 427 * gui, 240 * gui          # 1280×720 창, GUI 배율 3
    w, h = W // gui, H // gui
    canvas = dusk_scene(W, H)
    canvas.alpha_composite(death_overlay(W, H))
    unit = gui * 2                        # 제목은 2배로 그려진다
    tw = string_width(glyphs, title)
    # 바닐라: drawCenteredString(title, width/2/2, 30) 를 2배로. 글자 위쪽 = 줄 y + 7 - ascent
    x = (w // 2 // 2) * unit - tw * unit // 2
    y = (30 + 7 - ascent) * unit
    draw_glyph_string(canvas, sheet, cell_w, glyphs, title, x, y, unit, height_units)
    btn = vanilla.sprite("widget/button")
    for i, key in enumerate(("deathScreen.respawn", "deathScreen.titleScreen")):
        bx, by = (w // 2 - 100) * gui, (h // 4 + 72 + 24 * i) * gui
        if btn is not None:
            canvas.alpha_composite(enlarge(nine_slice(btn, 200, 20), gui), (bx, by))
        else:
            ImageDraw.Draw(canvas).rectangle([bx, by, bx + 200 * gui, by + 20 * gui], fill=(80, 80, 80, 255),
                                             outline=(20, 20, 20, 255), width=gui)
        text, color = legacy(lang[key])
        paste_text(canvas, text, bx + 100 * gui, by + 6 * gui, gui, color)
    canvas.save(os.path.join(out_dir, "death_screen.png"))


def hud(out_dir, bg, fill, vanilla, gui=3, stamina=0.7):
    W, H = 427 * gui, 120 * gui
    w, h = W // gui, H // gui
    canvas = dusk_scene(W, H * 2).crop((0, H, W, H * 2))
    small = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hotbar = vanilla.sprite("hud/hotbar")
    hx, hy = w // 2 - 91, h - 22
    if hotbar is not None:
        small.alpha_composite(hotbar, (hx, hy))
        sel = vanilla.sprite("hud/hotbar_selection")
        if sel is not None:
            small.alpha_composite(sel, (hx - 1 + 20 * 2, hy - 1))
    else:
        ImageDraw.Draw(small).rectangle([hx, hy, hx + 181, hy + 21], outline=(90, 90, 90, 255))
    ex, ey = w // 2 - 91, h - 32 + 3
    small.alpha_composite(bg, (ex, ey))
    n = int(stamina * 183)
    if n > 0:
        small.alpha_composite(fill.crop((0, 0, n, fill.height)), (ex, ey))
    heart_c, heart_f = vanilla.sprite("hud/heart/container"), vanilla.sprite("hud/heart/full")
    if heart_c is not None and heart_f is not None:
        for i in range(9, -1, -1):     # 클라이언트처럼 오른쪽부터 (왼쪽 하트의 x=8 이 오른쪽 하트의 x=0 을 덮는다)
            small.alpha_composite(heart_c, (w // 2 - 91 + i * 8, h - 39))
            small.alpha_composite(heart_f, (w // 2 - 91 + i * 8, h - 39))
    canvas.alpha_composite(enlarge(small, gui))
    canvas.save(os.path.join(out_dir, "hud.png"))


def bar_sheet(out_dir, bg, fill, k=6):
    rows = []
    rows.append(enlarge(bg, k))
    rows.append(enlarge(fill, k))
    for t in (0.0, 0.25, 0.6, 1.0):
        im = bg.copy()
        n = int(t * 183)
        if n:
            im.alpha_composite(fill.crop((0, 0, n, fill.height)), (0, 0))
        rows.append(enlarge(im, k))
    pad = 6
    sheet = Image.new("RGBA", (bg.width * k + pad * 2, sum(r.height + pad for r in rows) + pad), (24, 24, 26, 255))
    y = pad
    for r in rows:
        sheet.alpha_composite(r, (pad, y))
        y += r.height + pad
    sheet.save(os.path.join(out_dir, "stamina_bar.png"))


def you_died(out_dir, sheet, cell_w, glyphs, title, height_units, k=6):
    """제목을 실제 글자 폭대로 늘어놓아 k 배로 (위: 그림자 없이, 아래: 바닐라 그림자까지)."""
    unit = k * sheet.height // height_units          # 글꼴 1픽셀 = 그림 2칸
    tw = string_width(glyphs, title) * unit
    pad = 4 * k
    im = Image.new("RGBA", (tw + pad * 2, (sheet.height * k + pad) * 2 + pad), (30, 12, 11, 255))
    draw_glyph_string(im, sheet, cell_w, glyphs, title, pad, pad, unit, height_units, shadow=False)
    draw_glyph_string(im, sheet, cell_w, glyphs, title, pad, pad * 2 + sheet.height * k, unit, height_units)
    im.save(os.path.join(out_dir, "you_died.png"))


def pack_icon(out_dir, icon, k=4):
    enlarge(icon, k).save(os.path.join(out_dir, "pack_icon.png"))


def write_all(out_dir, built, vanilla_jar=None):
    """built: gen_pack 이 넘기는 dict (sheet, cell_w, glyphs, title, height, ascent, lang, icon)."""
    os.makedirs(out_dir, exist_ok=True)
    vanilla = Vanilla(vanilla_jar or os.environ.get("SOULS_CLIENT_JAR"))
    you_died(out_dir, built["sheet"], built["cell_w"], built["glyphs"], built["title"], built["height"])
    death_screen(out_dir, built["sheet"], built["cell_w"], built["glyphs"], built["title"], built["height"],
                 built["ascent"], built["lang"], vanilla)
    if "bar_bg" in built:      # 옛 경험치 막대 스태미나 (지금 HUD 미리보기는 hud.preview_hud 의 hud.png)
        bar_sheet(out_dir, built["bar_bg"], built["bar_fill"])
        hud(out_dir, built["bar_bg"], built["bar_fill"], vanilla)
    pack_icon(out_dir, built["icon"])
