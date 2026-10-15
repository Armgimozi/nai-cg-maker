import json, sys, collections
CL = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
def load(tag):
    d = json.load(open(f"ce_results_{tag}.json"))
    return d
def per_class(tag, diff, prof, key="clear"):
    d = load(tag)
    tab = collections.defaultdict(dict)
    for row in d["rows"]:
        t, r = row["task"], row["result"]
        if t[1] != "solo" or t[4] != diff or t[3] != prof: continue
        tab[(t[0], t[2])][t[5]] = r
    for nm in d["names"]:
        print(f"[{nm}] {diff} {prof} {key}")
        for c in CL:
            rr = tab[(nm, c)]
            cells = []
            for fl in (1,3,5,7,10):
                r = rr.get(fl)
                if not r: continue
                v = r[key]
                cells.append(f"F{fl} " + (f"{v:4.0%}" if key == "clear" else f"{(v or 0):5.0f}"))
            print(f"  {c:9} " + "  ".join(cells))
if __name__ == "__main__":
    tag = sys.argv[1]
    for diff, prof in [("normal","average"),("normal","skilled"),("nightmare","skilled")]:
        for key in ("clear","boss_t","room_t"):
            per_class(tag, diff, prof, key)
