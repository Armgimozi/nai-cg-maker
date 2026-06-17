"""실행 진입점: 태그 사전 로드 → Claude 클라이언트 준비 → 웹 서버 시작.

  python run.py                 # 기본 host/port (config.json 또는 기본값)
  python run.py --port 9000     # 포트 지정
  python run.py --no-browser    # 브라우저 자동 열기 끄기
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

from danbooru_tags.client import SuggestClient
from danbooru_tags.config import load_config, resolve_api_key, resolve_nai_token
from danbooru_tags.nai import NovelAIClient
from danbooru_tags.server import create_app
from danbooru_tags.tagdb import TagDB

# 콘솔 인코딩(cp949 등)에 없는 문자(이모지·em대시 등)로 print 가 죽지 않도록.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

DATA_CSV = Path(__file__).resolve().parent / "data" / "danbooru.csv"


def main() -> int:
    ap = argparse.ArgumentParser(description="Danbooru 태그 추천 도구")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default=None)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--byok", action="store_true",
                    help="서버 기본 키를 쓰지 않고 각 사용자가 웹에서 키 입력(BYO-key)")
    args = ap.parse_args()

    cfg = load_config()
    host = args.host or cfg.get("host", "127.0.0.1")
    port = args.port or cfg.get("port", 8765)

    if not DATA_CSV.is_file():
        print("태그 사전이 없습니다. 먼저 다음을 실행하세요:\n"
              "    python fetch_tags.py", file=sys.stderr)
        return 1

    print(f"태그 사전 로딩 중: {DATA_CSV}")
    db = TagDB(DATA_CSV)
    print(f"  {len(db):,} 개 정식 태그, {len(db.alias):,} 개 별칭 로드됨")

    # 0.0.0.0(외부 노출)이거나 --byok 이면 서버 기본 키를 쓰지 않는다(토큰 보호).
    byok = args.byok or host == "0.0.0.0"
    if byok:
        api_key = nai_token = None
        print("BYO-key 모드: 서버 기본 키 미사용. 각 사용자가 웹 설정에서 키를 "
              "입력해야 하며, 키가 없으면 어떤 토큰도 소모되지 않습니다.")
    else:
        api_key = resolve_api_key(cfg)
        nai_token = resolve_nai_token(cfg)
        print("로컬 모드(127.0.0.1): config.json 의 키를 기본값으로 사용.")

    app = create_app(cfg, db, default_api_key=api_key, default_nai_token=nai_token)
    local_url = f"http://127.0.0.1:{port}/"
    print(f"\n서버 시작 (이 PC): {local_url}   (종료: Ctrl+C)")
    if host == "0.0.0.0":
        ip = _lan_ip()
        if ip:
            print(f"휴대폰/다른 기기 (같은 와이파이): http://{ip}:{port}/")
        print("  ※ 폰에서 안 되면 Windows 방화벽에서 포트 "
              f"{port} 인바운드를 허용해야 합니다.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(local_url)).start()
    app.run(host=host, port=port, debug=False)
    return 0


def _lan_ip() -> str | None:
    """같은 네트워크의 다른 기기가 접속할 PC 의 LAN IP 를 추정."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())
