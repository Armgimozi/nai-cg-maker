/* 라이브러리 화면: 게임 목록 · 가져오기 · 게임별 설정 · 세이브 백업 · 전역 설정 · 도움말. */

import {
  games, files as fileStore, kv, deleteGame, globalDefaults, effectiveSettings, formatBytes,
} from "./db.js";
import { entriesFromFile, entriesFromFiles, analyze, install, ImportError } from "./importer.js";
import { saveSummary, exportSave, importSave, importTyranoSav, deleteSave, idbfsGroups } from "./saves.js";
import { PRESETS, autoPreset } from "./keys.js";
import { showPortingReport } from "./porting.js";
import { h, toast, dialog, confirmBox, promptBox, sheet, downloadBlob, timeAgo, formatDuration } from "./ui.js";

const $ = (s) => document.querySelector(s);
const grid = $("#grid");
const coverURLs = [];

/* ───────────── 서비스워커 · 설치 ───────────── */

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js", { scope: "./" }).catch((e) => console.warn("SW 등록 실패", e));
} else {
  toast("이 브라우저는 서비스워커를 지원하지 않아 게임을 실행할 수 없습니다.", 8000);
}

let installEvent = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  installEvent = e;
  $("#install-btn").hidden = false;
});
$("#install-btn").addEventListener("click", async () => {
  if (!installEvent) return;
  installEvent.prompt();
  await installEvent.userChoice.catch(() => {});
  installEvent = null;
  $("#install-btn").hidden = true;
});

/* ───────────── 목록 ───────────── */

function hue(s) {
  let x = 0;
  for (const ch of s) x = (x * 31 + ch.codePointAt(0)) >>> 0;
  return x % 360;
}

function coverEl(g) {
  if (g.cover instanceof Blob) {
    const url = URL.createObjectURL(g.cover);
    coverURLs.push(url);
    return h("img", { class: "cover", src: url, alt: "", loading: "lazy" });
  }
  const c = hue(g.title || g.id);
  return h("div", { class: "cover placeholder", style: { background: `linear-gradient(135deg, hsl(${c} 55% 32%), hsl(${(c + 50) % 360} 60% 18%))` } },
    h("span", {}, Array.from((g.title || "?").trim())[0] || "?"));
}

function playURL(g) {
  const iso = g.settings?.isolate ? "&iso=1" : "";
  return `play.html?id=${encodeURIComponent(g.id)}&from=lib${iso}`;
}

async function render() {
  coverURLs.splice(0).forEach((u) => URL.revokeObjectURL(u));
  const list = (await games.all()).sort((a, b) => (b.lastPlayed || 0) - (a.lastPlayed || 0) || b.addedAt - a.addedAt);
  grid.textContent = "";
  $("#empty").hidden = list.length > 0;
  for (const g of list) {
    const card = h("article", { class: "card" },
      h("a", { class: "card-main", href: playURL(g), "aria-label": `${g.title} 플레이` },
        coverEl(g),
        h("div", { class: "card-info" },
          h("h3", {}, g.title),
          h("p", {}, [g.kindLabel, formatBytes(g.size)].filter(Boolean).join(" · ")),
          h("p", { class: "dim" }, g.lastPlayed ? `${timeAgo(g.lastPlayed)} 플레이` : "새로 추가됨"))),
      h("button", { class: "card-more icon-btn", "aria-label": `${g.title} 관리`, onclick: () => openGame(g.id) }, "⋯"));
    grid.appendChild(card);
  }
  updateStorage();
}

async function updateStorage() {
  if (!navigator.storage?.estimate) return;
  const { usage = 0, quota = 0 } = await navigator.storage.estimate();
  if (!quota) return;
  const el = $("#storage");
  el.hidden = false;
  el.querySelector("i").style.width = `${Math.min(100, (usage / quota) * 100).toFixed(1)}%`;
  el.querySelector("span").textContent = `${formatBytes(usage)} 사용 / 여유 ${formatBytes(Math.max(0, quota - usage))}`;
}

window.addEventListener("pageshow", (e) => { if (e.persisted) render(); });

/* ───────────── 가져오기 ───────────── */

