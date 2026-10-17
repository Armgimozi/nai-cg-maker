#!/usr/bin/env bash
# 미궁 라비린스 — 마을이 미리 지어진 배포용 월드 만들기 (VILLAGE.md §4.6).
#   테스트 서버를 임시 폴더로 복사(world 없이) → level-seed=<시드> 로 새 월드 → 최신 플러그인으로
#   village build → village pregen 192 → village selftest → village dump → stop
#   → world 폴더(session.lock·uid.dat·미궁 공허 월드 제외)를 dist/world.zip 으로.
# 사용: tools/build_world.sh <시드> [<x> <z> <north|east|south|west>]
#   자리·방향을 안 주면 계획기가 월드 스폰 둘레 64칸에서 고른다 (village survey 로 미리 골라 두는 것을 권장).
#      tools/build_world.sh --base <예전 world.zip> [--district <mine|homes>] [<구역 자리>]       (증분 빌드, CONTRACT §2.13)
#   예전 배포 월드를 그대로 풀어 마을·지은 구역은 건드리지 않고 그 구역만 짓는다: village district build <id> <자리> → village selftest
#   (마을 mismatched=0 + 지은 구역 자가 진단 깨끗) → zip. 시드 = 예전 zip 옆 world.seed. 서버를 켜 둔 동안 random_tick_speed 0 ·
#   몹 스폰 끔 (잔디·잎·몹이 바뀌지 않게) — 끝나면 게임 규칙 파일은 예전 zip 것으로 되돌린다 (서버장 월드의 규칙은 그대로).
#   --district 기본 = mine (자리 east) · 0.3.7 homes (자리 south_west — 광산이 지어진 0.3.6.1 world.zip 위에). 예전 zip 에 그 구역이 이미
#   있으면 멈춘다. 집 구역은 맡긴 짐(labyrinth-parcels/)을 zip 에 넣지 않고, 소유 파일(labyrinth-plots.yml)은 주인 없는 새 파일
#   (fresh_world: true — 처음 켤 때 이사 기간·옛 건물 조사 없이 잠금을 켬)로 바꿔 넣는다.
# 환경 변수: TESTSERVER=/opt/testserver (paper.jar·libraries·cache 를 가져올 곳, 그 안의 world 는 건드리지 않음)
#            WORK=/opt/worldbuild/build (작업 폴더, 매번 새로) · PORT=25631 · PREGEN=192 · KEEP=1 이면 작업 폴더 남김
#            DIST=<결과 폴더> (기본 dist — 시험 빌드를 따로 모을 때) · XMX=4G (서버 최대 메모리)
# 결과: dist/world.zip · dist/world.seed · dist/world-build.log (자가 진단 줄 포함) · dist/village-dump.txt (render.py --dump 용)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
BASE=""
DISTRICT=mine
if [ "${1:-}" = "--base" ]; then
  BASE=$(readlink -f "${2:?"사용: tools/build_world.sh --base <예전 world.zip> [--district <id>] [자리]"}")
  [ -f "$BASE" ] || { echo "예전 world.zip 이 없습니다: $BASE"; exit 1; }
  shift 2
  if [ "${1:-}" = "--district" ]; then DISTRICT=${2:?"--district <mine|homes>"}; shift 2; fi
  case "$DISTRICT" in
    mine) DNAME="광산 마을"; DSITE=east;;
    homes) DNAME="집 구역"; DSITE=south_west;;
    *) echo "모르는 구역: $DISTRICT (mine · homes)"; exit 1;;
  esac
  SITE=${1:-$DSITE}
  SEED=$(cat "${BASE%.zip}.seed" 2>/dev/null || true)
  [ -n "$SEED" ] || { echo "${BASE%.zip}.seed 가 없습니다 (예전 world.zip 의 시드)"; exit 1; }
  BX=""; BZ=""; BDIR=""
else
  SEED=${1:?"사용: tools/build_world.sh <시드> [<x> <z> <방향>] · tools/build_world.sh --base <예전 world.zip> [자리]"}
  BX=${2:-}; BZ=${3:-}; BDIR=${4:-}
fi
TESTSERVER=${TESTSERVER:-/opt/testserver}
WORK=${WORK:-/opt/worldbuild/build}
PORT=${PORT:-25631}
PREGEN=${PREGEN:-192}
XMX=${XMX:-4G}
DIST=${DIST:-$ROOT/dist}
JAVA=${JAVA:-$( [ -x /opt/jdk25/bin/java ] && echo /opt/jdk25/bin/java || echo java )}
PY=${PYTHON:-$( [ -x /opt/packvenv/bin/python ] && echo /opt/packvenv/bin/python || echo python3 )}
JAR=$(ls -t plugin/build/libs/labyrinth-*.jar 2>/dev/null | grep -v -E 'sources|javadoc' | head -n 1 || true)
[ -n "$JAR" ] || { echo "플러그인 jar 가 없습니다 — 먼저 (cd plugin && ./gradlew build)"; exit 1; }
[ -f "$TESTSERVER/paper.jar" ] || { echo "$TESTSERVER/paper.jar 가 없습니다"; exit 1; }
if [ -n "$BASE" ]; then
  echo "== 배포 월드 증분 빌드: 예전 $(basename "$BASE") (시드 $SEED) + $DNAME ($DISTRICT $SITE) · 플러그인 $(basename "$JAR") =="
