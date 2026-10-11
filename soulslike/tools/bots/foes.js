// M1 P1b 적·허수아비·도장 (M1_PLAN 1절의 P1b, 3절의 도장). /soulstest dummy … · dojo …, 서버 기록의 FOE spawn|die|gone 줄.
//   들어오면 허수아비 셋이 이미 서 있다 (시험 방은 도장에서 dojo.near 32칸 안): toward (남쪽을 본다), away (북쪽), lane (달리기 길 끝)
//   시험 방 북쪽 문 → 복도 → 홀을 걸어서 지난다 (문 3칸·높이 3칸이 비었고 바닥이 이어진다)
//   허수아비는 enemies.yml dummy: 가상 체력 1000 (보통 난이도 × 1.0), 방어 20. 바닥 몸 (좀비) 의 바닐라 체력·피해는 그대로 (모든 바닐라
//     피해 취소, /damage 해도 깎이지 않는다), 난이도 체력 수정자 없음 (FoeScaling 이 souls_foe 를 건너뛴다)
//   한 대 (/soulstest dummy hit): 100 → 83.33 깎이고, 3초 (regen-after 60) 지나면 다 찬다. 쓰러지면 FOE die why=hit, 3초 (respawn 60)
//     뒤 도장이 다시 세운다. /kill 도 그대로 죽이고 (FOE die why=kill) 다시 선다
//   밀리면 제자리로 (check-every 10), 공허에 떨어지면 처음 선 자리로 (VOID 를 막고 돌려보낸다)
//   dummy clear 는 모두 지우고, 기다리면 셋이 다시 선다
//   300칸 떨어져 청크가 내려가면 FOE gone why=unload 셋, 등록부가 비고, 돌아오면 곧바로 다시 선다 (R7)
//   50번 세워도 아기·장비·떨굼이 없고 조용하고 AI 가 꺼져 있다 (R8)
'use strict'
const L = require('./lib')

/** "toward:alive:1000.0:123:0.00:0,..." → {toward: {state, hp, eid, drift, yaw}} */
function slots (r) {
  const out = {}
  if (!r || !r.kv || !r.kv.slots) return out
  for (const part of r.kv.slots.split(',')) {
    const [name, state, hp, eid, drift, yaw] = part.split(':')
    out[name] = { state, hp: L.num(hp), eid: +eid, drift: L.num(drift), yaw: L.num(yaw) }
  }
  return out
}

