/* 플레이 화면: 게임 iframe + 가상 패드 + 터치→마우스 + 메뉴.
 *
 * 게임은 같은 출처의 iframe(games/<id>/index.html)에서 돌고, 서비스워커가 넣은 inject.js 가
 * window.parent.UniPlayHost(아래 host 객체)에 연결된다. 입력은 inject.js 의 API(key/mouse/pad)로 넣는다.
 */

import { games, effectiveSettings, gameFileURL, DEFAULT_SETTINGS } from "./db.js";
import { Controls } from "./controls.js";
import { KEYS, KEY_GROUPS, PAD_BUTTONS, SPECIAL_BINDINGS, PRESETS, presetLayout, autoPreset, layoutUsesPad, bindingLabel } from "./keys.js";
import { h, toast, sheet, dialog, downloadBlob } from "./ui.js";

const $ = (s) => document.querySelector(s);
const params = new URLSearchParams(location.search);
const gameId = params.get("id");
const fromLibrary = params.get("from") === "lib";

const iframe = $("#game");
const loading = $("#loading");
const menuBtn = $("#menu-btn");
const fpsEl = $("#fps");
const touchLayer = $("#touch-layer");
const cursorEl = $("#cursor");

let game = null;
let settings = { ...DEFAULT_SETTINGS };
let api = null;               // inject.js 가 넘겨 주는 게임 쪽 API
let controls = null;
let menu = null;              // 열린 메뉴 시트
let lastPoint = null;         // 마우스 바인딩이 누를 위치
let errorCount = 0;
const logs = [];

/* ───────────── 게임과 연결되는 호스트 객체 ───────────── */

const host = (window.UniPlayHost = {
  gameId,
  settings,
  padWanted: false,
  logs,
  log(level, msg) {
    logs.push({ t: Date.now(), level, msg: String(msg).slice(0, 2000) });
    if (logs.length > 400) logs.splice(0, logs.length - 400);
    if (level === "error" || level === "alert") {
      errorCount++;
      menuBtn.classList.add("has-error");
      const hint = errorHint(msg);
      if (hint) toast(hint, 6000);
    }
  },
  onInject(a) { api = a; },
  onDomReady() { loading.hidden = true; },
  onUnityInstance() {
    loading.hidden = true;
    if (host.padWanted) api?.pad.connect();
    scheduleAutoCover();
  },
  onSavePath(prefix) {
    games.patch(gameId, (g) => {
      g.idbfsPrefixes = Array.from(new Set([...(g.idbfsPrefixes || []), prefix]));
      g.idbfsPrefix = g.idbfsPrefix || prefix;
    }).catch(() => {});
  },
  onFps(v) { if (settings.fps) fpsEl.textContent = `${Math.round(v)} FPS`; },
  onGameGesture(x, y) {
    if (Number.isFinite(x)) lastPoint = { x, y };
    userGesture();
  },
});

function errorHint(msg) {
  const m = String(msg);
  if (/out of memory|Cannot enlarge memory|OOM|memory access out of bounds/i.test(m)) {
    return "메모리가 부족합니다. 메뉴에서 해상도를 낮추거나 다른 앱을 닫고 다시 시작해 보세요.";
  }
  if (/SharedArrayBuffer|crossOriginIsolated/i.test(m)) {
    return "멀티스레드 빌드로 보입니다. 라이브러리 → 게임 설정에서 '격리 모드'를 켜 보세요.";
  }
  if (/WebGL 2|does not support WebGL/i.test(m)) return "이 브라우저/기기에서 WebGL 을 쓸 수 없습니다. Chrome 최신 버전을 써 보세요.";
  if (/Unable to parse|Failed to download|Unable to load file/i.test(m)) return "게임 파일을 읽지 못했습니다. 다시 가져오거나 메뉴 → 로그를 확인해 주세요.";
  return null;
}

/* ───────────── 시작 ───────────── */

