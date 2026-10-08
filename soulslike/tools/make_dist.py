#!/usr/bin/env python3
"""
배포 파일을 묶는다 (DESIGN.md 12.9, 10.10, 14 M0). M0 판.

  python3 tools/make_dist.py               팩 생성(gen_pack) → gradle build → 관문 → 묶기
  python3 tools/make_dist.py --no-build    이미 있는 plugin/build/libs/Soulslike.jar 로 관문 → 묶기
  python3 tools/make_dist.py --check-url   올린 팩을 주소 틀로 내려받아 SHA-1 까지 견준다 (인터넷 필요)

dist/
  Soulslike-Server.zip   서버 폴더 통째로 (시작기, 설정, 플러그인)  ← 이것만 받으면 된다
  Soulslike.jar          플러그인 (리소스팩·데이터팩이 안에 들어 있다)
  packs/<sha1>.zip       리소스팩. 이름이 내용의 SHA-1 이라 raw.githubusercontent.com 의 캐시와 상관없다 (10.10).
                         이 파일을 커밋·푸시해야 접속한 사람이 팩을 받는다. 지난 팩은 지운다.

M0 에는 미리 지은 세계가 없다. 플러그인이 처음 켜질 때 souls_world 를 짓는다.
세계를 묶기 시작하는 M3 에서 souls-state.yml 관문(처치한 보스·밝힌 화톳불·열린 지름길이 있으면 거절,
WorldCheck 실패면 거절)을 더한다. 그때까지 server/ 에 세계 폴더가 있으면 거절한다.

관문 (하나라도 어긋나면 아무것도 쓰지 않고 멈춘다)
  글       textlint 오류 0 (13.7, 한국어와 영어, 고유 이름 표기)
  문구     langcheck 오류 0 (10.3, 12.5): lang/ko.yml 과 en.yml 의 열쇠·자리·꼴이 같다, Java 에 한글 문자열이 없다
           (서버 기록 줄만), Java·콘텐츠가 부르는 열쇠가 있다, jar 안 팩의 언어 파일이 YAML 과 같다, 글이 자리 폭에 든다
  jar      resources/ 의 파일이 jar 안과 바이트까지 같다 (낡은 jar 거르기), paper-plugin.yml (12.2),
           데이터팩 soulsdp (형식 94.1, 지역 바이옴 9개, souls:hit)
  설정     jar 안 config.yml: pack.url 이 https 이고 {sha1} 이 있다, required, serve-port 0, test-mode 꺼짐
  팩       형식 75, 셰이더는 점검한 목록 (pack/shaders.py ALLOWED: 글꼴·GUI·메뉴 흐림·구르기 대역) 그대로 (10.8), 8MB 아래, 정렬 zip (경로 순서·날짜 고정, 폴더 항목 없음), artlint 오류 0,
           글꼴·모형·그림 참조가 팩 안에 있다 (바닐라 minecraft: 그림은 건너뛴다),
           사망 화면 언어 다섯 키가 바닐라의 모든 언어에 (gen_pack.LANGS, 10.9)
  글자표   glyphs.yml 의 모든 글자가 그 글꼴에 있고 빈칸 폭이 맞다, you_died 가 deathScreen.title 과 같다
           (config.yml death.title: true 나 death.screen-fade: true (서서히 나타나는 판, 기본) 면 deathScreen.title 은 빈칸.
           YOU DIED 는 한 번만, 5.6. gen_pack 이 같은 config.yml 을 읽어 팩을 만들므로 설정 한 곳만 바꾸면 맞는다),
           서서히 판의 문구 줄 you_died_fade (souls:death) 와 표식 death_fade 가 있고 표식이 글꼴 셰이더의 값과 같다,
           death.title-glyphs 의 이름이 glyphs.yml 에 있다,
           glyphs.yml 의 HUD 자리 값 (layout) 이 글꼴 셰이더의 값과 같다 (10.2)
  제목     게임 제목 스퀘어 소울 / Square Soul (0.4 의 7): lang 의 pack.description, pack.mcmeta 대체 글,
           start.bat·start.ps1 창 제목, README.txt 첫머리
  서버     인코딩 규칙 (12.9), server.properties 가 12.7 값 그대로 (motd 는 lang 의 pack.description 두 언어),
           bukkit.yml allow-end: false,
           start.ps1 과 start.sh 의 Paper 고정값(주소·크기·sha256)이 같다
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK_SRC = os.path.join(ROOT, "pack")
PLUGIN = os.path.join(ROOT, "plugin")
RES = os.path.join(PLUGIN, "src", "main", "resources")
JAVA_SRC = os.path.join(PLUGIN, "src", "main", "java")
JAR = os.path.join(PLUGIN, "build", "libs", "Soulslike.jar")
SERVER = os.path.join(ROOT, "server")
DIST = os.path.join(ROOT, "dist")
FIXED = (2026, 1, 1, 0, 0, 0)
TOP = "Soulslike-Server/"

for p in (HERE, PACK_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)
import artlint  # noqa: E402
import gen_pack  # noqa: E402
import langcheck  # noqa: E402
import textlint  # noqa: E402

# 서버 zip 에 넣는 것 (이 밖의 파일은 server/ 에서 서버를 켜 봤을 때 생긴 것으로 보고 넣지 않는다)
SERVER_FILES = ("README.txt", "bukkit.yml", "config/paper-global.yml", "server.properties",
                "start.bat", "start.ps1", "start.sh")
# 12.7 그대로. 마인크래프트가 처음 켤 때 파일을 다시 쓰므로 주석이 아니라 값만 본다
PROPERTIES = {
    "gamemode": "adventure", "force-gamemode": "true", "difficulty": "normal", "spawn-protection": "0",
    "view-distance": "10", "simulation-distance": "6", "allow-flight": "true", "online-mode": "true",
    "enforce-secure-profile": "false", "generate-structures": "false", "level-type": "minecraft:flat",
    "generator-settings": '{"layers":[{"block":"minecraft:air","height":1}],"biome":"minecraft:the_void",'
                          '"features":false,"lakes":false,"structure_overrides":[]}',
    "max-players": "4", "pause-when-empty-seconds": "60",
    # 12.7 밖: 로비 이름은 플러그인 설정의 주석대로 world
    "level-name": "world",
}
# 게임 제목 (DESIGN.md 0.4 의 7). lang 의 pack.description (팩 설명, 서버 목록 이름 motd 의 두 언어),
# pack.mcmeta 의 대체 글, 시작기 창 제목, 서버 README 첫머리가 이 글이다. 식은 가마 는 마지막 지역 (R7) 의 이름일 뿐이다
TITLE = {"ko": "스퀘어 소울", "en": "Square Soul"}
PACK_FORMAT = 75
DATAPACK_FORMAT = [94, 1]
BIOMES = ("hub", "prison", "redin", "parish", "mire", "spire", "ossuary", "forge", "kiln")
DEATH_KEYS = ("deathScreen.title", "deathScreen.respawn", "deathScreen.score.value",
              "deathScreen.titleScreen", "deathScreen.quit.confirm")
PACK_LIMIT = 8 * 1024 * 1024
GRADLE_TRIES = 10
# 다른 gradle 이 같은 폴더를 빌드하는 중일 때의 말 (이때만 기다렸다 다시 한다)
GRADLE_BUSY = re.compile(r"Timeout waiting to lock|in use by another Gradle instance|Could not acquire lock", re.I)


class Gate:
    """관문 한 묶음의 결과. 묶음마다 실패를 모아 보이고, 끝에서 하나라도 실패했으면 아무것도 쓰지 않고 멈춘다."""
    failed = []   # 실패한 묶음 이름 (모든 묶음이 같이 쓴다)

    def __init__(self):
        self.fails = []

    def check(self, ok, what):
        if not ok:
            self.fails.append(what)
        return ok

    def done(self, title):
        if self.fails:
            print(f"[{title}] 실패 {len(self.fails)}")
            for f in self.fails:
                print("  -", f)
            Gate.failed.append(title)
        else:
            print(f"[{title}] 통과")


def run(cmd, cwd):
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def build():
    """10.6 의 순서: gen_pack → gradle. gradle 잠금이 잡혀 있으면 (다른 빌드가 도는 중) 기다렸다 다시 한다."""
    r = run([sys.executable, os.path.join(PACK_SRC, "gen_pack.py")], ROOT)
    print(r.stdout.rstrip())
    if r.returncode != 0:
        print(r.stderr.rstrip())
        sys.exit("묶지 않음: gen_pack 실패")
    gradlew = os.path.join(PLUGIN, "gradlew.bat" if os.name == "nt" else "gradlew")
    for i in range(GRADLE_TRIES):
        r = run([gradlew, "build", "-q"], PLUGIN)
        if r.returncode == 0:
            return
        out = r.stdout + r.stderr
        if not GRADLE_BUSY.search(out):
            print(out.rstrip())
            sys.exit("묶지 않음: gradle build 실패")
        print(f"  gradle 잠금이 잡혀 있다. 20초 뒤 다시 ({i + 1}/{GRADLE_TRIES})")
        time.sleep(20)
    sys.exit("묶지 않음: gradle 잠금이 풀리지 않는다")


# ── jar ──

def check_jar(built):
    g = Gate()
    if not os.path.isfile(JAR):
        sys.exit(f"묶지 않음: {JAR} 가 없다 (pack/gen_pack.py 다음에 ./gradlew build)")
    with zipfile.ZipFile(JAR) as z:
        names = set(z.namelist())
        jar = {n: z.read(n) for n in names if not n.endswith("/")}

    # resources/ 가 그대로 들어 있는지 (paper-plugin.yml 은 gradle 이 버전을 채우므로 따로 본다)
    for base, dirs, files in os.walk(RES):
        dirs.sort()
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(base, f), RES).replace(os.sep, "/")
            if rel == "paper-plugin.yml":
                continue
            with open(os.path.join(base, f), "rb") as fh:
                g.check(jar.get(rel) == fh.read(), f"jar 안 {rel} 이 resources 와 다르다 (낡은 jar, 다시 빌드)")
    if not built:
        newest = max((os.path.getmtime(os.path.join(b, f)) for b, _, fs in os.walk(JAVA_SRC) for f in fs), default=0)
        g.check(os.path.getmtime(JAR) >= newest, "jar 가 Java 소스보다 오래됐다 (--no-build 를 빼고 다시)")

    meta = yaml.safe_load(jar.get("paper-plugin.yml", b"{}").decode("utf-8")) or {}
    g.check(meta.get("name") == "Soulslike", f"paper-plugin.yml name: {meta.get('name')}")
    g.check(meta.get("main") == "kr.souls.Souls", f"paper-plugin.yml main: {meta.get('main')}")
    g.check(meta.get("bootstrapper") == "kr.souls.SoulsBootstrap", f"paper-plugin.yml bootstrapper: {meta.get('bootstrapper')}")
    g.check(str(meta.get("api-version")) == "1.21.11", f"paper-plugin.yml api-version: {meta.get('api-version')}")
    g.check("$" not in str(meta.get("version", "$")), f"paper-plugin.yml version 이 채워지지 않았다: {meta.get('version')}")
    for cls in ("kr/souls/Souls.class", "kr/souls/SoulsBootstrap.class"):
        g.check(cls in names, f"jar 안에 {cls} 가 없다")

    dp = "datapack/soulsdp/"
    try:
        mc = json.loads(jar[dp + "pack.mcmeta"])["pack"]
        g.check(mc.get("min_format") == DATAPACK_FORMAT and mc.get("max_format") == DATAPACK_FORMAT,
                f"데이터팩 형식 {mc.get('min_format')}..{mc.get('max_format')} (94.1 이어야 한다, 12.2)")
    except (KeyError, ValueError) as ex:
        g.check(False, f"데이터팩 pack.mcmeta 를 읽지 못했다: {ex}")
    for b in BIOMES:
        g.check(f"{dp}data/souls/worldgen/biome/{b}.json" in names, f"데이터팩에 바이옴 souls:{b} 가 없다")
    g.check(f"{dp}data/souls/damage_type/hit.json" in names, "데이터팩에 피해 종류 souls:hit 가 없다")

    missing = [n for n in ("pack.zip", "glyphs.yml", "config.yml", "lang/ko.yml", "lang/en.yml") if n not in jar]
    g.check(not missing, f"jar 안에 {missing} 이 없다")
    g.done("jar")
    if missing:
        sys.exit("묶지 않음: jar 에 없는 것이 있어 다음 관문을 볼 수 없다")
    return jar


def check_config(jar):
    """시험용 값이 들어간 채로 묶지 않는다."""
    g = Gate()
    c = yaml.safe_load(jar["config.yml"].decode("utf-8")) or {}
    pack = c.get("pack") or {}
    url = str(pack.get("url", ""))
    g.check(url.startswith("https://"), f"pack.url 이 https 가 아니다: {url}")
    g.check("{sha1}" in url, f"pack.url 에 {{sha1}} 이 없다: {url}")
    g.check(pack.get("enabled") is True, "pack.enabled 가 꺼져 있다")
    g.check(pack.get("required") is True, "pack.required 가 꺼져 있다 (10.10)")
    g.check(pack.get("serve-port", 0) == 0, f"pack.serve-port 가 {pack.get('serve-port')} 이다 (로컬 시험용 값)")
    g.check((c.get("debug") or {}).get("test-mode") is False, "debug.test-mode 가 켜져 있다")
    g.done("설정")
    return url


# ── 팩 ──

def ref_path(ref, kind, ext):
    """'ns:path' → assets/ns/<kind>/path<ext>. 이름공간이 없으면 minecraft."""
    ns, _, path = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
    if not path.endswith(ext):
        path += ext
    return ns, f"assets/{ns}/{kind}/{path}"


def font_chars(font):
    """글꼴 json 의 제공자들이 정의한 글자 → 폭 (bitmap 은 None)."""
    chars = {}
    for p in font.get("providers", []):
        if p.get("type") == "bitmap":
            for row in p.get("chars", []):
                for ch in row:
                    chars[ch] = None
        elif p.get("type") == "space":
            chars.update(p.get("advances", {}))
    return chars


def check_pack(jar):
    g = Gate()
    data = jar["pack.zip"]
    sha1 = hashlib.sha1(data).hexdigest()
    g.check(len(data) < PACK_LIMIT, f"팩이 {len(data):,} 바이트로 8MB 를 넘는다 (10.10)")
    z = zipfile.ZipFile(io.BytesIO(data))
    infos = z.infolist()
    names = [i.filename for i in infos]
    files = {n: z.read(n) for n in names}

    # 정렬 zip (T8): 같은 입력이면 같은 SHA-1 이 나오도록 gen_pack 이 지키는 것
    g.check(names == sorted(names), "팩 zip 의 경로가 정렬되어 있지 않다")
    g.check(all(i.date_time == FIXED for i in infos), "팩 zip 의 날짜가 고정되어 있지 않다")
    g.check(not any(n.endswith("/") for n in names), "팩 zip 에 폴더 항목이 있다")

    try:
        mc = json.loads(files["pack.mcmeta"])["pack"]
        g.check(mc.get("min_format") == PACK_FORMAT and mc.get("max_format") == PACK_FORMAT,
                f"팩 형식 {mc.get('min_format')}..{mc.get('max_format')} (75 여야 한다, 10.9)")
        desc = mc.get("description")
        desc = desc if isinstance(desc, dict) else {}
        g.check(desc.get("translate") == "souls.pack.description" and desc.get("fallback") == TITLE["en"],
                f"pack.mcmeta description {mc.get('description')!r} (souls.pack.description, 대체 글 {TITLE['en']!r}, 0.4 의 7)")
    except (KeyError, ValueError) as ex:
        g.check(False, f"pack.mcmeta 를 읽지 못했다: {ex}")
    # 셰이더는 실제 클라이언트로 점검한 것뿐이다 (10.8, pack/shaders.py 의 ALLOWED): 글꼴 셰이더 (우리 bitmap 글꼴은 덮임을 R 에
    # 두고 알파가 0 이라 이것이 없으면 글이 보이지 않는다, HUD 덩이), GUI 셰이더 (2 배 창 그림의 넓이 평균, 비네트), 메뉴 흐림,
    # 구르기 대역의 아이템 셰이더 (1인칭에서 대역을 버린다, 3.3). 다른 것은 점검 전에 넣지 않는다
    import shaders as pack_shaders
    present = [n for n in names if re.match(r"assets/[^/]+/shaders/", n)]
    extra = [n for n in present if n not in pack_shaders.ALLOWED]
    missing = [n for n in pack_shaders.ALLOWED if n not in present]
    g.check(not extra, f"점검하지 않은 셰이더가 들어 있다 (10.8): {extra[:3]}")
    g.check(not missing, f"점검한 셰이더가 빠졌다 (10.8, 글꼴 셰이더가 없으면 글이 보이지 않는다): {missing[:3]}")

    # 참조: 글꼴 → 그림, 아이템 정의 → 모형, 모형 → 부모·그림. minecraft: 의 바닐라 파일은 팩에 없어도 된다
    def need(ns, path, what):
        if path in files or ns == "minecraft":
            return True
        return g.check(False, f"{what}: {path} 가 팩에 없다")

    fonts = {}
    for n in names:
        m = re.match(r"assets/([^/]+)/font/(.+)\.json$", n)
        if not m:
            continue
        font = json.loads(files[n])
        fonts[f"{m.group(1)}:{m.group(2)}"] = font
        for p in font.get("providers", []):
            if p.get("type") == "bitmap":
                ns, path = ref_path(p["file"], "textures", "")
                if need(ns, path, n) and path in files:
                    check_bitmap(g, n, files[path], p)
            elif p.get("type") == "reference":
                need(*ref_path(p["id"], "font", ".json"), n)
    for n in names:
        if re.match(r"assets/[^/]+/items/.+\.json$", n):
            for ref in walk_values(json.loads(files[n]), "model"):
                need(*ref_path(ref, "models", ".json"), n)
        elif re.match(r"assets/[^/]+/models/.+\.json$", n):
            model = json.loads(files[n])
            if isinstance(model.get("parent"), str) and not model["parent"].startswith("builtin/"):
                need(*ref_path(model["parent"], "models", ".json"), n)
            for ref in (model.get("textures") or {}).values():
                if isinstance(ref, str) and not ref.startswith("#"):
                    need(*ref_path(ref, "textures", ".png"), n)

    # 사망 화면 언어 (5.6, 10.9). 클라이언트는 en_us 다음에 고른 언어를 읽으므로 바닐라의 모든 언어를 덮어쓴다
    langs = {}
    for code in gen_pack.LANGS:
        path = f"assets/minecraft/lang/{code}.json"
        if g.check(path in files, f"{path} 가 없다"):
            langs[code] = json.loads(files[path])
            missing = [k for k in DEATH_KEYS if k not in langs[code]]
            g.check(not missing, f"{path} 에 사망 화면 키가 없다: {missing}")

    # artlint 는 팩 안 PNG 를 그대로 꺼내 본다 (묶인 것이 검사한 것과 같도록)
    with tempfile.TemporaryDirectory() as tmp:
        for n in names:
            if n.endswith(".png"):
                out = os.path.join(tmp, *n.split("/"))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "wb") as f:
                    f.write(files[n])
        report = artlint.lint([tmp], tmp, quiet=True)
        for level, path, rule, msg in report.errors:
            g.check(False, f"artlint {os.path.relpath(path, tmp)}: {rule} — {msg}")
    g.done("팩")
    print(f"  SHA-1 {sha1}, {len(data):,} 바이트, 파일 {len(names)}개")
    if report.warnings:
        print(f"  artlint 경고 {len(report.warnings)}개 (묶기는 한다): python3 pack/artlint.py")
    return sha1, fonts, langs


def walk_values(node, key):
    """json 트리에서 key 의 문자열 값을 모두 낸다."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                yield v
            else:
                yield from walk_values(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from walk_values(v, key)


def check_bitmap(g, font_file, png, provider):
    """bitmap 그림의 크기가 chars 격자로 나누어떨어지는지."""
    try:
        from PIL import Image
        w, h = Image.open(io.BytesIO(png)).size
    except Exception as ex:
        g.check(False, f"{font_file}: {provider['file']} 그림을 읽지 못했다: {ex}")
        return
    rows = provider.get("chars", [])
    cols = {len(r) for r in rows}
    g.check(len(cols) == 1, f"{font_file}: chars 줄 길이가 다르다 {sorted(cols)}")
    if rows and len(cols) == 1:
        g.check(w % cols.pop() == 0 and h % len(rows) == 0,
                f"{font_file}: {provider['file']} {w}×{h} 가 chars 격자 {len(rows[0])}×{len(rows)} 로 나누어떨어지지 않는다")


def jar_pack_text(jar, name):
    """jar 안 pack.zip 의 글 파일 하나 (없으면 None)."""
    try:
        with zipfile.ZipFile(io.BytesIO(jar["pack.zip"])) as z:
            return z.read(name).decode("utf-8")
    except (KeyError, zipfile.BadZipFile):
        return None


def check_glyphs(jar, fonts, langs):
    g = Gate()
    table = yaml.safe_load(jar["glyphs.yml"].decode("utf-8")) or {}
    g.check("you_died" in table, "glyphs.yml 에 you_died 가 없다")
    g.check("you_died_title" in table, "glyphs.yml 에 you_died_title (플러그인 화면 제목) 이 없다")
    g.check("you_died_fade" in table, "glyphs.yml 에 you_died_fade (서서히 나타나는 사망 화면 문구 줄) 가 없다")
    # HUD 자리 값 (hud.layout): 그림 글자가 아니다. 팩의 글꼴 셰이더가 같은 값으로 HUD 를 화면 가장자리로 옮긴다 (10.2, 10.8)
    lay = table.pop("layout", None) or {}
    stats = table.pop("stats", None) or {}     # 무기 설명 칸 수치 표 (pack/typeset.py): 값 글자 폭이 기본 글꼴과 같은지는 아래
    marks = table.pop("death_fade", None) or {}  # 서서히 나타나는 YOU DIED 의 표식 (hud.death_mark): 글꼴 셰이더와 같은 값
    g.check(len(str(stats.get("chars", ""))) == len(stats.get("widths", [])) and stats.get("value_col"),
            f"glyphs.yml stats 가 틀렸다: {stats}")
    shader = jar_pack_text(jar, "assets/minecraft/shaders/core/rendertype_text.vsh")
    g.check(all(k in lay for k in ("margin", "left", "right", "mark_left", "mark_right")), f"glyphs.yml layout 이 모자라다: {lay}")
    if shader is not None and lay:
        want = [f"centre - {lay.get('left')}.0", f"centre + {lay.get('right')}.0", f"{lay.get('margin')}.0"]
        if "boss_width" in lay:      # 보스 막대 (10.2): 셰이더가 늘이는 바탕 폭
            want.append(f"/ {lay.get('boss_width')}.0")
        g.check(all(w in shader for w in want), f"글꼴 셰이더의 자리 값이 glyphs.yml layout 과 다르다 ({want})")
    if shader is not None:
        want = [f"rgbi.r == {marks.get('mark_r')} && rgbi.g >= {marks.get('g0')}",
                f"rgbi.r == {marks.get('shadow_r')} && rgbi.g >= {marks.get('g0')}"]
        g.check(marks and all(w in shader for w in want), f"글꼴 셰이더의 YOU DIED 표식이 glyphs.yml death_fade 와 다르다 ({marks})")
    for name, e in table.items():
        font = fonts.get(e.get("font"))
        if not g.check(font is not None, f"glyphs.yml {name}: 글꼴 {e.get('font')} 이 팩에 없다"):
            continue
        defined = font_chars(font)
        text = str(e.get("char", ""))
        # 기본 글꼴의 보통 글자(개인 영역 밖)는 바닐라가 그린다
        bad = [f"U+{ord(c):04X}" for c in text
               if c not in defined and not (e["font"] == "minecraft:default" and ord(c) < 0xE000)]
        g.check(text and not bad, f"glyphs.yml {name}: 글꼴 {e['font']} 에 없는 글자 {bad or '(빈 글자)'}")
        if len(text) == 1 and defined.get(text) is not None:
            g.check(defined[text] == e.get("width"), f"glyphs.yml {name}: 폭 {e.get('width')} ≠ 글꼴 {defined[text]}")
    # YOU DIED 는 한 번만 (5.6): death.title 이 꺼져 있으면 (기본) 사망 화면 제목이 그림 글자,
    # 켜져 있으면 플러그인이 화면 제목으로 띄우므로 사망 화면 제목은 비어 있어야 한다 (gen_pack --death-title plugin)
    cfg = yaml.safe_load(jar["config.yml"].decode("utf-8")) or {}
    mode = gen_pack.death_mode_of(cfg.get("death"))
    names = str((cfg.get("death") or {}).get("title-glyphs") or "").split()
    missing = [n for n in names if n not in table]
    g.check(names and not missing, f"config.yml death.title-glyphs 의 이름이 glyphs.yml 에 없다: {missing or '(빈칸)'}")
    title = (table.get("you_died") or {}).get("char")
    for code, lang in langs.items():
        got = lang.get("deathScreen.title")
        if mode != "screen":
            g.check(got == "", f"{code} 의 deathScreen.title 이 비어 있지 않다 ({mode} 판 (config.yml death.*) 과 겹친다. "
                               f"팩을 다시 만든다: python3 pack/gen_pack.py)")
        else:
            g.check(got == title, f"{code} 의 deathScreen.title 이 glyphs.yml you_died 와 다르다")
    g.done("글자표")


# ── 서버 폴더 ──

def read_properties(raw):
    """server.properties 의 값 (\\: 와 \\uXXXX 를 푼다)."""
    out = {}
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line[0] in "#!" or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), v)
        out[k.strip()] = re.sub(r"\\(.)", r"\1", v)
    return out


