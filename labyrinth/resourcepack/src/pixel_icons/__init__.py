"""16×16 손그림 아이콘 (0.3.6.2, 주인 결정 C "지금 모양 다듬기") — 평면 2D 아이템 아이콘 전부를 한 벌로.

옛 길(src/icons.py)은 32×32 SDF 그림이라 GUI 에서 반 픽셀로 보여 "다른 게임"처럼 보였다. 여기서는 아이템마다
지금의 정체성(모양)은 남기고, 그림만 바닐라 그림 규칙으로 다시 그린다. 모든 픽셀은 이 패키지의 코드·지도에서 나온다
(바닐라 그림은 열지도, 따라 그리지도, 색만 바꾸지도 않는다).

그림 규칙 (C 시안 gen.py R1~R7 을 옮김)
  R1  16×16, 한 칸 = 한 픽셀. 반투명·안티에일리어싱·그라데이션 없음 (알파는 0 아니면 255).
  R2  색은 램프(어두움 → 밝음 6칸)에서만 고른다. 아이콘 하나에 6~16색.
  R3  램프는 색조를 민다: 그림자는 차갑게(파랑·보라 쪽), 밝은 쪽은 따뜻하게(노랑 쪽), 채도는 가운데가 가장 높다 → ramp().
  R4  빛은 왼쪽 위. 테두리 = 위·왼쪽은 램프 2번, 아래·오른쪽은 램프 0번. 검은 외곽선 없음 — 테두리도 그 물체 자기 색 → edge().
  R5  면은 평평한 덩어리, 밝은 모서리에만 1픽셀 하이라이트(램프 5번) → highlight(). 무작위 점 없음 (일부러 놓은 2~4픽셀 덩이만).
      몸통에서 떨어진 덩이·반짝이 없음 (DETACHED_OK 로만 허용), 순백 4칸 이하, 칸 회색과 같은 무채색 몸통 10% 이하(경고).
      UI 기호(화살표·+·하트 기호·방패 그림)를 물건에 그려 넣지 않는다 — 물건으로 보이게.
  R6  같은 틀은 한 집안 안에서만 (주괴 6 · 같은 크기 물약 · 두루마리 · 깃털 — FAMILY). 다른 종류끼리 실루엣이 같으면 경고.
      단계는 색과 크기로 갈린다.
  R7  지금 아이콘의 정체성은 그대로 두고 그림 규칙만 바꾼다.

픽셀 지도 문법 (paint): 한 줄 16글자, 16줄. '.' 또는 ' ' = 비움 (덧칠 지도에서는 '그대로 둠').
  0~5 → main 램프 칸,  a~f → acc 0~5,  A~F → acc2 0~5,  p~u → acc3 0~5,  'w' → 순백 반짝임 #ffffff,
  'x' → 지우기(투명으로 되돌림, 덧칠 지도에서 실루엣을 깎을 때). legend={'g': (r,g,b) | ('acc', 3)} 로 글자를 더할 수 있다.
  지도는 첫 지도 위에 다음 지도를 차례로 덮는다.

등록 (그룹 모듈 mine.py · organic.py · arcane.py · crafted.py · consumable.py 가 채운다)
    from . import register, paint, Ctx
    @register('copper_ore')            # 아이템 id — 그 아이템만
    def _(ctx: Ctx): return paint(ctx.slots(main='stone_cu', acc='copper'), ROCK, VEINS)
    @register('potion_small')          # 그림 style — 그 style 을 쓰는 아이템 전부 (팔레트로 색이 갈림)
    def _(ctx): return paint({'main': ctx.glass, 'acc': ctx.acc}, FLASK)
  찾는 순서: 아이템 id → style. 둘 다 없으면 None → items.py 가 옛 32px 그림으로 (팩은 언제나 빌드된다).
  그림 함수는 16×16 RGBA Image 또는 Art(img, layers=[...], frames=[...]) 를 돌려준다.
    layers: layer1 이후 (도안 blueprint 의 봉인 = 회색 그림, 플러그인이 희귀도 색으로 tint)
    frames: layer0 의 애니메이션 프레임 (없으면 정지 그림)
"""
from __future__ import annotations

