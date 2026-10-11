// M1 P1a 공격 동작 (attacks.js 1부, M1_PLAN P1a, DESIGN 3.6). 봇은 빈털터리 (곤봉 = 망치 6/2/10, 판자 방패) 로 태어난다.
// 경계는 서버가 적은 틱 (MOVE t=, HIT tick=) 으로 본다 (R35: 봇이 보낸 시각이 아니다). 정확한 틱 경계는 JUnit (MoveTimingTest·InputBufferTest).
//   - 적 공격 (bot.attack: mineflayer 는 휘두르기 → 공격 차례, R2): MOVE light1 하나, HIT 하나가 시작 + 준비 틱에
//   - 매 틱 휘두르기: 시작이 한 주기씩 떨어지고 (입력 기억으로 끝나는 틱에 바로), 약공격 1·2·3·1단 배율 100/105/115/100, 같은 틱에 둘이 없다
//   - 단도 매 틱: 한 주기 정확히 10틱
//   - 웅크리기 + 휘두르기: MOVE heavy 와 ROLL_TAP_SKIP why=attack. 달리며 휘두르기: MOVE running
//   - 스태미나 0: MOVE_DENY why=stamina, 1: 공격하고 0 에서 멈춘다
//   - 민첩 40: 틱이 3.6 의 셈과 같고, 든 무기의 휘두르는 길이 (swing_animation) 가 한 번만 바뀐다 (SWING_TIER)
//   - 휘두르는 중에 단축 칸을 바꿔도 시작한 무기의 값으로 맞힌다
//   - 가짜 휘두르기 (바닐라 클라이언트처럼 짝으로 보낸다, R36): Q (버리기) + 휘두르기, 우클릭 (use_item) + 휘두르기 → MOVE 없음
//   - 주손에 활: MOVE_DENY why=weapon
//   - 준비 중에 마신 물약은 막히고 (USE_DENY), 회복 중에는 마신다 (R17)
//   - 아이템: 곤봉의 swing_animation (whack, 준비 + 판정 8틱), attack_range (2.9, hitbox_margin 0), 바닐라 attack_speed 높게 (S3)
'use strict'
const L = require('./lib')

const isDummy = (e) => e.name === 'zombie' || e.displayName === 'Zombie'

