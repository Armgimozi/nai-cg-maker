// 레벨 올리기 (5.3, 5.9), 능력치 창, 능력치가 바꾸는 것 (5.2, 5.8). 봇은 빈털터리 (레벨 1, 모두 10) 로 태어난다.
//   1. 휴식 창 → "레벨 올리기" → 창 (능력치 여섯 + 되돌린다 + 올린다, 나가기 그만둔다). 단추를 누를 때마다 새 창 (새 값, 새 표식).
//   2. 생명력 + 세 번 (비용 320 + 340 + 360), 되돌린다 한 번, 올린다: 레벨 3, 소울 −660, 최대 HP 454, 하트는 그대로 10개.
//      지난 창의 단추는 버린다 (UI_STALE). 소울이 모자라면 더하지 않는다 (LEVELUP_PLUS_DENY why=souls).
//   3. 창이 떠 있는 동안 짧은 누름은 구르지 않는다 (why=dialog). 쉬는 중에 맞으면 창이 닫힌다 (REST interrupted).
//   4. 능력치 창 (휴식 창 "능력치", /stats): 값 표와 STATS 줄이 같은 수를 낸다.
//   5. 민첩 → 이동 속도 수정자, 지력 → 해로운 효과·불붙음 길이가 준다 (AILMENT), 지구력 → 최대 스태미나.
//   6. 장비 무게 (5.8): 무기를 잔뜩 들면 무게 단계가 오르고 구르기 종류가 따라간다 (너무 무거움 = 뒷걸음, 달리기 없음).
'use strict'
const L = require('./lib')

