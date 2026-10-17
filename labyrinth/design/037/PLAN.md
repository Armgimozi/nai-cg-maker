# 0.3.7 집 구역 + 지형 잠금 — 구현 계획 (10채)

기준: 0.3.6.1 (`claude/bold-darwin-nwa5vk` 7071ad91). 작업 가지 `plots-037` (`/home/user/w-pl37`).
설계: `design036/plots/plots_spec.md`·`plots_spec.json` (최종안) + `review_plots.md` (R1~R21).
주인 결정: 설계 그대로, **집은 10채** ("10채만 해").

이 글에서 "구역 기계"는 0.3.6.1 의 `village/District*.java` (지문 검사 → 백업 → 짓기 → 막힘 처리 → 되돌리기, 얼린 칸,
보호 상자·PvP 안전지대·경계) 를 말한다.

같이 보는 파일 (저장소 `labyrinth/design/037/` — 이 글도 `PLAN.md` 로 들어 있음):
- `plots10_spec.json` — 10채 숫자 원본 (설계 JSON 에서 두 채를 빼고 번호를 다시 매긴 것, `old_id` 에 옛 번호 · 자재 386줄 `materials.catalog` 포함)
- `tools/make_spec10.py` — 위 파일을 만드는 도구 (`python3 -I make_spec10.py design036/plots/plots_spec.json plots10_spec.json`)
- `tools/check_layout10.py` — 10채 배치 검사 (실제 jar `mine.json` 으로 광산 마스크를 펼쳐 봄) → `check10.json`
  (`python3 -I tools/check_layout10.py plots10_spec.json <world>/dimensions/minecraft/overworld/labyrinth-village.yml plugin/src/main/resources/village check10.json`)
- `under10.json` — 집터 아래 8칸 정리량 (`design036/plots/tools/judge_under.py`)

---

## 0. 한눈에

| 항목 | 정함 |
|---|---|
| 자리 | 마을 남쪽 "등불 골목" (x −179..−115, z 26..108). 광산 다음 둘째 구역 `homes` |
| 집 | **10채** 14×14, 짓기 높이 바닥 −6 ~ +24. 옛 3번(마을이 다듬은 칸 위)·옛 9번(광장에서 가장 멂)을 뺌 |
| 받기 | 마을 관리인 모아 · `/미궁 집` · 대문 표지판 · 메인 메뉴 "집". 공짜, 한 사람 한 집 |
| 권한 | 주인 + 초대 8명: 짓기·부수기·상자. 손님: 문·작업대·종 (집마다 끔) |
| 회복 | 집 안 5초 안 맞으면 초당 HP·MP 5% · 내 침대 2초면 가득 (60초에 한 번) · 미궁에는 안 넘어감 |
| 지형 잠금 | 주 월드에서 내 집 밖 부수기·놓기·양동이·불·괭이·밭 밟기 막음. 크리에이티브 관리자는 예외. **집 구역이 지어진 뒤에만** |
| 옛 건물 | 지우지 않음. 14일 이사 기간 (집터·보호 상자 밖 사람이 놓은 블록만 부수기). 관리자 convert |
| 자재 | 관리인 [자재] 탭, 바닐라 블록 **385가지** (설계 386 − 돌 도끼, R5) · 0.25~1G · 되팔기 없음 |
| 기존 서버 | jar 만 바꾸면 광산 구역 다음 차례로 자리 검사 → 깨끗하면 백업 후 짓기 · 막히면 블록 0 · 잠금 꺼짐 |

---

## 1. 10채 배치 (배포 월드 좌표)

### 1.1 뺀 두 채
| 옛 번호 | 왜 |
|---|---|
| 3 (x −144..−131, z 48..61) | review R1: 마을이 다듬은 칸(기록 높이 68) 10칸 위에 바닥 69 → 마을 자가 진단 floating·얼린 칸 충돌. 빼면 R1 의 3번 문제가 사라진다 |
| 9 (x −178..−165, z 84..97) | 광장에서 가장 멂 (설계 걸음 133). 깎기 179칸으로 가장 많음. 우물길 서쪽 끝(나무 무리 옆)도 같이 줄어든다 |

### 1.2 새 번호
| 번 | 옛 | x | z | 바닥 y (설계) | 짓기 y | 앞 | 대문 | 표지판 | 집 가기 칸 (yaw) | 걸음 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | −178..−165 | 48..61 | 73 | 67..97 | 남 | (−172, 62) | (−170, 62) | (−171.5, 63.5) 180 | 91 |
| 2 | 2 | −163..−150 | 48..61 | 72 | 66..96 | 남 | (−157, 62) | (−155, 62) | (−156.5, 63.5) 180 | 76 |
| 3 | 4 | −129..−116 | 48..61 | 68 | 62..92 | 남 | (−123, 62) | (−121, 62) | (−122.5, 63.5) 180 | 88 |
| 4 | 5 | −178..−165 | 69..82 | 75 | 69..99 | 북 | (−172, 68) | (−170, 68) | (−171.5, 67.5) 0 | 95 |
| 5 | 6 | −163..−150 | 69..82 | 71 | 65..95 | 북 | (−157, 68) | (−155, 68) | (−156.5, 67.5) 0 | 80 |
| 6 | 7 | −144..−131 | 69..82 | 67 | 61..91 | 북 | (−138, 68) | (−136, 68) | (−137.5, 67.5) 0 | 77 |
| 7 | 8 | −129..−116 | 69..82 | 66 | 60..90 | 북 | (−123, 68) | (−121, 68) | (−122.5, 67.5) 0 | 92 |
| 8 | 10 | −163..−150 | 84..97 | 70 | 64..94 | 남 | (−157, 98) | (−155, 98) | (−156.5, 99.5) 180 | 112 |
| 9 | 11 | −144..−131 | 84..97 | 67 | 61..91 | 남 | (−138, 98) | (−136, 98) | (−137.5, 99.5) 180 | 109 |
| 10 | 12 | −129..−116 | 84..97 | 66 | 60..90 | 남 | (−123, 98) | (−121, 98) | (−122.5, 99.5) 180 | 124 |

- 바닥 y 는 설계값이다. 실제 높이는 계획기가 정하고 구역 기록 `plots:` 에 남는다. 시험은 배포 지형에서 설계값 ±1 을 본다.
  **3번은 68 고정** (마을이 다듬은 칸 8칸 — z 48 x −129..−125, z 49 x −129..−127 — 의 기록 높이 68 과 같아야 함, R1).
- 걸음 = 광장 스폰 → 이음 칸 (맨해튼) + 공용 칸 BFS. 가장 먼 집은 10번 124걸음 (12채 때 133).
- 지도 메뉴 (4×3 실제 배치): 윗줄 `1 2 [마당] 3`, 가운데 `4 5 6 7`, 아랫줄 `[빈칸] 8 9 10` (가운데 세로줄 = 골목).

