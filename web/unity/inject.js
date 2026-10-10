/* UniPlay 주입 스크립트 — 서비스워커가 게임 index.html 의 <head> 맨 앞에 넣는다.
 * 게임 코드보다 먼저 실행되어 다음을 준비한다.
 *
 *   - 렌더 해상도(devicePixelRatio) 조절, 화면 맞춤(비율 유지/꽉 채우기)
 *   - 유니티 자체 다운로드 캐시(UnityCache) 끄기 → 같은 파일을 두 번 저장하지 않음
 *   - 가상 게임패드(navigator.getGamepads 확장)
 *   - 키보드/마우스/휠 이벤트 주입 API(바깥 플레이어가 호출)
 *   - 게임별 localStorage 분리(같은 출처의 다른 게임과 세이브가 섞이지 않게)
 *   - 세이브 위치(/idbfs/<해시>) 기록, Unity 2022+ 세이브 자동 동기화
 *   - 구버전 UnityLoader 의 "모바일 미지원" 팝업 건너뛰기
 *   - 오류·로그 수집, FPS, 스크린샷
 *   - iframe 안이라 안 되는 것 보정: window.close → 게임 종료, "페이지를 나갈까요?" 확인창 끄기
 *   - 티라노스크립트: 재생 못 하는 동영상 건너뛰기, 화면 크기 다시 맞추기, "탭해서 시작" 안내
 *
 * 바깥 플레이어(play.html)는 같은 출처라 window.parent.UniPlayHost 로 직접 연결된다.
 * 게임 주소를 따로 열면 host 없이도 해상도/캐시/로더 보정만 적용된다.
 */
