# Labyrinth — 미궁 라비린스 서버팩 설계서 (기술 계약)

이 문서는 플러그인(Java), 콘텐츠(YAML), 리소스팩(생성기) 작업자가 **같은 약속**으로 일하기 위한
단일 기준이다. 여기 적힌 ID 규칙·파일 위치·스키마를 바꾸려면 이 문서를 먼저 고친다.

## 0. 목표와 원칙

- Paper **26.3** (Java 25) 전용 **플러그인 하나 + 리소스팩 하나**. 모드 없음. 클라이언트는 바닐라 26.3.
- 적정 인원 3~10명. 서버 사양이 낮아도 돌아가게 (instance 당 엔티티·블록 작업 최소화).
- **모든 NPC·몹·보스·무기·방어구·UI는 자체 제작.** 바닐라/타 플러그인/타 리소스팩의 텍스처·모델·코드를
  복사하거나 변형해서 쓰지 않는다. `/opt/mc-ref/assets` 의 바닐라 파일은 **형식 참고용**이며 팩에 넣지 않는다.
  외부 라이브러리 의존 없음(Paper API만). 판매할 것이므로 전부 우리 저작물이어야 한다.
- **기존 지형을 건드리지 않는다.** 미궁은 전용 공허 월드(`labyrinth_world`)에서만 생성·삭제한다.
  오버월드 입구는 관리자가 고른 위치에 지형에 맞춰(경사·바닥 높이 맞춤, 나무/물 위 금지) 작게 설치하거나,
  아예 NPC 만 세운다(블록 변경 0). 미궁 밖 월드의 블록은 어떤 코드도 바꾸지 않는다.
- 게임 텍스트는 **한국어**. MiniMessage(Adventure) 사용. 레거시 `§` 코드 금지.
- 콘텐츠는 **데이터 주도**: 아이템·몹·층·레시피·칭호 수치는 YAML. 패턴/기믹 로직만 코드.
  (구매자가 YAML 로 밸런스를 바꿀 수 있어야 판매 가치가 있다.)

## 1. 디렉터리

```
labyrinth/
  ARCHITECTURE.md        ← 이 문서
  GDD.md                 ← 게임 디자인 (콘텐츠 작업자가 작성)
  plugin/                ← Gradle 프로젝트 (./gradlew build → build/libs/labyrinth-*.jar)
    src/main/java/kr/labyrinth/...
    src/main/resources/plugin.yml, config.yml
    src/main/resources/content/*.yml   ← 콘텐츠 단일 원본 (리소스팩 생성기도 이걸 읽음)
    src/test/java/...                  ← 순수 로직 단위테스트 (JUnit 5)
  resourcepack/
    generate.py          ← python3 generate.py → dist/labyrinth-pack.zip (+ sha1)
    requirements.txt     ← Pillow, PyYAML 만
    src/...              ← 생성기 모듈
    dist/                ← 결과물 (git 에는 zip 만 커밋하지 않음; 빌드 산출물)
```

빌드: `cd labyrinth/plugin && ./gradlew build` (JDK 25 필요; 이 컨테이너는 `/opt/jdk25`, `~/.gradle/gradle.properties` 에 설정됨).
리소스팩: `cd labyrinth/resourcepack && python3 generate.py`.

## 2. 네임스페이스와 ID 규칙 (플러그인 ↔ 리소스팩 계약)

- 리소스 네임스페이스: `labyrinth`. 플러그인 PDC 키 네임스페이스: 플러그인 이름(`labyrinth`).
- 모든 콘텐츠 ID 는 `snake_case` ASCII. 표시 이름은 YAML 의 `name` (한국어).
- **아이템**: 아이템 `id` → 아이템 모델 `labyrinth:<id>`
  - `assets/labyrinth/items/<id>.json` (item model definition) → `assets/labyrinth/models/item/<id>.json`
  - 텍스처 `assets/labyrinth/textures/item/<id>.png` (애니메이션이면 같은 이름 `.png.mcmeta`)
  - **장비는 3D**: 무기·방패·투구·장신구는 평면 아이콘이 아니라 **직육면체 요소(elements)로 만든 3D 모델**
    (손에 든 모습/인벤토리/땅/액자/머리 display 변환 모두 지정). 텍스처는 그 모델의 UV 아틀라스.
    전설·신화 무기는 아틀라스 자체를 프레임 애니메이션(.mcmeta)해서 룬·불꽃·번개가 흐르게 한다.
    재료·소모품만 2D 아이콘 허용.
  - **투구는 3D 모델을 머리에 씌운다**: 투구는 `EQUIPPABLE(slot=head)` 에 `assetId` 를 **넣지 않는다**
    (그래야 아이템 모델이 머리 display 로 렌더링됨). 상의·하의·신발만 장비 에셋 레이어 사용.
  - 플러그인은 `DataComponentTypes.ITEM_MODEL = Key.key("labyrinth", id)` 로 지정. CustomModelData 안 씀.
  - 활(`type: bow`)은 당김 단계 모델 `<id>_pulling_0..2` 도 생성 (바닐라 bow 정의와 같은 구조, 자체 텍스처).
- **방어구 세트**: YAML `armor_set` 값 `<set>` → 장비 에셋 `labyrinth:<set>`
  - `assets/labyrinth/equipment/<set>.json`, 텍스처 `assets/labyrinth/textures/entity/equipment/humanoid/<set>.png`,
    `.../humanoid_leggings/<set>.png` (64x32 바닐라 레이아웃)
  - 플러그인은 `EQUIPPABLE` 컴포넌트의 `assetId = labyrinth:<set>`.
- **몹/보스 모델**: 몹 `id` 의 각 파트 `<part>` → 아이템 모델 `labyrinth:mob/<id>/<part>`
  - `assets/labyrinth/items/mob/<id>/<part>.json`, 모델 `assets/labyrinth/models/mob/<id>/<part>.json`
  - 텍스처 `assets/labyrinth/textures/mob/<id>.png` (한 몹 = 한 장 아틀라스, UV 로 파트 나눔)
  - 파트 목록·피벗은 `mobs.yml`/`bosses.yml` 의 `model.parts` 가 원본 (아래 스키마).
  - **생성 결과 계약(pack-models 단계, `resourcepack/src/mobs.py`)** — Java `ModelRig` 은 이것만 믿으면 된다:
    - 파트마다 ItemDisplay 1개, `setItemDisplayTransform(ItemDisplayTransform.FIXED)`, 아이템 = 아무 아이템 + `ITEM_MODEL = labyrinth:mob/<id>/<part>`.
    - 엔티티 위치 = 몹 위치 + `rotY(몹 yaw)(pivot) × scale` (pivot 은 몹 로컬: +Z = 몹이 보는 방향, +X = 몹의 왼쪽, 블록 단위),
      ItemDisplay 의 yaw(또는 Transformation 회전) = 몹 yaw. `Transformation.scale` = 몹 `scale` (모델이 이미 1/s 복원을 품고 있으므로
      **Java 는 추가 배율 없이** YAML `size` 가 그대로 화면 크기). translation = 0 (회전 중심 = pivot = 모델 (8,8,8)).
    - 모델 **−Z = 몹의 앞**(얼굴·눈·발톱·무기 끝), 모델 −X = 몹의 왼쪽. 팔(`arm`/`tentacle_cluster` + `arm_left|arm_right`)·다리
      (`leg_pair` + `legs_walk`)는 pivot 에서 **아래로 매달린** 모양, `tail` 은 pivot 에서 뒤(몹 −Z)로 뻗거나(길이>높이) 아래로 매달린다.
    - **손에 쥔 파트**(팔과 pivot·anim 이 같은 blade/claw/slab/lantern/book…)는 생성기가 그 팔의 손 위치(pivot − (0, 팔 길이, 0))에
      붙여 만들었다 → Java 는 그 파트에 **팔과 똑같은 Transformation 회전**을 주면 손에 붙어 함께 휘두른다. blade 는 손에서 앞(−Z)으로,
      slab(방패)은 바깥쪽(±X)을 향한다.
    - 아틀라스 크기는 생성기가 자동으로 정한다(정사각형 2의 거듭제곱; YAML `texture_size` 는 참고값). 보스 아틀라스는 8프레임,
      발광 몹(emissive_core·heartbeat_glow·spore_glow·sculk_veins·molten_cracks·electric_veins)은 4프레임 `.mcmeta` 애니메이션 —
      발광 부위가 맥동한다. Java 는 신경 쓸 것 없음.
    - 눈·핵·수정 같은 발광 요소는 모델 요소의 `light_emission`(12~15)으로 이미 밝게 그려진다 → `Display#setBrightness` 불필요
      (어두운 미궁에서 몸 전체를 밝히고 싶을 때만 Brightness(블록 빛 ≥ 10) 권장).
    - 모든 파트 모델은 `display.fixed`(= `display.head`) rotation 0 / translation 0 / scale 1/s(≥1, ≤4), `gui`·`ground` 는 미리보기용.
- **3D 모델 공통 좌표 규칙 (몹 파트·fx·무기스킬 이펙트 — 플러그인과 생성기가 이것만 믿는다)**:
  모델 좌표 16 = 1블록. 파트의 **피벗(회전 중심)은 모델 좌표 (8, 8, 8)**. 요소는 -16~32 범위 안.
  모델의 `display.fixed` = rotation [0,0,0], translation [0,0,0], scale [1,1,1] (그 외 컨텍스트는 자유).
  플러그인은 `ItemDisplay` + `ItemDisplayTransform.FIXED`, 엔티티 위치 = 파트 피벗의 월드 좌표,
  `Transformation.scale` = 몹 `scale`(파트 크기 배율), 회전은 Transformation 의 left rotation 으로.
  (만약 26.3 클라이언트에서 FIXED 가 180° 뒤집혀 보이면 생성기가 모델 쪽에서 보정하고 여기 적는다.)
  **확인됨(26.3 클라이언트 `DisplayRenderer$ItemDisplayRenderer`)**: ItemDisplay 는 아이템 모델을 Y축 180° 돌려 그린다 →
  Transformation 이 항등일 때 **모델 −Z(north) 면이 엔티티 앞(+Z, yaw 방향)**, 모델 +X 가 엔티티 −X 쪽을 본다.
  그래서 생성기 규칙: 몹 파트·fx 의 "앞"(얼굴, 검기 볼록면, 투사체 머리)은 **모델 −Z** 쪽으로 만든다(무기스킬 fx 는 이미 그렇게 생성).
- **아틀라스 규칙(26.3)**: 아이템 모델이 쓰는 텍스처는 items 아틀라스에 있어야 한다. 바닐라 items 아틀라스는 `textures/item/` 만
  포함하므로 생성기가 `assets/minecraft/atlases/items.json` 에 `fx/`·`mob/` 디렉터리 소스를 추가한다(팩끼리 sources 병합).
  → fx 텍스처 `assets/labyrinth/textures/fx/<name>.png`(모델 `models/fx/<name>.json`), 몹 텍스처 `textures/mob/<id>.png` 가 그대로 동작.
  다른 폴더를 새로 쓰려면 같은 파일에 소스를 추가할 것.
