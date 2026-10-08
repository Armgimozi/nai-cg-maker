#!/usr/bin/env python3
"""
글 시험 그림 (texttest.sh) 에서 삐뚤빼뚤을 잰다.

  python3 measure.py <그림.png> <GUI 배율> <팩 폴더> [--json]

채팅 바탕을 검게 (textBackgroundOpacity 1.0) 띄우고 빈 줄을 사이에 둔 시험 줄 다섯 (한글 본문, 한글 제목, 로마 대문자 제목,
숫자, 영어 본문) 을, 같은 글꼴의 윤곽을 그 배율로 정확히 (힌팅 없이 8배로 그려 면적 평균) 그린 기준 그림과 글자마다 견준다.
글자 자리는 마인크래프트와 같은 셈 (공급자 차례, oversample 배 픽셀 진행 폭을 정수로).
  바탕선   글자 칸 안 잉크의 무게 중심 높이 (화면 그림 - 기준 그림). 모든 글자가 같은 바탕선에 앉고 꼴이 그대로면 줄 안에서 같은
           값이다. 줄의 가운데 값을 뺀 뒤 최대 어긋남·표준 편차를 화면 픽셀로 낸다 (글자가 위아래로 들쭉날쭉한 정도).
  획 굵기  글자 칸 안 잉크 (덮인 몫의 합) / 기준 그림의 잉크. 같은 굵기로 그려지면 글자마다 같다: 변동 계수 (표준 편차 / 평균).
이웃 글자 상자와 겹치는 열은 두 그림에서 똑같이 뺀다. 채팅 줄 아래로 내려가는 획 (g, p, 쉼표) 은 채팅이 잘라 빼고 잰다.
"""
import json
import os
import sys

import freetype
import numpy as np
from PIL import Image

LINES = [
    ("레딘 경비대가 차던 곧은 칼. 성벽 위의 병사들은 모두 안쪽을 보고 섰다.", "body"),
    ("레딘 경비대 직검 · 수문장 흐롤프 · 탑옥 아래", "title"),
    ("REDIN GUARD SWORD · GATEWARDEN HROLF", "title"),
    ("0123456789  공격력 62  무게 3.0  소울 87650", "body"),
    ("The straight sword the Redin guard wore, 1234.", "body"),
]
FG = (214, 203, 176)   # bone2
SUPER = 8


