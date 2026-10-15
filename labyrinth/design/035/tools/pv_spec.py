#!/usr/bin/env python3
"""TASK P — pvp_spec.md + pvp_spec.json 만들기 (pv_results.json 을 읽는다; 먼저 python3 pv_run.py)."""
import json
import os
import statistics as st

import pv_core as V
import pv_final as F
import pv_sim as S

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)
R = json.load(open(os.path.join(HERE, "pv_results.json"), encoding="utf-8"))
import pv_cc as _CC  # noqa: E402  (상태이상 표는 데이터에서 바로 — 시뮬레이터를 다시 돌리지 않아도 되게)
R["cc_rows"] = _CC.rows()
P = F.PVP_NEW
CN = {c: V.CLASS_NAME[c] for c in V.CLASS_ORDER}
KN = {"burst": "유리", "guard": "수비"}
KEYS = [(c, k) for c in V.CLASS_ORDER for k in ("burst", "guard")]
LV = [str(x) for x in R["levels"]]
CFG = R["configs"]
NEWC = CFG["new"]


def pct(x, d=0):
    return f"{x*100:.{d}f}%"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def short(c, k):
    return f"{CN[c]}·{KN[k]}"


def kk(c, k):
    return f"{c}|{k}"


# ───────────────────────────── 설정 (config.yml 모양) ─────────────────────────────
CONFIG_YAML = """pvp:
  enabled: true
  # ── 피해 ──────────────────────────────────────────────────────────────────────
  # 0.3.5: '기본 대비 배율'. 1.0 = 이 명세의 균형. 0.3.4 의 0.7(안 고친 값)은 1.0 으로, 고친 값은 값÷0.7 로 옮긴다.
  damage_multiplier: 1.0
  # 레벨 곡선 — 두 사람 중 높은 레벨 L 로: 기준 배율 = base × min(1, (ref_level ÷ L)^exponent)
  #   (공격 쪽 피해는 레벨²보다 빨리 크고 HP 는 레벨에 정비례라, 그대로 두면 Lv50 한 바퀴가 Lv20 의 3~4배가 된다)
  level_curve: {base: 2.0, ref_level: 20, exponent: 2.35}
  # PvP 완충 체력 B(L) — 모두에게 같은 양. PvP 피해 × 최대 HP ÷ (최대 HP + B). 레벨 20 까지 L×42, 그 위 레벨마다 +12
  buffer_hp: {per_level_low: 42, knee_level: 20, per_level_high: 12}
  # 피해 공식의 방어를 PvP 에서 얼마나 셀지 (0 = 방어 대신 아래 강인함)
  defense_weight: 0.0
  # 강인함 R = cap × S ÷ (S + per_level × L),  S = 체력(VIT) + 방어   → 받는 PvP 피해 × (1 − R)
  resilience: {cap: 0.40, per_level: 8}
  crit_damage_scale: 0.6       # 치명 '추가' 피해 × 0.6 (치명 피해 2.5 → 1.9)
  # 한 방 상한 (관리자용). 1.0 = 없음 — 한 바퀴로 쓰러뜨릴 수 있다. 0.3.4 의 안 고친 0.35 는 1.0 으로 옮긴다.
  max_hit_ratio: 1.0
  # 직업 보정 (플레이어에게 주는 피해). 1:1 시뮬레이터에서 크게 밀리거나 앞선 직업만. 적지 않은 직업 = 1.0
  class_damage: {hunter: 0.9, arcanist: 1.2, shadow: 1.2}
  # ── 회복·보호막 ('PvP 전투 중' = 다른 파티 플레이어와 피해를 주고받은 지 combat_seconds 안) ──────────
  combat_seconds: 8
  healing: 0.6                 # 받는 모든 회복 (스킬·물약·장비·재생)
  potion: 0.6                  # 물약은 한 번 더 (0.6 × 0.6 = 36%)
  lifesteal: 0.5               # 플레이어를 때려 얻는 흡혈 (장비·버프·무기 스킬·고유 효과) — healing 대신 이 값
  shield: 0.8                  # PvP 전투 중 새로 얻는 보호막
  flat_heal_by_pool: true      # 고정량 회복(치유력·흡혈·재생)은 × 최대 HP ÷ (최대 HP + B) — 피해와 같은 단위로
  # 긴 싸움: 전투가 start 초 넘게 이어지면 받는 회복·보호막이 초마다 per_second 씩 줄어든다 (floor 까지)
  long_fight: {start: 20, per_second: 0.025, floor: 0.10}
  # ── 상태이상 (플레이어가 다른 파티 플레이어에게 건 것만) ─────────────────────────────────────────
  cc:
    duration: {stun: 0.8, frozen: 1.0, root: 0.8, silence: 0.8, blind: 0.7, slow: 1.0, cooldown_slow: 0.5}
    max_seconds: {stun: 1.0, frozen: 1.5, root: 1.5, silence: 1.5, blind: 1.5, slow: 3.0, cooldown_slow: 2.0}
    slow_max_potency: 0.5      # 플레이어에게 거는 둔화 세기 상한 (지금 0.85)
    diminishing:
      window: 8                # 같은 분류를 이 시간 안에 다시 맞으면
      steps: [1.0, 0.5, 0.25, 0.0]   # 첫 번째 100% → 50% → 25% → 면역 (window 동안 안 맞으면 처음으로)
      groups: {control: [stun, frozen], root: [root], silence: [silence], blind: [blind]}
    control_immunity: 2.0      # 기절·빙결이 끝난 뒤 이 시간 동안 기절·빙결 면역
    min_seconds: 0.2           # 줄여서 이보다 짧으면 걸지 않는다 (그래도 횟수는 센다)
  # ── 그대로 ─────────────────────────────────────────────────────────────────────
  safe_zone_village: true
  safe_zone_margin: 8
  party_name_color: true"""

CONFIG_JSON = dict(
    enabled=True, damage_multiplier=1.0, level_curve=dict(base=2.0, ref_level=20, exponent=2.35),
    buffer_hp=dict(per_level_low=42, knee_level=20, per_level_high=12), defense_weight=0.0,
    resilience=dict(cap=0.40, per_level=8), crit_damage_scale=0.6, max_hit_ratio=1.0,
    class_damage=dict(hunter=0.9, arcanist=1.2, shadow=1.2), combat_seconds=8, healing=0.6, potion=0.6, lifesteal=0.5,
    shield=0.8, flat_heal_by_pool=True, long_fight=dict(start=20, per_second=0.025, floor=0.10),
    cc=dict(duration=F.CC_MULT, max_seconds=F.CC_CAP, slow_max_potency=F.SLOW_POTENCY_CAP,
            diminishing=dict(window=8, steps=[1.0, 0.5, 0.25, 0.0],
                             groups=dict(control=["stun", "frozen"], root=["root"], silence=["silence"], blind=["blind"])),
            control_immunity=2.0, min_seconds=0.2),
    safe_zone_village=True, safe_zone_margin=8, party_name_color=True)


# ───────────────────────────── 표 만들기 ─────────────────────────────

def targets_table():
    rows = []
    for name, label in (("0.3.4", "0.3.4 설정 (×0.7 · 상한 35%)"), ("nocap", "상한만 없앰 (×0.7)"), ("new", "새 PvP (이 명세)")):
        for L in LV:
            t = CFG[name]["targets"][L]
            d = CFG[name]["duel"][L]["summary"]
            rows.append([label, f"Lv{L}", pct(t["hit_max"], 1), pct(t["crit_max"], 1), pct(t["hit_med_gg"], 1),
                         pct(t["gg"]), pct(t["gg_all"]), pct(t["gd"]), pct(1 - t["gd"]) if t["gd"] < 1 else "0%",
                         pct(t["dg"]), pct(d["burst_vs_guard"]), f"{d['ttk_bb']:.1f}초", f"{d['ttk_bg']:.1f}초",
                         f"{d['ttk_gg']:.1f}초 ({pct(d['draw_gg'])})"])
    return table(["설정", "레벨", "기본 공격 한 대 최대", "치명 한 대 최대", "한 대 중앙 (유리→유리)",
                  "한 바퀴 유리→유리 (기대)", "같은 것 모두 치명", "한 바퀴 유리→수비", "수비 남는 HP",
                  "한 바퀴 수비→유리", "1:1 유리가 수비를 이김", "1:1 시간 유리↔유리", "유리↔수비", "수비↔수비 (90초 무승부)"], rows)


def why_table():
    rows = []
    for L in LV:
        for k in ("burst", "guard"):
            hp = [R["builds"][L][kk(c, k)]["hp"] for c in V.CLASS_ORDER]
            de = [R["builds"][L][kk(c, k)]["defense"] for c in V.CLASS_ORDER]
            rows.append([f"Lv{L}", KN[k], f"{min(hp)}–{max(hp)}", f"{min(de):.0f}–{max(de):.0f}",
                         f"{st.mean(R['builds'][L][kk(c, k)]['dr'] for c in V.CLASS_ORDER):.2f}"])
    return table(["레벨", "빌드", "최대 HP", "방어", "피해 감소 평균"], rows)


def build_table(L):
    rows = []
    for c, k in KEYS:
        b = R["builds"][L][kk(c, k)]
        s = b["stats"]
        st_ = " ".join(f"{x}{s[x]}" for x in ("STR", "DEX", "INT", "VIT", "WIS") if s[x] >= 10)
        look = {"heavy": "판금", "light": "가죽", "cloth": "천"}[b["look"]] + (" 4부위" if b["full"] else "")
        rows.append([short(c, k), f"{b['weapon_name']} `{b['weapon']}`", f"{b['interval']:.2f}초",
                     look + (" + 방패" if b["shield"] else ""), st_, b["hp"], f"{b['defense']:.0f}", f"{b['dr']:.2f}",
                     f"{b['crit']:.2f} / {b['crit_dmg']:.2f}", f"{b['atk_speed']:+.2f}", f"{b['per_hit']:.0f}",
                     f"{b['skill_power']:.0f}"])
    return table(["빌드", "무기", "간격", "방어구", "능력치(10 이상)", "HP", "방어", "피해 감소", "치명 확률/피해",
                  "공속", "한 방(공격력)", "스킬 위력"], rows)