- **NPC 스킨**: `npcs.yml` 의 `skin: <id>` → `assets/labyrinth/textures/entity/npc/<id>.png` (64x64 플레이어 스킨 레이아웃, 두 번째
  레이어 포함, **classic(4px 팔)**). 플러그인은 `Mannequin` 엔티티 + `ResolvableProfile` 의 SkinPatch 사용:
  `mannequin.setProfile(ResolvableProfile.resolvableProfile().skinPatch(b -> b.body(Key.key("labyrinth", "entity/npc/" + skin))
  .model(PlayerTextures.SkinModel.CLASSIC)).build())`. **asset id 형식 확인됨(26.3 클라이언트 `ClientAsset$ResourceTexture`)**:
  키 `ns:path` → 리소스 `assets/<ns>/textures/<path>.png` (= `"textures/" + path + ".png"`), 아틀라스 아님(단독 텍스처) →
  `labyrinth:entity/npc/<skin>` 이 정답(앞에 `textures/`·뒤에 `.png` 붙이지 말 것). 겉옷 레이어가 보이도록 `setSkinParts` 는 전부 켠다.
- **이펙트 모델**(아우라 링, 장판 경고, 투사체 등): `labyrinth:fx/<name>` → `assets/labyrinth/items/fx/<name>.json`.
  목록은 `content/fx.yml`.
- **표시 규칙(몹 파트·이펙트 공통)**: 플러그인은 `ItemDisplay` + `ItemDisplayTransform.FIXED` 로 띄운다. 생성기는 모델 좌표 한계
  (−16~32)를 넘는 큰 모델을 비율 s 로 줄여 만들고 `display.fixed.scale = 1/s`(rotation/translation 0)로 원래 크기를 복원한다.
  몹 파트는 **pivot 이 모델 중심(8,8,8)** 에 오게 만든다 → 플러그인의 Transformation 회전 중심 = pivot. YAML `size`(px, 16=1블록)가
  곧 화면 크기. 상세(파트 배치 기준·손에 쥐기 규칙): GDD.md §14.6.
- **fx 앵커와 크기(pack-models 단계, `src/fx_extra.py`)**: fx 모델은 전부 pivot (8,8,8) 중심. 예외(시작점 = pivot, 모델 −Z = 디스플레이가
  보는 방향으로 뻗음): `telegraph_line`·`telegraph_arrow`·`telegraph_cone`·`clock_hand`. `pendulum` 은 pivot = 막대 위 끝(Z축 회전으로 흔들기).
  바닥형(`flat: true`)은 두께 0.1px 판의 **윗면만** 텍스처 → 바닥 블록 윗면 + 0.02 블록 높이에 띄울 것. `size` 의 w/d(px) 가 scale 1 일 때 크기:
  - `telegraph_circle`/`telegraph_safe`/`telegraph_mechanic`/`telegraph_ring`: 지름 = w/16 블록 → 반경 r 이면 X·Z scale = 2r ÷ (w/16)
    (기본 32px → scale = r). `telegraph_ring` 안쪽 구멍 = 바깥 반경의 46% 고정.
  - `telegraph_line`/`telegraph_arrow`: X scale = 폭 ÷ (w/16), Z scale = 길이 ÷ (d/16), yaw = 방향. 시작점 = 디스플레이 위치.
  - `telegraph_cone`: 꼭짓점 = 디스플레이 위치, 반경 = d/16 블록, 90° 부채꼴 → Z scale = 길이 ÷ (d/16), X scale = 같은 값 × tan(각도/2).
  - `telegraph_tile`: 한 변 = w/16 블록. `clock_hand`: 길이 = d/16 블록, yaw 를 돌려 시곗바늘처럼 회전.
  - 아우라 `*_ring`: 지름 w/16 블록 링(애니메이션 텍스처가 모티프를 흘림), `ring_scale`·`ring_spin` 은 Java 가 Transformation 으로.
  - 경고 장판은 전부 프레임 애니메이션(테두리 맥동 + 중심→바깥 스윕 = 차오르는 느낌). 안쪽 채움은 반투명(α≈90) 텍스처.
- **UI 글리프**: `content/glyphs.yml` 이 원본. 폰트 `labyrinth:ui` (`assets/labyrinth/font/ui.json`).
  각 글리프 = 사설 영역 코드포인트(U+E000~) + PNG + ascent + height. 음수/양수 공백 글리프로 위치 이동.
  **공백 문자 규칙**: `spaces` 의 값 v(px, −1024~255)는 같은 폰트의 `space` 프로바이더에서 문자 **U+F800 + v** 로 매핑한다
  (예: −8 → U+F7F8). 플러그인 `ui.Glyphs.space(px)` 가 이 규칙으로 조합한다. glyphs.yml 이 없어도 플러그인은 동작(글리프 생략).
  플러그인은 `Component.text(char).font(Key.key("labyrinth","ui"))` 로 사용. 하드코딩 금지, glyphs.yml 에서 읽기.
  **생성 결과 계약(pack-ui 단계, `resourcepack/src/ui.py`)** — 클라이언트 바이트코드로 확인한 수치:
  - 글리프 윗변 y = 글줄 y + 7 − ascent (PNG 높이 = `height` → 배율 1). 글자 폭(advance) = 가장 오른쪽 불투명 열 + 2
    (glyphs.yml `advance` 에 적혀 있고 생성기가 PNG 와 대조, Java 는 `Glyphs.advance(id)`). ascent ≤ height 필수
    (줄 위로 띄우는 글리프는 생성기가 PNG 아래에 투명 줄을 덧대 height 를 맞춤).
  - **메뉴 배경**: 상자 창 = 176 × (114 + 줄수·18), 제목 글줄 = 창 (8, 6), 슬롯 아이템 = (8 + 18·열, 18 + 18·행), 플레이어
    인벤토리 y = 줄수·18 + 31, 핫바 = 줄수·18 + 89, "인벤토리" 글자 = (8, 높이 − 94). 배경 글리프 `gui_<id>` 는 ascent 13·
    advance 177 → 제목 = `Glyphs.menuTitle("gui_<id>", 176, 제목)` (= space(−8) + 배경 + space(−169) + 제목). 배경이 인벤토리
    부분까지 덮고(같은 디자인), 바닐라 인벤토리 글자 자리는 밝은 명판. 제목 글자색은 `menus.<id>.title_color`(밝은 양피지색).
    메뉴별 버튼 자리(소켓이 그려진 칸)는 glyphs.yml `menus.<id>.slots` 가 원본 — 채움 유리판을 깔지 말 것(배경을 가림).
    배경 14종: main(3줄), stats, class, party, setup(첫 서버 설정·난이도), entrance(층 선택), blacksmith, titles, accessories(3줄),
    merchant, pvp(도전·대기열·순위표), confirm(3줄), generic_6, generic_3.
  - **HUD 액션바**(글줄 y = 화면높이 − 72, 가운데 정렬): 핫바 왼쪽 끝 기준 x 0..181 로 배치하고 전체 advance 를 182 로 맞춘다
    (요소마다 space(x − 펜) + 글리프, 끝에 space(182 − 펜)). 위치·접두어는 glyphs.yml `hud:` 블록. HP 바(x0)·레벨 배지(x82)·
    MP 바(x100) = H−63..H−55, 경험치 줄 H−52, 상태 아이콘·골드 줄 H−76. 바는 21단계(`hud_hp_00..20` = round(비율×20)).
    숫자 `hud_num_*`/`gold_num_*` 고정폭 7(점·쌍점 4), 흰 바탕이라 color 로 물들일 수 있음. **액션바·보스바 글리프는
    `shadowColor(ShadowColor.none())`(MiniMessage `<!shadow>`) 필수** — 아니면 글자 그림자가 바 밑에 겹쳐 보인다.
  - 보스바 이름 = `boss_ornament_left` + space(2) + 이름 + space(2) + `boss_ornament_right`(대칭 → 자동 가운데).
    `boss_frame` 은 이름 전체로 쓰면 182×5 막대를 정확히 감싸는 금테(가운데 창 투명). 파티 미니 HP `party_hp_00..10`·직업
    아이콘 `party_class_<id>`(사이드바/탭 줄), 피해 숫자 `dmg_*`/`crit_*`/`dmg_icon_*`(TextDisplay), 상태 `status_<효과>`.
- 사운드: 1차 버전은 바닐라 사운드 이벤트를 pitch/volume 조합으로 사용(사운드 파일 미포함). 사운드 키는 YAML 에 둔다.

## 3. 리소스팩 배포

- 플러그인 `pack` 모듈이 내장 HTTP 서버(`com.sun.net.httpserver`, 기본 포트 `config.yml: pack.port`)로
  `plugins/Labyrinth/pack/labyrinth-pack.zip` 을 서빙하고, 접속 시 `Player#sendResourcePacks` (SHA-1 포함, 필수/거절 시 안내).
  외부 URL 을 쓰고 싶은 사람은 `pack.url` 로 덮어쓰기.
- pack.mcmeta: 26.3 리소스팩 포맷은 **97.1** (`version.json` 의 `pack_version.resource_major/minor`).
  26.x 형식(확인됨): `{"pack": {"description": [...컴포넌트], "min_format": [97, 1], "max_format": 97}}` —
  정수 `max_format` 은 "그 major 의 모든 minor"(TOP_CODEC = minor 최대값)라서 26.3.x 패치에도 경고 없이 맞는다. `pack_format` 은 넣지 않는다.
- 생성기 산출물: `resourcepack/dist/labyrinth-pack.zip`(결정적 zip: 정렬·고정 시각) + `labyrinth-pack.sha1`, 사람용 미리보기
  `preview_items.png`·`preview_anim.gif`·`preview_fx.png`·`preview_helmets_worn.png`·`preview_armor.png`·
  `preview_mobs.png`(몹·보스를 YAML pivot 에 조립한 정면 3/4 렌더)·`preview_mob_atlases.png`·`preview_npcs.png`·
  `preview_ui.png`(GUI 배경 14종 + 실제 슬롯 격자, HUD 액션바 조합 모의, 글리프 전체).
  생성기는 `generate.py` 의 `BUILDERS` 레지스트리(공유 `Ctx` → `ctx.add(path, bytes)`)로 확장한다: 몹·UI 글리프·NPC 스킨·나머지 fx 스타일
  단계는 자기 모듈을 `src/` 에 두고 BUILDERS 에 추가. 3D 모델 엔진 `src/model.py`(Model/El/bake/UV 아틀라스/display 맞춤),
  재질 셰이더 `src/materials.py`, 애니메이션 `src/effects.py`, 미리보기 렌더러 `src/render.py` 를 재사용할 것.

## 4. 플러그인 구조 (`kr.labyrinth`)

### 4.0 소유권 지도 (병렬 작업 규칙 — 반드시 지킬 것)

