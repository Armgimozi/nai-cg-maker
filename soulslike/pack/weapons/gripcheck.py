"""
무기 손 자세 검사와 시험 모형 (M1 P0, DECISIONS 2026-10-11 "무기 쥐는 각도는 바닐라 마인크래프트와 똑같이").

  python3 pack/weapons/gripcheck.py [팩폴더]   검사만 (기본 pack/resourcepack: gen_pack 이 지은 팩)
  build(out) → 오류 목록                       gen_pack 이 roll_figure 가 아이템 정의를 감싼 뒤 부른다. 시험 모형을 쓰고 검사한다.
                                               오류가 하나라도 있으면 gen_pack 은 팩을 묶지 않는다

검사는 값을 셈한 _common.compose 를 믿지 않는다. 바닐라 jar 의 display (없으면 _common.VANILLA) 와 아래의 따로 적은 틀 (FRAME)
에서 맞는지 본다 (M1 계획 R24):
  1. jar 의 바닐라 display (부모 사슬을 푼 네 손 맥락) 가 _common.VANILLA 와 같다
  2. 바닐라 그림의 쥐는 자리 g_v 를 바닐라 그림에서 다시 셈해 _common.GRIP 과 견준다 (0.01 픽셀):
       handheld  칼 손잡이 (3, 3, 8). 그 3인칭 오른손 자리가 팔 한가운데 줄 (팔 x = −1, z ≈ 0) 위에 있어야 한다 (주먹 한가운데 F)
       spear/mace  F 를 그 바닐라 모형의 3인칭 오른손에서 그림 공간으로 되돌려, 그림의 자루 칸에서 맞춘 가운데 줄에 내린 점
       bow  그림의 대칭 줄 (u = v) 위에서 모퉁이에 가장 가까운 활대 칸들의 가운데
       shield  ShieldModel 손잡이 상자 (−1, −3, −1)+(2, 6, 6) 의 가운데를 방패 그리기 (scale(1, −1, −1), 모서리 원점) 로 옮긴 점
  3. 팩의 무기 모형마다 (souls:item/<id>_3d, 방패 _block, 활 _3d_pulling_*, 구르기 표시판 *_m) 네 손 맥락이 있고, 맥락마다
     (바닐라 ItemTransform.apply 의 왼손 거울을 풀어) 우리 쥐는 점 (8, 8, 8) 이 바닐라 g_v 가 가는 자리에, 우리 +Y·+X·+Z 가
     바닐라 그림의 끝 방향·옆 방향·앞 (크기 k) 이 가는 곳에 간다 (1e-3 픽셀)
  4. 무기 막기 모형 (_guard) 이 없다. 활 당김 모형의 display 가 평소 모형과 같다. souls 아이템 정의 (구르기 대역의 것과 시험
     모형은 빼고) 가 모두 roll_figure 의 감싸기 (custom_model_data 깃발 MARK_FLAG → HIDE_FLAG) 를 지녔다
  5. 시험 모형이 바닐라 그림을 P⁻¹ 로 놓았다 (요소의 쥐는 점 기준 자리)

시험 모형 (언어 열쇠도 플러그인 아이템도 없다. 바닐라 명령 /item replace entity @s weapon.mainhand with
flint[item_model=souls:test_grip_sword] 로 든다. tools/client/grip_shots.sh 가 바닐라 아이템과 겹쳐 찍는다):
  souls:test_grip_sword    바닐라 철검 그림 (minecraft:item/iron_sword) 을 칸마다 상자로 P⁻¹ 해 놓은 것 + 우리 handheld display
  souls:test_grip_mace     바닐라 철퇴 그림 + 우리 철퇴 display        souls:test_grip_spear  바닐라 철창 (손에 든 32×32 그림) + 창
  souls:test_grip_bow      바닐라 활 그림 (당김 셋도) + 우리 활 display, 아이템 정의는 우리 활과 같은 꼴 (using_item, use_duration)
  souls:test_grip_shield   바닐라 ShieldModel 상자 둘 (판·손잡이) 에 minecraft:entity/shield_base_nopattern + 우리 방패·막기 display.
                           1.21.11 은 그림 이름을 아틀라스 모두에서 찾으므로 그 그림은 바닐라 shield_patterns 아틀라스의 것을 그대로
                           부른다 (items 아틀라스에 다시 넣으면 "Duplicate sprite" 경고가 난다)
  souls:test_grip_empty    빈 모형 (팔 자세는 그대로라 겹침 그림의 바탕)
  souls:test_grip_shield_block, test_grip_bow_pulling_0..2 와 바닐라 짝 test_grip_vanilla_shield_block (특수 방패 모형, 바탕
                           item/shield_blocking), test_grip_vanilla_bow_pulling_0..2: 쓰지 않아도 막기·당김 모형을 보인다 (아이템을
                           쓰지 못하는 마네킹 손에서 3인칭 맥락을 바닐라와 견준다, grip_shots.sh)
요소는 그림의 불투명 칸마다 1×1×1 상자 (바닐라 item/generated 와 같은 앞뒤 면과, 비어 있는 이웃 쪽의 옆면), 회전은 z 축 ±45°
(P⁻¹ 의 회전), 창은 그림 한 칸이 우리 모형 1 픽셀 (K⁻¹). 그림은 아래 MASKS (jar 에서 뽑은 알파, jar 가 있으면 견준다).
"""
import io
import json
import math
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
if PACK not in sys.path:
    sys.path.insert(0, PACK)

