"""배포용 WSGI 진입점 (gunicorn wsgi:app).

공개 호스팅을 위한 BYO-key 모드: 서버 기본 키를 두지 않는다.
모든 사용자는 웹의 🔑 설정에서 각자 API 키를 입력해야 하며, 키는
요청 헤더로만 전달되고 서버에 저장되지 않는다. (로컬 개인용은 run.py 사용)
"""

from __future__ import annotations

from pathlib import Path

from danbooru_tags.config import load_config
from danbooru_tags.server import create_app
from danbooru_tags.tagdb import TagDB

_DATA = Path(__file__).resolve().parent / "data" / "danbooru.csv"

cfg = load_config()
db = TagDB(_DATA)
# default_*=None → 서버 기본 키 없음(완전 BYO-key). 공개 노출돼도 주인 토큰 미사용.
app = create_app(cfg, db, default_api_key=None, default_nai_token=None)
