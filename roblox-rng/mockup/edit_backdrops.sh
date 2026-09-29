#!/usr/bin/env bash
# 목업 6번대(3D 배치 모드) 배경 그림 만들기: 맵 미리보기 도구(tools/world_preview)로 진짜 월드 + 진짜 ParkEdit 를 돌려
# 배치 모드 카메라로 본 장면을 그림(Roblox API 호출·업로드 없음).
#   mockup/bg/edit_<장면>.jpg   배경(화면 크기 그대로: pc 1280×720, phone844 844×390, phone667 667×375)
#   mockup/bg/edit_<장면>.json  hook 이 돌려준 값(카메라, 띠 자리, 들고 있는 명소 이름표·칸 이름표 화면 자리, 칸 배치, 보관함)
# 장면 = tools/world_preview/edit_hook.luau 의 SCENARIOS (목업 screen6 / screen6c / screen6p 와 같은 상태·크기).
# 그다음 python3 mockup/build.py 가 이 파일들을 index.html 에 넣음.
#
# 사용법(아무 폴더에서나): mockup/edit_backdrops.sh [장면...]   (기본: pc phone844 phone667)
#   처음 한 번: (cd tools/world_preview && npm install) — three.js. Playwright 는 전역 설치본을 씀
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
OUT="$ROOT/mockup/bg"
mkdir -p "$OUT"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

declare -A SIZES=([pc]=1280x720 [phone844]=844x390 [phone667]=667x375)
SCENES=("$@")
[ ${#SCENES[@]} -eq 0 ] && SCENES=(pc phone844 phone667)

for scene in "${SCENES[@]}"; do
	size="${SIZES[$scene]:?장면은 pc | phone844 | phone667}"
	PLAYERS="${PLAYERS:-3}" HOOK=tools/world_preview/edit_hook.luau HOOK_ARGS="edit=$scene" VIEWS=hook OVERLAP=0 KEEP=1 \
		PREVIEW_SIZE="$size" PREVIEW_JPEG=0.88 \
		tools/world_preview/preview.sh "$WORK" - "edit_$scene" | grep -e '배치 모드' -e 'render\]' -e '규칙 위반' -e 'task 오류' || true
	cp "$WORK/edit_${scene}_hook.jpg" "$OUT/edit_$scene.jpg"
	node -e '
		const fs = require("fs");
		const dump = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
		if (!dump.extra) throw new Error("덤프에 extra 가 없습니다");
		fs.writeFileSync(process.argv[2], JSON.stringify(dump.extra, null, 1) + "\n");
	' "$WORK/edit_${scene}_dump.json" "$OUT/edit_$scene.json"
	echo "[backdrops] mockup/bg/edit_$scene.jpg ($(du -k "$OUT/edit_$scene.jpg" | cut -f1) KB) + .json"
done
