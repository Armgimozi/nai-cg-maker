/* UniPlay 서비스워커.
 *
 * 1) games/<id>/... 요청 → 기기에 설치된 게임 파일(Cache Storage)로 응답한다.
 *    - 게임 첫 화면 html 에는 inject.js 를 <head> 맨 앞에 끼워 넣는다(가상 패드·해상도·세이브 연동).
 *    - Content-Type/Length, HEAD, Range(동영상 탐색), 대소문자·폴더가 다른 경로 보정.
 *    - 격리 모드 게임은 COOP/COEP 헤더를 붙여 SharedArrayBuffer(멀티스레드 빌드)를 쓸 수 있게 한다.
 * 2) 앱 화면(셸)은 네트워크 우선 + 2.5초 안에 응답이 없으면 캐시(잠든 무료 서버·오프라인 대비).
 */
const VERSION = "uniplay-shell-v1";
const SHELL_PREFIX = "uniplay-shell-";
const GAME_PREFIX = "uniplay-game-";
const SCOPE = new URL(self.registration.scope);
const GAMES_PATH = new URL("games/", SCOPE).pathname;
const INJECT_URL = new URL("inject.js", SCOPE).pathname + "?v=" + VERSION;

const SHELL_FILES = [
  "./", "index.html", "play.html", "manifest.webmanifest", "inject.js",
  "css/app.css",
  "js/db.js", "js/zip.js", "js/importer.js", "js/library.js", "js/player.js",
  "js/controls.js", "js/keys.js", "js/saves.js", "js/ui.js", "js/pcbuild.js", "js/porting.js",
  "vendor/brotli-decode.js",
  "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png",
];

const ISO_HEADERS = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
};

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    // 하나가 실패해도 나머지는 캐시되도록 개별 처리
    await Promise.all(SHELL_FILES.map((f) =>
      fetch(new Request(new URL(f, SCOPE), { cache: "reload" }))
        .then((r) => (r.ok ? cache.put(new URL(f, SCOPE).href, r) : null))
        .catch(() => null)));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith(SHELL_PREFIX) && k !== VERSION).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (e) => {
  if (e.data === "uniplay:ping") e.source?.postMessage("uniplay:pong");
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" && req.method !== "HEAD") return;
  const url = new URL(req.url);
  if (url.origin !== SCOPE.origin) return;
  if (url.pathname.startsWith(GAMES_PATH)) {
    e.respondWith(serveGame(req, url).catch((err) => textResponse(500, "UniPlay 오류: " + err)));
    return;
  }
  if (url.pathname.startsWith(SCOPE.pathname) && req.method === "GET") {
    e.respondWith(serveShell(e, req, url));
  }
});

/* ───────────── 앱 셸 ───────────── */

async function serveShell(e, req, url) {
  const cache = await caches.open(VERSION);
  const key = url.origin + url.pathname;
  const net = fetch(req).then((res) => {
    if (res && res.ok && res.type === "basic") {
      const copy = res.clone();
      e.waitUntil(cache.put(key, copy).catch(() => {}));
    }
    return res;
  });
  e.waitUntil(net.catch(() => {}));
  const cached = await cache.match(key, { ignoreSearch: true });
  let res;
  if (cached) {
    const timer = new Promise((r) => setTimeout(() => r(cached), 2500));
    res = await Promise.race([net.then((r) => (r.ok ? r : cached), () => cached), timer]);
  } else {
    try { res = await net; } catch { return textResponse(503, "오프라인입니다. 인터넷에 연결한 뒤 다시 열어 주세요."); }
  }
  // 격리 모드로 여는 플레이 화면(?iso=1)에는 COOP/COEP 를 붙인다
  if (req.mode === "navigate" && url.searchParams.get("iso") === "1") return withHeaders(res, ISO_HEADERS);
  return res;
}

/* ───────────── 게임 파일 ───────────── */

let dbPromise = null;
function openDB() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const r = indexedDB.open("uniplay", 1);
    r.onupgradeneeded = () => { // js/db.js 와 같은 스키마
      const db = r.result;
      if (!db.objectStoreNames.contains("games")) db.createObjectStore("games", { keyPath: "id" });
      if (!db.objectStoreNames.contains("files")) db.createObjectStore("files");
      if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
    };
    r.onsuccess = () => { r.result.onversionchange = () => { r.result.close(); dbPromise = null; }; resolve(r.result); };
    r.onerror = () => { dbPromise = null; reject(r.error); };
  });
  return dbPromise;
}

async function idbGet(store, key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const q = db.transaction(store).objectStore(store).get(key);
    q.onsuccess = () => resolve(q.result);
    q.onerror = () => reject(q.error);
  });
}

const metaCache = new Map(); // id → { at, game, defaults, lower }
async function gameInfo(id, fresh) {
  const hit = metaCache.get(id);
  if (hit && !fresh && Date.now() - hit.at < 2000) return hit;
  const [game, defaults] = await Promise.all([idbGet("games", id).catch(() => null), idbGet("kv", "defaults").catch(() => null)]);
  const info = { at: Date.now(), game, defaults: defaults || {}, lower: hit?.lower || null, byName: hit?.byName || null };
  metaCache.set(id, info);
  return info;
}

/** 정확한 경로가 없을 때: 대소문자 무시 → (그래도 없으면) 파일 이름만으로 찾기.
 *  폴더 구조 없이 파일만 골라 넣은 경우(안드로이드 파일 선택 등)에도 Build/xxx 요청이 맞춰진다. */
