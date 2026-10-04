#!/usr/bin/env python3
"""BlockSuseon.rbxl 을 Roblox Open Cloud 로 게시한다.

    python3 tools/publish.py            # 게시(Published)
    python3 tools/publish.py --save     # 저장만(Saved, 라이브 서버에는 안 나감)
    python3 tools/publish.py --no-wait  # 그림 검수를 기다리지 않고 게시

게시하기 전에 src/client/Art.luau 가 쓰는 그림(글자판 등)이 모두 Roblox 검수를 통과(Approved)했는지 본다.
검수 중인 그림은 게임에서 빈칸으로 보이므로, 다 통과할 때까지 기다렸다가 게시한다 (거절되면 멈춘다).

API 키는 ROBLOX_API_KEY 환경 변수로 넘긴다 (universe-places:write 권한 필요).
키를 프록시가 넣어 주는 환경에서는 비워 둬도 된다.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

UNIVERSE_ID = os.environ.get("ROBLOX_UNIVERSE_ID", "10768608141")
PLACE_ID = os.environ.get("ROBLOX_PLACE_ID", "71891059039004")


ART = "src/client/Art.luau"
WAIT_SECONDS = 20 * 60


def auth_headers(extra=None):
    headers = dict(extra or {})
    if os.environ.get("ROBLOX_API_KEY"):
        headers["x-api-key"] = os.environ["ROBLOX_API_KEY"]
    return headers


def moderation_state(asset_id: str) -> str:
    request = urllib.request.Request(f"https://apis.roblox.com/assets/v1/assets/{asset_id}", headers=auth_headers())
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    return (data.get("moderationResult") or {}).get("moderationState") or "Unknown"


# Art.luau 의 그림이 모두 검수를 통과할 때까지 기다린다. 통과하면 True
def wait_for_art() -> bool:
    if not os.path.exists(ART):
        return True
    ids = sorted(set(re.findall(r"rbxassetid://(\d+)", open(ART, encoding="utf-8").read())))
    pending = set(ids)
    deadline = time.time() + WAIT_SECONDS
    while True:
        for asset_id in sorted(pending):
            try:
                state = moderation_state(asset_id)
            except urllib.error.HTTPError as error:
                print(f"  그림 {asset_id} 상태를 못 읽었다 ({error.code}). 다시 본다", file=sys.stderr)
                continue
            if state == "Approved":
                pending.discard(asset_id)
            elif state == "Rejected":
                print(f"그림 {asset_id} 이(가) 검수에서 거절됐다. 게시하지 않는다.", file=sys.stderr)
                return False
        if not pending:
            print(f"그림 {len(ids)}장 모두 검수 통과")
            return True
        if time.time() > deadline:
            print(f"그림 {len(pending)}장이 {WAIT_SECONDS // 60}분 넘게 검수 중이다: {', '.join(sorted(pending))}", file=sys.stderr)
            return False
        print(f"  그림 {len(pending)}장 검수 중… 20초 뒤 다시 본다")
        time.sleep(20)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("place", nargs="?", default="BlockSuseon.rbxl")
    parser.add_argument("--save", action="store_true", help="게시하지 않고 저장만 한다")
    parser.add_argument("--no-wait", action="store_true", help="그림 검수를 기다리지 않는다")
    args = parser.parse_args()

    if not args.save and not args.no_wait and not wait_for_art():
        return 1

    with open(args.place, "rb") as f:
        body = f.read()

    version_type = "Saved" if args.save else "Published"
    url = (
        f"https://apis.roblox.com/universes/v1/{UNIVERSE_ID}/places/{PLACE_ID}/versions"
        f"?versionType={version_type}"
    )
    content_type = "application/xml" if args.place.endswith(".rbxlx") else "application/octet-stream"
    headers = auth_headers({"Content-Type": content_type})

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print(f"게시 실패 {error.code}: {error.read().decode(errors='replace')}", file=sys.stderr)
        return 1

    print(f"{version_type} · 플레이스 {PLACE_ID} · 버전 {result.get('versionNumber')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
