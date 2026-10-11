// 구르기와 무적 (3.3, 13.2 T3 roll_iframes). 지연 프록시로 다시 돌린다 (13.3, LAG_RTT).
// 구르기 키는 서버 설정 controls.roll-key 를 따른다 (2.1): sneak (기본) 이면 웅크리기를 짧게 눌렀다 뗀다 (player_input 의 shift 깃발,
// 뗄 때 판정), f 면 F (block_dig 상태 6), both 면 웅크리기로 구른다 (F 도 구른다). 아래 "F" 는 그 구르기 키를 말한다.
// 웅크리기 판에서는 더: 회복 중에 뗀 짧은 누름은 기억했다가 되는 첫 틱에 구른다 (ROLL_TAP_BUFFER), F 는 구르지 않고 패링
// (PARRY 줄, 왼손에 든 것으로), 길게 누르면 웅크리기 (ROLL_TAP_SKIP why=hold), 누르는 동안 휘두르면 조합 (why=attack).
// 구르기: 서버가 보낸 첫 틱 속도와 미는 틱 수(glide), 서버에서 잰 거리,
// 보이는 모습 (tumble: 관절 대역의 부위 표시 물체 두 벌이 타고 (봇은 자기 벌 열하나 이상을 받는다) 투명 깃발이 섰다가 걷힌다, 뒷걸음은 대역 없음 / crawl·tumble 에 combat.roll.crawl 이면: 기어가기 막힘이 깔리고 걷힘), 회복 지연 (구르기 끝 + 12틱), 회복 중 다시 F, 공중·웅크리기 F 막힘, 스태미나 1 이상이면 구름.
// 수치는 서버의 config.yml (combat.roll) 에서 읽는다. 3.3 표는 출발값이고 조정은 설정에서 한다 (사용자 결정 1).
// 무적: 서버 시각 기준 (rollhit: 구르기 시작 뒤 n 틱에 generic 피해) 1~iframes 틱은 피하고 그 밖은 맞는다.
//       F 뒤 같은 길로 /soulstest hit: 원인 있는 피해는 피하고, 원인 없는 피해(환경)는 맞는다.
//       위 둘은 서버가 처리하는 차례가 지연과 상관없어 지연으로는 실패할 수 없다 (지연 판에서는 연기 시험일 뿐이다).
//       자기 화면 기준 (warn, 13.3): 서버가 "[T] WARN hit_in=k" 를 보내고 k 틱 뒤에 때린다. 봇은 그 줄을 받은 순간 F 를
//       누른다. 이것만 왕복 지연에 따라 달라진다: F 가 서버에 닿는 늦음(틱)이 지연만큼 커지는지 보고, 피한 비율을 남긴다.
//       M0 에는 피격 대기열(3.9)이 없어 지연이 길면 피한 비율이 준다. M1 의 대기열이 세 지연에서 같게 만들어야 한다.
// 순간이동하면 남은 밀기를 멈춘다 (도착한 곳에서 미끄러지지 않는다).
// 낙하 피해는 들어온다. 체력은 서버가 보낸 update_health 로도 따로 확인한다.
'use strict'
const L = require('./lib')

const VEL_TOL = 0.06
const RC = L.rollConfig()
const K = RC.kinds
const SNEAK = RC.rollKey !== 'f'
const KEY = SNEAK ? 'sneak tap' : 'F'

