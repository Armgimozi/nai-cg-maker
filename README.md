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

## 🎮 UniPlay — 유니티 게임 플레이어 (`/unity/`)

JoiPlay 처럼 **유니티 게임(과 티라노스크립트 비주얼노벨)을 폰에 넣어 두고 실행**하는 설치형 웹앱(PWA)입니다.
같은 서버의 `/unity/` 주소로 열리며(예: `https://<이름>.onrender.com/unity/`), 게임 파일은
서버로 올라가지 않고 **폰 안(브라우저 저장소)에만** 설치되어 오프라인으로도 실행됩니다.
순수 정적 파일(`web/unity/`)이라 GitHub Pages 같은 아무 HTTPS 정적 호스팅에 올려도 동작합니다.

> ⚠️ 실행할 수 있는 것은 **유니티 WebGL(브라우저) 빌드**입니다. PC용(`.exe` + `UnityPlayer.dll`)
> 빌드는 x86 Windows 프로그램이라 폰 브라우저로는 실행할 수 없습니다(JoiPlay 도 미지원).
> 대신 PC 빌드 zip 을 넣으면 **모바일 변환 가능성 진단**을 보여 줍니다(아래).

**PC 게임 → 모바일 변환 진단** (`js/pcbuild.js`, `js/porting.js`) — 파일 앞부분만 읽어
유니티 버전(`globalgamemanagers` 등 SerializedFile 헤더 / `data.unity3d` UnityFS 헤더), 빌드 대상,
스크립트 백엔드(Mono: `Managed/Assembly-CSharp.dll` / IL2CPP: `GameAssembly.dll`+`il2cpp_data`),
실행 파일 CPU(x86/x64/ARM64), 그래픽 API(`BuildSettings.m_GraphicsAPIs` — 모바일에서 쓸 셰이더가 있는지),
HDRP·URP·2D·Steamworks·FMOD·Wwise 등 걸림돌(`ScriptingAssemblies.json`), 네이티브 플러그인을 찾아 경로별 가능성을 매깁니다.
진단 화면에서 **개발자에게 보낼 요청문**(한/영)을 복사할 수 있고, 지금 폰의 GPU(Adreno/Mali/Xclipse)에 맞는
Winlator 드라이버(Turnip/Vortek)를 알려 줍니다. 실제 빌드(Unity 2017.3 Win/Mac/Linux, 2022.3 Mono·IL2CPP)와
Unity 공식 테스트 파일(SerializedFile 형식 9~26)로 검증했습니다.

| 경로 | 언제 되나 | 비고 |
|---|---|---|
| 원본 프로젝트로 다시 빌드 | 개발자(원본 보유) | 가장 확실. WebGL → UniPlay, 또는 Android(IL2CPP·ARM64) |
| Winlator 로 PC판 그대로 | Windows 빌드, 안드로이드 | 변환 아님. 스냅드래곤(Adreno+Turnip)이 유리, 실행 인수 `-force-gfx-direct` |
| AssetRipper 디컴파일 → 재빌드 | **Mono** 빌드만 | 컴파일 오류·더미 셰이더를 손으로 고치는 수작업. 작은 2D·기본 파이프라인일수록 유리 |
| 데이터만 안드로이드 플레이어에 이식 | 사실상 불가 | D3D 전용 셰이더(분홍 화면), 안드로이드 Mono 는 32비트 전용, 정확한 버전 일치 필요 |

IL2CPP 빌드는 코드가 PC용 기계어(네이티브 코드)라 디컴파일로 복원되지 않습니다. 남의 게임을 변환해 배포하는 것은
저작권 침해이므로 개인적으로만 다루고, 가능하면 개발자에게 공식 WebGL/모바일 빌드를 요청하세요.

**게임 넣기** — WebGL 빌드 폴더(`index.html` + `Build/`)를 zip 으로 압축 → ＋ 게임 추가.
- Unity 5.6~2019(`UnityLoader.js`) / 2020~Unity 6(`*.loader.js`) 자동 판별
- `.gz`/`.br` 압축 빌드는 설치할 때 미리 풀어 둠(서버 `Content-Encoding` 설정 불필요)
- `index.html` 없이 `Build/` 만 있어도 실행 페이지를 만들어 줌
- 폴더째/여러 파일 선택, ZIP64, 한글(CP949)·일본어 파일명 zip 지원
- 덤으로 RPG Maker MV/MZ·일반 HTML5 게임도 실행을 시도