function openAdd() {
  const s = sheet("게임 추가", h("div", { class: "add-options" },
    h("button", { class: "opt", onclick: () => { s.close(); $("#pick-zip").click(); } },
      h("b", {}, "zip 파일"), h("span", {}, "게임 폴더를 압축한 파일 (가장 확실) · app.asar 하나도 가능")),
    h("button", { class: "opt", onclick: () => { s.close(); $("#pick-folder").click(); } },
      h("b", {}, "폴더"), h("span", {}, "압축을 푼 빌드 폴더 통째로 (지원하는 브라우저만)")),
    h("button", { class: "opt", onclick: () => { s.close(); $("#pick-files").click(); } },
      h("b", {}, "여러 파일"), h("span", {}, "index.html 과 Build 안의 파일들을 한꺼번에 선택 (폴더 구조 없어도 됨)")),
    h("p", { class: "hint" },
      "유니티 WebGL 빌드 = index.html + Build 폴더(*.loader.js, *.data, *.wasm …). ",
      ".gz/.br 로 압축된 빌드도 자동으로 풀어서 넣습니다. 티라노스크립트 게임은 PC판(.exe 폴더)도 안의 게임을 꺼내 실행해요. ",
      "유니티 PC 빌드(.exe)는 실행할 수 없지만, 넣으면 모바일 변환 가능성을 진단해 드려요.")));
}

async function importEntries(getEntries, sourceName) {
  const busy = progressDialog("파일 확인 중…");
  let plan;
  try {
    const entries = await getEntries();
    plan = await analyze(entries, sourceName);
  } catch (e) {
    busy.close();
    return showImportError(e);
  }
  busy.close();

  // 설치 전 확인
  const titleInput = h("input", { class: "field", value: plan.title });
  const est = navigator.storage?.estimate ? await navigator.storage.estimate().catch(() => null) : null;
  const free = est?.quota ? est.quota - (est.usage || 0) : Infinity;
  const ok = await dialog({
    title: "이 게임을 설치할까요?",
    body: h("div", { class: "plan" },
      row("이름", titleInput),
      h("dl", {},
        h("dt", {}, "종류"), h("dd", {}, plan.kindLabel),
        h("dt", {}, "파일"), h("dd", {}, `${plan.files.length.toLocaleString()}개 · ${formatBytes(plan.totalSize)}`),
        plan.decompress.size ? [h("dt", {}, "압축 빌드"), h("dd", {}, `${plan.decompress.size}개 파일을 미리 풀어 저장`)] : null),
      free < plan.totalSize * 1.1 ? h("p", { class: "warn" }, `저장 공간이 부족할 수 있습니다 (여유 ${formatBytes(free)}).`) : null,
      plan.warnings.map((w) => h("p", { class: "warn" }, w))),
    buttons: [{ label: "취소", value: false }, { label: "설치", value: true, kind: "primary" }],
    dismissValue: false,
  });
  if (!ok) return;
  plan.title = titleInput.value.trim() || plan.title;

  if (navigator.storage?.persist) navigator.storage.persist().catch(() => {});
  const ctrl = new AbortController();
  const prog = progressDialog("설치 중…", () => ctrl.abort());
  try {
    const game = await install(plan, {
      signal: ctrl.signal,
      onProgress: (done, total, file) => prog.update(done / total, `${formatBytes(done)} / ${formatBytes(total)}`, file),
    });
    prog.close();
    await render();
    const go = await dialog({
      title: "설치 완료",
      body: game.installNotes?.length
        ? h("div", {}, h("p", {}, `"${game.title}" 을(를) 라이브러리에 추가했습니다.`), game.installNotes.map((n) => h("p", { class: "warn" }, n)))
        : `"${game.title}" 을(를) 라이브러리에 추가했습니다.`,
      buttons: [{ label: "나중에", value: false }, { label: "지금 플레이", value: true, kind: "primary" }],
    });
    if (go) location.href = playURL(game);
  } catch (e) {
    prog.close();
    if (e.name === "AbortError") toast("설치를 취소했습니다.");
    else showImportError(e);
  }
}

function row(label, control) {
  return h("div", { class: "row" }, h("div", { class: "row-label" }, label), control);
}

function showImportError(e) {
  console.error(e);
  if (e instanceof ImportError && e.report) { showPortingReport(e.report); return; }
  const title = e instanceof ImportError ? {
    WINDOWS: "PC(Windows)용 게임이에요", MAC: "맥용 게임이에요", LINUX: "리눅스용 게임이에요", ANDROID: "안드로이드 앱이에요",
    PROJECT: "유니티 프로젝트 원본이에요", RGSS: "지원하지 않는 형식", RENPY: "지원하지 않는 형식", QUOTA: "저장 공간 부족",
    PACKAGE: "게임 꾸러미를 열 수 없어요",
  }[e.code] || "가져오지 못했습니다" : "가져오지 못했습니다";
  dialog({ title, body: h("p", { class: "dialog-body pre" }, e.message || String(e)) });
}

