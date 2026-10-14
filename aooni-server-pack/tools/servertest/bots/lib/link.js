'use strict'
// Python 오케스트레이터(tools/servertest/botrun.py)와 표준 입출력으로 주고받는 통로.
//
// 노드 → 파이썬 (stdout, 한 줄에 하나, 앞에 '@@'):
//   {t:'rcon', id, cmd}          RCON 명령을 대신 실행해 달라
//   {t:'signal', name, data}     진행 신호(파이썬이 wait_signal 로 기다림)
//   {t:'log', msg}               사람이 볼 로그
//   {t:'msg', ...}               봇이 받은 채팅·액션바·타이틀(실시간)
//   {t:'result', data}           최종 결과
//   {t:'fail', error}            실패
//   {t:'call_result', id, ok, value|error}   driver.js 의 RPC 응답
// 파이썬 → 노드 (stdin, JSON 한 줄):
//   {t:'rcon_result', id, ok, text}
//   {t:'signal', name, data}
//   {t:'call', id, method, args}
// '@@' 가 없는 표준 출력·오류 출력은 그냥 로그로 취급된다.

const readline = require('readline')

const pendingRcon = new Map()
const signals = []                 // 받은 신호(아직 소비 안 된 것)
const signalWaiters = []
const callHandlers = []
let nextId = 1

function send (obj) {
  process.stdout.write('@@' + JSON.stringify(obj) + '\n')
}

const rl = readline.createInterface({ input: process.stdin })
rl.on('line', (line) => {
  let msg
  try { msg = JSON.parse(line) } catch (e) { return }
  if (msg.t === 'rcon_result') {
    const p = pendingRcon.get(msg.id)
    if (p) { pendingRcon.delete(msg.id); msg.ok ? p.resolve(msg.text) : p.reject(new Error(msg.text)) }
  } else if (msg.t === 'signal') {
    const i = signalWaiters.findIndex((w) => w.name === msg.name)
    if (i >= 0) { const w = signalWaiters.splice(i, 1)[0]; w.resolve(msg.data) } else signals.push(msg)
  } else if (msg.t === 'call') {
    for (const h of callHandlers) h(msg)
  }
})
// 파이썬 쪽이 끝나면(stdin 닫힘) 노드도 끝낸다
rl.on('close', () => { setTimeout(() => process.exit(0), 200).unref() })

// 환경 변수로 받은 설정
function config () {
  return {
    host: process.env.AOONI_HOST || '127.0.0.1',
    port: parseInt(process.env.AOONI_PORT || '25565', 10),
    version: process.env.AOONI_VERSION || undefined,
    names: JSON.parse(process.env.AOONI_NAMES || '["AoBot1","AoBot2"]'),
    args: JSON.parse(process.env.AOONI_ARGS || '{}'),
    timeoutMs: parseInt(process.env.AOONI_TIMEOUT_MS || '180000', 10)
  }
}

// RCON 명령(서버 콘솔 권한). 응답 문자열을 돌려준다.
function rcon (cmd, timeoutMs = 20000) {
  const id = nextId++
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pendingRcon.delete(id); reject(new Error(`RCON 시간 초과: ${cmd}`)) }, timeoutMs)
    pendingRcon.set(id, {
      resolve: (v) => { clearTimeout(timer); resolve(v) },
      reject: (e) => { clearTimeout(timer); reject(e) }
    })
    send({ t: 'rcon', id, cmd })
  })
}

function signal (name, data = null) { send({ t: 'signal', name, data }) }

// 파이썬이 보내는 신호를 기다린다.
function waitFor (name, timeoutMs = 60000) {
  const i = signals.findIndex((s) => s.name === name)
  if (i >= 0) return Promise.resolve(signals.splice(i, 1)[0].data)
  return new Promise((resolve, reject) => {
    const w = { name, resolve: null }
    const timer = setTimeout(() => {
      const k = signalWaiters.indexOf(w)
      if (k >= 0) signalWaiters.splice(k, 1)
      reject(new Error(`신호 '${name}' 를 ${timeoutMs}ms 동안 받지 못함`))
    }, timeoutMs)
    w.resolve = (d) => { clearTimeout(timer); resolve(d) }
    signalWaiters.push(w)
  })
}

function log (msg) { send({ t: 'log', msg: String(msg) }) }
function result (data) { send({ t: 'result', data }) }
function fail (err) { send({ t: 'fail', error: String(err && err.stack ? err.stack : err) }) }
function onCall (handler) { callHandlers.push(handler) }

// 전체 시간 제한: 넘으면 실패를 알리고 종료한다(절대 멈춰 있지 않도록).
function watchdog (ms, cleanup) {
  setTimeout(() => {
    fail(new Error(`노드 시나리오 전체 시간 초과(${ms}ms)`))
    try { if (cleanup) cleanup() } catch (e) {}
    setTimeout(() => process.exit(3), 300)
  }, ms).unref()
}

module.exports = { send, config, rcon, signal, waitFor, log, result, fail, onCall, watchdog }