async function ensureServiceWorker() {
  if (!("serviceWorker" in navigator)) throw new Error("이 브라우저는 서비스워커를 지원하지 않아 게임을 실행할 수 없습니다.");
  if (navigator.serviceWorker.controller) return;
  await navigator.serviceWorker.register("sw.js", { scope: "./" });
  await navigator.serviceWorker.ready;
  if (navigator.serviceWorker.controller) return;
  await new Promise((resolve) => {
    navigator.serviceWorker.addEventListener("controllerchange", resolve, { once: true });
    setTimeout(resolve, 3000);
  });
  if (!navigator.serviceWorker.controller) {
    if (!sessionStorage.getItem("uniplay-reloaded")) {
      sessionStorage.setItem("uniplay-reloaded", "1");
      location.reload();
      await new Promise(() => {});
    }
    throw new Error("서비스워커가 이 페이지를 제어하지 않습니다. 새로고침(강력 새로고침 말고) 해 주세요.");
  }
}

async function start() {
  if (!gameId) { location.replace("./"); return; }
  try {
    await ensureServiceWorker();
    sessionStorage.removeItem("uniplay-reloaded");
    game = await games.get(gameId);
    if (!game) throw new Error("이 게임을 찾을 수 없습니다. 라이브러리에서 다시 가져와 주세요.");
  } catch (e) {
    loading.querySelector(".msg").textContent = e.message || String(e);
    loading.querySelector(".spinner")?.remove();
    loading.appendChild(h("a", { class: "btn", href: "./" }, "라이브러리로"));
    return;
  }
  document.title = `${game.title} · UniPlay`;
  loading.querySelector(".msg").textContent = `${game.title} 여는 중…`;
  Object.assign(settings, await effectiveSettings(game));

  // 격리 모드는 이 화면부터 COOP/COEP 헤더가 있어야 한다(서비스워커가 ?iso=1 에 붙여 줌)
  if (settings.isolate && !window.crossOriginIsolated) {
    if (params.get("iso") !== "1") {
      params.set("iso", "1");
      location.replace(`?${params}`);
      return;
    }
    toast("이 브라우저에서는 격리 모드를 쓸 수 없어 일반 모드로 실행합니다.", 5000);
  }

  const layout = currentLayout();
  host.padWanted = layoutUsesPad(layout);

  controls = new Controls($("#pad-layer"), {
    send,
    axis: (i, v) => api?.pad.axis(i, v),
    haptics: () => settings.haptics,
  });
  controls.setLayout(layout);
  controls.setOpacity(settings.padOpacity);
  controls.setVisible(settings.showPad);

  setupTouchLayer();
  setupHistory();
  fpsEl.hidden = !settings.fps;

  games.patch(gameId, { lastPlayed: Date.now() }).catch(() => {});
  startPlayClock();

  iframe.addEventListener("load", () => {
    loading.hidden = true;
    if (!api) host.log("warn", "주입 스크립트가 연결되지 않았습니다(가상 패드·마우스 입력 불가).");
  });
  iframe.src = gameFileURL(gameId, game.entry);
  menuBtn.addEventListener("click", openMenu);

  if (!localStorage.getItem("uniplay-menu-tip")) {
    localStorage.setItem("uniplay-menu-tip", "1");
    setTimeout(() => toast("왼쪽 위 ≡ 버튼(또는 뒤로 가기)으로 메뉴 · 가상 패드 · 터치 방식을 바꿀 수 있어요.", 5000), 1500);
  }
}

function currentLayout() {
  if (settings.layout && settings.preset === "custom") return settings.layout;
  const name = settings.preset === "auto" || !PRESETS[settings.preset] ? autoPreset(game.kind) : settings.preset;
  return presetLayout(name);
}

async function saveSetting(key, value) {
  settings[key] = value;
  await games.patch(gameId, (g) => { g.settings = { ...(g.settings || {}), [key]: value }; });
}

/* ───────────── 입력 전달 ───────────── */

function pointerPos() {
  if (settings.touch === "trackpad") return { ...cursor };
  if (lastPoint) return lastPoint;
  const c = api?.findCanvas?.();
  if (c) { const r = c.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }
  return { x: innerWidth / 2, y: innerHeight / 2 };
}

