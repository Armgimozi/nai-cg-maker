// 세계를 정한다 (5.7): 처음 들어온 사람이 난이도 넷 (단추) 과 PvP (체크 칸) 를 고른다. 봇은 실제 클라이언트처럼
// custom_click_action (id souls:ui, 단추의 additions + 입력 값) 을 보낸다.
//   1. 시험 서버는 start.auto 로 보통·PvP 끔이 확정되어 있다 (다른 시나리오가 창에 막히지 않게).
//   2. 설정을 지우고 다시 들어오면: 창을 띄우기 전에 잠정 기본값을 먼저 적고 (confirmed=false via=default), 창이 온다.
//      창은 제목·본문·단추가 번역 열쇠이고, 단추 다섯 (난이도 넷 + 나중에), 체크 칸 pvp.
//   3. "어려움" + PvP 켬을 누르면 확정된다 (confirmed=true via=dialog), 바닐라 규칙 pvp 도 켜진다. 같은 창의 단추를 다시
//      보내면 낡은 것으로 버린다 (UI_STALE).
//   4. 설정을 지우고 다시 들어와 Esc (나가기 동작) 를 누르면 잠정 그대로 (confirmed=false), 화톳불 휴식 창에 "세계를 정한다" 단추가
//      생기고, 거기서 다시 연 창으로 보통·끔을 확정한다.
//   5. 바뀐 설정은 세계 PDC 와 souls-state.yml 에 남는다 (/souls check 의 world settings 줄).
// 끝에 보통·PvP 끔으로 되돌린다 (뒤 시나리오를 위해).
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

async function settings (b) {
  const r = await b.cmd('/soulstest settings show', 'SETTINGS ')
  return r.kv || {}
}

async function rejoin (sc, b) {
  await b.quit()
  await L.sleep(1500)
  const n = await L.connect(sc)
  return n
}

L.run('start', async (sc) => {
  let b = await L.connect(sc)
  try {
    await body(sc, b, (n) => { b = n })
  } finally {
    // 무슨 일이 있어도 보통·PvP 끔 확정으로 되돌린다 (뒤 시나리오가 창에 막히지 않게)
    if (b && !b.ended) await b.cmd('/soulstest settings normal off', 'SETTINGS', 3000)
  }
})

