"""플레이어 상태 저장 — SQLite 한 파일.

상태 전체를 JSON 문서 하나로 보관한다(플레이어당 한 행). 뽑기·결제처럼
돈이 걸린 계산은 전부 서버에서만 하고, 클라이언트는 결과만 받는다.

플레이어 식별은 서버가 발급한 랜덤 토큰(pid)으로 한다. 계정/비밀번호가 없는
익명 저장이므로, 상용 출시 시에는 여기에 정식 인증을 붙여야 한다.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from . import econ
from .content import BY_ID, LEVEL_CAP, MAX_ASCEND, ASCEND_BONUS, DUPE_SHARDS

# KST 기준으로 하루를 자르면 출석·일일 미션이 한국 플레이어 기준과 맞는다.
KST = timezone(timedelta(hours=9))
_LOCK = threading.Lock()

DB_PATH = Path(os.environ.get("GACHA_DB")
               or Path(__file__).resolve().parent.parent / "data" / "gacha.db")

# 신규 플레이어 지급분: 10연 2회 + 여유
STARTER = {"stardust": 3200, "essence": 0, "ticket": 5, "gold": 20000}
# 첫 화면이 비어 있지 않도록, 그리고 1-1 을 바로 해볼 수 있도록 주는 시작 캐릭터.
STARTER_CHARS = ["sora", "coco"]


def today_str() -> str:
    return datetime.now(KST).date().isoformat()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS players ("
              "pid TEXT PRIMARY KEY, created REAL, updated REAL, data TEXT)")
    return c


def new_state(pid: str) -> dict:
    now = time.time()
    return {
        "pid": pid,
        "name": "이름 없는 감독관",
        "created": now,
        "currency": dict(STARTER),
        "stamina": {"value": econ.STAMINA_MAX, "ts": now},
        "roster": {},
        "team": [],
        "pity": {"limited": {"c5": 0, "c4": 0, "g5": False},
                 "standard": {"c5": 0, "c4": 0, "g5": False}},
        "pulls": {"total": 0, "banner": {}},
        "history": [],
        "stages": {},
        "shop": {"purchased": {}, "monthly_until": 0.0, "monthly_claimed": "",
                 "spent_krw": 0},
        "missions": {"date": today_str(), "progress": {}, "claimed": []},
        "login": {"date": "", "streak": 0},
    }


def create_player() -> dict:
    pid = secrets.token_urlsafe(18)
    st = new_state(pid)
    for cid in STARTER_CHARS:
        add_character(st, cid)
    with _LOCK, _conn() as c:
        c.execute("INSERT INTO players(pid, created, updated, data) VALUES (?,?,?,?)",
                  (pid, st["created"], st["created"],
                   json.dumps(st, ensure_ascii=False)))
    return st


def load(pid: str) -> dict | None:
    with _LOCK, _conn() as c:
        row = c.execute("SELECT data FROM players WHERE pid=?", (pid,)).fetchone()
    if not row:
        return None
    st = json.loads(row[0])
    return _migrate(st)


def save(st: dict) -> None:
    with _LOCK, _conn() as c:
        c.execute("UPDATE players SET updated=?, data=? WHERE pid=?",
                  (time.time(), json.dumps(st, ensure_ascii=False), st["pid"]))


def _migrate(st: dict) -> dict:
    """예전 저장본에 새 필드가 없어도 깨지지 않게 기본값을 채운다."""
    base = new_state(st.get("pid", ""))
    for k, v in base.items():
        if k not in st:
            st[k] = v
        elif isinstance(v, dict) and isinstance(st[k], dict):
            for kk, vv in v.items():
                st[k].setdefault(kk, vv)
    return st


# ───────────────────────────────────────────────────── 스태미나
def refresh_stamina(st: dict) -> None:
    s = st["stamina"]
    now = time.time()
    gained = int((now - s["ts"]) // econ.STAMINA_REGEN_SEC)
    if gained > 0:
        # 최대치를 넘겨 회복되지는 않지만, 초과분 시간은 버린다(일반적인 처리).
        s["value"] = min(econ.STAMINA_MAX, s["value"] + gained)
        s["ts"] = now if s["value"] >= econ.STAMINA_MAX else s["ts"] + gained * econ.STAMINA_REGEN_SEC
    if s["value"] >= econ.STAMINA_MAX:
        s["ts"] = now


def stamina_next_sec(st: dict) -> int:
    s = st["stamina"]
    if s["value"] >= econ.STAMINA_MAX:
        return 0
    return max(0, int(econ.STAMINA_REGEN_SEC - (time.time() - s["ts"])))


# ───────────────────────────────────────────────────── 재화
def spend(st: dict, kind: str, amount: int) -> bool:
    if st["currency"].get(kind, 0) < amount:
        return False
    st["currency"][kind] -= amount
    return True


def gain(st: dict, kind: str, amount: int) -> None:
    st["currency"][kind] = st["currency"].get(kind, 0) + int(amount)


# ───────────────────────────────────────────────────── 캐릭터
def add_character(st: dict, cid: str) -> dict:
    """획득 처리. 신규면 로스터에 넣고, 중복이면 성흔 또는 조각으로 바꾼다."""
    r = st["roster"]
    rarity = BY_ID[cid]["rarity"]
    if cid not in r:
        r[cid] = {"level": 1, "exp": 0, "ascend": 0, "shards": 0,
                  "obtained": time.time()}
        if len(st["team"]) < 4 and cid not in st["team"]:
            st["team"].append(cid)
        return {"new": True, "ascend": 0, "shards": 0}
    e = r[cid]
    if e["ascend"] < MAX_ASCEND:
        e["ascend"] += 1
        return {"new": False, "ascend": e["ascend"], "shards": 0}
    sh = DUPE_SHARDS[rarity]
    e["shards"] += sh
    return {"new": False, "ascend": e["ascend"], "shards": sh}


def unit_stats(cid: str, entry: dict) -> dict:
    """레벨·성흔을 반영한 최종 능력치."""
    c = BY_ID[cid]
    b = c["base"]
    lv = 1 + 0.085 * (entry["level"] - 1)
    asc = 1 + ASCEND_BONUS * entry["ascend"]
    return {
        "hp": int(b["hp"] * lv * asc),
        "atk": int(b["atk"] * lv * asc),
        "def": int(b["def"] * (1 + 0.07 * (entry["level"] - 1)) * asc),
        "spd": int(b["spd"] * (1 + 0.02 * entry["ascend"])),
    }


def power(cid: str, entry: dict) -> int:
    s = unit_stats(cid, entry)
    return int(s["atk"] * 2.2 + s["hp"] * 0.35 + s["def"] * 1.6 + s["spd"] * 1.5)


def levelup_cost(rarity: int, level: int) -> int:
    return int((60 + 18 * level) * (1 + 0.35 * (rarity - 3)))


def level_cap(cid: str) -> int:
    return LEVEL_CAP[BY_ID[cid]["rarity"]]


# ───────────────────────────────────────────────────── 일일 초기화
def roll_daily(st: dict) -> None:
    """날짜가 바뀌었으면 일일 미션을 초기화한다(출석은 claim 시 처리)."""
    t = today_str()
    if st["missions"].get("date") != t:
        st["missions"] = {"date": t, "progress": {}, "claimed": []}


def bump_mission(st: dict, mid: str, amount: int = 1) -> None:
    roll_daily(st)
    p = st["missions"]["progress"]
    p[mid] = p.get(mid, 0) + amount


def missions_view(st: dict) -> list[dict]:
    roll_daily(st)
    p = st["missions"]["progress"]
    done = set(st["missions"]["claimed"])
    out = []
    for m in econ.DAILY_MISSIONS:
        cur = min(p.get(m["id"], 0), m["goal"])
        out.append({**m, "progress": cur,
                    "complete": cur >= m["goal"], "claimed": m["id"] in done})
    return out
