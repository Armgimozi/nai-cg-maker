"""마을 거리 조각 — 대장간 · 떠돌이 상점 · 여관 · 마을집 셋 · 장식 (VILLAGE.md §5 3·6·7·8·9).

정방향: 정면(문)은 z=0 쪽, 북쪽을 본다. x 증가 = 동쪽. floor_y 층이 바닥(사람은 floor_y+1 에 섬), 그 아래는 땅속 기초.
지형 존중(§0): 실제로 쓰는 기둥만 칠하고 윤곽 밖(처마 밑 가장자리·마당 귀퉁이)은 ' ' 로 남겨 원래 땅이 그대로 이어지게 한다.
건물 밑 땅속 한 층(층 0)은 기초 돌 — 경사진 단 가장자리에서 드러나도 맨흙이 아니게.
장식(가로등·벤치·나무 …)은 floor_y=0: 층 0 이 땅 맨 윗블록 자리(받침돌·뿌리)이고 그 위로 선다.
"""
import random

from vlib import (Piece, mix, stairs, slab, log, leaves, wall, fence, pane, bars, trapdoor, lantern, candle, chain, campfire,
                  flower_pot, B, DXZ, parse_block, format_block)


# ─────────────────────────────── 공통 도우미 ───────────────────────────────

def _hang(p, x, y, z, chain_n=0, soul=False, kind=None):
    """(x, y, z) 에 매단 등불 + 그 위로 쇠사슬 chain_n 칸. 맨 위 사슬 위 칸(받침)은 부르는 쪽이 둔다."""
    for i in range(chain_n):
        p.set(x, y + 1 + i, z, chain())
    p.set(x, y, z, lantern(soul=soul, hanging=True, kind=kind))
    p.light(x, y, z)


def _corbel_lamp(p, x, y, z, wall_dir, mat="dark_oak", kind=None):
    """벽에 붙은 받침(뒤집힌 계단, 등판이 벽 쪽) 위에 선 등불. wall_dir = 받침에서 본 벽 방향."""
    p.set(x, y, z, stairs(mat, wall_dir, "top"))
    p.set(x, y + 1, z, lantern(hanging=False, kind=kind))
    p.light(x, y + 1, z)


def _vary(p, base_id, choices, seed=0):
    """모양 상태(facing·half 등)는 그대로 두고 블록 id 만 무게대로 섞기 — 넓은 지붕면·벽면에 결을 준다.
    choices = [(id, 무게), ...] (같은 종류 블록: 계단은 계단끼리)."""
    m = mix(*choices, seed=seed)
    pre = "minecraft:" + base_id
    for y in range(p.H):
        for z in range(p.D):
            for x in range(p.W):
                v = p.g[y][z][x]
                if v == pre or v.startswith(pre + "["):
                    _, props = parse_block(v)
                    p.set(x, y, z, format_block(parse_block(m.pick(x, y, z, p._salt))[0], props))


def _trim(p, cells, old_ids, new_of):
    """지붕 테두리(처마 줄·박공 끝) 칸의 블록 id 를 바꾸기. new_of = {옛 id: 새 id}."""
    for (x, y, z) in cells:
        if not p.inside(x, y, z):
            continue
        v = p.g[y][z][x]
        if v in (" ", "."):
            continue
        bid, props = parse_block(v)
        if bid in old_ids:
            p.set(x, y, z, format_block(new_of[bid], props))


def _gable_edges(axis, x0, z0, x1, z1, y, overhang=1, end_overhang=1, H=40):
    """gable_roof 의 처마 줄(맨 아래)과 박공 끝(맨 앞·뒤 줄) 칸 — _trim 에 넘긴다."""
    if axis == "x":
        a_lo, a_hi, c_lo, c_hi = x0 - end_overhang, x1 + end_overhang, z0 - overhang, z1 + overhang
        at = lambda a, yy, c: (a, yy, c)
    else:
        a_lo, a_hi, c_lo, c_hi = z0 - end_overhang, z1 + end_overhang, x0 - overhang, x1 + overhang
        at = lambda a, yy, c: (c, yy, a)
    out = [at(a, y, c) for a in range(a_lo, a_hi + 1) for c in (c_lo, c_hi)]
    out += [at(a, yy, c) for a in (a_lo, a_hi) for yy in range(y, y + H) for c in range(c_lo, c_hi + 1)]
    return out


def _stripe(p, x0, y0, z0, x1, y1, z1, a, b, by="x"):
    """상자 안 양털(블록·계단·반블록)을 줄무늬로: by 축 좌표가 짝수면 a 색, 홀수면 b 색 (천막 줄무늬)."""
    for y in range(y0, y1 + 1):
        for z in range(z0, z1 + 1):
            for x in range(x0, x1 + 1):
                v = p.get(x, y, z)
                if v in (" ", ".") or "_wool" not in v:
                    continue
                bid, props = parse_block(v)
                col = a if (x if by == "x" else z) % 2 == 0 else b
                for c in ("white", "red", "yellow", "blue", "lime", "green", "orange", "cyan", "purple", "light_blue"):
                    if bid.startswith(c + "_wool"):
                        p.set(x, y, z, format_block(col + bid[len(c):], props))
                        break


def _seal(p):
    """바닥 위 ' ' 칸 중 조각 바깥과 이어지지 않은 칸(지붕 골·다락 속)을 '.' 로 — 닫힌 속에 언덕 흙이 남지 않게 (§2.2)."""
    W, H, D, g = p.W, p.H, p.D, p.g
    y0 = p.floor_y + 1
    seen, stack = set(), []
    for y in range(y0, H):
        for z in range(D):
            for x in range(W):
                if (x in (0, W - 1) or z in (0, D - 1) or y == H - 1) and g[y][z][x] in (" ", "."):
                    seen.add((x, y, z))
                    stack.append((x, y, z))
    while stack:
        x, y, z = stack.pop()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + dx, y + dy, z + dz)
            if n not in seen and 0 <= n[0] < W and y0 <= n[1] < H and 0 <= n[2] < D and g[n[1]][n[2]][n[0]] in (" ", "."):
                seen.add(n)
                stack.append(n)
    for y in range(y0, H):
        for z in range(D):
            for x in range(W):
                if g[y][z][x] == " " and (x, y, z) not in seen:
                    p.set(x, y, z, ".")


def _cross_roof(p, cx, hw, z_front, y, z_back, mat, ridge_mat, base_mat):
    """앞으로 튀어나온 작은 박공(골 지붕) — 용마루 z 방향, 가운데 x=cx, 처마 폭 반 hw (처마 x = cx±hw).
    줄 k (높이 y+k) 는 z_front 부터 z_back(k) 까지 (본채 지붕 경사에 닿는 데까지). 맨 위는 ridge_mat 반블록."""
    k = 0
    while hw - k >= 0:
        yy = y + k
        lo, hi = cx - hw + k, cx + hw - k
        for z in range(z_front, z_back(k) + 1):
            if lo < hi:
                p.set(lo, yy, z, stairs(mat, "east"))
                p.set(hi, yy, z, stairs(mat, "west"))
                if k > 0:
                    p.set(lo, yy - 1, z, stairs(mat, "west", "top"))
                    p.set(hi, yy - 1, z, stairs(mat, "east", "top"))
            else:
                if k > 0:
                    p.set(lo, yy - 1, z, base_mat)
                p.set(lo, yy, z, ridge_mat)
        k += 1


def _cone(p, cx, cz, levels, mat, block, tip=None):
    """둥근 뾰족 지붕(마녀 모자). levels = [(y, 반지름), ...] 아래에서 위로. 줄마다 그 원판에서 다음 줄 원판을 뺀 고리 =
    계단(등판이 가운데 쪽), 다음 줄 원판의 테두리 = block, 그 안 = '.'. 반지름이 같은 두 줄은 곧은 띠가 된다."""
    def inside(dx, dz, r):
        return r >= 0 and dx * dx + dz * dz <= r * r + r
    for i, (y, r) in enumerate(levels):
        rn = levels[i + 1][1] if i + 1 < len(levels) else -1
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if not inside(dx, dz, r):
                    continue
                x, z = cx + dx, cz + dz
                if not inside(dx, dz, rn):
                    if dx == 0 and dz == 0:
                        p.set(x, y, z, block)
                    elif abs(dx) >= abs(dz):
                        p.set(x, y, z, stairs(mat, "west" if dx > 0 else "east"))
                    else:
                        p.set(x, y, z, stairs(mat, "north" if dz > 0 else "south"))
                elif all(inside(dx + ex, dz + ez, rn) for ex, ez in DXZ.values()):
                    p.set(x, y, z, ".")
                else:
                    p.set(x, y, z, block)
    if tip:
        p.set(cx, levels[-1][0] + 1, cz, tip)


def _plant(p, x, y, z, block, tall=False):
    """땅 위 풀꽃 + 바로 밑 칸 잔디 — 다듬은 단의 맨 윗블록이 모래·눈이어도 꽃이 떨어지지 않게."""
    p.set(x, y - 1, z, B("grass_block"))
    if tall:
        p.tall_plant(block, x, y, z)
    else:
        p.set(x, y, z, block)


def _ring_box(x0, z0, x1, z1):
    """상자 테두리 칸들 (x, z)."""
    return [(x, z) for z in range(z0, z1 + 1) for x in range(x0, x1 + 1) if x in (x0, x1) or z in (z0, z1)]


# ─────────────────────────────── 3. 두르간의 대장간 ───────────────────────────────

_TILE_MIX = [("deepslate_tile_stairs", 5), ("deepslate_brick_stairs", 2), ("cobbled_deepslate_stairs", 1),
             ("polished_deepslate_stairs", 1)]
_COPPER = {"deepslate_tile_stairs": "waxed_cut_copper_stairs", "deepslate_tile_slab": "waxed_cut_copper_slab"}


