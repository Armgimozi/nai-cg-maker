#!/usr/bin/env bash
# 미궁 라비린스 — 배포 zip 만들기.
#   1) 리소스팩 생성 (resourcepack/generate.py → resourcepack/dist/labyrinth-pack.zip)
#   2) 플러그인 빌드 (plugin: ./gradlew build — 테스트 포함, 최신 팩을 jar 안에 넣음)
#   3) 플러그인 ↔ 팩 에셋 id 대조 (tools/check_assets.py)
#   4) 리소스팩 공개 사본 pack-host/labyrinth-pack-<sha8>.zip (tools/check_pack_host.py --write — 새로 만들어지면 배포 가지에 커밋)
#   5) dist/Labyrinth-Server-<버전>.zip 조립 (폴더 Labyrinth-Server/) — 마을이 미리 지어진 world 폴더(dist/world.zip) 포함
# 사용: ./release.sh            (환경 변수: PYTHON=파이썬 경로, SKIP_PACK=1 이면 팩 재생성 생략, VERSION=버전 덮어쓰기)
# 배포 zip 에는 eula.txt · paper.jar 를 넣지 않는다 (EULA 는 서버 주인이 직접 동의, Paper 는 시작기가 공식 배포처에서 받음).
# world 폴더는 tools/build_world.sh <시드> 로 만든 dist/world.zip 을 풀어 넣는다 (VILLAGE.md §4.6). 시드는 release/server.properties
# 의 level-seed 와 같아야 한다 (마을 밖으로 나가도 같은 지형이 이어지게).
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(pwd)
OUT_WORLD="$ROOT/dist/world.zip"
PY=${PYTHON:-}
if [ -z "$PY" ]; then
  if [ -x /opt/packvenv/bin/python ]; then PY=/opt/packvenv/bin/python; else PY=python3; fi
fi
VERSION=${VERSION:-$(sed -n 's/^version = "\(.*\)"/\1/p' plugin/build.gradle.kts | head -n 1)}
[ -n "$VERSION" ] || { echo "버전을 읽지 못했습니다 (plugin/build.gradle.kts)"; exit 1; }
echo "== 미궁 라비린스 배포판 $VERSION =="

if [ "${SKIP_PACK:-0}" != "1" ]; then
  echo "[1/5] 리소스팩 생성"
  (cd resourcepack && "$PY" generate.py | tail -n 6)
else
  echo "[1/5] 리소스팩 생성 생략 (SKIP_PACK=1)"
fi
[ -f resourcepack/dist/labyrinth-pack.zip ] || { echo "리소스팩이 없습니다: resourcepack/dist/labyrinth-pack.zip"; exit 1; }

echo "[2/5] 플러그인 빌드 (테스트 포함)"
(cd plugin && ./gradlew build -q 2>&1 | grep -v -E '^Picked up JAVA_TOOL_OPTIONS|warning: \[deprecation\]|^\s+\^|^[0-9]+ warnings?$' || true)
JAR=$(ls -t plugin/build/libs/labyrinth-*.jar 2>/dev/null | grep -v -E 'sources|javadoc' | head -n 1 || true)
[ -n "$JAR" ] && [ -f "$JAR" ] || { echo "플러그인 jar 가 없습니다 (빌드 실패?)"; exit 1; }
# jar 안의 팩이 방금 만든 팩과 같은지
"$PY" - "$JAR" resourcepack/dist/labyrinth-pack.zip <<'PYEOF'
import hashlib, sys, zipfile
jar, pack = sys.argv[1], sys.argv[2]
inner = zipfile.ZipFile(jar).read("pack/labyrinth-pack.zip")
outer = open(pack, "rb").read()
if hashlib.sha1(inner).hexdigest() != hashlib.sha1(outer).hexdigest():
    sys.exit("jar 안의 리소스팩이 최신이 아닙니다 — plugin 을 다시 빌드하세요 (./gradlew clean build)")
print("  jar 에 최신 리소스팩 포함 확인 (sha1 %s)" % hashlib.sha1(outer).hexdigest())
PYEOF

