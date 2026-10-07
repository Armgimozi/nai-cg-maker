// 죽음 (5.5, 5.6, 사용자 결정 3: 새빨간 "YOU DIED"). 바닐라 사망 화면 (immediate_respawn=false) 이 열리고,
// 그 위에 큰 제목이 glyphs.yml 의 그림 글자로 온다. 팩 쪽 deathScreen.title 도 같은 그림 글자이고 그 그림은 붉다.
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

  // ── 제목 "YOU DIED" ──
  const title = b.p.titles.slice(t0).find((x) => x.plain.trim())
  sc.check('title packet sent on death', !!title, title ? JSON.stringify(title.plain) : '제목 없음')
  if (title && yd) {
    sc.check('title is the you_died glyph line (glyphs.yml)', title.plain === yd.char, `${[...title.plain].map((c) => c.codePointAt(0).toString(16)).join(' ')}`)
    const fonts = [...new Set(title.parts.filter((p) => p.text).map((p) => p.font || 'minecraft:default'))]
    sc.check('title uses the glyph font', fonts.length === 1 && fonts[0].replace(/^minecraft:/, '') === yd.font.replace(/^minecraft:/, ''), fonts.join(','))
    const cols = [...new Set(title.parts.filter((p) => p.text).map((p) => String(p.color || 'white').toLowerCase()))]
    sc.check('title text colour does not tint the glyph (white)', cols.every((c) => c === 'white' || c === '#ffffff'), cols.join(','))
  }
  const tt = b.p.titleTimes[b.p.titleTimes.length - 1]
  sc.check('title stays >= 2 s', tt && tt.stay >= 40, tt ? `${tt.fadeIn}/${tt.stay}/${tt.fadeOut}` : '시간 패킷 없음')
  const tl = b.tLines('TITLE', from)[0]
  sc.check('server TITLE line glyph=true', tl && tl.kv.glyph === 'true', tl ? tl.line : '')

  // ── 팩 쪽 (5.6, 10.9): deathScreen.title = 같은 그림 글자, 그림은 붉고 크다 ──
  const packFile = [E.runDir && path.join(E.runDir, 'received-pack.zip'), E.runDir && path.join(E.runDir, 'pack.zip')].find((f) => f && fs.existsSync(f))
  if (!packFile) sc.miss('pack death screen checks', '받은 팩이 없다')
  else {
    const zip = L.readZip(fs.readFileSync(packFile))
    for (const lang of ['en_us', 'ko_kr']) {
      const j = zip.json(`assets/minecraft/lang/${lang}.json`)
      if (!j) { sc.check(`${lang}: lang file present`, false); continue }
      sc.check(`${lang}: deathScreen.title = you_died glyphs`, yd && j['deathScreen.title'] === yd.char, j['deathScreen.title'] ? [...j['deathScreen.title']].map((c) => c.codePointAt(0).toString(16)).join(' ') : '없음')
      sc.check(`${lang}: score line empty`, j['deathScreen.score.value'] === '', JSON.stringify(j['deathScreen.score.value']))
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
  sc.check('stamina bar resent full after respawn', xp.length && xp[xp.length - 1].bar >= 0.99 && xp[xp.length - 1].level === 0,
    xp.length ? `bar=${xp[xp.length - 1].bar} level=${xp[xp.length - 1].level}` : '경험치 패킷 없음')
  sc.check('title cleared after respawn', b.p.clearTitles.length > c0)
  const mode = rp ? rp.gamemode : null
  sc.check('still adventure after respawn', mode === 'adventure', String(mode))
  b.bot.setQuickBarSlot(slot)
  await L.sleep(300)
  const after = b.bot.heldItem ? b.bot.heldItem.name : null
  sc.check('inventory kept (keep_inventory)', before && after === before, `${before} → ${after}`)
  sc.check('no kick during death scenario', !b.kick, b.kick || '')
})
