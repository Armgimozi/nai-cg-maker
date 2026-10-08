/* 게임 가져오기: zip/폴더 → 빌드 판별 → Cache Storage 에 설치.
 *
 * 판별 순서
 *   1) 유니티 2020+  : *.loader.js 를 참조하는 html (createUnityInstance)
 *   2) 유니티 5.6~2019: UnityLoader.js + UnityLoader.instantiate
 *   3) html 없이 Build 폴더만 있으면 실행용 index.html 을 만들어 준다
 *   4) RPG Maker MV/MZ, 그 밖의 HTML5 게임(index.html) 도 실행은 시도한다
 *   5) 위가 전부 아니면 Windows/맥/안드로이드 빌드인지 알려 준다
 *
 * Build 폴더의 .gz/.br 파일은 여기서 미리 풀어 둔다. 원래는 웹서버가
 * "Content-Encoding" 헤더를 붙여 줘야 하는데, 서비스워커가 만든 응답에는
 * 그 헤더가 효과가 없기 때문(브라우저가 풀어 주지 않음).
 */

import { readZip } from "./zip.js";
import { gameCacheName, gameFileURL, newId, games, files as fileStore } from "./db.js";

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
  if (has(/(^|\/)Assets\/.+\.(unity|cs)$/i) && has(/(^|\/)ProjectSettings\//i)) {
    return new ImportError("PROJECT", "유니티 프로젝트 원본입니다. Unity 에디터에서 File → Build Settings → WebGL 로 빌드한 결과물을 넣어 주세요.");
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
export async function analyze(allEntries, sourceName = "") {
  const entries = allEntries.filter((e) => !JUNK.test(e.path) && e.path);
  if (!entries.length) throw new ImportError("EMPTY", "비어 있는 압축 파일/폴더입니다.");

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

  // 4) RPG Maker MV/MZ · 기타 HTML5
  if (!plan) {
    for (const h of htmls) {
      const dir = dirname(h.path);
      if (!/index\.html?$/i.test(h.path)) continue;
      const j = (p) => (dir ? dir + "/" + p : p);
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
  if (!plan) {
    const h = htmls.find((e) => /index\.html?$/i.test(e.path));
    if (h) {
      const text = await readText(h);
      plan = { kind: "html5", kindLabel: "HTML5", root: dirname(h.path), entry: basename(h.path), title: htmlTitle(text) };
      warnings.push("유니티 빌드가 아닌 일반 HTML5 게임으로 보입니다. 실행은 시도하지만 동작은 보장하지 않아요.");
    }
  }

  // 5) 실행할 게 없음 → 어떤 플랫폼인지 알려 주기
  if (!plan) throw platformError(entries.map((e) => e.path));

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

  plan.title = plan.title || baseName(sourceName) || "이름 없는 게임";
  plan.files = inRoot.map((e) => ({ rel: relTo(root, e.path), entry: e }));
  if (plan.generatedHtml) plan.files = plan.files.filter((f) => f.rel !== plan.entry);
  plan.decompress = decompress;
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
    let body = await f.entry.open();
    let size = f.entry.size;
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
      idbfsPrefix: null,
      sourceName: plan.sourceName || "",
      warnings: plan.warnings || [],
    };
    stored.sort((a, b) => a[0].localeCompare(b[0]));
    await fileStore.put(id, stored);
    await games.put(game);
    return game;
  } catch (e) {
    await caches.delete(cacheName).catch(() => {});
    if (isQuota(e)) throw new ImportError("QUOTA", "저장 공간이 부족합니다. 다른 게임을 지우거나 기기 저장 공간을 확보해 주세요.");
    throw e;
  }
}