def pack_titles():
    """lang/ko.yml·en.yml 의 pack.description (꼴 태그를 뗀 글). 게임 제목 TITLE 과 같아야 한다 (0.4 의 7)."""
    tables = langcheck.langpack.load_all()
    return {lang: langcheck.langpack.split_style(langcheck.langpack.lines(tables[lang])["pack.description"])[1]
            for lang in ("ko", "en")}


def motd():
    """서버 목록 이름 = §7 + 한국어 · 영어 (lang/ko.yml·en.yml 의 pack.description, 꼴 태그를 뗀 글)."""
    text = pack_titles()
    return "\u00a77" + " \u00b7 ".join(text[lang] for lang in ("ko", "en"))


def check_server():
    g = Gate()
    raw = {}
    for f in SERVER_FILES:
        p = os.path.join(SERVER, *f.split("/"))
        if g.check(os.path.isfile(p), f"server/{f} 가 없다"):
            with open(p, "rb") as fh:
                raw[f] = fh.read()
    if len(raw) == len(SERVER_FILES):
        bom = b"\xef\xbb\xbf"
        try:
            raw["start.bat"].decode("ascii")
        except UnicodeDecodeError:
            g.check(False, "start.bat 에 ASCII 가 아닌 글자가 있다 (cmd.exe 가 한글을 잘못 읽는다)")
        for f in ("start.ps1", "README.txt"):
            g.check(raw[f].startswith(bom), f"{f} 가 UTF-8 BOM 으로 시작하지 않는다 (PowerShell 5.1·메모장이 한글을 깨뜨린다)")
        for f in ("start.bat", "start.ps1", "README.txt"):
            g.check(raw[f].count(b"\n") == raw[f].count(b"\r\n"), f"{f} 의 줄 끝이 모두 CRLF 가 아니다")
        g.check(b"\r" not in raw["start.sh"], "start.sh 에 CR 이 있다 (LF 만)")
        g.check(raw["start.sh"].startswith(b"#!/bin/sh"), "start.sh 첫 줄이 #!/bin/sh 가 아니다")
        g.check(not raw["server.properties"].startswith(bom), "server.properties 에 BOM 이 있다 (첫 키가 깨진다)")
        for f in ("start.ps1", "README.txt", "server.properties", "bukkit.yml", "config/paper-global.yml", "start.sh"):
            try:
                raw[f].decode("utf-8")
            except UnicodeDecodeError:
                g.check(False, f"{f} 가 UTF-8 이 아니다")

        props = read_properties(raw["server.properties"])
        for k, want in PROPERTIES.items():
            g.check(props.get(k) == want, f"server.properties {k}={props.get(k)} (12.7: {want})")
        # 서버 목록의 이름은 팩을 받기 전에 보여 두 언어를 함께 (10.9): lang 의 pack.description 한국어 · 영어
        want = motd()
        g.check(props.get("motd") == want, f"server.properties motd={props.get('motd')!r} (lang pack.description: {want!r})")
        # 게임 제목 (0.4 의 7): pack.description 이 제목 그대로, 시작기 창 제목과 서버 README 첫머리도 같은 제목
        got = pack_titles()
        g.check(got == TITLE, f"lang pack.description {got} 이 게임 제목 {TITLE} 이 아니다 (DESIGN.md 0.4 의 7)")
        bat_title = f"title {TITLE['en']} Server"   # start.bat 은 ASCII 만 (cmd.exe)
        g.check(bat_title in raw["start.bat"].decode("ascii", "replace").splitlines(), f"start.bat 에 '{bat_title}' 줄이 없다")
        ps1_title = f"WindowTitle = '{TITLE['ko']} 서버'"
        g.check(ps1_title in raw["start.ps1"].decode("utf-8-sig", "replace"), f"start.ps1 창 제목이 {ps1_title!r} 가 아니다")
        head = "\n".join(raw["README.txt"].decode("utf-8-sig", "replace").splitlines()[:4])
        g.check(TITLE["ko"] in head and TITLE["en"] in head, f"README.txt 첫머리에 게임 제목 {TITLE['ko']} ({TITLE['en']}) 이 없다")
        bukkit = yaml.safe_load(raw["bukkit.yml"].decode("utf-8")) or {}
        g.check((bukkit.get("settings") or {}).get("allow-end") is False, "bukkit.yml settings.allow-end 가 false 가 아니다 (12.7)")
        paper = yaml.safe_load(raw["config/paper-global.yml"].decode("utf-8")) or {}
        g.check((paper.get("misc") or {}).get("enable-nether") is False, "config/paper-global.yml misc.enable-nether 가 false 가 아니다")

        # 두 시작기의 Paper 고정값이 같은지 (한쪽만 고치는 실수)
        ps1 = raw["start.ps1"].decode("utf-8-sig")
        sh = raw["start.sh"].decode("utf-8")
        pin_ps1 = [re.search(rf"\${k}\s*=\s*'?([^'\r\n]+?)'?\s*$", ps1, re.M) for k in ("PaperUrl", "PaperSize", "PaperSha256")]
        pin_sh = [re.search(rf"^{k}=(\S+)$", sh, re.M) for k in ("PAPER_URL", "PAPER_SIZE", "PAPER_SHA256")]
        if g.check(all(pin_ps1) and all(pin_sh), "start.ps1 또는 start.sh 에서 Paper 고정값을 찾지 못했다"):
            a = [m.group(1) for m in pin_ps1]
            b = [m.group(1) for m in pin_sh]
            g.check(a == b, f"start.ps1 {a} 와 start.sh {b} 의 Paper 고정값이 다르다")
            g.check("paper-1.21.11-132.jar" in a[0] and a[2] in a[0], f"Paper 주소가 1.21.11 빌드 132 가 아니다: {a[0]}")

    # M0 은 세계를 묶지 않는다. 서버를 server/ 안에서 켜 봤다면 생긴 파일은 넣지 않는다
    extra = []
    for base, dirs, files in os.walk(SERVER):
        dirs.sort()
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(base, f), SERVER).replace(os.sep, "/")
            if rel not in SERVER_FILES:
                extra.append(rel)
    worlds = sorted({e.split("/")[0] for e in extra if e.endswith("level.dat")})
    g.check(not worlds, f"server/ 에 세계 폴더가 있다 {worlds} (M0 은 세계를 묶지 않는다. 지우고 다시)")
    g.done("서버 폴더")
    if extra:
        print(f"  server/ 에서 묶지 않는 파일 {len(extra)}개: {', '.join(extra[:6])}{' …' if len(extra) > 6 else ''}")
    return raw


