// 봇 시험 공통 틀 (DESIGN.md 13.2). 시나리오 파일은 이것만 불러 쓴다.
//
// 환경 변수 (run_tests.sh 가 채운다. 혼자 돌릴 때는 NODE_PATH 에 mineflayer 의 node_modules 를 넣는다)
//   MC_HOST, MC_PORT      서버 주소 (지연 시험이면 lagproxy 주소)
//   BOT_NAME              봇 이름 (ops.json 에 미리 올라 있어야 /souls, /soulstest 를 쓴다)
//   RUN_DIR               결과(<시나리오>.json)와 받은 팩을 남길 폴더
//   SERVER_DIR, SERVER_LOG, SOULS_ROOT   서버 폴더, 서버 기록, soulslike 폴더
//   GLYPHS_YML            jar 안 glyphs.yml 을 꺼낸 파일 (그림 글자 이름 → 문자)
//   PACK_SHA1             빌드한 pack.zip 의 SHA-1 (봇이 받은 팩과 견준다)
//   LAG_RTT               지연 프록시를 거칠 때 넣은 왕복 지연 (ms)
//   PACK_LENIENT=1        팩을 못 받아도 받았다고 답한다 (실제 클라이언트는 실패를 답하고 쫓겨난다)
//   SCENARIO_TAG          결과 이름 꼬리표 (lag60 → roll_iframes@lag60)
//   SCENARIO_TIMEOUT      시나리오 하나의 제한 시간 (초)
//
// 봇 요령 (13.2, 12.8): 웅크리기는 player_input 의 shift 깃발, F 는 block_dig 상태 6, 막기는 use_item 과 상태 5,
// 행동 막대는 날 action_bar / system_chat(overlay) 패킷, 위치·속도는 서버에서 잰다 (mineflayer 는 1.21.9+ 속도
// 패킷 배율을 잘못 읽는다). 달리기는 entity_action 의 start_sprinting 을 직접 보낸다.
// 플러그인 시험 줄은 "[T] 이름 열쇠=값 ..." 꼴의 시스템 채팅이다 (TestCommands).
//
// 판정은 셋이다. ok, FAIL, MISS (기능이 아직 없다: 명령어가 없거나 시험 줄이 정의되지 않음). MISS 도 실패로 센다.
'use strict'
const fs = require('fs')
const path = require('path')
const zlib = require('zlib')
const crypto = require('crypto')
const http = require('http')
const https = require('https')

const mineflayer = require('mineflayer')
const nbt = require('prismarine-nbt')

const ENV = {
  host: process.env.MC_HOST || '127.0.0.1',
  port: +(process.env.MC_PORT || 25601),
  name: process.env.BOT_NAME || '',
  runDir: process.env.RUN_DIR || '',
  serverDir: process.env.SERVER_DIR || '',
  serverLog: process.env.SERVER_LOG || '',
  root: process.env.SOULS_ROOT || path.resolve(__dirname, '..', '..'),
  glyphs: process.env.GLYPHS_YML || '',
  packSha1: (process.env.PACK_SHA1 || '').toLowerCase(),
  lagRtt: +(process.env.LAG_RTT || 0),
  lenient: process.env.PACK_LENIENT === '1'
}
const VERSION = '1.21.11'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// ─── 결과 ───────────────────────────────────────────────

class Scenario {
  constructor (name) {
    this.name = name
    this.results = []
    this.bots = []
    this.t0 = Date.now()
  }

  stamp () { return ((Date.now() - this.t0) / 1000).toFixed(1).padStart(5) }

  /** 판정 하나. 돌려주는 값은 cond 그대로라 이어서 쓸 수 있다. */
  check (id, cond, info = '') {
    const ok = !!cond
    this.results.push({ id, status: ok ? 'ok' : 'FAIL', info: String(info || '') })
    console.log(`${this.stamp()}  ${ok ? 'ok  ' : 'FAIL'}  ${id}${info ? '  — ' + info : ''}`)
    return ok
  }

  /** 기능이 아직 없어서 볼 수 없는 판정. */
  miss (id, info = '') {
    this.results.push({ id, status: 'MISS', info: String(info || '') })
    console.log(`${this.stamp()}  MISS  ${id}${info ? '  — ' + info : ''}`)
    return false
  }

