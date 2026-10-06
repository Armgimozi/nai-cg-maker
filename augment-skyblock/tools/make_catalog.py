#!/usr/bin/env python3
"""
증강 · 무기 · 갑옷 도감 페이지(HTML 한 장)를 만든다.
  python3 tools/make_catalog.py [출력.html]
플러그인 YAML(augments, weapons, skills, armor, items)과 pack/gen_pack.py 가 만든 그림(dist/catalog/)을 읽는다.
그림은 data: URI 로 페이지 안에 넣는다.
"""
import base64
import html
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
POOLS = [("basic", "섬 초반", "섬 재료로 작업대에서 만든다"), ("island", "섬 재료", "섬 재료로 작업대에서 만든다"),
         ("frost", "서리 균열", "서리 정수로 만든다"), ("flame", "화염 균열", "화염 정수로 만든다"),
         ("void", "공허 균열", "공허 정수로 만든다"), ("boss", "보스", "보스가 떨구거나 프리즘 결정으로 만든다"),
         ("prism", "프리즘", "프리즘 결정으로 만든다")]
TYPES = {"sword": "검", "greatsword": "대검", "dagger": "단검", "katana": "카타나", "axe": "도끼", "hammer": "망치",
         "spear": "창", "scythe": "낫", "staff": "지팡이", "wand": "마법봉", "bow": "활"}
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
    "VINE": "덩굴",
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
    if not recipe:
        return ""
    counts = {}
    for row in recipe["shape"]:
        for ch in row:
            if ch != " ":
                counts[ch] = counts.get(ch, 0) + 1
    parts = []
    for ch, n in counts.items():
        spec = recipe["ingredients"].get(ch)
        if spec is None:
            continue
        parts.append(f"{ingredient_name(spec, items, weapons, armor)} ×{n}")
    return ", ".join(parts)


