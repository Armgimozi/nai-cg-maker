/* PC 빌드 진단 결과 화면 — "모바일로 바꿀 수 있을까?" */

import { h, sheet, toast } from "./ui.js";
import { formatBytes } from "./db.js";

const ODDS = {
  good: ["가능성 높음", "good"],
  possible: ["해 볼 만함", "possible"],
  hard: ["어려움", "hard"],
  no: ["사실상 불가", "no"],
};

const BACKEND = {
  mono: ["Mono", "C# 코드가 DLL 로 남아 있음 → 디컴파일로 복원 가능"],
  il2cpp: ["IL2CPP", "C# 코드가 PC용 기계어(네이티브 코드)로 컴파일됨 → 코드 복원 불가"],
  unknown: ["알 수 없음", "스크립트 파일을 찾지 못했습니다"],
};

const PLATFORM = { windows: "Windows", mac: "macOS", linux: "Linux", unknown: "PC" };

function shaderNote(r) {
  if (r.mobileShaders) return "모바일용(OpenGL ES) 셰이더 있음";
  if (r.nonD3DShaders) return "Direct3D 외 셰이더 있음(데스크톱용)";
  return "모바일용 셰이더 없음(Direct3D 전용)";
}

/** 지금 이 폰의 GPU 이름(WEBGL_debug_renderer_info). 브라우저가 숨기면 null. */
export function deviceGpu() {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
    const name = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return name ? String(name) : null;
  } catch { return null; }
}

/** GPU 이름 → Winlator 그래픽 드라이버 추천 */
export function driverAdvice(gpu) {
  if (!gpu) return null;
  if (/adreno/i.test(gpu)) return `이 폰의 GPU: ${gpu}(스냅드래곤) → Winlator 에서 Turnip 드라이버를 고르세요. 가장 잘 되는 조합입니다.`;
  if (/mali|xclipse|immortalis|powervr|maleoon/i.test(gpu)) {
    return `이 폰의 GPU: ${gpu} → Turnip 을 쓸 수 없어 Vortek(실험적) 드라이버를 써야 합니다. 잘 안 되면 GameNative 도 시도해 보세요.`;
  }
  return null;
}

/** 개발자에게 보낼 요청문(한국어 + 영어) */
export function developerRequest(r) {
  const name = r.gameName || "이 게임";
  return [
    `안녕하세요. ${name} 을(를) 휴대폰에서 즐기고 싶어 문의드립니다.`,
    "혹시 브라우저용(WebGL) 또는 안드로이드 버전을 받아 볼 수 있을까요?",
    "• WebGL: 가능하면 Unity 6 이상, 압축은 Gzip 또는 끄기, Development Build 끔 — zip 으로 주시면 폰의 UniPlay 앱에서 바로 실행됩니다.",
    "• Android: Scripting Backend IL2CPP, ARM64, Target API 24 이상의 APK.",
    r.unityVersion ? `(참고: 현재 PC 빌드는 Unity ${r.unityVersion}, ${r.backend === "il2cpp" ? "IL2CPP" : r.backend === "mono" ? "Mono" : "백엔드 미확인"} 빌드입니다.)` : "",
    "",
    `Hello! I'd love to play ${r.gameName || "your game"} on my phone. Would you consider sharing a WebGL build`,
    "(ideally Unity 6+, Gzip or no compression, Development Build off) or an Android APK (IL2CPP, ARM64, target API 24+)?",
    r.unityVersion ? `For reference, the PC build I have is Unity ${r.unityVersion}.` : "",
    "Thank you!",
  ].filter((x) => x !== "").join("\n");
}

/** 공유·복사용 텍스트 */
export function reportText(r) {
  const lines = [
    `[UniPlay 변환 진단] ${r.gameName}`,
    `플랫폼: ${PLATFORM[r.platform]}${r.targetName ? ` (${r.targetName})` : ""}`,
    `유니티 버전: ${r.unityVersion || "알 수 없음"}`,
    `스크립트: ${BACKEND[r.backend][0]}${r.scriptBytes ? ` (게임 코드 ${formatBytes(r.scriptBytes)})` : ""}`,
    ...(r.graphicsAPIs ? [`그래픽 API: ${r.graphicsAPIs.join(", ")} — ${shaderNote(r)}`] : []),
    `용량: ${formatBytes(r.totalBytes)} · 파일 ${r.fileCount}개`,
  ];
  if (r.features.length) lines.push(`특징: ${r.features.map((f) => f.name).join(", ")}`);
  if (r.nativePlugins.length) lines.push(`네이티브 플러그인: ${r.nativePlugins.join(", ")}`);
  lines.push("");
  for (const x of r.routes) {
    lines.push(`■ ${x.title} — ${ODDS[x.odds][0]}`);
    lines.push(`  ${x.summary}`);
    (x.steps || []).forEach((s, i) => lines.push(`  ${i + 1}. ${s}`));
    (x.links || []).forEach(([label, url]) => lines.push(`  - ${label}: ${url}`));
  }
  return lines.join("\n");
}

