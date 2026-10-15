#!/usr/bin/env python3
"""TASK P — 상태이상(CC) 목록: 직업 스킬 24 · 무기 스킬 204 · 고유 효과 → 지금 시간 vs PvP 시간 (첫 번째 · 두 번째 · 세 번째)."""
import json

import pv_core as V
import pv_final as F

P = F.PVP_NEW
HARD = ("stun", "frozen", "root", "silence", "blind")
TIMED = HARD + ("slow", "cooldown_slow")
NAME = {"stun": "기절", "frozen": "빙결", "root": "속박", "silence": "침묵", "blind": "실명", "slow": "둔화",
        "cooldown_slow": "재사용 둔화", "frost": "서리 중첩", "knockback": "밀쳐내기", "pull": "끌어오기",
        "launch": "띄우기", "taunt": "도발", "mark": "표식(받는 피해+)", "vulnerable": "취약(받는 피해+)",
        "weaken": "약화(주는 피해−)", "venom": "독 중첩", "burn": "화상"}
CAT = {"stun": "control", "frozen": "control", "root": "root", "silence": "silence", "blind": "blind"}


def pvp_times(cid, base, heavy=False):
    """첫·둘째·셋째 적용 시간 (같은 분류를 8초 안에 다시 맞을 때). 정신(WIS) 감소는 빼고 본다."""
    d = base
    if heavy and cid in ("stun", "root", "frozen"):
        d *= 0.6
    d *= P["cc_mult"].get(cid, 1.0)
    cap = P["cc_cap"].get(cid)
    if cap:
        d = min(d, cap)
    out = []
    cat = CAT.get(cid)
    for i in range(3):
        f = P["dr"]["steps"][min(i, 3)] if cat in P["dr"]["cats"] else 1.0
        x = d * f
        out.append(round(x, 2) if x >= 0.2 else 0.0)
    return out


def rows():
    out = []
    # 직업 스킬
    for cls in V.CLASS_ORDER:
        for s in V.CLASSES[cls]["skills"]:
            p = s.get("params", {})
            sid = s["id"]
            items = []
            if sid == "shield_bash":
                items.append(("stun", p["stun"], None, "부채꼴 3.5칸"))
            elif sid == "frost_nova":
                items.append(("root", p["root"], None, "주위 5칸 (보스는 둔화)"))
            elif sid == "evasive_trap":
                items.append(("root", p["trap_root"], None, "덫을 밟으면"))
            elif sid == "arrow_storm":
                items.append(("slow", 0.8, p["slow"], "화살비 안에 있는 동안 (0.5초마다 다시 걸림, 4초)"))
            elif sid == "bulwark_citadel":
                items.append(("slow", 0.6, p["enemy_slow"], "방벽 안에 있는 동안 (6초)"))
            elif sid == "ground_cleaver":
                items.append(("launch", None, p["launch"], "띄우기 — 시간 없음"))
            elif sid == "ruinous_leap":
                items.append(("vulnerable", p["vuln_duration"], p["vulnerability"], "받는 피해 +15%"))
            elif sid == "hunters_mark":
                items.append(("mark", p["duration"], p["damage_taken"], "받는 피해 +20%, 은신 드러냄"))
            elif sid == "venom_blades":
                items.append(("weaken", 6.0, p["weaken_at_max"], "독 5중첩일 때"))
            elif sid == "taunting_roar":
                items.append(("taunt", p["duration"], None, "몹만 — 플레이어에게는 효과 없음"))
            for (cid, sec, pot, note) in items:
                out.append(dict(src="class", owner=cls, owner_name=V.CLASS_NAME[cls], skill=sid, name=s["name"], effect=cid,
                                seconds=sec, potency=pot, repeats=1, note=note))
    # 무기 스킬
    for wid in V.all_weapons():
        w = V.weapon(wid)
        for s in w["skills"]:
            for c in s["cc"]:
                cid = c["id"]
                if cid == "frost":
                    out.append(dict(src="weapon", owner=wid, owner_name=w["name"], skill=str(s["input"]), name=s["name"],
                                    effect="frost", seconds=c["seconds"], potency=c.get("stacks", 1),
                                    repeats=c.get("repeats", 1), note="서리 중첩 — 5중첩이면 빙결"))
                    continue
                out.append(dict(src="weapon", owner=wid, owner_name=w["name"], skill=str(s["input"]), name=s["name"], effect=cid,
                                seconds=c["seconds"] if cid not in ("knockback", "pull", "launch") else None,
                                potency=c.get("potency") if cid not in ("knockback", "pull", "launch") else c["seconds"],
                                repeats=c.get("repeats", 1), note=c.get("part")))
            for (dt, dur, pot) in s["dot"]:
                if dt == "wither":
                    out.append(dict(src="weapon", owner=wid, owner_name=w["name"], skill=str(s["input"]), name=s["name"],
                                    effect="weaken", seconds=dur, potency=0.12, repeats=1, note="시듦(출혈+약화)"))
    # 고유 효과 (기절·서리)
    for wid in V.all_weapons():
        w = V.weapon(wid)
        u = w.get("unique") or {}
        if u.get("id") == "shield_bash":
            out.append(dict(src="unique", owner=wid, owner_name=w["name"], skill="shield_bash", name=u.get("name", "방패 강타"),
                            effect="stun", seconds=u.get("stun", 0.8), potency=None, repeats=1,
                            note=f"{int(u.get('n', 5))}번째 공격마다, 같은 적 6초 면역(몹)"))
        if u.get("id") == "imbue" and u.get("element") == "frost":
            out.append(dict(src="unique", owner=wid, owner_name=w["name"], skill="imbue", name=u.get("name", "원소 부여"),
                            effect="frost", seconds=6.0, potency=1, repeats=1,
                            note=f"{int(u.get('chance', 0.25)*100)}% 확률 서리 1중첩, 5중첩이면 빙결 1초"))
    # 상태 규칙 자체
    out.append(dict(src="status", owner="frost", owner_name="서리 5중첩", skill="frost", name="빙결", effect="frozen",
                    seconds=4.0, potency=None, repeats=1, note="무기 스킬·몹이 건 서리 5중첩 → 빙결 (고유 효과 imbue 는 1초)"))
    for r in out:
        cid = r["effect"]
        if cid in TIMED and r["seconds"]:
            r["pvp"] = pvp_times(cid, r["seconds"])
            r["pvp_heavy"] = pvp_times(cid, r["seconds"], heavy=True)
        elif cid == "frost":
            fz = 1.0 if r["src"] == "unique" else 4.0
            r["frozen_today"] = fz
            r["pvp"] = pvp_times("frozen", fz)
            r["pvp_heavy"] = pvp_times("frozen", fz, heavy=True)
        else:
            r["pvp"] = None
    return out


if __name__ == "__main__":
    R = rows()
    import collections
    c = collections.Counter((r["src"], r["effect"]) for r in R)
    print(len(R), dict(c))
    for r in R:
        if r["effect"] in HARD + ("frost",):
            print(r["src"], r["owner_name"], r["name"], r["effect"], r["seconds"], r.get("repeats"), "→", r["pvp"], "판금", r["pvp_heavy"])
