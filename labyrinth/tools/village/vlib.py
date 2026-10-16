#!/usr/bin/env python3
"""vlib — 마을 조각(청사진) 그리기 라이브러리. 계약: VILLAGE.md §2.

조각 하나 = 정방향 캔버스 W×H×D. **정면(문 쪽)은 z=0 줄이고 북쪽(−Z)을 본다.** x 증가 = 동쪽, z 증가 = 남쪽,
y 증가 = 위. 칸 값: ' ' = 건드리지 않음(원래 지형), '.' = 공기여야 함, 그 밖 = 블록 문자열.

    from vlib import *
    p = Piece("demo_hut", "예제 오두막", 7, 9, 7, floor_y=1, anchor=(3, 2))
    p.fill(1, 1, 1, 5, 1, 5, mix(("spruce_planks", 3), ("stripped_spruce_wood", 1)))
    p.gable_roof(1, 1, 5, 5, 5, "dark_oak")
    p.door("spruce", 3, 2, 1, "north")
    p.finalize()          # 연결 상태·기본값 채우기 → 검증 → 팔레트 (build_all.py 가 불러 줌)

블록 이름·속성은 blockdata.json(26.x 바닐라 데이터 생성기 결과)으로 검사한다 — 없는 블록·속성은 set 할 때 바로 예외.
finalize 뒤 모든 블록 문자열은 속성을 전부 명시한다 (Java 는 물리 업데이트 없이 놓으므로 연결 상태를 다시 계산하지 않음).
"""
import collections
import json
import math
import os
import re
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

__all__ = [
    "VillageError", "Piece", "Blueprint", "Mix", "mix",
    "B", "stairs", "slab", "log", "pillar", "leaves", "lantern", "candle", "fence", "fence_gate", "wall",
    "pane", "bars", "trapdoor", "chain", "campfire", "torch", "end_rod", "carpet", "wool", "terracotta",
    "concrete", "glass", "flower_pot", "planks",
    "parse_block", "format_block", "check_block", "rotate_state", "rot_xz", "rot_dir", "rotated_size",
    "front_rotation", "DIRS", "DXZ", "cw", "ccw", "opposite", "ROTATIONS", "DYES",
]


class VillageError(Exception):
    """조각 설계 오류 — 메시지에 조각 id·좌표·이유를 담는다."""


# ─────────────────────────────── 블록 데이터 (blockdata.json) ───────────────────────────────

_DATA = None


def blockdata():
    global _DATA
    if _DATA is None:
        path = os.path.join(HERE, "blockdata.json")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        d["_full"] = set(d["full"])
        d["_tags"] = {k: set(v) for k, v in d["tags"].items()}
        d["_props"] = {b: collections.OrderedDict((p, (vals, dflt)) for p, vals, dflt in lst)
                       for b, lst in d["blocks"].items()}
        d["_patterns"] = set(d["banner_patterns"])
        _DATA = d
    return _DATA


def known(bid):
    return bid in blockdata()["_props"]


def tag(name):
    return blockdata()["_tags"].get(name, set())


def is_full(bid):
    """모델이 완전한 정육면체인 블록 (울타리·판유리·담장 연결의 '단단한 면' 판정 기준)."""
    return bid in blockdata()["_full"]


DYES = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray",
        "cyan", "purple", "blue", "brown", "green", "red", "black")

# ─────────────────────────────── 방향·회전 ───────────────────────────────

DIRS = ("north", "east", "south", "west")          # 시계 방향 순서
DXZ = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
AXIS = {"north": "z", "south": "z", "east": "x", "west": "x"}
_ALIASES = {"front": "north", "back": "south", "left": "west", "right": "east",
            "n": "north", "e": "east", "s": "south", "w": "west"}
ROTATIONS = ("NONE", "CLOCKWISE_90", "CLOCKWISE_180", "COUNTERCLOCKWISE_90")   # 시계 방향 90° 횟수 = 인덱스
_FRONT_ROT = {"north": 0, "east": 1, "south": 2, "west": 3}
# 마커 face: 건물이 북쪽을 볼 때 건물의 왼손 = 서쪽, 오른손 = 동쪽
_FACE_OF_DIR = {"north": "front", "south": "back", "west": "left", "east": "right"}


def norm_dir(d):
    d = str(d).lower()
    d = _ALIASES.get(d, d)
    if d not in DXZ:
        raise VillageError("방향은 north/east/south/west (또는 front/back/left/right) 중 하나여야 합니다: %r" % d)
    return d


def cw(d):
    return DIRS[(DIRS.index(d) + 1) % 4]


def ccw(d):
    return DIRS[(DIRS.index(d) + 3) % 4]


def opposite(d):
    return DIRS[(DIRS.index(d) + 2) % 4]


def rot_index(r):
    """'NONE'/'CLOCKWISE_90'/... 또는 0..3 → 시계 방향 90° 횟수."""
    if isinstance(r, int):
        return r % 4
    r = str(r).upper()
    if r in ROTATIONS:
        return ROTATIONS.index(r)
    alias = {"CW90": 1, "CW180": 2, "CCW90": 3, "CW270": 3, "0": 0, "90": 1, "180": 2, "270": 3}
    if r in alias:
        return alias[r]
    raise VillageError("회전 값이 이상합니다: %r" % r)


def front_rotation(front):
    """layout 의 front(조각 정면이 바라볼 방향) → 회전 인덱스 (north=NONE, east=CW90, south=CW180, west=CCW90)."""
    return _FRONT_ROT[norm_dir(front)]


def rot_dir(d, r):
    r = rot_index(r)
    if d in DXZ:
        return DIRS[(DIRS.index(d) + r) % 4]
    return d


def rotated_size(W, D, r):
    return (W, D) if rot_index(r) % 2 == 0 else (D, W)


def rot_xz(x, z, W, D, r):
    """VILLAGE.md §2.1 좌표 회전: 정방향 (x, z) → 회전 후 발자국 안 (x', z')."""
    r = rot_index(r)
    if r == 0:
        return x, z
    if r == 1:
        return D - 1 - z, x
    if r == 2:
        return W - 1 - x, D - 1 - z
    return z, W - 1 - x


# ─────────────────────────────── 블록 문자열 ───────────────────────────────

BLOCK_RE = re.compile(r"^minecraft:[a-z0-9_]+(\[[a-z0-9_]+=[a-z0-9_]+(,[a-z0-9_]+=[a-z0-9_]+)*\])?$")
_PARSE_CACHE = {}


def parse_block(s):
    """'minecraft:oak_stairs[facing=north,half=bottom]' → ('oak_stairs', {'facing': 'north', 'half': 'bottom'})."""
    r = _PARSE_CACHE.get(s)
    if r is not None:
        return r[0], dict(r[1])
    body = s[10:] if s.startswith("minecraft:") else s
    props = {}
    if "[" in body:
        bid, rest = body.split("[", 1)
        rest = rest.rstrip("]")
        for kv in rest.split(","):
            if kv:
                k, _, v = kv.partition("=")
                props[k] = v
    else:
        bid = body
    _PARSE_CACHE[s] = (bid, tuple(props.items()))
    return bid, props


def format_block(bid, props=None):
    if not props:
        return "minecraft:" + bid
    return "minecraft:%s[%s]" % (bid, ",".join("%s=%s" % (k, props[k]) for k in sorted(props)))


def _val(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v).lower()


def B(name, **props):
    """블록 문자열. B('stone_bricks') → 'minecraft:stone_bricks', B('oak_log', axis='x').
    이미 속성이 붙은 문자열에 속성을 더할 수도 있다: B('minecraft:oak_stairs[facing=north]', half='top')."""
    if name in (" ", "."):
        return name
    bid, base = parse_block(name if name.startswith("minecraft:") else "minecraft:" + name)
    base.update({k: _val(v) for k, v in props.items() if v is not None})
    return format_block(bid, base)


_CHECKED = {}


def check_block(s):
    """블록 문자열 형식·이름·속성 검사. 틀리면 VillageError(이유). 맞으면 그대로 돌려줌."""
    if s in _CHECKED:
        return s
    if not BLOCK_RE.match(s):
        raise VillageError("블록 문자열 형식이 틀렸습니다: %r (minecraft:id[속성=값,...])" % s)
    bid, props = parse_block(s)
    table = blockdata()["_props"]
    if bid not in table:
        hint = ""
        if bid == "chain":
            hint = " — 26.x 에서는 iron_chain"
        elif bid == "grass":
            hint = " — 26.x 에서는 short_grass"
        raise VillageError("26.x 에 없는 블록: %s%s" % (bid, hint))
    spec = table[bid]
    for k, v in props.items():
        if k not in spec:
            raise VillageError("%s 에는 '%s' 속성이 없습니다 (있는 속성: %s)" % (bid, k, ", ".join(spec) or "없음"))
        if v not in spec[k][0]:
            raise VillageError("%s[%s=%s] — 값은 %s 중 하나" % (bid, k, v, "/".join(spec[k][0])))
    _CHECKED[s] = True
    return s


def fill_defaults(s):
    """빠진 속성을 바닐라 기본값으로 채운다 (속성을 '전부 명시'하기)."""
    bid, props = parse_block(s)
    spec = blockdata()["_props"].get(bid)
    if not spec:
        return s
    for k, (vals, dflt) in spec.items():
        props.setdefault(k, dflt)
    return format_block(bid, props)


_ROT_CACHE = {}
_RAIL_CORNERS = {frozenset(("south", "east")): "south_east", frozenset(("south", "west")): "south_west",
                 frozenset(("north", "west")): "north_west", frozenset(("north", "east")): "north_east"}


