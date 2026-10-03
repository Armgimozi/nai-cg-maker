"""내보낸 FBX 를 다시 불러와 마네킹에 입혀 미리보기만 렌더한다(FBX 왕복 검증 겸용).

  python roblox_items/tools/render_previews.py --armor roblox_items/armor
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import armor_lib as L  # noqa: E402
import build_armor as B  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def import_set(armor: Path, st: str):
    objs = []
    for slot in B.SLOTS:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=str(armor / f"{st}_{slot}.fbx"), axis_forward="Z", axis_up="Y")
        new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        names = sorted(o.name.split(".")[0] for o in new)
        imgs = {n.image.name for o in new for ms in o.material_slots if ms.material
                for n in ms.material.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage" and n.image}
        print(f"  {st}_{slot}: 메시 {names} / 텍스처 {len(imgs)}장", flush=True)
        objs += new
    return objs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--armor", required=True)
    ap.add_argument("--samples", type=int, default=64)
    a = ap.parse_args()
    armor = Path(a.armor)
    prev = armor / "previews"
    L.reset_scene()
    B.setup_render(samples=a.samples)
    sets = {}
    for st in B.SETS:
        objs = import_set(armor, st)
        for o in [o for s in sets.values() for o in s]:
            o.hide_render = True
        man = B.mannequin()
        B.render(prev / f"{st}_front.png", (0, 0, 2.85), az=28)
        B.render(prev / f"{st}_back.png", (0, 0, 2.85), az=200)
        B.render(prev / f"{st}_helmet.png", (0, 0, 4.85), dist=4.2, az=35, el=8)
        for o in man:
            bpy.data.objects.remove(o)
        sets[st] = objs
    for i, (st, objs) in enumerate(sets.items()):
        off = Vector(((i - 1) * -4.6, 0, 0))
        for o in objs:
            o.hide_render = False
            o.location += off
        B.mannequin(off)
    bpy.context.scene.render.resolution_x = 1500
    B.render(prev / "lineup.png", (0, 0, 2.95), dist=21, az=12, el=10)


if __name__ == "__main__":
    main()
