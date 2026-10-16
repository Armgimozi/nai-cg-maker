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
  tools/                 ← check_assets.py(에셋 id 대조) · maze_render.py · gen_enhance.py(content/enhance.yml 생성, §6.6) · build_world.sh …
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
- **어깨·등 3D 장식**: 상의(`armor_slot: chest`)가 있는 세트 `<set>` 마다 부위 `<part>` ∈ `shoulder_l | shoulder_r | back`
  (Java `items.ArmorPieceLayout.Part` 가 원본) → 아이템 모델 `labyrinth:armor_piece/<set>/<part>`
  - `assets/labyrinth/items/armor_piece/<set>/<part>.json`, 모델 `models/armor_piece/<set>/<part>.json`, 텍스처 `textures/armor_piece/<set>/<part>.png`
    (생성: `resourcepack/src/armor_pieces.py`, 검사: `validate.validate_armor_pieces` · `tools/check_assets.py`).
  - 등 부분 종류 = items.yml `sets.<id>.back` (`plate` 등판 | `quiver` 화살통 | `cape` 망토·두건 | `pack` 담요 말이·배낭), 없으면 look 기본값
    (heavy → plate, light → quiver, cloth → cape). 공용(모든 직업) 세트(novice·wayfarer)는 `pack`.
  - **투구 여유**: 세트마다 그 세트 투구의 팩 모델(CustomHeadLayer: translate(0,−0.25,0)·R180y·scale(0.625,−0.625,−0.625), `display.head` 항등 —
    목 위 (−0.625(x−8), 4+0.625(y−8), −0.625(z−8)) px) + 맨머리를, 목 축 기준 한 바퀴(머리 ±50° 회전을 덮음)·고개 −20°~+25°·서기/웅크리기로
    쓸고 지나간 부피에서 0.5px 안의 장식 복셀을 지운다(잘린 면은 테두리 색, 부스러기 제거). `validate` 는 투구·맨머리와 장식 요소의
    겹침 부피를 머리 yaw 0·±25·±50(서기)·0·±50(웅크리기)에서 재서 0.25px³ 넘으면 오류(통계 `armor_piece_helmet_overlap_px3`).
    견갑은 팔 바깥쪽 위로, 등판·망토·배낭 윗단은 어깨선 아래로 그려 잘리는 양을 줄였다.
  - **모델 계약**: 피벗 (8,8,8) = 부위 기준점, 모델 1단위 = 스킨 1px, `display.fixed` = 항등. 모델 −Z = 착용자 앞, −X = 착용자 왼쪽.
    기준점(발에서 스킨 px, 서기): 어깨 = 팔 회전축 (±6, 22, 0), 등 = 목 (0, 24, 0) — 몸통 갑옷 뒷면은 z −3.
  - **Java 배치**: `ItemsModule` 의 `ArmorCosmetics` 가 ItemDisplay 3개를 **플레이어의 탑승물**로 붙인다(FIXED, yaw = 몸 yaw,
    teleport_duration = update_ticks). 몸 yaw 는 서버 `getBodyYaw()` 가 아니라 `ArmorPieceLayout.BodyYaw` 로 매 틱 직접 계산한다 —
    Paper 26.3 은 `ServerGamePacketListenerImpl.tickPlayer` 가 `doTick` 직전에 xo/zo 를 현재 위치로 맞춰 서버 몸 yaw 가 이동 방향을
    안 따라간다(머리 ±50° 제한·팔 휘두르기에만 반응). `BodyYaw` = 바닐라 클라이언트 계산(이동 방향 목표 · 뒷걸음 반대 · 휘두르기 6틱 동안
    보는 방향 · ×0.3 · 머리와 50°(막기 15°) 제한 · 4블록 넘는 이동은 보는 방향으로 초기화), 패킷은 update_ticks 마다 바뀌었을 때만. Transformation = `ArmorPieceLayout.place(part, stance, SCALE 속성)` — translation = 좌석(서기 1.8 / 웅크리기 1.5
    블록) 기준 부위 기준점, 회전 = X축 숙임(웅크리기 팔 0.4 · 몸통 0.5 rad), scale = 0.9375. 표의 `// @layout-table` 줄은
    `resourcepack/preview_armor.py` 가 그대로 읽어 미리보기를 그린다(형식 유지, `ArmorPieceLayoutTest` 가 확인).
  - 착용자에게는 기본으로 `hideEntity` (스폰 전에) — 서버는 1인칭/3인칭을 모르므로 **혼자서는 F5 로도 내 장식이 안 보인다**
    (`/미궁 장식 내화면 켜기` = ext `cosmetics.armor_pieces_self` 면 숨기지 않음). 착용자 시점 관전자, 착용자를 `hidePlayer`/`hideEntity` 로
    못 보는 시청자(`!viewer.canSee(wearer)` — 그 클라이언트엔 탈것이 없어 장식이 허공에 뜬다)에게도 숨김(update_ticks 마다 맞춤, 스폰 때는
    스폰 패킷 전에). 비영속 + `Keys.FX = armor_piece:<uuid>` 임시 태그(`ArmorCosmetics.isPiece`).
  - **플레이어를 다른 월드로 옮길 때는 `core.Teleports.to(p, loc)`**: Paper 26.3 `CraftPlayer#teleport0` 는 탑승물이 있는 플레이어의 월드 간
    teleport 를 이벤트 없이 false 로 거부한다(같은 월드는 탑승물이 따라옴). `Teleports.to` 는 월드가 다를 때만 탑승물을 먼저 내리고, 장식은
    월드 이동 뒤 다음 갱신 때 다시 생긴다. (다른 플러그인이 `Player#teleport` 로 월드를 옮기면 실패할 수 있다 — 그런 서버는
    `cosmetics.armor_pieces.enabled: false`.)
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
      관절형 form(새 몸 형태 단계): `segment`(몸 마디) = pivot 에서 뒤로, `wing`(날개 한 장) = pivot(어깨)에서 몸 바깥(pivot X 부호 쪽)으로,
      `neck` = pivot(목 뿌리)에서 앞·위로 — ModelRig 가 이 pivot 을 축으로 날개를 퍼덕이고 목·꼬리 사슬을 휘므로 지오메트리가 거기서 시작해야 한다.
    - **파트 붙음(ModelRig·BossRig = `RigMath.Skeleton`, GDD §14.3/§14.6)**: 회전 중심 = 파트 `joint`(없으면 pivot), 원점 위치 = J′ + R·(pivot − joint).
      anim `neck`·`tail_chain` 파트는 YAML 순서대로 사슬(마디 k 관절 = 마디 k−1 관절 + 누적 회전·(원래 관절 차)), 머리(이름 `head` + anim head,
      없으면 가장 큰 anim head 파트)는 목 사슬 끝에, anim `head` 인 다른 파트는 머리와 같은 회전·`jaw` 는 머리 회전 + 벌림으로 머리 관절을 따라 돈다.
      다리(`set` 으로 자른 다리 하나 = 파트 하나)는 관절 위치로 정한 위상으로 걷고(`RigMath.Gait` 가 갱신마다 이동 거리 ÷ 한 주기 거리만큼 위상을
      쌓음 — LabMob·Boss 는 그대로 moveSpeed 만 넘긴다), 디딘 발 높이로 몸 전체를 보정한다. 다리 아닌 파트 = 윗몸 무리(숨쉬기·기울기 한 중심).
      몸 전체(땅 보정·몸급 부유·보스 오버레이·피격·앞숙임·솟구침·사망)는 모든 파트에 같은 강체 변환 + 크기로 곱한다. 보스 시전 오버레이는
      `BossAnim.rig` → `RigMath.Overlay`(파트 로컬은 사슬 전에, 전체는 마지막) — 그래서 왕관·안경·독니도 머리를 따라간다.
      틱 비용은 그대로(파트 수만큼 사원수 몇 번 · 서 있으면 Transformation 이 같아 안 보냄). 미리보기: `RigPreviewDump`(RIG_DUMP) + `tools/rig_preview.py`.
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
    배경 14종: main(3줄), stats, class, party, setup(첫 서버 설정·난이도), entrance(층 선택), blacksmith, enhance(강화), titles, accessories(3줄),
    merchant, confirm(3줄), generic_6, generic_3.
  - **HUD 액션바**(글줄 y = 화면높이 − 72, 가운데 정렬): 핫바 왼쪽 끝 기준 x 0..181 로 배치하고 전체 advance 를 182 로 맞춘다
    (요소마다 space(x − 펜) + 글리프, 끝에 space(182 − 펜)). 위치·접두어는 glyphs.yml `hud:` 블록. HP 바(x0)·레벨 배지(x82)·
    MP 바(x100) = H−63..H−55, 경험치 줄 H−52, 상태 아이콘·골드 줄 H−76. 바는 21단계(`hud_hp_00..20` = round(비율×20)).
    숫자 `hud_num_*`/`gold_num_*` 고정폭 7(점·쌍점 4), 흰 바탕이라 color 로 물들일 수 있음. **액션바·보스바 글리프는
    `shadowColor(ShadowColor.none())`(MiniMessage `<!shadow>`) 필수** — 아니면 글자 그림자가 바 밑에 겹쳐 보인다.
  - **범용 배경** `gui_generic_1..6`: 전용 배경이 없거나 소켓 배치가 다른 메뉴는 같은 줄 수의 범용 배경을 쓴다(예전에는 1·2·4·5줄
    범용 배경이 없어 그런 메뉴가 바닐라 상자 화면으로 보였다). `gui_panel_*`·`gui_sock_*`·`gui_btn_*`·`gui_emblem_*` 는 예비(동적 소켓용).
  - **시전 막대** `cast_00..10`(64×7, H−61..H−55 위 빈 띠): `HudService#castBar(p, 글, 진행도, 틱)` → HUD 안 가운데. 취소·완료 `clearCast`.
  - **바닐라 화면 테마** (`resourcepack/src/vanilla_gui.py`, 원본 그림 복사 없이 같은 규격으로 새로 그림): `minecraft:gui/sprites/hud/`
    핫바·선택·보조손·십자선, `boss_bar/*`, `tooltip/background·frame`, `widget/button*`·스크롤바, `gui/container/` 플레이어 인벤토리·
    상자 3·6줄·작업대·화로·발사기·셜커 상자. **등급별 툴팁**: 미궁 아이템(`GearItemService`·`BasicItemService`)에
    `tooltip_style = labyrinth:<등급 id>` → `labyrinth:gui/sprites/tooltip/<등급>_background·_frame` (일반~신화 테두리 색, 영웅 이상 보석 장식).
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
  `preview_ui.png`(GUI 배경 15종 + 실제 슬롯 격자, HUD 액션바 조합 모의, 글리프 전체)·
  `preview_vanilla_gui.png`(바닐라 화면 테마·등급별 툴팁·보스바·버튼·핫바, 안내 글 + 시전 막대가 얹힌 HUD 모의).
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
| `pvp/` | **pvp** | `pvp/PvpModule` | `TargetFilter`(→`DefaultTargetFilter`: PvP 꺼짐 — 모듈이 config `pvp` 를 따르는 것으로 교체) |

