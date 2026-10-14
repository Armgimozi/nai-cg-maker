# 등불 어귀 마을 — 설계 계약 (VILLAGE.md)

미궁 입구 마을을 **미리 지어 둔 오버월드(world 폴더)** 째로 서버팩에 넣는다 (사용자 결정: "증강 스카이블럭 방식",
"미리 지은 월드만"). 서버를 처음 켜면 이미 마을이 있고, 스폰이 마을 광장이다.

- 우리가 시드를 골라 만든 월드라서 마을 자리 지형은 **설계해서 다듬는다**(계단식 단·옹벽·완만한 경사). 단, 사용자 규칙
  "기존 지형 무시하고 막 만들지 마셈" 정신대로 **자연스럽게**: 넓은 평판 + 절벽 같은 티 나는 평탄화 금지, 마을 바깥으로 갈수록
  원래 지형에 부드럽게 이어지게, 나무는 반쯤 잘린 채 남기지 않는다.
- 월드는 개발 환경(테스트 서버)에서 플러그인 관리자 명령으로 지은 뒤 world 폴더를 압축해 배포 zip 에 넣는다 (증강 스카이블럭의
  `augadmin buildmap` 과 같은 방식). 다른 시드·이미 쓰던 월드에 자동으로 짓는 기능은 **만들지 않는다**.

이 문서는 Java(플러그인)와 Python(설계 도구)이 함께 따르는 계약이다. 숫자·이름은 여기 적힌 대로 쓴다.

---

## 1. 파일 배치

| 경로 | 내용 | 담당 |
|---|---|---|
| `tools/village/vlib.py` | 조각 그리기 라이브러리 (캔버스, 모양 도우미, 블록 상태 도우미, 연결 상태 계산, JSON 내보내기) | 설계 도구 |
| `tools/village/render.py` | 등각(isometric) PNG 렌더러 — 조각 JSON / 마을 전체 / 서버 덤프 | 설계 도구 |
| `tools/village/pieces_*.py` | 조각 설계 코드 (실행하면 JSON 생성) | 설계 |
| `tools/village/build_all.py` | 모든 조각 + layout 생성 → `plugin/src/main/resources/village/` 에 씀, 검증 | 설계 도구 |
| `plugin/src/main/resources/village/pieces/<id>.json` | 조각 청사진 (생성물, 커밋함) | 생성물 |
| `plugin/src/main/resources/village/layout.json` | 마을 배치 (생성물, 커밋함) | 생성물 |
| `plugin/src/main/java/kr/labyrinth/village/*` | VillageModule · 청사진 파서 · VillageBuilder(지형 다듬기+짓기, 관리자 명령) · VillageService(실행 중: 보호·NPC·입구·텔레포트) | Java |
| `tools/build_world.sh` | 테스트 서버 복사본에서 시드로 월드 생성 → 마을 짓기 → 주변 청크 미리 생성 → 정지 → `dist/world.zip` | 조립 |

Python 은 표준 라이브러리 + Pillow 만 쓴다 (`/opt/packvenv/bin/python` 에 Pillow 있음).

---

## 2. 조각(piece) 청사진 JSON

```json
{
  "format": 1,
  "id": "forge",
  "name": "두르간의 대장간",
  "size": [W, H, D],
  "floor_y": 1,
  "foundation": "minecraft:cobblestone",
  "foundation_mix": [["minecraft:cobblestone", 3], ["minecraft:mossy_cobblestone", 1], ["minecraft:andesite", 1]],
  "anchor": [ax, az],
  "max_cut": 3,
  "max_fill": 4,
  "palette": { "#": "minecraft:stone_bricks", "s": "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]" },
  "layers": [ ["row z=0 (W글자)", "row z=1", "..."], ["y=1 ..."] ],
  "markers": [ { "type": "npc", "id": "blacksmith", "pos": [x, y, z], "face": "front" } ]
}
```

