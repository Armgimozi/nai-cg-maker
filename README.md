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
  tagdb.py           14만 태그 검증/별칭 해석
  client.py          Claude 호출(structured outputs) + 캐시
  server.py          Flask API
web/                 UI (index.html / style.css / app.js)
data/danbooru.csv    태그 사전
```

## UI 사용 팁

- **등급 필터**: 전체 / Q까지 / S까지 / 일반만 — Claude가 태그별로 추정한 등급으로 즉시 거름
- 칩의 숫자 = post 수(인기도), 점 색 = 등급, `?` = 사전에 없는 태그
- 하단 트레이의 **"공백으로 복사"** 체크 시 `long_hair` → `long hair`로 변환 복사
- 입력창에서 **Ctrl+Enter** 로 바로 검색
