# 실서버 테스트 하네스 (tools/servertest)

진짜 바닐라 마인크래프트 서버를 **임시 폴더에 잠깐 띄워서** 데이터팩을 돌려 보는 도구 모음입니다.
`tools/mcvalidate.py` 가 명령어 문법을 정적으로 검사한다면, 여기서는 서버가 실제로 데이터팩을 불러오는지,
저택이 실제로 지어지는지, 봇이 접속해서 한 판을 시작하고 상자를 열 수 있는지를 확인합니다.

- 서버 jar 는 Mojang 공식 매니페스트에서 받아 `.mcmeta-cache/server-jars/<버전>/` 에 캐시합니다(sha1 검증, git 무시).
- 서버 폴더는 **항상 저장소 밖** 임시 폴더에 새로 만들고, 끝나면 지웁니다(서버 로그만 `<임시 폴더>/logs/` 에 남김).
- 테스트 서버는 `online-mode=false`, `127.0.0.1` 전용, RCON 켬(무작위 비밀번호·빈 포트), 평지 월드입니다.
  자동 테스트 전용 일회용 샌드박스라서 `eula.txt` 에 `eula=true` 를 미리 적습니다.
  나머지 설정은 저장소의 `server/server.properties` 를 그대로 따릅니다.

## 준비물

| | 버전 | 용도 |
|---|---|---|
| Python | 3.10 이상 (3.13 에서 확인) | 모든 도구. 외부 패키지 없음 |
| Java | 1.21.x 는 **Java 21**, 26.x 는 **Java 25 이상** | 서버 실행 |
| Node.js | 18 이상 (22 에서 확인) + npm | 봇 시나리오만. `bots/node_modules` 가 없으면 처음 실행할 때 `npm ci` 를 자동으로 돌립니다 |

임시 폴더 위치는 환경 변수 `AOONI_SERVERTEST_TMP` 나 `--base` 로 정합니다(기본: 시스템 임시 폴더의 `aooni-servertest/`).
저장소 안을 가리키면 거부합니다.

## 바로 실행

저장소의 `aooni-server-pack/` 폴더에서:

```bash
# 1) 데이터팩 로드 점검 (기본 1.21.11, 약 20초)
python3 tools/servertest/check_load.py
python3 tools/servertest/check_load.py --version 1.21.5 --version 1.21.8 --version 1.21.11

# 2) 스모크 시나리오: 서버 + 봇 2명으로 실제 한 판 (약 50초)
python3 tools/servertest/scenario_smoke.py
python3 tools/servertest/scenario_smoke.py --max-chests 5 --verbose --json /tmp/smoke.json

# 3) 서버만 띄워서 RCON 명령 몇 개 실행 / RCON 콘솔
python3 tools/servertest/mcserver.py exec -- "datapack list" "scoreboard players get #built aooni.var"
python3 tools/servertest/mcserver.py console        # 한 줄씩 명령 입력, 빈 줄/Ctrl-D 로 종료
python3 tools/servertest/mcserver.py download --version 1.21.5
python3 tools/servertest/mcserver.py errors <로그 파일>   # 로그에서 오류 줄만 뽑기
```

종료 코드는 문제가 없으면 0, 있으면 1 입니다. `--keep` 을 주면 서버 폴더를 지우지 않습니다.

### check_load.py — 로드 점검

1. 서버를 켜고 저택 건축이 끝날 때까지(`#built` = `build/all.mcfunction` 의 BUILD_VERSION) 기다린 뒤, 최소 10초(`--settle`) 돌립니다.
2. `datapack list` 에 `file/aooni_mansion` 이 켜져 있는지, load·tick 함수가 도는지(`#state`, `#diff`, `#t` 변화) 확인합니다.
3. `function aooni:admin/help` 를 실행합니다.
4. **모든 `.mcfunction` 파일이 서버에 등록됐는지** 확인합니다. 함수마다
   `schedule function <id> 1000000s append` 를 보내면, 등록된 함수는 `Scheduled function ...`(매크로 함수는
   `Can't schedule a macro`), 불러오지 못한 함수는 `Unknown function` 으로 답합니다. 실행하지 않고 존재만
   확인하는 방법이고, `append` 라서 데이터팩 자신의 예약(`setup/check_build` 등)은 건드리지 않습니다.
