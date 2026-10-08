"""
mood2_gothic 의 글꼴: TTF 를 팩에 넣지 않고 우리가 FreeType 으로 미리 그려 bitmap 글꼴 공급자로 넣는다.

왜 (2026-10-08 사용자: "글자가 좀 삐뚤빼뚤하네")
  1차 시안은 TTF 공급자였다. 클라이언트가 글자마다 size × oversample 픽셀로 그려 1/oversample GUI 픽셀 단위의 제멋대로인
  자리 (진행 폭이 소수) 에 놓고 NEAREST 로 읽으니, GUI 배율 3 (텍셀 하나 = 화면 0.75 픽셀) 에서 줄이 하나씩 빠지거나 두 번
  찍혀 같은 글자도 자리마다 굵기가 달랐다.

어떻게
  * 모든 글자를 GUI 한 픽셀에 K=4 텍셀로 그린다 (FreeType 자동 힌팅 light: 바탕선·x 높이·대문자 높이를 텍셀 격자에 맞춘다).
  * 칸 (cell) 은 K 의 배수, 바탕선은 칸 위에서 ASC×K 텍셀 (GUI 픽셀 경계), 공급자 height = 칸 높이 / K 이라 글자 네모가
    늘 GUI 픽셀 격자에 놓인다. 진행 폭은 정수 GUI 픽셀 (글자를 그 폭 가운데에 놓아 반올림 오차를 양쪽에 나눈다).
    → 같은 글자는 어느 자리에서나 텍셀 격자가 화면 픽셀에 똑같이 겹친다 (배율 2·3·4 모두). 바탕선은 하나다.
  * 글꼴 셰이더 (shaders.py rendertype_text.fsh) 가 이 텍셀을 화면 픽셀이 덮는 넓이만큼 섞어 (area filter) 읽는다:
    배율 4 는 1:1, 2 는 2×2 평균, 3 은 4/3 텍셀 상자. NEAREST 처럼 줄이 빠지거나 겹치지 않는다.
  * 텍셀: R = 글자 덮임 (32 단), B = 1 과 알파 0 이 "우리 글자" 표식 (셰이더가 알아본다). 바닐라 그림자 사본은 셰이더가
    반 픽셀 오른쪽 아래에 덮임을 흐려 (상자 거르개를 2.5 텍셀 넓혀) 먹빛 테두리로 그린다.
  * 진행 폭: 클라이언트는 bitmap 글자의 폭을 "알파가 0 이 아닌 가장 오른쪽 열 + 1" 로 재 (int)(0.5 + 폭 × 배율) + 1 을
    진행 폭으로 쓴다. 덮임을 알파에 두면 글자 끝 뒤에 늘 0.75 픽셀 넘는 틈이 생겨 (바닐라 픽셀 글꼴의 "+1") 가라몽
    소문자가 글자마다 1 픽셀씩 벌어졌다. 그래서 글자는 알파 0 으로 두고 (A-1)×K - 1 열에 알파 1 점 하나만 찍어 진행
    폭을 정확히 A (글꼴의 진행 폭을 반올림한 정수 GUI 픽셀) 로 정한다. 글자는 칸 안에서 다음 글자 자리로 넘어가도 된다.

글꼴 (모두 SIL OFL 1.1, 받는 곳 google/fonts. 팩에는 TTF 가 아니라 그린 그림만 들어간다. 사용 허락 글은 팩의
assets/souls/font/gothic/licenses/ 와 FONTS-OFL.txt)
  본문 한글   Noto Serif KR (wght 600)          KS X 1001 2,350 자 + 호환 자모 + 문장 부호
  본문 로마자 EB Garamond (wght 600)            ASCII, 라틴-1, 문장 부호
  제목 로마자 Cinzel (wght 700)                 로마 비문 대문자 (창 제목·아이템 이름·보스 이름)
  제목 한글   Nanum Myeongjo ExtraBold          옛 명조의 무거운 붓맛 (제목에 나오는 음절만)
"""
import math
import os
import urllib.request

