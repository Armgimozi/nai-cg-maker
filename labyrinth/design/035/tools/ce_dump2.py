import yaml, json, collections
R="/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/"
it=yaml.safe_load(open(R+"items.yml"))["items"]
ws={k:v for k,v in it.items() if v.get("type")=="weapon"}
# show one with mechanics skill
for k,v in ws.items():
    if v.get("weapon_skills"):
        print(k, json.dumps(v["weapon_skills"],ensure_ascii=False,indent=1)[:2500]); break
# list all weapons compact
rows=sorted(ws.items(), key=lambda kv:(kv[1]["level_req"], kv[1]["weapon_type"]))
for k,v in rows:
    d=v["stats"]["damage"]
    sks=[(s["id"],s.get("skill"),s["input"]) for s in v.get("weapon_skills") or []]
    print(f'{k:34} {v["weapon_type"]:12} L{v["level_req"]:<2} F{v["floor"]:<2} {v["rarity"]:9} dmg={d} shape={v["model"]["shape"]} req={v.get("requires")} sk={[s[1] for s in sks]}')
