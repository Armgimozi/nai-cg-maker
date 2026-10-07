#!/bin/bash
# M0 실제 클라이언트 점검 화면 묶음 (DESIGN.md 13.4 의 1·2·3·5·6 을 눈으로 볼 그림). 서버는 debug.test-mode 여야 한다.
#   m0_shots.sh <포트> <찍을폴더>
# 시험 서버가 없으면: devserver.sh <포트> <서버폴더> 로 먼저 켠다 (Tester 에게 op 를 준다).
# 그림마다 무엇을 보는지:
#   01_hud              팩이 실렸다(형식 75), 경험치 자리 스태미나 막대가 꽉 차 있고 레벨 숫자가 없다, 허기 칸이 보이지 않는다
#   02_sprint           달리는 중 막대가 준다
#   03_after_sprint     멈춘 뒤 (회복 지연)
#   04_roll             F 구르기 (뒷걸음)
#   05_exhausted        스태미나 0 → 허기 6 으로 달리기가 막힌다 (앞으로 걷기만, 시야가 넓어지지 않는다)
#   06_guard            껍데기 아이템 + 막기 성분의 막는 자세 (우클릭을 누른 채, 1인칭)
#   06b_guard_front     같은 자세를 앞에서 (F5 두 번)
#   07_died_early       죽고 0.6초 (단추가 아직 꺼져 있다)
#   08_died             사망 화면: 핏빛 YOU DIED, "일어선다", 점수 줄 없음
#   09_respawned        되살아난 뒤
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 2 ] || { echo "쓰는 법: m0_shots.sh <포트> <찍을폴더>" >&2; exit 2; }
exec "$HERE/run_client.sh" "$1" "$2" \
  join clearchat wait:0.3 shot:01_hud \
  down:ctrl+w wait:1.5 shot:02_sprint up:ctrl+w \
  wait:0.4 shot:03_after_sprint \
  key:f wait:0.25 shot:04_roll \
  wait:1 "cmd:/soulstest stamina set 0" wait:0.3 clearchat \
  down:ctrl+w wait:1.2 shot:05_exhausted up:ctrl+w hold:s:2.5 \
  "cmd:/soulstest heal" "cmd:/soulstest guard empty" wait:0.5 clearchat \
  mdown:right wait:0.6 shot:06_guard key:F5 key:F5 wait:0.5 shot:06b_guard_front mup:right key:F5 \
  "cmd:/soulstest kill" wait:0.6 shot:07_died_early wait:1.4 shot:08_died \
  respawn wait:2 clearchat wait:0.3 shot:09_respawned
