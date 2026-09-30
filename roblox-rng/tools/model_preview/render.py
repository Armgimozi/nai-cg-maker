import json, sys, math
import numpy as np
from PIL import Image, ImageDraw

S = sys.argv[1]
ids = sys.argv[2].split(",")
data = {d["id"]: d for d in json.load(open(f"{S}/dump.json"))}
W = H = int(sys.argv[3])


def camera(eye, target, fov=38):
    eye = np.array(eye, float)
    target = np.array(target, float)
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    tan = math.tan(math.radians(fov) / 2)
    ys, xs = np.mgrid[0:H, 0:W]
    px = ((xs + 0.5) / W * 2 - 1) * tan
    py = (1 - (ys + 0.5) / H * 2) * tan
    d = f[None, None, :] + px[..., None] * r[None, None, :] + py[..., None] * u[None, None, :]
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    return eye, d.reshape(-1, 3)


def hit_part(part, O, D):
    p = np.array(part["p"])
    m = np.array(part["m"]).reshape(3, 3)
    size = np.array(part["z"])
    o = np.broadcast_to(O - p, D.shape) @ m  # R^T (O - p)
    v = D @ m
    n = len(D)
    INF = np.full(n, np.inf)
    shape = part["s"]
    cls = part["c"]
    hx, hy, hz = size / 2
    normal = np.zeros((n, 3))
    if cls == "WedgePart" or shape == "PartType.Block":
        planes = [
            (np.array([1, 0, 0.0]), hx),
            (np.array([-1, 0, 0.0]), hx),
            (np.array([0, 1, 0.0]), hy),
            (np.array([0, -1, 0.0]), hy),
            (np.array([0, 0, 1.0]), hz),
            (np.array([0, 0, -1.0]), hz),
        ]
        if cls == "WedgePart":
            nn = np.array([0, hz, -hy])
            nn = nn / np.linalg.norm(nn)
            planes.append((nn, 0.0))
        tnear = np.full(n, -np.inf)
        tfar = np.full(n, np.inf)
        miss = np.zeros(n, bool)
        for pn, d in planes:
            denom = v @ pn
            num = d - o @ pn
            with np.errstate(divide="ignore", invalid="ignore"):
                t = num / denom
            enter = denom < -1e-12
            exit_ = denom > 1e-12
            par = ~(enter | exit_)
            miss |= par & (num < 0)
            upd = enter & (t > tnear)
            tnear = np.where(upd, t, tnear)
            normal[upd] = pn
            tfar = np.where(exit_ & (t < tfar), t, tfar)
        ok = (~miss) & (tnear <= tfar) & (tnear > 1e-6)
        tt = np.where(ok, tnear, np.inf)
    elif shape == "PartType.Ball":
        r = size[0] / 2
        b = np.einsum("ij,ij->i", o, v)
        c = np.einsum("ij,ij->i", o, o) - r * r
        disc = b * b - c
        ok = disc >= 0
        t = -b - np.sqrt(np.where(ok, disc, 0))
        ok &= t > 1e-6
        tt = np.where(ok, t, np.inf)
        hitp = o + v * np.where(ok, t, 0)[:, None]
        normal = hitp / r
    else:  # cylinder along X
        r = min(size[1], size[2]) / 2
        a = v[:, 1] ** 2 + v[:, 2] ** 2
        b = 2 * (o[:, 1] * v[:, 1] + o[:, 2] * v[:, 2])
        c = o[:, 1] ** 2 + o[:, 2] ** 2 - r * r
        disc = b * b - 4 * a * c
        ok = (disc >= 0) & (a > 1e-12)
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (-b - np.sqrt(np.where(ok, disc, 0))) / (2 * a)
        x1 = o[:, 0] + v[:, 0] * t1
        side = ok & (t1 > 1e-6) & (np.abs(x1) <= hx)
        tt = np.where(side, t1, np.inf)
        hp = o + v * np.where(side, t1, 0)[:, None]
        normal = np.stack([np.zeros(n), hp[:, 1], hp[:, 2]], -1) / r
        for sgn in (1, -1):
            with np.errstate(divide="ignore", invalid="ignore"):
                tc = (sgn * hx - o[:, 0]) / v[:, 0]
            yc = o[:, 1] + v[:, 1] * tc
            zc = o[:, 2] + v[:, 2] * tc
            okc = (tc > 1e-6) & (yc * yc + zc * zc <= r * r) & (tc < tt)
            tt = np.where(okc, tc, tt)
            normal[okc] = [sgn, 0, 0]
    wn = normal @ m.T
    return tt, wn


