#!/usr/bin/env python3
"""
0.3.5 P0c — 스킬마다 PvP 배율: classes.yml `skills[].pvp_mult` · items.yml `weapon_skills[].pvp_mult` 를
pvp_spec JSON 의 `skill_mult` 대로 넣는다 (pvp_spec §6 — 한 사람 계수 2.5 를 넘는 광역·궁극기).

  python3 tools/gen_035_pvp.py            # 두 파일을 고쳐 씀 (이미 같은 값이면 그대로)
  python3 tools/gen_035_pvp.py --check    # 쓰지 않고 검사만 — 모두 명세와 같으면 종료 코드 0
  python3 tools/gen_035_pvp.py --dry-run  # 무엇이 바뀌는지만 출력

입력 = tools/data/035/pvp_spec.json (`skill_mult`: 직업 스킬 id → 배율, `무기id:입력` → 배율).
명세에 없는 스킬에 적힌 pvp_mult 는 지우지 않고 경고만 한다 (새 스킬도 같은 규칙으로 — tools/pv_sim.py skill_mults).
줄 단위로 고쳐 쓰므로 주석·순서·흐름 표기는 그대로 남는다. 다 쓰고 나서 YAML 을 다시 읽어 값이 명세와 같은지 확인한다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "plugin/src/main/resources/content"
ITEMS = CONTENT / "items.yml"
CLASSES = CONTENT / "classes.yml"
SPEC = ROOT / "tools/data/035/pvp_spec.json"

ITEM_RE = re.compile(r"^  ([a-z0-9_]+):\s*(#.*)?$")
ENTRY_RE = re.compile(r"^(\s+)- id: ([a-z0-9_]+)\s*$")
KEY_RE = re.compile(r"^(\s+)([a-z_]+):(.*)$")


def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def entries(lines, start, end):
    """lines[start:end] 안의 `- id:` 목록 항목 → (첫 줄, 끝 줄 다음, 들여쓰기)."""
    out = []
    i = start
    while i < end:
        m = ENTRY_RE.match(lines[i])
        if m:
            ind = len(m.group(1))
            j = i + 1
            while j < end:
                l = lines[j]
                if l.strip() and (len(l) - len(l.lstrip())) <= ind:
                    break
                j += 1
            out.append((i, j, ind))
            i = j
        else:
            i += 1
    return out


def field(lines, a, b, key, ind):
    """항목 안 key 줄 (항목 키 들여쓰기 = ind + 2)."""
    want = " " * (ind + 2) + key + ":"
    for k in range(a + 1, b):
        if lines[k].startswith(want):
            return k
    return None


def set_mult(lines, a, b, ind, value, where, changes):
    """항목 lines[a:b] 에 pvp_mult 를 넣거나 고친다. @return 줄 수 변화."""
    k = field(lines, a, b, "pvp_mult", ind)
    text = " " * (ind + 2) + "pvp_mult: " + fmt(value)
    if k is not None:
        if lines[k].rstrip() != text:
            changes.append(f"{where}: {lines[k].strip()} → pvp_mult: {fmt(value)}")
            lines[k] = text
        return 0
    anchor = field(lines, a, b, "mana", ind) or field(lines, a, b, "cooldown", ind) or field(lines, a, b, "input", ind)
    if anchor is None:
        sys.exit(f"{where}: mana·cooldown·input 줄이 없어 pvp_mult 를 넣을 자리를 못 찾음")
    lines.insert(anchor + 1, text)
    changes.append(f"{where}: + pvp_mult: {fmt(value)}")
    return 1


def item_blocks(lines):
    """items: 아래 아이템 → (첫 줄, 끝 줄 다음)."""
    out = {}
    starts = [(i, ITEM_RE.match(l).group(1)) for i, l in enumerate(lines) if ITEM_RE.match(l)]
    for n, (i, name) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        out[name] = (i, end)
    return out


def do_classes(lines, mults, changes):
    want = {k: v for k, v in mults.items() if ":" not in k}
    found = set()
    for a, b, ind in entries(lines, 0, len(lines)):
        sid = ENTRY_RE.match(lines[a]).group(2)
        if sid not in want:
            if field(lines, a, b, "pvp_mult", ind) is not None:
                print(f"경고: classes.yml {sid} 에 명세에 없는 pvp_mult", file=sys.stderr)
            continue
        if field(lines, a, b, "unlock_level", ind) is None:
            continue  # 직업 스킬만 (unlock_level 이 있는 항목)
        found.add(sid)
    # 줄을 넣으면 위치가 밀리므로 뒤에서부터
    for a, b, ind in reversed(entries(lines, 0, len(lines))):
        sid = ENTRY_RE.match(lines[a]).group(2)
        if sid in want and field(lines, a, b, "unlock_level", ind) is not None:
            set_mult(lines, a, b, ind, want[sid], f"classes.yml {sid}", changes)
    missing = set(want) - found
    if missing:
        sys.exit("classes.yml 에 없는 직업 스킬: " + ", ".join(sorted(missing)))


def do_items(lines, mults, changes):
    want = {}
    for k, v in mults.items():
        if ":" in k:
            item, inp = k.split(":")
            want.setdefault(item, {})[inp] = v
    blocks = item_blocks(lines)
    missing = [i for i in want if i not in blocks]
    if missing:
        sys.exit("items.yml 에 없는 무기: " + ", ".join(missing))
    for item in sorted(want, key=lambda i: -blocks[i][0]):
        a0, b0 = blocks[item]
        got = {}
        for a, b, ind in entries(lines, a0, b0):
            k = field(lines, a, b, "input", ind)
            if k is None:
                continue
            got[lines[k].split(":", 1)[1].strip().upper()] = (a, b, ind)
        for inp in sorted(want[item], key=lambda x: -(got.get(x, (0,))[0])):
            if inp not in got:
                sys.exit(f"items.yml {item}: 입력 {inp} 무기 스킬이 없음")
            a, b, ind = got[inp]
            set_mult(lines, a, b, ind, want[item][inp], f"items.yml {item}:{inp}", changes)


def verify(mults):
    """다시 읽어 값 확인 (YAML 의미)."""
    bad = []
    cls = yaml.safe_load(CLASSES.read_text(encoding="utf-8"))["classes"]
    seen = {}
    for c in cls.values():
        for s in c.get("skills", []):
            if "pvp_mult" in s:
                seen[s["id"]] = s["pvp_mult"]
    items = yaml.safe_load(ITEMS.read_text(encoding="utf-8"))["items"]
    for iid, d in items.items():
        for s in (d or {}).get("weapon_skills", []) or []:
            if "pvp_mult" in s:
                seen[f"{iid}:{str(s.get('input', 'RIGHT')).upper()}"] = s["pvp_mult"]
    for k, v in mults.items():
        if abs(float(seen.get(k, 1.0)) - v) > 1e-9:
            bad.append(f"{k}: 명세 {v} · 파일 {seen.get(k)}")
    for k in seen:
        if k not in mults:
            print(f"경고: 명세에 없는 pvp_mult {k} = {seen[k]}", file=sys.stderr)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    mults = json.loads(SPEC.read_text(encoding="utf-8"))["skill_mult"]
    changes = []
    cl = CLASSES.read_text(encoding="utf-8").split("\n")
    il = ITEMS.read_text(encoding="utf-8").split("\n")
    do_classes(cl, mults, changes)
    do_items(il, mults, changes)
    if a.check:
        for c in changes:
            print("다름:", c)
        sys.exit(1 if changes else 0)
    for c in changes:
        print(c)
    if a.dry_run:
        return
    if changes:
        CLASSES.write_text("\n".join(cl), encoding="utf-8")
        ITEMS.write_text("\n".join(il), encoding="utf-8")
    bad = verify(mults)
    if bad:
        sys.exit("다시 읽은 값이 명세와 다름:\n" + "\n".join(bad))
    print(f"pvp_mult {len(mults)}개 확인 ({len(changes)}줄 바꿈)")


if __name__ == "__main__":
    main()
