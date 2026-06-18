"""단부루 사전 PWA 아이콘 생성기.

브랜드 색(다크 보라 배경 + 핑크 액센트)에 '단' 글리프를 얹어
web/icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png 를 만든다.

    python tools/make_icons.py

Pillow 와 한글 폰트(맑은 고딕)가 필요하다.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WEB = Path(__file__).resolve().parent.parent / "web"

BG_TOP = (36, 26, 48)      # #241a30
BG_BOT = (20, 16, 26)      # #14101a  (style.css --bg)
ACCENT = (255, 122, 147)   # #ff7a93  (--accent)
ACCENT2 = (185, 139, 255)  # #b98bff  (--accent-2)
GLYPH = "단"

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _vgradient(size: int) -> Image.Image:
    """위→아래 세로 그라데이션 배경."""
    img = Image.new("RGB", (size, size), BG_BOT)
    px = img.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        r = round(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def _draw_glyph(img: Image.Image) -> None:
    size = img.width
    d = ImageDraw.Draw(img)
    font = _font(round(size * 0.58))
    # 중앙 정렬(글리프 실제 bbox 기준)
    l, t, r, b = d.textbbox((0, 0), GLYPH, font=font)
    x = (size - (r - l)) / 2 - l
    y = (size - (b - t)) / 2 - t
    # 살짝 그림자 → 액센트 글리프
    d.text((x, y + size * 0.012), GLYPH, font=font, fill=(0, 0, 0))
    d.text((x, y), GLYPH, font=font, fill=ACCENT)


def _rounded_frame(img: Image.Image) -> None:
    """'any' 아이콘용 액센트 라운드 사각 테두리(마스커블엔 안 씀 — 잘릴 수 있음)."""
    size = img.width
    d = ImageDraw.Draw(img)
    inset = round(size * 0.10)
    rad = round(size * 0.22)
    w = max(2, round(size / 64))
    d.rounded_rectangle([inset, inset, size - inset, size - inset],
                        radius=rad, outline=ACCENT2, width=w)


def make(name: str, size: int, *, frame: bool) -> None:
    img = _vgradient(size)
    if frame:
        _rounded_frame(img)
    _draw_glyph(img)
    out = WEB / name
    img.save(out, "PNG")
    print(f"  {out.name}  ({size}x{size})")


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    print("아이콘 생성:")
    make("icon-192.png", 192, frame=True)
    make("icon-512.png", 512, frame=True)
    make("icon-maskable-512.png", 512, frame=False)  # 안전영역 — 테두리 없이
    make("apple-touch-icon.png", 180, frame=True)
    print("완료.")


if __name__ == "__main__":
    main()
