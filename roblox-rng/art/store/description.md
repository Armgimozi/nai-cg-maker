# 스토어 설명 (LANDMARK RNG!)

붙여 넣을 글은 [`description.txt`](description.txt)에 있습니다. 그 파일 전체를 Creator Hub 의
**설명(Description)** 칸에 그대로 붙여 넣으면 됩니다(Open Cloud 로 넣는 방법은 아래 "API 로 넣기").

- 형식: 이모지로 감싼 환영 줄 한 개, 그 아래 이모지로 시작하는 짧은 줄들(인기 RNG 게임 스토어 페이지와 같은 모양).
  내용은 모두 이 게임 것입니다(다른 게임 이름은 쓰지 않음).
- **한국어만** 씁니다. 소스 언어가 한국어이고 로컬라이제이션의 "체험 정보" 자동 번역이 켜져 있어서, 다른 언어 사용자에게는 로블록스가 번역해 보여 줍니다.
- 길이: 431자(UTF-16 442단위) — 로블록스 설명 한도 1000자보다 짧습니다.
- 스토어 그림(아이콘·썸네일)에는 한글이 없습니다(영어·숫자만 — 그림 속 글자는 자동 번역되지 않음).

## 붙여 넣을 글

한국어만(소스 언어 = 한국어). 영어·독일어·중국어 등은 로블록스 자동 번역(로컬라이제이션 → 체험 정보: 켜기)이 맡음.

```
🌍 LANDMARK RNG!에 오신 것을 환영합니다! 🌍

🎲 지구본을 돌려 전 세계 명소 150곳을 모으세요 (실제 명소부터 전설까지)
🌈 7개 등급! 1/2부터 전설의 세계수 1/10,000,000,000까지
🔁 환생할 때마다 행운 2배, 최대 ×1,024!
⭐ 같은 명소를 또 찾으면 별 +1 (최대 ★5), 별마다 수입 +30%
📰 1/100,000,000 이상은 서버 전체 뉴스 속보, 1/375,000,000 이상은 하늘에 거대 홀로그램!
🛂 대륙별 도장을 모을 때마다 영구 행운 +25%
🏝️ 관광 공원 타이쿤: 명소를 3D로 전시하고 코인을 벌어요
⚡ AUTO 굴림 지원, 빠른 굴림 패스로 더 빠르게
🛒 상점: 행운 VIP · 빠른 굴림 · 수입 2배 · 15분 행운 부스트
👥 서버당 최대 8명

🆕 업데이트는 계속됩니다! 좋아요·즐겨찾기 눌러 주세요!
```

## 코드와 맞춰 본 내용

| 설명 줄 | 코드 근거 |
|---|---|
| 명소 150곳, 실제 명소부터 전설까지 | `Landmarks.luau` DEFINITIONS 150줄(아시아 37, 유럽 36, 아메리카 32, 아프리카 25, 오세아니아 20). 세계수·샹그릴라·용궁·무 대륙·아틀란티스처럼 전설 속 장소가 섞여 있어 "real wonders to lost legends" |
| 7개 등급, 1/2 ~ 1/10,000,000,000 | `Landmarks.Tiers` 7개(일반 명소 ~ 전설). 가장 흔한 홍콩 시계탑 `OneIn = 2`, 가장 희귀한 세계수 `OneIn = 10000000000`(게임 표기 `Format.oneIn` = "1 in 10,000,000,000") |
| 환생할 때마다 행운 2배, 최대 ×1,024 | `REBIRTH_LUCK_MULT = 2`, `MAX_REBIRTHS = 10` → 행운 × 2^환생 수, 10번 = ×1,024(`PlayerState.rebirthLuckMult`). 환생 수입 +50%/회(`REBIRTH_INCOME_BONUS`)는 줄 길이 때문에 뺌 |
| 중복이면 별 +1(최대 ★5), 별마다(each) 수입 +30% | `STAR_THRESHOLDS = {2,3,4,5,6}`(처음 발견 ☆0, 2번째 ★1 … 6번째 ★5), `STAR_INCOME_BONUS = 0.3`(`PlayerState.landmarkIncome` = 등급 수입 × (1 + 0.3 × 별)) |
| 1/100,000,000 이상 희귀 → 서버 뉴스 속보, 1/375,000,000 이상 → 거대 홀로그램 | 서버 `landmark.OneIn >= Config.ANNOUNCE_ONE_IN(100000000)` 이면 그 서버 전체 알림(사하라 신기루 성 1/110,000,000 · 샹그릴라 · 세계수), `>= HOLOGRAM_ONE_IN(375000000)` 이면 광장 하늘 홀로그램까지(샹그릴라 · 세계수 — 커밋 e8851d0 사용자 결정 D안). `>=` 라서 경계 숫자 자체도 들어감 → "or rarer / 이상 희귀" |
| 대륙 여권 도장마다 영구 행운 +25% | `REGION_LUCK_BONUS = 0.25`, 행운 × (1 + 0.25 × 도장 수). 도장 = 한 대륙의 불가사의 등급까지(`STAMP_MAX_RANK = 5`) 역대 발견 기록으로 모두 찾음 → 환생해도 안 사라짐("forever") |
| 관광 공원 타이쿤, 3D 전시, 코인 | 전시 명소가 초당 관광 수입(`Config.TIER_INCOME`), `ParkEdit.luau` 3D 배치 모드. "tycoon/타이쿤"은 검색어로 넣은 장르 말 |
| AUTO 굴림, 빠른 굴림 패스로 더 빠르게 | AUTO 는 굴림 간격(`ROLL_COOLDOWN = 1.2`초)대로 굴림(이미 발견한 명소는 짧은 연출 `AUTO_QUICK_REVEAL`). 빠른 굴림 `CooldownMult = 0.7` → 후반 시간당 3,000 → 4,286번(×1.43). 여행사 업그레이드도 간격 -5%/레벨 |
| 상점: 행운 VIP · 빠른 굴림 · 수입 2배 · 15분 행운 부스트 | `Config.GamePasses`: 행운 VIP(행운 ×2), 빠른 굴림, 수입 2배. `Config.Products`: 행운 부스트·서버 행운(900초 ×2, 개인 / 서버 전체). 코인 팩은 줄 길이 때문에 뺌. 영어 이름은 번역(게임 안 이름은 한국어) |
| 업데이트 줄 | 버전 번호 없음(게시할 때마다 고칠 필요 없음). 좋아요·즐겨찾기 부탁은 로블록스 스토어에서 흔한 문구 |

