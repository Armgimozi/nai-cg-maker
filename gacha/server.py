"""게임 API 블루프린트.

모든 판정(뽑기 결과·전투 승패·재화 증감·결제)은 서버에서만 이뤄진다.
클라이언트는 "무엇을 하고 싶은지"만 보내고 결과를 받는다.

  GET  /game                     게임 클라이언트
  GET  /game/<path>              게임 정적 파일
  POST /api/game/session         플레이어 생성/복구
  GET  /api/game/catalog         캐릭터·배너·확률공시·스테이지·상점 (정적 데이터)
  GET  /api/game/state           내 상태
  POST /api/game/pull            뽑기 (1회 / 10연)
  POST /api/game/battle          스테이지 전투
  POST /api/game/team            편성 변경
  POST /api/game/levelup         캐릭터 레벨업
  POST /api/game/shop/buy        상점 구매 (모의 결제)
  POST /api/game/shop/stamina    스태미나 충전
  POST /api/game/claim/mission   일일 미션 보상
  POST /api/game/claim/login     출석 보상
  POST /api/game/profile         이름 변경
  POST /api/game/reset           계정 초기화
"""

from __future__ import annotations

import random
import secrets
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from . import art, battle, econ, rng, state
from .content import (BY_ID, CHARACTERS, ELEMENTS, LEVEL_CAP, MAX_ASCEND,
                      RARITY_NAMES)

GAME_DIR = Path(__file__).resolve().parent.parent / "web" / "game"
game_bp = Blueprint("game", __name__)


# ─────────────────────────────────────────────────────── 헬퍼
def _player() -> dict | None:
    pid = request.headers.get("X-Player") or ""
    return state.load(pid) if pid else None


def _need_player():
    st = _player()
    if st is None:
        return None, (jsonify({"error": "플레이어를 찾을 수 없습니다. 새로고침 해주세요.",
                               "code": "no_player"}), 401)
    return st, None


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _monthly_tick(st: dict) -> list[dict]:
    """달빛 통행증이 살아있으면 하루 한 번 별가루를 지급."""
    out = []
    sh = st["shop"]
    today = state.today_str()
    if sh.get("monthly_until", 0) > time.time() and sh.get("monthly_claimed") != today:
        sh["monthly_claimed"] = today
        state.gain(st, "stardust", econ.MONTHLY_PASS["daily_stardust"])
        out.append({"kind": "stardust", "amount": econ.MONTHLY_PASS["daily_stardust"],
                    "reason": "달빛 통행증"})
    return out


def _login_view(st: dict) -> dict:
    lg = st["login"]
    today = state.today_str()
    streak = lg["streak"]
    if lg["date"] != today:
        yesterday = (datetime.fromisoformat(today) - timedelta(days=1)).date().isoformat()
        streak = streak + 1 if lg["date"] == yesterday else 1
    day = ((max(1, streak) - 1) % 7) + 1
    return {"claimed": lg["date"] == today, "streak": streak, "day": day,
            "rewards": econ.LOGIN_REWARDS}


def view(st: dict) -> dict:
    state.refresh_stamina(st)
    state.roll_daily(st)
    bonus = _monthly_tick(st)
    roster = {}
    for cid, e in st["roster"].items():
        roster[cid] = {**e, "stats": state.unit_stats(cid, e),
                       "power": state.power(cid, e),
                       "cap": LEVEL_CAP[BY_ID[cid]["rarity"]],
                       "cost": state.levelup_cost(BY_ID[cid]["rarity"], e["level"])}
    team_power = sum(state.power(c, st["roster"][c])
                     for c in st["team"] if c in st["roster"])
    return {
        "pid": st["pid"],
        "name": st["name"],
        "currency": st["currency"],
        "stamina": {"value": st["stamina"]["value"], "max": econ.STAMINA_MAX,
                    "next": state.stamina_next_sec(st)},
        "roster": roster,
        "team": st["team"],
        "team_power": team_power,
        "pity": st["pity"],
        "pulls": st["pulls"],
        "history": st["history"][-60:],
        "stages": st["stages"],
        "shop": {"purchased": st["shop"]["purchased"],
                 "spent_krw": st["shop"]["spent_krw"],
                 "monthly_until": st["shop"]["monthly_until"]},
        "missions": state.missions_view(st),
        "login": _login_view(st),
        "bonus": bonus,
    }


