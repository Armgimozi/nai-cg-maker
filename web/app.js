"use strict";

const EXAMPLES = [
  "비 오는 창가에 앉아 밖을 바라보는, 우울하고 차분한 분위기",
  "벚꽃 흩날리는 봄, 바람에 머리카락이 날리는 상반신",
  "야경이 보이는 옥상에서 검을 든, 로우앵글",
  "여름 해질녘 바닷가에서 뒤돌아보며 웃는 모습",
];
const CAT_ORDER = ["character", "copyright", "general", "artist", "meta", "other"];
const CAT_LABEL = { general: "일반", character: "캐릭터", copyright: "작품", artist: "작가", meta: "메타", other: "기타" };
const RATING_IDX = { general: 0, sensitive: 1, questionable: 2, explicit: 3 };

let lastTags = [], maxRating = 3;
let lastInterpretation = "", lastStats = null;   // 태그 추출 시 장면 해석/통계
let refImage = null;          // 참고 이미지(재구성용) dataURL
let refs = [];                // [{url,strength,info,type,fidelity}] 캐릭터 레퍼런스
let refMode = "precise";      // "precise"(V4.5 정밀 참조) | "vibe"(vibe transfer)
let gallery = [];             // [{url,seed,w,h}]
let curImg = null;            // 작업 영역 {url,seed,w,h}
let masking = false, brushSize = 55, drawing = false, lastPt = null;
let queue = [], queueRunning = false;
let seqIdx = 0, seqFoundation = null;

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function fmtCount(n) { if (!n) return ""; if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M"; if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "k"; return String(n); }
function setBox(id, msg, kind) { const el = $(id); if (!msg) { el.hidden = true; return; } el.hidden = false; el.textContent = msg; el.className = "status " + (kind || ""); }
function genInfo(msg, kind) { const el = $("#genInfo"); el.textContent = msg || ""; el.className = "gen-info" + (kind === "err" ? " err" : ""); }

// ── API (BYO-key) ────────────────────────────────────────
function authHeaders() {
  const h = { "Content-Type": "application/json" };
  const a = localStorage.getItem("anthropic_key"); if (a) h["X-Anthropic-Key"] = a;
  const n = localStorage.getItem("nai_token"); if (n) h["X-NAI-Token"] = n;
  return h;
}
async function safeJson(res) { const t = await res.text(); try { return JSON.parse(t); } catch { return { error: `서버 응답 오류 (HTTP ${res.status})` }; } }
async function api(path, body) {
  const res = await fetch(path, { method: "POST", headers: authHeaders(), body: JSON.stringify(body) });
  const d = await safeJson(res);
  if (!res.ok) throw new Error(d.error || ("HTTP " + res.status));
  return d;
}
function loadKeys() {
  $("#keyAnthropic").value = localStorage.getItem("anthropic_key") || "";
  $("#keyNai").value = localStorage.getItem("nai_token") || "";
}

// ── 설정/프롬프트 브라우저 저장(localStorage) ────────────
const STATE_KEY = "studio_state";
let _saveTimer = null;
function scheduleSave() { clearTimeout(_saveTimer); _saveTimer = setTimeout(saveState, 400); }
function saveState() {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({
      scene: $("#scene").value, base: $("#basePrompt").value, neg: $("#negPrompt").value, refText: $("#refText").value,
      refMode,
      chars: $$("#charList .char-input").map((t) => t.value),
      seq: $$("#seqList .seq-input").map((t) => t.value),
      set: {
        model: $("#setModel").value, size: $("#setSize").value, w: $("#setW").value, h: $("#setH").value,
        sampler: $("#setSampler").value, noise: $("#setNoise").value, steps: $("#setSteps").value,
        scale: $("#setScale").value, rescale: $("#setRescale").value, seed: $("#setSeed").value, seedFix: $("#seedFix").checked,
      },
    }));
  } catch (e) { /* quota 초과 등은 무시 */ }
}
function loadState() {
  let s; try { s = JSON.parse(localStorage.getItem(STATE_KEY) || "null"); } catch { s = null; }
  if (!s) return false;
  const set = (id, v) => { if (v != null && $(id)) $(id).value = v; };
  set("#scene", s.scene); set("#basePrompt", s.base); set("#negPrompt", s.neg); set("#refText", s.refText);
  if (s.refMode === "vibe" || s.refMode === "precise") refMode = s.refMode;
  $("#charList").innerHTML = ""; (Array.isArray(s.chars) && s.chars.length ? s.chars : [""]).forEach((v) => addCharRow(v));
  $("#seqList").innerHTML = ""; (Array.isArray(s.seq) ? s.seq : []).forEach((v) => addSeqRow(v));
  const st = s.set || {};
  set("#setModel", st.model); set("#setSize", st.size); set("#setW", st.w); set("#setH", st.h);
  set("#setSampler", st.sampler); set("#setNoise", st.noise); set("#setSteps", st.steps);
  set("#setScale", st.scale); set("#setRescale", st.rescale); set("#setSeed", st.seed);
  if (st.seedFix != null) $("#seedFix").checked = st.seedFix;
  $("#stepsVal").textContent = $("#setSteps").value;
  $("#scaleVal").textContent = $("#setScale").value;
  $("#rescaleVal").textContent = $("#setRescale").value;
  $("#customSize").hidden = $("#setSize").value !== "custom";
  return true;
}