function send(bind, down) {
  if (!bind) return;
  if (bind === "menu") { if (down) openMenu(); return; }
  if (bind === "text") { if (down) openTextInput(); return; }
  if (!api) return;
  if (bind.startsWith("key:")) {
    const codes = bind.slice(4).split("+").filter((c) => KEYS[c]);
    (down ? codes : codes.slice().reverse()).forEach((c) => api.key(KEYS[c], down));
  } else if (bind.startsWith("pad:")) {
    api.pad.button(+bind.slice(4), down);
  } else if (bind.startsWith("mouse:")) {
    const b = +bind.slice(6);
    const p = pointerPos();
    if (down) api.mouse("move", p.x, p.y, { buttons: 0 });
    api.mouse(down ? "down" : "up", p.x, p.y, { button: b, buttons: down ? (b === 2 ? 2 : 1) : 0 });
  } else if (bind.startsWith("wheel:")) {
    if (!down) return;
    const p = pointerPos();
    api.mouse("wheel", p.x, p.y, { deltaY: bind === "wheel:up" ? -120 : 120 });
  }
}

/* ───────────── 터치 → 마우스 / 터치패드 ───────────── */

const cursor = { x: innerWidth / 2, y: innerHeight / 2 };

function moveCursor(x, y) {
  cursor.x = Math.max(0, Math.min(innerWidth - 1, x));
  cursor.y = Math.max(0, Math.min(innerHeight - 1, y));
  cursorEl.style.transform = `translate(${cursor.x}px, ${cursor.y}px)`;
}

function applyTouchMode() {
  const mode = settings.touch;
  touchLayer.hidden = mode === "direct";
  cursorEl.hidden = mode !== "trackpad";
  if (mode === "trackpad") moveCursor(cursor.x, cursor.y);
}

function setupTouchLayer() {
  applyTouchMode();
  const pts = new Map();
  let g = null; // 현재 제스처 상태

  const mouse = (type, x, y, o) => api?.mouse(type, x, y, o);
  const click = (x, y, button = 0) => {
    mouse("move", x, y, { buttons: 0 });
    mouse("down", x, y, { button, buttons: button === 2 ? 2 : 1 });
    mouse("up", x, y, { button, buttons: 0 });
  };
  const endLeft = (x, y) => { if (g?.leftDown) { mouse("up", x, y, { button: 0, buttons: 0 }); g.leftDown = false; } };

  touchLayer.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    try { touchLayer.setPointerCapture(e.pointerId); } catch { /* 무시 */ }
    userGesture();
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now() });
    if (pts.size === 1) {
      const now = performance.now();
      const dragArmed = settings.touch === "trackpad" && g?.lastTapAt && now - g.lastTapAt < 300;
      clearTimeout(g?.timer);
      g = { kind: "one", start: now, moved: false, leftDown: false, dragArmed, lastTapAt: 0 };
      if (settings.touch === "mouse") {
        lastPoint = { x: e.clientX, y: e.clientY };
        mouse("move", e.clientX, e.clientY, { buttons: 0 });
        g.timer = setTimeout(() => { // 길게 누르기 → 우클릭
          if (g && g.kind === "one" && !g.moved && !g.leftDown) {
            click(e.clientX, e.clientY, 2);
            g.kind = "done";
            if (navigator.vibrate && settings.haptics) navigator.vibrate(15);
          }
        }, 450);
      } else if (dragArmed) { // 터치패드: 탭 후 다시 눌러 끌기
        g.leftDown = true;
        mouse("down", cursor.x, cursor.y, { button: 0, buttons: 1 });
      }
    } else if (pts.size === 2) {
      if (g) { clearTimeout(g.timer); endLeft(cursor.x, cursor.y); }
      const [a, b] = [...pts.values()];
      g = { kind: "two", start: performance.now(), moved: false, cy: (a.y + b.y) / 2, acc: 0, tapPoint: settings.touch === "mouse" ? { x: a.sx, y: a.sy } : { ...cursor } };
    }
  });

  touchLayer.addEventListener("pointermove", (e) => {
    const p = pts.get(e.pointerId);
    if (!p || !g) return;
    e.preventDefault();
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    const far = Math.hypot(e.clientX - p.sx, e.clientY - p.sy) > 10;
    if (g.kind === "one") {
      if (settings.touch === "mouse") {
        if (!g.moved && far) {
          g.moved = true;
          clearTimeout(g.timer);
          mouse("down", p.sx, p.sy, { button: 0, buttons: 1 });
          g.leftDown = true;
        }
        if (g.moved) { lastPoint = { x: e.clientX, y: e.clientY }; mouse("move", e.clientX, e.clientY, { buttons: 1, dx, dy }); }
      } else {
        if (far) g.moved = true;
        const k = 1.5;
        moveCursor(cursor.x + dx * k, cursor.y + dy * k);
        mouse("move", cursor.x, cursor.y, { buttons: g.leftDown ? 1 : 0, dx: dx * k, dy: dy * k });
      }
    } else if (g.kind === "two" && pts.size === 2) {
      const [a, b] = [...pts.values()];
      const cy = (a.y + b.y) / 2;
      g.acc += cy - g.cy;
      g.cy = cy;
      if (Math.abs(g.acc) > 12) {
        g.moved = true;
        const at = settings.touch === "mouse" ? { x: (a.x + b.x) / 2, y: cy } : cursor;
        mouse("wheel", at.x, at.y, { deltaY: -g.acc * 4 });
        g.acc = 0;
      }
    }
  });

  const up = (e) => {
    const p = pts.get(e.pointerId);
    if (!p) return;
    pts.delete(e.pointerId);
    if (!g) return;
    const quick = performance.now() - g.start < 300;
    if (g.kind === "one") {
      clearTimeout(g.timer);
      if (settings.touch === "mouse") {
        if (g.leftDown) endLeft(e.clientX, e.clientY);
        else if (!g.moved) click(p.sx, p.sy, 0);
      } else {
        if (g.leftDown) endLeft(cursor.x, cursor.y);
        else if (!g.moved && quick) { click(cursor.x, cursor.y, 0); g.lastTapAt = performance.now(); }
      }
      const keep = g.lastTapAt;
      g = keep ? { kind: "idle", lastTapAt: keep } : null;
    } else if (g.kind === "two" && pts.size === 0) {
      if (!g.moved && quick) click(g.tapPoint.x, g.tapPoint.y, 2);
      g = null;
    }
  };
  touchLayer.addEventListener("pointerup", up);
  touchLayer.addEventListener("pointercancel", up);
  touchLayer.addEventListener("contextmenu", (e) => e.preventDefault());
}

