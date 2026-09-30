# 🌍 랜드마크 RNG — 설계서

지구본을 돌려 세계의 **명소(랜드마크)**를 발견하고, 발견한 명소를 **내 관광 공원**에
미니어처로 전시해 관광 수입을 버는 RNG + 타이쿤 게임.

## 게임 흐름

1. **지구본 돌리기(굴리기)** → 명소 하나 발견 (1/2 시계탑 ~ 1/100,000,000 지구)
2. 처음 발견하면 **발견 보너스 코인**, 이미 있는 명소면 발견 횟수가 쌓여 **별(★1~5)** 이 오름
3. 가진 명소가 **내 공원 전시 칸**에 미니어처로 전시됨 — 기본은 희귀한 순서로 자동 배치,
   **3D 배치 모드**에서 놀이공원 시뮬레이션처럼 명소를 직접 눌러 집어 다른 받침대로 옮길 수도 있음(아래 "공원 배치")
4. 전시된 명소가 **초당 관광 수입**을 벌어줌 (등급·별·입장료 업그레이드에 비례)
5. 코인으로 **영구 업그레이드** 구매: 지구본(행운), 여행사(속도), 공원 확장(칸), 입장료(수입)
6. 한 지역의 명소를 모두 모으면 **여권 도장** → 영구 행운 보너스
7. **대표 명소** 하나가 캐릭터 옆에 작게 떠다님(자랑용)
8. 1/1,000 이상 발견 → 서버 전체 **📰 뉴스 속보**, 1/10,000 이상 → 광장 하늘에 거대 **홀로그램**

Sol's RNG 와 겹치지 않게 뺀 것: 오라, 10번째 굴림 x2, 시간제 물약, 날씨/바이옴, [GLOBAL] 채팅 문구.

## 파일 구조와 담당

```
src/shared/  (ReplicatedStorage.Shared)
  Config.luau        밸런스 값                           [계약 — 고정]
  Landmarks.luau     명소/등급/지역 정의                 [계약 — 고정]
  PlayerState.luau   데이터 규칙(순수 함수)              [계약 — 고정]
  RollLogic.luau     굴림 판정                           [계약 — 고정]
  Format.luau        숫자/시간 표시                      [계약 — 고정]
  Net.luau           원격 통신 객체                      [계약 — 고정]
  ParkGrid.luau      공원 격자(칸 자리·가장 가까운 칸·보관함·놓기 계획·위에서 보기 카메라, 순수 계산) [공용]
  Models.luau        명소 3D 모형(코드로 만든 임시 모형)  [모형 담당]
src/server/  (ServerScriptService.Server)
  init.server.luau   세션, 원격 처리, 수입 루프, 알림     [서버 담당]
  DataService.luau   DataStore + 세션 잠금               [기존 유지]
  ParkService.luau   공원 부지 배정/미니어처 전시/간판    [서버 담당]
                     (칸 모델 속성 Slot·Look, 부지 속성 OwnerUserId·Origin — 클라이언트 배치 모드가 읽음)
  ParkLayout.luau    부지·길 배치 기준(순수 계산) + 장식 금지 구역 판정 [서버 담당]
  Scenery/           주변 풍경(지형 섬·바다·산책로·정원·숲). Island=지형 모양(순수), Plan=배치(순수), Props=모양 [서버 담당]
  FeaturedDisplay.luau 대표 명소(캐릭터 옆) + 이름표       [서버 담당]
  World.luau         광장 + 가운데 거대 지구본            [서버 담당]
src/client/  (StarterPlayerScripts.Client)
  init.client.luau   상태 동기화, 굴리기 흐름, 입력       [화면 담당]
  Ui.luau            UI 헬퍼, 화면 크기 자동 스케일       [화면 담당]
  Viewport.luau      ViewportFrame 에 모형 띄우기 헬퍼    [화면 담당]
  Hud.luau           스탯, 버튼, 지구본 연출, 뉴스 속보   [화면 담당]
  Panels.luau        컬렉션 / 여권 / 업그레이드 창         [화면 담당]
  ParkEdit.luau      3D 공원 배치 모드(내 공원에서 명소 집어 옮기기 + 아래 보관함 띠) [화면 담당]
```

## 계약 1: Models.luau (서버·클라 공용)

```lua
-- 코드로 만든 임시 모형. 설계 공간: 바닥 가로·세로 10 스터드 안, 높이 22 스터드 이하.
-- 루트: 투명한 "Root" 파트(10 x 0.2 x 10)가 바닥 중앙, PrimaryPart. 모든 파트 Anchored=true, CanCollide=false.
Models.build(landmark: Landmarks.Landmark): Model

-- 실제로 쓰는 함수. ReplicatedStorage.LandmarkModels[landmark.Id] (Model) 가 있으면 그걸 복제(AI 메쉬 교체용),
-- 없으면 build(). 가로·세로 중 큰 쪽이 size 스터드가 되도록 Model:ScaleTo 로 축소/확대.
-- 피벗 = 바닥 중앙. 부모 없이 반환.
-- opts.Anchored == false 면 모든 BasePart: Anchored=false, Massless=true, CanCollide=false,
--   CanQuery=false, CanTouch=false (캐릭터에 용접할 때).
Models.create(landmark: Landmarks.Landmark, size: number, opts: { Anchored: boolean? }?): Model
```

