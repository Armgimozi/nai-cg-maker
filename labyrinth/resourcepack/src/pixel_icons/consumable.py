"""consumable — 물약 10 · 두루마리 4 (14개, 0.3.6.2 방향 C 16px 손그림).

그림 규칙·지도 문법·등록 API 는 pixel_icons/__init__.py 머리말. 램프 이름은 모두 'cn_' 로 시작한다 (add_ramps).
색은 아이템마다 items.yml texture.palette 에서 골라 R3 램프(그림자 차갑게 · 빛 따뜻하게)로 다시 짰다 (물약 본색 = 팔레트 가운데 색).
style 로 등록한다 (potion_small · potion · potion_large · scroll 은 이 그룹 아이템만 쓴다). 아이템마다 다른 색·표시는
아래 표(POTION · SCROLLS)에서 아이템 id 로 고른다. 표에 없는 새 아이템은 그 style 의 틀 + 팔레트 강조색으로 그려진다.
규칙 검사는 팩 빌드 때 validate.py 가 한다.

집안 (같은 틀 + 아이템마다 다른 색·표시, R6)
  물약 틀 셋 = 둥근 플라스크 + 짧은 목. 크기가 단계다: 작은 8칸 → 보통 10칸 → 큰 12칸.
    유리: 'cn_glass' 램프 (0.3.6.2 심사: 한 단계 어둡게 — 밝은 쪽 테두리가 칸 회색에 묻히고 빈 유리가 도자기처럼 무거웠다).
          테두리는 edge() (위·왼쪽 2, 아래·오른쪽 0), 빈 위쪽 유리 3 + 오른쪽 그늘 2 + 왼쪽 위 흰 반짝임 두 칸.
          물: 평평한 덩이(d) + 오른쪽·바닥 그늘(c) + 윗면 한 줄(e) + 윗면 왼쪽 빛(f).
    작은 물약 (하급 치유·하급 마나): 코르크 + 목, 물 색을 한 단계 밝게 (보통 물약과 크기만이 아니라 색으로도 갈린다).
    큰 물약 (상급 치유·상급 마나·재생의 비약): 코르크 대신 물 색 결정 마개 + 놋쇠 목테 — 한눈에 "비싼 병".
  강장제 둘 (작은 물약 style 이지만 병 모양이 다르다 — 물약과 헷갈리지 않게):
    강인함 = 어깨가 각진 네모 병 + 진한 호박색 · 분노 = 키 크고 가는 병 + 불꽃빛 밀랍 마개 + 노랑·주황.
  정화의 물약: 보통 물약 + 물 속에서 오르는 거품 두 덩이 (2×2, 흰 + 기호가 아니다).
  재생의 비약: 큰 물약 + 금 목테 (떠 있는 반짝이 없음).
  두루마리 = 비스듬히 말아 놓은 종이 (왼쪽 아래 → 오른쪽 위, 위 끝에 말린 면). 가운데를 감은 끈 + 2×2 밀랍 봉인의 색이 종류다:
    귀환 = 베이지 종이 + 초록 끈 · 망각 = 쪽빛 종이 + 연보라 끈 · 전직 = 옅은 하늘빛 종이 + 파란 끈 · 강화 보호 = 크림빛 종이 + 금 끈.
"""
from __future__ import annotations

from . import E, add_ramps, edge, paint, register

