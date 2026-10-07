#!/usr/bin/env bash
# 봇 시험 (DESIGN.md 13.2, 13.3). 빌드 → 새 Paper 1.21.11 서버 → 봇 시나리오 → 지연 프록시로 구르기 다시 → 서버 끄기.
#
#   tools/run_tests.sh [--port 25601] [--scratch DIR] [--paper paper.jar] [--jar Soulslike.jar | --no-build]
#                      [--no-pack] [--only "join roll_iframes"] [--lag "60 120" | --lag none] [--keep-running]
#
#   --port N        서버 포트 (기본 25601). 팩 HTTP 는 N+1000, 지연 프록시는 N+2010, N+2020 ...
#   --scratch DIR   서버 폴더·기록을 둘 곳 (기본: $SOULS_TEST_DIR → 시험 도구 폴더 옆 bots-run-<포트> → /tmp).
#                   매번 DIR/server 와 DIR/run 을 새로 만든다 (이 시험이 만든 폴더만 지운다)
#   --paper JAR     Paper 1.21.11 빌드 132 jar (기본: $PAPER_JAR → DIR/paper.jar → 이 컨테이너의 시험 도구 폴더)
#                   jar 옆에 libraries/ cache/ versions/ 가 있으면 링크로 빌려 써서 내려받지 않는다
#   --jar JAR       빌드하지 않고 이 플러그인 jar 를 쓴다. --no-build 는 plugin/build/libs/Soulslike.jar 를 그대로 쓴다
#   --no-pack       pack/gen_pack.py 를 돌리지 않는다 (jar 안 pack.zip 은 지난번 것)
#   --only "..."    이 시나리오만 (이름은 --list)
#   --lag "..."     roll_iframes 를 지연 프록시로 다시 돌릴 왕복 지연 ms 목록 (기본 "60 120", 13.3). none 이면 건너뛴다
#   --keep-running  끝나도 서버를 끄지 않는다 (콘솔: echo '<명령>' > DIR/server/console.in)
#   --mem 2G        서버 메모리
#   --timeout 300   시나리오 하나의 제한 시간 (초)
#   --visual V      구르기 모습 combat.roll.visual (tumble 기본 · spin · crawl) 을 바꾼다. 주지 않으면 jar 설정 그대로 (tumble:
#                   roll_iframes 가 대역 둘이 타고 투명 깃발이 섰다가 걷히는지도 본다)
#   --crawl         구르기 기어가기 방벽(combat.roll.crawl)을 jar 설정 그대로 둔다 (방벽은 visual: crawl 일 때만 깔린다. 그래서
#                   방벽 흉내까지 보려면 --visual crawl --crawl). 기본은 끈다 (봇은 기어가기 자세가 없다.
#                   켜면 lib.js 가 머리 높이 방벽을 봇 세계에서 지워 기어가기를 흉내 내고, roll_iframes 가 방벽이 깔리고 걷히는지 본다)
#
# 봇은 mineflayer 4.39 를 쓴다: $BOT_NODE_MODULES → tools/bots/node_modules → 이 컨테이너의 시험 도구 폴더.
# 결과: 시나리오마다 PASS/FAIL 한 줄과 실패한 판정. 자세한 기록은 DIR/run/logs/*.log, 판정 JSON 은 DIR/run/results/.
# 시나리오 뒤: 서버를 끄고 켠 뒤부터 꺼질 때까지의 기록 전체(플러그인 끄기·세계 저장 포함)에서 오류를 본다 (server_log).
# 그다음 같은 폴더로 한 번 더 켜서 두 번째 기동을 본다 (second_boot): 세계를 새로 만들지 않고, 난이도 경고가 없고,
# 시험 방을 다시 짓지 않고, 오류가 없다 (12.7, 13.2 T2).
# 지연 판의 roll_iframes 가 남긴 "자기 화면 기준" 피한 비율을 지연별로 모아 보인다 (판정 아님, 13.3).
# 끝 코드: 0 모두 통과, 1 실패한 시나리오가 있음, 2 준비 단계(빌드·서버 켜기)에서 멈춤.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
BOTS="$HERE/bots"

