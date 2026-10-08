#!/bin/bash
# 글 시험 한 바퀴: <jar> 로 서버를 다시 켜고 GUI 배율 4·3·2 로 클라이언트를 켜 texttest.sh 로 찍고 measure.py 로 잰다.
#   textround.sh <포트> <서버폴더> <jar> <팩 폴더 (잴 때 글꼴)> <찍을폴더> <앞머리>
# 화면은 1920x1080. 서버·클라이언트는 이 스크립트가 켜고 끈 것만 끈다.
set -u
R=$(cd "$(dirname "$0")/../../.." && pwd)
PORT=$1; SRV=$2; JAR=$3; PACK=$4; OUT=$5; P=$6
V="$R/pack/variants/mood2_refined"
cd "$R"
tools/client/devserver.sh --stop "$SRV"
PAPER_JAR=${PAPER_JAR:-} tools/client/devserver.sh "$PORT" "$SRV" "$JAR" | tail -1
for G in ${SCALES:-4 3 2}; do
  MC_SIZE=1920x1080 MC_GUI_SCALE=$G MC_OPTIONS="textBackgroundOpacity:1.0" tools/client/run_client.sh --start "$PORT" "$OUT" | tail -1
  tools/client/run_client.sh --do "$PORT" join wait:10 | grep -E "팩|오류|rror"
  "$V/texttest.sh" "$PORT" "$SRV" "$OUT" "${P}_g$G"
  tools/client/run_client.sh --stop "$PORT"
  python3 "$V/measure.py" "$OUT/${P}_g$G.png" "$G" "$PACK"
done
