#!/usr/bin/env python3
"""
TASK B — 요구 능력치 검사: 직업마다 5레벨 구간마다 '알맞은 한 벌'을 낄 수 있는가 (분배 초기화 뒤, 칭호 없음).

  내 능력치 = 직업 기본 + 시작 5 + 레벨마다 5 (칭호 0 — 12개 칭호는 한 사람씩만 가진다)
  한 벌 = 무기 1 + 방어구 4부위 (+ 방패: 그 구간에 방패를 드는 경우)
  무기 = 그 구간 무기 하나가 직업이 쓰는 두 능력치를 60/40 으로 요구한다고 본다 (합 T(L) = ceil(1.1 × 2.5(L−1)))
         (무기 쪽 설계자가 구간마다 여러 요구 짝을 낸다 — 여기서는 '그 직업 짝 무기가 하나는 있다'는 가정만)
  방어구 = 구간 안(또는 그 아래) 겉모습마다 가장 높은 세트 (lk_core.new_requires)
  검사 레벨 = 그 한 벌에서 가장 높은 아이템 레벨 (얻자마자 입는 가장 빡빡한 경우)
  알맞음 = 남는 포인트 ≥ 0, 그리고 직업이 안 쓰는 능력치에 억지로 넣는 포인트 ≤ 그 레벨 포인트의 25%

  python3 lk_reqcheck.py [--new]   → lk_reqcheck.json
"""
import json
import os
import sys

import lk_core as K

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
# 직업이 쓰는 능력치 (피해·생존·치명·자원). 이 밖의 능력치에 넣는 포인트 = '세금'
USEFUL = {"guardian": {"VIT", "STR", "DEX", "WIS"}, "berserker": {"STR", "VIT", "DEX", "LUK"},
          "hunter": {"DEX", "STR", "VIT", "LUK"}, "arcanist": {"INT", "VIT", "WIS"},
          "priest": {"WIS", "INT", "VIT"}, "shadow": {"DEX", "STR", "VIT", "LUK"}}
WEAPON_PAIR = {"guardian": {"STR": 0.6, "VIT": 0.4}, "berserker": {"STR": 0.6, "VIT": 0.4},
               "hunter": {"DEX": 0.6, "STR": 0.4}, "arcanist": {"INT": 0.6, "WIS": 0.4},
               "priest": {"WIS": 0.6, "INT": 0.4}, "shadow": {"DEX": 0.6, "STR": 0.4}}
TAX_LIMIT = 0.25
BANDS = [(1 + 5 * i, 5 + 5 * i) for i in range(10)]


def points(L):
    return K.CONFIG["level"]["start_points"] + K.CONFIG["level"]["points_per_level"] * (L - 1)


def sets_by_look(include_new):
    """겉모습 → [(세트 레벨, 세트 id, {slot: item})] (세트 없는 단품 투구는 그 겉모습의 '투구 후보')."""
    out = {"plain": [], "heavy": [], "light": [], "cloth": []}
    singles = {"plain": [], "heavy": [], "light": [], "cloth": []}
    shields = []
    for iid, v in K.armor_items(include_new).items():
        lk = K.look_of(iid)
        if v.get("armor_slot") == "offhand":
            shields.append((v["level_req"], iid))
            continue
        sid = v.get("set_bonus")
        if lk not in out:
            continue
        if sid is None:
            singles[lk].append((v["level_req"], iid))
            continue
        ent = next((e for e in out[lk] if e[1] == sid), None)
        if ent is None:
            ent = [v["level_req"], sid, {}]
            out[lk].append(ent)
        ent[2][v["armor_slot"]] = iid
    for lk in out:
        out[lk].sort()
    return out, singles, shields


def need_for(items, cls, L_weapon):
    need = {}
    for iid in items:
        for st, n in K.new_requires(iid).items():
            need[st] = max(need.get(st, 0), n)
    for st, n in K.split(K.T(L_weapon), WEAPON_PAIR[cls]).items():
        need[st] = max(need.get(st, 0), n)
    return need


