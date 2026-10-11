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
  6. 플러그인과 같은 껍데기 (검토 P0-2): content/weapons.yml 의 id·class·use 와 ItemFactory.SPEAR_CLASSES 를 읽어, 팩의 바닐라 모형
     (창·방패·활) 과 플러그인이 고르는 껍데기 아이템 (돌창·방패·활) 이 맞는가. 창 자세 ⇔ class ∈ SPEAR_CLASSES, 방패 ⇔ use: block,
     활 ⇔ use: bow, 두 쪽의 id 가 같다, 팩 분류와 weapons.yml class 가 같은 바닐라 모형으로 간다 (JUnit GripParityTest 가 pack.zip 으로 같은 것을 본다)
  7. 아이템 정의 길 (검토 P0-3): souls 무기 정의를 손 맥락 × using_item × use_duration {0, 13, 18} × 깃발 {없음, HIDE, MARK, 둘 다}
     마다 풀어 잎이 <id>_3d / _block / _3d_pulling_{0,1,2} (MARK 면 _m) 인지, gui·ground·fixed·on_shelf 가 <id> 인지, HIDE 면 손이
     비는지 본다. 활의 range_dispatch (속성·scale·문턱) 와 swap_animation_scale 은 jar 의 items/bow.json·stone_spear.json·mace.json …
     과 견준다
  8. 모양 (검토 P0-4): 팩의 *_3d·_block·_pulling 모형은 모두 무기 id 의 것이다 (빠진 묶음이 조용히 검사를 건너뛰지 않게). 방패가 아닌
     것은 쥐는 점 (8, 8, 8) 을 품은 요소가 있다 (방패는 손잡이 막대가 x·y 로 (8, 8) 을 지나고 z 8..10.5). 쥐는 점에서 가장 먼 곳이 +Y
     (끝) 쪽이다 (활은 ±Y, 쇠단지는 SPEC 대로 −X 로 매달린다, 방패는 앞면 +Z). 바닐라 그림의 끝 방향은 FRAME 을 믿지 않고 jar 그림의
     불투명 칸의 주축 (자루 쪽 반대로, 활은 시위 쪽에서) 으로 다시 셈해 FRAME 과 견준다
  9. souls 모형 가운데 손 맥락 display 를 지닌 것은 위에서 검사한 무기·시험 모형뿐이다 (예전 M0 시험 막기 도구의 자체 막는 자세 같은 것이
     다시 들어오지 않게)

시험 모형 (언어 열쇠도 플러그인 아이템도 없다. 바닐라 명령 /item replace entity @s weapon.mainhand with
flint[item_model=souls:test_grip_sword] 로 든다. tools/client/grip_shots.sh 가 바닐라 아이템과 겹쳐 찍는다):
  souls:test_grip_sword    바닐라 철검 그림 (minecraft:item/iron_sword) 을 칸마다 상자로 P⁻¹ 해 놓은 것 + 우리 handheld display
  souls:test_grip_mace     바닐라 철퇴 그림 + 우리 철퇴 display        souls:test_grip_spear  바닐라 철창 (손에 든 32×32 그림) + 창
  souls:test_grip_bow      바닐라 활 그림 (당김 셋도) + 우리 활 display, 아이템 정의는 우리 활과 같은 꼴 (using_item, use_duration)
  souls:test_grip_shield   바닐라 ShieldModel 상자 둘 (판·손잡이) 에 바닐라 방패 그림 + 우리 방패·막기 display. 아이템 모형은 items
                           아틀라스의 그림만 쓰므로 바닐라 그림 파일 textures/entity/shield_base_nopattern.png 을 items 아틀라스에
                           다른 이름 (SHIELD_SPRITE) 으로 하나 더 싣는다 (assets/minecraft/atlases/items.json 의 single 소스, sprite 이름 바꿈:
                           같은 이름으로 실으면 shield_patterns 아틀라스와 겹쳐 "Duplicate sprite" 경고가 난다). 그림 파일은 팩에 넣지 않는다
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
import re
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
ROOT = os.path.dirname(PACK)
WEAPONS_YML = os.path.join(ROOT, "plugin", "src", "main", "resources", "content", "weapons.yml")
ITEM_FACTORY = os.path.join(ROOT, "plugin", "src", "main", "java", "kr", "souls", "item", "ItemFactory.java")

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
SHIELD_TEX = "minecraft:entity/shield_base_nopattern"      # 바닐라 그림 파일 (textures/<이것>.png)
SHIELD_SPRITE = f"{NS}:item/test_grip_shield_base"          # 그 파일을 items 아틀라스에 실은 이름
SHIELD_ATLAS = {"sources": [{"type": "single", "resource": SHIELD_TEX, "sprite": SHIELD_SPRITE}]}

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