Shape 종류(Landmarks.luau 의 Shape 값, 28종): clocktower, lighthouse, windmill, fountain, arch, gate,
leaning, statue, needle, lattice, ring, dome, temple, sphinx, wall, pyramid, steps, terraces, facade,
moai, stones, gardens, spiral, island, pagoda, skyisland, tree, globe.
색은 landmark.Primary / Secondary / Accent, 재질은 landmark.Material 을 씀.

## 계약 2: 원격 통신 (Net.luau)

| 이름 | 종류 | 요청 | 응답 |
|---|---|---|---|
| GetState | Function | () | Snapshot? (데이터 로드까지 최대 30초 대기) |
| Roll | Function | () | 아래 RollResponse |
| Feature | Function | (landmarkId?) | { Ok, State } — nil 이면 대표 해제 |
| BuyUpgrade | Function | (upgradeId) | { Ok, Reason?, State } |
| SetSetting | Function | (key, value) | { Ok, State } — key 는 "AutoFeature" \| "AutoPark"(boolean) |
| SetDisplay | Function | (slot, landmarkId?, expected?, expectedFrom?) | { Ok, Reason?, State } — 공원 전시 칸에 놓기 / nil 이면 빼기. expected = 클라가 본 그 칸의 명소 Id(빈 칸 ""), expectedFrom = 옮기는 명소가 있던 칸(0 = 전시 안 됨), 지금과 다르면 Reason "stale" |
| Teleport | Function | ("Park" \| "Plaza") | { Ok } |
| State | Event 서버→클라 | Snapshot | 상태가 바뀔 때 + 10초마다 재동기화 |
| Announce | Event 서버→모두 | { UserId, Name, LandmarkId, Rolls, Hologram } | 뉴스 속보 |

```lua
RollResponse =
    { Ok = true, LandmarkId, Luck, Bonus, IsNew, StarUp, Stars, State }
  | { Ok = false, Reason = "cooldown", RetryIn }
  | { Ok = false, Reason = "loading" }
```

Snapshot 필드: Revision, Rolls, Coins, Inventory, Featured, Upgrades, Settings(AutoFeature, AutoPark), Display,
Luck, Cooldown, Income (+ v3 필드).
클라는 코인을 `Coins + Income × (지금 - 받은 시각)` 으로 부드럽게 올려서 표시.
PlayerState 의 읽기 함수(park, parkSlots, stars, slots, completedRegions, upgradePrice …)는 Snapshot 을 넘겨도 됨.

## 계약 3: 서버 규칙

- 굴림: 쿨타임 검증(허용 오차는 반복 악용 못 하게 기준 시각을 밀어 둠) → `PlayerState.luck` 으로 판정 →
  `PlayerState.applyRoll`. 1초마다 `PlayerState.addIncome`.
- 스포일러 방지: 세계 명소(Rank 4) 이상은 **4.5초 뒤**에 리더보드 "최고" 갱신, 뉴스 속보, 홀로그램.
  굴린 본인 클라는 자기 연출이 끝날 때까지 자기 뉴스 속보를 보류.
- 리더보드(leaderstats): "굴림"(IntValue), "최고"(StringValue, 가장 희귀한 명소 이름).
- 태그 "LandmarkSpin" 이 붙은 Model 은 클라가 제자리에서 천천히 회전시킴(광장 지구본, 홀로그램).

## 월드 배치

- 바닥은 서버 시작 때 만드는 **지형 섬**(Workspace.Terrain, Scenery/Island): 해안선 반지름 245~292 로 구불구불,
  공원 자리(r <= 214: 광장·부지·길·산책로)는 윗면이 정확히 y = 0, 부지 뒤 숲띠는 낮은 잔디 언덕, 모래사장은
  물속으로 완만하게 이어짐(물 높이 y = -4, 먼 바다는 사방 1536 까지 지형 물). 파트 밑 땅은 풀잎 장식 없는 재질로 칠함.
  풀잎 장식(Terrain.Decoration)은 스크립트로 못 켜는 속성이라 default.project.json 의 Workspace.Terrain 에서 켬(place 파일).
  비상 바닥: default.project.json 의 FallbackGround(반지름 225 원기둥, 윗면 y -0.5) — 지형을 못 만들면 그대로 남고,
  다 만들면 치움. 가운데 **광장**(반지름 45, 포석 + 둥근 벽돌·돌길 띠) + 받침대 위 거대 지구본 + 스폰 지점.
- **공원 부지**: 광장을 둘러싼 고리 하나에 8칸 = 서버 최대 8명(서버 크기 8).
  반지름 115 는 광장 중심에서 **부지 입구(앞 가장자리)** 까지의 거리(부지 76×80 이 서로 겹치지 않게).
  부지는 광장을 향해 회전. 부지 하나 = 전시 칸 6×6 격자(칸 간격 12, 미니어처 크기 9) + 입구 간판.
