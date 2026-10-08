"""
mood2_refined 의 글꼴 (모두 SIL OFL 1.1). 받고 → 굵기를 고정하고 → 쓰는 글자만 남기고 → 이름을 바꾼다.
mood_serif (1차 시안 A) 의 글꼴 그대로다: 받는 곳·잘라 내기·이름 바꾸기·사용 허락 글은 mood_serif/fonts.py 와 같고, 둘만 다르다.

  1. 힌팅을 끄지 않고 "힌팅 없음" 으로 고정한다. 1차 시안은 힌팅 명령을 지웠는데, 명령이 하나도 없는 TrueType 글꼴은 FreeType 이
     자동 힌팅 (보통 모드) 으로 그린다 (ftobjs.c: maxSizeOfInstructions·fpgm·prep 이 모두 0 이면 autohint). 그 자동 힌팅이 글자마다
     획을 다르게 격자에 붙여 "삐뚤빼뚤" 의 한 몫이었다. 여기서는 아무 일도 하지 않는 prep (SVTCA) 하나를 넣어 TrueType 해석기로 가게
     하고 (글자에는 명령이 없으니 윤곽 그대로), 글자는 12배 (oversample 12) 로 그려 셰이더가 화면 픽셀마다 정확한 면적 평균을 낸다
     (text.py).
  2. 한글 개인 영역 거울: 제목 글꼴의 한글 몇 자를 개인 영역에도 이어 둔다 (바닐라 창 제목을 언어 파일만으로 제목 글꼴로).

  본문 한글   Noto Serif KR (wght 500)   명조. KS X 1001 완성형 2,350자 + 언어 파일이 쓰는 한글 + 호환 자모 + 문장 부호
  본문 로마자 EB Garamond (wght 500)     다크 소울 설명문의 가라몽 계열
  제목 로마자 Cinzel (wght 600)          로마 비문 대문자 (보스 이름, 창 제목, 아이템 이름)
  제목 한글   Noto Serif KR (wght 700)   같은 명조의 굵은 것

원본은 캐시 폴더 (SOULS_FONT_CACHE, 기본 ~/.cache/souls-fonts/mood2_refined) 에 두고, 없으면 google/fonts 저장소에서 받는다.
잘라 낸 글꼴은 개조판이라 (OFL 4·5항) 이름 표의 글꼴 이름을 "Souls ..." 로 바꾸고 저작권 줄 (name 0) 과 사용 허락 줄
(name 13, 14) 은 그대로 둔다 (세 글꼴 다 예약 글꼴 이름이 없지만 원본과 헷갈리지 않게).
"""
import io
import json
import os
import urllib.request

from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.varLib import instancer

RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
SOURCES = {
    "noto_serif_kr": ("notoserifkr/NotoSerifKR%5Bwght%5D.ttf", "notoserifkr/OFL.txt", "Noto Serif KR"),
    "eb_garamond": ("ebgaramond/EBGaramond%5Bwght%5D.ttf", "ebgaramond/OFL.txt", "EB Garamond"),
    "cinzel": ("cinzel/Cinzel%5Bwght%5D.ttf", "cinzel/OFL.txt", "Cinzel"),
}


