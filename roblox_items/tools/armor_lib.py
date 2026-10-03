"""코드 모델링용 Blender(bpy) 유틸 — 방어구 빌더가 공통으로 쓰는 기하·재질·베이크·내보내기.

좌표계(블렌더): Z 위, 캐릭터 정면 = -Y, 캐릭터 오른쪽 = -X.
FBX 를 Forward=Z / Up=Y 로 내보내면 로블록스 좌표 (x, y, z) = (-bx, bz, by) 로 들어간다
(로블록스 문서 권장 설정: create.roblox.com/docs/art/blender).
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy  # noqa: I001  (bmesh 는 bpy 를 먼저 import 해야 로드됨)
import bmesh
import numpy as np
from mathutils import Matrix, Vector

TAU = math.tau

# ─────────────────────────── R15 기준 치수 (로블록스 스터드, X폭·Y높이·Z깊이) ──
R15_SIZE = {
    "Head": (1.2, 1.2, 1.2),
    "UpperTorso": (2.0, 1.6, 1.0),
    "LowerTorso": (2.0, 0.4, 1.0),
    "RightUpperArm": (1.0, 1.169, 1.0), "LeftUpperArm": (1.0, 1.169, 1.0),
    "RightLowerArm": (1.0, 1.052, 1.0), "LeftLowerArm": (1.0, 1.052, 1.0),
    "RightHand": (1.0, 0.3, 1.0), "LeftHand": (1.0, 0.3, 1.0),
    "RightUpperLeg": (1.0, 1.217, 1.0), "LeftUpperLeg": (1.0, 1.217, 1.0),
    "RightLowerLeg": (1.0, 1.193, 1.0), "LeftLowerLeg": (1.0, 1.193, 1.0),
    "RightFoot": (1.0, 0.3, 1.0), "LeftFoot": (1.0, 0.3, 1.0),
}
# 미리보기 조립용 부위 중심(로블록스 좌표, 발바닥 y=0). 실제 장착은 Luau 가 부위 CFrame 기준으로 한다.
R15_POS = {
    "LeftFoot": (-0.5, 0.15, -0.0), "RightFoot": (0.5, 0.15, 0.0),
    "LeftLowerLeg": (-0.5, 0.8465, 0), "RightLowerLeg": (0.5, 0.8465, 0),
    "LeftUpperLeg": (-0.5, 1.9085, 0), "RightUpperLeg": (0.5, 1.9085, 0),
    "LowerTorso": (0, 2.40, 0), "UpperTorso": (0, 3.40, 0),
    "LeftUpperArm": (-1.5, 3.6155, 0), "RightUpperArm": (1.5, 3.6155, 0),
    "LeftLowerArm": (-1.5, 2.576, 0), "RightLowerArm": (1.5, 2.576, 0),
    "LeftHand": (-1.5, 1.95, 0), "RightHand": (1.5, 1.95, 0),
    "Head": (0, 4.80, 0),
}


def rbx_to_bl(v):
    x, y, z = v
    return (-x, z, y)


def bl_to_rbx(v):
    bx, by, bz = v
    return (-bx, bz, by)


def part_half(part):
    """블렌더 축 기준 반치수 (hx, hy, hz)."""
    sx, sy, sz = R15_SIZE[part]
    return sx / 2, sz / 2, sy / 2


def part_loc_bl(part):
    return Vector(rbx_to_bl(R15_POS[part]))


# ─────────────────────────────────────────────────────────────── 씬 ──
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "NONE"
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    return sc


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


# ─────────────────────────────────────────────────────────── 메시 생성 ──
def mesh_from(name, verts, faces, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(int(i) for i in f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    if mat is not None:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def sq_ring(A, B, n, th, cx=0.0, cy=0.0):
    c, s = np.cos(th), np.sin(th)
    x = A * np.sign(c) * np.abs(c) ** (2.0 / n)
    y = B * np.sign(s) * np.abs(s) ** (2.0 / n)
    return x + cx, y + cy


def _resolve(v, z):
    if callable(v):
        return np.asarray(v(z), float)
    arr = np.asarray(v, float)
    return arr if arr.shape == z.shape else np.full_like(z, float(v))


def spline(ctrl, num):
    """제어점(행=점, 열=값들)을 지나는 Catmull-Rom 보간 → (num, k) 배열."""
    P = np.asarray(ctrl, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    nseg = len(P) - 3
    out = []
    for i in range(num):
        u = i / (num - 1) * nseg
        k = min(int(u), nseg - 1)
        t = u - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.asarray(out)


def loft_shell(name, zs, A, B, n=4.0, th=(0.0, TAU), M=48, cx=0.0, cy=0.0,
               deform=None, mat=None, xform=None, cap_top=False, cap_bottom=False):
    """초타원 단면을 z 방향으로 쌓은 면(두께 없음). A,B,cx,cy,n 은 상수 또는 z→값 함수.

    th: (시작각, 끝각). 각도 0=+X(캐릭터 왼쪽), -π/2=정면(-Y), π=캐릭터 오른쪽.
    """
    zs = np.asarray(zs, float)
    full = abs((th[1] - th[0]) - TAU) < 1e-6
    thetas = np.linspace(th[0], th[1], M, endpoint=not full)
    Az, Bz, CX, CY = (_resolve(v, zs) for v in (A, B, cx, cy))
    Nz = _resolve(n, zs)
    rings = []
    for i, z in enumerate(zs):
        x, y = sq_ring(Az[i], Bz[i], Nz[i], thetas, CX[i], CY[i])
        pts = np.stack([x, y, np.full_like(x, z)], 1)
        if deform is not None:
            pts = deform(pts, thetas)
        rings.append(pts)
    verts = np.concatenate(rings)
    faces = []
    nseg = M if full else M - 1
    for i in range(len(zs) - 1):
        for j in range(nseg):
            j2 = (j + 1) % M
            faces.append((i * M + j, i * M + j2, (i + 1) * M + j2, (i + 1) * M + j))
    verts = list(verts)
    if cap_bottom:
        c = rings[0].mean(0)
        verts.append(c)
        ci = len(verts) - 1
        for j in range(nseg):
            faces.append((ci, (j + 1) % M, j))
    if cap_top:
        c = rings[-1].mean(0)
        verts.append(c)
        ci = len(verts) - 1
        b = (len(zs) - 1) * M
        for j in range(nseg):
            faces.append((ci, b + j, b + (j + 1) % M))
    verts = np.asarray(verts)
    if xform is not None:
        verts = apply_xform(verts, xform)
    return mesh_from(name, verts, faces, mat)


def apply_xform(verts, xform):
    R, t = xform if isinstance(xform, tuple) else (xform, (0, 0, 0))
    return verts @ np.asarray(R, float).T + np.asarray(t, float)


def rot(axis, deg):
    return np.asarray(Matrix.Rotation(math.radians(deg), 3, axis))


def solidify(ob, thickness, offset=1.0, rim=True):
    m = ob.modifiers.new("solid", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    m.use_rim = rim
    m.use_even_offset = True
    m.use_quality_normals = True
    apply_mods(ob)
    return ob


def apply_mods(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier=m.name)


def bevel(ob, width, segments=2, angle=40):
    m = ob.modifiers.new("bev", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = False
    apply_mods(ob)
    return ob


def shell(name, zs, A, B, t=0.04, mat=None, bev=0.012, **kw):
    """두께가 있는 판금/가죽 판."""
    ob = loft_shell(name, zs, A, B, mat=mat, **kw)
    fix_normals(ob)
    solidify(ob, t, offset=1.0)
    if bev:
        bevel(ob, min(bev, t * 0.45), 1, 50)
    return ob


def fix_normals(ob, inside=False):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if inside:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def outward_normals_open(ob, center=(0, 0, 0)):
    """열린 면의 법선을 중심점 바깥쪽으로 정렬."""
    me = ob.data
    c = Vector(center)
    bm = bmesh.new()
    bm.from_mesh(me)
    flip = [f for f in bm.faces if f.normal.dot(f.calc_center_median() - c) < 0]
    bmesh.ops.reverse_faces(bm, faces=flip)
    bm.to_mesh(me)
    bm.free()


def _frames(pts, closed):
    P = np.asarray(pts, float)
    T = np.roll(P, -1, 0) - np.roll(P, 1, 0) if closed else np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    up = np.array([0, 0, 1.0])
    if abs(T[0] @ up) > 0.9:
        up = np.array([1.0, 0, 0])
    N = [np.cross(T[0], np.cross(up, T[0]))]
    N[0] /= np.linalg.norm(N[0])
    for i in range(1, len(P)):
        n = N[-1] - (N[-1] @ T[i]) * T[i]
        n /= np.linalg.norm(n) + 1e-12
        N.append(n)
    N = np.asarray(N)
    Bn = np.cross(T, N)
    return T, N, Bn


def tube(name, pts, r, closed=True, segs=8, mat=None, caps=True, flat=1.0):
    """경로를 따라가는 관(테두리 말림, 띠, 막대). flat<1 이면 납작한 띠."""
    P = np.asarray(pts, float)
    T, N, Bn = _frames(P, closed)
    rr = np.broadcast_to(np.asarray(r, float), (len(P),))
    ang = np.linspace(0, TAU, segs, endpoint=False)
    verts = []
    for i in range(len(P)):
        for a in ang:
            verts.append(P[i] + rr[i] * (math.cos(a) * N[i] + flat * math.sin(a) * Bn[i]))
    faces = []
    L = len(P)
    for i in range(L if closed else L - 1):
        i2 = (i + 1) % L
        for j in range(segs):
            j2 = (j + 1) % segs
            faces.append((i * segs + j, i * segs + j2, i2 * segs + j2, i2 * segs + j))
    if not closed and caps:
        verts.append(P[0])
        verts.append(P[-1])
        a0, a1 = len(verts) - 2, len(verts) - 1
        for j in range(segs):
            j2 = (j + 1) % segs
            faces.append((a0, j2, j))
            faces.append((a1, (L - 1) * segs + j, (L - 1) * segs + j2))
    ob = mesh_from(name, verts, faces, mat)
    fix_normals(ob)
    return ob


def rivets(name, pts, nrms, r=0.03, mat=None, h=0.6):
    """반구형 리벳 묶음(한 오브젝트)."""
    verts, faces = [], []
    ring_n, stacks = 8, 3
    for p, n in zip(pts, nrms):
        n = np.asarray(n, float)
        n /= np.linalg.norm(n) + 1e-12
        a = np.cross(n, [0, 0, 1.0])
        if np.linalg.norm(a) < 1e-3:
            a = np.cross(n, [1.0, 0, 0])
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        base = len(verts)
        for k in range(stacks):
            phi = (k / stacks) * (math.pi / 2)
            for j in range(ring_n):
                t = j / ring_n * TAU
                d = math.cos(phi) * (math.cos(t) * a + math.sin(t) * b)
                verts.append(np.asarray(p) + r * d + r * h * math.sin(phi) * n - 0.3 * r * n)
        verts.append(np.asarray(p) + r * h * n - 0.3 * r * n)
        top = len(verts) - 1
        for k in range(stacks - 1):
            for j in range(ring_n):
                j2 = (j + 1) % ring_n
                faces.append((base + k * ring_n + j, base + k * ring_n + j2,
                              base + (k + 1) * ring_n + j2, base + (k + 1) * ring_n + j))
        for j in range(ring_n):
            j2 = (j + 1) % ring_n
            faces.append((base + (stacks - 1) * ring_n + j, base + (stacks - 1) * ring_n + j2, top))
    ob = mesh_from(name, verts, faces, mat)
    return ob


def ring_points(z, A, B, n, th, cx=0.0, cy=0.0, grow=0.0):
    x, y = sq_ring(A + grow, B + grow, n, th, cx, cy)
    return np.stack([x, y, np.full_like(x, z)], 1)


def ring_normals(pts, cx=0.0, cy=0.0):
    d = pts.copy()
    d[:, 0] -= cx
    d[:, 1] -= cy
    d[:, 2] = 0
    return d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)


def mirror_x(ob, name):
    me = ob.data.copy()
    o2 = bpy.data.objects.new(name, me)
    link(o2)
    o2.matrix_world = ob.matrix_world.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return o2


def join(objs, name):
    objs = [o for o in objs if o is not None]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def finish(ob, sharp_angle=48):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(sharp_angle))
    except AttributeError:
        pass
    return ob


def limit_tris(ob, max_tris=9800):
    """로블록스 MeshPart 한도(2만) 안쪽으로 여유 있게 줄인다."""
    n = tri_count(ob)
    if n <= max_tris:
        return n
    m = ob.modifiers.new("dec", "DECIMATE")
    m.ratio = max_tris / n * 0.98
    m.use_collapse_triangulate = True
    apply_mods(ob)
    return tri_count(ob)


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ──────────────────────────────────────────────────────────── 재질 ──
# 모든 재질은 노드 이름으로 BASE(색) / METAL / ROUGH 출력과 BSDF 를 갖는다 → 베이크 때 재배선.
MATS = {
    #           base rgb               metal rough  kind      extra
    "steel":   ((0.62, 0.63, 0.66), 1.0, 0.28, "metal", {"hammer": 0.10, "rust": 0.0}),
    "iron":    ((0.40, 0.40, 0.42), 1.0, 0.48, "metal", {"hammer": 0.22, "rust": 0.35}),
    "darkiron": ((0.20, 0.20, 0.22), 1.0, 0.55, "metal", {"hammer": 0.15, "rust": 0.2}),
    "gold":    ((0.86, 0.62, 0.26), 1.0, 0.30, "metal", {"hammer": 0.05, "rust": 0.0}),
    "bronze":  ((0.62, 0.40, 0.20), 1.0, 0.38, "metal", {"hammer": 0.1, "rust": 0.0}),
    "leather": ((0.26, 0.145, 0.075), 0.0, 0.62, "leather", {}),
    "leather_dark": ((0.11, 0.065, 0.042), 0.0, 0.58, "leather", {}),
    "leather_red": ((0.36, 0.09, 0.06), 0.0, 0.60, "leather", {}),
    "cloth_red": ((0.50, 0.05, 0.05), 0.0, 0.85, "cloth", {}),
    "cloth_blue": ((0.07, 0.13, 0.36), 0.0, 0.85, "cloth", {}),
    "padding":  ((0.55, 0.47, 0.34), 0.0, 0.90, "cloth", {}),
    "mail":    ((0.42, 0.42, 0.44), 1.0, 0.42, "mail", {}),
    "fur":     ((0.30, 0.22, 0.15), 0.0, 0.95, "fur", {}),
    "inner":   ((0.015, 0.015, 0.018), 0.0, 0.95, "flat", {}),
}


def _n(nt, typ, name=None, loc=(0, 0), **props):
    nd = nt.nodes.new(typ)
    if name:
        nd.name = name
        nd.label = name
    nd.location = loc
    for k, v in props.items():
        setattr(nd, k, v)
    return nd


def _math(nt, op, a=None, b=None, name=None, clamp=False):
    nd = _n(nt, "ShaderNodeMath", name, operation=op)
    nd.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            nd.inputs[i].default_value = v
        else:
            nt.links.new(v, nd.inputs[i])
    return nd.outputs[0]


def _mix_rgb(nt, fac, c1, c2, blend="MIX"):
    nd = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type=blend)
    for sock, v in ((nd.inputs[0], fac), (nd.inputs[6], c1), (nd.inputs[7], c2)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = (*v, 1.0) if len(v) == 3 else v
        else:
            nt.links.new(v, sock)
    return nd.outputs[2]


def _noise(nt, vec, scale, detail=4.0, rough=0.55, distortion=0.0):
    nd = _n(nt, "ShaderNodeTexNoise")
    nt.links.new(vec, nd.inputs["Vector"])
    nd.inputs["Scale"].default_value = scale
    nd.inputs["Detail"].default_value = detail
    nd.inputs["Roughness"].default_value = rough
    nd.inputs["Distortion"].default_value = distortion
    return nd.outputs["Fac"]


def _voronoi(nt, vec, scale, feature="F1"):
    nd = _n(nt, "ShaderNodeTexVoronoi", feature=feature)
    nt.links.new(vec, nd.inputs["Vector"])
    nd.inputs["Scale"].default_value = scale
    return nd.outputs["Distance"]


def _ramp(nt, fac, a, b):
    """선형 보간 (a + (b-a)*fac) — 스칼라."""
    return _math(nt, "ADD", _math(nt, "MULTIPLY", fac, b - a), a)


def _mapping(nt, vec, scale):
    nd = _n(nt, "ShaderNodeMapping")
    nt.links.new(vec, nd.inputs["Vector"])
    nd.inputs["Scale"].default_value = scale
    return nd.outputs[0]


def make_material(key):
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    base, metal, rough, kind, extra = MATS[key]
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = _n(nt, "ShaderNodeOutputMaterial", "OUT", (900, 0))
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", "BSDF", (600, 0))
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    tc = _n(nt, "ShaderNodeTexCoord", "TC", (-1200, 0))
    co = tc.outputs["Object"]

    # 모서리 마모 / 틈새(AO)
    bev = _n(nt, "ShaderNodeBevel", "BEV", samples=16)
    bev.inputs["Radius"].default_value = 0.02
    geo = _n(nt, "ShaderNodeNewGeometry")
    dot = _n(nt, "ShaderNodeVectorMath", operation="DOT_PRODUCT")
    nt.links.new(bev.outputs[0], dot.inputs[0])
    nt.links.new(geo.outputs["Normal"], dot.inputs[1])
    edge = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, dot.outputs["Value"]), 9.0, clamp=True)
    edge = _math(nt, "MULTIPLY", edge, _ramp(nt, _noise(nt, co, 9.0, 6), 0.3, 1.6), clamp=True)
    ao = _n(nt, "ShaderNodeAmbientOcclusion", "AO", samples=12, only_local=True)
    ao.inputs["Distance"].default_value = 0.15
    cav = _ramp(nt, ao.outputs["AO"], 0.45, 1.0)

    big = _noise(nt, co, 3.0, 4)
    fine = _noise(nt, co, 40.0, 3)
    base_c = tuple(base)
    dark = tuple(c * 0.78 for c in base_c)
    light = tuple(min(1, c * 1.12) for c in base_c)
    col = _mix_rgb(nt, big, dark, light)

    bump_h = None
    if kind == "metal":
        worn = tuple(min(1, c * 1.35 + 0.05) for c in base_c)
        col = _mix_rgb(nt, edge, col, worn)
        scratch_v = _mapping(nt, co, (60.0, 2.0, 2.0))
        scratch = _math(nt, "GREATER_THAN", _noise(nt, scratch_v, 6.0, 2), 0.70)
        rough_s = _math(nt, "ADD", _ramp(nt, fine, rough - 0.06, rough + 0.08), _math(nt, "MULTIPLY", scratch, 0.08))
        metal_s = None
        if extra.get("rust", 0) > 0:
            rmask = _math(nt, "GREATER_THAN", _math(nt, "MULTIPLY", _noise(nt, co, 5.0, 8, 0.7), _math(nt, "SUBTRACT", 1.0, edge)), 0.70 - extra["rust"] * 0.1)
            rust_c = _mix_rgb(nt, _noise(nt, co, 25.0), (0.20, 0.09, 0.04), (0.32, 0.15, 0.06))
            col = _mix_rgb(nt, rmask, col, rust_c)
            rough_s = _math(nt, "ADD", _math(nt, "MULTIPLY", rmask, 0.35), rough_s)
            metal_s = _math(nt, "SUBTRACT", float(metal), _math(nt, "MULTIPLY", rmask, 0.7))
        hammer = _voronoi(nt, co, 14.0, "SMOOTH_F1")
        bump_h = _math(nt, "ADD", _math(nt, "MULTIPLY", hammer, extra.get("hammer", 0.1)),
                       _math(nt, "MULTIPLY", scratch, -0.02))
    elif kind == "leather":
        grain = _voronoi(nt, co, 90.0)
        wrinkle = _noise(nt, co, 4.0, 6, 0.6, 1.5)
        worn = tuple(min(1, c * 1.45 + 0.03) for c in base_c)
        col = _mix_rgb(nt, _math(nt, "MULTIPLY", edge, 0.8), col, worn)
        col = _mix_rgb(nt, _math(nt, "MULTIPLY", wrinkle, 0.35), col, dark)
        rough_s = _ramp(nt, fine, rough - 0.08, rough + 0.1)
        metal_s = None
        bump_h = _math(nt, "ADD", _math(nt, "MULTIPLY", grain, 0.25), _math(nt, "MULTIPLY", wrinkle, 0.5))
    elif kind == "cloth":
        wv = _n(nt, "ShaderNodeTexWave", wave_type="BANDS")
        nt.links.new(co, wv.inputs["Vector"])
        wv.inputs["Scale"].default_value = 120.0
        wv.inputs["Distortion"].default_value = 2.0
        rough_s = _ramp(nt, fine, rough - 0.05, rough + 0.05)
        metal_s = None
        bump_h = _math(nt, "ADD", _math(nt, "MULTIPLY", wv.outputs["Fac"], 0.25), _math(nt, "MULTIPLY", fine, 0.3))
    elif kind == "mail":
        cell = _voronoi(nt, _mapping(nt, co, (1.0, 1.0, 1.6)), 55.0)
        ringm = _math(nt, "LESS_THAN", _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT", cell, 0.32)), 0.12)
        col = _mix_rgb(nt, ringm, (0.05, 0.05, 0.055), col)
        col = _mix_rgb(nt, edge, col, tuple(min(1, c * 1.3) for c in base_c))
        rough_s = _ramp(nt, fine, rough - 0.05, rough + 0.1)
        metal_s = None
        bump_h = _math(nt, "MULTIPLY", ringm, 0.6)
    elif kind == "fur":
        fv = _mapping(nt, co, (40.0, 40.0, 6.0))
        strands = _noise(nt, fv, 10.0, 8, 0.8)
        col = _mix_rgb(nt, strands, dark, light)
        rough_s = _ramp(nt, fine, 0.85, 1.0)
        metal_s = None
        bump_h = _math(nt, "MULTIPLY", strands, 1.0)
    else:  # flat
        rough_s = _ramp(nt, fine, rough - 0.02, rough)
        metal_s = None

    col = _mix_rgb(nt, 1.0, col, _mix_rgb(nt, cav, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), "MULTIPLY")
    base_node = _n(nt, "ShaderNodeMix", "BASE", data_type="RGBA")
    base_node.inputs[0].default_value = 0.0
    nt.links.new(col, base_node.inputs[6])
    nt.links.new(base_node.outputs[2], bsdf.inputs["Base Color"])

    metal_node = _n(nt, "ShaderNodeMath", "METAL", operation="ADD")
    metal_node.use_clamp = True
    if metal_s is not None:
        nt.links.new(metal_s, metal_node.inputs[0])
    else:
        metal_node.inputs[0].default_value = float(metal)
    metal_node.inputs[1].default_value = 0.0
    nt.links.new(metal_node.outputs[0], bsdf.inputs["Metallic"])

    rough_node = _n(nt, "ShaderNodeMath", "ROUGH", operation="ADD")
    rough_node.use_clamp = True
    nt.links.new(rough_s, rough_node.inputs[0])
    rough_node.inputs[1].default_value = 0.0
    nt.links.new(rough_node.outputs[0], bsdf.inputs["Roughness"])

    if bump_h is not None:
        bump = _n(nt, "ShaderNodeBump", "BUMP")
        bump.inputs["Strength"].default_value = 0.35
        bump.inputs["Distance"].default_value = 0.02
        nt.links.new(bump_h, bump.inputs["Height"])
        nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


def M(key):
    return make_material(key)


# ─────────────────────────────────────────────────── UV · 베이크 · 내보내기 ──
def unwrap_pack(objs, margin=0.006):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def _bake_target(objs, img):
    for o in objs:
        for ms in o.material_slots:
            nt = ms.material.node_tree
            nd = nt.nodes.get("BAKE_IMG") or _n(nt, "ShaderNodeTexImage", "BAKE_IMG", (1100, 300))
            nd.image = img
            nt.nodes.active = nd


def _emit_from(objs, node_name):
    for o in objs:
        for ms in o.material_slots:
            nt = ms.material.node_tree
            em = nt.nodes.get("BAKE_EMIT") or _n(nt, "ShaderNodeEmission", "BAKE_EMIT", (900, 300))
            src = nt.nodes[node_name]
            out_sock = src.outputs[2] if src.bl_idname == "ShaderNodeMix" else src.outputs[0]
            nt.links.new(out_sock, em.inputs["Color"])
            nt.links.new(em.outputs[0], nt.nodes["OUT"].inputs["Surface"])


def _restore(objs):
    for o in objs:
        for ms in o.material_slots:
            nt = ms.material.node_tree
            nt.links.new(nt.nodes["BSDF"].outputs[0], nt.nodes["OUT"].inputs["Surface"])


def bake_atlas(objs, out_dir: Path, prefix: str, size=1024, samples=24):
    """여러 오브젝트를 한 장의 텍스처 아틀라스(색/노멀/거칠기/금속)로 굽는다."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.bake.margin = 8
    sc.render.bake.use_clear = True
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # 재질이 오브젝트 간 공유되므로 한 번에 굽는다.
    maps = {}
    for key, kind in (("color", "BASE"), ("roughness", "ROUGH"), ("metalness", "METAL"), ("normal", "NORMAL")):
        img = bpy.data.images.new(f"{prefix}_{key}", size, size, alpha=False, float_buffer=False)
        if key != "color":
            img.colorspace_settings.name = "Non-Color"
        _bake_target(objs, img)
        if kind == "NORMAL":
            _restore(objs)
            bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=8)
        else:
            _emit_from(objs, kind)
            bpy.ops.object.bake(type="EMIT", margin=8)
        png = out_dir / f"{prefix}_{key}.png"
        img.filepath_raw = str(png)
        img.file_format = "PNG"
        img.save()
        path = compact_texture(png, key, despeckle=key in ("color", "roughness"))
        img.filepath_raw = str(path)
        img.filepath = str(path)
        img.source = "FILE"
        img.reload()
        maps[key] = img
    _restore(objs)
    return maps


