# 증강 스카이블럭

친구들과 함께하는 마인크래프트 자바 에디션 **1.21.4** 스카이블럭 서버입니다. Paper 플러그인과 미리 지어 둔 맵으로 이루어져 있습니다.

- **증강 77개**: 실버 29, 골드 30, 프리즘 18. 맵 곳곳의 제단(실버 16 · 골드 9 · 프리즘 5)을 우클릭하면 제물 없이 3개 중 하나를 고르고, 제단은 한 번 쓰면 힘을 잃습니다.
- **죽으면 아이템을 떨어뜨립니다.** 지키려면 증강이 필요합니다: 단단한 주머니(핫바 칸), 무기 수호, 갑옷 결속, 보물 결속, 경험 보존, 영혼 결속(전부).
- **무기 69종 (활 8종 포함), 스킬 130개**: 우클릭 스킬과 F키 스킬. 무기마다 따로 디자인한 3D 모델이고, 보스·프리즘 무기에는 실시간으로 타오르는 아우라가 있습니다.
- **갑옷 9세트**: 2/4세트 효과, 머리에 쓰는 3D 투구.
- **새로운 몬스터 22종**: 밤에 섬에 나오는 변종, 균열 섬의 몬스터, 둥지를 지키는 3D 보스 3마리 (쓰러지면 30분 뒤 부활).
- **맵**: 반지름 약 380m, 떠 있는 섬 86개. 가운데 초원, 서쪽 서리, 동북쪽 화염, 북서쪽 공허, 남쪽 바다 지역.

![보스와 몬스터](dist/screenshots/showcase-bosses.png)

![섬과 제단](dist/screenshots/showcase-world.png)

![무기 (1인칭)](dist/screenshots/showcase-weapons.png)

![갑옷 9세트](dist/screenshots/showcase-armor.png)

![맵](dist/preview-map.png)

## 받을 파일

| 파일 | 내용 |
|---|---|
| `dist/AugmentSkyblock-Server.zip` | **이것만 받으면 됩니다.** 서버 폴더 통째로: `start.bat`, 설정, 플러그인, 맵, 설명서 |
| `dist/AugmentSkyblock-Map.zip` | 맵(`world` 폴더)만 |
| `dist/AugmentSkyblock.jar` | 플러그인만 |
| `dist/AugmentSkyblock-pack.zip` | 리소스팩만 (플러그인이 접속한 사람에게 자동으로 보냅니다) |

켜는 법과 게임 방법은 서버 zip 안의 `README.txt` 에 있습니다. 요약하면 `start.bat` 을 더블클릭하고(처음 한 번 Java 21 과 Paper 를 자동으로 받음) EULA 에 동의한 뒤, 마인크래프트 1.21.4 에서 `localhost` 로 접속합니다.

## 게임 흐름

1. 시작의 섬에서 조약돌 생성기를 만들고 섬을 넓힙니다.
2. 하늘로 솟은 빛기둥(제단)을 향해 다리를 놓습니다. 가장 가까운 실버 제단은 약 50m 거리입니다. 제단은 한 번 쓰면 꺼지므로 친구들과 나눠 씁니다.
3. 지역마다 다른 재료로 무기와 갑옷을 만들고, 균열 섬의 몬스터에게서 정수를 모읍니다.
4. 균열 너머 둥지의 보스를 쓰러뜨려 프리즘 결정, 증강권, 보스 무기와 갑옷을 얻습니다. 보스는 30분 뒤 다시 깨어납니다.
5. 프리즘 결정으로 최상위 무기와 프리즘 갑옷을 만들고, 맵 끝자락의 프리즘 제단을 찾아갑니다.

무기에 RPG 식 등급은 없습니다. 무기는 **얻는 곳**으로만 나뉩니다: 섬 초반 → 섬 재료 → 균열 정수 → 보스 → 프리즘 결정.

![무기](dist/preview-weapons.png)

## 폴더 구성