function progressDialog(title, onCancel) {
  const bar = h("div", { class: "progress" }, h("i"));
  const text = h("p", { class: "dim" }, "");
  const file = h("p", { class: "dim small ellipsis" }, "");
  const box = h("div", { class: "dialog" }, h("h3", {}, title), bar, text, file,
    onCancel ? h("div", { class: "dialog-actions" }, h("button", { class: "btn", onclick: onCancel }, "취소")) : null);
  const wrap = h("div", { class: "scrim" }, box);
  document.body.appendChild(wrap);
  if (!onCancel) bar.classList.add("indeterminate");
  return {
    update(frac, t, f) {
      bar.firstChild.style.width = `${Math.round(frac * 100)}%`;
      text.textContent = `${Math.round(frac * 100)}% · ${t}`;
      if (f) file.textContent = f;
    },
    close() { wrap.remove(); },
  };
}

$("#add-btn").addEventListener("click", openAdd);
$("#empty-add").addEventListener("click", () => $("#pick-zip").click());
$("#pick-zip").addEventListener("change", (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (f) importEntries(() => entriesFromFile(f), f.name);
});
for (const id of ["#pick-folder", "#pick-files"]) {
  $(id).addEventListener("change", (e) => {
    const list = Array.from(e.target.files);
    e.target.value = "";
    if (!list.length) return;
    const zip = list.length === 1 && /\.(zip|nw|asar|exe)$/i.test(list[0].name) ? list[0] : null;
    const name = zip ? zip.name : (list[0].webkitRelativePath || "").split("/")[0] || "";
    importEntries(() => (zip ? entriesFromFile(zip) : entriesFromFiles(list)), name);
  });
}

// 데스크톱: 끌어다 놓기 (zip 또는 폴더)
let dragDepth = 0;
document.addEventListener("dragenter", (e) => { if (e.dataTransfer?.types?.includes("Files")) { dragDepth++; $("#drop-hint").hidden = false; } });
document.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#drop-hint").hidden = true; } });
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", async (e) => {
  e.preventDefault();
  dragDepth = 0;
  $("#drop-hint").hidden = true;
  const items = Array.from(e.dataTransfer.items || []);
  const entry = items[0]?.webkitGetAsEntry?.();
  if (entry?.isDirectory) {
    importEntries(() => readDirEntry(entry), entry.name);
  } else if (e.dataTransfer.files[0]) {
    const f = e.dataTransfer.files[0];
    importEntries(() => entriesFromFile(f), f.name);
  }
});

async function readDirEntry(dir, prefix = "") {
  const out = [];
  const reader = dir.createReader();
  for (;;) {
    const batch = await new Promise((res, rej) => reader.readEntries(res, rej));
    if (!batch.length) break;
    for (const ent of batch) {
      const path = prefix + ent.name;
      if (ent.isDirectory) out.push(...(await readDirEntry(ent, path + "/")));
      else {
        const file = await new Promise((res, rej) => ent.file(res, rej));
        out.push({ path: `${dir.name}/${path}`.replace(/^\/+/, ""), size: file.size, open: async () => file });
      }
    }
  }
  return out;
}

/* ───────────── 게임 관리 ───────────── */

