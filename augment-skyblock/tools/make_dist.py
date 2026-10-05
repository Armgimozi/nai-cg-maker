#!/usr/bin/env python3
"""
배포 파일을 묶는다.
  python3 make_dist.py <맵을 지은 world 폴더>

dist/
  AugmentSkyblock-Server.zip   서버 폴더 통째로 (start.bat, 설정, 플러그인, 맵)  ← 이것만 받으면 됨
  AugmentSkyblock-Map.zip      맵(world 폴더)만
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
FIXED = (2026, 1, 1, 0, 0, 0)


def add_file(z, src, arc):
    zi = zipfile.ZipInfo(arc, date_time=FIXED)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = (0o755 if arc.endswith(".sh") else 0o644) << 16
    with open(src, "rb") as f:
        z.writestr(zi, f.read())


def add_world(z, world, prefix):
    for base, dirs, files in os.walk(world):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP:
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, world).replace(os.sep, "/")
            add_file(z, full, f"{prefix}world/{rel}")


def main():
    world = sys.argv[1]
    os.makedirs(DIST, exist_ok=True)
    with open(JAR, "rb") as f, open(os.path.join(DIST, "AugmentSkyblock.jar"), "wb") as o:
        o.write(f.read())
    with zipfile.ZipFile(os.path.join(DIST, "AugmentSkyblock-Map.zip"), "w") as z:
        add_world(z, world, "")
    top = "AugmentSkyblock-Server/"
    with zipfile.ZipFile(os.path.join(DIST, "AugmentSkyblock-Server.zip"), "w") as z:
        for f in sorted(os.listdir(SERVER)):
            add_file(z, os.path.join(SERVER, f), top + f)
        add_file(z, JAR, top + "plugins/AugmentSkyblock.jar")
        add_file(z, os.path.join(DIST, "AugmentSkyblock-pack.zip"), top + "AugmentSkyblock-pack.zip")
        add_world(z, world, top)
    for f in sorted(os.listdir(DIST)):
        print(f"{os.path.getsize(os.path.join(DIST, f)) / 1024:8.0f} KB  {f}")


if __name__ == "__main__":
    main()