# ─────────────────────────────────────────────────────── 정적
@game_bp.get("/game")
@game_bp.get("/game/")
def game_index():
    return send_from_directory(GAME_DIR, "index.html")


@game_bp.get("/game/<path:fname>")
def game_static(fname: str):
    return send_from_directory(GAME_DIR, fname)


# ─────────────────────────────────────────────────────── 세션 / 카탈로그
@game_bp.post("/api/game/session")
def session():
    pid = (_body().get("pid") or "").strip()
    st = state.load(pid) if pid else None
    if st is None:
        st = state.create_player()
    state.save(st)
    return jsonify(view(st))


@game_bp.get("/api/game/catalog")
def catalog():
    chars = []
    for c in CHARACTERS:
        chars.append({
            "id": c["id"], "name": c["name"], "title": c["title"],
            "rarity": c["rarity"], "rarity_name": RARITY_NAMES[c["rarity"]],
            "element": c["element"], "role": c["role"], "base": c["base"],
            "skill": c["skill"], "palette": c["palette"], "quote": c["quote"],
            "art": art.art_url(c["id"]),
        })
    banners = []
    for b in econ.BANNERS:
        banners.append({**b, "disclosure": econ.disclosure(b),
                        "pity_key": rng.pity_key(b),
                        "art": art.art_url(b["art_hint"])})
    return jsonify({
        "characters": chars,
        "elements": ELEMENTS,
        "banners": banners,
        "stages": econ.stage_list(),
        "shop": {"packages": econ.SHOP_PACKAGES, "monthly": econ.MONTHLY_PASS,
                 "first_purchase_mult": econ.FIRST_PURCHASE_MULT,
                 "stamina_cost": econ.STAMINA_REFILL_COST,
                 "stamina_amount": econ.STAMINA_REFILL_AMOUNT},
        "costs": {"pull": econ.PULL_COST, "pull10": econ.PULL_COST_10,
                  "essence_rate": econ.ESSENCE_TO_STARDUST},
        "limits": {"max_ascend": MAX_ASCEND, "stamina_max": econ.STAMINA_MAX,
                   "regen_sec": econ.STAMINA_REGEN_SEC},
    })


@game_bp.get("/api/game/state")
def get_state():
    st, err = _need_player()
    if err:
        return err
    state.save(st)
    return jsonify(view(st))


# ─────────────────────────────────────────────────────── 뽑기
@game_bp.post("/api/game/pull")
def pull():
    st, err = _need_player()
    if err:
        return err
    b = _body()
    banner = econ.BANNER_BY_ID.get(b.get("banner") or "")
    if banner is None:
        return jsonify({"error": "없는 배너입니다."}), 400
    count = 10 if int(b.get("count") or 1) >= 10 else 1
    use_ticket = bool(b.get("ticket"))

    cost = econ.PULL_COST_10 if count == 10 else econ.PULL_COST
    if use_ticket:
        if st["currency"].get("ticket", 0) < count:
            return jsonify({"error": "소환권이 부족합니다."}), 400
        st["currency"]["ticket"] -= count
        paid = {"ticket": count}
    else:
        if st["currency"].get("stardust", 0) < cost:
            return jsonify({"error": "별가루가 부족합니다.",
                            "code": "no_stardust",
                            "need": cost - st["currency"].get("stardust", 0)}), 400
        st["currency"]["stardust"] -= cost
        paid = {"stardust": cost}

    key = rng.pity_key(banner)
    pity = st["pity"].setdefault(key, rng.new_pity())
    r = random.Random(secrets.randbits(64))
    raw = rng.draw(banner, pity, count, r)

    results = []
    for item in raw:
        got = state.add_character(st, item["char"])
        c = BY_ID[item["char"]]
        results.append({**item, **got, "name": c["name"], "title": c["title"],
                        "element": c["element"], "palette": c["palette"],
                        "art": art.art_url(c["id"])})
        st["history"].append({"ts": time.time(), "banner": banner["id"],
                              "char": item["char"], "rarity": item["rarity"],
                              "pickup": item["pickup"]})
    st["history"] = st["history"][-300:]
    st["pulls"]["total"] += count
    st["pulls"]["banner"][banner["id"]] = st["pulls"]["banner"].get(banner["id"], 0) + count
    state.bump_mission(st, "pull1", count)
    state.save(st)
    return jsonify({"results": results, "paid": paid, "state": view(st)})


