// 반지 칸 (DESIGN 9.4, 2026-10-08 사용자 결정 B 안: 인벤토리 2×2 의 왼쪽 세로 두 칸 = 창 칸 1·3, item/RingSlots).
// 봇은 바닐라 클라이언트처럼 창 누르기를 날 패킷으로 보내고 (lib rawClick), 서버의 [T] RINGS 줄 (프로필 r1·r2, 2×2 다섯 칸 s0..s4,
// 인벤토리의 반지, 칸 밖 사본 strays, 땅의 반지 ground, 효과) 과 다시 받은 창 (클라이언트가 보는 칸) 을 함께 본다.
//   1. 끼기·빼기: 누르기 (손에 든 반지를 칸에), 웅크리고 누르기 (가방 → 빈 반지 칸, 반지 칸 → 가방), 숫자 키, 왼손 바꾸기, 바꾸기
//   2. 거절: 반지가 아닌 것, 오른쪽 두 칸과 결과 칸, 같은 반지 둘, 버리기 (Q), 두 번 누르기, 끌기, 창작 모드의 칸 쓰기
//   3. 제작 없음: 2×2 에 판자 둘을 세로로 (/item) 넣어도 결과 칸이 비고, 1초 안에 판자는 인벤토리로 돌아가고 반지가 다시 비친다
//   4. 효과: 스태미나 회복 반지를 끼면 회복이 1.2 배 (식과 잰 값), 빼면 돌아간다
//   5. 남는 것: 창 닫기, 다시 접속, 죽음과 다시 태어남, 다른 세계 다녀오기. 끼고 있던 것이 그대로, 겹친 반지도 땅에 떨어진 반지도 없다
//   7. 가장자리 (검토 ring-polish): 가방이 다 차면 빼기 거절, 손에 반지를 든 채 가방이 차면 닫기·나가기에서 반지 칸으로 (칸이 다 차면
//      발밑으로), 가방이 찬 채 왼손에서 집은 방패는 사라지지 않고 떨어진다, 칸 밖에 나온 사본은 반지가 아니다 (숫자 키로 겹치지 않는다),
//      칸이 비어 보여도 프로필의 반지는 덮어써지지 않는다, 낀 반지의 둘째는 웅크리고 누르면 단축 줄로, 상자가 열린 채 다른 세계로 가도
//      사본이 가방에 오지 않는다, /souls reload 뒤 설명 칸이 새 값
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

  // ── 5e. 다른 창 (상자) 이 열린 채 죽는다: 죽을 때 그 창을 먼저 닫고 2×2 를 비운다 (사본이 떨어지거나 가방에 오지 않는다) ──
  const c0 = await b.cmd('/soulstest ring chest', 'RING_CHEST')
  await L.sleep(500)
  from = b.sys.length
  const r1 = b.p.respawns.length
  await b.cmd('/soulstest kill', 'KILL')
  const end2 = Date.now() + 6000
  while (b.p.respawns.length === r1 && Date.now() < end2) await L.sleep(100)
  if (b.p.respawns.length === r1) { b.respawn(); await L.sleep(2000) }
  await L.sleep(2500)
  await b.syncInventory()
  s = await show()
  sc.check('death with another container open (chest): rings still worn and shown, nothing dropped, no copies in the inventory, no sweep needed',
    c0.kv && c0.kv.open === 'CHEST' && s.r1 === 'test_stamina' && s.r2 === 'test_parry' && s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' &&
    L.num(s.ground) === 0 && L.num(s.strays) === 0 && ringsIn(s).length === carried && b.tLines('RING_SWEEP', from).length === 0,
    (c0.line || '') + ' | sweeps ' + b.tLines('RING_SWEEP', from).map((x) => x.line).join(';') + ' | ' + JSON.stringify(s))

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

  // ── 7. 가장자리 ──
  const cobble = async (stacks) => {
    await b.cmd('/clear @s', null, 1200)
    if (stacks > 0) await b.cmd(`/give @s minecraft:cobblestone ${64 * stacks}`, null, 1500)
    await b.syncInventory()
  }
  const reset = async () => {
    b.closeInventory()
    await L.sleep(300)
    await b.cmd('/soulstest ring equip 1 none', 'RING_SET')
    await b.cmd('/soulstest ring equip 2 none', 'RING_SET')
    await b.cmd('/kill @e[type=item,distance=..16]', null, 800)
    await cobble(0)
  }

  // 7a. 가방 (단축 줄까지 36 칸) 이 다 차면 낀 반지를 빼지 않는다: 손에 든 반지가 돌아갈 자리가 늘 있게 (검토 R1)
  await reset()
  await b.cmd('/soulstest ring equip 1 test_stamina', 'RING_SET')
  await cobble(36)
  const bagFull = b.bot.inventory.slots.slice(9, 45).every((x) => !!x)
  from = b.sys.length
  await b.rawClick(1, 0, 0)
  const full1 = await b.waitT('RING_FULL', 2000, from)
  s = await show()
  sc.check('full bag: an empty-hand click on a worn ring is refused (RING_FULL), the ring stays worn, the cursor stays empty', bagFull && full1 &&
    s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.cursor === '-', `full=${bagFull} ` + (full1 ? full1.line : 'no RING_FULL') + ' | ' + JSON.stringify(s))
  from = b.sys.length
  await b.rawClick(1, 0, 1)
  const full2 = await b.waitT('RING_FULL', 2000, from)
  s = await show()
  sc.check('full bag: shift-clicking a worn ring is refused too (RING_FULL), still worn', full2 && s.r1 === 'test_stamina' && s.s1 === 'test_stamina*',
    (full2 ? full2.line : 'no RING_FULL') + ' | ' + JSON.stringify(s))
  // 가방의 반지로 바꾸기는 가방이 차도 된다 (집은 칸이 비었다가 빼낸 반지가 그 자리에 간다)
  await b.cmd('/item replace entity @s inventory.11 with minecraft:air', null, 800)
  await b.cmd('/soulstest ring give test_poise', 'RING_GIVE')
  await b.syncInventory()
  await b.rawClick(20, 0, 0)
  from = b.sys.length
  await b.rawClick(1, 0, 0)
  act = await b.waitT('RING act=', 2000, from)
  await b.rawClick(20, 0, 0)
  s = await show()
  sc.check('full bag: swapping through a ring from the bag still works (RING act=swap), the old ring lands in the freed bag slot', act && act.kv.act === 'swap' &&
    s.r1 === 'test_poise' && s.cursor === '-' && ringsIn(s).some((x) => x.idx === 20 && x.id === 'test_stamina'), (act ? act.line : 'none') + ' | ' + JSON.stringify(s))

  // 7b. 손에 반지를 든 채 가방이 찬다 (빼고 나서 무엇을 받았다) → 창 닫기: 반지는 빈 반지 칸으로 돌아간다 (사라지지 않는다)
  const takeThenFill = async (ring2) => {
    await reset()
    await b.cmd('/soulstest ring equip 1 test_stamina', 'RING_SET')
    if (ring2) await b.cmd('/soulstest ring equip 2 ' + ring2, 'RING_SET')
    await cobble(35)
    return b.bot.inventory.slots[35] === null || b.bot.inventory.slots[35] === undefined
  }
  let spare = await takeThenFill(null)
  await b.rawClick(1, 0, 0)
  s = await show()
  const took = s.cursor === 'test_stamina' && s.r1 === '-'
  await b.cmd('/item replace entity @s inventory.26 with minecraft:cobblestone 64', null, 1000)
  from = b.sys.length
  b.closeInventory()
  let resc = await b.waitT('RING_RESCUE', 2000, from)
  await L.sleep(400)
  s = await show()
  sc.check('ring on the cursor, bag filled, inventory closed: the ring goes back into the free ring slot (RING_RESCUE to=ring1), nothing lost',
    spare && took && resc && resc.kv.to === 'ring1' && s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.cursor === '-' && L.num(s.ground) === 0,
    `spare=${spare} took=${took} ` + (resc ? resc.line : 'no RING_RESCUE') + ' | ' + JSON.stringify(s))

  // 7c. 같은 차림에서 나간다 (창을 닫지 않고): 다시 들어오면 반지가 끼워져 있다
  spare = await takeThenFill(null)
  await b.rawClick(1, 0, 0)
  s = await show()
  const took2 = s.cursor === 'test_stamina' && s.r1 === '-'
  await b.cmd('/item replace entity @s inventory.26 with minecraft:cobblestone 64', null, 1000)
  await b.quit()
  await L.sleep(1500)
  b = await L.connect(sc, { name: b.name })
  await L.sleep(2000)
  await b.syncInventory()
  s = await show()
  sc.check('ring on the cursor, bag filled, disconnect: after relog the ring is worn again, not on the ground, no strays', spare && took2 &&
    s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.cursor === '-' && L.num(s.ground) === 0 && L.num(s.strays) === 0,
    `spare=${spare} took=${took2} ` + JSON.stringify(s))
  await b.cmd('/souls tp room', null, 1200)

  // 7d. 반지 칸이 다 찼고 손에 셋째 반지, 가방도 찼다 → 창 닫기: 발밑에 떨어진다 (자리가 나면 주워진다)
  spare = await takeThenFill('test_parry')
  await b.cmd('/soulstest ring give test_poise', 'RING_GIVE')
  await b.syncInventory()
  const poiseAt = b.bot.inventory.slots.findIndex((it, i) => i >= 9 && i <= 44 && b.ringAt(i) === 'test_poise')
  await b.rawClick(poiseAt, 0, 0)
  await b.cmd('/give @s minecraft:cobblestone 64', null, 1000)
  from = b.sys.length
  b.closeInventory()
  resc = await b.waitT('RING_RESCUE', 2000, from)
  await L.sleep(400)
  s = await show()
  sc.check('both ring slots worn, a third ring on the cursor, bag full, closed: the ring is put at the feet (RING_RESCUE to=ground), worn rings untouched',
    poiseAt >= 0 && resc && resc.kv.to === 'ground' && L.num(s.ground) === 1 && s.r1 === 'test_stamina' && s.r2 === 'test_parry' && s.cursor === '-',
    `poiseAt=${poiseAt} ` + (resc ? resc.line : 'no RING_RESCUE') + ' | ' + JSON.stringify(s))
  await b.cmd('/clear @s minecraft:cobblestone 64', null, 1000)
  await L.sleep(2500)
  s = await show()
  sc.check('...and with room again it is picked back up (nothing lost)', ringsIn(s).some((x) => x.id === 'test_poise') && L.num(s.ground) === 0, JSON.stringify(s))

  // 7e. 반지가 아닌 것도: 가방이 찬 채 왼손의 방패를 집어 들고 창을 닫으면 버리기 막기가 그것을 지우지 않고 발밑에 떨어진다 (Protection)
  await reset()
  await cobble(36)
  await b.cmd('/item replace entity @s weapon.offhand with minecraft:shield', null, 1000)
  await b.syncInventory()
  await b.rawClick(45, 0, 0)
  s = await show()
  const heldShield = s.cursor === 'shield'
  b.closeInventory()
  await L.sleep(1000)
  s = await show()
  sc.check('full bag, the off-hand shield on the cursor, inventory closed: the shield falls at the feet instead of vanishing (near=shield:1)',
    heldShield && /(^|,)shield:1(,|$)/.test(s.near || '') && s.cursor === '-', `held=${heldShield} ` + JSON.stringify(s))
  // 가방에 자리가 있으면 버리기는 여전히 막는다 (Q 는 아무것도 떨어뜨리지 않는다)
  await reset()
  await b.cmd('/item replace entity @s hotbar.0 with minecraft:stick', null, 1000)
  await b.syncInventory()
  await b.rawClick(36, 0, 4)
  await L.sleep(800)
  s = await show()
  sc.check('with room in the bag a Q drop is still blocked (nothing on the ground, the stick stays in the inventory)', !/stick/.test(s.near || '') &&
    b.bot.inventory.slots.some((it) => it && it.name === 'stick'), JSON.stringify(s))

  // 7f. 칸 밖에 나온 사본 (/item 으로 2×2 에서 단축 칸으로 베낀 것) 은 반지가 아니다: 숫자 키로 같은 반지를 낀 칸과 바꾸면 거절하고
  //     사본을 지운다 (검토 R2: 진짜 반지가 하나 더 생겼다). 1초 훑기가 먼저 지우면 다시 해 본다
  await reset()
  let copyTry = null
  let ringCountOk = true
  let lastCopy = ''
  for (let tries = 0; tries < 6 && !copyTry; tries++) {
    await b.cmd('/clear @s', null, 600)
    await b.cmd('/soulstest ring equip 1 test_stamina', 'RING_SET')
    await L.sleep(150)
    from = b.sys.length
    await b.cmd('/item replace entity @s hotbar.0 from entity @s player.crafting.0', null, 300)
    await b.rawClick(1, 0, 2, { wait: 60 })
    await L.sleep(1300)
    s = await show()
    lastCopy = `try ${tries} ` + JSON.stringify(s)
    if (total(s) !== 1 || L.num(s.strays) !== 0) ringCountOk = false
    if (b.tLines('RING_DENY', from).some((x) => x.kv.why === 'copy')) copyTry = s
  }
  sc.check('a leaked worn copy is no ring: number-key swap with it is refused (RING_DENY why=copy), the copy is swept, still exactly one ring',
    !!copyTry && ringCountOk && copyTry.r1 === 'test_stamina' && !ringsIn(copyTry).length, lastCopy)

  // 7g. 칸이 비어 보여도 (2×2 를 /item 으로 비웠다) 프로필의 반지는 덮어써지지 않는다: 다른 반지를 누르면 바꾸기 (검토 R3)
  await reset()
  await b.cmd('/soulstest ring equip 1 test_stamina', 'RING_SET')
  await b.cmd('/soulstest ring give test_poise', 'RING_GIVE')
  await b.syncInventory()
  s = await show()
  const pz = ringsIn(s).find((x) => x.id === 'test_poise')
  await b.rawClick(rawOf(pz.idx), 0, 0, { wait: 60 })
  await b.cmd('/item replace entity @s player.crafting.0 with minecraft:air', null, 200)
  from = b.sys.length
  await b.rawClick(1, 0, 0, { wait: 60 })
  act = await b.waitT('RING act=', 2000, from)
  s = await show()
  sc.check('ring slot emptied on the server while the profile still holds a ring: putting another ring swaps (RING act=swap), the old ring comes to the cursor',
    act && act.kv.act === 'swap' && s.r1 === 'test_poise' && s.cursor === 'test_stamina', (act ? act.line : 'none') + ' | ' + JSON.stringify(s))
  await putDown()

  // 7h. 낀 반지의 둘째를 웅크리고 누르면 (다른 반지 칸이 비어도) 끼지 않고 바닐라대로 단축 줄로 간다 (검토 R4: 누르기가 삼켜졌다)
  await reset()
  await b.cmd('/soulstest ring equip 1 test_stamina', 'RING_SET')
  await b.cmd('/soulstest ring give test_stamina', 'RING_GIVE')
  await b.syncInventory()
  s = await show()
  const st2 = ringsIn(s).find((x) => x.id === 'test_stamina')
  from = b.sys.length
  await b.rawClick(rawOf(st2.idx), 0, 1)
  s = await show()
  const moved = ringsIn(s).find((x) => x.id === 'test_stamina')
  sc.check('shift-click a second copy of a worn ring: no RING_SAME, not equipped, vanilla moves it from the bag to the hotbar',
    b.tLines('RING_SAME', from).length === 0 && s.r2 === '-' && st2.idx >= 9 && moved && moved.idx <= 8, `from ${st2.idx} | ` + JSON.stringify(s))

  // 7i. 상자가 열린 채 다른 세계로 (검토 R2: 2×2 에 손이 닿지 않아 사본 둘이 가방에 왔다가 다음 틱에 지워졌다)
  await reset()
  await b.cmd('/soulstest ring equip 1 test_stamina', 'RING_SET')
  await b.cmd('/soulstest ring equip 2 test_parry', 'RING_SET')
  await L.sleep(300)
  await b.cmd('/soulstest ring chest', 'RING_CHEST')
  from = b.sys.length
  await b.cmd('/souls tp lobby', null, 2500)
  await L.sleep(1500)
  s = await show()
  sc.check('world change with a chest open: no copies came into the bag (no RING_SWEEP), rings worn and shown', b.tLines('RING_SWEEP', from).length === 0 &&
    s.r1 === 'test_stamina' && s.s1 === 'test_stamina*' && s.s3 === 'test_parry*' && L.num(s.strays) === 0 && ringsIn(s).length === 0,
    b.tLines('RING_SWEEP', from).map((x) => x.line).join(';') + ' | ' + JSON.stringify(s))
  await b.cmd('/souls tp room', null, 2500)
  await L.sleep(1000)

  // 7j. /souls reload 뒤 낀 반지의 설명 칸도 새 값 (검토 R6: id 가 같은 사본을 그대로 두어 옛 효과 줄이 남았다)
  const RY = L.ENV.serverDir && path.join(L.ENV.serverDir, 'plugins', 'Soulslike', 'content', 'rings.yml')
  if (sc.check('server content/rings.yml found for the reload check', RY && fs.existsSync(RY), RY || 'SERVER_DIR 없음')) {
    const lore = () => JSON.stringify((b.bot.inventory.slots[1] && (b.bot.inventory.slots[1].components || b.bot.inventory.slots[1].nbt)) || '')
    await b.syncInventory()
    const before = lore()
    const orig = fs.readFileSync(RY, 'utf8')
    const reloaded = (m) => L.translateKeys(m.raw).includes('souls.admin.reloaded')
    try {
      fs.writeFileSync(RY, orig.replace(/stamina-regen: 1\.20/, 'stamina-regen: 1.30'))
      await b.cmd('/souls reload', reloaded, 5000)
      await L.sleep(400)
      await b.syncInventory()
      s = await show()
      const after = lore()
      sc.check('after /souls reload with stamina-regen 1.20 -> 1.30: effect 1.3 and the worn ring\'s tooltip says +30 (not +20)', L.num(s.regen) === 1.3 &&
        s.s1 === 'test_stamina*' && before.includes('+20') && after.includes('+30') && !after.includes('+20'),
        `regen=${s.regen} before+20=${before.includes('+20')} after+30=${after.includes('+30')} after+20=${after.includes('+20')}`)
    } finally {
      fs.writeFileSync(RY, orig)
      await b.cmd('/souls reload', reloaded, 5000)
    }
  }

  // 6 의 출발: 반지 칸 2 에 쳐내기, 가방에 스태미나·강인도
  await reset()
  await b.cmd('/soulstest ring equip 2 test_parry', 'RING_SET')
  await b.cmd('/soulstest ring give test_stamina', 'RING_GIVE')
  await b.cmd('/soulstest ring give test_poise', 'RING_GIVE')
  await b.syncInventory()

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
