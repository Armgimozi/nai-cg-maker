// 스토어 그림 3D 층 렌더러(노드 쪽): headless Chromium(Playwright, SwiftShader)에서 scene3d.html 을 열고
// 장면 JSON 의 층마다 투명 배경 PNG 를 저장합니다. 3D 점을 화면 좌표로 바꾼 값도 JSON 으로 남김(합성용).
// 사용법(아무 폴더에서나): NODE_PATH=$(npm root -g) node tools/store/render3d.js <scene.json> <출력 폴더>
//   → <출력 폴더>/<층 이름>.png ..., <출력 폴더>/project.json (scene.project 의 점들 → [x, y, 깊이])
// 페이지 파일은 http://store.local/ 가짜 주소로 열고 요청을 디스크 파일로 돌려줌:
//   /node_modules → tools/world_preview/node_modules, /wp/ → tools/world_preview/, /file/<절대경로> → 그 파일
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "../..");
const HERE = __dirname;
const WP = path.join(ROOT, "tools/world_preview");
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".json": "application/json", ".png": "image/png" };

function fileFor(p) {
  if (p.startsWith("/file/")) return p.slice(5);
  if (p.startsWith("/node_modules/")) return path.join(WP, p);
  if (p.startsWith("/wp/")) return path.join(WP, p.slice(4));
  const local = path.normalize(path.join(HERE, p));
  return local.startsWith(HERE) ? local : null;
}

async function main() {
  const [scenePath, outDir] = process.argv.slice(2);
  if (!scenePath || !outDir) {
    console.error("사용법: node render3d.js <scene.json> <출력 폴더>");
    process.exit(2);
  }
  const spec = JSON.parse(fs.readFileSync(scenePath, "utf8"));
  fs.mkdirSync(outDir, { recursive: true });
  const [W, H] = spec.size || [1024, 1024];
  const flagSets = [
    ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
    ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  ];
  let browser = null;
  let page = null;
  let lastError = "";
  for (const flags of flagSets) {
    browser = await chromium.launch({ executablePath: CHROME, args: flags });
    page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.route("http://store.local/**", async (route) => {
      const url = new URL(route.request().url());
      const file = fileFor(decodeURIComponent(url.pathname));
      if (!file || !fs.existsSync(file)) return route.fulfill({ status: 404, body: "not found" });
      const type = TYPES[path.extname(file)] || "application/octet-stream";
      return route.fulfill({ status: 200, contentType: type, body: fs.readFileSync(file) });
    });
    await page.goto("http://store.local/scene3d.html");
    try {
      await page.waitForFunction(() => window.storeReady === true, null, { timeout: 60000 });
      const info = await page.evaluate((s) => window.store.load(s), spec);
      console.log(`[render3d] 물체 ${info.objects}개, 층 ${info.layers.join(", ")}`);
      for (const e of errors) console.log("[render3d] 페이지 경고: " + e);
      break;
    } catch (e) {
      lastError = `${e}\n${errors.join("\n")}`;
      await browser.close();
      browser = null;
    }
  }
  if (!browser) {
    console.error("[render3d] WebGL 페이지를 열지 못했습니다:\n" + lastError);
    process.exit(1);
  }
  for (const layer of spec.layers) {
    const t0 = Date.now();
    const dataUrl = await page.evaluate((n) => window.store.render(n), layer.name);
    const file = path.join(outDir, `${layer.name}.png`);
    fs.writeFileSync(file, Buffer.from(dataUrl.split(",")[1], "base64"));
    console.log(`[render3d] ${file} (${((Date.now() - t0) / 1000).toFixed(1)}초)`);
  }
  if (spec.project) {
    const pts = await page.evaluate((p) => window.store.project(p), spec.project);
    fs.writeFileSync(path.join(outDir, "project.json"), JSON.stringify(pts));
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