  /** 명령어 응답을 보고 판정한다: 명령어가 없으면 MISS, 답이 없으면 FAIL, 있으면 pred. */
  checkCmd (id, r, pred, info) {
    if (!r || r.timeout) return this.check(id, false, '답 없음' + (r && r.cmd ? ' (' + r.cmd + ')' : ''))
    if (r.missing) return this.miss(id, '명령어 없음: ' + r.cmd)
    let ok = false
    try { ok = pred(r) } catch (e) { ok = false }
    return this.check(id, ok, info !== undefined ? info : r.line)
  }

  note (text) { console.log(`${this.stamp()}  ..    ${text}`) }

  counts () {
    const c = { ok: 0, FAIL: 0, MISS: 0 }
    for (const r of this.results) c[r.status]++
    return c
  }
}

/** 시나리오를 돌린다. 끝나면 봇을 닫고, 결과 JSON 을 남기고, 종료 코드로 알린다 (0 통과, 1 실패, 3 시험 틀 오류). */
async function run (name, fn, { timeout = 240 } = {}) {
  // 같은 시나리오를 지연 프록시로 다시 돌릴 때 결과 이름이 겹치지 않게 꼬리표를 붙인다 (roll_iframes@lag120)
  if (process.env.SCENARIO_TAG) name += '@' + process.env.SCENARIO_TAG
  const sc = new Scenario(name)
  console.log(`=== ${name}  (${ENV.host}:${ENV.port}${ENV.lagRtt ? ', 지연 ' + ENV.lagRtt + 'ms' : ''})`)
  let crashed = null
  const limit = +(process.env.SCENARIO_TIMEOUT || timeout) * 1000
  const guard = new Promise((resolve) => setTimeout(() => resolve('timeout'), limit).unref())
  try {
    const r = await Promise.race([fn(sc).then(() => 'done'), guard])
    if (r === 'timeout') { crashed = 'timeout'; sc.check('scenario finished in time', false, `${limit / 1000}s 안에 끝나지 않았다`) }
  } catch (e) {
    crashed = e
    sc.check('scenario ran without crash', false, (e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : String(e)))
  }
  for (const b of sc.bots) await b.quit().catch(() => {})
  const c = sc.counts()
  const status = c.FAIL || c.MISS ? 'FAIL' : 'PASS'
  console.log(`RESULT ${name} ${status} ok=${c.ok} fail=${c.FAIL} miss=${c.MISS}`)
  if (ENV.runDir) {
    try {
      fs.mkdirSync(path.join(ENV.runDir, 'results'), { recursive: true })
      fs.writeFileSync(path.join(ENV.runDir, 'results', name + '.json'),
        JSON.stringify({ name, status, counts: c, lag: ENV.lagRtt, crashed: crashed ? String(crashed) : null, results: sc.results }, null, 1))
    } catch (e) { console.log('결과 파일을 쓰지 못했다:', e.message) }
  }
  // 3 = 시나리오가 도중에 멈췄다 (예외 또는 시간 초과). 판정을 다 못 했으니 시험 틀 쪽도 의심한다
  process.exit(crashed ? 3 : status === 'PASS' ? 0 : 1)
}

// ─── 글 (NBT 글 요소 → 평문) ───────────────────────────────

// NBT 꼴({type, value})일 때만 펴고, 이미 편 값은 그대로 둔다
function simple (n) {
  if (n == null) return null
  if (typeof n !== 'object') return n
  if (typeof n.type === 'string' && 'value' in n) {
    try { return nbt.simplify(n) } catch (e) { return n }
  }
  return n
}

