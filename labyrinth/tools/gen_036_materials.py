#!/usr/bin/env python3
"""
0.3.6 Q3 — 광석 재료 + 몹 몸에 맞는 드롭. tools/gen_035_content.py 의 generate() 안에서 도는 메모리 단계다 (R §3-18).
따로 돌리지 않는다: `python3 tools/gen_035_content.py [--check]` 가 0.3.5 단계 다음에 apply() 를 부른다.

입력 (모두 tools/data/036/ — 계약, 손으로 고치지 않는다):
  materials.json   새 아이템(광석 6 · 주괴 6 · 보석 6 · 곡괭이 6 · 새 몬스터 재료 3 · 몹 주제 부위 6) · 제련·새기기·곡괭이 레시피 ·
                   옛 8개 바꿈 표 · 생성기 규칙(금속 = 힘 규칙 · ING_SHARE 0.20 · 던전 광석 1회량)
  mine.json        곡괭이 tool 블록 · 광석·보석 등급
  visual.json      광석·주괴·보석 아이콘 · 곡괭이 그림 · 광부·제련공 스킨
  drops_spec.json  몹 주제 드롭 (design036/drops 검토판 사본) — 몹·정예·보스 부위 · 상자 부위 · 고정 레시피 · 강화 표
  base_0351.json   0.3.5.1 장비 레시피 재료 (주괴 개수 = 옛 일반 재료 합 × 0.20 — content 가 바뀐 뒤에도 같은 값)
  drops_036.json   이 단계의 덧규칙 (드롭 명세가 광석을 안 준 층의 광석 몸 몹 · 정예 · 대사)

두 단계:
  ① 재료 (계약 §2.7·2.8·2.10): 옛 광물 8개를 지운다 — 주괴 칸 옛 재료는 루팅에서 빼고 레시피는 주괴로, 몬스터 칸은 새 몬스터 재료로 이름만.
     장비 레시피 184개에 주괴 (금속 = 장비 힘 규칙, 이웃 두 금속 섞기, 개수 = 반올림(옛 일반 재료 × 0.20), 최소 2).
  ② 몹 주제 드롭 (§0 결정 4, drops_spec): 몹은 자기 몸 부위 1~2개만 · 정령은 그 층 정수 · 상자는 그 층 부위를 고루 ·
     레시피 부위를 장비 겉모습·이름으로 고름(고정 표) · 던전 광석은 광석 몸 몹·정예·보스·상자에 (층마다 1회 기대량 = 계약 per_run).
  그 뒤 제련소 레시피 17개 · 광부·제련공 NPC · 획득처(sources)를 최종 루팅으로 다시 셈.

다시 돌려도 같다: 0.3.5 단계가 몹·상자 표를 0.3.5 꼴로 다시 쓰고, 지나가는 표(보스·구간 미로 상자)는 정규화(부위·광석을 지우고 다시 넣음)하며,
레시피는 base_0351.json 에서 다시 계산한다 (지금 레시피가 0.3.5.1 꼴도 0.3.6 꼴도 아니면 멈춘다 — 손으로 고친 레시피).
"""
import collections
import copy
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools/data/036"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_enhance as GE  # noqa: E402

GEAR_TYPES = ("weapon", "armor", "accessory")
STONES = {"lesser_enhance_stone", "greater_enhance_stone", "supreme_enhance_stone", "enhance_protection_scroll"}
MAT_SOURCE_ORDER = ["mine", "smelt", "drop", "elite", "boss", "chest", "craft", "shop", "reward", "starter"]
BRACKET = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10]}
MINE_HEADER = "  # ═════════ 광산 재료 (0.3.6 — 광석 · 주괴 · 보석. 등급 mine_level 1~6 · 종류 mine_kind, 화면에 등급 숫자 없음) ═════════"
TOOL_HEADER = "  # ═════════ 광산 도구 (0.3.6 — 곡괭이 type: tool. 장비 아님: 능력치·강화·판매 없음, 한 칸 1개, 레벨 조건 없음) ═════════"
RECIPE_HEADER = ("  # ═════════ 제련소 (0.3.6 — station: smelter · 제련 광석 ×2 → 주괴 · 새기기 보석 + 정수 → 강화석 2개 · "
                 "곡괭이 벼리기(앞 곡괭이를 재료로) · 레벨 조건 없음) ═════════")
NPC_HEADER = "  # ═══════════════════════════ 광산 마을 NPC (0.3.6 — 광부 브론 → 광산 관리소 메뉴 · 제련공 이그나 → 제련소) ═══════════════════════════"
RECIPE_DOC_SUBS = [
    ("#  category   : weapon | armor | accessory | material  — 대장장이 GUI 탭",
     "#  category   : weapon | armor | accessory | material | tool(0.3.6 곡괭이)  — GUI 탭"),
    ("#  station    : blacksmith",
     "#  station    : blacksmith (대장간) | smelter (0.3.6 제련소·광산 관리소 — 제련·새기기·곡괭이)"),
]
ITEM_DOC_SUBS = [
    ("#  floor       : 이 장비가 속한 층(1~10) — 장비는 그 층의 루팅 테이블·레시피에서만 나온다", None),
]


