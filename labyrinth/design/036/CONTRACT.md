# 0.3.6 계약 (Q0) — 광산 · 광산 마을 · 광석 재료

이 문서는 0.3.6 을 나눠 만드는 다섯 패키지(Q1~Q5)가 함께 지킬 약속이다.
숫자와 id 의 원본은 `labyrinth/tools/data/036/` 의 JSON 4개다. 이 문서의 표는 그 JSON 과 같다.

- `mine.json` — 광산 월드, 층 6개, 광석 6, 보석 6, 곡괭이 6, 캐기 규칙, config 기본값, 이름(interact·역할·ext·파일·명령)
- `materials.json` — 새 아이템 27개(이름·희귀도·판매가·얻는 곳 글), 제련·새기기·곡괭이 레시피, 옛 8개 바꿈 표, 생성기 규칙
- `visual.json` — 광석·보석 블록 12개, 빈 광맥 블록, 아이콘·곡괭이·보석 결정 그림 값, 층 분위기, NPC 스킨, 메뉴 배경
- `district.json` — 광산 마을 자리·건물·길·NPC 자리·보호 상자·지문 규칙·기존 월드 적용 절차

설계 숫자는 `tools/data/036/model/params.py` 한 곳에서만 고친다. 고친 뒤:

```
cd labyrinth
python3 -B tools/data/036/model/run_all.py      # 청사진 시안 → 콘텐츠 시제품 → 경제 표 → JSON 4개 → 검사
python3 -B tools/data/036/check_contract.py     # 검사만 (오류 0 이어야 함)
```

JSON 을 손으로 고치지 않는다. `check_contract.py` 가 JSON 이 `params.py` 와 다르면 오류를 낸다.
경제 표(§5)를 바꿨으면 이 문서의 §5 도 `model/out/economy.md` 로 바꿔 넣는다.

설계 입력: `design036/mine_spec`(M) · `materials_spec`(T) · `visual_spec`(V) · `review036.md`(R). 주인 결정(§1)이 이 넷보다 앞선다.

---

## 1. 주인 결정 (최종)

| # | 결정 | 이 계약에서 |
|---|---|---|
| 1 | 금속 6: 구리·철·은·금·미스릴·오리하르콘. 보석 6: 석영·석류석·월장석·황옥·청옥·용혈석. 별철·흑요석은 없다 | id `<금속>_ore`·`<금속>_ingot`·`<금속>_pickaxe`, 보석 `quartz`·`garnet`·`moonstone`·`topaz`·`sapphire`·`dragonblood_stone` (§3) |
| 2 | **레벨 조건이 어디에도 없다.** 곡괭이·승강기·광산 층 모두. 6층 모두 처음부터 열림 | 곡괭이 tier 는 (a) 빠르기 (b) 캘 수 있는 광석만 정한다. 광석 tier ≤ 곡괭이 tier. 못 캐면 진행 없음 + 액션바 "곡괭이가 약해 캘 수 없습니다". **R §2-6(level_req 검사)은 이 규칙으로 바뀐다.** 친구가 준 곡괭이를 써도 된다 |
| 3 | 층마다 깊이·분위기·**광석 섞임**이 다르다 | 모든 층에 광석이 3~6종 섞인다. 위층은 구리·철 + 은 조금, 깊을수록 금·미스릴·오리하르콘, 가장 깊은 층은 모두 있고 오리하르콘 몫이 가장 크다. 보석도 섞인다 (§4.1) |
| 4 | 레시피 금속은 **장비의 힘·희귀도**로 고른다 (띠 표 아님). 이웃 두 금속을 섞을 수 있다. ING_SHARE = 0.20. 광석·주괴·곡괭이·광산 층 글에 Lv·띠·층 표지 없음 | §2.7 힘 규칙. 검사 `NoLevelLabels` |
| 5 | R 권장대로: 따로 된 광산 월드 + 승강기 · 동쪽 자리(+ 남동쪽) · 개인 광맥 · 곡괭이 안 부서짐 · 첫 구리 곡괭이 무료 · 옛 재료 1:1 · 제련소 새기기 · 바닐라 블록 광맥(종류마다 다른 블록 12개 + 층마다 빈 광맥 블록) · 광석 날아오기 켬 · 기력 하루 상한 · 모든 층 던전 광석 조금 · 5·7·9층 새 몬스터 재료 · 기존 월드 자동 짓기(지문·백업·되돌리기) + 관리소 · 광산 안전 · 야생 경계에 구역 포함 · 설정 자리(R §3-16) | §2 전부 |
| 6 | 새 NPC(광부·제련공)는 V 방향 + **기존 NPC 스킨과 같은 그림 수준** (큰 눈·잔무늬 다시 그리기 거절) · 제련공 한국 이름 | 같은 `npc_skins.paint_skin` + GDD §14.5 닫힌 목록만. 이름 **광부 브론 · 제련공 이그나** |
| 7 | 몹 주제 드롭·상자 모양 미믹은 따로 설계 (`design036/drops/`) | Q3 가 재료 규칙 다음 단계로 얹는다 (§2.12) |

M·T·V 와 달라진 큰 것:
- 층 5 → 6. 층마다 광석 1종 → 섞임. 곡괭이 "n층까지" → "tier ≤ n 광석".
- 레시피 금속: 단계 띠 표(ceil(t/2)) → 힘 규칙 + 섞기. ING_SHARE 0.35 → 0.20.
- 블록: 층마다 2개 → 광석·보석 종류마다 1개 (12개).
- 기력: 240 / 1분 4 → 1,200 / 1분 1, 블록마다 0.75 (§2.4).
- 곡괭이 벼리기: 대장간 → 제련소·관리소 (마을 없이도 진행이 막히지 않게).
- 보석 판매 base 12 → 6 (광산 골드를 던전의 20% 안으로).
- R §2-1 의 "대장간 메뉴에도 제련 탭(권장)" 은 두지 않는다 — 관리소가 마을·구역 없이도 열리므로 그것으로 갈음한다.
- R §2-8 보강: 바닐라 서버는 블록 부수기를 5.5 칸까지 받는다. 그래서 광산이 손 닿는 거리를 서버에서 다시 본다 (§2.3).

---

## 2. 규칙

### 2.1 광산 월드

- 이름 `labyrinth_mine`. 공허 월드(`dungeon/VoidGenerator` 재사용). 지우지 않는다. 26.x 에서는 `world/dimensions/minecraft/labyrinth_mine` 에 생긴다 → `build_world.sh` skip_dirs, `release.sh` 는 zip 에 있으면 실패.
- 층 6개가 같은 x,z (−30..30) 에 위아래로 쌓인다 (청크 16개). 상자 = [바닥 y − 4, 바닥 y + 15].
- 규칙: `LabyrinthWorld.applyRules` 와 같음(몹 스폰 끔·스폰 한도 0·불 번짐 0·무작위 틱 0·시간 멈춤·keepInventory) + PvP 끔.
- 청사진은 정적이다 (`mine/levels/L1..L6.json`, 61×16×61). 마커 `lift`·`landing`·`office`·`vein`·`gem`·`sign`·`ambient`·`light`.
  - 팔레트 논리 글자 `@vein:<광석 id>`·`@gem:<보석 id>` 를 짓는 순간 블록으로 바꾼다. 블록을 바꿔도 청사진은 그대로다.
  - `<광산 월드>/labyrinth-mine.yml` 에 층마다 청사진 해시. 해시가 바뀐 층만 다시 짓고, 그 층 사람은 승강장으로, 그 층 광맥 기록은 지운다.
- 원형 평면 시안: `tools/data/036/model/out/L1.txt`~`L6.txt` (layout6.py). Q1 이 최종 청사진을 만든다.

### 2.2 안전 (R §2-2·2-3·2-4)

- 피해 0: `DamageService.applyToPlayer` 와 상태 이상 진입점에서 광산 월드면 피해를 0 으로. `EntityDamageEvent` 취소만으로는 부족하다(스킬·지속 피해가 `setHealth` 로 들어옴).
  바닐라 피해 `EntityDamageEvent`(떨어짐·**마그마 블록 = 용혈석 노드**·질식·불 등)도 광산 월드면 모두 취소한다.
- `TargetFilter.inSafeZone(광산 월드) = true`. `PvpModule.applyWorldRules` 는 광산 월드 PvP 를 늘 끈다.
- 게임 모드는 **기억 없이 규칙만**: 광산 월드 안 = ADVENTURE, 광산 밖인데 ADVENTURE = SURVIVAL, CREATIVE·SPECTATOR 는 건드리지 않는다. 접속·월드 이동·리스폰·텔레포트 때 같은 규칙. ext `mine.prev_mode` 는 없다.
- 몹 0: `EntitySpawnEvent` 는 종류 화이트리스트(MANNEQUIN·ITEM_DISPLAY·BLOCK_DISPLAY·TEXT_DISPLAY·INTERACTION·ITEM)만 통과, 30초마다 광산 월드 Mob 을 지운다, selftest `mobs=0`.
- 배고픔 안 줄어듦 · 엔더 진주·후렴과 텔레포트·양동이 막음 · 바닥 아래로 떨어지면 그 층 승강장으로 · 들어올 때 HASTE·CONDUIT_POWER 지움.

### 2.3 캐기