- 광장 지구본은 스폰 바로 앞 (0, 1, -26) 받침대 위. 회전하는 모형은 ModelStreamingMode = Atomic.
  모형(Models 의 globe, 굴림 연출 화면도 같은 모형): 진짜 세계 지도(Natural Earth 1:110m)를 따른 대륙 — 낮고 넓은
  겹친 돔 공 약 140개(초록 바탕 + 사하라·아라비아·이란·오스트레일리아 모래색 + 눈), 홍해·페르시아만은 물길로 남김.
  덧칠 사슬: 중앙아시아 마른 띠(카스피해 → 카자흐 초원 → 고비, 모래색), 히말라야 눈 띠, 짙은 초록 열대림
  (아마존·콩고·동남아, 곳마다 겹친 작은 공 셋). 표는 `tools/model_preview/globe_land.py` 가 만든 `Models/GlobeLand.luau`.
  금색 자오선 고리(32조각, 받침 기둥에 닿음) + 극 축받이(달은 뺌 — 굴림 연출 틀은 작아진 경계 상자에 맞춰 지구가 조금
  커짐). 파트 약 185개(매 프레임 PivotTo 로 돌리므로 더 늘리지 않기). 땅·극 돔은 CastShadow 끔, 광장 지구본은
  모든 파트 CanQuery·CanTouch 끔(충돌은 Models.create 가 끔). 처음 방향은 스폰 쪽으로 아프리카(World 의 EARTH_FACING).
  광장 둘레 나무 8그루는 섬 풍경과 같은 넓은잎나무(Scenery/Props 의 Tree, Scale 1.2·1.02) — Face 로 밝은 잎 공이
  광장 가운데를 봄. 넓은잎나무 줄기 두 마디 사이에는 아래 줄기와 같은 굵기의 공(둥근 어깨, 턱처럼 보이지 않게).
- 부지 바닥은 따뜻하고 밝은 돌 포석(Pavement, 광장 포석과 한 집안) + 부지 색 둘레 띠 — 둘레 잔디와 또렷이 갈리고
  흰 받침대·명소가 돋보임(버전 14 까지의 잔디색 Grass 바닥은 실제 게임에서 어두워 위에서 짙은 초록 판처럼 보였음).
  빈 부지(주인 없음)에는 칸 자리 36곳에 얇고 살짝 밝은 판(`EmptyGrid` 폴더의 `GridMark`, 9×9, 부지 윗면 +0.02~+0.08,
  충돌·광선·닿기·그림자 없음, `Slots` 폴더 밖)을 깔아 "명소가 올 자리"로 보이게 하고, 주인이 오면 치움(떠나면 되돌림).
- 주인 부지: 잠긴 칸은 같은 밝은 판(10×10), 열린 빈 칸은 받침대, 전시 칸에는 미니어처 + 작은 이름표(★ 포함).
- 간판: "OOO 님의 관광 공원" + "관광 수입 +X/초".
- **주변 풍경**(Scenery): 돌길 산책로 고리 둘(r 84 / 부지 뒤 r 208) + 이웃 부지 사이 쐐기 틈 8곳의 주제 정원
  (분수 광장·꽃 정원·과수원·연못과 다리·소풍 잔디·바위 정원·토피어리 길·정자)과 오솔길, 틈 양옆·안쪽 잔디의
  심은 무더기(작은 나무 + 덤불 + 들꽃), 부지 뒤 숲 무리(넓은잎나무·기둥 나무·꽃나무)와 빈터(바위·들꽃),
  모래사장(등대·나무 부두·줄무늬 파라솔과 선베드·간식 가게·모래성·야자수 무리·물가 둥근 화강암 바윗돌),
  바다(돛단배·부표·먼 작은 섬 여섯: 길쭉한 모래섬 + 풀 언덕 + 야자수·덤불).
  꽃밭은 돌 테두리 꽃밭과 테두리 없는 들꽃 무더기 두 가지, 부지 뒤 쉼터는 망원경 / 들꽃·꽃 산울타리를 번갈아.
  산울타리는 다듬은 네모 잎 몸통(부딪힘) + 윗면을 따라 1.85 스터드 이하 간격으로 얹은 잎 공 줄(초록 세 가지, 크기·높이 조금씩
  다름, 꽃 산울타리는 공 겉에 작은 꽃) — 버전 14 까지의 가로 원기둥 윗면은 위에서 보면 통나무처럼 보였음.
  장식은 ParkLayout.blocked(부지·입구 간판 자리·길·광장)를 비켜 가고, 물가 바로 바깥(물가 + 3)에는 해안선을 따라
  보이지 않는 벽(부두는 끝까지 감쌈). 배치·지형은 고정 시드라 매번 같음(미리보기 = 게임).
  파트 약 6400개(보이지 않는 벽·산책로·나무 줄기 마디 포함, 모두 Anchored·단순 모양), 구역별 수는 서버 출력 "[Scenery]" 줄.
  지형: 복셀 표 약 44만 칸(WriteVoxelChannels 7장: 본섬 + 먼 작은 섬 여섯) + 먼 바다 FillBlock 18번.
  **실제 Roblox 규칙(실측)**: 단단한 지형 윗면은 "맨 위 땅 복셀 바닥 + 2 + 4·점유율"(복셀 반 칸 위)에, 물 윗면은 "복셀 바닥 + 4·점유율" 에 그려짐.
  그래서 땅 점유율은 원하는 높이보다 Island.SOLID_LIFT(2) 낮춰 쓰고, 먼 바다 바닥 FillBlock 도 2 내려 채움.
  (버전 13 까지는 이 규칙을 몰라 땅이 2 스터드 높게 그려져 광장·길·부지 바닥이 묻혔음. 규칙은 Open Cloud Luau 실행으로 Raycast 해서 잼.
  미리보기의 가짜 지형(tools/roblox_mock.luau)도 같은 규칙으로 그림)

## 모형 교체 (AI 메쉬)

Studio 에서 `ReplicatedStorage` 아래에 `LandmarkModels` 폴더를 만들고, 명소 Id 와 **같은 이름의 Model** 을 넣으면
(예: `eiffel`) 코드 모형 대신 그 모형이 공원·연출·컬렉션 어디서나 쓰입니다. 크기는 자동으로 맞춰집니다.
Model 에 PrimaryPart 가 없어도 되고, 바닥 중앙을 피벗으로 맞춰 둘수록 정확히 놓입니다.