### 2.1 좌표 (정방향 = canonical)
- `x` 0..W-1, `y` 0..H-1, `z` 0..D-1. `layers[y][z]` 는 길이 W 문자열, 글자 하나 = x 한 칸.
- **정방향에서 조각의 앞(정면, 문 쪽)은 z=0 줄이고, 북쪽(−Z)을 바라본다.** 축은 월드 좌표 그대로: x 증가 = 동쪽(+X), z 증가 = 남쪽(+Z).
  (정면 앞에 서서 남쪽으로 건물을 바라보면 x=0 이 오른쪽(서쪽)이다.)
- 팔레트의 블록 상태는 정방향 기준으로 쓴다 (예: 정면 벽의 문 = `oak_door[facing=north,...]` 는 북쪽을 향해 열림).
- 배치 회전은 `org.bukkit.block.structure.StructureRotation` 으로 한다: 앞이 북쪽→`NONE`, 동쪽→`CLOCKWISE_90`,
  남쪽→`CLOCKWISE_180`, 서쪽→`COUNTERCLOCKWISE_90`. 블록 상태는 `BlockData#rotate(rotation)` (방향·축·연결·회전값을 바꿔 줌).
- 좌표 회전 (W×D 정방향 → 회전 후 발자국):
  - `NONE`: (x, z) → (x, z), 발자국 W×D
  - `CLOCKWISE_90`: (x, z) → (D−1−z, x), 발자국 D×W
  - `CLOCKWISE_180`: (x, z) → (W−1−x, D−1−z), 발자국 W×D
  - `COUNTERCLOCKWISE_90`: (x, z) → (z, W−1−x), 발자국 D×W
  - 검산: 정방향 앞줄(z=0) 가운데 문이 북쪽을 보면, CLOCKWISE_90 뒤 그 문은 x=D−1(동쪽 끝)에 있고 동쪽을 본다.

### 2.2 글자 규칙
- `' '` (공백) = **건드리지 않음**. 그 칸은 원래 지형 그대로 둔다(기록도 안 함). 건물 윤곽 밖은 공백.
- `'.'` = **공기여야 함**. 원래 블록이 공기면 그대로, 풀·꽃·눈 한 겹 같은 대체 가능 블록이나 자연 블록(흙·돌·잎 등)이면 지운다(기록).
  건물 안쪽 빈 공간·문 통로는 반드시 `.` 로 채운다 (공백으로 두면 언덕 흙이 실내에 남을 수 있음).
- 그 밖의 글자 = `palette[글자]` 블록. 팔레트 값은 `Bukkit.createBlockData()` 가 읽는 문자열(`minecraft:id[prop=val,...]`).
  - 연결되는 블록(울타리·판유리·철창·담장·계단 모양)은 **연결 상태를 명시**한다 (Java 는 물리 업데이트 없이 놓는다 → 상태를 다시 계산하지 않음).
    vlib 가 이웃을 보고 자동 계산해 준다.
  - 잎은 반드시 `persistent=true` (안 그러면 사라짐). 문·침대·큰 꽃은 두 칸 모두 명시.
  - 불이 꺼지는 블록 금지: `lit=true` 화로/용광로/훈연기(블록 엔티티가 즉시 끔), 신호 없는 레드스톤 램프. 대신 등불·영혼 등불·
    촛불(`lit=true` 유지됨)·모닥불·용암 가마솥(`lava_cauldron`)·발광석·바다 랜턴·버섯불·엔드 막대.
  - 금지 블록: 물·용암 **흐르는 것**(분수 물은 사방이 막힌 웅덩이 안의 source 만), 엔드 관문/포털, TNT, 스포너, 셜커 상자,
    호퍼/디스펜서/드로퍼/크래프터/관찰자 같은 레드스톤 장치, 명령 블록, 엔티티(갑옷 거치대·액자)는 청사진에 넣지 않는다.
- 팔레트 글자는 한 조각 안에서 유일하면 아무 글자나 된다 (`' '`, `'.'` 제외). 글자가 모자라면 유니코드 아무 글자.

