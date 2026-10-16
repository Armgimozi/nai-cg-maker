#!/usr/bin/env bash
# 미궁 라비린스 — 마을이 미리 지어진 배포용 월드 만들기 (VILLAGE.md §4.6).
#   테스트 서버를 임시 폴더로 복사(world 없이) → level-seed=<시드> 로 새 월드 → 최신 플러그인으로
#   village build → village pregen 192 → village selftest → village dump → stop
#   → world 폴더(session.lock·uid.dat·미궁 공허 월드 제외)를 dist/world.zip 으로.
# 사용: tools/build_world.sh <시드> [<x> <z> <north|east|south|west>]
#   자리·방향을 안 주면 계획기가 월드 스폰 둘레 64칸에서 고른다 (village survey 로 미리 골라 두는 것을 권장).
# 환경 변수: TESTSERVER=/opt/testserver (paper.jar·libraries·cache 를 가져올 곳, 그 안의 world 는 건드리지 않음)
#            WORK=/opt/worldbuild/build (작업 폴더, 매번 새로) · PORT=25631 · PREGEN=192 · KEEP=1 이면 작업 폴더 남김
#            DIST=<결과 폴더> (기본 dist — 시험 빌드를 따로 모을 때)
# 결과: dist/world.zip · dist/world.seed · dist/world-build.log (자가 진단 줄 포함) · dist/village-dump.txt (render.py --dump 용)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
SEED=${1:?"사용: tools/build_world.sh <시드> [<x> <z> <방향>]"}
BX=${2:-}; BZ=${3:-}; BDIR=${4:-}
TESTSERVER=${TESTSERVER:-/opt/testserver}
WORK=${WORK:-/opt/worldbuild/build}
PORT=${PORT:-25631}
PREGEN=${PREGEN:-192}
DIST=${DIST:-$ROOT/dist}
JAVA=${JAVA:-$( [ -x /opt/jdk25/bin/java ] && echo /opt/jdk25/bin/java || echo java )}
PY=${PYTHON:-$( [ -x /opt/packvenv/bin/python ] && echo /opt/packvenv/bin/python || echo python3 )}
JAR=$(ls -t plugin/build/libs/labyrinth-*.jar 2>/dev/null | grep -v -E 'sources|javadoc' | head -n 1 || true)
[ -n "$JAR" ] || { echo "플러그인 jar 가 없습니다 — 먼저 (cd plugin && ./gradlew build)"; exit 1; }
[ -f "$TESTSERVER/paper.jar" ] || { echo "$TESTSERVER/paper.jar 가 없습니다"; exit 1; }
echo "== 배포 월드 만들기: 시드 $SEED ${BX:+· 자리 ($BX, $BZ) $BDIR} · 플러그인 $(basename "$JAR") =="

# 1. 서버 복사 (world·logs·플러그인 데이터 없이 — 테스트 서버 world 는 그대로 둔다)
rm -rf "$WORK"
mkdir -p "$WORK/plugins/Labyrinth"
for f in paper.jar eula.txt bukkit.yml commands.yml server.properties; do
  [ -e "$TESTSERVER/$f" ] && cp -a "$TESTSERVER/$f" "$WORK/"
done
for d in libraries cache versions config .paper; do
  [ -e "$TESTSERVER/$d" ] && cp -a "$TESTSERVER/$d" "$WORK/"
done
cp "$JAR" "$WORK/plugins/Labyrinth.jar"
# 리소스팩 HTTP 는 끈다 (8163 포트를 다른 서버와 다투지 않게)
# 야생 막기(wild)도 끈다 — 배포 월드에 우리 경계(world_border)가 구워지지 않게, pregen 하는 청크에 동물(CHUNK_GEN)이 생기게.
#   경계는 서버장 서버가 처음 켤 때 정하고 기록(월드 폴더 labyrinth-wild-border.yml)을 남긴다.
sed -e '/^pack:/,/^[a-z]/ s/^  enabled: true/  enabled: false/' \
    -e '/^wild:/,/^[a-z]/ s/^  border: true/  border: false/' \
    -e '/^wild:/,/^[a-z]/ s/^  spawns: all/  spawns: none/' \
    plugin/src/main/resources/config.yml > "$WORK/plugins/Labyrinth/config.yml"
grep -qE '^  border: false' "$WORK/plugins/Labyrinth/config.yml" && grep -qE '^  spawns: none' "$WORK/plugins/Labyrinth/config.yml" \
  || { echo "config.yml 의 wild 를 끄지 못했습니다 (키 모양이 바뀜?) — tools/build_world.sh 를 고치세요"; exit 1; }
P="$WORK/server.properties"
touch "$P"
setprop() { if grep -q "^$1=" "$P"; then sed -i "s|^$1=.*|$1=$2|" "$P"; else echo "$1=$2" >> "$P"; fi; }
setprop level-seed "$SEED"
setprop level-name world
setprop level-type 'minecraft\:normal'
setprop generate-structures true
setprop server-port "$PORT"
setprop query.port "$PORT"
setprop online-mode false
setprop white-list true
setprop view-distance 6
setprop simulation-distance 4

