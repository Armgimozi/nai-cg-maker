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

## 🖌 그림체 실험실 (그림체 탭)

**작가 태그를 랜덤으로 조합해 시드를 고정한 채 실제로 생성**해서, 내 취향의
NAI V5 그림체를 찾아내는 탭입니다.

1. **작가 태그 풀** — 직접 붙여넣거나, 아래 **작가 검색**(사전의 `artist`
   카테고리만 · 키·비용 없음 · `POST /api/style/artists`)에서 눌러 담습니다.
   `인기 작가 60 불러오기`로 post 수 상위 작가를 바로 채울 수도 있습니다.
2. **조합 규칙** — 조합당 작가 수(예: 2~3명), 만들 조합 수, 그리고 두 개의 시드
   - **조합 시드**: 같은 값이면 항상 **같은 조합**이 나옵니다(재현 가능).
   - **이미지 시드**: `모든 조합에 같은 시드 고정`을 켜면 전 조합이 이 시드로
     생성돼 **구도·인물이 같고 그림체만** 달라집니다 → 비교가 쉬움.
   - `artist:` 접두사, **가중치 랜덤**(`1.15::artist:wlop::` 형식) 토글 지원.
   - 같은 작가 조합은 중복 없이 뽑습니다.
3. **🎲 조합 미리보기** 로 Anlas 를 쓰기 전에 조합을 눈으로 확인 →
   **그림체 생성** 이 큐에 넣어 순서대로 실제 생성(`POST /api/generate`).
4. 결과 카드에서 **스튜디오에 적용**(베이스 프롬프트 맨 앞에 작가 토큰 삽입 ·
   기존 작가 토큰은 자동 제거), **복사**, **☆ 저장**(마음에 든 조합은 텍스트로
   브라우저에 보관), **🔁 다른 시드**로 같은 조합 재생성, 이미지를 누르면
   스튜디오 작업영역으로 보내 그대로 인페인트할 수 있습니다.

모델·해상도·스텝 등은 상단 **⚙ 설정**(그림체·스튜디오 공용)을 따릅니다.

## 📚 위키 (위키 탭) — 사람도 AI 도 읽는 설정 노트

캐릭터 외형·작품 세계관·자주 쓰는 프롬프트 조각을 **마크다운 문서**로 정리하는 탭입니다.
문서는 서버의 `wiki/<이름>.md` 파일로 저장되므로 git 으로 버전 관리하거나 에디터/AI 가
파일을 직접 고쳐도 서버 재시작 없이 바로 반영됩니다.

- **문서 작성** — 제목·이름(slug)·태그·본문(마크다운). `[[다른문서]]` 로 문서끼리 연결.
  목록은 제목·태그·본문 키워드로 **검색**되고, **백업/복원**(JSON)으로 옮길 수 있습니다.
- **앱 안의 Claude 가 읽기** — 🎨 스튜디오의 **위키 참조**에서 문서를 고르면
  *이 장면의 태그 찾기*·*장면에 맞춰 재구성*·*연속 시퀀스* 요청에 그 문서가 맥락으로
  붙습니다(`wiki_pages: [slug, …]`). 캐릭터 설정을 한 번 적어 두면 매번 붙여넣지 않아도 됩니다.
- **외부 AI 가 읽기** — 모든 문서는 **API 키 없이** 평문으로 열립니다.

  | 주소 | 내용 |
  |---|---|
  | `GET /llms.txt` | 문서 목차 + 읽는 법 ([llms.txt 관례](https://llmstxt.org)) |
  | `GET /llms-full.txt` | 전체 문서를 한 파일로 |
  | `GET /wiki/<slug>.md` | 문서 1개 원문(text/markdown) |
  | `GET /api/wiki` · `GET /api/wiki/<slug>` | 목록 / 문서 1개 (JSON) |
  | `GET /api/wiki/search?q=키워드` | 검색 (JSON) |
  | `PUT /api/wiki/<slug>` `{title, content, tags}` · `DELETE /api/wiki/<slug>` | 쓰기 / 삭제 |
  | `GET /api/wiki/export` · `POST /api/wiki/import` | 백업 / 복원 |

  예: Claude Code 나 챗봇에 *"`https://<주소>/llms-full.txt` 를 읽고 세라의 외형을 요약해줘"*.
  저장소를 직접 여는 에이전트는 `wiki/*.md` 를 그대로 읽으면 됩니다.
- **편집 보호(선택)** — 서버에 환경변수 `WIKI_TOKEN`(또는 config `wiki_token`)을 두면
  쓰기/삭제/복원에 `X-Wiki-Token` 헤더가 필요합니다(읽기는 항상 공개). 앱에서는 🔑 API 키
  칸의 *위키 편집 토큰*에 입력합니다. 공개 배포라면 꼭 설정하세요.
- 위키 폴더는 환경변수 `WIKI_DIR` 또는 config `wiki_dir` 로 바꿀 수 있습니다.
  Render 같은 무료 호스팅은 재배포 때 디스크가 초기화되므로 문서를 **git 에 커밋**하거나
  주기적으로 **백업**하세요.

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
| `nai_model` | `nai-diffusion-5-full` | NovelAI 이미지 모델. V5(`nai-diffusion-5-*`)는 `params_version: 4`로 자동 전송되며, UI ⚙ 설정에서 v4.5 나 **직접 입력**한 모델 ID 로 바꿀 수 있습니다 |
| `nai_token` | — | 환경변수 `NAI_API_TOKEN`이 우선 |
| `wiki_dir` | `wiki/` | 위키 문서 폴더. 환경변수 `WIKI_DIR`이 우선 |
| `wiki_token` | — | 위키 편집 토큰(비우면 누구나 편집). 환경변수 `WIKI_TOKEN`이 우선 |

## 구조

```
fetch_tags.py        태그 사전 다운로더
run.py               실행 진입점 (사전 로드 → 서버 시작)
danbooru_tags/
  config.py          설정 로딩
  tagdb.py           14만 태그 검증/별칭 해석 + 직접 조회(search)
  client.py          Claude 호출(structured outputs) + 캐시 (suggest/compose/dict_search/explain)
  server.py          Flask API (/api/suggest, /api/dict/*, /api/style/artists, /api/compose, /api/generate, /api/wiki/* ...)
  nai.py             NovelAI 생성/인페인트 (v4.5 · V5)
  wiki.py            위키 저장소 (wiki/*.md 읽기·쓰기·검색 · llms.txt · AI 맥락 조립)
web/                 UI (index.html / style.css / app.js)
  manifest.webmanifest / sw.js / icon-*.png   PWA(설치형) 자산
tools/make_icons.py  PWA 아이콘 생성기 (Pillow)
data/danbooru.csv    태그 사전
wiki/*.md            위키 문서 (사람·AI 공용 · git 에 커밋 가능)
```

## UI 사용 팁

- **등급 필터**: 전체 / Q까지 / S까지 / 일반만 — Claude가 태그별로 추정한 등급으로 즉시 거름
- 칩의 숫자 = post 수(인기도), 점 색 = 등급, `?` = 사전에 없는 태그
- 하단 트레이의 **"공백으로 복사"** 체크 시 `long_hair` → `long hair`로 변환 복사
- 입력창에서 **Ctrl+Enter** 로 바로 검색