def evaluate(cls, need, L):
    base = K.CLASSES[cls]["base_stats"]
    pts = {st: max(0, n - base.get(st, 0)) for st, n in need.items()}
    used = sum(pts.values())
    have = points(L)
    tax = sum(v for st, v in pts.items() if st not in USEFUL[cls])
    return dict(level=L, need=need, used=used, have=have, left=have - used, tax=tax,
                ok=have - used >= 0 and tax <= TAX_LIMIT * have)


def check(include_new=False):
    by_look, singles, shields = sets_by_look(include_new)
    res = {}
    for cls in CLASSES:
        for lo, hi in BANDS:
            row = {}
            for lk, sets in by_look.items():
                cand = [e for e in sets if e[0] <= hi]
                if not cand:
                    row[lk] = None
                    continue
                lvl, sid, pieces = cand[-1]
                items = list(pieces.values())
                L = max(lvl, lo)
                ev = evaluate(cls, need_for(items, cls, min(hi, max(lo, lvl))), L)
                ev["set"] = sid
                ev["set_level"] = lvl
                # 같은 구간에 더 낮은 세트가 더 알맞으면 그것도 본다 (가장 높은 세트만 '세금'이 클 때)
                if not ev["ok"]:
                    for lvl2, sid2, p2 in reversed(cand[:-1]):
                        ev2 = evaluate(cls, need_for(list(p2.values()), cls, min(hi, max(lo, lvl))), max(lvl, lo))
                        if ev2["ok"]:
                            ev2["set"] = sid2
                            ev2["set_level"] = lvl2
                            ev2["fallback_from"] = sid
                            ev = ev2
                            break
                row[lk] = ev
            # 방패 (판금 한 부위) — 그 구간에서 가장 높은 방패를 같이 들 수 있는 겉모습
            sh = [s for s in sorted(shields) if s[0] <= hi]
            row["shield"] = sh[-1][1] if sh else None
            if sh:
                for lk in ("heavy", "light", "cloth"):
                    ev = row.get(lk)
                    if not ev:
                        continue
                    items = list(next(e for e in by_look[lk] if e[1] == ev["set"])[2].values()) + [sh[-1][1]]
                    e2 = evaluate(cls, need_for(items, cls, min(hi, max(lo, ev["set_level"]))),
                                  max(ev["level"], min(hi, sh[-1][0])))
                    ev["with_shield_ok"] = e2["ok"]
                    ev["with_shield_left"] = e2["left"]
            ok_looks = [lk for lk in ("plain", "heavy", "light", "cloth") if row.get(lk) and row[lk]["ok"]
                        and (lk != "plain" or lo == 1)]
            row["ok_looks"] = ok_looks
            res[f"{cls}|{lo}-{hi}"] = row
    return res


def summary(res):
    lines = []
    worst = None
    for cls in CLASSES:
        cells = []
        for lo, hi in BANDS:
            r = res[f"{cls}|{lo}-{hi}"]
            cells.append(("P" if "plain" in r["ok_looks"] else "") +
                         "".join(lk[0].upper() if lk in r["ok_looks"] else "·" for lk in ("heavy", "light", "cloth")))
            for lk in r["ok_looks"]:
                left = r[lk]["left"]
                if worst is None or left < worst[0]:
                    worst = (left, cls, lo, hi, lk)
        lines.append(f"{cls:9} " + " ".join(cells))
    return lines, worst


if __name__ == "__main__":
    inc = "--new" in sys.argv
    res = check(inc)
    lines, worst = summary(res)
    print("구간: " + " ".join(f"{lo}-{hi}" for lo, hi in BANDS))
    print("\n".join(lines))
    print("가장 빡빡한 알맞은 한 벌:", worst)
    locked = [k for k, r in res.items() if not r["ok_looks"]]
    print("한 구간 통째로 못 입는 직업:", locked or "없음")
    with open(os.path.join(HERE, "lk_reqcheck%s.json" % ("_new" if inc else "")), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
