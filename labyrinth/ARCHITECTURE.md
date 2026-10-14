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
- **NPC 스킨**: `npcs.yml` 의 `skin: <id>` → `assets/labyrinth/textures/entity/npc/<id>.png` (64x64 플레이어 스킨 레이아웃).
  플러그인은 `Mannequin` 엔티티 + `ResolvableProfile` 의 SkinPatch(body 텍스처 = `labyrinth:entity/npc/<id>`) 사용.
- **이펙트 모델**(아우라 링, 장판 경고, 투사체 등): `labyrinth:fx/<name>` → `assets/labyrinth/items/fx/<name>.json`.
  목록은 `content/fx.yml`.
- **UI 글리프**: `content/glyphs.yml` 이 원본. 폰트 `labyrinth:ui` (`assets/labyrinth/font/ui.json`).
  각 글리프 = 사설 영역 코드포인트(U+E000~) + PNG + ascent + height. 음수/양수 공백 글리프로 위치 이동.
  플러그인은 `Component.text(char).font(Key.key("labyrinth","ui"))` 로 사용. 하드코딩 금지, glyphs.yml 에서 읽기.
- 사운드: 1차 버전은 바닐라 사운드 이벤트를 pitch/volume 조합으로 사용(사운드 파일 미포함). 사운드 키는 YAML 에 둔다.

## 3. 리소스팩 배포

- 플러그인 `pack` 모듈이 내장 HTTP 서버(`com.sun.net.httpserver`, 기본 포트 `config.yml: pack.port`)로
  `plugins/Labyrinth/pack/labyrinth-pack.zip` 을 서빙하고, 접속 시 `Player#sendResourcePacks` (SHA-1 포함, 필수/거절 시 안내).
  외부 URL 을 쓰고 싶은 사람은 `pack.url` 로 덮어쓰기.
- pack.mcmeta: 26.3 리소스팩 포맷은 **97.1** (`version.json` 의 `pack_version.resource_major/minor`).
  26.x 의 `min_format`/`max_format` 형식으로 작성 (생성기 담당이 정확한 스키마 확인).

## 4. 플러그인 구조 (`kr.labyrinth`)

```
LabyrinthPlugin      onEnable: Services 생성 → 모듈 enable(순서대로) / onDisable: 역순 disable + 저장
Services             모든 서비스 인스턴스 보관 (생성자 주입 대신 단순 레지스트리). 순환 참조는 getter 로 지연 접근.
core/    Module(interface: name, enable, disable), Keys(NamespacedKey 모음), Text(MiniMessage 헬퍼),
         Settings(config.yml 래퍼: 난이도/파티 배율/팩/입구 등), ContentLoader(content/*.yml 를 데이터폴더로 복사·로드·/reload)
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
loot/    LootService(loot 테이블, 희귀도 가중치, LUK 보정, 파티 개인 루팅: 아이템은 개인별로 지급/표시)
crafting/CraftingService(+대장장이 GUI, 재료 확인/소모, 결과 지급)
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
ui/      Menu 프레임워크(InventoryHolder 기반, 커스텀 폰트 배경 타이틀, 버튼 콜백), menus/*(스탯, 직업, 파티, 입장/난이도,
         대장장이, 칭호, 장신구), HudService(액션바: HP/MP 바·레벨·골드, 사이드바: 층·남은 적·파티원 HP, 보스바)
pack/    PackService(HTTP 서빙 + 전송)
command/ CommandService(Paper Brigadier: LifecycleEvents.COMMANDS)
```

### 명령어
- 플레이어: `/lab`(별칭 `/미궁`: 입장 메뉴·퇴장·정보), `/party`(`/파티`), `/stats`(`/스탯`), `/class`(`/직업`), `/title`(`/칭호`),
  `/pvp`(`/대전`: 도전 <파티장>, 수락, 거절, 대기열 참가/취소, 순위, 전적)
- 관리자(`labyrinth.admin`): `/labadmin reload|give <item> [player]|spawnmob <id>|spawnboss <floor>|setentrance|removeentrance|
  setnpc <id>|tpfloor <n>|unlock <player> <floor>|reset <player>|instances|endinstance <id>`

