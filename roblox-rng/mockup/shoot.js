// index.html -> screen1..5.png (+ screen4b.png) + overview.png
//   node mockup/shoot.js            (playwright 가 전역 설치돼 있으면 NODE_PATH=$(npm root -g) 로)
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const HERE = __dirname;
const CHROME = ['/opt/pw-browsers/chromium-1194/chrome-linux/chrome'].find((p) => fs.existsSync(p));

(async () => {
  const browser = await chromium.launch(CHROME ? { executablePath: CHROME } : {});
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  await page.goto('file://' + path.join(HERE, 'index.html') + '?shot=1');
  await page.waitForFunction(() => window.__MOCKUP_READY === true, null, { timeout: 30000 });
  const info = await page.evaluate(() => window.__MOCKUP);
  const shots = [];
  for (const id of info.SHOTS) {
    const file = path.join(HERE, id + '.png');
    await page.locator('#' + id).screenshot({ path: file });
    shots.push({ id, file });
  }
  // 전체 보기: 본 화면 5개를 2열 격자로 줄여서
  const main = shots.filter((s) => /^screen\d$/.test(s.id));
  const titles = { screen1: '1. 기본 화면', screen2: '2. 명소 공개', screen3: '3. 도감', screen4: '4. 여권', screen5: '5. 강화' };
  const cells = main
    .map((s) => `<figure><img src="file://${s.file}"><figcaption>${titles[s.id] || s.id}</figcaption></figure>`)
    .join('');
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{margin:0;background:#24212f;font:600 18px 'KR Fallback','Noto Sans KR',sans-serif;color:#f3efe6}
    .grid{display:grid;grid-template-columns:repeat(2,640px);gap:16px;padding:16px}
    figure{margin:0} img{width:640px;height:360px;display:block;border-radius:6px}
    figcaption{padding:6px 2px 0}</style><div class="grid">${cells}</div>`;
  const overviewPage = await browser.newPage({ viewport: { width: 1312, height: 800 } });
  await overviewPage.setContent(html);
  await overviewPage.waitForLoadState('load');
  await overviewPage.screenshot({ path: path.join(HERE, 'overview.png'), fullPage: true });
  await browser.close();
  console.log(JSON.stringify({ shots: shots.map((s) => path.basename(s.file)), fonts: info.fonts, errors }, null, 1));
})();
