#!/usr/bin/env python3
"""
TASK B — look_spec.md + look_spec.json 만들기.
  먼저: python3 lk_results.py · python3 lk_reqcheck.py · python3 lk_reqcheck.py --new · python3 lk_sim.py full
  그다음: python3 lk_spec.py
"""
import json
import os
import re

import lk_core as K
import lk_reqcheck as RQ
import lk_tooltip as TT

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)


def load(n):
    with open(os.path.join(HERE, n), encoding="utf-8") as f:
        return json.load(f)


RES = load("lk_results.json")
REQ = load("lk_reqcheck.json")
REQN = load("lk_reqcheck_new.json")
SIM = load("lk_sim_full.json")
DECOMP = load("lk_decomp.json")

CL = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
CN = {"guardian": "수호기사", "berserker": "광전사", "hunter": "사냥꾼", "arcanist": "비전술사", "priest": "사제",
      "shadow": "그림자"}
LN = {"heavy": "판금", "light": "가죽", "cloth": "천", "plain": "평상복", "any": "어느 겉모습이든"}
SN = {"STR": "힘", "DEX": "민첩", "INT": "지능", "VIT": "체력", "WIS": "정신", "LUK": "행운"}
SLOT = {"head": "머리", "chest": "몸", "legs": "다리", "feet": "발", "offhand": "방패"}
RAR = {"common": "일반", "uncommon": "고급", "rare": "희귀", "epic": "영웅", "legendary": "전설", "mythic": "신화"}
NATIVE = {"guardian": "heavy", "berserker": "heavy", "hunter": "light", "shadow": "light", "arcanist": "cloth",
          "priest": "cloth"}


def pct(x, d=0):
    return f"{x * 100:+.{d}f}%"


def req_text(r):
    return " · ".join(f"{SN[k]} {v}" for k, v in r.items()) if r else "없음"


def strip(s):
    return re.sub(r"<[^>]+>", "", s)


# ───────────────────────────── 설정 (config.yml armor_looks) ─────────────────────────────
CONFIG_YAML = """armor_looks:
  enabled: true                  # false = 겉모습 효과·4부위 효과 모두 끔 (요구 능력치는 그대로)
  full_pieces: 4                 # '온전한 겉모습': 머리·몸·다리·발 네 칸이 같은 겉모습 (방패는 세지 않는다)
  shield_counts_as: heavy        # 방패 = 판금 한 부위 (숨은 효과만, 4부위 수에는 안 든다)
  heavy:
    name: "판금"
    color: "#b8c4d6"
    piece:                       # 부위 하나 (머리·몸·다리·발·방패 어느 칸이든 같은 값)
      defense_pct: 0.04          # 최종 방어 × (1 + 합)
      damage_reduction: 0.005    # 받는 피해 감소 (더하기, 상한 50% 그대로)
      move_speed: -0.02          # 이동 속도 (더하기, −60% ~ +30% 그대로)
      evasion: -0.01             # 회피 (더하기, 0 아래로 안 내려감)
      cooldown_pct: 0.02         # 직업·무기 스킬 재사용 대기 시간 × (1 + 합)
    full:
      id: steadfast
      name: "버팀"
      knockback_resist: 0.60     # 몬스터·함정·다른 플레이어에게 밀려나는 세기 −60% (보스는 그대로)
      cc_resist: 0.40            # 기절·속박·빙결 시간 −40% (보스가 건 것은 그대로)
  light:
    name: "가죽"
    color: "#c9a46a"
    piece:
      evasion: 0.015
      crit_chance: 0.01
      attack_speed: 0.015        # combat_spec 공격 속도 (간격 ÷ (1 + 공속), 상한 +60%)
      move_speed: 0.01
      defense_pct: -0.06
    full:
      id: tumble
      name: "구르기"
      double_tap: 0.30           # 웅크리기 키를 이 시간 안에 두 번 (누름-뗌-누름)
      distance: 3.5              # 블록 (움직이던 방향, 멈춰 있으면 뒤로)
      iframe: 0.40               # 이 시간 동안 '피할 수 있는' 공격은 모두 회피 (보스 패턴은 회피 불가 — 지금과 같음)
      back_distance: 2.0         # 방향 키를 안 누르고 있으면 뒤로
      cooldown: 8.0
      combo_guard: 0.40          # 웅크리기 조합 스킬(웅크리기+F/Q/클릭)을 쓴 뒤 이 시간 안이면 구르지 않음
      ready_sound: true          # 다시 쓸 수 있게 되면 본인에게만 작은 소리
  cloth:
    name: "천"
    color: "#b99cff"
    piece:
      skill_damage: 0.02
      cooldown_pct: -0.015
      mana_regen_pct: 0.06       # 초당 MP 재생 × (1 + 합)
      hp_pct: -0.02              # 최대 HP × (1 + 합)
    full:
      id: mana_shield
      name: "마나 보호막"
      absorb: 0.20               # 받는 최종 피해의 20% 를 MP 가 대신 받는다
      damage_per_mp: 2.0         # MP 1 = 피해 2
      off_below: 0.20            # MP 가 최대의 20% 아래면 쉰다 (스킬 쓸 MP 를 남김)
"""


def config_json():
    out = dict(enabled=True, full_pieces=4, shield_counts_as="heavy")
    colors = {"heavy": "#b8c4d6", "light": "#c9a46a", "cloth": "#b99cff"}
    for lk, v in K.LOOKS.items():
        out[lk] = dict(name=v["name"], color=colors[lk], piece=dict(v["piece"]), full=dict(v["full"]))
    out["light"]["full"].update(double_tap=0.30, back_distance=2.0, combo_guard=0.40, ready_sound=True)
    return out


# ───────────────────────────── 표 만들기 ─────────────────────────────

def t_piece():
    rows = ["| 겉모습 | 좋은 쪽 (부위 하나) | 나쁜 쪽 (부위 하나) | 4부위 합 (방패 빼고) | 4부위 효과 |", "|---|---|---|---|---|"]
    full_txt = {
        "heavy": "**버팀** — 밀려남 −60% · 기절·속박·빙결 시간 −40% (보스 제외)",
        "light": "**구르기** — 웅크리기 두 번 → 3.5칸 구르기, 0.4초 회피, 8초에 한 번",
        "cloth": "**마나 보호막** — 받는 피해 20% 를 MP 로 (MP 1 = 피해 2), MP 20% 아래면 쉼",
    }
    for lk in ("heavy", "light", "cloth"):
        p = K.LOOKS[lk]["piece"]
        good = [TT.cell(k, v) for k, v in p.items() if TT.is_good(k, v)]
        bad = [TT.cell(k, v) for k, v in p.items() if not TT.is_good(k, v)]
        tot = [TT.cell(k, v * 4) for k, v in p.items()]
        rows.append(f"| {LN[lk]} | {' · '.join(good)} | {' · '.join(bad)} | {' · '.join(tot)} | {full_txt[lk]} |")
    return "\n".join(rows)


def t_sets():
    rows = ["| 세트 | 겉모습 | 아이템 레벨 | 희귀도 | 요구 짝 | 요구 (그 레벨) | 스탯 줄 이름 바꿈 | 정체성 |", "|---|---|---|---|---|---|---|---|"]
    seen = {}
    for r in RES["armor"]:
        sid = r["set"] or r["id"]
        if sid in seen:
            continue
        seen[sid] = r
    def key(r):
        return (r["level"], {"heavy": 0, "light": 1, "cloth": 2}.get(r["look"], 3))
    for sid, r in sorted(seen.items(), key=lambda kv: key(kv[1])):
        shares, ident, why = K.req_spec(r["id"])
        pair = " / ".join(f"{SN[k]} {int(v * 100)}" for k, v in shares.items()) or "-"
        nm = K.ALL_SETS[sid]["name"] if sid in K.ALL_SETS else r["name"]
        kind = "" if sid in K.ALL_SETS else f" ({SLOT[r['slot']]})"
        ren = ", ".join(f"{SN[a]}→{SN[b]}" for a, b in (K.STATS_RENAME.get(sid) or {}).items()) or "-"
        prop = " *(gear_spec 안)*" if r["proposed"] else ""
        rows.append(f"| {nm}{kind} `{sid}`{prop} | {LN.get(r['look'], r['look'])} | {r['level']} | {RAR[r['rarity']]} | {pair} | "
                    f"{req_text(r['requires'])} | {ren} | {why} |")
    return "\n".join(rows)


