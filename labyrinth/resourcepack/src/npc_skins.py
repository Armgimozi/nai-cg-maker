"""NPC skins: original 64×64 player-skin-layout textures (`textures/entity/npc/<skin>.png`) painted
procedurally from npcs.yml `skin_style` (GDD §14.5): palette = [skin, hair, outfit main, outfit secondary,
metal/ornament, eyes], `outfit`, `hair`, `accessories`.

Layout = the standard 64×64 two-layer player skin (classic 4-px arms). The plugin shows these on a
`Mannequin` through `ResolvableProfile` SkinPatch body = `labyrinth:entity/npc/<skin>` (ARCHITECTURE §2).
Every pixel is painted here; nothing is derived from vanilla or third-party skins.

How a skin is painted (all deterministic):
  1. outfit   — hand-drawn 8×12 templates for the torso front/back/sides per outfit (collars, plackets, lapels,
                belts, pockets, buttons, folds) + parametric sleeves, cuffs, hands, trousers and boots on the
                limbs; the outer layers (jacket / sleeves / pants) add depth: coat tails, apron skirt, bell
                sleeves, cuffs, pauldrons …
  2. hair     — per-style coverage masks for front / sides / back, vertical strands with a shine band and dark
                tips, volume and locks on the hat layer, style extras (braid, ponytail, buns, beard, moustache)
  3. face     — 3×2 eyes on face rows 3–4 (sclera, palette[5] iris, dark pupil, highlight) with a 2 px gap,
                brows shaped by expression (role / outfit), nose shadow, 2–3 px mouth, blush / freckles,
                forehead light and jaw shadow, ears on the head sides
  4. accessories (closed list, GDD §14.5) — each drawn as a recognisable object
  5. light    — material-aware form shading: top-lit gradient per part, darker sides and occluded inner faces,
                hue-shifted ramps (warm light, cool shadow), fabric/leather grain; eyes and glows unshaded
"""
from __future__ import annotations

from PIL import Image

from .util import darken, h2, hex2rgb, lighten, lum, mix, saturate, stable_seed

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
ARMS = ('rarm', 'larm')
LEGS = ('rleg', 'lleg')

OUTFITS = ('robe', 'apron', 'coat', 'scholar', 'traveler', 'miner', 'uniform', 'armor')
HAIRS = ('long_braid', 'short_beard', 'silver_ponytail', 'messy_short', 'curly_short', 'short_bob', 'long_straight',
         'twin_buns', 'bun', 'bald_mustache', 'short_messy', 'none')
ACCESSORIES = ('hood_down', 'lantern_belt', 'satchel', 'soot_marks', 'thick_gloves', 'goggles_forehead', 'shoulder_cape',
               'medal_sash', 'monocle', 'round_glasses', 'scroll_bundle', 'quill_ear', 'big_backpack', 'coin_pouch',
               'scarf', 'helmet_lamp', 'bandage_arm', 'map_case', 'key_ring', 'rain_cape', 'ghostly', 'frost_cracks',
               'broken_crown', 'tuning_fork', 'crystal_pendant', 'ink_stains', 'tool_belt', 'mechanical_arm',
               'torn_cape', 'sculk_scars')
EXPRESSIONS = ('kind', 'stern', 'noble', 'gentle', 'cheerful', 'weary', 'earnest', 'sad', 'serene')
ROLE_EXPRESSION = {'entrance': 'kind', 'blacksmith': 'stern', 'class_master': 'noble', 'title_keeper': 'gentle',
                   'merchant': 'cheerful'}
OUTFIT_EXPRESSION = {'robe': 'serene', 'apron': 'earnest', 'coat': 'noble', 'scholar': 'gentle', 'traveler': 'earnest',
                     'miner': 'weary', 'uniform': 'earnest', 'armor': 'stern'}

NOSHADE = ('eye', 'glow', 'gem')
WARM = (255, 247, 226)
COOL = (26, 20, 50)


def sh(c, k):
    """One pixel-art ramp step per unit of k: k > 0 → toward a warm light, k < 0 → toward a cool, darker shadow."""
    c = (c[0], c[1], c[2])
    if k >= 0:
        return mix(c, mix(c, WARM, 0.8), min(1.0, 0.24 * k))
    return mix(c, mix(darken(c, 0.62), COOL, 0.4), min(1.0, 0.3 * -k))


def face_rect(part, face, layer=0):
    (bu, bv), (ou, ov), w, h, d = BOXES[part]
    u, v = (bu, bv) if layer == 0 else (ou, ov)
    return {
        'top': (u + d, v, w, d), 'bottom': (u + d + w, v, w, d), 'right': (u, v + d, d, h),
        'front': (u + d, v + d, w, h), 'left': (u + d + w, v + d, d, h), 'back': (u + 2 * d + w, v + d, w, h),
    }[face]


def canon(part, face, x):
    """Limb faces in right-limb orientation: front x0 = outer … x3 = inner; back x0 = inner … x3 = outer;
    'out' (outer side) x3 = front edge; 'in' (side toward the body) x0 = front edge."""
    if part in ('rarm', 'rleg'):
        return {'front': 'front', 'back': 'back', 'right': 'out', 'left': 'in'}.get(face, face), x
    return {'front': 'front', 'back': 'back', 'left': 'out', 'right': 'in'}.get(face, face), 3 - x


# ───────────────────────────── torso templates (8×12, figure's right on the left) ─────────────────────────────
# keys: M/N/m/n main (base/light/shadow/deep), S/T/s/z second, L/;/l/q leather (x = stitch), G/Y/g metal,
# K/k/J skin, W/w linen, P/Q/p trousers, A/a outfit accent, V/v vest, C/c mail, Z/z plate light/deep (armor),
# ' ' = leave as painted, '.' = transparent (outer layer only).  'side' = the right side face (x3 = front edge),
# mirrored for the left side; 'j…' = the same faces on the outer (jacket) layer.
TORSO = {
    'robe': {
        'front': ["MNTkkTNM",
                  "MMNTTmMM",
                  "MNNMTMMm",
                  "MNMMSMMm",
                  "MMMMSMmm",
                  "mMMMSMMm",
                  "mMMNSMmm",
                  "AAAAAYAa",
                  "aaaaagaa",
                  "MNMMSMmm",
                  "MMNmSNMm",
                  "mMmmSmMn"],
        'back': ["MNNNNNNM",
                 "MmmmmmmM",
                 "MNMMMMMm",
                 "MNMMMMMm",
                 "mMMMMMMm",
                 "mMMNMMMm",
                 "mMMMMMmm",
                 "AAAAAAAa",
                 "aaaaaaaa",
                 "MNMmMMNm",
                 "MMMmMNMm",
                 "mMmnmMmn"],
        'side': ["MMMM",
                 "mmmm",
                 "NMMM",
                 "NMMm",
                 "MMMm",
                 "MMMm",
                 "MMmm",
                 "AAAA",
                 "aaaa",
                 "NMMm",
                 "MMmm",
                 "mMmn"],
        'jfront': ["        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "     AA ",
                   "     aA ",
                   "     a  ",
                   "     aA ",
                   "      a "],
    },
    'apron': {
        'front': ["SLTkkTLS",
                  "SLsTTsLS",
                  "sGMMMMGs",
                  "sMNMMMms",
                  "sMNMMMms",
                  "sMMMMMms",
                  "sMMMMmms",
                  "lllllllq",
                  "sMMMMMms",
                  "sMxxxxms",
                  "sMllllms",
                  "sMMmmMms"],
        'back': ["SLSSSSLS",
                 "STLSSLTs",
                 "STSLLSTs",
                 "SSSLLSSs",
                 "STLSSLTs",
                 "SLSSSSLs",
                 "LSSSSSSl",
                 "lllllllq",
                 "ssslqsss",
                 "SSlTSlSs",
                 "STSSSSSs",
                 "sSSssSSs"],
        'side': ["SSSL",
                 "TSSL",
                 "TSSM",
                 "TSSM",
                 "SSsM",
                 "SSSM",
                 "SSsM",
                 "llll",
                 "SSsM",
                 "SSSM",
                 "SSsM",
                 "sSsm"],
        'jfront': ["        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "  Yg  g ",
                   "  ;   g ",
                   "        ",
                   "        ",
                   "        "],
    },
    'coat': {
        'front': ["nMTWWTMn",
                  "MNTwWTmM",
                  "MNMTTmMm",
                  "MNYMnYMm",
                  "MNMMnMMm",
                  "MMYMnYMm",
                  "MMMMnMMm",
                  "mmmmnmmm",
                  "MNMMnMMm",
                  "MNMpPMMm",
                  "MMmpPmMm",
                  "nmmpPmmn"],
        'back': ["nMMMMMMn",
                 "MNMMMMMm",
                 "MNMMmMMm",
                 "MNMMmMMm",
                 "MMMMmMMm",
                 "mMMMmMMm",
                 "mMMMmMMm",
                 "mmYmmYmm",
                 "MNMmnMMm",
                 "MNMmnMMm",
                 "MMmmnmMm",
                 "nmMmnMmn"],
        'side': ["MMMM",
                 "NMMM",
                 "NMMm",
                 "NMMm",
                 "MMMm",
                 "MMMm",
                 "MMMm",
                 "mmmm",
                 "NMMm",
                 "NMMm",
                 "MMmm",
                 "nMmn"],
        'jfront': [" mT  Tm ",
                   "  T  T  ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "MNM..MMm",
                   "MNM..MMm",
                   "MMm..mMm",
                   "nmm..mmn"],
        'jback': ["mMMMMMMm",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "MNMm.MMm",
                  "MNMm.MMm",
                  "MMmm.mMm",
                  "nmMm.Mmn"],
        'jside': ["mMMM",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "NMMm",
                  "NMMm",
                  "MMmm",
                  "nMmn"],
    },
    'scholar': {
        'front': ["MTWkkWTM",
                  "MSWAAWSm",
                  "MSVaaVSm",
                  "MSVYVVSm",
                  "MSVVvVSm",
                  "MSVYVVSm",
                  "MSVVvVSm",
                  "MSvVVvSm",
                  "MSppppSm",
                  "MSpPPpSm",
                  "MSpPPpSm",
                  "nSppppSn"],
        'back': ["MNNNNNNM",
                 "mmmmmmmm",
                 "MNMmMMmM",
                 "MNMmMMmM",
                 "MMMmMMmM",
                 "mMMmMMmm",
                 "mMMmMMmm",
                 "mMMmMMmm",
                 "mMMmMMmm",
                 "mMMmMMmm",
                 "mMMmNMmm",
                 "nmmnmmnn"],
        'side': ["MMMM",
                 "mmmm",
                 "NMMm",
                 "NMMm",
                 "MMMm",
                 "MMMm",
                 "MMmm",
                 "MMMm",
                 "MMMm",
                 "MMmm",
                 "MMmm",
                 "nmmn"],
        'jfront': ["MS    Sm",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "MS    Sm",
                   "MS    Sm",
                   "MS    Sm",
                   "nS    Sn"],
        'jback': ["        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "mMMmMMmm",
                  "mMMmMMmm",
                  "mMMmNMmm",
                  "nmmnmmnn"],
        'jside': ["    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "MMMm",
                  "MMmm",
                  "MMmm",
                  "nmmn"],
    },
    'traveler': {
        'front': ["MNTkkTmM",
                  "MNNqkmmM",
                  "MNNkqmmM",
                  "MNGSTGmM",
                  "MNNTsmmM",
                  "MMGSSGmM",
                  "mMNsSmmm",
                  "LLLYGLLl",
                  "lllggllq",
                  "MNMTSmMm",
                  "MMMSsmMm",
                  "nmmssmmn"],
        'back': ["MNNNNNNM",
                 "MNMMMMMm",
                 "MNMmMMMm",
                 "MMMmMMMm",
                 "mMMmMMMm",
                 "mMMmMMMm",
                 "mMMmMMmm",
                 "LLLLLLLl",
                 "llllllll",
                 "MNMmMMMm",
                 "MMMmMNMm",
                 "nmMnnMmn"],
        'side': ["MMMM",
                 "NMMM",
                 "NMMm",
                 "MMMm",
                 "MMMm",
                 "MMMm",
                 "MMmm",
                 "LLLL",
                 "llll",
                 "NMMm",
                 "MMmm",
                 "nMmn"],
        'jfront': ["        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "        ",
                   "MNM..mMm",
                   "MMM..mMm",
                   "nmm..mmn"],
        'jback': ["        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "        ",
                  "MNMmMMMm",
                  "MMMmMNMm",
                  "nmMnnMmn"],
        'jside': ["    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "    ",
                  "NMMm",
                  "MMmm",
                  "nMmn"],
    },
    'miner': {
        'front': ["SMTkkTMS",
                  "SMsTTsMS",
                  "SMSssSMS",
                  "sGNMMmGs",
                  "sMNllmMs",
                  "sMNqqmMs",
                  "sMMMMmMs",
                  "sMMMMmMs",
                  "MMNMMmMm",
                  "MNMMMMmm",
                  "MMMmMMmm",
                  "nMMnnMMn"],
        'back': ["SMSSSSMS",
                 "STMSSMTs",
                 "STSMMSTs",
                 "SSSMMSSs",
                 "STMMMMTs",
                 "SMMMMMMs",
                 "MMMMMMMm",
                 "MNMMMMMm",
                 "MNMmmMMm",
                 "MMMmmMMm",
                 "MMMmmMMm",
                 "nmMnnMmn"],
        'side': ["SSSM",
                 "TSSM",
                 "TSSM",
                 "TSsM",
                 "TSSM",
                 "TSGM",
                 "TSMM",
                 "NMMm",
                 "NMMm",
                 "MMMm",
                 "MMmm",
                 "nMmn"],
    },
    'uniform': {
        'front': ["nMSSSSMn",
                  "MNMSSMmM",
                  "MNYMMYmM",
                  "MNMMMMmM",
                  "MNYMMYmM",
                  "MMMMMMmM",
                  "MMYMMYmM",
                  "mMMMMMmm",
                  "qqqYGqqq",
                  "MNMSSMmM",
                  "MMMSSMmM",
                  "nmmSSmmn"],
        'back': ["nMSSSSMn",
                 "MNMMMMMM",
                 "MNmMMmMm",
                 "MNmMMmMm",
                 "MMmMMmMm",
                 "MMmMMmMm",
                 "mMmMMmMm",
                 "mMmMMmmm",
                 "qqYqqYqq",
                 "MNmMMmMm",
                 "MMmMMmMm",
                 "nmmnnmmn"],
        'side': ["SMMM",
                 "NMMM",
                 "NMMm",
                 "NMMm",
                 "MMMm",
                 "MMMm",
                 "MMMm",
                 "MMmm",
                 "qqqq",
                 "NMMm",
                 "MMmm",
                 "nMmn"],
    },
    'armor': {
        'front': ["aGGGGGGa",
                  "aAAZaAAa",
                  "AZAZaAZa",
                  "AZAZaAAa",
                  "aAAZaAAa",
                  "GaaZaaaG",
                  "aAAZaAAa",
                  "LLLYGLLl",
                  "AaMMMMaz",
                  "aaMGGMaa",
                  "AaMYYMaz",
                  "zaMmmMaz"],
        'back': ["aGGGGGGa",
                 "aAAZaAAa",
                 "AZAZaAZa",
                 "aZAZaAZa",
                 "aAAZaAAa",
                 "aaaZaaaa",
                 "aAAZaAAa",
                 "LLLLLLLl",
                 "AaMMMMaz",
                 "aaMNMMaa",
                 "AaMNMMaz",
                 "zaMmmMaz"],
        'side': ["aGGa",
                 "ZAAa",
                 "ZAAa",
                 "ZAAa",
                 "aAAa",
                 "aaaa",
                 "ZAAa",
                 "LLLL",
                 "ZAAz",
                 "aaaa",
                 "ZAAz",
                 "zaaz"],
    },
}