### 스킬 입력 (미궁 무기를 들고 있을 때)
- **무기 스킬** (상위 무기에 내장, `items.yml` 의 `weapon_skills`):
  좌클릭 = 무기 기본기(예: 검을 휘두르면 검기가 날아감, 짧은 내부 쿨다운),
  우클릭 = 무기 스킬, 웅크리기+좌클릭 = 무기 스킬2, 웅크리기+우클릭 = 무기 스킬3(오의).
  **무기마다 다르게**: 상위 무기라고 4칸을 다 채우지 않는다. 무기 콘셉트에 맞는 1~3개가 보통이고,
  4개 전부는 일부 신화 무기만. **좌클릭 기본기(검기 등)는 소수의 무기에만** — 대부분의 무기는 좌클릭이
  평범한 공격이다. 활은 우클릭(당기기)을 그대로 둔다.
- **직업 스킬**: F(손 바꾸기) = 스킬1, 웅크리기+F = 스킬2, Q(버리기) = 스킬3, 웅크리기+Q = 궁극기.
  미궁 무기를 든 상태의 손 바꾸기·Q 버리기 이벤트는 취소(인벤토리 창에서 끌어서 버리기는 허용).

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
  - **난이도**(입장 시 파티장이 선택, 관리자가 허용 목록 설정): 쉬움/보통/어려움/악몽. HP·피해·드롭 배율, 악몽은 어려움 10층 클리어 후 해금.
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
    armor_slot: null          # head | chest | legs | feet (armor 일 때)
    armor_set: null           # 방어구면 장비 에셋 세트 id
    rarity: legendary
    level_req: 25
    classes: [berserker]      # 비우면 모두
    stats: {damage: [38, 44], STR: [6, 9], crit_chance: [0.04, 0.06]}   # [최소, 최대] 굴림
    set_bonus: null           # 세트 id (sets: 섹션 참고)
    aura: ember               # fx.yml aura id (전설/신화 무기)
    weapon_skills:            # 일부 상위 무기에만, 무기마다 1~4개(보통 1~3). 좌클릭 기본기는 소수 무기만. 구현: items/weaponskills/*
      - id: ember_wave        # 코드 구현 키 (공용 구현을 params 로 재사용 가능: slash_wave, nova, dash_strike ...)
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

# titles.yml 조건 추가: PVP_WIN(count) | PVP_STREAK(count) | PVP_RATING(min) | PVP_FIRST_WIN

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

# glyphs.yml
glyphs:
  gui_stats:   {char: "", file: gui/stats.png, ascent: 13, height: 222}
  hp_bar_full: {char: "", file: hud/hp_full.png, ascent: -20, height: 9}
spaces: {neg_1: -1, neg_8: -8, neg_169: -169, pos_1: 1}   # 공백 프로바이더
```

스키마를 확장해야 하면 필드를 **추가**만 하고 이 문서 §6 을 갱신한다. 생성기·플러그인 모두 모르는 필드는 무시한다.

## 7. 성능·안정성 규칙

- 블록 대량 배치는 틱당 상한(예: 4,000 블록)으로 나눠서. 층 생성 중엔 입장자에게 진행 표시.
- 반복 작업은 `BukkitRunnable`/스케줄러 하나로 묶기. 플레이어 없는 인스턴스는 30초 후 정리.
- 모든 이벤트 리스너는 `labyrinth_world` 여부를 먼저 확인해 미궁 밖에는 영향 없게.
- 서버 종료/리로드 시: 인스턴스의 플레이어를 입구로 귀환, 커스텀 엔티티 제거, 데이터 저장.
- 커스텀 엔티티에는 PDC 태그(`labyrinth:mob`)를 달아 서버 재시작 후 남은 것 청소.
- 예외로 서버가 죽지 않게: 패턴/스킬 틱은 try-catch 후 로그.

## 8. 테스트

- 순수 로직(경험치 곡선, 스탯 계산, 피해 공식, 배율, 루팅 확률, 미로 생성 연결성, YAML 로딩/검증)은 JUnit 5.
- `./gradlew build` 가 테스트 포함 통과해야 함.
- `ContentValidator`: 모든 YAML 교차참조(아이템·몹·루팅·레시피·층·보스 id)가 유효한지 시작 시 + 테스트에서 검사.
- 리소스팩 생성기는 끝에 자체 검증: content 의 모든 아이템/몹 파트/NPC/글리프/fx 에 대응 파일이 있는지, JSON 파싱, PNG 크기.