ALL_SCENARIOS="t1_boot join lang stamina roll_iframes guard death reconnect"
# 시나리오별 봇 이름 (ops.json 에 미리 올린다. 오프라인 UUID)
declare -A BOT=( [t1_boot]=SoulsBoot [join]=SoulsJoin [lang]=SoulsLang [stamina]=SoulsStam [roll_iframes]=SoulsRoll
                 [guard]=SoulsGuard [death]=SoulsDeath [reconnect]=SoulsRecon [lag]=SoulsLag )

PORT=25601
SCRATCH="${SOULS_TEST_DIR:-}"
PAPER="${PAPER_JAR:-}"
JAR=""
BUILD=1
PACK=1
ONLY=""
LAG="60 120"
KEEP=0
CRAWL=0
VISUAL=""
MEM=2G
SC_TIMEOUT=300

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --scratch) SCRATCH="$2"; shift 2 ;;
    --paper) PAPER="$2"; shift 2 ;;
    --jar) JAR="$2"; BUILD=0; shift 2 ;;
    --no-build) BUILD=0; shift ;;
    --no-pack) PACK=0; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    --lag) LAG="$2"; shift 2 ;;
    --keep-running) KEEP=1; shift ;;
    --crawl) CRAWL=1; shift ;;
    --visual) VISUAL="$2"; shift 2 ;;
    --mem) MEM="$2"; shift 2 ;;
    --timeout) SC_TIMEOUT="$2"; shift 2 ;;
    --list) echo "lang_check $ALL_SCENARIOS (+ roll_iframes@lag<ms>)"; exit 0 ;;
    -h|--help) sed -n '2,/^set -u/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "모르는 인수: $1 (--help)"; exit 2 ;;
  esac
done
[ "$LAG" = none ] && LAG=""
PACK_PORT=$((PORT + 1000))

say() { printf '%s\n' "$*"; }
die() { say "SETUP FAIL: $*"; exit 2; }
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# ── 도구 찾기 ──
first_file() { for f in "$@"; do [ -n "$f" ] && [ -f "$f" ] && { echo "$f"; return 0; }; done; return 1; }
first_dir() { for d in "$@"; do [ -n "$d" ] && [ -d "$d" ] && { echo "$d"; return 0; }; done; return 1; }
# 이 컨테이너에서 미리 갖춘 시험 도구 (작업 폴더 경로가 세션마다 달라 glob 으로 찾는다)
TOOLS_PAPER=$(ls /tmp/claude-*/*/*/scratchpad/testsrv/paper.jar 2>/dev/null | head -n 1)
TOOLS_NM=$(ls -d /tmp/claude-*/*/*/scratchpad/bot/node_modules 2>/dev/null | head -n 1)

if [ -z "$SCRATCH" ]; then
  if [ -n "$TOOLS_PAPER" ]; then SCRATCH="$(dirname "$(dirname "$TOOLS_PAPER")")/bots-run-$PORT"; else SCRATCH="${TMPDIR:-/tmp}/souls-tests-$PORT"; fi
fi
mkdir -p "$SCRATCH" || die "폴더를 만들지 못했다: $SCRATCH"
SCRATCH="$(cd "$SCRATCH" && pwd)"
PAPER=$(first_file "$PAPER" "$SCRATCH/paper.jar" "$TOOLS_PAPER") || die "Paper jar 가 없다 (--paper)"
NODE_MODULES=$(first_dir "${BOT_NODE_MODULES:-}" "$BOTS/node_modules" "$TOOLS_NM") || die "mineflayer node_modules 가 없다 (BOT_NODE_MODULES)"
[ -d "$NODE_MODULES/mineflayer" ] || die "$NODE_MODULES 에 mineflayer 가 없다"
command -v java >/dev/null || die "java 가 없다"
command -v node >/dev/null || die "node 가 없다"
command -v python3 >/dev/null || die "python3 가 없다"

SRV="$SCRATCH/server"
RUN="$SCRATCH/run"
say "== 식은 가마 봇 시험  port=$PORT  pack=$PACK_PORT  dir=$SCRATCH"
say "   paper=$PAPER"
say "   mineflayer=$NODE_MODULES"

for p in "$PORT" "$PACK_PORT"; do port_busy "$p" && die "포트 $p 를 이미 누가 쓰고 있다 (다른 서버를 끄거나 --port 를 바꾼다)"; done

