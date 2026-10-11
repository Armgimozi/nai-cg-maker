// M1 P1-0 계약 점검 (M1_PLAN 1절의 P1-0, /soulstest contract). P1a·P1b 가 갈라지기 전에 함께 쓰는 틀이 서버에서 그대로 도는지 본다.
//   틱 차례: load → stamina → input → moves → roll → tap → brains → queue → poise → lock → hud → titles → rings (0.6, 빈 자리)
//   콘텐츠: moves.yml·enemies.yml 이 꺼내지고 비었다 (열쇠마다 jar 값으로 겹쳐 읽는 파일, R20)
//   적의 몸 (R8): randomizeData=false 라 좀비·허스크에 아기·갑옷이 없고 변명자·약탈자·스켈레톤이 무기를 들지 않는다. 떨굼 0, 조용히,
//     저장 안 함, 멀어도 사라지지 않음, 줍지 않음, 태그 souls_foe + souls_ent, 등록됨
//   옮기기 (R6): 표식 (souls_mark) 을 태운 채 Foes.teleport 가 옮기고 표식이 남는다. 깃발 없는 teleport 의 결과는 기록만
//   한 대: Foes.hit 원피해 100, 방어 20 → 83.33 (raw²/(raw+def)), 때린 사람의 lastCombatTick, 아파하는 몸짓 (hurt_animation),
//     두 번째 한 대로 쓰러지면 몸을 지우고 등록부에서 뺀다. 바닐라 /kill 로 죽어 세계에서 빠져도 등록부에서 빠진다 (R7)
//   서버 휘두르기 (S3): Swings.off / main 이 자기에게 animation 3 / 0 을 보내고 틱을 적는다
//   느려짐 (S4): Slow 0.5 → 걷기 0.1 (abilities 패킷 walkingSpeed 0.05), 뿌리 → 걷기 0·뛰기 0. 죽음·다른 세계·나가기 (다시 들어오면)
//     뒤에 바닐라 0.2 로 돌아온다. 서버 기록에 RESET why=DEATH|WORLD|QUIT|JOIN
'use strict'
const L = require('./lib')

const ORDER = 'load,stamina,input,moves,roll,tap,brains,queue,poise,lock,hud,titles,rings'

async function slow (b, what) {
  return b.cmd('/soulstest contract slow ' + what, 'CONTRACT_SLOW')
}

