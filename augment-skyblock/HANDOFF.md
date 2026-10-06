# 인수인계 (이전 세션 → 새 세션, 2026-10-07)

이전 Claude Code 세션(session_013bSaQ9syve2dqaKQQoPSk7)에서 이 프로젝트를 만들어 온 기록이다. 새 세션은 이 파일과 README.md 를 먼저 읽는다.

## 사용자와 규칙
- 사용자는 친구 몇 명과 이 서버를 같이 하는 한국인. 답은 **한국어 반말**로, 짧고 바로 할 일 위주로. 시각은 **한국 시간(KST)** 으로 말한다.
- 기다리게 하는 걸 싫어한다. 오래 걸리면 중간에 상황을 알리고, 끝난 것부터 먼저 보낸다. 모르는 건 솔직히.
- 작업 브랜치 `claude/gallant-noether-j4j8t5` 에서만 커밋·푸시. PR 만들지 않는다. `config.json`(실제 API 키) 절대 커밋 금지.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 와 `Claude-Session: <새 세션 주소>`. 커밋·문서에 모델 이름 쓰지 않기.
- 저장소: GitHub `Armgimozi/nai-cg-maker` (공개), 프로젝트는 `augment-skyblock/`.

## 지금 사용자 서버 상태 (배포판 = 커밋 4561100 의 dist/)
- 콘텐츠 판 8 jar(`dist/AugmentSkyblock.jar`, sha256 7032a64e…) + 새 맵(제단 재배치판, 하늘 섬 128 + 하늘 네더 섬 23).
- 사용자는 서버 폴더를 통째로 지우고 `AugmentSkyblock-Server.zip` 으로 다시 깔았다 (Windows, start.bat → start.ps1).
- 친구 접속: Radmin VPN 은 실패(사용자 PC 에 "다른 앱이 연결을 차단" 경고). **playit.gg** 로 전환, 터널 주소 `pgsql-greenwich.tun.ply.gg` (Minecraft Java, 로컬 25565).
- playit 은 8163(리소스팩) 을 못 열어서 config 의 `resource-pack.url` 에 커밋 고정 주소를 넣으라고 안내했다:
  `https://raw.githubusercontent.com/Armgimozi/nai-cg-maker/45611006c2a472720cfa89755a85c8ad45566584/augment-skyblock/dist/AugmentSkyblock-pack.zip`
  (jar 의 pack.zip 과 SHA-1 0f20c173… 일치 확인). **jar 의 팩이 바뀌면 이 주소도 새 커밋으로 바꿔 줘야 한다.**
- 저장소 기본값은 `pvp=true` 로 바꿨지만 사용자 서버의 server.properties 는 직접 고치라고 안내함(했는지 모름).
- 제단 `altar.single-use` 를 `player` 로 바꾸라고 안내함(친구가 같은 제단을 각자 한 번). op 가 날아가서 `/증강관리 리로드` 가 안 됐을 가능성 → 콘솔에서 `증강관리 리로드` 또는 `op 닉` 안내. 배포 기본값을 player 로 바꿀지 물었고 **답 없음**.
- 사용자 Radmin IP 26.234.170.149 (지금은 안 씀).

## 들어 있는 기능 (요약, 자세한 건 README.md)
- Paper 1.21.4 플러그인(Java 21, Gradle: `cd augment-skyblock/plugin && ./gradlew build -q --offline`) + 생성 맵 + 리소스팩(`pack/gen_pack.py`).
- 증강 78개(실버 29·골드 30·프리즘 19). 제단 하늘 18(10/6/2) + 하늘 네더 6(2/2/2), 고르게 섞어 배치, 가장 가까운 건 실버. 전투 확률 효과는 결정적(N번째 타격마다). 탱크엔진(프리즘, 플레이어 처치마다 최대 체력 +1, 상한 없음).
- 무기 69 + 곡괭이 7 (pickaxe 등급별 드롭, 자동 제련, 운석/프리즘은 채굴 속도 속성). 내구도·모루 수리(자기 재료/같은 아이템), 숫돌 같은 아이템만, 수선 책(섬 상자 4, 거미 굴 무한 책 2, 보스 40%, 보루, 낚시). 무한 화살은 뇌천궁(storm_longbow)·별무리 활(prism_bow)만.
- 스킬 입력: 우클릭=1, 웅크리기+우클릭=2, 웅크리기+좌클릭=3(프리즘 궁극기). 활: 웅크리기+당기기=1, 웅크리기+좌클릭=2. 스킬은 지금 **플레이어에게 안 맞음**(Targets.java) — PvP 켜도 평타·활만. 바꿀지 물었고 답 없음.
- 하늘 네더: 플러그인이 만드는 `world_augsky_nether`(배치 판 2), 포털 연결, 공허 안전장치.
- 콘텐츠 갱신: `AugSky.CONTENT_VERSION`(지금 8) 올리면 기존 서버의 yml 을 old-content-vN 으로 옮기고 새 안내서로 바꾼다. skills.yml 등 콘텐츠 yml 을 바꾸면 반드시 올린다.
- 배포: `python3 tools/make_dist.py <지은 world 폴더>` (네더 배치 판·제단 수·미사용 검사, server/ 폴더를 그대로 묶음). 도감: `tools/make_catalog.py` → 아티팩트 https://claude.ai/artifact/QDHmnDGaASTnGwQxibWhtP (판 4).

