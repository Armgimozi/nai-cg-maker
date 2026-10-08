#!/usr/bin/env python3
"""
그림 검사기 (DESIGN.md 10.7). 리소스팩의 모든 PNG 가 손으로 찍은 그림처럼 보이는지 기계로 먼저 거른다.

  python3 pack/artlint.py [폴더 또는 png ...]      (기본: pack/resourcepack)

오류 (하나라도 있으면 gen_pack 이 zip 을 만들지 않는다)
  palette    팔레트(palette.py) 밖의 색
  saturated  채도가 SAT_MAX 를 넘는 색, 빛 허용 그림(palette.GLOW)이 아니면
  blue       색상 200~300°(파랑~보라)이면서 밝기 0.5 를 넘는 색 (예외: 마나 막대 그림의 마나 계열, palette.blue_exempt)
  gradient   아주 작은 차이로 5칸 넘게 이어지는 매끈한 그라데이션 (가로·세로)
  glowalpha  빛 허용 그림이 아닌데 발광 알파(250~252)
  restricted 쓰는 곳이 정해진 계열(palette.RESTRICTED, 생피)을 다른 그림에 씀
  markalpha  구르기 대역의 1인칭 표시 알파 (palette.MARK_ALPHA, 240~249): 표시 그림 (palette.is_mark_path) 은 보이는 픽셀이 모두
             한 표시 알파여야 하고, 아이템·블록 그림 가운데 다른 그림은 그 알파를 쓰면 안 된다 (아이템 셰이더가 카메라 곁에서 버린다)
경고
  colors     16×16 칸 하나에 색이 12개 넘음
  symmetric  아이콘(textures/item, pack.png)의 완벽한 좌우 대칭
  repeat     똑같은 4×4 조각이 세 번 이상 반복 (색 3개 이상이고 한 색이 11칸 이하인 무늬 조각만 본다).
             GUI 그림(textures/gui/)에서는 두 가지를 무늬로 세지 않는다 (2026-10-07, 창을 구조로 다시 그리며):
               - 곧은 줄: 조각의 줄마다 한 색이거나 열마다 한 색 (테·베벨·홈처럼 곧게 뻗은 선). 고른 선은 어디를 잘라도
                 같은 조각이라 9조각 단추의 테만으로도 수십 번 걸렸다. 찍어 늘어놓은 무늬가 아니다.
               - 칸 격자: 같은 조각이 바로 옆 칸 (바닐라 칸 간격 18, 단축 슬롯 20) 에도 있는 것. 칸의 자리와 수는
                 바닐라가 정한다. 칸 격자 밖에서 세 번 이상 나오는 무늬, 아이템·몹 그림의 반복은 그대로 경고다.
  alpha      반투명 픽셀 (1~249). 손으로 찍은 그림은 보통 0 아니면 255. 창·HUD 그림 (textures/gui/, textures/font/) 은
             세지 않는다: 다크 소울 3 의 반투명 검은 판이 사용자 결정이다 (2026-10-07, gui_skin.py 머리말).
             HUD 그림 글자 (textures/font/hud_*) 는 반복 검사에서 GUI 그림처럼 곧은 줄을 세지 않는다 (막대 조각은 곧은 줄이다)

블록 그림 (textures/block/, textures/colormap/, palette.BLOCK_ART) 은 바닐라 그림의 꼴을 그대로 두고 색만 옮긴 것이라
(blocks_grade.py) 두 가지를 다르게 센다 (2026-10-08). 색·채도·파랑·그라데이션·색 수 검사는 그대로다.
  - repeat: 세로로 긴 움직이는 그림 (물, 용암, 불 …) 은 한 장면 (가로 폭 × 가로 폭) 안에서만 센다. 장면끼리는 같은 그림이
            조금씩 움직이는 것이라 겹치는 조각이 당연하다. 흐르는 물·용암의 32×32 장면은 16×16 한 장을 2×2 로 깐 것이라
            (98% 이상 같으면) 그 한 장만 센다.
  - 블록 그림의 경고는 갈래마다 한 줄로 모아 보인다 (바닐라의 판자·흐름 무늬에서 온 반복이 수천 건이다). -v 면 모두.
  - alpha:  비치는 블록 (BLOCK_TRANSLUCENT: 색유리, 얼음, 물, 차원문, 슬라임, 꿀, 부서지는 금) 은 반투명이 그 블록의 성질이다.
블록 그림에만 더 보는 경고 둘 (2026-10-08, AI 티: 흩뿌린 점과 1픽셀 바둑판). 움직이는 그림은 장면마다 보고 가장 나쁜 장면으로
  speck      외톨이 점: 여덟 이웃 어디에도 같은 색이 없고 네 이웃이 모두 한 색이며 그 색과 밝기가 한 단 (0.05) 넘게 다른 점이
             불투명 픽셀의 SPECK_MAX (6%) 를 넘음. 고른 바탕에 흩뿌린 잡음, 색 계단이 바닐라의 잔결을 점으로 뭉갠 것을 잡는다
             (대각선 1픽셀 선은 여덟 이웃에 같은 색이 있어 세지 않는다)
  dither     1픽셀 바둑판: 네 이웃과 모두 다르고 그 이웃이 두 색 이하인 점이 불투명 픽셀의 DITHER_MAX (30%) 를 넘음
             (짚단을 a·l·d 를 번갈아 찍어 그린 것 같은 무늬. 바닐라 블록 가운데 이 값을 넘는 것은 1,100 장 중 8 장)
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
REPEAT_FLAT = 11        # 한 색이 16칸 중 이보다 많으면 민무늬로 보고 반복을 세지 않는다
SLOT_PITCH = (18, 20)   # GUI 칸 격자 간격 (창 18, 단축 슬롯 20). 이 간격으로 이웃한 같은 조각은 칸 격자다

SPECK_MAX = 0.06       # 블록 그림: 외톨이 점의 몫
DITHER_MAX = 0.30      # 블록 그림: 바둑판 점의 몫

ERRORS = ("palette", "saturated", "blue", "gradient", "glowalpha", "restricted", "markalpha")
# 반투명이 성질인 블록 그림 (이름 조각). 바닐라도 이 그림들만 반투명 픽셀을 쓴다
BLOCK_TRANSLUCENT = ("glass", "ice", "water_", "nether_portal", "respawn_anchor_top", "slime_block", "honey_block",
                     "tripwire", "frogspawn", "destroy_stage_")


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

    def print(self, root=None, full=False):
        blocks = {}
        for level, path, rule, msg in self.items:
            rel = os.path.relpath(path, root) if root else path
            if level == "경고" and not full and palette.is_block_path(rel):
                blocks.setdefault(rule, []).append(palette.block_name(rel))
                continue
            print(f"  [{level}] {rel}: {rule} — {msg}")
        for rule, names in sorted(blocks.items()):
            uniq = sorted(set(names), key=lambda n: (-names.count(n), n))
            print(f"  [경고] 블록 그림 {rule} {len(names)}건, {len(uniq)}장 (많은 차례): {', '.join(uniq[:6])}"
                  + (" …" if len(uniq) > 6 else "") + " — 모두 보려면 artlint.py -v")


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


def _straight(t):
    """4×4 조각이 곧은 줄인가: 줄마다 한 색이거나 열마다 한 색."""
    rows = all((t[i] == t[i, 0]).all() for i in range(4))
    cols = all((t[:, j] == t[0, j]).all() for j in range(4))
    return rows or cols


def speck_dither(a):
    """
    블록 그림 한 장면 (정사각) 의 (외톨이 점 몫, 바둑판 점 몫). 가장자리는 감아서 본다 (블록은 이어 놓인다).
    외톨이: 여덟 이웃에 같은 색이 없고, 네 이웃이 한 색이고, 그 색과 밝기 (luma) 가 0.05 넘게 다르다.
    바둑판: 네 이웃과 모두 다르고, 네 이웃이 두 색 이하.
    """
    w = a.shape[1]
    op = a[..., 3] > 0
    key = a[..., 0].astype(np.int64) * 65536 + a[..., 1].astype(np.int64) * 256 + a[..., 2]
    lu = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) / 255.0
    sp = di = 0
    tot = int(op.sum())
    for y in range(w):
        for x in range(w):
            if not op[y, x]:
                continue
            n4 = [((y + dy) % w, (x + dx) % w) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if not all(op[p] for p in n4):
                continue
            ks = [key[p] for p in n4]
            if key[y, x] in ks:
                continue
            if len(set(ks)) <= 2:
                di += 1
            if len(set(ks)) == 1 and abs(lu[y, x] - lu[n4[0]]) >= 0.05:
                d4 = [((y + dy) % w, (x + dx) % w) for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1))]
                if all(not op[p] or key[p] != key[y, x] for p in d4):
                    sp += 1
    return sp / max(1, tot), di / max(1, tot)


def check_image(path, report, rel=None):
    rel = (rel or path).replace("\\", "/")
    glow = palette.is_glow_path(rel)
    vivid = palette.is_vivid_path(rel)
    mark = palette.is_mark_path(rel)
    tint_base = palette.is_tint_base_path(rel)
    img = Image.open(path).convert("RGBA")
    a = np.array(img)
    h, w = a.shape[:2]
    alpha = a[..., 3]
    vis = alpha > 0
    if not vis.any():
        return

    # 1~3. 색 하나하나
    bad_pal, bad_sat, bad_blue, bad_fam = [], [], [], []
    seen = {}
    ys, xs = np.nonzero(vis)
    for y, x in zip(ys, xs):
        rgb = tuple(int(v) for v in a[y, x, :3])
        if rgb not in seen:
            nm = palette.name_of(rgb)
            seen[rgb] = (nm, palette.too_saturated(rgb), palette.blue_glow(rgb),
                         nm is not None and not palette.family_allowed(nm, rel))
        name, sat, blue, fam = seen[rgb]
        if name is None and not tint_base:
            bad_pal.append((x, y, rgb))
        if sat and not (glow or vivid):
            bad_sat.append((x, y, rgb))
        if fam:
            bad_fam.append((x, y, rgb))
        if blue and not palette.blue_exempt(rgb, rel):   # 마나 막대만 예외 (palette.MANA_ART)
            bad_blue.append((x, y, rgb))
    if bad_pal:
        cols = sorted({"#%02x%02x%02x" % p[2] for p in bad_pal})
        report.add("오류", path, "palette", f"팔레트 밖의 색 {len(cols)}개 ({', '.join(cols[:5])}) 픽셀 {len(bad_pal)}개, "
                   f"처음 {_fmt([(p[0], p[1]) for p in bad_pal])}")
    if bad_sat:
        cols = sorted({palette.name_of(p[2]) or "#%02x%02x%02x" % p[2] for p in bad_sat})
        report.add("오류", path, "saturated", f"빛 허용 그림이 아닌데 채도 높은 색 {', '.join(cols)} 픽셀 {len(bad_sat)}개")
    if bad_fam:
        cols = sorted({palette.name_of(p[2]) for p in bad_fam})
        report.add("오류", path, "restricted", f"이 그림에서 쓸 수 없는 계열의 색 {', '.join(cols)} 픽셀 {len(bad_fam)}개")
    if bad_blue:
        report.add("오류", path, "blue", f"밝은 파랑·보라 픽셀 {len(bad_blue)}개, 처음 {_fmt([(p[0], p[1]) for p in bad_blue])}")

    # 발광 알파와 반투명
    ga = np.isin(alpha, palette.GLOW_ALPHA)
    if ga.any() and not glow:
        gy, gx = np.nonzero(ga)
        report.add("오류", path, "glowalpha", f"발광 알파 픽셀 {len(gx)}개, 처음 {_fmt(list(zip(gx, gy)))}")
    block = palette.is_block_path(rel)
    semi = (alpha > 0) & (alpha < 250)
    ui = "/textures/gui/" in "/" + rel or "/textures/font/" in "/" + rel
    if mark:
        # 구르기 대역의 표시 그림: 보이는 픽셀이 모두 한 표시 알파여야 한다 (셰이더가 그 값으로 반지름을 고른다)
        vals = set(int(v) for v in np.unique(alpha[vis]))
        if len(vals) != 1 or not vals <= set(palette.MARK_ALPHA):
            report.add("오류", path, "markalpha", f"표시 알파가 한 값 ({palette.MARK_ALPHA[0]}~{palette.MARK_ALPHA[-1]}) 이 아니다: {sorted(vals)[:6]}")
    else:
        # 아이템 셰이더로 그려지는 그림 (아이템·블록 아틀라스) 이 표시 알파를 쓰면 카메라 곁에서 사라진다 (1인칭 손에 든 것)
        if not ui and np.isin(alpha, palette.MARK_ALPHA).any() and ("/textures/item/" in "/" + rel or "/textures/block/" in "/" + rel):
            report.add("오류", path, "markalpha", "구르기 대역의 표시 알파 (240~249) 를 다른 그림이 쓴다 (카메라 곁에서 사라진다)")
        if semi.any() and not ui and not (block and any(t in palette.block_name(rel) for t in BLOCK_TRANSLUCENT)):
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

    # 블록 그림: 외톨이 점과 1픽셀 바둑판 (장면마다, 가장 나쁜 장면)
    if block and "/textures/block/" in "/" + rel and w >= 8 and h % w == 0:
        worst_s = worst_d = 0.0
        for fi in range(h // w):
            sv, dv = speck_dither(a[fi * w:(fi + 1) * w])
            worst_s, worst_d = max(worst_s, sv), max(worst_d, dv)
        if worst_s > SPECK_MAX:
            report.add("경고", path, "speck", f"외톨이 점 {worst_s:.0%} (한도 {SPECK_MAX:.0%})")
        if worst_d > DITHER_MAX:
            report.add("경고", path, "dither", f"1픽셀 바둑판 점 {worst_d:.0%} (한도 {DITHER_MAX:.0%})")

    # 6. 아이콘의 완벽한 좌우 대칭
    icon = "/textures/item/" in "/" + rel or rel.endswith("pack.png")
    if icon and w > 2:
        flat = np.where(vis[..., None], a, 0)
        if np.array_equal(flat, flat[:, ::-1]):
            report.add("경고", path, "symmetric", "좌우가 완벽히 같다. 마모로 대칭을 깬다")

    # 7. 같은 4×4 조각의 반복 (GUI 는 곧은 줄과 칸 격자를 빼고 센다)
    gui = "/textures/gui/" in "/" + rel or "/textures/font/hud_" in "/" + rel
    # 움직이는 블록 그림 (세로 띠) 은 장면마다 따로 센다. 반 폭으로 2×2 를 깐 장면은 그 한 장만
    frame = w if block and h > w and h % w == 0 else 0
    halves = set()
    for fi in range(h // frame if frame else 0):
        f, p = a[fi * frame:(fi + 1) * frame], frame // 2
        if frame % 2 == 0 and frame >= 16 and (f[:, :p] == f[:, p:]).all(-1).mean() >= 0.98 \
                and (f[:p] == f[p:]).all(-1).mean() >= 0.98:
            halves.add(fi)
    if w >= 8 or h >= 8:
        groups = {}
        for y in range(h - 3):
            if frame and y // frame != (y + 3) // frame:
                continue
            half = frame // 2 if frame and y // frame in halves else 0
            if half and y % frame + 3 >= half:
                continue
            for x in range(w - 3):
                if half and x + 3 >= half:
                    break
                t = a[y:y + 4, x:x + 4]
                if not (t[..., 3] > 0).all():
                    continue
                flat = [tuple(p) for p in t.reshape(-1, 4).tolist()]
                cols = set(flat)
                # 색이 셋 미만이거나 한 색이 거의 다 덮는 조각(민무늬 테, 바탕)은 무늬가 아니다
                if len(cols) < 3 or max(flat.count(k) for k in cols) > REPEAT_FLAT:
                    continue
                if gui and _straight(t):
                    continue
                groups.setdefault((y // frame if frame else 0, t.tobytes()), []).append((x, y))
        for key, pos in groups.items():
            if gui:
                at = set(pos)
                pos = [(x, y) for x, y in pos
                       if not any((x + d, y) in at or (x - d, y) in at or (x, y + d) in at or (x, y - d) in at
                                  for d in SLOT_PITCH)]
            taken = []
            for x, y in pos:
                if all(abs(x - tx) >= 4 or abs(y - ty) >= 4 for tx, ty in taken):
                    taken.append((x, y))
            if len(taken) >= REPEAT_MIN:
                report.add("경고", path, "repeat", f"같은 4×4 조각 {len(taken)}번: {_fmt(taken)}")


def lint(paths, root=None, quiet=False, full=False):
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
        report.print(root, full)
        print(f"artlint: PNG {len(files)}개, 오류 {len(report.errors)}, 경고 {len(report.warnings)}")
    return report


def main(argv):
    full = "-v" in argv
    paths = [p for p in argv if p != "-v"] or [os.path.join(HERE, "resourcepack")]
    root = paths[0] if len(paths) == 1 and os.path.isdir(paths[0]) else None
    report = lint(paths, root, full=full)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