# ─────────────────────────── 6. 플러그인과 같은 껍데기 (검토 P0-2) ───────────────────────────


def class_set(cls):
    """weapons.yml 의 class → 바닐라 모형 (expected_set 과 같은 기본안. 플러그인은 중형 방패를 medium_shield 로 적는다)."""
    if cls in ("spear", "halberd"):
        return "spear"
    if cls in ("hammer", "bell_mace"):
        return "mace"
    if cls in ("small_shield", "medium_shield", "shield", "greatshield"):
        return "shield"
    return "bow" if cls == "bow" else "handheld"


def plugin_weapons(errs, path=None):
    """content/weapons.yml → {id: (class, use)} (플러그인 Weapons.load 처럼: use 기본 guard, class 기본 straight_sword)."""
    import yaml
    path = path or WEAPONS_YML
    if not os.path.exists(path):
        errs.append(f"{path}: 플러그인 무기 목록이 없다 (껍데기 검사를 할 수 없다)")
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = {}
    for wid, sec in data.items():
        if isinstance(sec, dict):
            out[str(wid)] = (str(sec.get("class", "straight_sword")), str(sec.get("use", "guard")).lower())
    return out


def spear_classes(errs, path=None):
    """ItemFactory.SPEAR_CLASSES (돌창 껍데기로 만드는 class) 를 소스에서 읽는다. 못 읽으면 오류 (조용히 건너뛰지 않는다)."""
    path = path or ITEM_FACTORY
    src = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    m = re.search(r"SPEAR_CLASSES\s*=\s*Set\.of\(([^)]*)\)", src)
    if not m:
        errs.append(f"{path}: SPEAR_CLASSES = Set.of(...) 를 찾지 못했다 (껍데기 검사를 고친다)")
        return set()
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def check_plugin(kinds, errs):
    """팩의 바닐라 모형과 플러그인이 고르는 껍데기 아이템 (ItemFactory.weapon: 활·방패·돌창·부싯돌) 이 맞는가."""
    defs = plugin_weapons(errs)
    spears = spear_classes(errs)
    if not defs:
        return
    for wid in sorted(set(kinds) - set(defs)):
        errs.append(f"{wid}: 팩에 모형이 있는데 weapons.yml 에 없다")
    for wid in sorted(set(defs) - set(kinds)):
        errs.append(f"{wid}: weapons.yml 에 있는데 팩 무기 목록 (set_a.registry, set_b.WEAPONS) 에 없다")
    for wid in sorted(set(kinds) & set(defs)):
        cls, use = defs[wid]
        s = expected_set(kinds[wid])
        if s != class_set(cls):
            errs.append(f"{wid}: 팩 분류 {kinds[wid]} → {s} 인데 weapons.yml class {cls} → {class_set(cls)}")
        for name, pack_side, plugin_side, why in (
                ("spear", s == "spear", cls in spears, f"class {cls} ∈ ItemFactory.SPEAR_CLASSES {sorted(spears)} (돌창 껍데기)"),
                ("shield", s == "shield", use == "block", f"use {use} == block (방패 껍데기)"),
                ("bow", s == "bow", use == "bow", f"use {use} == bow (활 껍데기)")):
            if pack_side != plugin_side:
                errs.append(f"{wid}: 팩의 손 자세가 {s} 인데 플러그인 쪽 {why} 이 {plugin_side} 이다 (자세와 껍데기 아이템이 어긋난다)")


# ─────────────────────────── 7. 아이템 정의 길 (검토 P0-3) ───────────────────────────