- 광맥 = **진짜 바닐라 블록**. 서버 블록은 늘 광석이다. 캔 사람에게만 그 층 빈 광맥 블록을 보낸다(개인 광맥, `sendBlockChanges`).
- 캐는 모습은 바닐라 그대로: 어드벤처 + 곡괭이 `CAN_BREAK` + `Tool` 규칙(블록마다 speed, `correct_for_drops = TRUE`).
- 초 = 광석 `base_seconds` ÷ 곡괭이 `speed[광석 tier]`. 서버가 `speed = 30·단단함(Material#getHardness) ÷ (20·초)` 로 바꾼다. 보석 노드는 `gems.base_seconds` (같은 등급 광석의 1.5배). 어떤 조합도 1.0초보다 빠르지 않다.
- **tier 규칙**: 광석·보석 tier ≤ 곡괭이 tier 일 때만 캔다. 아니면 금도 안 가고(CAN_BREAK 밖) 액션바 `곡괭이가 약해 캘 수 없습니다` (1초에 1번, 팔 휘두름 + 5칸 시선 검사).
- `BlockBreakEvent` 는 늘 취소하고 서버가 다시 본다: 광산 월드 · 곡괭이 tier ≥ 광석 tier · **그 사람에게 고갈이 아님** · **눈 → 블록 상자 거리 ≤ 4.5 + 0.25** · 가방 자리. 하나라도 아니면 수확 없음 (`mine.json` `rules.server_recheck`).
  - 거리 한도를 두는 까닭: 바닐라 서버는 `isWithinBlockInteractionRange(pos, 1.0)` 으로 5.5 칸까지 받는다(26.3 `ServerPlayerGameMode.handleBlockBreakAction`). 고친 클라이언트로 5.5 에서 캐면 시안 청사진에서도 한 자리 광맥이 12~15개가 된다.
- 수확은 가방에 바로. 가득 차면 캐지지도 비워지지도 않는다. 바닐라 드롭·경험치 없음.
- 다시 보내기: **취소한 칸만** 1틱 뒤 (R §2-13, 6 이웃 아님). 그 밖에 `PlayerChunkLoadEvent`·텔레포트·승강기·우클릭 뒤·고갈 칸 `BlockDamageEvent` 때.
- 수확 = 블록마다 광석 1 + 곡괭이 덤 확률로 +1. 광석 블록마다 2.2% 로 **같은 등급 보석** 1. 보석 노드는 1개, 30분 재생. 풍부한 광맥: 다시 찰 때 4% 로 그 사람에게만 반짝이고 ×3.
- 재생은 개인·실제 시간(오프라인에도 흐름). 기본 분 = 층 1~6: 8 · 9 · 9 · 10 · 10 · 10 (config 손잡이).
- 광맥 번호 = 청사진 마커 (y, z, x) 정렬 순. 기록 ext `mine.depleted`.
- 한 자리 손 닿는 광맥 ≤ 12. 재는 법(R §2-8): 발 = 바닥+1, 눈 = 바닥+2.62, 선 자리 아무 곳(몸 폭 0.6), 눈 → 블록 상자의 가장 가까운 점 ≤ 4.5. 시안 최대 9~10.
  - 같은 방식으로 서버 한도 4.75 에서도 ≤ 12 여야 한다. 시안은 10~12 다.
  - 밟고 설 수 있는 장식(통·울타리·계단 등) 위도 선 자리로 잰다.
- 광산 밖에서 그 곡괭이로 광산 블록 12종을 부수면 취소 + 안내 1초에 1번 (R §3-15). "광산 밖" 에는 오버월드·네더·엔드와 **미궁 월드**가 모두 든다.
  - 미궁도 이 블록을 쓴다: 2층 벽 구리·철 광석 · 6·7층 방해석 · 4·6·7층 바다 랜턴 · 5층 마그마. `DungeonManager` 가 이미 부수기를 막으므로 안내 글만 더한다. 미궁 모양은 바꾸지 않는다 (check_contract 가 겹치는 층을 알려 준다).

### 2.4 기력 (R §3-11, 주인 결정 5)

- 최대 1,200, 1분에 1 회복 (오프라인 포함), 블록(광맥·노드)마다 0.75. 바닥이면 수확 ×0.3 (끊지 않음). 보스 처치 충전 없음.
- 보스바는 광산 월드 안에서 25% 아래일 때만.
- 블록마다 0.75 로 정한 이유: 6층이 모두 열려 여러 층을 돌면 정직한 속도가 ~13.6 블록/분이다. 쉬는 틈(제련·팔기·이동) 1/4 을 넣으면 약 3시간 동안 닿지 않는다 (§5 표 F). 최대·회복은 주인 결정 그대로.

### 2.5 승강기 · 관리소 · 오가기

- 승강기 메뉴: 6층 모두 깊이 순 + "마을로". **잠김 없음.** 2초 어둠 + 쇠사슬·수레 소리, 움직이면 취소. 도착 부제목 = `<층 색>층 이름` (층 번호 글자 없음).
- **광산 관리소** (R §2-1): 얕은 갱도 승강기 홀 북쪽 벽감의 우클릭 칸 `mine_office`. 탭: 곡괭이(첫 1개 무료, 이후 구리 곡괭이 50G) · 제련(×1·×8·전부) · 새기기 · 곡괭이 벼리기 · 팔기(SellMenu 그대로, 도구는 못 팜) · 광맥 현황·기력.
  메뉴는 코드로 만든다. npcs.yml 정의가 없어도, 마을·구역이 없어도 열린다. 구역의 광부·제련공 NPC 는 같은 메뉴의 얼굴이다.
- `/미궁 광산` (`/lab mine`)·메인 메뉴 "광산": 구역이 있으면 승강장으로, 없으면 얕은 갱도 승강장으로. 미궁 안에서는 못 씀. `village.teleport_command: false` 서버는 기본 끔 (config `mine.teleport_command: auto`).
- 마을로: 구역 승강장 `mine_exit` 에, 구역이 없으면 마을 광장에.

### 2.6 곡괭이

- `type: tool` (ItemType.TOOL). 장비가 아니다: 능력치·강화·요구 능력치·판매 없음, 한 칸에 1개, 내구도 없음(UNBREAKABLE 숨김).
- 바탕 아이템은 지금 재료처럼 `PAPER` 다(ENCHANTABLE 없음). 효율 마법·모루로 §3.4 속도표가 깨지지 않게 하려는 것이다. MAX_STACK_SIZE 1.
- items.yml `tool: {kind: pickaxe, tier, speed: {광석 tier: 배율}, bonus}`. `level_req` 를 적지 않는다.
- 구성요소(Q1 `MineApi.applyPickaxe`): Tool 규칙(블록마다 speed), CAN_BREAK(tier 이하 광석·보석 블록), UNBREAKABLE, 공격 속성 비움, TOOLTIP_DISPLAY 로 바닐라 줄 숨김. 블록 설정이 바뀌면 접속 때 다시 쓴다.
- 벼리기 레시피는 **제련소 `station: smelter`, `category: tool`** (마을 대장간이 아님 — 관리소에서도 된다). 앞 곡괭이를 재료로 넣으면 앞 곡괭이는 사라진다.
- 구리 곡괭이: 시작 꾸러미 + 관리소·광부에게서 첫 1개 무료(ext `mine.free_pickaxe`) + 잃으면 50G.

### 2.7 장비 레시피의 금속 (주인 결정 4)

- 힘 `P = 단계(tier) + 희귀도 걸음 + (보스 장비면 0.5)`. 희귀도 걸음: common 0 · uncommon 0.25 · rare 0.5 · epic 1.0 · legendary 1.5 · mythic 2.0.
- 자리 `pos = clamp(1 + (P − 1)/2, 1, 6)` → 1 구리 … 6 오리하르콘.
- `pos` 의 소수부 f: f < 0.375 → 아래 금속만, f > 0.625 → 윗 금속만, 그 사이(양끝 포함) → **이웃 두 금속을 섞음** (윗 금속 개수 = 반올림(n·f), 둘 다 1개 이상).
- 주괴 개수 n = 반올림(옛 일반 재료 개수 합 × **0.20**), 최소 2. 옛 일반 재료 = 그 층 몬스터 재료 + 광물 재료.
- 주괴는 몬스터 재료 바로 뒤(정예·정수·핵 앞), 아래 금속 먼저. 몬스터 재료 개수·골드는 그대로. 레벨 조건을 새로 넣지 않는다.

| 장비 (단계/희귀도) | pos | 금속 (주괴 10개일 때) |
|---|---|---|
| 1 일반 · 1 고급 | 1.0 · 1.125 | 구리 |
| 1 희귀 보스 · 2 고급 | 1.5 · 1.625 | 구리 5 + 철 5 · 구리 4 + 철 6 |
| 3 희귀 | 2.25 | 철 |
| 3 영웅 보스 · 4 희귀 · 4 영웅 · 5 희귀 | 2.75 ~ 3.25 | 은 |
| 5 영웅 | 3.5 | 은 5 + 금 5 |
| 6 영웅 · 7 희귀 | 4.0 · 4.25 | 금 |
| 7 영웅 | 4.5 | 금 5 + 미스릴 5 |
| 7 전설 보스 · 8 영웅 | 5.0 | 미스릴 |
| 8 전설 보스 · 9 영웅 | 5.5 | 미스릴 5 + 오리하르콘 5 |
| 9 전설 · 10 영웅 · 10 전설 | 5.75 ~ 6.0 | 오리하르콘 |

시제품 결과: 장비 레시피 184개 모두 바뀜, 그중 53개가 두 금속 섞임. 모든 레시피를 한 번씩 만들 때 주괴: 구리 59 · 철 118 · 은 102 · 금 182 · 미스릴 151 · 오리하르콘 162.
예: 이끼등 전투망치 `+ 구리 주괴 3` · 은실 손잡이 팔시온 `녹슨 철괴 8 → 구리 주괴 1 · 철 주괴 3` · 모루 서약 넓은검 `슬래그 14·불씨 12 → 잿불 가죽 12 · 은 주괴 2 · 금 주괴 3` · 공허 팔시온 `+ 오리하르콘 주괴 6`.

### 2.8 루팅 (생성기 규칙, Q3)