def matrix_table(L, key, cfg="new", rows_kind=("burst", "guard"), fmt=lambda v: f"{v*100:.0f}"):
    if key in ("win", "ttk"):
        M = CFG[cfg]["duel"][L][key]
    else:
        M = CFG[cfg]["rot"][L][key]
    head = ["공격 ＼ 상대"] + [short(c, k) for c, k in KEYS]
    rows = []
    for kind in rows_kind:
        for c in V.CLASS_ORDER:
            rows.append([f"**{short(c, kind)}**"] + [fmt(M[f"{kk(c, kind)}>{kk(cb, kb)}"]) for cb, kb in KEYS])
    return table(head, rows)


def class_avg_table():
    rows = []
    for c in V.CLASS_ORDER:
        r = [CN[c]]
        for L in LV:
            s = NEWC["duel"][L]["summary"]
            r.append(f"{s['class'][kk(c, 'burst')]*100:.0f} / {s['class'][kk(c, 'guard')]*100:.0f}")
        r.append(f"{st.mean(NEWC['duel'][L]['summary']['class_all'][c] for L in LV)*100:.0f}")
        r.append(f"{st.mean(CFG['nocap']['duel'][L]['summary']['class_all'][c] for L in LV)*100:.0f}")
        rows.append(r)
    return table(["직업", "Lv20 유리/수비 승률", "Lv35", "Lv50", "새 PvP 평균", "상한만 없앤 것 평균"], rows)


def parts_table(L):
    rows = []
    for c in V.CLASS_ORDER:
        ps = NEWC["rot"][L]["parts"][c]
        tot = sum(p for _n, p in ps)
        rows.append([CN[c], pct(tot), " · ".join(f"{_nice(n)} {p*100:.0f}" for n, p in ps)])
    return table(["직업 (유리)", "합", "구성 (상대 = 같은 레벨 유리 사냥꾼, %)"], rows)


SK_NAME = {k["id"]: k["name"] for c in V.CLASS_ORDER for k in V.class_kit(c)}


def _nice(n):
    if n == "basic":
        return "기본 공격"
    return SK_NAME.get(n, n)


RARN = {"common": "일반", "uncommon": "고급", "rare": "희귀", "epic": "영웅", "legendary": "전설", "mythic": "신화"}


def skill_mult_table():
    cls_ids = {k["id"]: (c, k) for c in V.CLASS_ORDER for k in V.class_kit(c)}
    rows = []
    for key, v in sorted(R["skill_mult"].items(), key=lambda x: (x[0] not in cls_ids, x[1])):
        if key in cls_ids:
            c, k = cls_ids[key]
            rows.append(["직업", CN[c], f"{k['name']} `{key}`" + (" (궁극기)" if k["ult"] else ""),
                         f"{S.class_coef(c, k):.2f}", f"×{v:.2f}"])
        else:
            wid, inp = key.split(":")
            w = V.weapon(wid)
            s = [x for x in w["skills"] if str(x["input"]) == inp][0]
            rows.append(["무기", f"{w['name']} `{wid}` (Lv{w['level']} {RARN[w['rarity']]})", f"{s['name']} ({inp})",
                         f"{S.weapon_coef(s):.2f}", f"×{v:.2f}"])
    return table(["종류", "직업·무기", "스킬", "한 사람 계수", "PvP 배율"], rows)


CCN = {"stun": "기절", "frozen": "빙결", "root": "속박", "silence": "침묵", "blind": "실명", "slow": "둔화",
       "cooldown_slow": "재사용 둔화", "frost": "서리", "knockback": "밀쳐내기", "pull": "끌어오기", "launch": "띄우기",
       "taunt": "도발", "mark": "표식", "vulnerable": "취약", "weaken": "약화", "venom": "독 중첩", "burn": "화상"}


def _pv(r, heavy=False):
    v = r["pvp_heavy"] if heavy else r["pvp"]
    if not v:
        return "-"
    return " → ".join("안 걸림" if x == 0 else f"{x:g}" for x in v)


def cc_rows(src, effects):
    return [r for r in R["cc_rows"] if r["src"] in src and r["effect"] in effects]


def cc_class_table():
    rows = []
    for r in R["cc_rows"]:
        if r["src"] != "class":
            continue
        e = r["effect"]
        today = f"{r['seconds']:g}초" if r["seconds"] else "-"
        if r["potency"] is not None and e in ("slow", "vulnerable", "mark", "weaken"):
            today += f" · {r['potency']*100:.0f}%"
        if e == "launch":
            today = f"세기 {r['potency']}"
        pv = _pv(r) if r["pvp"] else ("그대로" if e not in ("taunt",) else "효과 없음")
        if e == "slow":
            pv = f"{r['pvp'][0]:g}초 · {min(r['potency'], 0.5)*100:.0f}% (안에 있는 동안 계속)"
        rows.append([r["owner_name"], f"{r['name']} `{r['skill']}`", CCN.get(e, e), today, pv,
                     _pv(r, True) if r["pvp"] and e != "slow" else "-", r["note"]])
    return table(["직업", "스킬", "효과", "지금 (몹·플레이어 같음)", "PvP 첫 → 둘째 → 셋째 (초)", "판금 4부위", "메모"], rows)


def cc_weapon_hard_table():
    rows = []
    for r in R["cc_rows"]:
        if r["src"] != "weapon" or r["effect"] not in ("stun", "root", "silence", "blind", "frost"):
            continue
        e = r["effect"]
        reps = r.get("repeats") or 1
        if e == "frost":
            today = f"서리 {int(r['potency'])}중첩×{reps:g} ({r['seconds']:g}초 유지) → 5중첩 빙결 4초"
            pv = "빙결 " + _pv(r)
        else:
            today = f"{r['seconds']:g}초" + (f" × {reps:g}번" if reps and reps > 1.05 else "")
            pv = _pv(r)
        rows.append([f"{r['owner_name']} `{r['owner']}`", f"{r['name']} ({r['skill']})", CCN[e], today, pv,
                     _pv(r, True)])
    return table(["무기", "스킬 (입력)", "효과", "지금", "PvP 첫 → 둘째 → 셋째 (초)", "판금 4부위"], rows)


def cc_weapon_soft_table():
    rows = []
    for r in R["cc_rows"]:
        if r["src"] != "weapon" or r["effect"] not in ("slow", "cooldown_slow"):
            continue
        e = r["effect"]
        reps = r.get("repeats") or 1
        pot = r["potency"]
        today = f"{r['seconds']:g}초" + (f" · {float(pot)*100:.0f}%" if pot else "") + (f" × {reps:g}번" if reps > 1.05 else "")
        if e == "slow":
            pvs = f"{r['pvp'][0]:g}초" + (f" · {min(float(pot or 0.35), 0.5)*100:.0f}%" if True else "")
        else:
            pvs = f"{r['pvp'][0]:g}초 · {float(pot or 0.3)*100:.0f}%"
        rows.append([f"{r['owner_name']}", f"{r['name']} ({r['skill']})", CCN[e], today, pvs])
    return table(["무기", "스킬", "효과", "지금", "PvP"], rows)


def cc_unique_table():
    rows = []
    for r in R["cc_rows"]:
        if r["src"] not in ("unique", "status"):
            continue
        e = r["effect"]
        if e == "frost":
            today = f"서리 1중첩 → 5중첩 빙결 {r.get('frozen_today', 1):g}초"
            pv = "빙결 " + _pv(r)
        else:
            today = f"{r['seconds']:g}초"
            pv = _pv(r)
        rows.append([f"{r['owner_name']} `{r['owner']}`", r["name"], CCN.get(e, e), today, pv, _pv(r, True), r["note"]])
    return table(["무기 / 규칙", "효과 이름", "효과", "지금", "PvP 첫 → 둘째 → 셋째 (초)", "판금 4부위", "메모"], rows)


def cc_misc_table():
    import collections
    c = collections.Counter()
    ex = collections.defaultdict(list)
    for r in R["cc_rows"]:
        if r["effect"] in ("knockback", "pull", "launch", "taunt", "mark", "vulnerable", "weaken", "venom", "burn"):
            c[r["effect"]] += 1
            if len(ex[r["effect"]]) < 4:
                ex[r["effect"]].append(r["name"])
    rule = {"knockback": "그대로. 판금 4부위 −60% (TASK B), 힘 0.3%/점 저항", "pull": "그대로 (판금 4부위 −60%)",
            "launch": "그대로 (판금 4부위 −60%). 공중에서도 공격·스킬 가능 — 행동을 막지 않는다",
            "taunt": "몹만. 플레이어에게는 효과 없음 (지금과 같음)", "mark": "시간·세기 그대로 (받는 피해 +)",
            "vulnerable": "그대로 (받는 피해 +)", "weaken": "그대로 (주는 피해 −, 정신 감소 받음)",
            "venom": "독 피해 — 지속 피해 규칙(PvP 피해 공식)만", "burn": "화상 피해 — 지속 피해 규칙만"}
    rows = [[CCN[e], n, ", ".join(ex[e]), rule[e]] for e, n in sorted(c.items(), key=lambda x: -x[1])]
    return table(["효과", "개수", "예", "PvP"], rows)


