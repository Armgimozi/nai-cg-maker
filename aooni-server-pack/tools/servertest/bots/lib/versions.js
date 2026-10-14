'use strict'
// 설치된 mineflayer 가 접속할 수 있는 Minecraft 버전을 JSON 으로 출력한다.
//   node lib/versions.js            → {"mineflayer":"4.39.0","supported":[...],"latest":"..."}
// "supported" = mineflayer 가 시험한 버전 ∩ minecraft-protocol 지원 버전 ∩ minecraft-data 에 있는 버전
const mineflayer = require('mineflayer')
const mp = require('minecraft-protocol')
const md = require('minecraft-data')

const tested = mineflayer.testedVersions || []
const protoOk = new Set(mp.supportedVersions || [])
const supported = tested.filter((v) => protoOk.has(v) && md(v))
const out = {
  mineflayer: require('mineflayer/package.json').version,
  minecraftProtocol: require('minecraft-protocol/package.json').version,
  minecraftData: require('minecraft-data/package.json').version,
  supported,
  latest: supported[supported.length - 1] || null,
  protocol: Object.fromEntries(supported.map((v) => [v, md(v).version.version]))
}
process.stdout.write(JSON.stringify(out) + '\n')
