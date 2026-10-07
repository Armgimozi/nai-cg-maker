# 실제 클라이언트 점검 틀 (DESIGN.md 13.4)

아무것도 깔지 않은 바닐라 1.21.11 클라이언트를 가상 화면(Xvfb, mesa llvmpipe 소프트웨어 OpenGL)에 띄워 로컬 서버에 붙이고, 키를 누르고, 화면을 찍는다. 봇이 못 보는 것(그림 글자, HUD, 막는 자세, 사망 화면)을 그림으로 남긴다.

| 파일 | 하는 일 |
|---|---|
| `run_client.sh` | 들어가는 곳. 없는 도구(Xvfb, xdotool, ImageMagick, mesa)를 apt 로 설치하고 `mcclient.py` 를 부른다 |
| `mcclient.py` | 클라이언트 켜기·동작·찍기·끄기 |
| `setup_client.py` | piston-meta 에서 버전 문서 → 라이브러리·네이티브·에셋을 받는다 (처음 한 번, 약 110MB) |
| `devserver.sh` | 점검용 Paper 서버 (오프라인 접속, 시험 모드, 팩을 로컬 포트에서, Tester 에게 op) |
| `m0_shots.sh` | M0 점검 그림 묶음 (13.4 의 1·2·3·5·6) |
| `log4j2-client.xml` | 클라이언트 기록을 보통 글줄로 (런처 설정은 XML 로 낸다) |

## 쓰는 법

```sh
# 1. 서버 (플러그인은 plugin/build/libs/Soulslike.jar. 팩은 포트-17000 에서: 25602 → 8602)
PAPER_JAR=/경로/paper-1.21.11-132.jar tools/client/devserver.sh 25602 /tmp/srv

# 2. 한 번에: 켜고 → 동작 → 끈다
tools/client/run_client.sh 25602 /tmp/shots \
  join shot:joined sprint:2 shot:after_sprint key:f wait:0.3 shot:roll \
  "cmd:/soulstest kill" wait:2 shot:died respawn wait:2 shot:respawned

# 또는 켜 두고 여러 번
tools/client/run_client.sh --start 25602 /tmp/shots
tools/client/run_client.sh --do 25602 join clearchat shot:a
tools/client/run_client.sh --do 25602 down:ctrl+w wait:1 shot:running up:ctrl+w
tools/client/run_client.sh --stop 25602

# M0 묶음
tools/client/m0_shots.sh 25602 /tmp/shots

# 서버 끄기 / 콘솔 명령
tools/client/devserver.sh --cmd /tmp/srv give Tester minecraft:potion
tools/client/devserver.sh --stop /tmp/srv
```

찍은 그림은 `<찍을폴더>/<이름>.png` (1280x720). 표준 출력에 `SHOT <경로>` 줄이 나온다. `run` 은 끝날 때 클라이언트 기록을 `<찍을폴더>/client.log` 로 복사한다. 실패(클라이언트 꺼짐, 접속 실패, 기다림 초과)면 기록 끝 40줄을 보이고 1 로 끝난다.

## 동작

한 인수에 하나. 빈칸이 있으면 따옴표로 묶는다.

| 동작 | 뜻 |
|---|---|
| `join[:초]` | 세계에 들어가고 서버 팩을 다시 다 실을 때까지 + 2초. 팩 경고·오류 줄을 센다 (13.4-1). 팩이 10초 안에 안 오면 팩 없는 서버로 본다 |
| `wait:초` | 기다린다 |
| `shot:이름` | X 화면을 그대로 찍는다 (`import -window root`) |
| `f2:이름` | 게임 F2 스크린샷을 가져온다. 채팅에 저장 줄이 남는다 |
| `key:키[+키]` | 눌렀다 뗀다. xdotool 이름: `f`, `w`, `space`, `Escape`, `Return`, `Tab`, `F1`, `F3`, `F5`, `1`~`9`, `ctrl` |
| `hold:키[+키]:초` | 누르고 있다 뗀다 |
| `sprint:초` / `walk:초` | Ctrl 을 먼저 누른 채 W / W 만 |
| `down:키[+키]` / `up:키[+키]` | 누르기만 / 떼기만. 누르는 동안 찍을 때 |
| `mouse:left\|right\|middle[:초]` | 클릭, 초가 있으면 누르고 있기 (물약·에스트 마시기, 막기) |
| `mdown:버튼` / `mup:버튼` | 마우스 누르기만 / 떼기만 |
| `look:dx:dy` | 시점 돌리기 (화면 픽셀. 400 이면 대략 90도) |
| `slot:N` | 단축 슬롯 |
| `cmd:글` | T 로 채팅을 열어 치고 Enter |
| `type:글` | 열린 칸에 치기만 |
| `mark` / `log:정규식[:초]` | mark 뒤 클라이언트 기록에 맞는 줄을 기다린다. 채팅은 `[System] [CHAT] ...` 줄 (시험 줄 `[T] ...` 도 여기 나온다) |
| `respawn[:초]` | 사망 화면 단추가 켜질 때까지(기본 1.5초) 기다렸다가 Tab, Enter → 첫 단추 "일어선다" |
| `clearchat` | 채팅 비우기 (F3+D) |
| `close` | Escape |