import colorsys
import importlib
from dataclasses import dataclass, field
from typing import Callable

from PIL import Image

SIZE = 16
MIN_COLOURS, MAX_COLOURS = 6, 16
MAX_ISOLATED = 2          # 일부러 놓은 한 점 반짝임 허용 수 (그 이상 = speckle)
MAX_WHITE = 4             # 순백(#ffffff) 칸 수 상한 (0.3.6.2 심사: 순백이 많으면 반들거리는 플라스틱처럼 보인다)
# 몸통에서 떨어진 덩이(8방향으로 이어지지 않은 조각): 기본 0개. 일부러 떨어뜨린 것(흩날리는 가루 등)만 아이템 id 로 허용한다
# (0.3.6.2 심사: 물체 밖에 떠 있는 "+" 반짝이·점이 바닐라 재료와 어긋났다).
DETACHED_OK: dict[str, int] = {}
# 칸 색(#8b8b8b, 밝기 139)과 같은 밝기의 무채색: 밝기 ±14 · 채도 0.18 미만인 칸이 몸통의 10% 를 넘으면 경고 (1배에서 칸 속으로 사라짐)
SLOT_GREY_LUM, SLOT_GREY_TOL, SLOT_GREY_SAT, SLOT_GREY_MAX = 139, 14, 0.18, 0.10
# 다른 종류끼리 실루엣이 같으면 경고: 모양 겹침(IoU) ≥ 0.85 이고 테두리 겹침(Dice) ≥ 0.75. 같은 틀을 같이 쓰는 집안은 FAMILY 로 묶는다
# (style 로 등록한 그림은 그 style 이 집안 — 물약 크기 셋 · 두루마리).
SHAPE_IOU, SHAPE_OUTLINE = 0.85, 0.75
FAMILY: dict[str, str] = {
    **{i: 'ingot' for i in ('copper_ingot', 'iron_ingot', 'silver_ingot', 'gold_ingot', 'mithril_ingot', 'orichalcum_ingot')},
    **{i: 'feather' for i in ('librarian_quill', 'phoenix_feather')},
}
GROUPS = ('mine', 'organic', 'arcane', 'crafted', 'consumable')
# True (0.3.6.2 통합 — 평면 아이콘 83개 모두 16px): validate.py 가 옛 32px 로 떨어진 평면 아이콘을 오류로 본다 (False 면 경고).
REQUIRE_ALL_16 = True

WHITE = (255, 255, 255)
RGB = tuple


# ───────────────────────────── 색 ─────────────────────────────

def hx(c) -> RGB:
    """'#rrggbb' | (r,g,b) → (r,g,b)."""
    if isinstance(c, (tuple, list)):
        return tuple(int(v) for v in c[:3])
    c = c.strip().lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(c) -> str:
    return '#%02x%02x%02x' % tuple(c[:3])


def lum(c) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def _toward(h, target, amount):
    """색조 h(도) 를 target 쪽으로 가까운 길로 amount 도 만큼 (넘지 않게)."""
    d = ((target - h + 180.0) % 360.0) - 180.0
    step = max(-amount, min(amount, d))
    return (h + step) % 360.0


COOL_HUE = 245.0   # 그림자 쪽 (파랑·보라)
WARM_HUE = 55.0    # 밝은 쪽 (노랑)