/** 글 요소를 [{text, color, font, translate, with}] 조각으로 편다. 부모의 색·글꼴을 물려받는다. */
function flatten (c, inh = {}, out = []) {
  if (c == null) return out
  if (typeof c === 'string' || typeof c === 'number' || typeof c === 'boolean') {
    out.push({ text: String(c), color: inh.color, font: inh.font })
    return out
  }
  if (Array.isArray(c)) {
    for (const x of c) flatten(x, inh, out)
    return out
  }
  const style = {
    color: c.color !== undefined ? c.color : inh.color,
    font: c.font !== undefined ? c.font : inh.font,
    shadow: c.shadow_color !== undefined ? c.shadow_color : inh.shadow
  }
  let text = c.text !== undefined ? c.text : c[''] !== undefined ? c[''] : ''
  if (c.translate !== undefined) {
    const args = (c.with || []).map((w) => plain(w))
    text = c.translate + (args.length ? '(' + args.join(',') + ')' : '')
    out.push({ text, translate: c.translate, with: args, color: style.color, font: style.font })
  } else {
    out.push({ text: String(text), color: style.color, font: style.font, shadow: style.shadow })
  }
  if (c.extra) flatten(c.extra, style, out)
  return out
}

const plain = (c) => flatten(simple(c)).map((p) => p.text).join('')

/** "[T] NAME a=1 b=x" → {a:'1', b:'x'} */
function kvOf (line) {
  const o = {}
  if (!line) return o
  for (const tok of line.split(/\s+/)) {
    const i = tok.indexOf('=')
    if (i > 0) o[tok.slice(0, i)] = tok.slice(i + 1)
  }
  return o
}
const num = (v) => (v === undefined || v === null ? NaN : parseFloat(v))

// ─── 봇 ───────────────────────────────────────────────────

const PACK_RESULT = { LOADED: 0, DECLINED: 1, FAILED_DOWNLOAD: 2, ACCEPTED: 3, DOWNLOADED: 4 }

function fetchBuf (url, ms = 20000) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https:') ? https : http
    const req = mod.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume()
        fetchBuf(new URL(res.headers.location, url).toString(), ms).then(resolve, reject)
        return
      }
      if (res.statusCode !== 200) { res.resume(); reject(new Error('HTTP ' + res.statusCode)); return }
      const chunks = []
      res.on('data', (d) => chunks.push(d))
      res.on('end', () => resolve(Buffer.concat(chunks)))
      res.on('error', reject)
    })
    req.setTimeout(ms, () => req.destroy(new Error('시간 초과')))
    req.on('error', reject)
  })
}

const GAMEMODES = ['survival', 'creative', 'adventure', 'spectator']
const modeName = (m) => (typeof m === 'number' ? GAMEMODES[m] || String(m) : String(m))

class Bot {
  constructor (sc, name, opts) {
    this.sc = sc
    this.name = name
    this.opts = opts
    this.sys = [] // 시스템 채팅 {t, plain, parts, raw}
    this.p = {
      login: null,
      respawns: [],
      packs: [],
      packChecks: [],
      titles: [],
      subtitles: [],
      titleTimes: [],
      clearTitles: [],
      actionBars: [],
      xp: [],
      vel: [],
      health: [],
      deaths: [],
      difficulty: [],
      time: [],
      border: [],
      positions: [],
      gameState: [],
      sounds: []
    }
    this.kick = null
    this.ended = false
    this.inputs = { forward: false, backward: false, left: false, right: false, jump: false, shift: false, sprint: false }
  }

  get bot () { return this._bot }
  get id () { return this._bot.entity ? this._bot.entity.id : (this.p.login ? this.p.login.entityId : -1) }

