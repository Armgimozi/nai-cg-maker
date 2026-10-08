// 남는 것 (5.3, 5.7, 5.10). run_tests.sh 가 맨 끝 (지연 판 뒤) 에 돌리고, 서버를 다시 켠 뒤 persist_check.js 가 같은 봇으로 본다.
//   1. 레벨 비용이 5.3 의 식 그대로: 레벨 1 → 2 는 320 (319 면 거절 LEVELUP_PLUS_DENY why=souls), 레벨 40 → 41 은 5,974 (5,973 이면 거절),
//      한 번에 셋 (41 → 44) 은 차례로 더한 값. "올린다" 가 정확히 그만큼 빼고, 모자라면 아무것도 바꾸지 않는다.
//   2. 관리자가 출신을 지우고 기사로 고른 뒤 체력 +2, 기력 +1, 정신 +1 (레벨 9 → 13, 480 + 500 + 520 + 623 = 2,123 소울).
//      레벨을 샀으니 휴식 창에 "출신 다시 고르기" 가 없다.
//   3. 관리자 명령으로 세계 설정을 어려움·PvP 켬으로 (via=command, settings.log, 접속한 사람에게 알림).
//   4. 다시 켠 뒤 볼 값을 RUN_DIR/persist.json 에 적는다.
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

/** 5.3: 레벨 L 에서 다음 레벨의 비용 */
function cost (lv) {
  if (lv <= 11) return 300 + 20 * lv
  const x = lv + 1
  return Math.round(0.6 * (0.02 * x * x * x + 3.06 * x * x + 105.6 * x - 895))
}

