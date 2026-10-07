// 접속 (14 M0 "접속하면 팩을 받고 시험 방에 선다", 8.1, 10.2, 10.9, 10.10, 12.7).
// 첫 접속이 로비를 거치지 않고 souls_world 시험 방의 모험 모드로 서는지, 팩을 실제로 받아 SHA-1 이 맞는지,
// 다크 소울 HUD (왼쪽 위 막대 셋 = HUD 보스 막대의 그림 글자, 오른쪽 아래 소울 상자 = 행동 막대, 레벨 0) 가 오는지,
// 모험 모드 보호로 블록이 안 캐지는지 본다.
// 봇은 한국어 클라이언트 (ko_kr) 로 들어온다: 팩 안내는 서버가 한국어로 채우고, 팩을 싣기 전의 행동 막대 (대체 글 "소울 N")
// 는 번역 열쇠라 팩의 ko_kr 로 읽는다.
// 영어 쪽은 lang.js.
'use strict'
const L = require('./lib')

L.run('join', async (sc) => {
  const E = L.ENV
  const b = await L.connect(sc, { locale: 'ko_kr' })
  const room = L.testRoom()

  // ── 첫 화면 ──
  const lg = b.p.login
  sc.check('first login is already souls_world (no lobby)', lg && /souls_world$/.test(lg.world), lg ? lg.world : 'login 패킷 없음')
  await L.sleep(2500)
  const away = b.p.respawns.find((r) => !/souls_world$/.test(r.world))
  sc.check('stays in souls_world after join', !away, away ? '옮겨진 곳 ' + away.world : '')

  const info = await b.cmd('/soulstest info', 'INFO world', 4000)
  sc.checkCmd('info: world souls_world', info, (r) => r.kv.world === 'souls_world', info.line)
  sc.checkCmd('info: adventure mode', info, (r) => r.kv.mode === 'ADVENTURE')
  sc.checkCmd('login gamemode adventure', info, () => lg && lg.gamemode === 'adventure', lg && lg.gamemode)
  sc.checkCmd('stands inside test room', info, (r) => {
    const x = L.num(r.kv.x); const y = L.num(r.kv.y); const z = L.num(r.kv.z)
    return Math.abs(x - room.x) <= 12.5 && Math.abs(z - room.z) <= 12.5 && y >= room.y && y <= room.y + 3
  }, info.kv ? `(${info.kv.x}, ${info.kv.y}, ${info.kv.z}) 방 가운데 (${room.x}, ${room.y}, ${room.z})` : '')
  sc.checkCmd('room biome is a souls: biome', info, (r) => /^souls:/.test(r.kv.biome || ''), info.kv && info.kv.biome)
  sc.checkCmd('xp level 0', info, (r) => r.kv.xpLevel === '0')

  // ── 리소스팩 (10.10) ──
  const t0 = Date.now()
  while (!b.p.packs.length && Date.now() - t0 < 6000) await L.sleep(100)
  const pk = b.p.packs[0]
  if (!sc.check('resource pack pushed', !!pk, pk ? `${pk.state} ${pk.url}` : '6초 안에 add_resource_pack 이 없다')) return
  sc.check('pack url template filled with sha1', pk.hash && pk.url.includes(pk.hash), pk.url)
  if (E.packSha1) sc.check('pack hash = built pack.zip sha1', pk.hash === E.packSha1, `패킷 ${pk.hash} / 빌드 ${E.packSha1}`)
  sc.check('pack required (forced)', pk.forced === true, 'forced=' + pk.forced)
  sc.check('pack prompt text set', !!(pk.prompt && pk.prompt.trim()), pk.prompt || '')
  // 팩 안내는 팩을 싣기 전에 보이므로 번역 열쇠가 아니라 서버가 봇의 언어 (ko_kr) 로 채운 글이다
  sc.check('pack prompt is Korean for a ko_kr client (server-rendered)', /[가-힣]/.test(pk.prompt || '') && !L.translateKeys(pk.promptRaw).length, pk.prompt || '')
  const sent = b.tLines('PACK sent')[0]
  sc.check('server picked lang=ko for the pack prompt', sent && sent.kv.lang === 'ko', sent ? sent.line : '시험 줄 없음')
  const got = await b.p.packChecks[0]
  sc.check('pack downloaded from url', got.ok, got.ok ? `${got.size}B` : got.error)
  if (got.ok) sc.check('downloaded pack sha1 = packet hash', got.hashMatch, got.sha1)
  const st = await b.waitT('PACK status=SUCCESSFULLY_LOADED', 4000)
  sc.check('server saw pack SUCCESSFULLY_LOADED', !!st, st ? st.line : (b.tLines('PACK').map((x) => x.line).join(' | ') || '시험 줄 없음'))
  await L.sleep(1000)
  sc.check('not kicked after pack answer', !b.ended && !b.kick, b.kick || '')

  // 받은 팩의 기본 (10.9, 10.8, 10.2): 형식 75, 셰이더는 HUD 글꼴 셰이더 하나, 숨긴 바닐라 HUD 그림 (투명)
  if (got.ok) {
    const zip = L.readZip(got.buf)
    const meta = zip.json('pack.mcmeta')
    const mp = meta && meta.pack
    sc.check('pack.mcmeta min/max_format 75', mp && JSON.stringify(mp.min_format) === '75' && JSON.stringify(mp.max_format) === '75',
      mp ? `min=${JSON.stringify(mp.min_format)} max=${JSON.stringify(mp.max_format)}` : 'pack.mcmeta 없음')
    const shaders = zip.names.filter((n) => /^assets\/[^/]+\/shaders\//.test(n))
    sc.check('only the HUD text shader (10.8)', shaders.length === 1 && shaders[0] === 'assets/minecraft/shaders/core/rendertype_text.vsh', shaders.join(', ') || '없음')
    const seen = (n) => { const im = L.decodePng(zip.get(n)); for (let i = 3; i < im.rgba.length; i += 4) if (im.rgba[i]) return true; return false }
    const hidden = zip.names.filter((n) => /textures\/gui\/sprites\/(hud\/(food_|armor_|experience_bar_|heart\/)|boss_bar\/white_)[a-z_]*\.png$/.test(n))
    const kinds = ['food_', 'armor_', 'experience_bar_', 'heart/', 'boss_bar/white_'].filter((k) => !hidden.some((n) => n.includes(k)))
    const opaque = hidden.filter(seen)
    sc.check('hidden vanilla HUD sprites transparent (hearts, food, armor, xp bar, HUD boss bar)', !kinds.length && !opaque.length,
      `${hidden.length}개${kinds.length ? ', 빠진 것: ' + kinds.join(', ') : ''}${opaque.length ? ', 보이는 것: ' + opaque.join(', ') : ''}`)
    const boss = ['red', 'yellow'].map((k) => `assets/minecraft/textures/gui/sprites/boss_bar/${k}_progress.png`)
    sc.check('boss bar art for real bosses (red health, yellow posture)', boss.every((n) => zip.has(n) && seen(n)), boss.filter((n) => !zip.has(n)).join(', '))
    const sorted = zip.names.slice().sort()
    sc.check('pack zip entries sorted (deterministic)', zip.names.every((n, i) => n === sorted[i]))
  }

  // ── HUD (10.2): 왼쪽 위 막대 셋 (HUD 보스 막대), 오른쪽 아래 소울 상자 (행동 막대), 경험치 레벨 0 ──
  const xp = b.p.xp
  sc.check('experience level always 0 (no green number)', xp.every((x) => x.level === 0), [...new Set(xp.map((x) => x.level))].join(',') || '경험치 패킷 없음')
  const glyphs = L.loadGlyphs()
  const lay = (() => { try { return require('fs').readFileSync(E.glyphs, 'utf8').match(/^layout:\s*\{(.*)\}/m)[1] } catch (e) { return '' } })()
  const mark = (k) => ((lay.match(new RegExp(k + ':\\s*"(#[0-9a-f]{6})"')) || [])[1] || '').toLowerCase()
  let hb = null
  for (let i = 0; i < 30 && !hb; i++) { hb = b.hudBar(); if (!hb) await L.sleep(100) }
  if (sc.check('HUD boss bar added after the pack loaded (white, its sprites are transparent)', !!hb, `보스 막대 패킷 ${b.p.bossbars.length}개`)) {
    const h = L.decodeHud(hb.parts, glyphs)
    sc.check('HUD bar text: souls:hud glyphs, left marker colour, net advance 0 (starts at the screen centre)',
      h.fonts.join() === 'souls:hud' && h.colors.join() === mark('mark_left') && h.advance === 0 && !h.unknown,
      `font=${h.fonts} color=${h.colors} (layout ${mark('mark_left')}) advance=${h.advance} unknown=${h.unknown}`)
    const full = ['hp', 'fp', 'st'].every((k) => h.bars[k] && h.bars[k].fill > 0 && !h.bars[k].empty && !h.bars[k].trail)
    sc.check('HUD bars hp, warmth, stamina full at rest', full, JSON.stringify(h.bars))
    const hud = await b.cmd('/soulstest hud', 'HUD')
    sc.checkCmd('HUD readout (glyph mode) matches the bar packet', hud, (r) => r.kv.mode === 'glyph' && h.bars.hp &&
      r.kv.hp === `${h.bars.hp.fill}/${h.bars.hp.fill + h.bars.hp.empty + h.bars.hp.trail}` &&
      r.kv.st === `${h.bars.st.fill}/${h.bars.st.fill + h.bars.st.empty + h.bars.st.trail}`, hud.line)
  }
  const abFrom = b.p.actionBars.length
  await L.sleep(2600)
  const bars = b.p.actionBars.slice(abFrom)
  sc.check('action bar refreshed (>= 2 in 2.6 s)', bars.length >= 2, bars.length + '번')
  const ab = b.p.actionBars[b.p.actionBars.length - 1]
  const sb = ab ? L.decodeHud(ab.parts, glyphs) : null
  sc.check('souls box: box glyph + digits "0", right marker colour, net advance 0', sb && sb.soulBox && sb.digits === '0' &&
    sb.colors.join() === mark('mark_right') && sb.advance === 0 && !sb.unknown, sb ? JSON.stringify(sb) : '행동 막대 없음')
  // 팩을 싣기 전 (그림 글자를 쓸 수 없을 때) 의 행동 막대는 번역 열쇠 souls.hud.souls 이고, 대체 글이 그 사람의 언어다 (10.9)
  const pre = b.p.actionBars.find((x) => L.translateKeys(x.raw)[0] === 'souls.hud.souls')
  sc.check('before the pack: action bar is the translatable souls.hud.souls', !!pre, b.p.actionBars.slice(0, 3).map((x) => JSON.stringify(x.plain)).join(' | ') || '행동 막대 없음')
  if (got.ok && pre) {
    const shown = L.render(pre.raw, L.langTable(L.readZip(got.buf), 'ko_kr'))
    sc.check('pre-pack action bar reads "소울 N" with the pack ko_kr', /^소울 [\d,]+$/.test(shown.trim()), JSON.stringify(shown))
  }
  if (pre) {
    const fb = L.render(pre.raw, {})
    sc.check('pre-pack action bar fallback (no pack) is Korean for a ko_kr client', /^소울 [\d,]+$/.test(fb.trim()), JSON.stringify(fb))
  }
  sc.check('food 20 (sprint allowed) at rest', b.food === 20, 'food=' + b.food)

  // ── 모험 모드 보호 (12.7, 13.4 표: 모험 모드에서 블록을 못 캐는지) ──
  const pos = b.bot.entity.position.floored()
  const below = b.bot.blockAt(pos.offset(0, -1, 0))
  if (below && below.name !== 'air') {
    b.bot.dig(below, true).catch(() => {})
    await L.sleep(2500)
    try { b.bot.stopDigging() } catch (e) {}
    const q = await b.cmd(`/execute if block ${below.position.x} ${below.position.y} ${below.position.z} minecraft:air`,
      (m) => m.parts.some((p) => p.translate && p.translate.startsWith('commands.execute.conditional')), 3000)
    const r = q.msg && q.msg.parts.find((p) => p.translate && p.translate.startsWith('commands.execute.conditional'))
    sc.check('adventure: floor block cannot be broken', r && r.translate === 'commands.execute.conditional.fail', `${below.name} → ${r ? r.translate : q.line || '답 없음'}`)
  } else sc.check('adventure: floor block cannot be broken', false, '발밑 블록을 찾지 못했다')

  sc.check('no kick during join scenario', !b.kick, b.kick || '')
})
