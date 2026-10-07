# 스퀘어 소울 (Square Soul)

혼자 하는 소울류 마인크래프트 서버. 손으로 설계한 어두운 세계를 플러그인이 코드로 짓고, 구르기·막기·쳐내기·화톳불·에스트·소울·패턴 보스를 바닐라 클라이언트 그대로 한다.

- 서버: Paper 1.21.11 빌드 132 (고정) + 이 플러그인 (`Soulslike.jar`) + 서버 리소스팩. Java 21.
- 접속: 아무것도 깔지 않은 마인크래프트 자바 에디션 1.21.11.
- 설계: [`DESIGN.md`](DESIGN.md) (전체 명세), [`ART_DIRECTION.md`](ART_DIRECTION.md) (그림·글 규칙).

## 지금 판: M0 기반과 점검

접속하면 리소스팩을 받고 시험 방에 선다. 왼쪽 위에 다크 소울처럼 체력·온기·스태미나 막대가 있고 달리면 스태미나 막대가 준다 (소울 수는 오른쪽 아래). F 로 구른다 (시제품). 죽으면 핏빛 "YOU DIED". 지도·적·보스·에스트는 아직 없다. 관문은 `DESIGN.md` 13.4 의 실제 클라이언트 점검이다.

설계 문서를 쓴 뒤 정한 것 (문서와 다르면 이쪽이 앞선다):

| 항목 | 정한 것 |
|---|---|
| 제목 | 스퀘어 소울 (영어 Square Soul). 팩 설명과 서버 목록 이름이 이것이다. 예전 가제 "식은 가마" (Cold Kiln) 는 마지막 지역 (R7) 의 이름으로만 남는다 |
| 난이도 | 아직 정하지 않았다. 문서의 수치를 `config.yml` 값으로 둔다 |
| 마법 | 넣는다 (촉매, 마나 같은 자원, 기억 칸). 설계는 나중이고 M0 에는 없다. HUD·데이터에 마나 막대 자리를 남긴다 |
| 사망 화면 | 한국어 "사망했다" 대신 크고 새빨간 "YOU DIED". 손으로 찍은 그림 글자 |
| 화톳불 이동 | 처음부터 (넷째 보스 뒤가 아니다) |
| 에스트 | 바닐라 물약처럼: 단축 슬롯에 두고 우클릭을 누르고 있으면 마신다. 슬롯을 저절로 바꾸지 않는다 |
| 규모 | 짧은 맛보기판부터. 7지역 전체가 아니다 |
| 영어판 | 영어 번역을 고려하면서 개발한다. 한국어가 원본이고 영어는 소울류 영어판 문체로 따로 쓴다. 클라이언트 언어가 한국어면 한국어, 그 밖에는 영어 |

## 폴더

```
plugin/   Gradle 플러그인 (kr.souls). 리소스: paper-plugin.yml, config.yml, content/, datapack/soulsdp/,
          lang/ko.yml (게임 문구, 한국어 원본), lang/en.yml (영어), lang/names.yml (고유 이름의 영어 표기)
pack/     리소스팩 생성기 (gen_pack.py, langpack.py 문구 → 팩 언어 파일, hud.py 글꼴·사망 제목, gui_skin.py 하트·스태미나
          막대·단축 슬롯·창·단추, icons.py 아이템 그림·모형·입자, palette.py, artlint.py, art/ 손으로 찍은 그림)
server/   배포할 서버 폴더 (start.bat → start.ps1, start.sh, server.properties, bukkit.yml, config/paper-global.yml, README.txt)
tools/    make_dist.py (배포 묶기), textlint.py (글 검사, 한국어·영어), langcheck.py (문구 관문), run_tests.sh + bots/ (봇 시험),
          client/ (실제 클라이언트로 찍기)
dist/     묶은 결과: Soulslike.jar, Soulslike-Server.zip, packs/<sha1>.zip
```

## 빌드

필요한 것: JDK 21, Python 3 (Pillow, numpy, PyYAML).

```sh
python3 tools/make_dist.py            # 아래 셋을 차례로 하고 관문을 지나면 dist/ 에 묶는다
```

하나씩 할 때:

```sh
python3 pack/gen_pack.py              # 그림 → artlint → 정렬 zip → plugin/src/main/resources/pack.zip, glyphs.yml, dist/packs/<sha1>.zip
cd plugin && ./gradlew build          # → plugin/build/libs/Soulslike.jar (pack.zip 이 jar 안에 들어간다)
python3 tools/make_dist.py --no-build # 관문만 보고 묶는다
```

