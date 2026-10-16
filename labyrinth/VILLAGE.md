# 등불 어귀 마을 — 설계 계약 (VILLAGE.md)

미궁 입구 마을을 **미리 지어 둔 오버월드(world 폴더)** 째로 서버팩에 넣는다 (사용자 결정: "증강 스카이블럭 방식",
"미리 지은 월드만"). 서버를 처음 켜면 이미 마을이 있고, 스폰이 마을 광장이다.

- 우리가 시드를 골라 만든 월드라서 마을 자리 지형은 **설계해서 다듬는다**(계단식 단·옹벽·완만한 경사). 단, 사용자 규칙
  "기존 지형 무시하고 막 만들지 마셈" 정신대로 **자연스럽게**: 넓은 평판 + 절벽 같은 티 나는 평탄화 금지, 마을 바깥으로 갈수록
  원래 지형에 부드럽게 이어지게, 나무는 반쯤 잘린 채 남기지 않는다.
- 월드는 개발 환경(테스트 서버)에서 플러그인 관리자 명령으로 지은 뒤 world 폴더를 압축해 배포 zip 에 넣는다 (증강 스카이블럭의
  `augadmin buildmap` 과 같은 방식). 다른 시드·이미 쓰던 월드에 자동으로 짓는 기능은 **만들지 않는다**.

이 문서는 Java(플러그인)와 Python(설계 도구)이 함께 따르는 계약이다. 숫자·이름은 여기 적힌 대로 쓴다.

## 0. 지형 존중 규칙 (사용자 요청: "기존 지형 고려하면서 해. 대충 복붙식으로 했다가 겹치지 말고")
마을을 정해진 모양 그대로 찍어 누르지 않는다. 지형을 먼저 보고, 지형에 맞춰 놓는다.

- **자리·방향**: survey 는 후보 자리마다 마을 회전 4방향을 모두 계산해 원래 지형을 가장 적게 바꾸는(깎기+메우기 총량 최소)
  자리·방향을 고른다. 경사가 있으면 그 방향을 살려 단을 놓는다(예: 높은 쪽에 게이트, 낮은 쪽에 집들).
- **조각 높이**: 조각 단 높이 P 는 그 조각 자리의 원래 높이를 따른다(anchor 주변 중앙값). 광장 높이 기준 ±6 까지 허용.
  한 조각에서 깎기나 메우기가 4칸을 넘으면 그 자리·방향 후보는 탈락.
- **조각 위치 조정**: layout 의 조각 위치는 기준점이다. 조각마다 `"slack"`(기본 2)칸 안에서 위치를 옮겨 깎기·메우기가 가장 적은
  곳에 놓는다(다른 조각·길과 1칸 여유 유지, 정면 방향은 그대로). 장식 조각은 slack 3.
  장식 조각(가로등·나무·화단·표지판 …)은 slack 안 어느 자리도 지형 한도·동굴·1칸 여유에 맞지 않으면 **그 장식만 빼고** 짓는다
  (억지로 끼우거나 지형을 더 깎지 않음 — 계획 줄에 `장식 생략 n [...]`, survey 점수에 하나당 벌점 150). 건물은 하나라도 맞지 않으면 그 후보 탈락.
  layout 의 평지 계획(Java `BundledVillageTest`)에서는 장식이 하나도 빠지면 안 된다(빌드 실패).
- **겹침 금지** — 짓기 전에 검사해서 하나라도 걸리면 짓지 않고 이유를 출력한다:
  - 조각끼리, 조각과 길이 겹치거나 1칸 여유 안에 붙음.
  - R+B 안에 자연 생성 구조물·사람이 지은 블록(판자·유리·양털·상자 같은 비자연 블록, 블록 엔티티 — 바닐라 마을·폐허 포털·전초기지·
    난파선 등)이 있음 → 그 후보 탈락(survey 가 거르고, build 는 거절).
  - 조각 발자국 아래 6칸 안에 동굴(공기 덩어리)이 있으면 기초를 그 깊이까지 내려 막는다 — 건물 밑이 비어 떠 보이지 않게.
  - 물·용암이 R+B 안에 있음.
- **짓고 나서 검사** (`village selftest`): 조각 '.' 칸이 전부 공기(실내에 흙·잎·나무가 끼지 않음), 조각 블록이 청사진대로,
  다듬은 영역에 공중에 뜬 지형 블록 없음, 남은 나무 조각(원목 없는 잎 덩어리·잎 없는 원목) 없음, 길 칸 높이 차 ≤1(계단·반블록 예외),
  조각 정문 앞 칸과 바깥 땅 높이 차 ≤1(걸어서 들어갈 수 있음). 결과 줄에 `overlaps=0 floating=0 tree_remnants=0 blocked_doors=0`.

---

## 1. 파일 배치