class Fonts:
    def __init__(self, pack, which):
        from fontTools.ttLib import TTFont
        if which == "body":
            fd = json.load(open(os.path.join(pack, "assets", "minecraft", "font", "default.json")))
        else:
            fd = json.load(open(os.path.join(pack, "assets", "souls", "font", "title.json")))
        self.space = None
        self.fonts = []
        for p in fd["providers"]:
            if p.get("type") == "space" and " " in p.get("advances", {}) and self.space is None:
                self.space = p["advances"][" "]
            if p.get("type") == "ttf":
                path = os.path.join(pack, "assets", "souls", "font", p["file"].split(":", 1)[1])
                self.fonts.append((TTFont(path), freetype.Face(path), p["size"], p["oversample"],
                                   p.get("shift", [0, 0])[1]))
        if self.space is None:
            self.space = 4.0

    def find(self, ch):
        for f, face, size, ov, shift in self.fonts:
            g = f.getBestCmap().get(ord(ch))
            if g is not None:
                return f, face, size, ov, shift, g
        return None

    def advance(self, ch):
        if ch == " ":
            return self.space
        r = self.find(ch)
        if r is None:
            return 6.0
        f, face, size, ov, shift, g = r
        ppem = round(size * ov)
        return round(f["hmtx"].metrics[g][0] * ppem / f["head"].unitsPerEm) / ov

    def raster(self, ch, s):
        """(덮인 몫 그림 (화면 픽셀), 왼쪽, 위 (바탕선 기준, 아래가 +)) 또는 None. 힌팅 없이 SUPER 배로 그려 면적 평균."""
        r = self.find(ch)
        if r is None or ch == " ":
            return None
        f, face, size, ov, shift, g = r
        face.set_pixel_sizes(0, int(round(size * s * SUPER)))
        face.load_char(ch, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_BITMAP)
        bm = face.glyph.bitmap
        if not bm.width or not bm.rows:
            return None
        a = np.array(bm.buffer, np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width].astype(np.float32) / 255
        left = face.glyph.bitmap_left
        top = -face.glyph.bitmap_top + int(round(shift * s * SUPER))
        ox, oy = left % SUPER, top % SUPER
        H = (oy + a.shape[0] + SUPER - 1) // SUPER * SUPER
        W = (ox + a.shape[1] + SUPER - 1) // SUPER * SUPER
        big = np.zeros((H, W), np.float32)
        big[oy:oy + a.shape[0], ox:ox + a.shape[1]] = a
        small = big.reshape(H // SUPER, SUPER, W // SUPER, SUPER).mean(axis=(1, 3))
        return small, (left - ox) // SUPER, (top - oy) // SUPER


def coverage(img):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    fg = np.dot(FG, [0.299, 0.587, 0.114])
    return np.clip(lum / fg, 0, 1.2)


def chat_region(img, s):
    """채팅 바탕 (검정) 의 위·아래 줄: 글이 닿지 않는 채팅 오른쪽 몫 (GUI x 290..315) 이 검은 줄."""
    a = np.asarray(img.convert("RGB"))
    rows = np.where((a[:, 290 * s:315 * s].max(axis=2) < 6).mean(axis=1) > 0.9)[0]
    best, start = (0, -1), rows[0]
    for i in range(1, len(rows) + 1):
        if i == len(rows) or rows[i] != rows[i - 1] + 1:
            if rows[i - 1] - start > best[1] - best[0]:
                best = (start, rows[i - 1])
            if i < len(rows):
                start = rows[i]
    return best


def measure(path, s, pack, lines=LINES):
    img = Image.open(path)
    top, bot = chat_region(img, s)
    cov = coverage(img)
    lh = 9 * s
    n = (bot - top + 1) // lh
    bands = [top + (n - 1 - 2 * k) * lh for k in range(len(lines))][::-1]
    out = []
    for li, ((text, which), ytop) in enumerate(zip(lines, bands)):
        if ytop < top:
            continue
        fonts = Fonts(pack, which)
        y0 = ytop - lh // 2
        band = cov[y0:y0 + 2 * lh, :].copy()
        band[:max(0, top - y0)] = 0
        band[max(0, bot + 1 - y0):] = 0
        line_bottom = ytop + lh                           # 이 줄의 채팅 칸 아래 (화면 y)
        pen = 0.0
        glyphs = []
        for ch in text:
            r = fonts.raster(ch, s)
            if r is not None:
                glyphs.append((ch, pen, r))
            pen += fonts.advance(ch)
        ref = np.zeros((4 * lh, int(pen * s) + 8 * lh), np.float32)
        base = 2 * lh
        boxes = []
        for ch, px, (a, left, topo) in glyphs:
            x = int(round(px * s)) + left + 2 * lh
            y = base + topo
            ref[y:y + a.shape[0], x:x + a.shape[1]] = np.maximum(ref[y:y + a.shape[0], x:x + a.shape[1]], a)
            boxes.append((ch, x, x + a.shape[1], y, y + a.shape[0]))
        mcols = np.where(band.max(axis=0) > 0.3)[0]
        mcols = mcols[mcols >= 3 * s]
        rcols = np.where(ref.max(axis=0) > 0.3)[0]
        dx = int(mcols[0] - rcols[0])
        # 바탕선의 대략 자리 (내림 획 거르기용): 화면 띠의 잉크 무게 중심 - 기준의 잉크 무게 중심
        recs = []
        for i, (ch, x0, x1, ry0, ry1) in enumerate(boxes):
            lo = x0 if i == 0 else max(x0, boxes[i - 1][2])
            hi = x1 if i == len(boxes) - 1 else min(x1, boxes[i + 1][1])
            if hi - lo < 2 or lo + dx < 0:
                continue
            rsub = ref[:, lo:hi]
            msub = np.clip(band[:, lo + dx:hi + dx], 0, 1)
            rink = float(rsub.sum())
            mink = float(msub.sum())
            if rink < 1.0 or mink < 1.0:
                continue
            rcy = float((rsub * np.arange(rsub.shape[0])[:, None]).sum() / rink) - base
            mcy = float((msub * np.arange(msub.shape[0])[:, None]).sum() / mink)
            recs.append({"ch": ch, "dy": mcy - rcy, "ink": mink / rink, "below": ry1 - base})
        if len(recs) < 3:
            continue
        # 채팅 칸 아래로 내려가는 획 (잘린다) 은 뺀다: 바탕선 = 띠 위 + 무게 중심 차의 가운데 값
        base_in_band = float(np.median([r["dy"] for r in recs]))
        limit = line_bottom - y0 - base_in_band
        recs = [r for r in recs if r["below"] <= limit]
        d = np.array([r["dy"] for r in recs])
        d -= np.median(d)
        ink = np.array([r["ink"] for r in recs])
        out.append({"line": li, "kind": which, "glyphs": len(recs),
                    "baseline_max_dev_px": float(np.abs(d).max()), "baseline_range_px": float(d.max() - d.min()),
                    "baseline_sd_px": float(d.std()), "ink_cv": float(ink.std() / ink.mean()),
                    "worst": sorted(((round(float(v), 2), r["ch"]) for v, r in zip(d, recs)), key=lambda t: -abs(t[0]))[:4]})
    return out


def summary(res):
    if not res:
        return {}
    return {"baseline_max_dev_px": max(r["baseline_max_dev_px"] for r in res),
            "baseline_sd_px": float(np.mean([r["baseline_sd_px"] for r in res])),
            "ink_cv_max": max(r["ink_cv"] for r in res), "ink_cv_mean": float(np.mean([r["ink_cv"] for r in res]))}


def main(argv):
    path, s, pack = argv[0], int(argv[1]), argv[2]
    res = measure(path, s, pack)
    for r in res:
        print(f"GUI {s} 줄 {r['line']} ({r['kind']:5s}) 글자 {r['glyphs']:2d}: 바탕선 어긋남 최대 {r['baseline_max_dev_px']:.2f}px "
              f"(표준편차 {r['baseline_sd_px']:.2f}), 획 굵기 변동 {r['ink_cv'] * 100:4.1f}%  {r['worst']}")
    sm = summary(res)
    if sm:
        print(f"GUI {s} 요약: 바탕선 어긋남 최대 {sm['baseline_max_dev_px']:.2f}px, 평균 표준편차 {sm['baseline_sd_px']:.2f}px, "
              f"획 굵기 변동 평균 {sm['ink_cv_mean'] * 100:.1f}% (최대 {sm['ink_cv_max'] * 100:.1f}%)")
    if "--json" in argv:
        print(json.dumps({"lines": res, "summary": sm}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
