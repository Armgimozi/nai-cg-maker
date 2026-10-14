"""서버 목록 아이콘 (64×64) — 미궁의 아가리: 금테 두른 룬 석문 + 소용돌이치는 차원문 + 아래로 내려가는 계단.
사용: python tools/server_icon.py  → plugin/src/main/resources/server-icon.png (플러그인이 서버 목록에 보냄, + 8배 확대 미리보기)."""
import math
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = 64


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def h2(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def build():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 255))
    px = img.load()
    cx, cy = 31.5, 30.0
    # 배경: 남보라 → 검정 비네트 + 별가루
    for y in range(S):
        for x in range(S):
            d = math.hypot(x - cx, y - (cy + 4)) / 46
            c = mix((44, 22, 78), (6, 4, 12), d ** 0.8)
            if h2(x, y, 7) > 0.993:
                c = mix(c, (200, 180, 255), 0.6)
            px[x, y] = c + (255,)
    # 문 모양 (안쪽 반지름 r_in, 바깥 r_out, 기둥은 아래로)
    r_in, r_out = 15.0, 21.5
    top = 30.0          # 아치 중심 높이
    base = 57           # 바닥선

    def inside_arch(x, y, r):
        if y >= top:
            return abs(x - cx) <= r
        return math.hypot(x - cx, y - top) <= r

    # 차원문 (안쪽)
    for y in range(S):
        for x in range(S):
            if not inside_arch(x + 0.5, y + 0.5, r_in) or y >= base:
                continue
            dx, dy = x + 0.5 - cx, y + 0.5 - (top + 6)
            rr = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            swirl = 0.5 + 0.5 * math.sin(ang * 2 + rr * 0.62)
            t = min(1.0, rr / 19)
            c = mix((150, 250, 255), (120, 40, 230), t ** 0.7)
            c = mix(c, (34, 8, 80), (1 - swirl) ** 1.5 * 0.85 * min(1.0, t * 1.4))
            c = mix(c, (255, 170, 255), max(0.0, swirl - 0.82) * 2.2 * t)
            if rr < 3.2:
                c = mix(c, (255, 255, 255), 0.75 - rr / 6)
            if h2(x, y, 3) > 0.985 and rr > 5:
                c = mix(c, (230, 210, 255), 0.7)
            px[x, y] = c + (255,)
    # 계단 (문 안쪽 아래로 내려감 — 어두운 돌)
    for i, (y0, w) in enumerate([(base - 2, 13.5), (base - 4, 11.0), (base - 6, 8.5)]):
        for y in range(y0, y0 + 2):
            for x in range(S):
                if abs(x + 0.5 - cx) <= w:
                    edge = y == y0
                    c = (92, 86, 110) if edge else (48, 44, 62)
                    if edge and h2(x, y, 11) > 0.7:
                        c = (118, 110, 138)
                    px[x, y] = c + (255,)
    # 석문 (룬 돌 + 금테)
    for y in range(S):
        for x in range(S):
            fx, fy = x + 0.5, y + 0.5
            if y > base + 1:
                continue
            if inside_arch(fx, fy, r_out) and not inside_arch(fx, fy, r_in):
                # 돌 벽돌 무늬
                if fy >= top:
                    u = abs(fx - cx) - r_in
                    v = fy
                else:
                    u = math.hypot(fx - cx, fy - top) - r_in
                    v = math.degrees(math.atan2(fy - top, fx - cx)) / 9
                shade = 0.5 + 0.5 * (-(fx - cx) / 30 - (fy - 30) / 50)
                c = mix((38, 36, 52), (112, 106, 132), shade)
                if int(v) % 4 == 0 or abs(u - 3.2) < 0.45:
                    c = mix(c, (20, 18, 30), 0.55)  # 줄눈
                if h2(x, y, 5) > 0.9:
                    c = mix(c, (150, 144, 170), 0.35)
                # 금테 (안쪽·바깥 가장자리)
                if u < 1.1 or u > (r_out - r_in) - 1.1:
                    g = 0.5 + 0.5 * math.sin((fx + fy) * 0.9)
                    c = mix((150, 98, 24), (255, 222, 120), g)
                # 룬 (보라 빛)
                if fy < top and 2.2 < u < 4.4 and int(v * 1.0) % 5 == 2:
                    c = (205, 140, 255)
                px[x, y] = c + (255,)
    # 쐐기돌 보석
    gx, gy = int(cx), int(top - r_out + 1)
    for y in range(gy - 3, gy + 5):
        for x in range(gx - 3, gx + 4):
            d = abs(x + 0.5 - cx) + abs(y + 0.5 - (gy + 1))
            if d <= 3.6:
                c = (255, 214, 96) if d > 2.4 else mix((255, 120, 200), (255, 240, 255), 1 - d / 2.4)
                px[x, y] = c + (255,)
    # 받침돌
    for y in range(base, base + 3):
        for x in range(S):
            if abs(x + 0.5 - cx) <= r_out + 2.5:
                c = (70, 64, 88) if y == base else (36, 32, 48)
                if y == base and h2(x, y, 9) > 0.6:
                    c = (96, 90, 118)
                px[x, y] = c + (255,)
    # 빛 입자 (문 주위 반짝임)
    for k in range(14):
        a = k * 2.399
        rr = 23 + 6 * h2(k, 1, 2)
        x = int(cx + math.cos(a) * rr)
        y = int(top + 2 + math.sin(a) * rr * 0.9)
        if 0 <= x < S and 0 <= y < S:
            col = (255, 230, 140) if k % 3 == 0 else (190, 160, 255)
            px[x, y] = col + (255,)
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= x + ox < S and 0 <= y + oy < S and k % 3 == 0:
                    px[x + ox, y + oy] = mix(px[x + ox, y + oy][:3], col, 0.5) + (255,)
    return img


def main():
    img = build()
    for p in (os.path.join(ROOT, 'plugin', 'src', 'main', 'resources', 'server-icon.png'),):
        img.save(p)
        print('wrote', p)
    prev = sys.argv[1] if len(sys.argv) > 1 else None
    if prev:
        img.resize((S * 8, S * 8), Image.NEAREST).save(prev)
        print('preview', prev)


if __name__ == '__main__':
    main()