// ── 캐릭터 프롬프트 행 ────────────────────────────────────
function addCharRow(value = "") {
  const row = document.createElement("div");
  row.className = "char-row";
  const ta = document.createElement("textarea");
  ta.className = "prompt char-input"; ta.rows = 2;
  ta.placeholder = "long_hair, blue_eyes, school_uniform, smile, ...";
  ta.value = value;
  const rm = document.createElement("button");
  rm.className = "ghost xs rm"; rm.textContent = "✕"; rm.onclick = () => { row.remove(); saveState(); };
  row.append(ta, rm); $("#charList").appendChild(row); return ta;
}
const getChars = () => $$("#charList .char-input").map((t) => t.value.trim()).filter(Boolean);

// ── 예시 ─────────────────────────────────────────────────
function initExamples() {
  EXAMPLES.forEach((ex) => {
    const b = document.createElement("button");
    b.textContent = ex.length > 20 ? ex.slice(0, 19) + "…" : ex; b.title = ex;
    b.onclick = () => { $("#scene").value = ex; $("#scene").focus(); };
    $("#examples").appendChild(b);
  });
}

// ── 태그 찾기 ────────────────────────────────────────────
async function findTags() {
  const scene = $("#scene").value.trim();
  if (!scene) { setBox("#tagStatus", "원하는 장면을 먼저 입력하세요.", "err"); return; }
  $("#findTagsBtn").disabled = true; setBox("#tagStatus", "태그를 찾는 중…", "load"); $("#results").innerHTML = "";
  try {
    const data = await api("/api/suggest", { scene });
    setBox("#tagStatus", "", ""); lastTags = data.tags || [];
    lastInterpretation = data.interpretation || ""; lastStats = data.stats || null;
    $("#ratingSeg").hidden = false; renderTags();
  } catch (e) { setBox("#tagStatus", "오류: " + e.message, "err"); }
  finally { $("#findTagsBtn").disabled = false; }
}
function renderTags() {
  const root = $("#results"); root.innerHTML = ""; if (!lastTags.length) return;
  const visible = lastTags.filter((x) => RATING_IDX[x.rating] <= maxRating);
  if (lastInterpretation || lastStats) {
    const info = document.createElement("div"); info.className = "tag-info";
    const interp = lastInterpretation ? `<p class="tag-interp">🔎 ${esc(lastInterpretation)}</p>` : "";
    const stat = lastStats ? `<p class="tag-stat">태그 ${lastStats.total}개 · 검증됨 ${lastStats.verified}개 · 현재 표시 ${visible.length}개</p>` : "";
    info.innerHTML = interp + stat; root.appendChild(info);
  }
  const hint = document.createElement("p"); hint.className = "tag-hint"; hint.textContent = "태그를 누르면 베이스 프롬프트에 추가됩니다."; root.appendChild(hint);
  if (!visible.length) return;
  const groups = {}; visible.forEach((x) => { (groups[x.category] ||= []).push(x); });
  CAT_ORDER.forEach((cat) => {
    const list = groups[cat]; if (!list || !list.length) return;
    const g = document.createElement("div"); g.className = "group";
    g.innerHTML = `<h2>${CAT_LABEL[cat] || cat} <span class="n">${list.length}</span></h2>`;
    const chips = document.createElement("div"); chips.className = "chips";
    list.forEach((x) => chips.appendChild(makeChip(x))); g.appendChild(chips); root.appendChild(g);
  });
}
function makeChip(x) {
  const el = document.createElement("div"); el.className = "chip" + (x.status === "unverified" ? " unverified" : "");
  const dot = `<span class="dot" style="background:var(--r-${x.rating})"></span>`;
  const cnt = x.count ? `<span class="cnt">${fmtCount(x.count)}</span>` : "";
  const q = x.status === "unverified" ? '<span class="q" title="사전에 없는 태그">?</span>' : "";
  el.innerHTML = `${dot}<span class="name">${esc(x.tag)}</span>${cnt}${q}`;
  el.onclick = () => appendToBase(x.tag); return el;
}
function appendToBase(tag) {
  const ta = $("#basePrompt");
  if (ta.value.split(/[,\n]/).map((s) => s.trim()).includes(tag)) return;
  ta.value = (ta.value.trim() ? ta.value.trim() + ", " : "") + tag;
  saveState();
}