echo "[3/5] 에셋 id 대조"
# (출력을 파일로 받은 뒤 첫 줄만 — head 로 바로 자르면 경고가 많을 때 BrokenPipe 로 멈춘다)
mkdir -p dist
"$PY" tools/check_assets.py resourcepack/dist/labyrinth-pack.zip > dist/.check_assets.log 2>&1 || { cat dist/.check_assets.log; echo "에셋 id 불일치 — 위 목록을 고치세요"; exit 1; }
# 결과 줄 ("검사 N건 · 오류 0건") — Pillow 경고 같은 줄이 앞에 와도 결과를 보여 준다
grep -m1 '^검사 ' dist/.check_assets.log || head -n 1 dist/.check_assets.log

echo "[4/5] 리소스팩 공개 사본 (config pack.public_copy 가 가리키는 파일)"
# 팩과 jar 가 확정된 뒤. 없으면 만든다 (새로 만들어져도 배포는 계속 — 배포 가지에 커밋해 올리면 공개 주소로 받을 수 있다).
# 같은 이름인데 내용이 다른 사본만 멈춘다 (주소는 같은데 다른 팩이 나가게 되므로).
"$PY" tools/check_pack_host.py --write resourcepack/dist/labyrinth-pack.zip || { echo "pack-host 사본이 지금 팩과 다릅니다 — 위 안내대로 고치세요"; exit 1; }
PACK_SHA8=$("$PY" -c 'import hashlib,sys; print(hashlib.sha1(open(sys.argv[1],"rb").read()).hexdigest()[:8])' resourcepack/dist/labyrinth-pack.zip)
PACK_HOST_COPY="$ROOT/pack-host/labyrinth-pack-$PACK_SHA8.zip"
echo "  공개 사본: $PACK_HOST_COPY"
if [ -n "$(git -C "$ROOT" status --porcelain -- "pack-host/labyrinth-pack-$PACK_SHA8.zip" 2>/dev/null)" ]; then
  echo "  (새 사본 — git add pack-host/labyrinth-pack-$PACK_SHA8.zip 후 배포 가지에 커밋해 올리세요)"
fi

echo "[5/5] 배포 폴더 조립"
WORLD_ZIP="$OUT_WORLD"
[ -f "$WORLD_ZIP" ] || { echo "마을 월드가 없습니다: $WORLD_ZIP — 먼저 tools/build_world.sh <시드> <x> <z> <방향>"; exit 1; }
SEED_PROP=$(sed -n 's/^level-seed=//p' release/server.properties | head -n 1)
SEED_WORLD=$(cat "${WORLD_ZIP%.zip}.seed" 2>/dev/null || true)
[ -n "$SEED_PROP" ] || { echo "release/server.properties 에 level-seed 가 없습니다"; exit 1; }
[ "$SEED_PROP" = "$SEED_WORLD" ] || { echo "시드가 다릅니다: server.properties $SEED_PROP · world.zip ${SEED_WORLD:-?} (${WORLD_ZIP%.zip}.seed)"; exit 1; }
OUT="$ROOT/dist"
STAGE="$OUT/stage-$VERSION"
DIR="$STAGE/Labyrinth-Server"
rm -rf "$STAGE"
mkdir -p "$DIR/plugins"
cp "$JAR" "$DIR/plugins/Labyrinth.jar"
cp resourcepack/dist/labyrinth-pack.zip "$DIR/Labyrinth-pack.zip"
"$PY" - "$DIR/Labyrinth-pack.zip" > "$DIR/Labyrinth-pack.sha1" <<'PYEOF'
import hashlib, sys
print(hashlib.sha1(open(sys.argv[1], "rb").read()).hexdigest())
PYEOF