## 진행 중: 스킬 이펙트 화려하게 (사용자 요청: "적어도 고등급 무기는 화려해야")
- 등급별(기본<섬<균열<보스<프리즘)로 화려하게: 새 패키지 `kr/augsky/vfx`(표시 엔티티 스프라이트, 원소 팔레트, 프리즘/보스 전용 연출, 보스 몹 예고), `pack/vfx_assets.py`(마법진·베기 궤적·충격파 텍스처), 셰이더 수정. skills.yml 은 안 바꿈(엔진 기본값 + 자바 시그니처).
- 소스 변경은 **`wip/vfx-src-wip.patch`** 에 보관(14a1d4e 기준, 현재 브랜치에 깨끗이 적용됨 확인). 적용: `git apply augment-skyblock/wip/vfx-src-wip.patch` → `python3 pack/gen_pack.py` → gradle build. 빌드는 됐었다.
- 1차 다듬기 심사 7/10(등급 순서는 OK). 남은 지적(2차 다듬기 도중 끊김, 일부는 이미 손댔을 수 있음):
  기본 마법탄이 전과 같음 / void_slash·서리 군주 m_frozen_beam 이 가는 선 / m_blizzard 의 하늘 고리가 흰 줄로 보임 / heavens_spear 잔광이 너무 빨리 사라짐 / 바닥 그림의 검은 테두리(알파 번짐) / 반투명 흰 사각형 잔상 / world_creation 1인칭 가림 / 프리즘 스킬 마법진이 다 비슷 / 프리즘 별이 납작 / 큰 바닥 그림 해상도 / 섬 등급이 아직 밋밋 / 팩 없는 클라이언트·밤·4인 성능 재확인.
- 아직 안 한 것: 2차 다듬기, 코드 검토(엔티티 누수·틱 비용), 합치기(콘텐츠 판은 skills.yml 안 바꿨으면 안 올려도 됨, 팩이 바뀌므로 리소스팩 url 갱신 필요), 배포.
- 사용자에게 "1) 1차본을 직접 간단히 확인하고 바로 받기 / 2) 한도 풀린 뒤 다 끝내고 받기" 를 물었고 **답 없음**.

## 주의
- 이전 세션의 테스트 도구(Paper 서버 파일, mineflayer 봇, 실제 클라이언트, 맵을 지은 d7 월드)는 그 컨테이너의 /tmp 에만 있었다. 새 세션에서 서버 시험이나 맵 재생성이 필요하면 다시 갖춰야 한다(Paper 1.21.4 jar 는 api.papermc.io, mineflayer 는 npm). dist/ 의 zip 안에 지은 맵(world, world_augsky_nether)이 들어 있으니 시험 월드는 거기서 꺼내 쓰면 된다.
- 보조 에이전트(워크플로·서브에이전트)는 계정 주간 한도에 걸려 **2026-10-09 18:00 UTC(10일 03:00 KST)** 까지 실패한다.
- mineflayer(1.21.4): 웅크리기는 `entity_action` start_sneaking 을 직접 보내야 하고, 액션바는 raw `action_bar` 패킷으로만 온다.
- Windows 시작기: start.bat(ASCII) → start.ps1(UTF-8 BOM). server/README.txt 는 UTF-8 BOM + CRLF 를 지켜서 고친다.