/* ───────────── 전체화면 · 방향 · 화면 꺼짐 방지 ───────────── */

let wakeLock = null;
let fullscreenTried = false;

async function lockOrientation() {
  const o = settings.orientation;
  if (!screen.orientation?.lock) return;
  try {
    if (o === "any") screen.orientation.unlock();
    else await screen.orientation.lock(o);
  } catch { /* 전체화면이 아니면 실패할 수 있음 */ }
}

function userGesture() {
  if (settings.autoFullscreen && !fullscreenTried && !document.fullscreenElement && !matchMedia("(display-mode: fullscreen)").matches) {
    fullscreenTried = true;
    document.documentElement.requestFullscreen?.({ navigationUI: "hide" }).then(lockOrientation, () => lockOrientation());
  } else if (!fullscreenTried) {
    fullscreenTried = true;
    lockOrientation();
  }
  if (settings.keepAwake && !wakeLock && navigator.wakeLock && document.visibilityState === "visible") {
    navigator.wakeLock.request("screen").then((l) => {
      wakeLock = l;
      l.addEventListener("release", () => { wakeLock = null; });
    }, () => {});
  }
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen?.();
  else document.documentElement.requestFullscreen?.({ navigationUI: "hide" }).then(lockOrientation, () => toast("전체화면을 지원하지 않습니다."));
}

/* ───────────── 뒤로 가기 = 메뉴 ───────────── */

let baseHistoryLength = 0;
function setupHistory() {
  baseHistoryLength = history.length; // 이 화면이 마지막 항목일 때의 길이(나갈 때 몇 칸 돌아갈지 계산용)
  history.replaceState({ uniplay: "game" }, "");
  history.pushState({ uniplay: "guard" }, "");
  window.addEventListener("popstate", () => {
    if (leaving) return;
    history.pushState({ uniplay: "guard" }, "");
    if (menu) menu.close();
    else if (controls?.editing) finishEdit(false);
    else openMenu();
  });
}

/* ───────────── 플레이 시간 · 자동 표지 ───────────── */