| 패키지 | 소유(작업 단계) | 진입점 (여기서 `services.setXxx(...)`) | 계약(인터페이스) · 기본 구현 |
|---|---|---|---|
| 루트(`LabyrinthPlugin`, `Services`), `core/`, `content/`, `data/`, `stats/`, `combat/`, `pack/`, `command/`, `event/`, `ui/Menu·Button·ClickContext·MenuListener·Glyphs` | **plugin-core** | — | — |
| `items/` (+ `loot`·`crafting`·`weaponskills` 하위 패키지 자유) | **items** | `items/ItemsModule` | `ItemService`(→`BasicItemService`), `LootService`, `CraftingService`, `WeaponSkillService` (→`Noop*`) |
| `classes/` | **classes** | `classes/ClassesModule` | `ClassService`(→`BasicClassService`: 직업 저장+마나), `StatusEffectService`(→`Noop`) |
| `mobs/` (몹 + NPC) | **mobs+npc** | `mobs/MobsModule` | `MobService`, `CustomMob`, `NpcService` (→`Noop*`) |
| `dungeon/`, `party/` | **dungeon+party** | `dungeon/DungeonModule` | `DungeonService`(→`NoopDungeonService`), `InstanceContext`(core 가 만든 구체 클래스, 필드 추가는 dungeon 담당), `PartyService`·`Party`(→`SoloPartyService`) |
| `bosses/` | **bosses** (이후 단계) | `bosses/BossesModule` | `BossService`, `BossHandle extends CustomMob` (→`NoopBossService`) |
| `titles/` | **ui+titles** | `titles/TitlesModule` | `TitleService`(→`BasicTitleService`) |
| `ui/` (위 프레임워크 제외: `menus/*`, HUD 구현) | **ui+titles** | `ui/UiModule` | `HudService`(→`BasicHudService`), `MenuService`(→`ChatMenuService`: 채팅 클릭 대체) |
| `pvp/` | **pvp** | `pvp/PvpModule` | `TargetFilter`(→`DefaultTargetFilter`) |

- **자기 패키지 밖은 고치지 않는다.** 다른 서비스는 `services.xxx()` 로만 부른다 (필드에 저장 금지 — 나중에 교체됨).
  `LabyrinthPlugin`/`Services` 는 손대지 않아도 되게 되어 있다: 실제 구현은 자기 `XxxModule.enable()` 에서 setter 로 등록.
- 계약 인터페이스에 메서드를 **추가**해야 하면 소유자가 자기 패키지의 인터페이스·기본 구현을 함께 고친다 (기본 구현 클래스 이름 유지).
- 기본 구현은 전부 안전(아무것도 안 하거나 최소 동작)하며 처음 호출 시 `[미구현]` 경고를 한 번 남긴다 (`Log.notImplemented`).
- 모듈 enable 순서: core(janitor·records·data·stats·levels·combat·pack) → items → classes → mobs → dungeon → bosses → titles → ui → pvp
  → setup → commands. enable 안에서는 **앞 순서 모듈만** 확실히 준비돼 있다 (뒤 모듈은 런타임에 getter 로).
- 하위 명령: 각 모듈 enable 에서 `services.commands().addSubcommand("<루트>", Commands.literal(...))`.
  루트 = `lab`(미궁) · `party`(파티) · `stats`(스탯) · `class`(직업) · `title`(칭호) · `pvp`(대전) · `labadmin`(미궁관리, 권한 `labyrinth.admin`).
  인자 없는 루트 실행은 `MenuService.openXxx` 로 간다. core 가 이미 붙인 것: `lab enter|입장 [층]`, `lab leave|퇴장`(→DungeonService),
  `stats add|투자 <스탯> [양]`, `labadmin reload|give|setup|difficulty|level|xp|gold|points|info|pack`.
- **공용 규칙 (core 제공)**
  - 콘텐츠: `services.content()` → `content/` 의 불변 레코드(`ItemDef`, `MobDef`, `BossDef`, `FloorDef`, `LootTable`, `ClassDef`,
    `AchievementDef`, `NpcDef`, `AuraDef`, `FxModelDef`, `GlyphDef`, `ArenaDef`, `RecipeDef`, `ItemSetDef`). 자유 파라미터와 추가 필드는
    `Params`(각 정의의 `raw()`/`params()`): `dbl/integer/str/bool/sub/maps`, GDD §8.4 규칙 `scaled(key, n)`·`phased(key, phase)`.
    reload 시 새 객체로 바뀌므로 오래 보관하지 말 것.
  - 피해: 모든 피해는 `services.damage().deal(DamageContext...)` 한 곳. `DamageContext.attack(player, target, 배율, type)`(공격력 기반),
    `raw(attacker, target, 원피해, type)`(몹·보스), `percent(attacker, target, pct)`(_pct·방어 무시). `.skill(id)`, `.pattern(id)`(회피 불가),
    `.knockback(s)`, `.noCrit()`... 결과(`dealt/crit/evaded/blocked/killed`)는 ctx 에. 치유는 `services.damage().heal(target, amount, true)`.
  - 피해 가로채기: `services.damage().addInterceptor(DamageInterceptor)` — 회피되지 않은 최종 피해를 적용 직전에 바꾼다
    (0 = "막음"). items 가 무기 스킬 무적·보호막(`LabWeaponSkillService#shield`)·방어 자세·자동 부활 소모품에 쓴다. 직업 보호막도 이걸로.
  - 커스텀 몹·보스 HP: `combat.HealthPool` 계약(`applyDamage` 에 최종 피해가 온다, HP 0 이면 구현이 사망 처리). 바닐라 근접·화살 → 몹,
    몹의 바닐라 공격 → 플레이어 연결은 core `CombatListener` 가 이미 한다(`MobService.byEntity`/`BossService.byEntity` 로 판별).
  - 플레이어 HP: 바닐라 체력 = min(최대 HP, 1024), 하트는 10칸 고정 표시. 직접 만지지 말고 `services.stats().currentHp/heal/setHp`.
  - 스탯 보태기: `services.stats().addContributor((player, block) -> block.add("defense", 5))` (장비·칭호·버프). 값이 바뀌면 `markDirty(p)`.
    StatBlock 키 = GDD §11.7 + 버프용 `damage_mult`(주는 피해 %, 버프 키 `damage` 를 이 키로), `damage_taken`(받는 피해 %).
  - 경험치: `services.levels().reward(player, base × ctx.xpMultiplier())` (xp_bonus 자동 적용). 레벨업 시 `LevelUpEvent`.
  - 배율: `InstanceContext.hpMultiplier()/damageMultiplier()/dropMultiplier()/goldMultiplier()/xpMultiplier()/windup(초)`;
    인스턴스 밖 소환은 `InstanceContext.adhoc(floor, n, settings.difficulty(), settings.party())`.
  - 이벤트(`event/`): `MobKillEvent`(mobs/bosses 발생), `FloorClearEvent`(dungeon), `LevelUpEvent`(core), `ItemObtainEvent`(items),
    `CraftEvent`(items), `PvpMatchEndEvent`(pvp) — titles 가 듣는다.
  - 임시 엔티티(몹 히트박스·모델 파트·이펙트 디스플레이): 반드시 `Keys.tagTransient(entity, Keys.MOB|BOSS|FX, id)` +
    `setPersistent(false)`. `EntityJanitor` 가 재시작 후 남은 것을 청소한다. 진행 데이터는 `services.data().get(p)`(PlayerData,
    모듈 확장 값은 `ext()` 맵 + `markDirty()`), 서버 최초 기록은 `services.records().claim(key, ...)`.
  - 메뉴: `ui.Menu` 상속 → `build(viewer)` 에서 `set(slot, Button.icon(...), ctx -> ...)` → `open(p)`. 클릭 보호·연타 방지는 자동.
  - 초기 설정: 난이도 미설정이면 `settings().isDifficultySet() == false` → DungeonService 는 입장을 막고 안내.
    관리자 접속 시 `MenuService.openSetup` 이 자동으로 뜬다(`SetupListener`), 확정은 `/labadmin setup <난이도>`.

