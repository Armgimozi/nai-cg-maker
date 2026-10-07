# 인수인계 (이전 세션 → 새 세션, 2026-10-07)

이전 Claude Code 세션(session_013bSaQ9syve2dqaKQQoPSk7)에서 이 프로젝트를 만들어 온 기록이다. 새 세션은 이 파일과 README.md 를 먼저 읽는다.

## 사용자와 규칙
- 사용자는 친구 몇 명과 이 서버를 같이 하는 한국인. 답은 **한국어 반말**로, 짧고 바로 할 일 위주로. 시각은 **한국 시간(KST)** 으로 말한다.
- 기다리게 하는 걸 싫어한다. 오래 걸리면 중간에 상황을 알리고, 끝난 것부터 먼저 보낸다. 모르는 건 솔직히.
- 작업 브랜치 `claude/gallant-noether-j4j8t5` 에서만 커밋·푸시. PR 만들지 않는다. `config.json`(실제 API 키) 절대 커밋 금지.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 와 `Claude-Session: <새 세션 주소>`. 커밋·문서에 모델 이름 쓰지 않기.
- 저장소: GitHub `Armgimozi/nai-cg-maker` (공개), 프로젝트는 `augment-skyblock/`.

## 지금 사용자 서버 상태 (사용자가 받은 배포판 = 커밋 4561100 의 dist/. 그 뒤 dist/ 는 제단 player·PvP 스킬 판으로 다시 만들었지만 아직 사용자에게 안 보냈을 수 있음)
- 콘텐츠 판 8 jar(`dist/AugmentSkyblock.jar`, sha256 7032a64e…) + 새 맵(제단 재배치판, 하늘 섬 128 + 하늘 네더 섬 23).
- 사용자는 서버 폴더를 통째로 지우고 `AugmentSkyblock-Server.zip` 으로 다시 깔았다 (Windows, start.bat → start.ps1).
- 친구 접속: Radmin VPN 은 실패(사용자 PC 에 "다른 앱이 연결을 차단" 경고). **playit.gg** 로 전환, 터널 주소 `pgsql-greenwich.tun.ply.gg` (Minecraft Java, 로컬 25565).
- playit 은 8163(리소스팩) 을 못 열어서 config 의 `resource-pack.url` 에 커밋 고정 주소를 넣으라고 안내했다:
  `https://raw.githubusercontent.com/Armgimozi/nai-cg-maker/45611006c2a472720cfa89755a85c8ad45566584/augment-skyblock/dist/AugmentSkyblock-pack.zip`
  (jar 의 pack.zip 과 SHA-1 0f20c173… 일치 확인). **jar 의 팩이 바뀌면 이 주소도 새 커밋으로 바꿔 줘야 한다.**
- 저장소 기본값은 `pvp=true` 로 바꿨지만 사용자 서버의 server.properties 는 직접 고치라고 안내함(했는지 모름).
- 제단 `altar.single-use` 배포 기본값을 `player` 로 바꿨다(커밋 "제단 기본값 player, PvP 에서 스킬 적용"). 사용자 서버의 config.yml 은 직접 고치라고 안내함. op 가 날아가서 `/증강관리 리로드` 가 안 됐을 수 있음 → 콘솔에서 `증강관리 리로드` 또는 `op 닉` 안내.
- 사용자 Radmin IP 26.234.170.149 (지금은 안 씀).

