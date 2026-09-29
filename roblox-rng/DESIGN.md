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

- 바닥 600×600. 가운데 **광장**(반지름 45) + 받침대 위 거대 지구본 + 스폰 지점.
- **공원 부지**: 광장을 둘러싼 원형 배치. 안쪽 고리 8칸, 바깥 고리 16칸 = 최대 24명.
  반지름 115 / 210 은 광장 중심에서 **부지 입구(앞 가장자리)** 까지의 거리(부지 76×80 이 서로 겹치지 않게).
  부지는 광장을 향해 회전. 부지 하나 = 전시 칸 6×6 격자(칸 간격 12, 미니어처 크기 9) + 입구 간판.
- 광장 지구본은 스폰 바로 앞 (0, 1, -26) 받침대 위. 회전하는 모형은 ModelStreamingMode = Atomic.
- 잠긴 칸은 흐릿한 바닥, 열린 빈 칸은 받침대, 전시 칸에는 미니어처 + 작은 이름표(★ 포함).
- 간판: "OOO 님의 관광 공원" + "관광 수입 +X/초".

## 모형 교체 (AI 메쉬)

Studio 에서 `ReplicatedStorage` 아래에 `LandmarkModels` 폴더를 만들고, 명소 Id 와 **같은 이름의 Model** 을 넣으면
(예: `eiffel`) 코드 모형 대신 그 모형이 공원·연출·컬렉션 어디서나 쓰입니다. 크기는 자동으로 맞춰집니다.
Model 에 PrimaryPart 가 없어도 되고, 바닥 중앙을 피벗으로 맞춰 둘수록 정확히 놓입니다.
