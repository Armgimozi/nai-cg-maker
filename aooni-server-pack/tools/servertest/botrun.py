"""파이썬 쪽 시나리오 오케스트레이터: 서버(RCON) + 노드 봇 시나리오를 함께 돌린다.

    from mcserver import MCServer
    from botrun import NodeScenario, pick_version, ensure_node_modules

    version, note = pick_version("1.21.11")      # 봇이 지원하는 버전으로 맞춤
    with MCServer(version) as srv:
        srv.wait_built()
        with NodeScenario(srv, "scenarios/smoke.js", names=["AoBot1", "AoBot2"], version=version) as ns:
            joined = ns.wait_signal("joined", 60)
            srv.cmd("op AoBot1")
            ns.send_signal("go", {...})
            result = ns.wait_result(120)

노드 쪽은 bots/lib/link.js 로 같은 통로를 쓴다. 노드가 보낸 RCON 요청은 여기서 자동으로 처리한다.
driver.js 를 띄우면 ns.call("goto", bot="AoBot1", x=.., y=.., z=..) 처럼 파이썬에서 봇을 직접 조종할 수 있다.
모든 대기에는 시간 제한이 있고, 전체 시간 제한(global_timeout)이 지나면 노드와 서버를 강제로 끈다.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BOTS_DIR = os.path.join(HERE, "bots")
MIN_PACK_VERSION = (1, 21, 5)


def _say(msg: str) -> None:
    print(f"[botrun] {msg}", file=sys.stderr, flush=True)


def ensure_node_modules(timeout: float = 300) -> None:
    """bots/node_modules 가 없으면 package-lock.json 대로 설치(npm ci)."""
    if os.path.isdir(os.path.join(BOTS_DIR, "node_modules", "mineflayer")):
        return
    _say("bots/ 에 npm ci 를 실행합니다(처음 한 번)...")
    subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=BOTS_DIR, check=True, timeout=timeout)


def bot_versions() -> dict:
    """설치된 mineflayer 가 접속할 수 있는 버전 정보(bots/lib/versions.js 출력)."""
    ensure_node_modules()
    out = subprocess.run(["node", "lib/versions.js"], cwd=BOTS_DIR, capture_output=True, text=True,
                         timeout=60, check=True)
    return json.loads(out.stdout)


def _vt(v: str) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", v))


def pick_version(requested: str) -> tuple[str, str]:
    """(실제로 쓸 버전, 안내문). 봇이 요청 버전을 지원하지 않으면 지원하는 가장 새 1.21.x(1.21.5 이상)로 바꾼다.
    바닐라 서버는 자기 프로토콜만 받으므로 서버도 같은 버전으로 띄워야 한다."""
    info = bot_versions()
    sup = info["supported"]
    proto = info.get("protocol", {})
    if requested in sup:
        return requested, f"봇(mineflayer {info['mineflayer']})이 {requested}(프로토콜 {proto.get(requested)})을 지원"
    cands = [v for v in sup if v.startswith("1.21") and _vt(v) >= MIN_PACK_VERSION]
    if not cands:
        raise SystemExit(f"mineflayer {info['mineflayer']} 가 지원하는 1.21.5+ 버전이 없습니다: {sup}")
    best = max(cands, key=_vt)
    return best, (f"봇(mineflayer {info['mineflayer']})이 {requested} 를 지원하지 않아 "
                  f"{best}(프로토콜 {proto.get(best)})로 바꿔 테스트합니다")


class ScenarioError(Exception):
    pass


class NodeScenario:
    """노드 봇 시나리오 프로세스 하나."""

    def __init__(self, server, script: str, names: list[str], version: str, args: dict | None = None,
                 timeout: float = 240, echo_messages: bool = True):
        self.server = server
        self.script = script
        self.names = names
        self.version = version
        self.args = args or {}
        self.timeout = timeout
        self.echo_messages = echo_messages
        self.proc: subprocess.Popen | None = None
        self.signals: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._pending_signals: list[tuple[str, object]] = []
        self.result: object = None
        self.failure: str | None = None
        self.messages: list[dict] = []        # 봇이 받은 채팅·타이틀 등(실시간 수집)
        self.logs: list[str] = []
        self.rcon_log: list[tuple[str, str]] = []
        self._calls: dict[int, "queue.Queue"] = {}
        self._next_call = 1
        self._done = threading.Event()
        self._wlock = threading.Lock()
        self._watchdog: threading.Timer | None = None

    # ---- 시작/끝
    def start(self) -> "NodeScenario":
        ensure_node_modules()
        env = dict(os.environ)
        env.update({
            "AOONI_HOST": "127.0.0.1",
            "AOONI_PORT": str(self.server.port),
            "AOONI_VERSION": self.version,
            "AOONI_NAMES": json.dumps(self.names),
            "AOONI_ARGS": json.dumps(self.args, ensure_ascii=False),
            "AOONI_TIMEOUT_MS": str(int(self.timeout * 1000)),
        })
        _say(f"노드 시나리오 시작: {self.script} 봇 {self.names} 버전 {self.version}")
        self.proc = subprocess.Popen(["node", self.script], cwd=BOTS_DIR, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        # 노드 자체 시간 제한 + 여유 15초가 지나면 강제로 끝낸다
        self._watchdog = threading.Timer(self.timeout + 15, self._kill_on_timeout)
        self._watchdog.daemon = True
        self._watchdog.start()
        return self

    def _kill_on_timeout(self) -> None:
        if self.proc and self.proc.poll() is None:
            _say("노드 시나리오가 전체 시간 제한을 넘겨 강제 종료합니다")
            self.failure = self.failure or "전체 시간 초과(파이썬 감시)"
            self.proc.kill()

    def stop(self, timeout: float = 10) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()      # link.js 가 stdin 닫힘을 보고 스스로 끝난다
        except Exception:
            pass
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)

    def __enter__(self) -> "NodeScenario":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ---- 통신
    def _write(self, obj: dict) -> None:
        assert self.proc and self.proc.stdin
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self._wlock:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError, OSError):
                pass

    def _handle_rcon(self, msg: dict) -> None:
        try:
            text = self.server.cmd(msg["cmd"])
            self.rcon_log.append((msg["cmd"], text))
            self._write({"t": "rcon_result", "id": msg["id"], "ok": True, "text": text})
        except Exception as e:  # noqa: BLE001
            self._write({"t": "rcon_result", "id": msg["id"], "ok": False, "text": f"{type(e).__name__}: {e}"})

    def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if not line.startswith("@@"):
                if line.strip():
                    self.logs.append(line)
                    print(f"  [node] {line}", file=sys.stderr, flush=True)
                continue
            try:
                msg = json.loads(line[2:])
            except json.JSONDecodeError:
                continue
            t = msg.get("t")
            if t == "rcon":
                threading.Thread(target=self._handle_rcon, args=(msg,), daemon=True).start()
            elif t == "signal":
                self.signals.put((msg.get("name"), msg.get("data")))
            elif t == "log":
                self.logs.append(msg.get("msg", ""))
                print(f"  [node] {msg.get('msg')}", file=sys.stderr, flush=True)
            elif t == "msg":
                self.messages.append(msg)
                if self.echo_messages:
                    print(f"  [{msg.get('bot')}·{msg.get('kind')}] {msg.get('text')}", file=sys.stderr, flush=True)
            elif t == "result":
                self.result = msg.get("data")
                self._done.set()
            elif t == "fail":
                self.failure = msg.get("error")
                print(f"  [node 실패] {self.failure}", file=sys.stderr, flush=True)
                self._done.set()
            elif t == "call_result":
                q = self._calls.get(msg.get("id"))
                if q:
                    q.put(msg)
        self._done.set()
        self.signals.put(("__exit__", None))

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for raw in iter(self.proc.stderr.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if line.strip():
                self.logs.append(line)
                print(f"  [node:err] {line}", file=sys.stderr, flush=True)

    def send_signal(self, name: str, data: object = None) -> None:
        self._write({"t": "signal", "name": name, "data": data})

    def wait_signal(self, name: str, timeout: float = 60) -> object:
        """노드가 link.signal(name, data) 를 보낼 때까지 기다린다."""
        for i, (n, d) in enumerate(self._pending_signals):
            if n == name:
                self._pending_signals.pop(i)
                return d
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise ScenarioError(f"노드 신호 '{name}' 를 {timeout:.0f}초 동안 받지 못함")
            try:
                n, d = self.signals.get(timeout=min(left, 1.0))
            except queue.Empty:
                if self.failure:
                    raise ScenarioError(f"노드 시나리오 실패: {self.failure}")
                continue
            if n == name:
                return d
            if n == "__exit__":
                raise ScenarioError(f"노드 시나리오가 끝나 버림(기다리던 신호: {name}). 실패: {self.failure}")
            self._pending_signals.append((n, d))

    def wait_result(self, timeout: float = 120) -> object:
        if not self._done.wait(timeout):
            raise ScenarioError(f"노드 결과를 {timeout:.0f}초 동안 받지 못함")
        if self.result is None:
            raise ScenarioError(f"노드 시나리오 실패: {self.failure or '결과 없이 끝남'}")
        return self.result

    def call(self, method: str, timeout: float = 60, **args) -> object:
        """driver.js 에 RPC 호출. 실패하면 ScenarioError."""
        cid = self._next_call
        self._next_call += 1
        q: "queue.Queue" = queue.Queue()
        self._calls[cid] = q
        self._write({"t": "call", "id": cid, "method": method, "args": args})
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty:
            raise ScenarioError(f"봇 호출 {method} 이(가) {timeout:.0f}초 안에 끝나지 않음") from None
        finally:
            self._calls.pop(cid, None)
        if not msg.get("ok"):
            raise ScenarioError(f"봇 호출 {method} 실패: {msg.get('error')}")
        return msg.get("value")


class GlobalTimeout:
    """시나리오 전체 시간 제한. 넘으면 서버·노드를 강제로 끈다(대기 중인 코드는 곧 예외로 깨어난다)."""

    def __init__(self, seconds: float, *targets):
        self.seconds = seconds
        self.targets = list(targets)
        self.fired = False
        self._t = threading.Timer(seconds, self._fire)
        self._t.daemon = True

    def add(self, target) -> None:
        self.targets.append(target)

    def _fire(self) -> None:
        self.fired = True
        _say(f"시나리오 전체 시간 제한({self.seconds:.0f}초)을 넘겨 강제로 끕니다")
        for t in self.targets:
            proc = getattr(t, "proc", None)
            if proc is not None and proc.poll() is None:
                proc.kill()

    def __enter__(self) -> "GlobalTimeout":
        self._t.start()
        return self

    def __exit__(self, *exc) -> None:
        self._t.cancel()
