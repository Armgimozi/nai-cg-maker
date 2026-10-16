#!/usr/bin/env python3
"""
0.3.5 P1 — 무기 고유 효과 배정 데이터 (unique_spec §9 TASK D 결과 + review2 A12 + 주인 결정 B3).

  python3 tools/gen_035_unique.py --import <design2/unique_assign_all.json>
        설계 폴더의 배정 237개를 저장소 tools/data/035/unique_assign.json 으로 옮긴다. 옮기며 고치는 것:
          · A12  고유 효과 id shield_bash → bash_stun (직업 스킬 id 와 겹치지 않게, 툴팁 이름은 무기마다 그대로)
          · B3   보스 전설 2개(먹물 서고 지팡이 inkwell_staff · 종말시계 단두도끼 doomclock_executioner)의 강도 0.6
                 (강도 비례 수치 = 기준값 × 0.6, 툴팁 글도 다시)
  python3 tools/gen_035_unique.py --check     # 배정 파일 검사 + items.yml 에 이미 들어간 unique 블록이 파일과 같은지
  python3 tools/gen_035_unique.py --yaml ID…  # 그 무기들의 items.yml `unique:` 한 줄 (P3 생성기는 unique_block() 을 가져다 쓴다)

items.yml 에 넣는 일은 P3 생성기(tools/gen_035_content.py)가 한다 — 툴팁 줄(P6)과 함께 들어가야 보이지 않는 효과가 생기지 않는다.
닫힌 목록·수치 범위는 플러그인 content/UniqueCatalog.java 와 같다 (시험 UniqueEffectCatalogTest 가 두 쪽을 맞춰 본다).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools/data/035/unique_assign.json"
ITEMS = ROOT / "plugin/src/main/resources/content/items.yml"

RENAME = {"shield_bash": "bash_stun"}
B3 = {"inkwell_staff": 0.6, "doomclock_executioner": 0.6}

# 강도 비례 수치 (기준값, 상한) — UniqueCatalog.java 와 같음. 선제·추격·흘려치기(WG)는 pct 에 간격 보정 g 를 곱해 저장한다.
SCALED = {
    "rend": {"pct": (0.06, 0.15)},
    "hemorrhage": {"cc": (0.10, 0.22), "cd": (0.20, 0.45)},
    "leech": {"pct": (0.06, 0.14)},
    "feast": {"heal": (0.04, 0.10), "ls": (0.04, 0.10)},
    "thorns": {"pct": (0.30, 0.70)},
    "bash_stun": {"stun": (0.8, 1.5), "pct": (0.40, 0.90), "vuln": (0.06, 0.14)},
    "steadfast": {"dr": (0.08, 0.18)},
    "cleave": {"pct": (0.30, 0.70)},
    "chain_spark": {"pct": (0.45, 1.0)},
    "death_burst": {"pct": (0.80, 1.8)},
    "execute": {"pct": (0.25, 0.6)},
    "bloodrush": {"pct": (0.60, 1.4)},
    "momentum": {"as": (0.03, 0.06)},
    "flurry": {"pct": (0.70, 1.6)},
    "counterstep": {"pct": (0.30, 0.7)},
    "siphon": {"mp": (0.05, 0.12), "cdr": (0.5, 1.2)},
    "overcharge": {"pct": (1.2, 2.6)},
    "sanctify": {"pct": (0.12, 0.28)},
    "ward_aura": {"pct": (0.04, 0.09)},
    "imbue": {"pct": (0.10, 0.22)},
    "exploit": {"pct": (0.15, 0.35)},
    "first_strike": {"pct": (0.80, 1.8)},
    "backstab": {"pct": (0.25, 0.6)},
    "longshot": {"pct": (0.20, 0.45)},
    "berserk": {"pct": (0.025, 0.055), "ls": (0.05, 0.12)},
    "armor_break": {"pct": (0.04, 0.08)},
}
WG = {"first_strike", "bloodrush", "counterstep"}
# 저장값은 소수 둘째 자리로 반올림 — 상한 × g 같은 곱한 상한을 반올림이 0.005 까지 넘을 수 있다
ROUND_SLACK = 0.005 + 1e-9
SECS = {"cdr", "stun"}


def nice(k, v):
    """설계 도구(ue_catalog.nice)와 같은 반올림: 초 단위 소수 한 자리, 0.1 이상 소수 둘째, 그 밖 0.5% 단위."""
    if k in SECS:
        return round(v, 1)
    if v >= 0.1:
        return round(v, 2)
    return round(round(v * 200) / 200, 3)


def pc(v):
    return f"{round(v * 100, 1):g}%"


def tooltip(eid, p):
    """B3 로 수치가 바뀐 두 효과의 설명 줄 (설계 도구 ud_assign.desc 와 같은 글)."""
    if eid == "death_burst":
        return f"처치한 적이 터져 {p['radius']:g}칸 안 적에게 스킬 위력 {pc(p['pct'])}"
    if eid == "execute":
        return f"HP {pc(p['thr'])} 이하 적에게 피해 +{pc(p['pct'])} (보스는 60%만)"
    raise KeyError(eid)


def folded(eid, name, p):
    if eid == "death_burst":
        return f"✧ {name} 처치 폭발 위력 {pc(p['pct'])}"
    if eid == "execute":
        return f"✧ {name} 빈사 적 +{pc(p['pct'])}"
    raise KeyError(eid)


def weaken(entry, s):
    """강도를 s 로 낮춘다 (강도 비례 수치 = 기준값 × s × 획득처 보정 [× g]). 고정·정수 수치는 그대로."""
    eid = entry["effect"]
    p = dict(entry["params"])
    g = entry.get("interval_factor_g", 1.0) if eid in WG else 1.0
    f = entry.get("source_factor", 1.0)
    for k, (ref, mx) in SCALED[eid].items():
        if k in p:
            p[k] = nice(k, min(ref * s, mx) * f * (g if k == "pct" else 1.0))
    e = dict(entry)
    e["before_b3"] = {"params": entry["params"], "strength": entry["strength"], "tooltip": entry.get("tooltip")}
    e["params"] = p
    e["strength"] = s
    e["budget"] = round(s / 10, 3)
    e["owner_decision"] = "B3: 보스 전설이 그 띠에서 늘 이기지 않게 고유 효과 강도 0.6"
    if eid in ("death_burst", "execute"):
        head = entry["tooltip"][0] if entry.get("tooltip") else f"✧ 고유 {entry['name']}"
        e["tooltip"] = [head, "  " + tooltip(eid, p)]
        e["tooltip_folded"] = folded(eid, entry["name"], p)
    return e


def do_import(src):
    d = json.loads(Path(src).read_text(encoding="utf-8"))
    out = {}
    for wid, e in d.items():
        e = dict(e)
        if e["effect"] in RENAME:
            e["effect_before_a12"] = e["effect"]
            e["effect"] = RENAME[e["effect"]]
        if wid in B3:
            e = weaken(e, B3[wid])
        out[wid] = e
    meta = {
        "_meta": {
            "source": "design2/unique_assign_all.json (unique_spec §9, TASK D)",
            "changes": ["A12: shield_bash → bash_stun", "B3: inkwell_staff · doomclock_executioner 강도 0.6"],
            "weapons": len(out),
            "note": "items.yml 의 unique 블록은 P3 생성기가 이 파일에서 넣는다 (unique_block)",
        }
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({**meta, **out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"썼음: {DATA.relative_to(ROOT)} — 무기 {len(out)}개 (bash_stun {sum(1 for e in out.values() if e['effect'] == 'bash_stun')}, B3 {len(B3)})")


P3 = ROOT / "tools/data/035/content_p3.json"


def load():
    """배정 파일 → {무기 id: 항목} (_meta 뺌)."""
    d = json.loads(DATA.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}


def p3_blocks():
    """0.3.5 P3 가 바꾸거나 새로 넣은 무기의 unique 블록 (content_p3.json — B1 고침 · 31–35 승격 · B2 새 무기 · 활로 바뀐 7개)
    와 없어진 무기 id."""
    if not P3.exists():
        return {}, set()
    d = json.loads(P3.read_text(encoding="utf-8"))
    out = {wid: w["unique"] for wid, w in (d.get("weapons") or {}).items() if "unique" in w}
    out.update({wid: p["unique"] for wid, p in (d.get("existing_patch") or {}).items() if "unique" in p})
    return out, set(d.get("remove_weapons") or {})


def unique_block(entry):
    """items.yml 의 unique 블록 (dict): {id, name, 수치…}."""
    b = {"id": entry["effect"], "name": entry["name"]}
    b.update(entry["params"])
    return b


def flow(b):
    def v(x):
        if isinstance(x, str):
            return json.dumps(x, ensure_ascii=False)
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return str(x)
    return "{" + ", ".join(f"{k}: {v(x)}" for k, x in b.items()) + "}"


def check():
    data = load()
    bad = 0
    for wid, e in data.items():
        eid = e["effect"]
        if eid not in SCALED:
            print(f"✗ {wid}: 닫힌 목록에 없는 효과 {eid}")
            bad += 1
            continue
        for k, (ref, mx) in SCALED[eid].items():
            v = e["params"].get(k)
            if v is None:
                continue
            hi = mx * (e.get("interval_factor_g", 1.0) if eid in WG and k == "pct" else 1.0)
            if eid == "bash_stun" and k == "pct":
                hi *= e["params"].get("n", 4) / 4
            if v > hi + ROUND_SLACK:
                print(f"✗ {wid}: {eid}.{k} = {v} > 상한 {hi:.3f}")
                bad += 1
    try:
        import yaml
    except ImportError:
        print("(yaml 없음 — items.yml 비교 건너뜀)")
        return bad
    items = yaml.safe_load(ITEMS.read_text(encoding="utf-8"))["items"]
    have = {k: v["unique"] for k, v in items.items() if v.get("type") == "weapon" and "unique" in v}
    if not have:
        print(f"items.yml 에는 아직 unique 블록 없음 (P3 에서 넣음) — 배정 {len(data)}개 검사 {'통과' if not bad else '실패'}")
    p3, removed = p3_blocks()
    for wid, b in have.items():
        want = p3[wid] if wid in p3 else unique_block(data[wid]) if wid in data else None
        if want != b:
            print(f"✗ items.{wid}.unique 가 배정 파일과 다름: {b} ≠ {want}")
            bad += 1
    gone = [k for k in data if k not in items and k not in removed]
    if gone and have:
        print(f"✗ 배정 파일에는 있는데 items.yml 에 없는 무기 {len(gone)}개: {', '.join(gone[:10])}")
        bad += len(gone)
    missing = [k for k, v in items.items() if v.get("type") == "weapon" and k not in data and k not in p3]
    if missing:
        print(f"✗ 배정 파일에 없는 무기 {len(missing)}개: {', '.join(missing[:10])}")
        bad += len(missing)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--import", dest="src", help="설계 폴더의 unique_assign_all.json")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--yaml", nargs="*", metavar="ID")
    a = ap.parse_args()
    if a.src:
        do_import(a.src)
    if a.yaml is not None:
        data = load()
        for wid in a.yaml or sorted(data):
            print(f"  {wid}:\n    unique: {flow(unique_block(data[wid]))}")
    if a.check or (not a.src and a.yaml is None):
        sys.exit(1 if check() else 0)


if __name__ == "__main__":
    main()
