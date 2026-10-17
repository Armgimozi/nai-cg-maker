"""arcane — 조각·핵·결정·가루·정수·룬석·진주·잉크병 (16개).

시작점: C 시안의 불씨 혼(ember_soul) 1개. 나머지 15개는 이 파일에 새로 그린다
(chrono_dust·abyss_ichor·dim/labyrinth/radiant/primordial_essence·silk_queen_spinneret·ink_essence·brine_pearl·
brood/forge/tuning_fork_core·warden_heartwood·forbidden_seal·gatekeeper_rune).
그림 규칙·지도 문법·등록 API 는 pixel_icons/__init__.py 머리말. 미리보기·검사:
    /opt/packvenv/bin/python $IC/tools/preview.py arcane       (8배 옛/새 · 핫바 3배 · 인벤토리 9×4)
    /opt/packvenv/bin/python $IC/tools/check_rules.py arcane   (16px · 6~16색 · 반투명 0 · 검은 외곽선 0 · speckle)
    $IC/tools/originality.sh arcane                              (바닐라와 겹침 — 팔기 전 반드시 통과)
  ($IC = 작업 메모 frame.md 에 적힌 scratchpad/ic362)
"""
from __future__ import annotations

from . import E, add_ramps, register_maps  # noqa: F401  (그룹 작업자: register, paint, Ctx, ramp, edge, highlight, sparkle …)


def icon(iid, name, slots, *maps, legend=None):
    """C 시안의 icon(): 아이템 id · 한글 이름(설명용) · slot→램프 이름 · 지도들."""
    NAMES[iid] = name
    return register_maps(iid, slots, *maps, legend=legend, group='arcane')


NAMES: dict[str, str] = {}

add_ramps({
    'soul': ['#3a0c06', '#7a1e08', '#c03c0e', '#ee7418', '#ffae36', '#ffe486'],
})

# ═════════════════════════════ 불씨 혼 (C 시안) ═════════════════════════════
icon('ember_soul', '불씨 혼', {'main': 'soul'}, [
    E,                       # 불씨 혼: 기울어진 불 결정 조각 + 둘레의 불티 두 점
    '.........3......',
    '........241.....',
    '.......2451.....',
    '...4...24531..5.',
    '......245431....',
    '......254321....',
    '.....2454321....',
    '.....2554321....',
    '.....255431.....',
    '.....254321.....',
    '......24321.....',
    '......2321......',
    '.......10.......',
    E, E,
])
