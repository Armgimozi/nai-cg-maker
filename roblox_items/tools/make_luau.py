"""armor/fit_data.json + item_data.json → roblox/ItemData.lua (Luau 데이터 모듈) 생성.

  python roblox_items/tools/make_luau.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SET_KO = {"leather": "가죽", "iron": "철", "knight": "기사"}
SLOT_KO = {"helmet": "투구", "chest": "갑옷", "greaves": "각반"}
ARMOR_ORDER = ["leather", "iron", "knight"]
SLOT_ORDER = ["helmet", "chest", "greaves"]
# 빛나는 아이템 → PointLight 색
GLOW = {
    "mage_staff": (0.45, 0.75, 1.0),
    "arcane_orb": (0.70, 0.40, 1.0),
    "ancient_runestone": (0.35, 0.95, 1.0),
    "flame_ring": (1.0, 0.40, 0.20),
    "guardian_amulet": (0.35, 0.55, 1.0),
}


def v3(v):
    return "Vector3.new({:.4f}, {:.4f}, {:.4f})".format(*v)


def main():
    fit = json.loads((ROOT / "armor" / "fit_data.json").read_text("utf-8"))
    items = json.loads((ROOT / "item_data.json").read_text("utf-8"))
    L = ["-- 자동 생성 파일 (roblox_items/tools/make_luau.py) — 직접 고치지 말 것",
         "-- 방어구: 부위(R15) 중심 기준 offset / size  (기준 체형 = R15 기본, 스터드)",
         "-- 아이템: size = 실제 크기(스터드), grip = Handle 중심 기준 손잡이 위치",
         "", "local ItemData = {}", "", "ItemData.Armor = {"]
    for st in ARMOR_ORDER:
        if st not in fit:
            continue
        L.append(f"\t{st} = {{")
        L.append(f'\t\tname = "{SET_KO[st]}",')
        for slot in SLOT_ORDER:
            if slot not in fit[st]:
                continue
            L.append(f"\t\t{slot} = {{ -- {SET_KO[st]} {SLOT_KO[slot]}")
            for part, d in fit[st][slot].items():
                L.append(f"\t\t\t{part} = {{ offset = {v3(d['offset'])}, size = {v3(d['size'])} }},")
            L.append("\t\t},")
        L.append("\t},")
    L += ["}", "", "ItemData.Items = {"]
    for kind in ("weapon", "artifact"):
        for iid, d in items.items():
            if d["kind"] != kind:
                continue
            glow = GLOW.get(iid)
            g = ", glow = Color3.new({:.2f}, {:.2f}, {:.2f})".format(*glow) if glow else ""
            L.append(f'\t{iid} = {{ kind = "{kind}", name = "{d["name_ko"]}", '
                     f"size = {v3(d['size'])}, grip = {v3(d['grip'])}{g} }},")
    L += ["}", "", "return ItemData", ""]
    out = ROOT / "roblox" / "ItemData.lua"
    out.write_text("\n".join(L), "utf-8")
    print("생성:", out)


if __name__ == "__main__":
    main()
