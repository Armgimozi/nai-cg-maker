#!/usr/bin/env python3
"""
combat_spec.md + combat_spec.json 만들기 (TASK E).
  읽는 것: ce_tables.json (무기 표) · ce_kinds.json (피해 종류) · ce_classcheck.json (직업 비교)
           ce_results_<tag>.json (난이도 시뮬레이션, 기본 final2)
  python3 ce_spec.py [tag]
"""
import json
import math
import os
import sys

import ce_core as C
import ce_model as M
import ce_sim as X

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)
TAG = sys.argv[1] if len(sys.argv) > 1 else "final2"

T = json.load(open(os.path.join(HERE, "ce_tables.json"), encoding="utf-8"))
K = json.load(open(os.path.join(HERE, "ce_kinds.json"), encoding="utf-8"))
CC = json.load(open(os.path.join(HERE, "ce_classcheck.json"), encoding="utf-8"))
R = json.load(open(os.path.join(HERE, f"ce_results_{TAG}.json"), encoding="utf-8"))
P = X.P_FINAL
KO = {"guardian": "수호기사", "berserker": "광전사", "hunter": "사냥꾼", "arcanist": "비전술사", "priest": "사제", "shadow": "그림자"}
CL = list(KO)
TYPE_KO = {"sword_shield": "검방", "greatsword": "대검", "bow": "활", "staff": "지팡이", "scepter": "홀", "dagger": "단검"}
DIFF_KO = {"normal": "보통", "hard": "어려움", "nightmare": "악몽"}
PROF_KO = {"novice": "초보", "average": "보통 실력", "skilled": "숙련"}
STYLE_KO = {"melee": "근접", "ranged": "원거리", "caster": "시전"}
KIND_KO = {"physical": "물리", "magic": "마법", "hybrid": "혼합", "none": "피해 없음", "fixed": "고정"}

# 시나리오 이름
SC_OLD, SC_NEW = "old", "new"
SC_FIN = next((n for n in R["names"] if n.startswith("new:")), "new")
FINAL_HARD = None
if SC_FIN.startswith("new:"):
    FINAL_HARD = json.loads(SC_FIN[4:])["diffs"]["hard"]


def pct(v, signed=True):
    if v is None:
        return "-"
    return f"{v:+.0%}" if signed else f"{v:.0%}"


def _cell(x):
    return str(x).replace("|", "\\|")