else
  echo "== 배포 월드 만들기: 시드 $SEED ${BX:+· 자리 ($BX, $BZ) $BDIR} · 플러그인 $(basename "$JAR") =="
fi

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
# 구역 자동 짓기도 끈다 (광산 mine.district · 집 homes.district — 증분 빌드는 명령으로 자리를 정해 짓는다 · 새 월드는 마을이 지어지기 전에 돌지 않게),
# 광산 월드도 끈다 (world.zip 에 labyrinth_mine 이 들어가지 않게 — 서버장 서버가 처음 켤 때 만든다). 집 모듈(homes.enabled)은 켜 둔다.
sed -e '/^pack:/,/^[a-z]/ s/^  enabled: true/  enabled: false/' \
    -e '/^wild:/,/^[a-z]/ s/^  border: true/  border: false/' \
    -e '/^wild:/,/^[a-z]/ s/^  spawns: all/  spawns: none/' \
    -e '/^mine:/,/^[a-z]/ s/^  enabled: true/  enabled: false/' \
    -e '/^mine:/,/^[a-z]/ s/auto_build: true/auto_build: false/' \
    -e '/^homes:/,/^[a-z]/ s/auto_build: true/auto_build: false/' \
    plugin/src/main/resources/config.yml > "$WORK/plugins/Labyrinth/config.yml"
CFG="$WORK/plugins/Labyrinth/config.yml"
grep -qE '^  border: false' "$CFG" && grep -qE '^  spawns: none' "$CFG" \
  && sed -n '/^mine:/,/^[a-z]/p' "$CFG" | grep -qE 'auto_build: false' \
  && { ! grep -qE '^homes:' "$CFG" || sed -n '/^homes:/,/^[a-z]/p' "$CFG" | grep -qE 'auto_build: false'; } \
  || { echo "config.yml 의 wild·mine.district·homes.district 를 끄지 못했습니다 (키 모양이 바뀜?) — tools/build_world.sh 를 고치세요"; exit 1; }
if [ -n "$BASE" ]; then
  # 예전 배포 월드를 그대로 (잠금·UID 없이)
  "$PY" - "$BASE" "$WORK" <<'PYEOF'
import os, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(src) as z:
    names = z.namelist()
    bad = [n for n in names if not n.startswith("world/") or ".." in n.split("/")]
    if bad:
        sys.exit("예전 world.zip 안에 world/ 밖 경로: %s" % bad[:3])
    z.extractall(dst)
for f in ("session.lock", "uid.dat"):
    p = os.path.join(dst, "world", f)
    if os.path.exists(p):
        os.remove(p)
print("  예전 월드 풀기: 파일 %d개" % len(names))
PYEOF
  [ -f "$WORK/world/dimensions/minecraft/overworld/labyrinth-village.yml" ] || { echo "예전 world.zip 에 마을이 없습니다"; exit 1; }
  [ ! -f "$WORK/world/dimensions/minecraft/overworld/labyrinth-district-$DISTRICT.yml" ] || { echo "예전 world.zip 에 이미 $DNAME 이(가) 있습니다"; exit 1; }
fi
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
if [ -n "$BASE" ]; then
{
  echo "gamerule random_tick_speed 0"
  echo "gamerule spawn_mobs false"
  echo "sleep 3"
  echo "labadmin village district build $DISTRICT $SITE"
  echo "wait \[$DNAME\] 지었습니다|\[$DNAME\] 짓지 않았습니다|$DNAME 짓기 중 오류|마을이 없습니다|이미 지어져 1800"
  echo "abort \[$DNAME\] 짓지 않았습니다|$DNAME 짓기 중 오류"
  echo "sleep 12"
  echo "labadmin village selftest"
  echo "wait \[$DNAME 자가 진단\] 결과 900"
  echo "sleep 3"
  echo "labadmin village district info $DISTRICT"
  echo "labadmin village info"
  echo "labadmin village dump $DISTRICT"
  echo "wait 덤프 완료|마을 덤프 중 오류 600"
  echo "save-all flush"
  echo "sleep 5"
} > "$CMDS"
else
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
fi

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
) | (cd "$WORK" && timeout 7200 "$JAVA" -Xms1G -Xmx"$XMX" -Xshare:off -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -jar paper.jar --nogui > run.out 2>&1) || true

