"""
mood2_gothic 글자 미리보기: 클라이언트와 같은 셈으로 글 한 줄을 짜고 (정수 진행 폭, 칸 위 = 줄 위 + 7 - ascent),
셰이더 (shaders.py) 와 같은 상자 거르개로 GUI 배율 G 의 화면 픽셀을 만든다. 실제 클라이언트 그림과 견주는 데 쓴다.
"""
import numpy as np
from PIL import Image

from fonts import K


def layout(roles, text, line_h=12):
    """roles: 앞에서부터 그 글자를 가진 Role. 돌려주는 값: (알파, 그림자) K 배 텍셀 배열 (줄 위 = 2 GUI 픽셀)."""
    pen = 2 * K
    top = 2
    pieces = []
    for ch in text:
        role = next((r for r in roles if ch == " " or ch in r.glyphs), None)
        if role is None:
            continue
        if ch == " ":
            pen += role.space * K
            continue
        g = role.glyphs[ch]
        m = role.metrics()
        cell_top = (top + 7 - m["asc"]) * K
        pieces.append((g, pen, cell_top, m))
        pen += g["final_adv"] * K
    W = pen + 4 * K
    H = (line_h + 4) * K
    A = np.zeros((H, W), np.float32)
    for g, x, y, m in pieces:
        a = g["a"]
        if not a.size:
            continue
        yy = y + m["asc"] * K - g["top"]
        xx = x + g["x0"]
        A[yy:yy + a.shape[0], xx:xx + a.shape[1]] = np.maximum(A[yy:yy + a.shape[0], xx:xx + a.shape[1]], a)
    return A


def box(img, G):
    """K 텍셀 / GUI 픽셀 → G 화면 픽셀 / GUI 픽셀, 넓이 평균 (셰이더와 같다)."""
    h, w = img.shape
    up = np.repeat(np.repeat(img, G, 0), G, 1)
    H2, W2 = h * G // K, w * G // K
    up = up[:H2 * K, :W2 * K]
    return up.reshape(H2, K, W2, K).mean(axis=(1, 3))


def render(alpha, fg=(232, 220, 192), bg=(18, 16, 14), gamma=1.0):
    a = np.clip(alpha, 0, 1) ** gamma
    a = a[..., None]
    rgb = np.array(bg) * (1 - a) + np.array(fg) * a
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
