# 블록 소울 (Block Soul)

혼자 하는 소울류 마인크래프트 서버. 손으로 설계한 어두운 세계를 플러그인이 코드로 짓고, 구르기·막기·쳐내기·화톳불·에스트·소울·패턴 보스를 바닐라 클라이언트 그대로 한다.

- 서버: Paper 1.21.11 빌드 132 (고정) + 이 플러그인 (`Soulslike.jar`) + 서버 리소스팩. Java 21.
- 접속: 아무것도 깔지 않은 마인크래프트 자바 에디션 1.21.11.
- 설계: [`DESIGN.md`](DESIGN.md) (전체 명세), [`ART_DIRECTION.md`](ART_DIRECTION.md) (그림·글 규칙).

## 지금 판: M0 기반과 점검

접속하면 리소스팩을 받고 시험 방에 선다. 화면은 고딕 촛불 말씨 (깊은 검은 옻칠 판, 촛불 기운, 단조 장식, 명조·가라몽 글꼴) 다. 왼쪽 위에 다크 소울처럼 체력·마나·스태미나 막대 (세 잎 단조 장식, 검은 심에 흐린 빛 줄의 거무칙칙한 여러 색) 가 있고 달리면 스태미나 막대가 준다 (소울 수는 오른쪽 아래). 처음 들어오면 세계의 난이도와 PvP 를 고르고 출신 (여섯) 을 고른다. 웅크리기 키를 짧게 눌렀다 떼면 구른다 (시제품). 시험 방의 화톳불에서 쉬면 소울로 레벨을 올린다 (능력치 여섯). 죽으면 핏빛 "YOU DIED". 지도·적·보스·에스트는 아직 없다. 관문은 `DESIGN.md` 13.4 의 실제 클라이언트 점검이다.

설계 문서를 쓴 뒤 정한 것 (문서와 다르면 이쪽이 앞선다):

| 항목 | 정한 것 |
|---|---|
| 제목 | 블록 소울 (영어 Block Soul, 2026-10-08 사용자 결정으로 스퀘어 소울에서 바뀜). 팩 설명과 서버 목록 이름이 이것이다. 예전 가제 "식은 가마" (Cold Kiln) 는 마지막 지역 (R7) 의 이름으로만 남는다 |
| 난이도 | 처음 들어온 사람 (또는 관리자) 이 고른다: 쉬움·보통·어려움·아주 어려움 (플러그인의 배율. 바닐라 난이도는 늘 normal). PvP 켬/끔도 함께 |
| 마법 | 넣는다 (촉매, 마나 같은 자원, 기억 칸). 설계는 나중이고 M0 에는 없다. HUD·데이터에 마나 막대 자리를 남긴다 |
| 사망 화면 | 한국어 "사망했다" 대신 크고 새빨간 "YOU DIED". 손으로 한 점씩 찍은 픽셀 그림 글자 (`pack/art/you_died.txt`) |
| 화톳불 이동 | 처음부터 (넷째 보스 뒤가 아니다) |
| 에스트 | 바닐라 물약처럼: 단축 슬롯에 두고 우클릭을 누르고 있으면 마신다. 슬롯을 저절로 바꾸지 않는다 |
| 규모 | 짧은 맛보기판부터. 7지역 전체가 아니다 |
| 반지 | 인벤토리의 2×2 제작 칸 자리가 반지 칸 둘 (왼쪽 세로 두 칸, "반지" 글자 없음, 2026-10-08 사용자 결정 B 안). 반지는 아이템이고 그 칸에 넣으면 낀다. 화톳불 휴식 창의 반지 단추는 없다. 2×2 제작은 없다 |
| 영어판 | 영어 번역을 고려하면서 개발한다. 한국어가 원본이고 영어는 소울류 영어판 문체로 따로 쓴다. 클라이언트 언어가 한국어면 한국어, 그 밖에는 영어 |

## 게임 안에서 (지금 판)