# ─────────────────────────────────────────────────────── 전투
@game_bp.post("/api/game/battle")
def do_battle():
    st, err = _need_player()
    if err:
        return err
    key = (_body().get("stage") or "").strip()
    stage = econ.STAGES.get(key)
    if stage is None:
        return jsonify({"error": "없는 스테이지입니다."}), 400

    # 앞 스테이지를 깨야 다음이 열린다(1-1 은 항상 열림).
    prev = _prev_stage_key(key)
    if prev and not st["stages"].get(prev, {}).get("cleared"):
        return jsonify({"error": "이전 스테이지를 먼저 클리어하세요."}), 400

    team = [c for c in st["team"] if c in st["roster"]]
    if not team:
        return jsonify({"error": "편성된 캐릭터가 없습니다."}), 400

    state.refresh_stamina(st)
    if st["stamina"]["value"] < stage["stamina"]:
        return jsonify({"error": "스태미나가 부족합니다.", "code": "no_stamina"}), 400
    st["stamina"]["value"] -= stage["stamina"]
    if st["stamina"]["value"] < econ.STAMINA_MAX:
        st["stamina"]["ts"] = min(st["stamina"]["ts"], time.time())

    seed = secrets.randbits(32)
    allies = battle.build_team(st)
    enemies = battle.build_enemies(stage, seed)
    result = battle.simulate(allies, enemies, seed)

    rewards = []
    if result["win"]:
        rec = st["stages"].setdefault(key, {"cleared": False, "clears": 0})
        first = not rec["cleared"]
        rec["cleared"] = True
        rec["clears"] = rec.get("clears", 0) + 1
        rw = stage["reward"]
        state.gain(st, "gold", rw["gold"])
        rewards.append({"kind": "gold", "amount": rw["gold"]})
        if first:
            state.gain(st, "stardust", rw["stardust_first"])
            rewards.append({"kind": "stardust", "amount": rw["stardust_first"],
                            "reason": "최초 클리어"})
        state.bump_mission(st, "battle3", 1)
    state.save(st)
    return jsonify({"battle": result, "rewards": rewards, "stage": stage,
                    "state": view(st)})


def _prev_stage_key(key: str) -> str | None:
    ch, s = (int(x) for x in key.split("-"))
    if s > 1:
        return f"{ch}-{s - 1}"
    if ch > 1:
        prev_ch = next(c for c in econ.CHAPTERS if c["id"] == ch - 1)
        return f"{ch - 1}-{prev_ch['stages']}"
    return None


# ─────────────────────────────────────────────────────── 편성 / 육성
@game_bp.post("/api/game/team")
def set_team():
    st, err = _need_player()
    if err:
        return err
    want = _body().get("team") or []
    team, seen = [], set()
    for cid in want:
        if cid in st["roster"] and cid not in seen and len(team) < 4:
            team.append(cid)
            seen.add(cid)
    st["team"] = team
    state.save(st)
    return jsonify(view(st))


@game_bp.post("/api/game/levelup")
def levelup():
    st, err = _need_player()
    if err:
        return err
    b = _body()
    cid = b.get("char") or ""
    times = max(1, min(int(b.get("times") or 1), 50))
    entry = st["roster"].get(cid)
    if entry is None:
        return jsonify({"error": "보유하지 않은 캐릭터입니다."}), 400
    cap = LEVEL_CAP[BY_ID[cid]["rarity"]]
    spent = done = 0
    for _ in range(times):
        if entry["level"] >= cap:
            break
        cost = state.levelup_cost(BY_ID[cid]["rarity"], entry["level"])
        if st["currency"]["gold"] < cost:
            break
        st["currency"]["gold"] -= cost
        entry["level"] += 1
        spent += cost
        done += 1
    if done == 0:
        reason = "최대 레벨입니다." if entry["level"] >= cap else "골드가 부족합니다."
        return jsonify({"error": reason}), 400
    state.bump_mission(st, "levelup", 1)
    state.save(st)
    return jsonify({"levels": done, "gold_spent": spent, "state": view(st)})


