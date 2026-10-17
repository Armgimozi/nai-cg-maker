#!/usr/bin/env python3
"""배포 월드용 집 주인 기록 (0.3.7 fix) — 주인 없음 + fresh_world: true.

새 world.zip 으로 처음 켠 서버는 옮길 옛 건물이 없다. 이 표시가 있으면 집 모듈이 처음 잠금을 켤 때 이사 기간(14일)·옛 건물 조사를
건너뛴다 (지은 것이 없는데 "이사 기간 n일 남음" 안내가 나오고, 그 사이 구역 옹벽을 누구나 부수던 것). 처음 켤 때 잠금이 꺼져 있으면
(homes.terrain_lock: false 등) 표시를 지우고, 나중에 잠금을 켜면 보통처럼 이사 기간을 준다.

사용:
  python3 tools/village/fresh_plots.py <월드>/dimensions/minecraft/overworld/labyrinth-plots.yml   # 파일 쓰기 (build_world.sh)
  python3 tools/village/fresh_plots.py --zip dist/world.zip                                        # 이미 만든 world.zip 에 넣기 (같은 내용)
"""
import argparse
import os
import shutil
import sys
import tempfile
import zipfile

TEXT = (
    "# 미궁 라비린스 — 집 주인 기록 (0.3.7). 서버가 꺼진 동안에만 고치세요. 이 파일은 월드와 같이 다닙니다.\n"
    "# 배포 월드: 주인 없음. 처음 켤 때 이사 기간 없이 지형 잠금을 켭니다 (fresh_world).\n"
    "format: 1\n"
    "fresh_world: true\n"
)
ARC = "world/dimensions/minecraft/overworld/labyrinth-plots.yml"


def write_file(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEXT)
    print("  집 주인 기록: 주인 없음 · fresh_world (%s)" % os.path.basename(path))


def put_zip(zpath):
    """zip 안의 labyrinth-plots.yml 을 바꾸거나 더함 (다른 항목은 그대로 복사)."""
    fd, tmp = tempfile.mkstemp(suffix=".zip", dir=os.path.dirname(os.path.abspath(zpath)))
    os.close(fd)
    n = 0
    with zipfile.ZipFile(zpath) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
        for info in src.infolist():
            if info.filename == ARC:
                continue
            dst.writestr(info, src.read(info.filename))
            n += 1
        dst.writestr(ARC, TEXT)
        n += 1
    shutil.move(tmp, zpath)
    print("  %s: %s 넣음 (파일 %d개)" % (os.path.basename(zpath), ARC, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--zip")
    a = ap.parse_args()
    if a.zip:
        put_zip(a.zip)
    elif a.path:
        write_file(a.path)
    else:
        ap.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