// ── 재구성 (참고글/URL/이미지 반영) ──────────────────────
async function reconstruct() {
  const refRaw = $("#refText").value.trim();
  const isUrl = /^https?:\/\/\S+$/i.test(refRaw);
  const body = {
    scene: $("#scene").value.trim(), base_prompt: $("#basePrompt").value.trim(),
    character_prompts: getChars(), negative_prompt: $("#negPrompt").value.trim(), tags: [],
  };
  if (refRaw) { if (isUrl) body.reference_url = refRaw; else body.reference_text = refRaw; }
  if (refImage) body.image = refImage;
  $("#reconBtn").disabled = true; setBox("#reconStatus", "장면에 맞춰 재구성하는 중…", "load");
  try {
    const d = await api("/api/compose", body);
    $("#basePrompt").value = d.base_prompt || "";
    $("#charList").innerHTML = ""; (d.character_prompts || []).forEach((c) => addCharRow(c.prompt || ""));
    if (!getChars().length) addCharRow("");
    $("#negPrompt").value = d.negative_prompt || "";
    saveState();
    setBox("#reconStatus", d.note ? "✨ " + d.note : "재구성 완료.", "load");
  } catch (e) { setBox("#reconStatus", "오류: " + e.message, "err"); }
  finally { $("#reconBtn").disabled = false; }
}

// ── 캐릭터 레퍼런스(Precise Reference / Vibe Transfer) ────
function applyRefMode() {
  $$("#refModeSeg button").forEach((b) => b.classList.toggle("active", b.dataset.m === refMode));
  $("#refModeHint").textContent = refMode === "precise"
    ? "V4.5 정밀 참조 — 캐릭터/스타일을 더 정확히 유지. 생성당 +5 Anlas · vibe와 동시 사용 불가."
    : "Vibe Transfer — 분위기/스타일 위주 참조(추가 비용 없음).";
  renderRefs();
}
function setRefMode(m) { refMode = m === "vibe" ? "vibe" : "precise"; applyRefMode(); saveState(); }

