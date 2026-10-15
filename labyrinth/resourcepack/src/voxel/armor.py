"""Original voxel armour: helmets worn on the head, chest/legs/boots icons, shields.

Helmets: 1 voxel = 0.8 model units, voxel 0..15 = the wearer's head (model 1.6..14.4); the face is
toward −Z (north).  Icons and shields: 1 voxel = 0.5 units centred on (8, 8, 8); shields face +Z.

투구 껍데기 규칙 (머리·모자 층과 겹치지 않게):
  · 스킨의 모자(2번째) 층은 머리보다 0.5px(= 1 voxel) 바깥 — voxel −1 / 16 고리와 j = −1 / 16 이 그 자리다.
    이 고리에 투구 voxel 이 있으면 바깥면이 모자 층과 같은 평면이 되어 z-fighting (머리카락이 투구 위로 비침).
  · 그래서 투구 함수는 예전처럼 "몸에 붙는" 좌표(껍데기 −1/16, 정수리 16)로 그리고, 끝에서 `_inflate` 가
    머리 바깥의 모든 voxel 을 한 칸 밖으로 민다 → 껍데기는 −2/17 (머리에서 1px, 바닐라 투구와 같은 크기),
    장식은 그만큼 같이 밀린다.  머리 상자 [0, 15]³ 안에는 voxel 을 두지 않는다.
  · `finish_helmet` 이 껍데기 바로 안쪽(모자 층 자리, −1/16)에 안감을 한 겹 댄다 (`_line`): 모자 층의 옆·뒤·윗면이
    투구 속에 완전히 묻혀, 얼굴 구멍·목 쪽에서 들여다봐도 모자 층과 같은 평면에 놓인 투구 면이 없다 (`_seal`).
  · 옆·뒤 벽은 머리 아랫단 1px 아래(j −2)까지 내려 머리를 감싼다 (`_wrap_down`); 얼굴 쪽만 투구 종류에 맞게 연다.
    왕관만 디자인상 띠로 열어 둔다.
"""
from __future__ import annotations

import math

from .core import Grid, bezier, catmull, helix
from . import weapons as W


def _copy(dst: Grid, src: Grid, fn):
    for key, v in src.vox.items():
        q = fn(*key)
        dst.put(q[0], q[1], q[2], v[0], v[1], v[2], v[3])


HEAD_LO, HEAD_HI = -1, 16          # head (0..15) + the skin's hat layer (−1 / 16): no helmet voxel may sit here


def _out(c):
    """Snug → final coordinate(s) along one axis: everything outside the head moves one voxel out;
    the old shell plane (−1 / 16) is doubled so walls and bands stay closed after the move."""
    if c < HEAD_LO:
        return (c - 1,)
    if c == HEAD_LO:
        return (c - 1, c)
    if c > HEAD_HI:
        return (c + 1,)
    if c == HEAD_HI:
        return (c + 1, c)
    return (c,)


def _inside(i, j, k):
    return HEAD_LO <= i <= HEAD_HI and HEAD_LO <= j <= HEAD_HI and HEAD_LO <= k <= HEAD_HI


def _inflate(g: Grid):
    """Lift the whole helmet off the head and the hat layer (see module docstring)."""
    old = sorted(g.vox.items(), key=lambda kv: kv[1][3])            # low prio first → higher prio wins
    g.vox = {}
    for (i, j, k), (mat, val, glow, prio) in old:
        for i2 in _out(i):
            for j2 in _out(j):
                for k2 in _out(k):
                    if not _inside(i2, j2, k2):
                        g.put(i2, j2, k2, mat, val, glow, prio)


def _in_head(i, j, k):
    return 0 <= i <= 15 and 0 <= j <= 15 and 0 <= k <= 15


def _line(g: Grid):
    """Inner lining: one voxel behind every shell voxel that borders the hat layer (darker — it is the
    inside of the shell, seen only at the face opening / lower edge as the shell's thickness)."""
    from collections import Counter
    shell = Counter(v[0] for (i, j, k), v in g.vox.items() if (i in (-2, 17) or k in (-2, 17) or j == 17)
                    and v[0] not in ('glow', 'gem', 'crystal', 'eye'))
    lining = shell.most_common(1)[0][0] if shell else 'cloth'
    if lining not in ('cloth', 'dark'):
        lining = 'cloth'               # padded lining: flat cloth (no sheen / wrap bands) → few elements
    adds = {}
    for (i, j, k), (mat, val, glow, prio) in g.vox.items():
        inner = []
        if i in (-2, 17) and -1 <= j <= 16 and -1 <= k <= 16:
            inner.append((i + (1 if i < 0 else -1), j, k))
        if k in (-2, 17) and -1 <= i <= 16 and -1 <= j <= 16:
            inner.append((i, j, k + (1 if k < 0 else -1)))
        if j in (-2, 17) and -1 <= i <= 16 and -1 <= k <= 16:
            inner.append((i, j + (1 if j < 0 else -1), k))
        for q in inner:
            if q not in g.vox and not _in_head(*q):
                adds.setdefault(q, (lining, 0.26))
    for q, (m, v) in adds.items():
        g.put(q[0], q[1], q[2], m, v, False, 0)


