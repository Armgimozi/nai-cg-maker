#!/bin/sh
# 미궁 라비린스 — 맥/리눅스용 시작 스크립트. Java 25 가 설치되어 있어야 합니다 (https://adoptium.net → Temurin 25).
# 처음 실행하면 Paper 26.3 최신 안정판을 PaperMC Fill API(v3)에서 받아 sha256 을 확인합니다.
cd "$(dirname "$0")" || exit 1
MC_VERSION=26.3
MEMORY=${MEMORY:-4G}
API="https://fill.papermc.io/v3/projects/paper/versions/$MC_VERSION/builds"
UA="Labyrinth-Server-Launcher/__VERSION__ (Minecraft server pack launcher; sh)"

if [ ! -f plugins/Labyrinth.jar ]; then
  echo "압축을 먼저 모두 풀고, 풀린 폴더 안에서 start.sh 를 실행하세요."
  exit 1
fi
if ! java -version 2>&1 | grep -Eq 'version "(2[5-9]|[3-9][0-9])'; then
  echo "Java 25 이상이 필요합니다. https://adoptium.net 에서 Temurin 25 를 설치한 뒤 다시 실행하세요."
  exit 1
fi

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else echo ""; fi
}

if [ ! -f paper.jar ] || [ "$(wc -c < paper.jar | tr -d ' ')" -lt 10000000 ]; then
  echo "Paper $MC_VERSION 최신 안정판을 찾는 중..."
  JSON=$(curl -fsSL --retry 3 -A "$UA" "$API") || JSON=""
  # 빌드 하나 = 한 줄로 나눈 뒤 STABLE 중 번호가 가장 큰 빌드
  BEST=$(printf '%s' "$JSON" | tr -d '\n\r\t ' | awk '{ gsub(/\{"id":/, "\n{\"id\":"); print }' \
         | grep '"channel":"STABLE"' \
         | awk -F'[:,]' '{ print $2 "\t" $0 }' | sort -n -r | head -n 1 | cut -f2-)
  URL=$(printf '%s' "$BEST" | grep -o '"url":"[^"]*"' | head -n 1 | cut -d'"' -f4)
  SHA=$(printf '%s' "$BEST" | grep -o '"sha256":"[^"]*"' | head -n 1 | cut -d'"' -f4)
  if [ -z "$URL" ]; then
    echo "Paper $MC_VERSION 정보를 받지 못했습니다. https://papermc.io/downloads/paper 에서 받아 이 폴더에 paper.jar 로 넣어 주세요."
    exit 1
  fi
  echo "내려받는 중: $URL"
  if ! curl -fL --retry 3 -A "$UA" -o paper.jar.part "$URL"; then
    rm -f paper.jar.part
    echo "다운로드 실패. https://papermc.io/downloads/paper 에서 $MC_VERSION 을 받아 이 폴더에 paper.jar 로 넣어 주세요."
    exit 1
  fi
  GOT=$(sha256_of paper.jar.part)
  if [ -n "$SHA" ] && [ -n "$GOT" ] && [ "$GOT" != "$SHA" ]; then
    rm -f paper.jar.part
    echo "받은 파일의 sha256 이 맞지 않습니다 (중간에 깨졌을 수 있음). 다시 실행해 보세요."
    exit 1
  fi
  mv paper.jar.part paper.jar
  echo "sha256 확인 완료"
fi

# EULA 는 직접 동의해야 합니다 (미리 동의해 두지 않습니다)
while ! grep -qi "eula=true" eula.txt 2>/dev/null; do
  printf "마인크래프트 EULA(https://aka.ms/MinecraftEULA)에 동의하면 y 를 입력하세요: "
  read AGREE || exit 1
  case "$AGREE" in y|Y|yes|YES) echo "eula=true" > eula.txt ;; esac
done
echo "서버를 켭니다. \"Done\" 이 나오면 마인크래프트 $MC_VERSION 에서 localhost 로 접속하세요. 끌 때는 stop."
exec java -Xms1G -Xmx"$MEMORY" -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -jar paper.jar nogui
