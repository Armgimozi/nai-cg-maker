"""UniPlay(유니티 게임 플레이어) PWA 아이콘 생성기.

어두운 배경에 청록색 게임패드 실루엣을 그려
web/unity/icons/icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png 를 만든다.
글꼴이 필요 없도록 도형만 쓴다.

    python tools/make_unity_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "web" / "unity" / "icons"

BG_TOP = (28, 33, 42)
BG_BOT = (14, 16, 20)       # app.css --bg
ACCENT = (79, 209, 197)     # --accent
INK = (14, 16, 20)
SS = 4                      # 슈퍼샘플링 배율(가장자리 매끄럽게)


def _background(size: int, rounded: bool) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        c = tuple(round(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)) + (255,)
        for x in range(size):
            px[x, y] = c
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    if rounded:
        md.rounded_rectangle([0, 0, size - 1, size - 1], radius=round(size * 0.22), fill=255)
    else:
        md.rectangle([0, 0, size, size], fill=255)
    img.paste(grad, (0, 0), mask)
    return img


def _gamepad(size: int, scale: float) -> Image.Image:
    """중앙에 게임패드. scale 은 아이콘 대비 패드 너비 비율."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = size * scale
    h = w * 0.58
    cx, cy = size / 2, size / 2 + size * 0.02
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    # 몸통 + 양쪽 손잡이
    d.rounded_rectangle([x0, y0, x1, y1], radius=h * 0.48, fill=ACCENT)
    gr = h * 0.42
    d.ellipse([x0 + w * 0.02, y1 - gr * 1.3, x0 + w * 0.02 + gr * 1.5, y1 + gr * 0.35], fill=ACCENT)
    d.ellipse([x1 - w * 0.02 - gr * 1.5, y1 - gr * 1.3, x1 - w * 0.02, y1 + gr * 0.35], fill=ACCENT)
    # 십자키
    dx, dy = x0 + w * 0.27, cy
    arm, th = h * 0.36, h * 0.13
    d.rounded_rectangle([dx - arm, dy - th, dx + arm, dy + th], radius=th * 0.5, fill=INK)
    d.rounded_rectangle([dx - th, dy - arm, dx + th, dy + arm], radius=th * 0.5, fill=INK)
    # 재생 삼각형 버튼 자리(오른쪽)
    bx, by, r = x1 - w * 0.27, cy, h * 0.3
    d.polygon([(bx - r * 0.6, by - r), (bx - r * 0.6, by + r), (bx + r * 0.95, by)], fill=INK)
    return layer


def make(name: str, size: int, *, maskable: bool) -> None:
    big = size * SS
    img = _background(big, rounded=not maskable)
    img.alpha_composite(_gamepad(big, 0.58 if maskable else 0.7))
    img = img.resize((size, size), Image.LANCZOS)
    if name == "apple-touch-icon.png":
        img = img.convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name)
    print("wrote", OUT / name)


if __name__ == "__main__":
    make("icon-192.png", 192, maskable=False)
    make("icon-512.png", 512, maskable=False)
    make("icon-maskable-512.png", 512, maskable=True)
    make("apple-touch-icon.png", 180, maskable=True)
