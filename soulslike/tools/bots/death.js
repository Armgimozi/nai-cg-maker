// 죽음 (5.5, 5.6, 사용자 결정 3: 새빨간 "YOU DIED"). 바닐라 사망 화면 (immediate_respawn=false) 이 열리고,
// "YOU DIED" 는 한 번만 보인다. 자리는 config.yml 의 death.* 를 따른다 (lib.deathConfig):
//   fade (기본, death.screen-fade): 팩의 deathScreen.title 이 비고, 플러그인이 사망 화면 문구 줄에 souls:death 그림 글자 한 줄
//         (glyphs.yml you_died_fade, 띠 + 글자) 을 보낸다. 글자색·그림자색이 죽은 게임 시각을 싣는 표식 (glyphs.yml death_fade).
//         죽은 채 나갔다 들어오면 바로 일어선다 (문구 줄이 다시 오지 않으므로). 줄에는 단추 가림막 (fade_death_veil) 도 있다.
//         팩을 다 싣지 않은 사람 (holdPack) 에게는 문구 줄을 비운다 (그 클라이언트에는 souls:death 글꼴이 없다)
//   screen: 팩 쪽 deathScreen.title (glyphs.yml 의 그림 글자) 이고 플러그인은 아무것도 보내지 않는다
//   plugin (death.title): 팩 제목이 비고 플러그인 화면 제목이 일어설 때까지 떠 있다
// 그림 글자는 붉고 크다. 채팅 알림은 없다. 인벤토리는 그대로, 일어서면 souls_world 시험 방, 체력·스태미나가 찬다.
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
  const fade = dc.mode === 'fade'
  const yf = glyphs && glyphs.you_died_fade
  if (!fade) sc.check('death screen message is empty', dth && dth.message === '', dth ? JSON.stringify(dth.message) : '')
  else checkFadeLine(dth)
  sc.check('respawn screen enabled (immediate_respawn=false)', b.p.login && b.p.login.enableRespawnScreen === true, 'enableRespawnScreen=' + (b.p.login && b.p.login.enableRespawnScreen))
  const dl = b.tLines('DEATH', from)[0]
  sc.check('server DEATH line', !!dl, dl ? dl.line : '')
  const broadcast = b.sys.slice(from).find((m) => m.parts.some((p) => p.translate && p.translate.startsWith('death.')))
  sc.check('no death broadcast in chat', !broadcast, broadcast ? broadcast.plain : '')

  // ── 제목 "YOU DIED": 한 번만 보인다 (5.6, 13.4 의 3). 서서히 (문구 줄), 사망 화면 제목, 플러그인 화면 제목 가운데 하나 ──
  sc.note(`death.title=${dc.title}, death.screen-fade=${dc.screenFade} (${dc.source}): ` +
    `${{ fade: '사망 화면 문구 줄 (서서히)', screen: '사망 화면 제목', plugin: '플러그인 화면 제목' }[dc.mode]}, title-glyphs=${dc.titleGlyphs}`)
  const title = b.p.titles.slice(t0).find((x) => x.plain.trim())
  const tl = b.tLines('TITLE', from)[0]
  const tt = dc.title ? b.p.titleTimes[b.p.titleTimes.length - 1] : null
  if (!dc.title) {
    sc.check('no plugin title over the death screen (YOU DIED shown once)', !title, title ? JSON.stringify(title.plain) : '')
    sc.check(`server TITLE line mode=${dc.mode}`, tl && tl.kv.mode === dc.mode && (!fade || (tl.kv.glyph === 'true' && tl.kv.pack === 'true')), tl ? tl.line : '')
    if (fade && tl && dth) {
      // 문구 줄의 표식 색이 서버가 적은 죽은 게임 시각 (gt) 을 싣는다 (셰이더가 이 값으로 서서히 나타나게 한다)
      const m = fadeMark(dth)
      sc.check('fade line colour carries the death game time (TITLE gt)', m && String(m.t) === tl.kv.gt, m ? `t=${m.t} gt=${tl.kv.gt}` : '표식 없음')
    }
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
      // 사망 화면 제목: screen 판은 그림 글자 YOU DIED, 서서히 판·플러그인 화면 제목 판은 빈칸 (둘이 겹치지 않게).
      // 바닐라 "You Died!" 가 남거나 다른 글이면 안 된다
      const dt = j['deathScreen.title']
      const want = dc.mode === 'screen' ? (yd && yd.char) : ''
      sc.check(`${lang}: deathScreen.title = ${dc.mode === 'screen' ? 'you_died glyphs' : `empty (${dc.mode} instead)`}`, yd && dt === want,
        dt === undefined ? '키 없음 (바닐라 글이 남는다)' : dt === '' ? '빈칸' : [...dt].map((c) => c.codePointAt(0).toString(16)).join(' '))
      sc.check(`${lang}: score line empty`, j['deathScreen.score.value'] === '', JSON.stringify(j['deathScreen.score.value']))
      const rb = j['deathScreen.respawn'] || ''
      if (lang === 'ko_kr') sc.check('ko_kr: respawn button is Korean (다시 일어서기)', /^\u00a77[가-힣 ]+$/.test(rb), JSON.stringify(rb))
      else sc.check(`${lang}: respawn button is the souls English text (same as en_us, not vanilla Respawn)`, rb === enRespawn && /^\u00a77[A-Za-z ]+$/.test(rb) && !/Respawn/.test(rb), JSON.stringify(rb))
    }
    // 그림 글자 줄: screen 판은 사망 화면 제목 (기본 글꼴), 서서히 판은 문구 줄 (souls:death, 1배라 글꼴 높이가 두 배)
    for (const [label, line, minH] of [['title', yd, 10], ['fade line', fade ? yf : null, 20]]) {
      if (!line) continue
      const px = []
      let height = 0
      const errs = []
      let letters = 0
      // 제목 뒤의 검은 띠 (다크 소울 사망 화면, 5.6) 와 문구 줄의 단추 가림막: 글자로 세지 않는다
      const band = new Set(Object.entries(glyphs || {}).filter(([n, g]) => /^(fade_)?death_band/.test(n) && g.font === line.font)
        .map(([, g]) => g.char))
      const veil = new Set(Object.entries(glyphs || {}).filter(([n, g]) => /^fade_death_veil/.test(n) && g.font === line.font)
        .map(([, g]) => g.char))
      let bandTiles = 0
      let veils = 0
      for (const ch of [...line.char]) {
        const c = glyphCell(zip, line.font, ch)
        if (c.err) errs.push(c.err)
        else if (band.has(ch)) { if (!c.space) bandTiles++ }
        else if (veil.has(ch)) { if (!c.space) veils++ }
        else if (!c.space) { px.push(...c.px); height = Math.max(height, c.height); letters++ }
      }
      if (!dc.title) sc.check(`${label}: dark band behind the letters (death_band tiles)`, bandTiles >= 2, bandTiles + '조각')
      if (label === 'fade line') sc.check('fade line: one button veil (fade_death_veil)', veils === 1, veils + '장')
      else sc.check(`${label}: no button veil in the title`, veils === 0, veils + '장')
      sc.check(`${label}: every glyph exists in the pack font ${line.font}`, !errs.length, errs.join(', ') || `${letters}글자`)
      sc.check(`${label}: spells 7 letters (Y O U D I E D)`, letters === 7, letters + '글자')
      const red = redness(px)
      sc.check(`${label}: YOU DIED glyph pixels are vivid red`, red && red.red, red ? `평균 ${red.avg}, 밝은 면 ${red.top}` : '불투명 픽셀 없음')
      sc.check(`${label}: YOU DIED glyphs are large (font height >= ${minH})`, height >= minH, 'height=' + height)
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
  let h = null
  for (let i = 0; i < 30; i++) {
    const aliveBar = b.hudBar()
    h = aliveBar ? L.decodeHud(aliveBar.parts, glyphs) : null
    if (h && h.bars.hp) break
    await L.sleep(100)
  }
  sc.check('HUD bars back and full after respawn (hp, stamina)', h && ['hp', 'st'].every((k) => h.bars[k] && h.bars[k].fill > 0 && !h.bars[k].empty),
    h ? JSON.stringify(h.bars) : 'HUD 보스 막대 없음: ' + b.p.bossbars.slice(-5).map((e) => `${e.action}/${String(e.id).slice(0, 8)}/${e.color}`).join(' '))
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

  // ── 서서히 판: 죽은 채 나갔다 들어오면 (사망 화면이 문구 줄 없이 다시 열린다) 바로 일어선다 ──
  if (fade) {
    const k2 = await b.cmd('/soulstest kill', 'KILL')
    sc.check('second death for the rejoin check', k2 && !!k2.line, k2 && k2.line)
    await L.sleep(1000)
    await b.quit()
    await L.sleep(1500)
    const b2 = await L.connect(sc, { respawn: false })
    let rj = null
    for (let i = 0; i < 60 && !rj; i++) {
      rj = b2.tLines('DEATH_REJOIN', 0)[0]
      if (!rj) await L.sleep(100)
    }
    sc.check('rejoining dead (fade mode): server respawns (DEATH_REJOIN)', !!rj, rj ? rj.line : '시험 줄 없음')
    let alive = false
    for (let i = 0; i < 40 && !alive; i++) {
      alive = b2.health > 0 && b2.p.respawns.length > 0
      if (!alive) await L.sleep(100)
    }
    sc.check('rejoining dead (fade mode): alive again after rejoin', alive, `hp=${b2.health}, respawn 패킷 ${b2.p.respawns.length}`)
    sc.check('no kick during rejoin', !b2.kick, b2.kick || '')

    // 팩을 다 싣기 전에 죽으면 (팩이 선택이 된 서버에서 받지 않은 사람도 같다): 문구 줄을 비워 클라이언트의 바닐라 사망 화면
    // 제목 하나만 남는다 (souls:death 글꼴이 없는 클라이언트에 보내면 빈 네모 줄이 된다)
    await b2.quit()
    await L.sleep(1500)
    const b3 = await L.connect(sc, { respawn: false, holdPack: true })
    await L.sleep(1500)
    const held = b3.tLines('PACK', 0).filter((x) => x.kv.status).map((x) => x.kv.status)
    sc.check('holdPack: the pack is accepted but never loaded', held.includes('ACCEPTED') && !held.includes('SUCCESSFULLY_LOADED'), held.join(',') || '상태 줄 없음')
    const from3 = b3.sys.length
    const d3 = b3.p.deaths.length
    const k3 = await b3.cmd('/soulstest kill', 'KILL')
    sc.check('death before the pack is loaded', k3 && !!k3.line, k3 && k3.line)
    await L.sleep(1500)
    const dth3 = b3.p.deaths.slice(d3).find((d) => d.playerId === b3.id)
    sc.check('no pack: death screen opens with an empty message (vanilla title is the only YOU DIED)', dth3 && dth3.message === '',
      dth3 ? JSON.stringify(dth3.message).slice(0, 80) : '패킷 없음')
    const tl3 = b3.tLines('TITLE', from3)[0]
    sc.check('no pack: server TITLE line mode=fade pack=false', tl3 && tl3.kv.mode === 'fade' && tl3.kv.pack === 'false', tl3 ? tl3.line : '')
    b3.respawn()
    await L.sleep(1500)
    sc.check('no pack: alive again after respawn', b3.health > 0, 'hp=' + b3.health)
    sc.check('no kick without the pack', !b3.kick, b3.kick || '')
  }

  /** glyphs.yml 의 death_fade (표식: 글자색 R, 그림자 R, G 의 시작). 없으면 null. */
  function deathMarks () {
    const f = E.glyphs || path.join(E.root, 'plugin', 'src', 'main', 'resources', 'glyphs.yml')
    const m = fs.existsSync(f) && fs.readFileSync(f, 'utf8').match(/^death_fade:\s*\{mark_r:\s*(\d+),\s*shadow_r:\s*(\d+),\s*g0:\s*(\d+)\}/m)
    return m ? { r: +m[1], shadowR: +m[2], g0: +m[3] } : null
  }

  /** 문구 줄의 표식: 글자색 #RRGGBB → (R, t), 그림자색 (ARGB 정수) → R. glyphs.yml death_fade 의 값과 견준다. */
  function fadeMark (d) {
    const parts = L.flatten(d.raw).filter((p) => p.text)
    const p = parts[0]
    if (!p || typeof p.color !== 'string' || !/^#[0-9a-f]{6}$/i.test(p.color)) return null
    const v = parseInt(p.color.slice(1), 16)
    const r = v >> 16; const g = (v >> 8) & 255; const bb = v & 255
    const sh = p.shadow == null ? null : (Number(p.shadow) >>> 0)
    const dm = deathMarks() || { g0: 144 }
    return { r, g, b: bb, t: (g - dm.g0) * 256 + bb, shadow: sh, colors: [...new Set(parts.map((x) => String(x.color)))], fonts: [...new Set(parts.map((x) => x.font))] }
  }

  function checkFadeLine (d) {
    sc.check('fade: death screen message is the you_died_fade glyph line (glyphs.yml)', d && yf && d.message === yf.char,
      d ? [...d.message].slice(0, 8).map((c) => c.codePointAt(0).toString(16)).join(' ') + '…' : '')
    const m = d && fadeMark(d)
    sc.check('fade: one font souls:death, one marker colour', m && m.fonts.length === 1 && m.fonts[0] === (yf && yf.font) && m.colors.length === 1,
      m ? `${m.fonts.join(',')} ${m.colors.join(',')}` : '표식 없음')
    const dm = deathMarks()
    sc.check('fade: glyphs.yml has the death_fade markers', !!dm, dm ? JSON.stringify(dm) : '없음')
    if (!dm) return
    sc.check(`fade: marker colour (${dm.r}, ${dm.g0} + t/256, t%256), t < 24000`, m && m.r === dm.r && m.t >= 0 && m.t < 24000,
      m ? `r=${m.r} g=${m.g} b=${m.b} t=${m.t}` : '')
    sc.check(`fade: shadow colour is the shadow marker (opaque, ${dm.shadowR}, same t)`, m && m.shadow !== null &&
      (m.shadow >>> 24) === 255 && ((m.shadow >> 16) & 255) === dm.shadowR && ((m.shadow >> 8) & 255) === m.g && (m.shadow & 255) === m.b,
    m && m.shadow !== null ? '#' + (m.shadow >>> 0).toString(16) : '그림자색 없음')
  }

  function checkGlyphTitle (t) {
    sc.check(`title is the ${tg.name} glyph line (glyphs.yml)`, t.plain === tg.char, `${[...t.plain].map((c) => c.codePointAt(0).toString(16)).join(' ')}`)
    const fonts = [...new Set(t.parts.filter((p) => p.text).map((p) => p.font || 'minecraft:default'))]
    sc.check('title uses the glyph font', fonts.length === 1 && fonts[0].replace(/^minecraft:/, '') === tg.font.replace(/^minecraft:/, ''), fonts.join(','))
    const cols = [...new Set(t.parts.filter((p) => p.text).map((p) => String(p.color || 'white').toLowerCase()))]
    sc.check('title text colour does not tint the glyph (white)', cols.every((c) => c === 'white' || c === '#ffffff'), cols.join(','))
  }
})
