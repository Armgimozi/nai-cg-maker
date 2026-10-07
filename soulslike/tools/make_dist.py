#!/usr/bin/env python3
"""
배포 파일을 묶는다.
  python3 make_dist.py

M0 에는 미리 지은 세계가 없다. 플러그인이 처음 켜질 때 souls_world 를 짓는다.

dist/
  Soulslike-Server.zip   서버 폴더 통째로 (start.bat, 설정, 플러그인)  ← 이것만 받으면 됨
  Soulslike.jar          플러그인
  packs/<sha1>.zip       리소스팩. 이름이 내용의 SHA-1 이라 raw.githubusercontent.com 캐시와 상관없다 (DESIGN.md 10.10)

묶기 전에 확인하는 것 (하나라도 어긋나면 멈춘다):
  - jar 안에 pack.zip, glyphs.yml, paper-plugin.yml 이 있다
  - jar 안 config.yml 의 pack.url 에 {sha1} 이 들어 있다
  - server/ 의 인코딩 규칙: start.bat ASCII+CRLF, start.ps1·README.txt UTF-8 BOM+CRLF, start.sh LF
"""
import hashlib
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
JAR = os.path.join(ROOT, "plugin", "build", "libs", "Soulslike.jar")
SERVER = os.path.join(ROOT, "server")
FIXED = (2026, 1, 1, 0, 0, 0)
NEEDED = ("pack.zip", "glyphs.yml", "paper-plugin.yml", "config.yml")


def fail(msg):
    sys.exit(f"묶지 않음: {msg}")


def check_jar():
    if not os.path.isfile(JAR):
        fail(f"{JAR} 가 없다 (pack/gen_pack.py 다음에 gradle build)")
    with zipfile.ZipFile(JAR) as z:
        names = set(z.namelist())
        for n in NEEDED:
            if n not in names:
                fail(f"jar 안에 {n} 이 없다")
        pack = z.read("pack.zip")
        config = z.read("config.yml").decode("utf-8")
    url = re.search(r"^\s*url:\s*['\"]?([^'\"\n]+)", config.split("pack:", 1)[-1], re.M)
    if not url or "{sha1}" not in url.group(1):
        fail("config.yml 의 pack.url 에 {sha1} 이 없다")
    return pack


def check_server():
    def raw(name):
        with open(os.path.join(SERVER, name), "rb") as f:
            return f.read()
    bat = raw("start.bat")
    try:
        bat.decode("ascii")
    except UnicodeDecodeError:
        fail("start.bat 에 ASCII 가 아닌 글자가 있다")
    for name in ("start.ps1", "README.txt"):
        data = raw(name)
        if not data.startswith(b"\xef\xbb\xbf"):
            fail(f"{name} 가 UTF-8 BOM 으로 시작하지 않는다")
    for name in ("start.bat", "start.ps1", "README.txt"):
        data = raw(name)
        if data.count(b"\n") != data.count(b"\r\n"):
            fail(f"{name} 의 줄 끝이 CRLF 가 아니다")
    if b"\r\n" in raw("start.sh"):
        fail("start.sh 의 줄 끝이 LF 가 아니다")


def add_file(z, src, arc, data=None):
    zi = zipfile.ZipInfo(arc, date_time=FIXED)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = (0o755 if arc.endswith(".sh") else 0o644) << 16
    if data is None:
        with open(src, "rb") as f:
            data = f.read()
    z.writestr(zi, data)


def main():
    pack = check_jar()
    check_server()
    sha1 = hashlib.sha1(pack).hexdigest()
    os.makedirs(os.path.join(DIST, "packs"), exist_ok=True)
    with open(os.path.join(DIST, "packs", f"{sha1}.zip"), "wb") as f:
        f.write(pack)
    with open(JAR, "rb") as f, open(os.path.join(DIST, "Soulslike.jar"), "wb") as o:
        o.write(f.read())
    top = "Soulslike-Server/"
    with zipfile.ZipFile(os.path.join(DIST, "Soulslike-Server.zip"), "w") as z:
        for f in sorted(os.listdir(SERVER)):
            add_file(z, os.path.join(SERVER, f), top + f)
        add_file(z, JAR, top + "plugins/Soulslike.jar")
    for base, _, files in sorted(os.walk(DIST)):
        for f in sorted(files):
            p = os.path.join(base, f)
            print(f"{os.path.getsize(p) / 1024:8.0f} KB  {os.path.relpath(p, DIST)}")
    print(f"팩 SHA-1 {sha1} — dist/packs/{sha1}.zip 을 커밋·푸시해야 접속한 사람이 팩을 받는다")


if __name__ == "__main__":
    main()