def _seal(g: Grid):
    """No exposed face may lie on the hat layer's surface facing the same way (it would z-fight with the
    skin's hat layer): give every hat-layer voxel an outer neighbour where it has none."""
    for _ in range(2):
        adds = {}
        for (i, j, k), (mat, val, glow, prio) in g.vox.items():
            if not _inside(i, j, k) or _in_head(i, j, k):
                continue
            for a, c in enumerate((i, j, k)):
                if c in (HEAD_LO, HEAD_HI):
                    q = [i, j, k]
                    q[a] = c - 1 if c == HEAD_LO else c + 1
                    q = tuple(q)
                    if q not in g.vox:
                        adds.setdefault(q, (mat, val))
        if not adds:
            break
        for q, (m, v) in adds.items():
            g.put(q[0], q[1], q[2], m, v, False, 0)


def _ring2(front=False):
    """(i, k) columns of the final shell ring: sides (i = −2 / 17) and back (k = 17) [+ front (k = −2)]."""
    cols = set()
    for t in range(-2, 18):
        cols.update(((-2, t), (17, t), (t, 17)))
        if front:
            cols.add((t, -2))
    return cols


def _wrap_down(g: Grid, front=False, j_to=-2):
    """Carry every side/back wall column of the final shell down to the hat layer's lower edge, so the
    skin's head and hat layer are wrapped (only the face side stays as the helmet type opens it)."""
    for (i, k) in _ring2(front):
        js = [j for j in range(j_to, 18) if (i, j, k) in g.vox]
        if not js or js[0] <= j_to:
            continue
        mat, val, glow, prio = g.vox[(i, js[0], k)]
        for j in range(js[0] - 1, j_to - 1, -1):
            g.put(i, j, k, mat, max(0.2, val - 0.04), glow and mat == 'glow', min(prio, 1))


def _cowl(g: Grid, mat='cloth', j0=-2, j1=16, open_i=(1, 14), open_top=14, val=0.42):
    """Final-coordinate cowl under brimmed hats: closed sides, back and crown, open face."""
    for j in range(j0, j1 + 1):
        for (i, k) in _ring2(front=True):
            if k == -2 and open_i[0] <= i <= open_i[1] and j <= open_top:
                continue
            g.put(i, j, k, mat, val + 0.16 * (j - j0) / (j1 - j0 + 1), prio=0)
    for i in range(-2, 18):
        for k in range(-2, 18):
            g.put(i, 17, k, mat, val + 0.2, prio=0)


def _shell(g: Grid, y0, y1, face_open=None, mat='plate', dome=True, ridge=False):
    """Helmet shell around the 16³ head; face_open(i, j) → True leaves the front voxel empty."""
    for j in range(y0, y1 + 1):
        for i in range(-1, 17):
            for k in range(-1, 17):
                edge = i in (-1, 16) or k in (-1, 16)
                if not edge:
                    continue
                if k == -1 and face_open and face_open(i, j):
                    continue
                v = 0.45 + 0.2 * (j - y0) / max(1, y1 - y0) + (0.08 if j == y1 else 0)
                g.put(i, j, k, mat, v)
    if dome:
        for i in range(-1, 17):
            for k in range(-1, 17):
                g.put(i, 16, k, mat, 0.7)
                if 1 <= i <= 14 and 1 <= k <= 14:
                    g.put(i, 17, k, mat, 0.78)
                if 4 <= i <= 11 and 4 <= k <= 11:
                    g.put(i, 18, k, mat, 0.85)
    if ridge:
        for k in range(-1, 17):
            for j in range(17, 20 - (1 if k > 12 or k < 1 else 0)):
                g.put(7, j, k, 'orn', 0.7, prio=2)
                g.put(8, j, k, 'orn', 0.6, prio=2)


def _coif(g, p, mat='cloth', y0=3, open_top=13, prio=0):
    """Fitted cowl under masks/circlets so the head is fully dressed (reference look: no bare scalp)."""
    for j in range(y0, 17):
        for i in range(-1, 17):
            for k in range(-1, 17):
                wall = i in (-1, 16) or k in (-1, 16)
                if not wall and j < 16:
                    continue
                if k == -1 and 1 <= i <= 14 and j < open_top:
                    continue                                   # face opening
                fold = 0.07 if (i * 3 + j * 2 + k) % 7 == 0 else 0
                g.put(i, j, k, mat, 0.38 + 0.22 * (j - y0) / (17 - y0) + fold, prio=prio)
    for i in range(1, 15):
        for k in range(1, 15):
            if (i - 7.5) ** 2 + (k - 7.5) ** 2 < 36:
                g.put(i, 17, k, mat, 0.62, prio=prio)