### 일부러 바꾼 표현

- 확률은 게임 화면처럼 콤마를 넣은 자연수(1/10,000,000,000). "10B"처럼 줄이지 않음.
- 여권 도장은 "대륙을 다 모으면"이라고 쓰지 않았습니다(도장 조건은 불가사의 등급까지라 전설급은 빠짐).
- "서버 뉴스"는 같은 서버 안 전체 알림입니다(다른 서버로는 가지 않음 — MessagingService 안 씀). 그래서 "global"이 아니라 "server".
- 예전 설명의 "서버당 최대 8명" 줄은 한도 때문에 뺐습니다. 플레이스 설정 Max Players 는 여전히 8(광장 둘레 공원 부지 8칸)로 두세요.

## 게시 전 확인

- [ ] 붙여 넣은 뒤 스토어 페이지에서 숫자나 글자가 `###`으로 가려지지 않았는지(로블록스 글 필터).
- [ ] 게임패스 이름이 Creator Hub 에 한국어로 되어 있어도 괜찮습니다(설명은 뜻을 영어로 옮김). 영어 이름으로 바꾸고 싶으면 게임패스 번역(Localization)에서.
- [ ] 플레이스 설정 **Max Players = 8**.
- [ ] 게임 안 화면 글자는 한국어뿐입니다. 영어를 먼저 쓴 스토어라 영어권 플레이어가 들어올 수 있으니, 나중에 영어 번역(Localization 표)을 넣는 것을 고려하세요.

## API 로 넣기 (Open Cloud) — 2026-09-30 문서 기준, 호출은 하지 않았음

| 무엇 | 방법 | 권한(scope) |
|---|---|---|
| **설명(원래 언어)** | `PATCH https://apis.roblox.com/cloud/v2/universes/{universeId}/places/{rootPlaceId}?updateMask=description` 본문 `{"description": "<description.txt 내용>"}` — 유니버스 설명은 시작 플레이스(root place) 설명을 따라감(Universe 의 `description` 은 읽기 전용) | `universe.place:write` (API 키 `x-api-key` 또는 OAuth 2.0) |
| 이름·설명 번역(다른 언어) | `PATCH https://apis.roblox.com/legacy-game-internationalization/v1/name-description/games/{universeId}` 본문 `{"data":[{"name":..,"description":..,"languageCode":"en"}]}` — 원래 언어는 안 됨(오류 26) | `legacy-universe:manage` (EXPERIMENTAL) |
| **아이콘(원래 언어)** | API 키로 되는 엔드포인트 없음 → **Creator Hub** (Experience → Places/Basic Info → Icon) | — |
| **썸네일(원래 언어)** | `POST https://publish.roblox.com/v1/games/{universeId}/thumbnail/image` 는 쿠키(.ROBLOSECURITY) 전용 legacy API → **Creator Hub** 에서 올림(순서 thumb_1 → 5) | 쿠키만 |
| 아이콘·썸네일 번역(다른 언어) | `POST https://apis.roblox.com/legacy-game-internationalization/v1/game-icon/games/{universeId}/language-codes/{lang}`, `.../game-thumbnails/games/{universeId}/language-codes/{lang}/image`, 순서 `.../images/order` — 원래 언어는 안 됨(오류 26) | `legacy-universe:manage` (EXPERIMENTAL) |

