import yaml,collections,json
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
it=yaml.safe_load(open(C+'items.yml'))['items']
W={k:v for k,v in it.items() if v.get('type')=='weapon'}
band=lambda L:(L-1)//5+1
c=collections.Counter(); r=collections.defaultdict(collections.Counter); s=collections.defaultdict(collections.Counter); f=collections.defaultdict(collections.Counter)
for k,v in W.items():
    b=band(v['level_req']); c[b]+=1; r[b][v['rarity']]+=1; s[b]['+'.join(v.get('sources',[]))]+=1; f[b][v['floor']]+=1
for b in range(1,11): print(b, c[b], dict(r[b]), dict(s[b]), dict(f[b]))
# armor sets
sets=yaml.safe_load(open(C+'items.yml')).get('sets',{})
print(len(sets))
A={k:v for k,v in it.items() if v.get('type')=='armor'}
bys=collections.defaultdict(list)
for k,v in A.items(): bys[v.get('set_bonus') or v.get('armor_set') or '-'].append((k,v['armor_slot'],v['rarity'],v['level_req'],v['floor'],v.get('sources'),v.get('requires'),v.get('requires_any'),v.get('model',{}).get('shape')))
for k,l in sorted(bys.items(), key=lambda kv: kv[1][0][3]): print(k, l[0][2], 'L',l[0][3],'F',l[0][4], l[0][5], [x[1] for x in l], l[0][6], l[0][7], [x[8] for x in l])
