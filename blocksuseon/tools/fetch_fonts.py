#!/usr/bin/env python3
"""HUD 비트맵 글꼴에 쓸 글꼴 파일을 받는다.

src/shared, src/client, src/server 의 한글과 기본 ASCII 를 모아 Google Fonts 에서 그 글자만 담긴
woff2 를 받아 art/fonts/ 에 저장하고, 글자 목록을 art/fonts/charset.txt 에 쓴다.

    python3 tools/fetch_fonts.py
"""

import glob
import re
import urllib.parse
import urllib.request

FONTS = {
    # 이름: Google Fonts family 파라미터
    "title": "Song+Myung",
    "body": "Nanum+Myeongjo:wght@800",
}
EXTRA = "0123456789+-−×→/%.,:()[]!?~'\"#_&@= abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ…"
CHUNK = 120
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def charset() -> str:
    chars = set(EXTRA)
    # 서버 알림도 화면에 글자판으로 찍으므로 src/server 의 문구까지 모은다
    paths = glob.glob("src/shared/*.luau") + glob.glob("src/client/*.luau") + glob.glob("src/server/*.luau")
    # 맵 표지판과 NPC 말풍선은 Roblox 글꼴로 찍으므로 글자판에 넣지 않는다
    skip = {"src/server/World.luau", "src/shared/Npcs.luau"}
    for path in [p for p in paths if p not in skip]:
        text = open(path, encoding="utf-8").read()
        # 주석은 빼고 문자열 안의 한글만
        text = re.sub(r"--[^\n]*", "", text)
        for literal in re.findall(r'"([^"\n]*)"', text):
            chars.update(c for c in literal if "가" <= c <= "힣")
    return "".join(sorted(chars))


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main():
    chars = charset()
    open("art/fonts/charset.txt", "w", encoding="utf-8").write(chars)
    for name, family in FONTS.items():
        files = 0
        for start in range(0, len(chars), CHUNK):
            text = urllib.parse.quote(chars[start : start + CHUNK])
            css = fetch(f"https://fonts.googleapis.com/css2?family={family}&text={text}").decode()
            for url in re.findall(r"url\((https://[^)]+)\)", css):
                open(f"art/fonts/{name}_{files}.woff2", "wb").write(fetch(url))
                files += 1
        print(f"{name}: {files}개 파일")
    print(f"글자 {len(chars)}개")


if __name__ == "__main__":
    import os

    os.makedirs("art/fonts", exist_ok=True)
    main()
