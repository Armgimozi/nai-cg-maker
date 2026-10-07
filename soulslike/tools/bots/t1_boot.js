// T1 기동 (13.2): 플러그인 켜짐, 서버 기록에 오류 없음, /souls check FAIL 0, 게임 규칙·난이도·server.properties 가 12.7 대로,
// 시간이 13000 에 멈춤 (8.1), 세계 경계 (0, 20) 한 변 640 (8.1), 끝 세계를 띄우지 않음 (12.7).
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

// DESIGN.md 12.7 게임 규칙 (souls_world 와 로비 둘 다)
const RULES = {
  keep_inventory: 'true', immediate_respawn: 'false', natural_health_regeneration: 'false',
  spawn_mobs: 'false', spawn_monsters: 'false', spawn_patrols: 'false',
  spawn_phantoms: 'false', spawn_wandering_traders: 'false', spawn_wardens: 'false',
  raids: 'false', mob_griefing: 'false', show_advancement_messages: 'false',
  show_death_messages: 'true', advance_time: 'false', advance_weather: 'false',
  fire_spread_radius_around_player: '0', random_tick_speed: '0', pvp: 'false',
  mob_drops: 'false', block_drops: 'false', tnt_explodes: 'false',
  spread_vines: 'false', respawn_radius: '0', locator_bar: 'false',
  allow_entering_nether_using_portals: 'false', fall_damage: 'true',
  entity_drops: 'false', projectiles_can_break_blocks: 'false', spawner_blocks_work: 'false',
  universal_anger: 'false'
}

// DESIGN.md 12.7 server.properties
const PROPS = {
  gamemode: 'adventure', 'force-gamemode': 'true', difficulty: 'normal', 'spawn-protection': '0',
  'view-distance': '10', 'simulation-distance': '6', 'allow-flight': 'true', 'online-mode': 'true',
  'enforce-secure-profile': 'false', 'generate-structures': 'false', 'level-type': 'minecraft\\:flat',
  'max-players': '4', 'pause-when-empty-seconds': '60'
}
// 시험 서버가 일부러 바꾸는 값 (봇은 정품 계정이 없다)
const TEST_OVERRIDES = new Set(['online-mode', 'server-port'])