- **시작:** 새 세계에 처음 들어온 사람 (`start.setup-by: op` 면 관리자) 에게 "세계를 정한다" 창이 뜬다. 난이도 단추 넷 (쉬움 적 피해 ×0.7·적 HP ×0.8, 보통, 어려움 ×1.25·×1.2, 아주 어려움 ×1.5·×1.4) 과 PvP 체크 칸. 닫으면 우선 보통·PvP 끔이고, 그 사람이 다시 오거나 화톳불에서 쉴 때 다시 묻는다. 나중에 들어온 사람은 "이 세계: 보통 · PvP 끔" 한 줄을 본다. 관리자는 `/souls settings` (창), `/souls settings difficulty <easy|normal|hard|very_hard>`, `/souls settings pvp <on|off>` 로 바꾼다 (`plugins/Soulslike/settings.log` 에 남는다).
- **출신:** 그다음 사람마다 "너는 누구였나" 창 (기사·전사·도적·궁수·마법사·빈털터리, 능력치 여섯과 시작 아이템이 한눈에). 시작 아이템은 한 번만 받는다. 창을 닫으면 출신 없이 시작 자리 둘레만 걷고, 웅크리기 키를 짧게 누르면 창이 다시 뜬다. 레벨을 하나도 올리지 않았으면 화톳불 휴식 창에서 **한 번** 다시 고를 수 있다. 관리자 `/souls origin reset <이름>` 은 시험용으로 출신을 지운다.
- **레벨:** 시험 방 시작 자리 동쪽 여섯 칸의 캠프파이어 (시험 방 화톳불) 를 오른쪽 클릭 → 휴식 창 → "레벨 올리기" (능력치마다 "+", 다음 레벨 비용, 미리보기) / "능력치". 어디서나 `/stats`. 적이 아직 없어 소울은 `/souls souls <이름> add <n>` (관리자) 로 받는다.
- **반지:** 인벤토리 (E) 의 인물 그림 오른쪽 세로 두 칸이 반지 칸이다. 반지를 들고 누르거나, 가방의 반지를 웅크리고 누르면 끼고, 아무 때나 뺀다. 창을 닫아도, 나갔다 와도, 죽어도, 서버를 다시 켜도 끼워져 있다. 이야기가 정해지기 전이라 세계에는 반지가 없고, 시험 반지 셋만 시험 명령으로 얻는다 (`/soulstest ring give test_stamina` — 스태미나 회복 +20% 가 지금 듣는다. `test_poise`·`test_parry` 는 강인도·쳐내기 체계가 생길 때 듣는다). DESIGN 9.4.
- **조작:** 웅크리기 키를 짧게 눌렀다 떼면 구르기 (누르고 있으면 웅크리기·강공격 조합), F 는 무기 기술 자리. 웅크리기를 "전환" 으로 쓰면 `config.yml` 의 `controls.roll-key: f` 나 `both`.
- **지금 듣는 능력치 효과:** 체력 (최대 HP·방어력), 정신 (마법 저항. 최대 마나는 막대 길이만), 기력 (스태미나·회복), 근력 (적을 칠 때 피해·장비 무게 한도), 민첩 (이동 속도·공격 속도), 지능 (해로운 효과·불 길이. 술법 세기는 술법 M5 전까지 숫자만). 자세한 것은 `DESIGN.md` 5.

## 폴더

```
plugin/   Gradle 플러그인 (kr.souls). 리소스: paper-plugin.yml, config.yml, content/, datapack/soulsdp/,
          lang/ko.yml (게임 문구, 한국어 원본), lang/en.yml (영어), lang/names.yml (고유 이름의 영어 표기)
pack/     리소스팩 생성기 (gen_pack.py, langpack.py 문구 → 팩 언어 파일, fonts.py 게임 글꼴 (미리 그린 명조·가라몽),
          typeset.py 팩 글꼴로 창 제목·열 맞춤 짜기, hud.py HUD 그림 글자·사망 제목, bar_styles.py HUD 막대 색 짜임,
          gui_skin.py 단축 슬롯·창·단추·설명 칸,
          uidraw.py 2 배 UI 그림판, shaders.py 글꼴·GUI 셰이더, icons.py 아이템 그림·모형·입자, palette.py, artlint.py,
          art/ 손으로 찍은 그림)
server/   배포할 서버 폴더 (start.bat → start.ps1, start.sh, server.properties, bukkit.yml, config/paper-global.yml, README.txt)
tools/    make_dist.py (배포 묶기), textlint.py (글 검사, 한국어·영어), langcheck.py (문구 관문), run_tests.sh + bots/ (봇 시험),
          client/ (실제 클라이언트로 찍기)
dist/     묶은 결과: Soulslike.jar, Soulslike-Server.zip, packs/<sha1>.zip
```