add_ramps({
    'cn_glass': ['#1e2c40', '#34486a', '#4e6a8a', '#7896b4', '#a2bcd2', '#d8eaf4'],   # 물약 유리 (공용 glass 보다 한 단계 어둡게)
    # 마개 · 목테
    'cn_cork': ['#2a1610', '#4a2a18', '#76472a', '#9e6a3e', '#c4925a', '#e2ba80'],
    'cn_brass': ['#2e1a10', '#563418', '#86562a', '#b4803c', '#dcae5c', '#f6dc96'],
    'cn_wax': ['#4a0e08', '#86200c', '#c43c12', '#ee6a1c', '#ffa03a', '#ffd070'],      # 분노의 강장제 불꽃빛 밀랍 마개
    # 물 (3번 칸 = 팔레트 가운데 색)
    'cn_heal_s': ['#6e1428', '#a8202c', '#d83a3a', '#f06a56', '#ffa88a', '#ffd4c4'],    # #d83a3a · #ff9a8a (한 단계 밝게)
    'cn_heal': ['#420c20', '#7c1626', '#b82a2c', '#e84a3a', '#ff7c5c', '#ffb898'],      # #e84a3a · #ffb0a0
    'cn_heal_l': ['#3e0624', '#82102a', '#c41c30', '#ff3b3b', '#ff7860', '#ffc0a0'],    # #ff3b3b · #ffc0a0
    'cn_mana_s': ['#1e2e82', '#2a52b4', '#3a7ad8', '#62a2ee', '#9ac8ff', '#cce4ff'],    # #3a7ad8 · #9ac8ff (한 단계 밝게)
    'cn_mana': ['#16164a', '#203a8e', '#3060c4', '#4a8ae8', '#78b4f6', '#b0d8ff'],      # #4a8ae8 · #b0d8ff
    'cn_mana_l': ['#140e52', '#1e1e96', '#2c44d8', '#3a6aff', '#7898ff', '#c0d0ff'],    # #3a6aff · #c0d0ff
    'cn_fort': ['#2e140c', '#52260e', '#7a3e12', '#a05a1a', '#c87e2a', '#e8a848'],      # 진한 호박색 (#a8743c)
    'cn_fury': ['#6a2a08', '#b05010', '#e88018', '#ffb020', '#ffd650', '#fff09a'],      # 노랑·주황 (#e0571d · #ffb04a)
    'cn_clean': ['#0e2e30', '#1a6a4a', '#30a066', '#5ad88a', '#90ecaa', '#c8ffd8'],     # #5ad88a · #c8ffd8
    'cn_elix': ['#2e0c3a', '#6a1a6a', '#a43aa8', '#d85ad8', '#f08ee6', '#ffc8ff'],      # #d85ad8 · #ffc8ff
    # 두루마리 종이 · 끈
    'cn_parch': ['#4a3424', '#6e5a40', '#9a8462', '#c8b48a', '#e2d6b0', '#f4eed6'],     # 귀환 종이 #c8b48a · #efe4c8
    'cn_green': ['#1e3018', '#355722', '#577c32', '#7fa043', '#a8c862', '#d8ec98'],     # 귀환 끈 #7fa043
    'cn_indigo': ['#14101e', '#221e44', '#2e2e62', '#463e80', '#6a5aa0', '#8e80c0'],    # 망각 종이 #2a2a5a · #6a5aa0
    'cn_violet': ['#4a2a7a', '#6e44a8', '#9a6ad0', '#c09aec', '#dcc4ff', '#f4ecff'],    # 망각 끈 (연보라)
    'cn_cparch': ['#3a4668', '#5e6e94', '#8698bc', '#aec0dc', '#cfe0ff', '#eef4ff'],    # 전직 종이 #cfe0ff
    'cn_cblue': ['#0e1226', '#1c2850', '#26366a', '#3e5ca8', '#7fb2ff', '#c4dcff'],     # 전직 끈 #26366a · #7fb2ff
    'cn_pparch': ['#5a4630', '#8a7254', '#b8a07a', '#e0cca2', '#f4e6c4', '#fff8e8'],    # 보호 종이 #fff4d6
    'cn_cgold': ['#3a1e0a', '#5e3610', '#8a5418', '#b07a24', '#d8a440', '#f0cc70'],     # 보호 끈 (진한 금 — 크림 종이 위에서 보이게)
})


