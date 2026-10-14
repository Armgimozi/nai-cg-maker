#!/usr/bin/env python3
"""아오오니 저택 데이터팩 실서버 테스트 도구 (라이브러리 + CLI).

진짜 바닐라 서버를 임시 폴더에 띄워서 데이터팩을 돌려 본다.
- Mojang 버전 매니페스트에서 서버 jar 를 받아 .mcmeta-cache/server-jars/ 에 캐시(sha1 검증)
- 저장소 밖 임시 폴더에 일회용 서버를 만들고 데이터팩을 복사
  (online-mode=false, RCON 켬, 빈 포트 사용 - 자동 테스트 전용 샌드박스)
- 서버 로그를 파일로 받아 두고 "Done (" 를 기다림
- RCON(Source RCON 프로토콜) 클라이언트, 깨끗한 종료, 로그 오류 검색

사용 예:
  python3 tools/servertest/mcserver.py download --version 1.21.11
  python3 tools/servertest/mcserver.py exec -- "datapack list" "scoreboard players get #built aooni.var"
  python3 tools/servertest/mcserver.py console          # RCON 콘솔 (빈 줄/EOF 로 종료)
  python3 tools/servertest/mcserver.py errors path/to/server.out.log

임시 폴더 위치는 --base 나 환경 변수 AOONI_SERVERTEST_TMP 로 정한다(기본: 시스템 임시 폴더).
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # aooni-server-pack/
PACK_SRC = os.path.join(ROOT, "server", "world", "datapacks", "aooni_mansion")
PROPS_SRC = os.path.join(ROOT, "server", "server.properties")
CACHE = os.path.join(ROOT, ".mcmeta-cache", "server-jars")
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
DEFAULT_VERSION = "1.21.11"

# 로그에서 데이터팩·함수 문제로 볼 만한 줄
ERROR_PATTERNS = [
    "Failed to load function",
    "Couldn't load",
    "Unknown or incomplete command",
    "Incorrect argument",
    "Expected",
    "Whilst parsing",
    "Unknown function",
    "Failed to",
    "Couldn't",
    "Error",
    "Exception",
    "/ERROR]",
]
# 오류 단어가 들어 있지만 문제는 아닌 줄(바닐라 서버가 늘 찍는 것)
IGNORE_PATTERNS = [
    "Picked up JAVA_TOOL_OPTIONS",
    "Failed to save chunks",          # 강제 종료 중에만 나는 경우가 있어 아래에서 따로 판단하지 않음
]
_TS = re.compile(r"^\[\d\d:\d\d:\d\d\] \[")


def log(msg: str) -> None:
    print(f"[mcserver] {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------------ 다운로드/캐시
def _fetch(url: str, timeout: float = 60, retries: int = 6) -> bytes:
    """URL 을 받아 온다. 프록시 등에서 전송이 중간에 끊기면 Range 로 이어 받는다."""
    buf = bytearray()
    last: Exception | None = None
    for attempt in range(retries):
        headers = {"User-Agent": "aooni-servertest/1.0"}
        if buf:
            headers["Range"] = f"bytes={len(buf)}-"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if buf and r.status != 206:      # 서버가 이어 받기를 안 해 주면 처음부터
                    buf.clear()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    buf += chunk
                total = r.headers.get("Content-Range", "").rpartition("/")[2] or r.headers.get("Content-Length")
                if total and total.isdigit() and len(buf) < int(total):
                    raise http.client.IncompleteRead(bytes(buf), int(total) - len(buf))
            return bytes(buf)
        except (http.client.IncompleteRead, ConnectionError, TimeoutError, urllib.error.URLError) as e:
            last = e
            log(f"다운로드가 끊겨 다시 시도합니다({attempt + 1}/{retries}, {len(buf)} 바이트 받음): {type(e).__name__}")
            time.sleep(1 + attempt)
    raise RuntimeError(f"다운로드 실패: {url}: {last}")


def _sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def version_info(version: str) -> dict:
    """버전 JSON(downloads.server, javaVersion 등). 캐시가 있으면 그대로 쓴다."""
    vdir = os.path.join(CACHE, version)
    os.makedirs(vdir, exist_ok=True)
    vjson = os.path.join(vdir, "version.json")
    if os.path.exists(vjson):
        with open(vjson, encoding="utf-8") as f:
            return json.load(f)
    manifest_path = os.path.join(CACHE, "version_manifest_v2.json")
    manifest = None
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    if manifest is None or not any(v["id"] == version for v in manifest["versions"]):
        log("Mojang 버전 매니페스트를 받는 중...")
        data = _fetch(MANIFEST_URL)
        manifest = json.loads(data)
        with open(manifest_path, "wb") as f:
            f.write(data)
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        raise SystemExit(f"Mojang 매니페스트에 없는 버전입니다: {version}")
    data = _fetch(entry["url"])
    if hashlib.sha1(data).hexdigest() != entry["sha1"]:
        raise SystemExit(f"버전 JSON sha1 이 맞지 않습니다: {version}")
    with open(vjson, "wb") as f:
        f.write(data)
    return json.loads(data)


def ensure_jar(version: str = DEFAULT_VERSION) -> str:
    """서버 jar 경로를 돌려준다. 없거나 sha1 이 다르면 새로 받는다."""
    info = version_info(version)
    dl = info["downloads"]["server"]
    jar = os.path.join(CACHE, version, "server.jar")
    if os.path.exists(jar) and _sha1(jar) == dl["sha1"]:
        return jar
    log(f"{version} 서버 jar 를 받는 중... ({dl['size'] / 1e6:.1f} MB)")
    data = _fetch(dl["url"], timeout=300)
    if hashlib.sha1(data).hexdigest() != dl["sha1"]:
        raise SystemExit(f"서버 jar sha1 이 맞지 않습니다: {version}")
    tmp = jar + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, jar)
    return jar


def java_major() -> int:
    try:
        out = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return 0
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out.stderr + out.stdout)
    if not m:
        return 0
    major = int(m.group(1))
    return int(m.group(2)) if major == 1 and m.group(2) else major


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ------------------------------------------------------------------ RCON
class RconError(Exception):
    pass


class Rcon:
    """Source RCON 프로토콜 클라이언트.

    패킷: <int32 길이><int32 요청 id><int32 종류><본문 UTF-8>\\0\\0 (리틀 엔디언)
    종류: 3 로그인, 2 명령, 0 응답.
    서버는 긴 응답을 4096 바이트씩 여러 패킷으로 나눠 보낸다. 끝을 알 수 없으므로
    명령 뒤에 '없는 종류'의 빈 패킷을 하나 더 보내고, 그 응답(id 가 다음 번호)이 올 때까지
    받은 조각을 이어 붙인다. 서버는 요청을 순서대로 처리하므로 이 방식이 안전하다.
    """

    def __init__(self, host: str, port: int, password: str, timeout: float = 15):
        self.host, self.port, self.password, self.timeout = host, port, password, timeout
        self.sock: socket.socket | None = None
        self._id = 0
        self._lock = threading.Lock()

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        rid = self._send(3, self.password)
        _, got_id, _ = self._recv()
        if got_id == -1 or got_id != rid:
            raise RconError("RCON 로그인 실패(비밀번호)")

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _send(self, kind: int, body: str) -> int:
        self._id += 1
        payload = struct.pack("<ii", self._id, kind) + body.encode("utf-8") + b"\x00\x00"
        if len(payload) > 1460:
            raise RconError("RCON 명령이 너무 깁니다(1446 바이트 이하)")
        assert self.sock is not None
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)
        return self._id

    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RconError("RCON 연결이 끊겼습니다")
            buf += chunk
        return buf

    def _recv(self) -> tuple[int, int, bytes]:
        (length,) = struct.unpack("<i", self._recv_exact(4))
        data = self._recv_exact(length)
        rid, kind = struct.unpack("<ii", data[:8])
        return kind, rid, data[8:-2]

    def command(self, cmd: str, timeout: float | None = None) -> str:
        """명령을 실행하고 응답 문자열을 돌려준다(앞의 '/' 는 빼도 되고 넣어도 된다)."""
        cmd = cmd[1:] if cmd.startswith("/") else cmd
        with self._lock:
            if self.sock is None:
                self.connect()
            assert self.sock is not None
            self.sock.settimeout(timeout or self.timeout)
            rid = self._send(2, cmd)
            end_id = self._send(200, "")      # 응답 끝 표시용(서버가 "Unknown request c8" 로 답함)
            parts: list[bytes] = []
            while True:
                _, got, body = self._recv()
                if got == end_id:
                    break
                if got == rid:
                    parts.append(body)
            return b"".join(parts).decode("utf-8", errors="replace")


# ------------------------------------------------------------------ 서버
def _read_props(path: str) -> list[tuple[str, str | None]]:
    """server.properties 를 (키, 값) 목록으로. 주석 줄은 (줄, None)."""
    out: list[tuple[str, str | None]] = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f.read().splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                out.append((line, None))
            else:
                k, v = line.split("=", 1)
                out.append((k.strip(), v))
    return out


def _inside(path: str, parent: str) -> bool:
    path, parent = os.path.realpath(path), os.path.realpath(parent)
    return path == parent or path.startswith(parent + os.sep)


def default_base() -> str:
    base = os.environ.get("AOONI_SERVERTEST_TMP") or os.path.join(tempfile.gettempdir(), "aooni-servertest")
    os.makedirs(base, exist_ok=True)
    return base


class MCServer:
    """일회용 바닐라 서버.

    with MCServer("1.21.11") as srv:
        srv.wait_built()
        print(srv.cmd("datapack list"))
        print(srv.errors())
    """

    def __init__(self, version: str = DEFAULT_VERSION, base: str | None = None, xmx: str = "2G",
                 props: dict | None = None, pack_src: str = PACK_SRC, keep: bool = False,
                 jar: str | None = None):
        self.version = version
        self.base = base or default_base()
        self.xmx = xmx
        self.extra_props = props or {}
        self.pack_src = pack_src
        self.keep = keep
        self.jar = jar
        self.dir: str | None = None
        self.port = 0
        self.rcon_port = 0
        self.rcon_password = secrets.token_hex(12)
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self.log_path: str | None = None
        self._cond = threading.Condition()
        self._reader: threading.Thread | None = None
        self._rcon: Rcon | None = None

    # ---- 준비
    def prepare(self) -> str:
        if _inside(self.base, ROOT):
            raise SystemExit(f"임시 서버 폴더는 저장소 밖이어야 합니다: {self.base}")
        need = version_info(self.version).get("javaVersion", {}).get("majorVersion", 21)
        have = java_major()
        if have < need:
            raise SystemExit(f"{self.version} 서버는 Java {need} 이상이 필요합니다(현재 Java {have}).")
        jar = self.jar or ensure_jar(self.version)
        self.dir = tempfile.mkdtemp(prefix=f"mc-{self.version}-", dir=self.base)
        shutil.copy2(jar, os.path.join(self.dir, "server.jar"))
        shutil.copytree(self.pack_src, os.path.join(self.dir, "world", "datapacks", "aooni_mansion"))
        self.port = free_port()
        self.rcon_port = free_port()
        while self.rcon_port == self.port:
            self.rcon_port = free_port()
        override = {
            "online-mode": "false",
            "enforce-secure-profile": "false",
            "enable-rcon": "true",
            "rcon.port": str(self.rcon_port),
            "rcon.password": self.rcon_password,
            "broadcast-rcon-to-ops": "false",
            "server-port": str(self.port),
            "server-ip": "127.0.0.1",
            "level-type": "minecraft\\:flat",
            "enable-query": "false",
            "pause-when-empty-seconds": "0",     # 1.21.2+: 사람이 없어도 계속 틱(예약 함수가 돌도록)
            "sync-chunk-writes": "false",
            "spawn-protection": "0",
        }
        override.update({k: str(v) for k, v in self.extra_props.items()})
        lines, seen = [], set()
        for k, v in _read_props(PROPS_SRC):
            if v is None:
                lines.append(k)
                continue
            seen.add(k)
            lines.append(f"{k}={override.get(k, v)}")
        for k, v in override.items():
            if k not in seen:
                lines.append(f"{k}={v}")
        with open(os.path.join(self.dir, "server.properties"), "w", encoding="utf-8") as f:
            f.write("# 자동 테스트용 일회용 서버 (tools/servertest/mcserver.py 가 만듦)\n")
            f.write("\n".join(lines) + "\n")
        # 자동 테스트 전용 샌드박스 서버라 EULA 동의를 미리 적어 둔다
        with open(os.path.join(self.dir, "eula.txt"), "w", encoding="utf-8") as f:
            f.write("eula=true\n")
        self.log_path = os.path.join(self.dir, "server.out.log")
        return self.dir

    # ---- 실행
    def start(self, timeout: float = 240) -> "MCServer":
        if self.dir is None:
            self.prepare()
        assert self.dir is not None
        bundle = os.path.join(CACHE, self.version, "bundle")   # 서버 라이브러리 압축 해제를 캐시
        os.makedirs(bundle, exist_ok=True)
        cmd = ["java", f"-Xmx{self.xmx}", "-Xms512M", f"-DbundlerRepoDir={bundle}",
               "-jar", "server.jar", "nogui"]
        log(f"서버 시작: {self.version} 포트 {self.port} RCON {self.rcon_port} 폴더 {self.dir}")
        self.proc = subprocess.Popen(cmd, cwd=self.dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, bufsize=0)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        try:
            self.wait_for(r"Done \(", timeout=timeout)
            self.wait_for(r"RCON running on", timeout=30)
            self._rcon = Rcon("127.0.0.1", self.rcon_port, self.rcon_password)
            self._rcon.connect()
        except BaseException:
            self.stop()
            raise
        log("서버 준비 완료")
        return self

    def _read_loop(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None and self.log_path
        with open(self.log_path, "w", encoding="utf-8") as out:
            for raw in iter(self.proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                out.write(line + "\n")
                out.flush()
                with self._cond:
                    self.lines.append(line)
                    self._cond.notify_all()
        with self._cond:
            self._cond.notify_all()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def mark(self) -> int:
        """지금까지 받은 로그 줄 수. errors(since=...)/wait_for(since=...) 에 쓴다."""
        with self._cond:
            return len(self.lines)

    def wait_for(self, pattern: str, timeout: float = 60, since: int = 0) -> str:
        """로그에 정규식이 나올 때까지 기다린다. 서버가 죽거나 시간이 지나면 예외."""
        rx = re.compile(pattern)
        deadline = time.monotonic() + timeout
        idx = since
        with self._cond:
            while True:
                while idx < len(self.lines):
                    if rx.search(self.lines[idx]):
                        return self.lines[idx]
                    idx += 1
                if not self.alive() and (self._reader is None or not self._reader.is_alive()):
                    tail = "\n".join(self.lines[-30:])
                    raise RuntimeError(f"서버가 꺼졌습니다(기다리던 것: {pattern})\n{tail}")
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(f"{timeout:.0f}초 안에 로그에 '{pattern}' 가 나오지 않았습니다")
                self._cond.wait(min(left, 1.0))

    # ---- 명령
    def cmd(self, command: str, timeout: float = 20) -> str:
        if self._rcon is None:
            raise RuntimeError("서버가 아직 켜지지 않았습니다")
        return self._rcon.command(command, timeout=timeout)

    def score(self, holder: str, objective: str = "aooni.var") -> int | None:
        """scoreboard players get 결과를 정수로(없으면 None)."""
        out = self.cmd(f"scoreboard players get {holder} {objective}")
        m = re.search(r" has (-?\d+) \[", out)
        return int(m.group(1)) if m else None

    def tags(self, name: str) -> list[str]:
        out = self.cmd(f"tag {name} list")
        m = re.search(r"tags: (.*)$", out)
        if not m:
            return []
        return [t.strip() for t in m.group(1).split(",") if t.strip()]

    def players_with_tag(self, tag: str) -> list[str]:
        """tag 를 가진 플레이어 이름 목록(`tag @a[tag=..] list` 응답을 해석)."""
        out = self.cmd(f"tag @a[tag={tag}] list")
        return re.findall(r"(\S+) has \d+ tags", out)

    def wait_built(self, timeout: float = 90) -> float:
        """데이터팩이 저택을 다 지을 때까지(#built = 6) 기다린다. 걸린 초를 돌려준다."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.score("#built") == 6:
                return time.monotonic() - t0
            if not self.alive():
                raise RuntimeError("서버가 꺼졌습니다")
            time.sleep(1)
        raise TimeoutError(f"{timeout:.0f}초 안에 #built 가 6 이 되지 않았습니다(저택 건축 실패?)")

    # ---- 로그 검사
    def errors(self, since: int = 0, ignore: list[str] | tuple = ()) -> list[str]:
        with self._cond:
            lines = list(self.lines[since:])
        return scan_errors(lines, ignore)

    # ---- 종료
    def stop(self, timeout: float = 60) -> int | None:
        if self.proc is None:
            return None
        if self.proc.poll() is None:
            try:
                if self._rcon is not None:
                    self._rcon.command("stop", timeout=10)
            except Exception:
                pass
            try:
                if self.proc.poll() is None and self.proc.stdin:
                    self.proc.stdin.write(b"stop\n")
                    self.proc.stdin.flush()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                log("서버가 제때 꺼지지 않아 강제 종료합니다")
                self.proc.kill()
                self.proc.wait(timeout=15)
        if self._rcon:
            self._rcon.close()
            self._rcon = None
        if self._reader:
            self._reader.join(timeout=5)
        return self.proc.returncode

    def cleanup(self) -> None:
        """서버 폴더를 지운다. 로그(server.out.log)만 base/logs/ 로 옮겨 남긴다."""
        if not self.dir or not os.path.isdir(self.dir):
            return
        if self.keep:
            log(f"서버 폴더를 남겨 둡니다: {self.dir}")
            return
        if self.log_path and os.path.exists(self.log_path):
            logs = os.path.join(self.base, "logs")
            os.makedirs(logs, exist_ok=True)
            dst = os.path.join(logs, os.path.basename(self.dir) + ".log")
            shutil.move(self.log_path, dst)
            self.log_path = dst
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self) -> "MCServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
        self.cleanup()


