"""Custom UI for 미궁 라비린스: font `labyrinth:ui` (glyphs.yml) — chest-GUI backgrounds, HUD bars, digits,
status icons, party/class mini icons, damage-number digits and boss-bar decoration.

Everything here is original procedural pixel art (no vanilla GUI texture is read or copied).  The only
things taken from the 26.3 client are *measurements* (confirmed from the unobfuscated client bytecode):

- chest screen: 176 x (114 + rows*18); title drawn at (8, 6); container slot item at (8 + 18c, 18 + 18r);
  player inventory at y = rows*18 + 31 (+18 per row), hotbar at rows*18 + 89; inventory label at (8, H - 94).
- bitmap glyph: top = text_y + 7 - ascent (pixels, scale 1 when PNG height == `height`), advance =
  (rightmost column with alpha != 0) + 2.  `ascent` must not exceed `height`.
- action bar: text drawn centred at x = gui_w/2, y = gui_h - 72.

Painters are keyed by the glyph `file` (path under assets/labyrinth/textures/font/ui/); glyphs.yml stays the
single source of truth for char / ascent / height.  A painted image shorter than `height` is padded with
transparent rows at the bottom (that is how glyphs are lifted above the text line without breaking
ascent <= height).
"""
from __future__ import annotations

import io
import json
import re

from PIL import Image, ImageDraw

from .util import clamp8, darken, h2, hex2rgb, lighten, mix

NS = 'labyrinth'
FONT_TEX_DIR = 'font/ui'          # textures/font/ui/<file>
SPACE_BASE = 0xF800               # space glyph for v px = U+F800 + v (ARCHITECTURE §2)

# ───────────────────────────── palette ─────────────────────────────
STONE = [(12, 10, 16), (21, 18, 27), (31, 27, 39), (42, 37, 53), (57, 51, 71), (78, 70, 96)]
GOLD = [(44, 30, 14), (88, 62, 28), (140, 104, 50), (196, 156, 86), (238, 212, 150), (255, 240, 200)]
INK = (8, 6, 10)
SOCKET_IN = (15, 13, 20)
PARCHMENT = [(92, 80, 64), (138, 122, 98), (170, 154, 128), (196, 182, 156)]

STAT_COLORS = {'STR': '#e0533f', 'DEX': '#5fcf72', 'INT': '#5b8ff0', 'VIT': '#f0963c', 'WIS': '#b077ea', 'LUK': '#f0d25a'}
FLOOR_COLORS = ['#6fae4a', '#b8b8c8', '#a067d8', '#3f8fd8', '#f07a2a', '#8fe0f0', '#f08fd0', '#b08a5a', '#d8b048',
                '#e0303c']
DIFF_COLORS = {'easy': '#5fcf72', 'normal': '#5b8ff0', 'hard': '#f0963c', 'nightmare': '#e0303c'}


def _c(h):
    return hex2rgb(h) if isinstance(h, str) else tuple(h[:3])


# ───────────────────────────── tiny pixel fonts (original) ─────────────────────────────
# 4x5 HUD digits — drawn here, not traced from any font.
FONT45 = {
    '0': ['.##.', '#..#', '#..#', '#..#', '.##.'],
    '1': ['..#.', '.##.', '..#.', '..#.', '.###'],
    '2': ['###.', '...#', '.##.', '#...', '####'],
    '3': ['###.', '...#', '.##.', '...#', '###.'],
    '4': ['#..#', '#..#', '####', '...#', '...#'],
    '5': ['####', '#...', '###.', '...#', '###.'],
    '6': ['.##.', '#...', '###.', '#..#', '.##.'],
    '7': ['####', '...#', '..#.', '.#..', '.#..'],
    '8': ['.##.', '#..#', '.##.', '#..#', '.##.'],
    '9': ['.##.', '#..#', '.###', '...#', '.##.'],
    'slash': ['...#', '..#.', '.##.', '.#..', '#...'],
    'plus': ['....', '.#..', '###.', '.#..', '....'],
    'minus': ['....', '....', '###.', '....', '....'],
    'k': ['#...', '#..#', '###.', '#..#', '#..#'],
    'M': ['#..#', '####', '#..#', '#..#', '#..#'],
    'dot': ['.', '.', '.', '.', '#'],
    'colon': ['.', '#', '.', '#', '.'],
}
FONT35 = {
    '0': ['###', '#.#', '#.#', '#.#', '###'], '1': ['.#.', '##.', '.#.', '.#.', '###'],
    '2': ['##.', '..#', '.#.', '#..', '###'], '3': ['##.', '..#', '.#.', '..#', '##.'],
    '4': ['#.#', '#.#', '###', '..#', '..#'], '5': ['###', '#..', '##.', '..#', '##.'],
    '6': ['.##', '#..', '###', '#.#', '###'], '7': ['###', '..#', '.#.', '.#.', '.#.'],
    '8': ['###', '#.#', '.#.', '#.#', '###'], '9': ['###', '#.#', '###', '..#', '##.'],
    'B': ['##.', '#.#', '##.', '#.#', '##.'],
}

# 5x5 status symbols (original)
SYMBOLS = {
    'poison': ['.###.', '#####', '#.#.#', '#####', '.#.#.'],
    'bleed': ['..#..', '.###.', '.###.', '#####', '.###.'],
    'burn': ['..#..', '.##..', '.###.', '#####', '.###.'],
    'slow': ['..#..', '..#..', '#.#.#', '.###.', '..#..'],
    'root': ['..#..', '.###.', '..#..', '#.#.#', '.#.#.'],
    'stun': ['#.#.#', '.###.', '##.##', '.###.', '#.#.#'],
    'weaken': ['...##', '..##.', '.....', '.##..', '##...'],
    'vulnerable': ['#####', '#.#.#', '#..##', '.#.#.', '..#..'],
    'blind': ['#....', '.###.', '#.#.#', '.###.', '....#'],
    'silence': ['#...#', '.#.#.', '..#..', '.#.#.', '#...#'],
    'frost': ['..#..', '#.#.#', '.###.', '#.#.#', '..#..'],
    'infection': ['.#.#.', '#####', '.###.', '#####', '.#.#.'],
    'venom': ['#...#', '#...#', '##.##', '.#.#.', '.#.#.'],
    'mark': ['.###.', '#...#', '#.#.#', '#...#', '.###.'],
    'cooldown_slow': ['#####', '.###.', '..#..', '.###.', '#####'],
    'buff_damage': ['....#', '...#.', '#.#..', '.#...', '#.#..'],
    'buff_defense': ['#####', '#####', '#####', '.###.', '..#..'],
    'buff_speed': ['#.#..', '.#.#.', '..#.#', '.#.#.', '#.#..'],
    'buff_regen': ['..#..', '..#..', '#####', '..#..', '..#..'],
    'buff_shield': ['.###.', '#...#', '#.#.#', '#...#', '.###.'],
    'buff_crit': ['..#..', '..#..', '##.##', '..#..', '..#..'],
    'buff_mana': ['..#..', '.###.', '##.##', '.###.', '..#..'],
    'buff_haste': ['...##', '..##.', '.####', '.##..', '##...'],
    'stealth': ['.###.', '#####', '#.#.#', '#####', '#.#.#'],
    'buff_generic': ['..#..', '.###.', '#.#.#', '..#..', '..#..'],
}
SYMBOL_COLORS = {
    'poison': '#7fd34a', 'bleed': '#e0303c', 'burn': '#ff8a2a', 'slow': '#8fa8d0', 'root': '#a08850',
    'stun': '#ffe04a', 'weaken': '#a890c0', 'vulnerable': '#ff6a3c', 'blind': '#8060a8', 'silence': '#e060c0',
    'frost': '#a8ecff', 'infection': '#c8d84a', 'venom': '#9a4ad8', 'mark': '#ff4a4a', 'cooldown_slow': '#b48aff',
    'buff_damage': '#ff7a5a', 'buff_defense': '#7fb2ff', 'buff_speed': '#6ae0e0', 'buff_regen': '#6ae07a',
    'buff_shield': '#ffd27a', 'buff_crit': '#ffa040', 'buff_mana': '#5b9fff', 'buff_haste': '#ffe86a',
    'stealth': '#9a9ab8', 'buff_generic': '#8fe08f',
}

