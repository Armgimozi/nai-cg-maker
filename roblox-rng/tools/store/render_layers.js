// 스토어 그림용 3D 레이어 렌더러: 맵 미리보기 덤프(world.luau + stage_hook.luau)를 같은 카메라로 여러 번 그려서
// 합성용 레이어 PNG 를 만듭니다(배경 = 지형·풍경만, 주인공 = 명소 모형만, 아바타만 ...). three.js 장면은 맵 미리보기
// tools/world_preview/scene.js 를 그대로 씀(page.html?alpha = 하늘 없이 투명 배경 + 그림자만 받는 판).
//
// 사용법(roblox-rng 폴더에서, 보통은 tools/store/thumbs.py 가 부름):
//   NODE_PATH=$(npm root -g) node tools/store/render_layers.js <dump.json> <spec.json> <출력 폴더>
// spec.json = {
//   "size": [1920, 1080],                    그림 크기(크게 그린 뒤 줄이면 가장자리가 매끈)
//   "cam": "cam:x,y,z:tx,ty,tz:fov",           모든 레이어가 같은 카메라(scene.js customView)
//   "layers": [ {
//     "name": "bg",                            → <출력 폴더>/<name>.png
//     "alpha": true,                           하늘 없이 투명 배경(false 면 scene.js 하늘까지)
//     "terrain": true,                         지형(땅·물·풀) 포함 여부
//     "include": ["Store/Hero"],               이 경로로 시작하는 파트만(없으면 모두)
//     "exclude": ["Store"],                    이 경로로 시작하는 파트는 뺌
//     "clear": { "until": 90, "margin": 1.3 }, 카메라 앞 until 스터드 안쪽, 화면 폭 margin 배 안의 파트는 뺌(시야 청소)
//     "shadow": { "x":0, "y":0, "z":0, "size":200, "opacity":0.35 }  그림자만 받는 판
//   } ]
// }
// 페이지 파일은 render.js 와 같은 방식(http://preview.local/ 가짜 주소 → 디스크 파일)으로 엽니다.

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "../..");
const PREVIEW = path.join(ROOT, "tools/world_preview");
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
  const local = path.normalize(path.join(PREVIEW, urlPath));
  return local.startsWith(PREVIEW) ? local : null;
}

// 카메라 공간: 앞(깊이)·오른쪽·위 성분
function cameraBasis(cam) {
  const [, eye, target, fov] = cam.split(":");
  const e = eye.split(",").map(Number);
  const t = target.split(",").map(Number);
  const f = t.map((v, i) => v - e[i]);
  const fl = Math.hypot(...f);
  const fw = f.map((v) => v / fl);
  let r = [-fw[2], 0, fw[0]]; // 오른쪽 = cross(앞, 위(0,1,0))
  const rl = Math.hypot(...r) || 1;
  r = r.map((v) => v / rl);
  return { e, fw, r, fov: Number(fov) || 60 };
}

// 레이어에 넣을지: 경로(include/exclude) + 시야 청소(clear). pos = 중심, radius = 대략 반지름
function keeper(layer, cam, aspect) {
  const include = layer.include || null;
  const exclude = layer.exclude || [];
  const starts = (p, list) => list.some((prefix) => p === prefix || p.startsWith(prefix + "/"));
  const basis = layer.clear ? cameraBasis(cam) : null;
  return (p, pos, radius) => {
    if (include && !starts(p, include)) return false;
    if (starts(p, exclude)) return false;
    if (basis) {
      const d = pos.map((v, k) => v - basis.e[k]);
      const depth = d[0] * basis.fw[0] + d[1] * basis.fw[1] + d[2] * basis.fw[2];
      const side = d[0] * basis.r[0] + d[2] * basis.r[2];
      const halfW = Math.tan((basis.fov * Math.PI) / 360) * aspect * Math.max(depth, 0) * (layer.clear.margin || 1.3);
      if (depth > -radius && depth < layer.clear.until && Math.abs(side) < halfW + radius) return false;
    }
    return true;
  };
}

async function main() {
  const [dumpPath, specPath, outDir] = process.argv.slice(2);
  if (!dumpPath || !specPath || !outDir) {
    console.error("사용법: node render_layers.js <dump.json> <spec.json> <출력 폴더>");
    process.exit(2);
  }
  fs.mkdirSync(outDir, { recursive: true });
  const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  const [W, H] = spec.size || [1920, 1080];
  const browser = await chromium.launch({
    executablePath: CHROME,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
  for (const layer of spec.layers) {
    const started = Date.now();
    const keep = keeper(layer, spec.cam, W / H);
    const parts = dump.parts.filter((part) => keep(part.path || "", part.p, Math.max(...part.z) / 2));
    const layerDump = {
      ...dump,
      parts,
      terrain: layer.terrain ? dump.terrain : null,
      gui: (dump.gui || []).filter((g) => keep(g.path || "", g.center, Math.max(g.w || 0, g.h || 0) / 2)),
      hl: [], // 강조(Highlight)는 스토어 그림에 안 씀
    };
    const tmp = path.join(outDir, `.${layer.name}_dump.json`);
    fs.writeFileSync(tmp, JSON.stringify(layerDump));
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.route("http://preview.local/**", async (route) => {
      const url = new URL(route.request().url());
      const file = fileFor(decodeURIComponent(url.pathname), tmp);
      if (!file || !fs.existsSync(file)) return route.fulfill({ status: 404, body: "not found" });
      const type = TYPES[path.extname(file)] || "application/octet-stream";
      return route.fulfill({ status: 200, contentType: type, body: fs.readFileSync(file) });
    });
    await page.goto(`http://preview.local/page.html${layer.alpha === false ? "" : "?alpha"}`);
    await page.waitForFunction(() => window.previewReady === true, null, { timeout: 60000 });
    const stats = await page.evaluate((o) => window.preview.load(o), { gap: 2, shadowCatcher: layer.shadow || null });
    await page.evaluate(([w, h]) => window.preview.resize(w, h), [W, H]);
    const dataUrl = await page.evaluate((cam) => window.preview.render(cam, "png"), spec.cam);
    const file = path.join(outDir, `${layer.name}.png`);
    fs.writeFileSync(file, Buffer.from(dataUrl.split(",")[1], "base64"));
    fs.unlinkSync(tmp);
    await page.close();
    for (const e of errors) console.log(`[layers] ${layer.name} 페이지 오류: ${e}`);
    console.log(
      `[layers] ${file} 파트 ${stats.drawn}/${dump.parts.length} (${((Date.now() - started) / 1000).toFixed(1)}초)`,
    );
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