def jload(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def half_up(x):
    return int(x + 0.5)


# ───────────────────────── 계약 읽기 ─────────────────────────
class Contract:
    def __init__(self):
        self.mat = jload("materials.json")
        self.mine = jload("mine.json")
        self.vis = jload("visual.json")
        self.drops = jload("drops_spec.json")
        self.base = jload("base_0351.json")
        self.extra = jload("drops_036.json")
        g = self.mat["generator_rules"]
        self.metal_order = [k.replace("_ore", "") for k in self.mine["ores"]]           # copper … orichalcum
        self.metal_rank = {m: i + 1 for i, m in enumerate(self.metal_order)}
        mc = g["metal_choice"]
        self.rarity_step, self.boss_step, self.mix_band = mc["rarity_step"], mc["boss_step"], tuple(mc["mix_band"])
        self.ing_share, self.min_ing = g["ing_share"], g["min_ing"]
        dor = g["dungeon_ore"]
        self.ore_per_run = {int(k): v for k, v in dor["per_run"].items()}
        self.ore_metals = {int(k): v for k, v in dor["metals"].items()}
        self.ore_split = dor["split"]
        self.retired = self.mat["retired"]
        self.ingot_slot = {o for o, r in self.retired.items() if r["slot"] == "ingot"}
        self.monster_slot = {o: r["to"] for o, r in self.retired.items() if r["slot"] == "monster"}
        self.pre_release = dict(self.mat["conversion"].get("pre_release") or {})
        self.conversion = dict(self.mat["conversion"]["map"])
        self.all_old = set(self.retired) | set(self.pre_release)
        self.items = self.mat["items"]
        self.new_ids = list(self.mat["new_ids"])
        self.monster_new = [i for i in self.new_ids if self.items[i]["kind"] == "monster" and self.items[i].get("replaces")]
        self.drop_parts = [i for i in self.new_ids if self.items[i]["kind"] == "monster" and not self.items[i].get("replaces")]
        self.mine_ids = [i for i in self.new_ids if self.items[i]["kind"] in ("ore", "ingot", "gem")]
        self.tool_ids = [i for i in self.new_ids if self.items[i]["type"] == "tool"]
        self.ores = {i for i in self.mine_ids if self.items[i]["kind"] == "ore"}
        self.ingots = {i for i in self.mine_ids if self.items[i]["kind"] == "ingot"}
        self.gems = {i for i in self.mine_ids if self.items[i]["kind"] == "gem"}
        d = self.drops
        self.floor_parts = {int(k): list(v) for k, v in d["floor_parts"].items()}
        self.floor_ess = {int(k): v for k, v in d["floor_essence"].items()}
        self.spirit_ess = {int(k): v for k, v in d["rules"]["spirit_essence"].items()}
        # drops_spec 은 materials_spec(T) 위에서 만들어져 5층 재료 칸 이름이 cinder_hide 다 — 이 계약에서는 불씨 혼(ember_soul)
        self.spec_alias = {"cinder_hide": self.monster_slot.get("ember_shard", "ember_soul")}
        self.recipe_split = {int(f): {self.spec_alias.get(k, k): v for k, v in sp.items()} for f, sp in d["recipe_split"].items()}
        self.frozen = d["generator"]["recipes_frozen"]
        self.look_hard = d["rules"]["look_hard"]
        self.name_part = {int(k): v for k, v in d["rules"]["name_part"].items()}
        self.hard_kinds = set(d["hard_kinds"])
        self.renames = d["renames"]
        self.mob_drops, self.elite_drops, self.boss_drops = d["mob_drops"], d["elite_drops"], d["boss_drops"]

    def metals_for(self, tier, rarity, boss, n):
        """장비 하나의 주괴 n 개 → [(금속, 개수)] (계약 §2.7 힘 규칙, 윗 금속이 뒤)."""
        p = tier + self.rarity_step.get(rarity, 0.0) + (self.boss_step if boss else 0.0)
        pos = max(1.0, min(6.0, 1 + (p - 1) / 2))
        lo = int(pos)
        f = pos - lo
        by = self.metal_order
        if lo >= 6:
            return [(by[5], n)]
        if f < self.mix_band[0] - 1e-9:
            return [(by[lo - 1], n)]
        if f > self.mix_band[1] + 1e-9:
            return [(by[lo], n)]
        up = max(1, min(n - 1, half_up(n * f))) if n >= 2 else 0
        out = [(by[lo - 1], n - up)]
        if up:
            out.append((by[lo], up))
        return out


# ───────────────────────── 루팅 공통 ─────────────────────────
def entries_of(t, key):
    return list(t.get(key) or [])


def ids_in(e):
    if "item" in e:
        return [e["item"]]
    return list(e.get("one_of") or [])


def strip_entry(C, e):
    """① 재료 단계: 주괴 칸 옛 재료는 지움 (one_of 에서는 빼서 남은 재료가 몫을 나눔) · 몬스터 칸 옛 재료는 새 몬스터 재료로."""
    e = dict(e)
    ren = dict(C.monster_slot, **C.pre_release)
    if e.get("item") in C.ingot_slot:
        return []
    if e.get("item") in ren:
        e["item"] = ren[e["item"]]
        return [e]
    if e.get("one_of") and set(e["one_of"]) & C.all_old:
        new = []
        for x in e["one_of"]:
            if x in C.ingot_slot:
                continue
            y = ren.get(x, x)
            if y not in new:
                new.append(y)
        if not new:
            return []
        if len(new) == 1:
            e.pop("one_of")
            return [{"item": new[0], **e}]
        e["one_of"] = new
    return [e]


def strip_table(C, t):
    t2 = copy.deepcopy(t)
    for key in ("guaranteed", "entries"):
        if key in t2:
            t2[key] = [y for e in (t2.get(key) or []) for y in strip_entry(C, e)]
    return t2


def part_entry(p, chance, amount):
    e = {"item": p, "chance": chance}
    if amount != 1:
        e["amount"] = amount
    return e


# ───────────────────────── ② 드롭 단계 — 표 다시 짜기 ─────────────────────────
class Drops:
    def __init__(self, C, mobs, bosses, floors):
        self.C = C
        self.mobs, self.bosses, self.floors = mobs, bosses, floors
        self.fl = {int(k): v for k, v in floors.items()}
        self.normals = {f: [m for m in (fd.get("mobs") or []) if m in mobs and mobs[m].get("drops")] for f, fd in self.fl.items()}
        self.elite = {f: fd.get("elite") for f, fd in self.fl.items() if fd.get("elite") in mobs and mobs[fd["elite"]].get("drops")}
        self.boss_t = {f: bosses[fd["boss"]]["drops"] for f, fd in self.fl.items() if fd.get("boss") in bosses and bosses[fd["boss"]].get("drops")}
        # 부위 집합: 재료 단계(옛 이름을 바꾼 뒤)의 층 일반 재료 + 드롭 명세의 층 부위
        self.parts_new = C.floor_parts
        commons = set(C.base["commons"])
        ren = dict(C.monster_slot, **C.pre_release)
        self.parts_mat = {f: [] for f in self.fl}
        for m in C.base["commons_by_floor_order"]:
            f, iid = m
            if iid in C.ingot_slot:
                continue
            iid = ren.get(iid, iid)
            if iid in commons or iid in C.monster_new:
                if iid not in self.parts_mat[f]:
                    self.parts_mat[f].append(iid)
        self.all_parts = {p for ps in self.parts_new.values() for p in ps} | {p for ps in self.parts_mat.values() for p in ps}
        self.extra = C.extra
        missing = [m for f in self.normals for m in self.normals[f] if m not in C.mob_drops]
        missing += [self.elite[f] for f in self.elite if self.elite[f] not in C.elite_drops]
        missing += [self.boss_t[f] for f in self.boss_t if self.boss_t[f] not in C.boss_drops]
        if missing:
            raise SystemExit(f"[036] 드롭 명세에 없는 몹: {missing}")

    # 광석을 지닌 몸 (드롭 명세 ore 무게 + 명세가 광석을 안 준 층의 덧규칙 drops_036.json)
    def mob_ore_weight(self, m):
        w = (self.C.mob_drops.get(m) or {}).get("ore")
        if w:
            return float(w)
        return float((self.extra["mob_ore"].get(m) or {}).get("ore") or 0)

    def elite_ore(self, m):
        return bool((self.C.elite_drops.get(m) or {}).get("ore")) or bool((self.extra["elite_ore"].get(m) or {}).get("ore"))

    def mob_ore_amount(self, m):
        parts = (self.C.mob_drops.get(m) or {}).get("parts") or []
        big = any(isinstance(a, list) and a[-1] >= 3 for _, _, a in parts)
        return list((self.extra["mob_ore"].get(m) or {}).get("amount") or ([1, 3] if big else [1, 2]))

    def is_spec_part(self, iid):
        return iid in self.all_parts

    def rebuild_mob(self, m, t, f, ore_entries):
        spec = self.C.mob_drops[m]
        ess = self.C.floor_ess[f]
        out, placed, ess_done = [], False, False
        newp = [part_entry(p, ch, am) for p, ch, am in spec["parts"]] + ore_entries
        for e in t.get("entries") or []:
            ids = ids_in(e)
            if ids and all(x in self.all_parts or x in self.C.ores for x in ids):
                if not placed:
                    out.extend(newp)
                    placed = True
                continue
            if spec.get("spirit") and e.get("item") == ess:
                if not placed:
                    out.extend(newp)
                    placed = True
                if not ess_done:
                    out.append({"item": ess, "chance": self.C.spirit_ess[f]})
                    ess_done = True
                continue
            out.append(e)
        if not placed:
            out = newp + out
        t2 = dict(t)
        t2["entries"] = out
        return t2

    def rebuild_elite(self, m, t, f, ore_entries):
        spec = self.C.elite_drops[m]
        ess = self.C.floor_ess[f]
        out, placed = [], False
        newp = [part_entry(p, ch, am) for p, ch, am in spec["parts"]] + ore_entries
        for e in t.get("entries") or []:
            ids = ids_in(e)
            if ids and all(x in self.all_parts or x in self.C.ores for x in ids):
                if not placed:
                    out.extend(newp)
                    placed = True
                continue
            if spec.get("spirit_elite") and e.get("item") == ess:
                e = dict(e, chance=spec["spirit_elite"])
            out.append(e)
        if not placed:
            out = out[:1] + newp + out[1:]       # 정예 전리품(첫 항목) 바로 뒤
        t2 = dict(t)
        t2["entries"] = out
        return t2

    def rebuild_boss(self, tid, t, ore_entries):
        spec = self.C.boss_drops[tid]
        g_out, placed = [], False
        newp = [{"item": p, "amount": am} for p, am in spec["parts"]]
        for e in t.get("guaranteed") or []:
            if e.get("item") in self.all_parts:
                if not placed:
                    g_out.extend(newp)
                    placed = True
                continue
            g_out.append(e)
        if not placed:
            g_out = g_out[:1] + newp + g_out[1:]
        ents = [e for e in t.get("entries") or [] if not (ids_in(e) and all(x in self.C.ores for x in ids_in(e)))]
        t2 = dict(t)
        t2["guaranteed"] = g_out
        t2["entries"] = ents + ore_entries     # 광석은 맨 끝 — content_p3 loot_tweaks 가 entries 번호로 가리킨다
        return t2

    def rebuild_chest(self, t, parts_new, ore_entries=None):
        t2 = copy.deepcopy(t)
        for key in ("guaranteed", "entries"):
            if key not in t2:
                continue
            new = []
            for e in t2.get(key) or []:
                ids = ids_in(e)
                if ids and all(x in self.C.ores for x in ids):
                    continue                    # 광석 칸은 아래에서 다시 붙인다
                if ids and all(x in self.all_parts for x in ids):
                    e2 = {k: v for k, v in e.items() if k not in ("item", "one_of")}
                    new.append({"item": parts_new[0], **e2} if len(parts_new) == 1 else {"one_of": list(parts_new), **e2})
                else:
                    new.append(e)
            t2[key] = new
        if ore_entries is not None:
            t2["entries"] = list(t2.get("entries") or []) + ore_entries
        return t2


# ───────────────────────── 던전 광석 (계약 §2.8 — 모든 층, 1회 기대 = per_run) ─────────────────────────
def ore_plan(C, D, tables):
    """→ {표 id: [광석 항목]} (몹·정예는 부위 칸 자리, 보스·상자는 entries 끝). 집 비율 = 계약 split.
    몹 몫은 광석 몸 몹끼리 무게대로, 광석 몸 몹이 없는 층·광석 몸이 아닌 정예의 몫은 상자로 옮긴다."""
    plan = collections.defaultdict(list)
    report = {}
    for f in sorted(D.fl):
        total = C.ore_per_run[f]
        metals = C.ore_metals[f]
        fd = D.fl[f]
        rooms = fd.get("rooms") or {}
        normals = D.normals[f]
        n_kind = GE.MOBS_RUN.get(f, 40) / max(1, len(normals))
        holders = [(m, D.mob_ore_weight(m)) for m in normals if D.mob_ore_weight(m) > 0]
        elite = D.elite.get(f)
        elite_ok = elite is not None and D.elite_ore(elite)
        share = dict(C.ore_split)
        if not holders:
            share["chest"] += share.pop("mob")
        if not elite_ok:
            share["chest"] += share.pop("elite")
        got = collections.Counter()
        # 몹
        if holders:
            wsum = sum(w for _, w in holders)
            for m, w in holders:
                per_kill = total * share["mob"] * w / wsum / n_kind
                am = D.mob_ore_amount(m)
                for k, frac in metals.items():
                    x = per_kill * frac
                    a = list(am)
                    while x / GE.amount(a) > 0.95:
                        a = [a[0] + 1, a[1] + 1]
                    ch = round(x / GE.amount(a), 4)
                    plan[D.mobs[m]["drops"]].append({"item": f"{k}_ore", "chance": ch, "amount": a})
                    got[k] += ch * GE.amount(a) * n_kind
        # 정예 · 보스 · 상자 (정수 개수 — 계약 시제품과 같은 꼴: 기대 0.6 넘으면 개수를 올림)
        homes = []
        if elite_ok:
            homes.append(("elite", [(D.mobs[elite]["drops"], rooms.get("elite", 1))]))
        if f in D.boss_t:
            homes.append(("boss", [(D.boss_t[f], 1)]))
        homes.append(("chest", [(t, n) for t, n in ((f"treasure_floor_{f}", 3 * rooms.get("treasure", 1)), (f"gimmick_floor_{f}", 1))
                                if t in tables]))
        for h, lst in homes:
            tot_n = sum(n for _, n in lst)
            for tid, n in lst:
                rolls = max(1, tables[tid].get("rolls", 1)) if h == "chest" else 1
                for k, frac in metals.items():
                    exp = total * share[h] * frac / tot_n / rolls        # 한 번 굴림의 기대 개수
                    amt = 1 if exp <= 0.6 else max(1, round(exp / 0.6))
                    ch = round(min(1.0, exp / amt), 4)
                    e = {"item": f"{k}_ore", "chance": ch}
                    if amt > 1:
                        e["amount"] = amt
                    plan[tid].append(e)
                    got[k] += ch * amt * rolls * n
        report[f] = {"target": total, "got": round(sum(got.values()), 2), "metals": dict(got), "holders": [m for m, _ in holders],
                     "elite": elite if elite_ok else None, "share": share}
    return plan, report


# ───────────────────────── 레시피 ─────────────────────────
def gear_kind(v):
    if v.get("type") == "weapon":
        return (v.get("attack") or {}).get("style") or "melee"
    if v.get("type") == "accessory":
        return "accessory"
    return v.get("armor_slot") or "melee"


def is_boss_gear(v):
    return "boss" in (v.get("sources") or [])


class Recipes:
    def __init__(self, C, D, items, sets):
        self.C, self.D, self.items = C, D, items
        self.setlook = {p: s.get("look") for s in (sets or {}).values() for p in (s.get("pieces") or [])}
        self.commons = set(C.base["commons"])

    def look_of(self, i, v):
        if v.get("armor_slot") == "offhand":
            return "heavy"
        return self.setlook.get(i) or v.get("look")

    def is_hard(self, i, v, kind):
        if v.get("type") == "armor":
            lk = self.look_of(i, v)
            if lk in self.C.look_hard:
                return self.C.look_hard[lk]
        return kind in self.C.hard_kinds

    def pick_part(self, i, v, f, kind, m):
        split = self.C.recipe_split.get(f, {})
        if m not in split:
            return m
        hard = self.is_hard(i, v, kind)
        p = next(c for c, ks in split[m].items() if (set(ks) == self.C.hard_kinds) == hard)
        name = v.get("name", "")
        for kw, part in self.C.name_part.get(f, []):
            if kw in name and part in split[m]:
                return part
        return p

    def materials_stage(self, rid, base_mats, res):
        """① 0.3.5.1 재료 → 주괴 (계약 §2.7). 장비가 아니면 None."""
        if res.get("type") not in GEAR_TYPES:
            return None
        t = GE.gear_floor(res)
        mats = list(base_mats.items())
        B = sum(n for m, n in mats if m in self.commons)
        n_ing = max(self.C.min_ing, half_up(self.C.ing_share * B))
        split = self.C.metals_for(t, res.get("rarity", "common"), is_boss_gear(res), n_ing)
        new, last_common = [], -1
        ren = dict(self.C.monster_slot, **self.C.pre_release)
        for m, n in mats:
            if m in self.C.ingot_slot:
                continue
            m2 = ren.get(m, m)
            new.append((m2, n))
            if m in self.commons or m in ren:
                last_common = len(new) - 1
        ins = [(f"{k}_ingot", n) for k, n in split]
        new[last_common + 1:last_common + 1] = ins
        return new, split, n_ing

    def drops_stage(self, rid, mats, res, sup_b, sup_c, log):
        """② 부위 칸 → 몸에 맞는 부위 (drops_spec 고정 표 → 없으면 규칙). mats = [(id, n)]."""
        f = GE.gear_floor(res)
        parts_mat = self.D.parts_mat.get(f, [])
        cur_parts = [(m, n) for m, n in mats if m in parts_mat]
        fr = self.C.frozen.get(rid)
        rule = self.rule_parts(rid, res, f, mats, sup_b, sup_c)
        if fr:
            al = self.C.spec_alias
            from_parts = [(al.get(m, m), n) for m, n in fr["from"].items() if al.get(m, m) in parts_mat]
            to_parts = [(m, n) for m, n in fr["to"].items() if m in self.D.all_parts]
            if from_parts == cur_parts:
                if to_parts != rule:
                    log["frozen_vs_rule"].append((rid, to_parts, rule))
                new_parts, how = to_parts, "frozen"
            else:
                log["frozen_mismatch"].append((rid, from_parts, cur_parts))
                new_parts, how = rule, "rule"
        else:
            new_parts, how = rule, "rule"
            if rule != cur_parts:
                log["rule_changed"].append((rid, cur_parts, rule))
        log[how] += 1
        out, placed = [], False
        for m, n in mats:
            if m in parts_mat:
                if not placed:
                    out.extend(new_parts)
                    placed = True
                continue
            out.append((m, n))
        merged = collections.OrderedDict()
        for m, n in out:
            merged[m] = merged.get(m, 0) + n
        return list(merged.items())

    def rule_parts(self, rid, res, f, mats, sup_b, sup_c):
        kind = gear_kind(res)
        out = []
        lo, hi = self.C.drops["rules"]["count_deadband"]
        for m, n in mats:
            if m not in self.D.parts_mat.get(f, []):
                continue
            p = self.pick_part(res.get("_id", rid), res, f, kind, m)
            sb, sc = sup_b[f].get(m, 0), sup_c[f].get(p, 0)
            ratio = sc / sb if sb else 1.0
            n2 = n if (p == m and lo <= ratio <= hi) else max(1, half_up(n * ratio))
            out.append((p, n2))
        merged = collections.OrderedDict()
        for m, n in out:
            merged[m] = merged.get(m, 0) + n
        return list(merged.items())


# ───────────────────────── 텍스트 쓰기 ─────────────────────────
def qstr(s):
    return json.dumps(s, ensure_ascii=False)


def item_block(G, iid, v, keys):
    out = [f"  {iid}:"]
    for k in keys:
        if k not in v or v[k] is None:
            continue
        x = v[k]
        if k in ("name", "lore"):
            out.append(f"    {k}: {qstr(x)}")
        elif isinstance(x, (dict, list)):
            out.append(f"    {k}: {G.flow(x)}")
        else:
            out.append(f"    {k}: {G.scalar(x)}")
    return out


MAT_KEYS = ["name", "type", "rarity", "floor", "mine_level", "mine_kind", "sources", "model", "texture", "lore"]
TOOL_KEYS = ["name", "type", "rarity", "tool", "sources", "model", "texture", "lore"]


def find_block(lines, iid, a, b):
    pat = f"  {iid}:"
    for k in range(a, b):
        if lines[k] == pat or lines[k].startswith(pat + " "):
            j = k + 1
            while j < b and (lines[j].startswith("    ") or not lines[j].strip()):
                if not lines[j].strip():
                    break
                j += 1
            return k, j
    return None


def set_field(lines, a, b, key, text):
    """블록 [a, b) 안의 key 줄을 바꾼다 (없으면 lore 앞에 넣음). → 새 b."""
    want = "    " + key + ":"
    for k in range(a + 1, b):
        if lines[k].startswith(want):
            if lines[k] != text:
                lines[k] = text
            return b
    at = next((k for k in range(a + 1, b) if lines[k].startswith("    lore:")), b)
    lines.insert(at, text)
    return b + 1


# ───────────────────────── 적용 ─────────────────────────
def apply(G, spec, texts, mobs, bosses, floors, config, changes):
    """0.3.5 단계 결과 texts(items·loot·recipes·npcs) → 0.3.6 texts. G = gen_035_content 모듈."""
    C = Contract()
    if not isinstance(floors, dict):     # gen_035 은 층 번호 목록만 들고 있다
        floors = yaml.safe_load((G.CONTENT / "floors.yml").read_text(encoding="utf-8"))["floors"]
    y = {n: yaml.safe_load(texts[n]) for n in texts}
    items0 = y["items"]["items"]
    sets0 = y["items"].get("sets") or {}
    tables0 = y["loot"]["tables"]
    recipes0 = y["recipes"]["recipes"]
    D = Drops(C, mobs, bosses, floors)
    log = collections.defaultdict(list)
    for k in ("frozen", "rule"):
        log[k] = 0

    # ── ① 루팅: 옛 광물 지우기 · 이름 바꾸기 (모든 표, 다시 돌려도 같음) ──
    tables_b = {tid: strip_table(C, t) for tid, t in tables0.items()}
    # ── ② 드롭: 몹·정예·보스·상자 (광석 없이 먼저 — 공급 계산용) ──
    def drops_tables(base, plan):
        T = copy.deepcopy(base)
        for f, ms in D.normals.items():
            for m in ms:
                tid = mobs[m]["drops"]
                T[tid] = D.rebuild_mob(m, T[tid], f, plan.get(tid, []))
            if D.elite.get(f):
                tid = mobs[D.elite[f]]["drops"]
                T[tid] = D.rebuild_elite(D.elite[f], T[tid], f, plan.get(tid, []))
            if f in D.boss_t:
                T[D.boss_t[f]] = D.rebuild_boss(D.boss_t[f], T[D.boss_t[f]], plan.get(D.boss_t[f], []))
            for tid in [f"treasure_floor_{f}", f"gimmick_floor_{f}"] + [f"maze_chest_{k}_f{f}" for k in ("wood", "iron", "gold")]:
                if tid in T:
                    T[tid] = D.rebuild_chest(T[tid], D.parts_new[f], plan.get(tid, []) if tid in plan else [])
        for br, fs in BRACKET.items():
            parts = [p for f in fs for p in D.parts_new[f]]
            for k in ("wood", "iron", "gold"):
                tid = f"maze_chest_{k}_{br}"
                if tid in T:
                    T[tid] = D.rebuild_chest(T[tid], parts, [])
        return T

    # 재료 단계 공급(광석 없음) — 드롭 단계의 부위 개수 비 · 강화 S 배율의 기준
    # 지나가는 표(보스·구간 미로 상자)에 지난번 광석 칸이 있으면 뺀다 — 아래에서 다시 붙인다
    tables_b_noore = copy.deepcopy(tables_b)
    for tid, t in tables_b_noore.items():
        for key in ("guaranteed", "entries"):
            if key in t:
                t[key] = [e for e in t[key] if not (ids_in(e) and all(x in C.ores for x in ids_in(e)))]
    # 재료 단계 공급은 지나가는 표를 0.3.5.1 꼴(base)로 셈한다 — 이미 바뀐 content 에서도 같은 값 (다시 돌려도 같음)
    tables_b_sup = dict(tables_b_noore)
    for tid, t in C.base["loot_passthrough"].items():
        if tid in tables_b_sup:
            tables_b_sup[tid] = strip_table(C, t)
    tables_c0 = drops_tables(tables_b_noore, {})
    plan, ore_report = ore_plan(C, D, tables_c0)
    tables_c = drops_tables(tables_b_noore, plan)

    def supplies(T):
        out = {}
        for f, fd in D.fl.items():
            roots = GE.floor_roots(f, fd, T, mobs, bosses)
            out[f] = GE.supply_of(T, roots)
        return out
    sup_b, sup_c = supplies(tables_b_sup), supplies(tables_c)

    # ── 레시피 ──
    items_all = dict(items0)
    R = Recipes(C, D, items_all, sets0)
    base_rec = C.base["recipes"]
    rec_out = {}
    rlog = []
    for rid, r in recipes0.items():
        res = items0.get(r["result"]) or {}
        if res.get("type") not in GEAR_TYPES:
            continue
        if rid not in base_rec:
            raise SystemExit(f"[036] recipes.{rid}: base_0351.json 에 없는 장비 레시피 (새 레시피면 base 에 0.3.5.1 꼴로 더할 것)")
        res = dict(res, _id=r["result"])
        mats_b, split, n_ing = R.materials_stage(rid, base_rec[rid], res)
        mats_c = R.drops_stage(rid, mats_b, res, sup_b, sup_c, log)
        now = dict(r.get("materials") or {})
        if now != base_rec[rid] and now != dict(mats_c):
            raise SystemExit(f"[036] recipes.{rid}: 지금 재료 {now} 가 0.3.5.1 꼴({base_rec[rid]})도 0.3.6 꼴({dict(mats_c)})도 아님 — 손으로 고친 레시피")
        rec_out[rid] = dict(mats_c)
        rlog.append({"id": rid, "tier": GE.gear_floor(res), "split": split, "n": n_ing, "old": base_rec[rid], "new": dict(mats_c)})

    # ── 아이템 ──
    final_items = build_items(C, D, items0, tables_c, recipes0, rec_out, config, mobs, bosses)

    # ── 텍스트 ──
    out = dict(texts)
    out["loot"] = write_loot(G, spec, texts["loot"], tables0, tables_c, changes)
    out["recipes"] = write_recipes(G, C, texts["recipes"], rec_out, changes)
    out["items"] = write_items(G, C, D, texts["items"], final_items, items0, changes)
    out["npcs"] = write_npcs(G, C, texts["npcs"], changes)
    info = {"drops": D, "ore": ore_report, "recipes": rlog, "log": {k: (v if isinstance(v, int) else len(v)) for k, v in log.items()},
            "log_detail": dict(log), "tables": tables_c, "sup_b": sup_b, "sup_c": sup_c}
    return out, info


def build_items(C, D, items0, tables, recipes0, rec_out, config, mobs, bosses):
    """최종 새 아이템 정의 · 바뀐 지금 재료(이름·설명·획득처)."""
    kinds = {}
    for m in mobs.values():
        if m.get("drops"):
            kinds[m["drops"]] = "elite" if m.get("rank") == "elite" else "drop"
    for b in bosses.values():
        if b.get("drops"):
            kinds[b["drops"]] = "boss"
    found = collections.defaultdict(set)
    for tid, t in tables.items():
        k = kinds.get(tid, "chest" if tid.startswith(("treasure_", "gimmick_", "maze_chest_")) else None)
        if not k:
            continue
        for e in (t.get("guaranteed") or []) + (t.get("entries") or []):
            for x in ids_in(e):
                found[x].add(k)
    starter = {e["item"] for e in ((config.get("starter_kit") or {}).get("items") or [])}
    out = {}
    icons = C.vis["icons"]
    for i in C.new_ids:
        d = C.items[i]
        if d["type"] == "tool":
            pk = C.vis["pickaxes"][i]
            tex = {"style": pk["style"], "palette": pk["palette"]}
            if pk.get("animated"):
                tex.update({"animated": True, "frames": 8, "frametime": 2, "effect": pk.get("effect")})
            src = (["starter"] if i in starter or d["tool"]["tier"] == 1 else []) + (["shop"] if d["tool"]["tier"] == 1 else ["craft"])
            out[i] = {"name": d["name"], "type": "tool", "rarity": d["rarity"], "tool": dict(d["tool"]),
                      "sources": [s for s in MAT_SOURCE_ORDER if s in src], "model": {"shape": "pickaxe", "length": 1.0},
                      "texture": tex, "lore": d["lore"]}
            continue
        if d["kind"] in ("ore", "ingot", "gem"):
            src = {"mine"} if d["kind"] in ("ore", "gem") else {"smelt"}
            src |= found.get(i, set())
            out[i] = {"name": d["name"], "type": "material", "rarity": d["rarity"], "mine_level": d["mine_level"], "mine_kind": d["kind"],
                      "sources": [s for s in MAT_SOURCE_ORDER if s in src], "model": {"shape": "icon"},
                      "texture": {"style": icons[i]["style"], "palette": icons[i]["palette"]}, "lore": d["lore"]}
            continue
        tex = d.get("texture") or {"style": icons[i]["style"], "palette": icons[i]["palette"]}
        out[i] = {"name": d["name"], "type": "material", "rarity": d["rarity"], "floor": d["floor"],
                  "sources": [s for s in MAT_SOURCE_ORDER if s in found.get(i, set())], "model": {"shape": "icon"},
                  "texture": {"style": tex["style"], "palette": tex["palette"]}, "lore": d["lore"]}
    # 지금 재료: 이름·설명 (드롭 명세 renames) · 부위 획득처 다시 셈 · 강화석은 제련소(새기기)도
    upd = {}
    for f, ps in D.parts_new.items():
        for p in ps:
            if p in out or p not in items0:
                continue
            u = upd.setdefault(p, {})
            u["sources"] = [s for s in MAT_SOURCE_ORDER if s in found.get(p, set())]
    for p, r in C.renames.items():
        if p in out:
            continue
        upd.setdefault(p, {}).update(r)
    for s in ("lesser_enhance_stone", "greater_enhance_stone", "supreme_enhance_stone"):
        if s in items0:
            src = list(items0[s].get("sources") or [])
            if "smelt" not in src:
                src.append("smelt")
            upd.setdefault(s, {})["sources"] = src
    return {"new": out, "update": upd}


def write_loot(G, spec, text, tables0, tables_c, changes):
    lines = text.split("\n")
    tables_at = next(i for i, l in enumerate(lines) if l.startswith("tables:"))
    tb = G.blocks(lines, tables_at + 1, len(lines))
    tweaks = collections.defaultdict(dict)
    for tid, idx, ch, note in spec.loot_tweaks():
        if note:
            tweaks[tid][idx] = note
    for tid in reversed(list(tb)):
        if tid not in tables_c or tables_c[tid] == tables0.get(tid):
            continue
        a, b = tb[tid]
        gc = None
        k = G.field(lines, a, b, "guaranteed")
        if k is not None and "#" in lines[k]:
            gc = lines[k][lines[k].index("#"):]
        body = G.emit_table_body(tables_c[tid], gc)
        if tweaks.get(tid):
            ei = next(j for j, l in enumerate(body) if l.startswith("    entries:"))
            rows = [j for j in range(ei + 1, len(body)) if body[j].startswith("      - ")]
            for idx, note in tweaks[tid].items():
                if idx < len(rows):
                    body[rows[idx]] += "   # " + note
        if lines[a + 1:b] != body:
            lines[a + 1:b] = body
            changes.append(f"(036) loot.{tid}")
    return "\n".join(lines)


def write_recipes(G, C, text, rec_out, changes):
    lines = text.split("\n")
    for old, new in RECIPE_DOC_SUBS:
        if old in lines:
            lines[lines.index(old)] = new
    rec_at = next(i for i, l in enumerate(lines) if l.startswith("recipes:"))
    # 지난번에 넣은 제련소 칸은 지우고 다시 쓴다
    if RECIPE_HEADER in lines:
        h = lines.index(RECIPE_HEADER)
        j = h + 1
        while j < len(lines) and not lines[j].startswith("  # ═════════"):
            j += 1
        del lines[h:j]
    rb = G.blocks(lines, rec_at + 1, len(lines))
    for rid, mats in rec_out.items():
        a, b = rb[rid]
        k = G.field(lines, a, b, "materials")
        want = f"    materials: {G.flow(mats)}"
        if lines[k] != want:
            lines[k] = want
            changes.append(f"(036) recipes.{rid}")
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append("")
    lines.append(RECIPE_HEADER)
    names = {i: C.items[i]["name"] for i in C.items}
    for group in ("smelting", "carving", "pickaxe_recipes"):
        for r in C.mat[group]:
            res_name = names.get(r["result"], {"lesser_enhance_stone": "하급 강화석", "greater_enhance_stone": "상급 강화석",
                                               "supreme_enhance_stone": "최상급 강화석"}.get(r["result"], r["result"]))
            lines.append(f"  {r['id']}:   # {res_name}")
            lines.append(f"    result: {r['result']}")
            lines.append(f"    category: {r['category']}")
            lines.append(f"    station: {r['station']}")
            lines.append(f"    materials: {G.flow(r['materials'])}")
            lines.append(f"    gold: {r['gold']}")
            if r.get("amount", 1) != 1:
                lines.append(f"    amount: {r['amount']}")
    lines.append("")
    return "\n".join(lines)


def write_items(G, C, D, text, final, items0, changes):
    lines = text.split("\n")
    items_at = next(i for i, l in enumerate(lines) if l.startswith("items:"))
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    # 지난번에 넣은 블록·머리 주석, 옛 재료 블록을 지운다
    gone = set(C.new_ids) | C.all_old
    ib = G.blocks(lines, items_at + 1, sets_at)
    for iid in reversed(list(ib)):
        if iid in gone:
            a, b = ib[iid]
            del lines[a:b]
            if iid in C.all_old:
                changes.append(f"(036) items: - {iid}")
    for h in (MINE_HEADER, TOOL_HEADER):
        while h in lines:
            i = lines.index(h)
            j = i
            while j + 1 < len(lines) and not lines[j + 1].strip():
                j += 1
            del lines[i:j + 1]
    sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
    ib = G.blocks(lines, items_at + 1, sets_at)
    # 지금 재료 고치기 (이름·설명·획득처)
    for iid, u in final["update"].items():
        if iid not in ib:
            continue
        a, b = ib[iid]
        for key in ("name", "sources", "lore"):
            if key not in u:
                continue
            v = u[key]
            t = f"    {key}: {qstr(v)}" if key in ("name", "lore") else f"    {key}: {G.flow(v)}"
            b2 = set_field(lines, a, b, key, t)
            if b2 != b:
                ib = G.blocks(lines, items_at + 1, next(i for i, l in enumerate(lines) if l.startswith("sets:")))
                a, b = ib[iid]
    # 새 몬스터 재료 · 몹 주제 부위: 그 층 재료 단락 (그 층 일반 재료 뒤 — 없으면 그 층 첫 재료 앞)
    floor_of = lambda i: items0.get(i, {}).get("floor")
    for iid in C.monster_new + C.drop_parts:
        v = final["new"][iid]
        f = v["floor"]
        sets_at = next(i for i, l in enumerate(lines) if l.startswith("sets:"))
        ib = G.blocks(lines, items_at + 1, sets_at)
        order = list(ib)
        same = [k for k in order if k in items0 and items0[k].get("type") == "material" and floor_of(k) == f and k not in STONES]
        commons = [k for k in same if items0[k].get("rarity") in ("common", "uncommon") and (items0[k].get("sources") or []) != ["boss"]]
        placed = [k for k in order if k in final["new"] and final["new"][k].get("floor") == f]
        anchor = (placed or commons)
        if anchor:
            at = ib[anchor[-1]][1]
        else:
            at = ib[same[0]][0]
        lines[at:at] = item_block(G, iid, v, MAT_KEYS)
    # 광산 재료 · 도구: 강화 재료 머리 주석 앞
    at = next(i for i, l in enumerate(lines) if l.startswith("  # ═════════ 강화 재료"))
    add = [MINE_HEADER]
    for iid in C.mine_ids:
        add.extend(item_block(G, iid, final["new"][iid], MAT_KEYS))
    add.append("")
    add.append(TOOL_HEADER)
    for iid in C.tool_ids:
        add.extend(item_block(G, iid, final["new"][iid], TOOL_KEYS))
    add.append("")
    lines[at:at] = add
    changes.append(f"(036) items: 새 {len(C.new_ids)}개")
    out = []
    for l in lines:
        if not l.strip() and out and not out[-1].strip():
            continue
        out.append(l)
    return "\n".join(out)


def write_npcs(G, C, text, changes):
    lines = text.split("\n")
    if NPC_HEADER in lines:
        h = lines.index(NPC_HEADER)
        j = h + 1
        while j < len(lines) and not lines[j].startswith("  # ═══"):
            j += 1
        del lines[h:j]
    at = next(i for i, l in enumerate(lines) if l.startswith("  # ═══════════════════════════ 층 안 이야기 NPC"))
    add = [NPC_HEADER, ""]
    for role in ("miner", "smelter"):
        n = C.vis["npcs"][role]
        ss = n["skin_style"]
        add += [f"  {role}:",
                f"    name: {qstr(n['name'])}",
                f"    nameplate: {qstr(n['nameplate'])}",
                f"    skin: {n['skin']}",
                f"    role: {role}",
                "    placement: overworld",
                "    skin_style:",
                f"      palette: {G.flow(ss['palette'])}",
                f"      outfit: {ss['outfit']}",
                f"      hair: {ss['hair']}",
                f"      accessories: {G.flow(ss['accessories'])}",
                "    dialogue:"]
        for d in C.extra["npc_dialogue"][role]:
            add.append(f"      - {qstr(d)}")
        add.append("")
    lines[at:at] = add
    changes.append("(036) npcs: 광부·제련공")
    return "\n".join(lines)


# ───────────────────────── 검사 ─────────────────────────
def ingot_s_scale(D, sup_b):
    """강화 S 주괴의 층 상수 = 0.5 × p_scale(재료 단계 그 층 몬스터 재료 1회 공급 중 큰 값) — gen_enhance 가 drops_036.json 에서 읽는다."""
    out = {}
    for f in sorted(D.fl):
        top = max(sup_b[f].get(m, 0) for m in D.parts_mat[f])
        out[f] = max(1.0, min(2.0, half_up(top / GE.REF_SUPPLY * 4) / 4)) * 0.5
    return out


def verify(texts, info=None):
    """0.3.6 결과 검사 (gen_035_content --check 가 0.3.5 verify 와 함께 부른다)."""
    C = Contract()
    bad = []
    if info:
        want = {int(k): v for k, v in C.extra["ingot_s_scale"].items()}
        got = ingot_s_scale(info["drops"], info["sup_b"])
        if got != want:
            bad.append(f"drops_036.json ingot_s_scale {want} ≠ 지금 루팅으로 셈한 값 {got}")
        for f, r in info["ore"].items():
            if abs(r["got"] - r["target"]) > 0.1 * r["target"]:
                bad.append(f"{f}층 던전 광석 {r['got']} ≠ 목표 {r['target']} (±10%)")
    items = yaml.safe_load(texts["items"])["items"]
    loot = yaml.safe_load(texts["loot"])["tables"]
    recipes = yaml.safe_load(texts["recipes"])["recipes"]
    npcs = yaml.safe_load(texts["npcs"])["npcs"]
    refs = set(items)
    for t in loot.values():
        for e in (t.get("guaranteed") or []) + (t.get("entries") or []):
            refs.update(ids_in(e))
    for r in recipes.values():
        refs.add(r.get("result"))
        refs.update(r.get("materials") or {})
    for n in npcs.values():
        refs.update(s.get("item") for s in (n.get("shop") or []))
    for old in sorted(C.all_old & refs):
        bad.append(f"옛 id 가 남음: {old}")
    for i in C.new_ids:
        if i not in items:
            bad.append(f"새 id 없음: {i}")
    n_smelter = sum(1 for r in recipes.values() if r.get("station") == "smelter")
    if n_smelter != 17:
        bad.append(f"제련소 레시피 {n_smelter} (17 이어야 함)")
    if len(recipes) != C.mat["derived"]["recipes_total_after"]:
        bad.append(f"레시피 {len(recipes)} ≠ {C.mat['derived']['recipes_total_after']}")
    for rid, r in recipes.items():
        res = items.get(r.get("result")) or {}
        if res.get("type") in GEAR_TYPES and not any(m in C.ingots for m in (r.get("materials") or {})):
            bad.append(f"recipes.{rid}: 장비 레시피에 주괴 없음")
        for m in (r.get("materials") or {}):
            if m not in items:
                bad.append(f"recipes.{rid}: 없는 재료 {m}")
    for tid, t in loot.items():
        for e in (t.get("guaranteed") or []):
            if any(x in C.ores for x in ids_in(e)):
                bad.append(f"loot.{tid}: 광석이 guaranteed 에 (LootRoller 는 guaranteed 의 chance 를 보지 않음)")
        for e in (t.get("guaranteed") or []) + (t.get("entries") or []):
            for x in ids_in(e):
                if x not in items:
                    bad.append(f"loot.{tid}: 없는 아이템 {x}")
    for role in ("miner", "smelter"):
        if not any(v.get("role") == role for v in npcs.values()):
            bad.append(f"npcs: role {role} 없음")
    for i in C.tool_ids:
        v = items.get(i) or {}
        if v.get("type") != "tool" or "level_req" in v or not v.get("tool"):
            bad.append(f"{i}: 곡괭이 꼴 (type tool · tool 블록 · level_req 없음)")
    return bad