  attach (bot) {
    this._bot = bot
    const c = bot._client
    const now = () => Date.now()
    c.on('login', (d) => {
      const ws = d.worldState || {}
      this.p.login = { t: now(), entityId: d.entityId, world: ws.name, dimension: ws.dimension, gamemode: modeName(ws.gamemode), enableRespawnScreen: d.enableRespawnScreen }
    })
    c.on('respawn', (d) => {
      const ws = d.worldState || {}
      this.p.respawns.push({ t: now(), world: ws.name, gamemode: modeName(ws.gamemode) })
    })
    c.on('add_resource_pack', (d) => this.onPack(d, c.state))
    c.on('set_title_text', (d) => this.p.titles.push({ t: now(), raw: simple(d.text), parts: flatten(simple(d.text)), plain: plain(d.text) }))
    c.on('set_title_subtitle', (d) => this.p.subtitles.push({ t: now(), plain: plain(d.text) }))
    c.on('set_title_time', (d) => this.p.titleTimes.push({ t: now(), fadeIn: d.fadeIn, stay: d.stay, fadeOut: d.fadeOut }))
    c.on('clear_titles', (d) => this.p.clearTitles.push({ t: now(), reset: d.reset }))
    c.on('action_bar', (d) => this.p.actionBars.push({ t: now(), plain: plain(d.text), parts: flatten(simple(d.text)) }))
    c.on('system_chat', (d) => {
      const s = simple(d.content)
      const m = { t: now(), plain: flatten(s).map((x) => x.text).join(''), parts: flatten(s), raw: s }
      if (d.isActionBar) this.p.actionBars.push(m)
      else this.sys.push(m)
    })
    c.on('experience', (d) => this.p.xp.push({ t: now(), bar: d.experienceBar, level: d.level, total: d.totalExperience }))
    c.on('entity_velocity', (d) => {
      if (d.entityId !== this.id) return
      const v = d.velocity
      this.p.vel.push({ t: now(), x: v.x, y: v.y, z: v.z })
    })
    // mineflayer 가 옛 배율로 읽은 속도를 날 값으로 덮는다 (12.8). mineflayer 의 처리기보다 뒤에 돌아야 하므로
    // 플러그인이 다 실린 뒤(spawn)에 단다
    bot.once('spawn', () => {
      c.on('entity_velocity', (d) => {
        if (d.entityId !== this.id || !bot.entity || !bot.entity.velocity) return
        bot.entity.velocity.set(d.velocity.x, d.velocity.y, d.velocity.z)
      })
    })
    c.on('update_health', (d) => this.p.health.push({ t: now(), health: d.health, food: d.food }))
    c.on('death_combat_event', (d) => this.p.deaths.push({ t: now(), playerId: d.playerId, message: plain(d.message), raw: simple(d.message) }))
    c.on('difficulty', (d) => this.p.difficulty.push({ t: now(), difficulty: d.difficulty, locked: d.difficultyLocked }))
    c.on('update_time', (d) => this.p.time.push({ t: now(), age: i64(d.age), time: i64(d.time), ticking: d.tickDayTime }))
    c.on('initialize_world_border', (d) => this.p.border.push({ t: now(), x: d.x, z: d.z, size: d.newDiameter }))
    c.on('position', (d) => this.p.positions.push({ t: now(), x: d.x, y: d.y, z: d.z }))
    c.on('game_state_change', (d) => this.p.gameState.push({ t: now(), reason: d.reason, value: d.gameMode }))
    // 소리: 등록부 번호(soundId) 또는 이름. 이름은 soundName() 으로 푼다
    const snd = (d) => this.p.sounds.push({ t: now(), id: d.sound && d.sound.soundId, name: d.sound && d.sound.data && d.sound.data.soundName, entityId: d.entityId })
    c.on('sound_effect', snd)
    c.on('entity_sound_effect', snd)
    bot.on('kicked', (r) => { this.kick = plain(typeof r === 'string' ? safeJson(r) : r) || String(r) })
    bot.on('end', () => { this.ended = true })
    bot.on('error', (e) => { this.lastError = e })
  }

  // 팩 (10.10): 주소에서 실제로 받아 SHA-1 을 재고, 실제 클라이언트처럼 답한다
  onPack (d, state) {
    const info = { t: Date.now(), state, uuid: d.uuid, url: d.url, hash: String(d.hash || '').toLowerCase(), forced: d.forced, prompt: d.promptMessage ? plain(d.promptMessage) : null }
    this.p.packs.push(info)
    const reply = (result) => {
      if (state !== 'play' || this.ended) return // 설정 단계는 mineflayer 가 이미 답한다
      try { this._bot._client.write('resource_pack_receive', { uuid: d.uuid, result }) } catch (e) {}
    }
    reply(PACK_RESULT.ACCEPTED)
    const job = fetchBuf(d.url).then((buf) => {
      const sha1 = crypto.createHash('sha1').update(buf).digest('hex')
      const r = { ok: true, url: d.url, sha1, size: buf.length, hashMatch: sha1 === info.hash, buf }
      if (ENV.runDir) { try { fs.writeFileSync(path.join(ENV.runDir, 'received-pack.zip'), buf) } catch (e) {} }
      reply(PACK_RESULT.DOWNLOADED)
      reply(r.hashMatch || ENV.lenient ? PACK_RESULT.LOADED : PACK_RESULT.FAILED_DOWNLOAD)
      return r
    }, (e) => {
      reply(ENV.lenient ? PACK_RESULT.LOADED : PACK_RESULT.FAILED_DOWNLOAD)
      return { ok: false, url: d.url, error: e.message }
    })
    this.p.packChecks.push(job)
  }

