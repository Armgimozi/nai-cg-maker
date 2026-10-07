#!/usr/bin/env python3
"""
식은 가마 리소스팩 생성기 (DESIGN.md 10.6). augment-skyblock pack/gen_pack.py 에서 읽기·쓰기 틀만 옮겼다.

  python3 pack/gen_pack.py            그림 생성 → artlint → zip
  python3 pack/gen_pack.py --no-dist  dist/packs/ 에 쓰지 않는다 (시험용)
  python3 pack/gen_pack.py --death-title plugin
                                      사망 화면 제목을 비운다. 플러그인 config.yml 의 death.title: true 와 함께 쓴다
                                      (YOU DIED 를 화면 한가운데에 더 크게, 5.6 과 16절 질문 4). 기본은 screen

결과
  pack/resourcepack/                          팩 폴더 (zip 에 들어가는 그대로)
  plugin/src/main/resources/pack.zip          플러그인 jar 에 들어갈 팩
  plugin/src/main/resources/glyphs.yml        HUD·사망 화면 그림 글자 표 (플러그인 hud/Glyphs 가 읽는다)
  dist/packs/<sha1>.zip                       배포할 팩 (주소 틀의 {sha1}, 10.10). 예전 것은 지운다
  pack/preview/*.png                          사람이 볼 미리보기

순서
  1. 팩 폴더를 비우고 pack.mcmeta (형식 75), pack.png
  2. hud.build: 스태미나 막대, 투명한 허기, 사망 화면 글자, 글꼴
  3. 사망 화면 언어 다섯 키 (en_us, ko_kr)
  4. artlint: 오류가 하나라도 있으면 여기서 멈추고 zip 을 만들지 않는다
  5. 정렬 zip: 경로 순서, 날짜, 권한을 고정해 같은 입력이면 SHA-1 이 같다
  6. glyphs.yml, 미리보기

M0 에는 셰이더가 없다 (10.8). 무기·보스·갑옷 그림(wkit, mc3d, art/vboss_*)은 M1 부터 이 파일에 다시 붙인다.
아이템 그림은 모두 textures/item/ 아래에 둔다. 1.21.11 은 items 아틀라스가 textures/item 폴더를
이름공간과 상관없이 모두 읽으므로 skyblock 의 write_atlas_sources 는 필요 없다.
"""
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import artlint  # noqa: E402
import gui_skin  # noqa: E402
import hud  # noqa: E402
import previews  # noqa: E402

ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "plugin", "src", "main", "resources")
OUT = os.path.join(HERE, "resourcepack")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(HERE, "preview")
NS = hud.NS

PACK_FORMAT = 75                     # 1.21.11 클라이언트 version.json 의 resource_major
PACK_DESCRIPTION = "식은 가마"
ZIP_DATE = (2026, 1, 1, 0, 0, 0)

# 사망 화면 언어 (5.6). 제목은 hud 가 만든 그림 글자 문자열로 채운다.
# 클라이언트 언어가 무엇이든 같게 보이도록 en_us 와 ko_kr 를 똑같이 덮어쓴다.
DEATH_LANG = {
    "deathScreen.respawn": "일어선다",
    "deathScreen.score.value": "",
    "deathScreen.titleScreen": "그만둔다",
    "deathScreen.quit.confirm": "여기서 그만두겠나",
}
LANGS = ("en_us", "ko_kr")


