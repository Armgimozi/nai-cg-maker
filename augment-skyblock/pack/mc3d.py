"""
마인크래프트 3D 아이템 모델을 코드로 만드는 도구.

- Atlas: 한 장의 텍스처에 색 칸(셀)과 그림 영역을 나눠 담는다. 애니메이션 프레임도 지원.
- Model: 박스(element)를 쌓아 모델을 만든다. 면마다 셀을 지정하거나 그림 영역을 그대로 붙인다.
          light_emission(어둠 속에서도 밝게)과 element 회전을 지원한다.
- extrude(): 픽셀 그림을 두께가 있는 3D 로 뽑아낸다 (무기용).
- render(): 게임 밖에서 모델을 미리 보기 위한 간단한 소프트웨어 렌더러.

좌표: 모델 공간 0..16 이 한 블록. 앞면은 +Z(south). 아이템 디스플레이에서 (8,8,8) 이 엔티티 위치다.
"""
import colorsys
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw

LIMIT_MIN, LIMIT_MAX = -16.0, 32.0


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3)) + (c1[3] if len(c1) > 3 else 255,)


def shade(c, f):
    if f >= 1:
        return mix(c, (255, 255, 255, c[3] if len(c) > 3 else 255), min(1, f - 1))
    return mix((0, 0, 0, c[3] if len(c) > 3 else 255), c, f)


def hsv(h, s, v, a=255):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255), a)


# ─────────────────────────────── 텍스처 아틀라스 ───────────────────────────────

