/* 화면 위 가상 패드: 십자키 · 아날로그 스틱 · 버튼, 그리고 레이아웃 편집.
 *
 * 컨트롤은 입력을 직접 만들지 않고 send(binding, down) / axis(index, value) 를 부른다.
 * 실제로 게임에 키·패드·마우스 이벤트를 넣는 건 player.js 쪽 일.
 * 멀티터치: 컨트롤마다 pointerId 를 잡아(setPointerCapture) 따로 처리한다.
 */

import { bindingLabel } from "./keys.js";

const DIR_KEYS = {
  arrows: { up: "key:ArrowUp", down: "key:ArrowDown", left: "key:ArrowLeft", right: "key:ArrowRight" },
  wasd: { up: "key:KeyW", down: "key:KeyS", left: "key:KeyA", right: "key:KeyD" },
  pad: { up: "pad:12", down: "pad:13", left: "pad:14", right: "pad:15" },
};
const MODE_LABEL = { arrows: "방향키", wasd: "WASD", pad: "패드 십자키", "pad-left": "왼쪽 스틱", "pad-right": "오른쪽 스틱" };

export class Controls {
  /**
   * @param {HTMLElement} root 오버레이 컨테이너
   * @param {{send:(bind:string,down:boolean)=>void, axis:(i:number,v:number)=>void, haptics?:()=>boolean}} io
   */
  constructor(root, io) {
    this.root = root;
    this.io = io;
    this.layout = [];
    this.editing = false;
    this.onSelect = null; // 편집 중 컨트롤을 탭했을 때
    this.onChange = null; // 편집 중 위치가 바뀌었을 때
    this.selectedId = null;
    this.els = new Map();
    window.addEventListener("resize", () => this.position());
  }

  setOpacity(v) { this.root.style.setProperty("--pad-opacity", String(v)); }
  setVisible(v) { this.root.hidden = !v; if (!v) this.releaseAll(); }

  setLayout(layout) {
    this.releaseAll();
    this.layout = (layout || []).map((c, i) => ({ id: c.id || `c${Date.now().toString(36)}${i}`, ...c }));
    this.render();
  }

  getLayout() { return this.layout.map((c) => ({ ...c })); }

  vmin() { return Math.min(window.innerWidth, window.innerHeight); }

  render() {
    this.root.textContent = "";
    this.els.clear();
    for (const c of this.layout) {
      const el = document.createElement("div");
      el.className = `pad-ctl pad-${c.type}` + (c.shape === "pill" ? " pill" : "");
      el.dataset.id = c.id;
      if (c.type === "button") {
        el.textContent = c.label || bindingLabel(c.bind);
      } else if (c.type === "dpad") {
        el.innerHTML = '<i class="d-up"></i><i class="d-down"></i><i class="d-left"></i><i class="d-right"></i>';
      } else if (c.type === "stick") {
        el.innerHTML = '<i class="knob"></i>';
      }
      if (this.editing) {
        const tag = document.createElement("span");
        tag.className = "pad-tag";
        tag.textContent = c.type === "button" ? bindingLabel(c.bind) : MODE_LABEL[c.mode] || c.mode;
        el.appendChild(tag);
      }
      this.root.appendChild(el);
      this.els.set(c.id, el);
      this.attach(el, c);
    }
    this.root.classList.toggle("editing", this.editing);
    this.position();
    this.markSelected();
  }

  position() {
    const vw = window.innerWidth, vh = window.innerHeight, m = this.vmin();
    for (const c of this.layout) {
      const el = this.els.get(c.id);
      if (!el) continue;
      const d = Math.round(c.size * m);
      const w = c.shape === "pill" ? Math.round(d * 1.6) : d;
      const h = c.shape === "pill" ? Math.round(d * 0.62) : d;
      el.style.width = w + "px";
      el.style.height = h + "px";
      el.style.left = Math.round(c.x * vw - w / 2) + "px";
      el.style.top = Math.round(c.y * vh - h / 2) + "px";
      el.style.fontSize = Math.max(11, Math.round(Math.min(w, h) * 0.3)) + "px";
    }
  }

  vibrate() {
    if (this.io.haptics?.() && navigator.vibrate) { try { navigator.vibrate(8); } catch { /* 무시 */ } }
  }

  /* ───── 입력 ───── */

