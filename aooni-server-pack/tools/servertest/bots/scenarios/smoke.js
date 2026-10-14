'use strict'
// 스모크 시나리오(봇 쪽). 파이썬 쪽은 tools/servertest/scenario_smoke.py.
//  1. 봇들이 접속 → 'joined' 신호
//  2. 파이썬이 RCON 으로 게임을 시작하고 술래를 확인한 뒤 'go' 신호({survivor, oni, chests, ...})
//  3. 생존자 봇이 상자까지 걸어가 열고, 내용물을 읽고(필요하면 모두 가져오고), 결과를 보고
const B = require('../lib/bots')
const link = require('../lib/link')

const cfg = link.config()
let bots = []
link.watchdog(cfg.timeoutMs, () => B.quitAll(bots))

function inMansion (bot) {
  const p = bot.entity.position
  return p.x >= 0 && p.x <= 46 && p.z >= 0 && p.z <= 36 && p.y < -50
}

async function main () {
  bots = await B.connectBots({
    names: cfg.names,
    host: cfg.host,
    port: cfg.port,
    version: cfg.version,
    onLog: (e) => link.send({ t: 'msg', ...e })
  })
  link.signal('joined', { bots: bots.map((b) => ({ name: b.username, pos: B.position(b), version: b.version })) })

  const go = await link.waitFor('go', 90000)
  const s = bots.find((b) => b.username === go.survivor)
  if (!s) throw new Error(`생존자 봇이 없음: ${go.survivor}`)
  await B.waitUntil(() => inMansion(s), 15000, `${s.username} 가 저택으로 이동`)
  await B.sleep(500)
  link.log(`${s.username} 저택 도착 ${JSON.stringify(B.position(s))}`)

  const opened = []
  const failures = []
  const deadline = Date.now() + (go.budgetMs || 120000)
  for (const [x, y, z] of go.chests) {
    if (opened.length >= (go.maxChests || 1)) break
    if (Date.now() > deadline) { failures.push({ pos: [x, y, z], error: '시간 예산 초과로 건너뜀' }); break }
    const t0 = Date.now()
    try {
      await B.gotoReach(s, x, y, z, { timeoutMs: go.chestTimeoutMs || 40000 })
      const walkMs = Date.now() - t0
      const { window, items } = await B.openChestAt(s, x, y, z)
      let taken = []
      try {
        if (go.take) taken = await B.takeAll(s, window)
      } finally {
        s.closeWindow(window)
      }
      opened.push({ pos: [x, y, z], walkMs, botPos: B.position(s), items, taken })
      link.log(`상자 ${x} ${y} ${z} 열기 성공(${walkMs}ms): ${items.map((i) => i.customName || i.name).join(', ') || '(빈 상자)'}`)
    } catch (e) {
      failures.push({ pos: [x, y, z], error: String(e.message || e), botPos: B.position(s) })
      link.log(`상자 ${x} ${y} ${z} 실패: ${e.message || e}`)
      s.pathfinder.stop()
    }
  }
  // 쪽지 확인(loot/check)은 1초마다 돈다
  await B.sleep(go.settleMs || 2500)

  const result = {
    survivor: s.username,
    opened,
    failures,
    inventory: B.inventory(s),
    health: Object.fromEntries(bots.map((b) => [b.username, { health: b.health, food: b.food, pos: B.position(b) }])),
    messages: Object.fromEntries(bots.map((b) => [b.username, b.aooni.log]))
  }
  link.result(result)
}

main()
  .catch((e) => link.fail(e))
  .then(async () => {
    // 파이썬이 RCON 으로 확인을 마칠 때까지(봇이 접속해 있어야 하는 확인) 기다렸다가 나간다
    await link.waitFor('done', 30000).catch(() => {})
    B.quitAll(bots)
    setTimeout(() => process.exit(0), 500)
  })