FLAT = ("gui", "ground", "fixed", "on_shelf")
HELD = HANDS + ("head",)
DURATIONS = (0, 13, 18)               # 틱. 바닐라 활 문턱 (0.65, 0.9) × 20 의 양쪽
# 바닐라 아이템 (jar items/<이름>.json) 과 그것이 없을 때의 값
VANILLA_ITEM = {"handheld": "iron_sword", "mace": "mace", "spear": "stone_spear", "shield": "shield", "bow": "bow"}
VANILLA_SWAP = {"handheld": 1.0, "mace": 1.0, "spear": 1.95, "shield": 1.0, "bow": 1.0}
VANILLA_BOW_RANGE = ("minecraft:use_duration", 0.05, (0.65, 0.9))


def resolve(node, st):
    """아이템 정의 모형 나무를 상태 st (ctx, using, dur, flags) 로 풀어 잎 (모형 이름, "empty", "special:<base>") 을 돌려준다."""
    if not isinstance(node, dict):
        return "missing"
    t = node.get("type", "").replace("minecraft:", "")
    if t == "model":
        return node.get("model", "")
    if t == "empty":
        return "empty"
    if t == "special":
        return "special:" + node.get("base", "")
    if t == "composite":
        return "composite:" + ",".join(resolve(m, st) for m in node.get("models", []))
    if t == "condition":
        prop = node.get("property", "")
        if prop == "minecraft:using_item":
            v = st["using"]
        elif prop == "minecraft:custom_model_data":
            v = int(node.get("index", 0)) in st["flags"]
        else:
            return f"unknown-condition:{prop}"
        return resolve(node.get("on_true" if v else "on_false"), st)
    if t == "select":
        if node.get("property") != "minecraft:display_context":
            return f"unknown-select:{node.get('property')}"
        for case in node.get("cases", []):
            when = case.get("when")
            when = [when] if isinstance(when, str) else when
            if st["ctx"] in when:
                return resolve(case.get("model"), st)
        return resolve(node.get("fallback"), st)
    if t == "range_dispatch":
        if node.get("property") != "minecraft:use_duration":
            return f"unknown-range:{node.get('property')}"
        v = st["dur"] * float(node.get("scale", 1.0))
        pick = None
        for e in sorted(node.get("entries", []), key=lambda e: e["threshold"]):
            if e["threshold"] <= v + 1e-9:
                pick = e["model"]
        return resolve(pick if pick is not None else node.get("fallback"), st)
    return f"unknown-type:{t}"


def _range_nodes(node, out):
    if isinstance(node, dict):
        if node.get("type", "").replace("minecraft:", "") == "range_dispatch":
            out.append(node)
        for v in node.values():
            _range_nodes(v, out)
    elif isinstance(node, list):
        for v in node:
            _range_nodes(v, out)
    return out


def vanilla_items(z):
    """바닐라 아이템 정의 값: {set: swap}, 활 (속성, scale, 문턱)."""
    swap, bow = dict(VANILLA_SWAP), VANILLA_BOW_RANGE
    if z is not None:
        for s, name in VANILLA_ITEM.items():
            d = json.loads(z.read(f"assets/minecraft/items/{name}.json"))
            swap[s] = float(d.get("swap_animation_scale", 1.0))
            if s == "bow":
                r = _range_nodes(d, [])[0]
                bow = (r["property"], float(r.get("scale", 1.0)), tuple(sorted(float(e["threshold"]) for e in r["entries"])))
    return swap, bow


def want_leaf(base, s, ctx, using, dur, flags, bow_thr, wrapped=True):
    """그 상태에서 souls 무기 정의가 골라야 할 잎."""
    from roll_figure import HIDE_FLAG, MARK_FLAG
    mark = wrapped and MARK_FLAG in flags
    m = "_m" if mark else ""
    d3 = "_3d" if wrapped else ""          # 시험 모형은 손에 든 모형이 그 이름 그대로 (test_grip_bow, test_grip_bow_pulling_0)
    if ctx in FLAT:
        return f"{NS}:item/{base}{m}"
    if wrapped and not mark and HIDE_FLAG in flags:
        return "empty"
    if using and s == "shield":
        return f"{NS}:item/{base}_block{m}"
    if using and s == "bow":
        i = sum(1 for t in bow_thr if dur * 0.05 >= t - 1e-9)
        return f"{NS}:item/{base}{d3}_pulling_{i}{m}"
    return f"{NS}:item/{base}{d3}{m}"