def forge():
    """돌 아래층 + 앞으로 내민 원목 2층(짙은 기와 박공, 구리 테두리·용마루, 서쪽 지붕창)의 대장장이 집(서쪽)과,
    앞·옆이 트인 작업장(동쪽, 낮은 박공)을 나란히. 작업장 뒤 구석에서 검은 굴뚝(주황 띠)이 가장 높이 솟고
    꼭대기 모닥불이 연기를 피운다. 굴뚝 앞면이 화덕: 용암 가마솥 + 용광로, 그 위 돌 갓.
    작업장 안: 모루·대장장이 작업대(interact), 숫돌, 담금질 가마솥, 연장 선반, 대장장이 두르간."""
    W, H, D, F = 15, 15, 11, 1
    p = Piece("forge", "두르간의 대장간", W, H, D, floor_y=F, anchor=(11, 1),
              foundation_mix=[("cobbled_deepslate", 3), ("polished_blackstone_bricks", 2), ("tuff_bricks", 1),
                              ("mossy_cobblestone", 1)])
    stone = mix(("cobbled_deepslate", 4), ("polished_blackstone_bricks", 3), ("cracked_polished_blackstone_bricks", 1),
                ("tuff_bricks", 1), seed=21)
    pave = mix(("polished_blackstone_bricks", 3), ("cobbled_deepslate", 2), ("tuff_bricks", 1), ("polished_tuff", 1),
               seed=22)
    plaster = mix(("white_terracotta", 3), ("calcite", 1), seed=23)
    ember = mix(("orange_terracotta", 4), ("terracotta", 1), seed=24)
    cstone = mix(("polished_blackstone_bricks", 4), ("cracked_polished_blackstone_bricks", 1), ("blackstone", 1), seed=25)
    frame, roof = "dark_oak_log", "deepslate_tile"
    quoin, resin = B("polished_blackstone"), B("resin_bricks")
    ridge = slab("waxed_cut_copper")
    glass = "orange_stained_glass_pane"

    # ── 집 (x 1..7): 아래층 z 2..9 돌(y 2..4), 2층(y 6..8)은 앞으로 한 칸 내밀어 z 1..9
    p.fill(1, 0, 2, 7, 1, 9, stone)                                       # 기초 + 바닥 둘레
    p.fill(2, 1, 3, 6, 1, 8, mix(("spruce_planks", 4), ("stripped_spruce_wood", 1), seed=26))
    for (x, z) in _ring_box(1, 2, 7, 9):
        p.fill(x, 2, z, x, 4, z, stone)
    for (x, z) in ((1, 2), (7, 2), (1, 9), (7, 9)):                      # 모서리 돌 띠
        p.fill(x, 1, z, x, 4, z, quoin)
    p.clear(2, 2, 3, 6, 4, 8)
    # 2층 바닥 띠 (y=5): 둘레 가로보 + 내민 들보(z=1) + 들보 밑 모서리 받침
    for x in range(1, 8):
        p.set(x, 5, 1, log(frame, "x"))
        p.set(x, 5, 9, log(frame, "x"))
    for z in range(2, 9):
        p.set(1, 5, z, log(frame, "z"))
        p.set(7, 5, z, log(frame, "z"))
    p.fill(2, 5, 2, 6, 5, 8, B("spruce_planks"))
    for x in (1, 7):
        p.set(x, 4, 1, stairs("dark_oak", "south", "top"))
    # 2층 원목 뼈대 벽 (y 6..8, 꼭대기 y=8 은 도리)
    for (x0, z0, x1, z1) in ((1, 1, 7, 1), (1, 9, 7, 9), (1, 1, 1, 9), (7, 1, 7, 9)):
        p.timber_wall(x0, 6, z0, x1, 8, z1, frame=frame, infill=plaster, post_every=3, beams=False, mid_beam=8)
    p.clear(2, 6, 2, 6, 8, 8)
    # 지붕: 용마루 z 방향 → 박공이 앞·뒤. 박공 삼각형 = 주황 테라코타 + 가로보·왕기둥·둥근 창
    p.gable_roof(1, 1, 7, 9, 9, roof, axis="z", overhang=1, end_overhang=1, gable=ember, ridge=ridge)
    _trim(p, _gable_edges("z", 1, 1, 7, 9, 9), _COPPER, _COPPER)
    for z in (1, 9):
        for x in range(2, 7):
            p.set(x, 9, z, log(frame, "x"))
        p.set(4, 11, z, log(frame))
        p.set(4, 10, z, pane("orange"))
    # 서쪽 지붕창 (z 4..6): 창 + 작은 박공
    p.set(1, 10, 4, log(frame))
    p.set(1, 10, 6, log(frame))
    p.set(1, 10, 5, pane("orange"))
    p.set(2, 10, 5, ".")
    for x in (0, 1, 2):
        p.set(x, 11, 4, stairs(roof, "south"))
        p.set(x, 11, 5, B("deepslate_tiles"))
        p.set(x, 11, 6, stairs(roof, "north"))
        p.set(x, 12, 5, slab("deepslate_tile"))
    p.set(0, 10, 4, stairs(roof, "north", "top"))
    p.set(0, 10, 6, stairs(roof, "south", "top"))

    # 정면 (z=2 아래층, z=1 2층)
    p.door("dark_oak", 4, 2, 2, "north")
    p.set(4, 4, 2, B("chiseled_polished_blackstone"))
    for x in (2, 6):
        p.window(x, 3, 2, "north", glass=glass, sill=stairs("polished_blackstone", "south", "top"))
        p.window(x, 6, 1, "north", glass=glass, shutter="acacia")
    p.fill(2, 1, 1, 6, 1, 1, pave)                                      # 문 앞 돌판 (내민 2층 밑)
    p.fill(3, 1, 0, 5, 1, 0, pave)
    for x in (3, 5):                                                    # 내민 들보 밑 매단 등불
        _hang(p, x, 4, 1)
    p.banner(4, 7, 0, "black", [("gradient_up", "red"), ("triangles_bottom", "orange"), ("border", "black")],
             facing="north")
    # 옆·뒤 창 (아래층 창턱, 2층 덧문)
    for z in (4, 7):
        p.window(1, 3, z, "west", glass=glass, sill=stairs("polished_blackstone", "east", "top"))
    for z in (3, 6):
        p.window(1, 6, z, "west", glass=glass, shutter="acacia")
    p.window(4, 3, 9, "south", glass=glass, sill=stairs("polished_blackstone", "north", "top"))
    for x in (2, 6):
        p.window(x, 6, 9, "south", glass=glass, shutter="acacia")
    _corbel_lamp(p, 0, 4, 5, "east")
    _corbel_lamp(p, 2, 4, 10, "north")

    # 집 안 아래층: 쇠·석탄 재고, 상자, 작업대, 2층 사다리
    p.set(2, 2, 3, B("barrel", facing="up"))
    p.set(2, 3, 3, lantern(hanging=False))
    p.light(2, 3, 3)
    p.set(2, 2, 6, B("iron_block"))
    p.set(2, 2, 7, B("coal_block"))
    p.set(2, 3, 7, B("raw_iron_block"))
    p.set(3, 2, 8, B("chest", facing="north"))
    p.set(4, 2, 8, B("crafting_table"))
    p.set(5, 2, 8, B("barrel", facing="north"))
    for y in range(2, 6):
        p.set(6, y, 8, B("ladder", facing="west"))
    _hang(p, 4, 4, 5)
    # 2층: 침대, 상자, 지붕 밑 등불
    p.bed("orange", 3, 6, 7, "south")
    p.set(2, 6, 8, B("chest", facing="east"))
    p.set(5, 6, 2, B("barrel", facing="up"))
    p.set(2, 6, 4, B("orange_carpet"))
    _hang(p, 4, 10, 5, chain_n=1)

    # ── 작업장 (x 8..13, z 0..8): 기둥 + 들보 + 낮은 박공 (서쪽 처마는 집 벽에 붙음, 동쪽 처마는 기둥 밖 한 칸)
    p.fill(8, 0, 0, 13, 0, 8, stone)
    p.fill(8, 1, 0, 13, 1, 8, pave)
    p.gable_roof(9, 1, 13, 7, 6, roof, axis="z", overhang=1, end_overhang=1, gable=None, ridge=ridge)
    _trim(p, _gable_edges("z", 9, 1, 13, 7, 6), _COPPER, _COPPER)
    for z in (1, 4, 7):
        p.fill(13, 2, z, 13, 5, z, log(frame))
    for z in (1, 7):
        p.fill(8, 2, z, 8, 5, z, log(frame))
    for z in range(2, 7):
        if z != 4:
            p.set(13, 5, z, log(frame, "z"))
        p.set(8, 5, z, log(frame, "z"))
    for x in range(9, 13):
        p.set(x, 5, 1, log(frame, "x"))                                 # 앞 가로보
    p.fill(11, 6, 1, 11, 7, 1, log(frame))                              # 박공 왕기둥
    p.set(10, 6, 1, stairs("dark_oak", "east", "top"))                  # 버팀 (왕기둥 양옆)
    p.set(12, 6, 1, stairs("dark_oak", "west", "top"))
    p.banner(11, 6, 0, "orange", [("bricks", "black"), ("triangle_top", "black"), ("circle", "yellow"),
                                   ("border", "black")], facing="north")
    p.sign(11, 4, 1, ["<gold><b>두르간의</b></gold>", "<gold><b>대장간</b></gold>", "<gray>강화 · 수리</gray>"],
           wood="dark_oak", facing="north", wall=False, hanging=True, glow=True)
    _hang(p, 9, 4, 1)
    # 동쪽 낮은 난간 (기둥 사이) + 난간 위 등불
    for z in (2, 3, 5, 6):
        p.set(13, 2, z, wall("polished_blackstone"))
    p.set(13, 3, 2, lantern(hanging=False))
    p.light(13, 3, 2)
    p.set(13, 3, 6, B("decorated_pot", facing="west"))
    # 뒷벽 (z=8, x 8..10) + 그 위 박공 삼각형
    p.fill(8, 2, 8, 10, 5, 8, stone)
    for (x, y) in ((9, 6), (10, 6), (10, 7)):
        if p.get(x, y, 8) in (" ", "."):
            p.set(x, y, 8, plaster)

    # ── 굴뚝 (x 11..13, z 8..10): 검은 벽돌 + 주황 레진 띠, 꼭대기 모닥불 · 화덕 (앞면 z=8)
    for y in range(0, 14):
        for x in range(11, 14):
            for z in range(8, 11):
                corner = x in (11, 13) and z in (8, 10)
                p.set(x, y, z, quoin if corner else (resin if y in (6, 11) else cstone))
    for x in range(11, 14):
        for z in range(8, 11):
            if (x, z) == (12, 9):
                p.set(x, 14, z, campfire())
                p.light(x, 14, z)
            elif x in (11, 13) and z in (8, 10):
                p.set(x, 14, z, wall("polished_blackstone"))
            else:
                p.set(x, 14, z, slab("polished_blackstone_brick"))
    p.ambient(12, 14, 9, "embers")
    p.set(11, 2, 8, B("blast_furnace", facing="north", lit=False))
    p.set(12, 2, 8, B("lava_cauldron"))
    p.light(12, 2, 8)
    p.set(12, 3, 8, ".")
    p.set(12, 4, 8, B("chiseled_polished_blackstone"))
    p.ambient(12, 3, 8, "smoke")
    for x in range(11, 14):                                             # 화덕 갓
        p.set(x, 4, 7, stairs("polished_blackstone_brick", "south", "top"))
        p.set(x, 5, 7, B("polished_blackstone_bricks"))
    # 뒤쪽 장작더미 (x 8..10, z 9..10)
    p.fill(8, 2, 9, 10, 3, 10, log("spruce", "z"))
    p.fill(8, 4, 9, 10, 4, 10, slab("spruce"))
    p.set(9, 5, 10, lantern(hanging=False))
    p.light(9, 5, 10)

    # ── 작업장 살림: 모루 · 대장장이 작업대 (interact), 숫돌, 담금질 가마솥, 통, 매단 등불
    p.clear(9, 2, 2, 12, 4, 6)
    p.clear(8, 2, 2, 8, 4, 6)
    p.clear(9, 2, 1, 12, 3, 1)
    p.clear(8, 2, 0, 13, 4, 0)
    p.clear(11, 2, 7, 12, 3, 7)
    p.set(11, 2, 4, B("anvil", facing="west"))
    p.set(8, 2, 5, B("smithing_table"))
    p.set(8, 2, 3, B("grindstone", face="floor", facing="north"))
    p.set(10, 2, 7, B("water_cauldron", level=3))
    p.set(9, 2, 7, B("barrel", facing="up"))
    p.set(9, 3, 7, B("iron_block"))
    for z in range(3, 7):
        p.set(7, 3, z, B("dark_oak_shelf", facing="east"))              # 집 벽 = 연장 선반
    _hang(p, 11, 6, 4, chain_n=1)
    p.npc("blacksmith", 10, 2, 5, "front")
    p.interact("blacksmith", [(11, 2, 4), (8, 2, 5)])
    _vary(p, "deepslate_tile_stairs", _TILE_MIX, seed=27)
    return p