let clockStart = 0;
function startPlayClock() {
  clockStart = document.visibilityState === "visible" ? Date.now() : 0;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") { clockStart = Date.now(); if (settings.keepAwake) userGestureWakeOnly(); }
    else flushClock();
  });
  window.addEventListener("pagehide", flushClock);
  setInterval(flushClock, 60000);
}
function userGestureWakeOnly() {
  if (!wakeLock && navigator.wakeLock) navigator.wakeLock.request("screen").then((l) => { wakeLock = l; }, () => {});
}
function flushClock() {
  if (!clockStart) return;
  const sec = (Date.now() - clockStart) / 1000;
  clockStart = document.visibilityState === "visible" ? Date.now() : 0;
  if (sec > 1) games.patch(gameId, (g) => { g.playSeconds = (g.playSeconds || 0) + sec; }).catch(() => {});
}

function scheduleAutoCover() {
  if (game.cover) return;
  setTimeout(async () => {
    const shot = await api?.screenshot?.(480);
    if (shot && shot.size > 2000) {
      await games.patch(gameId, (g) => { if (!g.cover) { g.cover = shot; g.coverAuto = true; } });
      game.cover = shot;
    }
  }, 30000);
}

/* ───────────── 메뉴 ───────────── */

function seg(options, value, onPick) {
  const wrap = h("div", { class: "seg" });
  options.forEach(([v, label]) => {
    const b = h("button", { class: v === value ? "on" : "", onclick: () => {
      wrap.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      onPick(v);
    } }, label);
    wrap.appendChild(b);
  });
  return wrap;
}

function selectBox(options, value, onPick) {
  const s = h("select", { class: "field", onchange: () => onPick(s.value) },
    options.map(([v, label]) => h("option", { value: v, selected: String(v) === String(value) }, label)));
  return s;
}

function row(label, control, note) {
  return h("div", { class: "row" }, h("div", { class: "row-label" }, label, note ? h("small", {}, note) : null), control);
}

function toggle(value, onPick) {
  const i = h("input", { type: "checkbox", class: "switch", onchange: () => onPick(i.checked) });
  i.checked = !!value;
  return i;
}

