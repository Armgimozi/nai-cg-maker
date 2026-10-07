// 죽음 (5.5, 5.6, 사용자 결정 3: 새빨간 "YOU DIED"). 바닐라 사망 화면 (immediate_respawn=false) 이 열리고,
// "YOU DIED" 는 한 번만 보인다: 기본은 팩 쪽 deathScreen.title (glyphs.yml 의 그림 글자) 이고 플러그인은 제목을 보내지 않는다.
// death.title: true 면 반대로 팩 제목이 비고 플러그인 화면 제목이 일어설 때까지 떠 있다. 그림 글자는 붉고 크다.
// 사망 화면 밑 문구와 채팅 알림은 없다. 인벤토리는 그대로, 일어서면 souls_world 시험 방, 체력·스태미나가 찬다.
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

// 붉은가 (색상 ±25°, 채도와 밝기가 충분한가). "새빨간" 이라 마른 핏빛보다 밝은 쪽을 본다
function redness (pixels) {
  if (!pixels.length) return null
  let r = 0; let g = 0; let b = 0
  for (const p of pixels) { r += p[0]; g += p[1]; b += p[2] }
  r /= pixels.length; g /= pixels.length; b /= pixels.length
  const c = L.hsv(r, g, b)
  // 가장 밝은 1/4 의 평균 (글자의 밝은 면)
  const top = pixels.slice().sort((x, y) => (y[0] + y[1] + y[2]) - (x[0] + x[1] + x[2])).slice(0, Math.max(1, pixels.length >> 2))
  let tr = 0; let tg = 0; let tb = 0
  for (const p of top) { tr += p[0]; tg += p[1]; tb += p[2] }
  const t = L.hsv(tr / top.length, tg / top.length, tb / top.length)
  const hex = (x) => Math.round(x).toString(16).padStart(2, '0')
  return {
    avg: '#' + hex(r) + hex(g) + hex(b),
    top: '#' + hex(tr / top.length) + hex(tg / top.length) + hex(tb / top.length),
    red: (c.h <= 25 || c.h >= 335) && c.s >= 0.55 && (t.h <= 25 || t.h >= 335) && t.s >= 0.55 && t.v >= 0.55
  }
}

/** 팩 글꼴에서 글자 하나의 그림 칸 (bitmap 제공자의 격자). */
function glyphCell (zip, fontId, ch) {
  const [ns, name] = fontId.includes(':') ? fontId.split(':') : ['minecraft', fontId]
  const font = zip.json(`assets/${ns}/font/${name}.json`)
  if (!font) return { err: `글꼴 ${fontId} 없음` }
  for (const p of font.providers || []) {
    if (p.type === 'space' && p.advances && p.advances[ch] !== undefined) return { space: true }
    if (p.type !== 'bitmap') continue
    const rows = (p.chars || []).map((r) => [...r])
    for (let y = 0; y < rows.length; y++) {
      const x = rows[y].indexOf(ch)
      if (x < 0) continue
      const [fns, fpath] = p.file.includes(':') ? p.file.split(':') : ['minecraft', p.file]
      const png = zip.get(`assets/${fns}/textures/${fpath}`)
      if (!png) return { err: '그림 없음 ' + p.file }
      const im = L.decodePng(png)
      const cw = im.w / Math.max(...rows.map((r) => r.length)); const chh = im.h / rows.length
      const px = []
      for (let yy = Math.floor(y * chh); yy < Math.floor((y + 1) * chh); yy++) {
        for (let xx = Math.floor(x * cw); xx < Math.floor((x + 1) * cw); xx++) {
          const o = (yy * im.w + xx) * 4
          if (im.rgba[o + 3] > 0) px.push([im.rgba[o], im.rgba[o + 1], im.rgba[o + 2]])
        }
      }
      return { px, height: p.height || 8, cell: `${cw}x${chh}`, file: p.file }
    }
  }
  return { err: `글꼴 ${fontId} 에 ${ch.codePointAt(0).toString(16)} 없음` }
}

