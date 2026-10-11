// 입력 탐침 (M1 PS, M1_PLAN 2절): /soulstest probe on 으로 켠 사람의 입력 이벤트가 [T] PROBE ev=... 한 줄씩 나오는지,
// 봇이 바닐라 클라이언트의 날 패킷을 보내 본다 (클라이언트가 실제로 무엇을 보내는지는 실제 클라이언트로 tools/client/probe_shots.sh).
//   우클릭 짝 (R36): use_item 손 0 다음 손 1 → interact RIGHT_CLICK_AIR HAND, OFF_HAND (공중 클릭은 이미 취소된 채, R1)
//   휘두름: arm_animation 손 0·1 → swing HAND / OFF_HAND (+ 공중 좌클릭 LEFT_CLICK_AIR)
//   F (block_dig 6) → swap (Roll 이 늘 취소). fswing off 면 서버가 왼손을 휘두르고 (srvswing), 그 animation 패킷이 봇에게도 온다 (S3)
//   Q (block_dig 4) → drop. 웅크리기 (player_input) → input +sneak / -sneak
//   엔터티 공격 (use_entity) → attack will=true, damage. cancel attack 이면 attack cancelled=true 이고 damage 가 없다 (S12 흉내)
//   probe swing main → srvswing 과 animation 0. probe off → 줄이 없다
//   probe mob husk block → 허스크가 왼손 방패를 쓰는 중 (서버 쪽, S9). probe crawl → 머리 칸 막힘 block_change (S10)
//   S8 메모: 방패 껍데기로 막고 맞을 때 받은 소리 (판정 아님)
'use strict'
const L = require('./lib')

const evLines = (b, from, ev) => b.tLines('PROBE ev=' + ev, from)

