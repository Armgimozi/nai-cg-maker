// 접속 (14 M0 "접속하면 팩을 받고 시험 방에 선다", 8.1, 10.2, 10.9, 10.10, 12.7).
// 첫 접속이 로비를 거치지 않고 souls_world 시험 방의 모험 모드로 서는지, 팩을 실제로 받아 SHA-1 이 맞는지,
// HUD (경험치 막대 = 스태미나, 레벨 0, 행동 막대 한 줄) 가 오는지, 모험 모드 보호로 블록이 안 캐지는지 본다.
// 봇은 한국어 클라이언트 (ko_kr) 로 들어온다: 팩 안내는 서버가 한국어로 채우고, 행동 막대는 번역 열쇠라 팩의 ko_kr 로 읽는다.
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

  // 받은 팩의 M0 기본 (10.9, 10.8, 10.2): 형식 75, 셰이더 없음, 스태미나 막대 그림, 투명 허기
  if (got.ok) {
    const zip = L.readZip(got.buf)
    const meta = zip.json('pack.mcmeta')
    const mp = meta && meta.pack
    sc.check('pack.mcmeta min/max_format 75', mp && JSON.stringify(mp.min_format) === '75' && JSON.stringify(mp.max_format) === '75',
      mp ? `min=${JSON.stringify(mp.min_format)} max=${JSON.stringify(mp.max_format)}` : 'pack.mcmeta 없음')
    sc.check('no core shaders in M0 pack', !zip.names.some((n) => /^assets\/[^/]+\/shaders\//.test(n)))
    const xpBar = ['experience_bar_background', 'experience_bar_progress'].map((n) => `assets/minecraft/textures/gui/sprites/hud/${n}.png`)
    sc.check('stamina bar sprites (experience_bar_*)', xpBar.every((n) => zip.has(n)), xpBar.filter((n) => !zip.has(n)).join(', '))
    const food = zip.names.filter((n) => /textures\/gui\/sprites\/hud\/food_[a-z_]+\.png$/.test(n))
    const opaque = food.filter((n) => { const im = L.decodePng(zip.get(n)); for (let i = 3; i < im.rgba.length; i += 4) if (im.rgba[i]) return true; return false })
    sc.check('hunger sprites transparent', food.length >= 6 && !opaque.length, `${food.length}개${opaque.length ? ', 보이는 것: ' + opaque.join(', ') : ''}`)
    const sorted = zip.names.slice().sort()
    sc.check('pack zip entries sorted (deterministic)', zip.names.every((n, i) => n === sorted[i]))
  }

  // ── HUD (10.2) ──
  const xp = b.p.xp
  sc.check('experience packet sent (stamina bar)', xp.length > 0, xp.length ? `bar=${xp[xp.length - 1].bar} level=${xp[xp.length - 1].level}` : '없음')
  sc.check('experience level always 0 (no green number)', xp.length > 0 && xp.every((x) => x.level === 0), [...new Set(xp.map((x) => x.level))].join(','))
  sc.check('stamina bar full at rest', xp.length > 0 && xp[xp.length - 1].bar >= 0.99, xp.length ? String(xp[xp.length - 1].bar) : '')
  const abFrom = b.p.actionBars.length
  await L.sleep(2600)
  const bars = b.p.actionBars.slice(abFrom)
  sc.check('action bar refreshed (>= 2 in 2.6 s)', bars.length >= 2, bars.length + '번')
  const ab = b.p.actionBars[b.p.actionBars.length - 1]
  // 행동 막대는 번역 열쇠 souls.hud.souls (10.3). 받은 팩의 ko_kr 표로 읽으면 "소울 0"
  const keys = ab ? L.translateKeys(ab.raw) : []
  sc.check('action bar is the translatable souls.hud.souls', keys[0] === 'souls.hud.souls', keys.join(',') || (ab ? JSON.stringify(ab.plain) : '행동 막대 없음'))
  if (got.ok && ab) {
    const shown = L.render(ab.raw, L.langTable(L.readZip(got.buf), 'ko_kr'))
    sc.check('action bar reads "소울 N" with the pack ko_kr', /^소울 [\d,]+$/.test(shown.trim()), JSON.stringify(shown))
  }
  // 팩이 아직 없거나 못 실었을 때 보이는 대체 글도 그 사람의 언어 (Lang.c(viewer, ...), 10.9)
  if (ab) {
    const fb = L.render(ab.raw, {})
    sc.check('action bar fallback (no pack) is Korean for a ko_kr client', /^소울 [\d,]+$/.test(fb.trim()), JSON.stringify(fb))
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
