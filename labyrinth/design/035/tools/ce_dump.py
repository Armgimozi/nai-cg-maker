import yaml, json, collections
R="/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/"
it=yaml.safe_load(open(R+"items.yml"))["items"]
ws={k:v for k,v in it.items() if v.get("type")=="weapon"}
print(len(ws))
keys=collections.Counter()
for k,v in ws.items():
    for kk in v: keys[kk]+=1
print(keys)
ex=next(iter(ws.items()))
print(json.dumps(ex,ensure_ascii=False,indent=1)[:3000])
sk=collections.Counter()
for k,v in ws.items():
    for s in v.get("weapon_skills") or []:
        sk[(s.get("skill") or s.get("type") or s.get("id"))]+=1
print(sk)
