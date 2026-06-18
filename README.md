# 장면 → Danbooru 태그 찾기

구상한 장면을 자연어(한국어)로 입력하면, Claude가 장면을 분해해 어울리는
**Danbooru 태그**를 추천하고, 14만 개 실제 태그 사전으로 검증해 *존재하는 정식
태그만* 골라줍니다. AI 일러스트 프롬프트 작성용 로컬 웹앱.

## 동작 방식

1. 장면 설명 입력 → Claude(`claude-opus-4-8`)가 태그 후보 + 등급 추정 생성
2. 후보를 `data/danbooru.csv`(태그·카테고리·post수·별칭)로 검증
   - 별칭은 정식 태그로 치환 (`boobs` → `breasts`)
   - 공백/대소문자 정규화 (`long hair` → `long_hair`)
   - 사전에 없으면 `?`(unverified)로 표시
3. 카테고리별 칩으로 표시 → 클릭해 담고 → 하단에서 복사

동일 장면 응답은 `cache/`에 저장되어 재요청 시 즉시/무료.

## 📖 단부루 사전 (사전 탭)

상단 **📖 사전** 탭은 "원하는 걸 한글로 → 실제 Danbooru 태그"를 찾아주는 사전입니다.

- **AI 의미검색** — 한글 개념·문장(예: `양갈래 머리`, `뒤돌아보는 구도`)을 입력하면
  Claude가 그 뜻을 가진 실제 태그를 **한글 뜻풀이와 함께** 찾아주고, 14만 태그
  사전으로 검증합니다. (`POST /api/dict/search`)
- **직접 조회** — 태그명·별칭에 들어간 글자(예: `twintail`, `school_unif`)로 **즉시**
  검색. CSV 만 쓰므로 **API 키·비용 없이** 동작하고, 인기(post 수)순으로 정렬됩니다.
  (`POST /api/dict/lookup`)
- 각 항목의 **ℹ 뜻** 버튼 → 그 태그의 한글 설명·관련 태그를 불러옵니다
  (`POST /api/dict/explain`).
- **🧺 내 태그함** — 마음에 드는 태그를 담아 한 번에 **복사**하거나
  **스튜디오로 보내기**로 베이스 프롬프트에 추가. 브라우저에 저장됩니다.

## 📱 모바일 설치 (PWA)

설치형 웹앱(PWA)이라 휴대폰 홈 화면에 **앱처럼 설치**할 수 있습니다.

1. `start-phone.bat` 실행 → 서버 + cloudflared 터널이 함께 뜨고 `https://....trycloudflare.com` 주소 발급
2. 폰 브라우저로 그 주소 접속 → 🔑 설정에서 본인 Anthropic 키 입력(직접 조회는 키 없이도 OK)
3. **홈 화면에 추가**(Android Chrome: 메뉴 → 앱 설치 / iOS Safari: 공유 → 홈 화면에 추가)

오프라인에서도 앱 셸이 캐시(`web/sw.js`)되어 열리며, 실행 시 사전 탭으로 시작합니다.

## 설치 & 실행

```bash
pip install -r requirements.txt      # anthropic, flask
python fetch_tags.py                 # 태그 사전 다운로드 (data/danbooru.csv)

# API 키 설정 (둘 중 하나)
set ANTHROPIC_API_KEY=sk-...         # Windows (현재 세션)
#  또는 config.example.json 을 config.json 으로 복사 후 "api_key" 채우기

python run.py                        # http://127.0.0.1:8765 자동 열림
```

`python run.py --port 9000` / `--no-browser` 옵션 지원.

## 설정 (config.json, 선택)

| 키 | 기본값 | 설명 |
|---|---|---|
| `model` | `claude-opus-4-8` | 사용 모델 |
| `max_tokens` | `4000` | 응답 토큰 상한 |
| `max_tags` | `40` | 한 번에 추천받을 최대 태그 수 |
| `host` / `port` | `127.0.0.1` / `8765` | 서버 주소 |
| `api_key` | — | 환경변수 `ANTHROPIC_API_KEY`가 우선 |

## 구조

```
fetch_tags.py        태그 사전 다운로더
run.py               실행 진입점 (사전 로드 → 서버 시작)
danbooru_tags/
  config.py          설정 로딩
  tagdb.py           14만 태그 검증/별칭 해석 + 직접 조회(search)
  client.py          Claude 호출(structured outputs) + 캐시 (suggest/compose/dict_search/explain)
  server.py          Flask API (/api/suggest, /api/dict/*, /api/compose, /api/generate ...)
web/                 UI (index.html / style.css / app.js)
  manifest.webmanifest / sw.js / icon-*.png   PWA(설치형) 자산
tools/make_icons.py  PWA 아이콘 생성기 (Pillow)
data/danbooru.csv    태그 사전
```

## UI 사용 팁

- **등급 필터**: 전체 / Q까지 / S까지 / 일반만 — Claude가 태그별로 추정한 등급으로 즉시 거름
- 칩의 숫자 = post 수(인기도), 점 색 = 등급, `?` = 사전에 없는 태그
- 하단 트레이의 **"공백으로 복사"** 체크 시 `long_hair` → `long hair`로 변환 복사
- 입력창에서 **Ctrl+Enter** 로 바로 검색