# 지난 결과는 지운다 (표시 파일이 있는 우리 폴더만)
for d in "$SRV" "$RUN"; do
  if [ -d "$d" ]; then
    [ -f "$d/.souls-test" ] || [ -z "$(ls -A "$d")" ] || die "$d 는 이 시험이 만든 폴더가 아니다 (지우지 않는다)"
    rm -rf "$d"
  fi
  mkdir -p "$d" && touch "$d/.souls-test"
done
mkdir -p "$RUN/logs" "$RUN/results"

# ── 빌드 (10.6 순서: gen_pack → gradle) ──
# gen_pack 은 시험용 --no-dist 로 돌려 dist/packs/ 를 건드리지 않는다. 두 번 돌려 SHA-1 이 같은지도 본다 (13.2 T8)
REPRO=""
if [ "$BUILD" = 1 ]; then
  if [ "$PACK" = 1 ] && [ -f "$ROOT/pack/gen_pack.py" ]; then
    say "-- pack/gen_pack.py"
    GEN_ARGS=""
    grep -q -- '--no-dist' "$ROOT/pack/gen_pack.py" && GEN_ARGS="--no-dist"
    PZ="$ROOT/plugin/src/main/resources/pack.zip"
    for n in 1 2; do
      if ! (cd "$ROOT/pack" && python3 gen_pack.py $GEN_ARGS) > "$RUN/logs/build-pack-$n.log" 2>&1; then
        tail -n 20 "$RUN/logs/build-pack-$n.log"; say "FAIL  build:pack  ($RUN/logs/build-pack-$n.log)"; exit 2
      fi
      [ -f "$PZ" ] || { say "FAIL  build:pack  pack.zip 이 생기지 않았다 ($PZ)"; exit 2; }
      h=$(sha1sum "$PZ" | cut -d' ' -f1)
      if [ "$n" = 1 ]; then SHA_1=$h; else SHA_2=$h; fi
    done
    if [ "$SHA_1" = "$SHA_2" ]; then REPRO="PASS pack_repro sha1=$SHA_1"; else REPRO="FAIL pack_repro $SHA_1 != $SHA_2"; fi
  fi
  say "-- gradle build"
  if ! (cd "$ROOT/plugin" && ./gradlew build -q) > "$RUN/logs/build-gradle.log" 2>&1; then
    tail -n 30 "$RUN/logs/build-gradle.log"; say "FAIL  build:gradle  ($RUN/logs/build-gradle.log)"; exit 2
  fi
fi
[ -n "$JAR" ] || JAR="$ROOT/plugin/build/libs/Soulslike.jar"
[ -f "$JAR" ] || die "플러그인 jar 가 없다: $JAR"

# ── 새 서버 폴더 ──
mkdir -p "$SRV/plugins/Soulslike" "$SRV/config"
cp "$PAPER" "$SRV/paper.jar"
cp "$JAR" "$SRV/plugins/Soulslike.jar"          # 다른 빌드가 jar 를 바꿔도 이 시험은 이 사본으로 돈다
PDIR="$(dirname "$PAPER")"
for d in libraries cache versions; do [ -d "$PDIR/$d" ] && ln -s "$PDIR/$d" "$SRV/$d"; done
echo "eula=true" > "$SRV/eula.txt"
[ -f "$ROOT/server/bukkit.yml" ] && cp "$ROOT/server/bukkit.yml" "$SRV/bukkit.yml"
[ -f "$ROOT/server/config/paper-global.yml" ] && cp "$ROOT/server/config/paper-global.yml" "$SRV/config/paper-global.yml"
unzip -p "$JAR" glyphs.yml > "$RUN/glyphs.yml" 2>/dev/null || rm -f "$RUN/glyphs.yml"
unzip -p "$JAR" pack.zip > "$RUN/pack.zip" 2>/dev/null || rm -f "$RUN/pack.zip"
PACK_SHA1=""
[ -s "$RUN/pack.zip" ] && PACK_SHA1=$(sha1sum "$RUN/pack.zip" | cut -d' ' -f1)
unzip -p "$JAR" config.yml > "$RUN/config.default.yml" 2>/dev/null || die "jar 안에 config.yml 이 없다"

