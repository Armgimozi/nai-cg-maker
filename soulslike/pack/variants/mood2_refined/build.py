#!/usr/bin/env python3
"""
UI 분위기 2차 시안 "refined" (정제된 명조): 1차 시안 A (mood_serif) 를 이어, 글을 평평하고 깨끗하게 고치고 화면 전체 (HUD 막대 셋,
소울 상자, 보스 막대, 조준점, 사망 띠, 단축 슬롯, 단추·밀대·체크 칸, 설명 칸, 창, 채팅 바탕) 를 한 시각 언어로 다시 그린다.

  python3 pack/variants/mood2_refined/build.py <작업폴더> [기본 jar] [--no-java]

기본 팩·플러그인은 건드리지 않는다 (기본 꺼짐, 이 스크립트를 부를 때만). 기본 jar (없으면 plugin/build/libs/Soulslike.jar) 안의
pack.zip 을 <작업폴더>/pack/ 에 풀고 그 위에 덧입혀 <작업폴더>/pack.zip 과 <작업폴더>/Soulslike.jar (기본 jar 사본: pack.zip,
glyphs.yml 과 java_hook 의 작은 고리만 다르다) 를 쓴다.

모듈
  style.py     공통 값 (해상도, 글꼴 크기, 글자색, 선 색)
  fonts.py     글꼴 받기·잘라 내기 (SIL OFL 1.1)
  text.py      글꼴 정의, 글꼴 셰이더 (박스 필터, 글자색), GUI 그림 셰이더
  ornament.py  공통 장식 (머리카락 선, 마름모, 덩굴 끝) 을 4배 해상도로 그리는 붓
  hudart.py    HUD 그림 글자 (막대 셋·소울 상자·보스 막대·사망 띠) 와 조준점, glyphs.yml
  guiart.py    GUI 그림 (단축 슬롯, 단추, 밀대, 체크 칸, 설명 칸, 창, 채팅 바탕 셰이더)
  lang.py      언어 파일 장식 (제목 밑 실선, 영어 창 제목의 Cinzel)
  java_hook.py 플러그인 사본: <font:> 꼴 태그 (제목 글꼴), 보스 이름·아이템 이름에 제목 글꼴
  measure.py   실제 클라이언트 그림에서 바탕선·획 굵기를 잰다
  shots.sh     실제 클라이언트로 찍기
"""
import hashlib
import io
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

ZIP_DATE = (2026, 1, 1, 0, 0, 0)


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
        glyphs = z.read("glyphs.yml").decode("utf-8")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    with zipfile.ZipFile(io.BytesIO(data)) as p:
        p.extractall(dst)
    return len(data), glyphs


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
    base_size, base_glyphs = unpack_base(jar, pack)
    print(f"기본 팩 {base_size:,} 바이트 ({jar})")

    import text  # noqa: E402
    info = text.write_fonts(pack)
    extra_default = []
    glyphs_yml = base_glyphs
    if "--text-only" not in argv:
        import guiart  # noqa: E402
        import hudart  # noqa: E402
        import lang  # noqa: E402
        extra_default, glyphs_yml = hudart.build(pack, base_glyphs)
        guiart.build(pack)
        extra_default = extra_default + lang.build(pack, info)
    text.write_font_defs(pack, info, extra_default)
    text.write_shaders(pack)
    if "--text-only" not in argv:
        guiart.write_shaders(pack)

    data = zip_bytes(pack)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(os.path.join(work, "pack.zip"), "wb") as f:
        f.write(data)
    out_jar = os.path.join(work, "Soulslike.jar")
    if "--no-java" in argv:
        plugin_jar = jar
    else:
        import java_hook  # noqa: E402
        plugin_jar = java_hook.build(work, ROOT)
    replace_in_jar(plugin_jar, out_jar, {"pack.zip": data, "glyphs.yml": glyphs_yml.encode("utf-8")})
    print(f"시안 팩 {len(data):,} 바이트 (기본보다 {len(data) - base_size:+,}), sha1 {sha1}")
    print(f"  → {os.path.join(work, 'pack.zip')}, {out_jar}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
