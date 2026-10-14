'use strict'
// 범용 봇 조종기: 파이썬이 {t:'call', method, args} 를 보내면 봇에게 시키고 결과를 돌려준다.
// 시나리오를 파이썬만으로 쓰고 싶을 때 botrun.NodeScenario(..., script='driver.js') 와 .call() 로 쓴다.
//
//   call('connect')                                    → 이름 목록(AOONI_NAMES)의 봇을 모두 접속
//   call('goto', bot='AoBot1', x=.., y=.., z=.., range=1)
//   call('gotoReach', bot, x, y, z)                    → 블록에 손이 닿는 곳까지
//   call('lookAt', bot, x, y, z)
//   call('activateBlockAt', bot, x, y, z)              → 버튼 누르기
//   call('openChestAt', bot, x, y, z, take=False)      → 아이템 목록(take=True 면 모두 가져옴)
//   call('attackPlayer', bot, target) / call('chaseAndAttack', bot, target, timeoutMs)
//   call('equip', bot, item, dest='hand') / call('consume', bot)
//   call('chat', bot, msg) / call('command', bot, cmd)
//   call('inventory', bot) / call('position', bot)
//   call('messages', bot, since=0)                     → 받은 채팅·액션바·타이틀
//   call('quit')

const B = require('./lib/bots')
const link = require('./lib/link')

const cfg = link.config()
const bots = new Map()

function bot (name) {
  const b = bots.get(name)
  if (!b) throw new Error(`없는 봇: ${name}`)
  return b
}

const methods = {
  async connect () {
    const list = await B.connectBots({
      names: cfg.names,
      host: cfg.host,
      port: cfg.port,
      version: cfg.version,
      onLog: (e) => link.send({ t: 'msg', ...e })
    })
    for (const b of list) bots.set(b.username, b)
    return list.map((b) => ({ name: b.username, pos: B.position(b) }))
  },
  async goto (a) { await B.goto(bot(a.bot), a.x, a.y, a.z, a); return B.position(bot(a.bot)) },
  async gotoReach (a) { await B.gotoReach(bot(a.bot), a.x, a.y, a.z, a); return B.position(bot(a.bot)) },
  async lookAt (a) { await B.lookAt(bot(a.bot), a.x, a.y, a.z); return true },
  async activateBlockAt (a) { return B.activateBlockAt(bot(a.bot), a.x, a.y, a.z, a) },
  async openChestAt (a) {
    const b = bot(a.bot)
    const { window, items } = await B.openChestAt(b, a.x, a.y, a.z, a)
    let taken = []
    try { if (a.take) taken = await B.takeAll(b, window) } finally { b.closeWindow(window) }
    return { items, taken }
  },
  async attackPlayer (a) { return B.attackPlayer(bot(a.bot), a.target) },
  async chaseAndAttack (a) { return B.chaseAndAttack(bot(a.bot), a.target, a) },
  async equip (a) { return B.equip(bot(a.bot), a.item, a.dest || 'hand') },
  async consume (a) { await B.consume(bot(a.bot), a); return true },
  async chat (a) { B.chat(bot(a.bot), a.msg); return true },
  async command (a) { B.command(bot(a.bot), a.cmd); return true },
  async inventory (a) { return B.inventory(bot(a.bot)) },
  async position (a) { return B.position(bot(a.bot)) },
  async health (a) { const b = bot(a.bot); return { health: b.health, food: b.food } },
  async messages (a) { return bot(a.bot).aooni.log.slice(a.since || 0) },
  async quit () { B.quitAll([...bots.values()]); setTimeout(() => process.exit(0), 300); return true }
}

link.onCall(async (msg) => {
  const fn = methods[msg.method]
  try {
    if (!fn) throw new Error(`없는 메서드: ${msg.method}`)
    const value = await fn(msg.args || {})
    link.send({ t: 'call_result', id: msg.id, ok: true, value })
  } catch (e) {
    link.send({ t: 'call_result', id: msg.id, ok: false, error: String(e && e.message ? e.message : e) })
  }
})

link.watchdog(cfg.timeoutMs, () => B.quitAll([...bots.values()]))
link.signal('ready', { names: cfg.names })
