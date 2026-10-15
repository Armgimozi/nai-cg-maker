import itertools, statistics as st, pv_sim as S, pv_tune as T
import sys
res=[]
def score(P):
    tot=0; rows=[]
    for L in (20,35,50):
        m=T.rot_metrics(P,L)
        gg=m['gg_dmg_med']; gd=m['gd_dmg_med']; hm=m['hit_max'][0]; gga=m['gga_dmg_med']
        e=((gg-1.10)/0.12)**2 + ((gd-0.60)/0.08)**2 + (max(0,hm-0.15)/0.02)**2 + (max(0,1.0-gga)/0.05)**2
        tot+=e; rows.append((L,gg,gga,gd,hm,m['dg_med'],m['dd_med']))
    return tot, rows
best=[]
for dw in (0.0, 0.2, 0.35, 0.5):
  for ex in (2.5, 3.0, 3.5):
    for ult in (0.5, 0.7):
      for ws in (0.6, 0.8):
        for cs in (0.7, 0.85):
          # solve coef & dmg roughly: grid
          for coef in (0.02,0.05,0.1,0.2,0.4):
            for dmg in (0.7, 1.0, 1.4):
              P=dict(S.PVP_NOCAP, def_weight=dw, buffer=dict(coef=coef, exp=ex), ult=ult, wskill=ws, crit_scale=cs, dmg=dmg)
              s,rows=score(P)
              best.append((s,dw,ex,ult,ws,cs,coef,dmg,rows))
best.sort(key=lambda x:x[0])
for b in best[:15]:
    print(round(b[0],2), 'dw',b[1],'exp',b[2],'ult',b[3],'ws',b[4],'cs',b[5],'coef',b[6],'dmg',b[7])
    for r in b[8]: print('    L%d gg %.0f%% (all %.0f%%) gd %.0f%% hitmax %.1f%% dg %.0f%% dd %.0f%%'%(r[0],r[1]*100,r[2]*100,r[3]*100,r[4]*100,r[5]*100,r[6]*100))
