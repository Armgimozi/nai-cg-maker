#!/usr/bin/env python3
"""district_fingerprint.py — 배포 월드 지문 (0.3.6 광산 마을, CONTRACT §2.13 · district.json fingerprint).

    /opt/packvenv/bin/python -I tools/village/district_fingerprint.py                 # 만들기 → resources/village/districts/mine.fp
    /opt/packvenv/bin/python -I tools/village/district_fingerprint.py --check         # 지금 파일과 같은지만 (다르면 종료 코드 1)
    ... --world <world.zip | 서버팩 zip | world 폴더> [--world ...] --district mine

기존 서버의 구역 자리가 배포 월드 그대로인지(사람이 손대지 않았는지) jar 가 맞대어 보는 열 기록이다. 열(x, z)마다:
- h      = 땅 높이: 위에서 내려오며 처음 만나는 Nature GROUND 블록 (계획기 Scan.columns 와 같은 규칙)
- hash   = h−10 ~ h+30 블록을 정규화한 FNV-1a 64 (잔디·흙·거친 흙·회백토·균사체·뿌리 흙 = dirt, 공기·식물·눈 층·잎·원목·
           나무에 붙은 것 = air, 물·거품 기둥·얼음 = water)
- under  = 땅속 10칸(h−1 … h−10) 가운데 단단한 칸 비트 (새 공기·물 = 판 구덩이·굴)
- logs   = h+1 ~ h+30 원목 자리 (dy) — 새 원목 = 심은 나무·원목 건물
Java 쪽은 kr.labyrinth.village.DistrictFingerprint (같은 규칙, 같은 해시 — 시험이 nature_hash·probe 로 맞대어 봄).

두 배포 월드(지금 dist/world.zip 과 0.2.0 서버팩의 world)를 둘 다 읽어 열마다 맞대어 본다. 모두 같으면 지문 하나에 build_id 둘,
다르면 월드마다 따로 쓴다 (어느 쪽이든 맞으면 통과). 덮는 범위 = 구역 모든 자리(east·south_east)의 마스크 상자.
"""
import argparse
import gzip
import io
import json
import math
import os
import re
import struct
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
RES = os.path.join(ROOT, "plugin", "src", "main", "resources", "village")
MAGIC = b"LBFP"
VERSION = 1
UNDER = 10
ABOVE = 30
# 조각이 slack 으로 옮겨질 수 있는 칸 + 나무 조사 여유 — 마스크(R+B) 둘레에 더 덮는다
EXTRA = 4

# ── Nature.java 그대로 (블록 id 만 본다) ─────────────────────────────────────
GROUND = {"stone", "granite", "diorite", "andesite", "deepslate", "tuff", "calcite",
          "dripstone_block", "sandstone", "red_sandstone", "terracotta", "dirt", "coarse_dirt", "rooted_dirt", "grass_block",
          "podzol", "mycelium", "mud", "clay", "gravel", "sand", "red_sand", "snow_block", "powder_snow", "moss_block",
          "pale_moss_block", "amethyst_block", "budding_amethyst", "smooth_basalt", "obsidian", "magma_block", "bedrock",
          "mossy_cobblestone", "sculk", "infested_stone", "infested_deepslate", "raw_iron_block", "raw_copper_block",
          "bone_block", "cinnabar", "sulfur", "potent_sulfur"}
PLANT = {"short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "bush",
         "firefly_bush", "short_dry_grass", "tall_dry_grass", "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet",
         "red_tulip", "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley",
         "sunflower", "lilac", "rose_bush", "peony", "torchflower", "pitcher_plant", "pink_petals", "wildflowers", "leaf_litter",
         "closed_eyeblossom", "open_eyeblossom", "cactus_flower", "sweet_berry_bush", "snow", "brown_mushroom", "red_mushroom",
         "sugar_cane", "cactus", "bamboo", "bamboo_sapling", "pumpkin", "melon", "azalea", "flowering_azalea", "moss_carpet",
         "pale_moss_carpet", "big_dripleaf", "big_dripleaf_stem", "small_dripleaf", "spore_blossom", "glow_lichen",
         "hanging_roots", "lily_pad", "seagrass", "tall_seagrass", "kelp", "kelp_plant", "pointed_dripstone", "cave_vines",
         "cave_vines_plant", "sculk_vein", "amethyst_cluster", "large_amethyst_bud", "medium_amethyst_bud", "small_amethyst_bud",
         "red_shrub", "sulfur_spike"}
