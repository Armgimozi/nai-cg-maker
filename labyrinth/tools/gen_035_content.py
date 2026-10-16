#!/usr/bin/env python3
"""
0.3.5 P3 — 장비 데이터 한 번에: 요구 능력치(AND·나눔) · 층 이름표 없는 단계 풀 루팅 · 새 장비 (무기 245 · 방어구 6세트).

  python3 tools/gen_035_content.py            # items.yml · loot.yml · recipes.yml · npcs.yml 을 고쳐 쓴다 (다시 돌려도 같은 결과)
  python3 tools/gen_035_content.py --check    # 쓰지 않고 검사만 — 파일이 생성 결과와 같으면 종료 코드 0
  python3 tools/gen_035_content.py --dry-run  # 무엇이 바뀌는지만 출력

입력 (모두 tools/data/035/ — 설계 폴더 사본, 손으로 고치지 않는다):
  gear_spec.json     새 무기 106 · 기존 무기 131 요구(existing_changes) · 새 방어구 6세트 · 루팅 표 206 · 레시피 · 상점
  unique_assign.json 무기 237 고유 효과 (unique_spec §9 + review2 A12 + 주인 결정 B3)
  armor_looks.json   방어구 요구 짝 · 스탯 줄 이름 바꿈 (P2 — 새 6세트도 이 표로)
  content_p3.json    review2 §1.B B1 고침 23개 · 31–35 새 희귀 8개 영웅 승격 · 주인 결정 B2 새 무기 8개 (설계: scratchpad p3_design.py)
이 파일이 정하는 것 (생성 규칙):
  · items.yml 장비: floor → tier (값 같음, 재료는 floor 그대로), classes 삭제, 무기 requires = 명세, attack = 명세 (A8 지능 활·근접 magic),
    무기마다 unique, sources = 실제 획득처 (루팅·레시피·상점·칭호·시작 지급에서 계산 — trial · special · hoard 추가)
  · loot.yml: gear_spec loot_changes (단계 풀 band_tNN_* · 층 섞음 mix_fNN_drop(PICK 2:7:1) · hoard_fNN · special_trial_fNN ·
    몹·상자·시련방·정예 표 다시 씀 · gear_fNN_common 삭제) + B1 활 이름 바꿈 + B2 풀 넣기, settings.own_class_bias → own_build_bias
  · recipes.yml: 새 방어구 12개 · 무기 레시피 54개 골드 ×1.5 · npcs.yml: 상인 핀 3줄
줄 단위로 고쳐 쓰므로 손대지 않는 줄의 주석·순서·흐름 표기는 그대로 남는다. 다 쓰고 나서 YAML 을 다시 읽어 뜻이 기대와 같은지 확인한다.
강화 재료(enhance.yml)는 이 다음에 tools/gen_enhance.py 로 다시 만든다.
"""
import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "plugin/src/main/resources/content"
CONFIG = ROOT / "plugin/src/main/resources/config.yml"
DATA = ROOT / "tools/data/035"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_035_looks as LOOKS_GEN  # noqa: E402
import gen_035_unique as UNIQUE_GEN  # noqa: E402
import gen_036_blueprints as BP036  # noqa: E402  (0.3.6 Q6 도안 — generate() 마지막 단계)

ITEM_RE = re.compile(r"^  ([a-z0-9_]+):\s*(#.*)?$")
GEAR_TYPES = ("weapon", "armor", "accessory")
SPEC_ONLY = ("_spec", "direction", "source")
MODEL_SPEC_ONLY = ("palette", "notes", "hold", "new_silhouette", "style")
SOURCE_ORDER = ["drop", "chest", "elite", "boss", "trial", "special", "hoard", "craft", "shop", "reward", "starter"]
WEAPON_KEYS = ["name", "type", "attack", "rarity", "level_req", "requires", "tier", "stats", "pool", "sources", "unique",
               "weapon_skills", "model", "texture", "lore"]
ARMOR_KEYS = ["name", "type", "armor_slot", "armor_set", "rarity", "level_req", "requires", "tier", "stats", "set_bonus", "pool",
              "sources", "model", "texture", "lore"]
SKILL_KEYS = ["id", "name", "input", "cooldown", "mana", "description", "pvp_mult", "params"]
BAND_KO = {1: "1–5", 2: "6–10", 3: "11–15", 4: "16–20", 5: "21–25", 6: "26–30", 7: "31–35", 8: "36–40", 9: "41–45", 10: "46–50"}
LOOK_KO = {"heavy": "판금", "light": "가죽", "cloth": "천"}
STAT_KO = LOOKS_GEN.STAT_NAMES


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ───────────────────────── 흐름 표기 (items.yml · loot.yml 꼴) ─────────────────────────
PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(round(v, 6))
    if v is None:
        return "null"
    s = str(v)
    if PLAIN.match(s) and s not in ("true", "false", "null", "yes", "no", "on", "off"):
        return s
    return json.dumps(s, ensure_ascii=False)