def check_routes(items, kinds, z, errs):
    """souls 무기 정의 (roll_figure 가 감싼 것) 와 시험 모형 정의를 모든 상태로 풀어 본다. 돌려주는 값: 푼 상태 수."""
    from roll_figure import HIDE_FLAG, MARK_FLAG
    swap, bow = vanilla_items(z)
    flagsets = (frozenset(), frozenset({HIDE_FLAG}), frozenset({MARK_FLAG}), frozenset({HIDE_FLAG, MARK_FLAG}))
    cases = [(wid, wid, expected_set(k), True) for wid, k in sorted(kinds.items())]
    cases += [(f"test_grip_{p}", f"test_grip_{p}", v["set"], False) for p, v in PROBE.items()]
    n = 0
    for name, base, s, wrapped in cases:
        path = os.path.join(items, name + ".json")
        if not os.path.exists(path):
            errs.append(f"items/{name}.json: 아이템 정의가 없다")
            continue
        data = _load(path)
        bad = []
        for flags in (flagsets if wrapped else (frozenset(),)):
            for ctx in (FLAT + HELD if wrapped else HANDS):
                for using in (False, True):
                    for dur in (DURATIONS if using else (0,)):
                        got = resolve(data["model"], {"ctx": ctx, "using": using, "dur": dur, "flags": flags})
                        want = want_leaf(base, s, ctx, using, dur, flags, bow[2], wrapped)
                        n += 1
                        if got != want:
                            bad.append(f"{ctx} using={using} dur={dur} flags={sorted(flags)}: {got} (바라는 것 {want})")
        if bad:
            errs.append(f"items/{name}.json: 정의 길이 어긋난다 ({len(bad)}곳). 처음: " + "; ".join(bad[:3]))
        got_swap = float(data.get("swap_animation_scale", 1.0))
        if abs(got_swap - swap[s]) > 1e-9:
            errs.append(f"items/{name}.json: swap_animation_scale {got_swap} 이 바닐라 {VANILLA_ITEM[s]} 의 {swap[s]} 와 다르다")
        for r in _range_nodes(data, []):
            mine = (r.get("property"), float(r.get("scale", 1.0)), tuple(sorted(float(e["threshold"]) for e in r.get("entries", []))))
            if mine != bow:
                errs.append(f"items/{name}.json: range_dispatch {mine} 이 바닐라 활 {bow} 와 다르다")
        if s != "bow" and _range_nodes(data, []):
            errs.append(f"items/{name}.json: 활이 아닌데 use_duration 나눔이 있다")
    return n


# ─────────────────────────── 8. 모양 (검토 P0-4) ───────────────────────────

# 쥐는 점에서 가장 먼 곳의 방향 (기본 "+y" = 끝). SPEC.md 1.2 의 축 표: 쇠단지는 −X (땅 쪽) 로 매달린다, 활은 활대가 위아래 같은 길이
AXIS = {"kiln_pot": "-x"}
AXIS_OF_SET = {"bow": "±y"}
MODEL_RE = re.compile(r"(.+?)_(3d(?:_pulling_\d)?|block)(_m)?\.json$")


def _elements(models, name, seen=0):
    p = os.path.join(models, name + ".json")
    if not os.path.exists(p) or seen > 8:
        return None
    m = _load(p)
    if "elements" in m:
        return m["elements"]
    parent = m.get("parent", "")
    return _elements(models, parent.split("/", 1)[1], seen + 1) if parent.startswith(NS + ":item/") else None


def _boxes(els):
    """요소마다 (from, to, R, origin) (회전은 축 하나)."""
    out = []
    for e in els:
        a, b = np.array(e["from"], float), np.array(e["to"], float)
        r = e.get("rotation") or {}
        R = _r(r.get("axis", "x"), float(r.get("angle", 0))) if r.get("angle") else np.eye(3)
        out.append((np.minimum(a, b), np.maximum(a, b), R, np.array(r.get("origin", [8, 8, 8]), float)))
    return out


def _contains(box, p, eps=0.01):
    lo, hi, R, o = box
    q = R.T @ (p - o) + o
    return bool(np.all(q >= lo - eps) and np.all(q <= hi + eps))


def _corners(boxes):
    pts = []
    for lo, hi, R, o in boxes:
        for x in (lo[0], hi[0]):
            for y in (lo[1], hi[1]):
                for zz in (lo[2], hi[2]):
                    pts.append(R @ (np.array([x, y, zz]) - o) + o)
    return np.array(pts)