from weapons import _common as C  # noqa: E402

NS = C.NS
TOL = 1e-3
HANDS = C.HANDS
JAR = os.path.expanduser("~/.cache/souls-client/versions/1.21.11.jar")

# 바닐라 그림의 축 (우리 모형 축이 가야 할 곳). tip = 우리 +Y (끝), side = 우리 +X (윗날·도끼 등·활 시위 쪽), 앞은 늘 그림의 +Z.
# k = 우리 모형 1 픽셀이 그림의 몇 픽셀인가 (창: 32×32 그림이라 반)
FRAME = {
    "handheld": {"tip": (1, 1, 0), "side": (1, -1, 0), "k": 1.0},
    "mace": {"tip": (1, 1, 0), "side": (1, -1, 0), "k": 1.0},
    "bow": {"tip": (1, 1, 0), "side": (1, -1, 0), "k": 1.0},
    "spear": {"tip": (-1, 1, 0), "side": (1, 1, 0), "k": 0.5},
    "shield": {"tip": (0, 1, 0), "side": (1, 0, 0), "k": 1.0},
    "shield_blocking": {"tip": (0, 1, 0), "side": (1, 0, 0), "k": 1.0},
}
# 견줄 바닐라 아이템과 그 그림 (시험 모형과 grip_shots.sh)
PROBE = {
    "sword": {"set": "handheld", "sprite": "iron_sword", "vanilla": "iron_sword", "kind": "straight_sword"},
    "mace": {"set": "mace", "sprite": "mace", "vanilla": "mace", "kind": "hammer"},
    "spear": {"set": "spear", "sprite": "iron_spear_in_hand", "vanilla": "iron_spear", "kind": "spear"},
    "bow": {"set": "bow", "sprite": "bow", "vanilla": "bow", "kind": "bow"},
    "shield": {"set": "shield", "sprite": None, "vanilla": "shield", "kind": "shield"},
}
# 자루 가운데 줄을 맞출 칸 (그림 줄 범위, 그 줄에서 이 열까지): 창은 손잡이 쪽 곧은 자루, 철퇴는 머리 아래 자루
SHAFT = {"spear": ("iron_spear_in_hand", range(10, 29), 32), "mace": ("mace", range(9, 13), 8)}
# ShieldModel (1.21.11): 판 texOffs(0, 0) addBox(−6, −11, −2, 12, 22, 1), 손잡이 texOffs(26, 0) addBox(−1, −3, −1, 2, 6, 6), 그림 64×64
SHIELD_BOXES = (((-6, -11, -2), (12, 22, 1), (0, 0)), ((-1, -3, -1), (2, 6, 6), (26, 0)))
SHIELD_TEX = "minecraft:entity/shield_base_nopattern"