### 1.3 거리·골목
| 칸 | 상자 (x0, z0, x1, z1) |
|---|---|
| 이음 칸 (마을 길 1 첫 칸 (−137, 26..27) 에 붙음, 높이 66·67) | −145, 26, −138, 27 |
| 골목 | −145, 28, −144, 46 |
| 받는 칸 | −148, 47, −144, 47 |
| 가운데 골목 (폭 3) | −148, 47, −146, 98 |
| 등불길 (폭 5) | −179, 63, −115, 67 (그대로 — 1·2·3·4~7번) |
| 우물길 (폭 5) | **−164**, 99, −115, 103 (서쪽 15칸 줄임 — 옛 9번 앞) |
| 골목 마당 (옛 3번 자리) | −144, 48, −131, 61 — 땅은 그대로. 벤치·화단·등불만 z 52 이후 (마을이 다듬은 칸 z 47..49 를 피함). 장식이라 못 놓으면 그 장식만 빠진다 |

- 표시물은 설계 그대로: 관리인 노점 (−145..−143, 63..64) · 모아 (−143.5, 64.5, 남쪽) · 길잡이 (−146, 26) "등불 골목 — 집 1~10번지 · 관리인" ·
  울타리 등불 9개 (같은 자리, 설명만 새 번호) · 골목 끝 우물 (−149..−145, 104..108) · 벤치 (−143..−141, 104).
- 옛 3번 울타리 줄(z 47 · z 62 의 x −144..−131)과 대문·표지판은 없앤다. 옛 9번 둘레 생울타리 가운데 4번 뒤 (z 83) 만 남는다.

### 1.4 다시 돌린 검사 (`work/check10.json`, `design036/plots/tools/review/*` · `judge_under.py`)
| 검사 | 결과 |
|---|---|
| 10채 14×14, 서로 안 겹침, 사이 ≥ 1칸 | 됨 |
| 공용 칸 772칸이 이음 칸에서 모두 이어짐, 10개 대문 바깥 칸 모두 닿음, 집 가기 칸이 공용 칸 | 됨 |
| 집터·공용 칸 vs 마을 보호 상자·마을 길 칸 | 겹침 0. 이음 칸이 길 1 첫 칸에 붙음 |
| 집터·공용 칸 vs 광산 east·south_east 마스크 (실제 jar mine.json, 조각 + slack · 길 + R4 + B6) | 겹침 0. 마스크 서쪽 끝 x −115 = 3·7·10번 동쪽 생울타리 줄 (틈 0) |
| PvP (구역 보호 상자 + safe_margin 8) | 10채 모두 196/196 칸 덮음 (마을 원은 1~3번 일부만) |
| 국경 (마을 + 광산 + 집 구역 + 30) | 광산 east·SE: x −210..−25 · z −51..134 (한 변 185, 장식 상자를 넣으면 ≈ 190). 광산 막힘: x −231..−46. 10채 모두 안 |
| 마을만으로 계산한 국경 (H0 이 없을 때) | 8·9·10번 밖 → 구역 보호 상자를 경계에 넣는 것이 꼭 필요 (0.3.6.1 `protectAll()` 이 이미 넣음) |
| 마을 자가 진단 원 안 마을이 다듬은 칸 | 3번 8칸 (모두 68 = 바닥) · 울타리 줄 · 이음 칸 4 · 골목 7. 옛 3번 10칸은 마당 (안 건드림) |
| 아래 8칸 (빈칸·물·광석) | 1: 57·0·62 · 6: 56·17·16 · 7: 1,061·0·0 · 9: 21·49·17 · 10: 666·0·12 → 흙 3 + 돌 5 로 통째로 바꿈 |

---

## 2. 구역 기계 재사용 — 둘째 구역 `homes`

0.3.6.1 기계는 "구역 id" 를 받지만 광산만 있던 때라 광산 글·설정이 박혀 있다. 묶음 A 가 이렇게 일반화한다.

| 곳 | 지금 | 바꿀 것 |
|---|---|---|
| `DistrictLayout` (`homes.json`) | order·mask·options 는 구역 단위 | `homes.json` order 20 (광산 10 다음) · mask R 2 · B 4 · options `foundation_depth: 8` · `fill_small_water_max: 8` · 조각별 `max_fill` (plot_pad 12, 나머지 4 — Layout.Entry 에 선택 칸 하나) · `safe_margin: 8` |
| 집터 바닥 (`plot_pad`) | 없음 | 계획기: 14×14 한 높이, 위로 열린 구덩이 메움(12칸까지), 바닥 −1..−3 흙 · −4..−8 돌 (동굴·물·광석 통째로 바꿈), 바닥 위 +24 까지 공기·나무 치움. 마을이 다듬은 칸(TRIM)은 높이가 바닥과 같을 때만 허용하고 겉만 그대로 둠 (3번 8칸) |
| `DistrictService.startup` | 차례대로 보고 처음 할 일 하나 하고 끝. 시작 때 한 번 | 구역마다 `DistrictPolicy.onStart(…, prevDone)`. 앞 구역(광산)이 **끝남(built)·막힘·꺼짐(광산 모듈 없음·`mine.enabled: false`·`auto_build: false`)** 일 때만 다음(집) (R8). 한 구역 작업이 끝나면 다음 구역을 바로 이어서 (다시 켤 필요 없음) |
| 설정 | `module.districtConfig()` = `mine.district` 고정 · `mineEnabled()` 로 막음 | 구역별: mine → `mine.district`, homes → `homes.district` (`HomesConfig.fromRoot(...).district()`, 뼈대가 이미 읽음) · homes 는 `homes.enabled` 로 막음 |
| 글 | "광산 마을" 이 박힘 (Blocked 안내·짓기 끝 글·막힘 파일·되돌리기·info) | `L.name` + 구역별 안내 한 줄 (광산 = "광산은 /미궁 광산 으로 그대로", 집 = "집터는 관리자가 convert 로 줄 수 있습니다") |
| 지은 뒤 | NPC · 경계 refresh · 광산 승강장 연결 | + `services.homes().districtChanged(HomesDistrict)` (구역 기록 `plots:` → `PlotGeom` 10개) · 같은 것을 `load()` 마다 |
| 기록 (`labyrinth-district-homes.yml`) | DistrictMeta (pieces·paths·protect·npcs·interact·terrain·region) | + `plots: [{id, box, floor, window, front, gate, sign, home}]` · `yard` (Markers 가 plot_pad 조각에서 뽑음) |
| 지문 | `mine.fp` | `homes.fp` (덮는 범위 = homes 모든 자리 마스크 + 4). 굽는 월드 = 0.3.6.1 `dist/world.zip` (광산 지어짐) + 0.2.0 서버팩 world. **집 구역이 이미 지어진 월드는 뺌** (`has_district` 를 구역 id 로) (R2) |
| 보호 상자 | 조각·길에서 | 거리·골목·이음 칸·받는 칸·울타리/생울타리 줄·대문 기둥·등불·노점·우물·벤치·길잡이·마당 장식. **집 안 14×14 는 넣지 않음** |
| 짓는 동안 보호 | pending 상자 · building 보호 | 그대로 (`DistrictService.setPending`) |
| 되돌리기 | 우리가 놓은 칸만 | homes 는 주인이 있으면 거절, `force` 면 R9 순서 (아래) |
| 명령 | `village district … mine` 기본 | `village district info|preview|build|remove|selftest homes [south_west|here [방향]] [force]` |

