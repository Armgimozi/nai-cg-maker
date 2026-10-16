#!/usr/bin/env python3
"""0.3.6 광산 (Q1) 생성기 — 계약 tools/data/036/mine.json → content/mine.yml + 청사진 mine/levels/L1..L6.json.

    python3 -B tools/mine/gen_mine.py           # 만들기
    python3 -B tools/mine/gen_mine.py --check   # 만든 파일이 지금 계약·생성기와 같은지만 (다르면 1)

- content/mine.yml (자동 갱신 콘텐츠): mine.json 의 levels·ores·gems 를 그대로 옮긴다 (시안 정보 prototype 은 뺌).
  손잡이(재생 분·fx·자동 짓기)는 config.yml mine: 에 있다 (R §3-16).
- 청사진: tools/mine/levels.py 가 층마다 61×16×61 을 짓는다. 광석 종류별 블록 수 = levels[].vein_blocks,
  보석 노드 = levels[].gem_nodes. 손 닿는 광맥 수 한도는 없다 (계약 §0-2, 주인 늦은 결정).
- 검사 (만들 때마다): 층 6 · 광석 섞임(≥3종) · 블록 수 · 보석 노드 · 바닥 이어짐 · 광맥·보석이 손 닿는 곳(4.5)에 있고 보이는 면이 있음 ·
  장식·벽에 광석·보석·빈 광맥 블록 없음 · 빛(광맥 앞 ≥ 8, 바닥 ≥ 6, 홀 ≥ 12).
- 미리보기: tools/mine/out/L<n>.txt (위에서 본 평면 + 광맥 글자).
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import levels as LV  # noqa: E402

import yaml  # noqa: E402

CONTRACT = ROOT / 'tools/data/036/mine.json'
CONTENT = ROOT / 'plugin/src/main/resources/content/mine.yml'
BLUEPRINTS = ROOT / 'plugin/src/main/resources/mine/levels'
OUT = HERE / 'out'

HEADER = """\
# ─────────────────────────────────────────────────────────────────────────────
# mine.yml — 광산 (0.3.6). tools/mine/gen_mine.py 가 계약 tools/data/036/mine.json 에서 만든 파일.
# 자동 갱신 파일이다: 손대지 않았으면 jar 를 바꿀 때 새 판으로 바뀐다 (고친 파일은 그대로 두고 경고만).
#
# 층 6개는 모두 처음부터 열려 있다 — 레벨 조건이 어디에도 없다. 곡괭이 tier 는 캘 수 있는 광석(tier ≤ 곡괭이 + 1, 한 단계 위는 느림)과
# 빠르기만 정한다 (0.3.6.1).
# 층마다 광석·보석이 섞여 있다 (ore_weights · vein_blocks · gem_nodes). 광맥은 모두가 함께 쓴다: 누가 캐면 그 자리가 모두에게
# 빈 광맥(depleted_block)이 되고, config.yml mine.regen_minutes 뒤 다시 찬다 (광산 월드 사람 수만큼 빨리, 최대 4배).
#
# 블록(block)을 바꾸면 그 층을 다시 짓는다 (청사진은 @vein:<광석> · @gem:<보석> 글자라 그대로). 블록 12개는 서로 달라야 한다.
# 보석 6종 블록(좀벌레 돌)은 리소스팩이 네모난 보석 광석 그림으로 바꿔 보여 준다 (0.3.6.1 — 튀어나온 결정은 없앰). 다른 블록으로 바꾸면
# 팩 그림이 붙지 않아 바닐라 모습 그대로 보인다.
# 숫자·손잡이(재생 분·보석 확률·풍부한 광맥·광석 날아오기)는 config.yml mine: 에 있다.
# ─────────────────────────────────────────────────────────────────────────────
"""


def load():
    return json.loads(CONTRACT.read_text(encoding='utf-8'))


def content_doc(mine):
    lv = []
    for L in mine['levels']:
        x = {k: v for k, v in L.items() if k != 'prototype'}
        lv.append(x)
    ores = {k: dict(v) for k, v in mine['ores'].items()}
    gems = {k: dict(v) for k, v in mine['gems'].items()}
    return {'contract': mine['contract'], 'levels': lv, 'ores': ores, 'gems': gems}


def yaml_text(doc):
    body = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=None, width=140)
    return HEADER + body


def forbidden(mine):
    out = {v['block'] for v in mine['ores'].values()} | {v['block'] for v in mine['gems'].values()}
    out |= {L['depleted_block'] for L in mine['levels']}
    return out


def blueprint_text(bp):
    # 사람이 diff 를 읽을 수 있게: 층 하나 = 줄 61개 한 덩어리
    head = {k: v for k, v in bp.items() if k != 'layers'}
    s = json.dumps(head, ensure_ascii=False, indent=1)
    assert s.endswith('\n}')
    layers = ',\n'.join(' [\n' + ',\n'.join('  ' + json.dumps(r, ensure_ascii=False) for r in layer) + '\n ]' for layer in bp['layers'])
    return s[:-2] + ',\n "layers": [\n' + layers + '\n ]\n}\n'


# ── 검사 (청사진 JSON 만 보고) ───────────────────────────────────────────

def check_blueprint(bp, L, mine):
    errs = []
    W, H, D = bp['size']
    pal = bp['palette']
    ox, oy, oz = bp['origin']
    fy = L['floor_y']
    if [W, H, D] != [61, 16, 61]:
        errs.append('크기')
    if oy != fy - 2 or ox != -30 or oz != -30:
        errs.append('원점')
    box = L['box']
    if not (box[1] <= oy and oy + H - 1 <= box[4]):
        errs.append(f'청사진 높이가 층 상자 밖 {oy}..{oy + H - 1} {box}')
    cell = lambda x, y, z: bp['layers'][y][z][x]
    blocks = forbidden(mine)
    veins, gems = [], []
    for y in range(H):
        for z in range(D):
            for x in range(W):
                ch = cell(x, y, z)
                if ch in ' .':
                    continue
                b = pal[ch]
                if b.startswith('@vein:'):
                    veins.append((x, y, z, b[6:]))
                elif b.startswith('@gem:'):
                    gems.append((x, y, z, b[5:]))
                elif b.split('[')[0] in blocks:
                    errs.append(f'장식·벽에 광산 블록 {b} {(x, y, z)}')
    counts = {}
    for v in veins:
        counts[v[3]] = counts.get(v[3], 0) + 1
    if counts != L['vein_blocks']:
        errs.append(f'광맥 블록 수 {counts} ≠ {L["vein_blocks"]}')
    if len(counts) < 3:
        errs.append('광석이 섞이지 않음')
    if sorted(g[3] for g in gems) != sorted(L['gem_nodes']):
        errs.append(f'보석 노드 {sorted(g[3] for g in gems)} ≠ {sorted(L["gem_nodes"])}')
    full = set(LV.vlib.blockdata()['full'])

    def solid(x, y, z):
        if not (0 <= x < W and 0 <= y < H and 0 <= z < D):
            return False
        ch = cell(x, y, z)
        if ch in ' .':
            return False
        b = pal[ch]
        if b.startswith('@'):
            return True
        return b[10:].split('[')[0] in full

    def passable(x, y, z):
        ch = cell(x, y, z)
        if ch == '.':
            return True
        if ch == ' ':
            return False
        b = pal[ch]
        return not b.startswith('@') and b[10:].split('[')[0] in LV.PASSABLE

    def stand(x, z):
        return 0 <= x < W and 0 <= z < D and solid(x, 2, z) and passable(x, 3, z) and passable(x, 4, z)

    lx, _, lz = bp['markers'][[m['type'] for m in bp['markers']].index('landing')]['pos']
    sx, sz = int(math.floor(lx)) + 30, int(math.floor(lz)) + 30
    if not stand(sx, sz):
        errs.append('내리는 자리에 설 수 없음')
    seen = {(sx, sz)}
    q = [(sx, sz)]
    while q:
        x, z = q.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + dx, z + dz)
            if p not in seen and stand(*p):
                seen.add(p)
                q.append(p)
    floor = {(x, z) for x in range(W) for z in range(D) if stand(x, z)}
    if floor - seen:
        errs.append(f'이어지지 않은 바닥 {len(floor - seen)}칸')
    # 손 닿음: 보이는 면(공기 이웃) + 어떤 선 자리 눈(발 + 1.62)에서 블록 상자까지 ≤ 4.5
    unreachable = 0
    for (x, y, z, _id) in veins + gems:
        exposed = any(0 <= x + dx < W and 0 <= y + dy < H and 0 <= z + dz < D and passable(x + dx, y + dy, z + dz)
                      for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))
        ok = False
        if exposed:
            for (fx, fz) in seen:
                if abs(fx - x) > 6 or abs(fz - z) > 6:
                    continue
                ex = min(max(x, fx + 0.3), fx + 0.7) if not (fx <= x <= fx) else fx + 0.5
                ez = min(max(z, fz + 0.3), fz + 0.7) if not (fz <= z <= fz) else fz + 0.5
                ey = 3 + LV.EYE
                dx = max(x - ex, 0, ex - (x + 1))
                dy = max(y - ey, 0, ey - (y + 1))
                dz = max(z - ez, 0, ez - (z + 1))
                if math.sqrt(dx * dx + dy * dy + dz * dz) <= LV.REACH:
                    ok = True
                    break
        if not ok:
            unreachable += 1
            errs.append(f'손이 닿지 않음: {_id} 칸 {(x, y, z)} (월드 {(x + ox, y + oy, z + oz)}) 보이는 면 {exposed}')
    if unreachable:
        errs.append(f'손이 닿지 않는 광맥·보석 {unreachable}')
    types = [m['type'] for m in bp['markers']]
    lift = bp['markers'][types.index('lift')]['pos'] if 'lift' in types else None
    if lift != [0, fy + 1, 0]:
        errs.append(f'승강기 자리 {lift}')
    if ('office' in types) != bool(L['office']):
        errs.append('관리소 자리')
    return errs, {'veins': len(veins), 'gems': len(gems), 'floor': len(floor), 'unreachable': unreachable}


def preview(bp, L):
    W, H, D = bp['size']
    pal = bp['palette']
    letter = {'copper_ore': 'c', 'iron_ore': 'i', 'silver_ore': 's', 'gold_ore': 'g', 'mithril_ore': 'm', 'orichalcum_ore': 'o'}
    rows = []
    for z in range(D):
        row = []
        for x in range(W):
            col = [bp['layers'][y][z][x] for y in range(H)]
            ch = '#'
            veins = [pal[c][6:] for c in col if c not in ' .' and pal[c].startswith('@vein:')]
            gems = [pal[c] for c in col if c not in ' .' and pal[c].startswith('@gem:')]
            if gems:
                ch = '*'
            elif veins:
                ch = letter[veins[0]] if len(veins) == 1 else letter[veins[0]].upper()
            elif col[3] == '.' or (col[3] not in ' .' and pal[col[3]][10:].split('[')[0] in LV.PASSABLE):
                ch = '.'
            elif col[3] not in ' .' and not pal[col[3]].startswith('@'):
                b = pal[col[3]][10:].split('[')[0]
                ch = {'lodestone': 'L', 'lectern': 'O', 'barrel': 'b', 'oak_fence': '+', 'iron_bars': '+'}.get(b, '#')
            elif col[2] == ' ':
                ch = ' '
            row.append(ch)
        rows.append(''.join(row))
    head = [f"광산 {L['name']} ({L['id']}, 바닥 y={L['floor_y']}) — 위에서 본 평면 (위 = 북, x −30..30)",
            '# 바위  . 바닥  L 승강기  O 관리소  b 통  + 울타리  * 보석 노드  소문자 = 광맥 1칸 / 대문자 = 한 기둥에 2칸 이상',
            '글자: c 구리 · i 철 · s 은 · g 금 · m 미스릴 · o 오리하르콘  ·  ' + json.dumps(bp['stats']['vein_blocks'], ensure_ascii=False)]
    return '\n'.join(head + rows) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    mine = load()
    outputs = {CONTENT: yaml_text(content_doc(mine))}
    fb = forbidden(mine)
    errors = []
    for L in mine['levels']:
        lv = LV.build_level(L, mine['ores'], mine['gems'], fb)
        bp = lv.to_json()
        errs, st = check_blueprint(bp, L, mine)
        for e in errs:
            errors.append(f"L{L['n']}: {e}")
        text = blueprint_text(bp)
        json.loads(text)
        outputs[BLUEPRINTS / f"L{L['n']}.json"] = text
        outputs[OUT / f"L{L['n']}.txt"] = preview(bp, L)
        print(f"L{L['n']} {L['name']}: 광맥 {st['veins']} {bp['stats']['vein_blocks']} · 보석 {bp['stats']['gems']} · 바닥 {st['floor']}칸 · "
              f"손 안 닿음 {st['unreachable']} · 팔레트 {len(bp['palette'])}")
    if errors:
        for e in errors:
            print('  ✗', e)
        sys.exit(1)
    changed = []
    for path, text in outputs.items():
        old = path.read_text(encoding='utf-8') if path.exists() else None
        if old != text:
            changed.append(path)
            if not a.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
    if a.check:
        if changed:
            print('[광산 생성기] 다름: ' + ', '.join(str(p.relative_to(ROOT)) for p in changed))
            sys.exit(1)
        print('[광산 생성기] 같음')
    else:
        print('[광산 생성기] 씀: ' + (', '.join(str(p.relative_to(ROOT)) for p in changed) or '바뀐 것 없음'))


if __name__ == '__main__':
    main()
