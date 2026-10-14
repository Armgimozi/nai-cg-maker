# 등불 어귀 마을 — 설계 계약 (VILLAGE.md)

미궁 입구 마을을 **원래 월드(오버월드)** 에 짓는다. 사용자 규칙 "기존 지형 무시하고 막 만들지 마셈"을 지키는 것이 최우선:

- 지형을 밀어 평평하게 만들지 않는다. 건물(조각)마다 그 자리 땅높이에 맞춰 앉히고, 깎기·메우기는 조각당 몇 칸으로 제한한다.
- 사람이 지은 블록(자연 블록이 아닌 것)·컨테이너·물/용암이 걸리는 자리는 **거절**한다.
- 바꾸는 블록은 **전부 원래 상태를 기록**하고, 제거하면 기록 그대로 되돌린다(한 칸도 틀리지 않게).
- 짓기 전에 미리보기(파티클 외곽선 + 바뀌는 블록 수)를 보여 주고 확정을 받는다.

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
| `plugin/src/main/java/kr/labyrinth/village/*` | VillageModule · VillageService · 계획/배치/복원/보호/명령/메뉴 | Java |

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

### 2.3 높이 규칙 (지형 맞춤)
- `floor_y`: 걸어 다니는 바닥 층의 layer 번호. 바닥 블록이 이 층에 있고, 사람은 `floor_y + 1` 높이에 선다.
- `anchor` = 정방향 기준 (x, z) 한 칸 (보통 정문 바로 안쪽 바닥). Java 는 그 칸의 **땅 높이 G** (가장 위의 자연 고체 블록 y)를 기준으로
  layer y 를 월드 Y = `G + (y − floor_y)` 에 놓는다. 즉 바닥 층이 원래 땅 맨 윗블록을 대신한다 → 정문 앞이 땅과 같은 높이.
  - 조각 발자국 안 땅 높이 범위가 너무 크면(`max − min > max_cut + max_fill`) 그 자리는 실패.
  - G 는 발자국 땅 높이의 [min, max] 안으로 자르고, 깎기(G 보다 높은 땅) ≤ `max_cut`, 메우기(G 보다 낮은 땅) ≤ `max_fill`.
- **메우기**: 발자국 안 칸(그 열에 공백이 아닌 글자가 하나라도 있는 x,z)에서, 조각의 가장 낮은 비공백 블록 아래부터 실제 땅 바로 위까지
  `foundation_mix`(가중치 무작위, 좌표 해시로 결정적) 블록으로 채운다. 채우는 자리는 대체 가능 블록이어야 함.
- **깎기**: 발자국 안 칸에서 조각 꼭대기 층보다 아래이면서 글자가 `.` 인 자리는 지운다. 조각 높이 위로는 손대지 않는다.
- 기본값: `max_cut` 3, `max_fill` 4, `foundation` 은 첫 번째 mix 블록.

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
- `paths`: 꺾은선 점들(마을 좌표) 사이를 `width` 폭으로 칠한다. 각 칸에서 땅 맨 윗블록(흙·풀·모래 같은 표면 블록일 때만)을
  스타일 블록으로 바꾸고, 그 위 한 칸의 풀·꽃·눈은 지운다(기록). 조각 발자국 안 칸은 건너뜀. 물 위는 건너뜀(감점).
  지형을 따라가므로 길은 오르내린다(평탄화 안 함).
- 조각 발자국끼리 겹치면 안 된다 (build_all.py 가 검사). 장식 조각(가로등·벤치·나무·화단)도 조각으로 배치한다.

---

## 4. Java 동작

### 4.1 자리 고르기
- **자동**: 월드 스폰(또는 명령을 친 사람 위치) 주변을 나선형으로 후보 중심(8칸 간격, 반경 최대 `village.search_radius` 기본 384)을 돌며
  마을 계획을 세워 보고, 하드 조건을 통과한 것 중 점수가 가장 낮은 곳. 회전 4가지도 시도. 후보 계산은 여러 틱에 나눠
  (틱당 시간 예산 ~15ms) 서버가 멈추지 않게. 청크는 필요할 때 로드 (`World#getChunkAtAsync` 또는 틱 분할 동기 로드).