async function fuzzyPath(id, info, rel) {
  if (!info.lower) {
    const list = (await idbGet("files", id).catch(() => null)) || [];
    info.lower = new Map(list.map(([p]) => [p.toLowerCase(), p]));
    const byName = new Map();
    for (const [p] of list) {
      const n = p.slice(p.lastIndexOf("/") + 1).toLowerCase();
      byName.set(n, byName.has(n) ? null : p); // 같은 이름이 여럿이면 쓰지 않음
    }
    info.byName = byName;
  }
  const low = rel.toLowerCase();
  return info.lower.get(low) || info.byName.get(low.slice(low.lastIndexOf("/") + 1)) || null;
}

function encodeRel(rel) {
  return rel.split("/").map((s) => s.replace(/%/g, "%25").replace(/\?/g, "%3F").replace(/#/g, "%23")).join("/");
}

function safeDecode(s) {
  try { return decodeURIComponent(s); } catch { return s; }
}

async function serveGame(req, url) {
  const rest = url.pathname.slice(GAMES_PATH.length);
  const slash = rest.indexOf("/");
  const id = slash < 0 ? rest : rest.slice(0, slash);
  const cacheName = GAME_PREFIX + id;
  if (!id || !(await caches.has(cacheName))) {
    return htmlResponse(404, "이 게임은 기기에 없습니다. 라이브러리에서 다시 가져와 주세요.");
  }
  const cache = await caches.open(cacheName);
  const isDoc = req.mode === "navigate" || req.destination === "iframe" || req.destination === "document";
  const info = await gameInfo(id, isDoc); // 문서는 방금 바꾼 설정(격리 모드 등)을 바로 반영
  const base = GAMES_PATH + id + "/";
  let rel = slash < 0 ? "" : safeDecode(rest.slice(slash + 1));
  if (rel === "" || rel.endsWith("/")) rel += rel === "" ? (info.game?.entry || "index.html") : "index.html";

  let hit = await cache.match(url.origin + url.pathname);
  if (!hit) hit = await cache.match(new URL(base + encodeRel(rel), url.origin).href);
  if (!hit) {
    const fixed = await fuzzyPath(id, info, rel);
    if (fixed) { rel = fixed; hit = await cache.match(new URL(base + encodeRel(fixed), url.origin).href); }
  }
  if (!hit) {
    if (req.mode === "navigate") return htmlResponse(404, "파일을 찾을 수 없습니다: " + rel);
    return textResponse(404, "Not found: " + rel);
  }

  const settings = Object.assign({}, info.defaults, info.game?.settings || {});
  const isEntry = info.game && rel === info.game.entry;
  const headers = new Headers({
    "Content-Type": hit.headers.get("Content-Type") || "application/octet-stream",
    "Cache-Control": "no-cache",
    "Accept-Ranges": "bytes",
  });
  if (info.game?.addedAt) {
    headers.set("Last-Modified", new Date(info.game.addedAt).toUTCString());
    headers.set("ETag", `"${id}-${info.game.addedAt}"`);
  }
  // 격리된 플레이 화면(?iso=1) 안의 iframe 문서는 반드시 COEP 가 있어야 열린다
  const isoParent = /[?&]iso=1(&|$)/.test(req.referrer || "");
  if (settings.isolate || isoParent) {
    headers.set("Cross-Origin-Resource-Policy", "same-origin");
    if (isDoc) for (const [k, v] of Object.entries(ISO_HEADERS)) headers.set(k, v);
  }

  let blob = await hit.blob();
  if (isEntry && isDoc && /html/i.test(headers.get("Content-Type"))) {
    blob = await injectScript(blob, id);
  }

  const range = req.headers.get("Range");
  if (range && !isDoc) {
    const m = /^bytes=(\d*)-(\d*)$/.exec(range.trim());
    if (m && (m[1] || m[2])) {
      const size = blob.size;
      let start, end;
      if (m[1]) { start = +m[1]; end = m[2] ? Math.min(+m[2], size - 1) : size - 1; }
      else { start = Math.max(0, size - +m[2]); end = size - 1; }
      if (start >= size || start > end) {
        headers.set("Content-Range", `bytes */${size}`);
        return new Response(null, { status: 416, headers });
      }
      headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
      headers.set("Content-Length", String(end - start + 1));
      return new Response(req.method === "HEAD" ? null : blob.slice(start, end + 1), { status: 206, headers });
    }
  }
  headers.set("Content-Length", String(blob.size));
  return new Response(req.method === "HEAD" ? null : blob, { status: 200, headers });
}

/** html 바이트에서 <head>(없으면 <html>/doctype) 바로 뒤에 inject.js 태그를 넣는다. 원본 인코딩은 그대로 둔다. */
async function injectScript(blob, id) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const head = new TextDecoder("latin1").decode(bytes.subarray(0, Math.min(bytes.length, 65536)));
  const m = /<head(\s[^>]*)?>/i.exec(head) || /<html(\s[^>]*)?>/i.exec(head) || /<!doctype[^>]*>/i.exec(head);
  const pos = m ? m.index + m[0].length : 0;
  const tag = new TextEncoder().encode(`<script src="${INJECT_URL}" data-uniplay-game="${id}"></script>`);
  return new Blob([bytes.subarray(0, pos), tag, bytes.subarray(pos)], { type: blob.type });
}

/* ───────────── 유틸 ───────────── */

function withHeaders(res, extra) {
  const h = new Headers(res.headers);
  for (const [k, v] of Object.entries(extra)) h.set(k, v);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
}

function textResponse(status, text) {
  return new Response(text, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

function htmlResponse(status, msg) {
  const esc = String(msg).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  return new Response(
    `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
    `<body style="margin:0;display:grid;place-items:center;height:100vh;background:#101216;color:#ddd;font:15px system-ui,sans-serif;text-align:center;padding:24px;box-sizing:border-box">` +
    `<div>${esc}</div></body>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8" } });
}
