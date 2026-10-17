#!/usr/bin/env python3
"""
0.3.7 — 신화 무기 6 → 12 (직업마다 둘, 짝 신화와 다른 무기 종류). tools/gen_035_content.py 의 generate() 안에서 도는 메모리 단계
MYTH037 (BP036 뒤, 맨 마지막). 따로 돌리지 않는다: `python3 tools/gen_035_content.py [--check]` 가 부른다.

입력 = tools/data/037/mythic_037.json (최종 명세 final_spec.json 사본, 손으로 고치지 않는다):
  items    새 신화 6 블록 (items.yml 꼴) — 짝 신화 블록 바로 뒤에 넣는다
  loot     8·9·10층 보스 · 특별 시련 · 금고·미믹 표에 넣을 줄
             {item: 옛 신화, chance}          신화 드롭 (넬카르 표만, 모든 난이도) — 10층의 옛 신화 6 줄(one_of 0.04)을 한 자루마다 따로 0.2 줄 6개로
             {blueprint_of: [레시피 id …], chance}  신화 도안 (그 레시피 중 하나 — 빌드 편향 own_build_bias 그대로).
                                              새 6 은 한 줄 (주 능력치가 모두 달라 어느 빌드든 몫이 같다), 옛 6 은 한 장씩
  recipes  신화 12 레시피 (recipes.yml 끝 '신화 무기' 칸, 대장간 · 도안이 있어야 만든다)
고유 효과 블록은 tools/data/035/unique_assign.json 과 같아야 한다 (gen_035_unique.unique_block — 다르면 멈춘다).
획득처(sources)는 이 단계 뒤 최종 루팅·레시피로 다시 센다 → 옛 신화 6 = [boss, craft] (신화만 획득처 종류가 둘) · 새 신화 6 = [craft].
레시피에는 넬카르만 주는 재료가 없다 (verify 가 막는다) — 넬카르를 못 잡아도 만든다.

다시 돌려도 같다: generate() 가 맨 처음 strip() 으로 이 단계가 넣은 것(새 블록 · 루팅 줄 · 레시피 칸 · 글 줄)을 걷어 내고
0.3.5 · 0.3.6 단계를 돌린 뒤 마지막에 apply() 로 다시 넣는다 — 앞 단계는 0.3.6.1 과 똑같은 입력을 본다
(0.3.6 단계는 base_0351.json 에 없는 장비 레시피를 보면 멈추고, 0.3.5 검사는 무기 245개를 센다).
"""
import copy
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools/data/037/mythic_037.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_035_unique as UNIQUE_GEN  # noqa: E402

ITEM_ORDER = ["name", "type", "attack", "rarity", "level_req", "requires", "tier", "stats", "aura", "pool", "sources", "unique",
              "weapon_skills", "model", "texture", "lore"]
ITEM_MARK = "  # ── 0.3.7 둘째 신화 (tools/gen_037_mythic.py — 손으로 고치지 않음) ──"
ROW = "      - "