def cc_compare_table():
    rows = []
    for L in LV:
        x = R["cc_compare"][L]
        rows.append([f"Lv{L}", f"{x['old']['cc']:.2f}초 → {x['new']['cc']:.2f}초",
                     f"{x['old']['chain_med']:.2f}초 → {x['new']['chain_med']:.2f}초",
                     f"{x['old']['chain']:.1f}초 → {x['new']['chain']:.1f}초"])
    return table(["레벨", "한 판 동안 묶인 시간 (한 사람, 평균)", "가장 긴 연속 묶임 (중앙)", "가장 긴 연속 묶임 (최대)"], rows)


def curve_table():
    rows = []
    for L, v in R["curves"].items():
        rows.append([f"Lv{L}", f"{v['m']:.2f}", v["buffer"]])
    return table(["레벨 (두 사람 중 높은 쪽)", "기준 배율 m(L)", "완충 체력 B(L)"], rows)


def net_table():
    rows = []
    for L in LV:
        for k in ("burst", "guard"):
            for c in ("berserker", "arcanist"):
                n = R["net"][f"{L}|{c}|{k}"]
                m = R["curves"][str(L)]["m"] if str(L) in R["curves"] else R["curves"][L]["m"]
                mult = m * n['buffer_factor'] * (1 - n['resilience']) * (1 - n['dr'])
                rows.append([f"Lv{L}", short(c, k), n["hp"], n["pool"], f"{n['buffer_factor']:.2f}", f"{n['S']:.0f}",
                             pct(n["resilience"], 1), f"{n['dr']:.2f}", f"×{mult:.3f}", pct(1000 * mult / n["hp"], 1)])
    return table(["레벨", "빌드", "최대 HP", "PvP 체력 (HP+B)", "HP÷PvP 체력", "S = VIT+방어", "강인함", "피해 감소",
                  "실제 HP 로 받는 배율 (m × HP비 × (1−R) × (1−감소))", "원피해 1,000 이 깎는 HP 막대"], rows)


def unique_rules_table():
    rows = [
        ["`shield_bash` 방패 강타", "기절 대신 느려짐 40% 1초", "**기절 그대로** — PvP 상태이상 규칙(×0.8 · 최대 1초 · 줄어듦 · 끝나면 2초 면역). 몹용 '같은 적 6초 면역'은 플레이어에게도 그대로"],
        ["`imbue` 원소 부여 (서리)", "빙결 대신 느려짐", "**빙결 그대로** (1초 → PvP 1초, 상한 1.5초, 줄어듦·면역 규칙)"],
        ["`leech` 생명 흡수", "회복량 ×0.5", "전역 `lifesteal: 0.5` 로 바꿈 (따로 ×0.5 안 함 — 두 번 깎지 않게)"],
        ["`sanctify` 축성", "혼자면 자신에게 절반", "그대로 + 고정량 회복 규칙(× HP÷PvP 체력) + healing 0.6"],
        ["`feast` 포식", "플레이어 처치에도 발동", "그대로. 회복은 healing 0.6 (최대 HP 비율이라 PvP 체력 비율은 안 곱함)"],
        ["`ward_aura` 수호 기운", "같은 파티만", "그대로 + 보호막 × shield 0.8 · 긴 싸움 규칙"],
        ["`thorns` 가시 반격", "되돌리는 피해 ×0.5, PvP 상한 적용", "×0.5 그대로. '상한'은 이제 없음(1.0) — 되돌린 피해도 PvP 피해 공식을 거친다"],
        ["`hemorrhage` 피 냄새", "치명 피해는 PvP 상한이 막는다", "상한 대신 `crit_damage_scale 0.6` 이 치명 추가 피해를 줄인다"],
        ["`rend`·`armor_break`", "플레이어에게 최대 3중첩", "그대로"],
        ["곱하기 보정 (`execute`·`bloodrush`·`first_strike`·`backstab`·`longshot`·`berserk`·`exploit`·`counterstep`)", "+피해 ×0.5", "그대로"],
        ["피해 덧 공격 (`flurry`·`cleave`·`chain_spark`·`overcharge`·`death_burst`)", "×0.5 또는 터지지 않음", "그대로 (이 피해도 PvP 공식·완충을 거친다)"],
        ["`steadfast`·`momentum`·`siphon`", "그대로", "그대로"],
    ]
    return table(["고유 효과", "unique_spec 의 PvP 규칙", "바꾼 뒤"], rows)


CODE = [
    ("pvp/PvpConfig", "새 레코드: damageMultiplier(기본 대비) · levelCurve(base, ref, exp) · bufferHp(low, knee, high) · defenseWeight · resilience(cap, perLevel) · critDamageScale · maxHitRatio · classDamage(Map) · combatSeconds · healing · potion · lifesteal · shield · flatHealByPool · longFight(start, perSecond, floor) · cc(PvpCcConfig). `from()` 이 0.3.4 값 옮기기(§13). 옛 `adjust()` 는 `PvpMath` 로."),
    ("pvp/PvpMath (새, 순수)", "`levelMult(L)` · `bufferHp(L)` · `poolFactor(maxHp, L)` = H÷(H+B) · `resilience(vit, defense, L)` · `critMultiplier(critDamage)` = 1 + (cd−1)×scale · `longFight(secondsInCombat)` · `flatHeal(amount, maxHp, L)`. 모든 숫자는 PvpConfig 에서."),
    ("pvp/PvpCc (새, 순수)", "플레이어 하나의 줄어듦 기록(분류 → 횟수·마지막 시각)과 면역 끝 시각. `double duration(String id, double seconds, long now)` = PvP 배율 → 상한 → 줄어듦 단계 → 면역 → 0.2초 아래면 0 (횟수는 셈). `onControlEnd(until)` = 면역 시작."),
    ("pvp/PvpModule.PvpHook.before", "대상이 다른 파티 플레이어일 때: amount × damageMultiplier × levelMult(max(두 레벨)) × classDamage(공격자 직업) × skillPvpMult(ctx.sourceId) × (1 − 강인함(대상)) × poolFactor(대상). `ctx.defenseScale(defenseWeight)` · `ctx.critDamageScale(critDamageScale)`. 수호의 맹세(RELAYED)는 지금처럼 건너뜀. 두 사람 '전투 중' 시각 갱신."),
    ("pvp/PvpModule.PvpHook.absorb", "`maxHitRatio < 1` 일 때만 상한 (기본 1.0 = 없음). 기록(recordHit)은 그대로."),
    ("pvp/PvpModule (전투 중)", "UUID → (마지막 PvP 피해 시각, 이번 전투 시작 시각). `inCombat(p)` = combatSeconds 안. 전투가 끊기면 시작 시각을 지움. `PvpState` 를 TargetFilter 로 내보냄 (아래)."),
    ("pvp/TargetFilter + PvpState (새 인터페이스)", "`default PvpState pvp() { return PvpState.NONE; }` — PartyTargetFilter 가 모듈의 것을 돌려줌. PvpState: `inCombat(Player)` · `healFactor(Player, HealKind)` · `flatHealFactor(Player)` · `shieldFactor(Player)` · `ccSeconds(Player target, LivingEntity source, String id, double seconds)` · `onCcEnd(...)`. NONE 은 모두 1(그대로)."),
    ("pvp/PvpListener.onVanillaPvp", "바닐라 경로(물약·TNT·늑대 등): 'HP 20 기준' 환산 뒤 × poolFactor(대상) × (1 − 강인함(대상)) (레벨 곡선·직업 보정은 안 곱함 — 미궁 공격력이 아님). maxHitRatio < 1 이면 상한."),
    ("pvp/PvpModule.label · status · enable 로그", "출처 이름에 `ws:<무기>:<입력>` 도 읽기. `/labadmin pvp` 와 켤 때 로그: 기준 배율(Lv20·35·50) · 완충 · 강인함 상한 · 회복 60% · 상태이상 규칙 한 줄."),
    ("combat/DamageContext", "새 필드 `defenseScale`(기본 1) · `critDamageScale`(기본 1) + 설정자. 훅이 before() 에서 바꾼다."),
    ("combat/DamageService.deal", "방어 = 대상 방어 × ctx.defenseScale(). 치명 피해 = 1 + (critDamage − 1) × ctx.critDamageScale(). 흡혈: 대상이 플레이어면 `heal(공격자, 0, dealt×흡혈, HealKind.LIFESTEAL)`."),
    ("combat/DamageService.heal", "새 판 `heal(target, pctAmount, flatAmount, HealKind kind, boolean show)` — HealKind = SKILL · POTION · LIFESTEAL · REGEN · OTHER. 대상이 플레이어면 `targets().pvp()` 로: (pct + flat × flatHealFactor) × healFactor(kind) × 긴 싸움. 옛 `heal(target, amount, show)` = pct 만(OTHER)."),
    ("stats/StatService (재생)", "HP 재생 틱: `damage().heal(p, 0, hpRegen, REGEN, false)`."),
    ("classes/skills/SkillContext.heal · items/weaponskills/SkillCast.heal · MechanicsEngine(heal·heal_caster·lifesteal·absorption) · AreaSkills(흡혈)", "최대 HP 비율 몫과 치유력(고정) 몫을 나눠 넘김. 흡혈은 LIFESTEAL."),
    ("items/weaponskills/SkillCast.hit", "`.skill(skill.id())` → `.skill(sourceId())` (`ws:<무기>:<입력>`) — 스킬마다 PvP 배율·죽음 메시지가 무기 스킬을 알아보게."),
    ("items/ConsumableListener", "치유 물약 `heal(p, maxHp×amount, 0, POTION, true)`."),
    ("classes/LabyrinthStatusEffectService.apply", "정신(WIS) 감소 · 판금 4부위 cc_resist(TASK B) 다음에: 대상·시전자가 다른 파티 플레이어면 `pvp().ccSeconds(...)` — 0 이면 걸지 않음. 둔화 세기는 slow_max_potency 까지. frost 중첩 자체는 그대로, 5중첩 빙결(apply 'frozen')이 이 규칙을 탐. 기절·빙결이 풀릴 때(만료·해방·정화) `onCcEnd` 로 면역 시작."),
    ("classes/LabyrinthStatusEffectService.addShield", "대상이 PvP 전투 중이면 × shield × 긴 싸움."),
    ("items/unique/UniqueEffectService (unique_spec)", "shield_bash 의 '기절 → 느려짐', imbue 의 '빙결 → 느려짐' 지우기 (그냥 apply). leech 의 PvP ×0.5 지우기(전역 lifesteal). 고정량 회복은 HealKind 로."),
    ("content/ClassDef · ItemDef.WeaponSkillDef · ContentParser · ContentValidator", "스킬마다 `pvp_mult` (classes.yml skills[].pvp_mult · items.yml weapon_skills[].pvp_mult, 기본 1.0, 검사 0.1~1.0)."),
    ("content/classes.yml · items.yml", "§6 표의 38개 스킬에 pvp_mult. classes.yml 머리 주석에 'pvp_mult = 플레이어에게 주는 피해 배율' 한 줄."),
    ("ui/menus/MainMenu.pvpLore · ui/menus/StatsMenu", "메인 메뉴 PvP 칸: '한 바퀴로 쓰러뜨릴 수 있음 · 기절·속박은 짧고 연달아 걸리면 더 짧음 · PvP 중 회복 60%'. /스탯 에 'PvP 강인함 N% · PvP 체력 N (최대 HP + 완충 B)' 한 줄."),
    ("config.yml · GDD §18.3 · §9.2 · ARCHITECTURE(pvp)", "§12 설정 블록. GDD 18.3 표를 새 키로, 9.2 에 'PvP 에서는 §18.6 규칙' 한 줄."),
]