def finish_helmet(g, p):
    """Shared pass-2 finish (after each helmet's `_inflate`): bevel the boxy shell corners so silhouettes
    read rounder (decorations with prio ≥ 2 are kept), and give upper-tier helmets a glowing brow seam."""
    for (i, j, k) in [q for q in g.vox if _inside(*q)]:
        g.erase(i, j, k)                                            # safety: nothing on the head / hat layer yet
    for (i, j, k), v in list(g.vox.items()):
        if v[3] > 1:
            continue
        corner_v = i in (-2, 17) and k in (-2, 17)
        top_edge = j >= 17 and (i in (-2, 17) or k in (-2, 17))
        if corner_v or top_edge:
            g.erase(i, j, k)
    flare = {}
    for (i, j, k), v in list(g.vox.items()):
        # 볼 가리개: 옆 벽 아랫단(목 높이 23~25px)은 흉갑 몸통 상자의 옆면(x = ±5px)과 같은 평면이라 팔을 흔들면
        # z-fighting 이 난다 → 그 줄은 반 칸 바깥(−3/18)으로 벌려 볼 가리개처럼 두르고, 흉갑 윗면(25px)보다
        # 반 칸 높은 곳에서 벽과 이어 붙인다.
        if i in (-2, 17) and j <= 1 and v[3] <= 1:
            out = -3 if i < 0 else 18
            for jj in ((j, 2) if j == 1 else (j,)):
                src = v if jj == j else g.vox.get((i, 2, k), v)
                flare[(out, jj, k)] = (src[0], src[1])
            if 2 <= k <= 13:
                g.erase(i, j, k)
    for (i, j, k), (mat, val) in flare.items():
        g.put(i, j, k, mat, val, False, 1)
    if p.lv >= 4:
        for i in range(0, 16):
            key = (i, 13, -2)
            if key in g.vox and g.vox[key][3] <= 1:
                g.put(i, 13, -3, 'glow', 0.75 + (0.15 if i % 3 == 0 else 0), glow=True, prio=2)
    _line(g)
    _seal(g)


def _rim(g, y, mat='orn', lo=-2, hi=17):
    for i in range(lo, hi + 1):
        for k in range(lo, hi + 1):
            if i in (lo, hi) or k in (lo, hi):
                g.put(i, y, k, mat, 0.65 + (0.12 if (i + k) % 4 == 0 else 0), prio=2)


def _brow_gem(g, p, y=12):
    if p.lv >= 2:
        g.gem((7.5, y, -2), 1.3 if p.lv >= 3 else 1.0, 'gem', glow=p.glow)


def _side_wings(g, p, y=12, span=8, rise=9):
    for s in (-1, 1):
        t = Grid(g.seed)
        W.wing(t, (0, 0, 0), 1, p, span=span, rise=rise, n=5)
        x0 = 17 if s > 0 else -2
        _copy(g, t, lambda i, j, k, s=s, x0=x0: (x0 + s * (k + 0), y + j, 6 + i))


def helm_knight(g, p):
    _shell(g, 1, 15, face_open=lambda i, j: (j in (8, 9) and 1 <= i <= 14) or (j in (3, 5) and i in (4, 5, 10, 11)),
           ridge=p.lv >= 1)
    for i in range(1, 15):
        for j in (8, 9):
            g.put(i, j, -1, 'glow' if p.glow else 'dark', 0.7, glow=p.glow)   # visor slit (flush, lifted with the shell)
    for i in (4, 5, 10, 11):
        for j in (3, 5):
            g.put(i, j, -1, 'dark', 0.5)                                       # breathing holes
    for j in range(1, 8):
        g.put(7, j, -2, 'metal', 0.65, prio=2)
        g.put(8, j, -2, 'metal', 0.55, prio=2)
    _rim(g, 0, 'metal')
    _rim(g, 10, 'orn' if p.lv >= 1 else 'metal')
    _brow_gem(g, p)
    if p.lv >= 2:
        pts = bezier((7.5, 19, 2), (7.5, 24, 6), (7.5, 23, 14), (7.5, 16, 20), 20)
        g.tube(pts, 1.6, 0.8, 'feather' if p.theme != 'clock' else 'orn', sq=(0.6, 1, 1),
               vfn=lambda t, d, q: 0.4 + 0.4 * (1 - d) + 0.1 * math.sin(t * 30), prio=3)
    if p.theme == 'clock':
        for s, x in ((-1, -2), (1, 17)):
            W.gear(g, (x, 8, 7), 3.6, p, 8, 'xy', 'orn') if False else None
            t = Grid(g.seed)
            W.gear(t, (0, 0, 0), 3.6, p, 8, 'xy', 'orn')
            _copy(g, t, lambda i, j, k, x=x, s=s: (x + s * k, 9 + j, 8 + i))
    if p.lv >= 4:
        _side_wings(g, p, 11, 7, 8)
    _inflate(g)
    _wrap_down(g, front=True)                                                   # closed helm: chin too