```
LabyrinthPlugin      onEnable: Services 생성 → 모듈 enable(순서대로) / onDisable: 역순 disable + 저장
Services             모든 서비스 인스턴스 보관 (생성자 주입 대신 단순 레지스트리). 순환 참조는 getter 로 지연 접근.
core/    Module(interface: name, enable, disable, reload), Keys(NamespacedKey 모음 + tagTransient), Text(MiniMessage 헬퍼), Log,
         Settings(config.yml 래퍼: 난이도/파티 배율/팩/입구 등), Difficulty, PartyScaling, ContentLoader(content/*.yml 를
         데이터폴더로 복사·로드·/reload, 손대지 않은 기본 파일은 새 버전으로 자동 갱신), ContentValidator(교차참조 검사),
         EntityJanitor(임시 엔티티 청소), SetupListener(초기 설정 안내)
content/ Content(불변 스냅샷) + 정의 레코드(ClassDef, ItemDef, ItemSetDef, MobDef, ModelDef, BossDef, FloorDef, LootTable,
         RecipeDef, AchievementDef, NpcDef, AuraDef, FxModelDef, GlyphDef, ArenaDef), Params(자유 파라미터), Rarity, ItemType,
         ContentParser(원시 YAML → 레코드, Bukkit 무관 — 단위 테스트)
event/   MobKillEvent, FloorClearEvent, LevelUpEvent, ItemObtainEvent, CraftEvent, PvpMatchEndEvent
data/    PlayerData(레벨, 경험치, 스탯포인트, 스탯, 직업, 골드, 해금층, 칭호/업적, 장신구 2칸, 통계),
         PlayerDataService(플레이어별 YAML: plugins/Labyrinth/players/<uuid>.yml, 비동기 저장, 자동저장 5분),
         ServerRecords(서버 최초 달성 기록: records.yml)
stats/   Stat(STR 힘, DEX 민첩, INT 지능, VIT 체력, WIS 정신, LUK 행운), StatService(장비+스탯+칭호 → 파생 능력치,
         바닐라 속성 반영: max_health, movement_speed, attack_speed 등), LevelService(경험치 곡선, 레벨업 연출, 포인트 지급)
combat/  DamageService(모든 피해 계산의 단일 경로: 플레이어→몹, 몹→플레이어, 스킬, 보스 패턴), DamageContext, 치명타/회피/방어
         몹·보스는 **자체 HP 풀** 사용 (바닐라 체력은 표시/사망 처리용으로만). 피해 숫자 표시(TextDisplay, 0.8초).
classes/ RoleClass(classes.yml 로드), Skill(interface), ClassService(전직, 스킬 입력, 마나, 쿨다운), skills/*(직업별 구현)
items/   ItemDef, Rarity, ItemService(정의→ItemStack, ItemStack→정의/굴림값 PDC, 툴팁 lore 생성), AuraService(전설·신화 무기
         들고 있을 때 파티클 + ItemDisplay 링 이펙트, 플레이어 수·거리 기반 LOD)
         구현: GearItemService(기반 재질 PAPER, 활만 BOW+무한·파괴불가 — 활을 들면 '미궁 화살' 1개 자동 지급),
         ItemRolls(굴림·PDC 형식 "key=value;…"), ItemTooltip, EquipRules(레벨·직업 미달 = 스탯/무기 스킬 없음, 방어구는 착용 즉시 반환),
         EquipmentListener(장비 StatContributor + 세트 효과), ConsumableListener, ItemGuardListener(바닐라 제작·화로·모루·거래 차단)
items/weaponskills/ LabWeaponSkillService(입력: LEFT = PlayerArmSwingEvent, RIGHT = 우클릭, 쿨다운·마나·침묵),
         WeaponTargeting(무기 스킬 대상 선택의 단일 도형 헬퍼 — 적/아군 판정은 TargetFilter; classes 단계에서 pvp/TargetFilter 로 이동 예정),
         SkillCast(공통 키 처리), Fx(ItemDisplay 이펙트), 17종 구현 = Projectile/Movement/Area/SupportSkills,
         조합형 `mechanics` = MechanicsEngine(실행) + mechanics/MechanicsSpec(순수 파서·검사, ContentValidator 가 호출)
loot/    LootService(loot 테이블, 희귀도 가중치, LUK 보정, 파티 개인 루팅: 아이템은 개인별로 지급/표시)
         구현 items/loot: LootRoller(순수 굴림), LabLootService(주인에게만 보이는 아이템 엔티티, 줍는 순간 ItemObtainEvent·전설 알림)
crafting/CraftingService(+대장장이 GUI, 재료 확인/소모, 결과 지급) — 구현 items/crafting: RecipeCheck, LabCraftingService, BlacksmithMenu
mobs/    MobDef, CustomMob(기반 엔티티 + 모델 리그 + HP 풀 + AI 상태), ModelRig(파트별 ItemDisplay, 보간 애니메이션:
         idle/walk/attack/hurt/death), MobService(스폰, 틱, 디스폰, 일반 몹 스킬 타입), mob skill 타입은 YAML 로 조합
bosses/  BossDef, Boss(추상: 페이즈·패턴 스케줄러), Pattern, Telegraph(원/선/부채꼴/링 장판 경고 + 판정), BossService,
         impl/Floor01Boss .. Floor10Boss (층별 고유 패턴·기믹)
dungeon/ DungeonService(입장/퇴장/진행), Instance(파티·층·난이도·배율·상태), InstanceAllocator(공허 월드 격자 슬롯),
         VoidGenerator(ChunkGenerator: 빈 월드), FloorGenerator(층 테마 팔레트로 방+복도 미로 생성, 시드 기반),
         rooms/*(전투방, 엘리트방, 보물방, 기믹방, 휴식방, 보스방), EntranceService(오버월드 입구: 지형 존중)
party/   Party, PartyService(생성/초대/수락/탈퇴/추방/위임, 파티 채팅, 최대 인원 config)
pvp/     파티 대 파티 PvP: ArenaService(arenas.yml 의 오리지널 투기장을 labyrinth_world 의 별도 슬롯에 생성·정리),
         MatchService(도전/수락, 매칭 대기열, 라운드제 best-of-N, 준비 카운트다운, 사망→관전, 라운드 종료·승패 판정,
         인원 차 보정), PvpRules(PvP 전용 피해 배율·치유 감소·제어기 지속시간 감소·포션/소모품 제한, 장비 격차 완화 옵션),
         RatingService(파티 레이팅 Elo + 개인 전적, 시즌 리셋 명령), TargetFilter(스킬·무기스킬이 '적'을 고르는 단일 규칙:
         미궁에선 몹, 매치에선 상대 팀 플레이어 — 아군 오사 방지)
titles/  Achievement(titles.yml), TitleService(조건 검사, 서버 최초 달성 방송, 칭호 장착: 채팅·탭·이름표 접두어, 소소한 보너스)
npc/     NpcService(npcs.yml: 안내인/대장장이/전직관/칭호관리인… Mannequin + 커스텀 스킨, 우클릭 → GUI)
ui/      Menu 프레임워크(InventoryHolder 기반, 커스텀 폰트 배경 타이틀, 버튼 콜백), menus/*(초기 설정(난이도), 스탯, 직업, 파티, 입장(층 선택),
         대장장이, 칭호, 장신구), HudService(액션바: HP/MP 바·레벨·골드, 사이드바: 층·남은 적·파티원 HP, 보스바)
pack/    PackService(HTTP 서빙 + 전송)
command/ CommandService(Paper Brigadier: LifecycleEvents.COMMANDS)
```

### 4.1 classes 단계에서 추가된 계약 (다른 모듈이 쓰는 것)
- **피해 훅** `combat.DamageService.Hook` (`services.damage().addHook(h)`): `before(ctx)`(원피해 직후 — `ctx.amount/threat/critBonus` 조정),
  `absorb(ctx, dmg)`(적용 직전 — 보호막·피해 분담 후 남은 피해 반환), `after(ctx)`(적용 후 — 적중 효과). `DamageContext.critBonus(x)`
  = 이 피해의 치명타 확률 가산(≥1 확정). classes 가 상태이상·보호막·패시브에 쓰고, pvp 도 매치 규칙(피해 배율 등)에 쓸 수 있다.
- **StatusEffectService**(`classes.LabyrinthStatusEffectService`): GDD §9.2 14종 + `venom`(중첩 독) · `mark`(받는 피해+) · `cooldown_slow` ·
  `interrupt`(보스 시전 끊기 신호). 확장 메서드: `addShield/shield`, `stealth/isStealthed/breakStealth`, `isKnockbackImmune`, `cooldownRate`,
  `removeBuff/hasBuff`, `clearAll`. 이동 제한은 속성 수정치로 자동. **mobs/bosses 는 AI·스킬·패턴 전에 `isStunned` 확인**, 은신 대상 제외,
  밀쳐내기는 `isKnockbackImmune` 확인. 몹·보스의 weaken/vulnerable/mark 는 훅이 직접 곱하므로 `HealthPool.damageTaken()` 에 더하지 말 것.
  보스는 stun/root/빙결 면역(스킬은 boss_* 값 사용). 지속 피해 sourceId = `effect:<id>` (적중 효과에서 제외용).
- **ClassService** 확장: `changeClass(p, id)`(전직관 NPC·직업 메뉴가 부를 것 — 검사·안내·연출 포함), `skillBar(p)`(HUD 용 스킬 한 줄), `isChanneling(p)`.
  무기 스킬(items)은 `services.effects().isSilenced(p)` 와 `cooldownRate(p)` 를 확인할 것.
- **DungeonService** 기본 메서드: `isDowned(p)`, `revive(p, at, hpRatio)`(사제 부활의 성가) — dungeon 구현은 자기 사망 상태와 맞게 재정의.
- 직업 스킬은 미궁 무기 + **직업 무기 타입**(classes.yml weapon_types)을 들었을 때만 발동. 명령: `/직업 선택|choose <직업>`, `/직업 정보|info`, `/직업 스킬|skills`.

### 4.2 ui+titles 단계에서 추가된 계약 (다른 모듈이 쓰는 것)
- **MenuService** 실제 구현 `ui.LabMenuService`(상자 GUI, `ui/menus/*`; 열다가 오류 나면 채팅 메뉴로 대체). 기본 메서드 추가:
  `openPvp`(대전 메뉴) · `openBlacksmith`(→ CraftingService GUI) · `openMerchant`(npcs.yml `role: merchant` 의 ShopMenu).
  `/대전` 인자 없이 = 대전 메뉴. `/미궁 메뉴|장신구|대장간|상점|대전|기록` 하위 명령.
  메뉴는 다른 모듈 기능을 **명령으로 위임**한다(검사·메시지 일관): 파티 `party create|invite|accept|decline|kick|promote|disband|leave|chat`,
  대전 `pvp 도전 <파티장>|수락|거절|대기열 참가|대기열 취소` ← **pvp 담당은 이 한국어 하위 명령 이름을 그대로 등록할 것**.
  초기 설정 GUI 확정 = `labadmin setup <난이도>` + config `entrance.mode`, "여기에 설치" = `labadmin setentrance <block|npc>`.
- **대전 전적 표시(PvpMenu·순위)**: PlayerData ext `pvp.rating · pvp.wins · pvp.losses · pvp.streak · pvp.best_streak · pvp.best_rating`
  (정수) 를 읽는다 → **pvp 담당이 이 키로 기록할 것**. 없으면 titles 카운터(`titles.pvp_*`)로 대신 표시.
- **HudService** 실제 구현 `ui.LabHudService`: 액션바(0.25초 검사, 바뀐 때만 + 2초 유지 재전송) HP·MP·경험치 막대·레벨·골드,
  미궁 사이드바(층·난이도·인원·정복한 방·타이머·사망·파티원 HP), 플레이어마다 개인 스코어보드(이름표 팀 접두어 = 칭호).
  기본 메서드 추가: `nameTagPrefix(target, prefix)`, **`pvpMatch(viewer, HudService.PvpHud)` / `clearPvpMatch(viewer)`** —
  pvp 담당은 매치 중 1초마다 참가자·관전자에게 `PvpHud(matchId, phase(prep|fight|sudden_death|between|end), round, roundsToWin,
  scoreUs, scoreThem, secondsLeft, phaseSeconds, usName, themName, us[TeamMember(name,hpRatio,alive)], them[...])` 를 보내면
  사이드바 + 라운드 보스바가 그려진다(15초 갱신이 없으면 자동 정리).
- **DungeonService** 기본 메서드 `floorProgress(p)` → `FloorProgress(floor, roomsCleared, roomsTotal, deaths, startedAt, bossDefeated,
  ready, progress)` (HUD 용; 전투·정예·시련·수호자 방만 셈). dungeon 담당이 더 정확히 재정의해도 된다.
- **TitleService** 실제 구현 `titles.LabTitleService`. 기본 메서드 추가: `setBonusSuppressed(p, on)`(**pvp 담당이 매치 시작/종료 때 호출** —
  §18.3 칭호 보너스 꺼짐), `progress(p, id)`. 판정은 `titles.AchievementRules`(순수, 테스트), 카운터 갱신은 `titles.TitleCounters` —
  카운터 키 `titles.*` 목록은 AchievementRules 문서가 원본. 서버 기록 키: `first_clear.floor_<n>`(층 최초 돌파 파티 전원),
  `speed.floor_<n>`(최단 시간), `title.<업적 id>`(server_first 업적). 첫 칭호는 자동 장착. 채팅 = AsyncChatEvent 렌더러
  `[칭호] 이름 » 메시지`(취소된 파티 채팅은 건드리지 않음), 탭 목록 이름 = 접두어 + 이름.
  명령: `/칭호 장착|해제|목록|기록`, `/labadmin title grant|revoke <플레이어> <id>`, `/labadmin title recheck`.