def cache_dir():
    d = os.environ.get("SOULS_FONT_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "souls-fonts", "mood2_refined")
    os.makedirs(d, exist_ok=True)
    return d


def fetch(key):
    """(글꼴 경로, 사용 허락 글 경로). 캐시에 없으면 받는다."""
    font_rel, ofl_rel, _ = SOURCES[key]
    d = os.path.join(cache_dir(), key)
    os.makedirs(d, exist_ok=True)
    out = []
    for rel in (font_rel, ofl_rel):
        path = os.path.join(d, os.path.basename(rel).replace("%5B", "[").replace("%5D", "]"))
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print("  글꼴 받기:", RAW + rel)
            with urllib.request.urlopen(RAW + rel, timeout=180) as r:
                data = r.read()
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        out.append(path)
    return tuple(out)


def ks_x_1001_hangul():
    """KS X 1001 완성형 한글 2,350자 (EUC-KR 0xB0A1..0xC8FE)."""
    out = []
    for b1 in range(0xB0, 0xC9):
        for b2 in range(0xA1, 0xFF):
            try:
                out.append(bytes([b1, b2]).decode("euc-kr"))
            except UnicodeDecodeError:
                pass
    return out


def latin_set():
    s = [chr(c) for c in range(0x20, 0x7F)] + [chr(c) for c in range(0xA0, 0x100)]
    s += list("‐‑‒–—―‘’‚“”„†‡•…‰′″‹›™←↑→↓−·ˆ˜ŒœŠšŸŽž")
    return s


def hangul_set(extra=""):
    s = ks_x_1001_hangul()
    s += [chr(c) for c in range(0x3131, 0x318F)]
    s += list("、。〈〉《》「」『』【】〜※·")
    have = set(s)
    s += sorted({c for c in extra if 0xAC00 <= ord(c) <= 0xD7A3 and c not in have})
    return s


def lang_chars(pack):
    """팩의 언어 파일 (souls·minecraft 의 ko_kr, en_us) 이 쓰는 글자."""
    out = set()
    for ns in ("souls", "minecraft"):
        for lang in ("ko_kr", "en_us"):
            p = os.path.join(pack, "assets", ns, "lang", lang + ".json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    out |= set("".join(json.load(f).values()))
    return "".join(sorted(out))


def _instance(path, wght):
    f = TTFont(path)
    if "fvar" in f:
        f = instancer.instantiateVariableFont(f, {"wght": wght})
    return f


def _rename(font, family, style, origin):
    name = font["name"]
    keep = {0, 13, 14}
    full = f"{family} {style}".strip()
    ps = (family + "-" + style).replace(" ", "")
    for rec in list(name.names):
        if rec.nameID not in keep:
            name.removeNames(nameID=rec.nameID)
    for nid, val in ((1, family), (2, "Regular"), (3, f"{ps};souls-subset"), (4, full), (5, "Version 1.000; subset"),
                     (6, ps), (10, f"Subset of {origin} for Square Soul (pack/variants/mood2_refined). SIL OFL 1.1.")):
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)


def _no_autohint(font):
    """아무것도 하지 않는 prep 하나: FreeType 이 이 글꼴을 자동 힌팅하지 않고 윤곽 그대로 그린다 (머리말 1)."""
    prog = ttProgram.Program()
    prog.fromAssembly(["SVTCA[0]"])
    t = newTable("prep")
    t.program = prog
    font["prep"] = t
    if "maxp" in font:
        font["maxp"].maxSizeOfInstructions = max(1, getattr(font["maxp"], "maxSizeOfInstructions", 0))


def make(key, wght, chars, out_path, family, style="", pua_mirror=None):
    """
    key 글꼴을 wght 로 고정해 chars 만 남겨 out_path 에 쓴다. pua_mirror = {개인 영역 시작: 글자 목록} 이면 그 글자의 그림을
    개인 영역 (시작 + 순번) 에도 이어 둔다. 돌려주는 값: (out_path, 바이트, 남은 글자 수, 개인 영역 표 {글자: 개인 영역 글자}).
    """
    src, _ = fetch(key)
    font = _instance(src, wght)
    cmap = font.getBestCmap()
    have = [c for c in dict.fromkeys(chars) if ord(c) in cmap]
    opts = ft_subset.Options()
    opts.layout_features = []
    opts.hinting = False
    opts.notdef_outline = True
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 10, 13, 14]
    opts.name_languages = [0x409]
    opts.drop_tables += ["GSUB", "GPOS", "GDEF", "BASE", "JSTF", "MATH", "DSIG", "STAT", "meta", "vhea", "vmtx", "VORG"]
    sub = ft_subset.Subsetter(opts)
    sub.populate(unicodes=[ord(c) for c in have])
    sub.subset(font)
    pua = {}
    if pua_mirror:
        cm = font.getBestCmap()
        for table in font["cmap"].tables:
            if not table.isUnicode():
                continue
            for start, mirrored in pua_mirror.items():
                for i, ch in enumerate(mirrored):
                    g = cm.get(ord(ch))
                    if g is not None:
                        table.cmap[start + i] = g
                        pua[ch] = chr(start + i)
    _no_autohint(font)
    _rename(font, family, style, SOURCES[key][2])
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path, len(data), len(have), pua


def licence_text(key):
    _, ofl = fetch(key)
    with open(ofl, encoding="utf-8") as f:
        return f.read()