import freetype
import numpy as np
from PIL import Image

K = 4                       # 텍셀 / GUI 픽셀
MARGIN_L = 1                # 글자 왼쪽 여백 (텍셀): 셰이더의 상자 거르개가 칸 밖 (아틀라스 이웃) 을 읽지 않게
HALO = 3                    # 그림자 (셰이더가 덮임을 흐려 그린다) 가 글자 밖으로 번지는 텍셀: 칸에 이만큼 여백
LEVELS = 32                 # 덮임 단 수
RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
SOURCES = {
    # 열쇠: (저장소 폴더, 파일, 원 이름)
    "noto_serif_kr": ("notoserifkr", "NotoSerifKR%5Bwght%5D.ttf", "Noto Serif KR"),
    "eb_garamond": ("ebgaramond", "EBGaramond%5Bwght%5D.ttf", "EB Garamond"),
    "cinzel": ("cinzel", "Cinzel%5Bwght%5D.ttf", "Cinzel"),
    "nanum_myeongjo_eb": ("nanummyeongjo", "NanumMyeongjo-ExtraBold.ttf", "Nanum Myeongjo"),
}
MARK_B = 1                  # B = 1, 알파 0 (진행 폭 점만 1): 셰이더가 우리 글자 텍셀로 알아본다


def cache_dir():
    d = os.environ.get("SOULS_FONT_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "souls-fonts", "mood2_gothic")
    os.makedirs(d, exist_ok=True)
    return d


def fetch(key):
    """(글꼴 경로, OFL 글 경로). 캐시에 없으면 받는다."""
    folder, fname, _ = SOURCES[key]
    d = os.path.join(cache_dir(), folder)
    os.makedirs(d, exist_ok=True)
    out = []
    for rel, local in ((f"{folder}/{fname}", fname.replace("%5B", "[").replace("%5D", "]")), (f"{folder}/OFL.txt", "OFL.txt")):
        path = os.path.join(d, local)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print("  글꼴 받기:", RAW + rel)
            with urllib.request.urlopen(RAW + rel, timeout=180) as r:
                data = r.read()
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
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
    한 글꼴 역할 (본문, 제목 …): 글꼴 목록 (앞에서부터 그 글자를 가진 것), 자간 (GUI 픽셀), 빈칸 폭, 굵게 (gamma).
    rasterise() 가 글자마다 (알파, 그림자, 칸 안 자리) 와 진행 폭 (정수 GUI 픽셀) 을 만든다.
    """

    def __init__(self, name, faces, track=0.0, space=3, gain=1.0, shift=None):
        self.name = name
        self.faces = faces
        self.track = track
        self.space = space
        self.gain = gain
        self.shift = shift or {}        # 글꼴 열쇠 → 바탕선에서 내리는 텍셀 (한글과 로마자 바탕선 맞춤)
        self.glyphs = {}                # 글자 → dict(a, x0, y0 (바탕선 기준 위쪽 줄 = -top), adv)

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
            if self.gain != 1.0 and a.size:
                a = np.clip(a * self.gain, 0, 1)
            adv += self.track * K
            if a.size:
                # 알파가 0 인 바깥 열·줄은 버린다
                cols = np.nonzero(a.max(0) > 0)[0]
                rows = np.nonzero(a.max(1) > 0)[0]
                if len(cols) == 0:
                    a = np.zeros((0, 0), np.float32)
                else:
                    a = a[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
                    left += int(cols[0])
                    top -= int(rows[0])
            # 진행 폭 A: 글꼴의 진행 폭을 정수 GUI 픽셀로 반올림하고, 글자를 그 폭 가운데에 놓아 반올림 오차를 양쪽에 나눈다.
            # 글자 덮임은 알파가 아니라 R 에 있으므로 (아래 atlas) 글자가 다음 칸으로 넘어가도 진행 폭은 A 그대로다
            A = max(1, int(round(adv / K)))
            x0 = max(MARGIN_L, left + int(round((A * K - adv) / 2.0)))
            top -= self.shift.get(f.key, 0)
            self.glyphs[ch] = {"a": a, "x0": x0, "top": top, "adv": A, "face": f.key}

    def metrics(self):
        """칸 크기 (텍셀) 와 ascent (GUI 픽셀): 모든 글자가 그림자 테두리까지 들어가게."""
        up = max((g["top"] for g in self.glyphs.values() if g["a"].size), default=K * 7)
        down = max((g["a"].shape[0] - g["top"] for g in self.glyphs.values() if g["a"].size), default=K)
        asc = int(math.ceil((up + HALO) / K))
        desc = int(math.ceil((down + HALO) / K))
        right = max(max(g["x0"] + g["a"].shape[1] + HALO for g in self.glyphs.values() if g["a"].size),
                    max((g["adv"] - 1) * K for g in self.glyphs.values()))
        cw = int(math.ceil(right / K)) * K
        return {"asc": asc, "desc": desc, "cw": cw, "ch": (asc + desc) * K}

    def advance(self, ch):
        if ch == " ":
            return self.space
        g = self.glyphs.get(ch)
        return None if g is None else g["final_adv"]


def atlas(role, chars_per_row=64):
    """
    글자 그림 한 장 (RGBA: R=덮임, B=1 표식, 알파 0 (진행 폭 점만 1)) 과 공급자 값. 글자 차례는 role.glyphs 의 차례.
    돌려주는 값: (Image, provider dict (file 은 비워 둔다), 진행 폭 표 {글자: 정수 GUI 픽셀}, 넘친 글자 목록).
    """
    m = role.metrics()
    cw, ch_, asc = m["cw"], m["ch"], m["asc"]
    chars = list(role.glyphs.keys())
    rows = int(math.ceil(len(chars) / chars_per_row))
    W, H = cw * min(len(chars), chars_per_row), ch_ * rows
    A = np.zeros((H, W), np.float32)
    grid = []
    over = []
    sentinels = []
    advs = {}
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
            cell[y0:y0 + a.shape[0], g["x0"]:g["x0"] + a.shape[1]] = a
        # 진행 폭: 클라이언트는 알파가 0 이 아닌 가장 오른쪽 열로 잰다. 글자는 알파 0 (덮임은 R) 이라 (A-1)K - 1 열의 알파 1
        # 점 하나가 진행 폭을 A 로 정한다
        want = g["adv"]
        sent = (want - 1) * K - 1
        w_eff = sent + 1 if sent >= 0 else 0
        final = int(0.5 + w_eff / K) + 1
        if final != want:
            over.append((chr_, want, final))
        if sent >= 0:
            sentinels.append((cx + sent, cy + ch_ - 1))
        g["final_adv"] = final
        advs[chr_] = final
        A[cy:cy + ch_, cx:cx + cw] = cell
    for row_i in range(len(grid)):
        grid[row_i] = grid[row_i] + "\u0000" * (chars_per_row - len(grid[row_i])) if rows > 1 else grid[row_i]
    img = np.zeros((H, W, 4), np.uint8)
    # 덮임 32 단 (5 비트): 눈으로 갈리지 않고 그림이 절반 가까이 작아진다
    q = 255.0 / (LEVELS - 1)
    img[..., 0] = np.clip(np.rint(np.rint(A * 255 / q) * q), 0, 255).astype(np.uint8)
    img[..., 2] = MARK_B
    for x, y in sentinels:
        img[y, x, 3] = 1
    provider = {"type": "bitmap", "file": None, "height": ch_ // K, "ascent": asc, "chars": grid}
    return Image.fromarray(img, "RGBA"), provider, advs, over


def space_provider(chars_adv):
    return {"type": "space", "advances": dict(chars_adv)}