L.run('levelup', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(400)
  const s0 = await b.cmd('/soulstest stats', 'STATS ')
  if (!sc.checkCmd('starts as deprived level 1', s0, (r) => r.kv.origin === 'deprived' && r.kv.level === '1')) return
  await b.cmd('/soulstest souls 5000', 'SOULS ')

  // ── 휴식 창 → 레벨 올리기 ──
  let d = b.p.dialogs.length
  await b.cmd('/soulstest rest', 'REST shown')
  const rest = await b.waitDialog(d, 3000)
  if (!sc.check('rest menu opens with levelup / stats', rest && b.dialogButtons(rest).levelup && b.dialogButtons(rest).stats, rest ? Object.keys(b.dialogButtons(rest)).join(',') : '창 없음')) return
  d = b.p.dialogs.length
  let from = b.sys.length
  b.clickDialog('levelup', {}, rest)
  let raw = await b.waitDialog(d, 3000)
  const op = await b.waitT('LEVELUP open', 2000, from)
  sc.check('levelup dialog: six stats, undo, confirm, exit', raw && b.dialogId(raw) === 'levelup' &&
    ['plus_vig', 'plus_mnd', 'plus_end', 'plus_str', 'plus_dex', 'plus_int', 'undo', 'confirm', 'exit'].every((k) => b.dialogButtons(raw)[k]),
    raw ? Object.keys(b.dialogButtons(raw)).join(',') : '창 없음')
  sc.check('LEVELUP open level=1 souls=5000', op && op.kv.level === '1' && op.kv.souls === '5000', op ? op.line : '줄 없음')
  if (raw) {
    const k = L.deepKeys(raw)
    // 다크 소울 꼴 표 (5.9, DECISIONS 2026-10-10): 왼쪽 레벨·보유 소울·필요 소울과 능력치 여섯 (이름 칸), 오른쪽 나온 값. 한 글자 열
    // (stat.*.tag) 은 없다
    sc.check('level-up table: left column (level, souls held/needed, six stats), right column derived values, no one-letter tags',
      ['souls.table.level.cell', 'souls.table.held.cell', 'souls.table.need.cell', 'souls.stat.vig.name.cell', 'souls.stat.int.name.cell',
        'souls.derived.max-hp.cell', 'souls.derived.load.cell', 'souls.levelup.tip'].every((x) => k.includes(x)) &&
        !k.some((x) => /^souls\.stat\.[a-z]+\.tag/.test(x)),
      k.filter((x) => x.startsWith('souls.')).slice(0, 12).join(','))
  }

  // ── 창이 떠 있는 동안 짧은 누름 ──
  from = b.sys.length
  await b.tapSneak({})
  const sk = await b.waitT('ROLL_TAP_SKIP', 1500, from)
  sc.check('sneak tap while the level-up dialog is open does not roll (why=dialog)', sk && sk.kv.why === 'dialog' && !b.tLines('ROLL ', from).length, sk ? sk.line : '줄 없음')

  // ── 생명력 + 세 번, 되돌린다, 올린다 ──
  const costs = []
  for (let i = 0; i < 3; i++) {
    d = b.p.dialogs.length
    from = b.sys.length
    b.clickDialog('plus_vig', {}, raw)
    const pl = await b.waitT('LEVELUP_PLUS', 2000, from)
    costs.push(pl ? L.num(pl.kv.cost) : NaN)
    raw = await b.waitDialog(d, 3000)
  }
  sc.check('plus vigor x3: running cost 320, 660, 1020', JSON.stringify(costs) === JSON.stringify([320, 660, 1020]), costs.join(','))
  from = b.sys.length
  const old = b.p.dialogs[b.p.dialogs.length - 2].raw
  b.clickDialog('plus_vig', {}, old)
  const stale = await b.waitT('UI_STALE', 2000, from)
  sc.check('a button from the previous dialog is stale (UI_STALE)', !!stale, stale ? stale.line : '줄 없음')
  d = b.p.dialogs.length
  b.clickDialog('undo', {}, raw)
  const un = await b.waitT('LEVELUP_UNDO', 2000, from)
  sc.check('undo removes the last point (pending=2)', un && un.kv.pending === '2', un ? un.line : '줄 없음')
  raw = await b.waitDialog(d, 3000)
  d = b.p.dialogs.length
  from = b.sys.length
  b.clickDialog('confirm', {}, raw)
  const up = await b.waitT('LEVELUP from=', 2000, from)
  sc.check('confirm: level 1 -> 3 for 660 souls', up && up.kv.from === '1' && up.kv.to === '3' && up.kv.cost === '660' && up.kv.souls === '4340', up ? up.line : '줄 없음')
  raw = await b.waitDialog(d, 3000)
  const info = await b.cmd('/soulstest info', 'INFO ')
  sc.check('vigor 12 -> max HP 454, hearts stay 10 (scale 20)', info.kv && info.kv.maxhp === '454' && info.kv.scale === '20', info.line || '')
  const hh = b.lastHealth()
  sc.check('client health bar still reads full (20 = 10 hearts)', hh && hh.health >= 19.9, hh ? 'hp=' + hh.health : '')

  // ── 소울이 모자라면 ──
  await b.cmd('/soulstest souls 100', 'SOULS ')
  d = b.p.dialogs.length
  from = b.sys.length
  b.clickDialog('plus_str', {}, raw)
  const deny = await b.waitT('LEVELUP_PLUS_DENY', 2000, from)
  sc.check('not enough souls: no point added (LEVELUP_PLUS_DENY why=souls)', deny && deny.kv.why === 'souls', deny ? deny.line : '줄 없음')
  raw = await b.waitDialog(d, 3000)

  // ── 그만둔다 → 휴식 창 → 능력치 창 ──
  d = b.p.dialogs.length
  b.clickDialog('exit', {}, raw)
  const back = await b.waitDialog(d, 3000)
  sc.check('"cancel" goes back to the rest menu', back && b.dialogId(back) === 'rest', back ? b.dialogId(back) : '창 없음')
  d = b.p.dialogs.length
  from = b.sys.length
  b.clickDialog('stats', {}, back)
  const sd = await b.waitDialog(d, 3000)
  const sl = await b.waitT('STATS ', 2000, from)
  sc.check('stats dialog opens from the rest menu and logs the same numbers', sd && sl && sl.kv.hp === '454' && sl.kv.level === '3' && sl.kv.vig === '12', sl ? sl.line : '줄 없음')
  if (sd) {
    const sk = L.deepKeys(sd)
    sc.check('stats dialog: same table (origin, level, souls, six stats | derived values, load tier under equip load)',
      ['souls.table.origin.cell', 'souls.table.held.cell', 'souls.stat.vig.name.cell', 'souls.derived.defense.cell', 'souls.derived.load.cell'].every((x) => sk.includes(x)) &&
        sk.some((x) => /^souls\.load\.[a-z]+\.rcell$/.test(x)), sk.filter((x) => x.startsWith('souls.')).slice(0, 12).join(','))
  }
  if (sd) b.clickDialog('exit', {}, sd)
  await L.sleep(300)
  const cmdStats = await b.cmd('/stats', 'STATS ', 3000)
  sc.checkCmd('/stats works for players (souls.stats)', cmdStats, (r) => r.kv.hp === '454')

  // ── 쉬는 중에 맞으면 닫힌다 ──
  await b.cmd('/soulstest souls 5000', 'SOULS ')
  await b.cmd('/soulstest rest', 'REST shown')
  await L.sleep(200)
  await b.cmd('/soulstest levelup open', 'LEVELUP open')
  from = b.sys.length
  await b.cmd('/soulstest hit 40 def', 'HIT ')
  const intr = await b.waitT('REST interrupted', 2000, from)
  const ui = await b.cmd('/soulstest ui', 'UI ')
  sc.check('a hit while resting closes the dialog (REST interrupted)', intr && ui.kv && ui.kv.open === 'null', (intr ? intr.line : '줄 없음') + ' | ' + (ui.line || ''))
  await b.cmd('/soulstest heal', 'HEAL')

  // ── 민첩·지력·지구력 ──
  const dex = await b.cmd('/soulstest stat dex 40', 'ATTR ')
  sc.checkCmd('dex 40 -> movement speed +10% (attribute modifier souls:lvl_dex)', dex, (r) => Math.abs(L.num(r.kv.move) - 0.10) < 1e-6)
  await b.cmd('/soulstest stat int 40', 'ATTR ')
  const po = await b.cmd('/soulstest effect poison 200', 'AILMENT ')
  sc.checkCmd('int 40 -> poison 200 ticks shortened by 24% (152)', po, (r) => r.kv.from === '200' && r.kv.to === '152')
  const bu = await b.cmd('/soulstest burn 60', 'AILMENT ')
  sc.checkCmd('int 40 -> burning shortened too', bu, (r) => r.kv.type === 'fire' && L.num(r.kv.to) < 60)
  await b.cmd('/soulstest heal', 'HEAL')
  const st0 = await b.cmd('/soulstest stamina', 'STAMINA')
  await b.cmd('/soulstest stat end 30', 'ATTR ')
  const st1 = await b.cmd('/soulstest stamina', 'STAMINA')
  sc.check('endurance 30 -> max stamina 150', st0.kv && st1.kv && L.num(st0.kv.max) === 100 && L.num(st1.kv.max) === 150, `${st0.kv && st0.kv.max} -> ${st1.kv && st1.kv.max}`)

  // ── 장비 무게 ──
  await b.cmd('/soulstest stat str 10', 'ATTR ')
  const l0 = await b.cmd('/soulstest load', 'LOAD ')
  sc.checkCmd('starting kit is light', l0, (r) => r.kv.tier === 'light' && r.kv.roll === 'light')
  await b.cmd('/soulstest give all', 'GIVE')
  await L.sleep(800)
  const l1 = await b.cmd('/soulstest load', 'LOAD ')
  sc.checkCmd('a hotbar full of weapons is heavy at strength 10 (39.0 / 40)', l1, (r) => r.kv.tier === 'heavy' && r.kv.roll === 'heavy')
  await b.cmd('/soulstest stat str 1', 'ATTR ')
  const l1b = await b.cmd('/soulstest load', 'LOAD ')
  sc.checkCmd('strength 1 (limit 30): over the limit (backstep, no sprint)', l1b, (r) => r.kv.tier === 'over' && r.kv.roll === 'backstep')
  await b.cmd('/souls tp lane', null, 1200)
  await L.sleep(500)
  await b.ground(3000)
  await b.cmd('/soulstest heal', 'HEAL')
  from = b.sys.length
  await b.rollKey({ forward: true })
  const rl = await b.waitT('ROLL ', 2000, from)
  sc.check('overloaded roll is a backstep', rl && rl.kv.kind === 'backstep', rl ? rl.line : '줄 없음')
  await L.sleep(800)
  await b.cmd('/clear ' + b.name, null, 1500)
  await b.cmd('/soulstest stat str 10', 'ATTR ')
  await L.sleep(600)
  const l2 = await b.cmd('/soulstest load', 'LOAD ')
  sc.checkCmd('emptied: light again', l2, (r) => r.kv.tier === 'light')
  sc.check('no kick during levelup scenario', !b.kick, b.kick || '')
})