**티라노스크립트(TyranoScript · TyranoBuilder) 비주얼노벨** — 엔진이 원래 HTML5(jQuery)라
브라우저판은 물론 **PC판(.exe)도 안의 게임을 꺼내 그대로 실행**합니다(에뮬레이션 아님).
- 판별: `index.html` 옆의 `tyrano/tyrano.js`(또는 `libs.js`) + `data/system/Config.tjs`. 제목은 `Config.tjs` 의
  `;System.title`, 엔진 버전은 `readme.txt`, 세로 게임(`scHeight > scWidth`)은 세로 고정
- PC판 포장 풀기 (`js/asar.js`, `js/zip.js`): Electron `resources/app.asar`(+`app.asar.unpacked`)·`resources/app/`,
  NW.js `package.nw`/`app.nw`(zip), `copy /b nw.exe+app.nw 게임.exe` 처럼 **exe 뒤에 붙은 zip**, 맥 `.app/Contents/Resources/`.
  게임 폴더 zip 이 가장 확실하고, `app.asar`·`게임.exe`·`package.nw` 파일 하나만 골라도 됩니다
- 브라우저에서 깨지는 PC판 설정을 설치할 때 고침(`Config.tjs`): `configSave = file`(Node.js 파일 세이브 → 시작도 못 함)
  → `webstorage`, `ScreenRatio = default`(폰에서 화면 잘림) → `fix`, PNG 원본 크기 세이브 썸네일 → JPEG·가로 480px 이하
- **PC판 세이브 이어하기**: exe 옆의 `<projectID>_tyrano_data.sav`·`_sf.sav` 는 브라우저판 저장 값과 같은 형식이라
  게임 폴더째 넣으면 자동으로, 나중에는 세이브 메뉴의 '백업 파일에서 복원'으로 넣을 수 있음
- 실행 중 보정(`inject.js`): 첫 BGM 이 탭을 기다리며 멈춰 보일 때 "탭하면 시작" 안내, 아이폰이 `.ogg` 대신 찾는
  `.m4a` 가 없으면 서비스워커가 다른 형식으로 대신 응답, 재생 못 하는 동영상(.ogv 등)은 건너뜀, 게임의 '종료' 버튼 →
  라이브러리, "페이지를 나갈까요?" 확인창 끄기, 회전 뒤 화면 크기 다시 맞춤, 가상 게임패드(`useGamepad`) 인식
- 못 하는 것: Node.js·Steam 을 직접 부르는 플러그인(가져올 때 경고), Enigma Virtual Box 로 묶은 exe, 보호(변형)된 asar

**플레이 중** (왼쪽 위 ≡ 또는 뒤로 가기 → 메뉴)
- **가상 패드**: 프리셋(RPG · 액션 · 방향키 · 게임패드 · 비주얼노벨 · 티라노스크립트 · 마우스 보조) 또는 직접 편집
  (끌어서 배치, 버튼마다 키보드 키 / 키 조합 / 게임패드 버튼 / 아날로그 스틱 / 마우스 클릭·휠 지정)
- **터치 방식**: 터치 그대로 · 터치→마우스(길게=우클릭, 두 손가락=스크롤) · 터치패드(커서)
- 해상도 배율(0.5배~기기 최대), 화면 맞춤(비율 유지/꽉 채우기), 가로·세로 고정, 전체화면,
  화면 꺼짐 방지, FPS 표시, 글자 입력창, 스크린샷/표지, 오류 로그
- 블루투스 키보드·게임패드는 그대로 동작

**세이브** — 유니티 세이브(`/idbfs`)와 게임별로 분리된 localStorage 를 파일로 **백업/복원**.
localStorage 는 이 사이트의 모든 게임이 함께 쓰는 약 5MB 라, 가득 차서 세이브가 실패하면(티라노스크립트는 실패를
알리지 않음) 플레이 화면이 대신 알려 줍니다.

**구조** (`web/unity/`)
```
index.html / play.html     라이브러리 / 플레이 화면
sw.js                      서비스워커: games/<id>/… 를 기기 캐시에서 응답 + inject.js 주입
inject.js                  게임 iframe 안에서 먼저 실행(해상도·입력 주입·가상 패드·세이브 경로·유니티 캐시 끄기)
js/zip.js · asar.js        스트리밍 zip 리더(DecompressionStream, 앞에 exe 가 붙은 zip 포함) · Electron asar 리더
js/importer.js             빌드 판별·설치 · js/db.js 저장소 · js/saves.js 세이브 백업
js/pcbuild.js · porting.js PC 빌드 진단(유니티 버전·Mono/IL2CPP·걸림돌) · 진단 화면
js/player.js · controls.js · keys.js   플레이 화면 · 가상 패드 · 키/프리셋
vendor/brotli-decode.js    Google Brotli 디코더(MIT) — .br 빌드용
```
아이콘은 `python tools/make_unity_icons.py` 로 다시 만들 수 있습니다.

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
