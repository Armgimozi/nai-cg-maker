#!/bin/bash
# 실제 클라이언트 점검용 시험 서버 (DESIGN.md 13.4). Paper 1.21.11 + Soulslike.jar, 오프라인 접속, 시험 모드, 팩은 로컬에서.
#   devserver.sh <포트> <폴더> [플러그인.jar]   켜고 "Done" 까지 기다린다 (뒤에서 돈다)
#   devserver.sh --cmd <폴더> <명령...>         서버 콘솔에 명령을 넣는다 (예: --cmd srv op Tester)
#   devserver.sh --stop <폴더>                  끈다
# 환경 변수
#   PAPER_JAR   paper.jar 위치 (폴더에 paper.jar 가 없을 때 복사해 온다)
#   PACK_PORT   jar 안 pack.zip 을 내보낼 포트 (기본 <포트> - 17000, 25602 → 8602)
#   NO_PLUGIN=1 플러그인 없이 바닐라 Paper 로 (하네스만 볼 때)
#   OPS         켠 뒤 op 를 줄 이름들 (기본 "Tester" = 하네스 기본 이름. /soulstest 는 souls.test 권한, 곧 op 가 필요하다)
#   SET         플러그인 설정을 더 바꾼다. "묶음.키=값" 을 빈칸으로 (예 "pack.send-at=configure pack.self-check=false").
#               최상위 묶음 바로 밑의 키만 된다. 값은 그대로 쓴다 (글이면 따옴표까지 준다)
# 플러그인 설정(config.yml)은 켤 때마다 jar 안의 것을 새로 풀어 debug.test-mode: true, pack.serve-port, pack.url 만 바꾼다
# (그리고 SET). 시작 설정 (5.7, 5.10) 은 기본으로 세계를 보통·PvP 끔으로 확정하고 Tester·봇 (Souls…) 을 접속할 때 빈털터리로
# 태어나게 한다 (점검 그림이 창에 막히지 않게): START="" 로 끄면 실제 차례 (세계를 정한다 → 출신 창) 를 그대로 받는다.
# 창 그림만 볼 때는 켠 채로 /soulstest settings clear 와 /souls origin reset Tester 로 창을 다시 부른다 (ui_shots.sh).
# 기록: <폴더>/console.log
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)

die() { echo "devserver: $*" >&2; exit 1; }

if [ "${1:-}" = "--cmd" ]; then
  D=$2; shift 2
  [ -p "$D/console.in" ] || die "켜진 서버가 없다: $D"
  echo "$*" > "$D/console.in"
  exit 0
fi