# 바닐라 1.21.11 그림의 알파 (jar 에서 뽑았다. '#' 불투명). jar 가 있으면 build·check 가 jar 와 견준다
MASKS = {
    "iron_sword": [
        ".............###",
        "............####",
        "...........#####",
        "..........#####.",
        ".........#####..",
        "........#####...",
        "..##...#####....",
        "..###.#####.....",
        "...#######......",
        "...######.......",
        "....####........",
        "...######.......",
        "..###.####......",
        "####....##......",
        "###.............",
        "###.............",
    ],
    "mace": [
        ".........##.....",
        "........####.##.",
        ".......########.",
        "......########..",
        ".....##########.",
        ".....###########",
        "......##########",
        ".......########.",
        "......########..",
        ".....###.####...",
        "....###...##....",
        "...###..........",
        "..###...........",
        "####............",
        "###.............",
        "###.............",
    ],
    "bow": [
        "................",
        "...........####.",
        "........########",
        "......#########.",
        ".....######..#..",
        "....####....#...",
        "...####....#....",
        "...###....#.....",
        "..###....#......",
        "..###...#.......",
        "..###..#........",
        ".###..#.........",
        ".###.#..........",
        ".####...........",
        ".###............",
        "..#.............",
    ],
    "bow_pulling_0": [
        ".#..............",
        ".##........####.",
        "..##....########",
        "...##.#########.",
        "....#######...#.",
        "....####.....#..",
        "...#####.....#..",
        "...###.##...#...",
        "..###...##.#....",
        "..###....###....",
        "..###.....#.....",
        ".###....##......",
        ".###...#........",
        ".###.##.........",
        ".####...........",
        "..#.............",
    ],
    "bow_pulling_1": [
        "................",
        "..#.........###.",
        "..##....########",
        "...##.#########.",
        "....########..#.",
        "....####......#.",
        "...#####.....#..",
        "...###.##....#..",
        "..###...##..#...",
        "..###....##.#...",
        "..###.....##....",
        "..###.....#.....",
        ".###....##......",
        ".###..##........",
        ".#####..........",
        "..#.............",
    ],
    "bow_pulling_2": [
        "................",
        "................",
        "...#....#######.",
        "...##.##########",
        "....###########.",
        "....####......#.",
        "...#####......#.",
        "...###.##....#..",
        "..###...##...#..",
        "..###....##..#..",
        "..###.....##.#..",
        "..###......##...",
        "..###......#....",
        "..###..####.....",
        "..#####.........",
        "...#............",
    ],
    "iron_spear_in_hand": [
        "###.............................",
        "#####...........................",
        "#######.........................",
        ".########.......................",
        ".########.......................",
        "..######........................",
        "..######........................",
        "...######.......................",
        "...##..###......................",
        "........###.....................",
        ".........###....................",
        "..........###...................",
        "...........###..................",
        "............###.................",
        ".............###................",
        "..............###...............",
        "...............###..............",
        "................###.............",
        ".................###............",
        "..................###...........",
        "...................###..........",
        "....................###.........",
        ".....................###........",
        "......................###.......",
        ".......................###......",
        "........................###.....",
        ".........................###....",
        "..........................###...",
        "...........................###..",
        "............................###.",
        ".............................###",
        "..............................##",
    ],
}


# ─────────────────────────── 바닐라 jar ───────────────────────────


def client_jar():
    p = os.environ.get("SOULS_CLIENT_JAR") or JAR
    return zipfile.ZipFile(p) if p and os.path.exists(p) else None


def jar_masks(z):
    """jar 의 그림 알파 → MASKS 꼴."""
    from PIL import Image
    out = {}
    for name in MASKS:
        im = Image.open(io.BytesIO(z.read(f"assets/minecraft/textures/item/{name}.png"))).convert("RGBA")
        a = np.array(im)[..., 3]
        out[name] = ["".join("#" if v else "." for v in row) for row in a]
    return out


def jar_display(z, model):
    """jar 의 바닐라 모형 (item/...) 의 네 손 맥락 (부모 사슬, 왼손이 없으면 바닐라처럼 오른손 값)."""
    out, ref = {}, model
    while ref:
        ref = ref.replace("minecraft:", "")
        if ref.startswith("builtin/"):
            break
        m = json.loads(z.read(f"assets/minecraft/models/{ref}.json"))
        for c, v in m.get("display", {}).items():
            out.setdefault(c, v)
        ref = m.get("parent")
    out.setdefault("thirdperson_lefthand", out.get("thirdperson_righthand"))
    out.setdefault("firstperson_lefthand", out.get("firstperson_righthand"))
    return {c: out[c] for c in HANDS}


def _norm(d):
    return {k: [float(x) for x in d.get(k, [0, 0, 0] if k != "scale" else [1, 1, 1])] for k in ("rotation", "translation", "scale")}


# ─────────────────────────── 셈 (바닐라 ItemTransform.apply 를 따로 적는다) ───────────────────────────


