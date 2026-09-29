# 🌍 랜드마크 RNG — 설계서

지구본을 돌려 세계의 **명소(랜드마크)**를 발견하고, 발견한 명소를 **내 관광 공원**에
미니어처로 전시해 관광 수입을 버는 RNG + 타이쿤 게임.

## 게임 흐름

1. **지구본 돌리기(굴리기)** → 명소 하나 발견 (1/2 시계탑 ~ 1/100,000,000 지구)
2. 처음 발견하면 **발견 보너스 코인**, 이미 있는 명소면 발견 횟수가 쌓여 **별(★1~5)** 이 오름
3. 가진 명소 중 희귀한 순서로 **내 공원 전시 칸**에 미니어처가 자동 전시됨
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
  Models.luau        명소 3D 모형(코드로 만든 임시 모형)  [모형 담당]
src/server/  (ServerScriptService.Server)
  init.server.luau   세션, 원격 처리, 수입 루프, 알림     [서버 담당]
  DataService.luau   DataStore + 세션 잠금               [기존 유지]
  ParkService.luau   공원 부지 배정/미니어처 전시/간판    [서버 담당]
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
| SetSetting | Function | (key, value) | { Ok, State } — key 는 "AutoFeature" |
| Teleport | Function | ("Park" \| "Plaza") | { Ok } |
| State | Event 서버→클라 | Snapshot | 상태가 바뀔 때 + 10초마다 재동기화 |
| Announce | Event 서버→모두 | { UserId, Name, LandmarkId, Rolls, Hologram } | 뉴스 속보 |

```lua
RollResponse =
    { Ok = true, LandmarkId, Luck, Bonus, IsNew, StarUp, Stars, State }
  | { Ok = false, Reason = "cooldown", RetryIn }
  | { Ok = false, Reason = "loading" }
```

Snapshot 필드: Revision, Rolls, Coins, Inventory, Featured, Upgrades, Settings, Luck, Cooldown, Income.
클라는 코인을 `Coins + Income × (지금 - 받은 시각)` 으로 부드럽게 올려서 표시.
PlayerState 의 읽기 함수(park, stars, slots, completedRegions, upgradePrice …)는 Snapshot 을 넘겨도 됨.

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
  비상 바닥: default.project.json 의 FallbackGround(반지름 225 원기둥, 윗면 y -0.5) — 지형을 못 만들면 그대로 남고,
  다 만들면 치움. 가운데 **광장**(반지름 45, 포석 + 둥근 벽돌·돌길 띠) + 받침대 위 거대 지구본 + 스폰 지점.
- **공원 부지**: 광장을 둘러싼 고리 하나에 8칸 = 서버 최대 8명(서버 크기 8).
  반지름 115 는 광장 중심에서 **부지 입구(앞 가장자리)** 까지의 거리(부지 76×80 이 서로 겹치지 않게).
  부지는 광장을 향해 회전. 부지 하나 = 전시 칸 6×6 격자(칸 간격 12, 미니어처 크기 9) + 입구 간판.
- 광장 지구본은 스폰 바로 앞 (0, 1, -26) 받침대 위. 회전하는 모형은 ModelStreamingMode = Atomic.
- 잠긴 칸은 흐릿한 바닥, 열린 빈 칸은 받침대, 전시 칸에는 미니어처 + 작은 이름표(★ 포함).
- 간판: "OOO 님의 관광 공원" + "관광 수입 +X/초".
- **주변 풍경**(Scenery): 돌길 산책로 고리 둘(r 84 / 부지 뒤 r 208) + 이웃 부지 사이 쐐기 틈 8곳의 주제 정원
  (분수 광장·꽃 정원·과수원·연못과 다리·소풍 잔디·바위 정원·토피어리 길·정자)과 오솔길, 틈 양옆·안쪽 잔디의
  심은 무더기(작은 나무 + 덤불 + 들꽃), 부지 뒤 숲 무리(넓은잎나무·기둥 나무·꽃나무)와 빈터(바위·들꽃),
  모래사장(등대·나무 부두·줄무늬 파라솔과 선베드·간식 가게·모래성·야자수 무리·물가 둥근 화강암 바윗돌),
  바다(돛단배·부표·먼 작은 섬 여섯: 길쭉한 모래섬 + 풀 언덕 + 야자수·덤불).
  꽃밭은 돌 테두리 꽃밭과 테두리 없는 들꽃 무더기 두 가지, 부지 뒤 쉼터는 망원경 / 들꽃·꽃 산울타리를 번갈아.
  장식은 ParkLayout.blocked(부지·입구 간판 자리·길·광장)를 비켜 가고, 물가 바로 바깥(물가 + 3)에는 해안선을 따라
  보이지 않는 벽(부두는 끝까지 감쌈). 배치·지형은 고정 시드라 매번 같음(미리보기 = 게임).
  파트 약 5900개(보이지 않는 벽·산책로 포함, 모두 Anchored·단순 모양), 구역별 수는 서버 출력 "[Scenery]" 줄.
  지형: 복셀 표 약 44만 칸(WriteVoxelChannels 7장: 본섬 + 먼 작은 섬 여섯) + 먼 바다 FillBlock 18번.

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
- 환생 시 초기화: `Coins = 0`, `Upgrades` 전부 0, **`Inventory`(보유 명소·별·공원 전시) 비움**, `Featured = nil`.
  유지: `Discovered`(역대 발견 기록 = 도감 표시), 여권 도장(= Discovered 기준), `Settings`, 환생 수.
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
