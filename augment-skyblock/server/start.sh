#!/bin/sh
# 맥/리눅스용. Java 21 이 설치되어 있어야 합니다 (https://adoptium.net).
cd "$(dirname "$0")" || exit 1
MEMORY=4G
PAPER_URL=https://fill-data.papermc.io/v1/objects/5ee4f542f628a14c644410b08c94ea42e772ef4d29fe92973636b6813d4eaffc/paper-1.21.4-232.jar
PAPER_SIZE=51437498

if [ ! -f plugins/AugmentSkyblock.jar ] || [ ! -f world/level.dat ]; then
  echo "압축을 먼저 모두 풀고, 풀린 폴더 안에서 start.sh 를 실행하세요."
  exit 1
fi
if ! java -version 2>&1 | grep -Eq 'version "(2[1-9]|[3-9][0-9])'; then
  echo "Java 21 이상이 필요합니다. https://adoptium.net 에서 Temurin 21 을 설치하세요."
  exit 1
fi
size() { wc -c < "$1" | tr -d ' '; }
if [ ! -f paper.jar ] || [ "$(size paper.jar)" -lt 10000000 ]; then
  echo "Paper 1.21.4 를 내려받는 중..."
  if ! curl -fL --retry 3 -o paper.jar "$PAPER_URL" || [ "$(size paper.jar)" != "$PAPER_SIZE" ]; then
    rm -f paper.jar
    echo "다운로드 실패. https://papermc.io/downloads/all 에서 1.21.4 를 받아 이 폴더에 paper.jar 로 넣어 주세요."
    exit 1
  fi
fi
while ! grep -qi "eula=true" eula.txt 2>/dev/null; do
  printf "마인크래프트 EULA(https://aka.ms/MinecraftEULA)에 동의하면 y 를 입력하세요: "
  read AGREE || exit 1
  case "$AGREE" in y|Y) echo "eula=true" > eula.txt ;; esac
done
exec java -Xms1G -Xmx$MEMORY -Dstdout.encoding=UTF-8 -jar paper.jar nogui