def _r(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def eff(d, left):
    """display 한 칸 → 그려지는 (L = R·S, t 픽셀). 왼손이면 바닐라처럼 x 이동과 y·z 회전을 뒤집는다 (적은 값이 왼손 값이어도)."""
    d = _norm(d)
    rx, ry, rz = d["rotation"]
    tx, ty, tz = d["translation"]
    if left:
        ry, rz, tx = -ry, -rz, -tx
    return _r("x", rx) @ _r("y", ry) @ _r("z", rz) @ np.diag(d["scale"]), np.array([tx, ty, tz])


def arm_px(p_item, left=False):
    """3인칭 아이템 자리 (display 뒤, 픽셀) → 팔 모형 좌표 (ItemInHandLayer: Rx(−90)·Ry(180)·T(±1/16, 0.125, −0.625))."""
    k = -1 if left else 1
    v = np.array([k / 16, 0.125, -0.625]) + np.asarray(p_item) / 16
    return (_r("x", -90) @ _r("y", 180) @ v) * 16


def cells(rows):
    return [(u, v) for v, row in enumerate(rows) for u, ch in enumerate(row) if ch == "#"]


def texel_center(u, v, n):
    s = 16.0 / n
    return np.array([(u + 0.5) * s, 16 - (v + 0.5) * s, 8.0])


def grip_points(van, masks, errs):
    """바닐라 그림의 쥐는 자리 g_v (그림 모형 픽셀) 를 다시 셈한다."""
    g = {"handheld": np.array([3.0, 3.0, 8.0])}
    L, t = eff(van["handheld"]["thirdperson_righthand"], False)
    F = t + L @ (g["handheld"] - 8)                     # 주먹 한가운데 (아이템 자리, 픽셀)
    a = arm_px(F)
    if abs(a[0] + 1) > 0.01 or abs(a[2]) > 0.1:
        errs.append(f"handheld 쥐는 자리 (3, 3, 8) 가 팔 한가운데 줄에 없다: 팔 좌표 {np.round(a, 3).tolist()}")
    for name, (sprite, rows_, ucap) in SHAFT.items():
        rows = masks[sprite]
        n = len(rows)
        pts = np.array([texel_center(u, v, n) for u, v in cells(rows) if v in rows_ and u < ucap])
        d = np.array(FRAME[name]["tip"], float)
        d /= np.linalg.norm(d)
        c = pts.mean(axis=0)
        L, t = eff(van[name]["thirdperson_righthand"], False)
        q = 8 + np.linalg.solve(L, F - t)
        gx = c + ((q - c) @ d) * d
        g[name] = np.array([gx[0], gx[1], 8.0])
    rows = masks["bow"]
    diag = [k for k in range(16) if rows[k][k] == "#"]
    run = [diag[0]]
    for k in diag[1:]:
        if k != run[-1] + 1:
            break
        run.append(k)
    m = (run[0] + run[-1] + 1) / 2.0                    # 그림 칸 좌표 (칸 k 는 [k, k+1])
    g["bow"] = np.array([m, 16 - m, 8.0])
    (bx, by, bz), (sx, sy, sz), _ = SHIELD_BOXES[1]
    mc = np.array([bx + sx / 2, by + sy / 2, bz + sz / 2])
    g["shield"] = g["shield_blocking"] = mc * np.array([1, -1, -1])
    return g, F


def frame_matrix(name):
    """우리 모형 축 → 바닐라 그림 축 (열: +X, +Y, +Z 가 가는 곳, 크기 k)."""
    f = FRAME[name]
    tip = np.array(f["tip"], float)
    side = np.array(f["side"], float)
    return np.c_[f["k"] * side / np.linalg.norm(side), f["k"] * tip / np.linalg.norm(tip), [0, 0, 1]]


def check_display(label, disp, name, van, g, errs):
    """우리 display (네 손 맥락) 가 바닐라 name 의 자세를 P 로 옮긴 것인가 (쥐는 점·세 축, 1e-3)."""
    miss = [c for c in HANDS if c not in (disp or {})]
    if miss:
        errs.append(f"{label}: 손 맥락 {miss} 가 없다")
        return
    Qf = frame_matrix(name)
    for c in HANDS:
        left = c.endswith("lefthand")
        Ld, td = eff(disp[c], left)
        Lv, tv = eff(van[name][c], left)
        want_t = tv + Lv @ (g[name] - 8)
        e_t = float(np.max(np.abs(td - want_t)))
        e_l = float(np.max(np.abs(Ld - Lv @ Qf)))
        if e_t > TOL or e_l > TOL:
            errs.append(f"{label} {c}: 바닐라 {name} 와 어긋난다 (쥐는 점 {e_t:.4f} 픽셀, 축 {e_l:.4f})")


# ─────────────────────────── 팩 읽기 ───────────────────────────


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def model_display(models, name, seen=0):
    p = os.path.join(models, name + ".json")
    if not os.path.exists(p) or seen > 8:
        return None
    m = _load(p)
    if "display" in m:
        return m["display"]
    parent = m.get("parent", "")
    if parent.startswith(NS + ":item/"):
        return model_display(models, parent.split("/", 1)[1], seen + 1)
    return None


def expected_set(cls):
    """분류 → 바닐라 모형 (DECISIONS 2026-10-11 기본안: 창·미늘창 = 바닐라 창, 망치 = 바닐라 철퇴, 방패, 활, 나머지 handheld)."""
    if cls in ("spear", "halberd"):
        return "spear"
    if cls in ("hammer", "bell_mace"):
        return "mace"
    if cls in ("small_shield", "shield", "greatshield"):
        return "shield"
    return "bow" if cls == "bow" else "handheld"


def weapon_kinds():
    """id → 분류 (set_a, set_b 의 목록)."""
    from weapons import set_a, set_b
    out = {}
    for wid, entry in set_a.registry().items():
        out[wid] = set_a._spec(entry)["kind"]
    for wid, (_, kind, _) in set_b.WEAPONS.items():
        out[wid] = kind
    return out


def _walk_refs(node, out):
    if isinstance(node, dict):
        if node.get("type", "").replace("minecraft:", "") == "model":
            out.append(node.get("model", ""))
        for v in node.values():
            _walk_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_refs(v, out)
    return out


# ─────────────────────────── 시험 모형 ───────────────────────────


def _uv(u, v, n):
    s = 16.0 / n
    return [round(u * s, 4), round(v * s, 4), round((u + 1) * s, 4), round((v + 1) * s, 4)]


def sprite_elements(rows, name, g):
    """바닐라 그림의 불투명 칸마다 상자 (P⁻¹: 요소 자리 K⁻¹(q − g) + 8, z 축 회전 −θ, 원점 (8, 8, 8))."""
    n = len(rows)
    k = FRAME[name]["k"]
    tip = np.array(FRAME[name]["tip"], float)
    theta = math.degrees(math.atan2(-tip[0], tip[1]))     # 우리 +Y 를 tip 으로 돌리는 Rz 각
    filled = set(cells(rows))
    els = []
    s = 16.0 / n / k
    for u, v in sorted(filled, key=lambda c: (c[1], c[0])):
        q0 = np.array([u * 16.0 / n, 16 - (v + 1) * 16.0 / n])
        b0 = (q0 - g[:2]) / k + 8
        faces = {"south": {"uv": _uv(u, v, n), "texture": "#t"},
                 "north": {"uv": [_uv(u, v, n)[2], _uv(u, v, n)[1], _uv(u, v, n)[0], _uv(u, v, n)[3]], "texture": "#t"}}
        for face, (du, dv) in (("east", (1, 0)), ("west", (-1, 0)), ("up", (0, -1)), ("down", (0, 1))):
            if (u + du, v + dv) not in filled:
                faces[face] = {"uv": _uv(u, v, n), "texture": "#t"}
        els.append({"from": [round(b0[0], 4), round(b0[1], 4), 7.5], "to": [round(b0[0] + s, 4), round(b0[1] + s, 4), 8.5],
                    "rotation": {"angle": -theta, "axis": "z", "origin": [8, 8, 8]}, "faces": faces})
    return els


def shield_elements(g):
    """ShieldModel 상자 둘을 방패 그리기 (scale(1, −1, −1), 모서리 원점) 로 옮기고 P⁻¹ (= − g + 8)."""
    els = []
    for (x0, y0, z0), (dx, dy, dz), (u, v) in SHIELD_BOXES:
        lo = np.array([x0, -(y0 + dy), -(z0 + dz)], float) - g + 8
        hi = np.array([x0 + dx, -y0, -z0], float) - g + 8
        f, gg, h, i, j, k = u, u + dz, u + dz + dx, u + dz + 2 * dx, u + 2 * dz + dx, u + 2 * dz + 2 * dx
        l_, m, n = v, v + dz, v + dz + dy
        q = 16.0 / 64
        uv = {"south": (gg, m, h, n), "north": (j, m, k, n), "east": (h, m, j, n), "west": (f, m, gg, n),
              "up": (gg, l_, h, m), "down": (h, m, i, l_)}
        els.append({"from": [round(c, 4) for c in lo], "to": [round(c, 4) for c in hi],
                    "faces": {fn: {"uv": [round(c * q, 4) for c in r], "texture": "#s"} for fn, r in uv.items()}})
    return els


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=1)
        f.write("\n")


