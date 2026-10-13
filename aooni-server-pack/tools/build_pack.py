"""아오오니 저택 서버팩 생성기.

이 스크립트 하나가 데이터팩 전체(저택 건축 명령 + 게임 로직)를 만든다.
좌표가 건축과 로직 양쪽에 쓰이므로 한곳에서 생성해 어긋남을 막는다.

  python tools/build_pack.py            # 데이터팩 생성 + 구조 점검 + 명령어 검사
  python tools/build_pack.py --no-validate

생성물: server/world/datapacks/aooni_mansion/
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK = os.path.join(ROOT, "server", "world", "datapacks", "aooni_mansion")
NS = "aooni"
BUILD_VERSION = 5          # 바꾸면 기존 월드도 다음 로드 때 다시 짓는다
PACK_MIN, PACK_MAX = 71, 121   # 1.21.5 ~ 26.3

# ------------------------------------------------------------------ 좌표 상수
Y1 = -61      # 1층 바닥
C1 = -56      # 1층 천장 = 2층 바닥
RF = -51      # 지붕
F1 = Y1 + 1   # 1층 발 높이 (-60)
F2 = C1 + 1   # 2층 발 높이 (-55)
X0, X1, Z0, Z1 = 0, 46, 0, 36

LOBBY = (-21, F1, 14)      # 대기실 스폰
SPAWN_POINTS = [(32, 32), (35, 32), (32, 34), (35, 34), (33, 30), (34, 30)]
JAIL = (5.5, F1, 33.5)
RELEASE = (5.5, F1, 26.5)
SPEC_POS = (23, -45, 18)

# ------------------------------------------------------------------ 출력 버퍼
FUNCS: dict[str, list[str]] = {}


def fn(name, *lines):
    buf = FUNCS.setdefault(name, [])
    for ln in lines:
        if isinstance(ln, (list, tuple)):
            buf.extend(ln)
        else:
            buf.append(ln)


def J(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def T(text, color=None, **kw):
    d = {"text": text}
    if color:
        d["color"] = color
    d.update(kw)
    return d


SEL = {"selector": "@s", "color": "aqua"}


def comp(*parts):
    parts = [T(p) if isinstance(p, str) else p for p in parts]
    if len(parts) == 1:
        return J(parts[0])
    return J({"text": "", "extra": parts})


def tell(target, *parts):
    return f"tellraw {target} {comp(*parts)}"


def actionbar(target, *parts):
    return f"title {target} actionbar {comp(*parts)}"


def num(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


def P(*xyz):
    return " ".join(num(v) for v in xyz)


def var(name):
    return f"{name} {NS}.var"


def sound_all(sound, pitch=1.0, vol=1.0, who="@a[tag=aooni.player]"):
    return f"execute as {who} at @s run playsound {sound} master @s ~ ~ ~ {num(vol)} {num(pitch)}"


# ------------------------------------------------------------------ 복셀 모델(구조 점검용)
WORLD: dict[tuple, str] = {}
BUILD: list[str] = []          # 저택 건축 명령
LOBBY_BUILD: list[str] = []    # 대기실 건축 명령
_target = BUILD


def target(buf):
    global _target
    _target = buf


def bid(block):
    return block.split("[")[0].replace("minecraft:", "")


def _rng(a, b):
    return range(min(a, b), max(a, b) + 1)


def fill(x1, y1, z1, x2, y2, z2, block, record=True):
    block = block if ":" in block else "minecraft:" + block
    vol = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
    if vol > 32768:   # 한 번에 너무 크면 x 로 반 나눈다
        mid = (min(x1, x2) + max(x1, x2)) // 2
        fill(min(x1, x2), y1, z1, mid, y2, z2, block, record)
        fill(mid + 1, y1, z1, max(x1, x2), y2, z2, block, record)
        return
    if (x1, y1, z1) == (x2, y2, z2):
        _target.append(f"setblock {P(x1, y1, z1)} {block}")
    else:
        _target.append(f"fill {P(x1, y1, z1, x2, y2, z2)} {block}")
    if record:
        for x in _rng(x1, x2):
            for y in _rng(y1, y2):
                for z in _rng(z1, z2):
                    WORLD[(x, y, z)] = block


def setb(x, y, z, block):
    fill(x, y, z, x, y, z, block)


def door_cmds(x, y, z, facing, hinge, open_, mat="iron_door", record=False):
    st = f"facing={facing},hinge={hinge},open={'true' if open_ else 'false'}"
    cmds = [f"fill {P(x, y, z, x, y + 1, z)} minecraft:air",
            f"setblock {P(x, y, z)} minecraft:{mat}[half=lower,{st}]",
            f"setblock {P(x, y + 1, z)} minecraft:{mat}[half=upper,{st}]"]
    if record:
        WORLD[(x, y, z)] = f"minecraft:{mat}[half=lower,{st}]"
        WORLD[(x, y + 1, z)] = f"minecraft:{mat}[half=upper,{st}]"
    return cmds


def door(x, y, z, facing, hinge, mat="iron_door", open_=False):
    _target.extend(door_cmds(x, y, z, facing, hinge, open_, mat, record=True))


# ------------------------------------------------------------------ 상호작용(버튼) 등록
ACTS = []   # (id, x, y, z, state, scope) scope: lobby|game


def button(aid, x, y, z, face, facing, kind="stone_button", scope="game"):
    state = f"minecraft:{kind}[face={face},facing={facing},powered=false]"
    setb(x, y, z, state)
    ACTS.append((aid, x, y, z, state, kind, scope))


SAFES = {}   # 금고 번호 -> 버튼/표시 위치


def safe_panel(s, axis, w, yf, start, fd, label):
    """벽(axis 방향 좌표 w)에 4자리 다이얼 봉인 자물쇠를 단다. fd=+1/-1 은 버튼이 붙는 쪽."""
    if axis == "z":
        facing = "south" if fd > 0 else "north"
        yaw = 0 if fd > 0 else 180
        tz = w + 1.15 if fd > 0 else w - 0.15   # 버튼 앞면(0.125)보다 앞에
        fill(start - 1, yf, w, start + 5, yf + 2, w, "iron_block")
        fill(start, yf + 1, w, start + 4, yf + 1, w, "polished_deepslate")
        cells = [(start + k, w + fd) for k in range(5)]
        tpos = [(x + 0.5, tz) for (x, _) in cells]
        lpos = (start + 2.5, tz)
    else:
        facing = "east" if fd > 0 else "west"
        yaw = -90 if fd > 0 else 90
        tx = w + 1.15 if fd > 0 else w - 0.15
        fill(w, yf, start - 1, w, yf + 2, start + 5, "iron_block")
        fill(w, yf + 1, start, w, yf + 1, start + 4, "polished_deepslate")
        cells = [(w + fd, start + k) for k in range(5)]
        tpos = [(tx, z + 0.5) for (_, z) in cells]
        lpos = (tx, start + 2.5)
    rot = f",Rotation:[{yaw}f,0f]"
    for k in range(4):
        x, z = cells[k]
        button(f"safe{s}_d{k + 1}", x, yf + 1, z, "wall", facing, "polished_blackstone_button")
        text(tpos[k][0], yf + 1.4, tpos[k][1], T("0", "white", bold=True), "aooni.fx", f"aooni.dial{s}{k + 1}",
             scale=0.7, billboard="fixed", extra=rot)
    x, z = cells[4]
    button(f"safe{s}_ok", x, yf + 1, z, "wall", facing, "stone_button")
    text(tpos[4][0], yf + 1.4, tpos[4][1], T("확인", "green"), "aooni.fx", scale=0.5, billboard="fixed", extra=rot)
    text(lpos[0], yf + 2.45, lpos[1], T(label, "gold"), "aooni.fx", f"aooni.safe{s}", scale=0.5, billboard="fixed", extra=rot)
    SAFES[s] = {"ok": cells[4]}


# 옷장(숨는 곳)
CLOSETS = []
DIRS = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
OPP_FACING = {"E": "west", "W": "east", "S": "north", "N": "south"}


def closet(x, y0, z, d):
    dx, dz = DIRS[d]
    px, pz = abs(dz), abs(dx)
    cells = [(x, z), (x + dx, z + dz)]
    for cx, cz in cells:
        for s in (-1, 1):
            fill(cx + px * s, y0, cz + pz * s, cx + px * s, y0 + 1, cz + pz * s, "spruce_planks")
        fill(cx, y0, cz, cx, y0 + 1, cz, "air")
    xs = [c[0] for c in cells]
    zs = [c[1] for c in cells]
    fill(min(xs) - px, y0 + 2, min(zs) - pz, max(xs) + px, y0 + 2, max(zs) + pz, "spruce_planks")
    door(x + dx, y0, z + dz, OPP_FACING[d], "left", mat="spruce_door")
    CLOSETS.append({"inside": (x, y0, z), "door": (x + dx, y0, z + dz), "facing": OPP_FACING[d],
                    "out": (x + 2 * dx + 0.5, y0, z + 2 * dz + 0.5),
                    "box": (min(xs), y0, min(zs), max(xs) - min(xs), 1, max(zs) - min(zs))})


MARKERS = []   # (x, y, z, tags)
TEXTS = []     # (x, y, z, text_component_dict, tags, extra_nbt)


def marker(x, y, z, *tags):
    MARKERS.append((x + 0.5, y, z + 0.5, list(tags)))


def text(x, y, z, comp_, *tags, scale=0.7, billboard="vertical", extra=""):
    TEXTS.append((x, y, z, comp_, list(tags), scale, billboard, extra))


# ================================================================== 저택 건축
def build_mansion():
    target(BUILD)
    # 0) 부지 정리 + 땅
    fill(-3, F1, -3, 49, -44, 49, "air")
    fill(-3, Y1, -3, 49, Y1, 49, "grass_block")
    fill(-3, Y1 - 1, -3, 49, Y1 - 1, 49, "dirt")

    # 1) 바닥/외벽/천장/지붕
    fill(X0, Y1, Z0, X1, Y1, Z1, "dark_oak_planks")
    for (a, b, c, d) in [(X0, Z0, X1, Z0), (X0, Z1, X1, Z1), (X0, Z0, X0, Z1), (X1, Z0, X1, Z1)]:
        fill(a, Y1, b, c, Y1, d, "stone_bricks")
        fill(a, F1, b, c, RF - 1, d, "dark_oak_planks")
    fill(X0, C1, Z0, X1, C1, Z1, "dark_oak_planks")
    fill(X0, RF, Z0, X1, RF, Z1, "deepslate_tiles")
    for (a, b, c, d) in [(X0 - 1, Z0 - 1, X1 + 1, Z0 - 1), (X0 - 1, Z1 + 1, X1 + 1, Z1 + 1),
                         (X0 - 1, Z0 - 1, X0 - 1, Z1 + 1), (X1 + 1, Z0 - 1, X1 + 1, Z1 + 1)]:
        fill(a, RF, b, c, RF, d, "deepslate_tile_slab[type=top]")
    for (a, b, c, d) in [(X0, Z0, X1, Z0), (X0, Z1, X1, Z1), (X0, Z0, X0, Z1), (X1, Z0, X1, Z1)]:
        fill(a, RF + 1, b, c, RF + 1, d, "deepslate_brick_wall")
    # 외벽 기둥
    for (x, z) in [(0, 0), (46, 0), (0, 36), (46, 36), (14, 0), (22, 0), (36, 0), (10, 36), (18, 36),
                   (30, 36), (37, 36), (0, 12), (0, 17), (46, 12), (46, 17)]:
        fill(x, F1, z, x, RF - 1, z, "dark_oak_log")
    # 1층/2층 경계 띠
    for (a, b, c, d) in [(X0, Z0, X1, Z0), (X0, Z1, X1, Z1), (X0, Z0, X0, Z1), (X1, Z0, X1, Z1)]:
        fill(a, C1, b, c, C1, d, "stripped_dark_oak_wood")

    wall = "stripped_spruce_wood"

    # 2) 1층 칸막이
    fill(X0, F1, 12, X1, C1 - 1, 12, wall)
    fill(X0, F1, 17, X1, C1 - 1, 17, wall)
    for x in (14, 22, 36):
        fill(x, F1, Z0, x, C1 - 1, 12, wall)
    for x in (10, 18, 30, 37):
        fill(x, F1, 17, x, C1 - 1, Z1, wall)
    # 감옥 벽은 돌벽돌
    fill(0, F1, 17, 10, C1 - 1, 17, "stone_bricks")
    fill(10, F1, 17, 10, C1 - 1, 36, "stone_bricks")

    def gap(x1, z1, x2, z2, y=F1, h=3):
        fill(x1, y, z1, x2, y + h - 1, z2, "air")

    gap(36, 5, 36, 6)           # 식당 ↔ 피아노실
    gap(5, 17, 6, 17)           # 감옥
    gap(14, 17, 14, 17)         # 화장실
    gap(23, 17, 25, 17)         # 거실
    gap(32, 17, 35, 17)         # 현관홀
    gap(41, 17, 42, 17)         # 주방
    gap(30, 26, 30, 27)         # 거실 ↔ 현관홀
    gap(37, 30, 37, 31)         # 현관홀 ↔ 주방

    # 3) 2층 칸막이
    fill(X0, F2, 12, X1, RF - 1, 12, wall)
    fill(X0, F2, 17, X1, RF - 1, 17, wall)
    for x in (14, 22, 36):
        fill(x, F2, Z0, x, RF - 1, 12, wall)
    for x in (14, 30):
        fill(x, F2, 17, x, RF - 1, Z1, wall)
    gap(7, 12, 7, 12, F2)        # 안방
    gap(20, 12, 21, 12, F2)      # 계단실 → 2층 복도
    gap(29, 12, 29, 12, F2)      # 손님방
    gap(14, 3, 14, 4, F2)        # 계단 층계참 ↔ 안방
    gap(22, 3, 22, 4, F2)        # 계단 층계참 ↔ 손님방
    gap(7, 17, 7, 17, F2)        # 아이방
    gap(22, 17, 23, 17, F2)      # 작업실
    gap(38, 17, 38, 17, F2)      # 다락방
    gap(14, 25, 14, 26, F2)      # 아이방 ↔ 작업실
    gap(30, 30, 30, 31, F2)      # 작업실 ↔ 다락방

    # 4) 계단실 (x15..21, z1..11, 2개 층 높이)
    fill(15, F1, 1, 21, C1 - 1, 11, "stone_bricks")
    fill(16, F1, 11, 17, C1 - 1, 11, "air")
    for k, z in enumerate([10, 9, 8, 7, 6]):
        y = F1 + k
        fill(16, y, z, 17, y, z, "dark_oak_stairs[facing=north]")
        if y + 1 <= C1:
            fill(16, y + 1, z, 17, C1, z, "air")
    fill(16, C1, 7, 17, C1, 10, "air")
    fill(15, F2, 6, 15, F2, 10, "dark_oak_fence")
    fill(18, F2, 6, 18, F2, 10, "dark_oak_fence")
    fill(16, F2, 11, 17, F2, 11, "dark_oak_fence")
    setb(19, RF - 1, 3, "lantern[hanging=true]")
    setb(17, C1 - 1, 11, "soul_lantern[hanging=true]")
    fill(16, F1, 12, 17, F1 + 2, 12, "air")      # 계단실 입구 (높이 3칸)
    text(17.0, F1 + 2.75, 13.2, T("계단", "gray"), "aooni.fx")

    # 5) 1층 복도
    fill(1, F1, 14, 45, F1, 15, "red_carpet")
    for i, x in enumerate(range(4, 46, 8)):
        setb(x, C1 - 1, 14 + (i % 2), "soul_lantern[hanging=true]")
    setb(1, F1, 13, "potted_dead_bush")
    setb(45, F1, 16, "potted_dead_bush")

    # 6) 서재 (x1..13, z1..11) — 잠김
    fill(1, Y1, 1, 13, Y1, 11, "spruce_planks")
    fill(1, F1, 1, 1, C1 - 1, 11, "bookshelf")
    fill(1, F1, 1, 13, C1 - 1, 1, "bookshelf")
    fill(4, F1, 5, 9, F1 + 1, 5, "bookshelf")
    fill(4, F1, 8, 9, F1 + 1, 8, "bookshelf")
    fill(11, F1, 3, 12, F1, 3, "dark_oak_planks")
    setb(11, F1, 4, "dark_oak_stairs[facing=south]")
    setb(12, F1 + 1, 3, "candle[candles=3,lit=true]")
    setb(7, C1 - 1, 6, "soul_lantern[hanging=true]")
    setb(12, C1 - 1, 6, "lantern[hanging=true]")
    button("s_lib_desk", 11, F1 + 1, 3, "floor", "north", "polished_blackstone_button")
    button("s_lib_sheet", 2, F1 + 1, 9, "wall", "east", "polished_blackstone_button")
    button("s_lib_diary", 5, F1 + 1, 7, "wall", "north", "polished_blackstone_button")
    closet(13, F1, 10, "W")
    fill(7, F1, 12, 7, F1 + 2, 12, "air")        # 서재 입구
    text(7.5, F1 + 2.75, 13.2, T("서재", "gray"), "aooni.fx")

    # 7) 식당 (x23..35, z1..11) — 잠김
    fill(23, Y1, 1, 35, Y1, 11, "dark_oak_planks")
    fill(25, F1, 4, 33, F1, 8, "red_carpet")
    fill(25, F1, 6, 33, F1, 6, "dark_oak_slab[type=top]")
    for x in (26, 28, 30, 32):
        setb(x, F1, 5, "spruce_stairs[facing=north]")
        setb(x, F1, 7, "spruce_stairs[facing=south]")
    setb(27, F1 + 1, 6, "candle[candles=3,lit=true]")
    setb(31, F1 + 1, 6, "candle[candles=2,lit=true]")
    setb(29, C1 - 1, 6, "lantern[hanging=true]")
    button("s_din_plate", 29, F1 + 1, 6, "floor", "north", "polished_blackstone_button")
    button("s_din_candle", 25, F1 + 1, 6, "floor", "north", "polished_blackstone_button")
    closet(35, F1, 10, "W")
    for x in (26, 27, 31, 32):
        fill(x, F1 + 1, 0, x, F1 + 2, 0, "glass_pane")
    fill(29, F1, 12, 29, F1 + 2, 12, "air")      # 식당 입구
    text(29.5, F1 + 2.75, 13.2, T("식당", "gray"), "aooni.fx")

    # 8) 피아노실 (x37..45, z1..11)
    fill(37, Y1, 1, 45, Y1, 11, "stripped_dark_oak_wood")
    fill(38, F1, 1, 44, F1 + 1, 1, "black_concrete")
    fill(38, F1, 2, 38, F1, 2, "black_concrete")
    fill(44, F1, 2, 44, F1, 2, "black_concrete")
    fill(39, F1, 2, 43, F1, 2, "white_concrete")
    notes = ["도", "레", "미", "파", "솔"]
    for i, x in enumerate(range(39, 44)):
        button(f"piano{i + 1}", x, F1 + 1, 2, "floor", "north", "polished_blackstone_button")
        text(x + 0.5, F1 + 1.45, 2.5, T(notes[i], "white"), "aooni.fx", scale=0.6)
    setb(41, F1 + 2, 1, "black_concrete")
    setb(41, C1 - 1, 6, "lantern[hanging=true]")
    closet(45, F1, 10, "W")
    fill(46, F1 + 1, 5, 46, F1 + 2, 6, "glass_pane")
    text(36.5, F1 + 2.75, 5.9, T("피아노실", "gray"), "aooni.fx")

    # 9) 감옥 (x1..9, z18..35)
    fill(1, Y1, 18, 9, Y1, 35, "cobblestone")
    for (x, z) in [(2, 20), (7, 22), (3, 26), (8, 28), (4, 32), (8, 34), (2, 30)]:
        setb(x, Y1, z, "mossy_cobblestone")
    fill(1, F1, 30, 9, C1 - 1, 30, "iron_bars")
    door(5, F1, 30, "north", "left")
    setb(5, C1 - 1, 24, "lantern[hanging=true]")
    setb(5, C1 - 1, 33, "soul_lantern[hanging=true]")
    setb(1, C1 - 1, 18, "cobweb")
    setb(9, C1 - 1, 18, "cobweb")
    setb(1, C1 - 1, 35, "cobweb")
    setb(8, F1, 19, "chiseled_stone_bricks")
    button("s_jail_note", 8, F1 + 1, 19, "floor", "north", "polished_blackstone_button")
    button("rescue", 2, F1 + 1, 18, "wall", "south", "stone_button")
    text(2.5, F1 + 1.9, 18.35, T("감옥 문 열기", "yellow"), "aooni.fx", scale=0.55)
    text(5.5, F1 + 2.75, 16.8, T("감옥", "gray"), "aooni.fx")

    # 10) 화장실 (x11..17, z18..35)
    fill(11, Y1, 18, 17, Y1, 35, "polished_diorite")
    fill(11, F1, 33, 11, F1, 35, "smooth_quartz")
    fill(13, F1, 33, 13, F1, 35, "smooth_quartz")
    fill(12, F1, 33, 12, F1, 35, "water_cauldron[level=3]")
    setb(16, F1, 35, "cauldron")
    setb(17, F1, 22, "polished_diorite")
    fill(17, F1 + 2, 21, 17, F1 + 3, 23, "light_gray_stained_glass")
    button("s_bath_mirror", 17, F1 + 1, 22, "floor", "north", "polished_blackstone_button")
    button("s_bath_tub", 11, F1 + 1, 34, "floor", "north", "polished_blackstone_button")
    setb(14, C1 - 1, 27, "lantern[hanging=true]")
    closet(11, F1, 24, "E")
    text(14.5, F1 + 2.75, 16.8, T("화장실", "gray"), "aooni.fx")

    # 11) 거실 (x19..29, z18..35)
    fill(19, Y1, 18, 29, Y1, 35, "spruce_planks")
    fill(21, F1, 24, 27, F1, 30, "red_carpet")
    fill(19, F1, 26, 19, C1 - 1, 30, "bricks")
    fill(19, F1, 27, 19, F1 + 1, 29, "air")
    setb(19, F1, 28, "lantern")
    setb(24, F1, 27, "dark_oak_stairs[facing=east]")
    setb(24, F1, 28, "dark_oak_stairs[facing=east]")
    setb(24, F1, 29, "dark_oak_stairs[facing=east]")
    fill(22, F1, 27, 22, F1, 29, "spruce_slab[type=top]")
    fill(26, F1, 35, 27, F1 + 1, 35, "dark_oak_planks")
    setb(27, F1 + 2, 35, "flower_pot")
    fill(29, F1, 19, 29, F1 + 2, 19, "dark_oak_log")
    setb(24, C1 - 1, 28, "lantern[hanging=true]")
    button("s_liv_cab", 26, F1 + 2, 35, "floor", "north", "polished_blackstone_button")
    button("s_liv_fire", 20, F1 + 1, 26, "wall", "east", "polished_blackstone_button")
    button("s_liv_clock", 28, F1 + 1, 19, "wall", "west", "polished_blackstone_button")
    closet(19, F1, 20, "E")
    fill(21, F1 + 1, 36, 22, F1 + 2, 36, "glass_pane")
    text(24.5, F1 + 2.75, 16.8, T("거실", "gray"), "aooni.fx")

    # 12) 현관홀 (x31..36, z18..35)
    fill(31, Y1, 18, 36, Y1, 35, "polished_andesite")
    fill(33, F1, 18, 34, F1, 35, "red_carpet")
    for (x, z) in [(31, 21), (36, 21), (31, 33), (36, 33)]:
        fill(x, F1, z, x, C1 - 1, z, "stripped_dark_oak_log")
    setb(36, F1, 25, "polished_andesite")
    setb(36, F1, 24, "potted_wither_rose")
    setb(33, C1 - 1, 26, "lantern[hanging=true]")
    button("s_hall_vase", 36, F1 + 1, 25, "floor", "north", "polished_blackstone_button")
    button("s_hall_photo", 31, F1 + 1, 29, "wall", "east", "polished_blackstone_button")
    door(33, F1, 36, "north", "left")
    door(34, F1, 36, "north", "right")
    button("d_front", 31, F1 + 1, 35, "wall", "north")
    text(33.95, F1 + 2.6, 35.3, T("현관문", "gold"), "aooni.fx")
    text(33.95, F1 + 2.75, 16.8, T("현관홀", "gray"), "aooni.fx")

    # 13) 주방 (x38..45, z18..35)
    fill(38, Y1, 18, 45, Y1, 35, "smooth_stone")
    fill(45, F1, 20, 45, F1, 28, "polished_andesite")
    setb(45, F1, 24, "water_cauldron[level=3]")
    setb(45, F1, 21, "polished_deepslate")
    setb(45, F1, 26, "polished_blackstone_bricks")
    fill(45, F1, 30, 45, F1 + 1, 30, "iron_block")
    fill(41, F1, 25, 42, F1, 27, "spruce_slab[type=top]")
    setb(40, F1, 26, "spruce_stairs[facing=west]")
    setb(43, F1, 26, "spruce_stairs[facing=east]")
    setb(41, C1 - 1, 26, "lantern[hanging=true]")
    button("s_kit_fridge", 44, F1 + 1, 30, "wall", "west", "polished_blackstone_button")
    button("s_kit_sink", 45, F1 + 1, 23, "floor", "north", "polished_blackstone_button")
    closet(38, F1, 34, "E")
    fill(46, F1 + 1, 33, 46, F1 + 2, 34, "glass_pane")
    text(41.95, F1 + 2.75, 16.8, T("주방", "gray"), "aooni.fx")

    # ---------------- 2층
    fill(1, F2, 14, 45, F2, 15, "blue_carpet")
    for x in (6, 18, 30, 42):
        setb(x, RF - 1, 14, "soul_lantern[hanging=true]")

    # 안방 (x1..13, z1..11)
    fill(2, F2, 2, 3, F2, 4, "red_wool")
    fill(2, F2, 2, 3, F2, 2, "white_wool")
    setb(5, F2, 2, "spruce_planks")
    button("s_mb_diary", 5, F2 + 1, 2, "floor", "north", "polished_blackstone_button")
    setb(7, RF - 1, 6, "lantern[hanging=true]")
    closet(13, F2, 8, "W")
    fill(7, F2 + 1, 0, 8, F2 + 2, 0, "glass_pane")
    text(7.5, F2 + 2.75, 13.2, T("안방", "gray"), "aooni.fx")

    # 손님방 (x23..35, z1..11)
    fill(24, F2, 2, 25, F2, 4, "blue_wool")
    fill(28, F2, 2, 29, F2, 4, "blue_wool")
    setb(33, F2, 9, "brown_wool")
    button("s_gr_bag", 33, F2 + 1, 9, "floor", "north", "polished_blackstone_button")
    setb(29, RF - 1, 6, "lantern[hanging=true]")
    closet(35, F2, 2, "W")
    fill(31, F2 + 1, 0, 32, F2 + 2, 0, "glass_pane")
    text(29.5, F2 + 2.75, 13.2, T("손님방", "gray"), "aooni.fx")

    # 창고 (x37..45, z1..11) — 발판 퍼즐로 열림
    fill(37, C1, 1, 45, C1, 11, "spruce_planks")
    safe_panel(4, "z", 0, F2, 39, 1, "마검 금고 · 비밀번호 4자리")   # 북쪽 벽, 남쪽을 바라봄
    setb(44, F2, 10, "spruce_planks")
    setb(43, F2, 10, "spruce_planks")
    setb(45, F2, 7, "hay_block")
    button("s_sto_box", 44, F2 + 1, 10, "floor", "north", "polished_blackstone_button")
    setb(41, RF - 1, 6, "lantern[hanging=true]")
    setb(45, RF - 1, 1, "cobweb")
    closet(37, F2, 10, "E")
    fill(46, F2 + 1, 5, 46, F2 + 2, 6, "glass_pane")
    fill(41, F2, 12, 41, F2 + 2, 12, "air")      # 창고 입구
    text(41.5, F2 + 2.75, 13.2, T("창고", "gray"), "aooni.fx")

    # 아이방 (x1..13, z18..35)
    fill(1, C1, 18, 13, C1, 35, "birch_planks")
    fill(3, F2, 27, 7, F2, 31, "light_blue_carpet")
    fill(2, F2, 34, 3, F2, 35, "pink_wool")
    setb(10, F2, 19, "pink_wool")
    setb(8, F2, 34, "white_wool")
    button("s_kid_toy", 10, F2 + 1, 19, "floor", "north", "polished_blackstone_button")
    button("s_kid_draw", 1, F2 + 1, 24, "wall", "east", "polished_blackstone_button")
    setb(7, RF - 1, 27, "lantern[hanging=true]")
    closet(13, F2, 33, "W")
    fill(6, F2 + 1, 36, 7, F2 + 2, 36, "glass_pane")
    text(7.5, F2 + 2.75, 16.8, T("아이방", "gray"), "aooni.fx")

    # 작업실 (x15..29, z18..35)
    fill(15, C1, 18, 29, C1, 35, "spruce_planks")
    fill(29, F2, 23, 29, F2 + 2, 28, "bookshelf")
    fill(20, F2, 34, 21, F2, 34, "dark_oak_planks")
    setb(20, F2, 33, "dark_oak_stairs[facing=south]")
    setb(24, F2, 22, "lectern[facing=south]")
    button("s_st_note", 20, F2 + 1, 34, "floor", "north", "polished_blackstone_button")
    setb(22, RF - 1, 26, "lantern[hanging=true]")
    closet(15, F2, 21, "E")
    fill(24, F2 + 1, 36, 25, F2 + 2, 36, "glass_pane")
    text(22.95, F2 + 2.75, 16.8, T("작업실", "gray"), "aooni.fx")

    # 다락방 (x31..45, z18..35)
    fill(31, C1, 18, 45, C1, 35, "stripped_spruce_wood")
    for (x, z) in [(31, 18), (45, 18), (31, 35), (45, 35), (38, 35)]:
        setb(x, RF - 1, z, "cobweb")
    setb(40, F2, 33, "spruce_planks")
    setb(34, F2, 24, "spruce_stairs[facing=west]")
    button("s_spare_mirror", 40, F2 + 1, 33, "floor", "north", "polished_blackstone_button")
    setb(38, RF - 1, 26, "soul_lantern[hanging=true]")
    closet(45, F2, 27, "W")
    fill(36, F2 + 1, 36, 37, F2 + 2, 36, "glass_pane")
    fill(42, F2 + 1, 36, 43, F2 + 2, 36, "glass_pane")
    text(38.5, F2 + 2.75, 16.8, T("다락방", "gray"), "aooni.fx")

    # 굴뚝
    fill(19, RF + 1, 28, 19, RF + 3, 28, "bricks")

    # 정원 (승리하면 현관문이 열린다)
    fill(33, Y1, 37, 34, Y1, 45, "dirt_path")
    for x in (26, 41):
        fill(x, F1, 37, x, F1 + 2, 46, "oak_leaves[persistent=true]")
    fill(26, F1, 46, 41, F1 + 2, 46, "oak_leaves[persistent=true]")
    fill(33, F1, 46, 34, F1 + 2, 46, "iron_bars")
    for x in (30, 37):
        fill(x, F1, 40, x, F1 + 1, 40, "dark_oak_fence")
        setb(x, F1 + 2, 40, "lantern")
    text(33.95, F1 + 3.3, 45.5, T("아침이다…", "gold", bold=True), "aooni.fx", scale=1.0)


def build_lobby():
    target(LOBBY_BUILD)
    fill(-30, F1, 2, -12, -48, 22, "air")
    fill(-30, Y1, 2, -12, Y1, 22, "grass_block")
    fill(-28, Y1, 4, -14, Y1, 20, "spruce_planks")
    fill(-28, F1, 4, -14, F1 + 4, 4, "stripped_spruce_wood")
    fill(-28, F1, 20, -14, F1 + 4, 20, "stripped_spruce_wood")
    fill(-28, F1, 4, -28, F1 + 4, 20, "stripped_spruce_wood")
    fill(-14, F1, 4, -14, F1 + 4, 20, "stripped_spruce_wood")
    fill(-28, F1 + 5, 4, -14, F1 + 5, 20, "spruce_planks")
    fill(-24, F1, 9, -18, F1, 17, "gray_carpet")
    for (x, z) in [(-25, 8), (-17, 8), (-25, 16), (-17, 16)]:
        setb(x, F1 + 4, z, "lantern[hanging=true]")
    for x in range(-26, -15, 2):
        setb(x, F1, 19, "spruce_stairs[facing=south]")
    setb(-23, F1 + 1, 4, "lime_concrete")
    setb(-21, F1 + 1, 4, "yellow_concrete")
    setb(-19, F1 + 1, 4, "light_blue_concrete")
    setb(-25, F1 + 1, 4, "red_concrete")
    setb(-27, F1 + 1, 4, "purple_concrete")
    setb(-17, F1 + 1, 4, "cyan_concrete")
    button("l_solo_oni", -27, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_solo", -17, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-26.5, F1 + 1.75, 5.3, T("혼자 연습\n(아오오니)", "light_purple"), "aooni.fx", scale=0.45)
    text(-16.5, F1 + 1.75, 5.3, T("혼자 연습\n(생존자)", "aqua"), "aooni.fx", scale=0.45)
    button("l_want", -25, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-24.5, F1 + 1.75, 5.3, T("아오오니 지원", "red"), "aooni.fx", scale=0.5)
    text(-24.5, F1 + 0.55, 5.3, T("지원자 0명", "red"), "aooni.fx", "aooni.t_want", scale=0.45)
    button("l_start", -23, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_diff", -21, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_rules", -19, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-22.5, F1 + 1.75, 5.3, T("▶ 게임 시작", "green"), "aooni.fx", scale=0.5)
    text(-20.5, F1 + 1.75, 5.3, T("난이도 변경", "yellow"), "aooni.fx", scale=0.5)
    text(-18.5, F1 + 1.75, 5.3, T("규칙 보기", "aqua"), "aooni.fx", scale=0.5)
    text(-20.5, F1 + 3.3, 5.5, T("아오오니 저택", "blue", bold=True), "aooni.fx", scale=1.6)
    text(-20.5, F1 + 2.85, 5.5, T("4~6인 · 아오오니 1명 vs 생존자 · 비밀번호 4자리 → 마검 → 아오오니 족치기", "gray"), "aooni.fx", scale=0.6)
    text(-20.5, F1 + 2.45, 5.5, T("난이도: 보통", "yellow"), "aooni.fx", "aooni.t_diff", scale=0.7)
    text(-20.5, F1 + 2.15, 5.5, T("접속 인원: 0명", "white"), "aooni.fx", "aooni.t_count", scale=0.6)
    rules = ("한 명은 아오오니, 나머지는 생존자! (아오오니 지원 버튼)\n"
             "· 생존자: 검은 버튼을 눌러 저택을 뒤져 비밀번호 숫자 4개를 찾자\n"
             "· 2층 창고 금고에 비밀번호를 넣으면 마검! 마검으로만 아오오니를 벨 수 있다\n"
             "· 아오오니: 20초 뒤 깨어나 생존자를 때려 잡는다. 문·버튼·옷장은 못 만진다\n"
             "· 잡히면 감옥행 → 동료가 감옥 입구 버튼으로 구출. 목숨을 다 잃으면 관전\n"
             "· 옷장(가문비 문)에 들어가 문을 닫으면 완전히 안전")
    text(-26.95, F1 + 2.2, 12.5, T(rules, "white"), "aooni.fx", scale=0.55,
         billboard="fixed", extra=",Rotation:[-90f,0f],line_width:400,alignment:\"left\"")


# ================================================================== 구조 점검 (BFS)
PASSABLE_SUFFIX = ("_carpet", "_pressure_plate", "_button", "air", "light", "cobweb", "candle")


def passable(block, doors_open, iron_open=set()):
    if block is None:
        return True
    b = bid(block)
    if b.endswith(PASSABLE_SUFFIX) or b in ("lantern", "soul_lantern") and "hanging=true" in block:
        return True
    if b.endswith("_door"):
        if b != "iron_door":
            return True   # 나무문은 손으로 연다
        return doors_open or "open=true" in block
    return False


def standable_on(block):
    if block is None:
        return False
    b = bid(block)
    return not (b.endswith(PASSABLE_SUFFIX) or "lantern" in b or b.endswith("_door"))


def reachable(start, doors_open, h=2):
    """키 h 칸짜리 플레이어가 걸어서 닿는 칸(발 위치) 집합."""
    seen = {start}
    q = deque([start])

    def ok(x, y, z):
        if not (-40 < x < 60 and -70 < y < -40 and -10 < z < 60):
            return False
        return (all(passable(WORLD.get((x, y + k, z)), doors_open) for k in range(h))
                and standable_on(WORLD.get((x, y - 1, z))))

    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                n = (x + dx, y + dy, z + dz)
                if n in seen:
                    continue
                if dy == 1 and not passable(WORLD.get((x, y + h, z)), doors_open):
                    continue
                if ok(*n):
                    seen.add(n)
                    q.append(n)
    return seen


def structure_checks():
    problems = []
    start = (33, F1, 30)
    closed = reachable(start, doors_open=False)
    opened = reachable(start, doors_open=True)
    # 처음부터 모든 방이 열려 있다(아오오니도 플레이어라 어디든 다닌다). 잠긴 곳은 감옥 칸과 현관문뿐.
    must_initial = {"복도": (20, F1, 14), "감옥 앞": (5, F1, 26), "화장실": (15, F1, 28), "거실": (25, F1, 32),
                    "주방": (41, F1, 30), "서재": (6, F1, 10), "식당": (24, F1, 9), "피아노실": (40, F1, 8),
                    "2층 복도": (10, F2, 14), "안방": (6, F2, 6), "손님방": (30, F2, 7), "창고": (40, F2, 8),
                    "아이방": (6, F2, 22), "작업실": (22, F2, 28), "다락방": (40, F2, 28),
                    "아오오니 시작점": (int(ONI_SPAWN[0]), F2, int(ONI_SPAWN[2]))}
    for name, p in must_initial.items():
        if p not in closed:
            problems.append(f"시작 시 {name} 에 갈 수 없음 {p}")
    giant = reachable((int(ONI_SPAWN[0]), F2, int(ONI_SPAWN[2])), doors_open=False, h=3)
    for name, p in must_initial.items():
        if p not in giant:
            problems.append(f"거대 아오오니(키 3칸)가 {name} 에 갈 수 없음 {p}")
    if (33, F1, 43) in closed:
        problems.append("현관문이 닫혀 있는데 정원으로 나갈 수 있음")
    if (33, F1, 43) not in opened:
        problems.append("현관문을 열어도 정원에 갈 수 없음")
    if (5, F1, 33) in closed:
        problems.append("감옥 안이 바깥과 연결됨(문이 닫혀 있는데도)")
    # 정원 밖으로 새는지
    for p in opened:
        if p[2] > 36 and not (27 <= p[0] <= 40 and p[2] <= 45):
            problems.append(f"정원 밖으로 나갈 수 있음 {p}")
            break
        if p[0] < -1 or p[0] > 47 or p[2] < -1:
            problems.append(f"저택 밖으로 나갈 수 있음 {p}")
            break
    for (x, y, z, tags) in MARKERS:
        bx, bz = int(x - 0.5), int(z - 0.5)
        if not passable(WORLD.get((bx, y, bz)), True) or not passable(WORLD.get((bx, y + 1, bz)), True):
            problems.append(f"마커가 막힌 칸에 있음 {tags} {(bx, y, bz)}")
        if "aooni.spawn" in tags and (bx, y, bz) not in opened:
            problems.append(f"스폰 지점에 갈 수 없음 {tags} {(bx, y, bz)}")
    for c in CLOSETS:
        if c["door"][:3] and (c["door"][0], c["door"][1], c["door"][2]) not in opened and c["inside"] not in opened:
            problems.append(f"옷장에 들어갈 수 없음 {c}")
    for (sx, sz) in SPAWN_POINTS:
        if (sx, F1, sz) not in closed:
            problems.append(f"시작 위치가 막힘 {(sx, sz)}")
    for (aid, x, y, z, state, kind, scope) in ACTS:
        face = state.split("face=")[1].split(",")[0]
        facing = state.split("facing=")[1].split(",")[0]
        if face == "floor":
            sup = (x, y - 1, z)
        else:
            dx, dz = {"north": (0, 1), "south": (0, -1), "east": (-1, 0), "west": (1, 0)}[facing]
            sup = (x + dx, y, z + dz)
        if not standable_on(WORLD.get(sup)) or bid(WORLD.get(sup, "air")).endswith("glass_pane"):
            problems.append(f"버튼 {aid} 이 붙을 블록이 없음 {sup}={WORLD.get(sup)}")
        # 버튼이 철문 옆이면 누를 때 문이 잠깐 열린다
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                for ddz in (-1, 0, 1):
                    for base in ((x, y, z), sup):
                        b = WORLD.get((base[0] + ddx, base[1] + ddy, base[2] + ddz))
                        if b and bid(b).endswith("_door") and abs(ddx) + abs(ddy) + abs(ddz) == 1:
                            problems.append(f"버튼 {aid} 의 신호가 문 {bid(b)} 에 닿음")
    return problems, len(closed), len(opened)


def ascii_map(y, x0=-1, x1=48, z0=-1, z1=47):
    rows = []
    for z in range(z0, z1):
        row = ""
        for x in range(x0, x1):
            b = WORLD.get((x, y, z))
            if b is None or bid(b) == "air":
                row += "."
            elif "door" in b:
                row += "D" if "iron" in b else "d"
            elif "button" in b:
                row += "b"
            elif "stairs" in b:
                row += "/"
            elif "carpet" in b or "pressure" in b:
                row += "_"
            else:
                row += "#"
        rows.append(row)
    return "\n".join(rows)


# ================================================================== 게임 로직
GAMERULES = [  # (옛 이름 ≤1.21.10, 새 이름 ≥1.21.11, 값, 선택)
    ("doDaylightCycle", "advance_time", "false", False),
    ("doWeatherCycle", "advance_weather", "false", False),
    ("doMobSpawning", "spawn_mobs", "false", False),
    ("doMobSpawning", "spawn_monsters", "false", False),
    ("mobGriefing", "mob_griefing", "false", False),
    ("fallDamage", "fall_damage", "false", False),
    ("keepInventory", "keep_inventory", "true", False),
    ("doEntityDrops", "entity_drops", "false", False),
    ("doMobLoot", "mob_drops", "false", False),
    ("doTileDrops", "block_drops", "false", False),
    ("showDeathMessages", "show_death_messages", "false", False),
    ("announceAdvancements", "show_advancement_messages", "false", False),
    ("commandBlockOutput", "command_block_output", "false", False),
    ("logAdminCommands", "log_admin_commands", "false", False),
    ("randomTickSpeed", "random_tick_speed", "0", False),
    ("spawnRadius", "respawn_radius", "0", False),
    ("doInsomnia", "spawn_phantoms", "false", False),
    ("doPatrolSpawning", "spawn_patrols", "false", False),
    ("doTraderSpawning", "spawn_wandering_traders", "false", False),
    ("doImmediateRespawn", "immediate_respawn", "true", False),
    ("naturalRegeneration", "natural_health_regeneration", "false", False),
    ("locatorBar", "locator_bar", "false", True),
    ("pvp", "pvp", "true", True),   # 1.21.11+ 게임룰. 그 전 버전은 server.properties 의 pvp=true
]

DIFF_NAMES = {1: ("쉬움", "green"), 2: ("보통", "yellow"), 3: ("어려움", "red")}
# 난이도: 생존자 목숨 수, 아오오니 신속 효과 단계(None = 없음)
DIFF = {1: dict(lives=3, speed=None), 2: dict(lives=2, speed=0), 3: dict(lives=1, speed=1)}
SPEED_TEXT = {None: "기본 속도", 0: "신속 I", 1: "신속 II"}
ONI_SPAWN = (38.5, F2, 27.5)        # 다락방
ONI_FREEZE = 20                     # 시작 후 아오오니가 못 움직이는 시간(초)
ONI_HP_BASE, ONI_HP_PER = 60, 20    # 마검이 나온 뒤 아오오니 체력 = 60 + 생존자 수 × 20
FINAL_SCALE = 1.3                   # 마검이 나오면 아오오니가 커진다
WEAPON_ITEM, WEAPON_NAME = "netherite_sword", "마검"
WEAPON_STRENGTH = 4                 # 힘 V → 한 방 약 23
VAULT_DROP = (41.5, F2 + 1, 3.5)    # 아오오니가 마검을 주우면 금고 앞으로 돌아간다
CIRC = {1: "①", 2: "②", 3: "③", 4: "④"}
ORD = {1: "첫째", 2: "둘째", 3: "셋째", 4: "넷째"}
NOTE_PITCH = {1: 0.707107, 2: 0.793701, 3: 0.890899, 4: 0.943874, 5: 1.059463}
# 조사 지점에서 나올 수 있는 물약(한 번 쓰면 끝)
BUFFS = {1: ("speed", 1, 20, "신속 물약", "몸이 가벼워졌다! (20초)"),
         2: ("invisibility", 0, 25, "투명 물약", "몸이 투명해졌다… (25초)"),
         3: ("night_vision", 0, 120, "손전등", "어둠 속이 잘 보인다 (2분)")}
NOTHING = ["아무것도 없었다.", "종이인 줄 알았는데… 그냥 영수증이다.", "돌멩이 하나. 비밀번호가 아니다.", "먼지만 풀썩 날린다."]
FLAVOR = {
    "s_lib_desk": "서재 책상 서랍을 뒤졌다.",
    "s_lib_sheet": "책장 사이를 더듬었다.",
    "s_lib_diary": "낡은 일기장: '이 집에는 무언가가 산다. 파랗고, 거대하고… 문을 잠가도 소용없다.'",
    "s_din_plate": "식탁 위 빈 접시를 들춰 봤다.",
    "s_din_candle": "촛불이 흔들린다. 누군가 방금 옆을 지나간 것처럼…",
    "s_jail_note": "벽에 손톱으로 긁은 글씨: '도망쳐… 파란… 숨어…'",
    "s_bath_mirror": "김 서린 거울을 손으로 닦았다.",
    "s_bath_tub": "욕조에 검푸른 물이 고여 있다.",
    "s_liv_cab": "장식장 서랍을 열었다.",
    "s_liv_fire": "벽난로 재 속을 뒤졌다. 타다 남은 사진 조각… '1999년 여름'",
    "s_liv_clock": "괘종시계가 멈춰 있다. 바늘은 3시 33분.",
    "s_hall_vase": "꽃병 속을 들여다봤다. 장미는 오래전에 시들었다.",
    "s_hall_photo": "가족사진. 아이의 얼굴만 검게 칠해져 있다…",
    "s_kit_fridge": "냉장고 문을 살짝 열었다…",
    "s_kit_sink": "싱크대를 뒤졌다. 식칼꽂이에 칼 하나가 비어 있다.",
    "s_mb_diary": "부부의 일기장을 넘겼다.",
    "s_gr_bag": "손님의 여행 가방을 열었다.",
    "s_sto_box": "낡은 상자. 아이 장난감이 가득하다.",
    "s_kid_toy": "장난감 상자를 뒤지자 오르골이 저절로 울린다…",
    "s_kid_draw": "크레파스로 그린 파란 괴물 그림.",
    "s_st_note": "작업실 책상 위 설계 메모: '녀석을 벨 수 있는 건 마검뿐… 금고는 창고에.'",
    "s_spare_mirror": "거울 속, 내 어깨 너머로 파란 무언가가… 돌아보니 아무도 없다.",
}
ALL_FLAGS = (["#sec", "#sp", "#cd", "#found", "#wpn", "#final", "#rescue_cd", "#freeze", "#oni_gone", "#bh",
              "#bhp_prev", "#half10", "#hp", "#amb", "#stall", "#a0", "#swlost", "#wmsg", "#hunt"] + [f"#d{k}" for k in range(1, 5)])

ONI_PARTS = [  # (블록, 크기xyz, 최소좌표xyz(발밑 기준), 밝기)
    # 다리·몸통·팔은 높이 1.2 아래 → 아오오니 본인 시야(눈높이 1.62)에 윗면이 들어오지 않는다
    ("blue_concrete", (0.26, 0.62, 0.28), (-0.28, 0.0, -0.14), 11),
    ("blue_concrete", (0.26, 0.62, 0.28), (0.02, 0.0, -0.14), 11),
    ("blue_concrete", (0.66, 0.60, 0.40), (-0.33, 0.60, -0.20), 11),
    ("blue_concrete", (0.20, 0.80, 0.22), (-0.53, 0.38, -0.11), 11),
    ("blue_concrete", (0.20, 0.80, 0.22), (0.33, 0.38, -0.11), 11),
    # 큰 머리가 눈높이를 감싼다(안쪽 면은 보이지 않음). 얼굴은 눈높이보다 0.38 이상 위 → 본인 화면 위쪽 밖
    ("blue_concrete", (0.90, 1.30, 0.84), (-0.45, 1.20, -0.42), 11),
    ("white_concrete", (0.24, 0.22, 0.04), (-0.32, 2.12, 0.42), 15),
    ("white_concrete", (0.24, 0.22, 0.04), (0.08, 2.12, 0.42), 15),
    ("black_concrete", (0.10, 0.10, 0.03), (-0.25, 2.18, 0.46), 15),
    ("black_concrete", (0.10, 0.10, 0.03), (0.15, 2.18, 0.46), 15),
    ("black_concrete", (0.50, 0.07, 0.03), (-0.25, 2.01, 0.42), 11),
]


def oni_model_cmds(scale):
    """아오오니 플레이어를 매 틱 따라다니는 블록 디스플레이 모형(플레이어 본체는 투명)."""
    out = ["kill @e[type=minecraft:block_display,tag=aooni.part]"]
    for blk, s, m, br in ONI_PARTS:
        t = f"[{m[0] * scale:.4f}f,{m[1] * scale:.4f}f,{m[2] * scale:.4f}f]"
        sc = f"[{s[0] * scale:.4f}f,{s[1] * scale:.4f}f,{s[2] * scale:.4f}f]"
        out.append('summon minecraft:block_display ~ ~ ~ {block_state:{Name:"minecraft:%s"},Tags:["aooni.fx","aooni.part"],'
                   'teleport_duration:1,brightness:{sky:%d,block:%d},transformation:{left_rotation:[0f,0f,0f,1f],'
                   'right_rotation:[0f,0f,0f,1f],translation:%s,scale:%s}}' % (blk, br, br, t, sc))
    return out


SURV = "@a[tag=aooni.player,tag=!aooni.oni_p]"
ONI = "@a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure]"
# 혼자 연습(생존자) 때만 나오는 연습용 아오오니(좀비 AI). 실전에는 절대 나오지 않는다.
DUMMY = "@e[type=minecraft:zombie,tag=aooni.dummy]"
DUMMY_SPEED = {1: 0.27, 2: 0.30, 3: 0.33}   # 걷는 플레이어 ≈ 0.31, 달리면 따돌릴 수 있음
DUMMY_HUNT = 6                              # 몇 초마다 가장 가까운 생존자 냄새를 맡는지


def logic():
    spots = [a for a in ACTS if a[0].startswith("s_")]
    assert set(FLAVOR) == {a[0] for a in spots}, set(FLAVOR) ^ {a[0] for a in spots}

    # ---------------- load / tick
    fn("load",
       "scoreboard objectives add aooni.var dummy",
       f"scoreboard objectives add aooni.side dummy {comp(T('아오오니 저택', 'blue', bold=True))}",
       "scoreboard objectives add aooni.lives dummy",
       "scoreboard objectives add aooni.gid dummy",
       "scoreboard objectives add aooni.leave minecraft.custom:minecraft.leave_game",
       "scoreboard objectives add aooni.grace dummy",
       "scoreboard objectives add aooni.deaths deathCount",
       "# 생존자가 아오오니에게 맞으면 저항 효과가 피해를 막으면서 이 통계가 오른다 → 잡힘 판정",
       "scoreboard objectives add aooni.hit minecraft.custom:minecraft.damage_resisted",
       "scoreboard objectives add aooni.wc dummy",
       "# 연습 끝내기: OP 가 아니어도 /trigger aooni.quit",
       "scoreboard objectives add aooni.quit trigger",
       "scoreboard objectives add aooni.kz minecraft.killed:minecraft.zombie",
       "team add aooni_alive",
       f"team modify aooni_alive displayName {comp(T('생존자', 'aqua'))}",
       "team modify aooni_alive color aqua",
       "team modify aooni_alive collisionRule never",
       "team modify aooni_alive friendlyFire false",
       "team modify aooni_alive nametagVisibility hideForOtherTeams",
       "team add aooni_oni",
       f"team modify aooni_oni displayName {comp(T('아오오니', 'dark_blue'))}",
       "team modify aooni_oni color dark_blue",
       "team modify aooni_oni collisionRule never",
       "team modify aooni_oni nametagVisibility never",
       "team modify aooni_oni seeFriendlyInvisibles false",
       "team modify aooni_oni friendlyFire false",
       "team add aooni_out",
       "team modify aooni_out color gray",
       "team modify aooni_out collisionRule never",
       "team add aooni_lobby",
       "team modify aooni_lobby friendlyFire false",
       "team modify aooni_lobby collisionRule never",
       f"bossbar add aooni:goal {comp(T('목표', 'white'))}",
       "bossbar set aooni:goal color blue",
       "bossbar set aooni:goal max 4",
       f"bossbar add aooni:boss {comp(T('아오오니', 'dark_red', bold=True))}",
       "bossbar set aooni:boss color red",
       "bossbar set aooni:boss style notched_10",
       "execute unless score #state aooni.var matches 0..2 run scoreboard players set #state aooni.var 0",
       "execute unless score #diff aooni.var matches 1..3 run scoreboard players set #diff aooni.var 2",
       "execute unless score #gid aooni.var matches 0.. run scoreboard players set #gid aooni.var 0",
       "execute unless score #test aooni.var matches 0..2 run scoreboard players set #test aooni.var 0",
       "scoreboard players set #t aooni.var 0",
       "scoreboard players set #60 aooni.var 60",
       "scoreboard players set #2 aooni.var 2",
       "function aooni:setup/gamerules",
       "time set 18000",
       "weather clear",
       "difficulty normal",
       f"setworldspawn {P(*LOBBY)}",
       "forceload add -32 -4 50 50",
       "schedule function aooni:setup/check_build 2s")
    for old, new, v, _ in GAMERULES:
        fn("setup/gamerules", f'function aooni:compat/gamerule {{o:"{old}",n:"{new}",v:"{v}"}}')
    fn("compat/gamerule",
       "# 1.21.11 에서 게임룰 이름이 바뀌었다. 두 이름을 모두 시도하고, 버전에 없는 쪽은 조용히 실패한다.",
       '$function aooni:compat/gamerule_try {r:"$(o)",v:"$(v)"}',
       '$function aooni:compat/gamerule_try {r:"$(n)",v:"$(v)"}')
    fn("compat/gamerule_try", "$gamerule $(r) $(v)")
    fn("setup/check_build",
       "execute unless loaded -30 -60 2 run return run schedule function aooni:setup/check_build 1s",
       "execute unless loaded 48 -60 48 run return run schedule function aooni:setup/check_build 1s",
       "execute unless loaded -30 -60 48 run return run schedule function aooni:setup/check_build 1s",
       "execute unless loaded 48 -60 -3 run return run schedule function aooni:setup/check_build 1s",
       "# 게임 도중에 다시 지으면 숨겨 둔 숫자·모형이 사라진다 → 판이 끝난 뒤에 짓는다",
       f"execute unless score #built aooni.var matches {BUILD_VERSION} unless score #state aooni.var matches 0 run return run schedule function aooni:setup/check_build 10s",
       f"execute unless score #built aooni.var matches {BUILD_VERSION} run function aooni:build/all",
       "execute if score #state aooni.var matches 0 run function aooni:lobby/show_diff")
    fn("build/all",
       "kill @e[tag=aooni.fx]",
       "kill @e[type=minecraft:zombie,tag=aooni.oni]",
       f"kill {DUMMY}",
       "function aooni:build/lobby",
       "function aooni:build/mansion",
       "function aooni:build/fixtures",
       "kill @e[type=minecraft:item]",
       f"scoreboard players set #built aooni.var {BUILD_VERSION}",
       "function aooni:lobby/show_diff",
       "execute if score #state aooni.var matches 0 as @a[gamemode=!creative] run function aooni:player/to_lobby",
       tell("@a", T("[아오오니 저택] ", "blue"), T("저택과 대기실을 지었습니다.", "gray")))
    fn("tick",
       "execute as @a[tag=!aooni.seen] run function aooni:player/first_join",
       "execute as @a[scores={aooni.leave=1..}] run function aooni:player/rejoin",
       "execute as @e[type=minecraft:player,scores={aooni.deaths=1..}] run function aooni:player/respawned",
       "function aooni:act/poll",
       "execute as @a[scores={aooni.quit=1..}] run function aooni:test/quit",
       "scoreboard players add #t aooni.var 1",
       "execute if score #t aooni.var matches 20.. run function aooni:sec",
       "execute if score #state aooni.var matches 1 run function aooni:game/tick")
    fn("sec",
       "scoreboard players set #t aooni.var 0",
       "execute if score #state aooni.var matches 2 run return run function aooni:game/ending_sec",
       "execute if score #state aooni.var matches 1 run return run function aooni:game/sec",
       "execute if score #state aooni.var matches 0 run function aooni:lobby/sec")

    # ---------------- 접속/대기실
    fn("player/first_join",
       "tag @s add aooni.seen",
       "scoreboard players set @s aooni.leave 0",
       "execute if score #state aooni.var matches 1 run return run function aooni:player/watch",
       "function aooni:player/to_lobby",
       tell("@s", T("\n아오오니 저택", "blue", bold=True), T("에 오신 것을 환영합니다!\n", "white"),
            T("대기실의 ", "gray"), T("[규칙 보기]", "aqua"), T(" 로 규칙을 보고, 아오오니를 하고 싶으면 ", "gray"),
            T("[아오오니 지원]", "red"), T(", 모두 모이면 ", "gray"), T("[게임 시작]", "green"), T(" (권장 4~6명)\n혼자라면 ", "gray"), T("[혼자 연습]", "aqua"), T(" 버튼으로 미리 해 볼 수 있습니다.", "gray")))
    fn("player/rejoin",
       "scoreboard players set @s aooni.leave 0",
       "execute if score #state aooni.var matches 1 if entity @s[tag=aooni.player] if score @s aooni.gid = #gid aooni.var run return run function aooni:player/resume",
       "execute if score #state aooni.var matches 1 run return run function aooni:player/watch",
       "function aooni:player/to_lobby")
    fn("player/resume",
       f"execute if entity @s[tag=aooni.jailed] run tp @s {P(*JAIL)} 180 0",
       "execute if score #final aooni.var matches 1 if entity @s[tag=aooni.oni_p,tag=!aooni.giant,tag=!aooni.oni_dead] at @s run function aooni:oni/giant with storage aooni:v",
       "execute if score #wpn aooni.var matches 1 run function aooni:weapon/dedupe",
       tell("@s", T("다시 저택으로 돌아왔다…", "gray", italic=True)))
    fn("player/respawned",
       "scoreboard players set @s aooni.deaths 0",
       "execute if score #state aooni.var matches 2 run return run gamemode spectator @s",
       "execute unless score #state aooni.var matches 1 run return run function aooni:player/to_lobby",
       "execute unless entity @s[tag=aooni.player] run return run function aooni:player/watch",
       "execute if entity @s[tag=aooni.oni_p] run return run function aooni:oni/died",
       "function aooni:player/survivor_effects",
       f"execute if entity @s[tag=aooni.jailed] run tp @s {P(*JAIL)} 180 0",
       "execute if entity @s[tag=aooni.out] run gamemode spectator @s")
    fn("player/leave_role",
       "effect clear @s",
       "function aooni:player/clear_tags",
       "function aooni:player/reset_attrs",
       "team leave @s")
    fn("player/watch",
       "function aooni:player/clear_tags",
       "team join aooni_out @s",
       "gamemode spectator @s",
       f"tp @s {P(*SPEC_POS)} 0 60",
       tell("@s", T("게임이 진행 중입니다. 다음 판까지 관전 모드로 지켜보세요.", "gray")),
       "execute if score #test aooni.var matches 1.. run scoreboard players enable @s aooni.quit",
       "execute if score #test aooni.var matches 1.. run " + tell("@s", T("지금은 혼자 연습 중입니다. 끝내려면 ", "gray"), T("/trigger aooni.quit", "yellow")))
    fn("player/clear_tags",
       *[f"tag @s remove aooni.{t}" for t in ("player", "alive", "jailed", "out", "hidden", "hid_new", "safe", "me",
                                              "armed", "lasthit", "oni_p", "oni_dead", "cand_part", "enraged", "giant")])
    fn("player/reset_attrs",
       *[f"attribute @s minecraft:{a} base reset" for a in
         ("knockback_resistance", "block_interaction_range", "scale", "max_health")])
    fn("player/to_lobby",
       "function aooni:player/clear_tags",
       "team join aooni_lobby @s",
       "effect clear @s",
       "clear @s",
       "gamemode adventure @s",
       "function aooni:player/reset_attrs",
       "effect give @s minecraft:resistance infinite 4 true",
       "effect give @s minecraft:saturation infinite 0 true",
       "effect give @s minecraft:instant_health 1 4 true",
       f"tp @s {P(LOBBY[0] + 0.5, LOBBY[1], LOBBY[2] + 0.5)} 180 0",
       f"spawnpoint @s {P(*LOBBY)}")

    fn("lobby/sec",
       "execute store result storage aooni:v n int 1 if entity @a[gamemode=!spectator]",
       "function aooni:lobby/count with storage aooni:v",
       "execute store result storage aooni:v w int 1 if entity @a[tag=aooni.want_oni]",
       "function aooni:lobby/want_count with storage aooni:v",
       "execute if score #cd aooni.var matches 1.. run function aooni:lobby/countdown")
    fn("lobby/count",
       '$data modify entity @e[type=minecraft:text_display,tag=aooni.t_count,limit=1] text set value {"text":"접속 인원: $(n)명 (권장 4~6명)","color":"white"}')
    fn("lobby/want_count",
       '$data modify entity @e[type=minecraft:text_display,tag=aooni.t_want,limit=1] text set value {"text":"지원자 $(w)명","color":"red"}')
    fn("lobby/countdown",
       "scoreboard players remove #cd aooni.var 1",
       "execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]",
       "execute if score #n aooni.var matches ..1 run scoreboard players set #cd aooni.var 0",
       "execute if score #n aooni.var matches ..1 run return run " + tell("@a", T("인원이 부족해 시작을 취소했습니다 (최소 2명).", "red")),
       "execute if score #cd aooni.var matches 0 run return run function aooni:game/start",
       "execute store result storage aooni:v sec int 1 run scoreboard players get #cd aooni.var",
       "function aooni:lobby/countdown_show with storage aooni:v")
    fn("lobby/countdown_show",
       "$title @a title {\"text\":\"$(sec)\",\"color\":\"yellow\",\"bold\":true}",
       f"title @a subtitle {comp(T('곧 아오오니가 정해집니다…', 'gray'))}",
       "execute as @a at @s run playsound minecraft:block.note_block.hat master @s ~ ~ ~ 1 1")
    fn("lobby/show_diff", *[
        f'execute if score #diff aooni.var matches {d} run data modify entity @e[type=minecraft:text_display,tag=aooni.t_diff,limit=1] text set value {J(T("난이도: " + n, c))}'
        for d, (n, c) in DIFF_NAMES.items()])
    fn("on/l_start",
       "execute unless score #state aooni.var matches 0 run return run " + tell("@s", T("이미 게임이 진행 중입니다.", "red")),
       "execute if score #cd aooni.var matches 1.. run return 0",
       "execute unless score #built aooni.var matches 1.. run return run " + tell("@s", T("저택을 짓는 중입니다. 잠시 후 다시 눌러 주세요.", "red")),
       "execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]",
       "execute if score #n aooni.var matches ..1 run return run " + tell("@a", T("최소 2명이 필요합니다 (아오오니 1명 + 생존자).", "red")),
       "execute unless score #n aooni.var matches 4..6 run " + tell("@a", T("※ 권장 인원은 4~6명입니다. (현재 ", "gray"),
                                                                         {"score": {"name": "#n", "objective": "aooni.var"}, "color": "gray"},
                                                                         T("명) 그대로 시작합니다.", "gray")),
       "scoreboard players set #cd aooni.var 6",
       tell("@a", SEL, T(" 님이 게임을 시작했습니다!", "green")))
    fn("on/l_diff",
       "execute unless score #state aooni.var matches 0 run return 0",
       "scoreboard players add #diff aooni.var 1",
       "execute if score #diff aooni.var matches 4.. run scoreboard players set #diff aooni.var 1",
       "function aooni:lobby/show_diff",
       *[f"execute if score #diff aooni.var matches {d} run " + tell("@a", T("난이도: ", "gray"), T(n, c, bold=True),
                                                                          T(f"  (생존자 목숨 {DIFF[d]['lives']}개 · 아오오니 {SPEED_TEXT[DIFF[d]['speed']]})", "gray"))
         for d, (n, c) in DIFF_NAMES.items()],
       "playsound minecraft:ui.button.click master @s ~ ~ ~ 1 1.2")
    fn("on/l_want",
       "execute if entity @s[tag=aooni.want_oni] run return run function aooni:lobby/want_off",
       "tag @s add aooni.want_oni",
       "playsound minecraft:entity.ravager.roar master @s ~ ~ ~ 0.4 1.2",
       tell("@a", SEL, T(" 님이 ", "gray"), T("아오오니", "red", bold=True), T("에 지원했습니다. (지원자 중 무작위 1명)", "gray")))
    fn("lobby/want_off",
       "tag @s remove aooni.want_oni",
       "playsound minecraft:ui.button.click master @s ~ ~ ~ 1 0.8",
       tell("@a", SEL, T(" 님이 아오오니 지원을 취소했습니다.", "gray")))
    fn("on/l_rules", "function aooni:msg/rules")
    fn("msg/rules",
       tell("@s", T("\n━━━━ 아오오니 저택 규칙 ━━━━\n", "blue", bold=True),
            T("역할: ", "gold"), T("한 명이 아오오니(술래), 나머지는 생존자. 지원자가 있으면 그중에서 무작위로 뽑는다.\n", "white"),
            T("생존자: ", "gold"), T("검은 버튼을 눌러 저택을 뒤져 비밀번호 숫자 4개(①~④번째 자리)를 찾고, ", "white"),
            T("2층 창고 금고에 넣어 마검을 꺼내라. 판마다 숫자와 숨은 위치가 바뀐다.\n", "white"),
            T("아오오니: ", "gold"), T("20초 뒤 깨어난다. 생존자를 때리면 잡힌다. 문·버튼·옷장은 만질 수 없다.\n", "white"),
            T("잡히면: ", "gold"), T("감옥행(목숨 -1). 동료가 감옥 입구 버튼으로 구출. 목숨을 다 잃으면 관전.\n", "white"),
            T("옷장: ", "gold"), T("가문비나무 문 옷장에 들어가 문을 닫으면 완전히 안전. 아오오니는 절대 열 수 없다.\n", "white"),
            T("결전: ", "gold"), T("마검이 나오면 아오오니가 거대해지고 체력바가 뜬다. 마검(힘 V)만 피해를 준다 — 맨손은 0. ", "white"),
            T("마검을 든 사람이 잡히면 그 자리에 떨어진다.\n", "white"),
            T("혼자 연습: ", "gold"), T("대기실 양쪽 끝 버튼. 생존자 연습은 연습용 아오오니(AI)가 쫓아오고, 아오오니 연습은 승패 없이 둘러본다. ", "white"),
            T("끝내기 /trigger aooni.quit\n", "white"),
            T("승패: ", "gold"), T("아오오니를 쓰러뜨리면 생존자 승리, 생존자가 모두 갇히거나 탈락하면 아오오니 승리.", "white")))

    # ---------------- 게임 시작
    fn("game/start",
       "execute as @a run function aooni:player/clear_tags",
       "tag @a[gamemode=!creative,gamemode=!spectator] add aooni.cand_part",
       "scoreboard players set #test aooni.var 0",
       "function aooni:game/begin")
    fn("game/begin",
       "# 참가자(aooni.cand_part)와 #test(0 실전 · 1 생존자 연습 · 2 아오오니 연습)는 부르는 쪽에서 정한다",
       "scoreboard players set #state aooni.var 1",
       "scoreboard players add #gid aooni.var 1",
       "function aooni:build/all",
       *[f"scoreboard players set {f} aooni.var 0" for f in ALL_FLAGS],
       "scoreboard players set #amb aooni.var 40",
       f"scoreboard players set #freeze aooni.var {ONI_FREEZE}",
       "time set 18000",
       "bossbar set aooni:boss visible false",
       *[f"execute store result score #k{j} aooni.var run random value 0..9" for j in range(1, 5)],
       *[f"execute store result storage aooni:v k{j} int 1 run scoreboard players get #k{j} aooni.var" for j in range(1, 5)],
       *[f"execute store result storage aooni:v d{j} int 1 run scoreboard players get #d{j} aooni.var" for j in range(1, 5)],
       "# 아오오니 1명: 지원자 중 무작위, 지원자가 없으면 전체 중 무작위 (연습은 부르는 쪽에서 정함)",
       "execute if score #test aooni.var matches 0 as @r[tag=aooni.cand_part,tag=aooni.want_oni] run tag @s add aooni.oni_p",
       "execute if score #test aooni.var matches 0 unless entity @a[tag=aooni.oni_p] as @r[tag=aooni.cand_part] run tag @s add aooni.oni_p",
       "execute as @a[tag=aooni.cand_part,tag=!aooni.oni_p] run function aooni:player/enter",
       "execute as @a[tag=aooni.cand_part,tag=!aooni.oni_p] run function aooni:player/spawn_pos",
       "execute as @a[tag=aooni.oni_p,tag=aooni.cand_part,limit=1] run function aooni:oni/enter",
       f"execute store result score #nsurv aooni.var if entity {SURV}",
       "tag @a remove aooni.cand_part",
       "scoreboard players reset * aooni.kz",
       "execute if score #test aooni.var matches 1 run function aooni:test/dummy_spawn",
       "execute if score #test aooni.var matches 1.. run scoreboard players enable @a aooni.quit",
       "function aooni:game/assign_loot",
       "bossbar set aooni:goal players @a[tag=aooni.player]",
       "bossbar set aooni:goal color blue",
       "bossbar set aooni:goal visible true",
       "scoreboard objectives setdisplay sidebar aooni.side",
       "function aooni:game/progress",
       "function aooni:game/sidebar",
       "title @a[tag=aooni.player] times 10 70 20",
       f"title {SURV} title {comp(T('아오오니 저택', 'blue', bold=True))}",
       f"title {SURV} subtitle {comp(T('비밀번호 숫자 4개를 찾아 마검을 손에 넣어라', 'gray'))}",
       f"title @a[tag=aooni.oni_p] title {comp(T('당신은 아오오니', 'dark_red', bold=True))}",
       f"title @a[tag=aooni.oni_p] subtitle {comp(T(f'{ONI_FREEZE}초 뒤 깨어난다 — 생존자를 모두 잡아라', 'red'))}",
       sound_all("minecraft:block.iron_door.close", 0.6),
       sound_all("minecraft:entity.zombie.attack_iron_door", 0.5, 0.6),
       "execute if score #test aooni.var matches 0 run " + tell("@a[tag=aooni.player]", T("이번 판의 아오오니: ", "gray"),
                                                                {"selector": "@a[tag=aooni.oni_p]", "color": "dark_red", "bold": True}),
       "execute if score #test aooni.var matches 1 run " + tell(
           "@a[tag=aooni.player]", T("\n[혼자 연습 · 생존자] ", "aqua", bold=True),
           T(f"연습용 아오오니(AI)가 {ONI_FREEZE}초 뒤 2층 다락방에서 깨어나 쫓아온다. 실전에서는 사람이 아오오니를 맡는다.\n", "white"),
           T("끝내기: 채팅에 ", "gray"), T("/trigger aooni.quit", "yellow")),
       "execute if score #test aooni.var matches 2 run " + tell(
           "@a[tag=aooni.player]", T("\n[혼자 연습 · 아오오니] ", "light_purple", bold=True),
           T(f"생존자가 없어서 승패가 나지 않는다. {ONI_FREEZE}초 뒤 움직일 수 있다. 문·버튼·옷장을 못 만지는지 확인해 보자.\n", "white"),
           T("끝내기: 채팅에 ", "gray"), T("/trigger aooni.quit", "yellow")),
       *[f"execute if score #diff aooni.var matches {d} run " + tell("@a[tag=aooni.player]", T("난이도 ", "gray"), T(n, c, bold=True),
                                                                          T(f" · 생존자 목숨 {DIFF[d]['lives']}개 · 아오오니 {SPEED_TEXT[DIFF[d]['speed']]}", "gray"))
         for d, (n, c) in DIFF_NAMES.items()])
    fn("player/enter",
       "tag @s add aooni.player",
       "tag @s add aooni.alive",
       "scoreboard players operation @s aooni.gid = #gid aooni.var",
       *[f"execute if score #diff aooni.var matches {d} run scoreboard players set @s aooni.lives {DIFF[d]['lives']}" for d in DIFF],
       "scoreboard players set @s aooni.grace 0",
       "scoreboard players set @s aooni.leave 0",
       "scoreboard players reset @s aooni.hit",
       "team join aooni_alive @s",
       "gamemode adventure @s",
       "clear @s",
       "effect clear @s",
       "function aooni:player/reset_attrs",
       "function aooni:player/survivor_effects",
       "spawnpoint @s 33 -60 30")
    fn("player/survivor_effects",
       "effect give @s minecraft:resistance infinite 4 true",
       "effect give @s minecraft:saturation infinite 0 true",
       "execute unless entity @s[tag=aooni.armed] run effect give @s minecraft:weakness infinite 9 true",
       f"execute if entity @s[tag=aooni.armed] run effect give @s minecraft:strength infinite {WEAPON_STRENGTH} true",
       "attribute @s minecraft:knockback_resistance base set 1")
    fn("player/spawn_pos",
       "scoreboard players add #sp aooni.var 1",
       *[f"execute if score #sp aooni.var matches {i + 1} run tp @s {P(x + 0.5, F1, z + 0.5)} 180 0" for i, (x, z) in enumerate(SPAWN_POINTS)],
       f"execute if score #sp aooni.var matches {len(SPAWN_POINTS)}.. run scoreboard players set #sp aooni.var 0")
    fn("oni/enter",
       "tag @s add aooni.player",
       "scoreboard players operation @s aooni.gid = #gid aooni.var",
       "scoreboard players set @s aooni.leave 0",
       "team join aooni_oni @s",
       "gamemode adventure @s",
       "clear @s",
       "effect clear @s",
       "function aooni:player/reset_attrs",
       "function aooni:oni/effects",
       f"effect give @s minecraft:slowness {ONI_FREEZE} 255 true",
       f"effect give @s minecraft:blindness {ONI_FREEZE} 0 true",
       f"tp @s {P(*ONI_SPAWN)} 0 0",
       f"spawnpoint @s {P(int(ONI_SPAWN[0]), ONI_SPAWN[1], int(ONI_SPAWN[2]))}",
       "execute at @s run function aooni:oni/model")
    speed = [f"execute if score #diff aooni.var matches {d} run effect give @s minecraft:speed infinite {p['speed']} true"
             for d, p in DIFF.items() if p["speed"] is not None]
    fn("oni/effects",
       "# 아오오니는 투명(대신 파란 모형이 따라다님), 어둠을 꿰뚫어 보고, 블록을 전혀 만질 수 없다(문·버튼·옷장 불가)",
       "effect give @s minecraft:invisibility infinite 0 true",
       "effect give @s minecraft:saturation infinite 0 true",
       "effect give @s minecraft:night_vision infinite 0 true",
       *speed,
       "execute if entity @s[tag=aooni.enraged] run effect give @s minecraft:speed infinite 2 true",
       "attribute @s minecraft:block_interaction_range base set 0",
       "attribute @s minecraft:knockback_resistance base set 1")
    fn("oni/model", *oni_model_cmds(1.0))
    fn("oni/model_big", *oni_model_cmds(FINAL_SCALE))
    assign = []
    for tag in [f"dig{j}" for j in range(1, 5)] + [f"buff{b}" for b in BUFFS]:
        assign += [f"execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.{tag}",
                   f"tag @e[type=minecraft:marker,tag=aooni.{tag}] add aooni.loot"]
    fn("game/assign_loot", "# 비밀번호 숫자 4개와 물약 3개를 조사 지점 중 무작위 위치에 숨긴다", *assign)

    # ---------------- 틱/초
    fn("game/tick",
       f"execute if score #freeze aooni.var matches 1.. as {ONI} positioned {P(*ONI_SPAWN)} unless entity @s[distance=..0.4] run tp @s {P(*ONI_SPAWN)}",
       f"execute as {ONI} at @s run tp @e[type=minecraft:block_display,tag=aooni.part] ~ ~ ~ ~ 0",
       f"execute as {DUMMY} at @s run tp @e[type=minecraft:block_display,tag=aooni.part] ~ ~ ~ ~ 0",
       "execute as @a[tag=aooni.alive,scores={aooni.hit=1..}] at @s run function aooni:player/hit",
       "scoreboard players reset @a[scores={aooni.hit=1..}] aooni.hit",
       f"execute as @a[tag=aooni.oni_p] at @s run function aooni:oni/no_sword",
       "function aooni:hide/check",
       "scoreboard players remove @a[tag=aooni.safe] aooni.grace 1",
       "tag @a[tag=aooni.safe,scores={aooni.grace=..0}] remove aooni.safe",
       f"execute if score #final aooni.var matches 1 as {ONI} at @s run function aooni:final/hp",
       f"execute if score #final aooni.var matches 1 as {DUMMY} at @s run function aooni:final/hp",
       "# 죽은 몹은 @e 에 잡히지 않는다 → 결전 중 연습용 아오오니가 사라졌고 누군가 좀비를 잡았으면 쓰러진 것",
       f"execute if score #test aooni.var matches 1 if score #final aooni.var matches 1 unless entity {DUMMY} "
       "if entity @a[scores={aooni.kz=1..}] run function aooni:test/dummy_down")
    fn("game/sec",
       "scoreboard players add #sec aooni.var 1",
       "# 게임 도중 크리에이티브로 바뀐 사람은 역할에서 뺀다",
       "execute as @a[tag=aooni.player,gamemode=creative] run function aooni:player/leave_role",
       "execute store result score #alive aooni.var if entity @a[tag=aooni.alive,gamemode=adventure]",
       "execute store result score #jailed aooni.var if entity @a[tag=aooni.jailed]",
       "function aooni:game/sidebar",
       "bossbar set aooni:goal players @a[tag=aooni.player]",
       "execute if score #final aooni.var matches 1 run bossbar set aooni:boss players @a[tag=aooni.player]",
       "# 마지막 생존자가 잠깐 끊긴 경우는 20초 기다린다(모두 접속해 있으면 바로 판정)",
       f"execute store result score #son aooni.var if entity {SURV}",
       "execute if score #alive aooni.var matches 1.. run scoreboard players set #a0 aooni.var 0",
       "execute if score #alive aooni.var matches 0 run scoreboard players add #a0 aooni.var 1",
       "# (아오오니 연습은 생존자가 없으니 승패 판정을 하지 않는다)",
       "execute unless score #test aooni.var matches 2 if score #alive aooni.var matches 0 if score #son aooni.var >= #nsurv aooni.var run return run function aooni:game/oni_win",
       "execute unless score #test aooni.var matches 2 if score #a0 aooni.var matches 20.. run return run function aooni:game/oni_win",
       f"execute unless entity {ONI} unless entity {DUMMY} run scoreboard players add #oni_gone aooni.var 1",
       f"execute if entity {ONI} run scoreboard players set #oni_gone aooni.var 0",
       f"execute if entity {DUMMY} run scoreboard players set #oni_gone aooni.var 0",
       "# (연습용 아오오니가 쓰러지지 않고 그냥 사라진 경우는 '중단')",
       "execute unless score #test aooni.var matches 1 if score #final aooni.var matches 1 if score #oni_gone aooni.var matches 30.. run return run function aooni:game/victory",
       "execute if score #oni_gone aooni.var matches 30.. run return run function aooni:game/no_oni",
       "execute if score #wpn aooni.var matches 1 run function aooni:weapon/watch",
       "function aooni:hide/stall",
       f"execute as @a[tag=aooni.player,tag=!aooni.jailed,gamemode=adventure,x=1,y={Y1},z=31,dx=8,dy=5,dz=4] run tp @s {P(*RELEASE)} 180 0",
       "execute if score #freeze aooni.var matches 1.. run function aooni:game/freeze_sec",
       "execute as @a[tag=aooni.alive] run function aooni:player/arm_check",
       f"execute as @a[tag=aooni.alive,tag=!aooni.hidden] at @s if entity {ONI[:-1]},distance=..9] run function aooni:player/near_oni",
       f"execute as @a[tag=aooni.alive,tag=!aooni.hidden] at @s if entity {DUMMY[:-1]},distance=..9] run function aooni:player/near_oni",
       "execute if score #test aooni.var matches 1 if score #freeze aooni.var matches 0 run scoreboard players remove #hunt aooni.var 1",
       "execute if score #test aooni.var matches 1 if score #freeze aooni.var matches 0 if score #hunt aooni.var matches ..0 run function aooni:test/hunt",
       f"execute as @a[tag=aooni.jailed] unless entity @s[x=1,y={Y1},z=31,dx=8,dy=5,dz=4] run tp @s {P(*JAIL)} 180 0",
       "execute if score #rescue_cd aooni.var matches 1.. run scoreboard players remove #rescue_cd aooni.var 1",
       "execute if score #wmsg aooni.var matches 1.. run scoreboard players remove #wmsg aooni.var 1",
       f"execute if score #freeze aooni.var matches 0 as {ONI} run " + actionbar("@s", T("남은 생존자 ", "gray"),
                                                                                   {"score": {"name": "#alive", "objective": "aooni.var"}, "color": "red"},
                                                                                   T("명 · 감옥 ", "gray"),
                                                                                   {"score": {"name": "#jailed", "objective": "aooni.var"}, "color": "yellow"}, T("명", "gray")),
       "scoreboard players remove #amb aooni.var 1",
       "execute if score #amb aooni.var matches ..0 run function aooni:fx/ambient",
       "scoreboard players operation #m aooni.var = #sec aooni.var",
       "scoreboard players operation #m aooni.var %= #2 aooni.var",
       "execute if score #m aooni.var matches 0 run function aooni:fx/glimmer")
    fn("game/freeze_sec",
       "scoreboard players remove #freeze aooni.var 1",
       f"execute if score #freeze aooni.var matches 1.. as @a[tag=aooni.oni_p] run " + actionbar("@s", T("깨어나기까지 ", "gray"),
                                                                                               {"score": {"name": "#freeze", "objective": "aooni.var"}, "color": "red"},
                                                                                               T("초…", "gray")),
       "execute if score #freeze aooni.var matches 0 run function aooni:game/oni_wake")
    fn("game/oni_wake",
       "title @a[tag=aooni.player] times 5 40 15",
       f"title @a[tag=aooni.player] title {comp(T('', 'red'))}",
       f"title {SURV} subtitle {comp(T('…아오오니가 깨어났다', 'dark_red', bold=True))}",
       f"title @a[tag=aooni.oni_p] subtitle {comp(T('사냥 시작!', 'red', bold=True))}",
       sound_all("minecraft:entity.elder_guardian.curse", 0.5, 0.8),
       "bossbar set aooni:goal color red",
       f"execute as {DUMMY} run data merge entity @s {{NoAI:0b}}")
    fn("game/sidebar",
       "scoreboard players operation §a생존자 aooni.side = #alive aooni.var",
       "scoreboard players operation §c감옥 aooni.side = #jailed aooni.var",
       "scoreboard players operation §6숫자(4) aooni.side = #found aooni.var",
       "scoreboard players operation §7경과(분) aooni.side = #sec aooni.var",
       "scoreboard players operation §7경과(분) aooni.side /= #60 aooni.var")
    goals = ["비밀번호 숫자 4개를 찾아라 (검은 버튼 = 조사)", "2층 창고 금고에 비밀번호를 넣어 마검을 꺼내라!",
             "마검으로 아오오니를 족쳐라!"]
    fn("game/progress",
       "execute store result bossbar aooni:goal value run scoreboard players get #found aooni.var",
       "scoreboard players set #goal aooni.var 1",
       "execute if score #found aooni.var matches 4.. run scoreboard players set #goal aooni.var 2",
       "execute if score #wpn aooni.var matches 1 run scoreboard players set #goal aooni.var 3",
       *[f"execute if score #goal aooni.var matches {i} run bossbar set aooni:goal name " +
         comp(T("숫자 ", "gray"), {"score": {"name": "#found", "objective": "aooni.var"}, "color": "gold"},
              T("/4 · ", "gray"), T("목표: ", "gold"), T(g, "white")) for i, g in enumerate(goals, 1)])

    # ---------------- 결과
    def end_common(t):
        return ["scoreboard players set #state aooni.var 2",
                f"scoreboard players set #end_t aooni.var {t}",
                "kill @e[type=minecraft:block_display,tag=aooni.part]",
                f"kill {DUMMY}",
                "bossbar set aooni:boss visible false",
                "scoreboard players operation #min aooni.var = #sec aooni.var",
                "scoreboard players operation #min aooni.var /= #60 aooni.var",
                "scoreboard players operation #s aooni.var = #sec aooni.var",
                "scoreboard players operation #s aooni.var %= #60 aooni.var",
                "title @a times 10 100 30"]
    took = [T(" · 걸린 시간 ", "gray"), {"score": {"name": "#min", "objective": "aooni.var"}, "color": "white"},
            T("분 ", "gray"), {"score": {"name": "#s", "objective": "aooni.var"}, "color": "white"}, T("초", "gray")]
    fn("game/victory",
       *end_common(12),
       f"title @a title {comp(T('아오오니를 족쳤다!', 'gold', bold=True))}",
       "title @a subtitle " + comp(T("최후의 일격: ", "gray"), {"selector": "@a[tag=aooni.lasthit]", "color": "aqua"}, *took),
       "execute as @a at @s run playsound minecraft:entity.ender_dragon.death master @s ~ ~ ~ 0.6 1.2",
       "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1",
       f"execute as {SURV[:-1]},gamemode=adventure] at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 50",
       *door_cmds(33, F1, 36, "north", "left", True),
       *door_cmds(34, F1, 36, "north", "right", True),
       "time set 1000",
       tell("@a", T("\n[아오오니 저택] ", "blue"), T("생존자 승리! ", "gold", bold=True),
            T("아오오니가 쓰러지자 현관문이 열리고 아침 햇살이 들어온다. 12초 뒤 대기실로.", "white")))
    fn("game/oni_win",
       *end_common(10),
       f"title @a title {comp(T('아오오니의 승리', 'dark_red', bold=True))}",
       "title @a subtitle " + comp(T("생존자가 모두 붙잡혔다", "gray"), *took),
       "execute as @a at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 1 0.6",
       "execute unless score #test aooni.var matches 1 run " + tell(
           "@a", T("\n[아오오니 저택] ", "blue"), T("아오오니 ", "dark_red", bold=True),
           {"selector": "@a[tag=aooni.oni_p]", "color": "dark_red"}, T(" 의 승리! 10초 뒤 대기실로.", "white")),
       "execute if score #test aooni.var matches 1 run " + tell(
           "@a", T("\n[아오오니 저택] ", "blue"), T("연습용 아오오니의 승리! ", "dark_red", bold=True),
           T("10초 뒤 대기실로. 다시 하려면 [혼자 연습] 버튼.", "white")))
    fn("game/no_oni",
       *end_common(5),
       f"title @a title {comp(T('게임 중단', 'gray'))}",
       f"title @a subtitle {comp(T('아오오니가 자리를 비웠다', 'gray'))}",
       tell("@a", T("[아오오니 저택] 아오오니가 30초 동안 없어서 게임을 끝냅니다.", "gray")))
    fn("game/ending_sec",
       "scoreboard players remove #end_t aooni.var 1",
       "execute if score #end_t aooni.var matches ..0 run function aooni:game/reset")
    fn("game/reset",
       "kill @e[type=minecraft:block_display,tag=aooni.part]",
       "scoreboard players set #state aooni.var 0",
       "scoreboard players set #cd aooni.var 0",
       "bossbar set aooni:goal visible false",
       "bossbar set aooni:boss visible false",
       "time set 18000",
       "kill @e[type=minecraft:item]",
       f"kill {DUMMY}",
       "kill @e[type=minecraft:experience_orb]",
       "scoreboard players set #test aooni.var 0",
       "scoreboard players reset * aooni.kz",
       "# 연습용 아오오니가 남긴 팀 기록 정리(사람은 이 아래에서 모두 다른 팀으로 옮겨진다)",
       "team empty aooni_out",
       "scoreboard objectives setdisplay sidebar",
       "scoreboard players reset * aooni.side",
       "execute as @a[gamemode=!creative] run function aooni:player/to_lobby",
       "execute as @a[gamemode=creative,tag=aooni.player] run effect clear @s",
       "execute as @a[gamemode=creative] run function aooni:player/clear_tags",
       "execute as @a[gamemode=creative] run function aooni:player/reset_attrs",
       "team leave @a[gamemode=creative]")

    # ---------------- 잡힘/감옥
    fn("player/hit",
       "# 아오오니에게 맞았다(같은 팀 아군 공격은 막혀 있으므로 맞힐 수 있는 건 아오오니뿐)",
       "scoreboard players reset @s aooni.hit",
       "execute if entity @s[tag=aooni.safe] run return 0",
       "execute if entity @s[tag=aooni.hidden] run return 0",
       "execute if score #freeze aooni.var matches 1.. run return 0",
       "scoreboard players set #byoni aooni.var 0",
       "execute on attacker if entity @s[tag=aooni.oni_p] run scoreboard players set #byoni aooni.var 1",
       "execute on attacker if entity @s[tag=aooni.dummy] run scoreboard players set #byoni aooni.var 1",
       "execute if score #byoni aooni.var matches 0 run return 0",
       "function aooni:player/caught")
    fn("player/caught",
       "function aooni:player/drop_weapons",
       "tag @s remove aooni.alive",
       "tag @s remove aooni.hidden",
       "tag @s remove aooni.hid_new",
       "scoreboard players remove @s aooni.lives 1",
       "title @s times 5 40 15",
       f"title @s title {comp(T('잡혔다…', 'dark_red', bold=True))}",
       "effect give @s minecraft:blindness 3 0 true",
       "playsound minecraft:entity.ghast.scream master @s ~ ~ ~ 1 0.5",
       "playsound minecraft:entity.zombie.attack_iron_door hostile @a[distance=..24] ~ ~ ~ 1 0.6",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) 아오오니에게 잡혔다!", "red")),
       "execute if score @s aooni.lives matches 1.. run function aooni:player/jail",
       "execute if score @s aooni.lives matches ..0 run function aooni:player/out",
       "execute as @a[tag=aooni.oni_p] at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.6 0.6")
    fn("player/jail",
       "tag @s add aooni.jailed",
       "team join aooni_out @s",
       f"tp @s {P(*JAIL)} 180 0",
       tell("@s", T("감옥에 갇혔다. 동료가 감옥 입구의 버튼을 누르면 풀려난다. 남은 목숨: ", "gray"),
            {"score": {"name": "@s", "objective": "aooni.lives"}, "color": "yellow"}))
    fn("player/out",
       "tag @s add aooni.out",
       "team join aooni_out @s",
       "gamemode spectator @s",
       f"tp @s {P(*SPEC_POS)} 0 60",
       tell("@a[tag=aooni.player]", SEL, T(" 은(는) 더 이상 돌아오지 못했다… (탈락)", "dark_gray")))
    fn("player/release",
       "tag @s remove aooni.jailed",
       "tag @s add aooni.alive",
       "team join aooni_alive @s",
       "scoreboard players reset @s aooni.hit",
       f"tp @s {P(*RELEASE)} 180 0",
       "tag @s add aooni.safe",
       "scoreboard players set @s aooni.grace 100",
       actionbar("@s", T("풀려났다! 5초간 잡히지 않는다", "green")))
    fn("player/near_oni",
       "playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1",
       "effect give @s minecraft:darkness 2 0 true",
       actionbar("@s", T("…아오오니가 가까이 있다!", "red", bold=True)))

    # ---------------- 마검
    fn("player/drop_weapons",
       "# 잡힌 자리에 마검을 떨어뜨린다. 반짝여서 멀리서도 보인다",
       f"execute store result score #c aooni.var run clear @s minecraft:{WEAPON_ITEM} 0",
       "execute if score #c aooni.var matches 1.. run summon minecraft:item ~ ~1 ~ "
       f"{{Item:{{id:\"minecraft:{WEAPON_ITEM}\",count:1}},PickupDelay:30s,Age:-32768s,Glowing:1b,Invulnerable:1b}}",
       "execute if score #c aooni.var matches 1.. run " + tell("@a[tag=aooni.player]", T("마검이 바닥에 떨어졌다! ", "gold", bold=True),
                                                                T("누군가 주워서 싸워야 한다!", "yellow")),
       f"clear @s minecraft:{WEAPON_ITEM}",
       "function aooni:player/arm_check")
    fn("player/arm_check",
       f"execute store result score @s aooni.wc run clear @s minecraft:{WEAPON_ITEM} 0",
       "execute if score @s aooni.wc matches 1.. if entity @s[tag=!aooni.armed] run function aooni:player/arm",
       "execute if score @s aooni.wc matches ..0 if entity @s[tag=aooni.armed] run function aooni:player/disarm")
    fn("player/arm",
       "tag @s add aooni.armed",
       "effect clear @s minecraft:weakness",
       f"effect give @s minecraft:strength infinite {WEAPON_STRENGTH} true",
       actionbar("@s", T("마검이 힘을 불어넣는다! ", "gold", bold=True), T("아오오니를 족쳐라!", "yellow")))
    fn("player/disarm",
       "tag @s remove aooni.armed",
       "effect clear @s minecraft:strength",
       "effect give @s minecraft:weakness infinite 9 true")
    fn("oni/no_sword",
       "# 아오오니는 마검을 가질 수 없다. 주우면 금고 앞으로 돌려보낸다",
       f"execute store result score #c aooni.var run clear @s minecraft:{WEAPON_ITEM} 0",
       "execute if score #c aooni.var matches 0 run return 0",
       f"clear @s minecraft:{WEAPON_ITEM}",
       "function aooni:weapon/respawn",
       "execute if score #wmsg aooni.var matches 0 run " + tell("@a[tag=aooni.player]", T("마검이 아오오니의 손을 거부했다! ", "gold"),
                                                                 T("마검은 저택 어딘가로 날아갔다(반짝이는 곳).", "yellow")),
       "scoreboard players set #wmsg aooni.var 5")
    sword_item = (f"{{Item:{{id:\"minecraft:{WEAPON_ITEM}\",count:1}},PickupDelay:10s,Age:-32768s,Glowing:1b,"
                  "Invulnerable:1b,Motion:[0.0d,0.0d,0.0d]}")
    fn("weapon/respawn",
       "# 아오오니와 24칸 넘게 떨어진 조사 지점 중 무작위 한 곳(없으면 창고 금고 앞)에 마검을 놓는다",
       "tag @e[type=minecraft:marker,tag=aooni.wcand] remove aooni.wcand",
       "execute as @e[type=minecraft:marker,tag=aooni.spot] at @s unless entity @a[tag=aooni.oni_p,distance=..24] run tag @s add aooni.wcand",
       f"execute at @e[type=minecraft:marker,tag=aooni.wcand,sort=random,limit=1] run summon minecraft:item ~ ~0.5 ~ {sword_item}",
       f"execute unless entity @e[type=minecraft:marker,tag=aooni.wcand] run summon minecraft:item {P(*VAULT_DROP)} {sword_item}")
    SWORD_SEL = f"@e[type=minecraft:item,nbt={{Item:{{id:\"minecraft:{WEAPON_ITEM}\"}}}}]"
    fn("weapon/watch",
       "# 떨어진 마검은 사라지지 않고 반짝이게, 어디에도 없으면(소지자 퇴장 등) 10초 뒤 다시 나타나게",
       f"execute as {SWORD_SEL} run data merge entity @s {{Age:-32768s,Invulnerable:1b,Glowing:1b}}",
       f"execute store result score #sw aooni.var run clear @a minecraft:{WEAPON_ITEM} 0",
       f"execute store result score #swi aooni.var if entity {SWORD_SEL}",
       "scoreboard players operation #sw aooni.var += #swi aooni.var",
       "execute if score #sw aooni.var matches 1.. run scoreboard players set #swlost aooni.var 0",
       "execute if score #sw aooni.var matches 0 run scoreboard players add #swlost aooni.var 1",
       "execute if score #swlost aooni.var matches 10.. run function aooni:weapon/lost")
    fn("weapon/lost",
       "scoreboard players set #swlost aooni.var 0",
       "function aooni:weapon/respawn",
       tell("@a[tag=aooni.player]", T("사라졌던 마검이 저택 어딘가에 다시 나타났다! ", "gold"), T("(반짝이는 곳)", "yellow")))
    fn("weapon/dedupe",
       "# 오프라인으로 들고 나갔던 마검이 이미 다시 나타났다면, 돌아온 사람 것은 지운다",
       f"execute store result score #sw aooni.var run clear @a minecraft:{WEAPON_ITEM} 0",
       f"execute store result score #swi aooni.var if entity {SWORD_SEL}",
       "scoreboard players operation #sw aooni.var += #swi aooni.var",
       f"execute if score #sw aooni.var matches 2.. run clear @s minecraft:{WEAPON_ITEM}",
       "function aooni:player/arm_check")
    fn("weapon/give",
       "# 이름 붙은 검을 먼저 시도하고(아이템 컴포넌트 문법은 버전마다 다를 수 있다), 안 되면 그냥 검을 준다",
       "scoreboard players set #ok aooni.var 0",
       f'function aooni:weapon/give_named {{nm:"{WEAPON_NAME}"}}',
       f"execute if score #ok aooni.var matches 0 run give @s minecraft:{WEAPON_ITEM}",
       "function aooni:player/arm_check")
    fn("weapon/give_named",
       f'$execute store success score #ok aooni.var run give @s minecraft:{WEAPON_ITEM}'
       '[minecraft:custom_name={text:"$(nm)",color:"gold",italic:false},minecraft:enchantment_glint_override=true]')

    # ---------------- 결전
    fn("final/start",
       "scoreboard players set #final aooni.var 1",
       f"execute store result score #n aooni.var if entity {SURV}",
       f"scoreboard players set #k aooni.var {ONI_HP_PER}",
       "scoreboard players operation #hp aooni.var = #n aooni.var",
       "scoreboard players operation #hp aooni.var *= #k aooni.var",
       f"scoreboard players add #hp aooni.var {ONI_HP_BASE}",
       "execute store result storage aooni:v hp int 1 run scoreboard players get #hp aooni.var",
       "scoreboard players set #k aooni.var 5",
       "scoreboard players operation #half10 aooni.var = #hp aooni.var",
       "scoreboard players operation #half10 aooni.var *= #k aooni.var",
       f"execute as {ONI} at @s run function aooni:oni/giant with storage aooni:v",
       f"execute as {DUMMY} at @s run function aooni:test/dummy_giant with storage aooni:v",
       "execute store result bossbar aooni:boss max run scoreboard players get #hp aooni.var",
       "execute store result bossbar aooni:boss value run scoreboard players get #hp aooni.var",
       "bossbar set aooni:boss name " + comp(T("거대 아오오니 ", "dark_red", bold=True), {"selector": "@a[tag=aooni.oni_p]", "color": "red"}),
       "execute if score #test aooni.var matches 1 run bossbar set aooni:boss name " + comp(T("거대 아오오니 (연습용)", "dark_red", bold=True)),
       "bossbar set aooni:boss players @a[tag=aooni.player]",
       "bossbar set aooni:boss visible true",
       "title @a[tag=aooni.player] times 5 60 20",
       f"title @a[tag=aooni.player] title {comp(T('마검이 뽑혔다!', 'gold', bold=True))}",
       f"title {SURV} subtitle {comp(T('거대해진 아오오니를 족쳐라!', 'yellow'))}",
       f"title @a[tag=aooni.oni_p] subtitle {comp(T('몸이 거대해졌다 — 마검을 든 자부터 잡아라!', 'red'))}",
       sound_all("minecraft:entity.wither.spawn", 0.7, 0.5),
       "function aooni:game/progress")
    fn("oni/giant",
       "tag @s add aooni.giant",
       "function aooni:final/unstick",
       "$attribute @s minecraft:max_health base set $(hp)",
       "effect give @s minecraft:instant_health 1 6 true",
       f"attribute @s minecraft:scale base set {FINAL_SCALE}",
       "function aooni:oni/model_big",
       "execute store result score #bhp_prev aooni.var run data get entity @s Health 10",
       "particle minecraft:large_smoke ~ ~1.5 ~ 0.8 1.2 0.8 0.03 120",
       "playsound minecraft:entity.ravager.roar master @a[distance=..48] ~ ~ ~ 2 0.5")
    fn("final/hp",
       "execute store result score #bh aooni.var run data get entity @s Health 10",
       "execute store result bossbar aooni:boss value run data get entity @s Health",
       "execute if score #bh aooni.var matches ..0 run tag @a remove aooni.lasthit",
       "execute if score #bh aooni.var matches ..0 on attacker run tag @s add aooni.lasthit",
       "execute if score #bh aooni.var matches ..0 run return run function aooni:oni/defeated",
       "scoreboard players operation #bd aooni.var = #bhp_prev aooni.var",
       "scoreboard players operation #bd aooni.var -= #bh aooni.var",
       "execute if score #bd aooni.var matches 5.. run function aooni:final/hurt",
       "scoreboard players operation #bhp_prev aooni.var = #bh aooni.var")
    fn("final/hurt",
       "tag @a remove aooni.lasthit",
       "execute on attacker run tag @s add aooni.lasthit",
       "particle minecraft:crit ~ ~1.8 ~ 0.5 0.8 0.5 0.3 15",
       "execute unless entity @s[tag=aooni.enraged] if score #bh aooni.var <= #half10 aooni.var run function aooni:final/enrage")
    fn("final/enrage",
       "tag @s add aooni.enraged",
       "execute if entity @s[type=minecraft:player] run effect give @s minecraft:speed infinite 2 true",
       "# 좀비는 같은 신속에도 훨씬 빨라지므로 한 단계만",
       "execute unless entity @s[type=minecraft:player] run effect give @s minecraft:speed infinite 0 true",
       "playsound minecraft:entity.ravager.roar master @a[distance=..48] ~ ~ ~ 2 0.4",
       "title @a[tag=aooni.player] times 5 40 10",
       f"title @a[tag=aooni.player] title {comp(T('', 'red'))}",
       f"title @a[tag=aooni.player] subtitle {comp(T('아오오니가 격노했다! 더 빨라졌다!', 'red', bold=True))}")
    fn("oni/defeated",
       "execute unless score #state aooni.var matches 1 run return 0",
       "tag @s add aooni.oni_dead",
       "execute unless entity @a[tag=aooni.lasthit] run tag @a[tag=aooni.armed] add aooni.lasthit",
       "function aooni:game/victory")
    fn("oni/died",
       "# 결전 중 쓰러졌다면 승리 처리, 그 밖의 사고(관리자 /kill 등)면 아오오니로 되돌린다",
       "execute if score #final aooni.var matches 1 run return run function aooni:oni/defeated",
       "function aooni:oni/effects",
       f"tp @s {P(*ONI_SPAWN)} 0 0")

    # ---------------- 숨기 (옷장)
    hide = ["tag @a remove aooni.hid_new"]
    force = []
    for c in CLOSETS:
        x, y, z, dx, dy, dz = c["box"]
        box = f"x={x},y={y},z={z},dx={dx},dy={dy},dz={dz}"
        hide.append(f"execute as @a[tag=aooni.alive,{box}] "
                    f"if block {P(*c['door'])} minecraft:spruce_door[open=false] run tag @s add aooni.hid_new")
        hide.append(f"execute as @a[tag=aooni.oni_p,{box}] if block {P(*c['door'])} minecraft:spruce_door[open=false] "
                    f"run tp @s {P(*c['out'])}")
        hide.append(f"execute as {DUMMY[:-1]},{box}] if block {P(*c['door'])} minecraft:spruce_door[open=false] "
                    f"run tp @s {P(*c['out'])}")
        force += door_cmds(*c["door"], c["facing"], "left", True, mat="spruce_door")
    hide += ["execute as @a[tag=aooni.hid_new,tag=!aooni.hidden] run function aooni:hide/enter",
             "execute as @a[tag=aooni.hidden,tag=!aooni.hid_new] run function aooni:hide/leave"]
    fn("hide/check", *hide)
    unstick = ["# 1.3배가 되면 키가 2칸을 넘는다 → 옷장(2칸)이나 낮은 곳에 있으면 질식하므로 먼저 꺼낸다"]
    for c in CLOSETS:
        x, y, z, dx, dy, dz = c["box"]
        unstick.append(f"execute if entity @s[x={x},y={y},z={z},dx={dx},dy={dy},dz={dz}] run return run tp @s {P(*c['out'])}")
    unstick.append(f"execute at @s unless block ~ ~2 ~ minecraft:air run tp @s {P(*ONI_SPAWN)}")
    fn("final/unstick", *unstick)
    fn("hide/enter",
       "tag @s add aooni.hidden",
       actionbar("@s", T("옷장에 숨었다 — 아오오니는 이 문을 열 수 없다", "dark_aqua")))
    fn("hide/leave",
       "tag @s remove aooni.hidden",
       actionbar("@s", T("옷장에서 나왔다", "gray")))
    fn("hide/stall",
       "# 움직일 수 있는 생존자가 모두 옷장에 숨어 버리면 판이 끝나지 않는다 → 60초 뒤 옷장 문이 저절로 열린다",
       "execute store result score #free aooni.var if entity @a[tag=aooni.alive,tag=!aooni.hidden,gamemode=adventure]",
       "execute if score #free aooni.var matches 1.. run scoreboard players set #stall aooni.var 0",
       "execute if score #free aooni.var matches 0 if score #alive aooni.var matches 1.. run scoreboard players add #stall aooni.var 1",
       "execute if score #stall aooni.var matches 40 run " + tell("@a[tag=aooni.player]", T("모두가 옷장에 숨어 있다… 공기가 희박해진다. ", "dark_aqua"),
                                                                    T("20초 뒤 옷장 문이 저절로 열린다!", "red")),
       "execute if score #stall aooni.var matches 60.. run function aooni:hide/force_open")
    fn("hide/force_open",
       "scoreboard players set #stall aooni.var 0",
       *force,
       sound_all("minecraft:block.wooden_door.open", 0.6),
       tell("@a[tag=aooni.player]", T("끼이익… 저택의 모든 옷장 문이 열렸다!", "red", bold=True)))

    # ---------------- 효과
    fn("fx/ambient",
       "execute store result score #r aooni.var run random value 1..4",
       f"execute if score #r aooni.var matches 1 as {SURV} at @s run playsound minecraft:ambient.cave ambient @s ~ ~ ~ 1 0.8",
       f"execute if score #r aooni.var matches 2 as {SURV} at @s run playsound minecraft:block.wooden_door.close ambient @s ~4 ~ ~-3 0.6 0.5",
       f"execute if score #r aooni.var matches 3 as {SURV} at @s run playsound minecraft:entity.zombie.ambient ambient @s ~-5 ~ ~5 0.4 0.4",
       f"execute if score #r aooni.var matches 4 as {SURV} at @s run playsound minecraft:block.note_block.chime ambient @s ~ ~2 ~ 0.4 0.5",
       "execute store result score #amb aooni.var run random value 30..60")
    vx, vy, vz = SAFES[4]["ok"][0], F2 + 1, SAFES[4]["ok"][1]
    fn("fx/glimmer",
       "execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.searched] at @s run particle minecraft:glow ~ ~0.35 ~ 0.15 0.1 0.15 0 2",
       f"execute if score #found aooni.var matches 4.. if score #wpn aooni.var matches 0 run particle minecraft:glow {P(vx + 0.5, vy + 0.35, vz + 0.5)} 0.2 0.15 0.2 0 6")

    # ---------------- 버튼 폴링
    poll = []
    for (aid, x, y, z, state, kind, scope) in ACTS:
        poll.append(f"execute if block {P(x, y, z)} minecraft:{kind}[powered=true] run function aooni:act/{aid}")
        who = "@p[gamemode=!spectator,distance=..6]" if scope == "lobby" else "@p[tag=aooni.alive,distance=..6]"
        cond = "" if scope == "lobby" else "if score #state aooni.var matches 1 "
        fn(f"act/{aid}",
           f"setblock {P(x, y, z)} {state}",
           f"execute {cond}positioned {P(x + 0.5, y + 0.5, z + 0.5)} as {who} at @s run function aooni:on/{aid}")
    fn("act/poll", *poll)

    # ---------------- 조사 지점: 판마다 무작위로 숫자/물약/꽝
    for (aid, x, y, z, state, kind, scope) in spots:
        fn(f"on/{aid}",
           "playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1",
           tell("@s", T(FLAVOR[aid], "gray", italic=True)),
           "tag @s add aooni.me",
           f"execute as @e[type=minecraft:marker,tag=aooni.spot_{aid},limit=1] at @s run function aooni:loot/open",
           "tag @s remove aooni.me")
    fn("loot/open",
       "tag @s add aooni.searched",
       *[f"execute if entity @s[tag=aooni.dig{j}] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/digit{j} with storage aooni:v"
         for j in range(1, 5)],
       *[f"execute if entity @s[tag=aooni.buff{b},tag=!aooni.used] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/buff{b}"
         for b in BUFFS],
       "execute as @a[tag=aooni.me,limit=1] run function aooni:loot/nothing")
    for j in range(1, 5):
        fn(f"loot/digit{j}",
           f'$tellraw @s {{"text":"쪽지를 찾았다: 『비밀번호 {ORD[j]} 자리 = $(k{j})』","color":"dark_red","bold":true}}',
           "execute if entity @e[type=minecraft:marker,tag=aooni.spot,tag=aooni.found,distance=..0.5] run return 0",
           "tag @e[type=minecraft:marker,tag=aooni.spot,distance=..0.5,limit=1] add aooni.found",
           "scoreboard players add #found aooni.var 1",
           f'$summon minecraft:text_display ~ ~0.7 ~ {{Tags:["aooni.fx","aooni.digit"],text:{{"text":"{CIRC[j]} $(k{j})","color":"dark_red","bold":true}},'
           'billboard:"vertical",background:0,shadow:1b,transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],'
           'translation:[0f,0f,0f],scale:[0.8f,0.8f,0.8f]}}',
           tell(SURV, SEL, T(" 이(가) 비밀번호 ", "white"), T(f"{ORD[j]} 자리", "gold", bold=True), T("를 찾았다! (", "white"),
                {"score": {"name": "#found", "objective": "aooni.var"}, "color": "gold"}, T("/4)", "white")),
           sound_all("minecraft:entity.experience_orb.pickup", 1.3, who=SURV),
           "function aooni:game/progress")
    for b, (eff, amp, dur, name, msg) in BUFFS.items():
        fn(f"loot/buff{b}",
           "tag @e[type=minecraft:marker,tag=aooni.spot,distance=..0.5,limit=1] add aooni.used",
           f"effect give @s minecraft:{eff} {dur} {amp} true",
           "playsound minecraft:entity.generic.drink player @s ~ ~ ~ 1 1",
           tell("@s", T(f"[{name}]", "light_purple", bold=True), T(f" 을(를) 찾아 썼다! {msg}", "white")))
    nothing = ["execute store result score #r aooni.var run random value 1..%d" % len(NOTHING)]
    for i, line in enumerate(NOTHING, 1):
        nothing.append(f"execute if score #r aooni.var matches {i} run " + tell("@s", T(line, "dark_gray")))
    fn("loot/nothing", *nothing)

    # ---------------- 금고(마검)
    for k in range(1, 5):
        fn(f"on/safe4_d{k}",
           "execute if score #wpn aooni.var matches 1 run return run " + tell("@s", T("금고는 이미 비어 있다.", "gray")),
           f"scoreboard players add #d{k} aooni.var 1",
           f"execute if score #d{k} aooni.var matches 10.. run scoreboard players set #d{k} aooni.var 0",
           f"execute store result storage aooni:v d{k} int 1 run scoreboard players get #d{k} aooni.var",
           "function aooni:safe/show with storage aooni:v",
           "playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6")
    fn("safe/show",
       '$title @s actionbar {"text":"금고 다이얼:  $(d1)  $(d2)  $(d3)  $(d4)","color":"gold","bold":true}', *[
        f'$data modify entity @e[type=minecraft:text_display,tag=aooni.dial4{k},limit=1] text set value {{"text":"$(d{k})","color":"white","bold":true}}'
        for k in range(1, 5)])
    fn("on/safe4_ok",
       "execute if score #wpn aooni.var matches 1 run return run " + tell("@s", T("금고는 이미 비어 있다.", "gray")),
       *[f"execute unless score #d{k} aooni.var = #k{k} aooni.var run return run function aooni:safe/wrong" for k in range(1, 5)],
       "scoreboard players set #wpn aooni.var 1",
       "function aooni:weapon/give",
       "playsound minecraft:block.iron_door.open block @a[distance=..12] ~ ~ ~ 1 1.4",
       "playsound minecraft:item.trident.thunder master @a[distance=..48] ~ ~ ~ 0.8 1.2",
       "particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 60",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) 금고에서 ", "white"), T(f"[{WEAPON_NAME}]", "gold", bold=True),
            T("을(를) 꺼냈다!", "white")),
       "data modify entity @e[type=minecraft:text_display,tag=aooni.safe4,limit=1] text set value " + J(T("마검 금고 · 비었음", "gray")),
       "function aooni:final/start")
    fn("safe/wrong",
       "playsound minecraft:block.chest.locked block @a[distance=..12] ~ ~ ~ 1 0.6",
       "playsound minecraft:block.anvil.land block @a[distance=..32] ~ ~ ~ 0.5 0.5",
       "effect give @s minecraft:glowing 5 0 true",
       tell("@s", T("…비밀번호가 틀렸다! 금속음이 울려 5초간 위치가 드러난다.", "red")),
       "execute as @a[tag=aooni.oni_p] run " + actionbar("@s", T("창고 금고 쪽에서 금속음이 났다! (틀린 사람이 빛난다)", "red", bold=True)))

    # ---------------- 기타 버튼
    fn("on/rescue",
       "execute unless entity @a[tag=aooni.jailed] run return run " + tell("@s", T("감옥은 비어 있다.", "gray")),
       "execute if score #rescue_cd aooni.var matches 1.. run return run " + tell("@s", T("자물쇠가 아직 돌아가지 않는다… 잠시 후 다시.", "gray")),
       f"playsound minecraft:block.iron_door.open block @a[distance=..32] {P(*RELEASE)} 1 0.7",
       f"particle minecraft:large_smoke {P(RELEASE[0], RELEASE[1] + 1, RELEASE[2])} 0.4 0.6 0.4 0.02 20",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) 감옥 문을 열었다!", "green")),
       "execute as @a[tag=aooni.jailed] run function aooni:player/release",
       "scoreboard players set #rescue_cd aooni.var 20",
       "execute as @a[tag=aooni.oni_p] run " + actionbar("@s", T("감옥 문이 열리는 소리가 났다!", "red", bold=True)))
    for k in range(1, 6):
        fn(f"on/piano{k}", f"playsound minecraft:block.note_block.harp block @a[distance=..16] ~ ~ ~ 1 {NOTE_PITCH[k]}")
    fn("on/d_front",
       "playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 0.7",
       tell("@s", T("현관문은 꿈쩍도 하지 않는다… ", "gray"), T("아오오니를 쓰러뜨리기 전에는 나갈 수 없을 것 같다.", "red")))

    # ---------------- 혼자 연습
    fn("test/solo",
       "# 생존자 연습: 모험 모드인 사람 모두 생존자, 아오오니는 연습용 AI",
       "execute as @a run function aooni:player/clear_tags",
       "tag @a[gamemode=!creative,gamemode=!spectator] add aooni.cand_part",
       "scoreboard players set #test aooni.var 1",
       "function aooni:game/begin")
    fn("test/solo_oni",
       "# 아오오니 연습: 부른 사람이 아오오니, 생존자 없음(승패 없음)",
       "execute as @a run function aooni:player/clear_tags",
       "tag @s add aooni.cand_part",
       "tag @s add aooni.oni_p",
       "scoreboard players set #test aooni.var 2",
       "function aooni:game/begin")
    dummy_nbt = ('{Tags:["aooni.dummy"],NoAI:1b,Silent:1b,PersistenceRequired:1b,CanPickUpLoot:0b,CanBreakDoors:0b,IsBaby:0b,'
                 'active_effects:[{id:"minecraft:invisibility",amplifier:0b,duration:-1,show_particles:0b},'
                 '{id:"minecraft:fire_resistance",amplifier:0b,duration:-1,show_particles:0b}],'
                 'attributes:[{id:"minecraft:follow_range",base:256.0d},{id:"minecraft:knockback_resistance",base:1.0d},'
                 '{id:"minecraft:spawn_reinforcements",base:0.0d}]}')
    fn("test/dummy_spawn",
       "# 깨어나기 전까지는 NoAI 로 다락방에 묶어 둔다(game/oni_wake 에서 풀림)",
       f"kill {DUMMY}",
       f"summon minecraft:zombie {P(*ONI_SPAWN)} {dummy_nbt}",
       "# 갇힌/탈락한 사람과 같은 팀 → 그 사람들은 즉시 목표에서 빠진다",
       f"team join aooni_out {DUMMY}",
       *[f"execute if score #diff aooni.var matches {d} as {DUMMY} run attribute @s minecraft:movement_speed base set {v}"
         for d, v in DUMMY_SPEED.items()],
       f"execute at {DUMMY[:-1]},limit=1] run function aooni:oni/model")
    HUNT_SEL = '@p[tag=aooni.alive,tag=!aooni.hidden,gamemode=adventure,nbt=!{active_effects:[{id:"minecraft:invisibility"}]}]'
    fn("test/hunt",
       "# 벽 너머의 생존자도 쫓아오게: 가장 가까운(숨지 않은·투명하지 않은) 생존자가 때린 것으로 쳐서 그쪽을 노리게 한다",
       f"scoreboard players set #hunt aooni.var {DUMMY_HUNT}",
       f"execute as {DUMMY} at @s if entity {HUNT_SEL} run damage @s 0.01 minecraft:generic by {HUNT_SEL}")
    fn("test/dummy_giant",
       "# 좀비는 즉시 회복 물약에 오히려 다치므로 체력을 직접 채운다",
       "tag @s add aooni.giant",
       "function aooni:final/unstick",
       "$attribute @s minecraft:max_health base set $(hp)",
       "$data merge entity @s {Health:$(hp)f}",
       f"attribute @s minecraft:scale base set {FINAL_SCALE}",
       "function aooni:oni/model_big",
       "execute store result score #bhp_prev aooni.var run data get entity @s Health 10",
       "particle minecraft:large_smoke ~ ~1.5 ~ 0.8 1.2 0.8 0.03 120",
       "playsound minecraft:entity.ravager.roar master @a[distance=..48] ~ ~ ~ 2 0.5")
    fn("test/dummy_down",
       "tag @a remove aooni.lasthit",
       "tag @a[scores={aooni.kz=1..}] add aooni.lasthit",
       "function aooni:game/victory")
    fn("test/quit",
       "scoreboard players set @s aooni.quit 0",
       "scoreboard players enable @s aooni.quit",
       "execute unless score #state aooni.var matches 1 run return run " + tell("@s", T("진행 중인 연습이 없습니다.", "gray")),
       "execute unless score #test aooni.var matches 1.. run return run " + tell("@s", T("실전은 이 명령으로 끝낼 수 없습니다. (관리자: /function aooni:admin/stop)", "red")),
       tell("@a", T("[아오오니 저택] ", "blue"), SEL, T(" 님이 연습을 끝냈습니다.", "gray")),
       "function aooni:game/reset")
    solo_checks = [
        "execute unless score #state aooni.var matches 0 run return run " + tell("@s", T("이미 게임이 진행 중입니다.", "red")),
        "execute if score #cd aooni.var matches 1.. run return run " + tell("@s", T("게임 시작 카운트다운 중입니다.", "red")),
        "execute unless score #built aooni.var matches 1.. run return run " + tell("@s", T("저택을 짓는 중입니다. 잠시 후 다시 눌러 주세요.", "red")),
        "execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]",
        "execute if score #n aooni.var matches 0 run return run " + tell(
            "@s", T("크리에이티브 모드에서는 참가할 수 없습니다. /gamemode adventure 후 다시 눌러 주세요.", "red")),
        "execute unless score #n aooni.var matches 1 run return run " + tell(
            "@s", T("혼자 접속해 있을 때만 쓸 수 있습니다. 여럿이면 [게임 시작]을 누르세요.", "red"))]
    fn("on/l_solo", *solo_checks, "function aooni:test/solo")
    fn("on/l_solo_oni", *solo_checks, "execute as @a[gamemode=!creative,gamemode=!spectator,limit=1] run function aooni:test/solo_oni")

    # ---------------- 관리자 명령
    fn("admin/start", "scoreboard players set #cd aooni.var 0",
       "execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]",
       "execute if score #n aooni.var matches ..1 run return run " + tell("@s", T("최소 2명(모험 모드)이 필요합니다.", "red")),
       "execute if score #state aooni.var matches 0 run function aooni:game/start")
    fn("admin/stop",
       "execute if score #state aooni.var matches 1 run " + tell("@a", T("[아오오니 저택] 관리자가 게임을 중단했습니다.", "red")),
       "function aooni:game/reset")
    fn("admin/solo",
       "# 인원 제한 없이 생존자 연습(모험 모드인 사람 모두 생존자, 연습용 AI 아오오니)",
       "execute unless score #state aooni.var matches 0 run return run " + tell("@s", T("게임이 끝난 뒤에 쓸 수 있습니다. (중단: /function aooni:admin/stop)", "red")),
       "execute unless entity @a[gamemode=!creative,gamemode=!spectator] run return run " + tell(
           "@s", T("모험 모드인 플레이어가 없습니다. (크리에이티브는 참가자에서 빠집니다)", "red")),
       "scoreboard players set #cd aooni.var 0",
       "function aooni:test/solo")
    fn("admin/solo_oni",
       "# 실행한 사람이 아오오니가 되어 승패 없이 둘러본다",
       "execute unless score #state aooni.var matches 0 run return run " + tell("@s", T("게임이 끝난 뒤에 쓸 수 있습니다. (중단: /function aooni:admin/stop)", "red")),
       "execute unless entity @s[type=minecraft:player,gamemode=!creative,gamemode=!spectator] run return run " + tell(
           "@s", T("모험 모드인 플레이어가 직접 실행해야 합니다.", "red")),
       "scoreboard players set #cd aooni.var 0",
       "function aooni:test/solo_oni")
    fn("admin/rebuild", "scoreboard players set #built aooni.var 0",
       "execute unless score #state aooni.var matches 0 run " + tell("@s", T("게임이 끝나면 다시 짓습니다.", "gray")),
       "function aooni:setup/check_build")
    for d, (n, c) in DIFF_NAMES.items():
        fn(f"admin/difficulty_{d}", f"scoreboard players set #diff aooni.var {d}", "function aooni:lobby/show_diff",
           tell("@a", T("난이도: ", "gray"), T(n, c, bold=True)))
    fn("admin/oni_pick",
       "# 사용법: /execute as <닉네임> run function aooni:admin/oni_pick  → 다음 판 아오오니로 지정",
       "tag @a remove aooni.want_oni",
       "tag @s add aooni.want_oni",
       tell("@a", T("[아오오니 저택] 다음 판 아오오니: ", "gray"), SEL))
    fn("admin/final_now",
       "# 테스트용: 숫자를 다 찾은 것으로 하고 생존자 한 명에게 마검을 줘서 바로 결전",
       "execute unless score #state aooni.var matches 1 run return run " + tell("@s", T("게임 중에만 쓸 수 있습니다.", "red")),
       "execute if score #wpn aooni.var matches 1 run return run " + tell("@s", T("이미 결전 중입니다.", "red")),
       "scoreboard players set #found aooni.var 4",
       "scoreboard players set #freeze aooni.var 1",
       "scoreboard players set #wpn aooni.var 1",
       "execute as @r[tag=aooni.alive] run function aooni:weapon/give",
       "function aooni:final/start")
    fn("admin/help",
       tell("@s", T("\n[아오오니 저택 관리자 명령]\n", "blue", bold=True),
            T("/function aooni:admin/start", "yellow"), T(" 카운트다운 없이 바로 시작\n", "gray"),
            T("/function aooni:admin/stop", "yellow"), T(" 게임 중단 후 대기실로\n", "gray"),
            T("/function aooni:admin/rebuild", "yellow"), T(" 저택·대기실 다시 짓기\n", "gray"),
            T("/function aooni:admin/difficulty_1 | _2 | _3", "yellow"), T(" 난이도 쉬움/보통/어려움\n", "gray"),
            T("/execute as 닉네임 run function aooni:admin/oni_pick", "yellow"), T(" 다음 판 아오오니 지정\n", "gray"),
            T("/function aooni:admin/final_now", "yellow"), T(" (테스트) 마검 지급 후 바로 결전\n", "gray"),
            T("/function aooni:admin/solo", "yellow"), T(" (연습) 인원 상관없이 생존자 연습\n", "gray"),
            T("/function aooni:admin/solo_oni", "yellow"), T(" (연습) 실행한 사람이 아오오니로 둘러보기\n", "gray"),
            T("/trigger aooni.quit", "yellow"), T(" 연습 끝내기 (누구나)", "gray")))


def fixtures():
    out = []
    for (aid, x, y, z, state, kind, scope) in ACTS:
        if aid.startswith("s_"):
            out.append(f"summon minecraft:marker {P(x + 0.5, y, z + 0.5)} {{Tags:[\"aooni.fx\",\"aooni.spot\",\"aooni.spot_{aid}\"]}}")
    for (x, y, z, tags) in MARKERS:
        out.append(f"summon minecraft:marker {P(x, y, z)} {{Tags:{json.dumps(['aooni.fx'] + tags)}}}")
    for (x, y, z, c, tags, scale, bb, extra) in TEXTS:
        tg = json.dumps(["aooni.fx"] + tags)
        out.append(f"summon minecraft:text_display {P(x, y, z)} {{Tags:{tg},text:{J(c)},billboard:\"{bb}\","
                   f"background:0,shadow:1b,see_through:0b,transformation:{{left_rotation:[0f,0f,0f,1f],"
                   f"right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[{scale}f,{scale}f,{scale}f]}}{extra}}}")
    return out


# ================================================================== 쓰기
def write_pack():
    if os.path.isdir(PACK):
        shutil.rmtree(PACK)
    fdir = os.path.join(PACK, "data", NS, "function")
    os.makedirs(fdir)
    header = {"build/mansion": "# 자동 생성 — tools/build_pack.py 를 고치세요",
              "build/lobby": "# 자동 생성 — tools/build_pack.py 를 고치세요"}
    FUNCS["build/mansion"] = BUILD
    FUNCS["build/lobby"] = LOBBY_BUILD
    FUNCS["build/fixtures"] = fixtures()
    for name, lines in FUNCS.items():
        path = os.path.join(fdir, name + ".mcfunction")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        body = ([header[name]] if name in header else []) + lines
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(body) + "\n")
    tdir = os.path.join(PACK, "data", "minecraft", "tags", "function")
    os.makedirs(tdir)
    for tag, f_ in (("load", "aooni:load"), ("tick", "aooni:tick")):
        with open(os.path.join(tdir, tag + ".json"), "w", encoding="utf-8") as f:
            json.dump({"values": [f_]}, f, indent=2)
    meta = {"pack": {"description": [{"text": "아오오니 저택 ", "color": "blue"}, {"text": "4~6인 협동 탈출 (1.21.5~26.3)", "color": "gray"}],
                     "pack_format": PACK_MIN, "supported_formats": [PACK_MIN, PACK_MAX],
                     "min_format": PACK_MIN, "max_format": PACK_MAX}}
    with open(os.path.join(PACK, "pack.mcmeta"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return sum(len(v) for v in FUNCS.values()), len(FUNCS)


def make_dist():
    """배포용 zip 두 개: 서버팩 전체 / 데이터팩만. 타임스탬프를 고정해 내용이 같으면 파일도 같게 한다."""
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    server = os.path.join(ROOT, "server")
    stamp = (2026, 1, 1, 0, 0, 0)

    def add(z, path, arc):
        info = zipfile.ZipInfo(arc, stamp)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o755 if arc.endswith(".sh") else 0o644) << 16
        with open(path, "rb") as f:
            z.writestr(info, f.read())

    def walk(base):
        for root, dirs, names in os.walk(base):
            dirs.sort()
            for nm in sorted(names):
                yield os.path.join(root, nm)

    with zipfile.ZipFile(os.path.join(dist, "aooni-mansion-serverpack.zip"), "w") as z:
        for nm in ("server.properties", "start.bat", "start.sh"):
            add(z, os.path.join(server, nm), "aooni-mansion-server/" + nm)
        add(z, os.path.join(ROOT, "README.md"), "aooni-mansion-server/README.md")
        for path in walk(PACK):
            add(z, path, "aooni-mansion-server/" + os.path.relpath(path, server).replace(os.sep, "/"))
    with zipfile.ZipFile(os.path.join(dist, "aooni-mansion-datapack.zip"), "w") as z:
        for path in walk(PACK):
            add(z, path, os.path.relpath(path, PACK).replace(os.sep, "/"))


def main():
    build_mansion()
    build_lobby()
    logic()
    problems, nclosed, nopen = structure_checks()
    nlines, nfuncs = write_pack()
    make_dist()
    print(f"함수 {nfuncs}개, 명령 {nlines}줄, 버튼 {len(ACTS)}개, 옷장 {len(CLOSETS)}개, 마커 {len(MARKERS)}개")
    print(f"시작 시 이동 가능 칸 {nclosed}, 모든 문 열림 시 {nopen}")
    if "--map" in sys.argv:
        for y in (F1, F2):
            print(f"--- y={y}")
            print(ascii_map(y))
    if problems:
        print("구조 문제:")
        for p in problems:
            print("  -", p)
    else:
        print("구조 점검 통과")
    err = len(problems)
    if "--no-validate" not in sys.argv:
        sys.path.insert(0, HERE)
        import mcvalidate
        rules = [(o, n, v) for (o, n, v, opt) in GAMERULES if not opt]
        err += mcvalidate.main(PACK, gamerules=rules)
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