짓는 순서 (설계 §10.7 그대로, 10채): 마스크 안 사람 광장으로 → 백업 → building → 나무 → 지형(집터 바닥·구덩이·아래 8칸) →
조각(울타리·생울타리·옹벽·대문 기둥·표지판·등불·노점·우물·벤치·마당) → 길(거리·골목·이음 칸) → 표지판 글 → built → NPC →
빈 `labyrinth-plots.yml` → 색인 → 경계 다시 → PvP 파일 다시 → 잠금 켬 + 이사 기간 시작 + 옛 건물 조사 한 번.

---

## 3. review R1~R12 — 고침과 자리

| R | 고침 | 자리 (파일) | 묶음 | 시험 |
|---|---|---|---|---|
| R1 3번 바닥이 마을이 다듬은 칸 위 | 옛 3번을 뺌 (마당, 땅 그대로). 새 3번(옛 4번) 바닥 68 = 다듬은 칸 높이 → 그 8칸은 겉 그대로 (TRIM 허용 규칙). `VillageSelfTest` 마을 모드가 **구역 기록의 보호 상자·region 열과 집터 상자 열을 floating·tree_remnants 에서 뺌** (집 안에 흙·원목을 쌓아도 마을 진단 통과) | `tools/village/district_homes.py` · `Planner`/`PlanWriter` (plot_pad) · `VillageSelfTest` | A | `HomesLayoutTest` (3번 TRIM 칸 높이 = 68, 다른 집 TRIM 0) · `HomesPlanTest` · 서버: 3번 z 48..49 에 흙·원목 → `[마을 자가 진단]` 통과 |
| R2 흙·돌 건물을 못 잡음 | `homes.fp` 지문 검사 (지표·땅속 10칸·원목) — 광산과 같은 `DistrictCheck`. 이사 기간도 UNNATURAL 만 보므로 "흙·돌 집은 기간에도 못 옮김" 을 README 에 적음 | `district_fingerprint.py --district homes` · `resources/village/districts/homes.fp` · README | A (README 줄은 C) | `district_fingerprint.py --district homes --check` · 서버: 남쪽 들판에 흙·돌 집 → 막힘·블록 0·잠금 꺼짐 |
| R3 맡긴 짐 복제·사라짐 | a) 블록을 다 지우고 `World#save()` 뒤 `ready`, 시작 때 `pending` 이면 지우기 마저 → 저장 → ready. b) 짐은 **월드 폴더** `<월드>/labyrinth-parcels/<uuid>.yml`. c) 셜커는 블록 아이템 하나 (내용 포함), 다른 상자류는 내용 꺼내 비운 뒤 getDrops. d) 섬세한 손길 도구로 `getDrops(tool)` + 겹 반블록·초 개수. e) convert 집 비우기·회수 = 소유만 풂 | `homes/rules/ParcelStore` · `PlotReset` · `HomesService` | B | `ParcelTest` (pending→ready, 두 번 받기 불가, 셜커, 유리·잎·책장·잔디, 겹 반블록, 초 4, 큰 상자 반쪽) · 서버: 비우기 직후 kill −9 |
| R4 권한 구멍 | 상자류 = `BlockState instanceof InventoryHolder` (선반 13·구리 상자 8·제작기·발사기 포함). 남의 집 블록 우클릭·좌클릭 기본 막음 + 허용 목록(문·다락문·울타리 문·작업대류·종). 엔티티: 때리기·끈·털 깎기·양동이 담기·이름표·염색·타기·말/상자 보트/상자 수레 열기·낚싯대 끌기. `PlayerArmorStandManipulateEvent` 따로 · 거치대 폭발·화살 피해. 걸개 = 받침 칸·걸개 칸 둘 다 내 집. 두 칸 블록 위 칸도 같은 창. 발사기: 발사기·앞 칸 같은 집터만, 주 월드 그 밖 취소. `TNTPrimeEvent` 주 월드 취소 · 리스폰 정박기 우클릭 취소. 구리 골렘 `ItemTransportingEntityValidateTargetEvent` zone 다르면 막음. `EntityBlockFormEvent` 집 밖 취소. 잠금 리스너가 `EntityPlaceEvent`·`VehicleDestroyEvent`·`SignChangeEvent`·끈·엔티티 양동이를 직접 취소 (글 한 번) | `homes/rules/PlotRules` (순수 표) · `PlotRulesListener` · `TerrainLockListener` · `CrossZoneListener` | B | `PlotRulesTest` (표 그대로 + 26.3 블록) · `CrossZoneTest` · 서버 (f)(g) |
| R5 자재 목록이 자기 규칙을 어김 | 돌 도끼 뺌 (385가지). 건축 도구 허용 목록 = 나무·돌 괭이, 돌 삽, 돌 곡괭이, 가위. 시험 규칙 "녹이면 조각이 나오는 것(쇠·금 도구·갑옷)은 팔지 않음". chest·campfire 메모 고침 | `tools/data/037/housing_catalog.json` · `tools/gen_037_housing.py` · `content/housing.yml` | C | `HousingCatalogTest` · `gen_037_housing.py --check` |
| R6 경계가 줄 수 있음 | 자동 경계 = **지난번 우리 경계와 합친 상자** (줄지 않음). 줄이기는 `/labadmin wild border apply` (force) 만. `district remove` 도 경계를 줄이지 않음 | `WildBorder.decide`·`WildService.applyBorder` | A | `WildBorderTest` (늘기만 · force 는 줄임) |
| R7 얼린 칸에 다른 구역이 다듬은 칸 | **0.3.6.1 이 이미 함** (`FrozenCells.of(village, othersBuilt)` = 마을 + 먼저 지은 구역의 보호 상자·길·다듬은 칸). 집 쪽 일: 광산이 south_east 일 때 광산 띠가 x −115 (3·7·10번 동쪽 생울타리 줄) 에 닿는다 → 그 칸이 TRIM 이면 생울타리는 높이 그대로 겉만 | `Planner` (울타리 줄 TRIM 처리) | A | `HomesPlanTest` (광산 SE 지은 뒤 frozen 에 광산 TRIM 포함, 집 계획 통과) |
| R8 자동 짓기 조건이 영원히 안 맞음 | 앞 구역 "끝남·막힘·꺼짐(모듈 없음 포함)" 이면 다음 구역. 작업이 끝나면 바로 다음 | `DistrictPolicy.onStart` · `DistrictService.startup` | A | `DistrictPolicyTest` (mine built/blocked/off/none × homes) · 서버 (c) `mine.enabled: false` |
| R9 주인이 있는데 구역을 지움 | `district remove homes` → 주인이 있으면 거절 (몇 채인지 알림). `force`: ① `homes().reclaimAll()` (모두 맡긴 짐으로, 끝날 때까지 기다림) ② 블록 되돌리기 ③ `homes().districtRemoved()` (소유·색인 지움, 잠금 auto) | `VillageCommands`·`DistrictService` (A) · `HomesService.reclaimAll/districtRemoved` (B) | A+B | `DistrictRemoveRuleTest` · 서버 (e) |
| R10 단 사이 벽 | 이웃 바닥 차 ≥ 2 인 줄에 옹벽 (돌벽돌 + 이끼 돌벽돌, 위에 생울타리): 4|5 (75|71) · 5|골목|6 (71|67) · 8|골목|9 (70|67) · 2|골목 (72) · 4번 뒤 z 83 (75 vs 들판) 등. 울타리·생울타리 줄 보호 상자 높이 = 낮은 쪽 바닥 −8 ~ 높은 쪽 바닥 +3. 집터 사이에 zone −1 칸 없음 (울타리 줄 = 보호 상자 = zone 0) | `pieces_homes.py` (옹벽 조각) · `Markers` (울타리 줄 상자 높이) | A | `HomesPlanTest` (울타리 줄 상자가 집터 둘레를 빈틈없이 덮음) · 자가 진단 `blocked_doors=0` · `path_steps=0` |
| R11 집 가기가 "마을 텔레포트 끔" 을 우회 | `homes.home_teleport: auto` (= `village.teleport_command`), `homes.visit: auto` 도 같이. 관리자는 늘 됨 | `HomesConfig.Toggle` · `play/HomeTravel` | C | `HomeTeleportRuleTest` · 서버 (i) |
| R12 광산 → 집 갈 때 게임 모드 | **0.3.6.1 이 이미 규칙 방식** (`MineGameModeRule`: 광산 밖 어드벤처 → 서바이벌, 접속·월드 이동·리스폰·텔레포트 때, 기억 없음). 집 가기는 `Teleports.to` → 월드 이동 → 규칙이 서바이벌로 | `play/HomeTravel` (그대로 씀) | C | `HomeTeleportRuleTest` ("광산 → 집 가기 → 서바이벌" = `MineGameModeRule.target(ADVENTURE, false) == SURVIVAL`) · 서버 (d) |

