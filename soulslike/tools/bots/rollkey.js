// 구르기 키 (2.1, 2.3 의 11, 3.3, 사용자 결정 "구르기는 웅크리기 키로, F 가 아니라"). 서버의 config.yml controls.roll-key 를
// 바꾸고 /souls reload 로 다시 읽는다 (sneak → f → both → 처음 값). 기본 sneak 판의 짧게·길게·조합·창·기억은 roll_iframes 가 본다.
//   sneak  짧게 누르면 뗄 때 구른다 (방향키 → 그 쪽, 없으면 뒷걸음). F 는 구르지 않고 무기 기술 (ART). 누른 채 좌클릭 (물체를 쳐도),
//          누른 채 Q (버리기), 누른 채 창이 열림 (키가 모두 떼어짐) 은 구르지 않는다. 웅크리기 자세는 누른 동안만 (구른 뒤 남지 않는다).
//          지연: 누름 → 구르기는 뗄 때까지의 시간만큼 늦다 (ROLL_TAP held 틱, 봇 시각으로 F 판과 견준다).
//   f      F 가 구른다 (방향 그대로, 웅크린 채 F 는 무기 기술). 웅크리기 짧게는 구르지 않는다.
//   both   둘 다 구른다. 웅크린 채 F 는 무기 기술.
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

const CFG = L.ENV.serverDir && path.join(L.ENV.serverDir, 'plugins', 'Soulslike', 'config.yml')

async function setKey (sc, b, mode, original) {
  const text = original.replace(/^(controls:[\s\S]*?\n\s+roll-key:)[^\n]*/m, `$1 ${mode}`)
  fs.writeFileSync(CFG, text)
  const r = await b.cmd('/souls reload', (m) => L.translateKeys(m.raw).includes('souls.admin.reloaded'), 5000)
  sc.check(`roll-key: ${mode} (config.yml + /souls reload)`, !!r.msg && /roll-key: /.test(text), r.cmd)
  await L.sleep(300)
}

async function fresh (b) {
  await b.cmd('/soulstest heal', 'HEAL')
  await b.cmd('/souls tp lane', null, 1200)
  await L.sleep(500)
  await b.ground(3000)
  await L.sleep(200)
}

/** 키를 누르고 무엇이 났나: {roll, art, tap, skip} (from 뒤 줄). */
function seen (b, from) {
  return {
    roll: b.tLines('ROLL ', from)[0] || null,
    deny: b.tLines('ROLL_DENY', from)[0] || null,
    art: b.tLines('ART ', from)[0] || null,
    tap: b.tLines('ROLL_TAP ', from)[0] || null,
    skip: b.tLines('ROLL_TAP_SKIP', from)[0] || null
  }
}

async function tap (b, keys = {}, hold = 80) {
  b.input(keys)
  await L.sleep(150)
  const from = b.sys.length
  await b.tapSneak(keys, hold)
  await L.sleep(900)
  b.input({})
  await L.sleep(400)
  return seen(b, from)
}

async function fkey (b, keys = {}, sneak = false) {
  b.input(Object.assign({}, keys, sneak ? { shift: true } : {}))
  await L.sleep(sneak ? 300 : 150)
  const from = b.sys.length
  b.swap()
  await L.sleep(900)
  b.input({})
  await L.sleep(400)
  return seen(b, from)
}

const isCrouch = (v) => v === 5 || /crouch/i.test(String(v))

L.run('rollkey', async (sc) => {
  if (!sc.check('server config.yml reachable (SERVER_DIR)', CFG && fs.existsSync(CFG), CFG || 'SERVER_DIR 없음')) return
  const original = fs.readFileSync(CFG, 'utf8')
  const b = await L.connect(sc)
  try {
    await L.sleep(1500)
    await body(sc, b, original)
  } finally {
    fs.writeFileSync(CFG, original)
    if (!b.ended) await b.cmd('/souls reload', (m) => L.translateKeys(m.raw).includes('souls.admin.reloaded'), 5000)
  }
})

