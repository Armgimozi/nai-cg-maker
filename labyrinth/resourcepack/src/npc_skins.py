"""NPC skins: original 64×64 player-skin-layout textures (`textures/entity/npc/<skin>.png`) painted
procedurally from npcs.yml `skin_style` (GDD §14.5): palette = [skin, hair, outfit main, outfit secondary,
metal/ornament, eyes], `outfit`, `hair`, `accessories`.

Layout = the standard 64×64 two-layer player skin (classic 4-px arms). The plugin shows these on a
`Mannequin` through `ResolvableProfile` SkinPatch body = `labyrinth:entity/npc/<skin>` (ARCHITECTURE §2).
Every pixel is painted here; nothing is derived from vanilla or third-party skins.
"""
from __future__ import annotations

from PIL import Image

from .util import Palette, clamp8, darken, h2, hex2rgb, hue_shift, lighten, lum, mix, saturate, stable_seed

# part: (base uv, outer uv, w, h, d)
BOXES = {
    'head': ((0, 0), (32, 0), 8, 8, 8),
    'body': ((16, 16), (16, 32), 8, 12, 4),
    'rarm': ((40, 16), (40, 32), 4, 12, 4),
    'larm': ((32, 48), (48, 48), 4, 12, 4),
    'rleg': ((0, 16), (0, 32), 4, 12, 4),
    'lleg': ((16, 48), (0, 48), 4, 12, 4),
}
SIDES = ('right', 'front', 'left', 'back')
ALL = ('top', 'bottom') + SIDES

OUTFITS = ('robe', 'apron', 'coat', 'scholar', 'traveler', 'miner', 'uniform', 'armor')
HAIRS = ('long_braid', 'short_beard', 'silver_ponytail', 'messy_short', 'curly_short', 'short_bob', 'long_straight',
         'twin_buns', 'bun', 'bald_mustache', 'short_messy', 'none')


def face_rect(part, face, layer=0):
    (bu, bv), (ou, ov), w, h, d = BOXES[part]
    u, v = (bu, bv) if layer == 0 else (ou, ov)
    return {
        'top': (u + d, v, w, d), 'bottom': (u + d + w, v, w, d), 'right': (u, v + d, d, h),
        'front': (u + d, v + d, w, h), 'left': (u + d + w, v + d, d, h), 'back': (u + 2 * d + w, v + d, w, h),
    }[face]


