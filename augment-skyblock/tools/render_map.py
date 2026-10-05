#!/usr/bin/env python3
"""월드 폴더의 region 파일을 읽어 맵을 위에서 내려다본 그림을 만든다.  python3 render_map.py <world 폴더> <출력.png> [폰트.ttf]"""
import io
import math
import os
import struct
import sys
import zlib

import nbtlib
from PIL import Image, ImageDraw, ImageFont

COLORS = {
    "grass_block": (106, 170, 64), "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59), "stone": (125, 125, 125),
    "sand": (219, 207, 163), "sandstone": (216, 203, 155), "oak_leaves": (60, 120, 40), "birch_leaves": (90, 140, 60),
    "oak_log": (109, 85, 50), "birch_log": (216, 215, 210), "snow_block": (240, 250, 250), "packed_ice": (141, 180, 250),
    "blue_ice": (116, 168, 253), "netherrack": (110, 54, 52), "magma_block": (160, 70, 30), "blackstone": (42, 36, 41),
    "basalt": (80, 80, 85), "shroomlight": (240, 146, 70), "end_stone": (219, 222, 158), "obsidian": (20, 18, 30),
    "crying_obsidian": (50, 10, 90), "end_rod": (240, 240, 230), "sea_lantern": (172, 199, 190),
    "polished_diorite": (192, 193, 194), "smooth_quartz": (235, 229, 222), "quartz_pillar": (235, 230, 222),
    "smooth_sandstone": (223, 214, 170), "chiseled_sandstone": (216, 200, 150), "cut_sandstone": (218, 206, 160),
    "glowstone": (250, 210, 120), "lantern": (200, 150, 80), "purpur_block": (170, 125, 170), "prismarine_bricks": (99, 171, 158),
    "purpur_pillar": (172, 128, 172), "moss_block": (89, 110, 45), "calcite": (223, 224, 220), "chest": (160, 110, 40),
    "crafting_table": (140, 100, 60), "bedrock": (60, 60, 60), "cactus": (90, 140, 50), "polished_blackstone_bricks": (48, 42, 49),
    "lodestone": (150, 150, 155), "soul_lantern": (90, 170, 190), "end_portal_frame": (90, 120, 100), "short_grass": (106, 170, 64),
    "poppy": (200, 40, 40), "dandelion": (240, 220, 40), "coal_ore": (110, 110, 110), "iron_ore": (150, 135, 125),
    "diamond_ore": (120, 170, 170), "gold_ore": (170, 150, 90), "lapis_ore": (90, 100, 150), "emerald_ore": (100, 150, 110),
    "redstone_ore": (140, 100, 100), "nether_gold_ore": (130, 80, 50), "nether_quartz_ore": (140, 110, 100),
    "oak_sapling": (80, 140, 50),
}


def chunks(path):
    with open(path, "rb") as f:
        data = f.read()
    for i in range(1024):
        off = int.from_bytes(data[i * 4:i * 4 + 3], "big")
        if off == 0:
            continue
        start = off * 4096
        length = struct.unpack(">I", data[start:start + 4])[0]
        comp = data[start + 4]
        raw = data[start + 5:start + 4 + length]
        if comp == 2:
            raw = zlib.decompress(raw)
        else:
            continue
        yield nbtlib.File.parse(io.BytesIO(raw))


def column_tops(nbt):
    cx, cz = int(nbt["xPos"]), int(nbt["zPos"])
    tops = {}
    sections = sorted(nbt.get("sections", []), key=lambda s: -int(s["Y"]))
    for sec in sections:
        bs = sec.get("block_states")
        if bs is None:
            continue
        pal = [str(p["Name"]).replace("minecraft:", "") for p in bs["palette"]]
        if pal == ["air"]:
            continue
        sy = int(sec["Y"])
        if "data" not in bs:
            if pal[0] != "air":
                for x in range(16):
                    for z in range(16):
                        tops.setdefault((x, z), (sy * 16 + 15, pal[0]))
            continue
        bits = max(4, math.ceil(math.log2(len(pal))))
        per = 64 // bits
        mask = (1 << bits) - 1
        longs = [int(v) & 0xFFFFFFFFFFFFFFFF for v in bs["data"]]
        for x in range(16):
            for z in range(16):
                if (x, z) in tops:
                    continue
                for y in range(15, -1, -1):
                    idx = y * 256 + z * 16 + x
                    v = (longs[idx // per] >> ((idx % per) * bits)) & mask
                    name = pal[v]
                    if name != "air" and not name.endswith("_air"):
                        tops[(x, z)] = (sy * 16 + y, name)
                        break
    return cx, cz, tops


def main():
    world, out = sys.argv[1], sys.argv[2]
    font_path = sys.argv[3] if len(sys.argv) > 3 else None
    blocks = {}
    rdir = os.path.join(world, "region")
    for fn in os.listdir(rdir):
        if not fn.endswith(".mca"):
            continue
        for nbt in chunks(os.path.join(rdir, fn)):
            cx, cz, tops = column_tops(nbt)
            for (x, z), v in tops.items():
                blocks[(cx * 16 + x, cz * 16 + z)] = v
    xs = [k[0] for k in blocks]
    zs = [k[1] for k in blocks]
    minx, maxx, minz, maxz = min(xs) - 12, max(xs) + 12, min(zs) - 12, max(zs) + 12
    S = 3
    W, H = (maxx - minx + 1) * S, (maxz - minz + 1) * S
    img = Image.new("RGB", (W, H), (14, 16, 32))
    d = ImageDraw.Draw(img)
    for (x, z), (y, name) in blocks.items():
        c = COLORS.get(name, (150, 150, 150))
        k = max(0.6, min(1.3, 1 + (y - 70) / 60))
        c = tuple(min(255, int(v * k)) for v in c)
        px, pz = (x - minx) * S, (z - minz) * S
        d.rectangle([px, pz, px + S - 1, pz + S - 1], fill=c)
    labels = [("시작의 섬", 0, 0), ("모래섬", -38, 30), ("숲의 섬", 12, -48), ("실버 제단", 42, -6), ("골드 제단", -20, -96),
              ("프리즘 제단", 132, 118), ("서리 균열", -124, 52), ("화염 균열", 104, -124), ("공허 균열", -164, -172), ("끝의 섬", 230, -30)]
    f = ImageFont.truetype(font_path, 16) if font_path else ImageFont.load_default()
    for name, x, z in labels:
        px, pz = (x - minx) * S, (z - minz + 16) * S
        tw = d.textlength(name, font=f)
        d.text((px - tw / 2 + 1, pz + 1), name, font=f, fill=(0, 0, 0))
        d.text((px - tw / 2, pz), name, font=f, fill=(255, 255, 255))
    d.text((8, 6), "북 ↑", font=f, fill=(200, 200, 220))
    img.save(out)
    print(f"{len(blocks)} columns, {W}x{H}")


if __name__ == "__main__":
    main()
