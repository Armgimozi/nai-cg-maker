/* 가상 키 목록, 바인딩 문자열, 가상 패드 프리셋.
 *
 * 바인딩 문자열
 *   key:KeyZ            키보드(여러 키 동시: key:ControlLeft+KeyS)
 *   pad:0               게임패드 버튼(표준 배치 번호)
 *   mouse:0 / mouse:2   좌클릭 / 우클릭
 *   wheel:up / wheel:down
 *   menu / text         플레이어 메뉴 / 글자 입력창
 */

export const KEYS = {};

function add(code, key, keyCode, label, extra = {}) {
  KEYS[code] = { code, key, keyCode, label, ...extra };
}

for (let i = 0; i < 26; i++) {
  const up = String.fromCharCode(65 + i);
  const low = up.toLowerCase();
  add("Key" + up, low, 65 + i, up, { char: low });
}
for (let i = 0; i < 10; i++) add("Digit" + i, String(i), 48 + i, String(i), { char: String(i) });
for (let i = 1; i <= 12; i++) add("F" + i, "F" + i, 111 + i, "F" + i);
add("ArrowUp", "ArrowUp", 38, "↑");
add("ArrowDown", "ArrowDown", 40, "↓");
add("ArrowLeft", "ArrowLeft", 37, "←");
add("ArrowRight", "ArrowRight", 39, "→");
add("Enter", "Enter", 13, "Enter");
add("Escape", "Escape", 27, "Esc");
add("Space", " ", 32, "Space", { char: " " });
add("Tab", "Tab", 9, "Tab");
add("Backspace", "Backspace", 8, "⌫");
add("Delete", "Delete", 46, "Del");
add("Insert", "Insert", 45, "Ins");
add("Home", "Home", 36, "Home");
add("End", "End", 35, "End");
add("PageUp", "PageUp", 33, "PgUp");
add("PageDown", "PageDown", 34, "PgDn");
add("ShiftLeft", "Shift", 16, "Shift", { location: 1 });
add("ShiftRight", "Shift", 16, "R-Shift", { location: 2 });
add("ControlLeft", "Control", 17, "Ctrl", { location: 1 });
add("ControlRight", "Control", 17, "R-Ctrl", { location: 2 });
add("AltLeft", "Alt", 18, "Alt", { location: 1 });
add("Minus", "-", 189, "-", { char: "-" });
add("Equal", "=", 187, "=", { char: "=" });
add("BracketLeft", "[", 219, "[", { char: "[" });
add("BracketRight", "]", 221, "]", { char: "]" });
add("Backslash", "\\", 220, "\\", { char: "\\" });
add("Semicolon", ";", 186, ";", { char: ";" });
add("Quote", "'", 222, "'", { char: "'" });
add("Comma", ",", 188, ",", { char: "," });
add("Period", ".", 190, ".", { char: "." });
add("Slash", "/", 191, "/", { char: "/" });
add("Backquote", "`", 192, "`", { char: "`" });
for (let i = 0; i < 10; i++) add("Numpad" + i, String(i), 96 + i, "Num" + i, { char: String(i), location: 3 });
add("NumpadEnter", "Enter", 13, "NumEnter", { location: 3 });

/** 표준 게임패드 버튼 번호 → 이름 */
export const PAD_BUTTONS = [
  "A", "B", "X", "Y", "LB", "RB", "LT", "RT", "Back", "Start", "LS", "RS", "↑", "↓", "←", "→", "Home",
];

