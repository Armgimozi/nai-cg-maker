"""0.3.6.1 보석 광석 블록 (16×16) — 주인 결정: "삐쭉 튀어나온 부분이 별로임 그냥 광석 블록 텍스쳐를 네모난걸 새로 만드는게 나을듯".

보석 노드는 튀어나온 결정(ItemDisplay) 없이 네모난 블록 하나다. 팩은 그 블록(바닐라 좀벌레 돌 6개, 계약 visual.json blocks.gems)의
blockstates 만 바꿔 labyrinth:block/mine/gem_<보석> (cube_all) 을 보이게 한다. 그림은 바닐라 광석처럼 그린다:
광산 벽 돌 바탕(stone · tuff · deepslate · basalt) 위에 보석 색 알갱이·조각 4~6 무더기, 무더기마다 어두운 테 · 몸 · 밝은 빛.
바탕은 가장자리가 이어지게(16칸 주기) 그려서 블록이 붙어도 이음매가 없다. 모든 점은 이 파일이 찍는다 (바닐라 그림을 읽지 않음).
"""
from __future__ import annotations

import math
import random

from PIL import Image

from .util import hex2rgb, mix, stable_seed

SIZE = 16

# 바탕 돌: 어두운 → 밝은 5단 (광산 벽 블록과 비슷한 밝기) + 무늬 결.
# 밝기·대비는 바닐라 벽 블록(돌 · 응회암 · 심층암 · 현무암 옆면)의 평균 밝기·흩어짐에 맞춘 값이다 — 0.3.6.1 검증에서 바탕이 벽보다
# 8~20 어두워 보석 노드가 벽 속 어두운 네모로 보였다 (바닐라 그림은 읽지 않고 숫자만 맞춤).
BASES = {
    'stone': {'ramp': ['#646464', '#737373', '#808080', '#8c8c8c', '#999999'], 'grain': 'blotch'},
    'tuff': {'ramp': ['#42433f', '#585b53', '#6e7168', '#82877c', '#9ca094'], 'grain': 'speck'},
    'deepslate': {'ramp': ['#26262b', '#393940', '#4c4c53', '#5e5e67', '#75757d'], 'grain': 'layer'},
    'basalt': {'ramp': ['#242426', '#36363c', '#484850', '#5c5c63', '#72727d'], 'grain': 'streak'},
}


def _pnoise(rnd: random.Random, gx: int, gy: int):
    """주기 noise: 16 칸을 gx × gy 격자로 — 가장자리가 이어진다. → f(x, y) ∈ [0, 1)."""
    lat = [[rnd.random() for _ in range(gy)] for _ in range(gx)]
    cx, cy = SIZE / gx, SIZE / gy

    def f(x, y):
        fx, fy = x / cx, y / cy
        x0, y0 = int(math.floor(fx)), int(math.floor(fy))
        tx, ty = fx - x0, fy - y0
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = lat[x0 % gx][y0 % gy]
        b = lat[(x0 + 1) % gx][y0 % gy]
        c = lat[x0 % gx][(y0 + 1) % gy]
        d = lat[(x0 + 1) % gx][(y0 + 1) % gy]
        return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty
    return f


