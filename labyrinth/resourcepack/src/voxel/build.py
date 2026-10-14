"""Voxel item pipeline: design → shade → mesh → palette texture (+ animated strip) → model JSON."""
from __future__ import annotations

from .. import effects
from .core import Grid, frame_fn, mesh, model_json, shade
from .palette import GLOW_MATS, ramps_for


class VoxelOut:
    def __init__(self):
        self.model_json = None
        self.frames = []        # list of palette images (1 = static)
        self.vm = None
        self.stats = {}


def finish(name, grid: Grid, look, theme, ref, vs, origin, animated=False, effect='rune_flow', frames=8,
           seed=0, display=None, max_elements=720, emission=12):
    """Shade + mesh a grid; reduce colour noise if the element budget is exceeded."""
    ramps = ramps_for(look, theme)
    # keep every element inside the legal −16..32 model box
    for key in list(grid.vox):
        for a in range(3):
            lo = origin[a] + (key[a] - 0.5) * vs
            hi = origin[a] + (key[a] + 0.5) * vs
            if lo < -15.9 or hi > 31.9:
                grid.vox.pop(key, None)
                break
    noise = 1.0
    cell = 2 if animated else 999
    vm = None
    for attempt in range(5):
        sh = shade(grid, ramps, GLOW_MATS, noise_mul=noise)
        vm = mesh(name, sh, ramps, vs=vs, origin=origin, glow_cell=cell, emission=emission)
        if len(vm.model.els) <= max_elements:
            break
        noise *= 0.55
        if attempt >= 2 and animated:
            cell = 3 if cell == 2 else 4
    if display:
        display(vm.model)
    out = VoxelOut()
    out.vm = vm
    ff = frame_fn(vm)
    if animated:
        fr = effects.animate(vm.texels, effect, frames, look, seed, ff)
        if all(f.tobytes() == fr[0].tobytes() for f in fr[1:]):
            for t in vm.texels:
                t.glow = True
            fr = effects.animate(vm.texels, 'holy_pulse', frames, look, seed, ff)
        out.frames = fr
    else:
        out.frames = [ff()]
    out.model_json = model_json(vm, ref)
    out.stats = {'elements': len(vm.model.els), 'voxels': len(grid), 'palette': vm.size}
    return out