L.run('foes', async (sc) => {
  const b = await L.connect(sc)
  const dojo = () => b.cmd('/soulstest dojo dump', 'DOJO v=')
  /** dojo dump 을 pred 가 맞을 때까지 (ms 안) 다시 본다. 마지막 답을 돌려준다 */
  async function waitDojo (pred, ms) {
    const end = Date.now() + ms
    let r
    for (;;) {
      r = await dojo()
      let ok = false
      try { ok = r && r.kv && pred(r, slots(r)) } catch (e) { ok = false }
      if (ok || Date.now() > end) return r
      await L.sleep(300)
    }
  }
  const dump = () => b.cmd('/soulstest dummy dump', 'DUMMY dump')
  const yawOk = (y, want) => Math.abs(((y - want) % 360 + 540) % 360 - 180) < 3

  await L.sleep(1500)
  // ── 들어오면 셋이 서 있다 ──
  let r = await waitDojo((x) => x.kv.alive === '3', 6000)
  sc.checkCmd('dojo built and three dummies stand at join (test room is within dojo.near)', r,
    (x) => x.kv.v === '1' && x.kv.built === 'true' && x.kv.near === 'true' && x.kv.alive === '3', r.line)
  let s = slots(r)
  sc.check('dummies face their spots: toward south (yaw 0), away north (180), lane south (0)',
    s.toward && yawOk(s.toward.yaw, 0) && s.away && yawOk(s.away.yaw, 180) && s.lane && yawOk(s.lane.yaw, 0), r.line)
  sc.check('dummies stand on their anchors (drift < 0.2)', Object.values(s).length === 3 && Object.values(s).every((x) => x.drift < 0.2), r.line)
  const center = (r.kv.center || '200,100,-244').split(',').map(Number)
  if (L.ENV.serverLog) {
    const sp = L.serverTAny('FOE spawn id=dummy why=dojo_')
    sc.check('server log: FOE spawn id=dummy why=dojo_toward|away|lane with hp 1000 def 20 zombie', ['toward', 'away', 'lane'].every((n) =>
      sp.some((x) => x.kv.why === 'dojo_' + n && L.num(x.kv.hp) === 1000 && L.num(x.kv.def) === 20 && x.kv.type === 'zombie')),
    sp.slice(0, 3).map((x) => x.line).join(' | ') || '줄 없음')
  }

  // ── 시험 방 북쪽 문 → 복도 → 홀 ──
  r = await b.cmd('/soulstest dojo tp entry', 'DOJO tp')
  sc.checkCmd('dojo tp entry', r, (x) => x.kv.at === 'entry', r.line)
  await L.sleep(1500)
  const { Vec3 } = require('vec3')
  const room = L.testRoom()
  const doorZ = room.z - 13
  const block = (x, y, z) => b.bot.blockAt(new Vec3(x, y, z))
  const name = (x, y, z) => { const k = block(x, y, z); return k ? k.name : '?' }
  const door = []
  for (let x = room.x - 1; x <= room.x + 1; x++) for (let y = room.y + 1; y <= room.y + 3; y++) door.push(name(x, y, doorZ))
  sc.check('north doorway: 3 wide, 3 high, open (air)', door.every((n) => n === 'air'), door.join(','))
  sc.check('doorway jambs stand (polished deepslate at x = ±2)', name(room.x - 2, room.y + 2, doorZ) === 'polished_deepslate' &&
    name(room.x + 2, room.y + 2, doorZ) === 'polished_deepslate', name(room.x - 2, room.y + 2, doorZ) + ',' + name(room.x + 2, room.y + 2, doorZ))
  // 문에서 홀 안쪽까지 가운데 줄: 발밑이 막혔고 머리 높이 둘이 비었다
  const hallIn = center[2] + 12
  const path = []
  for (let z = doorZ + 2; z >= hallIn; z--) {
    const f = name(room.x, room.y, z)
    const a = name(room.x, room.y + 1, z)
    const c = name(room.x, room.y + 2, z)
    if (f === 'air' || f === '?' || a !== 'air' || c !== 'air') path.push(`z${z}:${f}/${a}/${c}`)
  }
  sc.check('walkable centre line from the doorway through the corridor into the hall (floor, 2 clear above)', path.length === 0,
    path.slice(0, 6).join(' ') || `z ${doorZ + 2}..${hallIn}`)
  // 걸어서 들어간다 (mineflayer 시선 0 = 북쪽)
  await b.bot.look(0, 0, true)
  b.bot.setControlState('forward', true)
  const t0 = Date.now()
  while (Date.now() - t0 < 16000 && b.bot.entity.position.z > hallIn) await L.sleep(100)
  b.bot.clearControlStates()
  await L.sleep(500)
  r = await b.cmd('/soulstest pos', 'POS')
  sc.checkCmd('walked from the test room through the north doorway into the dojo hall', r, (x) =>
    L.num(x.kv.z) <= hallIn + 0.5 && Math.abs(L.num(x.kv.x) - (room.x + 0.5)) < 1.2 && x.kv.ground === 'true', `${r.line} (${((Date.now() - t0) / 1000).toFixed(1)}s)`)

  // ── 허수아비의 몸 ──
  await b.cmd('/soulstest dojo tp hall', 'DOJO tp')
  await L.sleep(800)
  r = await dump()
  sc.checkCmd('three dummies registered, full (1000), vanilla body health untouched, no difficulty modifier', r, (x) =>
    x.kv.n === '3' && x.kv.hp.split(',').every((v) => L.num(v) === 1000) && x.kv.max.split(',').every((v) => L.num(v) === 1000) &&
    x.kv.vhp.split(',').every((v) => L.num(v) === 20) && x.kv.mod === '0', r.line)
  // 바닐라 피해는 모두 취소 (가상 체력만 깎인다)
  await b.cmd('/damage @e[type=zombie,tag=souls_foe,limit=1,sort=nearest] 8 minecraft:player_attack', null, 1000)
  await b.cmd('/damage @e[type=zombie,tag=souls_foe,limit=1,sort=nearest] 8 minecraft:on_fire', null, 1000)
  r = await dump()
  sc.checkCmd('vanilla damage (/damage player_attack, on_fire) changes neither vanilla nor virtual health', r, (x) =>
    x.kv.n === '3' && x.kv.vhp.split(',').every((v) => L.num(v) === 20) && x.kv.hp.split(',').every((v) => L.num(v) === 1000), r.line)

  // ── 한 대와 차오르기 ──
  // 손맛은 모두 서버가 낸다 (S12): 아파하는 몸짓, 재질 소리 (허수아비는 짚: 나무 거치대 소리), 핏방울 (DUST)
  const feel = { hurt: [], sound: 0, dust: 0 }
  b.bot._client.on('hurt_animation', (d) => feel.hurt.push(d.entityId))
  b.bot._client.on('sound_effect', () => { feel.sound++ })
  b.bot._client.on('world_particles', () => { feel.dust++ })
  r = await b.cmd('/soulstest dummy hit 100', 'DUMMY hit')
  const want = 1000 - 100 * 100 / 120
  sc.checkCmd('a 100 hit deals raw²/(raw+def) = 83.33 to the nearest dummy', r, (x) =>
    x.kv.n === '1' && Math.abs(L.num(x.kv.hp) - want) < 0.01 && x.kv.killed === 'false', r.line)
  const hitEid = r.kv ? r.kv.eid : '-'
  await L.sleep(400)
  sc.check('hit feel from the server: hurt animation on the dummy, a sound and dust particles', feel.hurt.includes(+hitEid) && feel.sound > 0 &&
    feel.dust > 0, `hurt=${feel.hurt.join(',')} sound=${feel.sound} particles=${feel.dust}`)
  await L.sleep(1500)
  r = await dump()
  const hpOf = (x, eid) => { const i = x.kv.eids.split(',').indexOf(String(eid)); return i < 0 ? NaN : L.num(x.kv.hp.split(',')[i]) }
  sc.checkCmd('still hurt 1.5 s after the hit (regen-after 60 ticks)', r, (x) => Math.abs(hpOf(x, hitEid) - want) < 0.06, r.line)
  await L.sleep(2200)
  r = await dump()
  sc.checkCmd('full again 3.7 s after the hit', r, (x) => hpOf(x, hitEid) === 1000, r.line)

  // ── 쓰러뜨리면 다시 선다 ──
  let logFrom = L.serverLogSize()
  r = await b.cmd('/soulstest dummy hit 100000', 'DUMMY hit')
  sc.checkCmd('a huge hit fells the nearest dummy', r, (x) => x.kv.killed === 'true' && L.num(x.kv.hp) === 0, r.line)
  const felled = r.kv ? +r.kv.eid : -1
  r = await dojo()
  s = slots(r)
  const which = Object.keys(s).find((k) => s[k].state.startsWith('wait'))
  sc.check('the felled dummy\'s slot waits (respawn 60 ticks), the other two stay', r.kv && r.kv.alive === '2' && which, r.line)
  r = await waitDojo((x) => x.kv.alive === '3', 6000)
  s = slots(r)
  sc.check('the dojo stands it again after the wait, as a new body', r.kv && r.kv.alive === '3' && which && s[which].eid !== felled &&
    s[which].hp === 1000, r.line)
  if (L.ENV.serverLog) {
    const die = L.serverTAny('FOE die', logFrom)
    sc.check('server log: FOE die id=dummy why=hit by=<bot>', die.some((x) => x.kv.id === 'dummy' && x.kv.why === 'hit' && +x.kv.eid === felled),
      die.map((x) => x.line).join(' | ') || '줄 없음')
  }

  // /kill 은 그대로 죽인다 (KILL 만 막지 않는다), 다시 선다
  logFrom = L.serverLogSize()
  await b.cmd('/kill @e[type=zombie,tag=souls_foe,limit=1,sort=nearest]', null, 1000)
  await L.sleep(600)
  r = await dojo()
  sc.checkCmd('vanilla /kill fells a dummy (KILL passes)', r, (x) => x.kv.alive === '2', r.line)
  if (L.ENV.serverLog) {
    const die = L.serverTAny('FOE die', logFrom)
    sc.check('server log: FOE die why=kill', die.some((x) => x.kv.why === 'kill'), die.map((x) => x.line).join(' | ') || '줄 없음')
  }
  r = await waitDojo((x) => x.kv.alive === '3', 6000)
  sc.checkCmd('and it stands again', r, (x) => x.kv.alive === '3', r.line)
  await b.cmd('/kill @e[type=item,distance=..40]', null, 600)
  await b.cmd('/kill @e[type=experience_orb,distance=..40]', null, 600)

  // 밀린 몸은 제자리로, 공허에 떨어진 몸은 처음 선 자리로
  await b.cmd('/tp @e[type=zombie,tag=souls_foe,limit=1,sort=nearest] ~1.5 ~ ~0.5', null, 800)
  r = await waitDojo((x, ss) => Object.values(ss).every((v) => v.drift < 0.2), 3000)
  sc.checkCmd('a pushed dummy goes back to its anchor (check-every 10)', r, (x) => x.kv.alive === '3' &&
    Object.values(slots(x)).every((v) => v.drift < 0.2), r.line)
  await b.cmd('/tp @e[type=zombie,tag=souls_foe,limit=1,sort=nearest] ~ -140 ~', null, 800)
  await L.sleep(1500)
  r = await waitDojo((x, ss) => x.kv.alive === '3' && Object.values(ss).every((v) => v.drift < 0.2), 3000)
  sc.checkCmd('a dummy dropped below the world is sent home, not killed (VOID)', r, (x) => x.kv.alive === '3' &&
    Object.values(slots(x)).every((v) => v.drift < 0.2), r.line)

  // ── dummy clear 뒤 기다리면 다시 선다 ──
  r = await b.cmd('/soulstest dummy clear', 'DUMMY clear')
  sc.checkCmd('dummy clear removes the three', r, (x) => x.kv.n === '3', r.line)
  r = await dojo()
  sc.checkCmd('right after clear: none stand', r, (x) => x.kv.alive === '0', r.line)
  r = await waitDojo((x) => x.kv.alive === '3', 7000)
  sc.checkCmd('after the respawn wait all three stand again', r, (x) => x.kv.alive === '3', r.line)

  // ── 300칸 떨어지면 청크와 함께 사라지고, 돌아오면 다시 선다 (R7) ──
  const farX = center[0] - 300
  const farZ = center[2]
  // 디딜 블록: 그 청크를 붙잡아 올려 두고 놓는다 (올라오지 않은 청크에는 /setblock 이 되지 않는다. 300칸 밖이라 도장 청크와 상관없다)
  await b.cmd(`/forceload add ${farX} ${farZ}`, null, 1500)
  await L.sleep(500)
  await b.cmd(`/setblock ${farX} ${room.y - 1} ${farZ} minecraft:deepslate_tiles`, null, 800)
  logFrom = L.serverLogSize()
  await b.cmd(`/tp @s ${farX + 0.5} ${room.y} ${farZ + 0.5}`, null, 1200)
  await L.sleep(1500)
  r = await b.cmd('/soulstest pos', 'POS')
  sc.checkCmd('standing 300 blocks west of the dojo', r, (x) => Math.abs(L.num(x.kv.x) - (farX + 0.5)) < 1 && x.kv.ground === 'true', r.line)
  let gone = []
  const tg = Date.now()
  while (Date.now() - tg < 35000) {
    gone = L.serverTAny('FOE gone id=dummy why=unload', logFrom)
    if (gone.length >= 3) break
    await L.sleep(500)
  }
  sc.check('300 blocks away: the dojo chunks unload and FOE gone id=dummy why=unload for all three', gone.length === 3,
    `${gone.length}줄, ${((Date.now() - tg) / 1000).toFixed(1)}s` + (gone[0] ? ' | ' + gone[0].line : ''))
  r = await dump()
  sc.checkCmd('the registry holds no dummy while away', r, (x) => x.kv.n === '0', r.line)
  r = await dojo()
  sc.checkCmd('the dojo does not stand dummies while nobody is near', r, (x) => x.kv.near === 'false' && x.kv.alive === '0', r.line)
  logFrom = L.serverLogSize()
  await b.cmd('/soulstest dojo tp hall', 'DOJO tp')
  r = await waitDojo((x) => x.kv.alive === '3', 8000)
  sc.checkCmd('back in the hall: all three stand again right away', r, (x) => x.kv.alive === '3' && x.kv.near === 'true', r.line)
  if (L.ENV.serverLog) {
    const sp = L.serverTAny('FOE spawn id=dummy why=dojo_', logFrom)
    sc.check('server log: FOE spawn why=dojo_* after coming back', sp.length >= 3, sp.map((x) => x.kv.why).join(','))
  }
  await b.cmd(`/setblock ${farX} ${room.y - 1} ${farZ} minecraft:air`, null, 800)
  await b.cmd(`/forceload remove ${farX} ${farZ}`, null, 800)

  // ── 50번 세워도 깨끗한 몸 (R8) ──
  const bad = []
  let made = 0
  for (let i = 0; i < 50; i++) {
    r = await b.cmd('/soulstest dummy spawn ' + (i % 2 ? 'away' : 'toward'), 'DUMMY spawn')
    if (!r.kv || r.kv.error) { bad.push('#' + i + ' ' + (r.line || 'no answer')); continue }
    made++
    const k = r.kv
    const clean = k.baby === '0' && k.equipped === '0' && k.drop === '0.000' && k.silent === 'true' && k.aware === 'false' &&
      k.collidable === 'false' && L.num(k.kbres) === 1 && k.persistent === 'false' && k.farremove === 'false' && k.pickup === 'false' &&
      k.tags === 'true' && k.reg === 'true' && k.mod === '0' && L.num(k.max) === 1000 && L.num(k.vhp) === 20
    if (!clean) bad.push('#' + i + ' ' + r.line)
    if (i % 10 === 9) await b.cmd('/soulstest dummy clear', 'DUMMY clear')
  }
  sc.check('50 dummy spawns: adult, unequipped, drop 0, silent, AI off, not pushed, kb resistance 1, not saved, kept far, no pickup, tagged, registered',
    made === 50 && bad.length === 0, bad.slice(0, 2).join(' | ') || `${made} 마리`)
  r = await b.cmd('/soulstest dummy spawn toward 50', 'DUMMY spawn')
  sc.checkCmd('dummy spawn with an hp override (×1.0 at normal)', r, (x) => L.num(x.kv.max) === 50 && L.num(x.kv.hp) === 50, r.line)
  r = await b.cmd('/soulstest dummy hit 1000', 'DUMMY hit')
  sc.checkCmd('the 50-hp dummy falls to one hit', r, (x) => x.kv.killed === 'true', r.line)
  await b.cmd('/soulstest dummy clear', 'DUMMY clear')
  r = await waitDojo((x) => x.kv.alive === '3', 7000)
  sc.checkCmd('the dojo is whole again at the end', r, (x) => x.kv.alive === '3', r.line)
  await b.cmd('/souls tp room', null, 1200)
}, { timeout: 300 })
