"""아오오니 저택 서버팩 생성기.

이 스크립트 하나가 데이터팩 전체(저택 건축 명령 + 게임 로직)를 만든다.
좌표가 건축과 로직 양쪽에 쓰이므로 한곳에서 생성해 어긋남을 막는다.

  python tools/build_pack.py            # 데이터팩 생성 + 구조 점검 + 명령어 검사
  python tools/build_pack.py --no-validate

생성물: server/world/datapacks/aooni_mansion/
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import zipfile
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK = os.path.join(ROOT, "server", "world", "datapacks", "aooni_mansion")
NS = "aooni"
BUILD_VERSION = 7          # 바꾸면 기존 월드도 다음 로드 때 다시 짓는다
PACK_MIN, PACK_MAX = 71, 121   # 1.21.5 ~ 26.3

# ------------------------------------------------------------------ 좌표 상수
FB, F1, F2, F3 = -60, -55, -50, -45   # 지하·1층·2층·3층 발 높이 (층 사이 5칸, 바닥 블록은 각각 한 칸 아래)
FLOORS = (FB, F1, F2, F3)
ROOF_Y = F3 + 4              # 3층 천장 = 지붕
GROUND = F1 - 1              # 저택 둘레 땅(풀) 높이 — 지하층은 땅속
X0, X1, Z0, Z1 = 0, 55, 0, 43
LF, LY = -60, -61            # 대기실 발 높이 / 바닥

LOBBY = (-21, LF, 14)      # 대기실 스폰
SPAWN_POINTS = [(26, 41), (27, 41), (28, 41), (26, 42), (27, 42), (28, 42)]   # 1층 현관홀
JAIL = (6.5, FB, 5.5)        # 지하 감옥 칸
RELEASE = (6.5, FB, 15.5)    # 감옥 앞방
JAIL_BOX = f"x=1,y={FB - 1},z=1,dx=11,dy=4,dz=8"
MANSION_BOX = f"x={X0},y={FB - 1},z={Z0},dx={X1 - X0},dy={ROOF_Y - FB + 1},dz={Z1 - Z0}"
SPEC_POS = (27, F3 + 12, 21)

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
SPOT_REQ = []   # 조사 상자 자리 요청 (id, x, y, z, face, facing) — 저택을 다 지은 뒤 place_chests() 가 놓는다
SPOTS = []      # 놓인 조사 상자 (id, x, y, z)


def button(aid, x, y, z, face, facing, kind="stone_button", scope="game"):
    if aid.startswith("s_"):   # 조사 지점은 버튼이 아니라 상자
        SPOT_REQ.append((aid, x, y, z, face, facing))
        return
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
# 지하 1층 + 지상 3층. 층마다 십자 복도(동서 z20..22, 남북 x26..28)와 방 8개.
# 계단은 두 갈래(남북 복도 · 동서 복도)가 층마다 번갈아 놓여 있어 쫓고 쫓기는 순환로가 생긴다.
ROOMS = {}        # 이름 -> (층 발높이, x1, z1, x2, z2)
ROOM_PROBES = {}  # 이름 -> 반드시 갈 수 있어야 하는 칸 (구조 점검용)
QUADS = {"NWa": (1, 1, 12, 18), "NWb": (14, 1, 24, 18), "NEa": (30, 1, 41, 18), "NEb": (43, 1, 54, 18),
         "SWa": (1, 24, 12, 42), "SWb": (14, 24, 24, 42), "SEa": (30, 24, 41, 42), "SEb": (43, 24, 54, 42)}


def lamp(x, z, F, soul=False):
    setb(x, F + 3, z, ("soul_lantern" if soul else "lantern") + "[hanging=true]")


def chest(x, z, F, facing="south"):
    SPOT_REQ.append((f"s_{len(SPOT_REQ) + 1}", x, F, z, "floor", facing))


def table(x1, z1, x2, z2, F, wood="dark_oak"):
    fill(x1, F, z1, x2, F, z2, f"{wood}_slab[type=top]")


def shelf(x1, z1, x2, z2, F, h=2, block="bookshelf"):
    fill(x1, F, z1, x2, F + h - 1, z2, block)


def bed(x, z, F, color, dz=1, dx=0):
    """진짜 침대를 쓰면 잠들어 부활 지점이 바뀌므로 양털 두 칸으로 흉내만 낸다."""
    setb(x, F, z, "white_wool")
    setb(x + dx, F, z + dz, f"{color}_wool")


def cobwebs(x1, z1, x2, z2, F):
    for (x, z) in [(x1, z1), (x2, z1), (x1, z2), (x2, z2)]:
        setb(x, F + 3, z, "cobweb")


def room(name, F, quad, floor_block, probe_off=(2, 2)):
    x1, z1, x2, z2 = QUADS[quad]
    ROOMS[name] = (F, x1, z1, x2, z2)
    fill(x1, F - 1, z1, x2, F - 1, z2, floor_block)
    ROOM_PROBES[name] = (x1 + probe_off[0], F, z1 + probe_off[1])
    return x1, z1, x2, z2


def opening(x1, z1, x2, z2, F, h=3):
    fill(x1, F, z1, x2, F + h - 1, z2, "air")


def stair_run(lanes, axis, start, sd, F, wood="dark_oak"):
    """F층에서 바로 위층으로 오르는 2칸 폭 계단(5단). 계단 위로는 3칸을 비워 거대 아오오니도 지나간다."""
    facing = {("z", -1): "north", ("z", 1): "south", ("x", -1): "west", ("x", 1): "east"}[(axis, sd)]
    for k in range(5):
        p = start + sd * k
        for ln in lanes:
            x, z = (ln, p) if axis == "z" else (p, ln)
            if k:
                fill(x, F, z, x, F + k - 1, z, f"{wood}_planks")
            setb(x, F + k, z, f"{wood}_stairs[facing={facing}]")
            # 거대 아오오니(키 2.3)가 한 칸 올라설 때 머리 위가 비어 있어야 한다 → 위층 바닥을 4칸 뚫는다
            fill(x, F + k + 1, z, x, F + k + (4 if k < 4 else 3), z, "air")


def build_mansion():
    target(BUILD)
    # 0) 부지 정리. 저택 둘레 땅을 1층 높이까지 돋워 지하층이 땅속에 묻히게 한다
    fill(-5, FB - 1, -5, 60, ROOF_Y + 12, 60, "air")
    fill(-5, FB - 1, -5, 60, GROUND - 1, 60, "dirt")
    fill(-5, GROUND, -5, 60, GROUND, 60, "grass_block")

    # 1) 외벽 · 층 바닥 · 지붕
    levels = [(FB, "polished_andesite", "stone_bricks"), (F1, "dark_oak_planks", "dark_oak_planks"),
              (F2, "spruce_planks", "dark_oak_planks"), (F3, "spruce_planks", "dark_oak_planks")]
    for F, flo, outer in levels:
        fill(X0, F - 1, Z0, X1, F - 1, Z1, flo)
        for (a, b, c, d) in [(X0, Z0, X1, Z0), (X0, Z1, X1, Z1), (X0, Z0, X0, Z1), (X1, Z0, X1, Z1)]:
            fill(a, F - 1, b, c, F + 3, d, outer)
        fill(X0 + 1, F, Z0 + 1, X1 - 1, F + 3, Z1 - 1, "air")
    fill(X0, FB - 1, Z0, X1, FB - 1, Z1, "cobblestone")
    fill(X0, ROOF_Y, Z0, X1, ROOF_Y, Z1, "deepslate_tiles")
    for (a, b, c, d) in [(X0 - 1, Z0 - 1, X1 + 1, Z0 - 1), (X0 - 1, Z1 + 1, X1 + 1, Z1 + 1),
                         (X0 - 1, Z0 - 1, X0 - 1, Z1 + 1), (X1 + 1, Z0 - 1, X1 + 1, Z1 + 1)]:
        fill(a, ROOF_Y, b, c, ROOF_Y, d, "deepslate_tile_slab[type=top]")
    for (a, b, c, d) in [(X0, Z0, X1, Z0), (X0, Z1, X1, Z1), (X0, Z0, X0, Z1), (X1, Z0, X1, Z1)]:
        fill(a, ROOF_Y + 1, b, c, ROOF_Y + 1, d, "deepslate_brick_wall")
    # 지상층 외벽 기둥과 층 경계 띠
    for x in range(0, X1 + 1, 11):
        for z in (Z0, Z1):
            fill(x, F1 - 1, z, x, ROOF_Y - 1, z, "dark_oak_log")
    for z in range(0, Z1 + 1, 11):
        for x in (X0, X1):
            fill(x, F1 - 1, z, x, ROOF_Y - 1, z, "dark_oak_log")
    for F in (F1, F2, F3):
        for (a, b, c, d) in [(X0, Z0, X1, Z0), (X0, Z1, X1, Z1), (X0, Z0, X0, Z1), (X1, Z0, X1, Z1)]:
            fill(a, F - 1, b, c, F - 1, d, "stripped_dark_oak_wood")
    # 시계탑 (지붕 위 장식)
    fill(25, ROOF_Y + 1, 19, 29, ROOF_Y + 7, 23, "dark_oak_planks")
    fill(26, ROOF_Y + 1, 20, 28, ROOF_Y + 6, 22, "air")
    fill(25, ROOF_Y + 8, 19, 29, ROOF_Y + 8, 23, "deepslate_tiles")
    setb(27, ROOF_Y + 5, 19, "black_concrete")

    # 2) 칸막이(층마다 같은 뼈대)
    walls = {FB: "stone_bricks", F1: "stripped_spruce_wood", F2: "stripped_birch_wood", F3: "spruce_planks"}
    for F, wb in walls.items():
        top = F + 3
        fill(1, F, 19, 54, top, 19, wb)
        fill(1, F, 23, 54, top, 23, wb)
        opening(26, 19, 28, 19, F, 4)
        opening(26, 23, 28, 23, F, 4)
        for x in (13, 25, 29, 42):
            fill(x, F, 1, x, top, 18, wb)
            fill(x, F, 24, x, top, 42, wb)
        # 방 입구 (2칸 폭, 3칸 높이)
        opening(11, 19, 12, 19, F)      # NWa
        opening(16, 19, 17, 19, F)      # NWb
        opening(25, 13, 25, 14, F)      # NWb ↔ 남북 복도
        opening(29, 12, 29, 13, F)      # NEa ↔ 남북 복도
        opening(38, 19, 39, 19, F)      # NEa
        opening(43, 19, 44, 19, F)      # NEb
        opening(5, 23, 6, 23, F)        # SWa
        opening(20, 23, 21, 23, F)      # SWb
        opening(25, 28, 25, 29, F)      # SWb ↔ 남북 복도
        opening(29, 28, 29, 29, F)      # SEa ↔ 남북 복도
        opening(33, 23, 34, 23, F)      # SEa
        opening(48, 23, 49, 23, F)      # SEb
        # 방끼리 이어지는 샛문(순환로)
        if F != FB:
            opening(13, 4, 13, 5, F)    # NWa ↔ NWb
        opening(42, 15, 42, 16, F)      # NEa ↔ NEb
        opening(13, 37, 13, 38, F)      # SWa ↔ SWb
        opening(42, 38, 42, 39, F)      # SEa ↔ SEb
        # 복도 조명
        for x in (4, 16, 40, 52):
            lamp(x, 22, F, soul=True)
        for z in (12, 31):
            lamp(28, z, F, soul=True)

    # 3) 계단: 남북 복도(x26..27) 북쪽/남쪽, 동서 복도(z20..21) 서쪽/동쪽 — 층마다 번갈아
    stair_run((26, 27), "z", 8, -1, FB)            # 지하 → 1층 (북)
    stair_run((20, 21), "x", 46, 1, FB)            # 지하 → 1층 (동)
    stair_run((26, 27), "z", 34, 1, F1, "spruce")  # 1층 → 2층 (현관홀의 큰 계단)
    stair_run((20, 21), "x", 9, -1, F1)            # 1층 → 2층 (서)
    stair_run((26, 27), "z", 8, -1, F2)            # 2층 → 3층 (북)
    stair_run((20, 21), "x", 46, 1, F2)            # 2층 → 3층 (동)

    # 4) 창문 (지상층 외벽)
    for F in (F1, F2, F3):
        for x in (4, 8, 17, 21, 33, 37, 46, 50):
            for z in (Z0, Z1):
                fill(x, F + 1, z, x + 1, F + 2, z, "glass_pane")
        for z in (6, 14, 30, 37):
            for x in (X0, X1):
                fill(x, F + 1, z, x, F + 2, z + 1, "glass_pane")

    # ================= 지하
    F = FB
    # 감옥 (NWa): 칸 z1..9, 쇠창살 z10, 앞방 z11..18
    room("감옥 앞", F, "NWa", "cobblestone", (5, 14))
    for (x, z) in [(2, 3), (9, 6), (4, 8), (11, 2), (7, 14), (3, 16)]:
        setb(x, F - 1, z, "mossy_cobblestone")
    fill(1, F, 10, 12, F + 3, 10, "iron_bars")
    setb(3, F, 10, "stone_bricks")
    setb(3, F + 1, 10, "stone_bricks")
    door(6, F, 10, "north", "left")
    button("rescue", 3, F + 1, 11, "wall", "south", "stone_button")
    text(3.5, F + 1.9, 11.35, T("감옥 문 열기", "yellow"), "aooni.fx", scale=0.55)
    lamp(6, 5, F, soul=True)
    lamp(6, 15, F)
    cobwebs(1, 1, 12, 9, F)
    chest(11, 17, F)
    closet(1, F, 13, "E")
    # 보일러실 (NWb)
    room("보일러실", F, "NWb", "polished_andesite", (5, 8))
    fill(15, F, 2, 17, F + 2, 4, "iron_block")
    fill(20, F, 2, 22, F + 2, 4, "iron_block")
    for x in (16, 21):
        fill(x, F + 3, 3, x, F + 3, 3, "lightning_rod")
    fill(15, F, 8, 15, F + 3, 8, "copper_block")
    fill(23, F, 10, 24, F + 1, 11, "cut_copper")
    lamp(19, 9, F, soul=True)
    chest(14, 16, F)
    chest(24, 6, F)
    closet(14, F, 12, "E")
    # 와인 저장고 (NEa)
    room("와인 저장고", F, "NEa", "spruce_planks", (2, 4))
    for z in (3, 7, 11):
        fill(31, F, z, 39, F + 1, z, "stripped_spruce_log[axis=x]")
    lamp(35, 5, F)
    lamp(35, 15, F, soul=True)
    chest(41, 9, F)
    chest(30, 17, F)
    closet(41, F, 1, "S")
    # 실험실 (NEb)
    room("실험실", F, "NEb", "white_concrete", (2, 4))
    fill(45, F, 3, 52, F, 3, "smooth_quartz")
    fill(45, F, 8, 52, F, 8, "smooth_quartz")
    for x in (46, 49, 52):
        setb(x, F + 1, 3, "cauldron")
    fill(44, F, 12, 46, F + 2, 14, "iron_bars")
    fill(45, F, 13, 45, F + 1, 13, "air")
    setb(45, F, 13, "skeleton_skull[rotation=8]")
    fill(51, F, 13, 53, F, 15, "blue_concrete")
    lamp(48, 6, F, soul=True)
    lamp(50, 15, F)
    chest(48, 9, F + 1)
    chest(54, 17, F)
    closet(54, F, 5, "W")
    # 지하 창고 (SWa)
    room("지하 창고", F, "SWa", "cobblestone", (5, 5))
    for (x, z) in [(2, 26), (3, 26), (2, 27), (9, 30), (10, 30), (2, 35), (8, 40), (9, 40), (9, 39)]:
        setb(x, F, z, "spruce_planks")
    fill(4, F, 33, 5, F + 1, 33, "hay_block")
    cobwebs(1, 24, 12, 42, F)
    lamp(6, 32, F, soul=True)
    chest(3, 27, F)
    chest(12, 41, F)
    closet(1, F, 39, "E")
    # 물탱크실 (SWb)
    room("물탱크실", F, "SWb", "stone_bricks", (2, 2))
    fill(16, F - 1, 30, 22, F, 36, "stone_bricks")
    fill(17, F, 31, 21, F, 35, "water")
    fill(17, F - 1, 31, 21, F - 1, 35, "stone_bricks")
    lamp(19, 27, F, soul=True)
    lamp(19, 39, F)
    chest(14, 41, F)
    chest(24, 25, F)
    closet(24, F, 42, "N")
    # 지하 서고 (SEa)
    room("지하 서고", F, "SEa", "spruce_planks", (1, 2))
    for z in (27, 31, 35, 39):
        fill(32, F, z, 39, F + 2, z, "bookshelf")
        opening(35, z, 35, z, F)
    lamp(35, 25, F)
    lamp(35, 33, F, soul=True)
    chest(41, 29, F)
    chest(31, 41, F)
    closet(41, F, 42, "N")
    # 관이 있는 방 (SEb)
    room("관이 있는 방", F, "SEb", "polished_blackstone_bricks")
    for z in (28, 33, 38):
        fill(46, F, z, 47, F, z + 2, "dark_oak_planks")
        fill(51, F, z, 52, F, z + 2, "dark_oak_planks")
        setb(49, F, z + 1, "candle[candles=3,lit=true]")
    cobwebs(43, 24, 54, 42, F)
    lamp(49, 31, F, soul=True)
    chest(54, 25, F)
    chest(44, 41, F)
    closet(54, F, 41, "W")

    # ================= 1층
    F = F1
    # 서재 (NWa)
    room("서재", F, "NWa", "spruce_planks")
    shelf(1, 1, 1, 18, F, 3)
    shelf(2, 1, 12, 1, F, 3)
    for z in (6, 10):
        shelf(4, z, 9, z, F, 2)
    table(10, 14, 11, 15, F)
    setb(10, F, 16, "dark_oak_stairs[facing=north]")
    setb(11, F + 1, 14, "candle[candles=3,lit=true]")
    lamp(7, 8, F)
    lamp(7, 15, F, soul=True)
    chest(10, 15, F + 1)
    chest(2, 17, F)
    closet(12, F, 2, "S")
    # 식당 (NWb)
    room("식당", F, "NWb", "dark_oak_planks")
    fill(17, F, 4, 21, F, 14, "red_carpet")
    table(19, 5, 19, 13, F)
    for z in range(6, 13, 2):
        setb(18, F, z, "spruce_stairs[facing=east]")
        setb(20, F, z, "spruce_stairs[facing=west]")
    setb(19, F + 1, 7, "candle[candles=3,lit=true]")
    setb(19, F + 1, 11, "candle[candles=2,lit=true]")
    lamp(19, 6, F)
    lamp(19, 12, F)
    chest(19, 9, F + 1)
    chest(24, 2, F)
    closet(14, F, 16, "E")
    # 피아노실 (NEa)
    room("피아노실", F, "NEa", "stripped_dark_oak_wood")
    fill(33, F, 1, 37, F + 1, 1, "black_concrete")
    setb(32, F, 2, "black_concrete")
    setb(38, F, 2, "black_concrete")
    fill(33, F, 2, 37, F, 2, "white_concrete")
    notes = ["도", "레", "미", "파", "솔"]
    for i, x in enumerate(range(33, 38)):
        button(f"piano{i + 1}", x, F + 1, 2, "floor", "north", "polished_blackstone_button")
        text(x + 0.5, F + 1.45, 2.5, T(notes[i], "white"), "aooni.fx", scale=0.6)
    setb(35, F, 4, "dark_oak_stairs[facing=north]")
    for (x, z) in [(31, 9), (31, 11), (40, 9), (40, 11)]:
        setb(x, F, z, "spruce_stairs[facing=south]")
    lamp(35, 6, F)
    lamp(35, 14, F, soul=True)
    chest(41, 17, F)
    chest(30, 1, F)
    closet(41, F, 3, "W")
    # 주방 (NEb)
    room("주방", F, "NEb", "smooth_stone")
    fill(54, F, 2, 54, F, 12, "polished_andesite")
    fill(44, F, 1, 53, F, 1, "polished_andesite")
    setb(54, F, 6, "water_cauldron[level=3]")
    fill(53, F, 14, 54, F + 1, 14, "iron_block")
    table(47, 8, 49, 10, F, "spruce")
    setb(46, F, 9, "spruce_stairs[facing=east]")
    setb(50, F, 9, "spruce_stairs[facing=west]")
    lamp(48, 5, F)
    lamp(48, 14, F)
    chest(54, 3, F + 1)
    chest(48, 9, F + 1)
    closet(43, F, 1, "S")
    # 화장실·세탁실 (SWa)
    room("화장실", F, "SWa", "polished_diorite")
    fill(1, F, 39, 4, F, 42, "smooth_quartz")
    fill(2, F, 40, 3, F, 41, "water_cauldron[level=3]")
    fill(12, F, 26, 12, F, 30, "smooth_quartz")
    fill(12, F + 2, 26, 12, F + 3, 30, "light_gray_stained_glass")
    for z in (32, 35):
        fill(8, F, z, 12, F + 2, z, "white_concrete")
    lamp(6, 28, F)
    lamp(6, 38, F, soul=True)
    chest(12, 28, F + 1)
    chest(1, 25, F)
    closet(1, F, 33, "E")
    # 거실 (SWb)
    room("거실", F, "SWb", "spruce_planks")
    fill(16, F, 29, 22, F, 36, "red_carpet")
    fill(14, F, 30, 14, F + 3, 34, "bricks")
    fill(14, F, 31, 14, F + 1, 33, "air")
    setb(14, F, 32, "lantern")
    for z in (30, 31, 32, 33, 34):
        setb(19, F, z, "dark_oak_stairs[facing=west]")
    table(17, 31, 17, 33, F, "spruce")
    fill(23, F, 41, 24, F + 1, 42, "dark_oak_planks")
    setb(24, F + 2, 42, "flower_pot")
    fill(24, F, 25, 24, F + 2, 25, "dark_oak_log")
    lamp(19, 28, F)
    lamp(19, 38, F)
    chest(23, 41, F + 2)
    chest(15, 26, F)
    closet(14, F, 41, "E")
    # 현관홀 (남북 복도 남쪽) — 생존자 시작 지점. 큰 계단이 2층으로 이어진다
    ROOM_PROBES["현관홀"] = (28, F, 40)
    fill(26, F, 39, 28, F, 42, "red_carpet")
    door(27, F, 43, "north", "left")
    door(28, F, 43, "north", "right")
    button("d_front", 25, F + 1, 42, "wall", "north")
    lamp(27, 41, F)
    # 응접실 (SEa)
    room("응접실", F, "SEa", "dark_oak_planks")
    fill(33, F, 31, 38, F, 36, "brown_carpet")
    for x in (34, 35, 36, 37):
        setb(x, F, 30, "dark_oak_stairs[facing=south]")
        setb(x, F, 37, "dark_oak_stairs[facing=north]")
    table(35, 33, 36, 34, F)
    fill(41, F, 25, 41, F + 2, 25, "dark_oak_log")
    setb(30, F, 41, "potted_wither_rose")
    lamp(35, 28, F)
    lamp(35, 39, F)
    chest(36, 33, F + 1)
    chest(41, 42, F)
    closet(31, F, 42, "N")
    # 손님방 (SEb)
    room("손님방", F, "SEb", "spruce_planks", (4, 6))
    bed(45, 40, F, "blue", dz=-1)
    bed(51, 40, F, "blue", dz=-1)
    fill(54, F, 30, 54, F + 2, 32, "spruce_planks")
    table(44, 26, 45, 26, F, "spruce")
    lamp(48, 33, F)
    chest(54, 33, F)
    chest(44, 27, F)
    closet(48, F, 42, "N")

    # ================= 2층
    F = F2
    # 안방 (NWa)
    room("안방", F, "NWa", "dark_oak_planks")
    fill(4, F, 2, 6, F, 4, "red_wool")
    fill(4, F, 2, 6, F, 2, "white_wool")
    fill(1, F, 8, 1, F + 2, 12, "spruce_planks")
    table(10, 2, 11, 2, F, "spruce")
    setb(10, F + 1, 2, "flower_pot")
    fill(3, F, 14, 8, F, 17, "purple_carpet")
    lamp(6, 9, F)
    chest(11, 2, F + 1)
    chest(1, 15, F)
    closet(12, F, 12, "W")
    # 드레스룸 (NWb)
    room("드레스룸", F, "NWb", "birch_planks")
    for z in (3, 7, 11, 15):
        for x in range(15, 23, 2):
            setb(x, F, z, "dark_oak_fence")
            setb(x, F + 1, z, ["red_wool", "black_wool", "white_wool", "purple_wool"][(x + z) % 4])
    lamp(19, 9, F)
    chest(24, 1, F)
    chest(14, 9, F)
    closet(24, F, 17, "W")
    # 아이방 (NEa)
    room("아이방", F, "NEa", "birch_planks")
    fill(33, F, 8, 38, F, 13, "light_blue_carpet")
    bed(31, 2, F, "pink", dz=1)
    bed(40, 2, F, "pink", dz=1)
    for (x, z, c) in [(34, 9, "red"), (36, 11, "yellow"), (35, 12, "lime")]:
        setb(x, F, z, f"{c}_concrete")
    fill(41, F, 6, 41, F + 1, 8, "white_concrete")
    lamp(35, 6, F)
    lamp(35, 15, F)
    chest(41, 9, F)
    chest(30, 17, F)
    closet(30, F, 6, "E")
    # 창고 (NEb) — 마검 금고
    room("창고", F, "NEb", "spruce_planks", (3, 5))
    safe_panel(4, "z", 0, F, 46, 1, "마검 금고 · 비밀번호 4자리")   # 북쪽 벽, 남쪽을 바라봄
    for (x, z) in [(53, 9), (54, 9), (53, 10), (44, 12), (44, 13), (52, 16)]:
        setb(x, F, z, "spruce_planks")
    setb(54, F, 4, "hay_block")
    cobwebs(43, 1, 54, 18, F)
    lamp(48, 6, F)
    lamp(48, 14, F, soul=True)
    chest(54, 12, F)
    chest(43, 17, F)
    closet(54, F, 17, "W")
    # 손님방2 (SWa)
    room("손님방2", F, "SWa", "spruce_planks")
    bed(3, 40, F, "green", dz=-1)
    bed(9, 40, F, "green", dz=-1)
    table(1, 26, 2, 26, F, "spruce")
    lamp(6, 32, F)
    chest(1, 27, F)
    chest(12, 41, F)
    closet(12, F, 25, "W")
    # 작업실 (SWb)
    room("작업실", F, "SWb", "spruce_planks", (4, 4))
    shelf(24, 30, 24, 35, F, 3)
    table(16, 40, 18, 41, F)
    setb(17, F, 39, "dark_oak_stairs[facing=south]")
    setb(15, F, 26, "crafting_table")
    setb(16, F, 26, "anvil[facing=east]")
    lamp(19, 33, F)
    chest(18, 41, F + 1)
    chest(14, 30, F)
    closet(23, F, 42, "N")
    # 욕실 (SEa)
    room("욕실", F, "SEa", "smooth_quartz")
    fill(37, F, 38, 41, F, 42, "smooth_quartz")
    fill(38, F, 39, 40, F, 41, "water_cauldron[level=3]")
    fill(30, F + 2, 30, 30, F + 3, 33, "light_gray_stained_glass")
    lamp(35, 32, F)
    chest(30, 25, F)
    chest(41, 26, F)
    closet(31, F, 42, "N")
    # 도서관 (SEb)
    room("도서관", F, "SEb", "dark_oak_planks", (1, 1))
    for x in (46, 49, 52):
        shelf(x, 26, x, 39, F, 3)
        opening(x, 32, x, 32, F)
    shelf(54, 25, 54, 42, F, 3)
    lamp(47, 30, F)
    lamp(50, 36, F, soul=True)
    chest(44, 41, F)
    chest(53, 25, F)
    closet(43, F, 33, "E")

    # ================= 3층
    F = F3
    # 다락방 (NWa)
    room("다락방", F, "NWa", "spruce_planks", (5, 5))
    for (x, z) in [(2, 2), (3, 2), (2, 3), (10, 5), (10, 6), (5, 14), (6, 14), (5, 15)]:
        setb(x, F, z, "spruce_planks")
    fill(8, F, 10, 9, F + 1, 11, "hay_block")
    cobwebs(1, 1, 12, 18, F)
    lamp(6, 9, F, soul=True)
    chest(3, 3, F)
    chest(12, 15, F)
    closet(1, F, 17, "E")
    # 하인 방 (NWb)
    room("하인 방", F, "NWb", "spruce_planks")
    for x in (15, 18, 21):
        bed(x, 2, F, "brown", dz=1)
    table(23, 10, 24, 10, F, "spruce")
    lamp(19, 9, F)
    chest(24, 11, F)
    chest(14, 17, F)
    closet(24, F, 2, "W")
    # 기도실 (NEa)
    room("기도실", F, "NEa", "polished_andesite")
    for z in (8, 11, 14):
        for x in (31, 32, 33, 37, 38, 39):
            setb(x, F, z, "spruce_stairs[facing=south]")
    fill(34, F, 2, 36, F, 3, "smooth_quartz")
    for x in (34, 36):
        setb(x, F + 1, 2, "candle[candles=4,lit=true]")
    lamp(35, 6, F)
    lamp(35, 15, F, soul=True)
    chest(35, 2, F + 1)
    chest(41, 17, F)
    closet(30, F, 1, "S")
    # 기계실 (NEb) — 시계탑 아래
    room("기계실", F, "NEb", "stone_bricks")
    for (x, z) in [(46, 4), (51, 4), (46, 13), (51, 13)]:
        fill(x, F, z, x, F + 3, z, "lightning_rod")
    fill(48, F, 7, 49, F + 1, 10, "cut_copper")
    lamp(48, 15, F, soul=True)
    chest(54, 9, F)
    chest(43, 2, F)
    closet(54, F, 17, "W")
    # 인형의 방 (SWa)
    room("인형의 방", F, "SWa", "pink_wool")
    for (x, z) in [(2, 26), (5, 26), (8, 26), (11, 26), (2, 40), (11, 40)]:
        setb(x, F, z, "white_wool")
        setb(x, F + 1, z, "skeleton_skull[rotation=0]")
    lamp(6, 33, F)
    chest(1, 33, F)
    chest(12, 37, F)
    closet(6, F, 42, "N")
    # 빈 방 (SWb)
    room("빈 방", F, "SWb", "spruce_planks")
    setb(19, F, 33, "spruce_stairs[facing=north]")
    cobwebs(14, 24, 24, 42, F)
    lamp(19, 30, F, soul=True)
    chest(24, 41, F)
    chest(14, 25, F)
    closet(14, F, 33, "E")
    # 봉인된 방 (SEa)
    room("봉인된 방", F, "SEa", "deepslate_tiles")
    fill(33, F, 30, 38, F + 3, 30, "iron_bars")
    fill(33, F, 36, 38, F + 3, 36, "iron_bars")
    fill(33, F, 31, 33, F + 3, 35, "iron_bars")
    fill(38, F, 31, 38, F + 3, 35, "iron_bars")
    opening(35, 30, 36, 30, F)
    setb(36, F, 33, "skeleton_skull[rotation=4]")
    lamp(35, 27, F, soul=True)
    chest(35, 33, F)
    chest(41, 41, F)
    closet(30, F, 41, "E")
    # 아오오니의 방 (SEb) — 아오오니 시작 지점
    room("아오오니의 방", F, "SEb", "blue_terracotta")
    for (x, z) in [(45, 26), (52, 29), (47, 38), (53, 40), (44, 33)]:
        setb(x, F - 1, z, "blue_concrete")
    for (x, z) in [(45, 40), (52, 26)]:
        setb(x, F, z, "bone_block")
    cobwebs(43, 24, 54, 42, F)
    lamp(48, 33, F, soul=True)
    chest(54, 37, F)
    chest(43, 25, F)
    closet(54, F, 25, "W")

    # 5) 정원 (승리하면 현관문이 열린다)
    G = F1
    fill(27, G - 1, 44, 28, G - 1, 53, "dirt_path")
    for x in (20, 35):
        fill(x, G, 44, x, G + 2, 54, "oak_leaves[persistent=true]")
    fill(20, G, 54, 35, G + 2, 54, "oak_leaves[persistent=true]")
    fill(27, G, 54, 28, G + 2, 54, "iron_bars")
    for x in (24, 31):
        fill(x, G, 48, x, G + 1, 48, "dark_oak_fence")
        setb(x, G + 2, 48, "lantern")
    text(27.95, G + 3.3, 53.5, T("아침이다…", "gold", bold=True), "aooni.fx", scale=1.0)
    place_chests()


FACE_DIRS = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}


def place_chests():
    """조사 상자를 놓는다. 벽에 붙어 있던 자리는 바닥까지 내리고, 앞면은 트인 쪽으로 돌린다."""
    for (aid, x, y, z, face, facing) in SPOT_REQ:
        while y > FB and passable(WORLD.get((x, y - 1, z)), False):
            y -= 1
        if face != "wall":
            facing = max(FACE_DIRS, key=lambda d: sum(passable(WORLD.get((x + FACE_DIRS[d][0] * k, y, z + FACE_DIRS[d][1] * k)), False)
                                                       for k in (1, 2, 3)))
        above = WORLD.get((x, y + 1, z))
        # 위가 꽉 찬 블록이면 상자 뚜껑이 안 열린다
        assert passable(above, False) or any(t in bid(above) for t in ("glass", "slab", "stairs", "lantern")), (aid, above)
        setb(x, y, z, f"chest[facing={facing},type=single,waterlogged=false]")
        SPOTS.append((aid, x, y, z))


def build_lobby():
    target(LOBBY_BUILD)
    fill(-30, LF, 2, -12, -48, 22, "air")
    fill(-30, LY, 2, -12, LY, 22, "grass_block")
    fill(-28, LY, 4, -14, LY, 20, "spruce_planks")
    fill(-28, LF, 4, -14, LF + 4, 4, "stripped_spruce_wood")
    fill(-28, LF, 20, -14, LF + 4, 20, "stripped_spruce_wood")
    fill(-28, LF, 4, -28, LF + 4, 20, "stripped_spruce_wood")
    fill(-14, LF, 4, -14, LF + 4, 20, "stripped_spruce_wood")
    fill(-28, LF + 5, 4, -14, LF + 5, 20, "spruce_planks")
    fill(-24, LF, 9, -18, LF, 17, "gray_carpet")
    for (x, z) in [(-25, 8), (-17, 8), (-25, 16), (-17, 16)]:
        setb(x, LF + 4, z, "lantern[hanging=true]")
    for x in range(-26, -15, 2):
        setb(x, LF, 19, "spruce_stairs[facing=south]")
    setb(-23, LF + 1, 4, "lime_concrete")
    setb(-21, LF + 1, 4, "yellow_concrete")
    setb(-19, LF + 1, 4, "light_blue_concrete")
    setb(-25, LF + 1, 4, "red_concrete")
    setb(-27, LF + 1, 4, "purple_concrete")
    setb(-17, LF + 1, 4, "cyan_concrete")
    button("l_solo_oni", -27, LF + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_solo", -17, LF + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-26.5, LF + 1.75, 5.3, T("혼자 연습\n(아오오니)", "light_purple"), "aooni.fx", scale=0.45)
    text(-16.5, LF + 1.75, 5.3, T("혼자 연습\n(생존자)", "aqua"), "aooni.fx", scale=0.45)
    button("l_want", -25, LF + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-24.5, LF + 1.75, 5.3, T("아오오니 지원", "red"), "aooni.fx", scale=0.5)
    text(-24.5, LF + 0.55, 5.3, T("지원자 0명", "red"), "aooni.fx", "aooni.t_want", scale=0.45)
    button("l_start", -23, LF + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_diff", -21, LF + 1, 5, "wall", "south", "stone_button", scope="lobby")
    button("l_rules", -19, LF + 1, 5, "wall", "south", "stone_button", scope="lobby")
    text(-22.5, LF + 1.75, 5.3, T("▶ 게임 시작", "green"), "aooni.fx", scale=0.5)
    text(-20.5, LF + 1.75, 5.3, T("난이도 변경", "yellow"), "aooni.fx", scale=0.5)
    text(-18.5, LF + 1.75, 5.3, T("규칙 보기", "aqua"), "aooni.fx", scale=0.5)
    text(-20.5, LF + 3.3, 5.5, T("아오오니 저택", "blue", bold=True), "aooni.fx", scale=1.6)
    text(-20.5, LF + 2.85, 5.5, T("4~6인 · 아오오니 1명 vs 생존자 · 비밀번호 4자리 → 마검 → 아오오니 족치기", "gray"), "aooni.fx", scale=0.6)
    text(-20.5, LF + 2.45, 5.5, T("난이도: 보통", "yellow"), "aooni.fx", "aooni.t_diff", scale=0.7)
    text(-20.5, LF + 2.15, 5.5, T("접속 인원: 0명", "white"), "aooni.fx", "aooni.t_count", scale=0.6)
    rules = ("한 명은 아오오니, 나머지는 생존자! (아오오니 지원 버튼)\n"
             "· 생존자: 저택 곳곳의 상자를 열어 비밀번호 쪽지 4장을 찾자\n"
             "· 2층 창고 금고에 비밀번호를 넣으면 마검! 마검으로만 아오오니를 벨 수 있다\n"
             "· 아오오니: 20초 뒤 깨어나 생존자를 때려 잡는다. 문·버튼·옷장은 못 만진다\n"
             "· 아오오니에게 여러 대 맞으면 쓰러져 지하 감옥에서 부활 → 동료가 감옥 앞 버튼으로 구출\n"
             "· 옷장(가문비 문)에 들어가 문을 닫으면 완전히 안전")
    text(-26.95, LF + 2.2, 12.5, T(rules, "white"), "aooni.fx", scale=0.55,
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
        if not (-40 < x < 64 and -70 < y < -30 and -10 < z < 64):
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
    start = (SPAWN_POINTS[0][0], F1, SPAWN_POINTS[0][1])
    closed = reachable(start, doors_open=False)
    opened = reachable(start, doors_open=True)
    giant = reachable((int(ONI_SPAWN[0]), ONI_SPAWN[1], int(ONI_SPAWN[2])), doors_open=False, h=3)
    for name, p in ROOM_PROBES.items():
        if p not in closed:
            problems.append(f"시작 시 {name} 에 갈 수 없음 {p}")
        if p not in giant:
            problems.append(f"거대 아오오니(키 3칸)가 {name} 에 갈 수 없음 {p}")
    jail = (int(JAIL[0]), JAIL[1], int(JAIL[2]))
    if jail in closed:
        problems.append("감옥 안이 바깥과 연결됨(문이 닫혀 있는데도)")
    if jail not in opened:
        problems.append("감옥 문을 열어도 감옥에 들어갈 수 없음")
    garden = (27, F1, 48)
    if garden in closed:
        problems.append("현관문이 닫혀 있는데 정원으로 나갈 수 있음")
    if garden not in opened:
        problems.append("현관문을 열어도 정원에 갈 수 없음")
    for p in opened:
        inside = X0 <= p[0] <= X1 and Z0 <= p[2] <= Z1
        in_garden = 21 <= p[0] <= 34 and 44 <= p[2] <= 53
        if not (inside or in_garden):
            problems.append(f"저택·정원 밖으로 나갈 수 있음 {p}")
            break
    for (aid, x, y, z) in SPOTS:
        near = [(x + dx, yy, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) for yy in (y - 2, y - 1, y, y + 1)]
        if not any(n in closed for n in near):
            problems.append(f"상자 {aid} 에 다가갈 수 없음 {(x, y, z)}")
    for (x, y, z, tags) in MARKERS:
        bx, bz = int(x - 0.5), int(z - 0.5)
        if not passable(WORLD.get((bx, y, bz)), True) or not passable(WORLD.get((bx, y + 1, bz)), True):
            problems.append(f"마커가 막힌 칸에 있음 {tags} {(bx, y, bz)}")
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
# 생존자 체력은 20. 아오오니 맨손 공격력 dmg → 쉬움 5대 · 보통 4대 · 어려움 3대 맞으면 쓰러진다(쓰러지면 감옥에서 부활)
DIFF = {1: dict(lives=4, speed=None, dmg=4), 2: dict(lives=3, speed=0, dmg=5), 3: dict(lives=2, speed=1, dmg=7)}
SPEED_TEXT = {None: "기본 속도", 0: "신속 I", 1: "신속 II"}
ONI_SPAWN = (48.5, F3, 33.5)        # 3층 아오오니의 방
ONI_FREEZE = 20                     # 시작 후 아오오니가 못 움직이는 시간(초)
ONI_HP_BASE, ONI_HP_PER = 60, 20    # 마검이 나온 뒤 아오오니 체력 = 60 + 생존자 수 × 20
FINAL_SCALE = 1.3                   # 마검이 나오면 아오오니가 커진다
WEAPON_ITEM, WEAPON_NAME = "netherite_sword", "마검"
WEAPON_STRENGTH = 4                 # 힘 V → 한 방 약 23
VAULT_DROP = (48.5, F2 + 1, 3.5)    # 아오오니가 마검을 주우면 금고 앞으로 돌아간다
CIRC = {1: "①", 2: "②", 3: "③", 4: "④"}
ORD = {1: "첫째", 2: "둘째", 3: "셋째", 4: "넷째"}
NOTE_PITCH = {1: 0.707107, 2: 0.793701, 3: 0.890899, 4: 0.943874, 5: 1.059463}


def item_named(item, name, color, lore, comps=""):
    return (f'minecraft:{item}[{comps}minecraft:custom_name={{text:"{name}",color:"{color}",italic:false}},'
            f'minecraft:lore=[{{text:"{lore}",color:"gray",italic:false}}]]')


def potion_comp(effects, color):
    eff = ",".join(f'{{id:"minecraft:{e}",amplifier:{a}b,duration:{max(1, d * 20)},show_particles:0b}}' for e, a, d in effects)
    return f"minecraft:potion_contents={{custom_color:{color},custom_effects:[{eff}]}},"


# 배가 불러도 먹을 수 있는 음식(먹으면 item/ate_* 에서 체력 회복)
FOOD = "minecraft:food={nutrition:4,saturation:4.0f,can_always_eat:true},"
# 상자에 넣는 특수 아이템 (키, 개수, 아이템). 한 상자에 특수 아이템은 하나뿐 → 상자가 모자라면 목록 뒤쪽부터 빠진다
SPECIALS = [
    ("bread", 3, item_named("bread", "빵", "white", "먹으면 체력 2칸 회복", FOOD)),
    ("steak", 2, item_named("cooked_beef", "스테이크", "white", "먹으면 체력 4칸 회복", FOOD)),
    ("heal", 2, item_named("potion", "회복 물약", "light_purple", "마시면 체력 4칸 즉시 회복",
                           potion_comp([("instant_health", 1, 0)], 16262179))),
    ("gapple", 1, item_named("golden_apple", "황금 사과", "gold", "먹으면 체력이 서서히 차오른다")),
    ("pearl", 2, item_named("ender_pearl", "엔더 진주", "dark_aqua", "던진 곳으로 순간이동 (체력 2.5칸 소모)")),
    ("slow", 2, item_named("splash_potion", "구속 물약 (던지기)", "light_purple", "아오오니에게 던지면 8초 동안 느려진다",
                           potion_comp([("slowness", 2, 8)], 5926017))),
    ("blind", 1, item_named("splash_potion", "실명 물약 (던지기)", "light_purple", "아오오니에게 던지면 7초 동안 앞이 안 보인다",
                            potion_comp([("blindness", 0, 7)], 2039587))),
    ("speed", 2, item_named("potion", "신속 물약", "light_purple", "마시면 20초 동안 빨라진다", potion_comp([("speed", 1, 20)], 8171462))),
    ("invis", 1, item_named("potion", "투명 물약", "light_purple", "마시면 25초 동안 투명해진다", potion_comp([("invisibility", 0, 25)], 8356754))),
    ("nightv", 1, item_named("potion", "야간 투시 물약", "light_purple", "마시면 2분 동안 어둠 속이 잘 보인다",
                             potion_comp([("night_vision", 0, 120)], 2039713))),
]
FAKE_ORD = [2, 3, 1]   # 가짜 쪽지에 적힌 자리 표시(진짜와 똑같이 생겼다)
# 잡동사니 (아이템, 이름, 설명). 상자마다 두 번 굴려 1..JUNK_ROLL 중 목록 안이면 넣는다
JUNK = [("rabbit_hide", "낡은 인형", "솜이 다 빠졌다"), ("bowl", "깨진 접시", "가장자리가 날카롭다"),
        ("iron_nugget", "녹슨 못", "손에 붉은 녹이 묻어난다"), ("glass_bottle", "빈 약병", "바닥에 파란 얼룩이 말라붙어 있다"),
        ("bone", "뼈", "…사람 뼈는 아니겠지"), ("book", "낡은 책", "페이지가 전부 찢겨 나갔다"), ("feather", "깃털", "어디서 날아왔을까"),
        ("clock", "멈춘 시계", "바늘이 새벽 3시에 멈춰 있다"), ("string", "실뭉치", "끝이 엉켜 있다"), ("candle", "다 탄 양초", "심지만 남았다")]
JUNK_ROLL = 16
ALL_FLAGS = (["#sec", "#sp", "#cd", "#found", "#wpn", "#final", "#rescue_cd", "#freeze", "#oni_gone", "#bh",
              "#bhp_prev", "#half10", "#hp", "#amb", "#stall", "#a0", "#swlost", "#wmsg", "#f1", "#f2", "#f3", "#f4",
              "#ap", "#atk", "#still", "#hbl"] + [f"#d{k}" for k in range(1, 5)])

# 아오오니 모델: 리소스팩(tools/build_rp.py)의 부위 6개를 item_display 로 띄워 관절마다 돌린다
with open(os.path.join(HERE, "rp_parts.json"), encoding="utf-8") as _f:
    RP_PARTS = json.load(_f)["parts"]
ONI_PART_NAMES = ["torso", "head", "arm_l", "arm_r", "leg_l", "leg_r"]
WALK_FRAMES = 8        # 걷기 한 주기 = 8동작
WALK_TICKS = 2         # 동작 하나에 2틱
LEG_DEG, ARM_DEG = 30, 35


def digit_paper(j, value=None):
    """value 가 없으면 상자에 넣는 '아직 안 읽은' 쪽지, 있으면 손에 넣은 뒤의 숫자 적힌 쪽지."""
    if value == "fake":
        lore, data = "접혀 있다. 집어서 펼쳐 보자", "{aooni_fake:1b}"
    elif value is None:
        lore, data = "접혀 있다. 집어서 펼쳐 보자", f"{{aooni_dig:{j}}}"
    else:
        lore, data = f"{ORD[j]} 자리 숫자: {value}", f"{{aooni_dig:{j},read:1b}}"
    return (f'minecraft:paper[minecraft:custom_name={{text:"비밀번호 쪽지 {CIRC[j]}",color:"gold",italic:false}},'
            f'minecraft:lore=[{{text:"{lore}",color:"white",italic:false}}],'
            f'minecraft:custom_data={data}]')


def _q(deg):
    """관절(엔티티 +X 축) 둘레 회전 쿼터니언. 음수 = 팔다리가 앞으로, 양수 = 고개를 숙임."""
    a = math.radians(deg) / 2
    return f"[{math.sin(a):.5f}f,0f,0f,{math.cos(a):.5f}f]"


def part_tf(part, deg, s):
    j = RP_PARTS[part]["joint"]
    return (f"{{translation:[{j[0] * s:.5f}f,{j[1] * s:.5f}f,{j[2] * s:.5f}f],left_rotation:{_q(deg)},"
            f"scale:[{s:g}f,{s:g}f,{s:g}f],right_rotation:[0f,0f,0f,1f]}}")


def part_merge(part, deg, s, dur):
    return (f"data merge entity @e[type=minecraft:item_display,tag=aooni.p_{part},limit=1] "
            f"{{start_interpolation:0,interpolation_duration:{dur},transformation:{part_tf(part, deg, s)}}}")


def oni_model_cmds(scale):
    """아오오니 플레이어를 매 틱 따라다니는 모델(플레이어 본체는 투명). 리소스팩이 있어야 보인다."""
    out = ["kill @e[tag=aooni.part]", "scoreboard players set #hbl aooni.var 99"]
    for part in ONI_PART_NAMES:
        model = RP_PARTS[part]["item_model"]
        out.append('summon minecraft:item_display ~ ~ ~ {Tags:["aooni.fx","aooni.part","aooni.p_%s"],'
                   'item:{id:"minecraft:paper",count:1,components:{"minecraft:item_model":"%s"}},item_display:"none",'
                   'teleport_duration:1,interpolation_duration:2,brightness:{sky:10,block:10},transformation:%s}'
                   % (part, model, part_tf(part, 0, scale)))
    return out


def walk_pose(i):
    s = math.sin(2 * math.pi * i / WALK_FRAMES)
    # 왼다리와 오른팔이 같이 앞으로(음수), 반대쪽은 뒤로
    return {"leg_l": -LEG_DEG * s, "leg_r": LEG_DEG * s, "arm_l": ARM_DEG * s, "arm_r": -ARM_DEG * s}


SWORD_NBT = ('{id:"minecraft:netherite_sword",count:1,components:{"minecraft:item_model":"aooni:magum",'
             '"minecraft:custom_name":{text:"마검",color:"gold",italic:false},"minecraft:enchantment_glint_override":true}}')
SURV = "@a[tag=aooni.player,tag=!aooni.oni_p]"
ONI = "@a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure]"


def logic():
    assert len(SPOTS) >= 7, len(SPOTS)

    # ---------------- load / tick
    fn("load",
       "scoreboard objectives add aooni.var dummy",
       f"scoreboard objectives add aooni.side dummy {comp(T('아오오니 저택', 'blue', bold=True))}",
       "scoreboard objectives add aooni.lives dummy",
       "scoreboard objectives add aooni.gid dummy",
       "scoreboard objectives add aooni.leave minecraft.custom:minecraft.leave_game",
       "scoreboard objectives add aooni.grace dummy",
       "scoreboard objectives add aooni.deaths deathCount",
       "# 회복 음식을 먹었는지(먹은 횟수 통계)",
       "scoreboard objectives add aooni.eb minecraft.used:minecraft.bread",
       "scoreboard objectives add aooni.es minecraft.used:minecraft.cooked_beef",
       "# 아오오니 걷기·공격 동작용 통계",
       "scoreboard objectives add aooni.mw minecraft.custom:minecraft.walk_one_cm",
       "scoreboard objectives add aooni.ms minecraft.custom:minecraft.sprint_one_cm",
       "scoreboard objectives add aooni.mc minecraft.custom:minecraft.crouch_one_cm",
       "scoreboard objectives add aooni.dd minecraft.custom:minecraft.damage_dealt",
       "scoreboard objectives add aooni.wc dummy",
       "# 연습 끝내기: OP 가 아니어도 /trigger aooni.quit",
       "scoreboard objectives add aooni.quit trigger",
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
       "team modify aooni_out friendlyFire false",
       "team modify aooni_out seeFriendlyInvisibles false",
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
       f"scoreboard players set #{WALK_FRAMES} aooni.var {WALK_FRAMES}",
       f"scoreboard players set #{WALK_TICKS}t aooni.var {WALK_TICKS}",
       "function aooni:setup/gamerules",
       "time set 18000",
       "weather clear",
       "difficulty normal",
       f"setworldspawn {P(*LOBBY)}",
       "forceload add -32 -6 61 61",
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
       "execute unless loaded 60 -60 60 run return run schedule function aooni:setup/check_build 1s",
       "execute unless loaded -30 -60 60 run return run schedule function aooni:setup/check_build 1s",
       "execute unless loaded 60 -60 -5 run return run schedule function aooni:setup/check_build 1s",
       "# 게임 도중에 다시 지으면 숨겨 둔 숫자·모형이 사라진다 → 판이 끝난 뒤에 짓는다",
       f"execute unless score #built aooni.var matches {BUILD_VERSION} unless score #state aooni.var matches 0 run return run schedule function aooni:setup/check_build 10s",
       f"execute unless score #built aooni.var matches {BUILD_VERSION} run function aooni:build/all",
       "execute if score #state aooni.var matches 0 run function aooni:lobby/show_diff")
    fn("build/all",
       "kill @e[tag=aooni.fx]",
       "kill @e[type=minecraft:zombie,tag=aooni.oni]",
       "# 이전 버전의 연습용 좀비가 남아 있으면 정리",
       "kill @e[type=minecraft:zombie,tag=aooni.dummy]",
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
       "execute if entity @s[tag=aooni.alive] run function aooni:player/died",
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
         ("knockback_resistance", "block_interaction_range", "scale", "max_health", "attack_damage")])
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
                                                                          T(f"  (생존자 목숨 {DIFF[d]['lives']}개 · {-(-20 // DIFF[d]['dmg'])}대 맞으면 쓰러짐 · 아오오니 {SPEED_TEXT[DIFF[d]['speed']]})", "gray"))
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
            T("생존자: ", "gold"), T("저택 곳곳의 상자를 열어 비밀번호 쪽지 4장(①~④번째 자리)을 찾고, ", "white"),
            T("2층 창고 금고에 넣어 마검을 꺼내라. 판마다 숫자와 숨은 위치가 바뀐다.\n", "white"),
            T("아오오니: ", "gold"), T("3층에서 20초 뒤 깨어난다. 생존자를 때려 쓰러뜨린다(난이도에 따라 3~5대). 문·버튼·옷장·상자는 만질 수 없다.\n", "white"),
            T("쓰러지면: ", "gold"), T("지하 감옥에서 부활(목숨 -1). 동료가 감옥 앞 버튼으로 구출. 목숨을 다 잃으면 관전. 체력은 상자 속 음식·물약으로만 회복된다.\n", "white"),
            T("옷장: ", "gold"), T("가문비나무 문 옷장에 들어가 문을 닫으면 완전히 안전. 아오오니는 절대 열 수 없다.\n", "white"),
            T("결전: ", "gold"), T("마검이 나오면 아오오니가 거대해지고 체력바가 뜬다. 마검(힘 V)만 피해를 준다 — 맨손은 0. ", "white"),
            T("마검을 든 사람이 쓰러지면 그 자리에 떨어진다.\n", "white"),
            T("혼자 연습: ", "gold"), T("대기실 양쪽 끝 버튼. 생존자 연습은 아오오니 없이 상자·금고를 해 보고, 아오오니 연습은 승패 없이 둘러본다. ", "white"),
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
       "execute if score #test aooni.var matches 1 run scoreboard players set #freeze aooni.var 0",
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
           T("아오오니 없이 저택을 둘러보며 상자를 열고 금고를 풀어 볼 수 있다. 마검을 꺼내면 연습 끝.\n", "white"),
           T("끝내기: 채팅에 ", "gray"), T("/trigger aooni.quit", "yellow")),
       "execute if score #test aooni.var matches 2 run " + tell(
           "@a[tag=aooni.player]", T("\n[혼자 연습 · 아오오니] ", "light_purple", bold=True),
           T(f"생존자가 없어서 승패가 나지 않는다. {ONI_FREEZE}초 뒤 움직일 수 있다. 문·버튼·옷장을 못 만지는지 확인해 보자.\n", "white"),
           T("끝내기: 채팅에 ", "gray"), T("/trigger aooni.quit", "yellow")),
       *[f"execute if score #diff aooni.var matches {d} run " + tell("@a[tag=aooni.player]", T("난이도 ", "gray"), T(n, c, bold=True),
                                                                          T(f" · 생존자 목숨 {DIFF[d]['lives']}개 · {-(-20 // DIFF[d]['dmg'])}대 맞으면 쓰러짐 · 아오오니 {SPEED_TEXT[DIFF[d]['speed']]}", "gray"))
         for d, (n, c) in DIFF_NAMES.items()])
    fn("player/enter",
       "tag @s add aooni.player",
       "tag @s add aooni.alive",
       "scoreboard players operation @s aooni.gid = #gid aooni.var",
       *[f"execute if score #diff aooni.var matches {d} run scoreboard players set @s aooni.lives {DIFF[d]['lives']}" for d in DIFF],
       "scoreboard players set @s aooni.grace 0",
       "scoreboard players set @s aooni.leave 0",
       "team join aooni_alive @s",
       "gamemode adventure @s",
       "clear @s",
       "effect clear @s",
       "function aooni:player/reset_attrs",
       "function aooni:player/survivor_effects",
       "effect give @s minecraft:instant_health 1 4 true",
       "# 쓰러지면 감옥에서 부활한다",
       f"spawnpoint @s {P(int(JAIL[0]), JAIL[1], int(JAIL[2]))}")
    fn("player/survivor_effects",
       "effect give @s minecraft:saturation infinite 0 true",
       "execute unless entity @s[tag=aooni.armed] run effect give @s minecraft:weakness infinite 9 true",
       f"execute if entity @s[tag=aooni.armed] run effect give @s minecraft:strength infinite {WEAPON_STRENGTH} true",
       "execute if entity @s[tag=aooni.jailed] run effect give @s minecraft:resistance infinite 4 true")
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
       "attribute @s minecraft:knockback_resistance base set 1",
       *[f"execute if score #diff aooni.var matches {d} run attribute @s minecraft:attack_damage base set {v['dmg']}" for d, v in DIFF.items()])
    fn("oni/model", *oni_model_cmds(1.0))
    fn("oni/model_big", *oni_model_cmds(FINAL_SCALE))
    # ---- 걷기·공격·고개 동작 (as 아오오니, 매 틱)
    fn("oni/anim",
       "scoreboard players operation #mv aooni.var = @s aooni.mw",
       "scoreboard players operation #mv aooni.var += @s aooni.ms",
       "scoreboard players operation #mv aooni.var += @s aooni.mc",
       "scoreboard players set @s aooni.mw 0",
       "scoreboard players set @s aooni.ms 0",
       "scoreboard players set @s aooni.mc 0",
       "execute if score @s aooni.dd matches 1.. run function aooni:oni/anim/attack",
       "scoreboard players set @s aooni.dd 0",
       "execute if score #atk aooni.var matches 1.. run scoreboard players remove #atk aooni.var 1",
       "execute if score #atk aooni.var matches 3 run function aooni:oni/anim/swing_back_d",
       "execute if score #atk aooni.var matches 1 run function aooni:oni/anim/arm_rest_d",
       "execute if score #mv aooni.var matches 1.. run function aooni:oni/anim/step",
       "execute if score #mv aooni.var matches ..0 run function aooni:oni/anim/still",
       "function aooni:oni/anim/look")
    fn("oni/anim/step",
       "scoreboard players set #still aooni.var 0",
       "scoreboard players add #ap aooni.var 1",
       "scoreboard players operation #am aooni.var = #ap aooni.var",
       f"scoreboard players operation #am aooni.var %= #{WALK_TICKS}t aooni.var",
       "execute unless score #am aooni.var matches 0 run return 0",
       "scoreboard players operation #af aooni.var = #ap aooni.var",
       f"scoreboard players operation #af aooni.var /= #{WALK_TICKS}t aooni.var",
       f"scoreboard players operation #af aooni.var %= #{WALK_FRAMES} aooni.var",
       "execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/frame_big",
       "function aooni:oni/anim/frame")
    fn("oni/anim/still",
       "scoreboard players add #still aooni.var 1",
       "execute unless score #still aooni.var matches 3 run return 0",
       "scoreboard players set #ap aooni.var 0",
       "execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/rest_big",
       "function aooni:oni/anim/rest")
    for tag, s in (("", 1.0), ("_big", FINAL_SCALE)):
        fn(f"oni/anim/frame{tag}",
           *[f"execute if score #af aooni.var matches {i} run return run function aooni:oni/anim/w{i}{tag}" for i in range(WALK_FRAMES)])
        for i in range(WALK_FRAMES):
            pose = walk_pose(i)
            fn(f"oni/anim/w{i}{tag}", *[
                ("execute unless score #atk aooni.var matches 1.. run " if part == "arm_r" else "") + part_merge(part, deg, s, WALK_TICKS)
                for part, deg in pose.items()])
        fn(f"oni/anim/rest{tag}", *[
            ("execute unless score #atk aooni.var matches 1.. run " if part == "arm_r" else "") + part_merge(part, 0, s, 4)
            for part in ("leg_l", "leg_r", "arm_l", "arm_r")])
        fn(f"oni/anim/swing{tag}", part_merge("arm_r", -95, s, 2))
        fn(f"oni/anim/swing_back{tag}", part_merge("arm_r", 15, s, 3))
        fn(f"oni/anim/arm_rest{tag}", part_merge("arm_r", 0, s, 3))
        fn(f"oni/anim/head{tag}", *[f"execute if score #hb aooni.var matches {b} run " + part_merge("head", 15 * b, s, 3)
                                    for b in range(-2, 3)])
    for nm in ("swing", "swing_back", "arm_rest"):
        fn(f"oni/anim/{nm}_d",
           f"execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/{nm}_big",
           f"function aooni:oni/anim/{nm}")
    fn("oni/anim/attack",
       "# 때리면 오른팔을 앞으로 휘둘렀다가(6틱) 내린다",
       "scoreboard players set #atk aooni.var 6",
       "function aooni:oni/anim/swing_d")
    fn("oni/anim/look",
       "# 아오오니가 위아래를 보면 고개도 따라 든다/숙인다(5단계, 바뀔 때만)",
       "execute if entity @s[x_rotation=..-22] run scoreboard players set #hb aooni.var -2",
       "execute if entity @s[x_rotation=-22..-7] run scoreboard players set #hb aooni.var -1",
       "execute if entity @s[x_rotation=-7..7] run scoreboard players set #hb aooni.var 0",
       "execute if entity @s[x_rotation=7..22] run scoreboard players set #hb aooni.var 1",
       "execute if entity @s[x_rotation=22..] run scoreboard players set #hb aooni.var 2",
       "execute if score #hb aooni.var = #hbl aooni.var run return 0",
       "scoreboard players operation #hbl aooni.var = #hb aooni.var",
       "execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/head_big",
       "function aooni:oni/anim/head")
    place = []
    for j in range(1, 5):
        place.append(("dig%d" % j, digit_paper(j), [f"tag @s add aooni.dig{j}"]))
    for key, n, item in SPECIALS:
        place += [(key, item, [])] * n
    for k, o in enumerate(FAKE_ORD, 1):
        place.append(("fake%d" % k, digit_paper(o, "fake"), []))
    put_lines = []
    for key, item, extra in place:
        put_lines += ["execute store result storage aooni:v slot int 1 run random value 0..26",
                      "execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s "
                      f"run function aooni:loot/put/{key} with storage aooni:v"]
        if f"loot/put/{key}" not in FUNCS:
            fn(f"loot/put/{key}", "tag @s add aooni.loot", *extra, f"$item replace block ~ ~ ~ container.$(slot) with {item}")
    fn("game/assign_loot",
       "# 상자를 모두 비우고 → 상자마다 잡동사니를 0~2개 → 특수 아이템(쪽지·회복·도망/방해·가짜 쪽지)을 서로 다른 상자에 하나씩",
       "execute at @e[type=minecraft:marker,tag=aooni.spot] run data modify block ~ ~ ~ Items set value []",
       "execute as @e[type=minecraft:marker,tag=aooni.spot] at @s run function aooni:loot/junk_roll",
       "execute as @e[type=minecraft:marker,tag=aooni.spot] at @s run function aooni:loot/junk_roll",
       *put_lines)
    fn("loot/junk_roll",
       f"execute store result score #r aooni.var run random value 1..{JUNK_ROLL}",
       "execute store result storage aooni:v slot int 1 run random value 0..26",
       *[f"execute if score #r aooni.var matches {i} run function aooni:loot/junk/{i} with storage aooni:v" for i in range(1, len(JUNK) + 1)])
    for i, (it, name, lore) in enumerate(JUNK, 1):
        fn(f"loot/junk/{i}", f"$item replace block ~ ~ ~ container.$(slot) with {item_named(it, name, 'gray', lore)}")

    # ---------------- 틱/초
    fn("game/tick",
       f"execute if score #freeze aooni.var matches 1.. as {ONI} positioned {P(*ONI_SPAWN)} unless entity @s[distance=..0.4] run tp @s {P(*ONI_SPAWN)}",
       f"execute as {ONI} at @s run tp @e[type=minecraft:item_display,tag=aooni.part] ~ ~ ~ ~ 0",
       f"execute as {ONI} run function aooni:oni/anim",
       "execute as @a[scores={aooni.eb=1..}] run function aooni:item/ate_bread",
       "execute as @a[scores={aooni.es=1..}] run function aooni:item/ate_steak",
       f"execute as @a[tag=aooni.oni_p] at @s run function aooni:oni/no_sword",
       "execute as @a[tag=aooni.oni_p] if items entity @s container.* minecraft:paper run function aooni:oni/no_paper",
       "function aooni:hide/check",
       f"execute if score #final aooni.var matches 1 as {ONI} at @s run function aooni:final/hp")
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
       "# (혼자 연습은 승패 판정을 하지 않는다. 생존자 연습에서 아무도 안 남으면 연습을 끝낸다)",
       "execute if score #test aooni.var matches 0 if score #alive aooni.var matches 0 if score #son aooni.var >= #nsurv aooni.var run return run function aooni:game/oni_win",
       "execute if score #test aooni.var matches 0 if score #a0 aooni.var matches 20.. run return run function aooni:game/oni_win",
       "execute if score #test aooni.var matches 1 if score #a0 aooni.var matches 20.. run return run function aooni:test/abandon",
       f"execute unless score #test aooni.var matches 1 unless entity {ONI} run scoreboard players add #oni_gone aooni.var 1",
       f"execute if entity {ONI} run scoreboard players set #oni_gone aooni.var 0",
       "execute if score #final aooni.var matches 1 if score #oni_gone aooni.var matches 30.. run return run function aooni:game/victory",
       "execute if score #oni_gone aooni.var matches 30.. run return run function aooni:game/no_oni",
       "execute if score #wpn aooni.var matches 1 run function aooni:weapon/watch",
       "function aooni:hide/stall",
       f"execute as @a[tag=aooni.player,tag=!aooni.jailed,gamemode=adventure,{JAIL_BOX}] run tp @s {P(*RELEASE)} 180 0",
       "# 엔더 진주 등으로 저택 밖에 나가면 현관홀로 돌려보낸다",
       f"execute as @a[tag=aooni.alive,gamemode=adventure] unless entity @s[{MANSION_BOX}] run function aooni:player/spawn_pos",
       "execute if score #freeze aooni.var matches 1.. run function aooni:game/freeze_sec",
       "execute as @a[tag=aooni.alive] run function aooni:player/arm_check",
       f"execute as @a[tag=aooni.alive,tag=!aooni.hidden] at @s if entity {ONI[:-1]},distance=..9] run function aooni:player/near_oni",
       "function aooni:loot/check",
       "execute if score #wpn aooni.var matches 1 as @e[type=minecraft:marker,tag=aooni.spot] at @s "
       "if data block ~ ~ ~ Items[{id:\"minecraft:netherite_sword\"}] run function aooni:weapon/unchest",
       f"execute as @a[tag=aooni.jailed] unless entity @s[{JAIL_BOX}] run tp @s {P(*JAIL)} 180 0",
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
       "bossbar set aooni:goal color red")
    fn("game/sidebar",
       "scoreboard players operation §a생존자 aooni.side = #alive aooni.var",
       "scoreboard players operation §c감옥 aooni.side = #jailed aooni.var",
       "scoreboard players operation §6숫자(4) aooni.side = #found aooni.var",
       "scoreboard players operation §7경과(분) aooni.side = #sec aooni.var",
       "scoreboard players operation §7경과(분) aooni.side /= #60 aooni.var")
    goals = ["상자를 열어 비밀번호 쪽지 4장을 찾아라", "2층 창고 금고에 비밀번호를 넣어 마검을 꺼내라!",
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
                "kill @e[tag=aooni.part]",
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
       *door_cmds(27, F1, 43, "north", "left", True),
       *door_cmds(28, F1, 43, "north", "right", True),
       "time set 1000",
       tell("@a", T("\n[아오오니 저택] ", "blue"), T("생존자 승리! ", "gold", bold=True),
            T("아오오니가 쓰러지자 현관문이 열리고 아침 햇살이 들어온다. 12초 뒤 대기실로.", "white")))
    fn("game/oni_win",
       *end_common(10),
       f"title @a title {comp(T('아오오니의 승리', 'dark_red', bold=True))}",
       "title @a subtitle " + comp(T("생존자가 모두 붙잡혔다", "gray"), *took),
       "execute as @a at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 1 0.6",
       tell("@a", T("\n[아오오니 저택] ", "blue"), T("아오오니 ", "dark_red", bold=True),
            {"selector": "@a[tag=aooni.oni_p]", "color": "dark_red"}, T(" 의 승리! 10초 뒤 대기실로.", "white")))
    fn("game/no_oni",
       *end_common(5),
       f"title @a title {comp(T('게임 중단', 'gray'))}",
       f"title @a subtitle {comp(T('아오오니가 자리를 비웠다', 'gray'))}",
       tell("@a", T("[아오오니 저택] 아오오니가 30초 동안 없어서 게임을 끝냅니다.", "gray")))
    fn("game/ending_sec",
       "scoreboard players remove #end_t aooni.var 1",
       "execute if score #end_t aooni.var matches ..0 run function aooni:game/reset")
    fn("game/reset",
       "kill @e[tag=aooni.part]",
       "scoreboard players set #state aooni.var 0",
       "scoreboard players set #cd aooni.var 0",
       "bossbar set aooni:goal visible false",
       "bossbar set aooni:boss visible false",
       "time set 18000",
       "kill @e[type=minecraft:item]",
       "kill @e[type=minecraft:zombie,tag=aooni.dummy]",
       "scoreboard players set #test aooni.var 0",
       "scoreboard objectives setdisplay sidebar",
       "scoreboard players reset * aooni.side",
       "execute as @a[gamemode=!creative] run function aooni:player/to_lobby",
       "execute as @a[gamemode=creative,tag=aooni.player] run effect clear @s",
       "execute as @a[gamemode=creative] run function aooni:player/clear_tags",
       "execute as @a[gamemode=creative] run function aooni:player/reset_attrs",
       "team leave @a[gamemode=creative]")

    # ---------------- 잡힘/감옥
    fn("player/died",
       "# 아오오니에게 맞아 체력이 다 닳았다(곧바로 감옥에서 부활한 상태). 들고 있던 마검은 쓰러진 자리에 떨어진다",
       "function aooni:player/drop_sword_at_death",
       "tag @s remove aooni.alive",
       "tag @s remove aooni.hidden",
       "tag @s remove aooni.hid_new",
       "scoreboard players remove @s aooni.lives 1",
       "title @s times 5 40 15",
       f"title @s title {comp(T('쓰러졌다…', 'dark_red', bold=True))}",
       "effect give @s minecraft:blindness 3 0 true",
       "playsound minecraft:entity.ghast.scream master @s ~ ~ ~ 1 0.5",
       tell("@a[tag=aooni.player]", SEL, T(" 이(가) 아오오니에게 당했다! ", "red"), T("(남은 목숨 ", "gray"),
            {"score": {"name": "@s", "objective": "aooni.lives"}, "color": "yellow"}, T(")", "gray")),
       "execute if score @s aooni.lives matches 1.. run function aooni:player/jail",
       "execute if score @s aooni.lives matches ..0 run function aooni:player/out",
       "execute as @a[tag=aooni.oni_p] at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.6 0.6")
    fn("player/jail",
       "tag @s add aooni.jailed",
       "team join aooni_out @s",
       "effect give @s minecraft:resistance infinite 4 true",
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
       f"tp @s {P(*RELEASE)} 180 0",
       "effect clear @s minecraft:resistance",
       "effect give @s minecraft:resistance 5 4 true",
       actionbar("@s", T("풀려났다! 5초간 다치지 않는다", "green")))
    fn("player/near_oni",
       "playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1",
       "effect give @s minecraft:darkness 2 0 true",
       actionbar("@s", T("…아오오니가 가까이 있다!", "red", bold=True)))

    # ---------------- 마검
    fn("player/drop_sword_at_death",
       "# 쓰러진 자리(LastDeathLocation)에 마검을 떨어뜨린다. 반짝여서 멀리서도 보인다",
       f"execute store result score #c aooni.var run clear @s minecraft:{WEAPON_ITEM} 0",
       "execute if score #c aooni.var matches 0 run return 0",
       f"clear @s minecraft:{WEAPON_ITEM}",
       *[f"execute store result storage aooni:v {a} int 1 run data get entity @s LastDeathLocation.pos[{i}]" for i, a in enumerate(("dx", "dy", "dz"))],
       "function aooni:player/drop_sword_at with storage aooni:v",
       tell("@a[tag=aooni.player]", T("마검이 쓰러진 자리에 떨어졌다! ", "gold", bold=True), T("누군가 주워서 싸워야 한다!", "yellow")),
       "function aooni:player/arm_check")
    fn("player/drop_sword_at",
       f"$execute positioned $(dx) $(dy) $(dz) run summon minecraft:item ~0.5 ~0.5 ~0.5 "
       f"{{Item:{SWORD_NBT},PickupDelay:20s,Age:-32768s,Glowing:1b,Invulnerable:1b}}")
    fn("item/ate_bread",
       "scoreboard players reset @s aooni.eb",
       "effect give @s minecraft:instant_health 1 0 true",
       actionbar("@s", T("체력 2칸 회복", "green")))
    fn("item/ate_steak",
       "scoreboard players reset @s aooni.es",
       "effect give @s minecraft:instant_health 1 1 true",
       actionbar("@s", T("체력 4칸 회복", "green")))
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
    sword_item = (f"{{Item:{SWORD_NBT},PickupDelay:10s,Age:-32768s,Glowing:1b,"
                  "Invulnerable:1b,Motion:[0.0d,0.0d,0.0d]}")
    fn("weapon/respawn",
       "# 아오오니와 24칸 넘게 떨어진 조사 지점 중 무작위 한 곳(없으면 창고 금고 앞)에 마검을 놓는다",
       "tag @e[type=minecraft:marker,tag=aooni.wcand] remove aooni.wcand",
       "execute as @e[type=minecraft:marker,tag=aooni.spot] at @s unless entity @a[tag=aooni.oni_p,distance=..24] run tag @s add aooni.wcand",
       f"execute at @e[type=minecraft:marker,tag=aooni.wcand,sort=random,limit=1] run summon minecraft:item ~ ~1 ~ {sword_item}",
       f"execute unless entity @e[type=minecraft:marker,tag=aooni.wcand] run summon minecraft:item {P(*VAULT_DROP)} {sword_item}")
    fn("weapon/unchest",
       "# 마검은 상자에 가둘 수 없다 → 상자 위로 튀어나온다",
       f"data remove block ~ ~ ~ Items[{{id:\"minecraft:{WEAPON_ITEM}\"}}]",
       f"summon minecraft:item ~ ~1 ~ {sword_item}",
       "playsound minecraft:block.chest.close block @a[distance=..16] ~ ~ ~ 1 0.6",
       tell("@a[tag=aooni.player]", T("마검은 상자에 가둘 수 없다! ", "gold"), T("상자 위로 튀어나왔다.", "yellow")))
    SWORD_SEL = f"@e[type=minecraft:item,nbt={{Item:{{id:\"minecraft:{WEAPON_ITEM}\"}}}}]"
    fn("weapon/watch",
       "# 떨어진 마검은 사라지지 않고 반짝이게, 어디에도 없으면(소지자 퇴장 등) 10초 뒤 다시 나타나게",
       f"execute as {SWORD_SEL} run data merge entity @s {{Age:-32768s,Invulnerable:1b,Glowing:1b}}",
       f"execute store result score #sw aooni.var run clear @a minecraft:{WEAPON_ITEM} 0",
       f"execute store result score #swi aooni.var if entity {SWORD_SEL}",
       "scoreboard players operation #sw aooni.var += #swi aooni.var",
       "execute if score #sw aooni.var matches 1.. run scoreboard players set #swlost aooni.var 0",
       "execute if score #sw aooni.var matches 0 run scoreboard players add #swlost aooni.var 1",
       "execute if score #swlost aooni.var matches 10.. run function aooni:weapon/lost",
       "# 어떤 이유로든 2개가 되면 바닥에 떨어진 쪽을 하나 지운다",
       f"execute if score #sw aooni.var matches 2.. if score #swi aooni.var matches 1.. run kill {SWORD_SEL[:-1]},limit=1]")
    fn("weapon/lost",
       "scoreboard players set #swlost aooni.var 0",
       "function aooni:weapon/respawn",
       tell("@a[tag=aooni.player]", T("사라졌던 마검이 저택 어딘가에 다시 나타났다! ", "gold"), T("(반짝이는 곳)", "yellow")))
    fn("weapon/dedupe",
       "# 오프라인으로 들고 나갔던 마검이 이미 다시 나타났다면, 돌아온 사람 것은 지운다(상자 속 마검도 먼저 꺼내서 센다)",
       "execute as @e[type=minecraft:marker,tag=aooni.spot] at @s if data block ~ ~ ~ Items[{id:\"minecraft:netherite_sword\"}] run function aooni:weapon/unchest",
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
       '[minecraft:custom_name={text:"$(nm)",color:"gold",italic:false},minecraft:enchantment_glint_override=true,'
       'minecraft:item_model="aooni:magum"]')

    # ---------------- 결전
    fn("final/start",
       "# 생존자 연습은 싸울 아오오니가 없으니 여기서 연습 끝",
       "execute if score #test aooni.var matches 1 run return run function aooni:test/done",
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
       "execute store result bossbar aooni:boss max run scoreboard players get #hp aooni.var",
       "execute store result bossbar aooni:boss value run scoreboard players get #hp aooni.var",
       "bossbar set aooni:boss name " + comp(T("거대 아오오니 ", "dark_red", bold=True), {"selector": "@a[tag=aooni.oni_p]", "color": "red"}),
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
       "effect give @s minecraft:speed infinite 2 true",
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
        force += door_cmds(*c["door"], c["facing"], "left", True, mat="spruce_door")
    hide += ["execute as @a[tag=aooni.hid_new,tag=!aooni.hidden] run function aooni:hide/enter",
             "execute as @a[tag=aooni.hidden,tag=!aooni.hid_new] run function aooni:hide/leave"]
    fn("hide/check", *hide)
    unstick = ["# 1.3배가 되면 키가 2칸을 넘는다 → 옷장(2칸)이나 낮은 곳에 있으면 질식하므로 먼저 꺼낸다"]
    for c in CLOSETS:
        x, y, z, dx, dy, dz = c["box"]
        unstick.append(f"execute if entity @s[x={x},y={y},z={z},dx={dx},dy={dy},dz={dz}] run return run tp @s {P(*c['out'])}")
    low = set()
    for (x, y, z) in reachable((SPAWN_POINTS[0][0], F1, SPAWN_POINTS[0][1]), doors_open=True):
        blk = WORLD.get((x, y + 2, z))
        if blk is None:
            continue
        b = bid(blk)
        if b.endswith(PASSABLE_SUFFIX) or "lantern" in b or "glass" in b or b.endswith(("_bars", "_door", "_trapdoor")):
            continue
        low.add(b)
    unstick += [f"execute at @s if block ~ ~2 ~ minecraft:{b} run return run tp @s {P(*ONI_SPAWN)}" for b in sorted(low)]
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

    # ---------------- 조사 상자: 쪽지를 처음 손에 넣으면 '찾음'
    for j in range(1, 5):
        fn(f"loot/put_digit{j}", f"item replace block ~ ~ ~ container.13 with {digit_paper(j)}")
    check = []
    for j in range(1, 5):
        pred = f"minecraft:paper[minecraft:custom_data={{aooni_dig:{j}}}]"
        for slot in ("container.*", "weapon.offhand"):
            check.append(f"execute if score #f{j} aooni.var matches 0 as {SURV} if items entity @s {slot} {pred} "
                         f"run function aooni:loot/found{j}")
    for slot in ("container.*", "weapon.offhand"):
        check.append(f"execute as {SURV} if items entity @s {slot} minecraft:paper[minecraft:custom_data={{aooni_fake:1b}}] "
                     "run function aooni:loot/fake")
    fn("loot/check", "# 생존자가 비밀번호 쪽지(또는 가짜 쪽지)를 처음 손에 넣었는지(1초마다)", *check)
    fn("loot/fake",
       "clear @s minecraft:paper[minecraft:custom_data={aooni_fake:1b}]",
       f"give @s {item_named('paper', '번진 쪽지', 'gray', '글씨가 번져서 아무것도 읽을 수 없다')}",
       "playsound minecraft:item.book.page_turn player @s ~ ~ ~ 1 0.8",
       tell("@s", T("쪽지를 펼쳐 보니… 글씨가 번져서 아무것도 읽을 수 없다. ", "gray"), T("가짜였다!", "red")))
    for j in range(1, 5):
        fn(f"loot/found{j}",
           f"execute if score #f{j} aooni.var matches 1 run return 0",
           f"scoreboard players set #f{j} aooni.var 1",
           "scoreboard players add #found aooni.var 1",
           f"clear @s minecraft:paper[minecraft:custom_data={{aooni_dig:{j}}}]",
           f"function aooni:loot/read{j} with storage aooni:v",
           sound_all("minecraft:entity.experience_orb.pickup", 1.3, who=SURV),
           "function aooni:game/progress")
        # 숫자는 생존자 모두에게 알린다(쪽지를 가진 사람이 잡히거나 나가도 숫자가 사라지지 않게). 아오오니에게는 안 보인다
        fn(f"loot/read{j}",
           f"$give @s {digit_paper(j, f'$(k{j})')}",
           f'$tellraw {SURV} {{"text":"","extra":[{{"selector":"@s","color":"aqua"}},{{"text":" 이(가) 비밀번호 쪽지 {CIRC[j]} 을(를) 찾았다: ","color":"white"}},'
           f'{{"text":"『{ORD[j]} 자리 = $(k{j})』","color":"dark_red","bold":true}},{{"text":" (","color":"white"}},'
           '{"score":{"name":"#found","objective":"aooni.var"},"color":"gold"},{"text":"/4)","color":"white"}]}')
    # 아오오니가 (누가 떨어뜨린) 쪽지를 주우면: 아직 아무도 안 읽은 쪽지는 원래 상자로 돌려보내고, 읽은 쪽지는 없앤다
    fn("oni/no_paper",
       *[f"execute if items entity @s container.* minecraft:paper[minecraft:custom_data={{aooni_dig:{j}}}] "
         f"at @e[type=minecraft:marker,tag=aooni.dig{j},limit=1] run function aooni:loot/put_digit{j}" for j in range(1, 5)],
       "clear @s minecraft:paper")

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
       "# 생존자 연습: 모험 모드인 사람 모두 생존자, 아오오니 없음(상자·금고·마검까지)",
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
    fn("test/done",
       *end_common(10),
       f"title @a title {comp(T('마검을 손에 넣었다!', 'gold', bold=True))}",
       f"title @a subtitle {comp(T('실전이라면 여기서 아오오니와 결전이 시작된다', 'gray'))}",
       "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1",
       tell("@a", T("\n[혼자 연습] ", "aqua", bold=True), T("연습 끝! 10초 뒤 대기실로.", "white")))
    fn("test/abandon",
       tell("@a", T("[아오오니 저택] ", "blue"), T("연습하던 사람이 없어서 연습을 끝냅니다.", "gray")),
       "function aooni:game/reset")
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
       "# 인원 제한 없이 생존자 연습(모험 모드인 사람 모두 생존자, 아오오니 없음)",
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
    for (aid, x, y, z) in SPOTS:
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
        rp = os.path.join(dist, "aooni-resourcepack.zip")
        if os.path.exists(rp):
            add(z, rp, "aooni-mansion-server/aooni-resourcepack.zip")
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
        for y in FLOORS:
            print(f"--- y={y}")
            print(ascii_map(y, -1, 57, -1, 56))
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