TREE_PART = {"vine", "cocoa", "bee_nest", "pale_hanging_moss", "resin_clump", "mangrove_propagule", "creaking_heart"}
DIRT = {"grass_block", "dirt", "coarse_dirt", "podzol", "mycelium", "rooted_dirt"}


def kind(k):
    if k in ("air", "cave_air", "void_air"):
        return "AIR"
    if k in ("water", "lava", "bubble_column"):
        return "LIQUID"
    if k in ("ice", "packed_ice", "blue_ice", "frosted_ice"):
        return "ICE"
    if k.endswith("_leaves"):
        return "LEAVES"
    if k in TREE_PART:
        return "TREE_PART"
    if not k.startswith("stripped_") and (k.endswith("_log") or k.endswith("_wood") or k in (
            "mushroom_stem", "brown_mushroom_block", "red_mushroom_block", "mangrove_roots", "muddy_mangrove_roots")):
        return "LOG"
    if k in PLANT or k.endswith("_sapling"):
        return "PLANT"
    if k in GROUND or (k.endswith("_ore") and "nether" not in k) or (k.endswith("_terracotta") and not k.endswith("glazed_terracotta")):
        return "GROUND"
    return "UNNATURAL"


def norm(k):
    """지문 정규화 (Java DistrictFingerprint.norm 과 같게)."""
    t = kind(k)
    if t in ("AIR", "PLANT", "LEAVES", "LOG", "TREE_PART"):
        return "air"
    if t == "LIQUID":
        return "lava" if k == "lava" else "water"
    if t == "ICE":
        return "water"
    if k in DIRT:
        return "dirt"
    return k


def fnv(data, h=0xcbf29ce484222325):
    for b in data:
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def nature_signature():
    """Java Nature.signature() 와 같은 글 — 두 쪽 분류 목록이 같은지 지문에 적어 둔다."""
    return "G:" + ",".join(sorted(GROUND)) + "|P:" + ",".join(sorted(PLANT)) + "|T:" + ",".join(sorted(TREE_PART))


def column_hash(names):
    """names = h−10 … h+30 의 정규화 이름 (아래부터)."""
    return fnv(("\n".join(names) + "\n").encode("utf-8"))


PROBE = ["stone", "dirt", "air", "water", "granite"]


def signed64(v):
    return v - (1 << 64) if v >= (1 << 63) else v


# ── Anvil 읽기 (표준 라이브러리만) ──────────────────────────────────────────

def _nbt(buf, pos, t):
    if t == 1:
        return struct.unpack_from(">b", buf, pos)[0], pos + 1
    if t == 2:
        return struct.unpack_from(">h", buf, pos)[0], pos + 2
    if t == 3:
        return struct.unpack_from(">i", buf, pos)[0], pos + 4
    if t == 4:
        return struct.unpack_from(">q", buf, pos)[0], pos + 8
    if t == 5:
        return struct.unpack_from(">f", buf, pos)[0], pos + 4
    if t == 6:
        return struct.unpack_from(">d", buf, pos)[0], pos + 8
    if t == 7:
        n = struct.unpack_from(">i", buf, pos)[0]
        return bytes(buf[pos + 4:pos + 4 + n]), pos + 4 + n
    if t == 8:
        n = struct.unpack_from(">H", buf, pos)[0]
        return buf[pos + 2:pos + 2 + n].decode("utf-8", "replace"), pos + 2 + n
    if t == 9:
        et = buf[pos]
        n = struct.unpack_from(">i", buf, pos + 1)[0]
        pos += 5
        out = []
        for _ in range(n):
            v, pos = _nbt(buf, pos, et)
            out.append(v)
        return out, pos
    if t == 10:
        d = {}
        while True:
            et = buf[pos]
            pos += 1
            if et == 0:
                return d, pos
            n = struct.unpack_from(">H", buf, pos)[0]
            name = buf[pos + 2:pos + 2 + n].decode("utf-8", "replace")
            pos += 2 + n
            v, pos = _nbt(buf, pos, et)
            d[name] = v
    if t == 11:
        n = struct.unpack_from(">i", buf, pos)[0]
        return list(struct.unpack_from(">%di" % n, buf, pos + 4)), pos + 4 + 4 * n
    if t == 12:
        n = struct.unpack_from(">i", buf, pos)[0]
        return list(struct.unpack_from(">%dq" % n, buf, pos + 4)), pos + 4 + 8 * n
    raise ValueError("NBT tag %d" % t)


def _root(raw):
    n = struct.unpack_from(">H", raw, 1)[0]
    v, _ = _nbt(raw, 3 + n, raw[0])
    return v


