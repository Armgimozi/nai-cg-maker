// 출신 (5.1, 5.10) 과 만능 열쇠 (9.5). 시험 봇은 접속할 때 빈털터리로 태어난다 (start.auto-origin). 이 시나리오는
// 관리자 명령으로 출신을 지운 뒤 진짜 창 차례를 밟는다 (custom_click_action).
//   1. /souls origin reset → 출신 창 (단추 여섯 + 나중에), 단추 글은 팩이 맞춘 칸 열쇠 (origin.*.name.cell …).
//   2. 출신이 없는 동안: 짧은 누름은 구르지 않고 (why=unborn), 원인 있는 피해를 받지 않는다 (UNBORN_SAFE).
//   3. 도적 → 확인 창 (이 출신으로 / 돌아간다) → 돌아간다 → 다시 도적 → 이 출신으로: 능력치 10·10·12·9·16·10 (레벨 8),
//      시작 아이템 (단도 주손, 결투 단검 왼손, 만능 열쇠 가방), 아직 없는 체계 (방어구·에스트) 는 기다린다 (pending).
//   4. 다시 고르기는 거절 (ORIGIN_DENY why=chosen). 다시 들어와도 시작 아이템이 겹치지 않는다 (장부).
//   5. 만능 열쇠: 열쇠 문 (탑옥 위층 독방, 병영 지하 감옥) 은 열고, 이야기로 막힌 문 (서쪽 탑) 은 열지 않는다.
//   6. 화톳불 휴식 창의 "출신 다시 고르기" (레벨을 올리기 전 한 번): 아이템을 거두고 창을 다시 띄운다 → 빈털터리로.
'use strict'
const L = require('./lib')

function countItem (b, id) {
  // souls 아이템은 바닐라 껍데기라 이름표 (item_name 번역 열쇠) 로 센다
  let n = 0
  for (const it of b.bot.inventory.slots) {
    if (!it || !Array.isArray(it.components)) continue
    const nm = it.components.find((c) => c.type === 'item_name')
    if (nm && JSON.stringify(nm.data).includes(id)) n += it.count
  }
  return n
}

