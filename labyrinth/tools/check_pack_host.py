#!/usr/bin/env python3
"""배포마다 리소스팩 공개 사본이 있는지 본다 (0.3.6.1 — config pack.public_copy 가 이 사본을 가리킨다).

  python3 tools/check_pack_host.py            # 지금 팩(resourcepack/dist/labyrinth-pack.zip)의 사본이 pack-host/ 에 있고 같은지 (없으면 1)
  python3 tools/check_pack_host.py --write    # 없으면 pack-host/labyrinth-pack-<sha8>.zip 으로 복사 (release 때)
  python3 tools/check_pack_host.py PACK.zip   # 다른 팩으로

pack-host/ 사본은 배포 가지(claude/bold-darwin-nwa5vk)에 올라가야 raw.githubusercontent.com 주소로 받을 수 있다.
release.sh 가 이 검사를 부르게 하는 것은 release.sh 를 맡은 쪽(광산 마을 가지)에서 합칠 때 한다.
"""
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = ROOT / 'pack-host'
DEFAULT_PACK = ROOT / 'resourcepack/dist/labyrinth-pack.zip'


def sha1_of(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main(argv):
    write = '--write' in argv
    args = [a for a in argv if not a.startswith('--')]
    pack = Path(args[0]) if args else DEFAULT_PACK
    if not pack.is_file():
        print(f'[팩 사본] 팩이 없습니다: {pack} (resourcepack/generate.py 먼저)')
        return 1
    sha = sha1_of(pack)
    copy = HOST / f'labyrinth-pack-{sha[:8]}.zip'
    if copy.is_file():
        have = sha1_of(copy)
        if have != sha:
            print(f'[팩 사본] {copy.name} 이 지금 팩과 다릅니다 (sha1 {have[:8]} ≠ {sha[:8]}) — 지우고 --write 로 다시 만드세요.')
            return 1
        print(f'[팩 사본] 있음: pack-host/{copy.name} (sha1 {sha})')
        return 0
    if write:
        HOST.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pack, copy)
        print(f'[팩 사본] 만듦: pack-host/{copy.name} (sha1 {sha}) — 배포 가지에 커밋해 올리세요.')
        return 0
    print(f'[팩 사본] 없음: pack-host/{copy.name} (sha1 {sha}) — release 전에 `python3 tools/check_pack_host.py --write` 후 커밋.')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
