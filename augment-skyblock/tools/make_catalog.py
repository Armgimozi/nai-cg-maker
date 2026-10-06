#!/usr/bin/env python3
"""
증강 · 무기(곡괭이 포함) · 갑옷 도감 페이지(HTML 한 장)를 만든다.
  python3 tools/make_catalog.py [출력.html]
플러그인 YAML(augments, weapons, skills, armor, items)과 pack/gen_pack.py 가 만든 그림(dist/catalog/)을 읽는다.
그림은 data: URI 로 페이지 안에 넣는다.
"""
import base64
import html
import math
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "plugin", "src", "main", "resources")
CAT = os.path.join(ROOT, "dist", "catalog")

ELEMENT = {
    "iron": ("철", "#c9ced6"), "stone": ("돌", "#a8a8a8"), "wood": ("나무", "#c99858"), "bone": ("뼈", "#d8d0ac"),
    "copper": ("구리", "#d8805a"), "flame": ("화염", "#ff7a2d"), "frost": ("서리", "#6cc4f4"), "storm": ("번개", "#a890ff"),
    "venom": ("독", "#86c840"), "ocean": ("바다", "#38b8d8"), "earth": ("대지", "#c09858"), "wind": ("바람", "#78d8c0"),
    "holy": ("빛", "#e8c850"), "nature": ("숲", "#62b848"), "blood": ("피", "#e8405a"), "abyss": ("심연", "#a060f0"),
    "shadow": ("그림자", "#8a8ab0"), "star": ("별", "#8898f8"), "crystal": ("수정", "#c088f0"), "prism": ("프리즘", "prism"),
    "gold": ("황금", "#e8c030"), "ender": ("엔더", "#38c8a0"), "sun": ("태양", "#f0b830"), "doom": ("종말", "#e82a5a"),
}
POOLS = [("basic", "섬 초반", "시작의 섬과 흔한 섬(숲, 광산, 목장…)의 재료로 만든다"),
         ("island", "섬 재료", "드문 섬의 재료(피뢰침, 프리즈머린, 발광석…)로 만든다"),
         ("frost", "서리 균열", "서리 정수로 만든다"), ("flame", "화염 균열", "화염 정수로 만든다"),
         ("void", "공허 균열", "공허 정수로 만든다"), ("boss", "보스", "보스가 떨구거나 프리즘 결정으로 만든다"),
         ("prism", "프리즘", "프리즘 결정으로 만든다")]
PICK_NOTE = "앞 곡괭이를 넣어 한 단계씩 강화한다 · 바닐라 채굴 속도는 돌 4, 철 6, 다이아몬드 8, 네더라이트 9"
TYPES = {"sword": "검", "greatsword": "대검", "dagger": "단검", "katana": "카타나", "axe": "도끼", "hammer": "망치",
         "spear": "창", "scythe": "낫", "staff": "지팡이", "wand": "마법봉", "bow": "활", "pickaxe": "곡괭이"}