async function openGame(id) {
  const g = await games.get(id);
  if (!g) return render();
  const s = sheet(g.title, h("div", { class: "game-sheet" },
    h("div", { class: "game-head" }, coverEl(g),
      h("dl", {},
        h("dt", {}, "종류"), h("dd", {}, g.kindLabel || g.kind),
        h("dt", {}, "용량"), h("dd", {}, `${formatBytes(g.size)} · 파일 ${g.fileCount?.toLocaleString?.() ?? "-"}개`),
        h("dt", {}, "플레이"), h("dd", {}, `${formatDuration(g.playSeconds)} · ${timeAgo(g.lastPlayed)}`),
        h("dt", {}, "추가"), h("dd", {}, new Date(g.addedAt).toLocaleString("ko-KR")),
        g.company ? [h("dt", {}, "제작"), h("dd", {}, g.company)] : null)),
    h("div", { class: "action-list" },
      h("a", { class: "btn primary", href: playURL(g) }, "▶ 플레이"),
      h("button", { class: "btn", onclick: () => { s.close(); openGameSettings(g.id); } }, "⚙ 게임 설정"),
      h("button", { class: "btn", onclick: () => { s.close(); openSaves(g.id); } }, "💾 세이브 백업/복원"),
      h("button", { class: "btn", onclick: async () => {
        const name = await promptBox("이름 바꾸기", g.title);
        if (name && name.trim()) { await games.patch(g.id, { title: name.trim() }); s.close(); render(); }
      } }, "✏ 이름 바꾸기"),
      h("button", { class: "btn", onclick: () => pickCover(g.id, s) }, "🖼 표지 바꾸기"),
      h("button", { class: "btn", onclick: () => showFiles(g) }, "📄 파일 목록"),
      h("button", { class: "btn danger", onclick: async () => {
        const really = await confirmBox("게임 삭제", `"${g.title}" 을(를) 기기에서 지웁니다. 세이브는 남겨 둘까요?`, "삭제");
        if (!really) return;
        const alsoSaves = await dialog({
          title: "세이브도 지울까요?",
          body: "세이브를 남겨 두면 같은 게임을 다시 넣었을 때 백업에서 복원할 수 있습니다.",
          buttons: [{ label: "세이브는 남기기", value: false }, { label: "세이브도 삭제", value: true, kind: "danger" }],
          dismissValue: false,
        });
        if (alsoSaves) await deleteSave(g).catch(() => {});
        await deleteGame(g.id);
        s.close();
        toast("삭제했습니다.");
        render();
      } }, "🗑 삭제")),
    g.warnings?.length ? h("div", { class: "notes" }, g.warnings.map((w) => h("p", { class: "dim small" }, "ⓘ " + w))) : null));
}

function pickCover(id, s) {
  const input = $("#pick-cover");
  input.onchange = async () => {
    const f = input.files[0];
    input.value = "";
    if (!f) return;
    const blob = await shrinkImage(f, 480).catch(() => f);
    await games.patch(id, { cover: blob, coverAuto: false });
    s.close();
    render();
  };
  input.click();
}

async function shrinkImage(file, maxW) {
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, maxW / bmp.width);
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * scale);
  c.height = Math.round(bmp.height * scale);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  return new Promise((res) => c.toBlob(res, "image/jpeg", 0.88));
}

async function showFiles(g) {
  const list = await fileStore.get(g.id);
  const shown = list.slice(0, 2000);
  sheet(`파일 ${list.length.toLocaleString()}개`, h("div", {},
    g.generated ? h("p", { class: "dim small" }, `${g.entry} 는 UniPlay 가 만든 실행 페이지입니다.`) : null,
    h("table", { class: "files" },
      shown.map(([p, n]) => h("tr", {}, h("td", {}, p), h("td", { class: "num" }, formatBytes(n))))),
    list.length > shown.length ? h("p", { class: "dim" }, `… 외 ${list.length - shown.length}개`) : null), { wide: true });
}

/* ───────────── 게임별 / 전역 설정 ───────────── */

function settingsForm(values, onChange, { perGame, kind }) {
  const sel = (key, opts) => {
    const s = h("select", { class: "field", onchange: () => onChange(key, s.value) },
      opts.map(([v, l]) => h("option", { value: v, selected: String(values[key]) === String(v) }, l)));
    return s;
  };
  const sw = (key) => {
    const i = h("input", { type: "checkbox", class: "switch", onchange: () => onChange(key, i.checked) });
    i.checked = !!values[key];
    return i;
  };
  const line = (label, control, note) =>
    h("div", { class: "row" }, h("div", { class: "row-label" }, label, note ? h("small", {}, note) : null), control);
  return h("div", { class: "settings" },
    h("h4", {}, "조작"),
    line("터치 방식", sel("touch", [["direct", "터치 그대로 (게임이 직접 받음)"], ["mouse", "터치 → 마우스 클릭"], ["trackpad", "터치패드 (커서)"]])),
    perGame ? line("가상 패드", sel("preset", [["auto", `자동 (${PRESETS[autoPreset(kind)].name})`],
      ...Object.entries(PRESETS).map(([k, p]) => [k, p.name]), ...(values.layout ? [["custom", "직접 편집한 배치"]] : [])])) : null,
    line("버튼 진동", sw("haptics")),
    h("h4", {}, "화면"),
    line("화면 맞춤", sel("fit", [["auto", "원래 비율 유지"], ["16:9", "16:9 유지"], ["4:3", "4:3 유지"], ["fill", "꽉 채우기"], ["original", "손대지 않음"]])),
    line("해상도", sel("dpr", [["auto", "자동 (최대 2배)"], ["0.5", "0.5배 (가장 빠름)"], ["0.75", "0.75배"], ["1", "1배"], ["1.5", "1.5배"], ["2", "2배"], ["native", "기기 최대"]]), "느리거나 튕기면 낮추세요"),
    line("화면 방향", sel("orientation", [["landscape", "가로 고정"], ["portrait", "세로 고정"], ["any", "자동 회전"]])),
    line("시작 시 전체화면", sw("autoFullscreen")),
    line("화면 꺼짐 방지", sw("keepAwake")),
    line("FPS 표시", sw("fps")),
    h("h4", {}, "고급"),
    line("유니티 캐시 끄기", sw("blockUnityCache"), "같은 파일이 두 번 저장되지 않게 (권장)"),
    line("세이브 자동 동기화", sw("autoSync"), "Unity 2022+ — 종료해도 세이브 유지"),
    line("게임별 localStorage 분리", sw("isolateStorage"), "끄면 다른 게임과 세이브가 섞일 수 있음"),
    perGame ? line("격리 모드 (COOP/COEP)", sw("isolate"), "멀티스레드 빌드용. 외부 리소스를 쓰는 게임은 깨질 수 있음") : null);
}

