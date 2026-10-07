"""
무기 모형 A 몫 (SPEC.md 4절): 칼 다섯 (blades_a), 방패 셋 (shields_a), 활 (bow_a), 가마지기의 쇠단지 (kiln_pot).

  build(out)                         팩 폴더 out 에 A 의 열 개를 쓴다 (gen_pack 이 weapons.build 로 부른다)
  python3 pack/weapons/set_a.py [id ...]
                                     시험 폴더에 짓고 미리보기를 dist/screenshots/weapons/<id>_{gui,side,fp,tp}.png 로 쓴다
                                     (id 를 주지 않으면 열 개 모두 + pack/preview/weapons_a.png, weapons_lineup.png)

아이템마다 (SPEC 1.9)
  souls:item/<id>      16×16 손으로 찍은 그림 (pack/art/weapon_icons_a.txt): 인벤토리·땅·액자·선반
  souls:item/<id>_3d   wkit 복셀 모형 (손에 든 것, 몹·대역·보스 인형)
  souls:item/<id>_guard / _block   막기 자세 (부모 _3d, display 만)
  활: _3d_pulling_0..2
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
ROOT = os.path.dirname(PACK)
if PACK not in sys.path:
    sys.path.insert(0, PACK)

from weapons import _common as C  # noqa: E402

ICONS = os.path.join(PACK, "art", "weapon_icons_a.txt")
SHOTS = os.path.join(ROOT, "dist", "screenshots", "weapons")
SCRATCH = os.environ.get("WEAPONS_SCRATCH") or os.path.join(__import__("tempfile").gettempdir(), "souls_weapons_a")


def registry():
    """id → 정의 (dict): make() → SoulsWeapon (또는 활은 [평소, 당김 셋]), kind, use, displays."""
    from weapons import blades_a
    reg = {}
    for mod in (blades_a,):
        reg.update(mod.ITEMS)
    try:
        from weapons import shields_a
        reg.update(shields_a.ITEMS)
    except ImportError:
        pass
    try:
        from weapons import bow_a
        reg.update(bow_a.ITEMS)
    except ImportError:
        pass
    try:
        from weapons import kiln_pot
        reg.update(kiln_pot.ITEMS)
    except ImportError:
        pass
    return reg


def _spec(entry):
    """옛 꼴 (make, kind) 도 받는다 → 무기 기본값."""
    if isinstance(entry, tuple):
        make, kind = entry
        return {"make": make, "kind": kind, "use": "guard",
                "display": C.hand_display(kind), "use_display": C.guard_display(kind)}
    return entry


def icons(strict=True):
    found = C.load_icons(ICONS) if os.path.exists(ICONS) else {}
    return {k: C.icon_image(rows, ink) for k, (rows, ink) in found.items()}


def build_one(out, wid, spec, icon):
    made = spec["make"]()
    if spec["use"] == "bow":
        w, pulls = made[0], made[1:]
    else:
        w, pulls = made, None
    res = C.write_item(out, wid, w, spec["display"], icon, spec["kind"], use=spec["use"],
                       use_display=spec.get("use_display"), swap=spec.get("swap"), bow_states=pulls)
    res["weapon"] = w
    return res


def build(out, strict=True):
    """팩에 A 의 열 개를 쓴다. 16px 그림이 빠졌으면 strict 에서 멈춘다."""
    ic = icons()
    reg = registry()
    out_models = {}
    for wid, entry in reg.items():
        spec = _spec(entry)
        if wid not in ic:
            if strict:
                raise KeyError(f"{wid}: 16px 그림이 {ICONS} 에 없다")
            from PIL import Image
            ic[wid] = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        out_models[wid] = build_one(out, wid, spec, ic[wid])
    return out_models


# ─────────────────────────── 미리보기 ───────────────────────────

def previews(wid, spec, res, icon):
    from weapons import _views as V
    os.makedirs(SHOTS, exist_ok=True)
    model = res["3d"]
    use_model = model  # _guard/_block 는 같은 모형에 손 자세만 다르다
    disp = spec["display"]
    udisp = spec.get("use_display") or {}
    kind = spec["kind"]
    files = []
    # 1. 16px 그림
    p = os.path.join(SHOTS, f"{wid}_gui.png")
    V.gui(icon).save(p)
    files.append(p)
    # 2. 모형만
    p = os.path.join(SHOTS, f"{wid}_side.png")
    V.strip(V.side(model), ["front (+Z)", "3/4", "edge (from +X)"]).save(p)
    files.append(p)
    # 3. 1인칭
    shots, labels = [], []
    if spec["use"] == "bow":
        shots.append(V.first_person([(model, disp["firstperson_righthand"], "r", None)]))
        labels.append("first person, idle")
        shots.append(V.first_person([(res["pull"][2], disp["firstperson_righthand"], "r", "bow")]))
        labels.append("first person, full draw")
    elif spec["use"] == "block":
        shots.append(V.first_person([(model, disp["firstperson_righthand"], "l", None)]))
        labels.append("first person, off hand")
        shots.append(V.first_person([(model, udisp["firstperson_righthand"], "l", "block")]))
        labels.append("first person, off hand, blocking")
    else:
        shots.append(V.first_person([(model, disp["firstperson_righthand"], "r", None)]))
        labels.append("first person, main hand")
        if spec["use"] == "guard":
            shots.append(V.first_person([(use_model, udisp["firstperson_righthand"], "r", "block")]))
            labels.append("first person, guard")
    p = os.path.join(SHOTS, f"{wid}_fp.png")
    V.strip([s.resize((640, 360)) for s in shots], labels).save(p)
    files.append(p)
    # 4. 3인칭
    side = "l" if spec["use"] == "block" else "r"
    poses = ("none", "item") if side == "l" else ("item", "none")
    tp = V.third_person([(model, disp["thirdperson_righthand"], side)], poses=poses, views=((-35, 10), (90, 4)))
    tp += V.third_person([(model, disp["thirdperson_righthand"], side)], poses=poses, views=((90, 4),), close=2.6)
    labels = ["third person, front 3/4", "third person, side", "side, close"]
    if spec["use"] in ("guard", "block"):
        bp = ("none", "block") if side == "l" else ("block", "none")
        tp += V.third_person([(use_model, udisp["thirdperson_righthand"], side)], poses=bp, views=((-35, 10),))
        labels.append("third person, " + ("blocking" if spec["use"] == "block" else "guard"))
    elif spec["use"] == "bow":
        tp += V.third_person([(res["pull"][2], disp["thirdperson_righthand"], "r")], poses=("bow_hold", "bow_draw"),
                             views=((-60, 6),))
        labels.append("third person, drawing")
    p = os.path.join(SHOTS, f"{wid}_tp.png")
    V.strip(tp, labels).save(p)
    files.append(p)
    return files


def main(argv):
    import shutil
    ids = [a for a in argv if not a.startswith("-")]
    out = SCRATCH
    if os.path.exists(out):
        shutil.rmtree(out)
    ic = icons()
    reg = registry()
    done = {}
    for wid, entry in reg.items():
        if ids and wid not in ids:
            continue
        spec = _spec(entry)
        from PIL import Image
        icon = ic.get(wid) or Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        res = build_one(out, wid, spec, icon)
        files = previews(wid, spec, res, icon)
        n = len(res["3d"].elements)
        print(f"{wid}: 요소 {n}, 재료 {C.mat_count(res['weapon'])}" + ("" if wid in ic else "  (16px 그림 없음)"))
        for f in files:
            print("  ", os.path.relpath(f, ROOT))
        done[wid] = res
    if not ids:
        from weapons import _views as V
        V.lineup([(k, v["3d"]) for k, v in done.items()], os.path.join(PACK, "preview", "weapons_lineup_a.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