// 구르기 하나: 키를 누르고 F. 돌려주는 값은 ROLL / ROLL_DENY 줄과 그 뒤 속도 패킷
async function roll (b, keys, wait = 1300) {
  b.input(keys)
  await L.sleep(120)
  const from = b.sys.length
  const v0 = b.p.vel.length
  await b.rollKey(keys)
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
  // 체력은 큰 숫자 (최대 HP 400~1500), 화면은 하트 10개 (5.2): 클라이언트 체력 1 = 서버 HP S
  const S = await b.hpScale()
  sc.note(`구르기 키 ${RC.rollKey} (controls.roll-key), 무게 ${RC.auto ? 'auto' : RC.load}, 하트 배율 ${S}`)

  if (E.lagRtt) {
    const rtt = await b.rtt(4)
    sc.check(`lag proxy adds ~${E.lagRtt} ms round trip`, rtt >= E.lagRtt * 0.9, `명령 왕복 ${rtt} ms`)
  }

  // ── 앞 구르기 ── lane 은 동쪽(+x)을 본다
  sc.note(`구르기 수치 (${RC.source}): ` + JSON.stringify(K[RC.load]) + ' visual=' + RC.visual + ' crawl=' + RC.crawl)
  await fresh(b)
  const st0 = await b.cmd('/soulstest stamina', 'STAMINA')
  if (!sc.checkCmd('stamina readout', st0, (r) => r.kv.cur !== undefined)) return
  const max = L.num(st0.kv.max)
  const kd = K[RC.load]
  const c0 = b.p.crawl.length
  const tv0 = { pas: b.p.passengers.length, flags: b.p.flags.length, spawned: b.p.spawned.length, destroyed: b.p.destroyed.length }
  const f = await roll(b, { forward: true })
  if (!sc.check(`${KEY} rolls (ROLL line)`, f.r && !f.r.deny, f.r ? f.r.line : 'ROLL 줄 없음')) return
  if (SNEAK) {
    const tap = b.tLines('ROLL_TAP ', f.from)[0]
    sc.check('sneak tap judged on release (ROLL_TAP held <= window)', tap && L.num(tap.kv.held) <= L.num(tap.kv.window), tap ? tap.line : 'ROLL_TAP 없음')
  }
  if (RC.auto) {
    const ld = await b.cmd('/soulstest load', 'LOAD ')
    sc.check('roll kind follows equip load (auto): starting kit is light', ld.kv && ld.kv.tier === 'light' && f.r.kv.kind === 'light', ld.line || '')
  }
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
    // 밀기는 1..glide 틱째에 한 번씩. F 를 받은 자리에서 밀면 다음 틱의 밀기가 덮어 하나가 사라졌다 (그래서 정확히 센다)
    const pushes = f.vel.filter((x) => Math.hypot(x.x, x.z) > 0.05).length
    sc.check(`push lasts exactly ${kd.glide} ticks`, pushes === kd.glide, pushes + '번')
  }
  sc.check('roll moves the player (server measured)', f.end && L.num(f.end.kv.dist) > 1.0, f.end ? 'dist=' + f.end.kv.dist : 'ROLLEND 없음')
  if (RC.visual === 'tumble') {
    // 대역 (3.3): 관절 대역의 부위 표시 물체 (머리·가슴·배·팔 넷·다리 넷 = 열하나, 투구·든 것이 있으면 더) 두 벌이 이 봇에 타고
    // (그 사람에게만 보이는 벌과 남에게 보이는 벌. 봇은 자기 벌만 받는다), 봇의 공유 깃발에 투명 (0x20) 이 섰다가, 구르기 뒤 봇이 받은
    // 물체는 모두 지워지고 깃발은 걷힌다. 미는 힘·무적 판정은 위와 같다 (대역은 보이는 것만 바꾼다).
    // 탑승은 하나씩 붙어 탑승 목록 패킷이 여럿 온다: 가장 긴 것을 본다
    const rides = b.p.passengers.slice(tv0.pas)
    const riders = rides.reduce((m, x) => (x.ids.length > m.length ? x.ids : m), [])
    sc.check('tumble: articulated stand-in (>= 11 part displays) rides this player during the roll', riders.length >= 11, JSON.stringify(rides.map((x) => x.ids.length)))
    const got = new Set(b.p.spawned.slice(tv0.spawned).map((x) => x.id))
    const mine = riders.filter((id) => got.has(id))
    const gone = new Set([].concat(...b.p.destroyed.slice(tv0.destroyed).map((x) => x.ids)))
    sc.check('tumble: stand-in parts this player received (>= 11) removed after the roll', mine.length >= 11 && mine.every((id) => gone.has(id)), `탄 물체 ${riders.length}, 받은 것 ${mine.length}, 지운 물체 ${gone.size}`)
    const fl = b.p.flags.slice(tv0.flags).map((x) => x.value)
    sc.check('tumble: invisible flag set during the roll and cleared after', fl.some((v) => v & 0x20) && fl.length > 0 && !(fl[fl.length - 1] & 0x20), fl.map((v) => '0x' + v.toString(16)).join(' '))
  }
  // 기어가기 막힘 (combat.roll.crawl): crawl 과 tumble 모습이 깐다 (tumble 은 duck 틱 동안. 봇 시험은 기본으로 끈다: run_tests --crawl)
  if (RC.crawl && (RC.visual === 'crawl' || RC.visual === 'tumble')) {
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
  // F 판: 둘째 F 는 next-2 틱 뒤 (땅에 내려선 뒤라 이유가 recovering), 셋째 F 는 next+3 틱 뒤 (받아야 한다)
  // 웅크리기 판: next-2 틱 뒤에 뗀 둘째 누름은 기억했다가 (ROLL_TAP_BUFFER) next 틱째에 구른다 (ROLL_TAP_BUFFERED)
  let from
  if (SNEAK) {
    await fresh(b)
    b.input({ forward: true })
    await L.sleep(120)
    from = b.sys.length
    await b.tapSneak({ forward: true })
    await L.sleep(Math.max(0, (kd.next - 2) * 50 - 80))
    await b.tapSneak({ forward: true })
    await L.sleep(1200)
    b.input({})
    const rolls = b.tLines('ROLL ', from)
    const buf = b.tLines('ROLL_TAP_BUFFER ', from)
    const done = b.tLines('ROLL_TAP_BUFFERED', from)
    const txt = b.sys.slice(from).filter((m) => /^\[T\] ROLL(_TAP|_DENY)?[ _]/.test(m.plain)).map((m) => m.plain).join(' | ')
    sc.check(`tap released at +${kd.next - 2} ticks is buffered (ROLL_TAP_BUFFER)`, rolls.length >= 1 && buf.length === 1, txt)
    const gap = rolls.length >= 2 ? L.num(rolls[1].kv.t) - L.num(rolls[0].kv.t) : NaN
    sc.check(`buffered tap rolls at tick ${kd.next} (ROLL_TAP_BUFFERED)`, done.length === 1 && gap >= kd.next && gap <= kd.next + 1, `간격 ${gap}틱 | ` + txt)
  } else {
    await fresh(b)
    b.input({ forward: true })
    await L.sleep(120)
    from = b.sys.length
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
  }

  // ── 뒷걸음 ── 방향키 없음
  await fresh(b)
  const kb = K.backstep
  const cb = b.p.crawl.length
  const pb = b.p.passengers.length
  const bs = await roll(b, {})
  sc.check('no keys -> backstep', bs.r && bs.r.kv.kind === 'backstep' && bs.r.kv.dir === 'back', bs.r ? bs.r.line : '줄 없음')
  sc.check(`backstep costs ${kb.cost}`, bs.r && Math.abs(L.num(bs.r.kv.st) - (max - kb.cost)) < 0.5, bs.r ? 'st=' + bs.r.kv.st : '')
  const bv = bs.vel[0]
  sc.check(`backstep velocity points backward (${kb.horizontal})`, bv && bv.x < -0.2 && Math.abs(Math.hypot(bv.x, bv.z) - kb.horizontal) < VEL_TOL, bv ? `(${bv.x.toFixed(3)}, ${bv.y.toFixed(3)}, ${bv.z.toFixed(3)})` : '속도 없음')
  sc.check(`backstep first push hops (vertical ${kb.vertical})`, bv && Math.abs(bv.y - kb.vertical) < 0.02, bv ? 'y=' + bv.y.toFixed(3) : '속도 없음')
  if (kb.glide) {
    const bp = bs.vel.filter((x) => Math.hypot(x.x, x.z) > 0.05).length
    sc.check(`backstep push lasts exactly ${kb.glide} ticks`, bp === kb.glide, bp + '번')
  }
  if (RC.crawl) sc.check('backstep does not crawl', b.p.crawl.length === cb, (b.p.crawl.length - cb) + '칸')
  if (RC.visual === 'tumble') sc.check('backstep has no stand-in (the real body hops back)', !b.p.passengers.slice(pb).some((x) => x.ids.length), JSON.stringify(b.p.passengers.slice(pb).map((x) => x.ids)))

  // ── 옆 구르기 ── 오른쪽 (lane 이 동쪽을 보니 오른쪽은 남쪽 +z)
  await fresh(b)
  const rr = await roll(b, { right: true })
  sc.check('right key -> roll right', rr.r && rr.r.kv.dir === 'right' && rr.vel[0] && rr.vel[0].z > 0.25, rr.r ? rr.r.line + (rr.vel[0] ? ` vz=${rr.vel[0].z.toFixed(3)}` : '') : '줄 없음')

  // ── 웅크리기 + F ── 패링 (3.5: 왼손에 든 것으로. 판정은 M1, 지금은 PARRY 줄만. 무기 기술은 없앴다)
  await fresh(b)
  b.input({ shift: true })
  await L.sleep(250)
  from = b.sys.length
  b.swap()
  await L.sleep(700)
  b.input({})
  const sn = b.sys.slice(from).find((m) => m.plain.startsWith('[T] ROLL '))
  sc.check('sneak + F does not roll', !sn, sn ? sn.plain : '')
  sc.check('sneak + F is parry (PARRY line)', b.tLines('PARRY', from).some((x) => x.kv.sneak === 'true'), b.tLines('PARRY', from).map((x) => x.line).join(' | ') || 'PARRY 줄 없음')
  await L.sleep(500)
  if (RC.rollKey === 'sneak') {
    // ── F 만 (구르기 키가 웅크리기) ── 구르지 않는다
    await fresh(b)
    b.input({ forward: true })
    await L.sleep(150)
    from = b.sys.length
    b.swap()
    await L.sleep(700)
    b.input({})
    const fr = b.sys.slice(from).find((m) => m.plain.startsWith('[T] ROLL '))
    sc.check('F alone does not roll, it parries (controls.roll-key: sneak)', !fr && b.tLines('PARRY', from).length === 1, fr ? fr.plain : (b.tLines('PARRY', from)[0] || {}).line || 'PARRY 줄 없음')
  }
  if (SNEAK) {
    // ── 길게 누르면 웅크리기 ── 뗄 때 구르지 않는다
    await fresh(b)
    from = b.sys.length
    b.input({ shift: true })
    await L.sleep(600)
    b.input({})
    await L.sleep(500)
    const hold = b.tLines('ROLL_TAP_SKIP', from)[0]
    sc.check('holding sneak (0.6 s) is a crouch, not a roll', hold && hold.kv.why === 'hold' && !b.tLines('ROLL ', from).length, hold ? hold.line : '줄 없음')
    // ── 누르는 동안 휘두르면 조합 (강공격 자리) ── 구르지 않는다
    await fresh(b)
    from = b.sys.length
    b.input({ shift: true })
    await L.sleep(40)
    b.bot.swingArm('right')
    await L.sleep(60)
    b.input({})
    await L.sleep(500)
    const combo = b.tLines('ROLL_TAP_SKIP', from)[0]
    sc.check('sneak + attack while held is a combo, not a roll', combo && combo.kv.why === 'attack' && !b.tLines('ROLL ', from).length, combo ? combo.line : '줄 없음')
  }

  // ── 공중 F ──
  await fresh(b)
  b.bot.setControlState('jump', true)
  b.input({ jump: true })
  await L.sleep(180)
  b.bot.setControlState('jump', false)
  from = b.sys.length
  await b.rollKey({ jump: true }, RC.rollKey)
  const air = await b.waitSys((m) => /^\[T\] ROLL(_DENY)? /.test(m.plain), 1500, from)
  b.input({})
  sc.check(`${KEY} in the air is refused`, air && /ROLL_DENY why=air/.test(air.plain), air ? air.plain : '줄 없음')
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
    const arm = await b.cmd(`/soulstest rollhit ${off} ${2 * S}`, 'ROLLHIT armed')
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
    await b.rollKey({ forward: true })
    await L.sleep(100)
    const h = await b.cmd(`/soulstest hit ${2 * S}` + flags, 'HIT ', 3000)
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

  // ── 무적: 자기 화면 기준 (13.3) ── 예고 줄을 받은 순간 F. k 틱 뒤의 피해가 무적 창 (1..iframes) 에 드는가
  const ws = []
  for (const k of [3, 5, 7]) {
    for (let rep = 0; rep < 2; rep++) {
      await fresh(b)
      b.input({ forward: true })
      await L.sleep(150)
      const from = b.sys.length
      b.onSysOnce((m) => m.plain.startsWith('[T] WARN '), () => b.rollKeyNow())
      const w = await b.cmd(`/soulstest warn ${k} 2`, 'WARN ', 3000)
      const hit = await b.waitT('WARNHIT ', 3000, from)
      // 지연이 길면 F 가 피해보다 늦게 닿는다 (roll_t=-1). 그래도 구르기는 시작되므로 그 줄을 조금 더 기다린다
      await b.waitT('ROLL ', 600, from)
      b.input({})
      const rl = b.tLines('ROLL ', from)[0]
      if (!w.kv || !hit || !rl) { sc.check(`warn ${k}: warned, rolled and hit`, false, (w.line || '예고 없음') + ' | ' + (rl ? rl.line : '구르지 않음') + ' | ' + (hit ? hit.line : '맞지 않음')); continue }
      ws.push({ k, d: L.num(rl.kv.t) - L.num(w.kv.t), rt: L.num(hit.kv.roll_t), dodged: hit.kv.dodged === 'true' })
      await L.sleep(250)
    }
  }
  if (ws.length) {
    const ds = ws.map((x) => x.d).sort((a, c) => a - c)
    const med = ds[ds.length >> 1]
    const lo = Math.floor(E.lagRtt / 50)
    sc.check(`screen-time F reaches the server ~RTT later (median ${lo}..${lo + 3} ticks after the warning)`, med >= lo && med <= lo + 3,
      `늦음 ${ds.join(',')} 틱 (왕복 ${E.lagRtt}ms)`)
    const n = ws.filter((x) => x.dodged).length
    // run_tests.sh 가 지연별로 모아 보인다 (판정은 하지 않는다: 대기열이 없는 M0 의 기준선)
    console.log(`SCREENDODGE rtt=${E.lagRtt} dodged=${n}/${ws.length} delay=${ds.join(',')} roll_t=${ws.map((x) => x.rt).join(',')}`)
    sc.note(`자기 화면 기준 피한 비율 ${n}/${ws.length} (k=3,5,7 두 번씩, 지연 ${E.lagRtt}ms). 대기열이 없는 M0 의 기준선`)
  }

  // ── 순간이동하면 남은 밀기를 멈춘다 ── 구르기 2틱 뒤 방으로 옮기고, 도착한 자리에서 미끄러지지 않는지
  await fresh(b)
  {
    const room = L.testRoom()
    b.input({ forward: true })
    await L.sleep(150)
    const from = b.sys.length
    await b.rollKey({ forward: true })
    await b.waitT('ROLL ', 2000, from)
    await L.sleep(100)
    await b.cmd('/souls tp room', null, 1500)
    b.input({})
    await L.sleep(1000)
    const p = b.bot.entity.position
    const sx = room.x + 0.5; const sz = room.z + 10.5
    const off = Math.hypot(p.x - sx, p.z - sz)
    sc.check('teleport mid-roll stops the glide (no slide after arriving)', off < 0.4, `도착 자리에서 ${off.toFixed(2)}칸`)
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
