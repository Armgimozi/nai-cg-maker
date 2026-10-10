/* 게임 목록·설정 저장소(IndexedDB) + 게임 파일 캐시(Cache Storage) 이름 규칙.
 *
 *   IndexedDB "uniplay"
 *     games : { id, title, kind, entry, size, fileCount, cover, settings, ... }
 *     files : id → [[상대경로, 크기], ...]   (서비스워커의 대소문자 보정·파일 보기용)
 *     kv    : 전역 기본 설정 등
 *   Cache Storage "uniplay-game-<id>" : games/<id>/<경로> → 실제 파일
 *
 * 서비스워커(sw.js)도 같은 DB 를 읽으므로 스키마를 바꾸면 sw.js 도 함께 고칠 것.
 */

export const APP_BASE = new URL("../", import.meta.url);
export const DB_NAME = "uniplay";
export const DB_VERSION = 1;
export const CACHE_PREFIX = "uniplay-game-";

export const gameCacheName = (id) => CACHE_PREFIX + id;
export const gameBaseURL = (id) => new URL(`games/${id}/`, APP_BASE);

/** 상대 경로 → 캐시 키 URL. 공백·한글 등은 브라우저가 요청할 때와 같은 방식으로 인코딩된다. */
export function gameFileURL(id, relPath) {
  const safe = relPath.split("/").map((s) => s.replace(/%/g, "%25").replace(/\?/g, "%3F").replace(/#/g, "%23")).join("/");
  return new URL(safe, gameBaseURL(id)).href;
}

/** 게임별 설정의 기본값. 게임 레코드의 settings 는 이 중 바뀐 것만 담는다. */
export const DEFAULT_SETTINGS = {
  fit: "auto",            // auto(템플릿 비율) | 16:9 | 4:3 | fill(꽉 채우기) | original(손대지 않음)
  dpr: "auto",            // auto(최대 2배) | 0.5 | 0.75 | 1 | 1.5 | 2 | native
  touch: "direct",        // direct(터치 그대로) | mouse(터치→마우스) | trackpad(터치패드)
  orientation: "landscape", // landscape | portrait | any
  preset: "auto",         // 가상 패드 프리셋 이름(auto 면 게임 종류로 결정) — 레이아웃을 편집하면 layout 사용
  layout: null,           // 사용자 편집 레이아웃
  showPad: true,
  padOpacity: 0.55,
  fps: false,
  blockUnityCache: true,  // 유니티 자체 캐시(UnityCache) 끄기 — 같은 파일을 두 번 저장하지 않도록
  isolate: false,         // 멀티스레드 빌드용 교차 출처 격리(COOP/COEP)
  autoSync: true,         // Unity 2022+ 세이브 자동 동기화(autoSyncPersistentDataPath)
  isolateStorage: true,   // 게임별 localStorage 분리(같은 키를 쓰는 다른 게임과 세이브가 섞이지 않게)
  haptics: true,
  autoFullscreen: true,
  keepAwake: true,
};

let dbPromise = null;

export function openDB() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("games")) db.createObjectStore("games", { keyPath: "id" });
      if (!db.objectStoreNames.contains("files")) db.createObjectStore("files");
      if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
    };
    req.onsuccess = () => {
      const db = req.result;
      db.onversionchange = () => { db.close(); dbPromise = null; };
      resolve(db);
    };
    req.onerror = () => { dbPromise = null; reject(req.error); };
    req.onblocked = () => console.warn("[uniplay] DB 업그레이드가 다른 탭 때문에 대기 중");
  });
  return dbPromise;
}

async function run(store, mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode);
    const os = tx.objectStore(store);
    let result;
    const r = fn(os);
    if (r) r.onsuccess = () => { result = r.result; };
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error("트랜잭션 중단"));
  });
}

export const games = {
  all: () => run("games", "readonly", (os) => os.getAll()).then((l) => l || []),
  get: (id) => run("games", "readonly", (os) => os.get(id)),
  put: (g) => run("games", "readwrite", (os) => os.put(g)),
  delete: (id) => run("games", "readwrite", (os) => os.delete(id)),
  /** 부분 갱신(동시 실행돼도 마지막 값이 덮지 않도록 같은 트랜잭션에서 읽고 쓴다). */
  async patch(id, fnOrObj) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("games", "readwrite");
      const os = tx.objectStore("games");
      let out;
      const g = os.get(id);
      g.onsuccess = () => {
        if (!g.result) return;
        out = typeof fnOrObj === "function" ? (fnOrObj(g.result) || g.result) : Object.assign(g.result, fnOrObj);
        os.put(out);
      };
      tx.oncomplete = () => resolve(out);
      tx.onerror = () => reject(tx.error);
    });
  },
};

export const files = {
  get: (id) => run("files", "readonly", (os) => os.get(id)).then((l) => l || []),
  put: (id, list) => run("files", "readwrite", (os) => os.put(list, id)),
  delete: (id) => run("files", "readwrite", (os) => os.delete(id)),
};

export const kv = {
  get: (k) => run("kv", "readonly", (os) => os.get(k)),
  set: (k, v) => run("kv", "readwrite", (os) => os.put(v, k)),
};

export async function globalDefaults() {
  return Object.assign({}, DEFAULT_SETTINGS, (await kv.get("defaults")) || {});
}

/** 게임 종류별 기본값. 티라노스크립트는 스스로 화면 크기를 맞추고(DOM 기반) 캔버스를 효과용으로만 쓰므로
 *  UniPlay 가 캔버스를 옮기면 오히려 화면이 깨진다 → "손대지 않음"이 기본. */
export const KIND_DEFAULTS = {
  tyrano: { fit: "original" },
};

/** 전역 기본값 + 종류별 기본값 + 가져올 때 감지한 값(세로 게임 등) + 게임별 설정을 합친 실효 설정.
 *  "기본값으로" 는 game.settings 만 비우므로 감지한 값은 남는다. */
export async function effectiveSettings(game) {
  return Object.assign(await globalDefaults(), KIND_DEFAULTS[game?.kind] || {}, game?.autoSettings || {}, game?.settings || {});
}

export async function deleteGame(id) {
  await caches.delete(gameCacheName(id));
  await files.delete(id);
  await games.delete(id);
}

export function newId() {
  const a = new Uint8Array(6);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => (b % 36).toString(36)).join("") + Date.now().toString(36).slice(-4);
}

export function formatBytes(n) {
  if (!Number.isFinite(n)) return "-";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n >= 100 || i === 0 ? Math.round(n) : n.toFixed(1)} ${u[i]}`;
}
