#!/usr/bin/env python3
"""스모크 시나리오: 서버 + 봇 2명으로 실제 한 판을 시작해 하네스 전체가 동작하는지 확인한다.

  python3 tools/servertest/scenario_smoke.py               # 1.21.11, 봇 AoBot1·AoBot2
  python3 tools/servertest/scenario_smoke.py --max-chests 4 --keep

흐름
 1. 일회용 서버를 켜고 저택 건축을 기다린다.
 2. 노드 시나리오(bots/scenarios/smoke.js)를 띄워 봇 2명을 접속시킨다.
 3. RCON: `op AoBot1`, `execute as AoBot1 run function aooni:admin/start`
 4. RCON 으로 #state, 술래(aooni.oni_p), 생존자(aooni.alive), 태그를 확인한다.
 5. 상자 22개의 내용물을 RCON 으로 미리 기록한 뒤, 생존자 봇에게 가까운 상자 몇 개와
    '진짜 비밀번호 쪽지가 든 가장 가까운 상자'를 열게 한다(내용물은 모두 가져옴).
 6. 봇이 본 내용물 = RCON 기록인지, 쪽지를 집었으면 #found 가 오르고 알림이 왔는지,
    타이틀이 떴는지, 서버 로그에 오류가 없는지 확인한다.
시간 제한이 곳곳에 있고 전체 제한(--timeout)을 넘으면 서버와 노드를 강제로 끈다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import packinfo  # noqa: E402
from botrun import GlobalTimeout, NodeScenario, ScenarioError, pick_version  # noqa: E402
from mcserver import DEFAULT_VERSION, MCServer  # noqa: E402


def entity_pos(srv: MCServer, name: str) -> tuple[float, float, float] | None:
    out = srv.cmd(f"data get entity {name} Pos")
    m = re.search(r"\[(-?[\d.]+)d, (-?[\d.]+)d, (-?[\d.]+)d\]", out)
    return tuple(float(v) for v in m.groups()) if m else None


def dig_of(custom_data: str | dict | None) -> int | None:
    """custom_data 에서 aooni_dig 번호(진짜 비밀번호 쪽지)를 꺼낸다."""
    if not custom_data:
        return None
    if isinstance(custom_data, dict):
        v = custom_data.get("aooni_dig")
        return int(v) if v is not None else None
    m = re.search(r"aooni_dig: ?(\d+)", custom_data)
    return int(m.group(1)) if m else None


def run(a) -> int:
    version, note = pick_version(a.version)
    names = a.names.split(",")
    checks: list[tuple[str, bool, str]] = []      # (항목, 통과?, 설명)
    warns: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append((name, ok, detail))
        return ok

    srv = MCServer(version, base=a.base, keep=a.keep)
    report: dict = {"version": version, "note": note}
    with GlobalTimeout(a.timeout, srv) as gt:
        ns = None
        try:
            srv.start()
            pack = os.path.join(srv.dir, "world", "datapacks", "aooni_mansion")
            srv.wait_built(timeout=90)
            ns = NodeScenario(srv, os.path.join("scenarios", "smoke.js"), names, version,
                              timeout=a.timeout - 20, echo_messages=a.verbose)
            gt.add(ns)
            ns.start()
            joined = ns.wait_signal("joined", 90)
            check("봇 접속", len(joined["bots"]) == len(names),
                  ", ".join(f"{b['name']}@{b['pos']['x']},{b['pos']['y']},{b['pos']['z']}" for b in joined["bots"]))

            # ---- 게임 시작
            starter = names[0]
            report["op"] = srv.cmd(f"op {starter}").strip()
            out = srv.cmd(f"execute as {starter} run function aooni:admin/start").strip()
            report["start"] = out
            time.sleep(1.5)
            state = srv.score("#state")
            check("게임 시작(#state=1)", state == 1, f"admin/start → {out!r}, #state={state}")
            oni = srv.players_with_tag("aooni.oni_p")
            alive = [n for n in srv.players_with_tag("aooni.alive") if n not in oni]
            report["oni"], report["survivors"] = oni, alive
            report["tags"] = {n: srv.tags(n) for n in names}
            report["lives"] = {n: srv.score(n, "aooni.lives") for n in alive}
            check("술래 1명", len(oni) == 1, f"술래={oni}")
            check("생존자 있음", len(alive) >= 1, f"생존자={alive}")
            if not alive:
                raise ScenarioError("생존자가 없어 상자 단계를 건너뜀")
            surv = alive[0]

            # ---- 상자 기록 + 열 순서 정하기
            chests = packinfo.chest_positions(pack)
            snap = {c: srv.block_items(*c) for c in chests}
            report["chest_count"] = len(chests)
            missing = [c for c, v in snap.items() if v is None]
            m = re.search(r"count: (\d+)", srv.cmd("execute if entity @e[type=minecraft:marker,tag=aooni.spot]"))
            spots = int(m.group(1)) if m else 0
            report["spot_markers"] = spots
            check("상자 블록 수 = 조사 지점 마커 수", not missing and len(chests) == spots,
                  f"상자 {len(chests)}개, 마커 {spots}개, 상자 아님 {missing}")
            notes_at = {c: [dig_of(i["custom_data"]) for i in v if dig_of(i["custom_data"])]
                        for c, v in snap.items() if v}
            notes_at = {c: d for c, d in notes_at.items() if d}
            report["notes_in_chests"] = {f"{c[0]} {c[1]} {c[2]}": d for c, d in notes_at.items()}
            check("비밀번호 쪽지 4장이 상자에 배치됨", sorted(sum(notes_at.values(), [])) == [1, 2, 3, 4],
                  f"{report['notes_in_chests']}")
            p = entity_pos(srv, surv) or (33.5, -60, 32.5)

            def dist(c):
                return ((c[0] + .5 - p[0]) ** 2 + (c[2] + .5 - p[2]) ** 2 + (3 * (c[1] - p[1])) ** 2) ** .5
            order = sorted(chests, key=dist)
            plan = order[: max(1, a.max_chests - 1)]
            with_note = [c for c in order if c in notes_at]
            if with_note and with_note[0] not in plan:
                plan.append(with_note[0])
            plan += [c for c in order if c not in plan]       # 실패하면 다음 후보로
            ns.send_signal("go", {"survivor": surv, "oni": oni[0] if oni else None, "expectPos": list(p),
                                  "chests": [list(c) for c in plan], "maxChests": a.max_chests,
                                  "take": True, "chestTimeoutMs": 40000, "budgetMs": a.budget * 1000})

            # ---- 결과
            res = ns.wait_result(timeout=a.budget + 60)
            report["result"] = res
            opened = res["opened"]
            check("생존자가 상자를 1개 이상 엶", len(opened) >= 1,
                  f"{len(opened)}개 열기 성공, 실패 {len(res['failures'])}개")
            mism = []
            for o in opened:
                c = tuple(o["pos"])
                seen = sorted((i["slot"], "minecraft:" + i["name"], i["count"]) for i in o["items"])
                want = sorted((i["slot"], i["id"], i["count"]) for i in (snap.get(c) or []))
                if seen != want:
                    mism.append(f"{c}: 봇 {seen} / RCON {want}")
            check("봇이 본 상자 내용 = RCON 기록", not mism, "; ".join(mism))
            taken_digs = sorted({d for o in opened for i in o["taken"] if (d := dig_of(i.get("customData")))})
            report["taken_digs"] = taken_digs
            found = srv.score("#found")
            report["found"] = found
            if taken_digs:
                smsgs = [m["text"] for m in res["messages"].get(surv, [])]
                got = [m for m in smsgs if "비밀번호 쪽지" in m and "찾았다" in m]
                check("쪽지를 집으면 #found 증가", found == len(taken_digs), f"집은 쪽지 {taken_digs}, #found={found}")
                check("쪽지 발견 알림을 받음", bool(got), got[0] if got else "알림 없음")
                inv_read = [i for i in res["inventory"] if (i.get("customData") or {}).get("read")]
                check("집은 쪽지가 '펼친 쪽지'로 바뀜", bool(inv_read),
                      "; ".join(f"{i.get('customName')}: {' / '.join(i.get('lore') or [])}" for i in inv_read))
            else:
                warns.append("이번에는 진짜 비밀번호 쪽지를 집지 못해 #found 확인을 건너뜀")

            titles = {n: [m["text"] for m in res["messages"].get(n, []) if m["kind"] in ("title", "subtitle")]
                      for n in names}
            report["titles"] = titles
            if oni:
                check("술래에게 '당신은 아오오니' 타이틀", any("아오오니" in t for t in titles.get(oni[0], [])),
                      " | ".join(titles.get(oni[0], [])))
            check("생존자에게 시작 타이틀", any("아오오니 저택" in t for t in titles.get(surv, [])),
                  " | ".join(titles.get(surv, [])))
            ns.send_signal("done")
        except (ScenarioError, TimeoutError, RuntimeError) as e:
            check("시나리오 진행", False, f"{type(e).__name__}: {e}")
        finally:
            if ns:
                ns.stop()
            errs = srv.errors() if srv.proc else []
            notes = srv.notes() if srv.proc else []
            srv.stop()
            srv.cleanup()
        if gt.fired:
            check("전체 시간 제한 안에 끝남", False, f"{a.timeout}초 초과")
    check("서버 로그 오류 없음", not errs, "\n".join(errs))

    # ---- 보고
    print(f"\n=== 아오오니 스모크 시나리오 · Minecraft {version} ===")
    print(f"버전: {note}")
    if "oni" in report:
        print(f"술래: {', '.join(report['oni']) or '-'} / 생존자: {', '.join(report['survivors']) or '-'}")
        for n, t in report.get("tags", {}).items():
            print(f"  {n} 태그: {', '.join(t)}")
    if "notes_in_chests" in report:
        print(f"쪽지가 든 상자(RCON): {report['notes_in_chests']}")
    res = report.get("result")
    if res:
        for o in res["opened"]:
            items = ", ".join(f"{i.get('customName') or i['name']}×{i['count']}" for i in o["items"]) or "(빈 상자)"
            print(f"  상자 {o['pos']} 열기 성공({o['walkMs'] / 1000:.1f}초 이동): {items}")
        for f in res["failures"]:
            print(f"  상자 {f['pos']} 실패: {f['error']}")
        inv = ", ".join(f"{i.get('customName') or i['name']}×{i['count']}" for i in res["inventory"])
        print(f"  생존자 인벤토리: {inv or '(없음)'}")
        for n, msgs in res["messages"].items():
            shown = [f"{m['kind']}: {m['text']}" for m in msgs if m["kind"] != "actionbar"][:12]
            print(f"  {n} 받은 메시지 {len(msgs)}개(액션바 제외 앞부분):")
            for s in shown:
                print(f"    {s.replace(chr(10), ' ')}")
    print("점검:")
    for name, ok, detail in checks:
        print(f"  [{'통과' if ok else '실패'}] {name}" + (f" — {detail}" if detail else ""))
    for w in warns:
        print(f"  [참고] {w}")
    for n in notes:
        print(f"  [참고] {n.splitlines()[0]}")
    print(f"서버 로그: {srv.log_path}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"report": report, "checks": checks}, f, ensure_ascii=False, indent=1)
    failed = [c for c in checks if not c[1]]
    print("결과: " + ("통과" if not failed else f"실패 {len(failed)}건"))
    return 0 if not failed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="아오오니 데이터팩 스모크 시나리오(서버 + mineflayer 봇)")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--names", default="AoBot1,AoBot2", help="봇 이름(쉼표로 구분, 첫 번째가 게임을 시작)")
    ap.add_argument("--max-chests", type=int, default=3, help="생존자가 열 상자 수(기본 3)")
    ap.add_argument("--budget", type=float, default=120, help="상자 단계 시간 예산(초)")
    ap.add_argument("--timeout", type=float, default=360, help="전체 시간 제한(초)")
    ap.add_argument("--base", default=None)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="봇이 받는 메시지를 실시간으로 출력")
    ap.add_argument("--json", default=None, help="결과를 JSON 파일로도 저장")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
