'use strict'
// 아오오니 저택 실서버 테스트용 mineflayer 봇 도우미 모음.
// 오프라인 모드 서버(online-mode=false)에 이름만으로 접속한다. 모든 대기 함수에는 시간 제한이 있다.

const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')
const nbt = require('prismarine-nbt')

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// 약속(promise)에 시간 제한을 건다. 시간이 지나면 onTimeout() 을 부르고 오류를 던진다.
function withTimeout (promise, ms, label, onTimeout) {
  let timer
  const timeout = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      try { if (onTimeout) onTimeout() } catch (e) {}
      reject(new Error(`시간 초과(${ms}ms): ${label}`))
    }, ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}

// 조건이 참이 될 때까지 기다린다.
async function waitUntil (fn, ms, label = '조건', every = 100) {
  const end = Date.now() + ms
  while (Date.now() < end) {
    if (await fn()) return true
    await sleep(every)
  }
  throw new Error(`시간 초과(${ms}ms): ${label}`)
}

// ---------------------------------------------------------------- 글자 변환
// 채팅 컴포넌트(JSON 문자열 / 1.20.3+ NBT / 일반 객체)를 평문으로.
function toText (bot, x) {
  if (x === undefined || x === null) return ''
  const ChatMessage = require('prismarine-chat')(bot.registry)
  try {
    if (typeof x === 'object' && x.type && x.value !== undefined) return ChatMessage.fromNotch(x).toString()
    if (typeof x === 'string') return ChatMessage.fromNotch(x).toString()
    return new ChatMessage(x).toString()
  } catch (e) {
    return typeof x === 'string' ? x : JSON.stringify(x)
  }
}

function simplifyNbt (x) {
  try { return x && x.type ? nbt.simplify(x) : x } catch (e) { return x }
}

// 아이템 하나를 사람이 읽기 쉬운 객체로: 이름, 개수, 사용자 지정 이름, 설명(lore), custom_data 등
function describeItem (bot, item) {
  if (!item) return null
  const out = { slot: item.slot, name: item.name, count: item.count }
  const cm = item.componentMap
  if (cm && cm.size) {
    out.components = [...cm.keys()]
    if (cm.has('custom_name')) out.customName = toText(bot, cm.get('custom_name').data)
    if (cm.has('item_name')) out.itemName = toText(bot, cm.get('item_name').data)
    if (cm.has('lore')) out.lore = (cm.get('lore').data || []).map((l) => toText(bot, l))
    if (cm.has('custom_data')) out.customData = simplifyNbt(cm.get('custom_data').data)
    if (cm.has('potion_contents')) out.potion = cm.get('potion_contents').data
  } else if (item.nbt) {
    // 1.20.4 이하(NBT 아이템)
    out.nbt = simplifyNbt(item.nbt)
    if (item.customName) out.customName = toText(bot, item.customName)
  }
  return out
}

function describeItems (bot, items) {
  return items.filter(Boolean).map((i) => describeItem(bot, i))
}

