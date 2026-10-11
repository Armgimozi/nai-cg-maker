"""
mood_serif 의 글꼴 자리와 글자색 (한 곳에서 정한다). build.py·art.py·lang.py·shader.py 가 읽는다.

글꼴 크기는 GUI 픽셀. 마인크래프트 TTF 공급자는 FreeType 으로 size × oversample 픽셀 em 에 그려 1/oversample 로 줄여 놓는다.
oversample 은 GUI 배율 4 에서 한 텍셀 = 한 화면 픽셀이 되게 4 (배율 3·2 에서는 줄여 그린다. 실제 클라이언트로 봤다).
shift 는 0: 이 크기에서 한글은 줄 위 + 0 .. + 7.5, 로마자 바탕선은 줄 위 + 7 로 바닐라 글자와 같은 자리에 온다 (실제 클라이언트로 쟀다).
"""
import os

import fonts

OVERSAMPLE = 4.0

# 이름: (글꼴 열쇠, wght, 글자 묶음, 파일, 이름 표의 글꼴 이름, 굵기 이름)
FILES = {
    "serif_la": ("eb_garamond", 500, "latin", "Souls Serif Latin", "Medium"),
    "serif_kr": ("noto_serif_kr", 500, "hangul", "Souls Serif KR", "Medium"),
    "title_la": ("cinzel", 600, "latin", "Souls Title Latin", "SemiBold"),
    "title_kr": ("noto_serif_kr", 600, "hangul", "Souls Title KR", "SemiBold"),
}

# 공급자: (파일, size, shift y). 바닐라 글자 줄은 위에서 7 이 바탕선, 줄 높이 9 (설명 칸은 10)
BODY = [("serif_la", 10.5, 0.0), ("serif_kr", 9.0, 0.0)]
TITLE = [("title_la", 10.5, 0.0), ("title_kr", 9.5, 0.0)]
SPACE = 3                     # 낱말 사이 (바닐라 4. 명조는 좁게)

# 영어 창 제목을 Cinzel 로: ASCII 0x20..0x7E 를 개인 영역 U+F120.. 에 이어 둔다 (기본 글꼴 안에서 언어 파일로 고른다)
PUA_TITLE = 0xF120

# 글자색 (팔레트 이름 → 값은 pack/palette.py). 셰이더가 바닐라 색을 이 색으로 바꾼다
TEXT = "bone2"               # 바닐라 흰 글 (단추, 화면 제목, 채팅, 개수): 뼈빛
TEXT_GREY = "parch2"         # §7: 창 제목·사망 화면 단추 → 흐린 옛 금빛
TEXT_OFF = "ash3"            # 꺼진 단추 (#A0A0A0)
TEXT_DARK = "parch0"         # §8
SHADOW = ("ink0", 200)       # 그림자 (바닐라는 글자색 × 0.25): 따뜻한 먹


def write_fonts(pack):
    """TTF 넷과 사용 허락 글을 팩에 쓰고, 글꼴 정의 (minecraft:default 에 덧붙임, souls:title) 를 쓴다."""
    import json
    sets = {"latin": fonts.latin_set(), "hangul": fonts.hangul_set()}
    info = {"files": {}, "pua": {}}
    font_dir = os.path.join(pack, "assets", "souls", "font")
    for name, (key, wght, which, family, style) in FILES.items():
        mirror = {PUA_TITLE: [chr(c) for c in range(0x20, 0x7F)]} if name == "title_la" else None
        path, size, n, pua = fonts.make(key, wght, sets[which], os.path.join(font_dir, name + ".ttf"), family, style,
                                        pua_mirror=mirror)
        info["files"][name] = {"path": path, "bytes": size, "glyphs": n, "key": key}
        if pua:
            info["pua"] = pua
        print(f"  글꼴 {name}: {fonts.SOURCES[key][2]} wght {wght}, 글자 {n}, {size:,} 바이트")
    lic_dir = os.path.join(font_dir, "licenses")
    os.makedirs(lic_dir, exist_ok=True)
    notice = ["Block Soul resource pack - fonts (pack/variants/mood_serif)", "",
              "The TrueType fonts in assets/souls/font/ are subsets of the following fonts, licensed under the",
              "SIL Open Font License, Version 1.1. They were renamed (\"Souls ...\") because they are modified (subset).", ""]
    for key in sorted({v[0] for v in FILES.values()}):
        text = fonts.licence_text(key)
        fname = "ofl-" + fonts.SOURCES[key][2].lower().replace(" ", "-") + ".txt"
        with open(os.path.join(lic_dir, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        notice.append(f"  {fonts.SOURCES[key][2]}: {text.splitlines()[0].strip()} -> assets/souls/font/licenses/{fname}")
    with open(os.path.join(pack, "FONTS-OFL.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(notice) + "\n")
    info["providers_body"] = [ttf(n, s, y) for n, s, y in BODY]
    info["providers_title"] = [ttf(n, s, y) for n, s, y in TITLE]
    return info


def ttf(name, size, shift_y, skip=""):
    p = {"type": "ttf", "file": f"souls:{name}.ttf", "size": size, "oversample": OVERSAMPLE, "shift": [0.0, shift_y]}
    if skip:
        p["skip"] = skip
    return p
