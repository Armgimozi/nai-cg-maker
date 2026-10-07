#!/usr/bin/env python3
"""
실제 바닐라 클라이언트를 가상 화면(Xvfb + mesa llvmpipe)에 띄워 서버에 붙이고 화면을 찍는다 (DESIGN.md 13.4).
보통은 run_client.sh 로 부른다.

  mcclient.py run    <포트> <찍을폴더> [동작...]   켜고 → 동작을 차례로 → 끈다
  mcclient.py start  <포트> <찍을폴더>            켜 두기만 한다 (뒤에서 돈다). 이어서 do 를 여러 번
  mcclient.py do     <포트> [동작...]             켜 둔 클라이언트에 동작
  mcclient.py stop   <포트>
  mcclient.py status <포트>

동작 (한 인수에 하나. 빈칸이 든 것은 따옴표로 묶는다)
  join[:초]              세계에 들어가고 서버 팩까지 실린 뒤 화면이 가라앉을 때까지 (기본 240초)
  wait:초                기다린다 (소수 가능)
  shot:이름              화면을 <찍을폴더>/이름.png 로 (X 화면 그대로, import -window root)
  f2:이름                게임의 F2 스크린샷을 <찍을폴더>/이름.png 로 (채팅에 저장 줄이 남는다)
  key:키[+키]            눌렀다 뗀다. xdotool 이름 (f, w, space, Escape, Return, Tab, F1, F3, 1~9, ctrl+w)
  hold:키[+키]:초        누르고 있다가 뗀다 (앞 키부터 누르고 거꾸로 뗀다)
  sprint:초              hold:Control_L+w:초 (왼쪽 Ctrl 을 먼저 누른 채 W)
  walk:초                hold:w:초
  down:키[+키] / up:키[+키]   누르기만 / 떼기만. 누르고 있는 동안 찍을 때 (down:ctrl+w wait:1 shot:run up:ctrl+w)
  mouse:left|right|middle[:초]   누르기. 초가 있으면 누르고 있기 (에스트·물약 마시기, 막기)
  mdown:버튼 / mup:버튼  마우스 누르기만 / 떼기만 (mdown:right wait:0.8 shot:drinking mup:right)
  look:dx:dy             시점을 돌린다 (마우스 상대 이동, 화면 픽셀)
  slot:N                 단축 슬롯 N (1~9)
  cmd:글                 채팅 창(T)을 열어 글을 치고 Enter. / 로 시작하면 명령 (예: "cmd:/soulstest kill")
  type:글                지금 열린 칸에 글만 친다
  mark                   log: 가 찾기 시작하는 자리를 지금으로 옮긴다 (do 를 부를 때마다 처음엔 그때 자리)
  log:정규식[:초]        mark 뒤 클라이언트 기록에 맞는 줄이 나올 때까지 (기본 30초). 채팅은 "[CHAT] ..." 줄이다
  respawn[:초]           사망 화면의 첫 단추(되살아나기)를 누른다. 단추가 켜질 때(죽고 1초)까지 기다린 뒤 Tab, Enter
  close                  열린 화면을 닫는다 (Escape)

환경 변수 (start/run 에서 읽는다)
  SOULS_CLIENT_HOME  받은 클라이언트와 실행 폴더 (기본 ~/.cache/souls-client). 실행 폴더는 run/<포트>/
  MC_HOST            접속할 곳 (기본 localhost). 주소는 <MC_HOST>:<포트>
  MC_NAME            오프라인 이름 (기본 Tester)
  MC_SIZE            창 크기 (기본 1280x720). 화면 크기도 같게 잡는다
  MC_LANG            클라이언트 언어 (기본 ko_kr. setup 이 받은 언어만)
  MC_GUI_SCALE       GUI 배율 (기본 0 = 자동. 1280x720 이면 3)
  MC_OPTIONS         options.txt 에 더 넣을 줄. "키:값;키:값" (예: "renderDistance:8;fov:0.0")
  MC_XMX             클라이언트 최대 메모리 (기본 2G)
  MC_CLIENT_JAR      처음 받을 때 이미 있는 client.jar 를 쓴다 (sha1 이 맞을 때만)

결과: 찍은 그림 경로를 한 줄씩 "SHOT <경로>" 로 표준 출력에 낸다. run 은 끝날 때 클라이언트 기록을 <찍을폴더>/client.log 로 복사한다.
실패하면 (클라이언트가 죽음, 기다림 시간 초과) 기록 끝 40줄을 보이고 1 로 끝난다.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import setup_client  # noqa: E402

VERSION = "1.21.11"
LOG4J = os.path.join(HERE, "log4j2-client.xml")
JOIN_TIMEOUT = 240
BUTTONS = {"left": 1, "middle": 2, "right": 3}
LOG_TIMEOUT = 30

# 클라이언트 기록에서 읽는 줄 (1.21.11 실측)
#   들어감: 첫 채팅 줄("[System] [CHAT] ...") 또는 "Loaded N advancements"
#   서버 팩: "Reloading ResourceManager: vanilla, server/..." 로 시작한다. 끝났다는 줄은 따로 없어서,
#           그 뒤 아틀라스("Created: ...")·글꼴·소리 엔진 줄이 2초 동안 더 나오지 않으면 끝난 것으로 본다
RE_JOINED = re.compile(r"\[CHAT\]|Loaded \d+ advancements")
RE_PACK_RELOAD = re.compile(r"Reloading ResourceManager: .*server")
RE_PACK_NOISE = re.compile(r"Created: |Found unifont|Sound engine started|OpenAL initialized")
RE_PACK_DONE = re.compile(r"PACK status=SUCCESSFULLY_LOADED")
RE_PACK_FAIL = re.compile(r"PACK status=(FAILED|DECLINED|INVALID|DISCARDED)|Failed to (download|load) .*pack", re.I)
RE_REFUSED = re.compile(r"Couldn't connect to server")
PACK_GRACE = 10     # 들어간 뒤 이만큼 기다려도 서버 팩이 오지 않으면 팩 없는 서버로 본다 (Soulslike 는 1초 뒤에 보낸다)

# options.txt 기본값. 처음 화면(접근성 안내, 다중 플레이 경고, 길잡이)을 모두 건너뛰고,
# 창이 초점을 잃어도 멈춤 메뉴를 띄우지 않는다. 1.21.11 은 graphicsPreset 이 fancy 면 켤 때 시야·구름·그림자 같은
# 값을 그 묶음 값으로 덮어쓴다. 그래서 custom 으로 두고 fancy 값을 그대로 적되 시야만 줄인다 (소프트웨어 렌더링)
BASE_OPTIONS = {
    "version": "4671",
    "onboardAccessibility": "false",
    "skipMultiplayerWarning": "true",
    "joinedFirstServer": "true",
    "tutorialStep": "none",
    "pauseOnLostFocus": "false",
    "inactivityFpsLimit": "\"minimized\"",
    "realmsNotifications": "false",
    "hideSplashTexts": "true",
    "narrator": "0",
    "narratorHotkey": "false",
    "autoJump": "false",
    "fullscreen": "false",
    "enableVsync": "false",
    "maxFps": "30",
    "graphicsPreset": "\"custom\"",
    "renderDistance": "8",
    "simulationDistance": "6",
    "renderClouds": "\"true\"",
    "entityShadows": "true",
    "particles": "0",
    "mipmapLevels": "4",
    "rawMouseInput": "false",
    "soundCategory_master": "0.0",
    "soundCategory_music": "0.0",
    "showAutosaveIndicator": "false",
    "telemetryOptInExtra": "false",
    "musicToast": "\"never\"",
    "resourcePacks": "[\"vanilla\"]",
    "incompatibleResourcePacks": "[]",
}


def say(*a):
    print("[client]", *a, flush=True)


def fail(msg, sess=None):
    say("실패:", msg)
    if sess:
        tail(sess.log_path)
    sys.exit(1)


def tail(path, n=40):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-n:]
        print("".join("  | " + ln for ln in lines), end="", flush=True)
    except OSError:
        pass


def alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # 끝났지만 거두지 않은 프로세스(좀비)는 죽은 것으로 본다
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().split(") ", 1)[1][0] != "Z"
    except OSError:
        return True


def run_dir(port):
    return os.path.join(setup_client.home(), "run", str(port))


# ── NBT (servers.dat, 압축 없음) ──

def _nbt_str(s):
    b = s.encode("utf-8")
    return len(b).to_bytes(2, "big") + b


def servers_dat(address, name="souls"):
    """서버 목록 한 줄. acceptTextures=1 이면 서버 팩을 묻지 않고 받는다.
    빠른 접속(--quickPlayMultiplayer)은 이 목록에서 주소 글자가 똑같은 줄을 찾아 그 설정을 쓴다."""
    entry = (b"\x08" + _nbt_str("ip") + _nbt_str(address)
             + b"\x08" + _nbt_str("name") + _nbt_str(name)
             + b"\x01" + _nbt_str("acceptTextures") + b"\x01"
             + b"\x01" + _nbt_str("hidden") + b"\x00"
             + b"\x00")
    return (b"\x0a" + _nbt_str("")
            + b"\x09" + _nbt_str("servers") + b"\x0a" + (1).to_bytes(4, "big") + entry
            + b"\x00")


def offline_uuid(name):
    """서버가 오프라인 모드에서 쓰는 것과 같은 UUID (OfflinePlayer:<이름> 의 MD5, 판 3)."""
    return str(uuid.UUID(bytes=_md5_v3(("OfflinePlayer:" + name).encode("utf-8"))))


def _md5_v3(data):
    import hashlib
    h = bytearray(hashlib.md5(data).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return bytes(h)


class Session:
    def __init__(self, port):
        self.port = int(port)
        self.dir = run_dir(port)
        self.game = os.path.join(self.dir, "game")
        self.log_path = os.path.join(self.dir, "client.log")
        self.state_path = os.path.join(self.dir, "session.json")
        self.state = {}
        if os.path.isfile(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                self.state = json.load(f)
        self.mark = self.log_size()

    # ── 상태 ──

    def save(self):
        with open(self.state_path + ".part", "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1)
        os.replace(self.state_path + ".part", self.state_path)

    def running(self):
        return alive(self.state.get("java")) and alive(self.state.get("xvfb"))

    @property
    def outdir(self):
        return self.state["outdir"]

    def env(self):
        e = dict(os.environ)
        e["DISPLAY"] = ":%d" % self.state["display"]
        return e

    def log_size(self):
        try:
            return os.path.getsize(self.log_path)
        except OSError:
            return 0

    def log_since(self, pos):
        try:
            with open(self.log_path, "rb") as f:
                f.seek(pos)
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    # ── 켜기·끄기 ──

    def start(self, outdir):
        if self.running():
            fail("포트 %d 의 클라이언트가 이미 켜져 있다 (stop 먼저)" % self.port)
        for tool in ("Xvfb", "xdotool", "import"):
            if not shutil.which(tool):
                fail("%s 이 없다. apt-get install -y xvfb xdotool imagemagick libgl1-mesa-dri" % tool)
        launch = setup_client.load(VERSION) or setup_client.setup(VERSION, os.environ.get("MC_CLIENT_JAR"))
        name = os.environ.get("MC_NAME", "Tester")
        width, height = (int(x) for x in os.environ.get("MC_SIZE", "1280x720").lower().split("x"))
        host = os.environ.get("MC_HOST", "localhost")
        address = "%s:%d" % (host, self.port)
        lang = os.environ.get("MC_LANG", "ko_kr")

        os.makedirs(self.game, exist_ok=True)
        os.makedirs(outdir, exist_ok=True)
        natives = os.path.join(self.dir, "natives")
        os.makedirs(natives, exist_ok=True)

        opts = dict(BASE_OPTIONS)
        opts["lang"] = lang
        opts["guiScale"] = os.environ.get("MC_GUI_SCALE", "0")
        opts["overrideWidth"] = str(width)
        opts["overrideHeight"] = str(height)
        for kv in filter(None, os.environ.get("MC_OPTIONS", "").split(";")):
            k, _, v = kv.partition(":")
            opts[k.strip()] = v.strip()
        with open(os.path.join(self.game, "options.txt"), "w", encoding="utf-8") as f:
            f.writelines("%s:%s\n" % kv for kv in opts.items())
        with open(os.path.join(self.game, "servers.dat"), "wb") as f:
            f.write(servers_dat(address))
        # 지난번 팩·스크린샷은 남겨 두되, 지난번 기록은 지운다
        open(self.log_path, "w").close()

        # 가상 화면. -displayfd 로 빈 번호를 X 가 스스로 고르게 한다 (다른 판과 부딪히지 않는다)
        rfd, wfd = os.pipe()
        xlog = open(os.path.join(self.dir, "xvfb.log"), "w")
        xvfb = subprocess.Popen(
            ["Xvfb", "-displayfd", str(wfd), "-screen", "0", "%dx%dx24" % (width, height),
             "-nolisten", "tcp", "-noreset", "+extension", "GLX", "+extension", "RANDR", "+render"],
            pass_fds=(wfd,), stdout=xlog, stderr=subprocess.STDOUT, start_new_session=True)
        os.close(wfd)
        buf = b""
        deadline = time.time() + 20
        while not buf.endswith(b"\n") and time.time() < deadline:
            chunk = os.read(rfd, 16)
            if not chunk:
                break
            buf += chunk
        os.close(rfd)
        if not buf.strip().isdigit():
            xvfb.kill()
            fail("Xvfb 가 켜지지 않았다 (%s)" % os.path.join(self.dir, "xvfb.log"))
        display = int(buf.strip())

        cmd = [os.environ.get("MC_JAVA", "java"),
               "-Xms512M", "-Xmx" + os.environ.get("MC_XMX", "2G"),
               "-XX:+UseG1GC",
               "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8",
               "-Djava.library.path=" + natives,
               "-Djna.tmpdir=" + natives,
               "-Dorg.lwjgl.system.SharedLibraryExtractPath=" + natives,
               "-Dio.netty.native.workdir=" + natives,
               "-Dlog4j.configurationFile=" + LOG4J,
               "-Dminecraft.launcher.brand=souls-client",
               "-Dminecraft.launcher.version=1",
               "-cp", os.pathsep.join(launch["classpath"]),
               launch["mainClass"],
               "--username", name,
               "--version", VERSION,
               "--gameDir", self.game,
               "--assetsDir", launch["assetsDir"],
               "--assetIndex", launch["assetIndex"],
               "--uuid", offline_uuid(name),
               "--accessToken", "0",
               "--versionType", "release",
               "--width", str(width), "--height", str(height),
               "--quickPlayMultiplayer", address]
        env = dict(os.environ)
        env.update({
            "DISPLAY": ":%d" % display,
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "GALLIUM_DRIVER": "llvmpipe",
            "ALSOFT_DRIVERS": "null",       # 소리 장치가 없으니 OpenAL 은 빈 출력으로
            "__GL_SYNC_TO_VBLANK": "0",
            "vblank_mode": "0",
        })
        # 런처가 쓰는 JAVA_TOOL_OPTIONS 의 프록시 값은 클라이언트가 쓰지 않지만(--proxyHost 가 없으면 직접 연결),
        # 매번 "Picked up" 줄이 섞이니 뺀다
        env.pop("JAVA_TOOL_OPTIONS", None)
        log = open(self.log_path, "ab")
        java = subprocess.Popen(cmd, cwd=self.game, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.state = {"port": self.port, "display": display, "xvfb": xvfb.pid, "java": java.pid,
                      "outdir": os.path.abspath(outdir), "address": address, "name": name,
                      "width": width, "height": height, "started": time.time()}
        self.save()
        self.mark = 0
        say("켜짐: 화면 :%d, java pid %d, 주소 %s, 이름 %s, 기록 %s" % (display, java.pid, address, name, self.log_path))

    def stop(self):
        for key in ("java", "xvfb"):
            pid = self.state.get(key)
            if not alive(pid):
                continue
            try:
                os.killpg(pid, signal.SIGTERM)
            except OSError:
                pass
            for _ in range(50):
                if not alive(pid):
                    break
                time.sleep(0.1)
            if alive(pid):
                try:
                    os.killpg(pid, signal.SIGKILL)
                except OSError:
                    pass
        if self.state:
            self.state["java"] = self.state["xvfb"] = None
            self.save()
        say("꺼짐: 포트 %d" % self.port)

    # ── 입력 ──

    def xdo(self, *args, check=True):
        r = subprocess.run(["xdotool", *[str(a) for a in args]], env=self.env(),
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            fail("xdotool %s: %s" % (" ".join(map(str, args)), r.stderr.strip()), self)
        return r.stdout.strip()

    def window(self):
        wid = self.state.get("window")
        if wid:
            return wid
        deadline = time.time() + 120
        while time.time() < deadline:
            self.check_alive()
            out = self.xdo("search", "--name", "^Minecraft", check=False)
            if out:
                wid = out.split()[-1]
                self.state["window"] = wid
                self.save()
                return wid
            time.sleep(1)
        fail("창을 찾지 못했다", self)

    def focus(self):
        """창 없이(창 관리자 없음) 도는 X 라 초점을 직접 준다. 커서도 창 가운데로 (놓쳤을 때 대비)."""
        wid = self.window()
        self.xdo("windowfocus", wid, check=False)

    def check_alive(self):
        if not alive(self.state.get("java")):
            fail("클라이언트가 꺼져 있다", self)

    def keys(self, spec):
        return [{"ctrl": "Control_L", "shift": "Shift_L", "alt": "Alt_L"}.get(k.lower(), k)
                for k in spec.split("+") if k]

    def hold(self, keys, secs):
        self.focus()
        for k in keys:
            self.xdo("keydown", k)
            time.sleep(0.05)
        time.sleep(max(0.0, secs))
        for k in reversed(keys):
            self.xdo("keyup", k)

    def tap(self, keys):
        self.hold(keys, 0.08)

    def type_text(self, text):
        self.focus()
        self.xdo("type", "--delay", "40", "--", text)

    # ── 화면 ──

    def shot(self, name):
        out = os.path.join(self.outdir, name if name.endswith(".png") else name + ".png")
        r = subprocess.run(["import", "-window", "root", out], env=self.env(), capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(out):
            fail("import: " + r.stderr.strip(), self)
        print("SHOT " + out, flush=True)
        return out

    def f2(self, name):
        sdir = os.path.join(self.game, "screenshots")
        before = set(os.listdir(sdir)) if os.path.isdir(sdir) else set()
        self.tap(["F2"])
        deadline = time.time() + 15
        while time.time() < deadline:
            now = set(os.listdir(sdir)) if os.path.isdir(sdir) else set()
            new = sorted(now - before)
            if new:
                time.sleep(0.5)  # 쓰는 중일 수 있다
                out = os.path.join(self.outdir, name if name.endswith(".png") else name + ".png")
                shutil.copyfile(os.path.join(sdir, new[-1]), out)
                print("SHOT " + out, flush=True)
                return out
            time.sleep(0.2)
        fail("F2 스크린샷이 생기지 않았다", self)

    # ── 기다리기 ──

    def wait_log(self, pattern, timeout, since=None):
        rx = re.compile(pattern)
        pos = self.mark if since is None else since
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.check_alive()
            text = self.log_since(pos)
            for line in text.splitlines():
                if rx.search(line):
                    return line
            time.sleep(0.3)
        fail("%d초 안에 기록에 /%s/ 가 없다" % (timeout, pattern), self)

    def join(self, timeout):
        """접속 → 세계 → (서버 팩이 오면) 팩 다시 싣기 끝 → 2초 가라앉히기."""
        deadline = time.time() + timeout
        self.window()
        joined_at = None
        noise, noise_at = -1, time.time()
        while time.time() < deadline:
            self.check_alive()
            text = self.log_since(0)
            now = time.time()
            if joined_at is None:
                if RE_REFUSED.search(text):
                    fail("접속하지 못했다", self)
                if RE_JOINED.search(text):
                    joined_at = now
                    say("세계에 들어감")
            else:
                m = RE_PACK_RELOAD.search(text)
                if m:
                    after = text[m.end():]
                    if RE_PACK_FAIL.search(after):
                        fail("서버 팩을 싣지 못했다", self)
                    count = len(RE_PACK_NOISE.findall(after))
                    if count != noise:
                        noise, noise_at = count, now
                    if RE_PACK_DONE.search(after) or (count > 0 and now - noise_at >= 2.0):
                        say("서버 팩 실음")
                        break
                elif now - joined_at > PACK_GRACE:
                    say("서버 팩 없음 (%d초 동안 오지 않음)" % PACK_GRACE)
                    break
            time.sleep(0.25)
        else:
            fail("%d초 안에 들어가지 못했다" % timeout, self)
        time.sleep(2)

    # ── 동작 ──

    def act(self, action):
        name, _, rest = action.partition(":")
        name = name.strip().lower()
        say(">", action)
        if name == "join":
            self.join(float(rest or JOIN_TIMEOUT))
        elif name == "wait":
            time.sleep(float(rest))
        elif name == "shot":
            self.check_alive()
            self.shot(rest or "shot-%d" % int(time.time()))
        elif name == "f2":
            self.check_alive()
            self.f2(rest or "f2-%d" % int(time.time()))
        elif name == "key":
            self.tap(self.keys(rest))
        elif name == "hold":
            spec, _, secs = rest.rpartition(":")
            self.hold(self.keys(spec), float(secs))
        elif name == "sprint":
            self.hold(["Control_L", "w"], float(rest or 2))
        elif name == "walk":
            self.hold(["w"], float(rest or 2))
        elif name in ("down", "up"):
            self.focus()
            keys = self.keys(rest)
            for k in (keys if name == "down" else reversed(keys)):
                self.xdo("key" + name, k)
                time.sleep(0.05)
        elif name in ("mdown", "mup"):
            self.focus()
            self.xdo("mousedown" if name == "mdown" else "mouseup", BUTTONS[rest.lower() or "left"])
        elif name == "mouse":
            button, _, secs = rest.partition(":")
            b = BUTTONS[button.lower() or "left"]
            self.focus()
            self.xdo("mousedown", b)
            time.sleep(float(secs) if secs else 0.08)
            self.xdo("mouseup", b)
        elif name == "look":
            dx, _, dy = rest.partition(":")
            self.focus()
            # 한 번에 크게 옮기면 GLFW 가 한 덩이로 받는다. 잘게 나눠 부드럽게 돌린다
            steps = max(1, int(max(abs(float(dx)), abs(float(dy or 0))) // 40))
            for _ in range(steps):
                self.xdo("mousemove_relative", "--", int(float(dx) / steps), int(float(dy or 0) / steps))
                time.sleep(0.03)
        elif name == "slot":
            self.tap([rest.strip()])
        elif name == "cmd":
            self.tap(["t"])
            time.sleep(0.6)
            self.type_text(rest)
            time.sleep(0.2)
            self.tap(["Return"])
            time.sleep(0.3)
        elif name == "type":
            self.type_text(rest)
        elif name == "mark":
            self.mark = self.log_size()
        elif name == "log":
            pattern, timeout = rest, LOG_TIMEOUT
            m = re.match(r"^(.*):(\d+(?:\.\d+)?)$", rest)
            if m:
                pattern, timeout = m.group(1), float(m.group(2))
            say("  찾음:", self.wait_log(pattern, timeout).strip())
        elif name == "respawn":
            time.sleep(float(rest or 1.5))
            self.tap(["Tab"])
            time.sleep(0.2)
            self.tap(["Return"])
            time.sleep(1.0)
        elif name == "close":
            self.tap(["Escape"])
        else:
            fail("모르는 동작: " + action)
        self.check_alive()


def main(argv):
    if len(argv) < 2 or argv[0] not in ("run", "start", "do", "stop", "status"):
        print(__doc__)
        return 2
    verb, port = argv[0], argv[1]
    sess = Session(port)
    if verb == "status":
        print(json.dumps({"running": sess.running(), **sess.state}, ensure_ascii=False, indent=1))
        return 0
    if verb == "stop":
        sess.stop()
        return 0
    if verb in ("run", "start"):
        if len(argv) < 3:
            print(__doc__)
            return 2
        sess.start(argv[2])
        actions = argv[3:]
    else:
        if not sess.running():
            fail("포트 %s 에 켜 둔 클라이언트가 없다 (start 먼저)" % port)
        actions = argv[2:]
    if verb == "start":
        sess.window()
        return 0
    try:
        for action in actions:
            sess.act(action)
    finally:
        if verb == "run":
            try:
                shutil.copyfile(sess.log_path, os.path.join(sess.outdir, "client.log"))
            except OSError:
                pass
            sess.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