export const KEY_GROUPS = [
  ["방향·기본", ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape", "Space", "Tab", "Backspace", "ShiftLeft", "ControlLeft", "AltLeft"]],
  ["문자", Object.keys(KEYS).filter((c) => c.startsWith("Key"))],
  ["숫자", Object.keys(KEYS).filter((c) => c.startsWith("Digit"))],
  ["기능키", Object.keys(KEYS).filter((c) => /^F\d+$/.test(c))],
  ["기타 키", ["Delete", "Insert", "Home", "End", "PageUp", "PageDown", "ShiftRight", "ControlRight", "Minus", "Equal",
    "BracketLeft", "BracketRight", "Backslash", "Semicolon", "Quote", "Comma", "Period", "Slash", "Backquote",
    ...Object.keys(KEYS).filter((c) => c.startsWith("Numpad"))]],
];

export const SPECIAL_BINDINGS = [
  ["mouse:0", "마우스 좌클릭"],
  ["mouse:2", "마우스 우클릭"],
  ["wheel:up", "휠 위로"],
  ["wheel:down", "휠 아래로"],
  ["menu", "플레이어 메뉴"],
  ["text", "글자 입력창"],
];

/** 바인딩 → 버튼에 표시할 기본 이름 */
export function bindingLabel(bind) {
  if (!bind) return "?";
  if (bind.startsWith("key:")) return bind.slice(4).split("+").map((c) => KEYS[c]?.label || c).join("+");
  if (bind.startsWith("pad:")) return PAD_BUTTONS[+bind.slice(4)] || "Pad";
  const sp = SPECIAL_BINDINGS.find(([b]) => b === bind);
  if (bind === "mouse:0") return "좌클릭";
  if (bind === "mouse:2") return "우클릭";
  if (bind === "wheel:up") return "휠↑";
  if (bind === "wheel:down") return "휠↓";
  return sp ? sp[1] : bind;
}

/* ───── 프리셋 ─────
 * x, y: 화면 가로/세로 대비 중심 위치(0~1), size: 화면 짧은 변 대비 지름 비율
 * dpad/stick 의 mode: arrows | wasd | pad(십자키 버튼) | pad-left | pad-right(아날로그)
 */
const btn = (x, y, size, bind, label, extra = {}) => ({ type: "button", x, y, size, bind, label, ...extra });

export const PRESETS = {
  none: { name: "없음 (터치만)", controls: [] },
  rpg: {
    name: "RPG · 어드벤처 (방향키 + Z/X)",
    controls: [
      { type: "dpad", x: 0.14, y: 0.7, size: 0.4, mode: "arrows" },
      btn(0.89, 0.72, 0.18, "key:KeyZ", "확인"),
      btn(0.76, 0.85, 0.15, "key:KeyX", "취소"),
      btn(0.76, 0.58, 0.13, "key:ShiftLeft", "대시"),
      btn(0.93, 0.1, 0.11, "key:Escape", "Esc", { shape: "pill" }),
    ],
  },
  action: {
    name: "액션 · 플랫포머 (WASD + 점프)",
    controls: [
      { type: "stick", x: 0.15, y: 0.7, size: 0.42, mode: "wasd" },
      btn(0.89, 0.74, 0.19, "key:Space", "점프"),
      btn(0.76, 0.86, 0.14, "key:ShiftLeft", "달리기"),
      btn(0.76, 0.6, 0.14, "key:KeyE", "E"),
      btn(0.9, 0.5, 0.13, "mouse:0", "공격"),
      btn(0.93, 0.1, 0.11, "key:Escape", "Esc", { shape: "pill" }),
    ],
  },
  arrows: {
    name: "방향키 + Z/X/C + Space",
    controls: [
      { type: "stick", x: 0.15, y: 0.7, size: 0.42, mode: "arrows" },
      btn(0.9, 0.78, 0.16, "key:KeyZ", "Z"),
      btn(0.78, 0.86, 0.14, "key:KeyX", "X"),
      btn(0.78, 0.64, 0.14, "key:KeyC", "C"),
      btn(0.9, 0.56, 0.14, "key:Space", "Space"),
      btn(0.93, 0.1, 0.11, "key:Escape", "Esc", { shape: "pill" }),
      btn(0.07, 0.1, 0.11, "key:Enter", "Enter", { shape: "pill" }),
    ],
  },
  gamepad: {
    name: "게임패드 (아날로그 스틱 + ABXY)",
    controls: [
      { type: "stick", x: 0.15, y: 0.68, size: 0.42, mode: "pad-left" },
      btn(0.88, 0.82, 0.15, "pad:0", "A"),
      btn(0.95, 0.66, 0.15, "pad:1", "B"),
      btn(0.81, 0.66, 0.15, "pad:2", "X"),
      btn(0.88, 0.5, 0.15, "pad:3", "Y"),
      btn(0.07, 0.14, 0.11, "pad:4", "LB", { shape: "pill" }),
      btn(0.19, 0.14, 0.11, "pad:6", "LT", { shape: "pill" }),
      btn(0.81, 0.14, 0.11, "pad:7", "RT", { shape: "pill" }),
      btn(0.93, 0.14, 0.11, "pad:5", "RB", { shape: "pill" }),
      btn(0.44, 0.9, 0.1, "pad:8", "Back", { shape: "pill" }),
      btn(0.56, 0.9, 0.1, "pad:9", "Start", { shape: "pill" }),
    ],
  },
  vn: {
    name: "비주얼노벨 (스킵·로그·우클릭)",
    controls: [
      btn(0.94, 0.3, 0.12, "wheel:up", "로그", { shape: "pill" }),
      btn(0.94, 0.45, 0.12, "key:ControlLeft", "스킵", { shape: "pill" }),
      btn(0.94, 0.6, 0.12, "mouse:2", "우클릭", { shape: "pill" }),
      btn(0.94, 0.75, 0.12, "key:Space", "다음", { shape: "pill" }),
    ],
  },
  // 티라노스크립트 기본 키: Enter=다음, Ctrl=누르는 동안 스킵, 휠↑=백로그, 우클릭=메시지 숨기기
  // (Space 는 다음이 아니라 메시지 숨기기라 vn 프리셋 대신 따로 둔다)
  tyrano: {
    name: "티라노스크립트 (로그·스킵·숨기기)",
    controls: [
      btn(0.94, 0.3, 0.12, "wheel:up", "로그", { shape: "pill" }),
      btn(0.94, 0.45, 0.12, "key:ControlLeft", "스킵", { shape: "pill" }),
      btn(0.94, 0.6, 0.12, "mouse:2", "숨기기", { shape: "pill" }),
      btn(0.94, 0.75, 0.12, "key:Enter", "다음", { shape: "pill" }),
    ],
  },
  mouse: {
    name: "마우스 보조 (우클릭·휠·Esc)",
    controls: [
      btn(0.94, 0.35, 0.12, "mouse:2", "우클릭", { shape: "pill" }),
      btn(0.94, 0.5, 0.12, "wheel:up", "휠↑", { shape: "pill" }),
      btn(0.94, 0.65, 0.12, "wheel:down", "휠↓", { shape: "pill" }),
      btn(0.94, 0.1, 0.11, "key:Escape", "Esc", { shape: "pill" }),
    ],
  },
};

/** 게임 종류에 맞는 기본 프리셋 */
export function autoPreset(kind) {
  if (kind === "rpgmv" || kind === "rpgmz") return "rpg";
  return "none";
}

export function presetLayout(name) {
  const p = PRESETS[name] || PRESETS.none;
  return p.controls.map((c, i) => ({ id: `${name}-${i}`, ...c }));
}

/** 레이아웃에 게임패드 바인딩이 있으면 가상 패드를 처음부터 연결해 둔다 */
export function layoutUsesPad(layout) {
  return (layout || []).some((c) => (c.bind || "").startsWith("pad:") || /^pad/.test(c.mode || ""));
}