L.run('probe', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(500)
  const anim = []
  b._bot._client.on('animation', (d) => { if (d.entityId === b._bot.entity.id) anim.push({ t: Date.now(), a: d.animation }) })
  const blocks = []
  b._bot._client.on('block_change', (d) => blocks.push({ t: Date.now(), type: d.type }))

  const on = await b.cmd('/soulstest probe on', 'PROBE_SET')
  if (!sc.checkCmd('probe on', on, (r) => r.kv.on === 'true')) return

  await b.cmd('/soulstest give redin_guard_sword main', 'GIVE')
  await b.cmd('/soulstest give parrying_dagger off', 'GIVE')
  await L.sleep(500)
  // 하늘을 본다: 서버의 시선 검사에 블록이 걸리지 않게 (공중 클릭)
  await b.bot.look(0, Math.PI / 2, true)
  await L.sleep(300)

  // ── 우클릭 짝 (S1 의 서버 쪽, R36): 바닐라는 주손 PASS 뒤 왼손으로 use_item 을 한 번 더 보낸다 ──
  let from = b.sys.length
  b._bot.activateItem(false)
  b._bot.activateItem(true)
  b._bot.usingHeldItem = false
  await L.sleep(600)
  let it = evLines(b, from, 'interact').filter((x) => x.kv.action === 'RIGHT_CLICK_AIR')
  sc.check('use_item hand 0 then 1 → interact RIGHT_CLICK_AIR HAND then OFF_HAND', it.length === 2 && it[0].kv.hand === 'HAND' && it[1].kv.hand === 'OFF_HAND',
    it.map((x) => x.line).join(' | ') || '줄 없음')
  sc.check('air right-click arrives already cancelled (R1: listeners need ignoreCancelled=false)', it.length > 0 && it.every((x) => x.kv.cancelled === 'true'),
    it.map((x) => `cancelled=${x.kv.cancelled} useItem=${x.kv.useItem}`).join(', '))
  sc.check('probe line carries the souls item id (flint:parrying_dagger on the off hand)', it.length === 2 && it[1].kv.item === 'flint:parrying_dagger',
    it.length === 2 ? 'item=' + it[1].kv.item : '')

  // ── 휘두름 ──
  from = b.sys.length
  b._bot._client.write('arm_animation', { hand: 0 })
  await L.sleep(300)
  b._bot._client.write('arm_animation', { hand: 1 })
  await L.sleep(500)
  const sw = evLines(b, from, 'swing')
  sc.check('arm_animation hand 0 / 1 → swing HAND / OFF_HAND', sw.length === 2 && sw[0].kv.hand === 'HAND' && sw[1].kv.hand === 'OFF_HAND',
    sw.map((x) => x.line).join(' | ') || '줄 없음')
  const lca = evLines(b, from, 'interact').filter((x) => x.kv.action === 'LEFT_CLICK_AIR')
  sc.note('swing at the sky also gives LEFT_CLICK_AIR: ' + lca.map((x) => `hand=${x.kv.hand} seq=${x.kv.seq}`).join(', ') +
    ' (swing seq ' + sw.map((x) => x.kv.seq).join(',') + ')')

  // ── F ──
  from = b.sys.length
  b.swap()
  await L.sleep(500)
  let swp = evLines(b, from, 'swap')
  sc.check('F (block_dig 6) → swap, cancelled by Roll in our world', swp.length === 1 && swp[0].kv.cancelled === 'true', swp.map((x) => x.line).join(' | ') || '줄 없음')

  // F 에 서버가 왼손을 휘두른다 (P3 의 패링 몸짓 흉내): swingOffHand 의 animation 3 이 자기에게도 온다 (S3)
  await b.cmd('/soulstest probe fswing off', 'PROBE_SET')
  await L.sleep(300)
  from = b.sys.length
  let a0 = anim.length
  b.swap()
  await L.sleep(600)
  const srv = evLines(b, from, 'srvswing')
  sc.check('fswing off: F → server swings the off hand (srvswing OFF_HAND)', srv.length === 1 && srv[0].kv.hand === 'OFF_HAND', srv.map((x) => x.line).join(' | ') || '줄 없음')
  sc.check('swingOffHand reaches the swinging player (animation 3 to self)', anim.slice(a0).some((x) => x.a === 3), 'animation ' + anim.slice(a0).map((x) => x.a).join(','))
  await b.cmd('/soulstest probe fswing none', 'PROBE_SET')
  a0 = anim.length
  from = b.sys.length
  await b.cmd('/soulstest probe swing main', 'PROBE ev=srvswing')
  await L.sleep(400)
  sc.check('probe swing main → swingMainHand reaches the player (animation 0 to self)', anim.slice(a0).some((x) => x.a === 0), 'animation ' + anim.slice(a0).map((x) => x.a).join(','))

  // ── 웅크리기 (길게 눌러 구르지 않게) ──
  from = b.sys.length
  b.input({ shift: true })
  await L.sleep(500)
  b.input({})
  await L.sleep(400)
  const inp = evLines(b, from, 'input')
  sc.check('player_input shift → input +sneak then -sneak', inp.length >= 2 && inp[0].kv.action === '+sneak' && inp[0].kv.in === 'sneak' && inp[inp.length - 1].kv.action === '-sneak',
    inp.map((x) => `${x.kv.action}/${x.kv.in}`).join(' ') || '줄 없음')

  // ── 엔터티 공격 ──
  await b.cmd('/summon minecraft:husk ~2 ~ ~ {NoAI:1b,Silent:1b,Tags:["souls_ent","souls_probe"],PersistenceRequired:0b}', null, 800)
  await L.sleep(700)
  const husk = Object.values(b.bot.entities).find((e) => e.name === 'husk' && e.position.distanceTo(b.bot.entity.position) < 4)
  if (sc.check('test husk is near', !!husk)) {
    await b.bot.lookAt(husk.position.offset(0, 1.4, 0), true)
    await L.sleep(300)
    from = b.sys.length
    b.bot.attack(husk)
    await L.sleep(600)
    const at = evLines(b, from, 'attack')
    const dm = evLines(b, from, 'damage')
    sc.check('use_entity attack → attack will=true, not cancelled', at.length === 1 && at[0].kv.will === 'true' && at[0].kv.cancelled === 'false' && at[0].kv.target === 'husk',
      at.map((x) => x.line).join(' | ') || '줄 없음')
    sc.check('uncancelled attack reaches damage', dm.length >= 1, dm.map((x) => `dmg=${x.kv.dmg} cancelled=${x.kv.cancelled}`).join(', ') || '줄 없음')
    await b.cmd('/soulstest probe cancel attack', 'PROBE_SET')
    await L.sleep(600) // 맞은 무적 시간 (10틱) 을 지난다
    from = b.sys.length
    b.bot.attack(husk)
    await L.sleep(600)
    const at2 = evLines(b, from, 'attack')
    const dm2 = evLines(b, from, 'damage')
    sc.check('cancel attack: attack cancelled=true and no damage (P1a stand-in)', at2.length === 1 && at2[0].kv.cancelled === 'true' && dm2.length === 0,
      at2.map((x) => x.line).join(' | ') + ' damage=' + dm2.length)
    await b.cmd('/soulstest probe cancel none', 'PROBE_SET')
  }
  await b.cmd('/kill @e[type=minecraft:husk,tag=souls_probe]', null, 800)
  await b.bot.look(0, Math.PI / 2, true)

  // ── Q ──
  from = b.sys.length
  b._bot._client.write('block_dig', { status: 4, location: { x: 0, y: 0, z: 0 }, face: 0, sequence: 0 })
  await L.sleep(500)
  const dr = evLines(b, from, 'drop')
  sc.check('Q (block_dig 4) → drop with the souls item', dr.length === 1 && /redin_guard_sword/.test(dr[0].kv.item), dr.map((x) => x.line).join(' | ') || '줄 없음')
  await L.sleep(300)
  await b.cmd('/kill @e[type=minecraft:item,distance=..6]', null, 800)

  // ── S9: 허스크의 방패 쓰기 (서버 쪽. 그림은 probe_shots.sh) ──
  from = b.sys.length
  await b.cmd('/soulstest probe mob husk block', 'PROBE_MOB')
  const m20 = await b.waitT('PROBE_MOB type=husk mode=block after=20', 3000, from)
  sc.check('probe mob husk block: still using the off-hand shield after 20 ticks (server side)', m20 && m20.kv.using === 'true' && m20.kv.hand === 'OFF_HAND', m20 ? m20.line : '줄 없음')
  const cl = await b.cmd('/soulstest probe mob clear', 'PROBE_MOB')
  sc.checkCmd('probe mob clear', cl, (r) => +r.kv.cleared >= 1)

  // ── S10: 화면에만 까는 머리 칸 막힘 ──
  await b.cmd('/soulstest give redin_guard_sword main', 'GIVE')
  const b0 = blocks.length
  from = b.sys.length
  await b.cmd('/soulstest probe crawl 10', 'PROBE_CRAWL')
  const off = await b.waitT('PROBE_CRAWL off', 3000, from)
  const fake = blocks.slice(b0)
  sc.check('probe crawl: client-only ceiling sent, then taken back', fake.length >= 2 && !!off, `block_change ${fake.length}개, ` + (off ? off.line : 'off 줄 없음'))

  // ── S8 메모: 방패 껍데기로 막고 맞을 때 받은 소리 ──
  {
    await b.cmd('/soulstest heal', 'HEAL')
    await b.cmd('/item replace entity @s weapon.mainhand with air', null, 800)
    await b.cmd('/soulstest give redin_guard_shield off', 'GIVE')
    await L.sleep(500)
    const s0 = b.p.sounds.length
    b._bot.activateItem(true)
    await L.sleep(400)
    await b.cmd('/soulstest hit 40', 'HIT ')
    await L.sleep(400)
    b._bot.deactivateItem()
    await L.sleep(200)
    sc.note('S8 sounds while the shield shell guards a hit: ' + (b.p.sounds.slice(s0).map((s) => b.soundName(s)).join(', ') || '(none)'))
  }

  // ── 끄기 ──
  const offr = await b.cmd('/soulstest probe off', 'PROBE_SET')
  sc.checkCmd('probe off', offr, (r) => r.kv.on === 'false')
  from = b.sys.length
  b._bot._client.write('arm_animation', { hand: 0 })
  b.swap()
  await L.sleep(800)
  sc.check('probe off: no more PROBE lines', b.tLines('PROBE ev=', from).length === 0, b.tLines('PROBE ev=', from).map((x) => x.line).join(' | '))
}, { timeout: 120 })