function addRefFiles(files) {
  [...files].forEach((f) => { if (!f.type.startsWith("image/")) return;
    const r = new FileReader(); r.onload = () => { refs.push({ url: r.result, strength: 1.0, info: 1.0, type: "character", fidelity: 1.0 }); renderRefs(); }; r.readAsDataURL(f); });
}
function renderRefs() {
  const box = $("#refList"); box.innerHTML = "";
  refs.forEach((r, i) => {
    const row = document.createElement("div"); row.className = "ref-row";
    const ctrls = refMode === "precise" ? `
        <label>유형 <select class="ref-type" data-i="${i}">
          <option value="character"${r.type === "character" ? " selected" : ""}>캐릭터</option>
          <option value="style"${r.type === "style" ? " selected" : ""}>스타일</option>
          <option value="both"${r.type === "both" ? " selected" : ""}>캐릭터+스타일</option>
        </select></label>
        <label>강도 <span class="val">${r.strength.toFixed(2)}</span><input type="range" min="0" max="1" step="0.05" value="${r.strength}" data-i="${i}" data-k="strength" /></label>
        <label>정밀도 <span class="val">${r.fidelity.toFixed(2)}</span><input type="range" min="0" max="1" step="0.05" value="${r.fidelity}" data-i="${i}" data-k="fidelity" /></label>` : `
        <label>강도 <span class="val">${r.strength.toFixed(2)}</span><input type="range" min="0" max="1" step="0.05" value="${r.strength}" data-i="${i}" data-k="strength" /></label>
        <label>정보추출 <span class="val">${r.info.toFixed(2)}</span><input type="range" min="0" max="1" step="0.05" value="${r.info}" data-i="${i}" data-k="info" /></label>`;
    row.innerHTML = `<img src="${r.url}" class="ref-thumb" alt="ref" />
      <div class="ref-ctrls">${ctrls}</div>
      <button class="ghost xs rm" data-rm="${i}">✕</button>`;
    box.appendChild(row);
  });
  box.querySelectorAll('input[type="range"]').forEach((inp) => inp.oninput = (e) => { const i = +e.target.dataset.i, k = e.target.dataset.k; refs[i][k] = Number(e.target.value); e.target.previousElementSibling.textContent = refs[i][k].toFixed(2); });
  box.querySelectorAll("select.ref-type").forEach((sel) => sel.onchange = (e) => { refs[+e.target.dataset.i].type = e.target.value; });
  box.querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => { refs.splice(+b.dataset.rm, 1); renderRefs(); });
}
const getRefs = () => refs.map((r) => ({ image: r.url, mode: refMode, strength: r.strength, info_extracted: r.info, ref_type: r.type, fidelity: r.fidelity }));

// ── 설정 ─────────────────────────────────────────────────
function getSettings() { return { model: $("#setModel").value, steps: Number($("#setSteps").value), scale: Number($("#setScale").value), cfg_rescale: Number($("#setRescale").value), sampler: $("#setSampler").value, noise_schedule: $("#setNoise").value }; }
function getSize() { const v = $("#setSize").value; if (v === "custom") return [Number($("#setW").value) || 832, Number($("#setH").value) || 1216]; return v.split("x").map(Number); }
function getSeed() { if (!$("#seedFix").checked) return null; const s = $("#setSeed").value.trim(); return s === "" ? null : Number(s); }
function getGenBody(base, chars, neg) {
  const [w, h] = getSize();
  return {
    base_prompt: base !== undefined ? base : $("#basePrompt").value.trim(),
    character_prompts: chars !== undefined ? chars : getChars(),
    negative_prompt: neg !== undefined ? neg : $("#negPrompt").value.trim(),
    width: w, height: h, seed: getSeed(), settings: getSettings(), references: getRefs(),
  };
}

// ── 큐(대기열) ───────────────────────────────────────────
function enqueue(job) { queue.push(job); renderQueue(); runQueue(); }
function renderQueue() { const el = $("#queueStatus"); if (!queue.length && !queueRunning) { el.hidden = true; return; } el.hidden = false; el.textContent = `대기열: ${queue.length}개${queueRunning ? " (실행 중)" : ""}`; }
async function runQueue() {
  if (queueRunning) return; queueRunning = true;
  while (queue.length) {
    const job = queue[0]; renderQueue(); genInfo(`${job.label} 중… (대기 ${queue.length - 1})`);
    try { await job.run(); genInfo(`완료 · 대기 ${queue.length - 1}`); }
    catch (e) { genInfo("오류: " + e.message, "err"); }
    queue.shift(); renderQueue();
  }
  queueRunning = false; renderQueue();
}
function queueGenerate(n) {
  const body0 = getGenBody();
  if (!body0.base_prompt && !body0.character_prompts.length) { genInfo("프롬프트가 비어 있습니다. 먼저 입력/재구성하세요.", "err"); return; }
  for (let i = 0; i < n; i++) {
    const body = getGenBody();
    enqueue({ label: "생성", run: async () => { const d = await api("/api/generate", body); addGallery(d.image, d.seed, body.width, body.height); showImage(d.image, d.seed, body.width, body.height); } });
  }
}