## UI 스타일 가이드 (v2 — "AI 티" 없애기)

목표: 흔한 웹 앱(어두운 둥근 상자 + 얇은 테두리 + 이모지) 대신 **인기 로블록스 게임식 통통한 UI**.

- **이모지 금지**: 화면 UI 글자에 이모지를 쓰지 않음(★☆ 별 기호만 허용). 아이콘은 `Icons.luau` 의 3D 미니 아이콘(ViewportFrame).
- **색**(Theme):
  - Ink `#1E1B2E` — 모든 굵은 테두리·글자 테두리
  - Cream `#FFF4DC` / Paper `#FFE6B0` — 창 바탕(여권 종이 느낌)
  - Sky `#39A0FF`/`#1F6FCC`, Grass `#4CD964`/`#2E9E45`, Sun `#FFC53D`/`#D9900F`, Coral `#FF5E5B`/`#C93A38`, Grape `#9B6BFF`/`#6A45C9` — (앞면/그림자)
- **글꼴**: 기본 `Enum.Font.FredokaOne`, 큰 제목(명소 공개, 속보)은 `Enum.Font.LuckiestGuy`. 한글은 로블록스 기본 대체 글꼴로 표시됨.
- **글자**: 색 바탕 위는 흰 글자 + Ink 글자 테두리(UIStroke 2~3), 크림 바탕 위는 Ink 글자.
- **통통 버튼**(`Ui.chunkyButton`): 아래에 어두운 그림자 판(6px 아래), 위에 앞면. 둥근 모서리 14, Ink 테두리 3,
  위쪽이 살짝 밝은 그라데이션. 누르면 앞면이 4px 내려감, 마우스를 올리면 1.05배.
- **창**(`Ui.window`): Cream 바탕, Ink 테두리 4, 모서리 18, 위에 색 리본 제목(흰 글자 + 테두리), 빨간 동그라미 닫기 버튼.
- **알약**(`Ui.pill`): 캡슐 모양 반투명 Ink 바탕, 왼쪽에 테두리를 살짝 넘는 동그란 3D 아이콘.
- **화면 배치**(1280×720 기준, 배율 0.55~0.9):
  - 왼쪽 위: 코인 알약(동전 아이콘 + 큰 숫자), 그 아래 작은 알약 "+13.5/초", 작은 칩 "굴림 57" "행운 ×1.25"
  - 왼쪽 가운데: 네모 통통 버튼 4개(컬렉션=Sky, 여권=Grape, 업그레이드=Sun, 내 공원/광장=Grass) — 3D 아이콘 + 짧은 글자
    (+ 내 공원 부지가 있으면 이동 버튼 옆에 [배치](Grass, 더 좋은데 전시 안 된 명소 수 배지) = 3D 배치 모드 — 아래 "공원 배치".
    배치 모드 동안은 왼쪽 메뉴·상점·굴리기 줄을 숨기고 아래 가운데에 보관함 띠)
  - 아래 가운데: 큰 초록 굴리기 버튼(돌아가는 지구본 아이콘 + "굴리기", 쿨타임은 버튼 안 채움 막대),
    옆에 작은 자동 버튼(꺼짐 회색 / 켜짐 주황 + ON 배지), 위에 작은 알약 "여권 도장 1/6"
  - 명소 공개: 뒤에 도는 햇살(얇은 막대 12개), 큰 LuckiestGuy 이름 + 굵은 테두리, 등급 색 리본
  - 뉴스 속보: 신문 띠(크림 바탕 + 빨간 "속보" 딱지 + Ink 글자)
- **월드 글자**(공원 간판, 전시 이름표, 대표 명소 이름표, 홀로그램 제목)도 같은 글꼴·테두리·색을 씀.
  간판은 나무 판자(나무 색 + Ink 테두리 느낌) 위 크림 글자판.

## 환생 (v3)

"Steal a Brainrot" 식: **코인 + 특정 명소 보유**가 조건. 환생하면 영구적으로 행운·관광 수입이 오름.

- 환생 단계마다 요구 사항은 `Config.REBIRTHS[n] = { Coins = number, Landmarks = { id, ... } }` (n = 다음 환생 번호).
  목록을 넘어서면 마지막 단계 요구 명소 + 코인 ×4 씩 증가.
  요구 명소는 **이번 판에서 보유**하고 있어야 함.
- 환생 시 초기화: `Coins = 0`, `Upgrades` 전부 0, **`Inventory`(보유 명소·별·공원 전시) 비움**, `Featured = nil`,
  공원 직접 배치(`Display`) 비우고 **`Settings.AutoPark = true`**(자동 배치로 되돌림 — 아래 "공원 배치").
  유지: `Discovered`(역대 발견 기록 = 도감 표시), 여권 도장(= Discovered 기준), 그 밖의 `Settings`(AutoFeature), 환생 수.
- `Data.Discovered: { [id]: true }` — 한 번이라도 발견한 명소. 도감의 "발견/미발견", 여권 진행도·도장은 이것 기준.
  발견 보너스 코인·"NEW" 표시는 **역대 처음**(Discovered 에 없을 때)만. 공원 전시·별·수입·환생 조건은 `Inventory` 기준.
