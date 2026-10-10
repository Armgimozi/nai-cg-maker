#!/bin/sh
# 블록 소울 서버 시작기 (맥/리눅스). 윈도우는 start.bat 을 쓴다.
# 처음 실행하면 Java 21 (없을 때만) 과 Paper 1.21.11 (빌드 132) 을 이 폴더에 내려받는다.
# 이 파일은 LF 줄 끝 + 실행 권한으로 둔다. 서버에 넘길 인수는 그대로 붙는다 (예: ./start.sh --port 25570)
#   MEMORY=6G ./start.sh      서버 메모리를 직접 정한다 (비우면 PC 메모리를 보고 2G~4G)
#   JAVA=/경로/java ./start.sh  쓸 Java 를 직접 정한다
cd "$(dirname "$0")" || exit 1

# Paper 는 1.21.11 빌드 132 로 고정한다 (DESIGN.md 0.1). 값은 fill.papermc.io v3 의 server:default 그대로. start.ps1 과 같아야 한다
PAPER_URL=https://fill-data.papermc.io/v1/objects/5ffef465eeeb5f2a3c23a24419d97c51afd7dbb4923ff42df9a3f58bba1ccfba/paper-1.21.11-132.jar
PAPER_SIZE=54846016
PAPER_SHA256=5ffef465eeeb5f2a3c23a24419d97c51afd7dbb4923ff42df9a3f58bba1ccfba
JAVA_API=https://api.adoptium.net/v3/binary/latest/21/ga

say() { printf '%s\n' "$*"; }
die() { say ""; for l in "$@"; do say "$l"; done; exit 1; }

# 받기: curl → 없으면 wget. 중간에 끊긴 파일이 남지 않게 .part 로 받아 옮긴다
fetch() {
  rm -f "$2.part"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --connect-timeout 30 -o "$2.part" "$1" || { rm -f "$2.part"; return 1; }
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2.part" "$1" || { rm -f "$2.part"; return 1; }
  else
    say "  curl 도 wget 도 없다."
    return 1
  fi
  mv -f "$2.part" "$2"
}
size() { wc -c < "$1" | tr -d ' '; }
sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else openssl dgst -sha256 "$1" | sed 's/.*= *//'
  fi
}
# paper.jar 가 고정한 판인지. 크기가 먼저 맞아야 sha256 을 잰다
paper_ok() { [ -f paper.jar ] && [ "$(size paper.jar)" = "$PAPER_SIZE" ] && [ "$(sha256 paper.jar)" = "$PAPER_SHA256" ]; }
# java 실행 파일의 주 버전 (21, 17, 1 ...). 실행이 안 되면 0
java_major() {
  [ -n "$1" ] && [ -x "$1" ] || { echo 0; return; }
  v=$("$1" -version 2>&1 | sed -n 's/.*version "\([0-9][0-9]*\).*/\1/p' | head -n 1)
  echo "${v:-0}"
}

say "[블록 소울 시작기 1판]"
say "폴더: $(pwd)"

# ── 압축을 풀었는지 (M0 에는 미리 지은 세계가 없다. 처음 켤 때 플러그인이 짓는다) ──
[ -f plugins/Soulslike.jar ] || die "plugins/Soulslike.jar 가 없다. zip 을 먼저 모두 풀고, 풀린 폴더 안에서 start.sh 를 실행한다."

# ── Java 21: JAVA → 이 폴더의 runtime → JAVA_HOME → PATH. 없으면 Temurin 21 JRE 를 runtime/ 에 받는다 ──
say ""
say "Java 확인 중..."
JAVA_BIN=""
for j in "$JAVA" runtime/bin/java runtime/Contents/Home/bin/java "${JAVA_HOME:+$JAVA_HOME/bin/java}" "$(command -v java 2>/dev/null)"; do
  if [ -n "$j" ] && [ "$(java_major "$j")" -ge 21 ]; then JAVA_BIN=$j; break; fi