python3 - "$ROOT/server/server.properties" "$SRV/server.properties" "$PORT" \
          "$RUN/config.default.yml" "$SRV/plugins/Soulslike/config.yml" "$PACK_PORT" \
          "$SRV/ops.json" "$CRAWL" "$VISUAL" "${BOT[@]}" <<'PY' || die "서버 설정을 쓰지 못했다"
import hashlib, json, os, re, sys, uuid
props_src, props_dst, port, cfg_src, cfg_dst, pack_port, ops_dst, keep_crawl, visual, *names = sys.argv[1:]

# server.properties: 저장소 판(12.7) 그대로 + 시험용으로 포트와 online-mode 만 바꾼다
lines = open(props_src, encoding="utf-8").read().splitlines() if os.path.exists(props_src) else []
over = {"server-port": port, "online-mode": "false", "level-name": "world"}
seen = set(); out = []
for l in lines:
    k = l.split("=", 1)[0].strip()
    if not l.startswith("#") and "=" in l and k in over:
        l = f"{k}={over[k]}"; seen.add(k)
    out.append(l)
out += [f"{k}={v}" for k, v in over.items() if k not in seen]
open(props_dst, "w", encoding="utf-8").write("\n".join(out) + "\n")

# 플러그인 설정: jar 기본값 + 시험 모드, 팩은 이 서버가 직접 내보낸다 (pack.serve-port)
sec = None; done = set(); out = []
for l in open(cfg_src, encoding="utf-8").read().split("\n"):
    m = re.match(r"^([A-Za-z0-9_-]+):", l)
    if m: sec = m.group(1)
    if sec == "debug" and re.match(r"^\s+test-mode:", l):
        l = re.sub(r"test-mode:.*", "test-mode: true", l); done.add("test-mode")
    if sec == "pack" and re.match(r"^\s+url:", l):
        l = re.sub(r"url:.*", f'url: "http://127.0.0.1:{pack_port}/{{sha1}}.zip"', l); done.add("url")
    if sec == "pack" and re.match(r"^\s+serve-port:", l):
        l = re.sub(r"serve-port:.*", f"serve-port: {pack_port}", l); done.add("serve-port")
    # 봇(mineflayer)은 기어가기 자세가 없어 구르기의 머리 위 방벽에 걸린다. 기어가기 모습은 실제 클라이언트 점검으로 본다
    # (--crawl 이면 그대로 두고 lib.js 의 흉내로 시험한다)
    if sec == "combat" and visual and re.match(r"^\s+visual:", l):
        l = re.sub(r"visual:.*", "visual: " + visual, l)
    if sec == "combat" and re.match(r"^\s+crawl:", l):
        if keep_crawl != "1": l = re.sub(r"crawl:.*", "crawl: false", l)
        done.add("crawl")
    out.append(l)
open(cfg_dst, "w", encoding="utf-8").write("\n".join(out))
missing = {"test-mode", "url", "serve-port", "crawl"} - done
if missing: print("  경고: config.yml 에서 못 찾은 열쇠:", ", ".join(sorted(missing)))

# ops.json: 봇 이름의 오프라인 UUID (UUID.nameUUIDFromBytes("OfflinePlayer:" + 이름))
def offline(n):
    h = bytearray(hashlib.md5(("OfflinePlayer:" + n).encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30; h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))
json.dump([{"uuid": offline(n), "name": n, "level": 4, "bypassesPlayerLimit": False} for n in sorted(set(names))],
          open(ops_dst, "w"), indent=2)
PY