# ─────────────────────────────── 6. 핀의 떠돌이 상점 ───────────────────────────────

def market():
    """떠돌이 상인의 노점. 가운데 빨강·흰 줄무늬 큰 천막(나무 마루 + 계산대, 뒤 진열 선반),
    서쪽 노랑·파랑 짐 천막(통·상자), 동쪽 연두·흰 차양 밑 상자 더미, 앞 동쪽 손수레, 서쪽 앞 지구본 깃발 장대.
    천막 처마 끝은 반블록 술 장식, 처마 밑 매단 등불. 상인 핀은 계산대 뒤."""
    W, H, D, F = 14, 9, 9, 1
    p = Piece("market", "핀의 떠돌이 상점", W, H, D, floor_y=F, anchor=(6, 0),
              foundation_mix=[("cobblestone", 3), ("mossy_cobblestone", 1), ("packed_mud", 1)])
    deck = mix(("spruce_planks", 4), ("stripped_spruce_wood", 1), seed=31)
    post = log("stripped_spruce")

    # ── 가운데 큰 천막 (기둥 x 4·8, z 1·5): 마루, 처마 술, 계산대
    p.fill(4, 0, 0, 8, 0, 5, B("packed_mud"))
    p.fill(4, 1, 0, 8, 1, 5, deck)
    for x in (4, 8):
        for z in (1, 5):
            p.fill(x, 2, z, x, 5, z, post)
    p.gable_roof(4, 1, 8, 5, 5, "red_wool", axis="x", overhang=1, end_overhang=1, under=None, ridge="slab")
    for x in range(3, 10):
        for z in (0, 6):
            p.set(x, 4, z, slab("red_wool", "top"))
    _stripe(p, 3, 4, 0, 9, 8, 6, "red", "white", by="x")
    p.clear(5, 2, 2, 7, 4, 4)
    p.clear(4, 2, 2, 4, 4, 4)
    p.clear(8, 2, 2, 8, 4, 4)
    p.clear(3, 2, 0, 9, 3, 0)
    # 계산대 (z=1, x 5..7) = interact merchant · 위에 종·장식 항아리·촛불
    for x in (5, 6, 7):
        p.set(x, 2, 1, B("stripped_spruce_wood", axis="x"))
    p.set(5, 3, 1, B("decorated_pot", facing="north"))
    p.set(6, 3, 1, candle("yellow", 3))
    p.set(7, 3, 1, B("bell", attachment="floor", facing="east"))
    p.interact("merchant", [(5, 2, 1), (6, 2, 1), (7, 2, 1)])
    # 뒤 진열 선반 (z=5): 통·상자 위에 물약대·자수정·화분
    p.set(5, 2, 5, B("barrel", facing="up"))
    p.set(6, 2, 5, B("barrel", facing="north"))
    p.set(7, 2, 5, B("barrel", facing="up"))
    p.set(5, 3, 5, B("brewing_stand", has_bottle_0=True, has_bottle_1=True, has_bottle_2=False))
    p.set(6, 3, 5, B("amethyst_cluster", facing="up"))
    p.set(7, 3, 5, flower_pot("fern"))
    p.set(4, 2, 3, B("barrel", facing="east"))
    p.set(8, 2, 3, B("chiseled_bookshelf", facing="west"))
    p.set(8, 2, 4, B("bookshelf"))
    p.set(8, 3, 4, candle("purple", 2))
    p.set(6, 2, 2, B("red_carpet"))
    for x in (5, 7):
        _hang(p, x, 5, 1)
    _hang(p, 5, 6, 3)
    _hang(p, 6, 3, 6)
    p.npc("merchant", 6, 2, 3, "front")

    # ── 서쪽 짐 천막 (x 0..2, z 3..8): 노랑·파랑, 용마루 z 방향, 속에 통·상자
    for x in (0, 2):
        for z in (4, 7):
            p.fill(x, 2, z, x, 3, z, post)
    p.gable_roof(0, 4, 2, 7, 4, "yellow_wool", axis="z", overhang=0, end_overhang=1, under=None, ridge="slab")
    _stripe(p, 0, 4, 3, 2, 5, 8, "yellow", "blue", by="z")
    p.clear(1, 2, 3, 1, 3, 8)
    p.set(1, 2, 5, B("barrel", facing="up"))
    p.set(1, 3, 5, flower_pot("red_tulip"))
    p.set(1, 2, 6, B("chest", facing="north"))
    p.set(1, 2, 7, B("hay_block", axis="z"))
    for z in (5, 6):
        p.set(0, 2, z, B("barrel", facing="west"))
        p.set(2, 2, z, B("composter", level=0))
    p.set(1, 1, 3, B("coarse_dirt"))
    p.set(1, 1, 4, B("coarse_dirt"))
    _hang(p, 1, 3, 4)
    # 지구본 깃발 장대 (서쪽 앞)
    p.fill(0, 2, 1, 0, 6, 1, fence("spruce"))
    p.set(0, 1, 1, B("cobblestone"))
    p.banner(0, 7, 1, "blue", [("globe", "yellow"), ("border", "yellow"), ("stripe_top", "light_blue")],
             facing="north", wall=False)

    # ── 동쪽 차양 (x 10..13, z 3..7): 연두·흰 반블록 완만 경사, 밑에 상자 더미
    for x in (10, 13):
        p.fill(x, 2, 3, x, 3, 3, post)
        p.fill(x, 2, 7, x, 5, 7, post)
    rows = ((3, 4, "bottom"), (4, 4, "top"), (5, 5, "bottom"), (6, 5, "top"), (7, 6, "bottom"))
    for x in range(10, 14):
        for z, y, half in rows:
            p.set(x, y, z, slab("lime_wool", half))
    _stripe(p, 10, 4, 3, 13, 6, 7, "lime", "white", by="x")
    p.clear(11, 2, 3, 12, 3, 5)
    p.set(11, 2, 6, B("barrel", facing="up"))
    p.set(12, 2, 6, B("composter", level=0))
    p.set(11, 2, 7, B("chest", facing="north"))
    p.set(12, 2, 7, B("barrel", facing="north"))
    p.set(11, 3, 7, B("barrel", facing="up"))
    p.set(12, 3, 7, B("composter", level=0))
    p.set(11, 3, 6, B("pumpkin"))
    p.set(12, 3, 6, flower_pot("cactus"))
    _hang(p, 11, 3, 4)

    # ── 손수레 (x 10..13, z 0..2): 바퀴 = 열린 다락문, 짐 = 건초·호박·통
    p.fill(11, 2, 1, 12, 2, 2, slab("spruce", "top"))
    for z in (2,):
        p.set(10, 2, z, trapdoor("dark_oak", "west", open=True))
        p.set(13, 2, z, trapdoor("dark_oak", "east", open=True))
    p.set(11, 2, 0, fence("spruce"))
    p.set(12, 2, 0, fence("spruce"))
    p.set(11, 3, 1, B("hay_block", axis="x"))
    p.set(12, 3, 1, B("pumpkin"))
    p.set(11, 3, 2, B("barrel", facing="up"))
    p.set(12, 3, 2, B("melon"))
    for x in (11, 12):
        p.set(x, 3, 0, ".")
    return p