작게 고칠 것 (R13~R21) 도 모두 넣는다:

| R | 고침 | 묶음 |
|---|---|---|
| R13 비우기 → 다시 받기 되풀이 | 스스로 비운 뒤 다시 받기 24시간 (`reclaim_cooldown_minutes: 1440`) | B |
| R14 옛 건물 조사 깊이 | Scan 과 같은 띠 (땅 위 + 땅속 10칸), `getChunkAtAsync` | B |
| R15 엔티티 수 | 집당 동물 24, 거치대 + 액자 + 그림 64 (번식·알·놓기 때 셈) | B |
| R16 설정 값 자르기 | `shop_price_multiplier ≥ 0.1`, `claim_cost ≥ 0` 등 (`HomesConfig` 가 자름 — 뼈대에 있음) | C |
| R17 묘목 안내 | 가장자리에서 못 자라면 "집터 밖으로 자랄 수 없습니다" 한 줄 | B |
| R18 관리자 명령 | `plot name <번지> <글>` · `plot parcel <이름>` · `plot give` 는 집 있는 사람 거절 | B |
| R19 `changesBlocks` 공개 | 뼈대에서 `VillageService.changesBlocks`·`allowedUse` 를 public 으로 | 뼈대 |
| R20 메뉴가 npcs.yml 없이 열림 | `/미궁 집`·표지판·interact `estate`·메인 메뉴가 NPC 정의 없이 같은 메뉴 | C |
| R21 용암 양동이·화염구 | `deny_place` 에서 빼고 `deny_use` (양동이 붓기·손 아이템 우클릭에서 막음) | B (설정 키는 뼈대) |

H0 (구역 공통) 점검 — 0.3.6.1 이 이미 한 것:
- 경계에 구역 보호 상자 넣기: `VillageService.protectAll()` → `borderTarget()` ✔ (R6 의 "줄지 않음" 만 남음)
- PvP 안전지대: `pvp/VillageZone` 이 `labyrinth-district-*.yml` 의 protect + safe_margin 을 읽음 ✔ (집 구역 파일도 그대로 읽힘)
- 계획기 옵션 max_fill·fill_small_water_max·foundation_depth: 구역 단위로 있음 ✔ (조각별 max_fill 만 더함)
- 얼린 칸 R7 ✔ · 짓는 동안 보호 ✔ · 자연 스폰 막기에 구역 원 ✔
- 우클릭 동작 등록부: 없음 (switch) → 뼈대가 `estate`·`plot:<번지>` 두 갈래를 `services.homes()` 로 넘김 (A·C 가 VillageService 를 같이 만지지 않게)

---

## 4. 데이터 파일

| 파일 | 내용 | 쓰는 쪽 |
|---|---|---|
| `<월드>/labyrinth-district-homes.yml` | DistrictMeta (광산과 같은 틀) + `plots:` [{id, box, floor, window [y0, y1], front, gate, sign [x,y,z], home [x,y,z,yaw]}] + `yard` | A |
| `<월드>/labyrinth-district-homes.backup.gz` | 짓기 전 원래 블록 | A |
| `<월드>/labyrinth-plots.yml` | format 1 · `district_build` (집 구역 build_id — 다르면 주인 기록을 "옛 구역"으로 보고 관리자에게 알림) · `lock {state: auto|on|off, started_at}` · `grace {days, started_at}` · `plots {<id>: owner, owner_name, name, trusted[uuid], guests, claimed_at, starter}` · `custom {c1: {box, window, owner…}}` · `vacated {uuid: 시각}`. 원자적 저장 (tmp → move) | B |
| `<월드>/labyrinth-parcels/<uuid>.yml` | 맡긴 짐: state pending|ready, items (base64 `serializeAsBytes`), from_plot, created_at (R3b — 월드와 같이 다님) | B |
| `plugins/Labyrinth/homes/legacy.txt` | 옛 건물 조사 보고 (관리자용) | B |
| PlayerData ext | `homes.starter_used` (C) · `homes.grace_notice` (B) · `homes.rest_at` (C) | B·C |
| `plugins/Labyrinth/content/housing.yml` | 자재 목록 (jar 기본 복사, ContentParser.FILES) | C |

소유 파일을 월드 폴더에 두는 이유: 월드를 되돌리면 집 주인·맡긴 짐도 같이 맞는다. jar 만 바꾸면 그대로다.

---

## 5. 설정 (`config.yml` `homes:` — 뼈대가 넣음, 키가 없으면 코드 기본값, `homes: false` 면 통째로 끔)

```yaml
homes:
  enabled: true
  terrain_lock: true             # 집 구역이 지어진 뒤에만 켜짐
  district: {auto_build: true, sites: [south_west], blocks_per_tick: 3000, notify_admins: true}
  claim_cost: 0
  max_trusted: 8
  guests_default: true
  height: {below: 6, above: 24}
  reclaim_cooldown_minutes: 1440 # 스스로 비운 뒤 다시 받기 (R13)
  rename_cooldown_minutes: 5
  inactive_days: 60              # 표시만
  legacy_grace_days: 14          # 0 = 이사 기간 없음
  home_regen: {hp: 0.05, mp: 0.05, calm_seconds: 5}
  bed_rest: {seconds: 2, cooldown_seconds: 60}
  home_teleport: auto            # auto = village.teleport_command (R11)
  visit: auto
  starter: {cottage: true, kit: true}
  tick_parts: {total: 16, hoppers: 8}
  entity_caps: {animals: 24, decorations: 64}   # R15
  deny_place: [tnt, tnt_minecart, respawn_anchor, end_crystal, dispenser]
  deny_use: [lava_bucket, fire_charge]          # R21
  shop_price_multiplier: 1.0     # 0.1 아래는 0.1 (R16)
  enter_actionbar: true
```
`foundation_depth`·마스크는 설정이 아니라 `homes.json` (A) 이다. `build_world.sh` 는 `homes.district.auto_build` 를 끄고 명령으로 짓는다 (A).

