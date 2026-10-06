#!/usr/bin/env python3
"""월드 폴더의 region 파일을 읽어 맵을 위에서 내려다본 그림을 만든다.

    python3 render_map.py <world 폴더> <출력.png> [폰트.ttf] [--spoiler]

배포용 그림(dist/preview-map.png)은 --spoiler 없이 그린다: 시작의 섬 말고는 아무 표시도 없다.
--spoiler 를 붙이면 제단(실버 흰색, 골드 노란색, 프리즘 보라색 동그라미)과 보스 둥지를 표시한다 (관리자용).
"""
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
    "oak_sapling": (80, 140, 50), "water": (63, 118, 228), "lava": (207, 92, 15), "nether_wart": (130, 20, 20),
    "fire": (230, 140, 40), "soul_fire": (60, 200, 220), "pointed_dripstone": (130, 100, 85),
}


_TEX = {}


def color_of(name):
    """COLORS 에 없으면 마인크래프트 클라이언트 jar(MC_CLIENT_JAR)의 블록 텍스처 평균색을 쓴다."""
    if name in COLORS:
        return COLORS[name]
    if name in _TEX:
        return _TEX[name]
    c = (150, 150, 150)
    jar = os.environ.get("MC_CLIENT_JAR")
    if jar and os.path.exists(jar):
        import zipfile
        with zipfile.ZipFile(jar) as z:
            for cand in (name + "_top", name, name.replace("_block", ""), name + "_side", name + "_stage3", name + "_stage7"):
                try:
                    im = Image.open(io.BytesIO(z.read(f"assets/minecraft/textures/block/{cand}.png"))).convert("RGBA")
                except KeyError:
                    continue
                im = im.crop((0, 0, im.width, im.width))
                px = [p for p in im.getdata() if p[3] > 0]
                if px:
                    c = tuple(sum(p[i] for p in px) // len(px) for i in range(3))
                    if "leaves" in name or name in ("short_grass", "tall_grass", "fern", "vine"):
                        c = (int(c[0] * 0.45), int(c[1] * 0.75), int(c[2] * 0.35))
                    break
    _TEX[name] = c
    return c


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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    spoiler = "--spoiler" in sys.argv[1:]
    world, out = args[0], args[1]
    font_path = args[2] if len(args) > 2 else None
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
    S = 2 if (maxx - minx) > 400 else 3
    W, H = (maxx - minx + 1) * S, (maxz - minz + 1) * S
    img = Image.new("RGB", (W, H), (14, 16, 32))
    d = ImageDraw.Draw(img)
    for (x, z), (y, name) in blocks.items():
        c = color_of(name)
        k = max(0.6, min(1.3, 1 + (y - 70) / 60))
        c = tuple(min(255, int(v * k)) for v in c)
        px, pz = (x - minx) * S, (z - minz) * S
        d.rectangle([px, pz, px + S - 1, pz + S - 1], fill=c)
    f = ImageFont.truetype(font_path, 15) if font_path else ImageFont.load_default()

    def label(name, x, z, font, fill=(255, 255, 255), dy=10):
        px, pz = (x - minx) * S, (z - minz + dy) * S
        tw = d.textlength(name, font=font)
        d.text((px - tw / 2 + 1, pz + 1), name, font=font, fill=(0, 0, 0))
        d.text((px - tw / 2, pz), name, font=font, fill=fill)

    tier_col = {"SILVER": (230, 236, 245), "GOLD": (255, 207, 64), "PRISM": (200, 107, 255)}
    if spoiler:
        # 제단 (월드 폴더의 기록)과 보스 둥지. 플레이어에게 보여 줄 그림에는 넣지 않는다
        try:
            import yaml
            alt = yaml.safe_load(open(os.path.join(world, "augsky-altars.yml"))) or {}
            for a in (alt.get("altars") or {}).values():
                px, pz = (a["x"] - minx) * S, (a["z"] - minz) * S
                r = 7
                d.ellipse([px - r, pz - r, px + r, pz + r], outline=(0, 0, 0), width=4)
                d.ellipse([px - r, pz - r, px + r, pz + r], outline=tier_col.get(a["tier"], (255, 255, 255)), width=2)
            lairs = yaml.safe_load(open(os.path.join(world, "augsky-lairs.yml"))) or {}
            names = {"frost_tyrant": "서리 군주의 둥지", "inferno_colossus": "화염 거신의 둥지", "void_sovereign": "공허 군주의 둥지"}
            for l in (lairs.get("lairs") or {}).values():
                label("☠ " + names.get(l["boss"], l["boss"]), l["x"], l["z"], f, (255, 140, 140), dy=22)
        except FileNotFoundError:
            pass
        lx, ly = 10, H - 90
        for i, (t, name) in enumerate([("SILVER", "실버 제단 16"), ("GOLD", "골드 제단 9"), ("PRISM", "프리즘 제단 5")]):
            yy = ly + i * 26
            d.ellipse([lx, yy, lx + 14, yy + 14], outline=tier_col[t], width=2)
            d.text((lx + 22, yy - 3), name, font=f, fill=(230, 230, 240))
    label("시작의 섬", 0, 0, f)
    d.text((8, 6), "북 ↑", font=f, fill=(200, 200, 220))
    img.save(out)
    print(f"{len(blocks)} columns, {W}x{H}")


if __name__ == "__main__":
    main()