function openMenu() {
  if (menu) return;
  controls?.releaseAll();
  const presetOptions = [
    ["auto", `자동 (${PRESETS[autoPreset(game.kind)].name})`],
    ...Object.entries(PRESETS).map(([k, p]) => [k, p.name]),
    ...(settings.layout ? [["custom", "직접 편집한 배치"]] : []),
  ];
  const action = (icon, label, fn) => h("button", { class: "menu-act", onclick: fn }, h("span", { class: "ic" }, icon), label);

  const body = h("div", { class: "menu" },
    h("div", { class: "menu-grid" },
      action("▶", "계속하기", () => menu.close()),
      action("가", "글자 입력", () => { menu.close(); openTextInput(); }),
      action("🎮", "패드 편집", () => { menu.close(); startEdit(); }),
      action("📷", "스크린샷", () => takeScreenshot(false)),
      action("🖼", "표지로 쓰기", () => takeScreenshot(true)),
      action("⛶", "전체화면", () => { toggleFullscreen(); }),
      action("↻", "다시 시작", () => { menu.close(); restartGame(); }),
      action("📜", `로그${errorCount ? ` (${errorCount})` : ""}`, () => openLogs()),
      action("⏏", "나가기", () => exitGame()),
    ),
    h("h4", {}, "조작"),
    row("가상 패드", selectBox(presetOptions, settings.preset === "custom" && settings.layout ? "custom" : settings.preset, async (v) => {
      await saveSetting("preset", v);
      const layout = currentLayout();
      controls.setLayout(layout);
      host.padWanted = layoutUsesPad(layout);
      if (host.padWanted) api?.pad.connect();
      if (!settings.showPad && layout.length) { await saveSetting("showPad", true); controls.setVisible(true); }
    })),
    row("패드 보이기", toggle(settings.showPad, async (v) => { await saveSetting("showPad", v); controls.setVisible(v); })),
    row("패드 투명도", (() => {
      const r = h("input", { type: "range", min: "0.15", max: "1", step: "0.05", value: settings.padOpacity, class: "range" });
      r.addEventListener("input", () => controls.setOpacity(+r.value));
      r.addEventListener("change", () => saveSetting("padOpacity", +r.value));
      return r;
    })()),
    row("터치 방식", seg([["direct", "터치 그대로"], ["mouse", "터치→마우스"], ["trackpad", "터치패드"]], settings.touch, async (v) => {
      await saveSetting("touch", v);
      applyTouchMode();
      toast({ direct: "게임이 터치를 직접 받습니다.", mouse: "탭=클릭 · 길게=우클릭 · 끌기=드래그 · 두 손가락=스크롤", trackpad: "밀어서 커서 이동 · 탭=클릭 · 두 손가락 탭=우클릭 · 탭 후 다시 눌러 끌기" }[v], 4000);
    }), "게임이 터치에 반응하지 않으면 마우스 방식을 써 보세요"),
    row("진동", toggle(settings.haptics, (v) => saveSetting("haptics", v))),
    h("h4", {}, "화면"),
    row("화면 맞춤", selectBox([["auto", "원래 비율 유지"], ["16:9", "16:9 유지"], ["4:3", "4:3 유지"], ["fill", "꽉 채우기"], ["original", "손대지 않음(다시 시작)"]], settings.fit, async (v) => {
      await saveSetting("fit", v);
      if (v === "original") toast("다시 시작하면 적용됩니다.");
      api?.refit?.();
    })),
    row("해상도", selectBox([["auto", "자동 (최대 2배)"], ["0.5", "0.5배 (가장 빠름)"], ["0.75", "0.75배"], ["1", "1배"], ["1.5", "1.5배"], ["2", "2배"], ["native", "기기 최대 (선명·느림)"]], String(settings.dpr), async (v) => {
      await saveSetting("dpr", v);
      const ok = await dialog({ title: "해상도 변경", body: "다시 시작해야 적용됩니다. 지금 다시 시작할까요? (저장하지 않은 진행은 사라질 수 있어요)", buttons: [{ label: "나중에", value: false }, { label: "다시 시작", value: true, kind: "primary" }] });
      if (ok) { menu?.close(); restartGame(); }
    }), "느리면 낮추세요"),
    row("화면 방향", selectBox([["landscape", "가로 고정"], ["portrait", "세로 고정"], ["any", "자동 회전"]], settings.orientation, async (v) => {
      await saveSetting("orientation", v);
      lockOrientation();
    })),
    row("FPS 표시", toggle(settings.fps, async (v) => { await saveSetting("fps", v); fpsEl.hidden = !v; })),
  );
  menu = sheet(game.title, body, { onClose: () => { menu = null; } });
  menuBtn.classList.remove("has-error");
}

async function takeScreenshot(asCover) {
  const blob = await api?.screenshot?.(asCover ? 480 : 0, asCover ? "image/jpeg" : "image/png");
  if (!blob) { toast("화면을 캡처하지 못했습니다."); return; }
  if (asCover) {
    await games.patch(gameId, { cover: blob, coverAuto: false });
    game.cover = blob;
    toast("라이브러리 표지로 저장했습니다.");
  } else {
    const d = new Date();
    const stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}-${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")}${String(d.getSeconds()).padStart(2, "0")}`;
    downloadBlob(blob, `${game.title.replace(/[\\/:*?"<>|]/g, "_")}-${stamp}.png`);
    toast("스크린샷을 저장했습니다.");
  }
}

function openLogs() {
  const text = logs.map((l) => `[${new Date(l.t).toLocaleTimeString("ko-KR")}] ${l.level.toUpperCase()} ${l.msg}`).join("\n") || "(로그 없음)";
  const pre = h("pre", { class: "logs" }, text);
  const body = h("div", {},
    h("div", { class: "row-actions" },
      h("button", { class: "btn", onclick: () => navigator.clipboard?.writeText(text).then(() => toast("복사했습니다.")) }, "복사"),
      h("button", { class: "btn", onclick: () => { logs.length = 0; errorCount = 0; pre.textContent = "(로그 없음)"; } }, "지우기")),
    pre);
  sheet("로그", body, { wide: true });
  setTimeout(() => { pre.scrollTop = pre.scrollHeight; }, 50);
}

/* ───────────── 글자 입력 ───────────── */