def table(head, rows):
    out = ["| " + " | ".join(_cell(h) for h in head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join(_cell(x) for x in r) + " |")
    return "\n".join(out)


# ───────────────────────────── 시뮬레이션 결과 모으기 ─────────────────────────────

def res_index():
    idx = {}
    for row in R["rows"]:
        t, r = row["task"], row["result"]
        idx[tuple(t[:6])] = r
    return idx


IDX = res_index()


def solo_avg(name, diff, prof, fl):
    rs = [IDX.get((name, "solo", c, prof, diff, fl)) for c in CL]
    rs = [r for r in rs if r]
    if not rs:
        return None
    cl = [r["clear"] for r in rs]
    bt = [r["boss_t"] for r in rs if r["boss_t"]]
    rt = [r["room_t"] for r in rs if r["room_t"]]
    et = [r["elite_t"] for r in rs if r["elite_t"]]
    return dict(clear=sum(cl) / len(cl), lo=min(cl), hi=max(cl), boss=sum(bt) / len(bt) if bt else None,
                room=sum(rt) / len(rt) if rt else None, elite=sum(et) / len(et) if et else None,
                per={c: IDX.get((name, "solo", c, prof, diff, fl)) for c in CL})


def party(name, diff, prof, fl, comp):
    return IDX.get((name, "party", comp, prof, diff, fl))


# ───────────────────────────── 0.3.4 연타 계산 ─────────────────────────────

def spam_ratio(rate, cps):
    p, t = 1 / rate, 1 / cps
    if t >= p:
        return p / t
    mult = 0.2 + 0.8 * (t / p) ** 2
    return mult * p / t


def spam_table():
    rows = []
    for wt in ("dagger", "sword_shield", "scepter", "staff", "greatsword"):
        r = C.OLD_AS[wt]
        rows.append([TYPE_KO[wt], f"{r}회", f"{1/r:.2f}초"] + [pct(spam_ratio(r, c) - 1) for c in (3, 5, 8, 10)])
    return table(["옛 종류", "공속(초당)", "꽉 차는 시간", "초당 3번 누름", "5번", "8번", "10번"], rows)


# ───────────────────────────── 본문 ─────────────────────────────

def weapons_existing():
    return {k: v for k, v in T["weapons"].items() if v["src"] == "existing"}


def weapons_new():
    return {k: v for k, v in T["weapons"].items() if v["src"] != "existing"}


def shape_table():
    rows = []
    groups = [("무거움", ["executioner_axe", "great_maul", "great_axe", "greatsword", "flamberge", "war_scythe", "glaive", "cleaver", "war_spear"]),
              ("중간", ["warhammer", "morning_star", "mace", "broadsword", "longsword", "falchion", "sabre", "rapier"]),
              ("가벼움", ["tanto", "sickle", "kris", "fang_blade", "dagger", "katar", "stiletto"]),
              ("시전", ["staff_orb", "antler_staff", "staff_crystal", "staff_ring", "staff_spiral", "staff_fork", "lamp_crook", "censer_staff",
                       "sun_scepter", "bell_scepter", "thurible_rod", "scepter", "chalice_scepter", "chime_rod"]),
              ("활 (한 발 주기 = 당김 + 0.15초)", ["longbow", "composite_bow", "blade_bow", "bone_bow", "recurve_bow", "twin_bow", "horn_bow"])]
    for g, shapes in groups:
        cells = [f"`{s}` {C.SHAPE_INTERVAL[s]:.2f}초 (초당 {1 / C.SHAPE_INTERVAL[s]:.1f}회)" for s in shapes]
        rows.append([g, " · ".join(cells)])
    return table(["무게", "모양 → 기본 간격"], rows)


def existing_weapon_table():
    rows = []
    ex = weapons_existing()
    for wid, r in sorted(ex.items(), key=lambda kv: (kv[1]["level"], kv[1]["old_type"], kv[0])):
        tw = C.LORE_TWEAK.get(wid, 0)
        rows.append([f"`{wid}`", r["name"], r["level"], TYPE_KO[r["old_type"]], r["shape"],
                     f"{r['interval']:.2f}" + (f" ({tw:+.2f})" if tw else ""), f"{r['rate_per_s']:.1f}",
                     f"{r['old_damage'][0]}–{r['old_damage'][1]}", f"**{r['per_hit'][0]}–{r['per_hit'][1]}**",
                     f"{r['dps_old']:.1f} → {r['dps_new']:.1f}", f"{r['skill_power']:.1f}",
                     f"×{r['weapon_skill_factor']:.3f}" if r["weapon_skill_factor"] else "-"])
    return table(["무기", "이름", "Lv", "옛 종류", "모양", "간격(초)", "초당", "옛 피해", "새 한 방", "초당 피해(옛 → 새)",
                  "스킬 위력", "무기 스킬 배율"], rows)


def new_weapon_table():
    rows = []
    for wid, r in sorted(weapons_new().items(), key=lambda kv: (kv[1]["level"], kv[0])):
        rows.append([f"`{wid}`", r["name"], r["level"], r["shape"], f"{r['gear_spec_speed']}",
                     f"{r['gear_spec_damage'][0]}–{r['gear_spec_damage'][1]}", f"{r['interval']:.2f}",
                     f"**{r['per_hit'][0]}–{r['per_hit'][1]}**", f"{r['dps_new']:.1f}"])
    return table(["무기", "이름", "Lv", "모양", "gear_spec 공속", "gear_spec 피해", "새 간격", "새 한 방", "초당 피해"], rows)


def band_table():
    rows = []
    for b, v in T["band_spread"].items():
        rows.append([b, v["n"], f"{v['per_hit'][0]}–{v['per_hit'][1]} (×{v['per_hit'][2]})",
                     f"{v['skill_power'][0]}–{v['skill_power'][1]} (×{v['skill_power'][2]})", f"{v['dps'][0]}–{v['dps'][1]}"])
    return table(["구간", "무기 수(신화 제외, 새 무기 포함)", "한 방 피해 (최고÷최저)", "스킬 위력 (최고÷최저)", "초당 피해"], rows)


def future_table():
    rows = []
    for L, v in T["future"].items():
        rows.append([L, v["P_old"], v["c"], v["TP_new_common"]])
    return table(["무기 레벨 L", "P(L) (gear_spec 무기 힘)", "c(L)", "새 티어 위력 TP′ = P×c (일반)"], rows)


def class_det_table():
    rows = []
    for cls in CL:
        cells = [KO[cls]]
        for L in (10, 25, 45):
            d = CC["det"][f"{cls}|{L}"]
            cells.append(f"{pct(d['dps'])} / {pct(d['ehp'])}")
        d45 = CC["det"][f"{cls}|45"]
        cells.append(f"{pct(d45['noreset_dps'])} / {pct(d45['noreset_ehp'])}")
        rows.append(cells)
    return table(["직업", "Lv10 DPS / EHP", "Lv25", "Lv45", "초기화 안 하면 (Lv45)"], rows)


def class_sim_table():
    rows = []
    for cls in CL:
        cells = [KO[cls]]
        for fl in (1, 3, 6, 10):
            s = CC["sim"][f"{cls}|F{fl}"]
            cells.append(f"{pct(s['dps'])} / {pct(s['taken'])}")
        rows.append(cells)
    return table(["직업", "1층 (Lv1~)", "3층 (Lv10)", "6층 (Lv25)", "10층 (Lv45)"], rows)


def class_alloc_table():
    rows = []
    for cls in CL:
        cells = [KO[cls]]
        for L in (10, 25, 45):
            d = CC["det"][f"{cls}|{L}"]
            so, sn = d["old_stats"], d["new_stats"]
            f = lambda s: " ".join(f"{k}{s[k]}" for k in ("STR", "DEX", "INT", "VIT", "WIS") if s[k] >= 15)  # noqa: E731
            cells.append(f"{f(so)} → {f(sn)}")
        rows.append(cells)
    return table(["직업", "Lv10 (옛 → 새, 장비 줄 포함)", "Lv25", "Lv45"], rows)


def tax_table():
    rows = []
    for L in (10, 25, 45):
        for armor in ("heavy", "light"):
            cells = [f"Lv{L}", {"heavy": "판금(VIT)", "light": "가죽(DEX)"}[armor]]
            for req in ("DEX", "VIT", "WIS", "LUK"):
                a = T["tax"].get(f"L{L}|{armor}|{req}|single")
                b = T["tax"].get(f"L{L}|{armor}|{req}|split")
                cells.append(f"{pct(a['dps_vs_str']) if a else '못 낌'} → {pct(b['dps_vs_str']) if b else '못 낌'}")
            rows.append(cells)
    return table(["레벨", "방어구", "DEX 요구 (하나 → 나눔)", "VIT 요구", "WIS 요구", "LUK 요구"], rows)


def ttk_table():
    rows = []
    for fl in (1, 3, 5, 7, 10):
        cells = [f"{fl}층 (Lv{CC['ttk'][f'F{fl}|guardian']['level']})"]
        for cls in CL:
            t = CC["ttk"][f"F{fl}|{cls}"]
            cells.append(f"{t['mob_old']} → {t['mob_new']}")
        rows.append(cells)
    return table(["층", *[KO[c] for c in CL]], rows)


def difficulty_tables():
    out = []
    for d in ("normal", "hard", "nightmare"):
        profs = ("novice", "average", "skilled") if d == "normal" else ("average", "skilled")
        rows = []
        for p in profs:
            for nm, lab in ((SC_OLD, "0.3.4"), (SC_NEW, "새 모델"), (SC_FIN, "새 모델 + 재조정")):
                if nm == SC_FIN and nm == SC_NEW:
                    continue
                if nm == SC_FIN and d != "hard":
                    continue
                cells = [PROF_KO[p], lab]
                for fl in (1, 3, 5, 7, 10):
                    a = solo_avg(nm, d, p, fl)
                    cells.append(f"{a['clear']:.0%} ({a['lo']:.0%}–{a['hi']:.0%})" if a else "-")
                rows.append(cells)
        out.append(f"**{DIFF_KO[d]}** — 솔로, 직업 6개 평균 클리어율 (가장 낮은 직업–가장 높은 직업)\n\n" +
                   table(["실력", "판", "1층", "3층", "5층", "7층", "10층"], rows))
    return "\n\n".join(out)


def party_tables():
    rows = []
    for d in ("normal", "hard", "nightmare"):
        for p in ("average", "skilled"):
            for nm, lab in ((SC_OLD, "0.3.4"), (SC_NEW, "새 모델")):
                cells = [DIFF_KO[d], PROF_KO[p], lab]
                for fl in (1, 3, 5, 7, 10):
                    a = party(nm, d, p, fl, "A")
                    b = party(nm, d, p, fl, "B")
                    cells.append(f"{a['clear']:.0%} / {b['clear']:.0%}" if a and b else "-")
                rows.append(cells)
    return table(["난이도", "실력", "판", "1층 (A / B)", "3층", "5층", "7층", "10층"], rows)


def time_tables():
    rows = []
    for d in ("normal", "nightmare"):
        for p in ("average", "skilled"):
            for nm, lab in ((SC_OLD, "0.3.4"), (SC_NEW, "새 모델")):
                cells = [DIFF_KO[d], PROF_KO[p], lab]
                for fl in (1, 3, 5, 7, 10):
                    a = solo_avg(nm, d, p, fl)
                    cells.append(f"{a['room']:.0f} · {a['elite']:.0f} · {a['boss']:.0f}" if a and a["boss"] else
                                 (f"{a['room']:.0f} · {a['elite']:.0f} · -" if a else "-"))
                rows.append(cells)
    return table(["난이도", "실력", "판", "1층 방·정예·보스(초)", "3층", "5층", "7층", "10층"], rows)


def boss_class_table():
    rows = []
    for cls in CL:
        cells = [KO[cls]]
        for fl in (1, 3, 5, 7, 10):
            o = IDX.get((SC_OLD, "solo", cls, "skilled", "normal", fl))
            n = IDX.get((SC_NEW, "solo", cls, "skilled", "normal", fl))
            cells.append(f"{(o or {}).get('boss_t') or '-'} → {(n or {}).get('boss_t') or '-'}")
        rows.append(cells)
    return table(["직업 (보통·숙련·솔로)", "1층 보스(초)", "3층", "5층", "7층", "10층"], rows)


def class_skill_kind_table():
    rows = []
    for cls in CL:
        for s in C.CLASSES[cls]["skills"]:
            sid = s["id"]
            rows.append([KO[cls], f"`{sid}`", s["name"], KIND_KO[K["class_skills"][sid]], K["class_skill_notes"][sid]])
    return table(["직업", "스킬 id", "이름", "종류", "비고"], rows)


def weapon_skill_kind_summary():
    from collections import Counter
    ws = {k: v for k, v in K["weapon_skills"].items() if K["weapon_skill_detail"][k].get("src") != "gear_spec_new"}
    cnt = Counter(ws.values())
    hy = [f"`{k}`" for k, v in ws.items() if v == "hybrid"]
    lines = [f"기존 무기 스킬 {len(ws)}개: 물리 {cnt['physical']} · 마법 {cnt['magic']} · 혼합 {cnt['hybrid']} · 피해 없음 {cnt['none']}"
             + (f" · 고정 {cnt['fixed']}" if cnt.get("fixed") else "") + ". 새 무기(gear_spec) 스킬까지 모두 JSON `skill_kinds.weapon_skills` 에 있다.",
             "", "혼합(hybrid) 스킬: " + " · ".join(hy)]
    return "\n".join(lines)


# ───────────────────────────── 본문 조립 ─────────────────────────────

IV_MIN = min(v["interval"] for v in T["weapons"].values())
IV_MAX = max(v["interval"] for v in T["weapons"].values())


def build_md():
    ex = weapons_existing()
    nw = weapons_new()
    chk = T["check"]
    f1n_old = solo_avg(SC_OLD, "nightmare", "skilled", 1)
    f1n_new = solo_avg(SC_NEW, "nightmare", "skilled", 1)
    n1a_old = solo_avg(SC_OLD, "normal", "average", 1)
    n1a_new = solo_avg(SC_NEW, "normal", "average", 1)
    h1s_old = solo_avg(SC_OLD, "hard", "skilled", 1)
    h1s_new = solo_avg(SC_NEW, "hard", "skilled", 1)
    h1s_fin = solo_avg(SC_FIN, "hard", "skilled", 1)
    h1a_old = solo_avg(SC_OLD, "hard", "average", 1)
    h1a_new = solo_avg(SC_NEW, "hard", "average", 1)
    h1a_fin = solo_avg(SC_FIN, "hard", "average", 1)
    hard_line = (f"어려움 HP ×1.4 → **×{FINAL_HARD['hp']}** (1층 숙련 {h1s_old['clear']:.0%} → 새 모델 {h1s_new['clear']:.0%} → 재조정 {h1s_fin['clear']:.0%}, "
                 f"보통 실력 {h1a_old['clear']:.0%} → {h1a_new['clear']:.0%} → {h1a_fin['clear']:.0%})") if FINAL_HARD else "어려움 그대로"

    md = []
    A = md.append
    A("# 미궁 라비린스 — 전투 모델 다시 짜기 (TASK E, 0.3.5 안)")
    A("")
    A("주인 결정 세 가지를 하나로 묶은 기초 명세다. 다른 설계자(장비·고유 효과)가 이 숫자를 그대로 쓴다.")
    A("")
    A("1. 공격 게이지를 없앤다. 서버가 **무기마다 공격 간격**을 지킨다. 누를 때마다 온전한 피해가 들어간다.")
    A("2. 툴팁의 **공격력 = 한 방 피해**. 그 아래 한 줄 **공격 속도 초당 N회**.")
    A("3. **힘(STR) = 물리 공격력, 지능(INT) = 마법 공격력.** 민첩(DEX)은 공격력을 올리지 않는다(치명·공격 속도·회피).")
    A("")
    A("- 데이터: `combat_spec.json` (무기 간격·한 방 피해 237개 · 공식 · 스킬 피해 종류 · 난이도 · 옮기기 · 시뮬레이션 표)")
    A("- 계산 스크립트(모두 `tools/`): `ce_core.py`(무기 간격·재기준 공식) · `ce_model.py`(직업 기대값 모델) · `ce_sim.py`(난이도 시뮬레이터, 0.3.4 r4 sim 위) ·"
      " `ce_run.py`(전후 실행) · `ce_tables.py` · `ce_kinds.py` · `ce_classcheck.py` · `ce_spec.py`(이 문서). `python3 tools/ce_spec.py` 로 다시 만든다.")
    A("- 무기 종류는 이미 없앤다는 전제다(gear_spec). 이 문서의 '옛 종류'는 0.3.4 숫자를 옮길 때만 쓰는 이름이다.")
    A("")
    A("## 0. 한눈에")
    A("")
    A("**주인 질문 — \"민첩이 공격 속도에 영향을 미치는가?\" → 그렇다.** 민첩 1점마다 공격 속도 +0.5%. 무기 간격이 그만큼 짧아진다(활은 당기는 시간이 짧아진다). "
      "공격 속도 합계 상한은 지금처럼 **+60%** (간격 ÷ 1.6). 어떤 경우에도 간격은 **0.25초**보다 짧지 않다. 툴팁 숫자는 민첩을 넣기 전 값이다.")
    A("")
    A(table(["항목", "지금 (0.3.4)", "바꾼 뒤"], [
        ["근접 공격", "바닐라 게이지 — 피해 × (0.2 + 0.8×충전²), 연타 손해(초보) · 연타 이득(무적 시간이 없어서)", "게이지 숨김. 서버가 무기 간격을 지킴. 맞으면 언제나 온전한 피해"],
        ["공격 간격", "종류마다 하나 (config `weapon_attack_speed`)", f"**무기마다** (모양 기본값 + 무기마다 조정, {IV_MIN:.2f}~{IV_MAX:.2f}초)"],
        ["이른 클릭", "약한 공격이 나감", "간격 끝 0.35초 안이면 **한 번 기억했다가** 끝나는 순간 넣음, 더 이르면 작은 '휙' 소리"],
        ["툴팁", "\"피해 23 (21–24)\" + 종류 이름", "\"⚔ 공격력 23 (21–24) · 물리\" + \"공격 속도 초당 1.5회\" (종류 이름 없음)"],
        ["공격력 스탯", "무기 × (1 + 2% × 직업 주스탯 혼합)", "무기 × (1 + **1%** × STR) 물리 · (1 + **1%** × INT) 마법"],
        ["민첩", "공격력(사냥꾼·그림자) + 치명 0.15%p + 공속 0.4%", "치명 **0.25%p** + 공속 **0.5%** (활 당김 포함) + 회피 **0.1%p**"],
        ["직업 스킬", "공격력 × 배율 × 추천 무기 환산", "**스킬 위력** × 직업 배율 × (1 + 1%×STR/INT) × 배율"],
        ["무기 스킬", "공격력 × 배율", "스킬 위력 × (1 + 1%×STR/INT) × 배율 (데이터 배율을 옛 종류만큼 옮김)"],
        ["무기 숫자", "131개, 종류 배율로 만든 피해", "131개 새 한 방 피해 + 간격, 초당 피해는 0.3.4 숙련과 같게 × 스탯 계수 보정 c(L)"],
        ["직업", "추천 무기 −10% 재사용", "모든 직업 스킬 재사용 ×0.9 · 매의 눈 +30% · 급소 찌르기 치명 피해 +40% · 은총 마법 피해 +10%"],
        ["난이도", "보통 1.0 · 어려움 1.4/1.3/0.9 · 악몽 1.8/1.6/0.85", hard_line + ", 나머지 그대로"],
    ]))
    A("")
    A(f"- 직업 6개 × Lv10·25·45, 알맞은 분배: 초당 피해·유효 HP 모두 0.3.4 의 ±10% 안 (사제 Lv10 피해 +11% 하나만 살짝 넘음 — 시뮬레이터 3층 +14%). §6.")
    A(f"- 악몽 1층 솔로 숙련 클리어율 {f1n_old['clear']:.0%} → {f1n_new['clear']:.0%} (목표 약 50%). 보통 1층 보통 실력 {n1a_old['clear']:.0%} → {n1a_new['clear']:.0%}. §9.")
    A(f"- 무기 237개(기존 {chk['existing']} + 새 {chk['new']}) 모두 간격·한 방 피해를 정했다. 정수로 반올림한 뒤 초당 피해 오차 평균 {chk['dps_rounding_err_mean']:.1%} · 최대 {chk['dps_rounding_err_max']:.1%}.")
    A("- 느린 무기가 스킬을 독차지하지 않는다: 같은 5레벨 구간에서 한 방 피해는 3~3.7배까지 벌어지지만 스킬 위력은 1.2~1.6배(희귀도·레벨 차이뿐). §5.6.")
    A("- 기존 플레이어: 스탯 무료 초기화 1회(새 깃발). 가진 무기의 굴림은 같은 '위치'로 새 범위에 옮긴다. config 는 안 고친 값만 새 값으로. §10.")
    A("")

    # 1
    A("## 1. 지금(0.3.4) 무엇이 문제인가")
    A("")
    A("### 1.1 게이지와 연타")
    A("")
    A("`CombatListener.meleeMult` = 0.2 + 0.8 × 충전². 미궁 몹·보스·PvP 는 바닐라 피해를 취소하고 직접 깎는다. 그래서 바닐라 무적 시간(10틱)이 생기지 않는다. "
      "누를 때마다 피해가 들어간다. 결과는 아래와 같다 (꽉 찬 공격을 기다려 친 숙련자 = 0%).")
    A("")
    A(spam_table())
    A("")
    A("- 천천히 누르는 사람은 손해를 본다(초보). 아주 빠르게 연타하면 오히려 더 세다. 느린 무기일수록 더하다(대검 초당 8번 +78%).")
    A("- 모든 무기가 연타 속도로 휘둘러진다. 주인이 본 \"연타하면 다 똑같다\"가 이것이다.")
    A("- 밸런스(무기 피해·0.3.2/0.3.4 시뮬레이터)는 '꽉 찬 공격' 기준으로 만들어졌다. 새 모델은 그 기준을 그대로 지킨다. 연타 이득은 사라지고, 손해도 사라진다.")
    A("")
    A("### 1.2 스탯")
    A("")
    A("`StatCalculator.primaryMix` 가 직업마다 공격력 스탯을 고른다(수호기사 STR0.6+VIT0.4, 사냥꾼 DEX, 사제 INT0.5+WIS0.5, 그림자 DEX0.7+LUK0.3 …). "
      "사냥꾼·그림자의 DEX 는 공격력·치명·공속(근접만)·요구 능력치(활·단검·가죽)를 한꺼번에 맡았다. 이번에 STR/INT 만 공격력이 되면 이 몫이 빠진다. §6 에서 메운다.")
    A("")
    A("### 1.3 무적 시간")
    A("")
    A("- 미궁 몹·보스(`HealthPool`): 이벤트를 취소하므로 바닐라 무적 시간이 없다. 지금도, 앞으로도 공격 간격은 **공격하는 쪽**이 지킨다.")
    A("- 플레이어(몹·PvP 에게 맞음): `setHealth` 로 깎아서 무적 시간이 없다. 죽는 한 방만 바닐라 `damage()` 경로.")
    A("- **미궁 밖 바닐라 몹**: `DamageService.applyVanilla` 가 `target.damage()` 를 불러 무적 10틱이 생긴다. 0.5초보다 빠른 무기는 두 번째 타격이 "
      "'지난 피해보다 큰 만큼만' 들어가 거의 0 이 된다 → §8.2 에서 고친다.")
    A("")

    # 2
    A("## 2. 새 공격 흐름")
    A("")
    A("### 2.1 근접·시전 기본 공격")
    A("")
    A("1. 미궁 무기(또는 맨손)를 들면 바닐라 `ATTACK_SPEED` 기본값을 **1024** 로 둔다. 게이지가 늘 꽉 차 있어 화면에 보이지 않는다. "
      "바닐라 무기(나무 검·도끼 등, `VanillaWeapon`)는 지금처럼 바닐라 속도·바닐라 게이지를 쓴다(미궁 장비가 아니다).")
    A("2. 플레이어마다 시계 하나: `nextReady`(다음 공격 가능 시각, ms). 공격 간격 = 무기 `attack.interval` ÷ (1 + 공격 속도), 0.25초 아래로는 안 내려감.")
    A("3. `PrePlayerAttackEntityEvent`(대상이 살아 있는 적일 때):")
    A("   - **지금 ≥ nextReady − 50ms** → 그대로 통과. 바닐라 공격 → `EntityDamageByEntityEvent` → 피해 = 공격력 × 1.0 (떨어지며 쳤으면 ×1.2). "
      "다음 시각 = (nextReady 가 50ms 안쪽이었으면 nextReady, 아니면 지금) + 간격. 이렇게 하면 틱(50ms) 반올림으로 속도가 새지 않는다.")
    A("   - **너무 이름** → 이 공격 이벤트를 취소(피해 없음, 바닐라 '약한 공격' 소리도 없음). 남은 시간이 **0.35초 이하**(간격이 더 짧으면 간격)면 그 대상을 "
      "**한 번 기억**한다(새 클릭이 오면 대상만 바꿈). 0.35초보다 이르면 기억하지 않고 '휙' 소리만 낸다.")
    A("4. 기억한 클릭은 1틱마다 본다. nextReady 가 되면 아래를 모두 만족할 때만 넣는다. 하나라도 어긋나면 조용히 버린다.")
    A("   - 대상이 살아 있고 같은 월드, 여전히 적(`TargetFilter.isEnemy`)")
    A("   - 거리: 눈 → 대상 히트박스 가장 가까운 점 ≤ `ENTITY_INTERACTION_RANGE`(기본 3.0) + 0.3")
    A("   - 시야: 바라보는 방향과 대상 중심 사이 각도 ≤ 50°, 그리고 `hasLineOfSight`")
    A("   - 클릭한 지 0.6초 안, 손에 든 무기가 그대로")
    A("   넣을 때: `player.swingMainHand()`(휘두르는 모습) + 바닐라와 같은 타격 소리(치명이면 치명 소리) + 같은 피해 경로(`DamageContext` 기본 공격, PvP 넉백·발화 포함). "
      "다음 시각 = nextReady + 간격.")
    A("5. 허공 클릭은 아무것도 하지 않는다(시계도 안 씀). 무기 스킬 입력(웅크리기+좌클릭 등)은 기본 공격 시계와 따로다.")
    A("")
    A("결과: 천천히 눌러도, 마구 눌러도 무기 간격마다 한 번 온전히 맞는다. 무거운 무기는 눈에 띄게 느리게, 가벼운 무기는 빠르게 휘두른다.")
    A("")
    A("### 2.2 이른 클릭이 '죽은 클릭'이 되지 않게 (UX)")
    A("")
    A("- 기억창 0.35초: 가벼운 무기(0.45초)는 거의 언제 눌러도 맞고, 무거운 무기(1.0초)는 박자 끝쪽 클릭이 맞는다. 너무 늦게 엉뚱한 곳에 맞는 일은 없다(거리·시야를 다시 봄).")
    A("- 너무 이른 클릭: 본인에게만 `entity.player.attack.nodamage`(음량 0.25, 높이 = 1.6 − 0.6×간격 → 가벼운 무기는 높고 무거운 무기는 낮은 소리), 150ms 에 한 번까지.")
    A("- 큰 글씨·액션바 없음. 게이지 대신 무기 휘두름 모습과 소리가 박자를 알려 준다.")
    A("- (하지 않음) 아이템 쿨다운 덮개: 무기가 모두 PAPER 라 우클릭 무기 스킬까지 막힌다.")
    A("")
    A("### 2.3 무기를 바꿀 때")
    A("")
    A("손에 든 미궁 무기가 바뀌면(칸 바꿈·양손 바꿈·줍기) nextReady = max(nextReady, 지금 + 새 무기 간격 × 0.5), 기억한 클릭은 지운다. "
      "빠른 무기로 치고 바로 무거운 무기로 바꿔 치는 꼼수를 막는다(바닐라도 바꾸면 게이지가 비었다).")
    A("")
    A("### 2.4 점프 치명 · 휩쓸기 · 넉백")
    A("")
    A("- 점프 치명(떨어지며 침): ×1.2 그대로. 통과한 바닐라 공격은 `isCritical()`, 기억했다 넣는 공격은 같은 조건(떨어지는 중·땅에 안 닿음·물/사다리/탈것 아님·실명 아님·달리지 않음)을 서버가 본다. "
      "무거운 무기는 매번 맞추기 쉽고 가벼운 무기는 절반쯤 → DPS 등가에는 넣지 않는다(기술 보너스).")
    A("- 휩쓸기: 미궁 무기는 PAPER 라 바닐라 휩쓸기가 없다(지금과 같음). 바닐라 검의 휩쓸기 ×0.35 규칙은 그대로. 여러 마리 치기는 고유 효과 `cleave` 몫.")
    A("- PvP 넉백: 지금 공식 그대로. '꽉 찬 공격의 달리기 넉백'은 통과한 공격이면 언제나 꽉 찬 공격으로 친다.")
    A("")
    A("### 2.5 활 (당기기 그대로)")
    A("")
    A("- 활의 `attack.interval` = **한 발 주기** = 끝까지 당기는 시간 + 0.15초(놓고 다시 메기기). 툴팁 '초당 N회' = 1 ÷ 한 발 주기.")
    A("- 끝까지 당기는 시간 = (interval − 0.15) ÷ (1 + 공격 속도), 0.25초 하한. 민첩·공속이 활을 빠르게 한다(0.3.4 에서는 활에 공속이 안 들었다).")
    A("- 당김 세기는 서버가 잰다: x = 당긴 시간 ÷ 끝까지 당기는 시간 (최대 1), 세기 = (x² + 2x) ÷ 3 (바닐라 곡선). 당긴 시간 = `LivingEntity#getActiveItemUsedTime()`"
      " (없으면 우클릭 시작 틱을 기억). 피해 = 공격력 × 세기(최소 0.1). 화살 속도 = 바닐라 최대 속도 × 세기. 세기 1 이면 `setCritical(true)`.")
    A("- 0.3.4 의 '끝까지 당긴 화살 ×1.25(치명 화살)'는 **한 방 피해 숫자 안에 넣었다**. 이제 툴팁 공격력 = 끝까지 당긴 화살 한 발.")
    A("- 끝까지 당겨지면 본인에게만 작은 '탁' 소리(`item.crossbow.loading_end`, 음량 0.3) — 바닐라 활 그림은 늘 1초라서.")
    A("- 덜 당겨 연사해도 이득이 없다: x = 0.5 면 세기 0.42, 시간당 피해는 끝까지 당김의 74%.")
    A("- 활 무기 스킬 '웅크리고 당겨 쏘기'(SNEAK_RIGHT)의 charge 도 같은 서버 세기 x 를 쓴다. 활은 '이른 클릭 기억'이 없다(당기기가 곧 박자).")
    A("")
    A("### 2.6 시전 무기")
    A("")
    A("- 기본 공격은 지금처럼 **근접 휘두르기**(기본 투사체는 지금 없다). 피해 종류는 **마법**(INT). 간격·기억·소리 규칙은 근접과 같다.")
    A("- 선택 사항(새 무기용): `attack.projectile: {speed: 1.6, range: 14, radius: 0.4, fx: <fx 이름>}` 이 있으면, 통과한(또는 기억했다 넣는) 클릭마다 "
      "작은 마법탄을 쏜다. 처음 맞은 적 하나에 한 방 피해. 허공 클릭도 시계가 준비됐으면 쏜다. 같은 간격을 쓴다. 기존 131개에는 넣지 않는다.")
    A("")
    A("### 2.7 맨손")
    A("")
    A("맨손 = 한 방 3, 간격 0.625초(config `weapon_attack_speed.none: 1.6` 의 역수), 물리. 요구 능력치를 못 채운 무기도 맨손으로 친다(지금 규칙).")
    A("")
    A("### 2.8 바닐라 무기 · 삼지창")
    A("")
    A("바닐라 검·도끼·삼지창은 미궁 장비가 아니다. 바닐라 공격 속도·게이지·피해를 그대로 쓴다(지금처럼 미궁 몹에게는 게이지 배율, 던진 삼지창은 피해 8 × 물리 배율). "
      "간격 시계는 미궁 무기와 맨손에만 건다.")
    A("")

    # 3
    A("## 3. 공식")
    A("")
    A("```")
    A("W        = 무기 한 방 피해 (굴린 값 × 강화 배율)                    맨손 3")
    A("물리 배율  = 1 + 0.01 × STR          마법 배율 = 1 + 0.01 × INT        혼합 = 1 + 0.01 × (STR + INT) / 2")
    A("공격력    = W × (무기 attack.kind 의 배율)                          ← 툴팁·/스탯 의 '공격력'")
    A("기본 공격 = 공격력 × (점프 치명 1.2) × (활 세기) × (매의 눈 1.30: 사냥꾼, 끝까지 당긴 화살)")
    A("")
    A("공격 속도 AS = 0.005 × DEX + 장비·버프,  −50% ~ +60%")
    A("실제 간격   = max(0.25, interval ÷ (1 + AS))       활: 당김 = max(0.25, (interval − 0.15) ÷ (1 + AS))")
    A("치명 확률   = 0.05 + 0.0025 × DEX + 0.0025 × LUK + 장비      (상한 75%)")
    A("치명 피해   = 1.5 + 장비 (+ 그림자 0.40)")
    A("회피       = 0.001 × DEX + 장비                              (상한 40%, 보스 패턴은 회피 불가 — 지금과 같음)")
    A("")
    A("K(방식, 간격) = 근접 1.47 − 0.143 × max(0, 1/간격 − 1.5) · 원거리 1.413 · 시전 1.22      (같은 단계 무기 1 의 '설계 초당 피해')")
    A("스킬 위력 SP = (W 가운데값 ÷ interval) ÷ K × skill_power_mult(시전 1.05, 그 밖 1.0) × (1 + 0.5 × AS)")
    A("직업 스킬   = SP × 직업 skill_scale × (스킬 종류의 배율) × 스킬 배율 × (1 + skill_damage) × (사제 마법 +10%)")
    A("무기 스킬   = SP × (스킬 종류의 배율) × 새 배율 × (1 + skill_damage)        새 배율 = 옛 배율 × weapon_skill_factor")
    A("지속 피해   = 부여할 때 SP × (그 상태이상 종류의 배율) × 비율 (× 직업 skill_scale: 직업 스킬이 건 것)  — 방어 무시 TRUE, 지금과 같음")
    A("최종       = DamageFormula 그대로 (주는 피해 버프 → 회피 → 치명 → 방어 100/(100+방어) → 피해 감소 → 막기)")
    A("```")
    A("")
    A("### 3.1 왜 1%/점인가 (0.3.4 는 2%/점)")
    A("")
    A("- STR/INT 하나가 피해를 다 맡으면, 요구 능력치(무기 2.5×(L−1) + 방어구 2.5×(L−1))가 다른 스탯인 빌드(가죽+활, 천+홀, 판금+DEX 무기)가 크게 진다. "
      "2%/점이면 사냥꾼·그림자가 Lv45 에서 −35~−45%, 사제 −37% (`ce_grid.py` 첫 실행).")
    A("- 1%/점으로 낮추고 무기 숫자를 그만큼 올린다(c(L)). 같은 레벨의 '정렬된'(주 스탯을 3:2 로 찍은) 빌드는 피해가 그대로다. 정렬 안 된 빌드의 손해가 절반으로 준다.")
    A("- c(L) = (1 + 0.02 S) ÷ (1 + 0.01 S),  S = 8 + 3.6 × (L + 3) — 그 무기를 쓰는 동안(무기 레벨 +3)의 정렬된 주 스탯(분배 + 장비 줄). "
      "Lv1 무기 ×1.18 · Lv10 ×1.37 · Lv25 ×1.52 · Lv45 ×1.63.")
    A("- 대가: 무기를 오래 들수록 레벨업 피해 상승이 조금 완만하다(무기 레벨 +8 에서 −4~−8%). 대신 새 무기로 바꿀 때 오르는 폭이 커진다(장비를 늘리는 이번 방향과 맞음).")
    A("")
    A("### 3.2 민첩 (주인 질문)")
    A("")
    A("- 공격 속도 0.4% → **0.5%/점**, 치명 0.15%p → **0.25%p/점**, 회피 **0.1%p/점(새로)**. 공격 속도 상한 +60% 그대로(민첩 120 + 장비면 닿는다).")
    A("- 왜 올리나: 민첩이 공격력에서 빠진 만큼 '빠르고 날카롭고 잘 피하는' 몫을 키운다. 가죽 방어구(DEX 요구)를 입는 빌드가 남는 포인트로 STR 을 찍어도 버틴다.")
    A("- 힘만 찍는 빌드가 민첩을 찍는 이득도 커지지만(광전사 최적 분배가 STR 쪽 80%→70%), 같은 분배 기준 광전사 피해는 +0~4% 로 거의 그대로다.")
    A("- 행운은 그대로(치명 0.25%p·드롭·골드). 이제 치명만 보면 민첩과 같고, 행운은 전리품 쪽 스탯이다.")
    A("")
    A("### 3.3 스킬 위력 — 느린 무기가 스킬을 독차지하지 않게")
    A("")
    A("- 한 방 피해로 스킬을 치면 같은 단계 대검(1.0초)이 단검(0.45초)의 2.2배다. 초당 피해(한 방 × 초당)로 치면 시전 무기가 손해다(설계상 기본 공격이 약함).")
    A("- 그래서 스킬 위력 = 무기의 **초당 피해 등가 ÷ K(방식)**. 같은 단계면 대검·단검·활·지팡이의 스킬 위력이 같다(희귀도·레벨 차이만). gear_spec 1.4 의 skill_power 와 같은 생각이다.")
    A("- (1 + 0.5 × 공격 속도): 주인이 예로 든 '피해 × 공격 속도'를 반만 넣었다. 빠른 손(민첩·공속 장비)이 스킬에도 조금 보탬이 된다. "
      "공속 +60% 면 스킬 +30%. 이게 없으면 사냥꾼·그림자의 스킬이 Lv45 에서 −20~−30% 로 떨어진다(시뮬레이터, §6.2).")
    A("- 무기 간격은 툴팁 값(민첩 전)을 쓴다. 강화는 W 를 키우므로 스킬 위력도 같이 오른다(지금 공격력과 같음).")
    A("- 툴팁에는 넣지 않는다(주인: 공격력 + 공격 속도 두 줄). /스탯 화면과 도감 자세히 보기에 '스킬 위력'을 보여 준다.")
    A("")
    A("### 3.4 혼합(hybrid)")
    A("")
    A("- 한 스킬에 물리 부분과 마법 부분이 같이 있으면(예: 베고 번개, 베고 불태움) **부분마다 자기 배율**로 친다. 그 스킬 꼬리표는 hybrid.")
    A("- 한 번의 피해 자체가 둘 다인 경우(새 무기용, `damage_type: hybrid`)는 (STR + INT) ÷ 2 로 친다. 기존 무기에는 없다.")
    A("- 최대 HP 비율 피해·되돌림(가시·맹세 분담)은 '고정'(fixed): 스탯을 안 탄다.")
    A("")
    A("### 3.5 고유 효과(unique_spec)에 쓰는 기준")
    A("")
    A("- **기본 공격 한 대마다 켜지는 것**(적중·치명·N번째): '공격력 X%' = 한 방 공격력 기준. 초당 횟수가 간격에 비례하니 무기 속도와 상관없이 공정하다 "
      "(`cleave`·`flurry`·`shield_bash`·`chain_spark`·`sanctify`·`leech`).")
    A("- **한 대마다가 아닌 것**(처치·주기·스킬 사용 뒤 1회·지속 피해 세기): '스킬 위력 X%' 로 바꾼다 (`death_burst`·`overcharge`·`rend`·`imbue` 의 지속 피해). "
      "한 방 기준이면 느린 무기가 2배 세진다.")
    A("- **확률로 거는 상태이상**(imbue 25%): 초당 횟수를 맞춘다 — 실제 확률 = 기준 × (간격 ÷ 0.67), 최대 ×1.5.")
    A("- 곱하기 보정(`execute`·`first_strike`·`backstab`…)은 그대로.")
    A("")

    # 4
    A("## 4. 피해 종류 꼬리표")
    A("")
    A("`DamageType`(MELEE·RANGED·MAGIC·TRUE)은 '어떻게 맞았나'로 남긴다(패시브·오브젝트 판정에 쓰임). 그 옆에 `DamageKind`(PHYSICAL·MAGIC·HYBRID·FIXED)를 새로 둔다. "
      "기본값: MELEE·RANGED → 물리, MAGIC → 마법, TRUE → 고정. 무기 기본 공격·무기 스킬의 기본값은 무기 `attack.kind`(근접·원거리 = 물리, 시전 = 마법).")
    A("")
    A("### 4.1 직업 스킬 24개")
    A("")
    A(class_skill_kind_table())
    A("")
    A("패시브: 피의 분노·비전 공명·급소 찌르기는 모든 종류에 곱하는 보정, 매의 눈은 물리(끝까지 당긴 화살), 은총의 새 줄은 마법.")
    A("")
    A("### 4.2 무기 스킬")
    A("")
    A(weapon_skill_kind_summary())
    A("")
    A("규칙: `mechanics` 의 효과마다 `damage_type` → 그대로, `magic: true` → 마법, `lightning` → 마법, 없으면 무기 기본값. 지속 효과 `ignite`(불태움) → 마법, `poison`·`bleed`·`wither` → 물리, "
      "`percent` → 고정. `riposte` 반격 = 물리 + 되돌림 고정, `sanctuary`·`mend`·`empower` = 피해 없음(숫자 damage 가 없을 때).")
    A("")
    A("### 4.3 상태이상 지속 피해")
    A("")
    A(table(["상태이상", "종류"], [[k, v] for k, v in K["status"].items()]))
    A("")
    A("### 4.4 고유 효과 26개 (unique_spec)")
    A("")
    A(table(["id", "종류", "기준"], [[f"`{k}`", K["unique_effects"][k], K["unique_notes"][k]] for k in K["unique_effects"]]))
    A("")

    # 5
    A("## 5. 무기 숫자")
    A("")
    A("### 5.1 모양별 기본 간격")
    A("")
    A(shape_table())
    A("")
    A("- 0.3.4 종류 주기와 비교: 검방 0.67(같음) · 대검 1.05 → 0.90~1.20 · 단검 0.45(같음) · 지팡이 0.91 → 0.90~0.95 · 홀 0.77 → 0.75~0.85 · 활 1.15 → 1.00~1.25.")
    A("- 무기마다 조정: 설명(lore)이 무게·속도를 말하는 무기는 ±0.02~0.10초 옮겼다(예: '작아서 재빨리 당길 수 있다' 각궁 −0.05, '묵직해서 당기기 힘들지만' 날활 +0.10, "
      "닻 참마도 +0.10, 용수철 활 −0.10). 표의 괄호 값. 목록은 `ce_core.LORE_TWEAK`.")
    A("- 새 무기(gear_spec 106개)는 gear_spec 공속의 역수를 쓰되, 모양 기본값 ±15% 안으로 자른다. 활은 모양 기본값.")
    A("")
    A("### 5.2 한 방 피해를 정하는 식 (기존 무기)")
    A("")
    A("```")
    A("0.3.4 설계 초당 피해  DPS_old = 옛 피해 가운데값 × 옛 종류 주기   (활 = 가운데값 × 1.25 ÷ 1.15, 치명 화살 포함)")
    A("새 DPS 등가          = DPS_old × c(L)                         (L = 무기 내부 레벨)")
    A("새 한 방 가운데값      = DPS_old × c(L) × 새 간격")
    A("새 범위             = 옛 범위 × (새 가운데값 ÷ 옛 가운데값) 을 정수로 (가운데값이 가장 가깝게, 폭 비율 유지)")
    A("```")
    A("")
    A("'0.3.4 숙련 DPS'는 게이지가 꽉 찰 때마다 친 값이다. 게이지가 없어지면 초보·보통 실력도 이 값에 가까워진다(§9 에서 난이도로 따진다).")
    A("")
    A("### 5.3 기존 무기 131개 (간격 · 새 한 방 · 초당 피해 · 스킬 위력 · 무기 스킬 배율 계수)")
    A("")
    A("'초당 피해'는 스탯 빼고 무기 하나의 값. 옛 → 새 차이는 c(L)(스탯 계수 2%→1% 보정)이다. '무기 스킬 배율'은 그 무기 스킬 데이터의 피해 숫자에 곱할 계수(§5.5).")
    A("")
    A(existing_weapon_table())
    A("")
    A("### 5.4 gear_spec 새 무기 106개")
    A("")
    A("gear_spec 의 피해(공속 기준)를 같은 초당 피해로 새 간격에 옮기고 c(L) 를 곱했다. gear_spec 이 쓰는 `attack.speed` 대신 `attack.interval`(초)을 쓴다.")
    A("")
    A(new_weapon_table())
    A("")
    A("### 5.5 무기 스킬 데이터 옮기기")
    A("")
    A("무기 스킬은 이제 공격력이 아니라 스킬 위력에 곱한다. 같은 사람(정렬 분배)에게 같은 피해가 나오도록 데이터의 피해 숫자를 곱해 둔다.")
    A("")
    A("```")
    A("weapon_skill_factor = K(방식, 새 간격) ÷ (옛 종류 주기 × skill_power_mult)")
    A("  ≈ 옛 종류 피해 배율: 검방 0.98 · 대검 1.547 · 활 1.30 · 지팡이 1.056 · 홀 0.894 · 단검 0.62")
    A("곱하는 키: params.damage · *_damage(counter_damage·echo… ) · mechanics 효과 damage/execute.amount·boss_amount/lightning/explosion 의 숫자")
    A("안 곱하는 키: percent(최대 HP 비율) · heal·shield·absorption · 상태이상 potency(비율은 §3 지속 피해 식이 SP 로 맞춤)")
    A("```")
    A("")
    A("### 5.6 같은 구간 안 퍼짐 — 느린 무기가 스킬을 독차지하지 않는다")
    A("")
    A(band_table())
    A("")
    A("한 방 피해는 무기 무게에 따라 3~3.7배 벌어진다(손맛). 스킬 위력은 1.2~1.6배 — 희귀도(일반→전설 1.31배)와 구간 안 레벨 차이뿐이다.")
    A("")
    A("### 5.7 앞으로 만들 무기의 공식")
    A("")
    A("```")
    A("새 티어 위력 TP′(L, 희귀도) = P(L) × 희귀도 배율 × c(L)")
    A("   P(L) = 7 + 0.25(L−1) + 0.0195(L−1)²     희귀도: 일반 1.00 · 고급 1.06 · 희귀 1.13 · 영웅 1.21 · 전설 1.31 · 신화 1.45 (gear_spec)")
    A("한 방 가운데값 = TP′ × K(방식, 간격) × 간격          범위 반폭 3~12% (평균 6.8%) → 정수")
    A("간격 = 모양 기본값 ± 0.10 (설명에 맞게)            시전 무기는 attack.kind: magic, 그 밖 physical (INT 요구 근접·활은 magic 으로 바꿔도 됨)")
    A("스킬 위력은 따로 적지 않는다 (식으로 나옴). 특별한 무기만 skill_power_mult (0.8~1.2)")
    A("```")
    A("")
    A(future_table())
    A("")

    # 6
    A("## 6. 직업 맞추기 (Lv10·25·45, 알맞은 분배)")
    A("")
    A("### 6.1 '알맞은 분배'")
    A("")
    A("두 판 모두 **무기·방어구 요구 능력치를 먼저 채운다**(0.3.4 규칙: 판금 VIT · 가죽 DEX · 천 INT|WIS · 방패 VIT, 무기는 그 요구치). 남은 포인트는 목표 비율에 모자란 스탯부터.")
    A("")
    A(table(["직업", "0.3.4 목표 비율", "새 목표 비율", "장비 (그 레벨 흔한 것)"], [
        ["수호기사", "VIT 3 : STR 2", "같음", "판금 + 검·방패"],
        ["광전사", "STR 3 : VIT 2", "같음", "판금 + 무거운 무기"],
        ["사냥꾼", "DEX 3 : VIT 2", "DEX 2 : STR 1.3 : VIT 1.7 (DEX 는 요구치가 정함)", "가죽 + 활"],
        ["비전술사", "INT 3 : VIT 2", "같음", "천 + 지팡이"],
        ["사제", "WIS 3 : VIT 2", "WIS 2.5 : INT 0.55 : VIT 1.95", "천 + 홀"],
        ["그림자", "DEX 3 : VIT 2", "DEX 2 : STR 1.4 : VIT 1.6", "가죽 + 단검"],
    ]))
    A("")
    A(class_alloc_table())
    A("")
    A("### 6.2 결과")
    A("")
    A("기대값 모델(`ce_model.py`, 기본 공격 + 직업 스킬 4개의 지속 DPS · 유효 HP = HP × 방어 × 피해 감소 × 회피(0.8배) × 막기):")
    A("")
    A(class_det_table())
    A("")
    A("시뮬레이터 방 전투 100판(같은 시드, 숙련, 보통) — 방 초당 피해 / 받은 피해(최대 HP 비율):")
    A("")
    A(class_sim_table())
    A("")
    A("- 기대값 모델: 18칸 중 17칸이 ±10% 안. 사제 Lv10 +11% 는 새 은총(마법 피해 +10%)이 초반에도 그대로 붙어서다(절대값이 작다: 초당 20 안팎).")
    A("- 시뮬레이터 3·6·10층: 사제 3층 +14% 하나만 넘는다(같은 까닭). 받은 피해는 그림자 6층 +14% 하나만 넘는다(VIT 를 조금 덜 찍은 몫, 회피로 일부 메움).")
    A("- 1층(Lv1~5)은 비교 기준 밖이지만 +5~20% 쪽이다(c(L)를 무기 레벨 +3 에 맞춘 덕). 0.3.4 에서 초반 솔로가 가장 약하던 그림자·비전술사가 특히 오른다.")
    A("- 초기화를 안 한 사람(0.3.4 분배 그대로)은 사냥꾼·그림자 피해가 크게 준다 → 접속 안내 + 무료 초기화(§10.3).")
    A("")
    A("### 6.3 classes.yml 에서 바꿀 값")
    A("")
    A(table(["어디", "지금", "바꿈", "왜"], [
        ["`weapon_types`", "추천 무기 종류", "삭제", "종류 없음"],
        ["`skill_scale` (새)", "-", "수호기사 1.00 · 광전사 1.55 · 사냥꾼 **1.55** · 비전술사 1.05 · 사제 0.90 · 그림자 0.62",
         "옛 추천 무기 배율을 직업으로 옮김 (시전 ÷1.05). 사냥꾼은 1.30→1.55: 스킬이 STR 만 타서"],
        ["`starter_weapon` (새)", "추천 무기 중 최저", "지금 주는 것 그대로 (corridor_longsword · rootcutter_greatsword · corridor_longbow · lantern_staff · acolyte_scepter · moss_dirk)", "-"],
        ["모든 스킬 `cooldown`", "추천 무기면 −10%", "숫자 ×0.9", "추천 무기를 든 사람은 그대로"],
        ["`keen_eye.full_draw_bonus`", "0.15", "**0.30**", "사냥꾼 공격력이 STR 로 옮겨 가며 준 몫"],
        ["`vital_point` (새 키 `crit_damage`)", "-", "**0.40**", "그림자: 높은 치명 확률을 피해로"],
        ["`grace` (새 키 `magic_damage`)", "-", "**0.10**", "사제: WIS 가 피해에서 빠진 몫"],
        ["`primary_stat`", "공격력 혼합에 씀", "UI '추천 분배' 글에만", "primaryMix 삭제"],
        ["설명 글", "\"대검의 광인\" · \"활잡이\" · \"단검술사\" · \"대검을 크게 돌려\" · \"대검을 내리꽂아\"",
         "\"피를 흘릴수록 강해지는 광인\" · \"먼 거리의 사수\" · \"급소를 노리는 암살자\" · \"무기를 크게 돌려\" · \"무기를 내리꽂아\"", "종류 이름을 쓰지 않는다"],
        ["`damage` 설명 규칙 (머리 주석)", "공격력에 곱하는 배율", "스킬 위력에 곱하는 배율", "-"],
    ]))
    A("")
    A("### 6.4 요구 능력치 — 다른 스탯을 요구하는 무기의 '세금' (gear_spec 에 주는 숫자)")
    A("")
    A("무기 요구치 R = ceil(2.5(L−1)) 에 방어구 요구치 R 이 더해지면 포인트가 거의 다 찬다. 요구 스탯이 STR/INT 가 아니면 피해 스탯 몫이 줄어든다. "
      "같은 레벨·같은 방어구, STR 요구 무기 대비 물리 초당 피해(분배 = 요구치 → 나머지 STR 3 : VIT 2, 기본 스탯 3):")
    A("")
    A(tax_table())
    A("")
    A("**권고 규칙(데이터)**: 물리 무기가 DEX·LUK·WIS·VIT **하나만** 요구하면 요구치를 그 스탯 60% + STR 40%(마법 무기면 INT 40%)로 나눈다(합은 R 그대로, 각각 올림). "
      "판금·천을 입은 사람이 DEX 무기를 들어도 피해 스탯이 0 이 되지 않는다. 가죽+DEX 무기는 어차피 방어구가 DEX R 을 요구하므로 바뀌는 게 없다. "
      "INT 요구 물리 모양 무기(gear_spec 의 지능 활·지능 언월도 등)는 `attack.kind: magic` 으로 두는 것이 낫다(INT 가 피해가 됨).")
    A("")

    # 7
    A("## 7. 보이는 것")
    A("")
    A("### 7.1 툴팁 · 도감 · 대장간")
    A("")
    A("```")
    A("영웅 무기 · 지하 4층 · ✦ 아우라                ← 첫 줄: 분류 이름(대검/활…) 없음")
    A("요구 힘 40                                    ← 그대로 (나뉘면 '요구 민첩 24 · 힘 16')")
    A("⚔ 공격력 23 (21–24) · 물리                    ← 한 방 피해, 강화 보너스는 지금처럼 (+5)")
    A("공격 속도 초당 1.5회                           ← 1 ÷ interval, 소수 한 자리, 민첩 전 값")
    A("```")
    A("")
    A("- 활은 같은 두 줄(공격력 = 끝까지 당긴 한 발, 초당 = 1 ÷ 한 발 주기). 시전 무기는 '· 마법'.")
    A("- 줄 폭 330px·20줄 상한(TooltipFitTest) 안: 공격 속도 줄은 짧다. 요구 능력치 두 개 줄은 최대 '요구 민첩 118 · 힘 79' (약 150px).")
    A("- 도감·대장간 목록도 같은 `ItemTooltip.lines`. 자세히 보기(도감)에 '스킬 위력 N' 한 줄을 덧붙인다.")
    A("")
    A("### 7.2 /스탯 화면")
    A("")
    A(table(["스탯", "지금 글", "바꾼 글"], [
        ["힘", "근접 공격력 · 방어 관통", "물리 공격력 +1%/점 · 넉백 저항"],
        ["민첩", "원거리 공격력 · 공격 속도 · 회피", "공격 속도 +0.5% · 치명 +0.25%p · 회피 +0.1%p /점"],
        ["지능", "마법 공격력 · 최대 MP · 스킬 피해", "마법 공격력 +1%/점 · 최대 MP +3 · 재사용 −0.2% (최대 20%)"],
        ["체력·정신·행운", "그대로", "그대로"],
    ]))
    A("")
    A("요약 칸(새): '공격력 물리 N · 마법 N (손에 든 무기 한 방)' · '공격 속도 초당 N회(지금 값)' · '스킬 위력 N'.")
    A("")
    A("### 7.3 떠오르는 피해 숫자")
    A("")
    A("- 기본 공격: 한 대마다 숫자 하나 — 방어까지 깎인 최종 피해(지금과 같음). 툴팁 공격력과 같은 단위다.")
    A("- 마법 피해는 하늘색(`#9fd3ff`), 물리는 지금 노란색, 치명은 지금 주황 굵게, 고정·지속 피해는 지금 보라.")
    A("- 지속 피해 틱과 한 틱 안의 여러 타격: 대상마다 0.5초 동안 더해서 하나로 띄운다(빠른 무기·독 중첩에서 숫자 홍수 방지). 틱당 24개 상한은 그대로.")
    A("")

    # 8
    A("## 8. PvP · 무적 시간")
    A("")
    A("### 8.1 PvP")
    A("")
    A("- `pvp.damage_multiplier 0.7` · `max_hit_ratio 0.35` 그대로. 같은 레벨에서 기본 공격 한 대 비율과 쓰러뜨리는 시간이 거의 같다:")
    A("")
    def _pk(k):
        for en, ko in KO.items():
            k = k.replace(en, ko)
        return k.replace("->", " → ")
    A(table(["경우 (같은 레벨, 기본 공격만)", "한 대 = 상대 HP %(옛 → 새)", "쓰러뜨리는 초(옛 → 새)"], [[_pk(k), f"{v['old_hit_pct']:.1%} → {v['new_hit_pct']:.1%}", f"{v['old_ttk_s']} → {v['new_ttk_s']}"] for k, v in T["pvp"].items()]))
    A("")
    A("- 공격하는 사람의 간격이 0.25초 하한이라 1초에 4대가 최대다. 받는 사람 무적 시간을 따로 두지 않는다(지금처럼 `setHealth`).")
    A("- 무거운 무기 치명 한 방은 35% 상한이 막고, 빠른 무기는 상한에 안 걸린다 → 빠른 무기가 PvP 에서 조금 유리. 지켜볼 것.")
    A("")
    A("### 8.2 무적 시간")
    A("")
    A("- 미궁 몹·보스: 바뀌는 것 없음(무적 시간 없음, 공격자 간격이 막음).")
    A("- 미궁 밖 바닐라 몹: `applyVanilla` 로 미궁 기본 공격·스킬 피해를 넣은 직후 `target.setNoDamageTicks(0)`. 빠른 무기가 0.5초 무적에 막히지 않는다. "
      "그 직후의 다른 바닐라 피해(용암·낙하 등)도 무적 없이 들어가지만, 미궁 밖 바닐라 몹에게만 해당해 영향이 작다.")
    A("- 플레이어가 죽는 한 방(바닐라 경로)은 그대로.")
    A("")

    # 9
    A("## 9. 난이도")
    A("")
    A("### 9.1 방법")
    A("")
    A("- `ce_sim.py` = 0.3.4 r4 시뮬레이터(지금 config 값, 악몽 1층 숙련 약 50% 로 맞춘 것) + 이번에 더한 것: 직업 스킬 2~4번과 버프·지속 피해, 회피, 2층 이후 보스(bosses.yml HP·피해·방어 + 경고 패턴·광역·연사·큰 한 방·소환), 3인 파티, 요구 능력치를 채우는 분배. "
      "더한 것은 0.3.4·새 모델 둘 다에 똑같이 들어간다.")
    A("- 새 모델만: 무기 숫자·간격, 공식, 직업 값(§6.3), 그리고 **게이지 손실이 사라짐**: 0.3.4 의 '공격 기회'(uptime 초보 0.70·보통 0.78·숙련 0.85) 안에 들어 있던 "
      "'꽉 차기 전에 누른 손실'을 초보 15% · 보통 8% · 숙련 0% 로 보고, 새 모델에서는 그만큼 기본 공격이 더 맞는다(활은 당기기라 그대로).")
    A("- 판: 직업 6개 솔로 × 보통(초보·보통 실력·숙련)·어려움·악몽(보통 실력·숙련) × 1·3·5·7·10층, 판마다 40번. 3인 파티 2조: A = 수호기사·사냥꾼·사제, B = 광전사·비전술사·그림자 (20번). "
      "층 입장 = 그 층 첫 레벨, 그 레벨에 흔한 장비(6층부터 영웅), 물약 10.")
    A("- 한계: 위치 선정을 확률로 근사, 2층 이후 보스는 일반형. 절대값보다 **같은 시드의 전후 차이**로 읽는다. 3층이 5·7층보다 어려운 것은 0.3.4 에도 똑같이 있는 모양(입장 레벨·장비 가정 때문).")
    A("")
    A("### 9.2 전후 (솔로)")
    A("")
    A(difficulty_tables())
    A("")
    A("### 9.3 3인 파티 (A 수호기사·사냥꾼·사제 / B 광전사·비전술사·그림자, 한 명이라도 보스까지 잡으면 클리어)")
    A("")
    A(party_tables())
    A("")
    A("### 9.4 처치 시간")
    A("")
    A("목표 범위(0.3.4 가 받아들여진 값을 기준으로 정함 — 바꾼 뒤에도 이 안이어야 한다):")
    A("")
    A(table(["무엇", "목표 (솔로·보통·그 층 첫 레벨·흔한 장비)"], [
        ["일반 몹 한 마리", "근접·원거리 딜러 1.5~6초 · 수호기사·비전술사 ≤ 9초 · 사제 ≤ 15초"],
        ["전투방 하나", "딜러 8~25초 · 수호기사 ≤ 45초 · 사제 ≤ 90초"],
        ["정예방", "20~90초 (3층 정예는 소환체 때문에 시뮬레이터에서 4분대 — 0.3.4 도 같음)"],
        ["보스", "딜러 1.5~4분 · 수호기사 ≤ 7분 · 사제 ≤ 15분 (어려움 ×1.4~1.6, 악몽 ×2~3)"],
        ["3인 파티 보스", "2~6분"],
    ]))
    A("")
    A("일반 몹 한 마리 처치 시간(초, 기대값 모델, 보통·솔로·몹 평균 HP·방어, 옛 → 새):")
    A("")
    A(ttk_table())
    A("")
    A("시뮬레이터 평균 (직업 6개, 방 · 정예 · 보스, 초):")
    A("")
    A(time_tables())
    A("")
    A("보통·숙련·솔로 보스 처치 시간(초, 직업별, 옛 → 새):")
    A("")
    A(boss_class_table())
    A("")
    A("### 9.5 재조정 결론")
    A("")
    A(f"- **보통**: 그대로. 게이지 손실이 사라진 만큼 초보·보통 실력이 조금 편해진다(1층 보통 실력 {n1a_old['clear']:.0%} → {n1a_new['clear']:.0%}). 주인 목표(보통 솔로 초반은 편하게)와 같은 방향이다.")
    A(f"- **악몽**: 그대로 (HP 1.8 · 피해 1.6 · 경고 0.85). 1층 숙련 {f1n_old['clear']:.0%} → {f1n_new['clear']:.0%} — 약 50% 유지. 숙련자는 게이지 손실이 없었으니 거의 안 움직인다.")
    if FINAL_HARD:
        A(f"- **어려움**: 1층이 쉬워진다(숙련 {h1s_old['clear']:.0%} → {h1s_new['clear']:.0%}, 보통 실력 {h1a_old['clear']:.0%} → {h1a_new['clear']:.0%}). "
          f"HP 만 1.4 → **{FINAL_HARD['hp']}** 로 올려 되돌린다(→ 숙련 {h1s_fin['clear']:.0%}, 보통 실력 {h1a_fin['clear']:.0%}). 피해 1.3 · 경고 0.9 · 드롭·경험치 그대로. 보통과 악몽 사이 자리가 지켜진다.")
    A("- **파티·솔로 보정**: `party.solo_hp 0.85` · `solo_damage 0.85` · `hp_per_member 0.6` · `dmg_per_member 0.08` · 몹 수(`party_mob_count` 1인 0.7·2인 0.9) 그대로. 3인 파티 결과가 전후로 같은 모양이다.")
    A("- **층·몹 숫자**: 손대지 않는다. 깊은 층(10층)이 숙련 기준 몇 %p 어려워진 직업(사냥꾼·그림자)은 직업 값(§6.3)으로 맞췄고, 남은 차이는 판수 잡음 범위다.")
    A("- 처치 시간: 목표 범위 안. 1층 보스는 5~10% 빨라지고(게이지 손실 없음), 3~10층 딜러 보스는 ±10% 안. "
      "예외는 사제 10층 보스 +16%(12분 → 14분). 사제는 혼자 보스를 빨리 잡는 직업이 아니라 그대로 둔다. 줄이고 싶으면 은총 마법 피해 +10% → +15% (Lv45 −9% → −5%, 대신 Lv10 +16%).")
    A("- 정예방 시간 평균은 '정예방까지 살아 온 판'만 세서 판마다 흔들린다(악몽 10층 숙련 271 → 397초는 살아 온 직업이 달라진 탓 — 직업별로는 ±10% 안).")
    A("")

    # 10
    A("## 10. 옮기기 (0.3.4 → 0.3.5)")
    A("")
    A("### 10.1 config.yml")
    A("")
    A("```yaml")
    A("combat:")
    A("  damage_numbers: true")
    A("  damage_number_ticks: 16")
    A("  base_crit_chance: 0.05")
    A("  base_crit_damage: 1.5")
    A("  scale_vanilla_damage: true")
    A("  # 0.3.5 — 게이지 없는 공격 (무기마다 items.yml attack.interval)")
    A("  attack_interval_min: 0.25    # 민첩·공속을 다 쌓아도 이보다 빠르지 않다 (초)")
    A("  early_click_buffer: 0.35     # 간격이 끝나기 이 시간 안의 클릭은 기억했다가 끝나는 순간 넣는다 (0 = 끔)")
    A("  early_click_sound: true      # 너무 이른 클릭에 작은 '휙' 소리 (본인만)")
    A("  click_tolerance_ms: 50       # 이만큼 이른 클릭은 그냥 통과 (지연 보정)")
    A("  jump_crit: 1.2               # 떨어지며 친 근접 공격")
    A("  bow_full_draw_cue: true      # 끝까지 당겨지면 작은 '탁' 소리")
    A("# 0.3.5 부터 무기마다 items.yml attack.interval — 이 표는 none(맨손)만 읽는다")
    A("weapon_attack_speed:")
    A("  none: 1.6")
    A("difficulties:")
    if FINAL_HARD:
        A(f"  hard:      {{name: \"어려움\", hp: {FINAL_HARD['hp']}, damage: 1.3, drop: 1.3, xp: 1.3, telegraph: 0.9}}")
    A("```")
    A("")
    A("- 새 `combat.*` 키가 없으면 코드 기본값(= 위 값). 키를 지우거나 0 으로 두면 끔(기억창·소리).")
    A("- `weapon_attack_speed` 의 다른 키(sword_shield …)는 읽지 않는다. 남아 있으면 켤 때 정보 로그 한 줄(무시함).")
    if FINAL_HARD:
        A(f"- 어려움: `Difficulty.legacy034(hard)` = {{hp 1.4, damage 1.3, drop 1.3, xp 1.3, telegraph 0.9}}. 키마다 이 값과 같으면 '안 고친 값'으로 보고 새 기본값({FINAL_HARD['hp']}), "
          "다르면 적힌 값 그대로 — 0.3.4 의 `legacy032` 승격과 같은 방식(`Settings.upgrade`). 0.3.2 값(1.5/1.4/0.85)이 남은 서버는 지금처럼 0.3.4 값을 거쳐 새 값이 된다.")
    A("- 보통·악몽·쉬움·파티 값은 바뀌지 않으므로 옮길 것이 없다.")
    A("")
    A("### 10.2 아이템 (이미 가진 무기)")
    A("")
    A("- 굴린 값이 PDC(`Keys.ITEM_ROLLS`)에 숫자로 박혀 있다. items.yml 범위만 바꾸면 옛 숫자가 남는다.")
    A("- 옮기기: 무기의 `damage` 굴림을 **같은 위치**로 옮긴다. t = (옛 값 − 옛 최소) ÷ (옛 최대 − 옛 최소), 새 값 = round(새 최소 + t × (새 최대 − 새 최소)). "
      "옛 범위는 `CombatMigration035` 표(이 JSON 의 `migration.items.old_damage`)에 박아 둔다. 옛 범위 밖 값(관리자 지급 등)은 비율(`per_hit_factor`)로.")
    A("- 시점: `GearItemService.baseRolls` 가 읽을 때(깃발 `Keys.ITEM_COMBAT_VER` < 35 이면 옮긴 값을 돌려줌) + 쓸 수 있는 곳(접속 때 가방·엔더 상자, 상자 열 때, 줍기, 손 바꿈)에서 "
      "PDC 를 고쳐 쓰고 깃발 35 + 툴팁 다시 그림.")
    A("- 강화 단계·다른 스탯 굴림·시드는 그대로. 주 스탯 줄 이름이 바뀐 무기(gear_spec `stats_rename`)는 같은 값으로 키만 바꾼다.")
    A("")
    A("### 10.3 플레이어")
    A("")
    A("- 스탯 무료 초기화 1회: 0.3.4 의 `LevelService.grantRequirementReset` 와 같은 모양, 새 깃발 `stats.role_reset_035`. 나눈 포인트가 있으면 `StatsMenu.FREE_RESET_KEY` 를 1 로(쌓지 않음).")
    A("- 접속 안내 (한 번): \"<#c79bff>힘은 물리, 지능은 마법 공격력이 되었습니다. 민첩은 공격 속도·치명·회피입니다.</#c79bff> <gray>/스탯</gray> <white>에서 스탯 초기화를 한 번 무료로 할 수 있습니다.\"")
    A("- 직업은 그대로. 시작 꾸러미·칭호 영향 없음.")
    A("")
    A("### 10.4 데이터 파일")
    A("")
    A(table(["파일", "바꿀 것"], [
        ["items.yml (무기 131)", "`weapon_type` 삭제 → `attack: {style, interval, kind}` · `stats.damage` 새 범위 · 무기 스킬 피해 숫자 × weapon_skill_factor (JSON 표)"],
        ["items.yml (새 무기 106)", "gear_spec 그대로 + `attack.speed` 대신 `attack.interval` · `stats.damage` 를 이 명세의 새 범위로"],
        ["classes.yml", "§6.3 표"],
        ["config.yml", "§10.1"],
        ["GDD.md", "§3 스탯 표 · §4.1 스킬 파라미터 규칙('스킬 위력') · §4.4 · §11.2 무기 피해 · §11.7 상한(공속 +60%·하한 0.25초·회피 40%) · §15.4 피해 유형/종류 · §18 PvP"],
        ["ARCHITECTURE.md", "combat: AttackClock · DamageKind · 스킬 위력 경로, stats: DerivedStats 새 필드"],
    ]))
    A("")

    # 11
    A("## 11. 구현 묶음")
    A("")
    A(table(["파일", "할 일"], [
        ["stats/StatCalculator", "`primaryMix` 삭제. 상수 STR_POWER 0.01 · INT_POWER 0.01 · DEX_SPEED 0.005 · DEX_CRIT 0.0025 · DEX_EVASION 0.001 · LUK_CRIT 0.0025. "
         "`compute(...)` 에 무기 interval·style·kind·skill_power_mult 를 받는 판(맨손 = 3, 0.625, melee, physical)."],
        ["stats/DerivedStats", "`physicalPower()`(1+0.01 STR) · `magicPower()` · `power(DamageKind)` · `weaponDamage()` · `attackPower()`(손에 든 무기 종류 기준) · "
         "`skillPower()` · `attackInterval()`(실제) · `weaponInterval()`(툴팁) · `weaponKind()`. 순수 계산 → `CombatMath.K(style, interval)`."],
        ["stats/StatService.applyAttributes", "미궁 무기·맨손이면 ATTACK_SPEED 1024, 바닐라 무기는 바닐라. `settings.weaponAttackSpeed(type)` 삭제(맨손만)."],
        ["combat/AttackClock (새)", "플레이어별 nextReady·기억한 클릭·마지막 휙 시각. 순수 판정 `AttackTiming`(테스트): `onClick(now) → ACCEPT|BUFFER|EARLY`, `release(now)`, `onSwap`."],
        ["combat/CombatListener", "`onPreAttack` → AttackClock (EARLY/BUFFER 면 `setCancelled`). `meleeMult` = 점프 치명만. `rangedMult` = 서버 당김 세기(×1.25 삭제). "
         "`onShoot` 에서 당긴 시간 기록·화살 속도 다시 맞춤·끝까지 당김 치명. `firedFromLabyrinthBow` = style RANGED. 기억한 클릭을 넣는 1틱 작업(같은 피해 경로, PvP 넉백·발화 포함)."],
        ["combat/DamageKind (새) · DamageContext", "`kind` 필드(기본은 type 에서), `base` = PER_HIT | SKILL. `DamageContext.basic(...)` · `DamageContext.skill(player, target, mult, type, kind)`. 옛 `attack(...)` 은 isSkill 이면 SKILL."],
        ["combat/DamageService", "원피해 = (base 가 SKILL 이면 skillPower, 아니면 weaponDamage) × power(kind) × mult (× 사제 마법 +10%). `applyVanilla` 뒤 `setNoDamageTicks(0)`(공격자가 플레이어일 때). 피해 숫자 0.5초 묶음·마법 색."],
        ["classes/skills/SkillContext", "`weaponScale()` → `cls.skillScale()`. `damage(...)` = SKILL base + 스킬 종류. `dotRatio` = 비율 × skillScale (위력은 SP 로)."],
        ["classes/ClassPassives · LabyrinthClassService · ClassesModule · ui/menus/ClassMenu", "매의 눈 0.30(데이터) · 급소 찌르기 치명 피해 · 은총 마법 피해(StatContributor). 추천 무기 −10%·'추천 무기' 글 삭제. 시작 무기 = `starterWeapon`."],
        ["content/WeaponTypes", "삭제 (gear_spec 과 같음). `effective()` 는 EquipRules 로."],
        ["content/ItemDef · ContentParser · ContentValidator", "`attack.style/interval/kind/projectile` 읽기(`speed` 만 있으면 1/speed, 경고). 검사: interval 0.35~1.30, 활 모양 ⇔ ranged, kind ∈ physical|magic."],
        ["items/weaponskills (SkillCast.hit · MechanicsEngine · Movement/Area/Projectile/Support)", "`DamageContext.attack` → `DamageContext.skill(..., kind)`. defaultType = 무기 style. 숫자는 데이터에서 이미 옮김."],
        ["items/ItemTooltip", "분류 글자 삭제, '⚔ 공격력 … · 물리/마법' + '공격 속도 초당 N회'. 도감 자세히 보기 '스킬 위력'."],
        ["items/GearItemService", "굴림 옮기기(§10.2)."],
        ["ui/menus/StatsMenu", "§7.2 글 + 요약 칸."],
        ["core/Settings · core/Difficulty", "combat 새 키, `legacy034` 승격."],
        ["stats/LevelService", "`ensureRoleReset` (§10.3)."],
        ["items/unique/UniqueEffectService (unique_spec)", "§3.5 기준(한 방 / 스킬 위력 / 확률 보정)."],
    ]))
    A("")

    # 12
    A("## 12. 테스트")
    A("")
    A(table(["테스트", "확인"], [
        ["AttackTimingTest (새)", "간격대로만 통과 · 50ms 안 이른 클릭 통과 · 0.35초 안 기억 → 끝에 1번 · 더 이르면 EARLY · 기억은 하나만(마지막 대상) · 틱 반올림으로 속도가 안 샘(100번 = 100×간격 ±1틱) · 무기 바꾸면 +간격×0.5 · 하한 0.25초"],
        ["StatCalculatorTest", "물리 = W(1+0.01 STR), 마법 = W(1+0.01 INT), DEX 는 공격력 불변 · 공속 0.005/점·상한 0.6 · 치명 0.0025 · 회피 0.001·상한 0.4 · 스킬 위력 식"],
        ["CombatMathTest (새)", "K(근접 0.67초) = 1.47, K(0.45초) ≈ 1.367, 원거리 1.413, 시전 1.22 · 같은 단계 무기(대검·단검·활·지팡이) 스킬 위력 ±3%"],
        ["WeaponIntervalDataTest (새)", f"모든 무기에 attack.interval({IV_MIN:.2f}~{IV_MAX:.2f}, 검사 범위 0.35~1.30) · 활 모양 = ranged · 시전 모양 = 기본 magic · 초당 피해 = TP′×K ±5% · 구간마다 스킬 위력 최고÷최저 ≤ 1.65(신화 제외)"],
        ["SkillKindTagsTest (새)", "직업 스킬 24개·무기 스킬 전부 꼬리표가 이 명세 JSON 과 같음(데이터에서 계산)"],
        ["WeaponFreedomTest", "추천 무기 환산 삭제 → 어떤 무기든 직업 스킬 = SP × skill_scale"],
        ["GearRequirementsDataTest", "무기 요구치는 무기마다(합 R, 나눔 규칙 60/40) · 그 층 한 벌이 포인트 안"],
        ["ItemRollsTest", "굴림 옮기기: 위치 t 보존 · 경계값 · 깃발 35 이면 다시 안 옮김"],
        ["RequirementResetTest", "role_reset_035 한 번만, 포인트 없으면 안 줌"],
        ["ScalingTest / BossScalingTest", "어려움 legacy034 승격 · 고친 값 유지"],
        ["TooltipFitTest", "새 두 줄 포함 330px·20줄"],
        ["DamageFormulaTest", "그대로 + 종류 배율 곱이 공식 앞단에서만"],
    ]))
    A("")

    # 13
    A("## 13. 다른 설계자에게 (gear_spec · unique_spec 과 맞출 것)")
    A("")
    A("- **gear_spec 1.2~1.4**: `attack.speed` → `attack.interval`(초). 이 명세의 간격 표를 쓴다. skill_power 생각은 같다 — 다만 이 명세는 K 를 간격 함수로 두고 "
      "(1 + 0.5 × 공격 속도)를 곱한다. 직업 skill_scale 은 사냥꾼만 1.30 → 1.55. 스킬 위력 식에 '(1 + 0.02 × 주스탯 혼합)' 대신 '(1 + 0.01 × STR 또는 INT)'.")
    A("- **gear_spec 1.3 피해 공식**: K 는 그대로 쓰되, 피해 가운데값에 c(L)를 곱한다(§5.7). 새 106개의 최종 한 방 숫자는 §5.4 표(JSON `per_hit`).")
    A("- **gear_spec 1.5 요구 능력치**: DEX·LUK·WIS·VIT 단독 요구는 60/40 나누기를 권한다(§6.4 세금 표). INT 요구 근접·활은 `attack.kind: magic` 을 권한다.")
    A("- **unique_spec**: §3.5 — 처치·주기·지속 피해 세기는 스킬 위력 기준, 확률 상태이상은 간격 보정. `momentum`(적중마다 공속 +3%)은 AS 에 더해져 스킬 위력에도 반이 든다(상한 +60% 안).")
    A("- **방어구(겉모습 장단점)**: 가죽 = DEX 요구 → 이제 공격력이 아니라 공속·치명·회피를 준다. 가죽에 STR 줄을 섞거나 회피 줄을 넉넉히 주면 사냥꾼·그림자 분배가 편해진다.")
    A("")
    A("## 14. 남은 위험")
    A("")
    A("- 지금 연타로 놀던 사람(특히 느린 무기)은 초당 피해가 줄었다고 느낀다(초당 8번 대검 −44%). 안내 글에 '이제 무기마다 박자가 있다'를 넣는다.")
    A("- 서버가 클릭을 막으면 클라이언트는 휘두름 모습을 이미 보여 준 뒤다. 기억창이 이 어색함을 대부분 덮지만, 0.35초보다 이른 클릭은 '빈 휘두름'으로 보인다(소리로 알림).")
    A("- `getActiveItemUsedTime` 이 26.3 Paper 에 없으면 우클릭 시작 틱으로 잰다(PlayerInteractEvent RIGHT_CLICK + 활). 손 바꿈·취소 때 지운다.")
    A("- 시뮬레이터의 2층 이후 보스는 일반형이다. 실제 보스 패턴(특히 처치 속도에 민감한 광폭·제한 시간)은 테스트 서버에서 한 번씩 확인한다.")
    A("- 사제 Lv10 피해 +11%, 1층 전반 +5~20% (모든 직업이 조금 강해짐) — 초반을 편하게 하는 방향이라 그대로 둔다.")
    A("")
    return "\n".join(md)


# ───────────────────────────── JSON ─────────────────────────────

def build_json():
    ex = weapons_existing()
    allw = T["weapons"]
    j = dict(
        version="combat-e1 (labyrinth 0.3.4 → 0.3.5 안)",
        intervals={k: v["interval"] for k, v in allw.items()},
        per_hit={k: v["per_hit"] for k, v in allw.items()},
        weapons={k: dict(name=v["name"], src=v["src"], shape=v["shape"], style=v["style"], kind=v["kind"], level=v["level"],
                         rarity=v["rarity"], interval=v["interval"], rate_per_s=v["rate_per_s"], per_hit=v["per_hit"],
                         dps_equiv=v["dps_new"], skill_power=v["skill_power"],
                         old_damage=v.get("old_damage"), old_type=v.get("old_type"), per_hit_factor=v.get("per_hit_factor"),
                         weapon_skill_factor=v.get("weapon_skill_factor"), gear_spec_damage=v.get("gear_spec_damage"),
                         gear_spec_speed=v.get("gear_spec_speed"), items_yml=dict(attack=dict(style=v["style"], interval=v["interval"], kind=v["kind"])))
                 for k, v in allw.items()},
        shape_interval=C.SHAPE_INTERVAL, lore_tweak=C.LORE_TWEAK,
        formulas=dict(
            per_hit_W="굴린 damage × 강화 배율 (맨손 3)",
            physical_power="1 + 0.01 × STR", magic_power="1 + 0.01 × INT", hybrid_power="1 + 0.01 × (STR + INT) / 2",
            attack_power="W × power(무기 attack.kind)",
            basic_hit="공격력 × 점프 치명 1.2(떨어지며) × 활 세기 × 매의 눈 1.30(사냥꾼·끝까지 당김)",
            attack_speed="AS = 0.005 × DEX + 장비·버프, clamp −0.5 ~ +0.60",
            interval_effective="max(0.25, interval / (1 + AS)); 활 당김 = max(0.25, (interval − 0.15) / (1 + AS))",
            bow_force="x = 당긴 시간 / 당김, force = (x² + 2x)/3, 피해 × max(0.1, force), 화살 속도 = 바닐라 최대 × force",
            crit_chance="0.05 + 0.0025 × DEX + 0.0025 × LUK + 장비 (≤ 0.75)",
            crit_damage="1.5 + 장비 (+0.40 그림자 패시브)",
            evasion="0.001 × DEX + 장비 (≤ 0.40), 보스 패턴 회피 불가",
            K="근접 1.47 − 0.143 × max(0, 1/interval − 1.5) · 원거리 1.413 · 시전 1.22",
            skill_power="(W_mid / interval) / K × skill_power_mult(시전 1.05) × (1 + 0.5 × AS)",
            class_skill="SP × skill_scale × power(스킬 종류) × 배율 × (1 + skill_damage) × (사제 마법 +10%)",
            weapon_skill="SP × power(스킬 종류) × (옛 배율 × weapon_skill_factor) × (1 + skill_damage)",
            weapon_skill_factor="K(style, interval) / (옛 종류 주기 × skill_power_mult)",
            dot="부여 순간 SP × power(상태이상 종류) × 비율 (× skill_scale: 직업 스킬), TRUE 틱",
            rebase_c="c(L) = (1 + 0.02 S) / (1 + 0.01 S), S = 8 + 3.6 × (L + 3)",
            existing_per_hit="mid = 옛 가운데값 × 옛 종류 주기(활 1.25/1.15) × 새 interval × c(L); 범위 = 옛 범위 비율, 정수",
            future_per_hit="mid = P(L) × 희귀도 × c(L) × K(style, interval) × interval; P(L) = 7 + 0.25(L−1) + 0.0195(L−1)²",
            requirement_split="물리 무기가 DEX·LUK·WIS·VIT 하나만 요구하면 그 스탯 ceil(0.6R) + STR ceil(0.4R) (마법 무기는 INT)",
            constants=dict(STR_POWER=0.01, INT_POWER=0.01, DEX_SPEED=0.005, DEX_CRIT=0.0025, DEX_EVASION=0.001, LUK_CRIT=0.0025,
                           CAP_ATTACK_SPEED=0.60, MIN_INTERVAL=0.25, BOW_NOCK=0.15, EARLY_CLICK_BUFFER=0.35, CLICK_TOLERANCE_MS=50,
                           JUMP_CRIT=1.2, SWAP_DELAY_FRACTION=0.5, BUFFER_REACH_SLACK=0.3, BUFFER_VIEW_DEG=50, BUFFER_MAX_AGE=0.6,
                           SP_SPEED_SHARE=0.5, CASTER_SP_MULT=1.05, UNARMED=dict(damage=3, interval=0.625)),
            class_values=dict(skill_scale=M.SKILL_SCALE, cooldown_mult=0.9, keen_eye_full_draw=0.30, vital_point_crit_damage=0.40,
                              grace_magic_damage=0.10),
            sensible_spread=dict(old=M.TARGET_OLD, new=M.TARGET_NEW),
        ),
        skill_kinds=dict(class_skills=K["class_skills"], weapon_skills=K["weapon_skills"], status=K["status"],
                         unique_effects=K["unique_effects"], passives=K["passives"], detail=K["weapon_skill_detail"]),
        difficulty=dict(
            decision=dict(normal="그대로", nightmare="그대로 (hp 1.8 · damage 1.6 · telegraph 0.85)",
                          hard=(f"hp 1.4 → {FINAL_HARD['hp']} (damage 1.3 · telegraph 0.9 · drop 1.3 · xp 1.3 그대로)" if FINAL_HARD else "그대로"),
                          party="그대로 (solo_hp 0.85 · solo_damage 0.85 · hp_per_member 0.6 · dmg_per_member 0.08 · party_mob_count 1:0.7 2:0.9)",
                          floors_mobs="그대로"),
            config=dict(difficulties=dict(easy=dict(hp=0.7, damage=0.6, drop=0.8, xp=0.8, telegraph=1.3),
                                          normal=dict(hp=1.0, damage=1.0, drop=1.0, xp=1.0, telegraph=1.0),
                                          hard=dict(hp=FINAL_HARD["hp"] if FINAL_HARD else 1.4, damage=1.3, drop=1.3, xp=1.3, telegraph=0.9),
                                          nightmare=dict(hp=1.8, damage=1.6, drop=1.8, xp=1.7, telegraph=0.85))),
            gauge_eff_assumption=X.GAUGE_EFF,
            ttk_targets=dict(normal_mob="딜러 1.5~6초 · 수호기사·비전술사 ≤ 9초 · 사제 ≤ 15초", room="딜러 8~25초 · 수호기사 ≤ 45초 · 사제 ≤ 90초",
                             elite="20~90초 (3층 정예는 소환으로 4분대, 0.3.4 와 같음)", boss="딜러 1.5~4분 · 수호기사 ≤ 7분 · 사제 ≤ 15분 (어려움 ×1.4~1.6, 악몽 ×2~3)",
                             party3_boss="2~6분", watch="사제 10층 보스 +16% (은총 +15% 로 줄일 수 있음)"),
        ),
        migration=dict(
            config=dict(new_keys={"combat.attack_interval_min": 0.25, "combat.early_click_buffer": 0.35, "combat.early_click_sound": True,
                                  "combat.click_tolerance_ms": 50, "combat.jump_crit": 1.2, "combat.bow_full_draw_cue": True},
                        weapon_attack_speed="none 만 읽음 (나머지 키 무시 + 정보 로그 1줄)",
                        difficulty_legacy034=dict(hard=dict(hp=1.4, damage=1.3, drop=1.3, xp=1.3, telegraph=0.9)),
                        rule="키마다 legacy034 와 같으면 새 기본값, 다르면 적힌 값 (Settings.upgrade, 0.3.4 legacy032 와 같은 방식)"),
            items=dict(rule="damage 굴림 위치 t = (v − 옛 lo)/(옛 hi − 옛 lo) 보존 → round(새 lo + t (새 hi − 새 lo)); 범위 밖이면 × per_hit_factor",
                       flag="Keys.ITEM_COMBAT_VER = 35", when="baseRolls 읽을 때 + 접속·상자·줍기·손 바꿈 때 PDC 다시 씀",
                       old_damage={k: v["old_damage"] for k, v in ex.items()}, new_damage={k: v["per_hit"] for k, v in ex.items()},
                       per_hit_factor={k: v["per_hit_factor"] for k, v in ex.items()}),
            players=dict(flag="stats.role_reset_035", pattern="LevelService.grantRequirementReset 와 같음 (FREE_RESET_KEY = 1, 쌓지 않음)",
                         message="힘은 물리, 지능은 마법 공격력이 되었습니다. 민첩은 공격 속도·치명·회피입니다. /스탯 에서 스탯 초기화를 한 번 무료로 할 수 있습니다."),
            weapon_skills=dict(rule="무기 스킬 피해 숫자 × weapon_skill_factor (percent·heal·shield·potency 제외)",
                               factor={k: v["weapon_skill_factor"] for k, v in ex.items() if v.get("weapon_skill_factor")}),
            classes=dict(remove=["weapon_types"], add=dict(skill_scale=M.SKILL_SCALE,
                                                           starter_weapon=dict(guardian="corridor_longsword", berserker="rootcutter_greatsword",
                                                                               hunter="corridor_longbow", arcanist="lantern_staff",
                                                                               priest="acolyte_scepter", shadow="moss_dirk")),
                         cooldown_mult=0.9, passives=dict(keen_eye=dict(full_draw_bonus=0.30), vital_point=dict(crit_damage=0.40),
                                                          grace=dict(magic_damage=0.10))),
        ),
        sim_tables=dict(
            class_det=CC["det"], class_sim=CC["sim"], mob_ttk=CC["ttk"],
            difficulty={f"{n}|{d}|{p}|F{fl}": {k: v for k, v in (solo_avg(n, d, p, fl) or {}).items() if k != "per"}
                        for n in R["names"] for d in ("normal", "hard", "nightmare") for p in ("novice", "average", "skilled")
                        for fl in (1, 3, 5, 7, 10) if solo_avg(n, d, p, fl)},
            per_class={f"{t[0]}|{t[2]}|{t[3]}|{t[4]}|F{t[5]}": r for t, r in ((tuple(x["task"]), x["result"]) for x in R["rows"]) if t[1] == "solo"},
            party={f"{t[0]}|{t[2]}|{t[3]}|{t[4]}|F{t[5]}": r for t, r in ((tuple(x["task"]), x["result"]) for x in R["rows"]) if t[1] == "party"},
            spam_0_3_4={TYPE_KO[wt]: {f"{c}cps": round(spam_ratio(C.OLD_AS[wt], c) - 1, 3) for c in (3, 5, 8, 10)} for wt in ("dagger", "sword_shield", "scepter", "staff", "greatsword")},
            band_spread=T["band_spread"], requirement_tax=T["tax"], pvp=T["pvp"], scenarios=R["names"], runs=R["runs"],
        ),
    )
    return j


if __name__ == "__main__":
    md = build_md()
    with open(os.path.join(D2, "combat_spec.md"), "w", encoding="utf-8") as f:
        f.write(md)
    js = build_json()
    with open(os.path.join(D2, "combat_spec.json"), "w", encoding="utf-8") as f:
        json.dump(js, f, ensure_ascii=False, indent=1)
    print("md", len(md), "json keys", list(js.keys()))