# 무기 내구도·수리 재료를 안 적었을 때의 기본값. 플러그인 Gear.weaponDurability · weaponRepair 와 같은 표
POOL_DURABILITY = {"basic": 250, "island": 750, "frost": 1561, "flame": 1561, "void": 1561, "boss": 2031, "prism": 3000}
ELEMENT_REPAIR = {
    "stone": "COBBLESTONE", "wood": "PLANKS", "bone": "BONE", "copper": "COPPER_INGOT", "gold": "GOLD_INGOT", "holy": "GOLD_INGOT",
    "crystal": "AMETHYST_SHARD", "nature": "VINE", "storm": "LIGHTNING_ROD", "venom": "SPIDER_EYE", "ocean": "DRIED_KELP_BLOCK",
    "earth": "MOSSY_COBBLESTONE", "wind": "PHANTOM_MEMBRANE", "blood": "REDSTONE", "star": "END_ROD",
}
# 갑옷 부위별 최대 내구도 = armor.yml 의 배수 × 이 값 (ArmorService 의 슬롯 배수, 바닐라와 같다)
SLOT_DURABILITY = {"helmet": 11, "chestplate": 16, "leggings": 15, "boots": 13}
# 곡괭이 채굴 등급: 이름과 그 등급으로 캐도 나오지 않는 블록 (바닐라 incorrect_for_*_tool 태그)
MINING_TIERS = {
    "stone": ("돌", "다이아몬드·금·레드스톤·에메랄드 광석과 흑요석은 캐도 나오지 않는다"),
    "iron": ("철", "흑요석·우는 흑요석·고대 잔해는 캐도 나오지 않는다"),
    "diamond": ("다이아몬드", "흑요석과 고대 잔해까지 다 캔다"),
    "netherite": ("네더라이트", "흑요석과 고대 잔해까지 다 캔다"),
}
TIERS = [("SILVER", "실버"), ("GOLD", "골드"), ("PRISM", "프리즘")]
# 스킬 칸마다 쓰는 법. 플러그인 WeaponDef.inputLabel 과 같은 글을 쓴다
SKILL_INPUTS = (("skill", "우클릭"), ("skill2", "웅크리기+우클릭"), ("skill3", "웅크리기+좌클릭"))
BOW_SKILL_INPUTS = (("skill", "웅크리기+당겨 쏘기"), ("skill2", "웅크리기+좌클릭"))
SLOTS = [("helmet", "투구"), ("chestplate", "갑옷"), ("leggings", "각반"), ("boots", "신발")]
MATERIAL = {
    "STICK": "막대기", "STRING": "실", "FEATHER": "깃털", "SPIDER_EYE": "거미 눈", "PACKED_ICE": "단단한 얼음",
    "MAGMA_BLOCK": "마그마 블록", "BLAZE_ROD": "블레이즈 막대", "OBSIDIAN": "흑요석", "DIAMOND": "다이아몬드",
    "DIAMOND_BLOCK": "다이아몬드 블록", "LIGHTNING_ROD": "피뢰침", "LAPIS_BLOCK": "청금석 블록", "GLOWSTONE": "발광석",
    "REDSTONE_BLOCK": "레드스톤 블록", "COBBLESTONE": "조약돌", "IRON_INGOT": "철 주괴", "AMETHYST_SHARD": "자수정 조각",
    "COPPER_BLOCK": "구리 블록", "FERMENTED_SPIDER_EYE": "발효된 거미 눈", "MOSSY_COBBLESTONE": "이끼 낀 조약돌",
    "MOSS_BLOCK": "이끼 블록", "GOLD_BLOCK": "금 블록", "OAK_LOG": "참나무 원목", "BONE": "뼈", "COPPER_INGOT": "구리 주괴",
    "CACTUS": "선인장", "GOLD_INGOT": "금 주괴", "OAK_PLANKS": "참나무 판자", "WHITE_WOOL": "흰색 양털",
    "NAUTILUS_SHELL": "앵무조개 껍데기", "BONE_BLOCK": "뼈 블록", "PHANTOM_MEMBRANE": "팬텀 막", "ENDER_PEARL": "엔더 진주",
    "EMERALD_BLOCK": "에메랄드 블록", "LEATHER": "가죽",
    "ACACIA_LOG": "아카시아나무 원목", "AMETHYST_BLOCK": "자수정 블록", "BAMBOO": "대나무", "BIRCH_LOG": "자작나무 원목",
    "BIRCH_PLANKS": "자작나무 판자", "BLUE_ICE": "푸른 얼음", "CALCITE": "방해석", "CHERRY_SAPLING": "벚나무 묘목", "COAL_BLOCK": "석탄 블록",
    "CRIMSON_STEM": "진홍빛 자루", "CRYING_OBSIDIAN": "우는 흑요석", "DARK_OAK_SAPLING": "짙은 참나무 묘목",
    "DARK_PRISMARINE": "짙은 프리즈머린", "DRIED_KELP_BLOCK": "말린 켈프 블록", "EMERALD": "에메랄드", "END_ROD": "엔드 막대기",
    "FIRE_CHARGE": "화염구", "FLINT": "부싯돌", "FLOWERING_AZALEA": "꽃 핀 진달래", "HAY_BLOCK": "건초 더미", "HONEYCOMB": "벌집 조각",
    "ICE": "얼음", "LANTERN": "랜턴", "LAVA_BUCKET": "용암 양동이", "MAGMA_CREAM": "마그마 크림", "NETHER_WART_BLOCK": "네더 사마귀 블록",
    "OAK_SLAB": "참나무 반 블록", "PACKED_MUD": "굳은 진흙", "POINTED_DRIPSTONE": "뾰족한 점적석", "POLISHED_GRANITE": "윤나는 화강암",
    "PRISMARINE": "프리즈머린", "PRISMARINE_CRYSTALS": "프리즈머린 수정", "PUFFERFISH": "복어", "PURPUR_PILLAR": "퍼퍼 기둥",
    "QUARTZ": "네더 석영", "SEA_LANTERN": "바다 랜턴", "SEA_PICKLE": "불우렁쉥이", "SHROOMLIGHT": "버섯불", "SLIME_BALL": "슬라임볼",
    "SNOW_BLOCK": "눈 블록", "SOUL_LANTERN": "영혼 랜턴", "SPRUCE_LOG": "가문비나무 원목", "STONE": "돌", "TINTED_GLASS": "착색 유리",
    "VINE": "덩굴", "TUFF": "응회암", "WEATHERED_COPPER": "풍화된 구리", "OXIDIZED_COPPER": "산화된 구리",
    "REDSTONE": "레드스톤 가루",
}


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def strip_mm(s):
    return re.sub(r"<[^>]+>", "", str(s))


