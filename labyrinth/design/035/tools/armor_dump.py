import yaml,json,collections
C='/home/user/w-r1/labyrinth/plugin/src/main/resources/content/'
d=yaml.safe_load(open(C+'items.yml'))
it=d['items']; sets=d['sets']
setlook={k:v.get('look') for k,v in sets.items()}
arm=[(k,v) for k,v in it.items() if v.get('type')=='armor']
print(len(arm))
arm.sort(key=lambda kv:(kv[1]['level_req'],kv[1].get('armor_slot'),kv[0]))
cnt=collections.Counter()
for k,v in arm:
    look=setlook.get(v.get('set_bonus')) if v.get('set_bonus') else None
    cnt[(look, v.get('armor_slot'))]+=1
    print(f"L{v['level_req']:<3} F{v.get('floor')} {v['rarity'][:4]:4} {v.get('armor_slot'):7} {k:30} set={v.get('set_bonus')} aset={v.get('armor_set')} look={look} cls={v.get('classes')} req={v.get('requires')}{v.get('requires_any') or ''} {json.dumps(v['stats'],ensure_ascii=False)} src={v.get('sources')}")
print(cnt)