def grid(text):
    """여러 줄 문자열 → 16×16 지도 (모자란 칸·줄은 비움). 16글자를 넘는 줄이 있으면 오류 — 지도 오타를 바로 잡는다."""
    out = [ln.strip() for ln in text.strip('\n').split('\n')]
    if len(out) > 16 or any(len(ln) > 16 for ln in out):
        raise ValueError(f'bad consumable map: {out!r}')
    out = [ln.ljust(16, '.') for ln in out]
    while len(out) < 16:
        out.append(E)
    return out


# ═════════ 물약 틀: 채움 지도(유리 4 · 코르크 D · 결정 마개 e · 목테 r) → edge() → 안쪽 지도(빈 유리 3·2 · 물 · 빛 · 마개 무늬) ═════════
# 슬롯: main = 유리('cn_glass'), acc = 물, acc2 = 코르크, acc3 = 목테(놋쇠·금) 또는 밀랍 마개.

SMALL = grid("""
................
................
................
................
......DDDD
......DDDD
.......44
......4444
.....444444
....44444444
....44444444
....44444444
....44444444
.....444444
......4444
""")
SMALL_IN = grid("""
................
................
................
................
......CEEA
......CCAA
.......20
.......33
......w332
.....w33332
.....feeeee
.....dddddc
.....dddddc
......cccc
""")

MED = grid("""
................
................
......DDDD
......DDDD
.......44
......4444
....44444444
....44444444
...4444444444
...4444444444
...4444444444
...4444444444
....44444444
....44444444
......4444
""")
MED_IN = grid("""
................
................
......CEEA
......CCAA
.......20
.......33
......w332
.....w333332
....feeeeeee
....dddddddc
....dddddddc
....dddddddc
.....ddddcc
......cccc
""")

LARGE = grid("""
................
......eeee
......eeee
.....rrrrrr
.....444444
...4444444444
...4444444444
..444444444444
..444444444444
..444444444444
..444444444444
..444444444444
...4444444444
...4444444444
.....444444
""")
LARGE_IN = grid("""
................
......dffe
......ddcc
.....rttrrp
................
.....w33332
....w33333332
...feeeeeeeee
...dddddddddc
...dddddddddc
...dddddddddc
...dddddddddc
....ddddddcc
.....cccccc
""")

# 강인함의 강장제: 어깨가 각진 네모 병 (코르크) — 둥근 물약과 실루엣이 다르다
FORT = grid("""
................
................
................
......DDDD
......DDDD
.......44
.....444444
....44444444
....44444444
....44444444
....44444444
....44444444
....44444444
....44444444
.....444444
""")
FORT_IN = grid("""
................
................
................
......CEEA
......CCAA
.......20
.....w3332
....w3333332
....feeeeeee
....dddddddc
....dddddddc
....dddddddc
....dddddddc
....dccccccc
""")
# 분노의 강장제: 키 크고 가는 병 + 불꽃빛 밀랍 마개(acc3)
FURY = grid("""
................
.......rr
......rssr
......rsrr
.......44
.......44
......4444
......4444
.....444444
.....444444
.....444444
.....444444
.....444444
.....444444
......4444
""")
FURY_IN = grid("""
................
.......tu
......tus
......tss
.......20
.......33
......w332
......w332
.....feeeee
.....dddddc
.....dddddc
.....dddddc
.....dddddc
......dccc
""")

# 정화의 물약: 물 속에서 오르는 거품 두 덩이 (2×2 — 한 점 반짝임이나 + 기호가 아니다)
BUBBLES = grid("""
................
................
................
................
................
................
................
................
................
........ff
........fe
................
.....fe
.....ee
""")

# ═════════ 아이템별 색 ═════════
POTION = {
    'minor_healing_potion': 'cn_heal_s', 'minor_mana_potion': 'cn_mana_s',
    'fortitude_tonic': 'cn_fort', 'fury_tonic': 'cn_fury',
    'healing_potion': 'cn_heal', 'mana_potion': 'cn_mana', 'cleansing_draught': 'cn_clean',
    'greater_healing_potion': 'cn_heal_l', 'greater_mana_potion': 'cn_mana_l', 'elixir_of_renewal': 'cn_elix',
}
TONIC_BOTTLE = {'fortitude_tonic': (FORT, FORT_IN, 'cn_brass'), 'fury_tonic': (FURY, FURY_IN, 'cn_wax')}

