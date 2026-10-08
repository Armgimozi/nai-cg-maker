// 난이도 배율이 실제로 적의 한 대에 듣는가 (5.7, 3.7, 3.9). 시험 서버는 보통·PvP 끔으로 확정되어 있다 (start.auto).
//   1. 난이도 넷 (easy normal hard very_hard) 을 차례로 고르고 (/soulstest settings = 창의 단추와 같은 처리기, via=dialog),
//      원인이 적 (시험 좀비) 인 피해 100 을 방어 고리로 맞는다 (/soulstest hit 100 def). DEF 줄의 원피해가 100 × enemy-damage
//      (0.70 / 1.00 / 1.25 / 1.50) 이고, 받은 피해는 원피해² / (원피해 + 방어력), 클라이언트 체력도 그만큼 준다.
//   2. 술 피해 (souls:magic) 도 같은 배율 뒤 마법 저항으로 준다.
//   3. 바닐라 난이도는 어느 판에서나 normal 이다 (3.9: hard 면 바닐라가 적 피해를 1.5 배 한다). HIT 줄의 diff, INFO 의 difficulty,
//      봇이 받은 difficulty 패킷.
//   4. 확정된 세계에서 바꾸면 접속한 사람에게 "세계 설정이 바뀌었다" (start.changed) 채팅과 부제목이 간다.
// 끝에 보통·PvP 끔으로 되돌린다.
'use strict'
const L = require('./lib')

const MULT = { easy: 0.70, normal: 1.00, hard: 1.25, very_hard: 1.50 }

L.run('difficulty', async (sc) => {
  const b = await L.connect(sc)
  try {
    await body(sc, b)
  } finally {
    if (b && !b.ended) await b.cmd('/soulstest settings normal off', 'SETTINGS', 3000)
  }
})