L.run('contract', async (sc) => {
  let b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(600)

  // ── 틱 차례와 콘텐츠, 거두기 이름 ──
  let r = await b.cmd('/soulstest contract ticker', 'CONTRACT_TICKER')
  // 빈 자리만 견준다: 묶음이 ticker.into 로 넣은 일 ("brains/dojo" 처럼 자리/이름) 은 자기 자리 뒤에 끼므로 빼고 본다 (P1b 부터)
  sc.checkCmd('ticker slots in the plan order (0.6)', r, (x) => x.kv.order.split(',').filter((s) => !s.includes('/')).join(',') === ORDER, r.line)
  r = await b.cmd('/soulstest contract content', 'CONTRACT_CONTENT')
  // P1-0 은 두 파일이 비었는지 봤다. 묶음이 내용을 더하므로 (P1b 의 dummy, P1a 의 동작) 겹쳐 읽혔는지만 본다
  sc.checkCmd('moves.yml and enemies.yml in Content.FILES and merged', r,
    (x) => /moves\.yml/.test(x.kv.files) && /enemies\.yml/.test(x.kv.files) && /^moves\.yml:\d+,enemies\.yml:\d+$/.test(x.kv.merged), r.line)
  r = await b.cmd('/soulstest contract reset', 'CONTRACT_RESET')
  sc.checkCmd('CombatReset has the slow owner (S4)', r, (x) => x.kv.owners.split(',').includes('slow'), r.line)
  const srv = L.ENV.serverDir
  if (srv) {
    const fs = require('fs')
    const path = require('path')
    const dir = path.join(srv, 'plugins', 'Soulslike', 'content')
    sc.check('content/moves.yml and enemies.yml extracted', fs.existsSync(path.join(dir, 'moves.yml')) && fs.existsSync(path.join(dir, 'enemies.yml')), dir)
  }

  // ── 적의 몸 (R8) ──
  for (const [type, n] of [['zombie', 20], ['husk', 10], ['vindicator', 6], ['pillager', 4], ['skeleton', 4]]) {
    r = await b.cmd(`/soulstest contract spawn ${type} ${n}`, 'CONTRACT_SPAWN', 6000)
    sc.checkCmd(`${type} x${n}: adult, unarmed, drop 0, silent, not saved, kept far, no pickup, tagged, registered (R8)`, r, (x) =>
      +x.kv.n === n && x.kv.baby === '0' && x.kv.equipped === '0' && x.kv.drop === '0.000' && +x.kv.silent === n && x.kv.persistent === '0' &&
      x.kv.farremove === '0' && x.kv.pickup === '0' && +x.kv.tags === n && +x.kv.reg === n, r.line)
    r = await b.cmd('/soulstest contract clear', 'CONTRACT_FOES')
    sc.checkCmd(`${type}: clear removes and unregisters`, r, (x) => x.kv.n === '0' && +x.kv.cleared === n, r.line)
  }
  r = await b.cmd('/soulstest contract spawn-id no_such_enemy', 'CONTRACT_SPAWN_ID')
  sc.checkCmd('Foes.spawn of an id not in enemies.yml gives nothing', r, (x) => x.kv.ok === 'false', r.line)
  // P1b: enemies.yml 의 dummy 는 선다 (몸 zombie)
  r = await b.cmd('/soulstest contract spawn-id dummy', 'CONTRACT_SPAWN_ID')
  sc.checkCmd('Foes.spawn of dummy (enemies.yml, P1b) gives a zombie body', r, (x) => x.kv.ok === 'true' && x.kv.type === 'zombie', r.line)
  await b.cmd('/soulstest contract clear', 'CONTRACT_FOES')

  // ── 옮기기 (R6) ──
  await b.cmd('/soulstest contract spawn zombie 1', 'CONTRACT_SPAWN')
  r = await b.cmd('/soulstest contract tp', 'CONTRACT_TP')
  sc.checkCmd('Foes.teleport moves a foe that carries a passenger and keeps it (R6)', r,
    (x) => x.kv.ok === 'true' && x.kv.kept === 'true' && Math.abs(L.num(x.kv.moved) - 1) < 0.05, r.line)
  if (r.kv) sc.note(`plain teleport with a passenger (no flag): ok=${r.kv.plain} kept=${r.kv.plainkept} moved=${r.kv.plainmoved}`)

  // ── 한 대 ──
  const hurt = []
  b._bot._client.on('hurt_animation', (d) => hurt.push(d))
  const h0 = hurt.length
  r = await b.cmd('/soulstest contract hit 100', 'CONTRACT_HIT')
  const want = 100 * 100 / 120
  sc.checkCmd('Foes.hit: 100 raw vs def 20 deals raw²/(raw+def) = 83.333, stamps lastCombatTick', r, (x) =>
    x.kv.landed === 'true' && Math.abs(L.num(x.kv.dealt) - want) < 0.01 && Math.abs(L.num(x.kv.hp) - (100 - want)) < 0.01 && x.kv.killed === 'false' &&
    x.kv.stamped === 'true', r.line)
  await L.sleep(400)
  sc.check('the foe plays the hurt animation (server-side hit feel, S12)', hurt.length > h0, `hurt_animation ${hurt.length - h0}`)
  r = await b.cmd('/soulstest contract hit 100', 'CONTRACT_HIT')
  sc.checkCmd('second hit fells it (hp 0, killed)', r, (x) => x.kv.killed === 'true' && L.num(x.kv.hp) === 0, r.line)
  r = await b.cmd('/soulstest contract foes', 'CONTRACT_FOES')
  sc.checkCmd('a felled foe leaves the registry', r, (x) => x.kv.n === '0', r.line)

  // 바닐라로 죽어 세계에서 빠진 몸도 등록부에서 빠진다 (EntityRemoveFromWorldEvent, R7)
  await b.cmd('/soulstest contract spawn husk 2', 'CONTRACT_SPAWN')
  r = await b.cmd('/soulstest contract foes', 'CONTRACT_FOES')
  sc.checkCmd('two foes registered and near', r, (x) => x.kv.n === '2' && x.kv.near === '2', r.line)
  // 이 시험이 세운 둘만 (도장의 허수아비는 시험 방에서 40칸 넘게 떨어져 있다)
  await b.cmd('/kill @e[tag=souls_foe,distance=..16]', null, 1000)
  await L.sleep(2000)
  // 죽은 몸이 떨군 것 (전리품) 을 치운다: 뒤의 시나리오가 바닥의 물체를 센다
  await b.cmd('/kill @e[type=item,distance=..24]', null, 800)
  await b.cmd('/kill @e[type=experience_orb,distance=..24]', null, 800)
  r = await b.cmd('/soulstest contract foes', 'CONTRACT_FOES')
  sc.checkCmd('foes removed from the world by vanilla leave the registry (R7)', r, (x) => x.kv.n === '0', r.line)

  // ── 서버 휘두르기 (S3) ──
  const anim = []
  b._bot._client.on('animation', (d) => { if (d.entityId === b._bot.entity.id) anim.push(d.animation) })
  let a0 = anim.length
  r = await b.cmd('/soulstest contract swing off', 'CONTRACT_SWING')
  await L.sleep(400)
  sc.checkCmd('Swings.off swings the off hand to the player and records the tick', r, (x) => x.kv.hand === 'OFF_HAND' && x.kv.at === x.kv.t &&
    x.kv.since === '0', r.line)
  sc.check('off-hand swing reaches the player (animation 3)', anim.slice(a0).includes(3), 'animation ' + anim.slice(a0).join(','))
  a0 = anim.length
  r = await b.cmd('/soulstest contract swing main', 'CONTRACT_SWING')
  await L.sleep(400)
  sc.checkCmd('Swings.main records the main hand', r, (x) => x.kv.hand === 'HAND' && x.kv.at === x.kv.t, r.line)
  sc.check('main-hand swing reaches the player (animation 0)', anim.slice(a0).includes(0), 'animation ' + anim.slice(a0).join(','))

  // ── 느려짐 (S4) ──
  const abil = []
  b._bot._client.on('abilities', (d) => abil.push(d))
  const ab0 = abil.length
  r = await slow(b, '0.5')
  sc.checkCmd('slow 0.5: walk speed 0.1, movement base 0.05 (setWalkSpeed, no FOV zoom)', r, (x) =>
    Math.abs(L.num(x.kv.walk) - 0.1) < 1e-4 && Math.abs(L.num(x.kv.base) - 0.05) < 1e-4 && x.kv.owners === 'contract:0.50', r.line)
  await L.sleep(400)
  const lastAb = abil[abil.length - 1]
  sc.check('client gets abilities walkingSpeed 0.05', abil.length > ab0 && Math.abs(lastAb.walkingSpeed - 0.05) < 1e-4,
    lastAb ? 'walkingSpeed=' + lastAb.walkingSpeed : 'abilities 패킷 없음')
  r = await slow(b, 'root')
  sc.checkCmd('root: walk 0 and jump 0', r, (x) => L.num(x.kv.walk) === 0 && L.num(x.kv.jump) === 0, r.line)
  r = await slow(b, 'clear')
  sc.checkCmd('clear: back to vanilla walk 0.2 and jump', r, (x) => Math.abs(L.num(x.kv.walk) - 0.2) < 1e-4 && L.num(x.kv.jump) > 0.3 &&
    x.kv.owners === '-', r.line)

  // 죽음
  await slow(b, '0.5')
  let from = b.sys.length
  await b.cmd('/soulstest kill', 'KILL')
  await b.waitT('RESPAWN', 8000, from)
  await L.sleep(800)
  const rd = b.tLines('RESET why=DEATH', from)
  sc.check('death fires CombatReset (RESET why=DEATH owners has slow)', rd.length === 1 && rd[0].kv.owners.split(',').includes('slow'), rd.map((x) => x.line).join(' | '))
  r = await slow(b, 'show')
  sc.checkCmd('after death: walk speed back to 0.2', r, (x) => Math.abs(L.num(x.kv.walk) - 0.2) < 1e-4 && x.kv.owners === '-', r.line)

  // 다른 세계
  await slow(b, '0.5')
  from = b.sys.length
  await b.cmd('/souls tp lobby', null, 1500)
  await L.sleep(1200)
  const rw = b.tLines('RESET why=WORLD', from)
  sc.check('world change fires CombatReset (RESET why=WORLD)', rw.length >= 1, rw.map((x) => x.line).join(' | ') || '줄 없음')
  r = await slow(b, 'show')
  sc.checkCmd('after world change: walk speed back to 0.2', r, (x) => Math.abs(L.num(x.kv.walk) - 0.2) < 1e-4, r.line)
  await b.cmd('/souls tp room', null, 1500)
  await L.sleep(1000)

  // 나가기 (다시 들어오면 바닐라 0.2)
  await slow(b, '0.5')
  const logFrom = L.serverLogSize()
  await b.quit()
  await L.sleep(1500)
  b = await L.connect(sc)
  await L.sleep(1500)
  r = await slow(b, 'show')
  sc.checkCmd('after quit and rejoin: walk speed 0.2 (not saved slowed)', r, (x) => Math.abs(L.num(x.kv.walk) - 0.2) < 1e-4 && x.kv.owners === '-', r.line)
  if (L.ENV.serverLog) {
    const q = L.serverTLines(b.name || process.env.BOT_NAME, 'RESET why=QUIT', logFrom)
    const j = L.serverTLines(b.name || process.env.BOT_NAME, 'RESET why=JOIN', logFrom)
    sc.check('quit fires CombatReset (server log RESET why=QUIT)', q.length === 1, q.map((x) => x.line).join(' | ') || '줄 없음')
    sc.check('join fires CombatReset (server log RESET why=JOIN)', j.length >= 1, j.map((x) => x.line).join(' | ') || '줄 없음')
  }
  await b.cmd('/soulstest contract clear', 'CONTRACT_FOES')
})
