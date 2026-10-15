import json, sys
f = sys.argv[1] if len(sys.argv) > 1 else 'lk_sim_full.json'
r = json.load(open(f))
V = ["base", "native", "heavy", "light", "cloth"]
CL = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
fls = sorted({int(k.split('|')[1]) for k in r})
for fl in fls:
    if fl == 2: continue
    print(f"== F{fl}  room dps/taken  |  clear avg-normal / skilled-normal / skilled-hard")
    for c in CL:
        cells = []
        for v in V:
            rm = r.get(f"room|{fl}|{v}|{c}|skilled|normal")
            a = r.get(f"solo|{fl}|{v}|{c}|average|normal"); s = r.get(f"solo|{fl}|{v}|{c}|skilled|normal"); h = r.get(f"solo|{fl}|{v}|{c}|skilled|hard")
            cells.append(f"{v[:2]} {rm['dps']:6.1f}/{rm['taken']:.2f} {a['clear']*100:3.0f}/{s['clear']*100:3.0f}/{h['clear']*100:3.0f}")
        print(f"{c:9} " + " | ".join(cells))
print("== F2 early (base vs native) novice / average")
for c in CL:
    cells=[]
    for v in ("base","native"):
        n=r.get(f"solo|2|{v}|{c}|novice|normal"); a=r.get(f"solo|2|{v}|{c}|average|normal")
        cells.append(f"{v} {n['clear']*100:3.0f}/{a['clear']*100:3.0f}")
    print(c, " | ".join(cells))