| 경로 | 내용 | 담당 |
|---|---|---|
| `tools/village/vlib.py` | 조각 그리기 라이브러리 (캔버스, 모양 도우미, 블록 상태 도우미, 연결 상태 계산, JSON 내보내기) | 설계 도구 |
| `tools/village/render.py` | 등각(isometric) PNG 렌더러 — 조각 JSON / 마을 전체 / 서버 덤프 | 설계 도구 |
| `tools/village/pieces_*.py` | 조각 설계 코드 (실행하면 JSON 생성) | 설계 |
| `tools/village/build_all.py` | 모든 조각 + layout 생성 → `plugin/src/main/resources/village/` 에 씀, 검증 (`--render` → `/tmp/village_renders/`) | 설계 도구 |
| `tools/village/blockdata.json` | 26.x 바닐라 블록 상태 표(속성 이름·값·기본값)·태그·모양·텍스처 평균색 — vlib 검증·render 색의 기준 (생성물, 커밋함) | 설계 도구 |
| `tools/village/gen_blockdata.py` | blockdata.json 생성기 (서버 jar 데이터 생성기 `--reports` + 클라이언트 jar 모델·텍스처). 버전 올릴 때만 | 설계 도구 |
| `tools/village/README.md` | 조각 설계자용 사용법 | 설계 도구 |
| `plugin/src/main/resources/village/pieces/<id>.json` | 조각 청사진 (생성물, 커밋함) | 생성물 |
| `plugin/src/main/resources/village/layout.json` | 마을 배치 (생성물, 커밋함) | 생성물 |
| `plugin/src/main/java/kr/labyrinth/village/*` | VillageModule · 청사진 파서 · VillageBuilder(지형 다듬기+짓기, 관리자 명령) · VillageService(실행 중: 보호·NPC·입구·텔레포트) | Java |
| `tools/village/pieces_signs.py` | layout 에 맞춘 길잡이 표지판 글 (`make_signpost` 변형, 동서남북 대신 '광장 왼편/오른편') | 조립 |
| `tools/build_world.sh` | 테스트 서버 복사본에서 시드로 월드 생성 → 마을 짓기 → 주변 청크 미리 생성 → 자가 진단 → 덤프 → 정지 → `dist/world.zip`·`dist/world.seed`·`dist/village-dump.txt`·`dist/world-build.log` | 조립 |

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
  "deco": false,
  "door": true,
  "slack": 2,
  "max_cut": 3,
  "max_fill": 4,
  "palette": { "#": "minecraft:stone_bricks", "s": "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]" },
  "layers": [ ["row z=0 (W글자)", "row z=1", "..."], ["y=1 ..."] ],
  "markers": [ { "type": "npc", "id": "blacksmith", "pos": [x, y, z], "face": "front" } ]
}
```

- 선택 필드: `deco` (장식 조각 — slack 3, 정문 검사 생략. 없으면 id 접두어로 판단: `lamp_post`·`bench`·`well`·`flower_bed`·`tree_`·
  `signpost`·`cart`·`fence`·`planter`·`statue`·`banner_pole`·`crate`·`barrel_stack`·`hay`), `door` (false 면 정문 앞 걸어 들어가기 검사 생략),
  `slack` (§0 위치 조정 칸 수, layout 항목의 slack 이 우선). vlib: `Piece(..., deco=, door=, slack=)`.

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
- 팔레트 글자는 한 조각 안에서 유일하면 아무 글자나 된다 (`' '`, `'.'` 제외). 글자가 모자라면 유니코드 아무 글자
  (Java 는 코드포인트 단위로 읽는다; vlib 는 BMP 글자만 쓴다).
- 블록 이름·속성은 26.x 기준 (blockdata.json 이 데이터 생성기 결과). 예전 이름 주의: `chain` → `iron_chain`, `grass` → `short_grass`.
  vlib 는 없는 블록·속성·값을 넣는 즉시 예외로 알려 주고, finalize 때 빠진 속성을 바닐라 기본값으로 채워 **모든 속성을 명시**한다.

### 2.3 높이 규칙
- `floor_y`: 걸어 다니는 바닥 층의 layer 번호. 바닥 블록이 이 층에 있고, 사람은 `floor_y + 1` 높이에 선다.
- 짓는 쪽(VillageBuilder)이 조각마다 **단 높이 P** 를 정하고 그 단까지 지형을 다듬은 뒤, layer y 를 월드 Y = `P + (y − floor_y)` 에 놓는다
  (바닥 층이 단의 맨 윗블록 자리). `floor_y` 아래 layer(기초·주춧돌)는 땅속으로 들어간다 — 경사진 단 가장자리에서 보이는 기초를
  1~2층 넣으면 보기 좋다.
- 건물을 단보다 한 칸 높이 올리고 싶으면(앞 계단으로 오르는 받침) `floor_y` 를 **땅 높이 층**(바깥 땅·정문 앞 칸과 같은 층)으로
  두고 실내 바닥은 `floor_y + 1` 층에 깐다 (예: `class_hall`). `floor_y` 를 실내 바닥에 두면 단 전체가 그 높이로 다듬어져 받침이 안 보인다.
  이때 `anchor` 는 실내 마루가 아니라 **앞 디딤단 줄**(바깥 땅과 같은 층)에 둔다 — selftest `blocked_doors` 가 anchor 위 두 칸(P+1, P+2)이
  트였는지 보므로(공기·문·아래 반블록만 통과) 디딤단은 아래 반블록으로.
- `anchor` = 정방향 기준 (x, z) 한 칸 (보통 정문 바로 안쪽 바닥). 단 높이를 정할 때 그 칸 주변 원래 땅높이를 가장 무겁게 본다.
- `foundation`/`foundation_mix`: 단 가장자리 옹벽·기초에 쓰는 블록. `max_cut`/`max_fill` 은 쓰지 않는다(있어도 무시).

### 2.4 마커
| type | 필드 | 뜻 |
|---|---|---|
| `npc` | `id`(npcs.yml id), `pos`, `face` (`front`/`back`/`left`/`right`, 정방향 기준; front=북, back=남, left=서(−X), right=동(+X) — 건물이 북쪽을 볼 때 건물의 왼손/오른손) | NPC 를 그 칸(발 칸) 가운데, 바닥 위에 세움. 회전 적용 |
| `entrance` | `pos`, `face` | 미궁 입구 위치(config entrance). 파티 모이는 곳·귀환 자리. 게이트 조각에 하나. 파티원은 이 점에서 `entrance.radius`(기본 8) 안에 있어야 입장되므로 우클릭하는 문면 바로 앞 바닥에 둔다 (`labyrinth_gate`: 계단 아래 문면 앞, 앞마당 계단 꼭대기까지 반경 안) |
| `interact` | `action` (`entrance`/`blacksmith`/`class`/`titles`/`merchant`/`main`), `pos` 들 (`"pos": [[x,y,z], ...]`) | 그 블록 우클릭 → 메뉴 열기 |
| `spawn` | `pos`, `face` | 마을 스폰(월드 스폰·/미궁 마을 텔레포트). 광장 조각에 하나 |
| `sign` | `pos`, `lines` (최대 4줄, MiniMessage), `glow` (bool), `back`(선택) | 놓은 뒤 표지판 글 쓰기. 그 자리 블록은 팔레트에서 표지판이어야 함 |
| `banner` | `pos`, `patterns` `[["pattern_key", "color"], ...]` | 놓은 뒤 깃발 무늬 (자리 블록은 팔레트의 `*_banner`/`*_wall_banner`) |
| `ambient` | `pos`, `fx` (`portal`/`embers`/`fountain`/`magic`/`smoke`) | Java 가 주기적으로 파티클 (게이트 소용돌이, 대장간 불씨 등) |
| `light` | `pos` | 정보용 (조명 위치, 렌더러가 표시) |

npc·spawn·entrance 의 `pos` y 는 **발이 놓이는 칸**(보통 `floor_y + 1`). Java 는 지은 뒤 그 칸이 막혔으면 위로, 발밑이 비었으면 아래로 최대 3칸 맞춘다.
interact 의 `pos` 는 우클릭할 **블록 자체**(공기 칸이면 자가 진단 interact 에서 빠짐). sign/banner 의 `pos` 는 그 블록 자리.

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
  가운데 칸 = 발자국 최소 모서리 + (회전 후 폭 // 2, 깊이 // 2) — 즉 최소 모서리 = `at − (w//2, d//2)` (짝수 폭도 이 규칙).
  `front` = 조각 정면이 바라볼 방향(마을 정방향 기준).
- 마을 전체도 회전할 수 있다 (`StructureRotation` 하나): 각 조각 발자국 **상자의 두 모서리**를 (x, z)→(−z, x) 식으로 돌려 새 상자를 잡고
  (짝수 폭에서 `at` 만 돌리면 1칸 어긋나 여유가 깨질 수 있음), 각 조각 front 에 같은 회전을 더한다. 길 점도 같은 식으로 돌린다.
- 조각 항목 선택 필드: `"dy": n` (단 높이를 H0 기준으로 고정), `"slack": n` (§0 위치 조정 칸 수 — 조각 JSON 의 slack·장식 기본 3보다 우선).
  layout 선택 필드 `"blend": 16` (§4.1 혼합 띠 B).
- `paths`: 꺾은선 점들(마을 좌표) 사이를 `width` 폭으로 칠한다. 다듬은 지형(§4.1) 맨 윗블록을 스타일 블록으로 바꾸고 그 위 한 칸
  식물은 지운다. 조각 발자국 안 칸은 건너뜀. 길 높이는 양 끝 단 사이를 완만하게 잇는다(§4.1 목표 높이장).
- 선택: `"terraces"` — 추가 단 `{ "at": [x, z], "size": [w, d], "dy": 2 }` (광장 높이 H0 기준 상대 높이, 예: 게이트를 광장보다 2칸 높은
  단에 올려 계단으로 오르게). 조각 단 높이를 직접 고정하려면 조각 항목에 `"dy": n` (H0 기준).
- 조각 발자국끼리 겹치면 안 된다 (build_all.py 가 검사). 장식 조각(가로등·벤치·나무·화단)도 조각으로 배치한다.
  겹침 판정은 Java `Planner.overlaps` 와 같다: 조각이 **차지한 기둥**(어느 층이든 `' '` 가 아닌 칸이 있는 (x, z)) + 둘레 1칸(8방향)이
  다른 조각의 차지한 기둥에 닿으면 안 됨.
- 길 칸 = 중심선(홀수 폭은 점이 칸 가운데, 짝수 폭은 칸 모서리)까지 거리 ≤ 폭/2 − 0.01 인 칸 (Java `PathRaster`, vlib `path_cells`).
  길 끝점이 어떤 조각의 차지한 기둥에서 체비셰프 2칸 안이면 그 조각에 **붙은 길** — 붙은 조각과는 닿아도 되고(문 앞까지 이어짐,
  slack 으로 조각이 옮겨지면 끝점도 같이 옮김), 그 밖의 조각과는 길 칸 + 둘레 1칸이 닿으면 안 된다. 정문 앞 칸(anchor 에서 정면으로
  발자국을 벗어난 첫 칸)은 다른 조각과 그 둘레에 들어가면 안 된다 (장식·`door: false` 제외).

---

## 4. Java 동작

### 4.1 지형 다듬기 + 짓기 (VillageBuilder — 개발용 관리자 명령)
`/labadmin village build [here | <x> <z>] [north|east|south|west] [force]` (콘솔 가능).
- 자리·방향을 **둘 다 안 주면**: 월드 스폰 둘레 64칸 안(4칸 간격) × 4방향을 survey 와 같은 계획기로 비교해 지형을 가장 덜 바꾸는 자리·방향.
- 자리만 주면(`here` / `<x> <z>`): 그 자리에서 4방향 중 가장 덜 바꾸는 방향. 방향만 주면: 월드 스폰 자리, 그 방향. 둘 다 주면 그대로.
- 계획이 §0 검사에 하나라도 걸리면 **블록을 하나도 바꾸지 않고** 이유(+4방향별 결과)를 출력한다.
- `force` (개발용): 이미 마을이 있어도 다시 짓는다. 자리·방향을 안 주면 예전 마을 자리·방향 그대로. 먼저 예전 조각·길 상자와 다듬은 칸의
  비자연 블록(옹벽 등)을 예전 목표 높이의 자연 땅(잔디·흙·돌)으로 되돌린 뒤 다시 조사한다.
- 실행 중 작업은 하나만 (`village cancel` 로 취소). 무거운 계산(조사·계획·나무 찾기)은 ChunkSnapshot + 비동기 스레드, 블록 바꾸기는
  틱 분할(틱당 `village.blocks_per_tick` 기본 4000 블록 **그리고** 35ms 이하)로 아래 순서를 실행하고 몇 초마다 진행률을 알린다.
1. **조사**: 마을 반경 R + 혼합 띠 B(layout `blend`, 기본 16) + 14칸(나무가 띠 밖으로 뻗은 부분) 안의 원래 땅높이(나무·풀·눈·잎 제외한 맨 위
   자연 고체 블록), 맨 윗 땅 블록(바이옴 표면), 땅 아래 16칸 빈칸 비트(동굴), 물·얼음·비자연 블록 표시, 원목 수, 바이옴을 수집.
   R = max(layout radius, 가장 먼 조각 칸 + slack + 1) — 조각이 radius 밖으로 나가도 띠가 조각을 자르지 않게.
2. **나무 치우기**: 마을이 **손대는 열**(고정 칸 = 조각 발자국·여유 칸·정문 앞·길·추가 단과 그 둘레 2칸, 목표 높이가 바뀐 칸, 옹벽 칸)에 걸친 나무 = 그 열의 원목 + 그 열의 잎에서 잎을 따라
   7칸 안에 닿는 원목을 씨앗으로, 원목끼리(26방향) 이어진 덩어리째 지운다(띠 밖으로 뻗은 부분 포함, 상한 8만). 잎은 남는 원목에서 잎을 따라
   6칸 안에 닿지 않는 것(바닐라 잎 거리 규칙)을 지운다 — 반쯤 잘린 잎 덩어리가 남지 않는다. 덩굴·코코아·벌집·창백한 이끼·송진, 지운 잎 위
   눈 한 겹도. 지운 줄기 밑 흙(나무가 잔디를 흙으로 바꿔 둔 자리)은 잔디로. **그대로인 땅에 선 나무는 남긴다** — 숲 가장자리가
   동그랗게 잘리지 않고 마을 모양을 따라 자연스럽게 남고, 건물·길에서 떨어진 원래 나무는 마을 안에도 남는다.
   풀·꽃·덤불·낙엽은 손대는 열에서만 지운다(R 안이라도 그대로인 땅의 풀꽃은 남김 — 동그란 민둥 자국 방지). 눈 한 겹: 그대로인 칸은 그대로,
   바뀐 칸은 원래 눈 덮였으면 다시 덮는다(길·정문 앞·발자국 제외) — 눈 덮인 들판 가운데 초록 원판이 생기지 않게.
3. **목표 높이장**: 광장 높이 H0 = 중심 반경 6 의 원래 높이 중앙값. 각 조각 발자국(+1칸 여유) = 그 조각 단 높이 P
   (anchor 주변 원래 높이 중앙값을 H0±6 으로 자름 → 자연스러운 계단식 단. 조각 위치는 §0 slack 안에서 지형에 맞게 옮긴 뒤). 길 칸 = 길 양 끝 단 사이 선형 보간.
   그 밖의 R 안 칸 = 가까운 단·길 높이들의 거리 가중 평균과 원래 높이를 섞음, R~R+B 띠에서는 원래 높이 쪽으로 점점(smoothstep) 돌아감.
   이웃 칸 높이 차는 최대 1 이 되게 몇 번 부드럽게(조각 단은 고정). 단과 그 주변 차가 2 이상이면 그 단 가장자리를 옹벽(foundation_mix +
   이끼 섞기)으로.
   **Java 구현 (`Planner` + `HeightField`, 순수 함수·단위 테스트)**:
   - 단 P = 발자국 칸 원래 높이의 가중 중앙값(anchor 체비셰프 ≤1 가중 4, ≤3 가중 2, 나머지 1) → [발자국+여유 칸 최고−4, 최저+4] 로 자름
     (한 칸이라도 4 넘게 깎거나 메우면 그 위치 탈락) → H0±6. 조각 항목 `dy` 가 있으면 H0+dy 고정.
   - 이미 놓은 조각과 **붙은 길**로 이어진 조각은 |P − P_이웃| ≤ (두 발자국 밖 길 칸 사이 거리) 여야 한다 — 짧은 길이 걸어서 못 오르는
     턱이 되지 않게 (안 되면 그 위치 탈락, 이유 "길 경사").
   - 고정 칸 우선순위: 조각 발자국 > 정문 앞 칸 > 길 > 조각 여유 칸(+1, 두 조각 여유가 겹치면 낮은 쪽) > terraces.
   - 길 높이: 양 끝 높이를 조각 발자국 바로 밖 첫/마지막 길 칸에 고정하고, 그 사이는 직선 보간 ±2 안에서 원래 지형을 따라가되 중심선
     1칸마다 차 ≤ 1 (길이 언덕을 불도저처럼 직선으로 밀지 않게). 길끼리 만나는 끝은 먼저 그린 길 높이를 따른다.
   - 나머지 칸: 바뀐 양 Δ = 고정 − 원래 를 가려진 라플라스(감쇠 길이 6칸, SOR)로 퍼뜨려 `원래 + Δ` (= 가까운 단 높이를 거리에 따라 섞음,
     원래 굴곡은 그대로, 단에서 먼 곳은 거의 그대로). 띠에서는 Δ × (1 − smoothstep). R+B 밖은 손대지 않음.
   - 다듬기: 고정이 아닌 칸은 4방향 이웃 차 ≤ 1 이 될 때까지 (R 안 전부, 띠는 바뀐 칸과 그 이웃). 끝내 2 이상 높은 칸 = 옹벽.
4. **지형 적용**: 칸마다 목표보다 높은 땅은 공기로, 낮으면 흙으로 채우고 맨 윗블록은 잔디(원래 맨 윗블록이 모래·눈 같은 바이옴 표면이면
   그것). 물·용암이 R+B 안에 있으면 그 칸은 손대지 않는다(시드 고를 때 피함 — §4.5 survey).
   → §0 에 따라 물·용암·얼음이 R+B 안에 있으면 그 자리는 **계획 단계에서 탈락**(짓지 않음)으로 정리했다. 깎은 칸은 새 맨 윗블록 + 그 아래
   두 칸을 표면/속흙으로, 메운 칸은 묻힌 잔디를 흙으로. 바뀐 칸 바로 아래 3칸(조각 발자국은 6칸)의 빈칸은 막는다(얇은 껍질·뜬 건물 방지).
   원래 눈 덮였던 바뀐 칸은 눈 한 겹을 되살린다 (2번 참고).
5. **조각 짓기**: 회전(§2.1) 적용, P 기준(§2.3)으로 `setBlockData(data, false)`. `'.'` 는 공기, `' '` 는 다듬은 지형 그대로.
6. **길**: 다듬은 지형 맨 윗블록을 스타일 블록으로(위 한 칸 식물 제거). 높이가 1 바뀌는 곳은 그 스타일의 반블록/계단을 써도 좋다.
7. **후처리**: 표지판 글(MiniMessage → 컴포넌트), 깃발 무늬(26.x 레지스트리 키로 PatternType 조회).
8. **메타데이터 저장**: `<월드 폴더>/labyrinth-village.yml` (§4.2). 월드 스폰 = spawn 마커, 스폰 반경 게임룰 0(API 있으면), NPC 배치·입구 설정(§4.3).
같은 월드에서 다시 build 하면 거절(이미 있음) — `build force` 만 덮어씀(개발용).
NPC·스폰·입구 위치는 지은 뒤 발 칸이 막혔으면 위로, 발밑이 비었으면 아래로 최대 3칸 맞춘 값을 메타데이터에 적는다.
개발 중에는 `plugins/Labyrinth/village/layout.json`·`pieces/*.json` 이 있으면 jar 안 청사진보다 먼저 쓴다(jar 다시 빌드 없이 고쳐 보기).

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
# ── Java 가 함께 적는 것 (자가 진단·dump·force 용) ──
blend: 16                                                   # 혼합 띠 B. radius 는 계획기 R(조각이 넓으면 layout radius 보다 큼)
pieces: [ {index, piece, turns, origin: [x0, z0], floor: P, offset: [dx, dz]}, ... ]   # 회전 후 상자 모서리 · 단 높이 · slack 오프셋
paths: [ {index, width, style, points: [[x, z], ...], attach: [a, b], cells: "x,z,y;x,z,y;..."}, ... ]  # 월드 꺾은선(옮긴 뒤), 붙은 조각, 칸
terrain: {origin: [x0, z0], size: n, base: y, heights: <base64 바이트 = 목표 높이 − base>, changed: <base64 비트셋>}
build_id: <uuid>                                            # 짓기마다 새로 — §4.3 적용 열쇠
built_at: <ISO 시각>
plugin_version: 0.1.7
```
- 파일 자리 = `World#getWorldFolder()` — 26.x 에서는 `world/dimensions/minecraft/overworld/labyrinth-village.yml` (world 폴더 안이라 함께 배포).
- 위치 [x, y, z, yaw] 의 x/z 는 칸 가운데(.5), y 는 발 칸. 상자는 양 끝 포함.

### 4.3 VillageService (실행 중)
- 시작할 때 주 월드(`Bukkit.getWorlds().get(0)`) 폴더의 labyrinth-village.yml 을 읽는다. 없으면 마을 기능은 조용히 꺼짐(로그 1줄).
- **월드 적용**: `plugins/Labyrinth/village-applied.yml` 에 적용한 월드 UID 와 메타데이터 `build_id` 를 적는다. 둘 중 하나라도 다르면(배포 월드를
  처음 켰거나 기존 서버가 world 폴더를 새 것으로 바꿈 — UID 가 같은 복사본이어도 마을을 새로 지었으면 build_id 가 다름) →
  - 마을 NPC 들을 메타데이터 자리로 `services.npcs().place(id, loc)` (예전 월드 좌표에 있던 배치를 덮어씀).
  - config `entrance.*` = 메타데이터 entrance (mode `village`). 예전 석문 기록(entrance.yml)은 **복원하지 않고** 버린다
    (예전 월드 좌표라 새 월드를 망가뜨림) — dungeon 쪽에 `forgetSaved()` 같은 공개 메서드 최소 추가, entrance.yml → entrance.yml.old.
  - 이후 접속하는 플레이어 중 이 월드 UID 를 처음 보는 사람(PlayerData ext `village.world` = `"<월드 UID>:<build_id>"`)은 미궁 안이 아니면 마을 스폰으로 텔레포트
    (예전 월드 좌표에 서 있다가 땅속에 끼는 것 방지). 새 플레이어는 원래 스폰이 광장이라 그대로.
    미궁 안에 있던 사람은 미궁에서 나와 주 월드로 들어올 때(PlayerChangedWorldEvent) 같은 검사. 적용 순간 접속해 있던 사람은 본 것으로 친다.
  - 관리자가 다시 적용하려면 `village apply`.
- **보호** (protect 상자 안): 관리자가 아니면 부수기·놓기 취소("마을은 부수거나 바꿀 수 없습니다"), 관리자는 크리에이티브일 때만 허용.
  폭발 목록에서 제외, 불 번짐/타기 취소, 피스톤 밀기/당기기 취소, 엔더맨 등 엔티티 블록 변경 취소, 물 흐름이 상자 밖으로 나가는 것 취소,
  나무 성장(StructureGrowEvent) 이 상자 안 블록을 바꾸면 취소.
- **적대 몹 자연 스폰 취소**: center 반경 radius+8 안 `CreatureSpawnEvent` NATURAL/`Enemy` (`village.block_mob_spawns`). PATROL·REINFORCEMENTS 도.
  (0.3.5.1) `wild.spawns`(기본 all) 가 마을 월드 전체를 막으므로 `spawns: none` 일 때만 따로 의미가 있다. 플러그인 몹(PDC labyrinth)은 건너뜀.
- **야생 막기** (0.3.5.1, `WildService` — ARCHITECTURE §6.10): 마을 + 보호 상자 + `wild.border_margin` 둘레 바닐라 월드 경계, 마을 월드 자연 스폰 막기.
  네더·엔드는 막지 않는다. `/labadmin wild …`. 경계 기록은 월드 폴더(`labyrinth-village.yml` 옆) `labyrinth-wild-border.yml`.
  배포 월드를 지을 때(`tools/build_world.sh`)는 wild 를 끈다 — 경계가 world.zip 에 구워지지 않고, pregen 청크에 동물이 생기게.
- **상호작용**: interact 칸 우클릭 → 메뉴 (`entrance`→openEntrance, `blacksmith`→openBlacksmith, `class`→openClass, `titles`→openTitles,
  `merchant`→ 상인 NPC 와 같은 상점, `main`→openMain). protect 안의 문·다락문·울타리 문·종·작업대·침대는 허용, 그 밖의 컨테이너·모루·숫돌·
  독서대·양조대 등은 장식이라 취소. 블록을 바꾸는 손 도구(괭이·삽·도끼·가위·뼛가루·밀랍·부싯돌·양동이·염료)도 상자 안에서는 막는다.
  관리자가 크리에이티브에서 웅크리고 우클릭하면 메뉴 대신 평소처럼(꾸미기 수정용). 표지판은 지을 때 밀랍칠(글 수정 막기).
- **연출**: ambient 자리 파티클(포털 소용돌이·불씨·분수 물보라·마법 반짝임·연기), 청크가 로드돼 있고 근처에 사람 있을 때만.
- **`/미궁 마을`** (`/lab village`, `/lab 마을`): 광장 스폰으로 텔레포트 (미궁 안이면 거절: "먼저 /미궁 귀환"), `village.teleport_command`.
  메인 메뉴 51번 칸 "마을" 버튼도 같은 동작. 마을 메타데이터가 없으면 "이 월드에는 마을이 없습니다 (서버팩의 world 폴더를 쓰세요)".
- 초기 설정 메뉴(SetupMenu)의 입구 방식 선택은 마을이 있으면 숨기고 "입구: 마을의 미궁의 아가리" 정보만 보여 준다.

### 4.4 그 밖의 관리자 명령
- `village info` — 청사진 요약, 메타데이터 요약, 적용 UID, NPC 상태.
- `village apply` — 이 월드에 다시 적용 (NPC·입구·적용 기록). `village cancel` — 진행 중인 마을 작업 취소.
- `village dump` — 마을 상자 + 16칸 여유 모든 비공기 블록 → `plugins/Labyrinth/village/dump.txt` (`x y z|blockdata`) → render.py --dump.
- `village survey [반경]` — 시드 고르기용: 스폰 주변 후보 중심들(8칸 간격, 기본 반경 160) × 회전 4방향마다 §0 규칙(조각 slack 조정 포함)으로
  실제 깎기·메우기 총량, 탈락 이유(물·구조물·동굴·한도 초과), 원목 수, 바이옴을 계산해 점수 좋은 5곳(자리+방향)을 출력
  (ChunkSnapshot 으로 비동기 계산, 메인 스레드 막지 않기). `build` 는 survey 와 같은 계획기로 그 자리·방향의 계획을 다시 세워 짓는다.
  빠른 계산(고정 칸 변화량)으로 거른 뒤 상위 몇십 곳만 목표 높이장까지 계산해 실제 깎기+메우기+동굴 메움으로 순위, 서로 16칸 안의 자리는 하나만.
  결과는 채팅 + 서버 로그 줄 `[마을 survey] <순위> <x> <z> <방향> <깎기> <메우기> <동굴메움> <원목> <바이옴> <H0>` + `plugins/Labyrinth/village/survey.txt`
  (조립 스크립트가 읽기 쉽게). 탈락 이유별 (자리×방향) 수도 출력.
- `village pregen <반경>` — 중심 주변 청크를 비동기로 미리 생성(동시 요청 수 제한, 진행률), 배포 월드 첫 접속 렉 줄이기.
- `village selftest` — 메타데이터를 다시 읽어 모든 조각 칸이 청사진대로인지 검사(mismatched 수), §0 짓고 나서 검사 전부, NPC 5명이 자리에 있는지,
  interact·spawn·entrance 유효성 → 결과 한 줄 `[마을 자가 진단] 결과: 예외 0 · checked=… mismatched=0 · overlaps=0 · floating=0 · tree_remnants=0 · blocked_doors=0 · npcs=5/5 · …`.
  실제 줄 (서버 로그에도 남음): `[마을 자가 진단] 결과: 예외 0 · checked=N mismatched=0 · overlaps=0 · floating=0 · tree_remnants=0 ·
  blocked_doors=0 · npcs=5/5 · interior=0 · path_steps=0 · interact=a/a · spawn=ok · entrance=ok · rot_mismatch=0`.
  - mismatched = 청사진 블록 상태가 다르거나 '.' 칸이 공기가 아님(interior 는 그중 '.' 칸 수). overlaps = `Planner.overlaps`(짓기 전 검사와 같은 함수).
  - floating = 바뀐 칸(발자국 밖)의 맨 윗블록이 비었거나 그 아래 두 칸이 빔, 또는 위 12칸 안에 지형 블록이 떠 있음.
  - tree_remnants = 손댄 열(고정 칸 둘레 2칸 + 바뀐 칸 — 짓기와 같은 규칙)에 남은 자연 원목(보호 상자 밖) + 반경 R+B+8 안 원목에서 잎을 따라 6칸 안에 닿지 않는 자연 잎.
  - blocked_doors = 정문 앞 칸 땅높이와 조각 바닥 P 차가 1 넘음, 또는 그 위 두 칸·anchor 위 두 칸이 막힘. path_steps = 길 칸 이웃 걸음 높이 차 > 1 (반블록 0.5).
  - rot_mismatch = 팔레트마다 `BlockData#rotate` 결과와 Java 문자열 회전(`Rot.rotateState`, 단위 테스트 대상) 결과가 다른 수 (정보용).

### 4.5 config.yml
```yaml
village:
  teleport_command: true     # /미궁 마을 로 광장 텔레포트
  block_mob_spawns: true     # 마을 안 적대 몹 자연 스폰 막기
  blocks_per_tick: 4000      # village build 속도 (개발용)
wild:                        # (0.3.5.1) 야생 막기 — ARCHITECTURE §6.10
  border: true
  border_margin: 30
  spawns: all
```

### 4.6 배포 (조립 담당)
- `tools/build_world.sh <시드> [<x> <z> <방향>]`: /opt/testserver 를 임시 폴더(`WORK`, 기본 /opt/worldbuild/build)로 복사(world·logs·플러그인
  데이터 없이 — 테스트 서버 world 는 건드리지 않음), server.properties level-seed=<시드>, 플러그인 최신 jar(리소스팩 HTTP 끔),
  명령: `village build <x> <z> <방향>` → `village pregen 192` → `village selftest` → `village info` → `village dump` → stop.
  짓기가 거절되면 바로 끄고 실패. 자가 진단 줄이 `예외 0 · mismatched=0 · overlaps=0 · floating=0 · tree_remnants=0 · blocked_doors=0` 이
  아니면 실패(`ALLOW_DIRTY=1` 로 무시). 그 world 폴더에서 `session.lock`·`uid.dat`·`dimensions/minecraft/labyrinth_world`·플레이어 데이터를
  빼고 `dist/world.zip`(안의 경로는 `world/...`) + 시드 `dist/world.seed`. 자리·방향은 `village survey` 결과(시드 고르기)에서 고른다.
  `dist/` 는 git 에 올리지 않는다 — world.zip 은 이 스크립트로 다시 만든다(같은 시드·자리·플러그인이면 같은 마을).
  - 26.x 메모 (Java 담당 확인): world 폴더에 `uid.dat` 가 없다 — UID 는 `world/dimensions/minecraft/overworld/data/paper/metadata.dat` 에 있다.
    §4.3 적용 열쇠가 UID + `build_id` 라서 UID 를 안 지워도 새로 지은 마을이면 적용된다(지워도 무방). 플레이어 데이터는 `world/players/` 아래.
    미궁 공허 월드도 `world/dimensions/minecraft/labyrinth_world` 로 world 폴더 안에 생기므로 zip 에서 빼는 게 좋다(시작할 때 다시 만듦).
- release.sh: world.zip 을 풀어 `Labyrinth-Server/world/` 로 넣는다(없으면 실패, 마을 메타데이터가 없으면 실패). release/server.properties 에
  `level-seed=<시드>`(월드 밖으로 나가도 같은 지형이 이어지게) — `dist/world.seed` 와 다르면 실패.
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
  - 지금 layout (`tools/village/layout.py`): radius 33, 계획기 R 37 (조각 상자 모서리 + slack + 1) + B 16 = 조사·물 검사 반경 53.
    R 은 가장 먼 조각 상자 모서리로 정해지므로 바깥 모퉁이 장식은 slack 1~2 로 둔다 (R 이 커지면 물 없는 자리를 찾기 어려워짐).
  - 표지판 글에는 동서남북을 쓰지 않는다 (마을 회전은 시드·지형이 정함) — '광장 왼편/오른편', '분수 건너 계단 위'.

### 5.1 배포 월드 (조립 담당 기록)
- 시드 **24680**, `village build -136 16 west` (sunflower_plains, H0 64, 깎기 829 · 메우기 627 · 원목 10, 월드 스폰에서 120칸).
  마을 북쪽 바로 밖(R+B 밖)에 강, 그 너머 숲. 마을 회전 COUNTERCLOCKWISE_90 — 게이트가 서쪽, 광장 스폰은 게이트를 바라봄.
- 다시 만들기: `(cd plugin && ./gradlew build) && tools/build_world.sh 24680 -136 16 west && ./release.sh`.
  청사진·계획기를 바꾸면 마을 모양이 달라질 수 있으니 자가 진단 줄과 덤프 렌더(`render.py --dump dist/village-dump.txt --top`)를 다시 본다.

## 6. 검증 기준 (끝났다고 하려면)
1. `build_all.py` — 모든 조각 JSON 생성, 팔레트 문자열 형식, 블록 이름·속성이 26.x 에 있음, 금지 블록 없음, 발자국 겹침 없음(§3 규칙),
   길이 붙지 않은 조각과 1칸 여유, 정문 앞 칸 막힘 없음, 반경 안, 마커 좌표가 크기 안, spawn·entrance 각 1개, npc 마커 id 가
   npcs.yml 의 overworld NPC, 연결 블록 상태 명시, 받침 없는 매단 등불·벽 표지판 없음. 경고 0 (마을 NPC 5명이 다 있어야 경고 0).
2. Java 단위 테스트: 청사진 파싱, 회전 좌표 공식 4방향(좌표 + facing 블록), 마커 회전, 목표 높이장(가짜 높이맵: 단 고정, 이웃 차 ≤1, 띠에서 원래 높이로 수렴).
3. 테스트 서버: `village build` 후 `village selftest` 예외 0 · mismatched=0 · npcs=5/5, 미궁 `labadmin selftest` 예외 0.
4. 배포 zip 을 빈 폴더에 풀어 켰을 때 마을이 있고 스폰이 광장, NPC 5명, 게이트 우클릭 → 입구 메뉴.
5. 렌더: 평지 위 마을 전체 PNG + 실제 월드 덤프 PNG — 사람이 봐서 "화려한 판타지 마을"로 보이고 지형이 자연스러울 것.


## 7. 광산 마을 (구역, 0.3.6.1 — CONTRACT §2.13 · `tools/data/036/district.json`)

마을과 같은 조각 형식·계획기·짓는 칸 일(PlanWriter)을 쓰지만, 원이 아니라 **마스크**로 계획하고 **기존 월드에 jar 교체만으로** 지을 수 있다.

- 배치: `tools/village/district_mine.py` (배포 월드 좌표로 적음) → build_all 이 마을 좌표로 바꿔 `districts/mine.json`. 조각 `pieces_mine.py`
  (mine_headframe 13×24×13 · smelter 13×18×12 · miners_lodge 11×12×9 · ore_yard · lamp_post_copper · signpost_mine + 마을 장식 조각).
  자리: east (큰길 끝 (-104,16) 에 붙음) → south_east (z +42, 큰길에서 남쪽으로 길) → 관리자 `here [방향]`. 승강장 slack 0, 제련소·숙소 1, 참나무 2.
- 마스크: 조각·길 상자 + R(4) = 다듬는 칸, + B(6) = 섞는 띠. **얼린 칸**(`FrozenCells`) = 마을 보호 상자 · 마을 길 · 마을이 다듬은 칸 —
  높이·지형을 바꾸지 않고 조각·정문 앞 칸이 올 수 없다. 구역 길은 마을 길·보호 상자 칸을 건너뛰고, 다듬은 칸 위는 겉 블록만 깐다.
  이음(junction): 구역 길 칸과 이웃한 마을 길 칸 높이 차 ≤ 1.
- 사람 손 검사: ① 계획기 — 영역 안 비자연 블록·지표 물 → 탈락. ② 지문(`mine.fp`, 배포 월드 두 판이 열 단위로 같아 지문 하나에 build_id 둘) —
  열마다 땅 높이 · 땅속 10칸~위 30칸 정규화 해시 · 원목 자리. 높이 차 > 2 · 땅속 새 빈칸·물 · 새 원목 → 막음. 잔디↔흙·꽃·풀·눈 층·잎·베어 낸 나무는 허용.
  ③ 엔티티 — 갑옷 거치대·액자·그림·수레·보트·끈 매듭·주민·이름표/길들인/묶인 동물 → 막음 (그냥 동물은 조각 밖으로 옮김).
  배포 월드가 아니면(마을 build_id 의 지문이 없음) 저절로 짓지 않는다.
- 순서 (`DistrictJob`): 자리 조사 → 통과한 첫 자리에서 나무 계산 → **바꿀 수 있는 모든 칸의 원래 블록을 백업 파일에 먼저** → 기록 `state: building`
  (보호 켬 · 그 자리 사람은 광장으로) → 나무·지형·조각·길·표지판 → 바뀐 칸만 백업(DIFF) → `state: built` + NPC 2명 (광부 브론 · 제련공 이그나).
  모두 막히면 블록 0칸 · `plugins/Labyrinth/village/district-mine-blocked.txt` · 관리자 하루 한 번 안내. building 으로 꺼졌으면 다음 시작 때
  백업으로 되돌린 뒤 처음부터. `remove` = 지금 블록이 우리가 놓은 것인 칸만 되돌리고 `state: removed` (저절로 다시 짓지 않음).
- 배포 월드 동쪽에 지으면: 바꾼 블록 약 4,300 · 백업 약 42,000칸 · 블록 쓰기 1~2초 (틱당 3,000). 마을 자가 진단 그대로 mismatched=0.
- 자가 진단 `[광산 마을 자가 진단] 결과: 예외 0 · checked=N mismatched=0 · overlaps=0 · floating=0 · tree_remnants=0 · blocked_doors=0 ·
  path_steps=0 · junction=ok · npcs=2/2 · interact=a/a` (`labadmin village selftest` 가 마을 줄 다음에 이어서, 또는 `village district selftest mine`).
- 새 world.zip: `tools/build_world.sh --base dist/world.zip east` (예전 배포 월드를 풀어 마을은 그대로, 광산 마을만 지음 → 두 자가 진단 → zip).

- 0.3.6.1 리뷰 반영 (안전):
  · 관리자가 `/worldborder` 로 정한 경계(우리 경계가 아님)면 보호 상자·승강장 앞·우클릭 칸이 다 경계 안인 자리만 짓는다 (막힘 이유 `border`).
    `/미궁 광산`·광산 '마을로' 는 mine_exit 가 경계 밖이면 예전처럼 광산 1층·마을 광장으로.
  · 다 지은 뒤·되돌린 뒤 `world.save(true)` (청크 저장이 끝날 때까지) → 그다음에 기록(built·removed)을 쓰고 백업을 지운다 — 기록이 블록보다 앞서지 않게.
  · 나무 치우기: 검사한 영역에서 원목이 6칸 넘게 이어지면 막음, 그 안의 영역 밖 열도 지문·비자연 검사, 먼 잎은 남김.
  · 큰길과 만나는 얼린 칸: 지문과 다르고 y~y+2 에 비자연 블록이면 막음 · 길 블록은 자연 땅일 때만 깔고 위는 풀만 치움.
  · 자리 검사 통과 ~ 블록 쓰기 사이: 잠깐 보호(놓기·부수기 막기, 기록 없이) + 백업 읽을 때 스냅샷과 비교해 사람 손 변화면 다시 살펴봄(두 번까지).
  · 짓다가 취소·오류 → 곧바로 백업으로 되돌림 (서버 끄는 중이면 다음 시작 때). 짓는 중 밀어내기는 실제로 쓰거나 되돌리는 동안만.
  · 백업이 없거나 깨진 building 기록 → 막힘 이유 `backup` · `village district remove mine force` (블록 그대로, 기록만 removed).
  · 지은 구역 블록 안에 끼어 접속한 사람 → 승강장 앞(경계 안이면) 또는 광장. remove 는 지금 블록이 놓은 것과 **같은 종류**면 되돌림(열고 닫은 문·덧문, 흙이 된 잔디).
- 0.3.6.1 리뷰 반영 (놀이): 마당 길 `follow: 0` (양 끝 사이 곧게 — 숙소 앞 도랑 없음) + 숙소 문 앞 길(반블록 계단) · 자가 진단 `door_paths`
  (정문 앞 칸에서 한 걸음 안에 길) · 가로등 2개 더 (마당 서쪽 끝·하치장 골목) · south_east 자리 갈림길 길잡이 `signpost_mine_turn` + 남쪽 길 가로등 3개
  (east 는 drop) · mine_exit 는 승강기 문 쪽을 봄 · 광산 관리소 메뉴 가운데 줄 = 층 1~6 + 승강기 (승강장 12칸 안이면 바로 탐).