async function body (sc, b, original) {
  // ── sneak ──
  await setKey(sc, b, 'sneak', original)
  await fresh(b)
  let r = await tap(b, { forward: true })
  sc.check('sneak: tap + W rolls forward on release', r.roll && r.roll.kv.dir === 'fwd' && r.tap, r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  r = await tap(b, { left: true })
  sc.check('sneak: tap + A rolls left', r.roll && r.roll.kv.dir === 'left', r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  r = await tap(b, { backward: true })
  sc.check('sneak: tap + S rolls backward (a roll, not the backstep)', r.roll && r.roll.kv.dir === 'bwd' && r.roll.kv.kind !== 'backstep', r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  const p0 = b.p.poses.length
  const fl0 = b.p.flags.length
  r = await tap(b, {})
  sc.check('sneak: tap with no direction = backstep', r.roll && r.roll.kv.kind === 'backstep' && r.roll.kv.dir === 'back', r.roll ? r.roll.line : JSON.stringify(r))
  // 웅크리기 자세: 누른 동안 (짧게) 만, 구른 뒤에는 서 있다
  const poses = b.p.poses.slice(p0)
  const crouch = poses.findIndex((x) => isCrouch(x.value))
  const after = crouch >= 0 ? poses.slice(crouch + 1).find((x) => !isCrouch(x.value)) : null
  const lastPose = poses.length ? poses[poses.length - 1].value : null
  const lastFlag = b.p.flags.length > fl0 ? b.p.flags[b.p.flags.length - 1].value : 0
  sc.check('sneak tap: crouch pose only while held (cleared within ~2 ticks of release), standing after the roll, sneak flag off',
    (crouch < 0 || (after && after.t - poses[crouch].t <= 80 + 150)) && !isCrouch(lastPose) && !(lastFlag & 0x02),
    poses.map((x) => `${x.value}@${x.t - (poses[0] ? poses[0].t : 0)}`).join(' ') + ` flag=0x${lastFlag.toString(16)}`)
  await fresh(b)
  r = await fkey(b, { forward: true })
  sc.check('sneak: F alone does not roll (weapon art, ART line)', !r.roll && r.art && r.art.kv.sneak === 'false', r.art ? r.art.line : JSON.stringify(r))
  // 누른 채 좌클릭으로 물체를 친다 (강공격 자리): 구르지 않는다
  await fresh(b)
  await b.cmd('/summon minecraft:armor_stand ~2 ~ ~ {Tags:["souls_ent"],NoGravity:1b}', null, 800)
  await L.sleep(600)
  const stand = Object.values(b.bot.entities).find((e) => e.name === 'armor_stand' && e.position.distanceTo(b.bot.entity.position) < 4)
  let from = b.sys.length
  b.input({ shift: true })
  await L.sleep(60)
  if (stand) {
    await b.bot.lookAt(stand.position.offset(0, 1, 0), true)
    b.bot.attack(stand)
  }
  await L.sleep(60)
  b.input({})
  await L.sleep(600)
  r = seen(b, from)
  sc.check('sneak held + left click on an entity (heavy attack) does not roll (why=attack)', stand && !r.roll && r.skip && r.skip.kv.why === 'attack',
    (stand ? '' : '갑옷 거치대 없음 ') + (r.skip ? r.skip.line : JSON.stringify(r)))
  await b.cmd('/kill @e[type=minecraft:armor_stand,tag=souls_ent]', null, 800)
  // 누른 채 Q (다음 표적 자리): 구르지 않는다
  await fresh(b)
  from = b.sys.length
  b.input({ shift: true })
  await L.sleep(40)
  b.bot._client.write('block_dig', { status: 4, location: { x: 0, y: 0, z: 0 }, face: 0, sequence: 0 })
  await L.sleep(60)
  b.input({})
  await L.sleep(600)
  r = seen(b, from)
  sc.check('sneak held + Q does not roll (why=drop)', !r.roll && r.skip && r.skip.kv.why === 'drop', r.skip ? r.skip.line : JSON.stringify(r))
  // 누른 채 창이 열림 (클라이언트가 키를 모두 뗀다: 방향키와 웅크리기가 같이 떨어진다)
  await fresh(b)
  b.input({ forward: true })
  await L.sleep(150)
  from = b.sys.length
  b.input({ forward: true, shift: true })
  await L.sleep(60)
  b.input({})
  await L.sleep(600)
  r = seen(b, from)
  sc.check('sneak tap released by a screen opening (all keys dropped) does not roll (why=screen)', !r.roll && r.skip && r.skip.kv.why === 'screen', r.skip ? r.skip.line : JSON.stringify(r))
  // 쥔 곤봉이 버려졌으면 되돌린다
  await b.cmd('/clear @s', null, 1000)
  await b.cmd('/soulstest give gaoler_club main', 'GIVE')
  await b.cmd('/soulstest give plank_shield off', 'GIVE')
  await b.cmd('/kill @e[type=minecraft:item,distance=..8]', null, 800)

  // 지연: 누름 → ROLL (봇 시각). 짧게 누르기는 뗄 때 구르므로 누른 시간만큼 늦다
  const lat = { tap: [], held: [] }
  for (let i = 0; i < 3; i++) {
    await fresh(b)
    b.input({ forward: true })
    await L.sleep(150)
    from = b.sys.length
    const t0 = Date.now()
    await b.tapSneak({ forward: true }, 80)
    const rl = await b.waitT('ROLL ', 2000, from)
    const tp = b.tLines('ROLL_TAP ', from)[0]
    if (rl) lat.tap.push(rl.t - t0)
    if (tp) lat.held.push(L.num(tp.kv.held))
    await L.sleep(900)
    b.input({})
  }

  // ── f ──
  await setKey(sc, b, 'f', original)
  await fresh(b)
  r = await fkey(b, { forward: true })
  sc.check('f: F rolls forward', r.roll && r.roll.kv.dir === 'fwd' && !r.art, r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  r = await fkey(b, {})
  sc.check('f: F with no direction = backstep', r.roll && r.roll.kv.kind === 'backstep', r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  r = await tap(b, { forward: true })
  sc.check('f: a sneak tap does not roll (no ROLL_TAP judged)', !r.roll && !r.tap, JSON.stringify(r))
  await fresh(b)
  r = await fkey(b, { forward: true }, true)
  sc.check('f: sneak held + F is the weapon art', !r.roll && r.art && r.art.kv.sneak === 'true', r.art ? r.art.line : JSON.stringify(r))
  const latF = []
  for (let i = 0; i < 3; i++) {
    await fresh(b)
    b.input({ forward: true })
    await L.sleep(150)
    from = b.sys.length
    const t0 = Date.now()
    b.swap()
    const rl = await b.waitT('ROLL ', 2000, from)
    if (rl) latF.push(rl.t - t0)
    await L.sleep(900)
    b.input({})
  }
  const med = (a) => a.slice().sort((x, y) => x - y)[a.length >> 1]
  sc.note(`누름 → ROLL (봇 시각, ms): 웅크리기 짧게 (80ms 누름) ${lat.tap.join(',')} (누른 틱 ${lat.held.join(',')}), F ${latF.join(',')}`)
  console.log(`ROLLKEY_LATENCY tap_ms=${lat.tap.join(',')} tap_held_ticks=${lat.held.join(',')} f_ms=${latF.join(',')} added_ms=${lat.tap.length && latF.length ? med(lat.tap) - med(latF) : 'NaN'}`)
  sc.check('latency: a tap rolls on release, so it adds the hold time (~80 ms, at most the 5-tick window) over F',
    lat.tap.length === 3 && latF.length === 3 && med(lat.tap) - med(latF) >= 30 && med(lat.tap) - med(latF) <= 250 + 60 && lat.held.every((h) => h >= 1 && h <= 5),
    `웅크리기 ${med(lat.tap)} ms, F ${med(latF)} ms, 차이 ${med(lat.tap) - med(latF)} ms, 누른 틱 ${lat.held.join(',')}`)

  // ── both ──
  await setKey(sc, b, 'both', original)
  await fresh(b)
  r = await fkey(b, { right: true })
  sc.check('both: F rolls (right)', r.roll && r.roll.kv.dir === 'right', r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  r = await tap(b, { forward: true })
  sc.check('both: a sneak tap rolls too', r.roll && r.roll.kv.dir === 'fwd' && r.tap, r.roll ? r.roll.line : JSON.stringify(r))
  await fresh(b)
  r = await fkey(b, {}, true)
  sc.check('both: sneak held + F is the weapon art, no roll', !r.roll && r.art && r.art.kv.sneak === 'true', r.art ? r.art.line : JSON.stringify(r))
  // 확인 창의 조작 안내도 키를 따른다 (both·sneak 은 웅크리기 키, f 는 F)
  await setKey(sc, b, 'f', original)
  let d = b.p.dialogs.length
  await b.cmd('/soulstest origin show', null, 800)
  const og = await b.waitDialog(d, 3000)
  d = b.p.dialogs.length
  if (og) b.clickDialog('deprived', {}, og)
  const conf = await b.waitDialog(d, 3000)
  sc.check('f: the origin confirm dialog shows the F roll hint (controls.hint.roll-f, key.swapOffhand)', conf && L.deepKeys(conf).includes('souls.controls.hint.roll-f') &&
    JSON.stringify(conf).includes('key.swapOffhand'), conf ? L.deepKeys(conf).filter((k) => k.includes('controls')).join(',') : '창 없음')
  if (conf) b.clickDialog('back', {}, conf)
  await L.sleep(300)
  await b.cmd('/soulstest ui', 'UI ')
  await b.cmd('/soulstest press origin exit', null, 800)

  // ── 처음 값으로 ──
  fs.writeFileSync(CFG, original)
  await b.cmd('/souls reload', (m) => L.translateKeys(m.raw).includes('souls.admin.reloaded'), 5000)
  await L.sleep(300)
  await fresh(b)
  r = await tap(b, { forward: true })
  const want = (original.match(/^\s+roll-key:\s*(\S+)/m) || [])[1] || 'sneak'
  sc.check(`restored roll-key ${want}: ${want === 'f' ? 'tap does not roll' : 'tap rolls again'}`, want === 'f' ? !r.roll : !!r.roll, r.roll ? r.roll.line : JSON.stringify(r))
  sc.check('no kick during roll-key scenario', !b.kick, b.kick || '')
}
