#!/bin/bash
# 글자 시험 (2026-10-08 사용자 "글자가 좀 삐뚤빼뚤하네"): 실제 클라이언트 채팅에 시험 글 다섯 줄을 띄워 찍는다.
#   texttest.sh <포트> <서버폴더> <찍을폴더> <이름> [제목글꼴]
# 클라이언트는 켜서 들어와 있어야 한다. 바탕을 고르게 하려고 실명 효과 (세상이 검다) 를 건다. 분석은 texttest.py.
#   줄: 1 한국어 본문, 2 한국어 제목 (제목 글꼴), 3 영어 제목 대문자 (제목 글꼴), 4 숫자, 5 같은 글자 되풀이
set -u
R=$(cd "$(dirname "$0")/../../.." && pwd)
PORT=$1; SRV=$2; OUT=$3; NAME=$4; TF=${5:-souls:gothic_title}
cd "$R"
c() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
c effect give Tester minecraft:blindness infinite 0 true
c gamemode adventure Tester
tools/client/run_client.sh --do "$PORT" clearchat wait:0.5 >/dev/null 2>&1
c 'tellraw Tester {"text":"레딘 경비대가 차던 곧은 칼. 성벽 위의 병사들은 모두 안쪽을 보고 섰다."}'
c "tellraw Tester {\"text\":\"레딘 경비대 직검 · 수문장 흐롤프 · 탑옥 아래\",\"font\":\"$TF\"}"
c "tellraw Tester {\"text\":\"REDIN GUARD SWORD · HROLF THE WARDEN\",\"font\":\"$TF\"}"
c 'tellraw Tester {"text":"0123456789 0123456789 공격력 62 무게 3.0"}'
c 'tellraw Tester {"text":"HHHHHHHHHH nnnnnnnnnn 기기기기기기 다다다다다다 8888888888"}'
tools/client/run_client.sh --do "$PORT" slot:9 wait:1 key:t wait:1 "shot:$NAME" key:Escape wait:0.3 clearchat slot:1 2>&1 | grep SHOT
c effect clear Tester minecraft:blindness