// ---------------------------------------------------------------- 접속
// 봇 하나를 만들고 스폰까지 기다린다. bot.aooni.log 에 채팅·액션바·타이틀이 쌓인다.
async function createBot ({ host = '127.0.0.1', port, username, version, timeoutMs = 45000, onLog } = {}) {
  const bot = mineflayer.createBot({
    host,
    port,
    username,
    version,
    auth: 'offline',
    checkTimeoutInterval: 60 * 1000,
    hideErrors: true
  })
  bot.loadPlugin(pathfinder)
  const t0 = Date.now()
  bot.aooni = { log: [], t0, ended: null }
  const push = (kind, text) => {
    const e = { time: +((Date.now() - t0) / 1000).toFixed(2), bot: username, kind, text }
    bot.aooni.log.push(e)
    if (onLog) onLog(e)
  }
  bot.on('messagestr', (text, position) => {
    if (!text || !text.trim()) return
    push(position === 'game_info' ? 'actionbar' : (position || 'chat'), text)
  })
  // 1.20.3+ 는 타이틀이 NBT 라서 원시 패킷을 직접 평문으로 바꾼다
  bot._client.on('set_title_text', (p) => push('title', toText(bot, p.text)))
  bot._client.on('set_title_subtitle', (p) => push('subtitle', toText(bot, p.text)))
  bot.on('kicked', (reason) => push('kicked', toText(bot, reason)))
  bot.on('error', (err) => push('error', String(err && err.message ? err.message : err)))
  bot.on('end', (reason) => { bot.aooni.ended = reason || 'end'; push('end', String(reason || '')) })
  bot.on('death', () => push('death', ''))

  await withTimeout(new Promise((resolve, reject) => {
    bot.once('spawn', resolve)
    bot.once('kicked', (r) => reject(new Error(`${username} 접속 거부: ${toText(bot, r)}`)))
    bot.once('end', (r) => reject(new Error(`${username} 연결 끊김: ${r}`)))
  }), timeoutMs, `${username} 스폰`, () => bot.end())

  // 길찾기 설정: 블록을 부수거나 놓지 않고, 문(옷장)도 열지 않는다
  const mv = new Movements(bot)
  mv.canDig = false
  mv.allow1by1towers = false
  mv.allowParkour = false
  mv.canOpenDoors = false
  mv.scafoldingBlocks = []
  mv.allowSprinting = true
  bot.pathfinder.setMovements(mv)
  bot.pathfinder.thinkTimeout = 10000
  return bot
}

// 여러 봇을 차례로 접속시킨다. names: ['AoBot1', 'AoBot2']
async function connectBots ({ names, host, port, version, timeoutMs = 45000, onLog, staggerMs = 400 }) {
  const bots = []
  for (const username of names) {
    bots.push(await createBot({ host, port, username, version, timeoutMs, onLog }))
    await sleep(staggerMs)
  }
  // 청크가 들어올 시간을 조금 준다
  await waitUntil(() => bots.every((b) => b.entity && b.blockAt(b.entity.position.offset(0, -1, 0))), 15000, '발밑 청크 로드')
  return bots
}

function quitAll (bots) {
  for (const b of bots) { try { b.quit() } catch (e) {} }
}

// ---------------------------------------------------------------- 이동·조작
function position (bot) {
  const p = bot.entity.position
  return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }
}

// (x, y, z) 근처(range 칸 이내)로 걸어간다.
async function goto (bot, x, y, z, { range = 1, timeoutMs = 60000 } = {}) {
  const goal = new goals.GoalNear(x, y, z, range)
  await withTimeout(bot.pathfinder.goto(goal), timeoutMs, `${bot.username} → ${x} ${y} ${z}`, () => bot.pathfinder.stop())
}

// 블록 면이 보이고 손이 닿는 곳까지 간다(상자·버튼용).
// 상자처럼 큰 블록은 GoalLookAtBlock(면이 보이는 자리), 버튼처럼 작은 블록은 그 방식이 자리를 못 찾으므로
// 블록 2칸 안으로만 간다(누를 때는 mineflayer 가 면을 알아서 고른다).
async function gotoReach (bot, x, y, z, { reach = 4, timeoutMs = 60000 } = {}) {
  const pos = new Vec3(x, y, z)
  const eye = bot.entity.position.offset(0, bot.entity.eyeHeight || 1.62, 0)
  if (eye.distanceTo(pos.offset(0.5, 0.5, 0.5)) <= reach - 0.3 && canSee(bot, pos)) return
  const block = bot.blockAt(pos)
  const small = block && /button|lever|pressure_plate|torch|sign|banner|carpet/.test(block.name)
  const label = `${bot.username} → 블록 ${x} ${y} ${z}`
  const stop = () => bot.pathfinder.stop()
  const end = Date.now() + timeoutMs
  if (!small) {
    try {
      await withTimeout(bot.pathfinder.goto(new goals.GoalLookAtBlock(pos, bot.world, { reach })), timeoutMs, label, stop)
      return
    } catch (e) {
      if (!/No path/i.test(String(e && e.message))) throw e
    }
  }
  await withTimeout(bot.pathfinder.goto(new goals.GoalNear(x, y, z, 2)), Math.max(1000, end - Date.now()), label, stop)
}