## 빌드

필요한 것: JDK 21, Python 3 (Pillow, numpy, PyYAML, freetype-py). 처음 팩을 만들 때 글꼴 넷을 github.com/google/fonts 에서 받는다 (아래 "글꼴").

```sh
python3 tools/make_dist.py            # 아래 셋을 차례로 하고 관문을 지나면 dist/ 에 묶는다
```

하나씩 할 때:

```sh
python3 pack/gen_pack.py              # 그림 → artlint → 정렬 zip → plugin/src/main/resources/pack.zip, glyphs.yml, dist/packs/<sha1>.zip
cd plugin && ./gradlew build          # → plugin/build/libs/Soulslike.jar (pack.zip 이 jar 안에 들어간다)
python3 tools/make_dist.py --no-build # 관문만 보고 묶는다
```

`make_dist.py` 는 글 검사(textlint), 문구 관문(langcheck), 그림 검사(artlint), 낡은 jar, 시험용 설정(`debug.test-mode`, `pack.serve-port`), 팩 형식 75·점검한 셰이더 목록 (`pack/shaders.py` 의 `ALLOWED`, `DESIGN.md` 10.8)·참조, 그림 글자 표, 서버 폴더 인코딩 규칙과 `server.properties` 값 가운데 하나라도 어긋나면 아무것도 쓰지 않고 멈춘다.

## 글꼴 (FONTS)

모든 글 (바닐라 화면·채팅·설명 칸까지) 을 명조·가라몽으로 그린다. TTF 는 팩에 넣지 않고 `pack/fonts.py` 가 FreeType 으로 GUI 한 픽셀에 4 텍셀로 미리 그린 bitmap 글꼴을 넣는다. 팩의 글꼴 셰이더 (`rendertype_text.fsh`) 가 그 글자를 넓이 평균으로 읽어 어느 GUI 배율에서나 바탕선과 굵기가 고르다 (이 셰이더가 없으면 글이 보이지 않는다). 자세한 것은 `DESIGN.md` 10.9.

| 글꼴 | 쓰는 곳 | 사용 허락 |
|---|---|---|
| EB Garamond | 본문 로마자, 소울 숫자 | SIL Open Font License 1.1 |
| Noto Serif KR | 본문 한글 | SIL Open Font License 1.1 |
| Cinzel | 제목 로마자 (창·설정 화면 제목, 무기·보스 이름) | SIL Open Font License 1.1 |
| Nanum Myeongjo ExtraBold | 제목 한글 | SIL Open Font License 1.1 |

- 원본은 github.com/google/fonts (`ofl/`) 에서 빌드 때 `~/.cache/souls-fonts/ofl` 에 받고 (`SOULS_FONT_CACHE` 로 바꾼다) sha256 으로 확인한다. 다르면 팩을 만들지 않는다 (`pack/fonts.py` 의 `SOURCES`).
- 팩에는 그린 그림 (`assets/souls/textures/font/text_*.png`) 만 들어가고, OFL 원문 넷은 팩의 `assets/souls/font/licenses/`, 알림은 팩 뿌리의 `FONTS-OFL.txt` 에 있다.
- 창 제목 (일시 정지·설정 화면·인벤토리·상자·제작대) 은 언어 파일이 글꼴을 고를 수 없어 팩이 YAML 의 글을 기본 글꼴 안의 제목 글자로 바꿔 쓴다 (`pack/typeset.py`). 글은 `lang/*.yml` 에만 있다.

## 문구와 영어판

