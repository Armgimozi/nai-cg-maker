#!/usr/bin/env python3
"""
0.3.5 P0b — 무기 종류 없애기: items.yml 의 기존 무기 131개를 combat_spec JSON 으로 옮긴다.

  python3 tools/gen_035_attack.py            # content/items.yml 을 고쳐 씀 (이미 옮긴 무기는 건드리지 않음)
  python3 tools/gen_035_attack.py --check    # 쓰지 않고 검사만 — 옮길 무기가 없고 값이 명세와 같으면 종료 코드 0
  python3 tools/gen_035_attack.py --dry-run  # 무엇이 바뀌는지만 출력

입력 = tools/data/035/combat_spec.json (설계 combat_spec.json 사본, `weapons.<id>` 의 src: existing 131개).
무기마다 (아직 `weapon_type:` 줄이 있는 무기만 — 한 번만 옮긴다):
  1) `weapon_type: X` 줄 → `attack: {style, interval, kind}` (combat_spec `items_yml.attack`)
  2) `stats.damage` → 새 한 방 피해 범위 (`per_hit`). 옛 범위가 명세의 `old_damage` 와 다르면 멈춘다(손으로 고친 값을 덮지 않게).
  3) 무기 스킬 피해 숫자 × `weapon_skill_factor` (combat_spec §5.5)
       곱함: params 의 damage · *_damage(counter_damage …) · riposte per_block,
             mechanics 효과 damage · execute.amount/boss_amount · lightning · explosion 의 숫자
       안 곱함: percent(최대 HP 비율) · heal · shield · absorption · 상태이상 potency · buff 안의 값
줄 단위로 고쳐 쓰므로 주석·순서·흐름 표기는 그대로 남는다. 다 쓰고 나서 YAML 을 다시 읽어 의미가 기대와 같은지 확인한다.
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "plugin/src/main/resources/content/items.yml"
SPEC = ROOT / "tools/data/035/combat_spec.json"

# 위에 적은 '곱함' 규칙 (params 맨 위 키만 — buff·ally_buff 안의 damage 는 버프 수치라 건드리지 않는다)
PARAM_DAMAGE_KEYS = {"damage", "counter_damage", "per_block", "end_damage", "burst_damage", "launch_damage",
                     "echo_damage", "explode_damage", "trail_dps"}
EFFECT_DAMAGE = {"damage": 1.0, "lightning": 0.0, "explosion": 0.0, "execute": 2.0}  # 효과 → 코드 기본 amount
ITEM_RE = re.compile(r"^  ([a-z0-9_]+):\s*(#.*)?$")
JSON_LINE_RE = re.compile(r"^(\s+)(params: |- )(\{.*\})\s*$")


def num(v):
    """배율 반올림 (소수 셋째 자리)."""
    r = round(v, 3)
    return int(r) if r == int(r) and isinstance(v, int) else r


def scale_params(p, f):
    out = dict(p)
    for k, v in p.items():
        if k in PARAM_DAMAGE_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = num(v * f)
    return out


def effect_type(e):
    if "type" in e:
        return str(e["type"]).lower(), None
    for k in e:
        return k, k
    return None, None


def scale_effect(e, f):
    t, key = effect_type(e)
    if t not in EFFECT_DAMAGE:
        return e
    e = dict(e)
    if key is None:  # {"type": "damage", "amount": 1.2, ...}
        e["amount"] = num(float(e.get("amount", EFFECT_DAMAGE[t])) * f)
        if "boss_amount" in e:
            e["boss_amount"] = num(float(e["boss_amount"]) * f)
        return e
    v = e[key]
    if isinstance(v, dict):
        v = dict(v)
        if "amount" in v or EFFECT_DAMAGE[t] > 0:
            v["amount"] = num(float(v.get("amount", EFFECT_DAMAGE[t])) * f)
        if "boss_amount" in v:
            v["boss_amount"] = num(float(v["boss_amount"]) * f)
        e[key] = v
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        e[key] = num(v * f)
    if "boss_amount" in e and isinstance(e["boss_amount"], (int, float)):
        e["boss_amount"] = num(e["boss_amount"] * f)
    return e


def scale_mechanics(node, f):
    """부품 트리를 돌며 effects 의 피해 숫자만 곱한다 (ally_effects 는 아군 — 피해 없음)."""
    if isinstance(node, list):
        return [scale_mechanics(x, f) for x in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k == "effects" and isinstance(v, list):
            out[k] = [scale_effect(e, f) if isinstance(e, dict) else e for e in v]
        elif isinstance(v, (dict, list)) and k != "ally_effects":
            out[k] = scale_mechanics(v, f)
        else:
            out[k] = v
    return out


def scale_skill(s, f):
    """YAML 로 읽은 무기 스킬 하나의 기대값 (검사용)."""
    s = copy.deepcopy(s)
    if isinstance(s.get("params"), dict):
        s["params"] = scale_params(s["params"], f)
    if s.get("mechanics") is not None:
        s["mechanics"] = scale_mechanics(s["mechanics"], f)
    return s


def flow(attack):
    return f"{{style: {attack['style']}, interval: {attack['interval']}, kind: {attack['kind']}}}"


def blocks(lines):
    """items: 아래 아이템 블록 (id, 시작 줄, 끝 줄 다음)."""
    out = []
    in_items = False
    cur = None
    for i, l in enumerate(lines):
        if re.match(r"^items:\s*$", l):
            in_items = True
            continue
        if in_items and re.match(r"^[^\s#]", l):  # 다음 최상위 키 (sets: …)
            if cur:
                out.append((cur[0], cur[1], i))
                cur = None
            in_items = False
            continue
        if not in_items:
            continue
        m = ITEM_RE.match(l)
        if m:
            if cur:
                out.append((cur[0], cur[1], i))
            cur = (m.group(1), i)
    if cur:
        out.append((cur[0], cur[1], len(lines)))
    return out


def transform(text, spec):
    """(새 글, 바뀐 무기 목록, 문제 목록)."""
    lines = text.split("\n")
    weapons = {k: v for k, v in spec["weapons"].items() if v.get("src") == "existing"}
    changed, problems = [], []
    seen = set()
    for wid, a, b in blocks(lines):
        if wid not in weapons:
            continue
        seen.add(wid)
        w = weapons[wid]
        attack = w["items_yml"]["attack"]
        f = w.get("weapon_skill_factor")
        wt = next((i for i in range(a, b) if re.match(r"^    weapon_type:\s*\S+", lines[i])), None)
        if wt is None:
            continue  # 이미 옮김 — 값 검사는 check() 가
        old_type = lines[wt].split(":", 1)[1].strip()
        if old_type != w["old_type"]:
            problems.append(f"{wid}: weapon_type {old_type} ≠ 명세 {w['old_type']}")
            continue
        lines[wt] = "    attack: " + flow(attack)
        st = next((i for i in range(a, b) if lines[i].startswith("    stats: {")), None)
        if st is None:
            problems.append(f"{wid}: stats 줄 없음")
            continue
        m = re.search(r"damage: \[(\d+), (\d+)\]", lines[st])
        if not m:
            problems.append(f"{wid}: stats.damage 없음")
            continue
        old = [int(m.group(1)), int(m.group(2))]
        if old != w["old_damage"]:
            problems.append(f"{wid}: 지금 damage {old} ≠ 명세 옛 범위 {w['old_damage']} (손으로 고친 값 — 그대로 둠)")
            continue
        lo, hi = w["per_hit"]
        lines[st] = lines[st][:m.start()] + f"damage: [{lo}, {hi}]" + lines[st][m.end():]
        n_scaled = 0
        if f:
            for i in range(a, b):
                jm = JSON_LINE_RE.match(lines[i])
                if not jm or '"' not in jm.group(3):
                    continue
                obj = json.loads(jm.group(3))
                if json.dumps(obj, ensure_ascii=False) != jm.group(3):
                    problems.append(f"{wid}: {i + 1}행 JSON 표기가 다시 쓰면 달라짐 — 손으로 확인")
                    continue
                if jm.group(2) == "params: ":
                    new = scale_params(obj, f)
                else:
                    new = scale_mechanics(obj, f)
                if new != obj:
                    n_scaled += 1
                    lines[i] = jm.group(1) + jm.group(2) + json.dumps(new, ensure_ascii=False)
        changed.append((wid, old, [lo, hi], attack, f, n_scaled))
    for wid in sorted(set(weapons) - seen):
        problems.append(f"{wid}: items.yml 에 없음")
    return "\n".join(lines), changed, problems


def verify(before_text, after_text, spec):
    """다시 읽은 YAML 이 기대(옛 값 → 규칙 적용)와 같은가."""
    old = yaml.safe_load(before_text)["items"]
    new = yaml.safe_load(after_text)["items"]
    problems = []
    if set(old) != set(new):
        problems.append("아이템 목록이 바뀜")
    for wid, w in spec["weapons"].items():
        if w.get("src") != "existing" or wid not in old:
            continue
        o, n = old[wid], new[wid]
        if "weapon_type" not in o:
            continue
        exp = copy.deepcopy(o)
        exp.pop("weapon_type")
        exp["attack"] = dict(w["items_yml"]["attack"])
        exp["stats"]["damage"] = list(w["per_hit"])
        f = w.get("weapon_skill_factor")
        if f:
            exp["weapon_skills"] = [scale_skill(s, f) for s in o.get("weapon_skills") or []]
        exp_keys = [k for k in o if k != "weapon_type"]
        if exp != n:
            problems.append(f"{wid}: 다시 읽은 값이 기대와 다름")
        if list(n.keys()) != [("attack" if k == "weapon_type" else k) for k in o]:
            problems.append(f"{wid}: 키 순서가 바뀜 {exp_keys}")
    for iid in old:
        if iid in spec["weapons"] and spec["weapons"][iid].get("src") == "existing":
            continue
        if old[iid] != new[iid]:
            problems.append(f"{iid}: 무기가 아닌데 바뀜")
    return problems


# review2 A8: 지능 활·지능 근접은 attack.kind magic (gear_spec 이 이김, P3 gen_035_content.py 가 넣음)
GEAR_SPEC = ROOT / "tools/data/035/gear_spec.json"


def kind_overrides():
    if not GEAR_SPEC.exists():
        return {}
    gs = json.loads(GEAR_SPEC.read_text(encoding="utf-8"))
    return {wid: ch["attack"]["kind"] for wid, ch in gs.get("existing_changes", {}).items() if "attack" in ch}


def check(text, spec):
    """옮긴 결과 검사: weapon_type 없음 · attack·damage 가 명세와 같음 (피해 종류는 A8 로 gear_spec 이 이김)."""
    items = yaml.safe_load(text)["items"]
    problems = []
    kinds = kind_overrides()
    for wid, w in spec["weapons"].items():
        if w.get("src") != "existing":
            continue
        it = items.get(wid)
        if it is None:
            problems.append(f"{wid}: items.yml 에 없음")
            continue
        if "weapon_type" in it:
            problems.append(f"{wid}: 아직 weapon_type — 옮기지 않음")
            continue
        want = dict(w["items_yml"]["attack"])
        if wid in kinds:
            want["kind"] = kinds[wid]
        if it.get("attack") != want:
            problems.append(f"{wid}: attack {it.get('attack')} ≠ 명세 {want}")
        if (it.get("stats") or {}).get("damage") != w["per_hit"]:
            problems.append(f"{wid}: damage {(it.get('stats') or {}).get('damage')} ≠ 명세 {w['per_hit']}")
    for iid, it in items.items():
        if "weapon_type" in it:
            problems.append(f"{iid}: weapon_type 이 남음")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default=str(ITEMS))
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path = Path(args.items)
    text = path.read_text(encoding="utf-8")
    if args.check:
        problems = check(text, spec)
        for p in problems:
            print("✘", p)
        print("같음" if not problems else f"문제 {len(problems)}개")
        return 1 if problems else 0
    new, changed, problems = transform(text, spec)
    problems += verify(text, new, spec)
    for wid, old, now, attack, f, n in changed:
        print(f"{wid}: damage {old} → {now} · {flow(attack)}" + (f" · 무기 스킬 ×{f} ({n}줄)" if f else ""))
    for p in problems:
        print("✘", p)
    if problems:
        print(f"문제 {len(problems)}개 — 쓰지 않음")
        return 1
    if not changed:
        print("옮길 무기 없음")
        return 0
    if args.dry_run:
        print(f"{len(changed)}개 바뀜 (dry-run — 쓰지 않음)")
        return 0
    path.write_text(new, encoding="utf-8")
    print(f"{len(changed)}개 옮김 → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
