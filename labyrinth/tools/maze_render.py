#!/usr/bin/env python3
"""미궁 층 배치 PNG (위에서 본 모습). MazeRenderDump 가 만든 floorNN_sS.txt 를 읽는다.

사용: python3 maze_render.py <덤프 폴더> [출력 폴더]
 - 층마다 floorNN_sS.png (타일 1칸 = 3px) + contact_sS.png (10층 한 장)
 - 색: 복도 회색(높을수록 밝음) · 계단 노랑 · 방은 종류별 · 출입구 갈색 · 도랑 파랑 · 금 간 벽 주황 · 비밀방 보라
       막다른 길 끝 빨간 점(비밀 통로 앞 주황, 미로 굴 안 노란 작은 점) · 주 경로 하늘색 선 · 셀 경계 옅은 격자
"""
import glob
import os
import sys

from PIL import Image, ImageDraw

SCALE = 3
COL = {
    ' ': (8, 8, 12), 'D': (150, 100, 50), '~': (40, 90, 200), '/': (230, 200, 60), 'X': (255, 140, 0), 's': (170, 90, 220),
    'S': (70, 140, 255), 'C': (190, 70, 70), 'E': (140, 20, 30), 'T': (230, 190, 60), 'G': (170, 120, 230),
    'R': (80, 190, 90), 'B': (110, 40, 40),
}
WALL = (52, 50, 58)


def hall(ch):
    e = int(ch)
    v = 120 + e * 35
    return (v, v, v + 6)


def render(path, outdir):
    lines = open(path, encoding='utf-8').read().split('\n')
    w, d, n, mx, mz, pitch = map(int, lines[0].split())
    grid = lines[1:1 + d]
    meta = lines[1 + d:]
    img = Image.new('RGB', (w * SCALE, d * SCALE), COL[' '])
    px = img.load()

    def is_open(x, z):
        return 0 <= z < d and 0 <= x < w and grid[z][x] != ' '

    for z in range(d):
        row = grid[z]
        for x in range(w):
            ch = row[x]
            if ch == ' ':
                if any(is_open(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)):
                    c = WALL
                else:
                    continue
            elif ch.isdigit():
                c = hall(ch)
            else:
                c = COL.get(ch, (255, 0, 255))
            for yy in range(SCALE):
                for xx in range(SCALE):
                    px[x * SCALE + xx, z * SCALE + yy] = c
    dr = ImageDraw.Draw(img)
    # 셀 격자
    for i in range(n + 1):
        x = (mx + i * pitch) * SCALE
        z = (mz + i * pitch) * SCALE
        dr.line([(x, mz * SCALE), (x, (mz + n * pitch) * SCALE)], fill=(30, 30, 40))
        dr.line([(mx * SCALE, z), ((mx + n * pitch) * SCALE, z)], fill=(30, 30, 40))
    stat = ''
    for ln in meta:
        if ln.startswith('PATH'):
            cells = list(map(int, ln.split()[1:]))
            pts = [((mx + (c % n) * pitch + 12) * SCALE + 1, (mz + (c // n) * pitch + 12) * SCALE + 1) for c in cells]
            if len(pts) > 1:
                dr.line(pts, fill=(90, 220, 255), width=2)
        elif ln.startswith('DEAD'):
            x, z, ddx, ddz, sec, minor = map(int, ln.split()[1:])
            cx, cz = x * SCALE + 1, z * SCALE + 1
            r = 2 if minor else 4
            col = (255, 230, 120) if minor else ((255, 60, 60) if sec < 0 else (255, 170, 0))
            dr.ellipse([cx - r, cz - r, cx + r, cz + r], fill=col)
        elif ln.startswith('STAT'):
            stat = ln[5:]
    name = os.path.splitext(os.path.basename(path))[0]
    dr.text((4, 2), name + '  ' + stat[:150], fill=(255, 255, 255))
    out = os.path.join(outdir, name + '.png')
    img.save(out)
    return out


def main():
    src = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else src
    os.makedirs(outdir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, 'floor*_s*.txt')))
    outs = [render(f, outdir) for f in files]
    seeds = sorted({os.path.basename(o).split('_s')[1].split('.')[0] for o in outs})
    for s in seeds:
        imgs = [Image.open(o) for o in outs if o.endswith('_s' + s + '.png')]
        if not imgs:
            continue
        thumb = 0.5
        ims = [im.resize((int(im.width * thumb), int(im.height * thumb))) for im in imgs]
        cols = 5
        cw = max(i.width for i in ims)
        ch = max(i.height for i in ims)
        sheet = Image.new('RGB', (cw * cols, ch * ((len(ims) + cols - 1) // cols)), (0, 0, 0))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * cw, (i // cols) * ch))
        sheet.save(os.path.join(outdir, 'contact_s' + s + '.png'))
    print('\n'.join(outs))


if __name__ == '__main__':
    main()