def helm_horned(g, p):
    _shell(g, 2, 15, face_open=lambda i, j: 3 <= i <= 12 and 2 <= j <= 10 and not (i in (7, 8) and j >= 4))
    for j in range(4, 11):
        g.put(7, j, -2, 'metal', 0.6, prio=2)
        g.put(8, j, -2, 'metal', 0.5, prio=2)
    _rim(g, 11, 'metal')
    for s in (-1, 1):
        x = 17 if s > 0 else -2
        pts = catmull([(x, 12, 7), (x + s * 4, 14, 6), (x + s * 7, 19, 5), (x + s * 6, 25, 3), (x + s * 3.5, 28, 2)], 6)
        g.tube(pts, 2.4, 0.6, 'bone', vfn=lambda t, d, q: 0.3 + 0.5 * t + (0.1 if int(t * 14) % 2 else 0), prio=3)
    if p.theme == 'forge':
        for i in range(0, 16, 3):
            g.put(i, 6, -1, 'glow', 0.8, glow=True, prio=3)
        for k in range(1, 15, 3):
            g.put(-1, 7 + k % 3, k, 'glow', 0.8, glow=True, prio=3)
            g.put(16, 7 + k % 3, k, 'glow', 0.8, glow=True, prio=3)
    if p.lv >= 3:
        for k in range(3):
            g.crystal((7.5, 18, 3 + k * 4), (0, 1, 0.3), 3.0 - k * 0.5, 0.9, 'metal', prio=2)
    _brow_gem(g, p, 13)
    _inflate(g)
    _wrap_down(g)


def helm_winged(g, p):
    _shell(g, 3, 15, face_open=lambda i, j: 3 <= i <= 12 and 3 <= j <= 10 and not (i in (7, 8) and j >= 5))
    _rim(g, 11, 'orn')
    for j in range(5, 11):
        g.put(7, j, -2, 'metal', 0.6, prio=2)
        g.put(8, j, -2, 'metal', 0.5, prio=2)
    _side_wings(g, p, 11, 9, 11)
    if p.theme == 'crystal':
        for k, x in enumerate((3, 7.5, 12)):
            g.crystal((x, 18, 4 + k % 2 * 3), (0, 1, 0.2), 4.5 if x == 7.5 else 3.2, 1.1, 'crystal', glow=p.glow, prio=3)
    _brow_gem(g, p, 13)
    if p.lv >= 4:
        W.halo(g, (7.5, 23, 8), 7.0, 'y')
    _inflate(g)
    _wrap_down(g)


def hood(g, p):
    for j in range(0, 18):
        for i in range(-2, 18):
            for k in range(-2, 18):
                if not (i in (-1, 16) or k in (-1, 16) or j == 16 or j == 17):
                    continue
                if j >= 17 and not (0 <= i <= 15 and 0 <= k <= 15):
                    continue
                if i < -1 or i > 16 or k < -1 or k > 16:
                    continue
                if k == -1 and 1 <= i <= 14 and j <= 14:
                    continue
                fold = 0.08 if (i + j) % 5 == 0 else 0
                g.put(i, j, k, 'cloth', 0.42 + 0.2 * j / 17 + fold)
    # pointed peak falling back + drape
    pts = bezier((7.5, 17, 6), (7.5, 21, 10), (7.5, 20, 16), (7.5, 15, 20), 16)
    g.tube(pts, 3.0, 0.8, 'cloth', vfn=lambda t, d, q: 0.45 + 0.25 * (1 - d))
    for i in range(-1, 17):
        g.put(i, 15, -2, 'orn' if p.lv >= 2 else 'cloth', 0.7, prio=2)
    if p.lv >= 3:
        for j in range(0, 15, 2):
            g.put(-1, j, -2, 'orn', 0.7, prio=2)
            g.put(16, j, -2, 'orn', 0.7, prio=2)
    if p.theme == 'abyss' and p.lv >= 4:
        for x in (5, 10):
            g.put(x, 12, -1, 'eye', 0.9, glow=True, prio=4)
        W.tendrils(g, (7.5, 2, 17), p, n=3, length=5, spread=4, up=-1.0)
    if p.theme in ('vine', 'fungi') and p.lv >= 2:
        for k, (x, z) in enumerate(((-2, 3), (17, 6), (-2, 11))):
            g.ball((x, 13 - k * 3, z), 1.3, 'leaf', sq=(0.7, 0.8, 1.3), vfn=lambda i, j, kk, d: 0.4 + 0.4 * (1 - d), prio=2)
    _brow_gem(g, p, 15)
    _inflate(g)
    _wrap_down(g)