async function openGameSettings(id) {
  const g = await games.get(id);
  const values = await effectiveSettings(g);
  const form = settingsForm(values, async (key, value) => {
    await games.patch(id, (x) => { x.settings = { ...(x.settings || {}), [key]: value }; });
  }, { perGame: true, kind: g.kind });
  const s = sheet(`${g.title} · 설정`, h("div", {}, form,
    h("div", { class: "row-actions" },
      h("button", { class: "btn", onclick: async () => {
        await games.patch(id, (x) => { x.settings = {}; });
        s.close();
        toast("이 게임 설정을 기본값으로 되돌렸습니다.");
      } }, "기본값으로"))));
}

async function openGlobalSettings() {
  const values = await globalDefaults();
  const form = settingsForm(values, async (key, value) => {
    const cur = (await kv.get("defaults")) || {};
    cur[key] = value;
    await kv.set("defaults", cur);
  }, { perGame: false });
  const persisted = navigator.storage?.persisted ? await navigator.storage.persisted().catch(() => false) : false;
  sheet("기본 설정 (모든 게임)", h("div", {},
    h("p", { class: "dim small" }, "게임별 설정에서 따로 바꾼 항목은 그 값이 우선합니다."),
    form,
    h("h4", {}, "저장 공간"),
    h("p", { class: "dim small" }, persisted ? "✓ 브라우저가 이 앱의 데이터를 자동으로 지우지 않도록 보호 중입니다."
      : "브라우저가 공간이 부족할 때 데이터를 지울 수 있습니다. 앱을 홈 화면에 설치하면 보호될 가능성이 높아요."),
    h("div", { class: "row-actions" },
      persisted ? null : h("button", { class: "btn", onclick: async () => {
        const ok = await navigator.storage?.persist?.().catch(() => false);
        toast(ok ? "보호를 켰습니다." : "브라우저가 거절했습니다. 앱을 설치한 뒤 다시 시도해 보세요.");
      } }, "데이터 보호 요청"),
      h("button", { class: "btn", onclick: clearUnityCaches }, "유니티 자체 캐시 정리"),
      h("button", { class: "btn", onclick: checkUpdate }, "앱 업데이트 확인"))));
}

async function clearUnityCaches() {
  const keys = (await caches.keys()).filter((k) => k.startsWith("UnityCache"));
  await Promise.all(keys.map((k) => caches.delete(k)));
  try { indexedDB.deleteDatabase("UnityCache"); } catch { /* 무시 */ }
  toast(keys.length ? `유니티 캐시 ${keys.length}개를 정리했습니다.` : "정리할 유니티 캐시가 없습니다.");
  updateStorage();
}

async function checkUpdate() {
  const reg = await navigator.serviceWorker?.getRegistration();
  if (!reg) return toast("서비스워커가 없습니다.");
  await reg.update().catch(() => {});
  toast("최신 버전을 확인했습니다. 바뀐 점이 있으면 다음에 열 때 적용됩니다.");
}

/* ───────────── 세이브 ───────────── */

