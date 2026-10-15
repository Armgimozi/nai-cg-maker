#!/usr/bin/env python3
"""review2 (2차) — g2_core 무기 표의 피해 종류를 gear_spec.json attack.kind 로 고쳐(지능 활·지능 근접 8개 = 마법)
직업 × 띠 '알맞은 무기 수'를 다시 센다. 방어구 요구 = look_spec 표 + review2 고침 3개 (rv_lookfix)."""
import io, json, os, sys, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rv_lookfix  # noqa: F401
import lk_core as K
import g2_core as G
import g2_check as C2
D2 = os.path.dirname(HERE)
gs = json.load(open(os.path.join(D2, 'gear_spec.json')))


def load(fix_kind=True):
    W = G.weapons_all()
    if fix_kind:
        for wid, w in W.items():
            src = gs['weapons'].get(wid) or gs['existing_changes'].get(wid)
            k = ((src or {}).get('attack') or {}).get('kind')
            if k:
                w['kind'] = k
    WR = {w: dict(requires=(gs['weapons'][w] if w in gs['weapons'] else gs['existing_changes'][w])['requires']) for w in W}
    A = G.armor_all()
    AR = {aid: dict(requires=K.new_requires(aid)) for aid in A}
    return W, WR, A, AR


def check(W, WR, A, AR):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return C2.run(W, WR, A, AR, verbose=False)


if __name__ == '__main__':
    out = {}
    for tag, fk in (('g2_core 종류', False), ('gear_spec attack.kind', True)):
        W, WR, A, AR = load(fk)
        chk = check(W, WR, A, AR)
        print('==', tag, '== 알맞은 무기 수 (사냥꾼: 원거리만 괄호)')
        rows = {}
        for c in G.CLS:
            cells = []
            for b in G.BANDS:
                ids = chk['by_class_band'][f'{c}|{b}']['good_ids']
                r = sum(1 for i in ids if W[i]['style'] == 'ranged')
                cells.append(f"{len(ids):2d}({r})" if c == 'hunter' else f"{len(ids):2d}   ")
            rows[c] = [len(chk['by_class_band'][f'{c}|{b}']['good_ids']) for b in G.BANDS]
            print(f'{c:10s}', ' '.join(cells))
        out[tag] = dict(rows=rows, short=chk['short'], orphans=chk['orphans'])
        print('short', chk['short'], 'orphans', chk['orphans'])
    json.dump(out, open(os.path.join(HERE, 'rv2_kindfix.json'), 'w'), ensure_ascii=False, indent=1)