# ─────────────────────────────────────────────────────── 상점 (모의 결제)
@game_bp.post("/api/game/shop/buy")
def shop_buy():
    st, err = _need_player()
    if err:
        return err
    pid = _body().get("package") or ""

    if pid == econ.MONTHLY_PASS["id"]:
        mp = econ.MONTHLY_PASS
        now = time.time()
        base = max(st["shop"].get("monthly_until", 0), now)
        st["shop"]["monthly_until"] = base + mp["days"] * 86400
        state.gain(st, "essence", mp["instant_essence"])
        st["shop"]["spent_krw"] += mp["price_krw"]
        st["shop"]["purchased"][pid] = st["shop"]["purchased"].get(pid, 0) + 1
        state.save(st)
        return jsonify({"granted": {"essence": mp["instant_essence"]},
                        "first": False, "state": view(st)})

    pkg = next((p for p in econ.SHOP_PACKAGES if p["id"] == pid), None)
    if pkg is None:
        return jsonify({"error": "없는 상품입니다."}), 400
    first = st["shop"]["purchased"].get(pid, 0) == 0
    amount = (pkg["essence"] + pkg["bonus"])
    if first:
        amount *= econ.FIRST_PURCHASE_MULT
    state.gain(st, "essence", amount)
    st["shop"]["purchased"][pid] = st["shop"]["purchased"].get(pid, 0) + 1
    st["shop"]["spent_krw"] += pkg["price_krw"]
    state.save(st)
    return jsonify({"granted": {"essence": amount}, "first": first,
                    "state": view(st)})


@game_bp.post("/api/game/shop/exchange")
def shop_exchange():
    """별정수 → 별가루 교환. 뽑기는 별가루만 소모하므로 유료 재화는 이 단계를 거친다."""
    st, err = _need_player()
    if err:
        return err
    amount = max(1, int(_body().get("amount") or 0))
    if st["currency"]["essence"] < amount:
        return jsonify({"error": "별정수가 부족합니다."}), 400
    st["currency"]["essence"] -= amount
    state.gain(st, "stardust", amount * econ.ESSENCE_TO_STARDUST)
    state.save(st)
    return jsonify(view(st))


@game_bp.post("/api/game/shop/stamina")
def shop_stamina():
    st, err = _need_player()
    if err:
        return err
    if st["currency"]["essence"] < econ.STAMINA_REFILL_COST:
        return jsonify({"error": "별정수가 부족합니다."}), 400
    state.refresh_stamina(st)
    st["currency"]["essence"] -= econ.STAMINA_REFILL_COST
    st["stamina"]["value"] += econ.STAMINA_REFILL_AMOUNT
    state.save(st)
    return jsonify(view(st))


# ─────────────────────────────────────────────────────── 보상 수령
@game_bp.post("/api/game/claim/mission")
def claim_mission():
    st, err = _need_player()
    if err:
        return err
    mid = _body().get("id") or ""
    for m in state.missions_view(st):
        if m["id"] == mid:
            if not m["complete"]:
                return jsonify({"error": "아직 완료되지 않았습니다."}), 400
            if m["claimed"]:
                return jsonify({"error": "이미 받았습니다."}), 400
            st["missions"]["claimed"].append(mid)
            state.gain(st, "stardust", m["reward"])
            state.save(st)
            return jsonify({"granted": {"stardust": m["reward"]}, "state": view(st)})
    return jsonify({"error": "없는 미션입니다."}), 400


@game_bp.post("/api/game/claim/login")
def claim_login():
    st, err = _need_player()
    if err:
        return err
    lv = _login_view(st)
    if lv["claimed"]:
        return jsonify({"error": "오늘 출석 보상은 이미 받았습니다."}), 400
    reward = econ.LOGIN_REWARDS[lv["day"] - 1]
    granted = {}
    for k in ("stardust", "gold", "ticket"):
        if reward.get(k):
            state.gain(st, k, reward[k])
            granted[k] = reward[k]
    st["login"] = {"date": state.today_str(), "streak": lv["streak"]}
    state.save(st)
    return jsonify({"granted": granted, "day": lv["day"], "state": view(st)})


# ─────────────────────────────────────────────────────── 기타
@game_bp.post("/api/game/profile")
def profile():
    st, err = _need_player()
    if err:
        return err
    name = (_body().get("name") or "").strip()[:16]
    if name:
        st["name"] = name
        state.save(st)
    return jsonify(view(st))


@game_bp.post("/api/game/reset")
def reset():
    st, err = _need_player()
    if err:
        return err
    fresh = state.new_state(st["pid"])
    for cid in state.STARTER_CHARS:
        state.add_character(fresh, cid)
    fresh["name"] = st["name"]
    state.save(fresh)
    return jsonify(view(fresh))
