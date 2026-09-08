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

## 📱 모바일 설치 (PWA)

설치형 웹앱(PWA)이라 휴대폰 홈 화면에 **앱처럼 설치**할 수 있습니다.

1. `start-phone.bat` 실행 → 서버 + cloudflared 터널이 함께 뜨고 `https://....trycloudflare.com` 주소 발급
2. 폰 브라우저로 그 주소 접속 → 🔑 설정에서 본인 Anthropic 키 입력(직접 조회는 키 없이도 OK)
3. **홈 화면에 추가**(Android Chrome: 메뉴 → 앱 설치 / iOS Safari: 공유 → 홈 화면에 추가)

오프라인에서도 앱 셸이 캐시(`web/sw.js`)되어 열리며, 실행 시 사전 탭으로 시작합니다.

## 🎀 별빛 소녀 컬렉션 (게임 · `/game`)

같은 서버에 붙어 있는 **미소녀 수집형 가챠 게임**입니다. 서버를 띄운 뒤
`http://127.0.0.1:8765/game` 으로 접속하면 바로 플레이할 수 있고, 폰에서
**홈 화면에 추가**하면 앱처럼 실행됩니다.

- **캐릭터 24명** — 5★ 6 / 4★ 8 / 3★ 10, 5속성(화염·질풍·해류·광휘·심연) 상성
- **소환** — 픽업 한정 배너 2종 + 상시 배너. 소프트 천장(74회~) · 하드 천장(90회) ·
  4★ 10회 보장 · 5★ 픽업 50/50 후 다음 확정
- **확률 공시** — 기본 확률과 **종합 확률(천장 반영)** 을 게임 안에 항상 표시.
  `python tools/verify_rates.py` 로 공시값이 실제 구현과 맞는지 검증합니다
  (게임산업법상 공시값은 실제 적용값과 같아야 합니다)
- **전투** — 4장 24스테이지 자동 전투. 속도순 행동 · 기력 100에 스킬 · 속성 상성
- **육성** — 레벨업(골드), 중복 획득 시 성흔 최대 5단계, 초과분은 조각으로 환원
- **상점(모의 결제)** — 별정수 패키지 6종 · 첫 구매 2배 · 달빛 통행증 · 스태미나 충전.
  **실제 결제는 연결되어 있지 않습니다.**

### 캐릭터 아트 생성

아트가 없으면 캐릭터 팔레트로 만든 SVG 플레이스홀더가 나오므로, 아트 없이도
게임은 정상 동작합니다. 실제 아트를 뽑으려면:

```bash
set NAI_API_TOKEN=...                       # 또는 config.json 의 nai_token
python tools/generate_art.py                # 기본 그림 24장 → web/game/art/<id>.png
python tools/generate_art.py --only seraphine kaguya
python tools/generate_art.py --force        # 전부 다시

# 눈 깜빡임용 표정 차분 (기본 그림을 뽑은 뒤에)
python tools/generate_art.py --expressions --variants blink
python tools/generate_art.py --expressions  # blink · smile · blush 전부
```

파일을 넣기만 하면 플레이스홀더가 자동으로 교체됩니다. 서버 재시작도 필요 없습니다.

**표정 차분**은 기본 그림과 **같은 시드**로 프롬프트에 표정 태그(`closed eyes`
등)만 덧붙여 재생성합니다. 같은 시드면 구도·인물이 그대로 유지되고 표정만
바뀌므로, 얼굴을 마스킹해 인페인트하는 것보다 안정적입니다. 기본 그림의 시드는
`web/game/art/manifest.json` 에 기록되어 차분 생성 때 재사용됩니다.

저장 전에 **메타데이터를 제거**합니다. PNG 텍스트 청크(프롬프트·시드·
`Software: NovelAI`)를 지우고, 알파 채널을 버려 **LSB 스텔스 워터마크**까지
없앱니다. 원본 그대로 두려면 `--keep-metadata`. 메타데이터 제거가 이용약관·
저작권 문제를 해결해주지는 않으므로, 상업 배포 계획이라면 NovelAI 구독 약관을
먼저 확인하세요. 프롬프트에 `artist:` 태그를 넣지 않은 것도 같은 이유입니다.

### 캐릭터를 움직이게 하는 법