### 2.3 높이 규칙
- `floor_y`: 걸어 다니는 바닥 층의 layer 번호. 바닥 블록이 이 층에 있고, 사람은 `floor_y + 1` 높이에 선다.
- 짓는 쪽(VillageBuilder)이 조각마다 **단 높이 P** 를 정하고 그 단까지 지형을 다듬은 뒤, layer y 를 월드 Y = `P + (y − floor_y)` 에 놓는다
  (바닥 층이 단의 맨 윗블록 자리). `floor_y` 아래 layer(기초·주춧돌)는 땅속으로 들어간다 — 경사진 단 가장자리에서 보이는 기초를
  1~2층 넣으면 보기 좋다.
- `anchor` = 정방향 기준 (x, z) 한 칸 (보통 정문 바로 안쪽 바닥). 단 높이를 정할 때 그 칸 주변 원래 땅높이를 가장 무겁게 본다.
- `foundation`/`foundation_mix`: 단 가장자리 옹벽·기초에 쓰는 블록. `max_cut`/`max_fill` 은 쓰지 않는다(있어도 무시).

### 2.4 마커
| type | 필드 | 뜻 |
|---|---|---|
| `npc` | `id`(npcs.yml id), `pos`, `face` (`front`/`back`/`left`/`right`, 정방향 기준; front=북) | NPC 를 그 칸 가운데, 바닥 위에 세움. 회전 적용 |
| `entrance` | `pos`, `face` | 미궁 입구 위치(config entrance). 파티 모이는 곳. 게이트 조각에 하나 |
| `interact` | `action` (`entrance`/`blacksmith`/`class`/`titles`/`merchant`/`main`), `pos` 들 (`"pos": [[x,y,z], ...]`) | 그 블록 우클릭 → 메뉴 열기 |
| `spawn` | `pos`, `face` | 마을 스폰(월드 스폰·/미궁 마을 텔레포트). 광장 조각에 하나 |
| `sign` | `pos`, `lines` (최대 4줄, MiniMessage), `glow` (bool), `back`(선택) | 놓은 뒤 표지판 글 쓰기. 그 자리 블록은 팔레트에서 표지판이어야 함 |
| `banner` | `pos`, `patterns` `[["pattern_key", "color"], ...]` | 놓은 뒤 깃발 무늬 (자리 블록은 팔레트의 `*_banner`/`*_wall_banner`) |
| `ambient` | `pos`, `fx` (`portal`/`embers`/`fountain`/`magic`/`smoke`) | Java 가 주기적으로 파티클 (게이트 소용돌이, 대장간 불씨 등) |
| `light` | `pos` | 정보용 (조명 위치, 렌더러가 표시) |

pattern_key 는 마인크래프트 배너 무늬 id (`border`, `stripe_center`, `rhombus`, `flower`, `globe`, `mojang` 금지 아님 등 — 26.x 레지스트리 키).

---

## 3. layout.json

```json
{
  "format": 1,
  "name": "등불 어귀 마을",
  "radius": 32,
  "pieces": [
    { "piece": "plaza", "at": [0, 0], "front": "north" },
    { "piece": "labyrinth_gate", "at": [0, -22], "front": "south" }
  ],
  "paths": [
    { "points": [[0, -9], [0, -15]], "width": 3, "style": "main" }
  ],
  "path_styles": {
    "main": [["minecraft:stone_bricks", 4], ["minecraft:cracked_stone_bricks", 1], ["minecraft:polished_andesite", 2], ["minecraft:mossy_stone_bricks", 1]],
    "lane": [["minecraft:dirt_path", 6], ["minecraft:coarse_dirt", 1], ["minecraft:gravel", 1]]
  }
}
```

- 마을 좌표: 마을 중심 = (0, 0). 마을 정방향에서 **게이트(마을의 "앞")는 북쪽(−Z)**. `at` = 조각의 (회전 후) 발자국 가운데 칸의 마을 좌표.
  `front` = 조각 정면이 바라볼 방향(마을 정방향 기준).