---

## 6. 명령

- 플레이어 `/미궁 집` (`/lab 집`, `/lab home`): 메뉴 · `가기` · `받기 [번지]` · `초대 <이름>` · `내보내기 <이름>` · `이름 <글>` · `손님 [켬|끔]` ·
  `방문 <이름>` · `짐` · `비우기 [확인]` · `여기` — 명령 등록·글은 C (`play/HomesCommands`), 일은 B (`HomesApi` 의 claim·vacate·invite…).
- 관리자 `/labadmin plot`: `list` · `info [번지|이름]` · `tp <번지>` · `give <번지> <이름>` · `reclaim <번지|이름>` · `convert <이름> <x1> <z1> <x2> <z2> [y1 y2]` ·
  `unconvert <번지>` · `lock <auto|on|off>` · `grace <일>` · `legacy` · `name <번지> <글>` · `parcel <이름>` · `selftest` — B (`admin/HomesAdminCommands`).
- 구역 `/labadmin village district info|preview|build|remove|selftest homes [south_west|here [방향]] [force]` — A.

## 7. NPC

- `npcs.yml` `estate_keeper`: 이름 "마을 관리인 모아", 직함 `[마을 관리인]`, role `estate`, placement overworld, 기존 skin_style 닫힌 목록
  (outfit·hair·accessories 는 GDD "Pack generator templates" 안에서만 — 새 그림 없음), 대사 3줄 (짧고 담백하게).
- 자리: 구역 조각 `keeper_stall` 의 npc 표시 (−143.5, 64.5, 남쪽). 세우기는 구역 기계 (`village-applied.yml districts.homes`).
- role `estate` → `services.homes().openEstate(p)`: `ContentValidator.NPC_ROLES` · `NpcServiceImpl` 분기 (C). 노점 우클릭 칸 interact `estate` (A 가 조각에 표시) 도 같은 메뉴.
- 안내인 대사 한 줄 더: "남쪽 골목으로 가면 집을 받을 수 있어요" (C).
- 스킨: 리소스팩 생성기가 skin_style 로 그림 → 팩 다시 생성·`check_assets.py` (C).

## 8. 메뉴 (C, `play/`)

- **EstateMenu** (관리인·`/미궁 집`·표지판·메인 메뉴, 6줄): 내 집 (가기·이름·손님·초대 목록·비우기) · 집 고르기 · 자재 · 맡긴 짐.
- **ClaimMenu**: 실제 배치 4×3 (1.2 의 지도). 연두 = 빈 집, 금색 = 내 집, 흰색 = 초대받은 집, 빨강 = 남의 집(주인 머리·이름). "아무 데나".
- **StarterMenu** (오두막 7×7 나무 4가지 / 집들이 꾸러미) · **TrustMenu** (머리 클릭 = 내보내기) · **BuildShopMenu** (탭 9 + 쪽 넘김, 왼클릭 1묶음·쉬프트 5묶음,
  골드 먼저 빼고 못 준 만큼 환불) · **ParcelMenu** (45칸 쪽 넘김 + 모두 받기) · **ConfirmMenu** (받기·비우기).
- 메인 메뉴 "집" 버튼 = **15번** (광산이 0.3.6.1 에 13번으로 갔으므로 설계의 52번 대신 그 옆). 미궁 안에서는 숨김.
- 이름 바꾸기: 채팅 입력 도구가 없어 명령을 채팅창에 넣어 줌.
- 글은 짧고 담백하게. 예: "3번지를 받았습니다.", "집터 밖은 부수거나 지을 수 없습니다 — /미궁 집".

---

## 9. 권한·지형 잠금 규칙표 (B)

`zone(x, y, z)` = 집터 키 (높이 창 안) / 0 = 보호 상자 (마을·광산·집 구역 공용) / −1 = 그 밖.
높이 창 밖은 내 집 열이라도 "그 밖". 잠금은 주 월드 (`Bukkit.getWorlds().get(0)`) 만.

| 행동 | 내 집 (주인·초대) | 남의 집 (손님) | 보호 상자 | 그 밖 (잠금 켜짐) | 그 밖 (잠금 꺼짐) | 크리에이티브 관리자 |
|---|---|---|---|---|---|---|
| 부수기·놓기 | O (`deny_place` X) | X | X (마을 핸들러) | X · 이사 기간: UNNATURAL 만 부수기 O | 지금 그대로 | O |
| 물 양동이 붓기·뜨기 | O | X | X | X | 그대로 | O |
| 용암 양동이·화염구 쓰기 (`deny_use`) | X | X | X | X | 그대로 | O |
| TNT·TNT 수레·리스폰 정박기·엔드 수정·발사기 놓기 | X | X | X | X | 그대로 | O |
| TNT 점화·리스폰 정박기 우클릭 | X (주 월드 어디서나) | X | X | X | X | O |
| 상자류 열기 (`InventoryHolder`: 상자·통·셜커·화로류·양조대·깔때기·공급기·독서대·주크박스·장식 단지·조각 책장·선반·구리 상자·제작기·발사기) | O | X | X (지금 그대로) | O (옛 건물) | O | O |
| 엔더 상자 | O | O | O | O | O | O |
| 문·다락문·울타리 문 | O | 손님 허용이면 O | O | O | O | O |
| 작업대류·종 | O | 손님 허용이면 O | 작업대·종만 | O | O | O |
| 버튼·레버·그 밖 블록 우클릭 (화분·가마솥·퇴비통·모닥불·케이크·초·소리 블록·중계기·비교기·벌통·표지판 밀랍·조각상…) | O | X (기본 막음) | X | O (옛 건물) | O | O |
| 압력판·실 밟기 | O | O | O | O | O | O |
| 침대 (리스폰·잠) | O | X | O | O | O | O |
| 걸개 놓기 (받침·걸개 칸 둘 다 내 집) · 돌리기·꺼내기·부수기·쏘기 | O | X | X | X | 그대로 | O |
| 갑옷 거치대 (놓기·`ArmorStandManipulate`·피해) | O | X | X | X | 그대로 | O |
| 보트·수레 놓기·부수기 (`EntityPlace`·`VehicleDestroy`) | O | X | X | X | 그대로 | O |
| 동물 때리기·끈·털 깎기·양동이 담기·이름표·염색·타기·말/상자 보트 열기·낚싯대 끌기 | O | X | — | 그대로 (들판 동물) | 그대로 | O |
| 심기·괭이·뼛가루·삽·도끼 벗기기·붓·가위 (`changesBlocks`) | O | X | X | X | 그대로 | O |
| 밭·거북알 밟기 | X | X | X | X | 그대로 | X |
| 부싯돌 불 (모닥불·초만, 번지지 않음) | O | X | X | X | 그대로 | O |
| 표지판 글 (`SignChange`) | O | X | X | X | 그대로 | O |
| 집 회복·침대 쉬기 | O | X | — | — | — | — |
| PvP | 금지 | 금지 | 금지 | pvp 설정대로 | 같음 | — |