L.run('death', async (sc) => {
  const E = L.ENV
  const glyphs = L.loadGlyphs()
  const yd = glyphs && glyphs.you_died
  if (!yd) sc.miss('glyphs.yml has you_died', E.glyphs || '(glyphs.yml 없음)')
  // 플러그인 화면 제목에 쓰는 줄 (config.yml death.title-glyphs, 기본 you_died_title: souls:hud 글꼴)
  const dc = L.deathConfig()
  const names = dc.titleGlyphs.split(/\s+/).filter(Boolean)
  const tg = glyphs && names.every((n) => glyphs[n]) ? { char: names.map((n) => glyphs[n].char).join(''), font: glyphs[names[0]].font, name: names.join(' ') } : null
  if (!tg) sc.miss('glyphs.yml has the plugin title glyphs', dc.titleGlyphs)

  const b = await L.connect(sc, { respawn: false })
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await b.cmd('/soulstest heal', 'HEAL')
  // 인벤토리가 남는지 보려고 시험 도구 하나를 손에 둔다
  await b.cmd('/soulstest guard empty', 'GUARD')
  await L.sleep(500)
  const before = b.bot.heldItem ? b.bot.heldItem.name : null
  const slot = b.bot.quickBarSlot

  // ── 죽기 ──
  const from = b.sys.length
  const d0 = b.p.deaths.length
  const t0 = b.p.titles.length
  const k = await b.cmd('/soulstest kill', 'KILL')
  if (!sc.checkCmd('kill command', k, (r) => !!r.line)) return
  await L.sleep(2000)
  const dth = b.p.deaths.slice(d0).find((d) => d.playerId === b.id)
  sc.check('vanilla death screen opens (death_combat_event)', !!dth, dth ? '' : '패킷 없음')
  sc.check('death screen message is empty', dth && dth.message === '', dth ? JSON.stringify(dth.message) : '')
  sc.check('respawn screen enabled (immediate_respawn=false)', b.p.login && b.p.login.enableRespawnScreen === true, 'enableRespawnScreen=' + (b.p.login && b.p.login.enableRespawnScreen))
  const dl = b.tLines('DEATH', from)[0]
  sc.check('server DEATH line', !!dl, dl ? dl.line : '')
  const broadcast = b.sys.slice(from).find((m) => m.parts.some((p) => p.translate && p.translate.startsWith('death.')))
  sc.check('no death broadcast in chat', !broadcast, broadcast ? broadcast.plain : '')

  // ── 제목 "YOU DIED": 한 번만 보인다 (5.6, 13.4 의 3). 기본은 팩의 사망 화면 제목, death.title: true 면 플러그인 화면 제목 ──
  sc.note(`death.title=${dc.title} (${dc.source}): ${dc.title ? '플러그인 화면 제목' : '사망 화면 제목'}, title-glyphs=${dc.titleGlyphs}`)
  const title = b.p.titles.slice(t0).find((x) => x.plain.trim())
  const tl = b.tLines('TITLE', from)[0]
  const tt = dc.title ? b.p.titleTimes[b.p.titleTimes.length - 1] : null
  if (!dc.title) {
    sc.check('no plugin title over the death screen (YOU DIED shown once)', !title, title ? JSON.stringify(title.plain) : '')
    sc.check('server TITLE line mode=screen', tl && tl.kv.mode === 'screen', tl ? tl.line : '')
  } else {
    sc.check('title packet sent on death', !!title, title ? JSON.stringify(title.plain) : '제목 없음')
    if (title && tg) checkGlyphTitle(title)
    sc.check('title held until respawn (stay >= 200)', tt && tt.stay >= 200, tt ? `${tt.fadeIn}/${tt.stay}/${tt.fadeOut}` : '시간 패킷 없음')
    sc.check('server TITLE line mode=plugin glyph=true', tl && tl.kv.mode === 'plugin' && tl.kv.glyph === 'true', tl ? tl.line : '')
  }

  // ── 팩 쪽 (5.6, 10.9): 사망 화면 제목 키, 점수 줄, 그림 글자는 붉고 크다 ──
  const packFile = [E.runDir && path.join(E.runDir, 'received-pack.zip'), E.runDir && path.join(E.runDir, 'pack.zip')].find((f) => f && fs.existsSync(f))
  if (!packFile) sc.miss('pack death screen checks', '받은 팩이 없다')
  else {
    const zip = L.readZip(fs.readFileSync(packFile))
    // 클라이언트는 en_us 다음에 고른 언어를 읽으므로 바닐라의 모든 언어 (1.21.11: 143개) 에 같은 키가 있어야 한다.
    // 여기서는 몇 언어를 자세히 보고, 개수는 따로 센다
    const langFiles = zip.names.filter((n) => /^assets\/minecraft\/lang\/[a-z_]+\.json$/.test(n))
    sc.check('death screen keys written for every vanilla language (>= 143 files)', langFiles.length >= 143, langFiles.length + '개')
    // 단추 글 (lang 의 vanilla.deathScreen.*): ko_kr 은 한국어, 그 밖의 모든 언어는 en_us 와 같은 영어 (10.9)
    const enRespawn = (zip.json('assets/minecraft/lang/en_us.json') || {})['deathScreen.respawn']
    for (const lang of ['en_us', 'ko_kr', 'en_gb', 'ja_jp', 'zh_cn']) {
      const j = zip.json(`assets/minecraft/lang/${lang}.json`)
      if (!j) { sc.check(`${lang}: lang file present`, false); continue }
      // 사망 화면 제목: 기본은 그림 글자 YOU DIED, 플러그인 화면 제목을 쓰면 빈칸 (둘이 겹치지 않게).
      // 바닐라 "You Died!" 가 남거나 다른 글이면 안 된다
      const dt = j['deathScreen.title']
      const want = dc.title ? '' : (yd && yd.char)
      sc.check(`${lang}: deathScreen.title = ${dc.title ? 'empty (plugin title instead)' : 'you_died glyphs'}`, yd && dt === want,
        dt === undefined ? '키 없음 (바닐라 글이 남는다)' : dt === '' ? '빈칸' : [...dt].map((c) => c.codePointAt(0).toString(16)).join(' '))
      sc.check(`${lang}: score line empty`, j['deathScreen.score.value'] === '', JSON.stringify(j['deathScreen.score.value']))
      const rb = j['deathScreen.respawn'] || ''
      if (lang === 'ko_kr') sc.check('ko_kr: respawn button is Korean (일어선다)', /^\u00a77[가-힣 ]+$/.test(rb), JSON.stringify(rb))
      else sc.check(`${lang}: respawn button is the souls English text (same as en_us, not vanilla Respawn)`, rb === enRespawn && /^\u00a77[A-Za-z ]+$/.test(rb) && !/Respawn/.test(rb), JSON.stringify(rb))
    }
    if (yd) {
      const px = []
      let height = 0
      const errs = []
      let letters = 0
      for (const ch of [...yd.char]) {
        const c = glyphCell(zip, yd.font, ch)
        if (c.err) errs.push(c.err)
        else if (!c.space) { px.push(...c.px); height = Math.max(height, c.height); letters++ }
      }
      sc.check('every title glyph exists in the pack font', !errs.length, errs.join(', ') || `${letters}글자`)
      sc.check('title spells 7 letters (Y O U D I E D)', letters === 7, letters + '글자')
      const red = redness(px)
      sc.check('YOU DIED glyph pixels are vivid red', red && red.red, red ? `평균 ${red.avg}, 밝은 면 ${red.top}` : '불투명 픽셀 없음')
      sc.check('YOU DIED glyphs are large (font height >= 10)', height >= 10, 'height=' + height)
    }
  }

  // ── 일어서기 ──
  await L.sleep(500)
  const r0 = b.p.respawns.length
  const x0 = b.p.xp.length
  // 죽어 있는 동안 HUD 는 비어 있다 (다크 소울처럼 YOU DIED 만): HUD 보스 막대의 이름이 빈 글
  const deadBar = b.hudBar()
  const deadHud = deadBar ? L.decodeHud(deadBar.parts, glyphs) : null
  sc.check('HUD blank while dead (HUD boss bar name empty)', deadHud && !Object.keys(deadHud.bars).length && !deadHud.unknown,
    deadHud ? JSON.stringify(deadHud.bars) : 'HUD 보스 막대 없음')
  const c0 = b.p.clearTitles.length
  const from2 = b.sys.length
  b.respawn()
  await L.sleep(2500)
  const rp = b.p.respawns[r0]
  sc.check('respawn packet into souls_world', rp && /souls_world$/.test(rp.world), rp ? rp.world : '없음')
  const rl = b.tLines('RESPAWN', from2)[0]
  sc.check('server RESPAWN line world=souls_world', rl && rl.kv.world === 'souls_world', rl ? rl.line : '')
  const room = L.testRoom()
  const pos = b.bot.entity.position
  sc.check('respawns in the test room', Math.abs(pos.x - room.x) <= 12.5 && Math.abs(pos.z - room.z) <= 12.5 && pos.y >= room.y && pos.y <= room.y + 3,
    `(${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)})`)
  sc.check('health full after respawn', b.health >= 19.99, 'hp=' + b.health)
  const xp = b.p.xp.slice(x0)
  sc.check('xp level still 0 after respawn', xp.every((x) => x.level === 0), xp.map((x) => x.level).join(',') || '경험치 패킷 없음')
  const aliveBar = b.hudBar()
  const h = aliveBar ? L.decodeHud(aliveBar.parts, glyphs) : null
  sc.check('HUD bars back and full after respawn (hp, stamina)', h && ['hp', 'st'].every((k) => h.bars[k] && h.bars[k].fill > 0 && !h.bars[k].empty),
    h ? JSON.stringify(h.bars) : 'HUD 보스 막대 없음')
  sc.check('title cleared after respawn', b.p.clearTitles.length > c0)
  const mode = rp ? rp.gamemode : null
  sc.check('still adventure after respawn', mode === 'adventure', String(mode))
  b.bot.setQuickBarSlot(slot)
  await L.sleep(300)
  const after = b.bot.heldItem ? b.bot.heldItem.name : null
  sc.check('inventory kept (keep_inventory)', before && after === before, `${before} → ${after}`)
  // 화면 제목 경로 (death.title: true 일 때 쓰는 길). 기본 판에서도 그림 글자가 제대로 실리는지 /soulstest title 로 본다
  if (!dc.title && tg) {
    const t1 = b.p.titles.length
    const r = await b.cmd('/soulstest title', 'TITLE', 1500)
    await L.sleep(300)
    const forced = b.p.titles.slice(t1).find((x) => x.plain.trim())
    sc.check('/soulstest title shows the glyph title', !!forced, forced ? '' : (r && r.line) || '제목 없음')
    if (forced) checkGlyphTitle(forced)
  }
  sc.check('no kick during death scenario', !b.kick, b.kick || '')

  function checkGlyphTitle (t) {
    sc.check(`title is the ${tg.name} glyph line (glyphs.yml)`, t.plain === tg.char, `${[...t.plain].map((c) => c.codePointAt(0).toString(16)).join(' ')}`)
    const fonts = [...new Set(t.parts.filter((p) => p.text).map((p) => p.font || 'minecraft:default'))]
    sc.check('title uses the glyph font', fonts.length === 1 && fonts[0].replace(/^minecraft:/, '') === tg.font.replace(/^minecraft:/, ''), fonts.join(','))
    const cols = [...new Set(t.parts.filter((p) => p.text).map((p) => String(p.color || 'white').toLowerCase()))]
    sc.check('title text colour does not tint the glyph (white)', cols.every((c) => c === 'white' || c === '#ffffff'), cols.join(','))
  }
})