## 환경 변수

| 이름 | 기본 | 뜻 |
|---|---|---|
| `SOULS_CLIENT_HOME` | `~/.cache/souls-client` | 받은 클라이언트와 실행 폴더 `run/<포트>/` (game/, client.log, session.json) |
| `MC_NAME` | `Tester` | 오프라인 이름 |
| `MC_HOST` | `localhost` | 접속 주소 앞부분 |
| `MC_SIZE` | `1280x720` | 창 = 화면 크기 |
| `MC_LANG` | `ko_kr` | 클라이언트 언어 (setup 이 받은 것만. `setup_client.py --langs ko_kr,en_us`) |
| `MC_GUI_SCALE` | `0` (자동, 1280x720 이면 3) | GUI 배율 |
| `MC_OPTIONS` | | options.txt 에 더할 줄 `"키:값;키:값"` (예 `"chatVisibility:2;renderDistance:12"`) |
| `MC_XMX` | `2G` | 클라이언트 메모리 |
| `MC_CLIENT_JAR` | | 이미 받아 둔 client.jar (sha1 이 맞을 때만 복사) |

## 알아 둘 것

- **서버는 `online-mode=false`** 여야 한다 (토큰 없는 오프라인 클라이언트). `devserver.sh` 가 그렇게 둔다.
- **`/soulstest` 는 op 가 있어야 보인다** (`souls.test` 권한). 없으면 "알 수 없거나 불완전한 명령어". `devserver.sh` 가 켤 때 `OPS` (기본 `Tester`) 에 op 를 준다.
- **팩 주소는 클라이언트가 직접 받는다** (프록시를 쓰지 않는다). 로컬 시험은 `pack.serve-port` 로 내보내고 `pack.url` 을 `http://127.0.0.1:<포트>/{sha1}.zip` 로 (`devserver.sh` 가 한다). 서버 목록(`servers.dat`)에 `acceptTextures=1` 을 넣어 묻는 창 없이 받는다. 빠른 접속은 주소 글자(`localhost:25602`)가 똑같은 줄만 쓴다.
- **1.21.11 의 `graphicsPreset`**: fancy 면 켤 때 시야·구름·그림자 값을 덮어쓴다. 그래서 `custom` 으로 두고 fancy 값 그대로에 시야만 8 로 줄였다. llvmpipe 4코어에서 약 17 FPS.
- **오른쪽 위 알림**: 들어가면 "대화 메시지를 검증할 수 없습니다" (서버가 `enforce-secure-profile=false` 라 실제 사람도 본다)와 "리소스 팩 다운로드 중" 이 몇 초 남는다. 깨끗한 화면이 필요하면 `join wait:8`. 아이템을 처음 받으면 "새로운 제작법 잠금 해제!" 도 뜬다.
- **채팅의 시험 줄**: 시험 모드는 `[T] ...` 줄을 채팅에 낸다. 찍기 전에 `clearchat`. 아예 숨기려면 `MC_OPTIONS="chatVisibility:2"` (그러면 명령 결과도 안 보인다. `log:` 는 그대로 된다).
- **사망 화면 단추**는 죽고 1초 동안 꺼져 있다. `respawn` 이 기다린다.
- **달리기**: Ctrl 을 먼저 누르고 W (`sprint:` / `down:ctrl+w`). 키 입력은 xdotool XTEST 라 창 관리자 없이 초점을 직접 준다. `rawMouseInput:false` 로 두어 `look` 이 먹는다.
- **소리**: 소리 에셋은 받지 않고 (`setup_client.py --sounds` 로 받을 수 있다) OpenAL 은 빈 장치로 돈다. 소리는 이 틀로 확인할 수 없다.
- **포트마다 세션 하나**: 실행 폴더가 `run/<포트>/` 라, 같은 포트에 클라이언트 둘은 안 된다. 게임 폴더는 남겨 두고(받은 서버 팩 캐시) `options.txt`·`servers.dat`·기록은 켤 때마다 새로 쓴다.
- **걸리는 시간**: 처음 받기 수 초(네트워크에 따라), 켜서 들어가기까지 약 17초, 팩 다시 싣기 약 4초. `m0_shots.sh` 전체 약 1분.
- 계정이 없어 클라이언트 기록에 `Failed to fetch user properties`, `profile key pair`, `Realms` 오류가 늘 나온다. 무시한다 (`join` 의 팩 경고 셈에서도 뺀다).