class Skin:
    def __init__(self, sid, style):
        self.sid = sid
        style = style or {}
        raw = list(style.get('palette') or [])
        while len(raw) < 6:
            raw.append(['#e0b090', '#3a2a20', '#40506a', '#a0a0b0', '#c8a060', '#304060'][len(raw)])
        cols = [hex2rgb(c) for c in raw[:6]]
        self.skin, self.hair, self.main, self.second, self.metal, self.eye = cols
        self.outfit = style.get('outfit') if style.get('outfit') in OUTFITS else 'traveler'
        self.hairstyle = style.get('hair') if style.get('hair') in HAIRS else 'messy_short'
        self.acc = set(style.get('accessories') or [])
        self.seed = stable_seed('npc', sid) & 0xFFFF
        self.img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        self.px = self.img.load()
        self.leather = mix((104, 66, 38), self.second, 0.15)
        self.boot = darken(mix((70, 46, 30), self.main, 0.15), 0.25)
        self.pants = darken(mix(self.main, (58, 56, 66), 0.55), 0.25)
        self.white = (236, 232, 222)
        self.warnings = []

    # ── raw access
    def put(self, layer, part, face, x, y, c):
        x0, y0, w, h = face_rect(part, face, layer)
        if 0 <= x < w and 0 <= y < h:
            self.px[x0 + x, y0 + y] = (0, 0, 0, 0) if c is None else (c[0], c[1], c[2], c[3] if len(c) > 3 else 255)

    def get(self, layer, part, face, x, y):
        x0, y0, w, h = face_rect(part, face, layer)
        if 0 <= x < w and 0 <= y < h:
            return self.px[x0 + x, y0 + y]
        return None

    def fill(self, layer, part, faces, fn):
        for f in faces:
            x0, y0, w, h = face_rect(part, f, layer)
            for y in range(h):
                for x in range(w):
                    c = fn(f, x, y, w, h)
                    if c is not False:
                        self.put(layer, part, f, x, y, c)

    def band(self, layer, part, y0, y1, c, faces=SIDES):
        self.fill(layer, part, faces, lambda f, x, y, w, h: c if y0 <= y <= y1 else False)

    def solid(self, layer, part, c, faces=ALL):
        self.fill(layer, part, faces, lambda f, x, y, w, h: c)

    # ── painting passes
    def paint(self):
        sk = self.skin
        for p in BOXES:
            self.solid(0, p, sk)
        self.outfit_pass()
        self.face_pass()
        self.hair_pass()
        self.accessory_pass()
        self.shade_pass()
        return self.img

    def outfit_pass(self):
        o = self.outfit
        M, S, MT, L, B, P = self.main, self.second, self.metal, self.leather, self.boot, self.pants
        dM = darken(M, 0.3)
        legs = ('rleg', 'lleg')
        arms = ('rarm', 'larm')
        if o == 'robe':
            self.solid(0, 'body', M, ALL)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: S if (y <= 1 and 2 <= x <= 5) or x in (3, 4) and y <= 7 else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: self.skin if y == 0 and x in (3, 4) else False)
            self.band(0, 'body', 7, 8, S)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if y in (7, 8) and x in (3, 4) else False)
            for a in arms:
                self.solid(0, a, M, ('top',) + SIDES)
                self.band(0, a, 11, 11, self.skin)
                self.band(1, a, 8, 10, S)
                self.band(1, a, 0, 7, False if False else M)
                self.fill(1, a, ('bottom',), lambda f, x, y, w, h: None)
            for lg in legs:
                self.solid(0, lg, M, ('top',) + SIDES)
                self.band(0, lg, 9, 10, S)
                self.band(0, lg, 11, 11, B)
                self.solid(0, lg, B, ('bottom',))
                self.band(1, lg, 0, 9, dM, faces=('front', 'right', 'left', 'back'))
            self.band(1, 'body', 9, 11, M)
        elif o == 'apron':
            self.solid(0, 'body', S, ALL)
            for a in arms:
                self.solid(0, a, S, ('top',) + SIDES)
                self.band(0, a, 5, 5, darken(S, 0.2))
                self.band(0, a, 6, 11, self.skin)
            for lg in legs:
                self.solid(0, lg, P, ALL)
                self.band(0, lg, 10, 11, B)
                self.solid(0, lg, B, ('bottom',))
            ap = M
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: ap if 1 <= x <= 6 and y >= 2 else (ap if x in (1, 6) else False))
            self.fill(0, 'body', ('back',), lambda f, x, y, w, h: ap if x in (1, 6) or y == 8 else False)
            self.band(0, 'body', 8, 8, darken(ap, 0.25), faces=('right', 'left'))
            for lg in legs:
                self.fill(1, lg, ('front',), lambda f, x, y, w, h: ap if y <= 7 else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: darken(ap, 0.25) if 3 <= x <= 4 and 6 <= y <= 8 else False)
        elif o in ('coat', 'scholar'):
            inner = S if o == 'coat' else darken(S, 0.1)
            self.solid(0, 'body', M, ALL)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: inner if 3 <= x <= 4 or (o == 'scholar' and 2 <= x <= 5 and y >= 1) else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if (o == 'coat' and x in (2, 5) and y in (3, 6, 9)) or
                      (o == 'scholar' and x in (3, 4) and y in (3, 5, 7)) else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: lighten(inner, 0.2) if y == 0 and 2 <= x <= 5 else False)
            for a in arms:
                self.solid(0, a, M, ('top',) + SIDES)
                self.band(0, a, 10, 10, S if o == 'coat' else MT)
                self.band(0, a, 11, 11, self.skin)
            for lg in legs:
                self.solid(0, lg, P, ALL)
                self.band(0, lg, 10, 11, B)
                self.solid(0, lg, B, ('bottom',))
                if o == 'coat':
                    self.band(1, lg, 0, 6, M)
                    self.fill(1, lg, ('front',), lambda f, x, y, w, h: None if (lg == 'rleg' and x == 3) or (lg == 'lleg' and x == 0) else False)
            if o == 'coat':
                self.band(1, 'body', 8, 11, M)
                self.fill(1, 'body', ('front',), lambda f, x, y, w, h: None if 3 <= x <= 4 else False)
        elif o == 'traveler':
            self.solid(0, 'body', M, ALL)
            self.band(0, 'body', 8, 8, L)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if y == 8 and x in (3, 4) else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: darken(M, 0.25) if y <= 2 and x in (3, 4) and y > 0 else False)
            for a in arms:
                self.solid(0, a, S, ('top',) + SIDES)
                self.band(0, a, 9, 10, L)
                self.band(0, a, 11, 11, self.skin)
            for lg in legs:
                self.solid(0, lg, mix(L, P, 0.5), ALL)
                self.band(0, lg, 8, 11, B)
                self.band(1, lg, 7, 8, darken(B, 0.1) if False else lighten(B, 0.15))
                self.solid(0, lg, B, ('bottom',))
            self.band(1, 'body', 9, 11, M)
        elif o == 'miner':
            self.solid(0, 'body', S, ALL)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: M if (1 <= x <= 6 and y >= 4) or x in (1, 6) else False)
            self.fill(0, 'body', ('back',), lambda f, x, y, w, h: M if x in (1, 6) or y >= 6 else False)
            self.band(0, 'body', 7, 11, M, faces=('right', 'left'))
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if y == 4 and x in (1, 6) else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: darken(M, 0.25) if 3 <= x <= 4 and 5 <= y <= 7 else False)
            for a in arms:
                self.solid(0, a, S, ('top',) + SIDES)
                self.band(0, a, 6, 6, darken(S, 0.2))
                self.band(0, a, 7, 11, self.skin)
            for lg in legs:
                self.solid(0, lg, M, ALL)
                self.band(0, lg, 9, 11, B)
                self.solid(0, lg, B, ('bottom',))
        elif o == 'uniform':
            self.solid(0, 'body', M, ALL)
            self.band(0, 'body', 0, 0, S)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: S if x in (3, 4) and y <= 7 else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if x in (2, 5) and y in (2, 4, 6) else False)
            self.band(0, 'body', 8, 8, darken(L, 0.3))
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if y == 8 and x in (3, 4) else False)
            for a in arms:
                self.solid(0, a, M, ('top',) + SIDES)
                self.band(0, a, 9, 10, S)
                self.band(0, a, 11, 11, self.skin)
                self.fill(1, a, ('top',), lambda f, x, y, w, h: MT)
                self.band(1, a, 0, 0, MT)
            for lg in legs:
                self.solid(0, lg, darken(M, 0.2), ALL)
                self.fill(0, lg, ('right', 'left'), lambda f, x, y, w, h: S if x == 1 and y < 9 else False)
                self.band(0, lg, 9, 11, darken(B, 0.3))
                self.solid(0, lg, darken(B, 0.3), ('bottom',))
        elif o == 'armor':
            plate = mix(S, MT, 0.3)
            self.solid(0, 'body', plate, ALL)
            self.fill(0, 'body', ('front', 'back'), lambda f, x, y, w, h: M if 2 <= x <= 5 and y >= 2 else False)
            self.fill(0, 'body', ('front',), lambda f, x, y, w, h: MT if y == 1 or (y == 7 and 2 <= x <= 5) else False)
            self.band(0, 'body', 8, 8, darken(plate, 0.35))
            self.band(1, 'body', 0, 1, lighten(plate, 0.1))
            self.band(1, 'body', 9, 11, M)
            self.fill(1, 'body', ('front', 'back'), lambda f, x, y, w, h: None if y >= 9 and x in (0, 7) else False)
            for a in arms:
                self.solid(0, a, plate, ALL)
                self.band(0, a, 4, 4, darken(plate, 0.3))
                self.band(0, a, 9, 11, darken(plate, 0.15))
                self.band(1, a, 0, 3, lighten(plate, 0.12))
                self.fill(1, a, ('top',), lambda f, x, y, w, h: lighten(plate, 0.18))
            for lg in legs:
                self.solid(0, lg, darken(plate, 0.1), ALL)
                self.band(0, lg, 5, 5, darken(plate, 0.35))
                self.band(0, lg, 10, 11, darken(plate, 0.3))
                self.fill(1, lg, ('front',), lambda f, x, y, w, h: MT if y == 5 and 1 <= x <= 2 else False)

    def face_pass(self):
        sk, e = self.skin, self.eye
        f = 'front'
        brow = darken(self.hair, 0.15) if self.hairstyle != 'none' else darken(sk, 0.3)
        for x, c in ((1, self.white), (2, e), (5, e), (6, self.white)):
            self.put(0, 'head', f, x, 4, c)
        self.put(0, 'head', f, 2, 4, darken(e, 0.1))
        for x in (1, 2, 5, 6):
            self.put(0, 'head', f, x, 3, brow)
        self.put(0, 'head', f, 3, 5, darken(sk, 0.12))
        self.put(0, 'head', f, 4, 5, darken(sk, 0.08))
        mouth = mix(darken(sk, 0.35), (150, 60, 60), 0.35)
        self.put(0, 'head', f, 3, 6, mouth)
        self.put(0, 'head', f, 4, 6, mouth)
        # ears (sides)
        for side in ('right', 'left'):
            self.put(0, 'head', side, 4 if side == 'right' else 3, 4, darken(sk, 0.15))
        # neck shadow under the chin (body top)
        self.fill(0, 'body', ('top',), lambda f_, x, y, w, h: darken(sk, 0.2) if 2 <= x <= 5 and y <= 2 else False)

    def hair_pass(self):
        hs = self.hairstyle
        H = self.hair
        hl = lighten(H, 0.18)
        hd = darken(H, 0.25)

        def tex(x, y):
            n = h2(x, y // 2, self.seed)
            if n > 0.86:
                return hl
            if n < 0.1:
                return hd
            return mix(H, hl, 0.25) if (x + (y // 3)) % 3 == 0 else H
        if hs == 'none':
            if self.outfit == 'armor':
                hel = mix(self.second, self.metal, 0.45)
                self.solid(1, 'head', hel, ('top', 'right', 'left', 'back'))
                self.fill(1, 'head', ('front',), lambda f, x, y, w, h: hel if y <= 2 or y >= 6 or x in (0, 7) else
                          (None if y in (3, 4, 5) else False))
                self.fill(1, 'head', ('front',), lambda f, x, y, w, h: darken(hel, 0.4) if y == 4 and 1 <= x <= 6 else False)
                self.fill(1, 'head', ('front',), lambda f, x, y, w, h: lighten(self.eye, 0.3) if y == 4 and x in (2, 5) else False)
                self.fill(1, 'head', ('bottom',), lambda f, x, y, w, h: None)
            return
        if hs == 'bald_mustache':
            self.fill(0, 'head', ('top',), lambda f, x, y, w, h: lighten(self.skin, 0.12) if (x + y) % 5 == 0 else False)
            for s in ('right', 'left', 'back'):
                self.fill(0, 'head', (s,), lambda f, x, y, w, h: tex(x, y) if 2 <= y <= 4 else False)
            for x in range(1, 7):
                self.put(0, 'head', 'front', x, 5 if x in (2, 5) else 6 if x in (1, 6) else 5, H)
            self.put(0, 'head', 'front', 3, 6, darken(self.skin, 0.35))
            self.put(0, 'head', 'front', 4, 6, darken(self.skin, 0.35))
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: H if y == 5 and 2 <= x <= 5 else False)
            return
        # base hair cap
        self.fill(0, 'head', ('top',), lambda f, x, y, w, h: tex(x, y))
        long_ = hs in ('long_braid', 'long_straight', 'silver_ponytail', 'short_bob')
        side_rows = 7 if hs in ('long_straight', 'long_braid') else 5 if hs == 'short_bob' else 3
        back_rows = 7 if long_ or hs in ('bun', 'twin_buns') else 5
        for s in ('right', 'left'):
            self.fill(0, 'head', (s,), lambda f, x, y, w, h: tex(x, y) if y <= side_rows and not (y >= 3 and
                      ((s == 'right' and x >= 5) or (s == 'left' and x <= 2)) and side_rows < 6) else False)
        self.fill(0, 'head', ('back',), lambda f, x, y, w, h: tex(x, y) if y <= back_rows else False)
        # fringe
        if hs in ('messy_short', 'short_messy', 'curly_short'):
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: tex(x, y) if y == 0 or (y == 1 and h2(x, 1, self.seed) > 0.35)
                      or (y == 2 and x in (0, 7)) else False)
            self.fill(1, 'head', ('top',), lambda f, x, y, w, h: tex(x + 9, y) if h2(x, y, self.seed + 4) > 0.55 else False)
            self.fill(1, 'head', ('front',), lambda f, x, y, w, h: tex(x, y + 3) if y == 0 and h2(x, 0, self.seed + 5) > 0.4 else False)
            if hs == 'curly_short':
                self.fill(1, 'head', ('right', 'left', 'back'), lambda f, x, y, w, h: (hl if (x + y) % 2 else H) if y <= 2 else False)
        elif hs == 'short_bob':
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: tex(x, y) if y <= 1 or (x in (0, 7) and y <= 5) else False)
            self.fill(1, 'head', ('right', 'left', 'back'), lambda f, x, y, w, h: tex(x, y) if 3 <= y <= 5 else False)
        elif hs in ('long_straight', 'long_braid', 'silver_ponytail'):
            part_x = 3 if hs != 'long_braid' else 4
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: tex(x, y) if (y == 0) or (y == 1 and x != part_x) or
                      (x in (0, 7) and y <= (6 if hs == 'long_straight' else 3)) else False)
            if hs == 'long_straight':
                self.fill(1, 'head', ('back', 'right', 'left'), lambda f, x, y, w, h: tex(x, y) if y >= 4 else False)
                self.fill(1, 'body', ('back',), lambda f, x, y, w, h: tex(x, y) if y <= 4 and 1 <= x <= 6 else False)
            if hs == 'long_braid':
                self.fill(1, 'body', ('back',), lambda f, x, y, w, h: ((hl if (y % 2 == 0) == (x == 3) else hd)
                          if x in (3, 4) and y <= 9 else (self.metal if x in (3, 4) and y == 10 else False)))
                self.fill(1, 'head', ('back',), lambda f, x, y, w, h: tex(x, y) if x in (3, 4) and y >= 5 else False)
            if hs == 'silver_ponytail':
                self.fill(1, 'head', ('back',), lambda f, x, y, w, h: (self.metal if y == 3 and x in (3, 4) else
                          tex(x, y) if x in (3, 4) and y >= 2 else False))
                self.fill(1, 'body', ('back',), lambda f, x, y, w, h: tex(x, y) if x in (3, 4) and y <= 5 else False)
        elif hs in ('bun', 'twin_buns'):
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: tex(x, y) if y == 0 or (y == 1 and x not in (3, 4)) else False)
            if hs == 'bun':
                self.fill(1, 'head', ('back',), lambda f, x, y, w, h: tex(x, y) if 2 <= x <= 5 and y <= 2 else False)
                self.fill(1, 'head', ('top',), lambda f, x, y, w, h: tex(x, y) if 2 <= x <= 5 and y >= 6 else False)
                self.put(1, 'head', 'back', 3, 3, self.metal)
            else:
                for (xs, side) in (((0, 1), 'right'), ((6, 7), 'left')):
                    self.fill(1, 'head', ('top',), lambda f, x, y, w, h: tex(x, y) if x in xs and 2 <= y <= 4 else False)
                    self.fill(1, 'head', (side,), lambda f, x, y, w, h: tex(x, y) if 2 <= x <= 4 and y <= 1 else False)
        elif hs == 'short_beard':
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: tex(x, y) if y == 0 or (y == 1 and x in (0, 1, 6, 7)) else False)
            beard = darken(H, 0.05)
            self.fill(0, 'head', ('front',), lambda f, x, y, w, h: tex(x, y + 10) if (y == 7) or (y == 6 and x not in (3, 4)) or
                      (y == 5 and x in (0, 1, 6, 7)) else False)
            self.fill(0, 'head', ('right', 'left'), lambda f, x, y, w, h: beard if y >= 5 and ((f == 'right' and x >= 4) or
                      (f == 'left' and x <= 3)) else False)
            self.fill(1, 'head', ('front',), lambda f, x, y, w, h: tex(x, y) if y == 7 and 2 <= x <= 5 else False)
            self.fill(1, 'head', ('bottom',), lambda f, x, y, w, h: tex(x, y) if y <= 3 and 1 <= x <= 6 else False)

    def accessory_pass(self):
        A = self.acc
        M, S, MT, L = self.main, self.second, self.metal, self.leather
        glow = lighten(saturate(self.eye, 1.3), 0.35)
        if 'hood_down' in A:
            self.fill(1, 'body', ('back',), lambda f, x, y, w, h: (darken(S, 0.15) if y == 2 else S) if y <= 2 else False)
            self.fill(1, 'head', ('back',), lambda f, x, y, w, h: S if y >= 6 else False)
            self.band(1, 'body', 0, 0, S, faces=('right', 'left', 'front'))
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: None if y == 0 and 2 <= x <= 5 else False)
        if 'shoulder_cape' in A or 'rain_cape' in A or 'torn_cape' in A:
            cape = S if 'rain_cape' not in A else mix(S, (60, 90, 110), 0.3)
            if 'torn_cape' in A:
                cape = darken(M, 0.2)
            self.fill(1, 'body', ('back',), lambda f, x, y, w, h: (None if 'torn_cape' in A and y >= 9 and h2(x, y, self.seed) > 0.5
                      else (lighten(cape, 0.15) if x in (0, 7) else cape)) if y <= 11 else False)
            self.band(1, 'body', 0, 1, cape, faces=('right', 'left'))
            for a in ('rarm', 'larm'):
                self.fill(1, a, ('top',), lambda f, x, y, w, h: cape)
                self.band(1, a, 0, 1, cape)
            if 'rain_cape' in A:
                self.fill(1, 'body', ('back',), lambda f, x, y, w, h: lighten(cape, 0.35) if (x + y * 2) % 7 == 0 else False)
        if 'scarf' in A:
            self.band(1, 'body', 0, 1, S)
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: (darken(S, 0.2) if y % 2 else S) if x in (1, 2) and y <= 5 else False)
            self.band(1, 'head', 7, 7, S, faces=('right', 'left', 'back', 'front'))
            self.fill(1, 'head', ('front',), lambda f, x, y, w, h: None if y == 7 and 2 <= x <= 5 else False)
        if 'medal_sash' in A:
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: S if abs((7 - x) - y * 0.7) < 0.9 and y <= 9 else False)
            self.put(1, 'body', 'front', 4, 3, MT)
            self.put(1, 'body', 'front', 5, 3, lighten(MT, 0.3))
        if 'satchel' in A or 'map_case' in A:
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: darken(L, 0.2) if abs(x - y * 0.65) < 0.7 else False)
            self.fill(1, 'body', ('back',), lambda f, x, y, w, h: darken(L, 0.2) if abs((7 - x) - y * 0.65) < 0.7 else False)
            if 'satchel' in A:
                self.fill(1, 'body', ('left',), lambda f, x, y, w, h: (L if y < 11 else darken(L, 0.3)) if y >= 7 else False)
                self.put(1, 'body', 'left', 1, 8, MT)
            if 'map_case' in A:
                self.fill(1, 'body', ('back',), lambda f, x, y, w, h: (S if (x + y) % 3 else MT) if abs((7 - x) - y * 0.65 + 1.5) < 0.8 else False)
        if 'big_backpack' in A:
            self.fill(1, 'body', ('back',), lambda f, x, y, w, h: (darken(L, 0.25) if y in (1, 10) or x in (0, 7) else
                      (MT if y == 5 and x in (3, 4) else L)) if 1 <= y <= 10 else False)
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: darken(L, 0.3) if x in (1, 6) and y <= 6 else False)
            self.fill(1, 'body', ('top',), lambda f, x, y, w, h: S if y >= 2 else False)
        if 'coin_pouch' in A:
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: (MT if (x, y) == (6, 9) else L) if 5 <= x <= 7 and 8 <= y <= 10 else False)
        if 'lantern_belt' in A:
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: (glow if (x, y) == (1, 9) else MT) if 0 <= x <= 2 and 8 <= y <= 10 else False)
        if 'key_ring' in A:
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: MT if (x, y) in ((5, 8), (6, 9), (5, 10), (6, 10), (7, 11)) else False)
        if 'tool_belt' in A:
            self.band(1, 'body', 8, 9, L)
            self.fill(1, 'body', ('front', 'right', 'left'), lambda f, x, y, w, h: (MT if (x + f.__len__()) % 3 == 0 else False) if y in (9, 10) else False)
        if 'scroll_bundle' in A:
            self.fill(1, 'body', ('back',), lambda f, x, y, w, h: ((236, 226, 196) if (y % 3) else (196, 176, 136)) if 2 <= x <= 5 and 2 <= y <= 8 else False)
        if 'crystal_pendant' in A:
            self.fill(1, 'body', ('front',), lambda f, x, y, w, h: MT if (y == 0 and x in (1, 6)) or (y == 1 and x in (2, 5)) or (y == 2 and x in (3, 4)) else False)
            self.put(1, 'body', 'front', 3, 3, glow)
            self.put(1, 'body', 'front', 4, 3, lighten(glow, 0.4))
        if 'tuning_fork' in A:
            self.fill(1, 'body', ('right',), lambda f, x, y, w, h: MT if (x in (1, 3) and 3 <= y <= 6) or (y == 7 and 1 <= x <= 3) or (x == 2 and y >= 7) else False)
        if 'thick_gloves' in A:
            for a in ('rarm', 'larm'):
                self.band(1, a, 8, 11, L)
                self.band(1, a, 8, 8, darken(L, 0.3))
        if 'bandage_arm' in A:
            self.fill(1, 'larm', SIDES, lambda f, x, y, w, h: self.white if y % 3 == 1 and 2 <= y <= 9 else False)
        if 'mechanical_arm' in A:
            arm = mix(MT, (120, 124, 132), 0.4)
            self.solid(0, 'rarm', arm, ALL)
            self.band(0, 'rarm', 4, 4, darken(MT, 0.35))
            self.band(0, 'rarm', 8, 8, darken(MT, 0.35))
            self.fill(0, 'rarm', ('front',), lambda f, x, y, w, h: lighten(arm, 0.3) if (x + y) % 4 == 0 else False)
            self.fill(0, 'rarm', SIDES, lambda f, x, y, w, h: glow if y == 6 and x == 1 else False)
        if 'ink_stains' in A or 'soot_marks' in A:
            stain = (24, 30, 58) if 'ink_stains' in A else (40, 36, 34)
            for p, faces in (('rarm', SIDES), ('larm', SIDES), ('body', ('front',))):
                self.fill(0, p, faces, lambda f, x, y, w, h: mix(stain, self.get(0, p, f, x, y)[:3], 0.3)
                          if h2(x + len(f) * 7, y + len(p) * 13, self.seed + 9) > 0.86 else False)
            if 'soot_marks' in A:
                self.put(0, 'head', 'front', 1, 6, darken(self.skin, 0.4))
                self.put(0, 'head', 'front', 6, 5, darken(self.skin, 0.35))
        if 'goggles_forehead' in A:
            strap = darken(L, 0.35)
            self.band(1, 'head', 1, 1, strap, faces=('right', 'left', 'back', 'front'))
            for x in (1, 2, 5, 6):
                self.put(1, 'head', 'front', x, 1, mix(MT, (120, 200, 220), 0.5) if x in (2, 5) else MT)
                self.put(1, 'head', 'front', x, 2, darken(MT, 0.3))
        if 'helmet_lamp' in A:
            hel = mix((200, 160, 60), S, 0.3)
            self.solid(1, 'head', hel, ('top',))
            self.band(1, 'head', 0, 1, hel, faces=('right', 'left', 'back', 'front'))
            self.put(1, 'head', 'front', 3, 1, glow)
            self.put(1, 'head', 'front', 4, 1, lighten(glow, 0.5))
        if 'round_glasses' in A or 'monocle' in A:
            eyes = (1, 2, 5, 6) if 'round_glasses' in A else (5, 6)
            for x in range(0, 8):
                if 'round_glasses' in A or x >= 4:
                    if x in eyes:
                        self.put(1, 'head', 'front', x, 3, MT)
                        self.put(1, 'head', 'front', x, 5, MT)
            for x in ((0, 3, 4, 7) if 'round_glasses' in A else (4, 7)):
                self.put(1, 'head', 'front', x, 4, MT)
            if 'monocle' in A:
                self.put(1, 'body', 'front', 6, 0, MT)
        if 'quill_ear' in A:
            self.fill(1, 'head', ('right',), lambda f, x, y, w, h: ((250, 250, 246) if x == 3 or (x == 2 and y % 2) else False) if 0 <= y <= 5 else False)
        if 'broken_crown' in A:
            crown = MT
            self.band(1, 'head', 0, 0, crown, faces=('right', 'left', 'back', 'front'))
            self.fill(1, 'head', ('front', 'back', 'right', 'left'), lambda f, x, y, w, h: (None if f == 'left' and x >= 5 else crown) if y == 0 else False)
            self.fill(1, 'head', ('top',), lambda f, x, y, w, h: crown if (x in (0, 7) or y in (0, 7)) and not (x >= 5 and y >= 5) else False)
        if 'ghostly' in A:
            # pale, cold, desaturated + spectral wisps on the outer leg layer
            for yy in range(64):
                for xx in range(64):
                    c = self.px[xx, yy]
                    if c[3]:
                        g = mix(saturate((c[0], c[1], c[2]), 0.7), (196, 226, 255), 0.18)
                        self.px[xx, yy] = (g[0], g[1], g[2], c[3])
            for lg in ('rleg', 'lleg'):
                self.fill(1, lg, SIDES, lambda f, x, y, w, h: (210, 236, 255) if y >= 8 and h2(x, y, self.seed + len(f)) > 0.6 else False)
        if 'frost_cracks' in A:
            for p in ('body', 'head', 'rarm', 'larm'):
                self.fill(0, p, SIDES, lambda f, x, y, w, h: (220, 244, 255) if (x * 3 + y * 5 + len(f)) % 11 == 0 and h2(x, y, 3) > 0.4 else False)
        if 'sculk_scars' in A:
            teal = (47, 224, 208)
            self.put(0, 'head', 'front', 6, 5, teal)
            self.put(0, 'head', 'front', 6, 6, darken(teal, 0.2))
            self.put(0, 'head', 'front', 5, 7, darken(teal, 0.3))
            self.fill(0, 'larm', SIDES, lambda f, x, y, w, h: teal if (x + y) % 5 == 0 and 3 <= y <= 9 else False)

    def shade_pass(self):
        """Pixel-art shading: top-lit gradient, side darkening, cloth/hair noise (both layers)."""
        for part in BOXES:
            for layer in (0, 1):
                for f in ALL:
                    x0, y0, w, h = face_rect(part, f, layer)
                    for y in range(h):
                        for x in range(w):
                            c = self.px[x0 + x, y0 + y]
                            if c[3] == 0:
                                continue
                            k = 0.0
                            if f in SIDES:
                                k += (0.5 - y / max(1, h - 1)) * (0.10 if part != 'head' else 0.05)
                                if f in ('right', 'left'):
                                    k -= 0.05
                                if f == 'back':
                                    k -= 0.03
                            elif f == 'top':
                                k += 0.06
                            else:
                                k -= 0.12
                            k += (h2(x0 + x, y0 + y, self.seed) - 0.5) * 0.07
                            rgb = (c[0], c[1], c[2])
                            rgb = lighten(rgb, k) if k > 0 else darken(rgb, -k)
                            self.px[x0 + x, y0 + y] = (rgb[0], rgb[1], rgb[2], c[3])
        # base layer must be fully opaque (only the outer layer may have holes)
        for part in BOXES:
            for f in ALL:
                x0, y0, w, h = face_rect(part, f, 0)
                for y in range(h):
                    for x in range(w):
                        c = self.px[x0 + x, y0 + y]
                        if c[3] != 255:
                            base = self.skin if c[3] == 0 else (c[0], c[1], c[2])
                            self.px[x0 + x, y0 + y] = (base[0], base[1], base[2], 255)


