// 출신 여섯 (5.1, 5.10, DECISIONS 2026-10-08 "출신은 더 짧고 바로 알아보게 여섯으로"). 봇은 빈털터리로 태어난다 (start.auto-origin).
// 출신마다: 관리자 지우기 (/souls origin reset) → 출신 창의 그 단추 글에 레벨과 능력치 여섯이 그 출신 값으로 보이는가 → 진짜 패킷으로
// 그 단추 → 확인 창 (설명·됨됨이·시작 아이템 그림·능력치 줄) → "이 출신으로" →
//   ORIGIN 줄 (레벨, 지금 주는 시작 아이템 = 장부, 그 체계가 생기면 줄 것 = pending), STATS 의 여섯 값, 최대 HP·스태미나,
//   인벤토리 (주손 = 단축 1, 왼손, 단축 2, 만능 열쇠는 도적만 가방에) 에 그 출신의 시작 아이템만 정확히 하나씩, 무게는 가벼움.
//   창을 다시 열어 다른 출신을 눌러도 거절 (ORIGIN_DENY why=chosen) 되고 아이템이 늘지 않는다.
// 마지막 출신 (기사) 으로: 죽고 일어서기, 다시 접속 뒤에도 시작 아이템이 겹치지 않고 (KIT_LATE 없음), 능력치·최대 HP·이동 속도
// 수정자가 그대로 하나씩 (쌓이지 않는다). 관리자 지우기는 아이템을 거두고 능력치를 10 으로 되돌린다. 끝에 빈털터리로 되돌린다.
'use strict'
const L = require('./lib')

const IDS = ['vig', 'mnd', 'end', 'str', 'dex', 'int']
// 5.1 의 표 (content/origins.yml). atk 는 시작 공격력 (5.1 "시작 때의 값", STATS atk), 마법사의 쇠단지는 왼손 (우클릭 = 왼손, DECISIONS 2026-10-10)
const O = {
  deprived: { level: 1, stats: [10, 10, 10, 10, 10, 10], atk: 81, twohand: false, main: 'gaoler_club', off: 'plank_shield', kit: 'weapon:gaoler_club,weapon:plank_shield', pending: ['armor:prisoner_rags', 'item:estus'] },
  warrior: { level: 8, stats: [11, 9, 12, 16, 10, 9], atk: 123, twohand: true, main: 'gaoler_greatsword', kit: 'weapon:gaoler_greatsword', pending: ['armor:redin_watch_garb', 'item:estus'] },
  thief: { level: 8, stats: [10, 10, 12, 9, 16, 10], atk: 52, twohand: false, main: 'alley_dagger', off: 'parrying_dagger', bag: 'master_key', kit: 'weapon:alley_dagger,weapon:parrying_dagger,item:master_key', pending: ['armor:prisoner_rags', 'item:estus'] },
  archer: { level: 8, stats: [11, 9, 10, 12, 15, 10], atk: 87, twohand: true, main: 'levy_hatchet', hot2: 'wall_shortbow', arrows: 32, kit: 'weapon:levy_hatchet,weapon:wall_shortbow,item:arrows', pending: ['armor:prisoner_rags', 'item:estus'] },
  sorcerer: { level: 8, stats: [9, 13, 9, 9, 11, 16], atk: 52, twohand: false, spell: 121, main: 'alley_dagger', off: 'kiln_pot', kit: 'weapon:alley_dagger,weapon:kiln_pot', pending: ['armor:prisoner_rags', 'spell:ember_toss', 'item:estus'] },
  knight: { level: 9, stats: [15, 9, 11, 13, 11, 9], atk: 72, twohand: false, main: 'redin_guard_sword', off: 'redin_guard_shield', kit: 'weapon:redin_guard_sword,weapon:redin_guard_shield', pending: ['armor:redin_watch_garb', 'item:estus'] }
}
// 5.2 의 곡선 (10 밑은 한 점에 HP −10, 스태미나 −2)
const curve = (pts, x) => {
  const ks = Object.keys(pts).map(Number).sort((a, b) => a - b)
  if (x <= ks[0]) return pts[ks[0]]
  for (let i = 1; i < ks.length; i++) if (x <= ks[i]) return pts[ks[i - 1]] + (pts[ks[i]] - pts[ks[i - 1]]) * (x - ks[i - 1]) / (ks[i] - ks[i - 1])
  return pts[ks[ks.length - 1]]
}
const MAXHP = { 1: 310, 10: 400, 20: 670, 30: 905, 40: 1105, 60: 1305, 99: 1500 }
const STAM = { 1: 82, 10: 100, 20: 130, 30: 150, 40: 165, 60: 180, 99: 200 }
const MOVE = { 10: 0, 20: 0.05, 30: 0.08, 40: 0.10, 60: 0.12, 99: 0.13 }

