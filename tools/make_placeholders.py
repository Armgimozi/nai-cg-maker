"""도트 캐릭터 플레이스홀더 생성기.

NAI 는 일러스트만 만들고, 게임 속 도트 스프라이트는 직접 그리는 구조다.
아직 그리지 않은 캐릭터도 게임이 바로 돌아가도록 characters.json 의 색상
(hair/outfit/accent)과 등급으로 간단한 32x48 도트 캐릭터를 절차적으로 그린다.

    python tools/make_placeholders.py            # 없는 것만 생성
    python tools/make_placeholders.py --force    # 전부 다시 생성
    python tools/make_placeholders.py --icon     # 앱 아이콘(game/icon.png)도 생성

출력: game/assets/characters/<id>.png (32x48, 투명 배경)
직접 그린 스프라이트를 같은 이름으로 덮어쓰면 그게 그대로 쓰인다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "game"
DATA = GAME / "data" / "characters.json"
OUT = GAME / "assets" / "characters"

W, H = 32, 48
SKIN_TONES = [(255, 224, 189), (241, 194, 150), (198, 134, 66), (141, 85, 36)]
OUTLINE = (24, 18, 32)
RARITY_ACCENT = {1: None, 2: (79, 195, 247), 3: (185, 139, 255),
                 4: (255, 213, 79), 5: (255, 122, 147)}


def _hex(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _shade(c: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(v * k))) for v in c)  # type: ignore[return-value]


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16))


def draw_character(ch: dict) -> Image.Image:
    rng = _rng(ch["id"])
    colors = ch.get("colors", {})
    hair = _hex(colors.get("hair", "#553322"))
    outfit = _hex(colors.get("outfit", "#556677"))
    accent = _hex(colors.get("accent", "#ddcc99"))
    skin = rng.choice(SKIN_TONES)
    rarity = int(ch.get("rarity", 1))
    is_boy = "1boy" in ch.get("prompt", "")

    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = W // 2

    def box(x0, y0, x1, y1, col, outline=True):
        d.rectangle([x0, y0, x1, y1], fill=col, outline=OUTLINE if outline else None)

    # 다리·신발
    box(cx - 5, 36, cx - 2, 44, _shade(outfit, 0.7))
    box(cx + 1, 36, cx + 4, 44, _shade(outfit, 0.7))
    box(cx - 6, 43, cx - 1, 46, _shade(accent, 0.6))
    box(cx, 43, cx + 5, 46, _shade(accent, 0.6))
    # 몸통(옷)
    box(cx - 7, 24, cx + 6, 37, outfit)
    d.rectangle([cx - 1, 26, cx, 35], fill=accent)          # 옷 무늬/벨트 줄
    # 팔
    box(cx - 10, 25, cx - 8, 34, outfit)
    box(cx + 7, 25, cx + 9, 34, outfit)
    d.rectangle([cx - 10, 33, cx - 8, 35], fill=skin)      # 손
    d.rectangle([cx + 7, 33, cx + 9, 35], fill=skin)
    # 망토(SR 이상)
    if rarity >= 3:
        cape = _shade(accent, 0.8)
        d.polygon([(cx - 9, 24), (cx + 8, 24), (cx + 10, 40), (cx - 11, 40)],
                  fill=cape, outline=OUTLINE)
        box(cx - 7, 24, cx + 6, 37, outfit)                 # 몸통 다시 위에
        d.rectangle([cx - 1, 26, cx, 35], fill=accent)
    # 어깨 장식(SSR 이상)
    if rarity >= 4:
        box(cx - 11, 23, cx - 7, 26, accent)
        box(cx + 6, 23, cx + 10, 26, accent)
    # 머리(얼굴)
    box(cx - 6, 10, cx + 5, 23, skin)
    # 머리카락 — 스타일 3종
    style = rng.choice(["short", "long", "twin"]) if not is_boy else rng.choice(["short", "messy"])
    box(cx - 7, 7, cx + 6, 13, hair)                        # 앞머리/윗머리
    d.rectangle([cx - 7, 12, cx - 6, 18], fill=hair)        # 옆머리
    d.rectangle([cx + 5, 12, cx + 6, 18], fill=hair)
    if style == "long":
        d.rectangle([cx - 8, 12, cx - 6, 30], fill=hair)
        d.rectangle([cx + 5, 12, cx + 7, 30], fill=hair)
    elif style == "twin":
        d.rectangle([cx - 11, 12, cx - 8, 26], fill=hair)
        d.rectangle([cx + 7, 12, cx + 10, 26], fill=hair)
    elif style == "messy":
        for x in range(cx - 7, cx + 7, 3):
            d.rectangle([x, 5, x + 1, 7], fill=hair)
    d.rectangle([cx - 4, 8, cx - 3, 10], fill=_shade(hair, 1.35))  # 하이라이트
    # 눈·입
    d.rectangle([cx - 4, 16, cx - 3, 18], fill=OUTLINE)
    d.rectangle([cx + 2, 16, cx + 3, 18], fill=OUTLINE)
    d.point((cx - 4, 16), fill=(255, 255, 255))
    d.point((cx + 2, 16), fill=(255, 255, 255))
    d.rectangle([cx - 1, 21, cx, 21], fill=_shade(skin, 0.7))
    # 왕관(UR)
    if rarity >= 5:
        crown = RARITY_ACCENT[5]
        d.rectangle([cx - 5, 4, cx + 4, 7], fill=(255, 208, 0), outline=OUTLINE)
        for x in (cx - 5, cx - 1, cx + 3):
            d.rectangle([x, 2, x + 1, 4], fill=(255, 208, 0))
        d.point((cx, 5), fill=crown)
    # 등급 아우라 점(R 이상): 발 옆에 반짝이
    aura = RARITY_ACCENT.get(rarity)
    if aura:
        for (x, y) in [(3, 40), (W - 4, 38), (4, 20), (W - 5, 22)][: rarity - 1]:
            d.rectangle([x, y, x + 1, y + 1], fill=aura)
    return im


def make_icon(path: Path) -> None:
    """앱 아이콘 512x512: 어두운 배경 + 등급색 테두리 + 확대한 UR 캐릭터."""
    size = 512
    bg = Image.new("RGBA", (size, size), (20, 16, 26, 255))
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([16, 16, size - 17, size - 17], radius=80, outline=(255, 122, 147), width=14)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    top = max(data["characters"], key=lambda c: int(c.get("rarity", 1)))
    sprite = draw_character(top)
    scale = 8
    big = sprite.resize((W * scale, H * scale), Image.NEAREST)
    bg.alpha_composite(big, ((size - W * scale) // 2, (size - H * scale) // 2))
    bg.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 생성")
    ap.add_argument("--icon", action="store_true", help="game/icon.png 도 생성")
    args = ap.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    made = skipped = 0
    for ch in data["characters"]:
        dst = OUT / f"{ch['id']}.png"
        if dst.exists() and not args.force:
            skipped += 1
            continue
        draw_character(ch).save(dst)
        made += 1
    print(f"도트 플레이스홀더: 생성 {made} · 건너뜀 {skipped} → {OUT}")
    if args.icon:
        make_icon(GAME / "icon.png")
        print(f"아이콘 → {GAME / 'icon.png'}")


if __name__ == "__main__":
    main()
