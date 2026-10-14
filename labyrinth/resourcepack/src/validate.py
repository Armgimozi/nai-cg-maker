"""Self-validation of the assembled pack (ARCHITECTURE §8)."""
from __future__ import annotations

import io
import json

from PIL import Image

NS = 'labyrinth'


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.checked = 0

    def err(self, msg):
        self.errors.append(msg)


def _json(files, path, rep):
    if path not in files:
        rep.err(f'missing {path}')
        return None
    try:
        return json.loads(files[path].decode('utf-8'))
    except Exception as e:  # noqa: BLE001
        rep.err(f'bad JSON {path}: {e}')
        return None


def _png(files, path, rep):
    if path not in files:
        rep.err(f'missing {path}')
        return None
    try:
        return Image.open(io.BytesIO(files[path]))
    except Exception as e:  # noqa: BLE001
        rep.err(f'bad PNG {path}: {e}')
        return None


def _tex_path(ref):
    ns, p = ref.split(':', 1) if ':' in ref else ('minecraft', ref)
    return f'assets/{ns}/textures/{p}.png'


def check_model(files, model_ref, rep, expect_frames):
    ns, p = model_ref.split(':', 1)
    path = f'assets/{ns}/models/{p}.json'
    m = _json(files, path, rep)
    if m is None:
        return
    rep.checked += 1
    if 'parent' in m and m['parent'].startswith('minecraft:'):
        for k, ref in (m.get('textures') or {}).items():
            img = _png(files, _tex_path(ref), rep)
            if img and (img.size[0] != img.size[1] and img.size[1] % img.size[0] != 0):
                rep.err(f'{path}: texture {ref} has invalid size {img.size}')
        return
    texs = m.get('textures') or {}
    if '0' not in texs:
        rep.err(f'{path}: no texture #0')
        return
    tp = _tex_path(texs['0'])
    img = _png(files, tp, rep)
    if img is not None:
        w, h = img.size
        if w & (w - 1):
            rep.err(f'{tp}: width {w} not power of two')
        if h % w:
            rep.err(f'{tp}: height {h} not a multiple of width {w}')
        frames = h // w
        meta = tp + '.mcmeta'
        if frames > 1:
            mm = _json(files, meta, rep)
            if mm is not None and 'animation' not in mm:
                rep.err(f'{meta}: no animation block')
            if tp in expect_frames and expect_frames[tp] != frames:
                rep.err(f'{tp}: {frames} frames, expected {expect_frames[tp]}')
            if frames > 1:
                first = img.crop((0, 0, w, w)).tobytes()
                if all(img.crop((0, k * w, w, (k + 1) * w)).tobytes() == first for k in range(1, frames)):
                    rep.err(f'{tp}: animation frames are identical')
        elif meta in files:
            rep.err(f'{meta}: present but texture is a single frame')
    els = m.get('elements') or []
    if not els:
        rep.err(f'{path}: no elements')
    for e in els:
        for key in ('from', 'to'):
            for v in e[key]:
                if v < -16 or v > 32:
                    rep.err(f'{path}: element {key} {e[key]} outside −16..32')
                    break
        le = e.get('light_emission', 0)
        if not (isinstance(le, int) and 0 <= le <= 15):
            rep.err(f'{path}: light_emission {le}')
        for fname, face in (e.get('faces') or {}).items():
            uv = face.get('uv')
            if not uv or any(u < 0 or u > 16 for u in uv):
                rep.err(f'{path}: bad uv {uv} on {fname}')
    for ctx, tr in (m.get('display') or {}).items():
        for t in tr.get('translation', []):
            if abs(t) > 80:
                rep.err(f'{path}: display {ctx} translation {t} beyond ±80')
        for s in tr.get('scale', []):
            if s > 4:
                rep.err(f'{path}: display {ctx} scale {s} > 4')


def check_item_definition(files, path, rep, expect_frames):
    d = _json(files, path, rep)
    if d is None:
        return

    def walk(node):
        if isinstance(node, dict):
            if node.get('type') in ('minecraft:model', 'model') and 'model' in node:
                check_model(files, node['model'], rep, expect_frames)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(d)


def validate(files: dict, content: dict, expect_frames: dict, fx_names=()) -> Report:
    rep = Report()
    _json(files, 'pack.mcmeta', rep)
    if 'pack.png' not in files:
        rep.err('missing pack.png')
    for path in files:
        if path.endswith('.json') or path.endswith('.mcmeta'):
            try:
                json.loads(files[path].decode('utf-8'))
            except Exception as e:  # noqa: BLE001
                rep.err(f'bad JSON {path}: {e}')
    items = content['items']
    for iid, it in items.items():
        check_item_definition(files, f'assets/{NS}/items/{iid}.json', rep, expect_frames)
        shape = (it.get('model') or {}).get('shape')
        if shape in ('longbow', 'recurve_bow', 'composite_bow'):
            for k in range(3):
                if f'assets/{NS}/models/item/{iid}_pulling_{k}.json' not in files:
                    rep.err(f'{iid}: missing pulling_{k} model')
    sets = set()
    for iid, it in items.items():
        if it.get('armor_set'):
            sets.add(it['armor_set'])
    for s in sorted(sets):
        eq = _json(files, f'assets/{NS}/equipment/{s}.json', rep)
        if eq is not None:
            layers = eq.get('layers') or {}
            for layer in ('humanoid', 'humanoid_leggings'):
                if layer not in layers:
                    rep.err(f'equipment {s}: missing layer {layer}')
        for layer in ('humanoid', 'humanoid_leggings'):
            img = _png(files, f'assets/{NS}/textures/entity/equipment/{layer}/{s}.png', rep)
            if img is not None and img.size != (64, 32):
                rep.err(f'equipment {s} {layer}: size {img.size} != 64x32')
    for name in fx_names:
        check_item_definition(files, f'assets/{NS}/items/fx/{name}.json', rep, expect_frames)
    return rep