`make_dist.py` 는 글 검사(textlint), 문구 관문(langcheck), 그림 검사(artlint), 낡은 jar, 시험용 설정(`debug.test-mode`, `pack.serve-port`), 팩 형식 75·셰이더 없음·참조, 그림 글자 표, 서버 폴더 인코딩 규칙과 `server.properties` 값 가운데 하나라도 어긋나면 아무것도 쓰지 않고 멈춘다.

## 문구와 영어판

플레이어가 보는 글은 모두 언어 열쇠다 (`DESIGN.md` 10.3, 10.9, 12.5). 플러그인은 `Component.translatable("souls.<열쇠>")` 을 보내고, 클라이언트가 리소스팩의 `assets/souls/lang/ko_kr.json`·`en_us.json` 에서 자기 언어의 글을 고른다. 아이템 이름·설명도 같다. 팩을 받기 전에 보이는 글 (팩 안내, 팩 때문에 쫓아낼 때) 만 서버가 그 사람의 언어로 채운다. 팩이 아직 없을 때 보이는 대체 글도 한 사람에게 가는 글은 그 사람의 언어다 (아이템만 영어). 서버 목록 이름은 게임 제목 "스퀘어 소울 · Square Soul" (`pack.description` 두 언어).

- 글을 고칠 때: `plugin/src/main/resources/lang/ko.yml` 과 `en.yml` 을 함께 고친다 (열쇠, 맨 앞 꼴 태그, `<자리>`, 목록 줄 수가 같아야 한다). 영어는 직역하지 않고 짧고 건조한 옛 말투로. 고유 이름은 `lang/names.yml` 대로.
- 그다음 `python3 tools/make_dist.py` (팩과 jar 를 함께 다시 만든다). 서버 폴더에는 문구 파일이 없다.
- 관문: `python3 tools/langcheck.py` (두 언어의 짝, Java 의 한글 문자열과 번역 안 되는 글, 부르는 열쇠와 자리 이름, 콘텐츠 id 의 열쇠, 낡은 팩 언어 파일, 자리 폭), `python3 tools/textlint.py` (문체, 고유 이름 표기). 하나라도 오류면 `make_dist` 가 묶지 않는다. Java 에서 열쇠를 만들어 부르면 그 줄에 `// lang-dyn: <glob>`, 봇이 읽는 기계 글에는 `// lang-machine` (`DESIGN.md` 13.7).
- 실제 클라이언트로 두 언어 보기: `MC_LANG=en_us tools/client/run_client.sh …` (`dist/screenshots/i18n/`).

## 배포

1. `python3 tools/make_dist.py`
2. `dist/packs/<sha1>.zip` 을 커밋·푸시한다. 플러그인은 `config.yml` 의 `pack.url` 틀에 jar 안 팩의 SHA-1 을 채워 그 주소로 팩을 보낸다 (파일 이름이 내용으로 정해지므로 캐시 문제가 없다). 올린 뒤 `python3 tools/make_dist.py --no-build --check-url` 로 주소가 이 팩을 내주는지 본다.
3. `dist/Soulslike-Server.zip` 을 풀고 `start.bat` (윈도우) 또는 `start.sh` (맥/리눅스). 처음 한 번 Java 21 과 Paper 를 받는다 (Paper 는 sha256 으로 확인). 자세한 것은 압축 안의 `README.txt`.

## 시험

- 게임 안: `/souls check` (데이터팩, 바이옴, 난이도, 게임 규칙, 시험 방, 팩, 그림 글자). `/soulstest` 는 `debug.test-mode: true` 일 때만 (봇 시험용).
- 봇: `tools/run_tests.sh` (`tools/bots/`, mineflayer 4.39), 지연 프록시 `tools/bots/lagproxy.js`.
- 실제 클라이언트: `tools/client/m0_shots.sh` (13.4 점검 그림, `dist/screenshots/m0/`).
- 사망 화면 제목의 두 판 (16절 질문 4) 은 `plugin/src/main/resources/config.yml` 의 `death.title` 하나로 고른다. `gen_pack.py` 와 `make_dist.py` 가 같은 값을 읽어 팩을 만든다.
- 글·그림: `python3 tools/textlint.py`, `python3 tools/langcheck.py`, `python3 pack/artlint.py`. 봇 시험의 `lang_check` 가 둘을 돌리고, `lang` 시나리오가 영어 클라이언트로 들어와 번역 열쇠와 서버가 채운 글을 본다.
