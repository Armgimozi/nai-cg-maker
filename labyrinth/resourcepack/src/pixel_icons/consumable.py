"""consumable — 물약 10 (작은·보통·큰 + 강장제·정화·영약) · 두루마리 4 (14개).

빈 모듈 — 이 그룹 작업자가 채운다. ids: minor_healing_potion, healing_potion, greater_healing_potion,
minor_mana_potion, mana_potion, greater_mana_potion, fortitude_tonic, fury_tonic, cleansing_draught, elixir_of_renewal,
return_scroll, stat_reset_scroll, class_change_scroll, enhance_protection_scroll.
같은 style(potion_small·potion·potion_large·scroll)은 같은 틀 + items.yml 팔레트 색 (ctx.acc = 물약 색).
그림 규칙·지도 문법·등록 API 는 pixel_icons/__init__.py 머리말. 미리보기·검사:
    /opt/packvenv/bin/python $IC/tools/preview.py consumable       (8배 옛/새 · 핫바 3배 · 인벤토리 9×4)
    /opt/packvenv/bin/python $IC/tools/check_rules.py consumable   (16px · 6~16색 · 반투명 0 · 검은 외곽선 0 · speckle)
    $IC/tools/originality.sh consumable                              (바닐라와 겹침 — 팔기 전 반드시 통과)
  ($IC = 작업 메모 frame.md 에 적힌 scratchpad/ic362)
"""
from __future__ import annotations

from . import E, add_ramps, register, register_maps  # noqa: F401  (paint, Ctx, Art, ramp, edge, highlight, sparkle, tier_pips …)

# 예 (style 하나를 그 style 의 아이템 전부에, 팔레트로 색이 갈리게):
#   from . import paint, Ctx
#   @register('potion_small')
#   def _(ctx: Ctx):
#       return paint(ctx.slots(), MAP)          # ctx.main / ctx.acc = items.yml 팔레트 램프