def wizard_hat(g, p):
    # brim
    for i in range(-6, 22):
        for k in range(-6, 22):
            d = math.hypot(i - 7.5, k - 7.5)
            if d <= 13.5 and not (0 <= i <= 15 and 0 <= k <= 15 and d < 8.5):
                g.put(i, 15, k, 'cloth', 0.45 + 0.15 * (d > 12.5))
                if d > 12.7:
                    g.put(i, 16, k, 'cloth', 0.55)
    # cone bending back
    pts = []
    for s in range(0, 21):
        t = s / 20
        pts.append((7.5, 16 + t * 17, 7.5 + 7 * t * t))
    g.tube(pts, 8.6, 1.0, 'cloth', vfn=lambda t, d, q: 0.42 + 0.22 * (1 - d) + 0.08 * math.sin(q[1] * 0.9), step=0.4)
    for i in range(-2, 18):
        for k in range(-2, 18):
            d = math.hypot(i - 7.5, k - 7.5)
            if 7.6 <= d <= 9.0:
                g.put(i, 17, k, 'orn', 0.7, prio=2)
    g.gem((7.5, 17.5, -1.5), 1.3, 'gem', glow=p.glow)
    if p.theme == 'fungi':
        for (x, z) in ((-3, 4), (18, 10), (5, 20)):
            W.fungi(g, (x, 15, z), p, 2.0)
    if p.lv >= 4:
        for k in range(6):
            t = 0.25 + k * 0.12
            q = pts[int(t * 20)]
            a = k * 2.1
            g.put(round(q[0] + math.cos(a) * (8.6 - 7 * t)), round(q[1]), round(q[2] + math.sin(a) * (8.6 - 7 * t)),
                  'glow', 0.9, glow=True, prio=4)
        W.float_shards(g, [(-4, 24, 4), (19, 27, 8)], p, 2.6, 0.8, 'glow')
    _inflate(g)
    _cowl(g, 'cloth', val=0.5)                                                  # 챙 아래 두건: 옆·뒤를 감쌈


def circlet(g, p):
    _coif(g, p, 'cloth', y0=2, open_top=12)
    for i in range(-1, 17):
        for k in range(-1, 17):
            if i in (-1, 16) or k in (-1, 16):
                g.put(i, 11, k, 'orn', 0.62 + (0.15 if (i + k) % 3 == 0 else 0))
                g.put(i, 12, k, 'orn', 0.5)
    g.gem((7.5, 12.5, -2), 1.6, 'gem', glow=True)
    for s in (-1, 1):
        pts = bezier((7.5 + s * 2, 12, -1.5), (7.5 + s * 5, 14, -1.5), (7.5 + s * 7, 15, -1), (7.5 + s * 8, 17, 0), 10)
        g.tube(pts, 0.7, 0.5, 'orn', 0.7, prio=2)
    if p.theme == 'ink':
        for s in (-1, 1):
            q = bezier((7.5 + s * 9, 12, 4), (7.5 + s * 11, 15, 7), (7.5 + s * 11, 19, 10), (7.5 + s * 10, 22, 13), 12)
            g.tube(q, 1.1, 0.5, 'feather', vfn=lambda t, d, q_: 0.5 + 0.35 * t, prio=3)
    _inflate(g)
    _wrap_down(g)


def crown(g, p):
    for j in range(13, 17):
        for i in range(-1, 17):
            for k in range(-1, 17):
                if i in (-1, 16) or k in (-1, 16):
                    g.put(i, j, k, 'orn', 0.5 + 0.1 * (j - 13) + (0.1 if (i + k + j) % 4 == 0 else 0))
    mat = 'ice' if p.theme == 'frost' else 'crystal' if p.lv >= 4 else 'orn'
    pts = [(i, k) for i in range(-1, 17, 4) for k in (-1, 16)] + [(i, k) for k in range(3, 15, 4) for i in (-1, 16)]
    for n, (i, k) in enumerate(pts):
        h = 5.0 if (i in (7, 8) or n % 2 == 0) else 3.5
        if p.lv >= 5:
            h *= 1.6
        g.crystal((i, 16.5, k), (0, 1, 0), h, 1.0, mat, glow=p.glow and n % 2 == 0, prio=2)
    for i in range(1, 16, 5):
        g.gem((i, 14.5, -2), 0.9, 'gem', glow=p.glow)
    g.gem((7.5, 15, -2), 1.4, 'gem', glow=True)
    if p.lv >= 5:
        W.halo(g, (7.5, 26, 7.5), 6.0, 'y')
        W.tendrils(g, (7.5, 14, 17), p, n=3, length=4, spread=5, up=-0.6)
    _inflate(g)                                                                 # 띠만 두르는 디자인 (모자 층과는 떨어짐)