def rotate_state(s, r):
    """BlockData#rotate 와 같은 블록 상태 회전 (facing·axis·rotation·동서남북 연결·레일 모양).
    계단 shape(inner/outer_left/right)은 회전해도 같은 값."""
    r = rot_index(r)
    if r == 0 or s in (" ", ".") or "[" not in s:
        return s
    key = (s, r)
    if key in _ROT_CACHE:
        return _ROT_CACHE[key]
    bid, props = parse_block(s)
    out = {}
    for k, v in props.items():
        if k in DXZ:                                   # 연결 속성: 이름(방향)이 돌아감
            out[rot_dir(k, r)] = v
        elif k == "facing":
            out[k] = rot_dir(v, r)
        elif k == "axis" and r % 2 == 1 and v in ("x", "z"):
            out[k] = "z" if v == "x" else "x"
        elif k == "rotation":
            out[k] = str((int(v) + 4 * r) % 16)
        elif k == "shape" and bid.endswith("rail"):
            if v.startswith("ascending_"):
                out[k] = "ascending_" + rot_dir(v[10:], r)
            elif v in ("north_south", "east_west"):
                out[k] = v if r % 2 == 0 else ("east_west" if v == "north_south" else "north_south")
            else:
                a, b = v.split("_")
                out[k] = _RAIL_CORNERS[frozenset((rot_dir(a, r), rot_dir(b, r)))]
        else:
            out[k] = v
    res = format_block(bid, out)
    _ROT_CACHE[key] = res
    return res


# ─────────────────────────────── 블록 도우미 ───────────────────────────────

def _strip(mat):
    return mat[10:] if mat.startswith("minecraft:") else mat


def _resolve(mat, kind):
    """재료 이름 + 종류 → 실제 블록 id. stairs('stone_bricks') → stone_brick_stairs, fence('oak') → oak_fence."""
    mat = _strip(mat).split("[", 1)[0]
    if known(mat) and mat.endswith(kind):
        return mat
    bases = [mat]
    for suf, rep in (("_planks", ""), ("_block", ""), ("bricks", "brick"), ("tiles", "tile"), ("s", "")):
        if mat.endswith(suf):
            bases.append(mat[: -len(suf)] + rep)
    for b in bases:
        if known(b + "_" + kind):
            return b + "_" + kind
    raise VillageError("'%s' 재료로 된 %s 블록이 없습니다" % (mat, kind))


def planks(mat):
    """나무 이름 → 판자 (가문비 → spruce_planks). 나무가 아니면 그 재료의 꽉 찬 블록 (stone_brick → stone_bricks)."""
    mat = _strip(mat).split("[", 1)[0]
    for cand in (mat + "_planks", mat, mat + "s", mat + "_block", mat.replace("brick", "bricks"),
                 mat.replace("tile", "tiles")):
        if known(cand) and is_full(cand):
            return "minecraft:" + cand
    for kind in ("_stairs", "_slab"):
        if mat.endswith(kind):
            return planks(mat[: -len(kind)])
    raise VillageError("'%s' 의 꽉 찬 블록을 못 찾았습니다" % mat)


def stairs(mat, facing, half="bottom", shape=None):
    """계단. facing = 높은 쪽(등판)이 있는 방향 = 올라가는 방향. shape 를 비우면 finalize 가 이웃을 보고 계산."""
    return B(_resolve(mat, "stairs"), facing=norm_dir(facing), half=half, shape=shape)


def slab(mat, type="bottom"):
    return B(_resolve(mat, "slab"), type=type)


def log(mat, axis="y"):
    """원목 (spruce → spruce_log, crimson → crimson_stem, 'stripped_spruce', 'spruce_wood' 도 됨)."""
    m = _strip(mat).split("[", 1)[0]
    for cand in (m, m + "_log", m + "_stem", m + "_block"):
        if known(cand) and "axis" in blockdata()["_props"][cand]:
            return B(cand, axis=axis)
    raise VillageError("'%s' 원목을 못 찾았습니다" % mat)


def pillar(mat, axis="y"):
    """축이 있는 블록 (quartz_pillar, purpur_pillar, basalt, bone_block, 원목 …)."""
    return log(mat, axis)


def leaves(mat="oak"):
    """잎 — persistent=true 강제 (안 그러면 사라짐)."""
    return B(_resolve(mat, "leaves"), persistent="true")


def lantern(soul=False, hanging=True, kind=None):
    """등불. kind 로 다른 등불 id 지정 가능 (예: 'copper_lantern')."""
    bid = kind or ("soul_lantern" if soul else "lantern")
    return B(bid, hanging=hanging)


def candle(color=None, n=1, lit=True):
    return B((color + "_candle") if color else "candle", candles=int(n), lit=lit)


def fence(mat="oak"):
    """울타리 — 연결 상태는 finalize 가 계산."""
    return B(_resolve(mat, "fence"))


def fence_gate(mat="oak", facing="north", open=False):
    return B(_resolve(mat, "fence_gate"), facing=norm_dir(facing), open=open)


def wall(mat="cobblestone"):
    """담장 — 연결(none/low/tall)·기둥(up)은 finalize 가 계산."""
    return B(_resolve(mat, "wall"))


def pane(color=None):
    """판유리 (color 없으면 투명 glass_pane, 있으면 색유리판). 연결은 finalize 가 계산."""
    return B((color + "_stained_glass_pane") if color else "glass_pane")


def bars(kind="iron"):
    return B("iron_bars" if kind == "iron" else kind + "_bars")


def trapdoor(mat, facing, half="bottom", open=False):
    """다락문. open=True 면 세워지고 판은 facing 반대쪽 면에 붙는다 (덧문: facing = 창 바깥 방향)."""
    return B(_resolve(mat, "trapdoor"), facing=norm_dir(facing), half=half, open=open)


def chain(axis="y", copper=False):
    """쇠사슬 (26.x 이름은 iron_chain)."""
    return B("copper_chain" if copper else "iron_chain", axis=axis)


def campfire(soul=False, facing="north", lit=True):
    return B("soul_campfire" if soul else "campfire", facing=norm_dir(facing), lit=lit, signal_fire=False)


def torch(soul=False, wall_facing=None):
    """횃불. wall_facing 을 주면 벽 횃불 (facing = 벽에서 멀어지는 방향)."""
    base = "soul_" if soul else ""
    if wall_facing:
        return B(base + "wall_torch", facing=norm_dir(wall_facing))
    return B(base + "torch")


def end_rod(facing="up"):
    return B("end_rod", facing=facing if facing in ("up", "down") else norm_dir(facing))


def carpet(color):
    return B(color + "_carpet" if color in DYES else color)


def wool(color):
    return B(color + "_wool")


def terracotta(color=None):
    return B((color + "_terracotta") if color else "terracotta")


def concrete(color):
    return B(color + "_concrete")


def glass(color=None):
    return B((color + "_stained_glass") if color else "glass")


def flower_pot(plant=None):
    return B("potted_" + plant if plant else "flower_pot")


class Mix:
    """여러 블록을 무게대로 섞기 — fill/set 에 블록 대신 넣으면 칸마다 결정적으로 고른다.
    mix(('stone_bricks', 4), ('mossy_stone_bricks', 1), ('cracked_stone_bricks', 1))"""

    def __init__(self, items, seed=0):
        self.items = []
        for it in items:
            if isinstance(it, (tuple, list)):
                b, w = it
            else:
                b, w = it, 1
            b = b if b in (" ", ".") else B(b)
            self.items.append((b, int(w)))
        self.total = sum(w for _, w in self.items)
        if self.total <= 0:
            raise VillageError("mix 무게 합이 0")
        self.seed = seed

    def pick(self, x, y, z, salt=0):
        h = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ (salt * 2654435761) ^ (self.seed * 40503)
        h &= 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0x5BD1E995) & 0xFFFFFFFF
        h ^= h >> 15
        n = h % self.total
        for b, w in self.items:
            if n < w:
                return b
            n -= w
        return self.items[-1][0]


def mix(*items, seed=0):
    return Mix(items, seed)


# ─────────────────────────────── 연결 규칙 (바닐라 근사) ───────────────────────────────

def _panes():
    d = blockdata()["_props"]
    return {b for b in d if b == "glass_pane" or b.endswith("_stained_glass_pane") or b.endswith("_bars")}


_KIND_CACHE = {}


def _kind(bid):
    k = _KIND_CACHE.get(bid)
    if k is not None:
        return k
    if bid in tag("walls"):
        k = "wall"
    elif bid in tag("fences"):
        k = "fence"
    elif bid in _panes():
        k = "pane"
    elif bid in tag("fence_gates"):
        k = "gate"
    elif bid.endswith("_stairs"):
        k = "stairs"
    else:
        k = ""
    _KIND_CACHE[bid] = k
    return k


def _excepted(bid):
    """울타리·판유리·담장이 단단한 면이어도 붙지 않는 블록 (바닐라 isExceptionForConnection)."""
    return (bid in tag("leaves") or bid in tag("shulker_boxes")
            or bid in ("barrier", "carved_pumpkin", "jack_o_lantern", "melon", "pumpkin"))


def _sturdy(bid, props, face):
    """이웃 블록의 face 쪽 면이 꽉 찬 면인가 (isFaceSturdy 근사)."""
    if is_full(bid):
        return True
    if bid.endswith("_slab"):
        return props.get("type") == "double"
    if bid.endswith("_stairs"):
        f = props.get("facing")
        shape = props.get("shape", "straight")
        if shape.startswith("outer"):
            return False
        if face == f:
            return True
        if shape == "inner_left" and face == ccw(f):
            return True
        if shape == "inner_right" and face == cw(f):
            return True
    return False


