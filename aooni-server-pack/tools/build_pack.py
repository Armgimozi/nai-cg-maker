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
BUILD_VERSION = 3          # 바꾸면 기존 월드도 다음 로드 때 다시 짓는다
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
        tz = w + 1.05 if fd > 0 else w - 0.05
        fill(start - 1, yf, w, start + 5, yf + 2, w, "iron_block")
        fill(start, yf + 1, w, start + 4, yf + 1, w, "polished_deepslate")
        cells = [(start + k, w + fd) for k in range(5)]
        tpos = [(x + 0.5, tz) for (x, _) in cells]
        lpos = (start + 2.5, tz)
    else:
        facing = "east" if fd > 0 else "west"
        yaw = -90 if fd > 0 else 90
        tx = w + 1.05 if fd > 0 else w - 0.05
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
    CLOSETS.append({"inside": (x, y0, z), "door": (x + dx, y0, z + dz),
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
    door(16, F1, 12, "north", "left")
    door(17, F1, 12, "north", "right")
    button("d_stairs", 20, F1 + 1, 13, "wall", "south")
    text(17.0, F1 + 2.75, 13.2, T("계단", "gray"), "aooni.fx")

    # 5) 1층 복도
    fill(1, F1, 14, 45, F1, 15, "red_carpet")
    for i, x in enumerate(range(4, 46, 8)):
        setb(x, C1 - 1, 14 + (i % 2), "soul_lantern[hanging=true]")
    setb(1, F1, 13, "potted_dead_bush")
    setb(45, F1, 16, "potted_dead_bush")
    marker(3, F1, 14, "aooni.spawn", "aooni.z1")
    marker(43, F1, 15, "aooni.spawn", "aooni.z1")

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
    safe_panel(2, "x", 14, F1, 4, -1, "봉인②  · 단서는 식당에")   # 동쪽 벽, 서쪽을 바라봄
    closet(13, F1, 10, "W")
    door(7, F1, 12, "north", "left")
    button("d_lib", 10, F1 + 1, 13, "wall", "south")
    text(7.5, F1 + 2.75, 13.2, T("서재", "gray"), "aooni.fx")
    marker(2, F1, 2, "aooni.first")
    marker(2, F1, 10, "aooni.spawn", "aooni.z2")
    marker(8, F1, 3, "aooni.spawn", "aooni.z2")

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
    text(29.5, F1 + 1.75, 6.5, T("", "dark_red"), "aooni.fx", "aooni.pw2", scale=0.7)
    closet(35, F1, 10, "W")
    for x in (26, 27, 31, 32):
        fill(x, F1 + 1, 0, x, F1 + 2, 0, "glass_pane")
    door(29, F1, 12, "north", "left")
    button("d_din", 32, F1 + 1, 13, "wall", "south")
    text(29.5, F1 + 2.75, 13.2, T("식당", "gray"), "aooni.fx")
    marker(24, F1, 2, "aooni.spawn", "aooni.z3")

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
    text(41.5, F1 + 2.35, 1.95, T("(악보가 비어 있다)", "gray"), "aooni.fx", "aooni.sheet", scale=0.55)
    text(41.5, F1 + 2.8, 1.95, T("", "dark_red"), "aooni.fx", "aooni.pw3", scale=0.7)
    setb(41, C1 - 1, 6, "lantern[hanging=true]")
    closet(45, F1, 10, "W")
    fill(46, F1 + 1, 5, 46, F1 + 2, 6, "glass_pane")
    text(36.5, F1 + 3.0, 5.9, T("피아노실", "gray"), "aooni.fx")
    marker(44, F1, 6, "aooni.spawn", "aooni.z3")

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
    marker(8, F1, 23, "aooni.spawn", "aooni.z1")

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
    text(16.55, F1 + 2.2, 22.5, T("", "dark_red"), "aooni.fx", "aooni.pw1", scale=0.8)
    setb(14, C1 - 1, 27, "lantern[hanging=true]")
    closet(11, F1, 24, "E")
    text(14.5, F1 + 2.75, 16.8, T("화장실", "gray"), "aooni.fx")
    marker(14, F1, 30, "aooni.spawn", "aooni.z1")

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
    marker(28, F1, 33, "aooni.spawn", "aooni.z1")

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
    # 제단: 봉인 네 개가 풀리면 전설의 검이 나타난다
    setb(36, F1, 28, "chiseled_quartz_block")
    setb(36, C1 - 1, 28, "soul_lantern[hanging=true]")
    button("altar", 36, F1 + 1, 28, "floor", "north", "polished_blackstone_button")
    text(36.5, F1 + 2.2, 28.5, T("제단 · 봉인 0/4", "light_purple"), "aooni.fx", "aooni.altar_t", scale=0.55)
    door(33, F1, 36, "north", "left")
    door(34, F1, 36, "north", "right")
    button("d_front", 31, F1 + 1, 35, "wall", "north")
    text(33.95, F1 + 2.6, 35.3, T("현관문", "gold"), "aooni.fx")
    text(33.95, F1 + 2.75, 16.8, T("현관홀", "gray"), "aooni.fx")
    marker(32, F1, 19, "aooni.spawn", "aooni.z1")

    # 13) 주방 (x38..45, z18..35)
    fill(38, Y1, 18, 45, Y1, 35, "smooth_stone")
    fill(45, F1, 20, 45, F1, 28, "polished_andesite")
    setb(45, F1, 24, "water_cauldron[level=3]")
    setb(45, F1, 21, "smoker[facing=west]")
    setb(45, F1, 26, "furnace[facing=west]")
    fill(45, F1, 30, 45, F1 + 1, 30, "iron_block")
    fill(41, F1, 25, 42, F1, 27, "spruce_slab[type=top]")
    setb(40, F1, 26, "spruce_stairs[facing=west]")
    setb(43, F1, 26, "spruce_stairs[facing=east]")
    setb(41, C1 - 1, 26, "lantern[hanging=true]")
    button("s_kit_fridge", 44, F1 + 1, 30, "wall", "west", "polished_blackstone_button")
    button("s_kit_sink", 45, F1 + 1, 23, "floor", "north", "polished_blackstone_button")
    closet(38, F1, 34, "E")
    safe_panel(1, "z", 36, F1, 40, -1, "봉인①  · 단서는 1층 어딘가에")   # 남쪽 벽, 북쪽을 바라봄
    fill(46, F1 + 1, 33, 46, F1 + 2, 34, "glass_pane")
    text(41.95, F1 + 2.75, 16.8, T("주방", "gray"), "aooni.fx")
    marker(43, F1, 22, "aooni.spawn", "aooni.z1")

    # ---------------- 2층
    fill(1, F2, 14, 45, F2, 15, "blue_carpet")
    for x in (6, 18, 30, 42):
        setb(x, RF - 1, 14, "soul_lantern[hanging=true]")
    marker(2, F2, 14, "aooni.spawn", "aooni.z4")
    marker(44, F2, 15, "aooni.spawn", "aooni.z4")

    # 안방 (x1..13, z1..11)
    fill(2, F2, 2, 3, F2, 4, "red_wool")
    fill(2, F2, 2, 3, F2, 2, "white_wool")
    setb(5, F2, 2, "spruce_planks")
    button("s_mb_diary", 5, F2 + 1, 2, "floor", "north", "polished_blackstone_button")
    text(5.5, F2 + 1.6, 2.5, T("", "dark_red"), "aooni.fx", "aooni.q4", scale=0.8)
    setb(7, RF - 1, 6, "lantern[hanging=true]")
    closet(13, F2, 8, "W")
    fill(7, F2 + 1, 0, 8, F2 + 2, 0, "glass_pane")
    setb(2, F2, 10, "light_weighted_pressure_plate")
    text(7.5, F2 + 2.75, 13.2, T("안방", "gray"), "aooni.fx")
    marker(10, F2, 3, "aooni.spawn", "aooni.z4")

    # 손님방 (x23..35, z1..11)
    fill(24, F2, 2, 25, F2, 4, "blue_wool")
    fill(28, F2, 2, 29, F2, 4, "blue_wool")
    setb(33, F2, 9, "brown_wool")
    button("s_gr_bag", 33, F2 + 1, 9, "floor", "north", "polished_blackstone_button")
    text(33.5, F2 + 1.6, 9.5, T("", "dark_red"), "aooni.fx", "aooni.q2", scale=0.8)
    setb(29, RF - 1, 6, "lantern[hanging=true]")
    closet(35, F2, 2, "W")
    fill(31, F2 + 1, 0, 32, F2 + 2, 0, "glass_pane")
    setb(24, F2, 10, "light_weighted_pressure_plate")
    text(29.5, F2 + 2.75, 13.2, T("손님방", "gray"), "aooni.fx")
    marker(26, F2, 7, "aooni.spawn", "aooni.z4")

    # 창고 (x37..45, z1..11) — 발판 퍼즐로 열림
    fill(37, C1, 1, 45, C1, 11, "spruce_planks")
    safe_panel(4, "z", 0, F2, 39, 1, "봉인④  · 단서는 2층 네 곳에")   # 북쪽 벽, 남쪽을 바라봄
    setb(44, F2, 10, "barrel[facing=up]")
    setb(43, F2, 10, "barrel[facing=up]")
    setb(45, F2, 7, "hay_block")
    button("s_sto_box", 44, F2 + 1, 10, "floor", "north", "polished_blackstone_button")
    setb(41, RF - 1, 6, "lantern[hanging=true]")
    setb(45, RF - 1, 1, "cobweb")
    closet(37, F2, 10, "E")
    fill(46, F2 + 1, 5, 46, F2 + 2, 6, "glass_pane")
    door(41, F2, 12, "north", "left")
    button("d_store", 44, F2 + 1, 13, "wall", "south")
    text(41.5, F2 + 2.75, 13.2, T("창고", "gray"), "aooni.fx")
    marker(44, F2, 5, "aooni.spawn", "aooni.z5")

    # 아이방 (x1..13, z18..35)
    fill(1, C1, 18, 13, C1, 35, "birch_planks")
    fill(3, F2, 27, 7, F2, 31, "light_blue_carpet")
    fill(2, F2, 34, 3, F2, 35, "pink_wool")
    setb(10, F2, 19, "pink_wool")
    setb(8, F2, 34, "white_wool")
    button("s_kid_toy", 10, F2 + 1, 19, "floor", "north", "polished_blackstone_button")
    button("s_kid_draw", 1, F2 + 1, 24, "wall", "east", "polished_blackstone_button")
    text(1.55, F2 + 2.1, 24.5, T("", "dark_red"), "aooni.fx", "aooni.q1", scale=0.8)
    setb(7, RF - 1, 27, "lantern[hanging=true]")
    closet(13, F2, 33, "W")
    fill(6, F2 + 1, 36, 7, F2 + 2, 36, "glass_pane")
    setb(3, F2, 32, "light_weighted_pressure_plate")
    text(7.5, F2 + 2.75, 16.8, T("아이방", "gray"), "aooni.fx")
    marker(11, F2, 22, "aooni.spawn", "aooni.z4")

    # 작업실 (x15..29, z18..35)
    fill(15, C1, 18, 29, C1, 35, "spruce_planks")
    fill(29, F2, 23, 29, F2 + 2, 28, "bookshelf")
    fill(20, F2, 34, 21, F2, 34, "dark_oak_planks")
    setb(20, F2, 33, "dark_oak_stairs[facing=south]")
    setb(24, F2, 22, "lectern[facing=south]")
    button("s_st_note", 20, F2 + 1, 34, "floor", "north", "polished_blackstone_button")
    setb(22, RF - 1, 26, "lantern[hanging=true]")
    closet(15, F2, 21, "E")
    safe_panel(3, "z", 17, F2, 25, 1, "봉인③  · 피아노가 답을 안다")   # 북쪽 벽, 남쪽을 바라봄
    fill(24, F2 + 1, 36, 25, F2 + 2, 36, "glass_pane")
    setb(27, F2, 20, "light_weighted_pressure_plate")
    text(22.95, F2 + 2.75, 16.8, T("작업실", "gray"), "aooni.fx")
    marker(27, F2, 33, "aooni.spawn", "aooni.z4")

    # 다락방 (x31..45, z18..35)
    fill(31, C1, 18, 45, C1, 35, "stripped_spruce_wood")
    for (x, z) in [(31, 18), (45, 18), (31, 35), (45, 35), (38, 35)]:
        setb(x, RF - 1, z, "cobweb")
    setb(40, F2, 33, "spruce_planks")
    setb(34, F2, 24, "spruce_stairs[facing=west]")
    button("s_spare_mirror", 40, F2 + 1, 33, "floor", "north", "polished_blackstone_button")
    text(40.5, F2 + 1.6, 33.5, T("", "dark_red"), "aooni.fx", "aooni.q3", scale=0.8)
    setb(38, RF - 1, 26, "soul_lantern[hanging=true]")
    closet(45, F2, 27, "W")
    fill(36, F2 + 1, 36, 37, F2 + 2, 36, "glass_pane")
    fill(42, F2 + 1, 36, 43, F2 + 2, 36, "glass_pane")
    text(38.5, F2 + 2.75, 16.8, T("다락방", "gray"), "aooni.fx")
    marker(44, F2, 33, "aooni.spawn", "aooni.z4")
    marker(32, F2, 20, "aooni.spawn", "aooni.z4")

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
    button("l_start", -23, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_diff", -21, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_rules", -19, F1 + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-22.5, F1 + 1.75, 5.3, T("▶ 게임 시작", "green"), "aooni.fx", scale=0.5)
    text(-20.5, F1 + 1.75, 5.3, T("난이도 변경", "yellow"), "aooni.fx", scale=0.5)
    text(-18.5, F1 + 1.75, 5.3, T("규칙 보기", "aqua"), "aooni.fx", scale=0.5)
    text(-20.5, F1 + 3.3, 5.5, T("아오오니 저택", "blue", bold=True), "aooni.fx", scale=1.6)
    text(-20.5, F1 + 2.85, 5.5, T("4~6인 협동 · 비밀번호 4개 → 개쎈 무기 → 아오오니 족치기", "gray"), "aooni.fx", scale=0.6)
    text(-20.5, F1 + 2.45, 5.5, T("난이도: 보통", "yellow"), "aooni.fx", "aooni.t_diff", scale=0.7)
    text(-20.5, F1 + 2.15, 5.5, T("접속 인원: 0명", "white"), "aooni.fx", "aooni.t_count", scale=0.6)
    rules = ("저택에 갇혔다. 비밀번호 4개로 봉인을 풀고, 개쎈 무기로 아오오니를 족쳐라!\n"
             "· 검은 버튼 = 조사, 철문 옆 버튼 = 문 열기, 봉인 버튼 = 숫자 돌리기\n"
             "· 봉인 4개가 풀리면 현관홀 제단에 전설의 검이 나타난다 (무기는 단 하나)\n"
             "· 검을 뽑으면 거대 아오오니 등장 — 체력바를 0으로! 맨손은 안 통한다\n"
             "· 잡히면 감옥행(검은 그 자리에 떨어짐) → 동료가 감옥 입구 버튼으로 구출\n"
             "· 옷장(가문비 문)에 들어가 문을 닫으면 숨을 수 있다")
    text(-27.3, F1 + 2.2, 12.5, T(rules, "white"), "aooni.fx", scale=0.55,
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
        return doors_open
    return False


def standable_on(block):
    if block is None:
        return False
    b = bid(block)
    return not (b.endswith(PASSABLE_SUFFIX) or "lantern" in b or b.endswith("_door"))


def reachable(start, doors_open, floors_y=(F1, F2)):
    """플레이어가 걸어서 닿는 칸(발 위치) 집합."""
    seen = {start}
    q = deque([start])

    def ok(x, y, z):
        if not (-40 < x < 60 and -70 < y < -40 and -10 < z < 60):
            return False
        return (passable(WORLD.get((x, y, z)), doors_open) and passable(WORLD.get((x, y + 1, z)), doors_open)
                and standable_on(WORLD.get((x, y - 1, z))))

    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                n = (x + dx, y + dy, z + dz)
                if n in seen:
                    continue
                if dy == 1 and not passable(WORLD.get((x, y + 2, z)), doors_open):
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
    must_open = {"서재": (6, F1, 10), "식당": (24, F1, 9), "피아노실": (40, F1, 8), "2층 복도": (10, F2, 14),
                 "안방": (6, F2, 6), "손님방": (30, F2, 7), "창고": (40, F2, 8), "아이방": (6, F2, 22),
                 "작업실": (22, F2, 28), "다락방": (40, F2, 28), "정원 탈출칸": (33, F1, 43)}
    must_initial = {"복도": (20, F1, 14), "감옥 앞": (5, F1, 26), "화장실": (15, F1, 28), "거실": (25, F1, 32),
                    "주방": (41, F1, 30)}
    for name, p in must_initial.items():
        if p not in closed:
            problems.append(f"시작 시 {name} 에 갈 수 없음 {p}")
    for name, p in must_open.items():
        if p in closed:
            problems.append(f"잠긴 구역 {name} 에 문을 안 열고도 들어갈 수 있음(벽 구멍?) {p}")
        if p not in opened:
            problems.append(f"문을 다 열어도 {name} 에 갈 수 없음 {p}")
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
    ("locatorBar", "locator_bar", "false", True),
]

DIFF_NAMES = {1: ("쉬움", "green"), 2: ("보통", "yellow"), 3: ("어려움", "red")}
# 난이도별: 목숨, 아오오니 기본 수, 이동속도, 재등장 대기(초) 범위, 추격 최대 시간, 놓친 뒤 사라지기까지
DIFF = {
    1: dict(lives=3, base=1, speed=0.31, cd="45..70", life=60, lost=10, boss_speed=0.27),
    2: dict(lives=2, base=1, speed=0.34, cd="30..50", life=90, lost=14, boss_speed=0.29),
    3: dict(lives=1, base=2, speed=0.37, cd="20..35", life=120, lost=20, boss_speed=0.31),
}
ENRAGE_SPEED_BONUS = 0.03
ONI_HP, REPEL_HP = 40, 28            # 사냥 중인 아오오니: 무기로 12 이상 맞으면 달아난다
BOSS_HP_BASE, BOSS_HP_PER, BOSS_HP_CAP = 200, 50, 800
# 무기는 단 하나: 네더라이트 검 + 지니고 있으면 힘 V (한 방 약 23)
WEAPON_ITEM, WEAPON_NAME = "netherite_sword", "전설의 검"
WEAPON_STRENGTH = 4
CIRC = {1: "①", 2: "②", 3: "③", 4: "④"}
NOTE_PITCH = {1: 0.707107, 2: 0.793701, 3: 0.890899, 4: 0.943874, 5: 1.059463}
NOTE_NAME = {1: "도", 2: "레", 3: "미", 4: "파", 5: "솔"}

GATES = [  # 진행 관문(앞에서부터 처음으로 안 된 것이 목표가 된다)
    ("#k_lib", "1층을 조사하라 — 거실과 화장실이 수상하다 (검은 버튼 = 조사)"),
    ("#lib", "서재 열쇠로 서재 문을 열어라 (문 옆 버튼)"),
    ("#k_din", "서재를 조사하라"),
    ("#din", "식당 문을 열어라 — 아오오니를 조심하라!"),
    ("#stairs", "피아노실에서 악보(서재)대로 연주하라"),
    ("#store", "2층 네 방의 발판을 동시에 밟아라"),
]
GOAL_SEALS = "남은 봉인의 비밀번호를 찾아 풀어라"
GOAL_ALTAR = "현관홀 제단에서 전설의 검을 뽑아라!"
GOAL_FINAL = "결전! 전설의 검으로 거대 아오오니를 족쳐라!"
ALL_FLAGS = ([g for g, _ in GATES] + ["#sheet", "#oni_on", "#pstep", "#rescue_cd", "#sec", "#sp", "#cd", "#weap",
                                      "#wpn", "#altar", "#final", "#boss_up", "#bhp", "#bhp_prev", "#bmax", "#half10"]
             + [f"#pw{i}" for i in range(1, 5)] + [f"#q{i}" for i in range(1, 5)] + [f"#w{i}" for i in range(1, 5)]
             + [f"#d{s_}{k}" for s_ in range(1, 5) for k in range(1, 5)])


def oni_summon_nbt(scale=1.0, tags=("aooni.oni", "aooni.new")):
    off = -2.0125   # 좀비 위 탑승 위치 (좀비 자체 크기는 그대로, 모양만 키운다)
    parts = [  # (블록, 크기xyz, 최소좌표xyz, 밝기)
        ("blue_concrete", (0.28, 0.85, 0.30), (-0.30, 0.0, -0.15), 11),
        ("blue_concrete", (0.28, 0.85, 0.30), (0.02, 0.0, -0.15), 11),
        ("blue_concrete", (0.75, 0.75, 0.42), (-0.375, 0.80, -0.21), 11),
        ("blue_concrete", (0.22, 0.95, 0.24), (-0.60, 0.62, -0.12), 11),
        ("blue_concrete", (0.22, 0.95, 0.24), (0.38, 0.62, -0.12), 11),
        ("blue_concrete", (1.25, 1.15, 1.05), (-0.625, 1.50, -0.525), 11),
        ("white_concrete", (0.26, 0.26, 0.04), (-0.38, 2.05, 0.525), 15),
        ("white_concrete", (0.26, 0.26, 0.04), (0.12, 2.05, 0.525), 15),
        ("black_concrete", (0.12, 0.12, 0.03), (-0.31, 2.12, 0.565), 15),
        ("black_concrete", (0.12, 0.12, 0.03), (0.19, 2.12, 0.565), 15),
        ("black_concrete", (0.60, 0.08, 0.03), (-0.30, 1.72, 0.525), 11),
    ]
    ps = []
    for blk, s, m, br in parts:
        t = f"[{m[0] * scale:.4f}f,{m[1] * scale + off:.4f}f,{m[2] * scale:.4f}f]"
        sc = f"[{s[0] * scale:.4f}f,{s[1] * scale:.4f}f,{s[2] * scale:.4f}f]"
        ps.append('{id:"minecraft:block_display",block_state:{Name:"minecraft:%s"},Tags:["aooni.part"],'
                  'brightness:{sky:%d,block:%d},transformation:{left_rotation:[0f,0f,0f,1f],'
                  'right_rotation:[0f,0f,0f,1f],translation:%s,scale:%s}}' % (blk, br, br, t, sc))
    return ('{Tags:' + json.dumps(list(tags)).replace(" ", "") + ',PersistenceRequired:1b,Silent:1b,CanPickUpLoot:0b,'
            'IsBaby:0b,CanBreakDoors:0b,Passengers:[' + ",".join(ps) + "]}")


def logic():
    # ---------------- load / tick
    fn("load",
       "scoreboard objectives add aooni.var dummy",
       f"scoreboard objectives add aooni.side dummy {comp(T('아오오니 저택', 'blue', bold=True))}",
       "scoreboard objectives add aooni.lives dummy",
       "scoreboard objectives add aooni.gid dummy",
       "scoreboard objectives add aooni.leave minecraft.custom:minecraft.leave_game",
       "scoreboard objectives add aooni.grace dummy",
       "scoreboard objectives add aooni.hidet dummy",
       "scoreboard objectives add aooni.life dummy",
       "scoreboard objectives add aooni.lost dummy",
       "scoreboard objectives add aooni.tgt dummy",
       "scoreboard objectives add aooni.deaths deathCount",
       "scoreboard objectives add aooni.hp dummy",
       "scoreboard objectives add aooni.wc dummy",
       "team add aooni_alive",
       f"team modify aooni_alive displayName {comp(T('생존자', 'aqua'))}",
       "team modify aooni_alive color aqua",
       "team modify aooni_alive collisionRule never",
       "team modify aooni_alive friendlyFire false",
       "team add aooni_oni",
       "team modify aooni_oni color dark_blue",
       "team modify aooni_oni collisionRule never",
       "team modify aooni_oni nametagVisibility never",
       "team modify aooni_oni seeFriendlyInvisibles false",
       "team modify aooni_oni friendlyFire false",
       "team add aooni_out",
       "team modify aooni_out color gray",
       "team modify aooni_out collisionRule never",
       f"bossbar add aooni:goal {comp(T('목표', 'white'))}",
       "bossbar set aooni:goal color blue",
       "bossbar set aooni:goal max 4",
       f"bossbar add aooni:boss {comp(T('거대 아오오니', 'dark_red', bold=True))}",
       "bossbar set aooni:boss color red",
       "bossbar set aooni:boss style notched_10",
       "execute unless score #state aooni.var matches 0..2 run scoreboard players set #state aooni.var 0",
       "execute unless score #diff aooni.var matches 1..3 run scoreboard players set #diff aooni.var 2",
       "execute unless score #gid aooni.var matches 0.. run scoreboard players set #gid aooni.var 0",
       "scoreboard players set #t aooni.var 0",
       "scoreboard players set #60 aooni.var 60",
       "scoreboard players set #12 aooni.var 12",
       "function aooni:setup/gamerules",
       "time set 18000",
       "weather clear",
       "difficulty normal",
       f"setworldspawn {P(*LOBBY)}",
       "forceload add -32 -4 50 50",
       "schedule function aooni:setup/check_build 2s",
       )
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
       f"execute unless score #built aooni.var matches {BUILD_VERSION} run function aooni:build/all",
       "execute if score #state aooni.var matches 0 run function aooni:lobby/show_diff")

    fn("build/all",
       "kill @e[tag=aooni.fx]",
       "kill @e[tag=aooni.part]",
       "kill @e[type=minecraft:zombie,tag=aooni.oni]",
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
       "scoreboard players add #t aooni.var 1",
       "execute if score #t aooni.var matches 20.. run function aooni:sec",
       "execute if score #state aooni.var matches 1 run function aooni:game/tick")

    fn("sec",
       "scoreboard players set #t aooni.var 0",
       "execute if score #state aooni.var matches 0 run function aooni:lobby/sec",
       "execute if score #state aooni.var matches 1 run function aooni:game/sec",
       "execute if score #state aooni.var matches 2 run function aooni:game/ending_sec")

    # ---------------- 플레이어 접속/로비
    fn("player/first_join",
       "tag @s add aooni.seen",
       "scoreboard players set @s aooni.leave 0",
       "execute if score #state aooni.var matches 1 run return run function aooni:player/watch",
       "function aooni:player/to_lobby",
       tell("@s", T("\n아오오니 저택", "blue", bold=True), T("에 오신 것을 환영합니다!\n", "white"),
            T("대기실의 ", "gray"), T("[규칙 보기]", "aqua"), T(" 버튼으로 규칙을 확인하고, 모두 모이면 ", "gray"),
            T("[게임 시작]", "green"), T("을 누르세요. (권장 4~6명)", "gray")))
    fn("player/rejoin",
       "scoreboard players set @s aooni.leave 0",
       "execute if score #state aooni.var matches 1 if entity @s[tag=aooni.player] if score @s aooni.gid = #gid aooni.var run return run function aooni:player/resume",
       "execute if score #state aooni.var matches 1 run return run function aooni:player/watch",
       "function aooni:player/to_lobby")
    fn("player/respawned",
       "scoreboard players set @s aooni.deaths 0",
       "execute unless score #state aooni.var matches 1 run return run function aooni:player/to_lobby",
       "execute unless entity @s[tag=aooni.player] run return run function aooni:player/watch",
       "effect give @s minecraft:resistance infinite 4 true",
       "effect give @s minecraft:saturation infinite 0 true",
       "execute unless entity @s[tag=aooni.armed] run effect give @s minecraft:weakness infinite 9 true",
       f"execute if entity @s[tag=aooni.armed] run effect give @s minecraft:strength infinite {WEAPON_STRENGTH} true",
       f"execute if entity @s[tag=aooni.jailed] run tp @s {P(*JAIL)} 180 0",
       "execute if entity @s[tag=aooni.out] run gamemode spectator @s")
    fn("player/resume",
       f"execute if entity @s[tag=aooni.jailed] run tp @s {P(*JAIL)} 180 0",
       tell("@s", T("다시 저택으로 돌아왔다…", "gray", italic=True)))
    fn("player/watch",
       "function aooni:player/clear_tags",
       "team join aooni_out @s",
       "gamemode spectator @s",
       f"tp @s {P(*SPEC_POS)} 0 60",
       tell("@s", T("게임이 진행 중입니다. 다음 판까지 관전 모드로 지켜보세요.", "gray")))
    fn("player/clear_tags",
       *[f"tag @s remove aooni.{t}" for t in ("player", "alive", "jailed", "out", "escaped", "hidden", "hid_new", "safe", "me",
                                              "armed", "lasthit")])
    fn("player/to_lobby",
       "function aooni:player/clear_tags",
       "team leave @s",
       "effect clear @s",
       "clear @s",
       "gamemode adventure @s",
       "effect give @s minecraft:resistance infinite 4 true",
       "effect give @s minecraft:saturation infinite 0 true",
       "attribute @s minecraft:knockback_resistance base reset",
       f"tp @s {P(LOBBY[0] + 0.5, LOBBY[1], LOBBY[2] + 0.5)} 180 0",
       f"spawnpoint @s {P(*LOBBY)}")

    fn("lobby/sec",
       "execute store result storage aooni:v n int 1 if entity @a[gamemode=!spectator]",
       "function aooni:lobby/count with storage aooni:v",
       "execute if score #cd aooni.var matches 1.. run function aooni:lobby/countdown")
    fn("lobby/count",
       '$data modify entity @e[type=minecraft:text_display,tag=aooni.t_count,limit=1] text set value {"text":"접속 인원: $(n)명 (권장 4~6명)","color":"white"}')
    fn("lobby/countdown",
       "scoreboard players remove #cd aooni.var 1",
       "execute if score #cd aooni.var matches 0 run return run function aooni:game/start",
       "execute store result storage aooni:v sec int 1 run scoreboard players get #cd aooni.var",
       "function aooni:lobby/countdown_show with storage aooni:v")
    fn("lobby/countdown_show",
       "$title @a title {\"text\":\"$(sec)\",\"color\":\"yellow\",\"bold\":true}",
       f"title @a subtitle {comp(T('저택으로 이동합니다…', 'gray'))}",
       "execute as @a at @s run playsound minecraft:block.note_block.hat master @s ~ ~ ~ 1 1")
    fn("lobby/show_diff", *[
        f'execute if score #diff aooni.var matches {d} run data modify entity @e[type=minecraft:text_display,tag=aooni.t_diff,limit=1] text set value {J(T("난이도: " + n, c))}'
        for d, (n, c) in DIFF_NAMES.items()])

    fn("on/l_start",
       "execute unless score #state aooni.var matches 0 run return run " + tell("@s", T("이미 게임이 진행 중입니다.", "red")),
       "execute if score #cd aooni.var matches 1.. run return 0",
       "execute unless score #built aooni.var matches 1.. run return run " + tell("@s", T("저택을 짓는 중입니다. 잠시 후 다시 눌러 주세요.", "red")),
       "execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]",
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
                                                                          T(f"  (목숨 {DIFF[d]['lives']}개 · 아오오니 {DIFF[d]['base']}마리부터)", "gray"))
         for d, (n, c) in DIFF_NAMES.items()],
       "playsound minecraft:ui.button.click master @s ~ ~ ~ 1 1.2")
    fn("on/l_rules", "function aooni:msg/rules")
    fn("msg/rules",
       tell("@s", T("\n━━━━ 아오오니 저택 규칙 ━━━━\n", "blue", bold=True),
            T("목표: ", "gold"), T("비밀번호 4개를 찾아 봉인 4개를 풀고, 개쎈 무기 하나로 아오오니를 족쳐라!\n", "white"),
            T("무기: ", "gold"), T("봉인이 다 풀리면 현관홀 제단에 전설의 검이 나타난다. 지닌 사람만 아오오니에게 피해를 준다(맨손은 0). ", "white"),
            T("검을 든 사람이 잡히면 검이 그 자리에 떨어진다 — 누군가 주워서 이어 싸워라. Q 로 건네줄 수도 있다.\n", "white"),
            T("조사: ", "gold"), T("가구 위·벽의 검은 버튼을 누르면 살펴본다.\n", "white"),
            T("문: ", "gold"), T("철문 옆 돌 버튼을 누른다. 열쇠가 있으면 열린다.\n", "white"),
            T("아오오니: ", "gold"), T("닿으면 잡혀 감옥에 갇힌다. 동료가 감옥 입구의 버튼을 눌러 구출할 수 있다.\n", "white"),
            T("목숨: ", "gold"), T("쉬움 3 · 보통 2 · 어려움 1. 다 잃으면 관전.\n", "white"),
            T("숨기: ", "gold"), T("옷장(가문비나무 문)에 들어가 문을 닫으면 아오오니가 쫓지 못한다. ", "white"),
            T("단, 근처를 오래 맴돌면 들킬 수 있다.\n", "red"),
            T("결전: ", "gold"), T("검을 뽑으면 거대 아오오니가 나타난다. 체력바를 0으로 만들면 승리! ", "white"),
            T("움직일 수 있는 생존자가 0명이 되면 패배.\n", "white"),
            T("팁: ", "gold"), T("화면 위 보스바에 지금 할 일이 표시된다. 반짝이는 곳을 조사해 보자.", "gray")))

    # ---------------- 게임 시작/종료
    fn("game/start",
       "scoreboard players set #state aooni.var 1",
       "scoreboard players add #gid aooni.var 1",
       "function aooni:build/all",
       *[f"scoreboard players set {f} aooni.var 0" for f in ALL_FLAGS],
       "scoreboard players set #amb aooni.var 40",
       "scoreboard players set #onis aooni.var 0",
       "scoreboard players set #oni_cd aooni.var 0",
       "time set 18000",
       "bossbar set aooni:boss visible false",
       "function aooni:game/randomize",
       "tag @e[type=minecraft:marker,tag=aooni.z1] add aooni.on",
       "execute as @a[gamemode=!creative,gamemode=!spectator] run function aooni:player/enter",
       "execute as @a[tag=aooni.player] run function aooni:player/spawn_pos",
       "bossbar set aooni:goal players @a[tag=aooni.player]",
       "bossbar set aooni:goal visible true",
       "scoreboard objectives setdisplay sidebar aooni.side",
       "function aooni:game/progress",
       "function aooni:game/sidebar",
       "title @a[tag=aooni.player] times 10 70 20",
       f"title @a[tag=aooni.player] title {comp(T('아오오니 저택', 'blue', bold=True))}",
       f"title @a[tag=aooni.player] subtitle {comp(T('…쾅! 등 뒤에서 현관문이 잠겼다', 'gray', italic=True))}",
       sound_all("minecraft:block.iron_door.close", 0.6),
       sound_all("minecraft:entity.zombie.attack_iron_door", 0.5, 0.6),
       *[f"execute if score #diff aooni.var matches {d} run " + tell("@a[tag=aooni.player]", T("난이도 ", "gray"), T(n, c, bold=True),
                                                                          T(" · 목숨 " + str(DIFF[d]['lives']) + "개. 비밀번호 4개로 봉인을 풀고, 개쎈 무기로 아오오니를 족쳐라!", "gray"))
         for d, (n, c) in DIFF_NAMES.items()])
    fn("player/enter",
       "function aooni:player/clear_tags",
       "tag @s add aooni.player",
       "tag @s add aooni.alive",
       "scoreboard players operation @s aooni.gid = #gid aooni.var",
       *[f"execute if score #diff aooni.var matches {d} run scoreboard players set @s aooni.lives {DIFF[d]['lives']}" for d in DIFF],
       "scoreboard players set @s aooni.grace 0",
       "scoreboard players set @s aooni.hidet 0",
       "scoreboard players set @s aooni.leave 0",
       "team join aooni_alive @s",
       "gamemode adventure @s",
       "clear @s",
       "effect clear @s",
       "effect give @s minecraft:resistance infinite 4 true",
       "effect give @s minecraft:saturation infinite 0 true",
       "effect give @s minecraft:weakness infinite 9 true",
       "attribute @s minecraft:knockback_resistance base set 1",
       "spawnpoint @s 33 -60 30")
    fn("player/spawn_pos",
       "scoreboard players add #sp aooni.var 1",
       *[f"execute if score #sp aooni.var matches {i + 1} run tp @s {P(x + 0.5, F1, z + 0.5)} 180 0" for i, (x, z) in enumerate(SPAWN_POINTS)],
       f"execute if score #sp aooni.var matches {len(SPAWN_POINTS)}.. run scoreboard players set #sp aooni.var 0")
    fn("game/randomize",
       *[f"execute store result score #k{s_}{j} aooni.var run random value 0..9" for s_ in range(1, 5) for j in range(1, 5)],
       *[f"execute store result storage aooni:v k{s_}{j} int 1 run scoreboard players get #k{s_}{j} aooni.var" for s_ in range(1, 5) for j in range(1, 5)],
       *[f"execute store result score #p{i} aooni.var run random value 1..5" for i in range(1, 6)],
       *[f"execute if score #p{i} aooni.var matches {k} run data modify storage aooni:v n{i} set value \"{NOTE_NAME[k]}\""
         for i in range(1, 6) for k in range(1, 6)],
       *[f"execute store result storage aooni:v d{s_}{k} int 1 run scoreboard players get #d{s_}{k} aooni.var" for s_ in range(1, 5) for k in range(1, 5)])

    fn("game/tick",
       "execute as @e[type=minecraft:zombie,tag=aooni.oni] at @s run function aooni:oni/tick",
       "function aooni:hide/check",
       "execute as @e[type=minecraft:item_display,tag=aooni.altar_item] at @s run rotate @s ~4 0",
       "scoreboard players remove @a[tag=aooni.safe] aooni.grace 1",
       "tag @a[tag=aooni.safe,scores={aooni.grace=..0}] remove aooni.safe",
       "execute if score #stairs aooni.var matches 1 if score #store aooni.var matches 0 run function aooni:puzzle/plates")

    fn("game/sec",
       "scoreboard players add #sec aooni.var 1",
       "execute store result score #alive aooni.var if entity @a[tag=aooni.alive]",
       "execute store result score #jailed aooni.var if entity @a[tag=aooni.jailed]",
       "execute store result score #onis aooni.var if entity @e[type=minecraft:zombie,tag=aooni.oni]",
       "function aooni:game/sidebar",
       "bossbar set aooni:goal players @a[tag=aooni.player]",
       "execute if score #boss_up aooni.var matches 1 unless entity @e[type=minecraft:zombie,tag=aooni.boss] run return run function aooni:game/victory",
       "execute if score #alive aooni.var matches 0 run return run function aooni:game/end",
       "execute as @a[tag=aooni.alive] run function aooni:player/arm_check",
       "execute if score #oni_on aooni.var matches 1 run function aooni:oni/manager",
       "execute as @e[type=minecraft:zombie,tag=aooni.oni] at @s run function aooni:oni/sec",
       "execute as @a[tag=aooni.hidden] at @s run function aooni:hide/sec",
       "execute as @a[tag=aooni.alive,tag=!aooni.hidden] at @s if entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..12] run function aooni:player/near_oni",
       "execute if score #rescue_cd aooni.var matches 1.. run scoreboard players remove #rescue_cd aooni.var 1",
       f"execute as @a[tag=aooni.jailed] unless entity @s[x=1,y={Y1},z=31,dx=8,dy=5,dz=4] run tp @s {P(*JAIL)} 180 0",
       "scoreboard players remove #amb aooni.var 1",
       "execute if score #amb aooni.var matches ..0 run function aooni:fx/ambient",
       "function aooni:fx/glimmer")
    fn("game/sidebar",
       "scoreboard players operation §a생존자 aooni.side = #alive aooni.var",
       "scoreboard players operation §c감옥 aooni.side = #jailed aooni.var",
       "scoreboard players operation §6봉인(4) aooni.side = #weap aooni.var",
       "scoreboard players operation §7경과(분) aooni.side = #sec aooni.var",
       "scoreboard players set #60 aooni.var 60",
       "scoreboard players operation §7경과(분) aooni.side /= #60 aooni.var")
    prog_lines = ["scoreboard players operation #weap aooni.var = #w1 aooni.var"]
    prog_lines += [f"scoreboard players operation #weap aooni.var += #w{i} aooni.var" for i in range(2, 5)]
    prog_lines.append("execute store result bossbar aooni:goal value run scoreboard players get #weap aooni.var")
    prog_lines.append(f"scoreboard players set #goal aooni.var {len(GATES) + 1}")
    for i in range(len(GATES) - 1, -1, -1):   # 뒤에서부터 덮어써서 가장 앞의 미완료 관문이 남게
        prog_lines.append(f"execute if score {GATES[i][0]} aooni.var matches 0 run scoreboard players set #goal aooni.var {i + 1}")
    prog_lines.append(f"execute if score #weap aooni.var matches 4.. run scoreboard players set #goal aooni.var {len(GATES) + 2}")
    prog_lines.append(f"execute if score #final aooni.var matches 1 run scoreboard players set #goal aooni.var {len(GATES) + 3}")
    goals = [g for _, g in GATES] + [GOAL_SEALS, GOAL_ALTAR, GOAL_FINAL]
    for i, g in enumerate(goals, 1):
        prog_lines.append(f"execute if score #goal aooni.var matches {i} run bossbar set aooni:goal name " +
                          comp(T("봉인 ", "gray"), {"score": {"name": "#weap", "objective": "aooni.var"}, "color": "gold"},
                               T("/4 · ", "gray"), T("목표: ", "gold"), T(g, "white")))
    prog_lines.append("execute if score #oni_on aooni.var matches 1 run bossbar set aooni:goal color red")
    prog_lines.append("execute if score #oni_on aooni.var matches 0 run bossbar set aooni:goal color blue")
    fn("game/progress", *prog_lines)

    fn("game/end",
       "scoreboard players set #state aooni.var 2",
       "scoreboard players set #end_t aooni.var 10",
       "function aooni:oni/kill_all",
       "scoreboard players operation #min aooni.var = #sec aooni.var",
       "scoreboard players operation #min aooni.var /= #60 aooni.var",
       "scoreboard players operation #s aooni.var = #sec aooni.var",
       "scoreboard players operation #s aooni.var %= #60 aooni.var",
       "title @a times 10 100 30",
       f"title @a title {comp(T('전멸…', 'dark_red', bold=True))}",
       "title @a subtitle " + comp(T("봉인 ", "gray"), {"score": {"name": "#weap", "objective": "aooni.var"}, "color": "gold"},
                                   T("/4 · 버틴 시간 ", "gray"), {"score": {"name": "#min", "objective": "aooni.var"}, "color": "white"},
                                   T("분 ", "gray"), {"score": {"name": "#s", "objective": "aooni.var"}, "color": "white"}, T("초", "gray")),
       "execute as @a at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 1 0.6",
       tell("@a", T("\n[아오오니 저택] ", "blue"), T("모두 아오오니에게 당했다… 10초 뒤 대기실로 돌아갑니다.", "white")))
    fn("game/victory",
       "scoreboard players set #state aooni.var 2",
       "scoreboard players set #end_t aooni.var 12",
       "function aooni:oni/kill_all",
       "scoreboard players operation #min aooni.var = #sec aooni.var",
       "scoreboard players operation #min aooni.var /= #60 aooni.var",
       "scoreboard players operation #s aooni.var = #sec aooni.var",
       "scoreboard players operation #s aooni.var %= #60 aooni.var",
       "title @a times 10 120 30",
       f"title @a title {comp(T('아오오니를 족쳤다!', 'gold', bold=True))}",
       "title @a subtitle " + comp(T("최후의 일격: ", "gray"), {"selector": "@a[tag=aooni.lasthit]", "color": "aqua"},
                                   T(" · 걸린 시간 ", "gray"), {"score": {"name": "#min", "objective": "aooni.var"}, "color": "white"},
                                   T("분 ", "gray"), {"score": {"name": "#s", "objective": "aooni.var"}, "color": "white"}, T("초", "gray")),
       "execute as @a at @s run playsound minecraft:entity.ender_dragon.death master @s ~ ~ ~ 0.6 1.2",
       "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1",
       "execute as @a[tag=aooni.player,gamemode=adventure] at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 50",
       *door_cmds(33, F1, 36, "north", "left", True),
       *door_cmds(34, F1, 36, "north", "right", True),
       "time set 1000",
       tell("@a", T("\n[아오오니 저택] ", "blue"), T("거대 아오오니가 쓰러지자 현관문이 열리고 아침 햇살이 들어온다. ", "gold"),
            T("12초 뒤 대기실로 돌아갑니다.", "white")))
    fn("game/ending_sec",
       "scoreboard players remove #end_t aooni.var 1",
       "execute if score #end_t aooni.var matches ..0 run function aooni:game/reset")
    fn("game/reset",
       "function aooni:oni/kill_all",
       "scoreboard players set #state aooni.var 0",
       "scoreboard players set #cd aooni.var 0",
       "bossbar set aooni:goal visible false",
       "bossbar set aooni:boss visible false",
       "time set 18000",
       "kill @e[type=minecraft:item]",
       "scoreboard objectives setdisplay sidebar",
       "scoreboard players reset * aooni.side",
       "execute as @a[gamemode=!creative] run function aooni:player/to_lobby")

    # ---------------- 플레이어 사건
    fn("player/drop_weapons",
       "# 잡힌 자리(아오오니 발밑)에 검을 떨어뜨린다. 반짝여서 멀리서도 보인다",
       f"execute store result score #c aooni.var run clear @s minecraft:{WEAPON_ITEM} 0",
       "execute if score #c aooni.var matches 1.. run summon minecraft:item ~ ~1 ~ "
       f"{{Item:{{id:\"minecraft:{WEAPON_ITEM}\",count:1}},PickupDelay:30s,Age:-32768s,Glowing:1b,Invulnerable:1b}}",
       "execute if score #c aooni.var matches 1.. run " + tell("@a[tag=aooni.player]", T("전설의 검이 바닥에 떨어졌다! ", "gold", bold=True),
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
       "effect give @s minecraft:glowing infinite 0 true",
       actionbar("@s", T("전설의 검이 힘을 불어넣는다! ", "gold", bold=True), T("아오오니를 족쳐라!", "yellow")))
    fn("player/disarm",
       "tag @s remove aooni.armed",
       "effect clear @s minecraft:strength",
       "effect clear @s minecraft:glowing",
       "effect give @s minecraft:weakness infinite 9 true")
    fn("player/caught",
       "tag @e[type=minecraft:zombie,tag=aooni.oni,sort=nearest,limit=1] add aooni.got",
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
       tell("@a", SEL, T(" 이(가) 아오오니에게 잡혔다!", "red")),
       "execute if score @s aooni.lives matches 1.. run function aooni:player/jail",
       "execute if score @s aooni.lives matches ..0 run function aooni:player/out")
    fn("player/jail",
       "tag @s add aooni.jailed",
       "team join aooni_oni @s",
       f"tp @s {P(*JAIL)} 180 0",
       tell("@s", T("감옥에 갇혔다. 동료가 감옥 입구의 버튼을 누르면 풀려난다. 남은 목숨: ", "gray"),
            {"score": {"name": "@s", "objective": "aooni.lives"}, "color": "yellow"}))
    fn("player/out",
       "tag @s add aooni.out",
       "team join aooni_out @s",
       "gamemode spectator @s",
       f"tp @s {P(*SPEC_POS)} 0 60",
       tell("@a", SEL, T(" 은(는) 더 이상 돌아오지 못했다… (탈락)", "dark_gray")))
    fn("player/release",
       "tag @s remove aooni.jailed",
       "tag @s add aooni.alive",
       "team join aooni_alive @s",
       f"tp @s {P(*RELEASE)} 180 0",
       "tag @s add aooni.safe",
       "scoreboard players set @s aooni.grace 100",
       actionbar("@s", T("풀려났다! 5초간 아오오니에게 잡히지 않는다", "green")))
    fn("player/found",
       tell("@s", T("…옷장 문이 벌컥 열렸다!", "dark_red", bold=True)),
       "function aooni:player/caught")
    fn("player/near_oni",
       "playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1",
       "execute if entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..6] run playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1.3",
       actionbar("@s", T("…아오오니가 가까이 있다!", "red", bold=True)))

    # ---------------- 숨기
    hide = ["tag @a remove aooni.hid_new"]
    for c in CLOSETS:
        x, y, z, dx, dy, dz = c["box"]
        d = c["door"]
        hide.append(f"execute as @a[tag=aooni.alive,x={x},y={y},z={z},dx={dx},dy={dy},dz={dz}] "
                    f"if block {P(*d)} minecraft:spruce_door[open=false] run tag @s add aooni.hid_new")
    hide += ["execute as @a[tag=aooni.hid_new,tag=!aooni.hidden] run function aooni:hide/enter",
             "execute as @a[tag=aooni.hidden,tag=!aooni.hid_new] run function aooni:hide/leave"]
    fn("hide/check", *hide)
    fn("hide/enter",
       "tag @s add aooni.hidden",
       "team join aooni_oni @s",
       "scoreboard players set @s aooni.hidet 0",
       actionbar("@s", T("옷장에 숨었다… 숨을 죽이자", "dark_aqua")))
    fn("hide/leave",
       "tag @s remove aooni.hidden",
       "execute if entity @s[tag=aooni.alive] run team join aooni_alive @s",
       actionbar("@s", T("옷장에서 나왔다", "gray")))
    fn("hide/sec",
       "execute if entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..3] run scoreboard players add @s aooni.hidet 1",
       "execute unless entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..3] run scoreboard players set @s aooni.hidet 0",
       "execute if score @s aooni.hidet matches 1.. run playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1.4",
       "execute if score @s aooni.hidet matches 3.. store result score #r aooni.var run random value 1..3",
       "execute if score @s aooni.hidet matches 3.. if score #r aooni.var matches 1 at @e[type=minecraft:zombie,tag=aooni.oni,sort=nearest,limit=1] run function aooni:player/found")

    # ---------------- 아오오니
    fn("oni/tick",
       "execute on passengers run rotate @s ~ 0",
       "execute as @a[tag=aooni.alive,tag=!aooni.hidden,tag=!aooni.safe,gamemode=adventure,distance=..1.6,sort=nearest,limit=1] run function aooni:player/caught",
       "execute if entity @s[tag=aooni.boss] run return run function aooni:boss/tick",
       "execute if entity @s[tag=aooni.got] run return run function aooni:oni/vanish",
       "execute store result score @s aooni.hp run data get entity @s Health",
       f"execute if score @s aooni.hp matches ..{REPEL_HP} run function aooni:oni/repelled")
    fn("oni/repelled",
       "execute on attacker run " + tell("@a[tag=aooni.player]", SEL, T(" 이(가) 무기로 아오오니를 후려쳤다! ", "gold"),
                                         T("아오오니가 비명을 지르며 달아난다!", "yellow")),
       "playsound minecraft:entity.zombie.hurt hostile @a[distance=..24] ~ ~ ~ 1.2 0.5",
       "particle minecraft:crit ~ ~1.5 ~ 0.4 0.6 0.4 0.3 30",
       "tag @s add aooni.repel",
       "function aooni:oni/vanish",
       "scoreboard players add #oni_cd aooni.var 10")
    fn("oni/spawn",
       f"summon minecraft:zombie ~ ~ ~ {oni_summon_nbt()}",
       "execute as @e[type=minecraft:zombie,tag=aooni.new] at @s run function aooni:oni/init")
    fn("oni/init",
       "tag @s remove aooni.new",
       "team join aooni_oni @s",
       "effect give @s minecraft:invisibility infinite 0 true",
       "effect give @s minecraft:fire_resistance infinite 0 true",
       "attribute @s minecraft:knockback_resistance base set 1",
       "attribute @s minecraft:follow_range base set 48",
       "attribute @s minecraft:spawn_reinforcements base set 0",
       f"attribute @s minecraft:max_health base set {ONI_HP}",
       f"data merge entity @s {{Health:{ONI_HP}f}}",
       "function aooni:oni/apply_speed",
       "scoreboard players set @s aooni.life 0",
       "scoreboard players set @s aooni.lost 0",
       "scoreboard players set @s aooni.tgt 0",
       "particle minecraft:large_smoke ~ ~1 ~ 0.4 0.8 0.4 0.02 40",
       "playsound minecraft:block.wooden_door.open hostile @a[distance=..40] ~ ~ ~ 1.5 0.6",
       "playsound minecraft:entity.iron_golem.step hostile @a[distance=..30] ~ ~ ~ 1.5 0.5",
       tell("@a[tag=aooni.alive]", T("어디선가 문이 열리는 소리가 났다…", "dark_red", italic=True)),
       "function aooni:oni/retarget")
    speed = []
    for d, p in DIFF.items():
        speed.append(f"execute if score #diff aooni.var matches {d} run attribute @s minecraft:movement_speed base set {p['speed']}")
    fn("oni/apply_speed", *speed)
    fn("oni/retarget",
       "scoreboard players set @s aooni.tgt 0",
       "damage @s 0.01 minecraft:generic by @p[tag=aooni.alive,tag=!aooni.hidden,gamemode=adventure]")
    fn("oni/sec",
       "execute if entity @s[tag=aooni.boss] run return run function aooni:boss/sec",
       "scoreboard players add @s aooni.life 1",
       "scoreboard players add @s aooni.tgt 1",
       "execute if entity @a[tag=aooni.alive,tag=!aooni.hidden,distance=..16] run scoreboard players set @s aooni.lost 0",
       "execute unless entity @a[tag=aooni.alive,tag=!aooni.hidden,distance=..16] run scoreboard players add @s aooni.lost 1",
       "execute if score @s aooni.tgt matches 2.. if entity @a[tag=aooni.alive,tag=!aooni.hidden,distance=..22] run function aooni:oni/retarget",
       "playsound minecraft:entity.iron_golem.step hostile @a[distance=..18] ~ ~ ~ 0.9 0.5",
       *[f"execute if score #diff aooni.var matches {d} if score @s aooni.lost matches {p['lost']}.. run return run function aooni:oni/vanish" for d, p in DIFF.items()],
       *[f"execute if score #diff aooni.var matches {d} if score @s aooni.life matches {p['life']}.. if score @s aooni.lost matches 4.. run return run function aooni:oni/vanish" for d, p in DIFF.items()],
       "execute if entity @s[y=-70,dy=-200] run function aooni:oni/vanish")
    fn("oni/vanish",
       "particle minecraft:large_smoke ~ ~1 ~ 0.4 0.8 0.4 0.02 40",
       "playsound minecraft:entity.enderman.teleport hostile @a[distance=..24] ~ ~ ~ 1 0.5",
       "execute if entity @s[tag=aooni.got] run " + tell("@a[tag=aooni.alive]", T("아오오니는 사냥감을 끌고 어둠 속으로 사라졌다…", "dark_red", italic=True)),
       "execute unless entity @s[tag=aooni.got] unless entity @s[tag=aooni.repel] run " + tell("@a[tag=aooni.alive]", T("…발소리가 멀어졌다.", "gray", italic=True)),
       "execute on passengers run kill @s",
       "tag @s remove aooni.oni",
       "tp @s ~ -120 ~",
       "kill @s",
       "function aooni:oni/reset_cd")
    fn("oni/reset_cd",
       *[f"execute if score #diff aooni.var matches {d} store result score #oni_cd aooni.var run random value {p['cd']}" for d, p in DIFF.items()])
    fn("oni/kill_all",
       "execute as @e[type=minecraft:zombie,tag=aooni.oni] run tp @s ~ -120 ~",
       "kill @e[tag=aooni.part]",
       "kill @e[type=minecraft:zombie,tag=aooni.oni]",
       "bossbar set aooni:boss visible false")
    fn("oni/manager",
       "execute if score #final aooni.var matches 1 run return 0",
       *[f"execute if score #diff aooni.var matches {d} run scoreboard players set #oni_max aooni.var {p['base']}" for d, p in DIFF.items()],
       "execute store result score #n aooni.var if entity @a[tag=aooni.player]",
       "execute if score #stairs aooni.var matches 1 if score #n aooni.var matches 5.. run scoreboard players add #oni_max aooni.var 1",
       "execute if score #oni_max aooni.var matches 4.. run scoreboard players set #oni_max aooni.var 3",
       "execute if score #onis aooni.var >= #oni_max aooni.var run return 0",
       "scoreboard players remove #oni_cd aooni.var 1",
       "execute if score #oni_cd aooni.var matches ..0 run function aooni:oni/spawn_auto")
    fn("oni/spawn_auto",
       "tag @e[type=minecraft:marker,tag=aooni.cand] remove aooni.cand",
       "execute as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s if entity @a[tag=aooni.alive,distance=..36] unless entity @a[tag=aooni.alive,distance=..10] run tag @s add aooni.cand",
       "execute unless entity @e[type=minecraft:marker,tag=aooni.cand] as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s unless entity @a[tag=aooni.alive,distance=..7] run tag @s add aooni.cand",
       "execute at @e[type=minecraft:marker,tag=aooni.cand,sort=random,limit=1] run function aooni:oni/spawn",
       "function aooni:oni/reset_cd")
    fn("oni/alert",
       "# 소리를 낸 플레이어(태그 aooni.me) 쪽으로 아오오니가 반응한다",
       "execute as @e[type=minecraft:zombie,tag=aooni.oni] run damage @s 0.01 minecraft:generic by @a[tag=aooni.me,limit=1]",
       "execute unless entity @e[type=minecraft:zombie,tag=aooni.oni] if score #oni_on aooni.var matches 1 if score #oni_cd aooni.var matches 9.. run scoreboard players set #oni_cd aooni.var 8")
    fn("event/first_oni",
       "execute unless score #state aooni.var matches 1 run return 0",
       "execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] run function aooni:oni/spawn",
       "execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] as @a[tag=aooni.alive,distance=..24] run title @s times 5 40 15",
       f"execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] as @a[tag=aooni.alive,distance=..24] run title @s title {comp(T('……!', 'dark_red', bold=True))}",
       f"execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] as @a[tag=aooni.alive,distance=..24] run title @s subtitle {comp(T('책장 뒤에 무언가가 있다', 'red'))}",
       sound_all("minecraft:entity.elder_guardian.curse", 0.5, 0.8, "@a[tag=aooni.alive]"),
       tell("@a[tag=aooni.player]", T("쿵… 쿵… 무거운 발소리가 저택을 울린다. ", "dark_red", italic=True),
            T("아오오니가 나타났다!", "red", bold=True)),
       "function aooni:oni/reset_cd")

    # ---------------- 결전: 거대 아오오니
    fn("altar/check",
       "execute if score #altar aooni.var matches 1 run return 0",
       *[f"execute unless score #w{i} aooni.var matches 1 run return 0" for i in range(1, 5)],
       "scoreboard players set #altar aooni.var 1",
       f"summon minecraft:item_display 36.5 -58.4 28.5 {{Tags:[\"aooni.fx\",\"aooni.altar_item\"],"
       f"item:{{id:\"minecraft:{WEAPON_ITEM}\",count:1}},billboard:\"fixed\",brightness:{{sky:15,block:15}},"
       "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.9f,0.9f,0.9f]}}",
       "data modify entity @e[type=minecraft:text_display,tag=aooni.altar_t,limit=1] text set value "
       + J(T("전설의 검 · 버튼을 눌러 뽑아라", "gold", bold=True)),
       "title @a[tag=aooni.player] times 10 60 20",
       f"title @a[tag=aooni.player] title {comp(T('봉인이 모두 풀렸다', 'gold', bold=True))}",
       f"title @a[tag=aooni.player] subtitle {comp(T('현관홀 제단에 전설의 검이 나타났다', 'light_purple'))}",
       sound_all("minecraft:block.beacon.activate", 0.8),
       "function aooni:game/progress")
    fn("on/altar",
       "execute if score #wpn aooni.var matches 1 run return run " + tell("@s", T("제단은 비어 있다. 검은 이미 누군가 뽑았다.", "gray")),
       "execute if score #altar aooni.var matches 0 run return run " + tell("@s", T("제단에 자물쇠 구멍 네 개가 있다… ", "gray"),
                                                                       T("봉인 ", "light_purple"), {"score": {"name": "#weap", "objective": "aooni.var"}, "color": "gold"},
                                                                       T("/4 풀림", "light_purple")),
       "scoreboard players set #wpn aooni.var 1",
       "kill @e[type=minecraft:item_display,tag=aooni.altar_item]",
       "data modify entity @e[type=minecraft:text_display,tag=aooni.altar_t,limit=1] text set value " + J(T("제단 · 비었음", "gray")),
       "function aooni:weapon/give",
       "particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 60",
       "playsound minecraft:item.trident.thunder master @a[distance=..32] ~ ~ ~ 0.8 1.2",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) 제단에서 ", "white"), T(f"[{WEAPON_NAME}]", "gold", bold=True),
            T("을(를) 뽑았다! ", "white"), T("…저택 깊은 곳에서 무언가가 울부짖는다.", "red", italic=True)),
       "function aooni:final/check")
    fn("weapon/give",
       "# 이름 붙은 검을 먼저 시도하고(아이템 컴포넌트 문법은 버전마다 다를 수 있다), 안 되면 그냥 검을 준다",
       "scoreboard players set #ok aooni.var 0",
       f'function aooni:weapon/give_named {{nm:"{WEAPON_NAME}"}}',
       f"execute if score #ok aooni.var matches 0 run give @s minecraft:{WEAPON_ITEM}",
       "function aooni:player/arm_check")
    fn("weapon/give_named",
       f'$execute store success score #ok aooni.var run give @s minecraft:{WEAPON_ITEM}'
       '[minecraft:custom_name={text:"$(nm)",color:"gold",italic:false},minecraft:enchantment_glint_override=true]')
    fn("final/check",
       "execute if score #final aooni.var matches 1 run return 0",
       "execute unless score #wpn aooni.var matches 1 run return 0",
       "scoreboard players set #final aooni.var 1",
       "title @a[tag=aooni.player] times 10 60 20",
       f"title @a[tag=aooni.player] title {comp(T('검이 뽑혔다', 'gold', bold=True))}",
       f"title @a[tag=aooni.player] subtitle {comp(T('…거대한 무언가가 깨어난다', 'red', italic=True))}",
       sound_all("minecraft:entity.ravager.roar", 0.5, 0.8),
       tell("@a[tag=aooni.player]", T("5초 뒤 ", "gray"), T("거대 아오오니", "dark_red", bold=True),
            T("가 나타난다. 검을 든 사람은 앞으로, 나머지는 유인과 감옥 구출을 맡자!", "gray")),
       "schedule function aooni:final/start 100t",
       "function aooni:game/progress")
    fn("final/start",
       "execute unless score #state aooni.var matches 1 run return 0",
       "execute as @e[type=minecraft:zombie,tag=aooni.oni,tag=!aooni.boss] at @s run function aooni:oni/vanish",
       "execute store result score #n aooni.var if entity @a[tag=aooni.player]",
       f"scoreboard players set #k aooni.var {BOSS_HP_PER}",
       "scoreboard players operation #bhp aooni.var = #n aooni.var",
       "scoreboard players operation #bhp aooni.var *= #k aooni.var",
       f"scoreboard players add #bhp aooni.var {BOSS_HP_BASE}",
       f"execute if score #bhp aooni.var matches {BOSS_HP_CAP + 1}.. run scoreboard players set #bhp aooni.var {BOSS_HP_CAP}",
       "scoreboard players operation #bmax aooni.var = #bhp aooni.var",
       "scoreboard players set #k aooni.var 5",
       "scoreboard players operation #half10 aooni.var = #bmax aooni.var",
       "scoreboard players operation #half10 aooni.var *= #k aooni.var",
       "tag @e[type=minecraft:marker,tag=aooni.cand] remove aooni.cand",
       "execute as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s if entity @a[tag=aooni.alive,distance=..30] unless entity @a[tag=aooni.alive,distance=..12] run tag @s add aooni.cand",
       "execute unless entity @e[type=minecraft:marker,tag=aooni.cand] as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s unless entity @a[tag=aooni.alive,distance=..6] run tag @s add aooni.cand",
       "execute at @e[type=minecraft:marker,tag=aooni.cand,sort=random,limit=1] run function aooni:boss/spawn",
       "execute unless entity @e[type=minecraft:zombie,tag=aooni.boss] positioned 23.5 -60 14.5 run function aooni:boss/spawn",
       "execute store result bossbar aooni:boss max run scoreboard players get #bmax aooni.var",
       "execute store result bossbar aooni:boss value run scoreboard players get #bmax aooni.var",
       "bossbar set aooni:boss players @a[tag=aooni.player]",
       "bossbar set aooni:boss visible true",
       "scoreboard players set #boss_up aooni.var 1",
       "title @a[tag=aooni.player] times 5 60 20",
       f"title @a[tag=aooni.player] title {comp(T('거대 아오오니', 'dark_red', bold=True))}",
       f"title @a[tag=aooni.player] subtitle {comp(T('무기로 족쳐라!', 'gold'))}",
       sound_all("minecraft:entity.wither.spawn", 0.7, 0.5),
       "function aooni:game/progress")
    fn("boss/spawn",
       f"summon minecraft:zombie ~ ~ ~ {oni_summon_nbt(1.45, ('aooni.oni', 'aooni.boss', 'aooni.new'))}",
       "execute as @e[type=minecraft:zombie,tag=aooni.new] at @s run function aooni:boss/init")
    fn("boss/init",
       "tag @s remove aooni.new",
       "team join aooni_oni @s",
       "effect give @s minecraft:invisibility infinite 0 true",
       "effect give @s minecraft:fire_resistance infinite 0 true",
       "attribute @s minecraft:knockback_resistance base set 1",
       "attribute @s minecraft:follow_range base set 64",
       "attribute @s minecraft:spawn_reinforcements base set 0",
       "attribute @s minecraft:max_health base set 1024",
       "execute store result entity @s Health float 1 run scoreboard players get #bhp aooni.var",
       "execute store result score #bhp_prev aooni.var run data get entity @s Health 10",
       "function aooni:boss/apply_speed",
       "scoreboard players set @s aooni.life 0",
       "scoreboard players set @s aooni.tgt 0",
       "particle minecraft:large_smoke ~ ~1.5 ~ 0.8 1.2 0.8 0.03 120",
       "playsound minecraft:entity.ravager.roar hostile @a[distance=..48] ~ ~ ~ 2 0.5",
       "function aooni:oni/retarget")
    bspeed = []
    for d, p in DIFF.items():
        bspeed.append(f"execute if score #diff aooni.var matches {d} run attribute @s minecraft:movement_speed base set {p['boss_speed']}")
        bspeed.append(f"execute if score #diff aooni.var matches {d} if entity @s[tag=aooni.enraged] run attribute @s minecraft:movement_speed base set {round(p['boss_speed'] + ENRAGE_SPEED_BONUS, 3)}")
    fn("boss/apply_speed", *bspeed)
    fn("boss/tick",
       "tag @s remove aooni.got",
       "execute store result score #bh aooni.var run data get entity @s Health 10",
       "execute store result bossbar aooni:boss value run data get entity @s Health",
       "scoreboard players operation #bd aooni.var = #bhp_prev aooni.var",
       "scoreboard players operation #bd aooni.var -= #bh aooni.var",
       "execute if score #bd aooni.var matches 5.. run function aooni:boss/hurt",
       "scoreboard players operation #bhp_prev aooni.var = #bh aooni.var")
    fn("boss/hurt",
       "# 0.5 이상 깎였을 때만(추격용 0.01 피해는 무시) 마지막으로 때린 사람을 기억한다",
       "tag @a remove aooni.lasthit",
       "execute on attacker run tag @s add aooni.lasthit",
       "particle minecraft:crit ~ ~1.8 ~ 0.5 0.8 0.5 0.3 15",
       "playsound minecraft:entity.zombie.hurt hostile @a[distance=..24] ~ ~ ~ 1 0.5",
       "execute unless entity @s[tag=aooni.enraged] if score #bh aooni.var <= #half10 aooni.var run function aooni:boss/enrage")
    fn("boss/enrage",
       "tag @s add aooni.enraged",
       "function aooni:boss/apply_speed",
       "playsound minecraft:entity.ravager.roar hostile @a[distance=..48] ~ ~ ~ 2 0.4",
       "title @a[tag=aooni.player] times 5 40 10",
       f"title @a[tag=aooni.player] title {comp(T('', 'red'))}",
       f"title @a[tag=aooni.player] subtitle {comp(T('거대 아오오니가 격노했다! 더 빨라졌다!', 'red', bold=True))}")
    fn("boss/sec",
       "scoreboard players add @s aooni.life 1",
       "scoreboard players add @s aooni.tgt 1",
       "execute if score @s aooni.tgt matches 2.. run function aooni:oni/retarget",
       "playsound minecraft:entity.iron_golem.step hostile @a[distance=..24] ~ ~ ~ 1.2 0.4",
       "scoreboard players operation #m aooni.var = @s aooni.life",
       "scoreboard players operation #m aooni.var %= #12 aooni.var",
       "execute if score #m aooni.var matches 0 run function aooni:boss/roar")
    fn("boss/roar",
       "playsound minecraft:entity.ravager.roar hostile @a[distance=..32] ~ ~ ~ 1.5 0.6",
       "particle minecraft:sonic_boom ~ ~1.5 ~ 0 0 0 0 1",
       "effect give @a[tag=aooni.alive,distance=..7] minecraft:slowness 2 1 true",
       "effect give @a[tag=aooni.alive,distance=..7] minecraft:darkness 3 0 true",
       "execute as @a[tag=aooni.alive,distance=..7] run " + actionbar("@s", T("포효에 몸이 굳는다…!", "red", bold=True)))

    # ---------------- 효과
    fn("fx/ambient",
       "execute store result score #r aooni.var run random value 1..4",
       "execute if score #r aooni.var matches 1 as @a[tag=aooni.alive] at @s run playsound minecraft:ambient.cave ambient @s ~ ~ ~ 1 0.8",
       "execute if score #r aooni.var matches 2 as @a[tag=aooni.alive] at @s run playsound minecraft:block.wooden_door.close ambient @s ~4 ~ ~-3 0.6 0.5",
       "execute if score #r aooni.var matches 3 as @a[tag=aooni.alive] at @s run playsound minecraft:entity.zombie.ambient ambient @s ~-5 ~ ~5 0.4 0.4",
       "execute if score #r aooni.var matches 4 as @a[tag=aooni.alive] at @s run playsound minecraft:block.note_block.chime ambient @s ~ ~2 ~ 0.4 0.5",
       "execute store result score #amb aooni.var run random value 30..60")
    pos = {a[0]: (a[1], a[2], a[3]) for a in ACTS}

    def glim(aid, cond):
        x, y, z = pos[aid]
        return f"execute {cond} run particle minecraft:glow {P(x + 0.5, y + 0.35, z + 0.5)} 0.15 0.1 0.15 0 3"
    fn("fx/glimmer",
       glim("s_liv_cab", "if score #k_lib aooni.var matches 0"),
       glim("s_bath_mirror", "if score #pw1 aooni.var matches 0"),
       glim("s_lib_desk", "if score #lib aooni.var matches 1 if score #k_din aooni.var matches 0"),
       glim("s_lib_sheet", "if score #lib aooni.var matches 1 if score #sheet aooni.var matches 0"),
       glim("s_din_plate", "if score #din aooni.var matches 1 if score #pw2 aooni.var matches 0"),
       glim("s_kid_draw", "if score #stairs aooni.var matches 1 if score #q1 aooni.var matches 0"),
       glim("s_gr_bag", "if score #stairs aooni.var matches 1 if score #q2 aooni.var matches 0"),
       glim("s_spare_mirror", "if score #stairs aooni.var matches 1 if score #q3 aooni.var matches 0"),
       glim("s_mb_diary", "if score #stairs aooni.var matches 1 if score #q4 aooni.var matches 0"),
       *[glim(f"safe{s_}_ok", f"if score #pw{s_} aooni.var matches 1 if score #w{s_} aooni.var matches 0") for s_ in range(1, 5)],
       glim("altar", "if score #altar aooni.var matches 1 if score #wpn aooni.var matches 0"))

    # ---------------- 상호작용(버튼) 폴링
    poll = []
    for (aid, x, y, z, state, kind, scope) in ACTS:
        poll.append(f"execute if block {P(x, y, z)} minecraft:{kind}[powered=true] run function aooni:act/{aid}")
        who = "@p[gamemode=!spectator,distance=..6]" if scope == "lobby" else "@p[tag=aooni.alive,distance=..6]"
        cond = "" if scope == "lobby" else "if score #state aooni.var matches 1 "
        fn(f"act/{aid}",
           f"setblock {P(x, y, z)} {state}",
           f"execute {cond}positioned {P(x + 0.5, y + 0.5, z + 0.5)} as {who} at @s run function aooni:on/{aid}")
    fn("act/poll", *poll)

    def locked_msg(what):
        return ["playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 1",
                tell("@s", T(f"{what} 잠겨 있다. ", "gray"), T("열쇠가 필요하다.", "red"))]

    def found_key(flag, key, where):
        return [f"execute if score {flag} aooni.var matches 1 run return run " + tell("@s", T(f"{where}에는 더 이상 아무것도 없다.", "gray")),
                f"scoreboard players set {flag} aooni.var 1",
                tell("@a[tag=aooni.player]", SEL, T(f" 이(가) {where}에서 ", "white"), T(f"[{key}]", "gold", bold=True), T("을(를) 찾았다!", "white")),
                sound_all("minecraft:entity.experience_orb.pickup", 1.2),
                "function aooni:game/progress"]

    def flavor(aid, *msg, extra=()):
        fn(f"on/{aid}", "playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1",
           tell("@s", *[T(m, "gray", italic=True) if isinstance(m, str) else m for m in msg]), *extra)

    # 문
    fn("on/d_lib",
       "execute if score #lib aooni.var matches 1 run return run " + tell("@s", T("서재 문은 열려 있다.", "gray")),
       "execute if score #k_lib aooni.var matches 0 run return run function aooni:msg/locked_lib",
       *door_cmds(7, F1, 12, "north", "left", True),
       "playsound minecraft:block.iron_door.open block @a[distance=..16] ~ ~ ~ 1 0.8",
       "scoreboard players set #lib aooni.var 1",
       "tag @e[type=minecraft:marker,tag=aooni.z2] add aooni.on",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) ", "white"), T("서재", "gold"), T(" 문을 열었다.", "white")),
       "function aooni:game/progress")
    fn("msg/locked_lib", *locked_msg("서재 문이"))
    fn("on/d_din",
       "execute if score #din aooni.var matches 1 run return run " + tell("@s", T("식당 문은 열려 있다.", "gray")),
       "execute if score #k_din aooni.var matches 0 run return run function aooni:msg/locked_din",
       *door_cmds(29, F1, 12, "north", "left", True),
       "playsound minecraft:block.iron_door.open block @a[distance=..16] ~ ~ ~ 1 0.8",
       "scoreboard players set #din aooni.var 1",
       "tag @e[type=minecraft:marker,tag=aooni.z3] add aooni.on",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) ", "white"), T("식당", "gold"), T(" 문을 열었다. 안쪽에서 피아노가 보인다…", "white")),
       "function aooni:game/progress")
    fn("msg/locked_din", *locked_msg("식당 문이"))
    fn("on/d_stairs",
       "execute if score #stairs aooni.var matches 1 run return run " + tell("@s", T("계단 철문은 열려 있다.", "gray")),
       "playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 0.8",
       tell("@s", T("굳게 닫힌 철문이다. 열쇠 구멍이 없다…", "gray"), T(" 어디선가 피아노 소리가 나면 열릴 것 같다.", "dark_aqua")))
    fn("on/d_store",
       "execute if score #store aooni.var matches 1 run return run " + tell("@s", T("창고 문은 열려 있다.", "gray")),
       "playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 0.8",
       tell("@s", T("창고 철문. 문 옆에 네 개의 작은 등불이 꺼져 있다… ", "gray"),
            T("(네 방의 발판을 동시에 밟아야 한다)", "dark_aqua")))
    fn("on/d_front",
       "playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 0.7",
       tell("@s", T("현관문은 꿈쩍도 하지 않는다… ", "gray"), T("아오오니를 쓰러뜨리기 전에는 나갈 수 없을 것 같다.", "red")))

    # 조사 지점: 열쇠/단서
    fn("on/s_liv_cab", *found_key("#k_lib", "서재 열쇠", "장식장 서랍"))
    fn("on/s_lib_desk",
       *found_key("#k_din", "식당 열쇠", "서재 책상")[:-1],
       "scoreboard players set #oni_on aooni.var 1",
       "scoreboard players set #oni_cd aooni.var 100",
       "playsound minecraft:block.wooden_door.close hostile @a[distance=..24] 2 -59 2 1 0.5",
       "schedule function aooni:event/first_oni 40t",
       "function aooni:game/progress")
    fn("on/s_lib_sheet",
       "playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1",
       "execute if score #sheet aooni.var matches 0 run " + tell("@a[tag=aooni.player]", SEL, T(" 이(가) 책장 사이에서 ", "white"),
                                                               T("[악보]", "gold", bold=True), T("를 찾았다! 피아노실 악보대에 옮겨 두었다.", "white")),
       "scoreboard players set #sheet aooni.var 1",
       "function aooni:piano/show_sheet with storage aooni:v",
       "function aooni:game/progress")
    fn("piano/show_sheet",
       '$tellraw @s {"text":"♪ 악보:  $(n1) → $(n2) → $(n3) → $(n4) → $(n5)","color":"light_purple","bold":true}',
       '$data modify entity @e[type=minecraft:text_display,tag=aooni.sheet,limit=1] text set value {"text":"♪ $(n1) $(n2) $(n3) $(n4) $(n5)","color":"light_purple"}')

    # 비밀번호 ①②③ 은 한 번에 통째로, ④ 는 2층 네 곳에 한 자리씩 흩어져 있다
    def pw_found(s_, what, desc):
        code = "$(k%d1)$(k%d2)$(k%d3)$(k%d4)" % (s_, s_, s_, s_)
        fn(f"clue/pw{s_}",
           f'$tellraw @s {{"text":"『 봉인{CIRC[s_]} 비밀번호: {code} 』","color":"dark_red","bold":true}}',
           f'$data modify entity @e[type=minecraft:text_display,tag=aooni.pw{s_},limit=1] text set value '
           f'{{"text":"봉인{CIRC[s_]} {code}","color":"dark_red","bold":true}}')
        return ["playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1",
                tell("@s", T(desc, "gray", italic=True)),
                f"function aooni:clue/pw{s_} with storage aooni:v",
                f"execute if score #pw{s_} aooni.var matches 0 run " + tell("@a[tag=aooni.player]", SEL, T(f" 이(가) {what}에서 ", "white"),
                                                                           T(f"봉인{CIRC[s_]} 비밀번호", "gold", bold=True), T("를 찾았다!", "white")),
                f"execute if score #pw{s_} aooni.var matches 0 run " + sound_all("minecraft:entity.experience_orb.pickup", 1.4),
                f"scoreboard players set #pw{s_} aooni.var 1"]
    fn("on/s_bath_mirror", *pw_found(1, "화장실 거울", "김 서린 거울에 손가락으로 쓴 숫자가 떠오른다…"))
    fn("on/s_din_plate", *pw_found(2, "식당 접시", "빈 접시 위에 붉은 소스로 숫자가 쓰여 있다…"))

    ORD = {1: "첫째", 2: "둘째", 3: "셋째", 4: "넷째"}

    def q_found(j, what, desc):
        fn(f"clue/q{j}",
           f'$tellraw @s {{"text":"『 봉인④ {ORD[j]} 자리: $(k4{j}) 』","color":"dark_red","bold":true}}',
           f'$data modify entity @e[type=minecraft:text_display,tag=aooni.q{j},limit=1] text set value '
           f'{{"text":"④-{j}: $(k4{j})","color":"dark_red","bold":true}}')
        return [tell("@s", T(desc, "gray", italic=True)),
                f"function aooni:clue/q{j} with storage aooni:v",
                f"execute if score #q{j} aooni.var matches 0 run " + tell("@a[tag=aooni.player]", SEL, T(f" 이(가) {what}에서 ", "white"),
                                                                         T(f"봉인④의 {ORD[j]} 자리", "gold", bold=True), T("를 찾았다!", "white")),
                f"scoreboard players set #q{j} aooni.var 1"]
    fn("on/s_kid_draw", "playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1",
       *q_found(1, "아이방 그림", "크레파스로 그린 파란 괴물. 구석에 '④-1' 과 숫자가…"))
    fn("on/s_gr_bag", "playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1",
       *q_found(2, "여행 가방", "가방 속 쪽지: '④-2' 와 숫자 하나."))

    # 조사 지점: 분위기
    flavor("s_lib_diary", "낡은 일기장: ", "'이 집에는 무언가가 산다. 파랗고, 거대하고… 문을 잠가도 소용없다.'")
    flavor("s_din_candle", "촛불이 흔들린다. 누군가 방금 옆을 지나간 것처럼…")
    flavor("s_jail_note", "벽에 손톱으로 긁은 글씨: ", "'도망쳐… 파란… 숨어…'")
    flavor("s_bath_tub", "욕조에 검푸른 물이 고여 있다. 손대지 않는 게 좋겠다.")
    flavor("s_liv_fire", "벽난로 재 속에 타다 남은 사진 조각… ", "'1999년 여름, 가족과 함께'")
    flavor("s_liv_clock", "괘종시계가 멈춰 있다. 바늘은 3시 33분을 가리킨다.")
    flavor("s_hall_vase", "꽃병의 장미는 오래전에 시들었다.")
    flavor("s_hall_photo", "가족사진. 아이의 얼굴만 검게 칠해져 있다…")
    flavor("s_kit_fridge", "냉장고 문을 살짝 열었다가… 아무것도 못 본 걸로 하자.")
    flavor("s_kit_sink", "싱크대. 식칼꽂이에 칼 하나가 비어 있다.")
    flavor("s_mb_diary", "부부의 일기: ",
           T("'아이방, 손님방, 작업실, 그리고 우리 방. 네 방의 발판을 동시에 밟으면 창고가 열린다.' ", "dark_aqua"),
           "마지막 장 귀퉁이에 숫자가 적혀 있다.", extra=q_found(4, "부부의 일기", "'④-4'"))
    flavor("s_st_note", "설계 메모: ",
           T("'녀석을 벨 수 있는 건 전설의 검뿐. 검은 네 개의 봉인으로 제단에 잠가 두었다… 검을 뽑으면 녀석의 본체가 깨어난다.'", "dark_aqua"))
    flavor("s_sto_box", "낡은 상자. 아이 장난감이 가득하다.")
    flavor("s_kid_toy", "오르골이 저절로 울리기 시작했다…",
           extra=("playsound minecraft:block.note_block.chime block @a[distance=..16] ~ ~ ~ 1 0.6",
                  "schedule function aooni:fx/musicbox 10t"))
    fn("fx/musicbox",
       "execute as @a[tag=aooni.alive] at @s if entity @e[type=minecraft:marker,tag=aooni.z4,distance=..14] run playsound minecraft:block.note_block.chime block @s ~ ~ ~ 0.6 0.8")
    flavor("s_spare_mirror", "거울 속, 내 어깨 너머로 파란 무언가가… 돌아보니 아무도 없다.",
           extra=("effect give @s minecraft:darkness 3 0 true",
                  "playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 0.6 1.2",
                  *q_found(3, "다락방 거울", "거울 아래에 '④-3' 과 숫자가 긁혀 있다…")))

    # 감옥 구출
    fn("on/rescue",
       "execute unless entity @a[tag=aooni.jailed] run return run " + tell("@s", T("감옥은 비어 있다.", "gray")),
       "execute if score #rescue_cd aooni.var matches 1.. run return run " + tell("@s", T("자물쇠가 아직 돌아가지 않는다… 잠시 후 다시.", "gray")),
       *door_cmds(5, F1, 30, "north", "left", True),
       "schedule function aooni:jail/close 60t",
       "playsound minecraft:block.iron_door.open block @a[distance=..20] ~ ~ ~ 1 0.7",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) 감옥 문을 열었다! ", "green"),
            T("…쇳소리에 아오오니가 반응한다.", "dark_red", italic=True)),
       "execute as @a[tag=aooni.jailed] run function aooni:player/release",
       "scoreboard players set #rescue_cd aooni.var 20",
       "tag @s add aooni.me",
       "function aooni:oni/alert",
       "tag @s remove aooni.me")
    fn("jail/close", *door_cmds(5, F1, 30, "north", "left", False))

    # 피아노
    for k in range(1, 6):
        fn(f"on/piano{k}",
           f"playsound minecraft:block.note_block.harp block @a[distance=..16] ~ ~ ~ 1 {NOTE_PITCH[k]}",
           "execute if score #stairs aooni.var matches 1 run return run function aooni:clue/pw3 with storage aooni:v",
           f"scoreboard players set #key aooni.var {k}",
           "function aooni:piano/press")
    fn("piano/press",
       "scoreboard players add #pstep aooni.var 1",
       *[f"execute if score #pstep aooni.var matches {i} run scoreboard players operation #exp aooni.var = #p{i} aooni.var" for i in range(1, 6)],
       "execute unless score #key aooni.var = #exp aooni.var run return run function aooni:piano/wrong",
       "execute if score #pstep aooni.var matches 5.. run function aooni:piano/solved")
    fn("piano/wrong",
       "scoreboard players set #pstep aooni.var 0",
       "execute if score #key aooni.var = #p1 aooni.var run scoreboard players set #pstep aooni.var 1",
       "playsound minecraft:block.note_block.bass block @a[distance=..16] ~ ~ ~ 1 0.5",
       "execute store result score #r aooni.var run random value 1..4",
       "execute if score #r aooni.var matches 1 run " + tell("@s", T("불협화음이 저택에 울려 퍼졌다…", "dark_red", italic=True)),
       "execute if score #r aooni.var matches 1 run tag @s add aooni.me",
       "execute if score #r aooni.var matches 1 run function aooni:oni/alert",
       "tag @s remove aooni.me")
    fn("piano/solved",
       "scoreboard players set #stairs aooni.var 1",
       *door_cmds(16, F1, 12, "north", "left", True),
       *door_cmds(17, F1, 12, "north", "right", True),
       "tag @e[type=minecraft:marker,tag=aooni.z4] add aooni.on",
       sound_all("minecraft:block.note_block.bell", 1.0),
       sound_all("minecraft:block.iron_door.open", 0.5, 0.7),
       tell("@a[tag=aooni.player]", T("♪ 아름다운 선율이 끝나자, 어딘가에서 ", "light_purple"), T("계단의 철문", "gold"),
            T("이 열리는 소리가 났다! 피아노 뚜껑 안쪽에 숫자가 새겨져 있다…", "light_purple")),
       *pw_found(3, "피아노 뚜껑", "뚜껑 안쪽에 새겨진 숫자:")[2:],
       "function aooni:game/progress")

    # 발판
    plates = [(2, F2, 10), (24, F2, 10), (3, F2, 32), (27, F2, 20)]
    fn("puzzle/plates",
       "scoreboard players set #pl aooni.var 0",
       *[f"execute if entity @a[tag=aooni.alive,x={x},y={y},z={z},dx=0,dy=0,dz=0] run scoreboard players add #pl aooni.var 1" for (x, y, z) in plates],
       "execute if score #pl aooni.var matches 0 run return 0",
       "scoreboard players operation #need aooni.var = #alive aooni.var",
       "execute if score #need aooni.var matches 5.. run scoreboard players set #need aooni.var 4",
       "execute if score #need aooni.var matches ..0 run scoreboard players set #need aooni.var 1",
       *[f"execute as @a[tag=aooni.alive,x={x},y={y},z={z},dx=0,dy=0,dz=0] run " +
         actionbar("@s", T("발판 ", "aqua"), {"score": {"name": "#pl", "objective": "aooni.var"}, "color": "white"},
                   T(" / ", "gray"), {"score": {"name": "#need", "objective": "aooni.var"}, "color": "white"},
                   T("  — 다른 방의 발판도 동시에!", "gray")) for (x, y, z) in plates],
       "execute if score #pl aooni.var >= #need aooni.var run function aooni:puzzle/plates_solved")
    fn("puzzle/plates_solved",
       "scoreboard players set #store aooni.var 1",
       *door_cmds(41, F2, 12, "north", "left", True),
       "tag @e[type=minecraft:marker,tag=aooni.z5] add aooni.on",
       sound_all("minecraft:block.iron_door.open", 0.7),
       sound_all("minecraft:entity.player.levelup", 0.8, 0.6),
       tell("@a[tag=aooni.player]", T("철컥! 2층 ", "white"), T("창고", "gold"), T(" 문이 열렸다!", "white")),
       "function aooni:game/progress")

    # 봉인 4개: 비밀번호를 맞히면 풀린다. 넷 다 풀리면 제단에 검
    for s_ in range(1, 5):
        for k in range(1, 5):
            fn(f"on/safe{s_}_d{k}",
               f"execute if score #w{s_} aooni.var matches 1 run return run " + tell("@s", T(f"봉인{CIRC[s_]}는 이미 풀렸다.", "gray")),
               f"scoreboard players add #d{s_}{k} aooni.var 1",
               f"execute if score #d{s_}{k} aooni.var matches 10.. run scoreboard players set #d{s_}{k} aooni.var 0",
               f"execute store result storage aooni:v d{s_}{k} int 1 run scoreboard players get #d{s_}{k} aooni.var",
               f"function aooni:safe/show{s_} with storage aooni:v",
               "playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6")
        fn(f"safe/show{s_}", *[
            f'$data modify entity @e[type=minecraft:text_display,tag=aooni.dial{s_}{k},limit=1] text set value {{"text":"$(d{s_}{k})","color":"white","bold":true}}'
            for k in range(1, 5)])
        fn(f"on/safe{s_}_ok",
           f"execute if score #w{s_} aooni.var matches 1 run return run " + tell("@s", T(f"봉인{CIRC[s_]}는 이미 풀렸다.", "gray")),
           *[f"execute unless score #d{s_}{k} aooni.var = #k{s_}{k} aooni.var run return run function aooni:safe/wrong" for k in range(1, 5)],
           f"scoreboard players set #w{s_} aooni.var 1",
           "playsound minecraft:block.iron_door.open block @a[distance=..12] ~ ~ ~ 1 1.4",
           sound_all("minecraft:block.amethyst_block.chime", 0.8, 1.0),
           "particle minecraft:enchant ~ ~1 ~ 0.4 0.6 0.4 0.5 40",
           "function aooni:game/progress",
           tell("@a[tag=aooni.player]", SEL, T(f" 이(가) 봉인{CIRC[s_]}를 풀었다! ", "light_purple"), T("(", "gray"),
                {"score": {"name": "#weap", "objective": "aooni.var"}, "color": "gold"}, T("/4)", "gray")),
           f"data modify entity @e[type=minecraft:text_display,tag=aooni.safe{s_},limit=1] text set value "
           + J(T(f"봉인{CIRC[s_]} · 풀림", "green")),
           "function aooni:altar/show",
           "function aooni:altar/check")
    fn("altar/show",
       "execute if score #altar aooni.var matches 0 store result storage aooni:v n int 1 run scoreboard players get #weap aooni.var",
       "execute if score #altar aooni.var matches 0 run function aooni:altar/show_n with storage aooni:v")
    fn("altar/show_n",
       '$data modify entity @e[type=minecraft:text_display,tag=aooni.altar_t,limit=1] text set value {"text":"제단 · 봉인 $(n)/4","color":"light_purple"}')
    fn("safe/wrong",
       "playsound minecraft:block.chest.locked block @a[distance=..12] ~ ~ ~ 1 0.6",
       "playsound minecraft:block.anvil.land block @a[distance=..16] ~ ~ ~ 0.4 0.5",
       tell("@s", T("…비밀번호가 틀렸다. 금속음이 저택에 울렸다!", "red"), T(" (단서를 다시 확인하자)", "gray")),
       "tag @s add aooni.me",
       "function aooni:oni/alert",
       "tag @s remove aooni.me")

    # ---------------- 관리자 명령
    fn("admin/start", "scoreboard players set #cd aooni.var 0", "execute if score #state aooni.var matches 0 run function aooni:game/start")
    fn("admin/stop",
       "execute if score #state aooni.var matches 1 run " + tell("@a", T("[아오오니 저택] 관리자가 게임을 중단했습니다.", "red")),
       "function aooni:game/reset")
    fn("admin/rebuild", "scoreboard players set #built aooni.var 0", "function aooni:setup/check_build")
    for d, (n, c) in DIFF_NAMES.items():
        fn(f"admin/difficulty_{d}", f"scoreboard players set #diff aooni.var {d}", "function aooni:lobby/show_diff",
           tell("@a", T("난이도: ", "gray"), T(n, c, bold=True)))
    fn("admin/final_now",
       "# 테스트용: 봉인을 모두 풀고 생존자 한 명에게 검을 줘서 바로 결전",
       "execute unless score #state aooni.var matches 1 run return run " + tell("@s", T("게임 중에만 쓸 수 있습니다.", "red")),
       *[f"scoreboard players set #w{i} aooni.var 1" for i in range(1, 5)],
       "scoreboard players set #oni_on aooni.var 1",
       "function aooni:game/progress",
       "function aooni:altar/check",
       "scoreboard players set #wpn aooni.var 1",
       "kill @e[type=minecraft:item_display,tag=aooni.altar_item]",
       "execute as @r[tag=aooni.alive] run function aooni:weapon/give",
       "function aooni:final/check")
    fn("admin/oni_now", "execute if score #state aooni.var matches 1 run scoreboard players set #oni_on aooni.var 1",
       "execute if score #state aooni.var matches 1 run function aooni:oni/spawn_auto")
    fn("admin/help",
       tell("@s", T("\n[아오오니 저택 관리자 명령]\n", "blue", bold=True),
            T("/function aooni:admin/start", "yellow"), T(" 카운트다운 없이 바로 시작\n", "gray"),
            T("/function aooni:admin/stop", "yellow"), T(" 게임 중단 후 대기실로\n", "gray"),
            T("/function aooni:admin/rebuild", "yellow"), T(" 저택·대기실 다시 짓기\n", "gray"),
            T("/function aooni:admin/difficulty_1 | _2 | _3", "yellow"), T(" 난이도 쉬움/보통/어려움\n", "gray"),
            T("/function aooni:admin/oni_now", "yellow"), T(" (테스트) 아오오니 즉시 소환\n", "gray"),
            T("/function aooni:admin/final_now", "yellow"), T(" (테스트) 봉인 해제 + 검 지급 후 바로 결전", "gray")))


def fixtures():
    out = []
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