# ─────────────────────────────── 7. 검은 등불 여관 ───────────────────────────────

_INN_ROOF = [("dark_prismarine_stairs", 6), ("warped_stairs", 2), ("prismarine_brick_stairs", 1)]


def inn():
    """2층 여관. 돌 아래층 + 가문비 뼈대 2층(창·문 칸을 감싸는 기둥 + 도리), 짙은 청록 박공 지붕(용마루 x 방향).
    정면 가운데 두 층 현관: 아래는 기둥 현관, 위는 난간 발코니, 그 위 앞으로 튀어나온 작은 박공(골 지붕).
    현관 기둥에서 동쪽으로 내민 팔에 걸린 간판 + 검은 등불(영혼 등불). 동쪽 박공벽 밖 돌 굴뚝(꼭대기 모닥불).
    1층 주점: 술통 벽 뒤 계산대, 탁자·의자, 벽난로, 2층 계단. 2층 객실: 침대 셋."""
    W, H, D, F = 13, 16, 11, 1
    p = Piece("inn", "검은 등불 여관", W, H, D, floor_y=F, anchor=(6, 2),
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 1), ("cobblestone", 1), ("andesite", 1)])
    stone = mix(("stone_bricks", 4), ("mossy_stone_bricks", 2), ("cracked_stone_bricks", 1), ("cobblestone", 1), seed=41)
    plaster = mix(("calcite", 2), ("white_terracotta", 2), ("birch_planks", 1), seed=42)
    floor = mix(("spruce_planks", 4), ("stripped_spruce_wood", 1), seed=43)
    frame = "spruce_log"
    roof = "dark_prismarine"
    trim_of = {"dark_prismarine_stairs": "spruce_stairs", "dark_prismarine_slab": "spruce_slab"}
    glass = "yellow_stained_glass_pane"

    # ── 본채 (x 1..11, z 3..9): 아래층 돌 y 2..4, 2층 가로보 y=5, 2층 원목 뼈대 y 6..8
    p.fill(1, 0, 3, 11, 0, 9, stone)
    p.fill(1, 1, 3, 11, 1, 9, stone)
    p.fill(2, 1, 4, 10, 1, 8, floor)
    for (x, z) in _ring_box(1, 3, 11, 9):
        p.fill(x, 2, z, x, 4, z, stone)
    for (x, z) in ((1, 3), (11, 3), (1, 9), (11, 9)):
        p.fill(x, 2, z, x, 4, z, log(frame))
    p.clear(2, 2, 4, 10, 4, 8)
    for x in range(1, 12):
        p.set(x, 5, 3, log(frame, "x"))
        p.set(x, 5, 9, log(frame, "x"))
    for z in range(4, 9):
        p.set(1, 5, z, log(frame, "z"))
        p.set(11, 5, z, log(frame, "z"))
    p.fill(2, 5, 4, 10, 5, 8, B("spruce_planks"))
    for (x0, z0, x1, z1) in ((1, 3, 11, 3), (1, 9, 11, 9), (1, 3, 1, 9), (11, 3, 11, 9)):
        p.timber_wall(x0, 6, z0, x1, 8, z1, frame=frame, infill=plaster, post_every=99, beams=False, mid_beam=8)
    for x in (4, 8):                                                    # 기둥: 창·문 칸을 감싸는 자리만
        for z in (3, 9):
            p.fill(x, 6, z, x, 7, z, log(frame))
    for z in (6,):
        for x in (1, 11):
            p.fill(x, 6, z, x, 7, z, log(frame))
    p.clear(2, 6, 4, 10, 8, 8)
    # 지붕 (처마 y=9, 용마루 y=13), 박공벽 = 회반죽 + 가운데 기둥·둥근 창
    p.gable_roof(1, 3, 11, 9, 9, roof, axis="x", overhang=1, end_overhang=1, gable=plaster, ridge=slab("spruce"))
    _trim(p, _gable_edges("x", 1, 3, 11, 9, 9), trim_of, trim_of)
    for x in (1, 11):
        p.set(x, 9, 6, log(frame))
        p.set(x, 10, 6, pane("yellow"))
        p.set(x, 11, 6, log(frame))
        p.set(x, 10, 5, log(frame, "z"))
        p.set(x, 10, 7, log(frame, "z"))

    # ── 정면 현관 + 발코니 (x 4..8, z 0..2): 기둥 (x 4·8, z=1) 이 발코니 지붕까지
    p.fill(3, 0, 0, 9, 0, 2, stone)
    p.fill(4, 1, 0, 8, 1, 2, mix(("polished_andesite", 2), ("stone_bricks", 2), seed=44))
    p.set(6, 1, 0, B("chiseled_stone_bricks"))
    for x in (4, 8):
        p.fill(x, 2, 1, x, 8, 1, log(frame))
        p.set(x, 1, 1, B("chiseled_stone_bricks"))
    p.fill(4, 5, 1, 8, 5, 2, B("spruce_planks"))                         # 발코니 바닥 (= 현관 천장)
    for x in (5, 6, 7):
        p.set(x, 5, 1, slab("spruce", "top"))
    for x in (5, 6, 7):
        p.set(x, 6, 1, fence("spruce"))                                 # 난간
    for x in (4, 8):
        p.set(x, 6, 2, fence("spruce"))
    p.clear(5, 2, 0, 7, 4, 2)
    p.clear(4, 2, 2, 4, 4, 2)
    p.clear(8, 2, 2, 8, 4, 2)
    p.clear(5, 7, 1, 7, 8, 2)
    p.clear(5, 6, 2, 7, 6, 2)
    # 발코니 위 작은 박공 (골 지붕: 줄마다 본채 지붕 경사에 닿는 데까지만)
    for k in range(4):
        yy = 9 + k
        for z in range(0, 3 + k):
            lo, hi = 3 + k, 9 - k
            if lo < hi:
                p.set(lo, yy, z, stairs(roof, "east"))
                p.set(hi, yy, z, stairs(roof, "west"))
                if k > 0:
                    p.set(lo, yy - 1, z, stairs(roof, "west", "top"))
                    p.set(hi, yy - 1, z, stairs(roof, "east", "top"))
            else:
                p.set(lo, yy - 1, z, B("dark_prismarine"))
                p.set(lo, yy, z, slab("spruce"))
    for x in range(3, 10):                                              # 앞 끝 줄 = 나무 테두리
        _trim(p, [(x, y, 0) for y in range(8, 14)], trim_of, trim_of)
    for (x, y) in ((5, 9), (6, 9), (7, 9), (6, 10)):                    # 작은 박공 삼각형 (z=1)
        p.set(x, y, 1, plaster)
    for (x, y) in ((5, 9), (6, 9), (7, 9), (6, 10)):
        if p.get(x, y, 2) in (" ", "."):
            p.set(x, y, 2, ".")
    p.banner(6, 10, 0, "green", [("rhombus", "black"), ("circle", "yellow"), ("stripe_top", "black"),
                                  ("border", "black")], facing="north")
    for x in (5, 7):
        _hang(p, x, 8, 2)

    # 정면 벽 (z=3): 문, 1층 창 (꽃 화분 창턱), 2층 창 + 발코니 문
    p.door("spruce", 6, 2, 3, "north")
    p.set(6, 4, 3, B("chiseled_stone_bricks"))
    p.door("spruce", 6, 6, 3, "north")
    for x0 in (2, 9):
        p.window(x0, 3, 3, "north", w=2, glass=glass, shutter="warped", sill=stairs("spruce", "south", "top"))
    p.set(2, 3, 2, flower_pot("red_tulip"))
    p.set(10, 3, 2, flower_pot("azure_bluet"))
    for x in (2, 9):
        p.window(x, 6, 3, "north", w=2, glass=glass, shutter="warped")
    _hang(p, 6, 4, 2)
    # 걸린 간판: 동쪽 현관 기둥에서 내민 팔 + 검은 등불
    p.set(9, 5, 1, fence("dark_oak"))
    p.set(10, 5, 1, fence("dark_oak"))
    p.sign(9, 4, 1, ["<dark_gray><b>검은 등불</b></dark_gray>", "<dark_green><b>여관</b></dark_green>",
                     "<gray>쉬어 가세요</gray>"], wood="dark_oak", facing="north", wall=False, hanging=True, glow=True,
           back=["<dark_gray><b>검은 등불</b></dark_gray>", "<dark_green><b>여관</b></dark_green>"])
    _hang(p, 10, 4, 1, soul=True)

    # 옆·뒤 창
    for z in (4, 8):
        p.window(1, 3, z, "west", glass=glass, sill=stairs("spruce", "east", "top"))
        p.window(11, 6, z, "east", glass=glass)
    for z in (4, 7):
        p.window(1, 6, z, "west", w=2, glass=glass, shutter="warped")
    for x in (2, 9):
        p.window(x, 6, 9, "south", w=2, glass=glass)
    p.window(6, 6, 9, "south", glass=glass)
    for x0 in (3, 8):
        p.window(x0, 3, 9, "south", w=2, glass=glass, shutter="warped")
    _corbel_lamp(p, 0, 4, 6, "east")
    _corbel_lamp(p, 6, 4, 10, "north")
    _corbel_lamp(p, 12, 4, 4, "west")
    _corbel_lamp(p, 11, 4, 10, "north")
    _corbel_lamp(p, 1, 4, 10, "north")

    # ── 굴뚝 (x 11..12, z 5..7, 동쪽 박공 밖) + 벽난로 (안쪽 x=11)
    cst = mix(("cobblestone", 3), ("stone_bricks", 2), ("mossy_cobblestone", 1), seed=45)
    for y in range(0, 15):
        for x in (11, 12):
            for z in (5, 6, 7):
                p.set(x, y, z, B("bricks") if y >= 12 else cst)
    for x in (11, 12):
        for z in (5, 7):
            p.set(x, 15, z, wall("brick"))
    p.set(11, 15, 6, slab("brick"))
    p.set(12, 15, 6, campfire())
    p.light(12, 15, 6)
    p.set(11, 2, 6, campfire(facing="west"))
    p.light(11, 2, 6)
    p.set(11, 3, 6, ".")
    p.set(11, 4, 6, B("chiseled_stone_bricks"))
    for z in (5, 7):
        p.set(10, 4, z, stairs("stone_brick", "east", "top"))

    # ── 1층 주점
    p.staircase(2, 2, 8, "north", 4, "spruce")                          # 2층 계단 (서쪽 벽 따라)
    p.clear(2, 5, 6, 2, 5, 8)
    p.clear(2, 6, 5, 2, 8, 8)
    for z in (6, 7, 8):
        p.set(3, 6, z, fence("spruce"))                                 # 2층 계단 난간
    # 계산대 (z=7, x 5..8) + 뒤 술통 벽 (z=8)
    for x in (5, 6, 7, 8):
        p.set(x, 2, 7, B("stripped_spruce_wood", axis="x"))
    p.set(5, 3, 7, candle("white", 2))
    p.set(8, 3, 7, B("brewing_stand"))
    for x in (5, 6, 7, 8):
        p.set(x, 2, 8, B("barrel", facing="north"))
        p.set(x, 3, 8, B("barrel", facing="north"))
    p.set(9, 2, 8, B("crafting_table"))
    p.set(4, 2, 8, B("barrel", facing="up"))
    # 탁자 둘 (울타리 + 누름판) + 의자 (계단)
    for (tx, tz) in ((4, 5), (8, 5)):
        p.set(tx, 2, tz, fence("spruce"))
        p.set(tx, 3, tz, B("spruce_pressure_plate"))
        p.set(tx - 1, 2, tz, stairs("spruce", "west"))
        p.set(tx + 1, 2, tz, stairs("spruce", "east"))
    p.set(10, 2, 4, B("barrel", facing="up"))
    p.set(10, 3, 4, flower_pot("fern"))
    for (lx, lz) in ((4, 5), (8, 5), (6, 7)):
        _hang(p, lx, 4, lz)
    p.set(6, 2, 5, B("green_carpet"))
    p.set(6, 2, 6, B("green_carpet"))
    # ── 2층 객실: 침대 셋, 옷궤, 지붕 밑 등불
    for x in (5, 7, 9):
        p.bed("green" if x != 7 else "lime", x, 6, 7, "south")
        p.set(x, 6, 6, B("green_carpet"))
    p.set(10, 6, 5, B("chest", facing="west"))
    p.set(4, 6, 8, B("barrel", facing="up"))
    p.set(4, 7, 8, candle("green", 2))
    p.set(10, 6, 8, flower_pot("lily_of_the_valley"))
    _hang(p, 6, 10, 6, chain_n=1)
    _hang(p, 9, 10, 6, chain_n=1)
    _vary(p, "dark_prismarine_stairs", _INN_ROOF, seed=46)
    return p