NAMES = {
    'minor_healing_potion': '하급 치유 물약', 'healing_potion': '치유 물약', 'greater_healing_potion': '상급 치유 물약',
    'minor_mana_potion': '하급 마나 물약', 'mana_potion': '마나 물약', 'greater_mana_potion': '상급 마나 물약',
    'fortitude_tonic': '강인함의 강장제', 'fury_tonic': '분노의 강장제', 'cleansing_draught': '정화의 물약',
    'elixir_of_renewal': '재생의 비약', 'return_scroll': '귀환 주문서', 'stat_reset_scroll': '망각의 주문서',
    'class_change_scroll': '전직의 두루마리', 'enhance_protection_scroll': '강화 보호 주문서',
}


def _flask(fill, inner):
    """물약 style 하나 → 그림 함수. 채움 → edge() (유리·코르크·마개·목테가 저마다 자기 램프로 테두리) → 안쪽 지도."""
    def draw(ctx):
        f, i, a3 = fill, inner, 'cn_brass'
        if ctx.iid in TONIC_BOTTLE:
            f, i, a3 = TONIC_BOTTLE[ctx.iid]
        if ctx.iid == 'elixir_of_renewal':
            a3 = 'gold'
        s = {'main': 'cn_glass', 'acc': POTION.get(ctx.iid, ctx.acc), 'acc2': 'cn_cork', 'acc3': a3}
        img = paint(s, f)
        img = edge(img, [s['main'], s['acc'], s['acc2'], s['acc3']])
        img = paint(s, i, img=img)
        if ctx.iid == 'cleansing_draught':
            img = paint(s, BUBBLES, img=img)
        return img
    return draw


register('potion_small', _flask(SMALL, SMALL_IN))
register('potion', _flask(MED, MED_IN))
register('potion_large', _flask(LARGE, LARGE_IN))

# ═════════ 두루마리: 비스듬히 말아 놓은 종이 + 감은 끈(acc) + 2×2 밀랍 봉인(acc2) ═════════
# 종이 = 위·왼쪽 빛 4 · 몸 3 · 그늘 2·1 (테두리는 edge()), 오른쪽 위 끝 = 말린 면 (2·1).
SCROLL = grid("""
................
............222
...........24321
..........244210
.........2443210
........24443210
.......24443321
......24443321
.....24443321
....24443321
...24443321
..244433210
.2444332210
.233332210
..2222110
""")
# 끈은 두루마리 축에 수직으로 감긴다 (↘), 봉인은 끈 가운데에.
BAND = grid("""
................
................
................
................
................
.......d
.......dd
........dc
.........DEc
.........CDbb
..........bb
""")
SCROLLS = {
    'return_scroll': {'main': 'cn_parch', 'acc': 'cn_green', 'acc2': 'cn_green'},
    'stat_reset_scroll': {'main': 'cn_indigo', 'acc': 'cn_violet', 'acc2': 'cn_violet'},
    'class_change_scroll': {'main': 'cn_cparch', 'acc': 'cn_cblue', 'acc2': 'cn_cblue'},
    'enhance_protection_scroll': {'main': 'cn_pparch', 'acc': 'cn_cgold', 'acc2': 'cn_cgold'},
}


@register('scroll')
def _scroll(ctx):
    s = SCROLLS.get(ctx.iid) or {'main': 'cn_parch', 'acc': ctx.acc, 'acc2': ctx.acc}
    img = paint(s, SCROLL)
    img = edge(img, [s['main'], s['acc'], s['acc2']])
    return paint(s, BAND, img=img)