  /** 시스템 채팅 중 pred 에 맞는 첫 줄을 기다린다 (from 번째부터). */
  async waitSys (pred, ms = 3000, from = 0) {
    const end = Date.now() + ms
    let i = from
    for (;;) {
      for (; i < this.sys.length; i++) if (pred(this.sys[i])) return this.sys[i]
      if (Date.now() > end || this.ended) return null
      await sleep(25)
    }
  }

  /** "[T] PREFIX ..." 줄을 기다린다. */
  async waitT (prefix, ms = 3000, from = 0) {
    const m = await this.waitSys((x) => x.plain.startsWith('[T] ' + prefix), ms, from)
    return m ? { line: m.plain, kv: kvOf(m.plain), t: m.t } : null
  }

  /** from 이후 들어온 "[T] PREFIX" 줄 모두. */
  tLines (prefix, from = 0) {
    return this.sys.slice(from).filter((x) => x.plain.startsWith('[T] ' + prefix)).map((m) => ({ line: m.plain, kv: kvOf(m.plain), t: m.t }))
  }

  /**
   * 명령어를 보내고 답을 기다린다.
   * expect: 기다릴 "[T] " 다음 머리말, 또는 (msg) => bool. 비우면 아무 줄이나.
   * 돌려주는 값: {cmd, line, kv, msg, missing, timeout}
   */
  async cmd (command, expect, ms = 4000) {
    const from = this.sys.length
    const cmd = command.startsWith('/') ? command : '/' + command
    this._bot.chat(cmd)
    const want = typeof expect === 'function' ? expect
      : expect ? (m) => m.plain.startsWith('[T] ' + expect) || m.plain.startsWith(expect) : () => true
    const m = await this.waitSys((x) => want(x) || isUnknownCommand(x), ms, from)
    if (!m) return { cmd, timeout: true }
    if (isUnknownCommand(m) && !want(m)) return { cmd, missing: true, line: m.plain }
    return { cmd, line: m.plain, kv: kvOf(m.plain), msg: m }
  }

  /** 명령어 왕복 시간 (ms). 지연 프록시가 먹는지 본다. */
  async rtt (n = 3) {
    let best = Infinity
    for (let i = 0; i < n; i++) {
      const t = Date.now()
      const r = await this.cmd('/soulstest pos', 'POS', 4000)
      if (r && r.line) best = Math.min(best, Date.now() - t)
      await sleep(80)
    }
    return best
  }

  // ── 입력 ──
  input (o = {}) {
    this.inputs = Object.assign({ forward: false, backward: false, left: false, right: false, jump: false, shift: false, sprint: false }, o)
    this._bot._client.write('player_input', { inputs: this.inputs })
  }

  /** 달리기: 바닐라 클라이언트처럼 entity_action 과 입력 깃발을 함께 보낸다. */
  sprint (on, keys = { forward: true }) {
    if (on) {
      this._bot.setControlState('forward', !!keys.forward)
      this.input(Object.assign({}, keys, { sprint: true }))
      this._bot._client.write('entity_action', { entityId: this.id, actionId: 'start_sprinting', jumpBoost: 0 })
    } else {
      this._bot._client.write('entity_action', { entityId: this.id, actionId: 'stop_sprinting', jumpBoost: 0 })
      this._bot.clearControlStates()
      this.input({})
    }
  }