5. **건축 결과 확인**: `build/lobby`·`build/mansion` 을 순서대로 흉내 내서 계산한 블록(모든 setblock 좌표 +
   fill 의 두 모서리·가운데)이 실제 월드에 있는지 `execute if block` 으로 봅니다. 함수 안의 fill/setblock 은
   실패해도 조용하므로(블록 수 제한 초과, 받침 없는 버튼이 떨어짐 등) 이 방법으로만 잡힙니다.
   32768 칸이 넘는 fill 도 따로 알려 줍니다.
6. 서버 로그에서 오류 줄(`Failed to load function`, `Couldn't load`, `Unknown or incomplete command`,
   `Incorrect argument`, `Expected`, `Error`, `Exception` 등)을 모두 모아 보여 줍니다.
   데이터팩과 무관한 줄은 "참고"로 따로 보여 주고 실패로 치지 않습니다:
   - `Failed to request yggdrasil public key` — 테스트 환경에서 Mojang 인증 API 에 접속할 수 없을 때(오프라인 모드라 무관)
   - `No key layers in MapLike[{}]` — `level-type=flat` 인데 `generator-settings` 가 비어 있어 기본 평지 설정을 쓴다는 바닐라 메시지

### scenario_smoke.py — 스모크 시나리오

`bots/scenarios/smoke.js` 와 함께 돕니다.

1. 서버를 켜고 봇 `AoBot1`, `AoBot2` 가 접속합니다(대기실).
2. RCON: `op AoBot1` → `execute as AoBot1 run function aooni:admin/start`
3. RCON 으로 `#state`, 술래(`aooni.oni_p`), 생존자(`aooni.alive`), 각 봇의 태그를 확인합니다.
4. 모든 조사 상자(`build/mansion.mcfunction` 의 `minecraft:chest[` setblock)의 내용물을 RCON 으로 기록하고,
   상자 수가 조사 지점 마커(`aooni.spot`) 수와 같은지, 진짜 비밀번호 쪽지 4장이 배치됐는지 봅니다.
5. 생존자 봇이 가까운 상자 몇 개와 '진짜 쪽지가 든 가장 가까운 상자'로 걸어가 열고, 내용물을 읽고 모두 가져옵니다.
6. 봇이 본 내용물이 RCON 기록과 같은지, 진짜 쪽지를 집으면 `#found` 가 오르고 발견 알림과 '펼친 쪽지'가 오는지,
   가짜 쪽지는 '번진 쪽지'로 바뀌는지, 술래·생존자에게 시작 타이틀이 떴는지, 서버 로그에 오류가 없는지 확인합니다.

옵션: `--names A,B`(첫 번째가 게임 시작), `--max-chests`, `--budget`(상자 단계 초), `--timeout`(전체 초, 기본 360),
`--verbose`(봇이 받는 채팅·타이틀을 실시간 출력), `--json 파일`.

## 버전

| 항목 | 값 |
|---|---|
| 기본 서버 버전 | **1.21.11** (Java 21) |
| 봇 | mineflayer 4.39.0, minecraft-protocol 1.68.0, minecraft-data 3.117.0, mineflayer-pathfinder 2.4.5 |
| 봇 접속 버전 | **1.21.11 (프로토콜 774)** 지원. mineflayer 가 시험한 1.21.x: 1.21.1·3·4·5·6·8·9·11 (+ 26.1) |
| 확인한 서버 | check_load: 1.21.5, 1.21.8, 1.21.11 / 스모크: 1.21.11 |

- 바닐라 서버는 자기 프로토콜만 받으므로 봇 시나리오는 서버와 봇이 같은 버전이어야 합니다.
  `botrun.pick_version()` 이 요청한 버전을 봇이 지원하지 않으면 **봇이 지원하는 가장 새 1.21.x(1.21.5 이상)** 로
  서버 버전을 바꾸고 그 사실을 출력합니다. 지원 목록은 `cd tools/servertest/bots && node lib/versions.js` 로 볼 수 있습니다.
