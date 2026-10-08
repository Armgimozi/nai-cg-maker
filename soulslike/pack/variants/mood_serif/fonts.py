"""
mood_serif 시안의 글꼴 (모두 SIL OFL 1.1). 받고 → 굵기를 고정하고 → 쓰는 글자만 남기고 → 이름을 바꾼다.

  본문 한글   Noto Serif KR (wght 500)  명조. KS X 1001 완성형 2,350자 + 호환 자모 + 한글에 붙는 문장 부호
  본문 로마자 EB Garamond (wght 500)    다크 소울 설명문의 가라몽 계열. ASCII + 라틴-1 + 일반 문장 부호
  제목 로마자 Cinzel (wght 600)         로마 비문 대문자 (Trajan / Optimus Princeps 계열). 창 제목·아이템 이름·보스 이름
  제목 한글   Noto Serif KR (wght 600)  같은 명조의 한 단 굵은 것 (souls:title 에서 조금 크게)

받는 곳은 google/fonts 저장소 (raw.githubusercontent.com). 받은 원본은 캐시 폴더 (SOULS_FONT_CACHE, 기본
~/.cache/souls-fonts) 에 두고 팩에는 잘라 낸 것만 넣는다. 잘라 낸 글꼴은 개조판이라 (OFL 4·5항) 이름 표의 글꼴 이름을
"Souls ..." 로 바꾸고 저작권 줄 (name 0) 과 사용 허락 줄 (name 13, 14) 은 그대로 둔다. 원 글꼴 셋 다 예약 글꼴 이름
(Reserved Font Name) 이 없지만 같은 이름의 원본과 헷갈리지 않게 바꾼다.

마인크래프트는 TTF 의 GSUB/GPOS (합자·글자 사이) 를 쓰지 않으므로 지운다. 힌팅 명령도 지운다 (크기를 줄이고, FreeType
자동 힌팅에 맡긴다).
"""
import io
import os
import urllib.request

from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
SOURCES = {
    # 열쇠: (저장소 경로, 가변 글꼴이면 wght, 원 이름)
    "noto_serif_kr": ("notoserifkr/NotoSerifKR%5Bwght%5D.ttf", "notoserifkr/OFL.txt", "Noto Serif KR"),
    "eb_garamond": ("ebgaramond/EBGaramond%5Bwght%5D.ttf", "ebgaramond/OFL.txt", "EB Garamond"),
    "cinzel": ("cinzel/Cinzel%5Bwght%5D.ttf", "cinzel/OFL.txt", "Cinzel"),
}


def cache_dir():
    d = os.environ.get("SOULS_FONT_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "souls-fonts")
    os.makedirs(d, exist_ok=True)
    return d


def fetch(key):
    """(글꼴 경로, 사용 허락 글 경로). 없으면 받는다."""
    font_rel, ofl_rel, _ = SOURCES[key]
    d = os.path.join(cache_dir(), key)
    os.makedirs(d, exist_ok=True)
    out = []
    for rel in (font_rel, ofl_rel):
        path = os.path.join(d, os.path.basename(rel).replace("%5B", "[").replace("%5D", "]"))
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print("  글꼴 받기:", RAW + rel)
            with urllib.request.urlopen(RAW + rel, timeout=120) as r:
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
    """본문 로마자: 인쇄 가능한 ASCII, 라틴-1 보충, 일반 문장 부호 몇."""
    s = [chr(c) for c in range(0x20, 0x7F)] + [chr(c) for c in range(0xA0, 0x100)]
    s += list("‐‑‒–—―‘’‚“”„†‡•…"
              "‰′″‹›™←↑→↓−·ˆ˜Œœ"
              "ŠšŸŽž")
    return s


def hangul_set():
    s = ks_x_1001_hangul()
    s += [chr(c) for c in range(0x3131, 0x318F)]       # 호환 자모 (ㄱ ㅏ ...)
    s += list("、。〈〉《》「」『』【】〜※·")
    return s


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
                     (6, ps), (10, f"Subset of {origin} for Square Soul (pack/variants/mood_serif). SIL OFL 1.1.")):
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)


def make(key, wght, chars, out_path, family, style="", pua_mirror=None):
    """
    key 글꼴을 wght 로 고정해 chars 만 남겨 out_path 에 쓴다. pua_mirror = {개인 영역 시작: 글자 목록} 이면 그 글자의
    그림을 개인 영역 (시작 + 순번) 에도 이어 둔다 (언어 파일의 창 제목을 바닐라 글꼴 안에서 이 글꼴로 그리려고).
    돌려주는 값: (out_path, 바이트, 남은 글자 수, 개인 영역 표 {글자: 개인 영역 글자}).
    """
    src, _ = fetch(key)
    font = _instance(src, wght)
    cmap = font.getBestCmap()
    have = [c for c in chars if ord(c) in cmap]
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


def metrics(path):
    """(upm, hhea 오름, hhea 내림, 대문자 높이, x 높이) 와 cmap, hmtx."""
    f = TTFont(path)
    os2 = f["OS/2"]
    return {"upm": f["head"].unitsPerEm, "asc": f["hhea"].ascent, "desc": f["hhea"].descent,
            "cap": getattr(os2, "sCapHeight", 0), "x": getattr(os2, "sxHeight", 0),
            "cmap": f.getBestCmap(), "hmtx": f["hmtx"].metrics, "glyf": f["glyf"] if "glyf" in f else None}
