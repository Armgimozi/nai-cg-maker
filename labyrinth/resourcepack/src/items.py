"""Item pipeline: items.yml entry → 3D model (or 2D icon) + UV atlas (+ animation) + item definition."""
from __future__ import annotations

import io
import json

from PIL import Image

from . import displays, effects, icons
from . import shapes_armor as A
from . import shapes_weapons as W
from .materials import Look, RARITY_LEVEL, make_shader
from .model import Model
from .util import stable_seed

NS = 'labyrinth'


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=False, compress_level=9)
    return buf.getvalue()


def jdump(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + '\n').encode('utf-8')


def strip(frames):
    w, h = frames[0].size
    out = Image.new('RGBA', (w, h * len(frames)), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        out.paste(fr, (0, h * k))
    return out


def frames_differ(frames):
    first = frames[0].tobytes()
    return any(fr.tobytes() != first for fr in frames[1:])


class ItemResult:
    def __init__(self, iid):
        self.iid = iid
        self.files: dict[str, bytes] = {}
        self.previews = []       # (label, model|None, faces_uv|None, frame0 image, kind)
        self.anim_frames = None  # list of (model, faces_uv, frames) for the GIF preview
        self.warnings: list[str] = []
        self.expect_frames = {}  # texture path -> frame count


def classify(it):
    shape = (it.get('model') or {}).get('shape') or 'icon'
    t = it.get('type')
    if shape in W.TEMPLATES or shape in W.BOWS:
        return 'weapon', shape
    if shape in A.HELMETS:
        return 'helmet', shape
    if shape in A.BODY:
        return 'body', shape
    if shape in A.SHIELDS:
        return 'shield', shape
    if shape in A.ACCESSORIES:
        return 'accessory', shape
    if shape == 'icon':
        return 'icon', shape
    # unknown → nearest sensible default (GDD §14: warn + fallback)
    if t == 'weapon':
        return 'weapon', 'longsword'
    if t == 'armor':
        slot = it.get('armor_slot')
        return {'head': ('helmet', 'helm_knight'), 'chest': ('body', 'chestplate'), 'legs': ('body', 'leggings'),
                'feet': ('body', 'boots'), 'offhand': ('shield', 'kite_shield')}.get(slot, ('body', 'chestplate'))
    if t == 'accessory':
        return 'accessory', 'charm'
    return 'icon', 'icon'


def _anim_params(tex):
    frames = int(tex.get('frames') or 8)
    frames = max(4, min(16, frames))
    ft = int(tex.get('frametime') or 2)
    ft = max(1, min(4, ft))
    return frames, ft, tex.get('effect') or 'rune_flow'


def _mcmeta(frametime, effect):
    a = {'frametime': frametime}
    if effect in effects.INTERPOLATE:
        a['interpolate'] = True
    return jdump({'animation': a})


def _bake_and_write(res: ItemResult, m: Model, name: str, look: Look, tex: dict, animated: bool, seed: int, label=None):
    ref = f'{NS}:item/{name}'
    baked = m.bake(make_shader(look), ref)
    frame0 = baked.frame()
    tex_path = f'assets/{NS}/textures/item/{name}.png'
    if animated:
        n, ft, eff = _anim_params(tex)
        if eff not in effects.KNOWN:
            res.warnings.append(f'{res.iid}: unknown effect {eff!r} → rune_flow')
        frames = effects.animate(baked.texels, eff, n, look, seed, baked.frame)
        if not frames_differ(frames):
            for t in baked.texels:
                t.glow = True
            frames = effects.animate(baked.texels, 'holy_pulse', n, look, seed, baked.frame)
            res.warnings.append(f'{res.iid}: effect {eff} produced static frames; used holy_pulse fallback')
        res.files[tex_path] = png_bytes(strip(frames))
        res.files[tex_path + '.mcmeta'] = _mcmeta(ft, eff)
        res.expect_frames[tex_path] = n
        res.anim_frames = (m, baked.faces_uv, frames)
        frame0 = frames[0]
    else:
        res.files[tex_path] = png_bytes(frame0)
    res.files[f'assets/{NS}/models/item/{name}.json'] = jdump(baked.model_json())
    res.previews.append((label or name, m, baked.faces_uv, frame0))
    return baked


def item_definition(iid, bow=False):
    if not bow:
        return {'model': {'type': 'minecraft:model', 'model': f'{NS}:item/{iid}'}}
    return {'model': {
        'type': 'minecraft:condition',
        'property': 'minecraft:using_item',
        'on_false': {'type': 'minecraft:model', 'model': f'{NS}:item/{iid}'},
        'on_true': {
            'type': 'minecraft:range_dispatch',
            'property': 'minecraft:use_duration',
            'scale': 0.05,
            'entries': [
                {'threshold': 0.65, 'model': {'type': 'minecraft:model', 'model': f'{NS}:item/{iid}_pulling_1'}},
                {'threshold': 0.9, 'model': {'type': 'minecraft:model', 'model': f'{NS}:item/{iid}_pulling_2'}},
            ],
            'fallback': {'type': 'minecraft:model', 'model': f'{NS}:item/{iid}_pulling_0'},
        },
    }}


def build_item(iid: str, it: dict) -> ItemResult:
    res = ItemResult(iid)
    tex = it.get('texture') or {}
    mdl = it.get('model') or {}
    rarity = it.get('rarity') or 'common'
    seed = stable_seed('item', iid)
    look = Look(tex.get('palette'), tex.get('style'), rarity, seed)
    kind, shape = classify(it)
    if shape != (mdl.get('shape') or 'icon'):
        res.warnings.append(f'{iid}: unknown model.shape {mdl.get("shape")!r} → {shape}')
    animated = bool(tex.get('animated'))
    length = max(0.6, min(1.4, float(mdl.get('length') or 1.0)))
    spec = {'level': RARITY_LEVEL.get(rarity, 0), 'length': length, 'style': look.style, 'rarity': rarity}

    if kind == 'icon':
        style = tex.get('style')
        if style not in icons.ICON_STYLES:
            res.warnings.append(f'{iid}: unknown icon style {style!r} → generic')
        ic = icons.Icon(look)
        icons.draw(ic, style, seed)
        texels = ic.texels()
        tex_path = f'assets/{NS}/textures/item/{iid}.png'
        if animated:
            n, ft, eff = _anim_params(tex)
            frames = effects.animate(texels, eff, n, look, seed, lambda vfn: icons.frame_from(texels, vfn))
            if not frames_differ(frames):
                for t in texels:
                    if t.role != 'outline':
                        t.glow = True
                frames = effects.animate(texels, 'holy_pulse', n, look, seed, lambda vfn: icons.frame_from(texels, vfn))
            res.files[tex_path] = png_bytes(strip(frames))
            res.files[tex_path + '.mcmeta'] = _mcmeta(ft, eff)
            res.expect_frames[tex_path] = n
            img0 = frames[0]
        else:
            img0 = icons.frame_from(texels)
            res.files[tex_path] = png_bytes(img0)
        res.files[f'assets/{NS}/models/item/{iid}.json'] = jdump(
            {'parent': 'minecraft:item/generated', 'textures': {'layer0': f'{NS}:item/{iid}'}})
        res.files[f'assets/{NS}/items/{iid}.json'] = jdump(item_definition(iid))
        res.previews.append((iid, None, None, img0))
        return res

    if kind == 'weapon' and shape in W.BOWS:
        variants = [(-1, iid)] + [(k, f'{iid}_pulling_{k}') for k in range(3)]
        for pull, name in variants:
            m = Model(name)
            W.bow(m, spec, shape, pull)
            m.fit_into_limits()
            displays.bow(m)
            b = _bake_and_write(res, m, name, look, tex, animated, seed, label=name if pull < 0 else None)
            if pull >= 0:
                res.previews.pop()   # keep the sheet compact: resting bow only
        res.files[f'assets/{NS}/items/{iid}.json'] = jdump(item_definition(iid, bow=True))
        return res

    m = Model(iid)
    if kind == 'weapon':
        W.TEMPLATES[shape](m, spec)
        m.fit_into_limits()
        displays.weapon(m, two_handed=shape in W.TWO_HANDED)
    elif kind == 'helmet':
        A.HELMETS[shape](m, spec)
        m.fit_into_limits()
        displays.helmet(m)
    elif kind == 'body':
        A.BODY[shape](m, spec)
        m.fit_into_limits()
        displays.miniature(m)
    elif kind == 'shield':
        A.SHIELDS[shape](m, spec)
        m.fit_into_limits()
        displays.shield(m)
    else:
        A.ACCESSORIES[shape](m, spec)
        m.fit_into_limits()
        displays.trinket(m)
    _bake_and_write(res, m, iid, look, tex, animated, seed)
    res.files[f'assets/{NS}/items/{iid}.json'] = jdump(item_definition(iid))
    return res