  attach(el, c) {
    const state = { pointer: null, dirs: new Set(), down: false, start: null, moved: false };
    el._state = state;
    el.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (state.pointer !== null) return;
      state.pointer = e.pointerId;
      try { el.setPointerCapture(e.pointerId); } catch { /* 무시 */ }
      if (this.editing) return this.editStart(el, c, e);
      el.classList.add("active");
      if (c.type === "button") this.press(c, state, true);
      else this.track(el, c, state, e);
    });
    el.addEventListener("pointermove", (e) => {
      if (e.pointerId !== state.pointer) return;
      e.preventDefault();
      if (this.editing) return this.editMove(el, c, e);
      if (c.type !== "button") this.track(el, c, state, e);
    });
    const end = (e) => {
      if (e.pointerId !== state.pointer) return;
      state.pointer = null;
      if (this.editing) return this.editEnd(el, c, e);
      el.classList.remove("active");
      if (c.type === "button") this.press(c, state, false);
      else this.center(el, c, state);
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("lostpointercapture", end);
    el.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  press(c, state, down) {
    if (c.toggle) { // 토글 버튼: 누를 때마다 눌림/뗌 전환
      if (!down) return;
      state.down = !state.down;
      this.els.get(c.id)?.classList.toggle("latched", state.down);
      this.io.send(c.bind, state.down);
      this.vibrate();
      return;
    }
    if (state.down === down) return;
    state.down = down;
    if (down) this.vibrate();
    this.io.send(c.bind, down);
  }

  track(el, c, state, e) {
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const rad = r.width / 2;
    let dx = (e.clientX - cx) / rad, dy = (e.clientY - cy) / rad;
    const len = Math.hypot(dx, dy);
    if (len > 1) { dx /= len; dy /= len; }
    if (c.type === "stick") {
      const knob = el.firstElementChild;
      if (knob) knob.style.transform = `translate(${dx * rad * 0.55}px, ${dy * rad * 0.55}px)`;
      if (c.mode === "pad-left" || c.mode === "pad-right") {
        const base = c.mode === "pad-left" ? 0 : 2;
        const dead = 0.12;
        const f = (v) => (Math.abs(v) < dead ? 0 : v);
        this.io.axis(base, f(dx));
        this.io.axis(base + 1, f(dy));
        return;
      }
    }
    // 8방향 → 키
    const dirs = new Set();
    const dead = c.type === "dpad" ? 0.22 : 0.35;
    if (Math.hypot(dx, dy) >= dead) {
      const ang = Math.atan2(dy, dx); // 오른쪽 0, 아래 +
      const sector = Math.round(ang / (Math.PI / 4)); // -4..4
      const map = { 0: ["right"], 1: ["right", "down"], 2: ["down"], 3: ["down", "left"], 4: ["left"], "-4": ["left"], "-3": ["left", "up"], "-2": ["up"], "-1": ["up", "right"] };
      (map[sector] || []).forEach((d) => dirs.add(d));
    }
    this.setDirs(el, c, state, dirs);
  }

  setDirs(el, c, state, dirs) {
    const keys = DIR_KEYS[c.mode] || DIR_KEYS.arrows;
    for (const d of state.dirs) if (!dirs.has(d)) this.io.send(keys[d], false);
    let pressed = false;
    for (const d of dirs) if (!state.dirs.has(d)) { this.io.send(keys[d], true); pressed = true; }
    if (pressed) this.vibrate();
    state.dirs = dirs;
    if (c.type === "dpad") for (const d of ["up", "down", "left", "right"]) el.classList.toggle("on-" + d, dirs.has(d));
  }

  center(el, c, state) {
    if (c.type === "stick") {
      const knob = el.firstElementChild;
      if (knob) knob.style.transform = "";
      if (c.mode === "pad-left" || c.mode === "pad-right") {
        const base = c.mode === "pad-left" ? 0 : 2;
        this.io.axis(base, 0);
        this.io.axis(base + 1, 0);
        return;
      }
    }
    this.setDirs(el, c, state, new Set());
  }

  /** 메뉴를 열거나 레이아웃을 바꿀 때 눌린 입력이 남지 않게 모두 뗀다. */
  releaseAll() {
    for (const c of this.layout) {
      const el = this.els.get(c.id);
      const st = el?._state;
      if (!st) continue;
      st.pointer = null;
      el.classList.remove("active", "latched");
      if (c.type === "button") { if (st.down) { st.down = false; this.io.send(c.bind, false); } }
      else this.center(el, c, st);
    }
  }

  /* ───── 편집 ───── */

  setEditing(on) {
    this.releaseAll();
    this.editing = on;
    this.selectedId = null;
    this.render();
  }

  editStart(el, c, e) {
    const st = el._state;
    st.start = { x: e.clientX, y: e.clientY, cx: c.x, cy: c.y };
    st.moved = false;
    this.select(c.id);
  }

  editMove(el, c, e) {
    const st = el._state;
    if (!st.start) return;
    const dx = e.clientX - st.start.x, dy = e.clientY - st.start.y;
    if (!st.moved && Math.hypot(dx, dy) < 6) return;
    st.moved = true;
    c.x = Math.min(0.99, Math.max(0.01, st.start.cx + dx / window.innerWidth));
    c.y = Math.min(0.99, Math.max(0.01, st.start.cy + dy / window.innerHeight));
    this.position();
  }

  editEnd(el, c) {
    const st = el._state;
    st.start = null;
    if (st.moved) this.onChange?.(c);
    else this.onSelect?.(c);
  }

  select(id) {
    this.selectedId = id;
    this.markSelected();
  }

  markSelected() {
    for (const [id, el] of this.els) el.classList.toggle("selected", id === this.selectedId);
  }

  update(id, patch) {
    const c = this.layout.find((x) => x.id === id);
    if (!c) return;
    Object.assign(c, patch);
    this.render();
  }

  remove(id) {
    this.layout = this.layout.filter((x) => x.id !== id);
    this.selectedId = null;
    this.render();
  }

  add(type) {
    const id = `c${Date.now().toString(36)}`;
    const c = type === "button"
      ? { id, type, x: 0.5, y: 0.5, size: 0.15, bind: "key:Space", label: "" }
      : { id, type, x: 0.5, y: 0.5, size: 0.38, mode: "arrows" };
    this.layout.push(c);
    this.selectedId = id;
    this.render();
    return c;
  }
}
