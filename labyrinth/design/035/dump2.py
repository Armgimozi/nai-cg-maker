import yaml
d=yaml.safe_load(open('/home/user/w-r1/labyrinth/plugin/src/main/resources/content/items.yml'))
it=d['items']
ws=[(k,v) for k,v in it.items() if v.get('type')=='weapon']
ws.sort(key=lambda kv:(kv[1]['weapon_type'],kv[1]['level_req']))
for k,v in ws:
    print(f"## {k} [{v['weapon_type']} L{v['level_req']} {v['rarity']}] {v['name']} — {v.get('lore','')}")
    for s in v.get('weapon_skills') or []:
        print(f"   - {s['input']} {s['name']}: {s.get('description','')}")