class Atlas:
    """
    한 장짜리 텍스처. alloc(w, h) 로 빈 영역을 받아 그림을 그린다.
    frames > 1 이면 세로로 프레임을 쌓아 애니메이션 텍스처가 된다 (모든 프레임이 같은 배치).
    """

    def __init__(self, name, size=64, frames=1, frametime=2, interpolate=True, seed=0):
        self.name = name  # 예: "boss/frost_tyrant"
        self.size = size
        self.frames = frames
        self.frametime = frametime
        self.interpolate = interpolate
        self.img = Image.new("RGBA", (size, size * frames), (0, 0, 0, 0))
        self.cursor_x = 0
        self.cursor_y = 0
        self.row_h = 0
        self.rnd = random.Random(seed)
        self.cells = {}

    # 단순 선반 배치
    def alloc(self, w, h):
        if self.cursor_x + w > self.size:
            self.cursor_x = 0
            self.cursor_y += self.row_h
            self.row_h = 0
        if self.cursor_y + h > self.size:
            raise ValueError(f"아틀라스 {self.name} 가 가득 찼습니다 (size={self.size})")
        x, y = self.cursor_x, self.cursor_y
        self.cursor_x += w
        self.row_h = max(self.row_h, h)
        return Region(self, x, y, w, h)

    def cell(self, color, style="noise", size=4, glow=False, key=None):
        """
        한 가지 색의 작은 칸. 같은 (색, 스타일) 은 한 번만 만든다.
        style: flat, noise, grad(위가 밝음), metal(줄무늬 광택), crack(갈라진 무늬), sparkle(반짝임)
        color 가 함수(frame, x, y, w, h) -> 색 이면 애니메이션 칸이 된다.
        """
        k = key or (color if not callable(color) else id(color), style, size)
        if k in self.cells:
            return self.cells[k]
        r = self.alloc(size, size)
        for f in range(self.frames):
            for yy in range(size):
                for xx in range(size):
                    if callable(color):
                        c = color(f, xx, yy, size, size)
                    else:
                        c = _styled(color, style, xx, yy, size, self.rnd)
                    r.put(f, xx, yy, c)
        self.cells[k] = r
        return r

    def save(self, tex_root):
        path = os.path.join(tex_root, self.name + ".png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.img.save(path)
        if self.frames > 1:
            with open(path + ".mcmeta", "w", encoding="utf-8") as f:
                json.dump({"animation": {"frametime": self.frametime, "interpolate": self.interpolate}}, f)

    def frame0(self):
        return self.img.crop((0, 0, self.size, self.size))


def _styled(c, style, x, y, n, rnd):
    if style == "flat":
        return c
    if style == "noise":
        return shade(c, 0.9 + rnd.random() * 0.2)
    if style == "grad":
        return shade(c, 1.12 - 0.3 * y / max(1, n - 1))
    if style == "metal":
        k = ((x + y) % n) / max(1, n - 1)
        return shade(c, 0.85 + 0.35 * (1 - abs(k - 0.35) * 2))
    if style == "crack":
        return shade(c, 0.55) if (x * 3 + y * 5) % 7 == 0 else shade(c, 0.95 + rnd.random() * 0.1)
    if style == "sparkle":
        return (255, 255, 255, 255) if rnd.random() < 0.12 else shade(c, 0.9 + rnd.random() * 0.2)
    return c


class Region:
    """아틀라스 안의 사각 영역. 픽셀 좌표와 UV(0..16) 를 둘 다 안다."""

    def __init__(self, atlas, x, y, w, h):
        self.atlas, self.x, self.y, self.w, self.h = atlas, x, y, w, h

    def put(self, frame, x, y, color):
        self.atlas.img.putpixel((self.x + x, frame * self.atlas.size + self.y + y), tuple(color))

    def paste(self, img, frame=0):
        self.atlas.img.alpha_composite(img.convert("RGBA"), (self.x, frame * self.atlas.size + self.y))

    def uv(self, sub=None):
        s = 16.0 / self.atlas.size
        if sub:
            x0, y0, x1, y1 = sub
            return [round((self.x + x0) * s, 4), round((self.y + y0) * s, 4),
                    round((self.x + x1) * s, 4), round((self.y + y1) * s, 4)]
        # 가장자리 번짐을 막으려고 살짝 안쪽을 쓴다
        e = 0.0 if (self.w > 2 and self.h > 2) else 0.0
        return [round((self.x + e) * s, 4), round((self.y + e) * s, 4),
                round((self.x + self.w - e) * s, 4), round((self.y + self.h - e) * s, 4)]


# ─────────────────────────────── 모델 ───────────────────────────────

FACES = ("north", "south", "east", "west", "up", "down")


class Model:
    def __init__(self, name, textures=None, parent=None):
        self.name = name                    # 예: "item/flame_sword", "boss/frost_head"
        self.textures = dict(textures or {})  # 키 -> 텍스처 이름 (Atlas.name)
        self.atlases = {}                    # 키 -> Atlas (미리보기용)
        self.elements = []
        self.display = {}
        self.parent = parent

    def use(self, key, atlas):
        self.textures[key] = "augsky:" + atlas.name
        self.atlases[key] = atlas
        return key

    def box(self, frm, to, faces, light=0, shade=True, rotation=None, cull=False):
        """
        faces: {"north": (key, Region 또는 uv리스트, rot) ...} 혹은 모든 면에 같은 값을 줄 때 (key, Region)
        rotation: {"origin": [x,y,z], "axis": "y", "angle": 22.5}
        """
        frm = [float(v) for v in frm]
        to = [float(v) for v in to]
        for i in range(3):
            if frm[i] > to[i]:
                frm[i], to[i] = to[i], frm[i]
        if isinstance(faces, tuple):
            faces = {f: faces for f in FACES}
        el = {"from": [round(v, 4) for v in frm], "to": [round(v, 4) for v in to], "faces": {}}
        for f, spec in faces.items():
            if spec is None:
                continue
            key, reg = spec[0], spec[1]
            rot = spec[2] if len(spec) > 2 else 0
            uv = reg.uv() if isinstance(reg, Region) else list(reg)
            face = {"texture": "#" + key, "uv": uv}
            if rot:
                face["rotation"] = rot
            el["faces"][f] = face
        if light:
            el["light_emission"] = int(light)
        if not shade:
            el["shade"] = False
        if rotation:
            el["rotation"] = dict(rotation)
        self.elements.append(el)
        return el

    def cube(self, center, size, faces, **kw):
        cx, cy, cz = center
        sx, sy, sz = size if isinstance(size, (list, tuple)) else (size, size, size)
        return self.box((cx - sx / 2, cy - sy / 2, cz - sz / 2), (cx + sx / 2, cy + sy / 2, cz + sz / 2), faces, **kw)

    def bounds(self):
        lo = [1e9] * 3
        hi = [-1e9] * 3
        for el in self.elements:
            for i in range(3):
                lo[i] = min(lo[i], el["from"][i])
                hi[i] = max(hi[i], el["to"][i])
        return lo, hi

    def check(self):
        lo, hi = self.bounds()
        bad = [i for i in range(3) if lo[i] < LIMIT_MIN - 1e-6 or hi[i] > LIMIT_MAX + 1e-6]
        if bad:
            raise ValueError(f"모델 {self.name} 가 -16..32 범위를 벗어남: {lo} ~ {hi}")
        for el in self.elements:
            r = el.get("rotation")
            if r and r["angle"] not in (-45, -22.5, 0, 22.5, 45):
                raise ValueError(f"모델 {self.name}: element 회전은 -45~45 의 22.5 배수만 됩니다")

    def to_json(self):
        self.check()
        j = {}
        if self.parent:
            j["parent"] = self.parent
        j["textures"] = self.textures
        if "particle" not in j["textures"] and self.textures:
            j["textures"]["particle"] = next(iter(self.textures.values()))
        j["elements"] = self.elements
        if self.display:
            j["display"] = self.display
        return j

    def write(self, assets_root):
        """assets/augsky/models/<name>.json 과 items/<name>.json(아이템 정의)을 쓴다."""
        mpath = os.path.join(assets_root, "models", self.name + ".json")
        os.makedirs(os.path.dirname(mpath), exist_ok=True)
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, separators=(",", ":"))
        item_name = self.name[len("item/"):] if self.name.startswith("item/") else self.name
        ipath = os.path.join(assets_root, "items", item_name + ".json")
        os.makedirs(os.path.dirname(ipath), exist_ok=True)
        with open(ipath, "w", encoding="utf-8") as f:
            json.dump({"model": {"type": "minecraft:model", "model": "augsky:" + self.name}}, f)
        return "augsky:" + item_name