async function body (sc, b) {
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(400)
  const s0 = await b.cmd('/soulstest settings show', 'SETTINGS ')
  sc.check('starts confirmed normal / pvp off', s0.kv && s0.kv.difficulty === 'normal' && s0.kv.confirmed === 'true', s0.line || '')
  const st = await b.cmd('/soulstest stats', 'STATS ')
  const level = st.kv ? L.num(st.kv.level) : NaN
  const vig = st.kv ? L.num(st.kv.vig) : NaN
  const mnd = st.kv ? L.num(st.kv.mnd) : NaN
  sc.check('deprived level 1 (all 10): defense 36.4, magic resistance 32.4', level === 1 && Math.abs(L.num(st.kv.def) - 36.4) < 0.05 &&
    Math.abs(L.num(st.kv.mres) - 32.4) < 0.05, st.line || '')
  const info = await b.cmd('/soulstest info', 'INFO ')
  const maxhp = info.kv ? L.num(info.kv.maxhp) : 400
  const S = maxhp / 20

  const rows = []
  for (const d of ['easy', 'normal', 'hard', 'very_hard']) {
    let from = b.sys.length
    const set = await b.cmd(`/soulstest settings ${d} off`, (m) => m.plain.startsWith('[T] SETTINGS ') && L.kvOf(m.plain).difficulty === d, 4000)
    sc.check(`${d}: settings confirmed (via=dialog)`, set.kv && set.kv.confirmed === 'true' && set.kv.via === 'dialog', set.line || '')
    // 이미 확정된 세계라 처음 바꾼 easy 도 "바뀌었다" 다
    const ch = await b.waitSys((m) => L.translateKeys(m.raw).includes('souls.start.changed'), 2000, from)
    sc.check(`${d}: players are told the settings changed (souls.start.changed chat)`, !!ch,
      ch ? ch.plain.slice(0, 80) : b.sys.slice(from).map((m) => L.translateKeys(m.raw).join('+') || m.plain.slice(0, 40)).join(' | '))
    await b.cmd('/soulstest heal', 'HEAL')
    await L.sleep(300)
    const hp0 = b.health
    from = b.sys.length
    const hit = await b.cmd('/soulstest hit 100 def', 'HIT ')
    const def = b.tLines('DEF ', from)[0]
    const raw = def ? L.num(def.kv.raw) : NaN
    const want = 100 * MULT[d]
    sc.check(`${d}: enemy hit 100 -> raw ${want.toFixed(0)} (enemy-damage x${MULT[d]})`, def && def.kv.from === 'foe' && Math.abs(raw - want) < 0.01,
      def ? def.line : 'DEF 줄 없음 ' + (hit.line || ''))
    const dv = def ? L.num(def.kv.def) : NaN
    const dealtWant = want * want / (want + dv)
    sc.check(`${d}: dealt = raw^2 / (raw + defense) = ${dealtWant.toFixed(2)}`, hit.kv && Math.abs(L.num(hit.kv.dealt) - dealtWant) < 0.05 &&
      def && Math.abs(L.num(def.kv.dealt) - dealtWant) < 0.05, hit.line || '')
    sc.check(`${d}: vanilla difficulty stays NORMAL (HIT diff)`, hit.kv && hit.kv.diff === 'NORMAL', hit.kv ? 'diff=' + hit.kv.diff : '')
    await L.sleep(300)
    sc.check(`${d}: client health drops by dealt / (maxhp/20)`, Math.abs((hp0 - b.health) - dealtWant / S) < 0.05,
      `hp ${hp0} → ${b.health} (기대 −${(dealtWant / S).toFixed(2)})`)
    // 술 피해: 같은 배율, 그다음 마법 저항
    await b.cmd('/soulstest heal', 'HEAL')
    from = b.sys.length
    const mh = await b.cmd('/soulstest hit 100 type=magic def', 'HIT ')
    const md = b.tLines('DEF ', from)[0]
    sc.check(`${d}: magic hit 100 -> raw ${want.toFixed(0)}, reduced by magic resistance`, md && md.kv.kind === 'magic' && Math.abs(L.num(md.kv.raw) - want) < 0.01 &&
      Math.abs(L.num(md.kv.def) - L.num(st.kv.mres)) < 0.05, md ? md.line : 'DEF 줄 없음 ' + (mh.line || ''))
    rows.push({ d, dealt: def ? L.num(def.kv.dealt) : NaN, txt: `${d} ×${MULT[d]}: raw ${raw.toFixed(1)} dealt ${def ? def.kv.dealt : '?'} / magic ${md ? md.kv.dealt : '?'}` })
  }
  sc.note('적 한 대 100: ' + rows.map((r) => r.txt).join(' · '))
  const rising = rows.length === 4 && rows.every((r, i) => i === 0 || r.dealt > rows[i - 1].dealt)
  sc.check('damage taken rises with difficulty (easy < normal < hard < very hard)', rising, rows.map((r) => r.d + '=' + r.dealt).join(' '))
  const info2 = await b.cmd('/soulstest info', 'INFO ')
  sc.check('INFO: world difficulty NORMAL at very_hard', info2.kv && info2.kv.difficulty === 'NORMAL', info2.kv ? 'difficulty=' + info2.kv.difficulty : '')
  const dp = b.p.difficulty.map((x) => x.difficulty)
  sc.check('client never told a vanilla difficulty other than normal', dp.length > 0 && dp.every((x) => x === 2 || x === 'normal'), dp.join(','))
  // 환경 피해는 난이도를 곱하지 않는다: 원인 없는 피해는 최대 HP / 20 배율만 (DEF 줄 없음)
  await b.cmd('/soulstest heal', 'HEAL')
  let from = b.sys.length
  const env = await b.cmd('/soulstest hit 2 type=none def', 'HIT ')
  sc.check('environment damage (no cause) is not scaled by difficulty: no DEF line', env.kv && !b.tLines('DEF ', from).length, env.line || '')

  // ── 되돌린다 ──
  from = b.sys.length
  await b.cmd('/soulstest settings normal off', 'SETTINGS ')
  await b.cmd('/soulstest heal', 'HEAL')
  const hit = await b.cmd('/soulstest hit 100 def', 'HIT ')
  const def = b.tLines('DEF ', from)[0]
  sc.check('back to normal: raw 100 again', def && Math.abs(L.num(def.kv.raw) - 100) < 0.01, def ? def.line : (hit.line || ''))
  await b.cmd('/soulstest heal', 'HEAL')
  sc.check('no kick during difficulty scenario', !b.kick, b.kick || '')
}