# 템플릿: __VERSION__ 치환, 윈도우용 파일은 CRLF, PowerShell·README 는 UTF-8 BOM (5.1·메모장이 한글을 바르게 읽도록)
"$PY" - "$ROOT/release" "$DIR" "$VERSION" <<'PYEOF'
import os, sys
src, dst, ver = sys.argv[1], sys.argv[2], sys.argv[3]
rules = {
    "start.bat": ("crlf", False), "start.ps1": ("crlf", True), "README.txt": ("crlf", True),
    "LICENSE": ("crlf", False), "server.properties": ("lf", False), "start.sh": ("lf", False),
}
for name, (eol, bom) in rules.items():
    with open(os.path.join(src, name), encoding="utf-8") as f:
        text = f.read().replace("__VERSION__", ver)
    text = text.replace("\r\n", "\n")
    if eol == "crlf":
        text = text.replace("\n", "\r\n")
    data = text.encode("utf-8")
    if name == "start.bat" and any(b > 127 for b in data):
        sys.exit("start.bat 에 ASCII 가 아닌 글자가 있습니다")
    with open(os.path.join(dst, name), "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom else b"") + data)
os.chmod(os.path.join(dst, "start.sh"), 0o755)
PYEOF

# 마을 월드 (world.zip 은 world/ 로 시작한다)
"$PY" - "$WORLD_ZIP" "$DIR" <<'PYEOF'
import os, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(src) as z:
    names = z.namelist()
    bad = [n for n in names if not n.startswith("world/") or ".." in n.split("/")]
    if bad:
        sys.exit("world.zip 안에 world/ 밖 경로가 있습니다: %s" % bad[:3])
    z.extractall(dst)
meta = os.path.join(dst, "world", "dimensions", "minecraft", "overworld", "labyrinth-village.yml")
if not os.path.isfile(meta):
    sys.exit("world.zip 에 마을 메타데이터(labyrinth-village.yml)가 없습니다")
# 0.3.6.1: 광산 마을이 미리 지어져 있어야 한다 (tools/build_world.sh --base <예전 world.zip>)
dm = os.path.join(dst, "world", "dimensions", "minecraft", "overworld", "labyrinth-district-mine.yml")
if not os.path.isfile(dm) or "\nstate: built" not in open(dm, encoding="utf-8").read():
    sys.exit("world.zip 에 지어진 광산 마을(labyrinth-district-mine.yml state: built)이 없습니다 — tools/build_world.sh --base <예전 world.zip>")
if not os.path.isfile(os.path.join(dst, "world", "dimensions", "minecraft", "overworld", "labyrinth-district-mine.backup.gz")):
    sys.exit("world.zip 에 광산 마을 되돌리기 백업(labyrinth-district-mine.backup.gz)이 없습니다")
print("  마을 월드 포함 (광산 마을 지어짐): 파일 %d개" % len(names))
PYEOF

# 금지 파일 확인 (월드 잠금·UID·미궁 공허 월드는 서버가 새로 만든다)
for bad in eula.txt paper.jar world/session.lock world/uid.dat world/dimensions/minecraft/labyrinth_world world/dimensions/minecraft/labyrinth_mine; do
  [ ! -e "$DIR/$bad" ] || { echo "배포 폴더에 $bad 가 있으면 안 됩니다"; exit 1; }
done

ZIP="$OUT/Labyrinth-Server-$VERSION.zip"
rm -f "$ZIP"
"$PY" - "$STAGE" "$ZIP" <<'PYEOF'
import os, sys, zipfile
stage, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for base, dirs, files in os.walk(stage):
        dirs.sort()
        for d in dirs:
            p = os.path.join(base, d)
            info = zipfile.ZipInfo(os.path.relpath(p, stage).replace(os.sep, "/") + "/")
            info.external_attr = (0o40755 << 16) | 0x10
            z.writestr(info, b"")
        for fn in sorted(files):
            p = os.path.join(base, fn)
            arc = os.path.relpath(p, stage).replace(os.sep, "/")
            info = zipfile.ZipInfo.from_file(p, arc)
            info.compress_type = zipfile.ZIP_STORED if fn.endswith((".jar", ".zip")) else zipfile.ZIP_DEFLATED
            info.external_attr = ((0o100755 if fn.endswith(".sh") else 0o100644) << 16)
            with open(p, "rb") as f:
                z.writestr(info, f.read())
PYEOF
rm -rf "$STAGE"
echo
echo "완성: $ZIP ($(du -h "$ZIP" | cut -f1))"
echo "팩 공개 사본: $PACK_HOST_COPY"
unzip -l "$ZIP" | sed -n '4,$p' | grep -v "Labyrinth-Server/world/." | head -n 20
