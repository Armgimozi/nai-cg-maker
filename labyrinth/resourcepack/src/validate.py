"""Self-validation of the assembled pack (ARCHITECTURE §8)."""
from __future__ import annotations

import io
import json
import re

from PIL import Image

from . import equipment as EQ
from . import shapes_weapons as W2D
from .materials import norm_style
from .voxel import weapons as VW
from .voxel.weapons import BOWS as VW_BOWS
from .voxel.weapons import theme_of

NS = 'labyrinth'


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checked = 0
        self.stats: dict = {}    # measured values worth printing with the build stats

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
        layers = {}
        for layer in ('humanoid', 'humanoid_leggings'):
            img = _png(files, f'assets/{NS}/textures/entity/equipment/{layer}/{s}.png', rep)
            if img is not None and img.size != (64, 32):
                rep.err(f'equipment {s} {layer}: size {img.size} != 64x32')
            elif img is not None:
                layers[layer] = img.convert('RGBA')
        if len(layers) == 2:
            check_equipment_cover(s, ((content.get('sets') or {}).get(s) or {}).get('look'), layers, rep)
    validate_shapes(items, rep)
    for name in fx_names:
        check_item_definition(files, f'assets/{NS}/items/fx/{name}.json', rep, expect_frames)
    validate_mobs_npcs_fx(files, content, rep, expect_frames)
    return rep


def check_equipment_cover(sid, look, layers, rep):
    """빈틈 없는 갑옷: 각 층이 맡은 면(equipment.coverage_regions)의 텍셀이 모두 불투명해야 한다 — 하나라도 비면
    그 자리로 피부가 비친다 (0.3.4 의 _cover 규칙)."""
    kind = look if look in ('heavy', 'light', 'cloth') else 'heavy'
    holes = 0
    for (layer, part, face), row0 in EQ.coverage_regions(kind).items():
        img = layers['humanoid' if layer == 'hum' else 'humanoid_leggings']
        x0, y0, w, h = EQ._rect(part, face)
        for j in range(row0, h):
            for i in range(w):
                if img.getpixel((x0 + i, y0 + j))[3] == 0:
                    holes += 1
    rep.checked += 1
    if holes:
        rep.err(f'equipment {sid}: {holes} transparent texel(s) on faces the armour must cover (skin shows through)')


def validate_shapes(items, rep):
    """손에 드는 표 (voxel/weapons.py): 활·양손·옆 머리·HOLD 가 실제 모양만 가리키는지, 무기마다 모양이 있는지,
    무기 id 가 테마 키(THEME_KEYS)를 품는지(아니면 texture.style 로 테마가 정해진다 — 경고)."""
    known = set(VW.TEMPLATES)
    for name, tab in (('TWO_HANDED', VW.TWO_HANDED), ('HEAD_SHAPES', VW.HEAD_SHAPES), ('HOLD', VW.HOLD)):
        for sh in tab:
            if sh not in known:
                rep.err(f'voxel/weapons.py {name}: {sh!r} is not a weapon template')
    for sh, h in VW.HOLD.items():
        bad = set(h) - {'fp_yaw', 'fp_mul'}
        if bad:
            rep.err(f'voxel/weapons.py HOLD[{sh!r}]: unknown keys {sorted(bad)}')
    for sh in VW.BOWS:
        if sh not in VW.BOW_CURV:
            rep.err(f'voxel/weapons.py BOWS: {sh!r} has no BOW_CURV entry')
        if sh in known:
            rep.err(f'voxel/weapons.py: {sh!r} is both a bow and a melee template')
    all_shapes = known | set(VW.BOWS) | set(W2D.TEMPLATES) | set(W2D.BOWS)
    no_theme = []
    for iid, it in items.items():
        if it.get('type') != 'weapon':
            continue
        shape = (it.get('model') or {}).get('shape')
        if shape not in all_shapes:
            rep.err(f'{iid}: weapon model.shape {shape!r} unknown (pack would fall back to longsword)')
        if not any(VW._key_in(k, iid) for _, keys in VW.THEME_KEYS for k in keys):
            no_theme.append(iid)
    rep.stats['weapons_style_theme'] = len(no_theme)
    if no_theme:
        rep.warnings.append(f'{len(no_theme)} weapon id(s) carry no THEME_KEYS key (theme from texture.style): '
                            + ', '.join(sorted(no_theme)[:12]) + (' …' if len(no_theme) > 12 else ''))


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
    validate_rig(files, content, rep)
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