def half_mask(g, p):
    _coif(g, p, 'plate' if p.theme in ('frost', 'crystal') else 'cloth', y0=6, open_top=13)
    for i in range(-1, 17):                                      # brow band
        g.put(i, 13, -1, 'orn', 0.66 + (0.12 if i % 4 == 0 else 0), prio=2)
    g.gem((7.5, 13.5, -2), 1.1, 'gem', glow=p.glow)
    for j in range(0, 9):
        for i in range(-1, 17):
            w = 0.5 + 0.15 * (1 - abs(i - 7.5) / 9)
            g.put(i, j, -1, 'plate', w + (0.1 if j == 8 else 0))
            if j == 8:
                g.put(i, j, -2, 'orn', 0.7, prio=2)
    for k in range(0, 16):
        g.put(-1, 7, k, 'leather', 0.45)
        g.put(16, 7, k, 'leather', 0.45)
    for i in range(-1, 17):
        g.put(i, 7, 16, 'leather', 0.45)
    # fangs / motif
    if p.theme == 'frost' or 'rime' in p.iid:
        for i in (3, 5, 10, 12):
            g.crystal((i, 1, -1.5), (0, -1, -0.2), 3.0, 0.8, 'ice', glow=p.glow, prio=3)
    elif p.theme == 'crystal':
        for s in (-1, 1):
            g.crystal((7.5 + s * 6, 6, -2), (s, 0.8, -0.3), 4.0, 0.9, 'crystal', glow=p.glow, prio=3)
    elif p.theme == 'ink':
        W.drips(g, [(3, 0, -2), (7, 0, -2), (12, 0, -2)], p)
    for i in range(4, 12, 2):
        g.put(i, 3, -2, 'dark', 0.4, prio=2)
    if p.lv >= 4:
        for x in (4, 11):
            g.put(x, 10, -2, 'glow', 0.9, glow=True, prio=3)
    _inflate(g)
    _wrap_down(g)


HELMETS = {'helm_knight': helm_knight, 'helm_horned': helm_horned, 'helm_winged': helm_winged, 'hood': hood,
           'wizard_hat': wizard_hat, 'circlet': circlet, 'crown': crown, 'half_mask': half_mask}


# ───────────────────────────── body icons (vs 0.5, centre 8,8,8) ─────────────────────────────

def _torso(g, mat, w=8, h=11, flare=0, y0=-9):
    def m(u, v):
        t = (v - y0) / h
        if t < 0 or t > 1:
            return False
        hw = w - 2 + 2 * t + flare * (1 - t) ** 2
        if t > 0.92:
            hw -= 3
        return abs(u) <= hw
    g.slab(m, (-16, y0), (16, y0 + h * 2 + 2), 'xy', 0, max_half=3, slope=0.8, base_half=0, mat=mat,
           vfn=lambda u, v, w_, d: 0.42 + 0.1 * min(d, 3) + 0.05 * (w_ > 0))


def chestplate(g, p):
    _torso(g, 'plate', 8, 22)
    for s in (-1, 1):
        g.ball((s * 9, 12, 0), 4.6, 'plate', sq=(1.2, 0.8, 1.0), vfn=lambda i, j, k, d: 0.4 + 0.35 * (1 - d) + 0.1 * (j > 12))
        g.torus((s * 9, 9, 0), 4.6, 0.6, 'y', 'orn' if p.lv >= 1 else 'metal', 0.7)
    for u in range(-6, 7):
        for v in (3, 4):
            g.put(u, v, 4, 'plate', 0.62, prio=2)
    g.box((-9, -9, -4), (9, -7, 4), 'leather', 0.45, prio=2)
    g.box((-1, -10, 4), (1, -6, 5), 'orn', 0.7, prio=3)
    if p.lv >= 1:
        g.box((0, -5, 4), (0, 10, 4), 'orn', 0.7, prio=3)
    if p.lv >= 2:
        g.gem((0, 5, 4.5), 1.6, 'gem', glow=p.glow)
    if p.theme == 'clock':
        W.gear(g, (0, 2, 5), 3.4, p, 8, 'xy', 'orn')
    if p.theme == 'crystal':
        for s in (-1, 1):
            g.crystal((s * 9, 15, 0), (s * 0.4, 1, 0), 4.5, 1.1, 'crystal', glow=p.glow, prio=3)
    if p.theme == 'forge':
        for s in (-1, 1):
            g.crystal((s * 10, 14, 0), (s, 0.8, 0), 4.0, 1.0, 'metal', prio=3)


