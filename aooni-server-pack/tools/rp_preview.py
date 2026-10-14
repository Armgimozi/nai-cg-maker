"""아오오니 리소스팩 미리보기·검사 (개발용, Pillow + numpy 필요).

  python tools/rp_preview.py --out DIR [--zip dist/aooni-resourcepack.zip] [--manifest tools/rp_parts.json]

zip 안의 모델 JSON 과 텍스처, rp_parts.json 의 관절 좌표만 읽어서 그린다. 꼭짓점 변환은 클라이언트와 같은 순서:
  요소 회전(origin 둘레) → 모델px/16 - 0.5 → Y 180도 (ItemDisplayRenderer) → transformation (관절 이동·회전·크기) → 엔티티 yaw
조명은 바닐라 엔티티 조명(빛 방향 2개, 0.4 + 0.6*합)을 흉내 낸다. 뒷면은 버린다(게임과 같음).
1인칭 검사: 아오오니 플레이어의 눈(1.62 / 1.27)에서 여러 방향·시야각으로 그려, 머리 픽셀이 하나라도 보이면 실패.
"""
from __future__ import annotations

import io
import json
import math
import os
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_rp import FACE_VERTS, rotate_model_point  # noqa: E402  (클라이언트 FaceInfo 꼭짓점 순서, 요소 회전)

L0 = np.array([0.2, 1.0, -0.7]) / np.linalg.norm([0.2, 1.0, -0.7])
L1 = np.array([-0.2, 1.0, 0.7]) / np.linalg.norm([-0.2, 1.0, 0.7])
UVIDX = [(0, 1), (0, 3), (2, 3), (2, 1)]   # 꼭짓점 i 의 (u 인덱스, v 인덱스) in [u1,v1,u2,v2]


