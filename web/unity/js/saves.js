/* 세이브 백업/복원.
 *
 * 유니티 WebGL 은 PlayerPrefs 와 Application.persistentDataPath 를 IndexedDB "/idbfs"
 * (스토어 FILE_DATA, 키 "/idbfs/<해시>/파일경로")에 저장한다. 게임마다 <해시>가 다르므로
 * inject.js 가 실행 중 처음 저장되는 경로를 기록해 둔 game.idbfsPrefix 로 구분한다.
 * 게임별로 분리된 localStorage("uniplay:<id>:키")도 함께 백업한다(RPG Maker MV, 티라노스크립트 등).
 * 티라노스크립트 PC판 세이브(.sav)도 그대로 가져올 수 있다(내용 형식이 브라우저판과 같음).
 */

import { games } from "./db.js";

const IDBFS = "/idbfs";
const STORE = "FILE_DATA";

function req2promise(r) {
  return new Promise((resolve, reject) => { r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
}

async function dbExists(name) {
  if (indexedDB.databases) {
    try { return (await indexedDB.databases()).some((d) => d.name === name); } catch { /* 모름 */ }
  }
  return true;
}

/** FILE_DATA 스토어가 있는 /idbfs DB 를 연다. create=true 면 없을 때 만든다(에뮬레이터 IDBFS 와 같은 구조). */
async function openIdbfs(create) {
  if (!create && !(await dbExists(IDBFS))) return null;
  let db = await req2promise(indexedDB.open(IDBFS));
  if (db.objectStoreNames.contains(STORE)) return db;
  if (!create) { db.close(); return null; }
  const ver = Math.max(db.version + 1, 21);
  db.close();
  const r = indexedDB.open(IDBFS, ver);
  r.onupgradeneeded = () => {
    const d = r.result;
    if (!d.objectStoreNames.contains(STORE)) d.createObjectStore(STORE).createIndex("timestamp", "timestamp", { unique: false });
  };
  db = await req2promise(r);
  return db;
}

async function allEntries(db) {
  const tx = db.transaction(STORE, "readonly");
  const os = tx.objectStore(STORE);
  const [keys, values] = await Promise.all([req2promise(os.getAllKeys()), req2promise(os.getAll())]);
  return keys.map((k, i) => ({ key: k, value: values[i] }));
}

/** /idbfs 안의 게임별 묶음: prefix → { count, bytes, latest } */
export async function idbfsGroups() {
  const db = await openIdbfs(false);
  if (!db) return new Map();
  try {
    const groups = new Map();
    for (const { key, value } of await allEntries(db)) {
      if (typeof key !== "string") continue;
      const seg = key.split("/")[2];
      if (!seg) continue;
      const p = `${IDBFS}/${seg}`;
      const g = groups.get(p) || { count: 0, bytes: 0, latest: 0 };
      g.count++;
      g.bytes += value?.contents?.byteLength || 0;
      g.latest = Math.max(g.latest, +new Date(value?.timestamp || 0));
      groups.set(p, g);
    }
    return groups;
  } finally { db.close(); }
}

function toB64(u8) {
  let s = "";
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
}
function fromB64(b64) {
  const s = atob(b64);
  const u8 = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u8[i] = s.charCodeAt(i);
  return u8;
}

function lsPrefix(id) { return `uniplay:${id}:`; }

function localStorageEntries(id) {
  const P = lsPrefix(id), out = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith(P)) out[k.slice(P.length)] = localStorage.getItem(k);
  }
  return out;
}

/** 이 게임의 세이브 요약 */
export async function saveSummary(game) {
  const ls = Object.keys(localStorageEntries(game.id)).length;
  let files = 0, bytes = 0, latest = 0;
  const prefixes = game.idbfsPrefixes || (game.idbfsPrefix ? [game.idbfsPrefix] : []);
  if (prefixes.length) {
    const groups = await idbfsGroups();
    for (const p of prefixes) {
      const g = groups.get(p);
      if (g) { files += g.count; bytes += g.bytes; latest = Math.max(latest, g.latest); }
    }
  }
  return { files, bytes, latest, localStorageKeys: ls, prefixes };
}

