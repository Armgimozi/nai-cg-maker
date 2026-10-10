// PvP 켜기/끄기 (5.7): 끈 세계에서는 플레이어 → 플레이어의 모든 길을 막는다 (근접, 화살·눈덩이, 투척 물약, 잔류 구름, 플러그인의
// 피해), 켠 세계에서는 막지 않고 피해를 셈한다 (근접은 souls 무기의 공격력 다리, 투사체는 최대 HP / 20 배율, 그다음 방어).
// 두 봇 A (때린다) 와 B (맞는다). 막은 줄 PVP_BLOCK 은 맞은 사람 (B) 에게 온다.
'use strict'
const L = require('./lib')

L.run('pvp', async (sc) => {
  const a = await L.connect(sc)
  const b = await L.connect(sc, { name: process.env.BOT_NAME_B || 'SoulsPvpB' })
  await L.sleep(1500)
  await a.cmd('/souls tp lane', null, 1200)
  await L.sleep(500)
  await a.ground(3000)
  // B 를 A 앞 2.2칸에 세운다 (구르기 길 lane 은 동쪽 +x 로 트였다. 시험 방은 머리 높이에 걸리는 것이 있어 화살이 박혔다)
  const pa = a.bot.entity.position
  await a.cmd(`/tp ${b.name} ${(pa.x + 2.2).toFixed(2)} ${pa.y.toFixed(2)} ${pa.z.toFixed(2)} 90 0`, null, 1500)
  await a.cmd(`/tp ${a.name} ${pa.x.toFixed(2)} ${pa.y.toFixed(2)} ${pa.z.toFixed(2)} -90 0`, null, 1500)
  await L.sleep(800)
  const s0 = await a.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check('world settings: pvp off (start.auto)', s0.kv && s0.kv.pvp === 'false' && s0.kv.gamerule_pvp === 'false', s0.line || '')
  const ib = await b.cmd('/soulstest info', 'INFO ')
  const maxhpB = ib.kv ? L.num(ib.kv.maxhp) : 400

  const target = () => Object.values(a.bot.entities).find((e) => e.type === 'player' && e.username === b.name)
  const blocks = (from) => b.tLines('PVP_BLOCK', from)

  // ── 끔: 모든 길이 막힌다 ──
  let from = b.sys.length
  const hp0 = b.health
  const ph = await a.cmd(`/soulstest pvphit ${b.name} 40`, 'PVPHIT ')
  // 원인이 플레이어인 피해는 바닐라 규칙 pvp=false 가 이벤트 전에 버린다 (ServerPlayer.hurtServer 의 canHarmPlayer): 줄 없이 0
  sc.checkCmd('off: damage caused by a player does not land (vanilla rule, before any event)', ph, (r) => L.num(r.kv.dealt) === 0 && !b.tLines('DEF ', from).length)
  from = b.sys.length
  const e = target()
  if (e) {
    await a.bot.lookAt(e.position.offset(0, 1.5, 0), true)
    await L.sleep(150)
    a.bot.attack(e)
    await L.sleep(500)
  }
  sc.check('off: melee is blocked before vanilla (PVP_BLOCK path=melee)', blocks(from).some((x) => x.kv.path === 'melee'), (e ? '' : '대상 없음 ') + blocks(from).map((x) => x.line).join(' | '))
  for (const kind of ['arrow', 'snowball', 'potion', 'cloud']) {
    from = b.sys.length
    await a.cmd(`/soulstest pvpshoot ${b.name} ${kind}`, 'PVPSHOOT ')
    const want = kind === 'arrow' || kind === 'snowball' ? 'projectile' : kind
    const got = await b.waitSys((m) => m.plain.startsWith('[T] PVP_BLOCK') && L.kvOf(m.plain).path === want, kind === 'arrow' ? 1500 : 3000, from)
    const tr = a.tLines('PVPSHOOT_TRACE').slice(-1).map((x) => x.line).join('')
    if (kind === 'arrow') {
      // 화살은 바닐라 규칙 pvp=false 가 맞을 대상에서 아예 뺀다 (이벤트 없이 지나간다). 플러그인의 ProjectileHitEvent 막기는 그 다음 겹
      const hurt = b.tLines('DEF ', from).length > 0 || Math.abs(b.health - hp0) > 0.01
      sc.check('off: arrow does not hit (vanilla rule passes it through, or PVP_BLOCK path=projectile)', !hurt, (got ? got.plain : '이벤트 없이 지나감') + ' ' + tr)
    } else {
      sc.check(`off: ${kind} is blocked (path=${want})`, !!got, got ? got.plain : (blocks(from).map((x) => x.line).join(' | ') || '줄 없음') + ' ' + tr)
    }
    await L.sleep(300)
  }
  await L.sleep(500)
  const poison = await b.cmd('/soulstest effect poison 1', 'EFFECT ')
  sc.check('off: victim health unchanged and not poisoned', Math.abs(b.health - hp0) < 0.01, `hp ${hp0} → ${b.health} ${poison.line || ''}`)

  // ── 켬 ──
  const on = await a.cmd('/souls settings pvp on', (m) => L.translateKeys(m.raw).includes('souls.admin.settings-set'), 3000)
  sc.check('admin turns pvp on (/souls settings pvp on, souls.admin.settings-set)', !!on.msg, on.cmd)
  await L.sleep(600)
  const s1 = await a.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check('settings: pvp on, gamerule follows', s1.kv && s1.kv.pvp === 'true' && s1.kv.gamerule_pvp === 'true', s1.line || '')
  // 순간이동 뒤 보호 (pvp.respawn-grace 100틱) 가 지나기를 기다린다
  await L.sleep(5500)
  await b.cmd('/soulstest heal', 'HEAL')
  from = b.sys.length
  const ph2 = await a.cmd(`/soulstest pvphit ${b.name} 40`, 'PVPHIT ')
  const def = b.tLines('DEF ', from)[0]
  sc.checkCmd('on: plugin (skill) damage lands in HP units, reduced by defense (DEF from=player_skill)', ph2, (r) => L.num(r.kv.dealt) > 0 && L.num(r.kv.dealt) < 40 && def && def.kv.from === 'player_skill' && Math.abs(L.num(def.kv.raw) - 40) < 0.01, (ph2.line || '') + ' | ' + (def ? def.line : 'DEF 없음'))
  await b.cmd('/soulstest heal', 'HEAL')
  // /stats 는 어디서나 열리지만 숨을 곳이 아니다 (검토 stats-dialog-pvp-immunity): 창이 열려 있어도 맞는다. 휴식 창은 숨을 곳이다
  await b.cmd('/stats', 'STATS ', 2000)
  from = b.sys.length
  const ps = await a.cmd(`/soulstest pvphit ${b.name} 40`, 'PVPHIT ')
  sc.checkCmd('on: a player with /stats open can still be hit (stats dialog is no shelter)', ps, (r) => L.num(r.kv.dealt) > 0 && r.kv.why === 'null')
  await b.cmd('/soulstest press stats exit', null, 600)
  await b.cmd('/soulstest heal', 'HEAL')
  await b.cmd('/soulstest rest', 'REST ', 2000)
  from = b.sys.length
  const pr = await a.cmd(`/soulstest pvphit ${b.name} 40`, 'PVPHIT ')
  sc.checkCmd('on: a resting player (rest menu open) is not hit (PVP_BLOCK why=dialog)', pr, (r) => L.num(r.kv.dealt) === 0 && r.kv.why === 'dialog')
  await b.cmd('/soulstest press rest exit', null, 600)
  await b.cmd('/soulstest heal', 'HEAL')
  // 해치는 잔류 구름: 바닐라 단위 (즉시 피해 I 의 구름 몫 3) 라 최대 HP / 20 배율을 받는다 (검토 pvp-indirect-unscaled)
  from = b.sys.length
  await a.cmd(`/soulstest pvpshoot ${b.name} harm`, 'PVPSHOOT ')
  const hc = await b.waitSys((m) => m.plain.startsWith('[T] DEF ') && L.kvOf(m.plain).from === 'player_indirect', 3000, from)
  const hk = hc ? L.kvOf(hc.plain) : null
  sc.check('on: a harming cloud is scaled like other vanilla damage (DEF from=player_indirect, raw = 3 x maxHP/20)', hk && Math.abs(L.num(hk.raw) - 3 * maxhpB / 20) < 0.5,
    hc ? hc.plain : '줄 없음 ' + b.tLines('DEF ', from).map((x) => x.line).join(' | '))
  await L.sleep(1600)
  await b.cmd('/soulstest heal', 'HEAL')
  await L.sleep(300)
  await L.sleep(300)
  from = b.sys.length
  const e2 = target()
  if (e2) {
    await a.bot.lookAt(e2.position.offset(0, 1.5, 0), true)
    await L.sleep(1300) // 공격 대기가 다 찬 뒤 (회복 1: 곤봉은 망치 분류, 한 주기 18틱 = 0.9초)
    a.bot.attack(e2)
    await L.sleep(600)
  }
  const mel = b.tLines('DEF ', from).find((x) => /^player_(melee|vanilla)$/.test(x.kv.from))
  sc.check('on: melee with the club uses its attack rating (DEF from=player_melee)', mel && mel.kv.from === 'player_melee' && L.num(mel.kv.raw) > 20, mel ? mel.line : b.tLines('', from).map((x) => x.line).slice(0, 4).join(' | ') || '줄 없음')
  // 근력이 PvP 근접 피해를 올린다 (공격력 = 74 × (1 + 0.8 × 곡선(근력)): 근력 10 → 81.7, 40 → 114.3, × 1.399)
  if (mel) {
    await a.cmd('/soulstest stat str 40', 'STAT ')
    await b.cmd('/soulstest heal', 'HEAL')
    from = b.sys.length
    const e3 = target()
    if (e3) {
      await a.bot.lookAt(e3.position.offset(0, 1.5, 0), true)
      await L.sleep(1300)
      a.bot.attack(e3)
      await L.sleep(600)
    }
    const mel40 = b.tLines('DEF ', from).find((x) => x.kv.from === 'player_melee')
    const ratio = mel40 ? L.num(mel40.kv.raw) / L.num(mel.kv.raw) : NaN
    sc.check('on: strength 40 hits harder than strength 10 (raw x1.399 = attack rating 114.3 / 81.7)', Math.abs(ratio - 114.256 / 81.696) < 0.04,
      `${mel.kv.raw} → ${mel40 ? mel40.kv.raw : '?'} (×${ratio.toFixed(3)})`)
    await a.cmd('/soulstest stat str 10', 'STAT ')
  }
  await b.cmd('/soulstest heal', 'HEAL')
  from = b.sys.length
  await a.cmd(`/soulstest pvpshoot ${b.name} arrow`, 'PVPSHOOT ')
  const arr = await b.waitSys((m) => m.plain.startsWith('[T] DEF ') && L.kvOf(m.plain).from === 'player_projectile', 3000, from)
  await L.sleep(300)
  sc.check('on: an arrow lands, scaled by max HP / 20 (DEF from=player_projectile)', !!arr, arr ? arr.plain : '줄 없음 ' + a.tLines('PVPSHOOT_TRACE').slice(-1).map((x) => x.line).join(''))
  // 투척 물약과 잔류 구름도 걸린다 (막는 줄 없이 독)
  for (const kind of ['potion', 'cloud']) {
    await b.cmd('/effect clear @s', null, 1000)
    await L.sleep(300)
    from = b.sys.length
    // 효과를 모두 지운 뒤라 들어온 효과는 그 독뿐이다 (효과 번호는 판마다 0/1 부터라 번호로 가리지 않는다)
    const poisoned = () => Object.values(b.bot.entity.effects || {}).some((x) => x && x.duration > 0)
    await a.cmd(`/soulstest pvpshoot ${b.name} ${kind}`, 'PVPSHOOT ')
    const end = Date.now() + 3000
    while (!poisoned() && Date.now() < end) await L.sleep(50)
    sc.check(`on: ${kind} poisons the other player (no PVP_BLOCK)`, poisoned() && !blocks(from).length,
      JSON.stringify(Object.values(b.bot.entity.effects || {})).slice(0, 120) + ' ' + blocks(from).map((x) => x.line).join(' | '))
  }
  await b.cmd('/effect clear @s', null, 1000)

  // 되돌린다 (뒤 시나리오를 위해)
  await a.cmd('/souls settings pvp off', (m) => L.translateKeys(m.raw).includes('souls.admin.settings-set'), 3000)
  await L.sleep(400)
  const s2 = await a.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check('pvp off again', s2.kv && s2.kv.pvp === 'false', s2.line || '')
  await b.cmd('/soulstest heal', 'HEAL')
  sc.check('no kick during pvp scenario', !a.kick && !b.kick, (a.kick || '') + (b.kick || ''))
})