def _item(name, model):
    return {"model": model if isinstance(model, dict) else {"type": "minecraft:model", "model": f"{NS}:item/{model}"}}


def write_probes(out, masks, g):
    """시험 모형 (souls:test_grip_*) 을 쓴다. 돌려주는 값: 이름 목록."""
    assets = os.path.join(out, "assets", NS)
    models = os.path.join(assets, "models", "item")
    items = os.path.join(assets, "items")
    made = []
    for probe, p in PROBE.items():
        name = f"test_grip_{probe}"
        if probe == "shield":
            _json(os.path.join(models, name + ".json"), {"textures": {"s": SHIELD_TEX, "particle": SHIELD_TEX},
                                                         "elements": shield_elements(g["shield"]),
                                                         "display": C.shield_display()})
            _json(os.path.join(models, name + "_block.json"), {"parent": f"{NS}:item/{name}",
                                                               "display": C.shield_block_display()})
            _json(os.path.join(items, name + ".json"), _item(name, {
                "type": "minecraft:condition", "property": "minecraft:using_item",
                "on_false": {"type": "minecraft:model", "model": f"{NS}:item/{name}"},
                "on_true": {"type": "minecraft:model", "model": f"{NS}:item/{name}_block"}}))
            made.append(name)
            continue
        disp = C.bow_display() if probe == "bow" else C.hand_display(p["kind"])
        tex = f"minecraft:item/{p['sprite']}"
        _json(os.path.join(models, name + ".json"), {"textures": {"t": tex, "particle": tex},
                                                     "elements": sprite_elements(masks[p["sprite"]], p["set"], g[p["set"]]),
                                                     "display": disp})
        tree = f"{name}"
        if probe == "bow":
            for i in range(3):
                tex = f"minecraft:item/bow_pulling_{i}"
                _json(os.path.join(models, f"{name}_pulling_{i}.json"), {
                    "textures": {"t": tex, "particle": tex},
                    "elements": sprite_elements(masks[f"bow_pulling_{i}"], "bow", g["bow"]), "display": disp})
            ref = lambda m: {"type": "minecraft:model", "model": f"{NS}:item/{m}"}  # noqa: E731
            tree = {"type": "minecraft:condition", "property": "minecraft:using_item", "on_false": ref(name),
                    "on_true": {"type": "minecraft:range_dispatch", "property": "minecraft:use_duration", "scale": 0.05,
                                "entries": [{"threshold": 0.65, "model": ref(f"{name}_pulling_1")},
                                            {"threshold": 0.9, "model": ref(f"{name}_pulling_2")}],
                                "fallback": ref(f"{name}_pulling_0")}}
        data = _item(name, tree)
        data["swap_animation_scale"] = float(C.SWAP.get(p["kind"], 1.0))
        _json(os.path.join(items, name + ".json"), data)
        made.append(name)
    _json(os.path.join(items, "test_grip_empty.json"), {"model": {"type": "minecraft:empty"}})
    made.append("test_grip_empty")
    # 쓰지 않아도 막기·당김 모형을 보이는 정의 (마네킹처럼 아이템을 쓰지 못하는 몸에서 3인칭 맥락을 견준다): 우리 시험 모형과 같은
    # 자리의 바닐라 모형 (방패 막기 특수 모형, 활 당김 셋)
    ref = lambda m: {"type": "minecraft:model", "model": m}  # noqa: E731
    still = {"test_grip_shield_block": ref(f"{NS}:item/test_grip_shield_block"),
             "test_grip_vanilla_shield_block": {"type": "minecraft:special", "base": "minecraft:item/shield_blocking",
                                                "model": {"type": "minecraft:shield"}}}
    for i in range(3):
        still[f"test_grip_bow_pulling_{i}"] = ref(f"{NS}:item/test_grip_bow_pulling_{i}")
        still[f"test_grip_vanilla_bow_pulling_{i}"] = ref(f"minecraft:item/bow_pulling_{i}")
    for name, model in still.items():
        _json(os.path.join(items, name + ".json"), {"model": model})
        made.append(name)
    return made


