/* 게임 가져오기: zip/폴더 → 빌드 판별 → Cache Storage 에 설치.
 *
 * 판별 순서
 *   1) 유니티 2020+  : *.loader.js 를 참조하는 html (createUnityInstance)
 *   2) 유니티 5.6~2019: UnityLoader.js + UnityLoader.instantiate
 *   3) html 없이 Build 폴더만 있으면 실행용 index.html 을 만들어 준다
 *   4) RPG Maker MV/MZ, 티라노스크립트(TyranoBuilder 포함)
 *   5) PC판 HTML5 게임 포장 풀기 — NW.js(package.nw, 게임.exe 뒤에 붙은 zip), Electron(resources/app.asar)
 *      안에서 꺼낸 파일로 1)~4) 를 다시 판별한다
 *   6) 그 밖의 HTML5 게임(index.html, NW.js package.json 의 main)도 실행은 시도한다
 *   7) 위가 전부 아니면 Windows/맥/안드로이드 빌드인지 알려 준다
 *      (PC 유니티 빌드면 pcbuild.js 로 모바일 변환 가능성을 진단해 err.report 로 붙인다)
 *
 * Build 폴더의 .gz/.br 파일은 여기서 미리 풀어 둔다. 원래는 웹서버가
 * "Content-Encoding" 헤더를 붙여 줘야 하는데, 서비스워커가 만든 응답에는
 * 그 헤더가 효과가 없기 때문(브라우저가 풀어 주지 않음).
 */

import { readZip } from "./zip.js";
import { isAsar, readAsar } from "./asar.js";
import { inspectPcBuild, readHead } from "./pcbuild.js";
import { gameCacheName, gameFileURL, newId, games, files as fileStore, globalDefaults } from "./db.js";
import { stripTyranoThumbs } from "./saves.js";

export class ImportError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

const JUNK = /(^|\/)(__MACOSX|\.git|\.svn)(\/|$)|(^|\/)(\.DS_Store|Thumbs\.db|desktop\.ini)$/i;

const MIME = {
  html: "text/html", htm: "text/html", js: "text/javascript", mjs: "text/javascript", css: "text/css",
  json: "application/json", wasm: "application/wasm", xml: "application/xml", txt: "text/plain",
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
  svg: "image/svg+xml", ico: "image/x-icon", bmp: "image/bmp", avif: "image/avif",
  mp3: "audio/mpeg", ogg: "audio/ogg", oga: "audio/ogg", wav: "audio/wav", m4a: "audio/mp4", aac: "audio/aac",
  mp4: "video/mp4", m4v: "video/mp4", webm: "video/webm", ogv: "video/ogg",
  woff: "font/woff", woff2: "font/woff2", ttf: "font/ttf", otf: "font/otf",
};

export function mimeFor(path) {
  if (/\.unityweb$/i.test(path)) return "application/octet-stream"; // 로더가 직접 푸는 압축 데이터
  const clean = path.replace(/\.(gz|br)$/i, "");
  const ext = clean.slice(clean.lastIndexOf(".") + 1).toLowerCase();
  return MIME[ext] || "application/octet-stream";
}

const dirname = (p) => { const i = p.lastIndexOf("/"); return i < 0 ? "" : p.slice(0, i); };
const basename = (p) => p.slice(p.lastIndexOf("/") + 1);
const depth = (p) => p.split("/").length - 1;
const under = (root, p) => !root || p.startsWith(root + "/");
const relTo = (root, p) => (root ? p.slice(root.length + 1) : p);
const relDir = (from, to) => (from ? relTo(from, to) : to); // to 는 from 아래에 있다고 가정

/* ───────────── 원본 모으기 ───────────── */

/** zip 파일 → 항목 목록 */
export async function entriesFromZip(file) {
  const list = await readZip(file);
  return list.filter((e) => !e.dir).map((e) => ({ path: e.path, size: e.size, open: e.open }));
}

/** Electron app.asar → 항목 목록. unpackedEntries: 같은 폴더의 app.asar.unpacked/ 아래 항목(경로는 그 안 기준) */
async function entriesFromAsar(blob, unpackedEntries) {
  const map = new Map((unpackedEntries || []).map((e) => [e.path, e]));
  return readAsar(blob, (p) => map.get(p) || null);
}

/**
 * 파일 하나 → 항목 목록. zip 말고도 PC판 HTML5 게임의 포장을 바로 연다:
 * NW.js 의 package.nw(=zip), 뒤에 zip 이 붙은 게임.exe, Electron 의 app.asar.
 */
export async function entriesFromFile(file) {
  if (await isAsar(file)) return entriesFromAsar(file, null);
  if (/\.asar$/i.test(file.name || "")) throw new ImportError("PACKAGE", BROKEN_ASAR(file.name));
  try {
    return await entriesFromZip(file);
  } catch (e) {
    if (/\.exe$/i.test(file.name || "")) {
      throw new ImportError("WINDOWS", "이 .exe 파일 안에는 게임 파일이 묶여 있지 않습니다.\n\n" +
        "게임 폴더 전체(.exe 와 같은 폴더에 있는 파일·폴더 모두)를 zip 으로 압축해서 넣어 주세요. " +
        "티라노스크립트·RPG Maker MV/MZ 같은 HTML5 게임이면 그 안에서 게임을 꺼내 실행합니다.");
    }
    throw e;
  }
}

/** <input webkitdirectory> 또는 여러 파일 선택 → 항목 목록 */
export function entriesFromFiles(fileList) {
  return Array.from(fileList, (f) => ({
    path: (f.webkitRelativePath || f.relativePath || f.name).replace(/\\/g, "/").replace(/^\/+/, ""),
    size: f.size,
    open: async () => f,
  }));
}

async function readText(entry, max = 4 << 20) {
  if (entry.size > max) return "";
  const body = await entry.open();
  return body instanceof Blob ? body.text() : new Response(body).text();
}

/** 텍스트 읽기: UTF-8 이 아니면 Shift_JIS(일본 PC 게임)로 다시 읽는다 */
async function readTextGuess(entry, max) {
  if (entry.size > max) return "";
  const bytes = new Uint8Array(await (await readBlob(entry)).arrayBuffer());
  try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { /* 아래로 */ }
  try { return new TextDecoder("shift_jis").decode(bytes); } catch { return new TextDecoder().decode(bytes); }
}

async function readBlob(entry) {
  const body = await entry.open();
  return body instanceof Blob ? body : new Response(body).blob();
}

/* ───────────── 판별 ───────────── */

