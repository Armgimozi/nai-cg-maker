#!/usr/bin/env bash
# 명소 모형 미리보기: 가짜 Roblox 환경에서 모든 명소를 만들어 검사하고, 고른 명소를 4방향 그림으로 렌더링.
# 사용법(roblox-rng 폴더에서): tools/model_preview/preview.sh eiffel,tajmahal out.png [크기=260]
set -euo pipefail
cd "$(dirname "$0")/../.."
IDS="${1:?명소 id 목록(쉼표)}"
OUT="${2:?출력 png}"
SIZE="${3:-260}"
WORK="$(mktemp -d)"
./tools/luaurun/target/release/luaurun tools/model_preview/mock.luau "$WORK" > "$WORK/out.txt" || true
grep -E "FAIL|passed|failed" "$WORK/out.txt" | grep -v "^  ok" | head -40 || true
sed -n '/^DUMP_BEGIN$/,/^DUMP_END$/p' "$WORK/out.txt" | sed '1d;$d' > "$WORK/dump.json"
python3 tools/model_preview/render.py "$WORK" "$IDS" "$SIZE" "$OUT"