RIG_LEG_FORMS = {'leg_pair': 2, 'leg_quad': 4, 'leg_six': 6, 'leg_eight': 8}


def _part_bounds(files, mid, name):
    """Entity-local bounds (blocks, relative to the part pivot: +X = mob left, +Z = front) of a part model → (lo, hi)."""
    path = f'assets/{NS}/models/mob/{mid}/{name}.json'
    if path not in files:
        return None
    m = json.loads(files[path].decode('utf-8'))
    k = float(((m.get('display') or {}).get('fixed') or {}).get('scale', [1, 1, 1])[0])
    pts = [p for e in m.get('elements') or [] for p in (e['from'], e['to'])]
    if not pts:
        return None
    q = [((8 - p[0]) * k / 16, (p[1] - 8) * k / 16, (8 - p[2]) * k / 16) for p in pts]
    return tuple(min(v[a] for v in q) for a in range(3)), tuple(max(v[a] for v in q) for a in range(3))


def validate_rig(files, content, rep):
    """Rig contract (GDD §14.6): part sets cut from one design, joints, feet, element budgets."""
    from .voxel.mob_build import PER_PART, budget_for
    for coll in ('mobs', 'bosses'):
        data = (content.get(coll) or {}).get(coll) or {}
        for mid, d in data.items():
            parts = ((d or {}).get('model') or {}).get('parts') or []
            total = 0
            for p in parts:
                path = f'assets/{NS}/models/mob/{mid}/{p.get("name")}.json'
                if path in files:
                    ne = len(json.loads(files[path].decode('utf-8')).get('elements') or [])
                    total += ne
                    if ne > PER_PART:
                        rep.err(f'{coll} {mid}/{p.get("name")}: {ne} elements > {PER_PART} per part')
            budget = budget_for((d or {}).get('rank'), coll == 'bosses')
            if total > budget:
                rep.err(f'{coll} {mid}: {total} elements > budget {budget}')
            sets = {}
            for p in parts:
                if p.get('set'):
                    sets.setdefault(p['set'], []).append(p)
                j = p.get('joint')
                if j is not None and (not isinstance(j, list) or len(j) != 3):
                    rep.err(f'{coll} {mid}/{p.get("name")}: joint must be [x, y, z]')
                f = p.get('foot')
                if f is not None and (not isinstance(f, list) or len(f) not in (3, 4)):
                    rep.err(f'{coll} {mid}/{p.get("name")}: foot must be [dx, dy, dz(, half)]')
            names = {p.get('name') for p in parts}
            for sname, ms in sets.items():
                tag = f'{coll} {mid} set {sname}'
                if sname in names:
                    rep.err(f'{tag}: a part has the set name itself')
                first = ms[0]
                for q in ms[1:]:
                    for key in ('form', 'anim', 'size', 'pivot'):
                        if q.get(key) != first.get(key):
                            rep.err(f'{tag}: {q.get("name")} {key} {q.get(key)} != {first.get(key)} (members share the design part)')
                form, anim = first.get('form'), first.get('anim')
                if form in RIG_LEG_FORMS and anim == 'legs_walk' and len(ms) != RIG_LEG_FORMS[form]:
                    rep.err(f'{tag}: {form} needs {RIG_LEG_FORMS[form]} legs, has {len(ms)}')
                if form == 'wing_pair' and (len(ms) != 2 or anim != 'wings_flap'):
                    rep.err(f'{tag}: a wing pair is 2 parts with anim wings_flap')
                piv = [float(v) for v in first.get('pivot') or [0, 0, 0]]
                sides = [0, 0]
                box = None
                for q in ms:
                    b = _part_bounds(files, mid, q.get('name'))
                    if b is None:
                        rep.err(f'{tag}: {q.get("name")} has no elements')
                        continue
                    box = b if box is None else (tuple(min(box[0][a], b[0][a]) for a in range(3)),
                                                 tuple(max(box[1][a], b[1][a]) for a in range(3)))
                for q in ms:
                    j = [float(v) for v in q.get('joint') or piv]
                    if q.get('joint') is None:
                        rep.err(f'{tag}: {q.get("name")} has no joint')
                    if j[0] > 1e-6:
                        sides[0] += 1
                    elif j[0] < -1e-6:
                        sides[1] += 1
                    if box is not None:
                        rel = [j[a] - piv[a] for a in range(3)]
                        if any(rel[a] < box[0][a] - 1 / 16 or rel[a] > box[1][a] + 1 / 16 for a in range(3)):
                            rep.err(f'{tag}: {q.get("name")} joint {j} outside the set geometry')
                    if anim == 'legs_walk' and form in RIG_LEG_FORMS and not q.get('foot'):
                        rep.err(f'{tag}: {q.get("name")} (leg) has no foot')
                if sides[0] != sides[1]:
                    rep.err(f'{tag}: {sides[0]} left / {sides[1]} right members (joint X sign)')
            # a leg set left as one part walks as one block (the "legs stuck together" bug)
            for p in parts:
                if p.get('anim') == 'legs_walk' and p.get('form') in RIG_LEG_FORMS and not p.get('set'):
                    rep.err(f'{coll} {mid}/{p.get("name")}: {p.get("form")} with legs_walk must be cut into one part per leg (set)')
                if p.get('form') == 'wing_pair' and not p.get('set'):
                    rep.err(f'{coll} {mid}/{p.get("name")}: a wing pair must be cut into wing_l / wing_r (set)')