- 마을 전체도 회전할 수 있다 (`StructureRotation` 하나): 조각 `at` 을 회전하고 각 조각 front 에 같은 회전을 더한다.
- `paths`: 꺾은선 점들(마을 좌표) 사이를 `width` 폭으로 칠한다. 다듬은 지형(§4.1) 맨 윗블록을 스타일 블록으로 바꾸고 그 위 한 칸
  식물은 지운다. 조각 발자국 안 칸은 건너뜀. 길 높이는 양 끝 단 사이를 완만하게 잇는다(§4.1 목표 높이장).
- 선택: `"terraces"` — 추가 단 `{ "at": [x, z], "size": [w, d], "dy": 2 }` (광장 높이 H0 기준 상대 높이, 예: 게이트를 광장보다 2칸 높은
  단에 올려 계단으로 오르게). 조각 단 높이를 직접 고정하려면 조각 항목에 `"dy": n` (H0 기준).
- 조각 발자국끼리 겹치면 안 된다 (build_all.py 가 검사). 장식 조각(가로등·벤치·나무·화단)도 조각으로 배치한다.

---

## 4. Java 동작

### 4.1 지형 다듬기 + 짓기 (VillageBuilder — 개발용 관리자 명령)
`/labadmin village build [here | <x> <z>] [north|east|south|west]` (콘솔 가능, 기본 = 월드 스폰, 정방향 north).
틱 분할(틱당 `village.blocks_per_tick` 기본 4000)로 아래 순서를 실행하고 진행률을 알린다. 서버가 멈추지 않게.
1. **조사**: 마을 반경 R(layout radius) + 혼합 띠 B(16칸) 안의 원래 땅높이(나무·풀·눈·잎 제외한 맨 위 자연 고체 블록) 수집.
2. **나무 치우기**: R+B 안에 걸친 원목/잎(persistent=false)은 이어진 덩어리째 flood fill 로 지운다(나무 밖으로 뻗은 부분 포함, 상한 있음).
   R 안의 풀·꽃·덤불·눈 한 겹도 지운다.
3. **목표 높이장**: 광장 높이 H0 = 중심 반경 6 의 원래 높이 중앙값. 각 조각 발자국(+1칸 여유) = 그 조각 단 높이 P
   (anchor 주변 원래 높이 중앙값을 H0±4 로 자름 → 자연스러운 계단식 단). 길 칸 = 길 양 끝 단 사이 선형 보간.
   그 밖의 R 안 칸 = 가까운 단·길 높이들의 거리 가중 평균과 원래 높이를 섞음, R~R+B 띠에서는 원래 높이 쪽으로 점점(smoothstep) 돌아감.
   이웃 칸 높이 차는 최대 1 이 되게 몇 번 부드럽게(조각 단은 고정). 단과 그 주변 차가 2 이상이면 그 단 가장자리를 옹벽(foundation_mix +
   이끼 섞기)으로.
4. **지형 적용**: 칸마다 목표보다 높은 땅은 공기로, 낮으면 흙으로 채우고 맨 윗블록은 잔디(원래 맨 윗블록이 모래·눈 같은 바이옴 표면이면
   그것). 물·용암이 R+B 안에 있으면 그 칸은 손대지 않는다(시드 고를 때 피함 — §4.5 survey).
5. **조각 짓기**: 회전(§2.1) 적용, P 기준(§2.3)으로 `setBlockData(data, false)`. `'.'` 는 공기, `' '` 는 다듬은 지형 그대로.
6. **길**: 다듬은 지형 맨 윗블록을 스타일 블록으로(위 한 칸 식물 제거). 높이가 1 바뀌는 곳은 그 스타일의 반블록/계단을 써도 좋다.
7. **후처리**: 표지판 글(MiniMessage → 컴포넌트), 깃발 무늬(26.x 레지스트리 키로 PatternType 조회).
8. **메타데이터 저장**: `<월드 폴더>/labyrinth-village.yml` (§4.2). 월드 스폰 = spawn 마커, 스폰 반경 게임룰 0(API 있으면), NPC 배치·입구 설정(§4.3).
같은 월드에서 다시 build 하면 거절(이미 있음) — `build force` 만 덮어씀(개발용).