def ramp(base, n=6, at=3, dark=0.2, light=0.97, cool=26.0, warm=16.0, sat_dark=1.08, sat_light=0.42,
         min_tint=0.10) -> list[RGB]:
    """밑색 하나 → n칸 램프 (어두움 → 밝음, R3). base 는 at 번 칸에 그대로 놓인다.

    어두운 쪽: 명도(HSV V)를 dark 까지 내리고 색조를 COOL_HUE 쪽으로 최대 cool 도, 채도 × sat_dark.
    밝은 쪽: 명도를 light 까지 올리고 채도를 × sat_light 까지 줄이며 색조를 WARM_HUE 쪽으로 최대 warm 도.
    회색(채도 낮음)도 끝 칸에는 min_tint 만큼 색을 준다 (차가운 그림자·따뜻한 빛)."""
    r, g, b = hx(base)
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h *= 360.0
    out = []
    for k in range(n):
        if k < at:
            t = (at - k) / at
            vv = v + (min(dark, v) - v) * t
            hh = _toward(h, COOL_HUE, cool * t) if s >= 0.06 else COOL_HUE
            ss = min(1.0, s * (1 + (sat_dark - 1) * t))
            ss = max(ss, min_tint * t)
        elif k > at:
            t = (k - at) / (n - 1 - at)
            vv = v + (max(light, v) - v) * t
            hh = _toward(h, WARM_HUE, warm * t) if s >= 0.06 else WARM_HUE
            ss = s * (1 - (1 - sat_light) * t)
            if s < 0.06:
                ss = max(ss, min_tint * 0.6 * t)
        else:
            out.append((r, g, b))
            continue
        rr, gg, bb = colorsys.hsv_to_rgb(hh / 360.0, max(0.0, min(1.0, ss)), max(0.0, min(1.0, vv)))
        out.append((round(rr * 255), round(gg * 255), round(bb * 255)))
    return out


# 여러 그룹이 같이 쓰는 고정 램프 (C 시안에서 옮김). 그룹 전용 램프는 그 모듈에 둔다.
RAMPS: dict[str, list[str]] = {
    'wood':    ['#2c1a10', '#4a2e18', '#6c4626', '#8e6236', '#ae8048', '#c89e60'],
    'dwood':   ['#1a0e0c', '#2e1a14', '#46281c', '#603826', '#7a4c32', '#946240'],
    'leather': ['#1e0e0a', '#341a10', '#4e2a18', '#6a3c22', '#86522e', '#a06a3e'],
    'steel_h': ['#1e2230', '#323a4a', '#4c5668', '#6a7688', '#8c98a8', '#b4bec8'],
    'glass':   ['#283a52', '#45607e', '#6f8ea8', '#a3c0d2', '#d4e6ee', '#f6fcff'],
    'parchment': ['#4a3020', '#7a5636', '#a88458', '#cfb07e', '#e8d4a6', '#f8ecd0'],
    'bone':    ['#3c2c1c', '#6a5238', '#9c8462', '#c6b28a', '#e4d6b0', '#f8f0d8'],
    'gold':    ['#5e2c08', '#985210', '#cf8a14', '#f0b828', '#fdde52', '#fff5a6'],
    'patina':  ['#123a3a', '#1c5e54', '#2b8670', '#45ab8a', '#72cfa8', '#a8ecd0'],
    'ember':   ['#6a1208', '#b03010', '#e85c18', '#ff8e2c', '#ffc65c', '#fff0b4'],
}


def named_ramp(r) -> list[RGB]:
    """램프 이름 (RAMPS 또는 모듈이 add_ramps 로 더한 것) | 색 6개 목록 | 밑색 하나('#hex' → ramp())."""
    if isinstance(r, str):
        if r in RAMPS:
            return [hx(c) for c in RAMPS[r]]
        if r.startswith('#'):
            return ramp(r)
        raise KeyError(f'unknown ramp {r!r}')
    if isinstance(r, (list, tuple)) and r and isinstance(r[0], (str, list, tuple)):
        return [hx(c) for c in r]
    return ramp(r)


def add_ramps(d: dict):
    """그룹 모듈이 자기 램프를 이름으로 등록 (이름이 겹치면 오류 — 그룹마다 앞에 붙이기 권장)."""
    for k, v in d.items():
        if k in RAMPS and RAMPS[k] != v:
            raise KeyError(f'ramp {k!r} already defined differently')
        assert len(v) == 6, (k, len(v))
        RAMPS[k] = list(v)


# ───────────────────────────── 지도 → 그림 ─────────────────────────────

E = '.' * SIZE
SLOT_KEYS = (('012345', 'main'), ('abcdef', 'acc'), ('ABCDEF', 'acc2'), ('pqrstu', 'acc3'))


def blank() -> Image.Image:
    return Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))


