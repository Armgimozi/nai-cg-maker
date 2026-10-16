#!/usr/bin/env python3
"""
0.3.6 Q6 — 도안 (blueprint) 데이터 단계. tools/gen_035_content.py 의 generate() 끝에서 돈다 (메모리 단계, 파일을 따로 쓰지 않는다).

  · items.yml: 도안 아이템 하나 `blueprint` (type: blueprint — 가르치는 레시피 id 는 아이템 PDC, 이름·색은 플러그인이 그 장비로 그린다)
  · loot.yml: 도안 항목 {blueprint: 단계, chance} 을 이 표들 entries 끝에 하나씩 (같은 표에 다시 돌려도 하나):
        정예(mobs.yml rank: elite 의 drops) · 보스(bosses.yml drops) · 미로 금·철 상자(maze_chest_gold/iron_f<층>) ·
        보물방(treasure_floor_<층>) · 금고·미믹(hoard_f<층>) · 특별 시련(special_trial_f<층>)
    단계 = 그 층 번호. 플러그인이 이웃 단계를 장비 풀처럼 2 : 7 : 1 로 섞어 도안 하나를 고른다 (items/blueprint/BlueprintRules).

확률 (CHANCE, 보통·솔로·LUK 0 기준 — 시험 BlueprintLootTest 가 같은 1회 모형으로 본다):
  한 층 끝까지 1회에 도안 약 2~3장 (1~3층 2.0 · 4~6층 2.4 · 7·8층 2.7 · 9·10층 2.9). 원하는 장비 하나의 도안(빌드에 맞는 것)을
  그 단계 층에서 얻기까지 기대 회차 = 그 장비를 드롭으로 찾는 회차(DropRateWindow: 몬스터·상자 2~4, 정예·시련·금고·특별 3.5~7.5)와
  비슷하게 — 가운데값 6.3회 (희귀 7.0 · 영웅 6.2 · 전설 4.5), 가장 긴 것 약 9회. 레시피가 적은 단계(2층 등)는 더 빨리 모인다.
  희귀 도안은 상인 핀이 날마다 3개 바꿔 판다 (config blueprints.shop_*).
"""
import re

import yaml

ITEM_ID = "blueprint"
# 표 종류 → 도안 확률 (그 표를 한 번 굴릴 때)
CHANCE = {
    "elite": 0.20,
    "boss": 0.40,
    "maze_gold": 0.08,
    "maze_iron": 0.04,
    "treasure": 0.06,
    "hoard": 0.10,
    "special": 0.40,
}
ITEM_HEADER = "  # ═════════ 도안 (0.3.6 — 희귀 이상 장비 레시피는 도안을 배워야 만든다. 우클릭: 영구히 배움) ═════════"
ITEM_BLOCK = [
    f"  {ITEM_ID}:",
    '    name: "도안"',
    "    type: blueprint",
    "    rarity: rare",
    "    level_req: 1",
    "    sources: [elite, boss, chest, hoard, special, shop]",
    "    model: {shape: icon}",
    '    texture: {style: blueprint, palette: ["#3a2a18", "#7a5a34", "#d8c49a", "#f1e6c8", "#fff8e8"]}',
    '    lore: "장비 하나를 만드는 법이 적힌 양피지. 우클릭하면 배운다."',
]
LOOT_DOC_AFTER = "#      {pick: [{table: 하위테이블, weight: n}, …], chance}   chance 를 넘으면 무게대로 하위 테이블 하나를 골라 굴림 (0.3.5, 순환 금지)"
LOOT_DOC = ("#      {blueprint: 단계, chance}                     도안 하나 (0.3.6) — 희귀 이상 장비 레시피 중 결과 단계가 그 단계 ±1 인 것,"
            " 이웃 단계 몫 2 : 7 : 1 (tools/gen_036_blueprints.py)")
BP_LINE = re.compile(r"^      - \{blueprint: ")
TABLE_RE = re.compile(r"^  ([a-z0-9_]+):\s*(#.*)?$")


