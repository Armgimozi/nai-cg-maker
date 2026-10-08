#!/bin/bash
# M0 실제 클라이언트 점검 그림 묶음 (DESIGN.md 13.4 가운데 M0 에 있는 것). 서버는 debug.test-mode 여야 한다.
#   m0_shots.sh <포트> <찍을폴더> [서버폴더]
# 시험 서버가 없으면: devserver.sh <포트> <서버폴더> 로 먼저 켠다 (Tester 에게 op 를 준다).
# 서버폴더를 주면 서버 설정을 잠깐 바꿔야 하는 점검(9 급류 회전 구르기, 13 설정 단계 팩 보내기)도 하고 설정을 되돌린다.
# 구르기 모습 셋을 장면 여러 장으로 견주는 것은 roll_strip.sh (dist/screenshots/roll/).
# 채팅은 숨긴다 (chatScale:0). 시험 줄([T] ...)과 바닐라 명령 결과가 그림에 남지 않는다 (클라이언트 기록에는 남는다).
# 처음에 Tester 의 인벤토리를 비운다 (지난 점검에서 받은 아이템이 남아 있으면 그림을 가린다).
#
# 그림마다 무엇을 보는지 (괄호는 13.4 번호):
#   01_join_test_room_hud            (1·2·10·11) 팩이 실렸다, 다크 소울 HUD (왼쪽 위 체력·온기·스태미나 막대 꽉 참,
#                                    오른쪽 아래 소울 상자), 하트·허기·경험치 막대·레벨 숫자 없음,
#                                    시험 방 바이옴(souls:redin)의 안개·하늘·재 입자
#   02_sprint_stamina_drain          (2) 달리는 중 왼쪽 위 스태미나 막대가 준다
#   03_roll_third_person             구르기 (온 블록 바닥, 3인칭 뒤, 기본 모습 tumble): 진짜 몸 대신 관절 대역이 어깨로 구른다.
#                                    0.2초 뒤라 뛰어드는 중
#   03b_roll_slab_third_person       판석(아래 반 블록) 위 구르기: 대역이 판석 바닥 위로 구른다 (가장 낮은 점이 발밑 높이)
#   04_exhausted_vs_sprint           (5) 스태미나 0 → 허기 6 으로 달리기가 막힌다 (앞으로 걷기만, 시야가 넓어지지 않는다)
#   05_dialog                        (4) 휴식 창 꼴: 단추 글 양피지색, 제목 옆 경고 단추는 녹슨 쇠판
#   06_offhand_shield_after_strip    (7) 막기 성분을 뗀 도구 + 왼손 방패 → 같은 우클릭으로 왼손 방패를 든다
#   07b_you_died_early               (3) 죽고 0.5초: 단추가 아직 꺼져 있다, 몸이 사라지는 연기는 재 부스러기 몇 점
#   07_you_died                      (3) 사망 화면: 새빨간 YOU DIED 한 번, 회색 "일어선다", 점수 줄·밑 문구 없음
#   09_guard_custom_model            (6) 맞춤 모형 souls:test_guard 로 막는 1인칭
#   09b_guard_custom_model_front     (6) 같은 자세를 앞에서 (3인칭)
#   09c_guard_custom_model_idle      (6) 막지 않을 때 (3인칭 앞)
#   10_swing_mid                     (8) swing_animation 12틱: 팔이 아직 휘두르는 중
#   10b_attack_indicator             (8) attack_speed 1.0: 조준점 밑 회복 표시기
#   12_hud_damaged                   (10) 맞은 직후 체력 막대 (잃은 몫이 바랜 양피지빛으로 잠깐 남는다)
#   13_spin_third_person             (9) 서버폴더가 있을 때: visual: spin (급류 회전). 구르기로 보이지 않아 대비책으로만 둔다
#   14_configure_join, 14_configure_join.txt
#                                    (13) 서버폴더가 있을 때: send-at: configure 로 다시 들어온 화면과
#                                    "팩을 다시 실은 줄이 세계에 들어간 줄보다 먼저" 인 기록
# 13.4 의 12 (몹 가죽) 는 M0 에 없다 (M4).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 2 ] || { echo "쓰는 법: m0_shots.sh <포트> <찍을폴더> [서버폴더]" >&2; exit 2; }
PORT=$1
OUT=$2
SRVDIR=${3:-}
export MC_OPTIONS="${MC_OPTIONS:-chatScale:0.0}"
RC="$HERE/run_client.sh"
DEV="$HERE/devserver.sh"