function openTextInput() {
  const input = h("input", { class: "field", type: "text", placeholder: "보낼 글자", autocomplete: "off", enterkeyhint: "send" });
  const sendText = () => {
    if (!input.value) { quick("Enter"); return; }
    const how = api?.typeText(input.value);
    toast(how === "field" ? "입력란에 넣었습니다." : "키 입력으로 보냈습니다.", 1500);
    input.value = "";
  };
  const quick = (code) => {
    if (!api) return;
    if (code === "Backspace") api.editKey?.("Backspace");
    api.key(KEYS[code], true);
    api.key(KEYS[code], false);
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); sendText(); } });
  const body = h("div", { class: "text-input" },
    h("div", { class: "row-actions" }, input, h("button", { class: "btn primary", onclick: sendText }, "보내기")),
    h("div", { class: "row-actions" },
      ["Backspace", "Enter", "Escape", "Tab", "Space"].map((c) => h("button", { class: "btn small", onclick: () => quick(c) }, KEYS[c].label))),
    h("p", { class: "hint" }, "게임의 입력칸을 먼저 누른 뒤 보내세요. 한글은 게임이 지원해야 입력됩니다."));
  sheet("글자 입력", body);
  setTimeout(() => input.focus(), 60);
}

/* ───────────── 패드 편집 ───────────── */

let editBackup = null;
let editBar = null;

function startEdit() {
  editBackup = controls.getLayout();
  controls.setVisible(true);
  controls.setEditing(true);
  touchLayer.hidden = true;
  editBar = h("div", { class: "edit-bar" },
    h("button", { class: "btn small", onclick: () => editProps(controls.add("button")) }, "+ 버튼"),
    h("button", { class: "btn small", onclick: () => editProps(controls.add("dpad")) }, "+ 십자키"),
    h("button", { class: "btn small", onclick: () => editProps(controls.add("stick")) }, "+ 스틱"),
    h("button", { class: "btn small", onclick: pickPresetForEdit }, "프리셋"),
    h("button", { class: "btn small", onclick: () => finishEdit(false) }, "취소"),
    h("button", { class: "btn small primary", onclick: () => finishEdit(true) }, "완료"));
  document.body.appendChild(editBar);
  controls.onSelect = (c) => editProps(c);
  toast("끌어서 옮기고, 탭해서 키·크기를 바꾸세요.", 3500);
}

async function pickPresetForEdit() {
  const name = await dialog({
    title: "프리셋 불러오기",
    body: "지금 배치를 프리셋으로 바꿉니다.",
    buttons: [...Object.entries(PRESETS).map(([k, p]) => ({ label: p.name, value: k })), { label: "취소", value: null }],
  });
  if (name) controls.setLayout(presetLayout(name));
}

async function finishEdit(save) {
  controls.setEditing(false);
  controls.onSelect = null;
  editBar?.remove();
  editBar = null;
  applyTouchMode();
  if (!save) { controls.setLayout(editBackup); return; }
  const layout = controls.getLayout();
  await saveSetting("layout", layout);
  await saveSetting("preset", "custom");
  host.padWanted = layoutUsesPad(layout);
  if (host.padWanted) api?.pad.connect();
  toast("패드 배치를 저장했습니다.");
}

function bindingSelect(value) {
  const s = h("select", { class: "field" });
  const base = (value || "").startsWith("key:") ? value.slice(4).split("+").pop() : value;
  for (const [group, codes] of KEY_GROUPS) {
    s.appendChild(h("optgroup", { label: "키보드 · " + group },
      codes.map((c) => h("option", { value: "key:" + c, selected: "key:" + c === "key:" + base }, KEYS[c].label + (KEYS[c].label !== c ? `  (${c})` : "")))));
  }
  s.appendChild(h("optgroup", { label: "게임패드" },
    PAD_BUTTONS.map((n, i) => h("option", { value: "pad:" + i, selected: base === "pad:" + i }, `패드 ${n}`))));
  s.appendChild(h("optgroup", { label: "마우스 · 기타" },
    SPECIAL_BINDINGS.map(([b, label]) => h("option", { value: b, selected: base === b }, label))));
  return s;
}