# ─────────────────────────────── 8. 마을집 셋 ───────────────────────────────

_HOUSE_FOUNDATION = [("cobblestone", 3), ("mossy_cobblestone", 1), ("stone_bricks", 1), ("andesite", 1)]


def house_a():
    """ㄱ자 오두막: 본채(용마루 x 방향) + 서쪽 앞으로 튀어나온 날개(작은 박공) — 둘 다 분홍 벚나무 지붕.
    돌 밑단 + 짙은 참나무 뼈대 흰 벽, 날개 정면 세 칸 창(덧문·꽃 화분), 안쪽 모퉁이 문(다락문 차양 + 받침 등불),
    뒤 벽돌 굴뚝(벽난로). 안: 침대, 탁자, 상자, 화로."""
    W, H, D, F = 9, 12, 9, 1
    p = Piece("house_a", "벚꽃 지붕 오두막", W, H, D, floor_y=F, anchor=(6, 4), foundation_mix=_HOUSE_FOUNDATION)
    stone = mix(("cobblestone", 3), ("mossy_cobblestone", 2), ("stone_bricks", 1), seed=51)
    plaster = mix(("calcite", 3), ("white_terracotta", 1), seed=52)
    frame, roof = "dark_oak_log", "cherry"
    trim_of = {"cherry_stairs": "dark_oak_stairs", "cherry_slab": "dark_oak_slab"}
    glass = "light_blue_stained_glass_pane"

    walls = _ring_box(1, 3, 7, 7) + _ring_box(1, 1, 5, 3)
    p.fill(1, 0, 3, 7, 1, 7, stone)
    p.fill(1, 0, 1, 5, 1, 3, stone)
    p.fill(2, 1, 4, 6, 1, 6, mix(("spruce_planks", 3), ("oak_planks", 1), seed=53))
    p.fill(2, 1, 2, 4, 1, 3, B("spruce_planks"))
    for (x, z) in set(walls):
        p.set(x, 2, z, stone)
        p.fill(x, 3, z, x, 4, z, plaster)
        p.set(x, 5, z, log(frame, "x" if z in (1, 3, 7) and x not in (1, 5, 7) else "z"))
    for (x, z) in ((1, 1), (5, 1), (1, 3), (5, 3), (7, 3), (1, 7), (7, 7), (3, 7), (5, 7), (1, 5), (7, 5)):
        p.fill(x, 3, z, x, 5, z, log(frame))
    p.clear(2, 2, 4, 6, 5, 6)
    p.clear(2, 2, 2, 4, 5, 3)                                           # 날개와 본채 사이 트임
    # 지붕: 본채 박공 → 날개 골 지붕 (본채 경사에 닿는 데까지)
    p.gable_roof(1, 3, 7, 7, 6, roof, axis="x", overhang=1, end_overhang=1, gable=plaster, ridge="slab")
    _trim(p, _gable_edges("x", 1, 3, 7, 7, 6), trim_of, trim_of)
    _cross_roof(p, 3, 3, 0, 6, lambda k: 2 + k, roof, slab("cherry"), B("cherry_planks"))
    _trim(p, [(x, y, 0) for x in range(0, 7) for y in range(6, 10)], trim_of, trim_of)
    for (x, y) in ((2, 6), (3, 6), (4, 6)):
        p.set(x, y, 1, plaster)
    p.set(3, 7, 1, pane("pink"))
    for x in (1, 7):                                                    # 본채 박공벽: 왕기둥 + 작은 창
        p.set(x, 6, 5, log(frame))
        p.set(x, 7, 5, pane("pink"))
        p.set(x, 8, 5, log(frame))
    # 정면: 날개 세 칸 창 + 꽃 화분, 문 (본채 정면 x=6) + 다락문 차양 + 받침 등불, 돌 디딤길
    p.window(2, 3, 1, "north", w=3, glass=glass, shutter="spruce", sill=stairs("spruce", "south", "top"))
    p.set(2, 3, 0, flower_pot("pink_tulip"))
    p.set(4, 3, 0, flower_pot("allium"))
    p.door("spruce", 6, 2, 3, "north", hinge="right")
    p.set(6, 4, 2, trapdoor("spruce", "north", "top"))
    _corbel_lamp(p, 7, 3, 2, "south")
    for z in (0, 1, 2):
        p.set(6, 1, z, mix(("mossy_cobblestone", 1), ("stone_bricks", 1), seed=54))
    _plant(p, 8, 2, 2, "peony", tall=True)
    _plant(p, 8, 2, 1, B("pink_tulip"))
    _plant(p, 7, 2, 0, B("allium"))
    # 옆·뒤 창
    p.window(1, 3, 2, "west", glass=glass, shutter="spruce")
    p.window(1, 3, 6, "west", glass=glass, shutter="spruce")
    p.window(7, 3, 4, "east", glass=glass, shutter="spruce")
    p.window(7, 3, 6, "east", glass=glass, shutter="spruce")
    p.window(2, 3, 7, "south", glass=glass, sill=stairs("spruce", "north", "top"))
    p.window(4, 3, 7, "south", glass=glass, sill=stairs("spruce", "north", "top"))
    _corbel_lamp(p, 0, 3, 4, "east")
    _corbel_lamp(p, 8, 3, 7, "west")
    # 굴뚝 (x 5..6, z 7..8, 뒤 처마 밖) + 벽난로
    for y in range(0, 11):
        for x in (5, 6):
            for z in (7, 8):
                p.set(x, y, z, B("bricks") if y >= 9 else stone)
    p.set(5, 11, 8, campfire())
    p.light(5, 11, 8)
    p.set(6, 11, 8, slab("brick"))
    p.set(5, 2, 7, campfire(facing="north"))
    p.light(5, 2, 7)
    p.set(5, 3, 7, ".")
    p.set(5, 4, 6, stairs("brick", "south", "top"))
    p.set(6, 4, 6, stairs("brick", "south", "top"))
    # 안: 침대, 탁자, 상자, 작업대, 꽃
    p.bed("pink", 2, 2, 4, "south")
    p.set(2, 2, 6, B("chest", facing="east"))
    p.set(3, 2, 6, B("crafting_table"))
    p.set(4, 2, 5, fence("dark_oak"))
    p.set(4, 3, 5, B("dark_oak_pressure_plate"))
    p.set(4, 2, 4, stairs("dark_oak", "north"))
    p.set(2, 2, 2, B("bookshelf"))
    p.set(4, 2, 2, B("barrel", facing="up"))
    p.set(4, 3, 2, flower_pot("pink_tulip"))
    p.set(6, 2, 5, B("pink_carpet"))
    _hang(p, 4, 5, 5, chain_n=2)
    _vary(p, "cherry_stairs", [("cherry_stairs", 9), ("pink_concrete_stairs", 1)], seed=56)
    _seal(p)
    return p