- **여기**: 명령 친 사람 위치가 중심, 바라보는 방향이 마을 정방향(게이트 쪽) — 실패하면 이유를 알려 줌.
- 하드 조건 (하나라도 걸리면 그 후보 실패):
  - 바뀌는 칸(조각 비공백 칸, 메우기, 깎기, 길)에 **자연 블록이 아닌 것**이 있음 → 사람이 지은 것으로 보고 거절.
    자연 블록 = 공기, 흙 계열(흙·풀블록·거친흙·회백토·균사체·뿌리흙·진흙), 돌 계열(돌·화강암·섬록암·안산암·심층암·응회암·석회암 계열 자연석),
    모래·붉은 모래·자갈·사암(자연), 점토, 눈·눈 블록·얼음(깎기만, 위에 짓지 않음), 식물(풀·고사리·꽃·덤불·묘목·버섯·사탕수수·대나무·덩굴·이끼 카펫·꽃잎),
    잎(persistent=false 인 것만), 광석(깎기만), 구멍 없는 동굴덩굴 등. 그 외(판자·유리·양털·상자 등) = 인공.
  - 블록 엔티티(상자·표지판 등)가 있는 칸.
  - 원목(log/stem) — 나무를 반쯤 자르면 공중에 뜬 나무가 남으므로 거절(자동 탐색에서 자연스럽게 피함).
  - 물·용암이 조각 발자국 + 2칸 여유 안에 있음.
  - 조각별 깎기/메우기 한도 초과.
- 점수 = Σ(깎기 칸수 + 1.3×메우기 칸수) + 0.5×지운 잎 + 20×물 위 길 칸 + 0.05×탐색 시작점 거리 + 조각 높이 차(인접 조각 G 차이 > 4 이면 그만큼 가산).

### 4.2 짓기 · 기록 · 복원
- 계획 = 바뀔 칸 목록 (순서: 아래→위, 메우기 → 조각 → 길 → 마커 후처리). 확정하면 **놓기 전에** 원래 블록 기록을
  `plugins/Labyrinth/village/undo.txt.gz` (한 줄: `x y z|blockdata`) 와 `plugins/Labyrinth/village/state.yml` (state: building) 에 저장.
- 틱당 `village.blocks_per_tick`(기본 3000)개씩 `setBlockData(data, false)` (물리 없음). 끝나면 표지판·깃발 후처리, NPC 배치, 입구·스폰 설정, state: built.
- 서버가 짓는 도중 꺼졌으면: 다음 시작 때 state: building → 자동으로 기록대로 되돌린 뒤 state 삭제 (로그 남김).
- 제거: 기록을 **역순**으로 틱당 같은 속도로 되돌림 → 표지판/깃발 블록 엔티티는 원래 블록으로 덮이므로 자연히 사라짐.
  NPC 제거, 입구 설정 비우기(마을 입구였으면), 월드 스폰·스폰 반경 원래대로, 파일 삭제. 제거 도중 꺼짐 → 다음 시작에 이어서 복원.
- 같은 칸이 두 번 기록되지 않게(처음 원래 값만) 한다.

### 4.3 보호 (마을 블록 = 기록에 있는 칸 + 조각 발자국 상자 안)
- 부수기 취소 (관리자도. 메시지: "마을 건물은 부술 수 없습니다. (관리자: /labadmin village remove)").
- 조각 발자국 상자 안 블록 놓기 취소 (관리자 제외).
- 폭발 목록에서 마을 블록 제외, 불 번짐/타기 취소, 피스톤이 마을 블록을 밀기/당기기 취소, 엔더맨 등 엔티티 블록 변경 취소,
  마을 물(분수)이 흘러 나가는 것 취소(BlockFromToEvent: from 이 마을 칸이고 to 가 마을 칸이 아니면 취소).
- 마을 반경 안 자연 스폰 적대 몹 취소 (`CreatureSpawnEvent`, NATURAL, `Enemy`/`Monster`).
- 마을 블록 상호작용: 문·다락문·울타리 문·종·작업대는 허용, 침대 허용. 컨테이너(통·상자·화로류)·모루·숫돌·대장장이 작업대·
  독서대·양조대 등은 vanilla 창 대신 취소 — 단 `interact` 마커 칸이면 해당 메뉴를 연다.

### 4.4 NPC · 입구 · 스폰
- `npc` 마커 → `services.npcs().place(id, loc)` (yaw = 회전 적용한 face). 마을 제거 시 그 NPC 들 `remove`.
- `entrance` 마커 → config `entrance.*` 에 저장 (mode `village`). 기존 석문 입구가 있으면 먼저 그 복원(석문 블록 되돌림) 후 교체.
  (석문 → `EntranceService.removeEntrance()` 를 부를 수 있게 dungeon 쪽에 공개 접근자 하나 추가)
