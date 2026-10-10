"""
픽셀 명조 (mood_pixelserif): 열린 글꼴 (SIL OFL) 의 명조·세리프를 2배 밀도 1비트 픽셀 글자로 굽는다.

마인크래프트의 unihex 글꼴 (바닐라 한글이 쓰는 그 꼴) 로 넣는다:
  - 칸은 16줄, 폭 8·16·24·32, 그림 한 칸 = GUI 0.5 픽셀 (2배 밀도). 클라이언트가 왼쪽·오른쪽 빈 열을 잘라 진행 폭을
    (잉크 폭 // 2) + 1 GUI 픽셀로 잰다. 글자 사이가 그림 1~2칸이라 bitmap 글꼴 (GUI 1픽셀 + 반올림) 보다 촘촘하다.
  - 그림자와 굵게는 GUI 0.5 픽셀 (그림 한 칸) 만 민다. 가는 명조 획에 그림자가 딱 붙어 새긴 글씨처럼 보인다
    (bitmap 글꼴은 GUI 1픽셀을 밀어 가는 획 옆에 검은 겹줄이 생긴다).
  - 1비트라 번지지 않는다. 글자 색은 바닐라처럼 글 색 하나 (흰색) 이고, 뼈빛·금빛은 글꼴 셰이더가 바꾼다 (build.py).

칸 안의 자리 (줄 위 = 0 행, GUI 픽셀로 바닐라 아스키와 같은 줄 높이)
  한글   나눔명조 Regular 16px, 단색 힌팅 (글꼴의 TrueType 힌트로 획이 1칸에 맞는다). 글꼴 기준선이 14 행
         (0..13 행 위, 14·15 행은 한글이 기준선 아래로 내려오는 몫). 칸을 넘는 몇 글자는 한 줄 올리거나 내린다
  로마자 EB Garamond 500, 8배로 그려 넓이로 줄인 뒤 문턱. 기준선 13 행 (영문 기준선이 한글 글자 아래끝보다 두 칸 위:
         명조 한글과 세리프 로마자를 섞어 짤 때의 보통 자리). 아래 내림 (g p q y j) 은 칸 아래 세 줄에 들게 줄여 그린다.
         숫자는 lnum (가지런한 숫자).
  제목   제목 글 (창 제목, 아이템 이름, 휴식 창 이름) 은 언어 파일에서 개인 영역 문자로 바꿔 따로 그린 글자를 쓴다:
         로마자는 Cinzel (로마 비문 대문자, 소문자 자리는 작은 대문자), 한글은 나눔명조 ExtraBold. 제목 글에 나오는
         글자만 굽는다.

글자 고르기
  한글   KS X 1001 완성형 2,350 자 + 바닐라·게임 언어 파일에 나오는 그 밖의 한글 + 호환 자모 (ㄱ..ㅣ)
  로마자 아스키 (! .. ~), 라틴-1 보충, 자주 쓰는 문장 부호 (· … – — ‘ ’ “ ” • ×)
  없는 글자는 바닐라 글꼴로 떨어진다 (바닐라 공급자가 뒤에 있다).

글꼴 원본은 내려받아 (~/.cache/souls-fonts, SOULS_FONT_CACHE) sha256 으로 확인한다. 팩에는 굽힌 1비트 글자 (unihex)
와 OFL 원문·저작권 줄만 들어간다. OFL 의 예약 글꼴 이름 (Nanum, NanumMyeongjo …) 을 쓰지 않으려고 팩 안 글꼴 이름은
souls:font/pixel_serif 다.
"""
import hashlib
import io
import os
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CELL = 16
HANGUL_BASE = 14          # 한글 글꼴 기준선 행 (0..13 위)
LATIN_BASE = 13           # 로마자 기준선 행 (0..12 위, 13..15 아래 내림)
SS = 8                    # 로마자 겹쳐 그리기 배수

GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {
    # 파일 이름: (주소, sha256, 저작권 원문 파일)
    "NanumMyeongjo-Regular.ttf": (GF + "nanummyeongjo/NanumMyeongjo-Regular.ttf",
                                  "7ed9e8653a8ed04285d51dc343ffea6eb3d9c73afc27383ea8929ee4ffd03205", "nanummyeongjo"),
    "NanumMyeongjo-Bold.ttf": (GF + "nanummyeongjo/NanumMyeongjo-Bold.ttf",
                               "bc9ed8e60d93fe6db054b8fb988481b625f2eef8cb2317ad0e9834681b8fe3f3", "nanummyeongjo"),
    "NanumMyeongjo-ExtraBold.ttf": (GF + "nanummyeongjo/NanumMyeongjo-ExtraBold.ttf",
                                    "60c0077fce069ba90ae97c0a3679f6eb3712e0ca637bdd0c15b72d335ec46db7", "nanummyeongjo"),
    "EBGaramond[wght].ttf": (GF + "ebgaramond/EBGaramond%5Bwght%5D.ttf",
                             "ef9512f92f6d579e5dc75af59a5a4b1b8b47d2eda89e00b954d44520e5369027", "ebgaramond"),
    "Cinzel[wght].ttf": (GF + "cinzel/Cinzel%5Bwght%5D.ttf",
                         "f4d83d34d1f6c741193e4acf4b3dff9531e5a67b6aa65228d00a7db72a4e0f34", "cinzel"),
}
LICENSES = {
    "nanummyeongjo": GF + "nanummyeongjo/OFL.txt",
    "ebgaramond": GF + "ebgaramond/OFL.txt",
    "cinzel": GF + "cinzel/OFL.txt",
}
CREDITS = {
    "nanummyeongjo": "Hangul body and title glyphs rasterised from Nanum Myeongjo (Regular, ExtraBold)",
    "ebgaramond": "Latin body glyphs rasterised from EB Garamond (weight 500)",
    "cinzel": "Latin title glyphs rasterised from Cinzel (weight 600)",
}