def house_b():
    """2층 집: 돌 아래층 + 앞으로 내민 원목 2층(자작나무 벽), 붉은 맹그로브 모임 지붕(네 면 경사 + 짧은 용마루)과
    앞 경사 지붕창. 동쪽 벽 밖 굴뚝(벽난로), 내민 2층 밑 받침·매단 등불, 꽃 창턱, 2층 덧문 + 가운데 깃발.
    안: 1층 부엌·식탁, 2층 침실(사다리)."""
    W, H, D, F = 9, 13, 9, 1
    p = Piece("house_b", "붉은 모임지붕 집", W, H, D, floor_y=F, anchor=(4, 4), foundation_mix=_HOUSE_FOUNDATION)
    stone = mix(("stone_bricks", 3), ("mossy_stone_bricks", 1), ("cobblestone", 1), ("andesite", 1), seed=61)
    infill = mix(("birch_planks", 3), ("white_terracotta", 1), seed=62)
    frame, roof = "dark_oak_log", "mangrove"
    trim_of = {"mangrove_stairs": "dark_oak_stairs", "mangrove_slab": "dark_oak_slab"}
    glass = "yellow_stained_glass_pane"

    # 아래층 (x 1..7, z 3..7) 돌 y 2..4 · 2층 (z 2..7, 앞 한 칸 내밂) y 6..8
    p.fill(1, 0, 3, 7, 1, 7, stone)
    p.fill(2, 1, 4, 6, 1, 6, mix(("spruce_planks", 3), ("stripped_spruce_wood", 1), seed=63))
    for (x, z) in _ring_box(1, 3, 7, 7):
        p.fill(x, 2, z, x, 4, z, stone)
    for (x, z) in ((1, 3), (7, 3), (1, 7), (7, 7)):
        p.fill(x, 1, z, x, 4, z, B("polished_andesite"))
    p.clear(2, 2, 4, 6, 4, 6)
    for x in range(1, 8):
        p.set(x, 5, 2, log(frame, "x"))
        p.set(x, 5, 7, log(frame, "x"))
    for z in range(3, 7):
        p.set(1, 5, z, log(frame, "z"))
        p.set(7, 5, z, log(frame, "z"))
    p.fill(2, 5, 3, 6, 5, 6, B("spruce_planks"))
    for x in (1, 7):
        p.set(x, 4, 2, stairs("dark_oak", "south", "top"))
    for (x0, z0, x1, z1) in ((1, 2, 7, 2), (1, 7, 7, 7), (1, 2, 1, 7), (7, 2, 7, 7)):
        p.timber_wall(x0, 6, z0, x1, 8, z1, frame=frame, infill=infill, post_every=3, beams=False, mid_beam=8)
    p.clear(2, 6, 3, 6, 8, 6)
    # 모임 지붕 (처마 y=9) + 앞 지붕창 (가운데 x=4)
    p.hip_roof(1, 2, 7, 7, 9, roof, overhang=1)
    _trim(p, [(x, 9, z) for x in range(0, 9) for z in range(1, 9) if x in (0, 8) or z in (1, 8)], trim_of, trim_of)
    p.set(4, 9, 2, pane("yellow"))
    p.set(4, 10, 2, pane("yellow"))
    for x in (3, 5):
        p.set(x, 9, 2, log(frame))
        p.set(x, 10, 2, infill)
    p.set(4, 10, 3, ".")
    _cross_roof(p, 4, 1, 1, 11, lambda k: 3 + k, roof, slab("mangrove"), B("mangrove_planks"))
    _trim(p, [(x, y, 1) for x in (3, 4, 5) for y in (11, 12)], trim_of, trim_of)
    # 정면: 문 + 꽃 창턱 창, 2층 창 덧문 + 가운데 깃발, 내민 들보 밑 등불, 디딤돌
    p.door("spruce", 4, 2, 3, "north")
    p.set(4, 4, 3, B("chiseled_stone_bricks"))
    for z in (0, 1, 2):
        p.set(4, 1, z, B("mossy_stone_bricks") if z == 0 else B("stone_bricks"))
    for x in (2, 6):
        p.window(x, 3, 3, "north", glass=glass, sill=stairs("spruce", "south", "top"))
        p.set(x, 3, 2, flower_pot("red_tulip" if x == 2 else "orange_tulip"))
        p.window(x, 6, 2, "north", glass=glass, shutter="mangrove")
    p.banner(4, 7, 1, "red", [("flower", "white"), ("border", "white"), ("stripe_bottom", "yellow")], facing="north")
    for x in (3, 5):
        _hang(p, x, 4, 2)
    # 옆·뒤 창
    p.window(1, 3, 5, "west", glass=glass, sill=stairs("spruce", "east", "top"))
    p.window(7, 3, 4, "east", glass=glass, sill=stairs("spruce", "west", "top"))
    p.window(1, 6, 3, "west", w=2, glass=glass, shutter="mangrove")
    p.window(1, 6, 6, "west", glass=glass, shutter="mangrove")
    p.window(7, 6, 3, "east", glass=glass, shutter="mangrove")
    p.window(7, 6, 6, "east", glass=glass)
    p.window(3, 3, 7, "south", glass=glass)
    p.window(5, 3, 7, "south", glass=glass)
    p.window(2, 6, 7, "south", w=2, glass=glass, shutter="mangrove")
    p.window(5, 6, 7, "south", w=2, glass=glass)
    _corbel_lamp(p, 0, 4, 4, "east")
    _corbel_lamp(p, 4, 4, 8, "north")
    _corbel_lamp(p, 8, 4, 7, "west")
    # 굴뚝 (동쪽 벽 밖 x=8, z 4..5) + 안 벽난로
    for y in range(0, 12):
        for z in (4, 5):
            p.set(8, y, z, stone if y < 9 else B("bricks"))
    p.set(8, 12, 4, campfire())
    p.light(8, 12, 4)
    p.set(8, 12, 5, slab("brick"))
    p.set(7, 2, 5, campfire(facing="west"))
    p.light(7, 2, 5)
    p.set(7, 3, 5, ".")
    p.set(6, 4, 5, stairs("stone_brick", "east", "top"))
    # 1층: 부엌 (훈연기·통·작업대), 식탁, 사다리
    p.set(2, 2, 6, B("smoker", facing="east", lit=False))
    p.set(3, 2, 6, B("barrel", facing="up"))
    p.set(3, 3, 6, flower_pot("fern"))
    p.set(2, 2, 5, B("crafting_table"))
    p.set(4, 2, 5, fence("spruce"))
    p.set(4, 3, 5, B("spruce_pressure_plate"))
    p.set(5, 2, 5, stairs("spruce", "east"))
    p.set(2, 2, 4, B("barrel", facing="up"))
    for y in range(2, 6):
        p.set(6, y, 6, B("ladder", facing="west"))
    _hang(p, 4, 4, 4)
    # 2층: 침대 둘, 상자, 등불
    p.bed("red", 2, 6, 5, "south")
    p.bed("white", 4, 6, 5, "south")
    p.set(5, 6, 3, B("chest", facing="south"))
    p.set(2, 6, 3, B("barrel", facing="up"))
    p.set(2, 7, 3, candle("red", 2))
    p.set(3, 6, 4, B("red_carpet"))
    _hang(p, 4, 10, 5, chain_n=1)
    _vary(p, "mangrove_stairs", [("mangrove_stairs", 6), ("crimson_stairs", 1), ("brick_stairs", 1)], seed=65)
    _seal(p)
    return p


