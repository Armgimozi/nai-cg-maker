"""Meshy 원본(GLB)을 로블록스 Tool 로 바로 쓸 수 있게 정리한다.

  python roblox_items/tools/process_meshy.py --raw <meshy_raw> --inspect <폴더>   # 원본 방향 확인용 3면 렌더
  python roblox_items/tools/process_meshy.py --raw <meshy_raw> --out roblox_items  # 정리·내보내기

정리 내용
  - 방향: 날/머리 쪽이 위(+Y), 날 끝·도끼날이 앞(-Z) — Tool 을 들면 위를 향하도록
  - 크기: 캐릭터(R15 ≈ 5.5 스터드)에 맞춘 실제 길이(스터드)
  - 손잡이 위치(Grip) 계산 → Luau 데이터
  - 텍스처 1024²(로블록스 최대치)로 줄여 색/노멀/거칠기/금속으로 나눠 FBX 에 내장
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # noqa: I001
import numpy as np
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_lib as L  # noqa: E402

# kind, 길이(스터드, 긴 축), 원본→정리 회전(XYZ 오일러, 도), 손잡이 위치(아래 끝=0 ~ 위 끝=1, 긴 축 기준), 한글 이름
ITEMS = {
    "iron_longsword":  ("weapon", 4.4, (0, 180, 90), 0.11, "철 롱소드"),
    "battle_axe":      ("weapon", 4.0, (0, 0, 90), 0.20, "전투 도끼"),
    "spear":           ("weapon", 7.0, (0, -90, 0), 0.38, "창"),
    "longbow":         ("weapon", 4.8, (0, -90, -90), 0.50, "장궁"),
    "mage_staff":      ("weapon", 5.6, (0, 0, 0), 0.45, "마법 지팡이"),
    "dagger":          ("weapon", 1.9, (0, 0, 90), 0.13, "단검"),
    "guardian_amulet": ("artifact", 0.9, (0, 0, 0), 0.0, "수호의 부적"),
    "flame_ring":      ("artifact", 0.7, (-90, 0, 0), 0.0, "화염의 반지"),
    "ancient_runestone": ("artifact", 1.3, (0, 0, 0), 0.0, "고대 룬석"),
    "arcane_orb":      ("artifact", 1.2, (0, 0, 0), 0.0, "비전 오브"),
    "chalice_of_life": ("artifact", 1.2, (0, 0, 0), 0.0, "생명의 성배"),
}


def load(raw: Path, name: str):
    L.reset_scene()
    bpy.ops.import_scene.gltf(filepath=str(raw / name / "model.glb"))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.scene.objects:
        o.select_set(o.type == "MESH")
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    # 부모(빈 오브젝트) 변환까지 굳히기
    mw = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = mw
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    ob.name = name
    return ob


def verts(ob):
    return np.array([v.co[:] for v in ob.data.vertices])


def _linked_image(sock):
    """소켓으로 들어오는 이미지 노드(중간 노드 한두 단계까지)."""
    seen = [sock]
    while seen:
        s = seen.pop()
        for lk in s.links:
            nd = lk.from_node
            if nd.bl_idname == "ShaderNodeTexImage":
                return nd.image
            seen += [i for i in nd.inputs if i.is_linked]
    return None


def rebuild_material(ob, name: str, tex_dir: Path):
    """glTF(메탈릭·러프 한 장) 재질 → 색/노멀/거칠기/금속 각각의 텍스처로 풀어서 직결.

    FBX 내보내기·로블록스 SurfaceAppearance 가 바로 읽을 수 있는 구조로 만든다.
    """
    from PIL import Image
    mat = ob.active_material
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    imgs = {
        "color": _linked_image(bsdf.inputs["Base Color"]),
        "normal": _linked_image(bsdf.inputs["Normal"]),
        "mr": _linked_image(bsdf.inputs["Roughness"]) or _linked_image(bsdf.inputs["Metallic"]),
    }
    files = {}
    for role, img in imgs.items():
        if img is None:
            continue
        tmp = tex_dir / f"_{name}_{role}.png"
        img.filepath_raw = str(tmp)
        img.file_format = "PNG"
        img.save()
        im = Image.open(tmp)
        if im.size[0] > 1024:
            im = im.resize((1024, 1024), Image.LANCZOS)
        if role == "mr":  # glTF: G = 거칠기, B = 금속
            rgb = im.convert("RGB")
            for key, ch in (("roughness", 1), ("metalness", 2)):
                p = tex_dir / f"{name}_{key}.png"
                rgb.getchannel(ch).save(p, optimize=True)
                files[key] = p
        else:
            p = tex_dir / f"{name}_{role}.jpg"
            im.convert("RGB").save(p, quality=92 if role == "color" else 95, optimize=True)
            files[role] = p
        tmp.unlink()
    loaded = {k: bpy.data.images.load(str(p)) for k, p in files.items()}
    for k, im in loaded.items():
        if k != "color":
            im.colorspace_settings.name = "Non-Color"
    new = bpy.data.materials.new(name)
    new.use_nodes = True
    nt = new.node_tree
    b = nt.nodes["Principled BSDF"]

    def tex(img):
        nd = nt.nodes.new("ShaderNodeTexImage")
        nd.image = img
        return nd.outputs[0]
    if "color" in loaded:
        nt.links.new(tex(loaded["color"]), b.inputs["Base Color"])
    if "metalness" in loaded:
        nt.links.new(tex(loaded["metalness"]), b.inputs["Metallic"])
    if "roughness" in loaded:
        nt.links.new(tex(loaded["roughness"]), b.inputs["Roughness"])
    if "normal" in loaded:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex(loaded["normal"]), nm.inputs["Color"])
        nt.links.new(nm.outputs[0], b.inputs["Normal"])
    ob.data.materials.clear()
    ob.data.materials.append(new)
    return files


def inspect(raw: Path, out: Path):
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    for name in ITEMS:
        ob = load(raw, name)
        V = verts(ob)
        lo, hi = V.min(0), V.max(0)
        c = (lo + hi) / 2
        ext = float((hi - lo).max())
        sc = bpy.context.scene
        sc.render.resolution_x = sc.render.resolution_y = 360
        sc.cycles.samples = 8
        _lights()
        tiles = []
        for label, d in (("front(-Y)", (0, -1, 0)), ("right(+X)", (1, 0, 0)), ("top(+Z)", (0, 0, 1))):
            _cam(c, Vector(d), ext * 1.15)
            p = out / f"_{name}_{label[:3]}.png"
            sc.render.filepath = str(p)
            bpy.ops.render.render(write_still=True)
            im = Image.open(p).convert("RGB")
            ImageDraw.Draw(im).text((6, 6), label, fill=(255, 255, 0))
            tiles.append(im)
            p.unlink()
        sheet = Image.new("RGB", (1080, 380), (20, 20, 20))
        for i, t in enumerate(tiles):
            sheet.paste(t, (360 * i, 20))
        ImageDraw.Draw(sheet).text((6, 2), f"{name}  ext={np.round(hi - lo, 3)}", fill=(255, 255, 255))
        sheet.save(out / f"{name}.png")
        print(name, "bbox", np.round(hi - lo, 3), flush=True)


def _lights():
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.36, 0.4, 1)
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    if "key" not in bpy.data.objects:
        ld = bpy.data.lights.new("key", "SUN")
        ld.energy = 3.0
        lo = bpy.data.objects.new("key", ld)
        lo.rotation_euler = (math.radians(50), 0, math.radians(-30))
        L.link(lo)


def _cam(center, direction, ortho):
    cam = bpy.data.objects.get("cam")
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        L.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = ortho
    cam.location = Vector(center) + direction * 10
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()  # 카메라 로컬 Y = 화면 위
    if abs(direction.z) > 0.9:
        cam.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = cam


def build(raw: Path, out: Path, only=None):
    data = {}
    wdir, adir = out / "weapons", out / "artifacts"
    for d in (wdir, adir, wdir / "previews", adir / "previews"):
        d.mkdir(parents=True, exist_ok=True)
    for name, (kind, length, rot_deg, grip_t, ko) in ITEMS.items():
        if only and name not in only:
            continue
        ob = load(raw, name)
        ob.rotation_mode = "XYZ"  # glTF 임포터는 쿼터니언 모드로 불러옴
        ob.rotation_euler = Euler([math.radians(a) for a in rot_deg], "XYZ")
        bpy.ops.object.transform_apply(rotation=True)
        V = verts(ob)
        lo, hi = V.min(0), V.max(0)
        ext = hi - lo
        long_ax = 2 if kind == "weapon" else int(np.argmax(ext))
        s = length / float(ext[long_ax])
        # 바닥 중심 → 원점 후 크기 맞춤
        c = (lo + hi) / 2
        ob.data.transform(Matrix.Translation(Vector((-c[0], -c[1], -c[2]))))
        ob.data.transform(Matrix.Scale(s, 4))
        ob.location = (0, 0, 0)
        V = verts(ob)
        lo, hi = V.min(0), V.max(0)
        ntri = L.limit_tris(ob, 9800)
        dest = wdir if kind == "weapon" else adir
        tex_dir = dest / "textures"
        tex_dir.mkdir(exist_ok=True)
        rebuild_material(ob, name, tex_dir)
        L.export([ob], dest / f"{name}.fbx")
        # 손잡이: 긴 축(z) 기준 아래에서 grip_t 지점, 단면 중심
        if kind == "weapon":
            gz = lo[2] + (hi[2] - lo[2]) * grip_t
            band = V[np.abs(V[:, 2] - gz) < 0.06]
            gx, gy = (band[:, 0].mean(), band[:, 1].mean()) if len(band) else (0.0, 0.0)
            grip = L.bl_to_rbx((gx, gy, gz))
        else:
            grip = (0.0, float(lo[2]) + 0.05, 0.0)  # 아래쪽을 손바닥에 올림
        size = (hi - lo)
        data[name] = {
            "kind": kind, "name_ko": ko,
            "size": [round(float(size[0]), 4), round(float(size[2]), 4), round(float(size[1]), 4)],
            "grip": [round(float(v), 4) for v in grip],
            "tris": ntri,
        }
        print(f"[{name}] {ko}: size(studs)={data[name]['size']} grip={data[name]['grip']} tris={ntri}", flush=True)
        _preview(ob, dest / "previews" / f"{name}.png", kind)
    p = out / "item_data.json"
    old = json.loads(p.read_text("utf-8")) if p.exists() else {}
    old.update(data)
    p.write_text(json.dumps(old, ensure_ascii=False, indent=1), "utf-8")


def _preview(ob, path, kind):
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = 640
    sc.cycles.samples = 32
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.render.film_transparent = True  # 금속 반사용 밝은 환경 + 배경은 PIL 로 어둡게 합성
    _lights()
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.42, 0.44, 0.5, 1)
    V = verts(ob)
    lo, hi = V.min(0), V.max(0)
    c = (lo + hi) / 2
    ext = float((hi - lo).max())
    d = Vector((0.45, -1.0, 0.18)).normalized()
    _cam(c, d, ext * 1.15)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (30, 32, 38, 255))
    Image.alpha_composite(bg, im).convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--inspect")
    ap.add_argument("--out")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    raw = Path(a.raw)
    if a.inspect:
        inspect(raw, Path(a.inspect))
    if a.out:
        build(raw, Path(a.out), [x for x in a.only.split(",") if x] or None)


if __name__ == "__main__":
    main()
