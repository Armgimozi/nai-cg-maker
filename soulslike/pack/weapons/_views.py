"""
무기 미리보기 (게임 밖 흉내). 깊이 버퍼가 있는 작은 소프트웨어 렌더러로 바닐라의 손 사슬을 그대로 따라 그린다.

  gui(icon)                 16px 그림: 크게 한 장 + 단축 슬롯 크기 (GUI 배율 2, 3)
  side(model)               3D 모형만: 앞면 (+Z), 비스듬히, 날 쪽 (−X) 에서
  first_person(...)         1인칭 (1280×720, 세로 시야 70°, 바닐라 손 그림의 시야는 늘 70°): ItemInHandRenderer 의
                            applyItemArmTransform T(±0.56, −0.52, −0.72) 뒤 아이템 1인칭 자세. 막기 (BLOCK) 는 방패가 아닌
                            아이템에 바닐라가 더 거는 몸짓까지
  third_person(...)         3인칭: 사람 모형 (넓은 팔, 0.9375 배) 의 팔 변환 → ItemInHandLayer 사슬
                            Rx(−90°)·Ry(180°)·T(±1/16, 0.125, −0.625) → 아이템 3인칭 자세
  lineup(...)               쥐는 점 높이를 맞춰 키 2 블록 사람 그림자 곁에 세운 줄 (비례 확인)

빛: 바닐라 엔티티 빛과 비슷하게 두 방향 빛 (0.2, 1, −0.7), (−0.2, 1, 0.7) + 바탕 0.4. 실제 게임 화면은 13.4 로 따로 본다.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from mc3d import Atlas, Model, _face_corners

BG = (34, 32, 30, 255)
L0 = np.array([0.2, 1.0, -0.7]) / np.linalg.norm([0.2, 1.0, -0.7])
L1 = np.array([-0.2, 1.0, 0.7]) / np.linalg.norm([-0.2, 1.0, 0.7])
FACE_N = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


# ─────────────────────────── 행렬 ───────────────────────────

def R(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    m = np.eye(4)
    if axis == "x":
        m[1:3, 1:3] = [[c, -s], [s, c]]
    elif axis == "y":
        m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    else:
        m[0:2, 0:2] = [[c, -s], [s, c]]
    return m


def T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = [x, y, z]
    return m


def S(x, y=None, z=None):
    y = x if y is None else y
    z = x if z is None else z
    return np.diag([x, y, z, 1.0])


def xyz(rx, ry, rz):
    """JOML rotationXYZ (모형 display 의 rotation)."""
    return R("x", rx) @ R("y", ry) @ R("z", rz)


def display_matrix(d, left=False):
    """모형 display 한 칸 → 4×4 (바닐라 ItemTransform.apply). 왼손은 x 이동과 y·z 회전을 뒤집는다."""
    t = list(d.get("translation", [0, 0, 0]))
    r = list(d.get("rotation", [0, 0, 0]))
    s = d.get("scale", [1, 1, 1])
    if left:
        t[0] = -t[0]
        r[1], r[2] = -r[1], -r[2]
    return T(t[0] / 16, t[1] / 16, t[2] / 16) @ xyz(*r) @ S(*s)


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = (np.array(v, float) for v in (eye, target, up))
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    V = np.eye(4)
    V[0, :3], V[1, :3], V[2, :3] = r, u, -f
    V[:3, 3] = -V[:3, :3] @ eye
    return V


# ─────────────────────────── 장면 ───────────────────────────

class Scene:
    def __init__(self):
        self.faces = []   # (corners world 4×3, tex img, uv, rot, normal world, emission)

    def add(self, model, M=None, tint=None):
        """모형 좌표 (0..16) 를 (p − 8)/16 블록으로 옮긴 뒤 M 을 건다 (바닐라 아이템 그리기와 같다)."""
        M = np.eye(4) if M is None else np.asarray(M, float)
        texs = {k: a.frame0() for k, a in model.atlases.items()}
        M3 = M[:3, :3]
        for el in model.elements:
            corners = _face_corners(el["from"], el["to"])
            rot = el.get("rotation")
            for fname, fd in el["faces"].items():
                tex = texs.get(fd["texture"].lstrip("#"))
                if tex is None:
                    continue
                pts = []
                for p in corners[fname]:
                    v = np.array(p, float)
                    if rot:
                        o = np.array(rot["origin"], float)
                        v = R(rot["axis"], rot["angle"])[:3, :3] @ (v - o) + o
                    v = (v - 8.0) / 16.0
                    pts.append((M @ np.append(v, 1.0))[:3])
                n = np.array(FACE_N[fname], float)
                if rot:
                    n = R(rot["axis"], rot["angle"])[:3, :3] @ n
                n = M3 @ n
                n /= np.linalg.norm(n) or 1
                shade = el.get("shade", True)
                self.faces.append((np.array(pts), tex, fd["uv"], fd.get("rotation", 0), n,
                                   el.get("light_emission", 0), shade, tint))
        return self

    def box(self, frm, to, color, M=None):
        """단색 상자 (사람 모형, 그림자). frm/to 는 블록 단위."""
        m = Model("preview/box")
        at = Atlas("preview/box", size=4)
        reg = at.alloc(4, 4)
        reg.paste(Image.new("RGBA", (4, 4), color))
        m.use("c", at)
        f = [v * 16 + 8 for v in frm]
        t = [v * 16 + 8 for v in to]
        m.box(f, t, ("c", reg))
        return self.add(m, M)


def _homography(src, dst):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    try:
        return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()
    except np.linalg.LinAlgError:
        return None


def render(scene, V, size=(512, 512), ortho=None, fov=70.0, bg=BG, light=1.0, center=None, lights=(L0, L1)):
    """
    V: 세계 → 카메라 (카메라는 −Z 를 본다, x 오른쪽, y 위).
    ortho: 1 블록의 화면 픽셀 수 (정사영). None 이면 원근 (세로 시야 fov).
    center: 정사영에서 화면 가운데에 둘 카메라 좌표 (x, y). light: 세계 밝기 (0..1, 빛 내는 요소는 그만큼 밝게 남는다).
    """
    W, H = size
    img = np.zeros((H, W, 4), float)
    img[...] = bg
    zbuf = np.full((H, W), -np.inf)
    f = 1.0 / math.tan(math.radians(fov) / 2)
    cx, cy = center or (0.0, 0.0)
    for pts, tex, uv, frot, n, emis, shade, tint in scene.faces:
        cam = (V @ np.c_[pts, np.ones(4)].T).T[:, :3]
        ncam = V[:3, :3] @ n
        if ortho:
            if ncam[2] <= 2e-3:
                continue
            scr = [((p[0] - cx) * ortho + W / 2, -(p[1] - cy) * ortho + H / 2) for p in cam]
            q = cam[:, 2]
        else:
            if np.any(cam[:, 2] > -0.02):
                continue
            if np.dot(ncam, -cam.mean(axis=0)) <= 1e-4:
                continue
            scr = [(p[0] / -p[2] * f * H / 2 + W / 2, -p[1] / -p[2] * f * H / 2 + H / 2) for p in cam]
            q = 1.0 / -cam[:, 2]
        xs = [p[0] for p in scr]
        ys = [p[1] for p in scr]
        bx0, by0 = int(max(0, math.floor(min(xs)))), int(max(0, math.floor(min(ys))))
        bx1, by1 = int(min(W, math.ceil(max(xs)) + 1)), int(min(H, math.ceil(max(ys)) + 1))
        if bx1 <= bx0 or by1 <= by0:
            continue
        tw, th = tex.size
        u0, v0, u1, v1 = [c / 16.0 * (tw if i % 2 == 0 else th) for i, c in enumerate(uv)]
        # uv 사각만 잘라 가장자리를 한 텍셀 늘린다: 다각형 가장자리 픽셀이 사각 밖을 집어도 이웃 칸·빈 곳을 집지 않게
        ua, ub = sorted((u0, u1))
        va, vb = sorted((v0, v1))
        ia, ib = int(math.floor(ua + 1e-4)), int(math.ceil(ub - 1e-4))
        ja, jb = int(math.floor(va + 1e-4)), int(math.ceil(vb - 1e-4))
        sub_t = np.array(tex.crop((ia, ja, max(ib, ia + 1), max(jb, ja + 1))))
        sub_t = np.pad(sub_t, ((1, 1), (1, 1), (0, 0)), mode="edge")
        crop = Image.fromarray(sub_t, "RGBA")
        u0, u1, v0, v1 = u0 - ia + 1, u1 - ia + 1, v0 - ja + 1, v1 - ja + 1
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        local = [(x - bx0, y - by0) for x, y in scr]
        coeffs = _homography(src, local)
        if coeffs is None:
            continue
        patch = np.array(crop.transform((bx1 - bx0, by1 - by0), Image.PERSPECTIVE, coeffs, Image.NEAREST)).astype(float)
        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        ImageDraw.Draw(mask).polygon(local, fill=255)
        m = (np.array(mask) > 0) & (patch[..., 3] > 0)
        # 깊이: 화면에서 평면 (정사영은 z, 원근은 1/z 가 화면 좌표에 대해 1차)
        A = np.array([[scr[i][0], scr[i][1], 1.0] for i in (0, 1, 2)])
        try:
            a, b, c0 = np.linalg.solve(A, q[:3])
        except np.linalg.LinAlgError:
            A = np.array([[scr[i][0], scr[i][1], 1.0] for i in (0, 2, 3)])
            try:
                a, b, c0 = np.linalg.solve(A, q[[0, 2, 3]])
            except np.linalg.LinAlgError:
                continue
        yy, xx = np.mgrid[by0:by1, bx0:bx1]
        depth = a * (xx + 0.5) + b * (yy + 0.5) + c0
        zsub = zbuf[by0:by1, bx0:bx1]
        m &= depth > zsub - 1e-7
        if not m.any():
            continue
        if shade:
            wn = n
            lv = 0.4 + 0.6 * sum(max(0.0, float(np.dot(wn, Ld))) for Ld in lights)
            lv = min(1.0, lv)
        else:
            lv = 1.0
        lv *= max(light, emis / 15.0)
        col = patch[..., :3] * lv
        if tint is not None:
            col = col * (np.array(tint[:3]) / 255.0)
        sub = img[by0:by1, bx0:bx1]
        sub[m, :3] = col[m]
        sub[m, 3] = 255
        zsub[m] = depth[m]
    return Image.fromarray(img.clip(0, 255).astype("uint8"), "RGBA")


# ─────────────────────────── 사람 모형 (바닐라 PlayerModel, 넓은 팔) ───────────────────────────

SKIN = (176, 138, 106, 255)
SHIRT = (78, 88, 96, 255)
SLEEVE = (70, 80, 88, 255)
PANTS = (52, 56, 66, 255)
BOOT = (40, 38, 36, 255)
HAIR = (60, 44, 32, 255)

PI = math.pi


def arm_pose(pose, side):
    """바닐라 HumanoidModel 의 팔 자세 (라디안): (xRot, yRot, zRot). side 'r' / 'l'."""
    sgn = 1 if side == "r" else -1
    if pose == "item":
        return (-PI / 10, 0.0, 0.0)
    if pose == "block":
        return (-0.9424779, -sgn * PI / 6, 0.0)
    if pose == "bow_hold":    # 활을 든 손 (오른손): 머리 방향 앞으로
        return (-PI / 2, -sgn * 0.1, 0.0)
    if pose == "bow_draw":    # 당기는 손 (왼손)
        return (-PI / 2, -sgn * (0.1 + 0.4), 0.0)
    return (0.0, 0.0, 0.0)


def _part(pivot, rot):
    """ModelPart.translateAndRotate: T(pivot/16) · Rz·Ry·Rx (rotationZYX)."""
    xr, yr, zr = rot
    return T(*(np.array(pivot) / 16)) @ R("z", math.degrees(zr)) @ R("y", math.degrees(yr)) @ R("x", math.degrees(xr))


def player_root(body_rot=0.0):
    """LivingEntityRenderer: Ry(180 − 몸 방향) · S(−1, −1, 1) · S(0.9375) · T(0, −1.501, 0). body_rot 180 이면 앞이 −Z."""
    return R("y", 180 - body_rot) @ S(-1, -1, 1) @ S(0.9375) @ T(0, -1.501, 0)


def add_player(scene, root, right="item", left="none"):
    """사람 모형을 그리고 두 팔의 변환 (모형 공간) 을 돌려준다."""
    def box(frm, to, col, M):
        scene.box([v / 16 for v in frm], [v / 16 for v in to], col, root @ M)
    box((-4, -8, -4), (4, 0, 4), SKIN, np.eye(4))
    box((-4.2, -8.2, -4.2), (4.2, -6, 4.2), HAIR, np.eye(4))
    box((-4, 0, -2), (4, 12, 2), SHIRT, np.eye(4))
    arms = {}
    for side, pivot, x0, pose in (("r", (-5, 2, 0), -3, right), ("l", (5, 2, 0), -1, left)):
        Ma = _part(pivot, arm_pose(pose, side))
        box((x0, -2, -2), (x0 + 4, 6, 2), SLEEVE, Ma)
        box((x0, 6, -2), (x0 + 4, 10, 2), SKIN, Ma)
        arms[side] = Ma
    for px in (-1.9, 1.9):
        Ml = _part((px, 12, 0), (0, 0, 0))
        box((-2, 0, -2), (2, 9, 2), PANTS, Ml)
        box((-2, 9, -2), (2, 12, 2), BOOT, Ml)
    return arms


def hand_item_matrix(root, arm, side, disp):
    """ItemInHandLayer: 팔 → Rx(−90)·Ry(180)·T(±1/16, 0.125, −0.625) → 3인칭 자세."""
    k = 1 if side == "r" else -1
    return root @ arm @ R("x", -90) @ R("y", 180) @ T(k / 16, 0.125, -0.625) @ display_matrix(disp, left=(side == "l"))


# ─────────────────────────── 1인칭 ───────────────────────────

def fp_matrix(disp, side="r", use=None, pull=1.0):
    """
    1인칭 손 사슬 (1.21.11 클라이언트 ItemInHandRenderer 바이트코드에서 옮김).
    use: None (평소) | "block" (방패가 아닌 막기 아이템. souls 방패도 껍데기가 부싯돌이라 여기에 든다) | "bow" (당김 pull 0..1)
    """
    k = 1 if side == "r" else -1
    M = T(k * 0.56, -0.52, -0.72)
    if use == "block":
        M = M @ T(k * -0.14142136, 0.08, 0.14142136) @ R("x", -102.25) @ R("y", k * 13.365) @ R("z", k * 78.05)
    elif use == "bow":
        M = M @ T(k * -0.2785682, 0.18344387, 0.15731531) @ R("x", -13.935) @ R("y", k * 35.3) @ R("z", k * -9.785)
        M = M @ T(0, 0, pull * 0.04) @ S(1, 1, 1 + pull * 0.2) @ R("y", -k * 45)
    return M @ display_matrix(disp, left=(side == "l"))


def first_person(items, size=(1280, 720), bg=(44, 42, 40, 255), crosshair=True):
    """items: [(Model, display 한 칸, 'r'|'l', use)]  use: None | "block" | "bow" (fp_matrix)"""
    sc = Scene()
    for model, disp, side, use in items:
        sc.add(model, fp_matrix(disp, side, use))
    img = render(sc, np.eye(4), size=size, ortho=None, fov=70, bg=bg)
    if crosshair:
        d = ImageDraw.Draw(img)
        cx, cy = size[0] // 2, size[1] // 2
        d.line((cx - 9, cy, cx + 9, cy), fill=(220, 220, 220, 255), width=2)
        d.line((cx, cy - 9, cx, cy + 9), fill=(220, 220, 220, 255), width=2)
    return img


# ─────────────────────────── 3인칭 ───────────────────────────

def third_person(items, poses=("item", "none"), views=((-35, 10), (90, 5)), size=(420, 520), zoom=150, bg=BG,
                 close=None):
    """
    items: [(Model, display 한 칸, 'r'|'l')]. poses: (오른팔, 왼팔). views: [(yaw, pitch)] 카메라 (yaw 0 = 사람 앞, 90 = 사람의 오른쪽).
    사람은 −Z 를 본다. 화면 가운데는 허리 높이. close 를 주면 (확대 배율) 첫 아이템의 쥐는 점을 가운데에 두고 그만큼 크게.
    """
    root = player_root(180.0)
    out = []
    for yaw, pitch in views:
        sc = Scene()
        arms = add_player(sc, root, right=poses[0], left=poses[1])
        grip = None
        for model, disp, side in items:
            M = hand_item_matrix(root, arms[side], side, disp)
            sc.add(model, M)
            if grip is None:
                grip = M[:3, 3]
        # 사람 앞 = −Z. yaw 만큼 사람의 오른쪽 (+X 세계) 으로 돈다
        a = math.radians(yaw)
        dist = 6.0
        eye = (math.sin(a) * dist, 1.0 + math.sin(math.radians(pitch)) * dist, -math.cos(a) * dist)
        V = look_at(eye, (0, 1.0, 0))
        if close and grip is not None:
            g = V @ np.append(grip, 1.0)
            out.append(render(sc, V, size=size, ortho=zoom * close, bg=bg, center=(g[0], g[1])))
        else:
            out.append(render(sc, V, size=size, ortho=zoom, bg=bg, center=(0, 0.1)))
    return out


# ─────────────────────────── 모형만, 16px 그림 ───────────────────────────

def side(model, size=(360, 520), bg=BG, views=(("front", 0, 0, 0), ("3/4", -35, 15, 0), ("edge", 90, 0, 0)), zoom=None):
    """3D 모형만 (정사영). views: (이름, yaw, pitch, roll). yaw 0 = 앞면 (+Z) 을 본다."""
    out = []
    for name, yaw, pitch, roll in views:
        sc = Scene().add(model, R("z", roll))
        a = math.radians(yaw)
        eye = (math.sin(a) * 4, math.sin(math.radians(pitch)) * 4, math.cos(a) * 4)
        V = look_at(eye, (0, 0, 0))
        allp = np.concatenate([(V @ np.c_[f[0], np.ones(4)].T).T[:, :2] for f in sc.faces]) if sc.faces else np.zeros((1, 2))
        lo, hi = allp.min(axis=0), allp.max(axis=0)
        span = max((hi[0] - lo[0]) / size[0], (hi[1] - lo[1]) / size[1]) or 1
        z = zoom or 0.86 / span
        out.append(render(sc, V, size=size, ortho=z, bg=bg, center=tuple((lo + hi) / 2)))
    return out


SLOT_BG = (30, 29, 28, 255)       # 이 팩의 칸: 반투명 ash0 판 (gui_skin) 위
SLOT_EDGE = (92, 89, 85, 255)


def gui(icon, bg=BG):
    """16px 그림: 크게 (×16) + 단축 슬롯 (칸 18px, GUI 배율 2·3)."""
    big = icon.resize((256, 256), Image.NEAREST)
    W, H = 256 + 32 + 60 + 16 + 54 + 16, 288
    img = Image.new("RGBA", (W, H), bg)
    img.alpha_composite(Image.new("RGBA", (256, 256), SLOT_BG), (16, 16))
    img.alpha_composite(big, (16, 16))
    x = 16 + 256 + 24
    for s in (2, 3):
        slot = Image.new("RGBA", (18 * s, 18 * s), SLOT_EDGE)
        slot.alpha_composite(Image.new("RGBA", (16 * s, 16 * s), SLOT_BG), (s, s))
        slot.alpha_composite(icon.resize((16 * s, 16 * s), Image.NEAREST), (s, s))
        img.alpha_composite(slot, (x, 16 if s == 2 else 70))
    return img


def _font(sz=14):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/unifont/unifont.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def strip(images, labels=None, pad=8, bg=(20, 19, 18, 255)):
    """그림 여러 장을 가로로 잇는다 (아래에 짧은 영문 이름표)."""
    h = max(i.height for i in images) + (20 if labels else 0)
    w = sum(i.width for i in images) + pad * (len(images) + 1)
    out = Image.new("RGBA", (w, h + pad * 2), bg)
    d = ImageDraw.Draw(out)
    x = pad
    f = _font(14)
    for k, im in enumerate(images):
        out.alpha_composite(im.convert("RGBA"), (x, pad))
        if labels:
            d.text((x + 4, pad + im.height + 3), labels[k], font=f, fill=(210, 205, 195, 255))
        x += im.width + pad
    return out


# ─────────────────────────── 줄 세우기 ───────────────────────────

def lineup(entries, out_png, px_per_block=150, bg=BG, gap=0.62):
    """
    entries: [(id, Model)] 세운 모형 (앞면 +Z) 을 쥐는 점 높이를 맞춰 나란히, 맨 앞에 키 2 블록 (64 복셀) 사람 그림자.
    쥐는 점은 사람의 주먹 높이 (땅에서 0.72 블록 = 바닐라 서 있는 팔 끝 근처) 에 둔다. 이름표는 두 줄로 엇갈린다.
    """
    grip_h = 0.72
    s = px_per_block
    width = int(s * (0.8 + gap * len(entries))) + 60
    H = int(s * 2.9) + 40
    img = Image.new("RGBA", (width, H), bg)
    ground = H - 60
    V = look_at((0, 0, 4), (0, 0, 0))
    d = ImageDraw.Draw(img)
    sx = 30
    d.rectangle((sx + 0.125 * s, ground - 2.0 * s, sx + 0.375 * s, ground - 1.5 * s), fill=(70, 66, 62, 255))
    d.rectangle((sx, ground - 1.5 * s, sx + 0.5 * s, ground - 0.75 * s), fill=(70, 66, 62, 255))
    d.rectangle((sx + 0.03 * s, ground - 0.75 * s, sx + 0.47 * s, ground), fill=(60, 57, 54, 255))
    d.line((0, ground, width, ground), fill=(90, 86, 80, 255), width=1)
    d.line((0, ground - grip_h * s, width, ground - grip_h * s), fill=(58, 55, 52, 255), width=1)
    f = _font(12)
    for i, (wid, model) in enumerate(entries):
        sc = Scene().add(model, T(0, grip_h, 0))
        x0 = sx + int(s * (0.8 + gap * i))
        tile = render(sc, V, size=(int(gap * s), H), ortho=s, bg=(0, 0, 0, 0), center=(0, (H / 2 - (H - ground)) / s))
        img.alpha_composite(tile, (x0, 0))
        d.text((x0 + 2, ground + 6 + (i % 2) * 18), wid, font=f, fill=(200, 195, 185, 255))
    img.save(out_png)
    return out_png
