#!/usr/bin/env python3
"""BlockSuseon.rbxl 을 Roblox Open Cloud 로 게시한다.

    python3 tools/publish.py            # 게시(Published)
    python3 tools/publish.py --save     # 저장만(Saved, 라이브 서버에는 안 나감)

API 키는 ROBLOX_API_KEY 환경 변수로 넘긴다 (universe-places:write 권한 필요).
키를 프록시가 넣어 주는 환경에서는 비워 둬도 된다.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

UNIVERSE_ID = os.environ.get("ROBLOX_UNIVERSE_ID", "10768608141")
PLACE_ID = os.environ.get("ROBLOX_PLACE_ID", "71891059039004")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("place", nargs="?", default="BlockSuseon.rbxl")
    parser.add_argument("--save", action="store_true", help="게시하지 않고 저장만 한다")
    args = parser.parse_args()

    with open(args.place, "rb") as f:
        body = f.read()

    version_type = "Saved" if args.save else "Published"
    url = (
        f"https://apis.roblox.com/universes/v1/{UNIVERSE_ID}/places/{PLACE_ID}/versions"
        f"?versionType={version_type}"
    )
    content_type = "application/xml" if args.place.endswith(".rbxlx") else "application/octet-stream"
    headers = {"Content-Type": content_type}
    if os.environ.get("ROBLOX_API_KEY"):
        headers["x-api-key"] = os.environ["ROBLOX_API_KEY"]

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