# 11x11 header emblems (original line art; '#' = gold, '+' = accent, 'o' = dark)
EMBLEMS = {
    'maze': ['###########', '#.....#...#', '#.###.#.#.#', '#.#...#.#.#', '#.#.###.#.#', '#.#.+.#.#.#',
             '#.###.#.#.#', '#.....#.#.#', '#######.#.#', '#.......#.#', '#########+#'],
    'stats': ['.....#.....', '....#+#....', '...#+++#...', '..#+++++#..', '.#+++++++#.', '#####+#####',
              '.....#.....', '....###....', '.....#.....', '...#####...', '..#######..'],
    'class': ['...#####...', '..#+++++#..', '.#+#####+#.', '.#+#ooo#+#.', '.#+#ooo#+#.', '.#+++#+++#.',
              '..#+++++#..', '...#+++#...', '....#+#....', '.....#.....', '...........'],
    'party': ['.#.......#.', '###.....###', '.#...#...#.', '.#..###..#.', '###..#..###', '#+#.###.#+#',
              '###.#+#.###', '.#..###..#.', '.#.#...#.#.', '.#.......#.', '...........'],
    'setup': ['....###....', '..#.#+#.#..', '.#+#####+#.', '..##ooo##..', '###oo+oo###', '#+#o+++o#+#',
              '###oo+oo###', '..##ooo##..', '.#+#####+#.', '..#.#+#.#..', '....###....'],
    'entrance': ['..#######..', '.#+++++++#.', '#++#####++#', '#+#ooooo#+#', '#+#o###o#+#', '#+#o#+#o#+#',
                 '#+#o#+#o#+#', '#+#o#+#o#+#', '#+#o###o#+#', '#+#ooooo#+#', '###########'],
    'blacksmith': ['..#######..', '.##+++++##.', '...#####...', '....###....', '....###....', '...#####...',
                   '..###+###..', '..#######..', '...........', '.+.+...+.+.', '..+.....+..'],
    'titles': ['#....#....#', '##..#+#..##', '#+#.#+#.#+#', '#++#+++#++#', '#+++++++++#', '###########',
               '#+#+#+#+#+#', '###########', '...........', '...........', '...........'],
    'accessories': ['....###....', '...#+++#...', '..#+#.#+#..', '..#+...+#..', '..#+...+#..', '...#+++#...',
                    '....###....', '.....#.....', '....#+#....', '.....#.....', '...........'],
    'merchant': ['...#####...', '..#.....#..', '...#####...', '..#+++++#..', '.#+++#+++#.', '#++++#++++#',
                 '#+++###+++#', '#++++#++++#', '#+++++++++#', '.#+++++++#.', '..#######..'],
    'confirm': ['...........', '.........#.', '........#+.', '.......#+..', '#.....#+...', '+#...#+....',
                '.+#.#+.....', '..+#+......', '...+.......', '...........', '...........'],
    'codex': ['...........', '.####.####.', '#++++#++++#', '#+##+#+##+#', '#++++#++++#', '#+##+#+##+#',
              '#++++#++++#', '#+##+#+##+#', '#++++#++++#', '.####o####.', '.....#.....'],
    'records': ['#.#######.#', '#.#+++++#.#', '.##+++++##.', '..#+++++#..', '..#++o++#..', '...#+++#...',
                '....#+#....', '.....#.....', '....###....', '...#+++#...', '..#######..'],
    'generic': ['....#.#....', '...#+#+#...', '..#+###+#..', '.#+#...#+#.', '#+#.....#+#', '.#.......#.',
                '#+#.....#+#', '.#+#...#+#.', '..#+###+#..', '...#+#+#...', '....#.#....'],
}


