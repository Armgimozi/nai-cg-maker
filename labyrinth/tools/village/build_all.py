#!/usr/bin/env python3
"""build_all.py — 모든 조각 + layout → plugin/src/main/resources/village/ (VILLAGE.md §1, §6.1).

    /opt/packvenv/bin/python tools/village/build_all.py            # 생성 + 검증
    /opt/packvenv/bin/python tools/village/build_all.py --render   # + /tmp/village_renders/ 에 PNG
    /opt/packvenv/bin/python tools/village/build_all.py --render --rotations --only forge,inn

- tools/village/pieces_*.py 를 모두 불러 각 모듈의 PIECES(인자 없는 함수 목록, Piece 반환)를 실행 → finalize·검증 →
  pieces/<id>.json. PIECES 에 없는 남은 json 은 지운다.
- tools/village/layout.py 의 LAYOUT → layout.json. 조각 id·발자국 겹침(1칸 여유)·반경·길·정문 앞·마커(spawn/entrance 1개씩,
  npc id 가 npcs.yml 에 있음)를 검사한다.
- tools/village/district_*.py 의 DISTRICT (0.3.6 광산 마을 …) → districts/<id>.json. 배포 월드 좌표로 쓴 배치를 마을 좌표로 바꾸고,
  자리(sites)마다 Java 계획기와 같은 규칙(조각 1칸 여유·정문 앞·붙지 않은 길)으로 겹침을 본다. 구역 조각은 광산 블록 12종·빈 광맥
  블록을 쓰지 않고 구리는 waxed_* 만 (CONTRACT §3.3, visual.json).
- 오류가 하나라도 있으면 아무것도 쓰지 않고 이유를 출력하고 끝 (종료 코드 1).
"""
import argparse
import glob
import importlib.util
import json
import math
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import vlib  # noqa: E402

RES = os.path.join(ROOT, "plugin", "src", "main", "resources", "village")
PIECES_DIR = os.path.join(RES, "pieces")
DISTRICT_DIR = os.path.join(RES, "districts")
VISUAL_JSON = os.path.join(ROOT, "tools", "data", "036", "visual.json")
NPCS_YML = os.path.join(ROOT, "plugin", "src", "main", "resources", "content", "npcs.yml")
RENDER_DIR = "/tmp/village_renders"
VILLAGE_NPCS = ("guide", "blacksmith", "class_master", "title_keeper", "merchant")