async function body (sc, b, swap) {
  await L.sleep(1500)

  const s0 = await settings(b)
  sc.check('test server starts with confirmed normal / pvp off (start.auto)', s0.difficulty === 'normal' && s0.pvp === 'false' && s0.confirmed === 'true',
    JSON.stringify(s0))

  // ── 지우고 다시 들어오면 창 ──
  await b.cmd('/soulstest settings clear', 'SETTINGS cleared')
  b = await rejoin(sc, b)
  swap(b)
  const d0 = 0 // 새 봇: 창이 접속하는 동안 (땅을 기다리는 사이) 이미 왔을 수 있다
  const st = await b.waitT('START_DIALOG ', 15000)
  sc.check('fresh world: settings dialog opens for the first player (START_DIALOG reason=fresh)', st && st.kv.reason === 'fresh', st ? st.line : '줄 없음')
  const raw = await b.waitDialog(d0, 4000)
  if (!sc.check('show_dialog received', !!raw)) return
  const btn = b.dialogButtons(raw)
  sc.check('dialog id settings with four difficulty buttons + later', b.dialogId(raw) === 'settings' &&
    ['easy', 'normal', 'hard', 'very_hard', 'exit'].every((k) => btn[k]), Object.keys(btn).join(','))
  const keys = L.deepKeys(raw)
  sc.check('title, body, buttons and checkbox are translatable', ['souls.start.title', 'souls.start.body', 'souls.start.choice', 'souls.start.pvp', 'souls.difficulty.hard.name'].every((k) => keys.includes(k)),
    keys.filter((k) => k.startsWith('souls.')).join(','))
  sc.check('pvp checkbox input (boolean, starts off)', JSON.stringify(raw).includes('"pvp"'), JSON.stringify(raw.inputs || '').slice(0, 160))
  const p0 = await settings(b)
  sc.check('provisional default written before the answer (confirmed=false via=default)', p0.confirmed === 'false' && p0.via === 'default' && p0.difficulty === 'normal', JSON.stringify(p0))
  // 창이 떠 있는 동안 구르기 키는 막힌다 (창이 웅크리기를 뗀다)
  {
    const from = b.sys.length
    await b.tapSneak({})
    const sk = await b.waitT('ROLL_TAP_SKIP', 1500, from)
    sc.check('sneak tap while the dialog is open does not roll (why=dialog)', sk && sk.kv.why === 'dialog' && !b.tLines('ROLL ', from).length, sk ? sk.line : '줄 없음')
  }

  // ── 어려움 + PvP 켬 ──
  let from = b.sys.length
  sc.check('click "hard" with pvp on (custom_click_action)', b.clickDialog('hard', { pvp: true }, raw))
  const ck = await b.waitT('UI click', 3000, from)
  sc.check('server took the click (UI click d=settings b=hard)', ck && ck.kv.d === 'settings' && ck.kv.b === 'hard', ck ? ck.line : '줄 없음')
  await L.sleep(400)
  const s1 = await settings(b)
  sc.check('settings confirmed: hard, pvp on (via=dialog)', s1.difficulty === 'hard' && s1.pvp === 'true' && s1.confirmed === 'true' && s1.via === 'dialog', JSON.stringify(s1))
  sc.check('vanilla pvp gamerule follows the settings', s1.gamerule_pvp === 'true', 'gamerule_pvp=' + s1.gamerule_pvp)
  from = b.sys.length
  b.clickDialog('easy', { pvp: false }, raw)
  const stale = await b.waitT('UI_STALE', 2000, from)
  sc.check('re-sending a button of a closed dialog is ignored (UI_STALE)', !!stale, stale ? stale.line : '줄 없음')
  const s1b = await settings(b)
  sc.check('stale click changed nothing', s1b.difficulty === 'hard' && s1b.pvp === 'true', JSON.stringify(s1b))

  // ── 지우고 Esc ── 잠정 그대로, 휴식 창에서 다시
  await b.cmd('/soulstest settings clear', 'SETTINGS cleared')
  b = await rejoin(sc, b)
  swap(b)
  const d1 = 0
  await b.waitT('START_DIALOG ', 15000)
  const raw2 = await b.waitDialog(d1, 4000)
  from = b.sys.length
  sc.check('Esc = exit action of the settings dialog', raw2 && b.clickDialog('exit', { pvp: true }, raw2),
    raw2 ? '' : `창 ${b.p.dialogs.length}개, 시험 줄 ${b.tLines('').map((x) => x.line.split(' ').slice(0, 3).join(' ')).join(' | ').slice(0, 300)}, 오류 ${b.lastError ? b.lastError.message : '-'}, 패킷 ${b.pkts.filter((n) => !/map_chunk|entity|light|sound|time|keep_alive|level_particles|block|bundle|action_bar|boss_bar/.test(n)).slice(-40).join(',')}`)
  await b.waitT('UI click', 3000, from)
  await L.sleep(600)
  const s2 = await settings(b)
  sc.check('Esc keeps the provisional settings (confirmed=false, default difficulty, pvp off)', s2.confirmed === 'false' && s2.difficulty === 'normal' && s2.pvp === 'false', JSON.stringify(s2))
  const orig = b.tLines('ORIGIN', from)
  sc.check('after Esc the born player is not asked for an origin', !orig.some((x) => x.line.startsWith('[T] ORIGIN_REOPEN')), orig.map((x) => x.line).join(' | '))

  const d2 = b.p.dialogs.length
  from = b.sys.length
  await b.cmd('/soulstest rest', 'REST shown')
  const rest = await b.waitDialog(d2, 3000)
  const rb = rest ? b.dialogButtons(rest) : {}
  sc.check('bonfire rest menu offers "settings" while provisional', !!rb.settings && !!rb.levelup && !!rb.stats, Object.keys(rb).join(','))
  const d3 = b.p.dialogs.length
  b.clickDialog('settings', {}, rest)
  const raw3 = await b.waitDialog(d3, 3000)
  sc.check('rest menu "settings" reopens the settings dialog', raw3 && b.dialogId(raw3) === 'settings', raw3 ? b.dialogId(raw3) : '창 없음')
  if (raw3) {
    b.clickDialog('normal', { pvp: false }, raw3)
    await L.sleep(600)
  }
  const s3 = await settings(b)
  sc.check('confirmed from the rest menu: normal, pvp off', s3.difficulty === 'normal' && s3.pvp === 'false' && s3.confirmed === 'true', JSON.stringify(s3))
  const d4 = b.p.dialogs.length
  await b.cmd('/soulstest rest', 'REST shown')
  const rest2 = await b.waitDialog(d4, 3000)
  sc.check('confirmed: rest menu no longer offers "settings"', rest2 && !b.dialogButtons(rest2).settings, rest2 ? Object.keys(b.dialogButtons(rest2)).join(',') : '창 없음')
  if (rest2) b.clickDialog('exit', {}, rest2)

  // ── 남는 곳 ──
  const ck2 = await b.cmd('/souls check', (m) => m.plain.includes('world settings'), 6000)
  sc.check('/souls check shows the world settings', ck2.line && /difficulty=normal pvp=false confirmed=true/.test(ck2.line), ck2.line || '')
  const sd = L.ENV.serverDir && path.join(L.ENV.serverDir, 'plugins', 'Soulslike', 'souls-state.yml')
  const yml = sd && fs.existsSync(sd) ? fs.readFileSync(sd, 'utf8') : ''
  sc.check('souls-state.yml keeps a copy with the world UID', /world-uid:/.test(yml) && /\\"difficulty\\":\\"normal\\"|"difficulty":"normal"/.test(yml), yml.slice(0, 160))
  const log = L.ENV.serverDir && path.join(L.ENV.serverDir, 'plugins', 'Soulslike', 'settings.log')
  const lines = log && fs.existsSync(log) ? fs.readFileSync(log, 'utf8').trim().split('\n') : []
  sc.check('settings.log records each change', lines.some((l) => /difficulty normal -> hard, pvp off -> on/.test(l)) && lines.some((l) => /via dialog/.test(l)), lines.slice(-3).join(' | '))
  sc.check('no kick during start scenario', !b.kick, b.kick || '')
}