- **UI 글리프 이름 (pack-ui 단계가 glyphs.yml 에 이 이름으로 넣으면 자동 적용, 없으면 글리프 없이 동작)**:
  - 메뉴 배경 `gui_<메뉴>`: main · stats · class · class_detail · party · players · titles · records · entrance · setup · accessories ·
    pvp · pvp_ranking · blacksmith · merchant (없으면 `gui_rows_<줄 수>`). 6줄 메뉴 = 54칸, 5줄 = 장신구·상점.
    선택 필드(glyphs.yml 항목에 추가 가능): `width`(배경 폭 px, 기본 176), `title_x`(제목 글자 시작 x, 기본 8), `title_color`(#RRGGBB,
    기본 #3b2a4d). 배경 글리프는 펜을 −8 당겨 컨테이너 왼쪽 끝부터 그린다 → ascent 는 제목 줄 기준(바닐라 상자 제목 높이)으로 맞출 것.
    글리프 배경이 있으면 빈 칸을 유리판으로 채우지 않는다(배경 그림이 보이도록).
  - HUD 막대 kind = `hp` · `mp` · `xp`: 프레임 방식 `hud_<kind>_0..N`(채움 단계별 한 장) 또는 칸 방식 `hud_<kind>_full|half|empty`
    (hp 10칸, mp 8칸, xp 6칸; 옛 이름 `<kind>_bar_full|half|empty` 도 인식). 아이콘 `hud_hp_icon · hud_mp_icon · hud_level_icon ·
    hud_gold_icon`. 액션바 줄 높이에 맞는 ascent 로 만들 것.

### 명령어
- 플레이어: `/lab`(별칭 `/미궁`: 입장 메뉴·퇴장·정보), `/party`(`/파티`), `/stats`(`/스탯`), `/class`(`/직업`), `/title`(`/칭호`),
  `/pvp`(`/대전`: 도전 <파티장>, 수락, 거절, 대기열 참가/취소, 순위, 전적, 관전)
- 관리자(`labyrinth.admin`): `/labadmin reload|give <item> [player]|spawnmob <id>|spawnboss <floor>|setentrance|removeentrance|
  setnpc <id>|tpfloor <n>|unlock <player> <floor>|reset <player>|instances|endinstance <id>|pvp season|pvp end <매치>|pvp arena <id>`
  (items 가 붙임: `blacksmith [player]`(대장간 GUI) · `loot <table> [player]`(개인 루팅 테스트) · `weaponskills`(구현 목록))

### 스킬 입력 (미궁 무기를 들고 있을 때)
- **무기 스킬** (상위 무기에 내장, `items.yml` 의 `weapon_skills`):
  좌클릭 = 무기 기본기(예: 검을 휘두르면 검기가 날아감, 짧은 내부 쿨다운),
  우클릭 = 무기 스킬, 웅크리기+좌클릭 = 무기 스킬2, 웅크리기+우클릭 = 무기 스킬3(오의).
  **무기마다 다르게**: 상위 무기라고 4칸을 다 채우지 않는다. 무기 콘셉트에 맞는 1~3개가 보통이고,
  4개 전부는 일부 신화 무기만. **좌클릭 기본기(검기 등)는 소수의 무기에만** — 대부분의 무기는 좌클릭이
  평범한 공격이다. 활은 우클릭(당기기)을 그대로 둔다.
- **직업 스킬**: F(손 바꾸기) = 스킬1, 웅크리기+F = 스킬2, Q(버리기) = 스킬3, 웅크리기+Q = 궁극기.
  미궁 무기를 든 상태의 손 바꾸기·Q 버리기 이벤트는 취소(인벤토리 창에서 끌어서 버리기는 허용).

### dungeon+party 구현 메모 (다른 모듈이 알아야 할 것)
- **설정 파일**: 미궁 진행 수치는 `plugins/Labyrinth/dungeon.yml` (jar 기본값 `src/main/resources/dungeon.yml`: 틱당 블록 수, 동시 인스턴스,
  층 높이·간격, 문 닫힘 지연, 몹 수 인원 보정, 휴식방 회복, 대체 보스 배율, 보물방 미믹 확률 …). 난이도·파티 배율은 그대로 config.yml.
- **공허 월드 좌표**: 미궁 인스턴스는 `InstanceAllocator` 슬롯(간격 2048, **z ≥ 2048** 영역)만 쓴다. **pvp 투기장 등 다른 모듈은 z < 0 영역을 쓸 것.**
  층 n 의 바닥 y = `top_floor_y − (n−1) × floor_spacing` (기본 280, 30 → B1 y280 … B10 y10). 같은 슬롯에서 아래층일수록 실제로 낮다.
- **인스턴스 id**: `InstanceContext.id()` = `r<번호>s<슬롯>-b<층>` (층마다 새 컨텍스트, 같은 Run 의 배율·난이도 유지). 몹·보스 정리는 이 id 로.
- **보스방**: 원형 투기장(bosses.yml `arena.radius/height`, `shape: circle|clock_face|tiled_circle` 바닥 무늬, `corridor_length/width` 면
  중심에서 **+z 방향**으로 추격 복도). 입구는 북쪽(−z). `spawnBoss(floor, 중심, ctx)` 의 중심 = 바닥 위 1칸. 보스 구현이 투기장에 놓은 블록은
  층 정리 때 원기둥(바닥 아래 2칸~천장) 전체를 비우므로 따로 안 지워도 된다. null 이면 층 정예 몹을 HP×`boss_fallback.hp_mult` 로 대신 세운다.
  보스 처치 후 투기장 중심 남쪽에 아래층 계단이 생긴다(중심 +2~+11 z 칸을 비워 둘 것).
- **이벤트**: 보스 처치 시 `FloorClearEvent`(참가자 전원, 입장 인원, 그 층 사망 수, 그 층 소요 초, 서버 난이도). 해금층 = 깬 층+1.
  PlayerData counters: `dungeon.floor_clears`, `dungeon.clear_floor_<n>`, `dungeon.solo_clears`.
- **사망**: 미궁 안 PlayerDeathEvent 는 취소되고 관전 모드(휴식방 도달·보스 처치 시 부활). 전원 쓰러지면 전멸 → 귀환.
  `DungeonManager` 가 `isDowned`/`revive` 를 재정의한다 — 쓰러짐 = Run 의 사망자 목록(게임 모드만 보지 않음), 사제 부활도 `Run.revive` 경로.
- **게임 모드** (`dungeon/GameModes`, 순수 로직·단위 테스트): 일반 입장 = 층에 도착할 때 서바이벌(입장 전 모드는 `Run.modes` +
  PlayerData ext `dungeon.gamemode` 에 기억 → 귀환·`recoverStranded` 때만 되돌림), 재접속 = 쓰러짐 관전 / 아니면 서바이벌, 부활 = 서바이벌.
  `adminEnter`(tpfloor) Run 만 `adminTest` 로 모드를 건드리지 않는다. (보스·몹·TargetFilter 는 크리에이티브·관전을 노리지 않는다.)
- **전멸 훅**: `Run.wipe()` → 현재 층 모든 방의 `Room.onWipe()` (BossRoom·GimmickRoom 이 점진 힌트 실패를 기록).
- **명령**: `/미궁 귀환|return`, `/미궁 정보|info`, `/파티 생성|초대|수락|거절|탈퇴|추방|위임|해산|채팅|정보`,
  `/labadmin setentrance [block|npc] · removeentrance · tpfloor <층> · unlock <플레이어> <층> · instances · endinstance <id>`.
- **입구**: block 방식 석문은 바꾼 원래 블록을 `entrance.yml` 에 저장 → removeentrance 가 복원. npc 방식은 블록 변경 0. 둘 다 npcs.yml
  `role: entrance` NPC 를 `NpcService.place` 로 세운다. 석문 우클릭 = `MenuService.openEntrance`.

### bosses 구현 메모 (floors 6~10 담당이 알아야 할 것)
- **구조**: `bosses/LabBossService`(BossService 구현 — 층→`BossFactory` 등록부, 1틱 루프 하나로 모든 보스 진행, 엔티티→핸들 조회,
  웅크리기·바닐라 피해 이벤트를 아레나의 보스에 전달) · `Boss`(추상 기반) · `impl/FloorNNBoss extends Boss`(생성자 `(Boss.Init)`).
  새 층 보스는 `LabBossService#registerDefaults()` 에 `register(NN, FloorNNBoss::new)` 한 줄.
- **Boss 기반이 해 주는 것**: 자체 HP 풀(DamageService 경로·위협 표·도발), 페이즈(`phases`, 전환 시 진행 중 경고 정리 + 1.5초 무적 + 대사 +
  보스바 깜빡임), `PatternScheduler`(GDD §8.3: cooldown/interval/system, 가중치 `weight`, 직전과 다른 패턴 우선, 최소 1.2초 간격),
  광폭화 타이머, 보스바(이름·칭호·페이즈·광폭/기절) + 시전 바(`boss_cast` 키, 끊을 수 있는 시전은 파란색), 아레나 경계(이탈 시 복귀),
  추격·기본 공격, `BossRig` 시전 애니메이션(`BossAnim`: SLAM·SWEEP·CHARGE·ROAR·THROW·CAST·POUR·LEAP·DROP·SPIN·STUN·DEATH — 팔·머리 파트 +
  몸 전체 회전/이동 오버레이), 보상(경험치·골드·`loot.drop(…,"boss")`·`MobKillEvent(boss=true)`), 정리(쫄·오브젝트·디스플레이·설치 블록 복원).
- **하위 클래스가 채우는 것**: `onSpawn()`(아레나 배치) · `startPattern(key)`(쿨다운 패턴 → 묶이는 틱 반환, 보통 `cast(...)` 의 반환값) ·
  `runInterval(key)` · `tickSystem(key)` · `onPhase(n)` · 필요 시 `canUse/onTick/onSneak/onPlayerVanillaDamage/knockbackImmune/outgoingMult/incomingReduction/onEnd`.
- **부품**: `Telegraph`(circle/ring/line/cone/arrow/tile/safe — fx 판 + DUST 윤곽, 0.3초 전 깜빡임, `follow(entity)`), `Mechanics`
  (Delay·Repeat·Zone(잔류 장판)·Marker(머리 위 표식)·Projectile(직선/포물선/왕복)·Tether), `ObjectTarget`(부술 수 있는 기믹 오브젝트 —
  BossHandle 이라 근접·화살·스킬이 그대로 맞음, 피해 유형 필터 `accept(...)`), `BossFx`(fx 디스플레이·글자·블록 디스플레이), `BossMath`(도형 판정·
  GDD §8.4 공식·배치 각도), `MechanicScaling`(난이도·페이즈·광폭화별 쿨다운 배율, 다중 대상 추가 개수(어려움 6인+ +1, 악몽 +1/+2),
  투사체 속도, 오브젝트 HP, 기믹 제한 시간 배율). 경고 시간은 `windup(params, 기본초)` = 난이도 telegraph 배율·최소 0.5초.
- **블록**: `setBlock(...)` 은 실제 인스턴스(`!adhoc`) + `labyrinth_world` 에서만 놓고 원래 블록을 기억해 사망·종료 때 복원한다(계단 자리 보호:
  `BossMath.inStairZone`). 관리자 소환(`/labadmin spawnboss <층> [인원]` — 서 있는 곳이 중심)은 블록 대신 디스플레이로 대체.
  관리자 명령: `spawnboss`, `endboss`(근처 보스전 종료), `bosses`(목록).
- 보스는 stun/root/빙결 면역(상태이상 서비스가 거름) — 기믹 기절은 `Boss.stun(초)`(+ `makeVulnerable`). `interrupt` 신호는 `interruptible`
  시전만 끊는다. 패턴 피해 대상은 `players()`(TargetFilter·아레나 경계·쓰러짐 제외), 대상 선택은 `targets()`(은신 제외).
- **문구 규칙** (GDD §19): `broadcastBar`/`notify`/이름표에는 조작법·정답을 쓰지 않는다(분위기·관찰 단서·진행도 아이콘만).
  정답은 bosses.yml `hints: [단서1, 단서2, 단서3]` 에 쓰면 BossRoom 이 실패 횟수에 맞춰 보스바 아래(`dungeon_boss_hint`)에 띄운다 —
  보스 구현은 아무것도 하지 않아도 된다.
- **점진 힌트** (`core/Hints`): 실패 횟수 = PlayerData ext `hints.boss.<id>` / `hints.gimmick.<키>`, 단계 = 함께 있는 파티원 최댓값 →
  config `hints.mode/thresholds`. 표시: BossRoom(등장 2.5초 뒤 20초), GimmickRoom(`hints()` — 입장 채팅 + `dungeon_gimmick_hint` 막대),
  휴식방 이야기 NPC(`NpcServiceImpl` — 그 층 보스 단서를 대사 첫 줄로).

### 통합·배포 메모 (integration-release 단계)
- **메뉴 배경 규칙** (`ui.UiTheme.background(menu, rows)`): 메뉴별 배경 `gui_<menu>` 에는 버튼 소켓이 그려져 있으므로 **버튼 배치가
  glyphs.yml `menus.<id>.slots` 와 같은 메뉴만** 전용 배경을 쓴다(현재 blacksmith · titles · setup · class · party — `SOCKET_LAYOUT`). 나머지는 같은 줄 수의
  `gui_rows_<n>` → `gui_generic_<n>`. 배경 높이로 줄 수를 계산해 줄 수가 다르면 절대 쓰지 않는다(5줄 메뉴 = 배경 없음 + 테두리).
  메뉴를 소켓에 맞게 고쳤으면 `SOCKET_LAYOUT` 에 id 를 추가할 것. 제목 색 = `menus.<id>.title_color`.
- **글리프 액션바** `ui.GlyphHud`: glyphs.yml `hud:` 수치대로 xp·hp·(보호막)·mp 바(`hud_*_00..20`), 레벨 배지·숫자, 상태 아이콘(`status_<효과>`,
  StatusEffectService#has), 골드 줄을 배치하고 전체 advance 를 `hud.total` 로 맞춘다(그림자 끔). 필요한 글리프가 없으면 텍스트 HUD.
  사이드바 파티원 줄 = `party_class_<직업>` + `party_hp_00..10`. 보스바 이름 양옆 = `boss_ornament_left/right`.
- **자가 진단** `/labadmin selftest [층 수]` (`dungeon.SelfTest`, 콘솔 가능): 아이템 전부 생성·역조회 → 도감 획득처 계산 → 임시 슬롯에 층 생성 →
  몹·정예 정의 전부(+정예 변종) 소환·피해·처치 → 1~5층 보스 + 구현 없는 층 대체 보스 소환·페이즈 피해·처치 → 정리. 진단 중 로그의
  SEVERE/예외를 하위 시스템(`kr.labyrinth.<패키지>`)별로 센다. 새 보스·몹을 넣으면 이것부터 돌릴 것.
- **도감** `/codex` = `/도감` = `/미궁 도감` (`ui.menus.CodexMenu`): 종류·희귀도별 아이템(실제 툴팁 + 획득처: 몹/보스 드롭·보물 상자·기믹 방·
  제작 재료·상점·칭호 보상 — loot 테이블 중첩·rarity_pool 까지 계산), 몬스터·보스(모델 머리 아이콘·능력치·드롭).
- **config.yml** 추가 키: `mobs.elite_variant_chance`(기본 0.06), `mobs.model_yaw_offset`(도, 기본 0).
- **에셋 id 대조** `python3 tools/check_assets.py [팩.zip]`: 아이템(활 당김 모델 포함)·방어구 세트·몹/보스 파트·NPC 스킨·fx(fx.yml + 아우라·params.fx
  참조 + Java 스킬 fx 기본값)·글리프(font/ui.json 문자, 메뉴 배경 줄 수) ↔ 팩 zip. 오류 0 이어야 배포.
- **배포** `./release.sh` → `dist/Labyrinth-Server-<버전>.zip` (폴더 `Labyrinth-Server/`: start.bat·start.ps1·start.sh·server.properties·README.txt·
  LICENSE·plugins/Labyrinth.jar·Labyrinth-pack.zip(+sha1)). 템플릿은 `release/` (`__VERSION__` 치환, 윈도우 파일 CRLF, ps1·README UTF-8 BOM).
  eula.txt·paper.jar·world 는 절대 넣지 않는다 — 시작기가 Java 25(Adoptium API)와 Paper 26.3 최신 STABLE(Fill API v3, sha256)을 받고
  EULA 는 서버 주인이 직접 Y 로 동의한다. `dist/` 는 커밋하지 않는다.

## 5. 게임 규칙 (수치는 YAML/config 로 조정 가능해야 함)

- 레벨 1~50. 레벨업마다 스탯포인트 5. 스탯 초기화 아이템/명령.
- 직업 6종: 수호기사(탱커), 광전사(근접 딜러), 사냥꾼(원거리), 비전술사(마법 광역), 사제(힐·버프), 그림자(암살·치명타).
  각 직업 스킬 4개(3 + 궁극기), 레벨에 따라 해금. 직업 전용 무기 타입.
- 희귀도: 일반(흰) < 고급(초록) < 희귀(파랑) < 영웅(보라) < 전설(금, 아우라) < 신화(빨강, 애니메이션 아우라).
  **전설·신화 무기 텍스처는 프레임 애니메이션(.mcmeta, GIF 처럼 움직임)** + 들고 있을 때 파티클/링 아우라.
- 장비 획득 루트: 일반 몹 드롭 / 엘리트·보스 드롭(보스 전용 장비) / 대장장이 제작(몹 재료) / 보물방 상자 / 칭호 보상.
- 미궁: 지하 1~10층. 층마다 테마·몹 3~4종·엘리트·고유 보스(페이즈 2~3, 고유 기믹). 보스 처치 → 다음 층 계단.
  - 해금: 처음엔 1층만. 층을 깨면 다음 층 해금. 파티는 **파티원 중 최소 해금층**까지 선택 가능.
  - 솔로 입장 또는 파티 입장(파티원 모두 입구 근처, 파티장만 시작).
  - **파티 인원 배율**: 몹 HP ×(1 + `hp_per_member`×(n−1)), 피해 ×(1 + `dmg_per_member`×(n−1)), 보상 약간 증가. config.
  - **난이도는 서버 전체 설정 하나**: 쉬움/보통/어려움/악몽 (HP·피해·드롭 배율, config.yml 프리셋). **난이도 해금 없음**,
    입장할 때 고르지도 않음. **서버를 처음 만들 때 관리자가 정한다**: 첫 실행 시 `config.yml: difficulty` 가 비어 있으면
    처음 접속한 관리자(OP/`labyrinth.admin`)에게 **초기 설정 GUI**(난이도 4개 + 입구 방식 블록/NPC-only)를 띄우고,
    정하기 전까지 미궁 입장을 막는다(안내 메시지). 이후 변경은 `/labadmin difficulty <난이도>` 또는 config 수정 후 reload
    (진행 중인 인스턴스에는 다음 입장부터 적용). 콘솔에서도 `/labadmin setup <난이도>` 가능.
    (층 해금은 그대로 유지: 처음엔 1층, 깬 층의 다음 층까지 입장 가능.)
  - 사망: 파티원이 있으면 관전 모드 → 휴식방 도달/보스 처치 시 부활. 전멸 시 인스턴스 실패·귀환. 아이템 손실 없음.
- **PvP (파티 대 파티)**: 파티장이 다른 파티에 도전하거나 대기열로 매칭. 전용 투기장(미궁 월드 별도 슬롯, 지형 무관)에서
  best-of-3 라운드. 인원이 다르면 config 에 따라 거절/허용(적은 쪽 HP·피해 보정). PvP 전용 밸런스 규칙(피해 배율, 치유 감소,
  제어기 감소). 미궁 밖·미궁 안에서는 PvP 꺼짐(매치 안에서만). 결과로 파티 레이팅·개인 전적·PvP 칭호. 장비/아이템 손실 없음,
  돈으로 살 수 있는 이점 없음(EULA).
- 칭호: 업적 달성 시 획득. 서버 최초 층 클리어(1등 파티 전원에게만), 솔로 클리어, 무사망 클리어, 난이도별 클리어,
  처치 수, 레벨, 전설·신화 획득, 제작 횟수, 스피드런 등. 칭호 1개 장착(채팅/탭/이름표 접두어), 일부는 작은 스탯 보너스.

## 6. 콘텐츠 YAML 스키마 (`plugin/src/main/resources/content/`)

모든 파일은 최상위에 `version: 1`. 수치는 정수/실수. 텍스트는 MiniMessage 허용.

```yaml
# classes.yml
classes:
  guardian:
    name: "수호기사"
    role: tank            # tank | melee | ranged | magic | healer | assassin
    icon_item: guardian_emblem   # items.yml id
    weapon_types: [sword_shield]
    base_stats: {STR: 5, DEX: 2, INT: 1, VIT: 6, WIS: 2, LUK: 1}
    per_level: {hp: 6, mp: 2}
    skills:
      - id: shield_bash          # 코드의 Skill 구현 키 (classes/skills/*)
        name: "방패 강타"
        input: SWAP              # SWAP | SNEAK_SWAP | DROP | SNEAK_DROP (직업 스킬)
        unlock_level: 1
        mana: 10
        cooldown: 6.0            # 초
        params: {damage: 1.2, stun: 1.0}   # 구현이 읽는 자유 파라미터
        description: "..."

# items.yml
items:
  ember_greatsword:
    name: "잿불 대검"
    type: weapon              # weapon | armor | accessory | material | consumable | key
    weapon_type: greatsword   # classes.weapon_types 와 매칭. bow 는 활 동작.
    armor_slot: null          # head | chest | legs | feet | offhand(방패, 수호기사 보조손) (armor 일 때)
    armor_set: null           # 방어구면 장비 에셋 세트 id
    rarity: legendary
    level_req: 25
    classes: [berserker]      # 비우면 모두
    stats: {damage: [38, 44], STR: [6, 9], crit_chance: [0.04, 0.06]}   # [최소, 최대] 굴림
    set_bonus: null           # 세트 id (sets: 섹션 참고)
    aura: ember               # fx.yml aura id (전설/신화 무기)
    weapon_skills:            # 일부 상위 무기에만, 무기마다 1~4개(보통 1~3). 좌클릭 기본기는 소수 무기만. 구현: items/weaponskills/*
      - id: slash_wave        # 구현 키 = GDD §17 Weapon skill catalog 의 닫힌 목록(17개). 같은 구현을 params·fx·이름만 바꿔 재사용
        name: "잿불 검기"
        input: LEFT           # LEFT | RIGHT | SNEAK_LEFT | SNEAK_RIGHT
        cooldown: 0.8
        mana: 0
        params: {damage: 0.8, range: 12, width: 2.5, fx: ember_slash}
        description: "휘두를 때마다 불꽃 검기를 날린다."
    model:                    # 3D 모델 지시 (리소스팩 생성기)
      shape: greatsword       # 생성기 3D 템플릿 (GDD.md "Pack generator templates" 의 닫힌 목록)
      length: 1.0             # 상대 크기
    texture:                  # 리소스팩 생성기 지시 (자체 제작 픽셀아트, 3D 모델 UV 아틀라스)
      style: greatsword       # 생성기가 아는 재질/장식 템플릿
      palette: ["#2b0d05", "#7a2410", "#e0571d", "#ffc46b", "#fff4d6"]
      animated: true          # 전설/신화 무기는 true
      frames: 8
      frametime: 2
      effect: ember_flicker   # 생성기 이펙트 프리셋
    lore: "용광로 대장간의 마지막 불씨로 벼린 검."
sets:
  forge_warden:
    name: "용광로 수문장"
    pieces: [forge_warden_helm, forge_warden_chest, forge_warden_legs, forge_warden_boots]
    bonuses: {2: {VIT: 5}, 4: {damage_reduction: 0.08}}

# mobs.yml
mobs:
  moss_crawler:
    name: "이끼 기어다니는 자"
    floor: 1
    base: SPIDER              # 히트박스/AI 용 바닐라 엔티티 (투명·무음 처리)
    scale: 1.0
    hp: 60
    damage: 6
    defense: 2
    speed: 0.28
    xp: 12
    gold: [2, 5]
    ai: melee                 # melee | ranged | caster | charger | swarm | turret
    skills:                   # 일반 몹 스킬 타입 (MobService 가 구현): leap, poison_spit, shield, summon, blink, ...
      - {type: leap, cooldown: 6, params: {power: 0.9, damage: 1.2}}
    drops: moss_crawler       # loot.yml 테이블 id
    model:
      texture_size: [64, 64]
      parts:
        - {name: body, pivot: [0, 0.4, 0], anim: body}
        - {name: head, pivot: [0, 0.6, 0.4], anim: head}
        - {name: legs, pivot: [0, 0.2, 0], anim: legs_walk}
      style: {palette: ["#1d2b14", "#3f5a23", "#7fa043", "#c9d98a"], shape: crawler}   # 생성기 지시

# bosses.yml  (패턴 로직은 bosses/impl/FloorNNBoss.java, 여기엔 수치·이름·모델)
bosses:
  floor01_moss_warden:
    name: "이끼 파수꾼 그로브"
    floor: 1
    title: "회랑의 수호자"
    base: IRON_GOLEM
    scale: 1.6
    hp: 2400
    damage: 14
    defense: 8
    phases: [1.0, 0.6, 0.25]   # HP 비율 경계
    xp: 400
    gold: [80, 120]
    drops: floor01_boss
    patterns: {vine_lash: {damage: 1.3}, spore_burst: {radius: 6}}   # 구현이 읽는 파라미터
    arena: {radius: 14, theme: mossy}
    model: { ... mobs 와 동일 ... }

# floors.yml
floors:
  1:
    name: "이끼 낀 회랑"
    theme: mossy
    palette: {floor: [MOSSY_STONE_BRICKS, STONE_BRICKS], wall: [...], ceiling: [...], accent: [...], light: [...]}
    size: {cells: 6}          # 미로 셀 수 (cells×cells)
    rooms: {combat: 6, elite: 1, treasure: 1, gimmick: 1, rest: 1}
    mobs: [moss_crawler, ...]
    elite: moss_crawler_alpha
    boss: floor01_moss_warden
    gimmick: lever_sequence   # 기믹방 구현 키
    ambient: {particle: SPORE_BLOSSOM_AIR, sound: ...}

# loot.yml
tables:
  moss_crawler:
    rolls: 1
    entries:
      - {item: moss_fiber, chance: 0.6, amount: [1, 2]}
      - {item: mossbound_dagger, chance: 0.02}
      - {rarity_pool: uncommon, chance: 0.05, floor: 1}   # 해당 층 장비 중 희귀도 랜덤

# recipes.yml
recipes:
  ember_greatsword:
    result: ember_greatsword
    station: blacksmith
    materials: {forge_core: 1, ember_shard: 12, dark_iron_ingot: 8}
    gold: 1500
    level_req: 25

# titles.yml
achievements:
  first_clear_floor_1:
    name: "회랑의 개척자"
    description: "서버 최초로 지하 1층을 돌파"
    condition: {type: FIRST_CLEAR, floor: 1}   # FIRST_CLEAR | CLEAR | SOLO_CLEAR | NO_DEATH_CLEAR | DIFFICULTY_CLEAR |
                                               # SPEED_CLEAR | KILL | BOSS_KILL | LEVEL | OBTAIN_RARITY | CRAFT
    title: "<gradient:#7fa043:#c9d98a>회랑의 개척자</gradient>"
    bonus: {LUK: 1}
    broadcast: true

# arenas.yml  (오리지널 투기장 — 생성기 코드가 블록 팔레트로 지음)
arenas:
  sunken_colosseum:
    name: "가라앉은 투기장"
    size: [41, 41]             # 바닥 크기
    palette: {floor: [...], wall: [...], accent: [...], light: [...]}
    layout: pillars_ring        # 구현 키: pillars_ring | bridges | tiers | maze_lite | central_altar ...
    team_spawns: 2
    hazards: [{type: rising_water, start: 90}]   # 선택: 시간이 지나면 발동
pvp:
  rounds_to_win: 2
  round_time: 180
  allow_uneven: true
  uneven_bonus: {hp: 0.15, damage: 0.10}   # 인원 1명 차이당 적은 쪽 보정
  rules: {damage_mult: 0.6, healing_mult: 0.7, cc_duration_mult: 0.6, consumables: false}
  rating: {start: 1000, k: 32}

# titles.yml 조건 추가: PVP_WIN(count) | PVP_STREAK(count) | PVP_RATING(min) | PVP_FIRST_WIN  (+ 선택 키 server_first: true)

# npcs.yml
npcs:
  guide:
    name: "미궁 안내인 벨라"
    skin: guide
    role: entrance            # entrance | blacksmith | class_master | title_keeper | merchant
    skin_style: {palette: [...], outfit: robe}   # 생성기 지시

# fx.yml  (아우라·경고장판·투사체 모델/파티클 정의)
auras:
  ember: {particles: [{type: FLAME, count: 2, radius: 0.6}], ring_model: ember_ring, ring_spin: 6.0}
models:
  ember_ring: {style: ring, palette: [...], animated: true, frames: 8}
  telegraph_circle: {style: telegraph_circle, palette: ["#ff3b3b"], animated: true, frames: 6}

# glyphs.yml  (pack-ui 단계에서 작성 — 전체 207 글리프, 상세 주석은 파일 머리말)
glyphs:
  gui_stats:  {char: "\uE001", file: gui/stats.png, ascent: 13, height: 222, advance: 177}
  hud_hp_14:  {char: "\uE10E", file: hud/hp_14.png, ascent: -2, height: 9, advance: 83}
spaces: {neg_1: -1, neg_8: -8, neg_169: -169, pos_1: 1}   # 공백 프로바이더 (값 v → U+F800+v)
menus:                     # 메뉴 배경별 배치 계약 (ui 담당이 따름)
  stats: {glyph: gui_stats, rows: 6, title: "스탯 배분", title_color: "#f3e3bd",
          slots: {stat_icons: [0, 9, 18, 27, 36, 45], plus_1: [6, ...], plus_5: [7, ...], plus_10: [8, ...]}}
hud: {total: 182, bar_steps: 20, bar_width: 82, hp_x: 0, badge_x: 82, mp_x: 100, xp_x: 0, status_x: 0, gold_right: 182, ...}
```

스키마를 확장해야 하면 필드를 **추가**만 하고 이 문서 §6 을 갱신한다. 생성기·플러그인 모두 모르는 필드는 무시한다.

### 6.1 콘텐츠 단계에서 추가된 필드 (classes/floors/mobs/bosses/npcs/titles/fx)
값의 닫힌 목록과 해석은 GDD.md 에 있다(§번호 표기). 모두 **추가** 필드이며 위 예시의 기존 필드는 그대로다.

- **classes.yml**: `color`(UI 색), `description`, `primary_stat`, `base_hp`, `base_mp`, `mana_regen`(초당),
  `passive: {id, name, description, params}`. 스킬 params 해석 규칙 = GDD §4.1.
- **floors.yml**: `subtitle`, `description`, `level_range: [min, max]`, `decor: [{block, where(floor|ceiling|wall|corner), chance}]`,
  `liquid(WATER|LAVA|null)`, `room_height`, `mob_density: [min, max]`(전투방당), `gimmick_params`(기믹방 구현이 읽음, GDD §10),
  `ambient: {particle, density, sound(바닐라 사운드 키), sound_interval: [min, max], volume, pitch}`.
- **mobs.yml**: `description`, `rank(normal|elite|add)`, `flying`, `sounds: {ambient, hurt, death, pitch}`, `drops: null`(소환물).
  `skills[].type` = GDD §9.1 닫힌 목록(24종), `params.effect` = §9.2. `model.parts[]` 에 `form`·`size: [w,h,d]`(px) 추가,
  `model.style` 에 `features` 추가 (form/anim/shape/features 목록 = GDD §14.3).
- **bosses.yml**: `core`(핵심 기믹 키, 보스마다 다름), `description`, `speed`, `flying`, `bossbar`(BossBar 색),
  `lines: {intro, phase2, phase3, death}`, `rotation: {페이즈번호: [패턴키…]}`, `sounds`, `arena` 에 보스별 배치 키
  (pillars/nests/platforms/valves/anchors/pylons/rune_shelves/corridor_length …). 패턴 params 공통 규칙(`*_base`·`*_per_member`·
  `*_per_members`·`*_pct`·`solo_*`·`p2_*`) = GDD §8.4. rotation 에 없는 패턴 키 = 상시 시스템/페이즈 트리거(GDD §8.3).
- **npcs.yml**: `role` 에 `lore`(층 휴식방 이야기 NPC) 추가, `nameplate`, `placement(overworld|floor)`, `floor`, `dialogue: [..]`,
  `shop: [{item, price, level_req?}]`(merchant), `skin_style` 에 `hair`, `accessories` (목록 = GDD §14.5, palette 6색 순서 고정).
- **titles.yml**: `category(pioneer|clear|challenge|combat|growth|collection|craft|pvp)`, `hidden`, `reward: {gold, items: {id: 개수}}`.
  condition 파라미터: CLEAR `{floor, count?}`, NO_DEATH_CLEAR `{floor, party_min?}`, DIFFICULTY_CLEAR `{floor, difficulty}`,
  SPEED_CLEAR `{floor, seconds}`, KILL `{count, mob?, rank?}`, BOSS_KILL `{count, boss?}`, LEVEL `{level}`, OBTAIN_RARITY `{rarity, count?}`,
  CRAFT `{count, rarity?}`, PVP_WIN/PVP_STREAK `{count}`, PVP_RATING `{min}`. `bonus` 키 = 스탯 6종 + `xp_bonus`, `gold_bonus`.
- **fx.yml**: `auras.<id>`: `tier(legendary|mythic)`, `particles[]: {type, count, radius, height, pattern, chance?, speed?, color?, color_to?, size?}`
  (color 류는 DUST/DUST_COLOR_TRANSITION 전용), `ring_scale`, `ring_height`, `ring_step`, `secondary_model`, `secondary_spin`,
  `secondary_mode(ring|back)`, `interval`(틱), `swing`. `models.<name>`: `motif`, `shape`(projectile), `frametime`, `size: [w,h,d]`(px),
  `flat`, `billboard(FIXED|CENTER|VERTICAL)`, `glow`. 아우라마다 `<id>_ring`/`<id>_slash`/`<id>_orb`/`<id>_burst` 모델이 있다
  (무기 스킬 `params.fx` 용). style/motif 목록 = GDD §14.4.

### 6.2 아이템·루팅·제작·PvP 단계에서 추가된 필드 (items/loot/recipes/arenas/titles/fx)
모두 **추가** 필드이며 닫힌 목록과 해석은 GDD.md 에 있다(§번호 표기). 생략한 필드 = null / 기본값.

- **items.yml**
  - `floor`(1~10): 장비가 속한 층 단계 — loot `rarity_pool` 후보 기준(GDD §11.10). 재료는 정보용(획득 층).
  - `pool`(기본 true): false 면 rarity_pool 이 뽑지 않음(보스 전용·제작 전용·칭호 보상).
  - `sources`: 획득처 목록 `drop | elite | boss | chest | craft | reward | shop` (툴팁 "획득처"·도감용, 콘텐츠 생성 시 계산해 적음).
  - `armor_slot: offhand` = 방패(수호기사). 보조손에 있을 때만 스탯 적용, `block_chance` 로 막기(GDD §11.2).
  - `stats` 키 = GDD §11.7 닫힌 목록 26개(`damage`, 스탯 6종, hp, mp, defense, crit_chance, crit_damage, attack_speed, move_speed,
    cooldown_reduction, skill_damage, mana_regen, hp_regen, heal_power, lifesteal, damage_reduction, evasion, block_chance, gold_bonus,
    xp_bonus, craft_discount). 값은 전부 [최소, 최대].
  - `weapon_skills[].id` = GDD §17.2 의 17개 구현 id **또는 `mechanics`**(조합형, GDD §17.5): 항목에 `mechanics: [부품…]` 목록을 두면
    파서가 `params.mechanics` 로 옮기고 `items/weaponskills/MechanicsEngine` 이 실행한다(부품 cone/nova/projectile/beam/dash/leap/blink/
    rain/strike/chain/zone/orbit/vortex/summon/self/target/party/repeat/delay/sound/particle/velocity/say, 효과 damage/percent/ignite/…).
    선택 `params.power`(전체 배율). 활의 `SNEAK_RIGHT` = 웅크리고 당겨 쏘기(EntityShootBowEvent, 당김 세기 = 위력).
    `params.damage_type` = melee | ranged | magic (DamageContext 피해 유형).
    `params.buff`·`ally_buff` 키 = GDD §11.7 버프 키.
  - `use`(consumable): `{action, amount?, duration?, buff?, cast_time?, cast_time_safe?, cancel_on_damage?, confirm?, auto?, invulnerable?,
    cooldown, cooldown_group}`, action = `heal | mana | restore | cleanse | buff | return | stat_reset | revive` (GDD §11.9).
  - `texture.style`/`effect` 에 아이콘 무늬 8개·effect 8개 추가(GDD §14.2), `model.shape` 는 기존 §14.1 목록 그대로.
  - `sets.<id>.look`: heavy | light | cloth — 장비 에셋 레이어 실루엣(GDD §14.7). `bonuses` 키 = 착용 개수(이상).
- **loot.yml**
  - 최상위 `settings: {own_class_bias, luck_per_point, party_bonus_per_member, max_chance, rarity_weight: {난이도: {희귀도: 배율}}, announce_rarity}`.
  - 테이블 `guaranteed: [{item, amount}]`(배율 무관 확정 지급), `gold: [min, max]`(상자 골드).
  - 항목 종류 추가: `{one_of: [id…], chance}`, `{table: id, chance}`(순환 금지). 공통 선택 키 `min_difficulty`. 해석 = GDD §11.10.
- **recipes.yml**: `category`(weapon | armor | accessory | material — 대장장이 GUI 탭), `amount`(결과 개수, 기본 1).
- **arenas.yml**: `description`, `theme`, `height`, `palette.liquid`, `layout_params`, `team_size: [min, max]`, `weight`,
  `spawns: {distance, protect}`, `hazards[]` 종류별 파라미터(닫힌 7종), `objective: {type: altar_control, …}`,
  `lava_contact`, `void_fall`, `ambient`. `pvp` 블록 추가 키: `enabled`, `prep_time`, `between_rounds`, `team_size`, `max_size_diff`,
  `challenge_timeout`, `min_level`, `queue`, `sudden_death`, `arena_pick`, `rules` 확장(shield_mult, cc_immunity, knockback_mult, execute_mult,
  stealth_reveal_on_damage, revive, title_bonuses, weapon_skills, friendly_fire), `gear: {mode: full|soften|flat, soften}`,
  `rating` 확장(k_placement, placement_matches, floor, uneven_k_mult, season_reset, tiers), `rewards`, `spectate`, `afk`. 해석 = GDD §18.
- **titles.yml**: condition 선택 키 `server_first: true`(PVP_FIRST_WIN · PVP_RATING — 서버 최초 1팀/1명, records.yml). PVP_RATING 은 개인 레이팅 기준.
- **fx.yml**: 전설 아우라 9종(soulfire, codex, geode, inkblot, abyssal, voltaic, quicksilver, aurora, venom)과 각자의 `_ring/_slash/_orb/_burst`,
  무기 스킬 전용 모델(`*_arrow`, `*_beam`, `venom_knife`). motif 9개 추가(GDD §14.4).

### 6.3 UI 단계에서 추가된 필드 (glyphs.yml)
- 글리프 `advance`(px, 생성기가 PNG 와 대조 — Java `GlyphDef.advance()` / `Glyphs.advance(id)`, 없으면 −1).
- 최상위 `menus.<id>: {glyph, rows, title, title_color, slots: {이름: 슬롯 | [슬롯…] | "설명"}}` — 배경 그림의 소켓 위치.
- 최상위 `hud: {total, bar_steps, bar_width, hp_x, badge_x, mp_x, shield_x, xp_x, status_x, gold_right, digit_advance,
  digit_chars, digit_names, draw_order, party_bar_steps, damage_digits}` — 액션바 조합 수치(§2 UI 글리프).
  YAML 키에 `.` 금지(Bukkit 경로 구분자 → 로더 무한 재귀) — 그래서 숫자 매핑은 `digit_chars`/`digit_names` 두 목록.
- 글리프 이름 접두어: `gui_` 배경 · `hud_` 바·배지·골드 · `hud_num_`/`gold_num_` 숫자 · `status_` 상태 · `party_` 파티 ·
  `dmg_`/`crit_` 피해 숫자 · `boss_` 보스바 장식. 글리프 문자는 U+E000~U+F3FF, U+F400~U+F8FF 는 공백 전용.

### 6.4 bosses 단계에서 추가된 필드 (bosses.yml — 전부 선택)
- 보스 최상위 `enrage`: 숫자(초) 또는 `{time}` — 광폭화까지 시간(기본 300 + 30 × 층, 0 = 없음). 광폭화: 주는 피해 +50%(+15초마다 +10%),
  패턴 쿨다운 × 0.6.
- `patterns.<key>` 공통 키: `weight`(스케줄러 가중치, 기본 1), `first_delay`(페이즈 진입 후 첫 사용까지 초, 기본 = 쿨다운/간격의 절반),
  `interruptible`(true 면 `interrupt` 상태이상으로 시전 차단).
- `arena` 4층: `platform_block`/`platform_base`(단상 블록, 기본 PRISMARINE_BRICKS/DARK_PRISMARINE), `valve_block`(기본 WAXED_OXIDIZED_COPPER).
- 보스 최상위 `hints`: 점진 힌트 단서 목록 `[흐릿, 조금 분명, 거의 정답]` (GDD §19.3, `Hints.bossClues(def)` = `def.raw().strings("hints")`).
  없으면 단서 없음, 리스트가 아니면 검증 오류, 3줄이 아니면 경고. MiniMessage(`<key:key.sneak>` 등) 가능.

### 6.5 config.yml `hints` (점진 힌트)
```yaml
hints:
  mode: progressive        # progressive | none | full
  thresholds: [2, 4, 6]    # 실패 횟수 경계 → 단계 1..3 (파티원 중 최댓값 기준)
```

## 7. 성능·안정성 규칙

- 블록 대량 배치는 틱당 상한(예: 4,000 블록)으로 나눠서. 층 생성 중엔 입장자에게 진행 표시.
- 반복 작업은 `BukkitRunnable`/스케줄러 하나로 묶기. 플레이어 없는 인스턴스는 30초 후 정리.
- 모든 이벤트 리스너는 `labyrinth_world` 여부를 먼저 확인해 미궁 밖에는 영향 없게.
- 서버 종료/리로드 시: 인스턴스의 플레이어를 입구로 귀환, 커스텀 엔티티 제거, 데이터 저장.
- 커스텀 엔티티에는 PDC 태그(`labyrinth:mob`)를 달아 서버 재시작 후 남은 것 청소.
- 예외로 서버가 죽지 않게: 패턴/스킬 틱은 try-catch 후 로그.

## 8. 테스트

- 순수 로직(경험치 곡선, 스탯 계산, 피해 공식, 배율, 루팅 확률, 미로 생성 연결성, YAML 로딩/검증, 점진 힌트 단계 `HintsTest`,
  미궁 게임 모드 규칙 `GameModesTest`)은 JUnit 5.
- `labadmin selftest` 는 층마다 기믹방 단서 3단계·보스 단서의 MiniMessage 읽기를 확인한다(`hints` 단계, `hint_gimmicks`/`hint_bosses` 개수).
- `./gradlew build` 가 테스트 포함 통과해야 함.
- `ContentValidator`: 모든 YAML 교차참조(아이템·몹·루팅·레시피·층·보스 id)가 유효한지 시작 시 + 테스트에서 검사.
- 리소스팩 생성기는 끝에 자체 검증: content 의 모든 아이템/몹 파트/NPC/글리프/fx 에 대응 파일이 있는지, JSON 파싱, PNG 크기.
