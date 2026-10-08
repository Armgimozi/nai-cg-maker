#!/usr/bin/env python3
"""
UI 분위기 시안 "gothic" (촛불 아래의 고딕): 더 어둡고 깊게. 무거운 비네트의 검정, 위에서 촛불 하나가 비춘 검은 옻칠 판
(윗날만 따뜻하게, 금빛 테는 위가 밝고 아래로 꺼진다), 다크 소울 3 식 아이템 설명 (로마 대문자·목판 명조 이름, 이름 밑 금실,
두 열 수치, 한 단 작고 조용한 설명), 명조·가라몽 본문.

  python3 pack/variants/mood_gothic/build.py <작업폴더> [--no-java] [--rev <git 판>]

저장소의 git 판 (기본 HEAD) 에서 plugin/ 을 <작업폴더>/snap 에 꺼내 (다른 작업이 고치는 중인 파일을 섞지 않으려고) 그 안의
pack.zip 을 <작업폴더>/pack/ 에 풀고 덧입힌다. 결과
  <작업폴더>/pack.zip          시안 팩
  <작업폴더>/Soulslike.jar     시안 플러그인 (사본을 고쳐 만든 jar 에 시안 팩)
  <작업폴더>/preview.png       그림 미리보기
저장소의 공용 파일 (gen_pack·gui_skin·hud, pack/resourcepack, plugin/) 은 건드리지 않는다.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(PACK_DIR)
for p in (HERE, PACK_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import art  # noqa: E402
import fonts  # noqa: E402
import java_hook  # noqa: E402
import lang  # noqa: E402
import shaders  # noqa: E402
import style as st  # noqa: E402
from palette import c  # noqa: E402

ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def palette_hex(name):
    r, g, b, _ = c(name)
    return f"#{r:02x}{g:02x}{b:02x}"


def zip_bytes(folder):
    files = []
    for base, dirs, names in os.walk(folder):
        dirs.sort()
        for n in names:
            full = os.path.join(base, n)
            files.append((os.path.relpath(full, folder).replace(os.sep, "/"), full))
    files.sort()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for arc, full in files:
            zi = zipfile.ZipInfo(arc, date_time=ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 0
            zi.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                z.writestr(zi, fh.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


def replace_in_jar(src, dst, entries):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst + ".part", "w") as zout:
        seen = set()
        for info in zin.infolist():
            if info.filename in entries:
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, entries[info.filename])
                seen.add(info.filename)
            else:
                zout.writestr(info, zin.read(info.filename))
        for name, data in entries.items():
            if name not in seen:
                zi = zipfile.ZipInfo(name, date_time=ZIP_DATE)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, data)
    os.replace(dst + ".part", dst)


def snapshot(work, rev):
    """git 판 rev 의 plugin/ 을 work/snap/plugin 에 꺼낸다."""
    snap = os.path.join(work, "snap")
    if os.path.exists(snap):
        shutil.rmtree(snap)
    os.makedirs(snap)
    arc = subprocess.run(["git", "archive", rev, "plugin"], cwd=ROOT, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", snap], input=arc, check=True)
    return os.path.join(snap, "plugin")


def client_jar():
    home = os.environ.get("SOULS_CLIENT_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "souls-client")
    return os.path.join(home, "versions", "1.21.11.jar")


def write_fonts(pack):
    """TTF 넷 (개인 영역 글자를 단 제목 글꼴 포함), 사용 허락 글. 돌려주는 값: Metrics 묶음과 크기 표."""
    sets = {"latin": fonts.latin_set(), "hangul": fonts.hangul_set()}
    pua = {"title_la": lang.title_latin(st), "title_kr": lang.title_hangul(st)}
    font_dir = os.path.join(pack, "assets", "souls", "font", "gothic")
    sizes = {}
    paths = {}
    for name, (key, wght, which, family, digits) in st.FILES.items():
        path, nbytes, n = fonts.make(key, sets[which], os.path.join(font_dir, name + ".ttf"), family, wght=wght,
                                     digits=digits, pua=pua.get(name))
        sizes[name] = nbytes
        paths[name] = path
        print(f"  글꼴 {name}: {fonts.SOURCES[key][2]}{' wght ' + str(wght) if wght else ''}, 글자 {n}, {nbytes:,} 바이트")
    lic_dir = os.path.join(pack, "assets", "souls", "font", "gothic", "licenses")
    os.makedirs(lic_dir, exist_ok=True)
    notice = ["Square Soul resource pack, UI mood variant \"gothic\" - fonts", "",
              "The TrueType fonts in assets/souls/font/gothic/ are subsets of the following fonts, licensed under the",
              "SIL Open Font License, Version 1.1 (full text next to this notice in assets/souls/font/gothic/licenses/).",
              "They are Modified Versions (subset, digits remapped, private-use copies of some glyphs) and were renamed",
              "\"Souls Gothic ...\"; the Reserved Font Names of the originals (Marcellus, NanumMyeongjo, ...) are not used.", ""]
    for key in sorted({v[0] for v in st.FILES.values()}):
        text = fonts.licence_text(key)
        fname = "ofl-" + fonts.SOURCES[key][2].lower().replace(" ", "-") + ".txt"
        with open(os.path.join(lic_dir, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        notice.append(f"  {fonts.SOURCES[key][2]}: {text.splitlines()[0].strip()}")
    with open(os.path.join(pack, "FONTS-OFL.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(notice) + "\n")
    os_ = st.OVERSAMPLE
    size_of = {n: s for n, s, _ in st.BODY + st.TITLE}
    m = {n: fonts.Metrics(paths[n], size_of[n], os_) for n in size_of}
    metrics = {"body": [m[n] for n, _, _ in st.BODY], "title": [m[n] for n, _, _ in st.TITLE],
               "title_pua": [m[n] for n, _, _ in st.TITLE]}
    return metrics, sizes


def write_ornaments(pack):
    img = art.title_divider()
    path = os.path.join(pack, "assets", "souls", "textures", "font", "gothic_orn.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    ch = chr(st.PUA_ORN)
    vis = img.width / art.ORN_SCALE
    adv = lang.divider_glyph_advance(img.width, art.ORN_SCALE)
    # 제목 줄 위에서 12 아래가 금실 위끝 (7 - ascent = 12)
    provider = {"type": "bitmap", "file": lang.ORN_FILE, "height": img.height // art.ORN_SCALE, "ascent": -5,
                "chars": [ch]}
    return {"char": ch, "vis": vis, "adv": adv, "provider": provider}


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[0])
    rev = argv[argv.index("--rev") + 1] if "--rev" in argv else "HEAD"
    os.makedirs(work, exist_ok=True)
    src = snapshot(work, rev)
    base_zip = os.path.join(src, "src", "main", "resources", "pack.zip")
    pack = os.path.join(work, "pack")
    if os.path.exists(pack):
        shutil.rmtree(pack)
    with zipfile.ZipFile(base_zip) as z:
        z.extractall(pack)
    base_size = os.path.getsize(base_zip)
    print(f"기본 팩 {base_size:,} 바이트 (git {rev})")

    metrics, sizes = write_fonts(pack)
    orn = write_ornaments(pack)
    art.build(pack, None)
    art.soul_digits(os.path.join(pack, "assets", "souls", "font", "gothic", "body_la.ttf"),
                    os.path.join(pack, "assets", "souls", "textures", "font", "hud_digits.png"))
    with zipfile.ZipFile(client_jar()) as z:
        vanilla_blur = z.read("assets/minecraft/post_effect/blur.json").decode("utf-8")
    shaders.build(pack, st, vanilla_blur)
    layout, report = lang.build(pack, st, metrics, orn)
    print("  언어:", report)

    data = zip_bytes(pack)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(os.path.join(work, "pack.zip"), "wb") as f:
        f.write(data)
    art.preview(pack, os.path.join(work, "preview.png"))
    out_jar = os.path.join(work, "Soulslike.jar")
    if "--no-java" in argv:
        plugin_jar = os.path.join(ROOT, "plugin", "build", "libs", "Soulslike.jar")
    else:
        plugin_jar = java_hook.build(work, src, st, layout, palette_hex)
    replace_in_jar(plugin_jar, out_jar, {"pack.zip": data})
    print(f"시안 팩 {len(data):,} 바이트 (기본보다 {len(data) - base_size:+,}; 글꼴 {sum(sizes.values()):,}), sha1 {sha1}")
    print(f"  → {os.path.join(work, 'pack.zip')}, {out_jar}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