TESTS = [
    ("PvpConfigTest (새)", "기본값 · 범위 자르기 · 0.3.4 옮기기: damage_multiplier 0.7 → 1.0, 고친 0.5 → 0.714 · max_hit_ratio 0.35 → 1.0, 고친 0.5 → 0.5 · 키 없으면 기본."),
    ("PvpMathTest (새, 순수)", "levelMult: Lv1~20 = 2.0, Lv35 ≈ 0.537, Lv50 ≈ 0.232 · bufferHp: Lv10 420, Lv20 840, Lv50 1200 · poolFactor · 강인함(S=360, Lv50 → 0.19) · 치명 2.5 → 1.9 · 긴 싸움 20초 1.0, 40초 0.5, 60초 0.1 · 높은 레벨 쪽을 쓴다."),
    ("PvpCcTest (새, 순수)", "기절 1초 → 0.8 → 0.4 → 0.2 → 면역 · 8초 지나면 처음으로 · 빙결 4초 → 1.5초 (상한) · 기절 끝난 뒤 2초 안 기절 0 · 속박은 다른 분류라 기절 면역과 무관 · 0.2초 아래 0 이지만 횟수 셈 · 정신·판금 감소가 PvP 배율 앞."),
    ("PvpDamageHookTest (새, 가짜 Services)", "같은 레벨 유리→유리 기본 공격 한 대가 공식대로 · 방어 0(defenseScale) · 스킬 pvp_mult 적용 · 같은 파티 0 · 몹 피해는 그대로 · 수호의 맹세 옮긴 피해는 두 번 줄이지 않음."),
    ("PvpHealTest (새)", "PvP 전투 중: 치유 스킬 = (비율 + 치유력×HP비) × 0.6 · 물약 × 0.36 · 흡혈 × 0.5 × HP비 · 재생 × HP비 × 0.6 · 전투 밖이면 그대로 · 긴 싸움 줄어듦."),
    ("PvpSkillMultDataTest (새, 데이터)", "classes.yml·items.yml 의 pvp_mult 가 pvp_spec.json `skill_mult` 와 같음 (38개) · 범위 0.1~1.0 · 없는 스킬은 1.0."),
    ("DamageFormulaTest", "그대로 + defenseScale 0 이면 방어 무시와 같고, critDamageScale 0.6 이면 치명 2.5 → 1.9."),
    ("PvpRulesTest · PvpSourcesTest", "그대로 (파티 규칙·책임 플레이어)."),
    ("UniqueProcTest (unique_spec)", "shield_bash·imbue 서리가 플레이어에게 기절·빙결 그대로 (PvpCc 를 거침)."),
]


