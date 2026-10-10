// 서버를 다시 켠 뒤 (run_tests.sh 의 두 번째 기동): persist.js 가 남긴 RUN_DIR/persist.json 과 견준다 (5.7, 5.10, 12.6).
//   1. 같은 봇 (기사, 레벨 13): 세계 설정 (어려움·PvP 켬, 확정, rev) 이 세계 PDC 에서 되살아났고 바닐라 규칙 pvp 도 켜져 있다.
//      세계 설정 창도 출신 창도 뜨지 않는다. 능력치·레벨·소울·최대 HP (체력이 잘리지 않는다)·이동 속도가 같고, 수정자는 하나씩,
//      시작 아이템이 겹치지 않는다 (KIT_LATE 없음).
//   2. 나중에 처음 들어온 사람 (이름이 Souls 로 시작하지 않아 출신 없이 온다): 세계 설정 창이 아니라 채팅 한 줄 "이 세계: 어려움 · PvP 켬"
//      (start.notice, START_NOTICE) 을 받고 곧바로 출신 창. 고르기 전에는 짧은 누름이 구르지 않는다. 궁수를 고르면 손도끼와 단궁.
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

L.run('persist_check', async (sc) => {
  const f = L.ENV.runDir && path.join(L.ENV.runDir, 'persist.json')
  if (!sc.check('persist.json from the first boot', f && fs.existsSync(f), f || 'RUN_DIR 없음')) return
  const exp = JSON.parse(fs.readFileSync(f, 'utf8'))
  const b = await L.connect(sc, { name: exp.name })
  await L.sleep(3000)
  const s = await b.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check(`restart: world settings kept (${exp.settings.difficulty}, pvp ${exp.settings.pvp}, confirmed, rev ${exp.settings.rev})`, s.kv &&
    s.kv.difficulty === exp.settings.difficulty && s.kv.pvp === exp.settings.pvp && s.kv.confirmed === 'true' && s.kv.rev === exp.settings.rev, s.line || '')
  sc.check('restart: vanilla pvp gamerule follows the saved settings', s.kv && s.kv.gamerule_pvp === exp.settings.pvp, s.kv ? 'gamerule_pvp=' + s.kv.gamerule_pvp : '')
  sc.check('restart: no settings dialog and no origin dialog for a born player', !b.tLines('START_DIALOG').length && !b.p.dialogs.length,
    `START_DIALOG ${b.tLines('START_DIALOG').length}, 창 ${b.p.dialogs.length}`)
  const st = await b.cmd('/soulstest stats', 'STATS ')
  const keys = ['level', 'origin', 'souls', 'vig', 'mnd', 'end', 'str', 'dex', 'int']
  sc.check(`restart: ${exp.stats.origin} level ${exp.stats.level}, souls ${exp.stats.souls}, stats kept`, st.kv && keys.every((k) => st.kv[k] === exp.stats[k]),
    st.line || '')
  const info = await b.cmd('/soulstest info', 'INFO ')
  sc.check(`restart: max HP ${exp.maxhp} and health not cut to 20`, info.kv && info.kv.maxhp === exp.maxhp && L.num(info.kv.hp) >= L.num(exp.maxhp) - 0.5, info.line || '')
  const a = await b.cmd('/soulstest attr', 'ATTRS ')
  sc.check('restart: one souls:lvl_vig on max_health, movement speed as before with one souls:lvl_dex', a.kv &&
    (a.kv.max_health_mods.match(/souls:lvl_vig/g) || []).length === 1 && Math.abs(L.num(a.kv.movement_speed) - exp.move) < 1e-4 &&
    (a.kv.movement_speed_mods.match(/souls:lvl_dex/g) || []).length === 1, a.line || '')
  const inv = b.bot.inventory.slots.map((it, i) => (it && JSON.stringify(it.components || []).match(/souls\.weapon\.([a-z_]+)\.name/) ? i + ':' + RegExp.$1 : null)).filter(Boolean)
  sc.check('restart: kit not duplicated (sword in hand, shield in off hand, nothing else)', JSON.stringify(inv) === JSON.stringify(Object.entries(exp.kit).map(([k, v]) => k + ':' + v)) &&
    !b.tLines('KIT_LATE').length, inv.join(' '))
  const ck = await b.cmd('/souls check', (m) => m.plain.includes('world settings'), 6000)
  sc.check('/souls check shows the saved settings', ck.line && ck.line.includes(`difficulty=${exp.settings.difficulty} pvp=${exp.settings.pvp} confirmed=true`), ck.line || '')

  // ── 나중에 처음 들어온 사람 ──
  const late = process.env.BOT_NAME_LATE || 'LateJoiner'
  let c = await L.connect(sc, { name: late })
  const noticeKey = (m) => L.translateKeys(m.raw).includes('souls.start.notice')
  const n = await c.waitSys(noticeKey, 15000)
  sc.check('later joiner: chat notice "this world: hard · PvP on" (souls.start.notice with the saved values)', n && L.translateKeys(n.raw).includes('souls.difficulty.hard.name') &&
    L.translateKeys(n.raw).includes('souls.pvp.on'), n ? L.translateKeys(n.raw).join(',') : c.sys.map((m) => m.plain.slice(0, 50)).join(' | '))
  const sn = await c.waitT('START_NOTICE', 3000)
  sc.check('later joiner: START_NOTICE line, not a settings dialog', sn && !c.tLines('START_DIALOG').length, sn ? sn.line : '줄 없음')
  let raw = await c.waitDialog(0, 4000)
  sc.check('later joiner: origin dialog follows', raw && c.dialogId(raw) === 'origin', raw ? c.dialogId(raw) : '창 없음')
  // 출신 창을 닫아도 (Esc = "나중에 고른다") 망가지지 않는다: 출신 없이 서 있고, 무엇을 하려 하면 창이 다시 뜨고, 다시 들어오면 또 묻는다
  let from = c.sys.length
  if (raw) c.clickDialog('exit', {}, raw)
  const later = await c.waitT('ORIGIN_LATER', 3000, from)
  sc.check('later joiner: closing the origin dialog leaves them unborn (ORIGIN_LATER), no origin given', !!later && !c.tLines('ORIGIN ', from).length, later ? later.line : '줄 없음')
  await L.sleep(2200) // start.reopen-cooldown 40틱
  from = c.sys.length
  let d = c.p.dialogs.length
  await c.tapSneak({})
  const sk = await c.waitT('ROLL_TAP_SKIP', 1500, from)
  const ro = await c.waitT('ORIGIN_REOPEN', 1500, from)
  raw = await c.waitDialog(d, 3000)
  sc.check('later joiner, unborn: a sneak tap does not roll and re-opens the origin dialog (ORIGIN_REOPEN)', sk && sk.kv.why === 'unborn' && !c.tLines('ROLL ', from).length &&
    ro && raw && c.dialogId(raw) === 'origin', [sk && sk.line, ro && ro.line, raw ? c.dialogId(raw) : '창 없음'].join(' | '))
  from = c.sys.length
  const hit = await c.cmd('/soulstest hit 40', 'HIT ')
  sc.check('later joiner, unborn: caused damage does not land (UNBORN_SAFE)', hit.kv && L.num(hit.kv.dealt) === 0, hit.line || '')
  if (raw) c.clickDialog('exit', {}, raw)
  await L.sleep(500)
  await c.quit()
  await L.sleep(1500)
  c = await L.connect(sc, { name: late })
  const sn2 = await c.waitT('START_NOTICE', 15000)
  raw = await c.waitDialog(0, 4000)
  sc.check('later joiner, rejoin while unborn: notice and origin dialog again', sn2 && raw && c.dialogId(raw) === 'origin', (sn2 ? sn2.line : '알림 없음') + ' | ' + (raw ? c.dialogId(raw) : '창 없음'))
  if (raw) {
    d = c.p.dialogs.length
    c.clickDialog('archer', {}, raw)
    const conf = await c.waitDialog(d, 3000)
    from = c.sys.length
    if (conf) c.clickDialog('choose', {}, conf)
    const og = await c.waitT('ORIGIN ', 3000, from)
    sc.check('later joiner: archer chosen (hatchet + short bow)', og && og.kv.id === 'archer' && og.kv.kit === 'weapon:levy_hatchet,weapon:wall_shortbow,item:arrows', og ? og.line : '줄 없음')
    await L.sleep(400)
  }
  const s2 = await c.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check('later joiner changed nothing in the world settings', s2.kv && s2.kv.rev === exp.settings.rev && s2.kv.difficulty === exp.settings.difficulty, s2.line || '')
  sc.check('no kick after restart', !b.kick && !c.kick, (b.kick || '') + (c.kick || ''))
})