def check_geometry(models, kinds, errs):
    """쥐는 점 (8, 8, 8) 의 요소, 긴 축, 무기 id 가 없는 모형. 돌려주는 값: 본 모형 수."""
    g = np.array([8.0, 8.0, 8.0])
    for f in sorted(os.listdir(models)) if os.path.isdir(models) else []:
        m = MODEL_RE.match(f)
        if m and not m.group(1).startswith("test_grip") and m.group(1) not in kinds:
            errs.append(f"models/item/{f}: 무기 모형인데 무기 목록 (set_a.registry, set_b.WEAPONS) 에 {m.group(1)} 이 없다 "
                        "(새 묶음이면 gripcheck.weapon_kinds 에 더한다: 그러지 않으면 손 자세 검사를 건너뛴다)")
    n = 0
    for wid, kind in sorted(kinds.items()):
        s = expected_set(kind)
        names = [f"{wid}_3d"] + [f"{wid}_3d_pulling_{i}" for i in range(3) if os.path.exists(os.path.join(models, f"{wid}_3d_pulling_{i}.json"))]
        for name in names:
            els = _elements(models, name)
            if not els:
                errs.append(f"{name}: 요소가 없다")
                continue
            n += 1
            boxes = _boxes(els)
            pts = _corners(boxes) - g
            if s == "shield":
                # 손잡이 막대: x·y 로 (8, 8) 을 지나고 z 가 쥐는 점 뒤 8..10.5 (판 뒷면 10.5) 안
                bar = [b for b in boxes if b[0][0] <= 8.01 and b[1][0] >= 7.99 and b[0][1] <= 8.01 and b[1][1] >= 7.99
                       and b[0][2] >= 7.99 and b[1][2] <= 10.51 and np.allclose(b[2], np.eye(3))]
                if not bar:
                    errs.append(f"{name}: 방패 손잡이 막대 (x·y 가 (8, 8) 을 지나고 z 8..10.5) 가 없다 (쥐는 점이 손잡이에서 벗어났다)")
                if not pts[:, 2].max() > -pts[:, 2].min():
                    errs.append(f"{name}: 방패 판이 앞 (+Z) 에 있지 않다 (z {pts[:, 2].min():.1f}..{pts[:, 2].max():.1f})")
                continue
            if not any(_contains(b, g) for b in boxes):
                errs.append(f"{name}: 쥐는 점 (8, 8, 8) 을 품은 요소가 없다 (모형이 주먹에서 떠 있다: 격자·PIVOT 을 본다)")
            far = pts[np.argmax(np.linalg.norm(pts, axis=1))]
            ax = AXIS.get(wid, AXIS_OF_SET.get(s, "+y"))
            i = "xyz".index(ax[-1])
            dom = abs(far[i]) > max(abs(far[j]) for j in range(3) if j != i)
            sign = {"+": far[i] > 0, "-": far[i] < 0, "±": True}[ax[0]]
            if not (dom and sign):
                errs.append(f"{name}: 쥐는 점에서 가장 먼 곳 {np.round(far, 2).tolist()} 이 {ax} 쪽이 아니다 (끝 = +Y, SPEC 1.2 축 표)")
    return n


def sprite_tip(rows, g, name):
    """jar 그림의 불투명 칸에서 끝 방향 (그림 모형 픽셀, y 위) 을 다시 셈한다: 주축을 45° 단위로 맞추고, 자루 쪽 (쥐는 자리 g 에서
    짧은 쪽) 의 반대를 끝으로. 활은 활대가 쥐는 자리 양쪽에 같아 시위 쪽 (쥐는 자리에서 칸 무게 가운데 쪽) 을 옆 (+X) 으로 보고 끝 = Z × 옆."""
    n = len(rows)
    pts = np.array([texel_center(u, v, n)[:2] for u, v in cells(rows)])
    c = pts.mean(axis=0)
    w, vecs = np.linalg.eigh(np.cov((pts - c).T))
    a = vecs[:, int(np.argmax(w))]
    ang = round(math.degrees(math.atan2(a[1], a[0])) / 45.0) * 45.0
    a = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
    if name == "bow":
        side = np.array([a[1], -a[0]])                  # 주축에 수직
        if (c - g[:2]) @ side < 0:
            side = -side                                # 시위 쪽: 쥐는 자리는 활대가 가장 휜 꼭대기라 나머지 칸 (활대 끝·시위) 은 시위 쪽에 있다
        tip = np.array([-side[1], side[0]])             # Z × 옆
    else:
        proj = (pts - g[:2]) @ a
        tip = a if proj.max() >= -proj.min() else -a
    return np.round(np.array([tip[0], tip[1], 0.0]), 6)