def flow(v):
    if isinstance(v, dict):
        return "{" + ", ".join(f"{scalar(k)}: {flow(x)}" for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(flow(x) for x in v) + "]"
    return scalar(v)


def jflow(v):
    """mechanics 줄 — 기존 items.yml 과 같은 JSON 흐름 (YAML 로도 읽힌다)."""
    return json.dumps(v, ensure_ascii=False)


def emit_skill(s, ind="      "):
    out = [f"{ind}- id: {s['id']}"]
    for k in SKILL_KEYS[1:]:
        if k not in s:
            continue
        v = s[k]
        if k in ("name", "description"):
            out.append(f"{ind}  {k}: {json.dumps(v, ensure_ascii=False)}")
        elif k == "params":
            out.append(f"{ind}  params: {jflow(v)}")
        else:
            out.append(f"{ind}  {k}: {scalar(v)}")
    if "mechanics" in s:
        out.append(f"{ind}  mechanics:")
        for m in s["mechanics"]:
            out.append(f"{ind}    - {jflow(m)}")
    return out


def emit_item(iid, it, keys):
    out = [f"  {iid}:"]
    for k in keys:
        if k not in it or it[k] is None:
            continue
        v = it[k]
        if k in ("requires",) and not v:
            continue
        if k in ("name", "lore"):
            out.append(f"    {k}: {json.dumps(v, ensure_ascii=False)}")
        elif k == "weapon_skills":
            if v:
                out.append("    weapon_skills:")
                for s in v:
                    out.extend(emit_skill(s))
        elif isinstance(v, (dict, list)):
            out.append(f"    {k}: {flow(v)}")
        else:
            out.append(f"    {k}: {scalar(v)}")
    return out


def entry_flow(e):
    order = ["item", "one_of", "table", "pick", "rarity_pool", "floor", "chance", "amount", "min_difficulty"]
    d = {k: e[k] for k in order if k in e}
    for k, v in e.items():
        d.setdefault(k, v)
    return flow(d)


def emit_table_body(t, guaranteed_comment=None):
    out = []
    out.append(f"    rolls: {t.get('rolls', 1)}")
    if t.get("gold"):
        out.append(f"    gold: {flow(t['gold'])}")
    if t.get("guaranteed"):
        out.append("    guaranteed:" + (f"   {guaranteed_comment}" if guaranteed_comment else ""))
        for e in t["guaranteed"]:
            out.append(f"      - {entry_flow(e)}")
    out.append("    entries:" + ("" if t.get("entries") else " []"))
    for e in t.get("entries") or []:
        out.append(f"      - {entry_flow(e)}")
    return out


def blocks(lines, start, end, indent=2):
    """lines[start:end] 안의 들여쓴 항목 → {id: (첫 줄, 끝 줄 다음)} (끝 = 다음 항목·주석 머리 전, 빈 줄 포함하지 않음)."""
    out = {}
    pat = re.compile(r"^" + " " * indent + r"([a-z0-9_]+):\s*(#.*)?$")
    i = start
    while i < end:
        m = pat.match(lines[i])
        if m:
            j = i + 1
            while j < end:
                l = lines[j]
                if l.strip() and (len(l) - len(l.lstrip())) <= indent:
                    break
                j += 1
            while j > i + 1 and not lines[j - 1].strip():
                j -= 1
            out[m.group(1)] = (i, j)
            i = j
        else:
            i += 1
    return out


def field(lines, a, b, key, ind="    "):
    want = ind + key + ":"
    for k in range(a + 1, b):
        if lines[k].startswith(want):
            return k
    return None


# ───────────────────────── 최종 데이터 ─────────────────────────
# gear_spec 새 무기 스킬 '연쇄 섬광 + MP 조금 되찾기' 의 {mana: 8} 은 MP 8 로 적혀 있지만 MechanicsEngine 의 mana 효과는
# 최대 MP 비율(0~2, 기본 0.05)이다 → 0.05 (MP 를 조금 되찾는다 — 설명 그대로)
SELF_MANA_RATIO = 0.05


def fix_self_mana(mechs):
    for m in mechs:
        if not isinstance(m, dict):
            continue
        for e in m.get("effects") or []:
            if isinstance(e, dict) and isinstance(e.get("mana"), (int, float)) and e["mana"] > 2:
                e["mana"] = SELF_MANA_RATIO
        fix_self_mana(m.get("mechanics") or [])


class Spec:
    def __init__(self):
        self.gs = load_json("gear_spec.json")
        self.ua = {k: v for k, v in load_json("unique_assign.json").items() if not k.startswith("_")}
        self.looks = load_json("armor_looks.json")
        self.p3 = load_json("content_p3.json")
        self.removed = dict(self.p3["remove_weapons"])          # 근접 → 활 (옛 id → 새 id)
        self.replaced_by = {v: k for k, v in self.removed.items()}

    @staticmethod
    def clean(it):
        out = {k: copy.deepcopy(v) for k, v in it.items() if k not in SPEC_ONLY and not k.startswith("_")}
        if isinstance(out.get("model"), dict):
            out["model"] = {k: v for k, v in out["model"].items() if k not in MODEL_SPEC_ONLY}
        return out

    def unique_of(self, wid):
        return UNIQUE_GEN.unique_block(self.ua[wid])

    def new_weapons(self):
        """새 무기 (gear_spec 순서, 바뀐 자리는 그 자리에, B2 는 띠 끝에) → {id: items.yml 꼴}."""
        out = {}
        for wid, it in self.gs["weapons"].items():
            if wid in self.removed:
                nid = self.removed[wid]
                out[nid] = self.clean(self.p3["weapons"][nid])
            elif wid in self.p3["weapons"]:
                out[wid] = self.clean(self.p3["weapons"][wid])
            else:
                w = self.clean(it)
                w["unique"] = self.unique_of(wid)
                patch = self.p3.get("new_weapon_patch", {}).get(wid, {})
                for sk in w.get("weapon_skills") or []:
                    sk["name"] = patch.get("skill_names", {}).get(sk.get("input"), sk["name"])
                out[wid] = w
        for nid in self.p3["b2_new"]:
            out[nid] = self.clean(self.p3["weapons"][nid])
        for w in out.values():
            w["tier"] = int(w["tier"])
            for sk in w.get("weapon_skills") or []:
                fix_self_mana(sk.get("mechanics") or [])
        return out

    def existing_weapon(self, wid):
        """기존 무기 131개: (requires, attack, unique, 더할 무기 스킬)."""
        ch = self.gs["existing_changes"][wid]
        p = self.p3["existing_patch"].get(wid, {})
        req = p.get("requires", ch["requires"])
        uniq = p.get("unique", self.unique_of(wid))
        return req, dict(ch["attack"]), uniq, p.get("add_weapon_skills", [])

    def new_armor(self):
        """새 방어구 6세트 24부위 → ({id: 꼴}, {set: 꼴}). 요구 = armor_looks 짝(P2 규칙), 줄 이름 바꿈도 그 표."""
        items, sets = {}, {}
        for sid, s in self.gs["armor_sets"].items():
            pair = self.looks["set_pairs"][sid]["pair"]
            ren = self.looks["stats_rename"].get(sid, {})
            for pid in s["pieces"]:
                p = self.clean(s["pieces_items"][pid])
                p["requires"] = LOOKS_GEN.split(LOOKS_GEN.budget(int(p["level_req"])), pair)
                p["stats"] = {ren.get(k, k): v for k, v in p["stats"].items()}
                p["tier"] = int(p["tier"])
                items[pid] = p
            sets[sid] = {"name": s["name"], "look": s["look"], "pieces": list(s["pieces"]), "bonuses": s["bonuses"]}
        return items, sets

    def loot(self, tables):
        """지금 loot.yml 표 → 0.3.5 표 (op: replace_entries · new · delete) + B1 활 이름 · B2 풀."""
        T = copy.deepcopy(tables)
        order = list(T)
        for tid, ch in self.gs["loot_changes"].items():
            if ch["op"] == "delete":
                T.pop(tid, None)
                continue
            t = {k: copy.deepcopy(ch[k]) for k in ("rolls", "gold", "guaranteed", "entries") if ch.get(k) is not None}
            if tid not in T:
                order.append(tid)
            T[tid] = t
        for t in T.values():
            for key in ("entries", "guaranteed"):
                for e in t.get(key) or []:
                    if "one_of" in e:
                        e["one_of"] = [self.removed.get(x, x) for x in e["one_of"]]
                    if "item" in e:
                        e["item"] = self.removed.get(e["item"], e["item"])
        weapons = self.new_weapons()
        for nid in self.p3["b2_new"]:
            w = weapons[nid]
            src = w["sources"][0]
            pid = f"band_t{w['tier']:02d}_{src}"
            t = T[pid]
            placed = False
            for key in ("guaranteed", "entries"):
                for e in t.get(key) or []:
                    ids = e.get("one_of") or []
                    if ids and all(x in weapons or x in self.gs["existing_changes"] for x in ids):
                        if nid not in ids:
                            ids.append(nid)
                        placed = True
            if not placed:
                raise SystemExit(f"B2 {nid}: {pid} 에 무기 묶음이 없음")
        for tid, i, ch, _ in self.loot_tweaks():
            T[tid]["entries"][i]["chance"] = ch
        return {k: T[k] for k in order if k in T}

    def loot_tweaks(self):
        """content_p3 loot_tweaks → [(표, entries 번호, chance, 주석)] (보스 고유 무기 묶음 확률 — 빌드 편향 몫)."""
        out = []
        for tid, tw in (self.p3.get("loot_tweaks") or {}).items():
            if tid.startswith("_"):
                continue
            for i, v in tw.items():
                v = v if isinstance(v, dict) else {"chance": v}
                out.append((tid, int(i), v["chance"], v.get("note")))
        return out


# ───────────────────────── 획득처 (sources) ─────────────────────────
def expand(tables, tid, seen=frozenset()):
    if tid in seen or tid not in tables:
        return set()
    t = tables[tid]
    s = set()
    for e in (t.get("entries") or []) + (t.get("guaranteed") or []):
        if "item" in e:
            s.add(e["item"])
        elif "one_of" in e:
            s |= set(e["one_of"])
        elif "table" in e:
            s |= expand(tables, e["table"], seen | {tid})
        elif "pick" in e:
            for p in e["pick"]:
                s |= expand(tables, p["table"], seen | {tid})
    return s


def compute_sources(items, tables, recipes, mobs, bosses, floors, npcs, titles, config):
    """장비 id → 획득처 꼬리표 목록. 몹 = drop · 정예 = elite · 보스 = boss · 보물방·미로 상자 = chest · 시련방 = trial ·
    특별 시련 = special · 금고·미믹 = hoard · 대장간 = craft · 상인 = shop · 칭호 = reward · 시작 지급 = starter."""
    roots = []
    for m in mobs.values():
        if m.get("drops"):
            roots.append((m["drops"], "elite" if m.get("rank") == "elite" else "drop"))
    for b in bosses.values():
        if b.get("drops"):
            roots.append((b["drops"], "boss"))
    for n in floors:
        roots.append((f"treasure_floor_{n}", "chest"))
        roots.append((f"gimmick_floor_{n}", "trial"))
        roots.append((f"special_trial_f{n:02d}", "special"))
        roots.append((f"hoard_f{n:02d}", "hoard"))
        for tier in ("wood", "iron", "gold"):
            roots.append((f"maze_chest_{tier}_f{n}", "chest"))
    tags = {}
    for tid, tag in roots:
        for iid in expand(tables, tid):
            tags.setdefault(iid, set()).add(tag)
    for r in recipes.values():
        tags.setdefault(r["result"], set()).add("craft")
    for n in npcs.values():
        for s in n.get("shop") or []:
            tags.setdefault(s["item"], set()).add("shop")
    for a in titles.values():
        for iid in ((a.get("reward") or {}).get("items") or {}):
            tags.setdefault(iid, set()).add("reward")
    for e in ((config.get("starter_kit") or {}).get("items") or []):
        tags.setdefault(e["item"], set()).add("starter")
    out = {}
    for iid, it in items.items():
        if it.get("type") not in GEAR_TYPES:
            continue
        out[iid] = [s for s in SOURCE_ORDER if s in tags.get(iid, set())]
    return out


# ───────────────────────── items.yml ─────────────────────────
HEADER_SUBS = [
    ("#  floor       : 이 장비가 속한 층(1~10) — 장비는 그 층의 루팅 테이블·레시피에서만 나온다",
     "#  tier        : 장비 단계(1~10, 숨김) = 그 장비를 만든 레벨 구간 Lv 5N−5 ~ 5N (0.3.5 — 화면에 층이 나오지 않는다).\n"
     "#                보스가 아닌 장비는 레벨 창(단계 ±1)이 겹치는 이웃 층 셋이 나눠 준다 (loot.yml 단계 풀 band_tNN_*, 층 몫 2 : 7 : 1).\n"
     "#                보스 고유 장비는 그 단계 층 보스만. 재료는 floor(그 층 재료) 그대로"),
    ("#                무기: 값 = ceil(2.5 × (level_req − 1)), 2 이하면 요구 없음, 무기마다 능력치를 정함 (물리 무기 STR·DEX, 마법 무기 INT·WIS 가 주)",
     "#                무기 (0.3.5, tools/gen_035_content.py): 합 = ceil(2.75 × (level_req − 1)), 2 이하면 없음, 능력치 2~3개 '그리고' —\n"
     "#                        60 : 40 또는 50 : 30 : 20 (세 개는 Lv12 부터). 물리 무기는 STR·DEX, 마법 무기는 INT·WIS 가 하나 이상"),
    ("#  classes     : 어울리는 직업 (비우면 모두) — 착용 제한이 아니다. 드롭 직업 편향(loot.yml own_class_bias)에만 쓴다 (툴팁·대장간에 표시 안 함)",
     "#  classes     : 직업 문장(key)만 — 장비에는 없다 (0.3.5). 드롭 편향은 요구 능력치로 (loot.yml own_build_bias)"),
    ("#  sources     : 획득처 (툴팁·도감 표시용, loot/recipes/titles/npcs 에서 계산해 적음). 장비 하나 = 한 층, 집은 최대 2곳",
     "#  sources     : 획득처 (툴팁·도감 표시용, tools/gen_035_content.py 가 loot/recipes/titles/npcs/시작 지급에서 계산해 적음)"),
    ("#                영웅·전설·신화 무기는 집 1곳 — 보스 고유 = 그 보스만 (제작법 없음) · 대장간 = 대장간만 (드롭 없음) · 5층 공용 = 몬스터·상자만",
     "#                영웅·전설·신화 무기는 획득처 종류 1개 — 보스 고유 = 그 보스만 (제작법 없음) · 대장간 = 대장간만 (드롭 없음) ·\n"
     "#                몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예 중 하나 (몬스터·상자 = drop+chest 한 종류)"),
    ("#                drop·chest 그 층 몬스터·상자(gear_fNN_common 한 집 — 일반 몹·보물방·기믹방·미로 상자, 6·8·9·10층은 없음) · elite 그 층 정예 · boss 그 층 보스 고유",
     "#                drop·chest 몬스터·상자(mix_fNN_drop → 단계 풀 band_tNN_drop — 일반 몹·보물방·미로 상자) · elite 정예(band_tNN_elite) ·\n"
     "#                boss 보스 고유 · trial 시련방(band_tNN_trial) · special 특별 시련(band_tNN_special) · hoard 금고·미믹(band_tNN_hoard)"),
]
NEW_WEAPON_HEADER = "  # ═════════ 무기 · 0.3.5 새 무기 · 띠 {band} (단계 풀 — 시련방·특별 시련·금고·미믹·정예·몬스터·상자·상인) ═════════"
NEW_SET_HEADER = "  # ═════════ 방어구 세트 · {name} ({sid}) — {look}, 0.3.5 새 세트, Lv{L} · 요구 {req} ═════════"


def apply_items(text, spec, sources, new_w, new_a, new_sets, changes):
    lines = text.split("\n")
    for old, new in HEADER_SUBS:
        if old in lines:
            i = lines.index(old)
            lines[i:i + 1] = new.split("\n")
            changes.append("머리 주석: " + old.split(":")[0].strip("# "))
    data = yaml.safe_load("\n".join(lines))
    items = data["items"]
    items_at = next(i for i, l in enumerate(lines) if l.startswith("items:"))
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    ib = blocks(lines, items_at + 1, sets_at)
    gs_new = set(spec.gs["weapons"]) | set(spec.removed.values()) | set(spec.p3["b2_new"])
    armor_new = set(new_a)
    # 이미 들어간 새 장비 블록은 지우고 다시 쓴다 (다시 돌려도 같은 결과)
    for iid in reversed(list(ib)):
        if iid in gs_new or iid in armor_new or iid in spec.removed:
            a, b = ib[iid]
            del lines[a:b]
    for i in range(len(lines) - 1, -1, -1):   # 새 장비 머리 주석 (빈 줄 포함)
        if lines[i].startswith("  # ═════════ 무기 · 0.3.5 새 무기") or (
                lines[i].startswith("  # ═════════ 방어구 세트 ·") and "0.3.5 새 세트" in lines[i]):
            j = i
            while j + 1 < len(lines) and not lines[j + 1].strip():
                j += 1
            del lines[i:j + 1]
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    ib = blocks(lines, items_at + 1, sets_at)
    # 기존 장비 고치기 (아래에서 위로 — 줄 번호가 밀리지 않게)
    for iid in reversed(list(ib)):
        it = items.get(iid) or {}
        if it.get("type") not in GEAR_TYPES:
            continue
        a, b = ib[iid]

        def setline(key, text, after=None):
            nonlocal b
            k = field(lines, a, b, key)
            if text is None:
                if k is not None:
                    del lines[k]
                    b -= 1
                    changes.append(f"{iid}: - {key}")
                return
            if k is None:
                at = field(lines, a, b, after) if after else None
                at = (at if at is not None else a)
                lines.insert(at + 1, text)
                b += 1
                changes.append(f"{iid}: + {key}")
            elif lines[k] != text:
                lines[k] = text
                changes.append(f"{iid}: {key}")

        k = field(lines, a, b, "floor")
        if k is not None:
            lines[k] = lines[k].replace("    floor:", "    tier:", 1)
            changes.append(f"{iid}: floor → tier")
        setline("classes", None)
        if it.get("type") == "weapon" and iid in spec.gs["existing_changes"]:
            req, attack, uniq, add_skills = spec.existing_weapon(iid)
            setline("attack", f"    attack: {flow(attack)}", "type")
            setline("requires", f"    requires: {flow(req)}" if req else None, "level_req")
            setline("sources", f"    sources: {flow(sources[iid])}", "pool")
            setline("unique", f"    unique: {flow(uniq)}", "sources")
            if add_skills:
                have = {s["name"] for s in it.get("weapon_skills") or []}
                todo = [s for s in add_skills if s["name"] not in have]
                if todo:
                    m = field(lines, a, b, "model")
                    if field(lines, a, b, "weapon_skills") is None:
                        lines.insert(m, "    weapon_skills:")
                        m += 1
                        b += 1
                    for s in todo:
                        new = emit_skill(s)
                        lines[m:m] = new
                        m += len(new)
                        b += len(new)
                    changes.append(f"{iid}: + 무기 스킬 {[s['name'] for s in todo]}")
        else:
            setline("sources", f"    sources: {flow(sources.get(iid, []))}", "pool")
    # 새 무기 — 방패 머리 주석 앞, 띠마다 머리 주석
    at = next(i for i, l in enumerate(lines) if l.startswith("  # ═════════ 방패"))
    add = []
    by_band = {}
    for wid, w in new_w.items():
        by_band.setdefault((int(w["level_req"]) - 1) // 5 + 1, []).append(wid)
    for band in sorted(by_band):
        add.append(NEW_WEAPON_HEADER.format(band=BAND_KO[band]))
        for wid in by_band[band]:
            w = dict(new_w[wid], sources=sources[wid])
            add.extend(emit_item(wid, w, WEAPON_KEYS))
        add.append("")
    lines[at:at] = add
    changes.append(f"새 무기 {len(new_w)}개")
    # 새 방어구 — 장신구 머리 주석 앞
    at = next(i for i, l in enumerate(lines) if l.startswith("  # ═════════ 장신구"))
    add = []
    for sid, s in new_sets.items():
        p0 = new_a[s["pieces"][0]]
        req = " · ".join(f"{STAT_KO[k]} {v}" for k, v in p0["requires"].items()) or "없음"
        add.append(NEW_SET_HEADER.format(name=s["name"], sid=sid, look=LOOK_KO[s["look"]], L=p0["level_req"], req=req))
        for pid in s["pieces"]:
            add.extend(emit_item(pid, dict(new_a[pid], sources=sources[pid]), ARMOR_KEYS))
        add.append("")
    lines[at:at] = add
    changes.append(f"새 방어구 {len(new_a)}부위")
    # sets: 끝에 새 세트 (이미 있으면 바꿈)
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    sb = blocks(lines, sets_at + 1, len(lines))
    for sid in reversed(list(sb)):
        if sid in new_sets:
            a, b = sb[sid]
            del lines[a:b]
    while lines and not lines[-1].strip():
        lines.pop()
    for sid, s in new_sets.items():
        lines.append(f"  {sid}:")
        lines.append(f"    name: {json.dumps(s['name'], ensure_ascii=False)}")
        lines.append(f"    look: {s['look']}")
        lines.append(f"    pieces: {flow(s['pieces'])}")
        lines.append(f"    bonuses: {flow({int(k): v for k, v in s['bonuses'].items()})}")
    lines.append("")
    return "\n".join(lines)


# ───────────────────────── loot.yml ─────────────────────────
LOOT_HEADER_OLD_START = "# 장비 획득 규칙: 장비 하나는 자기 층(items.yml floor)에만 속하고 집은 최대 2곳이다."
LOOT_HEADER_NEW = """# 장비 획득 규칙 (0.3.5 — 장비에 층 이름표가 없다, gear_spec §4):
#  장비 단계(items.yml tier) N 은 레벨 구간 Lv 5N−5 ~ 5N. 보스가 아닌 장비는 단계 풀 band_tNN_<종류> 에 들어가고,
#  층 f 는 이웃 단계 f−1 : f : f+1 = 2 : 7 : 1 로 섞어 준다 (특별 시련 1 : 8 : 1) — {pick: [{table, weight}, …], chance} 항목.
#  몬스터·상자 = mix_fNN_drop (일반 몹·보물방·미로 상자가 {table:} 로 굴림) → band_tNN_drop
#  시련방 = gimmick_floor_N 의 PICK → band_tNN_trial · 정예 = 정예 표의 PICK → band_tNN_elite (방어구 세트·방패·장신구·정예 무기)
#  금고·미믹 = hoard_fNN (금고 안 상자·길들인 미믹을 열 때 한 번 더) · 특별 시련 = special_trial_fNN (조건까지 지킨 시련방 성공 상자)
#  보스 고유 장비는 그 보스 표에만 (이웃 층 없음). 두 번째 집은 대장간(recipes.yml)
#  영웅·전설·신화 무기는 획득처 종류 1개 (보스 · 대장간 · 몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 정예)
#  드롭 편향 own_build_bias: one_of 로 장비를 고를 때 이 확률로 '요구치가 가장 큰 능력치가 줍는 사람 능력치 상위 2개 안'인 후보만 (없으면 전체)"""
LOOT_ENTRY_DOC_OLD = "#      {table: 하위테이블, chance}                    다른 테이블을 통째로 굴림 (순환 금지)"
LOOT_ENTRY_DOC_NEW = (LOOT_ENTRY_DOC_OLD + "\n"
                      "#      {pick: [{table: 하위테이블, weight: n}, …], chance}   chance 를 넘으면 무게대로 하위 테이블 하나를 골라 굴림 (0.3.5, 순환 금지)")
BIAS_OLD = "  own_class_bias: 0.65        # 장비 1개를 고를 때(one_of) 이 확률로 루팅한 사람 직업에 어울리는 장비(items.yml classes)만 후보 (없으면 전체, 착용 제한은 없음)"
BIAS_NEW = "  own_build_bias: 0.65        # 장비 1개를 고를 때(one_of) 이 확률로 요구치 1위 능력치가 줍는 사람 능력치(기본+분배+칭호) 상위 2개 안인 후보만 (없으면 전체)"
NEW_SECTIONS = [
    ("band_", "  # ═════════ 단계 풀 (0.3.5 — band_tNN_<종류>, 이웃 층 셋이 PICK 으로 나눠 굴린다. 표시에 층 없음) ═════════"),
    ("mix_", "  # ═════════ 층 섞음 — 몬스터·상자 (mix_fNN_drop = 단계 f−1 : f : f+1 = 2 : 7 : 1) ═════════"),
    ("hoard_", "  # ═════════ 금고·미믹 (hoard_fNN — 금고 안 금 상자·길들인 미믹 상자를 열 때 층 표에 더해 한 번 더) ═════════"),
    ("special_trial_", "  # ═════════ 특별 시련 상자 (special_trial_fNN — 특별 시련 성공 + 조건 지킴 때 시련방 상자에 더해 하나 더, 개인 루팅) ═════════"),
]
OLD_GEAR_COMMON_PAT = re.compile(r"^  gear_f\d\d_common:")
LOOT_TEXT_SUBS = [
    ("rarity_weight 는 장비 항목에만 — gear_fNN_common 안의 one_of(chance 1.0)에는 안 붙는다",
     "rarity_weight 는 장비 항목에만 — 단계 풀 band_tNN_* 안의 one_of(chance 1.0)에는 안 붙는다"),
    ("(그 층 재료 · gear_fNN_common(6·8·9·10층은 없음) · 금 상자는 그 층 정예 재료)",
     "(그 층 재료 · 몬스터·상자 단계 풀 mix_fNN_drop · 금 상자는 그 층 정예 재료)"),
]


def apply_loot(text, spec, final, changes):
    lines = text.split("\n")
    if BIAS_OLD in lines:
        lines[lines.index(BIAS_OLD)] = BIAS_NEW
        changes.append("settings: own_class_bias → own_build_bias")
    if LOOT_ENTRY_DOC_OLD in lines and LOOT_ENTRY_DOC_NEW.split("\n")[1] not in lines:
        i = lines.index(LOOT_ENTRY_DOC_OLD)
        lines[i:i + 1] = LOOT_ENTRY_DOC_NEW.split("\n")
    if LOOT_HEADER_OLD_START in lines:
        i = lines.index(LOOT_HEADER_OLD_START)
        j = i
        while j + 1 < len(lines) and lines[j + 1].startswith("#  "):
            j += 1
        lines[i:j + 1] = LOOT_HEADER_NEW.split("\n")
        changes.append("머리 주석: 단계 풀")
    for i, l in enumerate(lines):
        for old, new in LOOT_TEXT_SUBS:
            if old in l:
                lines[i] = l = l.replace(old, new)
        if "(gear_fNN_common = 그 층 공용 무기, potions_*, enhance_* …)" in l:
            lines[i] = l.replace("(gear_fNN_common = 그 층 공용 무기, potions_*, enhance_* …)",
                                 "(band_tNN_* 단계 풀 · mix_fNN_drop · hoard_fNN · special_trial_fNN · potions_* · enhance_* …)")
    tables_at = next(i for i, l in enumerate(lines) if l.startswith("tables:"))
    # 확률만 바꾸는 표(loot_tweaks)는 그 줄만 고친다 — 표를 다시 쓰지 않아 다른 주석이 남는다
    tb = blocks(lines, tables_at + 1, len(lines))
    for tid, idx, ch, note in spec.loot_tweaks():
        if tid in spec.gs["loot_changes"] or tid.startswith(("band_t", "mix_f", "hoard_f", "special_trial_f")):
            continue  # 통째로 다시 쓰는 표 — final 에 이미 들어 있다
        a, b = tb[tid]
        k = field(lines, a, b, "entries")
        rows = [j for j in range(k + 1, b) if lines[j].startswith("      - ")]
        j = rows[idx]
        new = re.sub(r"chance: [0-9.]+", f"chance: {ch}", lines[j].split("   #")[0].rstrip())
        if note:
            new += "   # " + note
        if lines[j] != new:
            lines[j] = new
            changes.append(f"loot.{tid}: entries[{idx}] chance {ch}")
    current = yaml.safe_load("\n".join(lines))["tables"]
    new_ids = [t for t in final if t not in current]
    # 지울 표 · 새 표 자리 (이미 생성된 새 표는 지우고 다시 쓴다)
    for tid in reversed(list(tb)):
        a, b = tb[tid]
        if tid not in final or tid.startswith(("band_t", "mix_f", "hoard_f", "special_trial_f")):
            # 표 바로 위의 자기 머리 주석(gear_fNN_common · 새 섹션)도 함께
            k = a
            while k - 1 > tables_at and lines[k - 1].startswith("  # ═════════") and (
                    tid.startswith(("band_t", "mix_f", "hoard_f", "special_trial_f"))):
                k -= 1
            del lines[k:b]
            if tid not in final:
                changes.append(f"loot.{tid}: 삭제")
            continue
        if tid in spec.gs["loot_changes"] or tid in final and final[tid] != current.get(tid):
            gc = None
            k = field(lines, a, b, "guaranteed")
            if k is not None and "#" in lines[k]:
                gc = lines[k][lines[k].index("#"):]
            body = emit_table_body(final[tid], gc)
            if lines[a + 1:b] != body:
                lines[a + 1:b] = body
                changes.append(f"loot.{tid}: 다시 씀")
    # 남은 새 섹션 머리 주석 정리
    lines = [l for l in lines if not any(l == h for _, h in NEW_SECTIONS)]
    while lines and not lines[-1].strip():
        lines.pop()
    # 새 표: 섹션마다 끝에 붙인다
    gen = [t for t in final if t.startswith(("band_t", "mix_f", "hoard_f", "special_trial_f"))]
    for prefix, head in NEW_SECTIONS:
        ids = [t for t in gen if t.startswith(prefix)]
        if not ids:
            continue
        lines.append("")
        lines.append(head)
        for tid in sorted(ids):
            lines.append(f"  {tid}:")
            lines.extend(emit_table_body(final[tid]))
    lines.append("")
    changes.append(f"loot: 새 표 {len(new_ids)}개")
    # 빈 줄 겹침 정리
    out = []
    for l in lines:
        if not l.strip() and out and not out[-1].strip():
            continue
        out.append(l)
    return "\n".join(out)


# ───────────────────────── recipes.yml · npcs.yml ─────────────────────────
RECIPE_HEADER = "  # ═════════ 0.3.5 새 방어구 (균사 갑각 · 수로 잠수부 · 색인 방벽 — 대장간 + 정예/시련방) ═════════"


def apply_recipes(text, spec, items, changes):
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if l.startswith("# 재료는 그 장비 층(items.yml floor)"):
            lines[i] = l.replace("그 장비 층(items.yml floor)", "그 장비 단계 층(items.yml tier)")
    rec_at = next(i for i, l in enumerate(lines) if l.startswith("recipes:"))
    rb = blocks(lines, rec_at + 1, len(lines))
    current = yaml.safe_load("\n".join(lines))["recipes"]
    for rid in reversed(list(rb)):
        a, b = rb[rid]
        if rid in spec.gs["recipes_new"]:
            del lines[a:b]
            continue
        ch = spec.gs["recipes_changes"].get(rid)
        if ch:
            k = field(lines, a, b, "gold")
            want = f"    gold: {ch['gold']}"
            if lines[k] != want:
                if current[rid]["gold"] != ch["gold_old"]:
                    raise SystemExit(f"recipes.{rid}: 골드 {current[rid]['gold']} ≠ 명세의 옛 값 {ch['gold_old']} (손으로 고친 값?)")
                lines[k] = want
                changes.append(f"recipes.{rid}: 골드 {ch['gold_old']} → {ch['gold']}")
    lines = [l for l in lines if l != RECIPE_HEADER]
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append("")
    lines.append(RECIPE_HEADER)
    for rid, r in spec.gs["recipes_new"].items():
        lines.append(f"  {rid}:   # {items[rid]['name']}")
        lines.append(f"    result: {r['result']}")
        lines.append(f"    category: {r['category']}")
        lines.append(f"    station: {r['station']}")
        lines.append(f"    materials: {flow(r['materials'])}")
        lines.append(f"    gold: {r['gold']}")
        lines.append(f"    level_req: {r['level_req']}")
    lines.append("")
    out = []
    for l in lines:
        if not l.strip() and out and not out[-1].strip():
            continue
        out.append(l)
    return "\n".join(out)


def apply_npcs(text, spec, changes):
    lines = text.split("\n")
    want = spec.p3["shop"]["merchant"]
    at = next(i for i, l in enumerate(lines) if l.startswith("  merchant:"))
    k = next(i for i in range(at, len(lines)) if lines[i].startswith("    shop:"))
    j = k + 1
    while j < len(lines) and lines[j].startswith("      - "):
        j += 1
    rows = lines[k + 1:j]
    keep = [r for r in rows if not any(f"item: {w['item']}," in r for w in want)
            and not any(f"item: {old}," in r for old in spec.removed)]
    new = keep + [f"      - {flow(w)}" for w in want]
    if new != rows:
        lines[k + 1:j] = new
        changes.append(f"npcs.merchant: 상점 {len(want)}줄")
    return "\n".join(lines)


# ───────────────────────── 검사 ─────────────────────────
def verify(paths, spec):
    items_doc = yaml.safe_load(paths["items"])
    items = items_doc["items"]
    loot = yaml.safe_load(paths["loot"])
    bad = []
    weapons = {k: v for k, v in items.items() if v.get("type") == "weapon"}
    if len(weapons) != 245:
        bad.append(f"무기 {len(weapons)}개 (245 여야 함)")
    for k, v in items.items():
        if v.get("type") in GEAR_TYPES:
            if "floor" in v:
                bad.append(f"{k}: floor 남음")
            if "tier" not in v:
                bad.append(f"{k}: tier 없음")
            if "classes" in v:
                bad.append(f"{k}: classes 남음")
            if v.get("requires_any"):
                bad.append(f"{k}: requires_any 남음")
        if v.get("type") == "weapon" and "unique" not in v:
            bad.append(f"{k}: unique 없음")
    for wid in spec.gs["existing_changes"]:
        req, attack, uniq, _ = spec.existing_weapon(wid)
        if (items[wid].get("requires") or {}) != req:
            bad.append(f"{wid}: requires {items[wid].get('requires')} ≠ {req}")
        if items[wid]["unique"] != uniq:
            bad.append(f"{wid}: unique 다름")
        if items[wid]["attack"] != attack:
            bad.append(f"{wid}: attack {items[wid]['attack']} ≠ {attack}")
    for old in spec.removed:
        if old in items:
            bad.append(f"{old}: 활로 바뀐 무기가 남음")
    t = loot["tables"]
    for tid in ("gear_f01_common", "gear_f07_common"):
        if tid in t:
            bad.append(f"loot.{tid} 남음")
    for n in range(1, 11):
        for tid in (f"special_trial_f{n:02d}", f"hoard_f{n:02d}", f"mix_f{n:02d}_drop"):
            if tid not in t:
                bad.append(f"loot.{tid} 없음")
    if "own_build_bias" not in (loot.get("settings") or {}):
        bad.append("loot.settings.own_build_bias 없음")
    bad += LOOKS_GEN.verify(paths["items"], spec.looks)
    return bad


def generate():
    spec = Spec()
    texts = {n: (CONTENT / f"{n}.yml").read_text(encoding="utf-8") for n in ("items", "loot", "recipes", "npcs")}
    y = {n: yaml.safe_load(texts[n]) for n in texts}
    mobs = yaml.safe_load((CONTENT / "mobs.yml").read_text(encoding="utf-8"))["mobs"]
    bosses = yaml.safe_load((CONTENT / "bosses.yml").read_text(encoding="utf-8"))["bosses"]
    floors = sorted(int(k) for k in yaml.safe_load((CONTENT / "floors.yml").read_text(encoding="utf-8"))["floors"])
    titles = yaml.safe_load((CONTENT / "titles.yml").read_text(encoding="utf-8"))["achievements"]
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    new_w = spec.new_weapons()
    new_a, new_sets = spec.new_armor()
    final_loot = spec.loot(y["loot"]["tables"])
    # 최종 아이템 (획득처 계산용)
    items = {k: v for k, v in y["items"]["items"].items() if k not in spec.removed}
    items.update(new_w)
    items.update(new_a)
    recipes = dict(y["recipes"]["recipes"])
    recipes.update(spec.gs["recipes_new"])
    npcs = copy.deepcopy(y["npcs"]["npcs"])
    npcs["merchant"]["shop"] = [s for s in npcs["merchant"]["shop"] if s["item"] not in spec.removed
                                and s["item"] not in {w["item"] for w in spec.p3["shop"]["merchant"]}] + spec.p3["shop"]["merchant"]
    sources = compute_sources(items, final_loot, recipes, mobs, bosses, floors, npcs, titles, config)
    changes = []
    out = {
        "items": apply_items(texts["items"], spec, sources, new_w, new_a, new_sets, changes),
        "loot": apply_loot(texts["loot"], spec, final_loot, changes),
        "recipes": apply_recipes(texts["recipes"], spec, items, changes),
        "npcs": apply_npcs(texts["npcs"], spec, changes),
    }
    # 방어구 요구·줄 이름은 P2 생성기 규칙 그대로 (새 세트 포함) — 다시 한 번 돌려 고칠 것이 없어야 한다
    lines = out["items"].split("\n")
    look_changes = []
    LOOKS_GEN.apply(lines, spec.looks, look_changes)
    out["items"] = "\n".join(lines)
    changes += [f"(겉모습) {c}" for c in look_changes]
    out = BP036.apply(out, mobs, bosses, floors, changes)   # 0.3.6 Q6 도안: blueprint 아이템 + 루팅 항목 (마지막 단계)
    return spec, texts, out, changes, sources


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec, texts, out, changes, sources = generate()
    if a.check:
        diff = [n for n in out if out[n] != texts[n]]
        bad = verify(texts, spec)
        for b in bad:
            print("✘", b)
        if diff:
            print("생성 결과와 다른 파일:", ", ".join(f"{n}.yml" for n in diff), "(python3 tools/gen_035_content.py)")
        if not bad and not diff:
            print("✔ items · loot · recipes · npcs 가 생성 결과와 같음")
        sys.exit(1 if bad or diff else 0)
    if a.dry_run:
        for c in changes[:200]:
            print(c)
        print(f"(dry-run) 바뀜 {len(changes)}줄")
        return
    for n, t in out.items():
        if t != texts[n]:
            (CONTENT / f"{n}.yml").write_text(t, encoding="utf-8")
    # 다시 돌려도 같은지 (멱등)
    spec2, texts2, out2, changes2, _ = generate()
    if any(out2[n] != texts2[n] for n in out2):
        print("✘ 다시 돌리면 또 바뀜 (멱등 아님):", [n for n in out2 if out2[n] != texts2[n]])
        sys.exit(1)
    bad = verify(texts2, spec2)
    for b in bad:
        print("✘", b)
    if bad:
        sys.exit(1)
    print(f"✔ items · loot · recipes · npcs — 바뀐 것 {len(changes)}개, 무기 {sum(1 for v in yaml.safe_load(texts2['items'])['items'].values() if v.get('type') == 'weapon')}개")


if __name__ == "__main__":
    main()