if [ "${1:-}" = "--stop" ]; then
  D=$2
  [ -f "$D/server.pid" ] || exit 0
  pid=$(cat "$D/server.pid")
  if kill -0 "$pid" 2>/dev/null; then
    echo stop > "$D/console.in"
    for _ in $(seq 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill "$pid" 2>/dev/null
  fi
  [ -f "$D/keeper.pid" ] && kill "$(cat "$D/keeper.pid")" 2>/dev/null
  rm -f "$D/server.pid" "$D/keeper.pid" "$D/console.in"
  exit 0
fi

[ $# -ge 2 ] || die "쓰는 법: devserver.sh <포트> <폴더> [플러그인.jar]"
PORT=$1
D=$2
JAR=${3:-$ROOT/plugin/build/libs/Soulslike.jar}
PACK_PORT=${PACK_PORT:-$((PORT - 17000))}
mkdir -p "$D/plugins" "$D/config"
D=$(cd "$D" && pwd)

if [ -f "$D/server.pid" ] && kill -0 "$(cat "$D/server.pid")" 2>/dev/null; then
  die "이미 켜져 있다 (pid $(cat "$D/server.pid")). 먼저 --stop"
fi

# Paper
if [ ! -f "$D/paper.jar" ]; then
  [ -n "${PAPER_JAR:-}" ] && [ -f "$PAPER_JAR" ] || die "paper.jar 가 없다. PAPER_JAR=<paper-1.21.11-132.jar> 로 준다"
  cp "$PAPER_JAR" "$D/paper.jar"
  # Paper 가 처음 켤 때 만드는 cache/libraries 를 옆 폴더에서 가져오면 바닐라 서버 jar 를 다시 받지 않는다
  src=$(dirname "$PAPER_JAR")
  for x in cache libraries versions; do
    [ -d "$src/$x" ] && [ ! -e "$D/$x" ] && cp -r "$src/$x" "$D/$x"
  done
fi

# 서버 설정: 배포 server/ 의 값(12.7) 위에 시험에 필요한 것만 덮는다
cp "$ROOT/server/server.properties" "$D/server.properties"
cp "$ROOT/server/bukkit.yml" "$D/bukkit.yml"
cp "$ROOT/server/spigot.yml" "$D/spigot.yml"
[ -f "$D/config/paper-global.yml" ] || cp "$ROOT/server/config/paper-global.yml" "$D/config/paper-global.yml"
setprop() {
  if grep -q "^$1=" "$D/server.properties"; then sed -i "s|^$1=.*|$1=$2|" "$D/server.properties"
  else echo "$1=$2" >> "$D/server.properties"; fi
}
setprop server-port "$PORT"
setprop online-mode false
setprop enforce-secure-profile false
setprop pause-when-empty-seconds -1
echo "eula=true" > "$D/eula.txt"

# 플러그인
if [ "${NO_PLUGIN:-0}" = "1" ]; then
  rm -f "$D/plugins/Soulslike.jar"
else
  [ -f "$JAR" ] || die "플러그인 jar 가 없다: $JAR"
  cp "$JAR" "$D/plugins/Soulslike.jar"
  mkdir -p "$D/plugins/Soulslike"
  unzip -p "$JAR" config.yml > "$D/plugins/Soulslike/config.yml" || die "jar 안에 config.yml 이 없다"
  # 최상위 블록(pack:, debug:) 안의 키만 바꾼다
  START_SET='start.auto="normal,off" start.auto-origin=deprived start.auto-names="Souls,Tester"'
  [ "${START-x}" = "" ] && START_SET=""
  awk -v pp="$PACK_PORT" -v set="$START_SET ${SET:-}" '
    BEGIN { n = split(set, kv, " "); for (i = 1; i <= n; i++) { eq = index(kv[i], "="); want[substr(kv[i], 1, eq - 1)] = substr(kv[i], eq + 1) } }
    /^[^ #]/ { sec = $1; sub(":$", "", sec) }
    /^  [a-z-]+:/ { k = $1; sub(":$", "", k); if ((sec "." k) in want) { print "  " k ": " want[sec "." k]; next } }
    sec == "pack"  && /^  url:/        { print "  url: \"http://127.0.0.1:" pp "/{sha1}.zip\""; next }
    sec == "pack"  && /^  serve-port:/ { print "  serve-port: " pp; next }
    sec == "debug" && /^  test-mode:/  { print "  test-mode: true"; next }
    { print }
  ' "$D/plugins/Soulslike/config.yml" > "$D/plugins/Soulslike/config.yml.tmp" \
    && mv "$D/plugins/Soulslike/config.yml.tmp" "$D/plugins/Soulslike/config.yml"
fi

# 콘솔은 FIFO 로 받는다. 붙잡는 sleep 이 없으면 첫 명령 뒤에 EOF 로 서버가 꺼진다
cd "$D" || exit 1
rm -f console.in
mkfifo console.in
nohup sleep infinity > console.in 2>/dev/null &
echo $! > keeper.pid
nohup java -Xms1G -Xmx2G -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 \
  -jar paper.jar --nogui < console.in > console.log 2>&1 &
echo $! > server.pid

for _ in $(seq 600); do
  if grep -q "Done (" console.log 2>/dev/null; then
    for n in ${OPS-Tester}; do echo "op $n" > console.in; done
    echo "devserver: 켜짐 port=$PORT pack=$PACK_PORT pid=$(cat server.pid) 기록=$D/console.log"
    exit 0
  fi
  kill -0 "$(cat server.pid)" 2>/dev/null || { tail -30 console.log; die "서버가 꺼졌다"; }
  sleep 1
done
die "600초 안에 Done 이 나오지 않았다 ($D/console.log)"
