// 맵 미리보기 3단계(노드 쪽): headless Chromium(Playwright)에서 page.html + scene.js(three.js)를 열어 시점별 PNG 저장.
// 사용법(roblox-rng 폴더에서, 보통은 preview.sh 가 부름):
//   NODE_PATH=$(npm root -g) node tools/world_preview/render.js <dump.json> <출력 폴더> <접두어> [시점,시점...]
// 시점: overview, spawn, edge, top (기본: 전부). 파일 이름: <접두어>_<시점>.png (1280x720)
//   임의 시점 "cam:x,y,z:tx,ty,tz[:fov]" 도 됨(파일 이름 <접두어>_cam<순번>.png). 시점은 ';' 로 구분해도 됨
//   "hook" = world.luau hook 이 덤프에 넣은 카메라(extra.Camera, 예: 3D 배치 모드 카메라)
// 환경 변수(선택): PREVIEW_SIZE=667x375 (그림 크기, 기본 1280x720), PREVIEW_JPEG=0.86 (JPEG 품질 → .jpg)
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
      await page.waitForFunction(() => window.previewReady === true, null, { timeout: 30000 });
      const stats = await page.evaluate(() => window.preview.load());
      console.log(
        `[render] 파트 ${stats.parts}개 중 ${stats.drawn}개 그림(묶음 ${stats.groups}), 간판 면 ${stats.gui}개, ` +
          `해 방향 ${JSON.stringify(stats.sun)}, 안개 밀도 ${stats.fog.toFixed(5)}`,
      );
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

  const size = (process.env.PREVIEW_SIZE || "").match(/^(\d+)x(\d+)$/);
  if (size) await page.evaluate(([w, h]) => window.preview.resize(w, h), [Number(size[1]), Number(size[2])]);
  const jpeg = process.env.PREVIEW_JPEG ? Number(process.env.PREVIEW_JPEG) : 0;

  const views = viewArg
    ? viewArg.split(viewArg.includes(";") || viewArg.startsWith("cam:") ? ";" : ",")
    : await page.evaluate(() => window.preview.views);
  for (const view of views) {
    const started = Date.now();
    const dataUrl = await page.evaluate(
      ([v, format, quality]) => window.preview.render(v, format, quality),
      [view, jpeg ? "jpeg" : "png", jpeg || 0.9],
    );
    const label = view.startsWith("cam:") ? "cam" + (views.indexOf(view) + 1) : view;
    const file = path.join(outDir, `${prefix}_${label}.${jpeg ? "jpg" : "png"}`);
    fs.writeFileSync(file, Buffer.from(dataUrl.split(",")[1], "base64"));
    console.log(`[render] ${file} (${((Date.now() - started) / 1000).toFixed(1)}초)`);
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
