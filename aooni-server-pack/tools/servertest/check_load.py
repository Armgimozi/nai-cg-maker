#!/usr/bin/env python3
"""데이터팩 로드 점검: 진짜 서버에 데이터팩을 넣고 켜서 문제를 찾는다.

  python3 tools/servertest/check_load.py                    # 1.21.11
  python3 tools/servertest/check_load.py --version 1.21.5 --version 1.21.11

하는 일
 1. 일회용 서버를 켜고 저택 건축(#built = 6)을 기다린 뒤 몇 초 더 돌린다(--settle).
 2. `datapack list` 에 file/aooni_mansion 이 켜져 있는지 확인.
 3. `function aooni:admin/help` 실행.
 4. .mcfunction 파일마다 `schedule function <id> 1000000s append` 를 보내서 서버에 실제로 등록됐는지 확인한다.
    (실행하지 않고 존재만 확인하는 방법. 등록 안 된 함수는 "Unknown function", 매크로 함수는
    "Can't schedule a macro" 로 답한다. append 라 데이터팩 자신의 예약은 건드리지 않는다.)
 5. 건축 함수를 흉내 내 계산한 블록이 실제 월드에 있는지 확인(fill·setblock 이 조용히 실패했거나
    받침이 없어 떨어진 블록 찾기).
 6. 서버 로그에서 오류 줄을 모두 모아 보여 준다.
오류가 하나라도 있으면 종료 코드 1.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import packinfo  # noqa: E402
from mcserver import DEFAULT_VERSION, MCServer, java_major, version_info  # noqa: E402

MAX_FILL = 32768


def check_version(version: str, settle: float, base: str | None, keep: bool) -> bool:
    print(f"\n=== 아오오니 데이터팩 로드 점검 · Minecraft {version} ===")
    need = version_info(version).get("javaVersion", {}).get("majorVersion", 21)
    if java_major() < need:
        print(f"[건너뜀] Java {need} 이상이 필요합니다(현재 Java {java_major()}).")
        return True
    problems: list[str] = []
    srv = MCServer(version, base=base, keep=keep)
    t0 = time.monotonic()
    try:
        srv.start()
        t_start = time.monotonic() - t0
        pack = os.path.join(srv.dir, "world", "datapacks", "aooni_mansion")   # 서버에 복사된 그 팩을 기준으로
        try:
            t_built = srv.wait_built(timeout=90)
            print(f"서버 시작 {t_start:.1f}초, 저택 건축(#built=6) {t_built:.1f}초")
        except TimeoutError as e:
            problems.append(str(e))
            print(f"[실패] {e}")
        # 예약된 함수·틱 함수가 몇 초 더 돌게 둔다
        left = settle - (time.monotonic() - t0 - t_start)
        if left > 0:
            time.sleep(left)

        # 1) 데이터팩 목록
        out = srv.cmd("datapack list")
        m = re.search(r"enabled: (.*?)(?:There are|$)", out)
        if m and "file/aooni_mansion" in m.group(1):
            print("데이터팩: file/aooni_mansion 켜짐")
        else:
            problems.append("datapack list 에 file/aooni_mansion 이 켜져 있지 않음")
            print(f"[실패] 데이터팩이 켜져 있지 않습니다: {out}")

        # 2) load·tick 이 돌았는지
        state, diff = srv.score("#state"), srv.score("#diff")
        t_a = srv.score("#t")
        time.sleep(0.35)
        t_b = srv.score("#t")
        tick_ok = t_a is not None and t_b is not None and t_a != t_b
        print(f"load 함수: #state={state} #diff={diff} / tick 함수: {'돌고 있음' if tick_ok else '안 도는 것 같음'} (#t {t_a}→{t_b})")
        if state is None or diff is None:
            problems.append("load 함수가 실행되지 않은 것 같음(#state/#diff 없음)")
        if not tick_ok:
            problems.append("tick 함수가 도는지 확인하지 못함(#t 가 변하지 않음)")

        # 3) admin/help
        out = srv.cmd("function aooni:admin/help")
        print(f"function aooni:admin/help → {out.strip()}")
        if "Running function" not in out and "Executed" not in out:
            problems.append(f"admin/help 실행 실패: {out.strip()}")

        # 4) 모든 함수 등록 확인
        files = packinfo.function_files(pack)
        missing, odd, n_macro = [], [], 0
        for fid, _, macro in files:
            r = srv.cmd(f"schedule function {fid} 1000000s append").strip()
            if r.startswith("Scheduled function"):
                continue
            if "Can't schedule a macro" in r:
                n_macro += 1
                continue
            if "Unknown function" in r:
                missing.append(fid)
            else:
                odd.append(f"{fid}: {r}")
        loaded = len(files) - len(missing) - len(odd)
        print(f"함수: 파일 {len(files)}개 중 {loaded}개가 서버에 등록됨 (매크로 {n_macro}개 포함)")
        for fid in missing:
            print(f"  [누락] {fid} — 서버가 이 함수를 불러오지 못함(로그의 'Failed to load function' 참고)")
        for o in odd:
            print(f"  [?] {o}")
        if missing or odd:
            problems.append(f"등록 안 된 함수 {len(missing) + len(odd)}개")

        # 5) 건축 결과 확인
        if srv.score("#built") == 6 and srv.score("#state") == 0:
            exp, _ = packinfo.expected_blocks(pack)
            bad = []
            for (x, y, z), bid in exp.items():
                r = srv.cmd(f"execute if block {x} {y} {z} {bid}")
                if "Test passed" not in r:
                    bad.append(((x, y, z), bid, r.strip()))
            print(f"건축 확인: {len(exp)}곳 중 {len(exp) - len(bad)}곳이 계산과 같음")
            for (x, y, z), bid, r in bad[:30]:
                print(f"  [다름] {x} {y} {z}: 기대 {bid} → {r}")
            if len(bad) > 30:
                print(f"  ... 외 {len(bad) - 30}곳")
            if bad:
                problems.append(f"건축 결과가 다른 칸 {len(bad)}곳")
        big = [(fid, vol, ln) for fid, vol, ln in packinfo.fill_volumes(pack) if vol > MAX_FILL]
        for fid, vol, ln in big:
            print(f"  [fill 너무 큼] {fid}: {vol}칸 > {MAX_FILL}: {ln}")
        if big:
            problems.append(f"{MAX_FILL}칸이 넘는 fill {len(big)}개")

        # 6) 로그
        errs = srv.errors()
        notes = srv.notes()
    finally:
        srv.stop()
        srv.cleanup()

    print(f"로그 오류: {len(errs)}건")
    for e in errs:
        print("  " + e.replace("\n", "\n  "))
    if errs:
        problems.append(f"로그 오류 {len(errs)}건")
    if notes:
        print("참고(데이터팩과 무관한 서버·환경 메시지):")
        for n in notes:
            print("  " + n.replace("\n", "\n  "))
    print(f"서버 로그: {srv.log_path}")
    if problems:
        print(f"결과: 실패 — {'; '.join(problems)}")
    else:
        print("결과: 통과")
    return not problems


def main() -> int:
    ap = argparse.ArgumentParser(description="아오오니 데이터팩을 진짜 서버에서 불러와 점검")
    ap.add_argument("--version", action="append", help=f"Minecraft 버전(여러 번 가능, 기본 {DEFAULT_VERSION})")
    ap.add_argument("--settle", type=float, default=10, help="서버 시작 뒤 최소 몇 초 돌릴지(기본 10)")
    ap.add_argument("--base", default=None, help="임시 서버 폴더를 만들 곳(저장소 밖)")
    ap.add_argument("--keep", action="store_true", help="서버 폴더를 지우지 않음")
    a = ap.parse_args()
    ok = True
    for v in a.version or [DEFAULT_VERSION]:
        ok = check_version(v, a.settle, a.base, a.keep) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
