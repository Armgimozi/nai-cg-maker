#!/usr/bin/env python3
"""스토어 그림 한눈에 보기(art/store/overview.png): 아이콘(512 + 150px 실제 크기) + 썸네일 5장, 이름표 붙임.

    python3 tools/store/overview.py      # make_icon.py · thumbs.py 를 먼저 돌린 뒤

이름표도 영어·숫자만(스토어 그림에는 한글을 넣지 않음 — 점검용 그림도 같은 규칙). 숫자는 게임 코드에서 읽음.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fx  # noqa: E402
import thumbs  # noqa: E402

OUT = thumbs.OUT
BG = (243, 244, 247)
INK = (30, 27, 46)
SUB = (96, 100, 116)
FONT = "fredoka"


def labels() -> dict:
    mult, count, top = thumbs.rebirth_numbers()
    return {
        "thumb_1.png": f"1  World Tree {thumbs.odds('worldtree')} (legendary)",
        "thumb_2.png": f"2  Rebirth luck x{mult:g} each, x{top:,} after {count}",
        "thumb_3.png": f"3  Collect {len(thumbs.LANDMARKS)} landmarks (real odds)",
        "thumb_4.png": "4  Build your park (edit mode + real income)",
        "thumb_5.png": f"5  Shangri-La {thumbs.odds('shangrila')} (legendary)",
    }


def rounded(im: Image.Image, radius: int) -> Image.Image:
    m = Image.new("L", (im.width * 4, im.height * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), radius=radius * 4, fill=255)
    out = im.convert("RGBA")
    out.putalpha(m.resize(im.size, Image.Resampling.LANCZOS))
    return out


def main() -> Path:
    title_f = fx.font(FONT, 44)
    label_f = fx.font(FONT, 26)
    small_f = fx.font(FONT, 20)
    tw, th, gap, pad = 640, 360, 36, 48
    icon_px = 512
    left_w = icon_px + pad
    cols, rows = 3, 2
    W = pad + left_w + tw * cols + gap * (cols - 1) + pad
    H = pad + 70 + (th + 80) * rows + gap * (rows - 1) + pad - 10
    canvas = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(canvas)
    d.text((pad, pad - 6), "LANDMARK RNG! - store art", font=title_f, fill=INK)
    d.text((W - pad, pad + 6), "art/store - corners rounded like the Roblox store. Upload thumbnails in this order.",
           font=small_f, fill=SUB, anchor="ra")
    top = pad + 70

    # 아이콘(512) + 실제 스토어 크기(150)
    icon = Image.open(OUT / "icon.png").convert("RGB")
    canvas.alpha_composite(rounded(icon, int(icon_px * 0.18)), (pad, top + 40))
    d.text((pad, top), "Icon icon.png (512x512)", font=label_f, fill=INK)
    small = Image.open(OUT / "icon_small.png").convert("RGB")
    sy = top + 40 + icon_px + 40
    d.text((pad, sy), "150px (store list size)", font=label_f, fill=INK)
    canvas.alpha_composite(rounded(small, 27), (pad, sy + 40))
    d.text((pad + 170, sy + 60), f"{thumbs.odds('worldtree')}\n= World Tree OneIn\n(Landmarks.luau)", font=small_f,
           fill=SUB, spacing=6)

    # 썸네일 3x2(다섯 장)
    x0 = pad + left_w
    for i, (name, text) in enumerate(labels().items()):
        path = OUT / name
        if not path.exists():
            continue
        im = Image.open(path).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        x = x0 + (i % cols) * (tw + gap)
        y = top + (i // cols) * (th + 80 + gap)
        d.text((x, y), text, font=label_f, fill=INK)
        size_mb = path.stat().st_size / 1e6
        d.text((x + tw, y + 40 + th + 8), f"{name} - 1920x1080 - {size_mb:.2f} MB", font=small_f, fill=SUB, anchor="ra")
        canvas.alpha_composite(rounded(im, 14), (x, y + 40))
    path = OUT / "overview.png"
    canvas.convert("RGB").save(path, optimize=True)
    print(f"[overview] {path} ({path.stat().st_size / 1e6:.2f} MB)")
    return path


if __name__ == "__main__":
    main()