class Skin:
    def __init__(self, sid, style, role=None):
        self.sid = sid
        self.role = role or ''
        self.warnings = []
        style = style or {}
        defaults = ['#e0b090', '#3a2a20', '#40506a', '#a0a0b0', '#c8a060', '#304060']
        raw = list(style.get('palette') or [])
        while len(raw) < 6:
            raw.append(defaults[len(raw)])
        cols = []
        for i, c in enumerate(raw[:6]):
            try:
                cols.append(hex2rgb(str(c)))
            except ValueError:
                self.warnings.append(f'npc skin {sid}: bad palette colour {c!r} → {defaults[i]}')
                cols.append(hex2rgb(defaults[i]))
        self.skin, self.hair, self.main, self.second, self.metal, self.eye = cols
        o, hs = style.get('outfit'), style.get('hair')
        if o not in OUTFITS:
            self.warnings.append(f'npc skin {sid}: unknown outfit {o!r} → traveler')
            o = 'traveler'
        if hs not in HAIRS:
            self.warnings.append(f'npc skin {sid}: unknown hair {hs!r} → messy_short')
            hs = 'messy_short'
        self.outfit, self.hairstyle = o, hs
        self.acc = set()
        for a in style.get('accessories') or []:
            if a in ACCESSORIES:
                self.acc.add(a)
            else:
                self.warnings.append(f'npc skin {sid}: unknown accessory {a!r} (skipped)')
        self.seed = stable_seed('npc', sid) & 0xFFFF
        self.img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        self.px = self.img.load()
        self.mat = [[None] * 64 for _ in range(64)]
        self.hair_front = set()          # base-layer head-front texels covered by hair (the face pass keeps them)
        # derived colours (palette + shades only)
        self.leather = mix((118, 78, 48), self.second, 0.16)
        self.boot = mix((60, 42, 32), self.main, 0.14)
        self.sole = (36, 28, 26)
        self.linen = mix((240, 234, 218), self.second, 0.12)
        self.pants = mix(sh(self.main, -1.3), (62, 60, 70), 0.45)
        self.sclera = (248, 246, 240)
        self.glow = lighten(saturate(self.eye, 1.3), 0.35)
        self.expr = ROLE_EXPRESSION.get(self.role) or OUTFIT_EXPRESSION.get(self.outfit, 'kind')
        if 'ghostly' in self.acc:
            self.expr = 'sad'
        self.km = self._keymap()

    # ───────────────────────────── raw access
    def P(self, layer, part, face, x, y, c, m='cloth'):
        x0, y0, w, h = face_rect(part, face, layer)
        if 0 <= x < w and 0 <= y < h:
            if c is None:
                self.px[x0 + x, y0 + y] = (0, 0, 0, 0)
                self.mat[y0 + y][x0 + x] = None
            else:
                self.px[x0 + x, y0 + y] = (c[0], c[1], c[2], 255)
                self.mat[y0 + y][x0 + x] = m

    def G(self, layer, part, face, x, y):
        x0, y0, w, h = face_rect(part, face, layer)
        if 0 <= x < w and 0 <= y < h:
            c = self.px[x0 + x, y0 + y]
            return None if c[3] == 0 else (c[0], c[1], c[2])
        return None

    def Gm(self, layer, part, face, x, y):
        x0, y0, w, h = face_rect(part, face, layer)
        if 0 <= x < w and 0 <= y < h:
            return self.mat[y0 + y][x0 + x]
        return None

    def F(self, layer, part, faces, fn, m='cloth'):
        """fn(face, x, y, w, h) → colour | (colour, material) | None (clear) | False (keep)."""
        for f in faces:
            x0, y0, w, h = face_rect(part, f, layer)
            for y in range(h):
                for x in range(w):
                    c = fn(f, x, y, w, h)
                    if c is False:
                        continue
                    if c is not None and len(c) == 2:
                        self.P(layer, part, f, x, y, c[0], c[1])
                    else:
                        self.P(layer, part, f, x, y, c, m)

    def L(self, layer, parts, fn, faces=ALL, m='cloth'):
        """Limb fill in right-limb orientation: fn(cface, cx, y, part) (see canon())."""
        for p in parts:
            self.F(layer, p, faces, lambda f, x, y, w, h, p=p: fn(*canon(p, f, x), y, p), m)

    def tpl(self, layer, part, face, rows, mirror=False):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                xx = len(row) - 1 - x if mirror else x
                if ch == ' ':
                    continue
                if ch == '.':
                    self.P(layer, part, face, xx, y, None)
                    continue
                c, m = self.km[ch]
                self.P(layer, part, face, xx, y, c, m)

    def torso(self, t, layer=0):
        pre = '' if layer == 0 else 'j'
        if pre + 'front' in t:
            self.tpl(layer, 'body', 'front', t[pre + 'front'])
        if pre + 'back' in t:
            self.tpl(layer, 'body', 'back', t[pre + 'back'])
        if pre + 'side' in t:
            self.tpl(layer, 'body', 'right', t[pre + 'side'])
            self.tpl(layer, 'body', 'left', t[pre + 'side'], mirror=True)

    def _keymap(self):
        M, S, MT, Lh, sk = self.main, self.second, self.metal, self.leather, self.skin
        P, W, B = self.pants, self.linen, self.boot
        km = {
            'M': (M, 'cloth'), 'N': (sh(M, 1), 'cloth'), 'm': (sh(M, -1), 'cloth'), 'n': (sh(M, -2), 'cloth'),
            'S': (S, 'cloth'), 'T': (sh(S, 1), 'cloth'), 's': (sh(S, -1), 'cloth'), 'z': (sh(S, -2), 'cloth'),
            'L': (Lh, 'leather'), ';': (sh(Lh, 1.2), 'leather'), 'l': (sh(Lh, -1), 'leather'), 'q': (sh(Lh, -2), 'leather'),
            'x': (sh(Lh, 1.3), 'leather'),
            'G': (MT, 'metal'), 'Y': (sh(MT, 1.6), 'metal'), 'g': (sh(MT, -1.3), 'metal'),
            'K': (sk, 'skin'), 'k': (sh(sk, -0.9), 'skin'), 'J': (sh(sk, 0.5), 'skin'),
            'W': (W, 'cloth'), 'w': (sh(W, -1), 'cloth'),
            'P': (P, 'cloth'), 'Q': (sh(P, 1), 'cloth'), 'p': (sh(P, -1), 'cloth'),
            'B': (B, 'leather'), 'b': (sh(B, -1), 'leather'), '^': (sh(B, 1.3), 'leather'), 'O': (self.sole, 'leather'),
            'A': (sh(mix(S, M, 0.45), -0.2), 'cloth'), 'a': (sh(mix(S, M, 0.45), -1.2), 'cloth'),
            'V': (sh(mix(S, M, 0.55), -0.4), 'cloth'), 'v': (sh(mix(S, M, 0.55), -1.4), 'cloth'),
            'C': (mix((140, 144, 154), MT, 0.25), 'metal'), 'c': (sh(mix((140, 144, 154), MT, 0.25), -1.1), 'metal'),
        }
        o = self.outfit
        if o == 'apron':
            km.update({'M': (M, 'leather'), 'N': (sh(M, 1), 'leather'), 'm': (sh(M, -1), 'leather'),
                       'n': (sh(M, -2), 'leather'), 'x': (sh(M, 1.4), 'leather'),
                       'S': (sh(S, 0.6), 'cloth'), 'T': (sh(S, 1.5), 'cloth'), 's': (sh(S, -0.4), 'cloth')})
        elif o == 'robe':
            km.update({'A': (sh(mix(S, M, 0.5), -0.6), 'cloth'), 'a': (sh(mix(S, M, 0.5), -1.6), 'cloth')})
        elif o == 'scholar':
            ribbon = mix(self.eye, M, 0.25)
            km.update({'A': (sh(ribbon, 0.6), 'cloth'), 'a': (sh(ribbon, -0.8), 'cloth')})
        elif o == 'miner':
            km.update({'l': (sh(M, -1.3), 'cloth'), 'q': (sh(M, -2.2), 'cloth')})
        elif o == 'uniform':
            self.pants = sh(M, -0.9)
            km.update({'P': (self.pants, 'cloth'), 'Q': (sh(self.pants, 1), 'cloth'), 'p': (sh(self.pants, -1), 'cloth')})
        elif o == 'armor':
            plate = self.plate()
            km.update({'A': (plate, 'metal'), 'Z': (sh(plate, 1.6), 'metal'), 'a': (sh(plate, -1), 'metal'),
                       'z': (sh(plate, -2), 'metal'),
                       'G': (MT if lum(MT) < 0.85 else sh(MT, -0.5), 'metal'),
                       'R': (S, 'glow' if self._vivid(S) else 'cloth')})
        return km

    @staticmethod
    def _vivid(c):
        mx, mn = max(c), min(c)
        return mx > 160 and (mx - mn) > 120

    def plate(self):
        S = self.second
        base = S if not self._vivid(S) else mix(S, self.main, 0.55)
        return mix(saturate(base, 0.55), (150, 156, 168), 0.35)

    # ───────────────────────────── painting passes
    def paint(self):
        for p in BOXES:
            self.F(0, p, ALL, lambda f, x, y, w, h: self.skin, 'skin')
        getattr(self, 'outfit_' + self.outfit)()
        self.hair_pass()
        self.face_pass()
        self.accessory_pass()
        self.post_pass()
        self.light_pass()
        self.finish()
        return self.img

    # ── limb helpers
    def limb_cloth(self, layer, parts, col, y0, y1, folds='arm', faces=ALL, m='cloth'):
        """Cloth on limb rows y0..y1 with fold highlights/creases (light from the top, outer edge lit)."""

        def fn(cf, cx, y, p):
            if cf in ('top', 'bottom'):
                return (sh(col, 0.4 if cf == 'top' else -0.6), m) if cf == 'top' or y1 >= 11 else False
            if not (y0 <= y <= y1):
                return False
            k = 0.0
            edge_lit = (cf == 'front' and cx == 1) or (cf == 'out' and cx == 2) or (cf == 'back' and cx == 2)
            if edge_lit and y <= 8:
                k += 0.35
            if (cf == 'front' and cx == 3) or (cf == 'back' and cx == 0):
                k -= 0.45
            if folds == 'arm' and cf in ('front', 'out'):           # one clean crease at the elbow
                if (cx, y) in ((1, 5), (2, 6)):
                    k -= 0.7
                elif (cx, y) in ((1, 6), (2, 7)):
                    k += 0.3
            if folds == 'leg':
                if y == 5 and cf == 'front' and cx in (1, 2):       # knee
                    k += 0.5 if cx == 1 else -0.4
                if y == 9 and cf == 'front' and cx == 2:            # bunching above the boot
                    k -= 0.6
            if folds == 'robe' and cf == 'front' and cx == 3:
                k -= 0.4
            return (sh(col, k), m)
        self.L(layer, parts, fn, faces)

    def hands(self, rows=(10, 11), glove=None, parts=ARMS):
        sk = glove or self.skin
        m = 'skin' if glove is None else 'leather'

        def fn(cf, cx, y, p):
            if cf == 'bottom':
                return (sh(sk, -0.5), m)
            if cf == 'top' or y not in range(rows[0], 12):
                return False
            k = 0.0
            if y == rows[0] and rows[0] < 11:
                k -= 0.35                                     # cuff shadow on the wrist
            if cf == 'front' and y == 11 and cx == 3:
                k -= 0.8                                      # thumb gap
            if cf == 'front' and y == 11 and cx in (0, 1, 2) and glove is not None:
                k += 0.4 if cx % 2 == 0 else -0.3             # glove fingers
            if cf == 'in' and y == 11:
                k += 0.3                                      # thumb
            if cf == 'back' and y == 11 and cx % 2 == 1:
                k -= 0.35                                     # knuckles
            return (sh(sk, k), m)
        self.L(0, parts, fn)

    def cuff(self, layer, row0, row1, col, parts=ARMS, button=None, stitch=None, m='cloth'):
        def fn(cf, cx, y, p):
            if cf in ('top', 'bottom') or not (row0 <= y <= row1):
                return False
            k = 0.6 if y == row0 else (-0.6 if y == row1 else 0.0)
            if cf == 'front' and cx == 3:
                k -= 0.4
            if button is not None and cf == 'out' and cx == 1 and y == (row0 + row1) // 2:
                return (button, 'metal')
            if stitch is not None and y == row1 and (cx + (cf == 'back')) % 2 == 0:
                return (stitch, 'metal')
            return (sh(col, k), m)
        self.L(layer, parts, fn)

    def trousers(self, col, y0=0, y1=8, stripe=None, parts=LEGS):
        def fn(cf, cx, y, p):
            if cf == 'bottom' or (not (y0 <= y <= y1) and cf != 'top'):
                return False
            if cf == 'top':
                return (sh(col, -0.4), 'cloth')
            k = 0.0
            if cf == 'front' and cx == 1:
                k += 0.45                                     # crease catches the light
            if (cf == 'front' and cx == 3) or cf == 'in':
                k -= 0.5
            if y == 5 and cf == 'front':
                k += 0.4 if cx == 1 else (-0.4 if cx == 2 else 0)
            if y == y1 and cf == 'front' and cx == 2:
                k -= 0.6                                      # bunching over the boot
            if stripe is not None and cf == 'out' and cx in (1, 2):
                return (sh(stripe, 0.3 if cx == 2 else -0.2), 'cloth')
            return (sh(col, k), 'cloth')
        self.L(0, parts, fn)

    def boots(self, kind, top, parts=LEGS, col=None):
        """kind: work (laced, toe cap) | tall (riding, polished) | wrap (strapped traveller boots) |
        shoe (buckled shoes) | slipper (soft robe shoes) | plate (sabatons)."""
        B = col or self.boot
        MT, so = self.metal, self.sole

        def fn(cf, cx, y, p):
            if cf == 'bottom':
                return (so, 'leather')
            if cf == 'top' or y < top:
                return False
            k = 0.0
            if y == 11:
                return (so if kind != 'slipper' else sh(B, -1.2), 'leather')
            if cf == 'front' and cx == 1:
                k += 0.6                                      # polish / shin highlight
            if cf == 'in' or (cf == 'front' and cx == 3):
                k -= 0.45
            if kind == 'work':
                if y == top:
                    k += 0.8                                  # collar
                if cf == 'front' and top < y < 10 and cx in (1, 2):
                    return (sh(self.leather, 0.9 if (cx + y) % 2 else -0.3), 'leather')   # laces
                if y == 10 and cf == 'front':
                    k += 0.9                                  # toe cap
            elif kind == 'tall':
                if y == top:
                    return (sh(B, 1.2), 'leather')
                if y == top + 1:
                    k -= 0.5
                if cf == 'out' and cx == 2 and y in (top + 3, top + 4):
                    return ((sh(MT, 0.8) if y == top + 3 else MT), 'metal')            # buckle strap
                if y == 10 and cf == 'front':
                    k += 0.7
            elif kind == 'wrap':
                if (y - top) % 2 == 1 and y < 10:
                    return (sh(self.leather, -1.3 if cf in ('in', 'back') else -0.6), 'leather')   # straps
                if y == top:
                    k += 0.9
            elif kind == 'shoe':
                if cf == 'front' and y == 10 and cx in (1, 2):
                    return ((sh(MT, 1) if cx == 1 else MT), 'metal')                     # buckle
            elif kind == 'slipper':
                if y == top:
                    return (sh(self.second, 0.3), 'cloth')
            elif kind == 'plate':
                k += 0.8 if (y - top) % 2 == 0 else -0.6
                return (sh(B, k), 'metal')
            return (sh(B, k), 'leather')
        self.L(0, parts, fn)

    # ───────────────────────────── outfits
    def outfit_robe(self):
        t = TORSO['robe']
        self.torso(t)
        self.torso(t, 1)
        M, S, MT = self.main, self.second, self.metal
        self.limb_cloth(0, ARMS, M, 0, 9)
        self.cuff(0, 9, 9, S)
        self.hands((10, 11))

        def sleeve(cf, cx, y, p):                     # wide bell sleeve on the outer layer, trimmed cuff
            if cf == 'top':
                return (sh(M, 0.6), 'cloth')
            if cf == 'bottom':
                return None
            if not (5 <= y <= 10):
                return False
            if y >= 9:
                if y == 10 and (cx + (cf in ('front', 'out'))) % 2 == 0:
                    return (MT, 'metal')
                return (sh(S, 0.5 if y == 9 else -0.4), 'cloth')
            k = 0.5 if cx == 1 and cf in ('front', 'out') else (-0.5 if cx == 3 and cf == 'front' else 0)
            if y == 5:
                k += 0.3
            return (sh(M, k), 'cloth')
        self.L(1, ARMS, sleeve)
        # skirt over the legs: robe fabric to the hem, embroidered hem, soft shoes
        self.limb_cloth(0, LEGS, M, 0, 9, folds='robe')
        self.L(0, LEGS, lambda cf, cx, y, p: False if cf in ('top', 'bottom') or y != 10 else
               ((MT, 'metal') if (cx + (cf == 'back')) % 2 == 0 else (S, 'cloth')))
        self.L(0, LEGS, lambda cf, cx, y, p: (sh(S, -0.6), 'cloth') if cf not in ('top', 'bottom') and y == 9 else False)
        self.boots('slipper', 11, col=sh(self.leather, -0.5))

        def skirt(cf, cx, y, p):
            if cf in ('top', 'bottom') or y > 8:
                return False
            if cf == 'in' and y < 6:
                return False
            if y == 8:
                return (sh(S, 0.2), 'cloth')
            k = {'front': (0.15, 0.45, 0.0, -0.8), 'out': (-0.2, 0.0, 0.35, 0.15), 'back': (-0.5, 0.0, 0.3, 0.0),
                 'in': (-0.5, -0.5, -0.6, -0.6)}[cf][cx]
            if cf in ('front', 'out') and cx + y == 7:
                k -= 0.6                                     # one diagonal fold across each panel
            elif cf in ('front', 'out') and cx + y == 6:
                k += 0.3
            return (sh(M, k + (0.3 if y < 2 else 0)), 'cloth')
        self.L(1, LEGS, skirt)
        if 'hood_down' not in self.acc:                     # embroidered crest between the shoulder blades
            for (x, y, c, m) in ((3, 2, sh(MT, 1.2), 'metal'), (4, 2, MT, 'metal'), (2, 3, MT, 'metal'),
                                 (3, 3, sh(S, 0.4), 'cloth'), (4, 3, sh(S, 0.1), 'cloth'), (5, 3, sh(MT, -0.6), 'metal'),
                                 (3, 4, MT, 'metal'), (4, 4, sh(MT, -0.6), 'metal')):
                self.P(0, 'body', 'back', x, y, c, m)
        # the centre trim of the robe runs down the left leg panel
        for y in range(0, 9):
            self.P(1, 'lleg', 'front', 0, y, sh(S, 0.2 if y % 3 else -0.3), 'cloth')
            self.P(0, 'lleg', 'front', 0, y, sh(S, -0.2), 'cloth')
        self.P(1, 'lleg', 'front', 0, 4, MT, 'metal')

    def outfit_apron(self):
        t = TORSO['apron']
        self.torso(t)
        self.torso(t, 1)
        S, M = self.second, self.main
        # rolled sleeves: shirt to the elbow, rolled cuff, bare forearms
        self.limb_cloth(0, ARMS, S, 0, 3)
        self.cuff(0, 4, 5, sh(S, 0.4))
        self.hands((6, 11))
        if self.hairstyle in ('short_beard', 'bald_mustache'):
            self.L(0, ARMS, lambda cf, cx, y, p: (sh(self.skin, -0.7), 'skin')
                   if cf in ('front', 'out') and 6 <= y <= 9 and h2(cx * 7 + (cf == 'out'), y, self.seed + 3) > 0.72 else False)
        self.trousers(self.pants, 0, 8)
        self.boots('work', 8)

        def skirt(cf, cx, y, p):                         # leather apron over the thighs, stitched hem
            if cf in ('top', 'bottom') or y > 7:
                return False
            if cf == 'front' or (cf == 'out' and cx == 3) or (cf == 'in' and cx == 0 and y < 5):
                if y == 7:
                    return (sh(M, 1.0) if (cx % 2 == 0) else sh(M, -0.9), 'leather')
                k = 0.5 if (cf == 'front' and cx == 1) else (-0.6 if cf != 'front' or cx == 3 else 0)
                if y in (3, 4) and cf == 'front' and cx in (1, 2):
                    k += -0.7 if y == 4 else 0.2              # a crease where the apron bends at the knee
                return (sh(M, k), 'leather')
            return False
        self.L(1, LEGS, skirt)

    def outfit_coat(self):
        t = TORSO['coat']
        self.torso(t)
        self.torso(t, 1)
        M, S, MT = self.main, self.second, self.metal
        self.limb_cloth(0, ARMS, M, 0, 8)
        self.cuff(0, 8, 9, S, button=MT)
        self.hands((10, 11), glove=self.linen)
        self.trousers(sh(mix(M, (40, 40, 48), 0.5), -0.3), 0, 5)
        self.boots('tall', 5, col=mix((34, 28, 30), M, 0.12))

        def tails(cf, cx, y, p):                         # coat tails over the thighs, split at the front centre
            if cf in ('top', 'bottom') or y > 6:
                return False
            if cf == 'front' and cx == 3:
                return None
            if cf == 'in' and y < 6:
                return False
            if y == 6:
                return (sh(M, -1.2), 'cloth')
            k = 0.5 if (cf in ('front', 'out') and cx == 1) else (-0.5 if cx == 2 and cf == 'front' else 0)
            if cf == 'back' and cx == 0:
                k -= 0.8                                      # centre vent
            return (sh(M, k), 'cloth')
        self.L(1, LEGS, tails)

    def outfit_scholar(self):
        t = TORSO['scholar']
        self.torso(t)
        self.torso(t, 1)
        M, S = self.main, self.second
        self.limb_cloth(0, ARMS, M, 0, 9)
        self.hands((10, 11))

        def bell(cf, cx, y, p):                         # bell sleeves lined with the facing colour
            if cf == 'top':
                return (sh(M, 0.5), 'cloth')
            if cf == 'bottom':
                return (sh(S, -0.8), 'cloth')
            if not (4 <= y <= 9):
                return False
            if y == 9:
                return (sh(S, 0.3 if cf in ('front', 'out') else -0.5), 'cloth')
            k = 0.5 if cx == 1 and cf in ('front', 'out') else (-0.5 if (cf == 'front' and cx == 3) else 0)
            if y == 8:
                k -= 0.5
            return (sh(M, k), 'cloth')
        self.L(1, ARMS, bell)
        self.trousers(self.pants, 0, 9)
        self.boots('shoe', 10)

        def gown(cf, cx, y, p):
            if cf in ('top', 'bottom') or y > 8:
                return False
            if cf == 'front':
                if cx == 0:
                    return (sh(M, 0.3 - 0.1 * y / 8), 'cloth')
                if cx == 1:
                    return (sh(S, 0.2 if y < 8 else -0.5), 'cloth')
                return False
            if cf == 'in':
                return False
            k = 0.4 if cx == 1 else (-0.5 if cx == 3 else 0)
            if y == 8:
                k -= 0.7
            return (sh(M, k), 'cloth')
        self.L(1, LEGS, gown)

    def outfit_traveler(self):
        t = TORSO['traveler']
        self.torso(t)
        self.torso(t, 1)
        S, Lh = self.second, self.leather
        self.limb_cloth(0, ARMS, S, 0, 6)
        # laced leather bracers
        self.L(0, ARMS, lambda cf, cx, y, p: False if cf in ('top', 'bottom') or not (7 <= y <= 9) else
               ((sh(Lh, 2.0), 'leather') if cf == 'front' and (cx + y) % 2 == 0 and cx in (1, 2) else
                (sh(Lh, 0.6 if y == 7 else (-0.8 if y == 9 else 0)), 'leather')))
        self.hands((10, 11))
        self.trousers(mix(self.pants, Lh, 0.35), 0, 6)
        self.boots('wrap', 6, col=sh(Lh, -0.6))

        def cuffs(cf, cx, y, p):                        # folded boot tops stand out from the leg
            if cf in ('top', 'bottom') or y not in (6, 7):
                return False
            return (sh(Lh, 0.9 if y == 6 else -0.2), 'leather')
        self.L(1, LEGS, cuffs)

    def outfit_miner(self):
        t = TORSO['miner']
        self.torso(t)
        M, S, MT = self.main, self.second, self.metal
        self.limb_cloth(0, ARMS, S, 0, 3)
        self.cuff(0, 4, 4, sh(S, 0.5))
        self.hands((5, 11))
        self.limb_cloth(0, LEGS, M, 0, 9, folds='leg')

        def patch(cf, cx, y, p):                        # stitched knee patches, rolled cuffs
            if cf == 'front' and 4 <= y <= 6 and cx in (0, 1, 2):
                if y in (4, 6) or cx in (0, 2):
                    return (sh(S, 1.0) if (cx + y) % 2 == 0 else sh(S, -0.4), 'cloth')
                return (sh(S, -0.1), 'cloth')
            if cf not in ('top', 'bottom') and y == 8:
                return (sh(M, 1.0), 'cloth')
            return False
        self.L(0, LEGS, patch)
        self.boots('work', 9)
        self.L(0, LEGS, lambda cf, cx, y, p: ((sh(MT, 0.8) if cx == 1 else MT), 'metal')
               if cf == 'front' and y == 10 else False)
        # grime: a few deliberate smudges
        for (part, face, x, y) in (('body', 'front', 2, 9), ('body', 'front', 5, 10), ('rleg', 'front', 2, 2),
                                   ('lleg', 'front', 1, 7), ('body', 'back', 3, 10)):
            c = self.G(0, part, face, x, y)
            if c:
                self.P(0, part, face, x, y, sh(c, -1.2), 'cloth')

    def outfit_uniform(self):
        t = TORSO['uniform']
        self.torso(t)
        M, S, MT = self.main, self.second, self.metal
        self.limb_cloth(0, ARMS, M, 0, 9)
        self.cuff(0, 9, 9, S, button=MT)
        self.hands((10, 11))

        def boards(cf, cx, y, p):                       # shoulder boards with a fringe
            if cf == 'top':
                return (sh(S, 0.6), 'cloth') if cx in (1, 2) else (sh(MT, 0.4), 'metal')
            if cf == 'bottom' or y > 1:
                return False
            if y == 0:
                return (sh(MT, 0.5), 'metal')
            return (sh(MT, -0.6), 'metal') if (cx + (cf == 'back')) % 2 == 0 else None
        self.L(1, ARMS, boards)
        self.trousers(self.pants, 0, 8, stripe=S)
        self.boots('tall', 8, col=mix((28, 26, 30), M, 0.15))

    def outfit_armor(self):
        t = TORSO['armor']
        self.torso(t)
        plate = self.plate()
        MT = self.km['G'][0]

        def arm(cf, cx, y, p):
            if cf == 'top':
                return (sh(plate, 1.0), 'metal')
            if cf == 'bottom':
                return (sh(plate, -1.4), 'metal')
            if y <= 3:
                k = 1.2 if (cf in ('front', 'out') and cx == 1) else (0.3 if y == 0 else -0.2)
                return (sh(plate, k), 'metal')
            if y in (4, 5):
                return (self.mail(cx, y), 'metal')
            if y <= 9:
                if y == 6:
                    return (MT, 'metal')
                k = 1.4 if (cf in ('front', 'out') and cx == 1) else (-0.8 if cf == 'in' else 0)
                return (sh(plate, k), 'metal')
            k = 0.6 if y == 10 else -0.4
            if y == 11 and cf == 'front':
                k += 0.5 if cx % 2 == 0 else -0.5
            return (sh(plate, k - 0.3), 'metal')
        self.L(0, ARMS, arm)

        def pauldron(cf, cx, y, p):                     # layered lames over the shoulder
            if cf == 'top':
                return (sh(plate, 1.4) if cx in (1, 2) else sh(plate, 0.6), 'metal')
            if cf == 'bottom' or y > 3 or cf == 'in':
                return False
            if y == 3:
                return (MT, 'metal')
            if cf == 'out' and cx == 2 and y == 1:
                return (sh(MT, 1.2), 'metal')                 # rivet
            k = (1.0 - 0.5 * y) + (0.6 if cx == 1 else 0)
            return (sh(plate, k), 'metal')
        self.L(1, ARMS, pauldron)

        def leg(cf, cx, y, p):
            if cf == 'top':
                return (sh(plate, -0.6), 'metal')
            if cf == 'bottom':
                return (self.sole, 'leather')
            if cf == 'back' and y in (5, 6):
                return (self.mail(cx, y), 'metal')
            if y in (5, 6):
                return (sh(plate, 0.9 if y == 5 else -0.9), 'metal')
            if y == 11:
                return (sh(plate, -1.2), 'metal')
            k = 1.3 if (cf == 'front' and cx == 1) else (-0.7 if cf == 'in' or (cf == 'front' and cx == 3) else 0)
            if y == 10:
                k -= 0.3
            if y == 4 and cf in ('front', 'out'):
                k -= 0.6
            return (sh(plate, k), 'metal')
        self.L(0, LEGS, leg)

        def knee(cf, cx, y, p):                         # poleyn with a rivet, tasset lip at the hip
            if cf == 'front' and y in (4, 5, 6) and cx in (1, 2):
                if y == 5 and cx == 1:
                    return (sh(MT, 1.2), 'metal')
                return (sh(plate, 1.1 if y == 4 else (-0.5 if y == 6 else 0.4)), 'metal')
            if cf in ('front', 'out') and y == 0:
                return (MT, 'metal')
            return False
        self.L(1, LEGS, knee)
        # glowing seams for vivid accent colours (sculk knight)
        if self.km['R'][1] == 'glow':
            for (x, y) in ((3, 5), (4, 5), (2, 9), (5, 9)):
                self.P(0, 'body', 'front', x, y, sh(self.second, 0.4), 'glow')

    # ───────────────────────────── hair
    def hair_ramp(self):
        H = self.hair
        if lum(H) > 0.72:                                 # silver / white hair: ramp toward cool grey
            return {'shine': sh(H, 0.9), 'light': H, 'base': sh(H, -0.7), 'dark': sh(H, -1.6), 'deep': sh(H, -2.4)}
        return {'shine': sh(H, 1.6), 'light': sh(H, 0.8), 'base': H, 'dark': sh(H, -1.0), 'deep': sh(H, -1.9)}

    def lockmap(self, face):
        """Hair locks across one face: (lock id, position in lock, width) per column; widths 1–3, seeded."""
        key = 'lock_' + face
        if key not in self.__dict__:
            cols, lid, w = [], 0, 0
            salt = sum(ord(c) for c in face)
            for x in range(16):
                if w >= 3 or (w >= 2 and h2(x, salt, self.seed + 5) > 0.45) or (w == 1 and h2(x, salt, self.seed + 9) > 0.85):
                    lid, w = lid + 1, 0
                cols.append([lid, w])
                w += 1
            width = {}
            for lid, p in cols:
                width[lid] = max(width.get(lid, 0), p + 1)
            self.__dict__[key] = [(lid, p, width[lid]) for lid, p in cols]
        return self.__dict__[key]

    def hcol(self, fam, face, x, y, tip=False, hat=False):
        """Hair texel colour by style family: smooth / tousled / combed = locks of 1–3 px (lit first column, shaded
        last column, every third lock deeper) with a shine band near the crown; curly = jittered round curls;
        spiky = locks slanted across the face with hard contrast; dark tips where a lock ends."""
        R = self.R
        s = self.seed
        p, wd = 0, 1
        if fam == 'curly':
            row = y // 2
            ox = (row + (h2(x // 2, row, s + 2) > 0.7)) % 2
            cx = (x + ox) // 2
            k = (0.85, 0.05, 0.0, -0.85)[(x + ox) % 2 + 2 * (y % 2)] + (h2(cx, row, s + 4) - 0.5) * 0.6
        else:
            xs = x
            if fam == 'spiky':
                xs = x + y // 2 + 1
            elif fam == 'combed' and face in ('right', 'left'):
                xs = x + y // 3
            lid, p, wd = self.lockmap(face)[xs % 16]
            k = 0.35 if p == 0 else (-0.3 if p == wd - 1 and wd > 1 else 0.05)
            if fam == 'spiky':
                k *= 1.8
            if lid % 3 == 2:
                k -= 0.25
            if fam == 'tousled':
                k += (h2(x, y // 2, s + 11) - 0.5) * 0.7
        if face == 'top':
            k *= 0.7
            if 2 <= y <= 4 and fam != 'curly' and k > 0.1:
                k += 0.6
        else:
            k += 0.35 - 0.8 * y / 7.0                       # light from the top of the head
            if fam in ('smooth', 'combed') and y in (1, 2) and not (p == wd - 1 and wd > 1):
                k += 0.6                                    # shine band, broken at the lock partings
        if tip:
            k -= 0.8
        if hat:
            k += 0.3
        if k > 0.95:
            return R['shine']
        if k > 0.3:
            return R['light']
        if k < -1.0:
            return R['deep']
        if k < -0.3:
            return R['dark']
        return R['base']

    def hair_pass(self):
        hs = self.hairstyle
        self.R = R = self.hair_ramp()
        if hs == 'none':
            if self.outfit == 'armor':
                self.coif()
            else:
                self.F(0, 'head', ('top',), lambda f, x, y, w, h: (sh(self.skin, 0.8 if (x, y) in ((2, 3), (3, 3), (2, 4)) else 0.2), 'skin'))
            return
        spec = HAIR[hs]
        fam = spec['fam']

        def paint_mask(layer, face, mask, dist_faces=False):
            rows = [r.ljust(8) for r in mask] + [_E] * (8 - len(mask))
            faces = ('right', 'left') if dist_faces else (face,)
            for f in faces:
                for y in range(8):
                    for i in range(8):
                        if rows[y][i] != '#':
                            continue
                        x = (7 - i if f == 'right' else i) if dist_faces else i
                        tip = layer == 0 and (y == 7 or rows[y + 1][i] != '#')
                        self.P(layer, 'head', f, x, y, self.hcol(fam, f, x, y, tip, layer == 1), 'hair')
                        if layer == 0 and f == 'front':
                            self.hair_front.add((x, y))
        if hs == 'bald_mustache':
            self.F(0, 'head', ('top',), lambda f, x, y, w, h: (sh(self.skin, 1.0 if (x, y) in ((2, 2), (3, 2), (2, 3)) else 0.3), 'skin'))
        else:
            part = spec.get('part', 3)
            self.F(0, 'head', ('top',), lambda f, x, y, w, h: (R['deep'] if (x == part and y >= 3 and fam != 'curly')
                                                               else self.hcol(fam, 'top', x, y), 'hair'))
        paint_mask(0, 'front', spec.get('front', ()))
        paint_mask(0, None, spec.get('side', ()), dist_faces=True)
        paint_mask(0, 'back', spec.get('back', ()))
        paint_mask(1, 'front', spec.get('hat_front', ()))
        paint_mask(1, None, spec.get('hat_side', ()), dist_faces=True)
        paint_mask(1, 'back', spec.get('hat_back', ()))
        for y, row in enumerate(spec.get('hat_top', ())):
            for x, ch in enumerate(row):
                if ch == '#':
                    self.P(1, 'head', 'top', x, y, self.hcol(fam, 'top', x + 1, y, False, True), 'hair')
        extra = getattr(self, 'hair_' + hs, None)
        if extra:
            extra(R)

    def hair_long_braid(self, R):
        # braid down the back of the head and over the left shoulder onto the chest, tied with a ribbon
        rib = sh(self.second, 0.2)

        def braid(x, y):
            return R['light'] if (x + y) % 2 == 0 else R['dark']
        for y in range(3, 8):
            for x in (3, 4):
                self.P(1, 'head', 'back', x, y, braid(x, y), 'hair')
        for y in range(0, 3):
            for x in (3, 4):
                self.P(1, 'body', 'back', x, y, braid(x, y), 'hair')
        for y in range(0, 4):
            self.P(1, 'body', 'top', 6, y, R['base'], 'hair')
        for y in range(0, 6):
            for x in (6, 7):
                self.P(1, 'body', 'front', x, y, R['shine'] if (x + y) % 2 == 0 else R['dark'], 'hair')
        self.P(1, 'body', 'front', 6, 6, rib, 'cloth')
        self.P(1, 'body', 'front', 7, 6, sh(rib, -0.9), 'cloth')
        self.P(1, 'body', 'front', 6, 7, R['base'], 'hair')
        self.P(1, 'body', 'front', 7, 7, R['dark'], 'hair')
        self.P(1, 'body', 'left', 0, 0, R['dark'], 'hair')

    def hair_silver_ponytail(self, R):
        clasp = self.metal
        for y in range(2, 8):
            for x in (3, 4):
                self.P(1, 'head', 'back', x, y, R['light'] if (x == 3) == (y % 2 == 0) else R['base'], 'hair')
        self.P(1, 'head', 'back', 3, 3, sh(clasp, 1), 'metal')
        self.P(1, 'head', 'back', 4, 3, clasp, 'metal')
        for y in range(0, 6):
            for x in ((3, 4) if y < 4 else (3,) if y < 5 else (4,)):
                self.P(1, 'body', 'back', x, y, R['light'] if (x + y) % 3 == 0 else R['base'] if y < 4 else R['dark'], 'hair')

    def hair_long_straight(self, R):
        for y in range(0, 6):                                  # hair falling down the back
            for x in range(8):
                if (y == 5 and x in (0, 2, 5, 7)) or (y == 4 and x in (0, 7)):
                    continue
                c = self.hcol('smooth', 'back', x, y + 3, tip=(y == 5 or (y == 4 and x in (2, 5))))
                self.P(1, 'body', 'back', x, y, c, 'hair')
        for x in (0, 7):                                       # locks falling forward over the shoulders
            for y in range(0, 3):
                self.P(1, 'body', 'front', x, y, R['light'] if y == 0 else R['dark'] if y == 2 else R['base'], 'hair')

    def hair_twin_buns(self, R):
        tie = self.metal
        bun_top = {(1, 2): 'light', (0, 3): 'base', (1, 3): 'shine', (2, 3): 'light', (0, 4): 'dark', (1, 4): 'base',
                   (2, 4): 'base', (1, 5): 'dark'}
        for (x, y), k in bun_top.items():                  # two round buns high on the head, seen from above
            self.P(1, 'head', 'top', x, y, R[k], 'hair')
            self.P(1, 'head', 'top', 7 - x, y, R[k], 'hair')
        bun_side = {(3, 0): 'light', (4, 0): 'shine', (2, 1): 'base', (3, 1): 'light', (4, 1): 'base', (5, 1): 'dark',
                    (3, 2): 'dark', (4, 2): 'deep'}
        for f in ('right', 'left'):                        # dist from the front edge → x on each side face
            for (d, y), k in bun_side.items():
                x = 7 - d if f == 'right' else d
                self.P(1, 'head', f, x, y, R[k], 'hair')
            for d in (2, 5):
                x = 7 - d if f == 'right' else d
                self.P(1, 'head', f, x, 2, sh(tie, 0.6 if d == 2 else -0.4), 'metal')    # hair ties
        for (x, k) in ((0, 'base'), (1, 'light'), (6, 'light'), (7, 'base')):
            self.P(1, 'head', 'front', x, 0, R[k], 'hair')
        self.P(1, 'head', 'front', 0, 1, R['dark'], 'hair')
        self.P(1, 'head', 'front', 7, 1, R['dark'], 'hair')

    def hair_bun(self, R):
        for x in range(2, 6):
            for y in range(0, 3):
                c = R['shine'] if (x, y) == (3, 0) else R['light'] if y == 0 else R['dark'] if y == 2 else R['base']
                self.P(1, 'head', 'back', x, y, c, 'hair')
            for y in range(5, 8):
                self.P(1, 'head', 'top', x, y, R['light'] if y == 6 else R['base'], 'hair')
        pin = self.metal
        self.P(1, 'head', 'back', 1, 0, pin, 'metal')
        self.P(1, 'head', 'back', 6, 2, sh(pin, -0.8), 'metal')
        self.P(1, 'head', 'top', 1, 6, pin, 'metal')
        self.P(1, 'head', 'top', 6, 6, sh(pin, -0.8), 'metal')

    def hair_short_beard(self, R):
        beard = {'l': sh(self.hair, 0.5), 'b': sh(self.hair, -0.2), 'd': sh(self.hair, -1.1)}
        for (x, y, k) in BEARD_FRONT:
            self.P(0, 'head', 'front', x, y, beard[k], 'hair')
            self.hair_front.add((x, y))
        for f in ('right', 'left'):
            for x in range(8):
                dist = 7 - x if f == 'right' else x
                for y in range(5, 8):
                    if dist <= 2 + (y - 5):
                        self.P(0, 'head', f, x, y, beard['b'] if (x + y) % 2 else beard['d'], 'hair')
        self.F(0, 'head', ('bottom',), lambda f, x, y, w, h: (beard['d'] if (x + y) % 2 else beard['b'], 'hair') if y >= 3 else False)
        for x in range(1, 7):                               # chin volume on the hat layer
            self.P(1, 'head', 'front', x, 7, beard['l'] if x in (2, 5) else beard['b'], 'hair')
        self.F(1, 'head', ('bottom',), lambda f, x, y, w, h: (beard['d'], 'hair') if y >= 5 and 1 <= x <= 6 else False)

    def hair_bald_mustache(self, R):
        # big walrus moustache with curled tips; the mouth peeks out underneath
        mo = {'l': R['light'], 'b': R['base'], 'd': R['dark'], 's': R['shine']}
        for (x, y, k) in ((1, 5, 'd'), (2, 5, 'b'), (3, 5, 'l'), (4, 5, 's'), (5, 5, 'b'), (6, 5, 'd'),
                          (1, 6, 'b'), (2, 6, 'd'), (5, 6, 'd'), (6, 6, 'b')):
            self.P(0, 'head', 'front', x, y, mo[k], 'hair')
            self.hair_front.add((x, y))
        for (x, y, k) in ((0, 5, 'l'), (7, 5, 'l'), (0, 6, 'b'), (7, 6, 'b'), (2, 5, 'l'), (5, 5, 'l')):
            self.P(1, 'head', 'front', x, y, mo[k], 'hair')

    def mail(self, x, y):
        """Chainmail: staggered rows of rings (dark hole, lit ring edge) — reads as mail, not a checkerboard."""
        C = self.km['C'][0]
        p = (x + 2 * (y % 2)) % 4
        return sh(C, -1.1) if p == 0 else (sh(C, 0.6) if p == 2 else C)

    def coif(self):
        """Mail coif for a bare-headed knight: rows of rings over the crown, sides, back and around the face."""
        C = self.km['C'][0]
        ring = self.mail
        self.F(0, 'head', ('top', 'right', 'left', 'back'), lambda f, x, y, w, h: (ring(x, y), 'metal'))
        for x in range(8):
            for y in range(8):
                if y <= 1 or (x in (0, 7) and y >= 5) or (y == 7 and x in (1, 6)):
                    self.P(0, 'head', 'front', x, y, ring(x, y), 'metal')
                    self.hair_front.add((x, y))
        for x in range(8):
            self.P(0, 'head', 'front', x, 1, sh(C, -1.4), 'metal')

    # ───────────────────────────── face
    def face_pass(self):
        sk, E = self.skin, self.eye
        hp = self.hair_front
        ghost = 'ghostly' in self.acc

        def put(x, y, c, m='skin', force=False):
            if force or (x, y) not in hp:
                self.P(0, 'head', 'front', x, y, c, m)
        # modelling: light forehead, cheekbones, darker jaw and face sides
        for y in range(8):
            for x in range(8):
                k = 0.0
                if y <= 2:
                    k += 0.3
                if y == 7:
                    k -= 0.5
                if x in (0, 7):
                    k -= 0.25 if y < 5 else 0.45
                if y == 6 and x in (1, 6):
                    k -= 0.2
                if y == 5 and x in (1, 2, 5, 6):
                    k += 0.15
                if ghost and y in (2, 5) and x not in (3, 4):
                    k -= 0.7                                 # hollow sockets around the eyes
                put(x, y, sh(sk, k))
        for x in range(8):                                  # shadow under the fringe
            ys = [y for y in range(3) if (x, y) in hp]
            if ys and max(ys) + 1 <= 2:
                put(x, max(ys) + 1, sh(sk, -0.6))
        # eyes: 3×2 each (sclera · iris/pupil · highlight/iris) on rows 3–4, 2 px gap at x = 3..4
        iris = E
        hl = mix(E, (255, 255, 255), 0.62)
        pupil = mix(darken(E, 0.72), (12, 10, 20), 0.55)
        iris_d = sh(E, -0.9)
        scl = self.sclera
        scl_d = mix(scl, sh(sk, -0.4), 0.35)
        if ghost:                                           # spectral: glowing irises, cold whites
            iris, hl = lighten(saturate(E, 1.4), 0.15), (255, 255, 255)
            pupil, iris_d = (22, 30, 74), saturate(E, 1.3)
            scl, scl_d = (226, 238, 252), (186, 204, 228)
        for (w, a, b) in ((0, 1, 2), (7, 6, 5)):
            put(w, 3, scl, 'eye', True)
            put(w, 4, scl_d, 'eye', True)
            put(a, 3, iris, 'eye', True)
            put(a, 4, pupil, 'eye', True)
            put(b, 3, hl, 'eye', True)
            put(b, 4, iris_d, 'eye', True)
        # brows (hair colour, shaped by expression); pushed below a fringe that would hide them
        e = self.expr
        brow = self.brow_colour()
        lift = {'left': 0, 'right': 0}
        if 'round_glasses' in self.acc:
            lift = {'left': -1, 'right': -1}
        if 'monocle' in self.acc:
            lift['left'] = -1
        shape = list(BROWS.get(e, BROWS['kind']))
        if self.hairstyle == 'bald_mustache':
            shape += [(1, 1, 0.5), (2, 1, 0.3), (0, 2, 0.2)]           # bushy
        for (x, y, k) in shape:
            for (xx, side) in ((x, 'right'), (7 - x, 'left')):
                yy = max(0, y + lift[side])
                while (xx, yy) in hp and yy < 2:
                    yy += 1
                self.P(0, 'head', 'front', xx, yy, sh(brow, k), 'hair')
                hp.add((xx, yy))
        # nose: bridge light between the eyes, shadow under the tip
        if (3, 4) not in hp:
            put(3, 4, sh(sk, 0.35))
        put(4, 4, sh(sk, -0.25))
        put(4, 5, sh(sk, -0.75))
        put(3, 5, sh(sk, 0.2))
        # cheeks: blush (kind/gentle/cheerful/serene), freckles for outdoor folk, eye bags when weary
        blush = mix(sk, (236, 112, 116), 0.38)
        if e in ('kind', 'cheerful', 'gentle', 'serene'):
            put(0, 5, blush)
            put(7, 5, blush)
        if self.outfit == 'traveler' or self.hairstyle == 'curly_short':
            for (x, y) in ((1, 5), (6, 5), (2, 6)):
                put(x, y, mix(sk, (166, 92, 52), 0.3))
        if e == 'weary':
            for x in (0, 1, 6, 7):
                put(x, 5, sh(sk, -0.45))
        # mouth (2–3 px)
        lip = mix(sh(sk, -1.0), (176, 72, 78), 0.38)
        lip_d = mix(sh(sk, -1.9), (110, 40, 50), 0.3)
        teeth = (244, 238, 228)
        mouth = {'kind': [(3, 6, lip_d), (4, 6, lip_d), (5, 6, lip), (3, 7, sh(sk, 0.2))],
                 'serene': [(3, 6, lip), (4, 6, lip), (3, 7, sh(sk, 0.15))],
                 'gentle': [(3, 6, lip), (4, 6, lip_d), (3, 7, sh(sk, 0.15))],
                 'cheerful': [(3, 6, teeth), (4, 6, teeth), (5, 6, lip_d), (3, 7, lip)],
                 'stern': [(2, 6, lip_d), (3, 6, lip_d), (4, 6, lip_d)],
                 'noble': [(3, 6, lip), (4, 6, lip_d)],
                 'weary': [(3, 6, lip_d), (4, 6, lip_d), (5, 7, sh(sk, -0.4))],
                 'earnest': [(3, 6, lip), (4, 6, lip)],
                 'sad': [(3, 6, lip_d), (4, 6, lip_d), (2, 7, sh(sk, -0.5)), (5, 7, sh(sk, -0.5))]}[e]
        for (x, y, c) in mouth:
            if (x, y) in hp and not (y == 6 and 3 <= x <= 4):
                continue
            put(x, y, c, 'skin', force=True)
        # ears + head-side modelling
        for f in ('right', 'left'):
            for x in range(8):
                for y in range(8):
                    if self.Gm(0, 'head', f, x, y) != 'skin':
                        continue
                    dist = 7 - x if f == 'right' else x
                    k = 0.2 if y <= 2 else (-0.4 if y == 7 else 0)
                    if dist >= 6:
                        k -= 0.2
                    if 3 <= dist <= 4 and 3 <= y <= 5:
                        k = -0.2 if (dist == 3 and y == 4) else 0.15   # ear
                        if dist == 4 and y == 4:
                            k = -1.0
                    self.P(0, 'head', f, x, y, sh(sk, k), 'skin')
        self.F(0, 'head', ('bottom',), lambda f, x, y, w, h: (sh(sk, -0.9), 'skin') if self.Gm(0, 'head', 'bottom', x, y) == 'skin' else False)
        # neck shadow on the body top under the chin
        self.F(0, 'body', ('top',), lambda f, x, y, w, h: (sh(sk, -0.8), 'skin') if 2 <= x <= 5 and 1 <= y <= 2 else False)

    def brow_colour(self):
        if self.hairstyle == 'none':
            return sh(self.hair, -1.4) if lum(self.hair) > 0.6 else sh(self.skin, -1.5)
        H = self.hair
        return sh(H, -1.3) if lum(H) > 0.65 else sh(H, -0.5)

    # ───────────────────────────── accessories
    def accessory_pass(self):
        order = ('hood_down', 'rain_cape', 'torn_cape', 'shoulder_cape', 'big_backpack', 'scroll_bundle', 'map_case',
                 'satchel', 'medal_sash', 'scarf', 'crystal_pendant', 'tool_belt', 'lantern_belt', 'coin_pouch',
                 'key_ring', 'tuning_fork', 'thick_gloves', 'bandage_arm', 'mechanical_arm', 'soot_marks', 'ink_stains',
                 'goggles_forehead', 'helmet_lamp', 'round_glasses', 'monocle', 'quill_ear', 'broken_crown',
                 'frost_cracks', 'sculk_scars')
        for a in order:
            if a in self.acc:
                getattr(self, 'acc_' + a)()

    def acc_hood_down(self):
        S = self.second if self.outfit != 'robe' else sh(self.main, 0.25)
        lining = sh(self.second, -0.3)
        hood = ["SSTTTTSS",
                "STssssTS",
                "TsllllsT",
                "sTsllsTs",
                " sTssTs ",
                "  sTTs  "]
        cols = {'S': sh(S, 0.2), 'T': sh(S, 0.8), 's': sh(S, -0.7), 'l': sh(lining, -1.2)}
        for y, row in enumerate(hood):
            for x, ch in enumerate(row):
                if ch != ' ':
                    self.P(1, 'body', 'back', x, y, cols[ch], 'cloth')
        for x in range(8):                                  # rim of the hood behind the neck
            self.P(1, 'head', 'back', x, 7, sh(S, 0.5 if x % 3 else -0.2), 'cloth')
        for f in ('right', 'left'):
            for x in range(4):
                self.P(1, 'body', f, x, 0, sh(S, 0.4), 'cloth')
                if (f == 'right' and x <= 1) or (f == 'left' and x >= 2):
                    self.P(1, 'body', f, x, 1, sh(S, -0.3), 'cloth')
        for x in (0, 1, 6, 7):
            self.P(1, 'body', 'front', x, 0, sh(S, 0.5), 'cloth')
        self.P(1, 'body', 'front', 1, 1, sh(S, -0.4), 'cloth')
        self.P(1, 'body', 'front', 6, 1, sh(S, -0.4), 'cloth')
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: (sh(S, 0.6), 'cloth') if y <= 1 or x in (0, 7) else False)

    def acc_shoulder_cape(self):
        C = self.second
        MT = self.metal
        for y in range(0, 9):
            for x in range(8):
                if y == 8 and x in (0, 7):
                    continue
                k = (0.4 if y <= 1 else 0) + (0.5 if x in (1, 4) else (-0.6 if x in (3, 6) else 0))
                c, m = sh(C, k), 'cloth'
                if y == 7:
                    c, m = (MT if x % 2 == 0 else sh(MT, -0.8)), 'metal'
                if y == 8:
                    c = sh(C, -0.9)
                self.P(1, 'body', 'back', x, y, c, m)
        for f in ('right', 'left'):
            for x in range(4):
                for y in range(0, 4):
                    self.P(1, 'body', f, x, y, sh(C, 0.3 - 0.4 * y) if y < 3 else MT, 'cloth' if y < 3 else 'metal')
        for p in ARMS:                                       # mantle over the shoulders
            self.F(1, p, ('top',), lambda f, x, y, w, h: (sh(C, 0.8), 'cloth'))
            self.F(1, p, SIDES, lambda f, x, y, w, h: ((sh(C, 0.5 - 0.5 * y), 'cloth') if y < 2 else
                                                       ((MT if (x % 2 == 0) else sh(MT, -0.8)), 'metal') if y == 2 else False))
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: (sh(C, 0.7), 'cloth') if y >= 2 or x in (0, 7) else False)
        for x in (1, 6):                                     # clasps on the collarbones + chain
            self.P(1, 'body', 'front', x, 0, sh(MT, 1.2), 'metal')
            self.P(1, 'body', 'front', x, 1, MT, 'metal')
        for x in (2, 5):
            self.P(1, 'body', 'front', x, 1, sh(MT, -0.6), 'metal')
        self.P(1, 'body', 'front', 0, 0, sh(C, 0.4), 'cloth')
        self.P(1, 'body', 'front', 7, 0, sh(C, 0.4), 'cloth')

    def acc_rain_cape(self):
        C = mix(self.second, (70, 96, 116), 0.35)
        hood = sh(C, -0.4)
        for y in range(0, 12):
            for x in range(8):
                k = (0.6 if x in (1, 5) else -0.6 if x in (3, 7) else 0) + (0.4 if y < 2 else 0)
                c = sh(C, k)
                if (x * 5 + y * 3 + self.seed) % 11 == 0 and y > 2:
                    c = sh(C, 1.8)                            # beads of rain on the oilcloth
                if y == 11:
                    c = sh(C, -1.0)
                self.P(1, 'body', 'back', x, y, c, 'cloth')
        for x in range(1, 7):
            for y in range(0, 3):
                self.P(1, 'body', 'back', x, y, sh(hood, 0.5 if y == 0 else (-0.5 if y == 2 else 0)), 'cloth')
        for x in range(8):
            self.P(1, 'head', 'back', x, 7, sh(hood, 0.6), 'cloth')
        for f in ('right', 'left'):
            for x in range(4):
                back_half = (f == 'right' and x <= 1) or (f == 'left' and x >= 2)
                for y in range(12):
                    if y <= 2 or back_half:
                        self.P(1, 'body', f, x, y, sh(C, 0.3 if y <= 1 else -0.3), 'cloth')
        for p in ARMS:
            self.F(1, p, ('top',), lambda f, x, y, w, h: (sh(C, 0.7), 'cloth'))
            self.F(1, p, SIDES, lambda f, x, y, w, h: (sh(C, 0.4 - 0.4 * y), 'cloth') if y <= 3 else False)
            self.F(1, p, SIDES, lambda f, x, y, w, h: (sh(C, 1.8), 'cloth') if y == 2 and (x + len(f)) % 3 == 0 else False)
        for x in (0, 7):
            for y in range(0, 3):
                self.P(1, 'body', 'front', x, y, sh(C, 0.2 - 0.3 * y), 'cloth')
        self.P(1, 'body', 'front', 1, 0, self.metal, 'metal')
        self.P(1, 'body', 'front', 6, 0, self.metal, 'metal')
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: (sh(C, 0.5), 'cloth') if y >= 2 or x in (0, 7) else False)

    def acc_torn_cape(self):
        C = sh(mix(self.main, self.hair, 0.45), 0.2)
        s = self.seed

        def torn(x, y, h_):
            return y >= h_ - 3 and h2(x, y, s + 21) < 0.25 + 0.2 * (y - (h_ - 3))
        for y in range(0, 12):
            for x in range(8):
                k = (0.6 if x in (1, 4) else -0.7 if x in (2, 6) else 0) + (0.4 if y < 2 else 0)
                self.P(1, 'body', 'back', x, y, sh(C, k), 'cloth')
        for p in LEGS:
            for y in range(0, 9):
                for x in range(4):
                    if torn(x + (4 if p == 'lleg' else 0), y, 9) or (y == 8 and (x + y + s) % 2):
                        continue
                    k = (0.5 if x == 1 else -0.6 if x == 3 else 0) - 0.3 * (y / 8)
                    self.P(1, p, 'back', x, y, sh(C, k), 'cloth')
        for f in ('right', 'left'):
            for x in range(4):
                self.P(1, 'body', f, x, 0, sh(C, 0.4), 'cloth')
        MT = self.metal
        for x in (0, 7):
            self.P(1, 'body', 'front', x, 0, sh(MT, 1.0), 'metal')
            self.P(1, 'body', 'front', x, 1, sh(MT, -0.5), 'metal')
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: (sh(C, 0.6), 'cloth') if y <= 1 else False)

    def acc_big_backpack(self):
        Lh, S, MT = self.leather, self.second, self.metal
        pack = ["RRRRRRRR",
                "BffffffB",
                "BfFFFFfB",
                "BffYYffB",
                "BlllllLB",
                "BLLLLLLB",
                "BLqLLqLB",
                "BLqLLqLB",
                "BLLLLLLB",
                "BLppppLB",
                "BLLLLLLB",
                " bbbbbb "]
        roll = sh(S, -0.1)
        cols = {'R': sh(roll, 0.6), 'B': sh(Lh, -0.9), 'b': sh(Lh, -1.6), 'f': sh(Lh, 0.5), 'F': sh(Lh, 1.0), 'Y': MT,
                'l': sh(Lh, -1.2), 'L': Lh, 'q': sh(Lh, -1.8), 'p': sh(Lh, 0.8)}
        for y, row in enumerate(pack):
            for x, ch in enumerate(row):
                if ch != ' ':
                    self.P(1, 'body', 'back', x, y, cols[ch], 'metal' if ch == 'Y' else 'cloth' if ch == 'R' else 'leather')
        # bedroll on top of the pack, spiral end on the sides
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: (sh(roll, 0.8 if y == 3 else 0.2 if y == 2 else -0.5), 'cloth') if y >= 1 else False)
        for f in ('right', 'left'):
            for x in range(4):
                back_x = (x <= 1) if f == 'right' else (x >= 2)
                for y in range(12):
                    if y == 0:
                        self.P(1, 'body', f, x, y, sh(roll, 0.3 if (x + y) % 2 else -0.6), 'cloth')
                    elif back_x and 1 <= y <= 10:
                        c = sh(Lh, 0.3 if y in (6, 7) else -0.5)
                        if y in (6, 7, 8) and ((f == 'right' and x == 0) or (f == 'left' and x == 3)):
                            c = sh(Lh, 0.8)                     # side pocket
                        self.P(1, 'body', f, x, y, c, 'leather')
        for x in (1, 6):                                       # shoulder straps
            for y in range(0, 7):
                self.P(1, 'body', 'front', x, y, sh(Lh, -0.4 if y else 0.4), 'leather')
            self.P(1, 'body', 'front', x, 4, MT, 'metal')
        # a tin cup hanging from the side
        self.P(1, 'body', 'left', 2, 9, sh(MT, 0.8), 'metal')
        self.P(1, 'body', 'left', 2, 10, sh(MT, -0.6), 'metal')

    def acc_scroll_bundle(self):
        paper, paper_d = (236, 226, 196), (190, 170, 130)
        tie = sh(self.main, 0.4)
        strap = sh(self.leather, -0.6)
        for (x0, y0, ln) in ((1, 1, 8), (3, 0, 9), (5, 2, 8)):
            for y in range(y0, y0 + ln):
                for dx in (0, 1):
                    c = paper if dx == 0 else paper_d
                    if y == y0:
                        c = (250, 244, 224) if dx == 0 else paper
                    if y == y0 + ln // 2:
                        c = tie if dx == 0 else sh(tie, -0.8)
                    self.P(1, 'body', 'back', x0 + dx, y, c, 'cloth')
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: ((250, 244, 224), 'cloth') if (x in (3, 4) and y in (1, 2)) else False)
        for y in range(11):                                   # carrying strap across the chest
            x = 7 - int(y * 0.7)
            self.P(1, 'body', 'front', x, y, strap if y % 3 else sh(strap, 1.2), 'leather')

    def acc_map_case(self):
        Lh, MT = self.leather, self.metal
        tube = sh(self.second, -0.6)
        strap = sh(Lh, -0.7)
        for y in range(11):                                   # strap across the chest
            x = int(y * 0.7)
            self.P(1, 'body', 'front', x, y, strap if y % 3 else sh(strap, 1.2), 'leather')
        for y in range(0, 11):                                # diagonal map tube across the back
            x = 6 - int(y * 0.5)
            for dx in (0, 1):
                xx = x + dx
                c, m = sh(tube, 0.6 if dx == 0 else -0.5), 'leather'
                if y in (0, 10):
                    c, m = (MT if dx == 0 else sh(MT, -0.8)), 'metal'
                if y == 5:
                    c = sh(Lh, -1.0)
                self.P(1, 'body', 'back', xx, y, c, m)
        self.P(1, 'body', 'top', 6, 3, (236, 226, 196), 'cloth')
        self.P(1, 'body', 'top', 7, 3, (210, 196, 160), 'cloth')

    def acc_satchel(self):
        Lh, MT = self.leather, self.metal
        strap = sh(Lh, -0.5)
        for y in range(0, 9):                                 # strap from the left shoulder to the right hip
            x = 7 - int(round(y * 0.85))
            self.P(1, 'body', 'front', x, y, strap if y % 3 else sh(Lh, 1.0), 'leather')
            self.P(1, 'body', 'back', 7 - x, y, strap, 'leather')
        bag = ["fFFf",
               "fYgf",
               "LLLL",
               "LxLL",
               "lllq"]
        cols = {'f': sh(Lh, 0.5), 'F': sh(Lh, 0.9), 'Y': sh(MT, 1.0), 'g': MT, 'L': Lh, 'x': sh(Lh, 1.8), 'l': sh(Lh, -1.0),
                'q': sh(Lh, -1.8)}
        for y, row in enumerate(bag):                          # bag hangs on the right hip
            for x, ch in enumerate(row):
                self.P(1, 'body', 'right', x, 7 + y, cols[ch], 'metal' if ch in 'Yg' else 'leather')
        self.P(1, 'body', 'front', 0, 9, sh(Lh, 0.4), 'leather')
        self.P(1, 'body', 'front', 0, 10, sh(Lh, -0.4), 'leather')
        self.P(1, 'body', 'back', 7, 9, sh(Lh, -0.8), 'leather')
        self.P(1, 'body', 'back', 7, 10, sh(Lh, -1.2), 'leather')

    def acc_medal_sash(self):
        S, MT, E = self.second, self.metal, self.eye
        for y in range(0, 10):                                # sash from the right shoulder to the left hip
            x = int(round(y * 0.75))
            self.P(1, 'body', 'front', x, y, sh(S, 0.5), 'cloth')
            self.P(1, 'body', 'front', x + 1, y, sh(S, -0.5) if y % 3 else sh(MT, 0.2), 'cloth' if y % 3 else 'metal')
            self.P(1, 'body', 'back', 7 - x, y, sh(S, 0.2), 'cloth')
            self.P(1, 'body', 'back', 6 - x, y, sh(S, -0.6), 'cloth')
        # two medals on ribbons in the eye colour, and a jewel on the sash knot
        for (x, y, c, m) in ((5, 2, sh(E, 0.3), 'cloth'), (5, 3, sh(MT, 1.5), 'metal'), (6, 2, sh(E, -0.4), 'cloth'),
                             (6, 3, MT, 'metal'), (6, 4, sh(MT, -0.8), 'metal'), (5, 4, sh(MT, -0.3), 'metal')):
            self.P(1, 'body', 'front', x, y, c, m)
        self.P(1, 'body', 'front', 7, 9, sh(MT, 1.2), 'metal')
        self.P(1, 'body', 'front', 7, 10, sh(E, 0.6), 'gem')

    def acc_scarf(self):
        S = sh(self.main, 0.5)
        band = self.second
        for f in SIDES:                                       # thick wrap around the neck, folds every few texels
            x0, y0, w, h = face_rect('body', f, 1)
            for x in range(w):
                self.P(1, 'body', f, x, 0, sh(S, 0.7 if x % 3 else 0.2), 'cloth')
                self.P(1, 'body', f, x, 1, sh(S, -0.2 if x % 3 else -0.9), 'cloth')
        for f in SIDES:                                       # rising to the chin on the hat layer
            for x in range(8):
                if f == 'front' and 1 <= x <= 6:
                    continue
                self.P(1, 'head', f, x, 7, sh(S, 0.3 if x % 3 else -0.4), 'cloth')
        self.F(1, 'head', ('bottom',), lambda f, x, y, w, h: (sh(S, -0.8), 'cloth') if x in (0, 7) or y in (0, 7) else False)
        self.F(1, 'body', ('top',), lambda f, x, y, w, h: (sh(S, 0.6 if (x + y) % 3 else 0.0), 'cloth'))
        for y in range(2, 8):                                 # one tail hanging over the chest, banded end, fringe
            c = band if y in (6,) else S
            self.P(1, 'body', 'front', 4, y, sh(c, 0.4 if y < 4 else 0.0), 'cloth')
            self.P(1, 'body', 'front', 5, y, sh(c, -0.7), 'cloth')
        self.P(1, 'body', 'front', 4, 8, sh(S, 0.5), 'cloth')
        self.P(1, 'body', 'front', 5, 8, None)

    def acc_crystal_pendant(self):
        MT = self.metal
        g = self.glow
        for (x, y) in ((1, 0), (2, 1), (5, 1), (6, 0)):
            self.P(1, 'body', 'front', x, y, MT if (x + y) % 2 else sh(MT, -0.6), 'metal')
        self.P(1, 'body', 'front', 3, 2, sh(MT, 0.8), 'metal')
        self.P(1, 'body', 'front', 4, 2, sh(MT, -0.6), 'metal')
        for (x, y, c) in ((3, 3, (255, 255, 255)), (4, 3, lighten(g, 0.55)), (3, 4, lighten(g, 0.3)), (4, 4, g),
                          (3, 5, g), (4, 5, sh(g, -0.9))):
            self.P(1, 'body', 'front', x, y, c, 'glow')
        for (x, y) in ((2, 3), (5, 3), (2, 4), (5, 4), (3, 6), (4, 6)):      # light spilling onto the robe
            c = self.G(0, 'body', 'front', x, y)
            self.P(0, 'body', 'front', x, y, mix(c, lighten(g, 0.3), 0.35), 'cloth')

    def acc_tool_belt(self):
        Lh, MT = self.leather, self.metal
        wood = (150, 104, 62)
        for f in SIDES:
            x0, y0, w, h = face_rect('body', f, 1)
            for x in range(w):
                self.P(1, 'body', f, x, 8, sh(Lh, 0.4), 'leather')
                self.P(1, 'body', f, x, 9, sh(Lh, -0.6), 'leather')
        self.P(1, 'body', 'front', 3, 8, sh(MT, 1.2), 'metal')
        self.P(1, 'body', 'front', 4, 8, MT, 'metal')
        self.P(1, 'body', 'front', 3, 9, sh(MT, -0.6), 'metal')
        self.P(1, 'body', 'front', 4, 9, sh(MT, -0.6), 'metal')
        for (x0, w_) in ((0, 2), (5, 3)):                     # pouches
            for x in range(x0, x0 + w_):
                self.P(1, 'body', 'front', x, 10, sh(Lh, 0.2 if x == x0 else -0.4), 'leather')
                self.P(1, 'body', 'front', x, 11, sh(Lh, -1.0), 'leather')
        for (x, y, c, m) in ((0, 7, sh(MT, 1.0), 'metal'), (1, 6, wood, 'leather'), (1, 7, sh(wood, -0.8), 'leather'),
                             (6, 6, sh(MT, 0.8), 'metal'), (6, 7, MT, 'metal'), (7, 7, sh(MT, 1.2), 'metal')):
            self.P(1, 'body', 'front', x, y, c, m)            # wrench, screwdriver, spanner sticking out
        for f in ('right', 'left'):
            self.P(1, 'body', f, 1, 10, sh(Lh, -0.2), 'leather')
            self.P(1, 'body', f, 2, 10, sh(Lh, -0.8), 'leather')

    def acc_lantern_belt(self):
        MT = self.metal
        warm = (255, 214, 120)
        lamp = ["  g ",
                " gYg",
                " gWg",
                " gwg",
                "  g "]
        cols = {'g': sh(MT, -0.8), 'Y': sh(MT, 1.2), 'W': lighten(warm, 0.5), 'w': warm}
        for y, row in enumerate(lamp):                        # small lantern hooked to the right hip
            for x, ch in enumerate(row):
                if ch != ' ':
                    self.P(1, 'body', 'right', x, 7 + y, cols[ch], 'glow' if ch in 'Ww' else 'metal')
        self.P(1, 'rleg', 'right', 2, 0, sh(MT, -1.0), 'metal')
        self.P(1, 'body', 'front', 0, 9, sh(MT, -0.4), 'metal')
        self.P(1, 'body', 'front', 0, 10, warm, 'glow')
        for (p, f, x, y) in (('body', 'right', 0, 9), ('body', 'right', 0, 10), ('rleg', 'right', 1, 1), ('rleg', 'right', 3, 1)):
            c = self.G(0, p, f, x, y)                         # warm light falling on the clothes around it
            if c:
                self.P(0, p, f, x, y, mix(c, warm, 0.3), 'cloth')

    def acc_coin_pouch(self):
        Lh, MT = self.leather, self.metal
        pouch = ["gYg",
                 "LdL",
                 "LLl",
                 "lql"]
        cols = {'g': sh(Lh, -1.0), 'Y': sh(MT, 1.0), 'L': sh(Lh, 0.5), 'l': sh(Lh, -0.6), 'q': sh(Lh, -1.4), 'd': MT}
        for y, row in enumerate(pouch):
            for x, ch in enumerate(row):
                self.P(1, 'body', 'front', 5 + x, 8 + y, cols[ch], 'metal' if ch in 'Yd' else 'leather')
        self.P(1, 'body', 'left', 0, 9, sh(Lh, -0.2), 'leather')
        self.P(1, 'body', 'left', 0, 10, sh(Lh, -0.9), 'leather')

    def acc_key_ring(self):
        MT = self.metal
        for (x, y) in ((5, 8), (6, 8), (5, 9), (7, 9), (6, 10)):
            self.P(1, 'body', 'front', x, y, sh(MT, 0.6 if y == 8 else -0.3), 'metal')
        for (x, y, k) in ((5, 10, 0.8), (5, 11, 0.0), (7, 10, 0.4), (7, 11, -0.4), (6, 11, 1.2)):
            self.P(1, 'body', 'front', x, y, sh(MT, k), 'metal')
        self.P(1, 'lleg', 'front', 2, 0, sh(MT, -0.2), 'metal')
        self.P(1, 'lleg', 'front', 3, 0, sh(MT, 0.6), 'metal')
        self.P(1, 'lleg', 'front', 2, 1, sh(MT, -0.8), 'metal')

    def acc_tuning_fork(self):
        MT = self.metal
        g = self.glow
        fork = ["G.G.",
                "Y.G.",
                "G.g.",
                "Y.G.",
                "GgG.",
                ".G..",
                ".g.."]
        for y, row in enumerate(fork):                        # hangs on the right hip, prongs up
            for x, ch in enumerate(row):
                if ch != '.':
                    self.P(1, 'body', 'right', x, 4 + y, {'G': MT, 'Y': sh(MT, 1.4), 'g': sh(MT, -0.9)}[ch], 'metal')
        for y in range(0, 3):
            self.P(1, 'rleg', 'right', 1, y, sh(MT, -0.5 if y else 0.2), 'metal')
        self.P(1, 'rleg', 'right', 1, 3, sh(MT, 0.8), 'metal')
        for (x, y) in ((1, 4), (1, 6)):                       # faint resonance between the prongs
            self.P(1, 'body', 'right', x, y, lighten(g, 0.2), 'glow')
        self.P(1, 'body', 'front', 0, 8, sh(self.leather, -0.6), 'leather')

    def acc_thick_gloves(self):
        G_ = sh(self.leather, -0.3)
        self.hands((8, 11), glove=G_)

        def gaunt(cf, cx, y, p):                         # flared gauntlet cuff with stitching
            if cf in ('top', 'bottom') or not (7 <= y <= 9):
                return False
            if y == 9:
                return (sh(G_, 2.0) if cx % 2 == 0 else sh(G_, 0.2), 'leather')
            return (sh(G_, 0.9 if y == 7 else 0.3), 'leather')
        self.L(1, ARMS, gaunt)
        self.L(0, ARMS, lambda cf, cx, y, p: (sh(G_, 0.6 if cx % 2 else -0.2), 'leather') if cf == 'back' and y == 10 else False)

    def acc_bandage_arm(self):
        W = (238, 232, 218)
        order = {'front': 0, 'in': 4, 'back': 8, 'out': 12}

        def wrap(cf, cx, y, p):                         # strips wound diagonally around the forearm
            if cf in ('top', 'bottom') or not (5 <= y <= 9):
                return False
            t = order[cf] + cx
            d = (t + 2 * y) % 6
            if d == 0:
                return (sh(W, -1.1), 'cloth')
            return (sh(W, 0.3 if d in (1, 2) else -0.25), 'cloth')
        self.L(1, ('larm',), wrap)
        self.P(1, 'larm', 'front', 1, 7, mix(W, (170, 56, 56), 0.45), 'cloth')
        self.P(1, 'larm', 'front', 2, 7, mix(W, (170, 56, 56), 0.25), 'cloth')
        self.P(1, 'larm', 'left', 1, 10, sh(W, 0.1), 'cloth')       # loose end
        self.P(1, 'larm', 'left', 1, 11, sh(W, -0.4), 'cloth')

    def acc_mechanical_arm(self):
        MT = self.metal
        steel = mix(MT, (118, 122, 132), 0.5)
        g = self.glow
        keys = {'Y': (sh(MT, 1.3), 'metal'), 'B': (MT, 'metal'), 'b': (sh(MT, -1.0), 'metal'), 'd': ((40, 36, 40), 'metal'),
                'H': (sh(steel, 1.2), 'metal'), 'S': (steel, 'metal'), 's': (sh(steel, -1.0), 'metal'),
                'r': (sh(MT, 1.8), 'metal'), 'g': (g, 'glow'), 'G': (lighten(g, 0.5), 'glow'), 'P': (sh(steel, 1.6), 'metal')}
        faces = {'front': ["YBBb", "BYBb", "bBBb", "dddd", "HSSs", "HSSs", "HSSs", "dddd", "YBBb", "BrBb", "BbBb", "bdbd"],
                 'out': ["bBYB", "bBrY", "bbBB", "dddd", "sSSH", "sgGH", "sSSH", "dddd", "bBYB", "bPPB", "bBBB", "dbdb"],
                 'back': ["bBBb", "bBrb", "bbBb", "dddd", "sSSs", "sSHs", "sSSs", "dddd", "bBBb", "bBBb", "bBbb", "dbdb"],
                 'in': ["bbBb", "bbBb", "bbbb", "dddd", "ssSs", "ssSs", "ssSs", "dddd", "bbBb", "bbBb", "bbbb", "dbdb"]}

        def arm(cf, cx, y, p):
            if cf == 'top':
                return (sh(MT, 0.8), 'metal')
            if cf == 'bottom':
                return (sh(MT, -1.2), 'metal')
            return keys[faces[cf][y][cx]]
        self.L(0, ('rarm',), arm)

        def mount(cf, cx, y, p):                         # bolted shoulder mount on the outer layer
            if cf == 'top':
                return (sh(MT, 1.0 if cx in (1, 2) else 0.4), 'metal')
            if cf in ('bottom', 'in') or y > 1:
                return False
            if y == 1 and cx in (0, 3):
                return (sh(MT, 1.8), 'metal')
            return (sh(MT, 0.9 if y == 0 else -0.5), 'metal')
        self.L(1, ('rarm',), mount)
        for x in range(4):                                   # harness strap across the chest
            self.P(1, 'body', 'right', x, 1, sh(self.leather, -0.6), 'leather')
        for y in range(1, 8):
            self.P(1, 'body', 'front', int(y * 0.9), y, sh(self.leather, -0.4 if y % 2 else 0.2), 'leather')

    def acc_soot_marks(self):
        soot = (44, 38, 36)
        marks = [('head', 'front', 1, 6, 0.55), ('head', 'front', 2, 6, 0.35), ('head', 'front', 6, 5, 0.45),
                 ('head', 'front', 0, 1, 0.3), ('body', 'front', 2, 3, 0.4), ('body', 'front', 3, 3, 0.25),
                 ('body', 'front', 5, 6, 0.45), ('body', 'front', 4, 10, 0.4), ('rarm', 'front', 1, 8, 0.4),
                 ('rarm', 'front', 2, 9, 0.5), ('larm', 'front', 2, 7, 0.35), ('larm', 'right', 1, 9, 0.45),
                 ('rleg', 'front', 1, 3, 0.35), ('lleg', 'front', 2, 5, 0.4)]
        for (p, f, x, y, t) in marks:
            c = self.G(0, p, f, x, y)
            if c and self.Gm(0, p, f, x, y) != 'eye':
                self.P(0, p, f, x, y, mix(c, soot, t), self.Gm(0, p, f, x, y) or 'cloth')

    def acc_ink_stains(self):
        ink = (26, 30, 66)
        marks = [('rarm', 'front', 2, 10, 0.75), ('rarm', 'front', 3, 11, 0.85), ('rarm', 'left', 0, 11, 0.7),
                 ('rarm', 'front', 1, 11, 0.5), ('body', 'front', 2, 9, 0.6), ('body', 'front', 2, 10, 0.4),
                 ('body', 'front', 6, 5, 0.55), ('head', 'front', 6, 6, 0.4), ('larm', 'front', 1, 9, 0.5)]
        for (p, f, x, y, t) in marks:
            c = self.G(0, p, f, x, y)
            if c:
                self.P(0, p, f, x, y, mix(c, ink, t), self.Gm(0, p, f, x, y) or 'cloth')

    def acc_goggles_forehead(self):
        MT = self.metal
        strap = sh(self.leather, -1.0)
        glass = mix(MT, (110, 196, 214), 0.55)
        for f in ('right', 'left', 'back'):
            for x in range(8):
                self.P(1, 'head', f, x, 1, strap, 'leather')
                self.P(1, 'head', f, x, 2, sh(strap, -0.6), 'leather')
        gog = ["gYgssgYg",
               "gWlgglWg"]
        cols = {'g': sh(MT, -0.6), 'Y': sh(MT, 1.2), 'W': lighten(glass, 0.6), 'l': glass, 's': strap}
        for y, row in enumerate(gog):                          # lenses sit on the forehead: rows 0–1 only
            for x, ch in enumerate(row):
                self.P(1, 'head', 'front', x, y, cols[ch], 'glow' if ch in 'Wl' else 'leather' if ch == 's' else 'metal')
        for x in range(8):
            self.P(1, 'head', 'front', x, 2, None)

    def acc_helmet_lamp(self):
        hel = mix(sh(self.metal, -0.2), (210, 170, 70), 0.45)
        warm = (255, 226, 140)
        self.F(1, 'head', ('top',), lambda f, x, y, w, h: (sh(hel, 1.4 if (2 <= x <= 4 and 2 <= y <= 4) else 0.5 if y < 6 else 0), 'metal'))
        self.F(1, 'head', ('right', 'left', 'back'), lambda f, x, y, w, h: (sh(hel, 0.4 if y == 0 else (-1.0 if y == 2 else 0)), 'metal') if y <= 2 else False)
        for x in range(8):
            self.P(1, 'head', 'front', x, 0, sh(hel, 0.5), 'metal')
            self.P(1, 'head', 'front', x, 1, sh(hel, -1.0), 'metal')
        for (x, y, c) in ((3, 0, lighten(warm, 0.6)), (4, 0, warm), (3, 1, warm), (4, 1, sh(warm, -0.6))):
            self.P(1, 'head', 'front', x, y, c, 'glow')
        self.P(1, 'head', 'front', 2, 0, sh(self.metal, -1.0), 'metal')
        self.P(1, 'head', 'front', 5, 0, sh(self.metal, -1.0), 'metal')

    def acc_round_glasses(self):
        MT = self.metal
        rim, rim_d = sh(MT, -0.6), sh(MT, -1.4)
        glint = lighten(MT, 0.75)
        for (lens, inner, outer) in (((0, 1, 2), 3, 'right'), ((7, 6, 5), 4, 'left')):
            a, b, c = lens                                    # a = outer column, c = inner column
            for (x, y, col) in ((a, 2, rim_d), (b, 2, rim), (c, 2, rim_d), (b, 5, rim_d), (c, 5, rim_d),
                                (inner, 3, rim), (inner, 4, rim_d)):
                self.P(1, 'head', 'front', x, y, col, 'metal')
            self.P(1, 'head', 'front', b, 2, glint, 'glow')
            fx, dx = (7, -1) if outer == 'right' else (0, 1)  # temples along the head sides to the ears
            for i in range(4):
                self.P(1, 'head', outer, fx + dx * i, 3, sh(rim, -0.3 * i), 'metal')
            self.P(1, 'head', outer, fx, 4, rim_d, 'metal')

    def acc_monocle(self):
        MT = self.metal
        rim, rim_d = sh(MT, -0.2), sh(MT, -1.0)
        for (x, y, c) in ((5, 2, rim), (6, 2, lighten(MT, 0.6)), (7, 2, rim), (4, 3, rim), (4, 4, rim_d),
                          (5, 5, rim_d), (6, 5, rim_d)):
            self.P(1, 'head', 'front', x, y, c, 'glow' if c != rim and c != rim_d else 'metal')
        self.P(1, 'head', 'left', 0, 3, rim, 'metal')
        self.P(1, 'head', 'left', 0, 4, rim_d, 'metal')
        for (x, y) in ((7, 5), (7, 6), (7, 7)):                 # thin chain falling to the collar
            self.P(1, 'head', 'front', x, y, sh(MT, -0.3 if y % 2 else 0.4), 'metal')
        self.P(1, 'body', 'front', 7, 0, sh(MT, -0.3), 'metal')
        self.P(1, 'body', 'front', 7, 1, sh(MT, 0.4), 'metal')

    def acc_quill_ear(self):
        vane, vane_d = (250, 248, 240), (206, 200, 190)
        tip = (30, 30, 52)
        for (x, y, k) in ((5, 6, 'n'), (5, 5, 's'), (4, 4, 's'), (4, 3, 's'), (3, 2, 's'), (3, 1, 's'), (2, 0, 's')):
            self.P(1, 'head', 'right', x, y, tip if k == 'n' else (226, 214, 180), 'cloth')   # shaft behind the ear
        for (x, y) in ((5, 4), (5, 3), (4, 2), (4, 1), (3, 0), (4, 0)):
            self.P(1, 'head', 'right', x, y, vane, 'cloth')
        for (x, y) in ((3, 4), (3, 3), (2, 2), (2, 1), (1, 0)):
            self.P(1, 'head', 'right', x, y, vane_d, 'cloth')
        self.P(1, 'head', 'top', 0, 2, vane, 'cloth')
        self.P(1, 'head', 'top', 0, 1, vane_d, 'cloth')

    def acc_broken_crown(self):
        MT = self.metal
        gold, gold_d, gold_l = MT, sh(MT, -1.0), sh(MT, 1.2)
        gem = sh(saturate(self.eye, 1.2), 0.2)
        for f in ('front', 'right', 'left', 'back'):
            for x in range(8):
                broken = (f == 'left' and x >= 4) or (f == 'back' and x <= 1)
                self.P(1, 'head', f, x, 1, gold_d if broken and x % 2 else gold, 'metal')
                if x % 3 == 1 and not broken:
                    self.P(1, 'head', f, x, 0, gold_l, 'metal')
                elif broken and x % 4 == 0:
                    self.P(1, 'head', f, x, 0, gold_d, 'metal')       # stub of a snapped point
        for (f, x) in (('front', 3), ('front', 4), ('right', 3), ('back', 5)):
            self.P(1, 'head', f, x, 1, gem if (f, x) != ('front', 4) else lighten(gem, 0.4), 'gem')
        self.P(1, 'head', 'left', 5, 1, (220, 240, 255), 'glow')                  # crack glint
        self.F(1, 'head', ('top',), lambda f, x, y, w, h: (gold, 'metal') if (x in (0, 7) or y in (0, 7)) and not (x >= 4 and y >= 6) else False)

    def acc_frost_cracks(self):
        ice, ice_d = (226, 246, 255), (150, 206, 236)
        # a few branching hairline cracks (polylines), brightest at the centre of each crack
        cracks = {('body', 'front'): [(1, 1), (2, 2), (2, 3), (3, 4), (1, 3)],
                  ('body', 'back'): [(5, 1), (5, 2), (4, 3), (4, 4), (6, 3)],
                  ('rarm', 'front'): [(1, 6), (2, 7), (2, 8)],
                  ('larm', 'left'): [(2, 7), (1, 8), (1, 9)],
                  ('head', 'front'): [(6, 6), (7, 7)],
                  ('rleg', 'front'): [(1, 2), (2, 3), (2, 4)]}
        for (p, f), pts in cracks.items():
            for i, (x, y) in enumerate(pts):
                self.P(0, p, f, x, y, ice if 0 < i < len(pts) - 1 else ice_d, 'glow')

    def acc_sculk_scars(self):
        teal = (47, 224, 208)
        teal_d = sh(teal, -1.2)
        for (x, y, c) in ((7, 5, teal), (6, 6, teal_d), (7, 6, teal), (6, 7, teal)):
            self.P(0, 'head', 'front', x, y, c, 'glow')
        for (x, y, c) in ((0, 5, teal_d), (1, 6, teal), (1, 7, teal_d)):
            self.P(0, 'head', 'left', x, y, c, 'glow')
        for i, (x, y) in enumerate(((0, 3), (1, 4), (1, 5), (2, 6), (1, 7), (2, 8), (3, 9))):
            self.P(0, 'larm', 'front', x, y, teal if i % 2 == 0 else teal_d, 'glow')

    # ───────────────────────────── post effects / lighting
    def post_pass(self):
        if 'ghostly' not in self.acc:
            return
        pale = (200, 228, 255)
        for yy in range(64):
            for xx in range(64):
                c = self.px[xx, yy]
                m = self.mat[yy][xx]
                if not c[3] or m in ('glow', 'eye'):
                    continue
                g = mix(saturate(c[:3], 0.92), pale, 0.07) if m == 'hair' else mix(saturate(c[:3], 0.7), pale, 0.16)
                self.px[xx, yy] = (g[0], g[1], g[2], 255)
        for p in LEGS:                                            # lower legs fade to mist, wisps on the pants layer
            for f in SIDES:
                for y in range(8, 12):
                    for x in range(4):
                        c = self.G(0, p, f, x, y)
                        self.P(0, p, f, x, y, mix(c, (214, 236, 255), 0.16 * (y - 7)), 'glow' if y >= 10 else 'cloth')
            self.F(1, p, SIDES, lambda f, x, y, w, h, p=p: ((226, 242, 255), 'glow')
                   if y >= 9 and h2(x + len(f) * 3, y, self.seed + len(p)) > 0.7 else False)

    def ao(self, part, f, x, y):
        k = 0.0
        if part in ARMS:
            cf, cx = canon(part, f, x)
            if cf == 'in':
                k -= 0.35
            if (cf == 'front' and cx == 3) or (cf == 'back' and cx == 0):
                k -= 0.12
        elif part in LEGS:
            cf, cx = canon(part, f, x)
            if cf == 'in':
                k -= 0.45
            if y <= 1 and f in SIDES:
                k -= 0.25
        elif part == 'body' and f in ('right', 'left'):
            k -= 0.15
        return k

    def light_pass(self):
        s = self.seed
        for part in BOXES:
            for layer in (0, 1):
                for f in ALL:
                    x0, y0, w, h = face_rect(part, f, layer)
                    for y in range(h):
                        for x in range(w):
                            X, Y = x0 + x, y0 + y
                            c = self.px[X, Y]
                            if c[3] == 0:
                                continue
                            m = self.mat[Y][X]
                            if m in NOSHADE:
                                continue
                            k = 0.0
                            if f in SIDES:
                                t = y / max(1, h - 1)
                                k += (0.15 - 0.3 * t) if part == 'head' else (0.3 - 0.6 * t)
                                if f in ('right', 'left'):
                                    k -= 0.2
                                elif f == 'back':
                                    k -= 0.12
                            elif f == 'top':
                                k += 0.3
                            else:
                                k -= 0.6
                            k += self.ao(part, f, x, y)
                            if m == 'skin':
                                k *= 0.55
                            elif m == 'cloth':
                                k += (h2(X, Y, s) - 0.5) * 0.08
                            elif m == 'leather':
                                n = h2(X, Y, s + 7)
                                k += (n - 0.5) * 0.12 + (0.25 if n > 0.96 else 0)
                            elif m == 'hair':
                                k += (h2(X, Y // 2, s + 3) - 0.5) * 0.1
                            elif m == 'metal':
                                k *= 1.2
                            if abs(k) < 0.02:
                                continue
                            rgb = sh(c, k)
                            self.px[X, Y] = (rgb[0], rgb[1], rgb[2], c[3])

    def finish(self):
        """Base layer must be fully opaque (only the outer layer may have holes)."""
        for part in BOXES:
            for f in ALL:
                x0, y0, w, h = face_rect(part, f, 0)
                for y in range(h):
                    for x in range(w):
                        c = self.px[x0 + x, y0 + y]
                        if c[3] != 255:
                            base = self.skin if c[3] == 0 else (c[0], c[1], c[2])
                            self.px[x0 + x, y0 + y] = (base[0], base[1], base[2], 255)


# ───────────────────────────── hair styles
# fam: colouring family (see Skin.hcol).  Masks are 8×8 '#' grids (missing rows = empty):
#   front / hat_front — head front, x = face column (rows 3–4 hold the eyes and are never covered;
#                       long styles hang locks beside the cheeks on rows 5–7 of the hat layer)
#   side / hat_side   — both head sides, column = distance from the FRONT edge (an empty patch around
#                       distance 3–4, rows 3–5 leaves the ear visible)
#   back / hat_back   — head back;  hat_top — top of the hat layer
_E = "        "
_F = "########"
HAIR = {
    'long_braid': {'fam': 'smooth', 'part': 5,
                   'front': [_F, "##### ##", "#       "],
                   'side': [_F] * 8,
                   'back': [_F] * 8,
                   'hat_front': [_F, "####  ##", "#       ", _E, _E, "#      #", "#      #"],
                   'hat_side': ["  ######", " #######", _F, _F, "#### ###", _F, "### ####", " # # ## "],
                   'hat_back': [_F, _F, _F, "##    ##", "##    ##", "##    ##", "# #  # #"],
                   'hat_top': [" ###### ", _F, _F, _F, _F, _F, _F, " ###### "]},
    'short_beard': {'fam': 'tousled',
                    'front': [_F, "#      #"],
                    'side': [_F, _F, _F, "##   ###", "##   ###", "##   ###", "##    ##", "#      #"],
                    'back': [_F, _F, _F, _F, _F, _F, "# ## # #"],
                    'hat_front': ["# #### #"],
                    'hat_side': ["### ####", "#  #  # "],
                    'hat_back': ["## ## ##", "# #  # #"],
                    'hat_top': ["# #  # #", " ###### ", "## ## ##", " ###### ", _F, " # ## # ", _F, "## ## ##"]},
    'silver_ponytail': {'fam': 'combed', 'part': 2,
                        'front': [_F, "###    #", "##      "],
                        'side': [_F, _F, _F, "#   ####", "#    ###", "     ###", "      ##"],
                        'back': [_F, _F, _F, _F, _F, _F, "  ####  "],
                        'hat_front': [_F, "##      ", "#       "],
                        'hat_side': [_F, " #######"],
                        'hat_back': [_F, _F, "## ## ##"],
                        'hat_top': [_F] * 8},
    'messy_short': {'fam': 'tousled',
                    'front': [_F, "## # ###", "#     # "],
                    'side': [_F, _F, _F, _F, "##  ####", "#   # ##", "      # "],
                    'back': [_F, _F, _F, _F, _F, "# ######", " # # ## ", "#   #   "],
                    'hat_front': ["# ## ###", " #  #  #"],
                    'hat_side': ["## ### #", " # #  ##", "#  #  # "],
                    'hat_back': ["## ## ##", "# ## ## ", " #  # # ", "#  #   #", "  #  #  ", " #   #  "],
                    'hat_top': ["# # # ##", " # ## # ", "## # # #", " #  ## #", "# ##  # ", " # # ## ", "## #  # ", " # ## ##"]},
    'curly_short': {'fam': 'curly',
                    'front': [_F, "# #  # #"],
                    'side': [_F, _F, _F, _F, "###  ###", "#     ##", "      # "],
                    'back': [_F, _F, _F, _F, _F, _F, "# ## # #"],
                    'hat_front': [_F, "## #  ##", "#      #"],
                    'hat_side': [_F, _F, "## ## ##", "#  #  # "],
                    'hat_back': [_F, _F, _F, "## ## ##", "# ## ## ", " #  #  #"],
                    'hat_top': [_F] * 8},
    'short_bob': {'fam': 'smooth',
                  'front': [_F, _F],
                  'side': [_F] * 7,
                  'back': [_F] * 7,
                  'hat_front': [_F, _F, _E, _E, _E, "#      #", "#      #"],
                  'hat_side': [_F, _F, _F, _F, _F, _F, " ## # ##"],
                  'hat_back': [_F, _F, _F, _F, _F, _F, "# ## ## "],
                  'hat_top': [_F] * 8},
    'long_straight': {'fam': 'smooth', 'part': 3,
                      'front': [_F, "###  ###", "#      #"],
                      'side': [_F] * 8,
                      'back': [_F] * 8,
                      'hat_front': [_F, "### ####", "#      #", _E, _E, "#      #", "#      #", "#      #"],
                      'hat_side': [_F] * 8,
                      'hat_back': [_F] * 8,
                      'hat_top': [_F] * 8},
    'twin_buns': {'fam': 'smooth',
                  'front': [_F, "## ## ##", "#      #"],
                  'side': [_F, _F, _F, "##   ###", "#     ##", "      ##"],
                  'back': [_F, _F, _F, _F, _F, "# #### #"],
                  'hat_front': [_F, "#  ##  #"],
                  'hat_side': ["##      ", "#       "],
                  'hat_back': [_F, "# #  # #"]},
    'bun': {'fam': 'combed', 'part': 4,
            'front': [_F, "#      #"],
            'side': [_F, _F, _F, "##   ###", "#    ###", "     ###", "      ##"],
            'back': [_F, _F, _F, _F, _F, _F, " ###### "],
            'hat_front': [_F, "#       ", "#       "],
            'hat_side': [_F]},
    'bald_mustache': {'fam': 'combed',
                      'side': [_E, _E, "  ######", "     ###", "#    ###", "#    ###", "      ##"],
                      'back': [_E, _E, _F, _F, _F, _F, " ###### "],
                      'hat_side': [_E, _E, _E, "      # ", "     # #"],
                      'hat_back': [_E, _E, _E, "# #  # #", " # ## # "]},
    'short_messy': {'fam': 'spiky',
                    'front': [_F, "   # ###", "      ##"],
                    'side': [_F, _F, _F, "#   ####", "#    ###", "      ##"],
                    'back': [_F, _F, _F, _F, _F, "# # ## #", " #   # #"],
                    'hat_front': ["## # ###", "     ###", "      ##"],
                    'hat_side': ["# # # # ", "## ## ##", "#  #   #"],
                    'hat_back': ["# # # # ", " # # # #", _F, "# ## # #", " #  #  #", "#  #  # "],
                    'hat_top': ["# ## # #", _F, " # ## ##", _F, "## # ## ", _F, " ## # ##", "# #  # #"]},
}


# beard texels on the face front: (x, y, l = light / b = base / d = dark)
BEARD_FRONT = [(0, 5, 'b'), (1, 5, 'd'), (6, 5, 'd'), (7, 5, 'b'),
               (2, 5, 'b'), (3, 5, 'l'), (4, 5, 'l'), (5, 5, 'b'),          # moustache under the nose
               (0, 6, 'd'), (1, 6, 'b'), (2, 6, 'd'), (5, 6, 'd'), (6, 6, 'b'), (7, 6, 'd'),
               (0, 7, 'b'), (1, 7, 'l'), (2, 7, 'b'), (3, 7, 'd'), (4, 7, 'b'), (5, 7, 'b'), (6, 7, 'l'), (7, 7, 'b')]

# brow texels for the figure's right brow (face x 0..2), mirrored for the left one: (x, y, shade)
BROWS = {
    'kind': [(0, 2, 0.4), (1, 1, 0.0), (2, 1, 0.2)],
    'serene': [(0, 2, 0.3), (1, 2, 0.0), (2, 2, 0.3)],
    'gentle': [(1, 2, 0.3), (2, 2, 0.0)],
    'cheerful': [(0, 1, 0.2), (1, 1, 0.0), (2, 1, 0.0)],
    'stern': [(0, 1, 0.0), (1, 2, -0.3), (2, 2, -0.6), (1, 1, 0.3)],
    'noble': [(0, 2, 0.2), (1, 1, 0.0), (2, 2, 0.2)],
    'weary': [(0, 2, 0.0), (1, 2, 0.0), (2, 2, -0.2)],
    'earnest': [(0, 2, 0.0), (1, 2, -0.2), (2, 2, -0.2)],
    'sad': [(0, 2, 0.3), (1, 2, 0.0), (2, 1, -0.2)],
}


def paint_skin(sid, style, role=None):
    s = Skin(sid, style, role)
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
