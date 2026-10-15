#!/usr/bin/env python3
"""review2 (2차) — 그림자 PvE 고침(skill_scale 0.62→0.70, 급소 찌르기 치명 피해 +0.40→+0.50)이 PvP 에 주는 영향.
pvp_spec 최종안 그대로, 직업 평균 승률(모든 상대)과 유리→유리 한 바퀴(그림자)."""
import os, sys, json, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import pv_core as V, pv_build as B, pv_final as F, pv_matrix as MX, pv_sim as S
res = {}
for tag in ('spec', 'shadow_fix', 'shadow_fix_cm1.1'):
    if tag != 'spec':
        V.SKILL_SCALE['shadow'] = 0.70
        V.CLASS_VALUES['vital_point_crit_damage'] = 0.50
    P = dict(F.PVP_NEW)
    if tag == 'shadow_fix_cm1.1':
        P['class_mult'] = dict(P['class_mult'], shadow=1.1)
    row = {}
    for L in (20, 35, 50):
        bl = {(c, k): B.build(c, L, k) for c in V.CLASS_ORDER for k in ('burst', 'guard')}
        M = MX.matrix(P, L, n=24, builds=bl)
        s = MX.summary(M)
        rot = [S.rotation(bl[('shadow', 'burst')], bl[(c, 'burst')], P)[0] for c in V.CLASS_ORDER]
        row[L] = dict(class_all={k: round(v, 3) for k, v in s['class_all'].items()}, shadow_rot_glass=round(st.median(rot), 3))
        print(tag, L, 'shadow win', row[L]['class_all'].get('shadow'), 'spread', min(row[L]['class_all'].values()), max(row[L]['class_all'].values()),
              'shadow 한 바퀴→유리 중앙', row[L]['shadow_rot_glass'])
    res[tag] = row
json.dump(res, open(os.path.join(HERE, 'rv2_pvpshadow.json'), 'w'), ensure_ascii=False, indent=1)