L.run('t1_boot', async (sc) => {
  const E = L.ENV

  // ── 서버 기록 ──
  if (E.serverLog && fs.existsSync(E.serverLog)) {
    const log = fs.readFileSync(E.serverLog, 'utf8').split(/\r?\n/)
    sc.check('plugin enabled', log.some((l) => /Enabling Soulslike/.test(l)), 'Enabling Soulslike 줄')
    // 난이도 (12.7 "다르면 바꾸고 크게 기록한다"). Bukkit 이 새로 만든 세계는 늘 easy 로 생긴다.
    // run_tests.sh 는 매번 빈 서버 폴더에서 켜므로 souls_world 는 새로 만들어지고 (level.dat 이 없었다),
    // 그때만 경고 한 줄 "을 새로 만들어 난이도를 ..." 이 나와야 한다. SEVERE 띠 ("난이도가 ... 입니다") 는
    // 이미 있던 세계가 어긋났을 때의 것이라 깨끗한 기동에서는 나오면 안 된다.
    const fresh = log.filter((l) => /\[Soulslike\].*을 새로 만들어 난이도를/.test(l))
    sc.check('fresh souls_world: one WARN line fixing its difficulty to normal', fresh.length === 1 && /WARN\]/.test(fresh[0]),
      fresh.map((l) => l.replace(/^.*?\[Soulslike\] /, '')).join(' / ').slice(0, 300) || '줄 없음')
    const fix = log.filter((l) => /\[Soulslike\].*난이도가 .* 입니다/.test(l))
    sc.check('no difficulty drift banner on a clean boot', fix.length === 0, fix.map((l) => l.replace(/^.*\[Soulslike\] /, '')).join(' / ').slice(0, 300))
    const banner = (l) => /\[Soulslike\] =+\s*$/.test(l)
    const errs = log.filter((l) => /\b(ERROR|SEVERE)\]|Exception|Caused by:/.test(l) && !fix.includes(l) && !banner(l))
    sc.check('server log has no other ERROR/exception', errs.length === 0, errs.length ? errs.length + '줄: ' + errs.slice(0, 4).join(' / ').slice(0, 600) : '')
    const warns = log.filter((l) => /WARN\]: \[Soulslike\]/.test(l))
    if (warns.length) sc.note('Soulslike 경고 ' + warns.length + '줄: ' + warns.slice(0, 4).join(' / ').slice(0, 500))
  } else {
    sc.note('SERVER_LOG 가 없어 서버 기록 검사는 건너뛴다')
  }

  // ── server.properties (원본은 12.7 그대로, 시험 서버는 online-mode·포트만 다르다) ──
  const src = L.readProps(path.join(E.root, 'server', 'server.properties'))
  if (src) {
    const bad = Object.entries(PROPS).filter(([k, v]) => src[k] !== v).map(([k, v]) => `${k}=${src[k]} (기대 ${v})`)
    if (src['generator-settings'] === undefined || !src['generator-settings'].includes('minecraft\\:air')) bad.push('generator-settings 에 공기 한 층이 없다')
    sc.check('server/server.properties matches 12.7', bad.length === 0, bad.join(', '))
  } else sc.miss('server/server.properties matches 12.7', 'soulslike/server/server.properties 가 없다')
  if (E.serverDir) {
    const run = L.readProps(path.join(E.serverDir, 'server.properties'))
    if (run) {
      const bad = Object.entries(PROPS).filter(([k, v]) => !TEST_OVERRIDES.has(k) && run[k] !== v).map(([k, v]) => `${k}=${run[k]} (기대 ${v})`)
      sc.check('running server.properties matches 12.7 (except test overrides)', bad.length === 0, bad.join(', '))
    }
    sc.check('end world not created (bukkit.yml allow-end false)', !fs.existsSync(path.join(E.serverDir, 'world_the_end')))
    if (fs.existsSync(path.join(E.serverDir, 'world_nether'))) sc.note('world_nether 폴더가 있다 (네더를 끄는 설정이 듣지 않았다)')
  }

  const b = await L.connect(sc)
  await L.sleep(1500)

  // ── /souls check ──
  const from = b.sys.length
  b.bot.chat('/souls check')
  const end = await b.waitSys((m) => m.plain.startsWith('[CHECK] done') || m.parts.some((p) => p.translate === 'command.unknown.command'), 6000, from)
  if (!end) sc.check('/souls check answered', false, '답 없음')
  else if (!end.plain.startsWith('[CHECK]')) sc.miss('/souls check answered', '명령어 없음')
  else {
    const lines = b.sys.slice(from).filter((m) => m.plain.startsWith('[CHECK] ')).map((m) => m.plain)
    for (const l of lines) {
      if (l.startsWith('[CHECK] FAIL ')) sc.check('check: ' + l.slice(13).split(' ').slice(0, 2).join(' '), false, l)
    }
    sc.check('/souls check FAIL 0', /FAIL 0\s*$/.test(end.plain), end.plain)
    for (const l of lines.filter((x) => x.startsWith('[CHECK] OK '))) sc.note(l)
  }

  // ── 게임 규칙 (바닐라 /gamerule 로 직접 묻는다) ──
  for (const [label, prefix] of [['souls_world', ''], ['lobby', 'execute in minecraft:overworld run ']]) {
    const bad = []
    for (const [rule, want] of Object.entries(RULES)) {
      const r = await b.cmd('/' + prefix + 'gamerule ' + rule, (m) => m.parts.some((p) => p.translate === 'commands.gamerule.query' && p.with && p.with[0] === rule) ||
        m.parts.some((p) => p.translate && /^(argument|command|commands\.gamerule)\./.test(p.translate) && p.translate !== 'commands.gamerule.query'), 3000)
      const q = r.msg && r.msg.parts.find((p) => p.translate === 'commands.gamerule.query')
      if (!q) bad.push(rule + '=? (' + (r.timeout ? '답 없음' : r.line) + ')')
      else if (String(q.with[1]) !== want) bad.push(`${rule}=${q.with[1]} (기대 ${want})`)
      await L.sleep(40)
    }
    sc.check(`gamerules ${label} (${Object.keys(RULES).length})`, bad.length === 0, bad.join(', '))
  }

  // ── 난이도 ──
  for (const [label, prefix] of [['souls_world', ''], ['lobby', 'execute in minecraft:overworld run ']]) {
    const r = await b.cmd('/' + prefix + 'difficulty', (m) => m.parts.some((p) => p.translate === 'commands.difficulty.query'), 3000)
    const q = r.msg && r.msg.parts.find((p) => p.translate === 'commands.difficulty.query')
    sc.check(`difficulty ${label} = normal`, q && /normal/i.test(q.with.join(',')), q ? q.with.join(',') : (r.line || '답 없음'))
  }
  const dp = b.p.difficulty[b.p.difficulty.length - 1]
  sc.check('difficulty packet = normal', dp && dp.difficulty === 'normal', dp ? dp.difficulty : '패킷 없음')

  // ── 시간·날씨·경계 (8.1) ──
  await L.sleep(1500)
  const times = b.p.time
  const tod = times.map((x) => ((x.time % 24000) + 24000) % 24000)
  sc.check('time frozen at 13000', times.length > 0 && tod.every((v) => Math.abs(v - 13000) <= 2) && times.every((x) => x.ticking === false),
    times.length ? `시각 ${[...new Set(tod)].join(',')} 흐름=${[...new Set(times.map((x) => x.ticking))].join(',')}` : 'update_time 없음')
  sc.check('no rain', !b.p.gameState.some((g) => g.reason === 'start_raining'))
  const bd = b.p.border[b.p.border.length - 1]
  sc.check('world border center (0, 20) size 640', bd && Math.abs(bd.x) < 0.01 && Math.abs(bd.z - 20) < 0.01 && Math.abs(bd.size - 640) < 0.01,
    bd ? `(${bd.x}, ${bd.z}) ${bd.size}` : '경계 패킷 없음')

  // ── 틱 시간 ──
  const pf = await b.cmd('/souls perf', (m) => /server avg tick/.test(m.plain), 3000)
  if (pf.missing) sc.miss('MSPT under 20', '/souls perf 없음')
  else {
    const ms = pf.line ? parseFloat((pf.line.match(/([\d.]+)\s*ms/) || [])[1]) : NaN
    sc.check('MSPT under 20', ms < 20, pf.line || '답 없음')
  }
})