경계 넘는 것 (집터가 하나라도 있으면 늘): 물·용암 흐름 (출발 zone = 도착 zone, 밖→밖 그대로) · 피스톤 (피스톤·움직이는 블록·도착 칸 같은 집터, 집터 밖 피스톤 취소) ·
깔때기·공급기 옮김 (보내는 곳·받는 곳 zone 같음) · 깔때기 줍기 (아이템 zone = 깔때기 zone) · 나무·큰 버섯 (모든 칸이 묘목 zone, R17 글) · 뼛가루 결과 칸 ·
퍼짐 (덩굴·버섯·잔디·이끼·스컬크 같은 zone, 불 퍼짐은 주 월드 전부 취소) · 자람 (호박·수박·사탕수수·선인장·대나무 같은 창) · 불 타기 주 월드 취소 ·
폭발 주 월드 블록 피해 없음 · 엔티티 블록 바꿈 (떨어지는 블록 같은 zone, 나머지 비플레이어 취소) · 눈 골렘 자국·차가운 걸음 집 밖 취소 · 스펀지 다른 zone 안 빨아들임 ·
발사기 같은 집터만 · 구리 골렘 옮기기 같은 zone · 차원문 (플레이어가 붙이는 것은 모든 칸이 자기 집 안, NETHER_PAIR 는 집 하나 안이 아니면 취소 + "/미궁 마을" 안내).

틱 부품: 깔때기·공급기·제작기·피스톤·끈끈이 피스톤·관측기 합 16, 깔때기 8 (그 블록을 놓을 때만 집터 청크 ≤ 4 를 셈). 엔티티: 동물 24, 거치대 + 액자 + 그림 64.

리스너 차례: 잠금 리스너 **LOW** → (주 월드 아님 → 끝) → (집터 → PlotRules) → (`VillageService.isProtected` → 그대로 넘김, 마을 HIGH 가 막고 글 한 번) →
(잠금 켜짐 → 막음). VillageService 보호 핸들러는 고치지 않는다. 글: 풀·꽃(Nature PLANT)은 글 없이 취소, 나머지 2초에 한 번.

잠금 켜짐 = `homes.terrain_lock` && (lock.state on || (auto && 집 구역 built)). convert 집만 있는 서버는 관리자가 `plot lock on` 해야 켜진다.

## 10. 이사 기간 (B)

- 잠금이 **처음** 켜진 날부터 `legacy_grace_days` (14) 일. `labyrinth-plots.yml grace.started_at` 에 한 번 씀 (다시 켜도 다시 세지 않음; `plot grace <일>` 로 바꿈).
- 기간 중: 집터·보호 상자 밖의 `Nature.kind == UNNATURAL` 블록 (판자·유리·상자·횃불…) 만 부술 수 있고 바닐라 드롭 그대로. 놓기는 막힘. 돌·흙·원목·광석은 잠김 (R2 — 흙·돌 집은 기간에도 못 옮김).
- 접속하면 하루 한 번 "이사 기간 n일 남음 — 집터 밖에 지은 것은 그 안에 옮기세요." (ext `homes.grace_notice`).
- 처음 켜질 때 옛 건물 조사 한 번 (R14 띠, 비동기, 8칸 안끼리 묶어 큰 것부터 20곳) → 관리자 로그 + `plugins/Labyrinth/homes/legacy.txt`. 규칙에는 안 씀.

## 11. convert (B)

`/labadmin plot convert <이름> <x1> <z1> <x2> <z2> [y1 y2]` — 가로·세로 ≤ 32, 높이 ≤ 48 (기본 땅 최저 −8 ~ 최고 +24), 보호 상자·다른 집터와 안 겹침,
그 사람의 한 집으로 셈 (이미 집이 있으면 거절), id `c1`·`c2`…, `labyrinth-plots.yml custom`. 시작 선물은 꾸러미만. `unconvert` = 소유만 지움 (블록 그대로, 다시 잠김).
convert 집 비우기·회수 = 소유만 풂 (R3e). 10채가 다 차면 11번째부터 convert.

## 12. 자재 목록 (C)

- 출처: `design036/plots/plots_spec.json` `materials.catalog` (386줄) → `tools/data/037/housing_catalog.json` 에 그대로 옮기고 `stone_axe` 를 뺌 (385).
- `tools/gen_037_housing.py` → `content/housing.yml` (+ `--check`). 값 규칙: 0.25~1G/칸, 원목 = 판자 4개 값, 계단 1.5배, 반블록 0.5배,
  낱개: 상자 5 · 침대 20 · 깔때기 40 · 물 양동이 30. 배율 `homes.shop_price_multiplier`.
- 금지 검사 (생성기 + `HousingCatalogTest`): 쇠·금·구리·다이아·에메랄드·네더라이트 (주괴·조각·블록·광석·원석) · 녹이면 조각이 나오는 도구·갑옷 · 무기·활·쇠뇌·화살·삼지창·철퇴 ·
  TNT·부싯돌·화염구·용암 양동이 · 피스톤·발사기·공급기·제작기·관측기·레일·수레 · 레드스톤 가루·횃불·중계기·비교기 · 엔더 진주·엔더 상자·셜커 · 신호기·스포너·알·명령 블록 ·
  청금석·석영·흑요석·모루·마법 부여대·양조대. 도구는 허용 목록만 (나무·돌 괭이, 돌 삽, 돌 곡괭이, 가위). id 는 `tools/village/blockdata.json` 에 있어야 함.
- 되팔기 없음 (`SellPrices` 가 바닐라를 이미 거절). 광산 부산물 판매 없음.

## 13. 자가 진단 줄

```
[집 구역 자가 진단] 결과: 예외 0 · checked n · mismatched=0 · floating=0 · tree_remnants=0 · blocked_doors=0 · path_steps=0 · junction=ok · plots=10/10 · pads=10/10 · under=10/10 · gates=10/10 · signs=10/10 · homes_safe=10/10 · npc=1/1 · border=ok · pvp_safe=ok
[집터 자가 진단] 결과: 예외 0 · index=ok(2000/2000) · rules=ok(n/n) · owners=n · orphans=0 · over_cap=0 · parcels_pending=0 · lock=on · grace=n일
[집 메뉴 자가 진단] 결과: 예외 0 · catalog=385 · banned=0 · npc_def=ok · menus=ok · home_tp=auto(켬)
```
- 첫 줄 A (`VillageSelfTest` 구역 모드, `village selftest` 끝 · `village district selftest homes`). under = 바닥 −1..−8 전부 고체, homes_safe = 집 가기 칸·머리 칸 공기 + 발밑 고체,
  border = 구역 상자가 지금 WorldBorder 안, pvp_safe = 집터 가운데가 PvP 안전.
- 둘째 줄 B (`HomesApi.selfTestLines()` 의 첫 줄), 셋째 줄 C (`HomesUi.selfTestLine()`). `/labadmin plot selftest` 는 둘째·셋째, `village selftest` 는 셋 다.
- 집 구역이 없으면 첫 줄 대신 "[집 구역 자가 진단] 아직 없음 (state …)" 한 줄, 둘째·셋째는 그대로.