## 검색 키워드

지금 로블록스에는 태그 칸이 없어 **게임 이름과 설명 글**이 검색에 쓰입니다. 설명에 들어 있는 말:
RNG(이름), landmarks, globe, legends, rebirth, luck, tycoon, park, hologram / 명소, 지구본, 전설, 환생, 행운, 타이쿤, 공원.

## 추천 장르

- **시뮬레이션(Simulation)**
  - 하위 장르 1순위: **Incremental Simulator**. 굴리기·수집·환생이 이어지는 RNG 게임이 주로 여기에 들어갑니다.
  - 2순위: **Tycoon**. 공원 전시·관광 수입 쪽을 앞세우고 싶을 때.
- 하위 장르 이름은 Creator Hub 드롭다운에 보이는 이름을 기준으로 골라 주세요(목록은 가끔 바뀜).

## 참고

- 언어별 설명을 따로 넣을 수도 있습니다(Localization). 나누려면 `🇰🇷 한국어` 줄 위(영어)와 아래(한국어)를 잘라 각 언어 칸에 넣으면 됩니다.
- 이모지는 스토어 페이지에서만 씁니다. 게임 안 UI 에는 쓰지 않습니다.
- 그림: `art/store/icon.png`(512), `thumb_1.png` ~ `thumb_5.png`(1920×1080, 올리는 순서대로), 한눈에 보기 `overview.png`.
  다시 그리기: `python3 tools/store/make_icon.py && python3 tools/store/thumbs.py && python3 tools/store/overview.py`.

## 그림마다 약속 하나 (올리는 순서)

| 그림 | 약속(글자) | 코드 근거 |
|---|---|---|
| `thumb_1.png` | 희귀: "1/10,000,000,000" + "LEGENDARY / WORLD TREE" | 세계수 OneIn 10000000000, 전설 등급(MinOneIn 8000000) |
| `thumb_2.png` | 성장: "X1,024 LUCK!" + "X2 EVERY REBIRTH!" | `REBIRTH_LUCK_MULT` 2 ^ `MAX_REBIRTHS` 10 = 1,024 |
| `thumb_3.png` | 수집: "COLLECT 150 LANDMARKS!" + 딱지 "1/70"(자유의 여신상) · "1/25,000,000"(용궁, 전설) + "?" 그림자 둘(트로이 목마 · 네시 — 아직 못 찾은 명소) | 명소 150줄, 각 OneIn |
| `thumb_4.png` | 타이쿤: "BUILD YOUR PARK!" + 용궁 위 "+500/s" 하나(꼬리가 용궁을 가리킴) | 진짜 `PlayerState.landmarkIncome`(처음 발견 ☆0 = `TIER_INCOME` 전설 500) — 그림 만들 때 파이썬 식과 같은지 확인 |
| `thumb_5.png` | 특별 연출: "1/375,000,000" + "GIANT HOLOGRAM!" — 진짜 `World.hologram(샹그릴라)` 자리·크기 | 샹그릴라 OneIn = `HOLOGRAM_ONE_IN` 375000000(바로 그 기준) |

- 모든 썸네일에 얼굴이 보이는 블록 아바타(놀람·신남 표정, 자리는 왼쪽 아래 · 오른쪽 계단 · 오른쪽 아래 · 왼쪽 아래 · 양쪽 앞).
- 중요한 글자는 아래 12% 밖(작은 화면·가림 방지). 그림 속 글자는 영어·숫자만 — `fx.no_hangul` 이 그리는 글자를 검사하고,
  덤프에서는 BillboardGui(명소 이름표, 홀로그램 제목 "속보!"+한국어 이름)를 지우고 SurfaceGui 간판 글자를 검사(한글이면 멈춤).
  그래서 5번 홀로그램에는 게임 속 제목 띠가 없습니다(모형·자리·크기는 게임 그대로).

## A/B 시험(Creator Hub → 아이콘·썸네일 A/B 테스트)

- 아이콘: `icon.png`(세계수 + 놀란 아바타, 기본) ↔ `icon_a.png`(같은 장면, 밝은 낮 하늘) ↔ `icon_globe.png`(지구본에서 에펠탑·피라미드·
  자유의 여신상이 튀어나옴 — "명소 게임"이 한눈에 보이는 안). 셋 다 숫자는 같은 1/10,000,000,000.
- 썸네일 첫 장: `thumb_1.png`(희귀) ↔ `thumb_2.png`(환생 행운) 을 첫 자리에 바꿔 시험.
