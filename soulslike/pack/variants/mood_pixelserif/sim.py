"""
픽셀 명조 글줄 미리보기 (클라이언트 없이 글자 모양을 고를 때). 클라이언트 unihex 규칙을 그대로 흉내 낸다:
진행 폭 = 잉크 폭 // 2 + 1 (GUI), 그림자 = 글 색 × 0.25 를 GUI 0.5 (그림 한 칸) 오른쪽 아래, 빈칸은 SPACE GUI 픽셀.
GUI 배율 k 면 그림 한 칸이 화면 k/2 픽셀 (k=3 이면 1.5: 가장 가까운 픽셀로 늘려 실제처럼 고르지 않다).

  python3 sim.py <out.png> [GUI배율]
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import serif  # noqa: E402

SPACE = 3


def line(face, text, color=(214, 203, 176), shadow=True, space=SPACE):
    """글 한 줄 → 그림 한 칸 단위 RGBA (높이 CELL+1)."""
    parts, x = [], 0
    for ch in text:
        if ch == " ":
            x += 2 * space
            continue
        g = face.glyph(ch)
        if g is None:
            x += 2 * 5
            continue
        parts.append((x, g))
        x += 2 * serif.advance(g)
    im = Image.new("RGBA", (max(x, 1) + 1, serif.CELL + 1), (0, 0, 0, 0))
    sc = tuple(int(v * 0.25) for v in color)
    for layer, (dx, col) in enumerate(((1, sc), (0, color))):
        if layer == 0 and not shadow:
            continue
        for px, g in parts:
            solid = Image.new("RGBA", g.size, col + (255,))
            im.paste(solid, (px + dx, dx), g)
    return im


def page(rows, gui, bg=(20, 18, 16), width=None, pad=8):
    """[(face, 글, 색)] → GUI 배율 gui 의 화면 그림. 줄 사이 10 GUI 픽셀 (설명 칸)."""
    lines = [line(f, t, c) for f, t, c in rows]
    W = width or max(l.width for l in lines) + 2 * pad
    H = 20 * len(rows) + 2 * pad
    canvas = Image.new("RGBA", (W, H), bg + (255,))
    for i, l in enumerate(lines):
        canvas.alpha_composite(l, (pad, pad + 20 * i))
    k = gui / 2
    return canvas.resize((int(W * k), int(H * k)), Image.NEAREST)


def demo(out, gui=4):
    body, title = serif.body_face(), serif.title_face()
    bone, gold, gray, lore = (214, 203, 176), (209, 195, 160), (133, 128, 121), (143, 129, 100)
    rows = [
        (title, "레딘 경비대 직검", gold),
        (body, "직검 · 베기/찌르기", gray),
        (body, "공격력 62   근력 C   기량 D", gray),
        (body, "필요 근력 10 · 기량 10   무게 3.0", gray),
        (body, "레딘 경비대가 차던 곧은 칼.", lore),
        (body, "성벽 위의 병사들은 모두 안쪽을 보고 섰다.", lore),
        (title, "Redin Watch Straight Sword", gold),
        (body, "Straight Sword · Slash/Thrust", gray),
        (body, "Attack 62   Str C   Dex D   Weight 3.5", gray),
        (body, "Every man on the wall stood facing inward.", lore),
        (body, "None recorded where their blades pointed.", lore),
        (body, "게임으로   설정...   일어선다   그만둔다", bone),
        (body, "Back to Game   Options...   Respawn   Title Screen", bone),
        (title, "게임 메뉴   탑옥 아래   제작", gold),
        (title, "Game Menu   Beneath the Tower   Crafting", gold),
    ]
    page(rows, gui).save(out)


def compare(out, gui=4):
    """제목 한글 굵기 견주기."""
    rows = []
    for name in ("NanumMyeongjo-Regular.ttf", "NanumMyeongjo-Bold.ttf", "NanumMyeongjo-ExtraBold.ttf"):
        f = serif.Face(hangul=serif.load(name, 16))
        rows.append((f, "레딘 경비대 직검   볼크 가의 장검   탑옥 아래", (209, 195, 160)))
        rows.append((f, "게임 메뉴   제작   보관함   화톳불   쉰다", (209, 195, 160)))
    page(rows, gui).save(out)


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "compare":
        compare(sys.argv[1], int(sys.argv[2]))
    else:
        demo(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