function canSee (bot, pos) {
  const block = bot.blockAt(pos)
  return !!block && bot.canSeeBlock(block)
}

async function lookAt (bot, x, y, z, force = true) {
  await bot.lookAt(new Vec3(x, y, z), force)
}

function blockAt (bot, x, y, z) {
  const b = bot.blockAt(new Vec3(x, y, z))
  if (!b) throw new Error(`${x} ${y} ${z} 블록 정보가 없음(청크 미로드)`)
  return b
}

// 버튼·레버·문 등을 우클릭한다.
async function activateBlockAt (bot, x, y, z, { timeoutMs = 5000 } = {}) {
  const block = blockAt(bot, x, y, z)
  await bot.lookAt(block.position.offset(0.5, 0.5, 0.5), true)
  await withTimeout(bot.activateBlock(block), timeoutMs, `${bot.username} 블록 누르기 ${x} ${y} ${z}`)
  return block.name
}

// 상자를 연다. { window, items } — 다 쓴 뒤 bot.closeWindow(window) 를 부르거나 closeAfter: true.
async function openChestAt (bot, x, y, z, { timeoutMs = 8000, closeAfter = false } = {}) {
  const block = blockAt(bot, x, y, z)
  if (!/chest|barrel|shulker/.test(block.name)) throw new Error(`${x} ${y} ${z} 는 상자가 아님: ${block.name}`)
  await bot.lookAt(block.position.offset(0.5, 0.5, 0.5), true)
  const window = await withTimeout(bot.openContainer(block), timeoutMs, `${bot.username} 상자 열기 ${x} ${y} ${z}`)
  const items = describeItems(bot, window.containerItems())
  if (closeAfter) { bot.closeWindow(window); return { window: null, items } }
  return { window, items }
}

// 열린 창의 상자 칸 아이템을 모두 Shift+클릭으로 가져온다. 가져온 아이템 목록을 돌려준다.
async function takeAll (bot, window, { timeoutMs = 8000 } = {}) {
  const taken = []
  const end = Date.now() + timeoutMs
  for (const item of window.containerItems()) {
    if (Date.now() > end) throw new Error('takeAll 시간 초과')
    taken.push(describeItem(bot, item))
    await withTimeout(bot.clickWindow(item.slot, 0, 1), 3000, `slot ${item.slot} 가져오기`)
    await sleep(80)
  }
  return taken
}

function inventory (bot) {
  return describeItems(bot, bot.inventory.items())
}

function findItem (bot, match) {
  const test = typeof match === 'function'
    ? match
    : (i) => i.name === match || i.name === String(match).replace('minecraft:', '') ||
        (describeItem(bot, i).customName || '').includes(match)
  return bot.inventory.items().find(test) || null
}

// 아이템을 손(또는 'off-hand' 등)에 든다.
async function equip (bot, match, dest = 'hand') {
  const item = findItem(bot, match)
  if (!item) throw new Error(`${bot.username} 인벤토리에 없음: ${match}`)
  await withTimeout(bot.equip(item, dest), 5000, `${bot.username} equip ${match}`)
  return describeItem(bot, item)
}