# ─────────────────────────────── 픽셀 그림 → 3D ───────────────────────────────

def extrude(model, key, atlas_region, sprite, depth_of, px=0.5, origin=(0.0, 0.0), zc=8.0,
            light_of=None, skip=None):
    """
    sprite: RGBA PIL 이미지 (atlas_region 에 이미 붙여 둔 것과 같은 그림)
    depth_of(x, y) -> 그 픽셀의 두께(모델 단위). 0 이면 비운다.
    같은 두께/같은 발광의 픽셀을 가로로 이은 뒤 세로로 합쳐 박스 수를 줄인다.
    앞(south)/뒤(north) 면은 그림을 그대로, 옆면은 가장자리 한 줄을 쓴다.
    """
    w, h = sprite.size
    a = np.array(sprite)
    depth = np.zeros((h, w))
    light = np.zeros((h, w), dtype=int)
    for y in range(h):
        for x in range(w):
            if a[y, x, 3] < 20:
                continue
            if skip and skip(x, y):
                continue
            depth[y, x] = depth_of(x, y)
            if light_of:
                light[y, x] = light_of(x, y)
    used = np.zeros((h, w), dtype=bool)
    ox, oy = origin
    count = 0
    for y in range(h):
        x = 0
        while x < w:
            d = depth[y, x]
            if d <= 0 or used[y, x]:
                x += 1
                continue
            lv = light[y, x]
            x1 = x
            while x1 + 1 < w and depth[y, x1 + 1] == d and light[y, x1 + 1] == lv and not used[y, x1 + 1]:
                x1 += 1
            y1 = y
            while y1 + 1 < h and all(depth[y1 + 1, xx] == d and light[y1 + 1, xx] == lv and not used[y1 + 1, xx]
                                     for xx in range(x, x1 + 1)):
                y1 += 1
            used[y:y1 + 1, x:x1 + 1] = True
            # 모델 좌표: 그림의 아래쪽이 y 가 작다
            fx0 = ox + x * px
            fx1 = ox + (x1 + 1) * px
            fy0 = oy + (h - 1 - y1) * px
            fy1 = oy + (h - y) * px
            z0, z1 = zc - d / 2, zc + d / 2
            rx, ry = atlas_region.x, atlas_region.y
            s = 16.0 / atlas_region.atlas.size

            def uv(u0, v0, u1, v1):
                return [round((rx + u0) * s, 4), round((ry + v0) * s, 4), round((rx + u1) * s, 4), round((ry + v1) * s, 4)]

            faces = {
                "south": (key, uv(x, y, x1 + 1, y1 + 1)),
                "north": (key, uv(x1 + 1, y, x, y1 + 1)),
            }
            # 옆면: 이웃이 같거나 더 두꺼우면 가려지므로 생략
            def thinner(xx, yy):
                if xx < 0 or yy < 0 or xx >= w or yy >= h:
                    return True
                return depth[yy, xx] < d
            if any(thinner(x - 1, yy) for yy in range(y, y1 + 1)):
                faces["west"] = (key, uv(x, y, x + 1, y1 + 1))
            if any(thinner(x1 + 1, yy) for yy in range(y, y1 + 1)):
                faces["east"] = (key, uv(x1, y, x1 + 1, y1 + 1))
            if any(thinner(xx, y - 1) for xx in range(x, x1 + 1)):
                faces["up"] = (key, uv(x, y, x1 + 1, y + 1))
            if any(thinner(xx, y1 + 1) for xx in range(x, x1 + 1)):
                faces["down"] = (key, uv(x, y1, x1 + 1, y1 + 1))
            model.box((fx0, fy0, z0), (fx1, fy1, z1), faces, light=int(lv))
            count += 1
            x = x1 + 1
    return count