def check_frames(masks, g, errs):
    """FRAME (손으로 적은 그림 축) 을 jar 그림에서 다시 셈한 끝 방향과 견준다."""
    for name, sprite in (("handheld", "iron_sword"), ("mace", "mace"), ("spear", "iron_spear_in_hand"), ("bow", "bow")):
        want = np.array(FRAME[name]["tip"], float)
        want /= np.linalg.norm(want)
        got = sprite_tip(masks[sprite], g[name], name)
        if np.max(np.abs(got - want)) > 1e-6:
            errs.append(f"FRAME[{name!r}] 끝 {np.round(want, 3).tolist()} 이 jar 그림 {sprite} 의 주축에서 셈한 끝 {got.tolist()} 와 다르다")
        side = np.array(FRAME[name]["side"], float)
        side /= np.linalg.norm(side)
        if np.max(np.abs(np.cross(side, want) - np.array([0, 0, 1]))) > 1e-6:
            errs.append(f"FRAME[{name!r}]: 옆·끝·앞이 오른손 좌표가 아니다 (옆 × 끝 ≠ +Z: 모형이 거울로 뒤집힌다)")


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
            _json(os.path.join(out, "assets", "minecraft", "atlases", "items.json"), SHIELD_ATLAS)
            _json(os.path.join(models, name + ".json"), {"textures": {"s": SHIELD_SPRITE, "particle": SHIELD_SPRITE},
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
    check_frames(masks, g, errs)
    # 3. 무기 모형
    models = os.path.join(out, "assets", NS, "models", "item")
    items = os.path.join(out, "assets", NS, "items")
    n_models = 0
    checked = set()
    kinds = weapon_kinds()
    for wid, kind in sorted(kinds.items()):
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
            checked.add(m)
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
            checked.add(m)
            n_models += 1
    check_probe_geometry(models, masks, g, errs)
    # 9. 손 맥락 display 는 검사한 모형에만
    for f in sorted(os.listdir(models)) if os.path.isdir(models) else []:
        own = _load(os.path.join(models, f)).get("display", {}) if f.endswith(".json") else {}
        if f.endswith(".json") and f[:-5] not in checked and any(c in own for c in HANDS):
            errs.append(f"models/item/{f}: 바닐라와 견주지 않은 손 맥락 display {sorted(c for c in own if c in HANDS)} "
                        "(손에 든 자세는 바닐라 그대로다: 무기 모형이면 weapon_kinds 에, 아니면 display 를 뺀다)")
    # 6·7·8. 플러그인 껍데기, 아이템 정의 길, 모양
    check_plugin(kinds, errs)
    n_routes = check_routes(items, kinds, z, errs)
    n_geo = check_geometry(models, kinds, errs)
    # 방패 시험 모형의 그림: items 아틀라스에 다른 이름으로 실었는가 (없으면 클라이언트가 "Missing textures" 로 보라·검정 칸을 그린다)
    atlas = os.path.join(out, "assets", "minecraft", "atlases", "items.json")
    srcs = _load(atlas).get("sources", []) if os.path.exists(atlas) else []
    if SHIELD_ATLAS["sources"][0] not in srcs:
        errs.append(f"assets/minecraft/atlases/items.json: 방패 시험 그림 소스 {SHIELD_ATLAS['sources'][0]} 가 없다")
    # 4. 무기 막기 모형 (<id>_guard) 없음 (시험 막기 도구 souls:test_guard 는 무기가 아니다), 아이템 정의의 감싸기
    guards = {f"{NS}:item/{wid}_guard" for wid in kinds} | {f"{NS}:item/{wid}_guard_m" for wid in kinds}
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
    notes.append(f"아이템 정의 {len(kinds) + len(PROBE)}개를 {n_routes}가지 상태로 풀었다, 모형 {n_geo}개의 쥐는 점·긴 축, "
                 f"weapons.yml·ItemFactory.SPEAR_CLASSES 와 껍데기")
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
