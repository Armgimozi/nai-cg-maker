// art/*.html 의 id 붙은 .asset 요소를 하나씩 투명 PNG 로 찍는다.
//   node tools/render_art.mjs            (blocksuseon 폴더에서)
// 결과: art/out/<id>.png, art/out/manifest.json (크기·SliceCenter)
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

// NODE_PATH 로 전역 playwright 를 찾을 수 있게 require 를 쓴다
const { chromium } = createRequire(import.meta.url)('playwright');

const root = resolve('art');
const out = resolve('art/out');
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
const manifest = {};

for (const file of readdirSync(root).filter((f) => f.endsWith('.html'))) {
  await page.goto('file://' + resolve(root, file), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  const ids = await page.$$eval('.asset[id]', (els) => els.map((e) => e.id));
  for (const id of ids) {
    const el = await page.$('#' + id);
    await el.screenshot({ path: `${out}/${id}.png`, omitBackground: true });
    const info = await el.evaluate((e) => ({
      width: Math.round(e.getBoundingClientRect().width),
      height: Math.round(e.getBoundingClientRect().height),
      slice: e.dataset.slice || null,
      meta: e.dataset.meta ? JSON.parse(e.dataset.meta) : null,
    }));
    manifest[id] = { file: `${id}.png`, source: file, ...info };
  }
}

writeFileSync(`${out}/manifest.json`, JSON.stringify(manifest, null, 2));
await browser.close();
console.log(`${Object.keys(manifest).length} assets → art/out`);
