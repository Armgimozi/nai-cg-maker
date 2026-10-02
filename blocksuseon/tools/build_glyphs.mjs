// HUD 비트맵 글꼴 아틀라스 만들기.   node tools/build_glyphs.mjs   (blocksuseon 폴더에서, fetch_fonts.py 다음)
//
// art/fonts/charset.txt 의 글자를 글꼴별로 흰 글자 + 진한 테두리로 그려 1024px 이하 페이지에 채운다.
// 런타임에 ImageColor3/UIGradient 로 곱해서 색을 입히므로, 흰 부분은 원하는 색이 되고 테두리는 어둡게 남는다.
// 결과: art/out/glyphs_<글꼴>_<페이지>.png, art/out/glyphs.json
import { createRequire } from 'node:module';
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const { chromium } = createRequire(import.meta.url)('playwright');

const FONTS = {
  // size: 아틀라스에 그리는 픽셀 크기, outline: 테두리 두께(px)
  body: { prefix: 'body_', size: 34, outline: 3.2 },
  title: { prefix: 'title_', size: 54, outline: 4.5 },
};
const PAGE = 1024;

const fontDir = resolve('art/fonts');
const outDir = resolve('art/out');
mkdirSync(outDir, { recursive: true });
const charset = [...readFileSync(`${fontDir}/charset.txt`, 'utf8')];

const faces = [];
const families = {};
for (const [name, cfg] of Object.entries(FONTS)) {
  const files = readdirSync(fontDir).filter((f) => f.startsWith(cfg.prefix) && f.endsWith('.woff2')).sort();
  families[name] = files.map((f, i) => {
    const family = `${name}${i}`;
    // about:blank 에서는 file:// 글꼴을 못 읽으므로 data URL 로 넣는다
    const data = readFileSync(`${fontDir}/${f}`).toString('base64');
    faces.push(`@font-face{font-family:'${family}';src:url(data:font/woff2;base64,${data}) format('woff2');}`);
    return `'${family}'`;
  });
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage();
await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${faces.join('\n')}</style></head><body></body></html>`);

const result = await page.evaluate(async ({ FONTS, families, charset, PAGE }) => {
  const fonts = {};
  for (const [name, cfg] of Object.entries(FONTS)) {
    const fontCss = `${cfg.size}px ${families[name].join(', ')}`;
    await document.fonts.load(fontCss, charset.join(''));

    const probe = document.createElement('canvas').getContext('2d');
    probe.font = fontCss;
    const ref = probe.measureText('가Hg');
    const ascent = Math.ceil(ref.fontBoundingBoxAscent);
    const descent = Math.ceil(ref.fontBoundingBoxDescent);
    const pad = Math.ceil(cfg.outline) + 2;
    const cellH = ascent + descent + pad * 2;

    const pages = [];
    const glyphs = {};
    let canvas, ctx, x = 0, y = 0;
    const newPage = () => {
      canvas = document.createElement('canvas');
      canvas.width = PAGE;
      canvas.height = PAGE;
      ctx = canvas.getContext('2d');
      ctx.font = fontCss;
      ctx.textBaseline = 'alphabetic';
      ctx.lineJoin = 'round';
      ctx.miterLimit = 2;
      pages.push({ canvas, used: 0 });
      x = 0;
      y = 0;
    };
    newPage();

    for (const ch of charset) {
      const adv = probe.measureText(ch).width;
      if (ch === ' ') {
        glyphs[ch] = [0, 0, 0, 0, 0, Math.round(adv * 100) / 100];
        continue;
      }
      const w = Math.ceil(adv) + pad * 2;
      if (x + w > PAGE) {
        x = 0;
        y += cellH;
      }
      if (y + cellH > PAGE) newPage();
      ctx.lineWidth = cfg.outline * 2;
      ctx.strokeStyle = '#1b150d';
      ctx.strokeText(ch, x + pad, y + pad + ascent);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(ch, x + pad, y + pad + ascent);
      glyphs[ch] = [pages.length - 1, x, y, w, cellH, Math.round(adv * 100) / 100];
      pages[pages.length - 1].used = y + cellH;
      x += w;
    }

    fonts[name] = {
      size: cfg.size,
      pad,
      lineHeight: ascent + descent,
      pages: pages.map((p) => {
        // 쓴 높이까지만 잘라 낸다
        const cut = document.createElement('canvas');
        cut.width = PAGE;
        cut.height = Math.max(1, p.used);
        cut.getContext('2d').drawImage(p.canvas, 0, 0);
        return cut.toDataURL('image/png');
      }),
      glyphs,
    };
  }
  return fonts;
}, { FONTS, families, charset, PAGE });

const meta = {};
for (const [name, font] of Object.entries(result)) {
  const files = font.pages.map((data, i) => {
    const file = `glyphs_${name}_${i}.png`;
    writeFileSync(`${outDir}/${file}`, Buffer.from(data.split(',')[1], 'base64'));
    return file;
  });
  meta[name] = { size: font.size, pad: font.pad, lineHeight: font.lineHeight, pages: files, glyphs: font.glyphs };
  console.log(`${name}: 글자 ${Object.keys(font.glyphs).length}개, 페이지 ${files.length}장`);
}
writeFileSync(`${outDir}/glyphs.json`, JSON.stringify(meta));
await browser.close();
