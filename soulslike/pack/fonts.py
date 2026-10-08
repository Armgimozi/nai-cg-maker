"""
게임 글꼴 (DESIGN.md 10.9 "글꼴", 2026-10-08 사용자 결정: UI 는 고딕 촛불 시안 B). gen_pack.py 가 부른다.

TTF 를 팩에 넣지 않고 우리가 FreeType 으로 미리 그린 그림을 bitmap 글꼴 공급자로 넣는다. 바닐라 화면·채팅·설명 칸·개수까지
모든 글이 명조·가라몽으로 그려진다.

왜 미리 그리나 (2026-10-08 사용자: "글자가 좀 삐뚤빼뚤하네")
  TTF 공급자는 클라이언트가 글자마다 size × oversample 픽셀로 그려 1/oversample GUI 픽셀 단위의 제멋대로인 자리 (진행 폭이 소수) 에
  놓고 NEAREST 로 읽어, GUI 배율 3 에서 줄이 하나씩 빠지거나 두 번 찍혀 같은 글자도 자리마다 굵기가 달랐다.

어떻게
  * 모든 글자를 GUI 한 픽셀에 K = 4 텍셀로 그린다 (FreeType 자동 힌팅 light: 바탕선·x 높이·대문자 높이를 텍셀 격자에 맞춘다).
  * 칸은 K 의 배수, 바탕선은 칸 위에서 ascent × K 텍셀 (GUI 픽셀 경계), 공급자 height = 칸 높이 / K 라 글자 네모가 늘 GUI 픽셀
    격자에 놓인다. 진행 폭은 정수 GUI 픽셀 (글자를 그 폭 가운데에 놓아 반올림 오차를 양쪽에 나눈다): 같은 글자는 어느
    자리에서나 텍셀 격자가 화면 픽셀에 똑같이 겹친다 (배율 2·3·4 모두). 바탕선은 하나다.
  * 텍셀: R = 글자 덮임 (32 단), B = 1 과 알파 0 이 "우리 글자" 표식. 글꼴 셰이더 (shaders.py rendertype_text.fsh) 가 이 텍셀을
    화면 픽셀이 덮는 넓이만큼 섞어 (area filter) 흰 글자로 읽는다: 배율 4 는 1:1, 2 는 2×2 평균, 3 은 4/3 텍셀 상자. 바닐라
    그림자 사본은 셰이더가 반 픽셀 오른쪽 아래에 덮임을 흐려 먹빛 테두리로 그린다. **이 셰이더가 없으면 글자가 보이지 않는다**
    (알파 0): 글꼴 셰이더는 이 글꼴의 일부다 (10.8).
  * 진행 폭: 클라이언트는 bitmap 글자의 폭을 "알파가 0 이 아닌 가장 오른쪽 열 + 1" 로 재 (int)(0.5 + 폭 × 배율) + 1 을 쓴다.
    글자는 알파 0 이라 (A-1)×K - 1 열의 맨 아래 칸에 알파 1 점 하나만 찍어 진행 폭을 정확히 A (글꼴의 진행 폭을 반올림한 정수
    GUI 픽셀) 로 정한다. 글자는 칸 안에서 다음 글자 자리로 넘어가도 된다 (덮임은 R 에 있다).

글꼴과 역할 (모두 SIL Open Font License 1.1, 받는 곳 github.com/google/fonts. 팩에는 TTF 가 아니라 그린 그림만 들어간다.
OFL 원문은 팩의 assets/souls/font/licenses/, 알림은 팩 뿌리 FONTS-OFL.txt)
  본문 로마자 EB Garamond (wght 600)            ASCII, 라틴-1, 문장 부호             minecraft:default
  본문 한글   Noto Serif KR (wght 600)          KS X 1001 2,350 자 + 호환 자모 + 부호 minecraft:default
  제목 로마자 Cinzel (wght 700)                 로마 비문 대문자                    souls:title, 창 제목 (기본 글꼴 U+F120~)
  제목 한글   Nanum Myeongjo ExtraBold          제목에 나오는 음절만               souls:title, 창 제목 (기본 글꼴 U+F200~)
  souls:title 은 YAML 의 꼴 태그 <font:souls:title> 이 고른다 (무기 이름, 보스 이름, 화톳불 이름). 창 제목 (일시 정지의 게임 메뉴,
  인벤토리·제작대·상자) 은 언어 문자열이 글꼴을 고를 수 없어 기본 글꼴의 개인 영역 글자로 넣고 언어 파일이 그 글자를 쓴다
  (typeset.py). 원본 TTF 는 빌드 때 ~/.cache/souls-fonts/ofl (SOULS_FONT_CACHE) 에 받아 sha256 으로 확인한다.

기본 글꼴 개인 영역 (typeset.py 의 상수): U+F120~F17E 제목 로마자, U+F200~ 제목 한글, U+E300 제목 밑 금실, U+E380~E38F 빈칸
(±1 … 128). U+E000~E01F 는 사망 화면 (hud.py).
"""
import hashlib
import json
import math
import os
import urllib.request

