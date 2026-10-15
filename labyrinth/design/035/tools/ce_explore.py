import sys, copy
import ce_core as C, ce_model as M

PREF = {"guardian": ["STR", "VIT"], "berserker": ["STR"], "hunter": ["DEX", "STR"], "arcanist": ["INT"],
        "priest": ["WIS", "INT"], "shadow": ["DEX", "STR", "LUK"]}

def req_stat(wid):
    r = C.requires_of(wid)
    if "any" in r: return list(r["any"].keys())
    return list(r.keys()) or ["-"]

def pick_weapon(cls, L, pref=None, include_new=False):
    fl = M.floor_of_level(L); cap = 3 if fl >= 6 else 2
    style = C.STYLE_OF_TYPE[C.RECOMMENDED[cls]]
    wt = C.RECOMMENDED[cls]
    pref = pref or PREF[cls]
    cands = []
    for wid, w in list(C.WEAPONS.items()) + (list(C.NEW_WEAPONS.items()) if include_new else []):
        if w.get("level_req", 1) > L or M.RANK[w["rarity"]] > cap: continue
        if wid in C.WEAPONS:
            if w["weapon_type"] != wt: continue
        else:
            if C.style_of(w["model"]["shape"]) != style: continue
        rs = req_stat(wid)
        score = min([pref.index(s) for s in rs if s in pref] + [9]) if rs != ["-"] else 0
        if score == 9: continue
        cands.append((w["level_req"], M.RANK[w["rarity"]], -score, wid))
    return max(cands)[3] if cands else M.gear_for(cls, L)[0]

def best_split(cls, L, P, wid):
    """VIT = 0.3.4 와 같은 개수, 요구치 채움, 나머지를 '요구 스탯 더'와 '피해 스탯'으로 나누는 비율 중 DPS 최대."""
    best = None
    for frac in [i/10 for i in range(0, 11)]:
        a = M.plan_alloc(cls, L, wid, "sensible", P)
        dmg = "INT" if M.CLASS_SKILL_KIND[cls] == "magic" or M.weapon_kind(wid) == "magic" else "STR"
        mv = int(a[dmg] * frac)
        if cls != "priest":
            a[dmg] -= mv; a["DEX"] += mv
        n = M.new_player(cls, L, P, "sensible", wid, alloc=a)
        if best is None or n["dps"] > best[1]["dps"]:
            best = (frac, n)
    return best

def table(P, levels=(10, 25, 45), include_new=False, opt=True):
    rows = []
    for L in levels:
        for cls in C.CLASSES:
            o = M.old_player(cls, L)
            wid = o["weapon"] if not C.USE_GEAR_REQUIRES else pick_weapon(cls, L, include_new=include_new)
            if opt:
                frac, n = best_split(cls, L, P, wid)
            else:
                frac, n = 0, M.new_player(cls, L, P, "sensible", wid)
            rows.append((L, cls, o, n, frac))
            print(f"L{L:<2} {cls:9} old {o['weapon'][:20]:20} dps {o['dps']:7.1f} ehp {o['ehp']:6.0f} | new {n['weapon'][:20]:20} req {'/'.join(req_stat(n['weapon'])):7} "
                  f"dps {n['dps']:7.1f} ({n['dps']/o['dps']-1:+.0%}) ehp {n['ehp']:6.0f} ({n['ehp']/o['ehp']-1:+.0%}) dex→{frac:.1f} "
                  f"S{n['stats']['STR']} D{n['stats']['DEX']} I{n['stats']['INT']} V{n['stats']['VIT']} W{n['stats']['WIS']} spd{n['speed']:.2f}")
    return rows

if __name__ == "__main__":
    P = dict(C.P_DEFAULT)
    C.USE_GEAR_REQUIRES = False
    for a in sys.argv[1:]:
        if a == "gear":
            C.USE_GEAR_REQUIRES = True; continue
        k, v = a.split("="); P[k] = float(v)
    table(P)