function editProps(c) {
  if (!c) return;
  controls.select(c.id);
  const sizeRange = (min, max) => {
    const r = h("input", { type: "range", min, max, step: "0.01", value: c.size, class: "range" });
    r.addEventListener("input", () => controls.update(c.id, { size: +r.value }));
    return r;
  };
  let body;
  if (c.type === "button") {
    const label = h("input", { class: "field", type: "text", value: c.label || "", placeholder: bindingLabel(c.bind) });
    const bind = bindingSelect(c.bind);
    const parts = (c.bind || "").startsWith("key:") ? c.bind.slice(4).split("+") : [];
    const mod = selectBox([["", "없음"], ["ShiftLeft", "Shift"], ["ControlLeft", "Ctrl"], ["AltLeft", "Alt"]], parts.length > 1 ? parts[0] : "", () => {});
    const shape = seg([["round", "원"], ["pill", "알약"]], c.shape === "pill" ? "pill" : "round", (v) => controls.update(c.id, { shape: v }));
    const tog = toggle(c.toggle, (v) => controls.update(c.id, { toggle: v }));
    const apply = () => {
      let b = bind.value;
      if (b.startsWith("key:") && mod.value) b = `key:${mod.value}+${b.slice(4)}`;
      controls.update(c.id, { bind: b, label: label.value.trim() });
    };
    label.addEventListener("input", apply);
    bind.addEventListener("change", apply);
    mod.addEventListener("change", apply);
    body = h("div", {},
      row("동작", bind),
      row("함께 누를 키", mod, "Ctrl+S 같은 조합용"),
      row("표시 이름", label),
      row("크기", sizeRange("0.07", "0.32")),
      row("모양", shape),
      row("누를 때마다 켜기/끄기", tog, "달리기 유지 등"));
  } else {
    const modes = c.type === "dpad"
      ? [["arrows", "방향키"], ["wasd", "WASD"], ["pad", "게임패드 십자키"]]
      : [["arrows", "방향키"], ["wasd", "WASD"], ["pad-left", "게임패드 왼쪽 스틱(아날로그)"], ["pad-right", "게임패드 오른쪽 스틱(아날로그)"]];
    body = h("div", {},
      row("동작", selectBox(modes, c.mode, (v) => controls.update(c.id, { mode: v }))),
      row("크기", sizeRange("0.2", "0.65")));
  }
  body.appendChild(h("div", { class: "row-actions" },
    h("button", { class: "btn danger", onclick: () => { controls.remove(c.id); s.close(); } }, "삭제")));
  const s = sheet(c.type === "button" ? "버튼" : c.type === "dpad" ? "십자키" : "스틱", body);
}

/* ───────────── 다시 시작 · 나가기 ───────────── */

// 유니티 instance.Quit() 은 쓰지 않는다: 메뉴를 한 번 연 뒤 부르면 렌더러가 죽는 경우가 있었고
// (헤드리스 Chromium 141 · SwiftShader 에서 재현), 문서를 바꾸면 어차피 메모리가 모두 풀린다.
const settle = () => new Promise((r) => setTimeout(r, 300)); // 진행 중인 세이브(IndexedDB) 쓰기 마무리

async function restartGame() {
  await settle();
  api = null;
  loading.hidden = false;
  loading.querySelector(".msg").textContent = `${game.title} 다시 시작하는 중…`;
  Object.assign(settings, await effectiveSettings(await games.get(gameId)));
  // iframe.src 를 바꾸면 방문 기록이 쌓여 '나가기'·뒤로 가기가 꼬이므로 replace 로 다시 연다
  try { iframe.contentWindow.location.replace(gameFileURL(gameId, game.entry)); }
  catch { iframe.src = gameFileURL(gameId, game.entry); }
}

let leaving = false;
async function exitGame() {
  if (leaving) return;
  leaving = true;
  menu?.close();
  loading.hidden = false;
  loading.querySelector(".msg").textContent = "저장하고 나가는 중…";
  flushClock();
  await settle();
  wakeLock?.release?.();
  if (document.fullscreenElement) await document.exitFullscreen?.().catch(() => {});
  // 라이브러리에서 왔으면 기록을 되돌아가(게임 화면이 '앞으로'에 남지 않게), 아니면 바꿔치기
  const back = history.length - baseHistoryLength + 1;
  if (fromLibrary && back >= 1 && back < history.length) history.go(-back);
  else location.replace("./");
}

start();