/** 인벤토리의 souls 아이템: [{slot, id}] (item_name 번역 열쇠 souls.weapon.<id>.name / souls.item.<id>.name 에서 id). */
function soulsItems (b) {
  const out = []
  b.bot.inventory.slots.forEach((it, slot) => {
    if (!it || !Array.isArray(it.components)) return
    const nm = it.components.find((c) => c.type === 'item_name')
    const keys = nm ? L.deepKeys(L.simple(nm.data)) : []
    const k = keys.find((x) => /^souls\.(weapon|item)\./.test(x))
    if (k) out.push({ slot, id: k.split('.')[2], count: it.count })
  })
  return out
}
function kitPlaced (b, o) {
  const items = soulsItems(b)
  const at = (slot) => (items.find((x) => x.slot === slot) || {}).id || null
  const want = [o.main, o.off, o.hot2, o.bag].filter(Boolean)
  // 궁수의 화살은 바닐라 화살 (souls 이름이 없다): 개수만 센다 (o.arrows, 없으면 0)
  const arrows = b.bot.inventory.slots.reduce((n, it) => n + (it && it.name === 'arrow' ? it.count : 0), 0)
  const ok = at(36) === o.main && (o.off ? at(45) === o.off : at(45) === null) && (o.hot2 ? at(37) === o.hot2 : true) &&
    (o.bag ? items.some((x) => x.id === o.bag && x.slot >= 9 && x.slot <= 35) : true) &&
    items.length === want.length && items.every((x) => x.count === 1) && arrows === (o.arrows || 0)
  return { ok, txt: (items.map((x) => `${x.slot}:${x.id}${x.count > 1 ? 'x' + x.count : ''}`).join(' ') || '없음') + (arrows ? ` arrows×${arrows}` : '') }
}
/** 출신 창에서 그 출신 단추의 글 (평문) 과 숫자들. */
function rowOf (raw, id) {
  let label = null
  const walk = (o) => {
    if (label || !o || typeof o !== 'object') return
    if (Array.isArray(o)) { for (const x of o) walk(x); return }
    if (o.label && JSON.stringify(o.action || o).includes(`"b":"${id}"`)) { label = o.label; return }
    for (const v of Object.values(o)) walk(v)
  }
  walk(raw)
  if (!label) return null
  const parts = L.flatten(L.simple(label))
  return { keys: L.deepKeys(label), nums: parts.map((p) => p.text).join('').match(/\d+/g) || [] }
}