### 4.2 labyrinth-village.yml (월드 폴더 안 — 월드와 함께 배포됨)
```yaml
format: 1
name: 등불 어귀 마을
center: [x, y, z]
rotation: NONE
radius: 32
spawn: [x, y, z, yaw]
entrance: [x, y, z, yaw]
npcs: { guide: [x, y, z, yaw], blacksmith: [...], class_master: [...], title_keeper: [...], merchant: [...] }
interact: { "x,y,z": entrance, "x,y,z": blacksmith, ... }   # 우클릭 → 메뉴
ambient: [ [x, y, z, portal], [x, y, z, embers], ... ]
protect: [ [x0, y0, z0, x1, y1, z1], ... ]                  # 조각 상자들(+1칸) + 광장 + 길 칸 상자
```

### 4.3 VillageService (실행 중)
- 시작할 때 주 월드(`Bukkit.getWorlds().get(0)`) 폴더의 labyrinth-village.yml 을 읽는다. 없으면 마을 기능은 조용히 꺼짐(로그 1줄).
- **월드 적용**: `plugins/Labyrinth/village-applied.yml` 에 적용한 월드 UID 를 적는다. 현재 월드 UID 가 다르면(배포 월드를 처음 켰거나
  기존 서버가 world 폴더를 새 것으로 바꿈) →
  - 마을 NPC 들을 메타데이터 자리로 `services.npcs().place(id, loc)` (예전 월드 좌표에 있던 배치를 덮어씀).
  - config `entrance.*` = 메타데이터 entrance (mode `village`). 예전 석문 기록(entrance.yml)은 **복원하지 않고** 버린다
    (예전 월드 좌표라 새 월드를 망가뜨림) — dungeon 쪽에 `forgetSaved()` 같은 공개 메서드 최소 추가, entrance.yml → entrance.yml.old.
  - 이후 접속하는 플레이어 중 이 월드 UID 를 처음 보는 사람(PlayerData ext `village.world`)은 미궁 안이 아니면 마을 스폰으로 텔레포트
    (예전 월드 좌표에 서 있다가 땅속에 끼는 것 방지). 새 플레이어는 원래 스폰이 광장이라 그대로.
- **보호** (protect 상자 안): 관리자가 아니면 부수기·놓기 취소("마을은 부수거나 바꿀 수 없습니다"), 관리자는 크리에이티브일 때만 허용.
  폭발 목록에서 제외, 불 번짐/타기 취소, 피스톤 밀기/당기기 취소, 엔더맨 등 엔티티 블록 변경 취소, 물 흐름이 상자 밖으로 나가는 것 취소,
  나무 성장(StructureGrowEvent) 이 상자 안 블록을 바꾸면 취소.
- **적대 몹 자연 스폰 취소**: center 반경 radius+8 안 `CreatureSpawnEvent` NATURAL/`Enemy` (`village.block_mob_spawns`).
- **상호작용**: interact 칸 우클릭 → 메뉴 (`entrance`→openEntrance, `blacksmith`→openBlacksmith, `class`→openClass, `titles`→openTitles,
  `merchant`→ 상인 NPC 와 같은 상점, `main`→openMain). protect 안의 문·다락문·울타리 문·종·작업대·침대는 허용, 그 밖의 컨테이너·모루·숫돌·
  독서대·양조대 등은 장식이라 취소.
- **연출**: ambient 자리 파티클(포털 소용돌이·불씨·분수 물보라·마법 반짝임·연기), 청크가 로드돼 있고 근처에 사람 있을 때만.
- **`/미궁 마을`** (`/lab village`, `/lab 마을`): 광장 스폰으로 텔레포트 (미궁 안이면 거절: "먼저 /미궁 귀환"), `village.teleport_command`.
  메인 메뉴 51번 칸 "마을" 버튼도 같은 동작. 마을 메타데이터가 없으면 "이 월드에는 마을이 없습니다 (서버팩의 world 폴더를 쓰세요)".
