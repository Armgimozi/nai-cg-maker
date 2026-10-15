"""Extra item definitions merged into items.yml for the pack build (0.3.5 new gear, before P3 lands).

The pack reads item ids, model shapes and palettes from the plugin's content/items.yml.  The 0.3.5 weapons
(106) and armour sets (6 sets, 24 pieces) are designed in `labyrinth/tools/data/035/gear_spec.json` and reach
items.yml only through P3's content generator.  Until then this module feeds their model/texture blocks to the
pack so every new id already has its item model, palette, equipment layer and helmet.

    generate.py --extra-items auto       (default) merge only while items.yml has none of the extra ids;
                                         once P3 wrote them, items.yml is the single source again (no-op)
    generate.py --extra-items off        items.yml only
    generate.py --extra-items FILE[,..]  always merge FILE (ids missing from items.yml; items.yml wins)

FILE is either gear_spec.json (`weapons` + `armor_sets.<id>.pieces_items`) or a YAML/JSON document in
items.yml form ({items: {...}, sets: {...}}).  Only what the pack reads is kept; spec-only keys (`_spec`,
`direction`, `source`, `model.palette/notes/hold/new_silhouette/style`) are dropped.
"""
from __future__ import annotations

import json
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.normpath(os.path.join(HERE, '..', '..', 'tools', 'data', '035', 'gear_spec.json'))
SPEC_ONLY = ('_spec', 'direction', 'source')
MODEL_SPEC_ONLY = ('palette', 'notes', 'hold', 'new_silhouette', 'style')


def _clean(it: dict) -> dict:
    out = {k: v for k, v in it.items() if k not in SPEC_ONLY and not k.startswith('_')}
    if isinstance(out.get('model'), dict):
        out['model'] = {k: v for k, v in out['model'].items() if k not in MODEL_SPEC_ONLY}
    return out


def load(path: str) -> tuple[dict, dict]:
    """→ (items, sets) in items.yml form."""
    with open(path, encoding='utf-8') as f:
        doc = json.load(f) if path.endswith('.json') else (yaml.safe_load(f) or {})
    items, sets = {}, {}
    if 'weapons' in doc or 'armor_sets' in doc:          # gear_spec.json
        for iid, it in (doc.get('weapons') or {}).items():
            items[iid] = _clean(it)
        for sid, s in (doc.get('armor_sets') or {}).items():
            for pid in s.get('pieces') or []:
                items[pid] = _clean((s.get('pieces_items') or {})[pid])
            sets[sid] = {k: s[k] for k in ('name', 'look', 'back', 'pieces', 'bonuses') if k in s}
    else:                                                # items.yml form
        for iid, it in (doc.get('items') or {}).items():
            items[iid] = _clean(it)
        sets = dict(doc.get('sets') or {})
    return items, sets


def merge(items: dict, sets: dict, mode: str = 'auto') -> dict:
    """Merge extra definitions into `items` / `sets` in place.  → report {source, added, sets, skipped, note}."""
    rep = {'source': None, 'added': [], 'sets': [], 'skipped': 0, 'note': ''}
    mode = (mode or 'auto').strip()
    if mode == 'off':
        rep['note'] = 'off'
        return rep
    paths = [DEFAULT] if mode == 'auto' else [p for p in mode.split(',') if p]
    for path in paths:
        if not os.path.exists(path):
            if mode != 'auto':
                raise FileNotFoundError(path)
            rep['note'] = f'no {path}'
            continue
        ex_items, ex_sets = load(path)
        rep['source'] = path if rep['source'] is None else rep['source'] + ',' + path
        if mode == 'auto' and (set(ex_items) & set(items) or set(ex_sets) & set(sets)):
            # P3 already put (some of) these into items.yml → items.yml is the single source of truth
            rep['skipped'] += len(ex_items)
            rep['note'] = 'items.yml already has 0.3.5 gear — extras not merged'
            continue
        for iid, it in ex_items.items():
            if iid in items:
                rep['skipped'] += 1
                continue
            items[iid] = it
            rep['added'].append(iid)
        for sid, s in ex_sets.items():
            if sid not in sets:
                sets[sid] = s
                rep['sets'].append(sid)
    return rep
