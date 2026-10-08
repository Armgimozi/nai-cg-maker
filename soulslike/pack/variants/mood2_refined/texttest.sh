#!/bin/bash
# 글 시험 (삐뚤빼뚤 재기): 채팅에 빈 줄을 사이에 두고 시험 줄 다섯 (한글 본문, 한글 제목, 영어 로마 대문자 제목, 숫자, 영어 본문) 을 띄우고 찍는다.
#   texttest.sh <포트> <서버폴더> <찍을폴더> <이름>
# 클라이언트는 MC_OPTIONS="textBackgroundOpacity:1.0" (채팅 바탕을 검게, 잴 때 바탕이 고르게) 로 켜 두고 들어와 있어야 한다.
set -u
R=$(cd "$(dirname "$0")/../../.." && pwd)
PORT=$1; SRV=$2; OUT=$3; NAME=$4
cd "$R"
con() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
# 팩을 다시 싣는 동안 (붉은 Mojang 화면) 은 기다린다
for _ in $(seq 40); do
  tools/client/run_client.sh --do "$PORT" "shot:_settle" >/dev/null 2>&1
  python3 -c "
import sys; import numpy as np; from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('RGB').resize((16, 9))).reshape(-1, 3).astype(int)
red = int(((a[:, 0] > 200) & (a[:, 1] < 80) & (a[:, 2] < 90)).sum())
sys.exit(1 if red > 60 else 0)" "$OUT/_settle.png" && break
  sleep 3
done
rm -f "$OUT/_settle.png"
tools/client/run_client.sh --do "$PORT" wait:3 clearchat wait:0.3 >/dev/null
con 'tellraw Tester {"text":"레딘 경비대가 차던 곧은 칼. 성벽 위의 병사들은 모두 안쪽을 보고 섰다."}'
con 'tellraw Tester {"text":" "}'
con 'tellraw Tester {"text":"레딘 경비대 직검 · 수문장 흐롤프 · 탑옥 아래","font":"souls:title"}'
con 'tellraw Tester {"text":" "}'
con 'tellraw Tester {"text":"REDIN GUARD SWORD · GATEWARDEN HROLF","font":"souls:title"}'
con 'tellraw Tester {"text":" "}'
con 'tellraw Tester {"text":"0123456789  공격력 62  무게 3.0  소울 87650"}'
con 'tellraw Tester {"text":" "}'
con 'tellraw Tester {"text":"The straight sword the Redin guard wore, 1234."}'
tools/client/run_client.sh --do "$PORT" wait:0.6 "shot:$NAME" 2>&1 | grep SHOT
