"""crafted — 만든 물건: 강화석 3 · 도안 · 열쇠 2 · 휘장 2 · 왕관 2 · 칼날 · 종 · 진자 · 판 · 기름병 · 낡은 쪽지 (16개).

빈 모듈 — 이 그룹 작업자가 채운다. ids: lesser/greater/supreme_enhance_stone, blueprint, vault_key, floodgate_key,
foreman_badge, alpha_moss_crest, frozen_crown_shard, mycelium_crown, executioner_edge, funeral_bell_shard,
regulator_pendulum, verdigris_plate, clock_oil, old_page.
도안(blueprint)은 Art(img=양피지, layers=[봉인]) 을 돌려준다 — 봉인은 회색만으로 (플러그인이 희귀도 색으로 tint).
그림 규칙·지도 문법·등록 API 는 pixel_icons/__init__.py 머리말. 미리보기·검사:
    /opt/packvenv/bin/python $IC/tools/preview.py crafted       (8배 옛/새 · 핫바 3배 · 인벤토리 9×4)
    /opt/packvenv/bin/python $IC/tools/check_rules.py crafted   (16px · 6~16색 · 반투명 0 · 검은 외곽선 0 · speckle)
    $IC/tools/originality.sh crafted                              (바닐라와 겹침 — 팔기 전 반드시 통과)
  ($IC = 작업 메모 frame.md 에 적힌 scratchpad/ic362)
"""
from __future__ import annotations

from . import E, add_ramps, register, register_maps  # noqa: F401  (paint, Ctx, Art, ramp, edge, highlight, sparkle, tier_pips …)

# 예 (style 하나를 그 style 의 아이템 전부에, 팔레트로 색이 갈리게):
#   from . import paint, Ctx
#   @register('rune_stone')
#   def _(ctx: Ctx):
#       return paint(ctx.slots(), MAP)          # ctx.main / ctx.acc = items.yml 팔레트 램프
