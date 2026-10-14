"""Pack assembly: pack.mcmeta (26.x min/max_format), original pack.png, atlas sources and a
deterministic zip writer."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

from PIL import Image

from .util import darken, h2, lighten, mix, rng_for

RESOURCE_MAJOR, RESOURCE_MINOR = 97, 1   # Minecraft 26.3 (version.json pack_version.resource_major/minor)


def pack_mcmeta() -> bytes:
    meta = {
        'pack': {
            'description': [
                {'text': '미궁 라비린스', 'color': '#ffd27a', 'bold': True},
                {'text': ' · 지하 10층 공략 전용 리소스팩', 'color': '#c8c8d0'},
            ],
            # 26.x schema: [major, minor]; an integer max_format means "any minor of that major".
            'min_format': [RESOURCE_MAJOR, RESOURCE_MINOR],
            'max_format': RESOURCE_MAJOR,
        }
    }
    return (json.dumps(meta, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def items_atlas() -> bytes:
    """Adds our non-`item/` texture folders (fx, mob) to the items atlas (sources merge across packs)."""
    atlas = {'sources': [
        {'type': 'minecraft:directory', 'source': 'fx', 'prefix': 'fx/'},
        {'type': 'minecraft:directory', 'source': 'mob', 'prefix': 'mob/'},
    ]}
    return (json.dumps(atlas, indent=2) + '\n').encode('utf-8')


def pack_png(size=128) -> Image.Image:
    """Original emblem: a stone labyrinth disc around a glowing gate."""
    S = 32
    rng = rng_for('pack_icon')
    # maze on a 15x15 cell grid (recursive backtracker)
    n = 7
    walls = {(x, y): {'N', 'S', 'E', 'W'} for x in range(n) for y in range(n)}
    stack = [(0, 0)]
    seen = {(0, 0)}
    while stack:
        x, y = stack[-1]
        nb = [(dx, dy, a, b) for dx, dy, a, b in ((0, -1, 'N', 'S'), (0, 1, 'S', 'N'), (1, 0, 'E', 'W'), (-1, 0, 'W', 'E'))
              if (x + dx, y + dy) in walls and (x + dx, y + dy) not in seen]
        if not nb:
            stack.pop()
            continue
        dx, dy, a, b = nb[rng.randrange(len(nb))]
        walls[(x, y)].discard(a)
        walls[(x + dx, y + dy)].discard(b)
        seen.add((x + dx, y + dy))
        stack.append((x + dx, y + dy))
    grid = [[1] * (2 * n + 1) for _ in range(2 * n + 1)]
    for (x, y), w in walls.items():
        gx, gy = 2 * x + 1, 2 * y + 1
        grid[gy][gx] = 0
        if 'E' not in w:
            grid[gy][gx + 1] = 0
        if 'S' not in w:
            grid[gy + 1][gx] = 0
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    px = img.load()
    stone = [(28, 26, 38), (52, 48, 66), (84, 78, 104), (120, 112, 140), (168, 160, 190)]
    gold = (255, 210, 122)
    gm = 2 * n + 1
    off = (S - gm * 2) // 2
    for y in range(S):
        for x in range(S):
            dx, dy = x - S / 2 + 0.5, y - S / 2 + 0.5
            r = (dx * dx + dy * dy) ** 0.5
            if r > 15.5:
                continue
            if r > 14.2:
                px[x, y] = gold + (255,) if (x + y) % 3 else lighten(gold, 0.4) + (255,)
                continue
            if r > 13.4:
                px[x, y] = darken(gold, 0.55) + (255,)
                continue
            gx, gy = (x - off) // 2, (y - off) // 2
            if 0 <= gx < gm and 0 <= gy < gm:
                wall = grid[gy][gx]
            else:
                wall = 1
            if wall:
                k = 2 + (1 if (x + y) % 2 == 0 else 0) - (1 if dy > 4 else 0)
                c = stone[max(0, min(4, k))]
                if h2(x, y, 3) > 0.9:
                    c = stone[4]
            else:
                glow = max(0.0, 1 - r / 13)
                c = mix((18, 16, 30), (255, 180, 90), glow ** 2.2)
            px[x, y] = c + (255,)
    # central gate gem
    for y in range(S):
        for x in range(S):
            dx, dy = abs(x - S / 2 + 0.5), abs(y - S / 2 + 0.5)
            if dx + dy <= 3.2:
                px[x, y] = (lighten(gold, 0.6) if dx + dy < 1.5 else gold) + (255,)
            elif dx + dy <= 4.2:
                px[x, y] = darken(gold, 0.5) + (255,)
    return img.resize((size, size), Image.NEAREST)


def write_zip(files: dict, path) -> str:
    """Deterministic zip: sorted names, fixed timestamps/permissions. Returns SHA-1 hex."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zi.create_system = 0
            z.writestr(zi, files[name])
    data = buf.getvalue()
    with open(path, 'wb') as f:
        f.write(data)
    return hashlib.sha1(data).hexdigest()
