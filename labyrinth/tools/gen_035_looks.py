#!/usr/bin/env python3
"""
0.3.5 P2 — 방어구 겉모습 장단점 데이터를 items.yml 에 넣는다 (look_spec §3·§8 + review2 A2·A3·A5).

  python3 tools/gen_035_looks.py            # items.yml 을 고쳐 씀 (이미 같은 값이면 그대로)
  python3 tools/gen_035_looks.py --check    # 쓰지 않고 검사만 — 모두 명세와 같으면 종료 코드 0
  python3 tools/gen_035_looks.py --dry-run  # 무엇이 바뀌는지만 출력

입력 = tools/data/035/armor_looks.json
  - 방어구 요구 능력치: 세트·단품마다 요구 짝(set_pairs · item_pairs), 합 T(L) = ceil(2.75(L−1)) (L ≤ 2 이면 없음),
    두 능력치 60 : 40 (앞 = ceil(0.6 T)), 세 능력치 50 : 30 : 20. `requires_any` 는 지운다 ('… 중 하나' 없음).
  - 스탯 줄 이름 바꿈(stats_rename): 요구 짝과 맞추려고 세트 부위의 스탯 줄 이름만 바꾼다 (값 그대로). 가진 아이템은
    플러그인이 PDC 키를 같은 깃발(ITEM_COMBAT_VER 35)에 옮긴다 (ItemMigration035.ARMOR_RENAME).
  - 겉모습: 세트 없는 투구에 `look:` (item_looks), 수련생·길잡이 세트에 `look_effects: false` (평상복).
  - 세트 머리 주석의 '요구 …' 글을 새 값으로.
줄 단위로 고쳐 쓰므로 다른 주석·순서·흐름 표기는 그대로 남는다. 다 쓰고 나서 YAML 을 다시 읽어 값이 명세와 같은지 확인한다.
아직 items.yml 에 없는 세트(json new_sets — gear_spec 새 6세트)는 건너뛴다 (P3 생성기가 같은 표로 만든다).
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "plugin/src/main/resources/content/items.yml"
SPEC = ROOT / "tools/data/035/armor_looks.json"

ITEM_RE = re.compile(r"^  ([a-z0-9_]+):\s*(#.*)?$")
STAT_NAMES = {"STR": "힘", "DEX": "민첩", "INT": "지능", "VIT": "체력", "WIS": "정신", "LUK": "행운"}


def budget(level):
    return 0 if level <= 2 else math.ceil(2.75 * (level - 1) - 1e-9)


def split(total, order):
    """합 total 을 order(앞이 큰 쪽) 로 나눈다: 두 개 60/40 (앞 올림), 세 개 50/30/20 (앞 올림 · 가운데 반올림 · 끝 나머지)."""
    if total <= 0 or not order:
        return {}
    if len(order) == 1:
        return {order[0]: total}
    if len(order) == 2:
        a = math.ceil(0.6 * total - 1e-9)
        return {order[0]: a, order[1]: total - a}
    a = math.ceil(0.5 * total - 1e-9)
    b = int(math.floor(0.3 * total + 0.5))
    return {order[0]: a, order[1]: b, order[2]: total - a - b}


def flow(m):
    return "{" + ", ".join(f"{k}: {v}" for k, v in m.items()) + "}"


def req_text(m):
    return " · ".join(f"{STAT_NAMES[k]} {v}" for k, v in m.items())


def blocks(lines, start, end):
    """lines[start:end] 안의 2칸 들여쓴 항목 → {id: (첫 줄, 끝 줄 다음)}."""
    out = {}
    i = start
    while i < end:
        m = ITEM_RE.match(lines[i])
        if m:
            j = i + 1
            while j < end:
                l = lines[j]
                if l.strip() and (len(l) - len(l.lstrip())) <= 2:
                    break
                j += 1
            out[m.group(1)] = (i, j)
            i = j
        else:
            i += 1
    return out


def field(lines, a, b, key):
    want = "    " + key + ":"
    for k in range(a + 1, b):
        if lines[k].startswith(want):
            return k
    return None


def expected(spec, items, sets):
    """방어구 id → (requires, rename, look) 기대값."""
    out = {}
    for iid, it in items.items():
        if it.get("type") != "armor":
            continue
        sid = it.get("set_bonus") or it.get("armor_set")
        if iid in spec["item_pairs"]:
            pair = spec["item_pairs"][iid]["pair"]
        elif sid in spec["set_pairs"]:
            pair = spec["set_pairs"][sid]["pair"]
        else:
            sys.exit(f"{iid}: 요구 짝이 없음 (set_pairs / item_pairs)")
        req = split(budget(int(it.get("level_req", 1))), pair)
        rename = spec["stats_rename"].get(sid, {}) if sid in sets else {}
        look = spec["item_looks"].get(iid)
        out[iid] = (req, rename, look)
    return out


def apply(lines, spec, changes):
    data = yaml.safe_load("\n".join(lines))
    items, sets = data["items"], data["sets"]
    want = expected(spec, items, sets)
    items_at = next(i for i, l in enumerate(lines) if l.startswith("items:"))
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    # 아래에서 위로 고쳐 줄 번호가 안 밀리게
    item_blocks = blocks(lines, items_at + 1, sets_at)
    set_blocks = blocks(lines, sets_at + 1, len(lines))
    for sid in reversed(list(set_blocks)):
        a, b = set_blocks[sid]
        k = field(lines, a, b, "look_effects")
        if sid in spec["plain_sets"]:
            if k is None:
                at = field(lines, a, b, "look") or a
                lines.insert(at + 1, "    look_effects: false")
                changes.append(f"sets.{sid}: + look_effects: false")
            elif lines[k].strip() != "look_effects: false":
                lines[k] = "    look_effects: false"
                changes.append(f"sets.{sid}: look_effects → false")
    for iid in reversed(list(item_blocks)):
        if iid not in want:
            continue
        a, b = item_blocks[iid]
        req, rename, look = want[iid]
        # 스탯 줄 이름
        k = field(lines, a, b, "stats")
        if rename:
            line = lines[k]
            new = line
            for old, to in rename.items():
                new = re.sub(r"([{,]\s*)" + old + r"(\s*:)", r"\g<1>" + to + r"\g<2>", new)
            if new != line:
                lines[k] = new
                changes.append(f"{iid}: stats {rename}")
        # requires_any 지움
        k = field(lines, a, b, "requires_any")
        if k is not None:
            changes.append(f"{iid}: - {lines[k].strip()}")
            del lines[k]
            b -= 1
        k = field(lines, a, b, "requires")
        text = "    requires: " + flow(req)
        if req:
            if k is None:
                at = field(lines, a, b, "level_req")
                lines.insert(at + 1, text)
                changes.append(f"{iid}: + requires: {flow(req)}")
                b += 1
            elif lines[k].rstrip() != text:
                changes.append(f"{iid}: {lines[k].strip()} → requires: {flow(req)}")
                lines[k] = text
        elif k is not None:
            changes.append(f"{iid}: - {lines[k].strip()}")
            del lines[k]
            b -= 1
        # 세트 없는 투구의 겉모습
        k = field(lines, a, b, "look")
        if look:
            text = "    look: " + look
            if k is None:
                at = field(lines, a, b, "armor_slot")
                lines.insert(at + 1, text)
                changes.append(f"{iid}: + look: {look}")
            elif lines[k].rstrip() != text:
                lines[k] = text
                changes.append(f"{iid}: look → {look}")
    # 세트 머리 주석: "… Lv8 · 요구 체력 18 ═══" → 새 요구
    for i, l in enumerate(lines):
        m = re.match(r"^(  # ═+ 방어구 세트 · .*\(([a-z0-9_]+)\).*? · )요구 [^═]*?( ═+)$", l)
        if not m:
            continue
        sid = m.group(2)
        piece = next((iid for iid in want if (items[iid].get("set_bonus") or items[iid].get("armor_set")) == sid), None)
        if piece is None:
            continue
        req = want[piece][0]
        new = m.group(1) + ("요구 " + req_text(req) if req else "요구 없음") + m.group(3)
        if new != l:
            lines[i] = new
            changes.append(f"주석 sets.{sid}: 요구 {req_text(req) or '없음'}")
    return want


def verify(text, spec):
    data = yaml.safe_load(text)
    items, sets = data["items"], data["sets"]
    want = expected(spec, items, sets)
    bad = []
    for iid, (req, rename, look) in want.items():
        it = items[iid]
        if (it.get("requires") or {}) != req:
            bad.append(f"{iid}: requires {it.get('requires')} ≠ {req}")
        if it.get("requires_any"):
            bad.append(f"{iid}: requires_any 남음")
        for old, to in rename.items():
            if old in it["stats"]:
                bad.append(f"{iid}: 스탯 줄 {old} 이 남음 (→ {to})")
        if look and it.get("look") != look:
            bad.append(f"{iid}: look {it.get('look')} ≠ {look}")
    for sid in spec["plain_sets"]:
        if sets[sid].get("look_effects") is not False:
            bad.append(f"sets.{sid}: look_effects: false 없음")
    for sid, s in sets.items():
        if sid not in spec["plain_sets"] and s.get("look_effects") is False:
            bad.append(f"sets.{sid}: 평상복이 아닌데 look_effects: false")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    text = ITEMS.read_text(encoding="utf-8")
    lines = text.split("\n")
    changes = []
    apply(lines, spec, changes)
    new = "\n".join(lines)
    if a.check:
        bad = verify(text, spec)
        for b in bad:
            print("✘", b)
        if changes:
            print(f"고칠 것 {len(changes)}개 (python3 tools/gen_035_looks.py)")
        print("✔ 명세와 같음" if not bad and not changes else "")
        sys.exit(1 if bad or changes else 0)
    for c in changes:
        print(c)
    if a.dry_run:
        print(f"(dry-run) 바뀔 줄 {len(changes)}개")
        return
    if new != text:
        ITEMS.write_text(new, encoding="utf-8")
    bad = verify(new, spec)
    for b in bad:
        print("✘", b)
    if bad:
        sys.exit(1)
    print(f"✔ items.yml — 바뀐 것 {len(changes)}개, 방어구 요구·겉모습·줄 이름이 명세와 같음")


if __name__ == "__main__":
    main()