def _lookup(ch, slots, legend):
    if legend and ch in legend:
        v = legend[ch]
        if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str):
            return named_ramp(slots[v[0]] if v[0] in slots else v[0])[v[1]]
        return hx(v)
    if ch == 'w':
        return WHITE
    for keys, slot in SLOT_KEYS:
        if ch in keys:
            r = slots.get(slot)
            if r is None:
                raise KeyError(f'{slot} ramp missing for {ch!r}')
            return named_ramp(r)[keys.index(ch)]
    raise KeyError(f'unknown map char {ch!r}')


def paint(slots: dict, *maps, legend: dict | None = None, img: Image.Image | None = None) -> Image.Image:
    """slots = {'main': 램프, 'acc': …, 'acc2': …, 'acc3': …} (램프 = 이름 | 색 6개 | 밑색) + 지도들 → 16×16 RGBA."""
    out = img.copy() if img is not None else blank()
    px = out.load()
    for m in maps:
        if len(m) != SIZE:
            raise ValueError(f'map has {len(m)} rows (want {SIZE})')
        for y, row in enumerate(m):
            if len(row) != SIZE:
                raise ValueError(f'map row {y} has {len(row)} chars: {row!r}')
            for x, ch in enumerate(row):
                if ch in '. ':
                    continue
                if ch == 'x':
                    px[x, y] = (0, 0, 0, 0)
                    continue
                px[x, y] = _lookup(ch, slots, legend) + (255,)
    return out


def rows(text: str) -> list[str]:
    """여러 줄 문자열 → 지도 (빈 줄·앞뒤 공백 줄 무시, 16줄 미만이면 아래를 비움)."""
    out = [ln.rstrip('\n') for ln in text.strip('\n').split('\n')]
    out = [ln.strip() for ln in out]
    out = [ln.ljust(SIZE, '.') for ln in out]
    while len(out) < SIZE:
        out.append(E)
    return out


def shift(m: list[str], dx=0, dy=0) -> list[str]:
    """지도 옮기기 (밖으로 나간 칸은 버림)."""
    out = [E] * SIZE
    for y in range(SIZE):
        sy = y - dy
        if 0 <= sy < SIZE:
            row = m[sy]
            out[y] = ''.join(row[x - dx] if 0 <= x - dx < SIZE else '.' for x in range(SIZE))
    return out


def mirror(m: list[str]) -> list[str]:
    return [row[::-1] for row in m]


# ───────────────────────────── 규칙 도우미 (R4·R5·R6) ─────────────────────────────

def mask_of(img) -> list[list[bool]]:
    px = img.load()
    return [[px[x, y][3] >= 128 for x in range(SIZE)] for y in range(SIZE)]


def _find(c, ramps):
    for r in ramps:
        rr = named_ramp(r)
        if c in rr:
            return rr, rr.index(c)
    return None, None


def edge(img, ramps, lit=2, shade=0, only=None) -> Image.Image:
    """R4: 실루엣 테두리를 그 물체 자기 램프의 lit(위·왼쪽이 열림) / shade(아래·오른쪽만 열림) 칸으로.
    ramps = 그림에 쓴 램프들 (픽셀 색이 어느 램프인지 찾는다). only=(x,y)→bool 로 범위를 줄일 수 있다."""
    out = img.copy()
    src, dst = img.load(), out.load()
    m = mask_of(img)
    for y in range(SIZE):
        for x in range(SIZE):
            if not m[y][x] or (only and not only(x, y)):
                continue
            up = y == 0 or not m[y - 1][x]
            left = x == 0 or not m[y][x - 1]
            down = y == SIZE - 1 or not m[y + 1][x]
            right = x == SIZE - 1 or not m[y][x + 1]
            if not (up or left or down or right):
                continue
            rr, _ = _find(src[x, y][:3], ramps)
            if rr is None:
                continue
            dst[x, y] = rr[lit if (up or left) else shade] + (255,)
    return out


