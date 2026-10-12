#!/usr/bin/env bash
# 아오오니 저택 서버 실행 (Linux / macOS)
set -euo pipefail
cd "$(dirname "$0")"

# 지원 버전: 1.21.5 ~ 26.3 (자바 에디션)
MC_VERSION="${MC_VERSION:-1.21.11}"
RAM="${RAM:-4G}"

if ! command -v java >/dev/null 2>&1; then
  echo "[오류] Java 가 없습니다. 1.21.x 는 Java 21, 26.x 는 Java 25 이상이 필요합니다."
  exit 1
fi

if [ ! -f server.jar ]; then
  echo "[아오오니 저택] Minecraft ${MC_VERSION} 서버 파일을 Mojang 에서 내려받습니다..."
  manifest="https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
  ver_url=$(curl -fsSL "$manifest" | python3 -c 'import sys,json; v=[x for x in json.load(sys.stdin)["versions"] if x["id"]==sys.argv[1]]; print(v[0]["url"] if v else "")' "$MC_VERSION")
  if [ -z "$ver_url" ]; then echo "[오류] 버전을 찾을 수 없습니다: $MC_VERSION"; exit 1; fi
  jar_url=$(curl -fsSL "$ver_url" | python3 -c 'import sys,json; j=json.load(sys.stdin); print(j["downloads"]["server"]["url"]); print("필요한 Java:", j["javaVersion"]["majorVersion"], file=sys.stderr)')
  curl -fL "$jar_url" -o server.jar
fi

if ! grep -q "eula=true" eula.txt 2>/dev/null; then
  echo "서버를 실행하려면 Minecraft EULA 에 동의해야 합니다: https://aka.ms/MinecraftEULA"
  read -r -p "EULA 에 동의하십니까? [y/N]: " agree
  case "$agree" in
    [yY]*) echo "eula=true" > eula.txt ;;
    *) echo "동의하지 않아 종료합니다."; exit 1 ;;
  esac
fi

echo "[아오오니 저택] 서버를 시작합니다. 종료: stop"
exec java -Xms1G -Xmx"$RAM" -jar server.jar nogui