L.run('persist', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  const st0 = await b.cmd('/soulstest stats', 'STATS ')
  if (!sc.checkCmd('starts as deprived level 1', st0, (r) => r.kv.origin === 'deprived' && r.kv.level === '1')) return
  sc.check('level cost formula matches the 5.3 table (1→2 320, 8→9 460, 11→12 520, 12→13 623, 20→21 1714, 40→41 5974, 99→100 36159)',
    cost(1) === 320 && cost(8) === 460 && cost(11) === 520 && cost(12) === 623 && cost(20) === 1714 && cost(40) === 5974 && cost(99) === 36159,
    [1, 8, 11, 12, 20, 40, 99].map((l) => l + ':' + cost(l)).join(' '))

  // ── 레벨 1 → 2: 319 는 모자라고 320 은 된다 ──
  await b.cmd('/soulstest souls 319', 'SOULS ')
  let from = b.sys.length
  await b.cmd('/soulstest levelup vig', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  let deny = b.tLines('LEVELUP_PLUS_DENY', from)[0]
  sc.check('319 souls at level 1: "+" refused (cost 320)', deny && deny.kv.why === 'souls', deny ? deny.line : b.tLines('LEVELUP', from).map((x) => x.line).join(' | '))
  await b.cmd('/soulstest souls 320', 'SOULS ')
  from = b.sys.length
  const p1 = await b.cmd('/soulstest levelup vig', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  sc.check('320 souls: "+" takes it (LEVELUP_PLUS cost=320)', p1.kv && p1.line.startsWith('[T] LEVELUP_PLUS ') && L.num(p1.kv.cost) === 320, p1.line || '')
  from = b.sys.length
  const c1 = await b.cmd('/soulstest levelup confirm', (m) => /^\[T\] LEVELUP(_DENY)? /.test(m.plain) && !/open/.test(m.plain))
  sc.check('confirm: level 1 -> 2 for exactly 320, purse 0', c1.kv && c1.kv.from === '1' && c1.kv.to === '2' && c1.kv.cost === '320' && c1.kv.souls === '0', c1.line || '')

  // ── 레벨 40 → 41 (세제곱 식) ──
  await b.cmd('/soulstest levelup cancel', 'LEVELUP', 1500)
  await b.cmd('/soulstest stat vig 49', 'STAT ')
  const s40 = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('vigor 49 + five 10s = level 40', s40.kv && s40.kv.level === '40', s40.line || '')
  await b.cmd('/soulstest souls 5973', 'SOULS ')
  from = b.sys.length
  await b.cmd('/soulstest levelup str', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  deny = b.tLines('LEVELUP_PLUS_DENY', from)[0]
  sc.check('5,973 souls at level 40: refused (cost 5,974)', deny && deny.kv.why === 'souls', deny ? deny.line : '')
  await b.cmd('/soulstest souls 5974', 'SOULS ')
  const p40 = await b.cmd('/soulstest levelup str', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  sc.check('5,974 souls: "+" takes it', p40.kv && p40.line.startsWith('[T] LEVELUP_PLUS ') && L.num(p40.kv.cost) === 5974, p40.line || '')
  const c40 = await b.cmd('/soulstest levelup confirm', (m) => /^\[T\] LEVELUP(_DENY)? /.test(m.plain) && !/open/.test(m.plain))
  sc.check('confirm: level 40 -> 41 for exactly 5,974, purse 0', c40.kv && c40.kv.from === '40' && c40.kv.to === '41' && c40.kv.cost === '5974' && c40.kv.souls === '0', c40.line || '')
  // 셋 한꺼번에 (41 → 44): 차례로 더한다. 하나 모자라면 셋째 점에서 거절
  const three = cost(41) + cost(42) + cost(43)
  await b.cmd(`/soulstest souls ${three - 1}`, 'SOULS ')
  const run = []
  from = b.sys.length
  for (let i = 0; i < 3; i++) {
    const r = await b.cmd('/soulstest levelup dex', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
    run.push(r.line ? (r.line.startsWith('[T] LEVELUP_PLUS_DENY') ? 'deny' : L.num(r.kv.cost)) : 'none')
  }
  sc.check(`one soul short of three points (${three - 1}): the third "+" is refused`, run[0] === cost(41) && run[1] === cost(41) + cost(42) && run[2] === 'deny', run.join(','))
  await b.cmd(`/soulstest souls ${three}`, 'SOULS ')
  const r3 = await b.cmd('/soulstest levelup dex', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  sc.check(`with ${three}: running cost ${cost(41)} + ${cost(42)} + ${cost(43)} = ${three}`, r3.kv && L.num(r3.kv.cost) === three, r3.line || '')
  // 그 사이 소울이 줄면 "올린다" 는 거절하고 아무것도 바꾸지 않는다
  await b.cmd(`/soulstest souls ${three - 1}`, 'SOULS ')
  const cd = await b.cmd('/soulstest levelup confirm', (m) => /^\[T\] LEVELUP(_DENY)? /.test(m.plain) && !/open/.test(m.plain))
  const sd = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('souls dropped meanwhile: confirm refused (LEVELUP_DENY why=souls), level and purse unchanged', cd.line && cd.line.startsWith('[T] LEVELUP_DENY') &&
    cd.kv.why === 'souls' && sd.kv && sd.kv.level === '41' && L.num(sd.kv.souls) === three - 1, (cd.line || '') + ' | ' + (sd.line || ''))
  // 거절한 "올린다" 는 쌓아 둔 점을 비운다 (지금 값으로 창을 다시 띄운다): 다시 셋
  await b.cmd(`/soulstest souls ${three}`, 'SOULS ')
  const again = await b.cmd('/soulstest levelup dex 3', (m) => /^\[T\] LEVELUP_PLUS stat=dex pending=3 /.test(m.plain))
  sc.check('after the refusal the pending points were dropped; three again', again.kv && L.num(again.kv.cost) === three, again.line || '')
  const c3 = await b.cmd('/soulstest levelup confirm', (m) => /^\[T\] LEVELUP(_DENY)? /.test(m.plain) && !/open/.test(m.plain))
  sc.check(`confirm: level 41 -> 44 for exactly ${three}, purse 0`, c3.kv && c3.kv.from === '41' && c3.kv.to === '44' && L.num(c3.kv.cost) === three && c3.kv.souls === '0', c3.line || '')
  await b.cmd('/soulstest levelup cancel', 'LEVELUP', 1500)

  // ── 기사로 다시: 체력 +2, 기력 +1, 정신 +1 ──
  let d = b.p.dialogs.length
  await b.cmd('/souls origin reset ' + b.name, 'ORIGIN_RESET', 4000)
  await b.waitDialog(d, 3000)
  const og = await b.cmd('/soulstest origin knight', 'ORIGIN ')
  sc.check('knight chosen (level 9)', og.kv && og.kv.id === 'knight' && og.kv.level === '9', og.line || '')
  await b.cmd('/soulstest souls 5000', 'SOULS ')
  await b.cmd('/soulstest levelup vig 2', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  await L.sleep(200)
  await b.cmd('/soulstest levelup end', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  const pk = await b.cmd('/soulstest levelup mnd', (m) => /^\[T\] LEVELUP_PLUS/.test(m.plain))
  sc.check('knight: four points from level 9 cost 480 + 500 + 520 + 623 = 2,123', pk.kv && L.num(pk.kv.cost) === 2123, pk.line || '')
  const ck = await b.cmd('/soulstest levelup confirm', (m) => /^\[T\] LEVELUP(_DENY)? /.test(m.plain) && !/open/.test(m.plain))
  sc.check('knight: level 9 -> 13, 5,000 - 2,123 = 2,877 souls left', ck.kv && ck.kv.from === '9' && ck.kv.to === '13' && ck.kv.cost === '2123' && ck.kv.souls === '2877', ck.line || '')
  await b.cmd('/soulstest levelup cancel', 'LEVELUP', 1500)
  await L.sleep(300)
  const st = await b.cmd('/soulstest stats', 'STATS ')
  const info = await b.cmd('/soulstest info', 'INFO ')
  sc.check('knight 13: vigor 17, mind 10, endurance 12, max HP 589', st.kv && st.kv.vig === '17' && st.kv.mnd === '10' && st.kv.end === '12' && st.kv.level === '13' &&
    info.kv && info.kv.maxhp === '589', (st.line || '') + ' | maxhp=' + (info.kv && info.kv.maxhp))
  d = b.p.dialogs.length
  await b.cmd('/soulstest rest', 'REST shown')
  const rest = await b.waitDialog(d, 3000)
  sc.check('after buying a level: rest menu has no "repick"', rest && !b.dialogButtons(rest).repick && b.dialogButtons(rest).levelup, rest ? Object.keys(b.dialogButtons(rest)).join(',') : '창 없음')
  if (rest) b.clickDialog('exit', {}, rest)
  await L.sleep(300)

  // ── 관리자 명령으로 어려움·PvP 켬 ──
  from = b.sys.length
  const sd1 = await b.cmd('/souls settings difficulty hard', (m) => L.translateKeys(m.raw).includes('souls.admin.settings-set'), 3000)
  const sp1 = await b.cmd('/souls settings pvp on', (m) => L.translateKeys(m.raw).includes('souls.admin.settings-set'), 3000)
  await L.sleep(400)
  const s1 = await b.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check('admin: hard + pvp on (via=command, gamerule follows)', sd1.msg && sp1.msg && s1.kv && s1.kv.difficulty === 'hard' && s1.kv.pvp === 'true' &&
    s1.kv.via === 'command' && s1.kv.confirmed === 'true' && s1.kv.gamerule_pvp === 'true', s1.line || '')
  const told = b.sys.slice(from).filter((m) => L.translateKeys(m.raw).includes('souls.start.changed'))
  sc.check('players are told twice (souls.start.changed)', told.length === 2, told.length + '번')
  const logf = L.ENV.serverDir && path.join(L.ENV.serverDir, 'plugins', 'Soulslike', 'settings.log')
  const log = logf && fs.existsSync(logf) ? fs.readFileSync(logf, 'utf8').trim().split('\n') : []
  sc.check('settings.log: both admin changes, by this player, via command', log.some((l) => /difficulty \S+ -> hard/.test(l) && l.includes(b.name) && /via command/.test(l)) &&
    log.some((l) => /pvp off -> on/.test(l) && /via command/.test(l)), log.slice(-2).join(' | '))

  // ── 다시 켠 뒤 볼 값 ──
  const exp = {
    name: b.name,
    stats: { level: st.kv.level, origin: st.kv.origin, souls: st.kv.souls, vig: st.kv.vig, mnd: st.kv.mnd, end: st.kv.end, str: st.kv.str, dex: st.kv.dex, int: st.kv.int },
    maxhp: info.kv.maxhp,
    move: L.num((await b.cmd('/soulstest attr', 'ATTRS ')).kv.movement_speed),
    settings: { difficulty: s1.kv.difficulty, pvp: s1.kv.pvp, rev: s1.kv.rev, confirmed: s1.kv.confirmed },
    kit: { 36: 'redin_guard_sword', 45: 'redin_guard_shield' }
  }
  if (L.ENV.runDir) fs.writeFileSync(path.join(L.ENV.runDir, 'persist.json'), JSON.stringify(exp, null, 1))
  sc.note('다시 켠 뒤 볼 값: ' + JSON.stringify(exp))
  sc.check('no kick during persist scenario', !b.kick, b.kick || '')
})
