// 맵 미리보기 3단계(노드 쪽): headless Chromium(Playwright)에서 page.html + scene.js(three.js)를 열어 시점별 PNG 저장.
// 사용법(roblox-rng 폴더에서, 보통은 preview.sh 가 부름):
//   NODE_PATH=$(npm root -g) node tools/world_preview/render.js <dump.json> <출력 폴더> <접두어> [시점,시점...]
// 시점: overview, spawn, edge, beach, closeup, top (기본: 이 여섯). 파일 이름: <접두어>_<시점>.png (1280x720)
//   점검 장면(WORLD=test)의 기본은 overview, samples, shore, hill, top
// 환경 변수: FOAM=1 (물가 거품 — Roblox 에는 없음, 비교용), GAP=1~8 (closeup 이 볼 부지 사이 틈),
//   TERRAIN_DEBUG=1 (지형을 재질별 가짜 색으로: Grass 초록, LeafyGrass 파랑, Sand 노랑 ... terrain.js DEBUG_COLORS)
//   임의 시점 "cam:x,y,z:tx,ty,tz[:fov]" 도 됨(파일 이름 <접두어>_cam<순번>.png). 시점은 ';' 로 구분해도 됨
// 페이지 파일은 http://preview.local/ 가짜 주소로 열고, 요청을 page.route 로 디스크 파일에 연결합니다
// (/node_modules → tools/world_preview/node_modules, /art/png → art/png, /fonts → mockup/fonts, /dump.json → 덤프).

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "../..");
const HERE = __dirname;
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".png": "image/png",
  ".woff2": "font/woff2",
};

function fileFor(urlPath, dumpPath) {
  if (urlPath === "/dump.json") return dumpPath;
  if (urlPath.startsWith("/art/png/")) return path.join(ROOT, "art/png", path.basename(urlPath));
  if (urlPath.startsWith("/fonts/")) return path.join(ROOT, "mockup/fonts", path.basename(urlPath));
  const local = path.normalize(path.join(HERE, urlPath));
  return local.startsWith(HERE) ? local : null;
}

async function main() {
  const [dumpPath, outDir, prefix = "map", viewArg] = process.argv.slice(2);
  if (!dumpPath || !outDir) {
    console.error("사용법: node render.js <dump.json> <출력 폴더> <접두어> [시점,...]");
    process.exit(2);
  }
  fs.mkdirSync(outDir, { recursive: true });

  const launch = (args) => chromium.launch({ executablePath: CHROME, args });
  // GPU 가 없으니 SwiftShader(소프트웨어 WebGL). 첫 시도가 안 되면 다른 플래그로
  const flagSets = [
    ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
    ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  ];
  let browser = null;
  let page = null;
  let lastError = null;
  for (const flags of flagSets) {
    browser = await launch(flags);
    page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => {
      if (m.type() === "error" || m.type() === "warning") errors.push(m.text());
    });
    await page.route("http://preview.local/**", async (route) => {
      const url = new URL(route.request().url());
      const file = fileFor(decodeURIComponent(url.pathname), path.resolve(dumpPath));
      if (!file || !fs.existsSync(file)) return route.fulfill({ status: 404, body: "not found" });
      const type = TYPES[path.extname(file)] || "application/octet-stream";
      return route.fulfill({ status: 200, contentType: type, body: fs.readFileSync(file) });
    });
    await page.goto("http://preview.local/page.html");
    try {
      await page.waitForFunction(() => window.previewReady === true, null, { timeout: 60000 });
      const flag = (name) => !!process.env[name] && process.env[name] !== "0";
      const opts = { foam: flag("FOAM"), gap: Number(process.env.GAP) || 2, debug: flag("TERRAIN_DEBUG") };
      const stats = await page.evaluate((o) => window.preview.load(o), opts);
      console.log(
        `[render] 파트 ${stats.parts}개 중 ${stats.drawn}개 그림(묶음 ${stats.groups}), 간판 면 ${stats.gui}개, ` +
          `해 방향 ${JSON.stringify(stats.sun)}, 안개 밀도 ${stats.fog.toFixed(5)}, 재질 텍스처 ${stats.textureMs}ms`,
      );
      if (stats.terrain) {
        const t = stats.terrain;
        console.log(
          `[render] 지형: 땅 삼각형 ${t.triangles}개, 물 삼각형 ${t.waterTriangles}개, 자세한 타일 ${t.tiles}개, ` +
            `풀 장식 ${t.decoration ? "켬" : "끔"}, 섬 반지름(시점용) ${stats.frame}${opts.foam ? ", 거품 켬(FOAM=1)" : ""}`,
        );
      }
      for (const e of errors) console.log("[render] 페이지 경고: " + e);
      lastError = null;
      break;
    } catch (e) {
      lastError = `${e}\n${errors.join("\n")}`;
      await browser.close();
      browser = null;
    }
  }
  if (!browser) {
    console.error("[render] WebGL 페이지를 열지 못했습니다:\n" + lastError);
    process.exit(1);
  }

  const views = viewArg
    ? viewArg.split(viewArg.includes(";") || viewArg.startsWith("cam:") ? ";" : ",")
    : await page.evaluate(() => window.preview.views);
  for (const view of views) {
    const started = Date.now();
    const dataUrl = await page.evaluate((v) => window.preview.render(v), view);
    const label = view.startsWith("cam:") ? "cam" + (views.indexOf(view) + 1) : view;
    const file = path.join(outDir, `${prefix}_${label}.png`);
    fs.writeFileSync(file, Buffer.from(dataUrl.split(",")[1], "base64"));
    console.log(`[render] ${file} (${((Date.now() - started) / 1000).toFixed(1)}초)`);
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