import freetype
import numpy as np
from PIL import Image

import typeset
import uidraw
from uidraw import Img, Mask

K = typeset.K               # 텍셀 / GUI 픽셀
MARGIN_L = 1                # 글자 왼쪽 여백 (텍셀): 셰이더의 상자 거르개가 칸 밖 (아틀라스 이웃) 을 읽지 않게
HALO = 3                    # 그림자 (셰이더가 덮임을 흐려 그린다) 가 글자 밖으로 번지는 텍셀: 칸에 이만큼 여백
LEVELS = 32                 # 덮임 단 수
MARK_B = 1                  # B = 1, 알파 0 (진행 폭 점만 1): 셰이더가 우리 글자 텍셀로 알아본다
RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
# 열쇠: (저장소 폴더, 파일, 원 이름, 글꼴 sha256, OFL.txt sha256). 받은 파일이 다르면 멈춘다 (같은 입력 → 같은 팩)
SOURCES = {
    "noto_serif_kr": ("notoserifkr", "NotoSerifKR%5Bwght%5D.ttf", "Noto Serif KR",
                      "11f8d5de6f1b79195efba3828aaa2ec95c1178f5ae976fb23c8d53250a9938f3",
                      "5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6"),
    "eb_garamond": ("ebgaramond", "EBGaramond%5Bwght%5D.ttf", "EB Garamond",
                    "ef9512f92f6d579e5dc75af59a5a4b1b8b47d2eda89e00b954d44520e5369027",
                    "0985066662eb755ed3683ae5482a81a9195b49ce3f7e165cc2388b3dbece7dd7"),
    "cinzel": ("cinzel", "Cinzel%5Bwght%5D.ttf", "Cinzel",
               "f4d83d34d1f6c741193e4acf4b3dff9531e5a67b6aa65228d00a7db72a4e0f34",
               "f2b3029aba64c378bf0963b62945eee15e564fe4330b934c8f2eb058282b5e83"),
    "nanum_myeongjo_eb": ("nanummyeongjo", "NanumMyeongjo-ExtraBold.ttf", "Nanum Myeongjo",
                          "60c0077fce069ba90ae97c0a3679f6eb3712e0ca637bdd0c15b72d335ec46db7",
                          "8eb1c1019fe7fe6d0b6e7d7bbbba1d9cbdd969d8c5f26455708f6cfb8a77284c"),
}

