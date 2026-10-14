"""마을 공공 조각 — 미궁의 아가리 · 등불 광장 · 전직의 전당 · 기록 보관소 (VILLAGE.md §5 1·2·4·5).

정방향: 정면(문)은 z=0 쪽, 북쪽을 본다. x 증가 = 동쪽. floor_y 층이 바닥(사람은 floor_y+1 에 섬), 그 아래는 땅속 기초.
지형 존중(§0): 실제로 쓰는 기둥만 칠하고 윤곽 밖(모서리·건물 옆 빈 땅)은 ' ' 로 남겨 원래 지형이 그대로 이어지게 한다.
땅속 공간(게이트 계단 우물)은 벽·바닥·계단 밑을 전부 직접 막는다 — 지형 흙에 기대지 않음.
"""
import math

from vlib import (Piece, mix, stairs, slab, log, wall, fence, pane, glass, lantern, candle, chain, campfire,
                  end_rod, flower_pot, trapdoor, B, DXZ, opposite, is_full, parse_block)


# ─────────────────────────────── 공통 도우미 ───────────────────────────────

def _quarters(inside, u, v):
    """칸 (u, v) 안 네 점 (왼아래, 오른아래, 왼위, 오른위) 이 모양 안인가."""
    return [inside(u + du, v + dv) for du, dv in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))]


def _pointed(w, spring, rr):
    """뾰족 아치 윤곽 (폭 w, u 0..w): v ≤ spring 은 곧은 벽, 그 위는 반지름 rr 원호 두 개가 만나는 꼭짓점."""
    def inside(u, v):
        if u < 0 or u > w:
            return False
        if v <= spring:
            return True
        dv = v - spring
        return (u - rr) ** 2 + dv * dv <= rr * rr and (u - (w - rr)) ** 2 + dv * dv <= rr * rr
    return inside


def _ogive(p, x0, x1, y0, top, spring, rr, zs, body, edge):
    """뾰족 아치 모양 덩어리 (바깥 윤곽). x0..x1 폭, y0 에서 위로, 윤곽 가장자리는 edge 재료 계단·반블록으로 다듬음.
    돌려줌: {x: 그 x 줄 맨 윗 칸 y}."""
    w = x1 - x0 + 1
    inside = _pointed(w, spring - y0, rr)
    tops = {}
    for i in range(w):
        for j in range(0, top - y0 + 1):
            bl, br, tl, tr = _quarters(inside, i, j)
            n = bl + br + tl + tr
            if n == 0:
                continue
            if n >= 3 or (n == 2 and not (bl and br)):
                b = body
            elif n == 2:
                b = slab(edge, "bottom")
            elif bl:
                b = stairs(edge, "west")
            elif br:
                b = stairs(edge, "east")
            else:
                continue
            for z in zs:
                p.set(x0 + i, y0 + j, z, b)
            tops[x0 + i] = y0 + j
    return tops


def _circle(dx, dz, r):
    """vlib.disc 와 같은 원 판정."""
    return dx * dx + dz * dz <= r * r + r


def _face_in(dx, dz):
    """중심을 바라보는 방향 (가구 앞면)."""
    if abs(dx) >= abs(dz):
        return "west" if dx > 0 else "east"
    return "north" if dz > 0 else "south"


def _lamp(p, x, z, y, arms="x", soul=False, kind=None, base="chiseled_stone_bricks", post="dark_oak"):
    """가로등: 받침(y) + 기둥 울타리 3칸 + 가로 팔(arms 축 양쪽) 아래 매단 등불 + 꼭대기 등불."""
    p.set(x, y, z, B(base))
    p.set(x, y + 1, z, fence(post))
    p.set(x, y + 2, z, fence(post))
    p.set(x, y + 3, z, fence(post))
    ax, az = (1, 0) if arms == "x" else (0, 1)
    for s in (-1, 1):
        p.set(x + ax * s, y + 3, z + az * s, fence(post))
        p.set(x + ax * s, y + 2, z + az * s, lantern(soul=soul, hanging=True, kind=kind))
        p.light(x + ax * s, y + 2, z + az * s)
    p.set(x, y + 4, z, lantern(soul=soul, hanging=False, kind=kind))


# ─────────────────────────────── 1. 미궁의 아가리 ───────────────────────────────

