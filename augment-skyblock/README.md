# 증강 스카이블럭

친구들과 함께하는 마인크래프트 자바 에디션 **1.21.4** 스카이블럭 서버입니다. Paper 플러그인과 미리 지어 둔 맵으로 이루어져 있습니다.

- **증강 77개**: 실버 29, 골드 30, 프리즘 18. 맵에 있는 제단에서 제물을 바치고 3개 중 하나를 고릅니다.
- **죽으면 아이템을 떨어뜨립니다.** 지키려면 증강이 필요합니다: 단단한 주머니(핫바 칸), 무기 수호, 갑옷 결속, 보물 결속, 경험 보존, 영혼 결속(전부).
- **무기 61종, 스킬 120개**: 우클릭 스킬과 F키 스킬이 있고, 작업대에서 섬의 재료로 만듭니다.
- **새로운 몬스터 22종**: 밤에 섬에 나오는 변종, 균열 섬 3곳의 몬스터, 보스 3마리.
- **맵**: 시작의 섬, 모래섬, 숲의 섬, 제단 3곳, 균열 3곳, 끝의 섬.

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
2. 밤에 몬스터를 잡거나 돌을 캐서 **증강 파편**을 모읍니다.
3. 빛기둥을 따라 다리를 놓아 **실버 제단**(동쪽 42m)에서 증강을 고릅니다. 골드 제단은 북쪽 98m, 프리즘 제단은 남동쪽 177m 입니다.
4. 섬 재료로 무기를 만들고, **균열**의 몬스터에게서 정수를 모아 더 강한 무기와 보스 **소환석**을 만듭니다.
5. 보스를 잡으면 **프리즘 결정**과 증강권을 얻습니다. 프리즘 결정은 프리즘 제단의 제물이자 최상위 무기의 재료입니다.

무기에 RPG 식 등급은 없습니다. 무기는 **얻는 곳**으로만 나뉩니다: 섬 초반 → 섬 재료 → 균열 정수 → 보스 · 프리즘 결정.

![무기](dist/preview-weapons.png)

## 폴더 구성

```
augment-skyblock/
  plugin/                 Paper 플러그인 (Java 21, Gradle)
    src/main/java/kr/augsky/
      augment/            증강: 정의, 수치 합산, 효과 이벤트, 저장
      altar/              제단 화면(증강 선택, 다시 뽑기, 도감), 제단 보호, 프리즘 빛기둥
      weapon/             무기 아이템, 우클릭/F키 스킬, 패시브
      skill/              스킬 엔진 (베기, 투사체, 광선, 돌진, 운석, 연쇄, 장판, 소환 ...)
      mob/                커스텀 몬스터, 균열 스폰, 보스바, 보스 소환대
      item/               파편/결정/증강권/정수/소환석, 조합법, 바닐라 용도 차단
      map/                맵 짓기 (/증강관리 맵생성)
      pack/               리소스팩 HTTP 배포
    src/main/resources/   augments.yml, weapons.yml, skills.yml, mobs.yml, items.yml, config.yml
  pack/gen_pack.py        무기/아이템 텍스처를 코드로 그려 리소스팩을 만든다
  server/                 서버 zip 에 들어가는 start.bat, start.sh, server.properties, README.txt
  tools/make_dist.py      dist/ 의 배포 파일을 묶는다
  tools/render_map.py     맵을 위에서 본 그림을 만든다
  dist/                   배포 파일
```

## 내용 바꾸기

증강, 무기, 스킬, 몬스터는 전부 YAML 한 항목씩입니다. 서버의 `plugins/AugmentSkyblock/` 에서 고치고 게임 안에서 `/증강관리 리로드` 하면 됩니다. 각 파일 맨 위에 쓸 수 있는 효과와 부품이 정리되어 있습니다.

- 증강 하나 추가: `augments.yml` 에 `tier`, `name`, `icon`, `description`, `effects` 를 적습니다. 효과는 `attribute`, `lifesteal`, `ore_gen`, `double_jump` 처럼 이미 있는 종류를 조합합니다.
- 무기 하나 추가: `weapons.yml` 에 항목을 적고 `skill` 에 `skills.yml` 의 스킬 id 를 넣습니다. 그 뒤 `pack/gen_pack.py` 를 돌리면 `type` 과 `element` 에 맞는 텍스처가 생깁니다.
- 스킬 하나 추가: `skills.yml` 에 `cone`, `projectile`, `rain` 같은 부품을 이어 붙입니다.

## 다시 빌드하기

```sh
cd pack && python3 gen_pack.py             # 리소스팩 (Pillow, PyYAML 필요) → plugin/src/main/resources/pack.zip
cd plugin && ./gradlew build               # 플러그인 → plugin/build/libs/AugmentSkyblock.jar (윈도우는 gradlew.bat)
python3 tools/make_dist.py <world 폴더>     # 배포 zip
```

맵은 빈 공허 월드(이 폴더의 `server.properties` 설정)에서 서버를 켜고 콘솔에 `augadmin buildmap` 을 입력하면 지어집니다.

## 확인한 것

이 컨테이너에서 Paper 1.21.4 서버를 실제로 켜고, 테스트용 봇(mineflayer)으로 접속해 확인했습니다.

- 시작 보급, 실버/골드 제단: 증강권 사용, 파편과 금 주괴 제물, 3개 중 선택, 다시 뽑기, 획득 공지
- 무기 61종의 우클릭/F키 스킬 전부 실행 (서버 오류 없음), 표적 몬스터에게 실제 피해가 들어가는 것
- 조합법: 일반 조합, 무기 강화 조합, 다른 무기로 강화 시도 차단, 바닐라 아이템으로 위조 차단
- 커스텀 몬스터 소환, 균열 스폰, 보스 소환대 → 보스 능력 사용 → 처치 보상(함께 싸운 사람 각자)
- '미다스의 손' 증강: 조약돌 생성기 40번 중 9번 광석(다이아 포함), 증강 없이는 30번 모두 조약돌
- '공허 수호' 증강: 공허로 떨어지면 부활 지점으로 돌아옴

확인하지 못한 것: 실제 마인크래프트 화면(리소스팩 모델이 손에 들렸을 때의 모양, 파티클 연출), 이단 점프(봇이 비행 토글을 보낼 수 없음), 윈도우에서 `start.bat` 실행.
