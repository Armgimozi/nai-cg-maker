#!/usr/bin/env python3
"""스토어 그림 한눈에 보기(art/store/overview.png): 아이콘(512 + 150px 실제 크기) + 썸네일 4장, 이름표 붙임.

    python3 tools/store/overview.py      # make_icon.py · thumbs.py 를 먼저 돌린 뒤
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

LABELS = {
    "thumb_1.png": f"썸네일 1 — 세계수 {thumbs.odds('worldtree')} (전설)",
    "thumb_2.png": f"썸네일 2 — 샹그릴라 {thumbs.odds('shangrila')} (전설)",
    "thumb_3.png": "썸네일 3 — 150개 명소를 모아라 (실제 확률)",
    "thumb_4.png": "썸네일 4 — 나만의 관광 공원 (3D 배치 모드 + 수입)",
}


def rounded(im: Image.Image, radius: int) -> Image.Image:
    m = Image.new("L", (im.width * 4, im.height * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), radius=radius * 4, fill=255)
    out = im.convert("RGBA")
    out.putalpha(m.resize(im.size, Image.Resampling.LANCZOS))
    return out


def main() -> Path:
    kr = thumbs.font_path(thumbs.KR)
    title_f = fx.font(kr, 44)
    label_f = fx.font(kr, 26)
    small_f = fx.font(kr, 20)
    tw, th, gap, pad = 800, 450, 36, 48
    icon_px = 512
    left_w = icon_px + pad
    W = pad + left_w + tw * 2 + gap + pad
    H = pad + 70 + (th + 80) * 2 + gap + pad - 10
    canvas = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(canvas)
    d.text((pad, pad - 6), "LANDMARK RNG! — 스토어 그림", font=title_f, fill=INK)
    d.text((W - pad, pad + 6), "art/store · Roblox 스토어처럼 모서리를 둥글게 잘라 봄", font=small_f, fill=SUB, anchor="ra")
    top = pad + 70

    # 아이콘(512) + 실제 스토어 크기(150)
    icon = Image.open(OUT / "icon.png").convert("RGB")
    canvas.alpha_composite(rounded(icon, int(icon_px * 0.18)), (pad, top + 40))
    d.text((pad, top), "아이콘 icon.png (512×512)", font=label_f, fill=INK)
    small = Image.open(OUT / "icon_small.png").convert("RGB")
    sy = top + 40 + icon_px + 40
    d.text((pad, sy), "150px (스토어 목록 크기)", font=label_f, fill=INK)
    canvas.alpha_composite(rounded(small, 27), (pad, sy + 40))
    d.text((pad + 170, sy + 60), f"숫자 {thumbs.odds('worldtree')}\n= Landmarks.luau 세계수 OneIn", font=small_f,
           fill=SUB, spacing=6)

    # 썸네일 2x2
    x0 = pad + left_w
    for i, name in enumerate(["thumb_1.png", "thumb_2.png", "thumb_3.png", "thumb_4.png"]):
        im = Image.open(OUT / name).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        x = x0 + (i % 2) * (tw + gap)
        y = top + (i // 2) * (th + 80 + gap)
        d.text((x, y), LABELS[name], font=label_f, fill=INK)
        size_mb = (OUT / name).stat().st_size / 1e6
        d.text((x + tw, y + 40 + th + 8), f"{name} · 1920×1080 · {size_mb:.2f} MB", font=small_f, fill=SUB, anchor="ra")
        canvas.alpha_composite(rounded(im, 16), (x, y + 40))
    path = OUT / "overview.png"
    canvas.convert("RGB").save(path, optimize=True)
    print(f"[overview] {path} ({path.stat().st_size / 1e6:.2f} MB)")
    return path


if __name__ == "__main__":
    main()