def paint_skin(sid, style):
    s = Skin(sid, style)
    return s.paint(), s.warnings


def preview_figure(img, scale=6):
    """Flat front + back view of a skin (base + outer layer) for the preview sheet."""
    W = 16 + 4 + 16
    out = Image.new('RGBA', (W, 32), (0, 0, 0, 0))

    def blit(part, face, layer, dx, dy):
        x0, y0, w, h = face_rect(part, face, layer)
        out.alpha_composite(img.crop((x0, y0, x0 + w, y0 + h)), (dx, dy))
    for view, ox in (('front', 0), ('back', 20)):
        for layer in (0, 1):
            blit('head', view, layer, ox + 4, 0)
            blit('body', view, layer, ox + 4, 8)
            if view == 'front':
                blit('rarm', 'front', layer, ox + 0, 8)
                blit('larm', 'front', layer, ox + 12, 8)
                blit('rleg', 'front', layer, ox + 4, 20)
                blit('lleg', 'front', layer, ox + 8, 20)
            else:
                blit('larm', 'back', layer, ox + 0, 8)
                blit('rarm', 'back', layer, ox + 12, 8)
                blit('lleg', 'back', layer, ox + 4, 20)
                blit('rleg', 'back', layer, ox + 8, 20)
    return out.resize((W * scale, 32 * scale), Image.NEAREST)