L.run('attacks', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(500)
  await b.ground(3000)
  const stamina = (v) => b.cmd(`/soulstest stamina set ${v}`, 'STAMINA')
  const state = () => b.cmd('/soulstest state', 'MOVE_STATE')
  const swing = () => b.bot.swingArm('right')
  /** 동작이 다 끝날 때까지 (MOVE_STATE move=-) 기다린다 */
  const idle = async (ms = 3000) => {
    const end = Date.now() + ms
    for (;;) {
      const r = await state()
      if (r.kv && r.kv.move === '-' && r.kv.buf === '-') return r
      if (Date.now() > end) return r
      await L.sleep(100)
    }
  }
  /** n 번 매 틱 (50ms) 휘두른다 */
  const spam = async (n, gap = 50) => {
    for (let i = 0; i < n; i++) {
      swing()
      await L.sleep(gap)
    }
  }

  const s0 = await b.cmd('/soulstest stats', 'STATS ')
  if (!sc.checkCmd('starts as deprived with the club (hammer), dex 10', s0, (r) => r.kv.weapon === 'gaoler_club' && r.kv.dex === '10')) return

  // ── 아이템 ──
  const st0 = await state()
  sc.checkCmd('held club: weapon format 1, swing tier 0, whack swing 8 ticks (light 1: 6 + 2)', st0, (r) =>
    r.kv.held === 'gaoler_club' && r.kv.fmt === '1' && r.kv.tier === '0' && r.kv.want === '0' && r.kv.swing === 'whack/8')
  sc.checkCmd('vanilla attack_speed is high while holding a souls melee weapon (S3: no dip after server swings)', st0, (r) => L.num(r.kv.aspd) >= 4)
  const held = b.bot.inventory.slots[36 + b.bot.quickBarSlot]
  const comp = (t) => held && Array.isArray(held.components) ? (held.components.find((c) => c.type === t) || {}).data : null
  const ar = comp('attack_range')
  const sw = comp('swing_animation')
  sc.check('the client gets attack_range max 2.9 with hitbox margin 0 (S6) and the swing length', ar && Math.abs(ar.maxRange - 2.9) < 1e-3 &&
    Math.abs(ar.hitboxMargin) < 1e-6 && sw && sw.duration === 8, JSON.stringify({ ar, sw }))

  // ── 허수아비 ──
  await b.cmd('/soulstest dummy clear', 'DUMMY clear')
  const ds = await b.cmd('/soulstest dummy spawn', 'DUMMY spawn', 4000)
  if (!sc.checkCmd('a dummy stands 3 blocks ahead (P1b)', ds, (r) => r.kv.id === 'dummy')) return
  await L.sleep(800)
  const dummy = L.nearestEntity(b, isDummy, 6)
  if (!sc.check('the bot sees the dummy', !!dummy)) return
  await L.faceEntity(b, dummy)
  await stamina(100)
  await L.sleep(300)

  // ── 한 번 치기 ──
  let from = b.sys.length
  b.bot.attack(dummy)
  await L.sleep(1400)
  let mv = L.moveLines(b, from)
  let hits = b.tLines('HIT ', from)
  sc.check('bot.attack (swing, then attack packet): exactly one MOVE light1', mv.length === 1 && mv[0].kv.kind === 'light1' && mv[0].kv.cls === 'hammer' &&
    mv[0].s === 6 && mv[0].a === 2 && mv[0].r === 10, mv.map((x) => x.line).join(' | ') || '줄 없음')
  sc.check('the attack packet is the aim hint only (aim= the dummy), not a second input', mv.length === 1 && mv[0].kv.aim !== '-', mv.map((x) => x.kv.aim).join(','))
  sc.check('exactly one HIT at start + startup (tick 6), dealt = raw^2/(raw+def)', hits.length === 1 && hits[0].kv.tick === '6' && hits[0].kv.move === 'light1' &&
    Math.abs(L.num(hits[0].kv.dealt) - L.num(hits[0].kv.raw) ** 2 / (L.num(hits[0].kv.raw) + L.num(hits[0].kv.def))) < 0.05 &&
    L.num(hits[0].kv.raw) === L.num(mv[0] && mv[0].kv.ar), hits.map((x) => x.line).join(' | ') || '줄 없음')
  await idle()

  // ── 매 틱 휘두르기 (곤봉, 민첩 10: 6/2/10 = 18틱) ──
  await stamina(100)
  await L.sleep(200)
  from = b.sys.length
  await spam(66)
  await idle(3000)
  mv = L.moveLines(b, from)
  const kinds = mv.map((x) => x.kv.kind)
  sc.check('swinging every tick: four moves light1 light2 light3 light1', kinds.slice(0, 4).join(',') === 'light1,light2,light3,light1', kinds.join(','))
  sc.check('motion values 100 / 105 / 115 / 100', mv.slice(0, 4).map((x) => x.kv.mv).join(',') === '100,105,115,100', mv.map((x) => x.kv.mv).join(','))
  let spaced = true
  let exact = 0
  for (let i = 1; i < mv.length; i++) {
    const gap = mv[i].tick - mv[i - 1].tick
    if (gap < mv[i - 1].cycle) spaced = false
    if (gap === mv[i - 1].cycle) exact++
  }
  sc.check('starts are spaced at least one cycle (18) apart; the buffered input starts on the end tick', spaced && mv.length >= 4 && exact >= mv.length - 2,
    mv.map((x) => `${x.kv.kind}@${x.tick}(+${x.cycle}) buf=${x.kv.buf}`).join(' '))
  const ticks = mv.map((x) => x.tick)
  sc.check('at most one buffered input: never two moves on one tick, chained moves are buf=true', new Set(ticks).size === ticks.length &&
    mv.slice(1).every((x) => x.kv.buf === 'true'), ticks.join(','))
  sc.check('early swings are dropped (MOVE_EARLY) and late ones buffered (MOVE_BUF)', b.tLines('MOVE_EARLY', from).length > 0 && b.tLines('MOVE_BUF', from).length > 0,
    `early ${b.tLines('MOVE_EARLY', from).length} buf ${b.tLines('MOVE_BUF', from).length}`)
  const hitsSpam = b.tLines('HIT ', from)
  sc.check('each move hits the dummy once', hitsSpam.length === mv.length && hitsSpam.every((x) => x.kv.n === '1'), hitsSpam.map((x) => `${x.kv.move}@${x.kv.tick}`).join(' '))

  // ── 단도 매 틱: 한 주기 10 ──
  await b.cmd('/soulstest give alley_dagger main', 'GIVE')
  await L.sleep(400)
  await stamina(100)
  from = b.sys.length
  await spam(44)
  await idle(2000)
  mv = L.moveLines(b, from)
  sc.check('dagger every tick: cycle exactly 10 (3/1/6), starts 10 ticks apart', mv.length >= 3 && mv.every((x) => x.cycle === 10 && x.kv.cls === 'dagger') &&
    mv.slice(1).every((x, i) => x.tick - mv[i].tick === 10), mv.map((x) => `${x.kv.kind}@${x.tick} ${x.s}/${x.a}/${x.r}`).join(' '))
  await b.cmd('/soulstest give gaoler_club main', 'GIVE')
  await L.sleep(400)

  // ── 강공격 (웅크리기 키 + 좌클릭) ──
  await stamina(100)
  from = b.sys.length
  b.input({ shift: true })
  await L.sleep(60)
  swing()
  await L.sleep(80)
  b.input({})
  await L.sleep(600)
  mv = L.moveLines(b, from)
  const skip = b.tLines('ROLL_TAP_SKIP', from)[0]
  sc.check('sneak + swing: MOVE heavy (hammer 11/2/15, motion 160, stamina 30)', mv.length === 1 && mv[0].kv.kind === 'heavy' && mv[0].s === 11 && mv[0].a === 2 &&
    mv[0].r === 15 && mv[0].kv.mv === '160' && mv[0].kv.stam === '30.0', mv.map((x) => x.line).join(' | ') || '줄 없음')
  sc.check('the sneak press used as a combo key does not roll (ROLL_TAP_SKIP why=attack)', skip && skip.kv.why === 'attack' && !b.tLines('ROLL ', from).length,
    skip ? skip.line : '줄 없음')
  await idle()

  // ── 달리기 공격 ──
  await stamina(100)
  b.sprint(true)
  await L.sleep(350)
  from = b.sys.length
  swing()
  await L.sleep(250)
  b.sprint(false)
  await L.sleep(400)
  mv = L.moveLines(b, from)
  sc.check('sprint + swing: MOVE running (motion 115, stamina 20 x 1.15 = 23)', mv.length === 1 && mv[0].kv.kind === 'running' && mv[0].kv.mv === '115' &&
    mv[0].kv.stam === '23.0', mv.map((x) => x.line).join(' | ') || '줄 없음')
  await idle()
  // 달리다 밀려났을 수 있으니 허수아비 앞에 다시 선다
  await b.cmd('/soulstest dummy clear', 'DUMMY clear')
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(500)
  await b.cmd('/soulstest dummy spawn', 'DUMMY spawn', 4000)
  await L.sleep(800)
  const dummy2 = L.nearestEntity(b, isDummy, 6)
  await L.faceEntity(b, dummy2)

  // ── 스태미나 ──
  await stamina(0)
  from = b.sys.length
  swing()
  await L.sleep(400)
  const deny = b.tLines('MOVE_DENY', from)[0]
  sc.check('stamina 0: MOVE_DENY why=stamina', deny && deny.kv.why === 'stamina' && !L.moveLines(b, from).length, deny ? deny.line : '줄 없음')
  await stamina(1)
  from = b.sys.length
  swing()
  await L.sleep(400)
  mv = L.moveLines(b, from)
  sc.check('stamina 1: the attack goes and stamina stops at 0', mv.length === 1 && mv[0].kv.st === '0.0', mv.map((x) => x.line).join(' | ') || '줄 없음')
  await idle()
  await stamina(100)

  // ── 민첩 40 ──
  from = b.sys.length
  await b.cmd('/soulstest stat dex 40', 'STAT ')
  await L.sleep(500)
  const tier = b.tLines('SWING_TIER', from)
  sc.check('dex 40: the swing tier changes once (tier 3) and the held club is rebuilt', tier.length === 1 && tier[0].kv.tier === '3' && L.num(tier[0].kv.n) >= 1,
    tier.map((x) => x.line).join(' | ') || '줄 없음')
  const st40 = await state()
  sc.checkCmd('dex 40: the club swings 7 ticks (5 + 2) and carries tier 3', st40, (r) => r.kv.tier === '3' && r.kv.want === '3' && r.kv.swing === 'whack/7')
  from = b.sys.length
  await b.cmd('/soulstest stat dex 40', 'STAT ')
  await L.sleep(300)
  sc.check('setting the same dex again does not rebuild', !b.tLines('SWING_TIER', from).length && !b.tLines('WEAPON_REFRESH', from).length,
    b.tLines('', from).map((x) => x.line).filter((l) => /SWING_TIER|WEAPON_REFRESH/.test(l)).join(' | '))
  await stamina(100)
  from = b.sys.length
  await spam(64)
  await idle(3000)
  mv = L.moveLines(b, from)
  // 망치 6/2/10 ÷ 1.22: 준비 round(4.92) = 5, 판정 2, 회복 8.197 (올린 9 에서 모은 몫이 차면 8)
  const ok40 = mv.length >= 3 && mv.every((x) => x.s === 5 && x.a === 2 && (x.r === 8 || x.r === 9))
  const sum = mv.reduce((t, x) => t + x.cycle, 0)
  sc.check('dex 40: hammer 5/2/(8|9), cycle sum within one tick of n x 15.2 (fraction carried)', ok40 && Math.abs(sum - mv.length * (7 + 10 / 1.22)) <= 1,
    `${mv.map((x) => `${x.s}/${x.a}/${x.r}`).join(' ')} sum=${sum} want=${(mv.length * (7 + 10 / 1.22)).toFixed(2)}`)
  sc.check('dex 40: starts follow the shortened cycle', mv.slice(1).every((x, i) => x.tick - mv[i].tick === mv[i].cycle), mv.map((x) => x.tick).join(','))
  from = b.sys.length
  await b.cmd('/soulstest stat dex 10', 'STAT ')
  await L.sleep(400)
  const back = await state()
  sc.check('dex back to 10: tier 0 and the 8-tick swing again', b.tLines('SWING_TIER', from).length === 1 && back.kv && back.kv.tier === '0' && back.kv.swing === 'whack/8',
    (back.line || '') + ' | ' + b.tLines('SWING_TIER', from).map((x) => x.line).join(' | '))
  await idle()

  // ── 단축 칸 바꾸기: 시작한 무기의 값으로 ──
  await b.cmd('/soulstest give alley_dagger inv', 'GIVE')
  await L.sleep(500)
  const daggerSlot = b.bot.inventory.slots.findIndex((it, i) => i >= 36 && i < 45 && it && JSON.stringify(it.components || []).includes('souls.weapon.alley_dagger.name'))
  if (sc.check('a dagger sits in the hotbar', daggerSlot >= 36, String(daggerSlot))) {
    const clubSlot = b.bot.quickBarSlot
    await stamina(100)
    await L.faceEntity(b, L.nearestEntity(b, isDummy, 6))
    from = b.sys.length
    swing()
    await L.sleep(120)
    b.bot.setQuickBarSlot(daggerSlot - 36)
    await L.sleep(700)
    const hit = b.tLines('HIT ', from)[0]
    sc.check('a hotbar switch during startup keeps the club (HIT weapon=gaoler_club cls=hammer)', hit && hit.kv.weapon === 'gaoler_club' && hit.kv.cls === 'hammer',
      hit ? hit.line : '줄 없음')
    b.bot.setQuickBarSlot(clubSlot)
    await L.sleep(400)
    await idle()
  }

  // ── 가짜 휘두르기 (바닐라처럼 짝으로) ──
  await stamina(100)
  from = b.sys.length
  b.bot._client.write('block_dig', { status: 4, location: { x: 0, y: 0, z: 0 }, face: 0, sequence: 0 })
  swing()
  await L.sleep(500)
  let fake = b.tLines('MOVE_FAKE', from)
  sc.check('Q (drop) + arm_animation: no MOVE (MOVE_FAKE why=mark)', !L.moveLines(b, from).length && fake.length === 1 && fake[0].kv.why === 'mark',
    b.tLines('', from).map((x) => x.line).filter((l) => /MOVE/.test(l)).join(' | ') || '줄 없음')
  from = b.sys.length
  b.bot.activateItem(false)
  swing()
  await L.sleep(500)
  b.bot.deactivateItem()
  fake = b.tLines('MOVE_FAKE', from)
  sc.check('use_item + arm_animation: no MOVE (MOVE_FAKE why=mark)', !L.moveLines(b, from).length && fake.length === 1 && fake[0].kv.why === 'mark',
    b.tLines('', from).map((x) => x.line).filter((l) => /MOVE/.test(l)).join(' | ') || '줄 없음')
  // 두 틱 뒤의 휘두르기는 진짜 좌클릭
  from = b.sys.length
  b.bot._client.write('block_dig', { status: 4, location: { x: 0, y: 0, z: 0 }, face: 0, sequence: 0 })
  await L.sleep(250)
  swing()
  await L.sleep(400)
  sc.check('a swing well after the drop is a real attack', L.moveLines(b, from).length === 1, L.moveLines(b, from).map((x) => x.line).join(' | ') || '줄 없음')
  await idle()

  // ── 근접 무기가 아닌 것 ──
  await b.cmd('/soulstest give wall_shortbow main', 'GIVE')
  await L.sleep(400)
  from = b.sys.length
  swing()
  await L.sleep(400)
  const bow = b.tLines('MOVE_DENY', from)[0]
  sc.check('bow in the main hand + swing: MOVE_DENY why=weapon', bow && bow.kv.why === 'weapon' && bow.kv.weapon === 'wall_shortbow' && !L.moveLines(b, from).length,
    bow ? bow.line : '줄 없음')
  await b.cmd('/soulstest give gaoler_club main', 'GIVE')
  await L.sleep(400)

  // ── 마시기 (R17): 준비 중에는 막고 회복 중에는 된다 ──
  const offName = () => { const it = b.bot.inventory.slots[45]; return it ? it.name : '-' }
  await b.cmd('/item replace entity @s weapon.offhand with minecraft:potion[potion_contents={potion:"minecraft:water"}]', null, 1000)
  await L.sleep(400)
  if (sc.check('setup: a water bottle in the off hand', offName() === 'potion', offName())) {
    await stamina(100)
    from = b.sys.length
    swing()
    const m1 = await b.waitT('MOVE ', 1500, from)
    b.bot.activateItem(true)
    await L.sleep(2200)
    b.bot.deactivateItem()
    const ud = b.tLines('USE_DENY', from)
    sc.check('drinking in startup is denied (USE_DENY why=attack) and the potion is kept', m1 && ud.length >= 1 && ud[0].kv.why === 'attack' && offName() === 'potion',
      `${ud.map((x) => x.line).join(' | ') || 'USE_DENY 없음'} off=${offName()}`)
    await idle()
    from = b.sys.length
    swing()
    const m2 = await b.waitT('MOVE ', 1500, from)
    // 곤봉: 준비 6 + 판정 2 → 회복은 9틱째부터 (받은 줄 뒤 0.5초)
    await L.sleep(500)
    const fromUse = b.sys.length
    b.bot.activateItem(true)
    await L.sleep(2300)
    b.bot.deactivateItem()
    await L.sleep(300)
    sc.check('drinking in recovery is allowed ("quick drink"): the bottle is emptied', m2 && !b.tLines('USE_DENY', fromUse).length && offName() === 'glass_bottle',
      `off=${offName()} ${b.tLines('USE_DENY', fromUse).map((x) => x.line).join(' | ')}`)
  }
  await b.cmd('/soulstest give plank_shield off', 'GIVE')
  await b.cmd('/soulstest dummy clear', 'DUMMY clear')
  await stamina(100)
  sc.check('no kick during attacks scenario', !b.kick, b.kick || '')
})