정지 그림 한 장으로도 살아있어 보이게 하는 장치가 클라이언트에 들어 있습니다.

| 장치 | 내용 | 필요한 것 |
|---|---|---|
| **호흡** | 4.4초 주기로 아주 미세하게 확대·상하 이동 | 없음 (즉시 동작) |
| **패럴랙스** | 폰 자이로·PC 마우스에 따라 그림이 기울어짐 | 없음 |
| **눈 깜빡임** | 기본/눈 감은 그림을 교차. 3~4초에 한 번, 가끔 연속 두 번 | `<id>@blink` 차분 |
| **5★ 연출** | 화면 섬광 + 카드 위로 빛이 스치고 링이 퍼짐 | 없음 |
| **전투 연출** | 공격자 돌진, 스킬 시전 발광, 피격 흔들림 | 없음 |

`prefers-reduced-motion` 을 켠 기기에서는 호흡·패럴랙스가 자동으로 꺼집니다.

더 나아가려면 (매출이 나온 뒤 권장):
- **누끼 분리** — 배경/캐릭터를 분리해 진짜 깊이 패럴랙스를 줍니다.
- **Live2D** — 부위별 리깅. 상용 가챠의 정석이지만 캐릭터당 외주 비용이 듭니다.
  5★ 캐릭터부터 적용하는 것이 일반적입니다.

실제 아트를 넣은 뒤 배너·홈에서 얼굴이 잘리면, `web/game/game.css` 의
`.hero-art .portrait` / `.banner .bg .portrait` 의 `object-position` 값만
조정하면 됩니다(작을수록 그림 위쪽을 보여줍니다).

### 구글 플레이 출시로 가는 길

웹 게임 그대로 **TWA(Trusted Web Activity)** 로 감싸면 안드로이드 앱이 됩니다
(`bubblewrap init --manifest https://<도메인>/game/manifest.webmanifest`).
출시 전에 반드시 처리해야 하는 것:

1. **결제** — 디지털 재화는 Google Play 결제(수수료 15~30%)를 써야 합니다.
   `POST /api/game/shop/buy` 의 모의 지급을 **영수증 검증 후 지급**으로 교체하세요.
   지금 코드에서 결제가 닿는 곳은 이 엔드포인트 하나뿐입니다.
2. **계정** — 지금은 브라우저에 저장된 익명 토큰(`pid`)이라 기기를 바꾸면 사라집니다.
   정식 인증(구글 로그인 등)을 붙이세요.
3. **등급분류** — 구글플레이가 자체등급분류사업자라 스토어 내에서 처리됩니다.
4. **확률 공시** — 게임 안 + 광고물에 확률을 표시해야 합니다(이미 구현).

### 게임 구조

```
gacha/
  content.py   캐릭터 24명(능력치·스킬·NAI 프롬프트·팔레트)
  econ.py      재화·확률·배너·상점·스테이지·미션 (밸런스 단일 출처)
  rng.py       뽑기 판정(천장·보장·픽업)
  battle.py    자동 전투 시뮬레이션
  state.py     플레이어 상태(SQLite, data/gacha.db)
  server.py    게임 API 블루프린트 (/game, /api/game/*)
  art.py       아트 자산 해석 + 프롬프트 조립
web/game/      게임 클라이언트 (index.html / game.css / game.js / art/)
tools/generate_art.py   NAI 아트 일괄 생성(메타데이터 제거 포함)
tools/verify_rates.py   확률 공시값 검증
```

뽑기 결과·전투 승패·재화 증감은 **전부 서버에서만** 계산합니다. 클라이언트는
무엇을 하고 싶은지만 보내고 결과를 받습니다.

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

## 구조

```
fetch_tags.py        태그 사전 다운로더
run.py               실행 진입점 (사전 로드 → 서버 시작)
danbooru_tags/
  config.py          설정 로딩
  tagdb.py           14만 태그 검증/별칭 해석 + 직접 조회(search)
  client.py          Claude 호출(structured outputs) + 캐시 (suggest/compose/dict_search/explain)
  server.py          Flask API (/api/suggest, /api/dict/*, /api/style/artists, /api/compose, /api/generate ...)
  nai.py             NovelAI 생성/인페인트 (v4.5 · V5)
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
