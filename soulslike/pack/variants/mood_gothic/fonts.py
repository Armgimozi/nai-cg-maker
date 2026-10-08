"""
mood_gothic 의 글꼴 (모두 SIL OFL 1.1). 받고 → 굵기를 고정하고 → 쓰는 글자만 남기고 → 이름을 바꾼다.

  본문 로마자  Cormorant Garamond (wght 600)  가라몽 계열의 높은 대비. 숫자는 고정 폭 라이닝 (.tf) 으로 바꿔 끼운다
                                             (수치 칸의 숫자를 오른쪽에 맞추려고, 셈은 advance())
  본문 한글    Nanum Myeongjo Bold           옛 명조. 얇은 획이 GUI 배율 2 에서도 남는 굵기
  제목 로마자  Marcellus SC                  나팔꼴 세리프의 로마 비문 대문자 (다크 소울 제목의 Optimus Princeps 쪽)
  제목 한글    Song Myung (송명)              옛 목판 인쇄의 무거운 명조. 아이템 이름·창 제목

받는 곳은 google/fonts 저장소 (raw.githubusercontent.com). 원본은 캐시 폴더 (GOTHIC_FONT_CACHE, 기본
~/.cache/souls-fonts-gothic) 에 두고 팩에는 잘라 낸 것만 넣는다. 잘라 낸 글꼴은 개조판이라 (OFL 4·5항) 글꼴 이름을
"Souls Gothic ..." 으로 바꾼다 (Marcellus, NanumMyeongjo 는 예약 글꼴 이름이라 개조판에 그 이름을 쓸 수 없다). 저작권 줄
(name 0) 과 사용 허락 줄 (name 13, 14) 은 그대로 둔다. 마인크래프트는 TTF 의 GSUB/GPOS 를 쓰지 않으므로 지우고 힌팅도 지운다.
"""
import io
import os
import urllib.request

from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
# 열쇠: (저장소 글꼴 경로, 저장소 사용 허락 글 경로, 원 이름)
SOURCES = {
    "cormorant": ("cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf", "cormorantgaramond/OFL.txt", "Cormorant Garamond"),
    "nanum_myeongjo_b": ("nanummyeongjo/NanumMyeongjo-Bold.ttf", "nanummyeongjo/OFL.txt", "Nanum Myeongjo"),
    "marcellus_sc": ("marcellussc/MarcellusSC-Regular.ttf", "marcellussc/OFL.txt", "Marcellus SC"),
    "song_myung": ("songmyung/SongMyung-Regular.ttf", "songmyung/OFL.txt", "Song Myung"),
}


def cache_dir():
    d = os.environ.get("GOTHIC_FONT_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "souls-fonts-gothic")
    os.makedirs(d, exist_ok=True)
    return d


def fetch(key):
    """(글꼴 경로, 사용 허락 글 경로). 캐시에 없으면 받는다."""
    font_rel, ofl_rel, _ = SOURCES[key]
    d = os.path.join(cache_dir(), font_rel.split("/")[0])
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
    """로마자: 인쇄 가능한 ASCII, 라틴-1 보충, 일반 문장 부호."""
    s = [chr(c) for c in range(0x20, 0x7F)] + [chr(c) for c in range(0xA0, 0x100)]
    s += list("‐‑‒–—―‘’‚“”„†‡•…"
              "‰′″‹›™−ŒœŠšŸŽž")
    return s


def hangul_set():
    s = ks_x_1001_hangul()
    s += [chr(c) for c in range(0x3131, 0x318F)]       # 호환 자모 (ㄱ ㅏ ...)
    s += list("、。〈〉《》「」『』【】〜※")
    return s


def _instance(path, wght):
    f = TTFont(path)
    if "fvar" in f:
        f = instancer.instantiateVariableFont(f, {"wght": wght})
    return f


def _rename(font, family, origin):
    name = font["name"]
    keep = {0, 13, 14}
    ps = family.replace(" ", "")
    for rec in list(name.names):
        if rec.nameID not in keep:
            name.removeNames(nameID=rec.nameID)
    for nid, val in ((1, family), (2, "Regular"), (3, f"{ps};souls-gothic-subset"), (4, family),
                     (5, "Version 1.000; subset"), (6, ps),
                     (10, f"Subset of {origin} for Square Soul (pack/variants/mood_gothic). SIL OFL 1.1.")):
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)


def _swap_digits(font, suffix):
    """cmap 의 0..9 를 suffix 붙은 그림 (예 .tf 고정 폭 라이닝) 으로 바꿔 끼운다. 없으면 그대로."""
    order = set(font.getGlyphOrder())
    names = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    if not all(n + suffix in order for n in names):
        return False
    for table in font["cmap"].tables:
        if table.isUnicode():
            for i, n in enumerate(names):
                if 0x30 + i in table.cmap:
                    table.cmap[0x30 + i] = n + suffix
    return True


def make(key, chars, out_path, family, wght=None, digits=None, pua=None):
    """
    key 글꼴 (wght 로 고정) 에서 chars 만 남겨 out_path 에 쓴다. digits 가 있으면 숫자 그림을 바꿔 끼운다.
    pua = {개인 영역 글자: 원 글자} 면 그 그림을 개인 영역에도 이어 둔다 (기본 글꼴 안에서 언어 파일로 이 글꼴을 고르려고).
    돌려주는 값: (out_path, 바이트, 남은 글자 수).
    """
    src, _ = fetch(key)
    font = _instance(src, wght) if wght else TTFont(src)
    if digits:
        _swap_digits(font, digits)
    cmap = font.getBestCmap()
    have = [c for c in chars if ord(c) in cmap]
    if pua:
        for table in font["cmap"].tables:
            if table.isUnicode():
                for p, ch in pua.items():
                    if ord(ch) in cmap:
                        table.cmap[ord(p)] = cmap[ord(ch)]
        have += [p for p, ch in pua.items() if ord(ch) in cmap]
    opts = ft_subset.Options()
    opts.layout_features = []
    opts.hinting = False
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 10, 13, 14]
    opts.name_languages = [0x409]
    opts.drop_tables += ["GSUB", "GPOS", "GDEF", "BASE", "JSTF", "MATH", "DSIG", "STAT", "meta", "vhea", "vmtx", "VORG"]
    sub = ft_subset.Subsetter(opts)
    sub.populate(unicodes=[ord(c) for c in have])
    sub.subset(font)
    _rename(font, family, SOURCES[key][2])
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path, len(data), len(have)


def licence_text(key):
    _, ofl = fetch(key)
    with open(ofl, encoding="utf-8") as f:
        return f.read()


class Metrics:
    """
    잘라 낸 TTF 의 글자 폭을 마인크래프트와 같은 식으로 잰다: FreeType 이 size × oversample 픽셀 em 에 힌팅해 그리면
    진행 폭이 그 크기의 정수 픽셀로 반올림되고, 마인크래프트는 그것을 oversample 로 나눈다 (GUI 픽셀, 1/oversample 단위).
    """

    def __init__(self, path, size, oversample):
        f = TTFont(path)
        self.upm = f["head"].unitsPerEm
        self.cmap = f.getBestCmap()
        self.hmtx = f["hmtx"].metrics
        self.px = size * oversample
        self.oversample = oversample

    def has(self, ch):
        return ord(ch) in self.cmap

    def advance(self, ch):
        g = self.cmap.get(ord(ch))
        if g is None:
            return None
        units = self.hmtx[g][0]
        return int(units * self.px / self.upm + 0.5) / self.oversample