L.run('origins_all', async (sc) => {
  let b = await L.connect(sc, { respawn: false })
  await L.sleep(1500)
  const s0 = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('bot is born deprived at join', s0.kv && s0.kv.origin === 'deprived', s0.line || '')

  for (const id of ['deprived', 'warrior', 'thief', 'archer', 'sorcerer', 'knight']) {
    const o = O[id]
    let d = b.p.dialogs.length
    const rs = await b.cmd('/souls origin reset ' + b.name, 'ORIGIN_RESET', 4000)
    let raw = await b.waitDialog(d, 3000)
    if (!sc.check(`${id}: reset opens the origin dialog`, rs.kv && raw && b.dialogId(raw) === 'origin', rs.line || 'ORIGIN_RESET 없음')) continue
    await L.sleep(300)
    sc.check(`${id}: reset took every souls item back`, soulsItems(b).length === 0, kitPlaced(b, { main: null }).txt)
    const row = rowOf(raw, id)
    const want = [o.level, ...o.stats].map(String)
    sc.check(`${id}: its row shows level ${o.level} and stats ${o.stats.join('/')} (name and kit cells are lang keys)`, row &&
      JSON.stringify(row.nums) === JSON.stringify(want) && row.keys.includes(`souls.origin.${id}.name.cell`) && row.keys.includes(`souls.origin.${id}.kit.cell`),
      row ? row.nums.join(',') + ' ' + row.keys.join(',') : '단추 없음')
    d = b.p.dialogs.length
    b.clickDialog(id, {}, raw)
    const conf = await b.waitDialog(d, 3000)
    const ck = conf ? L.deepKeys(conf) : []
    const cj = conf ? JSON.stringify(conf) : ''
    const items = [o.main, o.off, o.hot2, o.bag].filter(Boolean)
    sc.check(`${id}: confirm dialog shows desc, style, stats table and the kit items`, conf && b.dialogId(conf) === 'origin_confirm' &&
      ck.includes(`souls.origin.${id}.desc`) && ck.includes(`souls.origin.${id}.style`) && ck.includes('souls.stat.vig.name.cell') &&
      ck.includes('souls.derived.max-hp.cell') &&
      items.every((w) => cj.includes(w)), ck.filter((k) => k.startsWith('souls.origin')).join(','))
    let from = b.sys.length
    d = b.p.dialogs.length
    b.clickDialog('choose', {}, conf)
    const og = await b.waitT('ORIGIN ', 3000, from)
    sc.check(`${id}: chosen via the dialog (level ${o.level}, kit ${o.kit})`, og && og.kv.id === id && og.kv.level === String(o.level) &&
      og.kv.via === 'dialog' && og.kv.kit === o.kit, og ? og.line : '줄 없음')
    sc.check(`${id}: systems not built yet wait in the ledger (${o.pending.join(', ')})`, og && o.pending.every((x) => (og.kv.pending || '').split(',').includes(x)),
      og ? 'pending=' + og.kv.pending : '')
    await L.sleep(500)
    const st = await b.cmd('/soulstest stats', 'STATS ')
    sc.check(`${id}: stats ${IDS.map((k, i) => k + ' ' + o.stats[i]).join(', ')}, level ${o.level}`, st.kv && st.kv.origin === id &&
      st.kv.level === String(o.level) && IDS.every((k, i) => st.kv[k] === String(o.stats[i])), st.line || '')
    sc.check(`${id}: starting attack ${o.atk}${o.twohand ? ' (two-handed)' : ''}${o.spell ? ', spell power ' + o.spell : ''} as in DESIGN 5.1`, st.kv &&
      Math.round(L.num(st.kv.atk)) === o.atk && st.kv.twohand === String(o.twohand) && (o.spell ? Math.round(L.num(st.kv.spell)) === o.spell : true), st.line || '')
    const info = await b.cmd('/soulstest info', 'INFO ')
    const hp = curve(MAXHP, o.stats[0])
    const stam = curve(STAM, o.stats[2])
    sc.check(`${id}: max HP ${hp} (vigor ${o.stats[0]}), stamina ${stam} (endurance ${o.stats[2]}), full`, info.kv && L.num(info.kv.maxhp) === hp &&
      L.num(info.kv.hp) >= hp - 0.5 && info.kv.stamina === `${stam.toFixed(1)}/${stam.toFixed(0)}`, info.line || '')
    const kp = kitPlaced(b, o)
    sc.check(`${id}: inventory holds exactly its kit (main ${o.main}${o.off ? ', off ' + o.off : ''}${o.hot2 ? ', hotbar 2 ' + o.hot2 : ''}${o.bag ? ', bag ' + o.bag : ''})`, kp.ok, kp.txt)
    const ld = await b.cmd('/soulstest load', 'LOAD ')
    sc.checkCmd(`${id}: starting kit is light`, ld, (r) => r.kv.tier === 'light')
    if (o.arrows) {
      // 궁수의 단궁은 바닐라 활 껍데기: 화살이 있으면 당겨 쏜다 (검토 archer-thief-promises)
      const bow = b.bot.inventory.slots[37]
      sc.check(`${id}: the short bow is a real bow item (vanilla draw and shoot)`, bow && bow.name === 'bow', bow ? bow.name : '없음')
      b.bot.setQuickBarSlot(1)
      await L.sleep(300)
      b.bot.activateItem()
      await L.sleep(1200)
      b.bot.deactivateItem()
      await L.sleep(800)
      const left = b.bot.inventory.slots.reduce((n, it) => n + (it && it.name === 'arrow' ? it.count : 0), 0)
      sc.check(`${id}: drawing and releasing the bow looses an arrow (${o.arrows} -> ${o.arrows - 1})`, left === o.arrows - 1, `화살 ${left}`)
      b.bot.setQuickBarSlot(0)
      await L.sleep(300)
      // 쏜 화살은 주울 수 있다: 뒤의 셈이 흔들리지 않게 땅의 화살을 치우고 지금 개수로 맞춰 둔다
      await b.cmd('/kill @e[type=arrow]', null, 800)
      o.arrows = left
    }
    // 창을 다시 열어 눌러도 다시 고를 수 없다
    d = b.p.dialogs.length
    await b.cmd('/soulstest origin show', null, 800)
    const again = await b.waitDialog(d, 3000)
    if (again) {
      const other = id === 'knight' ? 'warrior' : 'knight'
      d = b.p.dialogs.length
      b.clickDialog(other, {}, again)
      const c2 = await b.waitDialog(d, 3000)
      from = b.sys.length
      if (c2) b.clickDialog('choose', {}, c2)
      const deny = await b.waitT('ORIGIN_DENY', 3000, from)
      await L.sleep(400)
      sc.check(`${id}: re-opened dialog cannot pick again (ORIGIN_DENY why=chosen), no new items`, deny && deny.kv.why === 'chosen' && kitPlaced(b, o).ok,
        (deny ? deny.line : '거절 줄 없음') + ' | ' + kitPlaced(b, o).txt)
      await b.cmd('/soulstest ui', 'UI ')
    } else sc.check(`${id}: origin dialog re-opens on request`, false, '창 없음')
    if (id === 'thief') {
      const op = await b.cmd('/soulstest opens gaol.upper_cell', 'OPENS ')
      sc.checkCmd('thief: the master key opens a key door', op, (r) => r.kv.result === 'true' && r.kv.master === 'true')
    } else {
      const op = await b.cmd('/soulstest opens gaol.upper_cell', 'OPENS ')
      sc.checkCmd(`${id}: no master key, the cell stays locked`, op, (r) => r.kv.result === 'false' && r.kv.master === 'false')
    }
  }

  // ── 기사로: 죽음·일어서기·다시 접속 ──
  const o = O.knight
  const attrs = async () => {
    const r = await b.cmd('/soulstest attr', 'ATTRS ')
    return r
  }
  const moveWant = 0.1 * (1 + curve(MOVE, o.stats[4]))
  const sameState = async (label) => {
    const st = await b.cmd('/soulstest stats', 'STATS ')
    sc.check(`${label}: origin, level and stats kept`, st.kv && st.kv.origin === 'knight' && st.kv.level === '9' && IDS.every((k, i) => st.kv[k] === String(o.stats[i])), st.line || '')
    const kp = kitPlaced(b, o)
    sc.check(`${label}: kit not duplicated (exactly sword + shield)`, kp.ok, kp.txt)
    const a = await attrs()
    sc.check(`${label}: server max_health ${curve(MAXHP, o.stats[0])} with one souls:lvl_vig, movement ${moveWant.toFixed(4)} with one souls:lvl_dex`,
      a.kv && Math.abs(L.num(a.kv.max_health) - curve(MAXHP, o.stats[0])) < 0.01 && a.kv.max_health_mods.split(',').filter((x) => x.startsWith('souls:lvl_vig')).length === 1 &&
      Math.abs(L.num(a.kv.movement_speed) - moveWant) < 1e-4 && (a.kv.movement_speed_mods.match(/souls:lvl_dex/g) || []).length === 1, a.line || '')
    const cm = b.attr('movement_speed')
    sc.check(`${label}: client movement speed ${moveWant.toFixed(4)}`, cm && Math.abs(cm.value - moveWant) < 1e-4, cm ? `${cm.value} ${JSON.stringify(cm.modifiers)}` : '속성 없음')
  }
  await sameState('knight chosen')
  // 죽음 → 일어서기
  let from = b.sys.length
  const r0 = b.p.respawns.length
  await b.cmd('/soulstest kill', 'KILL')
  await L.sleep(1500)
  b.respawn()
  const end = Date.now() + 6000
  while (b.p.respawns.length <= r0 && Date.now() < end) await L.sleep(100)
  await L.sleep(1500)
  sc.check('knight: respawned', b.p.respawns.length > r0 && b.health > 0, `respawn 패킷 ${b.p.respawns.length - r0}, hp ${b.health}`)
  await sameState('after death + respawn')
  sc.check('after death + respawn: no late kit (KIT_LATE)', !b.tLines('KIT_LATE', from).length, b.tLines('KIT_LATE', from).map((x) => x.line).join(' | '))
  const info = await b.cmd('/soulstest info', 'INFO ')
  sc.check('after respawn: health full at the knight max HP (535)', info.kv && L.num(info.kv.maxhp) === 535 && L.num(info.kv.hp) >= 534.5, info.line || '')
  // 다시 접속
  await b.quit()
  await L.sleep(1500)
  b = await L.connect(sc, { respawn: false })
  await L.sleep(2500)
  from = 0
  await sameState('after relog')
  sc.check('after relog: no late kit and no origin dialog', !b.tLines('KIT_LATE').length && !b.p.dialogs.length,
    `KIT_LATE ${b.tLines('KIT_LATE').length}, 창 ${b.p.dialogs.length}`)
  const info2 = await b.cmd('/soulstest info', 'INFO ')
  sc.check('after relog: health not cut to 20 (saved max HP modifier)', info2.kv && L.num(info2.kv.hp) >= 534.5, info2.line || '')

  // ── 관리자 지우기 ──
  let d = b.p.dialogs.length
  const rs = await b.cmd('/souls origin reset ' + b.name, 'ORIGIN_RESET', 4000)
  await b.waitDialog(d, 3000)
  await L.sleep(400)
  const st = await b.cmd('/soulstest stats', 'STATS ')
  const a = await attrs()
  sc.check('op reset: kit taken back (items=2), origin cleared, all stats 10, souls 0, max HP 400',
    rs.kv && rs.kv.items === '2' && soulsItems(b).length === 0 && st.kv && st.kv.origin === '-' && st.kv.level === '1' && st.kv.souls === '0' &&
    a.kv && Math.abs(L.num(a.kv.max_health) - 400) < 0.01, `${rs.line || ''} | ${st.line || ''} | ${a.line || ''}`)
  const log = L.ENV.serverLog && require('fs').existsSync(L.ENV.serverLog) ? require('fs').readFileSync(L.ENV.serverLog, 'utf8') : ''
  sc.check('op reset is logged on the server (INFO "출신 지우기: <name> (by …")', log.includes('출신 지우기: ' + b.name + ' (by '), '')
  // 빈털터리로 되돌린다
  from = b.sys.length
  d = b.p.dialogs.length
  const back = await b.cmd('/soulstest origin deprived', 'ORIGIN ')
  await L.sleep(400)
  sc.check('back to deprived (club + plank shield)', back.kv && back.kv.id === 'deprived' && kitPlaced(b, O.deprived).ok, kitPlaced(b, O.deprived).txt)
  sc.check('no kick during origins scenario', !b.kick, b.kick || '')
})