- 초기 설정 메뉴(SetupMenu)의 입구 방식 선택은 마을이 있으면 숨기고 "입구: 마을의 미궁의 아가리" 정보만 보여 준다.

### 4.4 그 밖의 관리자 명령
- `village info` — 메타데이터 요약, 적용 UID, NPC 상태.
- `village dump` — 마을 상자 + 16칸 여유 모든 비공기 블록 → `plugins/Labyrinth/village/dump.txt` (`x y z|blockdata`) → render.py --dump.
- `village survey [반경]` — 시드 고르기용: 스폰 주변 후보 중심들(8칸 간격, 기본 반경 160)에서 R+B 안 물/용암 칸 수, 원래 높이 표준편차·최대-최소,
  원목 수, 바이옴을 계산해 점수 좋은 5곳을 출력 (ChunkSnapshot 으로 비동기 계산, 메인 스레드 막지 않기).
- `village pregen <반경>` — 중심 주변 청크를 비동기로 미리 생성(동시 요청 수 제한, 진행률), 배포 월드 첫 접속 렉 줄이기.
- `village selftest` — 메타데이터를 다시 읽어 모든 조각 칸이 청사진대로인지 검사(mismatched 수), NPC 5명이 자리에 있는지, interact·spawn·entrance
  유효성 → 결과 한 줄 `[마을 자가 진단] 결과: 예외 0 · checked=… mismatched=0 · npcs=5/5 · …`.

### 4.5 config.yml
```yaml
village:
  teleport_command: true     # /미궁 마을 로 광장 텔레포트
  block_mob_spawns: true     # 마을 안 적대 몹 자연 스폰 막기
  blocks_per_tick: 4000      # village build 속도 (개발용)
```

### 4.6 배포 (조립 담당)
- `tools/build_world.sh`: /opt/testserver 를 임시 폴더로 복사(world 없이), server.properties level-seed=<고른 시드>, 플러그인 최신 jar,
  명령: `village build` → `village pregen 192` → `village selftest` → stop. 그 world 폴더에서 `session.lock`·`uid.dat` 를 빼고
  `dist/world.zip` 으로. (uid.dat 를 빼야 서버마다 새 UID → §4.3 월드 적용이 동작)
- release.sh: world.zip 을 풀어 `Labyrinth-Server/world/` 로 넣는다. release/server.properties 에 `level-seed=<시드>`(월드 밖으로
  나가도 같은 지형이 이어지게).
- README: 새 서버는 그냥 켜면 됨. **이미 돌리던 서버 업데이트**: 서버 끄기 → `world` 폴더 이름을 `world_old` 로 → 새 zip 의 `world` 폴더 복사 →
  `world_old` 안의 `playerdata`·`advancements`·`stats` 폴더를 새 `world` 로 복사(인벤토리·엔더상자 유지) → 켜기. 미궁 레벨·칭호·골드는
  plugins/Labyrinth 에 있어 그대로. 예전 월드에 지은 건물은 world_old 에 남는다(돌아가려면 폴더 이름만 되돌리기).

## 5. 미술 방향 — "화려한 판타지 RPG"

바닐라 블록만으로, 멀리서 봐도 실루엣이 또렷하고 색이 풍부하게. 조각마다 주제색 하나 + 공통 재료로 통일감.

- 공통 재료: 바닥/기초 = 석재 벽돌·안산암·응회암 벽돌·이끼 낀 변형 섞기, 뼈대 = 짙은 참나무/가문비 원목 기둥(축 방향 맞춰), 벽 = 회반죽 느낌(흰색/
  크림색 테라코타·자작나무 판자·방해석), 지붕 = 짙은 색 계단+반블록으로 **처마가 튀어나오고 용마루가 있는** 박공/모임지붕(심층암 기와·
  체리/맹그로브/진홍 판자 계단 중 조각별 주제색), 창 = 색유리판 + 덧문(다락문), 조명 = 등불·영혼 등불·촛불을 넉넉히(밤에 몹 안 생기게, 광원 레벨 8+ 간격 7칸 이내).