def rot_x(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.array([v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c])


def rot_y(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.array([v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c])


def load(zip_path, manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        man = json.load(f)
    parts = {}
    with zipfile.ZipFile(zip_path) as z:
        texcache = {}
        for name, info in man["parts"].items():
            ns, p = info["item_model"].split(":")
            item = json.loads(z.read(f"assets/{ns}/items/{p}.json"))
            mns, mp = item["model"]["model"].split(":")
            model = json.loads(z.read(f"assets/{mns}/models/{mp}.json"))
            tex = {}
            for k, ref in model["textures"].items():
                if ref not in texcache:
                    tns, tp = ref.split(":")
                    texcache[ref] = np.array(Image.open(io.BytesIO(z.read(f"assets/{tns}/textures/{tp}.png"))).convert("RGBA"))
                tex[k] = texcache[ref]
            parts[name] = (info, model, tex)
        icon = Image.open(io.BytesIO(z.read("pack.png"))).convert("RGBA")
        sword = Image.open(io.BytesIO(z.read("assets/aooni/textures/item/magum.png"))).convert("RGBA")
    return man, parts, icon, sword


def build_quads(parts, pose=None, scale=1.0, yaw=0.0, only=None):
    """월드 좌표의 사각형 목록: (꼭짓점 4개, uv 4개, 텍스처, 부위)."""
    pose = pose or {}
    quads = []
    for name, (info, model, tex) in parts.items():
        if only and name not in only:
            continue
        joint = np.array(info["joint"]) * scale
        ang = math.radians(pose.get(name, 0.0))
        for e in model["elements"]:
            frm, to = e["from"], e["to"]
            ext = {"x0": frm[0], "x1": to[0], "y0": frm[1], "y1": to[1], "z0": frm[2], "z1": to[2]}
            for fname, f in e["faces"].items():
                vs = []
                for vert in FACE_VERTS[fname]:
                    m = rotate_model_point(tuple(ext[k] for k in vert), e.get("rotation"))
                    v = np.array(m, dtype=float) / 16.0 - 0.5     # ItemTransform.NO_TRANSFORM: translate(-0.5)
                    v = np.array([-v[0], v[1], -v[2]])           # ItemDisplayRenderer: Axis.YP.rotation(pi)
                    v = rot_x(v, ang) * scale + joint            # transformation: T * L(rot) * S
                    v = rot_y(v, math.radians(-yaw))             # 엔티티: rotationYXZ(-yaw, 0, 0)
                    vs.append(v)
                uv = f["uv"]
                quads.append((vs, [(uv[a], uv[b]) for a, b in UVIDX], tex[f["texture"][1:]], name))
    return quads


def light(n):
    return min(1.0, 0.4 + 0.6 * (max(0.0, float(n @ L0)) + max(0.0, float(n @ L1))))


class Cam:
    def __init__(self, w, h, ortho=True, az=0.0, el=0.0, center=(0, 1.2, 0), ppb=200.0, pos=None, fwd=None, fov=70.0):
        self.w, self.h, self.ortho = w, h, ortho
        if fwd is None:
            a, e = math.radians(az), math.radians(el)
            fwd = -np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])
        self.f = np.array(fwd, dtype=float) / np.linalg.norm(fwd)
        up = np.array([0.0, 1.0, 0.0])
        if abs(self.f @ up) > 0.999:
            up = np.array([0.0, 0.0, -1.0 if self.f[1] < 0 else 1.0])
        self.r = np.cross(self.f, up)
        self.r /= np.linalg.norm(self.r)
        self.u = np.cross(self.r, self.f)
        self.c = np.array(center, dtype=float)
        self.ppb = ppb
        self.pos = np.array(pos, dtype=float) if pos is not None else None
        self.focal = (h / 2) / math.tan(math.radians(fov) / 2)

    def to_cam(self, p):
        d = p - (self.c if self.ortho else self.pos)
        return np.array([d @ self.r, d @ self.u, d @ self.f])

    def project_cam(self, c):
        if self.ortho:
            return (self.w / 2 + c[0] * self.ppb, self.h / 2 - c[1] * self.ppb, c[2])
        return (self.w / 2 + c[0] / c[2] * self.focal, self.h / 2 - c[1] / c[2] * self.focal, c[2])

    def project(self, p):
        return self.project_cam(self.to_cam(p))

    def facing(self, n, p0):
        if self.ortho:
            return n @ self.f < 0
        return n @ (p0 - self.pos) < 0


def clip_near(poly, near):
    """Sutherland–Hodgman: 카메라 공간 다각형 [(xyz, uv)] 을 z >= near 로 자른다."""
    out = []
    for i in range(len(poly)):
        (a, ua), (b, ub) = poly[i], poly[(i + 1) % len(poly)]
        ina, inb = a[2] >= near, b[2] >= near
        if ina:
            out.append((a, ua))
        if ina != inb:
            t = (near - a[2]) / (b[2] - a[2])
            out.append((a + (b - a) * t, (ua[0] + (ub[0] - ua[0]) * t, ua[1] + (ub[1] - ua[1]) * t)))
    return out


def render(quads, cam, bg=None, near=0.05, count=False):
    W, H = cam.w, cam.h
    img = np.zeros((H, W, 3), dtype=np.float32) if bg is None else bg.astype(np.float32).copy()
    zbuf = np.full((H, W), np.inf)
    owner = np.full((H, W), -1, dtype=np.int32)
    names = []
    for vs, uvs, tex, name in quads:
        n = np.cross(vs[1] - vs[0], vs[2] - vs[0])
        nl = np.linalg.norm(n)
        if nl == 0:
            continue
        n = n / nl
        if not cam.facing(n, vs[0]):
            continue
        shade = light(n)
        poly = [(cam.to_cam(v), uv) for v, uv in zip(vs, uvs)]
        if not cam.ortho:
            poly = clip_near(poly, near)
            if len(poly) < 3:
                continue
        pr = [(cam.project_cam(c), uv) for c, uv in poly]
        th, tw = tex.shape[0], tex.shape[1]
        if name not in names:
            names.append(name)
        nid = names.index(name)
        for k in range(1, len(pr) - 1):
            (P0, U0), (P1, U1), (P2, U2) = pr[0], pr[k], pr[k + 1]
            P, U = (P0, P1, P2), (U0, U1, U2)
            x0 = max(int(math.floor(min(p[0] for p in P))), 0)
            x1 = min(int(math.ceil(max(p[0] for p in P))), W - 1)
            y0 = max(int(math.floor(min(p[1] for p in P))), 0)
            y1 = min(int(math.ceil(max(p[1] for p in P))), H - 1)
            if x0 > x1 or y0 > y1:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-12:
                continue
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
            w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
            w2 = 1 - w0 - w1
            m = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
            if not m.any():
                continue
            if cam.ortho:
                z = w0 * az + w1 * bz + w2 * cz
                k0, k1, k2 = w0, w1, w2
            else:
                z = 1 / (w0 / az + w1 / bz + w2 / cz)
                k0, k1, k2 = w0 / az * z, w1 / bz * z, w2 / cz * z
            sub = zbuf[y0:y1 + 1, x0:x1 + 1]
            m &= z < sub
            if not m.any():
                continue
            u = k0 * U[0][0] + k1 * U[1][0] + k2 * U[2][0]
            v = k0 * U[0][1] + k1 * U[1][1] + k2 * U[2][1]
            tx = np.clip((u / 16 * tw).astype(int), 0, tw - 1)
            ty = np.clip((v / 16 * th).astype(int), 0, th - 1)
            col = tex[ty, tx, :3].astype(np.float32) * shade
            sub[m] = z[m]
            img[y0:y1 + 1, x0:x1 + 1][m] = col[m]
            owner[y0:y1 + 1, x0:x1 + 1][m] = nid
    if count:
        return img, {nm: int((owner == i).sum()) for i, nm in enumerate(names)}
    return img


def backdrop(w, h, top=(34, 36, 52), bottom=(12, 12, 18)):
    t = np.linspace(0, 1, h)[:, None, None]
    a = np.array(top, dtype=np.float32)[None, None, :]
    b = np.array(bottom, dtype=np.float32)[None, None, :]
    return np.broadcast_to(a + (b - a) * t, (h, w, 3)).copy()


def finish(img, ss):
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if ss > 1:
        im = im.resize((im.width // ss, im.height // ss), Image.LANCZOS)
    return im


def player_proxy(x_off):
    """크기 비교용 회색 플레이어(1.8 블록)."""
    boxes = [((-0.25, 1.5, -0.25), (0.25, 2.0, 0.25)), ((-0.25, 0.75, -0.125), (0.25, 1.5, 0.125)),
             ((-0.5, 0.75, -0.125), (-0.25, 1.5, 0.125)), ((0.25, 0.75, -0.125), (0.5, 1.5, 0.125)),
             ((-0.25, 0.0, -0.125), (0.0, 0.75, 0.125)), ((0.0, 0.0, -0.125), (0.25, 0.75, 0.125))]
    gray = np.full((1, 1, 4), 150, dtype=np.uint8)
    quads = []
    for lo, hi in boxes:
        lo = np.array(lo) + [x_off, 0, 0]
        hi = np.array(hi) + [x_off, 0, 0]
        ext = {"x0": lo[0], "x1": hi[0], "y0": lo[1], "y1": hi[1], "z0": lo[2], "z1": hi[2]}
        for verts in FACE_VERTS.values():
            quads.append(([np.array([ext[k] for k in vv]) for vv in verts], [(0, 0)] * 4, gray, "proxy"))
    return quads


def ruler(im, cam, ss):
    """세로 눈금(0.5 블록)과 눈 높이 1.62 선."""
    d = ImageDraw.Draw(im)
    for i in range(0, 6):
        y = i * 0.5
        _, sy, _ = cam.project(np.array([cam.c[0], y, cam.c[2]]))
        sy /= ss
        d.line([(4, sy), (16, sy)], fill=(120, 120, 140))
        d.text((20, sy - 6), f"{y:.1f}", fill=(140, 140, 160))
    _, sy, _ = cam.project(np.array([cam.c[0], 1.62, cam.c[2]]))
    sy /= ss
    d.line([(4, sy), (im.width - 4, sy)], fill=(200, 60, 60))
    d.text((im.width - 120, sy - 14), "eye 1.62", fill=(220, 90, 90))


def render_all(zip_path, manifest_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    man, parts, icon, sword = load(zip_path, manifest_path)
    ss = 2
    W, H = 560, 760
    outs = []
    base = build_quads(parts)
    for tag, az, el in (("front", 0, 0), ("side", 90, 0), ("34", 35, 14)):
        cam = Cam(W * ss, H * ss, az=az, el=el, center=(0.55 if tag == "front" else 0, 1.25, 0), ppb=250 * ss)
        q = base + (player_proxy(1.15) if tag == "front" else [])
        im = finish(render(q, cam, backdrop(W * ss, H * ss)), ss)
        ruler(im, cam, ss)
        p = os.path.join(out_dir, f"rp_preview_{tag}.png")
        im.save(p)
        outs.append(p)
    # 걷는 자세 (관절 확인용): 옆 / 3/4 / 뒤에서
    pose = {"arm_l": -35, "arm_r": 35, "leg_l": 30, "leg_r": -30, "head": 20, "torso": 0}
    walk = build_quads(parts, pose=pose)
    tiles = []
    for az, el in ((90, 0), (35, 14), (-140, 20)):
        cam = Cam(W * ss, H * ss, az=az, el=el, center=(0, 1.25, 0), ppb=250 * ss)
        tiles.append(finish(render(walk, cam, backdrop(W * ss, H * ss)), ss))
    sheet = Image.new("RGB", (W * len(tiles), H))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * W, 0))
    p = os.path.join(out_dir, "rp_preview_walk.png")
    sheet.save(p)
    outs.append(p)
    # 마검 (어두운/밝은 바탕, 1x 2x 4x) + pack.png
    S = 32
    big = sword.resize((S * 12, S * 12), Image.NEAREST)
    sheet = Image.new("RGBA", (S * 12 * 2 + 60 + 200, S * 12 + 40), (24, 24, 30, 255))
    sheet.alpha_composite(big, (20, 20))
    light_bg = Image.new("RGBA", big.size, (200, 200, 205, 255))
    light_bg.alpha_composite(big)
    sheet.alpha_composite(light_bg, (S * 12 + 30, 20))
    x = S * 12 * 2 + 45
    for k in (1, 2, 4):
        sheet.alpha_composite(sword.resize((S * k, S * k), Image.NEAREST), (x, 20))
        x += S * k + 10
    sheet.alpha_composite(icon, (S * 12 * 2 + 45, 200))
    p = os.path.join(out_dir, "rp_preview_sword.png")
    sheet.convert("RGB").save(p)
    outs.append(p)
    # 1인칭(머리 안) 검사
    lines, fp, fails = first_person_check(parts, man)
    p = os.path.join(out_dir, "rp_preview_firstperson.png")
    fp.save(p)
    outs.append(p)
    for line in lines:
        print("  ", line)
    return outs, fails


def first_person_check(parts, man):
    """아오오니 플레이어 눈에서 사방을 본다. 머리 픽셀이 하나라도 보이면 실패."""
    W, H = 256, 144
    lines, tiles, fails = [], [], []
    n = 0
    for head_pitch in (-30, 0, 30):
        quads = build_quads(parts, pose={"head": head_pitch})
        for eye in (man["camera"]["standing_eye_y"], man["camera"]["sneaking_eye_y"]):
            for fov in (70, 126):
                for pitch in (-90, -60, -30, 0, 30, 60, 89):
                    for yaw in (0, 45, 90, 135, 180, 225, 270, 315):
                        a, p = math.radians(yaw), math.radians(pitch)
                        fwd = np.array([-math.sin(a) * math.cos(p), -math.sin(p), math.cos(a) * math.cos(p)])
                        cam = Cam(W, H, ortho=False, pos=(0, eye, 0), fwd=fwd, fov=fov)
                        img, cnt = render(quads, cam, backdrop(W, H, (90, 110, 140), (60, 70, 80)), count=True)
                        n += 1
                        if cnt.get("head", 0):
                            fails.append(f"1인칭: 눈 {eye}, 고개 {head_pitch}, 시야 {fov}, yaw {yaw}, pitch {pitch} 에서 머리 픽셀 {cnt['head']}개")
                        if head_pitch == 0 and fov == 70 and yaw == 0 and pitch in (0, 60, 89):
                            tiles.append((f"eye {eye}  pitch {pitch}", finish(img, 1)))
    lines.append(f"1인칭 검사 {n}장: " + ("머리가 한 번도 보이지 않음" if not fails else f"{len(fails)}장에서 머리가 보임"))
    sheet = Image.new("RGB", (W * 3, (H + 20) * 2), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i, (label, t) in enumerate(tiles):
        x, y = (i % 3) * W, (i // 3) * (H + 20)
        sheet.paste(t, (x, y + 20))
        d.text((x + 4, y + 4), label, fill=(255, 255, 255))
    return lines, sheet, fails


def main():
    args = sys.argv[1:]
    if "--out" not in args:
        raise SystemExit(__doc__)
    out = args[args.index("--out") + 1]
    root = os.path.dirname(HERE)
    zp = args[args.index("--zip") + 1] if "--zip" in args else os.path.join(root, "dist", "aooni-resourcepack.zip")
    mp = args[args.index("--manifest") + 1] if "--manifest" in args else os.path.join(HERE, "rp_parts.json")
    paths, fails = render_all(zp, mp, out)
    for p in paths:
        print(p)
    for f in fails:
        print("FAIL", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