- 보상(누적, 곱): 행운 × (1 + `REBIRTH_LUCK_BONUS` × 환생 수), 관광 수입 × (1 + `REBIRTH_INCOME_BONUS` × 환생 수).
- 데이터: `Data.Rebirths: number`. 리더보드 "환생" 추가(IntValue).
- 원격: `Rebirth` (Function) `() -> { Ok, Reason?, State }` — 서버가 조건 검사(코인·명소) 후 적용.
- PlayerState: `rebirthRequirement(rebirths) -> { Coins, Landmarks }`, `canRebirth(data) -> (ok, missing: { string }, coinsShort: number)`,
  `rebirth(data) -> (ok, reason?)`.

## 유료 상품 (Robux, v3)

ID 는 Creator Hub 에서 만든 뒤 `Config` 에 넣음. **ID 가 0 이면 그 상품은 화면에 안 나옴**(게임은 정상 동작).

- **게임패스**(한 번 사면 영구, `Config.GamePasses`):
  - `LuckVIP` 행운 ×2 · `FastRoll` 굴림 간격 ×0.7 · `DoubleIncome` 관광 수입 ×2
  - 소유 여부는 서버가 접속 시 `MarketplaceService:UserOwnsGamePassAsync` 로 확인 + 구매 완료 이벤트로 갱신,
    세션에만 저장(`Session.Passes`). 스냅샷에 `Passes: { [id]: true }` 포함.
- **개발자 상품**(여러 번 구매, `Config.Products`):
  - `LuckBoost` 행운 ×2 15분(시간 누적) · `ServerLuck` **서버 전체** 행운 ×2 15분 · `CoinPack` 코인 = max(1000, 초당 수입 × 1800)
  - `MarketplaceService.ProcessReceipt`: 세션이 있고 지급 + **저장 성공 후에만** `PurchaseGranted`.
    같은 `PurchaseId` 는 한 번만 지급(`Data.Receipts` 에 최근 50개 보관). 실패하면 `NotProcessedYet`.
  - 시간 부스트는 **접속 중에만** 줄어듦(`Data.Boosts[id] = 남은 초`). 서버 행운은 서버 변수(저장 안 함, 서버 전원 적용).
- 효과 합산(곱): 행운 = 기본 × 지구본 × 여권 도장 × 환생 × VIP × 행운 부스트 × 서버 행운.
  수입 = 기존 × 환생 × DoubleIncome. 쿨타임 = 기존 × FastRoll.
  PlayerState 읽기 함수는 선택 인자 `mods: { Passes: { [string]: boolean }?, ServerLuck: boolean? }` 를 받음
  (없으면 기존과 같은 결과). 스냅샷의 `Luck/Cooldown/Income` 은 mods 를 반영한 값.
- 원격: `BuyPass` (Function) `(passKey) -> { Ok }` → 서버가 `PromptGamePassPurchase`,
  `BuyProduct` (Function) `(productKey) -> { Ok }` → 서버가 `PromptProductPurchase`. 결과는 State/Announce 이벤트로 반영.
  서버 행운 구매 시 `Announce` 와 별도로 `ServerLuck` 이벤트 `{ Name, Until }` 를 모두에게 보냄.

## 공원 배치 (v4)

플레이어가 **어떤 명소를 어느 칸에** 전시할지 고름. 기본은 예전처럼 자동 배치(희귀한 순서).

- 데이터:
  - `Data.Settings.AutoPark: boolean` — 기본 `true`(예전 저장에 없으면 `true` = 예전과 같은 공원).
  - `Data.Display: { string }` — 직접 배치. 칸 번호 → 명소 Id, 빈 칸은 `""`. 구멍 없는 배열(DataStore 안전),
    길이 ≤ `PARK_GRID²`(36), 끝 빈 칸은 저장 안 함. `AutoPark = true` 면 쓰지 않음(비어 있음).
    reconcile: 문자열이 아니면 `""`, 앞 칸과 겹치는 Id 는 `""`, 모르는 명소 Id 는 보존(전시할 때만 건너뜀).
- 칸 번호: 1번 = 입구 쪽 줄 가운데. 입구 쪽 줄부터, 한 줄 안에서는 가운데에 가까운 칸부터
  (입구에서 공원 안쪽을 볼 때 가운데 오른쪽 → 가운데 왼쪽 → …). `PlayerState.slotCell(slot) -> (row, column)`
  (row 1 = 입구 줄, column 1 = 입구에서 볼 때 왼쪽 끝) 을 월드 받침대(ParkService)와 3D 배치 모드가 같이 씀(`ParkGrid`).
  칸 번호는 내부 값일 뿐 화면에 "#3" 같은 글자로 보여 주지 않음(격자 자리가 곧 칸).