def esc(s):
    return html.escape(strip_mm(s))


def img_uri(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def ingredient_name(spec, items, weapons, armor):
    spec = str(spec)
    if spec.startswith("item:"):
        d = items.get(spec[5:])
        return strip_mm(d["name"]) if d else spec[5:]
    if spec.startswith("weapon:"):
        w = weapons.get(spec[7:])
        return strip_mm(w["name"]) if w else spec[7:]
    if spec.startswith("armor:"):
        names = [strip_mm(armor[x]["name"]) for x in spec[6:].split(",") if x in armor]
        return "/".join(names) + " 갑옷(같은 부위)"
    if spec not in MATERIAL:
        # 영어 이름이 그대로 도감에 나가지 않게 멈춘다
        sys.exit("재료 이름이 없음: " + spec)
    return MATERIAL[spec]


def recipe_text(recipe, items, weapons, armor):
    """조합 재료 한 줄. 다른 무기를 넣는 조합은 '강화:' 로 그 무기를 앞에 적어 무엇을 강화하는지 보이게 한다."""
    if not recipe:
        return ""
    counts = {}
    for row in recipe["shape"]:
        for ch in row:
            if ch != " ":
                counts[ch] = counts.get(ch, 0) + 1
    bases, parts = [], []
    for ch, n in counts.items():
        spec = recipe["ingredients"].get(ch)
        if spec is None:
            continue
        name = ingredient_name(spec, items, weapons, armor)
        if str(spec).startswith("weapon:"):
            bases.append(name)
        else:
            parts.append(f"{name} ×{n}")
    if bases:
        return "강화: " + " + ".join(bases) + " + " + ", ".join(parts)
    return "조합: " + ", ".join(parts)


def element_chip(el):
    name, col = ELEMENT.get(el, (el, "#999"))
    style = "background: var(--prism)" if col == "prism" else f"background:{col}"
    return f'<span class="el"><i style="{style}"></i>{esc(name)}</span>'


def weapon_durability(w):
    """최대 내구도. 안 적었으면 얻는 곳으로 정하고, 빠른 무기는 공격 속도만큼(최대 1.4배), 활은 384 이상."""
    if w.get("durability", 0) > 0:
        return int(w["durability"])
    base = POOL_DURABILITY.get(w.get("pool", "basic"), 750)
    if w.get("type") == "bow":
        return max(base, 384)
    if w.get("type") == "pickaxe":
        return base
    k = max(1.0, min(1.4, w.get("speed", 1.6) / 1.6))
    return int(math.floor(base * k + 0.5))  # 자바 Math.round 와 같게 (파이썬 round 는 짝수 쪽으로 반올림)


def weapon_repair(w):
    if w.get("repair"):
        return str(w["repair"])
    pool = w.get("pool", "basic")
    if pool in ("frost", "flame", "void"):
        return "item:essence_" + pool
    if pool == "boss":
        return "DIAMOND"
    if pool == "prism":
        return "item:prism_crystal"
    return ELEMENT_REPAIR.get(str(w.get("element", "iron")).lower(), "IRON_INGOT")


def repair_name(spec, items, weapons, armor):
    """수리 재료 이름. 여러 개는 쉼표로 적으므로 / 로 잇고, PLANKS 는 아무 판자 (Gear.Repair.label 과 같은 글)."""
    spec = str(spec).strip()
    if spec.startswith("item:"):
        return ingredient_name(spec, items, weapons, armor)
    names = []
    for part in spec.split(","):
        p = part.strip().upper()
        names.append("판자" if p in ("PLANKS", "#PLANKS") else ingredient_name(p, items, weapons, armor))
    return "/".join(names)


def roman(n):
    return {1: "I", 2: "II", 3: "III", 4: "IV"}.get(n, str(n))


def weapon_card(wid, w, skills, items, weapons, armor):
    uri = img_uri(os.path.join(CAT, "weapons", wid + ".png"))
    pic = f'<img src="{uri}" alt="" loading="lazy">' if uri else '<div class="noimg"></div>'
    pool = w.get("pool", "basic")
    is_bow, is_pick = w.get("type") == "bow", w.get("type") == "pickaxe"
    dur = f'<div><dt>내구도</dt><dd>{weapon_durability(w)}</dd></div>'
    extra = ""
    if is_pick:
        # 곡괭이는 스킬 대신 채굴 등급·속도와 패시브를 보인다 (플러그인 무기 설명과 같은 글)
        mining = w.get("mining") or {}
        tier = str(mining.get("tier", "iron")).lower()
        tname, tnote = MINING_TIERS.get(tier, (tier, ""))
        stat = (f'<dl><div><dt>채굴 등급</dt><dd>{esc(tname)}</dd></div><div><dt>채굴 속도</dt><dd>{mining.get("speed", 6):g}</dd></div>'
                f'<div><dt>공격력</dt><dd>{w.get("damage", 6):g}</dd></div>{dur}</dl>')
        perks = w.get("perks") or {}
        lines = []
        if perks.get("auto_smelt"):
            lines.append("캐낸 광석이 곧바로 제련된다")
        if perks.get("haste", 0) > 0:
            lines.append(f'들고 있는 동안 성급함 {roman(perks["haste"])}')
        body = "".join(f'<li><b>패시브</b> {esc(t)}</li>' for t in lines)
        body = (f'<ul class="skills">{body}</ul>' if body else "") + (f'<p class="mine">{esc(tnote)}</p>' if tnote else "")
    else:
        stat = (f'<dl><div><dt>화살 피해</dt><dd>{w["damage"]:g}</dd></div>{dur}</dl>' if is_bow else
                f'<dl><div><dt>공격력</dt><dd>{w["damage"]:g}</dd></div><div><dt>공격 속도</dt><dd>{w.get("speed", 1.6):g}</dd></div>{dur}</dl>')
        sk = []
        for key, label in (BOW_SKILL_INPUTS if is_bow else SKILL_INPUTS):
            s = skills.get(w.get(key) or "")
            if s:
                sk.append(f'<li><b>{label}</b> {esc(s["name"])} <small>{s.get("cooldown", 0):g}초</small>'
                          f'<span>{esc(" ".join(s.get("description", [])))}</span></li>')
        passive = (w.get("passive") or {}).get("description")
        pas = f'<p class="passive">{esc(passive)}</p>' if passive else ""
        # 초반 무기 대부분은 스킬이 없다. 빈 칸 대신 한 줄로 알려 준다
        body = (f'<ul class="skills">{"".join(sk)}</ul>' if sk else
                f'<p class="noskill">스킬 없음 · {"기본 공격과 패시브" if passive else "기본 공격"}</p>') + pas
        if is_bow:
            # 화살이 줄지 않는 활은 보스·프리즘 활만 (WeaponDef.infiniteArrows)
            extra = ('<p class="gear">화살 1개만 있으면 줄지 않는다 · 무한은 붙지 않는다</p>' if pool in ("boss", "prism") else
                     '<p class="gear">화살을 쓴다 · 무한을 붙일 수 있다</p>')
    extra += f'<p class="gear">수리 재료 {esc(repair_name(weapon_repair(w), items, weapons, armor))}</p>'
    src = w.get("source")
    rec = recipe_text(w.get("recipe"), items, weapons, armor)
    # source 가 있어도 조합법이 있으면 함께 적는다 (보스가 떨구면서 만들 수도 있는 무기)
    obtain = "<br>".join(esc(t) for t in (src, rec) if t) or esc(dict((p, s) for p, _, s in POOLS).get(pool, ""))
    # 곡괭이는 맨 위(프리즘)만 아우라가 있다
    aura = '<span class="aura">아우라</span>' if pool in ("boss", "prism") and (not is_pick or pool == "prism") else ""
    return (f'<article class="card wep" data-q="{esc(w["name"])} {TYPES.get(w["type"], "")} {ELEMENT.get(w.get("element"), ("",))[0]}">'
            f'<div class="pic">{pic}</div><div class="body"><header><h4>{esc(w["name"])}</h4>{aura}</header>'
            f'<div class="meta">{TYPES.get(w["type"], w["type"])} · {element_chip(w.get("element"))}</div>{stat}'
            f'{body}{extra}<p class="obtain">{obtain}</p></div></article>')


def build():
    augments = load("augments.yml")
    weapons = load("weapons.yml")
    skills = load("skills.yml")
    armor = load("armor.yml")
    items = load("items.yml")

    # ---- 증강
    aug_html = []
    tier_counts = {}
    for code, kname in TIERS:
        cards = []
        for aid, a in augments.items():
            if not isinstance(a, dict) or a.get("tier") != code:
                continue
            desc = "".join(f"<p>{esc(d)}</p>" for d in a.get("description", []))
            stacks = a.get("max_stacks", 1)
            st = f'<span class="stack">최대 {stacks}중첩</span>' if stacks > 1 else ""
            cards.append(f'<article class="card aug t-{code.lower()}" data-q="{esc(a["name"])} {esc(" ".join(a.get("description", [])))}">'
                         f'<header><h4>{esc(a["name"])}</h4>{st}</header>{desc}</article>')
        tier_counts[code] = len(cards)
        aug_html.append(f'<section class="group" id="aug-{code.lower()}"><h3 class="tier-h t-{code.lower()}">{kname} <span>{len(cards)}</span></h3>'
                        f'<div class="grid">{"".join(cards)}</div></section>')

    # ---- 무기 (곡괭이는 얻는 곳과 상관없이 한 묶음으로, 강화 차례인 weapons.yml 순서대로)
    weps = {k: v for k, v in weapons.items() if isinstance(v, dict)}
    groups = [(pool, pname, psrc, [(k, w) for k, w in weps.items() if w.get("pool") == pool and w.get("type") != "pickaxe"])
              for pool, pname, psrc in POOLS]
    groups.append(("pickaxe", "곡괭이", PICK_NOTE, [(k, w) for k, w in weps.items() if w.get("type") == "pickaxe"]))
    n_wep = sum(len(g[3]) for g in groups if g[0] != "pickaxe")
    n_pick = len(groups[-1][3])
    wep_html = []
    for gid, gname, gsrc, members in groups:
        cards = [weapon_card(wid, w, skills, items, weapons, armor) for wid, w in members]
        if cards:
            wep_html.append(f'<section class="group" id="wep-{gid}"><h3 class="pool-h">{gname} <span>{len(cards)}</span>'
                            f'<small>{gsrc}</small></h3><div class="grid wide">{"".join(cards)}</div></section>')

    # ---- 갑옷
    arm_html = []
    for sid, a in armor.items():
        uri = img_uri(os.path.join(CAT, "armor", sid + ".png"))
        pic = f'<img src="{uri}" alt="" loading="lazy">' if uri else '<div class="noimg"></div>'
        # 부위마다 방어 · 강도 · 내구도를 칸으로 (폰 폭에서도 한 줄에 들어가게 이름은 머리줄에만)
        mult = max(1, int(a.get("durability", 33)))  # ArmorService 기본값과 같게
        tough = any(len(a["pieces"][slot]) > 1 and a["pieces"][slot][1] for slot, _ in SLOTS)
        rows = ['<tr><th></th><th>방어</th>' + ('<th>강도</th>' if tough else '') + '<th>내구도</th></tr>']
        for slot, sname in SLOTS:
            v = a["pieces"][slot]
            t = f'<td>{v[1]:g}</td>' if tough else ""
            rows.append(f'<tr><th>{sname}</th><td>{v[0]:g}</td>{t}<td>{mult * SLOT_DURABILITY[slot]}</td></tr>')
        fix = f'<p class="gear">수리 재료 {esc(repair_name(a.get("repair", "DIAMOND"), items, weapons, armor))}</p>'
        bonus = "".join(f'<li><b>{k}세트</b> {esc(d)}</li>' for k, d in (a.get("bonus_desc") or {}).items())
        rec = a.get("recipe")
        how = esc(a.get("source", ""))
        if rec and "shape" not in rec:
            how += f'<br><small>부위마다: {esc(ingredient_name(rec["M"], items, weapons, armor))} + {esc(ingredient_name(rec["S"], items, weapons, armor))} 1개</small>'
        elif rec:
            counts = {}
            for row in rec["shape"]:
                for ch in row:
                    if ch != " ":
                        counts[ch] = counts.get(ch, 0) + 1
            how += "<br><small>부위마다: " + ", ".join(
                f'{esc(ingredient_name(rec[ch], items, weapons, armor))} ×{n}' for ch, n in counts.items()) + "</small>"
        arm_html.append(
            f'<article class="card arm" data-q="{esc(a["name"])}"><div class="pic">{pic}</div><div class="body">'
            f'<header><h4>{esc(a["name"])} 세트</h4></header><table>{"".join(rows)}</table>{fix}'
            f'<ul class="bonus">{bonus}</ul><p class="obtain">{how}</p></div></article>')

    n_aug = sum(tier_counts.values())
    return PAGE.format(
        n_aug=n_aug, n_wep=n_wep, n_pick=n_pick, n_arm=len(armor),
        silver=tier_counts.get("SILVER", 0), gold=tier_counts.get("GOLD", 0), prism=tier_counts.get("PRISM", 0),
        aug="".join(aug_html), wep="".join(wep_html), arm="".join(arm_html),
        pools="".join(f'<a href="#wep-{g[0]}">{g[1]}</a>' for g in groups if g[3]))


PAGE = """<title>증강 스카이블럭 도감</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=IBM+Plex+Sans+KR:wght@400;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* 레이아웃: 위에 고정된 목차와 찾기, 그 아래 증강 · 무기 · 갑옷이 차례로. 카드는 칸에 맞춰 흐른다 */
:root {{
  --bg: #e9ecf1; --surface: #f7f8fa; --ink: #161a22; --muted: #5a6373; --line: #d3d8e0;
  --accent: #5b3fd0; --silver: #7d8ca0; --gold: #a57a08;
  --prism: linear-gradient(90deg, #ff6b9d, #ffb84d, #4fd88f, #4fb4ff, #b86bff);
  --display: "Black Han Sans", "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  --body: "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #0e1117; --surface: #161a23; --ink: #e7eaf1; --muted: #98a1b2; --line: #262c38;
  --accent: #a58cff; --silver: #b4c2d4; --gold: #e3b63a; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #0e1117; --surface: #161a23; --ink: #e7eaf1; --muted: #98a1b2; --line: #262c38;
  --accent: #a58cff; --silver: #b4c2d4; --gold: #e3b63a; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font: 15px/1.6 var(--body); }}
.wrap {{ max-width: 1240px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 64px; }}
.hero {{ display: grid; gap: 8px; padding-block: 8px 20px; }}
.hero h1 {{ font: 400 clamp(32px, 6vw, 56px)/1.05 var(--display); margin: 0; letter-spacing: 0.01em; text-wrap: balance; }}
.hero h1 em {{ font-style: normal; background: var(--prism); -webkit-background-clip: text; background-clip: text; color: transparent; }}
.hero p {{ margin: 0; color: var(--muted); max-width: 62ch; }}
.counts {{ display: flex; flex-wrap: wrap; gap: 8px 18px; font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--muted); }}
.counts b {{ color: var(--ink); font-weight: 500; }}
nav.bar {{ position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--bg);
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; padding-block: 10px; border-bottom: 1px solid var(--line); }}
nav.bar a {{ color: var(--ink); text-decoration: none; font-weight: 600; }}
nav.bar a:hover, nav.bar a:focus-visible {{ color: var(--accent); }}
nav.bar .sub {{ display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 13px; }}
nav.bar .sub a {{ color: var(--muted); font-weight: 400; }}
#q {{ margin-left: auto; min-width: 0; width: min(260px, 100%); padding: 7px 10px; border: 1px solid var(--line);
  border-radius: 6px; background: var(--surface); color: var(--ink); font: inherit; }}
#q:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
h2 {{ font: 400 30px/1.2 var(--display); margin: 40px 0 6px; }}
h2 + .lede, .lede + .lede {{ margin: 0 0 8px; color: var(--muted); max-width: 70ch; }}
h3 {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; font-size: 17px; margin: 26px 0 12px; }}
h3 span {{ font-family: var(--mono); font-size: 13px; color: var(--muted); font-weight: 500; }}
h3 small {{ color: var(--muted); font-weight: 400; font-size: 13px; }}
.tier-h::before {{ content: ""; width: 12px; height: 12px; border-radius: 2px; align-self: center; }}
.tier-h.t-silver::before {{ background: var(--silver); }}
.tier-h.t-gold::before {{ background: var(--gold); }}
.tier-h.t-prism::before {{ background: var(--prism); }}
.grid {{ display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); }}
.grid.wide {{ grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }}
.card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; min-width: 0; }}
.card header {{ display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }}
.card h4 {{ margin: 0; font-size: 16px; line-height: 1.35; }}
.card p {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; }}
.aug {{ border-top: 3px solid var(--silver); }}
.aug.t-gold {{ border-top-color: var(--gold); }}
.aug.t-prism {{ border-top: 3px solid transparent; border-image: var(--prism) 1; border-image-slice: 1 0 0 0; }}
.stack {{ font: 500 12px var(--mono); color: var(--muted); white-space: nowrap; }}
.wep, .arm {{ display: grid; grid-template-columns: 96px 1fr; gap: 12px; align-items: start; }}
.pic {{ width: 96px; height: 96px; border-radius: 6px; background: #1a1d26; display: grid; place-items: center; overflow: hidden; }}
.pic img {{ width: 96px; height: 96px; object-fit: contain; image-rendering: pixelated; }}
.noimg {{ width: 40px; height: 40px; border: 2px dashed #3a4050; border-radius: 4px; }}
.body {{ min-width: 0; }}
.meta {{ color: var(--muted); font-size: 13px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }}
.el {{ display: inline-flex; align-items: center; gap: 4px; }}
.el i {{ display: inline-block; width: 9px; height: 9px; border-radius: 2px; }}
.aura {{ font-size: 11px; font-weight: 600; letter-spacing: 0.04em; padding: 1px 6px; border-radius: 4px; color: #fff;
  background: var(--prism); white-space: nowrap; }}
dl {{ display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 6px 0 0; }}
dl div {{ display: flex; gap: 6px; align-items: baseline; }}
dt {{ color: var(--muted); font-size: 12px; }}
dd {{ margin: 0; font: 500 15px var(--mono); font-variant-numeric: tabular-nums; }}
ul.skills, ul.bonus {{ list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 6px; font-size: 14px; }}
ul.skills b, ul.bonus b {{ color: var(--accent); font-size: 12px; margin-right: 4px; }}
ul.skills small {{ font: 500 12px var(--mono); color: var(--muted); }}
ul.skills span {{ display: block; color: var(--muted); font-size: 13px; }}
.passive {{ border-left: 2px solid var(--line); padding-left: 8px; }}
.card p.noskill {{ margin-top: 8px; font-size: 13px; }}
.obtain {{ font-size: 12.5px !important; margin-top: 8px !important; }}
.card p.gear, .card p.mine {{ margin-top: 6px; font-size: 13px; }}
.card p.mine {{ border-left: 2px solid var(--line); padding-left: 8px; }}
tr:first-child th {{ font-size: 12px; }}
table {{ border-collapse: collapse; margin-top: 6px; font-size: 13.5px; }}
th {{ text-align: left; color: var(--muted); font-weight: 400; padding: 1px 12px 1px 0; white-space: nowrap; }}
td {{ font-family: var(--mono); font-variant-numeric: tabular-nums; padding-right: 14px; }}
.empty {{ color: var(--muted); }}
@media (max-width: 480px) {{ .wep, .arm {{ grid-template-columns: 72px 1fr; }} .pic, .pic img {{ width: 72px; height: 72px; }} #q {{ margin-left: 0; width: 100%; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
html {{ scroll-behavior: smooth; scroll-padding-top: 64px; }}
</style>
<div class="wrap">
  <div class="hero">
    <h1>증강 스카이블럭 <em>도감</em></h1>
    <p>제단에서 고르는 증강, 섬과 균열과 보스에게서 얻는 무기, 세트 효과가 있는 갑옷을 한곳에 모았습니다. 수치는 서버 기본 설정 기준입니다.</p>
    <div class="counts"><span>증강 <b>{n_aug}</b> (실버 {silver} · 골드 {gold} · 프리즘 {prism})</span><span>무기 <b>{n_wep}</b></span><span>곡괭이 <b>{n_pick}</b></span><span>갑옷 <b>{n_arm}</b>세트</span></div>
  </div>
  <nav class="bar" aria-label="목차">
    <a href="#augments">증강</a><a href="#weapons">무기</a><a href="#armor">갑옷</a>
    <span class="sub">{pools}</span>
    <input id="q" type="search" placeholder="이름으로 찾기" aria-label="이름으로 찾기">
  </nav>
  <h2 id="augments">증강</h2>
  <p class="lede">맵 곳곳의 제단을 우클릭하면 같은 등급 증강 3개 중 하나를 고릅니다. 제단은 한 번 쓰면 힘을 잃습니다. 증강권은 손에 들고 우클릭하면 어디서든 씁니다.</p>
  {aug}
  <h2 id="weapons">무기</h2>
  <p class="lede">무기에 등급은 없고 얻는 곳으로만 나뉩니다. 조합 재료는 섬마다 나는 것이라 무기마다 찾아갈 섬이 다르고, 다른 무기를 넣는 강화 조합은 같은 종류의 무기만 받습니다. 섬 초반 무기는 대부분 스킬이 없습니다. 스킬은 우클릭과 웅크리기+우클릭으로 쓰고, 프리즘 무기는 웅크리기+좌클릭으로 궁극기까지 씁니다. 활은 그냥 당기면 화살이고, 웅크리기+당겨 쏘기와 웅크리기+좌클릭으로 스킬을 씁니다. 보스·프리즘 활만 화살이 줄지 않고, 다른 활은 화살을 쓰며 무한을 붙일 수 있습니다. 보스와 프리즘 무기에는 움직이는 아우라가 있습니다.</p>
  <p class="lede">곡괭이는 무기와 따로, 앞 곡괭이를 넣어 한 단계씩 강화합니다. 채굴 등급이 낮으면 캐도 블록이 나오지 않습니다. 무기·곡괭이·갑옷은 쓰면 닳고 스킬을 써도 조금 닳습니다. 모루에 그 장비의 수리 재료나 같은 장비를 올려 고치고, 숫돌은 같은 장비끼리만 합칩니다.</p>
  {wep}
  <h2 id="armor">갑옷</h2>
  <p class="lede">같은 세트를 2개, 4개 입으면 세트 효과가 붙습니다. 보스 세트는 보스가 떨구고, 프리즘 세트는 보스 갑옷과 프리즘 결정으로 만듭니다.</p>
  <div class="grid wide">{arm}</div>
  <p class="empty" id="none" hidden>찾는 이름이 없습니다.</p>
</div>
<script>
(function () {{
  var q = document.getElementById('q');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var none = document.getElementById('none');
  q.addEventListener('input', function () {{
    var t = q.value.trim();
    var shown = 0;
    cards.forEach(function (c) {{
      var ok = !t || (c.getAttribute('data-q') || '').indexOf(t) >= 0;
      c.hidden = !ok;
      if (ok) shown++;
    }});
    document.querySelectorAll('.group').forEach(function (g) {{
      g.hidden = !g.querySelector('.card:not([hidden])');
    }});
    none.hidden = shown > 0;
  }});
}})();
</script>
"""

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "catalog.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build())
    print(out, os.path.getsize(out) // 1024, "KB")
