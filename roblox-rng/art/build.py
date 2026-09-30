#!/usr/bin/env python3
"""Render art/src/*.svg -> art/png/*.png and compose art/preview.png.

Needs:  pip install resvg-py pillow pyoxipng   (pyoxipng is optional)
Usage:  python3 art/build.py            # render everything
        python3 art/build.py coin dice  # render only these (preview is still rebuilt)
"""
import io
import re
import sys
from pathlib import Path

import resvg_py
from PIL import Image, ImageDraw, ImageFont

try:
    import oxipng  # pyoxipng
except ImportError:  # optimisation is nice-to-have
    oxipng = None

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "png"

# 9-slice skins: SliceCenter rect (left, top, right, bottom) in source pixels.
SLICE = {
    "button_face": (64, 64, 192, 192),
    "button_shadow": (64, 64, 192, 192),
    "panel_paper": (64, 64, 192, 192),
    "pill": (64, 64, 192, 192),
    "tag": (64, 64, 192, 192),
}
SKINS = list(SLICE) + ["sunburst"]

ICON_ORDER = [
    "coin", "globe", "passport", "album", "hammer", "park", "plaza", "dice",
    "clover", "star", "star_empty", "news", "lock", "auto", "close", "check",
    "arrow_up", "stamp_home", "stamp_europe", "stamp_asia", "stamp_africa",
    "stamp_americas", "stamp_legend",
]

INK = (30, 27, 46)
SKY = (57, 160, 255)
SKY_D = (31, 111, 204)
GRASS = (76, 217, 100)
GRASS_D = (46, 158, 69)
SUN = (255, 197, 61)
SUN_D = (217, 144, 15)
CORAL = (255, 94, 91)
CORAL_D = (201, 58, 56)
GRAPE = (155, 107, 255)
GRAPE_D = (106, 69, 201)
CREAM = (255, 244, 220)


def svg_size(text):
    w = re.search(r'<svg[^>]*\swidth="(\d+)"', text)
    h = re.search(r'<svg[^>]*\sheight="(\d+)"', text)
    return int(w.group(1)), int(h.group(1))


def render(svg_path):
    text = svg_path.read_text()
    w, h = svg_size(text)
    data = bytes(resvg_py.svg_to_bytes(svg_path=str(svg_path), width=w, height=h))
    # normalise through Pillow (drops metadata) then squeeze with oxipng
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if oxipng is not None:
        data = oxipng.optimize_from_memory(data, level=4, strip=oxipng.StripChunks.safe())
    if len(data) > 100_000:  # still big: palette-quantise (keeps alpha)
        q = im.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
        buf = io.BytesIO()
        q.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
    out = OUT / (svg_path.stem + ".png")
    out.write_bytes(data)
    return out, len(data)


