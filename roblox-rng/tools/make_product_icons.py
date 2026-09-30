#!/usr/bin/env python3
"""게임패스·개발자 상품 아이콘(512x512 PNG)을 게임 그림(art/png)으로 만듭니다.

    python3 tools/make_product_icons.py        # art/products/<Id>.png + art/products/sheet.png

모양: 등급 색 동그라미 배경 + 햇살(sunburst) + 굵은 Ink 테두리 + 가운데 게임 아이콘(글자 최소).
Id 는 Config.GamePasses / Config.Products 의 Id 와 같습니다.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "png"
OUT = ROOT / "art" / "products"
S = 512
INK = (30, 27, 46, 255)


def art(name, size):
    im = Image.open(ART / f"{name}.png").convert("RGBA")
    return im.resize((size, size), Image.Resampling.LANCZOS)


def tint(im, rgb):
    r, g, b, a = im.split()
    r = r.point(lambda v: v * rgb[0] // 255)
    g = g.point(lambda v: v * rgb[1] // 255)
    b = b.point(lambda v: v * rgb[2] // 255)
    return Image.merge("RGBA", (r, g, b, a))


def font(size):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def base(top, bottom):
    """둥근 사각 배경(위→아래 그라데이션) + 햇살 + Ink 테두리."""
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line((0, y, S, y), fill=c)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((14, 14, S - 14, S - 14), 96, fill=255)
    im.paste(grad, (0, 0), mask)
    burst = tint(art("sunburst", 560), (255, 255, 255))
    burst.putalpha(burst.getchannel("A").point(lambda v: v * 55 // 100))
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    layer.alpha_composite(burst, (-24, -24))
    clipped = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    clipped.paste(layer, (0, 0), mask)
    im.alpha_composite(clipped)
    ImageDraw.Draw(im).rounded_rectangle((14, 14, S - 14, S - 14), 96, outline=INK, width=16)
    return im


def shadowed(canvas, icon, xy):
    sh = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    sh.putalpha(icon.getchannel("A").point(lambda v: v * 45 // 100))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    canvas.alpha_composite(sh, (xy[0] + 8, xy[1] + 14))
    canvas.alpha_composite(icon, xy)


def badge(canvas, text, fill, xy, size=78):
    d = ImageDraw.Draw(canvas)
    f = font(size)
    w = d.textlength(text, font=f)
    x, y = xy
    pad = 22
    box = (x - pad, y - 10, x + w + pad, y + size + 14)
    d.rounded_rectangle(box, 40, fill=fill, outline=INK, width=10)
    d.text((x, y - 4), text, font=f, fill=(255, 255, 255, 255), stroke_width=8, stroke_fill=INK)


def luck_vip():
    im = base((190, 150, 255), (110, 70, 210))
    shadowed(im, art("clover", 330), (91, 96))
    shadowed(im, art("star", 150), (320, 40))
    badge(im, "VIP", (255, 197, 61, 255), (150, 400))
    return im


def fast_roll():
    im = base((120, 200, 255), (30, 110, 210))
    d = ImageDraw.Draw(im)
    for i, y in enumerate((170, 250, 330)):
        d.rounded_rectangle((60, y, 190 - i * 20, y + 26), 13, fill=(255, 255, 255, 200))
    shadowed(im, art("dice", 300), (170, 100))
    shadowed(im, art("arrow_up", 150), (330, 300))
    return im


def double_income():
    im = base((150, 235, 140), (46, 158, 69))
    shadowed(im, art("coin", 250), (70, 90))
    shadowed(im, art("coin", 250), (180, 150))
    badge(im, "x2", (255, 94, 91, 255), (190, 390), 86)
    return im


def luck_boost():
    im = base((170, 240, 150), (60, 170, 80))
    shadowed(im, art("clover", 300), (106, 90))
    shadowed(im, art("arrow_up", 170), (310, 280))
    return im


def server_luck():
    im = base((255, 220, 120), (230, 150, 30))
    shadowed(im, art("globe", 330), (91, 70))
    shadowed(im, art("clover", 190), (290, 270))
    return im


def coin_pack():
    im = base((255, 225, 130), (225, 150, 20))
    for i, (x, y) in enumerate(((90, 210), (230, 210), (160, 90), (300, 110))):
        shadowed(im, art("coin", 190), (x, y))
    return im


ICONS = {
    "LuckVIP": luck_vip,
    "FastRoll": fast_roll,
    "DoubleIncome": double_income,
    "LuckBoost": luck_boost,
    "ServerLuck": server_luck,
    "CoinPack": coin_pack,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tiles = []
    for name, make in ICONS.items():
        im = make()
        im.save(OUT / f"{name}.png", optimize=True)
        tiles.append((name, im))
    sheet = Image.new("RGBA", (len(tiles) * 270 + 10, 300), (245, 240, 230, 255))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(tiles):
        sheet.alpha_composite(im.resize((256, 256), Image.Resampling.LANCZOS), (10 + i * 270, 8))
        d.text((10 + i * 270 + 128, 282), name, font=font(20), fill=INK, anchor="mm")
    sheet.save(OUT / "sheet.png")
    print("wrote", len(tiles), "icons ->", OUT)


if __name__ == "__main__":
    main()