def _covers_post(bid, props):
    """위 블록의 아랫면이 담장 기둥 자리를 덮는가 (담장 up 계산용)."""
    if is_full(bid) or bid in tag("wall_post_override"):
        return True
    if bid.endswith("_slab"):
        return props.get("type") in ("bottom", "double")
    if bid.endswith("_stairs"):
        return props.get("half") == "bottom"
    if _kind(bid) in ("wall", "fence", "pane"):
        return True
    if bid.endswith("lantern"):
        return props.get("hanging") == "false"
    if bid.endswith("candle") or bid.endswith("_carpet") or bid in ("campfire", "soul_campfire"):
        return True
    if bid.endswith("_chain"):
        return props.get("axis") == "y"
    if bid in ("end_rod", "lightning_rod") or bid.endswith("lightning_rod"):
        return props.get("facing") in ("up", "down")
    return False


# ─────────────────────────────── 조각 캔버스 ───────────────────────────────

FORBIDDEN = {
    "end_gateway": "엔드 관문", "end_portal": "엔드 포털", "nether_portal": "네더 포털", "tnt": "TNT",
    "spawner": "스포너", "trial_spawner": "시련 스포너", "hopper": "호퍼", "dispenser": "디스펜서",
    "dropper": "드로퍼", "crafter": "크래프터", "observer": "관찰자", "piston": "피스톤",
    "sticky_piston": "끈끈이 피스톤", "piston_head": "피스톤 머리", "moving_piston": "움직이는 피스톤",
    "comparator": "비교기", "repeater": "중계기", "redstone_wire": "레드스톤 가루",
    "daylight_detector": "햇빛 감지기", "sculk_sensor": "스컬크 감지체", "calibrated_sculk_sensor": "스컬크 감지체",
    "sculk_shrieker": "스컬크 비명체", "tripwire": "철사", "tripwire_hook": "철사 덫 갈고리",
    "command_block": "명령 블록", "chain_command_block": "명령 블록", "repeating_command_block": "명령 블록",
    "structure_block": "구조물 블록", "jigsaw": "직소 블록", "test_block": "테스트 블록",
    "test_instance_block": "테스트 블록", "bubble_column": "거품 기둥",
}
GRAVITY = {"sand", "red_sand", "gravel", "suspicious_sand", "suspicious_gravel", "anvil", "chipped_anvil",
           "damaged_anvil", "dragon_egg", "scaffolding"}
AMBIENT_FX = ("portal", "embers", "fountain", "magic", "smoke", "dust")
# 0.3.6 광산 마을: mine_lift(승강장) · smelter(제련소) · mine_info(숙소 게시판) · mine_office(광산 관리소 — 광산 청사진 쪽)
INTERACT_ACTIONS = ("entrance", "blacksmith", "class", "titles", "merchant", "main", "mine_lift", "mine_office", "smelter", "mine_info")
# 이름 붙은 서 있을 자리 마커 (spawn·entrance 처럼 발 칸 + face) — 0.3.6 mine_exit = 광산에서 마을로 나오는 자리
POINT_MARKERS = ("mine_exit",)
MARKER_FACES = ("front", "back", "left", "right")
ID_RE = re.compile(r"^[a-z0-9_]+$")

# 팔레트 글자 후보: ASCII 다음 BMP 글자들 (서로게이트 쌍 없음 → Java charAt 으로 읽어도 됨)
_POOL = ([c for c in "#abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"]
         + [c for c in "$%&*+-/:;<=>?@^_`|~!()[]{},'"]
         + [chr(c) for c in range(0xC0, 0x180) if c not in (0xD7, 0xF7)]
         + [chr(c) for c in range(0x391, 0x3CA) if c != 0x3A2]
         + [chr(c) for c in range(0x410, 0x450)])