# ---------------------------------------------------------------- preview helpers
def font(size, bold=True):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def tint(im, rgb):
    """Roblox ImageColor3: multiply RGB, keep alpha."""
    r, g, b, a = im.split()
    r = r.point(lambda v: v * rgb[0] // 255)
    g = g.point(lambda v: v * rgb[1] // 255)
    b = b.point(lambda v: v * rgb[2] // 255)
    return Image.merge("RGBA", (r, g, b, a))


def nine_slice(im, rect, size, scale=1.0):
    """Roblox ScaleType.Slice with SliceCenter=rect and SliceScale=scale."""
    W, H = size
    l, t, r, b = rect
    sw, sh = im.size
    # source column/row edges and destination column/row edges
    sx = [0, l, r, sw]
    sy = [0, t, b, sh]
    cl, cr = round(l * scale), round((sw - r) * scale)
    ct, cb = round(t * scale), round((sh - b) * scale)
    dx = [0, cl, max(cl, W - cr), W]
    dy = [0, ct, max(ct, H - cb), H]
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i in range(3):
        for j in range(3):
            box = (sx[i], sy[j], sx[i + 1], sy[j + 1])
            dw, dh = dx[i + 1] - dx[i], dy[j + 1] - dy[j]
            if dw <= 0 or dh <= 0 or box[2] <= box[0] or box[3] <= box[1]:
                continue
            piece = im.crop(box).resize((dw, dh), Image.Resampling.LANCZOS)
            out.alpha_composite(piece, (dx[i], dy[j]))
    return out


def small(im, px):
    return im.resize((px, px), Image.Resampling.LANCZOS)


def paste(canvas, im, xy):
    canvas.alpha_composite(im, (int(xy[0]), int(xy[1])))


def label(d, xy, text, size=15, fill=(245, 245, 245), anchor="mm"):
    d.text(xy, text, font=font(size), fill=fill, anchor=anchor)


def ribbon(img, size, color, dark):
    """Ui.ribbon: code-drawn plate (shadow base + lighter face + gloss + Ink edge) with the two tail images
    (ribbon_tail_l/r, 56x50 per 50 px of plate height, right one mirrored) behind it. Returns (image, (plate x, plate y))."""
    w, h = size
    k = h / 50
    tw, th = round(56 * k), round(50 * k)
    left, top = round(-36 * k), round(17 * k)
    pad = -left
    out = Image.new("RGBA", (w + 2 * pad, h + top + th), (0, 0, 0, 0))
    for name, x in (("ribbon_tail_l", 0), ("ribbon_tail_r", pad + w - (left + tw))):  # right = mirror of left
        if name in img:
            out.alpha_composite(tint(img[name].resize((tw, th), Image.Resampling.LANCZOS), color), (x, top))
    d = ImageDraw.Draw(out)
    r, shade, edge = round(12 * k), round(9 * k), 3
    box = (pad, 0, pad + w - 1, h - 1)
    d.rounded_rectangle(box, r, fill=dark, outline=INK, width=edge)
    d.rounded_rectangle((pad + edge, edge, pad + w - 1 - edge, h - 1 - shade), r - edge, fill=color)
    d.rounded_rectangle((pad + round(10 * k), round(5 * k), pad + w - round(10 * k), round(8 * k)), 2, fill=(255, 255, 255))
    return out, (pad, 0)


def chunky(face, shadow, size, color, dark, scale=0.25, drop=6):
    """Compose a button the way Ui.chunkyButton would (shadow plate + tinted face)."""
    W, H = size
    out = Image.new("RGBA", (W, H + drop), (0, 0, 0, 0))
    out.alpha_composite(tint(nine_slice(shadow, SLICE["button_shadow"], (W, H), scale), dark), (0, drop))
    out.alpha_composite(tint(nine_slice(face, SLICE["button_face"], (W, H), scale), color), (0, 0))
    return out


def build_preview(images):
    CW, CH = 196, 200  # icon cell
    cols = 7
    rows = (len(ICON_ORDER) + cols - 1) // cols
    W = cols * CW + 40
    icons_h = 70 + rows * CH
    skins_h = 1180
    H = icons_h + skins_h
    bg = (118, 118, 124)
    canvas = Image.new("RGBA", (W, H), bg + (255,))
    d = ImageDraw.Draw(canvas)
    label(d, (20, 30), "ICONS  (128px  |  36px on cream / on dark pill / on sky button)", 22, anchor="lm")

    for n, name in enumerate(ICON_ORDER):
        if name not in images:
            continue
        im = images[name]
        cx = 20 + (n % cols) * CW
        cy = 60 + (n // cols) * CH
        d.rounded_rectangle((cx + 4, cy + 4, cx + CW - 4, cy + CH - 4), 14, fill=(104, 104, 110))
        paste(canvas, small(im, 128), (cx + (CW - 128) // 2, cy + 8))
        label(d, (cx + CW // 2, cy + 146), name, 14)
        # 36px legibility strip
        s = small(im, 36)
        y = cy + 158
        d.rounded_rectangle((cx + 14, y - 2, cx + 60, y + 38), 8, fill=CREAM)
        paste(canvas, s, (cx + 19, y))
        d.rounded_rectangle((cx + 72, y - 2, cx + 122, y + 38), 20, fill=(38, 34, 56))
        paste(canvas, s, (cx + 79, y))
        d.rounded_rectangle((cx + 134, y - 2, cx + 180, y + 38), 10, fill=SKY)
        paste(canvas, s, (cx + 139, y))

    # ---------------------------------------------------------------- skins
    y0 = icons_h + 10
    label(d, (20, y0), "SKINS  (raw 256px with SliceCenter box  |  in use)", 22, anchor="lm")
    y0 += 30
    x = 20
    for name in SKINS:
        if name not in images:
            continue
        im = images[name]
        th = small(im, 128)
        chk = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chk)
        for i in range(0, 128, 16):
            for j in range(0, 128, 16):
                if (i + j) // 16 % 2 == 0:
                    cd.rectangle((i, j, i + 15, j + 15), fill=(140, 140, 146, 255))
        paste(canvas, chk, (x, y0))
        paste(canvas, th, (x, y0))
        if name in SLICE:
            l, t, r, b = [v // 2 for v in SLICE[name]]
            d.rectangle((x + l, y0 + t, x + r, y0 + b), outline=(255, 60, 200), width=1)
        label(d, (x + 64, y0 + 142), name, 13)
        x += 150

    img = images
    y = y0 + 170
    # buttons: every palette colour, a couple of sizes
    if "button_face" in img and "button_shadow" in img:
        bx = 20
        for col, dark, ic in [(SKY, SKY_D, "album"), (GRAPE, GRAPE_D, "passport"), (SUN, SUN_D, "hammer"),
                              (GRASS, GRASS_D, "park"), (CORAL, CORAL_D, "close")]:
            b = chunky(img["button_face"], img["button_shadow"], (96, 96), col, dark, 0.3)
            paste(canvas, b, (bx, y))
            if ic in img:
                paste(canvas, small(img[ic], 64), (bx + 16, y + 12))
            bx += 116
        # big roll button
        b = chunky(img["button_face"], img["button_shadow"], (300, 100), GRASS, GRASS_D, 0.35, 8)
        paste(canvas, b, (bx + 10, y))
        if "globe" in img:
            paste(canvas, small(img["globe"], 80), (bx + 30, y + 8))
        label(d, (bx + 200, y + 50), "ROLL", 34, fill=(255, 255, 255))
        if "auto" in img:
            b2 = chunky(img["button_face"], img["button_shadow"], (96, 96), (255, 150, 60), (200, 95, 20), 0.3)
            paste(canvas, b2, (bx + 330, y))
            paste(canvas, small(img["auto"], 72), (bx + 342, y + 10))
            b3 = chunky(img["button_face"], img["button_shadow"], (96, 96), (170, 170, 178), (110, 110, 120), 0.3)
            paste(canvas, b3, (bx + 446, y))
            paste(canvas, small(img["auto"], 72), (bx + 458, y + 10))
        # tiny buttons (36px icon on 52px button)
        tx = bx + 570
        for col, dark, ic in [(SKY, SKY_D, "album"), (SUN, SUN_D, "arrow_up"), (CORAL, CORAL_D, "lock")]:
            b = chunky(img["button_face"], img["button_shadow"], (52, 52), col, dark, 0.18, 4)
            paste(canvas, b, (tx, y + 20))
            if ic in img:
                paste(canvas, small(img[ic], 36), (tx + 8, y + 27))
            tx += 64
    y += 130

    # panel with ribbon title and pills / tags inside
    if "panel_paper" in img:
        pw, ph = 620, 440
        panel = nine_slice(img["panel_paper"], SLICE["panel_paper"], (pw, ph), 0.5)
        paste(canvas, panel, (20, y + 30))
        rb, (ox, oy) = ribbon(img, (300, 56), GRAPE, GRAPE_D)
        paste(canvas, rb, (20 + (pw - 300) // 2 - ox, y + 6 - oy))
        label(d, (20 + pw // 2, y + 30), "PASSPORT", 26, fill=(255, 255, 255))
        if "close" in img:
            paste(canvas, small(img["close"], 64), (20 + pw - 50, y + 12))
        stamps = [n for n in ICON_ORDER if n.startswith("stamp_")]
        for i, s in enumerate(stamps):
            if s in img:
                sx = 60 + (i % 3) * 190
                sy = y + 110 + (i // 3) * 170
                paste(canvas, small(img[s], 120), (sx + 20, sy))
                if "tag" in img:
                    tg = tint(nine_slice(img["tag"], SLICE["tag"], (140, 40), 0.25), (255, 230, 176))
                    paste(canvas, tg, (sx + 10, sy + 118))
                    label(d, (sx + 80, sy + 138), "3 / 5", 18, fill=INK)

    # pills (HUD) on a fake "3D world" background
    px0 = 680
    world = Image.new("RGBA", (W - px0 - 20, 440), (0, 0, 0, 0))
    wd = ImageDraw.Draw(world)
    for i in range(440):
        c = (int(120 + i * 0.12), int(190 + i * 0.05), int(250 - i * 0.2), 255)
        wd.line((0, i, world.width, i), fill=c)
    wd.rectangle((0, 300, world.width, 440), fill=(98, 178, 90, 255))
    paste(canvas, world, (px0, y + 30))
    if "pill" in img:
        pill_rows = [("coin", "1,234,567", 64), ("globe", "57", 44), ("clover", "x1.25", 44), ("star", "12", 44)]
        py = y + 50
        for ic, txt, h in pill_rows:
            pw = 280 if h == 64 else 190
            p = nine_slice(img["pill"], SLICE["pill"], (pw, h), h / 128)
            paste(canvas, p, (px0 + 40, py))
            if ic in img:
                isz = int(h * 1.25)
                paste(canvas, small(img[ic], isz), (px0 + 40 - isz // 4, py + h // 2 - isz // 2 - 2))
            label(d, (px0 + 40 + int(h * 1.1), py + h // 2), txt, int(h * 0.5), fill=(255, 255, 255), anchor="lm")
            py += h + 22
    if "sunburst" in img:
        sb = small(img["sunburst"], 300)
        sb = tint(sb, (255, 236, 150))
        paste(canvas, sb, (px0 + 380, y + 60))
        if "star" in img:
            paste(canvas, small(img["star"], 120), (px0 + 470, y + 150))
    if "news" in img and "tag" in img:
        ny = y + 400
        tg = tint(nine_slice(img["tag"], SLICE["tag"], (330, 50), 0.3), CREAM)
        paste(canvas, tg, (px0 + 40, ny))
        paste(canvas, small(img["news"], 64), (px0 + 30, ny - 8))
        tg2 = tint(nine_slice(img["tag"], SLICE["tag"], (110, 38), 0.22), CORAL)
        paste(canvas, tg2, (px0 + 100, ny + 6))
        label(d, (px0 + 155, ny + 25), "NEWS", 18, fill=(255, 255, 255))
        label(d, (px0 + 225, ny + 25), "Eiffel!  1/2,000", 17, fill=INK, anchor="lm")

    # ribbons in all colours
    y += 500
    rx = 40
    for col, dark in [(SKY, SKY_D), (GRASS, GRASS_D), (SUN, SUN_D), (CORAL, CORAL_D), (GRAPE, GRAPE_D)]:
        rb, (ox, oy) = ribbon(img, (190, 50), col, dark)
        paste(canvas, rb, (rx - ox, y + 6 - oy))
        rx += 270
    y += 90
    # checker to show translucency of the pill & raw icons on white
    if "pill" in img:
        strip = Image.new("RGBA", (W - 40, 100), (250, 250, 250, 255))
        paste(canvas, strip, (20, y))
        p = nine_slice(img["pill"], SLICE["pill"], (220, 56), 56 / 128)
        paste(canvas, p, (40, y + 22))
        label(d, (150, y + 50), "pill on white", 16, fill=(255, 255, 255))
        for i, n in enumerate(["coin", "star", "star_empty", "lock", "check", "close", "arrow_up", "dice", "clover"]):
            if n in img:
                paste(canvas, small(img[n], 56), (300 + i * 72, y + 22))
    y += 110
    canvas = canvas.crop((0, 0, W, min(H, y + 10)))
    # palette PNG keeps the contact sheet small; it is a review image, not a game asset
    rgb = canvas.convert("RGB")
    pal = rgb.quantize(256, method=Image.Quantize.MEDIANCUT)
    rgb.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).save(ROOT / "preview.png", optimize=True)


def main():
    OUT.mkdir(exist_ok=True)
    only = set(sys.argv[1:])
    total = 0
    for svg in sorted(SRC.glob("*.svg")):
        if only and svg.stem not in only:
            continue
        out, size = render(svg)
        total += size
        flag = "  <-- >100KB" if size > 100_000 else ""
        print(f"{svg.stem:16s} {size / 1024:7.1f} KB{flag}")
    images = {p.stem: Image.open(p).convert("RGBA") for p in sorted(OUT.glob("*.png"))}
    build_preview(images)
    print(f"rendered {total / 1024:.1f} KB; preview -> {ROOT / 'preview.png'}")


if __name__ == "__main__":
    main()