def check_probe_geometry(models, masks, g, errs):
    """시험 모형의 요소가 바닐라 그림 칸을 P⁻¹ 로 놓았는가 (요소 가운데 → P → 그림 칸 가운데, 1e-3)."""
    for probe, p in PROBE.items():
        if probe == "shield":
            continue
        sets = [(f"test_grip_{probe}", p["sprite"])]
        if probe == "bow":
            sets += [(f"test_grip_bow_pulling_{i}", f"bow_pulling_{i}") for i in range(3)]
        Qf = frame_matrix(p["set"])
        for model, sprite in sets:
            path = os.path.join(models, model + ".json")
            if not os.path.exists(path):
                errs.append(f"{model}: 시험 모형이 없다")
                continue
            els = _load(path)["elements"]
            n = len(masks[sprite])
            want = sorted(tuple(np.round(texel_center(u, v, n)[:2], 3)) for u, v in cells(masks[sprite]))
            got = []
            for el in els:
                ctr = (np.array(el["from"], float) + np.array(el["to"], float)) / 2
                rot = el["rotation"]
                ctr = _r("z", rot["angle"]) @ (ctr - 8) + 8
                q = Qf @ (ctr - 8) + g[p["set"]]
                got.append(tuple(np.round(q[:2], 3)))
            if len(got) != len(want) or max(abs(a - b) for x, y in zip(sorted(got), want) for a, b in zip(x, y)) > TOL:
                errs.append(f"{model}: 요소가 바닐라 그림 {sprite} 칸에 맞지 않는다")


