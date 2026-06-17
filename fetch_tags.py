"""Danbooru 태그 사전(CSV) 다운로드.

a1111-sd-webui-tagcomplete 의 danbooru.csv 를 data/danbooru.csv 로 받는다.
포맷: tag,category,post_count,"alias1,alias2,..."
  category: 0=general 1=artist 3=copyright 4=character 5=meta

사용법:
  python fetch_tags.py            # 기본 URL 에서 받기
  python fetch_tags.py <URL>      # 다른 소스 지정
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://raw.githubusercontent.com/DominikDoom/"
    "a1111-sd-webui-tagcomplete/main/tags/danbooru.csv"
)
DEST = Path(__file__).resolve().parent / "data" / "danbooru.csv"


def fetch(url: str = DEFAULT_URL, dest: Path = DEST) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"다운로드 중: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "danbooru-tag-tool"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    dest.write_bytes(data)
    lines = data.count(b"\n")
    print(f"저장 완료: {dest}  ({len(data):,} bytes, ~{lines:,} 태그)")
    return dest


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    try:
        fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"다운로드 실패: {e}", file=sys.stderr)
        sys.exit(1)