class Piece:
    """정방향 조각 캔버스. 좌표는 0 ≤ x < W, 0 ≤ y < H, 0 ≤ z < D. 기본값은 ' ' (건드리지 않음)."""

    def __init__(self, id, name, W, H, D, floor_y=1, anchor=None, foundation_mix=None, foundation=None,
                 deco=None, door=None, slack=None):
        """deco = 장식 조각(slack 3, 정문 검사 생략; 비우면 id 접두어로 판단 — lamp_post·bench·tree_ …),
        door = False 면 정문 앞 걸어 들어가기 검사 생략 (문 없는 조각), slack = layout 기본 slack 대신 이 값."""
        if not ID_RE.match(id):
            raise VillageError("조각 id 는 소문자·숫자·_ 만: %r" % id)
        if min(W, H, D) < 1:
            raise VillageError("%s: 크기가 0 이하" % id)
        self.id, self.name = id, name
        self.W, self.H, self.D = W, H, D
        self.floor_y = floor_y
        self.anchor = tuple(anchor) if anchor else None
        mixl = foundation_mix or [("cobblestone", 3), ("mossy_cobblestone", 1), ("andesite", 1)]
        self.foundation_mix = [(check_block(B(b)), int(w)) for b, w in mixl]
        self.foundation = check_block(B(foundation)) if foundation else self.foundation_mix[0][0]
        self.deco, self.has_door, self.slack = deco, door, slack
        self.g = [[[" "] * W for _ in range(D)] for _ in range(H)]
        self.markers = []
        self.clip = False          # True 면 크기 밖 set 을 조용히 무시 (기본: 예외)
        self._salt = zlib.crc32(id.encode())
        self._final = None

    def __repr__(self):
        return "<Piece %s %dx%dx%d>" % (self.id, self.W, self.H, self.D)

    # ── 기본 칸 조작 ──
    def inside(self, x, y, z):
        return 0 <= x < self.W and 0 <= y < self.H and 0 <= z < self.D

    def _norm(self, block, x, y, z):
        if isinstance(block, Mix):
            block = block.pick(x, y, z, self._salt)
        if block in (" ", "."):
            return block
        if not isinstance(block, str):
            raise VillageError("%s: (%d,%d,%d) 블록 값이 문자열이 아닙니다: %r" % (self.id, x, y, z, block))
        if not block.startswith("minecraft:"):
            block = "minecraft:" + block
        try:
            return check_block(block)
        except VillageError as e:
            raise VillageError("%s: (%d,%d,%d) %s" % (self.id, x, y, z, e))

    def set(self, x, y, z, block):
        if not self.inside(x, y, z):
            if self.clip:
                return
            raise VillageError("%s: (%d,%d,%d) 가 조각 크기 %dx%dx%d 밖입니다" % (self.id, x, y, z, self.W, self.H, self.D))
        self.g[y][z][x] = self._norm(block, x, y, z)
        self._final = None

    def get(self, x, y, z):
        """칸 값 (' ', '.', 블록 문자열). 크기 밖이면 ' '."""
        if not self.inside(x, y, z):
            return " "
        return self.g[y][z][x]

    def is_set(self, x, y, z):
        return self.get(x, y, z) != " "

    def fill(self, x0, y0, z0, x1, y1, z1, block, only_empty=False):
        """상자 채우기 (양 끝 포함, 순서 무관). only_empty=True 면 ' ' 칸만."""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                for x in range(x0, x1 + 1):
                    if only_empty and self.get(x, y, z) != " ":
                        continue
                    self.set(x, y, z, block)

    def clear(self, x0, y0, z0, x1, y1, z1, only_empty=False):
        """'.'(공기여야 함)로 채우기 — 실내·통로는 꼭 이걸로 (공백이면 언덕 흙이 남을 수 있음)."""
        self.fill(x0, y0, z0, x1, y1, z1, ".", only_empty)

    def hollow_box(self, x0, y0, z0, x1, y1, z1, wall, floor=None, ceiling=None, inside="."):
        """벽 상자: 옆면 = wall, 바닥(y0) = floor(없으면 wall), 천장(y1) = ceiling(None 이면 안 덮음), 속 = inside."""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                for x in range(x0, x1 + 1):
                    edge = x in (x0, x1) or z in (z0, z1)
                    if y == y0:
                        b = floor if floor is not None else wall
                    elif y == y1 and ceiling is not None:
                        b = ceiling
                    elif edge:
                        b = wall
                    else:
                        b = inside
                    if b is not None:
                        self.set(x, y, z, b)

    def replace(self, x0, y0, z0, x1, y1, z1, old, new):
        """상자 안에서 old 를 new 로. old 는 블록 문자열·'.'·' ' 또는 함수(칸 값 → bool)."""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        if not callable(old):
            o = old if old in (" ", ".") else B(old)
            test = lambda v: v == o or (o.startswith("minecraft:") and "[" not in o and v.split("[")[0] == o)
        else:
            test = old
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                for x in range(x0, x1 + 1):
                    if self.inside(x, y, z) and test(self.g[y][z][x]):
                        self.set(x, y, z, new)

    def set_anchor(self, x, z):
        self.anchor = (x, z)

    # ── 두 칸짜리 블록 ──
    def door(self, mat, x, y, z, facing, hinge="left", open=False):
        """문 (아래 칸 y, 위 칸 y+1). facing = 문 밖으로 나가는 방향 (정면 벽 문은 'north')."""
        bid = _resolve(mat, "door")
        f = norm_dir(facing)
        self.set(x, y, z, B(bid, facing=f, half="lower", hinge=hinge, open=open, powered=False))
        self.set(x, y + 1, z, B(bid, facing=f, half="upper", hinge=hinge, open=open, powered=False))

    def bed(self, color, x, y, z, facing):
        """침대: (x,y,z) = 발치, 머리는 facing 쪽 옆 칸."""
        f = norm_dir(facing)
        dx, dz = DXZ[f]
        bid = color + "_bed"
        self.set(x, y, z, B(bid, facing=f, part="foot", occupied=False))
        self.set(x + dx, y, z + dz, B(bid, facing=f, part="head", occupied=False))

    def tall_plant(self, name, x, y, z):
        """큰 식물 두 칸 (rose_bush, peony, lilac, sunflower, tall_grass, large_fern …)."""
        self.set(x, y, z, B(name, half="lower"))
        self.set(x, y + 1, z, B(name, half="upper"))

    # ── 표지판·깃발 (블록 + 마커) ──
    @staticmethod
    def _rotation16(facing):
        if isinstance(facing, int):
            return facing % 16
        return {"south": 0, "west": 4, "north": 8, "east": 12}[norm_dir(facing)]

    def sign(self, x, y, z, lines, wood="oak", facing="north", wall=True, glow=False, back=None, hanging=False):
        """표지판 + 글 마커. facing = 글이 보이는 쪽. wall=True 면 벽 표지판(facing 반대쪽 칸에 붙음).
        hanging=True 면 매다는 표지판. lines 는 최대 4줄 MiniMessage."""
        w = _strip(wood)
        if hanging:
            if wall:
                blk = B(w + "_wall_hanging_sign", facing=norm_dir(facing))
            else:
                blk = B(w + "_hanging_sign", rotation=self._rotation16(facing), attached=False)
        elif wall:
            blk = B(w + "_wall_sign", facing=norm_dir(facing))
        else:
            blk = B(w + "_sign", rotation=self._rotation16(facing))
        self.set(x, y, z, blk)
        m = {"type": "sign", "pos": [x, y, z], "lines": list(lines), "glow": bool(glow)}
        if back:
            m["back"] = list(back)
        self.markers.append(m)

    def banner(self, x, y, z, color, patterns=(), facing="north", wall=True):
        """깃발 + 무늬 마커. patterns = [('border', 'black'), ('rhombus', 'yellow'), ...] (26.x 무늬 id)."""
        if wall:
            blk = B(color + "_wall_banner", facing=norm_dir(facing))
        else:
            blk = B(color + "_banner", rotation=self._rotation16(facing))
        self.set(x, y, z, blk)
        if patterns:
            self.markers.append({"type": "banner", "pos": [x, y, z], "patterns": [list(p) for p in patterns]})

    # ── 마커 ──
    @staticmethod
    def _face(face):
        f = str(face).lower()
        if f in MARKER_FACES:
            return f
        return _FACE_OF_DIR[norm_dir(f)]

    def npc(self, id, x, y, z, face="front"):
        """NPC 자리 (발이 놓이는 칸). id = npcs.yml id. face 는 front/back/left/right (front=북)."""
        self.markers.append({"type": "npc", "id": id, "pos": [x, y, z], "face": self._face(face)})

    def entrance(self, x, y, z, face="front"):
        self.markers.append({"type": "entrance", "pos": [x, y, z], "face": self._face(face)})

    def spawn(self, x, y, z, face="front"):
        self.markers.append({"type": "spawn", "pos": [x, y, z], "face": self._face(face)})

    def point(self, kind, x, y, z, face="front"):
        """이름 붙은 서 있을 자리 (POINT_MARKERS — 예: mine_exit = 광산에서 마을로 나오는 자리)."""
        self.markers.append({"type": kind, "pos": [x, y, z], "face": self._face(face)})

    def interact(self, action, positions):
        """우클릭 → 메뉴. positions = [(x,y,z), ...] (그 블록들)."""
        self.markers.append({"type": "interact", "action": action, "pos": [list(p) for p in positions]})

    def ambient(self, x, y, z, fx):
        self.markers.append({"type": "ambient", "pos": [x, y, z], "fx": fx})

    def light(self, x, y, z):
        self.markers.append({"type": "light", "pos": [x, y, z]})

    # ── 모양 도우미 ──
    def gable_roof(self, x0, z0, x1, z1, y, mat, axis="x", overhang=1, end_overhang=1, under="stairs",
                   gable=None, ridge="slab", hollow=True):
        """박공 지붕. (x0,z0)-(x1,z1) = 지붕을 얹을 벽의 바깥 테두리, y = 첫 처마 줄 높이(보통 벽 꼭대기 + 1).
        axis='x' 면 용마루가 x 방향(경사면이 북·남), 'z' 면 용마루가 z 방향(경사면이 동·서).
        overhang = 경사면 쪽 처마 돌출, end_overhang = 박공 쪽 돌출.
        under = 'stairs'(뒤집힌 계단으로 지붕 두께·안쪽 경사 천장) | 'block' | None.
        gable = 박공벽 삼각형 채움 블록 (None 이면 비워 둠 — 직접 꾸밀 때; Mix 가능).
        ridge = 'slab'(홀수 폭일 때 용마루 반블록) | None | 블록 문자열(용마루 장식, 짝수 폭이면 두 줄).
        hollow = 지붕 속 빈칸(벽 안쪽)을 '.' 로. 굴뚝처럼 지붕을 뚫는 것은 지붕 다음에 그린다.
        돌려줌: 가장 높은 지붕 블록의 y."""
        x0, x1 = sorted((x0, x1))
        z0, z1 = sorted((z0, z1))
        if axis == "x":
            a_lo, a_hi, c_lo, c_hi = x0 - end_overhang, x1 + end_overhang, z0 - overhang, z1 + overhang
            f_lo, f_hi = "south", "north"
            put = lambda a, yy, c, b: self.set(a, yy, c, b)
            peek = lambda a, yy, c: self.get(a, yy, c)
            gable_a, inner = (x0, x1), (x0 + 1, x1 - 1)
        else:
            a_lo, a_hi, c_lo, c_hi = z0 - end_overhang, z1 + end_overhang, x0 - overhang, x1 + overhang
            f_lo, f_hi = "east", "west"
            put = lambda a, yy, c, b: self.set(c, yy, a, b)
            peek = lambda a, yy, c: self.get(c, yy, a)
            gable_a, inner = (z0, z1), (z0 + 1, z1 - 1)
        base = planks(mat)
        u_lo = stairs(mat, f_hi, "top") if under == "stairs" else (base if under else None)
        u_hi = stairs(mat, f_lo, "top") if under == "stairs" else (base if under else None)
        levels = []
        k, top = 0, y
        while c_lo + k <= c_hi - k:
            lo, hi, yy = c_lo + k, c_hi - k, y + k
            for a in range(a_lo, a_hi + 1):
                if lo < hi:
                    put(a, yy, lo, stairs(mat, f_lo))
                    put(a, yy, hi, stairs(mat, f_hi))
                    if k > 0 and u_lo:
                        put(a, yy - 1, lo, u_lo)
                        put(a, yy - 1, hi, u_hi)
                else:                                   # 홀수 폭 꼭대기 한 줄
                    if k > 0:
                        put(a, yy - 1, lo, base)
                    if ridge == "slab":
                        put(a, yy, lo, slab(mat))
                    elif ridge:
                        put(a, yy, lo, ridge)
            levels.append((yy, lo, hi))
            top = yy
            k += 1
        if (c_hi - c_lo) % 2 == 1 and ridge not in (None, "slab"):   # 짝수 폭: 장식 용마루는 두 줄 위에
            lo, hi = c_lo + k - 1, c_hi - k + 1
            for a in range(a_lo, a_hi + 1):
                put(a, top + 1, lo, ridge)
                put(a, top + 1, hi, ridge)
            top += 1
        for yy, lo, hi in levels:                       # 박공벽·지붕 속
            for c in range(lo + 1, hi):
                for a in gable_a:
                    if gable is not None and peek(a, yy, c) == " ":
                        put(a, yy, c, gable)
                if hollow:
                    for a in range(inner[0], inner[1] + 1):
                        if peek(a, yy, c) == " ":
                            put(a, yy, c, ".")
        return top

    def hip_roof(self, x0, z0, x1, z1, y, mat, overhang=1, under="stairs", ridge="slab", hollow=True):
        """모임 지붕 (네 면 경사). 인자는 gable_roof 와 같음. 모서리 계단 모양은 finalize 가 계산."""
        x0, x1 = sorted((x0, x1))
        z0, z1 = sorted((z0, z1))
        xs, xe, zs, ze = x0 - overhang, x1 + overhang, z0 - overhang, z1 + overhang
        base = planks(mat)
        k, top = 0, y
        rings = []
        while xs + k <= xe - k and zs + k <= ze - k:
            ax0, ax1, az0, az1, yy = xs + k, xe - k, zs + k, ze - k, y + k
            if ax0 == ax1 or az0 == az1:                # 한 줄(또는 한 칸) → 용마루
                for x in range(ax0, ax1 + 1):
                    for z in range(az0, az1 + 1):
                        if k > 0:
                            self.set(x, yy - 1, z, base)
                        if ridge == "slab":
                            self.set(x, yy, z, slab(mat))
                        elif ridge:
                            self.set(x, yy, z, ridge)
                top = yy
                break
            for x in range(ax0, ax1 + 1):
                for z in range(az0, az1 + 1):
                    if not (x in (ax0, ax1) or z in (az0, az1)):
                        continue
                    if z == az0:
                        f = "south"
                    elif z == az1:
                        f = "north"
                    elif x == ax0:
                        f = "east"
                    else:
                        f = "west"
                    self.set(x, yy, z, stairs(mat, f))
                    if k > 0 and under:
                        self.set(x, yy - 1, z, stairs(mat, opposite(f), "top") if under == "stairs" else base)
            rings.append((yy, ax0, ax1, az0, az1))
            top = yy
            k += 1
        if hollow:
            for yy, ax0, ax1, az0, az1 in rings:
                for x in range(max(ax0 + 1, x0 + 1), min(ax1, x1)):
                    for z in range(max(az0 + 1, z0 + 1), min(az1, z1)):
                        if self.get(x, yy, z) == " ":
                            self.set(x, yy, z, ".")
        return top

    def spire(self, cx, cz, y, r, height, mat, round=True, hollow=True, tip=None, block=None):
        """첨탑/원뿔 지붕. 중심 (cx, cz), 밑면 반지름 r, 밑면 높이 y 에서 꼭대기까지 height 칸.
        round=True 면 원뿔, False 면 사각뿔. 겉 = 계단(경사) + 꽉 찬 블록(가파른 옆면, block 기본 = 그 재료).
        tip = 꼭대기 위 장식 (예: 'lightning_rod', end_rod(), 'gold_block'). 돌려줌: 꼭대기 y."""
        base = block or planks(mat)
        tops = {}
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if round:
                    if dx * dx + dz * dz > r * r + r:
                        continue
                    d = min(math.sqrt(dx * dx + dz * dz), r)
                else:
                    d = max(abs(dx), abs(dz))
                tops[(dx, dz)] = int(math.floor((r - d) / float(max(r, 1)) * height + 0.5)) if r else height
        for (dx, dz), t in tops.items():
            x, z = cx + dx, cz + dz
            nb = {d: tops.get((dx + DXZ[d][0], dz + DXZ[d][1]), -1) for d in DIRS}
            for lv in range(t):
                exposed = any(v <= lv for v in nb.values())
                if exposed:
                    self.set(x, y + lv, z, base)
                elif hollow:
                    if self.get(x, y + lv, z) == " ":
                        self.set(x, y + lv, z, ".")
                else:
                    self.set(x, y + lv, z, base)
            low = min(nb.values())
            if low < t:
                # 가장 낮은 이웃 쪽에서 올라오는 계단 (같으면 중심에서 먼 축 우선)
                cands = [d for d in DIRS if nb[d] == low]
                cands.sort(key=lambda d: -abs(DXZ[d][0] * dx + DXZ[d][1] * dz))
                self.set(x, y + t, z, stairs(mat, opposite(cands[0])))
            else:
                self.set(x, y + t, z, base)
        apex = y + tops.get((0, 0), 0)
        if tip:
            self.set(cx, apex + 1, cz, tip)
            apex += 1
        return apex

    def arch(self, a0, a1, y0, height, w0, w1=None, mat="stone_bricks", axis="x", style="round", frame=None):
        """벽에 아치 구멍. axis='x' 면 벽이 x 방향(구멍 폭 = x a0..a1, 벽 두께 = z w0..w1),
        'z' 면 구멍 폭 = z a0..a1, 두께 = x w0..w1. y0 = 구멍 바닥, height = 구멍 전체 높이(아치 꼭대기 포함).
        곡선 가장자리는 mat 의 뒤집힌 계단·윗 반블록으로 다듬는다. style = 'round' | 'pointed'.
        frame = 구멍 둘레 테두리 블록 (None 이면 기존 벽 그대로)."""
        a0, a1 = sorted((a0, a1))
        w1 = w0 if w1 is None else w1
        w0, w1 = sorted((w0, w1))
        w = a1 - a0 + 1
        if style == "pointed":
            rr = float(w)
            vs = height - rr * math.sqrt(3) / 2.0

            def inside(u, v):
                return v <= vs or ((u - w) ** 2 + (v - vs) ** 2 <= rr * rr and u * u + (v - vs) ** 2 <= rr * rr)
        else:
            rr = w / 2.0
            vs = height - rr

            def inside(u, v):
                return v <= vs or (u - rr) ** 2 + (v - vs) ** 2 <= rr * rr

        low_side, high_side = ("west", "east") if axis == "x" else ("north", "south")
        put = (lambda a, yy, d, b: self.set(a, yy, d, b)) if axis == "x" else (lambda a, yy, d, b: self.set(d, yy, a, b))
        state = {}
        for i in range(w):
            for j in range(height + 1):
                q = [inside(i + du, j + dv) for du, dv in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))]
                bl, br, tl, tr = q
                n = sum(q)
                if j >= height and n == 0:
                    continue
                if n >= 3 or (n == 2 and not (bl and br)):
                    state[(i, j)] = "."
                elif n == 2:
                    state[(i, j)] = slab(mat, "top")
                elif n == 1 and br:
                    state[(i, j)] = stairs(mat, low_side, "top")
                elif n == 1 and bl:
                    state[(i, j)] = stairs(mat, high_side, "top")
        opening = {k for k in state}
        for (i, j), b in state.items():
            for d in range(w0, w1 + 1):
                put(a0 + i, y0 + j, d, b)
        if frame is not None:
            ring = set()
            for (i, j) in opening:
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        k2 = (i + di, j + dj)
                        if k2 not in opening and k2[1] >= 0:
                            ring.add(k2)
            for (i, j) in ring:
                for d in range(w0, w1 + 1):
                    put(a0 + i, y0 + j, d, frame)

    def disc(self, cx, cz, y, r, block, ring=False):
        """원판 (ring=True 면 테두리만). 반지름 r 칸 — 바닐라 빌더들이 쓰는 매끈한 원 근사."""
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if not _in_circle(dx, dz, r):
                    continue
                if ring and all(_in_circle(dx + ex, dz + ez, r) for ex, ez in DXZ.values()):
                    continue
                self.set(cx + dx, y, cz + dz, block)

    def cylinder(self, cx, cz, y0, y1, r, block, hollow=False, inside="."):
        """원기둥 (hollow=True 면 벽만, 속은 inside)."""
        for y in range(min(y0, y1), max(y0, y1) + 1):
            if hollow:
                self.disc(cx, cz, y, r, block, ring=True)
                if inside is not None and r > 1:
                    for dx in range(-r, r + 1):
                        for dz in range(-r, r + 1):
                            if _in_circle(dx, dz, r) and all(_in_circle(dx + ex, dz + ez, r) for ex, ez in DXZ.values()):
                                self.set(cx + dx, y, cz + dz, inside)
            else:
                self.disc(cx, cz, y, r, block)

    def timber_wall(self, x0, y0, z0, x1, y1, z1, frame="dark_oak_log", infill="white_terracotta",
                    post_every=3, beams=True, mid_beam=None):
        """원목 뼈대 벽 (한 평면: x0==x1 이거나 z0==z1). 기둥(세로 원목)은 양 끝과 post_every 칸마다,
        가로보(가로 원목)는 아래·위 줄(beams=True)과 mid_beam 높이에. 나머지는 infill (Mix 가능)."""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        if x0 != x1 and z0 != z1:
            raise VillageError("%s: timber_wall 은 한 평면이어야 합니다 (x0==x1 또는 z0==z1)" % self.id)
        along_x = z0 == z1 and x0 != x1
        a0, a1 = (x0, x1) if along_x else (z0, z1)
        has_axis = "axis" in blockdata()["_props"].get(parse_block(B(frame))[0], {})
        post_b = log(frame, "y") if has_axis else B(frame)
        beam_b = log(frame, "x" if along_x else "z") if has_axis else B(frame)
        posts = {a0, a1} | set(range(a0, a1 + 1, max(1, post_every)))
        rows = set()
        if beams:
            rows |= {y0, y1}
        if mid_beam is not None:
            rows.add(mid_beam)
        for a in range(a0, a1 + 1):
            for y in range(y0, y1 + 1):
                x, z = (a, z0) if along_x else (x0, a)
                if a in posts:
                    b = post_b
                elif y in rows:
                    b = beam_b
                else:
                    b = infill
                self.set(x, y, z, b)

    def window(self, x, y, z, facing, w=1, h=2, glass="light_blue_stained_glass_pane", shutter=None,
               sill=None, lintel=None):
        """창. (x,y,z) = 창 구멍의 아래 왼쪽 칸 (북/남 벽은 +x 로, 동/서 벽은 +z 로 w 칸), 높이 h.
        facing = 창 바깥 방향. glass = 판유리 (pane('cyan') 등). shutter = 덧문 나무 ('spruce') → 바깥 양옆에 열린 다락문.
        sill = 창턱: True(덧문 나무의 뒤집힌 계단) 또는 블록 문자열 → 바깥 아래 줄. lintel = 창 위 벽 줄 블록."""
        f = norm_dir(facing)
        sx, sz = (1, 0) if f in ("north", "south") else (0, 1)
        ox, oz = DXZ[f]
        g = B(glass) if not glass.startswith("minecraft:") else glass
        for i in range(w):
            for j in range(h):
                self.set(x + sx * i, y + j, z + sz * i, g)
        if shutter:
            t = trapdoor(shutter, f, "bottom", open=True)
            for j in range(h):
                for i in (-1, w):
                    self.set(x + sx * i + ox, y + j, z + sz * i + oz, t)
        if sill:
            sb = stairs(shutter or "spruce", opposite(f), "top") if sill is True else sill
            for i in range(w):
                self.set(x + sx * i + ox, y - 1, z + sz * i + oz, sb)
        if lintel:
            for i in range(w):
                self.set(x + sx * i, y + h, z + sz * i, lintel)

    def chimney(self, x, z, y0, y1, block="bricks", cap="campfire"):
        """굴뚝 기둥 (y0..y1) + 꼭대기 cap: 'campfire'(연기) | 'soul_campfire' | 블록 문자열 | None.
        지붕을 뚫는 굴뚝은 지붕을 그린 다음에 부른다."""
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self.set(x, y, z, block)
        top = max(y0, y1) + 1
        if cap == "campfire":
            self.set(x, top, z, campfire())
        elif cap == "soul_campfire":
            self.set(x, top, z, campfire(soul=True))
        elif cap:
            self.set(x, top, z, cap)

    def column(self, x, z, y0, y1, shaft="quartz_pillar", base=None, capital=None, flare=None):
        """기둥: base(y0) + shaft + capital(y1). shaft 가 축 블록(원목·기둥)이면 axis=y.
        flare = 계단 재료 → 밑둥·머리 사방에 계단을 둘러 굵게 (사방 한 칸이 필요)."""
        y0, y1 = sorted((y0, y1))
        sb = B(shaft)
        if "axis" in blockdata()["_props"].get(parse_block(sb)[0], {}):
            sb = B(sb, axis="y")
        for y in range(y0, y1 + 1):
            self.set(x, y, z, sb)
        if base:
            self.set(x, y0, z, base)
        if capital:
            self.set(x, y1, z, capital)
        if flare:
            for d in DIRS:
                dx, dz = DXZ[d]
                self.set(x + dx, y0, z + dz, stairs(flare, opposite(d), "bottom"))
                self.set(x + dx, y1, z + dz, stairs(flare, opposite(d), "top"))

    def staircase(self, x, y, z, facing, n, mat, width=1, down=False, headroom=3, support=None):
        """계단 길. (x,y,z) 첫 칸에서 facing 쪽으로 n 칸, 한 칸에 1 씩 오름(down=True 면 내려감).
        width 는 facing 의 오른쪽(시계 방향)으로 넓힘. headroom 칸만큼 위를 '.' 로 비우고, support 블록을 아래에."""
        f = norm_dir(facing)
        dx, dz = DXZ[f]
        rx, rz = DXZ[cw(f)]
        sf = opposite(f) if down else f
        for i in range(n):
            yy = y - i if down else y + i
            for wcol in range(width):
                px, pz = x + dx * i + rx * wcol, z + dz * i + rz * wcol
                self.set(px, yy, pz, stairs(mat, sf))
                for hgt in range(1, headroom + 1):
                    if self.inside(px, yy + hgt, pz) and self.get(px, yy + hgt, pz) in (" ", "."):
                        self.set(px, yy + hgt, pz, ".")
                if support and self.inside(px, yy - 1, pz):
                    self.set(px, yy - 1, pz, support)

    # ── 마무리: 연결 상태 → 기본값 → 검증 → 팔레트 ──
    def _cell(self, x, y, z):
        """(id, props) 또는 None (공백·공기·크기 밖)."""
        if not self.inside(x, y, z):
            return None
        v = self.g[y][z][x]
        if v in (" ", "."):
            return None
        return parse_block(v)

    def _compute_states(self):
        W, H, D = self.W, self.H, self.D
        g = self.g
        # ① 계단 모양 (shape 를 비운 계단만)
        todo = []
        for y in range(H):
            for z in range(D):
                for x in range(W):
                    v = g[y][z][x]
                    if v in (" ", ".") or "_stairs" not in v:
                        continue
                    bid, pr = parse_block(v)
                    if bid.endswith("_stairs") and "shape" not in pr:
                        todo.append((x, y, z, bid, pr))
        shapes = {}
        for x, y, z, bid, pr in todo:
            shapes[(x, y, z)] = self._stair_shape(x, y, z, pr.get("facing", "north"), pr.get("half", "bottom"))
        for x, y, z, bid, pr in todo:
            pr["shape"] = shapes[(x, y, z)]
            g[y][z][x] = format_block(bid, pr)
        # ② 울타리·판유리·철창·담장 연결 (연결 속성이 하나라도 빠진 것만)
        walls = []
        for y in range(H):
            for z in range(D):
                for x in range(W):
                    v = g[y][z][x]
                    if v in (" ", "."):
                        continue
                    bid, pr = parse_block(v)
                    k = _kind(bid)
                    if k not in ("fence", "pane", "wall"):
                        continue
                    if all(d in pr for d in DIRS):
                        continue
                    for d in DIRS:
                        if d in pr:
                            continue
                        nb = self._cell(x + DXZ[d][0], y, z + DXZ[d][1])
                        c = self._connects(k, bid, nb, d)
                        pr[d] = ("true" if c else "false") if k != "wall" else ("low" if c else "none")
                    g[y][z][x] = format_block(bid, pr)
                    if k == "wall" and "up" not in pr:
                        walls.append((x, y, z))
        # ③ 담장 높이(low/tall)·기둥(up) — 위에서 아래로 (위 담장의 up 을 먼저 정함)
        for x, y, z in sorted(walls, key=lambda t: -t[1]):
            bid, pr = parse_block(g[y][z][x])
            above = self._cell(x, y + 1, z)
            for d in DIRS:
                if pr[d] == "none":
                    continue
                tall = False
                if above:
                    aid, ap = above
                    ak = _kind(aid)
                    if is_full(aid):
                        tall = True
                    elif ak == "wall":
                        tall = ap.get(d, "none") != "none"
                    elif ak in ("fence", "pane"):
                        tall = ap.get(d) == "true"
                pr[d] = "tall" if tall else "low"
            pr["up"] = "true" if self._wall_up(pr, above) else "false"
            g[y][z][x] = format_block(bid, pr)
        # ④ 나머지 속성 기본값
        for y in range(H):
            for z in range(D):
                for x in range(W):
                    v = g[y][z][x]
                    if v not in (" ", "."):
                        g[y][z][x] = fill_defaults(v)

    def _stair_shape(self, x, y, z, f, half):
        def st(d):
            c = self._cell(x + DXZ[d][0], y, z + DXZ[d][1])
            if c and c[0].endswith("_stairs"):
                return c[1]
            return None

        def can_take(face):
            n = st(face)
            return n is None or n.get("facing") != f or n.get("half", "bottom") != half

        front = st(f)
        if front and front.get("half", "bottom") == half:
            f2 = front.get("facing")
            if f2 in AXIS and AXIS[f2] != AXIS[f] and can_take(opposite(f2)):
                return "outer_left" if f2 == ccw(f) else "outer_right"
        back = st(opposite(f))
        if back and back.get("half", "bottom") == half:
            f3 = back.get("facing")
            if f3 in AXIS and AXIS[f3] != AXIS[f] and can_take(f3):
                return "inner_left" if f3 == ccw(f) else "inner_right"
        return "straight"

    @staticmethod
    def _connects(kind, bid, nb, d):
        if nb is None:
            return False
        nid, np_ = nb
        nk = _kind(nid)
        face = opposite(d)
        if nk == "gate":
            gate_ok = AXIS.get(np_.get("facing", "north")) != AXIS[d]
        else:
            gate_ok = False
        solid = not _excepted(nid) and _sturdy(nid, np_, face)
        if kind == "fence":
            same = nk == "fence" and ((nid in tag("wooden_fences")) == (bid in tag("wooden_fences")))
            return solid or same or gate_ok
        if kind == "pane":
            return solid or nk == "pane" or nk == "wall"
        # wall
        return nk == "wall" or solid or nk == "pane" or gate_ok

    @staticmethod
    def _wall_up(pr, above):
        if above and _kind(above[0]) == "wall" and above[1].get("up") == "true":
            return True
        n, e, s, w = (pr[d] for d in DIRS)
        if all(v == "none" for v in (n, e, s, w)) or (n == "none") != (s == "none") or (e == "none") != (w == "none"):
            return True
        if (n == "tall" and s == "tall") or (e == "tall" and w == "tall"):
            return False
        return bool(above) and _covers_post(above[0], above[1])

    def finalize(self):
        """연결 상태·계단 모양·기본 속성 채우기 → 검증 → 팔레트. 실패하면 VillageError (이유 목록)."""
        self._compute_states()
        self.validate()
        self._final = self._build_palette()
        return self

    def _solid_at(self, x, y, z):
        c = self._cell(x, y, z)
        return bool(c) and is_full(c[0])

    def validate(self):
        """VILLAGE.md §2 검증. 실패는 VillageError (여러 건을 한 번에)."""
        errs = []
        W, H, D = self.W, self.H, self.D
        if not (0 <= self.floor_y < H):
            errs.append("floor_y=%d 가 0..%d 밖" % (self.floor_y, H - 1))
        if not self.anchor:
            errs.append("anchor 가 없습니다 (Piece(..., anchor=(x, z)) — 보통 정문 바로 안쪽 바닥)")
        else:
            ax, az = self.anchor
            if not (0 <= ax < W and 0 <= az < D):
                errs.append("anchor %s 가 크기 밖" % (self.anchor,))
            elif 0 <= self.floor_y < H and self.g[self.floor_y][az][ax] in (" ", "."):
                errs.append("anchor %s 의 바닥 층(y=%d) 칸이 비어 있습니다 — 바닥 블록 위에 둬야 함" % (self.anchor, self.floor_y))
        g = self.g
        lit_off = {"furnace", "blast_furnace", "smoker"}
        for y in range(H):
            for z in range(D):
                for x in range(W):
                    v = g[y][z][x]
                    if v in (" ", "."):
                        continue
                    at = "(%d,%d,%d) %s" % (x, y, z, v)
                    try:
                        check_block(v)
                    except VillageError as e:
                        errs.append("%s: %s" % (at, e))
                        continue
                    bid, pr = parse_block(v)
                    spec = blockdata()["_props"][bid]
                    missing = [k for k in spec if k not in pr]
                    if missing:
                        errs.append("%s: 속성 %s 가 빠짐 (finalize 를 불렀나요?)" % (at, ",".join(missing)))
                    if bid in FORBIDDEN:
                        errs.append("%s: 금지 블록 (%s)" % (at, FORBIDDEN[bid]))
                    elif bid in tag("shulker_boxes"):
                        errs.append("%s: 금지 블록 (셜커 상자)" % at)
                    if bid in lit_off and pr.get("lit") == "true":
                        errs.append("%s: lit=true 화로류는 블록 엔티티가 바로 끔 — 등불·모닥불을 쓰세요" % at)
                    if bid == "redstone_lamp" and pr.get("lit") == "true":
                        errs.append("%s: 신호 없는 레드스톤 램프는 꺼짐" % at)
                    if bid == "brewing_stand" and "true" in (pr.get("has_bottle_0"), pr.get("has_bottle_1"), pr.get("has_bottle_2")):
                        errs.append("%s: 양조대 has_bottle 은 블록 엔티티(빈 칸)가 매 틱 false 로 되돌림 — 병 없이 두세요" % at)
                    if bid in tag("leaves") and pr.get("persistent") != "true":
                        errs.append("%s: 잎은 persistent=true 여야 합니다 (leaves() 를 쓰세요)" % at)
                    if bid in ("water", "lava"):
                        if pr.get("level") != "0":
                            errs.append("%s: 흐르는 %s 금지 (level=0 source 만)" % (at, bid))
                        for (ex, ey, ez) in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
                            nb = self.get(x + ex, y + ey, z + ez)
                            # 공기·미정(' ')·풀처럼 대체되는 블록이면 물이 흘러 나감
                            if nb in (" ", ".") or (parse_block(nb)[0] != bid and parse_block(nb)[0] in tag("replaceable")):
                                errs.append("%s: %s 가 사방·아래가 막힌 웅덩이 안이 아닙니다 (옆 %s)"
                                            % (at, bid, (x + ex, y + ey, z + ez)))
                                break
                    if bid in ("fire", "soul_fire"):
                        below = self._cell(x, y - 1, z)
                        okb = {"fire": ("netherrack", "magma_block"), "soul_fire": ("soul_sand", "soul_soil")}[bid]
                        if not below or below[0] not in okb:
                            errs.append("%s: 불은 %s 위에서만 꺼지지 않음 — 모닥불을 쓰세요" % (at, "/".join(okb)))
                    if (bid in GRAVITY or bid.endswith("_concrete_powder")) and self.get(x, y - 1, z) == ".":
                        errs.append("%s: 아래가 비어 떨어지는 블록" % at)
                    # 두 칸짜리 짝
                    if "half" in spec and set(spec["half"][0]) == {"upper", "lower"}:
                        dy = 1 if pr.get("half") == "lower" else -1
                        mate = self._cell(x, y + dy, z)
                        want = dict(pr, half="upper" if dy == 1 else "lower")
                        if not mate or mate[0] != bid or any(mate[1].get(k) != want[k] for k in want):
                            errs.append("%s: 두 칸 블록의 짝(%s 칸)이 맞지 않음 — door()/tall_plant() 를 쓰세요"
                                        % (at, "위" if dy == 1 else "아래"))
                    if bid.endswith("_bed"):
                        f = pr.get("facing", "north")
                        sgn = 1 if pr.get("part") == "foot" else -1
                        mx, mz = x + DXZ[f][0] * sgn, z + DXZ[f][1] * sgn
                        mate = self._cell(mx, y, mz)
                        if (not mate or mate[0] != bid or mate[1].get("facing") != f
                                or mate[1].get("part") == pr.get("part")):
                            errs.append("%s: 침대 짝이 (%d,%d,%d) 에 없음 — bed() 를 쓰세요" % (at, mx, y, mz))
                    # 붙어 있어야 하는 블록 (받침 칸이 '.' 이면 확실히 떨어짐)
                    sup = self._support(bid, pr)
                    if sup is not None:
                        sx, sy, sz = x + sup[0], y + sup[1], z + sup[2]
                        if self.get(sx, sy, sz) == ".":
                            errs.append("%s: 붙을 곳 (%d,%d,%d) 이 공기 — 물리 업데이트 때 떨어짐" % (at, sx, sy, sz))
        errs += self._enclosed_blanks()
        errs += self._validate_markers()
        if errs:
            more = "" if len(errs) <= 40 else "\n  … 그 밖 %d건" % (len(errs) - 40)
            raise VillageError("%s: 청사진 검증 실패 %d건\n  - %s%s" % (self.id, len(errs), "\n  - ".join(errs[:40]), more))

    def _enclosed_blanks(self):
        """바닥 위 ' ' 칸 중 조각 바깥(옆면·윗면)과 빈칸으로 이어지지 않은 칸 = 닫힌 실내인데 '.' 를 안 채움."""
        W, H, D, g = self.W, self.H, self.D, self.g
        y0 = self.floor_y + 1
        seen = set()
        stack = []
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
                if n in seen or not (0 <= n[0] < W and y0 <= n[1] < H and 0 <= n[2] < D):
                    continue
                if g[n[1]][n[2]][n[0]] in (" ", "."):
                    seen.add(n)
                    stack.append(n)
        bad = [(x, y, z) for y in range(y0, H) for z in range(D) for x in range(W)
               if g[y][z][x] == " " and (x, y, z) not in seen]
        if not bad:
            return []
        return ["닫힌 실내 빈칸 %d개가 ' ' (예: %s) — clear()/'.' 로 채우세요 (§2.2: 공백이면 언덕 흙이 남을 수 있음)"
                % (len(bad), bad[0])]

    @staticmethod
    def _support(bid, pr):
        """받침이 필요한 블록이면 받침 칸 상대 좌표, 아니면 None."""
        f = pr.get("facing")
        if bid.endswith("_wall_sign") or bid.endswith("_wall_banner") or bid.endswith("wall_torch") or bid == "ladder":
            if f in DXZ:
                ox, oz = DXZ[opposite(f)]
                return (ox, 0, oz)
        if bid.endswith("lantern") and "hanging" in pr:
            return (0, 1, 0) if pr["hanging"] == "true" else (0, -1, 0)
        if bid.endswith("_wall_hanging_sign"):
            return None                       # 옆(facing 의 시계·반시계 쪽) 블록에 붙음 — 어느 쪽인지 몰라 검사 생략
        if bid.endswith("_hanging_sign"):
            return (0, 1, 0)
        if bid.endswith("_door") and pr.get("half") == "lower":
            return (0, -1, 0)
        if (bid.endswith("_sign") or bid.endswith("_banner") or bid.endswith("torch") or bid.endswith("candle")
                or bid.endswith("_carpet") or bid.endswith("pressure_plate") or bid.endswith("rail")):
            return (0, -1, 0)
        shp = blockdata()["shapes"].get(bid)
        if shp and shp[6] == "cross" and not bid.startswith("potted_") and pr.get("half") != "upper" \
                and bid not in ("cobweb", "hanging_roots", "pale_hanging_moss", "weeping_vines", "weeping_vines_plant",
                                "cave_vines", "cave_vines_plant") and not bid.endswith("amethyst_bud") \
                and bid != "amethyst_cluster":
            return (0, -1, 0)
        return None

    def _validate_markers(self):
        errs = []
        npc_ids = set()

        def chk_pos(m, p):
            if not (isinstance(p, (list, tuple)) and len(p) == 3 and all(isinstance(v, int) for v in p)):
                errs.append("마커 %s: pos 는 [x,y,z] 정수" % m["type"])
                return False
            if not self.inside(*p):
                errs.append("마커 %s %s: 조각 크기 밖" % (m["type"], p))
                return False
            return True

        for m in self.markers:
            t = m.get("type")
            if t in ("npc", "entrance", "spawn") + POINT_MARKERS:
                if not chk_pos(m, m["pos"]):
                    continue
                if m.get("face") not in MARKER_FACES:
                    errs.append("마커 %s: face 는 front/back/left/right" % t)
                x, y, z = m["pos"]
                if self._solid_at(x, y, z) or self._solid_at(x, y + 1, z):
                    errs.append("마커 %s %s: 서 있을 칸(발·머리)이 막혀 있음" % (t, m["pos"]))
                below = self.get(x, y - 1, z)
                if y == 0 or below == ".":
                    errs.append("마커 %s %s: 발밑 (%d,%d,%d) 이 비어 있음" % (t, m["pos"], x, y - 1, z))
                if t == "npc":
                    if not ID_RE.match(str(m.get("id", ""))):
                        errs.append("npc 마커 id 가 이상함: %r" % m.get("id"))
                    if m.get("id") in npc_ids:
                        errs.append("npc %s 가 두 번" % m.get("id"))
                    npc_ids.add(m.get("id"))
            elif t == "interact":
                if m.get("action") not in INTERACT_ACTIONS:
                    errs.append("interact action 은 %s 중 하나: %r" % ("/".join(INTERACT_ACTIONS), m.get("action")))
                if not m["pos"]:
                    errs.append("interact %s: 칸이 없음" % m.get("action"))
                for p in m["pos"]:
                    if chk_pos(m, p) and self.get(*p) in (" ", "."):
                        errs.append("interact %s %s: 그 칸에 블록이 없음 (우클릭할 블록이어야 함)" % (m["action"], p))
            elif t == "sign":
                if chk_pos(m, m["pos"]):
                    c = self._cell(*m["pos"])
                    if not c or not c[0].endswith("_sign"):
                        errs.append("sign 마커 %s: 그 칸 블록이 표지판이 아님" % (m["pos"],))
                if not (1 <= len(m.get("lines", [])) <= 4):
                    errs.append("sign 마커 %s: lines 는 1~4줄" % (m["pos"],))
                if "back" in m and len(m["back"]) > 4:
                    errs.append("sign 마커 %s: back 은 최대 4줄" % (m["pos"],))
            elif t == "banner":
                if chk_pos(m, m["pos"]):
                    c = self._cell(*m["pos"])
                    if not c or not c[0].endswith("_banner"):
                        errs.append("banner 마커 %s: 그 칸 블록이 깃발이 아님" % (m["pos"],))
                for pat in m.get("patterns", []):
                    if len(pat) != 2 or pat[0] not in blockdata()["_patterns"] or pat[1] not in DYES:
                        errs.append("banner 무늬 %r: [무늬 id, 염료 색] (무늬: %s …)" % (pat, ", ".join(sorted(blockdata()["_patterns"])[:8])))
                if len(m.get("patterns", [])) > 16:
                    errs.append("banner 무늬가 16개 넘음")
            elif t == "ambient":
                chk_pos(m, m["pos"])
                if m.get("fx") not in AMBIENT_FX:
                    errs.append("ambient fx 는 %s 중 하나: %r" % ("/".join(AMBIENT_FX), m.get("fx")))
            elif t == "light":
                chk_pos(m, m["pos"])
            else:
                errs.append("모르는 마커 종류: %r" % t)
        return errs

    def _build_palette(self):
        counts = collections.Counter()
        for layer in self.g:
            for row in layer:
                for v in row:
                    if v not in (" ", "."):
                        counts[v] += 1
        used, palette, inv = set(), {}, {}
        pool = iter(_POOL)
        for s in sorted(counts, key=lambda s: (-counts[s], s)):
            words = parse_block(s)[0].split("_")
            ch = None
            for c in (words[-1][0], words[0][0], words[-1][0].upper(), words[0][0].upper()):
                if c not in used:
                    ch = c
                    break
            while ch is None:
                c = next(pool, None)
                if c is None:
                    raise VillageError("%s: 블록 종류가 너무 많아 팔레트 글자가 모자랍니다 (%d)" % (self.id, len(counts)))
                if c not in used:
                    ch = c
            used.add(ch)
            palette[ch] = s
            inv[s] = ch
        layers = []
        for layer in self.g:
            rows = []
            for row in layer:
                rows.append("".join(v if v in (" ", ".") else inv[v] for v in row))
            layers.append(rows)
        return palette, layers

    def to_dict(self):
        if self._final is None:
            self.finalize()
        palette, layers = self._final
        return collections.OrderedDict([
            ("format", 1),
            ("id", self.id),
            ("name", self.name),
            ("size", [self.W, self.H, self.D]),
            ("floor_y", self.floor_y),
            ("foundation", self.foundation),
            ("foundation_mix", [[b, w] for b, w in self.foundation_mix]),
            ("anchor", list(self.anchor)),
        ] + [(k, v) for k, v in (("deco", self.deco), ("door", self.has_door), ("slack", self.slack)) if v is not None] + [
            ("palette", collections.OrderedDict(sorted(palette.items(), key=lambda kv: kv[1]))),
            ("layers", layers),
            ("markers", self.markers),
        ])

    def to_json(self):
        """VILLAGE.md §2 JSON 문자열 — 층마다 줄 단위로 써서 diff 가 읽기 쉽게."""
        d = self.to_dict()
        dump = lambda v: json.dumps(v, ensure_ascii=False)
        out = ["{"]
        for k in ("format", "id", "name", "size", "floor_y", "foundation", "foundation_mix", "anchor", "deco", "door", "slack"):
            if k in d:
                out.append('  %s: %s,' % (dump(k), dump(d[k])))
        out.append('  "palette": {')
        items = list(d["palette"].items())
        for i, (ch, s) in enumerate(items):
            out.append('    %s: %s%s' % (dump(ch), dump(s), "," if i < len(items) - 1 else ""))
        out.append("  },")
        out.append('  "layers": [')
        for yi, layer in enumerate(d["layers"]):
            out.append("    [")
            for zi, row in enumerate(layer):
                out.append("      %s%s" % (dump(row), "," if zi < len(layer) - 1 else ""))
            out.append("    ]%s" % ("," if yi < len(d["layers"]) - 1 else ""))
        out.append("  ],")
        out.append('  "markers": [')
        for i, m in enumerate(d["markers"]):
            out.append("    %s%s" % (dump(m), "," if i < len(d["markers"]) - 1 else ""))
        out.append("  ]")
        out.append("}")
        return "\n".join(out) + "\n"

    def export(self, path):
        """JSON 파일로 쓰기 (UTF-8)."""
        text = self.to_json()
        json.loads(text)   # 형식 자체 검사
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def layer_text(self, y):
        """디버그용: 한 층을 글자 그림으로 (블록은 id 첫 글자)."""
        return "\n".join("".join(v if v in (" ", ".") else parse_block(v)[0][0] for v in row) for row in self.g[y])


