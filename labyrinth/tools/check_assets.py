#!/usr/bin/env python3
"""플러그인 ↔ 리소스팩 에셋 id 대조 (ARCHITECTURE §2 계약).

content/*.yml + Java 소스의 하드코딩 id 가 resourcepack/dist/labyrinth-pack.zip 안에 실제로 있는지 본다.
  items      : assets/labyrinth/items/<id>.json (+ 활 당김 단계 <id>_pulling_0..2)
  armor sets : assets/labyrinth/equipment/<set>.json (투구 제외 — 투구는 3D 아이템 모델)
  mob parts  : assets/labyrinth/items/mob/<id>/<part>.json (mobs.yml + bosses.yml)
  npc skins  : assets/labyrinth/textures/entity/npc/<skin>.png
  fx         : fx.yml models + aura ring/secondary 모델 + params.fx 참조 + Java 리터럴 → assets/labyrinth/items/fx/<name>.json
  glyphs     : glyphs.yml 의 모든 글리프 문자가 font/ui.json 에 있는지, 메뉴 배경 줄 수가 menus.<id>.rows 와 같은지
사용: python3 tools/check_assets.py [pack.zip]   (종료 코드 0 = 일치)
"""
import json
import re
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "plugin/src/main/resources/content"
JAVA = ROOT / "plugin/src/main/java"


def load(name):
    with open(CONTENT / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def walk_fx_refs(node, out):
    """params 안의 fx/ring_model/secondary_model/model 참조 수집."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("fx", "fx_model", "ring_model", "secondary_model", "projectile_fx", "impact_fx", "trail_fx") and isinstance(v, str):
                out.add(v)
            else:
                walk_fx_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_fx_refs(v, out)


def main():
    pack = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "resourcepack/dist/labyrinth-pack.zip"
    if not pack.exists():
        print(f"팩이 없습니다: {pack} (resourcepack/generate.py 먼저)")
        return 2
    names = set(zipfile.ZipFile(pack).namelist())
    A = "assets/labyrinth/"
    errors, checked = [], 0

    def need(path, why):
        nonlocal checked
        checked += 1
        if A + path not in names:
            errors.append(f"{why}: {A + path} 없음")

    items = load("items.yml").get("items", {})
    for iid, it in items.items():
        need(f"items/{iid}.json", f"아이템 {iid}")
        if (it.get("weapon_type") or it.get("type")) == "bow":
            for i in range(3):  # 당김 단계는 items/<id>.json 의 condition 이 부르는 모델
                need(f"models/item/{iid}_pulling_{i}.json", f"활 {iid}")
        aset = it.get("armor_set")
        if aset and it.get("armor_slot") not in ("head", "offhand", None):
            need(f"equipment/{aset}.json", f"방어구 세트 {aset} ({iid})")

    for fname, key in (("mobs.yml", "mobs"), ("bosses.yml", "bosses")):
        for mid, m in (load(fname).get(key) or {}).items():
            for part in ((m.get("model") or {}).get("parts") or []):
                need(f"items/mob/{mid}/{part['name']}.json", f"{key} {mid} 파트")

    for nid, n in (load("npcs.yml").get("npcs") or {}).items():
        skin = n.get("skin")
        if skin:
            need(f"textures/entity/npc/{skin}.png", f"NPC {nid} 스킨")

    fx = load("fx.yml")
    fx_models = set((fx.get("models") or {}).keys())
    refs = set()
    for aid, a in (fx.get("auras") or {}).items():
        walk_fx_refs(a, refs)
    for fname in ("items.yml", "bosses.yml", "mobs.yml", "classes.yml"):
        walk_fx_refs(load(fname), refs)
    for name in sorted(fx_models | refs):
        need(f"items/fx/{name}.json", f"fx {name}" + ("" if name in fx_models else " (fx.yml 에 없음)"))

    # Java: 스킬 fx 기본값 c.fx("파라미터", "기본 fx") / SkillFx·BossFx 의 fx 이름 리터럴 → 오류.
    #       그 밖의 fx 모양 리터럴(telegraph_*, *_ring/_slash/...)은 스킬·패턴 id 일 수도 있어 경고만.
    lit_re = re.compile(r'"([a-z][a-z0-9_]{2,})"')
    fx_like = re.compile(r"^(telegraph_[a-z_]+|[a-z0-9]+_(ring|slash|orb|burst|beam|arrow))$")
    default_re = re.compile(r'\bfx\(\s*"[a-z0-9_]+"\s*,\s*"([a-z0-9_]+)"\s*\)')
    direct_re = re.compile(r'(?:Fx|fx|Telegraph|telegraph)\w*\.(?!startsWith|equals|sub\b|maps\b|get)\w+\(\s*"([a-z0-9_]+)"')
    warns = []
    seen = set()
    for jf in JAVA.rglob("*.java"):
        src = jf.read_text(encoding="utf-8")
        strict = set(default_re.findall(src)) | set(direct_re.findall(src))
        for s in sorted(strict):
            if (s, jf.name) in seen:
                continue
            seen.add((s, jf.name))
            checked += 1
            if A + f"items/fx/{s}.json" not in names:
                errors.append(f"Java fx '{s}' ({jf.name}): items/fx/{s}.json 없음")
        for m in lit_re.finditer(src):
            s = m.group(1)
            if fx_like.match(s) and s not in items and s not in strict and A + f"items/fx/{s}.json" not in names:
                warns.append(f"Java 리터럴 '{s}' ({jf.name}) — fx 모델이면 fx.yml 에 추가 필요 (스킬/패턴 id 면 무시)")

    # 글리프
    g = load("glyphs.yml")
    font_path = A + "font/ui.json"
    if font_path not in names:
        errors.append("font/ui.json 없음")
    else:
        font = json.loads(zipfile.ZipFile(pack).read(font_path))
        chars = set()
        for p in font.get("providers", []):
            for row in p.get("chars", []):
                chars.update(row)
            for k in (p.get("advances") or {}):
                chars.add(k)
        for gid, gd in (g.get("glyphs") or {}).items():
            checked += 1
            if gd["char"] not in chars:
                errors.append(f"글리프 {gid}: 문자 U+{ord(gd['char']):04X} 가 font/ui.json 에 없음")
        for mid, md in (g.get("menus") or {}).items():
            gd = (g.get("glyphs") or {}).get(md.get("glyph"))
            checked += 1
            if gd is None:
                errors.append(f"메뉴 {mid}: 배경 글리프 {md.get('glyph')} 없음")
            elif round((gd["height"] - 114) / 18) != md.get("rows"):
                errors.append(f"메뉴 {mid}: 배경 높이 {gd['height']} 가 rows {md.get('rows')} 와 다름")

    print(f"검사 {checked}건 · 오류 {len(errors)}건 ({pack.name})")
    for e in errors:
        print("  -", e)
    for w in sorted(set(warns)):
        print("  (경고)", w)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
