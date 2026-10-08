/* 작은 UI 도우미: 요소 생성, 토스트, 확인창, 바텀시트. */

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

let toastTimer = null;
export function toast(msg, ms = 2600) {
  let el = document.getElementById("toast");
  if (!el) {
    el = h("div", { id: "toast", role: "status", "aria-live": "polite" });
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

/** 모달 대화상자. buttons: [{label, value, kind}] → 누른 버튼의 value 로 resolve */
export function dialog({ title, body, buttons = [{ label: "확인", value: true, kind: "primary" }], dismissValue = null }) {
  return new Promise((resolve) => {
    const close = (v) => { wrap.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => { if (e.key === "Escape") close(dismissValue); };
    const box = h("div", { class: "dialog", role: "dialog", "aria-modal": "true" },
      title ? h("h3", {}, title) : null,
      typeof body === "string" ? h("p", { class: "dialog-body" }, body) : body,
      h("div", { class: "dialog-actions" },
        buttons.map((b) => h("button", { class: `btn ${b.kind || ""}`, onclick: () => close(b.value) }, b.label))));
    const wrap = h("div", { class: "scrim", onclick: (e) => { if (e.target === wrap) close(dismissValue); } }, box);
    document.body.appendChild(wrap);
    document.addEventListener("keydown", onKey);
    box.querySelector(".btn.primary, .btn")?.focus();
  });
}

export function confirmBox(title, body, okLabel = "확인", danger = false) {
  return dialog({
    title, body,
    buttons: [{ label: "취소", value: false }, { label: okLabel, value: true, kind: danger ? "danger" : "primary" }],
    dismissValue: false,
  });
}

export function promptBox(title, value = "", placeholder = "") {
  const input = h("input", { class: "field", value, placeholder, type: "text" });
  const p = dialog({
    title,
    body: input,
    buttons: [{ label: "취소", value: null }, { label: "확인", value: "ok", kind: "primary" }],
  }).then((v) => (v === "ok" ? input.value : null));
  setTimeout(() => { input.focus(); input.select(); }, 30);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") input.closest(".dialog").querySelector(".btn.primary").click(); });
  return p;
}

/** 아래에서 올라오는 시트. 반환값.close() 로 닫는다. */
export function sheet(title, content, { onClose, wide = false } = {}) {
  const close = () => {
    wrap.style.pointerEvents = "none"; // 닫히는 애니메이션 동안 터치를 가로채지 않게
    wrap.classList.remove("open");
    setTimeout(() => wrap.remove(), 180);
    onClose?.();
  };
  const panel = h("div", { class: "sheet" + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true" },
    h("div", { class: "sheet-head" },
      h("h3", {}, title),
      h("button", { class: "icon-btn", "aria-label": "닫기", onclick: close }, "✕")),
    h("div", { class: "sheet-body" }, content));
  const wrap = h("div", { class: "scrim sheet-scrim", onclick: (e) => { if (e.target === wrap) close(); } }, panel);
  document.body.appendChild(wrap);
  requestAnimationFrame(() => wrap.classList.add("open"));
  return { close, panel, body: panel.querySelector(".sheet-body") };
}

export function downloadBlob(blob, name) {
  const a = h("a", { href: URL.createObjectURL(blob), download: name });
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
}

export function timeAgo(ts) {
  if (!ts) return "아직 안 함";
  const s = (Date.now() - ts) / 1000;
  if (s < 60) return "방금";
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}일 전`;
  return new Date(ts).toLocaleDateString("ko-KR");
}

export function formatDuration(sec) {
  sec = Math.round(sec || 0);
  if (sec < 60) return `${sec}초`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m}분`;
  return `${Math.floor(m / 60)}시간 ${m % 60}분`;
}