- **자기 패키지 밖은 고치지 않는다.** 다른 서비스는 `services.xxx()` 로만 부른다 (필드에 저장 금지 — 나중에 교체됨).
  `LabyrinthPlugin`/`Services` 는 손대지 않아도 되게 되어 있다: 실제 구현은 자기 `XxxModule.enable()` 에서 setter 로 등록.
- 계약 인터페이스에 메서드를 **추가**해야 하면 소유자가 자기 패키지의 인터페이스·기본 구현을 함께 고친다 (기본 구현 클래스 이름 유지).
- 기본 구현은 전부 안전(아무것도 안 하거나 최소 동작)하며 처음 호출 시 `[미구현]` 경고를 한 번 남긴다 (`Log.notImplemented`).
- 모듈 enable 순서: core(janitor·records·data·stats·levels·combat·pack) → items → classes → mobs → dungeon → bosses → titles → ui → pvp
  → setup → commands. enable 안에서는 **앞 순서 모듈만** 확실히 준비돼 있다 (뒤 모듈은 런타임에 getter 로).
- 하위 명령: 각 모듈 enable 에서 `services.commands().addSubcommand("<루트>", Commands.literal(...))`.
  루트 = `lab`(미궁) · `party`(파티) · `stats`(스탯) · `class`(직업) · `title`(칭호) · `labadmin`(미궁관리, 권한 `labyrinth.admin`).
  인자 없는 루트 실행은 `MenuService.openXxx` 로 간다. core 가 이미 붙인 것: `lab enter|입장 [층]`, `lab leave|퇴장`(→DungeonService),
  `stats add|투자 <스탯> [양]`, `labadmin reload|give|setup|difficulty|level|xp|gold|points|info|pack`.
- **공용 규칙 (core 제공)**
  - 콘텐츠: `services.content()` → `content/` 의 불변 레코드(`ItemDef`, `MobDef`, `BossDef`, `FloorDef`, `LootTable`, `ClassDef`,
    `AchievementDef`, `NpcDef`, `AuraDef`, `FxModelDef`, `GlyphDef`, `RecipeDef`, `ItemSetDef`). 자유 파라미터와 추가 필드는
    `Params`(각 정의의 `raw()`/`params()`): `dbl/integer/str/bool/sub/maps`, GDD §8.4 규칙 `scaled(key, n)`·`phased(key, phase)`.
    reload 시 새 객체로 바뀌므로 오래 보관하지 말 것.
  - 피해: 모든 피해는 `services.damage().deal(DamageContext...)` 한 곳. `DamageContext.attack(player, target, 배율, type)`(공격력 기반),
    `raw(attacker, target, 원피해, type)`(몹·보스), `percent(attacker, target, pct)`(_pct·방어 무시). `.skill(id)`, `.pattern(id)`(회피 불가),
    `.knockback(s)`, `.noCrit()`... 결과(`dealt/crit/evaded/blocked/killed`)는 ctx 에. 치유는 `services.damage().heal(target, amount, true)`.
  - 피해 가로채기: `services.damage().addInterceptor(DamageInterceptor)` — 회피되지 않은 최종 피해를 적용 직전에 바꾼다
    (0 = "막음"). items 가 무기 스킬 무적·보호막(`LabWeaponSkillService#shield`)·방어 자세·자동 부활 소모품에 쓴다. 직업 보호막도 이걸로.
    순서: `addInterceptor(i, order)` — 작은 값부터(기본 0) → 천 마나 보호막 `ORDER_MANA_SHIELD`(50) → 자동 부활 `ORDER_LAST`(100).
  - 밀쳐내기: 플레이어를 미는 곳은 `services.damage().knockbackScale(target, from)` 을 곱한다 (1 − 밀려남 저항 = 힘 + 판금 4부위 버팀 +
    넉백 면역, 보스가 민 것은 1). DamageContext.knockback·상태이상 knockback·몹 스킬 push·무기 스킬 push·함정 톱날이 쓴다.
  - 커스텀 몹·보스 HP: `combat.HealthPool` 계약(`applyDamage` 에 최종 피해가 온다, HP 0 이면 구현이 사망 처리). 바닐라 근접·화살 → 몹,
    몹의 바닐라 공격 → 플레이어 연결은 core `CombatListener` 가 이미 한다(`MobService.byEntity`/`BossService.byEntity` 로 판별).
  - 플레이어 HP: 바닐라 체력 = min(최대 HP, 1024), 하트는 10칸 고정 표시. 직접 만지지 말고 `services.stats().currentHp/heal/setHp`.
  - 스탯 보태기: `services.stats().addContributor((player, block) -> block.add("defense", 5))` (장비·칭호·버프). 값이 바뀌면 `markDirty(p)`.
    StatBlock 키 = GDD §11.7 + 버프용 `damage_mult`(주는 피해 %, 버프 키 `damage` 를 이 키로), `damage_taken`(받는 피해 %).
  - 경험치: `services.levels().reward(player, base × ctx.xpMultiplier())` (xp_bonus 자동 적용). 레벨업 시 `LevelUpEvent`.
  - 배율: `InstanceContext.hpMultiplier()/damageMultiplier()/dropMultiplier()/goldMultiplier()/xpMultiplier()/windup(초)`;
    인스턴스 밖 소환은 `InstanceContext.adhoc(floor, n, settings.difficulty(), settings.party())`.
  - 이벤트(`event/`): `MobKillEvent`(mobs/bosses 발생), `FloorClearEvent`(dungeon), `LevelUpEvent`(core), `ItemObtainEvent`(items),
    `CraftEvent`(items), `EnhanceEvent`(items 강화) — titles 가 듣는다.
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
         RecipeDef, AchievementDef, NpcDef, AuraDef, FxModelDef, GlyphDef), Params(자유 파라미터), Rarity, ItemType,
         ContentParser(원시 YAML → 레코드, Bukkit 무관 — 단위 테스트)
event/   MobKillEvent, FloorClearEvent, LevelUpEvent, ItemObtainEvent, CraftEvent, EnhanceEvent
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
         EquipmentListener(장비 StatContributor + 세트 효과 + 겉모습 수 `look.<id>`·`look_body.<id>`), ConsumableListener,
         ItemGuardListener(바닐라 제작·화로·모루·거래 차단)
         방어구 겉모습 (0.3.5, look_spec): content/ArmorLook(heavy·light·cloth·plain·any, `ItemDef.armorLook()` — 파서가 단품 look →
         방패 판금 → 세트 look(look_effects: false 면 평상복) 순으로 정함) · 설정 core/ArmorLooks(config armor_looks) · 숨은 효과·4부위
         판정 stats/ArmorLookMath(순수, StatCalculator 가 부름 → DerivedStats lookCounts·fullLook·cooldownMult·ccResist·밀려남 저항) ·
         4부위 런타임 ArmorLookService(창구 `LookEffects` = `services.looks()`: 가죽 구르기 — 순수 TumbleInput, 구르는 동안
         DamageService 가 회피 100% · 천 마나 보호막 — 순수 ManaShield, 가로채기 50) · 판금 버팀은 combat/CrowdControl(순수).
         데이터 tools/data/035/armor_looks.json → tools/gen_035_looks.py (방어구 요구 짝 · 스탯 줄 이름 · look · look_effects)
items/weaponskills/ LabWeaponSkillService(입력: LEFT = PlayerArmSwingEvent, RIGHT = 우클릭, 쿨다운·마나·침묵),
         WeaponTargeting(무기 스킬 대상 선택의 단일 도형 헬퍼 — 적/아군 판정은 TargetFilter),
         SkillCast(공통 키 처리), Fx(ItemDisplay 이펙트), 17종 구현 = Projectile/Movement/Area/SupportSkills,
         조합형 `mechanics` = MechanicsEngine(실행) + mechanics/MechanicsSpec(순수 파서·검사, ContentValidator 가 호출)
items/unique/ 무기 고유 효과 26종 (0.3.5, unique_spec) — 창구 `UniqueEffects`(`services.unique()`, 기본 NONE), 구현 UniqueEffectService
         (DamageService.Hook + 1초 타이머: 손 무기의 `ItemDef.unique()` 하나, 요구 능력치 미달이면 꺼짐) + 순수 UniqueProcs(재발동·N번째·
         첫 타 창·중첩·기절 면역·장전). 정의 = content/UniqueDef · 닫힌 목록 content/UniqueCatalog(검사기·시험과 같은 표).
         배정 데이터 tools/data/035/unique_assign.json (tools/gen_035_unique.py, items.yml 에는 P3 가 넣음)
loot/    LootService(loot 테이블, 희귀도 가중치, LUK 보정, 파티 개인 루팅: 아이템은 개인별로 지급/표시)
         구현 items/loot: LootRoller(순수 굴림), LabLootService(주인에게만 보이는 아이템 엔티티, 줍는 순간 ItemObtainEvent·전설 알림)
crafting/CraftingService(+대장장이 GUI, 재료 확인/소모, 결과 지급) — 구현 items/crafting: RecipeCheck, LabCraftingService, BlacksmithMenu
enhance/ 강화(GDD §11.13) — EnhanceRules(순수: 확률·하락·보호·비용·강화석 구간·스탯 배율, config.yml enhance), Enhancement(PDC 코덱
         Keys.ITEM_ENHANCE + 현재 규칙 + 툴팁 줄), EnhanceService(확인·소모·판정·연출·방송, EnhanceEvent), EnhanceMenu(강화 창 —
         장비는 고르기만, 제자리에서 고침), EnhanceGlow(+10 은은한 빛). 스탯 배율은 GearItemService.rolledStats 가 곱한다
mobs/    MobDef, CustomMob(기반 엔티티 + 모델 리그 + HP 풀 + AI 상태), ModelRig(파트별 ItemDisplay, 보간 애니메이션:
         idle/walk/attack/hurt/death), MobService(스폰, 틱, 디스폰, 일반 몹 스킬 타입), mob skill 타입은 YAML 로 조합
bosses/  BossDef, Boss(추상: 페이즈·패턴 스케줄러), Pattern, Telegraph(원/선/부채꼴/링 장판 경고 + 판정), BossService,
         impl/Floor01Boss .. Floor10Boss (층별 고유 패턴·기믹)