class Region:
    def __init__(self, data):
        self.data = data

    def chunk(self, lcx, lcz):
        i = 4 * ((lcx & 31) + (lcz & 31) * 32)
        off = int.from_bytes(self.data[i:i + 3], "big")
        if off == 0:
            return None
        p = off * 4096
        ln = struct.unpack_from(">i", self.data, p)[0]
        comp = self.data[p + 4]
        body = self.data[p + 5:p + 4 + ln]
        if comp == 2:
            raw = zlib.decompress(body)
        elif comp == 1:
            raw = gzip.decompress(body)
        elif comp == 3:
            raw = body
        else:
            return None
        return _root(raw)


def _pal_id(p):
    """팔레트 항목 → id. 26.x 는 속성 없는 블록을 문자열("minecraft:stone")로, 있는 블록은 {Name, Properties} 로 쓴다
    (둘이 섞이면 문자열은 {"": …})."""
    if isinstance(p, dict):
        # 섞인 목록(문자열 + 묶음)은 문자열을 {"": 문자열} 로 감싼다 (NBT 목록은 한 종류만)
        name = p.get("Name", p.get(""))
    else:
        name = p
    name = str(name)
    return name.split("[", 1)[0].split(":", 1)[-1]


class Chunk:
    """블록 id (네임스페이스·속성 뺀) 조회."""

    def __init__(self, nbt):
        self.sections = {}
        for s in nbt.get("sections", []):
            bs = s.get("block_states")
            if not bs:
                continue
            pal = [_pal_id(p) for p in bs["palette"]]
            data = bs.get("data")
            if not data or len(pal) == 1:
                self.sections[s["Y"]] = (pal, None)
                continue
            bits = max(4, (len(pal) - 1).bit_length())
            per = 64 // bits
            mask = (1 << bits) - 1
            idx = []
            for i in range(4096):
                v = data[i // per] & 0xFFFFFFFFFFFFFFFF
                idx.append((v >> ((i % per) * bits)) & mask)
            self.sections[s["Y"]] = (pal, idx)
        self.min_y = min(self.sections) * 16 if self.sections else -64
        self.max_y = max(self.sections) * 16 + 15 if self.sections else 319

    def block(self, lx, y, lz):
        s = self.sections.get(y >> 4)
        if s is None:
            return "air"
        pal, idx = s
        if idx is None:
            return pal[0]
        return pal[idx[((y & 15) * 16 + lz) * 16 + lx]]


class World:
    """zip(서버팩·world.zip) 또는 폴더 안의 주 월드."""

    def __init__(self, path):
        self.path = path
        self.zip = zipfile.ZipFile(path) if path.endswith(".zip") else None
        names = self.zip.namelist() if self.zip else [os.path.relpath(os.path.join(b, f), path).replace(os.sep, "/")
                                                      for b, _, fs in os.walk(path) for f in fs]
        metas = [n for n in names if n.endswith("dimensions/minecraft/overworld/labyrinth-village.yml")]
        if not metas:
            raise SystemExit("%s: 마을 메타데이터(labyrinth-village.yml)가 없습니다" % path)
        self.prefix = metas[0][: -len("labyrinth-village.yml")]
        meta = self.read(metas[0]).decode("utf-8")
        m = re.search(r"^build_id:\s*['\"]?([0-9a-f-]+)", meta, re.M)
        self.build_id = m.group(1) if m else ""
        self.regions = {}
        self.chunks = {}

    def read(self, name):
        if self.zip:
            return self.zip.read(name)
        with open(os.path.join(self.path, name), "rb") as f:
            return f.read()

    def chunk(self, cx, cz):
        k = (cx, cz)
        if k in self.chunks:
            return self.chunks[k]
        rk = (cx >> 5, cz >> 5)
        if rk not in self.regions:
            name = self.prefix + "region/r.%d.%d.mca" % rk
            try:
                self.regions[rk] = Region(self.read(name))
            except (KeyError, FileNotFoundError):
                self.regions[rk] = None
        reg = self.regions[rk]
        nbt = reg.chunk(cx & 31, cz & 31) if reg else None
        st = nbt.get("Status", "") if nbt else ""
        c = Chunk(nbt) if nbt and str(st).split(":")[-1] in ("full", "minecraft:full") else None
        self.chunks[k] = c
        return c

    def column(self, x, z):
        """열 지문 (h, hash, under, logs) — 청크가 없으면 None."""
        c = self.chunk(x >> 4, z >> 4)
        if c is None:
            return None
        lx, lz = x & 15, z & 15
        h = None
        for y in range(c.max_y, c.min_y - 1, -1):
            if kind(c.block(lx, y, lz)) == "GROUND":
                h = y
                break
        if h is None:
            return None
        names = []
        for y in range(h - UNDER, h + ABOVE + 1):
            names.append(norm(c.block(lx, y, lz)) if c.min_y <= y <= c.max_y else "void")
        under = 0
        for k in range(1, UNDER + 1):
            y = h - k
            nm = norm(c.block(lx, y, lz)) if c.min_y <= y <= c.max_y else "void"
            if nm not in ("air", "water", "lava"):
                under |= 1 << (k - 1)
        logs = [dy for dy in range(1, ABOVE + 1) if c.min_y <= h + dy <= c.max_y and kind(c.block(lx, h + dy, lz)) == "LOG"]
        return (h, column_hash(names), under, tuple(logs))


# ── 덮는 범위 (구역 json + 조각 크기 + 배포 마을 중심·회전) ─────────────────

def _around(x, z, t):
    t %= 4
    return [(x, z), (-z, x), (-x, -z), (z, -x)][t]


def _dims(w, d, turns):
    return (w, d) if turns % 2 == 0 else (d, w)


FRONT = {"north": 0, "east": 1, "south": 2, "west": 3}


def coverage(district):
    """구역 json → 모든 자리의 마스크 상자 (배포 월드 좌표, x0 z0 x1 z1 — 양끝 포함)."""
    cx, cz = district["shipped"]["center"]
    t = district["shipped"]["turns"]
    R, B = district["mask"]["R"], district["mask"]["B"]
    reach = R + B + EXTRA
    boxes = []
    for site in district["sites"]:
        sx, sz = site.get("shift", [0, 0])
        drop = set(site.get("drop", []))
        rep = {int(k): v for k, v in site.get("replace_paths", {}).items()}
        x0 = z0 = 10 ** 9
        x1 = z1 = -10 ** 9
        for i, e in enumerate(district["pieces"]):
            if i in drop:
                continue
            with open(os.path.join(RES, "pieces", e["piece"] + ".json"), encoding="utf-8") as f:
                bp = json.load(f)
            w, _, d = bp["size"]
            deco = bp.get("deco", any(e["piece"].startswith(p) for p in (
                "lamp_post", "bench", "well", "flower_bed", "tree_", "signpost", "cart", "fence", "planter", "statue",
                "banner_pole", "crate", "barrel_stack", "hay")))
            slack = e.get("slack", bp.get("slack", 3 if deco else 2))
            pt = FRONT[e["front"]]
            vw, vd = _dims(w, d, pt)
            ax, az = e["at"][0] + sx, e["at"][1] + sz
            vx0, vz0 = ax - vw // 2, az - vd // 2
            for (qx, qz) in ((vx0, vz0), (vx0 + vw - 1, vz0 + vd - 1)):
                wx, wz = _around(qx, qz, t)
                x0, x1 = min(x0, cx + wx - slack), max(x1, cx + wx + slack)
                z0, z1 = min(z0, cz + wz - slack), max(z1, cz + wz + slack)
        for i, pth in enumerate(district["paths"]):
            pts = rep[i] if i in rep else [[q[0] + sx, q[1] + sz] for q in pth["points"]]
            half = pth.get("width", 3) // 2 + 1
            for q in pts:
                wx, wz = _around(q[0], q[1], t)
                x0, x1 = min(x0, cx + wx - half), max(x1, cx + wx + half)
                z0, z1 = min(z0, cz + wz - half), max(z1, cz + wz + half)
        boxes.append((x0 - reach, z0 - reach, x1 + reach, z1 + reach))
    return boxes


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


# ── 쓰기 ────────────────────────────────────────────────────────────────

def _utf(s):
    b = s.encode("utf-8")
    return struct.pack(">H", len(b)) + b


def encode(worlds, rect):
    """worlds = [(build_ids, {(x, z): col | None})]. rect = (x0, z0, x1, z1)."""
    x0, z0, x1, z1 = rect
    sx, sz = x1 - x0 + 1, z1 - z0 + 1
    out = io.BytesIO()
    out.write(MAGIC)
    out.write(struct.pack(">i", VERSION))
    out.write(struct.pack(">q", signed64(fnv(nature_signature().encode("utf-8")))))
    out.write(struct.pack(">q", signed64(column_hash(PROBE))))
    out.write(struct.pack(">ii", UNDER, ABOVE))
    out.write(struct.pack(">i", len(worlds)))
    for ids, cols in worlds:
        out.write(struct.pack(">i", len(ids)))
        for i in ids:
            out.write(_utf(i))
        out.write(struct.pack(">iiii", x0, z0, sx, sz))
        for z in range(z0, z1 + 1):
            for x in range(x0, x1 + 1):
                c = cols.get((x, z))
                if c is None:
                    out.write(struct.pack(">h", -32768))
                    continue
                h, hs, under, logs = c
                out.write(struct.pack(">hqhB", h, signed64(hs), under, len(logs)))
                out.write(bytes(logs))
    raw = out.getvalue()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(raw)
    return buf.getvalue()


def default_worlds():
    dist = os.path.join(ROOT, "dist")
    cands = [os.path.join(dist, "world.zip"), os.path.join(dist, "Labyrinth-Server-0.2.0.zip")]
    # 작업 나무(worktree)에는 dist 가 없을 수 있다 — 저장소 본체의 dist 도 찾아본다
    main_dist = os.path.normpath(os.path.join(ROOT, "..", "..", "nai-cg-maker", "labyrinth", "dist"))
    cands += [os.path.join(main_dist, "world.zip"), os.path.join(main_dist, "Labyrinth-Server-0.2.0.zip")]
    seen, out = set(), []
    for c in cands:
        if os.path.isfile(c) and os.path.basename(c) not in seen:
            seen.add(os.path.basename(c))
            out.append(c)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="배포 월드 지문 → village/districts/<id>.fp")
    ap.add_argument("--district", default="mine")
    ap.add_argument("--world", action="append", default=[], help="world.zip · 서버팩 zip · world 폴더 (여러 번)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true", help="다시 만들어 지금 파일과 같은지만 본다")
    a = ap.parse_args(argv)
    with open(os.path.join(RES, "districts", a.district + ".json"), encoding="utf-8") as f:
        district = json.load(f)
    out = a.out or os.path.join(RES, "districts", district.get("fingerprint", a.district + ".fp"))
    paths = a.world or default_worlds()
    if not paths:
        raise SystemExit("배포 월드가 없습니다 (--world)")
    boxes = coverage(district)
    rect = union(boxes)
    print("덮는 범위: x %d..%d · z %d..%d (%d열) — 자리 %s" % (rect[0], rect[2], rect[1], rect[3],
          (rect[2] - rect[0] + 1) * (rect[3] - rect[1] + 1), ", ".join("%s %s" % (s["id"], b) for s, b in zip(district["sites"], boxes))))
    worlds = []
    for p in paths:
        w = World(p)
        cols = {}
        miss = 0
        for z in range(rect[1], rect[3] + 1):
            for x in range(rect[0], rect[2] + 1):
                c = w.column(x, z)
                if c is None:
                    miss += 1
                cols[(x, z)] = c
        print("  %s — build_id %s · 열 %d · 청크 없음 %d" % (os.path.basename(p), w.build_id or "?", len(cols), miss))
        worlds.append((w.build_id, cols))
    # 두 월드 맞대기
    merged = []
    for bid, cols in worlds:
        for m in merged:
            diff = [k for k in cols if cols[k] != m[1].get(k)]
            if not diff:
                if bid and bid not in m[0]:
                    m[0].append(bid)
                print("  %s: 지문이 %s 와 열 단위로 같음 (지문 하나로 씀)" % (bid, m[0][0]))
                break
            print("  %s: %s 와 다른 열 %d (예 %s) — 따로 씀" % (bid, m[0][0], len(diff), sorted(diff)[:3]))
        else:
            merged.append(([bid] if bid else [], cols))
    for bid in district["shipped"].get("build_ids", []):
        if not any(bid in m[0] for m in merged):
            print("  경고: 배포 월드 build_id %s 의 지문이 없음 (그 월드가 --world 에 없음)" % bid)
    data = encode(merged, rect)
    if a.check:
        old = open(out, "rb").read() if os.path.isfile(out) else b""
        if gzip.decompress(old) != gzip.decompress(data) if old else True:
            print("지문이 다릅니다 — tools/village/district_fingerprint.py 로 다시 만드세요 (%s)" % out)
            return 1
        print("지문 같음: %s" % os.path.relpath(out, ROOT))
        return 0
    with open(out, "wb") as f:
        f.write(data)
    print("씀: %s (%d바이트, 지문 %d개)" % (os.path.relpath(out, ROOT), len(data), len(merged)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