done
if [ -z "$JAVA_BIN" ]; then
  case "$(uname -s)" in
    Linux) os=linux ;;
    Darwin) os=mac ;;
    *) os="" ;;
  esac
  case "$(uname -m)" in
    x86_64|amd64) arch=x64 ;;
    aarch64|arm64) arch=aarch64 ;;
    *) arch="" ;;
  esac
  [ -n "$os" ] && [ -n "$arch" ] || die "Java 21 이상이 필요하다. https://adoptium.net 에서 Temurin 21 을 설치한 뒤 다시 실행한다."
  say "[1/2] Java 21 ($os $arch) 을 내려받는 중... (처음 한 번만, 50MB 정도)"
  fetch "$JAVA_API/$os/$arch/jre/hotspot/normal/eclipse" java21.tar.gz \
    || die "Java 21 을 받지 못했다. 인터넷 연결을 확인하거나 https://adoptium.net 에서 Temurin 21 을 설치한다."
  rm -rf runtime runtime_tmp
  mkdir runtime_tmp
  tar -xzf java21.tar.gz -C runtime_tmp || die "받은 Java 의 압축을 풀지 못했다. java21.tar.gz 를 지우고 다시 실행한다."
  inner=$(find runtime_tmp -mindepth 1 -maxdepth 1 -type d | head -n 1)
  mv "$inner" runtime && rm -rf runtime_tmp java21.tar.gz
  for j in runtime/bin/java runtime/Contents/Home/bin/java; do
    if [ "$(java_major "$j")" -ge 21 ]; then JAVA_BIN=$j; break; fi
  done
  [ -n "$JAVA_BIN" ] || die "받은 Java 가 실행되지 않는다. runtime 폴더를 지우고 다시 실행하거나 Temurin 21 을 설치한다."
fi
say "  Java: $JAVA_BIN"

# ── Paper 서버 파일 (크기와 sha256 이 다르면 지우고 다시 받는다) ──
if ! paper_ok; then
  [ -f paper.jar ] && say "  paper.jar 가 1.21.11 빌드 132 가 아니어서 다시 받는다." && rm -f paper.jar
  say "[2/2] Paper 1.21.11 서버 파일을 내려받는 중... (55MB 정도)"
  if ! fetch "$PAPER_URL" paper.jar || ! paper_ok; then
    rm -f paper.jar
    die "Paper 서버 파일을 받지 못했거나, 받은 파일이 맞지 않는다 (크기·sha256 확인 실패)." \
        "https://papermc.io/downloads/all 에서 1.21.11 의 빌드 132 를 받아 이 폴더에 paper.jar 로 넣는다."
  fi
fi
say "  Paper: paper.jar (1.21.11 빌드 132, sha256 확인)"

# ── 메모리 (DESIGN.md 12.10: 3~4GB) ──
if [ -z "$MEMORY" ]; then
  kb=$(sed -n 's/^MemTotal: *\([0-9]*\).*/\1/p' /proc/meminfo 2>/dev/null)
  [ -n "$kb" ] || kb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 8589934592) / 1024 ))
  gb=$(( kb / 1024 / 1024 ))
  if [ "$gb" -ge 12 ]; then MEMORY=4G; elif [ "$gb" -ge 7 ]; then MEMORY=3G; else MEMORY=2G; fi
  say "  PC 메모리 약 ${gb}GB → 서버 메모리 $MEMORY"
fi

# ── EULA ──
while ! grep -qi "eula=true" eula.txt 2>/dev/null; do
  say ""
  say "마인크래프트 서버를 열려면 Mojang 의 최종 사용자 계약(EULA)에 동의해야 한다. 내용: https://aka.ms/MinecraftEULA"
  printf "동의하면 y 를 입력하고 Enter: "
  read -r AGREE || die "EULA 동의를 받지 못했다."
  case "$AGREE" in y|Y|yes|YES) echo "eula=true" > eula.txt ;; esac
done

# ── 서버 켜기 ──
say ""
say "서버를 켠다. \"Done\" 이 나오면 마인크래프트 1.21.11 에서 localhost 로 접속한다."
say "처음 켤 때는 마인크래프트 서버 파일을 한 번 더 받고 세계를 짓느라 몇 분 걸린다. 끌 때는 stop."
say ""
exec "$JAVA_BIN" -Xms1G "-Xmx$MEMORY" -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 \
  -jar paper.jar nogui "$@"