def base_stone(kind: str, seed: int) -> Image.Image:
    """광산 벽 돌 바탕 16×16 (이음매 없음)."""
    spec = BASES[kind]
    ramp = [hex2rgb(c) for c in spec['ramp']]
    rnd = random.Random(seed)
    grain = spec['grain']
    if grain == 'layer':        # 심층암: 가로 결
        n1, n2 = _pnoise(rnd, 2, 8), _pnoise(rnd, 4, 16)
    elif grain == 'streak':     # 현무암: 세로 결
        n1, n2 = _pnoise(rnd, 8, 2), _pnoise(rnd, 16, 4)
    else:                       # 돌·응회암: 얼룩
        n1, n2 = _pnoise(rnd, 4, 4), _pnoise(rnd, 8, 8)
    img = Image.new('RGBA', (SIZE, SIZE))
    px = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            v = 0.62 * n1(x, y) + 0.28 * n2(x, y) + 0.10 * rnd.random()
            k = min(4, max(0, int(v * 5.2 - 0.3)))
            px[x, y] = ramp[k] + (255,)
    # 잔 점 (돌 = 어두운 점 · 응회암 = 밝고 어두운 점이 많음 · 심층암·현무암 = 결 따라 짧은 어두운 줄)
    dots = {'blotch': 10, 'speck': 22, 'layer': 8, 'streak': 8}[grain]
    for _ in range(dots):
        x, y = rnd.randrange(SIZE), rnd.randrange(SIZE)
        if grain == 'speck' and rnd.random() < 0.45:
            px[x, y] = ramp[4] + (255,)
        else:
            px[x, y] = ramp[0] + (255,)
        if grain == 'layer':
            px[(x + 1) % SIZE, y] = ramp[0] + (255,)
        elif grain == 'streak':
            px[x, (y + 1) % SIZE] = ramp[0] + (255,)
    return img


# 무더기 모양 (글자 그림): 0 테(그림자) · 1 몸 어두운 쪽 · 2 몸 · 3 빛 · '.' 빈칸. 큰 것 · 중간 · 작은 것.
_SHAPE_ART = {
    'grain': [   # 석류석: 둥근 알
        ['.32.', '3221', '2210', '.10.'],
        ['32.', '221', '.10'],
        ['31', '10'],
    ],
    'cabochon': [   # 월장석: 젖빛 둥근 알 (가운데 밝음)
        ['.121.', '13321', '12210', '.110.'],
        ['.21', '231', '110'],
        ['31', '10'],
    ],
    'shard': [   # 석영·황옥: 비스듬한 굵은 조각 (끝이 밝음)
        ['..33', '.320', '3210', '20..'],
        ['.3', '32', '20'],
        ['33.', '.20', '..0'],
    ],
    'hex': [   # 청옥: 육각 결정 (가운데 빛)
        ['.22.', '2331', '2311', '.10.'],
        ['.2.', '231', '.10'],
        ['31', '10'],
    ],
}
SHAPES = {k: [[(x, y, int(ch)) for y, row in enumerate(art) for x, ch in enumerate(row) if ch != '.'] for art in arts]
          for k, arts in _SHAPE_ART.items()}


def _clusters(rnd: random.Random, n: int, margin=1, min_dist=4.6):
    """무더기 자리 n 개 (서로 떨어지게, 가장자리 margin 안)."""
    pts = []
    tries = 0
    while len(pts) < n and tries < 2000:
        tries += 1
        x, y = rnd.randint(margin, SIZE - 4 - margin), rnd.randint(margin, SIZE - 4 - margin)
        if all((x - a) ** 2 + (y - b) ** 2 >= min_dist ** 2 for a, b in pts):
            pts.append((x, y))
    return pts


