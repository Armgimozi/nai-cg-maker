// 구르기와 무적 (3.3, 13.2 T3 roll_iframes). 지연 프록시로 다시 돌린다 (13.3, LAG_RTT).
// F(block_dig 상태 6) → 구르기: 종류·방향·비용, 서버가 보낸 첫 틱 속도와 미는 틱 수(glide), 서버에서 잰 거리,
// 기어가기 방벽(켜져 있으면), 회복 지연 (구르기 끝 + 12틱), 회복 중 다시 F, 공중·웅크리기 F 막힘, 스태미나 1 이상이면 구름.
// 수치는 서버의 config.yml (combat.roll) 에서 읽는다. 3.3 표는 출발값이고 조정은 설정에서 한다 (사용자 결정 1).
// 무적: 서버 시각 기준 (rollhit: 구르기 시작 뒤 n 틱에 generic 피해) 1~iframes 틱은 피하고 그 밖은 맞는다.
//       봇 시각 기준 (F 100ms 뒤 /soulstest hit) 원인 있는 피해는 피하고, 원인 없는 피해(환경)는 맞는다.
// 낙하 피해는 들어온다. 체력은 서버가 보낸 update_health 로도 따로 확인한다.
'use strict'
const L = require('./lib')

const VEL_TOL = 0.06
const RC = L.rollConfig()
const K = RC.kinds

// 구르기 하나: 키를 누르고 F. 돌려주는 값은 ROLL / ROLL_DENY 줄과 그 뒤 속도 패킷
async function roll (b, keys, wait = 1300) {
  b.input(keys)
  await L.sleep(120)
  const from = b.sys.length
  const v0 = b.p.vel.length
  b.swap()
  const r = await b.waitSys((m) => /^\[T\] ROLL(_DENY)? /.test(m.plain), 2000, from)
  await L.sleep(wait)
  b.input({})
  const line = r ? { line: r.plain, kv: L.kvOf(r.plain), deny: r.plain.startsWith('[T] ROLL_DENY') } : null
  const end = b.tLines('ROLLEND', from)[0] || null
  return { r: line, end, vel: b.p.vel.slice(v0), from }
}

async function fresh (b, where = 'lane') {
  await b.cmd('/soulstest heal', 'HEAL')
  await b.cmd('/souls tp ' + where, null, 1200)
  await L.sleep(500)
  await b.ground(3000)
  await L.sleep(200)
}

