#!/usr/bin/env python3
"""
UI 분위기 시안 "serif" (새긴 명조·로마 대문자, 절제): 지금 판의 자리와 판은 그대로 두고 글을 바꾼다.

  python3 pack/variants/mood_serif/build.py <작업폴더> [기본 jar] [--no-java]

기본 jar (없으면 plugin/build/libs/Soulslike.jar) 안의 pack.zip 을 <작업폴더>/pack/ 에 풀고 그 위에 덧입힌 뒤
<작업폴더>/Soulslike.jar (기본 jar 사본, pack.zip 만 바뀐 것) 와 <작업폴더>/pack.zip 을 쓴다. 저장소의 공용 파일
(gen_pack·gui_skin·hud, pack/resourcepack, plugin/src) 은 건드리지 않는다.

덧입히는 것
  1. 글꼴 (fonts.py, 모두 SIL OFL 1.1): 바닐라 기본 글꼴 (minecraft:default) 앞에 TTF 둘 (본문 로마자 EB Garamond,
     본문 한글 Noto Serif KR) 을 끼워 바닐라 화면·채팅·설명 칸·아이템 개수까지 명조로. 제목 글꼴 souls:title (Cinzel +
     한 단 굵은 명조). 영어 창 제목은 Cinzel 그림을 개인 영역 (U+F120..) 에 이어 두어 언어 파일만으로 로마 대문자.
     사용 허락 글은 팩 assets/souls/font/licenses/ 와 FONTS-OFL.txt
  2. 글자색 (rendertype_text_intensity.vsh): TTF 글자는 이 셰이더로 그려진다. 바닐라 흰 글 (#FFFFFF) → 뼈빛,
     §7 (#AAAAAA) → 흐린 옛 금빛, 꺼진 단추 (#A0A0A0) → 재, 그림자 → 먹빛으로. 플러그인이 색을 준 글은 그대로.
     HUD 표식 색 (보스 이름) 을 옮기는 덩이는 rendertype_text.vsh (hud.py) 와 같다 (보스 이름도 이제 TTF 라)
  3. 장식 (art.py): 제목 밑 금빛 실선 한 줄 (가운데 작은 마름모, 양 끝은 알파 계단), 판 안쪽의 옅은 비네트, 소울 숫자를
     명조 숫자로
  4. 언어 (lang.py): 일시 정지 제목·창 제목·휴식 창 제목 밑에 실선, 무기 설명의 첫 줄 위에 실선 (이름 밑)
"""
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(PACK_DIR)
for p in (HERE, PACK_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import fonts  # noqa: E402
import style  # noqa: E402

ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


def unpack_base(jar, dst):
    with zipfile.ZipFile(jar) as z:
        data = z.read("pack.zip")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    with zipfile.ZipFile(io.BytesIO(data)) as p:
        p.extractall(dst)
    return len(data)


def replace_in_jar(src, dst, entries):
    """src jar 를 dst 로 베끼며 entries {이름: 바이트} 만 바꾼다."""
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


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    work = os.path.abspath(argv[0])
    args = [a for a in argv[1:] if not a.startswith("--")]
    jar = os.path.abspath(args[0]) if args else os.path.join(ROOT, "plugin", "build", "libs", "Soulslike.jar")
    os.makedirs(work, exist_ok=True)
    pack = os.path.join(work, "pack")
    base_size = unpack_base(jar, pack)
    print(f"기본 팩 {base_size:,} 바이트 ({jar})")

    import art  # noqa: E402
    import java_hook  # noqa: E402
    import lang  # noqa: E402
    import shader  # noqa: E402

    font_info = style.write_fonts(pack)
    art.build(pack, font_info)
    lang.build(pack, font_info)
    shader.build(pack)

    data = zip_bytes(pack)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(os.path.join(work, "pack.zip"), "wb") as f:
        f.write(data)
    out_jar = os.path.join(work, "Soulslike.jar")
    # 플러그인: 사본에서 제목 글꼴 고리를 단 jar (--no-java 면 기본 jar 그대로). 팩과 HUD 글자 표는 기본 jar 의 것과 짝을 맞춘다
    with zipfile.ZipFile(jar) as z:
        glyphs = z.read("glyphs.yml")
    plugin_jar = jar if "--no-java" in argv else java_hook.build(work, ROOT)
    replace_in_jar(plugin_jar, out_jar, {"pack.zip": data, "glyphs.yml": glyphs})
    print(f"시안 팩 {len(data):,} 바이트 (기본보다 {len(data) - base_size:+,}), sha1 {sha1}")
    print(f"  → {os.path.join(work, 'pack.zip')}, {out_jar}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