# 글 줄 (앞 단계가 쓴 줄 → 0.3.7 줄). strip() 은 거꾸로 되돌린다.
TEXT_SUBS = {
    "items": [
        (["#                영웅·전설·신화 무기는 획득처 종류 1개 — 보스 고유 = 그 보스만 (제작법 없음) · 대장간 = 대장간만 (드롭 없음) ·",
          "#                몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예 중 하나 (몬스터·상자 = drop+chest 한 종류)"],
         ["#                영웅·전설 무기는 획득처 종류 1개 — 보스 고유 = 그 보스만 (제작법 없음) · 대장간 = 대장간만 (드롭 없음) ·",
          "#                몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예 중 하나 (몬스터·상자 = drop+chest 한 종류)",
          "#                신화 무기(0.3.7, 직업마다 둘)만 따로 — 옛 6 = boss(넬카르) + craft(신화 도안을 배운 대장간) · 새 6 = craft 만"]),
        (['    lore: "심연의 심장 넬카르에서 떨어져 나온 조각. 아직도 아주 느리게 박동한다. 대장장이 두르간에게 가져가면 넬카르가 지키던 전설 무기를 벼릴 수 있다."'],
         ['    lore: "심연의 심장 넬카르에서 떨어져 나온 조각. 아직도 아주 느리게 박동한다. 넬카르의 장비와 신화 무기를 끝까지 강화할 때 든다."']),
    ],
    "loot": [
        (["#  영웅·전설·신화 무기는 획득처 종류 1개 (보스 · 대장간 · 몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예)"],
         ["#  영웅·전설 무기는 획득처 종류 1개 (보스 · 대장간 · 몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예)",
          "#  신화 무기 12 (0.3.7): 옛 6 은 넬카르가 한 자루마다 따로 20% (item 줄 여섯) + 대장간, 새 6 은 대장간만 (드롭 없음).",
          "#    신화 도안 {blueprint_of}: 8·9·10층 보스 · 특별 시련 · 금고·미믹 — 새 6 은 한 줄, 옛 6 은 한 장씩. 넬카르를 안 잡아도 모인다.",
          "#    모든 난이도. 신화 아이템은 넬카르만 준다 (tools/gen_037_mythic.py)"]),
    ],
    "recipes": [
        (["# 레시피가 없는 장비: 1층 Lv1 공용 무기 · 몬스터·상자 전용 공용 무기(2·3·4·5·7층) · 영웅 이상 보스 고유 무기(2~10층, 보스만 — 핵은 보스 방어구·장신구·강화에)",
          "#                   · 신화 · 넬카르의 심장 · 칭호 보상 · 수련생(시작 지급).  6·8·9·10층 공용 무기(영웅)는 대장간 전용 (몹·상자에서 안 나옴)",
          "# 영웅·전설·신화 무기는 획득처가 1곳이다 — 여기 있는 영웅 무기는 드롭이 없고, 보스 고유 무기는 여기 없다."],
         ["# 레시피가 없는 장비: 1층 Lv1 공용 무기 · 몬스터·상자 전용 공용 무기(2·3·4·5·7층) · 영웅·전설 보스 고유 무기(2~10층, 보스만 — 핵은 보스 방어구·장신구·강화에)",
          "#                   · 넬카르의 심장 · 칭호 보상 · 수련생(시작 지급).  6·8·9·10층 공용 무기(영웅)는 대장간 전용 (몹·상자에서 안 나옴)",
          "# 영웅·전설 무기는 획득처가 1곳이다 — 여기 있는 영웅 무기는 드롭이 없고, 보스 고유 무기는 여기 없다.",
          "# 신화 무기 12 (0.3.7)는 맨 끝 '신화 무기' 칸 (신화 도안을 배워야 보인다). 옛 6 은 넬카르도 떨어뜨리고, 새 6 은 여기서만 만든다.",
          "#   재료는 10층 몹·정예·상자 것 + 오리하르콘 주괴 · 용혈석 — 넬카르 핵은 없다 (못 잡아도 만든다). 다른 층 재료 금지는 그대로."]),
    ],
}


