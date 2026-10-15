"""Self-validation of the assembled pack (ARCHITECTURE §8)."""
from __future__ import annotations

import io
import json
import re

from PIL import Image

from . import armor_pieces as AP
from .materials import norm_style
from .voxel.weapons import BOWS as VW_BOWS
from .voxel.weapons import theme_of

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
    path_ok = re.compile(r'[a-z0-9_.\-/]+')
    for path in files:
        # 마인크래프트 리소스 경로 규칙: assets/ 아래는 소문자·숫자·_ . - / 만 (대문자 하나면 그 폰트/모델 전체가 거부됨)
        if path.startswith('assets/') and not path_ok.fullmatch(path):
            rep.err(f'invalid resource path (lowercase a-z0-9/._- only): {path}')
        if path.endswith('.json') or path.endswith('.mcmeta'):
            try:
                json.loads(files[path].decode('utf-8'))
            except Exception as e:  # noqa: BLE001
                rep.err(f'bad JSON {path}: {e}')
    items = content['items']
    for iid, it in items.items():
        check_item_definition(files, f'assets/{NS}/items/{iid}.json', rep, expect_frames)
        shape = (it.get('model') or {}).get('shape')
        if shape in VW_BOWS:
            for k in range(3):
                if f'assets/{NS}/models/item/{iid}_pulling_{k}.json' not in files:
                    rep.err(f'{iid}: missing pulling_{k} model')
    sets = set()
    themes = {}
    for iid, it in items.items():
        if it.get('armor_set'):
            sets.add(it['armor_set'])
            # 세트 부위는 한 테마로 칠한다 (THEME_KEYS 에 키가 빠지면 style 따라 부위마다 갈린다)
            style = norm_style((it.get('texture') or {}).get('style'))
            themes.setdefault(it['armor_set'], {})[iid] = theme_of(iid, style)
    for s in sorted(sets):
        if len(set(themes[s].values())) > 1:
            rep.err(f'equipment {s}: pieces use different voxel themes {themes[s]} (voxel/weapons.py THEME_KEYS)')
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
    validate_armor_pieces(files, content, rep, expect_frames)
    validate_mobs_npcs_fx(files, content, rep, expect_frames)
    return rep


def validate_armor_pieces(files, content, rep, expect_frames):
    """3D shoulder/back pieces (ArmorPieceLayout model contract): every set with a chest piece has
    items/armor_piece/<set>/<part>.json for shoulder_l·shoulder_r·back → own model + texture, display.fixed identity
    (the plugin's Transformation does all the placing), element count within AP.ELEMENT_LIMIT, and no stray sets."""
    specs = AP.set_specs(content['items'], content.get('sets') or {})
    for sid in specs:
        for part in AP.PARTS:
            base = f'armor_piece/{sid}/{part}'
            ipath = f'assets/{NS}/items/{base}.json'
            d = _json(files, ipath, rep)
            if d is None:
                continue
            ref = (d.get('model') or {}).get('model')
            if ref != f'{NS}:{base}':
                rep.err(f'{ipath}: model {ref!r} != {NS}:{base}')
                continue
            check_item_definition(files, ipath, rep, expect_frames)
            mpath = f'assets/{NS}/models/{base}.json'
            if mpath not in files:
                continue
            m = json.loads(files[mpath].decode('utf-8'))
            if (m.get('textures') or {}).get('0') != f'{NS}:{base}':
                rep.err(f'{mpath}: texture #0 must be {NS}:{base}')
            n = len(m.get('elements') or [])
            if n > AP.ELEMENT_LIMIT:
                rep.err(f'{mpath}: {n} elements > {AP.ELEMENT_LIMIT} (keep worn pieces light)')
            fx = (m.get('display') or {}).get('fixed') or {}
            if (fx.get('rotation') or [0, 0, 0]) != [0, 0, 0] or (fx.get('translation') or [0, 0, 0]) != [0, 0, 0] \
                    or (fx.get('scale') or [1, 1, 1]) != [1, 1, 1]:
                rep.err(f'{mpath}: display.fixed must be identity (ArmorPieceLayout places the piece)')
    prefix = f'assets/{NS}/items/armor_piece/'
    for path in files:
        if path.startswith(prefix):
            sid, _, part = path[len(prefix):].rpartition('/')
            if sid not in specs or part[:-5] not in AP.PARTS:
                rep.err(f'{path}: no chest piece of set {sid!r} / unknown part (stale armour piece)')


