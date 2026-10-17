#!/usr/bin/env python3
"""플러그인 ↔ 리소스팩 에셋 id 대조 (ARCHITECTURE §2 계약).

content/*.yml + Java 소스의 하드코딩 id 가 resourcepack/dist/labyrinth-pack.zip 안에 실제로 있는지 본다.
  items      : assets/labyrinth/items/<id>.json (+ 활 당김 단계 <id>_pulling_0..2 — 활 = model.shape 가 팩의 활 모양
               (resourcepack/src/voxel/weapons.py BOWS). 원거리(attack.style ranged)인데 활 모양이 아니면 오류)
               + 아이템 정의가 부르는 모델 전부
  armor sets : assets/labyrinth/equipment/<set>.json (투구 제외 — 투구는 3D 아이템 모델)
  mob parts  : assets/labyrinth/items/mob/<id>/<part>.json (mobs.yml + bosses.yml)
  npc skins  : assets/labyrinth/textures/entity/npc/<skin>.png
  fx         : fx.yml models + aura ring/secondary 모델 + params.fx 참조 + Java 리터럴 → assets/labyrinth/items/fx/<name>.json
  glyphs     : glyphs.yml 의 모든 글리프 문자가 font/ui.json 에 있는지, 메뉴 배경 줄 수가 menus.<id>.rows 와 같은지
  mine 0.3.6 : 계약 tools/data/036 (visual·materials·mine.json) — 광석·주괴·보석·곡괭이·새 몬스터 재료 아이템
               (+ resourcepack/generate.py MINE_EXTRA_ICONS 드롭 명세 재료), 0.3.6.1 보석 광석 블록 6개 (mine.json gems.*.block 의
               blockstates → visual.json 모델 → 16×16 그림, 결정 모델 0), 옛 재료 id 별칭 (두 판), 광부·제련공 스킨, 메뉴 배경 3개,
               보석 블록 밖 블록 덮어쓰기 0개
  평면 아이콘 : item/generated 아이템 그림이 모두 16×16 손그림 (0.3.6.2 resourcepack/src/pixel_icons, 반투명 없음).
               옛 32×32 로 떨어진 그림은 오류, 계약 visual.json size 와 다른 크기는 경고
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
PACK_SRC = ROOT / "resourcepack/src/voxel/weapons.py"
PACK_GEN = ROOT / "resourcepack/generate.py"
CONTRACT036 = ROOT / "tools/data/036"


def bow_shapes():
    """팩의 활 모양 목록 (voxel/weapons.py 의 BOWS = (...) 한 줄 — 팩 모듈을 import 하지 않고 읽는다)."""
    m = re.search(r"^BOWS = \(([^)]*)\)", PACK_SRC.read_text(encoding="utf-8"), re.M)
    return set(re.findall(r"'([a-z_]+)'", m.group(1))) if m else set()


def mine_extra_ids():
    """generate.py MINE_EXTRA_ICONS 의 id (드롭 명세 새 재료 — items.yml 에 들어가기 전에도 팩이 그린다)."""
    m = re.search(r"^MINE_EXTRA_ICONS = \{(.*?)^\}", PACK_GEN.read_text(encoding="utf-8"), re.M | re.S)
    return re.findall(r"^\s+'([a-z_]+)':", m.group(1), re.M) if m else []


def contract036():
    out = {}
    for name in ("visual", "materials", "mine"):
        p = CONTRACT036 / f"{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def model_refs(node, out):
    """아이템 정의(items/<id>.json) 안의 모델 참조 수집."""
    if isinstance(node, dict):
        if node.get("type") in ("minecraft:model", "model") and isinstance(node.get("model"), str):
            out.add(node["model"])
        for v in node.values():
            model_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            model_refs(v, out)


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
    zf = zipfile.ZipFile(pack)
    names = set(zf.namelist())
    A = "assets/labyrinth/"
    bows = bow_shapes()
    errors, checked = ([] if bows else ["resourcepack/src/voxel/weapons.py: BOWS 를 읽지 못함"]), 0

    def need(path, why):
        nonlocal checked
        checked += 1
        if A + path not in names:
            errors.append(f"{why}: {A + path} 없음")

    items = load("items.yml").get("items", {})
    for iid, it in items.items():
        need(f"items/{iid}.json", f"아이템 {iid}")
        shape = (it.get("model") or {}).get("shape")
        style = (it.get("attack") or {}).get("style")
        if shape in bows:  # 활 (0.3.5: 무기 종류 대신 모델 모양)
            for i in range(3):  # 당김 단계는 items/<id>.json 의 condition 이 부르는 모델
                need(f"models/item/{iid}_pulling_{i}.json", f"활 {iid}")
        elif style == "ranged":
            errors.append(f"아이템 {iid}: 원거리 무기인데 model.shape {shape!r} 가 팩의 활 모양이 아님 (당김 모델 없음)")
        if A + f"items/{iid}.json" in names:
            refs = set()
            model_refs(json.loads(zf.read(A + f"items/{iid}.json")), refs)
            for ref in sorted(refs):
                ns, _, path = ref.partition(":")
                if ns == "labyrinth":
                    need(f"models/{path}.json", f"아이템 {iid} 모델 {ref}")
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
        font = json.loads(zf.read(font_path))
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

    # 0.3.6 광산 (계약 tools/data/036)
    c = contract036()
    vis, mat, mine = c.get("visual") or {}, c.get("materials") or {}, c.get("mine") or {}
    renamed = {"cinder_hide": "cinder_scale"}          # 계약 §0-4 (드롭 명세가 재료 id 를 정함)
    mine_ids = [renamed.get(i, i) for i in (vis.get("icons") or {})] + mine_extra_ids() + list(vis.get("pickaxes") or {})
    for iid in dict.fromkeys(mine_ids):
        need(f"items/{iid}.json", f"광산 아이템 {iid}")
        if A + f"items/{iid}.json" in names:
            refs = set()
            model_refs(json.loads(zf.read(A + f"items/{iid}.json")), refs)
            for ref in sorted(refs):
                ns, _, path = ref.partition(":")
                if ns == "labyrinth":
                    need(f"models/{path}.json", f"광산 아이템 {iid} 모델 {ref}")
    # 0.3.6.1 보석 광석 블록 (결정 모델 없음): mine.json 보석 블록마다 바닐라 blockstates 1 → 계약 visual.json 의 labyrinth 모델 → 16×16 그림
    allowed = set()
    vgems = ((vis.get("blocks") or {}).get("gems")) or {}
    for gid, gd in (mine.get("gems") or {}).items():
        checked += 1
        block = (gd.get("block") or "").split(":", 1)[-1]
        vg = vgems.get(gid) or {}
        ref = vg.get("model") or ""
        tex = vg.get("texture") or ref
        if vg.get("block") != gd.get("block") or ":" not in ref:
            errors.append(f"보석 블록 {gid}: mine.json 블록 {gd.get('block')} ≠ visual.json {vg.get('block')} (또는 모델 없음)")
            continue
        st = f"assets/minecraft/blockstates/{block}.json"
        mns, _, mpath = ref.partition(":")
        tns, _, tpath = tex.partition(":")
        mo, tx = f"assets/{mns}/models/{mpath}.json", f"assets/{tns}/textures/{tpath}.png"
        allowed |= {st, mo, tx}
        for path in (st, mo, tx):
            if path not in names:
                errors.append(f"보석 블록 {gid}: 팩에 없음 — {path}")
        if st in names:
            d = json.loads(zf.read(st))
            refs = {v["model"] for vs in (d.get("variants") or {}).values() for v in (vs if isinstance(vs, list) else [vs])}
            if refs != {ref}:
                errors.append(f"보석 블록 {gid}: {st} 가 {ref} 만 가리키지 않음 ({sorted(refs)})")
        if "node_model" in gd:
            errors.append(f"보석 {gid}: mine.json 에 0.3.6 결정 모델(node_model)이 남음")
    nodes = sorted(n for n in names if re.match(r"assets/[^/]+/(items|models/item|textures/item)/mine/node_", n))
    checked += 1
    if nodes:
        errors.append(f"0.3.6 보석 결정 모델이 팩에 남음 (0.3.6.1: 네모난 광석 블록만): {nodes[:3]}")
    retired = set(mat.get("retired") or {}) | set(((mat.get("conversion") or {}).get("map")) or {})
    for old in sorted(retired - set(items)):
        need(f"items/{old}.json", f"옛 재료 별칭 {old} (두 판)")
    for role, d in (vis.get("npcs") or {}).items():
        if isinstance(d, dict) and d.get("skin"):
            need(f"textures/entity/npc/{d['skin']}.png", f"광산 NPC {role} 스킨")
    gmenus = (g.get("menus") or {})
    for mid, md in (vis.get("menus") or {}).items():
        gid = (md or {}).get("glyph") or ""
        if gid.startswith("gui_") and " " not in gid:
            checked += 1
            if (gmenus.get(mid) or {}).get("glyph") != gid:
                errors.append(f"메뉴 {mid}: glyphs.yml menus.{mid}.glyph 가 계약의 {gid} 가 아님")
    blocks = sorted(n for n in names if re.match(r"assets/[^/]+/(blockstates/|models/block/|textures/block/)", n) and n not in allowed)
    checked += 1
    if blocks:
        errors.append(f"보석 블록 6개 밖 블록 덮어쓰기 {len(blocks)}개 (계약 §0-8): " + ", ".join(blocks[:5]))

    # 0.3.6.2 평면 아이콘 (item/generated): 16×16 손그림 (resourcepack/src/pixel_icons). 크기가 16·32 가 아니거나 반투명이 섞인
    # 16px 는 오류, 옛 32×32 로 떨어진 것도 오류 (통합 뒤 83개 모두 16px). 계약 visual.json icons.*.size 와 다르면 경고.
    from io import BytesIO
    from PIL import Image
    sizes = {}
    for iid in sorted(set(items) | set(mine_ids)):
        p = A + f"models/item/{iid}.json"
        if p not in names:
            continue
        m = json.loads(zf.read(p))
        if m.get("parent") != "minecraft:item/generated":
            continue
        checked += 1
        ref = (m.get("textures") or {}).get("layer0") or ""
        ns, _, tp = ref.partition(":")
        tpath = f"assets/{ns}/textures/{tp}.png"
        if tpath not in names:
            errors.append(f"평면 아이콘 {iid}: {tpath} 없음")
            continue
        im = Image.open(BytesIO(zf.read(tpath))).convert("RGBA")
        w, h = im.size
        sizes[iid] = w
        if w not in (16, 32) or h % w:
            errors.append(f"평면 아이콘 {iid}: 크기 {w}×{h} (16×16 손그림 또는 옛 32×32)")
        elif w == 16 and ({a for *_, a in im.getdata()} - {0, 255}):
            errors.append(f"평면 아이콘 {iid}: 16px 그림에 반투명 픽셀 (pixel_icons 규칙 R1)")
        want = ((vis.get("icons") or {}).get(iid) or {}).get("size")
        if want and w != want:
            warns.append(f"평면 아이콘 {iid}: {w}px — 계약 visual.json 은 {want}px (옛 그림, pixel_icons 로 옮길 것)")
    n16 = sum(1 for w in sizes.values() if w == 16)
    if sizes and n16 < len(sizes):
        # 0.3.6.2 통합부터 평면 아이콘은 모두 16px (pixel_icons.REQUIRE_ALL_16) — 옛 32px 로 떨어진 것은 오류
        old32 = sorted(i for i, w in sizes.items() if w != 16)
        errors.append(f"평면 아이콘 옛 32px {len(old32)}개 (16px {n16}개): " + ", ".join(old32[:8]) +
                      " — resourcepack/src/pixel_icons 에 그림을 등록할 것")

    print(f"검사 {checked}건 · 오류 {len(errors)}건 ({pack.name})")
    for e in errors:
        print("  -", e)
    for w in sorted(set(warns)):
        print("  (경고)", w)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
