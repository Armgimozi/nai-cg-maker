// 반지 칸 (DESIGN 9.4, 2026-10-08 사용자 결정 B 안: 인벤토리 2×2 의 왼쪽 세로 두 칸 = 창 칸 1·3, item/RingSlots).
// 봇은 바닐라 클라이언트처럼 창 누르기를 날 패킷으로 보내고 (lib rawClick), 서버의 [T] RINGS 줄 (프로필 r1·r2, 2×2 다섯 칸 s0..s4,
// 인벤토리의 반지, 칸 밖 사본 strays, 땅의 반지 ground, 효과) 과 다시 받은 창 (클라이언트가 보는 칸) 을 함께 본다.
//   1. 끼기·빼기: 누르기 (손에 든 반지를 칸에), 웅크리고 누르기 (가방 → 빈 반지 칸, 반지 칸 → 가방), 숫자 키, 왼손 바꾸기, 바꾸기
//   2. 거절: 반지가 아닌 것, 오른쪽 두 칸과 결과 칸, 같은 반지 둘, 버리기 (Q), 두 번 누르기, 끌기, 창작 모드의 칸 쓰기
//   3. 제작 없음: 2×2 에 판자 둘을 세로로 (/item) 넣어도 결과 칸이 비고, 1초 안에 판자는 인벤토리로 돌아가고 반지가 다시 비친다
//   4. 효과: 스태미나 회복 반지를 끼면 회복이 1.2 배 (식과 잰 값), 빼면 돌아간다
//   5. 남는 것: 창 닫기, 다시 접속, 죽음과 다시 태어남, 다른 세계 다녀오기. 끼고 있던 것이 그대로, 겹친 반지도 땅에 떨어진 반지도 없다
//   6. 다시 켠 뒤 (rings_check.js) 볼 값을 RUN_DIR/rings.json 에 적는다
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

/** PlayerInventory 칸 번호 → 창 칸 번호 (단축 0..8 → 36..44, 가방 9..35 그대로, 왼손 40 → 45, 갑옷 36..39 → 8..5). */
function rawOf (idx) {
  if (idx < 9) return 36 + idx
  if (idx < 36) return idx
  if (idx === 40) return 45
  return 8 - (idx - 36)
}

/** RINGS 줄의 inv= → [{idx, id, worn}] */
function invOf (kv) {
  if (!kv || !kv.inv || kv.inv === '-') return []
  return kv.inv.split(',').map((x) => {
    const [i, id] = x.split(':')
    return { idx: +i, id }
  })
}

