#!/usr/bin/env python3
"""
글자 시험 그림 (texttest.sh) 을 잰다: 같은 글자를 되풀이한 낱말 (HHHH, nnnn, 기기기기, 다다다다, 8888) 에서

  period    글자 사이 (화면 픽셀). 정수 GUI 픽셀 × 배율이면 모든 글자가 같은 자리 맞춤이다
  diff      첫 글자와 나머지 글자의 화면 픽셀 차 (밝기 0..255, 가장 잘 맞는 ±1 픽셀 밀기 뒤 평균·최대).
            0 이면 같은 글자가 어느 자리에서나 똑같이 그려진다 (굵기·바탕선이 흔들리지 않는다)
  ink cv    글자마다 먹 (밝기 합) 의 변동 계수 (%): 굵기가 글자마다 다른 정도
  base      글자마다 가장 아래 밝은 줄의 흩어짐 (화면 픽셀, 최대 - 최소): 바탕선이 흔들리는 정도

  python3 texttest.py <그림> <GUI 배율> [--crop out.png]
"""
import sys

import numpy as np
from PIL import Image

INK = 110          # 글자 픽셀로 보는 밝기 (그림자·바탕은 이보다 어둡다)


def lum(img):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def bands(L, x0, x1):
    rows = (L[:, x0:x1] > INK).any(1)
    out, y = [], 0
    while y < len(rows):
        if rows[y]:
            s = y
            while y < len(rows) and rows[y]:
                y += 1
            out.append((s, y))
        y += 1
    return out


def words(L, y0, y1, n_words, x_min):
    """줄 띠에서 낱말 n_words 개: 빈 열이 가장 넓은 n_words - 1 곳 (빈칸) 으로 나눈다."""
    cols = (L[y0:y1] > INK).any(0)
    xs = np.nonzero(cols)[0]
    xs = xs[xs >= x_min]
    gaps = []
    for a, b in zip(xs, xs[1:]):
        if b - a > 1:
            gaps.append((b - a, a, b))
    cut = sorted(sorted(gaps, reverse=True)[:n_words - 1], key=lambda g: g[1])
    out, s = [], xs[0]
    for _, a, b in cut:
        out.append((s, a + 1))
        s = b
    out.append((s, xs[-1] + 1))
    return out


def analyse_word(W, n):
    """W: 낱말 (줄 띠 × 열) 밝기. n 글자. period 를 찾고 글자마다 견준다."""
    h, w = W.shape
    V = np.clip(W - 60, 0, None)

    def windows(P, cell):
        return [int(round(i * P)) for i in range(n)]

    best = None
    for P10 in range(int(w / n * 0.7 * 10), int(w / (n - 1) * 10) + 1):
        P = P10 / 10.0
        starts = windows(P, 0)
        cell = min(int(P), w - starts[-1])
        if cell < 2:
            continue
        ref = V[:, :cell]
        sc = np.mean([np.abs(V[:, a:a + cell] - ref).mean() for a in starts[1:]])
        if best is None or sc < best[0]:
            best = (sc, P, cell)
    _, P, cell = best
    ref = V[:, :cell]
    diffs, inks, bases = [], [], []
    for i, o in enumerate(windows(P, cell)):
        cands = []
        for sh in (-1, 0, 1):
            a = o + sh
            if a < 0 or a + cell > w:
                continue
            seg = V[:, a:a + cell]
            cands.append((float(np.abs(seg - ref).mean()), float(np.abs(seg - ref).max()), a))
        m, mx, a = min(cands)
        seg = W[:, a:a + cell]
        if i:
            diffs.append((m, mx))
        inks.append(np.clip(seg - 60, 0, None).sum())
        ink_rows = np.nonzero((seg > INK).any(1))[0]
        bases.append(int(ink_rows.max()) if len(ink_rows) else -1)
    inks = np.array(inks)
    return {"period": P, "diff_mean": float(np.mean([d[0] for d in diffs])), "diff_max": float(np.max([d[1] for d in diffs])),
            "ink_cv": float(inks.std() / max(inks.mean(), 1e-6) * 100), "base_spread": int(max(bases) - min(bases))}


def main(argv):
    path, G = argv[0], int(argv[1])
    img = Image.open(path)
    L = lum(img)
    H, Wd = L.shape
    x1 = min(Wd, 330 * G)
    # 채팅 글 덩이 (줄들이 붙어 한 띠가 된다): 화면 아래 단축 슬롯·입력 줄 위에서 가장 큰 띠. 그 맨 아래 9 GUI 픽셀이 되풀이 줄
    bs = [b for b in bands(L, 0, x1) if b[1] - b[0] >= 3 * G and b[1] < H - 16 * G and b[0] > H * 0.35]
    blk = bs[-1]                      # 가장 아래 띠 (줄이 붙으면 덩이 전체) 의 맨 아래 9 GUI 픽셀
    y1 = blk[1]
    y0 = max(blk[0] - 1, y1 - 8 * G - 1)
    bs = [(blk[0], y0), (y0, y1)]
    ws = words(L, y0, y1, 5, x_min=4 * G)   # 채팅 왼쪽 표시 막대 (x < 4 GUI) 는 뺀다
    names = [("H", 10), ("n", 10), ("기", 6), ("다", 6), ("8", 10)]
    res = {}
    for (nm, n), (a, b) in zip(names, ws):
        r = analyse_word(L[y0:y1, a:b], n)
        res[nm] = r
        print(f"  {nm}×{n}: period {r['period']:.1f}px ({r['period'] / G:.2f} GUI), diff mean {r['diff_mean']:.2f} max {r['diff_max']:.0f}, "
              f"ink cv {r['ink_cv']:.1f}%, baseline spread {r['base_spread']}px")
    if "--crop" in argv:
        out = argv[argv.index("--crop") + 1]
        top = bs[0][0] - 3 * G
        img.crop((0, max(0, top), x1, min(H, y1 + 3 * G))).save(out)
    return res


if __name__ == "__main__":
    main(sys.argv[1:])
