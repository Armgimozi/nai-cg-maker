#!/usr/bin/env bash
# Studio 없이 ArmorService / ItemService 로직을 모의 환경에서 실행해 본다.
#   roblox_items/tools/luau_test/run.sh [luau 실행파일]   (https://github.com/luau-lang/luau/releases)
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
R="$D/../../roblox"
LUAU=${1:-luau}
OUT=$(mktemp --suffix .luau)
trap 'rm -f "$OUT"' EXIT
{
	cat "$D/mock.luau"
	echo 'modules = {}'
	echo 'script = { Parent = { ItemData = "ItemData", ArmorService = "ArmorService", ItemService = "ItemService" } }'
	echo 'require = function(m) return modules[m] end'
	for m in ItemData ArmorService ItemService; do
		echo "modules.$m = (function()"
		cat "$R/$m.lua"
		echo "end)()"
	done
	cat "$D/tests.luau"
} > "$OUT"
"$LUAU" "$OUT"