async function openSaves(id) {
  const g = await games.get(id);
  const sum = await saveSummary(g);
  const known = sum.prefixes.length > 0;
  const unity = /^unity/.test(g.kind || "");
  const settingsIsolated = (await effectiveSettings(g)).isolateStorage !== false;
  const content = h("div", { class: "saves" },
    unity ? h("p", {}, known
      ? `세이브 파일 ${sum.files}개 (${formatBytes(sum.bytes)})${sum.latest ? ` · 마지막 저장 ${timeAgo(sum.latest)}` : ""}`
      : "아직 이 게임의 세이브 위치를 모릅니다. 게임을 플레이하며 한 번 저장하면 자동으로 기록됩니다.",
    sum.localStorageKeys ? ` · 웹 저장소 항목 ${sum.localStorageKeys}개` : "")
      : h("p", {}, sum.localStorageKeys ? `브라우저 저장소에 세이브 항목 ${sum.localStorageKeys}개`
        : ["tyrano", "rpgmv"].includes(g.kind) && settingsIsolated ? "아직 저장된 세이브가 없습니다."
          : "이 게임의 세이브를 찾지 못했습니다(게임이 다른 저장소를 쓰면 여기서 보이지 않을 수 있어요)."),
    g.kind === "tyrano" ? h("p", { class: "dim small" }, "PC판 세이브 파일(.exe 옆의 ○○_tyrano_data.sav · ○○_sf.sav — 파일 세이브를 쓰는 게임만 있어요)도 '백업 파일에서 복원'으로 넣을 수 있어요.") : null,
    h("div", { class: "action-list" },
      h("button", { class: "btn primary", onclick: async () => {
        const { blob, count } = await exportSave(g);
        if (!count) return toast("내보낼 세이브가 없습니다.");
        const d = new Date().toISOString().slice(0, 10).replace(/-/g, "");
        downloadBlob(blob, `${g.title.replace(/[\\/:*?"<>|]/g, "_")}-save-${d}.json`);
        toast(`세이브 ${count}개 항목을 내보냈습니다.`);
      } }, "⬇ 백업 파일로 내보내기"),
      h("button", { class: "btn", onclick: () => {
        const input = $("#pick-save");
        input.onchange = async () => {
          const list = Array.from(input.files);
          const f = list[0];
          input.value = "";
          if (!f) return;
          if (list.some((x) => /\.sav$/i.test(x.name))) return restoreTyranoSav(g, list, s);
          const ok = await confirmBox("세이브 복원", "백업의 세이브로 덮어씁니다. 게임이 실행 중이면 끄고 진행하세요.", "복원");
          if (!ok) return;
          try {
            const r = await importSave(g, f);
            toast(`복원했습니다 (${r.written}개 항목).`);
            if (r.unknownTarget) {
              dialog({ title: "확인 필요", body: "이 게임의 세이브 위치를 아직 몰라 백업의 원래 위치에 넣었습니다. 게임에서 세이브가 안 보이면, 게임을 한 번 실행해 아무 데이터나 저장한 뒤 다시 복원해 주세요." });
            }
            s.close();
          } catch (e) { dialog({ title: "복원 실패", body: e.message || String(e) }); }
        };
        input.click();
      } }, "⬆ 백업 파일에서 복원"),
      known || sum.localStorageKeys ? h("button", { class: "btn danger", onclick: async () => {
        if (!(await confirmBox("세이브 삭제", "이 게임의 세이브를 모두 지웁니다. 되돌릴 수 없어요.", "삭제", true))) return;
        await deleteSave(g);
        toast("세이브를 지웠습니다.");
        s.close();
      } }, "세이브 모두 삭제") : null),
    known || !unity ? null : await unknownGroups(g));
  const s = sheet(`${g.title} · 세이브`, content);
}