# ───────────────────────────── 0.3.6 광산 (계약 tools/data/036) ─────────────────────────────
BLOCK_OVERRIDE = re.compile(r'^assets/[^/]+/(blockstates/|models/block/|textures/block/)')


def _elements(files, model_ref):
    ns, p = model_ref.split(':', 1)
    path = f'assets/{ns}/models/{p}.json'
    if path not in files:
        return None
    return json.loads(files[path].decode('utf-8')).get('elements') or []


def validate_mine(files, content, contract, rep, mine_ids=(), aliases=None, nodes=None):
    """계약 §3.8 · §8 Q4: 아이콘·곡괭이·보석 결정·옛 id 별칭·메뉴 배경·NPC 스킨 + 팩이 블록을 하나도 안 바꿈."""
    vis = (contract or {}).get('visual') or {}
    items = content.get('items') or {}
    # 팩은 블록을 바꾸지 않는다 (광맥 = 바닐라 블록): blockstates · models/block · textures/block 0개
    bad = sorted(p for p in files if BLOCK_OVERRIDE.match(p))
    rep.checked += 1
    rep.stats['block_overrides'] = len(bad)
    if bad:
        rep.err(f'pack overrides {len(bad)} block asset(s) (contract §3.3: zero): ' + ', '.join(bad[:5]))
    if not vis:
        rep.warnings.append('tools/data/036/visual.json not found — 0.3.6 mine asset checks skipped')
        return
    # 아이콘·곡괭이: 모든 계약 id 에 아이템 정의 + 모델
    for iid in mine_ids:
        rep.checked += 1
        path = f'assets/{NS}/items/{iid}.json'
        if path not in files:
            rep.err(f'mine item {iid}: missing {path}')
            continue
        it = items.get(iid) or {}
        want = (vis.get('icons') or {}).get(iid) or (vis.get('pickaxes') or {}).get(iid)
        have = (it.get('texture') or {}).get('style')
        if want and have and have != want.get('style'):
            rep.warnings.append(f'mine item {iid}: items.yml style {have!r} ≠ contract {want.get("style")!r}')
        if (it.get('model') or {}).get('shape', 'icon') == 'icon':
            img = _png(files, f'assets/{NS}/textures/item/{iid}.png', rep)
            if img is not None and img.size[0] != 32:
                rep.err(f'mine icon {iid}: {img.size} (icons are 32 px wide)')
    picks = vis.get('pickaxes') or {}
    worst = {}
    for iid, pk in picks.items():
        rep.checked += 1
        it = items.get(iid) or {}
        if (it.get('model') or {}).get('shape') != 'pickaxe':
            rep.err(f'pickaxe {iid}: model.shape {(it.get("model") or {}).get("shape")!r} (contract: pickaxe)')
        els = _elements(files, f'{NS}:item/{iid}')
        if els is None:
            rep.err(f'pickaxe {iid}: no model')
            continue
        budget = int(pk.get('element_budget') or 380)
        worst[iid] = len(els)
        if len(els) > budget:
            rep.err(f'pickaxe {iid}: {len(els)} elements > budget {budget}')
        m = json.loads(files[f'assets/{NS}/models/item/{iid}.json'].decode('utf-8'))
        for ctx_name in ('firstperson_righthand', 'thirdperson_righthand', 'gui', 'fixed'):
            if ctx_name not in (m.get('display') or {}):
                rep.err(f'pickaxe {iid}: display.{ctx_name} missing (held model = displays.voxel_weapon)')
    rep.stats['pickaxe_elements'] = '/'.join(str(worst[k]) for k in picks if k in worst)
    # 보석 노드 결정: visual.json gem_nodes 의 6개, ≤ 300 요소, 바닥이 모델 y = 8 (ItemDisplay 원점 = 블록 면)
    want_nodes = ((vis.get('gem_nodes') or {}).get('models')) or {}
    counts = []
    for key, d in want_nodes.items():
        rep.checked += 1
        ref = f'{NS}:item/mine/{key}'
        check_item_definition(files, f'assets/{NS}/items/mine/{key}.json', rep, {})
        els = _elements(files, ref)
        if not els:
            rep.err(f'gem node {key}: no model')
            continue
        counts.append(len(els))
        cap = min(300, int(d.get('element_budget') or 300))
        if len(els) > cap:
            rep.err(f'gem node {key}: {len(els)} elements > {cap}')
        lo = min(e['from'][1] for e in els)
        if not 7.0 <= lo <= 8.5:
            rep.err(f'gem node {key}: base at model y {lo} (must sit on the block face, y = 8)')
        if d.get('glow') and not any(e.get('light_emission') for e in els):
            rep.err(f'gem node {key}: contract glow=true but no emissive element')
    rep.stats['gem_node_elements'] = '/'.join(map(str, counts))
    # 옛 재료 별칭 (두 판): items/<옛 id>.json → 새 id 의 모델
    mat = (contract or {}).get('materials') or {}
    retired = set((mat.get('retired') or {})) | set(((mat.get('conversion') or {}).get('map')) or {})
    for old in sorted(retired):
        rep.checked += 1
        if old in items:
            continue
        new = (aliases or {}).get(old)
        path = f'assets/{NS}/items/{old}.json'
        if not new or path not in files:
            rep.err(f'retired id {old}: no alias item definition (contract §2.10: keep two versions)')
            continue
        refs = set()

        def walk(n):
            if isinstance(n, dict):
                if 'model' in n and isinstance(n['model'], str):
                    refs.add(n['model'])
                for v in n.values():
                    walk(v)
        walk(json.loads(files[path].decode('utf-8')))
        if refs != {f'{NS}:item/{new}'}:
            rep.err(f'retired id {old}: alias points at {sorted(refs)} (want {NS}:item/{new})')
    # 메뉴 배경 (glyphs.yml menus) · NPC 스킨
    menus = (content.get('glyphs') or {}).get('menus') or {}
    for mid, md in (vis.get('menus') or {}).items():
        gid = (md or {}).get('glyph') or ''
        if not gid.startswith('gui_') or ' ' in gid:
            continue                                      # 'gui_merchant (재사용)' 같은 설명 줄
        rep.checked += 1
        if (menus.get(mid) or {}).get('glyph') != gid:
            rep.err(f'menu {mid}: glyphs.yml menus.{mid}.glyph must be {gid} (contract visual.json menus)')
        elif (menus.get(mid) or {}).get('rows') != md.get('rows'):
            rep.err(f'menu {mid}: rows {(menus.get(mid) or {}).get("rows")} ≠ contract {md.get("rows")}')
    for role, d in (vis.get('npcs') or {}).items():
        if isinstance(d, dict) and d.get('skin'):
            rep.checked += 1
            if f'assets/{NS}/textures/entity/npc/{d["skin"]}.png' not in files:
                rep.err(f'npc {role}: skin {d["skin"]} not painted')