## 14. 시험

**단위**

| 시험 | 묶음 |
|---|---|
| `HomesLayoutTest` (뼈대 — 10채·14×14·안 겹침·대문 줄·BFS·마을·광산 east/SE 마스크·3번 TRIM 68·PvP 덮임) | A |
| `HomesPlanTest` (배포 지형 픽스처로 homes.json 계획: 겹침 0 · 바닥 설계 ±1 · 3번 68 · 이음 ok · 울타리 줄 상자 빈틈 없음 · 광산 SE 뒤에도 통과) · `DistrictPolicyTest` 더함 (R8) · `WildBorderTest` 더함 (R6) · `DistrictRemoveRuleTest` (R9) | A |
| `PlotIndexTest` (무작위 10만 점 vs 전수, 청크 경계, 높이 창, custom) · `PlotRulesTest` (§9 표) · `TerrainLockClassifierTest` · `CrossZoneTest` · `GraceRuleTest` · `TickPartsLimitTest` · `EntityCapTest` · `PlotStoreTest` (yml 왕복·원자 저장·옛 구역) · `ParcelTest` (R3) · `PlotResetPlanTest` · `ClaimRulesTest` (한 사람 한 집·24시간·convert 셈) | B |
| `HomesConfigDefaultsTest` (뼈대 — 키 없음·`homes: false`·자르기) · `HousingCatalogTest` (R5) · `HomeRegenTest` · `BedRestTest` · `HomeTeleportRuleTest` (R11·R12) · `StarterCottageTest` · `ClaimMapTest` (4×3 지도 칸 ↔ 번지) · `EstateRoleTest` (ContentValidator) | C |

**서버** (검증 단계, 칸 B `/tmp/labyrinth-srv2.lock`, 포트 25901~25949, Xmx 3G, 사본만 online-mode=false):
(a) 0.3.6.1 서버팩 world 사본 + 0.3.7 jar → 로그 "광산 마을 지음/이미 있음" → "집 구역 지음 (south_west)" · 자가 진단 세 줄 예외 0 · 경계 늘기만 · 1~10번 PvP 0.
(b) 남쪽 들판에 흙·돌 집 → 막힘, 블록 변화 0, 잠금 꺼짐. (c) `mine.enabled: false` → 집 구역 지어짐. (d) 광산에서 `/미궁 집 가기` → 서바이벌, 블록 놓기 됨.
(e) 비우기: 셜커·큰 상자·유리·겹 반블록·초 4 → 맡긴 짐 개수 정확 · 비우기 직후 kill −9 → 상자와 짐 중 하나만. `district remove homes` 주인 있으면 거절, force 면 짐으로.
(f) 손님: 선반·구리 상자·제작기·화분·가마솥·거치대·액자·말·상자 보트·낚싯대·끈 막힘, 초대한 친구는 됨. (g) convert 집의 옛 발사기가 물·뼛가루를 집 밖으로 못 냄.
(h) 3번 z 48..49 에 흙·원목 → `[마을 자가 진단]` 통과. (i) `village.teleport_command: false` → 집 가기·방문 꺼짐.
(j) 이사 기간: 판자 부수기 O·돌 X, 기간 뒤 부수기 X·상자 열기 O. (k) 새 world.zip 으로 처음 켜기 → 아무것도 다시 짓지 않음, 잠금 켜짐.
봇: `int361/final/play/tools/`·`owner/tools/` 를 `pl37/` 로 복사해 씀 (구역 업그레이드 검사·region 읽기).

## 15. 문서

- `VILLAGE.md §8 집 구역` (자리·조각·검사·계획기 옵션·옹벽·지문) — A
- `README.md` "집 (0.3.7)" + 업데이트 안내: "jar 만 바꾸면 광산 다음 집 구역이 지어지고, 그날부터 14일 이사 기간. 남쪽 들판에 건물이 있으면 짓지 않고 관리자에게 알림.
  흙·돌로 지은 것은 이사 기간에도 못 부숨 — 관리자가 convert 로 집터로 바꿀 수 있음" — C
- `GDD.md` 집·지형 잠금·자재·회복·맡긴 짐 — C · `ARCHITECTURE.md` `kr.labyrinth.homes`, 데이터 파일, 이벤트 차례 (LOW 잠금 → HIGH 마을), HomesApi — C
- `config.yml` `homes:` 주석 — C (뼈대가 첫 판을 넣음)

## 16. world.zip 다시 만들기 (A)

1. `df -h /` 확인 (3 GB 미만이면 자기 사본 지움).
2. `homes.fp`: `district_fingerprint.py --district homes --world dist/world.zip(0.3.6.1, 7071ad91) --world <0.2.0 서버팩 zip>` (집 구역이 이미 있는 월드는 뺌) → `--check`.
3. `tools/build_world.sh --base <0.3.6.1 dist/world.zip> --district homes south_west`: 마을·광산은 그대로, `labadmin village district build homes south_west` →
   `village selftest` (세 줄) → `village district info homes` → zip. `--base` 가 "광산이 이미 있으면 멈춤" 을 구역 id 별로 (`--district` 의 id 만 없어야 함).
   config 사본: `homes.district.auto_build: false` · `homes.enabled: true` · 광산·야생 끄기는 지금처럼.
4. `release.sh` 검사 더함: `labyrinth-district-homes.yml` state built · `labyrinth-district-homes.backup.gz` 있음 · `labyrinth-plots.yml` 이 없거나 주인 0 · `labyrinth-parcels/` 없음.
5. 새 world.zip 의 village build_id 는 그대로 (마을을 다시 짓지 않음) → 광산 `mine.fp`·`homes.fp` 의 build_id 목록과 맞음.

---

## 17. 계약 (뼈대 커밋이 넣은 것 — 세 묶음이 같이 씀)

`kr.labyrinth.homes`:
- `HomesApi` — `services.homes()` (기본 `NoopHomesApi`, `HomesModule` 이 `HomesService` 로 바꿈). 상태 (`enabled`·`districtBuilt`·`isTerrainLocked`), 자리 (`plotAt`·`plot`·`plots`·`zone`),
  사람 (`ownerOf`·`homeOf`·`roleIn`·`canBuild`·`canOpen`·`info`), 일 (`claim`·`vacate`·`invite`·`kick`·`rename`·`setGuests`·`parcel`·`takeParcel`), 구역 (`districtChanged`·`ownedCount`·`reclaimAll`·`districtRemoved`),
  메뉴 (`openEstate`·`openPlotSign` → `HomesUi`), 자가 진단 (`selfTestLines`). 바꿀 때는 **더하기만** (default 메서드).