TEXT_SUBS_PREV = {  # HEAD 99c35149 (CR37 전) 이 쓴 글 줄 — strip() 만 되돌린다
    "items": [
        (["#                영웅·전설·신화 무기는 획득처 종류 1개 — 보스 고유 = 그 보스만 (제작법 없음) · 대장간 = 대장간만 (드롭 없음) ·",
          "#                몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예 중 하나 (몬스터·상자 = drop+chest 한 종류)"],
         ["#                영웅·전설 무기는 획득처 종류 1개 — 보스 고유 = 그 보스만 (제작법 없음) · 대장간 = 대장간만 (드롭 없음) ·",
          "#                몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예 중 하나 (몬스터·상자 = drop+chest 한 종류)",
          "#                신화 무기(0.3.7, 직업마다 둘)만 둘 — boss(8·9·10층 보스) + craft(신화 도안을 배운 대장간)"]),
        (['    lore: "심연의 심장 넬카르에서 떨어져 나온 조각. 아직도 아주 느리게 박동한다. 대장장이 두르간에게 가져가면 넬카르가 지키던 전설 무기를 벼릴 수 있다."'],
         ['    lore: "심연의 심장 넬카르에서 떨어져 나온 조각. 아직도 아주 느리게 박동한다. 대장장이 두르간에게 가져가면 신화 무기를 벼릴 수 있다."']),
    ],
    "loot": [
        (["#  영웅·전설·신화 무기는 획득처 종류 1개 (보스 · 대장간 · 몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예)"],
         ["#  영웅·전설 무기는 획득처 종류 1개 (보스 · 대장간 · 몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예)",
          "#  신화 무기 12 (0.3.7)는 보스 + 대장간: 8·9·10층 보스 {one_of} (넬카르가 가장 높음, 모든 난이도) · 신화 도안 {blueprint_of} 은",
          "#    8·9·10층 보스 · 특별 시련 · 금고·미믹. 아이템 자체는 보스만 준다 (tools/gen_037_mythic.py)"]),
    ],
    "recipes": [
        (["# 레시피가 없는 장비: 1층 Lv1 공용 무기 · 몬스터·상자 전용 공용 무기(2·3·4·5·7층) · 영웅 이상 보스 고유 무기(2~10층, 보스만 — 핵은 보스 방어구·장신구·강화에)",
          "#                   · 신화 · 넬카르의 심장 · 칭호 보상 · 수련생(시작 지급).  6·8·9·10층 공용 무기(영웅)는 대장간 전용 (몹·상자에서 안 나옴)",
          "# 영웅·전설·신화 무기는 획득처가 1곳이다 — 여기 있는 영웅 무기는 드롭이 없고, 보스 고유 무기는 여기 없다."],
         ["# 레시피가 없는 장비: 1층 Lv1 공용 무기 · 몬스터·상자 전용 공용 무기(2·3·4·5·7층) · 영웅·전설 보스 고유 무기(2~10층, 보스만 — 핵은 보스 방어구·장신구·강화에)",
          "#                   · 넬카르의 심장 · 칭호 보상 · 수련생(시작 지급).  6·8·9·10층 공용 무기(영웅)는 대장간 전용 (몹·상자에서 안 나옴)",
          "# 영웅·전설 무기는 획득처가 1곳이다 — 여기 있는 영웅 무기는 드롭이 없고, 보스 고유 무기는 여기 없다.",
          "# 신화 무기 12 (0.3.7)만 둘이다 — 8·9·10층 보스 드롭 + 맨 끝 '신화 무기' 칸 (신화 도안을 배워야 보인다).",
          "#   재료는 10층 것(핵 50 — 넬카르 50번) + 오리하르콘 주괴 · 용혈석. 다른 층 재료 금지는 그대로."]),
    ],
}


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def emit_item(G, iid, it):
    bad = [k for k in it if k not in ITEM_ORDER]
    if bad:
        raise SystemExit(f"[037] {iid}: 모르는 키 {bad}")
    out = [f"  {iid}:"]
    for k in ITEM_ORDER:
        if k not in it:
            continue
        v = it[k]
        if k == "weapon_skills":
            out.append("    weapon_skills:")
            for s in v:
                out += G.emit_skill(s)
        elif k in ("name", "lore"):
            out.append(f"    {k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            out.append(f"    {k}: {G.flow(v)}")
    return out


def row_text(G, r):
    return ROW + G.flow(r["entry"]) + (f"   # {r['note']}" if r.get("note") else "")


def parse_row(line):
    if not line.startswith(ROW):
        return None
    try:
        return yaml.safe_load(line[len(ROW):].split("   #")[0])
    except yaml.YAMLError:
        return None


def sub_lines(lines, old, new):
    """lines 안의 연속 줄 old 를 new 로 (한 번). @return 바꿨는지."""
    n = len(old)
    for i in range(len(lines) - n + 1):
        if lines[i:i + n] == old:
            lines[i:i + n] = new
            return True
    return False


def _tables(G, lines):
    at = next(i for i, l in enumerate(lines) if l.startswith("tables:"))
    return G.blocks(lines, at + 1, len(lines))


def _entry_rows(lines, a, b):
    k = next((j for j in range(a + 1, b) if lines[j].startswith("    entries:")), None)
    if k is None:
        return None, []
    rows = []
    j = k + 1
    while j < b and lines[j].startswith(ROW):
        rows.append(j)
        j += 1
    return k, rows


def _is_mythic_row(e, myth):
    """이 단계가 넣는 줄인가: 신화 도안(blueprint_of) · 신화 item · 신화가 든 one_of."""
    if not isinstance(e, dict):
        return False
    return "blueprint_of" in e or e.get("item") in myth or any(x in myth for x in (e.get("one_of") or []))


# ───────────────────────── 걷어 내기 (generate() 맨 처음) ─────────────────────────
def strip(G, texts, data=None):
    """이 단계가 넣은 것을 걷어 낸 texts (items · loot · recipes, 나머지는 그대로). 넣은 적이 없으면 그대로 돌려준다.
    G = gen_035_content 모듈."""
    data = data or load()
    out = dict(texts)
    # items: 새 6 블록 + 표시 줄
    lines = out["items"].split("\n")
    new = set(data["items"])
    i = 0
    keep = []
    while i < len(lines):
        l = lines[i]
        if l == ITEM_MARK:
            i += 1
            continue
        m = G.ITEM_RE.match(l)
        if m and m.group(1) in new:
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or lines[i].startswith("      ")):
                i += 1
            continue
        keep.append(l)
        i += 1
    for old, nw in TEXT_SUBS["items"] + TEXT_SUBS_PREV["items"]:
        sub_lines(keep, nw, old)
    out["items"] = "\n".join(keep)
    # loot: 넣은 줄 지우고 10층 줄 되돌림
    lines = out["loot"].split("\n")
    for old, nw in TEXT_SUBS["loot"] + TEXT_SUBS_PREV["loot"]:
        sub_lines(lines, nw, old)
    tb = _tables(G, lines)
    myth = set(data["mythics"])
    for tid, spec in sorted(data["loot"].items(), key=lambda kv: -tb.get(kv[0], (0, 0))[0]):
        if tid not in tb:
            continue
        a, b = tb[tid]
        _, rows = _entry_rows(lines, a, b)
        rep = spec.get("replace")
        # 명세가 바뀌어도 걷힌다: 이 표의 신화 줄(신화 item · 신화 one_of · blueprint_of)을 모두 걷고, 첫 신화 줄은 0.3.6.1 줄(rep.from)로
        hits = [j for j in rows if _is_mythic_row(parse_row(lines[j]), myth)]
        for j in reversed(hits):
            if rep and j == hits[0]:
                lines[j] = ROW + G.flow(rep["from"])
            else:
                del lines[j]
    out["loot"] = "\n".join(lines)
    # recipes: 신화 칸 (머리 줄부터 다음 머리 줄 전까지)
    lines = out["recipes"].split("\n")
    for old, nw in TEXT_SUBS["recipes"] + TEXT_SUBS_PREV["recipes"]:
        sub_lines(lines, nw, old)
    if data["recipe_header"] in lines:
        h = lines.index(data["recipe_header"])
        j = h + 1
        while j < len(lines) and not lines[j].startswith("  # ═════════"):
            j += 1
        del lines[h:j]
        if h > 0 and not lines[h - 1].strip() and (h >= len(lines) or not lines[h].strip()):
            del lines[h - 1]          # 칸 앞 빈 줄 (apply() 가 넣은 것)
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append("")
    out["recipes"] = "\n".join(lines)
    return out


