"""데이터팩 mcfunction 정적 검사기.

실제 마인크래프트 서버 없이도 명령어 문법을 검증하기 위해, Mojang 이 배포한
버전별 명령어 트리/블록/레지스트리 데이터(misode/mcmeta 의 *-summary 브랜치)를
내려받아 모든 줄을 Brigadier 방식(백트래킹)으로 파싱해 본다.

검사 항목
- 명령어 구조(리터럴/인자 순서, 실행 가능 노드에서 끝나는지)
- 블록 ID/블록 상태 속성, 아이템·엔티티·효과·사운드·파티클·속성 레지스트리 ID
- SNBT/텍스트 컴포넌트 문법, 선택자 옵션, 좌표, 범위 표기
- function 참조가 팩 안에 실제로 있는지, fill 부피 한도(32768)

사용: python tools/mcvalidate.py <datapack 경로> [버전 ...]
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

DEFAULT_VERSIONS = ["1.21.5", "1.21.8", "1.21.11", "26.1.2", "26.2", "26.3"]
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".mcmeta-cache")
BASE = "https://raw.githubusercontent.com/misode/mcmeta/{v}-summary/{f}"
FILL_LIMIT = 32768

# 매크로 줄($)을 검사할 때 $(이름) 자리에 넣어 볼 예시 값
MACRO_SAMPLES = {
    "c1": "7", "c2": "0", "c3": "9", "c4": "3",
    "d1": "1", "d2": "2", "d3": "3", "d4": "4",
    "n1": "도", "n2": "레", "n3": "미", "n4": "파", "n5": "솔",
    "n": "4", "t": "보통", "sec": "12", "min": "3",
    "o": "doMobSpawning", "v": "false", "r": "doMobSpawning",
    "nm": "전설의 검",
}
# 버전마다 이름이 달라 일부러 한쪽이 실패하도록 만든 매크로 파일(별도 검사)
MACRO_SKIP_FILES = {"compat/gamerule_try.mcfunction"}

COLORS = {"black", "dark_blue", "dark_green", "dark_aqua", "dark_red", "dark_purple", "gold",
          "gray", "dark_gray", "blue", "green", "aqua", "red", "light_purple", "yellow", "white"}
SELECTOR_KEYS = {"x", "y", "z", "dx", "dy", "dz", "distance", "limit", "sort", "type", "tag", "team",
                 "name", "scores", "level", "gamemode", "x_rotation", "y_rotation", "nbt",
                 "advancements", "predicate"}
UNQUOTED = re.compile(r"[0-9A-Za-z_\-.+]")
RL_CHARS = re.compile(r"[0-9a-z_\-./:]")


class PErr(Exception):
    def __init__(self, pos, msg):
        super().__init__(msg)
        self.pos = pos
        self.msg = msg


# ---------------------------------------------------------------- data
def fetch(version, name):
    os.makedirs(os.path.join(CACHE, version), exist_ok=True)
    path = os.path.join(CACHE, version, name.replace("/", "_"))
    if not os.path.exists(path):
        url = BASE.format(v=version, f=name)
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class VersionData:
    def __init__(self, version):
        self.version = version
        self.tree = fetch(version, "commands/data.json")
        self.blocks = fetch(version, "blocks/data.json")
        self.reg = fetch(version, "registries/data.json")

    def registry(self, name):
        name = name.replace("minecraft:", "")
        return self.reg.get(name)


def strip_ns(s):
    return s[10:] if s.startswith("minecraft:") else s


# ---------------------------------------------------------------- SNBT
class SNBT:
    """SNBT/JSON 겸용 파서. 끝 위치만 돌려준다(구문 검증용)."""

    NUM = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?(?:[bBsSlLfFdD]|[uU]?[bBsSiIlL]|[sS][bBsSiIlL])?")

    def __init__(self, s):
        self.s = s

    def ws(self, i):
        while i < len(self.s) and self.s[i] in " \t":
            i += 1
        return i

    def value(self, i):
        i = self.ws(i)
        if i >= len(self.s):
            raise PErr(i, "SNBT 값이 필요함")
        c = self.s[i]
        if c == "{":
            return self.compound(i)
        if c == "[":
            return self.list(i)
        if c in "\"'":
            return self.quoted(i)
        j = i
        while j < len(self.s) and (UNQUOTED.match(self.s[j])):
            j += 1
        if j == i:
            raise PErr(i, f"SNBT 값 시작이 잘못됨: {self.s[i:i+10]!r}")
        # 1.21.5+ 의 bool(...)/uuid(...) 같은 연산은 쓰지 않는다
        return j

    def quoted(self, i):
        q = self.s[i]
        j = i + 1
        while j < len(self.s):
            if self.s[j] == "\\":
                j += 2
                continue
            if self.s[j] == q:
                return j + 1
            j += 1
        raise PErr(i, "닫히지 않은 문자열")

    def key(self, i):
        i = self.ws(i)
        if i < len(self.s) and self.s[i] in "\"'":
            return self.quoted(i)
        j = i
        while j < len(self.s) and UNQUOTED.match(self.s[j]):
            j += 1
        if j == i:
            raise PErr(i, "SNBT 키가 필요함")
        return j

    def compound(self, i):
        i += 1
        i = self.ws(i)
        if i < len(self.s) and self.s[i] == "}":
            return i + 1
        while True:
            i = self.key(i)
            i = self.ws(i)
            if i >= len(self.s) or self.s[i] != ":":
                raise PErr(i, "SNBT ':' 가 필요함")
            i = self.value(i + 1)
            i = self.ws(i)
            if i < len(self.s) and self.s[i] == ",":
                i += 1
                continue
            if i < len(self.s) and self.s[i] == "}":
                return i + 1
            raise PErr(i, "SNBT ',' 또는 '}' 가 필요함")

    def list(self, i):
        i += 1
        if re.match(r"[BIL];", self.s[i:i+2]):
            i += 2
        i = self.ws(i)
        if i < len(self.s) and self.s[i] == "]":
            return i + 1
        while True:
            i = self.value(i)
            i = self.ws(i)
            if i < len(self.s) and self.s[i] == ",":
                i += 1
                continue
            if i < len(self.s) and self.s[i] == "]":
                return i + 1
            raise PErr(i, "SNBT ',' 또는 ']' 가 필요함")


# ---------------------------------------------------------------- argument parsers
class LineParser:
    def __init__(self, vd: VersionData, line: str, functions: set, fn_tags: set):
        self.vd = vd
        self.s = line
        self.n = len(line)
        self.functions = functions
        self.fn_tags = fn_tags
        self.best = (0, "알 수 없는 명령")
        self.root = vd.tree

    # ---- helpers
    def fail(self, pos, msg):
        if pos >= self.best[0]:
            self.best = (pos, msg)

    def word(self, i):
        j = i
        while j < self.n and self.s[j] != " ":
            j += 1
        return j

    def unquoted(self, i):
        j = i
        while j < self.n and UNQUOTED.match(self.s[j]):
            j += 1
        return j

    def string(self, i):
        if i < self.n and self.s[i] in "\"'":
            return SNBT(self.s).quoted(i)
        return self.unquoted(i)

    def rl(self, i, allow_tag=False):
        j = i
        if allow_tag and j < self.n and self.s[j] == "#":
            j += 1
        k = j
        while k < self.n and RL_CHARS.match(self.s[k]):
            k += 1
        if k == j:
            raise PErr(i, "리소스 위치가 필요함")
        val = self.s[j:k]
        if val.count(":") > 1:
            raise PErr(i, f"잘못된 리소스 위치 {val}")
        return k, val, (self.s[i] == "#")

    def number(self, i, integer=False):
        m = re.compile(r"-?\d+" if integer else r"-?(?:\d+\.?\d*|\.\d+)").match(self.s, i)
        if not m:
            raise PErr(i, "숫자가 필요함")
        return m.end(), m.group(0)

    def coord(self, i, integer=False, allow_caret=True):
        if i < self.n and self.s[i] in "~^":
            if self.s[i] == "^" and not allow_caret:
                raise PErr(i, "^ 좌표 불가")
            j = i + 1
            m = re.compile(r"-?(?:\d+\.?\d*|\.\d+)").match(self.s, j)
            return m.end() if m else j, self.s[i]
        j, _ = self.number(i, integer=integer)
        return j, "abs"

    def coords(self, i, count, integer=False, allow_caret=True):
        kinds = []
        for k in range(count):
            if k:
                if i >= self.n or self.s[i] != " ":
                    raise PErr(i, "좌표 개수가 부족함")
                i += 1
            i, kind = self.coord(i, integer, allow_caret)
            kinds.append(kind)
        if "^" in kinds and any(k != "^" for k in kinds):
            raise PErr(i, "^ 좌표는 섞어 쓸 수 없음")
        return i

    def block_state(self, i, predicate=False):
        j, val, is_tag = self.rl(i, allow_tag=predicate)
        props = None
        if is_tag:
            if self.vd.reg.get("tag/block") is not None and strip_ns(val) not in self.vd.reg["tag/block"]:
                raise PErr(i, f"블록 태그 없음: #{val}")
        else:
            bid = strip_ns(val)
            if bid not in self.vd.blocks:
                raise PErr(i, f"블록 없음: {val}")
            props = self.vd.blocks[bid][0]
        if j < self.n and self.s[j] == "[":
            k = self.s.index("]", j) if "]" in self.s[j:] else -1
            if k < 0:
                raise PErr(j, "블록 상태 ']' 누락")
            body = self.s[j+1:k]
            if body.strip():
                for kv in body.split(","):
                    if "=" not in kv:
                        raise PErr(j, f"블록 상태 형식 오류: {kv}")
                    pk, pv = [x.strip() for x in kv.split("=", 1)]
                    if props is not None:
                        if pk not in props:
                            raise PErr(j, f"{val} 에 속성 {pk} 없음")
                        if pv not in props[pk]:
                            raise PErr(j, f"{val}[{pk}] 값 {pv} 불가 (가능: {props[pk]})")
            j = k + 1
        if j < self.n and self.s[j] == "{":
            j = SNBT(self.s).compound(j)
        return j

    def item(self, i, predicate=False):
        if predicate and i < self.n and self.s[i] == "*":
            j = i + 1
        else:
            j, val, is_tag = self.rl(i, allow_tag=predicate)
            reg = self.vd.reg.get("tag/item" if is_tag else "item")
            if reg is not None and strip_ns(val) not in reg:
                raise PErr(i, f"아이템 없음: {val}")
        if j < self.n and self.s[j] == "[":
            depth = 0
            k = j
            while k < self.n:
                if self.s[k] in "[{":
                    depth += 1
                elif self.s[k] in "]}":
                    depth -= 1
                    if depth == 0:
                        break
                elif self.s[k] in "\"'":
                    k = SNBT(self.s).quoted(k) - 1
                k += 1
            j = k + 1
        if j < self.n and self.s[j] == "{":
            j = SNBT(self.s).compound(j)
        return j

    def selector(self, i, props):
        if self.s[i] != "@":
            j = self.word(i)
            if j == i:
                raise PErr(i, "대상이 필요함")
            return j
        if i + 1 >= self.n or self.s[i+1] not in "aeprsn":
            raise PErr(i, "잘못된 선택자")
        kind = self.s[i+1]
        j = i + 2
        opts = {}
        if j < self.n and self.s[j] == "[":
            j += 1
            while True:
                j = SNBT(self.s).ws(j)
                if j < self.n and self.s[j] == "]":
                    j += 1
                    break
                k = self.unquoted(j)
                key = self.s[j:k]
                if key not in SELECTOR_KEYS:
                    raise PErr(j, f"선택자 옵션 없음: {key}")
                if k >= self.n or self.s[k] != "=":
                    raise PErr(k, "선택자 '=' 필요")
                k += 1
                if k < self.n and self.s[k] == "!":
                    k += 1
                if key in ("scores", "advancements"):
                    k = self._balanced(k)
                elif key == "nbt":
                    k = SNBT(self.s).compound(k)
                elif k < self.n and self.s[k] in "\"'":
                    k = SNBT(self.s).quoted(k)
                else:
                    start = k
                    while k < self.n and self.s[k] not in ",]":
                        k += 1
                    v = self.s[start:k]
                    if key in ("distance", "level", "x_rotation", "y_rotation") and not re.fullmatch(r"-?[\d.]*(\.\.)?-?[\d.]*", v):
                        raise PErr(start, f"범위 형식 오류: {v}")
                    if key in ("x", "y", "z", "dx", "dy", "dz") and not re.fullmatch(r"-?\d+(\.\d+)?", v):
                        raise PErr(start, f"좌표 형식 오류: {v}")
                    if key == "limit" and not re.fullmatch(r"\d+", v):
                        raise PErr(start, "limit 숫자 필요")
                    if key == "sort" and v not in ("nearest", "furthest", "random", "arbitrary"):
                        raise PErr(start, f"sort 값 오류: {v}")
                    if key == "gamemode" and v not in ("survival", "creative", "adventure", "spectator"):
                        raise PErr(start, f"gamemode 값 오류: {v}")
                    if key == "type":
                        ev = v.lstrip("#")
                        reg = self.vd.reg.get("tag/entity_type" if v.startswith("#") else "entity_type")
                        if reg is not None and strip_ns(ev) not in reg:
                            raise PErr(start, f"엔티티 타입 없음: {v}")
                    if key in ("tag", "team") and v and not re.fullmatch(r"[0-9A-Za-z_\-.+]+", v):
                        raise PErr(start, f"{key} 이름 오류: {v}")
                    opts.setdefault(key, []).append(v)
                j = k
                if j < self.n and self.s[j] == ",":
                    j += 1
                    continue
                if j < self.n and self.s[j] == "]":
                    j += 1
                    break
                raise PErr(j, "선택자 ',' 또는 ']' 필요")
        if props:
            if props.get("amount") == "single" and kind in "ae" and opts.get("limit") != ["1"]:
                raise PErr(i, "단일 대상 자리인데 limit=1 없음")
            if props.get("type") == "players" and kind == "e" and "player" not in [strip_ns(t) for t in opts.get("type", [])]:
                raise PErr(i, "플레이어 전용 자리에 @e")
        return j

    def _balanced(self, k):
        if self.s[k] != "{":
            raise PErr(k, "'{' 필요")
        depth = 0
        while k < self.n:
            if self.s[k] == "{":
                depth += 1
            elif self.s[k] == "}":
                depth -= 1
                if depth == 0:
                    return k + 1
            k += 1
        raise PErr(k, "괄호 불균형")

    def nbt_path(self, i):
        j = i
        depth = 0
        while j < self.n:
            c = self.s[j]
            if c in "\"'":
                j = SNBT(self.s).quoted(j)
                continue
            if c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
            elif c == " " and depth == 0:
                break
            j += 1
        if j == i or depth != 0:
            raise PErr(i, "NBT 경로 오류")
        return j

    def registry_check(self, i, val, registry, is_tag=False):
        reg = self.vd.registry(("tag/" if is_tag else "") + registry)
        if reg is None:
            return
        if strip_ns(val) not in reg:
            raise PErr(i, f"{registry} 에 {val} 없음")

    # ---- argument dispatcher: returns end index
    def arg(self, node, i):
        p = node.get("parser")
        props = node.get("properties", {}) or {}
        s = self.s
        if p == "brigadier:bool":
            for w in ("true", "false"):
                if s.startswith(w, i):
                    return i + len(w)
            raise PErr(i, "true/false 필요")
        if p in ("brigadier:integer", "brigadier:long"):
            j, v = self.number(i, integer=True)
            v = int(v)
            if "min" in props and v < props["min"] or "max" in props and v > props["max"]:
                raise PErr(i, f"범위 밖 정수 {v}")
            return j
        if p in ("brigadier:float", "brigadier:double"):
            j, v = self.number(i)
            v = float(v)
            if "min" in props and v < props["min"] or "max" in props and v > props["max"]:
                raise PErr(i, f"범위 밖 실수 {v}")
            return j
        if p == "brigadier:string":
            t = props.get("type")
            if t == "greedy":
                return self.n
            if t == "phrase":
                return self.string(i)
            j = self.unquoted(i)
            if j == i:
                raise PErr(i, "단어 필요")
            return j
        if p in ("minecraft:entity", "minecraft:game_profile"):
            return self.selector(i, props)
        if p == "minecraft:score_holder":
            if s[i] == "*":
                return i + 1
            if s[i] == "@":
                return self.selector(i, None)
            return self.word(i)
        if p == "minecraft:block_pos":
            return self.coords(i, 3, integer=True)
        if p == "minecraft:vec3":
            return self.coords(i, 3)
        if p in ("minecraft:vec2", "minecraft:rotation"):
            return self.coords(i, 2, allow_caret=(p == "minecraft:vec2"))
        if p == "minecraft:column_pos":
            return self.coords(i, 2, integer=True, allow_caret=False)
        if p == "minecraft:angle":
            j, _ = self.coord(i, allow_caret=False)
            return j
        if p == "minecraft:block_state":
            return self.block_state(i)
        if p == "minecraft:block_predicate":
            return self.block_state(i, predicate=True)
        if p == "minecraft:item_stack":
            return self.item(i)
        if p == "minecraft:item_predicate":
            return self.item(i, predicate=True)
        if p in ("minecraft:resource_location", "minecraft:dimension", "minecraft:loot_table",
                 "minecraft:loot_predicate", "minecraft:loot_modifier", "minecraft:dialog"):
            j, _, _ = self.rl(i)
            return j
        if p == "minecraft:resource":
            j, val, _ = self.rl(i)
            self.registry_check(i, val, props.get("registry", ""))
            return j
        if p in ("minecraft:resource_or_tag", "minecraft:resource_or_tag_key", "minecraft:resource_key",
                 "minecraft:resource_selector"):
            j, val, is_tag = self.rl(i, allow_tag=True)
            if p == "minecraft:resource_or_tag":
                self.registry_check(i, val, props.get("registry", ""), is_tag)
            return j
        if p == "minecraft:function":
            j, val, is_tag = self.rl(i, allow_tag=True)
            full = val if ":" in val else "minecraft:" + val
            if is_tag:
                if full not in self.fn_tags:
                    raise PErr(i, f"함수 태그 없음: #{full}")
            elif full.startswith("aooni:") and full not in self.functions:
                raise PErr(i, f"함수 없음: {full}")
            return j
        if p in ("minecraft:component", "minecraft:nbt_tag"):
            return SNBT(s).value(i)
        if p in ("minecraft:nbt_compound_tag", "minecraft:style"):
            if s[i] != "{":
                raise PErr(i, "'{' 필요")
            return SNBT(s).compound(i)
        if p == "minecraft:nbt_path":
            return self.nbt_path(i)
        if p in ("minecraft:objective", "minecraft:team"):
            j = self.unquoted(i)
            if j == i:
                raise PErr(i, "이름 필요")
            return j
        if p == "minecraft:objective_criteria":
            j = self.word(i)
            crit = s[i:j]
            if crit not in ("dummy", "trigger", "deathCount", "playerKillCount", "totalKillCount", "health",
                            "xp", "level", "food", "air", "armor") and not re.fullmatch(r"minecraft\.[a-z_]+:minecraft\.[a-z_.]+", crit):
                raise PErr(i, f"기준 오류: {crit}")
            return j
        if p in ("minecraft:color", "minecraft:team_color"):
            j = self.unquoted(i)
            if s[i:j] not in COLORS and not (p == "minecraft:team_color" and s[i:j] == "reset"):
                raise PErr(i, f"색 이름 오류: {s[i:j]}")
            return j
        if p == "minecraft:entity_anchor":
            for w in ("feet", "eyes"):
                if s.startswith(w, i):
                    return i + len(w)
            raise PErr(i, "feet/eyes")
        if p == "minecraft:swizzle":
            j = self.unquoted(i)
            if not re.fullmatch(r"[xyz]{1,3}", s[i:j]):
                raise PErr(i, "swizzle 오류")
            return j
        if p in ("minecraft:int_range", "minecraft:float_range"):
            j = self.word(i)
            pat = r"-?\d+(\.\.(-?\d+)?)?|\.\.-?\d+" if p == "minecraft:int_range" else r"-?[\d.]+(\.\.(-?[\d.]+)?)?|\.\.-?[\d.]+"
            if not re.fullmatch(pat, s[i:j]):
                raise PErr(i, f"범위 오류: {s[i:j]}")
            return j
        if p == "minecraft:time":
            m = re.compile(r"\d+(\.\d+)?[dst]?").match(s, i)
            if not m:
                raise PErr(i, "시간 형식 오류")
            return m.end()
        if p == "minecraft:gamemode":
            j = self.unquoted(i)
            if s[i:j] not in ("survival", "creative", "adventure", "spectator"):
                raise PErr(i, "게임모드 오류")
            return j
        if p == "minecraft:operation":
            j = self.word(i)
            if s[i:j] not in ("=", "+=", "-=", "*=", "/=", "%=", "<", ">", "><"):
                raise PErr(i, "연산자 오류")
            return j
        if p == "minecraft:scoreboard_slot":
            j = self.word(i)
            v = s[i:j]
            if v not in ("list", "sidebar", "below_name", "belowName") and not v.startswith("sidebar.team."):
                raise PErr(i, "슬롯 오류")
            return j
        if p == "minecraft:particle":
            j, val, _ = self.rl(i)
            self.registry_check(i, val, "particle_type")
            if j < self.n and s[j] == "{":
                j = SNBT(s).compound(j)
            return j
        if p in ("minecraft:item_slot", "minecraft:item_slots", "minecraft:heightmap", "minecraft:template_mirror",
                 "minecraft:template_rotation", "minecraft:uuid", "minecraft:hex_color", "minecraft:slot_source",
                 "minecraft:swing_animation", "minecraft:feature"):
            j = self.word(i)
            if j == i:
                raise PErr(i, "값 필요")
            return j
        if p == "minecraft:message":
            return self.n
        if p in ("minecraft:context_int_provider", "minecraft:context_float_provider"):
            if s[i] in "{[":
                return SNBT(s).value(i)
            j, _ = self.number(i)
            return j
        raise PErr(i, f"검사기가 모르는 인자 형식 {p}")

    # ---- tree walking (backtracking)
    def resolve(self, node):
        if "redirect" in node:
            tgt = self.root
            for k in node["redirect"]:
                tgt = tgt["children"][k]
            return tgt
        if not node.get("children") and not node.get("executable"):
            return self.root  # execute run / return run → 루트로
        return node

    def children_of(self, node, i):
        lits = []
        args = []
        for name, ch in node.get("children", {}).items():
            (lits if ch["type"] == "literal" else args).append((name, ch))
        for name, ch in lits:
            end = i + len(name)
            if self.s.startswith(name, i) and (end == self.n or self.s[end] == " "):
                if self.after(ch, end):
                    return True
        for name, ch in args:
            try:
                end = self.arg(ch, i)
            except PErr as e:
                self.fail(e.pos, f"<{name}> {e.msg}")
                continue
            except (ValueError, IndexError) as e:
                self.fail(i, f"<{name}> 파싱 실패 {e}")
                continue
            if end == self.n or (end < self.n and self.s[end] == " "):
                if self.after(ch, end):
                    return True
            else:
                self.fail(end, f"<{name}> 뒤에 공백 필요: {self.s[end:end+20]!r}")
        if lits or args:
            self.fail(i, "다음 토큰을 해석할 수 없음: " + self.s[i:i+30])
        return False

    def after(self, node, end):
        if end == self.n:
            if node.get("executable"):
                return True
            self.fail(end, "명령이 덜 끝남")
            return False
        nxt = self.resolve(node)
        if nxt is node and not node.get("children"):
            self.fail(end, "불필요한 추가 인자")
            return False
        return self.children_of(nxt, end + 1)

    def check(self):
        if self.children_of(self.root, 0):
            return None
        return self.best


# ---------------------------------------------------------------- pack walking
def collect(pack):
    functions, fn_tags, files = set(), set(), []
    data = os.path.join(pack, "data")
    for ns in os.listdir(data):
        fdir = os.path.join(data, ns, "function")
        for root, _, names in os.walk(fdir):
            for nm in names:
                if nm.endswith(".mcfunction"):
                    rel = os.path.relpath(os.path.join(root, nm), fdir).replace(os.sep, "/")
                    functions.add(f"{ns}:{rel[:-11]}")
                    files.append((ns, rel, os.path.join(root, nm)))
        tdir = os.path.join(data, ns, "tags", "function")
        for root, _, names in os.walk(tdir):
            for nm in names:
                if nm.endswith(".json"):
                    rel = os.path.relpath(os.path.join(root, nm), tdir).replace(os.sep, "/")
                    fn_tags.add(f"{ns}:{rel[:-5]}")
    return functions, fn_tags, files


SOUND_RE = re.compile(r"\b(?:playsound|stopsound \S+ \S+) (minecraft:[a-z0-9_.]+)")
FILL_RE = re.compile(r"(?:^|\brun )fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) ")


def validate(pack, versions):
    functions, fn_tags, files = collect(pack)
    total_err = 0
    lines_checked = 0
    # 함수 태그 내용 검사
    for tag in fn_tags:
        ns, path = tag.split(":")
        with open(os.path.join(pack, "data", ns, "tags", "function", path + ".json"), encoding="utf-8") as f:
            for v in json.load(f)["values"]:
                ref = v["id"] if isinstance(v, dict) else v
                if ref.startswith("aooni:") and ref not in functions:
                    print(f"[태그] {tag}: 없는 함수 {ref}")
                    total_err += 1
    for version in versions:
        vd = VersionData(version)
        errs = 0
        for ns, rel, path in files:
            with open(path, encoding="utf-8") as f:
                for ln, raw in enumerate(f, 1):
                    line = raw.rstrip("\n")
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    if line != line.strip():
                        print(f"[{version}] {ns}:{rel}:{ln}: 앞뒤 공백")
                        errs += 1
                    if line.startswith("$"):
                        if rel in MACRO_SKIP_FILES:
                            continue
                        line = line[1:]
                        missing = [m for m in re.findall(r"\$\((\w+)\)", line)
                                   if m not in MACRO_SAMPLES and not re.fullmatch(r"[kd]\d\d", m)]
                        if missing:
                            print(f"[{version}] {ns}:{rel}:{ln}: 매크로 예시값 없음 {missing}")
                            errs += 1
                            continue
                        line = re.sub(r"\$\((\w+)\)", lambda m: MACRO_SAMPLES.get(m.group(1), "5"), line)
                    elif "$(" in line:
                        print(f"[{version}] {ns}:{rel}:{ln}: $ 없는 줄에 $( ) 사용")
                        errs += 1
                    lines_checked += 1
                    m = FILL_RE.search(line)
                    if m:
                        a = list(map(int, m.groups()))
                        vol = (abs(a[3]-a[0])+1) * (abs(a[4]-a[1])+1) * (abs(a[5]-a[2])+1)
                        if vol > FILL_LIMIT:
                            print(f"[{version}] {ns}:{rel}:{ln}: fill 부피 {vol} > {FILL_LIMIT}")
                            errs += 1
                    for snd in SOUND_RE.findall(line):
                        if strip_ns(snd) not in vd.reg.get("sound_event", []):
                            print(f"[{version}] {ns}:{rel}:{ln}: 사운드 없음 {snd}")
                            errs += 1
                    res = LineParser(vd, line, functions, fn_tags).check()
                    if res:
                        pos, msg = res
                        print(f"[{version}] {ns}:{rel}:{ln}: {msg}\n    {line}\n    {' ' * pos}^")
                        errs += 1
        print(f"== {version}: 오류 {errs}개")
        total_err += errs
    print(f"검사한 줄 수(버전당): {lines_checked // max(1, len(versions))}, 함수 {len(functions)}개")
    return total_err


def check_gamerules(pack_rules, versions):
    """compat 매크로로 넘기는 (옛 이름, 새 이름) 중 버전마다 하나는 반드시 존재해야 한다."""
    errs = 0
    for version in versions:
        vd = VersionData(version)
        names = set(vd.tree["children"]["gamerule"]["children"].keys())
        for old, new, _ in pack_rules:
            if old not in names and new not in names:
                print(f"[{version}] 게임룰 {old}/{new} 둘 다 없음")
                errs += 1
    return errs


def main(pack_dir, versions=None, gamerules=None):
    versions = versions or DEFAULT_VERSIONS
    n = validate(pack_dir, versions)
    if gamerules:
        n += check_gamerules(gamerules, versions)
    print("통과" if n == 0 else f"실패: {n}")
    return n


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1], sys.argv[2:]) else 0)