def t_reqcheck(res):
    hdr = "| 직업 | " + " | ".join(f"{lo}–{hi}" for lo, hi in RQ.BANDS) + " |"
    rows = [hdr, "|" + "---|" * (len(RQ.BANDS) + 1)]
    for cls in CL:
        cells = []
        for lo, hi in RQ.BANDS:
            r = res[f"{cls}|{lo}-{hi}"]
            ok = r["ok_looks"]
            if "plain" in ok:
                cells.append("평상복")
                continue
            s = "·".join(LN[lk] for lk in ("heavy", "light", "cloth") if lk in ok)
            # 가장 빡빡한 남는 포인트
            left = min(r[lk]["left"] for lk in ok) if ok else None
            cells.append(f"{s} ({left})" if ok else "**없음**")
        rows.append(f"| {CN[cls]} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def t_model(L):
    rows = [f"| 직업 | 기준 DPS / EHP | 판금 | 가죽 | 천 (마나 보호막 포함) | 엄격히 지는 겉모습 |", "|---|---|---|---|---|---|"]
    for cls in CL:
        row = RES["model"][f"{cls}|{L}"]
        b = row["base"]
        cells = []
        for lk in ("heavy", "light", "cloth"):
            x = row[lk]
            mark = "**" if lk == NATIVE[cls] else ""
            ms = f" ({pct(x['d_ehp_ms'])})" if x["full"] == "cloth" else ""
            cells.append(f"{mark}{pct(x['d_dps'])} / {pct(x['d_ehp'])}{ms}{mark}")
        dom = RES["dominance"][f"{cls}|{L}"]
        dom_t = ", ".join(f"{LN[d.split('>')[1]]}({LN[d.split('>')[0]]}에게)" for d in dom) or "없음"
        rows.append(f"| {CN[cls]} | {b['dps']:.0f} / {b['ehp']:.0f} | " + " | ".join(cells) + f" | {dom_t} |")
    return "\n".join(rows)


def t_model_sets(L):
    rows = ["| 직업 | 판금 | 가죽 | 천 |", "|---|---|---|---|"]
    for cls in CL:
        row = RES["model"][f"{cls}|{L}"]
        cells = []
        for lk in ("heavy", "light", "cloth"):
            x = row[lk]
            names = []
            for s in x["sets"]:
                names.append(K.ALL_SETS[s]["name"] if s in K.ALL_SETS else K.ALL_ITEMS[s]["name"])
            cells.append(", ".join(names) + f" · 분배 {' '.join(SN[k] + str(v) for k, v in x['alloc'].items())}")
        rows.append(f"| {CN[cls]} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def sim_get(kind, fl, v, cls, prof, diff):
    return SIM.get(f"{kind}|{fl}|{v}|{cls}|{prof}|{diff}")


def t_sim(fl):
    vs = ["base", "native", "heavy", "light", "cloth"]
    vn = {"base": "기준", "native": "제 겉모습", "heavy": "판금", "light": "가죽", "cloth": "천"}
    rows = ["| 직업 | " + " | ".join(vn[v] for v in vs) + " |", "|---|" + "---|" * len(vs)]
    for cls in CL:
        cells = []
        for v in vs:
            rm = sim_get("room", fl, v, cls, "skilled", "normal")
            a = sim_get("solo", fl, v, cls, "average", "normal")
            s = sim_get("solo", fl, v, cls, "skilled", "normal")
            h = sim_get("solo", fl, v, cls, "skilled", "hard")
            cells.append(f"{rm['dps']:.0f} / {rm['taken']:.2f} · {a['clear'] * 100:.0f}·{s['clear'] * 100:.0f}·{h['clear'] * 100:.0f}%")
        rows.append(f"| {CN[cls]} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def t_sim_early():
    vs = ["native_noimp", "native", "heavy"]
    vn = {"native_noimp": "같은 장비 · 지금 규칙", "native": "제 겉모습 (새 규칙)", "heavy": "판금"}
    out = []
    for fl in (2, 3):
        lab = "초보(보통) · 보통 실력(보통) · 숙련(어려움)" if fl == 2 else "보통 실력(보통) · 숙련(보통) · 숙련(어려움)"
        rows = [f"**{fl}층 (Lv{X_entry(fl)})** — 클리어율 {lab}", "",
                "| 직업 | " + " | ".join(vn[v] for v in vs) + " |", "|---|" + "---|" * len(vs)]
        for cls in CL:
            cells = []
            for v in vs:
                if fl == 2:
                    n = sim_get("solo", 2, v, cls, "novice", "normal")
                    a = sim_get("solo", 2, v, cls, "average", "normal")
                    h = sim_get("solo", 2, v, cls, "skilled", "hard")
                    cells.append(f"{n['clear'] * 100:.0f}·{a['clear'] * 100:.0f}·{h['clear'] * 100:.0f}%")
                else:
                    a = sim_get("solo", 3, v, cls, "average", "normal")
                    s = sim_get("solo", 3, v, cls, "skilled", "normal")
                    h = sim_get("solo", 3, v, cls, "skilled", "hard")
                    cells.append(f"{a['clear'] * 100:.0f}·{s['clear'] * 100:.0f}·{h['clear'] * 100:.0f}%")
            rows.append(f"| {CN[cls]} | " + " | ".join(cells) + " |")
        out.append("\n".join(rows))
    return "\n\n".join(out)


def X_entry(fl):
    return 1 if fl == 1 else {2: 5, 3: 10, 6: 25, 10: 45}.get(fl, fl)


def t_mixed():
    rows = ["| 빌드 | Lv | 입은 것 | 제 겉모습 대비 DPS / EHP | 이동 속도 · 회피 · 치명 · 공속 | 분배 | 4부위 |", "|---|---|---|---|---|---|---|"]
    for m in RES["mixed"]:
        names = [K.ALL_SETS[s]["name"] if s in K.ALL_SETS else K.ALL_ITEMS[s]["name"] for s in m["sets"]]
        full = K.LOOKS[m["full"]]["full"]["name"] if m["full"] else "없음"
        rows.append(f"| {m['name']} | {m['L']} | {', '.join(names)} | {pct(m['vs_native_dps'])} / {pct(m['vs_native_ehp'])} | "
                    f"{pct(m['move'])} · {m['evasion'] * 100:.1f}% · {m['crit'] * 100:.1f}% · {pct(m['speed'])} | "
                    f"{' '.join(SN[k] + str(v) for k, v in m['alloc'].items())} | {full} |")
    return "\n".join(rows)


def sim_summary():
    """겉모습마다 '엄격히 진다'(초당 피해 낮고 받은 피해 많고 클리어율도 낮음) 판정."""
    out = {}
    for fl in (3, 6, 10):
        for cls in CL:
            res = {}
            for v in ("heavy", "light", "cloth"):
                rm = sim_get("room", fl, v, cls, "skilled", "normal")
                cl = [sim_get("solo", fl, v, cls, p, d)["clear"] for p, d in (("average", "normal"), ("skilled", "normal"), ("skilled", "hard"))]
                res[v] = (rm["dps"], rm["taken"], sum(cl) / 3)
            lost = []
            for a in res:
                for b in res:
                    if a == b:
                        continue
                    A, B = res[a], res[b]
                    if A[0] >= B[0] * 1.02 and A[1] <= B[1] * 0.98 and A[2] >= B[2] - 0.02:
                        lost.append(f"{b}<{a}")
            out[f"F{fl}|{cls}"] = lost
    return out


def tooltip_examples():
    """예시 툴팁 (MiniMessage 를 벗긴 글자) — 영웅 판금 흉갑 · 전설 가죽 투구 · 영웅 천 하의."""
    ex = []
    for iid in ("geode_bastion_chest", "inkveil_helm", "frost_regalia_legs", "inkbound_kite_shield", "wayfarer_chest"):
        it = K.ALL_ITEMS[iid]
        lk = K.look_of(iid)
        top = f"{RAR[it['rarity']]} {LN[lk] + ' ' if lk in K.LOOKS else ''}{ {'head': '투구', 'chest': '흉갑', 'legs': '각반', 'feet': '장화', 'offhand': '방패'}[it['armor_slot']]}"
        lines = [top, "요구 " + req_text(K.new_requires(iid)), ""]
        st = K.renamed_stats(iid)
        keys = list(st)
        first = keys[0]
        lines.append(f"{'방어' if first == 'defense' else first} {st[first][0]}~{st[first][1]}")
        rest = keys[1:]
        names = {"VIT": "체력", "STR": "힘", "DEX": "민첩", "INT": "지능", "WIS": "정신", "LUK": "행운", "hp": "최대 HP",
                 "mp": "최대 MP", "damage_reduction": "받는 피해 감소", "evasion": "회피", "crit_damage": "치명타 피해",
                 "crit_chance": "치명타 확률", "block_chance": "막기 확률", "cooldown_reduction": "재사용 대기 감소",
                 "heal_power": "치유력", "skill_damage": "스킬 피해", "mana_regen": "초당 MP 재생", "hp_regen": "초당 HP 재생",
                 "move_speed": "이동 속도", "attack_speed": "공격 속도"}
        cells = [f"{names.get(k, k)} {st[k][0]}~{st[k][1]}" for k in rest]
        for i in range(0, len(cells), 2):
            lines.append(" · ".join(cells[i:i + 2]))
        if lk in K.LOOKS:
            lines.append("")
            lines += [strip(x) for x in TT.piece_lines(lk)]
            if it["armor_slot"] != "offhand":
                lines.append(strip(TT.full_line(lk)))
            else:
                lines.append("(방패는 판금 한 부위 — 4부위 수에는 안 든다)")
        sid = it.get("set_bonus")
        if sid:
            s = K.ALL_SETS[sid]
            lines.append("")
            lines.append(f"세트: {s['name']} ({len(s['pieces'])}부위)")
            for n, b in (s.get("bonuses") or {}).items():
                lines.append(f"  ({n}) " + ", ".join(f"{names.get(k, k)} {v}" for k, v in b.items()))
        lines.append("")
        lines.append("(설명 1~2줄)")
        lines.append("획득처: …  (층 숫자 없음)")
        ex.append(dict(id=iid, lines=lines, widths=[TT.width(x) for x in lines], count=len(lines)))
    return ex


def native_ranges():
    parts = []
    groups = [(("guardian", "berserker"), "heavy"), (("hunter", "shadow"), "light"), (("arcanist", "priest"), "cloth")]
    for clss, lk in groups:
        xs = [RES["model"][f"{c}|{L}"][lk] for c in clss for L in (10, 25, 45)]
        dd = [x["d_dps"] for x in xs]
        de = [x["d_ehp"] for x in xs]
        dm = [x["d_ehp_ms"] for x in xs]
        t = f"{'·'.join(CN[c] for c in clss)} {LN[lk]} DPS {pct(min(dd))}~{pct(max(dd))} · EHP {pct(min(de))}~{pct(max(de))}"
        if lk == "cloth":
            t += f" (마나 보호막 넣으면 {pct(min(dm))}~{pct(max(dm))})"
        parts.append(t)
    return ", ".join(parts)


def md():
    L = []
    w = L.append
    sim_lost = sim_summary()
    tl = TT.all_lines()
    w("# 미궁 라비린스 — 방어구 겉모습 장단점 (TASK B, 0.3.5 안)")
    w("")
    w("주인이 고른 방향 \"방어구 겉모습별 장단점\"을 숫자로 만든다. 판금·가죽·천이 저마다 좋은 점과 나쁜 점을 갖는다.")
    w("같은 레벨에서 '단단하지만 느린 옷', '빠르고 날카롭지만 얇은 옷', '스킬이 세지만 몸이 약한 옷' 가운데 고르게 한다.")
    w("")
    w("- 전투 규칙은 `combat_spec` 을 그대로 따른다: 힘 = 물리 공격력, 지능 = 마법 공격력, 민첩 = 공격 속도·치명·회피, 무기마다 공격 간격, 공격 속도 상한 +60%, 회피 상한 40%(보스 패턴 회피 불가).")
    w("- 새 주인 결정을 따른다: 요구 능력치는 '그리고(AND)'만 (`requires_any` 없음), 두 능력치로 나눔, 장비에 층 표시 없음, 무기 종류 없음.")
    w("- 데이터: `look_spec.json` (설정 기본값 · 방어구 119부위 요구 능력치 · 검사 · 시뮬레이션 표)")
    w("- 스크립트(모두 `tools/`): `lk_core.py`(겉모습·요구 규칙) · `lk_model.py`(기대값 모델, combat_spec `ce_model` 위) · `lk_sim.py`(시뮬레이터, combat_spec `ce_sim` 위) · `lk_reqcheck.py`(구간 검사) · `lk_tooltip.py`(툴팁 폭) · `lk_results.py` · `lk_spec.py`(이 문서).")
    w("")
    w("## 0. 한눈에")
    w("")
    w(t_piece())
    w("")
    w("- 효과는 **부위마다 같은 값**이다. 두 부위면 두 배. 판금 2 + 가죽 2 로 섞으면 반씩 받는다. 4부위 효과는 머리·몸·다리·발이 모두 같은 겉모습일 때만.")
    w("- 방패는 판금 한 부위로 친다(숨은 효과만). 4부위 수에는 들지 않는다.")
    w("- 1층 옷(수련생·길잡이)은 '평상복'이다. 겉모습 효과가 없다. 2층부터 고른다.")
    w("- 숫자는 굴리지 않는다. 희귀도·레벨·강화와 상관없이 같다. 겉모습의 '성격'이지 힘이 아니다.")
    w("- 방어구 요구 능력치: 합 = ceil(1.1 × 2.5(L−1)), 두 능력치를 60 : 40 으로. 앞 능력치는 겉모습(판금 체력 · 가죽 민첩 · 천 지능 또는 정신), 뒤 능력치는 세트의 정체성. §3.")
    w("- 검사: 모든 직업이 모든 5레벨 구간에서 알맞은 한 벌을 입는다(칭호 없이). 11레벨부터는 세 겉모습 모두 입을 수 있다(광전사·그림자 11–15 의 천만 '세금'이 큼). §3.4.")
    w("- 기대값 모델: 제 겉모습(직업이 늘 입던 겉모습)은 DPS ±10% 안 (사제 Lv45 +20% 하나 — 천 세트의 지능 줄), 겉모습마다 엄격히 이기는 쪽이 없는 조합이 직업마다 둘 이상. §4.")
    w("- 시뮬레이터(솔로): 1·2층은 바뀌지 않는다(평상복). 3층부터 제 겉모습이 조금 편해진다. 판금은 '느리지만 안전', 가죽·천은 '빠르지만 위험'. 세 겉모습 중 하나가 피해·받은 피해·클리어율 셋 다 이기는 경우는 물리 직업의 천, 마법 직업의 가죽뿐이다(기본 스탯 줄 탓). §5.")
    w("")
    w("## 1. 규칙")
    w("")
    w("### 1.1 겉모습은 어디서 오나")
    w("")
    w("| 경우 | 겉모습 |")
    w("|---|---|")
    w("| 세트 방어구 | `sets.<id>.look` (heavy · light · cloth) — 지금 장비 텍스처가 쓰는 값 그대로 |")
    w("| 세트에 `look_effects: false` | 평상복 — 효과 없음, 4부위로 안 셈 (수련생 `novice` · 길잡이 `wayfarer`). 텍스처는 `look` 그대로 |")
    w("| 세트 없는 투구 | `items.<id>.look` (새 필드): 이끼 석관 투구 판금 · 여왕의 면사포 가죽 · 균사왕의 관 천 · 수문 망령의 투구 판금 · 악몽의 왕관 `any` |")
    w("| 방패 | 언제나 판금 (적지 않는다) |")
    w("| `any` (악몽의 왕관) | 자기 숨은 효과는 없다. 4부위를 셀 때 나머지 세 칸의 겉모습으로 센다(신화 보상의 덤) |")
    w("")
    w("### 1.2 계산 (combat_spec §3 의 식에 이어서)")
    w("")
    w("```")
    w("n[겉모습]  = 그 겉모습 부위 수 (요구 능력치를 맞춘 것만, 방패 = 판금 1)")
    w("합[키]     = Σ n[겉모습] × piece[겉모습][키]")
    w("더하는 키   damage_reduction · move_speed · evasion · crit_chance · attack_speed · skill_damage → 장비 스탯처럼 더함 (상한 그대로)")
    w("방어       = (VIT × 0.5 + 장비 방어) × (1 + 합[defense_pct])")
    w("최대 HP    = (직업·레벨·VIT·장비 HP) × (1 + 합[hp_pct])")
    w("MP 재생    = (직업 + WIS × 0.05 + 장비) × (1 + 합[mana_regen_pct])")
    w("재사용 대기 = 기본 × (직업 0.9, combat_spec) × (1 − 재사용 감소) × (1 + 합[cooldown_pct])   (0.5 아래로 안 내려감)")
    w("회피       = clamp(0.001 × DEX + 장비 + 합[evasion], 0, 0.40)")
    w("밀려남 저항 = clamp(0.003 × STR + (판금 4부위 ? 0.60 : 0), 0, 0.85)  — 보스가 미는 것에는 안 듬")
    w("4부위      = 머리·몸·다리·발 중 같은 겉모습 수 + any 수 ≥ 4")
    w("```")
    w("")
    w("- 판금의 '재사용 대기 +2%' 와 천의 '−1.5%' 는 재사용 감소 스탯(상한 40%)과 따로 곱한다. 그래서 재사용 감소가 0 인 사람도 똑같이 느낀다.")
    w("- 회피가 0 아래로 내려가지 않는다. 판금의 회피 −1%p 는 민첩을 찍은 사람에게만 아프다. 민첩 사수가 판금을 입는 값이다.")
    w("- 요구 능력치를 못 맞춘 부위는 숨은 효과도 4부위 수도 없다(지금 '스탯이 빠진다' 규칙과 같다).")
    w("")
    w("### 1.3 4부위 효과")
    w("")
    w("**판금 — 버팀**")
    w("- 몬스터·함정·다른 플레이어의 밀쳐내기: 세기 × (1 − 0.60). 힘의 밀려남 저항(0.3%/점)과 더한다. 상한 85%.")
    w("- 기절·속박·빙결: 시간 × (1 − 0.40). 정신의 '해로운 효과 감소'와 따로 곱한다.")
    w("- 보스가 미는 것·거는 것은 그대로다. 보스 싸움의 짜임을 깨지 않으려고. 툴팁에 '(보스 제외)'.")
    w("")
    w("**가죽 — 구르기**")
    w("- 땅 위에서 웅크리기 키를 0.3초 안에 두 번 누르면(누름-뗌-누름) 움직이던 방향으로 3.5칸 구른다. 아무 방향도 안 누르고 있으면 뒤로 2칸.")
    w("- 구르는 0.4초 동안 '피할 수 있는 공격'은 모두 회피한다(회피 숫자가 뜬다). 보스 패턴은 지금처럼 회피 불가 — 몸이 경고 범위 밖으로 나가는 것으로만 피한다.")
    w("- 8초에 한 번. 다시 쓸 수 있으면 본인에게만 작은 가죽 소리. 큰 글씨 없음.")
    w("- 못 쓰는 때: 공중·물속·탈것·활공·기절·속박·빙결. 침묵이어도 쓸 수 있다(스킬이 아니다).")
    w("- 웅크리기+F/Q/클릭 스킬을 누르다 잘못 구르지 않게: 방향 키를 누르고 있을 때, 그리고 웅크리기 조합 스킬을 쓴 뒤 0.4초 안이면 구르지 않는다. `/스탯` 화면에서 끌 수 있다(사람마다).")
    w("")
    w("**천 — 마나 보호막**")
    w("- 받는 최종 피해(방어·감소·막기 뒤, 보호막 다음)의 20% 를 MP 가 대신 받는다. MP 1 = 피해 2.")
    w("- MP 가 최대 MP 의 20% 아래면 쉰다. 스킬 쓸 MP 는 남는다. 지속 피해·고정 피해에도 든다.")
    w("- 흡수할 때 몸 둘레에 옅은 하늘색 빛 (0.3초에 한 번까지). 숫자는 HP 로 받은 몫만 뜬다.")
    w("")
    w("### 1.4 툴팁 줄 폭 (330px · 20줄 안)")
    w("")
    w("| 줄 | 폭 |")
    w("|---|---|")
    for lk, ls in tl.items():
        for l, wd in ls:
            w(f"| `{strip(l)}` | {wd}px |")
    w("")
    w("## 2. 섞어 입기 — 쓸 만한 빌드")
    w("")
    w("기대값 모델, 그 레벨에 흔한 장비(6층부터 영웅까지), 요구 능력치를 먼저 채우고 나머지는 combat_spec '알맞은 분배' 비율. '제 겉모습 대비'는 같은 직업이 늘 입던 겉모습(새 규칙)과 비교한 값. EHP 는 마나 보호막 포함(MP 절반을 보호막에 쓴다고 봄).")
    w("")
    w(t_mixed())
    w("")
    w("- **피하며 치는 전사**(광전사·수호기사 가죽): 피해 +30% 안팎, 버티기는 절반. 회피·치명·공속이 같이 오른다. 요구 민첩은 치명·공속이 되니 버리는 포인트가 아니다.")
    w("- **단단한 마법사**(비전술사 판금): 피해 −15~25%, 버티기 +50~100%. 재사용 대기 +8% 와 느린 걸음이 값이다. 정신·지능 짝 판금(녹청 수문 경비, 균사 갑각, 색인 방벽)이 쉽다.")
    w("- **성기사 사제**(사제 판금 + 정신 방패): 정신 분배가 같아 치유력은 거의 그대로(천의 치유력 줄만큼 낮다), 피해는 조금 낮고 버티기는 크게. 파티 앞줄을 같이 설 수 있다.")
    w("- **버티는 사수**(사냥꾼·그림자 판금): 같은 레벨 판금의 HP 줄이 커서 버티기가 크게 오른다. 대신 피해 −10% 안팎, 걸음 −8%, 회피 −4%p. 거리를 벌리는 싸움이 둔해진다.")
    lb = RES["model"]["berserker|45"]["light"]
    w(f"- **스킬로 싸우는 전사**(광전사 천, 서고지기 지능·체력): 지능이 재사용 감소가 되고 천이 스킬 피해·재사용을 준다. 다만 같은 레벨 가죽 광전사(기준 대비 {pct(lb['d_dps'])} / {pct(lb['d_ehp'])})에게 둘 다 진다 — 재미 빌드다(§13).")
    w("- **반반**(판금 2 + 가죽 2): 4부위 효과는 없지만 양쪽 장단점을 반씩. 머리·발을 가죽으로 두면 걸음 손해가 반.")
    w("- **빠른 마법 검사**(비전술사 먹물 장막, 민첩·지능 짝): 지능 요구가 겹쳐 싸게 입고, 가죽의 치명·공속이 마법 기본 공격과 스킬 위력(공속의 반)에 든다. 천보다 피해가 높고 버티기는 낮다. 같은 겉모습이라도 요구 짝이 빌드를 가른다.")
    w("- 이 표의 어느 빌드도 제 겉모습을 피해·버티기 둘 다에서 이기지 않는다. 그래서 '정답 하나'가 아니라 '고르는 것'이다.")
    w("")
    w("## 3. 요구 능력치 (방어구)")
    w("")
    w("### 3.1 규칙")
    w("")
    w("```")
    w("R(L)  = ceil(2.5 × (L − 1)), 2 이하면 0               (0.3.4 단독 요구치, L = 숨은 아이템 레벨)")
    w("T(L)  = ceil(1.1 × R(L))                              (두 능력치 합 — 조금 높다. 겹치면 싸지고, 안 겹치면 조금 비싸다)")
    w("앞    = ceil(0.6 × T)   뒤 = T − 앞                    (세 능력치면 50 / 30 / 20)")
    w("앞 능력치 = 겉모습: 판금·방패 체력 · 가죽 민첩 · 천 지능 또는 정신")
    w("뒤 능력치 = 세트 정체성: 힘(버팀·출혈 치명) · 정신(신전·회복) · 지능(룬 판금·마법 검사) · 행운(매복) · 체력(생존·지원)")
    w("한 세트 4부위는 같은 요구. 판정 능력치 = 직업 기본 + 분배 + 칭호 (장비 제외, 지금과 같음)")
    w("requires_any 삭제 — '… 중 하나' 문구도 삭제")
    w("```")
    w("")
    w("- 같은 판금이라도 세트마다 뒤 능력치가 다르다. 마법사는 정신·지능 짝 판금을, 전사는 힘 짝 판금을 싸게 입는다. 무기 요구 짝(gear_spec)과 겹치면 더 싸다.")
    w("- 세트의 스탯 줄 하나가 요구 짝과 어긋나면 **이름만** 바꾼다(값 그대로, §3.3). 예: 녹청 수문 경비의 힘 줄 → 정신 줄.")
    w("")
    w("### 3.2 세트·단품마다 요구 짝 (방어구 95 + gear_spec 안 24)")
    w("")
    w(t_sets())
    w("")
    w("### 3.3 스탯 줄 이름 바꿈")
    w("")
    w("| 세트 | 바꿈 | 왜 |")
    w("|---|---|---|")
    for sid, ren in K.STATS_RENAME.items():
        nm = K.ALL_SETS[sid]["name"]
        why = K.SET_REQ[sid][2]
        w(f"| {nm} `{sid}` | " + ", ".join(f"{SN[a]} → {SN[b]}" for a, b in ren.items()) + f" | {why} |")
    w("")
    w("이미 가진 아이템: 굴린 값 PDC 의 키만 바꾼다(combat_spec §10.2 와 같은 때·같은 깃발 `ITEM_COMBAT_VER` 35).")
    w("")
    w("### 3.4 검사 — 직업 × 5레벨 구간 (분배 초기화 뒤, 칭호 없음)")
    w("")
    w("내 능력치 = 직업 기본 + 시작 5 + 레벨마다 5. 한 벌 = 무기(그 직업이 쓰는 두 능력치를 60 : 40 으로 요구한다고 봄, 합 T) + 그 구간까지 나온 겉모습별 가장 높은 세트 4부위. 검사 레벨 = 그 한 벌에서 가장 높은 아이템 레벨(얻자마자 입는 가장 빡빡한 때). '알맞음' = 포인트가 모자라지 않고, 직업이 안 쓰는 능력치에 넣는 포인트가 25% 이하. 칸 = 알맞게 입는 겉모습 (가장 빡빡한 남는 포인트).")
    w("")
    w("**지금 있는 방어구만**")
    w("")
    w(t_reqcheck(REQ))
    w("")
    w("**gear_spec 새 6세트를 넣으면**")
    w("")
    w(t_reqcheck(REQN))
    w("")
    bad = []
    for k, r in REQ.items():
        for lk in ("heavy", "light", "cloth"):
            e = r.get(lk)
            if e and not e["ok"]:
                cls, band = k.split("|")
                bad.append(f"{CN[cls]} {band} {LN[lk]}({K.ALL_SETS[e['set']]['name']}: 남는 {e['left']}, 세금 {e['tax']})")
    w("- 한 구간을 통째로 못 입는 직업은 없다. 1–5 는 평상복(요구치가 직업 기본 능력치로 거의 찬다).")
    w("- 알맞지 않은 칸(입을 수는 있지만 세금이 큼): " + " · ".join(bad) + ".")
    w("- 2층 전후(6–10)는 마법사의 가죽, 전사·사수의 천이 비싸다. 2층부터 '제 겉모습 + 판금'은 모두 된다.")
    w("")
    w("### 3.5 구간 × 겉모습 빈칸 (무기·장비 설계자에게)")
    w("")
    w("세트가 처음 나오는 구간만 센 것. 빈칸은 아래 구간의 세트를 계속 입는다. 장비를 늘릴 때 이 칸부터 채우면 구간마다 겉모습 셋이 다 새로 나온다.")
    w("")
    w("| 구간 | 판금 | 가죽 | 천 |")
    w("|---|---|---|---|")
    for lo, hi in RQ.BANDS:
        cells = []
        for lk in ("heavy", "light", "cloth"):
            secs = []
            for sid, (sh, ident, why) in K.SET_REQ.items():
                s = K.ALL_SETS.get(sid)
                if not s or K.SET_LOOK_OVERRIDE.get(sid) == "plain" or s.get("look") != lk:
                    continue
                lvl = min(K.ALL_ITEMS[p]["level_req"] for p in s["pieces"])
                if lo <= lvl <= hi:
                    tag = "*" if s.get("proposed") else ""
                    secs.append("/".join(SN[x] for x in sh) + tag)
            from collections import Counter
            cc = Counter(secs)
            cells.append(", ".join(k + (f" ×{n}" if n > 1 else "") for k, n in cc.items()) or "—")
        w(f"| {lo}–{hi} | " + " | ".join(cells) + " |")
    w("")
    w("`*` = gear_spec 안. 권하는 짝: 26–30 판금 체력/지능, 36–40 천 정신/체력, 16–20 천 지능/정신, 46–50 겉모습마다 하나(판금 체력/정신 · 가죽 민첩/힘 · 천 지능/체력).")
    w("")
    w("## 4. 기대값 모델 (Lv10 · 25 · 45)")
    w("")
    w("combat_spec 의 `ce_model.new_player` 를 그대로 쓰고 겉모습만 얹었다(`lk_model.build`, 겉모습 끄면 combat_spec 값과 소수점까지 같다). DPS = 기본 공격 + 직업 스킬 지속. EHP = HP × 방어 × 피해 감소 × 회피(0.8배) × 막기. 기준 = combat_spec 판(직업 대표 방어구, 겉모습 없음, 0.3.4 방어구 요구치), 세트 효과 넣음. 칸 = 기준 대비 DPS / EHP, **굵게** = 제 겉모습. 방어구는 겉모습마다 그 레벨 세트 중 √(DPS×EHP)가 가장 큰 것.")
    w("")
    for Lv in (10, 25, 45):
        w(f"**Lv{Lv}**")
        w("")
        w(t_model(Lv))
        w("")
    w("입은 세트와 분배 (Lv25):")
    w("")
    w(t_model_sets(25))
    w("")
    w("- 제 겉모습 (기준 대비, Lv10·25·45): " + native_ranges() + ".")
    nd = sum(len(v) for k, v in RES["dominance"].items() if not k.endswith("|5"))
    nd0 = sum(len(v) for k, v in RES["dominance_noimp"].items() if not k.endswith("|5"))
    w(f"- '엄격히 지는 겉모습'은 물리 직업의 천, 마법 직업의 가죽뿐이다. 겉모습 효과를 끄고 봐도 같다(기본 스탯 줄 — 천 옷에는 지능·정신·MP, 가죽에는 민첩·회피 줄이 있다). 겉모습 효과는 엄격한 지배를 줄였다(Lv10·25·45, 효과 끔 {nd0}건 → 켬 {nd}건).")
    w("- 판금과 가죽(물리), 판금과 천(마법)은 어느 레벨에서도 서로 이기지 못한다: 판금 = EHP, 다른 쪽 = DPS.")
    w("")
    w("## 5. 시뮬레이터 (솔로)")
    w("")
    w("### 5.1 방법")
    w("")
    w("- `lk_sim.py` = combat_spec `ce_sim`(0.3.4 r4 시뮬레이터 + 새 전투 모델) + 겉모습. 능력치는 `lk_model.build` 와 같다(레벨이 오르면 같은 장비로 다시 계산).")
    w("- 더한 것(기준·변형 모두): 세트 효과, 장비의 받는 피해 감소·재사용 감소·스킬 피해 줄 (ce_sim 은 뺐던 것).")
    w("- 겉모습만: 이동 속도 변화 Δ 만큼 경고 피하기 창 w′ = 0.3 + (w − 0.3)(1 + Δ), 사냥꾼(거리 벌리기)은 근접 몹이 닿는 비율 × (1 − 1.5Δ). 구르기 = 8초마다 한 번, 못 피한 경고 공격을 초보 30% · 보통 50% · 숙련 70% 로 피함. 마나 보호막 = 위 규칙 그대로. 버팀 = 시뮬레이터에 플레이어 밀려남·기절이 없어 0 (보수적).")
    w("- 판 = 층마다 40번, 같은 시드. 층 입장 = 그 층 첫 레벨, 흔한 장비, 물약 10. 방 = 죽지 않게 한 전투방 60개(숙련·보통).")
    w("")
    w("### 5.2 초반 (1~3층)")
    w("")
    w("1층은 평상복이라 바뀌지 않는다. 2층(Lv5)에는 겉모습 부위가 이끼 석관 투구·방패뿐이다.")
    w("")
    w(t_sim_early())
    w("")
    w("### 5.3 3 · 6 · 10층")
    w("")
    w("칸 = 방 초당 피해 / 방 하나에 받은 피해(최대 HP 비율) · 클리어율 보통 실력(보통)·숙련(보통)·숙련(어려움).")
    w("")
    for fl in (3, 6, 10):
        w(f"**{fl}층 (Lv{X_entry(fl)})**")
        w("")
        w(t_sim(fl))
        w("")
    w("### 5.4 읽기")
    w("")
    grp = {}
    for k, v in sim_lost.items():
        fl, cls = k.split("|")
        for x in v:
            loser, winner = x.split("<")
            grp.setdefault((cls, loser), []).append((fl[1:], winner))
    parts = []
    for (cls, loser), lst in sorted(grp.items(), key=lambda kv: (CL.index(kv[0][0]), kv[0][1])):
        fls = sorted({int(f) for f, _ in lst})
        wins = sorted({LN[wn] for _, wn in lst})
        parts.append(f"{CN[cls]}의 {LN[loser]}({'·'.join(str(f) for f in fls)}층, {'·'.join(wins)}에게)")
    w("- 세 지표(방 초당 피해·받은 피해·클리어율 평균)를 모두 지는 겉모습: " + (", ".join(parts) or "없음") + ". 물리 직업의 천과 사제 10층의 가죽뿐이다 — §4 와 같은 결론.")
    dc = DECOMP
    g = lambda k: dc[k] * 100  # noqa: E731
    w(f"- 비전술사 10층(보통 실력·보통 / 숙련·어려움, 100판): 지금 규칙 {g('rules_old|0.2|average|normal'):.0f}% / {g('rules_old|0.2|skilled|hard'):.0f}%"
      f" → 새 요구 짝·줄 이름(서고지기 지능·체력, 정신 줄 → 체력 줄) {g('req_only|0.2|average|normal'):.0f}% / {g('req_only|0.2|skilled|hard'):.0f}%"
      f" → 천 숨은 효과 {g('looks|0.0|average|normal'):.0f}% / {g('looks|0.0|skilled|hard'):.0f}%"
      f" → 마나 보호막 10% {g('looks|0.1|average|normal'):.0f}% / {g('looks|0.1|skilled|hard'):.0f}% · 15% {g('looks|0.15|average|normal'):.0f}% / {g('looks|0.15|skilled|hard'):.0f}% · 20% {g('looks|0.2|average|normal'):.0f}% / {g('looks|0.2|skilled|hard'):.0f}%."
      " 오른 몫의 반은 요구 짝, 반은 마나 보호막이다. 0.3.4 의 비전술사가 깊은 층에서 가장 약했던 직업 중 하나라 그대로 둔다(손잡이 `absorb`).")
    w("- 판금은 '느리지만 안전'이다. 잘 죽는 직업(그림자·비전술사·사냥꾼)이 판금을 입으면 보통 실력 클리어율이 크게 오르고 방 초당 피해는 10~30% 준다. 솔로가 편한 쪽을 남긴다(주인 규칙).")
    w("- 가죽은 전사에게 '빠르지만 위험'이다: 방 초당 피해 +30~60%, 받은 피해 2~3배, 클리어율은 보통 실력에서 조금 낮다.")
    w("- 천은 마법 직업에게 판금보다 빠르고(방 초당 피해 +15~40%), 마나 보호막 덕에 제 옷보다 버틴다. 10층 비전술사 보통 실력 클리어율이 크게 오른다 — 지켜볼 것(조정 손잡이 `absorb`).")
    w("- 1·2층 솔로는 그대로(평상복). 3층부터 제 겉모습이 조금 편해진다(초반을 편하게 하는 방향 — combat_spec 과 같은 쪽).")
    w("")
    w("## 6. 보이는 것")
    w("")
    w("### 6.1 툴팁 (도감·대장간 목록도 같은 `ItemTooltip.lines`)")
    w("")
    w("```")
    w("영웅 판금 흉갑                                    ← 첫 줄: 희귀도 · 겉모습 · 부위 (층 숫자 없음, 평상복은 겉모습 글자 없음)")
    w("요구 체력 56 · 힘 36                              ← AND 만 (보는 사람을 알면 맞춘 것 초록, 모자란 것 빨강 '(현재 22)')")
    w("")
    w("방어 13~15                                        ← 스탯 (지금과 같음)")
    w("체력 5~7 · 힘 3~4")
    w("최대 HP 80~108 · 받는 피해 감소 2.2%~2.9%")
    w("")
    w("판금 ▲ 방어 +4% · 받는 피해 −0.5%                   ← 겉모습 줄 둘 (색 = 겉모습 색, ▲ 초록 · ▼ 붉은 회색)")
    w("     ▼ 이동 속도 −2% · 회피 −1%p · 재사용 대기 +2%")
    w("판금 4부위 · 버팀: 밀려남 −60% · 기절·속박·빙결 −40% (보스 제외)   ← 지금 4부위면 겉모습 색, 아니면 어두운 회색 + '(지금 2/4)' (보는 사람을 알 때)")
    w("")
    w("세트: 정동 성채 (4부위)")
    w("  (2) 체력 +6, 최대 HP +80")
    w("  (4) 받는 피해 감소 +5%, 방어 +10")
    w("```")
    w("")
    w("- 겉모습 줄은 세트 줄보다 앞, 스탯 바로 아래. 줄이 넘칠 때 설명(이야기) → 획득처 → 빈 줄 순으로 빠지고, 겉모습 줄은 빠지지 않는다.")
    w("- 방패: 겉모습 줄 둘 + '방패는 판금 한 부위 (4부위 수에는 안 든다)' 대신 4부위 줄을 뺀다.")
    w("- 평상복·장신구: 겉모습 줄 없음. 악몽의 왕관: '어느 겉모습과도 4부위를 이룬다' 한 줄.")
    w("- 예시 툴팁 5개의 줄 수·폭은 JSON `tooltip.examples` (가장 긴 것 " + str(max(e["count"] for e in tooltip_examples())) + "줄, 강화 줄 2개를 더해도 20줄 안).")
    w("")
    w("### 6.2 /스탯 화면")
    w("")
    w("- 요약 칸에 한 줄: `겉모습 판금 4 · 방패 1 → 버팀` (없으면 `겉모습 판금 2 · 가죽 2`). 마우스를 올리면 지금 받는 숨은 효과 합.")
    w("- 파생 능력치에 `이동 속도 −8%` · `재사용 대기 ×1.08` 을 더 보여 준다(지금 회피·재사용 감소 줄 옆).")
    w("- 단추 하나: `구르기 켜짐/꺼짐` (가죽 4부위일 때만 보임, PlayerData `look.tumble_off`).")
    w("")
    w("### 6.3 도감 · 대장간")
    w("")
    w("- 방어구 거르개: 부위 + 겉모습(판금 · 가죽 · 천 · 평상복). 겉모습은 무기 종류와 달리 게임 규칙이라 보여 준다.")
    w("- 도감 자세히 보기: 4부위 효과 설명 전문(§1.3 첫 두 줄)과 요구 짝 이름(예: '판금 · 체력과 정신').")
    w("- 획득처 줄에 층 숫자 없음(새 주인 결정, gear_spec 쪽 일).")
    w("")
    w("## 7. 설정 (config.yml)")
    w("")
    w("```yaml")
    w(CONFIG_YAML.rstrip())
    w("```")
    w("")
    w("- 키가 없으면 코드 기본값(= 위 값). `enabled: false` 면 숨은 효과와 4부위 효과가 모두 꺼진다. 요구 능력치는 items.yml 이 정하므로 그대로다.")
    w("- piece 아래 키는 StatBlock 키(더하기) 또는 `defense_pct · hp_pct · mana_regen_pct · cooldown_pct`(곱하기)만. 모르는 키는 켤 때 경고 한 줄, 무시.")
    w("")
    w("## 8. 데이터 바꿈 (items.yml)")
    w("")
    w("| 무엇 | 바꿈 |")
    w("|---|---|")
    w("| `sets.novice` · `sets.wayfarer` | `look_effects: false` 추가 (look 은 텍스처용으로 그대로) |")
    w("| 세트 없는 투구 5개 | `look:` 추가 (§1.1) |")
    w("| 방어구 95부위 (+ gear_spec 24) | `requires` 를 §3.2 값으로, `requires_any` 삭제 |")
    w("| 10세트 스탯 줄 | §3.3 이름 바꿈 (값 그대로) |")
    w("| 방어구 `classes` (드롭 편향용) | 요구 짝으로 다시 채움: 짝의 능력치가 그 직업의 주 능력치 둘(수호기사 체력·힘, 광전사 힘·체력, 사냥꾼 민첩·힘, 비전술사 지능·정신, 사제 정신·지능, 그림자 민첩·힘) 중 하나라도 들면 그 직업 (JSON `armor_items[].classes`) |")
    w("| 머리 주석 | '판금 VIT · 가죽 DEX · 천 INT|WIS' 규칙 줄 → §3.1 |")
    w("")
    w("## 9. 코드")
    w("")
    w("| 파일 | 할 일 |")
    w("|---|---|")
    for f, t in CODE:
        w(f"| {f} | {t} |")
    w("")
    w("### 9.1 이동 속도")
    w("")
    for t in MOVE_NOTES:
        w(f"- {t}")
    w("")
    w("## 10. 테스트")
    w("")
    w("| 테스트 | 확인 |")
    w("|---|---|")
    for f, t in TESTS:
        w(f"| {f} | {t} |")
    w("")
    w("## 11. 옮기기 (0.3.4 → 0.3.5)")
    w("")
    for t in MIGRATION:
        w(f"- {t}")
    w("")
    w("## 12. 다른 설계자에게")
    w("")
    for t in OTHERS:
        w(f"- {t}")
    w("")
    w("## 13. 남은 위험")
    w("")
    for t in RISKS:
        w(f"- {t}")
    w("")
    return "\n".join(L)


CODE = [
    ("content/ArmorLook (새 enum)", "HEAVY · LIGHT · CLOTH · PLAIN · ANY, `id()`·`byId`. 순수."),
    ("content/ItemDef · ItemSetDef", "`ItemDef.look()` (파싱 때 정함: item `look` → 세트 `look`(+`look_effects: false` 면 PLAIN) → 방패면 HEAVY → 없으면 PLAIN). `ItemSetDef.lookEffects`. 0.3.2 생성자는 look = null(→ 세트에서)로 남긴다."),
    ("content/ContentParser", "items `look`, sets `look_effects` 읽기. `requires_any` 를 읽지 않는다(있으면 경고 — combat/gear spec 와 같이 삭제)."),
    ("core/ContentValidator", "모든 방어구가 겉모습을 갖는가(세트 없는 투구는 `look` 필수). 방어구 `requires`: 능력치 1~3개, 합 = ceil(1.1·R(L)), 앞 능력치 = 겉모습 규칙(판금·방패 VIT, 가죽 DEX, 천 INT|WIS; plain·any 는 자유), 가장 큰 몫 ≤ 60%."),
    ("core/Settings", "`ArmorLooks` 레코드 (`armor_looks` 읽기, 기본값 = 이 명세). piece 키 검사, 범위 검사(효과 ±0.5 안, cooldown_pct 합 ≥ −0.5)."),
    ("items/EquipmentListener.contribute", "요구를 맞춘 방어구·방패마다 `block.add(\"look.\" + id, 1)`, 머리·몸·다리·발은 `block.add(\"look_body.\" + id, 1)` 도. PLAIN 은 아무것도 안 더함, ANY 는 `look_body.any` 만."),
    ("stats/StatCalculator", "`compute(..., ArmorLooks looks)` (기존 시그니처는 looks = 꺼짐으로 남김). 위 키를 읽어 §1.2 계산: 더하는 키는 bonus 사본에 더하고, 방어·최대 HP·MP 재생에 곱하고, `cooldownMult`·`fullLook`·`ccResist` 를 정한다. 밀려남 저항 = clamp(0.003·STR + 버팀, 0, 0.85). 순수 — 단위 테스트."),
    ("stats/DerivedStats", "새 필드 `fullLook`(ArmorLook) · `lookCounts`(EnumMap) · `cooldownMult` · `ccResist`. `knockbackResistance` 는 뜻이 넓어짐(힘 + 버팀)."),
    ("stats/StatService.applyAttributes", "`MOVEMENT_SPEED` 식 그대로(moveSpeed 에 겉모습이 들어 있음). `KNOCKBACK_RESISTANCE` = `s.knockbackResistance()` (바닐라 밀쳐내기·PvP 바닐라 경로). §9.1."),
    ("combat/DamageService", "① `deal`: 대상이 구르는 중이고 `ctx.canEvade()` 면 회피 = 1.0. ② `knockback(target, from, s)`: 대상이 플레이어면 × (1 − 밀려남 저항), 공격자가 보스면 그대로. ③ 마나 보호막은 Hook 으로(아래)."),
    ("classes/LabyrinthStatusEffectService", "`apply`: 대상이 플레이어이고 id ∈ {stun, root, frozen} 이고 source 가 보스가 아니면 시간 × (1 − ccResist). `knockback`(효과): 플레이어면 × (1 − 밀려남 저항), source 가 보스면 그대로."),
    ("mobs/MobSkills.push", "대상이 플레이어면 세기 × (1 − 밀려남 저항)."),
    ("bosses/Boss.push · pull · impl", "바꾸지 않는다(보스 제외). 주석 한 줄."),
    ("classes/LabyrinthClassService (직업 스킬 쿨다운)", "`CooldownTracker.effective(base, cdr) × cooldownMult` (combat_spec 의 ×0.9 기본 위에)."),
    ("items/weaponskills/LabWeaponSkillService", "`cd = s.cooldown() × (1 − cdr) × cooldownMult` (cooldown_slow ×1.3 은 그 뒤 그대로)."),
    ("items/ArmorLookService (새, ItemsModule)", "구르기: `PlayerToggleSneakEvent` 로 누름 시각 기록 → 순수 `TumbleInput.onSneak(now, onGround, hasMoveInput, blocked, lastComboAt)` 가 TUMBLE/NONE. 방향 = `Player#getCurrentInput()` (앞뒤좌우) + 바라보는 방향, 없으면 뒤로. 속도 = 수평 1.05·dir + y 0.12(3.5칸), 0.4초 `tumblingUntil`, 쿨다운 8초, 준비 소리·작은 먼지. 마나 보호막: `DamageService.Hook.absorb` (StatusEffectService 보다 뒤에 등록 → 보호막 다음), 순수 `ManaShield.split(damage, mp, maxMp, cfg)` → (hp 피해, mp 비용), `classes().useMana`. `tumbling(Player)` 를 DamageService 에 알려 줌."),
    ("items/ItemTooltip", "첫 줄 `{희귀도} {겉모습} {부위}` (층 글자 삭제). 스탯 아래 `lookLines(def, viewer)` 두 줄 + 4부위 한 줄(방패는 대신 안내 한 줄). 줄 줄이기 단계에서 겉모습 줄은 남김. 겉모습 이름·색은 Settings 에서."),
    ("items/GearItemService.applyEquippable", "장착 소리를 `def.look()` 로 (지금은 세트 look) — 방패·단품 투구도 맞는 소리."),
    ("items/GearItemService.baseRolls", "§3.3 스탯 줄 이름 바꿈 (combat_spec 굴림 옮기기와 같은 깃발 35)."),
    ("ui/menus/StatsMenu · ChatMenuService", "겉모습 요약 줄, 이동 속도·재사용 대기 배율, 구르기 켜기/끄기 단추 (§6.2)."),
    ("ui/menus/CodexMenu · 대장간 목록", "방어구 겉모습 거르개, 자세히 보기의 4부위 설명."),
    ("data/PlayerData", "`look.tumble_off` (불린, 기본 false)."),
    ("resourcepack (equipment.py · armor.py)", "바꿀 것 없음 — `sets.<id>.look` 이 텍스처를 정하는 것은 그대로. 새 세트도 look 만 맞으면 된다."),
]

MOVE_NOTES = [
    "지금처럼 `MOVEMENT_SPEED` 기본값 = 0.1 × (1 + moveSpeed). moveSpeed = 장비 이동 속도 줄 + 세트 + 겉모습(판금 −2%/부위, 가죽 +1%/부위) + 버프, clamp(−0.6, +0.3). 따로 수정치를 두지 않는다 — 한 곳에서 계산.",
    "상태이상 둔화(`fx_move` 곱하기 수정치)는 그 위에 곱한다. 달리기 ×1.3 도 바닐라 그대로. 그래서 판금 4부위 + 방패(−10%)는 걷기·달리기 모두 −10%.",
    "보통 판금 사람(장화 이동 속도 +3~5%)은 실제로 −5% 안팎. 가죽 4부위 + 장화는 +7~9%.",
    "바닐라는 걷기 속도에 따라 시야각(FOV)을 바꾼다. 장비를 갈아입을 때 화면이 살짝 당겨지거나 퍼진다(클라이언트 설정 'FOV 효과'로 끌 수 있음). 값이 작아(±10% 안) 그대로 둔다. 툴팁·도감 안내 없음.",
    "기본값을 바꾸는 방식이라 플러그인을 끄면 마지막 값이 남는다(지금도 같음). `StatService.disable` 에서 0.1 로 되돌리는 한 줄을 더한다.",
    "구르기는 이동 속도와 따로다(속도 벡터). 둔화·판금 다리를 섞어도 구르는 거리는 같다. 속박·기절·빙결이면 못 구른다.",
    "PvP: 이동 속도 차이가 그대로 나온다. 쫓는 쪽·도망가는 쪽 모두 가죽이 유리 — combat_spec §8 의 한 방 상한과 함께 지켜볼 것.",
]

TESTS = [
    ("ArmorLookTest (새, 순수)", "부위 수 → 숨은 효과 합 · 4부위 판정(방패는 안 셈, any 는 나머지 셋과, 2+2 는 없음) · 곱하는 키(방어·HP·MP 재생·재사용 배율 ≥ 0.5) · 회피 0 아래로 안 감 · 밀려남 저항 상한 0.85 · enabled=false 면 0."),
    ("StatCalculatorTest", "겉모습 없는 compute 결과가 그대로(옛 시그니처) · 판금 4 + 방패 = 방어 +20%, 받는 피해 +2.5%p, 이동 −10%, 재사용 ×1.10."),
    ("ManaShieldTest (새, 순수)", "20% 흡수 · MP 비용 = 흡수 ÷ 2 · MP 20% 아래면 0 · 경계 바로 위면 남은 만큼만 흡수 · 0 피해."),
    ("TumbleInputTest (새, 순수)", "0.3초 안 두 번 = 구름, 0.31초 = 아님 · 쿨다운 8초 · 공중·속박·꺼짐이면 아님 · 웅크리기 조합 스킬 뒤 0.4초 안이면 아님 · 방향 없음 = 뒤로."),
    ("CrowdControlTest (새, 순수)", "`duration(base, ccResist, fromBoss)` · `knockback(strength, resist, fromBoss)` — 보스면 그대로."),
    ("ArmorLookDataTest (새)", "방어구 119부위가 모두 겉모습을 갖는다 · 세트 look ∈ heavy|light|cloth · `look_effects: false` 는 수련생·길잡이뿐 · 세트 없는 투구는 `look` 이 있다 · 방패에는 `look` 을 적지 않는다."),
    ("ArmorRequirementsDataTest (GearRequirementsDataTest 의 방어구 몫을 바꿈)", "requires 만(requires_any 없음) · 능력치 1~3개 · 합 = ceil(1.1·R(L)) · 앞 능력치 = 겉모습 규칙 · 가장 큰 몫 0.5~0.6 · 이름 바꾼 스탯 줄이 요구 짝과 맞음 · 한 세트 4부위 요구가 같다."),
    ("ArmorBandFitTest (새, lk_reqcheck 를 옮김)", "직업 6 × 구간 10: 알맞은 겉모습이 하나 이상(1–5 는 평상복) · 11레벨부터 둘 이상 · Lv1 시작 포인트로 시작 지급·평상복을 다 입는다."),
    ("TooltipFitTest", "겉모습 두 줄 + 4부위 줄이 330px 안, 모든 방어구 툴팁이 강화 줄 포함 20줄 안 (가장 긴 것 = 전설 세트 투구)."),
    ("WeaponFreedomTest · EarlySoloDataTest", "층 숫자 대신 레벨 창으로 (gear_spec) — 방어구 쪽은 '1층 장비' 를 '아이템 레벨 ≤ 5' 로."),
]

MIGRATION = [
    "겉모습은 콘텐츠(ItemDef)에서 오므로 아이템을 다시 쓸 것이 없다. 이미 가진 방어구도 바로 효과를 받는다.",
    "요구 능력치가 바뀌어 입은 방어구가 '못 맞춤'이 되면 지금 규칙대로 입은 채 두고 스탯·겉모습 효과만 빠진다(한 번 알림). combat_spec 의 무료 스탯 초기화(`stats.role_reset_035`)로 다시 맞춘다.",
    "접속 안내(combat_spec §10.3 줄 뒤에 한 줄): \"<gray>방어구에 겉모습 효과가 생겼습니다. 판금·가죽·천의 장단점은 툴팁에서 보세요.\"",
    "스탯 줄 이름 바꿈(10세트): combat_spec §10.2 와 같은 때(`GearItemService.baseRolls`, 깃발 `ITEM_COMBAT_VER` < 35)에 PDC 키만 바꾼다. 값·강화·시드는 그대로.",
    "config 에 `armor_looks` 가 없으면 코드 기본값. `Settings.upgrade` 에 더할 것 없음.",
    "구르기 끔 기본 false — 처음 가죽 4부위를 입으면 행동 막대에 한 번: \"<#c9a46a>가죽 4부위 · 구르기</#c9a46a> <gray>웅크리기 두 번 (/스탯 에서 끌 수 있음)\".",
]

OTHERS = [
    "gear_spec(장비 늘리기): 새 방어구 세트는 `look` + 요구 짝(§3.1 규칙: 앞 = 겉모습, 뒤 = 정체성) + T(L) 합. `requires_any` 를 쓰지 않는다. §3.5 빈칸부터 채우면 구간마다 겉모습 셋이 다 나온다. 6세트 안의 요구치는 §3.2 표 값(이 명세가 다시 정함).",
    "gear_spec(드롭 편향): 방어구도 무기와 같은 규칙 — 65% 로 '요구 능력치 중 하나가 내 능력치(직업 기본 + 분배) 상위 2개 안'인 것. 겉모습으로 거르지 않는다(섞어 입기를 막지 않게).",
    "gear_spec(무기 요구 짝): 검사(§3.4)는 '직업마다 그 직업 두 능력치 짝 무기가 구간마다 하나는 있다'고 본다. 수호기사·광전사 힘/체력, 사냥꾼·그림자 민첩/힘, 비전술사 지능/정신, 사제 정신/지능.",
    "combat_spec: 가죽의 공격 속도는 AS 에 더한다(상한 +60% 안, 스킬 위력 (1 + 0.5·AS) 에도 반이 든다). 회피 상한 40% — 가죽 4부위(+6%p) + 민첩 130 + 장비면 닿는다. 재사용 배율은 직업 ×0.9 위에 곱한다.",
    "unique_spec: 방어구에는 고유 효과가 없다. 겉모습 효과와 겹치는 무기 고유 효과(예: `momentum` 공속, `steadfast` 받는 피해 감소)는 그대로 더한다.",
    "보스 설계: 판금 4부위 '버팀'은 보스의 밀쳐내기·기절에 안 든다. 보스 코드는 바꿀 것이 없다(Boss.push 를 쓰는 한).",
]

RISKS = [
    "판금의 기본 스탯(같은 레벨 HP 줄 +300~500)이 커서, 잘 죽는 직업에게 판금이 '보통 실력 솔로의 정답'처럼 보일 수 있다(시뮬레이터 6·10층 그림자·비전술사). 대신 방 초당 피해 −10~30%. 너무 많이 입으면 판금 `cooldown_pct` 0.02 → 0.03, `move_speed` −0.02 → −0.025 가 첫 손잡이.",
    "마나 보호막은 깊은 층 마법사를 크게 살린다(10층 비전술사 보통 실력 61% → 88%). 강하면 `absorb` 0.20 → 0.15 (→ 86%) 또는 0.10 (→ 83%). 효과가 처음 10% 에서 거의 다 나오므로 끄는 쪽보다 줄이는 쪽이 낫다.",
    "구르기 입력이 웅크리기 조합과 겹친다. 조합 뒤 0.4초 막음 + 방향 키 조건 + 끄기 단추로 줄였지만 테스트 서버에서 한 번 손으로 확인한다. `getCurrentInput` 이 26.3 Paper 에 없으면 바라보는 방향으로만(뒤로 가기 없음).",
    "물리 직업의 천, 마법 직업의 가죽은 거의 늘 손해다(기본 스탯 줄). 주인이 원하면 '전사용 천'(체력·지능 짝, 스킬 피해 줄) 같은 세트를 gear_spec 에서 따로 만든다 — 이 명세는 기본 스탯을 바꾸지 않는다.",
    "보스 제외 규칙을 모르면 '버팀이 안 든다'고 느낄 수 있다. 툴팁에 '(보스 제외)'를 남긴다.",
    "시뮬레이터의 2층 이후 보스는 일반형이고 플레이어 밀려남·기절이 없다 — 버팀의 값은 0 으로 쳤다(실제로는 조금 더 좋다).",
]


def js():
    tl = TT.all_lines()
    rows = []
    prim = {"guardian": ("VIT", "STR"), "berserker": ("STR", "VIT"), "hunter": ("DEX", "STR"), "arcanist": ("INT", "WIS"),
            "priest": ("WIS", "INT"), "shadow": ("DEX", "STR")}
    for r in RES["armor"]:
        shares = K.req_spec(r["id"])[0]
        cls = [c for c in CL if set(shares) & set(prim[c])] if shares else []
        rr = dict(r)
        rr["classes"] = cls
        rr["requires_pair"] = shares
        rows.append(rr)
    out = dict(
        version="look-b1 (labyrinth 0.3.4 → 0.3.5 안, combat_spec combat-e1 위)",
        summary=dict(
            looks={lk: dict(name=v["name"], piece=v["piece"], full=v["full"]) for lk, v in K.LOOKS.items()},
            rule="부위마다 같은 값(방패 = 판금 1, 4부위는 머리·몸·다리·발만), 굴림·희귀도·레벨·강화와 무관, 평상복(수련생·길잡이) 효과 없음",
            requirement="T(L) = ceil(1.1 × ceil(2.5(L−1))), 앞 ceil(0.6T) = 겉모습 능력치, 뒤 = 세트 정체성, requires_any 삭제",
        ),
        armor_looks=config_json(),
        config_yaml=CONFIG_YAML,
        formulas=dict(
            counts="n[look] = 요구를 맞춘 그 겉모습 부위 수 (방패 = heavy 1), body 수 = 머리·몸·다리·발만, any = body 와일드카드",
            additive="damage_reduction · move_speed · evasion · crit_chance · attack_speed · skill_damage → StatBlock 에 더함 (상한 그대로)",
            defense="(VIT × 0.5 + 장비) × (1 + Σ defense_pct)",
            max_hp="(직업·레벨·VIT·장비) × (1 + Σ hp_pct)",
            mana_regen="(직업 + WIS × 0.05 + 장비) × (1 + Σ mana_regen_pct)",
            cooldown="기본 × 0.9(combat_spec) × (1 − 재사용 감소) × max(0.5, 1 + Σ cooldown_pct)",
            evasion="clamp(0.001 DEX + 장비 + Σ evasion, 0, 0.40)",
            knockback_resist="clamp(0.003 STR + (판금 4부위 0.60), 0, 0.85), 보스 밀쳐내기에는 안 듬",
            cc_resist="판금 4부위: 기절·속박·빙결 × (1 − 0.40), 보스가 건 것 제외, 정신 감소와 따로 곱함",
            full_look="body 같은 겉모습 수 + any ≥ 4",
            mana_shield="흡수 = 최종 피해 × 0.20 (MP − 흡수/2 ≥ 0.2 × 최대 MP 일 때, 아니면 남은 만큼), MP 비용 = 흡수 / 2",
            tumble="웅크리기 누름 두 번 ≤ 0.30초, 땅·방향 키·막힘 없음·조합 스킬 0.4초 뒤 → 3.5칸, 0.4초 회피(canEvade 인 피해), 쿨 8초",
            requirement_total="T(L) = ceil(1.1 × R(L)), R(L) = ceil(2.5(L−1)) (≤2 면 0)",
            requirement_split="앞 = ceil(0.6 T), 뒤 = T − 앞 (세 개면 50/30/20: ceil·round·나머지)",
        ),
        look_sources=dict(set_look="sets.<id>.look", plain_sets=["novice", "wayfarer"], item_look=K.ITEM_LOOK,
                          shield="heavy", wildcard="nightmare_crown"),
        requirements=dict(
            set_pairs={k: dict(pair=v[0], identity=v[1], why=v[2]) for k, v in K.SET_REQ.items()},
            item_pairs={k: dict(pair=v[0], identity=v[1], why=v[2]) for k, v in K.ITEM_REQ.items()},
            stats_rename=K.STATS_RENAME,
            total_mult=K.REQ_TOTAL_MULT,
        ),
        armor_items=rows,
        checks=dict(band_fit_existing=REQ, band_fit_with_gear_spec=REQN, tax_limit=RQ.TAX_LIMIT,
                    weapon_pair_assumption=RQ.WEAPON_PAIR, useful_stats={k: sorted(v) for k, v in RQ.USEFUL.items()}),
        tooltip=dict(lines={lk: [dict(text=strip(l), px=wd) for l, wd in ls] for lk, ls in tl.items()},
                     colors=TT.COLORS, max_px=TT.MAX_PX, examples=tooltip_examples(),
                     top_line="{희귀도} {겉모습} {부위} (층 없음, 평상복은 겉모습 없음)"),
        model=dict(tables=RES["model"], dominance=RES["dominance"], mixed=RES["mixed"]),
        sim=dict(raw=SIM, strict_losses=sim_summary(), arcanist_f10_decomposition=DECOMP,
                 method=dict(move_window="w' = 0.3 + (w − 0.3)(1 + Δ)", kite="e_kite × (1 − 1.5Δ)",
                             tumble_save={"novice": 0.3, "average": 0.5, "skilled": 0.7}, runs=40, room_fights=60)),
        code=[dict(file=f, change=t) for f, t in CODE],
        movement=MOVE_NOTES,
        tests=[dict(test=f, checks=t) for f, t in TESTS],
        migration=MIGRATION,
        for_other_designers=OTHERS,
        risks=RISKS,
    )
    return out


if __name__ == "__main__":
    with open(os.path.join(D2, "look_spec.md"), "w", encoding="utf-8") as f:
        f.write(md())
    with open(os.path.join(D2, "look_spec.json"), "w", encoding="utf-8") as f:
        json.dump(js(), f, ensure_ascii=False, indent=1)
    print("ok")