# ── 역할: (글꼴 열쇠, em 텍셀, wght). 앞에서부터 그 글자를 가진 글꼴을 쓴다
BODY_LA = ("eb_garamond", 38, 600)
BODY_KR = ("noto_serif_kr", 34, 600)
TITLE_LA = ("cinzel", 39, 700)
TITLE_KR = ("nanum_myeongjo_eb", 36, None)
DIGITS = ("eb_garamond", 44, 600)   # 소울 수 숫자 (HUD, 4 텍셀/GUI)
TITLE_TRACK = 0.5                   # 제목 로마자 자간 (GUI 픽셀): 비문 대문자는 넉넉하게
BODY_SPACE = 3                      # 빈칸 진행 폭 (GUI 픽셀)
TITLE_SPACE = 4
TITLE_MAX_ASC = 8                   # 제목 글꼴 ascent 상한: 보스 막대 줄 (글자 네모 위가 줄 위 - 1 보다 위로 가면 셰이더가 줄을 못 가른다)
ORN_S = 2                           # 장식 그림 (제목 밑 금실): 텍셀 / GUI 픽셀
TEX = "souls:font/"                 # 글자 그림 자리 (textures/font/text_*.png: 덮임 자료라 artlint 는 꼴만 본다)


def cache_dir():
    d = os.environ.get("SOULS_FONT_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "souls-fonts", "ofl")
    os.makedirs(d, exist_ok=True)
    return d


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(key):
    """(글꼴 경로, OFL 글 경로). 캐시에 없으면 받는다. sha256 이 다르면 멈춘다."""
    folder, fname, _, sha_font, sha_ofl = SOURCES[key]
    d = os.path.join(cache_dir(), folder)
    os.makedirs(d, exist_ok=True)
    out = []
    for rel, local, want in ((f"{folder}/{fname}", fname.replace("%5B", "[").replace("%5D", "]"), sha_font),
                             (f"{folder}/OFL.txt", "OFL.txt", sha_ofl)):
        path = os.path.join(d, local)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print("  글꼴 받기:", RAW + rel)
            with urllib.request.urlopen(RAW + rel, timeout=180) as r:
                data = r.read()
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        got = _sha256(path)
        if got != want:
            raise SystemExit(f"글꼴 파일 {path} 의 sha256 이 {got} 이다 ({want} 이어야 한다). google/fonts 가 바뀌었으면 "
                             f"그림을 확인하고 pack/fonts.py 의 SOURCES 를 고친다")
        out.append(path)
    return tuple(out)


def licence_text(key):
    with open(fetch(key)[1], encoding="utf-8") as f:
        return f.read()


# ─────────────────────────── 글자 묶음 ───────────────────────────

def ks_x_1001_hangul():
    out = []
    for b1 in range(0xB0, 0xC9):
        for b2 in range(0xA1, 0xFF):
            try:
                out.append(bytes([b1, b2]).decode("euc-kr"))
            except UnicodeDecodeError:
                pass
    return out


def latin_set():
    s = [chr(c) for c in range(0x21, 0x7F)] + [chr(c) for c in range(0xA1, 0x100) if c != 0xAD]
    s += list("‐‑‒–—―‘’‚“”„†‡•…‰′″‹›™←↑→↓−∞≠≤≥ŒœŠšŸŽž")
    return s


def hangul_set():
    s = ks_x_1001_hangul()
    s += [chr(c) for c in range(0x3131, 0x3164)]       # 호환 자모 (채팅 입력 중)
    s += list("、。〈〉《》「」『』【】〜※")
    return s


# ─────────────────────────── 그리기 ───────────────────────────

class Face:
    """FreeType 글꼴 하나 (가변 글꼴은 wght 로 고정), em = px 텍셀."""

    def __init__(self, key, px, wght=None, hint="light"):
        self.key = key
        self.path = fetch(key)[0]
        self.face = freetype.Face(self.path)
        if wght is not None:
            self.face.set_var_design_coords((wght,))
        self.px = px
        self.hint = hint
        self.face.set_pixel_sizes(0, px)

    def has(self, ch):
        return self.face.get_char_index(ord(ch)) != 0

    def render(self, ch):
        """(알파 0..1 배열, 왼쪽 텍셀, 바탕선 위 줄 수, 진행 폭 텍셀 (소수))."""
        flags = freetype.FT_LOAD_RENDER
        if self.hint == "light":
            flags |= freetype.FT_LOAD_TARGET_LIGHT | freetype.FT_LOAD_FORCE_AUTOHINT
        elif self.hint == "none":
            flags |= freetype.FT_LOAD_NO_HINTING
        self.face.load_char(ch, flags)
        g = self.face.glyph
        bm = g.bitmap
        if bm.rows and bm.width:
            a = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width].astype(np.float32) / 255.0
        else:
            a = np.zeros((0, 0), np.float32)
        return a, g.bitmap_left, g.bitmap_top, g.advance.x / 64.0