- 26.x 서버는 Java 25 가 필요합니다. Java 가 낮으면 check_load 는 그 버전을 "건너뜀"으로 표시합니다.
  (mineflayer 4.39.0 은 26.1 만 지원하므로 26.2·26.3 봇 테스트는 아직 불가)

## 파일 구성

```
tools/servertest/
  mcserver.py        서버 jar 다운로드·캐시, 일회용 서버(MCServer), RCON 클라이언트(Rcon), 로그 오류 검사
  packinfo.py        데이터팩 읽기: 함수 목록, 상자 좌표, 건축 결과 계산, fill 부피
  check_load.py      로드 점검 CLI
  botrun.py          파이썬 오케스트레이터: 노드 시나리오 실행(NodeScenario), 버전 선택, 전체 시간 제한(GlobalTimeout)
  scenario_smoke.py  스모크 시나리오(파이썬 쪽)
  bots/
    package.json, package-lock.json
    lib/bots.js      봇 도우미 모음(접속·이동·상자·전투·먹기·메시지 기록)
    lib/link.js      파이썬과 주고받는 통로(RCON 요청, 신호, 결과)
    lib/versions.js  봇이 지원하는 버전 출력
    driver.js        범용 봇 조종기(파이썬에서 RPC 로 봇을 직접 조종)
    scenarios/smoke.js  스모크 시나리오(봇 쪽)
```

## 시나리오 새로 만들기

### A. 파이썬 + JS 시나리오 (스모크와 같은 방식)

JS 쪽은 봇을 움직이고, 파이썬 쪽은 서버·RCON 을 맡습니다. 둘은 신호로 박자를 맞춥니다.

```js
// bots/scenarios/my.js
const B = require('../lib/bots')
const link = require('../lib/link')
const cfg = link.config()                       // host, port, version, names, args, timeoutMs
let bots = []
link.watchdog(cfg.timeoutMs, () => B.quitAll(bots))   // 전체 시간 제한
;(async () => {
  bots = await B.connectBots({
    names: cfg.names, host: cfg.host, port: cfg.port, version: cfg.version,
    onLog: (e) => link.send({ t: 'msg', ...e })     // 받은 메시지를 파이썬 쪽(ns.messages)에도 실시간으로
  })
  link.signal('joined')
  const go = await link.waitFor('go', 60000)    // 파이썬이 보낸 데이터
  console.log(await link.rcon('tag AoBot1 list'))   // JS 에서도 RCON 가능
  const { window, items } = await B.openChestAt(bots[0], ...go.chest)
  bots[0].closeWindow(window)
  link.result({ items })
})().catch(link.fail).then(async () => { await link.waitFor('done', 30000).catch(() => {}); B.quitAll(bots); process.exit(0) })
```

```python
# tools/servertest/my_scenario.py
from mcserver import MCServer
from botrun import NodeScenario, GlobalTimeout, pick_version
version, note = pick_version("1.21.11")
srv = MCServer(version)
with GlobalTimeout(300, srv) as gt:
    try:
        srv.start(); srv.wait_built()
        with NodeScenario(srv, "scenarios/my.js", ["AoBot1", "AoBot2"], version) as ns:
            gt.add(ns)
            ns.wait_signal("joined", 60)
            srv.cmd("op AoBot1")
            srv.cmd("execute as AoBot1 run function aooni:admin/start")
            print(srv.score("#state"), srv.players_with_tag("aooni.oni_p"), srv.tags("AoBot2"))
            ns.send_signal("go", {"chest": [31, -60, 29]})
            print(ns.wait_result(120))
            ns.send_signal("done")
        print(srv.errors())
    finally:
        srv.stop(); srv.cleanup()
```

### B. 파이썬만 (driver.js)

`driver.js` 를 띄우면 파이썬에서 봇을 한 동작씩 직접 시킬 수 있습니다.

```python
with NodeScenario(srv, "driver.js", ["AoBot1", "AoBot2"], version) as ns:
    ns.wait_signal("ready", 20)
    ns.call("connect", timeout=60)
    ns.call("gotoReach", bot="AoBot1", x=-21, y=-59, z=5)          # 대기실 [난이도 변경] 버튼 앞으로
    ns.call("activateBlockAt", bot="AoBot1", x=-21, y=-59, z=5)    # 누르기 → #diff 가 바뀜
    ns.call("openChestAt", bot="AoBot1", x=31, y=-60, z=29, take=True)
    ns.call("equip", bot="AoBot1", item="bread"); ns.call("consume", bot="AoBot1")
    ns.call("chaseAndAttack", bot="AoBot2", target="AoBot1", timeoutMs=60000, timeout=65)
    ns.call("messages", bot="AoBot1")                              # 받은 채팅·액션바·타이틀
```