// ── 갤러리 ───────────────────────────────────────────────
function addGallery(url, seed, w, h) {
  gallery.unshift({ url, seed, w, h }); $("#galleryCard").hidden = false; renderGallery();
}
function renderGallery() {
  const box = $("#gallery"); box.innerHTML = "";
  gallery.forEach((g) => {
    const d = document.createElement("div"); d.className = "gthumb";
    d.innerHTML = `<img src="${g.url}" alt="result" /><span class="gseed">${g.seed}</span>`;
    d.onclick = () => showImage(g.url, g.seed, g.w, g.h);
    box.appendChild(d);
  });
}

// ── 작업 이미지 + 인페인트 ───────────────────────────────
function showImage(url, seed, w, h) {
  curImg = { url, seed, w, h }; masking = false;
  $("#genResult").innerHTML = `
    <div class="img-wrap"><img id="genImg" src="${url}" alt="작업 이미지" /><canvas id="maskCanvas"></canvas></div>
    <div class="inpaint-bar">
      <button id="inpaintToggle" class="ghost">🖌 인페인트</button>
      <span id="ipControls" class="ip-controls" hidden>
        <span class="ip-lbl">브러시</span><input type="range" id="brush" min="10" max="180" value="55" />
        <button id="maskClear" class="ghost">마스크 지우기</button>
        <button id="inpaintRun" class="go small">선택 영역 다시 그리기</button>
      </span>
      <a class="ghost dl" href="${url}" download="nai_${seed}.png">다운로드</a>
    </div>
    <p id="ipHint" class="ip-hint" hidden>흰색으로 칠한 영역만 다시 그려집니다.</p>`;
  const canvas = $("#maskCanvas"); canvas.width = w; canvas.height = h; setupCanvas(canvas);
  $("#inpaintToggle").onclick = toggleMask;
  $("#brush").oninput = (e) => { brushSize = Number(e.target.value); }; brushSize = 55;
  $("#maskClear").onclick = clearMask;
  $("#inpaintRun").onclick = () => runInpaint($("#basePrompt").value.trim());
}
function setupCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  canvas.onpointerdown = (e) => { if (!masking) return; e.preventDefault(); drawing = true; try { canvas.setPointerCapture(e.pointerId); } catch { } const p = ptOf(e, canvas); dab(ctx, p, p); lastPt = p; };
  canvas.onpointermove = (e) => { if (!drawing || !masking) return; const p = ptOf(e, canvas); dab(ctx, lastPt || p, p); lastPt = p; };
  canvas.onpointerup = canvas.onpointercancel = () => { drawing = false; lastPt = null; };
}
function ptOf(e, c) { const r = c.getBoundingClientRect(); return { x: (e.clientX - r.left) * (c.width / r.width), y: (e.clientY - r.top) * (c.height / r.height) }; }
function dab(ctx, a, b) { ctx.strokeStyle = "#fff"; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.lineWidth = brushSize; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
function clearMask() { const c = $("#maskCanvas"); c.getContext("2d").clearRect(0, 0, c.width, c.height); }
function toggleMask() { masking = !masking; $("#maskCanvas").classList.toggle("active", masking); $("#ipControls").hidden = !masking; $("#ipHint").hidden = !masking; $("#inpaintToggle").textContent = masking ? "🖌 인페인트 끄기" : "🖌 인페인트"; }
function exportMask() {
  const s = $("#maskCanvas");
  const o = document.createElement("canvas"); o.width = s.width; o.height = s.height;
  const c = o.getContext("2d");
  c.fillStyle = "#000"; c.fillRect(0, 0, o.width, o.height); c.drawImage(s, 0, 0);
  // NAI infill 은 흰=재생성/검=유지의 '이진' 마스크를 기대한다. 브러시 경계의
  // 안티앨리어싱(회색)을 그대로 두면 부분 강도로 해석돼 결과가 흐려지므로,
  // 임계값으로 순수 흑백(알파 255)으로 만든다.
  const img = c.getImageData(0, 0, o.width, o.height), d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const v = d[i] > 127 ? 255 : 0;
    d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255;
  }
  c.putImageData(img, 0, 0);
  return o.toDataURL("image/png");
}
function fullMask(w, h) { const o = document.createElement("canvas"); o.width = w; o.height = h; const c = o.getContext("2d"); c.fillStyle = "#fff"; c.fillRect(0, 0, w, h); return o.toDataURL("image/png"); }
function maskHasContent() { const c = $("#maskCanvas"); const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true; return false; }
async function runInpaint(basePrompt) {
  if (!curImg) return;
  if (!maskHasContent()) { genInfo("먼저 다시 그릴 영역을 칠하세요.", "err"); return; }
  const body = { base_prompt: basePrompt, character_prompts: getChars(), negative_prompt: $("#negPrompt").value.trim(), image: curImg.url, mask: exportMask(), width: curImg.w, height: curImg.h, seed: getSeed(), settings: getSettings(), references: getRefs() };
  genInfo("인페인트 중… (10~25초)");
  try { const d = await api("/api/inpaint", body); addGallery(d.image, d.seed, curImg.w, curImg.h); showImage(d.image, d.seed, curImg.w, curImg.h); genInfo("인페인트 완료 · seed " + d.seed); }
  catch (e) { genInfo("오류: " + e.message, "err"); }
}