/** 백업 JSON(Blob) 만들기. prefixes 를 넘기면 그 묶음을 쓴다(게임이 아직 기록 안 했을 때). */
export async function exportSave(game, prefixes) {
  prefixes = prefixes || game.idbfsPrefixes || (game.idbfsPrefix ? [game.idbfsPrefix] : []);
  const idbfs = [];
  const db = prefixes.length ? await openIdbfs(false) : null;
  if (db) {
    try {
      for (const { key, value } of await allEntries(db)) {
        if (typeof key !== "string" || !prefixes.some((p) => key === p || key.startsWith(p + "/"))) continue;
        const c = value?.contents;
        idbfs.push({
          key,
          mode: value?.mode,
          timestamp: new Date(value?.timestamp || Date.now()).toISOString(),
          contents: c ? toB64(new Uint8Array(c.buffer, c.byteOffset, c.byteLength)) : null,
        });
      }
    } finally { db.close(); }
  }
  const localStorageData = localStorageEntries(game.id);
  const data = {
    format: "uniplay-save",
    version: 1,
    exportedAt: new Date().toISOString(),
    game: { id: game.id, title: game.title },
    prefixes,
    idbfs,
    localStorage: localStorageData,
  };
  return {
    blob: new Blob([JSON.stringify(data)], { type: "application/json" }),
    count: idbfs.length + Object.keys(localStorageData).length,
  };
}

/** 백업 복원. 게임의 세이브 경로를 알면 그 경로로 옮겨 넣는다. */
export async function importSave(game, file) {
  let data;
  try { data = JSON.parse(await file.text()); } catch { throw new Error("세이브 백업 파일(JSON)이 아닙니다."); }
  if (data?.format !== "uniplay-save") throw new Error("UniPlay 세이브 백업 파일이 아닙니다.");
  const target = game.idbfsPrefix || null;
  const srcPrefixes = data.prefixes || [];
  const remap = (key) => {
    if (!target) return key;
    for (const p of srcPrefixes) if (key === p || key.startsWith(p + "/")) return target + key.slice(p.length);
    return key;
  };
  let written = 0;
  if (data.idbfs?.length) {
    const db = await openIdbfs(true);
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        const os = tx.objectStore(STORE);
        for (const e of data.idbfs) {
          const value = { timestamp: new Date(e.timestamp), mode: e.mode };
          if (e.contents != null) value.contents = fromB64(e.contents);
          os.put(value, remap(e.key));
          written++;
        }
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      });
    } finally { db.close(); }
    if (!target && srcPrefixes.length) {
      await games.patch(game.id, { idbfsPrefix: srcPrefixes[0], idbfsPrefixes: srcPrefixes });
    }
  }
  for (const [k, v] of Object.entries(data.localStorage || {})) {
    localStorage.setItem(lsPrefix(game.id) + k, v);
    written++;
  }
  return { written, remapped: !!target, unknownTarget: !target && !!data.idbfs?.length };
}

/**
 * 티라노스크립트 PC판 세이브(.sav) 가져오기. 파일 이름이 localStorage 키(<projectID>_tyrano_data 등)이고
 * 내용은 브라우저판과 같은 escape(JSON) 문자열이다.
 */
export async function importTyranoSav(game, fileList) {
  let written = 0;
  const bad = [];
  for (const f of fileList) {
    const m = /^(.+_(sf|tyrano_data|tyrano_quick_save|tyrano_auto_save))\.sav$/.exec(f.name);
    if (!m) { bad.push(f.name); continue; }
    const text = (await f.text()).trim();
    try { JSON.parse(unescape(text)); } catch { bad.push(f.name); continue; }
    localStorage.setItem(lsPrefix(game.id) + m[1], text);
    written++;
  }
  return { written, bad };
}

/** 이 게임의 세이브를 모두 지운다. */
export async function deleteSave(game) {
  const prefixes = game.idbfsPrefixes || (game.idbfsPrefix ? [game.idbfsPrefix] : []);
  if (prefixes.length) {
    const db = await openIdbfs(false);
    if (db) {
      try {
        const keys = (await allEntries(db)).map((e) => e.key)
          .filter((k) => typeof k === "string" && prefixes.some((p) => k === p || k.startsWith(p + "/")));
        await new Promise((resolve, reject) => {
          const tx = db.transaction(STORE, "readwrite");
          keys.forEach((k) => tx.objectStore(STORE).delete(k));
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
        });
      } finally { db.close(); }
    }
  }
  const P = lsPrefix(game.id);
  Object.keys(localStorageEntries(game.id)).forEach((k) => localStorage.removeItem(P + k));
}
