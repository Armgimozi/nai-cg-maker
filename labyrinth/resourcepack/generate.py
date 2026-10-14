#!/usr/bin/env python3
"""Labyrinth (미궁 라비린스) resource-pack generator.

    python3 generate.py [--content DIR] [--out DIR] [--no-preview]

Reads the plugin's content YAML (single source of truth), procedurally generates every model,
texture, icon, animation and equipment layer (all original — nothing copied from vanilla or third
parties), validates the result and writes a deterministic dist/labyrinth-pack.zip (+ SHA-1).

Builders are a simple registry (BUILDERS); each receives the shared Ctx and adds files.  New
generator modules (mobs, UI glyphs, NPC skins, more fx styles) register themselves the same way.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import yaml
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src import equipment, fx_models, items, pack, render, validate  # noqa: E402
from src.materials import Look  # noqa: E402
from src.util import stable_seed  # noqa: E402

NS = 'labyrinth'


class Ctx:
    def __init__(self, content_dir, out_dir, preview):
        self.content_dir = content_dir
        self.out_dir = out_dir
        self.preview = preview
        self.files: dict[str, bytes] = {}
        self.warnings: list[str] = []
        self.expect_frames: dict[str, int] = {}
        self.content: dict = {}
        self.item_previews = []    # (label, model|None, faces_uv|None, frame0)
        self.anim_previews = []    # (label, model, faces_uv, frames)
        self.fx_previews = []
        self.fx_names: list[str] = []
        self.armor_previews = []   # (label, hum, leg)
        self.stats: dict[str, int] = {}

    def load(self, name):
        path = os.path.join(self.content_dir, f'{name}.yml')
        if not os.path.exists(path):
            return {}
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def add(self, path, data: bytes):
        if path in self.files and self.files[path] != data:
            self.warnings.append(f'file written twice with different content: {path}')
        self.files[path] = data


# ───────────────────────────── builders ─────────────────────────────

def build_core(ctx: Ctx):
    ctx.add('pack.mcmeta', pack.pack_mcmeta())
    ctx.add('pack.png', items.png_bytes(pack.pack_png()))
    ctx.add('assets/minecraft/atlases/items.json', pack.items_atlas())


def build_items(ctx: Ctx):
    data = ctx.content['items']
    n3d = n2d = nanim = 0
    for iid, it in data.items():
        res = items.build_item(iid, it)
        for p, b in res.files.items():
            ctx.add(p, b)
        ctx.warnings.extend(res.warnings)
        ctx.expect_frames.update(res.expect_frames)
        ctx.item_previews.extend(res.previews)
        if res.anim_frames:
            m, uv, frames = res.anim_frames
            ctx.anim_previews.append((iid, m, uv, frames))
            nanim += 1
        if res.previews and res.previews[0][1] is None:
            n2d += 1
        else:
            n3d += 1
    ctx.stats.update({'items': len(data), 'items_3d': n3d, 'items_2d': n2d, 'items_animated': nanim})


def build_equipment(ctx: Ctx):
    data = ctx.content['items']
    sets = ctx.content.get('sets') or {}
    chest_of = {}
    for iid, it in data.items():
        s = it.get('armor_set')
        if s and (it.get('armor_slot') == 'chest' or s not in chest_of):
            if it.get('armor_slot') == 'chest' or s not in chest_of:
                chest_of[s] = it
    for s in sorted(chest_of):
        it = chest_of[s]
        tex = it.get('texture') or {}
        look = Look(tex.get('palette'), tex.get('style'), it.get('rarity'), stable_seed('set', s))
        kind = (sets.get(s) or {}).get('look') or 'heavy'
        hum, leg = equipment.paint_set(look, kind, stable_seed('set', s))
        ctx.add(f'assets/{NS}/textures/entity/equipment/humanoid/{s}.png', items.png_bytes(hum))
        ctx.add(f'assets/{NS}/textures/entity/equipment/humanoid_leggings/{s}.png', items.png_bytes(leg))
        ctx.add(f'assets/{NS}/equipment/{s}.json', items.jdump({'layers': {
            'humanoid': [{'texture': f'{NS}:{s}'}],
            'humanoid_leggings': [{'texture': f'{NS}:{s}'}],
        }}))
        ctx.armor_previews.append((s, hum, leg))
    ctx.stats['armor_sets'] = len(chest_of)


FX_STYLES = {'slash', 'shockwave', 'orb', 'tether', 'projectile'}


def build_weapon_fx(ctx: Ctx):
    """FX models for weapon skills (+ every other fx.yml model of the same styles)."""
    fxm = (ctx.content.get('fx') or {}).get('models') or {}
    needed = set()
    for it in ctx.content['items'].values():
        for ws in it.get('weapon_skills') or []:
            f = (ws.get('params') or {}).get('fx')
            if f:
                needed.add(f)
    names = sorted(n for n, d in fxm.items() if (d or {}).get('style') in FX_STYLES)
    missing = sorted(needed - set(fxm))
    for n in missing:
        ctx.warnings.append(f'weapon skill fx {n!r} not defined in fx.yml — generated as generic orb')
    for name in names + missing:
        d = fxm.get(name) or {'style': 'orb', 'palette': ['#202040', '#6060c0', '#c0c0ff', '#ffffff']}
        spec = fx_models.FxSpec(name, d)
        m, fn = fx_models.build(spec)
        fx_models.finalize_display(m)
        ref = f'{NS}:fx/{name}'
        baked = m.bake(lambda c: ([(0, 0, 0)], 0, (0, 0, 0), 0), ref)
        frames = [baked.frame(lambda t, f=f: (lambda r: (r[0], 0, r[1]))(fn(t, f))) for f in range(spec.frames)]
        tp = f'assets/{NS}/textures/fx/{name}.png'
        if spec.frames > 1:
            if not items.frames_differ(frames):
                ctx.warnings.append(f'fx {name}: frames identical')
            ctx.add(tp, items.png_bytes(items.strip(frames)))
            ctx.add(tp + '.mcmeta', items.jdump({'animation': {'frametime': spec.frametime}}))
            ctx.expect_frames[tp] = spec.frames
        else:
            ctx.add(tp, items.png_bytes(frames[0]))
        ctx.add(f'assets/{NS}/models/fx/{name}.json', items.jdump(baked.model_json()))
        ctx.add(f'assets/{NS}/items/fx/{name}.json',
                items.jdump({'model': {'type': 'minecraft:model', 'model': ref}}))
        ctx.fx_previews.append((name, m, baked.faces_uv, frames[0]))
    ctx.fx_names = sorted(needed)
    ctx.stats['fx_models'] = len(names) + len(missing)


BUILDERS = [build_core, build_items, build_equipment, build_weapon_fx]


# ───────────────────────────── previews ─────────────────────────────

def _cell(model, uv, frame0, ppu=6, key='gui'):
    if model is None:
        return frame0.resize((16 * ppu, 16 * ppu), Image.NEAREST)
    return render.render(model, uv, frame0, model.display.get(key) or model.display.get('fixed'), ppu=ppu)


def write_previews(ctx: Ctx):
    os.makedirs(ctx.out_dir, exist_ok=True)
    cells = [(_cell(m, uv, fr), label) for (label, m, uv, fr) in ctx.item_previews]
    render.grid(cells, 16, 96, title=f'Labyrinth items: {len(cells)} (GUI view, frame 0)').convert('RGB').save(
        os.path.join(ctx.out_dir, 'preview_items.png'))
    if ctx.fx_previews:
        cells = [(_cell(m, uv, fr), label) for (label, m, uv, fr) in ctx.fx_previews]
        render.grid(cells, 14, 96, title=f'FX models: {len(cells)} (GUI view, frame 0)').convert('RGB').save(
            os.path.join(ctx.out_dir, 'preview_fx.png'))
    heads = [(label, m, uv, fr) for (label, m, uv, fr) in ctx.item_previews
             if m is not None and 'head' in m.display and m.display['head'].get('scale') == [1.0, 1.0, 1.0]]
    if heads:
        skin = (196, 150, 118)
        head_box = ((1.6, 1.6, 1.6), (14.4, 14.4, 14.4), skin)
        cells = []
        for (label, m, uv, fr) in heads:
            for rot in ((18, 200, 0), (12, 120, 0)):
                tr = {'rotation': list(rot), 'translation': [0, -1.5, 0], 'scale': [0.62, 0.62, 0.62]}
                cells.append((render.render(m, uv, fr, tr, ppu=6, solids=[head_box]), label))
        render.grid(cells, 12, 96, title='Helmets worn (3D model on a stand-in head, HEAD transform = identity)').convert(
            'RGB').save(os.path.join(ctx.out_dir, 'preview_helmets_worn.png'))
    if ctx.armor_previews:
        cells = []
        for (s, hum, leg) in ctx.armor_previews:
            sheet = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            sheet.alpha_composite(hum, (0, 0))
            sheet.alpha_composite(leg, (0, 32))
            cells.append((sheet.resize((256, 256), Image.NEAREST), s))
        render.grid(cells, 4, 256, title='Equipment layers (top: humanoid, bottom: humanoid_leggings)').convert('RGB').save(
            os.path.join(ctx.out_dir, 'preview_armor.png'))
    if ctx.anim_previews:
        nmax = max(len(fr) for (_, _, _, fr) in ctx.anim_previews)
        per = [[render.render(m, uv, fr, m.display['gui'], ppu=5) for fr in frames]
               for (_, m, uv, frames) in ctx.anim_previews]
        labels = [l for (l, _, _, _) in ctx.anim_previews]
        gif_frames = []
        for f in range(nmax):
            cells = [(per[k][f % len(per[k])], labels[k]) for k in range(len(per))]
            gif_frames.append(render.grid(cells, 10, 80).convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255))
        gif_frames[0].save(os.path.join(ctx.out_dir, 'preview_anim.gif'), save_all=True,
                           append_images=gif_frames[1:], duration=100, loop=0, disposal=2)


# ───────────────────────────── main ─────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description='Labyrinth resource pack generator')
    ap.add_argument('--content', default=os.path.join(HERE, '..', 'plugin', 'src', 'main', 'resources', 'content'))
    ap.add_argument('--out', default=os.path.join(HERE, 'dist'))
    ap.add_argument('--no-preview', action='store_true')
    args = ap.parse_args(argv)
    t0 = time.time()
    ctx = Ctx(os.path.abspath(args.content), os.path.abspath(args.out), not args.no_preview)
    for name in ('items', 'fx', 'mobs', 'bosses', 'npcs', 'classes'):
        ctx.content[name] = ctx.load(name)
    ctx.content['sets'] = ctx.content['items'].get('sets') or {}
    ctx.content['items'] = ctx.content['items'].get('items') or {}
    for b in BUILDERS:
        b(ctx)
    rep = validate.validate(ctx.files, ctx.content, ctx.expect_frames, ctx.fx_names)
    os.makedirs(ctx.out_dir, exist_ok=True)
    zpath = os.path.join(ctx.out_dir, 'labyrinth-pack.zip')
    sha = pack.write_zip(ctx.files, zpath)
    with open(os.path.join(ctx.out_dir, 'labyrinth-pack.sha1'), 'w') as f:
        f.write(sha + '\n')
    if ctx.preview:
        write_previews(ctx)
    for w in ctx.warnings:
        print('warning:', w)
    print('stats:', ', '.join(f'{k}={v}' for k, v in ctx.stats.items()), f'files={len(ctx.files)}',
          f'models_checked={rep.checked}')
    print(f'zip: {zpath} ({os.path.getsize(zpath) // 1024} KiB)')
    print(f'sha1: {sha}')
    print(f'time: {time.time() - t0:.1f}s')
    if rep.errors:
        for e in rep.errors[:200]:
            print('ERROR:', e)
        print(f'VALIDATION FAILED: {len(rep.errors)} error(s)')
        return 1
    print('validation: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
