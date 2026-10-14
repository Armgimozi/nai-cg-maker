"""Material colour ramps for voxel designs, derived from an item's palette (Look) + theme."""
from __future__ import annotations

from ..util import darken, hue_shift, lighten, lum, mix, saturate

THEME_HUE = {
    'vine': (70, 150, 50), 'fungi': (200, 110, 170), 'web': (210, 215, 225), 'water': (60, 170, 200),
    'forge': (255, 120, 30), 'frost': (150, 215, 255), 'crystal': (170, 110, 255), 'ink': (60, 90, 170),
    'clock': (110, 220, 190), 'abyss': (40, 220, 205), 'holy': (255, 215, 120), 'storm': (170, 210, 255),
    'blood': (220, 30, 60), 'plain': (160, 170, 180),
}


def _r(base, n=7):
    out = []
    for k in range(n):
        t = k / (n - 1) * (len(base) - 1)
        i = min(int(t), len(base) - 2)
        out.append(mix(base[i], base[i + 1], t - i))
    return out


def vivid(look):
    """Most saturated palette colour (creature / accent body colour)."""
    cols = look.pal.raw
    return max(cols, key=lambda c: (max(c) - min(c)) + (40 if 0.15 < lum(c) < 0.8 else 0))


def ramps_for(look, theme):
    p = look.pal
    a = p.accent
    v = vivid(look)
    th = THEME_HUE.get(theme, THEME_HUE['plain'])
    light = p.light
    blade_base = list(p.ramp)
    if look.style not in ('crystal', 'gold', 'holy', 'copper', 'bone'):
        # blades read as forged metal (silver-white like a real edge), tinted by the item palette
        mid = p.ramp[len(p.ramp) // 2]
        # pass 2: blades carry more of the item's own colour (darker, themed metals like the reference)
        k = 0.55 if look.style in ('wood', 'leather', 'cloth', 'moss', 'silk', 'steel') else 0.3
        blade_base = [darken(mix(mid, (40, 44, 52), k), 0.4), mix(mid, (96, 102, 114), k), mix(mid, (156, 162, 174), k),
                      mix(light, (214, 220, 228), k), mix(light, (244, 246, 250), 0.7)]
    blade = _r([darken(blade_base[0], 0.3)] + blade_base + [lighten(blade_base[-1], 0.35)], 8)
    edge = _r([blade[3], blade[5], lighten(blade[6], 0.3), lighten(blade[7], 0.6), (255, 255, 255)], 6)
    creature = v if lum(v) < 0.85 else mix(th, v, 0.4)
    if theme in ('abyss', 'blood', 'water', 'storm'):
        creature = hue_shift(creature, {'abyss': 40, 'blood': -8, 'water': 25, 'storm': 30}[theme], 1.1, 0.95)
    r = {
        'blade': blade,
        'edge': edge,
        'fuller': _r([darken(blade[1], 0.4), blade[1], blade[3], blade[4]], 5),
        'metal': _r(look.metal, 7),
        'orn': _r([darken(look.orn[0], 0.3)] + list(look.orn) + [lighten(look.orn[-1], 0.4)], 8),
        'grip': _r(look.grip, 6),
        'wood': _r(look.wood, 7),
        'gem': _r([darken(a, 0.7), darken(a, 0.4), saturate(a, 1.2), lighten(a, 0.35), lighten(a, 0.7), (255, 255, 255)], 7),
        'glow': _r([darken(a, 0.45), saturate(a, 1.15), lighten(a, 0.3), lighten(a, 0.6), lighten(a, 0.85), (255, 255, 255)], 7),
        'crystal': _r([darken(a, 0.75), darken(a, 0.5), darken(a, 0.22), a, lighten(a, 0.4), lighten(a, 0.75)], 7),
        'scale': _r([darken(creature, 0.85), darken(creature, 0.65), darken(creature, 0.42), darken(creature, 0.18),
                     creature, lighten(creature, 0.3), lighten(creature, 0.55)], 8),
        'belly': _r([darken(light, 0.55), darken(mix(light, (230, 215, 180), 0.5), 0.3), mix(light, (235, 220, 190), 0.5),
                     lighten(light, 0.35)], 6),
        'fin': _r([darken(a, 0.6), darken(a, 0.3), a, lighten(a, 0.4), lighten(a, 0.7)], 6),
        'vine': _r([darken(th, 0.8), darken(th, 0.6), darken(th, 0.38), darken(th, 0.15), th, lighten(th, 0.3)], 7),
        'leaf': _r([darken(th, 0.6), darken(th, 0.35), mix(th, (120, 200, 80), 0.3), lighten(th, 0.25),
                    lighten(th, 0.55)], 6),
        'feather': _r([darken(mix(light, th, 0.5), 0.55), darken(mix(light, th, 0.4), 0.3), mix(light, th, 0.3),
                       lighten(mix(light, th, 0.25), 0.4), lighten(mix(light, th, 0.15), 0.75)], 7),
        'bone': _r(look.horn, 7),
        'dark': _r(look.dark, 5),
        'flame': _r([(90, 20, 6), (170, 44, 10), (232, 96, 18), (255, 160, 40), (255, 214, 110), (255, 248, 210)], 7)
        if theme != 'abyss' else _r([darken(th, 0.8), darken(th, 0.5), th, lighten(th, 0.4), lighten(th, 0.8)], 7),
        'ice': _r([(30, 56, 96), (64, 112, 168), (120, 176, 224), (176, 222, 252), (224, 246, 255), (255, 255, 255)], 7),
        'paper': _r([(96, 80, 56), (150, 130, 96), (204, 188, 150), (232, 222, 196), (250, 246, 232)], 6),
        'ink': _r([(4, 4, 10), (14, 18, 36), (28, 38, 76), (56, 76, 136), (96, 120, 190)], 6),
        'shell': _r([(80, 52, 56), (150, 100, 96), (214, 162, 146), (244, 210, 192), (255, 240, 230)], 6),
        'fungus': _r([darken(th, 0.75), darken(th, 0.45), th, lighten(th, 0.35), lighten(th, 0.7)], 6),
        'tendril': _r([(4, 4, 8), darken(th, 0.88), darken(th, 0.7), darken(th, 0.5), darken(th, 0.25), th], 7),
        'eye': _r([darken(a, 0.5), a, lighten(a, 0.5), (255, 255, 255)], 5),
        'string': _r(look.string, 4),
        'cloth': _r([darken(p.ramp[0], 0.3)] + list(p.ramp), 7),
        'leather': _r(look.grip, 6),
        'plate': _r([darken(p.ramp[0], 0.35)] + list(p.ramp) + [lighten(light, 0.3)], 8),
    }
    return r


GLOW_MATS = ('glow', 'eye')
