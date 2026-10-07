#!/usr/bin/env python3
"""
실제 바닐라 클라이언트를 받는다 (DESIGN.md 13.4). run_client.sh 가 처음 한 번 부른다.

  python3 tools/client/setup_client.py [--version 1.21.11] [--client-jar 받아 둔.jar] [--sounds] [--langs ko_kr,ja_jp]

받는 곳: $SOULS_CLIENT_HOME (없으면 ~/.cache/souls-client). 내용 주소로 받으므로 여러 판이 같이 써도 된다.
  versions/<판>.json      piston-meta 의 버전 문서 (버전 목록 → 판 문서)
  versions/<판>.jar       클라이언트 jar (sha1 확인. --client-jar 가 sha1 이 맞으면 그것을 복사)
  libraries/...           리눅스 라이브러리와 네이티브 jar. 네이티브는 LWJGL 이 실행할 때 스스로 푼다
  assets/indexes/, assets/objects/
                          에셋. 소리(약 330MB)는 --sounds 일 때만, 언어 파일은 --langs 만 (기본 ko_kr).
                          글꼴(unifont)은 늘 받는다. 없으면 한국어가 네모로 나온다
  versions/<판>.launch.json   mcclient.py 가 읽는 실행 정보 (mainClass, classpath, assetIndex)

표준 라이브러리만 쓴다. HTTPS_PROXY 환경 변수를 그대로 따른다.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import shutil
import sys
import urllib.request

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
RESOURCES = "https://resources.download.minecraft.net"
DEFAULT_VERSION = "1.21.11"
DEFAULT_LANGS = "ko_kr"
# 이 이름으로 시작하는 에셋은 늘 받는다 (작고, 빠지면 화면이 달라진다)
ALWAYS = ("minecraft/font/", "minecraft/textures/", "minecraft/resourcepacks/", "minecraft/sounds.json",
          "pack.mcmeta", "icons/", "minecraft/icons/")


def home():
    return os.environ.get("SOULS_CLIENT_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "souls-client")


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dst, sha1=None, tries=3):
    """dst 에 받는다. 이미 있고 sha1 이 맞으면 건너뛴다. 받는 동안은 .part 에 써서 반쯤 받은 파일이 남지 않게 한다."""
    if os.path.isfile(dst) and (sha1 is None or sha1_of(dst) == sha1):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part = "%s.%d.part" % (dst, os.getpid())
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if sha1 and sha1_of(part) != sha1:
                raise IOError("sha1 이 다르다: " + url)
            os.replace(part, dst)
            return True
        except Exception as e:  # noqa: BLE001 - 다시 해 본다
            last = e
    if os.path.exists(part):
        os.remove(part)
    raise IOError("못 받았다: %s (%s)" % (url, last))


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def os_name():
    return {"Linux": "linux", "Darwin": "osx", "Windows": "windows"}.get(platform.system(), "linux")


def allowed(lib):
    """라이브러리 rules: 마지막으로 맞는 규칙이 이긴다. 규칙이 없으면 허용."""
    rules = lib.get("rules")
    if not rules:
        return True
    ok = False
    for rule in rules:
        cond = rule.get("os")
        if cond and cond.get("name") and cond["name"] != os_name():
            continue
        if "features" in rule:
            continue
        ok = rule["action"] == "allow"
    return ok


def wanted_arch(name):
    """네이티브 이름의 다른 CPU 판은 뺀다 (netty linux-aarch_64 등)."""
    machine = platform.machine().lower()
    arm = machine in ("aarch64", "arm64")
    if "aarch_64" in name or "arm64" in name:
        return arm
    if "x86_64" in name:
        return not arm
    return True


def asset_wanted(key, sounds, langs):
    if key.startswith("minecraft/sounds/"):
        return sounds
    if key.startswith("minecraft/lang/"):
        return os.path.splitext(os.path.basename(key))[0] in langs
    return True


def setup(version=DEFAULT_VERSION, client_jar=None, sounds=False, langs=DEFAULT_LANGS, quiet=False):
    root = home()
    vdir = os.path.join(root, "versions")
    vjson = os.path.join(vdir, version + ".json")
    say = (lambda *a: None) if quiet else (lambda *a: print("[setup]", *a, flush=True))

    if not os.path.isfile(vjson):
        man = os.path.join(vdir, "version_manifest_v2.json")
        fetch(MANIFEST, man)
        entry = next((v for v in read_json(man)["versions"] if v["id"] == version), None)
        if entry is None:
            raise SystemExit("버전 목록에 %s 이 없다" % version)
        fetch(entry["url"], vjson, entry.get("sha1"))
    meta = read_json(vjson)

    # 클라이언트 jar
    client = meta["downloads"]["client"]
    jar = os.path.join(vdir, version + ".jar")
    if not (os.path.isfile(jar) and sha1_of(jar) == client["sha1"]):
        if client_jar and os.path.isfile(client_jar) and sha1_of(client_jar) == client["sha1"]:
            shutil.copyfile(client_jar, jar + ".part")
            os.replace(jar + ".part", jar)
            say("client.jar 복사:", client_jar)
        else:
            say("client.jar 받는 중 (%d MB)" % (client["size"] >> 20))
            fetch(client["url"], jar, client["sha1"])

    # 라이브러리
    libdir = os.path.join(root, "libraries")
    jobs, classpath = [], []
    for lib in meta["libraries"]:
        art = lib.get("downloads", {}).get("artifact")
        if not art or not allowed(lib) or not wanted_arch(lib["name"]):
            continue
        dst = os.path.join(libdir, art["path"])
        classpath.append(dst)
        jobs.append((art["url"], dst, art["sha1"]))
    classpath.append(jar)

    # 에셋
    ai = meta["assetIndex"]
    adir = os.path.join(root, "assets")
    index = os.path.join(adir, "indexes", ai["id"] + ".json")
    fetch(ai["url"], index, ai["sha1"])
    lang_set = {x.strip() for x in langs.split(",") if x.strip()}
    for key, obj in read_json(index)["objects"].items():
        if not asset_wanted(key, sounds, lang_set):
            continue
        h = obj["hash"]
        jobs.append(("%s/%s/%s" % (RESOURCES, h[:2], h), os.path.join(adir, "objects", h[:2], h), h))

    todo = [j for j in jobs if not os.path.isfile(j[1])]
    if todo:
        say("받을 파일 %d 개" % len(todo))
        with concurrent.futures.ThreadPoolExecutor(16) as ex:
            got = list(ex.map(lambda j: fetch(*j), todo))
        say("받음 %d 개" % sum(got))

    launch = {
        "version": version,
        "mainClass": meta["mainClass"],
        "assetIndex": ai["id"],
        "assetsDir": adir,
        "classpath": classpath,
        "javaMajor": meta.get("javaVersion", {}).get("majorVersion", 21),
        "sounds": sounds,
        "langs": sorted(lang_set),
    }
    out = os.path.join(vdir, version + ".launch.json")
    with open(out + ".part", "w", encoding="utf-8") as f:
        json.dump(launch, f, indent=1)
    os.replace(out + ".part", out)
    say("준비됨:", out)
    return launch


def load(version=DEFAULT_VERSION):
    """준비된 실행 정보. 없거나 파일이 빠졌으면 None."""
    path = os.path.join(home(), "versions", version + ".launch.json")
    if not os.path.isfile(path):
        return None
    launch = read_json(path)
    if not all(os.path.isfile(p) for p in launch["classpath"]):
        return None
    return launch


def main():
    ap = argparse.ArgumentParser(description="바닐라 클라이언트 받기")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--client-jar", help="이미 받아 둔 client.jar (sha1 이 맞을 때만 쓴다)")
    ap.add_argument("--sounds", action="store_true", help="소리 에셋도 받는다 (약 330MB)")
    ap.add_argument("--langs", default=DEFAULT_LANGS, help="받을 언어 파일 (쉼표로). en_us 는 jar 안에 있다")
    a = ap.parse_args()
    setup(a.version, a.client_jar, a.sounds, a.langs)


if __name__ == "__main__":
    sys.exit(main())
