#!/usr/bin/env bash
# 맵 전체 미리보기: 올리기 전에 맵을 그림으로 확인합니다(Roblox API 호출·업로드 없음).
#   1) world.luau: 가짜 Roblox 환경에서 진짜 서버 모듈(World, ParkService, Scenery)을 돌려 파트 목록(JSON) 덤프
#   2) render.js : three.js + headless Chromium 으로 시점별 PNG (overview / spawn / edge / top, 1280x720)
#   3) overlap.js: 풍경 파트가 부지·간판 자리·길·광장·스폰·World 물체를 막는지 보고서
#
# 사용법(아무 폴더에서나): tools/world_preview/preview.sh <출력 폴더> [변형] [접두어]
#   변형  : Scenery 변형 이름(없거나 "-" 면 Config 기본값). init.server.luau 의 Scenery 호출이 읽는 Config 필드를 바꿔서 그림
#           "off" 면 풍경 없이(Scenery 를 부르지 않음)
#   접두어: 파일 이름 앞부분(기본: 변형 이름, 변형이 없으면 map) → <접두어>_overview.png ... <접두어>_overlap.txt
# 환경 변수(선택)
#   VIEWS=overview,top   일부 시점만. 임의 시점은 VIEWS="cam:x,y,z:tx,ty,tz:fov;cam:..." (→ <접두어>_cam1.png ...)
#   PLAYERS=3            전시를 채울 샘플 플레이어 수(0~8)
#   FIELD=이름           변형을 넣을 Config 필드를 직접 지정(자동으로 못 찾을 때)
#   REV=HEAD             작업 폴더 대신 git 커밋의 src/ 와 default.project.json 으로 그림(예: 올라가 있는 현재 맵)
#   KEEP=1               덤프(<접두어>_dump.json)를 출력 폴더에 남김
# 처음 한 번: (cd tools/world_preview && npm install)   — three.js. Playwright 는 전역 설치본을 씀
set -euo pipefail
OUT="${1:?출력 폴더}"
VARIANT="${2:-}"
[ "$VARIANT" = "-" ] && VARIANT=""
PREFIX="${3:-${VARIANT:-map}}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)" # 부른 곳 기준 경로를 절대 경로로(아래에서 roblox-rng 폴더로 이동)
cd "$(dirname "$0")/../.."
ROOT="$(pwd)"

if [ ! -d tools/world_preview/node_modules/three ]; then
	(cd tools/world_preview && npm install --no-audit --no-fund >/dev/null)
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ARGS=("players=${PLAYERS:-3}")
if [ "$VARIANT" = "off" ]; then
	ARGS+=("scenery=off")
elif [ -n "$VARIANT" ]; then
	ARGS+=("variant=$VARIANT")
fi
[ -n "${FIELD:-}" ] && ARGS+=("field=$FIELD")

# 게임 코드 위치: 작업 폴더 또는 REV 커밋을 풀어 둔 임시 폴더(도구 파일은 항상 지금 것을 씀)
GAME="$ROOT"
if [ -n "${REV:-}" ]; then
	GAME="$WORK/rev"
	mkdir -p "$GAME/tools/world_preview" "$GAME/tests"
	SUBDIR="$(git rev-parse --show-prefix)"
	TREE="$REV"
	[ -n "$SUBDIR" ] && TREE="$REV:${SUBDIR%/}"
	git -C "$(git rev-parse --show-toplevel)" archive "$TREE" src default.project.json | tar -x -C "$GAME"
	cp tools/roblox_mock.luau "$GAME/tools/"
	cp tools/world_preview/world.luau "$GAME/tools/world_preview/"
	cp tests/harness.luau "$GAME/tests/"
	echo "[preview] $REV ($(git rev-parse --short "$REV")) 의 src/ + default.project.json 으로 그립니다"
fi

if ! (cd "$GAME" && "$ROOT/tools/luaurun/target/release/luaurun" tools/world_preview/world.luau "${ARGS[@]}") >"$WORK/out.txt" 2>&1; then
	cat "$WORK/out.txt" >&2
	echo "world.luau 실행 실패" >&2
	exit 1
fi
grep -v -e '^DUMP_BEGIN$' -e '^DUMP_END$' -e '^{"meta"' "$WORK/out.txt" || true
sed -n '/^DUMP_BEGIN$/,/^DUMP_END$/p' "$WORK/out.txt" | sed '1d;$d' >"$WORK/dump.json"
[ -s "$WORK/dump.json" ] || {
	echo "덤프가 비었습니다" >&2
	exit 1
}

NODE_PATH="$(npm root -g)" node tools/world_preview/render.js "$WORK/dump.json" "$OUT" "$PREFIX" ${VIEWS:+"$VIEWS"}
node tools/world_preview/overlap.js "$WORK/dump.json" "$OUT/${PREFIX}_overlap.txt"
if [ -n "${KEEP:-}" ]; then
	cp "$WORK/dump.json" "$OUT/${PREFIX}_dump.json"
fi
exit 0