// ── 연속 시퀀스 (인페인트 체인) ──────────────────────────
function addSeqRow(value = "") {
  const row = document.createElement("div"); row.className = "char-row";
  const inp = document.createElement("input"); inp.type = "text"; inp.className = "prompt seq-input";
  inp.placeholder = "이 프레임의 장면을 한글로 (예: 침대에 앉아 이쪽을 바라본다)"; inp.value = value;
  const rm = document.createElement("button"); rm.className = "ghost xs rm"; rm.textContent = "✕"; rm.onclick = () => { row.remove(); saveState(); };
  row.append(inp, rm); $("#seqList").appendChild(row);
}
const seqScenes = () => $$("#seqList .seq-input").map((t) => t.value.trim()).filter(Boolean);

// 한글 장면 → Claude 재구성 → {base, chars, neg}. found 를 정체성 바탕으로 사용해 연속성 유지.
// frameIdx 를 주면 전체 시퀀스(seqScenes)를 맥락으로 넘겨 앞뒤가 이어지게 한다.
async function composeScene(scene, found, frameIdx) {
  const body = { scene, base_prompt: found.base, character_prompts: found.chars,
                 negative_prompt: found.neg, tags: [],
                 sequence_scenes: seqScenes(), frame_index: frameIdx };
  const refRaw = $("#refText").value.trim();
  if (refRaw) { if (/^https?:\/\/\S+$/i.test(refRaw)) body.reference_url = refRaw; else body.reference_text = refRaw; }
  if (refImage) body.image = refImage;
  const d = await api("/api/compose", body);
  return { base: d.base_prompt || "", chars: (d.character_prompts || []).map((c) => c.prompt), neg: d.negative_prompt || "" };
}
async function seqStart() {
  const seq = seqScenes();
  if (!seq.length) { $("#seqInfo").textContent = "장면을 1개 이상 입력하세요."; return; }
  $("#seqStartBtn").disabled = true; $("#seqInfo").textContent = "프레임 1: 장면 재구성 + 생성 중…";
  try {
    const found0 = { base: $("#basePrompt").value.trim(), chars: getChars(), neg: $("#negPrompt").value.trim() };
    const p = await composeScene(seq[0], found0, 0); seqFoundation = p;
    const body = getGenBody(p.base, p.chars, p.neg);
    const d = await api("/api/generate", body);
    addGallery(d.image, d.seed, body.width, body.height); showImage(d.image, d.seed, body.width, body.height);
    seqIdx = 1; $("#seqNextBtn").disabled = false;
    $("#seqInfo").textContent = `프레임 1/${seq.length} 완료 · 바뀔 곳 마스킹 후 ②`;
  } catch (e) { $("#seqInfo").textContent = "오류: " + e.message; }
  finally { $("#seqStartBtn").disabled = false; }
}
async function seqNext() {
  if (!curImg) { $("#seqInfo").textContent = "먼저 ①로 프레임 1을 생성하세요."; return; }
  const seq = seqScenes();
  if (seqIdx >= seq.length) { $("#seqInfo").textContent = "마지막 프레임입니다."; return; }
  $("#seqNextBtn").disabled = true; $("#seqInfo").textContent = `프레임 ${seqIdx + 1}: 장면 재구성 + 인페인트 중…`;
  try {
    const found = seqFoundation || { base: $("#basePrompt").value.trim(), chars: getChars(), neg: $("#negPrompt").value.trim() };
    const p = await composeScene(seq[seqIdx], found, seqIdx); seqFoundation = p;
    const mask = maskHasContent() ? exportMask() : fullMask(curImg.w, curImg.h);
    const body = { base_prompt: p.base, character_prompts: p.chars, negative_prompt: p.neg,
                   image: curImg.url, mask, width: curImg.w, height: curImg.h,
                   seed: getSeed(), settings: getSettings(), references: getRefs() };
    const d = await api("/api/inpaint", body);
    addGallery(d.image, d.seed, curImg.w, curImg.h); showImage(d.image, d.seed, curImg.w, curImg.h);
    seqIdx++;
    $("#seqInfo").textContent = seqIdx >= seq.length ? `완료 (${seq.length}프레임)` : `프레임 ${seqIdx}/${seq.length} 완료 · 마스킹 후 ②`;
  } catch (e) { $("#seqInfo").textContent = "오류: " + e.message; }
  finally { $("#seqNextBtn").disabled = seqIdx >= seqScenes().length; }
}