L.run('rings', async (sc) => {
  let b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  const mode0 = (b.p.login && b.p.login.gamemode) || 'adventure'
  const show = async () => (await b.cmd('/soulstest ring show', 'RINGS ')).kv || {}
  const ringsIn = (kv) => invOf(kv).filter((x) => x.id)
  const total = (kv) => ringsIn(kv).length + ['r1', 'r2'].filter((k) => kv[k] && kv[k] !== '-').length
  // 손 (커서) 의 것을 빈 가방 칸에 내려놓는다
  const putDown = async () => {
    const empty = b.bot.inventory.slots.findIndex((it, i) => i >= 9 && i <= 35 && !it)
    if (empty >= 0) await b.rawClick(empty, 0, 0)
    return empty
  }

  // 시작: 반지 없음, 인벤토리를 비우고 반지 아닌 것 둘 (단축 칸 0 의 막대, 왼손의 방패) 만 (다시 돌려도 같은 출발)
  await b.cmd('/soulstest ring equip 1 none', 'RING_SET')
  await b.cmd('/soulstest ring equip 2 none', 'RING_SET')
  await b.cmd('/clear @s', null, 1500)
  await b.cmd('/item replace entity @s hotbar.0 with minecraft:stick', null, 1500)
  await b.cmd('/item replace entity @s weapon.offhand with minecraft:shield', null, 1500)
  await b.syncInventory()
  let s = await show()
  if (!sc.check('starts with no rings worn, 2x2 empty', s.r1 === '-' && s.r2 === '-' && ['s0', 's1', 's2', 's3', 's4'].every((k) => s[k] === '-'),
    JSON.stringify(s))) return

  // ── 효과 기준: 반지 없이 스태미나 회복 ──
  const measure = async () => {
    await b.cmd('/soulstest stamina set 5', 'STAMINA ')
    await L.sleep(900)
    const a = await b.cmd('/soulstest stamina', 'STAMINA ')
    await L.sleep(450)
    const c = await b.cmd('/soulstest stamina', 'STAMINA ')
    if (!a.kv || !c.kv) return { ok: false }
    const dt = L.num(c.kv.t) - L.num(a.kv.t)
    const capped = L.num(c.kv.cur) >= L.num(c.kv.max) - 0.01
    return { ok: dt > 0 && !capped, measured: (L.num(c.kv.cur) - L.num(a.kv.cur)) / dt, formula: L.num(c.kv.rate), a: a.line, c: c.line }
  }
  const base = await measure()
  sc.check('baseline stamina regen measured (no ring): per-tick gain equals the formula rate', base.ok && Math.abs(base.measured - base.formula) < 0.02 * base.formula,
    JSON.stringify(base))

  // ── 반지 넷 (스태미나 둘, 강인도, 쳐내기) ──
  for (const id of ['test_stamina', 'test_poise', 'test_parry', 'test_stamina']) await b.cmd('/soulstest ring give ' + id, 'RING_GIVE')
  const unknown = await b.cmd('/soulstest ring give gatekeeper_band', 'RING_GIVE')
  sc.check('only rings.yml ids can be given (no lore rings ship)', unknown.kv && unknown.kv.ok === 'false', unknown.line || '')
  await b.syncInventory()
  s = await show()
  sc.check('four test rings in the backpack', ringsIn(s).length === 4 && ringsIn(s).every((x) => x.idx >= 9 && x.idx <= 35), s.inv)

  // ── 1a. 누르기로 끼기: 가방의 스태미나 반지를 집어 반지 칸 1 (창 칸 1) 에 ──
  const stam = ringsIn(s).find((x) => x.id === 'test_stamina')
  await b.rawClick(rawOf(stam.idx), 0, 0)
  let from = b.sys.length
  await b.rawClick(1, 0, 0)
  let act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('click: ring on cursor into ring slot 1 (RING act=put, profile r1, marked copy in craft slot 1, cursor empty)', act && act.kv.act === 'put' &&
    s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.cursor === '-' && ringsIn(s).length === 3, (act ? act.line : 'no RING line') + ' | ' + JSON.stringify(s))
  sc.check('client sees the ring in slot 1 and nothing in the result slot', b.ringAt(1) === 'test_stamina' && b.ringAt(0) === '',
    `slot1=${b.ringAt(1)} slot0=${b.ringAt(0)}`)

  // ── 4a. 효과: 회복 1.2 배 ──
  s = await show()
  const worn = await measure()
  sc.check('stamina-regen ring worn: RINGS regen=1.2000 and formula rate x1.2', L.num(s.regen) === 1.2 && Math.abs(worn.formula - base.formula * 1.2) < 1e-3,
    `regen=${s.regen} rate ${base.formula} -> ${worn.formula}`)
  sc.check('stamina-regen ring worn: measured regen x1.2 (±3%)', worn.ok && base.ok && Math.abs(worn.measured / base.measured - 1.2) < 0.036,
    `${base.measured && base.measured.toFixed(4)} -> ${worn.measured && worn.measured.toFixed(4)}`)

  // ── 1b. 웅크리고 누르기: 가방의 강인도 반지 → 빈 반지 칸 2 ──
  s = await show()
  const poise = ringsIn(s).find((x) => x.id === 'test_poise')
  from = b.sys.length
  await b.rawClick(rawOf(poise.idx), 0, 1)
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('shift-click a ring in the backpack: equips into the free ring slot 2 (RING act=equip)', act && act.kv.act === 'equip' && s.r2 === 'test_poise' &&
    s.s3 === 'test_poise*' && L.num(s.poise) === 0.4 && ringsIn(s).length === 2, (act ? act.line : 'none') + ' | ' + JSON.stringify(s))
  sc.check('poise hook value while worn (poise=0.40, no system reads it yet)', L.num(s.poise) === 0.4, s.poise)

  // ── 1c. 반지 칸에서 웅크리고 누르기: 가방으로 ──
  from = b.sys.length
  await b.rawClick(3, 0, 1)
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('shift-click ring slot 2: unequips into the backpack (RING act=unequip), poise back to 0', act && act.kv.act === 'unequip' && s.r2 === '-' && s.s3 === '-' &&
    L.num(s.poise) === 0 && ringsIn(s).some((x) => x.id === 'test_poise'), (act ? act.line : 'none') + ' | ' + JSON.stringify(s))

  // ── 2a. 같은 반지 둘은 끼지 않는다 ──
  const second = ringsIn(s).find((x) => x.id === 'test_stamina')
  await b.rawClick(rawOf(second.idx), 0, 0)
  from = b.sys.length
  await b.rawClick(3, 0, 0)
  const same = await b.waitT('RING_SAME', 2000, from)
  s = await show()
  sc.check('the same ring twice is refused (RING_SAME), the second copy stays on the cursor', same && s.r2 === '-' && s.cursor === 'test_stamina',
    (same ? same.line : 'no RING_SAME') + ' | ' + JSON.stringify(s))
  await putDown()
  s = await show()
  sc.check('nothing lost or duplicated so far (4 rings: 1 worn + 3 carried)', total(s) === 4 && s.cursor === '-' && L.num(s.strays) === 0, JSON.stringify(s))

  // ── 2b. 반지가 아닌 것: 곤봉 (단축 칸 0 = 창 칸 36) 을 들고 반지 칸·지운 칸 ──
  await b.rawClick(36, 0, 0)
  s = await show()
  const club = s.cursor
  from = b.sys.length
  for (const slot of [3, 2, 4, 0]) await b.rawClick(slot, 0, 0)
  const denies = b.tLines('RING_DENY', from).map((x) => x.kv.slot)
  s = await show()
  sc.check(`non-ring (${club}) refused by ring slot 2, the two erased craft slots and the result slot`, ['3', '2', '4', '0'].every((x) => denies.includes(x)) &&
    ['s0', 's2', 's3', 's4'].every((k) => s[k] === '-') && s.cursor === club, 'denied ' + denies.join(',') + ' | ' + JSON.stringify(s))
  sc.check('client view after the refusals: craft slots 0, 2, 3, 4 empty (no ghost item)', [0, 2, 3, 4].every((i) => b.ringAt(i) === ''),
    [0, 2, 3, 4].map((i) => i + ':' + JSON.stringify(b.bot.inventory.slots[i] && b.bot.inventory.slots[i].name)).join(' '))
  await b.rawClick(36, 0, 0)
  // 웅크리고 누른 반지 아닌 것은 2×2 로 가지 않는다 (바닐라: 단축 줄 → 가방). 곤봉은 다시 단축 칸 0 으로 (숫자 키 시험이 쓴다)
  await b.rawClick(36, 0, 1)
  s = await show()
  sc.check('shift-clicking a non-ring never lands in the 2x2', ['s0', 's1', 's2', 's3', 's4'].every((k) => s[k] === '-' || s[k].endsWith('*')), JSON.stringify(s))
  const clubAt = b.bot.inventory.slots.findIndex((it, i) => i >= 9 && i <= 44 && it && it.name === club)
  if (clubAt >= 0 && clubAt !== 36) {
    await b.rawClick(clubAt, 0, 0)
    await b.rawClick(36, 0, 0)
  }

  // ── 1d. 숫자 키: 쳐내기 반지를 단축 칸 3 으로 옮긴 뒤 반지 칸 2 위에서 3 을 누른다 ──
  s = await show()
  const parry = ringsIn(s).find((x) => x.id === 'test_parry')
  await b.rawClick(rawOf(parry.idx), 0, 0)
  await b.rawClick(39, 0, 0)
  from = b.sys.length
  await b.rawClick(3, 3, 2)
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('number key over ring slot 2 with a ring in that hotbar slot: equips it (RING act=hotbar), hotbar slot empty', act && act.kv.act === 'hotbar' &&
    s.r2 === 'test_parry' && !ringsIn(s).some((x) => x.idx === 3) && L.num(s.parry) === 2, (act ? act.line : 'none') + ' | ' + JSON.stringify(s))
  // 숫자 키 0 (곤봉) 은 거절
  from = b.sys.length
  await b.rawClick(3, 0, 2)
  const numDeny = await b.waitT('RING_DENY', 2000, from)
  s = await show()
  sc.check('number key with a non-ring in that hotbar slot is refused', numDeny && s.r2 === 'test_parry', (numDeny ? numDeny.line : 'none') + ' | ' + JSON.stringify(s))

  // ── 1e. 왼손 바꾸기 (F, 숫자 키 40): 왼손에 방패가 있으면 거절, 비우면 반지가 왼손으로 갔다가 돌아온다 ──
  from = b.sys.length
  await b.rawClick(3, 40, 2)
  const offDeny = await b.waitT('RING_DENY', 2000, from)
  sc.check('offhand swap with a shield in the off hand is refused', !!offDeny, offDeny ? offDeny.line : 'none')
  await b.rawClick(45, 0, 0)
  await putDown()
  from = b.sys.length
  await b.rawClick(3, 40, 2)
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('offhand swap with an empty off hand: the worn ring goes to the off hand (RING act=offhand)', act && act.kv.act === 'offhand' && s.r2 === '-' &&
    ringsIn(s).some((x) => x.idx === 40 && x.id === 'test_parry'), (act ? act.line : 'none') + ' | ' + JSON.stringify(s))
  from = b.sys.length
  await b.rawClick(3, 40, 2)
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('offhand swap again: the ring comes back from the off hand into ring slot 2', act && s.r2 === 'test_parry' && !ringsIn(s).some((x) => x.idx === 40),
    (act ? act.line : 'none') + ' | ' + JSON.stringify(s))

  // ── 2c. 버리기 (Q, Ctrl+Q) 와 두 번 누르기 ──
  from = b.sys.length
  await b.rawClick(1, 0, 4)
  await b.rawClick(3, 1, 4)
  s = await show()
  sc.check('Q / Ctrl+Q on a ring slot is refused: nothing dropped', b.tLines('RING_DENY', from).length >= 2 && s.r1 === 'test_stamina' && s.r2 === 'test_parry' &&
    L.num(s.ground) === 0, JSON.stringify(s))
  const poiseNow = ringsIn(s).find((x) => x.id === 'test_poise')
  await b.rawClick(rawOf(poiseNow.idx), 0, 0)
  await b.rawClick(rawOf(poiseNow.idx), 0, 6)
  s = await show()
  sc.check('double-click (collect) with a ring on the cursor collects nothing: worn rings untouched, poise ring still on the cursor',
    s.r1 === 'test_stamina' && s.r2 === 'test_parry' && s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' && s.cursor === 'test_poise', JSON.stringify(s))
  await b.rawClick(rawOf(poiseNow.idx), 0, 0)

  // ── 2d. 끌기 (빵 16 개를 오른쪽 두 칸에 나눠 놓기) ──
  await b.cmd('/give @s minecraft:bread 16', null, 1500)
  await b.syncInventory()
  const bread = b.bot.inventory.slots.findIndex((it, i) => i >= 9 && it && it.name === 'bread')
  if (sc.check('bread given for the drag test', bread >= 0, String(bread))) {
    await b.rawClick(bread, 0, 0)
    from = b.sys.length
    await b.rawClick(-999, 0, 5, { sync: false })
    await b.rawClick(2, 1, 5, { sync: false })
    await b.rawClick(4, 1, 5, { sync: false })
    await b.rawClick(-999, 2, 5)
    const drag = await b.waitT('RING_DENY', 2000, from)
    s = await show()
    sc.check('dragging a stack across the erased craft slots is refused (RING_DENY why=drag), slots stay empty', drag && drag.kv.why === 'drag' &&
      s.s2 === '-' && s.s4 === '-' && s.cursor === 'bread', (drag ? drag.line : 'none') + ' | ' + JSON.stringify(s))
    await b.rawClick(bread, 0, 0)
  }

  // ── 2e. 창작 모드: "모두 지우기" 처럼 2×2 칸을 비우라는 칸 쓰기 ──
  await b.cmd('/gamemode creative', null, 1500)
  from = b.sys.length
  b.creativeSlot(1, null)
  b.creativeSlot(3, null)
  await L.sleep(600)
  s = await show()
  sc.check('creative set-slot on the ring slots is refused (RING_DENY why=creative), rings stay worn and shown', b.tLines('RING_DENY', from).some((x) => x.kv.why === 'creative') &&
    s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.r2 === 'test_parry' && s.s3 === 'test_parry*', JSON.stringify(s))
  await b.cmd('/gamemode ' + mode0, null, 1500)

  // ── 3. 2×2 제작 없음: 반지 칸에 판자 둘을 세로로 (바닐라라면 막대 넷) ──
  await b.cmd('/item replace entity @s player.crafting.0 with minecraft:oak_planks', null, 1500)
  await b.cmd('/item replace entity @s player.crafting.2 with minecraft:oak_planks', null, 1500)
  s = await show()
  const planksIn = s.s1 === 'oak_planks' || s.s3 === 'oak_planks'
  sc.check('no crafting in the 2x2: two planks stacked in the grid give no result (s0 empty)', s.s0 === '-', JSON.stringify(s) + (planksIn ? '' : ' (이미 돌려줬다)'))
  await L.sleep(1500)
  await b.syncInventory()
  s = await show()
  const planks = b.bot.inventory.slots.filter((it, i) => i >= 9 && it && it.name === 'oak_planks').reduce((n, it) => n + it.count, 0)
  sc.check('within a second the planks go back to the inventory and the rings show again (profile untouched)', s.s0 === '-' && s.s1 === 'test_stamina*' &&
    s.s3 === 'test_parry*' && s.r1 === 'test_stamina' && planks === 2, `planks=${planks} ` + JSON.stringify(s))
  sc.check('client: result slot empty, rings in slots 1 and 3', b.ringAt(0) === '' && b.ringAt(1) === 'test_stamina' && b.ringAt(3) === 'test_parry',
    `0=${b.ringAt(0)} 1=${b.ringAt(1)} 3=${b.ringAt(3)}`)

  // ── 5a. 창 닫기: 바닐라는 2×2 를 인벤토리로 돌려준다. 끼고 있는 그대로, 겹친 사본 없음 ──
  const carried = ringsIn(s).length
  b.closeInventory()
  await L.sleep(600)
  await b.syncInventory()
  s = await show()
  sc.check('after closing the inventory: still worn and shown, no copies returned to the inventory (strays=0)', s.r1 === 'test_stamina' && s.r2 === 'test_parry' &&
    s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' && L.num(s.strays) === 0 && ringsIn(s).length === carried, JSON.stringify(s))
  sc.check('after closing: client still sees both rings', b.ringAt(1) === 'test_stamina' && b.ringAt(3) === 'test_parry', `1=${b.ringAt(1)} 3=${b.ringAt(3)}`)

  // ── 5b. 다시 접속 ──
  await b.quit()
  await L.sleep(1500)
  b = await L.connect(sc, { name: b.name })
  await L.sleep(2000)
  await b.syncInventory()
  s = await show()
  sc.check('after relog: rings worn and shown, nothing dropped on the ground, no strays', s.r1 === 'test_stamina' && s.r2 === 'test_parry' && s.s1 === 'test_stamina*' &&
    s.s3 === 'test_parry*' && L.num(s.ground) === 0 && L.num(s.strays) === 0 && ringsIn(s).length === carried, JSON.stringify(s))
  sc.check('after relog: client sees both rings, effect not doubled (regen=1.2000)', b.ringAt(1) === 'test_stamina' && b.ringAt(3) === 'test_parry' && L.num(s.regen) === 1.2,
    `1=${b.ringAt(1)} 3=${b.ringAt(3)} regen=${s.regen}`)

  // ── 5c. 죽음과 다시 태어남 (몸이 치워질 때 바닐라는 2×2 를 떨어뜨린다) ──
  const r0 = b.p.respawns.length
  await b.cmd('/soulstest kill', 'KILL')
  const end = Date.now() + 6000
  while (b.p.respawns.length === r0 && Date.now() < end) await L.sleep(100)
  if (b.p.respawns.length === r0) { b.respawn(); await L.sleep(2000) }
  sc.check('died and respawned', b.p.respawns.length > r0, `respawns ${r0} -> ${b.p.respawns.length}`)
  await L.sleep(2500)
  await b.syncInventory()
  s = await show()
  sc.check('after death and respawn: rings worn and shown, none dropped (ground=0), no strays', s.r1 === 'test_stamina' && s.r2 === 'test_parry' &&
    s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' && L.num(s.ground) === 0 && L.num(s.strays) === 0 && ringsIn(s).length === carried, JSON.stringify(s))

  // ── 5d. 다른 세계 다녀오기 (로비) ──
  await b.cmd('/souls tp lobby', null, 2500)
  await L.sleep(1500)
  s = await show()
  const inLobby = s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' && L.num(s.strays) === 0 && ringsIn(s).length === carried
  await b.cmd('/souls tp room', null, 2500)
  await L.sleep(1500)
  s = await show()
  sc.check('world change (lobby and back): rings worn and shown, no copies in the inventory', inLobby && s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' &&
    s.s3 === 'test_parry*' && L.num(s.strays) === 0 && ringsIn(s).length === carried, JSON.stringify(s))

  // ── 5e. 다른 창 (깔때기) 이 열린 채 죽는다: 2×2 에 손이 닿지 않아 비우지 못한 사본은 몸이 치워질 때 떨어지려다 막힌다 ──
  const c0 = await b.cmd('/soulstest ring chest', 'RING_CHEST')
  await L.sleep(500)
  const r1 = b.p.respawns.length
  await b.cmd('/soulstest kill', 'KILL')
  const end2 = Date.now() + 6000
  while (b.p.respawns.length === r1 && Date.now() < end2) await L.sleep(100)
  if (b.p.respawns.length === r1) { b.respawn(); await L.sleep(2000) }
  await L.sleep(2500)
  await b.syncInventory()
  s = await show()
  sc.check('death with another container open (hopper): rings still worn and shown, nothing dropped, no copies in the inventory', c0.kv &&
    s.r1 === 'test_stamina' && s.r2 === 'test_parry' && s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' && L.num(s.ground) === 0 &&
    L.num(s.strays) === 0 && ringsIn(s).length === carried, (c0.line || '') + ' | ' + JSON.stringify(s))

  // ── 4b. 빼면 효과도 빠진다 ──
  b.closeInventory()
  await L.sleep(400)
  await b.syncInventory()
  from = b.sys.length
  await b.rawClick(1, 0, 0)
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('click an empty hand on ring slot 1: takes the ring (RING act=take), regen back to 1.0', act && act.kv.act === 'take' && s.r1 === '-' &&
    s.cursor === 'test_stamina' && L.num(s.regen) === 1, (act ? act.line : 'none') + ' | ' + JSON.stringify(s))
  await putDown()
  const off = await measure()
  sc.check('ring removed: measured stamina regen back to the baseline (±3%)', off.ok && base.ok && Math.abs(off.measured / base.measured - 1) < 0.03,
    `${base.measured && base.measured.toFixed(4)} -> ${off.measured && off.measured.toFixed(4)}`)

  // ── 6. 다시 켠 뒤 볼 값: 스태미나 반지를 다시 끼운다 ──
  s = await show()
  const again = ringsIn(s).find((x) => x.id === 'test_stamina')
  await b.rawClick(rawOf(again.idx), 0, 1)
  s = await show()
  sc.check('equipped again for the restart check (r1 test_stamina, r2 test_parry)', s.r1 === 'test_stamina' && s.r2 === 'test_parry', JSON.stringify(s))
  const exp = { name: b.name, r1: s.r1, r2: s.r2, carried: ringsIn(s).length, regen: s.regen }
  if (L.ENV.runDir) fs.writeFileSync(path.join(L.ENV.runDir, 'rings.json'), JSON.stringify(exp, null, 1))
  sc.note('다시 켠 뒤 볼 값: ' + JSON.stringify(exp))
  sc.check('no kick during the rings scenario', !b.kick, b.kick || '')
}, { timeout: 300 })
