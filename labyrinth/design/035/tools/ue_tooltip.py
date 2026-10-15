# ItemTooltip.lines 줄 수 재현 (근사) — 고유 효과 줄을 넣었을 때 20줄 안에 드는지
import yaml,sys,json,math
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
it=yaml.safe_load(open(C+'items.yml'))['items']
WRAP=34;MAX=20
def wrap(t,w=WRAP):
    out=[];rest=t.strip()
    while len(rest)>w:
        cut=rest.rfind(' ',0,w+1)
        if cut<=w//2: cut=w
        out.append(rest[:cut].strip()); rest=rest[cut:].strip()
    if rest: out.append(rest)
    return out
def count(v,uniq_lines=0,E=2,uniq_short=1):
    head=1+(1 if v.get('requires') or v.get('requires_any') else 0)
    st=v['stats']; n=len(st); stats=1+math.ceil((n-1)/2)
    sk=v.get('weapon_skills') or []
    descs=[len(wrap(s.get('description',''))) for s in sk]
    flavor=len(wrap(v.get('lore',''))) if v.get('lore') else 0
    boss='boss' in (v.get('sources') or [])
    src=1
    for tier in range(5):
        keep= tier<=2 if boss else tier<=1
        blanks= tier<=1 if boss else tier<=2
        short= tier>=4
        o=head
        o+= (1 if blanks else 0)+stats+E
        if sk or uniq_lines:
            o+= 1 if blanks else 0
            o+= len(sk)+sum((1 if (short and d>1) else d) for d in descs)
            o+= (min(uniq_lines,1+uniq_short) if short else uniq_lines)
        if tier==0 and flavor: o+=1+flavor
        if keep: o+=src
        if o<=MAX: return o,tier,keep
    return o,4,keep
if __name__=='__main__':
    ws=[(k,v) for k,v in it.items() if v.get('type')=='weapon']
    for u in (0,2,3):
        bad=[];worst=0
        for k,v in ws:
            for E in (2,1):
                o,t,keep=count(v,u,E)
                boss='boss' in v['sources']
                if o>MAX or (boss and not keep): bad.append((k,E,o,t))
        print('uniq_lines',u,'bad',len(bad),bad[:12])
    for k,v in ws:
        o,t,keep=count(v,0,2)
        if t>=2: print(k,o,t,keep)