function cleanTitle(t) {
  return (t || "")
    .replace(/^\s*Unity\s+Web(GL)?\s+Player\s*\|\s*/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function configValue(text, key) {
  const m = new RegExp(`["']?${key}["']?\\s*:\\s*(["'\`])((?:(?!\\1).){1,120})\\1`).exec(text);
  return m ? m[2] : "";
}

function htmlTitle(text) {
  const m = /<title[^>]*>([^<]*)<\/title>/i.exec(text);
  return m ? cleanTitle(m[1].replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")) : "";
}

function baseName(sourceName) {
  return (sourceName || "").replace(/\.(zip)$/i, "").replace(/[_]+/g, " ").trim();
}

function platformError(paths) {
  const has = (re) => paths.some((p) => re.test(p));
  const winHint =
    "이 앱은 유니티 WebGL(브라우저) 빌드만 실행합니다. PC 빌드는 x86 Windows 프로그램이라 " +
    "브라우저에서 돌릴 수 없어요.\n\n" +
    "• 개발자가 브라우저(WebGL/HTML5) 버전을 주면 그 파일을 넣어 주세요.\n" +
    "• PC 빌드를 꼭 폰에서 돌리려면 Winlator 같은 Windows 에뮬레이터 앱이 필요합니다.";
  // 원본 프로젝트가 들어 있으면(빌드 결과물이 같이 있어도) 그것부터 안내한다
  if (has(/(^|\/)Assets\/.+\.(unity|cs)$/i) && has(/(^|\/)ProjectSettings\//i)) {
    return new ImportError("PROJECT", "유니티 프로젝트 원본입니다. Unity 에디터에서 이 프로젝트를 열고 File → Build Settings(Unity 6 은 Build Profiles) → WebGL 로 빌드한 결과물(zip)을 넣어 주세요. 원본이 있으니 가장 확실한 방법입니다.");
  }
  if (has(/(^|\/)UnityPlayer\.dll$/i) || has(/_Data\/(globalgamemanagers|data\.unity3d|resources\.assets)$/i) && has(/\.exe$/i)) {
    return new ImportError("WINDOWS", "Windows용 유니티 게임입니다 (UnityPlayer.dll · _Data 폴더).\n\n" + winHint);
  }
  if (has(/\.app\/Contents\/(MacOS|Resources)\//i)) {
    return new ImportError("MAC", "macOS용 게임(.app)입니다.\n\n" + winHint.replace("x86 Windows", "macOS"));
  }
  if (has(/\.x86(_64)?$/i) && has(/_Data\//i)) {
    return new ImportError("LINUX", "Linux용 유니티 게임입니다.\n\n" + winHint.replace("x86 Windows", "Linux"));
  }
  if (has(/\.(apk|xapk|apks|aab)$/i) || has(/(^|\/)assets\/bin\/Data\//i)) {
    return new ImportError("ANDROID", "안드로이드용 빌드(APK)입니다. 이 앱이 아니라 폰에 바로 설치해서 실행하면 됩니다.");
  }
  if (has(/(^|\/)(Game\.rgss\w*|Game\.ini)$/i)) {
    return new ImportError("RGSS", "RPG Maker XP/VX/VX Ace 게임입니다. 이 형식은 JoiPlay 같은 전용 앱으로 실행해 주세요.");
  }
  if (has(/(^|\/)renpy\//i) || has(/\.rpa$/i)) {
    return new ImportError("RENPY", "Ren'Py 게임입니다. 이 형식은 JoiPlay 같은 전용 앱으로 실행해 주세요.");
  }
  if (has(/\.exe$/i)) {
    return new ImportError("WINDOWS", "Windows 프로그램(.exe)이 들어 있는 게임입니다.\n\n" + winHint);
  }
  return new ImportError("NO_GAME", "실행할 수 있는 게임을 찾지 못했습니다.\n유니티 WebGL 빌드라면 index.html 과 Build 폴더(*.loader.js 또는 UnityLoader.js)가 들어 있어야 해요.");
}

/* ───────────── 티라노스크립트 ───────────── */

/** Config.tjs → { 키: 값 } — 엔진의 compileConfig(kag.parser.js)와 같은 규칙으로 읽는다 */
export function tyranoConfig(text) {
  const map = {};
  for (const raw of String(text || "").split("\n")) {
    let line = raw.trim();
    if (!line.startsWith(";")) continue;
    const c = line.indexOf("//");
    if (c >= 0) line = line.slice(0, c).trim();
    line = line.replace(/;/g, "").replace(/"/g, "");
    const parts = line.split("=");
    map[parts[0].trim()] = (parts[1] || "").trim();
  }
  return map;
}

/** Config.tjs 의 ";키 = 값" 줄을 바꾼다(없으면 끝에 붙인다). 다른 줄은 손대지 않는다. */
function setTyranoConfigLine(text, key, value) {
  const re = new RegExp(`^[ \\t]*;[ \\t]*${key}[ \\t]*=[^\\r\\n]*`, "gm");
  return re.test(text) ? text.replace(re, `;${key} = ${value};`) : `${text.replace(/\s*$/, "")}\n;${key} = ${value};\n`;
}

const THUMB_MAX_WIDTH = 480;

/**
 * 폰 브라우저에서 문제가 되는 설정 고치기.
 *   - configSave = file : PC판 전용 "파일 세이브" → 브라우저에서는 경고창이 반복되고 시작도 못 한다 → webstorage
 *   - ScreenRatio = default : 화면 크기 조절 안 함 → 폰에서 화면이 잘린다 → fix(비율 유지)
 *   - 세이브 썸네일 PNG 원본 크기 : 슬롯 하나가 1MB 를 넘어 모든 게임이 함께 쓰는 브라우저 저장소(약 5MB)를
 *     금방 채우고, 엔진은 실패를 알리지 않는다 → JPEG(middle) · 가로 480px 이하
 * @returns {{ text: string, notes: string[] }}
 */
export function patchTyranoConfig(text, cfg = tyranoConfig(text), engine = { scale: true, quality: true }) {
  let out = String(text);
  const notes = [];
  if (/^file$/i.test(cfg.configSave || "")) {
    out = setTyranoConfigLine(out, "configSave", "webstorage");
    notes.push("PC판 전용 '파일 세이브' 설정을 브라우저 저장소 세이브로 바꿔 설치합니다.");
  }
  // 엔진은 fix·fit 일 때만 화면에 맞춰 늘이고 줄인다(그 밖의 값이나 줄이 없으면 원래 크기 그대로 → 폰에서 잘림)
  if (!/^(fix|fit)$/.test(cfg.ScreenRatio || "")) {
    out = setTyranoConfigLine(out, "ScreenRatio", "fix");
    notes.push("화면 크기 맞춤(ScreenRatio)이 꺼져 있어 폰 화면에 맞도록 켰습니다.");
  }
  if (cfg.configThumbnail !== "false" && !engine.scale) {
    // 2022년 8월 이전 엔진(V4·초기 V5)은 썸네일 크기를 줄일 수 없다(V4.50 이하는 화질 설정도 없음 = 원본 PNG)
    // → 슬롯 하나가 수백 KB~수 MB 라 몇 번 저장하면 저장소가 찬다 → 썸네일을 끈다
    out = setTyranoConfigLine(out, "configThumbnail", "false");
    notes.push("이 게임의 엔진(옛 버전)은 세이브 썸네일을 줄일 수 없어 썸네일을 껐습니다(브라우저 저장 공간 절약).");
  } else if (cfg.configThumbnail !== "false") {
    let thumb = false;
    if (!/^(low|middle)$/.test(cfg.configThumbnailQuality || "")) { out = setTyranoConfigLine(out, "configThumbnailQuality", "middle"); thumb = true; }
    // 엔진 기본값은 1(원본 크기). 썸네일 가로가 480px 을 넘으면 그 이하로 줄인다(1280→0.37, 1920→0.25)
    const width = +cfg.scWidth > 0 ? +cfg.scWidth : 1280;
    const scale = parseFloat(cfg.configThumbnailScale);
    const eff = scale > 0 ? Math.min(scale, 1) : 1;
    if (eff * width > THUMB_MAX_WIDTH) {
      out = setTyranoConfigLine(out, "configThumbnailScale", String(Math.floor((THUMB_MAX_WIDTH / width) * 100) / 100));
      thumb = true;
    }
    if (thumb) notes.push("세이브 썸네일을 작게 저장하도록 바꿨습니다(브라우저 저장 공간 절약).");
  }
  return { text: out, notes };
}

// PC 전용 기능(Node.js·NW.js·Electron·Steam)을 부르는 플러그인/스크립트 흔적.
// UMD 래퍼(require("jquery"))나 Emscripten(ENVIRONMENT_IS_NODE 일 때만 require("fs")) 처럼
// Node 인지 먼저 확인하고 쓰는 코드는 브라우저에서 문제없으므로 빼고 센다.
const TYRANO_PC_ONLY = new RegExp([
  "\\brequire\\s*\\(\\s*[\"'`](fs|fs-extra|original-fs|path|os|child_process|electron|nw\\.gui|greenworks|steamworks[\\w.-]*|adm-zip)[\"'`]\\s*\\)",
  "\\bnw\\.(gui|Window|App|Shell)\\b", "\\bstudio_api\\b", "\\bgreenworks\\b", "\\bsteamworks\\b",
].join("|"));
const NODE_GUARD = /ENVIRONMENT_IS_NODE|typeof\s+(require|process|module|nw)\b\s*[!=]=|[!=]=\s*typeof\s+(require|process|module|nw)\b|\$\.isNWJS\s*\(|\$\.isElectron\s*\(/;

/** 가져올 때 미리 알려 줄 호환성 문제(경고만, 실행은 막지 않음) */
async function tyranoCompat(entries, dir) {
  const notes = [];
  const j = (p) => (dir ? dir + "/" + p : p);
  const hits = new Set();
  let budget = 24 << 20;
  const scripts = entries.filter((e) => (e.path.startsWith(j("data/others/")) && /\.js$/i.test(e.path)) ||
    (e.path.startsWith(j("data/scenario/")) && /\.ks$/i.test(e.path)));
  for (const e of scripts) {
    if (e.size > 2 << 20 || (budget -= e.size) < 0) continue;
    try {
      const t = await readText(e);
      if (TYRANO_PC_ONLY.test(t) && !NODE_GUARD.test(t)) hits.add(relTo(dir, e.path));
    } catch { /* 무시 */ }
    if (hits.size >= 3) break;
  }
  if (hits.size) {
    notes.push(`PC 전용 기능(Node.js·Steam 등)을 쓰는 스크립트가 있어 그 부분은 동작하지 않을 수 있어요: ${[...hits].join(", ")}`);
  }
  const videos = entries.filter((e) => e.path.startsWith(j("data/video/")));
  if (videos.some((e) => /\.(ogv|wmv|avi)$/i.test(e.path)) && !videos.some((e) => /\.(webm|mp4|m4v)$/i.test(e.path))) {
    notes.push("동영상이 폰 브라우저에서 재생되지 않는 형식(.ogv 등)이라 동영상 장면은 건너뜁니다.");
  }
  return notes;
}

/** 이 엔진이 썸네일 크기·화질 설정을 읽는지(2022-08 이후 configThumbnailScale, V4.55 이후 configThumbnailQuality).
 *  kag.menu.js 를 못 찾으면(합쳐서 압축한 빌드 등) 읽는다고 본다. */
async function tyranoEngineSupport(entries, dir) {
  const m = entries.find((e) => e.path === (dir ? dir + "/" : "") + "tyrano/plugins/kag/kag.menu.js");
  if (!m || m.size > 4 << 20) return { scale: true, quality: true };
  try {
    const t = await readText(m);
    return { scale: t.includes("configThumbnailScale"), quality: t.includes("configThumbnailQuality") };
  } catch { return { scale: true, quality: true }; }
}

/** readme.txt 첫 줄의 엔진 버전("…Ver6.00（C）ShikemokuMK") */
async function tyranoVersion(entries, dir) {
  const r = entries.find((e) => e.path === (dir ? dir + "/readme.txt" : "readme.txt"));
  if (!r || r.size > 1 << 20) return "";
  try {
    const first = (await readText(r)).split("\n")[0];
    const m = /Tyrano\S*.*?Ver\.?\s*(\d+(?:\.\d+)?)/i.exec(first);
    return m ? m[1] : "";
  } catch { return ""; }
}

const TYRANO_SAVE = /^(.+)_(sf|tyrano_data|tyrano_quick_save|tyrano_auto_save)\.sav$/;

/**
 * PC판 세이브(<projectID>_tyrano_data.sav 등) 찾기. 내용은 브라우저판 localStorage 값과 같은
 * escape(JSON) 문자열이라 그대로 옮기면 이어서 할 수 있다.
 * @returns {Promise<Record<string,string>>} localStorage 키 → 값
 */
async function tyranoPcSaves(entries, projectID) {
  const out = {};
  if (!projectID) return out;
  for (const e of entries) {
    const m = TYRANO_SAVE.exec(basename(e.path));
    if (!m || m[1] !== projectID || e.size > 64 << 20) continue;
    const key = basename(e.path).replace(/\.sav$/, "");
    try {
      const text = (await readText(e, 64 << 20)).trim();
      JSON.parse(unescape(text)); // 깨진 파일은 건너뛴다
      // 같은 키가 여러 곳(예: 맥의 _TyranoGameData 와 exe 옆)에 있으면 큰 쪽(더 많이 저장된 쪽)
      // 원본 크기 썸네일은 빼고 넣는다(저장 공간) — 엔진이 다음 저장 때 다시 만든다
      if (!out[key] || text.length > out[key].length) out[key] = stripTyranoThumbs(text);
    } catch { /* 무시 */ }
  }
  return out;
}

/* ───────────── PC판 HTML5 포장(NW.js · Electron) ───────────── */

const BROKEN_ASAR = (name) => `Electron 게임(${name})이지만 app.asar 를 열 수 없습니다. ` +
  "파일이 손상됐거나, 꺼내지 못하게 일부러 변형(보호)한 경우입니다.";

// NW.js 런타임 파일(이 폴더의 .exe 는 뒤에 게임 zip 이 붙어 있을 수 있다)
const NW_RUNTIME = /(^|\/)(nw\.dll|nw_elf\.dll|node\.dll|nw\.pak|nw_100_percent\.pak|ffmpegsumo\.dll|libnw\.so|libnode\.so)$/i;

/** 포장 후보: [{ type: "asar"|"nw"|"exe", entry }] (우선순위 순) */
function findPackages(entries) {
  const out = [];
  for (const e of entries) if (/(^|\/)app\.asar$/i.test(e.path)) out.push({ type: "asar", entry: e });
  for (const e of entries) if (/(^|\/)(package|app)\.nw$/i.test(e.path)) out.push({ type: "nw", entry: e });
  const nwDirs = new Set(entries.filter((e) => NW_RUNTIME.test(e.path)).map((e) => dirname(e.path)));
  for (const e of entries) {
    const d = dirname(e.path);
    // 윈도: 게임.exe / 리눅스: 확장자 없는 실행 파일(nw 런타임과 같은 폴더)
    if (nwDirs.has(d) && e.size > 64 << 10 && !NW_HELPER.test(e.path) && (/\.exe$/i.test(e.path) || !/\.[^/]*$/.test(basename(e.path)))) {
      out.push({ type: "exe", entry: e });
    }
  }
  return out.sort((a, b) => depth(a.entry.path) - depth(b.entry.path));
}

const PACKAGE_LABEL = { asar: "Electron · app.asar", nw: "NW.js · package.nw/app.nw", exe: "NW.js · 실행 파일에 묶인 zip" };

/** 항목의 마지막 n 바이트(스트림이면 끝까지 흘려 보내며 끝부분만 남긴다 — 통째로 메모리에 올리지 않음) */
async function tailBytes(entry, n) {
  const body = await entry.open();
  if (body instanceof Blob) return new Uint8Array(await body.slice(Math.max(0, body.size - n)).arrayBuffer());
  const reader = body.getReader();
  let buf = new Uint8Array(0);
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const joined = new Uint8Array(Math.min(n, buf.length + value.length));
    const fromValue = Math.min(value.length, joined.length);
    joined.set(buf.subarray(buf.length - (joined.length - fromValue)), 0);
    joined.set(value.subarray(value.length - fromValue), joined.length - fromValue);
    buf = joined;
  }
  return buf;
}

/** 끝부분에 zip 의 끝 표시(EOCD "PK\x05\x06")가 있는가 */
function hasZipEnd(tail) {
  for (let i = tail.length - 22; i >= 0; i--) {
    if (tail[i] === 0x50 && tail[i + 1] === 0x4b && tail[i + 2] === 0x05 && tail[i + 3] === 0x06) return true;
  }
  return false;
}

// NW.js·크롬 런타임의 보조 실행 파일(게임 zip 이 붙어 있지 않다)
const NW_HELPER = /(^|\/)(notification_helper|nacl64|nacl_helper\w*|nwjc|chrome_crashpad_handler|crashpad_handler|chromedriver|minidump_stackwalk|payload)(\.exe)?$/i;

/**
 * 포장 꺼내기.
 * @returns {Promise<Blob|null>} 포장 파일 내용. exe 끝에 zip 이 없으면 null(후보 아님).
 * 바깥 zip 에서 이 항목을 못 꺼내면(지원하지 않는 압축·암호·용량) 그 이유를 알리는 ImportError.
 */
async function packageBlob(c) {
  try {
    if (c.type === "exe" && !hasZipEnd(await tailBytes(c.entry, 22 + 0xffff + 20))) return null;
    return await readBlob(c.entry);
  } catch (e) {
    throw new ImportError("PACKAGE", `${basename(c.entry.path)} 을(를) 압축 파일에서 꺼내지 못했습니다.\n${e.message || e}\n\n` +
      "게임 폴더를 일반 zip(Deflate) 또는 '압축 안 함(저장)' 으로 다시 압축하거나, 이 파일만 따로 골라 넣어 보세요.");
  }
}

async function openPackage(c, entries, blob) {
  if (c.type === "asar") {
    const up = c.entry.path + ".unpacked/";
    const unpacked = entries.filter((e) => e.path.startsWith(up)).map((e) => ({ ...e, path: e.path.slice(up.length) }));
    return entriesFromAsar(blob, unpacked);
  }
  const list = await readZip(blob);
  return list.filter((e) => !e.dir).map((e) => ({ path: e.path, size: e.size, open: e.open }));
}

/** Enigma Virtual Box 로 묶은 exe("앞 5KB 안에 .enigma 섹션") — 안의 파일을 꺼낼 수 없다 */
async function enigmaExe(entries) {
  const exes = entries.filter((e) => /\.exe$/i.test(e.path) && e.size > 1 << 20).sort((a, b) => b.size - a.size).slice(0, 3);
  for (const e of exes) {
    try {
      const head = await readHead(e, 5120);
      if (new TextDecoder("latin1").decode(head).includes(".enigma")) return e.path;
    } catch { /* 무시 */ }
  }
  return null;
}

/** NW.js package.json 의 main 이 html 이면 그것이 시작 페이지 ("app://./index.html" 같은 형식 포함) */
async function nwMainHtml(entries) {
  const pkgs = entries.filter((e) => /(^|\/)package\.json$/i.test(e.path) && !/(^|\/)node_modules\//i.test(e.path))
    .sort((a, b) => depth(a.path) - depth(b.path));
  for (const pkg of pkgs.slice(0, 3)) {
    let main = "";
    try { main = String(JSON.parse(await readText(pkg, 1 << 20)).main || ""); } catch { continue; }
    main = main.replace(/^[a-z][\w+.-]*:\/\/[^/]*\//i, "").replace(/^\.?\//, "").split(/[?#]/)[0];
    if (!/\.html?$/i.test(main)) continue;
    const dir = dirname(pkg.path);
    const path = dir ? `${dir}/${main}` : main;
    const hit = entries.find((e) => e.path === path) || entries.find((e) => e.path.toLowerCase() === path.toLowerCase());
    if (hit) return { root: dir, entry: relTo(dir, hit.path), html: hit };
  }
  return null;
}

const COVER_SKIP = /(unity-logo|webgl-logo|progress|fullscreen|memoryprofiler|webmemd|favicon)/i;
const COVER_RANK = [/(cover|capsule|thumb|thumbnail|banner|key.?art|title)/i, /(icon)/i, /(logo|splash)/i];

function findCover(entries, root) {
  const imgs = entries.filter((e) =>
    under(root, e.path) && /\.(png|jpe?g|webp)$/i.test(e.path) && e.size > 1024 && e.size < 3 << 20 &&
    !COVER_SKIP.test(basename(e.path)) && depth(relTo(root, e.path)) <= 2);
  for (const re of COVER_RANK) {
    const hit = imgs.filter((e) => re.test(basename(e.path))).sort((a, b) => depth(a.path) - depth(b.path))[0];
    if (hit) return hit;
  }
  return null;
}

/** 모던(2020+) 빌드 파일 이름 찾기: <name>.data(.gz|.br|.unityweb) 등 */
function modernParts(entries, loader) {
  const dir = dirname(loader.path);
  const name = basename(loader.path).replace(/\.loader\.js$/i, "");
  const inDir = entries.filter((e) => dirname(e.path) === dir).map((e) => basename(e.path));
  const pick = (re) => inDir.find((n) => re.test(n));
  const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const sfx = "(\\.(gz|br|unityweb))?$";
  return {
    dir, name,
    data: pick(new RegExp(`^${esc}\\.data${sfx}`, "i")),
    framework: pick(new RegExp(`^${esc}\\.framework\\.js${sfx}`, "i")),
    code: pick(new RegExp(`^${esc}\\.wasm${sfx}`, "i")),
    symbols: pick(new RegExp(`^${esc}\\.symbols\\.json${sfx}`, "i")),
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

const GEN_STYLE =
  "html,body{margin:0;height:100%;background:#000;overflow:hidden}" +
  "canvas{display:block;outline:none}" +
  "#up-msg{position:fixed;left:0;right:0;bottom:14px;text-align:center;color:#bbb;font:14px system-ui,sans-serif;pointer-events:none}";

function generateModernHtml(title, buildRel, loaderName, parts, meta) {
  const cfg = {
    dataUrl: parts.data, frameworkUrl: parts.framework, codeUrl: parts.code,
    ...(parts.symbols ? { symbolsUrl: parts.symbols } : {}),
  };
  return `<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>${escapeHtml(title)}</title>
<style>${GEN_STYLE}#unity-canvas{position:fixed;inset:0;width:100%;height:100%}</style>
</head><body>
<canvas id="unity-canvas" width="960" height="600" tabindex="-1"></canvas>
<div id="up-msg">불러오는 중… 0%</div>
<script>
(function () {
  var buildUrl = ${JSON.stringify(buildRel)};
  function u(f) { return buildUrl ? buildUrl + "/" + f : f; }
  var files = ${JSON.stringify(cfg)};
  var config = { streamingAssetsUrl: "StreamingAssets", companyName: ${JSON.stringify(meta.company || "UniPlay")},
    productName: ${JSON.stringify(title)}, productVersion: ${JSON.stringify(meta.version || "1.0")},
    showBanner: function (m, t) { if (t === "error") document.getElementById("up-msg").textContent = "오류: " + m; } };
  for (var k in files) config[k] = u(files[k]);
  var msg = document.getElementById("up-msg");
  var s = document.createElement("script");
  s.src = u(${JSON.stringify(loaderName)});
  s.onload = function () {
    createUnityInstance(document.getElementById("unity-canvas"), config, function (p) {
      msg.textContent = "불러오는 중… " + Math.round(p * 100) + "%";
    }).then(function (inst) { window.unityInstance = inst; msg.remove(); })
      .catch(function (e) { msg.textContent = "오류: " + e; });
  };
  document.body.appendChild(s);
})();
</script>
</body></html>`;
}

function generateLegacyHtml(title, loaderRel, jsonRel) {
  return `<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>${escapeHtml(title)}</title>
<style>${GEN_STYLE}#unityContainer{position:fixed;inset:0;width:100%;height:100%}</style>
<script src="${escapeHtml(loaderRel)}"></script>
</head><body>
<div id="unityContainer" style="width:960px;height:600px"></div>
<div id="up-msg">불러오는 중…</div>
<script>
var unityInstance = UnityLoader.instantiate("unityContainer", ${JSON.stringify(jsonRel)}, {
  onProgress: function (inst, p) {
    var m = document.getElementById("up-msg");
    if (m) { m.textContent = "불러오는 중… " + Math.round(p * 100) + "%"; if (p >= 1) m.remove(); }
  }
});
</script>
</body></html>`;
}

/**
 * 항목 목록을 보고 설치 계획을 세운다.
 * @returns {Promise<{kind,kindLabel,root,entry,generatedHtml,title,company,version,files,decompress:Set<string>,cover,warnings:string[],totalSize}>}
 */
export async function analyze(allEntries, sourceName = "", ctx = {}) {
  const nested = ctx.nested || 0; // PC판 포장 안을 판별 중이면 1 이상
  const entries = allEntries.filter((e) => !JUNK.test(e.path) && e.path);
  if (!entries.length) throw new ImportError("EMPTY", "비어 있는 압축 파일/폴더입니다.");
  const missingUnpacked = allEntries.missingUnpacked || [];
  const truncated = allEntries.truncated || [];

  const htmls = entries
    .filter((e) => /\.html?$/i.test(e.path))
    .sort((a, b) => depth(a.path) - depth(b.path) || (/index\.html?$/i.test(b.path) - /index\.html?$/i.test(a.path)));
  const modernLoaders = entries.filter((e) => /\.loader\.js$/i.test(e.path));
  const legacyLoaders = entries.filter((e) => /(^|\/)UnityLoader(\.min)?\.js$/i.test(e.path));
  const has = (p) => entries.some((e) => e.path === p);
  const warnings = [];

  let plan = null;

  // 1~2) 유니티 loader 를 참조하는 html 찾기
  for (const h of htmls.slice(0, 40)) {
    const dir = dirname(h.path);
    const text = await readText(h);
    if (!text) continue;
    const modern = modernLoaders.find((l) => under(dir, l.path) && text.includes(basename(l.path)));
    if (modern || (/createUnityInstance/.test(text) && modernLoaders.some((l) => under(dir, l.path)))) {
      const loader = modern || modernLoaders.find((l) => under(dir, l.path));
      plan = { kind: "unity", kindLabel: "Unity 2020+", root: dir, entry: relTo(dir, h.path), loader,
        title: cleanTitle(configValue(text, "productName")) || htmlTitle(text),
        company: configValue(text, "companyName"), version: configValue(text, "productVersion") };
      break;
    }
    if (/UnityLoader\.instantiate/.test(text) && legacyLoaders.some((l) => under(dir, l.path))) {
      const loader = legacyLoaders.find((l) => under(dir, l.path));
      plan = { kind: "unity-legacy", kindLabel: "Unity 5.6~2019", root: dir, entry: relTo(dir, h.path), loader,
        title: htmlTitle(text) };
      break;
    }
  }

  // 3) html 없이 Build 폴더만 → 실행용 html 생성
  if (!plan && modernLoaders.length) {
    const loader = modernLoaders.sort((a, b) => depth(a.path) - depth(b.path))[0];
    const parts = modernParts(entries, loader);
    if (!parts.data || !parts.framework || !parts.code) {
      throw new ImportError("INCOMPLETE", `Build 폴더가 불완전합니다 (${parts.name}.data / .framework.js / .wasm 중 일부가 없음).`);
    }
    const loaderDir = parts.dir;
    const root = /(^|\/)Build$/i.test(loaderDir) ? dirname(loaderDir) : loaderDir;
    const title = baseName(sourceName) || parts.name;
    plan = { kind: "unity", kindLabel: "Unity 2020+", root, entry: "index.html", loader, title,
      generatedHtml: generateModernHtml(title, relDir(root, loaderDir), basename(loader.path), parts, {}) };
    warnings.push("index.html 이 없어 실행용 페이지를 자동으로 만들었습니다.");
  }
  if (!plan && legacyLoaders.length) {
    const loader = legacyLoaders[0];
    const loaderDir = dirname(loader.path);
    const json = entries.find((e) => dirname(e.path) === loaderDir && /\.json$/i.test(e.path) && !/symbols|asm\./i.test(e.path));
    if (!json) throw new ImportError("INCOMPLETE", "UnityLoader.js 는 있지만 빌드 설정(.json) 파일이 없습니다.");
    const root = /(^|\/)Build$/i.test(loaderDir) ? dirname(loaderDir) : loaderDir;
    const title = baseName(sourceName) || basename(json.path).replace(/\.json$/i, "");
    plan = { kind: "unity-legacy", kindLabel: "Unity 5.6~2019", root, entry: "index.html", loader, title,
      generatedHtml: generateLegacyHtml(title, relDir(root, loader.path), relDir(root, json.path)) };
    warnings.push("index.html 이 없어 실행용 페이지를 자동으로 만들었습니다.");
  }

  // 4) RPG Maker MV/MZ · 티라노스크립트
  if (!plan) {
    for (const h of htmls) {
      const dir = dirname(h.path);
      if (!/index\.html?$/i.test(h.path)) continue;
      const j = (p) => (dir ? dir + "/" + p : p);
      const tjs = entries.find((e) => e.path === j("data/system/Config.tjs"));
      if (tjs && (has(j("tyrano/tyrano.js")) || has(j("tyrano/libs.js")) || has(j("tyrano/tyrano.base.js")))) {
        const text = await readTextGuess(tjs, 1 << 20);
        const cfg = tyranoConfig(text);
        const ver = await tyranoVersion(entries, dir);
        plan = { kind: "tyrano", kindLabel: ver ? `TyranoScript ${ver}` : "TyranoScript", root: dir, entry: relTo(dir, h.path),
          title: cfg["System.title"] || "", version: cfg.game_version && cfg.game_version !== "0.0" ? cfg.game_version : "",
          overrides: new Map(), seedStorage: {}, autoSettings: {} };
        // 세로 화면 게임(스마트폰용 720x1280 등)은 세로로 고정
        if (+cfg.scHeight > +cfg.scWidth) plan.autoSettings.orientation = "portrait";
        const patched = patchTyranoConfig(text, cfg, await tyranoEngineSupport(entries, dir));
        if (patched.text !== text) plan.overrides.set(relTo(dir, tjs.path), patched.text);
        warnings.push(...patched.notes, ...(await tyranoCompat(entries, dir)));
        // projectID 줄이 없으면 엔진 기본값 tyranoproject 로 저장된다(kag.js)
        plan.seedStorage = await tyranoPcSaves(ctx.outer || entries, cfg.projectID ?? "tyranoproject");
        const n = Object.keys(plan.seedStorage).length;
        if (n) warnings.push(`PC판 세이브 파일 ${n}개를 찾았습니다. 설치하면 이어서 플레이할 수 있어요(세이브 목록의 썸네일 그림은 빠집니다).`);
        break;
      }
      if (has(j("js/rpg_core.js")) || has(j("js/rmmz_core.js"))) {
        const mz = has(j("js/rmmz_core.js"));
        let title = "";
        const sys = entries.find((e) => e.path === j("data/System.json"));
        if (sys) { try { title = JSON.parse(await readText(sys)).gameTitle || ""; } catch { /* 암호화/손상 */ } }
        plan = { kind: mz ? "rpgmz" : "rpgmv", kindLabel: mz ? "RPG Maker MZ" : "RPG Maker MV", root: dir,
          entry: relTo(dir, h.path), title: title || htmlTitle(await readText(h)) };
        break;
      }
    }
  }
  // PC 유니티 빌드(UnityPlayer.dll 이나 _Data/.app 의 globalgamemanagers 등)면 안의 html(크레딧·매뉴얼·내장 브라우저 화면)은
  // 게임이 아니다 → 아래 7) 에서 변환 진단을 보여 준다. nw.js 같은 HTML5 게임의 .exe 는 이 표시가 없어 영향 없음.
  const pcUnity = entries.some((e) => /(^|\/)UnityPlayer\.(dll|so)$/i.test(e.path) ||
    /(_Data|\.app\/Contents\/Resources\/Data)\/(globalgamemanagers|mainData|data\.unity3d)$/i.test(e.path));

  // 5) PC판 HTML5 포장(NW.js · Electron) 안의 게임 꺼내기
  let brokenAsar = null;
  if (!plan && !pcUnity && nested < 2) {
    for (const c of findPackages(entries)) {
      const blob = await packageBlob(c); // 바깥 zip 에서 못 꺼내면 이유와 함께 멈춘다
      if (!blob) continue; // 끝에 zip 이 안 붙은 exe
      let inner;
      try { inner = await openPackage(c, entries, blob); } catch { // asar·zip 형식이 아님
        if (c.type === "asar") brokenAsar = c.entry.path;
        continue;
      }
      if (!inner.length) continue;
      let p;
      try { p = await analyze(inner, sourceName, { nested: nested + 1, outer: ctx.outer || entries }); } catch { continue; }
      p.warnings.unshift(`PC판(${PACKAGE_LABEL[c.type]}) 안에서 게임 파일을 꺼내 설치합니다.`);
      // 아는 엔진(유니티·RPG Maker·티라노)은 브라우저 모드가 있지만, 그 밖의 게임은 PC 전용 기능을 쓸 수 있다
      if (p.kind === "html5") p.warnings.push("PC판 전용 기능(Node.js 파일 접근 등)을 쓰는 부분은 브라우저에서 동작하지 않을 수 있어요.");
      return p;
    }
  }

  // 6) 그 밖의 HTML5 — NW.js package.json 의 main, 없으면 가장 얕은 index.html
  if (!plan && !pcUnity) {
    const main = await nwMainHtml(entries);
    const h = main ? main.html : htmls.find((e) => /index\.html?$/i.test(e.path));
    if (h) {
      const text = await readText(h);
      plan = { kind: "html5", kindLabel: "HTML5", root: main ? main.root : dirname(h.path), entry: main ? main.entry : basename(h.path), title: htmlTitle(text) };
      warnings.push("유니티 빌드가 아닌 일반 HTML5 게임으로 보입니다. 실행은 시도하지만 동작은 보장하지 않아요.");
    }
  }

  // 7) 실행할 게 없음 → 어떤 플랫폼인지 알려 주기
  if (!plan && brokenAsar) {
    throw new ImportError("PACKAGE", BROKEN_ASAR(brokenAsar));
  }
  if (!plan && !pcUnity && nested === 0) {
    const enigma = await enigmaExe(entries);
    if (enigma) {
      throw new ImportError("WINDOWS", `${basename(enigma)} 는 Enigma Virtual Box 로 게임 파일을 실행 파일 안에 숨겨 묶은 형식이라 꺼낼 수 없습니다.\n\n` +
        "PC 에서 evbunpack 같은 도구로 먼저 풀어 낸 폴더를 zip 으로 넣어 주세요. (안의 게임이 티라노스크립트·RPG Maker MV/MZ 같은 HTML5 게임이면 실행됩니다)");
    }
  }
  if (!plan) {
    const err = platformError(entries.map((e) => e.path));
    // PC 빌드면 "모바일로 바꿀 수 있는지" 진단을 붙여 보낸다
    if (["WINDOWS", "MAC", "LINUX"].includes(err.code) && !nested) err.report = await inspectPcBuild(entries).catch(() => null);
    throw err;
  }

  const root = plan.root;
  const inRoot = entries.filter((e) => under(root, e.path));
  if (!plan.generatedHtml && entries.some((e) => /(^|\/)UnityPlayer\.dll$/i.test(e.path))) {
    warnings.push("Windows 빌드 파일도 함께 들어 있어 WebGL 빌드만 가져옵니다.");
  }

  // 미리 풀어 둘 압축 빌드 파일(.gz/.br) — loader 와 같은 폴더만
  const decompress = new Set();
  if (plan.kind === "unity" && plan.loader) {
    const ldir = dirname(plan.loader.path);
    for (const e of inRoot) {
      if (dirname(e.path) === ldir && /\.(gz|br)$/i.test(e.path)) decompress.add(relTo(root, e.path));
    }
    const parts = modernParts(entries, plan.loader);
    if (!parts.data || !parts.framework || !parts.code) {
      warnings.push("Build 폴더에서 .data/.framework.js/.wasm 중 일부를 찾지 못했습니다. 템플릿이 다른 이름을 쓰면 괜찮아요.");
    }
  }

  // 레거시 빌드는 json 에 제품명이 있다
  if (plan.kind === "unity-legacy" && plan.loader) {
    const json = entries.find((e) => dirname(e.path) === dirname(plan.loader.path) && /\.json$/i.test(e.path));
    if (json) {
      try {
        const j = JSON.parse(await readText(json));
        plan.title = cleanTitle(j.productName) || plan.title;
        plan.company = j.companyName || "";
        plan.version = j.productVersion || "";
      } catch { /* 무시 */ }
    }
  }

  if (missingUnpacked.length) {
    warnings.push(`app.asar 밖(app.asar.unpacked 폴더)에 있어야 할 파일 ${missingUnpacked.length}개가 없습니다` +
      ` (${missingUnpacked.slice(0, 3).join(", ")}${missingUnpacked.length > 3 ? " …" : ""}). 게임 폴더 전체를 zip 으로 넣어 주세요.`);
  }
  if (truncated.length) {
    warnings.push(`app.asar 가 중간에 잘려 있어(덜 받았거나 복사 중 끊김) 파일 ${truncated.length}개가 빠졌습니다. 원본을 다시 받아 넣어 주세요.`);
  }
  plan.title = plan.title || baseName(sourceName) || "이름 없는 게임";
  plan.files = inRoot.map((e) => ({ rel: relTo(root, e.path), entry: e }));
  if (plan.generatedHtml) plan.files = plan.files.filter((f) => f.rel !== plan.entry);
  plan.decompress = decompress;
  plan.overrides = plan.overrides || new Map();
  plan.seedStorage = plan.seedStorage || {};
  plan.cover = findCover(entries, root);
  plan.warnings = warnings;
  plan.totalSize = plan.files.reduce((s, f) => s + (f.entry.size || 0), 0);
  plan.sourceName = sourceName;
  return plan;
}

/* ───────────── 설치 ───────────── */

async function decompressBuildFile(blob, rel) {
  if (/\.gz$/i.test(rel)) {
    const head = new Uint8Array(await blob.slice(0, 2).arrayBuffer());
    if (head[0] !== 0x1f || head[1] !== 0x8b) return blob; // 이름만 .gz
    return new Response(blob.stream().pipeThrough(new DecompressionStream("gzip"))).blob();
  }
  if (/\.br$/i.test(rel)) {
    try { // 브라우저가 brotli 를 지원하면 스트림으로
      const ds = new DecompressionStream("brotli");
      return await new Response(blob.stream().pipeThrough(ds)).blob();
    } catch { /* 미지원 → JS 디코더 */ }
    try {
      const { BrotliDecode } = await import("../vendor/brotli-decode.js");
      const out = BrotliDecode(new Int8Array(await blob.arrayBuffer()));
      return new Blob([out]);
    } catch (e) {
      console.warn("[uniplay] brotli 해제 실패, 원본 유지:", rel, e);
      return blob;
    }
  }
  return blob;
}

/**
 * PC판에서 가져온 세이브를 이 게임의 localStorage 에 넣는다(inject.js 의 게임별 분리 규칙과 같은 키).
 * 분리를 끈 경우 같은 키(projectID 가 같은 다른 게임)의 세이브는 덮어쓰지 않는다.
 * @returns {Promise<{written:number, failed:string[], message:string}>}
 */
async function seedLocalStorage(id, data) {
  const keys = Object.keys(data || {});
  const out = { written: 0, failed: [], message: "" };
  if (!keys.length) return out;
  const isolate = (await globalDefaults()).isolateStorage !== false;
  let full = false;
  for (const k of keys) {
    const key = isolate ? `uniplay:${id}:${k}` : k;
    if (!isolate && localStorage.getItem(key) !== null) { out.failed.push(k); continue; }
    try { localStorage.setItem(key, data[k]); out.written++; } catch (e) {
      console.warn("[uniplay] 세이브를 넣지 못했습니다:", k, e);
      out.failed.push(k);
      full = true;
    }
  }
  if (out.failed.length) {
    out.message = full
      ? `PC판 세이브 ${out.failed.length}개는 브라우저 저장 공간(모든 게임이 함께 쓰는 약 5MB)이 부족해 넣지 못했습니다: ${out.failed.join(", ")}. 안 하는 게임의 세이브를 지운 뒤 세이브 메뉴의 '백업 파일에서 복원'으로 .sav 를 넣어 주세요.`
      : `PC판 세이브 ${out.failed.length}개는 같은 이름의 세이브가 이미 있어 넣지 않았습니다(게임별 저장소 분리가 꺼져 있음): ${out.failed.join(", ")}.`;
  }
  return out;
}

function isQuota(e) {
  return e && (e.name === "QuotaExceededError" || /quota/i.test(e.message || ""));
}

/**
 * 계획대로 게임을 설치한다.
 * @param {object} plan analyze() 결과
 * @param {{onProgress?:(done:number,total:number,file:string)=>void, signal?:AbortSignal, settings?:object}} opt
 */
export async function install(plan, opt = {}) {
  const { onProgress = () => {}, signal } = opt;
  const id = newId();
  const cacheName = gameCacheName(id);
  const cache = await caches.open(cacheName);
  const total = plan.totalSize || 1;
  let done = 0;
  const report = (file) => onProgress(Math.min(done, total), total, file);
  const stored = [];

  async function storeOne(f) {
    if (signal?.aborted) throw new DOMException("취소됨", "AbortError");
    const url = gameFileURL(id, f.rel);
    const headers = { "Content-Type": mimeFor(f.rel), "X-UniPlay-Path": encodeURIComponent(f.rel) };
    let body = plan.overrides?.has(f.rel) ? new Blob([plan.overrides.get(f.rel)]) : await f.entry.open();
    let size = body instanceof Blob ? body.size : f.entry.size;
    if (plan.decompress.has(f.rel)) {
      const blob = body instanceof Blob ? body : await new Response(body).blob();
      body = await decompressBuildFile(blob, f.rel);
      size = body.size;
    }
    if (body instanceof Blob) {
      await cache.put(url, new Response(body, { headers }));
      done += f.entry.size;
    } else {
      let counted = 0;
      const counter = new TransformStream({
        transform(chunk, ctl) {
          counted += chunk.byteLength;
          done += chunk.byteLength;
          report(f.rel);
          ctl.enqueue(chunk);
        },
      });
      try {
        await cache.put(url, new Response(body.pipeThrough(counter), { headers }));
      } catch (e) {
        if (isQuota(e) || e.name === "AbortError") throw e;
        // 일부 브라우저는 스트림 본문을 캐시에 못 넣는다 → Blob 으로 한 번 더
        done -= counted;
        const again = await f.entry.open();
        await cache.put(url, new Response(again instanceof Blob ? again : await new Response(again).blob(), { headers }));
        done += f.entry.size;
      }
      size = counted || size;
      done += Math.max(0, f.entry.size - counted); // 압축 해제 크기와 목록 크기가 다를 때 보정
    }
    stored.push([f.rel, size]);
    report(f.rel);
  }

  try {
    const queue = plan.files.slice().sort((a, b) => a.entry.size - b.entry.size);
    const worker = async () => { while (queue.length) await storeOne(queue.shift()); };
    await Promise.all([worker(), worker(), worker()]);
    if (plan.generatedHtml) {
      const blob = new Blob([plan.generatedHtml], { type: "text/html" });
      await cache.put(gameFileURL(id, plan.entry), new Response(blob, { headers: { "Content-Type": "text/html; charset=utf-8" } }));
      stored.push([plan.entry, blob.size]);
    }
    let cover = null;
    if (plan.cover) { try { cover = await readBlob(plan.cover); } catch { /* 표지는 없어도 됨 */ } }
    const game = {
      id,
      title: plan.title,
      company: plan.company || "",
      version: plan.version || "",
      kind: plan.kind,
      kindLabel: plan.kindLabel,
      entry: plan.entry,
      generated: !!plan.generatedHtml,
      size: stored.reduce((s, [, n]) => s + n, 0),
      fileCount: stored.length,
      cover,
      coverAuto: true,
      addedAt: Date.now(),
      lastPlayed: 0,
      playSeconds: 0,
      settings: opt.settings || {},
      autoSettings: plan.autoSettings || {},
      idbfsPrefix: null,
      sourceName: plan.sourceName || "",
      warnings: plan.warnings || [],
    };
    stored.sort((a, b) => a[0].localeCompare(b[0]));
    await fileStore.put(id, stored);
    const seeded = await seedLocalStorage(id, plan.seedStorage);
    if (seeded.failed.length) game.warnings.push(seeded.message);
    await games.put(game);
    game.installNotes = seeded.failed.length ? [seeded.message] : [];
    return game;
  } catch (e) {
    await caches.delete(cacheName).catch(() => {});
    if (isQuota(e)) throw new ImportError("QUOTA", "저장 공간이 부족합니다. 다른 게임을 지우거나 기기 저장 공간을 확보해 주세요.");
    throw e;
  }
}