L.run('origin', async (sc) => {
  let b = await L.connect(sc)
  await L.sleep(1500)
  const st0 = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('test bot is born at join (start.auto-origin deprived)', st0.kv && st0.kv.origin === 'deprived' && st0.kv.level === '1', st0.line || '')

  // ── 지우기 → 창 ──
  let d0 = b.p.dialogs.length
  const rs = await b.cmd('/souls origin reset ' + b.name, 'ORIGIN_RESET', 4000)
  sc.checkCmd('admin reset clears the origin (ORIGIN_RESET)', rs, (r) => L.num(r.kv.items) >= 2)
  let raw = await b.waitDialog(d0, 3000)
  if (!sc.check('origin dialog opens after reset', raw && b.dialogId(raw) === 'origin', raw ? b.dialogId(raw) : '창 없음')) return
  const ids = Object.keys(b.dialogButtons(raw)).filter((k) => k !== 'exit')
  sc.check('six origins in order + later (exit action)', JSON.stringify(ids) === JSON.stringify(['knight', 'warrior', 'thief', 'archer', 'sorcerer', 'deprived']) &&
    !!b.dialogButtons(raw).exit, ids.join(','))
  const keys = L.deepKeys(raw)
  sc.check('rows use pack-padded cells (origin.*.name.cell, origin.*.kit.cell, stat.*.short.rcell)',
    ['souls.origin.thief.name.cell', 'souls.origin.thief.kit.cell', 'souls.stat.dex.short.rcell', 'souls.origin.head-name.cell'].every((k) => keys.includes(k)),
    keys.filter((k) => /cell$/.test(k)).slice(0, 8).join(','))
  sc.check('origin descriptions are button tooltips (origin.*.desc)', keys.includes('souls.origin.thief.desc') && keys.includes('souls.origin.knight.desc'))
  const inv0 = b.bot.inventory.slots.filter(Boolean).length
  sc.check('reset took the starting items back', inv0 === 0, `칸 ${inv0}`)

  // ── 출신이 없는 동안 ──
  let from = b.sys.length
  await b.tapSneak({})
  const sk = await b.waitT('ROLL_TAP_SKIP', 1500, from)
  sc.check('unborn: sneak tap does not roll', sk && /unborn|dialog/.test(sk.kv.why) && !b.tLines('ROLL ', from).length, sk ? sk.line : '줄 없음')
  from = b.sys.length
  const hit = await b.cmd('/soulstest hit 40', 'HIT ')
  sc.check('unborn: caused damage does not land (UNBORN_SAFE)', hit.kv && L.num(hit.kv.dealt) === 0 && b.tLines('UNBORN_SAFE', from).length > 0, hit.line || '')

  // ── "나중에 고른다" 를 진짜 단추로 (검토 origin-later-dead-dialog): 클라이언트는 단추의 afterAction (NONE) 을 따라 창을 두므로 서버가 닫는다.
  //    그리고 다시 여는 길 ("고르려면 · 웅크리기 키 짧게", 키 묶음 글) 을 부제목과 채팅으로 알린다 (검토 origin-none-no-way-back) ──
  from = b.sys.length
  const cl0 = b.p.dialogClears.length
  const sub0 = b.p.subtitles.length
  b.clickDialog('exit', {}, raw)
  const lt = await b.waitT('ORIGIN_LATER', 2000, from)
  await L.sleep(400)
  sc.check('"decide later" by mouse: server closes the dialog (clear_dialog)', lt && b.p.dialogClears.length > cl0, (lt ? lt.line : '줄 없음') + ` clears ${b.p.dialogClears.length - cl0}`)
  const hint = b.sys.slice(from).find((m) => L.translateKeys(m.raw).includes('souls.origin.none-hint'))
  sc.check('"decide later": chat tells how to reopen (origin.none-hint with the key.sneak keybind)', hint && JSON.stringify(hint.raw).includes('key.sneak'),
    hint ? JSON.stringify(hint.raw).slice(0, 160) : b.sys.slice(from).map((m) => L.translateKeys(m.raw).join('+')).join(' | '))
  const subs = b.p.subtitles.slice(sub0).map((m) => L.translateKeys(m.raw).join('+')).join(' | ')
  sc.check('"decide later": subtitle "not yet chosen" (origin.none)', /souls\.origin\.none/.test(subs), subs || '부제목 없음')
  // ── 둘레 밖에서도 굳지 않는다 (검토 unborn-freeze-outside-radius): 시작 자리 (지운 자리) 에서 10칸 넘는 구르기 길로 옮긴 뒤,
  //    시작 자리 쪽으로는 걷고, 바깥쪽 걸음은 되돌린다 ──
  const home = b.bot.entity.position.clone()
  await b.cmd('/souls tp lane', null, 1500)
  await L.sleep(600)
  await b.ground(3000)
  const p1 = b.bot.entity.position.clone()
  const dist1 = Math.hypot(p1.x - home.x, p1.z - home.z)
  await b.bot.lookAt(home.offset(0, 1.6, 0), true)
  from = b.sys.length
  b.bot.setControlState('forward', true)
  await L.sleep(700)
  b.bot.setControlState('forward', false)
  await L.sleep(500)
  const p2 = b.bot.entity.position.clone()
  const dist2 = Math.hypot(p2.x - home.x, p2.z - home.z)
  sc.check(`unborn outside the radius (${dist1.toFixed(1)} blocks): walking toward the start is allowed`, dist1 > 8 && dist2 < dist1 - 0.8 && !b.tLines('ORIGIN_REOPEN', from).some((x) => x.kv.why === 'walk'),
    `${dist1.toFixed(2)} -> ${dist2.toFixed(2)} ` + b.tLines('ORIGIN_REOPEN', from).map((x) => x.line).join(' | '))
  await b.bot.lookAt(p2.offset(2 * (p2.x - home.x), 1.6, 2 * (p2.z - home.z)), true)
  from = b.sys.length
  b.bot.setControlState('forward', true)
  await L.sleep(700)
  b.bot.setControlState('forward', false)
  await L.sleep(800)
  const p3 = b.bot.entity.position.clone()
  const dist3 = Math.hypot(p3.x - home.x, p3.z - home.z)
  // 둘레 (8칸) 안이면 바깥으로도 걷는다: 둘레를 넘는 블록 걸음에서 되돌린다 (같은 블록 안의 걸음은 보지 않아 한 칸쯤 넘을 수 있다)
  sc.check('unborn: walking further away stops at the radius (ORIGIN_REOPEN why=walk)', dist3 < 8 + 1.5 && b.tLines('ORIGIN_REOPEN', from).some((x) => x.kv.why === 'walk'),
    `${dist2.toFixed(2)} -> ${dist3.toFixed(2)} ` + b.tLines('ORIGIN_REOPEN', from).map((x) => x.line).join(' | '))
  await b.cmd('/souls tp room', null, 1500)
  await L.sleep(600)
  d0 = b.p.dialogs.length
  await b.cmd('/soulstest origin show', null, 800)
  raw = await b.waitDialog(d0, 3000)
  if (!sc.check('origin dialog shown again', raw && b.dialogId(raw) === 'origin', raw ? b.dialogId(raw) : '창 없음')) return

  // ── 도적 → 돌아간다 → 도적 → 이 출신으로 ──
  d0 = b.p.dialogs.length
  b.clickDialog('thief', {}, raw)
  let conf = await b.waitDialog(d0, 3000)
  sc.check('confirm dialog for thief (choose / back)', conf && b.dialogId(conf) === 'origin_confirm' && b.dialogButtons(conf).choose && b.dialogButtons(conf).back,
    conf ? b.dialogId(conf) + ' ' + Object.keys(b.dialogButtons(conf)).join(',') : '창 없음')
  if (conf) {
    const ck = L.deepKeys(conf)
    sc.check('confirm shows style, stats table and the roll key as a keybind (key.sneak)', ck.includes('souls.origin.thief.style') &&
      ck.includes('souls.stat.dex.name.cell') && ck.includes('souls.derived.max-hp.cell') &&
      ck.includes('souls.controls.hint.roll') && JSON.stringify(conf).includes('key.sneak'), ck.filter((k) => k.startsWith('souls.')).join(','))
  }
  d0 = b.p.dialogs.length
  b.clickDialog('back', {}, conf)
  raw = await b.waitDialog(d0, 3000)
  sc.check('"back" returns to the origin list', raw && b.dialogId(raw) === 'origin', raw ? b.dialogId(raw) : '창 없음')
  d0 = b.p.dialogs.length
  b.clickDialog('thief', {}, raw)
  conf = await b.waitDialog(d0, 3000)
  from = b.sys.length
  b.clickDialog('choose', {}, conf)
  const og = await b.waitT('ORIGIN ', 3000, from)
  sc.check('thief chosen via dialog (level 8)', og && og.kv.id === 'thief' && og.kv.level === '8' && og.kv.via === 'dialog', og ? og.line : '줄 없음')
  if (og) {
    sc.check('thief kit: dagger, parrying dagger, master key', og.kv.kit === 'weapon:alley_dagger,weapon:parrying_dagger,item:master_key', og.kv.kit)
    sc.check('not-yet systems wait in the ledger (armor, estus)', /armor:prisoner_rags/.test(og.kv.pending) && /item:estus/.test(og.kv.pending), og.kv.pending)
  }
  await L.sleep(500)
  const st = await b.cmd('/soulstest stats', 'STATS ')
  sc.checkCmd('thief stats 10/10/12/9/16/10, weapon in main hand', st, (r) => r.kv.vig === '10' && r.kv.mnd === '10' && r.kv.end === '12' && r.kv.str === '9' &&
    r.kv.dex === '16' && r.kv.int === '10' && r.kv.weapon === 'alley_dagger' && r.kv.level === '8')
  const held = b.bot.heldItem
  const off = b.bot.inventory.slots[45]
  sc.check('dagger in hotbar 1, parrying dagger in the off hand', held && JSON.stringify(held.components || []).includes('alley_dagger') &&
    off && JSON.stringify(off.components || []).includes('parrying_dagger'), (held ? held.name : '-') + ' / ' + (off ? off.name : '-'))
  const keySlot = b.bot.inventory.slots.findIndex((it) => it && JSON.stringify(it.components || []).includes('master_key'))
  sc.check('master key goes to the backpack (slot 9..35) with its own model', keySlot >= 9 && keySlot <= 35 &&
    JSON.stringify(b.bot.inventory.slots[keySlot].components).includes('souls:master_key'), 'slot ' + keySlot)
  const info = await b.cmd('/soulstest info', 'INFO ')
  sc.check('max HP from vigor 10 = 400, hearts stay 10 (scale 20)', info.kv && info.kv.maxhp === '400' && info.kv.scale === '20', info.line || '')

  // ── 다시는 못 고른다, 다시 들어와도 겹치지 않는다 ──
  const deny = await b.cmd('/soulstest origin knight', 'ORIGIN_DENY')
  sc.checkCmd('second choice is refused (ORIGIN_DENY why=chosen)', deny, (r) => r.kv.why === 'chosen')
  const keys0 = countItem(b, 'master_key')
  await b.quit()
  await L.sleep(1500)
  b = await L.connect(sc)
  await L.sleep(2500)
  sc.check('rejoin: no second kit (ledger)', countItem(b, 'master_key') === keys0 && keys0 === 1 && countItem(b, 'alley_dagger') === 1 && !b.tLines('KIT_LATE').length,
    `열쇠 ${countItem(b, 'master_key')}, 단도 ${countItem(b, 'alley_dagger')}`)
  const st2 = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('rejoin: origin and stats kept', st2.kv && st2.kv.origin === 'thief' && st2.kv.dex === '16', st2.line || '')
  const info2 = await b.cmd('/soulstest info', 'INFO ')
  sc.check('rejoin: max HP kept (saved modifier) and health full', info2.kv && info2.kv.maxhp === '400' && L.num(info2.kv.hp) >= 399, info2.line || '')

  // ── 만능 열쇠 ──
  for (const [lock, want] of [['gaol.upper_cell', true], ['barracks.cells', true], ['redin.west_tower', false], ['shrine.seal_left', false]]) {
    const r = await b.cmd('/soulstest opens ' + lock, 'OPENS ')
    sc.checkCmd(`master key ${want ? 'opens' : 'does not open'} ${lock}`, r, (x) => x.kv.result === String(want) && x.kv.master === 'true')
  }

  // ── 출신 다시 고르기 (휴식 창) ──
  let d1 = b.p.dialogs.length
  await b.cmd('/soulstest rest', 'REST shown')
  const rest = await b.waitDialog(d1, 3000)
  sc.check('rest menu offers "repick" before any level is bought', rest && !!b.dialogButtons(rest).repick, rest ? Object.keys(b.dialogButtons(rest)).join(',') : '창 없음')
  d1 = b.p.dialogs.length
  from = b.sys.length
  b.clickDialog('repick', {}, rest)
  const rp = await b.waitT('REPICK ', 3000, from)
  sc.check('repick takes the kit back (REPICK items=3)', rp && rp.kv.from === 'thief' && rp.kv.items === '3', rp ? rp.line : '줄 없음')
  raw = await b.waitDialog(d1, 3000)
  d1 = b.p.dialogs.length
  b.clickDialog('deprived', {}, raw)
  conf = await b.waitDialog(d1, 3000)
  from = b.sys.length
  b.clickDialog('choose', {}, conf)
  const og2 = await b.waitT('ORIGIN ', 3000, from)
  sc.check('repicked: deprived (level 1, club and plank shield)', og2 && og2.kv.id === 'deprived' && og2.kv.level === '1' && og2.kv.kit === 'weapon:gaoler_club,weapon:plank_shield', og2 ? og2.line : '줄 없음')
  await L.sleep(400)
  sc.check('repick: no master key left', countItem(b, 'master_key') === 0, '열쇠 ' + countItem(b, 'master_key'))
  // 다시 고르기는 한 번뿐 (검토 repick-not-once): 레벨은 그대로 출신의 레벨이지만 휴식 창에 다시 나오지 않고, 명령도 거절
  d1 = b.p.dialogs.length
  await b.cmd('/soulstest rest', 'REST shown')
  const rest2 = await b.waitDialog(d1, 3000)
  sc.check('after one repick the rest menu no longer offers "repick"', rest2 && !b.dialogButtons(rest2).repick && !!b.dialogButtons(rest2).levelup,
    rest2 ? Object.keys(b.dialogButtons(rest2)).join(',') : '창 없음')
  await b.cmd('/soulstest press rest exit', null, 600)
  const op = await b.cmd('/soulstest opens gaol.upper_cell', 'OPENS ')
  sc.checkCmd('without the key the cell stays locked', op, (x) => x.kv.result === 'false')
  sc.check('no kick during origin scenario', !b.kick, b.kick || '')
})