def house_c():
    """돌 오두막 + 앞 동쪽 모퉁이 둥근 탑. 오두막은 노란 초가(대나무) 박공 지붕 + 가문비 용마루,
    탑은 돌 원통 + 짙은 슬레이트 원뿔 첨탑(오두막 용마루를 뚫고 솟음). 정문은 탑 앞면, 탑 안에서 오두막으로 이어짐.
    서쪽 박공 밖 굴뚝. 안: 침대, 책장, 가마솥, 탁자."""
    W, H, D, F = 11, 13, 10, 1
    p = Piece("house_c", "탑 달린 초가집", W, H, D, floor_y=F, anchor=(7, 2), foundation_mix=_HOUSE_FOUNDATION)
    stone = mix(("cobblestone", 3), ("andesite", 2), ("stone_bricks", 2), ("mossy_cobblestone", 1), seed=71)
    tstone = mix(("stone_bricks", 4), ("cracked_stone_bricks", 1), ("mossy_stone_bricks", 1), ("tuff_bricks", 1), seed=72)
    glass = "lime_stained_glass_pane"

    # ── 오두막 (x 1..6, z 3..8): 돌벽 y 2..4, 초가 박공 (용마루 x 방향, 짝수 폭 → 가문비 반블록 두 줄 용마루)
    p.fill(1, 0, 3, 6, 1, 8, stone)
    p.fill(2, 1, 4, 5, 1, 7, mix(("spruce_planks", 3), ("oak_planks", 1), seed=73))
    for (x, z) in _ring_box(1, 3, 6, 8):
        p.fill(x, 2, z, x, 4, z, stone)
    for (x, z) in ((1, 3), (6, 8), (1, 8)):
        p.fill(x, 2, z, x, 4, z, log("spruce"))
    p.clear(2, 2, 4, 5, 4, 7)
    p.gable_roof(1, 3, 6, 8, 5, "bamboo", axis="x", overhang=1, end_overhang=1, gable=stone, ridge=slab("spruce"))
    _trim(p, [(x, 5, z) for x in range(0, 8) for z in (2, 9)], {"bamboo_stairs": "spruce_stairs"},
          {"bamboo_stairs": "spruce_stairs"})
    for x in (1, 6):                                                    # 박공벽 작은 창
        p.set(x, 6, 5, pane("lime"))
        p.set(x, 6, 6, pane("lime"))
    # 창
    p.window(2, 3, 3, "north", w=2, glass=glass, shutter="spruce", sill=stairs("spruce", "south", "top"))
    p.window(2, 3, 8, "south", w=2, glass=glass, shutter="spruce")
    p.window(5, 3, 8, "south", glass=glass)
    p.window(1, 3, 5, "west", w=2, glass=glass, sill=stairs("spruce", "east", "top"))
    p.window(6, 3, 6, "east", glass=glass, shutter="spruce")
    p.set(2, 3, 2, flower_pot("cornflower"))
    p.set(3, 3, 2, flower_pot("oxeye_daisy"))

    # ── 둥근 탑 (가운데 x=7, z=3, 반지름 2): 벽 y 0..6, 안 3×3, 첨탑 y=7 반지름 3 · 높이 5
    cx, cz = 7, 3
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if dx * dx + dz * dz > 6:
                continue
            x, z = cx + dx, cz + dz
            inner = abs(dx) <= 1 and abs(dz) <= 1
            p.set(x, 0, z, tstone)
            p.set(x, 1, z, B("polished_andesite") if inner else tstone)
            for y in range(2, 7):
                p.set(x, y, z, "." if inner else tstone)
    for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2)):                     # 탑 띠 (y=6) + 모서리 받침
        p.set(cx + dx, 6, cz + dz, B("chiseled_stone_bricks"))
    _cone(p, cx, cz, [(7, 3), (8, 2), (9, 2), (10, 1), (11, 0)], "deepslate_tile", B("deepslate_tiles"),
          tip=B("end_rod", facing="up"))
    _vary(p, "deepslate_tile_stairs", [("deepslate_tile_stairs", 4), ("deepslate_brick_stairs", 1),
                                       ("polished_deepslate_stairs", 1)], seed=74)
    p.door("spruce", cx, 2, cz - 2, "north")
    p.set(cx, 4, cz - 2, B("chiseled_stone_bricks"))
    p.clear(5, 2, 4, 5, 3, 4)                                           # 탑 → 오두막 통로
    p.clear(6, 2, 3, 6, 4, 4)
    p.set(9, 4, 3, pane("lime"))                                        # 탑 화살창
    p.set(9, 5, 3, pane("lime"))
    p.set(7, 4, 5, pane("lime"))
    p.set(7, 5, 5, pane("lime"))
    for (lx, lz, wd) in ((6, 0, "south"), (8, 0, "south")):              # 탑 문 양옆 받침 등불
        _corbel_lamp(p, lx, 3, lz, wd, mat="stone_brick")
    _hang(p, 7, 8, 3, chain_n=1)
    for (x, z) in ((5, 2), (9, 4)):                                     # 화살창 더
        p.set(x, 4, z, pane("lime"))

    # ── 굴뚝 (서쪽 박공 밖 x=0, z 5..6)
    for y in range(0, 10):
        for z in (5, 6):
            p.set(0, y, z, stone if y < 8 else B("bricks"))
    p.set(0, 10, 5, campfire())
    p.light(0, 10, 5)
    p.set(0, 10, 6, slab("brick"))
    p.set(1, 2, 6, campfire(facing="east"))
    p.light(1, 2, 6)
    p.set(1, 3, 6, ".")
    # 안: 침대, 책장, 가마솥, 탁자, 등불
    p.bed("lime", 3, 2, 7, "west")
    p.set(5, 2, 7, B("bookshelf"))
    p.set(5, 3, 7, B("bookshelf"))
    p.set(4, 2, 7, B("cauldron"))
    p.set(2, 2, 4, B("barrel", facing="up"))
    p.set(2, 3, 4, flower_pot("cornflower"))
    p.set(3, 2, 5, fence("spruce"))
    p.set(3, 3, 5, B("spruce_pressure_plate"))
    p.set(4, 2, 5, stairs("spruce", "east"))
    p.set(8, 2, 3, B("barrel", facing="up"))
    p.set(6, 2, 2, B("lime_carpet"))
    _hang(p, 3, 5, 5, chain_n=2)
    _corbel_lamp(p, 0, 3, 8, "east")
    _corbel_lamp(p, 0, 3, 3, "east")
    _corbel_lamp(p, 7, 3, 7, "west")
    _corbel_lamp(p, 10, 3, 2, "west", mat="stone_brick")
    p.set(8, 3, 3, lantern(hanging=False))
    p.light(8, 3, 3)
    # 앞마당 들꽃 (오두막 처마 밑)
    for x in (1, 4):
        _plant(p, x, 2, 2, B("wildflowers", facing="north", flower_amount=3))
    _seal(p)
    return p


# ─────────────────────────────── 9. 장식 ───────────────────────────────
# 장식은 floor_y=0: 층 0 = 땅 맨 윗블록 자리 (받침돌·뿌리·디딤돌), 그 위로 선다. 정문 검사 없음, slack 3.

def lamp_post_a():
    """나무 가로등: 돌 받침 → 담장 → 원목 → 울타리 기둥, 앞으로 뻗은 팔 끝에 매단 등불 + 꼭대기 등불 (높이 5)."""
    p = Piece("lamp_post_a", "나무 가로등", 1, 6, 2, floor_y=0, anchor=(0, 1))
    p.set(0, 0, 1, B("chiseled_stone_bricks"))
    p.set(0, 1, 1, wall("mossy_stone_brick"))
    p.set(0, 2, 1, log("dark_oak"))
    p.set(0, 3, 1, fence("dark_oak"))
    p.set(0, 4, 1, fence("dark_oak"))
    p.set(0, 4, 0, fence("dark_oak"))
    _hang(p, 0, 3, 0)
    p.set(0, 5, 1, lantern(hanging=False))
    p.light(0, 5, 1)
    return p


def lamp_post_b():
    """쇠 쌍등: 검은 돌 받침 + 검은 담장 기둥, 꼭대기 양옆 쇠창살 팔에 매단 등불 둘 + 구리 등불 (높이 5)."""
    p = Piece("lamp_post_b", "쇠 쌍등", 3, 6, 1, floor_y=0, anchor=(1, 0))
    p.set(1, 0, 0, B("polished_blackstone_bricks"))
    p.set(1, 1, 0, B("chiseled_polished_blackstone"))
    for y in (2, 3, 4):
        p.set(1, y, 0, wall("polished_blackstone"))
    for x in (0, 2):
        p.set(x, 4, 0, bars())
        _hang(p, x, 3, 0)
    p.set(1, 5, 0, B("waxed_copper_lantern", hanging=False))
    p.light(1, 5, 0)
    return p


def bench():
    """긴 의자: 짙은 참나무 계단 두 칸 + 다락문 팔걸이·등받이, 발밑 돌판."""
    p = Piece("bench", "긴 의자", 4, 3, 1, floor_y=0, anchor=(1, 0))
    for x in range(4):
        p.set(x, 0, 0, mix(("stone_bricks", 2), ("mossy_stone_bricks", 1), seed=81))
    for x in (1, 2):
        p.set(x, 1, 0, stairs("dark_oak", "south"))
        p.set(x, 2, 0, trapdoor("dark_oak", "north", open=True))
    p.set(0, 1, 0, trapdoor("dark_oak", "west", open=True))
    p.set(3, 1, 0, trapdoor("dark_oak", "east", open=True))
    return p


def well():
    """우물: 땅속 돌 통 안 물(사방·바닥 막힘) + 돌 테두리, 두 기둥과 가로대에 사슬로 매단 등불, 가문비 박공 지붕,
    둘레 십자 돌판. 원 모서리는 ' ' (잔디 그대로)."""
    p = Piece("well", "마을 우물", 5, 10, 5, floor_y=2, anchor=(2, 1),
              foundation_mix=[("cobblestone", 3), ("mossy_cobblestone", 2)])
    cob = mix(("cobblestone", 3), ("mossy_cobblestone", 2), seed=82)
    p.fill(1, 0, 1, 3, 1, 3, cob)
    p.set(2, 1, 2, B("water", level=0))
    for (x, z) in _ring_box(1, 1, 3, 3):
        p.set(x, 2, z, cob)
    p.set(2, 2, 2, ".")
    for (x, z) in ((0, 1), (0, 2), (0, 3), (4, 1), (4, 2), (4, 3), (1, 0), (2, 0), (3, 0), (1, 4), (2, 4), (3, 4)):
        p.set(x, 2, z, mix(("stone_bricks", 2), ("mossy_stone_bricks", 1), ("cracked_stone_bricks", 1), seed=83))
    for (x, z) in ((1, 1), (3, 1), (1, 3), (3, 3)):
        p.set(x, 3, z, B("mossy_cobblestone"))
    for (x, z) in ((2, 1), (2, 3)):
        p.set(x, 3, z, slab("cobblestone"))
    p.clear(2, 3, 2, 2, 3, 2)
    for x in (1, 3):
        p.fill(x, 3, 2, x, 7, 2, log("spruce"))
    p.set(2, 7, 2, log("spruce", "x"))
    _hang(p, 2, 4, 2, chain_n=2)
    p.gable_roof(1, 1, 3, 3, 7, "spruce", axis="x", overhang=1, end_overhang=1, under="stairs", ridge="slab")
    _trim(p, _gable_edges("x", 1, 1, 3, 3, 7), {"spruce_stairs": "dark_oak_stairs", "spruce_slab": "dark_oak_slab"},
          {"spruce_stairs": "dark_oak_stairs", "spruce_slab": "dark_oak_slab"})
    p.set(3, 4, 3, flower_pot("fern"))
    p.set(1, 4, 1, flower_pot("red_tulip"))
    return p