## 들어 있는 기능 (요약, 자세한 건 README.md)
- Paper 1.21.4 플러그인(Java 21, Gradle: `cd augment-skyblock/plugin && ./gradlew build -q --offline`) + 생성 맵 + 리소스팩(`pack/gen_pack.py`).
- 증강 78개(실버 29·골드 30·프리즘 19). 제단 하늘 18(10/6/2) + 하늘 네더 6(2/2/2), 고르게 섞어 배치, 가장 가까운 건 실버. 전투 확률 효과는 결정적(N번째 타격마다). 탱크엔진(프리즘, 플레이어 처치마다 최대 체력 +1, 상한 없음).
- 무기 69 + 곡괭이 7 (pickaxe 등급별 드롭, 자동 제련, 운석/프리즘은 채굴 속도 속성). 내구도·모루 수리(자기 재료/같은 아이템), 숫돌 같은 아이템만, 수선 책(섬 상자 4, 거미 굴 무한 책 2, 보스 40%, 보루, 낚시). 무한 화살은 뇌천궁(storm_longbow)·별무리 활(prism_bow)만.
- 스킬 입력: 우클릭=1, 웅크리기+우클릭=2, 웅크리기+좌클릭=3(프리즘 궁극기). 활: 웅크리기+당기기=1, 웅크리기+좌클릭=2.
- PvP(기본 pvp=true): 플레이어가 직접 쓴 스킬·무기 패시브·증강 효과가 다른 플레이어에게도 들어간다(Targets.isEnemy, world.getPVP). 플레이어→플레이어 추가 피해는 `pvp.skill-damage`(기본 0.5) 배. 처형(즉사)은 플레이어 제외, 소환수는 플레이어를 노리지 않음. 치유·버프(isFriend)는 여전히 모든 플레이어에게.
- 하늘 네더: 플러그인이 만드는 `world_augsky_nether`(배치 판 2), 포털 연결, 공허 안전장치.
- 콘텐츠 갱신: `AugSky.CONTENT_VERSION`(지금 8) 올리면 기존 서버의 yml 을 old-content-vN 으로 옮기고 새 안내서로 바꾼다. skills.yml 등 콘텐츠 yml 을 바꾸면 반드시 올린다.
- 배포: `python3 tools/make_dist.py <지은 world 폴더>` (네더 배치 판·제단 수·미사용 검사, server/ 폴더를 그대로 묶음). 도감: `tools/make_catalog.py` → 아티팩트 https://claude.ai/artifact/QDHmnDGaASTnGwQxibWhtP (판 4).

## 스킬 이펙트 (적용됨, 입자 방식)
- 사용자가 마법진 같은 리소스팩 그림 말고 "마크에이지 스킬처럼" 입자로 그리는 방식을 원했다. 그래서 `kr/augsky/vfx` 연출 층을 넣되 팩 그림 조각(sprite)은 끄고(`vfx.sprites` 기본 false, 팩에 이펙트 모델도 없음) 입자만 쓴다. 리소스팩은 그대로라 playit 용 팩 주소도 그대로다.
- 입자 판 손본 곳: 두께 있는 초승달 참격(Kit.slashDust), 마법진 대신 바닥 입자 회오리(swirlDust), 나선 빛기둥·광선, 날아가는 검기(slashWave), 입자 예산 1.8배(CastFx.particleBoost), 반쯤 묻혀 솟는 블록이 새까맣던 문제(한 칸 위 빛 사용).
- 설정: config `vfx.enabled`, `vfx.density`(0.3~1.5). skills.yml 은 안 바꿔서 콘텐츠 판은 8 그대로.
- 확인: 실제 클라이언트 화면으로 등급별 스킬을 찍어 봄(공허 베기·지진·프리즘 궁극기·서리 군주·화염 대검 등), 시전 뒤 남는 연출 엔티티 0, 오류 0, PvP 스킬 피해 시험 통과.
- 예전 팩 그림판(마법진) 소스는 커밋 8622a88 의 wip/vfx-src-wip.patch 에만 남아 있다.

## 주의
- 이전 세션의 테스트 도구(Paper 서버 파일, mineflayer 봇, 실제 클라이언트, 맵을 지은 d7 월드)는 그 컨테이너의 /tmp 에만 있었다. 새 세션에서 서버 시험이나 맵 재생성이 필요하면 다시 갖춰야 한다(Paper 1.21.4 jar 는 api.papermc.io, mineflayer 는 npm). dist/ 의 zip 안에 지은 맵(world, world_augsky_nether)이 들어 있으니 시험 월드는 거기서 꺼내 쓰면 된다.
- 보조 에이전트(워크플로·서브에이전트)는 계정 주간 한도에 걸려 **2026-10-09 18:00 UTC(10일 03:00 KST)** 까지 실패한다.
- mineflayer(1.21.4): 웅크리기는 `entity_action` start_sneaking 을 직접 보내야 하고, 액션바는 raw `action_bar` 패킷으로만 온다.
- Windows 시작기: start.bat(ASCII) → start.ps1(UTF-8 BOM). server/README.txt 는 UTF-8 BOM + CRLF 를 지켜서 고친다.