# ─────────────────────────────── 미리보기 렌더러 ───────────────────────────────

FACE_LIGHT = {"up": 1.0, "down": 0.5, "north": 0.8, "south": 0.8, "east": 0.62, "west": 0.62}


def _rot_matrix(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _face_corners(f, t):
    """면의 네 꼭짓점: (uv 좌상, 우상, 우하, 좌하) 순서. 마인크래프트 UV 규칙을 따른다."""
    x0, y0, z0 = f
    x1, y1, z1 = t
    return {
        "north": [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)],
        "south": [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)],
        "east": [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)],
        "west": [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)],
        "up": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        "down": [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
    }


def _homography(src, dst):
    """dst(화면) → src(텍스처) 로 가는 PIL PERSPECTIVE 계수."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    try:
        return np.linalg.solve(np.array(A, dtype=float), np.array(B, dtype=float)).tolist()
    except np.linalg.LinAlgError:
        return None


def render(parts, size=512, yaw=-35, pitch=25, bg=(24, 22, 32, 255), pad=0.08, scale=None, center=None):
    """
    parts: [(Model, 4x4 행렬 또는 None)] — 모델 좌표(0..16)를 월드 좌표(블록 단위)로 보내는 변환.
    yaw/pitch: 카메라 각도(도). 정사영.
    """
    ry = _rot_matrix("y", yaw)
    rx = _rot_matrix("x", pitch)
    view = rx @ ry
    faces = []
    for model, mat in parts:
        M = np.eye(4) if mat is None else np.array(mat, dtype=float)
        texs = {k: a.frame0() for k, a in model.atlases.items()}
        for el in model.elements:
            corners_by_face = _face_corners(el["from"], el["to"])
            rot = el.get("rotation")
            for fname, fd in el["faces"].items():
                key = fd["texture"].lstrip("#")
                tex = texs.get(key)
                if tex is None:
                    continue
                pts = []
                for p in corners_by_face[fname]:
                    v = np.array(p, dtype=float)
                    if rot:
                        o = np.array(rot["origin"], dtype=float)
                        v = _rot_matrix(rot["axis"], rot["angle"]) @ (v - o) + o
                    v = (v - 8.0) / 16.0  # 블록 단위, 원점 중심
                    w4 = M @ np.append(v, 1.0)
                    pts.append(view @ w4[:3])
                pts = np.array(pts)
                n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
                if n[2] >= 0:  # 카메라(-z 쪽을 봄) 반대편 면은 생략
                    continue
                light = 1.0 if el.get("light_emission", 0) >= 8 else FACE_LIGHT[fname]
                faces.append((pts, tex, fd["uv"], fd.get("rotation", 0), light))
    if not faces:
        return Image.new("RGBA", (size, size), bg)
    allp = np.concatenate([f[0] for f in faces])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
    sc = scale or size * (1 - 2 * pad) / span
    cx = center[0] if center else (lo[0] + hi[0]) / 2
    cy = center[1] if center else (lo[1] + hi[1]) / 2
    img = Image.new("RGBA", (size, size), bg)
    faces.sort(key=lambda f: -f[0][:, 2].mean())  # 먼 면부터 (z 가 클수록 멀다)
    for pts, tex, uv, frot, light in faces:
        scr = [((p[0] - cx) * sc + size / 2, -(p[1] - cy) * sc + size / 2) for p in pts]
        tw, th = tex.size
        u0, v0, u1, v1 = [c / 16.0 * tw if i % 2 == 0 else c / 16.0 * th for i, c in enumerate(uv)]
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        xs = [p[0] for p in scr]
        ys = [p[1] for p in scr]
        bx0, by0 = int(max(0, math.floor(min(xs)))), int(max(0, math.floor(min(ys))))
        bx1, by1 = int(min(size, math.ceil(max(xs)) + 1)), int(min(size, math.ceil(max(ys)) + 1))
        if bx1 <= bx0 or by1 <= by0:
            continue
        local = [(x - bx0, y - by0) for x, y in scr]
        coeffs = _homography(src, local)
        if coeffs is None:
            continue
        patch = tex.transform((bx1 - bx0, by1 - by0), Image.PERSPECTIVE, coeffs, Image.NEAREST)
        arr = np.array(patch).astype(float)
        # 알파 252/251/250 = 스스로 빛나는 픽셀 (게임에서는 pack/shaders 의 셰이더가 처리)
        glow = (arr[..., 3] >= 249.5) & (arr[..., 3] <= 252.5)
        if light < 1.0:
            arr[..., :3] = np.where(glow[..., None], arr[..., :3], arr[..., :3] * light)
        arr[..., 3] = np.where(arr[..., 3] > 251.5, np.where(glow, 255, arr[..., 3]),
                               np.where(arr[..., 3] > 250.5, np.where(glow, 191, arr[..., 3]), np.where(glow, 128, arr[..., 3])))
        patch = Image.fromarray(arr.clip(0, 255).astype("uint8"), "RGBA")
        mask = Image.new("L", patch.size, 0)
        ImageDraw.Draw(mask).polygon(local, fill=255)
        alpha = np.minimum(np.array(mask), np.array(patch.split()[3]))
        patch.putalpha(Image.fromarray(alpha))
        img.alpha_composite(patch, (bx0, by0))
    return img


def mat(translate=(0, 0, 0), scale=1.0, yaw=0.0, pitch=0.0, roll=0.0):
    """미리보기용 4x4 행렬: 크기 → roll(z) → pitch(x) → yaw(y) → 이동."""
    s = np.diag([scale, scale, scale]) if not isinstance(scale, (list, tuple)) else np.diag(scale)
    r = _rot_matrix("y", yaw) @ _rot_matrix("x", pitch) @ _rot_matrix("z", roll)
    m = np.eye(4)
    m[:3, :3] = r @ s
    m[:3, 3] = translate
    return m


def contact_sheet(images, labels=None, cols=4, cell=256, font=None, bg=(18, 16, 26)):
    from PIL import ImageFont
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + (24 if labels else 0))), bg)
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(font, 16) if font else ImageFont.load_default()
    for i, im in enumerate(images):
        x, y = (i % cols) * cell, (i // cols) * (cell + (24 if labels else 0))
        sheet.paste(im.convert("RGB").resize((cell, cell)), (x, y))
        if labels:
            d.text((x + 6, y + cell + 3), labels[i], font=f, fill=(230, 230, 240))
    return sheet