# 장식 조각 id 접두어 (Java Blueprint.DECO_PREFIXES 와 같게)
DECO_PREFIXES = ("lamp_post", "bench", "well", "flower_bed", "tree_", "signpost", "cart", "fence", "planter", "statue",
                 "banner_pole", "crate", "barrel_stack", "hay")
PATH_ATTACH = 2      # 길 끝이 조각에서 이 칸(체비셰프) 안이면 그 조각에 붙은 길 (Java Planner.ATTACH)


def is_deco_id(pid):
    return any(pid.startswith(pre) for pre in DECO_PREFIXES)


def path_cells(points, width):
    """길 꺾은선 → 칸 집합 (Java PathRaster 와 같은 규칙: 홀수 폭은 점이 칸 가운데, 짝수 폭은 칸 모서리;
    중심선까지 거리 ≤ 폭/2 − 0.01 인 칸)."""
    off = 0.5 if width % 2 == 1 else 0.0
    pts = [(q[0] + off, q[1] + off) for q in points]
    half = width / 2.0 - 0.01
    xs = [q[0] for q in points]
    zs = [q[1] for q in points]
    pad = width // 2 + 2
    out = set()
    for z in range(min(zs) - pad, max(zs) + pad + 1):
        for x in range(min(xs) - pad, max(xs) + pad + 1):
            cx, cz = x + 0.5, z + 0.5
            best = 1e18
            for (ax, az), (bx, bz) in zip(pts, pts[1:]):
                dx, dz = bx - ax, bz - az
                l2 = dx * dx + dz * dz
                u = 0.0 if l2 <= 1e-9 else ((cx - ax) * dx + (cz - az) * dz) / l2
                u = max(0.0, min(1.0, u))
                best = min(best, math.hypot(cx - (ax + u * dx), cz - (az + u * dz)))
            if best <= half:
                out.add((x, z))
    return out