- PlayerState:
  - `parkSlots(data) -> ({ [slot]: id }, unlocked)` — 열린 칸마다 전시 명소(빈 칸 nil).
    자동 = 보유 명소를 희귀한 순서로 1번 칸부터. 직접 = `Display` 에서 열린 칸 · 보유한 명소 · 겹치지 않는 것만.
    `park(data)` = 빈 칸을 뺀 목록(칸 번호 순서). **관광 수입은 전시 칸에 있는 명소만** 셈.
  - `setDisplay(data, slot, id?, expected?, expectedFrom?) -> (ok, reason?)` — slot 은 1..열린 칸 수 정수, id 는 보유한 명소(nil = 빼기).
    이미 다른 칸에 있는 명소면 두 칸이 자리를 바꿈(빈 칸이면 옮김). 자동 배치 중 첫 편집이면 **지금 자동 배치에서 시작**하고
    `AutoPark = false`. `expected`(선택) = 요청한 쪽이 본 그 칸의 명소 Id(빈 칸 `""`): 지금 그 칸에 보이는 것과 다르면
    아무것도 안 바꾸고 `"stale"`(문자열이 아니어도 `"stale"`, nil 이면 확인 안 함 — 서버 내부·옛 클라이언트).
    `expectedFrom`(선택, id 가 있을 때) = 옮기는 명소가 요청한 쪽 화면에서 있던 칸(0 = 전시 안 됨): 지금과 다르면 `"stale"`.
    실패 사유: "잘못된 칸입니다" / "잠긴 칸입니다" / "보유하지 않은 명소입니다" / "stale" (실패하면 그대로).
  - `setAutoPark(data, on)` / `autoPark(data)` / `setSetting(data, "AutoPark", bool)` — 켜면 가장 희귀한 명소들로
    다시 채우고 `Display` 를 비움, 끄면 지금 자동 배치 그대로 `Display` 에 옮겨 적음(화면 안 바뀜).
  - 직접 배치 편의: 이번 판에 **처음 얻은 명소**(applyRoll 첫 보유)는 첫 빈 칸(칸 번호 순서)에 놓임
    (빈 칸이 없으면 안 놓임). **공원 확장**으로 새로 열린 칸은 아직 전시 안 된 보유 명소 중 희귀한 순서로 채움.
  - `missedByFullPark(data, id) -> boolean` — 직접 배치 중 이번 판에 처음 얻은(보유 1개) 명소가 빈 열린 칸이 없어
    전시되지 못했는지(자동 배치면 false). "공원 꽉 참" 알림 기준.
  - `betterHidden(data) -> { id }` — 직접 배치 중 전시 안 된 보유 명소 가운데 **전시 칸에 있는 가장 약한 명소보다
    수입이 큰 것**(희귀한 순서). 전시가 하나도 없으면 수입이 있는 보유 명소 전부, 자동 배치면 빈 목록.
    일부러 뺀 약한 명소나 빈 칸은 세지 않음. HUD·도감의 [배치] 버튼 숫자 배지 기준.
  - 환생: `Display` 비우고 **`AutoPark = true`**(자동 배치로 되돌림). 직접 배치 그대로 빈 공원에서 다시 시작하면
    처음 얻는 흔한 명소들이 칸을 먼저 채우고, 꽉 찬 뒤 얻는 더 좋은 명소는 전시가 안 돼서 수입이 줄기 때문.
- 서버: `SetDisplay(slot, id?, expected?, expectedFrom?)` 는 Feature/SetSetting 과 같은 세션 검사 + 배치 편집 속도 제한(연속 10번,
  그다음 초당 4번, `SetSetting("AutoPark")` 도 같이 셈. 넘으면 `{ Ok = false, Reason = "busy", State }`).
  `"stale"` 이면 `{ Ok = false, Reason = "stale", State }`(새 상태). 성공하면 공원을 칸 단위로
  다시 그림(ParkService.update — 바뀐 칸만 다시 만듦). 연출 중인 희귀 명소는 공개될 때까지 그 칸이 비어 보임.
- 월드(복제 속성, 서버는 ClickDetector 를 달지 않음): 부지 모델 `OwnerUserId`(주인 UserId, 빈 부지는 없음)·`Origin`
  (부지 CFrame: 중앙 바닥, -Z = 입구), 칸 모델(`Slots` 폴더, **36칸 모두 — 잠긴 칸 포함**) `Slot`(칸 번호)·`Look`
  (`"#locked"` | `"#empty"` | 명소 Id, 모델을 만들 때 한 번 정함 — 모습이 바뀌면 새 모델). 칸 자리는 `Shared/ParkGrid`
  (`slotOffset`, 칸 간격 12, 받침대 10) 를 서버 받침대와 클라이언트 배치 모드가 같이 씀. 새로 믿는 클라이언트 값은 없음(검증은 setDisplay).

### 3D 배치 모드 (ParkEdit, v5 — 2D "배치" 창을 대신함)

놀이공원 시뮬레이션처럼 메뉴 창 없이 **내 공원에서 명소를 직접 눌러 집고 다른 받침대에 놓음**. 내 부지에서만.

- 들어가기: HUD [배치] · 도감 머리 줄 [배치](열린 창은 닫힘) — 내 공원 밖이면 먼저 `Teleport("Park")` 로 이동한 뒤.
  또는 배치 모드 밖에서 **내 받침대·명소를 누름**: 주인 클라이언트만 자기 부지(OwnerUserId = 내 UserId)의 열린 칸에
  클라이언트 전용 `ClickDetector`(MaxActivationDistance 40)를 닮 → 누르면 배치 모드 + 그 명소를 바로 집음.
  남의 공원 받침대에는 손가락 커서가 뜨지 않음. 배치 모드 동안은 ClickDetector 를 떼고(직접 광선으로 찾음) 나가면 다시 닮.
