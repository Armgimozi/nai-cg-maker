// 막기 성분 + generic 피해 서버 시험 (3.4, 13.4 표 첫 줄, 14 M0 "막기 성분 + generic 피해 서버 시험").
// 우클릭(use_item)으로 시험 막기 도구를 들고 /soulstest hit 로 원인 있는 generic 피해를 넣는다.
//   empty   빈 감소표 + #bypasses_shield (설계 기본): 막는 자세인데 피해가 그대로, 밀림·내구도 감소 없음
//   control 바닐라 방패처럼 다 막는 감소표 (대조군): 시험이 바닐라 막기를 알아보는지. 피해 0
//   bypass  다 막는 감소표 + #bypasses_shield: 우회가 먹어 피해가 그대로, 밀림·내구도 감소 없음
// 놓기(block_dig 상태 5) 뒤에는 막지 않는다. generic 은 방어구를 지나친다, 데이터팩 피해 종류 souls:hit.
'use strict'
const L = require('./lib')

L.run('guard', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(500)

  const cases = [
    ['empty', { full: true, clean: true }],
    ['control', { full: false, clean: false }],
    ['bypass', { full: true, clean: true }]
  ]
  for (const [kind, want] of cases) {
    await b.cmd('/soulstest heal', 'HEAL')
    const g = await b.cmd('/soulstest guard ' + kind, 'GUARD')
    if (!sc.checkCmd(`guard ${kind}: tool given`, g, (r) => r.kv.kind === kind, g.line)) continue
    await L.sleep(500)
    const held = b.bot.heldItem
    const comps = held && Array.isArray(held.components) ? held.components.map((c) => c.type) : null
    if (comps) sc.check(`guard ${kind}: item has blocks_attacks + use_effects`, comps.includes('blocks_attacks') && comps.includes('use_effects'), comps.join(','))
    const hp0 = b.health
    b.use()
    await L.sleep(500)
    const h = await b.cmd('/soulstest hit 2', 'HIT ')
    await L.sleep(250)
    b.release()
    if (!sc.checkCmd(`guard ${kind}: server sees blocking`, h, (r) => r.kv.blocking === 'true', h.line)) { await L.sleep(400); continue }
    sc.check(`guard ${kind}: generic damage ${want.full ? 'goes through in full' : 'fully blocked (control)'}`, h.kv.full === String(want.full), `dealt=${h.kv.dealt}`)
    if (want.clean) {
      sc.check(`guard ${kind}: no vanilla knockback`, h.kv.knockback === 'false', 'knockback=' + h.kv.knockback)
      sc.check(`guard ${kind}: no durability loss`, /^(0->0|-->-)$/.test(h.kv.dur), 'dur=' + h.kv.dur)
    } else {
      sc.check(`guard ${kind}: vanilla block side effects seen (control works)`, h.kv.knockback === 'true' || !/^(0->0|-->-)$/.test(h.kv.dur), `knockback=${h.kv.knockback} dur=${h.kv.dur}`)
    }
    sc.check(`guard ${kind}: client health ${want.full ? 'drops by 2' : 'unchanged'}`, want.full ? Math.abs(hp0 - 2 - b.health) < 0.6 : Math.abs(hp0 - b.health) < 0.01, `hp ${hp0} → ${b.health}`)
    await L.sleep(400)
  }

  // 놓은 뒤에는 막지 않는다 (대조군 도구로: 막았다면 피해 0)
  await b.cmd('/soulstest heal', 'HEAL')
  await b.cmd('/soulstest guard control', 'GUARD')
  await L.sleep(400)
  b.use()
  await L.sleep(400)
  b.release()
  await L.sleep(300)
  const off = await b.cmd('/soulstest hit 2', 'HIT ')
  sc.checkCmd('released guard (status 5) does not block', off, (r) => r.kv.blocking === 'false' && r.kv.full === 'true', off.line)

  // generic 은 방어구를 지나친다 (방어력 +20 을 잠깐 걸고 맞는다)
  await b.cmd('/soulstest heal', 'HEAL')
  const ar = await b.cmd('/soulstest hit 3 type=generic armor', 'HIT ')
  sc.checkCmd('generic damage bypasses armor', ar, (r) => r.kv.full === 'true' && L.num(r.kv.armor) >= 20, ar.line)

  // 데이터팩 피해 종류 souls:hit (12.2)
  await b.cmd('/soulstest heal', 'HEAL')
  const sh = await b.cmd('/soulstest hit 3 type=hit', 'HIT ')
  if (sh.kv && /없음/.test(sh.kv.type || '')) sc.miss('souls:hit damage type registered', sh.line)
  else sc.checkCmd('souls:hit damage type deals full damage', sh, (r) => r.kv.type === 'souls:hit' && r.kv.full === 'true', sh.line)
  await b.cmd('/soulstest heal', 'HEAL')
  sc.check('no kick during guard scenario', !b.kick, b.kick || '')
})