def cache_dir():
    d = os.environ.get("SOULS_FONT_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "souls-fonts")
    os.makedirs(d, exist_ok=True)
    return d


def _fetch(url, path):
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    with open(path, "wb") as f:
        f.write(data)
    return data


def font_file(name):
    """내려받은 글꼴 경로 (없으면 받는다). sha256 이 다르면 멈춘다."""
    url, sha, _ = FONTS[name]
    path = os.path.join(cache_dir(), name)
    if not os.path.exists(path):
        _fetch(url, path)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if got != sha:
        raise SystemExit(f"글꼴 {name} 의 sha256 이 다르다 ({got}). {path} 를 지우고 다시 받는다")
    return path


def license_text(key):
    path = os.path.join(cache_dir(), f"OFL_{key}.txt")
    if not os.path.exists(path):
        _fetch(LICENSES[key], path)
    return open(path, encoding="utf-8").read()


def load(name, size, wght=None):
    f = ImageFont.truetype(font_file(name), size)
    if wght is not None:
        f.set_variation_by_axes([wght])
    return f


# ─────────────────────────── 글자 고르기 ───────────────────────────

def ksx1001_hangul():
    """KS X 1001 완성형 한글 2,350 자 (EUC-KR B0A1..C8FE)."""
    out = []
    for lead in range(0xB0, 0xC9):
        for trail in range(0xA1, 0xFF):
            try:
                ch = bytes([lead, trail]).decode("euc-kr")
            except UnicodeDecodeError:
                continue
            if 0xAC00 <= ord(ch) <= 0xD7A3:
                out.append(ch)
    return out


COMPAT_JAMO = [chr(c) for c in range(0x3131, 0x3164)]
LATIN = ([chr(c) for c in range(0x21, 0x7F)] + [chr(c) for c in range(0xA1, 0x100) if c != 0xAD]
         + list("·…–—‘’‚“”„•×‹›†‡‰€™"))


def is_hangul(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3131 <= ord(ch) <= 0x318E


# ─────────────────────────── 굽기 ───────────────────────────

def _mono(font, ch, base):
    """단색 힌팅 그림 (글꼴 힌트). 칸 높이 CELL, 폭 넉넉히. (L 그림 0/255, 잉크 bbox)"""
    im = Image.new("L", (48, CELL + 8), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((4, base + 4), ch, font=font, fill=255, anchor="ls")
    return im


def _fit_rows(im):
    """여유 4줄을 둔 그림에서 CELL 줄을 고른다: 잉크가 칸을 넘으면 넘는 쪽에서 한두 줄 옮긴다."""
    bb = im.getbbox()
    top = 4
    if bb:
        if bb[3] > top + CELL:            # 아래로 넘친다 → 올린다
            top = bb[3] - CELL
        if bb[1] < top:                   # 위로 넘친다 → 내린다 (아래가 더 잘리면 위를 지킨다)
            top = bb[1]
    return im.crop((0, top, im.width, top + CELL))


def hangul_glyph(font, ch):
    return _fit_rows(_mono(font, ch, HANGUL_BASE))


def latin_glyph(font_hi, ch, base=LATIN_BASE, thr=0.42, squash=0.62, features=None):
    """
    로마자: SS 배로 그려 기준선 아래 (내림) 를 squash 배로 눌러 칸 아래 세 줄에 넣고, 넓이 평균으로 줄여 thr 문턱.
    font_hi 는 SS 배 크기 글꼴.
    """
    W, H = 48 * SS, (CELL + 8) * SS
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    d.text((4 * SS, (base + 4) * SS), ch, font=font_hi, fill=255, anchor="ls", features=features)
    a = np.asarray(im, dtype=np.float32) / 255.0
    b0 = (base + 4) * SS
    if squash < 1.0:
        below = a[b0:, :]
        n = below.shape[0]
        m = int(round(n * squash))
        if m > 0:
            idx = np.minimum((np.arange(m) / squash).astype(int), n - 1)
            # 누를 때 겹치는 줄은 최댓값 (가는 획이 사라지지 않게)
            sq = np.zeros((m, a.shape[1]), dtype=np.float32)
            for i in range(m):
                lo = int(i / squash)
                hi = max(lo + 1, int((i + 1) / squash))
                sq[i] = below[lo:hi].max(axis=0)
            a = np.vstack([a[:b0], sq, np.zeros((n - m, a.shape[1]), dtype=np.float32)])
    h, w = a.shape[0] // SS, a.shape[1] // SS
    blk = a[:h * SS, :w * SS].reshape(h, SS, w, SS)
    cov = blk.mean(axis=(1, 3))
    on = cov >= thr
    # 가는 획 지키기: 칸을 반쯤만 덮는 가는 가로획 (e 의 가로줄, t·f 의 가로대) 과 세로획은 넓이 평균이 문턱 아래라
    # 사라진다. 칸 안의 한 겹 (가로 한 줄 / 세로 한 줄) 을 거의 다 덮는데 위아래 (좌우) 이웃이 모두 꺼졌으면 켠다
    row_full = blk.mean(axis=3).max(axis=1)      # 칸 안 가로 한 줄이 덮인 몫의 최댓값
    col_full = blk.mean(axis=1).max(axis=2)      # 칸 안 세로 한 줄
    pad = np.pad(on, 1)
    up, down, left, right = pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]
    thin_h = (row_full >= 0.8) & (cov >= 0.16) & ~up & ~down
    thin_v = (col_full >= 0.8) & (cov >= 0.16) & ~left & ~right
    on = on | thin_h | thin_v
    bits = on.astype(np.uint8) * 255
    out = Image.fromarray(bits, "L")
    return _fit_rows(out)


def ink(img):
    """잉크만 남긴 1비트 그림 (왼쪽·오른쪽 빈 열을 자른다. 높이는 CELL 그대로)."""
    bb = img.getbbox()
    if not bb:
        return None
    return img.crop((bb[0], 0, bb[2], CELL))


def advance(img):
    """unihex 진행 폭 (GUI 픽셀): 잉크 폭 // 2 + 1."""
    return img.width // 2 + 1


# ─────────────────────────── unihex ───────────────────────────

def hex_line(cp, img):
    """한 글자 unihex 줄 "XXXX:..." (폭 8/16/24/32 가운데 잉크가 드는 가장 작은 것, 잉크는 왼쪽에 붙인다)."""
    w = img.width
    for W in (8, 16, 24, 32):
        if w <= W:
            break
    else:
        raise ValueError(f"U+{cp:04X} 잉크 폭 {w} 이 32 를 넘는다")
    px = img.load()
    rows = []
    for y in range(CELL):
        v = 0
        for x in range(W):
            bit = 1 if x < w and px[x, y] else 0
            v = (v << 1) | bit
        rows.append(f"{v:0{W // 4}X}")
    return f"{cp:04X}:" + "".join(rows)


def hex_zip(glyphs, name="pixel_serif.hex"):
    """{코드포인트: 잉크 그림} → unihex zip 바이트 (정렬, 날짜 고정)."""
    lines = [hex_line(cp, img) for cp, img in sorted(glyphs.items())]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, "\n".join(lines) + "\n", compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


# ─────────────────────────── 글자 묶음 ───────────────────────────

class Face:
    """한 벌의 굽는 법: 글자 → 잉크 그림 (없으면 None)."""

    def __init__(self, hangul=None, latin=None, latin_kw=None):
        self.hangul, self.latin, self.latin_kw = hangul, latin, latin_kw or {}
        self._cache = {}

    def glyph(self, ch):
        if ch in self._cache:
            return self._cache[ch]
        img = None
        if is_hangul(ch):
            if self.hangul is not None:
                img = ink(hangul_glyph(self.hangul, ch))
        elif self.latin is not None:
            img = ink(latin_glyph(self.latin, ch, **self.latin_kw))
        self._cache[ch] = img
        return img


def body_face():
    return Face(hangul=load("NanumMyeongjo-Regular.ttf", 16),
                latin=load("EBGaramond[wght].ttf", 18 * SS, 500),
                latin_kw={"thr": 0.42, "squash": 0.6, "features": ["lnum", "kern"]})


def title_face():
    return Face(hangul=load("NanumMyeongjo-ExtraBold.ttf", 16),
                latin=load("Cinzel[wght].ttf", 16 * SS, 600),
                latin_kw={"thr": 0.45, "squash": 0.6, "features": ["lnum"]})