# ── 서버 켜기 (콘솔은 FIFO) ──
SERVER_PID=""; KEEPER_PID=""; PROXY_PIDS=""
stop_server() {
  [ -n "$PROXY_PIDS" ] && kill $PROXY_PIDS 2>/dev/null
  PROXY_PIDS=""
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "stop" > "$SRV/console.in"
    for _ in $(seq 1 60); do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 1; done
    kill -0 "$SERVER_PID" 2>/dev/null && { say "   서버가 꺼지지 않아 강제로 끈다"; kill -9 "$SERVER_PID" 2>/dev/null; }
  fi
  [ -n "$KEEPER_PID" ] && kill "$KEEPER_PID" 2>/dev/null
  SERVER_PID=""; KEEPER_PID=""
}
cleanup() {
  if [ "$KEEP" = 1 ] && [ -n "$SERVER_PID" ]; then
    [ -n "$PROXY_PIDS" ] && kill $PROXY_PIDS 2>/dev/null
    say "-- 서버를 켜 둔다 (pid $SERVER_PID). 끄기: echo stop > $SRV/console.in; kill \$(cat $SRV/keeper.pid)"
    return
  fi
  stop_server
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# start_server <기록 파일 이름>: 켜고 "Done" 까지 기다린다. 실패하면 0 이 아닌 값
start_server() {
  local logname="$1"
  rm -f "$SRV/console.in"
  mkfifo "$SRV/console.in"
  sleep 2147483647 > "$SRV/console.in" 2>/dev/null < /dev/null &
  KEEPER_PID=$!
  echo "$KEEPER_PID" > "$SRV/keeper.pid"
  (cd "$SRV" && exec java -Xms512M -Xmx"$MEM" -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 \
     -jar paper.jar --nogui < console.in > "$logname" 2>&1) > /dev/null 2>&1 &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$SRV/server.pid"
  T0=$(date +%s)
  until grep -q 'Done (' "$SRV/$logname" 2>/dev/null; do
    kill -0 "$SERVER_PID" 2>/dev/null || { tail -n 40 "$SRV/$logname"; SERVER_PID=""; return 1; }
    [ $(( $(date +%s) - T0 )) -gt 300 ] && { tail -n 20 "$SRV/$logname"; return 2; }
    sleep 1
  done
  say "   켜짐 ($(( $(date +%s) - T0 ))초)"
}

say "-- 서버 켜는 중"
start_server console.log || die "서버가 켜지지 않았다 ($SRV/console.log)"
# 켜진 직후 몇 초는 청크 만들기·시험 방 짓기로 틱이 밀린다. 그동안 굴린 첫 구르기가 밀리지 않은 적이 있어 조금 기다린다
sleep 5

# ── 시나리오 ──
export NODE_PATH="$NODE_MODULES"
export MC_HOST=127.0.0.1 RUN_DIR="$RUN" SERVER_DIR="$SRV" SERVER_LOG="$SRV/console.log" SOULS_ROOT="$ROOT"
export GLYPHS_YML="$RUN/glyphs.yml" PACK_SHA1 SCENARIO_TIMEOUT="$SC_TIMEOUT"
[ -s "$GLYPHS_YML" ] || export GLYPHS_YML="$ROOT/plugin/src/main/resources/glyphs.yml"

declare -a SUMMARY=()
FAILED=0
want() { [ -z "$ONLY" ] && return 0; for o in $ONLY; do [ "$o" = "$1" ] && return 0; done; return 1; }

# run_one <표시 이름> <파일> <봇 이름> <포트> [지연]
run_one() {
  local label="$1" file="$2" name="$3" port="$4" lag="${5:-0}" tag=""
  [ "$lag" != 0 ] && tag="lag$lag"
  local log="$RUN/logs/$label.log"
  MC_PORT="$port" BOT_NAME="$name" LAG_RTT="$lag" SCENARIO_TAG="$tag" \
    timeout --kill-after=15 $((SC_TIMEOUT + 30)) node "$BOTS/$file.js" > "$log" 2>&1
  local code=$?
  local res; res=$(grep -a '^RESULT ' "$log" | tail -n 1)
  local counts; counts=$(echo "$res" | sed -n 's/^RESULT [^ ]* [A-Z]* //p')
  local status=FAIL
  [ "$code" = 0 ] && status=PASS
  # 실패가 모두 MISS(기능이 아직 없다)뿐이면 따로 표시한다
  [ "$code" = 1 ] && echo "$counts" | grep -q 'fail=0 miss=[1-9]' && status="MISS"
  [ "$code" = 3 ] && status="FAIL(중단)"
  [ "$code" = 124 ] || [ "$code" = 137 ] && status="FAIL(시간 초과)"
  [ -z "$res" ] && [ "$code" != 0 ] && status="FAIL(시험 틀 오류 $code)"
  printf '%-10s %-24s %s\n' "$status" "$label" "$counts"
  if [ "$code" != 0 ]; then
    FAILED=$((FAILED + 1))
    grep -a -E '^ *[0-9.]+  (FAIL|MISS)' "$log" | sed 's/^ */           /' | cut -c1-260
    [ -z "$res" ] && tail -n 8 "$log" | sed 's/^/           | /'
  fi
  SUMMARY+=("$status $label")
}

say "-- 시나리오"
if [ -n "$REPRO" ]; then
  r_status=${REPRO%% *}; r_rest=${REPRO#* }
  printf '%-10s %-24s %s\n' "$r_status" pack_repro "${r_rest#pack_repro }"
  [ "$r_status" = PASS ] || FAILED=$((FAILED + 1))
  SUMMARY+=("$r_status pack_repro")
fi
# 문구 관문 (10.3, 12.5, 13.7): ko/en 열쇠·자리·꼴, Java 의 한글 문자열, 열쇠 부르기, jar 안 팩의 언어 파일, 폭, 글 검사
if [ -z "$ONLY" ] || want lang_check; then
  LC_ARGS=""
  [ -s "$RUN/pack.zip" ] && LC_ARGS="--pack $RUN/pack.zip"
  if python3 "$HERE/langcheck.py" $LC_ARGS > "$RUN/logs/lang_check.log" 2>&1 && python3 "$HERE/textlint.py" >> "$RUN/logs/lang_check.log" 2>&1; then
    printf '%-10s %-24s %s\n' PASS lang_check "$(grep -a -h -E '^(langcheck|textlint):' "$RUN/logs/lang_check.log" | tr '\n' ' ')"
    SUMMARY+=("PASS lang_check")
  else
    printf '%-10s %-24s %s\n' FAIL lang_check "($RUN/logs/lang_check.log)"
    grep -a -E '\[오류\]' "$RUN/logs/lang_check.log" | head -n 8 | cut -c1-240 | sed 's/^/           /'
    FAILED=$((FAILED + 1))
    SUMMARY+=("FAIL lang_check")
  fi
fi
for s in $ALL_SCENARIOS; do
  want "$s" || continue
  run_one "$s" "$s" "${BOT[$s]}" "$PORT"
done

# 지연 프록시로 구르기·무적 다시 (13.3)
if [ -n "$LAG" ] && want roll_iframes; then
  i=0
  for rtt in $LAG; do
    i=$((i + 1))
    pp=$((PORT + 2000 + 10 * i))
    port_busy "$pp" && { say "FAIL       roll_iframes@lag$rtt     프록시 포트 $pp 를 누가 쓰고 있다"; FAILED=$((FAILED + 1)); SUMMARY+=("FAIL roll_iframes@lag$rtt"); continue; }
    node "$BOTS/lagproxy.js" --listen "$pp" --target "127.0.0.1:$PORT" --rtt "$rtt" --quiet > "$RUN/logs/lagproxy-$rtt.log" 2>&1 &
    ppid=$!
    PROXY_PIDS="$PROXY_PIDS $ppid"
    for _ in $(seq 1 50); do grep -q 'LAGPROXY ready' "$RUN/logs/lagproxy-$rtt.log" 2>/dev/null && break; sleep 0.1; done
    if ! grep -q 'LAGPROXY ready' "$RUN/logs/lagproxy-$rtt.log"; then
      say "FAIL       roll_iframes@lag$rtt     지연 프록시가 켜지지 않았다"; FAILED=$((FAILED + 1)); SUMMARY+=("FAIL roll_iframes@lag$rtt"); continue
    fi
    run_one "roll_iframes@lag$rtt" roll_iframes "${BOT[lag]}" "$pp" "$rtt"
    kill "$ppid" 2>/dev/null
  done
fi

# 자기 화면 기준 피한 비율 (roll_iframes 의 SCREENDODGE 줄, 지연별). 대기열(3.9)이 없는 M0 의 기준선이라 판정하지 않는다
SD=$(grep -a -h '^SCREENDODGE ' "$RUN"/logs/roll_iframes*.log 2>/dev/null | sed 's/^SCREENDODGE //' | sort -t= -k2 -n | tr '\n' ';')
[ -n "$SD" ] && printf '%-10s %-24s %s\n' NOTE screen_dodge "${SD%;}"

# 시험하는 동안 서버 기록에 남은 오류. 켜지는 동안의 줄은 t1_boot 가 보니, 여기서는 Done 뒤를 본다.
# 플러그인 끄기(onDisable)와 세계 저장의 오류도 잡도록 서버를 먼저 끄고 꺼질 때까지 기다린 뒤 본다
ERR_RE='(ERROR|SEVERE)\]|Exception|Caused by:'
if [ "$KEEP" = 1 ]; then
  say "   (--keep-running: 서버를 끄지 않아 끄는 동안의 기록은 보지 않는다)"
else
  stop_server
fi
awk 'f; /Done \(/{f=1}' "$SRV/console.log" > "$RUN/logs/server-after-boot.log"
ERRS=$(grep -a -n -E "$ERR_RE" "$RUN/logs/server-after-boot.log" | head -n 6)
STOPPED=$(grep -a -c 'Disabling Soulslike' "$RUN/logs/server-after-boot.log")
if [ -n "$ERRS" ]; then
  printf '%-10s %-24s %s\n' FAIL server_log "켠 뒤·끌 때 오류 $(grep -a -c -E "$ERR_RE" "$RUN/logs/server-after-boot.log")줄"
  echo "$ERRS" | cut -c1-240 | sed 's/^/           /'
  FAILED=$((FAILED + 1))
  SUMMARY+=("FAIL server_log")
elif [ "$KEEP" != 1 ] && [ "$STOPPED" = 0 ]; then
  printf '%-10s %-24s %s\n' FAIL server_log "끄는 기록(Disabling Soulslike)이 없다 (강제로 꺼졌다)"
  FAILED=$((FAILED + 1))
  SUMMARY+=("FAIL server_log")
else
  printf '%-10s %-24s %s\n' PASS server_log "켠 뒤·끌 때 오류 없음"
  SUMMARY+=("PASS server_log")
fi

# 두 번째 기동: 같은 세계로 다시 켠다. 새로 만들지 않고 (level.dat 이 있다), 난이도는 이미 normal, 시험 방은 그대로
if [ "$KEEP" != 1 ] && { [ -z "$ONLY" ] || want second_boot; }; then
  if start_server console-2.log; then
    sleep 3
    stop_server
    L2="$SRV/console-2.log"
    bad=""
    grep -a -q '을 새로 만들어 난이도를' "$L2" && bad="$bad 세계를 새로 만들었다고 한다;"
    grep -a -q -E '\[Soulslike\].*난이도가 .* 입니다' "$L2" && bad="$bad 난이도 띠가 나왔다;"
    grep -a -q '시험 방은 이미 지었습니다' "$L2" || bad="$bad 시험 방을 다시 지었다 (이미 지었다는 줄이 없다);"
    n2=$(grep -a -c -E "$ERR_RE" "$L2")
    [ "$n2" = 0 ] || bad="$bad 오류 ${n2}줄;"
    grep -a -q 'Disabling Soulslike' "$L2" || bad="$bad 끄는 기록이 없다;"
    if [ -z "$bad" ]; then
      printf '%-10s %-24s %s\n' PASS second_boot "새로 만들지 않음, 난이도 경고 없음, 시험 방 그대로, 오류 없음"
      SUMMARY+=("PASS second_boot")
    else
      printf '%-10s %-24s %s\n' FAIL second_boot "$bad"
      FAILED=$((FAILED + 1))
      SUMMARY+=("FAIL second_boot")
    fi
  else
    printf '%-10s %-24s %s\n' FAIL second_boot "다시 켜지지 않았다 ($SRV/console-2.log)"
    FAILED=$((FAILED + 1))
    SUMMARY+=("FAIL second_boot")
  fi
fi

printf '%s\n' "${SUMMARY[@]}" > "$RUN/summary.txt"
say "-- 끝: 실패 $FAILED  (기록 $RUN/logs, 판정 $RUN/results, 요약 $RUN/summary.txt, 서버 기록 $SRV/console.log)"
[ "$FAILED" = 0 ]