def robe_top(g, p):
    _torso(g, 'cloth', 7, 24, flare=5, y0=-12)
    for s in (-1, 1):
        pts = [(s * 7, 10, 0), (s * 10, 4, 0), (s * 12, -3, 0)]
        g.tube(pts, 2.5, 3.4, 'cloth', vfn=lambda t, d, q: 0.45 + 0.2 * (1 - d))
        g.torus((s * 12, -4, 0), 3.2, 0.6, 'y', 'orn', 0.7)
    for v in range(-12, 12):
        g.put(0, v, 4, 'orn', 0.7, prio=2)
    for u in range(-12, 13):
        g.put(u, -12, 3, 'orn', 0.65, prio=2)
    g.box((-7, -1, -4), (7, 0, 4), 'leather', 0.45, prio=2)
    if p.lv >= 2:
        g.gem((0, 0, 4.5), 1.4, 'gem', glow=p.glow)
    if p.lv >= 4:
        for v in range(-10, 10, 4):
            g.put(-3, v, 4, 'glow', 0.9, glow=True, prio=3)
            g.put(3, v + 2, 4, 'glow', 0.9, glow=True, prio=3)


def leather_vest(g, p):
    _torso(g, 'leather', 8, 21)
    g.torus((0, 11, 0), 6.0, 1.6, 'y', 'cloth', vfn=lambda t, d, q: 0.5 + 0.3 * (1 - d) + 0.1 * math.sin(t * 50))
    for s in (-1, 1):
        g.ball((s * 8.5, 10, 0), 3.0, 'leather', vfn=lambda i, j, k, d: 0.4 + 0.3 * (1 - d))
    for k in range(-8, 10):
        g.put(k // 1 if abs(k) < 9 else 0, -k // 1 + 1, 4, 'metal', 0.6, prio=2)
    g.box((-9, -9, -4), (9, -8, 4), 'metal', 0.5, prio=2)
    g.box((4, -7, 4), (7, -4, 5), 'leather', 0.55, prio=3)
    if p.lv >= 3:
        g.gem((0, 8, 4.5), 1.2, 'gem', glow=p.glow)
    if p.theme == 'abyss' and p.lv >= 4:
        W.tendrils(g, (0, -9, 0), p, n=3, length=4, spread=4, up=-1.0)


def leggings(g, p):
    g.box((-8, 8, -3), (8, 10, 3), 'leather', 0.45)
    g.box((-1, 7, 3), (1, 11, 4), 'orn' if p.lv >= 1 else 'metal', 0.7, prio=2)
    for s in (-1, 1):
        def m(u, v, s=s):
            x = u * s
            return 1 <= x <= 8 - (10 - v) * 0.08 and -14 <= v <= 8
        g.slab(m, (-9, -15), (9, 9), 'xy', 0, max_half=2, slope=0.7, mat='plate', base_half=1,
               vfn=lambda u, v, w, d: 0.42 + 0.08 * min(d, 3))
        g.ball((s * 4.5, -3, 3), 2.4, 'metal', sq=(1, 1, 0.6), vfn=lambda i, j, k, d: 0.45 + 0.35 * (1 - d), prio=2)
        if p.lv >= 2:
            for v in range(-12, 7, 3):
                g.put(s * 8, v, 2, 'orn', 0.7, prio=2)
        if p.lv >= 3:
            g.gem((s * 4.5, -3, 4.5), 0.9, 'gem', glow=p.glow)


def boots(g, p):
    for s in (-1, 1):
        x = s * 5
        def m(u, v, x=x):
            # side view silhouette (z, y): shaft + foot pointing −z... built in zy plane
            return (-3 <= u <= 3 and -6 <= v <= 8) or (-9 <= u <= 3 and -10 <= v <= -5)
        g.slab(m, (-10, -11), (4, 9), 'zy', x, max_half=2, slope=0.8, base_half=1, mat='plate',
               vfn=lambda u, v, w, d: ('dark', 0.3) if v == -10 else 0.42 + 0.08 * min(d, 3))
        for zz in range(-4, 5):
            for ww in range(-3, 4):
                g.put(x + ww, 8, zz, 'orn' if p.lv >= 1 else 'leather', 0.65, prio=2)
        g.box((x - 3, -9, -10), (x + 3, -6, -9), 'metal', 0.6, prio=2)
        if p.lv >= 3:
            g.gem((x, 2, -4.5), 0.9, 'gem', glow=p.glow)
        if p.lv >= 4:
            t = Grid(g.seed)
            W.wing(t, (0, 0, 0), 1, p, span=5, rise=6, n=4)
            _copy(g, t, lambda i, j, k, x=x, s=s: (x + s * 3 + s * k, 4 + j, 2 + i))


BODY = {'chestplate': chestplate, 'robe_top': robe_top, 'leather_vest': leather_vest, 'leggings': leggings,
        'boots': boots}


# ───────────────────────────── shields (front +Z) ─────────────────────────────

def _shield(g, p, mask, lo, hi, face='plate'):
    face = 'wood' if p.theme == 'vine' and p.lv < 2 else face
    dist = g.slab(mask, lo, hi, 'xy', 0, max_half=1, slope=0.5, base_half=0, mat=face,
                  vfn=lambda u, v, w, d: ('orn' if p.lv >= 1 else 'metal', 0.6 + 0.1 * (w > 0)) if d <= 1 else
                  (0.4 + 0.06 * min(d, 4) + (0.08 if (u * 3 + v * 2) % 9 == 0 else 0)))
    return dist


def _boss(g, p, c=(0, 0)):
    g.ball((c[0], c[1], 1), 3.2, 'metal', sq=(1, 1, 0.7), vfn=lambda i, j, k, d: None if k < 1 else 0.4 + 0.4 * (1 - d))
    if p.lv >= 2:
        g.gem((c[0], c[1], 3.3), 1.4, 'gem', glow=p.glow)


def _shield_motif(g, p, top, bottom, hw):
    th = p.theme
    if th == 'crystal':
        for k in range(5):
            a = math.pi / 2 + (k - 2) * 0.5
            g.crystal((math.cos(a) * 4, math.sin(a) * 4, 2), (math.cos(a), math.sin(a), 0.3), 5.0 + (k == 2) * 2, 1.1,
                      'crystal', glow=p.glow, prio=3)
    elif th == 'clock':
        W.gear(g, (0, 0, 2), 6.0, p, 12, 'xy', 'orn')
        W.gear(g, (-6, top - 6, 2), 3.0, p, 8, 'xy', 'metal')
        W.gear(g, (6, bottom + 6, 2), 3.0, p, 8, 'xy', 'metal')
    elif th == 'forge':
        for s in (-1, 1):
            g.crystal((s * (hw - 2), top - 3, 1), (s * 0.6, 1, 0.3), 4.0, 1.0, 'metal', prio=3)
        for v in range(bottom + 4, top - 3, 3):
            g.put(0, v, 2, 'glow', 0.8, glow=True, prio=3)
    elif th == 'water':
        W.shell(g, (0, -2, 2), p, 4.0)
    elif th == 'vine':
        W.vines(g, bottom + 2, top - 2, hw - 2, p, n=1, zs=0.15)
    if p.lv >= 4:
        W.float_shards(g, [(-(hw + 4), top - 4, 0), (hw + 4, bottom + 6, 0)], p, 3.0, 0.9)


def round_shield(g, p):
    R = 12
    _shield(g, p, lambda u, v: u * u + v * v <= R * R, (-R - 1, -R - 1), (R + 1, R + 1))
    if p.lv >= 1:
        g.torus((0, 0, 1), R - 3.5, 0.5, 'z', 'orn', 0.65)
    _boss(g, p)
    _shield_motif(g, p, R, -R, R)


def kite_shield(g, p):
    def m(u, v):
        if v > 8:
            return abs(u) <= 10 - (v - 8) * 0.9 and v <= 12
        return abs(u) <= 10 * max(0.0, (v + 16) / 24) ** 0.8 and v >= -16
    _shield(g, p, m, (-11, -17), (11, 13))
    for v in range(-12, 10):
        g.put(0, v, 1, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=2)
    for u in range(-7, 8):
        g.put(u, 3, 1, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=2)
    _boss(g, p, (0, 3))
    _shield_motif(g, p, 12, -16, 10)


def tower_shield(g, p):
    def m(u, v):
        if v > 12:
            return abs(u) <= 9 and (v - 12) ** 2 + u * u * 0.25 <= 16
        return abs(u) <= 9 and v >= -15
    _shield(g, p, m, (-10, -16), (10, 17))
    for v in range(-13, 15, 4):
        for u in (-7, 7):
            g.put(u, v, 1, 'metal', 0.7, prio=2)
    _boss(g, p, (0, 1))
    _shield_motif(g, p, 15, -15, 9)


SHIELDS = {'round_shield': round_shield, 'kite_shield': kite_shield, 'tower_shield': tower_shield}