```
augment-skyblock/
  plugin/                 Paper 플러그인 (Java 21, Gradle)
    src/main/java/kr/augsky/
      augment/            증강: 정의, 수치 합산(갑옷 세트 효과 포함), 효과 이벤트, 저장
      altar/              일회용 제단(월드 폴더에 기록), 증강 선택 화면, 증강권, 도감
      armor/              갑옷 세트: 아이템, 세트 효과, 입자
      weapon/             무기 아이템, 우클릭/F키 스킬, 패시브, 활
      skill/              스킬 엔진 (베기, 투사체, 광선, 돌진, 운석, 연쇄, 장판, 소환 ...)
      mob/                커스텀 몬스터, 균열 스폰, 보스 둥지(Lairs), 보스 3D 모델(Rigs)
      item/               파편/결정/증강권/정수, 조합법, 바닐라 용도 차단
      map/                맵 짓기 (/증강관리 맵생성)
      pack/               리소스팩 HTTP 배포
    src/main/resources/   augments, weapons, skills, mobs, items, armor, rigs(자동 생성), config
  pack/
    gen_pack.py           리소스팩을 만든다 (무기, 갑옷, 보스, 아이템, 셰이더)
    wkit.py               복셀로 무기를 짓는 도구 (3D 모델, 움직이는 텍스처, 아우라, 손에 든 자세)
    mc3d.py               3D 아이템 모델 도구와 미리보기 렌더러
    weapons/              무기 디자인 (그룹별 모듈, preview/ 에 미리보기)
    art/                  보스 3D 모델과 갑옷 디자인
    shaders/              알파 252/251/250 픽셀을 스스로 빛나게 하는 셰이더
  server/                 서버 zip 에 들어가는 start.bat, start.sh, server.properties, README.txt
  tools/                  make_dist.py(배포 zip), render_map.py(맵 그림), make_catalog.py(도감 페이지)
  dist/                   배포 파일
```

## 내용 바꾸기

증강, 무기, 스킬, 몬스터는 전부 YAML 한 항목씩입니다. 서버의 `plugins/AugmentSkyblock/` 에서 고치고 게임 안에서 `/증강관리 리로드` 하면 됩니다. 각 파일 맨 위에 쓸 수 있는 효과와 부품이 정리되어 있습니다.

- 증강 하나 추가: `augments.yml` 에 `tier`, `name`, `icon`, `description`, `effects` 를 적습니다. 효과는 `attribute`, `lifesteal`, `ore_gen`, `double_jump` 처럼 이미 있는 종류를 조합합니다.
- 무기 하나 추가: `weapons.yml` 에 항목을 적고 `skill` 에 `skills.yml` 의 스킬 id 를 넣습니다. 모양은 `pack/weapons/` 의 모듈에 `wkit` 으로 지어 `WEAPONS` 에 넣고 `pack/gen_pack.py` 를 돌립니다 (모듈이 없으면 `type` 과 `element` 로 기본 모양을 만듭니다).
- 갑옷 세트 추가: `armor.yml` 에 수치와 세트 효과를 적습니다. 그림은 `pack/art/` 모듈이 그립니다.
- 스킬 하나 추가: `skills.yml` 에 `cone`, `projectile`, `rain` 같은 부품을 이어 붙입니다.

## 다시 빌드하기

```sh
cd pack && python3 gen_pack.py             # 리소스팩 (Pillow, PyYAML 필요) → plugin/src/main/resources/pack.zip
cd plugin && ./gradlew build               # 플러그인 → plugin/build/libs/AugmentSkyblock.jar (윈도우는 gradlew.bat)
python3 tools/make_dist.py <world 폴더>     # 배포 zip
```

맵은 빈 공허 월드(이 폴더의 `server.properties` 설정)에서 서버를 켜고 콘솔에 `augadmin buildmap` 을 입력하면 지어집니다.

## 확인한 것

이 컨테이너에서 Paper 1.21.4 서버를 실제로 켜고, 테스트용 봇(mineflayer)과 실제 마인크래프트 1.21.4 클라이언트(가상 화면)로 접속해 확인했습니다. 마지막 확인은 `dist/AugmentSkyblock-Server.zip` 을 그대로 풀어 켠 서버에서 했습니다.

- 제단: 제물 없이 우클릭하면 바로 3개 중 선택, 고른 뒤 빛기둥이 꺼지고 다시 누르면 "이미 힘을 다했습니다". 서버를 다시 켜도 쓴 제단은 그대로 꺼져 있음
- 증강권 우클릭, 다시 뽑기(무료 횟수 → 파편 3개), 획득 공지
- 갑옷: 서리 세트 4개 → 최대 체력·방어력 세트 효과, 바닐라 아이템과 제작기(crafter)로 보스 갑옷을 위조하지 못함
- 활: 끝까지 당겨 쏜 화살 피해, 일반 화살이 줄지 않음
- 보스 둥지: 가까이 가면 보스가 깨어나 자리를 지킴, 처치하면 30분 시계가 뜨고 둥지 기록에 남음
- 무기 69종과 스킬 130개를 불러오는 데 오류 없음, 조합법 90개 등록
- 실제 클라이언트에서: 복셀 무기(1인칭/3인칭/왼손), 활을 당기는 모습, 보스·프리즘 무기 아우라(밤에도 스스로 빛남), 복셀 보스 3마리, 갑옷 9세트와 복셀 투구 (위 스크린샷)

확인하지 못한 것: 스킬 파티클 연출을 움직이는 화면으로 본 것, 이단 점프(봇이 비행 토글을 보낼 수 없음), 윈도우에서 `start.bat` 실행.