플레이어가 보는 글은 모두 언어 열쇠다 (`DESIGN.md` 10.3, 10.9, 12.5). 플러그인은 `Component.translatable("souls.<열쇠>")` 을 보내고, 클라이언트가 리소스팩의 `assets/souls/lang/ko_kr.json`·`en_us.json` 에서 자기 언어의 글을 고른다. 아이템 이름·설명도 같다. 팩을 받기 전에 보이는 글 (팩 안내, 팩 때문에 쫓아낼 때) 만 서버가 그 사람의 언어로 채운다. 팩이 아직 없을 때 보이는 대체 글도 한 사람에게 가는 글은 그 사람의 언어다 (아이템만 영어). 서버 목록 이름은 게임 제목 "블록 소울 · Block Soul" (`pack.description` 두 언어).

- 글을 고칠 때: `plugin/src/main/resources/lang/ko.yml` 과 `en.yml` 을 함께 고친다 (열쇠, 맨 앞 꼴 태그, `<자리>`, 목록 줄 수가 같아야 한다). 영어는 직역하지 않고 짧고 건조한 옛 말투로. 고유 이름은 `lang/names.yml` 대로.
- 그다음 `python3 tools/make_dist.py` (팩과 jar 를 함께 다시 만든다). 서버 폴더에는 문구 파일이 없다.
- 관문: `python3 tools/langcheck.py` (두 언어의 짝, Java 의 한글 문자열과 번역 안 되는 글, 부르는 열쇠와 자리 이름, 콘텐츠 id 의 열쇠, 낡은 팩 언어 파일, 자리 폭), `python3 tools/textlint.py` (문체, 고유 이름 표기). 하나라도 오류면 `make_dist` 가 묶지 않는다. Java 에서 열쇠를 만들어 부르면 그 줄에 `// lang-dyn: <glob>`, 봇이 읽는 기계 글에는 `// lang-machine` (`DESIGN.md` 13.7).
- 실제 클라이언트로 두 언어 보기: `MC_LANG=en_us tools/client/run_client.sh …` (`dist/screenshots/i18n/`). UI 전체 그림은 `tools/client/ui_shots.sh` (`dist/screenshots/ui_final/`).

## 배포

1. `python3 tools/make_dist.py`
2. `dist/packs/<sha1>.zip` 을 커밋·푸시한다. 플러그인은 `config.yml` 의 `pack.url` 틀에 jar 안 팩의 SHA-1 을 채워 그 주소로 팩을 보낸다 (파일 이름이 내용으로 정해지므로 캐시 문제가 없다). 올린 뒤 `python3 tools/make_dist.py --no-build --check-url` 로 주소가 이 팩을 내주는지 본다.
3. `dist/Soulslike-Server.zip` 을 풀고 `start.bat` (윈도우) 또는 `start.sh` (맥/리눅스). 처음 한 번 Java 21 과 Paper 를 받는다 (Paper 는 sha256 으로 확인). 자세한 것은 압축 안의 `README.txt`.

## 시험

- 게임 안: `/souls check` (데이터팩, 바이옴, 난이도, 게임 규칙, 시험 방, 팩, 그림 글자). `/soulstest` 는 `debug.test-mode: true` 일 때만 (봇 시험용).
- 봇: `tools/run_tests.sh` (`tools/bots/`, mineflayer 4.39), 지연 프록시 `tools/bots/lagproxy.js`.
- 실제 클라이언트: `tools/client/m0_shots.sh` (13.4 점검 그림, `dist/screenshots/m0/`).
- 사망 화면 YOU DIED 의 세 판 (DESIGN 5.6, 16절 질문 4) 은 `plugin/src/main/resources/config.yml` 의 `death.title`·`death.screen-fade` 로 고른다 (기본: 서서히 나타나는 사망 화면 문구 줄). `gen_pack.py` 와 `make_dist.py` 가 같은 값을 읽어 팩을 만든다.
- 글·그림: `python3 tools/textlint.py`, `python3 tools/langcheck.py`, `python3 pack/artlint.py`. 봇 시험의 `lang_check` 가 둘을 돌리고, `lang` 시나리오가 영어 클라이언트로 들어와 번역 열쇠와 서버가 채운 글을 본다.