/** 티라노스크립트 PC판 세이브(.sav, 게임 .exe 와 같은 폴더) 넣기 */
async function restoreTyranoSav(g, list, s) {
  if (g.kind !== "tyrano") {
    return dialog({ title: "복원 실패", body: ".sav 파일은 티라노스크립트 게임의 PC판 세이브만 넣을 수 있어요." });
  }
  const ok = await confirmBox("PC판 세이브 가져오기", "같은 이름의 세이브를 덮어씁니다. 게임이 실행 중이면 끄고 진행하세요.", "가져오기");
  if (!ok) return;
  let r;
  try { r = await importTyranoSav(g, list.filter((x) => /\.sav$/i.test(x.name))); } catch (e) {
    return dialog({ title: "복원 실패", body: e.message || String(e) });
  }
  const problems = [
    r.bad.length ? `티라노스크립트 세이브 파일이 아님: ${r.bad.join(", ")} (이름이 프로젝트ID_tyrano_data.sav · 프로젝트ID_sf.sav 같은 형식이어야 해요)` : "",
    r.mismatch.length ? `이 게임의 세이브가 아님: ${r.mismatch.join(", ")} (이 게임의 세이브 파일 이름은 ${g.tyranoProjectID}_… 로 시작해요)` : "",
    r.full.length ? `저장 공간 부족으로 못 넣음: ${r.full.join(", ")} (브라우저 저장소는 모든 게임이 함께 약 5MB — 안 하는 게임의 세이브를 지워 주세요)` : "",
  ].filter(Boolean);
  if (!r.written) return dialog({ title: "복원 실패", body: h("p", { class: "dialog-body pre" }, problems.join("\n\n")) });
  if (problems.length) dialog({ title: `PC판 세이브 ${r.written}개를 넣었습니다`, body: h("p", { class: "dialog-body pre" }, problems.join("\n\n")) });
  else toast(`PC판 세이브 ${r.written}개를 넣었습니다(썸네일 그림은 빠집니다).`);
  s.close();
}

/** 위치를 모를 때: 다른 게임에 속하지 않은 /idbfs 묶음을 보여 주고 고르게 한다. */
async function unknownGroups(g) {
  const groups = await idbfsGroups().catch(() => new Map());
  const all = await games.all();
  const owned = new Set(all.flatMap((x) => x.idbfsPrefixes || (x.idbfsPrefix ? [x.idbfsPrefix] : [])));
  const free = [...groups].filter(([p]) => !owned.has(p));
  if (!free.length) return null;
  return h("div", { class: "notes" },
    h("h4", {}, "주인을 모르는 유니티 세이브"),
    h("p", { class: "dim small" }, "이전에 저장된 세이브 중 어느 게임에도 연결되지 않은 것입니다. 이 게임 것이라면 연결하세요."),
    free.map(([p, info]) => h("div", { class: "row" },
      h("div", { class: "row-label" }, `${p.split("/")[2].slice(0, 12)}…`, h("small", {}, `${info.count}개 · ${formatBytes(info.bytes)} · ${timeAgo(info.latest)}`)),
      h("button", { class: "btn small", onclick: async () => {
        await games.patch(g.id, { idbfsPrefix: p, idbfsPrefixes: [p] });
        toast("이 게임의 세이브로 연결했습니다.");
        document.querySelector(".sheet-scrim")?.remove();
        openSaves(g.id);
      } }, "연결"))));
}

/* ───────────── 도움말 ───────────── */