  /** F (손 바꾸기) = block_dig 상태 6. */
  swap () {
    this._bot._client.write('block_dig', { status: 6, location: { x: 0, y: 0, z: 0 }, face: 0, sequence: 0 })
  }

  /** 우클릭을 누른다 (use_item). 떼기는 release (block_dig 상태 5). */
  use () { this._bot.activateItem() }
  release () { this._bot.deactivateItem() }

  respawn () { this._bot._client.write('client_command', { actionId: 0 }) }

  get health () { return this._bot.health }
  get food () { return this._bot.food }
  lastXp () { return this.p.xp[this.p.xp.length - 1] || null }

  /** 소리 기록 하나의 이름 (minecraft-data 의 소리 표로 번호를 푼다). */
  soundName (s) {
    if (s.name) return String(s.name).replace(/^minecraft:/, '')
    const reg = this._bot.registry
    const byId = reg && reg.sounds
    const e = byId && (byId[s.id] || null)
    return e ? e.name : '#' + s.id
  }
  lastHealth () { return this.p.health[this.p.health.length - 1] || null }

  async quit () {
    if (this.ended) return
    try { this._bot.quit() } catch (e) {}
    const end = Date.now() + 3000
    while (!this.ended && Date.now() < end) await sleep(50)
  }
}

function isUnknownCommand (m) {
  return m.parts.some((p) => p.translate === 'command.unknown.command' || p.translate === 'command.unknown.argument' ||
    p.translate === 'command.expected.separator') || /^Unknown or incomplete command/.test(m.plain)
}

function safeJson (s) { try { return JSON.parse(s) } catch (e) { return s } }

// protodef 의 i64 는 [높은 32비트, 낮은 32비트] 배열이나 BigInt 로 온다
function i64 (v) {
  if (Array.isArray(v)) return v[0] * 4294967296 + (v[1] >>> 0)
  if (typeof v === 'bigint') return Number(v)
  return Number(v)
}

/**
 * 봇 하나를 접속시킨다. 서버가 아직 짓는 중이라 막거나 포트가 닫혀 있으면 잠시 뒤 다시 한다.
 * opts: name, respawn(기본 true), retries(기본 8), host, port
 */
async function connect (sc, opts = {}) {
  const name = opts.name || ENV.name || 'SoulsBot'
  const retries = opts.retries || 8
  let last = null
  for (let attempt = 1; attempt <= retries; attempt++) {
    const b = new Bot(sc, name, opts)
    try {
      await connectOnce(b, opts)
      sc.bots.push(b)
      return b
    } catch (e) {
      last = e
      await b.quit().catch(() => {})
      sc.note(`접속 실패 ${attempt}/${retries}: ${e.message}`)
      if (attempt < retries) await sleep(4000)
    }
  }
  throw new Error('접속하지 못했다: ' + (last && last.message))
}

function connectOnce (b, opts) {
  return new Promise((resolve, reject) => {
    const bot = mineflayer.createBot({
      host: opts.host || ENV.host,
      port: opts.port || ENV.port,
      username: b.name,
      version: VERSION,
      auth: 'offline',
      respawn: opts.respawn !== false,
      hideErrors: true,
      checkTimeoutInterval: 90 * 1000
    })
    b.attach(bot)
    let done = false
    const fail = (why) => { if (!done) { done = true; reject(new Error(why)) } }
    const timer = setTimeout(() => fail('spawn 시간 초과'), opts.spawnTimeout || 45000)
    bot.once('spawn', () => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve(b)
    })
    bot.once('kicked', (r) => { clearTimeout(timer); fail('쫓겨남: ' + (b.kick || r)) })
    bot.once('end', (r) => { clearTimeout(timer); fail('연결 끊김: ' + r) })
    bot.once('error', (e) => { clearTimeout(timer); fail('오류: ' + e.message) })
  })
}

// ─── 파일 (glyphs.yml, zip, png, yml) ──────────────────────

function unescapeYaml (s) {
  return s.replace(/\\U([0-9a-fA-F]{8})|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})|\\(.)/g, (m, u8, u4, x2, ch) => {
    if (u8) return String.fromCodePoint(parseInt(u8, 16))
    if (u4) return String.fromCharCode(parseInt(u4, 16))
    if (x2) return String.fromCharCode(parseInt(x2, 16))
    return { n: '\n', t: '\t', '"': '"', '\\': '\\', '/': '/', 0: '\0' }[ch] ?? ch
  })
}