def highlight(img, ramps, idx=5, length=None) -> Image.Image:
    """R5: 위·왼쪽 테두리 바로 안쪽 한 줄에 1픽셀 하이라이트 (램프 idx 칸). length 로 줄 길이를 줄인다
    (왼쪽 위 모서리에서 가까운 순)."""
    out = img.copy()
    src, dst = img.load(), out.load()
    m = mask_of(img)
    cand = []
    for y in range(1, SIZE - 1):
        for x in range(1, SIZE - 1):
            if not m[y][x]:
                continue
            inner = m[y - 1][x] and m[y][x - 1] and m[y + 1][x] and m[y][x + 1]
            if not inner:
                continue
            if (not (y >= 2 and m[y - 2][x])) or (not (x >= 2 and m[y][x - 2])):
                cand.append((x + y, x, y))
    cand.sort()
    if length is not None:
        cand = cand[:length]
    for _, x, y in cand:
        rr, _ = _find(src[x, y][:3], ramps)
        if rr is not None:
            dst[x, y] = rr[idx] + (255,)
    return out


def recolour(img, mapping: dict) -> Image.Image:
    """색 바꾸기 (같은 틀 + 다른 램프): {옛 RGB: 새 RGB}. 틀 지도를 다른 램프로 칠할 때는 paint 를 다시 부르는 편이 낫다."""
    out = img.copy()
    px = out.load()
    mp = {hx(k): hx(v) for k, v in mapping.items()}
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = px[x, y]
            if a and (r, g, b) in mp:
                px[x, y] = mp[(r, g, b)] + (255,)
    return out


# ───────────────────────────── 규칙 검사 (validate.py 가 씀) ─────────────────────────────

def colours(img) -> set:
    return {p[:3] for p in img.convert('RGBA').getdata() if p[3]}


def isolated(img) -> list[tuple[int, int]]:
    """speckle 후보: 네 이웃이 모두 불투명하고 한 색인데, 자기 색이 8 이웃 어디에도 없는 한 점."""
    im = img.convert('RGBA')
    px = im.load()
    out = []
    for y in range(1, SIZE - 1):
        for x in range(1, SIZE - 1):
            c = px[x, y]
            if not c[3]:
                continue
            n4 = [px[x + 1, y], px[x - 1, y], px[x, y + 1], px[x, y - 1]]
            if any(not n[3] for n in n4) or len({n[:3] for n in n4}) != 1 or n4[0][:3] == c[:3]:
                continue
            n8 = n4 + [px[x + 1, y + 1], px[x - 1, y - 1], px[x + 1, y - 1], px[x - 1, y + 1]]
            if all(n[:3] != c[:3] for n in n8):
                out.append((x, y))
    return out


def components(img) -> list[int]:
    """불투명 칸의 8방향 연결 덩이 크기 (큰 것부터). [0] = 몸통, 나머지 = 떨어진 덩이."""
    m = mask_of(img)
    seen = [[False] * SIZE for _ in range(SIZE)]
    sizes = []
    for y0 in range(SIZE):
        for x0 in range(SIZE):
            if not m[y0][x0] or seen[y0][x0]:
                continue
            seen[y0][x0] = True
            stack, n = [(x0, y0)], 0
            while stack:
                x, y = stack.pop()
                n += 1
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        u, v = x + dx, y + dy
                        if 0 <= u < SIZE and 0 <= v < SIZE and m[v][u] and not seen[v][u]:
                            seen[v][u] = True
                            stack.append((u, v))
            sizes.append(n)
    return sorted(sizes, reverse=True)


def white_count(img) -> int:
    return sum(1 for p in img.convert('RGBA').getdata() if p[3] and p[:3] == WHITE)


def slot_grey_ratio(img) -> float:
    """몸통 칸 가운데 칸 색과 구분되지 않는 무채색 비율 (SLOT_GREY_*)."""
    px = [p for p in img.convert('RGBA').getdata() if p[3]]
    if not px:
        return 0.0
    n = 0
    for r, g, b, _ in px:
        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0.0 if mx == 0 else (mx - mn) / mx
        if abs(0.2126 * r + 0.7152 * g + 0.0722 * b - SLOT_GREY_LUM) <= SLOT_GREY_TOL and sat < SLOT_GREY_SAT:
            n += 1
    return n / len(px)


def soft_check(img) -> list[str]:
    """경고만 하는 검사 (빌드를 막지 않음): 칸 회색에 묻히는 몸통."""
    r = slot_grey_ratio(img)
    return [f'{r:.0%} of the body is slot-grey (lum {SLOT_GREY_LUM}±{SLOT_GREY_TOL}, sat < {SLOT_GREY_SAT}) — '
            f'fades into the inventory slot'] if r > SLOT_GREY_MAX else []


