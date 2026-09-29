// index.html -> screen1..5.png (+ screen1t/1p = 태블릿·휴대폰 크기, screen2b.png, screen4b.png) + overview.png
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
  // 전체 보기: 화면 5개 + 여권 펼침을 2열 격자로 줄여서 (그림은 data URI 로 넣음)
  const titles = {
    screen1: '1. 기본 화면', screen1t: '1-2. 기본 화면 (태블릿 1024×768)', screen1p: '1-3. 기본 화면 (휴대폰 667×375)',
    screen2: '2. 명소 공개 (처음 발견)', screen2b: '2-2. 명소 공개 (별 오름)', screen3: '3. 도감',
    screen4: '4. 여권', screen5: '5. 강화', screen4b: '4-2. 여권 스크롤 내용 전체',
  };
  const order = ['screen1', 'screen1t', 'screen1p', 'screen2', 'screen2b', 'screen3', 'screen4', 'screen5', 'screen4b'];
  const cells = order
    .map((id) => shots.find((s) => s.id === id))
    .filter(Boolean)
    .map((s) => {
      const uri = 'data:image/png;base64,' + fs.readFileSync(s.file).toString('base64');
      return `<figure><div class="cell"><img src="${uri}"></div><figcaption>${titles[s.id] || s.id}</figcaption></figure>`;
    })
    .join('');
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{margin:0;background:#24212f;font:600 18px 'KR Fallback','Noto Sans KR',sans-serif;color:#f3efe6}
    .grid{display:grid;grid-template-columns:repeat(2,640px);gap:16px;padding:16px}
    figure{margin:0} .cell{width:640px;height:360px;display:flex;justify-content:center;background:#1a1824;border-radius:6px;overflow:hidden}
    .cell img{max-width:640px;max-height:360px;display:block}
    figcaption{padding:6px 2px 0}</style><div class="grid">${cells}</div>`;
  const overviewPage = await browser.newPage({ viewport: { width: 1312, height: 800 } });
  await overviewPage.setContent(html);
  await overviewPage.waitForLoadState('load');
  await overviewPage.screenshot({ path: path.join(HERE, 'overview.png'), fullPage: true });
  await browser.close();
  const checks = (info.findings || []).map((t) => t.replace(/<[^>]+>/g, ''));
  console.log(JSON.stringify({ shots: shots.map((s) => path.basename(s.file)), fonts: info.fonts, checks, errors }, null, 1));
})();