/** glyphs.yml (gen_pack.py 가 쓴다): 이름 → {char, width, font}. */
function loadGlyphs (file) {
  const f = file || ENV.glyphs || path.join(ENV.root, 'plugin', 'src', 'main', 'resources', 'glyphs.yml')
  if (!f || !fs.existsSync(f)) return null
  const out = {}
  for (const line of fs.readFileSync(f, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z0-9_.-]+):\s*\{(.*)\}\s*$/)
    if (!m) continue
    const body = m[2]
    const ch = body.match(/char:\s*"((?:[^"\\]|\\.)*)"|char:\s*'([^']*)'/)
    const w = body.match(/width:\s*(-?\d+)/)
    const font = body.match(/font:\s*"([^"]*)"|font:\s*'([^']*)'|font:\s*([^,\s}]+)/)
    if (!ch) continue
    out[m[1]] = {
      char: ch[1] !== undefined ? unescapeYaml(ch[1]) : ch[2],
      width: w ? +w[1] : null,
      font: font ? (font[1] || font[2] || font[3]) : 'minecraft:default'
    }
  }
  return out
}

/** 아주 작은 zip 읽개 (정리된 zip, 압축 없음 또는 deflate). */
function readZip (buf) {
  let eocd = -1
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break }
  }
  if (eocd < 0) throw new Error('zip 끝 표시가 없다')
  const count = buf.readUInt16LE(eocd + 10)
  let p = buf.readUInt32LE(eocd + 16)
  const entries = new Map()
  for (let i = 0; i < count; i++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw new Error('zip 목차가 깨졌다')
    const method = buf.readUInt16LE(p + 10)
    const csize = buf.readUInt32LE(p + 20)
    const nlen = buf.readUInt16LE(p + 28)
    const elen = buf.readUInt16LE(p + 30)
    const clen = buf.readUInt16LE(p + 32)
    const lho = buf.readUInt32LE(p + 42)
    const name = buf.toString('utf8', p + 46, p + 46 + nlen)
    entries.set(name, { method, csize, lho })
    p += 46 + nlen + elen + clen
  }
  return {
    names: [...entries.keys()],
    has: (n) => entries.has(n),
    get (n) {
      const e = entries.get(n)
      if (!e) return null
      const nl = buf.readUInt16LE(e.lho + 26)
      const el = buf.readUInt16LE(e.lho + 28)
      const data = buf.subarray(e.lho + 30 + nl + el, e.lho + 30 + nl + el + e.csize)
      return e.method === 0 ? Buffer.from(data) : zlib.inflateRawSync(data)
    },
    json (n) {
      const b = this.get(n)
      return b ? JSON.parse(b.toString('utf8').replace(/^\uFEFF/, '')) : null
    }
  }
}