def targets(mobs, bosses, floors):
    """도안 항목을 넣을 표 → (단계, 종류)."""
    out = {}
    for m in mobs.values():
        if m.get("rank") == "elite" and m.get("drops") and m.get("floor"):
            out[m["drops"]] = (int(m["floor"]), "elite")
    for b in bosses.values():
        if b.get("drops") and b.get("floor"):
            out[b["drops"]] = (int(b["floor"]), "boss")
    for n in floors:
        out[f"maze_chest_gold_f{n}"] = (n, "maze_gold")
        out[f"maze_chest_iron_f{n}"] = (n, "maze_iron")
        out[f"treasure_floor_{n}"] = (n, "treasure")
        out[f"hoard_f{n:02d}"] = (n, "hoard")
        out[f"special_trial_f{n:02d}"] = (n, "special")
    return out


def _tables(lines):
    at = next(i for i, l in enumerate(lines) if l.startswith("tables:"))
    out = {}
    i = at + 1
    while i < len(lines):
        m = TABLE_RE.match(lines[i])
        if m:
            j = i + 1
            while j < len(lines) and not (lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) <= 2):
                j += 1
            while j > i + 1 and not lines[j - 1].strip():
                j -= 1
            out[m.group(1)] = (i, j)
            i = j
        else:
            i += 1
    return out


def apply_loot(text, tgt, changes):
    lines = text.split("\n")
    if LOOT_DOC not in lines and LOOT_DOC_AFTER in lines:
        k = lines.index(LOOT_DOC_AFTER)
        lines.insert(k + 1, LOOT_DOC)
    tb = _tables(lines)
    # 아래 표부터 고쳐 위쪽 줄 번호가 흔들리지 않게
    for tid, (a, b) in sorted(tb.items(), key=lambda kv: -kv[1][0]):
        want = tgt.get(tid)
        body = lines[a + 1:b]
        new = [l for l in body if not BP_LINE.match(l)]
        if want is not None:
            tier, kind = want
            row = f"      - {{blueprint: {tier}, chance: {CHANCE[kind]}}}"
            k = next((i for i, l in enumerate(new) if l.startswith("    entries:")), None)
            if k is None:
                new.append("    entries:")
                new.append(row)
            else:
                if new[k].strip() == "entries: []":
                    new[k] = "    entries:"
                end = k + 1
                while end < len(new) and new[end].startswith("      "):
                    end += 1
                new.insert(end, row)
        if new != body:
            lines[a + 1:b] = new
            changes.append(f"(도안) loot.{tid}")
    return "\n".join(lines)


def apply_items(text, changes):
    lines = text.split("\n")
    # 있던 도안 블록·머리 지우기
    out = []
    i = 0
    while i < len(lines):
        l = lines[i]
        if l == ITEM_HEADER:
            if out and not out[-1].strip():
                out.pop()
            i += 1
            continue
        if l == f"  {ITEM_ID}:":
            i += 1
            while i < len(lines) and lines[i].startswith("    "):
                i += 1
            continue
        out.append(l)
        i += 1
    sets_at = next(i for i, l in enumerate(out) if l.startswith("sets:"))
    k = sets_at
    while k > 0 and (not out[k - 1].strip() or out[k - 1].startswith("#")):
        k -= 1
    block = ["", ITEM_HEADER] + ITEM_BLOCK
    out[k:k] = block
    res = "\n".join(out)
    if res != text:
        changes.append("(도안) items.blueprint")
    return res


def apply(out, mobs, bosses, floors, changes):
    """gen_035_content.generate() 의 out{items, loot, …} 을 고친다."""
    tgt = targets(mobs, bosses, floors)
    out["items"] = apply_items(out["items"], changes)
    out["loot"] = apply_loot(out["loot"], tgt, changes)
    return out


def verify(texts, mobs, bosses, floors):
    bad = []
    items = yaml.safe_load(texts["items"])["items"]
    if (items.get(ITEM_ID) or {}).get("type") != "blueprint":
        bad.append("items.blueprint 없음")
    tables = yaml.safe_load(texts["loot"])["tables"]
    for tid, (tier, kind) in targets(mobs, bosses, floors).items():
        t = tables.get(tid)
        if t is None:
            continue
        rows = [e for e in (t.get("entries") or []) if "blueprint" in e]
        if len(rows) != 1 or rows[0]["blueprint"] != tier or rows[0]["chance"] != CHANCE[kind]:
            bad.append(f"loot.{tid}: 도안 항목 {rows}")
    return bad
