#!/usr/bin/env python3
"""아오오니 모델(리소스팩 item_display 6부위)과 동작을 실서버에서 확인한다.

  - 게임이 시작되면 부위 6개가 아오오니 발밑에 붙어 다니는지
  - 걸으면 다리·팔 회전값이 계속 바뀌고, 멈추면 차렷(회전 0)으로 돌아오는지
  - 때리면 오른팔이 앞으로 휘둘러지는지
  - 아래를 보면 고개가 숙여지는지
  - 결전(거대화)에서 모델이 1.3배가 되는지

사용:  python3 tools/servertest/scenario_anim.py [--version 1.21.11]
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mcserver import MCServer  # noqa: E402
from botrun import NodeScenario, GlobalTimeout, pick_version  # noqa: E402
from scenario_full import Report  # noqa: E402


def rot(srv, part):
    out = srv.cmd(f"data get entity @e[type=minecraft:item_display,tag=aooni.p_{part},limit=1] transformation.left_rotation")
    v = re.findall(r"(-?\d+(?:\.\d+)?(?:E-?\d+)?)f", out)
    return [round(float(x), 3) for x in v] if len(v) == 4 else None


def scale(srv, part):
    out = srv.cmd(f"data get entity @e[type=minecraft:item_display,tag=aooni.p_{part},limit=1] transformation.scale[0]")
    m = re.search(r"(-?\d+(?:\.\d+)?)f?\s*$", out.strip())
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.21.11")
    a = ap.parse_args()
    version, note = pick_version(a.version)
    names = ["AoOni", "AoSurv"]
    ONI, S = names
    R = Report()
    srv = MCServer(version)
    print(f"=== 아오오니 모델·동작 시나리오 · Minecraft {version} ===", flush=True)
    with GlobalTimeout(400, srv) as gt:
        try:
            srv.start()
            srv.wait_built()
            with NodeScenario(srv, "driver.js", names, version, timeout=400, echo_messages=False) as ns:
                gt.add(ns)
                ns.wait_signal("ready", 30)
                ns.call("connect", timeout=120)
                srv.cmd(f"execute as {ONI} run function aooni:admin/oni_pick")
                srv.cmd(f"execute as {ONI} run function aooni:admin/start")
                time.sleep(1.5)
                srv.cmd("scoreboard players set #freeze aooni.var 1")
                time.sleep(2)
                srv.cmd(f"effect clear {ONI} minecraft:slowness")
                srv.cmd(f"effect clear {ONI} minecraft:blindness")
                cnt = srv.cmd("execute store result score #dbg aooni.var if entity @e[type=minecraft:item_display,tag=aooni.part]")
                R.check("모델 부위 6개", srv.score("#dbg") == 6, cnt.strip())
                items = srv.cmd("data get entity @e[type=minecraft:item_display,tag=aooni.p_head,limit=1] item")
                R.check("머리 부위가 리소스팩 모델(aooni:oni_head)", "aooni:oni_head" in items, items.strip()[:160])
                near = srv.cmd(f"execute at {ONI} if entity @e[type=minecraft:item_display,tag=aooni.part,distance=..0.6]")
                R.check("부위가 아오오니 발밑에 붙어 있음", "passed" in near.lower(), near.strip())

                # 걷기: 3층 복도를 왕복하며 다리 회전값을 여러 번 읽는다
                srv.cmd(f"tp {ONI} 48.5 -45 21.5 90 0")
                time.sleep(1.5)
                rest0 = rot(srv, "leg_l")
                samples = []
                ns_call = ns.call
                import threading
                walker = threading.Thread(target=lambda: ns_call("goto", bot=ONI, x=33, y=-45, z=21, range=1, timeout=40), daemon=True)
                walker.start()
                for _ in range(12):
                    time.sleep(0.25)
                    samples.append(rot(srv, "leg_l"))
                walker.join(40)
                distinct = {tuple(x) for x in samples if x}
                R.check("서 있을 때 다리 회전 0", rest0 is not None and abs(rest0[0]) < 0.01, str(rest0))
                R.check("걸으면 다리 회전값이 계속 바뀜", len(distinct) >= 3, f"{len(distinct)}가지 {sorted(distinct)[:4]}")
                arm = rot(srv, "arm_l")
                time.sleep(1.0)
                still = rot(srv, "leg_l")
                R.check("멈추면 차렷 자세로 돌아옴", still is not None and abs(still[0]) < 0.01, str(still))

                # 고개
                srv.cmd(f"tp {ONI} ~ ~ ~ ~ 40")
                time.sleep(0.6)
                head = rot(srv, "head")
                R.check("아래를 보면 고개를 숙임(+30도)", head is not None and head[0] > 0.2, str(head))
                srv.cmd(f"tp {ONI} ~ ~ ~ ~ 0")
                time.sleep(0.6)
                R.check("앞을 보면 고개가 돌아옴", (rot(srv, "head") or [1])[0] < 0.01, str(rot(srv, "head")))

                # 공격
                srv.cmd(f"tp {S} {ONI}")
                time.sleep(0.4)
                ns.call("attackPlayer", bot=ONI, target=S, timeout=10)
                time.sleep(0.12)
                arm = rot(srv, "arm_r")
                R.check("때리면 오른팔을 앞으로 휘두름", arm is not None and arm[0] < -0.5, str(arm))
                time.sleep(0.6)
                arm2 = rot(srv, "arm_r")
                R.check("휘두른 뒤 팔이 내려옴", arm2 is not None and arm2[0] > -0.2, str(arm2))

                # 거대화
                srv.cmd(f"execute as {S} run function aooni:admin/final_now")
                time.sleep(1.5)
                R.check("결전에서 모델 1.3배", abs((scale(srv, "torso") or 0) - 1.3) < 0.01, str(scale(srv, "torso")))
                cnt = srv.cmd("execute store result score #dbg aooni.var if entity @e[type=minecraft:item_display,tag=aooni.part]")
                R.check("거대화 뒤에도 부위 6개(중복 없음)", srv.score("#dbg") == 6)
                ns.call("quit", timeout=10)
            errs = srv.errors()
            R.check("서버 로그 오류 0건", not errs, "\n".join(errs[:5]))
        finally:
            srv.stop()
            srv.cleanup()
    print("결과:", "통과" if R.ok else "실패", f"({sum(r[1] for r in R.rows)}/{len(R.rows)})")
    return 0 if R.ok else 1


if __name__ == "__main__":
    sys.exit(main())