def _fixed_ok(files, model_ref, rep):
    """ARCHITECTURE §2: display.fixed must be rotation 0 / translation 0 / uniform scale ≥ 1 (1/s restore)."""
    ns, p = model_ref.split(':', 1)
    path = f'assets/{ns}/models/{p}.json'
    if path not in files:
        return
    m = json.loads(files[path].decode('utf-8'))
    fx = (m.get('display') or {}).get('fixed')
    if not fx:
        rep.err(f'{path}: missing display.fixed')
        return
    if any(abs(v) > 1e-6 for v in fx.get('rotation', [0, 0, 0]) + fx.get('translation', [0, 0, 0])):
        rep.err(f'{path}: display.fixed must have zero rotation/translation')
    sc = fx.get('scale', [1, 1, 1])
    if len(set(sc)) != 1 or sc[0] < 1 - 1e-6:
        rep.err(f'{path}: display.fixed scale {sc} must be uniform and ≥ 1')


def validate_mobs_npcs_fx(files, content, rep, expect_frames):
    # mob / boss parts: item definition + model + shared atlas
    for coll in ('mobs', 'bosses'):
        data = (content.get(coll) or {}).get(coll) or {}
        for mid, d in data.items():
            parts = ((d or {}).get('model') or {}).get('parts') or []
            if not parts:
                rep.err(f'{coll} {mid}: no model parts')
            names = [p.get('name') for p in parts]
            if len(names) != len(set(names)):
                rep.err(f'{coll} {mid}: duplicate part names {names}')
            tex = f'assets/{NS}/textures/mob/{mid}.png'
            if tex not in files:
                rep.err(f'{coll} {mid}: missing atlas {tex}')
            for p in parts:
                ref = f'{NS}:mob/{mid}/{p.get("name")}'
                check_item_definition(files, f'assets/{NS}/items/mob/{mid}/{p.get("name")}.json', rep, expect_frames)
                _fixed_ok(files, ref, rep)
                mp = f'assets/{NS}/models/mob/{mid}/{p.get("name")}.json'
                if mp in files:
                    m = json.loads(files[mp].decode('utf-8'))
                    if (m.get('textures') or {}).get('0') != f'{NS}:mob/{mid}':
                        rep.err(f'{mp}: must use the shared atlas {NS}:mob/{mid}')
    # NPC skins: 64×64, opaque base layer
    base_rects = [(0, 0, 32, 16), (0, 16, 56, 32), (16, 48, 48, 64)]
    for nid, d in ((content.get('npcs') or {}).get('npcs') or {}).items():
        sid = (d or {}).get('skin') or nid
        img = _png(files, f'assets/{NS}/textures/entity/npc/{sid}.png', rep)
        if img is None:
            continue
        if img.size != (64, 64):
            rep.err(f'npc skin {sid}: size {img.size} != 64x64')
            continue
        im = img.convert('RGBA')
        px = im.load()
        # head/body/arm/leg base faces (not the unused corners) must be opaque
        holes = 0
        for (x0, y0, x1, y1) in base_rects:
            for y in range(y0, y1):
                for x in range(x0, x1):
                    used = not ((y < 8 or 16 <= y < 20 or 48 <= y < 52) and
                                (x in range(0, 8) or x in range(24, 32) or x in range(0, 4) or x in range(12, 20)
                                 or x in range(36, 44) or x in range(52, 56) or x in range(28, 36) or x in range(44, 48)))
                    if used and px[x, y][3] == 0 and y >= 8:
                        holes += 1
        if holes > 40:
            rep.err(f'npc skin {sid}: {holes} transparent base-layer pixels')
    # every fx.yml model
    for name in sorted(((content.get('fx') or {}).get('models') or {})):
        check_item_definition(files, f'assets/{NS}/items/fx/{name}.json', rep, expect_frames)
        _fixed_ok(files, f'{NS}:fx/{name}', rep)
    # every aura's ring/secondary model must exist
    for aid, a in (((content.get('fx') or {}).get('auras')) or {}).items():
        for key in ('ring_model', 'secondary_model'):
            ref = (a or {}).get(key)
            if ref and f'assets/{NS}/items/fx/{ref}.json' not in files:
                rep.err(f'aura {aid}: {key} {ref} has no fx model')