def flower_bed():
    """돌 화단: 무릎 높이 돌 테두리 + 흙 위 꽃(장미 덤불·작약은 두 칸)."""
    p = Piece("flower_bed", "돌 화단", 5, 4, 4, floor_y=0, anchor=(2, 1))
    rim = mix(("stone_bricks", 2), ("mossy_stone_bricks", 2), ("polished_andesite", 1), seed=84)
    for (x, z) in _ring_box(0, 0, 4, 3):
        p.set(x, 0, z, rim)
        p.set(x, 1, z, rim)
    for x in range(1, 4):
        for z in (1, 2):
            p.set(x, 0, z, B("dirt"))
            p.set(x, 1, z, B("grass_block"))
    p.tall_plant("rose_bush", 2, 2, 1)
    p.tall_plant("peony", 1, 2, 2)
    p.set(1, 2, 1, B("red_tulip"))
    p.set(3, 2, 1, B("allium"))
    p.set(2, 2, 2, B("oxeye_daisy"))
    p.set(3, 2, 2, B("cornflower"))
    for (x, z) in ((0, 0), (4, 3)):
        p.set(x, 2, z, flower_pot("azure_bluet"))
    return p


def _blob(cells, cx, cy, cz, rx, ry, rz, rng, rough=0.35):
    """잎 덩어리: 타원체(가운데 = 칸 좌표 + 0.5 기준) 안 칸을 cells 에 더한다. 바깥 껍질은 rng 로 들쭉날쭉."""
    for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for z in range(int(cz - rz) - 1, int(cz + rz) + 2):
                d = ((x + 0.5 - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 + ((z + 0.5 - cz) / rz) ** 2
                if d <= 1.0 - rough * rng.random() * (1 if d > 0.45 else 0):
                    cells.add((x, y, z))


def _leaves_in(p, cells, block):
    for (x, y, z) in sorted(cells):
        if p.inside(x, y, z) and p.get(x, y, z) == " ":
            p.set(x, y, z, block)


def tree_cherry():
    """벚나무 (중간 크기): 낮게 갈라지는 줄기 + 세 갈래 비스듬한 가지, 넓고 납작한 분홍 잎 지붕
    (가장자리는 아래로 늘어짐), 위에 작은 둔덕, 발치에 꽃잎."""
    W, H, D = 7, 8, 7
    p = Piece("tree_cherry", "벚나무", W, H, D, floor_y=0, anchor=(3, 3))
    rng = random.Random(91)
    for y in range(0, 3):
        p.set(3, y, 3, log("cherry"))
    p.set(3, 3, 3, B("cherry_wood", axis="y"))
    for (x, y, z, ax) in ((4, 3, 3, "x"), (5, 4, 3, "x"), (5, 5, 2, "y"),
                          (2, 4, 4, "x"), (1, 4, 4, "y"), (1, 5, 5, "z"),
                          (3, 4, 2, "z"), (3, 5, 1, "z"), (3, 5, 3, "y")):
        p.set(x, y, z, log("cherry", ax))
    cells = set()
    _blob(cells, 3.5, 5.4, 3.5, 4.0, 1.0, 3.9, rng, 0.35)              # 넓고 납작한 잎 지붕
    _blob(cells, 3.7, 6.3, 3.6, 2.4, 0.9, 2.3, rng, 0.3)               # 위 둔덕
    _blob(cells, 5.4, 6.0, 2.6, 1.4, 0.8, 1.3, rng)
    _blob(cells, 1.9, 6.0, 5.0, 1.3, 0.8, 1.4, rng)
    for (x, y, z) in list(cells):                                       # 가장자리 늘어진 잎 (한두 칸)
        if y == 5 and not ((x + 1, 5, z) in cells and (x - 1, 5, z) in cells and (x, 5, z + 1) in cells
                           and (x, 5, z - 1) in cells):
            if rng.random() < 0.55:
                cells.add((x, 4, z))
                if rng.random() < 0.15:
                    cells.add((x, 3, z))
    _leaves_in(p, cells, leaves("cherry"))
    for (x, z) in ((2, 4), (4, 2), (1, 3), (4, 4), (5, 2), (2, 1), (5, 5), (1, 1)):
        _plant(p, x, 1, z, B("pink_petals", facing=("north", "east", "south", "west")[(x + z) % 4],
                             flower_amount=1 + (x * 3 + z) % 4))
    return p


def tree_oak():
    """큰 참나무: 굵은 줄기 + 세 갈래 굵은 가지(가로 원목), 가지 끝마다 울퉁불퉁한 잎 덩어리 다섯, 발치 낙엽."""
    W, H, D = 9, 12, 9
    p = Piece("tree_oak", "큰 참나무", W, H, D, floor_y=0, anchor=(4, 4))
    rng = random.Random(92)
    for y in range(0, 7):
        p.set(4, y, 4, log("oak"))
    for (x, y, z) in ((5, 0, 4), (3, 0, 4), (4, 0, 5)):                 # 땅속 뿌리
        p.set(x, y, z, log("oak", "x" if z == 4 else "z"))
    p.set(5, 1, 4, B("oak_wood", axis="y"))                             # 뿌리 혹
    branches = [((5, 4, 4, "x"), (6, 5, 4, "x"), (6, 6, 4, "y")),
                ((4, 5, 3, "z"), (4, 6, 2, "z"), (3, 7, 2, "y")),
                ((3, 6, 4, "x"), (2, 6, 5, "z"), (2, 7, 5, "y"))]
    for br in branches:
        for (x, y, z, ax) in br:
            p.set(x, y, z, log("oak", ax))
    p.set(4, 7, 4, log("oak"))
    p.set(4, 8, 4, log("oak"))
    cells = set()
    _blob(cells, 4.5, 9.0, 4.6, 3.3, 2.1, 3.3, rng)
    _blob(cells, 6.9, 7.4, 4.8, 2.4, 1.7, 2.4, rng)
    _blob(cells, 3.7, 8.2, 2.3, 2.4, 1.6, 2.2, rng)
    _blob(cells, 2.5, 8.0, 6.3, 2.3, 1.7, 2.3, rng)
    _blob(cells, 5.6, 10.2, 3.9, 1.7, 1.2, 1.7, rng)
    _leaves_in(p, cells, leaves("oak"))
    for (x, z) in ((2, 3), (6, 6), (5, 2), (3, 6), (7, 3)):
        _plant(p, x, 1, z, B("leaf_litter", facing=("north", "east", "south", "west")[(x * z) % 4],
                             segment_amount=1 + (x + z) % 4))
    return p


# 길잡이 표지판 기본 글 — 면 이름은 조각 정방향 기준(front=북쪽 면). 조립 담당은 make_signpost 로 layout 에 맞는 판을 만든다.
SIGNPOST_SIGNS = {
    "front": ["<gold><b>등불 어귀</b></gold>", "<gray>마을 광장</gray>"],
    "right": ["<yellow>대장간</yellow>", "<yellow>떠돌이 상점</yellow>"],
    "left": ["<yellow>검은 등불 여관</yellow>", "<yellow>마을집</yellow>"],
    "back": ["<light_purple>미궁의 아가리</light_purple>", "<gray>분수 건너 계단 위</gray>"],
}
_SIGN_FACE = {"front": ("north", 1, 3, 0), "right": ("east", 2, 2, 1), "left": ("west", 0, 2, 1),
              "back": ("south", 1, 3, 2)}


def make_signpost(pid="signpost", signs=None, name="길잡이 표지판"):
    """길잡이 표지판 조각을 만든다. signs = {면: [줄, ...]} (면 = front/right/left/back, 빠진 면은 판 없음,
    줄은 최대 4줄 MiniMessage). 판은 가문비 기둥 옆에 붙는다 — 그 면 쪽이 그 길 방향."""
    p = Piece(pid, name, 3, 5, 3, floor_y=0, anchor=(1, 1))
    p.set(1, 0, 1, B("cobblestone"))
    p.set(1, 1, 1, log("spruce"))
    p.set(1, 2, 1, log("spruce"))
    p.set(1, 3, 1, log("spruce"))
    p.set(1, 4, 1, lantern(hanging=False))
    p.light(1, 4, 1)
    for face, lines in (signs if signs is not None else SIGNPOST_SIGNS).items():
        facing, x, y, z = _SIGN_FACE[face]
        p.sign(x, y, z, lines, wood="spruce", facing=facing, glow=True)
    for (x, z) in ((0, 0), (2, 2)):
        _plant(p, x, 1, z, B("short_grass"))
    return p


def signpost():
    """길잡이 표지판 (기본 글 SIGNPOST_SIGNS) — 네 면에 높이를 달리한 판, 꼭대기 등불."""
    return make_signpost()


def cart():
    """손수레: 가문비 바닥(위 반블록) + 열린 다락문 바퀴, 앞 손잡이 울타리, 짐 = 건초·호박·통·양털 자루."""
    p = Piece("cart", "손수레", 4, 4, 4, floor_y=0, anchor=(1, 1))
    for z in (1, 2, 3):
        for x in (1, 2):
            p.set(x, 0, z, B("coarse_dirt"))
            p.set(x, 1, z, slab("spruce", "top"))
    p.set(0, 1, 2, trapdoor("spruce", "west", open=True))
    p.set(3, 1, 2, trapdoor("spruce", "east", open=True))
    p.set(1, 1, 0, fence("spruce"))
    p.set(2, 1, 0, fence("spruce"))
    p.set(1, 2, 1, B("hay_block", axis="x"))
    p.set(2, 2, 1, B("pumpkin"))
    p.set(1, 2, 2, B("barrel", facing="up"))
    p.set(2, 2, 2, B("hay_block", axis="z"))
    p.set(1, 2, 3, B("brown_wool"))
    p.set(2, 2, 3, B("white_wool"))
    p.set(1, 3, 2, flower_pot("dandelion"))
    p.set(2, 3, 3, slab("brown_wool"))
    return p


PIECES = [forge, market, inn, house_a, house_b, house_c,
          lamp_post_a, lamp_post_b, bench, well, flower_bed, tree_cherry, tree_oak, signpost, cart]