def main():
    md = []
    A = md.append
    A("# 미궁 라비린스 — PvP 밸런스 (TASK P, 0.3.5 안)")
    A("")
    A("주인 결정 세 가지를 새 전투 모델(combat_spec) 위에서 숫자로 맞춘 명세다.")
    A("")
    A("1. 플레이어에게도 **기절은 기절 그대로**. 대신 너무 긴 것만 줄이고, 같은 종류를 연달아 맞으면 더 짧아지고, 기절이 끝나면 잠깐 면역.")
    A("2. **한 방 상한을 없앤다** (`max_hit_ratio` 0.35 → 1.0, 키는 관리자용으로 남김). 한 바퀴로 쓰러뜨릴 수 있다(원턴킬).")
    A("3. 그래도 **유리 대포 독주는 없게**: 유리끼리는 한 바퀴에 쓰러질 수 있고, 수비 빌드는 한 바퀴를 맞고 30~50% 남아 되받아친다. 오래 싸우면 어느 쪽도 일방적이지 않다.")
    A("")
    A("- 데이터: `pvp_spec.json` (설정 모양 `pvp:` · 상태이상 표 · 스킬 PvP 배율 · 시뮬레이터 표 · 코드 위치 · 테스트)")
    A("- 계산 스크립트(모두 `tools/`): `pv_core.py`(데이터·무기 스킬 읽기) · `pv_build.py`(직업 6 × 2빌드 × Lv20·35·50) · `pv_sim.py`(PvP 피해 공식·한 바퀴) · `pv_duel.py`(1:1 몬테카를로) · `pv_cc.py`(상태이상 목록) · `pv_final.py`(최종 설정) · `pv_tune.py`·`pv_solve2.py`·`pv_fit.py`·`pv_grid.py`(맞추기) · `pv_matrix.py` · `pv_run.py`(모든 표 → `pv_results.json`) · `pv_spec.py`(이 문서). `python3 tools/pv_run.py && python3 tools/pv_spec.py` 로 다시 만든다.")
    A("- 전투 모델은 combat_spec 그대로다(무기마다 간격, 한 방 = 공격력, STR 물리·INT 마법, 스킬 위력). 방어구 겉모습 효과는 look_spec(TASK B) 그대로다. combat_spec §8.1 의 'PvP 0.7·35% 그대로'는 이 명세가 대신한다.")
    A("")
    A("## 0. 한눈에")
    A("")
    A(table(["항목", "지금 (0.3.4)", "바꾼 뒤"], [
        ["한 방 상한", "최대 HP 35%", "**없음** (1.0, 관리자용 키)"],
        ["피해 배율", "×0.7 고정", "기준 배율 m(L) × 직업 보정 × 스킬 PvP 배율 (§3)"],
        ["HP 차이", "그대로", "모두에게 같은 **완충 체력 B(L)** — 피해 × HP ÷ (HP + B)"],
        ["방어", "그대로", "PvP 에서는 **강인함**(최대 40%, VIT+방어를 레벨로 나눔)으로 바뀜"],
        ["치명", "그대로", "추가 피해 × 0.6 (2.5배 → 1.9배)"],
        ["큰 스킬·궁극기", "그대로", "스킬마다 `pvp_mult` 38개 (궁극기 0.30~0.45)"],
        ["회복", "그대로", "PvP 전투 중 ×0.6 · 물약 ×0.36 · 흡혈 ×0.5 · 고정량 회복은 HP÷PvP 체력 · 20초부터 점점 줄어듦"],
        ["보호막", "그대로", "×0.8 (긴 싸움 규칙도)"],
        ["직업", "-", "사냥꾼 0.9 · 비전술사 1.2 · 그림자 1.2 (1:1 시뮬레이터 보정)"],
        ["상태이상", "몹과 같음 (빙결 4초, 속박 2.5초…)", "종류마다 배율·상한, 같은 분류 8초 안 다시 맞으면 50%→25%→면역, 기절·빙결 끝나면 2초 면역. **기절은 기절 그대로**"],
    ]))
    A("")
    nt = NEWC["targets"]
    nd = {L: NEWC["duel"][L]["summary"] for L in LV}
    A(f"- 기본 공격 한 대: 같은 레벨 상대 HP 의 최대 {pct(nt['20']['hit_max'],1)}(Lv20) · {pct(nt['35']['hit_max'],1)}(Lv35) · {pct(nt['50']['hit_max'],1)}(Lv50). 중앙 {pct(nt['20']['hit_med_gg'],1)}·{pct(nt['35']['hit_med_gg'],1)}·{pct(nt['50']['hit_med_gg'],1)}. 목표 ~15% 이하.")
    A(f"- 유리 대포의 한 바퀴(모든 스킬, 재사용 없음): 같은 레벨 유리 상대 HP 의 {pct(nt['20']['gg'])}·{pct(nt['35']['gg'])}·{pct(nt['50']['gg'])} (치명 기대값), 모두 치명이면 {pct(nt['20']['gg_all'])}·{pct(nt['35']['gg_all'])}·{pct(nt['50']['gg_all'])} → **쓰러뜨릴 수 있다**.")
    A(f"- 같은 한 바퀴를 수비 빌드가 맞으면 {pct(nt['20']['gd'])}·{pct(nt['35']['gd'])}·{pct(nt['50']['gd'])} → **{pct(1-nt['20']['gd'])}·{pct(1-nt['35']['gd'])}·{pct(1-nt['50']['gd'])} 남는다** (목표 30~50% — Lv35·50 은 위쪽 끝을 조금 넘는다. 1:1 균형을 먼저 맞췄다, §17). 수비의 한 바퀴는 유리에게 {pct(nt['20']['dg'])}·{pct(nt['35']['dg'])}·{pct(nt['50']['dg'])} — 되받아칠 수 있다.")
    A(f"- 끝까지 1:1 (직업 6 × 6, 서로 보고 시작): 유리가 수비를 이기는 비율 {pct(nd['20']['burst_vs_guard'])}·{pct(nd['35']['burst_vs_guard'])}·{pct(nd['50']['burst_vs_guard'])} — 어느 쪽도 독주하지 않는다. 상한만 없애면 수비가 거의 다 이긴다(유리 승률 {pct(CFG['nocap']['duel']['20']['summary']['burst_vs_guard'])}·{pct(CFG['nocap']['duel']['35']['summary']['burst_vs_guard'])}·{pct(CFG['nocap']['duel']['50']['summary']['burst_vs_guard'])}).")
    A(f"- 싸움 시간(중앙): 유리↔유리 {nd['20']['ttk_bb']:.0f}·{nd['35']['ttk_bb']:.0f}·{nd['50']['ttk_bb']:.0f}초, 유리↔수비 {nd['20']['ttk_bg']:.0f}·{nd['35']['ttk_bg']:.0f}·{nd['50']['ttk_bg']:.0f}초, 수비↔수비 {nd['20']['ttk_gg']:.0f}·{nd['35']['ttk_gg']:.0f}·{nd['50']['ttk_gg']:.0f}초.")
    cc = R["cc_compare"]
    A(f"- 상태이상: 빙결 4초 → 1.5초, 속박 2.5초 → 1.5초, 실명 3초 → 1.5초, 방패 강타 기절 1초 → 0.8초. 한 판 동안 묶인 시간(한 사람) {' · '.join(f'{cc[L][chr(111)+chr(108)+chr(100)][chr(99)+chr(99)]:.1f}→{cc[L][chr(110)+chr(101)+chr(119)][chr(99)+chr(99)]:.1f}초' for L in LV)} (Lv20·35·50). 행동 불가(기절·빙결)는 한 번에 최대 1.5초, 끝나면 2초 면역.")
    A("")
    A("## 1. 왜 이렇게 하나 — 새 전투 모델에서 잰 숫자")
    A("")
    A("두 빌드를 직업마다 만들었다 (§10.1). **유리** = 가죽(물리)·천(마법) 4부위, 남은 포인트를 피해 스탯 위주로. **수비** = 판금 4부위 + 방패, VIT 3 : 피해 스탯 2. 둘 다 요구 능력치를 먼저 채운다.")
    A("")
    A(why_table())
    A("")
    A("- 같은 레벨에서 수비 빌드는 HP 가 3~4배, 방어가 3~6배, 피해 감소·막기까지 더하면 **유효 HP 가 5~12배**다(레벨이 높을수록 차이가 커진다).")
    A("- 공격 쪽은 레벨이 오를수록 HP 보다 훨씬 빨리 큰다(무기 위력 ≈ 레벨², STR/INT 1%/점, 치명·공속 줄, 궁극기·무기 스킬 수). Lv50 유리 대포의 한 바퀴는 같은 레벨 유리 HP 의 10배를 넘는다(0.7 배율, 상한 없음).")
    A("- 그래서 0.3.4 설정 그대로(×0.7, 35%) 또는 상한만 없애면:")
    A("")
    A(targets_table())
    A("")
    nc = CFG["nocap"]
    A(f"- 상한만 없애면 Lv50 유리끼리는 치명 기본 공격 한 대(100%)로 끝난다(1:1 {nc['duel']['50']['summary']['ttk_bb']:.1f}초). 레벨이 오를수록 모두가 몇 초 만에 지워지고, 수비가 유리를 지우는 쪽이 훨씬 빠르다(수비의 한 바퀴 → 유리 {pct(nc['targets']['35']['dg'])}·{pct(nc['targets']['50']['dg'])}). 1:1 은 수비가 85% 넘게 이긴다 → **수비 독주 + 순삭**.")
    A(f"- 0.3.4 설정(35% 상한)도 같다: 상한이 한 방만 막고 한 바퀴는 못 막는다. Lv50 유리끼리 {CFG['0.3.4']['duel']['50']['summary']['ttk_bb']:.1f}초, 유리가 수비를 이기는 비율 {pct(CFG['0.3.4']['duel']['50']['summary']['burst_vs_guard'])}.")
    A("- 주인이 예로 든 'VIT·방어·피해 감소로 PvP 강인함'을 그대로 더하면 이 차이가 더 커진다. 그래서 이 명세는 **먼저 PvP 에서 생 HP·방어 차이를 줄이고**(완충 체력·방어 → 강인함), **그 자리에 상한이 있는 강인함을 둔다**. VIT·판금·방패는 여전히 PvP 에서 2배쯤 더 버티게 해 준다(목표: 한 바퀴를 맞고 30~50% 남음).")
    A("")
    A("## 2. 목표 (같은 레벨)")
    A("")
    A(table(["목표", "잰 값", "기준"], [
        ["기본 공격 한 대", "치명 아님, 빌드 아무거나 → 상대 최대 HP 의 %", "가장 센 경우 ≈ 15% 이하"],
        ["유리 대포의 한 바퀴가 유리를 쓰러뜨릴 수 있다", "피해 직업(광전사·사냥꾼·비전술사·그림자) 유리의 한 바퀴 → 유리 6직업, 중앙", "치명 기대값 ≈ 100~130%, 모두 치명 ≥ 100%"],
        ["수비는 한 바퀴를 버티고 30~50% 남는다", "같은 한 바퀴 → 수비 6직업, 중앙", "50~70%"],
        ["수비도 되받아친다", "수비의 한 바퀴 → 유리", "40~70%"],
        ["오래 싸우면 어느 쪽도 독주하지 않는다", "1:1 끝까지, 유리 6 × 수비 6, 유리 승률 평균", "40~60%"],
        ["싸움이 끝난다", "수비↔수비 90초 무승부", "낮게 (긴 싸움 규칙)"],
        ["기절 연쇄 없음", "행동 불가 한 번 · 한 판 동안 묶인 시간", "한 번 ≤ 1.5초, 묶인 시간은 지금보다 짧게"],
    ]))
    A("")
    A("한 바퀴 = 버프부터 해금된 직업 스킬 전부 + 손에 든 무기의 무기 스킬 전부 + 그 사이 3초 동안의 기본 공격 (스킬 하나마다 0.25초). 모두 맞는다고 본다. 막는 쪽의 즉시 반응(보호막·물약)은 넣지 않는다.")
    A("")
    A("## 3. PvP 피해 공식")
    A("")
    A("```")
    A("대상이 다른 파티 플레이어일 때 (DamageService 한 경로, 기본 공격·직업 스킬·무기 스킬·지속 피해·고유 효과 모두)")
    A("")
    A("L        = max(공격자 레벨, 대상 레벨)")
    A("m(L)     = 2.0 × min(1, (20 ÷ L)^2.35) × damage_multiplier(관리자, 기본 1.0)")
    A("B(L)     = 42 × min(L, 20) + 12 × max(0, L − 20)                 PvP 완충 체력 (모두 같음)")
    A("R        = 0.40 × S ÷ (S + 8 × L_대상),  S = 대상 VIT + 대상 방어      강인함")
    A("")
    A("원피해    = 지금 그대로 (한 방 × 물리/마법 배율, 스킬 위력 × 직업 배율 × 스킬 배율 …)")
    A("PvP 원피해 = 원피해 × m(L) × 직업 보정(공격자) × 스킬 pvp_mult × (1 − R) × H_대상 ÷ (H_대상 + B(L))")
    A("그다음    = DamageFormula 그대로 — 단, 방어 = 0 (defense_weight), 치명 피해 = 1 + (치명 피해 − 1) × 0.6")
    A("           (주는 피해 버프 → 회피 → 치명 → 피해 감소 → 받는 피해 증가(표식·취약) → 막기 → 보호막)")
    A("한 방 상한 = max_hit_ratio (기본 1.0 = 없음)")
    A("```")
    A("")
    A("- **완충 체력**은 'PvP 에서는 모두가 B 만큼 HP 를 더 가진 것처럼 맞는다'는 뜻이다. 화면의 HP 막대는 그대로다. 실제로 깎이는 HP = 피해 × H ÷ (H + B), 막대에서 깎이는 비율 = 피해 ÷ (H + B). 누구에게나 같은 B 가 더해지니 HP 가 적은 사람과 많은 사람의 차이가 줄어든다 (예: HP 700 대 2,600 → PvP 체력 1,900 대 3,800, 3.7배 → 2배).")
    A("- **방어**는 PvP 에서 피해 공식에 넣지 않고 강인함으로 센다. 판금의 방어 % 와 VIT 의 방어는 강인함으로 그대로 값을 한다. 피해 감소(장비 줄·수호기사 강철 의지·판금 부위)·막기(방패)·회피는 그대로다.")
    A("- **레벨 곡선**: Lv20 위로 공격 쪽이 HP 보다 레벨²배쯤 빨리 커서, 같은 레벨끼리의 '한 바퀴 = 상대 HP 의 몇 %' 를 Lv20·35·50 에서 비슷하게 맞춘다. 두 사람 중 높은 레벨을 쓴다 → 높은 레벨이 낮은 레벨을 칠 때 배율이 낮아진다(그래도 원피해가 커서 이긴다, §10.8).")
    A("- 지속 피해(출혈·독·화상)도 같은 식을 탄다(방어는 원래 무시). 스킬 pvp_mult 는 스킬의 직접 피해에만 (지속 피해는 상태이상으로 따로 걸리므로).")
    A("- 떠오르는 피해 숫자 = 실제로 깎인 HP (지금과 같음).")
    A("")
    A(curve_table())
    A("")
    A("예 (실제 HP 로 받는 배율 = m × HP비 × (1 − 강인함) × (1 − 피해 감소), 방어 0):")
    A("")
    A(net_table())
    A("")
    A("## 4. 강인함 (PvP 에서만)")
    A("")
    A("- 강인함 R = 0.40 × S ÷ (S + 8 × 레벨), S = 체력(VIT) + 방어(VIT×0.5 + 방어구 방어, 판금 %·가죽 % 포함). 받는 PvP 피해 × (1 − R).")
    A("- VIT 는 HP·방어·강인함 세 번 값을 한다. 판금은 방어 % 로, 방패는 막기로. 최대 40%.")
    A("- 같은 레벨 유리 빌드 5~11%, 수비 빌드 17~21% 쯤 (§3 표). '수비가 2배쯤 더 버틴다'의 몫을 HP·강인함·피해 감소·막기가 나눠 맡는다.")
    A("- /스탯 화면에 'PvP 강인함 N% · PvP 체력 = 최대 HP + 완충 B' 한 줄 (§16).")
    A("")
    A("## 5. 치명")
    A("")
    A("- 플레이어에게 들어가는 치명은 '추가 피해'만 × 0.6: 치명 피해 1.5 → 1.3, 2.0 → 1.6, 2.5 → 1.9, 2.9(그림자) → 2.1.")
    A("- 운 좋은 치명 몇 번으로 끝나는 것을 줄인다. 치명 확률·확정 치명(그림자 일격 등 뒤)은 그대로.")
    A("")
    A("## 6. 스킬마다 PvP 배율 (궁극기 포함)")
    A("")
    A("규칙: 스킬 한 번이 한 사람에게 주는 피해 계수(스킬 위력 단위, 직업 skill_scale 포함, 맞을 확률을 반영한 기대 타수)가 **2.5 를 넘으면** `pvp_mult = 2.5 ÷ 계수` (0.05 단위 내림). 0.9 이하일 때만 적는다. 여러 명을 치라고 만든 광역(같은 사람을 여러 번 노리는 낙뢰·화살비 등)과 궁극기가 대부분이다.")
    A("")
    A("- 데이터: classes.yml `skills[].pvp_mult`, items.yml `weapon_skills[].pvp_mult` (기본 1.0). 새 스킬을 만들 때도 같은 규칙(`tools/pv_sim.py skill_mults`).")
    A("- 궁극기 넷: 화살비 0.30 · 운석 낙하 0.35 · 그림자 처형 0.40 · 파멸의 도약 0.45. 수비의 성채·부활의 성가는 피해가 없어 그대로.")
    A("")
    A(skill_mult_table())
    A("")
    A("## 7. 직업 보정")
    A("")
    A("- 플레이어에게 주는 피해만: 사냥꾼 ×0.9 · 비전술사 ×1.2 · 그림자 ×1.2 · 나머지 ×1.0.")
    A("- 까닭: 1:1 은 몹 무리와 다르다. 비전술사의 광역·그림자의 기습은 1:1 에서 덜 빛나고, 사냥꾼은 거리를 벌려 근접 직업의 기본 공격을 거의 막는다(시뮬레이터에서 근접 → 사냥꾼 닿는 비율 0.55). 보정 전 평균 승률은 §10.7.")
    A("- 시뮬레이터는 위치·지형·눈속임을 확률로만 본다. 이 셋은 **시작값**이다. 테스트 서버에서 직업마다 1:1 을 몇 판씩 해 보고 0.05 단위로 고친다(config 한 줄).")
    A("")
    A("## 8. 회복·보호막")
    A("")
    A("'PvP 전투 중' = 다른 파티 플레이어에게 피해를 주거나 받은 지 8초 안. 이때만 아래 배율이 붙는다. 몹과 싸울 때는 그대로다.")
    A("")
    A(table(["회복·보호막", "PvP 전투 중", "왜"], [
        ["치유 스킬 (치유의 빛·정화의 파동·부활의 성가 회복·무기 스킬 heal·mend·sanctuary)", "× 0.6 (최대 HP 비율 몫) + 치유력 몫 × HP÷PvP 체력 × 0.6", "치유력은 고정량이라 HP 가 적은 사람에게 너무 크다 — 피해와 같은 단위로"],
        ["치유 물약·재생의 비약", "× 0.6 × 0.6 = 36% (상급 물약 60% → 21.6%)", "12초마다 HP 60% 는 1:1 을 끝없이 늘린다"],
        ["흡혈 (장비·피의 갈망·무기 스킬 lifesteal·고유 leech)", "× 0.5 × HP÷PvP 체력", "때린 만큼 되찾는 것 — 반만"],
        ["HP 재생 (장비 hp_regen)", "× 0.6 × HP÷PvP 체력", "고정량"],
        ["보호막 (수호의 맹세·성스러운 가호·은총 넘친 치유·무기 스킬 absorption·수호 기운)", "× 0.8", "보호막은 최대 HP 비율이라 그대로에 가깝게"],
        ["긴 싸움", "전투 20초 뒤부터 회복·보호막 × (1 − 0.025 × 초), 최소 10% (60초면 10%)", "수비↔수비가 물약으로 끝없이 버티지 않게. 8초 동안 PvP 피해가 없으면 처음으로"],
        ["부활 (불사조 깃털)", "그대로", "5분에 한 번"],
    ]))
    A("")
    A("## 9. 상태이상 (CC)")
    A("")
    A("### 9.1 규칙")
    A("")
    A("플레이어가 다른 파티 플레이어에게 건 것만 바뀐다. 몹·보스가 플레이어에게 건 것, 플레이어가 몹에게 건 것은 그대로다. **기절을 느려짐으로 바꾸지 않는다** (unique_spec 의 그 규칙도 지운다).")
    A("")
    A("```")
    A("시간 = 기본 시간")
    A("     × (1 − 정신 해로운 효과 감소)          (기절·빙결 제외 — 지금 규칙)")
    A("     × (1 − 0.40)                         (판금 4부위 '버팀': 기절·속박·빙결 — TASK B)")
    A("     × PvP 배율 (종류마다)                 기절 0.8 · 빙결 1.0 · 속박 0.8 · 침묵 0.8 · 실명 0.7 · 둔화 1.0 · 재사용 둔화 0.5")
    A("     → 상한 (종류마다)                     기절 1.0초 · 빙결 1.5초 · 속박 1.5초 · 침묵 1.5초 · 실명 1.5초 · 둔화 3초 · 재사용 둔화 2초")
    A("     × 줄어듦 (같은 분류를 8초 안에 다시)   첫 번째 100% → 두 번째 50% → 세 번째 25% → 네 번째부터 면역 (8초 동안 안 맞으면 처음으로)")
    A("     → 0.2초보다 짧으면 걸지 않음 (그래도 횟수는 센다)")
    A("분류: 행동 불가(기절·빙결) · 속박 · 침묵 · 실명. 둔화는 줄어듦 없음 — 대신 세기 상한 50% (지금 85%)")
    A("기절·빙결이 끝나면(만료·동료가 깨 줌·정화) 2초 동안 기절·빙결 면역")
    A("이미 걸린 동안 같은 것을 다시 맞으면: 남은 시간과 새 시간 중 긴 쪽 (지금 규칙), 줄어듦 횟수는 센다")
    A("```")
    A("")
    A("- 몹 상대보다 짧아지는 것은 '너무 긴 것'이 대부분이다: 빙결 4초, 속박 2~2.5초, 실명 3초, 침묵 2초, 고유 효과 기절 1.5초. 짧은 것(0.5초 낙뢰 기절 등)은 거의 그대로다.")
    A("- 연달아 거는 스킬(낙뢰 6번 기절 0.5초, 덫 장판 속박 반복)은 줄어듦과 면역 때문에 처음 한두 번만 제대로 걸린다.")
    A("- 시간이 없는 효과(밀쳐내기·끌기·띄우기)는 그대로. 판금 4부위가 −60%. 도발은 몹만.")
    A("")
    A("### 9.2 직업 스킬")
    A("")
    A(cc_class_table())
    A("")
    A("### 9.3 무기 스킬 — 행동·이동을 막는 것 (기절·속박·침묵·실명·서리)")
    A("")
    A("'× N번' = 한 번 쓸 때 같은 사람에게 들어갈 수 있는 기대 횟수(장판·연속 낙뢰). 두 번째부터 줄어듦을 탄다. '안 걸림' = 줄어든 시간이 0.2초보다 짧아 걸지 않음(네 번째부터는 8초 동안 면역).")
    A("")
    A(cc_weapon_hard_table())
    A("")
    A("### 9.4 무기 스킬 — 둔화·재사용 둔화")
    A("")
    A(cc_weapon_soft_table())
    A("")
    A("### 9.5 고유 효과 · 상태 규칙")
    A("")
    A(cc_unique_table())
    A("")
    A("### 9.6 시간이 없는 것 · 피해 수정")
    A("")
    A(cc_misc_table())
    A("")
    A("### 9.7 시뮬레이터로 본 묶인 시간 (같은 설정, 상태이상 규칙만 바꿈)")
    A("")
    A(cc_compare_table())
    A("")
    A("- '연속 묶임'은 기절·빙결·속박·침묵이 끊기지 않고 이어진 시간이다. 분류가 다르면 이어질 수 있다(예: 기절 0.8초 → 속박 1.5초 = 2.3초). 그래도 움직이지도 행동하지도 못하는 시간(기절·빙결)은 한 번에 최대 1.5초, 끝나면 2초 면역이다. 속박 중에는 공격·스킬이 된다.")
    A("- 시뮬레이터의 스킬 사용은 단순해서(재사용이 돌면 씀) 실제 손으로 노린 연쇄보다 덜 묶인다. 규칙상 최악의 행동 불가: 빙결 1.5초 → 2초 면역 → 기절 0.4초(줄어듦 50%) → 2초 면역 → 기절 0.2초 → 면역(8초).")
    A("")
    A("## 10. 시뮬레이터")
    A("")
    A("### 10.1 방법")
    A("")
    A("- 빌드(`pv_build.py`): 직업 6 × Lv20·35·50 × 유리·수비. 무기는 직업이 쓰는 공격 방식(수호기사 0.55~0.8초 근접 · 광전사 0.85초 넘는 근접 · 사냥꾼 활 · 비전술사 0.84초 넘는 시전 · 사제 0.86초 아래 시전 · 그림자 0.52초 아래 근접) 안에서 그 레벨의 가장 센 것(스킬 위력, 수비는 VIT·HP·감소 줄 우선). 등급 상한 Lv20 영웅 · Lv35·50 전설. 방어구는 그 겉모습의 가장 높은 것, 장신구 2개, 세트 효과·겉모습 효과(look_spec) 포함. 무기 숫자는 combat_spec 237개(새 106 포함), 요구 능력치는 gear_spec 새 값.")
    A("- 한 바퀴(`pv_sim.rotation`): §2 의 정의. 무기 스킬은 mechanics 를 읽어 한 사람에게 들어가는 기대 피해 배율을 셈(장판 시간·간격, 낙뢰 수, 투사체 수, 맞을 확률 — 근접 범위 0.85, 투사체 0.8, 장판 0.45 …).")
    A("- 1:1(`pv_duel.py`): 0.1초 단위, 판마다 40번(같은 시드). 서로 보고 시작. 기본 공격은 무기 간격마다 — 근접(시전 무기 휘두르기 포함)은 닿는 비율 0.85, 사냥꾼 상대 0.55, 상대가 묶이면 1.0, 내가 속박이면 ×0.4. 스킬은 재사용·MP 가 되면 우선순위(위급 회복 → 방어 버프 → 공격 버프 → 제어 → 피해). 물약 5개(HP 40% 아래, 12초). 상태이상·회복·보호막·고유 효과(1:1 에서 의미 있는 20개)·겉모습 4부위(판금 버팀 · 가죽 구르기 · 천 마나 보호막)를 넣었다. 90초가 넘으면 무승부.")
    A("- 맞추기: (1) 방어 0 + 강인함 상한 0.4 로 두고, 레벨마다 '유리→유리 한 바퀴 ÷ 유리→수비 한 바퀴' 가 1.95·2.25·2.6 이 되는 완충 B 와 유리→유리 한 바퀴가 110~115% 가 되는 배율 m 을 풀었다(`pv_solve2.py`). (2) 그 B 를 선(42/레벨 → 12/레벨), m 을 2.0 × (20/L)^2.35 로 맞췄다(`pv_fit.py`). (3) 1:1 표로 회복·물약·흡혈·긴 싸움·직업 보정을 골랐다(`pv_matrix.py`).")
    A("- 한계: 위치·지형·시야·눈속임을 확률로 본다. 사람이 고르는 순서보다 단순하다. 절대값보다 **설정끼리의 차이**와 **유리↔수비의 균형**으로 읽는다. 직업끼리의 승률은 무기 하나에 크게 흔들린다(같은 직업이 레벨마다 다른 무기를 든다).")
    A("")
    A("### 10.2 목표 확인")
    A("")
    A(targets_table())
    A("")
    for L in LV:
        A(f"### 10.3 빌드 — Lv{L}")
        A("")
        A(build_table(L))
        A("")
    for L in LV:
        A(f"### 10.4 한 바퀴 — Lv{L} (상대 최대 HP 의 %, 치명 기대값, 새 PvP)")
        A("")
        A(matrix_table(L, "rotation"))
        A("")
        A(f"모두 치명일 때 (Lv{L}, 유리 공격만):")
        A("")
        A(matrix_table(L, "rotation_all_crit", rows_kind=("burst",)))
        A("")
        A(f"한 바퀴 구성 (Lv{L}):")
        A("")
        A(parts_table(L))
        A("")
    for L in LV:
        A(f"### 10.5 기본 공격 한 대 — Lv{L} (치명 아님 / 치명, 상대 최대 HP 의 %)")
        A("")
        H = NEWC["rot"][L]["basic_hit"]
        C = NEWC["rot"][L]["basic_crit"]
        head = ["공격 ＼ 상대"] + [short(c, k) for c, k in KEYS]
        rows = []
        for kind in ("burst", "guard"):
            for c in V.CLASS_ORDER:
                rows.append([f"**{short(c, kind)}**"] + [f"{H[f'{kk(c, kind)}>{kk(cb, kb)}']*100:.1f}/{C[f'{kk(c, kind)}>{kk(cb, kb)}']*100:.0f}"
                                                          for cb, kb in KEYS])
        A(table(head, rows))
        A("")
    for L in LV:
        s = NEWC["duel"][L]["summary"]
        A(f"### 10.6 1:1 끝까지 — Lv{L} (행이 이긴 비율 %, 무승부 반)")
        A("")
        A(f"유리→수비 {pct(s['burst_vs_guard'])} · 시간 중앙 유리↔유리 {s['ttk_bb']:.1f}초 · 유리↔수비 {s['ttk_bg']:.1f}초 · 수비↔수비 {s['ttk_gg']:.1f}초 (무승부 {pct(s['draw_gg'])}) · 묶인 시간 {s['cc_per_fight']:.1f}초/판 · 가장 긴 연속 묶임 {s['chain_max']:.1f}초")
        A("")
        A(matrix_table(L, "win"))
        A("")
        A(f"걸린 시간 (초, 중앙, Lv{L}):")
        A("")
        A(matrix_table(L, "ttk", fmt=lambda v: f"{v:.0f}"))
        A("")
    A("### 10.7 직업별 평균 승률 (모든 상대, %)")
    A("")
    A(class_avg_table())
    A("")
    cb = R["class_before"]
    A("- 직업 보정만 뺀 새 PvP 의 평균 승률: " + " · ".join(f"{CN[c]} {st.mean(cb[L]['class_all'][c] for L in LV)*100:.0f}" for c in V.CLASS_ORDER)
      + f" (유리→수비 {' · '.join(pct(cb[L]['burst_vs_guard']) for L in LV)}). 보정 뒤는 위 표.")
    A("- 남는 큰 치우침은 무기 하나 때문인 경우가 많다: 예) Lv35 수호기사 유리는 무기 스킬이 없는 자수정 팔시온을 들어 약하고, Lv50 은 무기 스킬 셋 달린 전설 심연 파수검이라 세다. 사제 유리는 치유 + 강한 마법 기본 공격으로 Lv35·50 에서 앞선다(치유는 이미 60%·고정량 규칙을 받는다). 무기 간 차이는 gear_spec 의 몫이다.")
    A("")
    A("### 10.8 낮은 레벨 · 레벨 차이")
    A("")
    low = NEWC["targets"]
    rows = []
    for L in ("5", "10"):
        t = low[L]
        d = NEWC["duel"][L]["summary"]
        rows.append([f"Lv{L}", pct(t["hit_max"], 1), pct(t["gg"]), pct(t["gd"]), pct(d["burst_vs_guard"]), f"{d['ttk_bb']:.0f}초", f"{d['ttk_bg']:.0f}초"])
    A(table(["레벨", "기본 공격 한 대 최대", "한 바퀴 유리→유리", "유리→수비", "1:1 유리 승률", "유리↔유리 시간", "유리↔수비 시간"], rows))
    A("")
    A(f"- Lv20 아래는 스킬이 1~3개뿐이라 한 바퀴로 끝나지 않는다(기본 공격 싸움). VIT 를 찍은 쪽이 유리하다 — 지켜볼 것.")
    A(f"- 레벨 차이(같은 직업·빌드끼리, 낮은 쪽 승률): Lv20 vs 35 {pct(R['cross']['20-35'])} · Lv35 vs 50 {pct(R['cross']['35-50'])} · Lv20 vs 50 {pct(R['cross']['20-50'])}. 레벨이 높은 쪽이 이긴다. 높은 레벨 기준 배율이라 고레벨이 저레벨을 '한 대에' 지우지는 않는다.")
    A("")
    A("## 11. unique_spec 의 PvP 규칙 바꿈")
    A("")
    A(unique_rules_table())
    A("")
    A("## 12. 설정 (config.yml)")
    A("")
    A("```yaml")
    A(CONFIG_YAML)
    A("```")
    A("")
    A("## 13. 옮기기 (0.3.4 → 0.3.5)")
    A("")
    A("- `max_hit_ratio`: 0.35(0.3.4 기본, 안 고친 값) → **1.0**. 다른 값(관리자가 고친 것)은 그대로 둔다 — 일부러 상한을 원하는 서버.")
    A("- `damage_multiplier`: 뜻이 바뀐다('기본 대비 배율'). 0.7(안 고친 값) → **1.0**. 고친 값 v → v ÷ 0.7 (0.5 → 0.71, 1.0 → 1.43). 켤 때 로그 한 줄: \"PvP 피해 배율을 새 기준으로 옮겼습니다 (0.5 → 0.71)\".")
    A("- 새 키가 없으면 코드 기본값(= §12). 0.3.4 의 `Settings.upgrade` 와 같은 '안 고친 값이면 새 기본값' 방식을 `PvpConfig.from` 안에서 쓴다.")
    A("- 데이터: classes.yml 7개 스킬, items.yml 31개 무기 스킬에 `pvp_mult` (§6 표, JSON `skill_mult`).")
    A("- 플레이어: 바꿀 것 없음 (스탯 초기화는 combat_spec 의 `stats.role_reset_035` 하나로 충분).")
    A("- GDD §18.3 표를 새 키로 다시 쓰고, §18.6 'PvP 상태이상' 과 §18.7 'PvP 회복' 을 더한다. §9.2 끝에 'PvP 에서는 §18.6' 한 줄. combat_spec §8.1 의 표는 이 명세 §10.2 로 바꾼다.")
    A("")
    A("## 14. 코드 (구현 묶음)")
    A("")
    A(table(["파일", "할 일"], CODE))
    A("")
    A("## 15. 테스트")
    A("")
    A(table(["테스트", "확인"], TESTS))
    A("")
    A("## 16. 보이는 것")
    A("")
    A("- 메인 메뉴 'PvP 규칙' 칸 (MainMenu.pvpLore): 지금 4줄 + 바꿈 —")
    A("  - \"한 바퀴에 쓰러질 수 있습니다. 수비 장비(판금·방패·체력)는 PvP 에서도 더 버팁니다.\"")
    A("  - \"플레이어가 건 기절·속박은 짧고, 연달아 맞으면 더 짧아집니다.\"")
    A("  - \"PvP 중 회복 60% · 물약 36% · 오래 싸우면 회복이 점점 줄어듭니다.\"")
    A("  - 배율 숫자 줄(\"×0.7 · 최대 HP 35%\")은 지운다. 상한이 1 아래면(관리자) \"한 번에 최대 HP N%\" 를 지금처럼.")
    A("- /스탯 (StatsMenu): 요약 칸 아래 \"PvP 강인함 N% · PvP 체력 N (최대 HP + 완충 B)\".")
    A("- 액션바 'PvP' 알림·죽음 메시지는 그대로. 줄어든 상태이상은 따로 알리지 않는다(면역이면 대상 머리 위에 작은 '면역' 입자 한 번 — 선택).")
    A("- `/labadmin pvp`: 기준 배율 Lv20·35·50, 완충, 강인함 상한, 회복·물약·흡혈·보호막, 상태이상 규칙 요약, 직업 보정.")
    A("")
    A("## 17. 남은 위험")
    A("")
    A("- 시뮬레이터는 위치·시야를 확률로만 본다. 특히 사냥꾼(거리), 비전술사(속박 + 순간이동), 그림자(은신·등 뒤)는 손에 따라 크게 다르다 → 직업 보정은 테스트 서버에서 다시 본다.")
    A("- 완충 체력 때문에 고레벨에서 생 HP 의 PvP 값이 몹 상대보다 작다(Lv50 HP 비 0.36~0.73). VIT 는 강인함으로 일부 되찾는다. 'VIT 를 찍었는데 PvP 에서 덜 버틴다'는 말이 나오면 강인함 상한(0.40)을 올리고 완충을 줄이는 쪽으로.")
    A("- 수비↔수비는 여전히 길다(Lv50 중앙 약 1분). 긴 싸움 규칙(20초부터 회복 감소)이 끝을 낸다. 더 빨리 끝나야 하면 `long_fight.start` 를 15 로.")
    A("- 스킬 pvp_mult 는 기대 타수 추정(장판에 머무는 비율 등)에 기대고 있다. 실제로 피하기 쉬운 장판은 덜 깎아도 된다.")
    A("- 무기 스킬 데이터가 바뀌면(gear_spec 적용) `pv_sim.skill_mults` 를 다시 돌려 pvp_mult 를 다시 뽑는다(PvpSkillMultDataTest 가 어긋남을 알려 준다).")
    A("- 레벨 곡선(지수 2.35)은 Lv20·35·50 세 점에 맞춘 것이다. Lv25~30(궁극기가 막 열리는 구간)은 테스트 서버에서 한 번 확인.")
    A("- Lv35·50 에서 수비는 유리 대포의 한 바퀴를 맞고 54~56% 남는다(목표 30~50% 의 위쪽 끝을 조금 넘음). 이보다 덜 남게 하면(완충을 늘리면) Lv50 1:1 에서 유리가 60% 넘게 이긴다. 1:1 균형을 먼저 두었다. 수비가 너무 단단하다는 말이 나오면 `resilience.cap` 을 0.35 로.")
    md_text = "\n".join(md) + "\n"
    with open(os.path.join(D2, "pvp_spec.md"), "w", encoding="utf-8") as f:
        f.write(md_text)

    # ── JSON ──
    js = dict(
        version="pvp-p1 (0.3.5 안, combat_spec + look_spec 위)",
        config=dict(pvp=CONFIG_JSON),
        formulas=dict(
            level="L = max(공격자 레벨, 대상 레벨)",
            level_mult="m(L) = 2.0 × min(1, (20/L)^2.35) × damage_multiplier",
            buffer="B(L) = 42 × min(L, 20) + 12 × max(0, L − 20)",
            pool_factor="H / (H + B(L))  (H = 대상 최대 HP)",
            resilience="R = 0.40 × S / (S + 8 × L_대상), S = VIT + 방어",
            pvp_amount="원피해 × m(L) × class_damage[공격자] × skill pvp_mult × (1 − R) × H/(H+B)",
            formula="DamageFormula: 방어 × defense_weight(0) · 치명 = 1 + (cd − 1) × 0.6 · 피해 감소·표식·막기·보호막 그대로 · max_hit_ratio",
            heal="PvP 전투 중: (비율 몫 + 고정 몫 × H/(H+B)) × healing(0.6) [× potion 0.6] × 긴 싸움;  흡혈 = dealt × ls × lifesteal(0.5) × H/(H+B) × 긴 싸움 (healing 은 안 곱함)",
            shield="× 0.8 × 긴 싸움",
            long_fight="max(0.10, 1 − 0.025 × max(0, t − 20)), t = 이번 PvP 전투가 이어진 초 (8초 끊기면 0)",
            cc="시간 × (1−WIS, 기절·빙결 제외) × (1−0.40 판금4, 기절·속박·빙결) × PvP 배율 → 상한 → 줄어듦 [1, .5, .25, 0] (8초) → 0.2초 아래 무시; 기절·빙결 끝나면 2초 면역",
            skill_mult_rule="계수 c = 한 사람 기대 피해(스킬 위력 단위, skill_scale 포함); c > 2.5 이면 pvp_mult = floor20(2.5/c), 0.9 이하만",
        ),
        targets=dict(
            basic_hit_max=0.15, rotation_glass_vs_glass=[1.0, 1.3], rotation_glass_vs_glass_all_crit_min=1.0,
            rotation_glass_vs_guard=[0.5, 0.7], guard_rotation_vs_glass=[0.4, 0.7], duel_burst_vs_guard=[0.4, 0.6],
            longest_control_chain_s=1.5),
        skill_mult=R["skill_mult"],
        class_damage=CONFIG_JSON["class_damage"],
        cc_table=R["cc_rows"],
        unique_rule_changes=[dict(effect=r[0], before=r[1], after=r[2]) for r in [
            ["shield_bash", "stun → slow 40% 1s vs players", "stun stays; PvP CC rules"],
            ["imbue(frost)", "frozen → slow vs players", "frozen stays; PvP CC rules"],
            ["leech", "heal ×0.5", "global lifesteal 0.5 (no extra)"],
            ["sanctify", "self half when solo", "same + flat heal rule + healing 0.6"],
            ["feast", "procs on player kill", "same; healing 0.6"],
            ["ward_aura", "same party only", "same; shield 0.8 + long fight"],
            ["thorns", "×0.5, PvP cap", "×0.5; no cap (1.0); PvP formula"],
            ["hemorrhage", "crit capped by PvP cap", "crit_damage_scale 0.6"],
            ["rend/armor_break", "max 3 stacks vs players", "same"],
            ["multiplier bonuses", "+dmg ×0.5", "same"],
        ]],
        sim=dict(
            method="pv_build 6×3×2 builds · pv_sim rotation (all land, 3s, 0.25s/skill) · pv_duel 0.1s MC n=40 (final) / n=24 (compare), 90s cap",
            builds=R["builds"], targets={k: v["targets"] for k, v in CFG.items()},
            rotation={L: NEWC["rot"][L] for L in LV},
            duel_new={L: NEWC["duel"][L] for L in list(NEWC["duel"].keys())},
            duel_compare={name: {L: CFG[name]["duel"][L]["summary"] for L in LV} for name in ("0.3.4", "nocap")},
            cc_compare=R["cc_compare"], cross_level=R["cross"], curves=R["curves"], net=R["net"],
            class_before=R["class_before"],
        ),
        code_touch_points=[dict(file=a, change=b) for a, b in CODE],
        tests=[dict(name=a, checks=b) for a, b in TESTS],
        migration=dict(
            max_hit_ratio="0.35(안 고침) → 1.0, 그 밖은 그대로",
            damage_multiplier="0.7(안 고침) → 1.0 (뜻: 기본 대비 배율), 고친 값 v → v/0.7",
            new_keys="없으면 코드 기본값 = config.pvp",
            data="classes.yml skills[].pvp_mult 7 · items.yml weapon_skills[].pvp_mult 31",
            docs="GDD §18.3 다시 · §18.6 PvP 상태이상 · §18.7 PvP 회복 · §9.2 한 줄 · combat_spec §8.1 대체",
        ),
    )
    with open(os.path.join(D2, "pvp_spec.json"), "w", encoding="utf-8") as f:
        json.dump(js, f, ensure_ascii=False, indent=1, default=str)
    print("wrote", os.path.join(D2, "pvp_spec.md"), len(md_text), "chars;", os.path.join(D2, "pvp_spec.json"))


if __name__ == "__main__":
    main()