- 주괴 칸 옛 재료(녹슨 철괴·슬래그 주괴·서리 결정·자수정 파편·놋쇠 톱니)의 `{item}` 항목은 지운다 (확정 항목 포함). `one_of` 안이면 목록에서 뺀다(남은 재료가 몫을 나눔).
- 몬스터 칸 옛 재료(불씨 조각·프리즘 가루·태엽 용수철) → 새 몬스터 재료로 이름만.
- **던전 광석 (R §3-10, 모든 층)**: 층마다 1회(솔로) 기대 광석이 아래 값이 되게 루팅 `guaranteed` 에 확률 항목을 더한다. 집 비율: 일반 몹 45% · 정예 5% · 보스 15% · 상자(treasure_floor_N·gimmick_floor_N) 35%. 기대값이 0.6 을 넘으면 amount 를 올린다. 허용 ±10%.

| 층 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1회 광석 | 8 | 7 | 7 | 8 | 8 | 11 | 12 | 11 | 14 | 13 |
| 금속 | 구리 81%·철 19% | 철 68%·구리 32% | 철 | 은 | 금 55%·은 45% | 금 | 금 64%·미스릴 36% | 미스릴 | 오리하르콘 74%·미스릴 26% | 오리하르콘 |

  금속 비율 = 그 단계 장비 레시피의 주괴 수요 비율 (15% 미만 뺌, 최대 2종). 목표량 = 그 단계 대표 한 벌 광석 수요 ÷ 던전 횟수 × 0.25.
- 강화석 표·정수·장비 표는 그대로.

### 2.9 강화 (gen_enhance, Q3 — T §8 + 금속만 힘으로)

- P = 그 장비의 몬스터 재료 (레시피에서 가장 많이 드는 몬스터 재료 / 드롭 장비는 HARD 표).
- S = **그 장비의 주 금속 주괴** (레시피면 가장 많이 드는 주괴, 같으면 윗 금속 / 드롭 장비는 힘 규칙의 pos 를 반올림한 금속). 개수 = 반올림(S_BASE × P 공급 배율 × 0.5), 최소 1.
- R·K 그대로 (정예 재료·정수·보스 핵).
- 겹침 피하기: 몬스터 재료가 둘인 층(1·3·4·8·10) = 다른 몬스터 재료를 P 로 / 하나인 층(2·5·6·7·9) = 주괴를 P 로 (P 주괴 × 0.5, S 는 몬스터 재료).
- HARD: 2 `spider_silk` · 5 `cinder_hide` · 6 `grave_bone` · 7 `resonant_sinew` · 9 `clock_oil`.
- 주괴 1회 공급량(환산 비교·보스 장비 검사) = 그 금속 곡괭이로 그 금속만 노릴 때 1분당 광석 × 그 층 1회 클리어 분 ÷ 2.
- 시제품: 장비 364종 모두 mid·high 에 주괴, 같은 층 똑같은 구성 0, 보스 장비가 더 싼 단계 0, 얻을 수 없는 재료 0, 주괴가 P 인 장비 75.

### 2.10 옛 재료 바꿈 (T §5 + R §2-7)

| 옛 id | 이름 | → 새 id | 이름 |
|---|---|---|---|
| rusted_iron | 녹슨 철괴 | iron_ore | 철 광석 |
| slag_ingot | 슬래그 주괴 | gold_ore | 금 광석 |
| rime_crystal | 서리 결정 | gold_ore | 금 광석 |
| amethyst_shard | 자수정 파편 | gold_ore | 금 광석 |
| brass_gear | 놋쇠 톱니 | orichalcum_ore | 오리하르콘 광석 |
| ember_shard | 불씨 조각 | cinder_hide | 잿불 가죽 |
| prism_dust | 프리즘 가루 | resonant_sinew | 공명 힘줄 |
| mainspring | 태엽 용수철 | clock_oil | 태엽 기름 |

- 1:1, 그 자리에서 id 만 (칸·개수 그대로). 주괴 칸 → 그 층 장비 레시피가 가장 많이 쓰는 금속의 광석. 몬스터 칸 → 새 몬스터 재료.
- 입구: `ItemMigration036` 은 PDC 의 원래 `item_id` 를 먼저 본다(지금 content 의 `defOf()` 로 거르지 않음). 접속 때 가방·**엔더 상자**, 보관함 열 때, 줍기·손에 들기, 셜커·꾸러미 안, 액자·갑옷 거치대·바닥 아이템은 `EntitiesLoadEvent`, 판매 바구니·대장간 창은 닫을 때.
- 결과는 `ItemService` 로 새로 만든 아이템과 `isSimilar` (겹쳐짐). 새 id 가 content 에 없으면 바꾸지 않고 시작 때 경고 1줄. 두 번 해도 같음.
- 팩은 옛 8개 id 를 새 그림으로 가리키는 별칭을 두 판(0.3.6·0.3.7) 남긴다.
- 첫 접속 안내 1번 (ext `mat036.notice`): "광산이 열렸습니다. 녹슨 철괴·슬래그 주괴 같은 광물 재료는 광석으로, 불씨 조각·프리즘 가루·태엽 용수철은 새 몬스터 재료로 바뀌었습니다. 광석은 제련소나 광산 관리소에서 주괴로 녹이세요."

### 2.11 판매 · 도감 · 툴팁 글

