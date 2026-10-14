#!/usr/bin/env python3
"""blockdata.json 생성기 — 26.x 바닐라 데이터에서 블록 상태 표·태그·모양·색을 뽑는다.

vlib.py(블록 이름·속성 검증, 기본값 채우기, 완전 고체 판정)와 render.py(색)가 이 파일을 읽는다.
마인크래프트 버전을 올릴 때만 다시 만든다:

    /opt/packvenv/bin/python tools/village/gen_blockdata.py \
        --server-jar /opt/paper/cache/mojang_26.3.jar --client-jar /opt/mc-ref/client.jar

- 블록 상태 표: 서버 jar 의 데이터 생성기(--reports)가 만드는 blocks.json (속성 이름·값·기본 상태).
- 태그: 서버 jar 안 data/minecraft/tags/block/*.json (담장·울타리·잎 등 연결 규칙용).
- 모양·색: 클라이언트 jar 의 blockstates·models·textures (완전한 정육면체인지, 윗면/옆면 평균색).
  텍스처 자체는 저장하지 않고 평균색 숫자만 남긴다.
"""
import argparse
import colorsys
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "blockdata.json")

# 바이옴 색이 입혀지는 텍스처(tintindex)의 기본 색 — 평원 기준
GRASS_TINT = (0x91, 0xBD, 0x59)
FOLIAGE_TINT = (0x77, 0xAB, 0x2F)
WATER_TINT = (0x3F, 0x76, 0xE4)
SPECIAL_TINT = {
    "spruce_leaves": (0x61, 0x99, 0x61),
    "birch_leaves": (0x80, 0xA7, 0x55),
    "mangrove_leaves": (0x92, 0xC6, 0x48),
    "lily_pad": (0x20, 0x80, 0x30),
    "melon_stem": (0x9A, 0xB8, 0x2A),
    "pumpkin_stem": (0x9A, 0xB8, 0x2A),
    "attached_melon_stem": (0xC8, 0xB0, 0x30),
    "attached_pumpkin_stem": (0xC8, 0xB0, 0x30),
    "redstone_wire": (0xC0, 0x10, 0x10),
}
TAGS = ["walls", "fences", "wooden_fences", "fence_gates", "leaves", "wall_post_override",
        "shulker_boxes", "signs", "wall_signs", "standing_signs", "ceiling_hanging_signs",
        "wall_hanging_signs", "banners", "pressure_plates", "logs", "flowers", "small_flowers",
        "saplings", "replaceable", "replaceable_by_trees", "dirt", "sand", "base_stone_overworld",
        "snow", "stairs", "slabs", "doors", "trapdoors", "beds", "candles", "buttons", "rails",
        "climbable", "ice", "infiniburn_overworld", "fire", "campfires", "crops", "flower_pots"]


def run_reports(server_jar, workdir):
    """데이터 생성기를 돌려 reports/blocks.json 경로를 돌려준다."""
    out = os.path.join(workdir, "out")
    cmd = ["java", "-DbundlerMainClass=net.minecraft.data.Main", "-jar", server_jar,
           "--reports", "--output", out]
    print("데이터 생성기 실행:", " ".join(cmd))
    subprocess.run(cmd, cwd=workdir, check=True, stdout=subprocess.DEVNULL)
    return os.path.join(out, "reports", "blocks.json")


def inner_server_jar(server_jar, workdir):
    """번들러 jar 안의 진짜 서버 jar 를 꺼낸다 (태그 읽기용)."""
    with zipfile.ZipFile(server_jar) as z:
        names = [n for n in z.namelist() if n.startswith("META-INF/versions/") and n.endswith(".jar")]
        if not names:
            return server_jar
        z.extract(names[0], workdir)
        return os.path.join(workdir, names[0])


def read_banner_patterns(jar):
    with zipfile.ZipFile(jar) as z:
        pre = "data/minecraft/banner_pattern/"
        return sorted(n[len(pre):-5] for n in z.namelist() if n.startswith(pre) and n.endswith(".json"))


def read_tags(jar):
    raw = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.startswith("data/minecraft/tags/block/") and n.endswith(".json"):
                key = n[len("data/minecraft/tags/block/"):-5]
                raw[key] = json.loads(z.read(n))["values"]

    def resolve(key, seen=()):
        out = []
        for v in raw.get(key, []):
            if isinstance(v, dict):
                v = v["id"]
            if v.startswith("#"):
                k = v[1:].split(":", 1)[-1]
                if k not in seen:
                    out += resolve(k, seen + (key,))
            else:
                out.append(v.split(":", 1)[-1])
        return sorted(set(out))

    return {k: resolve(k) for k in TAGS if k in raw}