# ───────────────────────── 넣기 (generate() 맨 끝, BP036 뒤) ─────────────────────────
def apply(G, out, mobs, bosses, floors, titles, config, changes, data=None):
    data = data or load()
    out = dict(out)
    ua = UNIQUE_GEN.load()
    for wid, it in data["items"].items():
        want = UNIQUE_GEN.unique_block(ua[wid]) if wid in ua else None
        if it.get("unique") != want:
            raise SystemExit(f"[037] {wid}: 명세 unique {it.get('unique')} ≠ unique_assign.json {want}")
    # ── items: 짝 신화 블록 뒤에 새 블록 ──
    lines = out["items"].split("\n")
    for old, nw in TEXT_SUBS["items"]:
        if sub_lines(lines, old, nw):
            changes.append("(037) items 글 줄")
    items_at = next(i for i, l in enumerate(lines) if l.startswith("items:"))
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    ib = G.blocks(lines, items_at + 1, sets_at)
    for wid in sorted(data["items"], key=lambda w: -ib[data["pair"][w]][1]):
        if wid in ib:
            raise SystemExit(f"[037] items.{wid}: 이미 있음 (strip() 을 먼저)")
        a, b = ib[data["pair"][wid]]
        lines[b:b] = [ITEM_MARK] + emit_item(G, wid, data["items"][wid])
        changes.append(f"(037) items.{wid}")
    out["items"] = "\n".join(lines)
    # ── loot ──
    lines = out["loot"].split("\n")
    for old, nw in TEXT_SUBS["loot"]:
        if sub_lines(lines, old, nw):
            changes.append("(037) loot 글 줄")
    tb = _tables(G, lines)
    for tid, spec in sorted(data["loot"].items(), key=lambda kv: -tb[kv[0]][0]):
        a, b = tb[tid]
        k, rows = _entry_rows(lines, a, b)
        if k is None:
            raise SystemExit(f"[037] loot.{tid}: entries 없음")
        rep = spec.get("replace")
        if rep:
            hit = [j for j in rows if parse_row(lines[j]) == rep["from"]]
            if len(hit) != 1:
                raise SystemExit(f"[037] loot.{tid}: 바꿀 줄 {rep['from']} 이 {len(hit)}개")
            lines[hit[0]] = row_text(G, {"entry": rep["to"], "note": rep.get("note")})
        end = (rows[-1] + 1) if rows else k + 1
        if lines[k].strip() == "entries: []":
            lines[k] = "    entries:"
        lines[end:end] = [row_text(G, r) for r in spec.get("append") or []]
        changes.append(f"(037) loot.{tid}")
    out["loot"] = "\n".join(lines)
    # ── recipes: 끝에 신화 칸 ──
    lines = out["recipes"].split("\n")
    for old, nw in TEXT_SUBS["recipes"]:
        if sub_lines(lines, old, nw):
            changes.append("(037) recipes 글 줄")
    items_y = yaml.safe_load(out["items"])["items"]
    while lines and not lines[-1].strip():
        lines.pop()
    lines += ["", data["recipe_header"]]
    for rid, r in data["recipes"].items():
        lines.append(f"  {rid}:   # {items_y[r['result']]['name']}")
        for key in ("result", "category", "station"):
            lines.append(f"    {key}: {r[key]}")
        lines.append(f"    materials: {G.flow(r['materials'])}")
        lines.append(f"    gold: {r['gold']}")
        lines.append(f"    level_req: {r['level_req']}")
    lines.append("")
    out["recipes"] = "\n".join(lines)
    changes.append(f"(037) recipes 신화 {len(data['recipes'])}")
    # ── 획득처를 최종 루팅·레시피로 다시 센다 ──
    y = {n: yaml.safe_load(out[n]) for n in ("items", "loot", "recipes", "npcs")}
    src = G.compute_sources(y["items"]["items"], y["loot"]["tables"], y["recipes"]["recipes"], mobs, bosses, floors,
                            y["npcs"]["npcs"], titles, config)
    lines = out["items"].split("\n")
    items_at = next(i for i, l in enumerate(lines) if l.startswith("items:"))
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    ib = G.blocks(lines, items_at + 1, sets_at)
    for iid, s in src.items():
        if iid in ib and s != (y["items"]["items"][iid].get("sources") or []):
            a, b = ib[iid]
            k = G.field(lines, a, b, "sources")
            if k is not None:
                lines[k] = f"    sources: {G.flow(s)}"
                changes.append(f"(037) {iid}: sources {s}")
    out["items"] = "\n".join(lines)
    return out


