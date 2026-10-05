#!/bin/sh
# 맥/리눅스용. Java 21 이 설치되어 있어야 합니다 (https://adoptium.net).
cd "$(dirname "$0")"
MEMORY=4G
PAPER_URL=https://fill-data.papermc.io/v1/objects/5ee4f542f628a14c644410b08c94ea42e772ef4d29fe92973636b6813d4eaffc/paper-1.21.4-232.jar
if [ ! -f paper.jar ]; then
  echo "Paper 1.21.4 를 내려받는 중..."
  curl -L -o paper.jar "$PAPER_URL" || { echo "다운로드 실패"; exit 1; }
fi
if ! grep -qi "eula=true" eula.txt 2>/dev/null; then
  echo "마인크래프트 EULA(https://aka.ms/MinecraftEULA)에 동의합니까? (y/n)"
  read AGREE
  [ "$AGREE" = "y" ] || [ "$AGREE" = "Y" ] || { echo "동의하지 않아 종료합니다."; exit 1; }
  echo "eula=true" > eula.txt
fi
exec java -Xms2G -Xmx$MEMORY -Dstdout.encoding=UTF-8 -jar paper.jar nogui