# ───────────────────────────── canvas ─────────────────────────────
class Canvas:
    def __init__(self, w, h, fill=(0, 0, 0, 0)):
        self.img = Image.new('RGBA', (w, h), fill)
        self.px = self.img.load()
        self.w, self.h = w, h

    def set(self, x, y, c, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = tuple(c[:3]) + (a,)

    def get(self, x, y):
        return self.px[x, y]

    def blend(self, x, y, c, t):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = self.px[x, y]
            self.px[x, y] = mix(o[:3], c[:3], t) + (max(o[3], 255 if t > 0 else o[3]),)

    def rect(self, x0, y0, x1, y1, c, a=255):
        """Filled, inclusive bounds."""
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.px[x, y] = tuple(c[:3]) + (a,)

    def hline(self, x0, x1, y, c):
        for x in range(x0, x1 + 1):
            self.set(x, y, c)

    def vline(self, x, y0, y1, c):
        for y in range(y0, y1 + 1):
            self.set(x, y, c)

    def box(self, x0, y0, x1, y1, c):
        self.hline(x0, x1, y0, c)
        self.hline(x0, x1, y1, c)
        self.vline(x0, y0, y1, c)
        self.vline(x1, y0, y1, c)

    def pattern(self, x, y, rows, cmap, scale=1):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                c = cmap.get(ch)
                if c is None:
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        self.set(x + i * scale + dx, y + j * scale + dy, c)


# ───────────────────────────── GUI backgrounds ─────────────────────────────
def gui_height(rows):
    return 114 + rows * 18


def slot_xy(slot):
    """Top-left of the 18x18 socket frame of a container slot (item itself sits at +1,+1)."""
    r, c = divmod(slot, 9)
    return 7 + 18 * c, 17 + 18 * r


def _stone(cv: Canvas, x0, y0, x1, y1, seed, base=2, blocks=True):
    """Carved dark-stone wall: running-bond blocks with per-block tone, mortar and soft noise."""
    bw, bh = 22, 11
    for y in range(y0, y1 + 1):
        row = (y - y0) // bh
        off = (row % 2) * (bw // 2)
        for x in range(x0, x1 + 1):
            bx = (x - x0 + off) // bw
            lx, ly = (x - x0 + off) % bw, (y - y0) % bh
            tone = h2(bx, row, seed) * 0.9
            c = mix(STONE[base], STONE[base + 1], tone * 0.55)
            n = (h2(x, y, seed + 7) - 0.5) * 6
            c = tuple(clamp8(v + n) for v in c)
            if blocks and (ly == bh - 1 or lx == bw - 1):
                c = mix(STONE[base - 1], STONE[0], 0.3)
            elif blocks and ly == 0:
                c = mix(c, STONE[base + 2], 0.35)
            if h2(x * 3, y * 5, seed + 11) > 0.985:
                c = mix(c, STONE[0], 0.6)
            cv.set(x, y, c)


def _gold_frame(cv: Canvas, x0, y0, x1, y1, thick=2):
    """Bevelled antique-gold frame (light top-left, dark bottom-right)."""
    cv.box(x0, y0, x1, y1, INK)
    for k in range(1, thick + 1):
        top = GOLD[4] if k == 1 else GOLD[3]
        bot = GOLD[1] if k == 1 else GOLD[2]
        cv.hline(x0 + k, x1 - k, y0 + k, top)
        cv.vline(x0 + k, y0 + k, y1 - k, top)
        cv.hline(x0 + k, x1 - k, y1 - k, bot)
        cv.vline(x1 - k, y0 + k, y1 - k, bot)
    cv.box(x0 + thick + 1, y0 + thick + 1, x1 - thick - 1, y1 - thick - 1, INK)


def _rivet(cv, x, y):
    cv.set(x, y, GOLD[4])
    cv.set(x + 1, y, GOLD[3])
    cv.set(x, y + 1, GOLD[3])
    cv.set(x + 1, y + 1, GOLD[1])


def _corner_ornament(cv, x, y, fx, fy, accent):
    pat = ['###..', '#+#..', '###..', '.....', '.....']
    pat = ['#####.', '#+++#.', '#+#..#', '#+..#.', '#.#.#.', '.#..#.']
    for j, row in enumerate(pat):
        for i, ch in enumerate(row):
            if ch == '.':
                continue
            px = x + (i if fx > 0 else -i)
            py = y + (j if fy > 0 else -j)
            cv.set(px, py, GOLD[4] if ch == '#' else accent)


def socket(cv: Canvas, x, y, style='plain', accent=None):
    """18x18 recessed slot socket at (x, y) — the item renders on (x+1..x+16, y+1..y+16)."""
    acc = _c(accent) if accent else GOLD[3]
    for j in range(16):
        for i in range(16):
            d = max(abs(i - 7.5), abs(j - 7.5)) / 7.5
            c = mix(SOCKET_IN, STONE[1], d * 0.55)
            cv.set(x + 1 + i, y + 1 + j, c)
    cv.hline(x, x + 17, y, STONE[0])
    cv.vline(x, y, y + 17, STONE[0])
    cv.hline(x + 1, x + 17, y + 17, STONE[4])
    cv.vline(x + 17, y + 1, y + 17, STONE[4])
    if style == 'plain':
        return
    if style in ('button', 'tab'):
        rim_hi, rim_lo = (GOLD[4], GOLD[1]) if style == 'button' else ((150, 150, 165), (60, 60, 72))
        cv.hline(x, x + 17, y, rim_lo)
        cv.vline(x, y, y + 17, rim_lo)
        cv.hline(x, x + 17, y + 17, rim_hi)
        cv.vline(x + 17, y, y + 17, rim_hi)
        for (cx, cy) in ((x, y), (x + 17, y), (x, y + 17), (x + 17, y + 17)):
            cv.set(cx, cy, INK)
        cv.set(x + 1, y + 1, acc)
        cv.set(x + 16, y + 1, acc)
        cv.set(x + 1, y + 16, acc)
        cv.set(x + 16, y + 16, acc)
        return
    if style in ('gem', 'big'):
        # accent glow ring inside the socket edge + gold corner studs
        for i in range(1, 17):
            for (px, py) in ((x + i, y + 1), (x + i, y + 16), (x + 1, y + i), (x + 16, y + i)):
                cv.blend(px, py, acc, 0.55)
        for (cx, cy) in ((x, y), (x + 17, y), (x, y + 17), (x + 17, y + 17)):
            cv.set(cx, cy, GOLD[4])
        cv.hline(x + 6, x + 11, y, GOLD[3])
        cv.hline(x + 6, x + 11, y + 17, GOLD[2])
        cv.vline(x, y + 6, y + 11, GOLD[3])
        cv.vline(x + 17, y + 6, y + 11, GOLD[2])
    if style == 'big':
        # outer ornate frame (2px outside) — only for isolated sockets
        _gold_frame(cv, x - 3, y - 3, x + 20, y + 20, thick=1)
        socket(cv, x, y, 'gem', accent)


def _emblem(cv, x, y, name, accent):
    cv.pattern(x, y, EMBLEMS[name], {'#': GOLD[4], '+': _c(accent), 'o': STONE[0]})


def _digits35(cv, x, y, text, color, shadow=True):
    cx = x
    for ch in text:
        g = FONT35[ch]
        if shadow:
            cv.pattern(cx + 1, y + 1, g, {'#': STONE[0]})
        cv.pattern(cx, y, g, {'#': color})
        cx += 4
    return cx - x - 1


def _text35_width(text):
    return len(text) * 4 - 1


def _engrave_line(cv, x0, x1, y, accent=None):
    cv.hline(x0, x1, y, STONE[0])
    cv.hline(x0, x1, y + 1, accent if accent else STONE[4])


def _inset(cv, x0, y0, x1, y1, fill=None, seed=0):
    """Recessed panel: dark bevel top-left, light bottom-right."""
    for y in range(y0 + 1, y1):
        for x in range(x0 + 1, x1):
            base = fill if fill else STONE[1]
            n = (h2(x, y, seed) - 0.5) * 5
            cv.set(x, y, tuple(clamp8(v + n) for v in base))
    cv.hline(x0, x1, y0, STONE[0])
    cv.vline(x0, y0, y1, STONE[0])
    cv.hline(x0, x1, y1, STONE[4])
    cv.vline(x1, y0, y1, STONE[4])


class Gui:
    """One chest-GUI background (176 px wide).  Draw order: base → decor → sockets."""

    def __init__(self, rows, accent, emblem, seed, sockets=True):
        self.rows = rows
        self.H = gui_height(rows)
        self.accent = _c(accent)
        self.cv = Canvas(176, self.H)
        cv = self.cv
        _stone(cv, 0, 0, 175, self.H - 1, seed)
        _gold_frame(cv, 0, 0, 175, self.H - 1, thick=2)
        for (x, y, fx, fy) in ((4, 4, 1, 1), (171, 4, -1, 1), (4, self.H - 5, 1, -1), (171, self.H - 5, -1, -1)):
            _corner_ornament(cv, x, y, fx, fy, self.accent)
        # cut the four outermost corner pixels (soft corners)
        for (x, y) in ((0, 0), (175, 0), (0, self.H - 1), (175, self.H - 1)):
            cv.set(x, y, (0, 0, 0), 0)
        # header plaque behind the title text (title glyphs: x 8.., y 6..14)
        _inset(cv, 4, 3, 171, 15, fill=mix(STONE[1], self.accent, 0.10), seed=seed + 3)
        cv.hline(5, 170, 4, mix(STONE[0], self.accent, 0.25))
        for x in range(8, 156, 2):
            cv.blend(x, 14, self.accent, 0.35)
        if emblem:
            _emblem(cv, 158, 4, emblem, self.accent)
        # container region: recessed panel framing the slot grid
        top, bot = 16, 17 + rows * 18
        _inset(cv, 5, top, 170, bot + 1, fill=STONE[1], seed=seed + 5)
        cv.hline(6, 169, top + 1, mix(STONE[1], self.accent, 0.18))
        # inventory label plaque (vanilla draws the dark-grey "인벤토리" label at (8, H-94)) — light stone so it reads
        ly = self.H - 94
        _inset(cv, 5, ly - 3, 72, ly + 9, fill=PARCHMENT[2], seed=seed + 9)
        for x in range(6, 72):
            cv.blend(x, ly - 2, PARCHMENT[3], 0.6)
        cv.set(73, ly + 3, GOLD[3])
        cv.hline(74, 168, ly + 3, GOLD[2])
        cv.hline(74, 168, ly + 4, GOLD[0])
        for x in range(80, 168, 12):
            _rivet(cv, x, ly + 2)
        # player inventory 3x9 + hotbar sockets (exact vanilla positions)
        inv_y = rows * 18 + 31
        _inset(cv, 5, inv_y - 2, 170, inv_y + 54 - 1, fill=STONE[1], seed=seed + 13)
        for r in range(3):
            for c in range(9):
                socket(cv, 7 + 18 * c, inv_y - 1 + 18 * r)
        hot_y = rows * 18 + 89
        _inset(cv, 5, hot_y - 2, 170, hot_y + 17, fill=mix(STONE[1], self.accent, 0.08), seed=seed + 17)
        for c in range(9):
            socket(cv, 7 + 18 * c, hot_y - 1, 'plain')
        cv.hline(7, 168, hot_y + 17, mix(GOLD[2], self.accent, 0.3))

    # helpers -------------------------------------------------------------------------------------
    def sock(self, slots, style='plain', accent=None):
        for s in ([slots] if isinstance(slots, int) else slots):
            x, y = slot_xy(s)
            socket(self.cv, x, y, style, accent or self.accent)

    def glow(self, cx, cy, radius, color, strength=0.5):
        c = _c(color)
        for y in range(int(cy - radius), int(cy + radius) + 1):
            for x in range(int(cx - radius), int(cx + radius) + 1):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / radius
                if d < 1 and 6 <= x <= 169 and 17 <= y <= 17 + self.rows * 18:
                    self.cv.blend(x, y, c, strength * (1 - d) ** 1.6)

    def image(self):
        return self.cv.img


def _row_y(r):
    return 17 + 18 * r


def gui_main(seed):
    g = Gui(3, '#e6aa50', 'maze', seed)
    cv = g.cv
    # engraved maze filigree on rows 0 and 2
    for (y0, y1) in ((18, 33), (54, 69)):
        for x in range(8, 168):
            for y in range(y0, y1 + 1):
                gx, gy = (x - 8) // 4, (y - y0) // 4
                if (x - 8) % 4 == 0 and h2(gx, gy, seed) > 0.55 or (y - y0) % 4 == 0 and h2(gx, gy, seed + 1) > 0.6:
                    cv.blend(x, y, GOLD[2], 0.28)
    g.glow(88, 44, 70, g.accent, 0.18)
    _gold_frame(cv, 22, 33, 153, 54, thick=1)
    g.sock(list(range(10, 17)), 'button')
    return g


def gui_stats(seed):
    g = Gui(6, '#d84a50', 'stats', seed)
    cv = g.cv
    for r, (stat, col) in enumerate(STAT_COLORS.items()):
        col = _c(col)
        y = _row_y(r)
        # engraved stat track over columns 1..5 with five notches and a coloured glow line
        _inset(cv, 25, y + 2, 114, y + 15, fill=mix(STONE[1], col, 0.10), seed=seed + r)
        for k in range(1, 5):
            cv.vline(25 + 18 * k, y + 3, y + 14, mix(STONE[0], col, 0.15))
        for x in range(26, 114):
            cv.blend(x, y + 13, col, 0.55)
            cv.blend(x, y + 14, col, 0.25)
        # divider between rows
        if r < 5:
            for x in range(8, 168, 3):
                cv.blend(x, y + 17, GOLD[1], 0.5)
        # separator rune before the buttons
        cv.vline(117, y + 3, y + 14, GOLD[1])
        cv.set(117, y + 8, col)
        cv.set(117, y + 9, col)
    for r, (stat, col) in enumerate(STAT_COLORS.items()):
        g.sock(r * 9, 'gem', col)
        g.sock([r * 9 + 6, r * 9 + 7, r * 9 + 8], 'button', col)
    return g


def _arch(g: Gui, slot, accent):
    """Gold-rimmed arch niche with an accent glow around a class socket, standing on a pedestal."""
    cv = g.cv
    x, y = slot_xy(slot)
    acc = _c(accent)
    cx = x + 8.5
    top = y - 11
    R = 12.5

    def shape(xx, yy, r):
        dx = abs(xx - cx)
        if yy >= top + 8:
            return dx <= r
        return dx * dx + ((yy - top - 8) * 1.45) ** 2 <= r * r

    for yy in range(top - 2, y + 20):
        for xx in range(x - 7, x + 26):
            if shape(xx, yy, R):
                t = max(0.0, 1 - ((xx - cx) ** 2 + (yy - y - 8) ** 2) ** 0.5 / 18)
                cv.set(xx, yy, mix(STONE[0], acc, 0.16 + 0.42 * t * t))
            elif shape(xx, yy, R + 1):
                cv.set(xx, yy, GOLD[4] if yy < y + 4 else GOLD[3])
            elif shape(xx, yy, R + 2):
                cv.set(xx, yy, GOLD[1])
    # keystone gem
    cv.rect(int(cx) - 1, top - 1, int(cx) + 1, top + 1, GOLD[4])
    cv.set(int(cx), top, acc)
    # pedestal
    cv.rect(x - 5, y + 19, x + 22, y + 21, GOLD[2])
    cv.hline(x - 5, x + 22, y + 19, GOLD[4])
    cv.hline(x - 5, x + 22, y + 22, INK)
    g.sock(slot, 'gem', accent)


def gui_class(seed, class_colors):
    g = Gui(6, '#9a5ae0', 'class', seed)
    cols = list(class_colors) + ['#9a5ae0'] * 6
    for k, slot in enumerate((10, 13, 16, 28, 31, 34)):
        _arch(g, slot, cols[k])
    cv = g.cv
    # skill strip (row 4, columns 2..6): engraved rail under the five skill sockets
    _engrave_line(cv, 40, 135, _row_y(5) - 1, mix(STONE[4], g.accent, 0.5))
    g.sock(list(range(38, 43)), 'plain')
    g.sock([45, 53], 'button')
    g.sock(49, 'gem', '#ffd27a')
    return g


def _banner(cv, x, y, w, h, color):
    col = _c(color)
    for j in range(h):
        for i in range(w):
            notch = j >= h - 4 and abs(i - (w - 1) / 2) < (j - (h - 4)) + 0.5
            if notch:
                continue
            c = mix(darken(col, 0.45), col, 0.55 + 0.45 * (1 - j / h))
            if i in (0, w - 1):
                c = GOLD[2]
            if (i + j) % 7 == 0 and 1 < i < w - 2:
                c = lighten(c, 0.15)
            cv.set(x + i, y + j, c)
    cv.hline(x - 1, x + w, y - 1, GOLD[4])


def gui_party(seed):
    g = Gui(6, '#3cc0b4', 'party', seed)
    cv = g.cv
    # header band row 0 with the party crest socket in the middle
    for x in range(8, 168):
        cv.blend(x, _row_y(0) + 8, g.accent, 0.25)
    _gold_frame(cv, 60, _row_y(0) + 1, 115, _row_y(0) + 16, thick=1)
    members = [9, 11, 13, 15, 17, 27, 29, 31, 33, 35]
    for s in members:
        x, y = slot_xy(s)
        _banner(cv, x + 3, y + 19, 12, 15, mix(g.accent, (40, 40, 60), 0.35))
        # mini HP plate under the banner
        cv.rect(x + 2, y + 34, x + 15, y + 35, STONE[0])
        cv.hline(x + 3, x + 14, y + 34, (60, 160, 80))
    g.sock(4, 'gem', '#ffd27a')
    g.sock(members, 'gem')
    g.sock([45, 47, 49, 51, 53], 'button')
    return g


def gui_setup(seed):
    g = Gui(6, '#f0b446', 'setup', seed)
    cv = g.cv
    for k, (diff, col) in enumerate(DIFF_COLORS.items()):
        slot = (10, 12, 14, 16)[k]
        x, y = slot_xy(slot)
        c = _c(col)
        # crest pillar spanning rows 0..2
        _inset(cv, x - 3, _row_y(0) + 1, x + 20, _row_y(3) - 2, fill=mix(STONE[1], c, 0.14), seed=seed + k)
        for yy in range(_row_y(0) + 2, _row_y(3) - 2):
            cv.blend(x - 2, yy, c, 0.5)
            cv.blend(x + 19, yy, c, 0.5)
        # difficulty pips (1..4 skull-gems) under the socket
        n = k + 1
        px0 = x + 9 - (n * 5 - 1) // 2
        for i in range(n):
            cv.pattern(px0 + i * 5, y + 22, ['.##.', '#++#', '#..#', '.##.'], {'#': GOLD[4], '+': c, '.': None})
        g.glow(x + 9, y + 9, 16, c, 0.35)
    # divider band with gate emblem (row 3)
    y3 = _row_y(3) + 8
    _engrave_line(cv, 10, 165, y3, mix(STONE[4], g.accent, 0.4))
    _emblem(cv, 82, y3 - 5, 'entrance', g.accent)
    for k, slot in enumerate((10, 12, 14, 16)):
        g.sock(slot, 'gem', list(DIFF_COLORS.values())[k])
    # entrance mode options (row 4) + confirm (row 5)
    g.sock(38, 'big', '#c8a070')
    g.sock(42, 'big', '#8fd0ff')
    g.sock(49, 'big', '#ffd27a')
    return g


def gui_entrance(seed):
    g = Gui(6, '#4a78e6', 'entrance', seed)
    cv = g.cv
    nodes = [9, 11, 13, 15, 17, 35, 33, 31, 29, 27]
    # depth gradient: rows darken and redden toward floor 10
    for y in range(18, _row_y(5)):
        t = (y - 18) / (_row_y(5) - 18)
        for x in range(6, 170):
            cv.blend(x, y, (60, 8, 20), 0.18 * t)
    # carved path channel joining the nodes (snake)
    pts = [slot_xy(s) for s in nodes]
    for (a, b) in zip(pts, pts[1:]):
        (x0, y0), (x1, y1) = a, b
        if y0 == y1:
            for x in range(min(x0, x1) + 9, max(x0, x1) + 9):
                cv.set(x, y0 + 8, STONE[0])
                cv.set(x, y0 + 9, mix(STONE[3], g.accent, 0.35) if x % 4 else GOLD[2])
                cv.set(x, y0 + 10, STONE[4])
        else:
            for y in range(min(y0, y1) + 9, max(y0, y1) + 9):
                cv.set(x0 + 8, y, STONE[0])
                cv.set(x0 + 9, y, mix(STONE[3], g.accent, 0.35) if y % 4 else GOLD[2])
                cv.set(x0 + 10, y, STONE[4])
    # floor numbers engraved under each node (rows 2 and 4)
    for k, s in enumerate(nodes):
        x, y = slot_xy(s)
        label = str(k + 1)
        w = _text35_width('B' + label)
        _digits35(cv, x + 9 - w // 2, y + 20, 'B' + label, lighten(_c(FLOOR_COLORS[k]), 0.25))
        g.glow(x + 9, y + 9, 13, FLOOR_COLORS[k], 0.35)
    for k, s in enumerate(nodes):
        g.sock(s, 'gem', FLOOR_COLORS[k])
    g.sock([45, 53], 'button')
    g.sock(49, 'big', '#ffd27a')
    return g


def gui_blacksmith(seed):
    g = Gui(6, '#f07828', 'blacksmith', seed)
    cv = g.cv
    # row 1: forge banner — anvil silhouette with embers and chains
    y1 = _row_y(1)
    _inset(cv, 7, y1 + 1, 168, y1 + 16, fill=(26, 18, 16), seed=seed + 1)
    for x in range(8, 168):
        for y in range(y1 + 2, y1 + 16):
            t = 1 - abs(x - 88) / 80
            cv.blend(x, y, (240, 110, 30), 0.30 * t * ((y - y1) / 16) ** 1.5)
    anvil = ['..##########..', '.############.', '...########...', '.....####.....', '.....####.....',
             '...########...', '..##########..']
    cv.pattern(81, y1 + 4, anvil, {'#': (60, 58, 66)})
    cv.hline(82, 92, y1 + 4, (120, 116, 130))
    for k in range(18):
        ex = 20 + int(h2(k, 1, seed) * 136)
        ey = y1 + 3 + int(h2(k, 2, seed) * 11)
        cv.set(ex, ey, (255, 170 + int(h2(k, 3, seed) * 70), 60))
    for cx in (12, 160):
        for y in range(y1 + 2, y1 + 16, 3):
            cv.set(cx, y, GOLD[2])
            cv.set(cx + 1, y + 1, GOLD[1])
    # recipe grid frame rows 2..4 (iron with rivets)
    yy0, yy1 = _row_y(2) - 1, _row_y(5)
    cv.box(6, yy0, 169, yy1, (90, 90, 100))
    for x in range(10, 168, 16):
        _rivet(cv, x, yy0 - 1)
    g.sock(list(range(18, 45)), 'plain')
    g.sock([1, 3, 5, 7], 'tab', '#f07828')
    g.sock([45, 53], 'button')
    g.sock([47, 51], 'button', '#c8c8d0')
    # bottom centre forge emblem (decor only)
    _emblem(cv, 83, _row_y(5) + 3, 'blacksmith', g.accent)
    return g


def gui_titles(seed):
    g = Gui(6, '#f0c85a', 'titles', seed)
    cv = g.cv
    # velvet display case rows 1..4
    for y in range(_row_y(1) - 1, _row_y(5) + 1):
        for x in range(6, 170):
            v = 0.5 + 0.5 * h2(x // 2, y // 2, seed)
            cv.set(x, y, mix((40, 10, 24), (66, 18, 38), v * 0.6))
    _gold_frame(cv, 5, _row_y(1) - 2, 170, _row_y(5) + 1, thick=1)
    cat_cols = ['#ffd27a', '#7fd0ff', '#ff7a5a', '#e05050', '#8fe08f', '#c890ff', '#f0a050', '#ff5a7a']
    for k in range(8):
        g.sock(k, 'tab', cat_cols[k])
    g.sock(8, 'gem', '#ffd27a')
    g.sock(list(range(9, 45)), 'plain')
    g.sock([45, 53], 'button')
    g.sock(49, 'big', '#ffd27a')
    return g


def gui_accessories(seed):
    g = Gui(3, '#46c882', 'accessories', seed)
    cv = g.cv
    # filigree vines across rows 0 and 2
    for x in range(8, 168):
        y = _row_y(0) + 9 + int(3 * __import__('math').sin(x / 6.0))
        cv.set(x, y, GOLD[2])
        y2 = _row_y(2) + 8 + int(3 * __import__('math').sin(x / 6.0 + 3.1))
        cv.set(x, y2, GOLD[2])
        if x % 12 == 0:
            cv.set(x, y - 1, g.accent)
            cv.set(x, y2 + 1, g.accent)
    g.glow(88, 44, 60, g.accent, 0.20)
    ring = ['..###..', '.#...#.', '#.....#', '#.....#', '#.....#', '.#...#.', '..###..']
    amulet = ['#.....#', '.#...#.', '..#.#..', '...#...', '..###..', '.#+++#.', '..###..']
    x11, y11 = slot_xy(11)
    x15, y15 = slot_xy(15)
    cv.pattern(x11 - 14, y11 + 5, ring, {'#': GOLD[3]})
    cv.pattern(x15 + 25, y15 + 5, amulet, {'#': GOLD[3], '+': g.accent})
    g.sock(11, 'big', '#46c882')
    g.sock(15, 'big', '#46c882')
    g.sock(13, 'gem', '#ffd27a')
    return g


def gui_merchant(seed):
    g = Gui(6, '#a0c850', 'merchant', seed)
    cv = g.cv
    # striped awning along row 0
    y0 = _row_y(0)
    for x in range(6, 152):
        stripe = ((x - 6) // 8) % 2 == 0
        for y in range(y0 + 1, y0 + 12):
            c = (120, 36, 40) if stripe else (196, 176, 130)
            if y >= y0 + 9:
                scallop = abs(((x - 6) % 8) - 3.5) < (y0 + 12 - y) * 1.5
                if not scallop:
                    continue
            cv.set(x, y, darken(c, 0.25 * (y - y0) / 12))
    # shelves under each shop row (rows 1..4, cols 1..7)
    for r in range(1, 5):
        y = _row_y(r) + 17
        cv.rect(23, y, 152, y + 1, (100, 66, 36))
        cv.hline(23, 152, y, (150, 104, 60))
    # lantern pillars at columns 0 and 8
    for cx in (15, 160):
        cv.rect(cx - 2, _row_y(1), cx + 2, _row_y(5) - 2, (52, 40, 30))
        cv.vline(cx - 2, _row_y(1), _row_y(5) - 2, (80, 62, 44))
        for r in (1, 3):
            ly = _row_y(r) + 6
            cv.rect(cx - 3, ly, cx + 3, ly + 6, GOLD[1])
            cv.rect(cx - 2, ly + 1, cx + 2, ly + 5, (255, 200, 90))
            g.glow(cx, ly + 3, 10, (255, 190, 90), 0.4)
    shop = [r * 9 + c for r in range(1, 5) for c in range(1, 8)]
    g.sock(shop, 'plain')
    g.sock(8, 'gem', '#ffd27a')
    g.sock([45, 53], 'button')
    g.sock(49, 'gem', '#a0c850')
    return g


def gui_confirm(seed):
    g = Gui(3, '#c8a064', 'confirm', seed)
    g.glow(30, 44, 26, '#46c882', 0.30)
    g.glow(146, 44, 26, '#e04646', 0.30)
    g.sock(11, 'big', '#46c882')
    g.sock(15, 'big', '#e04646')
    g.sock(13, 'gem', '#ffd27a')
    return g


def gui_generic(seed, rows):
    g = Gui(rows, '#8a7ab0', 'generic', seed)
    g.sock(list(range(rows * 9)), 'plain')
    return g


def gui_panel(seed, rows):
    """동적 메뉴 바탕: 소켓 없는 상자 영역(새긴 미궁 무늬) + 플레이어 인벤토리. 버튼 자리 소켓은 플러그인이
    제목에 gui_sock_<줄>/gui_btn_<줄> 글리프로 덧그리고, 오른쪽 위 문장은 gui_emblem_<이름> 으로 얹는다."""
    g = Gui(rows, '#c8a064', None, seed)
    cv = g.cv
    y0, y1 = 18, 16 + rows * 18
    for y in range(y0, y1 + 1):
        for x in range(7, 169):
            gx, gy = (x - 7) // 6, (y - y0) // 6
            on_v = (x - 7) % 6 == 0 and h2(gx, gy, seed) > 0.5
            on_h = (y - y0) % 6 == 0 and h2(gx, gy, seed + 1) > 0.55
            if on_v or on_h:
                cv.blend(x, y, GOLD[2], 0.16)
            elif (x - 7) % 6 == 1 and on_v is False and (y - y0) % 6 == 1 and h2(gx, gy, seed + 2) > 0.8:
                cv.blend(x, y, GOLD[3], 0.30)
    g.glow(88, 17 + rows * 9, 40 + rows * 10, (150, 110, 220), 0.10)
    return g


def paint_socket_glyph(style):
    cv = Canvas(18, 18)
    socket(cv, 0, 0, 'plain' if style == 'plain' else 'button', '#e6aa50')
    if style == 'button':
        # 버튼 칸: 안쪽 금빛 테 (반투명) — 눌러 볼 수 있는 자리
        for i in range(2, 16):
            for (x, y) in ((i, 2), (i, 15), (2, i), (15, i)):
                cv.blend(x, y, GOLD[3], 0.30)
    return cv.img


def paint_emblem_glyph(name):
    cv = Canvas(11, 11)
    _emblem(cv, 0, 0, name, (255, 210, 122) if name not in ('pvp',) else (230, 70, 70))
    if cv.get(10, 10)[3] == 0:
        cv.set(10, 10, (0, 0, 0), 1)     # advance 고정 (가장 오른쪽 열이 비어도 12)
    return cv.img


def paint_cast(step, steps=10):
    """시전 막대 64×7 (cast_00..10): 먹선 + 금 끝장식 + 보라→금 채움. 귀환 주문서·부활의 성가 등."""
    W, H = 64, 7
    cv = Canvas(W, H)
    inner = W - 6
    fill = round(inner * step / steps)
    for x in range(W):
        for y in range(H):
            tip = abs(y - 3)
            if x < 3 or x > W - 4:      # 마름모 끝장식
                dx = x if x < 3 else W - 1 - x
                if tip <= dx:
                    cv.set(x, y, GOLD[4] if y < 3 else GOLD[2])
                    if tip == dx:
                        cv.set(x, y, INK)
                continue
            if y in (0, H - 1):
                cv.set(x, y, INK)
                continue
            ix = x - 3
            if ix < fill:
                t = ix / max(1, inner - 1)
                c = mix((150, 90, 255), (255, 214, 120), t)
                c = lighten(c, 0.35) if y == 1 else c if y < 4 else darken(c, 0.25)
                if ix == fill - 1:
                    c = lighten(c, 0.4)
            else:
                c = (24, 20, 32) if y > 1 else (34, 30, 44)
            cv.set(x, y, c)
    cv.set(1, 3, (190, 140, 255))
    cv.set(W - 2, 3, (190, 140, 255))
    return cv.img


def paint_gui(name, ctx_content):
    seed = sum(map(ord, name)) * 131
    if name == 'class':
        classes = (ctx_content.get('classes') or {}).get('classes') or {}
        cols = [(d or {}).get('color') or '#9a5ae0' for d in classes.values()]
        return gui_class(seed, cols).image()
    fns = {
        'main': gui_main, 'stats': gui_stats, 'party': gui_party, 'setup': gui_setup, 'entrance': gui_entrance,
        'blacksmith': gui_blacksmith, 'titles': gui_titles, 'accessories': gui_accessories,
        'merchant': gui_merchant, 'confirm': gui_confirm,
        'generic_6': lambda s: gui_generic(s, 6), 'generic_3': lambda s: gui_generic(s, 3),
    }
    for r in range(1, 7):
        fns.setdefault(f'generic_{r}', lambda s, r=r: gui_generic(s, r))
        fns[f'panel_{r}'] = lambda s, r=r: gui_panel(s, r)
    if name not in fns:
        return None
    return fns[name](seed).image()


# ───────────────────────────── HUD glyphs ─────────────────────────────
BAR_STEPS = 20
BAR_W, BAR_H = 82, 9
XP_W, XP_H = 182, 3
BAR_COLORS = {
    'hp': [(255, 150, 150), (230, 52, 64), (150, 18, 36), (90, 8, 20)],
    'mp': [(170, 225, 255), (60, 140, 235), (24, 70, 160), (12, 36, 90)],
    'xp': [(255, 236, 160), (232, 180, 60), (150, 100, 24), (80, 50, 12)],
    'shield': [(255, 250, 220), (240, 214, 120), (176, 140, 50), (96, 72, 20)],
}


def paint_bar(kind, step):
    """Segmented bar 82x9: 20 segments of 4px (3 fill + 1 groove), gold end cap on the outer side."""
    cols = BAR_COLORS[kind]
    cv = Canvas(BAR_W, BAR_H)
    mirror = kind == 'mp'
    for y in range(BAR_H):
        for x in range(BAR_W):
            edge = x in (0, BAR_W - 1) or y in (0, BAR_H - 1)
            corner = (x in (0, BAR_W - 1)) and (y in (0, BAR_H - 1))
            if corner:
                continue
            if edge:
                cv.set(x, y, INK)
                continue
            ix = x - 1                     # 0..79
            seg = ix // 4
            if mirror:
                seg = BAR_STEPS - 1 - seg
            groove = ix % 4 == 3
            filled = seg < step
            iy = y - 1                     # 0..6
            if filled and not groove:
                if iy == 0:
                    c = cols[0]
                elif iy <= 3:
                    c = mix(cols[0], cols[1], (iy) / 3)
                else:
                    c = mix(cols[1], cols[2], (iy - 3) / 3)
                if seg == step - 1:
                    c = lighten(c, 0.18)   # bright leading edge
            elif filled:
                c = cols[3]
            else:
                c = mix((22, 18, 28), (34, 30, 42), 1 - iy / 6)
                if groove:
                    c = (14, 12, 18)
            cv.set(x, y, c)
    # gold cap on the outer end
    cx = 0 if not mirror else BAR_W - 1
    for y in range(1, BAR_H - 1):
        cv.set(cx, y, GOLD[3] if y < BAR_H // 2 else GOLD[2])
    cv.set(cx, 0, GOLD[4])
    cv.set(cx, BAR_H - 1, GOLD[1])
    return cv.img


def paint_xp(step):
    cols = BAR_COLORS['xp']
    cv = Canvas(XP_W, XP_H)
    filled_w = round(180 * step / BAR_STEPS)
    for x in range(XP_W):
        for y in range(XP_H):
            if x in (0, XP_W - 1) or y in (0, XP_H - 1):
                cv.set(x, y, INK)
            else:
                ix = x - 1
                if ix < filled_w:
                    cv.set(x, y, cols[1] if (ix // 9) % 2 == 0 else mix(cols[1], cols[0], 0.35))
                else:
                    cv.set(x, y, (26, 22, 32))
    # 0.5-alpha marks every 10% so progress reads at a glance
    for k in range(1, 10):
        cv.set(1 + 18 * k, 0, GOLD[3])
    return cv.img


def paint_badge():
    """Level shield 18x16 (digits are drawn on top by the plugin)."""
    cv = Canvas(18, 16)
    for y in range(16):
        for x in range(18):
            dx = abs(x - 8.5)
            lim = 8.5 if y < 9 else 8.5 - (y - 8) * 1.2
            if dx > lim:
                continue
            if dx > lim - 1 or y == 0:
                c = INK
            elif dx > lim - 2 or y == 1:
                c = GOLD[3] if y < 8 else GOLD[2]
            else:
                c = mix((40, 26, 52), (22, 14, 30), y / 15)
            cv.set(x, y, c)
    cv.set(8, 0, GOLD[4])
    cv.set(9, 0, GOLD[4])
    cv.set(8, 15, GOLD[2]) if cv.get(8, 15)[3] else None
    return cv.img


def paint_coin():
    cv = Canvas(9, 9)
    for y in range(9):
        for x in range(9):
            d = ((x - 4) ** 2 + (y - 4) ** 2) ** 0.5
            if d > 4.4:
                continue
            if d > 3.6:
                c = GOLD[1]
            elif d > 2.6:
                c = GOLD[3] if x + y < 9 else GOLD[2]
            else:
                c = GOLD[4] if x + y < 8 else GOLD[3]
            cv.set(x, y, c)
    cv.set(4, 3, GOLD[1])
    cv.set(4, 4, GOLD[1])
    cv.set(4, 5, GOLD[1])
    cv.set(3, 2, GOLD[5])
    return cv.img


def paint_digit(sym, scale=1, style='hud'):
    """Outlined pixel digit.  White-ish body (tintable via component colour) unless style == 'crit'."""
    g = FONT45[sym]
    w, h = len(g[0]) * scale, len(g) * scale
    cv = Canvas(w + 2, h + 2)
    body = set()
    for j, row in enumerate(g):
        for i, ch in enumerate(row):
            if ch == '#':
                for dy in range(scale):
                    for dx in range(scale):
                        body.add((1 + i * scale + dx, 1 + j * scale + dy))
    for (x, y) in body:
        # 상하좌우 1px 외곽선만 (대각선까지 칠하면 숫자마다 어두운 네모 칸처럼 보임)
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (x + ox, y + oy) not in body:
                cv.set(x + ox, y + oy, (20, 12, 24))
    for (x, y) in body:
        t = (y - 1) / max(1, h - 1)
        if style == 'crit':
            c = mix((255, 246, 140), (255, 120, 30), t) if t < 0.7 else mix((255, 120, 30), (220, 40, 30), (t - 0.7) / 0.3)
        elif style == 'dmg':
            c = mix((255, 255, 255), (214, 210, 224), t)
        else:
            c = mix((255, 255, 255), (220, 220, 232), t)
        cv.set(x, y, c)
    # monospace: pin the advance with an (invisible) alpha-1 pixel in the last column
    full_w = (4 if sym not in ('dot', 'colon') else 1) * scale + 2
    if cv.w < full_w:
        pass
    img = cv.img
    if img.size[0] < full_w:
        n = Image.new('RGBA', (full_w, img.size[1]), (0, 0, 0, 0))
        n.alpha_composite(img, (0, 0))
        img = n
    px = img.load()
    if px[img.size[0] - 1, img.size[1] - 1][3] == 0:
        px[img.size[0] - 1, img.size[1] - 1] = (0, 0, 0, 1)
    return img


def paint_status(sym, buff):
    cv = Canvas(9, 9)
    col = _c(SYMBOL_COLORS[sym])
    rim = (40, 110, 70) if buff else (120, 26, 36)
    for y in range(9):
        for x in range(9):
            if (x in (0, 8)) and (y in (0, 8)):
                continue
            if x in (0, 8) or y in (0, 8):
                cv.set(x, y, INK)
            elif x in (1, 7) or y in (1, 7):
                cv.set(x, y, rim if not (x == 1 and y == 1) else lighten(rim, 0.3))
            else:
                cv.set(x, y, (20, 16, 26))
    cv.pattern(2, 2, SYMBOLS[sym], {'#': col})
    # top-left highlight on the symbol
    for y in range(2, 7):
        for x in range(2, 7):
            p = cv.get(x, y)
            if p[:3] == col and (y == 2 or x == 2):
                cv.set(x, y, lighten(col, 0.35))
    return cv.img


def paint_party_bar(step):
    """Mini party HP bar 33x5, 10 steps, colour by remaining HP."""
    cv = Canvas(33, 5)
    ratio = step / 10
    col = (90, 210, 100) if ratio > 0.5 else (240, 200, 70) if ratio > 0.25 else (230, 60, 60)
    for y in range(5):
        for x in range(33):
            if (x in (0, 32)) and (y in (0, 4)):
                continue
            if x in (0, 32) or y in (0, 4):
                cv.set(x, y, INK)
                continue
            ix = x - 1
            if ix < step * 3 + (1 if step == 10 else 0) and ix // 3 < step:
                c = lighten(col, 0.3) if y == 1 else col if y == 2 else darken(col, 0.3)
            else:
                c = (30, 26, 36)
            cv.set(x, y, c)
    return cv.img


CLASS_ICONS = {
    'guardian': ['#######', '#+++++#', '#+###+#', '#+#+#+#', '.#+++#.', '..#+#..', '...#...'],
    'berserker': ['#.....#', '##...##', '.##.##.', '..###..', '.##.##.', '##...##', '#.....#'],
    'hunter': ['..##...', '.#..#..', '#....#.', '#######', '#....#.', '.#..#..', '..##...'],
    'arcanist': ['...#...', '..#+#..', '.#+++#.', '#+++++#', '.#+++#.', '..#+#..', '...#...'],
    'priest': ['...#...', '...#...', '#######', '...#...', '...#...', '...#...', '...#...'],
    'shadow': ['.#####.', '#######', '#.#.#.#', '#######', '.##.##.', '.#...#.', '.......'],
}


def paint_class_icon(cid, color):
    cv = Canvas(7, 7)
    pat = CLASS_ICONS.get(cid) or CLASS_ICONS['arcanist']
    c = _c(color)
    cv.pattern(0, 0, pat, {'#': c, '+': lighten(c, 0.5)})
    return cv.img


def paint_boss_ornament(side):
    """Wing/horn ornament 20x12 flanking the boss name (gold + crimson gem)."""
    pat = ['..............##....', '...........####.....', '........#####......#', '.....######.......##',
           '...#######.......###', '.########......#####', '#########....###++##', '.########......#####',
           '...#######.......###', '.....######.......##', '........#####......#', '...........####.....']
    cv = Canvas(20, 12)
    for j, row in enumerate(pat):
        for i, ch in enumerate(row):
            if ch == '#':
                cv.set(i, j, GOLD[4] if j < 6 else GOLD[2])
            elif ch == '+':
                cv.set(i, j, (230, 40, 60))
    img = cv.img
    return img if side == 'left' else img.transpose(Image.FLIP_LEFT_RIGHT)


def paint_boss_frame():
    """190x13 frame with a transparent 182x5 window at (4, 4): use as the *whole* boss-bar name."""
    cv = Canvas(190, 13)
    for y in range(13):
        for x in range(190):
            in_win = 4 <= x <= 185 and 4 <= y <= 8
            if in_win:
                continue
            if 3 <= x <= 186 and 3 <= y <= 9:
                cv.set(x, y, INK)
            elif 2 <= x <= 187 and 2 <= y <= 10:
                cv.set(x, y, GOLD[3] if y <= 6 else GOLD[2])
            elif 1 <= x <= 188 and 1 <= y <= 11 and (x < 12 or x > 177 or y in (1, 11)) and (x + y) % 2 == 0:
                cv.set(x, y, GOLD[1])
    # end gems
    for gx in (0, 186):
        cv.rect(gx, 4, gx + 3, 8, GOLD[1])
        cv.rect(gx + 1, 5, gx + 2, 7, (230, 40, 60))
    for gx in range(30, 170, 35):
        cv.set(gx, 2, GOLD[5])
        cv.set(gx, 10, GOLD[1])
    return cv.img


def paint_dmg_icon(kind):
    pats = {
        'crit': ['#...#...#', '.#..#..#.', '..#.#.#..', '...###...', '#########', '...###...', '..#.#.#..',
                 '.#..#..#.', '#...#...#'],
        'evade': ['..####...', '.#....#..', '#..##..#.', '#.#..#.#.', '#.#.##.#.', '#..#...#.', '.#....#..',
                  '..####...', '.........'],
        'block': ['#########', '#+++++++#', '#+++++++#', '#+++++++#', '.#+++++#.', '.#+++++#.', '..#+++#..',
                  '...#+#...', '....#....'],
        'heal': ['...###...', '...#+#...', '...#+#...', '####+####', '#+++++++#', '####+####', '...#+#...',
                 '...#+#...', '...###...'],
    }
    cols = {'crit': ((255, 220, 80), (255, 120, 30)), 'evade': ((200, 220, 255), (120, 160, 230)),
            'block': ((220, 220, 235), (110, 140, 200)), 'heal': ((40, 120, 50), (120, 240, 120))}
    cv = Canvas(9, 9)
    a, b = cols[kind]
    cv.pattern(0, 0, pats[kind], {'#': a, '+': b})
    return cv.img


# ───────────────────────────── dispatch by file ─────────────────────────────
DIGIT_SYMS = [str(d) for d in range(10)] + ['slash', 'plus', 'minus', 'k', 'M', 'dot', 'colon']


def paint_file(path, content):
    """Return the painted image for a glyph file (relative to textures/font/ui/), or None."""
    if path == 'gui/sock.png':
        return paint_socket_glyph('plain')
    if path == 'gui/sock_button.png':
        return paint_socket_glyph('button')
    m = re.fullmatch(r'gui/emblem_([a-z_]+)\.png', path)
    if m and m.group(1) in EMBLEMS:
        return paint_emblem_glyph(m.group(1))
    m = re.fullmatch(r'gui/([a-z0-9_]+)\.png', path)
    if m:
        return paint_gui(m.group(1), content)
    m = re.fullmatch(r'hud/cast_(\d\d)\.png', path)
    if m:
        return paint_cast(int(m.group(1)))
    m = re.fullmatch(r'hud/(hp|mp|shield)_(\d\d)\.png', path)
    if m:
        return paint_bar(m.group(1), int(m.group(2)))
    m = re.fullmatch(r'hud/xp_(\d\d)\.png', path)
    if m:
        return paint_xp(int(m.group(1)))
    if path == 'hud/level_badge.png':
        return paint_badge()
    if path == 'hud/gold.png':
        return paint_coin()
    m = re.fullmatch(r'hud/digit_([a-z0-9]+)\.png', path)
    if m:
        # 리소스 경로는 소문자만 허용 — 대문자 기호는 별칭 파일명으로 (mega → 'M')
        sym = {'mega': 'M'}.get(m.group(1), m.group(1))
        if sym in FONT45:
            return paint_digit(sym)
    m = re.fullmatch(r'status/([a-z_]+)\.png', path)
    if m and m.group(1) in SYMBOLS:
        return paint_status(m.group(1), m.group(1).startswith('buff_') or m.group(1) == 'stealth')
    m = re.fullmatch(r'party/hp_(\d\d)\.png', path)
    if m:
        return paint_party_bar(int(m.group(1)))
    m = re.fullmatch(r'party/class_([a-z_]+)\.png', path)
    if m:
        classes = (content.get('classes') or {}).get('classes') or {}
        col = ((classes.get(m.group(1)) or {}).get('color')) or '#c8c8d0'
        return paint_class_icon(m.group(1), col)
    m = re.fullmatch(r'dmg/(dmg|crit)_([A-Za-z0-9]+)\.png', path)
    if m and m.group(2) in FONT45:
        return paint_digit(m.group(2), scale=2, style=m.group(1))
    m = re.fullmatch(r'dmg/icon_([a-z]+)\.png', path)
    if m:
        return paint_dmg_icon(m.group(1))
    if path == 'boss/ornament_left.png':
        return paint_boss_ornament('left')
    if path == 'boss/ornament_right.png':
        return paint_boss_ornament('right')
    if path == 'boss/frame.png':
        return paint_boss_frame()
    return None


def glyph_advance(img):
    """Client advance of a bitmap glyph at scale 1: rightmost column with alpha != 0, + 2 (0-width → 1)."""
    a = img.getchannel('A')
    bbox = a.getbbox()
    if not bbox:
        return 1
    return bbox[2] + 1


# ───────────────────────────── font assembly ─────────────────────────────
def build(glyphs_doc: dict, content: dict):
    """Returns (files: {path: bytes}, warnings, errors, info) for font labyrinth:ui."""
    files, warnings, errors = {}, [], []
    info = {'glyphs': {}, 'images': {}}
    glyphs = (glyphs_doc or {}).get('glyphs') or {}
    spaces = (glyphs_doc or {}).get('spaces') or {}
    providers = []
    painted = {}
    seen_chars = {}
    for gid, g in glyphs.items():
        g = g or {}
        ch, f = g.get('char'), g.get('file')
        asc, hgt = g.get('ascent'), g.get('height')
        if not isinstance(ch, str) or len(ch) != 1:
            errors.append(f'glyph {gid}: char must be exactly one code point')
            continue
        cp = ord(ch)
        if not (0xE000 <= cp <= 0xF3FF):
            errors.append(f'glyph {gid}: char U+{cp:04X} outside U+E000..U+F3FF (U+F400..U+F8FF are spaces)')
        if ch in seen_chars:
            errors.append(f'glyph {gid}: char U+{cp:04X} also used by {seen_chars[ch]}')
        seen_chars[ch] = gid
        if not isinstance(asc, int) or not isinstance(hgt, int):
            errors.append(f'glyph {gid}: ascent/height must be integers')
            continue
        if asc > hgt:
            errors.append(f'glyph {gid}: ascent {asc} > height {hgt} (client rejects the font)')
        if f not in painted:
            img = paint_file(f, content)
            if img is None:
                errors.append(f'glyph {gid}: no painter for file {f!r}')
                continue
            painted[f] = img
        img = painted[f]
        if img.size[1] > hgt:
            errors.append(f'glyph {gid}: painted image is {img.size[1]} px tall > height {hgt}')
            continue
        if img.size[1] < hgt:   # lift above the line: pad transparent rows at the bottom
            key = f'{f}@{hgt}'
            if key not in painted:
                n = Image.new('RGBA', (img.size[0], hgt), (0, 0, 0, 0))
                n.alpha_composite(img, (0, 0))
                painted[key] = n
            img = painted[key]
            fname = f[:-4] + f'_h{hgt}.png'
        else:
            fname = f
        adv = glyph_advance(img)
        want = g.get('advance')
        if want is not None and want != adv:
            errors.append(f'glyph {gid}: advance {want} in glyphs.yml but the PNG gives {adv}')
        tex_path = f'assets/{NS}/textures/{FONT_TEX_DIR}/{fname}'
        if tex_path not in files:
            files[tex_path] = _png(img)
        providers.append({'type': 'bitmap', 'file': f'{NS}:{FONT_TEX_DIR}/{fname}', 'ascent': asc, 'height': hgt,
                          'chars': [ch]})
        info['glyphs'][gid] = {'char': ch, 'ascent': asc, 'height': hgt, 'advance': adv, 'image': img}
    adv_map = {}
    for sid, v in spaces.items():
        if not isinstance(v, int) or not (-1024 <= v <= 255) or v == 0:
            errors.append(f'space {sid}: value {v!r} must be a non-zero int in -1024..255')
            continue
        adv_map[chr(SPACE_BASE + v)] = v
    vals = set(adv_map.values())
    if 1 not in vals or -1 not in vals:
        errors.append('spaces must include 1 and -1 (Glyphs.space composes any offset from them)')
    providers.insert(0, {'type': 'space', 'advances': dict(sorted(adv_map.items()))})
    files[f'assets/{NS}/font/ui.json'] = (json.dumps({'providers': providers}, ensure_ascii=True, indent=1) + '\n'
                                          ).encode('utf-8')
    info['spaces'] = sorted(vals)
    return files, warnings, errors, info


def _png(img):
    b = io.BytesIO()
    img.save(b, 'PNG', optimize=True)
    return b.getvalue()


# ───────────────────────────── preview ─────────────────────────────
def _grid_overlay(img, rows):
    """2x preview with the real slot grid (cyan) — container rows, player inventory and hotbar."""
    s = 2
    big = img.resize((img.size[0] * s, img.size[1] * s), Image.NEAREST).convert('RGBA')
    ov = Image.new('RGBA', big.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cells = [(8 + 18 * c, 18 + 18 * r) for r in range(rows) for c in range(9)]
    cells += [(8 + 18 * c, rows * 18 + 31 + 18 * r) for r in range(3) for c in range(9)]
    cells += [(8 + 18 * c, rows * 18 + 89) for c in range(9)]
    for (x, y) in cells:
        d.rectangle([x * s, y * s, (x + 16) * s - 1, (y + 16) * s - 1], outline=(0, 255, 255, 110))
    d.text((8 * s, 6 * s), 'Title text', fill=(240, 228, 200, 255))
    d.text((8 * s, (img.size[1] - 94) * s), 'Inventory', fill=(64, 64, 64, 255))
    big.alpha_composite(ov)
    return big


def hud_mock(info, layout):
    """Simulate the action-bar composition on a 320x120 'screen' bottom to check vertical/horizontal placement."""
    W, H = 320, 110
    scr = Image.new('RGBA', (W, H), (70, 96, 60, 255))
    d = ImageDraw.Draw(scr)
    for y in range(H):
        for x in range(W):
            if h2(x // 4, y // 4, 5) > 0.7:
                scr.putpixel((x, y), (62, 88, 54, 255))
    cx = W // 2
    # vanilla HUD stand-ins (outlines only — positions from the client): hotbar, hearts row, food row, xp bar
    d.rectangle([cx - 91, H - 22, cx + 90, H - 1], outline=(30, 30, 30, 255), fill=(50, 50, 50, 255))
    d.rectangle([cx - 91, H - 29, cx + 90, H - 25], fill=(40, 60, 30, 255))
    for k in range(10):
        d.rectangle([cx - 91 + k * 8, H - 39, cx - 91 + k * 8 + 8, H - 31], outline=(120, 30, 30, 255))
        d.rectangle([cx + 82 - k * 8, H - 39, cx + 82 - k * 8 + 8, H - 31], outline=(120, 90, 30, 255))
    text_y = H - 72
    x0 = cx - layout['total'] // 2
    g = info['glyphs']

    def put(gid, x):
        gi = g[gid]
        top = text_y + 7 - gi['ascent']
        scr.alpha_composite(gi['image'], (x0 + x, top))

    def put_num(prefix, s, x):
        for ch in s:
            sym = {'/': 'slash', '+': 'plus', '-': 'minus', '.': 'dot', ':': 'colon'}.get(ch, ch)
            gid = prefix + sym
            put(gid, x)
            x += g[gid]['advance']
        return x

    def num_w(prefix, s):
        return sum(g[prefix + {'/': 'slash', '.': 'dot'}.get(ch, ch)]['advance'] for ch in s) - 1

    put('hud_xp_13', layout['xp_x'])
    put('hud_hp_14', layout['hp_x'])
    put('hud_mp_09', layout['mp_x'])
    put('hud_level_badge', layout['badge_x'])
    hp_s, mp_s = '842/1200', '210/460'
    put_num('hud_num_', hp_s, layout['hp_x'] + (BAR_W - num_w('hud_num_', hp_s)) // 2)
    put_num('hud_num_', mp_s, layout['mp_x'] + (BAR_W - num_w('hud_num_', mp_s)) // 2)
    put_num('hud_num_', '27', layout['badge_x'] + (18 - num_w('hud_num_', '27')) // 2)
    for k, sid in enumerate(['status_buff_damage', 'status_buff_shield', 'status_poison', 'status_frost']):
        put(sid, layout['status_x'] + k * g[sid]['advance'])
    gold_s = '12840'
    gw = g['hud_gold']['advance'] + num_w('gold_num_', gold_s)
    gx = layout['total'] - gw
    put('hud_gold', gx)
    put_num('gold_num_', gold_s, gx + g['hud_gold']['advance'])
    return scr.resize((W * 3, H * 3), Image.NEAREST)


def hud_mock_live(info, layout, vimgs, message='귀환 중  3.2초', cast_step=6, scale=1):
    """실제 화면 아래쪽 흉내 (1배): 테마 핫바 + 글리프 HUD + 액션바 문구(HUD 위) + 시전 막대.
    액션바 글줄 y = H − 72, 글리프 윗변 = 글줄 + 7 − ascent. 문구 글자는 PIL 글꼴(자리 확인용)."""
    W, H = 360, 96
    scr = Image.new('RGBA', (W, H), (70, 96, 60, 255))
    for y in range(H):
        for x in range(W):
            if h2(x // 4, y // 4, 5) > 0.7:
                scr.putpixel((x, y), (62, 88, 54, 255))
    cx = W // 2
    mc = 'assets/minecraft/textures/gui/sprites/hud/'
    if vimgs:
        scr.alpha_composite(vimgs[mc + 'hotbar_offhand_left.png'], (cx - 91 - 29, H - 23))
        scr.alpha_composite(vimgs[mc + 'hotbar.png'], (cx - 91, H - 22))
        scr.alpha_composite(vimgs[mc + 'hotbar_selection.png'], (cx - 91 - 1 + 20 * 0, H - 23))
    text_y = H - 72
    g = info['glyphs']
    x0 = cx - 91

    def put(gid, x):
        gi = g[gid]
        scr.alpha_composite(gi['image'], (x0 + x, text_y + 7 - gi['ascent']))

    def put_num(prefix, s_, x):
        for ch in s_:
            gid = prefix + {'/': 'slash', '.': 'dot', ':': 'colon'}.get(ch, ch)
            put(gid, x)
            x += g[gid]['advance']

    def num_w(prefix, s_):
        return sum(g[prefix + {'/': 'slash', '.': 'dot'}.get(ch, ch)]['advance'] for ch in s_) - 1

    put('hud_xp_13', layout['xp_x'])
    put('hud_hp_14', layout['hp_x'])
    put('hud_mp_09', layout['mp_x'])
    put('hud_level_badge', layout['badge_x'])
    for s_, bx in (('842/1200', layout['hp_x']), ('210/460', layout['mp_x'])):
        put_num('hud_num_', s_, bx + (BAR_W - num_w('hud_num_', s_)) // 2)
    put_num('hud_num_', '27', layout['badge_x'] + (18 - num_w('hud_num_', '27')) // 2)
    for k, sid in enumerate(['status_buff_damage', 'status_poison']):
        put(sid, layout['status_x'] + k * g[sid]['advance'])
    gw = g['hud_gold']['advance'] + num_w('gold_num_', '12840')
    put('hud_gold', layout['total'] - gw)
    put_num('gold_num_', '12840', layout['total'] - gw + g['hud_gold']['advance'])
    if cast_step is not None and f'cast_{cast_step:02d}' in g:
        cw = g[f'cast_{cast_step:02d}']['image'].size[0]
        put(f'cast_{cast_step:02d}', 91 - cw // 2)
    if message:
        d = ImageDraw.Draw(scr)
        try:
            from PIL import ImageFont
            font = ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', 9)
        except Exception:
            font = None
        tw = int(d.textlength(message, font=font)) if font else len(message) * 6
        d.text((cx - tw // 2 + 1, text_y + 1), message, fill=(40, 30, 50, 255), font=font)
        d.text((cx - tw // 2, text_y), message, fill=(201, 162, 255, 255), font=font)
    return scr.resize((W * scale, H * scale), Image.NEAREST)


def preview(info, gui_rows, layout, out_path):
    from .render import grid  # local import keeps module load light
    cells = []
    sheet_w = 2 * 176 + 16
    panels = []
    for gid, rows in gui_rows.items():
        if gid not in info['glyphs']:
            continue
        panels.append((_grid_overlay(info['glyphs'][gid]['image'], rows), gid))
    cols = 4
    ph = max(p.size[1] for p, _ in panels) + 18
    rows_n = (len(panels) + cols - 1) // cols
    mock = hud_mock(info, layout)
    small = [v['image'] for k, v in info['glyphs'].items() if not k.startswith('gui_')]
    strip_h = 0
    x = y = 0
    rowh = 0
    pos = []
    for im in small:
        w, h = im.size[0] * 3, im.size[1] * 3
        if x + w > cols * sheet_w - 8:
            x = 0
            y += rowh + 6
            rowh = 0
        pos.append((x, y))
        x += w + 6
        rowh = max(rowh, h)
    strip_h = y + rowh + 6
    W = cols * sheet_w
    H = 24 + rows_n * ph + mock.size[1] + 30 + strip_h + 30
    sheet = Image.new('RGBA', (W, H), (40, 42, 50, 255))
    d = ImageDraw.Draw(sheet)
    d.text((6, 6), f'Labyrinth UI: {len(panels)} GUI backgrounds (2x, cyan = real slot grid), HUD mock, '
                   f'{len(small)} HUD/icon glyphs', fill=(235, 235, 235, 255))
    for k, (p, label) in enumerate(panels):
        cx, cy = (k % cols) * sheet_w + 8, 24 + (k // cols) * ph
        d.text((cx, cy), label, fill=(255, 220, 140, 255))
        sheet.alpha_composite(p, (cx, cy + 14))
    yb = 24 + rows_n * ph
    d.text((8, yb), 'HUD action bar mock (3x): composed exactly as glyphs.yml hud: describes — '
                    'grey boxes = vanilla hotbar/hearts/food positions', fill=(235, 235, 235, 255))
    sheet.alpha_composite(mock, (8, yb + 14))
    ys = yb + 14 + mock.size[1] + 16
    for im, (px, py) in zip(small, pos):
        sheet.alpha_composite(im.resize((im.size[0] * 3, im.size[1] * 3), Image.NEAREST), (8 + px, ys + py))
    sheet.convert('RGB').save(out_path)
    return grid  # silence linters (grid is optional)
