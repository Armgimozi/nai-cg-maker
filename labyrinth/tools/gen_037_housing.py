#!/usr/bin/env python3
"""집 자재 목록 생성기 (0.3.7) → plugin/src/main/resources/content/housing.yml.

관리인 모아의 [자재] 탭에서 파는 바닐라 블록 목록. 원본은 tools/data/037/housing_catalog.json 이다
(설계 design036/plots/plots_spec.json materials.catalog 386줄에서 돌 도끼를 뺀 385줄 — review R5).
흑요석·부싯돌은 팔지 않는다 — 서버장 결정 "네더 막아" (0.3.7, 네더 차원문은 core.NetherLock 이 막음).

규칙 (생성기와 HousingCatalogTest 가 같이 본다):
  · 쇠·금·구리·다이아·에메랄드·네더라이트 (주괴·조각·블록·광석·원석) 는 팔지 않는다. 구리는 이름에 copper 가 든 것 모두.
  · 녹이면 조각이 나오는 것 (쇠·금·구리·사슬 도구·갑옷·말 갑옷) 은 팔지 않는다.
  · 무기 (검·도끼·창·활·쇠뇌·화살·삼지창·철퇴) · 갑옷 은 팔지 않는다. 도구는 건축 도구 허용 목록만
    (나무·돌 괭이, 돌 삽, 돌 곡괭이, 가위).
  · TNT·부싯돌·화염구·용암 양동이 · 피스톤·발사기·공급기·제작기·관측기·레일·수레 · 레드스톤 가루·횃불·중계기·비교기 ·
    엔더 진주·엔더 상자·셜커 · 신호기·스포너·알·명령 블록 · 청금석·석영·흑요석·모루·마법 부여대·양조대 는 팔지 않는다.
  · 블록 id 는 tools/village/blockdata.json 에 있어야 한다. 블록이 아닌 것은 ITEMS 허용 목록만.
  · 값: 기본·색 블록 한 칸 0.25~1G · 원목 ≥ 판자 4개 값 · 계단 ≥ 바탕 블록 1.5배 · 반블록 ≥ 바탕 0.5배.
    되팔기는 없다 (바닐라 아이템은 SellPrices 가 이미 거절).

사용:
  python3 tools/gen_037_housing.py            # housing.yml 쓰기
  python3 tools/gen_037_housing.py --check    # 쓰지 않고 규칙 검사 + 지금 파일과 같은지 (같으면 종료 코드 0)
  python3 tools/gen_037_housing.py --import design036/plots/plots_spec.json   # 원본 json 을 설계에서 다시 만들기 (돌 도끼 빼고 메모 고침)
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools/data/037/housing_catalog.json"
OUT = ROOT / "plugin/src/main/resources/content/housing.yml"
BLOCKDATA = ROOT / "tools/village/blockdata.json"

# 탭 (차례 = 메뉴 차례). id 는 메뉴·설정에서 쓰는 영문 키.
TABS = [
    ("basic", "기본 블록", "stone_bricks"),
    ("color", "색 블록", "white_wool"),
    ("wood", "나무", "oak_log"),
    ("stairs", "계단·반블록", "oak_stairs"),
    ("doors", "문·창·울타리", "oak_door"),
    ("light", "빛", "lantern"),
    ("furniture", "가구·쓸모", "chest"),
    ("garden", "정원", "poppy"),
    ("deco", "꾸밈", "white_banner"),
]

# 블록이 아닌데 파는 것 (blockdata.json 에 없음)
ITEMS = {"item_frame", "painting", "armor_stand", "water_bucket", "wheat_seeds", "carrot", "potato", "beetroot_seeds",
         "pumpkin_seeds", "melon_seeds", "sweet_berries", "bone_meal",
         "wooden_hoe", "stone_hoe", "stone_shovel", "stone_pickaxe", "shears"}
# 건축 도구 허용 목록 (review R5 — 돌 도끼는 무기라 뺌)
TOOLS = {"wooden_hoe", "stone_hoe", "stone_shovel", "stone_pickaxe", "shears"}

BANNED_EXACT = {
    "tnt", "tnt_minecart", "flint_and_steel", "fire_charge", "lava_bucket", "wind_charge",
    "piston", "sticky_piston", "dispenser", "dropper", "crafter", "observer",
    "rail", "powered_rail", "detector_rail", "activator_rail",
    "minecart", "chest_minecart", "furnace_minecart", "hopper_minecart", "command_block_minecart",
    "redstone", "redstone_torch", "redstone_wall_torch", "repeater", "comparator", "redstone_block",
    "ender_pearl", "ender_eye", "ender_chest", "end_crystal", "respawn_anchor",
    "beacon", "spawner", "trial_spawner", "vault", "command_block", "chain_command_block", "repeating_command_block",
    "structure_block", "structure_void", "jigsaw", "barrier", "light",
    "anvil", "chipped_anvil", "damaged_anvil", "enchanting_table", "brewing_stand",
    "bow", "crossbow", "arrow", "trident", "mace",
    "egg", "blue_egg", "brown_egg", "turtle_egg", "sniffer_egg", "dragon_egg",
    "elytra", "gilded_blackstone", "ancient_debris", "raw_iron", "raw_gold", "raw_iron_block", "raw_gold_block",
    "iron_ingot", "iron_nugget", "iron_block", "iron_ore", "deepslate_iron_ore",
    "gold_ingot", "gold_nugget", "gold_block", "gold_ore", "deepslate_gold_ore", "nether_gold_ore",
}
# 이름에 들어 있으면 팔지 않는 말 (구리·금·다이아·에메랄드·네더라이트·청금석·석영·흑요석·셜커)
BANNED_WORDS = ("copper", "gold", "diamond", "emerald", "netherite", "lapis", "quartz", "obsidian", "shulker")
TOOL_SUFFIX = ("_pickaxe", "_shovel", "_hoe", "_axe")
WEAPON_SUFFIX = ("_sword", "_axe", "_spear")
ARMOR_SUFFIX = ("_helmet", "_chestplate", "_leggings", "_boots", "_horse_armor", "_nautilus_armor")
SMELT_METALS = ("iron_", "golden_", "copper_", "chainmail_")


def ban_reason(i):
    """팔면 안 되는 이유 (팔아도 되면 None). Java HousingCatalog.banReason 과 같다."""
    if i in BANNED_EXACT:
        return "금지 목록"
    if i.startswith(SMELT_METALS) and (i.endswith(TOOL_SUFFIX) or i.endswith(WEAPON_SUFFIX) or i.endswith(ARMOR_SUFFIX)):
        return "녹이면 조각이 나옴"
    for w in BANNED_WORDS:
        if w in i:
            return "금지 재료 (" + w + ")"
    if i.endswith(ARMOR_SUFFIX) or i == "turtle_helmet" or i == "wolf_armor":
        return "갑옷"
    if i.endswith(("_sword", "_spear", "_arrow")):
        return "무기"
    if i.endswith(TOOL_SUFFIX) or i in ("shears", "brush", "fishing_rod", "carrot_on_a_stick", "warped_fungus_on_a_stick"):
        return None if i in TOOLS else ("무기" if i.endswith("_axe") else "도구 (허용 목록 밖)")
    if i.endswith("_spawn_egg"):
        return "알"
    if i.endswith("_bucket") and i != "water_bucket":
        return "양동이 (물 양동이만)"
    return None


def base_of(i, units):
    """계단·반블록·벽 → 바탕 블록 id (목록에 있는 것, 없으면 None)."""
    for suf in ("_stairs", "_slab", "_wall"):
        if i.endswith(suf):
            stem = i[: -len(suf)]
            for cand in (stem + "_planks", stem, stem + "s", stem.replace("brick", "bricks"), stem.replace("tile", "tiles")):
                if cand in units:
                    return cand
    return None


def load_data():
    return json.loads(DATA.read_text(encoding="utf-8"))


def check(data):
    """규칙 검사 → 오류 줄 목록."""
    errs = []
    rows = data["catalog"]
    blocks = json.loads(BLOCKDATA.read_text(encoding="utf-8"))["blocks"]
    names = {t[1] for t in TABS}
    seen = set()
    units = {}
    for r in rows:
        i = r["item"].removeprefix("minecraft:")
        if i in seen:
            errs.append(f"{i}: 두 번 나옴")
        seen.add(i)
        if r["category"] not in names:
            errs.append(f"{i}: 모르는 탭 {r['category']}")
        why = ban_reason(i)
        if why:
            errs.append(f"{i}: 팔면 안 됨 ({why})")
        if i not in blocks and i not in ITEMS:
            errs.append(f"{i}: blockdata.json 에 없는 블록 (블록이 아니면 ITEMS 에 적기)")
        if not (isinstance(r["bundle"], int) and 1 <= r["bundle"] <= 64):
            errs.append(f"{i}: 묶음 수 {r['bundle']}")
        if not (isinstance(r["price"], int) and r["price"] >= 1):
            errs.append(f"{i}: 값 {r['price']}")
        units[i] = r["price"] / r["bundle"]
    for r in rows:
        i = r["item"].removeprefix("minecraft:")
        u = units[i]
        if r["category"] in ("기본 블록", "색 블록") and not (0.25 - 1e-9 <= u <= 1 + 1e-9):
            errs.append(f"{i}: 한 칸 {u:.3f}G — 0.25~1G 밖")
        if i.endswith("_log") and not i.startswith("stripped_"):
            planks = i[: -len("_log")] + "_planks"
            if planks in units and u + 1e-9 < 4 * units[planks]:
                errs.append(f"{i}: 원목 {u:.3f}G < 판자 4개 {4 * units[planks]:.3f}G")
        b = base_of(i, units)
        if i.endswith("_stairs") and b and u + 1e-9 < 1.5 * units[b]:
            errs.append(f"{i}: 계단 {u:.3f}G < 바탕 {b} ×1.5")
        if i.endswith("_slab") and b and u + 1e-9 < 0.5 * units[b]:
            errs.append(f"{i}: 반블록 {u:.3f}G < 바탕 {b} ×0.5")
    if "stone_axe" in seen:
        errs.append("stone_axe: 돌 도끼는 무기라 뺌 (review R5)")
    if len(rows) != data.get("count", len(rows)):
        errs.append(f"줄 수 {len(rows)} ≠ count {data.get('count')}")
    return errs


def yq(s):
    """YAML 한 줄 문자열 (늘 큰따옴표)."""
    return json.dumps(s, ensure_ascii=False)


def render(data):
    rows = data["catalog"]
    out = [
        "# ─────────────────────────────────────────────────────────────────────────────",
        "# housing.yml — 마을 관리인 모아의 [자재] 탭 (0.3.7 집). tools/gen_037_housing.py 생성물.",
        "#   원본: tools/data/037/housing_catalog.json (다시 생성하면 덮어씀 — 값을 바꾸려면 원본을 고치고 다시 돌리세요)",
        "#   tabs[].items[]: id = 바닐라 아이템 id · bundle = 한 번에 사는 개수 · price = 그 묶음 값 (골드) · note = 설명 한 줄 (선택)",
        "#   값 배율은 config.yml homes.shop_price_multiplier (0.1 이상). 바닐라 아이템은 되팔 수 없다.",
        "#   쇠·금·구리 같은 금속, 무기·갑옷, 폭발물, 레드스톤 장치는 적어도 팔지 않는다 (플러그인이 건너뛰고 로그에 남김).",
        "# ─────────────────────────────────────────────────────────────────────────────",
        "version: 1",
        f"count: {len(rows)}",
        "tabs:",
    ]
    for tid, name, icon in TABS:
        items = [r for r in rows if r["category"] == name]
        out.append(f"  - id: {tid}")
        out.append(f"    name: {yq(name)}")
        out.append(f"    icon: {icon}")
        out.append("    items:")
        for r in items:
            i = r["item"].removeprefix("minecraft:")
            line = f"      - {{id: {i}, bundle: {r['bundle']}, price: {r['price']}"
            if r.get("note"):
                line += f", note: {yq(r['note'])}"
            out.append(line + "}")
    return "\n".join(out) + "\n"


NOTE_FIX = {
    "chest": "",                                   # "상자 수 한도에 셈" — 상자 수 한도는 뺀 기능 (R5 메모)
    "campfire": "모닥불은 장식",                    # "화덕은 따로" — 화덕은 뺀 기능
    "decorated_pot": "아이템 한 묶음을 넣을 수 있음",  # "→ 상자 수 한도에 셈" 뺌
}


def do_import(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    rows = []
    for r in spec["materials"]["catalog"]:
        i = r["item"].removeprefix("minecraft:")
        if i == "stone_axe":
            continue
        note = NOTE_FIX.get(i, r.get("note") or "")
        rows.append({"category": r["category"], "item": "minecraft:" + i, "bundle": r["bundle"], "price": r["price"], "note": note})
    data = {
        "version": 1,
        "source": "design036/plots/plots_spec.json materials.catalog (386줄) — stone_axe 뺌 (review R5), chest·campfire·decorated_pot 메모 고침",
        "count": len(rows),
        "catalog": rows,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✔ {DATA.relative_to(ROOT)} — {len(rows)}줄")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--import", dest="imp")
    a = ap.parse_args()
    if a.imp:
        do_import(a.imp)
    data = load_data()
    errs = check(data)
    if errs:
        for e in errs:
            print("✘", e)
        sys.exit(1)
    text = render(data)
    y = yaml.safe_load(text)
    n = sum(len(t["items"]) for t in y["tabs"])
    if n != len(data["catalog"]):
        print("✘ 탭에 들어가지 않은 줄이 있음", n, len(data["catalog"]))
        sys.exit(1)
    if a.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print(f"✘ {OUT.relative_to(ROOT)} 이 생성 결과와 다름 — python3 tools/gen_037_housing.py 로 다시 쓰세요")
            sys.exit(1)
        print(f"✔ housing.yml 이 생성 결과와 같음 ({n}가지, 탭 {len(TABS)}, 금지 0)")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"✔ {OUT.relative_to(ROOT)} — {n}가지, 탭 {len(TABS)}")


if __name__ == "__main__":
    main()