### 봇 도우미 (bots/lib/bots.js)

| 함수 | 설명 |
|---|---|
| `connectBots({names, host, port, version})` | 오프라인 봇 여러 명 접속, 스폰·청크 로드까지 대기 |
| `goto(bot, x, y, z, {range})` | 근처로 걷기(블록을 부수거나 놓지 않음, 문은 열지 않음) |
| `gotoReach(bot, x, y, z)` | 블록에 손이 닿는 곳까지(상자는 면이 보이는 자리, 버튼 같은 작은 블록은 2칸 안) |
| `lookAt`, `activateBlockAt(bot, x, y, z)` | 바라보기, 버튼·레버 누르기 |
| `openChestAt(bot, x, y, z)` | 상자 열기 → `{window, items}`. 아이템은 이름·개수·사용자 지정 이름·lore·custom_data·물약 효과 |
| `takeAll(bot, window)` | 상자 칸을 모두 Shift+클릭으로 가져오기 |
| `attackPlayer(bot, name)`, `chaseAndAttack(bot, name)` | 한 대 때리기 / 쫓아가서 때리기 |
| `equip(bot, 이름)`, `consume(bot)` | 들기, 먹기·마시기(이 팩의 '배불러도 먹는' 빵·스테이크도 처리, 실제로 줄어들 때까지 대기) |
| `chat`, `command(bot, cmd)` | 채팅, 명령(`/trigger aooni.quit` 등) |
| `inventory(bot)`, `position(bot)` | 인벤토리, 좌표 |
| `waitForMessage(bot, 정규식)` | `bot.aooni.log`(채팅·시스템·액션바·타이틀·부제·킥) 에서 메시지 기다리기 |

모든 대기 함수에는 시간 제한이 있습니다. 노드 시나리오는 `AOONI_TIMEOUT_MS` 를 넘기면 스스로 끝나고,
파이썬 쪽 `NodeScenario` 와 `GlobalTimeout` 도 각자 시간이 지나면 노드·서버 프로세스를 강제로 끕니다.

## 한계와 메모

- **함수 안에서 실패한 명령은 서버 로그에 남지 않습니다**(바닐라 동작). check_load 가 잡는 것은 함수 파싱·로드 실패,
  등록 누락, 건축 결과 차이, 서버 로그에 찍히는 오류입니다. 게임 규칙의 논리 오류는 시나리오로 확인해야 합니다.
- mineflayer 의 물리·길찾기는 실제 클라이언트와 조금 다를 수 있습니다. 봇은 문(옷장)을 열지 않고, 블록을 부수거나
  놓지 않습니다. 소리·파티클·화면 효과(어둠 등)는 확인하지 않습니다.
- RCON 응답은 서버 언어(영어)입니다. `tellraw @s` 처럼 플레이어에게만 가는 메시지는 RCON 으로는 보이지 않으니 봇의 메시지 기록으로 확인하세요.
- 바닐라 RCON 은 TCP 읽기 한 번에 패킷이 정확히 하나 들어와야 하며, 두 패킷이 붙어 오면 연결을 끊습니다.
  그래서 `Rcon.command()` 는 첫 응답 조각을 받은 뒤에 '응답 끝 표시' 패킷을 보내 여러 조각 응답을 이어 붙입니다.
- 서버 jar 다운로드가 프록시 등에서 끊기면 HTTP Range 로 이어 받습니다(최대 6번).
- 서버 jar 안의 라이브러리(약 60MB)는 `-DbundlerRepoDir` 로 캐시 폴더에 한 번만 풀어 둡니다. 서버가 켜지는 데는 보통 10초 안팎 걸립니다.
- 봇이 쓰는 포트·RCON 포트는 매번 빈 포트를 고르므로 여러 테스트를 동시에 돌려도 됩니다.