dungeon/ DungeonService(입장/퇴장/진행), Instance(파티·층·난이도·배율·상태), InstanceAllocator(공허 월드 격자 슬롯),
         VoidGenerator(ChunkGenerator: 빈 월드), FloorGenerator(층 테마 팔레트로 방+복도 미로 생성, 시드 기반),
         rooms/*(전투방, 엘리트방, 보물방, 기믹방, 휴식방, 보스방), EntranceService(오버월드 입구: 지형 존중)
party/   Party, PartyService(생성/초대/수락/탈퇴/추방/위임, 파티 채팅, 최대 인원 config)
pvp/     파티 규칙 PvP (GDD §18 — 대전·투기장·레이팅 없음): 같은 파티원끼리는 어디서든 피해 없음, 그 밖의 플레이어끼리는 피해 가능.
         PvpRules(순수 적/아군 표 — 단위 테스트), TargetFilter·DefaultTargetFilter(엔티티 → PvpRules, 근접·화살·스킬·무기 스킬·
         장판의 단일 규칙), PvpSources(책임 플레이어: 투사체·TNT·엔드 수정·물약 구름·번개·길들인 동물), PvpConfig(config `pvp`),
         VillageZone(마을 안전지대 = 주 월드 폴더 labyrinth-village.yml center/radius, 없으면 없음), PvpListener(물약·잔류 구름·발화·
         늑대·낚싯대·바닐라 경로 배율·죽음 메시지·월드 PvP 규칙), PvpModule(DamageService 훅: 파티원 피해 차단·배율·한 방 상한,
         1초마다 파티원 이름표 초록·모든 월드 게임 규칙 pvp = pvp.enabled)
titles/  Achievement(titles.yml), TitleService(사건 판정 → 칭호마다 주인 한 명(records.yml), 주인 방송, 칭호 장착: 채팅·탭·이름표 접두어, 소소한 보너스)
npc/     NpcService(npcs.yml: 안내인/대장장이/전직관/칭호관리인… Mannequin + 커스텀 스킨, 우클릭 → GUI)
ui/      Menu 프레임워크(InventoryHolder 기반, 커스텀 폰트 배경 타이틀, 버튼 콜백), menus/*(초기 설정(난이도), 스탯, 직업, 파티, 입장(층 선택),
         대장장이, 칭호, 장신구), HudService(액션바: HP/MP 바·레벨·골드, 사이드바: 층·남은 적·파티원 HP, 보스바)
pack/    PackService(HTTP 서빙 + 전송)
command/ CommandService(Paper Brigadier: LifecycleEvents.COMMANDS)
```

### 4.1 classes 단계에서 추가된 계약 (다른 모듈이 쓰는 것)
- **피해 훅** `combat.DamageService.Hook` (`services.damage().addHook(h)`): `before(ctx)`(원피해 직후 — `ctx.amount/threat/critBonus` 조정),
  `absorb(ctx, dmg)`(적용 직전 — 보호막·피해 분담 후 남은 피해 반환), `after(ctx)`(적용 후 — 적중 효과). `DamageContext.critBonus(x)`
  = 이 피해의 치명타 확률 가산(≥1 확정). classes 가 상태이상·보호막·패시브에 쓰고, pvp 가 플레이어끼리 배율·한 방 상한에 쓴다.
  `allow(ctx)`(맨 처음 — false 면 피해 자체를 취소, 숫자도 안 뜸): pvp 가 같은 파티원끼리의 피해(늦게 도착한 지속 피해 등)를 막는다.
  `evaded(ctx)`(회피됐을 때, after 대신 — 고유 효과 흘려치기). `ctx.isBasicAttack()` = 무기로 친 한 대(출처 없음·스킬·패턴 아님),
  `ctx.critDamageAdd(x)` = 이 피해의 치명 피해 가산. 고유 효과가 낸 피해 sourceId = `unique:<id>` — 어떤 고유 효과도 다시 켜지 않는다.
  방어 깎기(갑옷 부수기)는 DamageService 가 `services.unique().defenseShred(target)` 로 방어에 곱한다(상한 40%).
  `services.damage().isApplyingVanilla()` = 지금 미궁 피해의 사망 처리(바닐라 damage 호출) 중 — 다른 리스너는 그 피해를 다시 가로채지 말 것.
- **StatusEffectService**(`classes.LabyrinthStatusEffectService`): GDD §9.2 14종 + `venom`(중첩 독) · `mark`(받는 피해+) · `cooldown_slow` ·
  `interrupt`(보스 시전 끊기 신호). 확장 메서드: `addShield/shield`, `stealth/isStealthed/breakStealth`, `isKnockbackImmune`, `cooldownRate`,
  `removeBuff/hasBuff`, `clearAll`. 이동 제한은 속성 수정치로 자동. **mobs/bosses 는 AI·스킬·패턴 전에 `isStunned` 확인**, 은신 대상 제외,
  밀쳐내기는 `isKnockbackImmune` 확인. 몹·보스의 weaken/vulnerable/mark 는 훅이 직접 곱하므로 `HealthPool.damageTaken()` 에 더하지 말 것.
  보스는 stun/root/빙결 면역(스킬은 boss_* 값 사용). 지속 피해 sourceId = `effect:<id>` (적중 효과에서 제외용).
  고유 효과용 확장: `applyStacks`(중첩 출혈·독 = 따로 쌓이는 층 bleed_stack·poison_stack, `has("bleed"/"poison")` 에 함께 잡힘) ·
  `applyFrost`(5중첩 빙결 1초, 보스는 받는 피해 증가 3초). 스킬 사용 뒤 `services.unique().onSkill(p)`(직업·무기 스킬 모두).
- **ClassService** 확장: `changeClass(p, id)`(전직관 NPC·직업 메뉴·`/직업 선택` 이 부를 것 — 검사·안내·연출 포함), `skillBar(p)`(HUD 용 스킬 한 줄), `isChanneling(p)`.
  **직업 변경 제한**(GDD §4.5): 모든 `changeClass` 구현은 `classes.ClassChangeGate` 하나를 거친다 — 순수 판정 `ClassChangeRule`
  (첫 선택 무료 · 그 뒤 `class_change_scroll` 1장 · 바꾼 뒤 `cooldown_hours`(첫 선택은 세지 않음) · 미궁 공략 중 금지 · 같은 직업), 통과하면 두루마리 1장 소모 →
  적용 → PlayerData ext `class.changed_at`(epoch ms) 기록. 직업 메뉴·`/직업 정보` 도 같은 판정으로 규칙·남은 시간·가진 두루마리를 보여 준다.
  config.yml 최상위 `class_change: {require_item, item, cooldown_hours}`(키 없으면 true · class_change_scroll · 24, `class_change: false` = 제한 없음).
  관리자 강제 변경 `/labadmin setclass <플레이어> <직업|none>` 은 관문·기록을 건드리지 않는다. 다른 모듈은 `setClass` 를 직접 부르지 말 것.
  무기 스킬(items)은 `services.effects().isSilenced(p)` 와 `cooldownRate(p)` 를 확인할 것.
- **DungeonService** 기본 메서드: `isDowned(p)`, `revive(p, at, hpRatio)`(사제 부활의 성가) — dungeon 구현은 자기 사망 상태와 맞게 재정의.
- 직업 스킬은 **아무 미궁 무기**(type: weapon, 종류 무관)를 들었을 때 발동 — 바닐라 무기는 해당 없음(F/Q 바닐라 그대로).
  classes.yml weapon_types = **추천 무기**: 들면 직업 스킬 재사용 대기 −10%, 직업 스킬 피해는 무기 종류 배율을 추천 무기 기준으로 환산
  (`SkillContext.damage`·`dotRatio` 가 자동 적용 — 새 직업 스킬은 피해를 `c.damage(...)`, 지속 피해 potency 를 `c.dotRatio(...)` 로 낼 것).
  규칙 원본 = `content.WeaponTypes`(순수, GDD §4.4). 명령: `/직업 선택|choose <직업>`, `/직업 정보|info`, `/직업 스킬|skills`.
- **장비 직업 제한 없음**: `ItemDef.usableBy` 는 항상 true, `EquipRules` 는 요구 능력치만 본다. 0.3.5 부터 장비에는 `classes` 가 없다
  (`ItemDef.suitedFor` 는 늘 true) — 드롭 편향은 요구 능력치로 (`LootRoller` own_build_bias). 다른 모듈도 착용 가능 여부를 직업으로 막지 말 것.

### 4.2 ui+titles 단계에서 추가된 계약 (다른 모듈이 쓰는 것)
- **MenuService** 실제 구현 `ui.LabMenuService`(상자 GUI, `ui/menus/*`; 열다가 오류 나면 채팅 메뉴로 대체). 기본 메서드 추가:
  `openBlacksmith`(→ CraftingService GUI) · `openMerchant`(npcs.yml `role: merchant` 의 ShopMenu).
  `/미궁 메뉴|장신구|대장간|상점|기록` 하위 명령. 메인 메뉴 24번 칸 = "PvP 규칙" 안내(클릭 = 파티 메뉴).
  메뉴는 다른 모듈 기능을 **명령으로 위임**한다(검사·메시지 일관): 파티 `party create|invite|accept|decline|kick|promote|disband|leave|chat`.
  초기 설정 GUI 확정 = `labadmin setup <난이도>` + config `entrance.mode`, "여기에 설치" = `labadmin setentrance <block|npc>`.
- **HudService** 실제 구현 `ui.LabHudService`: 액션바(0.25초 검사, 바뀐 때만 + 2초 유지 재전송) HP·MP·경험치 막대·레벨·골드,
  미궁 사이드바(층·난이도·인원·정복한 방·타이머·사망·파티원 HP), 플레이어마다 개인 스코어보드(이름표 팀 접두어 = 칭호).
  기본 메서드 추가: `nameTagPrefix(target, prefix)`, `nameTagColor(viewer, target, color|null)` — 보는 사람별 이름표·탭 이름 색
  (칭호 접두어와 같은 대상별 팀을 쓴다). pvp 가 1초마다 파티원을 초록으로 맞춘다.
- **DungeonService** 기본 메서드 `floorProgress(p)` → `FloorProgress(floor, roomsCleared, roomsTotal, deaths, startedAt, bossDefeated,
  ready, progress)` (HUD 용; 전투·정예·시련·수호자 방만 셈). dungeon 담당이 더 정확히 재정의해도 된다.
- **DungeonService** 기본 메서드 `showMap(p)` — 채팅에 지금 층 탐험 지도(파티가 지나간 셀만)를 그린다. 미궁 밖이면 안내 후 false (메인 메뉴 버튼이 호출).
  미로 정보(GDD §5.4): `FloorLayout.deadEnds()`·`hallTiles()`·`secretRooms()`·`mainPathCells()`·`rooms()`, 금 간 벽 열림 콜백 `FloorState.secrets().onOpen(...)`.
  floors.yml 층별 `maze:` 키(`dead_end_keep`·`loop_chance`·`branch`·`braid`·`twist`·`secret_ratio`·`secret_max`·`min_path`)와 `palette.secret`·`palette.stairs`.
- **함정·미로 보물** (GDD §5.5·§5.6): 패키지 `dungeon.traps`(`TrapType` 닫힌 13종·`TrapPlanner`·`TrapMath` 순수, `Traps` 런타임)와
  `dungeon.treasure`(`TreasurePlanner`·`ChestLedger`·`VaultKeys` 순수/도우미, `Treasures` 런타임). 배치는 `traps.HazardPlan.plan(layout, traps, chests, seed)`
  하나(보물 → 함정 → 함정 뒤 금 상자) — FloorState·테스트·MazeRenderDump 공용. 런타임 접근 `FloorState.traps()`·`treasures()`,
  정예방 정리 → `treasures().onEliteCleared(room)`(열쇠), 블록 상호작용은 DungeonManager 가 `treasures().onInteract` 먼저 묻는다.
  floors.yml 층별 `traps: {density, types, mark, spacing}`·`chests: {dead_end, minor, iron, gold, gold_behind_trap, mimic, vault, key_from_elite, bracket}`,
  dungeon.yml `traps.*`(disarm_seconds·shadow_disarm_seconds·shadow_sense_radius·disarm_gold·disarm_xp)·`treasure.mimic_lock_seconds`
  → `DungeonConfig.traps()`(TrapRules). loot.yml 미로 상자 = `treasure.ChestTier.table(층, chests.bracket, 존재)`: bracket 강제가 없으면 층별 표
  `maze_chest_<wood|iron|gold>_f<층>`(있을 때), 아니면 구간 표 `maze_chest_<tier>_<1~4>`(층 구간 1~3·4~6·7~9·10 — 여러 층 공용이라 장비 없음). 검사기·도감도
  같은 함수로 실제로 굴릴 표를 고른다. + 철·금 상자 강화석 `maze_enhance_<iron|gold>_t<1~3>`(강화석 구간 1~3·4~7·8~10, 상자마다 따로 한 번), items.yml `vault_key`(type key,
  PDC "런id#층" — `Run.restore`·`Run.begin`(입장자)·`DungeonManager.recoverStranded`·다음 층 첫 도착 때 지움). titles.yml 조건 `TREASURE {kind: chest|gold_chest|vault|mimic, count}` —
  카운터 `titles.treasure.<kind>`. PlayerData 카운터 `dungeon.traps_disarmed`. 자가 진단 결과에 `traps=·chests=·vaults=·secret_rooms=·mimics=`.
- **TitleService** 실제 구현 `titles.LabTitleService`. 기본 메서드 추가: `setBonusSuppressed(p, on)`(칭호 스탯 보너스 잠시 끄기 — 지금은 부르는 곳 없음),
  `progress(p, id)`. 판정은 `titles.AchievementRules`(순수, 테스트), 카운터 갱신은 `titles.TitleCounters` —
  카운터 키 `titles.*` 목록은 AchievementRules 문서가 원본. 서버 기록 키: `first_clear.floor_<n>`(층 최초 돌파 파티 전원),
  `speed.floor_<n>`(최단 시간), `title.<업적 id>`(server_first 업적). 첫 칭호는 자동 장착. 채팅 = AsyncChatEvent 렌더러
  `[칭호] 이름 » 메시지`(취소된 파티 채팅은 건드리지 않음), 탭 목록 이름 = 접두어 + 이름.
  명령: `/칭호 장착|해제|목록|기록`, `/labadmin title grant|revoke <플레이어> <id>`, `/labadmin title recheck`.
- **UI 글리프 이름 (pack-ui 단계가 glyphs.yml 에 이 이름으로 넣으면 자동 적용, 없으면 글리프 없이 동작)**:
  - 메뉴 배경 `gui_<메뉴>`: main · stats · class · class_detail · party · players · titles · records · entrance · setup · accessories ·
    blacksmith · enhance · merchant (없으면 `gui_rows_<줄 수>`). 6줄 메뉴 = 54칸, 5줄 = 장신구·상점.
    선택 필드(glyphs.yml 항목에 추가 가능): `width`(배경 폭 px, 기본 176), `title_x`(제목 글자 시작 x, 기본 8), `title_color`(#RRGGBB,
    기본 #3b2a4d). 배경 글리프는 펜을 −8 당겨 컨테이너 왼쪽 끝부터 그린다 → ascent 는 제목 줄 기준(바닐라 상자 제목 높이)으로 맞출 것.
    글리프 배경이 있으면 빈 칸을 유리판으로 채우지 않는다(배경 그림이 보이도록).
  - HUD 막대 kind = `hp` · `mp` · `xp`: 프레임 방식 `hud_<kind>_0..N`(채움 단계별 한 장) 또는 칸 방식 `hud_<kind>_full|half|empty`
    (hp 10칸, mp 8칸, xp 6칸; 옛 이름 `<kind>_bar_full|half|empty` 도 인식). 아이콘 `hud_hp_icon · hud_mp_icon · hud_level_icon ·
    hud_gold_icon`. 액션바 줄 높이에 맞는 ascent 로 만들 것.

### 명령어
- 플레이어: `/lab`(별칭 `/미궁`: 입장 메뉴·퇴장·정보·`강화`), `/party`(`/파티`), `/stats`(`/스탯`), `/class`(`/직업`), `/title`(`/칭호`).
  PvP 명령은 없다(파티 규칙, GDD §18).
- 관리자(`labyrinth.admin`): `/labadmin reload|give <item> [player]|spawnmob <id>|mobdrill <몹…|all|f<층>>|spawnboss <floor>|setentrance|removeentrance|
  setnpc <id>|tpfloor <n>|unlock <player> <floor>|reset <player>|instances|endinstance <id>|pvp`(PvP 규칙·안전지대·월드 규칙 상태)
  (items 가 붙임: `blacksmith [player]`(대장간 GUI) · `loot <table> [player]`(개인 루팅 테스트) · `weaponskills`(구현 목록) ·
  `enhance <단계> [player]`(주손 장비 강화 단계 바로 설정). 플레이어: `/미궁 강화|enhance`(강화 창))

### 스킬 입력 (미궁 무기를 들고 있을 때 — 종류·직업 무관)
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
  0.3.2: 솔로·2인 몹 수 `party_mob_count` + 보상 보정 `party_mob_reward` · 방 정리 회복 `room_clear_heal` · 층 첫 돌파 보너스 `first_clear_bonus` (§6.7).
- **공허 월드 좌표**: 미궁 인스턴스는 `InstanceAllocator` 슬롯(간격 2048, **z ≥ 2048** 영역)만 쓴다. **다른 모듈이 공허 월드에 무언가 지어야 하면 z < 0 영역을 쓸 것.**
  층 n 의 바닥 y = `top_floor_y − (n−1) × floor_spacing` (기본 280, 30 → B1 y280 … B10 y10). 같은 슬롯에서 아래층일수록 실제로 낮다.
- **인스턴스 id**: `InstanceContext.id()` = `r<번호>s<슬롯>-<세션>-b<층>` (세션 = 플러그인 활성 시각 36진수 — 재시작 뒤 run id 가 다시 나오지 않음. 층마다 새 컨텍스트, 같은 Run 의 배율·난이도 유지). 몹·보스 정리는 이 id 로.
- **보스방**: 원형 투기장(bosses.yml `arena.radius/height`, `shape: circle|clock_face|tiled_circle` 바닥 무늬, `corridor_length/width` 면
  중심에서 **+z 방향**으로 추격 복도, `rim_radius` 면 복도 끝에 원형 단 + 바깥 `FloorGenerator.RIM_MOAT`(3)칸 고리 —
  단 중심 z 오프셋 = `FloorGenerator.rimCenterOffset(radius, corridor_length, rim_radius)`, 고리는 바닥으로 깔고 보스가 비운다). 입구는 북쪽(−z). `spawnBoss(floor, 중심, ctx)` 의 중심 = 바닥 위 1칸. 보스 구현이 투기장에 놓은 블록은
  층 정리 때 원기둥(바닥 아래 2칸~천장) 전체를 비우므로 따로 안 지워도 된다. null 이면 층 정예 몹을 HP×`boss_fallback.hp_mult` 로 대신 세운다.
  보스 처치 후 투기장 중심 남쪽에 아래층 계단이 생긴다(중심 +2~+11 z 칸을 비워 둘 것).
- **이벤트**: 보스 처치 시 `FloorClearEvent`(참가자 전원, 입장 인원, 그 층 사망 수, 그 층 소요 초, 서버 난이도). 해금층 = 깬 층+1.
  PlayerData counters: `dungeon.floor_clears`, `dungeon.clear_floor_<n>`, `dungeon.solo_clears`.
- **사망**: 미궁 안 PlayerDeathEvent 는 취소되고 관전 모드(휴식방 도달·보스 처치 시 부활). 전원 쓰러지면 전멸 → 귀환.
  PvP 로 쓰러져도 똑같다(파티를 나간 사람이 같은 인스턴스에 남으면 규칙대로 적 — GDD §18.5).
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
- **아레나가 옮겨 가는 보스**(10층): `Boss#relocate(위치)` = 전투 중심(`center` — 경계·`randomPoint`·관전자·`bossAt` 기준) 이동 + 순간이동,
  `blockAllowed(Block)` 를 넓히면 원 밖(추격 복도·가장자리)에도 `setBlock`, `validPlayer` 를 재정의하면 판정 구역을 넓힌다.
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
- 7층 보스 단계 추가: `Boss.setBarColor(색)`(전투 중 보스바 기본 색 바꾸기 — 극성 얼굴), `BossRig.partLight(파트, 밝기, 발광색)`(모델 일부만 강조).
  공격자별 피해 배율·반사처럼 "누가 때렸나"가 필요한 규칙은 `services.damage().addInterceptor` 로 보스 히트박스 대상만 걸고 `onEnd` 에서 해제
  (`impl/Floor07Boss`). 보스 개인 막대는 `hud().showBossBar(p, "boss_polarity", …)` 처럼 `boss_` 접두어 키를 쓴다.

### 통합·배포 메모 (integration-release 단계)
- **메뉴 배경 규칙** (`ui.UiTheme.background(menu, rows)`): 메뉴별 배경 `gui_<menu>` 에는 버튼 소켓이 그려져 있으므로 **버튼 배치가
  glyphs.yml `menus.<id>.slots` 와 같은 메뉴만** 전용 배경을 쓴다(현재 blacksmith · enhance · titles · setup · class · party — `SOCKET_LAYOUT`). 나머지는 같은 줄 수의
  `gui_rows_<n>` → `gui_generic_<n>`. 배경 높이로 줄 수를 계산해 줄 수가 다르면 절대 쓰지 않는다(5줄 메뉴 = 배경 없음 + 테두리).
  메뉴를 소켓에 맞게 고쳤으면 `SOCKET_LAYOUT` 에 id 를 추가할 것. 제목 색 = `menus.<id>.title_color`.
- **글리프 액션바** `ui.GlyphHud`: glyphs.yml `hud:` 수치대로 xp·hp·(보호막)·mp 바(`hud_*_00..20`), 레벨 배지·숫자, 상태 아이콘(`status_<효과>`,
  StatusEffectService#has), 골드 줄을 배치하고 전체 advance 를 `hud.total` 로 맞춘다(그림자 끔). 필요한 글리프가 없으면 텍스트 HUD.
  **안내 글이 있어도 HUD 는 사라지지 않는다**: `actionBar(p, 글, 틱)`·`castBar` 의 글은 HUD 위(바닐라 액션바 글줄) 가운데에 함께 그린다 —
  `LabHudService.withMessage` = `[글][space(−91 − m/2)][HUD 182][space(+4096)][글 사본][space(−91 − m/2 − 4096)]`
  (m = `ui.TextWidth` 추정 폭; 화면 밖 사본이 실제 폭과 상쇄되어 추정이 틀려도 HUD 위치는 그대로, 글만 몇 px 비킨다).
  사이드바 파티원 줄 = `party_class_<직업>` + `party_hp_00..10`. 보스바 이름 양옆 = `boss_ornament_left/right`.
- **자가 진단** `/labadmin selftest [층 수]` (`dungeon.SelfTest`, 콘솔 가능): 아이템 전부 생성·역조회 → 도감 획득처 계산 → 임시 슬롯에 층 생성 →
  몹·정예 정의 전부(+정예 변종) 소환·피해·처치 → 1~5층 보스 + 구현 없는 층 대체 보스 소환·페이즈 피해·처치 → 정리. 진단 중 로그의
  SEVERE/예외를 하위 시스템(`kr.labyrinth.<패키지>`)별로 센다. 새 보스·몹을 넣으면 이것부터 돌릴 것.
  보스가 기믹으로 무적이면(빙결 껍질 등) 처치 단계가 아레나의 기믹 오브젝트(BossHandle 인 인장·알…)를 먼저 깨고 1초마다 다시 시도한다(최대 40회).
- **몹 스킬 훈련** `/labadmin mobdrill <몹 id…|all|f<층>>` (`mobs.MobDrill`, 콘솔은 `execute positioned … run labadmin mobdrill …`):
  그 자리에 몹 + 6칸 앞 허수아비(무적 갑옷 거치대)를 세우고 능동 스킬을 하나씩 강제로 시전(거리·시야 조건 무시, 경고·판정은 그대로) →
  피해(분노 임계)·처치(사망 스킬) → 소환물·허수아비 정리. 자가 진단은 플레이어가 없으면 스킬을 한 번도 안 쓰므로, **새 몹·새 스킬은 이걸로 확인**.
  로그 `[몹 훈련] 결과: 예외 0 · 몹 n/n · 시전 … · 허수아비 적중 …`. 스킬 대상은 `LivingEntity`(플레이어 또는 허수아비) — 광역 판정은 `LabMob.victimsNear`.
- **도감** `/codex` = `/도감` = `/미궁 도감` (`ui.menus.CodexMenu`): 종류·희귀도별 아이템(실제 툴팁 + 획득처: 몹/보스 드롭·보물 상자·기믹 방·
  제작 재료·상점·칭호 보상·시작 지급 — loot 테이블 중첩·PICK 까지 계산. 층 섞음 표 `mix_fNN_drop`(0.3.4 `gear_fNN_common`)은 따라 들어가지 않고 "몬스터·상자 지하 N층" 한 줄,
  `special_trial_fNN`·`hoard_fNN` 은 "특별 시련"·"금고·미믹" 묶음 (0.3.5 P3 임시 — P6 가 층 없는 글로 바꿈),
  층별 미로 상자는 `ChestTier` 규칙으로 실제로 굴리는 표를 보물 상자로), 몬스터·보스(모델 머리 아이콘·능력치·드롭, 수치는 "(보통·보정 전)").
  획득처 그룹 순서(장비) = 보스 · 정예 · 몬스터·상자 · 제작 · 칭호 보상.
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
  각 직업 스킬 4개(3 + 궁극기), 레벨에 따라 해금. 직업마다 추천 무기 타입(장비 제한은 없음 — 누구나 모든 장비).
- 희귀도: 일반(흰) < 고급(초록) < 희귀(파랑) < 영웅(보라) < 전설(금, 아우라) < 신화(빨강, 애니메이션 아우라).
  **전설·신화 무기 텍스처는 프레임 애니메이션(.mcmeta, GIF 처럼 움직임)** + 들고 있을 때 파티클/링 아우라.
- 장비 획득 루트 (GDD §11.3, 0.3.5): 장비는 숨은 단계 `tier` 를 갖고, 보스가 아닌 장비는 단계 풀 `band_tNN_<종류>` 를 이웃 층 셋이 PICK 2 : 7 : 1 로
  나눠 준다 — 몬스터·상자(`mix_fNN_drop`) / 시련방 / 특별 시련(`special_trial_fNN`) / 금고·미믹(`hoard_fNN`, `Treasures.open`) / 정예 /
  보스(그 보스 고유 장비만, 핵으로 대장간) / 대장장이 제작 / 상인 / 칭호 보상 / 시작 지급. 획득처 종류 1~2개, 영웅 이상 무기는 1개.
- 미궁: 지하 1~10층. 층마다 테마·몹 3~4종·엘리트·고유 보스(페이즈 2~3, 고유 기믹). 보스 처치 → 다음 층 계단.
  - 해금: 처음엔 1층만. 층을 깨면 다음 층 해금. 파티는 **파티원 중 최소 해금층**까지 선택 가능.
  - 솔로 입장 또는 파티 입장(파티원 모두 입구 근처, 파티장만 시작).
  - **파티 인원 배율**: 몹 HP ×(1 + `hp_per_member`×(n−1)), 피해 ×(1 + `dmg_per_member`×(n−1)), 보상 약간 증가. config.
    솔로(1명)만 HP ×`party.solo_hp`·피해 ×`party.solo_damage`(0.85, 보상 그대로 — `core.PartyScaling`).
  - **난이도 층 램프**: 어려움·악몽의 HP·피해·경고 시간은 낮은 층에서 완만하게 시작해 `ramp.full_floor` 층부터 원래 값(`Difficulty.atFloor`,
    InstanceContext 가 층마다 한 번 적용 — 몹·보스·함정·보스 기믹 배율이 모두 층 실효값). 드롭·경험치는 1층부터 원래 값. GDD §2.4.
  - **난이도는 서버 전체 설정 하나**: 쉬움/보통/어려움/악몽 (HP·피해·드롭 배율, config.yml 프리셋). **난이도 해금 없음**,
    입장할 때 고르지도 않음. **서버를 처음 만들 때 관리자가 정한다**: 첫 실행 시 `config.yml: difficulty` 가 비어 있으면
    처음 접속한 관리자(OP/`labyrinth.admin`)에게 **초기 설정 GUI**(난이도 4개 + 입구 방식 블록/NPC-only)를 띄우고,
    정하기 전까지 미궁 입장을 막는다(안내 메시지). 이후 변경은 `/labadmin difficulty <난이도>` 또는 config 수정 후 reload
    (진행 중인 인스턴스에는 다음 입장부터 적용). 콘솔에서도 `/labadmin setup <난이도>` 가능.
    (층 해금은 그대로 유지: 처음엔 1층, 깬 층의 다음 층까지 입장 가능.)
  - 사망: 파티원이 있으면 관전 모드 → 휴식방 도달/보스 처치 시 부활. 전멸 시 인스턴스 실패·귀환. 아이템 손실 없음.
  - 미궁 밖 사망(야생·마을·네더·엔드, PvP 포함) = 인벤세이브 `core.DeathKeep`(config.yml `death: {keep_inventory, keep_level}`, 키 없으면 둘 다 true):
    소지품·바닐라 경험치 레벨 유지, 드롭·경험치 구슬 0. false 면 그 부분만 바닐라. 미궁 월드는 DungeonManager 가 같은 `DeathKeep.apply` 로 언제나 보존.
- **PvP = 파티 규칙 하나** (대전·투기장·매치·레이팅 없음, GDD §18): 같은 파티원끼리는 야생·마을·미궁 어디서든 서로 피해를 줄 수 없고,
  그 밖의 플레이어끼리는 피해를 줄 수 있다. 근접·화살·스킬·무기 스킬·장판·물약·불·TNT·늑대·낚싯대 모두 같은 규칙. 플레이어끼리
  피해는 `pvp/PvpDamage`(기준 배율 m(L) · 직업 보정 · 스킬 pvp_mult · 강인함 · 완충 체력, 방어 대신 강인함, 치명 추가 피해 ×0.6,
  한 방 상한 없음). 회복·보호막·상태이상은 `TargetFilter.pvp()`(`PvpState`) 에 물어 PvP 전투 중 배율·줄어듦·면역(GDD §18.6·18.7).
  마을 안전지대 안은 금지. 플러그인이 모든
  월드의 바닐라 PvP 게임 규칙을 `pvp.enabled` 로 맞춘다. 돈으로 살 수 있는 이점 없음(EULA).
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
    weapon_types: [sword_shield]   # 추천 무기 (제한 아님, GDD §4.4)
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
    weapon_type: greatsword   # classes.weapon_types(추천 무기) 와 매칭. bow 는 활 동작.
    armor_slot: null          # head | chest | legs | feet | offhand(방패, 보조손 — 수호기사 추천) (armor 일 때)
    armor_set: null           # 방어구면 장비 에셋 세트 id
    rarity: legendary
    level_req: 25
    requires: {STR: 33, VIT: 20, INT: 13}   # 0.3.5: '모두 채움' 요구 능력치 (합 ceil(2.75(L−1)), 2~3개) — classes 는 장비에 없다
    tier: 5                   # 0.3.5 숨은 단계 (Lv 5N−5~5N, 옛 floor) — 보스가 아니면 이웃 층 셋이 단계 풀로 나눠 준다
    pool: false               # rarity_pool 미사용 (장비는 전부 false)
    sources: [boss, craft]    # 획득처 (툴팁·도감) — 집 최대 2곳, GDD §11.3
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
  band_t01_drop:              # 0.3.5 단계 풀 (단계 1 몬스터·상자 무기) — 이웃 층이 PICK 으로 나눠 굴린다
    rolls: 1
    entries:
      - {one_of: [corridor_longsword, rootcutter_greatsword, ...], chance: 1.0}
  mix_f01_drop:               # 1층 몬스터·상자 = 단계 1 : 2 = 7 : 1 (2~9층은 f−1 : f : f+1 = 2 : 7 : 1)
    rolls: 1
    entries:
      - {pick: [{table: band_t01_drop, weight: 7}, {table: band_t02_drop, weight: 1}], chance: 1.0}
  moss_crawler:
    rolls: 1
    entries:
      - {item: moss_fiber, chance: 0.55, amount: [1, 2]}
      - {table: mix_f01_drop, chance: 0.0228}            # 장비는 이름으로만 (rarity_pool 은 쓰지 않음)
      - {table: enhance_mob_t1, chance: 1.0}

# recipes.yml
recipes:
  ember_greatsword:
    result: ember_greatsword
    station: blacksmith
    materials: {forge_core: 1, ember_shard: 20, slag_ingot: 16, executioner_edge: 3, labyrinth_essence: 5}   # 그 층 재료 + 그 보스 핵
    gold: 9000
    level_req: 25

# titles.yml
achievements:                    # 0.3.4: 12개, 칭호마다 서버에서 단 한 명 (records.yml title.<id>)
  black_blade:
    name: "검은 칼날"               # 이름·lore 는 조건을 암시하지 않게
    lore: "칼집에서 나온 적이 드문 칼일수록 이름이 길게 남는다."
    condition: {type: SOLO_CLEAR, floor: 5}   # FIRST_CLEAR | CLEAR | SOLO_CLEAR | NO_DEATH_CLEAR | DIFFICULTY_CLEAR |
                                               # SPEED_CLEAR | KILL | BOSS_KILL | LEVEL | OBTAIN_RARITY | CRAFT | ENHANCE | TREASURE
                                               # 돌파 조건 공통 선택 키: solo · no_death · party_min · difficulty · seconds
    title: "<gradient:#1e1e26:#6a6a7a:#d8d8e8>검은 칼날</gradient>"
    bonus: {STR: 2}                 # 장착 중에만, 한 명만 가지니 작게
    broadcast: true                 # 주인이 생기면 방송 (조건 공개)
    reward: {gold: 1500}            # 주인이 될 때 1회
  # 판정: 사건(층 돌파·처치·레벨업·획득·제작·강화·미로 보물)이 일어난 순간만, 주인 없는 칭호만 (titles.AchievementRules.qualifies).
  # 파티 사건은 그 보스에게 가장 많은 피해를 준 한 명 (CustomMob.damageByPlayer → titles.AwardOrder: 피해 → 막타 → 파티 순서).
  # 조건 문구(AchievementRules.conditionText)는 주인이 생긴 칭호와 /labadmin title list 에서만 (titles.TitleView).
  # 예전 키 server_first · category · hidden · description 은 읽어도 쓰지 않음. 0.3.4 첫 접속 때 예전 칭호 회수 (ext titles.reset_034).

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

# glyphs.yml  (pack-ui 단계에서 작성 — 전체 254 글리프, 상세 주석은 파일 머리말)
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
  `skills[].type` = GDD §9.1 닫힌 목록(26종 — 새 몸 형태 단계에서 `burrow`(땅 위 전용)·`dive`(flying 전용) 추가, ContentValidator 가 검사),
  `params.effect` = §9.2. `model.parts[]` 에 `form`·`size: [w,h,d]`(px) 추가, `model.style` 에 `features` 추가 (form/anim/shape/features 목록 = GDD §14.3).
  새 몸 형태 단계 추가 키: projectile `blast_radius`·`blast_delay`·`blast_damage`·`blast_knockback`(착탄 폭발), cleave `rear`·`knockback`(꼬리 휩쓸기),
  form `wing`·`neck`·`segment`, anim `wings_flap`·`neck`·`tail_chain`, shape `drake`·`wyvern`·`dragonkin`·`naga`·`centaur`·`harpy`·`minotaur`·`lich`·`worm`.
  0.3.2 추가 키: 몹 최상위 `attack_interval`(기본 공격 간격 초, 없으면 1.2 — 떼 ×0.85, 원거리 기본탄 +0.8초, `MobAi.attackInterval`; 1층 몹 1.5 · 2층 몹 1.35),
  `summon` 스킬 params `solo_count`·`solo_max_alive`(1인일 때 count·max_alive 대신, 2인 이상은 원래 값 — `Params.scaledInt`, GDD §8.4·§2.7).
- **bosses.yml**: `core`(핵심 기믹 키, 보스마다 다름), `description`, `speed`, `flying`, `bossbar`(BossBar 색),
  `lines: {intro, phase2, phase3, death}`, `rotation: {페이즈번호: [패턴키…]}`, `sounds`, `arena` 에 보스별 배치 키
  (pillars/nests/platforms/valves/anchors/pylons/rune_shelves/corridor_length …). 패턴 params 공통 규칙(`*_base`·`*_per_member`·
  `*_per_members`·`*_pct`·`solo_*`·`p2_*`) = GDD §8.4. rotation 에 없는 패턴 키 = 상시 시스템/페이즈 트리거(GDD §8.3).
- **npcs.yml**: `role` 에 `lore`(층 휴식방 이야기 NPC) 추가, `nameplate`, `placement(overworld|floor)`, `floor`, `dialogue: [..]`,
  `shop: [{item, price, level_req?}]`(merchant), `skin_style` 에 `hair`, `accessories` (목록 = GDD §14.5, palette 6색 순서 고정).
- **titles.yml**: `lore`, `reward: {gold, items: {id: 개수}}` (`category`·`hidden` 은 0.3.4 부터 안 씀).
  condition 파라미터: CLEAR `{floor, count?}`, NO_DEATH_CLEAR `{floor, party_min?}`, DIFFICULTY_CLEAR `{floor, difficulty}`,
  SPEED_CLEAR `{floor, seconds}`, KILL `{count, mob?, mobs?(id 목록 — 처치 수 합), rank?}`, BOSS_KILL `{count, boss?}`, LEVEL `{level}`, OBTAIN_RARITY `{rarity, count?}`,
  CRAFT `{count, rarity?}`, ENHANCE `{level}`. `bonus` 키 = 스탯 6종 + `xp_bonus`, `gold_bonus`.
- **fx.yml**: `auras.<id>`: `tier(legendary|mythic)`, `particles[]: {type, count, radius, height, pattern, chance?, speed?, color?, color_to?, size?}`
  (color 류는 DUST/DUST_COLOR_TRANSITION 전용), `ring_scale`, `ring_height`, `ring_step`, `secondary_model`, `secondary_spin`,
  `secondary_mode(ring|back)`, `interval`(틱), `swing`. `models.<name>`: `motif`, `shape`(projectile), `frametime`, `size: [w,h,d]`(px),
  `flat`, `billboard(FIXED|CENTER|VERTICAL)`, `glow`. 아우라마다 `<id>_ring`/`<id>_slash`/`<id>_orb`/`<id>_burst` 모델이 있다
  (무기 스킬 `params.fx` 용). style/motif 목록 = GDD §14.4.

### 6.2 아이템·루팅·제작 단계에서 추가된 필드 (items/loot/recipes/titles/fx)
모두 **추가** 필드이며 닫힌 목록과 해석은 GDD.md 에 있다(§번호 표기). 생략한 필드 = null / 기본값.

- **items.yml**
  - `tier`(1~10, 0.3.5 — 장비): 숨은 단계 = 레벨 구간 Lv 5N−5~5N (`ItemDef.tier()`, 레코드 필드는 `floor` 그대로). 보스가 아닌 장비는 단계 N−1·N·N+1
    층 표에서만 나온다(검사기 경고 "레벨 창 밖"). 옛 `floor` 도 같은 값으로 읽고 경고. 강화석 등급(`enhance.stones.max_floor`)도 이 값.
    재료의 `floor` 는 그대로(획득 층). 장비 생성기 = `tools/gen_035_content.py` (입력 `tools/data/035/`, 손으로 고치지 말 것).
  - `pool`(기본 true): false 면 rarity_pool 이 뽑지 않음. loot.yml 은 rarity_pool 을 쓰지 않으므로 장비는 **전부 false**(실수로 풀을 다시 써도 안전).
  - `sources`: 획득처 목록 `drop | chest | elite | boss | trial | special | hoard | craft | reward | shop | starter` (툴팁 "획득처"·도감용,
    gen_035_content 가 loot/recipes/titles/npcs/config `starter_kit` 에서 계산해 적음). `drop`+`chest` = 몬스터·상자 한 종류(`mix_fNN_drop`),
    `trial` 시련방 · `special` 특별 시련 · `hoard` 금고·미믹, `starter` = 시작 지급(몹·상자·대장간에서 안 나옴). **획득처 종류 1~2개, 영웅 이상 무기는 1개**.
    실제 획득처와 다르면 검사기 경고. 툴팁 한 줄 = `ItemTooltip.sourceLine`
    ("보스 테오라(9층) · 대장간", "정예 <이름>(N층)", "지하 N층 몬스터·상자", "시작 지급" — 이름은 주는 보스·정예가 하나뿐일 때만, 콘텐츠를 다시 읽을 때 계산).
  - `classes`: 0.3.5 부터 장비에는 없다 (드롭 편향은 `requires` 로 — loot.yml `own_build_bias`). `requires_any` 도 없어졌다(파서가 문제로 알리고 무시).
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
  - `texture.style`/`effect` 에 아이콘 무늬 8개·effect 8개 추가(GDD §14.2).
  - 무기 `model.shape` 에 새 실루엣 12종 추가(GDD §14.1·§11.2, 무기 종류마다 2개): warhammer · falchion · war_scythe · glaive ·
    horn_bow · blade_bow(활 — `_pulling_0..2` 자동) · staff_spiral · staff_fork · bell_scepter · chalice_scepter · sickle · katar.
    생성기 = `resourcepack/src/voxel/weapons.py`(복셀 전용, 옛 상자 템플릿 없음). 플러그인은 shape 를 읽지 않는다(활 여부는 weapon_type).
  - `sets.<id>.look`: heavy | light | cloth — 장비 에셋 레이어 실루엣(GDD §14.7). `bonuses` 키 = 착용 개수(이상).
- **loot.yml**
  - 최상위 `settings: {own_build_bias, luck_per_point, party_bonus_per_member, max_chance, rarity_weight: {난이도: {희귀도: 배율}}, announce_rarity}`.
    `own_build_bias`(0.3.5, 옛 `own_class_bias` 도 읽음) = one_of 로 장비를 고를 때 그 확률로 "요구치 1위 능력치가 줍는 사람 능력치
    (`StatService.requirementStats` 상위 2개) 안" 인 후보만 (`LootRoller.Request.stats`, `fitsBuild`).
  - 테이블 `guaranteed: [{item, amount}]`(배율 무관 확정 지급 — `one_of`·`table` 도 가능), `gold: [min, max]`(상자 골드).
  - 항목 종류 추가: `{one_of: [id…], chance}`, `{table: id, chance}`(순환 금지), `{pick: [{table, weight}, …], chance}`(0.3.5 — 무게대로 하위 표 하나,
    `LootTable.Kind.PICK`, 하위 표 없음·무게 ≤ 0·순환은 검사기 오류). 공통 선택 키 `min_difficulty`. 해석 = GDD §11.10.
  - **장비 배치 테이블 (0.3.5, GDD §11.3)**: 단계 풀 `band_tNN_<drop|trial|special|hoard|elite>` · 층 섞음 `mix_fNN_drop`(일반 몹·`treasure_floor_N`·
    층별 미로 상자가 `{table: mix_fNN_drop, chance: p}`) · `gimmick_floor_N`·정예 표의 PICK · `hoard_fNN`(금고 안 상자·길들인 미믹 — `Treasures.open`
    이 강화 표 다음에 한 번 더) · `special_trial_fNN`(P4 특별 시련 성공 상자). 보스 장비는 `floorNN_boss` 에 `one_of`/`item` 으로 직접.
    `rarity_pool` 항목은 쓰지 않는다(검사기 경고). 0.3.4 의 `gear_fNN_common` 은 없어졌다.
  - **미로 상자 표**: 층별 `maze_chest_<wood|iron|gold>_f<N>`(그 층 재료·`mix_fNN_drop`·금 상자는 그 층 정예 재료 — 장비 직접 금지) 가 **우선**이고, floors.yml `chests.bracket`
    강제(> 0)나 층별 표가 없을 때만 구간 표 `maze_chest_<tier>_<1~4>`(장비 없음). 판정 = `dungeon.treasure.ChestTier.table(floor, bracket, exists)`.
  - 검사기(`ContentValidator`) 경고: rarity_pool 사용 · 층 표가 레벨 창(단계 ±1, 보스는 같은 단계) 밖 장비를 줌 · 획득처 종류 3개 이상 ·
    영웅 이상 무기 획득처 종류 2개 이상 · items.yml `sources` 불일치 · 시작 지급 장비가 루팅·제작에서도 나옴 · 요구 능력치 규칙(합·나눔·피해 능력치).
- **recipes.yml**: `category`(weapon | armor | accessory | material — 대장장이 GUI 탭), `amount`(결과 개수, 기본 1).
  레시피 재료는 그 층 것만(그 층 일반 재료 + 그 층 정예 재료 + 그 층 정수 등급, 보스 장비는 + 그 보스 핵 — 정예 장비에는 핵을 넣지 않는다). 대장간 GUI 에 직업 필터는 없다.
- **titles.yml**: (0.3.4) 모든 칭호가 서버에서 1명만 — 예전 선택 키 `server_first` 는 무시.
  (예전 파티 대전용 PVP_* 조건과 arenas.yml 은 없앴다 — PvP 는 파티 규칙 하나, GDD §18.)
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

- `arena` 6층: `sigil_ring_radius`(인장 링, 기본 10), `floor_thaw`(기본 true — 전투 동안 아레나 바닥의 원래 얼음을 눈·방해석으로 덮어
  영구 동토 얼음판만 미끄럽게, 끝나면 복원). 6층 `glacier_shell.role_damage` = classes.yml `role` → 깰 수 있는 인장 유형(melee|ranged|magic).
- 9층 `timed_seals`·`doom_clock`: 바늘·봉인석은 바닥 판(`clock_hand`/`clock_hand_reverse`, `seal_glyph`/`seal_glyph_open` 모델 교체)이고 블록을 바꾸지 않는다.
  종말 시계는 세 번째 보스바(HUD 키 `boss_doom`), 이 보스는 기본 광폭화 대신 종말 시계를 쓴다(`enrage` 를 적으면 둘 다). 되감기·시간 역류는 `impl.PositionHistory`(0.5초 링버퍼).
### 6.5 config.yml `hints` (점진 힌트)
```yaml
hints:
  mode: progressive        # progressive | none | full
  thresholds: [2, 4, 6]    # 실패 횟수 경계 → 단계 1..3 (파티원 중 최댓값 기준)
```

### 6.6 강화 단계에서 추가된 것 (GDD §11.13 — 전부 추가)
- **config.yml** `enhance:` — `enabled, max_level, chances[], downgrade_from, protection_item, stat_bonus[], weapon_stats[], armor_stats[],
  gold_base, gold_level_offset, gold_rarity{}, gold_steps[], craft_discount, stone_counts[], stones[{item, max_floor}], broadcast_from,
  glint_from, glow_interval`. 목록은 목표 단계 +1.. 순(모자라면 마지막 값). 원본 파서 = `items.enhance.EnhanceRules.Config.from`.
  **`stat_bonus`**(0.3.2 — 예전 `stat_per_level` 을 대체): 단계별 **누적** 보너스, 배율 = 1 + stat_bonus[단계−1]. 기본(키가 없거나 빈 목록·숫자 없음)
  `[0.04, 0.08, 0.13, 0.19, 0.26, 0.35, 0.46, 0.60, 0.78, 1.00]` = 상승폭 4·4·5·6·7·9·11·14·18·22% → +5 ×1.26 · +8 ×1.6 · +10 ×2.0
  (`EnhanceRules.Config.defaultStatBonus()` = 번들 config 값, 테스트가 같음을 확인). 줄어드는 값은 앞 값으로 올려 막는다(단조). `stat_per_level` 은 읽지 않는다
  (예전 config.yml 에 남아 있어도 무시 → 기본 곡선). `EnhanceRules.multiplier(단계)`·`stepGain(단계)`(다음 단계 상승 몫).
- **content/enhance.yml** (선택 파일 — 없으면 모든 장비가 강화석·골드만, 시작 때 경고 한 번. 파서 `ContentParser` → `content.EnhanceDef`, `Content.enhance()`):
  ```yaml
  version: 1
  bands: {low: [1, 3], mid: [4, 6], high: [7, 10]}   # 목표 단계 구간. 마지막 구간 너머(max_level 을 올렸을 때) = 마지막 구간의 마지막 개수
  items:
    grove_warden_maul:                               # 장비 id → 구간 → {재료 id: 개수}  (YAML 순서 = 강화 창 표시 순서, 툴팁에는 첫 재료만)
      low:  {moss_fiber: [4, 4, 5]}                  # 개수 = 숫자 하나(구간 전체) 또는 목록(구간 안 목표 단계 순, 모자라면 마지막 값, 0 = 그 단계엔 없음)
      mid:  {moss_fiber: [5, 5, 6], beetle_shell: [3, 3, 4]}
      high: {moss_fiber: [6, 7, 8, 9], beetle_shell: [4, 4, 5, 6], alpha_moss_crest: [1, 2, 0, 0], warden_heartwood: [0, 0, 1, 2]}
  ```
  `EnhanceDef.costs(id, 목표)` = 그 시도의 장비 재료(개수 > 0). 없는 재료·장비 id 는 읽을 때 경고 목록(`warnings`)에 넣고 그 줄만 무시.
  **생성기** `tools/gen_enhance.py`(`--check`·`--report`·`--spec`): loot.yml 을 펼쳐 층별 1회 공급량을 계산해 개수를 맞추고, 규칙·공급량·예상 클리어 수·검사 결과를
  파일 머리 주석에 쓴다. 재료 규칙(GDD §11.13): 제작법이 있는 장비 = 그 레시피 재료(P 가장 많이 드는 것 · S 두 번째 · R 가장 귀한 것), 없는 장비 = 그 장비를
  주는 곳의 드롭, 보스 장비 +7·+8 = 정예 재료 · +9·+10 = 그 보스 핵, mid 까지는 일반 재료만, 같은 층 구성 겹침 0. 장비·레시피·루팅을 바꾸면 다시 돌릴 것
  (`EnhanceMaterialsTest` 가 재료 존재·그 층에서 얻을 수 있음·구간 규칙·보스 핵·겹침·번들 파일 경고 0 을 검사).
- **비용** `EnhanceRules.cost(def, 목표, 할인, EnhanceDef)` → `EnhanceCost(gold, lines)` — 강화석 줄이 맨 앞(`stone()`), 그다음 장비 재료(`materials()`), 같은 id 는 한 줄로 합침.
  `EnhanceCost` 는 골드·강화석·재료를 **전부 확인한 뒤에만** 한꺼번에 소모(하나라도 모자라면 아무것도 안 가져감), 실패해도 소모. 강화 창 비용 줄 배치 = `EnhanceLayout`
  (glyphs.yml `menus.enhance.slots` 의 `gold`·`stone`·`protection` 소켓, `materials: [..]` 가 있으면 그 칸 — 지금 배경은 29·31·33 소켓이라 재료 30·32·28, 글리프 끔 28~33,
  값이 틀리면 예전 소켓 배치). 자가 진단은 단계마다 비용이 실제 아이템을 가리키는지 확인한다.
- **아이템 PDC** `Keys.ITEM_ENHANCE`(Integer 0~max, 없으면 0). 쓸 때 `ITEM_VERSION` 을 2 로 올린다(1 이하 = 강화 0). 다른 모듈은
  `items.enhance.Enhancement.level(stack)` 로 읽고, 단계를 바꾼 뒤 `services.items().refresh(stack)`(이름 `+N`·툴팁·광택 다시 그리기).
  `ItemService.rolledStats` 는 **강화 배율 포함**(무기 `damage`, 방어구·방패 `defense`·`hp`) — 장비 StatContributor·PvP 장비 보정이 그대로 쓴다.
- **items.yml** 재료 4종: `lesser_enhance_stone` · `greater_enhance_stone` · `supreme_enhance_stone` · `enhance_protection_scroll`(2D 아이콘).
  장비별 재료는 기존 재료(층 재료·정예 재료·정수·보스 핵)를 그대로 쓴다 — 강화 전용 새 재료는 없다.
- **loot.yml** 하위 테이블 `enhance_{mob|swarm|elite|boss|chest|gimmick}_t{1|2|3}` · `enhance_preview_t{2|3}` — 몹·보스 테이블은 entries 에,
  rolls 2 인 보물·기믹 상자는 `guaranteed` 에 `{table: enhance_*, chance: 1.0}` 한 줄. **새 몹/층 테이블을 만들면 이 한 줄을 같이 넣을 것.**
- **titles.yml** 조건 `ENHANCE {level}` (+ `server_first`), 카운터 `titles.enhance_best` · `titles.enhance_success`. 이벤트 `event.EnhanceEvent`
  (player, def, item, from, to, outcome = success | fail | downgrade | protected).
- **glyphs.yml** 배경 `gui_enhance`(U+E0E8, 6줄) + `menus.enhance.slots`, `menus.blacksmith.slots.enhance: 13`(배너 모루 자리 = [장비 강화]).
- **명령** `/미궁 강화|enhance`, `/labadmin enhance <단계> [플레이어]`. 자가 진단에 `enhance_checked`(강화 가능 장비 전부 +1~+10 기록·배율 확인).

### 6.7 0.3.2 에서 추가된 설정 (config.yml · dungeon.yml — 전부 추가, 키가 없어도 동작)
기존 서버는 `saveDefaultConfig()`·dungeon.yml 이 이미 있는 파일을 덮어쓰지 않으므로, 아래 키를 읽는 코드는 **Bukkit jar 기본값에 기대지 않고**
키가 없거나 묶음이 비어 있으면 **코드 기본값(= jar 의 값)** 을 쓴다(`core.Settings`, `dungeon.DungeonConfig.of`). 끄는 방법은 키마다 명시값으로 정했다.
```yaml
# config.yml
difficulties:
  hard:      {…, ramp: {from_floor: 1, full_floor: 4, start: {hp: 1.2, damage: 1.15, telegraph: 0.95}}}
  nightmare: {…, ramp: {from_floor: 1, full_floor: 6, start: {hp: 1.8, damage: 1.6, telegraph: 0.85}}}
  # ramp: 층 램프 (core.Difficulty.Ramp — 층 f 값 = start + (원래 − start) × clamp((f − from)/(full − from), 0, 1)).
  #   hp·damage·telegraph 와 보스 기믹 배율(MechanicScaling: 쿨다운·속도·오브젝트 HP·제한 시간 보간, 추가 개수는 진행도 0.5 부터)만. drop·xp 는 그대로.
  #   키 없음/빈 묶음 = Difficulty.Ramp.defaultFor(id) (어려움·악몽만, 원래 값이 기본 시작 값보다 낮으면 그 값으로 자름) · 빠진 하위 키 = 기본 램프 값
  #   끄기 = ramp: {enabled: false} 또는 ramp: false · full_floor ≤ from_floor 면 램프 없음
party:
  solo_hp: 0.85            # 1명일 때만 몹·보스 HP 배율 (PartyScaling.hp(1)), 0.1~1.5 로 자름. 끄기 1.0
  solo_damage: 0.85        # 1명일 때만 몹·보스 피해 배율. 보상은 그대로
starter_kit:               # 직업을 처음 고를 때 플레이어당 한 번 (LabyrinthClassService + classes.StarterKit, 지급 출처 "starter")
  enabled: true            #   끄기 = enabled: false 또는 starter_kit: false. 키 없음/빈 묶음/items 비면 코드 기본 목록(Settings.DEFAULT_STARTER_KIT)
  gold: 300                #   시작 골드 (키 없으면 300)
  items: [{item: novice_cap, amount: 1}, {item: novice_tunic, amount: 1}, {item: novice_trousers, amount: 1},
          {item: novice_boots, amount: 1}, {item: minor_healing_potion, amount: 10}, {item: minor_mana_potion, amount: 5},
          {item: return_scroll, amount: 2}, {item: "minecraft:bread", amount: 16}]
  # id 가 minecraft: 로 시작하면 바닐라 아이템. 콘텐츠에 없는 id 는 경고 후 건너뜀, amount ≤ 64.
  # 0.3.2 기본 목록(수련생 4 + 하급 치유 물약 5)이 그대로면 새 기본값으로 읽는다 (Settings.LEGACY_STARTER_KIT_032).
  # 받은 양 = PlayerData ext starter.kit_got ["id*개수", …, "$gold*n"] — 꾸러미를 늘리면 차이만 지급. 예전 starter.kit: true = 0.3.2 목록을 받은 것.
  # 기존 플레이어(이미 직업 있음): 접속 때 Lv.5 이하이고 dungeon.clear_floor_1 == 0 일 때만 지급, 그 밖에는 받은 것으로 기록만
class_change:              # 직업 변경 제한 (§4.1 ClassChangeGate) — 끄기 class_change: false (또는 require_item: false + cooldown_hours: 0)
  require_item: true
  item: class_change_scroll
  cooldown_hours: 24       # 바꾼 뒤 대기 (실제 시간, ext class.changed_at — 첫 선택은 기록하지 않음)
death:                     # 인벤세이브 (core.DeathKeep) — 키 없으면 둘 다 true
  keep_inventory: true
  keep_level: true
enhance:
  stat_bonus: [0.04, 0.08, 0.13, 0.19, 0.26, 0.35, 0.46, 0.60, 0.78, 1.00]   # §6.6 (stat_per_level 대체)

# dungeon.yml
party_mob_count:           # 솔로·2인 전투방 몹 수 배율 {인원: 배율} (0.1~1.5, 없는 인원 1.0). 정예방 호위도 같은 배율(최소 1)
  enabled: true            #   키 없음/인원 키 없음 = 코드 기본 {1: 0.7, 2: 0.9} · 끄기 = enabled: false 또는 party_mob_count: false (또는 {1: 1.0, 2: 1.0})
  1: 0.7
  2: 0.9
party_mob_reward: true     # 줄인 만큼 웨이브 몹 보상 보정 — 끄기 false
room_clear_heal: 0.15      # 전투방·정예방 정리 때 살아 있는 파티원 최대 HP 비율 회복 (0~1) — 끄기 0
first_clear_bonus: 0.4     # 층 첫 돌파 경험치 = 그 층 level_range 최소→최대 필요 경험치 합 × 값 (0~2, 난이도 배율 없음) — 끄기 0
```
- **몹 수·보상**: `DungeonConfig.battleWave(굴림, n)` / `eliteEscort(굴림, n)` → `Wave(count, rewardMult)`. 전투방 = round(굴림 × party_mob_count[n] × (1 +
  `mob_count_per_member`×(n−1))), 1 ~ `max_mobs_per_room`; rewardMult = '배율 없이 나왔을 수 ÷ 실제 수'(`party_mob_reward: false` 면 1). BattleRoom 이
  웨이브 몹마다 `CustomMob.rewardMultiplier(m)` 로 기록 → `MobServiceImpl.reward` 가 경험치·골드에 곱하고 `LootService.drop(table, looters, at, ctx, source, extraMult)`
  로 루팅 확률(정예 변종 두 번째 굴림·테이블 골드 포함)에 곱한다(`LabLootService` = 확률 배율 × extraMult, 기본 구현은 extraMult 무시).
  정예 본체·소환물·미믹·경보 몹은 1. **새 방 종류가 몹 수를 줄이면 같은 방법으로 rewardMult 를 넘길 것.**
- **방 정리 회복**: `BattleRoom` 정리 때 `fs.alivePlayers()` 각자 `stats().heal(maxHp × room_clear_heal)` + 액션바 "+15% HP".
- **첫 돌파 보너스**: `Run.onFloorCleared` — 카운터 `dungeon.clear_floor_<n>` 이 1이 된 사람에게 `DungeonConfig.firstClearXp(curve, level_range)`.
- **램프 적용 지점**: `InstanceContext` 생성자가 층 실효 `Difficulty.atFloor(floor)` 와 `rampProgress` 를 한 번 정한다(돌려받은 값은 ramp = null 이라 두 번 적용 안 됨).
  대체 보스(BossRoom·SelfTest)는 원래 ctx 의 rampProgress 를 넘기는 생성자를 쓴다. 표시: `Difficulty.hpDamageText()`/`telegraphText()`(초기 설정·난이도 변경),
  입장 메뉴·채팅 설정 메뉴는 고른 층의 실효 배율 + 솔로 보정 줄.
- **mobs.yml** `attack_interval`, summon `solo_count`·`solo_max_alive` 는 §6.1. classes.yml 은 수치만 바뀜(그림자 base_hp 115·VIT 5, 비전술사 110·VIT 4, 마력탄 damage 2.0).

### 6.8 0.3.4 어깨·등 3D 장식 (config.yml — 키가 없어도 코드 기본값)
```yaml
cosmetics:
  armor_pieces:            # items.ArmorCosmetics.Config.from — 묶음·키가 없으면 DEFAULT (true, 2, 0.6)
    enabled: true          #   끄기 = false (디스플레이를 하나도 만들지 않음)
    update_ticks: 2        #   몸 yaw·자세를 다시 보는 간격 1~20 틱 (teleport_duration 도 같은 값)
    view_range: 0.6        #   Display view_range (1.0 ≈ 64블록), 0 이하·NaN → 기본, 최대 4
```
- 플레이어별 `/미궁 장식|cosmetics [켜기|끄기|on|off]` (인자 없으면 뒤집기) → PlayerData ext `cosmetics.armor_pieces` (Boolean, 없으면 켜짐).
  끄면 그 플레이어의 장식이 아예 생기지 않는다(다른 사람에게도 안 보임). 다른 사람 장식을 내 화면에서만 끄는 기능은 없다.
- `/미궁 장식 내화면|self [켜기|끄기]` → ext `cosmetics.armor_pieces_self` (없으면 꺼짐): 켜면 내 장식을 나에게도 보인다(3인칭 확인용 —
  1인칭에서 아래를 보거나 고개를 돌리면 어깨 장식이 화면 가장자리에 걸릴 수 있다고 안내). 기본은 꺼짐이라 **혼자 접속해 F5 로 보면 장식이
  안 보인다** — 두 번째 계정으로 보거나 내화면 켜기로 확인한다. 처음 장식이 생길 때 한 번 이 명령을 안내한다(ext `cosmetics.armor_pieces_told`).
- 자세 (`ArmorPieceLayout.stance`): 사망·관전 = 디스플레이 제거, 투명(효과 포함)·탈것·잠·활공·헤엄·급류·서기/웅크리기 밖의 자세 = 크기 0,
  웅크리기 = 웅크리기 배치(보간 3틱). 벗기·나가기·사망·월드 이동·reload·플러그인 종료 때 제거, 탑승이 풀리면 다시 태움(40틱 안에 6번 넘게
  풀리면 100틱 쉼 — 탑승물을 계속 내리는 다른 코드와 싸우지 않음).
- SelfTest 1층: `ArmorCosmetics.selfCheck` — 첫 세트 장식 3개를 시작방에 띄웠다 지우고(모델 키·배율 확인), 배포 팩 zip(`plugins/Labyrinth/pack/labyrinth-pack.zip`
  또는 jar 안 `pack/`)이 있으면 모든 세트 × 부위의 아이템 정의가 있는지 본다.

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
- 0.3.2 콘텐츠 규칙 테스트: `LootHomesTest`(장비 집 1~2곳·다른 층 누수 0·sources 일치·보스 장비는 그 층 보스만·수련생 비드롭·층별 미로 상자·
  요구 레벨 ≤ 층 구간), `EnhanceMaterialsTest`·`EnhanceRulesTest`·`EnhanceLayoutTest`(재료 규칙·곡선·비용 줄 배치), `ScalingTest`(램프·솔로 보정·예전 설정 기본값),
  `RoomRewardTest`(솔로·2인 몹 수·보상 보정·방 정리 회복·첫 돌파), `EarlySoloDataTest`(1·2층 공격 간격·소환 솔로 값·직업 HP), `StarterKitTest`, `ClassChangeRuleTest`.
  콘텐츠를 고치면 이 테스트와 `tools/gen_enhance.py --check` 를 같이 돌릴 것.
- `labadmin selftest` 는 층마다 기믹방 단서 3단계·보스 단서의 MiniMessage 읽기를 확인한다(`hints` 단계, `hint_gimmicks`/`hint_bosses` 개수).
- `./gradlew build` 가 테스트 포함 통과해야 함.
- `ContentValidator`: 모든 YAML 교차참조(아이템·몹·루팅·레시피·층·보스 id)가 유효한지 시작 시 + 테스트에서 검사.
- 리소스팩 생성기는 끝에 자체 검증: content 의 모든 아이템/몹 파트/NPC/글리프/fx 에 대응 파일이 있는지, JSON 파싱, PNG 크기.
