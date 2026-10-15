#!/usr/bin/env python3
"""review2 — 명세끼리·데이터와 어긋남 검사 (읽기만)."""
import json, os, sys, yaml, collections, math
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "/home/user/nai-cg-maker/labyrinth"
C = f"{REPO}/plugin/src/main/resources/content"
items = yaml.safe_load(open(f"{C}/items.yml"))
IT, SETS = items["items"], items["sets"]
g = json.load(open(f"{D}/gear_spec.json"))
cs = json.load(open(f"{D}/combat_spec.json"))
ua = json.load(open(f"{D}/unique_assign_all.json"))
un = json.load(open(f"{D}/unique_assign_new.json"))
lk = json.load(open(f"{D}/look_spec.json"))
pv = json.load(open(f"{D}/pvp_spec.json"))
out = collections.OrderedDict()

# 1. id 충돌
new_w = set(g["weapons"])
new_a = set()
for sid, s in g["armor_sets"].items():
    new_a |= set(s.get("pieces_items", {}))
coll = sorted((new_w | new_a | set(g["armor_sets"])) & (set(IT) | set(SETS)))
out["id_collisions_with_items_yml"] = coll
out["new_weapon_ids"] = len(new_w)
out["new_armor_piece_ids"] = len(new_a)
dup = [k for k, v in collections.Counter(list(new_w) + list(new_a)).items() if v > 1]
out["dup_new_ids"] = dup
names = collections.Counter([v["name"] for v in IT.values()] + [g["weapons"][k]["name"] for k in new_w]
                            + [p["name"] for s in g["armor_sets"].values() for p in s.get("pieces_items", {}).values()])
out["dup_names"] = [n for n, c in names.items() if c > 1]

# 2. unique 블록: gear_spec 새 무기 vs unique_assign_new (D)
diff_u = []
for k in new_w:
    gu = g["weapons"][k].get("unique") or {}
    du = un.get(k)
    if not du:
        diff_u.append((k, "D 없음")); continue
    gp = {kk: vv for kk, vv in gu.items() if kk not in ("id", "name")}
    if gu.get("id") != du["effect"] or gu.get("name") != du["name"] or any(abs(float(gp.get(p, -1)) - float(v)) > 1e-6 for p, v in du["params"].items() if isinstance(v, (int, float))):
        diff_u.append((k, gu.get("id"), du["effect"]))
out["gear_vs_D_unique_mismatch"] = len(diff_u)
out["gear_vs_D_unique_mismatch_examples"] = diff_u[:8]

# 3. 간격·한 방: gear_spec vs combat_spec
iv_diff, ph_diff = [], []
for k in new_w:
    gw = g["weapons"][k]
    if abs(gw["attack"]["interval"] - cs["intervals"][k]) > 1e-6:
        iv_diff.append((k, gw["attack"]["interval"], cs["intervals"][k]))
    if list(gw["stats"]["damage"]) != list(cs["per_hit"][k]):
        ph_diff.append((k, gw["stats"]["damage"], cs["per_hit"][k]))
for k, ch in g["existing_changes"].items():
    if abs(ch["attack"]["interval"] - cs["intervals"][k]) > 1e-6:
        iv_diff.append((k, ch["attack"]["interval"], cs["intervals"][k]))
    if list(ch["stats_damage"]) != list(cs["per_hit"][k]):
        ph_diff.append((k, ch["stats_damage"], cs["per_hit"][k]))
out["interval_mismatch"] = iv_diff
out["per_hit_mismatch"] = ph_diff

# 4. 방어구 요구치: gear_spec armor_changes / armor_sets vs look_spec armor_items
lk_req = {}
for a in lk["armor_items"]:
    lk_req[a["id"]] = a.get("requires") or {}
g_req = {k: v.get("requires", {}) for k, v in g["armor_changes"].items()}
for s in g["armor_sets"].values():
    for pid, p in s["pieces_items"].items():
        g_req[pid] = p.get("requires", {})
same = differ = 0; ex = []
for k in sorted(set(lk_req) & set(g_req)):
    if lk_req[k] == g_req[k]: same += 1
    else:
        differ += 1
        if len(ex) < 12: ex.append((k, g_req[k], lk_req[k]))
out["armor_req_same"] = same
out["armor_req_differ"] = differ
out["armor_req_examples"] = ex
out["armor_only_in_look"] = sorted(set(lk_req) - set(g_req))[:10]
out["armor_only_in_gear"] = sorted(set(g_req) - set(lk_req))[:10]

# 5. 예산 식 차이 (무기 gear T vs look T)
def Tg(L): return 0 if L <= 2 else math.ceil(2.75 * (L - 1) - 1e-9)
def Tl(L):
    R = 0 if L <= 2 else math.ceil(2.5 * (L - 1) - 1e-9)
    return math.ceil(1.1 * R - 1e-9)
out["budget_diff_levels"] = [(L, Tg(L), Tl(L)) for L in range(3, 51) if Tg(L) != Tl(L)]

# 6. tier/level window 와 hidden level
wins = collections.Counter()
for k in new_w:
    sp = g["weapons"][k]["_spec"]
    wins[(sp["level_band"], tuple(sp["level_window"]), tuple(sp["floors"]))] += 1
out["level_windows_sample"] = [list(k) + [v] for k, v in list(wins.items())[:12]]

# 7. epic+ 한 획득처 종류
viol = []
allw = {}
for k, v in IT.items():
    if v.get("type") == "weapon":
        ch = g["existing_changes"][k]
        allw[k] = (v["rarity"], ch.get("sources", v.get("sources")))
for k in new_w:
    allw[k] = (g["weapons"][k]["rarity"], g["weapons"][k]["sources"])
for k, (r, s) in allw.items():
    if r in ("epic", "legendary", "mythic") and len(set(s or [])) != 1:
        viol.append((k, r, s))
out["epic_plus_multi_source_tags"] = viol
src = collections.Counter()
for k, (r, s) in allw.items():
    for x in s or []: src[(x)] += 1
out["source_tag_counts_all_weapons"] = dict(src)

# 8. new weapons have models: new_silhouette shapes listed?
shapes = collections.Counter(g["weapons"][k]["model"]["shape"] for k in new_w)
out["new_weapon_shapes"] = dict(shapes)
out["new_shapes_spec"] = list(g["new_shapes"])
old_shapes = collections.Counter(v["model"]["shape"] for v in IT.values() if v.get("type") == "weapon")
out["old_shapes"] = len(old_shapes)
out["shapes_unknown"] = sorted(set(shapes) - set(old_shapes) - set(g["new_shapes"]))

# 9. unique_assign_all covers 237
out["ua_count"] = len(ua)
out["ua_missing"] = sorted((set(IT[k]["name"] and k for k in IT if IT[k].get("type") == "weapon") | new_w) - set(ua))

# 10. pvp skill_mult covers new weapon skills?
nskills = [(k, s["input"]) for k in new_w for s in (g["weapons"][k].get("weapon_skills") or [])]
out["new_weapon_skill_count"] = len(nskills)
out["pvp_skill_mult_keys"] = len(pv["skill_mult"]) if isinstance(pv["skill_mult"], (list, dict)) else pv["skill_mult"]
json.dump(out, open(f"{D}/tools/rv_consist.json", "w"), ensure_ascii=False, indent=1)
for k, v in out.items():
    print(k, ":", v if not isinstance(v, list) or len(v) < 15 else (v[:15], "... n=", len(v)))
