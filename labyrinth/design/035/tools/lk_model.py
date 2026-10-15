#!/usr/bin/env python3
"""
TASK B — 겉모습별 기대값 모델 (combat_spec 의 ce_model.new_player 를 그대로 따르고, 그 위에 겉모습만 얹는다).

  build(cls, L, look, ...)  → dps · ehp · 이동 속도 · 회피 · 치명 · 공속 · 분배
     look = "native"(combat_spec 와 같은 방어구: 직업 대표 스탯 줄이 있는 것) | "heavy" | "light" | "cloth" | {slot: look}
     looks=False      겉모습 효과 끔 (비교 기준)
     new_req=False    0.3.4 방어구 요구치 (판금 VIT · 가죽 DEX · 천 INT|WIS) — combat_spec 기준
     sets=False       세트 효과 빼기 (ce_model 과 똑같이 맞출 때)

combat_spec 값(P_FINAL · REQ_SPLIT_FINAL · 직업 skill_scale · 매의 눈 · 급소 · 은총 · 스킬 위력 (1+0.5·AS))은 ce_sim 에서 읽는다.
"""
import math

import ce_core as C
import ce_model as M
import ce_sim as X
import lk_core as K

P = X.P_FINAL
C.USE_GEAR_REQUIRES = False
C.REQ_SPLIT = X.REQ_SPLIT_FINAL

CLASSES = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
NATIVE = {"guardian": "heavy", "berserker": "heavy", "hunter": "light", "shadow": "light", "arcanist": "cloth",
          "priest": "cloth"}
# 직업이 원하는 능력치 (요구 짝 고를 때 · '알맞은' 판정)
WANT = {"guardian": ("VIT", "STR", "DEX"), "berserker": ("STR", "VIT", "DEX"), "hunter": ("DEX", "STR", "VIT", "LUK"),
        "arcanist": ("INT", "VIT", "WIS"), "priest": ("WIS", "INT", "VIT"), "shadow": ("DEX", "STR", "VIT", "LUK")}
TARGET = M.TARGET_NEW


def cap_of(L):
    return 3 if M.floor_of_level(L) >= 6 else 2


def item_ok(v, L, cap, include_new):
    if v.get("proposed") and not include_new:
        return False
    return v.get("level_req", 1) <= L and K.RANK[v.get("rarity", "common")] <= cap and "stats" in v


def _cands(cls, L, look, slot, include_new):
    cap = cap_of(L)
    out = []
    for iid, v in K.armor_items(include_new).items():
        if v.get("armor_slot") != slot or not item_ok(v, L, cap, include_new):
            continue
        if slot != "offhand" and K.look_of(iid) != look:
            continue
        out.append(iid)
    out.sort(key=lambda i: (K.ALL_ITEMS[i]["level_req"], K.RANK[K.ALL_ITEMS[i]["rarity"]]), reverse=True)
    return out


def pick_armor(cls, L, look, include_new=False, shield=None, metric=None, **kw):
    """slot → item id. look: 겉모습 이름 또는 {slot: look}.
    겉모습 하나면: 그 겉모습 세트마다 4부위(+ 같은 겉모습 단품 투구) 를 맞춰 보고 metric(기본 = √(DPS·EHP)) 가 가장 큰 것.
    방패(수호기사): 레벨 높은 방패 3개 중 metric 이 가장 큰 것. {slot: look} 이면 칸마다 가장 높은 것."""
    if isinstance(look, dict):
        out = {}
        for slot in K.SLOTS:
            c = _cands(cls, L, look[slot], slot, include_new)
            if c:
                out[slot] = c[0]
        sh = _cands(cls, L, None, "offhand", include_new) if (shield or (shield is None and cls == "guardian")) else []
        if sh:
            out["offhand"] = sh[0]
        return out
    metric = metric or (lambda b: (b["dps"] * b["ehp"]) ** 0.5)
    cap = cap_of(L)
    sets = {}
    for slot in K.SLOTS:
        for iid in _cands(cls, L, look, slot, include_new):
            sid = K.ALL_ITEMS[iid].get("set_bonus") or ("_single_" + slot)
            sets.setdefault(sid, {})[slot] = iid
    options = []
    best_single = {slot: next((i for i in _cands(cls, L, look, slot, include_new)), None) for slot in K.SLOTS}
    for sid, pieces in sets.items():
        if sid.startswith("_single_"):
            continue
        arm = {slot: pieces.get(slot) or best_single[slot] for slot in K.SLOTS}
        arm = {k: v for k, v in arm.items() if v}
        options.append(arm)
        # 같은 겉모습 단품 투구가 더 높으면 그것도
        h = best_single["head"]
        if h and h != arm.get("head") and K.ALL_ITEMS[h].get("set_bonus") is None:
            alt = dict(arm, head=h)
            options.append(alt)
    # 그 겉모습이 아직 없는 칸(1층 근처)은 평상복 → 다른 겉모습 순으로 가장 높은 것
    def fill(arm):
        for slot in K.SLOTS:
            if slot in arm:
                continue
            for lk2 in ("plain", "any", "heavy", "light", "cloth"):
                if lk2 == look:
                    continue
                c = _cands(cls, L, lk2, slot, include_new)
                if c:
                    arm[slot] = c[0]
                    break
        return arm

    if not options:
        options = [{sl: i for sl, i in best_single.items() if i}]
    options = [fill(dict(a)) for a in options]
    # 레벨이 가장 높은 세트 3개만 (오래된 세트는 볼 필요 없음)
    options.sort(key=lambda a: max(K.ALL_ITEMS[i]["level_req"] for i in a.values()), reverse=True)
    options = options[:4]
    use_shield = shield or (shield is None and cls == "guardian")
    best = None
    for arm in options:
        b = build(cls, L, dict(_fixed=arm), _shield=False, **kw)
        m = metric(b)
        if best is None or m > best[0]:
            best = (m, arm)
    arm = dict(best[1])
    if use_shield:
        sb = None
        for sh in _cands(cls, L, None, "offhand", include_new)[:3]:
            b = build(cls, L, dict(_fixed=dict(arm, offhand=sh)), _shield=False, **kw)
            m = metric(b)
            if sb is None or m > sb[0]:
                sb = (m, sh)
        if sb:
            arm["offhand"] = sb[1]
    return arm