- `PlotGeom` (집터 모양: id·zoneKey·상자·바닥·높이 창·앞·대문·표지판·집 가기 칸·custom) · `HomesDistrict` (구역 상태·build_id·집터들) · `PlotRole` · `PlotInfo` · `HomesResult`.
- `HomesUi` (C 가 구현: 메뉴 열기·표지판 다시 쓰기·받은 뒤 선물·자가 진단 줄) · `NoopHomesUi`.
- `HomesConfig` (설정 전부 + 자르기) · `HomesLayout` (배포 월드 10채 순수 자료) · `HomesModule` (켜기: 설정 → HomesService → 규칙 리스너(B) → 놀이 연결(C) → 명령).
- 리스너 빈 틀 (`homes.enabled` 일 때만 등록, 처리기 안에서 `active()`): `rules/PlotRulesListener`·`rules/TerrainLockListener`·`rules/CrossZoneListener` (B) · `play/HomeCareListener` (C).
- 명령 빈 틀: `admin/HomesAdminCommands` (B) · `play/HomesCommands` (C).
- 바깥 연결: `Services.homes()/setHomes()` · `LabyrinthPlugin` 모듈 차례 Village → Mine → Homes · `VillageService.openMenu` 의 `estate`·`plot:<번지>` 갈래 ·
  `VillageService.allowedUse/changesBlocks` public (R19) · `config.yml homes:`.

## 18. 묶음 (파일 소유 — 한 파일은 한 묶음만)

순서: 뼈대 → (A ∥ B ∥ C) → 합치기·검증. A·B·C 는 서로 계약(17)만 보고 동시에 한다. 합치기 순서 A → B → C (C 가 문서·버전).

**A "district"** — 소유: `plugin/src/main/java/kr/labyrinth/village/**` · `pvp/VillageZone.java` · `homes/HomesLayout.java` · `homes/PlotGeom.java` · `homes/HomesDistrict.java` ·
`plugin/src/main/resources/village/**` · `plugin/src/test/java/kr/labyrinth/village/**` · `plugin/src/test/java/kr/labyrinth/homes/HomesLayoutTest.java` · `plugin/src/test/resources/village/**` ·
`tools/village/**` · `tools/build_world.sh` · `release.sh` · `dist/world.zip` (+ `.seed`) · `VILLAGE.md`.
일: `pieces_homes.py` (plot_pad · 울타리/생울타리 줄 · 옹벽 · 대문 기둥 + 표지판 · keeper_stall (npc estate_keeper + interact estate) · lamp_post_small · signpost_home · 마당 장식, well·bench 재사용) ·
`district_homes.py` (10채 배치, 자리 south_west, 표지판 interact `plot:<번지>`) · build_all → `homes.json`·index · `homes.fp` · 계획기 plot_pad (바닥 −8 → 흙 3 + 돌 5, 구덩이 12, TRIM 허용) · 조각별 max_fill ·
DistrictService/Job/Policy 구역 일반화 + "광산 다음 집" (R8) · 기록 `plots:` · `homes().districtChanged` · 보호 상자 높이 (R10) · 얼린 칸 (R7 점검) · R6 경계 · R9 remove ·
VillageSelfTest 구역 줄 `[집 구역 자가 진단]` + 마을 줄에서 구역·집터 열 빼기 (R1) + B·C 줄 붙이기 · VillageCommands homes · build_world.sh `--district` · release.sh 검사 · world.zip.

**B "rules"** — 소유: `homes/HomesApi.java` · `homes/NoopHomesApi.java` · `homes/HomesService.java` · `homes/PlotRole.java` · `homes/PlotInfo.java` · `homes/HomesResult.java` ·
`homes/rules/**` · `homes/admin/**` · `plugin/src/test/java/kr/labyrinth/homes/rules/**` · `…/homes/admin/**`.
일: PlotIndex (청크 → 집터, 구역 + custom) · PlotStore (`labyrinth-plots.yml`) · 받기·비우기·초대·내보내기·이름·손님 · ParcelStore (R3) · PlotReset (바닥 틀로) ·
PlotRules + 3 리스너 (R4 전부, R17, R21) · TerrainLock (LOW, 보호 상자 넘김, 글 한 번) · 이사 기간 (10) · 틱 부품·엔티티 한도 (R15) · 옛 건물 조사 (R14) ·
관리자 명령 (11, R18) · reclaimAll/districtRemoved (R9) · `[집터 자가 진단]` · 24시간 (R13).

**C "play"** — 소유: `homes/HomesModule.java` · `homes/HomesConfig.java` · `homes/HomesUi.java` · `homes/NoopHomesUi.java` · `homes/play/**` ·
`plugin/src/test/java/kr/labyrinth/homes/play/**` · `…/homes/HomesConfigDefaultsTest.java` · `Services.java` · `LabyrinthPlugin.java` · `plugin/src/main/resources/config.yml` ·
`content/npcs.yml` · `content/housing.yml` · `core/ContentParser.java` (FILES 한 줄) · `core/ContentValidator.java` · `mobs/npc/NpcServiceImpl.java` · `ui/menus/MainMenu.java` ·
`tools/gen_037_housing.py` · `tools/data/037/**` · `labyrinth/resourcepack/**` (생성물) · `README.md` · `GDD.md` · `ARCHITECTURE.md`.
일: 관리인 모아 (npcs.yml · estate 역할 · 스킨 생성) · `/미궁 집` 명령 · 메뉴 6가지 + 지도 · 표지판 메뉴·글 · 들어설 때 액션바 · 집 회복·침대 쉬기 · 집 가기·방문 (R11·R12) ·
시작 오두막·꾸러미 · 자재 탭 (R5, R16) · 메인 메뉴 15번 · 안내인 한 줄 · `[집 메뉴 자가 진단]` · README·GDD·ARCHITECTURE·config 주석.

고정 (뼈대 뒤 아무 묶음도 안 만짐): `labyrinth/design/037/**` (이 계획·10채 자료·검사 도구), `VillageService.openMenu` 의 estate·plot: 두 줄.

같이 쓰는 것 규칙:
- A 는 `HomesConfig.fromRoot(cfg).district()` 를 읽기만 한다 (C 파일). B·C 는 `VillageService.isProtected`·`changesBlocks`·`spawn()`·`Nature.kind` 를 읽기만 한다 (A 파일).
- `HomesApi` 를 바꿔야 하면 B 가 **default 메서드로 더하기만** 하고 A·C 에 알린다. `PlotGeom`·`HomesDistrict` 는 A 가 더하기만.
- 버전 번호 (`build.gradle` 등) 는 합치기 때 한 번 (묶음은 안 만짐).
- 팩 생성은 C 만 (`flock /tmp/ic362-build.lock`). 빌드는 모두 `flock /tmp/pl37-build.lock`.

## 19. 위험

- 계획기가 고른 바닥이 설계값과 다를 수 있다 → 시험이 ±1, 3번은 68 고정. 바닥이 바뀌면 옹벽 줄도 다시 (A 가 지은 기록으로 계산).
- 광산 south_east 서버: 광산 띠가 x −115 줄에 닿음 → 울타리 줄 TRIM 처리 필요 (R7 줄).
- 라이브 서버 남쪽 들판에 건물이 있으면 자동 짓기가 막힌다 (안전, 관리자 손 필요).
- 이사 기간에는 누구나 남의 옛 판자를 부술 수 있다 (블록 주인 기록 없음). 친구 서버라 받아들일 만하고, 싫으면 0일.
- 7·10번 밑 8칸보다 깊은 동굴은 남는다 (높이 창 밖이라 잠김, 0.3.5.1 이 자연 스폰 막음).
- 네더·엔드는 0.3.5.1 대로 열려 있다 (네더 블록이 공짜 자재가 되지만 팔 수 없어 골드와 무관).
