// 언어 (10.3, 10.9, 12.5): 게임 글은 번역 열쇠이고 클라이언트가 팩의 언어 파일에서 고른다. 한국어가 원본, 영어는 따로 썼다.
// 봇은 영어 클라이언트 (en_us) 로 들어와 본다:
//   팩 안내 (팩을 싣기 전이라 서버가 채운 글) 가 영어, 받은 팩의 souls 언어 파일 ko_kr·en_us 의 열쇠와 자리가 같다,
//   팩을 싣기 전의 행동 막대 (팩을 실은 뒤는 그림 글자 소울 상자)·시험 도구 이름과 설명·Dialog 창·관리자 답이 번역 열쇠이고
//   대체 글이 영어다,
//   같은 열쇠가 en_us·fr_fr (en_us 로 떨어진다)·ko_kr 표로 제 언어가 된다, 꼴(색)과 기울임 끔이 번역 글에 붙는다.
// 끝으로 팩을 거절하는 영어·한국어 클라이언트가 각자 자기 언어의 서버 글로 쫓겨나는지 본다 (번역 열쇠가 아니다).
'use strict'
const L = require('./lib')

const HANGUL = /[가-힣]/

L.run('lang', async (sc) => {
  const b = await L.connect(sc, { locale: 'en_us' })

  // ── 팩 안내 (서버가 봇의 언어로 채운다) ──
  const t0 = Date.now()
  while (!b.p.packs.length && Date.now() - t0 < 6000) await L.sleep(100)
  const pk = b.p.packs[0]
  if (!sc.check('resource pack pushed', !!pk)) return
  sc.check('pack prompt is English for an en_us client (server-rendered)', pk.prompt && !HANGUL.test(pk.prompt) && /resource pack/i.test(pk.prompt) &&
    !L.translateKeys(pk.promptRaw).length, pk.prompt || '')
  const sent = b.tLines('PACK sent')[0]
  sc.check('server picked lang=en for the pack prompt', sent && sent.kv.lang === 'en', sent ? sent.line : '시험 줄 없음')
  const got = await b.p.packChecks[0]
  if (!sc.check('pack downloaded', got && got.ok, got && got.error)) return
  const zip = L.readZip(got.buf)
  const T = { en: L.langTable(zip, 'en_us'), ko: L.langTable(zip, 'ko_kr'), fr: L.langTable(zip, 'fr_fr') }

  // ── 팩의 souls 언어 파일 ──
  const ko = zip.json('assets/souls/lang/ko_kr.json')
  const en = zip.json('assets/souls/lang/en_us.json')
  sc.check('pack has assets/souls/lang/ko_kr.json and en_us.json', ko && en)
  if (ko && en) {
    const kk = Object.keys(ko).sort(); const ek = Object.keys(en).sort()
    sc.check('ko_kr and en_us have the same keys', JSON.stringify(kk) === JSON.stringify(ek),
      `ko ${kk.length}, en ${ek.length}: ${kk.filter((k) => !(k in en)).concat(ek.filter((k) => !(k in ko))).slice(0, 5).join(', ')}`)
    sc.check('every key is under souls.', kk.every((k) => k.startsWith('souls.')))
    const args = (v) => [...new Set((String(v).match(/%(\d+\$)?s/g) || []).map((m, i) => m.includes('$') ? m : `%${i + 1}$s`))].sort().join()
    const badArgs = kk.filter((k) => args(ko[k]) !== args(en[k]))
    sc.check('ko_kr and en_us use the same placeholders per key', !badArgs.length, badArgs.slice(0, 5).join(', '))
    const enKo = ek.filter((k) => HANGUL.test(en[k]))
    sc.check('no Hangul in en_us', !enKo.length, enKo.slice(0, 5).join(', '))
    const tags = ek.filter((k) => /<[#a-z!][^<>]*>/.test(en[k]) || /<[#a-z!][^<>]*>/.test(ko[k]))
    sc.check('lang JSON holds plain text (no MiniMessage tags)', !tags.length, tags.slice(0, 5).join(', '))
  }

  // ── 행동 막대 (번역 열쇠 + 꼴) ── 팩을 싣기 전의 소울 줄 (대체 글). 팩을 실은 뒤는 언어가 없는 그림 글자 상자 (10.2)
  const end = Date.now() + 3000
  let ab = null
  while (!(ab = b.p.actionBars.find((x) => findTranslate(x.raw, 'souls.hud.souls'))) && Date.now() < end) await L.sleep(100)
  const tr = ab && findTranslate(ab.raw, 'souls.hud.souls')
  sc.check('pre-pack action bar = translatable souls.hud.souls', !!tr, b.p.actionBars.slice(0, 3).map((x) => JSON.stringify(x.raw).slice(0, 120)).join(' | ') || '행동 막대 없음')
  // 팩을 실은 뒤 첫 그림 글자 상자가 올 때까지 기다린다 (바로 앞의 마지막 줄은 아직 팩 전 대체 글일 수 있다)
  const glyphs = L.loadGlyphs()
  const boxEnd = Date.now() + 3000
  let box = null
  for (;;) {
    const last = b.p.actionBars[b.p.actionBars.length - 1]
    box = last && L.decodeHud(last.parts, glyphs)
    if ((box && box.soulBox) || Date.now() >= boxEnd) break
    await L.sleep(100)
  }
  sc.check('after the pack: action bar is the language-free souls glyph box', box && box.soulBox && /^\d+$/.test(box.digits) && !box.unknown,
    box ? JSON.stringify(box) : '행동 막대 없음')
  if (tr) {
    // 한 사람에게 가는 글의 대체 글은 그 사람의 언어 (Lang.c(viewer, ...)). 이 봇은 en_us 라 영어 (join 은 ko_kr 로 한국어를 본다)
    sc.check('translatable carries the viewer-language (English) fallback', typeof tr.fallback === 'string' && /^Souls %1\$s$/.test(tr.fallback), JSON.stringify(tr.fallback))
    sc.check('translatable carries the key style (#b3a37f)', String(tr.color || '').toLowerCase() === '#b3a37f', JSON.stringify(tr.color))
    const shownEn = L.render(ab.raw, T.en).trim(); const shownFr = L.render(ab.raw, T.fr).trim(); const shownKo = L.render(ab.raw, T.ko).trim()
    sc.check('en_us reads "Souls N"', /^Souls [\d,]+$/.test(shownEn), JSON.stringify(shownEn))
    sc.check('fr_fr falls back to en_us', shownFr === shownEn, JSON.stringify(shownFr))
    sc.check('ko_kr reads "소울 N"', /^소울 [\d,]+$/.test(shownKo), JSON.stringify(shownKo))
  }

  // ── 시험 도구: 이름과 설명이 번역 열쇠 (아이템에 글이 아니라 열쇠가 적힌다) ──
  const s0 = b.p.slots.length
  const g = await b.cmd('/soulstest guard empty', 'GUARD')
  sc.checkCmd('/soulstest guard gives the tool', g, (r) => r.kv.kind === 'empty')
  const se = Date.now() + 3000
  let item = null
  while (Date.now() < se && !item) {
    item = b.p.slots.slice(s0).reverse().find((x) => x.name && L.translateKeys(x.name)[0] === 'souls.test.guard')
    if (!item) await L.sleep(100)
  }
  sc.check('item_name = translatable souls.test.guard', !!item, b.p.slots.slice(s0).map((x) => JSON.stringify(x.name)).join(' | ').slice(0, 300) || '칸 패킷 없음')
  if (item) {
    sc.check('item name reads in English / Korean (<kind> is the typed argument)', L.render(item.name, T.en) === 'Test Guard [empty]' && /^시험 막기 \[empty\]$/.test(L.render(item.name, T.ko)),
      `${L.render(item.name, T.en)} / ${L.render(item.name, T.ko)}`)
    // 아이템은 여러 사람이 볼 수 있어 대체 글 (팩이 없을 때) 이 영어다 (10.9)
    sc.check('item fallback (no pack) is English', L.render(item.name, {}) === 'Test Guard [empty]', JSON.stringify(L.render(item.name, {})))
    const lk = item.lore.map((l) => L.translateKeys(l)[0])
    sc.check('lore lines = translatable souls.test.guard-lore.1, .2', lk.join() === 'souls.test.guard-lore.1,souls.test.guard-lore.2', lk.join())
    sc.check('lore is not italic (vanilla lore is italic by default)', item.lore.length && item.lore.every((l) => l.italic === false || l.italic === 0), item.lore.map((l) => l.italic).join())
    sc.check('lore reads in English', item.lore.every((l) => !HANGUL.test(L.render(l, T.en)) && L.render(l, T.en).length > 3), item.lore.map((l) => L.render(l, T.en)).join(' / '))
    sc.check('no custom_name (item_name only)', !item.customName)
  }

  // ── Dialog 창 (휴식 창 꼴) ──
  const d0 = b.p.dialogs.length
  const dl = await b.cmd('/soulstest dialog', 'DIALOG shown')
  sc.checkCmd('/soulstest dialog shown', dl, () => true)
  const de = Date.now() + 2000
  while (b.p.dialogs.length === d0 && Date.now() < de) await L.sleep(50)
  const dg = b.p.dialogs[b.p.dialogs.length - 1]
  if (!dg || b.p.dialogs.length === d0) sc.check('show_dialog packet received', false, '패킷 없음')
  else {
    const keys = L.translateKeys(collectText(dg.raw))
    const want = ['souls.bonfire.test-name', 'souls.bonfire.status', 'souls.bonfire.rest', 'souls.bonfire.warp', 'souls.bonfire.leave']
    sc.check('dialog title, body and buttons are translatable', want.every((k) => keys.includes(k)), keys.join(','))
    const title = dg.raw && dg.raw.title
    sc.check('dialog title reads in English', title && !HANGUL.test(L.render(title, T.en)), title ? L.render(title, T.en) : JSON.stringify(dg.raw).slice(0, 200))
  }

  // ── 관리자 답 (번역 열쇠 + 인수) ──
  const tp = await b.cmd('/souls tp nowhere', (m) => L.translateKeys(m.raw).includes('souls.admin.no-anchor'), 3000)
  sc.checkCmd('admin reply = translatable souls.admin.no-anchor', tp, (r) => !!r.msg)
  if (tp.msg) sc.check('admin reply reads "No such anchor: nowhere"', L.render(tp.msg.raw, T.en) === 'No such anchor: nowhere', L.render(tp.msg.raw, T.en))
  sc.check('no kick during lang scenario', !b.kick, b.kick || '')
  await b.quit()

  // ── 팩을 거절하면 자기 언어의 서버 글로 쫓겨난다 (팩이 없으니 번역 열쇠가 아니다) ──
  for (const [locale, re, label] of [['en_us', /^[^가-힣]*resource pack/i, 'English'], ['ko_kr', /리소스팩/, 'Korean']]) {
    await L.sleep(1500)
    const d = await L.connect(sc, { locale, declinePack: true, retries: 3 })
    const ke = Date.now() + 8000
    while (!d.kick && !d.ended && Date.now() < ke) await L.sleep(100)
    sc.check(`${locale}: declining the required pack kicks with ${label} server text`, d.kick && re.test(d.kick) && !L.translateKeys(d.kickRaw).length,
      d.kick ? JSON.stringify(d.kick) : '쫓겨나지 않았다')
    await d.quit()
  }
})

/** 글 요소 트리에서 translate 가 key 인 첫 요소. */
function findTranslate (c, key) {
  c = L.simple(c)
  if (c == null || typeof c !== 'object') return null
  if (Array.isArray(c)) { for (const x of c) { const r = findTranslate(x, key); if (r) return r } return null }
  if (c.translate === key) return c
  for (const x of [...(c.with || []), ...(Array.isArray(c.extra) ? c.extra : c.extra ? [c.extra] : [])]) {
    const r = findTranslate(x, key)
    if (r) return r
  }
  return null
}

/** Dialog NBT 안의 글 요소들 (제목, 본문 contents, 단추 label) 을 한 목록으로. */
function collectText (node, out = []) {
  if (node == null || typeof node !== 'object') return out
  if (Array.isArray(node)) { for (const x of node) collectText(x, out); return out }
  if (node.translate !== undefined || node.text !== undefined) { out.push(node); return out }
  for (const v of Object.values(node)) collectText(v, out)
  return out
}