def native_armor(cls, L):
    """combat_spec(ce_model.gear_for) 와 같은 방어구."""
    _, items = M.gear_for(cls, L)
    out = {}
    for i in items:
        v = C.ITEMS[i]
        if v.get("type") == "armor":
            out[v.get("armor_slot")] = i
    return out


def accessories(cls, L):
    _, items = M.gear_for(cls, L)
    return [i for i in items if C.ITEMS[i].get("type") == "accessory"]


def armor_req(cls, iid, new_req):
    if new_req:
        return K.new_requires(iid)
    return M.item_requirements(cls, iid, "old")


def plan(cls, L, wid, armor, new_req, target=None):
    n = M.points(L)
    base = C.CLASSES[cls]["base_stats"]
    need = {}
    for st, v in M.item_requirements(cls, wid, "new", P).items():
        need[st] = max(need.get(st, 0), v)
    for iid in armor.values():
        for st, v in armor_req(cls, iid, new_req).items():
            need[st] = max(need.get(st, 0), v)
    a = {k: max(0, need.get(k, 0) - base.get(k, 0)) for k in M.STATS}
    left = n - sum(a.values())
    tgt = target or TARGET[cls]
    tot = sum(tgt.values())
    want = {k: n * tgt.get(k, 0) / tot for k in M.STATS}
    while left > 0:
        k = max(M.STATS, key=lambda s: (want[s] - a[s]) if want[s] > 0 else -1e9)
        a[k] += 1
        left -= 1
    return a, left, need


def item_stats(iid, new_req):
    if new_req:
        st = K.renamed_stats(iid)
    else:
        st = K.ALL_ITEMS[iid]["stats"]
    return {k: K.mid(v) for k, v in st.items()}