def _veins(img, rnd, ramp):
    """용혈석: 현무암 바탕에 붉게 타는 갈라진 결 (짧은 걸음 3줄) + 작은 덩이 3개."""
    px = img.load()
    hot = set()
    for _ in range(3):
        x, y = rnd.randint(2, 13), rnd.randint(2, 13)
        dx = rnd.choice((-1, 1))
        for step in range(rnd.randint(5, 7)):
            if 1 <= x <= 14 and 1 <= y <= 14:
                hot.add((x, y))
            y += 1 if rnd.random() < 0.6 else 0
            x += dx if rnd.random() < 0.7 else 0
    for (x, y) in hot:                       # 결 둘레 그을음
        for ax, ay in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            q = (x + ax, y + ay)
            if q not in hot and 0 <= q[0] < SIZE and 0 <= q[1] < SIZE:
                px[q] = ramp[0] + (255,)
    for (x, y) in hot:
        px[x, y] = ramp[1] + (255,)
    core = rnd.sample(sorted(hot), max(3, len(hot) // 3))
    for (x, y) in core:
        px[x, y] = ramp[2] + (255,)
    for (x, y) in core[: max(2, len(core) // 3)]:
        px[x, y] = ramp[3] + (255,)
    for (cx, cy) in _clusters(rnd, 3, margin=2, min_dist=4.0):
        for (dx, dy, role) in SHAPES['grain'][2]:  # noqa: B007
            if (cx + dx, cy + dy) not in hot:
                px[cx + dx, cy + dy] = ramp[(3, 2, 1, 0)[3 - role]] + (255,)
    return img


def gem_texture(gem: str, look: dict) -> Image.Image:
    """보석 광석 블록 그림 16×16 — look = visual.json blocks.gems.<보석>.look {base, style, palette[4]}."""
    seed = stable_seed('mine_gem_block', gem)
    img = base_stone(look.get('base') or 'stone', seed)
    pal = [hex2rgb(c) for c in look['palette']]
    rnd = random.Random(seed ^ 0x5bd1e995)
    style = look.get('style') or 'grain'
    if style == 'vein':
        return _veins(img, rnd, pal)
    px = img.load()
    shapes = SHAPES[style]
    pts = _clusters(rnd, 6, min_dist=4.2)
    for i, (cx, cy) in enumerate(pts):
        shape = shapes[0] if i < 2 else shapes[1] if i < 4 else shapes[2]
        flip = rnd.random() < 0.5 and style in ('shard', 'grain')
        w = max(dx for dx, _, _ in shape)
        for (dx, dy, role) in shape:
            x = cx + (w - dx if flip else dx)
            y = cy + dy
            if not (0 <= x < SIZE and 0 <= y < SIZE):
                continue
            if role == 0:                          # 테 = 보석 어두운 색과 바탕을 섞음 (바닐라 광석의 그림자 테)
                bg = px[x, y][:3]
                px[x, y] = mix(pal[0], bg, 0.35) + (255,)
            else:
                px[x, y] = pal[role] + (255,)
    return img


def blockstate(block: str, model: str) -> dict:
    """바닐라 블록의 blockstates 를 팩 모델 하나로 (축 있는 심층암도 모든 축 → 같은 모델, 돌리지 않음)."""
    if block.endswith('deepslate'):
        return {'variants': {f'axis={a}': {'model': model} for a in ('x', 'y', 'z')}}
    return {'variants': {'': {'model': model}}}


def cube_model(texture: str) -> dict:
    return {'parent': 'minecraft:block/cube_all', 'textures': {'all': texture}}


def iso_cube(tex: Image.Image, px=64) -> Image.Image:
    """미리보기용 등각 정육면체 (윗면 + 두 옆면, 옆면은 조금 어둡게)."""
    t = tex.convert('RGBA').resize((px, px), Image.NEAREST)
    w = px * 2
    out = Image.new('RGBA', (w, int(px * 2.0)), (0, 0, 0, 0))
    top = t.rotate(45, expand=True, resample=Image.NEAREST)
    top = top.resize((w, w // 2), Image.NEAREST)
    out.alpha_composite(top, (0, 0))

    # 왼쪽 옆면: 아래로 비스듬히 (x 가 늘면 y 도 늘어남)
    lw = Image.new('RGBA', (px, int(px * 1.5)), (0, 0, 0, 0))
    rw = Image.new('RGBA', (px, int(px * 1.5)), (0, 0, 0, 0))
    lp, rp, src = lw.load(), rw.load(), t.load()
    for y in range(px):
        for x in range(px):
            c = src[x, y]
            lp[x, y + x // 2] = (int(c[0] * 0.78), int(c[1] * 0.78), int(c[2] * 0.78), 255)
            rp[x, y + (px - 1 - x) // 2] = (int(c[0] * 0.62), int(c[1] * 0.62), int(c[2] * 0.62), 255)
    out.alpha_composite(lw, (0, px // 2 - 1))
    out.alpha_composite(rw, (px, px // 2 - 1))
    return out
