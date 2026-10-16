#!/usr/bin/env python3
"""Labyrinth (미궁 라비린스) resource-pack generator.

    python3 generate.py [--content DIR] [--out DIR] [--no-preview] [--only-mobs ID,ID,...] [--compare]
                        [--extra-items off|auto|FILE,...]

--only-mobs builds just those mobs/bosses (fast design loop: no items/fx/UI, no zip, mob checks only) and
writes preview_mobs.png; --compare adds compare_mobs.png (old box model vs voxel design side by side).

--extra-items (default off) adds item definitions items.yml does not have yet, for previewing designed gear
before it lands in items.yml (src/extra_items.py): FILE,... (gear_spec.json or items.yml form) or auto (the
0.3.5 gear_spec.json, only while items.yml has none of its ids).  items.yml is the single source by default.

Reads the plugin's content YAML (single source of truth), procedurally generates every model,
texture, icon, animation and equipment layer (all original — nothing copied from vanilla or third
parties), validates the result and writes a deterministic dist/labyrinth-pack.zip (+ SHA-1).

Builders are a simple registry (BUILDERS); each receives the shared Ctx and adds files.  New
generator modules (mobs, UI glyphs, NPC skins, more fx styles) register themselves the same way.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import yaml
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src import equipment, extra_items, fx_extra, fx_models, items, mobs, npc_skins, pack, render, ui, validate  # noqa: E402
from src import vanilla_gui  # noqa: E402
from src.materials import Look  # noqa: E402
from src.util import stable_seed  # noqa: E402

NS = 'labyrinth'


class Ctx:
    def __init__(self, content_dir, out_dir, preview, only_mobs=None, compare=False):
        self.only_mobs = only_mobs        # None = every mob, else a set of ids
        self.compare = compare
        self.compare_rows = []            # (id, boss, old_preview+count, new_preview+count)
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
        self.mob_previews = []     # (id, boss, assembled model, faces_uv, frame0, elements, voxel part count)
        self.npc_previews = []     # (skin id, image)
        self.stats: dict[str, int] = {}
        self.ui_errors: list[str] = []
        self.ui_info: dict = {}
        self.contract: dict = {}           # tools/data/036 visual/materials/mine.json (0.3.6 광산 계약)
        self.mine_added: list[str] = []    # items.yml 에 없어 계약 값으로 그린 광산 아이템
        self.mine_aliases: dict = {}       # 옛 재료 id → 새 id (그림 별칭)
        self.mine_gem_blocks: dict = {}    # 0.3.6.1 보석 광석 블록 그림 (결정 모델 없음)

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
        hum, leg = equipment.paint_set(look, kind, stable_seed('set', s), set_id=s)
        ctx.add(f'assets/{NS}/textures/entity/equipment/humanoid/{s}.png', items.png_bytes(hum))
        ctx.add(f'assets/{NS}/textures/entity/equipment/humanoid_leggings/{s}.png', items.png_bytes(leg))
        ctx.add(f'assets/{NS}/equipment/{s}.json', items.jdump({'layers': {
            'humanoid': [{'texture': f'{NS}:{s}'}],
            'humanoid_leggings': [{'texture': f'{NS}:{s}'}],
        }}))
        ctx.armor_previews.append((s, hum, leg))
    ctx.stats['armor_sets'] = len(chest_of)


FX_STYLES = {'slash', 'shockwave', 'orb', 'tether', 'projectile'}


def _emit_fx(ctx: Ctx, name, spec, m, fn):
    """Bake one fx model (pivot 8,8,8; display.fixed identity or 1/s) + its (animated) texture."""
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
        _emit_fx(ctx, name, spec, m, fn)
    ctx.fx_names = sorted(needed)
    ctx.stats['fx_models'] = len(names) + len(missing)


def build_fx_extra(ctx: Ctx):
    """Every other fx.yml style: aura rings, telegraphs, glyphs, runes, markers, crystals, props (src/fx_extra.py)."""
    fxm = (ctx.content.get('fx') or {}).get('models') or {}
    n = 0
    for name in sorted(fxm):
        d = fxm[name] or {}
        st = d.get('style')
        if st in FX_STYLES:
            continue
        if st not in fx_extra.EXTRA_STYLES:
            ctx.warnings.append(f'fx {name}: unknown style {st!r} — generated as a soft plate')
        spec = fx_models.FxSpec(name, d)
        m, fn = fx_extra.build(spec)
        _emit_fx(ctx, name, spec, m, fn)
        n += 1
    ctx.stats['fx_models'] = ctx.stats.get('fx_models', 0) + n


def build_mobs(ctx: Ctx):
    """3D part models + one atlas per mob/boss (src/mobs.py; voxel designs in src/mobvox)."""
    nparts = nvox = nel = 0
    for coll, boss in (('mobs', False), ('bosses', True)):
        data = (ctx.content.get(coll) or {}).get(coll) or {}
        built = 0
        for mid, d in data.items():
            if ctx.only_mobs is not None and mid not in ctx.only_mobs:
                continue
            res = mobs.build_mob(mid, d or {}, boss, items.jdump, items.png_bytes, items.strip)
            for p, b in res.files.items():
                ctx.add(p, b)
            ctx.warnings.extend(res.warnings)
            if res.frames > 1:
                ctx.expect_frames[res.texture_path] = res.frames
            if res.preview:
                ctx.mob_previews.append((mid, boss) + res.preview + (res.elements, len(res.voxel_parts)))
            if ctx.compare:
                old = mobs.build_mob(mid, d or {}, boss, items.jdump, items.png_bytes, items.strip, mode='old')
                ctx.compare_rows.append((mid, boss, old, res))
            nparts += len(res.parts)
            nvox += len(res.voxel_parts)
            nel += res.elements
            built += 1
        ctx.stats[coll] = built
    ctx.stats['mob_parts'] = nparts
    ctx.stats['mob_voxel_parts'] = nvox
    ctx.stats['mob_elements'] = nel


def build_npcs(ctx: Ctx):
    """64×64 player-layout skins for every npcs.yml skin id (src/npc_skins.py)."""
    data = (ctx.content.get('npcs') or {}).get('npcs') or {}
    done = set()
    for nid, d in data.items():
        sid = (d or {}).get('skin') or nid
        if sid in done:
            continue
        done.add(sid)
        img, warns = npc_skins.paint_skin(sid, (d or {}).get('skin_style'))
        ctx.warnings.extend(warns)
        ctx.add(f'assets/{NS}/textures/entity/npc/{sid}.png', items.png_bytes(img))
        ctx.npc_previews.append((sid, img))
    ctx.stats['npc_skins'] = len(done)


def build_ui(ctx: Ctx):
    """Font labyrinth:ui from glyphs.yml: GUI backgrounds, HUD bars/digits, status icons, boss decor (src/ui.py)."""
    doc = ctx.content.get('glyphs') or {}
    if not doc.get('glyphs'):
        ctx.warnings.append('glyphs.yml missing or empty — no custom UI font generated')
        return
    files, warns, errs, info = ui.build(doc, ctx.content)
    for p, b in files.items():
        ctx.add(p, b)
    ctx.warnings.extend(warns)
    ctx.ui_errors.extend(errs)
    ctx.ui_info = info
    ctx.stats['ui_glyphs'] = len(info['glyphs'])
    ctx.stats['ui_spaces'] = len(info['spaces'])
    # 바닐라 하트·허기·경험치 바·방어 아이콘 숨김: 같은 경로에 투명 그림(우리 HUD 가 대신 그림).
    # 서버 리소스팩이라 이 서버에서만 적용된다. 플러그인은 허기를 가득 유지하고 바닐라 경험치를 0 으로 둔다.
    from PIL import Image as _Image
    import io as _io
    blank = _io.BytesIO(); _Image.new('RGBA', (9, 9), (0, 0, 0, 0)).save(blank, 'PNG'); blank = blank.getvalue()
    xp_blank = _io.BytesIO(); _Image.new('RGBA', (182, 5), (0, 0, 0, 0)).save(xp_blank, 'PNG'); xp_blank = xp_blank.getvalue()
    hud = 'assets/minecraft/textures/gui/sprites/hud/'
    hearts = ['container', 'container_blinking', 'container_hardcore', 'container_hardcore_blinking',
              'vehicle_container', 'vehicle_full', 'vehicle_half']
    for kind in ('', 'hardcore_', 'absorbing_', 'absorbing_hardcore_', 'frozen_', 'frozen_hardcore_',
                 'poisoned_', 'poisoned_hardcore_', 'withered_', 'withered_hardcore_'):
        for part in ('full', 'half'):
            hearts += [kind + part, kind + part + '_blinking']
    for h in hearts:
        ctx.add(hud + 'heart/' + h + '.png', blank)
    for f in ('food_empty', 'food_empty_hunger', 'food_full', 'food_full_hunger', 'food_half', 'food_half_hunger',
              'armor_empty', 'armor_full', 'armor_half'):
        ctx.add(hud + f + '.png', blank)
    for f in ('experience_bar_background', 'experience_bar_progress'):
        ctx.add(hud + f + '.png', xp_blank)
    # 바닐라 화면 테마 (핫바·십자선·보스바·툴팁·상자·인벤토리·작업대·화로·버튼…) + 등급별 툴팁 (src/vanilla_gui.py)
    vfiles, vimgs = vanilla_gui.build()
    for p, b in vfiles.items():
        ctx.add(p, b)
    ctx.ui_info['vanilla'] = vimgs
    ctx.stats['vanilla_gui'] = len(vimgs)


# ───────────────────────────── 0.3.6 광산 (계약 tools/data/036) ─────────────────────────────
# 광석·주괴·보석·곡괭이·새 몬스터 재료의 그림은 items.yml (Q3 생성기) 이 정한다 — items.yml 이 단일 원본.
# items.yml 에 아직 없는 id 만 계약 값으로 그린다 (그림·검사·check_assets 가 통합 전에도 돌게):
#   visual.json icons/pickaxes (style·palette) + materials.json items (희귀도) + 아래 MINE_EXTRA_ICONS (드롭 명세 §2).
# 새 아이콘 id 가 더 생기면 (Q3·드롭 명세) MINE_EXTRA_ICONS 에 한 줄 더하면 된다 — items.yml 에 들어가면 그쪽이 이긴다.
CONTRACT_DIR = os.path.normpath(os.path.join(HERE, '..', 'tools', 'data', '036'))
# design036/drops/drops_spec.md §2 (계약 §0-4: 드롭 명세가 재료 id 를 정한다) — id: (희귀도, 모양, 팔레트)
MINE_EXTRA_ICONS = {
    'moss_scale': ('common', 'scale', ['#14200f', '#2f4a1f', '#5f8a34', '#a8c870']),
    'tunnel_fang': ('common', 'fang', ['#241c16', '#5a4a3a', '#b8a888', '#efe6d0']),
    'cinder_scale': ('uncommon', 'scale', ['#0c0a0a', '#1e1a1a', '#363030', '#5a4a44', '#ff7a2a']),
    'ember_soul': ('uncommon', 'shard', ['#1a0a06', '#5a1a0a', '#c43c12', '#ff9a2a', '#fff0a0']),
    'rime_talon': ('uncommon', 'fang', ['#0a1428', '#1e4a7a', '#4a90d8', '#7cc4ff']),
    'chrono_dust': ('uncommon', 'dust', ['#1a140c', '#4a3a20', '#b08a40', '#f0d890', '#6ad0b0']),
    'abyss_scale': ('uncommon', 'scale', ['#020306', '#0a1a20', '#1a3c46', '#2fe0d0']),
}
# 계약 §0-4: 배포 전 id 이름 바꿈 (cinder_hide 잿불 가죽 → cinder_scale 잿불 비늘) · 옛 불씨 조각은 불씨 혼으로
MINE_RENAMED = {'cinder_hide': 'cinder_scale'}
MINE_ALIAS_OVERRIDE = {'ember_shard': 'ember_soul'}
# 옛 재료 별칭은 두 판(0.3.6·0.3.7)만 둔다 (계약 §2.10). 0.3.8 에서 이 표와 build_mine_aliases 를 지운다.
RETIRED_ALIAS_LAST = '0.3.7'


def load_contract036(path=CONTRACT_DIR):
    out = {}
    for name in ('visual', 'materials', 'mine'):
        p = os.path.join(path, f'{name}.json')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                out[name] = json.load(f)
    return out


def mine_item_ids(contract):
    """계약이 그림을 요구하는 아이템 id (이름 바꿈 반영, 순서 = 광석·주괴·보석·몬스터 재료·곡괭이)."""
    vis = contract.get('visual') or {}
    ids = [MINE_RENAMED.get(i, i) for i in (vis.get('icons') or {})]
    ids += [i for i in MINE_EXTRA_ICONS if i not in ids]
    ids += [i for i in (vis.get('pickaxes') or {}) if i not in ids]
    return ids


def mine_item_def(iid, contract):
    """items.yml 꼴 정의 (그림에 쓰는 키만): 계약 visual.json → 없으면 MINE_EXTRA_ICONS."""
    vis = contract.get('visual') or {}
    mat = (contract.get('materials') or {}).get('items') or {}
    old = next((o for o, n in MINE_RENAMED.items() if n == iid), None)
    if iid in MINE_EXTRA_ICONS:
        rarity, style, pal = MINE_EXTRA_ICONS[iid]
        return {'type': 'material', 'rarity': rarity, 'model': {'shape': 'icon'},
                'texture': {'style': style, 'palette': list(pal)}}
    icon = (vis.get('icons') or {}).get(iid) or (vis.get('icons') or {}).get(old)
    rarity = (mat.get(iid) or mat.get(old) or {}).get('rarity') or 'common'
    if icon:
        return {'type': 'material', 'rarity': rarity, 'model': {'shape': 'icon'},
                'texture': {'style': icon['style'], 'palette': list(icon['palette'])}}
    pk = (vis.get('pickaxes') or {}).get(iid)
    if pk:
        tex = {'style': pk['style'], 'palette': list(pk['palette'])}
        if pk.get('animated'):
            tex.update({'animated': True, 'effect': pk.get('effect') or 'ember_glow', 'frames': 8, 'frametime': 2})
        return {'type': 'tool', 'rarity': rarity, 'model': {'shape': pk.get('template') or 'pickaxe'}, 'texture': tex}
    return None


def merge_mine_items(items, contract):
    """items.yml 에 없는 계약 아이템을 그림용 정의로 더한다 → 더한 id 목록."""
    added = []
    for iid in mine_item_ids(contract):
        if iid in items:
            continue
        d = mine_item_def(iid, contract)
        if d is not None:
            items[iid] = d
            added.append(iid)
    return added


def retired_aliases(contract, items):
    """옛 id → 새 id (계약 materials.json retired/conversion.map + §0-4 바꿈). items.yml 에 남은 옛 id 는 빼고."""
    mat = contract.get('materials') or {}
    conv = dict(((mat.get('conversion') or {}).get('map')) or {})
    for old, r in (mat.get('retired') or {}).items():
        conv.setdefault(old, r.get('to'))
    conv.update(MINE_ALIAS_OVERRIDE)
    conv = {o: MINE_RENAMED.get(n, n) for o, n in conv.items()}
    for old, new in MINE_RENAMED.items():
        conv.setdefault(old, new)
    return {o: n for o, n in sorted(conv.items()) if o not in items}


def build_mine_aliases(ctx: Ctx):
    """옛 재료 8개 (+ 배포 전 cinder_hide) 가 바꿈 전에도 새 그림으로 보이게: items/<옛 id>.json → 새 id 의 모델."""
    al = retired_aliases(ctx.contract, ctx.content['items'])
    for old, new in al.items():
        if new not in ctx.content['items']:
            ctx.warnings.append(f'retired alias {old} → {new}: {new} has no item definition — alias skipped')
            continue
        ctx.add(f'assets/{NS}/items/{old}.json', items.jdump(items.item_definition(new)))
    ctx.mine_aliases = al
    ctx.stats['retired_aliases'] = len(al)


def build_mine_gem_blocks(ctx: Ctx):
    """0.3.6.1 보석 광석 블록 6개 (주인: "삐쭉 튀어나온 부분이 별로 … 광석 블록 텍스쳐를 네모난걸 새로"): 결정 ItemDisplay 대신
    바닐라 좀벌레 돌 6개(visual.json blocks.gems)의 blockstates 를 labyrinth:block/mine/gem_<보석> (cube_all, 16×16) 으로."""
    from src import mine_blocks
    gems = (((ctx.contract.get('visual') or {}).get('blocks') or {}).get('gems')) or {}
    if not gems:
        ctx.warnings.append('tools/data/036/visual.json blocks.gems missing — no gem ore blocks built')
    ctx.mine_gem_blocks = {}
    for gid, d in gems.items():
        block = d.get('block') or ''
        look = d.get('look') or {}
        if not block.startswith('minecraft:') or not look.get('palette'):
            ctx.warnings.append(f'gem block {gid}: no block/look in visual.json — skipped')
            continue
        ref = d.get('model') or f'{NS}:block/mine/gem_{gid}'
        tex_ref = d.get('texture') or ref
        img = mine_blocks.gem_texture(gid, look)
        tns, tpath = tex_ref.split(':', 1)
        mns, mpath = ref.split(':', 1)
        ctx.add(f'assets/{tns}/textures/{tpath}.png', items.png_bytes(img))
        ctx.add(f'assets/{mns}/models/{mpath}.json', items.jdump(mine_blocks.cube_model(tex_ref)))
        ctx.add(f'assets/minecraft/blockstates/{block.split(":", 1)[1]}.json', items.jdump(mine_blocks.blockstate(block, ref)))
        ctx.mine_gem_blocks[gid] = {'block': block, 'model': ref, 'texture': tex_ref, 'img': img, 'look': look}
    ctx.stats['mine_gem_blocks'] = len(ctx.mine_gem_blocks)


def build_mine_npcs(ctx: Ctx):
    """광부·제련공 스킨 (visual.json npcs): npcs.yml 이 아직 그 스킨을 안 부르면 계약 skin_style 로 그린다."""
    used = {(d or {}).get('skin') or nid for nid, d in ((ctx.content.get('npcs') or {}).get('npcs') or {}).items()}
    n = 0
    for role, d in ((ctx.contract.get('visual') or {}).get('npcs') or {}).items():
        if not isinstance(d, dict) or not d.get('skin') or d['skin'] in used:
            continue
        img, warns = npc_skins.paint_skin(d['skin'], d.get('skin_style'))
        ctx.warnings.extend(warns)
        ctx.add(f'assets/{NS}/textures/entity/npc/{d["skin"]}.png', items.png_bytes(img))
        ctx.npc_previews.append((d['skin'], img))
        n += 1
    ctx.stats['npc_skins'] = ctx.stats.get('npc_skins', 0) + n


BUILDERS = [build_core, build_items, build_equipment, build_weapon_fx, build_fx_extra, build_mobs,
            build_npcs, build_ui, build_mine_aliases, build_mine_gem_blocks, build_mine_npcs]


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
    write_mob_previews(ctx)
    write_mine_preview(ctx)
    if ctx.npc_previews:
        cells = []
        for (sid, img) in ctx.npc_previews:
            fig = npc_skins.preview_figure(img, 5)
            cell = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
            cell.alpha_composite(fig, ((200 - fig.size[0]) // 2, (200 - fig.size[1]) // 2))
            cells.append((cell, sid))
            cells.append((img.resize((200, 200), Image.NEAREST), sid + ' (sheet)'))
        render.grid(cells, 6, 200, title='NPC skins (front/back + 64x64 sheet)').convert('RGB').save(
            os.path.join(ctx.out_dir, 'preview_npcs.png'))
    if ctx.ui_info.get('glyphs'):
        doc = ctx.content.get('glyphs') or {}
        rows = {f'gui_{k}': (v or {}).get('rows', 6) for k, v in (doc.get('menus') or {}).items()}
        ui.preview(ctx.ui_info, rows, doc.get('hud') or {}, os.path.join(ctx.out_dir, 'preview_ui.png'))
        if ctx.ui_info.get('vanilla'):
            hud_img = ui.hud_mock_live(ctx.ui_info, doc.get('hud') or {}, ctx.ui_info['vanilla'])
            vanilla_gui.preview_screens(ctx.ui_info['vanilla'], hud_img).convert('RGB').save(
                os.path.join(ctx.out_dir, 'preview_vanilla_gui.png'))
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


def write_mine_preview(ctx: Ctx):
    """preview_mine.png: 0.3.6 광산 아이템 (4배 + 인벤토리 1배·2배 띠), 곡괭이, 0.3.6.1 보석 광석 블록, 옛 id 별칭
    + preview_mine_blocks.png (보석 블록 그림 8배 · 광산 벽 돌 사이에 놓은 3×3 · 정육면체)."""
    ids = mine_item_ids(ctx.contract)
    byid = {label: (m, uv, fr) for (label, m, uv, fr) in ctx.item_previews}
    cells, strip = [], []
    for iid in ids:
        if iid not in byid:
            continue
        m, uv, fr = byid[iid]
        cell = _cell(m, uv, fr, ppu=8)
        n = '' if m is None else f' {len(m.els)}el'
        cells.append((cell, iid + n))
        strip.append(cell)
    from src import mine_blocks
    for gid, n in ctx.mine_gem_blocks.items():
        cell = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
        cell.alpha_composite(mine_blocks.iso_cube(n['img'], 48), (16, 8))
        cells.append((cell, f"{gid} ({n['block'].split(':')[1]})"))
    for old, new in ctx.mine_aliases.items():
        if new in byid:
            m, uv, fr = byid[new]
            cells.append((_cell(m, uv, fr, ppu=8), f'{old} -> {new}'))
    if not cells:
        return
    render.grid(cells, 9, 128, title=f'0.3.6 mine: {len(ids)} items, {len(ctx.mine_gem_blocks)} gem ore blocks, '
                                      f'{len(ctx.mine_aliases)} retired-id aliases').convert('RGB').save(
        os.path.join(ctx.out_dir, 'preview_mine.png'))
    write_mine_block_preview(ctx)
    for px in (16, 32):    # 인벤토리 실제 크기 (GUI 배율 1·2), 확인용으로 3배 확대
        bar = Image.new('RGBA', (len(strip) * (px + 4) + 4, px + 8), (139, 139, 139, 255))
        for k, im in enumerate(strip):
            bar.alpha_composite(im.resize((px, px), Image.BOX), (4 + k * (px + 4), 4))
        bar.resize((bar.size[0] * 3, bar.size[1] * 3), Image.NEAREST).convert('RGB').save(
            os.path.join(ctx.out_dir, f'preview_mine_{px}px.png'))


def write_mine_block_preview(ctx: Ctx):
    """preview_mine_blocks.png: 보석 광석 블록 6개 — 그림 8배 · 광산 벽 돌(그 바탕) 사이에 놓은 3×3 (4배) · 정육면체."""
    from src import mine_blocks
    if not ctx.mine_gem_blocks:
        return
    cells = []
    for gid, n in ctx.mine_gem_blocks.items():
        cells.append((n['img'].resize((128, 128), Image.NEAREST), f'{gid} x8'))
        wall = Image.new('RGBA', (48, 48))
        base = n['look'].get('base') or 'stone'
        for gy in range(3):
            for gx in range(3):
                tile = n['img'] if (gx, gy) == (1, 1) else mine_blocks.base_stone(base, stable_seed('wall', gid, gx, gy))
                wall.alpha_composite(tile, (gx * 16, gy * 16))
        cells.append((wall.resize((128, 128), Image.NEAREST), f'{gid} on {base} wall'))
        cube = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
        cube.alpha_composite(mine_blocks.iso_cube(n['img'], 48), (16, 8))
        cells.append((cube, n['block'].split(':')[1]))
    render.grid(cells, 6, 128, title='0.3.6.1 gem ore blocks (pack repaints these vanilla blocks; no crystal models)').convert('RGB').save(
        os.path.join(ctx.out_dir, 'preview_mine_blocks.png'))


def _mob_label(mid, boss, nel, nvox):
    return f"{'[B] ' if boss else ''}{mid} {nel}el{' V' if nvox else ''}"


def write_mob_previews(ctx: Ctx):
    """preview_mobs.png (element count per cell, V = voxel design), atlases, and compare_mobs.png."""
    os.makedirs(ctx.out_dir, exist_ok=True)
    if ctx.mob_previews:
        cells = []
        for (mid, boss, pm, uv, fr, nel, nvox) in ctx.mob_previews:
            cells.append((mobs.preview_cell(pm, uv, fr, px=192), _mob_label(mid, boss, nel, nvox)))
        render.grid(cells, min(8, len(cells)), 192, label_h=12,
                    title=f'Mobs & bosses: {len(cells)} (YAML pivots, front 3/4, frame 0; Nel = elements, '
                          f'V = voxel)').convert('RGB').save(os.path.join(ctx.out_dir, 'preview_mobs.png'))
        sheets = []
        for (mid, boss, pm, uv, fr, nel, nvox) in ctx.mob_previews:
            sheets.append((fr.resize((128, 128), Image.NEAREST), mid))
        render.grid(sheets, min(12, len(sheets)), 128, title='Mob texture atlases (frame 0)').convert('RGB').save(
            os.path.join(ctx.out_dir, 'preview_mob_atlases.png'))
    if ctx.compare_rows:
        cells = []
        px = 256
        for (mid, boss, old, new) in ctx.compare_rows:
            for tag, r, rot in (('OLD', old, (18, 205, 0)), ('NEW', new, (18, 205, 0)), ('NEW back', new, (18, 25, 0)),
                                ('NEW side', new, (8, 270, 0))):
                if not r.preview:
                    continue
                pm, uv, fr = r.preview
                cells.append((mobs.preview_cell(pm, uv, fr, px=px, rot=rot),
                              f'{mid} {tag} {r.elements}el' if tag in ('OLD', 'NEW') else f'{mid} {tag}'))
        render.grid(cells, 4, px, label_h=12,
                    title='Old box model vs voxel design (front 3/4, back 3/4, side) - element counts').convert(
            'RGB').save(os.path.join(ctx.out_dir, 'compare_mobs.png'))


# ───────────────────────────── main ─────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description='Labyrinth resource pack generator')
    ap.add_argument('--content', default=os.path.join(HERE, '..', 'plugin', 'src', 'main', 'resources', 'content'))
    ap.add_argument('--out', default=os.path.join(HERE, 'dist'))
    ap.add_argument('--no-preview', action='store_true')
    ap.add_argument('--only-mobs', default=None,
                    help='comma-separated mob/boss ids: build only those (mob previews + mob checks, no zip)')
    ap.add_argument('--compare', action='store_true',
                    help='also write compare_mobs.png: old box model vs voxel design for every built mob')
    ap.add_argument('--extra-items', default='off',
                    help='off (default: items.yml only), auto (0.3.5 gear from tools/data/035/gear_spec.json while '
                         'items.yml lacks it), or comma-separated files (gear_spec.json or items.yml form)')
    args = ap.parse_args(argv)
    t0 = time.time()
    only = None
    if args.only_mobs:
        only = {s.strip() for s in args.only_mobs.split(',') if s.strip()}
    ctx = Ctx(os.path.abspath(args.content), os.path.abspath(args.out), not args.no_preview, only, args.compare)
    for name in ('items', 'fx', 'mobs', 'bosses', 'npcs', 'classes', 'glyphs', 'mine'):
        ctx.content[name] = ctx.load(name)
    ctx.content['sets'] = ctx.content['items'].get('sets') or {}
    ctx.content['items'] = ctx.content['items'].get('items') or {}
    ex = extra_items.merge(ctx.content['items'], ctx.content['sets'], args.extra_items)
    ctx.stats['extra_items'] = len(ex['added'])
    ctx.stats['extra_sets'] = len(ex['sets'])
    if ex['added'] or (ex['note'] and ex['note'] != 'off'):
        print('extra items:', ex['note'] or f"{len(ex['added'])} from {ex['source']}")
    ctx.contract = load_contract036()
    ctx.content['contract036'] = ctx.contract          # ui.py: 승강기 배경의 층 색 (content/mine.yml 이 없을 때)
    ctx.mine_added = merge_mine_items(ctx.content['items'], ctx.contract)
    ctx.stats['mine_items_from_contract'] = len(ctx.mine_added)
    if ctx.mine_added:
        print(f'mine items: {len(ctx.mine_added)} drawn from the 0.3.6 contract (items.yml lacks them)')
    if only is not None:
        return _main_only_mobs(ctx, only, t0)
    for b in BUILDERS:
        b(ctx)
    rep = validate.validate(ctx.files, ctx.content, ctx.expect_frames, ctx.fx_names)
    ctx.stats.update(rep.stats)
    ctx.warnings.extend(rep.warnings)
    rep.errors.extend(ctx.ui_errors)
    validate.validate_ui(ctx.files, ctx.content.get('glyphs') or {}, rep)
    validate.validate_mine(ctx.files, ctx.content, ctx.contract, rep, mine_item_ids(ctx.contract), ctx.mine_aliases)
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


def _main_only_mobs(ctx: Ctx, only, t0):
    """Fast design loop: core + the named mobs, mob-only validation, mob previews (no zip)."""
    known = set(((ctx.content.get('mobs') or {}).get('mobs') or {})) | \
        set(((ctx.content.get('bosses') or {}).get('bosses') or {}))
    unknown = sorted(only - known)
    if unknown:
        print('unknown mob ids:', ', '.join(unknown))
        return 2
    build_core(ctx)
    build_mobs(ctx)
    sub = {
        'mobs': {'mobs': {k: v for k, v in ((ctx.content.get('mobs') or {}).get('mobs') or {}).items() if k in only}},
        'bosses': {'bosses': {k: v for k, v in ((ctx.content.get('bosses') or {}).get('bosses') or {}).items()
                              if k in only}},
    }
    rep = validate.Report()
    validate.validate_mobs_npcs_fx(ctx.files, sub, rep, ctx.expect_frames)
    if ctx.preview:
        write_mob_previews(ctx)
    for w in ctx.warnings:
        print('warning:', w)
    for (mid, boss, pm, uv, fr, nel, nvox) in ctx.mob_previews:
        print(f'  {mid}: {nel} elements' + (f' ({nvox} voxel parts)' if nvox else ''))
    print('stats:', ', '.join(f'{k}={v}' for k, v in ctx.stats.items()), f'models_checked={rep.checked}')
    print(f'previews: {ctx.out_dir}')
    print(f'time: {time.time() - t0:.1f}s')
    if rep.errors:
        for e in rep.errors[:200]:
            print('ERROR:', e)
        print(f'VALIDATION FAILED: {len(rep.errors)} error(s)')
        return 1
    print('validation (mobs only): OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