def build(cls, L, look="native", looks=True, new_req=True, sets=True, include_new=False, target=None,
          wid=None, shield=None, mana_share=0.5, P_over=None, _shield=None, accs=None):
    Pp = dict(P, **(P_over or {}))
    wid0, _ = M.gear_for(cls, L)
    wid = wid or wid0
    if look == "native":
        armor = native_armor(cls, L)
    elif isinstance(look, dict) and "_fixed" in look:
        armor = look["_fixed"]
    else:
        armor = pick_armor(cls, L, look, include_new, shield, looks=looks, new_req=new_req, sets=sets,
                           target=target, wid=wid, mana_share=mana_share, P_over=P_over)
    accs = accs if accs is not None else accessories(cls, L)
    w = C.WEAPONS[wid]
    ph = C.new_per_hit(wid, Pp)
    wst = {k: C.mid(v) for k, v in w["stats"].items()}
    wst["damage"] = C.mid(ph)
    bonus = dict(wst)

    def add(st):
        for k, v in st.items():
            bonus[k] = bonus.get(k, 0) + v

    for iid in armor.values():
        add(item_stats(iid, new_req))
    for iid in accs:
        add({k: K.mid(v) for k, v in C.ITEMS[iid]["stats"].items()})
    # 세트 효과
    set_count = {}
    for iid in list(armor.values()) + accs:
        sid = K.ALL_ITEMS[iid].get("set_bonus")
        if sid:
            set_count[sid] = set_count.get(sid, 0) + 1
    if sets:
        for sid, c in set_count.items():
            for need, b in (K.ALL_SETS[sid].get("bonuses") or {}).items():
                if c >= int(need):
                    add(b)
    # 겉모습
    counts = {}
    for slot, iid in armor.items():
        lk = K.look_of(iid)
        counts[lk] = counts.get(lk, 0) + 1
    body = {}
    for slot, iid in armor.items():
        if slot == "offhand":
            continue
        lk = K.look_of(iid)
        body[lk] = body.get(lk, 0) + 1
    anyc = body.pop("any", 0)
    full = None
    if body:
        top = max(body, key=lambda k: body[k])
        if top in K.LOOKS and body[top] + anyc >= K.FULL_PIECES:
            full = top
    imp = K.look_totals(counts) if looks else {}
    for k, v in imp.items():
        if k in K.MULT_KEYS:
            continue
        bonus[k] = bonus.get(k, 0) + v
    alloc, _, need = plan(cls, L, wid, armor, new_req, target)
    d = M.derive(cls, L, alloc, bonus, Pp, new=True)
    d["defense"] *= 1 + imp.get("defense_pct", 0)
    d["max_hp"] *= 1 + imp.get("hp_pct", 0)
    d["mana_regen"] *= 1 + imp.get("mana_regen_pct", 0)
    d["move_speed"] = max(-0.6, min(0.30, bonus.get("move_speed", 0)))
    if cls == "shadow":
        d["crit_dmg"] += Pp.get("shadow_crit_dmg", 0.0)
    if cls == "priest":
        d["magic_bonus"] = Pp.get("priest_magic", 0.0)
    s = d["s"]
    kind = M.weapon_kind(wid)
    k_of = {"physical": Pp["k_phys"] * s["STR"], "magic": Pp["k_mag"] * s["INT"]}
    ap = wst["damage"] * (1 + k_of[kind])
    style = C.style_of(C.weapon_shape(wid))
    iv = C.interval_of(wid)
    cf = M.crit_factor(d)
    spd = 1 + d["atk_speed"]
    if style == "ranged":
        period = max(C.MIN_INTERVAL, (iv - C.BOW_NOCK) / spd + C.BOW_NOCK)
        per_s = (Pp["keen_eye"] if cls == "hunter" else 1.0) / period
    else:
        period = max(C.MIN_INTERVAL, iv / spd)
        per_s = 1.0 / period
    mb = 1 + (d.get("magic_bonus", 0.0) if kind == "magic" else 0.0)
    basic = ap * per_s * cf * M.buff_mult(cls, L) * mb
    sp = C.skill_power(wst["damage"], iv, style, M.CASTER_SP_MULT if style == "caster" else 1.0) * \
        (1 + Pp.get("sp_speed", 0.0) * max(0.0, d["atk_speed"]))
    skind = M.CLASS_SKILL_KIND[cls]
    unit = sp * M.SKILL_SCALE[cls] * (1 + k_of[skind]) * cf * (1 + d["skill_dmg"]) * \
        (1 + (d.get("magic_bonus", 0.0) if skind == "magic" else 0.0))
    inc = d["mana_regen"] + (3 * per_s if cls == "berserker" else 0) + \
        (3 * per_s / Pp["keen_eye"] if cls == "hunter" and style == "ranged" else 0)
    d["cd_mult"] = 1 + imp.get("cooldown_pct", 0.0)
    sk = M.skill_dps(cls, L, d, unit, inc, 0.9 * d["cd_mult"])
    e = M.ehp(d)
    e_ms = e
    if full == "cloth" and looks:
        f = K.LOOKS["cloth"]["full"]
        budget = d["max_mp"] * (1 - f["off_below"]) * mana_share
        e_ms = e + min(f["absorb"] / (1 - f["absorb"]) * e, f["damage_per_mp"] * budget)
    skill_ap = sp * M.SKILL_SCALE[cls] * (1 + k_of[skind])
    return dict(cls=cls, L=L, look=look, weapon=wid, armor=armor, accs=accs, full=full, counts=counts, alloc=alloc,
                need=need, ap=ap, skill_ap=skill_ap, style=style, interval=iv, imp=imp, bonus=bonus,
                stats=s, dps=basic + sk, basic=basic, skill=sk, ehp=e, ehp_ms=e_ms, hp=d["max_hp"], mp=d["max_mp"],
                defense=d["defense"], dr=d["dr"], evasion=d["evasion"], crit=d["crit"], speed=d["atk_speed"],
                move=d["move_speed"], cdr=d["cdr"], skill_dmg=d["skill_dmg"], mana_regen=d["mana_regen"],
                heal_power=d["heal_power"], d=d)


if __name__ == "__main__":
    # 1) ce_model 재현 (겉모습 끔 · 0.3.4 방어구 요구 · 세트 효과 끔)
    for L in (10, 25, 45):
        for cls in CLASSES:
            o = M.old_player(cls, L)
            ref = M.new_player(cls, L, P, "sensible", o["weapon"])
            mine = build(cls, L, "native", looks=False, new_req=False, sets=False, wid=o["weapon"])
            print(f"L{L} {cls:9} ref dps {ref['dps']:7.1f} ehp {ref['ehp']:7.0f} | mine dps {mine['dps']:7.1f} ehp {mine['ehp']:7.0f}")