- 화면: HUD 왼쪽 메뉴·상점·굴리기 줄을 숨김(건설 모드 — 위쪽 코인·알림은 그대로).
  **자동 굴리기는 배치 모드 동안 쉼**(AUTO 가 켜져 있으면 들어갈 때 Ink 알림 [auto] "AUTO 쉬는 중", 나가면 다시 돎). 띠에 자동 굴리기
  스위치를 따로 두지 않는 까닭: 띠에는 이미 [자동](자동 배치)이 있어 "자동" 두 개가 나란히 있으면 아이들이 헷갈리고, 쉬는 동안은
  새 명소가 빈 칸에 들어와 들고 있는 칸이 바뀌는(stale) 일도 없음. 휴대폰도 굴리기 줄 없이 끌 수 있는 셈(나가면 AUTO 버튼 그대로).
  R = 한 번 굴리기는 됨, T = AUTO 켜고 끄기(알림 "AUTO ON"/"AUTO OFF", 나가면 적용). 배치 모드의 굴림 결과는 가운데 연출(공원 한가운데를
  가림) 대신 위쪽 알림 줄의 작은 딱지 [지구본] 명소 이름(등급 색, 처음이면 작은 NEW) — 도는 중에 들어가면 연출을 바로 숨기고 결과만
  딱지로(결과를 보인 뒤에 상태 반영: 순서 그대로).
  카메라는 **부지 위 3/4 시점**(입구 쪽 위에서 55도로 내려다봄, Scriptable)으로 날아감. `ParkGrid.topView` 가 상단바 아래 ~
  아래 띠 위 영역에 **열린 칸이 있는 줄 + 잠긴 줄 하나**(`ParkGrid.topRows` — 공원 확장으로 어디가 늘어날지 보이게, 칸이 적을 때
  명소가 작게 보이지 않게)의 받침대 + 명소 꼭대기가 딱 들어오는 거리·바라보는 곳을 계산(휴대폰·세로 화면도). 공원 확장으로 줄이
  늘면 다시 맞춤. 휠 = 조금 가까이/멀리(0.8~1.45배). 터치는 **두 손가락 벌리기/모으기**(같은 범위, `ParkGrid.pinchZoom`):
  두 번째 손가락이 닿으면 진행 중인 집기·끌기를 취소(든 명소는 제자리로)하고, 손가락이 모두 떨어질 때까지 뗌은 무시(놓기 없음).
  이 시점에서는 **캐릭터 이동을 끔**(카메라가 캐릭터를 따라가지 않아 걸으면 화면 밖으로 나가 버리고, 터치 조이스틱·점프 버튼이
  부지 아래쪽을 가림). 띠의 [시점] 을 누르면 평소 따라가는 카메라(이동 켜짐) ↔ 위에서 보기. 나가면 원래 카메라·이동으로.
- 칸 표시(이 화면에서만, 빛나는 판 36개 + 강조 둘 — `Highlight` 는 가리키는 칸 하나와 들고 있는 명소 하나만):
  들고 있지 않을 때 빈 열린 칸 = 옅은 초록 판. 들고 있으면 놓을 수 있는 칸이 숨 쉬듯 빛남(빈 칸 초록, 명소 칸 = 자리 바꿈 노랑),
  집은 자리 = 흰 판, 잠긴 칸 = 아주 흐린 빨강(잠긴 칸이 많아도 놓을 자리가 먼저 보이게). 가리키는 칸 강조: 명소 노랑 · 빈 칸 초록 ·
  잠긴 칸 빨강. 들고 있는 명소 이름표는 화면 px 고정이라 작은 화면(자동 배율 0.55)에서는 줄임.
- 집기: 명소를 누르면 "들고 있음" — 원래 명소(와 이름표)는 이 화면에서만 숨기고, 반투명 복사본(노란 강조 + 흰 테두리,
  머리 위 이름 + 별)이 3.4 스터드 떠서 살짝 오르내리며 돎. 가리키는 칸 위로 붙고, 칸이 없는 곳은 바닥 위(부지 가장자리에서 멈춤).
  가리키는 칸 찾기 = 내 부지 칸 모델에 광선 → 안 맞으면 부지 바닥 평면과 만나는 점에서 가장 가까운 칸(`ParkGrid.slotAt`).
  이 화면에서 숨긴 원래 명소(들고 있는 칸·날아와 앉을 칸)는 광선 목록에서 빠짐(안 보이는 명소가 뒤쪽 받침대를 가리지 않게).
  띠 위 딱지 줄의 비친 곳을 눌러도 뒤 명소를 집지 않음(띠와 같음). 채팅 등 글자 칸에 쓰는 중에는 Esc·Q 를 무시.
  잠긴 칸 위면 복사본이 빨갛게.
- 놓기(누르기 또는 끌어서 떼기): 다른 열린 칸 = 옮기기 / 명소가 있으면 자리 바꾸기(상대가 원래 칸으로 폴짝) —
  `ParkGrid.dropPlan` → `SetDisplay(칸, Id, expected, expectedFrom)`(패널 때와 같은 stale 확인). 같은 칸 · Esc/Q ·
  오른쪽 클릭 · 부지 밖 누름 = 내려놓기(제자리로 날아감). 잠긴 칸 = "공원 확장" 알림(계속 들고 있음).
  마우스·위에서 보기 터치: 누르는 순간 집어서 끌어 놓을 수 있고, 톡 집고 → 톡 놓기도 됨. 평소 카메라 + 터치에서는 끌기 =
  화면 돌리기라서 톡 = 집기. 끌어서 아래 띠에 떼면 보관.