- config `sell.mine: {ore: 1, ingot: 3, gem: 6, rank_bonus: 0.35}`. 값 = 반올림(base × (1 + 0.35 × (등급 − 1))), 최소 1. 종류는 items.yml `mine_kind`. 도구는 못 판다 ("도구는 팔 수 없습니다.").
- 녹여 팔면 언제나 손해 (주괴 값 < 광석 2개 + 제련 골드).
- 도감 묶음 순서: 보스 · 정예 · 몬스터·상자 · 보물 상자 · 시련방 · 특별 시련 · 금고·미믹 · **광산**(#d9a066) · **제련소**(#ff9a5a) · 대장간 · 상인 · 칭호 보상 · 시작 지급 · 몬스터.
- 광산 줄: "광산 · 많이 나는 곳: <층 이름 둘>" (mine.json 무게가 가장 큰 두 곳). 제련소 줄: "제련소 구리 광석 ×2, 2G" (amount 2 이상이면 끝에 "(2개)").
- 곡괭이 툴팁: "캘 수 있는 것: <광석·보석 이름들> · 속도 ×1.4 · 광석 덤 4%". **레벨 줄 없음.**
- 광석·주괴·보석·곡괭이·광산 층의 이름·설명·도감·툴팁 글에 `Lv`·층 번호·단계·띠 글자를 쓰지 않는다. 층은 이름으로만 부른다.
  - 던전에서 나오는 광석의 도감 줄도 그렇다. 지금 `CodexMenu` 는 재료 획득처에 "(9층)"·"지하 9·10층" 을 붙인다. `mine_kind` 가 있는 아이템에는 붙이지 않고 장비처럼 종류 이름만 쓴다 ("몬스터·상자에서 조금"). `EnhanceMenu.sourceText` 는 floor 가 비어 있어 이미 층 글자가 없다.

### 2.12 몹 주제 드롭 자리 (주인 결정 7)

- `design036/drops/` 명세(따로 설계 — 지금 `drops_spec.md·json` 이 있다)를 Q3 가 같은 `generate()` 안에서 **재료 규칙 다음 단계**로 얹는다.
- 더할 수 있는 것: 몹 주제 재료 id, 상자 모양 미믹 루팅.
- 지킬 것 (바꾸려면 Q0 계약 `params.py` 부터 고친다):
  - 이 계약의 금속·보석·곡괭이 id·규칙, mine.json, ING_SHARE·던전 광석 1회량
  - 새 몬스터 재료 3개의 id·이름 (`cinder_hide` 잿불 가죽 · `resonant_sinew` 공명 힘줄 · `clock_oil` 태엽 기름 — 주인 결정 5)
  - 옛 8개 바꿈 표 (§2.10)
- 지금 드롭 명세는 옛 T(금속 5) 위에서 만들어져 이 계약과 다른 곳이 있다. 이렇게 읽는다.
  - 거기 적힌 옛 금속 광석 → 그 층 §2.8 표의 금속.
  - `cinder_hide → cinder_scale` 이름 바꿈과 `ember_shard → ember_soul` 바꿈은 주인 결정 5 와 다르다. 주인이 따로 승인할 때만, 이 계약을 먼저 고친 뒤 적용한다.

### 2.13 광산 마을 (구역)

- 자리: `east` — 마을 큰길 끝 (-104,16) 에 붙여 동쪽 (배포 월드 좌표). 막히면 `south_east` (z +42, 큰길에서 남쪽으로 길 더). 그다음은 `/labadmin village district build mine here [방향]`.
- 건물: 광산 승강장 13×24×13 `x −72..−60, z 9..21` (정면 서) · 제련소 **13×18×12** `x −88..−76, z 23..34` (정면 북) · 광부 숙소 11×12×9 `x −85..−75, z 4..12` (정면 남) · 광석 하치장(장식) 9×5×7 `x −68..−60, z 26..32` + 가로등·수레·벤치·참나무·화단·길잡이. 조각 상자 + 1칸 겹침 0, 모두 x ≥ −100 (마을이 다듬은 칸 x ≤ −101 과 떨어짐).
- 길: 큰길 (-103,16)→(-87,16) 폭 3 · 광산 마당 (-87,16)→(-73,16) 폭 7 (`mine_yard`) · 제련소 문 앞 (-82,19)→(-82,22) 폭 3 · 하치장 골목 폭 2.
- interact: `mine_lift`(승강장) · `smelter`(제련소) · `mine_info`(숙소 게시판). 마커 `mine_exit`, 연출 `dust`·`embers`·`smoke`.
- NPC: 광부 브론 `(-74, 13)` 서쪽 봄 (승강장 앞) · 제련공 이그나 `(-85, 21)` 북쪽 봄 (제련소 문 옆). ±2 칸은 Q2 가 조각 마커로 맞춘다.
- 기존 월드 적용(R §2-5 + 주인 결정 5): `labyrinth-district-mine.yml` 이 없고 `mine.district.auto_build: true` 면 시작 5초 뒤 한 번.
  1. 자리 후보 차례로 조사 (ChunkSnapshot 비동기, 마스크 = 조각·길 상자 + 4칸, 띠 + 6칸).
  2. **배포 월드 지문** 비교: 칸마다 땅 높이 · 땅속 10칸~위 30칸 블록 해시 · 원목 자리 (jar `village/districts/mine.fp`). 높이 차 > 2 · 땅속 새 공기·물 · 새 원목 · 비자연 블록 → 사람 손으로 보고 막는다. 잔디↔흙·꽃·풀·눈 층은 허용. 두 배포 월드의 지형이 다르면 build_id 마다 지문.
  3. 얼린 칸 = 높이·지형을 바꾸지 않음(깎기·메우기·나무 치우기 없음): 마을 보호 상자 · 마을 길 · 마을이 다듬은 칸(meta.terrain).
     구역 큰길은 큰길 끝 x −103..−101 에서 얼린 칸을 지난다. 그 칸은 겉 블록만 길 블록으로 깐다. 마을 길 칸과 보호 상자 안은 겉 블록도 그대로 둔다.
  4. 엔티티 검사 (갑옷 거치대·액자·그림·수레·보트·끈 매듭·이름표·길들인 동물·주민 → 막음).
  5. 통과 → **백업 먼저** → `state: building` → 짓기(틱 분할, 짓는 동안 상자 보호·사람 밀어냄) → `state: built` + NPC 2명.
  6. 모두 막히면 블록 0칸, `district-mine-blocked.txt` 남기고 관리자에게 하루 한 번 안내. **광산은 관리소로 그대로 된다.**
  - `building` 으로 꺼졌으면 다음 시작 때 백업으로 되돌린 뒤 처음부터. `/labadmin village district remove mine` = 백업으로 되돌림(우리가 놓은 블록인 칸만).
  - 마을 build_id 는 그대로. 구역 NPC 적용 열쇠는 `village-applied.yml` `districts.mine`.
- 안전지대·경계: `VillageZone` 에 구역 보호 상자(+8칸)를 더해 승강장·제련소 앞도 PvP 안 됨. **야생 경계(`WildBorder.compute`)의 보호 상자에 구역 상자를 더한다** (지은 자리가 east 든 south_east 든). 구역 중심 R+8 안 적대 몹 스폰 막음.
- 새 world.zip: `build_world.sh --base <예전 zip>` → `village district build mine east` → selftest → zip (random_tick_speed 0, 몹 스폰 끔, 마을 `mismatched=0`).

### 2.14 설정 자리 (R §3-16)

- `content/mine.yml` (자동 갱신): 층·광석·보석·블록·바이옴·초·섞임·청사진 정보. 원본 `mine.json` 의 `levels`·`ores`·`gems` 를 Q1 `tools/mine/gen_mine.py` 가 옮긴다. `ContentParser` → `Content.mine()` (`MineDef`).
- items.yml 의 `mine_level`·`mine_kind`·`tool` 은 Q3 생성기가 mine.json 에서 채우고 `ContentValidator` 가 mine.yml 과 맞대어 본다.
- `config.yml` 에는 손잡이만 (`mine.json` `config_defaults`, 키가 없으면 코드 기본값 = 이 값):

```yaml
mine:
  enabled: true
  world: labyrinth_mine
  teleport_command: auto          # auto = village.teleport_command 를 따름
  lift_seconds: 2.0
  regen_minutes: [8, 9, 9, 10, 10, 10]
  gem_node_regen_minutes: 30
  gem_chance: 0.022
  rich: {chance: 0.04, multiplier: 3}
  stamina: {enabled: true, max: 1200, regen_per_minute: 1.0, cost_per_block: 0.75, tired_yield: 0.3, bar_below: 0.25}
  fx: {pop: true}                 # 광석 날아오기
  alert_per_hour: 600
  no_hunger: true
  safe: true
  district: {auto_build: true, sites: [east, south_east], blocks_per_tick: 3000, notify_admins: true}
sell:
  mine: {ore: 1, ingot: 3, gem: 6, rank_bonus: 0.35}   # Q3
starter_kit: ... + {item: copper_pickaxe, amount: 1}    # Q3
```

---

## 3. id 와 이름

### 3.1 새 아이템 27개

| 등급 | 광석 | 주괴 | 곡괭이 | 보석 |
|---|---|---|---|---|
| 1 | `copper_ore` 구리 광석 (common) | `copper_ingot` 구리 주괴 (uncommon) | `copper_pickaxe` 구리 곡괭이 (common) | `quartz` 석영 (rare) |
| 2 | `iron_ore` 철 광석 (common) | `iron_ingot` 철 주괴 (uncommon) | `iron_pickaxe` 철 곡괭이 (uncommon) | `garnet` 석류석 (rare) |
| 3 | `silver_ore` 은 광석 (common) | `silver_ingot` 은 주괴 (uncommon) | `silver_pickaxe` 은 곡괭이 (rare) | `moonstone` 월장석 (rare) |
| 4 | `gold_ore` 금 광석 (uncommon) | `gold_ingot` 금 주괴 (rare) | `gold_pickaxe` 금 곡괭이 (rare) | `topaz` 황옥 (epic) |
| 5 | `mithril_ore` 미스릴 광석 (uncommon) | `mithril_ingot` 미스릴 주괴 (rare) | `mithril_pickaxe` 미스릴 곡괭이 (epic) | `sapphire` 청옥 (epic) |
| 6 | `orichalcum_ore` 오리하르콘 광석 (rare) | `orichalcum_ingot` 오리하르콘 주괴 (epic) | `orichalcum_pickaxe` 오리하르콘 곡괭이 (legendary) | `dragonblood_stone` 용혈석 (legendary) |

새 몬스터 재료 (uncommon): `cinder_hide` 잿불 가죽 (5층) · `resonant_sinew` 공명 힘줄 (7층) · `clock_oil` 태엽 기름 (9층).
모두 플러그인 id 다 (minecraft: 아님). 지금 items.yml 과 겹치는 것 0. 설명 글은 `materials.json` `items`.

### 3.2 광산 층 6

| 층 | id | 이름 | 깊이 | 바닥 y | 바이옴 (y 띠) | 빛 | 빈 광맥 | 광석 섞임 (%) | 광맥 블록 | 보석 노드 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | shallow_drift | 얕은 갱도 | 40m | 135 | dripstone_caves (≥128) | 등불·구리 등불 | cobblestone | 구리 62 · 철 30 · 은 8 | 56 | 석영 2 · 석류석 1 |
| 2 | dripstone_drift | 종유 갱도 | 90m | 110 | dripstone_caves (104~127) | 등불(쇠사슬) | mossy_cobblestone | 구리 34 · 철 46 · 은 15 · 금 5 | 58 | 석영 1 · 석류석 2 |
| 3 | moss_vein | 이끼빛 수맥 | 140m | 85 | lush_caves (80~103) | 영혼 등불·발광 이끼 | cobbled_deepslate | 구리 14 · 철 30 · 은 41 · 금 12 · 미스릴 3 | 60 | 석류석 1 · 월장석 2 |
| 4 | ochre_fault | 황토 단층 | 200m | 60 | badlands (52~79) | 황토빛 개구리불·등불 | cobblestone | 구리 9 · 철 14 · 은 23 · 금 39 · 미스릴 12 · 오리 3 | 60 | 월장석 1 · 황옥 2 |
| 5 | geode_hollow | 청록 정동 | 260m | 35 | warped_forest (28~51) | 진주빛 개구리불·자수정 싹·발광 이끼 | cobbled_deepslate | 구리 4 · 철 8 · 은 12 · 금 22 · 미스릴 41 · 오리 13 | 62 | 황옥 1 · 청옥 2 |
| 6 | dragon_abyss | 용의 심연 | 330m | 10 | basalt_deltas (<28) | 끝 막대·초록빛 개구리불 | blackstone | 구리 5 · 철 7 · 은 9 · 금 13 · 미스릴 23 · 오리 43 | 66 | 청옥 1 · 용혈석 2 |

층 색·재생 입자·팔레트·분위기 글은 `mine.json` `levels`, `visual.json` `levels`. 승강기 (0, 바닥+1, 0), 내리는 자리 (0.5, 바닥+1, 3.5).

### 3.3 블록 (바닐라, 12개 모두 다름)

| 광석 | 블록 | 보석 | 블록 (+ 결정 모델) |
|---|---|---|---|
| 구리 | copper_ore | 석영 | nether_quartz_ore (+ node_quartz) |
| 철 | iron_ore | 석류석 | cinnabar (+ node_garnet) |
| 은 | calcite | 월장석 | sea_lantern (+ node_moonstone) |
| 금 | gold_ore | 황옥 | glowstone (+ node_topaz) |
| 미스릴 | deepslate_diamond_ore | 청옥 | deepslate_lapis_ore (+ node_sapphire) |
| 오리하르콘 | ancient_debris | 용혈석 | magma_block (+ node_dragonblood) |

- 고른 이유는 `visual.json` `blocks.*.why`. 쓰면 안 됨: 레드스톤 광석(lit), 떨어지는 블록, 블록 엔티티, 정육면체 아님.
- 이 12개와 빈 광맥 블록은 광산 어느 층의 벽·바닥·장식·빛에도 쓰지 않는다. 구역 장식에도 쓰지 않는다(원석 블록 `raw_*_block` 은 됨).
- 팩은 블록을 하나도 바꾸지 않는다 (blockstates·models/block·textures/block 0개).

### 3.4 캐는 초 (곡괭이 × 광석)

| 곡괭이 (speed · 덤) | 구리 | 철 | 은 | 금 | 미스릴 | 오리하르콘 |
|---|---|---|---|---|---|---|
| 구리 (×1.0 · 0%) | 2.50 | − | − | − | − | − |
| 철 (×1.2 · 2%) | 2.08 | 2.42 | − | − | − | − |
| 은 (×1.4 · 4%) | 1.79 | 2.07 | 2.36 | − | − | − |
| 금 (×1.6 · 6%) | 1.56 | 1.81 | 2.06 | 2.31 | − | − |
| 미스릴 (×1.8 · 8%) | 1.39 | 1.61 | 1.83 | 2.06 | 2.28 | − |
| 오리하르콘 (×2.0 · 10%) | 1.25 | 1.45 | 1.65 | 1.85 | 2.05 | 2.25 |

광석 base_seconds (×1.0): 2.5 · 2.9 · 3.3 · 3.7 · 4.1 · 4.5. 보석 노드: 3.75 · 4.35 · 4.95 · 5.55 · 6.15 · 6.75 (÷ 곡괭이 speed).
"−" = 못 캠 (곡괭이가 약해 캘 수 없습니다). 좋은 곡괭이일수록 모든 광석에서 빠르다.

### 3.5 레시피 17개 (모두 `station: smelter`, 레벨 조건 없음)

- 제련 6 (`category: material`, amount 1): `<금속>_ingot` = `<금속>_ore` ×2 + 골드 2 · 4 · 8 · 12 · 18 · 25.
- 새기기 6 (amount 2):
  - `lesser_enhance_stone` = 석영 1 + 희미한 미궁 정수 1 + 20G · `lesser_enhance_stone_garnet` = 석류석 1 + 희미한 정수 1 + 20G
  - `greater_enhance_stone` = 월장석 1 + 미궁 정수 1 + 120G · `greater_enhance_stone_topaz` = 황옥 1 + 미궁 정수 1 + 120G
  - `supreme_enhance_stone` = 청옥 1 + 찬란한 미궁 정수 1 + 400G · `supreme_enhance_stone_dragonblood` = 용혈석 1 + 찬란한 정수 1 + 400G
- 곡괭이 5 (`category: tool`, 앞 곡괭이 사라짐):

| 곡괭이 | 재료 | 골드 |
|---|---|---|
| iron_pickaxe | copper_pickaxe 1 · copper_ingot 12 · quartz 2 · dim_essence 2 | 300 |
| silver_pickaxe | iron_pickaxe 1 · iron_ingot 16 · garnet 2 · dim_essence 4 | 1,000 |
| gold_pickaxe | silver_pickaxe 1 · silver_ingot 20 · moonstone 3 · labyrinth_essence 2 | 2,500 |
| mithril_pickaxe | gold_pickaxe 1 · gold_ingot 24 · topaz 3 · labyrinth_essence 4 | 5,000 |
| orichalcum_pickaxe | mithril_pickaxe 1 · mithril_ingot 28 · sapphire 4 · radiant_essence 3 | 10,000 |

레시피 수 187 → 204. 정수가 들어가 광산만으로 곡괭이 사다리를 오를 수 없다(레벨 조건 대신 던전 진행이 속도를 정함).

### 3.6 판매가

| 등급 | 광석 | 주괴 | 보석 | 제련 골드 |
|---|---|---|---|---|
| 1 | 1 | 3 | 6 | 2 |
| 2 | 1 | 4 | 8 | 4 |
| 3 | 2 | 5 | 10 | 8 |
| 4 | 2 | 6 | 12 | 12 |
| 5 | 2 | 7 | 14 | 18 |
| 6 | 3 | 8 | 17 | 25 |

### 3.7 이름 (Java `kr.labyrinth.mine.MineNames` — 문자열을 따로 쓰지 말 것)

| 종류 | 값 |
|---|---|
| 월드 | `labyrinth_mine` |
| interact | `mine_lift` (승강기) · `mine_office` (관리소) · `smelter` (구역 제련소) · `mine_info` (게시판) |
| NPC 역할 | `miner` → `MineApi.openOffice` · `smelter` → `CraftingService.openSmelter` |
| station · category · source | `blacksmith` · `smelter` · `tool` · sources `mine`(광산) · `smelt`(제련소) |
| 마커 · 연출 | `mine_exit` · `office` · `dust` (+ 기존 `embers`·`smoke`) |
| ext | `mine.depleted` · `mine.hash` · `mine.stamina` · `mine.stamina_at` · `mine.free_pickaxe` · `mat036.notice` (없앰: `mine.prev_mode`) |
| PDC | `labyrinth:mine_node` = "L<n>:<i>" (보석 노드 ItemDisplay) |
| 액션바 | `곡괭이가 약해 캘 수 없습니다` |
| 명령 | `/미궁 광산` (`/lab mine`) · `/labadmin mine selftest\|stats <이름>\|rebuild [층]` · `/labadmin village district info\|preview\|build\|remove mine` |
| 파일 | `<광산 월드>/labyrinth-mine.yml` · `<주 월드>/labyrinth-district-mine.yml` · `…backup.gz` · `plugins/Labyrinth/village/district-mine-blocked.txt` · jar `mine/levels/L1..L6.json` · `village/districts/mine.json` · `mine.fp` |
| NPC | 광부 브론 (`miner`, 스킨 miner) · 제련공 이그나 (`smelter`, 스킨 smelter) |
| 메뉴 배경 | `gui_smelter` · `gui_mine_lift` · `gui_mine_office` · 광부 상점 = `gui_merchant` |

자가 진단 줄:
- `[광산 자가 진단] 결과: 예외 0 · levels=6/6 · mismatched=0 · veins=N · gems=18 · reach_max≤12 · unreachable=0 · lifts=6/6 · office=1 · tool_mismatch=0 · mobs=0`
- `[광산 마을 자가 진단] 결과: 예외 0 · checked=N mismatched=0 · overlaps=0 · floating=0 · tree_remnants=0 · blocked_doors=0 · path_steps=0 · junction=ok · npcs=2/2 · interact=a/a`

### 3.8 그림 (Q4 — `visual.json`)

- 아이콘 21개 (32×32, 0.3.5 `icons.py` 방식): V 의 새 모양 17개 + Q0 가 더한 `ore_ember`(오리하르콘 광석) · `gem_drop`(용혈석). 금 광석 `ore_star`, 금 주괴 `ingot_bar`(철과 같은 모양·다른 색), 오리하르콘 주괴 `ingot_star`, 황옥 `gem_shard`.
- 곡괭이 3D 6개 (새 틀 `pickaxe`, 손 모습 `displays.voxel_weapon`): 모양 copper · steel · silver · **gold**(새) · crystal · **ember**(새, 반짝임 `ember_glow`). 요소 예산 380 · 380 · 380 · 450 · 520 · 720.
- 보석 결정 6개 (ItemDisplay, ≤ 300 요소): node_quartz · node_garnet · node_moonstone · node_topaz(새) · node_sapphire · node_dragonblood(새). 놓는 법·숨김은 `visual.json` `gem_nodes`.
- NPC 스킨: 기존 `paint_skin` + 닫힌 목록. 광부 `miner/short_beard/[helmet_lamp, tool_belt, soot_marks]` 푸른 회색 작업복 · 제련공 `apron/bun/[goggles_forehead, thick_gloves, tool_belt]` 주황·녹청 강조. 큰 눈·잔무늬 없음.

---

## 4. 섞임 · 광맥 배치 (시안)

`tools/data/036/model/layout6.py` → `model/out/L1..L6.txt`, `layout.json`. Q1 의 최종 청사진은 층마다 광석 종류별 블록 수가 `mine.json` `vein_blocks` 와 같아야 한다 (다르게 하려면 `params.py` 를 고치고 run_all).

| 층 | 모양 | 광맥 블록 (광석별) | 보석 노드 | 손 닿는 최대 (4.5 / 서버 4.75) | 한 바퀴 |
|---|---|---|---|---|---|
| 1 얕은 갱도 | 갱도 3갈래 | 구리 35 · 철 17 · 은 4 | 석영·석영·석류석 | 10 / 10 | 190칸 |
| 2 종유 갱도 | 갱도 3갈래 | 구리 20 · 철 26 · 은 9 · 금 3 | 석영·석류석·석류석 | 10 / 12 | 190칸 |
| 3 이끼빛 수맥 | 갱도 3갈래 | 구리 8 · 철 18 · 은 25 · 금 7 · 미스릴 2 | 석류석·월장석·월장석 | 10 / 11 | 190칸 |
| 4 황토 단층 | 어긋난 단층 | 구리 6 · 철 8 · 은 14 · 금 23 · 미스릴 7 · 오리 2 | 월장석·황옥·황옥 | 10 / 12 | 192칸 |
| 5 청록 정동 | 둥근 정동 | 구리 3 · 철 5 · 은 7 · 금 14 · 미스릴 25 · 오리 8 | 황옥·청옥·청옥 | 9 / 12 | 184칸 |
| 6 용의 심연 | 큰 굴 | 구리 3 · 철 5 · 은 6 · 금 9 · 미스릴 15 · 오리 28 | 청옥·용혈석·용혈석 | 10 / 12 | 184칸 |

모두 362 블록, 보석 노드 18. 무더기 하나는 광석 한 종류(3~5칸).
Q0 검사 때 따로 다시 잰 값: 보석 노드까지 세면 4.5 에서 최대 11, 서버 한도 없이 5.5 면 10·14·15·12·14·13 (그래서 §2.3 거리 한도).

---

## 5. 경제 (6층 섞인 광산 · ING_SHARE 0.20)

`tools/data/036/model/economy.py` (design036 `mine_model.py`·`mat_balance.py`·`rv_balance.py` 를 고침). 가정:
- 1회 클리어(보통·솔로) 15·16·18·20·21·23·24·26·27·30분 (T 와 같음 — 주인 서버 `records.yml` `speed.floor_N` 으로 맞추기 전). 4인 = 시간 × 0.8, 드롭 +15% (핵 제외).
- 캐기: 블록마다 조준 1초 + 무더기 사이 걷기 0.5초, 층 한 바퀴 45초 + 승강기 12초. 개인 광맥이라 4인도 1인 몫 그대로.
- 대표 한 벌 = 그 단계 대장간 일반 무기 1 (재료 합 가운데) + 4부위 세트 1벌 (가운데). 곡괭이 = 그 한 벌이 쓰는 가장 높은 금속.
- 광산 분 = (주괴 × 2 − 그 던전 횟수 동안 주운 광석) 을 가장 빨리 모으는 층 묶음 (63가지 중).

### 표 A. 곡괭이 × 층 — 한 층에 머물며 캘 수 있는 것을 다 캘 때 1분당 광석 (괄호: 많이 나오는 금속)

| 곡괭이 \ 층 | 얕은 갱도 | 종유 갱도 | 이끼빛 수맥 | 황토 단층 | 청록 정동 | 용의 심연 |
|---|---|---|---|---|---|---|
| 구리 | 4.7 (구리) | 2.4 (구리) | 1.0 (구리) | 0.7 (구리) | 0.3 (구리) | 0.3 (구리) |
| 철 | 7.2 (구리·철) | 5.6 (철·구리) | 3.2 (철·구리) | 1.5 (철·구리) | 0.9 (철·구리) | 0.9 (철·구리) |
| 은 | 7.9 (구리·철) | 6.9 (철·구리) | 6.4 (은·철) | 3.1 (은·철) | 1.7 (은·철) | 1.6 (은·철) |
| 금 | 8.0 (구리·철) | 7.4 (철·구리) | 7.4 (은·철) | 5.8 (금·은) | 3.3 (금·은) | 2.6 (금·은) |
| 미스릴 | 8.2 (구리·철) | 7.5 (철·구리) | 7.8 (은·철) | 6.8 (금·은) | 6.3 (미스릴·금) | 4.4 (미스릴·금) |
| 오리하르콘 | 8.3 (구리·철) | 7.7 (철·구리) | 7.9 (은·철) | 7.1 (금·은) | 7.4 (미스릴·금) | 7.8 (오리하르콘·미스릴) |

한 층만 돌면 재생이 상한이다 (약 6~8 블록/분). 약한 곡괭이로 깊은 층에 가도 캘 것이 적다 — 레벨 잠김 없이도 진행 순서가 생긴다.

### 표 B. 금속 하나만 노리고 여러 층을 돌 때 1분당 광석 (괄호: 도는 층)

| 곡괭이 | 구리 | 철 | 은 | 금 | 미스릴 | 오리하르콘 |
|---|---|---|---|---|---|---|
| 구리 | 8.7 (1234) | — | — | — | — | — |
| 철 | 8.9 (1234) | 8.6 (1234) | — | — | — | — |
| 은 | 9.2 (12345) | 8.8 (12345) | 7.3 (23456) | — | — | — |
| 금 | 9.6 (12346) | 9.2 (12346) | 7.4 (23456) | 6.5 (23456) | — | — |
| 미스릴 | 9.8 (12345) | 9.6 (12346) | 7.6 (123456) | 6.7 (23456) | 5.7 (3456) | — |
| 오리하르콘 | 10.0 (12345) | 9.9 (12345) | 7.8 (123456) | 6.8 (23456) | 5.8 (3456) | 4.5 (456) |

희귀할수록 덜 나온다 (구리 ~9 → 오리하르콘 4.5). 오리하르콘은 4~6층에만 있다.

### 표 C. 대표 한 벌 제작 총시간 (던전 분 + 광산 분) — 0.3.5 와 비교

| 단계 | 0.3.5 솔로 | 0.3.6 솔로 = 던전 + 광산 | 변화 | 0.3.5 4인 | 0.3.6 4인 | 변화 | 쓰는 금속 (주괴) | 곡괭이 |
|---|---|---|---|---|---|---|---|---|
| 1 | 11분 | 11 + 2 = 14분 | +19% | 8분 | 8 + 2 = 10분 | +26% | 구리 12 | 구리 |
| 2 | 15분 | 15 + 2 = 17분 | +11% | 10분 | 10 + 2 = 12분 | +16% | 구리 5 · 철 8 | 철 |
| 3 | 19분 | 19 + 3 = 22분 | +15% | 13분 | 13 + 3 = 16분 | +21% | 철 16 | 철 |
| 4 | 20분 | 20 + 3 = 23분 | +17% | 14분 | 14 + 3 = 17분 | +25% | 은 16 | 은 |
| 5 | 26분 | 26 + 4 = 30분 | +17% | 18분 | 18 + 4 = 22분 | +25% | 은 16 · 금 3 | 금 |
| 6 | 24분 | 21 + 5 = 26분 | +8% | 16분 | 15 + 5 = 19분 | +16% | 금 20 | 금 |
| 7 | 27분 | 22 + 3 = 25분 | −6% | 19분 | 15 + 3 = 18분 | −0% | 금 13 · 미스릴 9 | 미스릴 |
| 8 | 32분 | 32 + 7 = 40분 | +23% | 22분 | 22 + 7 = 30분 | +33% | 미스릴 28 | 미스릴 |
| 9 | 28분 | 27 + 9 = 36분 | +28% | 20분 | 19 + 9 = 28분 | +41% | 미스릴 3 · 오리하르콘 25 | 오리하르콘 |
| 10 | 34분 | 34 + 9 = 43분 | +27% | 23분 | 23 + 9 = 32분 | +40% | 오리하르콘 28 | 오리하르콘 |

솔로 −6 ~ +28%, 4인 0 ~ +41%. R §3-9 의 0.20 예상(솔로 +0~28%, 4인 +7~40%)과 맞는다. 6·7단계에서 던전 횟수가 주는 것은 옛 광물 칸이 빠져 미로 상자의 몬스터 재료 몫이 늘었기 때문이다(T 와 같은 이유).

+5 까지 (제작 + 강화, 솔로):

| 단계 | 0.3.5 | 0.3.6 = 던전 + 광산 | 변화 |
|---|---|---|---|
| 1 | 29분 | 26 + 4 = 30분 | +4% |
| 2 | 34분 | 29 + 10 = 38분 | +12% |
| 3 | 50분 | 47 + 6 = 53분 | +6% |
| 4 | 56분 | 56 + 5 = 61분 | +9% |
| 5 | 47분 | 39 + 11 = 50분 | +7% |
| 6 | 59분 | 44 + 16 = 60분 | +3% |
| 7 | 61분 | 46 + 16 = 63분 | +3% |
| 8 | 70분 | 67 + 13 = 80분 | +14% |
| 9 | 59분 | 52 + 25 = 76분 | +29% |
| 10 | 82분 | 82 + 15 = 97분 | +18% |

### 표 D. 곡괭이 준비 (앞 곡괭이로 앞 금속 주괴·보석을 캐는 분, 한 번)

| 곡괭이 | 재료 | 광산 분 | 골드 (제련 포함) |
|---|---|---|---|
| 철 곡괭이 | 구리 곡괭이 · 구리 주괴 12 · 석영 2 · 희미한 미궁 정수 2 | 7분 | 324G |
| 은 곡괭이 | 철 곡괭이 · 철 주괴 16 · 석류석 2 · 희미한 미궁 정수 4 | 7분 | 1,064G |
| 금 곡괭이 | 은 곡괭이 · 은 주괴 20 · 월장석 3 · 미궁 정수 2 | 12분 | 2,660G |
| 미스릴 곡괭이 | 금 곡괭이 · 금 주괴 24 · 황옥 3 · 미궁 정수 4 | 13분 | 5,288G |
| 오리하르콘 곡괭이 | 미스릴 곡괭이 · 미스릴 주괴 28 · 청옥 4 · 찬란한 미궁 정수 3 | 19분 | 10,504G |

보석이 병목이다. 주괴는 그동안 캔 광석으로 채워진다.

### 표 E. 골드 — 광산에서 캔 것을 다 팔 때 G/분 ÷ 던전 G/분

| 단계 | 던전 G/분 (드롭 골드만) | + 재료 판매 | 그 단계 곡괭이 | 광산 G/분 | 비율 (드롭만 / 판매 포함) | 가장 좋은 곡괭이를 받았을 때 | 비율 (드롭만) |
|---|---|---|---|---|---|---|---|
| 1 | 58.9 | 83.1 | 구리 | 10.4 | 18% / 12% | 39.7 | 67% |
| 2 | 68.6 | 88.4 | 철 | 15.9 | 23% / 18% | 39.7 | 58% |
| 3 | 74.2 | 101.2 | 철 | 15.9 | 22% / 16% | 39.7 | 53% |
| 4 | 148.0 | 188.9 | 은 | 22.1 | 15% / 12% | 39.7 | 27% |
| 5 | 174.1 | 223.6 | 금 | 27.9 | 16% / 12% | 39.7 | 23% |
| 6 | 195.4 | 251.8 | 금 | 27.9 | 14% / 11% | 39.7 | 20% |
| 7 | 379.0 | 453.8 | 미스릴 | 32.2 | 8% / 7% | 39.7 | 10% |
| 8 | 479.6 | 612.5 | 미스릴 | 32.2 | 7% / 5% | 39.7 | 8% |
| 9 | 553.1 | 703.4 | 오리하르콘 | 39.7 | 7% / 6% | 39.7 | 7% |
| 10 | 753.4 | 920.9 | 오리하르콘 | 39.7 | 5% / 4% | 39.7 | 5% |

- 던전이 실제로 주는 골드(드롭 골드 + 주운 재료 판매, 장비 판매는 뺌)와 견주면 모든 단계 ≤ 18%. 드롭 골드만 견주면 2·3단계가 22~23% 다 (광석 1G 가 바닥값이라 더 내릴 수 없음).
- 친구가 가장 좋은 곡괭이를 준 신입은 초반 던전 골드의 53~67% 를 광산에서 번다. 레벨 잠김을 없앤 결과이고 주인 결정 2 가 허락한 일이다. 절대값은 1분에 40G 아래다.

### 표 F. 기력 (최대 1,200 · 1분에 1 · 블록마다 0.75 · 바닥나면 수확 ×0.3)

| 캐는 속도 (블록/분) | 가득 찬 데서 바닥까지 | 하루 24시간 내내 캘 때 받는 몫 |
|---|---|---|
| 6 | 5.7시간 | 58% |
| 8 | 4.0시간 | 51% |
| 10 | 3.1시간 | 47% |
| 12 | 2.5시간 | 44% |

- 정직한 플레이: 한 벌 재료를 노려 캘 때 3.8~9.7 블록/분 → 3.2~10.8시간 동안 닿지 않는다. 가장 좋은 곡괭이로 모든 층을 쉬지 않고 돌면 13.6 블록/분 → 2.2시간, 쉬는 틈이 1/4 이면 3.0시간.
- 한 자리 매크로 (손 닿는 광맥 전부를 재생마다): 층별 9~10개 → 0.9~1.25 블록/분, 정직한 속도의 7~9%. 회복보다 느려 기력이 줄지 않지만 얻는 것이 적다.
- 모든 층을 하루 내내 도는 봇 (13.6 블록/분): 2.2시간 뒤 지침, 하루 수확은 정직한 속도의 43%.

---

## 6. 패키지 경계 · 파일 주인

Q0 가 이미 넣은 것 (뼈대, 컴파일·기존 시험 통과):
- `content/ItemType.TOOL` · `content/MineKind` · `content/ToolSpec` · `ItemDef` 의 `mineLevel()`·`mineKind()`·`tool()` (+ `isTool()`·`isMineMaterial()`)
- `content/MineDef` + `Content.mine()` · `ContentParser.parseMine` · FILES·OPTIONAL_FILES·COUPLED 에 `mine.yml`
- `mine/MineApi` (`enabled`·`isMineWorld`·`openLift`·`openOffice`·`openInfo`·`applyPickaxe`) · `mine/NoopMineApi` · `mine/MineNames` · `Services.mine()`/`setMine`
- `CraftingService.openSmelter`·`openMineShop` (기본 메서드 = 안내만)
- 연결: `NpcServiceImpl` 역할 miner·smelter, `VillageService.openMenu` 의 mine_lift·mine_office·smelter·mine_info, `ContentValidator.NPC_ROLES`(+miner·smelter)·`RECIPE_CATEGORIES`(+tool), `ItemTooltip.category` TOOL = "도구"
- 시험: `mine/MineContractTest` (계약 JSON ↔ MineDef·ToolSpec·MineNames) · `content/ToolSpecTest`
- 계약: `tools/data/036/*.json` · `check_contract.py` · `model/` · 이 문서

| 패키지 | 맡는 파일 | 하는 일 |
|---|---|---|
| **Q1 광산 엔진** | `kr/labyrinth/mine/**` (MineNames·MineApi 이름은 바꾸지 않음, 더하기만 · MineConfig·NamespacedKey 도 여기) · `content/MineDef` (더하기만, `parse` 포함) · `content/mine.yml` (`tools/mine/gen_mine.py` 생성) · `resources/mine/levels/L1–L6.json` · `tools/mine/**` · `LabyrinthPlugin` (모듈) · `dungeon/LabyrinthWorld.applyRules` (공용 정적) · `pvp/PvpModule` · `pvp/DefaultTargetFilter` · `combat/DamageService` · 상태 이상 진입점(`classes/LabyrinthStatusEffectService`) · config.yml `mine:` 절 | 월드·승강기·관리소 칸·개인 광맥·재생·다시 보내기 · tier 규칙·액션바 · 기력 · 안전(모드 규칙·피해·PvP·몹 화이트리스트·떨어짐·진주·양동이) · 곡괭이 구성요소(`applyPickaxe`)·광산 밖 막기 · `/미궁 광산`·`/labadmin mine` · `MineApi` 실제 구현 + `services.setMine` |
| **Q2 광산 마을 + 기존 월드** | `village/**` (Planner·HeightField 마스크·얼린 칸, DistrictLibrary·Builder·Meta·Backup·Fingerprint, VillageService 덧씌우기, VillageSelfTest, VillageCommands, Markers, WildService·WildBorder 에 구역 상자) · `pvp/VillageZone` · `tools/village/pieces_mine.py`·`build_all.py`·`district_fingerprint.py` · `resources/village/districts/mine.json`·`mine.fp` · `tools/build_world.sh --base` · `release.sh` | §2.13 전부. 승강장 `mine_lift` → `services.mine().openLift` (이미 연결됨) |
| **Q3 재료·생성기·바꿈·제련·상점 (+드롭)** | `tools/gen_036_materials.py` (새) · `tools/gen_035_content.py` (generate() 안 단계, SOURCE_ORDER 에 mine·smelt) · `tools/gen_enhance.py` · content `items/loot/recipes/npcs/enhance.yml` (생성물, npcs 스킨 값은 visual.json 에서) · `content/ContentParser`·`ItemDef` (Q0 뒤 더하기) · `core/ContentValidator` (mine.yml ↔ items.yml 맞대기, tool·mine_kind 검사) · `core/ContentLoader` · `core/Settings` (starter_kit 옛 기본 목록만) · `core/Keys` · `items/ItemsModule` · `items/ItemMigration036` (새) · `items/EquipmentListener` · `items/GearItemService`·`BasicItemService` (TOOL 만들기 → `MineApi.applyPickaxe`, 한 칸 1개) · `items/crafting/*` (station 거르기, SmelterMenu 탭 제련·새기기·곡괭이, ×1·×8·전부, 앞 곡괭이를 재료로, `LabCraftingService.openSmelter`·`openMineShop`) · `mobs/npc/NpcServiceImpl` · `items/sell/SellPrices` (sell.mine, 도구 못 팜) · config.yml `sell.mine`·`starter_kit` · 다음 단계로 `design036/drops/` | §2.7~2.12 · 관리소 메뉴의 곡괭이·제련·새기기·팔기 탭 내용(Q1 의 관리소가 이 메뉴들을 연다) |
| **Q4 리소스팩** | `resourcepack/src/icons.py` (모양 19: V 17 + ore_ember·gem_drop) · `src/voxel/weapons.py` (`pickaxe` 틀, 모양 6) · `generate.py` (`build_mine_nodes` 6, 옛 8 id 별칭) · `src/ui.py` + `content/glyphs.yml` (gui_smelter·gui_mine_lift·gui_mine_office) · `src/validate.py` (곡괭이 예산, 결정 ≤300, 블록 덮어쓰기 0) · `tools/check_assets.py` · NPC 스킨 2 (기존 painter) | §3.8. 기댈 것은 visual.json·materials.json 의 id·style 뿐 |
| **Q5 툴팁·도감·문서** | `items/ItemTooltip` (도구 줄·광산 재료 줄) · `ui/menus/CodexMenu` (광산·제련소 묶음, 도구 탭) · `ui/menus/MainMenu` (메인 메뉴 광산 버튼) · `items/enhance/EnhanceMenu.sourceText` · `GDD.md`·`ARCHITECTURE.md`·`VILLAGE.md`(§0 정책·§7 광산 마을)·`release/README.txt` · 판 번호 0.3.6 (`build.gradle.kts`) | §2.11 글 규칙. Q1~Q3 를 합친 뒤 |

여럿이 만지는 파일:

| 파일 | 누가 |
|---|---|
| config.yml | Q1 `mine:` · Q3 `sell.mine`·`starter_kit` (서로 다른 절) |
| items/npcs/recipes/loot/enhance.yml | Q3 만 (Q4 는 읽기만) |
| content/glyphs.yml | Q4 만 |
| GearItemService | Q3 만 (Q1 의 `applyPickaxe` 를 부름) |
| LabyrinthPlugin · PvpModule · DamageService · DefaultTargetFilter | Q1 만 |
| VillageService · VillageZone · WildService · WildBorder | Q2 만 |
| EquipmentListener · NpcServiceImpl · ContentValidator · ContentParser | Q3 만 |
| MineNames · MineApi · Services | Q0 가 만듦 — 이름·메서드를 바꾸려면 Q0 계약부터 (더하기는 Q1) |
| content/ToolSpec · content/MineKind | Q0 가 만듦 — 모양을 바꾸려면 Q0 계약부터 (Q1·Q3 은 읽기만) |
| content/MineDef (+ `MineDef.parse`) | Q1 만 (더하기만). mine.yml 읽기는 `MineDef.parse` 안에서 — ContentParser 는 부르기만 하므로 Q1 이 ContentParser 를 고치지 않는다 |
| core/Settings | Q3 만 — starter_kit: 0.3.5.1 기본 목록(지금 `DEFAULT_STARTER_KIT` 7줄)을 `LEGACY_STARTER_KIT_0351` 로 더해 새 기본값(+ copper_pickaxe)으로 읽음. 안 하면 기존 서버의 새 플레이어 꾸러미에 곡괭이가 빠진다 |
| config `mine:` 읽기 | Q1 만, `mine/MineConfig` 에서 (core/Settings 를 건드리지 않음) |
| core/Keys | Q3 만 (바꿈 깃발 등). Q1 의 `labyrinth:mine_node` 키는 mine 패키지 안에서 만든다 |
| items/ItemsModule | Q3 만 (ItemMigration036·제련소 리스너·명령 등록). Q1 은 자기 MineModule 에서 등록 (`services.commands()`) |
| ItemTooltip · CodexMenu · ui/menus/MainMenu | Q5 만 (Q0 는 TOOL 줄 하나만 넣음. 메인 메뉴 "광산" 버튼 = MainMenu → `services.mine().openLift`) |

## 7. 순서

```
Q0 (이 커밋) ──┬─ Q1 광산 엔진 ─────────────────┐
               ├─ Q3 재료·생성기·제련·상점 ─────┤
               ├─ Q4 리소스팩 ──────────────────┼─ Q5 툴팁·도감·문서 ─ 통합 검증
               └─ Q2 계획기·지문·백업 → 연결 ───┘
                    (승강장 → MineApi 는 이미 있음, 실제 승강기는 Q1 뒤)
Q3 의 다음 단계: design036/drops/ 명세가 오면 재료 규칙 뒤에 얹는다.
```

- Q1·Q3 은 첫날부터 따로 간다. Q3 의 TOOL 만들기는 `MineApi.applyPickaxe` (Noop 이면 그대로)를 부르면 된다.
- Q2 의 계획기·지문·백업은 첫날부터. 승강장 연결은 이미 `services.mine().openLift` 로 걸려 있다.
- Q5 는 Q1~Q3 을 합친 뒤.

## 8. 합격 기준

모든 패키지 공통: `./gradlew build -q` 통과 (지금 시험 656개 + 새 시험) · `python3 -B tools/data/036/check_contract.py` 오류 0 · 계약 id·이름을 바꾸지 않음.

**Q1**
- 단위 시험: MineMath (speed↔틱 왕복, 초 표 = mine.json `pickaxes.*.seconds` ±0.01, 좋은 곡괭이일수록 빠름) · TierRule (tier ≤ 곡괭이만, 못 캐면 액션바 문구) · VeinState (만료·직렬화·해시 지움) · Stamina (1,200 · +1/분 · 0.75 · ×0.3 · 보스바 25%) · MineBlueprint (6층, 광석별 블록 수 = `vein_blocks`, 보석 노드 = `gem_nodes`, 손 닿는 최대 ≤ 12 (R §2-8 방식 4.5 와 서버 한도 4.75 둘 다, 밟을 수 있는 장식 위 포함), 모두 이어짐, 장식에 광석·보석·빈 광맥 블록 없음, id 순서) · ServerRecheck (4.75 넘는 거리·고갈 칸·약한 곡괭이·가방 가득 = 수확 0) · PickaxeComponent (Tool 규칙·CAN_BREAK·UNBREAKABLE·바탕 PAPER) · MineConfigDefaults (= mine.json `config_defaults`) · MineGameModeRule (기억 없음) · MineSafety (광산 월드 피해 0 — DamageService 경로).
- 서버: `[광산 자가 진단] … levels=6/6 … gems=18 … reach_max≤12 … lifts=6/6 · office=1 · tool_mismatch=0 · mobs=0`.
- 손으로: 구리 곡괭이로 구리 2.5초, 철 광석은 금도 안 가고 액션바 · 승강기 6층 모두 열림 · 캔 블록이 나에게만 빈 광맥 · 재생 · 가방 가득 · `require_near_entrance: false` 에서 광산 → 미궁 → 돌아와 마을로 나가면 서바이벌 · PvP 켬 서버에서 광산 안 피해 0.

**Q2**
- 단위 시험: DistrictLayout (평지 계획·겹침 0·큰길에 붙음·얼린 칸 그대로) · DistrictCheck (지문·비자연·엔티티) · DistrictBackup · FrozenCells (meta.terrain 포함) · WildBorderDistrict (구역 상자가 경계 안) · VillageZoneDistrict (구역 상자 안전지대).
- 서버: 0.3.5 → 0.3.6 jar 교체로 두 배포 월드 모두 east 에 지음 · 판자·흙집·판 구덩이가 있으면 블록 변화 0 + blocked.txt, south_east 로 넘어감 · remove → build 같은 결과 · 자가 진단 두 줄 깨끗 · 마을 없는 월드에서 관리소로 광산 전 과정.

**Q3**
- `python3 tools/gen_035_content.py --check && python3 tools/gen_enhance.py --check`.
- 시험: NoRetiredIds · GearRecipeIngot (금속 = §2.7 힘 규칙, 이웃 두 금속까지, 개수 = 0.20 규칙) · MineLadder (제련 6 · 새기기 6 · 곡괭이 5 사다리 · 레벨 조건 0) · SellMine (표 값·녹여 팔면 손해·도구 못 팜) · EnhanceIngot (mid·high 에 주 금속 주괴, R·K 그대로) · DungeonOrePerRun (층마다 §2.8 표 ±10%) · ItemMigration036 (isSimilar·셜커·꾸러미·엔더 상자·모르는 id·새 id 없음·두 번) · ContentMineContract (items.yml mine_level·mine_kind·tool = mine.json) · NoLevelLabels · StarterKit0351 (0.3.5.1 기본 목록 → 새 기본값 + 구리 곡괭이) · 기존 데이터 시험 (DropRateWindow·LootHomes·BandDiversity·EnhanceMaterialsTest 등).
- 레시피 187 → 204, 새 아이템 27, 옛 8개 id 가 content 어디에도 없음.

**Q4**
- `generate.py` · `validate.py` 오류 0, `check_assets.py` 깨끗 · 아이콘 21 + 곡괭이 6 + 결정 6 · 블록 덮어쓰기 0 · 곡괭이 요소 예산 · 옛 8개 별칭 · 메뉴 배경 3 · NPC 스킨 2 (기존 그림 수준).

**Q5**
- 시험: CodexMineSource ("광산 · 많이 나는 곳: …", "제련소 구리 광석 ×2, 2G", 곡괭이 줄) · TooltipFit (도구 줄 폭) · NoLevelLabels (툴팁·도감 글에 Lv·층 번호·단계 없음).
- 문서: GDD 광산 장·§11.11 표·§11.13 강화 규칙 · ARCHITECTURE §6 (mine.yml·tool·station smelter·MineApi) · VILLAGE.md §0·§7 · README ("jar 만 바꾸면 광산 마을이 지어집니다").

**통합 (lead)**: 생성기 `--check` 전부 · 팩 validate·check_assets · 서버 (a) 두 배포 월드 사본에 옛 8 id 를 가방·엔더 상자·셜커·꾸러미·상자·액자에 넣고 0.3.5 → 0.3.6 (b) 더러운 자리 (c) 마을 없는 월드 (d) 새 배포 zip (e) npcs.yml 을 고친 서버.

## 9. 아직 열린 것

1. **1회 클리어 시간 가정** (15~30분, T 와 같음). 주인 서버 `records.yml` `speed.floor_N` 이나 실제 시간으로 맞춘 뒤 §5 를 다시 잰다 (`params.RUN_MINUTES` → run_all).
2. **2·3단계 광산 골드** — 드롭 골드만 견주면 22~23% (재료 판매 포함 16~18%). 엄격히 20% 를 원하면 1·2등급 광석을 팔 수 없게 하거나 보석 값을 더 내린다.
3. **곡괭이를 받은 신입**의 광산 골드 (초반 던전의 53~67%) — 주인 결정 2 로 허락. 문제가 되면 판매가만 손본다 (레벨 조건은 넣지 않음).
4. **기력 블록당 0.75** — 최대·회복은 주인 값, 소모는 "정직하게 약 3시간"을 맞추려고 Q0 가 정했다. 시험 플레이 뒤 0.6~1.0 사이로 손본다 (config 손잡이).
5. **청사진은 시안이다.** Q1 이 최종 청사진에서 광석별 블록 수를 바꾸려면 `params.py` 의 무게·광맥 수를 고치고 run_all → §4·§5 갱신.
6. **두 배포 월드 지형이 마스크에서 같은지** (R §2-5) — Q2 가 먼저 확인.
7. **황토 단층 바이옴 `badlands`** 의 음악·안개가 땅속에서 어울리는지 — 어색하면 `dripstone_caves`·`lush_caves` 로 (mine.yml 값만 바뀜, 띠 경계는 그대로).
8. **빛 나는 보석 블록**(바다 랜턴·발광석·마그마)을 캔 뒤 그 자리에 빛이 남을 수 있다 (V 의 알려진 흠, 보기만 다름).
9. **몹 주제 드롭·상자 미믹** (`design036/drops/`) — 명세가 이제 있다. Q3 가 재료 규칙 뒤에 얹는다. 다만 `cinder_scale`·`ember_soul` 이름 바꿈은 주인 결정 5 와 달라 주인 확인이 필요하다 (§2.12). 던전 광석 1회량·ING_SHARE 를 건드리면 이 계약을 고친다.
10. NPC 자리는 ±2칸 (Q2 조각 마커로 확정).
11. **미궁 층이 광산 블록을 쓴다** (2층 벽 구리·철 광석, 6·7층 방해석, 4·6·7층 바다 랜턴, 5층 마그마). 곡괭이를 든 채 미궁 벽을 치면 금이 가다가 되돌아가고 "광산 밖" 안내가 뜬다. Q0 는 미궁 모양을 바꾸지 않았다(주인 결정 밖). 헷갈린다는 말이 나오면 floors.yml 2층 벽의 광석 두 개만 바꾸면 된다.