def validate_ui(files, glyphs_doc, rep):
    """Font labyrinth:ui: provider files exist with the declared height, ascent <= height, unique chars, space
    range, GUI backgrounds 176 x (114 + rows*18) and menu slot maps inside the chest."""
    glyphs = (glyphs_doc or {}).get('glyphs') or {}
    if not glyphs:
        return
    font = _json(files, f'assets/{NS}/font/ui.json', rep)
    if font is None:
        return
    seen = {}
    space_seen = False
    for prov in font.get('providers') or []:
        t = prov.get('type')
        if t == 'space':
            space_seen = True
            for ch, v in (prov.get('advances') or {}).items():
                if len(ch) != 1 or ord(ch) != 0xF800 + int(v):
                    rep.err(f'font ui: space {ch!r} → {v} breaks the U+F800+v rule')
            continue
        if t != 'bitmap':
            rep.err(f'font ui: unexpected provider type {t}')
            continue
        ref = prov.get('file', '')
        ns, p = ref.split(':', 1)
        img = _png(files, f'assets/{ns}/textures/{p}', rep)
        h, a = prov.get('height', 8), prov.get('ascent')
        if a is None or a > h:
            rep.err(f'font ui: {ref} ascent {a} > height {h}')
        if img is not None and img.size[1] != h:
            rep.err(f'font ui: {ref} is {img.size[1]} px tall, provider height {h} (glyph would be rescaled)')
        for row in prov.get('chars') or []:
            for ch in row:
                if ch in seen:
                    rep.err(f'font ui: U+{ord(ch):04X} declared twice ({seen[ch]} / {ref})')
                seen[ch] = ref
                if 0xF400 <= ord(ch) <= 0xF8FF:
                    rep.err(f'font ui: glyph U+{ord(ch):04X} inside the reserved space range')
    if not space_seen:
        rep.err('font ui: no space provider')
    for gid, g in glyphs.items():
        ch = (g or {}).get('char')
        if ch not in seen:
            rep.err(f'glyph {gid}: char not in font ui.json')
    for mid, m in ((glyphs_doc.get('menus') or {}).items()):
        gid = (m or {}).get('glyph')
        rows = (m or {}).get('rows', 6)
        g = glyphs.get(gid)
        if not g:
            rep.err(f'menu {mid}: glyph {gid} not defined')
            continue
        if g.get('height') != 114 + rows * 18 or g.get('ascent') != 13:
            rep.err(f'menu {mid}: {gid} must be height {114 + rows * 18} / ascent 13 for a {rows}-row chest')
        if g.get('advance') != 177:
            rep.err(f'menu {mid}: {gid} advance {g.get("advance")} != 177 (menuTitle offsets assume 176 px)')
        for name, v in ((m or {}).get('slots') or {}).items():
            vals = v if isinstance(v, list) else [v] if isinstance(v, int) else []
            for s in vals:
                if isinstance(s, int) and not (0 <= s < rows * 9):
                    rep.err(f'menu {mid}: slot {name}={s} outside a {rows}-row chest')
