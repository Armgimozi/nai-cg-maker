"""Voxel mob designs.  Every module here (f01_03.py, f04_06.py, f07_08.py, f09_10.py, bosses.py, or any
other non-underscore file) defines

    DESIGNS = {mob_id: design_fn}
    design_fn(look, part_name, part_def, ctx) -> voxel.mob_kit.MobGrid | None   (None = old box model)

Modules are imported automatically; a module that fails to import is reported (stderr + build warning)
and skipped so one designer's work-in-progress never blocks the others.  See README.md.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import traceback

REGISTRY: dict = {}     # mob id → design fn
SOURCE: dict = {}       # mob id → module name
ERRORS: list = []       # import / registration problems (strings)
_loaded = False


def load(force=False):
    global _loaded
    if _loaded and not force:
        return REGISTRY
    REGISTRY.clear()
    SOURCE.clear()
    ERRORS.clear()
    for m in sorted(pkgutil.iter_modules(__path__), key=lambda q: q.name):
        if m.name.startswith('_'):
            continue
        try:
            mod = importlib.import_module(f'{__name__}.{m.name}')
            if force:
                mod = importlib.reload(mod)
        except Exception:  # noqa: BLE001
            msg = f'mobvox/{m.name}.py failed to import — its designs are skipped:\n' + traceback.format_exc(limit=4)
            ERRORS.append(msg)
            print('warning:', msg, file=sys.stderr)
            continue
        for mid, fn in (getattr(mod, 'DESIGNS', None) or {}).items():
            if mid in REGISTRY:
                ERRORS.append(f'mobvox: {mid} designed in both {SOURCE[mid]} and {m.name} — keeping {SOURCE[mid]}')
                continue
            REGISTRY[mid] = fn
            SOURCE[mid] = m.name
    _loaded = True
    return REGISTRY


def design_for(mid):
    return load().get(mid)