def labyrinth_gate():
    """마을의 상징. 앞마당 → 땅속으로 내려가는 계단 우물 → 그 끝 거대한 룬 아치와 검은 문면.
    정면(z=0)이 광장을 본다. 계단은 정면에서 뒤로(남쪽) 내려간다.
    실루엣: 가운데 뾰족 박공(층 19 + 수정 꼭지) > 양옆 기둥탑(층 14 + 수정관) > 앞마당 영혼불 화로 기둥 두 개."""
    W, H, D, F = 17, 22, 13, 5
    p = Piece("labyrinth_gate", "미궁의 아가리", W, H, D, floor_y=F, anchor=(8, 1),
              foundation_mix=[("deepslate_bricks", 3), ("cracked_deepslate_bricks", 1), ("cobbled_deepslate", 1),
                              ("tuff_bricks", 1)])
    brick = mix(("deepslate_bricks", 6), ("cracked_deepslate_bricks", 1), ("deepslate_tiles", 2), seed=1)
    tile = mix(("deepslate_tiles", 5), ("cracked_deepslate_tiles", 1), seed=2)
    flag = mix(("polished_deepslate", 3), ("deepslate_tiles", 2), ("cobbled_deepslate", 1), ("tuff_bricks", 1), seed=3)
    pol, rune = B("polished_deepslate"), B("chiseled_deepslate")
    gold, gild = B("gold_block"), B("gilded_blackstone")
    amy, cry = B("amethyst_block"), B("crying_obsidian")

    # ── 앞마당 (z 0..3): 바닥돌 + 바로 밑 기초 한 겹. 가운데는 금빛 흑암·룬 줄이 계단으로 이끈다
    for z in range(0, 4):
        for x in (range(2, 15) if z == 0 else range(1, 16)):
            p.set(x, F - 1, z, brick)
            p.set(x, F, z, flag)
    for z in range(0, 4):
        p.set(7, F, z, pol)
        p.set(9, F, z, pol)
        p.set(8, F, z, B("pearlescent_froglight", axis="y") if z % 2 == 0 else rune)   # 빛나는 룬 징검돌
    for x in (5, 11):
        p.set(x, F, 1, B("pearlescent_froglight", axis="y"))
        p.set(x, F, 0, gild)
        p.set(x, F, 2, gild)
    p.fill(4, 0, 3, 12, F - 2, 3, brick)               # 계단 우물 앞벽 (땅속)

    # ── 계단 우물 (x 5..11): z 4..7 네 칸 내려가고 z 8..10 바닥(층 0). 벽·계단 밑은 전부 직접 채움
    for i, z in enumerate(range(4, 8)):
        y = F - 1 - i
        for x in range(5, 12):
            p.set(x, y, z, stairs("polished_deepslate", "north"))
            if y > 0:
                p.fill(x, 0, z, x, y - 1, z, brick)
            p.clear(x, y + 1, z, x, F + 3, z)
    for z in range(8, 11):
        for x in range(5, 12):
            p.set(x, 0, z, pol)
    p.set(8, 0, 9, rune)
    p.set(8, 0, 10, gild)
    p.clear(5, 1, 8, 11, F + 3, 8)
    for x in (4, 12):                                   # 우물 옆벽 (땅속 0..F) + 룬 띠, 가운데 진주빛 개구리불
        for z in range(4, 9):
            p.fill(x, 0, z, x, F, z, brick)
            p.set(x, 3, z, rune)
        p.set(x, 3, 6, B("pearlescent_froglight", axis="y"))
    for x in (4, 12):                                   # 난간: 기둥(z 4, 8) 위 영혼 등불, 사이는 담장
        for z in range(4, 9):
            p.set(x, F + 1, z, pol if z in (4, 8) else wall("polished_deepslate"))
        for z in (4, 8):
            p.set(x, F + 2, z, lantern(soul=True, hanging=False))
            p.light(x, F + 2, z)

    # ── 양옆 턱 (z 4..8): 바닥돌 + 땅을 뚫고 나온 자수정 정동(현무암 → 방해석 → 자수정)
    for x0 in (1, 13):
        for z in range(4, 9):
            for x in range(x0, x0 + 3):
                p.set(x, F, z, flag)
                p.set(x, F - 1, z, brick)
    for sx in (1, -1):                                  # 서쪽(sx=1)·동쪽(sx=-1) 거울
        X = (lambda x: x) if sx == 1 else (lambda x: 16 - x)
        p.set(X(1), F, 6, B("calcite"))
        p.set(X(2), F, 5, B("calcite"))
        p.set(X(1), F + 1, 6, B("smooth_basalt"))
        p.set(X(1), F + 2, 6, amy)
        p.set(X(2), F + 1, 5, amy)
        p.set(X(1), F + 3, 6, B("amethyst_cluster", facing="up"))
        p.set(X(2), F + 2, 5, B("amethyst_cluster", facing="up"))
        p.set(X(2), F + 1, 6, B("large_amethyst_bud", facing="up"))
        p.set(X(1), F + 1, 5, B("medium_amethyst_bud", facing="up"))
        p.set(X(3), F + 1, 6, B("small_amethyst_bud", facing="up"))
        p.set(X(1), F + 1, 7, B("small_amethyst_bud", facing="up"))

    # ── 기둥탑 두 개 (x 1..3 / 13..15, z 9..11) + 뒤 버팀벽 (z 12)
    for x0 in (1, 13):
        cxp = x0 + 1
        p.fill(x0, 0, 9, x0 + 2, F + 8, 11, brick)
        p.fill(x0, 0, 12, x0 + 2, F + 3, 12, brick)
        for x in range(x0, x0 + 3):
            p.set(x, F + 4, 12, stairs("polished_deepslate", "north"))
        p.set(cxp, F + 4, 12, pol)
        p.set(cxp, F + 5, 12, lantern(soul=True, hanging=False))
        p.light(cxp, F + 5, 12)
        for z in range(9, 12):                         # 바깥 옆면은 타일로 결 바꿈
            for y in range(F + 1, F + 9):
                p.set(x0 if x0 == 1 else x0 + 2, y, z, tile)
        for y in range(0, F + 9):                       # 모서리 광택 띠 (꼭대기는 금)
            p.set(x0, y, 9, gold if y == F + 8 else pol)
            p.set(x0 + 2, y, 9, gold if y == F + 8 else pol)
        # 앞면: 작은 기둥 두 개(z=8)가 룬 판을 감싼다
        for x in (x0, x0 + 2):
            p.fill(x, F + 1, 8, x, F + 6, 8, pol)
            p.set(x, F + 7, 8, stairs("polished_deepslate", "south"))
        for y, b in ((F + 1, pol), (F + 2, rune), (F + 3, cry), (F + 4, cry), (F + 5, rune), (F + 6, gild)):
            p.set(cxp, y, 9, b)
        p.set(cxp, F + 7, 8, wall("polished_deepslate"))
        p.set(cxp, F + 6, 8, lantern(soul=True, hanging=True))
        p.light(cxp, F + 6, 8)
        p.set(cxp, F + 1, 8, B("deepslate_tile_slab", type="bottom"))
        # 띠 (층 F+8) + 수정관: 계단 고리 → 끌 심층암 + 사방 자수정 → 꼭대기 군락
        y = F + 9
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == 0 and dz == 0:
                    p.set(cxp, y, 10, pol)
                elif abs(dx) >= abs(dz):
                    p.set(cxp + dx, y, 10 + dz, stairs("deepslate_tiles", "east" if dx < 0 else "west"))
                else:
                    p.set(cxp + dx, y, 10 + dz, stairs("deepslate_tiles", "south" if dz < 0 else "north"))
        p.set(cxp, y + 1, 10, rune)
        for f in ("north", "south", "east", "west"):
            dx, dz = DXZ[f]
            p.set(cxp + dx, y + 1, 10 + dz, B("amethyst_cluster", facing=f))
        p.set(cxp, y + 2, 10, amy)
        p.set(cxp, y + 3, 10, B("amethyst_cluster", facing="up"))

    # ── 가운데 박공 + 룬 아치 (x 4..12, z 9..12): 뾰족 윤곽 꼭대기 층 19
    tops = _ogive(p, 4, 12, 0, 20, 12, 8.5, range(9, 11), brick, "polished_deepslate")
    _ogive(p, 4, 12, 0, 17, 10, 7.0, range(11, 12), brick, "deepslate_tiles")     # 뒤는 한 단씩 낮게
    _ogive(p, 4, 12, 0, 15, 8, 6.0, range(12, 13), brick, "deepslate_tiles")
    # 앞면 박공 테두리 한 칸 안쪽 = 금빛 흑암 선
    for x in range(4, 13):
        t = tops[x]
        for y in range(t - 1, t + 1):
            v = p.get(x, y, 9)
            if v not in (" ", ".") and is_full(parse_block(v)[0]) and y >= 13:
                below_edge = p.get(x, y + 1, 9)
                if below_edge not in (" ", ".") and not is_full(parse_block(below_edge)[0]):
                    p.set(x, y, 9, gild)
    # 앞 아치 (z=9): 폭 9, 테 = 룬/광택 섞기
    p.arch(4, 12, 1, 14, 9, 9, mat="polished_deepslate", axis="x", style="pointed",
           frame=mix(("chiseled_deepslate", 1), ("polished_deepslate", 1), seed=4))
    # 안 아치 (z=10): 폭 7, 테 = 자수정 블록
    p.arch(5, 11, 1, 12, 10, 10, mat="deepslate_bricks", axis="x", style="pointed", frame=amy)
    for x in range(4, 13):                              # 아치 밑 바닥 (z 9 양끝 벽감 포함)
        p.set(x, 0, 9, pol)
    # 앞면 아치 테 바깥 둘째 줄 = 타일 띠 + 띠 위 빛나는 룬 (우는 흑요석) 몇 점
    hole = {(x, y) for x in range(4, 13) for y in range(1, 16) if p.get(x, y, 9) == "."}
    for x in range(4, 13):
        for y in range(F + 1, 19):
            v = p.get(x, y, 9)
            if v in (" ", ".") or not is_full(parse_block(v)[0]) or v in (gild,):
                continue
            dist = min((max(abs(x - hx), abs(y - hy)) for hx, hy in hole), default=99)
            if dist == 2:
                p.set(x, y, 9, cry if (y in (8, 12) and x != 8) else tile)
    # 뒷면 (z=12): 아래 띠 + 광택 기둥 두 줄 + 가운데 세로로 빛나는 룬 틈
    for x in range(4, 13):
        p.set(x, F + 1, 12, pol)
    for x in (5, 11):
        for y in range(F + 1, 20):
            v = p.get(x, y, 12)
            if v not in (" ", ".") and is_full(parse_block(v)[0]):
                p.set(x, y, 12, pol)
    for x in (6, 10):
        p.set(x, F + 6, 12, rune)
    for y in range(F + 2, F + 8):
        p.set(8, y, 12, cry if F + 3 <= y <= F + 6 else rune)
        p.set(7, y, 12, pol)
        p.set(9, y, 12, pol)
    p.set(8, F + 8, 12, gild)
    # 문면 (z=11): 안 아치 구멍 모양 그대로 검은 콘크리트 + 우는 흑요석 고리·가운데 줄
    face = []
    for y in range(1, 14):
        for x in range(5, 12):
            if p.get(x, y, 10) == ".":
                d = math.hypot(x - 8, y - 7.0)
                b = cry if (2.3 <= d <= 3.2) or (x == 8 and (y <= 3 or y == 7)) else B("black_concrete")
                p.set(x, y, 11, b)
                face.append((x, y, 11))
    # 쐐기돌 + 그 위 룬 눈 (팀파눔)
    apex = max(y for y in range(H) if p.get(8, y, 9) == ".")
    p.set(8, apex + 1, 9, gold)
    p.set(7, apex + 1, 9, gild)
    p.set(9, apex + 1, 9, gild)
    ey = apex + 3
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            p.set(8 + dx, ey + dy, 9, gold if (dx, dy) == (0, 0) else (cry if dx == 0 or dy == 0 else rune))
    # 아치 꼭대기 쇠사슬 + 영혼 등불
    p.set(8, apex, 9, chain())
    p.set(8, apex - 1, 9, chain())
    p.set(8, apex - 2, 9, lantern(soul=True, hanging=True))
    p.light(8, apex - 2, 9)
    # 송곳니: 안 아치 자수정 테 밑에 매달린 자수정 군락
    fangs = 0
    for y in range(12, 7, -1):
        for x in range(5, 8):
            if fangs < 3 and p.get(x, y, 10) == "." and p.get(x, y + 1, 10) == amy:
                for xx in (x, 16 - x):
                    p.set(xx, y, 10, B("amethyst_cluster", facing="down"))
                fangs += 1
    fangs = 0                                           # 앞 아치 테 밑에도 송곳니 두 쌍 (정면에서 보이는 아가리)
    for y in range(13, 8, -1):
        for x in range(4, 8):
            v = p.get(x, y + 1, 9)
            if fangs < 2 and p.get(x, y, 9) == "." and v not in (" ", ".") and is_full(parse_block(v)[0]):
                for xx in (x, 16 - x):
                    p.set(xx, y, 9, B("amethyst_cluster", facing="down"))
                fangs += 1
                break
    for x in (4, 12):                                   # 벽감 (z=9 양끝, 땅속): 영혼 등불
        p.set(x, 1, 9, lantern(soul=True, hanging=False))
        p.light(x, 1, 9)
    # 꼭지: 박공 꼭대기 → 자수정 블록 → 자수정 군락 (군락은 꽉 찬 면 위에만 붙음)
    crest = tops[8]
    p.set(8, crest, 9, pol)
    p.set(8, crest + 1, 9, amy)
    p.set(8, crest + 2, 9, B("amethyst_cluster", facing="up"))

    # ── 앞마당 영혼불 화로 기둥 두 개 (x 1..3 / 13..15, z 1..3)
    for cx in (2, 14):
        p.fill(cx - 1, F + 1, 1, cx + 1, F + 1, 3, pol)
        p.fill(cx - 1, F + 2, 1, cx + 1, F + 2, 3, tile)
        p.set(cx, F + 2, 2, brick)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx or dz:
                    f = ("east" if dx < 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz < 0 else "north")
                    p.set(cx + dx, F + 3, 2 + dz, stairs("polished_deepslate", f))
                    p.set(cx + dx, F + 7, 2 + dz, stairs("polished_deepslate", f, "top"))
        for y, b in ((F + 3, brick), (F + 4, rune), (F + 5, pol), (F + 6, cry), (F + 7, pol)):
            p.set(cx, y, 2, b)
        for dx in (-1, 1):
            for dz in (-1, 1):
                p.set(cx + dx, F + 8, 2 + dz, wall("polished_deepslate"))
        p.set(cx, F + 8, 2, campfire(soul=True))
        p.light(cx, F + 8, 2)
        p.banner(cx, F + 5, 1, "purple", [("rhombus", "black"), ("circle", "magenta"), ("border", "black"),
                                           ("triangles_bottom", "black")], facing="north")

    # 안내 표지판 (화로 기둥 받침 안쪽 면)
    p.sign(4, F + 2, 2, ["<light_purple><b>미궁의 아가리</b></light_purple>", "<gray>계단 아래 검은 문을</gray>",
                         "<gray>우클릭하면 입장</gray>"], wood="dark_oak", facing="east", glow=True)
    p.sign(12, F + 2, 2, ["<gold>미궁 안내인 벨라</gold>", "<gray>파티원은 모두</gray>", "<gray>검은 문 가까이로</gray>"],
           wood="dark_oak", facing="west", glow=True)

    # ── 마커
    p.entrance(8, 1, 9, "front")
    p.npc("guide", 11, F + 1, 1, "front")
    p.interact("entrance", face)
    p.ambient(8, 6, 10, "portal")
    return p