def _in_circle(dx, dz, r):
    return dx * dx + dz * dz <= r * r + r


# ─────────────────────────────── 청사진 JSON 읽기 (렌더·build_all 용) ───────────────────────────────

class Blueprint:
    """내보낸 조각 JSON. cells: (x,y,z) → 블록 문자열 또는 '.' (공백은 없음)."""

    def __init__(self, d):
        self.d = d
        self.id = d["id"]
        self.name = d.get("name", d["id"])
        self.W, self.H, self.D = d["size"]
        self.floor_y = d["floor_y"]
        self.anchor = tuple(d["anchor"])
        self.markers = d.get("markers", [])
        self.slack = d.get("slack")
        self.deco = d["deco"] if "deco" in d else is_deco_id(self.id)
        self.door = (not self.deco) and d.get("door", True)
        pal = d["palette"]
        self.cells = {}
        for y, layer in enumerate(d["layers"]):
            for z, row in enumerate(layer):
                for x, ch in enumerate(row):
                    if ch == " ":
                        continue
                    self.cells[(x, y, z)] = "." if ch == "." else pal[ch]

    def columns(self):
        """차지하는 기둥 (x, z) — 어느 층이든 ' ' 가 아닌 칸이 있는 곳 (Java Blueprint.occupied 와 같음)."""
        return {(x, z) for (x, y, z) in self.cells}

    def world_columns(self, r, x0, z0):
        """회전 r, 발자국 최소 모서리 (x0, z0) 에 놓았을 때 차지하는 월드 기둥."""
        out = set()
        for (x, z) in self.columns():
            rx, rz = rot_xz(x, z, self.W, self.D, r)
            out.add((x0 + rx, z0 + rz))
        return out

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def of(cls, piece):
        return cls(json.loads(piece.to_json()))

    def rotated(self, r):
        """회전한 칸 dict, 마커 목록 (pos 회전, face 는 회전된 실제 방향 이름으로), 발자국 크기 (w, d)."""
        r = rot_index(r)
        W, D = self.W, self.D
        cells = {}
        for (x, y, z), s in self.cells.items():
            nx, nz = rot_xz(x, z, W, D, r)
            cells[(nx, y, nz)] = rotate_state(s, r) if s != "." else s
        markers = []
        inv = {v: k for k, v in _FACE_OF_DIR.items()}
        for m in self.markers:
            m2 = dict(m)
            if m["type"] == "interact":
                m2["pos"] = [[rot_xz(p[0], p[2], W, D, r)[0], p[1], rot_xz(p[0], p[2], W, D, r)[1]] for p in m["pos"]]
            else:
                p = m["pos"]
                nx, nz = rot_xz(p[0], p[2], W, D, r)
                m2["pos"] = [nx, p[1], nz]
            if "face" in m:
                m2["dir"] = rot_dir(inv[m["face"]], r)
            markers.append(m2)
        w, d = rotated_size(W, D, r)
        return cells, markers, (w, d)