// 손에 든 것을 먹거나 마신다.
// mineflayer 는 배가 부르면(food 20) 'Food is full' 로 거절하는데, 이 팩의 빵·스테이크처럼
// food 컴포넌트에 can_always_eat 이 있으면 배불러도 먹을 수 있으므로 그 검사를 잠깐 피한다.
// 또 mineflayer 는 손 아이템 갱신 패킷만 와도 '다 먹었다'고 일찍 끝내므로, 손의 개수가 실제로 줄거나
// 다른 아이템(물약 → 빈 병)으로 바뀔 때까지 기다린다.
async function consume (bot, { timeoutMs = 8000, force = false } = {}) {
  const held = bot.heldItem
  if (!held) throw new Error(`${bot.username}: 손에 든 것이 없음`)
  const { slot, type, count } = held
  const food = held.componentMap && held.componentMap.get('food')
  const always = force || !!(food && food.data && (food.data.canAlwaysEat || food.data.can_always_eat))
  if (always && bot.food >= 20) bot.food = 19      // 다음 체력 패킷이 오면 원래 값으로 돌아온다
  const end = Date.now() + timeoutMs
  await withTimeout(bot.consume(), timeoutMs, `${bot.username} 먹기/마시기`)
  await waitUntil(() => {
    const it = bot.inventory.slots[slot]
    return !it || it.type !== type || it.count < count
  }, Math.max(500, end - Date.now()), `${bot.username} 먹기/마시기 완료`)
}

// 이름으로 찾은 플레이어를 한 번 때린다(가까이 있어야 함).
async function attackPlayer (bot, name) {
  const p = bot.players[name]
  if (!p || !p.entity) throw new Error(`${name} 이(가) 보이지 않음`)
  await bot.lookAt(p.entity.position.offset(0, (p.entity.height || 1.8) * 0.8, 0), true)
  bot.attack(p.entity)
  return bot.entity.position.distanceTo(p.entity.position)
}

// 쫓아가서 때린다(reach 안에 들어오면 한 번 공격).
// 멀리 있을 때 GoalFollow 는 층을 오가는 긴 경로를 잘 못 찾아서, 대상의 현재 위치로 GoalNear 를 여러 번 다시 잡는다.
async function chaseAndAttack (bot, name, { timeoutMs = 30000, reach = 3 } = {}) {
  const end = Date.now() + timeoutMs
  while (Date.now() < end) {
    const p = bot.players[name]
    if (!p || !p.entity) { await sleep(200); continue }
    const d = bot.entity.position.distanceTo(p.entity.position)
    if (d <= reach) { bot.pathfinder.setGoal(null); return attackPlayer(bot, name) }
    const t = p.entity.position
    try {
      await withTimeout(bot.pathfinder.goto(new goals.GoalNear(t.x, t.y, t.z, Math.max(1, reach - 1.5))),
        Math.max(500, Math.min(d > 8 ? 15000 : 3000, end - Date.now())), `${bot.username} → ${name}`,
        () => bot.pathfinder.stop())
    } catch (e) {
      await sleep(150)
    }
  }
  bot.pathfinder.setGoal(null)
  throw new Error(`${bot.username}: ${timeoutMs}ms 안에 ${name} 에게 닿지 못함`)
}

function chat (bot, msg) { bot.chat(msg) }
function command (bot, cmd) { bot.chat(cmd.startsWith('/') ? cmd : '/' + cmd) }

// bot.aooni.log 에서 정규식에 맞는 메시지를 기다린다(이미 받은 것도 확인, sinceIndex 이후).
async function waitForMessage (bot, re, { timeoutMs = 10000, sinceIndex = 0, kinds = null } = {}) {
  const rx = re instanceof RegExp ? re : new RegExp(re)
  let found = null
  await waitUntil(() => {
    found = bot.aooni.log.slice(sinceIndex).find((e) => (!kinds || kinds.includes(e.kind)) && rx.test(e.text))
    return !!found
  }, timeoutMs, `${bot.username} 메시지 /${rx.source}/`)
  return found
}

module.exports = {
  sleep,
  withTimeout,
  waitUntil,
  toText,
  describeItem,
  describeItems,
  createBot,
  connectBots,
  quitAll,
  position,
  goto,
  gotoReach,
  canSee,
  lookAt,
  blockAt,
  activateBlockAt,
  openChestAt,
  takeAll,
  inventory,
  findItem,
  equip,
  consume,
  attackPlayer,
  chaseAndAttack,
  chat,
  command,
  waitForMessage,
  goals,
  Vec3
}
