// 다시 접속 (8.1 "그 뒤로는 저장된 위치에서 들어온다", 10.10, 10.2, 3.2).
// 나갔다 들어오면 souls_world 의 나간 자리에 모험 모드로 서고, 팩을 다시 받고, HUD (막대 셋·소울 상자) 가 다시 오고, 스태미나가 찬다.
// 죽은 채로 나갔다 들어와도 일어서면 시험 방이다.
'use strict'
const L = require('./lib')

async function ready (b, sc, label) {
  const lg = b.p.login
  sc.check(`${label}: login into souls_world`, lg && /souls_world$/.test(lg.world), lg ? lg.world : 'login 없음')
  sc.check(`${label}: adventure`, lg && lg.gamemode === 'adventure', lg && lg.gamemode)
  const t0 = Date.now()
  while (!b.p.packs.length && Date.now() - t0 < 6000) await L.sleep(100)
  const pk = b.p.packs[0]
  sc.check(`${label}: pack offered again`, !!pk, pk ? pk.url : '')
  if (pk) {
    const got = await b.p.packChecks[0]
    sc.check(`${label}: pack download sha1 matches`, got.ok && got.hashMatch, got.ok ? got.sha1 : got.error)
  }
  await L.sleep(1500)
  const xp = b.lastXp()
  sc.check(`${label}: xp level 0`, !xp || xp.level === 0, xp ? `level=${xp.level}` : '')
  const hb = b.hudBar()
  const st = hb && L.decodeHud(hb.parts, L.loadGlyphs()).bars.st
  sc.check(`${label}: HUD bars sent again (stamina full)`, st && st.fill > 0 && !st.empty, st ? JSON.stringify(st) : 'HUD 보스 막대 없음')
  sc.check(`${label}: action bar sent`, b.p.actionBars.length > 0, b.p.actionBars.length ? JSON.stringify(b.p.actionBars[b.p.actionBars.length - 1].plain) : '')
}

L.run('reconnect', async (sc) => {
  // ── 첫 접속, 자리를 옮긴다 ──
  let b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/soulstest heal', 'HEAL')
  await b.cmd('/souls tp lane', null, 1200)
  await L.sleep(1200)
  const p1 = await b.cmd('/soulstest pos', 'POS')
  if (!sc.checkCmd('position readout', p1, (r) => r.kv.x !== undefined)) return
  await b.quit()
  sc.check('quit cleanly', b.ended)
  await L.sleep(1500)

  // ── 다시 들어온다 ──
  b = await L.connect(sc)
  await ready(b, sc, 'rejoin')
  const p2 = await b.cmd('/soulstest pos', 'POS')
  if (p2.kv) {
    const d = Math.hypot(L.num(p2.kv.x) - L.num(p1.kv.x), L.num(p2.kv.z) - L.num(p1.kv.z))
    sc.check('rejoin at the saved position (not the room spawn)', d < 1.5 && Math.abs(L.num(p2.kv.y) - L.num(p1.kv.y)) < 1.5,
      `나간 곳 (${p1.kv.x}, ${p1.kv.y}, ${p1.kv.z}) → (${p2.kv.x}, ${p2.kv.y}, ${p2.kv.z})`)
  }
  const st = await b.cmd('/soulstest stamina', 'STAMINA')
  sc.checkCmd('rejoin: stamina full, not exhausted', st, (r) => L.num(r.kv.cur) === L.num(r.kv.max) && r.kv.exhausted === 'false' && r.kv.food === '20', st.line)
  const info = await b.cmd('/soulstest info', 'INFO world')
  sc.checkCmd('rejoin: info world souls_world / ADVENTURE', info, (r) => r.kv.world === 'souls_world' && r.kv.mode === 'ADVENTURE', info.line)
  await b.quit()
  await L.sleep(1500)

  // ── 죽은 채로 나갔다 들어온다 ──
  b = await L.connect(sc, { respawn: false })
  await L.sleep(1200)
  await b.cmd('/soulstest kill', 'KILL')
  await L.sleep(1200)
  await b.quit()
  await L.sleep(1500)
  b = await L.connect(sc, { respawn: false, allowDead: true })
  await L.sleep(2000)
  const dead = b.p.health.some((h) => h.health <= 0)
  if (dead) {
    sc.note('죽은 채로 들어왔다 → 일어선다')
    const from = b.sys.length
    b.respawn()
    await L.sleep(2500)
    const rl = b.tLines('RESPAWN', from)[0]
    sc.check('dead rejoin: respawn works', rl && rl.kv.world === 'souls_world', rl ? rl.line : '부활 줄 없음')
  } else sc.note('죽은 채로 나갔지만 살아서 들어왔다 (서버가 먼저 일으켰다)')
  const room = L.testRoom()
  const pos = b.bot.entity.position
  sc.check('dead rejoin: alive in the test room', b.health > 0 && Math.abs(pos.x - room.x) <= 12.5 && Math.abs(pos.z - room.z) <= 12.5,
    `hp=${b.health} (${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)})`)
  const st2 = await b.cmd('/soulstest stamina', 'STAMINA')
  sc.checkCmd('dead rejoin: stamina full', st2, (r) => L.num(r.kv.cur) === L.num(r.kv.max), st2.line)
  sc.check('no kick during reconnect scenario', !b.kick, b.kick || '')
})
