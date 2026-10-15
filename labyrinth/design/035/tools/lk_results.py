#!/usr/bin/env python3
"""TASK B — 기대값 모델 표 · 지배 검사 · 섞어 입기 예 → lk_results.json (lk_spec.py 가 읽는다)."""
import json
import os

import lk_core as K
import lk_model as LM

HERE = os.path.dirname(os.path.abspath(__file__))
LVS = (5, 10, 25, 45)
LOOKS3 = ("heavy", "light", "cloth")


def slim(b, ref):
    return dict(dps=round(b["dps"], 1), ehp=round(b["ehp"]), ehp_ms=round(b["ehp_ms"]),
                d_dps=round(b["dps"] / ref["dps"] - 1, 3), d_ehp=round(b["ehp"] / ref["ehp"] - 1, 3),
                d_ehp_ms=round(b["ehp_ms"] / ref["ehp"] - 1, 3),
                hp=round(b["hp"]), defense=round(b["defense"], 1), dr=round(b["dr"], 3), evasion=round(b["evasion"], 3),
                crit=round(b["crit"], 3), speed=round(b["speed"], 3), move=round(b["move"], 3), cdr=round(b["cdr"], 3),
                cd_mult=round(b["d"].get("cd_mult", 1.0), 3), skill_dmg=round(b["skill_dmg"], 3),
                mana_regen=round(b["mana_regen"], 2), mp=round(b["mp"]), full=b["full"], counts=b["counts"],
                armor=b["armor"], sets=sorted({K.ALL_ITEMS[i].get("set_bonus") or i for i in b["armor"].values()}),
                alloc={k: v for k, v in b["alloc"].items() if v}, need=b["need"], weapon=b["weapon"])


def model_tables():
    out = {}
    for L in LVS:
        for cls in LM.CLASSES:
            ref = LM.build(cls, L, "native", looks=False, new_req=False, sets=True)
            row = dict(base=slim(ref, ref))
            row["native_noimp"] = slim(LM.build(cls, L, LM.NATIVE[cls], looks=False), ref)
            for lk in LOOKS3:
                row[lk] = slim(LM.build(cls, L, lk), ref)
                row[lk + "_noimp"] = slim(LM.build(cls, L, lk, looks=False), ref)
            out[f"{cls}|{L}"] = row
    return out


def dominance(tab, tol=0.02, suffix=""):
    """a 가 b 를 '엄격히 이긴다' = DPS·EHP(마나 보호막 포함) 둘 다 b 이상, 그리고 하나는 tol 보다 크게."""
    res = {}
    for key, row in tab.items():
        dom = []
        for a in LOOKS3:
            for b in LOOKS3:
                if a == b:
                    continue
                A, B = row[a + suffix], row[b + suffix]
                ea, eb = A["ehp_ms"], B["ehp_ms"]
                if A["dps"] >= B["dps"] * (1 - 0.005) and ea >= eb * (1 - 0.005) and \
                        (A["dps"] > B["dps"] * (1 + tol) or ea > eb * (1 + tol)):
                    dom.append(f"{a}>{b}")
        res[key] = dom
    return res


MIXED = [
    ("warrior_light", "광전사 가죽 — 피하며 치는 치명 전사", "berserker", 25, "light", {}),
    ("guardian_light", "수호기사 가죽 — 방패 든 날랜 전사", "guardian", 25, "light", {}),
    ("mage_heavy", "비전술사 판금 — 단단한 마법사", "arcanist", 25, "heavy", {}),
    ("priest_heavy_shield", "사제 판금 + 방패 — 성기사 사제", "priest", 25, "heavy", {"shield": True}),
    ("hunter_heavy", "사냥꾼 판금 — 버티는 사수", "hunter", 25, "heavy", {}),
    ("berserker_cloth", "광전사 천 — 스킬로 싸우는 전사", "berserker", 45, "cloth", {}),
    ("shadow_half", "그림자 판금 2 + 가죽 2 — 반반", "shadow", 25,
     {"head": "light", "chest": "heavy", "legs": "heavy", "feet": "light"}, {}),
    ("arcanist_spellblade", "비전술사 먹물 장막(전설 가죽, 민첩·지능) — 빠른 마법 검사", "arcanist", 45,
     {"_fixed": {"head": "inkveil_helm", "chest": "inkveil_chest", "legs": "inkveil_legs", "feet": "inkveil_boots"}}, {}),
]


def mixed():
    out = []
    for mid, name, cls, L, look, kw in MIXED:
        ref = LM.build(cls, L, LM.NATIVE[cls])
        b = LM.build(cls, L, look, **kw)
        r = slim(b, ref)
        r.update(id=mid, name=name, cls=cls, L=L, look=look if isinstance(look, str) else "mixed",
                 vs_native_dps=round(b["dps"] / ref["dps"] - 1, 3), vs_native_ehp=round(b["ehp_ms"] / ref["ehp_ms"] - 1, 3))
        out.append(r)
    return out


def armor_table():
    rows = []
    for iid, v in sorted(K.armor_items(True).items(), key=lambda kv: (kv[1]["level_req"], kv[1].get("armor_slot"), kv[0])):
        shares, ident, why = K.req_spec(iid)
        old_all, old_any = K.old_requires(iid)
        ren = dict(K.STATS_RENAME.get(v.get("set_bonus"), {}))
        rows.append(dict(id=iid, name=v["name"], slot=v.get("armor_slot"), set=v.get("set_bonus"), level=v["level_req"],
                         rarity=v["rarity"], look=K.look_of(iid), identity=ident, old_requires=old_all,
                         old_requires_any=old_any, requires=K.new_requires(iid), stats_rename=ren,
                         proposed=bool(v.get("proposed"))))
    return rows


if __name__ == "__main__":
    tab = model_tables()
    res = dict(model=tab, dominance=dominance(tab), dominance_noimp=dominance(tab, suffix="_noimp"), mixed=mixed(),
               armor=armor_table(),
               looks={k: dict(piece=v["piece"], full=v["full"], name=v["name"]) for k, v in K.LOOKS.items()})
    with open(os.path.join(HERE, "lk_results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for k, v in res["dominance"].items():
        print(k, v)
    for m in res["mixed"]:
        print(m["name"], m["sets"], f"dps {m['vs_native_dps']:+.0%} ehp {m['vs_native_ehp']:+.0%}")
