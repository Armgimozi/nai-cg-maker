import yaml, collections, json
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
items=yaml.safe_load(open(C+'items.yml'))['items']
cnt=collections.Counter()
gear={}
for k,v in items.items():
    t=v.get('type')
    if t in('weapon','armor','accessory'):
        slot=v.get('armor_slot') if t=='armor' else t
        cnt[(t,slot)]+=1
        gear[k]=v
print(cnt)
print('req keys', collections.Counter(tuple(sorted((v.get('requires') or {}).keys())) for v in gear.values()))
print('reqany', collections.Counter(tuple(sorted((v.get('requires_any') or {}).keys())) for v in gear.values()))
print('sources', collections.Counter(tuple(v.get('sources') or []) for v in gear.values()))
# armour sets
sets=collections.Counter(v.get('armor_set') for v in gear.values() if v.get('type')=='armor')
print(len(sets), sets)
print(collections.Counter(v.get('set_bonus') for v in gear.values() if v.get('type')=='armor'))