def silhouette_match(a, b) -> tuple[float, float]:
    """두 그림의 (모양 겹침 IoU, 테두리 겹침 Dice) — 같은 자리에 놓고 잰다."""
    ma, mb = mask_of(a), mask_of(b)
    inter = sum(ma[y][x] and mb[y][x] for y in range(SIZE) for x in range(SIZE))
    uni = sum(ma[y][x] or mb[y][x] for y in range(SIZE) for x in range(SIZE))

    def rim(m):
        return {(x, y) for y in range(SIZE) for x in range(SIZE) if m[y][x] and any(
            not (0 <= x + dx < SIZE and 0 <= y + dy < SIZE) or not m[y + dy][x + dx]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    ra, rb = rim(ma), rim(mb)
    return (inter / uni if uni else 0.0), (2 * len(ra & rb) / (len(ra) + len(rb)) if ra or rb else 0.0)


def family(iid, style) -> str:
    """같은 틀을 같이 쓰는 집안 이름 (FAMILY → style 로 등록한 그림이면 그 style → 아이템 자신)."""
    if iid in FAMILY:
        return FAMILY[iid]
    hit = lookup(iid, style)
    if hit and hit[0] == style and style != iid:
        return style
    return iid


def check(img, frames_ok=True, detached_ok=0) -> list[str]:
    """R1·R2·R4·R5 기계 검사 → 문제 목록 (빈 목록 = 통과). frames_ok: 16×(16k) 세로 띠(애니메이션) 허용.
    detached_ok: 몸통에서 떨어진 덩이를 몇 개까지 허용하는지 (DETACHED_OK, 기본 0)."""
    probs = []
    w, h = img.size
    if w != SIZE or (h != SIZE and not (frames_ok and h % SIZE == 0)):
        return [f'size {w}x{h} (want {SIZE}x{SIZE})']
    im = img.convert('RGBA')
    for k in range(h // SIZE):
        fr = im.crop((0, k * SIZE, SIZE, (k + 1) * SIZE))
        tag = f'frame {k}: ' if h > SIZE else ''
        alphas = {p[3] for p in fr.getdata()}
        if alphas - {0, 255}:
            probs.append(f'{tag}semi-transparent alpha {sorted(alphas - {0, 255})[:4]}')
        cols = colours(fr)
        if not (MIN_COLOURS <= len(cols) <= MAX_COLOURS):
            probs.append(f'{tag}{len(cols)} colours (want {MIN_COLOURS}-{MAX_COLOURS})')
        if not cols:
            probs.append(f'{tag}empty')
            continue
        m = mask_of(fr)
        px = fr.load()
        black = 0
        for y in range(SIZE):
            for x in range(SIZE):
                if not m[y][x]:
                    continue
                border = any(not (0 <= x + dx < SIZE and 0 <= y + dy < SIZE) or not m[y + dy][x + dx]
                             for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                r, g, b = px[x, y][:3]
                if border and max(r, g, b) <= 6:
                    black += 1
        if black:
            probs.append(f'{tag}{black} pure-black outline pixel(s)')
        iso = isolated(fr)
        if len(iso) > MAX_ISOLATED:
            probs.append(f'{tag}{len(iso)} isolated single pixels (speckle) at {iso[:6]}')
        wc = white_count(fr)
        if wc > MAX_WHITE:
            probs.append(f'{tag}{wc} pure-white pixels (max {MAX_WHITE})')
        parts = components(fr)
        if len(parts) - 1 > detached_ok:
            probs.append(f'{tag}{len(parts) - 1} detached piece(s) {parts[1:6]} (floating sparkle/dot; allowed {detached_ok} — '
                         f'pixel_icons.DETACHED_OK)')
    return probs


# ───────────────────────────── 등록 ─────────────────────────────

@dataclass
class Art:
    img: Image.Image                                   # layer0, 16×16
    layers: list = field(default_factory=list)         # layer1… (16×16)
    frames: list | None = None                         # layer0 애니메이션 프레임 (16×16 각각)
    frametime: int = 2


class Ctx:
    """그림 함수가 받는 것: 아이템 id·style·희귀도·씨앗 + items.yml 팔레트에서 만든 램프.

    ctx.main  : 본 램프 (팔레트 본 줄의 밝은 가운데 색을 밑색으로 ramp())
    ctx.acc   : 강조 램프 (팔레트 강조색 — 0.3.5 Palette 규칙: 끝 색이 본 줄보다 어두우면 강조색)
    ctx.dark  : 팔레트에서 가장 어두운 색 / ctx.light: 가장 밝은 색 (RGB)
    ctx.raw   : 팔레트 색 그대로 (RGB 목록)
    ctx.ramp(c): 아무 색(또는 RAMPS 이름) → 램프
    ctx.slots(main=…, acc=…): paint 에 줄 slots dict (지정 안 한 main/acc 는 팔레트 램프)"""

    def __init__(self, iid, style, palette, rarity='common', seed=0):
        from ..util import Palette
        from ..materials import RARITY_LEVEL
        self.iid, self.style, self.rarity, self.seed = iid, style, rarity or 'common', seed
        self.level = RARITY_LEVEL.get(self.rarity, 0)
        self.palette = list(palette or [])
        p = Palette(self.palette or None)
        self.pal = p
        self.raw = [tuple(c) for c in p.raw]
        rp = p.ramp
        self.main_base = tuple(rp[min(len(rp) - 1, max(0, round((len(rp) - 1) * 0.66)))])
        self.acc_base = tuple(p.accent)
        self.dark = tuple(p.dark)
        self.light = tuple(p.light)
        self.main = ramp(self.main_base)
        self.acc = ramp(self.acc_base)

    def ramp(self, c, **kw):
        if isinstance(c, str) and not c.startswith('#'):
            return named_ramp(c)
        return ramp(c, **kw)

    def slots(self, **kw):
        s = {'main': self.main, 'acc': self.acc}
        s.update(kw)
        return s


DrawFn = Callable[[Ctx], 'Image.Image | Art']
_REG: dict[str, tuple[DrawFn, str]] = {}


def register(key: str, fn: DrawFn | None = None, *, group: str | None = None):
    """register('id_or_style', fn) 또는 @register('id_or_style'). 같은 키를 두 번 등록하면 오류."""
    def deco(f):
        g = group or f.__module__.rsplit('.', 1)[-1]
        if key in _REG and _REG[key][0] is not f:
            raise KeyError(f'pixel icon {key!r} registered twice ({_REG[key][1]} and {g})')
        _REG[key] = (f, g)
        return f
    return deco(fn) if fn is not None else deco


def register_maps(key: str, slots: dict, *maps, legend=None, group: str | None = None):
    """고정 지도 아이콘 한 줄 등록 (C 시안처럼 램프까지 정해진 아이템). group 을 안 주면 부른 모듈 이름."""
    import sys
    img = paint(slots, *maps, legend=legend)
    g = group or (sys._getframe(1).f_globals.get('__name__') or '').rsplit('.', 1)[-1]
    register(key, lambda ctx, _i=img: _i.copy(), group=g)
    return img


def lookup(iid, style):
    """→ (key, fn, group) | None. 아이템 id 가 style 보다 먼저."""
    for k in (iid, style):
        if k and k in _REG:
            f, g = _REG[k]
            return k, f, g
    return None


def render(iid, style, palette, rarity='common', seed=0) -> Art | None:
    hit = lookup(iid, style)
    if hit is None:
        return None
    key, fn, group = hit
    r = fn(Ctx(iid, style, palette, rarity, seed))
    art = r if isinstance(r, Art) else Art(r)
    for im in [art.img] + list(art.layers) + list(art.frames or []):
        if im.size != (SIZE, SIZE):
            raise ValueError(f'pixel icon {iid} ({key}, {group}): image {im.size} (want 16x16)')
    return art


def registry() -> dict[str, str]:
    """키 → 그룹 (미리보기·검사용)."""
    return {k: g for k, (f, g) in _REG.items()}


for _g in GROUPS:
    importlib.import_module(f'{__name__}.{_g}')