mkdir -p "$DIST"
grep -E "\[마을|\[광산 마을|\[집 구역|\[집터|\[집 메뉴|마을 짓기|마을을 지었|구역 짓기|계획:|지형|나무:|표지판|통과 —|막힘|짓기 시작|청크 미리 생성 완료|덤프 완료|자가 진단|Exception|ERROR.*Labyrinth" "$LOG" \
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
if [ -n "$BASE" ]; then
  OW="$W/dimensions/minecraft/overworld"
  for id in mine $DISTRICT; do
    DM="$OW/labyrinth-district-$id.yml"
    [ -f "$DM" ] && grep -q "^state: built" "$DM" || { echo "구역 $id 이(가) 지어져 있지 않습니다 ($DIST/world-build.log)"; exit 1; }
  done
  DSELF=$(grep -h "\[$DNAME 자가 진단\] 결과" "$LOG" | tail -n 1 || true)
  KEYS="예외 0 |mismatched=0 |overlaps=0 |floating=0 |tree_remnants=0 |blocked_doors=0 |path_steps=0 |junction=ok "
  [ "$DISTRICT" = "homes" ] && KEYS="$KEYS|plots=10/10 |pads=10/10 |under=10/10 |gates=10/10 |signs=10/10 |homes_safe=10/10 |border=ok |pvp_safe=ok"
  IFS='|' read -r -a KARR <<< "$KEYS"
  for k in "${KARR[@]}"; do
    echo "$DSELF " | grep -q "$k" || { echo "$DNAME 자가 진단이 깨끗하지 않습니다 ($k): ${DSELF:-(결과 줄 없음)}"; [ "${ALLOW_DIRTY:-0}" = "1" ] || exit 1; }
  done
  if [ "$DISTRICT" != "mine" ]; then
    MSELF=$(grep -h "\[광산 마을 자가 진단\] 결과" "$LOG" | tail -n 1 || true)
    echo "$MSELF" | grep -q "예외 0 " && echo "$MSELF" | grep -q "mismatched=0 " \
      || { echo "광산 마을 자가 진단이 깨끗하지 않습니다: ${MSELF:-(결과 줄 없음)}"; [ "${ALLOW_DIRTY:-0}" = "1" ] || exit 1; }
  fi
  # 집 모듈이 만든 소유 파일·맡긴 짐·옛 건물 보고는 배포 월드에 넣지 않는다 (서버장 서버가 처음 켤 때 새로 — 주인 0)
  rm -rf "$OW/labyrinth-plots.yml" "$OW/labyrinth-plots.yml.tmp" "$OW/labyrinth-plots.yml.broken-"* "$OW/labyrinth-parcels"
  # 집 구역이 지어진 배포 월드: 주인 없는 소유 파일 + 새 월드 표시 (옮길 옛 건물이 없으니 이사 기간 없이 잠금 — 0.3.7 fix)
  if [ -f "$OW/labyrinth-district-homes.yml" ] && grep -q "^state: built" "$OW/labyrinth-district-homes.yml"; then
    "$PY" "$ROOT/tools/village/fresh_plots.py" "$OW/labyrinth-plots.yml"
  fi
  # 게임 규칙은 예전 zip 것으로 (켜 둔 동안만 random_tick_speed 0 · 몹 스폰 끔)
  "$PY" - "$BASE" "$WORK" <<'PYEOF'
import sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(src) as z:
    n = 0
    for name in z.namelist():
        if name.endswith("data/minecraft/game_rules.dat"):
            with open(dst + "/" + name, "wb") as f:
                f.write(z.read(name))
            n += 1
print("  게임 규칙 되돌림: %d개 차원" % n)
PYEOF
fi
[ -f "$WORK/plugins/Labyrinth/village/dump.txt" ] && cp "$WORK/plugins/Labyrinth/village/dump.txt" "$DIST/village-dump.txt"
[ -n "$BASE" ] && [ -f "$WORK/plugins/Labyrinth/village/dump-$DISTRICT.txt" ] && cp "$WORK/plugins/Labyrinth/village/dump-$DISTRICT.txt" "$DIST/district-$DISTRICT-dump.txt"

# 4. world.zip (session.lock · uid.dat · 미궁 공허 월드 · 플레이어 데이터 제외)
"$PY" - "$W" "$DIST/world.zip" <<'PYEOF'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
skip_files = {"session.lock", "uid.dat", "labyrinth-plots.yml.tmp"}
skip_dirs = {os.path.join("dimensions", "minecraft", "labyrinth_world"), os.path.join("dimensions", "minecraft", "labyrinth_mine"),
             os.path.join("dimensions", "minecraft", "overworld", "labyrinth-parcels"),
             "players", "playerdata", "advancements", "stats"}
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