- 아래 띠(배치 모드에서만, 크림 쟁반 + Ink 테두리, 아래 가운데 — 터치 기기는 오른쪽 아래 점프 버튼 자리를 비움):
  왼쪽 [보관](나무 상자 아이콘, 전시 명소를 들고 있으면 Coral = 보관함으로 `SetDisplay(칸, nil, Id)`, Backspace/Delete 도)
  [자동](시상대 아이콘, 켜짐 = 초록 + ON 딱지, 직접 배치가 바뀌면 "확인?" 한 번 더), 가운데 **보관함** = 가졌지만 전시 안 된 명소
  카드(희귀한 순서 `ParkGrid.storage`, 가로 스크롤, 카드 96×104 = 배율 0.55 에서 53×57px, 등급 색 사진은 보이는 카드만
  3D 로 만듦, 별, 전시 칸의 가장 약한 명소보다 좋으면 오른쪽 위 노란 위 화살표 딱지 = `betterHidden`), 오른쪽 [시점](사진기)
  [완료](체크 = 나가기). 버튼 앞면 92×102 = 배율 0.55 에서 50×56px. 쟁반 위 테두리에 걸친 딱지 [공원 전시 수/열린 칸] [동전 +X/s].
  카드를 누르면 그 명소를 집음(보관함에서, expectedFrom 0) → 받침대를 눌러 놓음(명소가 있는 칸이면 그 명소는 보관함으로
  톡 튀며 사라짐). 같은 카드를 다시 누르면 내려놓기. 보관함이 비면 도감처럼 도는 지구본 + "굴리기" 딱지.
  집은 명소는 첫 빈 칸 위에서 시작, 공원이 꽉 찼으면 **가장 약한 전시 명소 칸 위**(`ParkGrid.storageStart` = `betterHidden` 이
  견주는 명소, 같으면 앞 번호 — 휴대폰 좁은 화면에서도 보이는 앞쪽; 예전 부지 가운데는 화면 위 끝 밖이었음). 그 명소 위로 떠서
  겹치지 않고, 손가락을 떼면(가리키는 곳 없음) 떠 있는 칸의 판·강조가 켜짐(톡 = 바꿔 넣기). 보관함에서 들고 있으면 명소 있는 칸
  (바꿔 넣기) 판이 자리 바꿈 판보다 또렷함(투명도 0.6, 자리 바꿈 0.8).
- 미리 보기: 누르는 즉시 같은 PlayerState 규칙을 스냅샷 사본에 적용해 보여 주고(`ParkGrid.preview`), 옮긴 칸에는 이 화면에서만
  보이는 모형을 두었다가 서버가 칸 모델을 다시 만들면(`Look` 이 맞으면, 최대 3초) 치움. 서버 상태가 진실 — 실패·stale 이면
  미리 보기를 버리고 서버 모습으로 되돌림(알림 "공원 바뀜"/실패 알림). 들고 있는 복사본·날아가는 모형은 파트마다 피벗 기준 자리를
  적어 두고 매 프레임 절대 자리로 옮김(`BulkMoveTo`, PivotTo 되풀이 오차 없음).
- 나가기: [완료] · Esc/Q(들고 있으면 먼저 내려놓기) · 다른 창 열기 · 이동 버튼 · 부지 밖으로 걸어가거나 순간 이동(여유 14) ·
  죽음/캐릭터 사라짐 · 부지 잃음. 나가면 이 모드가 만든 연결·로컬 모형·강조를 모두 지우고 숨긴 명소를 되돌림.
  배치 모드 중 서버가 칸 모델을 다시 만들어도(ChildAdded/Removed — 자동 굴림으로 새 명소, 다른 편집) 그때그때 맞춤.
  환생으로 들고 있던 명소가 없어지면 내려놓음.
- 알림: 배치 편집(놓기·빼기·옮기기)이 받아들여져 자동 배치가 켜짐 → 꺼짐이 되면 [자동] 버튼이 통통 튀고, 이번 접속에서
  처음이면 중립(Ink) 알림 [시상대] "자동 꺼짐". [자동] 버튼을 직접 눌러 끈 경우는 알림 없음.
  직접 배치 중 이번 판에 처음 얻은 명소가 공원이 꽉 차서 전시되지 못했으면(`PlayerState.missedByFullPark`) 연출이 끝난 뒤
  Sun 알림 [공원] "공원 꽉 참". stale = 중립 알림 [공원] "공원 바뀜"(굴림 연출 중에 받은 새 상태는 연출이 끝난 뒤 반영).
- HUD [배치] 버튼과 도감 머리 줄 [배치] 버튼 오른쪽 위에 `#betterHidden` 숫자 배지(여권 "1/6" 배지와 같은 Ink 딱지 +
  Sun 숫자, 0 이면 숨김). HUD [배치] 는 왼쪽 메뉴 이동 버튼([공원]/[광장]) 바로 오른쪽 — **내 공원 부지가 있으면 어디에 있든** 보임
  (메뉴 칸 수 계산에는 안 셈: 여러 열이면 비어 있는 칸, 1열이면 묶음 옆, 가로 한 줄이면 한 칸 더 넓은 묶음으로 쳐서 위 가운데 묶음이
  비켜 감). 아이콘은 `Icons` "arrange"(잔디 판 위 2×2 칸, 세 칸에 미니 명소 블록 + 빈 칸 "+"), 띠 아이콘 "crate"(보관)·"camera"(시점).
- 목업: `mockup` 6번(PC, 집어 옮기는 중)·6-3(844×390, 빈 보관함)·6-4(667×375, 보관함에서 집음) — 위에서 보기 카메라를
  topView 와 같은 식으로 그려서 격자가 띠 위에 들어오는지·누르는 크기(띠 버튼 앞면·카드 40px 이상)를 잼(명소는 등급 색 상자로 대신).
- 확인: `tests/run.luau`(ParkGrid 순수 계산 — 칸 자리·가장 가까운 칸·보관함 순서·놓기 계획·topView), Studio 없이
  `tools/client_smoke/`(가짜 Roblox 환경에서 진짜 ParkService + ParkEdit / init.client 를 돌려 집기·옮기기·stale·나가기 확인).