# ───────────────────────── 검사 ─────────────────────────
def verify(texts, data=None):
    data = data or load()
    bad = []
    items = yaml.safe_load(texts["items"])["items"]
    tables = yaml.safe_load(texts["loot"])["tables"]
    recipes = yaml.safe_load(texts["recipes"])["recipes"]
    ua = UNIQUE_GEN.load()
    myth = [k for k, v in items.items() if v.get("type") == "weapon" and v.get("rarity") == "mythic"]
    if sorted(myth) != sorted(data["mythics"]):
        bad.append(f"신화 무기 {sorted(myth)} ≠ 명세 {sorted(data['mythics'])}")
    for wid, it in data["items"].items():
        got = items.get(wid)
        if got is None:
            bad.append(f"items.{wid} 없음")
            continue
        if got != it:
            diff = [k for k in set(got) | set(it) if got.get(k) != it.get(k)]
            bad.append(f"items.{wid} 가 명세와 다름: {diff}")
    for wid in data["mythics"]:
        v = items.get(wid) or {}
        want_src = ["craft"] if wid in data["new"] else ["boss", "craft"]
        if v.get("sources") != want_src:
            bad.append(f"items.{wid}.sources {v.get('sources')} (옛 신화 = [boss, craft] · 새 신화 = [craft])")
        for m in (recipes.get(wid) or {}).get("materials") or {}:
            if (items.get(m) or {}).get("sources") == ["boss"]:
                bad.append(f"recipes.{wid}: {m} 는 보스만 준다 (넬카르를 못 잡아도 만들어야 함)")
        if wid in ua and v.get("unique") != UNIQUE_GEN.unique_block(ua[wid]):
            bad.append(f"items.{wid}.unique 가 unique_assign.json 과 다름")
        if wid not in ua:
            bad.append(f"unique_assign.json 에 {wid} 없음")
        if recipes.get(wid) != data["recipes"].get(wid):
            bad.append(f"recipes.{wid} 가 명세와 다름: {recipes.get(wid)}")
    for tid, spec in data["loot"].items():
        ents = (tables.get(tid) or {}).get("entries") or []
        want = [r["entry"] for r in spec.get("append") or []] + ([spec["replace"]["to"]] if spec.get("replace") else [])
        for e in want:
            if ents.count(e) != 1:
                bad.append(f"loot.{tid}: {e} 가 {ents.count(e)}번")
        if spec.get("replace") and spec["replace"]["from"] in ents:
            bad.append(f"loot.{tid}: 옛 줄 {spec['replace']['from']} 이 남음")
    # 신화 아이템은 넬카르 표에서만 (옛 6 만, 새 6 은 드롭 줄이 없다) · 도안 줄은 신화 레시피만 · 모든 난이도 (min_difficulty 없음)
    boss_tables = {"floor10_boss"}
    for tid, t in tables.items():
        for e in (t.get("guaranteed") or []) + (t.get("entries") or []):
            ids = [e["item"]] if "item" in e else list(e.get("one_of") or [])
            if any(x in data["mythics"] for x in ids):
                if tid not in boss_tables:
                    bad.append(f"loot.{tid}: 신화 아이템은 넬카르 표에만")
                if any(x in data["new"] for x in ids):
                    bad.append(f"loot.{tid}: 새 신화 {ids} 는 드롭 줄이 없어야 함 (도안 제작만)")
                if not all(x in data["mythics"] for x in ids):
                    bad.append(f"loot.{tid}: 신화 줄에 신화가 아닌 것 {ids}")
            if "blueprint_of" in e:
                if any(x not in data["recipes"] for x in e["blueprint_of"]):
                    bad.append(f"loot.{tid}: blueprint_of 에 신화 레시피가 아닌 것 {e['blueprint_of']}")
            if ("blueprint_of" in e or any(x in data["mythics"] for x in ids)) and e.get("min_difficulty"):
                bad.append(f"loot.{tid}: 신화 줄에 min_difficulty (모든 난이도여야 함)")
    for wid in data["mythics"]:
        if not any(wid in (e.get("blueprint_of") or []) for t in tables.values() for e in (t.get("entries") or [])):
            bad.append(f"{wid}: 신화 도안 출처(blueprint_of) 없음")
        if not any(wid in (e.get("blueprint_of") or []) for tid, t in tables.items() if tid != "floor10_boss"
                   for e in (t.get("entries") or [])):
            bad.append(f"{wid}: 넬카르 밖 신화 도안 출처 없음 (넬카르를 못 잡아도 도안이 나와야 함)")
    return bad


if __name__ == "__main__":
    sys.exit("이 단계는 따로 돌리지 않는다 — python3 tools/gen_035_content.py [--check]")
