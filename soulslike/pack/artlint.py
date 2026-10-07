#!/usr/bin/env python3
"""
그림 검사기 (DESIGN.md 10.7). 리소스팩의 모든 PNG 가 손으로 찍은 그림처럼 보이는지 기계로 먼저 거른다.

  python3 pack/artlint.py [폴더 또는 png ...]      (기본: pack/resourcepack)

오류 (하나라도 있으면 gen_pack 이 zip 을 만들지 않는다)
  palette    팔레트(palette.py) 밖의 색
  saturated  채도가 SAT_MAX 를 넘는 색, 빛 허용 그림(palette.GLOW)이 아니면
  blue       색상 200~300°(파랑~보라)이면서 밝기 0.5 를 넘는 색
  gradient   아주 작은 차이로 5칸 넘게 이어지는 매끈한 그라데이션 (가로·세로)
  glowalpha  빛 허용 그림이 아닌데 발광 알파(250~252)
경고
  colors     16×16 칸 하나에 색이 12개 넘음
  symmetric  아이콘(textures/item, pack.png)의 완벽한 좌우 대칭
  repeat     똑같은 4×4 조각이 세 번 넘게 반복 (색 3개 이상인 조각만 본다)
  alpha      반투명 픽셀 (1~249). 손으로 찍은 그림은 보통 0 아니면 255
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import palette  # noqa: E402

GRADIENT_STEP = 10      # 채널마다 이 이하로만 바뀌면 '아주 작은 차이'
GRADIENT_RUN = 5        # 이 칸 수를 넘게 (= 6픽셀 이상) 이어지면 오류
TILE_COLORS = 12
REPEAT_MIN = 3          # 같은 4×4 조각이 이만큼 (겹치지 않게) 나오면 경고

ERRORS = ("palette", "saturated", "blue", "gradient", "glowalpha")


class Report:
    def __init__(self):
        self.items = []    # (등급, 파일, 규칙, 글)

    def add(self, level, path, rule, msg):
        self.items.append((level, path, rule, msg))

    @property
    def errors(self):
        return [i for i in self.items if i[0] == "오류"]

    @property
    def warnings(self):
        return [i for i in self.items if i[0] == "경고"]

    def print(self, root=None):
        for level, path, rule, msg in self.items:
            rel = os.path.relpath(path, root) if root else path
            print(f"  [{level}] {rel}: {rule} — {msg}")


def _fmt(xy):
    return ", ".join(f"({x},{y})" for x, y in xy[:4]) + (" …" if len(xy) > 4 else "")


def _gradient_runs(px, mask):
    """한 줄(가로 또는 세로)에서 매끈한 그라데이션 구간을 찾는다. (시작, 길이) 목록."""
    runs = []
    n = len(px)
    i = 0
    while i < n - 1:
        j = i
        sign = 0
        while j < n - 1 and mask[j] and mask[j + 1]:
            d = px[j + 1].astype(int) - px[j].astype(int)
            if not d.any() or np.abs(d).max() > GRADIENT_STEP:
                break
            s = 1 if d.sum() > 0 else -1
            if sign and s != sign:
                break
            sign = s
            j += 1
        if j - i > GRADIENT_RUN - 1 and j - i + 1 > GRADIENT_RUN:
            runs.append((i, j - i + 1))
        i = max(j, i + 1)
    return runs


def check_image(path, report, rel=None):
    rel = (rel or path).replace("\\", "/")
    glow = palette.is_glow_path(rel)
    img = Image.open(path).convert("RGBA")
    a = np.array(img)
    h, w = a.shape[:2]
    alpha = a[..., 3]
    vis = alpha > 0
    if not vis.any():
        return

    # 1~3. 색 하나하나
    bad_pal, bad_sat, bad_blue = [], [], []
    seen = {}
    ys, xs = np.nonzero(vis)
    for y, x in zip(ys, xs):
        rgb = tuple(int(v) for v in a[y, x, :3])
        if rgb not in seen:
            seen[rgb] = (palette.name_of(rgb), palette.too_saturated(rgb), palette.blue_glow(rgb))
        name, sat, blue = seen[rgb]
        if name is None:
            bad_pal.append((x, y, rgb))
        if sat and not glow:
            bad_sat.append((x, y, rgb))
        if blue:
            bad_blue.append((x, y, rgb))
    if bad_pal:
        cols = sorted({"#%02x%02x%02x" % p[2] for p in bad_pal})
        report.add("오류", path, "palette", f"팔레트 밖의 색 {len(cols)}개 ({', '.join(cols[:5])}) 픽셀 {len(bad_pal)}개, "
                   f"처음 {_fmt([(p[0], p[1]) for p in bad_pal])}")
    if bad_sat:
        cols = sorted({palette.name_of(p[2]) or "#%02x%02x%02x" % p[2] for p in bad_sat})
        report.add("오류", path, "saturated", f"빛 허용 그림이 아닌데 채도 높은 색 {', '.join(cols)} 픽셀 {len(bad_sat)}개")
    if bad_blue:
        report.add("오류", path, "blue", f"밝은 파랑·보라 픽셀 {len(bad_blue)}개, 처음 {_fmt([(p[0], p[1]) for p in bad_blue])}")

    # 발광 알파와 반투명
    ga = np.isin(alpha, palette.GLOW_ALPHA)
    if ga.any() and not glow:
        gy, gx = np.nonzero(ga)
        report.add("오류", path, "glowalpha", f"발광 알파 픽셀 {len(gx)}개, 처음 {_fmt(list(zip(gx, gy)))}")
    semi = (alpha > 0) & (alpha < 250)
    if semi.any():
        report.add("경고", path, "alpha", f"반투명 픽셀 {int(semi.sum())}개")

    # 5. 매끈한 그라데이션 (가로줄, 세로줄)
    rgb = a[..., :3]
    found = []
    for y in range(h):
        for s, n in _gradient_runs(rgb[y], vis[y]):
            found.append(f"가로 y={y} x={s}..{s + n - 1}")
    for x in range(w):
        for s, n in _gradient_runs(rgb[:, x], vis[:, x]):
            found.append(f"세로 x={x} y={s}..{s + n - 1}")
    if found:
        report.add("오류", path, "gradient", f"{len(found)}곳, {'; '.join(found[:3])}")

    # 4. 16×16 칸의 색 수
    for ty in range(0, h, 16):
        for tx in range(0, w, 16):
            t = a[ty:ty + 16, tx:tx + 16]
            tv = t[..., 3] > 0
            n = len({tuple(p) for p in t[tv][:, :3].tolist()})
            if n > TILE_COLORS:
                report.add("경고", path, "colors", f"칸 ({tx},{ty}) 에 색 {n}개")

    # 6. 아이콘의 완벽한 좌우 대칭
    icon = "/textures/item/" in "/" + rel or rel.endswith("pack.png")
    if icon and w > 2:
        flat = np.where(vis[..., None], a, 0)
        if np.array_equal(flat, flat[:, ::-1]):
            report.add("경고", path, "symmetric", "좌우가 완벽히 같다. 마모로 대칭을 깬다")

    # 7. 같은 4×4 조각의 반복
    if w >= 8 or h >= 8:
        groups = {}
        for y in range(h - 3):
            for x in range(w - 3):
                t = a[y:y + 4, x:x + 4]
                if not (t[..., 3] > 0).all():
                    continue
                cols = {tuple(p) for p in t.reshape(-1, 4).tolist()}
                if len(cols) < 3:
                    continue
                groups.setdefault(t.tobytes(), []).append((x, y))
        for key, pos in groups.items():
            taken = []
            for x, y in pos:
                if all(abs(x - tx) >= 4 or abs(y - ty) >= 4 for tx, ty in taken):
                    taken.append((x, y))
            if len(taken) >= REPEAT_MIN:
                report.add("경고", path, "repeat", f"같은 4×4 조각 {len(taken)}번: {_fmt(taken)}")


def lint(paths, root=None, quiet=False):
    """paths 의 PNG 를 모두 검사해 Report 를 돌려준다. root 는 경로 표시와 빛 허용 판단의 기준."""
    report = Report()
    files = []
    for p in paths:
        if os.path.isdir(p):
            for base, _, fs in os.walk(p):
                files += [os.path.join(base, f) for f in fs if f.endswith(".png")]
        elif p.endswith(".png"):
            files.append(p)
    for f in sorted(files):
        rel = os.path.relpath(f, root) if root else f
        check_image(f, report, rel)
    if not quiet:
        report.print(root)
        print(f"artlint: PNG {len(files)}개, 오류 {len(report.errors)}, 경고 {len(report.warnings)}")
    return report


def main(argv):
    paths = argv or [os.path.join(HERE, "resourcepack")]
    root = paths[0] if len(paths) == 1 and os.path.isdir(paths[0]) else None
    report = lint(paths, root)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
