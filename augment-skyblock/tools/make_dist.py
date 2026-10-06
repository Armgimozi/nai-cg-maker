#!/usr/bin/env python3
"""
배포 파일을 묶는다.
  python3 make_dist.py <맵을 지은 world 폴더>

world 옆에 플러그인이 만든 하늘 네더 폴더(<world>_augsky_nether)도 world_augsky_nether/ 로 함께 넣는다.
그 폴더가 없거나 다 지어지지 않았으면 멈춘다 (서버를 한 번 켜서 네더가 지어진 뒤 묶는다).

dist/
  AugmentSkyblock-Server.zip   서버 폴더 통째로 (start.bat, 설정, 플러그인, 맵)  ← 이것만 받으면 됨
  AugmentSkyblock-Map.zip      맵(world, world_augsky_nether 폴더)만
  AugmentSkyblock.jar          플러그인
  AugmentSkyblock-pack.zip     리소스팩 (gen_pack.py 가 만든다)
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
JAR = os.path.join(ROOT, "plugin", "build", "libs", "AugmentSkyblock.jar")
SERVER = os.path.join(ROOT, "server")
SKIP = {"session.lock", "uid.dat"}
SKIP_DIRS = {"playerdata", "stats", "advancements"}
# 플러그인이 '<level-name>_augsky_nether' 로 만든다 (NetherService.name). 배포 서버의 level-name 은 world
NETHER = "world_augsky_nether"
NETHER_MARKER = "augsky-nether.yml"
FIXED = (2026, 1, 1, 0, 0, 0)


def add_file(z, src, arc):
    zi = zipfile.ZipInfo(arc, date_time=FIXED)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = (0o755 if arc.endswith(".sh") else 0o644) << 16
    with open(src, "rb") as f:
        z.writestr(zi, f.read())


def add_world(z, world, prefix, name="world"):
    for base, dirs, files in os.walk(world):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP:
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, world).replace(os.sep, "/")
            add_file(z, full, f"{prefix}{name}/{rel}")


def add_worlds(z, world, nether, prefix):
    add_world(z, world, prefix)
    add_world(z, nether, prefix, NETHER)


def main():
    world = os.path.normpath(sys.argv[1])
    # 네더를 빼먹거나 짓다 만 네더를 담은 zip 을 내보내지 않도록, 다 지은 표시 파일이 없으면 멈춘다
    nether = world + "_augsky_nether"
    if not os.path.isfile(os.path.join(nether, NETHER_MARKER)):
        sys.exit(f"하늘 네더 폴더가 없거나 다 지어지지 않았습니다: {nether} ({NETHER_MARKER} 없음)")
    os.makedirs(DIST, exist_ok=True)
    with open(JAR, "rb") as f, open(os.path.join(DIST, "AugmentSkyblock.jar"), "wb") as o:
        o.write(f.read())
    with zipfile.ZipFile(os.path.join(DIST, "AugmentSkyblock-Map.zip"), "w") as z:
        add_worlds(z, world, nether, "")
    top = "AugmentSkyblock-Server/"
    with zipfile.ZipFile(os.path.join(DIST, "AugmentSkyblock-Server.zip"), "w") as z:
        for f in sorted(os.listdir(SERVER)):
            add_file(z, os.path.join(SERVER, f), top + f)
        add_file(z, JAR, top + "plugins/AugmentSkyblock.jar")
        add_file(z, os.path.join(DIST, "AugmentSkyblock-pack.zip"), top + "AugmentSkyblock-pack.zip")
        add_worlds(z, world, nether, top)
    for f in sorted(os.listdir(DIST)):
        print(f"{os.path.getsize(os.path.join(DIST, f)) / 1024:8.0f} KB  {f}")


if __name__ == "__main__":
    main()