/** PNG → {w, h, rgba}. 8비트 이하, 비월 PNG (gen_pack 이 쓰는 꼴). */
function decodePng (buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) throw new Error('png 가 아니다')
  let p = 8
  let w, h, depth, ctype, interlace
  let palette = null
  let trns = null
  const idat = []
  while (p < buf.length) {
    const len = buf.readUInt32BE(p)
    const type = buf.toString('ascii', p + 4, p + 8)
    const data = buf.subarray(p + 8, p + 8 + len)
    p += 12 + len
    if (type === 'IHDR') {
      w = data.readUInt32BE(0); h = data.readUInt32BE(4); depth = data[8]; ctype = data[9]; interlace = data[12]
    } else if (type === 'PLTE') palette = data
    else if (type === 'tRNS') trns = data
    else if (type === 'IDAT') idat.push(data)
    else if (type === 'IEND') break
  }
  if (interlace) throw new Error('비월 png 는 읽지 못한다')
  const ch = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ctype]
  const bitsPP = depth * ch
  const bpp = Math.max(1, bitsPP >> 3)
  const stride = Math.ceil(w * bitsPP / 8)
  const raw = zlib.inflateSync(Buffer.concat(idat))
  const img = Buffer.alloc(stride * h)
  let prev = Buffer.alloc(stride)
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)]
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1))
    const cur = img.subarray(y * stride, (y + 1) * stride)
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? cur[x - bpp] : 0
      const b = prev[x]
      const c = x >= bpp ? prev[x - bpp] : 0
      let v = line[x]
      if (f === 1) v += a
      else if (f === 2) v += b
      else if (f === 3) v += (a + b) >> 1
      else if (f === 4) {
        const pp = a + b - c
        const pa = Math.abs(pp - a); const pb = Math.abs(pp - b); const pc = Math.abs(pp - c)
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c
      }
      cur[x] = v & 255
    }
    prev = cur
  }
  const sample = (row, i) => {
    if (depth === 8) return row[i]
    if (depth === 16) return row[i * 2]
    const bit = i * depth
    return (row[bit >> 3] >> (8 - depth - (bit & 7))) & ((1 << depth) - 1)
  }
  const rgba = Buffer.alloc(w * h * 4)
  const scale = depth < 8 ? 255 / ((1 << depth) - 1) : 1
  for (let y = 0; y < h; y++) {
    const row = img.subarray(y * stride, (y + 1) * stride)
    for (let x = 0; x < w; x++) {
      const o = (y * w + x) * 4
      if (ctype === 3) {
        const idx = sample(row, x)
        rgba[o] = palette[idx * 3]; rgba[o + 1] = palette[idx * 3 + 1]; rgba[o + 2] = palette[idx * 3 + 2]
        rgba[o + 3] = trns && idx < trns.length ? trns[idx] : 255
      } else if (ctype === 0 || ctype === 4) {
        const g = Math.round(sample(row, x * ch) * scale)
        rgba[o] = rgba[o + 1] = rgba[o + 2] = g
        rgba[o + 3] = ctype === 4 ? sample(row, x * ch + 1) : 255
      } else {
        rgba[o] = sample(row, x * ch); rgba[o + 1] = sample(row, x * ch + 1); rgba[o + 2] = sample(row, x * ch + 2)
        rgba[o + 3] = ctype === 6 ? sample(row, x * ch + 3) : 255
      }
    }
  }
  return { w, h, rgba }
}

function hsv (r, g, b) {
  const mx = Math.max(r, g, b) / 255; const mn = Math.min(r, g, b) / 255
  const d = mx - mn
  let hh = 0
  if (d > 0) {
    if (mx === r / 255) hh = 60 * (((g - b) / 255 / d) % 6)
    else if (mx === g / 255) hh = 60 * ((b - r) / 255 / d + 2)
    else hh = 60 * ((r - g) / 255 / d + 4)
  }
  if (hh < 0) hh += 360
  return { h: hh, s: mx ? d / mx : 0, v: mx }
}

/** server.properties 같은 "열쇠=값" 파일. */
function readProps (file) {
  const o = {}
  if (!fs.existsSync(file)) return null
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    if (!line || line.startsWith('#') || line.startsWith('!')) continue
    const i = line.indexOf('=')
    if (i > 0) o[line.slice(0, i).trim()] = line.slice(i + 1).trim()
  }
  return o
}

/** 플러그인 config.yml 의 시험 방 가운데 (test-room: {x, y, z}). 못 찾으면 기본값. */
function testRoom () {
  const f = ENV.serverDir && path.join(ENV.serverDir, 'plugins', 'Soulslike', 'config.yml')
  const d = { x: 200, y: 100, z: -200 }
  if (!f || !fs.existsSync(f)) return d
  const m = fs.readFileSync(f, 'utf8').match(/test-room:\s*\{\s*x:\s*(-?\d+),\s*y:\s*(-?\d+),\s*z:\s*(-?\d+)\s*\}/)
  return m ? { x: +m[1], y: +m[2], z: +m[3] } : d
}

module.exports = {
  ENV, VERSION, sleep, run, connect, Scenario, Bot, kvOf, num, plain, flatten, simple,
  loadGlyphs, readZip, decodePng, hsv, readProps, testRoom, fetchBuf
}
