#!/usr/bin/env python3
"""한 판의 핵심 흐름을 실서버 + 봇 3명(아오오니 1, 생존자 2)으로 끝까지 돌려 본다.

  1) 아오오니에게 여러 대 맞아 쓰러짐 → 지하 감옥에서 부활(목숨 -1)
  2) 동료가 감옥 앞 버튼으로 구출
  3) 맞은 뒤 빵을 먹어 체력 회복
  4) 2층 금고 다이얼을 실제로 눌러 비밀번호 입력 → 마검 + 결전 시작(거대화, 체력)
  5) 마검을 든 생존자가 쓰러지면 마검이 그 자리에 떨어짐
  6) 다른 생존자가 마검을 주워 아오오니를 쓰러뜨림 → 생존자 승리
  7) 서버 로그 오류 0건

사용:  python3 tools/servertest/scenario_full.py [--version 1.21.11] [--verbose]
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

PACK_FN = os.path.join(os.path.dirname(os.path.dirname(HERE)), "server", "world", "datapacks", "aooni_mansion",
                       "data", "aooni", "function")

# 데이터팩 좌표(tools/build_pack.py 와 같아야 한다)
JAIL_SEL = "x=1,y=-61,z=1,dx=11,dy=4,dz=8"
RESCUE = (3, -59, 11)
RESCUE_STAND = (3.5, -60, 13.5)
SAFE_STAND = (48.5, -50, 3.5)
SAFE_Y, SAFE_Z = -49, 1          # 다이얼 x=46..49, 확인 x=50


def item_from(fn_rel):
    """생성된 loot/put/*.mcfunction 에서 아이템 문자열을 꺼낸다."""
    with open(os.path.join(PACK_FN, fn_rel), encoding="utf-8") as f:
        for ln in f:
            if " with " in ln:
                return ln.split(" with ", 1)[1].strip()
    raise RuntimeError(fn_rel)


class Report:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), detail))
        print(f"  [{'통과' if ok else '실패'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
        return ok

    @property
    def ok(self):
        return all(r[1] for r in self.rows)


def attr(srv, who, name):
    out = srv.cmd(f"attribute {who} minecraft:{name} get")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*$", out.strip())
    return float(m.group(1)) if m else None


def inside(srv, who, sel):
    return "passed" in srv.cmd(f"execute if entity @a[name={who},{sel}]").lower()


def hit_until(srv, ns, attacker, target, done, tries=15, gap=0.75, away=None):
    """때릴 때마다 붙여 주고, 끝나면(away 가 있으면) 곧바로 멀리 보낸다(떨어진 아이템을 줍지 않게)."""
    n = 0
    for _ in range(tries):
        if done():
            break
        srv.cmd(f"tp {attacker} {target}")
        time.sleep(0.15)
        ns.call("attackPlayer", bot=attacker, target=target, timeout=10)
        n += 1
        time.sleep(0.25)
        if done():
            break
        time.sleep(gap - 0.25)
    if away:
        srv.cmd(f"tp {attacker} {away}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.21.11")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    version, note = pick_version(a.version)
    if note:
        print(note)
    names = ["AoOni", "AoSurvA", "AoSurvB"]
    ONI, A, B = names
    R = Report()
    srv = MCServer(version)
    print(f"=== 아오오니 저택 전체 흐름 시나리오 · Minecraft {version} ===", flush=True)
    with GlobalTimeout(a.timeout, srv) as gt:
        try:
            srv.start()
            srv.wait_built()
            with NodeScenario(srv, "driver.js", names, version, timeout=a.timeout, echo_messages=a.verbose) as ns:
                gt.add(ns)
                ns.wait_signal("ready", 30)
                ns.call("connect", timeout=120)

                # ---- 시작
                srv.cmd(f"execute as {ONI} run function aooni:admin/oni_pick")
                srv.cmd(f"execute as {ONI} run function aooni:admin/start")
                time.sleep(1.5)
                R.check("게임 시작(#state=1)", srv.score("#state") == 1)
                R.check("지원자가 아오오니", "aooni.oni_p" in srv.tags(ONI), str(srv.tags(ONI)))
                R.check("생존자 2명", all("aooni.alive" in srv.tags(n) for n in (A, B)))
                R.check("아오오니 공격력 5(보통)", attr(srv, ONI, "attack_damage") == 5.0, str(attr(srv, ONI, "attack_damage")))
                srv.cmd("scoreboard players set #freeze aooni.var 1")
                time.sleep(2)
                srv.cmd(f"effect clear {ONI} minecraft:slowness")
                srv.cmd(f"effect clear {ONI} minecraft:blindness")
                R.check("아오오니가 깨어남(#freeze=0)", srv.score("#freeze") == 0)

                # ---- 1) 여러 대 맞아 쓰러짐 → 감옥
                lives0 = srv.score(A, "aooni.lives")
                first = None
                n = 0
                for _ in range(12):
                    if "aooni.alive" not in srv.tags(A):
                        break
                    srv.cmd(f"tp {ONI} {A}")
                    time.sleep(0.15)
                    ns.call("attackPlayer", bot=ONI, target=A, timeout=10)
                    n += 1
                    time.sleep(0.75)
                    if first is None:
                        first = ns.call("health", bot=A)["health"]
                R.check("한 대 맞으면 체력 5 감소", first is not None and abs(first - 15) < 0.6, f"첫 대 뒤 체력 {first}")
                R.check("여러 대(4대) 맞아야 쓰러짐", n == 4, f"{n}대")
                time.sleep(1.5)
                tg = srv.tags(A)
                R.check("쓰러지면 감옥 태그", "aooni.jailed" in tg and "aooni.alive" not in tg, str(tg))
                R.check("목숨 1 감소", srv.score(A, "aooni.lives") == (lives0 or 0) - 1, f"{lives0} → {srv.score(A, 'aooni.lives')}")
                R.check("지하 감옥 칸 안에서 부활", inside(srv, A, JAIL_SEL))
                R.check("부활 후 체력 20", ns.call("health", bot=A)["health"] >= 19.5)

                # ---- 2) 구출
                srv.cmd(f"tp {B} {RESCUE_STAND[0]} {RESCUE_STAND[1]} {RESCUE_STAND[2]} facing {RESCUE[0] + .5} {RESCUE[1] + .5} {RESCUE[2] + .5}")
                time.sleep(0.8)
                ns.call("activateBlockAt", bot=B, x=RESCUE[0], y=RESCUE[1], z=RESCUE[2], timeout=15)
                time.sleep(1.5)
                tg = srv.tags(A)
                R.check("감옥 앞 버튼으로 구출", "aooni.alive" in tg and "aooni.jailed" not in tg, str(tg))
                R.check("구출되면 감옥 칸 밖", not inside(srv, A, JAIL_SEL))

                # ---- 3) 맞고 빵 먹기
                srv.cmd(f"effect clear {A} minecraft:resistance")
                srv.cmd(f"tp {ONI} {A}")
                time.sleep(0.2)
                ns.call("attackPlayer", bot=ONI, target=A, timeout=10)
                time.sleep(0.8)
                h1 = ns.call("health", bot=A)["health"]
                srv.cmd(f"give {A} {item_from('loot/put/bread.mcfunction')}")
                time.sleep(0.5)
                ns.call("equip", bot=A, item="bread", timeout=10)
                ns.call("consume", bot=A, timeout=15)
                time.sleep(0.8)
                h2 = ns.call("health", bot=A)["health"]
                R.check("빵을 먹으면 체력 4(2칸) 회복", abs((h2 - h1) - 4) < 0.6, f"{h1} → {h2}")

                # ---- 4) 금고
                digits = [srv.score(f"#k{j}") for j in range(1, 5)]
                srv.cmd(f"tp {B} {SAFE_STAND[0]} {SAFE_STAND[1]} {SAFE_STAND[2]} facing 48.5 {SAFE_Y + .5} {SAFE_Z + .5}")
                time.sleep(0.8)
                for j, d in enumerate(digits, 1):
                    for _ in range(d):
                        ns.call("activateBlockAt", bot=B, x=45 + j, y=SAFE_Y, z=SAFE_Z, timeout=10)
                        time.sleep(0.25)
                time.sleep(0.5)
                dials = [srv.score(f"#d{j}") for j in range(1, 5)]
                R.check("금고 다이얼을 눌러 비밀번호 입력", dials == digits, f"정답 {digits} / 입력 {dials}")
                ns.call("activateBlockAt", bot=B, x=50, y=SAFE_Y, z=SAFE_Z, timeout=10)
                time.sleep(1.5)
                R.check("금고가 열려 결전 시작", srv.score("#wpn") == 1 and srv.score("#final") == 1)
                inv = ns.call("inventory", bot=B)
                R.check("마검을 받음", any("netherite_sword" in str(i.get("name")) for i in inv), str([i.get("name") for i in inv]))
                time.sleep(1.2)
                R.check("마검을 들면 armed 태그", "aooni.armed" in srv.tags(B))
                R.check("아오오니 거대화(1.3배)", abs((attr(srv, ONI, "scale") or 0) - 1.3) < 0.01)
                R.check("결전 체력 60+20×2=100", attr(srv, ONI, "max_health") == 100.0, str(attr(srv, ONI, "max_health")))

                # ---- 5) 마검을 든 사람이 쓰러지면 그 자리에 떨어짐
                pos = ns.call("position", bot=B)
                srv.cmd(f"effect clear {B} minecraft:resistance")
                hit_until(srv, ns, ONI, B, lambda: "aooni.alive" not in srv.tags(B), away="48.5 -45 33.5")
                time.sleep(1.5)
                R.check("마검 든 생존자도 쓰러짐 → 감옥", "aooni.jailed" in srv.tags(B))
                near = srv.cmd(f"execute positioned {pos['x']:.1f} {pos['y']:.1f} {pos['z']:.1f} if entity "
                               "@e[type=minecraft:item,distance=..4,nbt={Item:{id:\"minecraft:netherite_sword\"}}]")
                R.check("마검이 쓰러진 자리에 떨어짐", "passed" in near.lower(), near.strip())
                if "passed" not in near.lower():
                    print("    진단: 쓰러지기 전 위치", pos)
                    print("    진단:", srv.cmd(f"data get entity {B} LastDeathLocation").strip())
                    print("    진단:", srv.cmd("data get entity @e[type=minecraft:item,limit=1,nbt={Item:{id:\"minecraft:netherite_sword\"}}] Pos").strip())
                    print("    진단: 마검 아이템 수", srv.cmd("execute store result score #dbg aooni.var if entity @e[type=minecraft:item,nbt={Item:{id:\"minecraft:netherite_sword\"}}]").strip(), srv.score("#dbg"))
                    print("    진단: 마검 든 플레이어", srv.cmd("clear @a minecraft:netherite_sword 0").strip())
                    print("    진단: storage", srv.cmd("data get storage aooni:v").strip()[:300])
                R.check("쓰러진 사람은 마검이 없음", "aooni.armed" not in srv.tags(B))

                # ---- 5b) 아오오니가 떨어진 마검을 건드리면 먼 곳으로 날아간다
                srv.cmd(f"tp {ONI} {pos['x']:.2f} {pos['y']:.2f} {pos['z']:.2f}")
                time.sleep(2.5)
                srv.cmd(f"tp {ONI} 48.5 -45 33.5")
                sw = srv.cmd("data get entity @e[type=minecraft:item,limit=1,nbt={Item:{id:\"minecraft:netherite_sword\"}}] Pos")
                m = re.findall(r"(-?\d+(?:\.\d+)?)d", sw)
                spos = [float(v) for v in m[:3]] if len(m) >= 3 else None
                far = spos is not None and ((spos[0] - pos["x"]) ** 2 + (spos[2] - pos["z"]) ** 2) ** 0.5 > 10
                R.check("아오오니가 건드린 마검은 먼 곳으로 날아감", far and "No items" in srv.cmd(f"clear {ONI} minecraft:netherite_sword 0"),
                        f"마검 위치 {spos}")
                if spos:
                    pos = {"x": spos[0], "y": spos[1], "z": spos[2]}

                # ---- 6) 다른 생존자가 주워서 족치기
                srv.cmd(f"tp {A} {pos['x']:.2f} {pos['y']:.2f} {pos['z']:.2f}")
                time.sleep(2.5)
                inv = ns.call("inventory", bot=A)
                R.check("다른 생존자가 마검을 주움", any("netherite_sword" in str(i.get("name")) for i in inv))
                ns.call("equip", bot=A, item="netherite_sword", timeout=10)
                time.sleep(1.2)
                hits = hit_until(srv, ns, A, ONI, lambda: srv.score("#state") != 1, tries=20, gap=0.9)
                time.sleep(1.0)
                R.check("아오오니를 쓰러뜨려 생존자 승리(#state=2)", srv.score("#state") == 2, f"{hits}번 휘두름")
                msgs = ns.call("messages", bot=A)
                R.check("승리 타이틀", any("족쳤다" in str(m.get("text", "")) for m in msgs))
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