function linkRow(links) {
  return links?.length ? h("p", { class: "links" }, links.map(([label, url]) => h("a", { href: url, target: "_blank", rel: "noopener" }, label))) : null;
}

function copy(text, done) {
  if (!navigator.clipboard?.writeText) { toast("이 브라우저에서는 복사할 수 없습니다."); return; }
  navigator.clipboard.writeText(text).then(() => toast(done), () => toast("복사하지 못했습니다."));
}

export function showPortingReport(r, { title } = {}) {
  const chip = (f) => h("span", { class: `chip ${f.level}`, title: f.note }, f.name);
  const facts = h("dl", { class: "facts" },
    h("dt", {}, "플랫폼"), h("dd", {}, `${PLATFORM[r.platform]}${r.targetName ? ` · ${r.targetName}` : ""}`),
    h("dt", {}, "유니티"), h("dd", {}, r.unityVersion || "알 수 없음"),
    r.company && r.company !== "DefaultCompany" ? [h("dt", {}, "제작"), h("dd", {}, r.company)] : null,
    h("dt", {}, "스크립트"), h("dd", {}, h("b", {}, BACKEND[r.backend][0]), " — ", BACKEND[r.backend][1]),
    r.graphicsAPIs ? [h("dt", {}, "그래픽"), h("dd", {}, r.graphicsAPIs.join(" · "), " — ", shaderNote(r))] : null,
    r.arch ? [h("dt", {}, "CPU"), h("dd", {}, { x86: "x86 (32비트)", x64: "x64 (64비트)", arm64: "ARM64" }[r.arch])] : null,
    r.scriptBytes ? [h("dt", {}, "게임 코드"), h("dd", {}, formatBytes(r.scriptBytes))] : null,
    h("dt", {}, "용량"), h("dd", {}, `${formatBytes(r.totalBytes)} · 파일 ${r.fileCount.toLocaleString()}개`));

  const notes = [
    ...r.features.filter((f) => f.level !== "info"),
    ...(r.nativePlugins.length ? [{ level: "warn", name: "네이티브 플러그인", note: `${r.nativePlugins.join(", ")} — PC(데스크톱) 전용 네이티브 라이브러리라 모바일용으로 바꾸거나 빼야 합니다.` }] : []),
    ...(r.modded ? [{ level: "info", name: "모드 로더", note: "BepInEx/MelonLoader 모드가 설치돼 있습니다." }] : []),
  ];

  const gpuTip = driverAdvice(deviceGpu());
  const routes = r.routes.map((x) => h("section", { class: `route ${ODDS[x.odds][1]}` },
    h("div", { class: "route-head" }, h("h4", {}, x.title), h("span", { class: `odds ${ODDS[x.odds][1]}` }, ODDS[x.odds][0])),
    h("p", {}, x.summary),
    x.key === "emulate" && x.odds !== "no" && gpuTip ? h("p", { class: "tip" }, "📱 ", gpuTip) : null,
    x.key === "source" ? h("div", { class: "row-actions" },
      h("button", { class: "btn small", onclick: () => copy(developerRequest(r), "개발자에게 보낼 요청문을 복사했습니다.") }, "개발자에게 보낼 요청문 복사")) : null,
    x.steps?.length ? h("details", {},
      h("summary", {}, "방법 보기"),
      h("ol", {}, x.steps.map((s) => h("li", {}, s))),
      linkRow(x.links)) : linkRow(x.links)));

  const body = h("div", { class: "porting" },
    h("p", { class: "lead" }, `${PLATFORM[r.platform]}용 유니티 게임이에요. 이 앱은 PC용 빌드를 직접 실행할 수 없지만, 파일을 살펴 모바일로 옮길 수 있는지 진단했어요.`),
    facts,
    r.features.length ? h("div", { class: "chips" }, r.features.map(chip)) : null,
    notes.length ? h("ul", { class: "notes-list" }, notes.map((f) => h("li", { class: f.level }, h("b", {}, f.name), " — ", f.note))) : null,
    h("h4", {}, "방법별 가능성"),
    routes,
    h("div", { class: "row-actions" },
      h("button", { class: "btn", onclick: () => copy(reportText(r), "진단 결과를 복사했습니다.") }, "진단 결과 복사")),
    h("p", { class: "hint" }, "다른 사람이 만든 게임을 변환·배포하는 것은 저작권 문제가 될 수 있어요. 개인적으로 즐기는 범위에서, 가능하면 개발자에게 먼저 문의하세요."));
  return sheet(title || `${r.gameName} — 모바일 변환 진단`, body, { wide: true });
}