class Role:
    """
    한 글꼴 역할 (본문, 제목 …): 글꼴 목록 (앞에서부터 그 글자를 가진 것), 자간 (GUI 픽셀), 빈칸 폭.
    add() 가 글자마다 (덮임, 칸 안 자리) 와 진행 폭 (정수 GUI 픽셀) 을 만든다.
    """

    def __init__(self, name, faces, track=0.0, space=3, max_asc=None):
        self.name = name
        self.faces = faces
        self.track = track
        self.space = space
        self.max_asc = max_asc          # ascent 상한 (보스 막대 줄: 글자 네모 위가 줄 위 - 1 보다 위로 가면 안 된다)
        self.glyphs = {}                # 글자 → dict(a, x0, top, adv, face)

    def face_for(self, ch):
        for f in self.faces:
            if f.has(ch):
                return f
        return None

    def add(self, chars):
        for ch in chars:
            if ch in self.glyphs or ch == " ":
                continue
            f = self.face_for(ch)
            if f is None:
                continue
            a, left, top, adv = f.render(ch)
            adv += self.track * K
            if a.size:
                cols = np.nonzero(a.max(0) > 0)[0]
                rows = np.nonzero(a.max(1) > 0)[0]
                if len(cols) == 0:
                    a = np.zeros((0, 0), np.float32)
                else:
                    a = a[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
                    left += int(cols[0])
                    top -= int(rows[0])
            # 진행 폭 A: 글꼴의 진행 폭을 정수 GUI 픽셀로 반올림하고, 글자를 그 폭 가운데에 놓아 반올림 오차를 양쪽에 나눈다
            A = max(1, int(round(adv / K)))
            x0 = max(MARGIN_L, left + int(round((A * K - adv) / 2.0)))
            self.glyphs[ch] = {"a": a, "x0": x0, "top": top, "adv": A, "face": f.key}

    def metrics(self):
        """칸 크기 (텍셀) 와 ascent (GUI 픽셀): 모든 글자가 그림자 테두리까지 들어가게."""
        up = max((g["top"] for g in self.glyphs.values() if g["a"].size), default=K * 7)
        down = max((g["a"].shape[0] - g["top"] for g in self.glyphs.values() if g["a"].size), default=K)
        asc = int(math.ceil((up + HALO) / K))
        if self.max_asc is not None:
            asc = min(asc, self.max_asc)
        desc = int(math.ceil((down + HALO) / K))
        right = max(max(g["x0"] + g["a"].shape[1] + HALO for g in self.glyphs.values() if g["a"].size),
                    max((g["adv"] - 1) * K for g in self.glyphs.values()))
        cw = int(math.ceil(right / K)) * K
        return {"asc": asc, "desc": desc, "cw": cw, "ch": (asc + desc) * K}


class MappedRole(Role):
    """개인 영역 글자 → 원 글자를 그린다 (창 제목용)."""

    def add_mapped(self, mapping):
        """mapping = {개인 영역 글자: 원 글자}."""
        for pua, src in mapping.items():
            if pua in self.glyphs or src == " ":
                continue
            before = dict(self.glyphs)
            self.add(src)
            if src in self.glyphs and src not in before:
                self.glyphs[pua] = self.glyphs.pop(src)
            elif src in self.glyphs:
                self.glyphs[pua] = dict(self.glyphs[src])


def atlas(role, chars_per_row=64):
    """
    글자 그림 한 장 (RGBA: R=덮임, B=1 표식, 알파 0 (진행 폭 점만 1)) 과 공급자. 글자 차례는 role.glyphs 의 차례.
    돌려주는 값: (Image, provider dict (file 은 비워 둔다), 진행 폭이 바뀐 글자 목록).
    """
    m = role.metrics()
    cw, ch_, asc = m["cw"], m["ch"], m["asc"]
    chars = list(role.glyphs.keys())
    rows = int(math.ceil(len(chars) / chars_per_row))
    W, H = cw * min(len(chars), chars_per_row), ch_ * rows
    A = np.zeros((H, W), np.float32)
    grid, over, sentinels = [], [], []
    for i, chr_ in enumerate(chars):
        g = role.glyphs[chr_]
        cx, cy = (i % chars_per_row) * cw, (i // chars_per_row) * ch_
        if i % chars_per_row == 0:
            grid.append("")
        grid[-1] += chr_
        cell = np.zeros((ch_, cw), np.float32)
        a = g["a"]
        if a.size:
            y0 = asc * K - g["top"]
            if y0 < 0:
                a = a[-y0:]
                y0 = 0
            cell[y0:y0 + a.shape[0], g["x0"]:g["x0"] + a.shape[1]] = a
        want = g["adv"]
        sent = (want - 1) * K - 1
        w_eff = sent + 1 if sent >= 0 else 0
        final = int(0.5 + w_eff / K) + 1
        if final != want:
            over.append((chr_, want, final))
        if sent >= 0:
            sentinels.append((cx + sent, cy + ch_ - 1))
        g["final_adv"] = final
        A[cy:cy + ch_, cx:cx + cw] = cell
    if rows > 1:
        grid = [r + "\u0000" * (chars_per_row - len(r)) for r in grid]
    img = np.zeros((H, W, 4), np.uint8)
    q = 255.0 / (LEVELS - 1)            # 덮임 32 단 (5 비트): 눈으로 갈리지 않고 그림이 절반 가까이 작아진다
    img[..., 0] = np.clip(np.rint(np.rint(A * 255 / q) * q), 0, 255).astype(np.uint8)
    img[..., 2] = MARK_B
    for x, y in sentinels:
        img[y, x, 3] = 1
    provider = {"type": "bitmap", "file": None, "height": ch_ // K, "ascent": asc, "chars": grid}
    return Image.fromarray(img, "RGBA"), provider, over


def write_atlas(out, role, fname):
    img, prov, over = atlas(role)
    path = os.path.join(out, "assets", "souls", "textures", "font", fname + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    prov["file"] = TEX + fname + ".png"
    if over:
        print(f"  {fname}: 진행 폭이 바뀐 글자 {len(over)}개 {over[:6]}")
    return prov, os.path.getsize(path)


def digit_role():
    """HUD 소울 수 숫자 (가라몽 라이닝 숫자, 4 텍셀/GUI). hud.py 가 그림 글자로 굽는다."""
    r = Role("digits", [Face(*DIGITS)])
    r.add("0123456789")
    return r


# ─────────────────────────── 제목 밑 금실 (장식 그림 글자) ───────────────────────────

GOLD = ["rust1", "bronze3", "parch2", "glim0"]


def title_divider():
    """창 제목 밑 금실 (GUI DIVIDER_W × 5): 가운데 단조 마름모, 양쪽으로 금실 (위 줄 길고, 아래 짧은 청동), 끝은 알파 계단."""
    W, H = typeset.DIVIDER_W * ORN_S, 5 * ORN_S
    img = Img(W, H)
    cx = W / 2.0
    for x in range(W):
        d = abs(x + 0.5 - cx) / cx
        if abs(x + 0.5 - cx) > 8:
            img.put(x, 4, "parch2" if d < 0.3 else "parch1", 0.95 * max(0.0, 1 - d ** 1.6))
            img.put(x, 5, "ink0", 0.5 * max(0.0, 1 - d ** 1.6))
        if 8 < abs(x + 0.5 - cx) < 60:
            img.put(x, 7, "bronze2", 0.8 * max(0.0, 1 - (abs(x + 0.5 - cx) - 8) / 52.0))
    m = Mask(W, H).poly([(cx - 7, 4.5), (cx, 0.0), (cx + 7, 4.5), (cx, 9.5)])
    hole = Mask(W, H).poly([(cx - 3, 4.5), (cx, 2.4), (cx + 3, 4.5), (cx, 6.6)])
    img.over(uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), GOLD))
    img.fill(Mask(W, H).disc(cx, 4.5, 1.0).cov(), "glim0", 1.0)
    return img


# ─────────────────────────── 엮기 ───────────────────────────

class FontSet:
    """build() 의 결과: 기본 글꼴·제목 글꼴·유니코드 글꼴에 넣을 공급자 (hud.py 의 사망 화면 공급자 앞에 둔다)."""

    def __init__(self, default, title, uniform, size):
        self.default, self.title, self.uniform, self.size = default, title, uniform, size


def title_chars(ko_lines):
    """제목 글꼴 (souls:title) 로 그려질 한국어 음절: YAML 의 꼴 태그에 <font:souls:title> 이 있는 글 (무기·보스·화톳불 이름)."""
    tag = "<font:" + typeset.TITLE_FONT + ">"
    out = []
    for k in sorted(ko_lines):
        v = ko_lines[k]
        if isinstance(v, str) and tag in v:
            for ch in v:
                if 0xAC00 <= ord(ch) <= 0xD7A3 and ch not in out:
                    out.append(ch)
    return out


def write_licences(out):
    lic = os.path.join(out, "assets", "souls", "font", "licenses")
    os.makedirs(lic, exist_ok=True)
    notice = ["Square Soul resource pack - fonts", "",
              "The glyph images assets/souls/textures/font/text_*.png were rendered (FreeType) from these fonts,",
              "licensed under the SIL Open Font License, Version 1.1 (full text in assets/souls/font/licenses/).",
              "No font software is included in this pack; only pre-rendered glyph bitmaps (a Modified Version",
              "under the OFL; none of the fonts declares a Reserved Font Name).", ""]
    for key in sorted({BODY_LA[0], BODY_KR[0], TITLE_LA[0], TITLE_KR[0]}):
        text = licence_text(key)
        name = SOURCES[key][2]
        with open(os.path.join(lic, "ofl-" + name.lower().replace(" ", "-") + ".txt"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(text)
        notice.append(f"  {name}: {text.splitlines()[0].strip()}")
    with open(os.path.join(out, "FONTS-OFL.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(notice) + "\n")


def build(out, ko_lines):
    """
    글자 그림 (textures/font/text_*.png), 제목 밑 금실, 사용 허락 글을 쓰고 FontSet 을 돌려준다. ko_lines = 한국어 YAML 의
    {점 열쇠: 글} (langpack.lines): 제목 글꼴과 창 제목의 한글 음절을 여기서 고른다.
    """
    import time
    t = time.time()
    body_la = Role("body_la", [Face(*BODY_LA)], space=BODY_SPACE)
    body_la.add(latin_set())
    body_kr = Role("body_kr", [Face(*BODY_KR)], space=BODY_SPACE)
    body_kr.add([ch for ch in hangul_set() if ch not in body_la.glyphs])
    title_la = Role("title_la", [Face(*TITLE_LA)], track=TITLE_TRACK, space=TITLE_SPACE, max_asc=TITLE_MAX_ASC)
    title_la.add([chr(c) for c in range(0x21, 0x7F)] + list("·’‘“”—–…"))
    title_kr = Role("title_kr", [Face(*TITLE_KR)], space=TITLE_SPACE, max_asc=TITLE_MAX_ASC)
    title_kr.add([ch for ch in title_chars(ko_lines) if ch not in title_la.glyphs])
    mapping = typeset.title_map(typeset.title_syllables(ko_lines))
    la_map = {v: k for k, v in mapping.items() if 0x20 <= ord(k) < 0x7F}
    kr_map = {v: k for k, v in mapping.items() if ord(k) >= 0xAC00}
    pua_la = MappedRole("title_pua_la", [Face(*TITLE_LA)], track=TITLE_TRACK, space=TITLE_SPACE)
    pua_la.add_mapped(la_map)
    pua_kr = MappedRole("title_pua_kr", [Face(*TITLE_KR)], space=TITLE_SPACE)
    pua_kr.add_mapped(kr_map)
    provs, size = {}, 0
    for role in (body_la, body_kr, title_la, title_kr, pua_la, pua_kr):
        provs[role.name], n = write_atlas(out, role, "text_" + role.name)
        size += n
    print(f"  글자 그림: " + ", ".join(f"{r.name} {len(r.glyphs)}자" for r in (body_la, body_kr, title_la, title_kr, pua_la, pua_kr))
          + f", {size // 1024} KB ({time.time() - t:.1f}초)")

    div = title_divider().image()
    uidraw.save(div, os.path.join(out, "assets", "souls", "textures", "font", "title_rule.png"))
    div_prov = {"type": "bitmap", "file": TEX + "title_rule.png", "height": div.height // ORN_S, "ascent": -4,
                "chars": [typeset.DIVIDER]}
    spaces = {"type": "space", "advances": typeset.space_advances()}
    title_space = chr(typeset.TITLE_LA_PUA)          # 제목 글자의 빈칸 (ASCII 0x20)
    default = [{"type": "space", "advances": {" ": BODY_SPACE, " ": BODY_SPACE, "　": 8, title_space: TITLE_SPACE}},
               provs["body_la"], provs["body_kr"], provs["title_pua_la"], provs["title_pua_kr"], div_prov, spaces]
    title = [{"type": "space", "advances": {" ": TITLE_SPACE, " ": TITLE_SPACE}}, provs["title_la"], provs["title_kr"],
             div_prov, spaces, {"type": "reference", "id": typeset.DEFAULT_FONT}]
    # 유니코드 글꼴 강제 설정을 켠 사람: 본문은 바닐라 유니코드 글꼴이지만 창 제목 글자·금실·빈칸은 그려져야 한다
    uniform = [{"type": "space", "advances": {title_space: TITLE_SPACE}}, provs["title_pua_la"], provs["title_pua_kr"],
               div_prov, spaces]
    write_licences(out)
    return FontSet(default, title, uniform, size)


def check(out):
    """글꼴 정의의 bitmap 공급자: ascent <= height (클라이언트가 글꼴 전체를 버린다), 그림이 있고 칸이 나누어 떨어지고 256 이하."""
    bad = []
    for ns in ("minecraft", "souls"):
        d = os.path.join(out, "assets", ns, "font")
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if not n.endswith(".json"):
                continue
            with open(os.path.join(d, n), encoding="utf-8") as f:
                provs = json.load(f).get("providers", [])
            for p in provs:
                if p.get("type") != "bitmap":
                    continue
                where = f"{ns}:font/{n} {p['file']}"
                if p["ascent"] > p["height"]:
                    bad.append(f"{where}: ascent {p['ascent']} > height {p['height']}")
                fns, fp = p["file"].split(":", 1)
                img = Image.open(os.path.join(out, "assets", fns, "textures", fp))
                rows = p["chars"]
                if img.height % len(rows) or any(len(r) != len(rows[0]) for r in rows) or img.width % len(rows[0]):
                    bad.append(f"{where}: 칸이 나누어 떨어지지 않는다")
                    continue
                cw, ch = img.width // len(rows[0]), img.height // len(rows)
                if cw > 256 or ch > 256:
                    bad.append(f"{where}: 칸 {cw}×{ch} 텍셀 (글꼴 아틀라스 256×256 을 넘으면 빈 네모)")
    return bad