def compact_texture(png: Path, key: str, despeckle=False, size=1024) -> Path:
    """용량 줄이기: 색/노멀 → JPEG, 거칠기/금속 → 흑백 PNG. (로블록스 텍스처 최대 1024²)"""
    from PIL import Image, ImageFilter
    im = Image.open(png)
    if im.size[0] > size:
        im = im.resize((size, size), Image.LANCZOS)
    if despeckle:
        im = im.filter(ImageFilter.MedianFilter(3))  # 베벨/AO 샘플링 반점 제거
    if key in ("color", "normal"):
        out = png.with_suffix(".jpg")
        im.convert("RGB").save(out, quality=92 if key == "color" else 95, optimize=True)
    else:
        out = png.with_suffix(".png")
        im.convert("L").save(out, optimize=True)
    if out != png:
        png.unlink()
    return out


def atlas_material(name, maps):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    def tex(img, loc):
        nd = nt.nodes.new("ShaderNodeTexImage")
        nd.image = img
        nd.location = loc
        return nd
    nt.links.new(tex(maps["color"], (-600, 300)).outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(tex(maps["metalness"], (-600, 0)).outputs[0], bsdf.inputs["Metallic"])
    nt.links.new(tex(maps["roughness"], (-600, -250)).outputs[0], bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex(maps["normal"], (-800, -500)).outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return mat


def assign_single(objs, mat):
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.material_index = 0


def export(objs, fbx_path: Path, glb_path: Path | None = None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path), use_selection=True, object_types={"MESH"},
        axis_forward="Z", axis_up="Y", apply_scale_options="FBX_SCALE_UNITS",
        path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE",
        add_leaf_bones=False, bake_anim=False, use_mesh_modifiers=True,
    )
    if glb_path:
        bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True)


def bbox_local(ob):
    co = np.array([v.co[:] for v in ob.data.vertices])
    lo, hi = co.min(0), co.max(0)
    return (lo + hi) / 2, hi - lo
