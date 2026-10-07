// 스태미나 (3.2, 10.2): 달리면 줄고 (틱당 0.6, 그동안 회복 없음), 멈추면 12틱 뒤부터 틱당 2.2 씩 찬다.
// 0 이 되면 탈진: 허기 6 (달리기 막힘), 회복 지연 24틱, 25 까지 차면 허기 20. 경험치 막대가 스태미나를 따른다 (레벨 0).
'use strict'
const L = require('./lib')

// 두 시험 줄 사이의 틱당 변화량
const rate = (a, b) => (L.num(b.kv.cur) - L.num(a.kv.cur)) / Math.max(1, L.num(b.kv.t) - L.num(a.kv.t))

L.run('stamina', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1500)
  await b.cmd('/soulstest heal', 'HEAL')
  await L.sleep(800)

  const s0 = await b.cmd('/soulstest stamina', 'STAMINA')
  if (!sc.checkCmd('stamina readout', s0, (r) => r.kv.cur !== undefined)) return
  sc.check('full at rest', L.num(s0.kv.cur) === L.num(s0.kv.max), s0.line)
  sc.check('max 100 at endurance 10 (3.2)', L.num(s0.kv.max) === 100, 'max=' + s0.kv.max)

  // ── 달리기 ── 시험 방 남쪽 벽 앞에서 북쪽(-z)으로 22칸쯤 달릴 수 있다
  await b.bot.look(0, 0, true) // mineflayer 시선 0 = 북쪽
  b.sprint(true)
  await L.sleep(700)
  const s1 = await b.cmd('/soulstest stamina', 'STAMINA')
  await L.sleep(700)
  const s2 = await b.cmd('/soulstest stamina', 'STAMINA')
  const xpRun = b.lastXp()
  b.sprint(false)
  sc.check('server sees sprinting', s1.kv && s1.kv.sprinting === 'true', s1.line)
  sc.check('sprint drains stamina', s2.kv && L.num(s2.kv.cur) < L.num(s0.kv.cur) - 5, s2.line)
  const drain = s1.kv && s2.kv ? -rate(s1, s2) : NaN
  sc.check('drain ~0.6 per tick, no regen while sprinting', Math.abs(drain - 0.6) <= 0.2, 'drain=' + drain.toFixed(3) + '/틱')
  sc.check('xp bar follows stamina while sprinting', xpRun && Math.abs(xpRun.bar - L.num(s2.kv.ratio)) < 0.06 && xpRun.bar < 0.97,
    xpRun ? `bar=${xpRun.bar.toFixed(3)} ratio=${s2.kv.ratio}` : '경험치 패킷 없음')
  sc.check('xp level stays 0 while sprinting', b.p.xp.every((x) => x.level === 0))

  // 멈춘 뒤 첫 시험 줄: 회복은 멈춘 틱 + 12 부터 (regenFrom)
  const stop = await b.cmd('/soulstest stamina', 'STAMINA')
  if (stop.kv) {
    const left = L.num(stop.kv.regenFrom) - L.num(stop.kv.t)
    sc.check('regen held ~12 ticks after sprint stops', left >= 8 && left <= 13, `regenFrom-t=${left}`)
  }

  // ── 회복 속도 ── 30 으로 내려 두고 잰다 (set 은 지금부터 regen-delay 동안 회복을 멈춘다)
  await L.sleep(300)
  const a = await b.cmd('/soulstest stamina set 30', 'STAMINA')
  await L.sleep(250)
  const d1 = await b.cmd('/soulstest stamina', 'STAMINA')
  await L.sleep(550)
  const r1 = await b.cmd('/soulstest stamina', 'STAMINA')
  await L.sleep(250)
  const r2 = await b.cmd('/soulstest stamina', 'STAMINA')
  if (a.kv && d1.kv && r1.kv && r2.kv) {
    const dt = L.num(d1.kv.t) - L.num(a.kv.t)
    sc.check('no regen during the delay', dt >= 12 || L.num(d1.kv.cur) === 30, `+${dt}틱 cur=${d1.kv.cur}`)
    const rr = rate(r1, r2)
    const capped = L.num(r2.kv.cur) >= L.num(r2.kv.max)
    sc.check('regen ~2.2 per tick after delay', capped ? L.num(r1.kv.cur) > 30 : Math.abs(rr - 2.2) <= 0.3,
      `${r1.kv.cur}@${r1.kv.t} → ${r2.kv.cur}@${r2.kv.t} (${rr.toFixed(2)}/틱)`)
  } else sc.check('regen readouts', false, '시험 줄이 빠졌다')

  // ── 탈진 ── 10 에서 달려 0 을 만든다 (시험 명령으로 0 을 넣는 대신 실제 길로)
  await L.sleep(1200)
  await b.cmd('/souls tp room', null, 1500)
  await b.cmd('/soulstest heal', 'HEAL')
  await L.sleep(600)
  await b.bot.look(0, 0, true)
  await b.cmd('/soulstest stamina set 10', 'STAMINA')
  b.sprint(true)
  await L.sleep(1300) // 0.6/틱이면 17틱에 바닥
  const z = await b.cmd('/soulstest stamina', 'STAMINA')
  sc.checkCmd('sprinting to 0 exhausts', z, (r) => L.num(r.kv.cur) === 0 && r.kv.exhausted === 'true', z.line)
  await L.sleep(300)
  sc.check('exhausted -> food 6 (client stops sprinting)', b.food === 6, 'food=' + b.food)
  const xp0 = b.lastXp()
  sc.check('xp bar empty at 0', xp0 && xp0.bar <= 0.01, xp0 ? 'bar=' + xp0.bar : '')
  b.sprint(false)
  await L.sleep(150)
  const ez = await b.cmd('/soulstest stamina', 'STAMINA')
  if (ez.kv) {
    const left = L.num(ez.kv.regenFrom) - L.num(ez.kv.t)
    sc.check('exhausted regen delay ~24 ticks', left >= 19 && left <= 25, `regenFrom-t=${left} (${ez.line})`)
  }
  await L.sleep(700)
  const e1 = await b.cmd('/soulstest stamina', 'STAMINA')
  if (e1.kv && ez.kv) {
    const held = L.num(e1.kv.t) < L.num(ez.kv.regenFrom)
    sc.check('no regen while exhausted delay runs', !held || L.num(e1.kv.cur) === 0, e1.line)
    sc.check('still exhausted below 25', L.num(e1.kv.cur) >= 25 || e1.kv.exhausted === 'true', e1.line)
  }
  await L.sleep(2000)
  const e2 = await b.cmd('/soulstest stamina', 'STAMINA')
  sc.check('recovers to >= 25 and leaves exhaustion', e2.kv && L.num(e2.kv.cur) >= 25 && e2.kv.exhausted === 'false', e2.line)
  await L.sleep(200)
  sc.check('food back to 20 after exhaustion', b.food === 20, 'food=' + b.food)
})
