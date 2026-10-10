// 짧은 누름의 늦음과 지연 (13.3 의 TAPLAT, 3.3, 2.3 의 11). 구르기 키가 웅크리기로 바뀌며 구르기는 뗄 때 나간다: 누른 시간만큼 늦고,
// 지연이 흔들리면 짧은 누름이 길게 읽힐 수 있다. 봇이 보낸 누름 길이와 서버의 ROLL_TAP held (틱) 를 견준다. 지연 프록시로 0/60/120ms 를 돈다.
//   1. 2틱 (100ms) 누름 20번: 모두 구른다. held 는 2 (봇의 타이머와 서버 틱의 자리 때문에 ±1 은 받아 준다), 지연이 고르면 지연과 상관없다.
//   2. 10틱 (500ms) 누름 20번: 모두 웅크리기 (ROLL_TAP_SKIP why=hold), 구르기 0번.
//   3. 핑이 controls.roll-tap.lag-ping (100ms) 을 넘으면 창이 max-ticks + lag-extra-ticks (5 + 1 = 6틱) 로 늘어 6틱 누름도 구른다.
//      어느 판이든 "held <= window 이면 구르고 넘으면 구르지 않는다" 가 모든 누름에서 맞는다.
//   4. 봇 시각으로 누름 → ROLL 줄 (ms): 누른 시간 + 왕복 지연 + 틱 맞춤. TAPLAT 줄로 남긴다 (run_tests.sh 가 지연별로 모은다).
'use strict'
const L = require('./lib')

const RC = L.rollConfig()

L.run('taplat', async (sc) => {
  if (RC.rollKey === 'f') {
    sc.note('controls.roll-key: f 판에는 짧은 누름이 없다 (건너뛴다)')
    sc.check('roll-key f: nothing to measure', true)
    return
  }
  const E = L.ENV
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp lane', null, 1200)
  await L.sleep(500)
  await b.ground(3000)
  if (E.lagRtt) {
    const rtt = await b.rtt(4)
    sc.check(`lag proxy adds ~${E.lagRtt} ms round trip`, rtt >= E.lagRtt * 0.9, `명령 왕복 ${rtt} ms`)
    await L.sleep(3000) // 서버가 잰 핑 (keep-alive) 이 지연을 따라오게
  }
  const kind = RC.kinds[RC.load] || RC.kinds.light
  const rows = []
  async function one (holdMs) {
    await b.cmd('/soulstest stamina set 200', 'STAMINA')
    b.input({ forward: true })
    await L.sleep(120)
    const from = b.sys.length
    const t0 = Date.now()
    await b.tapSneak({ forward: true }, holdMs)
    const res = await b.waitSys((m) => /^\[T\] ROLL_TAP(_SKIP)? /.test(m.plain), 1500, from)
    const roll = await b.waitT('ROLL ', holdMs > 250 ? 400 : 1200, from)
    await L.sleep(Math.max(0, (kind.next + 3) * 50 - (Date.now() - t0) + holdMs))
    b.input({})
    await L.sleep(150)
    const kv = res ? L.kvOf(res.plain) : {}
    const r = { hold: holdMs, held: L.num(kv.held), window: L.num(kv.window), why: kv.why || null, tap: !!res && res.plain.startsWith('[T] ROLL_TAP '), roll: !!roll, ms: roll ? roll.t - t0 : NaN }
    rows.push(r)
    return r
  }

  const short = []
  for (let i = 0; i < 20; i++) short.push(await one(100))
  const longs = []
  for (let i = 0; i < 20; i++) longs.push(await one(500))
  const six = []
  const lagWin = E.lagRtt > 100
  if (lagWin) for (let i = 0; i < 10; i++) six.push(await one(300))

  const dist = (a) => { const m = {}; for (const r of a) m[r.held] = (m[r.held] || 0) + 1; return Object.entries(m).map(([k, v]) => `${k}:${v}`).join(' ') }
  const med = (a) => { const s = a.filter((x) => !isNaN(x)).sort((x, y) => x - y); return s.length ? s[s.length >> 1] : NaN }
  const heldOk = short.filter((r) => r.held >= 1 && r.held <= 3).length
  const rolled = short.filter((r) => r.roll).length
  const holdRoll = longs.filter((r) => r.roll).length
  const win = med(short.map((r) => r.window))
  console.log(`TAPLAT rtt=${E.lagRtt} window=${win} held=${dist(short)} held_ok=${heldOk}/20 roll=${rolled}/20 hold_roll=${holdRoll}/20` +
    (lagWin ? ` six_held=${dist(six)} six_roll=${six.filter((r) => r.roll).length}/10` : '') + ` press_to_roll_ms=${med(short.map((r) => r.ms))}`)
  sc.check(`2-tick taps: server reads held 1..3 (most 2) in ${heldOk}/20`, heldOk >= 19 && short.filter((r) => r.held === 2).length >= 14, dist(short))
  sc.check('2-tick taps: all 20 roll', rolled === 20, `${rolled}/20 ` + short.filter((r) => !r.roll).map((r) => `held=${r.held} why=${r.why}`).join(','))
  sc.check('10-tick holds: none roll (ROLL_TAP_SKIP why=hold)', holdRoll === 0 && longs.every((r) => r.why === 'hold'), dist(longs) + ' ' + longs.filter((r) => r.why !== 'hold').map((r) => r.why).join(','))
  sc.check(`tap window ${lagWin ? '6 (ping over lag-ping adds a tick)' : '5'}`, win === (lagWin ? 6 : 5), `window=${win}`)
  if (lagWin) sc.check('ping over 100 ms: 6-tick presses roll when held <= 6', six.filter((r) => r.held <= 6).every((r) => r.roll) && six.some((r) => r.roll), dist(six))
  const bad = rows.filter((r) => (r.held <= r.window) !== r.roll && r.why !== 'buffer')
  sc.check('every press: rolls exactly when held <= window', bad.length === 0, bad.map((r) => `hold ${r.hold}ms held=${r.held} win=${r.window} roll=${r.roll} why=${r.why}`).join(' | '))
  const ms = med(short.map((r) => r.ms))
  sc.note(`누름 → ROLL 줄 (봇 시각, 가운데 값) ${ms} ms = 누른 100ms + 왕복 ${E.lagRtt}ms + 틱 맞춤`)
  sc.check('press-to-roll latency = hold time + round trip (+ at most ~2 ticks)', ms >= 100 + E.lagRtt * 0.8 && ms <= 100 + E.lagRtt + 120, `${ms} ms`)
  sc.check('no kick during tap latency scenario', !b.kick, b.kick || '')
})
