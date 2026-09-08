"""별빛 소녀 컬렉션 — 미소녀 수집형 가챠 게임.

기존 NovelAI 태그 도구(danbooru_tags)와 같은 Flask 앱에 블루프린트로 붙는다.
  /game            게임 클라이언트
  /api/game/*      게임 API (서버 권위 · SQLite 저장)

`gacha.server` 는 Flask 를 필요로 하므로 여기서 미리 import 하지 않는다.
확률 검증 스크립트 같은 도구가 Flask 없이도 gacha.econ/rng 를 쓸 수 있게 한다.
"""