# 2. 명령 (한 줄 = 콘솔 명령, "wait <정규식> [초]" = 그 줄이 로그에 나올 때까지, "abort <정규식>" = 그 줄이 나왔으면 바로 끄기)
CMDS="$WORK/commands.txt"
{
  if [ -n "$BX" ]; then echo "labadmin village build $BX $BZ $BDIR"; else echo "labadmin village build"; fi
  echo "wait 마을을 지었습니다|여기에는 마을을 지을 수 없습니다|마을 짓기 중 오류 1800"
  echo "abort 여기에는 마을을 지을 수 없습니다|마을 짓기 중 오류"
  echo "labadmin village pregen $PREGEN"
  echo "wait 청크 미리 생성 완료|청크 미리 생성 중 오류 1800"
  echo "labadmin village selftest"
  echo "wait \[마을 자가 진단\] 결과 900"
  echo "labadmin village info"
  echo "labadmin village dump"
  echo "wait 덤프 완료|마을 덤프 중 오류 600"
  echo "save-all flush"
  echo "sleep 5"
} > "$CMDS"

LOG="$WORK/logs/latest.log"
(
  cd "$WORK"
  until grep -q 'Done (' "$LOG" 2>/dev/null; do sleep 1; done
  mark=1
  while IFS= read -r line; do
    case "$line" in
      sleep\ *) sleep "${line#sleep }";;
      wait\ *)
        rest=${line#wait }; t=900
        if [[ "$rest" =~ ^(.*)\ ([0-9]+)$ ]]; then rest=${BASH_REMATCH[1]}; t=${BASH_REMATCH[2]}; fi
        i=0
        until tail -n +"$mark" "$LOG" | grep -qE "$rest"; do
          sleep 1; i=$((i+1)); if [ $i -ge "$t" ]; then echo "[build_world] 기다리다 시간 초과: $rest" >&2; break; fi
        done;;
      abort\ *)
        if tail -n +"$mark" "$LOG" | grep -qE "${line#abort }"; then echo "[build_world] 중단: 짓기 실패" >&2; break; fi;;
      ""|\#*) ;;
      *) mark=$(wc -l < "$LOG"); echo "$line";;
    esac
  done < "$CMDS"
  sleep 3; echo stop
) | (cd "$WORK" && timeout 7200 "$JAVA" -Xms1G -Xmx4G -Xshare:off -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -jar paper.jar --nogui > run.out 2>&1) || true

mkdir -p "$DIST"
grep -E "\[마을|마을 짓기|마을을 지었|계획:|지형|나무:|표지판|청크 미리 생성 완료|덤프 완료|자가 진단|Exception|ERROR.*Labyrinth" "$LOG" \
  | grep -v "PaperVersionFetcher" > "$DIST/world-build.log" || true
cat "$DIST/world-build.log" | sed 's/^\[[0-9:]*\] \[[^]]*\]: //' | grep -v "· [0-9]*%$" | tail -n 40

# 3. 확인: 마을이 지어졌고 자가 진단이 깨끗한가
W="$WORK/world"
META="$W/dimensions/minecraft/overworld/labyrinth-village.yml"
[ -f "$META" ] || { echo "마을 메타데이터가 없습니다 — 짓기 실패 ($DIST/world-build.log)"; exit 1; }
SELF=$(grep -h "\[마을 자가 진단\] 결과" "$LOG" | tail -n 1 || true)
echo "$SELF" | grep -q "예외 0 " && echo "$SELF" | grep -q "mismatched=0 " && echo "$SELF" | grep -q "overlaps=0 " \
  && echo "$SELF" | grep -q "floating=0 " && echo "$SELF" | grep -q "tree_remnants=0 " && echo "$SELF" | grep -q "blocked_doors=0 " \
  || { echo "자가 진단이 깨끗하지 않습니다: ${SELF:-(결과 줄 없음)}"; [ "${ALLOW_DIRTY:-0}" = "1" ] || exit 1; }
[ -f "$WORK/plugins/Labyrinth/village/dump.txt" ] && cp "$WORK/plugins/Labyrinth/village/dump.txt" "$DIST/village-dump.txt"

# 4. world.zip (session.lock · uid.dat · 미궁 공허 월드 · 플레이어 데이터 제외)
"$PY" - "$W" "$DIST/world.zip" <<'PYEOF'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
skip_files = {"session.lock", "uid.dat"}
skip_dirs = {os.path.join("dimensions", "minecraft", "labyrinth_world"), "players", "playerdata", "advancements", "stats"}
n = 0
with zipfile.ZipFile(out + ".tmp", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for base, dirs, files in os.walk(src):
        rel = os.path.relpath(base, src)
        dirs[:] = sorted(d for d in dirs if os.path.normpath(os.path.join(rel, d)) not in skip_dirs)
        for fn in sorted(files):
            if fn in skip_files:
                continue
            p = os.path.join(base, fn)
            arc = os.path.join("world", os.path.relpath(p, src)).replace(os.sep, "/")
            z.write(p, arc)
            n += 1
os.replace(out + ".tmp", out)
print("  world.zip: 파일 %d개" % n)
PYEOF
echo "$SEED" > "$DIST/world.seed"
echo "완성: $DIST/world.zip ($(du -h "$DIST/world.zip" | cut -f1)) · 시드 $SEED (world.seed — release/server.properties 의 level-seed 와 같게)"
grep -E "^(rotation|radius):" "$META" || true
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORK"