# ─────────────────────────── 검사 ───────────────────────────


def check(out, masks=None):
    """팩 폴더 out 을 검사한다. 돌려주는 값: (오류 목록, 알림 목록)."""
    errs, notes = [], []
    z = client_jar()
    van = {name: {c: _norm(v) for c, v in C.VANILLA[name].items()} for name in C.VANILLA}
    masks = masks or MASKS
    if z is not None:
        for name, model in C.VANILLA_MODEL.items():
            jd = {c: _norm(v) for c, v in jar_display(z, model).items()}
            if jd != van[name]:
                errs.append(f"_common.VANILLA[{name!r}] 가 jar 의 {model} 와 다르다: {json.dumps(jd)}")
            van[name] = jd
        jm = jar_masks(z)
        for name in MASKS:
            if jm[name] != MASKS[name]:
                errs.append(f"MASKS[{name!r}] 가 jar 의 그림과 다르다")
        masks = jm
        notes.append(f"바닐라 값: {z.filename}")
    else:
        notes.append("클라이언트 jar 가 없어 _common.VANILLA 와 MASKS 로 본다")
    g, fist = grip_points(van, masks, errs)
    for name, gv in g.items():
        mine = np.array(C.GRIP[name]["g"], float)
        if np.max(np.abs(mine - gv)) > 0.01:
            errs.append(f"_common.GRIP[{name!r}].g = {mine.tolist()} 이 다시 셈한 {np.round(gv, 3).tolist()} 와 다르다")
        if np.max(np.abs(C.p_matrix(C.GRIP[name]["q"], C.GRIP[name]["k"]) - frame_matrix(name))) > 1e-9:
            errs.append(f"_common.GRIP[{name!r}] 의 q·k 가 FRAME 과 다르다")
    notes.append("쥐는 자리 g_v: " + ", ".join(f"{k} {(np.round(v, 3) + 0.0).tolist()}" for k, v in g.items() if k != "shield_blocking")
                 + f" (주먹 한가운데 팔 좌표 {np.round(arm_px(fist), 2).tolist()})")
    # 3. 무기 모형
    models = os.path.join(out, "assets", NS, "models", "item")
    items = os.path.join(out, "assets", NS, "items")
    n_models = 0
    for wid, kind in sorted(weapon_kinds().items()):
        want = expected_set(kind)
        if C.grip_set(kind) != want:
            errs.append(f"{wid}: _common.GRIP_OF 의 {kind} → {C.grip_set(kind)} (DECISIONS 기본안은 {want})")
        targets = [(f"{wid}_3d", want)]
        if os.path.exists(os.path.join(models, f"{wid}_block.json")):
            targets.append((f"{wid}_block", "shield_blocking"))
            if want != "shield":
                errs.append(f"{wid}_block: 방패가 아닌 것에 막기 모형이 있다")
        elif want == "shield":
            errs.append(f"{wid}: 방패인데 막기 모형 {wid}_block 이 없다")
        pulls = [f"{wid}_3d_pulling_{i}" for i in range(3) if os.path.exists(os.path.join(models, f"{wid}_3d_pulling_{i}.json"))]
        if want == "bow" and len(pulls) != 3:
            errs.append(f"{wid}: 활 당김 모형이 셋이 아니다 ({pulls})")
        base = model_display(models, f"{wid}_3d")
        for pm in pulls:
            targets.append((pm, "bow"))
            if model_display(models, pm) != base:
                errs.append(f"{pm}: 활 당김 모형의 display 가 평소 ({wid}_3d) 와 다르다")
        for m, name in list(targets):
            if os.path.exists(os.path.join(models, m + "_m.json")):
                targets.append((m + "_m", name))
        for m, name in targets:
            disp = model_display(models, m)
            if disp is None:
                errs.append(f"{m}: 모형이나 display 가 없다")
                continue
            check_display(m, disp, name, van, g, errs)
            n_models += 1
    # 시험 모형도 같은 검사
    for probe, p in PROBE.items():
        for m, name in ([(f"test_grip_{probe}", p["set"])] + ([("test_grip_shield_block", "shield_blocking")] if probe == "shield" else [])
                        + ([(f"test_grip_bow_pulling_{i}", "bow") for i in range(3)] if probe == "bow" else [])):
            disp = model_display(models, m)
            if disp is None:
                errs.append(f"{m}: 시험 모형이 없다")
                continue
            check_display(m, disp, name, van, g, errs)
            n_models += 1
    check_probe_geometry(models, masks, g, errs)
    # 4. 무기 막기 모형 (<id>_guard) 없음 (시험 막기 도구 souls:test_guard 는 무기가 아니다), 아이템 정의의 감싸기
    guards = {f"{NS}:item/{wid}_guard" for wid in weapon_kinds()} | {f"{NS}:item/{wid}_guard_m" for wid in weapon_kinds()}
    for ref in sorted(guards):
        if os.path.exists(os.path.join(models, ref.split("/", 1)[1] + ".json")):
            errs.append(f"{ref}: 무기 막기 모형은 없앴다 (바닐라 칼 막기, SPEC 1.3)")
    import roll_figure
    for f in sorted(os.listdir(items)) if os.path.isdir(items) else []:
        if not f.endswith(".json"):
            continue
        data = _load(os.path.join(items, f))
        if any(r in guards for r in _walk_refs(data, [])):
            errs.append(f"items/{f}: 무기 막기 모형 (_guard) 을 부른다")
        if f in roll_figure.OWN or f.startswith("test_grip_"):
            continue
        mdl = data.get("model", {})
        inner = mdl.get("on_false", {})
        ok = (mdl.get("property") == "minecraft:custom_model_data" and mdl.get("index") == roll_figure.MARK_FLAG
              and inner.get("property") == "minecraft:custom_model_data" and inner.get("index") == roll_figure.HIDE_FLAG)
        if not ok:
            errs.append(f"items/{f}: 구르기 감싸기 (MARK_FLAG → HIDE_FLAG) 가 없다 (gripcheck 는 roll_figure 뒤에 부른다)")
    notes.append(f"무기·시험 모형 {n_models}개의 네 손 맥락을 바닐라 jar 값과 견줬다 (1e-3)")
    return errs, notes


def build(out):
    """gen_pack: 시험 모형을 쓰고 검사한다. 돌려주는 값: 오류 목록 (알림은 찍는다)."""
    z = client_jar()
    masks = jar_masks(z) if z is not None else MASKS
    van = {name: {c: _norm(v) for c, v in (jar_display(z, C.VANILLA_MODEL[name]) if z else C.VANILLA[name]).items()}
           for name in C.VANILLA}
    g, _ = grip_points(van, masks, [])
    made = write_probes(out, masks, g)
    errs, notes = check(out, masks)
    for n in notes:
        print("gripcheck:", n)
    print(f"gripcheck: 시험 모형 {len(made)}개 ({', '.join(made)})")
    return errs


def main(argv):
    out = argv[0] if argv else os.path.join(PACK, "resourcepack")
    errs, notes = check(out)
    for n in notes:
        print("gripcheck:", n)
    for e in errs:
        print("  오류:", e)
    print(f"gripcheck: 오류 {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