# ── 묶기 ──

def add(z, arc, data):
    zi = zipfile.ZipInfo(arc, date_time=FIXED)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.create_system = 3   # 유닉스 권한을 읽게 (start.sh 실행 권한)
    zi.external_attr = (0o100755 if arc.endswith(".sh") else 0o100644) << 16
    z.writestr(zi, data)


def write_dist(jar_bytes, pack, sha1, server):
    os.makedirs(os.path.join(DIST, "packs"), exist_ok=True)
    packs = os.path.join(DIST, "packs")
    # 한 번 커밋한 팩은 지우지 않는다: 그 판의 jar 를 받은 서버가 아직 그 주소로 팩을 보낸다 (지우면 "다운로드 실패").
    # 커밋하지 않은 중간 팩만 지운다.
    try:
        kept = set(os.path.basename(x) for x in subprocess.run(
            ["git", "ls-files", "--", packs], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split())
    except (OSError, subprocess.CalledProcessError):
        kept = None   # git 이 없으면 아무것도 지우지 않는다
    for old in sorted(os.listdir(packs)):
        if old.endswith(".zip") and old != sha1 + ".zip" and kept is not None and old not in kept:
            os.remove(os.path.join(packs, old))
            print("커밋하지 않은 지난 팩을 지웠다:", old)
    with open(os.path.join(packs, sha1 + ".zip"), "wb") as f:
        f.write(pack)
    with open(os.path.join(DIST, "Soulslike.jar"), "wb") as f:
        f.write(jar_bytes)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for arc, data in sorted([(TOP + f, d) for f, d in server.items()] + [(TOP + "plugins/Soulslike.jar", jar_bytes)]):
            add(z, arc, data)
    with open(os.path.join(DIST, "Soulslike-Server.zip"), "wb") as f:
        f.write(buf.getvalue())


def check_url(url, sha1):
    """올린 팩을 받아 본다. 플러그인도 켤 때 같은 일을 한다 (PackService 자체 확인)."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            got = hashlib.sha1(r.read()).hexdigest()
    except Exception as ex:
        print(f"[주소] 받지 못했다: {ex}")
        return False
    print(f"[주소] {'같다' if got == sha1 else '다르다: ' + got}")
    return got == sha1


def main(argv):
    built = "--no-build" not in argv
    if built:
        build()
    g = Gate()
    report = textlint.lint(quiet=True)
    for level, path, key, rule, msg in report.errors:
        g.check(False, f"textlint {textlint.show(path)}: {key}: {rule} — {msg}")
    g.done("글")
    if report.warnings:
        print(f"  textlint 경고 {len(report.warnings)}개 (묶기는 한다): python3 tools/textlint.py")

    jar = check_jar(built)
    g = Gate()
    report = langcheck.lint(pack=jar["pack.zip"], quiet=True)
    for level, rule, where, msg in report.errors:
        g.check(False, f"langcheck {rule}: {where}: {msg}")
    g.done("문구")
    if report.warnings:
        print(f"  langcheck 경고 {len(report.warnings)}개 (묶기는 한다): python3 tools/langcheck.py")
    url = check_config(jar)
    sha1, fonts, langs = check_pack(jar)
    check_glyphs(jar, fonts, langs)
    server = check_server()
    if Gate.failed:
        sys.exit(f"묶지 않음: {', '.join(Gate.failed)}")

    with open(JAR, "rb") as f:
        jar_bytes = f.read()
    write_dist(jar_bytes, jar["pack.zip"], sha1, server)
    for base, dirs, files in os.walk(DIST):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(base, f)
            print(f"{os.path.getsize(p) / 1024:8.0f} KB  dist/{os.path.relpath(p, DIST).replace(os.sep, '/')}")
    resolved = url.replace("{sha1}", sha1)
    print(f"팩 주소 {resolved}")
    if "--check-url" in argv:
        if not check_url(resolved, sha1):
            sys.exit("팩 주소가 아직 이 팩을 내주지 않는다. dist/packs/ 를 커밋·푸시한 뒤 다시 본다.")
    else:
        print(f"dist/packs/{sha1}.zip 을 커밋·푸시해야 접속한 사람이 팩을 받는다 (확인: --check-url).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
