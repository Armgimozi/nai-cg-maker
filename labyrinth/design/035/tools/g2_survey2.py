import yaml
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
items=yaml.safe_load(open(C+'items.yml'))['items']
for k,v in items.items():
    if v.get('type')=='armor':
        st=v.get('stats',{})
        print(k, v.get('armor_slot'), v.get('armor_set'), v.get('rarity'), 'L',v.get('level_req'),'F',v.get('floor'), v.get('requires'), v.get('requires_any'), v.get('sources'), v.get('classes'), v.get('model',{}).get('shape'), {a:b for a,b in st.items()})