(function () {
  "use strict";
  if (window.__uniplay) return;

  var script = document.currentScript;
  var gameId = (script && script.getAttribute("data-uniplay-game")) || "";
  var host = null;
  try {
    var ph = window.parent !== window && window.parent.UniPlayHost;
    if (ph && ph.gameId === gameId) host = ph;
  } catch (e) { /* 다른 출처면 무시 */ }
  var S = (host && host.settings) || {};

  var api = (window.__uniplay = {
    gameId: gameId,
    host: host,
    settings: S,
    canvas: null,
    instance: null,
    idbfsPrefixes: [],
    fps: 0,
    mods: { shift: false, ctrl: false, alt: false },
  });

  function call(name) {
    if (!host || typeof host[name] !== "function") return;
    try { return host[name].apply(host, Array.prototype.slice.call(arguments, 1)); } catch (e) { /* 호스트 오류는 게임에 영향 없게 */ }
  }

  /* ───── 로그·오류 수집 ───── */
  function fmt(v) {
    if (v instanceof Error) return v.name + ": " + v.message;
    if (typeof v === "string") return v;
    if (v && typeof v === "object" && Object.keys(v).length > 40) return String(v); // 큰 객체는 직렬화 비용이 커서 생략
    try { return JSON.stringify(v); } catch (e) { return String(v); }
  }
  ["log", "info", "warn", "error"].forEach(function (level) {
    var orig = console[level];
    if (typeof orig !== "function") return;
    console[level] = function () {
      if (host) call("log", level, Array.prototype.map.call(arguments, fmt).join(" "));
      return orig.apply(this, arguments);
    };
  });
  window.addEventListener("error", function (e) {
    if (!e.message) return;
    var where = e.filename ? " @" + e.filename.split("/").pop() + ":" + e.lineno : "";
    call("log", "error", e.message + where);
  });
  window.addEventListener("unhandledrejection", function (e) { call("log", "error", "Promise: " + fmt(e.reason)); });
  var origAlert = window.alert;
  window.alert = function (msg) { call("log", "alert", fmt(msg)); return origAlert.apply(this, arguments); };

  /* ───── 렌더 해상도 ───── */
  var nativeDpr = window.devicePixelRatio || 1;
  var dpr = null;
  if (S.dpr === undefined || S.dpr === "auto") dpr = Math.min(nativeDpr, 2);
  else if (S.dpr !== "native" && +S.dpr > 0) dpr = +S.dpr;
  if (dpr) {
    try { Object.defineProperty(window, "devicePixelRatio", { configurable: true, get: function () { return dpr; } }); } catch (e) { /* 무시 */ }
  }
  api.dpr = dpr || nativeDpr;
  api.nativeDpr = nativeDpr;

  /* ───── UnityCache 끄기 ───── */
  if (S.blockUnityCache !== false && window.IDBFactory) {
    var origOpen = IDBFactory.prototype.open;
    IDBFactory.prototype.open = function (name) {
      if (name === "UnityCache") return failedRequest();
      return origOpen.apply(this, arguments);
    };
  }
  function failedRequest() {
    // 유니티 로더는 open 실패 시 그냥 네트워크(=서비스워커)로 받는다
    var req = new EventTarget();
    req.result = undefined;
    req.error = new DOMException("UniPlay: 유니티 캐시 비활성화", "NotAllowedError");
    req.readyState = "done";
    req.source = null;
    req.transaction = null;
    req.onerror = req.onsuccess = req.onupgradeneeded = req.onblocked = null;
    setTimeout(function () {
      var ev = new Event("error", { cancelable: true });
      req.dispatchEvent(ev);
      if (typeof req.onerror === "function") req.onerror(ev);
    }, 0);
    return req;
  }

  /* ───── 세이브 위치 기록(/idbfs/<해시>/...) ───── */
  if (window.IDBObjectStore) {
    var origPut = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (value, key) {
      try {
        if (typeof key === "string" && key.indexOf("/idbfs/") === 0 && this.name === "FILE_DATA") {
          var seg = key.split("/")[2];
          var prefix = seg && "/idbfs/" + seg;
          if (prefix && api.idbfsPrefixes.indexOf(prefix) < 0) {
            api.idbfsPrefixes.push(prefix);
            call("onSavePath", prefix);
          }
        }
      } catch (e) { /* 무시 */ }
      return origPut.apply(this, arguments);
    };
  }

  /* ───── localStorage 가득 참 알림 ───── */
  // 티라노스크립트 등은 이 오류를 삼키고 "저장했다"고 보여 준다 → 플레이어가 대신 알린다(게임별 분리를 꺼도)
  try {
    var origSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (k, v) {
      try { return origSetItem.apply(this, arguments); } catch (e) {
        if (e && (e.name === "QuotaExceededError" || /quota/i.test(e.message || ""))) call("onStorageFull", String(k), String(v).length);
        throw e;
      }
    };
  } catch (e) { /* 무시 */ }

  /* ───── 게임별 localStorage ───── */
  if (gameId && S.isolateStorage !== false) {
    try {
      var real = window.localStorage;
      var P = "uniplay:" + gameId + ":";
      var keys = function () {
        var out = [];
        for (var i = 0; i < real.length; i++) { var k = real.key(i); if (k && k.indexOf(P) === 0) out.push(k.slice(P.length)); }
        return out;
      };
      var store = {
        getItem: function (k) { return real.getItem(P + k); },
        setItem: function (k, v) { real.setItem(P + k, String(v)); },
        removeItem: function (k) { real.removeItem(P + k); },
        clear: function () { keys().forEach(function (k) { real.removeItem(P + k); }); },
        key: function (i) { var l = keys(); return i < l.length ? l[i] : null; },
      };
      var proxy = new Proxy(store, {
        get: function (t, k) {
          if (k === "length") return keys().length;
          if (Object.prototype.hasOwnProperty.call(t, k)) return t[k];
          if (typeof k === "symbol") return undefined;
          var v = t.getItem(k);
          return v === null ? undefined : v;
        },
        set: function (t, k, v) { t.setItem(k, v); return true; },
        deleteProperty: function (t, k) { t.removeItem(k); return true; },
        has: function (t, k) { return k in t || k === "length" || t.getItem(k) !== null; },
        ownKeys: function () { return keys(); },
        getOwnPropertyDescriptor: function (t, k) {
          var v = t.getItem(k);
          return v === null ? undefined : { value: v, writable: true, enumerable: true, configurable: true };
        },
      });
      Object.defineProperty(window, "localStorage", { configurable: true, get: function () { return proxy; } });
    } catch (e) { /* 저장소 접근 불가 → 원래대로 */ }
  }

  /* ───── 가상 게임패드 ───── */
  var vpad = {
    id: "UniPlay Virtual Gamepad (STANDARD GAMEPAD Vendor: 045e Product: 028e)",
    index: -1,
    connected: false,
    mapping: "standard",
    timestamp: 0,
    axes: [0, 0, 0, 0],
    buttons: [],
    vibrationActuator: null,
    hapticActuators: [],
  };
  for (var b = 0; b < 17; b++) vpad.buttons.push({ pressed: false, touched: false, value: 0 });
  var realGetPads = navigator.getGamepads ? navigator.getGamepads.bind(navigator) : function () { return []; };
  try {
    navigator.getGamepads = function () {
      var list;
      try { list = Array.prototype.slice.call(realGetPads() || []); } catch (e) { list = []; }
      if (!vpad.connected) return list;
      if (vpad.index < 0 || list[vpad.index]) { var free = list.indexOf(null); vpad.index = free < 0 ? list.length : free; }
      while (list.length <= vpad.index) list.push(null);
      list[vpad.index] = padSnapshot();
      return list;
    };
  } catch (e) { /* 일부 브라우저는 덮어쓰기 불가 */ }
  /** 실제 브라우저처럼 부를 때마다 새 스냅숏을 준다. 같은 객체를 돌려주면 "지난번 상태"를 객체째 기억해
   *  비교하는 엔진(티라노스크립트 등)이 버튼이 눌린 것을 알아채지 못한다. */
  function padSnapshot() {
    return {
      id: vpad.id, index: vpad.index, connected: true, mapping: "standard", timestamp: vpad.timestamp,
      axes: vpad.axes.slice(),
      buttons: vpad.buttons.map(function (b) { return { pressed: b.pressed, touched: b.touched, value: b.value }; }),
      vibrationActuator: null, hapticActuators: [],
    };
  }
  function padConnect() {
    if (vpad.connected) return;
    vpad.connected = true;
    vpad.timestamp = performance.now();
    navigator.getGamepads();
    var ev = new Event("gamepadconnected");
    Object.defineProperty(ev, "gamepad", { value: padSnapshot() });
    window.dispatchEvent(ev);
  }
  api.pad = {
    connect: padConnect,
    button: function (i, pressed, value) {
      padConnect();
      var bt = vpad.buttons[i];
      if (!bt) return;
      bt.pressed = bt.touched = !!pressed;
      bt.value = value != null ? value : pressed ? 1 : 0;
      vpad.timestamp = performance.now();
    },
    axis: function (i, v) {
      padConnect();
      vpad.axes[i] = Math.max(-1, Math.min(1, v));
      vpad.timestamp = performance.now();
    },
    state: vpad,
  };
  if (host && host.padWanted) padConnect();

  /* ───── 입력 주입 API ───── */
  function findCanvas() {
    if (api.canvas && api.canvas.isConnected) return api.canvas;
    var c = document.querySelector("#unity-canvas, #unityContainer canvas, #gameContainer canvas, #unity-container canvas, canvas#canvas");
    if (!c) {
      var all = document.getElementsByTagName("canvas"), best = null, area = 0;
      for (var i = 0; i < all.length; i++) {
        var r = all[i].getBoundingClientRect();
        if (r.width * r.height > area) { area = r.width * r.height; best = all[i]; }
      }
      c = best;
    }
    if (c) api.canvas = c;
    return c;
  }
  api.findCanvas = findCanvas;

  function define(ev, name, value) {
    try { Object.defineProperty(ev, name, { configurable: true, get: function () { return value; } }); } catch (e) { /* 무시 */ }
  }
  function keyTarget() {
    var a = document.activeElement;
    if (a && a !== document.body && a !== document.documentElement) return a;
    return findCanvas() || document.body || document;
  }
  function fireKey(type, init, code) {
    var ev = new KeyboardEvent(type, init);
    define(ev, "keyCode", code.keyCode);
    define(ev, "which", code.which);
    define(ev, "charCode", code.charCode);
    keyTarget().dispatchEvent(ev);
  }
  /** k: { key, code, keyCode, location?, char? } */
  api.key = function (k, down) {
    if (k.code === "ShiftLeft" || k.code === "ShiftRight") api.mods.shift = down;
    if (k.code === "ControlLeft" || k.code === "ControlRight") api.mods.ctrl = down;
    if (k.code === "AltLeft" || k.code === "AltRight") api.mods.alt = down;
    var init = {
      key: k.key, code: k.code, location: k.location || 0, bubbles: true, cancelable: true, composed: true,
      view: window, repeat: false, shiftKey: api.mods.shift, ctrlKey: api.mods.ctrl, altKey: api.mods.alt,
    };
    fireKey(down ? "keydown" : "keyup", init, { keyCode: k.keyCode, which: k.keyCode, charCode: 0 });
    if (down && k.char) {
      var cc = k.char.charCodeAt(0);
      init.key = k.char;
      fireKey("keypress", init, { keyCode: cc, which: cc, charCode: cc });
    }
  };

  /** 글자 입력. 유니티 입력란(숨은 <input>)이 포커스돼 있으면 값을 직접 넣고, 아니면 키 이벤트로 보낸다. */
  api.typeText = function (text) {
    var el = document.activeElement;
    if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
      el.value += text;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return "field";
    }
    Array.from(text).forEach(function (ch) {
      var up = ch.toUpperCase();
      var isLetter = /^[a-z]$/i.test(ch);
      var isDigit = /^[0-9]$/.test(ch);
      var k = {
        key: ch, char: ch,
        code: isLetter ? "Key" + up : isDigit ? "Digit" + ch : ch === " " ? "Space" : "",
        keyCode: isLetter ? up.charCodeAt(0) : isDigit ? ch.charCodeAt(0) : ch === " " ? 32 : 0,
      };
      api.key(k, true);
      api.key(k, false);
    });
    return "keys";
  };
  api.editKey = function (which) { // Backspace / Enter 를 입력란에도 반영
    var el = document.activeElement;
    if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA") && which === "Backspace") {
      el.value = el.value.slice(0, -1);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  };

  /** 마우스 주입. x,y 는 이 문서 기준 좌표. type: down|move|up|wheel */
  var lastPointerTarget = null;
  api.mouse = function (type, x, y, o) {
    o = o || {};
    var target = (type === "move" || type === "up") && lastPointerTarget && lastPointerTarget.isConnected
      ? lastPointerTarget : document.elementFromPoint(x, y) || findCanvas() || document.body;
    var buttons = o.buttons || 0;
    var base = {
      bubbles: true, cancelable: true, composed: true, view: window,
      clientX: x, clientY: y, screenX: x, screenY: y, button: o.button || 0, buttons: buttons,
      movementX: o.dx || 0, movementY: o.dy || 0, detail: 1,
      shiftKey: api.mods.shift, ctrlKey: api.mods.ctrl, altKey: api.mods.alt,
    };
    if (type === "wheel") {
      target.dispatchEvent(new WheelEvent("wheel", Object.assign(base, { deltaX: o.deltaX || 0, deltaY: o.deltaY || 0, deltaMode: 0 })));
      return;
    }
    if (type === "down") lastPointerTarget = target;
    var ptype = { down: "pointerdown", move: "pointermove", up: "pointerup" }[type];
    var mtype = { down: "mousedown", move: "mousemove", up: "mouseup" }[type];
    target.dispatchEvent(new PointerEvent(ptype, Object.assign({
      pointerId: 1, pointerType: "mouse", isPrimary: true, width: 1, height: 1, pressure: buttons ? 0.5 : 0,
    }, base)));
    target.dispatchEvent(new MouseEvent(mtype, base));
    if (type === "up") {
      target.dispatchEvent(new MouseEvent(base.button === 2 ? "contextmenu" : "click", base));
      lastPointerTarget = null;
    }
  };

  /* ───── 유니티 인스턴스 잡기 ───── */
  function onInstance(inst, kind) {
    if (!inst || api.instance === inst) return;
    api.instance = inst;
    api.unityKind = kind;
    if (vpad.connected) { vpad.connected = false; padConnect(); }
    call("onUnityInstance", inst, kind);
  }

  // 2020+: 템플릿이 loader.js 를 불러온 뒤 createUnityInstance(canvas, config) 를 부른다.
  function wrapCreate() {
    var f = window.createUnityInstance;
    if (typeof f !== "function" || f.__uniplay) return !!(f && f.__uniplay);
    var w = function (canvas, config, onProgress) {
      config = config || {};
      try {
        if (dpr && S.dpr !== undefined && S.dpr !== "auto") config.devicePixelRatio = dpr; // 사용자가 고른 값 우선
        else if (dpr && config.devicePixelRatio == null) config.devicePixelRatio = dpr;
        if (S.autoSync !== false && config.autoSyncPersistentDataPath === undefined) config.autoSyncPersistentDataPath = true;
      } catch (e) { /* 무시 */ }
      if (canvas) api.canvas = canvas;
      call("onUnityStart", config);
      var p = f.call(this, canvas, config, function (v) { call("onProgress", v); if (onProgress) return onProgress(v); });
      if (p && p.then) p.then(function (inst) { onInstance(inst, "modern"); }, function (err) { call("log", "error", "createUnityInstance 실패: " + fmt(err)); });
      return p;
    };
    w.__uniplay = true;
    try { window.createUnityInstance = w; } catch (e) { return false; }
    return true;
  }
  // 템플릿의 script.onload 직전에 감싸기
  try {
    var onloadDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "onload");
    if (onloadDesc && onloadDesc.set) {
      Object.defineProperty(HTMLScriptElement.prototype, "onload", {
        configurable: true, enumerable: true,
        get: function () { return onloadDesc.get.call(this); },
        set: function (fn) {
          onloadDesc.set.call(this, typeof fn === "function" ? function (ev) { wrapCreate(); return fn.call(this, ev); } : fn);
        },
      });
    }
  } catch (e) { /* 무시 */ }
  // 정적 <script src=loader.js> 다음 인라인 스크립트에서 바로 부르는 경우: 스크립트 실행 사이의 마이크로태스크에서 감싼다
  var mo = new MutationObserver(function (records) {
    wrapCreate();
    if (!fitReady) return;
    // 캔버스가 새로 생겼을 때만(구버전 로더는 캔버스를 나중에 만든다) 다시 맞춘다
    for (var i = 0; i < records.length; i++) {
      var nodes = records[i].addedNodes;
      for (var j = 0; j < nodes.length; j++) {
        var n = nodes[j];
        if (n.nodeName === "CANVAS" || (n.querySelector && n.querySelector("canvas"))) { applyFit(); return; }
      }
    }
  });
  mo.observe(document, { childList: true, subtree: true });

  // 5.6~2019: UnityLoader 전역 객체를 가로채 모바일 경고를 건너뛰고 인스턴스를 잡는다
  var UL;
  try {
    Object.defineProperty(window, "UnityLoader", {
      configurable: true, enumerable: true,
      get: function () { return UL; },
      set: function (v) { UL = v; patchLegacy(v); },
    });
  } catch (e) { /* 무시 */ }
  function wrapProp(obj, name, wrap) {
    if (typeof obj[name] === "function") { obj[name] = wrap(obj[name]); return; }
    var val;
    Object.defineProperty(obj, name, {
      configurable: true, enumerable: true,
      get: function () { return val; },
      set: function (v) { val = typeof v === "function" ? wrap(v) : v; },
    });
  }
  function patchLegacy(L) {
    if (!L || typeof L !== "object" || L.__uniplay) return;
    try { L.__uniplay = true; } catch (e) { return; }
    wrapProp(L, "compatibilityCheck", function (orig) {
      return function (inst, ok) {
        try { if (L.SystemInfo && L.SystemInfo.hasWebGL) return ok(); } catch (e) { /* 원래 검사로 */ }
        return orig.apply(this, arguments);
      };
    });
    wrapProp(L, "instantiate", function (orig) {
      return function () {
        var inst = orig.apply(this, arguments);
        setTimeout(function () { onInstance(inst, "legacy"); }, 0);
        return inst;
      };
    });
  }

  /* ───── 화면 맞춤 ───── */
  var fitReady = false;
  var baseAspect = 0;
  function setImp(el, props) {
    if (!el) return;
    for (var k in props) el.style.setProperty(k, props[k], "important");
  }
  function readBaseAspect() {
    var c = document.querySelector("#unity-canvas, canvas");
    var legacy = document.querySelector("#unityContainer, #gameContainer");
    var w = 0, h = 0;
    if (c && c.getAttribute("width") && c.getAttribute("height")) { w = +c.getAttribute("width"); h = +c.getAttribute("height"); }
    else if (legacy) { w = parseFloat(legacy.style.width) || 0; h = parseFloat(legacy.style.height) || 0; }
    return w > 0 && h > 0 ? w / h : 16 / 9;
  }
  function containers() {
    return Array.prototype.slice.call(document.querySelectorAll("#unity-container, #unityContainer, #gameContainer"));
  }
  function applyFit() {
    var mode = S.fit || "auto";
    if (mode === "original") return;
    var iw = window.innerWidth, ih = window.innerHeight;
    setImp(document.documentElement, { margin: "0", padding: "0", width: "100%", height: "100%", overflow: "hidden", background: "#000" });
    setImp(document.body, { margin: "0", padding: "0", width: "100%", height: "100%", overflow: "hidden", background: "#000" });
    var footer = document.getElementById("unity-footer");
    if (footer) setImp(footer, { display: "none" });
    var box = { left: 0, top: 0, width: iw, height: ih };
    if (mode !== "fill") {
      var a = mode === "16:9" ? 16 / 9 : mode === "4:3" ? 4 / 3 : baseAspect || 16 / 9;
      var w = iw, h = iw / a;
      if (h > ih) { h = ih; w = ih * a; }
      box = { left: Math.round((iw - w) / 2), top: Math.round((ih - h) / 2), width: Math.round(w), height: Math.round(h) };
    }
    var px = function (n) { return n + "px"; };
    var legacy = document.querySelector("#unityContainer, #gameContainer");
    var c = findCanvas();
    if (legacy && (!c || legacy.contains(c))) {
      // 구버전: 컨테이너 크기에 캔버스가 100% 로 맞춰진다
      setImp(legacy, { position: "fixed", left: px(box.left), top: px(box.top), width: px(box.width), height: px(box.height), margin: "0", transform: "none" });
      if (c) setImp(c, { width: "100%", height: "100%" });
    } else {
      containers().forEach(function (el) {
        setImp(el, { position: "fixed", left: "0", top: "0", width: "100%", height: "100%", margin: "0", transform: "none" });
      });
      if (c) setImp(c, { position: "fixed", left: px(box.left), top: px(box.top), width: px(box.width), height: px(box.height), margin: "0", transform: "none" });
    }
  }
  function initPage() {
    baseAspect = readBaseAspect();
    fitReady = true;
    applyFit();
    var css = document.createElement("style");
    css.textContent =
      "canvas{touch-action:none;-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;outline:none}" +
      "html,body{-webkit-tap-highlight-color:transparent;overscroll-behavior:none}";
    (document.head || document.documentElement).appendChild(css);
    call("onDomReady", window);
  }
  window.addEventListener("resize", function () { if (fitReady) applyFit(); });
  api.refit = function () { if (fitReady) applyFit(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initPage);
  else initPage();
  window.addEventListener("load", function () { if (fitReady) applyFit(); });

  /* ───── FPS·스크린샷 ───── */
  var origRAF = window.requestAnimationFrame.bind(window);
  var frames = 0, lastT = -1, since = performance.now();
  var shots = [];
  window.requestAnimationFrame = function (cb) {
    return origRAF(function (t) {
      if (t !== lastT) { frames++; lastT = t; }
      cb(t);
      if (shots.length) takeShots();
    });
  };
  setInterval(function () {
    var now = performance.now();
    api.fps = (frames * 1000) / (now - since);
    frames = 0;
    since = now;
    call("onFps", api.fps);
  }, 1000);
  function takeShots() {
    var list = shots.splice(0);
    var c = findCanvas();
    if (!c || !c.width) { list.forEach(function (s) { s.resolve(null); }); return; }
    list.forEach(function (s) {
      try {
        var scale = Math.min(1, (s.maxW || c.width) / c.width);
        var off = document.createElement("canvas");
        off.width = Math.max(1, Math.round(c.width * scale));
        off.height = Math.max(1, Math.round(c.height * scale));
        off.getContext("2d").drawImage(c, 0, 0, off.width, off.height);
        off.toBlob(function (bl) { s.resolve(bl); }, s.type || "image/jpeg", 0.88);
      } catch (e) { s.resolve(null); }
    });
  }
  /** 다음 프레임이 그려진 직후의 화면을 이미지로. 게임이 멈춰 있으면 1초 뒤 바로 찍는다. */
  api.screenshot = function (maxW, type) {
    return new Promise(function (resolve) {
      var s = { maxW: maxW, type: type, resolve: resolve };
      shots.push(s);
      setTimeout(function () { if (shots.indexOf(s) >= 0) takeShots(); }, 1000);
    });
  };

  /* ───── iframe 안이라 안 되는 것들 ───── */
  // 게임의 "종료" 버튼(window.close)은 iframe 에서 아무 일도 안 한다 → 플레이어가 라이브러리로 나간다
  try { window.close = function () { call("onGameClose"); }; } catch (e) { /* 무시 */ }
  // "페이지를 나갈까요?" 확인창(티라노 useCloseConfirm 등) 끄기. 핸들러는 그대로 실행해서 저장 같은 마무리는 된다.
  // (다시 시작·나가기는 플레이어가 직접 확인한다)
  (function () {
    var BU = "beforeunload", wrapped = new WeakMap(), propFn = null, propWrapped = null;
    var add = window.addEventListener, remove = window.removeEventListener;
    function tame(fn) {
      return function (e) {
        try {
          Object.defineProperty(e, "returnValue", { configurable: true, get: function () { return ""; }, set: function () {} });
          e.preventDefault = function () {};
        } catch (x) { /* 무시 */ }
        try { typeof fn === "function" ? fn.call(window, e) : fn && fn.handleEvent && fn.handleEvent(e); } catch (x) { /* 무시 */ }
      };
    }
    try {
      window.addEventListener = function (type, fn, opt) {
        if (type !== BU || !fn) return add.apply(this, arguments);
        if (!wrapped.has(fn)) wrapped.set(fn, tame(fn));
        return add.call(this, type, wrapped.get(fn), opt);
      };
      window.removeEventListener = function (type, fn, opt) {
        if (type === BU && fn && wrapped.has(fn)) return remove.call(this, type, wrapped.get(fn), opt);
        return remove.apply(this, arguments);
      };
      var accessor = {
        configurable: true,
        get: function () { return propFn; },
        set: function (fn) {
          if (propWrapped) remove.call(window, BU, propWrapped);
          propFn = typeof fn === "function" ? fn : null;
          propWrapped = propFn ? tame(propFn) : null;
          if (propWrapped) add.call(window, BU, propWrapped);
        },
      };
      Object.defineProperty(window, "onbeforeunload", accessor);
      // document.body.onbeforeunload = … 은 window 의 처리기를 바로 바꾸므로 같은 길로 돌린다
      [window.HTMLBodyElement, window.HTMLFrameSetElement].forEach(function (C) {
        if (C) Object.defineProperty(C.prototype, "onbeforeunload", accessor);
      });
    } catch (e) { /* 무시 */ }
    // <body onbeforeunload="…"> 속성: 지우고(처리기 해제) 같은 코드를 길들인 처리기로 다시 단다
    document.addEventListener("DOMContentLoaded", function () {
      var b = document.body, code = b && b.getAttribute("onbeforeunload");
      if (!code) return;
      b.removeAttribute("onbeforeunload");
      try { window.onbeforeunload = new Function("event", code); } catch (e) { /* 무시 */ }
    });
  })();

  /* ───── 티라노스크립트 ───── */
  // [movie] 는 재생 오류를 처리하지 않아 폰이 못 여는 동영상(.ogv 등)에서 게임이 멈춘다 → 끝난 것으로 처리
  document.addEventListener("error", function (e) {
    var t = e.target, v = t && t.tagName === "SOURCE" ? t.parentNode : t;
    if (!v || v.tagName !== "VIDEO" || !window.TYRANO || !v.closest || !v.closest("#tyrano_base, .tyrano_base")) return;
    if (t !== v && t.nextElementSibling && t.nextElementSibling.tagName === "SOURCE") return; // 다음 후보가 있음
    if (v.__uniplaySkipped) return;
    v.__uniplaySkipped = true;
    var blend = v.classList && v.classList.contains("blendvideo"); // [layermode_movie]
    // 반복 재생하는 [layermode_movie] 는 엔진이 이미 다음으로 넘어갔다(페이드인 때) → '끝남'을 보내면 한 줄을 건너뛴다
    if (blend && v.loop) { call("log", "warn", "동영상을 재생할 수 없습니다: " + (v.currentSrc || v.src || "")); return; }
    call("log", "warn", "동영상을 재생할 수 없어 건너뜁니다: " + (v.currentSrc || v.src || (t && t.src) || ""));
    // [bgmovie] 대기열: 끝난 영상의 ended 처리기는 대기열(video_stack)이 남아 있으면 다음 영상을 또 만든다.
    // 대기 중이던 영상(아직 id 가 bgmovie 가 아님)이 실패하면 대기열을 비워 같은 실패가 끝없이 반복되지 않게 한다.
    var st = window.TYRANO && TYRANO.kag && TYRANO.kag.stat;
    var queued = !v.id && !blend; // id 없는 <video> = [bgmovie] 대기열에서 만든 다음 영상
    if (st && st.video_stack && queued) st.video_stack = null;
    setTimeout(function () {
      v.dispatchEvent(new Event("ended"));
      if (queued && v.parentNode) v.parentNode.removeChild(v);
    }, 0);
  }, true);
  // 폰에서 티라노는 $.fn.click 을 tap 으로 바꿔(터치 전용) 대사 넘기기·버튼 처리기가 "tap" 이벤트에만 붙는다.
  // 그래서 엔진 자신의 Enter·게임패드 "다음"($(".layer_event_click").trigger("click"))과 UniPlay 의
  // 마우스 입력(터치→마우스·터치패드·가상 패드의 클릭)이 아무것도 못 한다 → tap 처리기로 이어 준다.
  function tapOnly(el) {
    var jq = window.jQuery, ev = jq && jq._data && jq._data(el, "events");
    return !!(ev && ev.tap && ev.tap.length && !(ev.click && ev.click.length));
  }
  function tyranoTapMode() {
    var jq = window.jQuery;
    return !!(window.TYRANO && jq && jq.fn && jq.fn.tap && jq.fn.click === jq.fn.tap);
  }
  function inTouchEnd() { var e = window.event; return !!(e && e.type === "touchend"); } // 진짜 탭은 엔진이 직접 tap 을 부른다
  var tapHooked = false;
  function hookTyranoTap() {
    if (tapHooked || !tyranoTapMode()) return;
    tapHooked = true;
    var jq = window.jQuery, origTrigger = jq.fn.trigger;
    jq.fn.trigger = function (ev) {
      var type = typeof ev === "string" ? ev : ev && ev.type;
      var r = origTrigger.apply(this, arguments);
      if (type === "click" && !inTouchEnd()) {
        this.each(function () { if (tapOnly(this)) origTrigger.call(jq(this), "tap"); });
      }
      return r;
    };
  }
  document.addEventListener("click", function (e) {
    // jQuery 의 trigger("click") 도 기본 동작으로 elem.click() 을 불러 여기로 오는데, 그쪽은 위 trigger 가 처리한다
    if (e.isTrusted || !tyranoTapMode() || inTouchEnd() || window.jQuery.event.triggered === "click") return;
    for (var el = e.target; el && el !== document; el = el.parentNode) {
      if (el.nodeType === 1 && tapOnly(el)) { window.jQuery(el).trigger("tap"); return; }
    }
  }, true);
  var tapTimer = setInterval(function () { hookTyranoTap(); if (tapHooked) clearInterval(tapTimer); }, 300);
  setTimeout(function () { clearInterval(tapTimer); }, 60000);

  // 엔진은 100ms 안에 연달아 온 resize 를 버려서 회전·전체화면 직후 크기가 어긋날 수 있다 → 잠시 뒤 한 번 더
  var nudge = 0;
  window.addEventListener("resize", function (e) {
    if (!e.isTrusted || !window.TYRANO) return;
    clearTimeout(nudge);
    nudge = setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 400);
  });
  // 첫 [playbgm] 은 소리 재생 허락(첫 탭)을 기다리며 화면을 멈춰 둔다 → "탭하면 시작" 안내
  (function () {
    var tries = 0;
    var t = setInterval(function () {
      if (++tries > 60) { clearInterval(t); return; }
      var jq = window.jQuery, base = document.querySelector(".tyrano_base");
      if (!window.TYRANO || !jq || !jq._data || !base) return;
      var ev = jq._data(base, "events");
      if (ev && ev.click && ev.click.some(function (h) { return h.namespace === "bgm"; })) {
        clearInterval(t);
        call("onHint", "tapToStart");
        // 첫 탭으로 대기가 풀리면(click.bgm 해제) 안내를 내린다
        var w = setInterval(function () {
          var e2 = base.isConnected ? jq._data(base, "events") : null;
          if (!e2 || !e2.click || !e2.click.some(function (h) { return h.namespace === "bgm"; })) {
            clearInterval(w);
            call("onHint", "started");
          }
        }, 200);
      }
    }, 250);
  })();

  /* ───── 사용자 제스처 → 바깥(전체화면·화면 꺼짐 방지) ───── */
  ["pointerdown", "touchstart", "keydown"].forEach(function (t) {
    window.addEventListener(t, function (e) {
      if (e.isTrusted === false) return; // 플레이어가 넣은 가짜 입력은 제외
      var p = e.touches && e.touches[0] ? e.touches[0] : e;
      call("onGameGesture", p.clientX, p.clientY);
    }, { capture: true, passive: true });
  });

  call("onInject", api);
})();