L.run('roll_iframes', async (sc) => {
  const E = L.ENV
  const b = await L.connect(sc)
  await L.sleep(1500)

  if (E.lagRtt) {
    const rtt = await b.rtt(4)
    sc.check(`lag proxy adds ~${E.lagRtt} ms round trip`, rtt >= E.lagRtt * 0.9, `명령 왕복 ${rtt} ms`)
  }

  // ── 앞 구르기 ── lane 은 동쪽(+x)을 본다
  sc.note(`구르기 수치 (${RC.source}): ` + JSON.stringify(K[RC.load]) + ' crawl=' + RC.crawl)
  await fresh(b)
  const st0 = await b.cmd('/soulstest stamina', 'STAMINA')
  if (!sc.checkCmd('stamina readout', st0, (r) => r.kv.cur !== undefined)) return
  const max = L.num(st0.kv.max)
  const kd = K[RC.load]
  const c0 = b.p.crawl.length
  const f = await roll(b, { forward: true })
  if (!sc.check('F rolls (ROLL line)', f.r && !f.r.deny, f.r ? f.r.line : 'ROLL 줄 없음')) return
  sc.check(`forward roll is ${RC.load} / fwd`, f.r.kv.kind === RC.load && f.r.kv.dir === 'fwd', f.r.line)
  sc.check(`${RC.load} roll costs ${kd.cost}`, Math.abs(L.num(f.r.kv.st) - (max - kd.cost)) < 0.5, `st=${f.r.kv.st} max=${max}`)
  const v = f.vel[0]
  sc.check('server sent roll velocity', !!v, v ? `(${v.x.toFixed(3)}, ${v.y.toFixed(3)}, ${v.z.toFixed(3)})` : '속도 패킷 없음')
  if (v) {
    const h = Math.hypot(v.x, v.z)
    sc.check(`first push horizontal ${kd.horizontal}, vertical ${kd.vertical}`, Math.abs(h - kd.horizontal) < VEL_TOL && Math.abs(v.y - kd.vertical) < VEL_TOL, `h=${h.toFixed(3)} y=${v.y.toFixed(3)}`)
    sc.check('rolls toward facing (+x on lane)', v.x > 0.25 && Math.abs(v.z) < 0.1, `x=${v.x.toFixed(3)} z=${v.z.toFixed(3)}`)
  }
  if (kd.glide) {
    const pushes = f.vel.filter((x) => Math.hypot(x.x, x.z) > 0.05).length
    sc.check(`push lasts ~${kd.glide} ticks`, pushes >= kd.glide - 1 && pushes <= kd.glide + 1, pushes + '번')
  }
  sc.check('roll moves the player (server measured)', f.end && L.num(f.end.kv.dist) > 1.0, f.end ? 'dist=' + f.end.kv.dist : 'ROLLEND 없음')
  if (RC.crawl) {
    const laid = b.p.crawl.slice(c0)
    sc.check('crawl: head-height barriers sent to this player', laid.length > 0, laid.length + '칸')
    await L.sleep(300)
    sc.check('crawl: barriers taken back after the roll', b.crawlLive.size === 0, b.crawlLive.size ? '남은 칸 ' + [...b.crawlLive].join(' ') : `${b.p.crawlRestored.length}칸 되돌림`)
  }
  const sr = await b.cmd('/soulstest stamina', 'STAMINA')
  if (sr.kv && f.r) {
    const from = L.num(sr.kv.regenFrom) - L.num(f.r.kv.t)
    const want = kd.end + 12
    sc.check(`stamina regen from roll start +${want} (end ${kd.end} + 12)`, Math.abs(from - want) <= 1, `regenFrom-ROLL=${from}`)
  }

  // ── 회복 중 다시 F ── next 틱째부터 다음 구르기를 받는다 (회복을 끊는다).
  // 둘째 F 는 next-2 틱 뒤 (땅에 내려선 뒤라 이유가 recovering), 셋째 F 는 next+3 틱 뒤 (받아야 한다)
  await fresh(b)
  b.input({ forward: true })
  await L.sleep(120)
  let from = b.sys.length
  b.swap()
  await L.sleep((kd.next - 2) * 50)
  b.swap()
  await L.sleep(5 * 50)
  b.swap()
  await L.sleep(900)
  b.input({})
  const tries = b.sys.slice(from).filter((m) => /^\[T\] ROLL(_DENY)? /.test(m.plain)).map((m) => ({ line: m.plain, kv: L.kvOf(m.plain) }))
  const txt = tries.map((x) => x.line).join(' | ')
  // 지연이 있으면 서버는 봇이 내려섰다는 위치를 늦게 받아 이유가 air 일 수 있다 (막히는 것은 같다)
  const why = E.lagRtt ? /ROLL_DENY why=(recovering|air)/ : /ROLL_DENY why=recovering/
  sc.check(`F at +${kd.next - 2} ticks is refused (recovering)`, tries.length >= 2 && tries[0].line.startsWith('[T] ROLL ') && why.test(tries[1].line), txt)
  sc.check(`F after tick ${kd.next} starts the next roll`, tries.length >= 3 && tries[2].line.startsWith('[T] ROLL ') && L.num(tries[2].kv.t) - L.num(tries[0].kv.t) >= kd.next, txt)

  // ── 뒷걸음 ── 방향키 없음
  await fresh(b)
  const kb = K.backstep
  const cb = b.p.crawl.length
  const bs = await roll(b, {})
  sc.check('no keys -> backstep', bs.r && bs.r.kv.kind === 'backstep' && bs.r.kv.dir === 'back', bs.r ? bs.r.line : '줄 없음')
  sc.check(`backstep costs ${kb.cost}`, bs.r && Math.abs(L.num(bs.r.kv.st) - (max - kb.cost)) < 0.5, bs.r ? 'st=' + bs.r.kv.st : '')
  const bv = bs.vel[0]
  sc.check(`backstep velocity points backward (${kb.horizontal})`, bv && bv.x < -0.2 && Math.abs(Math.hypot(bv.x, bv.z) - kb.horizontal) < VEL_TOL, bv ? `(${bv.x.toFixed(3)}, ${bv.y.toFixed(3)}, ${bv.z.toFixed(3)})` : '속도 없음')
  if (RC.crawl) sc.check('backstep does not crawl', b.p.crawl.length === cb, (b.p.crawl.length - cb) + '칸')

  // ── 옆 구르기 ── 오른쪽 (lane 이 동쪽을 보니 오른쪽은 남쪽 +z)
  await fresh(b)
  const rr = await roll(b, { right: true })
  sc.check('right key -> roll right', rr.r && rr.r.kv.dir === 'right' && rr.vel[0] && rr.vel[0].z > 0.25, rr.r ? rr.r.line + (rr.vel[0] ? ` vz=${rr.vel[0].z.toFixed(3)}` : '') : '줄 없음')

  // ── 웅크리기 + F ── 무기 기술 자리 (M3), 지금은 아무것도 하지 않는다
  await fresh(b)
  b.input({ shift: true })
  await L.sleep(250)
  from = b.sys.length
  b.swap()
  await L.sleep(700)
  b.input({})
  const sn = b.sys.slice(from).find((m) => m.plain.startsWith('[T] ROLL '))
  sc.check('sneak + F does not roll', !sn, sn ? sn.plain : '')

  // ── 공중 F ──
  await fresh(b)
  b.bot.setControlState('jump', true)
  b.input({ jump: true })
  await L.sleep(180)
  b.bot.setControlState('jump', false)
  from = b.sys.length
  b.swap()
  const air = await b.waitSys((m) => /^\[T\] ROLL(_DENY)? /.test(m.plain), 1500, from)
  b.input({})
  sc.check('F in the air is refused', air && /ROLL_DENY why=air/.test(air.plain), air ? air.plain : '줄 없음')
  await L.sleep(800)

  // ── 스태미나 1 이상이면 구른다 (모자라면 0 에서 멈춘다) ──
  await fresh(b)
  await b.cmd('/soulstest stamina set 5', 'STAMINA')
  const low = await roll(b, { forward: true }, 400)
  sc.check(`rolls with 5 stamina (cost ${kd.cost}), stops at 0`, low.r && !low.r.deny && L.num(low.r.kv.st) === 0, low.r ? low.r.line : '줄 없음')
  const zero = await roll(b, { forward: true }, 300)
  sc.check('no roll at 0 stamina', zero.r && /ROLL_DENY why=(stamina|recovering)/.test(zero.r.line), zero.r ? zero.r.line : '줄 없음')

  // ── 무적: 서버 시각 기준 ──
  const offsets = [1, 4, 8, 9, 12]
  for (const off of offsets) {
    await fresh(b)
    const hp0 = b.health
    const arm = await b.cmd(`/soulstest rollhit ${off} 2`, 'ROLLHIT armed')
    if (!sc.checkCmd(`rollhit ${off}: armed`, arm, (r) => !!r.line)) continue
    const h0 = b.p.health.length
    const rl = await roll(b, { forward: true }, 900)
    const hit = b.tLines('ROLLHIT off=', rl.from)[0]
    if (!hit) { sc.check(`rollhit ${off}: hit happened`, false, rl.r ? rl.r.line : '구르지 않았다'); continue }
    const ifr = L.num(hit.kv.iframes)
    const expect = off >= 1 && off <= ifr
    sc.check(`rollhit +${off} ticks: ${expect ? 'dodged' : 'lands'} (iframes 1..${ifr})`, hit.kv.dodged === String(expect), hit.line)
    const dropped = b.p.health.slice(h0).some((h) => h.health < hp0 - 0.5)
    sc.check(`rollhit +${off}: client health ${expect ? 'unchanged' : 'drops'}`, dropped === !expect, `hp ${hp0} → ${b.health}`)
  }

  // ── 무적: 봇 시각 기준 (F 를 누르고 100ms 뒤 피해 명령, 둘은 같은 길로 차례대로 간다) ──
  for (const [label, flags, dodge] of [['caused generic', '', true], ['no-cause generic (environment)', ' type=none', false]]) {
    await fresh(b)
    b.input({ forward: true })
    await L.sleep(120)
    const hp0 = b.health
    from = b.sys.length
    b.swap()
    await L.sleep(100)
    const h = await b.cmd('/soulstest hit 2' + flags, 'HIT ', 3000)
    b.input({})
    await L.sleep(300)
    const rl = b.tLines('ROLL ', from)[0]
    const tick = rl && h.kv ? L.num(h.kv.t) - L.num(rl.kv.t) : NaN
    if (!sc.checkCmd(`hit during roll window: ${label} -> ${dodge ? 'dodged' : 'lands'}`, h,
      (r) => rl && (dodge ? L.num(r.kv.dealt) === 0 : r.kv.full === 'true'), `+${tick}틱 ${h.line}`)) continue
    sc.check(`hit during roll window: ${label} landed inside i-frames`, tick >= 1 && tick <= 8, `+${tick}틱`)
    const dodgeLine = b.tLines('DODGE', from)[0]
    sc.check(`hit during roll window: ${label} ${dodge ? 'logs DODGE' : 'no DODGE'}`, !!dodgeLine === dodge, dodgeLine ? dodgeLine.line : '')
    await L.sleep(200)
    sc.check(`hit during roll window: ${label} client health`, dodge ? b.health >= hp0 - 0.01 : b.health <= hp0 - 1.5, `hp ${hp0} → ${b.health}`)
  }

  // ── 낙하 피해는 들어온다 (6칸 턱에서 걸어 내려간다) ──
  await fresh(b, 'ledge')
  const hp0 = b.health
  b.bot.setControlState('forward', true)
  b.input({ forward: true })
  await L.sleep(1400)
  b.bot.setControlState('forward', false)
  b.input({})
  await L.sleep(1200)
  sc.check('fall damage applies', b.health < hp0, `hp ${hp0} → ${b.health}`)
  await b.cmd('/soulstest heal', 'HEAL')
  sc.check('no kick during roll scenario', !b.kick, b.kick || '')
})