class Assets:
    def __init__(self, client_jar):
        self.z = zipfile.ZipFile(client_jar)
        self.names = set(self.z.namelist())
        self.models = {}
        self.tex_cache = {}

    def json(self, path):
        if path not in self.names:
            return None
        return json.loads(self.z.read(path))

    def model(self, ref):
        """부모를 따라가며 textures/elements 를 합친 모델."""
        name = ref.split(":", 1)[-1]
        if name in self.models:
            return self.models[name]
        data = self.json("assets/minecraft/models/%s.json" % name) or {}
        textures, elements, chain = {}, None, [name]
        if "parent" in data and not data["parent"].startswith("builtin/"):
            parent = self.model(data["parent"])
            textures.update(parent["textures"])
            elements = parent["elements"]
            chain += parent["chain"]
        textures.update(data.get("textures", {}))
        if "elements" in data:
            elements = data["elements"]
        m = {"textures": textures, "elements": elements or [], "chain": chain}
        self.models[name] = m
        return m

    @staticmethod
    def resolve_tex(textures, ref, depth=0):
        if isinstance(ref, dict):  # 새 형식: {"sprite": "...", ...}
            ref = ref.get("sprite")
        while ref and ref.startswith("#") and depth < 10:
            ref = textures.get(ref[1:])
            if isinstance(ref, dict):
                ref = ref.get("sprite")
            depth += 1
        return ref

    def tex_stats(self, ref):
        """텍스처 평균색 (불투명 픽셀 가중), 강조색(채도 높은 픽셀), 불투명 비율."""
        if not ref:
            return None
        name = ref.split(":", 1)[-1]
        if name in self.tex_cache:
            return self.tex_cache[name]
        path = "assets/minecraft/textures/%s.png" % name
        if path not in self.names:
            self.tex_cache[name] = None
            return None
        im = Image.open(io.BytesIO(self.z.read(path))).convert("RGBA")
        w, h = im.size
        if h > w:  # 애니메이션 띠 → 첫 프레임
            im = im.crop((0, 0, w, w))
        px = list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())
        opaque = [(r, g, b) for r, g, b, a in px if a >= 128]
        cover = len(opaque) / float(len(px))
        alpha = sum(a for _, _, _, a in px if a >= 8) / 255.0 / max(1, sum(1 for p in px if p[3] >= 8))
        if not opaque:
            self.tex_cache[name] = None
            return None
        avg = tuple(sum(c[i] for c in opaque) / len(opaque) for i in range(3))
        sat = sorted(opaque, key=lambda c: -colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)[1])
        top = sat[:max(1, len(sat) // 4)]
        accent = tuple(sum(c[i] for c in top) / len(top) for i in range(3))
        h, sv, v = colorsys.rgb_to_hsv(avg[0] / 255, avg[1] / 255, avg[2] / 255)
        st = {"avg": avg, "accent": accent, "cover": cover, "alpha": alpha, "sat": sv}
        self.tex_cache[name] = st
        return st


def pick_model(bs, default_props):
    """기본 상태에 맞는 모델 이름 하나 (variants 또는 multipart 첫 조각)."""
    if not bs:
        return None
    if "variants" in bs:
        variants = bs["variants"]
        best = None
        for key, v in variants.items():
            ok = True
            if key:
                for kv in key.split(","):
                    k, _, val = kv.partition("=")
                    if default_props.get(k) != val:
                        ok = False
                        break
            if ok:
                best = v
                break
        if best is None:
            best = next(iter(variants.values()))
        if isinstance(best, list):
            best = best[0]
        return best.get("model")
    if "multipart" in bs:
        for part in bs["multipart"]:
            ap = part["apply"]
            if isinstance(ap, list):
                ap = ap[0]
            return ap.get("model")
    return None


def tint_for(block_id, tags):
    if block_id in SPECIAL_TINT:
        return SPECIAL_TINT[block_id]
    if block_id in ("water", "bubble_column", "water_cauldron"):
        return WATER_TINT
    if block_id in tags.get("leaves", []) or block_id in ("vine",):
        return FOLIAGE_TINT
    return GRASS_TINT


def mul(c, t):
    return tuple(c[i] * t[i] / 255.0 for i in range(3))


def hexc(c):
    return "%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server-jar", default="/opt/paper/cache/mojang_26.3.jar")
    ap.add_argument("--client-jar", default="/opt/mc-ref/client.jar")
    ap.add_argument("--reports", help="이미 만든 reports/blocks.json (없으면 데이터 생성기 실행)")
    ap.add_argument("--version", default="26.3")
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="blockdata_")
    reports = args.reports or run_reports(args.server_jar, work)
    sjar = inner_server_jar(args.server_jar, work)
    tags = read_tags(sjar)
    patterns = read_banner_patterns(sjar)
    report = json.load(open(reports))
    assets = Assets(args.client_jar)

    blocks, full, colors, shapes = {}, [], {}, {}
    for full_id in sorted(report):
        bid = full_id.split(":", 1)[1]
        info = report[full_id]
        props = info.get("properties", {})
        default = next(s for s in info["states"] if s.get("default")).get("properties", {})
        blocks[bid] = [[k, props[k], default[k]] for k in sorted(props)]

        bs = assets.json("assets/minecraft/blockstates/%s.json" % bid)
        mref = pick_model(bs, default)
        model = assets.model(mref) if mref else {"textures": {}, "elements": []}
        els = model["elements"]
        if any(e.get("from") == [0, 0, 0] and e.get("to") == [16, 16, 16] for e in els):
            full.append(bid)
        elif els:
            # 완전 고체가 아닌 블록: 기본 상태 모델의 요소 전체를 감싸는 상자(1/16 단위) + 십자형(꽃·풀) 여부
            lo = [min(min(e["from"][i], e["to"][i]) for e in els) for i in range(3)]
            hi = [max(max(e["from"][i], e["to"][i]) for e in els) for i in range(3)]
            cross = any("cross" in c or c.endswith("/crop") for c in model["chain"])
            shapes[bid] = [round(v, 1) for v in lo + hi] + ["cross" if cross else "box"]

        tx = model["textures"]
        top_ref = side_ref = None
        top_tint = side_tint = False
        for e in els:
            faces = e.get("faces", {})
            if top_ref is None and "up" in faces:
                top_ref = Assets.resolve_tex(tx, faces["up"].get("texture"))
                top_tint = "tintindex" in faces["up"]
            for f in ("north", "south", "east", "west"):
                if side_ref is None and f in faces:
                    side_ref = Assets.resolve_tex(tx, faces[f].get("texture"))
                    side_tint = "tintindex" in faces[f]
        part = Assets.resolve_tex(tx, tx.get("particle")) if tx else None
        ts = assets.tex_stats(top_ref) or assets.tex_stats(side_ref) or assets.tex_stats(part)
        ss = assets.tex_stats(side_ref) or assets.tex_stats(top_ref) or assets.tex_stats(part)
        if ts is None or ss is None:
            continue
        # tintindex 가 있어도 텍스처 자체가 색이 있으면(벚나무 잎 등) 바이옴 색을 입히지 않는다
        tint = tint_for(bid, tags)
        top_tint = top_tint and ts["sat"] < 0.18
        side_tint = side_tint and ss["sat"] < 0.18
        top = mul(ts["avg"], tint) if top_tint else ts["avg"]
        side = mul(ss["avg"], tint) if side_tint else ss["avg"]
        accent = mul(ss["accent"], tint) if side_tint else ss["accent"]
        if bid == "grass_block":  # 옆면은 흙 + 위쪽 풀 띠 → 흙 쪽으로
            side = tuple(side[i] * 0.8 + mul(GRASS_TINT, (255, 255, 255))[i] * 0.2 for i in range(3))
        cover = min(ts["cover"], ss["cover"])
        colors[bid] = [hexc(top), hexc(side), hexc(accent), round(cover, 2), round(ss["alpha"], 2)]

    out = {
        "version": args.version,
        "note": "gen_blockdata.py 생성물 — 손으로 고치지 말 것. blocks: id → [[속성, [값...], 기본값], ...]; "
                "full: 모델이 완전한 정육면체인 블록; shapes: 그 밖의 블록 → [x0,y0,z0,x1,y1,z1 (1/16), cross|box]; "
                "colors: id → [윗면, 옆면, 강조색, 불투명 비율, 평균 알파]",
        "blocks": blocks,
        "full": full,
        "tags": tags,
        "colors": colors,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("{\n")
        f.write('"version": %s,\n"note": %s,\n' % (json.dumps(out["version"]), json.dumps(out["note"], ensure_ascii=False)))
        f.write('"blocks": {\n')
        f.write(",\n".join("%s: %s" % (json.dumps(k), json.dumps(v, separators=(",", ":"))) for k, v in blocks.items()))
        f.write("\n},\n")
        f.write('"full": %s,\n' % json.dumps(full, separators=(",", ":")))
        f.write('"banner_patterns": %s,\n' % json.dumps(patterns, separators=(",", ":")))
        f.write('"shapes": {\n')
        f.write(",\n".join("%s: %s" % (json.dumps(k), json.dumps(v, separators=(",", ":"))) for k, v in shapes.items()))
        f.write("\n},\n")
        f.write('"tags": {\n')
        f.write(",\n".join("%s: %s" % (json.dumps(k), json.dumps(v, separators=(",", ":"))) for k, v in tags.items()))
        f.write("\n},\n")
        f.write('"colors": {\n')
        f.write(",\n".join("%s: %s" % (json.dumps(k), json.dumps(v, separators=(",", ":"))) for k, v in colors.items()))
        f.write("\n}\n}\n")
    print("블록 %d개, 완전 고체 %d개, 색 %d개 → %s" % (len(blocks), len(full), len(colors), OUT))


if __name__ == "__main__":
    sys.exit(main())