def write_json(path, data):
    """팩 안의 json 은 ASCII 로만 쓴다 (개인 영역 문자도 \\uE000 처럼 보이게, 줄바꿈과 순서 고정)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def pack_icon():
    """art/pack_icon.txt (32×32 손으로 찍은 그림). 키우지 않고 그대로 쓴다 (팩 목록에 32×32 로 보인다)."""
    ink = {".": "ash0", ",": "ash1", ":": "ash2", ";": "ash3", "r": "rust0", "R": "rust1", "s": "rust2", "S": "rust3",
           "b": "bronze0", "B": "bronze1", "n": "bronze2", "k": "blood0", "e": "ember0"}
    rows = hud.load_grids(os.path.join(HERE, "art", "pack_icon.txt"))["icon"]
    return hud.grid_image(rows, ink, clear=None)


def zip_bytes(folder):
    """
    folder 를 정렬 zip 으로 묶는다. 폴더 항목은 넣지 않고, 파일 경로 순서·날짜·권한·만든 시스템을 고정한다.
    같은 입력이면 어느 날 몇 번을 돌려도 같은 바이트가 나온다 (T8).
    """
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
    return buf.getvalue(), [a for a, _ in files]


def yaml_str(s):
    """glyphs.yml 용 큰따옴표 문자열. ASCII 밖은 \\uXXXX 로 적어 파일이 눈에 보이게 한다."""
    out = []
    for ch in s:
        if ch in ('"', "\\"):
            out.append("\\" + ch)
        elif 0x20 <= ord(ch) < 0x7f:
            out.append(ch)
        else:
            out.append(f"\\u{ord(ch):04x}")
    return '"' + "".join(out) + '"'


def write_glyphs(path, glyphs, title):
    lines = [
        "# HUD·사망 화면 그림 글자 표 (pack/gen_pack.py 가 만든다. 직접 고치지 말 것)",
        "# 이름: {char: 문자, width: 진행 폭 (글꼴 픽셀, 음수는 왼쪽으로 민다), font: 글꼴}",
        "# 플러그인은 이 표로 Component.text(char).font(font) 를 만든다. 문자 번호를 코드에 적지 않는다.",
        "# you_died 는 사망 화면 제목 한 줄 전체 (deathScreen.title 과 같은 문자열). 나머지는 한 글자씩.",
    ]
    adv = {g.char: g.width for g in glyphs if g.font == hud.DEFAULT_FONT}
    rows = [("you_died", title, sum(adv[ch] for ch in title), hud.DEFAULT_FONT)]
    rows += [(g.name, g.char, g.width, g.font) for g in glyphs]
    for name, ch, width, font in rows:
        lines.append(f"{name}: {{char: {yaml_str(ch)}, width: {width}, font: {yaml_str(font)}}}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def death_title_mode(argv):
    """--death-title screen|plugin (기본 screen). 모르는 값이면 None."""
    mode = "screen"
    for i, a in enumerate(argv):
        if a == "--death-title" and i + 1 < len(argv):
            mode = argv[i + 1]
        elif a.startswith("--death-title="):
            mode = a.split("=", 1)[1]
    if mode not in ("screen", "plugin"):
        print("--death-title 은 screen 또는 plugin 이다:", mode)
        return None
    return mode


def main(argv):
    mode = death_title_mode(argv)
    if mode is None:
        return 2
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # 1. pack.mcmeta, pack.png
    write_json(os.path.join(OUT, "pack.mcmeta"), {
        "pack": {"description": PACK_DESCRIPTION, "min_format": PACK_FORMAT, "max_format": PACK_FORMAT},
    })
    icon = pack_icon()
    icon.save(os.path.join(OUT, "pack.png"))

    # 2. HUD 그림과 글꼴
    glyphs, fonts = hud.build(OUT)
    for (ns, name), data in fonts.items():
        write_json(os.path.join(OUT, "assets", ns, "font", name + ".json"), data)
    gui_skin.build(OUT)   # 체력·단축 슬롯·창·단추·설명 칸 그림 (스태미나 막대는 hud 의 것을 덮어쓴다)
    title = hud.death_title(glyphs)

    # 3. 사망 화면 언어
    # YOU DIED 는 한 번만 보인다 (5.6). 기본은 사망 화면 제목 자리 (플러그인 death.title: false).
    # plugin 이면 이 제목을 비우고 플러그인이 화면 제목으로 띄운다 (둘을 함께 쓰면 겹쳐 보였다)
    lang = dict(DEATH_LANG)
    lang["deathScreen.title"] = title if mode == "screen" else ""
    lang = dict(sorted(lang.items()))
    for code in LANGS:
        write_json(os.path.join(OUT, "assets", "minecraft", "lang", code + ".json"), lang)

    # 4. artlint (오류가 있으면 zip 을 만들지 않는다)
    report = artlint.lint([OUT], OUT)
    if report.errors:
        print("artlint 오류가 있어 팩을 묶지 않는다.")
        return 1

    # 5. 정렬 zip
    data, names = zip_bytes(OUT)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(os.path.join(RES, "pack.zip"), "wb") as f:
        f.write(data)
    if "--no-dist" not in argv:
        packs = os.path.join(DIST, "packs")
        os.makedirs(packs, exist_ok=True)
        for old in sorted(os.listdir(packs)):
            if old.endswith(".zip") and old != sha1 + ".zip":
                os.remove(os.path.join(packs, old))
                print("지난 팩을 지웠다:", old)
        with open(os.path.join(packs, sha1 + ".zip"), "wb") as f:
            f.write(data)

    # 6. 글자 표, 미리보기
    write_glyphs(os.path.join(RES, "glyphs.yml"), glyphs, title)
    sheet, cell_w, _ = hud.you_died_sheet()
    bar_bg, bar_fill = gui_skin.stamina_bar()
    previews.write_all(PREVIEW, {
        "sheet": sheet, "cell_w": cell_w, "glyphs": glyphs, "title": title, "height": hud.YOU_DIED_HEIGHT,
        "ascent": hud.YOU_DIED_ASCENT, "lang": lang, "bar_bg": bar_bg, "bar_fill": bar_fill, "icon": icon,
    })
    gui_skin.write_previews(OUT, PREVIEW)
    print(f"팩 파일 {len(names)}개, {len(data):,} 바이트, sha1 {sha1}")
    print(f"  → {os.path.relpath(os.path.join(RES, 'pack.zip'), ROOT)}"
          + ("" if "--no-dist" in argv else f", dist/packs/{sha1}.zip"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