// ── 초기화 ───────────────────────────────────────────────
initExamples(); loadKeys();
if (!loadState()) {
  addCharRow("");
  addSeqRow("창가에 서서 밖을 바라본다"); addSeqRow("돌아서서 이쪽을 본다"); addSeqRow("의자에 앉아 미소짓는다");
}
applyRefMode();
document.addEventListener("input", scheduleSave);
document.addEventListener("change", scheduleSave);
$("#keySave").onclick = () => { localStorage.setItem("anthropic_key", $("#keyAnthropic").value.trim()); localStorage.setItem("nai_token", $("#keyNai").value.trim()); $("#keyStatus").textContent = "저장됨 ✓"; setTimeout(() => $("#keyStatus").textContent = "", 2000); };
$("#findTagsBtn").onclick = findTags;
$("#ratingSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; maxRating = Number(b.dataset.r); $$("#ratingSeg button").forEach((x) => x.classList.toggle("active", x === b)); renderTags(); });
$("#scene").addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") findTags(); });
$("#reconBtn").onclick = reconstruct;
$("#addCharBtn").onclick = () => { addCharRow(""); saveState(); };
$("#refImgBtn").onclick = () => $("#refImgInput").click();
$("#refImgInput").onchange = (e) => { const f = e.target.files[0]; if (!f) return; const r = new FileReader(); r.onload = () => { refImage = r.result; $("#refImgPreview").src = refImage; $("#refImgPreview").hidden = false; $("#refImgClear").hidden = false; }; r.readAsDataURL(f); e.target.value = ""; };
$("#refImgClear").onclick = () => { refImage = null; $("#refImgPreview").hidden = true; $("#refImgClear").hidden = true; };
$("#refBtn").onclick = () => $("#refInput").click();
$("#refInput").onchange = (e) => { addRefFiles(e.target.files); e.target.value = ""; };
$("#refModeSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setRefMode(b.dataset.m); });
$("#setSize").onchange = (e) => { $("#customSize").hidden = e.target.value !== "custom"; };
$("#setSteps").oninput = (e) => { $("#stepsVal").textContent = e.target.value; };
$("#setScale").oninput = (e) => { $("#scaleVal").textContent = e.target.value; };
$("#setRescale").oninput = (e) => { $("#rescaleVal").textContent = e.target.value; };
$("#genBtn").onclick = () => queueGenerate(1);
$("#queueAddBtn").onclick = () => queueGenerate(1);
$("#queueAddN").onclick = () => queueGenerate(Math.max(1, Math.min(20, Number($("#queueN").value) || 1)));
$("#addSeqBtn").onclick = () => { addSeqRow(""); saveState(); };
$("#seqStartBtn").onclick = seqStart;
$("#seqNextBtn").onclick = seqNext;