- 금지: 네모 상자 건물, 한 가지 블록으로 된 넓은 면, 평지붕, 1칸 두께 밋밋한 벽만 있는 것. 벽은 기둥·가로보·창틀로 리듬을 준다.
- 조각 목록(id · 이름 · 대략 크기 W×H×D · 주제색 · 마커):
  1. `labyrinth_gate` · 미궁의 아가리 · ~15×18×11 · 자수정/심층암/금 · `entrance`, `npc guide`(벨라), `interact entrance`(문 안쪽 면 블록들), `ambient portal`.
     거대한 룬 아치 + 아래로 내려가는 계단 + 검은 문면(검은 콘크리트·우는 흑요석) + 쇠사슬·영혼 등불·자수정 군락. 마을의 상징.
  2. `plaza` · 등불 광장 · ~21×8×21 · 흰 돌/청록 · `spawn`. 무늬 깔린 원형 광장, 가운데 분수(물 source 웅덩이 + 수정 조각상/엔드 막대), 벤치, 화단, 게시판(표지판).
  3. `forge` · 두르간의 대장간 · ~13×12×11 · 주황/검정 · `npc blacksmith`, `interact blacksmith`(모루·대장장이 작업대), `ambient embers`.
     돌 아래층 + 큰 굴뚝(꼭대기 모닥불 연기), 앞이 트인 작업장, 용암 가마솥, 모루, 숫돌, 쇠사슬.
  4. `class_hall` · 전직의 전당 · ~15×20×13 · 파랑/흰색/금 · `npc class_master`, `interact class`. 탑이 있는 전당, 색유리 창, 깃발(6직업 색).
  5. `archive` · 기록 보관소 · ~11×14×11 · 보라/짙은 나무 · `npc title_keeper`, `interact titles`. 책장 벽, 독서대, 촛불, 유리 돔/천창.
  6. `market` · 핀의 떠돌이 상점 · ~11×7×9 · 원색 줄무늬 천막 · `npc merchant`, `interact merchant`. 줄무늬 양털 천막 2~3개, 통·상자 더미, 매달린 등불, 수레.
  7. `inn` · 검은 등불 여관 · ~13×14×11 · 초록/나무 · (NPC 없음) 2층 + 발코니 + 걸린 간판.
  8. `house_a`, `house_b`, `house_c` · 마을집 · ~7~9 × ~10 × ~7~9 · 서로 다른 지붕색.
  9. 장식: `lamp_post` (2~3종), `bench`, `well`, `flower_bed`, `tree_cherry`, `tree_oak` (잎 persistent), `signpost`, `cart`.
- 마을 크기: 반경 ~32 (지름 ~65) 안에 다 들어가게. 광장 북쪽에 게이트, 광장 둘레에 대장간·전당·보관소·상점, 바깥에 여관·집·장식.

## 6. 검증 기준 (끝났다고 하려면)
1. `build_all.py` — 모든 조각 JSON 생성, 팔레트 문자열 형식, 금지 블록 없음, 발자국 겹침 없음, 마커 좌표가 크기 안,
   npc 마커 id 가 npcs.yml 에 있음, 연결 블록 상태 명시. 경고 0.
2. Java 단위 테스트: 청사진 파싱, 회전 좌표 공식 4방향(좌표 + facing 블록), 마커 회전, 목표 높이장(가짜 높이맵: 단 고정, 이웃 차 ≤1, 띠에서 원래 높이로 수렴).
3. 테스트 서버: `village build` 후 `village selftest` 예외 0 · mismatched=0 · npcs=5/5, 미궁 `labadmin selftest` 예외 0.
4. 배포 zip 을 빈 폴더에 풀어 켰을 때 마을이 있고 스폰이 광장, NPC 5명, 게이트 우클릭 → 입구 메뉴.
5. 렌더: 평지 위 마을 전체 PNG + 실제 월드 덤프 PNG — 사람이 봐서 "화려한 판타지 마을"로 보이고 지형이 자연스러울 것.