def element_chip(el):
    name, col = ELEMENT.get(el, (el, "#999"))
    style = "background: var(--prism)" if col == "prism" else f"background:{col}"
    return f'<span class="el"><i style="{style}"></i>{esc(name)}</span>'


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

    # ---- 무기
    wep_html = []
    total_w = 0
    for pool, pname, psrc in POOLS:
        cards = []
        for wid, w in weapons.items():
            if not isinstance(w, dict) or w.get("pool") != pool:
                continue
            total_w += 1
            uri = img_uri(os.path.join(CAT, "weapons", wid + ".png"))
            pic = f'<img src="{uri}" alt="" loading="lazy">' if uri else '<div class="noimg"></div>'
            is_bow = w.get("type") == "bow"
            stat = (f'<dl><div><dt>화살 피해</dt><dd>{w["damage"]:g}</dd></div></dl>' if is_bow else
                    f'<dl><div><dt>공격력</dt><dd>{w["damage"]:g}</dd></div><div><dt>공격 속도</dt><dd>{w.get("speed", 1.6):g}</dd></div></dl>')
            sk = []
            for key, label in (BOW_SKILL_INPUTS if is_bow else SKILL_INPUTS):
                s = skills.get(w.get(key) or "")
                if s:
                    sk.append(f'<li><b>{label}</b> {esc(s["name"])} <small>{s.get("cooldown", 0):g}초</small>'
                              f'<span>{esc(" ".join(s.get("description", [])))}</span></li>')
            passive = (w.get("passive") or {}).get("description")
            pas = f'<p class="passive">{esc(passive)}</p>' if passive else ""
            # 초반 무기 대부분은 스킬이 없다. 빈 칸 대신 한 줄로 알려 준다
            skills_html = (f'<ul class="skills">{"".join(sk)}</ul>' if sk else
                           f'<p class="noskill">스킬 없음 · {"기본 공격과 패시브" if passive else "기본 공격"}</p>')
            src = w.get("source")
            rec = recipe_text(w.get("recipe"), items, weapons, armor)
            obtain = esc(src) if src else (f"조합: {esc(rec)}" if rec else esc(psrc))
            aura = '<span class="aura">아우라</span>' if pool in ("boss", "prism") else ""
            cards.append(
                f'<article class="card wep" data-q="{esc(w["name"])} {TYPES.get(w["type"], "")} {ELEMENT.get(w.get("element"), ("",))[0]}">'
                f'<div class="pic">{pic}</div><div class="body"><header><h4>{esc(w["name"])}</h4>{aura}</header>'
                f'<div class="meta">{TYPES.get(w["type"], w["type"])} · {element_chip(w.get("element"))}</div>{stat}'
                f'{skills_html}{pas}<p class="obtain">{obtain}</p></div></article>')
        if cards:
            wep_html.append(f'<section class="group" id="wep-{pool}"><h3 class="pool-h">{pname} <span>{len(cards)}</span>'
                            f'<small>{psrc}</small></h3><div class="grid wide">{"".join(cards)}</div></section>')

    # ---- 갑옷
    arm_html = []
    for sid, a in armor.items():
        uri = img_uri(os.path.join(CAT, "armor", sid + ".png"))
        pic = f'<img src="{uri}" alt="" loading="lazy">' if uri else '<div class="noimg"></div>'
        rows = []
        for slot, sname in SLOTS:
            v = a["pieces"][slot]
            extra = f' · 강도 {v[1]:g}' if len(v) > 1 and v[1] else ""
            rows.append(f'<tr><th>{sname}</th><td>방어 {v[0]:g}{extra}</td></tr>')
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
            f'<header><h4>{esc(a["name"])} 세트</h4></header><table>{"".join(rows)}</table>'
            f'<ul class="bonus">{bonus}</ul><p class="obtain">{how}</p></div></article>')

    n_aug = sum(tier_counts.values())
    return PAGE.format(
        n_aug=n_aug, n_wep=total_w, n_arm=len(armor),
        silver=tier_counts.get("SILVER", 0), gold=tier_counts.get("GOLD", 0), prism=tier_counts.get("PRISM", 0),
        aug="".join(aug_html), wep="".join(wep_html), arm="".join(arm_html),
        pools="".join(f'<a href="#wep-{p}">{n}</a>' for p, n, _ in POOLS))


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
h2 + .lede {{ margin: 0 0 8px; color: var(--muted); max-width: 70ch; }}
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
table {{ border-collapse: collapse; margin-top: 6px; font-size: 13.5px; }}
th {{ text-align: left; color: var(--muted); font-weight: 400; padding: 1px 12px 1px 0; }}
td {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
.empty {{ color: var(--muted); }}
@media (max-width: 480px) {{ .wep, .arm {{ grid-template-columns: 72px 1fr; }} .pic, .pic img {{ width: 72px; height: 72px; }} #q {{ margin-left: 0; width: 100%; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
html {{ scroll-behavior: smooth; scroll-padding-top: 64px; }}
</style>
<div class="wrap">
  <div class="hero">
    <h1>증강 스카이블럭 <em>도감</em></h1>
    <p>제단에서 고르는 증강, 섬과 균열과 보스에게서 얻는 무기, 세트 효과가 있는 갑옷을 한곳에 모았습니다. 수치는 서버 기본 설정 기준입니다.</p>
    <div class="counts"><span>증강 <b>{n_aug}</b> (실버 {silver} · 골드 {gold} · 프리즘 {prism})</span><span>무기 <b>{n_wep}</b></span><span>갑옷 <b>{n_arm}</b>세트</span></div>
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
  <p class="lede">무기에 등급은 없고 얻는 곳으로만 나뉩니다. 섬 초반 무기는 대부분 스킬이 없습니다. 스킬은 우클릭과 웅크리기+우클릭으로 쓰고, 프리즘 무기는 웅크리기+좌클릭으로 궁극기까지 씁니다. 활은 그냥 당기면 화살이고, 웅크리기+당겨 쏘기와 웅크리기+좌클릭으로 스킬을 씁니다. 보스와 프리즘 무기에는 움직이는 아우라가 있습니다.</p>
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
