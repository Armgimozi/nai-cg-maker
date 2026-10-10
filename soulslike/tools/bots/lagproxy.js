#!/usr/bin/env node
// 지연 프록시 (DESIGN.md 13.3). 봇과 서버 사이에 왕복 지연을 넣는 TCP 중계기.
//   node lagproxy.js --listen 25611 --target 127.0.0.1:25601 --rtt 120 [--jitter 10] [--quiet]
// 왕복 rtt 를 반씩 나눠 양쪽 방향에 건다. jitter 는 한 방향마다 0~jitter ms 를 더 얹되,
// TCP 라서 순서는 절대 바꾸지 않는다 (앞 덩어리보다 먼저 나가지 않는다).
// 모듈로도 쓴다: const px = await require('./lagproxy').startProxy({ listen, host, port, rtt }); px.close()
// 준비되면 표준 출력에 "LAGPROXY ready ..." 한 줄을 남긴다 (run_tests.sh 가 이 줄을 기다린다. --quiet 여도 남긴다).
'use strict'
const net = require('net')

// 한 방향 지연선: 덩어리마다 나갈 시각을 정해 차례대로 내보낸다
class DelayLine {
  constructor (dst, delay, jitter) {
    this.dst = dst
    this.delay = delay
    this.jitter = jitter
    this.q = []
    this.timer = null
    this.lastDue = 0
    this.ended = false
    this.bytes = 0
  }

  push (buf) {
    let due = Date.now() + this.delay + (this.jitter > 0 ? Math.random() * this.jitter : 0)
    if (due < this.lastDue) due = this.lastDue
    this.lastDue = due
    this.q.push({ due, buf })
    this.bytes += buf.length
    this.arm()
  }

  // 원본 쪽이 끝나면 남은 덩어리를 다 보낸 뒤에 닫는다
  end () {
    this.ended = true
    this.arm()
  }

  arm () {
    if (this.timer) return
    if (!this.q.length) {
      if (this.ended && !this.dst.destroyed) this.dst.end()
      return
    }
    const wait = Math.max(0, this.q[0].due - Date.now())
    this.timer = setTimeout(() => {
      this.timer = null
      const now = Date.now()
      while (this.q.length && this.q[0].due <= now) {
        const { buf } = this.q.shift()
        if (!this.dst.destroyed) this.dst.write(buf)
      }
      this.arm()
    }, wait)
  }

  close () {
    if (this.timer) clearTimeout(this.timer)
    this.timer = null
    this.q = []
  }
}

function startProxy ({ listen, host = '127.0.0.1', port, rtt = 0, jitter = 0, quiet = false }) {
  const oneWay = Math.max(0, rtt) / 2
  const conns = new Set()
  const log = (...a) => { if (!quiet) console.log('[lagproxy]', ...a) }
  const server = net.createServer((client) => {
    const upstream = net.connect({ host, port })
    client.setNoDelay(true)
    upstream.setNoDelay(true)
    const up = new DelayLine(upstream, oneWay, jitter)
    const down = new DelayLine(client, oneWay, jitter)
    const c = { client, upstream, up, down }
    conns.add(c)
    log('연결', client.remoteAddress + ':' + client.remotePort, '->', host + ':' + port)
    client.on('data', (b) => up.push(b))
    upstream.on('data', (b) => down.push(b))
    client.on('end', () => up.end())
    upstream.on('end', () => down.end())
    const kill = (why) => {
      if (!conns.has(c)) return
      conns.delete(c)
      up.close()
      down.close()
      client.destroy()
      upstream.destroy()
      log('끊김', why, 'up=' + up.bytes + 'B down=' + down.bytes + 'B')
    }
    // 한쪽이 닫혀도 지연선에 남은 덩어리가 마저 나가도록 조금 기다렸다 끊는다
    const grace = oneWay + jitter + 50
    client.on('close', () => setTimeout(() => kill('client'), grace))
    upstream.on('close', () => setTimeout(() => kill('server'), grace))
    client.on('error', (e) => kill('client error ' + e.code))
    upstream.on('error', (e) => kill('server error ' + e.code))
  })
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(listen, '127.0.0.1', () => {
      console.log(`LAGPROXY ready listen=${listen} target=${host}:${port} rtt=${rtt} jitter=${jitter}`)
      resolve({
        server,
        port: listen,
        rtt,
        close: () => new Promise((r) => {
          for (const c of conns) { c.client.destroy(); c.upstream.destroy(); c.up.close(); c.down.close() }
          conns.clear()
          server.close(() => r())
        })
      })
    })
  })
}

module.exports = { startProxy, DelayLine }

if (require.main === module) {
  const args = process.argv.slice(2)
  const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 && i + 1 < args.length ? args[i + 1] : d }
  const target = opt('target', '127.0.0.1:25601')
  const [host, port] = target.includes(':') ? target.split(':') : ['127.0.0.1', target]
  startProxy({
    listen: +opt('listen', 25611),
    host,
    port: +port,
    rtt: +opt('rtt', 100),
    jitter: +opt('jitter', 0),
    quiet: args.includes('--quiet')
  }).catch((e) => { console.error('LAGPROXY failed', e.message); process.exit(1) })
  const stop = () => process.exit(0)
  process.on('SIGTERM', stop)
  process.on('SIGINT', stop)
}
