"""생성된 데이터팩(server/world/datapacks/aooni_mansion)을 읽어 테스트에 필요한 정보를 뽑는다.

- 모든 함수 id 와 매크로 함수 여부
- 저택 상자 좌표(build/mansion.mcfunction 의 `setblock ... minecraft:chest[`)
- 건축 함수(lobby → mansion 순서)를 흉내 내서 '마지막에 어떤 블록이 있어야 하는지' 계산
"""
from __future__ import annotations

import os
import re

from mcserver import PACK_SRC

FUNC_DIR_REL = os.path.join("data", "aooni", "function")


def function_files(pack: str = PACK_SRC) -> list[tuple[str, str, bool]]:
    """(함수 id, 파일 경로, 매크로 여부) 목록. id 예: aooni:admin/start"""
    out = []
    data = os.path.join(pack, "data")
    for ns in sorted(os.listdir(data)):
        fdir = os.path.join(data, ns, "function")
        if not os.path.isdir(fdir):
            continue
        for dirpath, _, files in os.walk(fdir):
            for f in sorted(files):
                if not f.endswith(".mcfunction"):
                    continue
                path = os.path.join(dirpath, f)
                rel = os.path.relpath(path, fdir)[: -len(".mcfunction")].replace(os.sep, "/")
                with open(path, encoding="utf-8") as fh:
                    macro = any(line.startswith("$") for line in fh)
                out.append((f"{ns}:{rel}", path, macro))
    out.sort()
    return out


def _read(rel: str, pack: str = PACK_SRC) -> list[str]:
    with open(os.path.join(pack, FUNC_DIR_REL, rel), encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]


_SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)")
_FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (\S+))?")


def block_id(spec: str) -> str:
    """'minecraft:chest[facing=south]{...}' → 'minecraft:chest'"""
    bid = re.split(r"[\[{]", spec, maxsplit=1)[0]
    return bid if ":" in bid else "minecraft:" + bid


def chest_positions(pack: str = PACK_SRC) -> list[tuple[int, int, int]]:
    """저택 조사 상자 좌표들(파일에 나온 순서)."""
    out = []
    for ln in _read("build/mansion.mcfunction", pack):
        m = _SETBLOCK.match(ln)
        if m and block_id(m.group(4)) == "minecraft:chest":
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return out


def expected_blocks(pack: str = PACK_SRC, files=("build/lobby.mcfunction", "build/mansion.mcfunction")):
    """건축 함수를 순서대로 흉내 내서 확인할 좌표 → 기대 블록 id 를 돌려준다.

    모든 좌표를 다 확인하면 너무 많으므로, setblock 좌표 전부와 fill 의 두 모서리·가운데만 고른다.
    값은 '마지막으로 그 칸에 놓인 블록'이다(뒤의 fill/setblock 이 덮어쓰는 것까지 반영).
    fill 은 모두 기본(replace) 모드라고 가정한다(모드가 붙어 있으면 그 fill 은 확인 대상에서 뺀다).
    """
    world: dict[tuple[int, int, int], str] = {}
    probes: set[tuple[int, int, int]] = set()
    skipped_modes = 0
    for rel in files:
        for ln in _read(rel, pack):
            m = _SETBLOCK.match(ln)
            if m:
                p = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                world[p] = block_id(m.group(4))
                probes.add(p)
                continue
            m = _FILL.match(ln)
            if m:
                x1, y1, z1, x2, y2, z2 = (int(m.group(i)) for i in range(1, 7))
                mode = m.group(8)
                if mode and mode not in ("replace", "destroy"):
                    skipped_modes += 1
                    continue
                bid = block_id(m.group(7))
                xs = range(min(x1, x2), max(x1, x2) + 1)
                ys = range(min(y1, y2), max(y1, y2) + 1)
                zs = range(min(z1, z2), max(z1, z2) + 1)
                for x in xs:
                    for y in ys:
                        for z in zs:
                            world[(x, y, z)] = bid
                probes.add((x1, y1, z1))
                probes.add((x2, y2, z2))
                probes.add(((x1 + x2) // 2, (y1 + y2) // 2, (z1 + z2) // 2))
    return {p: world[p] for p in sorted(probes)}, skipped_modes


def fill_volumes(pack: str = PACK_SRC) -> list[tuple[str, int, str]]:
    """모든 함수의 fill 명령 부피. (함수 id, 부피, 줄) — 32768 칸을 넘으면 바닐라가 거부한다."""
    out = []
    for fid, path, _ in function_files(pack):
        with open(path, encoding="utf-8") as f:
            for ln in f:
                m = re.search(r"\bfill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) ", ln)
                if m:
                    x1, y1, z1, x2, y2, z2 = (int(m.group(i)) for i in range(1, 7))
                    vol = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
                    out.append((fid, vol, ln.strip()))
    return out