# ─────────────────────────────── 2. 등불 광장 ───────────────────────────────

def plaza():
    """둥근 광장 (반지름 10). 가운데 분수: 웅덩이(물 source 는 둘레·바닥이 막힌 칸 안만) + 얇은 접시 + 빛나는 수정 꼭대기.
    가로등 11개, 벤치·화단, 게시판(스폰 옆). 원 밖 모서리는 ' ' — 원래 지형이 그대로 이어진다."""
    N, c, R = 21, 10, 10
    p = Piece("plaza", "등불 광장", N, 10, N, floor_y=1, anchor=(c, c), door=False,
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 1), ("andesite", 1), ("tuff_bricks", 1)])
    border = mix(("stone_bricks", 3), ("polished_andesite", 2), ("mossy_stone_bricks", 1), ("cracked_stone_bricks", 1), seed=5)
    white = mix(("calcite", 4), ("polished_diorite", 2), ("quartz_bricks", 1), seed=6)
    teal = B("waxed_oxidized_cut_copper")
    teal2 = B("waxed_oxidized_copper")

    cells = [(x, z) for z in range(N) for x in range(N) if _circle(x - c, z - c, R)]
    inc = set(cells)
    for (x, z) in cells:
        dx, dz = x - c, z - c
        d = math.hypot(dx, dz)
        edge = any((x + ex, z + ez) not in inc for ex, ez in DXZ.values())
        p.set(x, 0, z, border)
        if edge:
            b = border
        elif d >= 8.8:
            b = B("stone_bricks") if (dx + dz) % 2 else B("polished_andesite")
        elif 5.6 <= d <= 6.5:
            b = teal                                   # 분수 둘레 청록 고리
        elif dx == 0 or dz == 0:
            b = teal2 if d > 6.5 else white            # 네 길 가운데 청록 줄
        elif abs(dx) <= 1 or abs(dz) <= 1:
            b = B("smooth_quartz")
        elif abs(dx) == abs(dz):
            b = B("prismarine_bricks")                 # 대각선 별 무늬
        else:
            b = white
        p.set(x, 1, z, b)
        p.clear(x, 2, z, x, 4, z)

    # ── 분수 1단: 계단 고리(r5) → 수반 벽(r4) → 물(층 2) → 바닥(층 1: 짙은 프리즈머린 + 바닷속 등)
    for (x, z) in cells:
        dx, dz = x - c, z - c
        if _circle(dx, dz, 5) and not _circle(dx, dz, 4):
            f = ("west" if dx > 0 else "east") if abs(dx) > abs(dz) else ("north" if dz > 0 else "south")
            p.set(x, 2, z, stairs("prismarine_bricks", f))
        elif _circle(dx, dz, 4):
            ring = any(not _circle(dx + ex, dz + ez, 4) for ex, ez in DXZ.values())
            if ring:
                p.set(x, 2, z, B("quartz_bricks"))
                p.set(x, 1, z, B("stone_bricks"))
            elif max(abs(dx), abs(dz)) > 1:
                p.set(x, 2, z, B("water", level=0))
                p.set(x, 1, z, B("dark_prismarine"))
                p.clear(x, 3, z, x, 4, z)
    for dx, dz in ((3, 0), (-3, 0), (0, 3), (0, -3)):
        p.set(c + dx, 1, c + dz, B("sea_lantern"))
        p.light(c + dx, 1, c + dz)
    # 받침 (3×3, 물 안) + 가운데 기둥 → 얇은 접시(위 반블록) → 끌 석영 → 바다 등불 수정(십자) → 끝 막대
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            p.set(c + dx, 1, c + dz, B("dark_prismarine"))
            p.set(c + dx, 2, c + dz, stairs("prismarine_bricks", ("west" if dx > 0 else "east") if dx else
                                            ("north" if dz > 0 else "south"), "bottom") if (dx or dz) else B("chiseled_quartz_block"))
    for y in (3, 4):
        p.set(c, y, c, log("quartz_pillar"))
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx or dz:
                p.set(c + dx, 4, c + dz, slab("smooth_quartz", "top"))
    p.set(c, 5, c, B("chiseled_quartz_block"))
    p.set(c, 6, c, B("sea_lantern"))
    for d in ("north", "south", "east", "west"):
        dx, dz = DXZ[d]
        p.set(c + dx, 6, c + dz, B("light_blue_stained_glass"))
        p.set(c + dx, 7, c + dz, B("amethyst_cluster", facing="up"))
        p.set(c + dx, 5, c + dz, B("amethyst_cluster", facing="down"))
    p.set(c, 7, c, B("light_blue_stained_glass"))
    p.set(c, 8, c, B("light_blue_stained_glass"))
    p.set(c, 9, c, end_rod("up"))
    p.light(c, 6, c)
    # 물보라: 접시 테두리 밑 (떨어지는 물방울이 웅덩이로)
    for dx, dz in ((1, 1), (-1, -1)):
        p.ambient(c + dx, 3, c + dz, "fountain")

    # ── 가로등: 네 길 입구 양옆 8개 (구부러진 팔 끝에 청록 구리 등불, 팔은 길 쪽) + 사분면 화단 3개 (두 팔 큰 등)
    for s in (-3, 3):
        for (x, z, ax, az) in ((c + s, c - 9, -s // 3, 0), (c + s, c + 9, -s // 3, 0),
                               (c - 9, c + s, 0, -s // 3), (c + 9, c + s, 0, -s // 3)):
            p.set(x, 2, z, B("chiseled_stone_bricks"))
            p.set(x, 3, z, wall("stone_brick"))
            p.fill(x, 4, z, x, 6, z, fence("dark_oak"))
            p.set(x + ax, 6, z + az, fence("dark_oak"))
            p.set(x + ax, 5, z + az, B("waxed_oxidized_copper_lantern", hanging=True))
            p.set(x, 7, z, B("dark_oak_trapdoor", half="bottom", facing="north"))
            p.light(x + ax, 5, z + az)

    # ── 사분면: 벤치(r 6.5..7.5) + 화단(r 7.5..8.8) — 남동쪽은 게시판
    flowers = mix(("allium", 2), ("cornflower", 2), ("azure_bluet", 2), ("oxeye_daisy", 1), ("lily_of_the_valley", 1),
                  ("blue_orchid", 1), ("short_grass", 2), seed=7)
    for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        board = (sx, sz) == (1, 1)
        for (x, z) in cells:
            dx, dz = x - c, z - c
            if dx * sx < 3 or dz * sz < 3:
                continue
            d = math.hypot(dx, dz)
            if 6.5 <= d < 7.5 and not board:
                f = ("east" if dx > 0 else "west") if abs(dx) > abs(dz) else ("south" if dz > 0 else "north")
                p.set(x, 2, z, stairs("dark_oak", f))
            elif 7.5 <= d < 8.8:
                p.set(x, 1, z, B("grass_block"))
                p.set(x, 2, z, flowers)
        lx, lz = c + 6 * sx, c + 6 * sz
        if not board:
            p.set(lx, 1, lz, B("stone_bricks"))
            _lamp(p, lx, lz, 2, arms="x" if sx == sz else "z", post="spruce")
            p.tall_plant("lilac" if sx < 0 else "peony", c + 7 * sx, 2, c + 4 * sz)
            p.tall_plant("rose_bush" if sz < 0 else "lilac", c + 4 * sx, 2, c + 7 * sz)

    # ── 게시판 (남동쪽): 기둥 두 개 + 판자 + 작은 박공 지붕, 표지판은 서쪽(스폰 쪽)을 본다
    bx = c + 4
    for z in (c + 4, c + 8):
        p.set(bx, 1, z, B("stone_bricks"))
        p.fill(bx, 2, z, bx, 4, z, log("dark_oak"))
    for z in range(c + 5, c + 8):
        p.fill(bx, 3, z, bx, 4, z, B("spruce_planks"))
        p.set(bx, 2, z, trapdoor("spruce", "west", "top"))
    for z in range(c + 4, c + 9):
        p.set(bx - 1, 5, z, stairs("dark_oak", "east"))
        p.set(bx + 1, 5, z, stairs("dark_oak", "west"))
        p.set(bx, 5, z, B("dark_oak_planks"))
        p.set(bx, 6, z, slab("dark_oak"))
    for z in (c + 4, c + 8):
        p.set(bx - 1, 4, z, lantern(hanging=True))
        p.light(bx - 1, 4, z)
    p.sign(bx - 1, 4, c + 6, ["<gold><b>등불 어귀 마을</b></gold>", "<gray>미궁 라비린스 입구 마을</gray>"],
           wood="spruce", facing="west", glow=True)
    p.sign(bx - 1, 3, c + 5, ["<aqua>/미궁 메뉴</aqua>", "<gray>모든 기능 열기</gray>"], wood="spruce", facing="west", glow=True)
    p.sign(bx - 1, 3, c + 7, ["<aqua>/미궁 마을</aqua>", "<gray>이 광장으로</gray>", "<gray>돌아오기</gray>"],
           wood="spruce", facing="west", glow=True)
    # 뒷면 (동쪽): 길 안내
    p.sign(bx + 1, 4, c + 6, ["<light_purple>미궁의 아가리</light_purple>", "<gray>분수 건너 계단 위</gray>"],
           wood="spruce", facing="east", glow=True)
    p.sign(bx + 1, 3, c + 6, ["<aqua>/미궁 메뉴</aqua>"], wood="spruce", facing="east", glow=True)
    p.set(bx + 1, 2, c + 5, B("barrel", facing="up"))
    p.set(bx + 1, 3, c + 5, flower_pot("blue_orchid"))
    p.set(bx + 1, 2, c + 7, B("barrel", facing="up"))
    p.set(bx + 1, 3, c + 7, flower_pot("azure_bluet"))
    # 분수 테두리 화분 (대각선 네 곳)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.set(c + 3 * sx, 3, c + 3 * sz, flower_pot("blue_orchid" if sx == sz else "azure_bluet"))

    p.spawn(c, 2, c + 8, "front")
    return p


# ─────────────────────────────── 3. 전직의 전당 ───────────────────────────────

# 여섯 직업: (이름, 염료 색, 깃발 무늬) — 수호기사 하늘 / 광전사 빨강 / 사냥꾼 초록 / 비전술사 보라 / 사제 노랑 / 그림자 검정
CLASSES = (
    ("수호기사", "light_blue", [("cross", "white"), ("border", "blue"), ("circle", "light_blue")]),
    ("광전사", "red", [("stripe_downleft", "black"), ("stripe_downright", "black"), ("border", "orange")]),
    ("사냥꾼", "green", [("triangle_top", "lime"), ("stripe_center", "brown"), ("border", "lime")]),
    ("비전술사", "purple", [("rhombus", "magenta"), ("circle", "white"), ("border", "magenta")]),
    ("사제", "yellow", [("straight_cross", "white"), ("circle", "yellow"), ("border", "white")]),
    ("그림자", "black", [("triangles_bottom", "gray"), ("skull", "gray"), ("border", "gray")]),
)


def class_hall():
    """탑이 있는 전당. 정면 가운데 종탑(출입구, 꼭대기 푸른 첨탑 + 금 꼭지) 뒤로 본당.
    본당은 바닥이 땅보다 한 칸 높고(층 2), 앞 계단으로 오른다. 정면 양 날개벽에 여섯 직업 깃발.
    안: 안쪽 단 위에 전직 교관, 앞 교탁(독서대 + 제단 두 개) = interact class, 양옆 벽에 직업 색 받침대 6개."""
    W, H, D = 15, 26, 15
    # anchor = 앞 계단 줄 가운데: 바깥 땅과 같은 층이고 위 두 칸이 트여 있어야 selftest blocked_doors 를 통과 (반블록 계단은 통과)
    p = Piece("class_hall", "전직의 전당", W, H, D, floor_y=1, anchor=(7, 0),
              foundation_mix=[("stone_bricks", 4), ("mossy_stone_bricks", 1), ("cracked_stone_bricks", 1), ("andesite", 1)])
    base = mix(("stone_bricks", 4), ("mossy_stone_bricks", 1), ("cracked_stone_bricks", 1), seed=11)
    white = mix(("calcite", 3), ("smooth_quartz", 2), ("quartz_bricks", 1), seed=12)
    pil = log("quartz_pillar")
    lapis, gold = B("lapis_block"), B("gold_block")
    roof = "blue_concrete"

    # ── 바닥: 층 0 기초(땅속) · 층 1 받침(땅 높이) · 층 2 마루 (본당 x 1..13 z 5..13, 탑 x 5..9 z 1..5, 계단 z 0)
    def box(x0, z0, x1, z1):
        return [(x, z) for z in range(z0, z1 + 1) for x in range(x0, x1 + 1)]
    hall = box(1, 5, 13, 13)
    tower = box(5, 1, 9, 5)
    for (x, z) in set(hall) | set(tower):
        p.set(x, 0, z, base)
        p.set(x, 1, z, base)
        p.set(x, 2, z, base)
    # 마루 무늬: 석영 + 청금석 마름모, 가운데 파란 양탄자 길
    for (x, z) in box(2, 6, 12, 12) + box(6, 2, 8, 4):
        d = abs(x - 7) + abs(z - 9)
        p.set(x, 2, z, lapis if d == 3 else (B("smooth_quartz") if (x + z) % 2 else B("polished_diorite")))
    # 앞 디딤단 (z=0, 반블록 — 땅 → 반 칸 → 마루) + 양끝 난간 기둥 위 등불
    for x in range(5, 10):
        p.set(x, 1, 0, base)
        p.set(x, 2, 0, slab("stone_brick", "bottom"))
        p.clear(x, 3, 0, x, 4, 0)
    for x in (4, 10):
        p.set(x, 1, 0, base)
        p.set(x, 2, 0, B("chiseled_stone_bricks"))
        p.set(x, 3, 0, lantern(hanging=False))
        p.light(x, 3, 0)

    # ── 본당 벽 (층 3..8): 석영 기둥 + 흰 벽, 꼭대기 청금석 띠(층 8), 기둥머리 금
    p.clear(2, 3, 6, 12, 8, 12)
    walls = [((1, 5), (1, 13)), ((13, 5), (13, 13)), ((1, 13), (13, 13)), ((1, 5), (4, 5)), ((10, 5), (13, 5))]
    for (x0, z0), (x1, z1) in walls:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(3, 8):
                    p.set(x, y, z, white)
                p.set(x, 8, z, lapis)
    posts = [(1, 5), (1, 9), (1, 13), (13, 5), (13, 9), (13, 13), (4, 13), (10, 13), (4, 5), (10, 5)]
    for (x, z) in posts:
        p.fill(x, 3, z, x, 7, z, pil)
        p.set(x, 8, z, gold)
    # 옆벽 아치 창 (z 6..8, 10..12 — 3칸 폭, 층 4..7) 파란/하늘색 색유리
    for x, f in ((1, "west"), (13, "east")):
        for z0 in (6, 10):
            p.arch(z0, z0 + 2, 4, 4, x, x, mat="smooth_quartz", axis="z", style="round")
            for z in range(z0, z0 + 3):
                for y in range(4, 8):
                    if p.get(x, y, z) == ".":
                        p.set(x, y, z, pane("blue" if z == z0 + 1 else "light_blue"))
                ox = -1 if f == "west" else 1
                p.set(x + ox, 3, z, stairs("smooth_quartz", "east" if f == "west" else "west", "top"))
    # 뒷벽 둥근 장미창 (x 5..9, 층 4..8 — 가운데 금)
    for x in range(5, 10):
        for y in range(4, 9):
            d = math.hypot(x - 7, y - 6)
            if d <= 2.3:
                p.set(x, y, 13, pane("yellow" if d < 0.5 else ("light_blue" if d < 1.5 else "blue")))
    # 정면 날개벽 (x 1..4 / 10..13, z=5): 작은 창 + 여섯 직업 깃발 (층 7, 앞 z=4 에 걸림)
    for x in (2, 3, 11, 12):
        p.set(x, 4, 5, pane("light_blue"))
        p.set(x, 5, 5, pane("light_blue"))
    for i, (name, color, pats) in enumerate(CLASSES):
        x = (2, 3, 4, 10, 11, 12)[i]
        p.banner(x, 7, 4, color, pats, facing="north")
    # 버팀벽 (옆 x 0/14 의 z 9, 뒤 z 14 의 x 4/10): 위에 등불
    for (x, z) in ((0, 9), (14, 9), (4, 14), (10, 14)):
        p.fill(x, 0, z, x, 5, z, base)
        p.set(x, 6, z, B("chiseled_stone_bricks"))
        p.set(x, 7, z, lantern(hanging=False))
        p.light(x, 7, z)

    # ── 지붕: 파란 콘크리트 박공 (용마루 x 방향), 박공벽 = 흰 벽 + 둥근 창
    p.gable_roof(1, 5, 13, 13, 9, roof, axis="x", overhang=1, end_overhang=1, under="stairs", gable=white,
                 ridge=slab("smooth_quartz"))
    for x in (1, 13):                                   # 박공벽 둥근 창 (3×3, 가운데 노랑)
        for z in (8, 9, 10):
            for y in (10, 11, 12):
                if (z == 9) or (y == 11):
                    p.set(x, y, z, pane("yellow" if (z, y) == (9, 11) else "light_blue"))
    for (x, z) in ((1, 5), (13, 5), (1, 13), (13, 13)):  # 네 모서리 기둥이 처마를 뚫고 올라간 작은 첨탑
        for y in (9, 10, 11):
            p.set(x, y, z, pil)
        p.set(x, 12, z, gold)
        p.set(x, 13, z, end_rod("up"))
    for (x, z) in ((0, 4), (14, 4), (0, 14), (14, 14)):
        p.set(x, 8, z, lantern(hanging=True))
        p.light(x, 8, z)

    # ── 종탑 (x 5..9, z 1..5): 층 2..15 벽, 1층 현관(층 3..8), 종실(층 13..15), 꼭대기 첨탑
    for x in range(5, 10):
        for z in range(1, 6):
            edge = x in (5, 9) or z in (1, 5)
            for y in range(3, 16):
                p.set(x, y, z, white if edge else ".")
    for (x, z) in ((5, 1), (9, 1), (5, 5), (9, 5)):
        p.fill(x, 2, z, x, 16, z, pil)
    for x in range(5, 10):
        for z in range(1, 6):
            if x in (5, 9) or z in (1, 5):
                if p.get(x, 8, z) != pil:
                    p.set(x, 8, z, lapis)
    p.fill(6, 9, 2, 8, 9, 4, B("spruce_planks"))           # 현관 천장
    p.fill(6, 12, 2, 8, 12, 4, B("spruce_planks"))          # 종실 바닥
    p.fill(6, 16, 2, 8, 16, 4, white)                       # 종실 천장
    # 정문·안문 아치 (3칸 폭, 층 3..6) — 금 쐐기돌
    for z in (1, 5):
        p.arch(6, 8, 3, 4, z, z, mat="quartz", axis="x", style="round", frame=B("chiseled_quartz_block"))
        p.set(7, 7, z, gold)
    p.set(7, 8, 3, lantern(hanging=True))
    p.light(7, 8, 3)
    # 종실 아치 창 (네 면, 층 13..15) + 종
    for z in (1, 5):
        p.arch(6, 8, 13, 3, z, z, mat="quartz", axis="x", style="round")
    for x in (5, 9):
        p.arch(2, 4, 13, 3, x, x, mat="quartz", axis="z", style="round")
    p.set(7, 15, 3, B("bell", attachment="ceiling", facing="north"))
    p.set(6, 13, 2, lantern(hanging=False))
    p.set(8, 13, 4, lantern(hanging=False))
    p.light(6, 13, 2)
    # 꼭대기: 처마가 탑 밖으로 한 칸 나온 둥근 첨탑 (속은 꽉 채움 — 빈 어둠 칸 없게), 끝 = 금 띠 + 끝 막대
    top = p.spire(7, 3, 16, 3, 7, roof, round=True, hollow=False)
    p.set(7, top, 3, gold)
    p.set(7, top + 1, 3, end_rod("up"))
    for (x, z) in ((5, 1), (9, 1), (5, 5), (9, 5)):          # 탑 모서리 기둥머리 금
        p.set(x, 15, z, gold)
    for (x, z) in ((7, 0), (4, 3), (10, 3)):                 # 첨탑 처마 밑 매단 등불 (처마 블록에 매달림)
        p.set(x, 15, z, lantern(hanging=True))
        p.light(x, 15, z)
    # 탑 몸통 창: 네 면 층 10..11 좁은 창 (하늘색)
    for z in (1,):
        p.set(7, 10, z, pane("light_blue"))
        p.set(7, 11, z, pane("light_blue"))
    for x in (5, 9):
        p.set(x, 10, 3, pane("light_blue"))
        p.set(x, 11, 3, pane("light_blue"))
    p.set(6, 10, 2, lantern(hanging=False))
    p.light(6, 10, 2)

    # ── 실내: 단(z 10..12), 교관, 교탁, 직업 받침대, 샹들리에
    for x in range(4, 11):
        p.set(x, 3, 10, stairs("smooth_quartz", "south"))
        for z in (11, 12):
            p.set(x, 3, z, B("smooth_quartz"))
    p.set(7, 3, 11, lapis)
    p.npc("class_master", 7, 4, 11, "front")
    for x in (5, 9):
        p.set(x, 4, 12, B("chiseled_quartz_block"))
        p.set(x, 5, 12, candle("yellow", 3))
        p.light(x, 5, 12)
    p.set(7, 3, 9, B("lectern", facing="north"))
    for x in (6, 8):
        p.set(x, 3, 9, B("chiseled_quartz_block"))
        p.set(x, 4, 9, candle("white", 2))
    p.interact("class", [(7, 3, 9), (6, 3, 9), (8, 3, 9)])
    for i, (name, color, pats) in enumerate(CLASSES):
        x, z = ((2, 7), (2, 9), (2, 11), (12, 7), (12, 9), (12, 11))[i]
        p.set(x, 3, z, B(color + "_glazed_terracotta", facing="north"))
        p.set(x, 4, z, candle(color, 3))
    for z in range(2, 9):
        p.set(7, 3, z, B("blue_carpet"))
    for z in (6, 7):                                    # 의자 두 줄 (등받이 북쪽 → 앉으면 단을 본다), 끝은 다락문 팔걸이
        for x0 in (3, 9):
            for x in range(x0, x0 + 3):
                p.set(x, 3, z, stairs("spruce", "north"))
            # 통로 쪽 팔걸이: 열린 다락문 판은 facing 반대 면에 붙으므로 의자 쪽 면에 오게
            p.set(x0 - 1 if x0 == 9 else x0 + 3, 3, z, trapdoor("spruce", "east" if x0 == 3 else "west", open=True))
    for x in (4, 7, 10):                                # 샹들리에: 용마루 밑에서 쇠사슬로 층 8 까지
        for y in range(9, 13):
            p.set(x, y, 9, chain())
        p.set(x, 8, 9, lantern(hanging=True))
        p.light(x, 8, 9)
    return p


# ─────────────────────────────── 4. 기록 보관소 ───────────────────────────────

def archive():
    """팔각 서고. 짙은 참나무 뼈대 + 흰 회벽, 진홍 고리 지붕 위에 갈비뼈 있는 보라 유리 돔(천창) + 자수정 꼭지.
    앞(북) 작은 현관. 안: 대각선 벽마다 책장(촛불), 가운데 독서대 3개(interact titles) 뒤에 칭호 관리인,
    돔 꼭대기에서 내려온 샹들리에."""
    W, H, D = 13, 18, 14
    cx, cz = 6, 7
    p = Piece("archive", "기록 보관소", W, H, D, floor_y=1, anchor=(6, 3),
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 1), ("cobbled_deepslate", 1), ("andesite", 1)])
    base = mix(("polished_deepslate", 3), ("deepslate_bricks", 2), ("cobbled_deepslate", 1), seed=21)
    infill = mix(("calcite", 3), ("white_terracotta", 1), seed=22)
    frame = log("dark_oak")
    TOP = 8                                             # 벽 꼭대기 층

    def octa(dx, dz, r):
        return abs(dx) <= r and abs(dz) <= r and abs(dx) + abs(dz) <= r + 2

    inside = {(x, z) for z in range(D) for x in range(W) if octa(x - cx, z - cz, 5)}
    ring = {(x, z) for (x, z) in inside
            if any((x + ex, z + ez) not in inside for ex in (-1, 0, 1) for ez in (-1, 0, 1))}
    room = inside - ring
    verts = {(4, 2), (8, 2), (1, 5), (11, 5), (1, 9), (11, 9), (4, 12), (8, 12)}

    # ── 바닥 (층 0 기초 · 층 1 마루: 짙은 참나무 + 가운데 자수정·보라 고리)
    for (x, z) in inside:
        p.set(x, 0, z, base)
        p.set(x, 1, z, base if (x, z) in ring else B("dark_oak_planks"))
    for (x, z) in room:
        d = math.hypot(x - cx, z - cz)
        if 1.5 <= d <= 2.5:
            p.set(x, 1, z, B("purpur_block") if (x + z) % 2 else B("amethyst_block"))
    # ── 벽 (층 2 받침돌 · 3..TOP 뼈대 벽: 모서리 기둥, 층 5 가로보, 꼭대기 가로보)
    for (x, z) in ring:
        p.set(x, 2, z, base)
        for y in range(3, TOP + 1):
            if (x, z) in verts:
                b = frame
            elif y in (5, TOP):
                b = B("stripped_dark_oak_wood")
            else:
                b = infill
            p.set(x, y, z, b)
    for (x, z) in room:
        p.clear(x, 2, z, x, TOP, z)
    # 창: 동·서·남 곧은 면 가운데 높은 창 (층 3..7, 위 자홍) + 창턱 화분 (대각선 면은 안쪽이 책장이라 창 없음)
    for (x, z, f) in ((11, 7, "east"), (1, 7, "west"), (6, 12, "south")):
        for y in range(3, 8):
            p.set(x, y, z, pane("magenta" if y == 7 else "purple"))
        ox, oz = DXZ[f]
        p.set(x + ox, 2, z + oz, stairs("dark_oak", opposite(f), "top"))
        p.set(x + ox, 3, z + oz, flower_pot("allium"))
    # ── 처마 띠 (층 TOP+1): 바깥으로 한 칸 나온 뒤집힌 계단, 그 위 벽 줄에 진홍 고리 지붕 한 단 → 유리 돔
    E = TOP + 1
    outer = {(x, z) for z in range(D) for x in range(W) if octa(x - cx, z - cz, 6) and not octa(x - cx, z - cz, 5)}
    for (x, z) in outer:
        p.set(x, E, z, stairs("dark_oak", opposite(_face_in(x - cx, z - cz)), "top"))
    for (x, z) in ring:
        p.set(x, E, z, B("crimson_planks"))
        p.set(x, E + 1, z, stairs("crimson", _face_in(x - cx, z - cz)))
    for (x, z) in room:
        p.set(x, E, z, ".")
    # ── 돔 (반구, 밑 반지름 4.3): 갈비뼈 = 8 방향 짙은 참나무, 나머지 보라·자홍 유리
    y0, R = E + 1, 4.3
    def in_dome(x, z, y):                               # 세로로 조금 늘린 반구 (꼭대기가 납작하지 않게)
        if y < y0:
            return False
        rr = R * R - ((y - y0 + 0.3) * 0.75) ** 2
        return rr > 0 and (x - cx) ** 2 + (z - cz) ** 2 <= rr + 0.5
    for y in range(y0, H - 2):
        for z in range(D):
            for x in range(W):
                if not in_dome(x, z, y) or p.get(x, y, z) not in (" ", "."):
                    continue
                dx, dz = x - cx, z - cz
                shell = (not in_dome(x, z, y + 1)) or any(not in_dome(x + ex, z + ez, y) for ex, ez in DXZ.values())
                if not shell:
                    p.set(x, y, z, ".")
                elif (dx == 0 or dz == 0 or abs(dx) == abs(dz)) and dx * dx + dz * dz > 2:
                    p.set(x, y, z, B("dark_oak_planks"))
                else:
                    p.set(x, y, z, glass("purple") if (x + y + z) % 3 else glass("magenta"))
    apex = max(y for y in range(H) if p.get(cx, y, cz) not in (" ", "."))
    p.set(cx, apex, cz, B("amethyst_block"))
    p.set(cx, apex + 1, cz, B("chiseled_deepslate"))
    p.set(cx, apex + 2, cz, B("amethyst_cluster", facing="up"))

    # ── 현관 (z 0..1, x 4..8): 기둥 두 개 + 작은 진홍 박공 지붕, 문 + 간판 + 매단 등불
    for x in range(4, 9):
        for z in (0, 1):
            p.set(x, 0, z, base)
            p.set(x, 1, z, B("polished_deepslate") if x in (4, 8) else B("dark_oak_planks"))
            if x not in (4, 8):
                p.clear(x, 2, z, x, 4, z)
    for x in (4, 8):
        p.fill(x, 2, 0, x, 4, 0, log("dark_oak"))
        p.set(x, 2, 1, fence("dark_oak"))
        p.set(x, 3, 1, fence("dark_oak"))
        p.set(x, 4, 1, log("dark_oak", "z"))
    p.gable_roof(4, 0, 8, 1, 5, "crimson", axis="z", overhang=0, end_overhang=0, under=None,
                 gable=B("dark_oak_planks"), hollow=False)
    p.door("dark_oak", 6, 2, 2, "north")
    p.clear(6, 2, 3, 6, 3, 3)
    p.sign(6, 4, 1, ["<light_purple><b>기록 보관소</b></light_purple>", "<gray>칭호와 기록</gray>"],
           wood="dark_oak", facing="north", glow=True)
    for x in (5, 7):
        p.set(x, 4, 0, lantern(hanging=True))
        p.light(x, 4, 0)
    for x in (3, 9):                                   # 현관 양옆 보라 깃발 (앞 대각선 벽에 걸림)
        p.banner(x, 6, 2, "purple", [("flower", "magenta"), ("stripe_bottom", "black"), ("border", "black")],
                 facing="north")

    # ── 안: 대각선 벽 안쪽 책장 (층 2..4, 위 촛불), 가운데 독서대, 관리인, 마법 탁자, 샹들리에
    for (x, z) in room:
        dx, dz = x - cx, z - cz
        near_wall = any((x + ex, z + ez) in ring for ex, ez in DXZ.values())
        if near_wall and abs(dx) >= 2 and abs(dz) >= 2:
            for y in (2, 3, 4):
                p.set(x, y, z, B("bookshelf") if (x + y + z) % 3 else
                      B("chiseled_bookshelf", facing=_face_in(dx, dz), slot_0_occupied=True, slot_2_occupied=True,
                        slot_4_occupied=True))
            p.set(x, 5, z, candle("purple" if (x + z) % 2 else "white", 3 + (x + z) % 2))
    p.set(cx, 2, cz - 1, B("lectern", facing="north", has_book=True))
    for x in (cx - 1, cx + 1):
        p.set(x, 2, cz - 1, B("lectern", facing="north", has_book=True))
    p.interact("titles", [(cx - 1, 2, cz - 1), (cx, 2, cz - 1), (cx + 1, 2, cz - 1)])
    p.npc("title_keeper", cx, 2, cz + 1, "front")
    p.ambient(cx, 4, cz - 1, "magic")
    for (x, z) in ((cx - 2, cz + 3), (cx + 2, cz + 3)):
        p.set(x, 2, z, B("enchanting_table"))
    for (x, z) in ((cx - 3, cz), (cx + 3, cz), (cx, cz + 4)):     # 촛대 (울타리 위 촛불) — 창 옆
        p.set(x, 2, z, fence("dark_oak"))
        p.set(x, 3, z, candle("white", 3))
    for (x, z) in ((cx - 1, cz + 1), (cx + 1, cz + 1), (cx, cz + 2)):
        p.set(x, 2, z, B("purple_carpet"))
    for y in range(E, apex):                            # 샹들리에: 돔 꼭대기 → 쇠사슬 → 등불
        p.set(cx, y, cz, chain())
    p.set(cx, E - 1, cz, lantern(hanging=True))
    p.light(cx, E - 1, cz)
    for dx in (-2, 2):                                  # 둘레 작은 샹들리에 넷: 돔 껍질에서 쇠사슬로 내려온 등불
        for dz in (-2, 2):
            x, z = cx + dx, cz + dz
            shell = min(y for y in range(E, H) if p.get(x, y, z) not in (" ", "."))
            for y in range(E, shell):
                p.set(x, y, z, chain())
            p.set(x, E - 1, z, lantern(hanging=True))
            p.light(x, E - 1, z)
    # 바깥 등불: 벽에서 나온 울타리 받침 밑에 매단다 (대각선 네 면 + 뒤) — 뒤집힌 계단 밑은 가운데가 비어 못 매닮
    for (x, z) in ((cx - 4, cz - 4), (cx + 4, cz - 4), (cx - 4, cz + 4), (cx + 4, cz + 4), (cx, cz + 6)):
        p.set(x, E - 1, z, fence("dark_oak"))
        p.set(x, E - 2, z, lantern(hanging=True))
        p.light(x, E - 2, z)
    return p


PIECES = [labyrinth_gate, plaza, class_hall, archive]