- 게이트 `interact`(entrance) 칸 우클릭 → `services.menus().openEntrance(p)`. `ambient` 마커 파티클.
- `spawn` 마커 → `village.set_world_spawn: true` 면 월드 스폰을 그곳으로(원래 값 저장), 스폰 반경 게임룰 0 (원래 값 저장). 제거 시 복구.

### 4.5 명령 · 권한 · 메뉴
- `ServerSetup.canBuildVillage(sender)`: 콘솔/관리자 = true, 아니면 `setup.everyone_can_build_village`(기본 true) **그리고 마을이 아직 없을 때**.
- `/미궁 마을` (`/lab village`, `/lab 마을`):
  - 마을 있음 → 광장 스폰으로 텔레포트 (미궁 안이면 거절: "먼저 /미궁 귀환"). `village.teleport_command: true` 일 때.
  - 마을 없음 + canBuild → 마을 짓기 메뉴 (자동: 스폰 근처 / 여기 / 취소) → 계획 → 미리보기(외곽선 파티클 30초 + 채팅
    "바뀌는 블록 N개 · 깎기 a · 메우기 b · 위치 (x, z)" + 클릭 버튼 [확정] [취소]) → `/lab village confirm <토큰>`.
  - 마을 없음 + 권한 없음 → 안내.
- 관리자/콘솔: `/labadmin village build [auto|here]` (미리보기→확정 없이 바로 짓기는 `build auto now`), `remove`, `info`,
  `preview [auto|here]`, `selftest`, `dump`.
- `selftest` (콘솔 가능): 자동 자리 찾기 → 짓기 → 모든 계획 칸이 계획대로인지 검사 → NPC 배치 확인 → 제거 → 기록된 모든 칸이
  원래 블록과 같은지 검사 → 결과 한 줄 (`[마을 자가 진단] 결과: 예외 0 · placed=… mismatched=0 · restored=… diff=0 · …`).
  `selftest keep` 은 제거하지 않고 남겨 둔다(렌더 확인용).
- `dump`: 마을 경계 상자 + 8칸 여유의 모든 비공기 블록을 `plugins/Labyrinth/village/dump.txt` (`x y z|blockdata`)로 → `render.py --dump` 가 실제 지형 위 모습을 그림.
- 초기 설정 메뉴(SetupMenu) 입구 방식에 **마을 (추천)** 추가 → 확정 시 난이도 적용 후 마을이 없으면 자동 자리 찾기 → 미리보기/확정 흐름.
- 메인 메뉴 51번 칸: "마을" 버튼 (`/미궁 마을` 과 같음).
- 접속 시: 난이도는 정했는데 마을이 없고 canBuild 면 한 번 안내 ("/미궁 마을 로 스폰 근처에 마을을 지을 수 있어요").

### 4.6 config.yml
```yaml
village:
  set_world_spawn: true      # 마을 광장을 월드 스폰으로 (원래 스폰은 기억했다가 마을 제거 시 복구)
  teleport_command: true     # /미궁 마을 로 광장 텔레포트 허용
  search_radius: 384         # 자동 자리 찾기 반경 (스폰 기준, 블록)
  blocks_per_tick: 3000      # 짓기/복원 속도
  block_mob_spawns: true     # 마을 안 적대 몹 자연 스폰 막기
setup:
  everyone_can_build_village: true   # 마을이 아직 없을 때만 op 아닌 사람도 지을 수 있음 (옮기기·제거는 관리자/콘솔)
```

---

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
1. `build_all.py` — 모든 조각 JSON 생성, 팔레트 문자열이 형식에 맞고(정규식), 금지 블록 없음, 발자국 겹침 없음, 마커 좌표가 크기 안,
   npc 마커 id 가 npcs.yml 에 있음, 연결 블록 상태가 명시됨. 경고 0.
2. Java 단위 테스트: 청사진 파싱, 회전 좌표 공식 4방향, 마커 회전, 깎기/메우기 계산(가짜 높이맵), 점수.
3. 테스트 서버 `/labadmin village selftest`: 예외 0 · mismatched=0 · diff=0 · NPC 5명 배치.
4. 렌더: 평지 위 마을 전체 PNG + 실제 서버 덤프 PNG — 사람이 봐서 "화려한 판타지 마을"로 보일 것.