LIGHT = np.array([-0.45, 0.8, -0.4])
LIGHT /= np.linalg.norm(LIGHT)


def render(model, eye, target):
    O, D = camera(eye, target)
    n = len(D)
    # floor at y = 0
    with np.errstate(divide="ignore", invalid="ignore"):
        tf = -O[1] / D[:, 1]
    floor_ok = (tf > 0) & np.isfinite(tf)
    fp = O + D * np.where(floor_ok, tf, 0)[:, None]
    checker = ((np.floor(fp[:, 0] / 2) + np.floor(fp[:, 2] / 2)) % 2).astype(float)
    inside = (np.abs(fp[:, 0]) <= 5) & (np.abs(fp[:, 2]) <= 5)
    floor_col = np.where(inside[:, None], [0.78, 0.8, 0.84], [0.9, 0.92, 0.95]) - 0.04 * checker[:, None]
    sky = np.array([0.97, 0.98, 1.0])
    color = np.where(floor_ok[:, None], floor_col, sky)
    depth = np.where(floor_ok, tf, np.inf)
    trans = []
    for part in model["parts"]:
        t, wn = hit_part(part, O, D)
        col = np.array(part["col"])
        mat = part["mat"]
        if mat == "Material.Neon":
            shade = np.clip(col * 1.15 + 0.1, 0, 1)[None, :].repeat(n, 0)
        else:
            lam = np.clip(wn @ LIGHT, 0, 1)
            # two-sided for thin parts
            shade = col[None, :] * (0.38 + 0.62 * lam[:, None])
            if mat == "Material.Glass":
                shade = shade * 0.85 + 0.15
        if part["t"] >= 0.02:
            trans.append((t, shade, part["t"]))
            continue
        closer = t < depth
        depth = np.where(closer, t, depth)
        color = np.where(closer[:, None], shade, color)
    # transparent: blend back-to-front per pixel (approx: sort by mean depth)
    trans.sort(key=lambda x: -np.nanmean(np.where(np.isfinite(x[0]), x[0], np.nan)) if np.isfinite(x[0]).any() else 0)
    for t, shade, tr in trans:
        vis = t < depth
        a = 1 - tr
        color = np.where(vis[:, None], color * (1 - a) + shade * a, color)
    img = (np.clip(color, 0, 1).reshape(H, W, 3) * 255).astype(np.uint8)
    return Image.fromarray(img)



views = [((-19, 20, -31), (0, 9, 0)), ((23, 11, -21), (0, 8.5, 0)), ((0.01, 40, -0.01), (0, 0, 0)), ((0, 8, -30), (0, 8, 0))]
sheet = Image.new("RGB", (4 * W, len(ids) * (H + 16)), "white")
draw = ImageDraw.Draw(sheet)
for i, mid in enumerate(ids):
    model = data[mid]
    top = 0
    for part in model["parts"]:
        top = max(top, part["p"][1] + max(part["z"]) / 2)
    scale = max(top, 13.5) / 21
    for k, (eye, target) in enumerate(views):
        if k == 2:
            e, t = (0, 16.5, -0.01), (0, 0, 0)
        else:
            ty = target[1] * scale
            e = (eye[0] * scale, ty + (eye[1] - target[1]) * scale, eye[2] * scale)
            t = (0, ty, 0)
        sheet.paste(render(model, e, t), (k * W, i * (H + 16) + 16))
    draw.text((4, i * (H + 16) + 2), f"{mid} ({model['shape']}) {len(model['parts'])}p", fill="black")
out = sys.argv[4]
sheet.save(out)
print(out, sheet.size)