function openHelp() {
  sheet("도움말", h("div", { class: "help" },
    h("h4", {}, "무엇을 실행할 수 있나요?"),
    h("ul", {},
      h("li", {}, h("b", {}, "유니티 WebGL 빌드"), " — Unity 5.6 ~ Unity 6 (index.html + Build 폴더). 압축(.gz/.br) 빌드도 OK."),
      h("li", {}, h("b", {}, "티라노스크립트 · TyranoBuilder 비주얼노벨"), " — 브라우저판, 그리고 PC판(.exe)도 됩니다. 아래 참고."),
      h("li", {}, "덤으로 RPG Maker MV/MZ, 일반 HTML5 게임(index.html)도 실행을 시도합니다.")),
    h("h4", {}, "티라노스크립트 PC판(.exe)은요?"),
    h("p", {}, "티라노스크립트는 원래 HTML5 엔진이고, PC판은 그 게임을 NW.js·Electron 으로 감싼 것뿐이라 ",
      h("b", {}, "안의 게임을 꺼내 그대로 실행"), "합니다(에뮬레이션 아님)."),
    h("ul", {},
      h("li", {}, "게임 폴더(.exe 가 있는 폴더) 전체를 zip 으로 압축해 넣으세요. 용량이 크면 resources/app.asar 파일 하나만 골라도 됩니다(옛 NW.js 판은 package.nw 나 게임.exe 하나)."),
      h("li", {}, "PC판 세이브: 파일 세이브를 쓰는 게임은 .exe 옆(맥은 홈 폴더의 _TyranoGameData)에 ○○_tyrano_data.sav · ○○_sf.sav 가 있고, 폴더째 넣으면 함께 들어가 이어서 할 수 있어요. 이 파일이 없는 게임은 세이브가 PC 앱 내부 저장소에 있어 옮길 수 없습니다."),
      h("li", {}, "PC 전용 설정(파일 세이브, 화면 크기 고정 등)은 설치할 때 폰에 맞게 고칩니다."),
      h("li", {}, "처음에 화면이 멈춘 듯하면 한 번 탭하세요 — 소리 재생 허락을 기다리는 중입니다."),
      h("li", {}, "Node.js·Steam 기능을 직접 쓰는 일부 게임, Enigma Virtual Box 로 묶은 exe 는 실행할 수 없어요.")),
    h("h4", {}, "PC용 유니티 게임(.exe)을 모바일로 바꿀 수 있나요?"),
    h("p", {}, "PC 빌드는 x86 Windows 프로그램(UnityPlayer.dll)이라 그대로는 폰 브라우저에서 실행할 수 없습니다(JoiPlay 도 유니티는 미지원). ",
      "대신 PC 게임 zip 을 넣으면 UniPlay 가 파일을 살펴 ", h("b", {}, "변환 가능성 진단"), "을 보여 줍니다(유니티 버전, Mono/IL2CPP, 걸림돌)."),
    h("ul", {},
      h("li", {}, h("b", {}, "원본 프로젝트가 있으면"), " — 유니티에서 WebGL/Android 로 다시 빌드. 가장 확실합니다(개발자에게 요청)."),
      h("li", {}, h("b", {}, "그대로 돌리기"), " — 안드로이드의 Winlator(Windows 에뮬레이터). 변환 없이 되지만 폰마다 차이가 큽니다."),
      h("li", {}, h("b", {}, "Mono 빌드"), " — AssetRipper 로 프로젝트를 복원해 다시 빌드할 수 있지만 유니티 경험이 필요한 수작업입니다."),
      h("li", {}, h("b", {}, "IL2CPP 빌드"), " — 코드가 기계어라 복원이 안 됩니다. 에뮬레이터나 개발자 요청뿐이에요.")),
    h("h4", {}, "게임 넣는 법"),
    h("ol", {},
      h("li", {}, "WebGL 빌드 폴더(index.html 이 들어 있는 폴더)를 zip 으로 압축합니다."),
      h("li", {}, "＋ 게임 추가 → zip 파일을 고르면 폰 안에 설치됩니다(서버로 올라가지 않음)."),
      h("li", {}, "설치 후에는 인터넷 없이도 실행됩니다. 앱을 홈 화면에 설치해 두면 편해요.")),
    h("h4", {}, "조작"),
    h("ul", {},
      h("li", {}, "게임 중 왼쪽 위 ≡ 또는 뒤로 가기 → 메뉴."),
      h("li", {}, "가상 패드: 프리셋을 고르거나 '패드 편집'에서 버튼을 끌어 옮기고 키를 바꿉니다. 키보드 키, 게임패드 버튼(아날로그 스틱 포함), 마우스 클릭/휠을 지정할 수 있어요."),
      h("li", {}, "터치 방식: 게임이 터치에 반응하지 않으면 '터치→마우스'(탭=클릭, 길게=우클릭) 또는 '터치패드'를 써 보세요."),
      h("li", {}, "블루투스 키보드·게임패드도 그대로 동작합니다.")),
    h("h4", {}, "느리거나 튕길 때"),
    h("ul", {},
      h("li", {}, "메뉴 → 해상도를 1배 또는 0.75배로 낮추세요."),
      h("li", {}, "다른 앱을 닫아 메모리를 확보하세요. 큰 3D 게임은 폰 브라우저에서 무리일 수 있어요."),
      h("li", {}, "메뉴 → 로그에서 오류를 확인할 수 있습니다.")),
    h("h4", {}, "세이브"),
    h("p", {}, "세이브는 이 기기 브라우저에 저장됩니다. 브라우저 데이터를 지우면 함께 사라지니, ",
      "게임 ⋯ → 세이브 백업으로 가끔 파일로 내보내 두세요. 아이폰은 사파리가 7일 동안 안 쓴 사이트의 데이터를 지울 수 있으니 ",
      "꼭 '홈 화면에 추가'한 앱으로 쓰세요."),
  ));
}

$("#help-btn").addEventListener("click", openHelp);
$("#empty-help").addEventListener("click", openHelp);
$("#settings-btn").addEventListener("click", openGlobalSettings);

render();