set_cfg() {   # set_cfg <키 정규식> <새 줄>: 서버의 플러그인 설정 한 줄을 바꾸고 다시 읽힌다
  local cfg="$SRVDIR/plugins/Soulslike/config.yml"
  sed -i "s|^\( *\)$1:.*|\1$2|" "$cfg"
  "$DEV" --cmd "$SRVDIR" souls reload
  sleep 1
}

"$RC" --start "$PORT" "$OUT" || exit 1
trap '"$RC" --stop "$PORT" >/dev/null 2>&1' EXIT

"$RC" --do "$PORT" \
  join "cmd:/clear" "cmd:/soulstest heal" "cmd:/souls tp room" wait:8 shot:01_join_test_room_hud \
  down:ctrl+w wait:1.5 shot:02_sprint_stamina_drain up:ctrl+w wait:1 \
  "cmd:/soulstest heal" "cmd:/souls tp lane" wait:1.5 key:F5 wait:0.5 \
  down:w hold:Shift_L:0.1 wait:0.15 shot:03_roll_third_person up:w wait:1 \
  "cmd:/soulstest heal" "cmd:/souls tp slab" wait:1.5 \
  down:w hold:Shift_L:0.1 wait:0.25 shot:03b_roll_slab_third_person up:w wait:1 key:F5 key:F5 wait:0.3 \
  "cmd:/souls tp room" wait:1 "cmd:/soulstest stamina set 0" wait:0.3 \
  down:ctrl+w wait:1.2 shot:04_exhausted_vs_sprint up:ctrl+w hold:s:2 \
  "cmd:/soulstest heal" "cmd:/soulstest dialog" wait:1.2 shot:05_dialog close wait:0.5 \
  "cmd:/soulstest guard strip" "cmd:/item replace entity @s weapon.offhand with minecraft:shield" wait:0.8 \
  mdown:right wait:0.8 shot:06_offhand_shield_after_strip mup:right wait:0.3 \
  "cmd:/item replace entity @s weapon.offhand with minecraft:air" \
  "cmd:/soulstest guard empty" wait:2 \
  mdown:right wait:0.8 shot:09_guard_custom_model key:F5 key:F5 wait:0.6 shot:09b_guard_custom_model_front \
  mup:right wait:0.6 shot:09c_guard_custom_model_idle key:F5 wait:0.3 \
  "cmd:/soulstest swing 12 1.0" wait:1.5 mouse:left wait:0.15 shot:10_swing_mid wait:0.15 shot:10b_attack_indicator wait:1.2 \
  "cmd:/soulstest hit 140" wait:0.15 shot:12_hud_damaged wait:1 \
  "cmd:/soulstest kill" wait:0.5 shot:07b_you_died_early wait:1.3 shot:07_you_died \
  respawn wait:2 "cmd:/soulstest heal" || exit 1

if [ -n "$SRVDIR" ]; then
  # 9: 급류 회전 구르기 (3인칭)
  orig_visual=$(grep -E '^ +visual:' "$SRVDIR/plugins/Soulslike/config.yml" | head -n 1 | sed 's/^ *visual: *//')
  set_cfg "visual" "visual: spin"
  "$RC" --do "$PORT" "cmd:/souls tp lane" wait:1.5 key:F5 wait:0.4 \
    down:w hold:Shift_L:0.1 wait:0.15 shot:13_spin_third_person up:w wait:1 key:F5 key:F5 || exit 1
  set_cfg "visual" "visual: ${orig_visual:-tumble}"

  # 13: 설정 단계에서 팩 보내기. 클라이언트를 끄고 새로 켜서 들어온다
  set_cfg "send-at" "send-at: configure"
  "$RC" --stop "$PORT" >/dev/null 2>&1
  "$RC" --start "$PORT" "$OUT" || exit 1
  "$RC" --do "$PORT" join wait:8 shot:14_configure_join || exit 1
  LOG="${SOULS_CLIENT_HOME:-$HOME/.cache/souls-client}/run/$PORT/client.log"
  {
    echo "13.4 의 13: pack.send-at: configure 로 다시 들어온 클라이언트 기록 (차례대로)."
    echo "팩을 다시 싣는 줄(Reloading ResourceManager ... server)이 세계에 들어온 줄(Loaded N advancements)보다 먼저면"
    echo "설정 단계에서 받고 실은 것이다."
    grep -a -n -E 'Connecting to|Reloading ResourceManager|Loaded [0-9]+ advancements|Disconnect|kicked' "$LOG" | cut -c1-200
  } > "$OUT/14_configure_join.txt"
  set_cfg "send-at" "send-at: join"
fi
echo "끝: $OUT"