def scan_errors(lines: list[str], ignore: list[str] | tuple = ()) -> list[str]:
    """로그 줄들에서 문제 줄을 찾는다. 바로 뒤의 이어지는 줄(예외 메시지·스택)도 몇 줄 붙인다."""
    found: list[str] = []
    i = 0
    skip = list(IGNORE_PATTERNS) + list(ignore)
    while i < len(lines):
        line = lines[i]
        if any(p in line for p in ERROR_PATTERNS) and not any(s in line for s in skip):
            block = [line]
            j = i + 1
            while j < len(lines) and not _TS.match(lines[j]):
                if len(block) < 6:
                    block.append(lines[j])
                j += 1
            found.append("\n".join(block))
            i = j
            continue
        i += 1
    return found


def response_is_error(text: str) -> bool:
    """RCON 응답이 명령 오류처럼 보이는지."""
    keys = ("Unknown or incomplete command", "Incorrect argument", "Unknown function", "Expected",
            "<--[HERE]", "No entity was found", "No player was found", "Can't find", "Invalid")
    return any(k in text for k in keys)


# ------------------------------------------------------------------ CLI
def _cli() -> int:
    ap = argparse.ArgumentParser(description="아오오니 데이터팩 일회용 테스트 서버")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("download", help="서버 jar 를 받아 캐시")
    p.add_argument("--version", default=DEFAULT_VERSION)
    for name, hlp in (("exec", "서버를 켜고 명령들을 실행한 뒤 끈다"), ("console", "RCON 콘솔")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--version", default=DEFAULT_VERSION)
        p.add_argument("--base", default=None, help="임시 서버 폴더를 만들 곳(저장소 밖)")
        p.add_argument("--keep", action="store_true", help="끝난 뒤 서버 폴더를 지우지 않음")
        p.add_argument("--no-wait-built", action="store_true", help="저택 건축(#built=6)을 기다리지 않음")
        if name == "exec":
            p.add_argument("commands", nargs="*")
    p = sub.add_parser("errors", help="로그 파일에서 오류 줄 찾기")
    p.add_argument("logfile")
    a = ap.parse_args()

    if a.cmd == "download":
        print(ensure_jar(a.version))
        return 0
    if a.cmd == "errors":
        with open(a.logfile, encoding="utf-8", errors="replace") as f:
            errs = scan_errors(f.read().splitlines())
        for e in errs:
            print(e)
        return 1 if errs else 0

    srv = MCServer(a.version, base=a.base, keep=a.keep)
    try:
        srv.start()
        if not a.no_wait_built:
            log(f"저택 건축 완료까지 {srv.wait_built():.1f}초")
        if a.cmd == "exec":
            for c in a.commands:
                print(f"> {c}\n{srv.cmd(c)}")
        else:
            print("RCON 콘솔입니다. 빈 줄이나 Ctrl-D 로 끝냅니다.")
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    break
                print(srv.cmd(line))
        errs = srv.errors()
        if errs:
            print("\n[로그의 오류 줄]")
            for e in errs:
                print(e)
        return 1 if errs else 0
    finally:
        srv.stop()
        srv.cleanup()
        if srv.log_path:
            log(f"로그: {srv.log_path}")


if __name__ == "__main__":
    sys.exit(_cli())
