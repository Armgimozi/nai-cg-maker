# 식은 가마 (가제)

혼자 하는 소울류 마인크래프트 서버. 손으로 설계한 어두운 세계를 플러그인이 코드로 짓고, 구르기·막기·쳐내기·화톳불·에스트·소울·패턴 보스를 바닐라 클라이언트 그대로 한다.

- 서버: Paper 1.21.11 빌드 132 (고정) + 이 플러그인 (`Soulslike.jar`) + 서버 리소스팩. Java 21.
- 접속: 아무것도 깔지 않은 마인크래프트 자바 에디션 1.21.11.
- 설계: [`DESIGN.md`](DESIGN.md) (전체 명세), [`ART_DIRECTION.md`](ART_DIRECTION.md) (그림·글 규칙).

## 지금 판: M0 기반과 점검

접속하면 리소스팩을 받고 시험 방에 선다. 달리면 스태미나 막대(경험치 막대 자리)가 준다. F 로 구른다 (시제품). 죽으면 핏빛 "YOU DIED". 지도·적·보스·에스트는 아직 없다. 관문은 `DESIGN.md` 13.4 의 실제 클라이언트 점검이다.

설계 문서를 쓴 뒤 정한 것 (문서와 다르면 이쪽이 앞선다):

| 항목 | 정한 것 |
|---|---|
| 난이도 | 아직 정하지 않았다. 문서의 수치를 `config.yml` 값으로 둔다 |
| 마법 | 넣는다 (촉매, 마나 같은 자원, 기억 칸). 설계는 나중이고 M0 에는 없다. HUD·데이터에 마나 막대 자리를 남긴다 |
| 사망 화면 | 한국어 "사망했다" 대신 크고 새빨간 "YOU DIED". 손으로 찍은 그림 글자 |
| 화톳불 이동 | 처음부터 (넷째 보스 뒤가 아니다) |
| 에스트 | 바닐라 물약처럼: 단축 슬롯에 두고 우클릭을 누르고 있으면 마신다. 슬롯을 저절로 바꾸지 않는다 |
| 규모 | 짧은 맛보기판부터. 7지역 전체가 아니다 |

## 폴더

```
plugin/   Gradle 플러그인 (kr.souls). 리소스: paper-plugin.yml, config.yml, lang/ko.yml, content/, datapack/soulsdp/
pack/     리소스팩 생성기 (gen_pack.py, hud.py, palette.py, artlint.py)
server/   배포할 서버 폴더 (start.bat → start.ps1, start.sh, server.properties, bukkit.yml, config/paper-global.yml, README.txt)
tools/    make_dist.py (배포 묶기), textlint.py (글 검사), bots/ (봇 시험)
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

`make_dist.py` 는 글 검사(textlint), 그림 검사(artlint), 낡은 jar, 시험용 설정(`debug.test-mode`, `pack.serve-port`), 팩 형식 75·셰이더 없음·참조, 그림 글자 표, 서버 폴더 인코딩 규칙과 `server.properties` 값 가운데 하나라도 어긋나면 아무것도 쓰지 않고 멈춘다.

## 배포

1. `python3 tools/make_dist.py`
2. `dist/packs/<sha1>.zip` 을 커밋·푸시한다. 플러그인은 `config.yml` 의 `pack.url` 틀에 jar 안 팩의 SHA-1 을 채워 그 주소로 팩을 보낸다 (파일 이름이 내용으로 정해지므로 캐시 문제가 없다). 올린 뒤 `python3 tools/make_dist.py --no-build --check-url` 로 주소가 이 팩을 내주는지 본다.
3. `dist/Soulslike-Server.zip` 을 풀고 `start.bat` (윈도우) 또는 `start.sh` (맥/리눅스). 처음 한 번 Java 21 과 Paper 를 받는다 (Paper 는 sha256 으로 확인). 자세한 것은 압축 안의 `README.txt`.

## 시험

- 게임 안: `/souls check` (데이터팩, 바이옴, 난이도, 게임 규칙, 시험 방, 팩, 그림 글자). `/soulstest` 는 `debug.test-mode: true` 일 때만 (봇 시험용).
- 봇: `tools/bots/` (mineflayer 4.39), 지연 프록시 `tools/bots/lagproxy.js`.
- 글·그림: `python3 tools/textlint.py`, `python3 pack/artlint.py`.