def load_piece_modules(errors):
    mods = []
    for path in sorted(glob.glob(os.path.join(HERE, "pieces_*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:  # noqa: BLE001 — 설계 파일 오류는 이유를 보여 주고 계속 모은다
            errors.append("%s 불러오기 실패: %s\n%s" % (name, e, traceback.format_exc(limit=3)))
            continue
        if not isinstance(getattr(mod, "PIECES", None), (list, tuple)):
            errors.append("%s: PIECES 리스트가 없습니다" % name)
            continue
        mods.append((name, mod))
    return mods


def build_pieces(mods, errors):
    pieces = {}
    for name, mod in mods:
        for fn in mod.PIECES:
            label = "%s.%s" % (name, getattr(fn, "__name__", fn))
            try:
                p = fn()
                if not isinstance(p, vlib.Piece):
                    errors.append("%s: Piece 를 돌려주지 않았습니다 (%r)" % (label, type(p)))
                    continue
                p.finalize()
            except vlib.VillageError as e:
                errors.append("%s: %s" % (label, e))
                continue
            except Exception as e:  # noqa: BLE001
                errors.append("%s: 예외 %s\n%s" % (label, e, traceback.format_exc(limit=4)))
                continue
            if p.id in pieces:
                errors.append("조각 id '%s' 가 두 번 (%s, %s)" % (p.id, pieces[p.id][1], label))
                continue
            p.origin = name
            pieces[p.id] = (p, label)
    return {k: v[0] for k, v in pieces.items()}


def read_npcs(path):
    """npcs.yml 간단 파싱 → {id: placement}."""
    out, cur = {}, None
    in_npcs = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if re.match(r"^npcs:\s*$", line):
                in_npcs = True
                continue
            if not in_npcs:
                continue
            if re.match(r"^\S", line) and not line.startswith("#"):
                break
            m = re.match(r"^  ([a-z0-9_]+):\s*(#.*)?$", line)
            if m:
                cur = m.group(1)
                out[cur] = None
                continue
            m = re.match(r"^    placement:\s*([a-z_]+)", line)
            if m and cur:
                out[cur] = m.group(1)
    return out


def _box(e, p):
    r = vlib.front_rotation(e.get("front", "north"))
    w, d = vlib.rotated_size(p.W, p.D, r)
    ax, az = e["at"]
    x0, z0 = ax - w // 2, az - d // 2
    return r, (x0, z0, x0 + w - 1, z0 + d - 1)


def _ring(cells):
    """칸들 + 둘레 1칸 (8방향)."""
    return {(x + dx, z + dz) for (x, z) in cells for dx in (-1, 0, 1) for dz in (-1, 0, 1)}


def _attach(placed, end):
    """길 끝 → 붙은 조각 순번 (Java Planner.attach: 체비셰프 거리 ≤ 2, 가까운 것, 같으면 장식 아닌 것).
    abut 조각(0.3.7 집 구역 울타리 줄·집터·노점)에는 길이 붙지 않는다 — 길 높이는 길이 정한다."""
    best, best_score = None, None
    for i, (tag, e, p, bp, r, b, cols) in enumerate(placed):
        if getattr(bp, "abut", False):
            continue
        d = min(max(abs(x - end[0]), abs(z - end[1])) for (x, z) in cols) if cols else 10 ** 9
        score = d * 2 + (1 if bp.deco else 0)
        if d <= vlib.PATH_ATTACH and (best_score is None or score < best_score):
            best, best_score = i, score
    return best


def validate_layout(L, pieces, npcs, errors, warnings):
    bps = {pid: vlib.Blueprint.of(p) for pid, p in pieces.items()}
    if L.get("format") != 1:
        errors.append("layout: format 은 1")
    if not isinstance(L.get("name"), str) or not L["name"]:
        errors.append("layout: name 이 없음")
    R = L.get("radius")
    if not isinstance(R, int) or R <= 0:
        errors.append("layout: radius 는 양의 정수")
        R = 32
    styles = L.get("path_styles", {})
    for sname, mixl in styles.items():
        for item in mixl:
            try:
                b, w = item
                vlib.check_block(b)
                bid = vlib.parse_block(b)[0]
                if not (vlib.is_full(bid) or bid in ("dirt_path", "farmland")):
                    errors.append("path_styles.%s: %s 는 꽉 찬 블록이 아님 (길 맨 윗블록 자리)" % (sname, b))
                if not isinstance(w, int) or w <= 0:
                    errors.append("path_styles.%s: 무게는 양의 정수 (%r)" % (sname, item))
            except (ValueError, TypeError):
                errors.append("path_styles.%s: [블록, 무게] 형식이 아님: %r" % (sname, item))
            except vlib.VillageError as e:
                errors.append("path_styles.%s: %s" % (sname, e))

    placed = []          # (tag, 항목, Piece, Blueprint, 회전, 발자국 상자, 차지한 월드 기둥)
    for i, e in enumerate(L.get("pieces", [])):
        pid = e.get("piece")
        tag = "pieces[%d] %s" % (i, pid)
        if pid not in pieces:
            errors.append("%s: 그런 조각이 없음 (있는 것: %s)" % (tag, ", ".join(sorted(pieces))))
            continue
        if e.get("front", "north") not in vlib.DIRS:
            errors.append("%s: front 는 north/east/south/west" % tag)
            continue
        if not (isinstance(e.get("at"), list) and len(e["at"]) == 2 and all(isinstance(v, int) for v in e["at"])):
            errors.append("%s: at 은 [x, z] 정수" % tag)
            continue
        if "dy" in e and (not isinstance(e["dy"], int) or abs(e["dy"]) > 6):
            errors.append("%s: dy 는 −6..6 정수 (§0: 광장 높이 ±6)" % tag)
        if "slack" in e and (not isinstance(e["slack"], int) or not 0 <= e["slack"] <= 6):
            errors.append("%s: slack 은 0..6 정수" % tag)
        p = pieces[pid]
        bp = bps[pid]
        r, b = _box(e, p)
        cols = bp.world_columns(r, b[0], b[1])
        placed.append((tag, e, p, bp, r, b, cols))
        far = max(math.hypot(x, z) for (x, z) in cols) if cols else 0
        if far > R:
            errors.append("%s: 발자국 (%d,%d)-(%d,%d) 이 반경 %d 밖까지 (%.1f)" % (tag, b[0], b[1], b[2], b[3], R, far))
    # 조각끼리: 차지한 기둥 + 둘레 1칸이 다른 조각 기둥과 겹치면 안 됨 (Java Planner.overlaps)
    for i in range(len(placed)):
        ta, ring_a = placed[i][0], _ring(placed[i][6])
        for j in range(i + 1, len(placed)):
            tb, cols_b = placed[j][0], placed[j][6]
            hit = ring_a & cols_b
            if hit:
                kind = "겹침" if placed[i][6] & cols_b else "1칸 여유 없음"
                errors.append("%s 와 %s %s (예: %s)" % (ta, tb, kind, sorted(hit)[0]))
    # 정문 앞 칸이 다른 조각·그 둘레에 막히지 않음 (장식·door=false 제외)
    for tag, e, p, bp, r, b, cols in placed:
        if not bp.door:
            continue
        ax, az = p.anchor
        rx, rz = vlib.rot_xz(ax, az, p.W, p.D, r)
        wx, wz = b[0] + rx, b[1] + rz
        dx, dz = vlib.DXZ[vlib.rot_dir("north", r)]
        while b[0] <= wx <= b[2] and b[1] <= wz <= b[3]:
            wx, wz = wx + dx, wz + dz
        for t2, _, _, _, _, _, cols2 in placed:
            if t2 != tag and (wx, wz) in _ring(cols2):
                errors.append("%s: 정문 앞 칸 (%d,%d) 이 %s 에 막힘" % (tag, wx, wz, t2))
    # 단
    for i, t in enumerate(L.get("terraces", [])):
        try:
            (tx, tz), (tw, td), dy = t["at"], t["size"], t["dy"]
        except (KeyError, ValueError, TypeError):
            errors.append("terraces[%d]: {at:[x,z], size:[w,d], dy:n}" % i)
            continue
        if abs(dy) > 6:
            errors.append("terraces[%d]: dy 는 −6..6" % i)
        far = max(math.hypot(x, z) for x in (tx - tw // 2, tx - tw // 2 + tw - 1) for z in (tz - td // 2, tz - td // 2 + td - 1))
        if far > R:
            errors.append("terraces[%d]: 반경 %d 밖" % (i, R))
    # 길: 붙은 조각(끝점이 2칸 안)이 아닌 조각과는 1칸 여유 (Java Planner.overlaps)
    for i, pth in enumerate(L.get("paths", [])):
        pts = pth.get("points", [])
        tag = "paths[%d]" % i
        if len(pts) < 2 or not all(isinstance(q, list) and len(q) == 2 and all(isinstance(v, int) for v in q) for q in pts):
            errors.append("%s: points 는 [[x,z], ...] 정수 두 점 이상" % tag)
            continue
        wdt = pth.get("width", 3)
        if not isinstance(wdt, int) or not 1 <= wdt <= 7:
            errors.append("%s: width 는 1..7" % tag)
            continue
        if pth.get("style", "main") not in styles:
            errors.append("%s: style '%s' 가 path_styles 에 없음" % (tag, pth.get("style")))
        att = {_attach(placed, pts[0]), _attach(placed, pts[-1])} - {None}
        cells = vlib.path_cells(pts, wdt)
        far = max(math.hypot(x + 0.5, z + 0.5) for (x, z) in cells)
        if far > R + 1:
            errors.append("%s: 반경 %d 밖까지 감 (%.1f)" % (tag, R, far))
        ring = _ring(cells)
        for k, (t2, _, _, _, _, _, cols2) in enumerate(placed):
            if k in att:
                continue
            hit = ring & cols2
            if hit:
                errors.append("%s: 길이 %s 를 지나가거나 1칸 여유 없이 붙음 (예: %s) — 끝점을 그 조각 2칸 안에 두면 붙은 길"
                              % (tag, t2, sorted(hit)[0]))
        if not att:
            warnings.append("%s: 어느 조각에도 붙지 않은 길 (끝점이 조각 2칸 안이 아님)" % tag)
    # 마커
    counts = {"spawn": 0, "entrance": 0}
    seen_npcs = {}
    for tag, e, p, bp, r, b, cols in placed:
        for m in p.markers:
            t = m["type"]
            if t in counts:
                counts[t] += 1
            if t == "npc":
                nid = m["id"]
                if nid not in npcs:
                    errors.append("%s: npc '%s' 가 npcs.yml 에 없음" % (tag, nid))
                elif npcs[nid] != "overworld":
                    errors.append("%s: npc '%s' 는 placement=%s (마을에는 overworld NPC 만)" % (tag, nid, npcs[nid]))
                if nid in seen_npcs:
                    errors.append("npc '%s' 가 %s 와 %s 에 둘 다 있음" % (nid, seen_npcs[nid], tag))
                seen_npcs[nid] = tag
    for t, n in counts.items():
        if n != 1:
            errors.append("layout 전체에 %s 마커가 정확히 1개여야 함 (지금 %d)" % (t, n))
    missing = [n for n in VILLAGE_NPCS if n not in seen_npcs]
    if missing:
        warnings.append("마을 NPC 가 아직 없음: %s (selftest npcs=5/5 기준)" % ", ".join(missing))


# ─────────────────────────────── 구역 (0.3.6 광산 마을 …) ───────────────────────────────

def load_district_modules(errors):
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, "district_*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name == "district_fingerprint":      # 지문 굽는 도구 (배치 아님)
            continue
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:  # noqa: BLE001
            errors.append("%s 불러오기 실패: %s" % (name, e))
            continue
        d = getattr(mod, "DISTRICT", None)
        if not isinstance(d, dict):
            errors.append("%s: DISTRICT dict 가 없습니다" % name)
            continue
        out.append((name, d))
    return out


def _around(x, z, t):
    """Java Rot.around: 원점 둘레 시계 방향 t 번 (CW90: (x, z) → (−z, x))."""
    t %= 4
    return [(x, z), (-z, x), (-x, -z), (z, -x)][t]


def banned_district_blocks():
    """구역 조각에 쓰면 안 되는 블록: 광산 광석·보석 블록 12종 + 층마다 빈 광맥 블록 (visual.json)."""
    with open(VISUAL_JSON, encoding="utf-8") as f:
        v = json.load(f)["blocks"]
    out = {}
    for group in ("ores", "gems"):
        for k, e in v[group].items():
            out[vlib.parse_block(e["block"])[0]] = "광산 %s 블록 (%s)" % ("광석" if group == "ores" else "보석", k)
    for lvl, b in v["depleted"].items():
        out.setdefault(vlib.parse_block(b)[0], "빈 광맥 블록 (층 %s)" % lvl)
    return out


def check_district_blocks(pid, p, banned, errors, own=True):
    """own = 구역 전용 조각 (마을 장식 조각을 빌려 쓸 때는 기초를 구역 foundation_mix 가 대신한다)."""
    for layer_i, layer in enumerate(p.g):
        for z, row in enumerate(layer):
            for x, v in enumerate(row):
                if v in (" ", "."):
                    continue
                bid = vlib.parse_block(v)[0]
                if bid in banned:
                    errors.append("구역 조각 %s (%d,%d,%d): %s 는 쓰지 않음 — %s" % (pid, x, layer_i, z, bid, banned[bid]))
                elif "copper" in bid and not bid.startswith("waxed_") and not bid.startswith("raw_copper"):
                    errors.append("구역 조각 %s (%d,%d,%d): 구리는 waxed_* 만 (%s 는 녹이 슮)" % (pid, x, layer_i, z, bid))
    if own:
        for b, _ in p.foundation_mix:
            if vlib.parse_block(b)[0] in banned:
                errors.append("구역 조각 %s: foundation_mix 의 %s 는 쓰지 않음" % (pid, b))


def site_world(D, site):
    """자리 하나의 배포 월드 배치: (조각 목록 [(순번, 항목)], 길 목록 [(순번, 항목)])."""
    sx, sz = site.get("shift", [0, 0])
    drop = set(site.get("drop", []))
    rep = {int(k): v for k, v in site.get("replace_paths", {}).items()}
    ps = [(i, dict(e, w=[e["w"][0] + sx, e["w"][1] + sz])) for i, e in enumerate(D["pieces"]) if i not in drop]
    paths = []
    for i, pth in enumerate(D["paths"]):
        pts = rep[i] if i in rep else [[q[0] + sx, q[1] + sz] for q in pth["points"]]
        paths.append((i, dict(pth, points=pts)))
    return ps, paths


def validate_site(tag, ps, paths, pieces, styles, errors, warnings):
    """Java Planner.overlaps 와 같은 규칙 (배포 월드 좌표, 마을 회전 포함 = 조각 정면 방향 그대로)."""
    placed = []
    for i, e in ps:
        pid = e["piece"]
        t = "%s pieces[%d] %s" % (tag, i, pid)
        if pid not in pieces:
            errors.append("%s: 그런 조각이 없음" % t)
            continue
        p = pieces[pid]
        bp = vlib.Blueprint.of(p)
        r = vlib.front_rotation(e["front"])
        w2, d2 = vlib.rotated_size(p.W, p.D, r)
        x0, z0 = e["w"]
        b = (x0, z0, x0 + w2 - 1, z0 + d2 - 1)
        placed.append((t, e, p, bp, r, b, bp.world_columns(r, x0, z0)))
    for i in range(len(placed)):
        ta, ring_a = placed[i][0], _ring(placed[i][6])
        for j in range(i + 1, len(placed)):
            tb, cols_b = placed[j][0], placed[j][6]
            # abut 끼리(0.3.7 집 구역 울타리 줄·집터)는 붙어도 됨 — 겹침만 안 됨 (Java Planner.overlaps 와 같게)
            both = placed[i][3].abut and placed[j][3].abut
            hit = (placed[i][6] & cols_b) if both else (ring_a & cols_b)
            if hit:
                errors.append("%s 와 %s %s (예: %s)" % (ta, tb, "겹침" if placed[i][6] & cols_b else "1칸 여유 없음", sorted(hit)[0]))
    for t, e, p, bp, r, b, cols in placed:
        if not bp.door:
            continue
        ax, az = p.anchor
        rx, rz = vlib.rot_xz(ax, az, p.W, p.D, r)
        wx, wz = b[0] + rx, b[1] + rz
        dx, dz = vlib.DXZ[vlib.rot_dir("north", r)]
        while (wx, wz) in cols:
            wx, wz = wx + dx, wz + dz
        for t2, _, _, bp2, _, _, cols2 in placed:
            if t2 == t:
                continue
            near = (wx, wz) in cols2 if (bp.abut and bp2.abut) else (wx, wz) in _ring(cols2)
            if near:
                errors.append("%s: 정문 앞 칸 (%d,%d) 이 %s 에 막힘" % (t, wx, wz, t2))
    for i, pth in paths:
        pts, wdt = pth["points"], pth.get("width", 3)
        if pth.get("style", "main") not in styles:
            errors.append("%s paths[%d]: style '%s' 없음" % (tag, i, pth.get("style")))
        att = {_attach(placed, pts[0]), _attach(placed, pts[-1])} - {None}
        cells = vlib.path_cells(pts, wdt)
        ring = _ring(cells)
        for k, (t2, _, _, bp2, _, _, cols2) in enumerate(placed):
            if k in att:
                continue
            hit = (cells & cols2) if bp2.abut else (ring & cols2)
            if hit:
                errors.append("%s paths[%d]: 길이 %s 를 지나가거나 1칸 여유 없이 붙음 (예: %s)" % (tag, i, t2, sorted(hit)[0]))
    return placed


def district_json(D, pieces):
    """배포 월드 좌표 → 마을 좌표 (layout.json 과 같은 틀). Java DistrictLayout 이 읽는다."""
    cx, cz = D["shipped"]["center"]
    t = D["shipped"]["turns"]

    def to_v(x, z):
        return list(_around(x - cx, z - cz, -t))

    out_p = []
    for e in D["pieces"]:
        p = pieces[e["piece"]]
        rw = vlib.front_rotation(e["front"])
        w2, d2 = vlib.rotated_size(p.W, p.D, rw)
        x0, z0 = e["w"]
        a, b = to_v(x0, z0), to_v(x0 + w2 - 1, z0 + d2 - 1)
        vx0, vz0 = min(a[0], b[0]), min(a[1], b[1])
        fv = vlib.DIRS[(vlib.DIRS.index(vlib.norm_dir(e["front"])) - t) % 4]
        vw, vd = vlib.rotated_size(p.W, p.D, vlib.front_rotation(fv))
        assert (abs(a[0] - b[0]) + 1, abs(a[1] - b[1]) + 1) == (vw, vd), (e, a, b, vw, vd)
        q = {"piece": e["piece"], "at": [vx0 + vw // 2, vz0 + vd // 2], "front": fv}
        # 0.3.7: max_fill (조각별 깎기·메우기 한도) · floor_ref (그 조각들 바닥 중 가장 높은 것) · floor_near [조각, 차] · tag (집터 번호)
        for k in ("dy", "slack", "max_fill", "floor_ref", "floor_near", "tag"):
            if k in e:
                q[k] = e[k]
        out_p.append(q)
    out_paths = [dict({"points": [to_v(*q) for q in pth["points"]], "width": pth.get("width", 3), "style": pth.get("style", "main")},
                      **({"follow": pth["follow"]} if "follow" in pth else {}))
                 for pth in D["paths"]]
    sites = []
    for s in D["sites"]:
        sx, sz = s.get("shift", [0, 0])
        q = {"id": s["id"], "shift": list(_around(sx, sz, -t))}
        if s.get("replace_paths"):
            q["replace_paths"] = {k: [to_v(*pt) for pt in v] for k, v in s["replace_paths"].items()}
        if s.get("drop"):
            q["drop"] = list(s["drop"])
        sites.append(q)
    keep = {k: D[k] for k in ("format", "id", "name", "order", "mask", "options", "safe_margin", "foundation_mix", "npcs",
                              "fingerprint") if k in D}
    keep["frame"] = "village"
    keep["note"] = "build_all.py 생성물 (tools/village/district_%s.py) — 직접 고치지 마세요. 좌표 = 마을 좌표 (layout.json 과 같은 틀)" % D["id"]
    keep["shipped"] = D["shipped"]
    keep["path_styles"] = D.get("path_styles", {})
    keep["pieces"] = out_p
    keep["paths"] = out_paths
    keep["sites"] = sites
    return keep


def validate_districts(districts, pieces, layout, npcs, errors, warnings):
    banned = banned_district_blocks()
    styles = dict(layout.get("path_styles", {})) if layout else {}
    out = {}
    for name, D in districts:
        did = D.get("id")
        if not did or not re.match(r"^[a-z0-9_]+$", did):
            errors.append("%s: id 는 소문자·숫자·_" % name)
            continue
        st = dict(styles)
        st.update(D.get("path_styles", {}))
        for sname, mixl in D.get("path_styles", {}).items():
            for b, w in mixl:
                vlib.check_block(b)
                if vlib.parse_block(b)[0] in banned:
                    errors.append("구역 %s path_styles.%s: %s 는 쓰지 않음" % (did, sname, b))
        used = sorted({e["piece"] for e in D["pieces"]})
        own_ids = {pid for pid in used if getattr(pieces.get(pid), "origin", "") == "pieces_" + did}
        for b, w in D.get("foundation_mix", []):
            vlib.check_block(b)
            if vlib.parse_block(b)[0] in banned:
                errors.append("구역 %s foundation_mix: %s 는 쓰지 않음" % (did, b))
        for pid in used:
            if pid not in pieces:
                errors.append("구역 %s: 조각 %s 가 없음" % (did, pid))
                continue
            check_district_blocks(pid, pieces[pid], banned, errors, own=pid in own_ids)
            for m in pieces[pid].markers:
                if m["type"] == "npc" and m["id"] not in npcs:
                    warnings.append("구역 %s: npc '%s' 가 아직 npcs.yml 에 없음 (Q3 가 넣음 — 없으면 그 NPC 만 안 섬)" % (did, m["id"]))
        # 0.3.7 조각 손잡이: floor_ref·floor_near 는 앞에 놓인 조각만 (계획기가 차례대로 놓는다), max_fill 1..16, tag 글
        for i, e in enumerate(D["pieces"]):
            for r in e.get("floor_ref", []):
                if not isinstance(r, int) or not 0 <= r < i:
                    errors.append("구역 %s pieces[%d] %s: floor_ref %r 는 앞 조각 순번이어야 함" % (did, i, e["piece"], r))
            fn = e.get("floor_near")
            if fn is not None and not (isinstance(fn, list) and len(fn) == 2 and isinstance(fn[0], int) and 0 <= fn[0] < i
                                       and isinstance(fn[1], int) and 0 <= fn[1] <= 8):
                errors.append("구역 %s pieces[%d] %s: floor_near 는 [앞 조각 순번, 0..8]: %r" % (did, i, e["piece"], fn))
            mf = e.get("max_fill")
            if mf is not None and not (isinstance(mf, int) and 1 <= mf <= 16):
                errors.append("구역 %s pieces[%d] %s: max_fill 은 1..16: %r" % (did, i, e["piece"], mf))
            if "tag" in e and not (isinstance(e["tag"], str) and re.match(r"^[a-z0-9_]+$", e["tag"])):
                errors.append("구역 %s pieces[%d] %s: tag 는 소문자·숫자·_: %r" % (did, i, e["piece"], e["tag"]))
        # 집터 바닥(pad)마다 같은 tag 의 앞 울타리(대문·표지판 plot:{plot})가 하나
        pad_tags = [e.get("tag") for e in D["pieces"] if getattr(pieces.get(e["piece"]), "pad", False)]
        for t in pad_tags:
            fronts = [e for e in D["pieces"] if e.get("tag") == t and any(
                m["type"] == "interact" and m.get("action") == "plot:{plot}" for m in getattr(pieces.get(e["piece"]), "markers", []))]
            if t is None or len(fronts) != 1:
                errors.append("구역 %s: 집터 tag %r 의 앞 울타리(plot:{plot} 표지판) %d개 (1개여야 함)" % (did, t, len(fronts)))
        if len(set(pad_tags)) != len(pad_tags):
            errors.append("구역 %s: 집터 tag 가 겹침 %r" % (did, pad_tags))
        if not D.get("sites"):
            errors.append("구역 %s: sites 가 없음" % did)
        for site in D.get("sites", []):
            ps, paths = site_world(D, site)
            validate_site("구역 %s/%s" % (did, site["id"]), ps, paths, pieces, st, errors, warnings)
        if not any(e for e in errors if ("구역 " + did) in e):
            out[did] = district_json(D, pieces)
    return out


def dump_district(d):
    dump = lambda v: json.dumps(v, ensure_ascii=False)
    out = ["{"]
    keys = list(d.keys())
    for ki, k in enumerate(keys):
        v = d[k]
        comma = "," if ki < len(keys) - 1 else ""
        if isinstance(v, list) and k in ("pieces", "paths", "sites"):
            out.append("  %s: [" % dump(k))
            for i, item in enumerate(v):
                out.append("    %s%s" % (dump(item), "," if i < len(v) - 1 else ""))
            out.append("  ]%s" % comma)
        else:
            out.append("  %s: %s%s" % (dump(k), dump(v), comma))
    out.append("}")
    return "\n".join(out) + "\n"


def dump_layout(L):
    d = lambda v: json.dumps(v, ensure_ascii=False)
    out = ["{"]
    keys = [k for k in ("format", "name", "radius") if k in L]
    for k in keys:
        out.append("  %s: %s," % (d(k), d(L[k])))
    rest = [k for k in L if k not in keys]
    for ki, k in enumerate(rest):
        v = L[k]
        comma = "," if ki < len(rest) - 1 else ""
        if isinstance(v, list):
            out.append("  %s: [" % d(k))
            for i, item in enumerate(v):
                out.append("    %s%s" % (d(item), "," if i < len(v) - 1 else ""))
            out.append("  ]%s" % comma)
        elif isinstance(v, dict):
            out.append("  %s: {" % d(k))
            items = list(v.items())
            for i, (kk, vv) in enumerate(items):
                out.append("    %s: %s%s" % (d(kk), d(vv), "," if i < len(items) - 1 else ""))
            out.append("  }%s" % comma)
        else:
            out.append("  %s: %s%s" % (d(k), d(v), comma))
    out.append("}")
    return "\n".join(out) + "\n"


def render_all(pieces, L, only, rotations, views):
    import render
    os.makedirs(RENDER_DIR, exist_ok=True)
    bps = {pid: vlib.Blueprint.of(p) for pid, p in pieces.items()}
    paths = []
    for pid, bp in sorted(bps.items()):
        if only and pid not in only:
            continue
        px = max(10, min(26, int(900 / (bp.W + bp.D + 4))))
        sc = render.scene_from_blueprint(bp, 0)
        paths += render.save_views(sc, os.path.join(RENDER_DIR, pid + ".png"), views, False, px)
        if rotations:
            ims = [render.render_iso(render.scene_from_blueprint(bp, r), "ne", px) for r in range(4)]
            p = os.path.join(RENDER_DIR, pid + "_rot.png")
            render.contact_sheet(ims, ["%s (front=%s)" % (vlib.ROTATIONS[r], vlib.DIRS[r]) for r in range(4)]).save(p)
            paths.append(p)
    if L is not None and not only:
        need = {e["piece"] for e in L["pieces"]}
        sc = render.scene_from_layout(L, {k: bps[k] for k in need})
        paths += render.save_views(sc, os.path.join(RENDER_DIR, "village.png"), views, True, 10)
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description="마을 조각·layout 생성 + 검증")
    ap.add_argument("--render", action="store_true", help="조각별 PNG + 마을 전체 PNG → %s" % RENDER_DIR)
    ap.add_argument("--rotations", action="store_true", help="--render 와 함께: 조각마다 회전 4방향 한 장 (<id>_rot.png)")
    ap.add_argument("--only", default="", help="--render 할 조각 id (쉼표) — 마을 전체 렌더는 생략")
    ap.add_argument("--views", default="ne,sw")
    ap.add_argument("--check", action="store_true", help="검증만 (파일 안 씀)")
    a = ap.parse_args(argv)
    t0 = time.time()
    errors, warnings = [], []
    mods = load_piece_modules(errors)
    pieces = build_pieces(mods, errors)
    L = None
    try:
        spec = importlib.util.spec_from_file_location("layout", os.path.join(HERE, "layout.py"))
        lm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lm)
        L = dict(lm.LAYOUT)
    except Exception as e:  # noqa: BLE001
        errors.append("layout.py 불러오기 실패: %s" % e)
    npcs = read_npcs(NPCS_YML)
    if L is not None:
        validate_layout(L, pieces, npcs, errors, warnings)
    districts = validate_districts(load_district_modules(errors), pieces, L, npcs, errors, warnings)

    for w in warnings:
        print("경고:", w)
    if errors:
        print("\n오류 %d건 — 아무것도 쓰지 않았습니다:" % len(errors))
        for e in errors:
            print(" ✗", e)
        return 1

    if not a.check:
        os.makedirs(PIECES_DIR, exist_ok=True)
        for pid, p in sorted(pieces.items()):
            p.export(os.path.join(PIECES_DIR, pid + ".json"))
        removed = []
        for path in glob.glob(os.path.join(PIECES_DIR, "*.json")):
            if os.path.splitext(os.path.basename(path))[0] not in pieces:
                os.remove(path)
                removed.append(os.path.basename(path))
        with open(os.path.join(RES, "layout.json"), "w", encoding="utf-8") as f:
            f.write(dump_layout(L))
        os.makedirs(DISTRICT_DIR, exist_ok=True)
        for did, dj in sorted(districts.items()):
            with open(os.path.join(DISTRICT_DIR, did + ".json"), "w", encoding="utf-8") as f:
                f.write(dump_district(dj))
        order = sorted(districts, key=lambda k: (districts[k].get("order", 100), k))
        with open(os.path.join(DISTRICT_DIR, "index.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"note": "build_all.py 생성물 — 구역 목록 (짓는 차례)", "districts": order}, ensure_ascii=False) + "\n")
        for path in glob.glob(os.path.join(DISTRICT_DIR, "*.json")):
            base = os.path.splitext(os.path.basename(path))[0]
            if base != "index" and base not in districts:
                os.remove(path)
                print("지운 구역 JSON:", os.path.basename(path))
        if removed:
            print("지운 조각 JSON:", ", ".join(sorted(removed)))
    blocks = sum(sum(1 for layer in p.g for row in layer for v in row if v not in (" ", ".")) for p in pieces.values())
    print("조각 %d개 (%s) · 블록 %d · layout 조각 %d · 구역 %s · 경고 %d · 오류 0%s  (%.1fs)" % (
        len(pieces), ", ".join(sorted(pieces)), blocks, len(L["pieces"]), ",".join(sorted(districts)) or "-", len(warnings),
        "" if a.check else " → " + os.path.relpath(RES, ROOT), time.time() - t0))
    if a.render:
        only = {s.strip() for s in a.only.split(",") if s.strip()}
        for p in render_all(pieces, L, only, a.rotations, [v.strip() for v in a.views.split(",") if v.strip()]):
            print("렌더:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
