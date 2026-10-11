// 서버를 다시 켠 뒤 (run_tests.sh 의 두 번째 기동): rings.js 가 남긴 RUN_DIR/rings.json 과 견준다 (9.4, 12.6).
// 낀 반지는 프로필 (플레이어 PDC) 에 있고 2×2 칸은 그 사본이다: 서버를 끄고 켜도 같은 반지가 끼워져 칸에 보이고, 효과가 그대로이고,
// 가방의 반지 수가 같고 (끌 때 바닐라가 2×2 를 떨어뜨리거나 돌려주지 않았다), 땅에 반지가 없다.
'use strict'
const fs = require('fs')
const path = require('path')
const L = require('./lib')

L.run('rings_check', async (sc) => {
  const f = L.ENV.runDir && path.join(L.ENV.runDir, 'rings.json')
  if (!sc.check('rings.json from the first boot', f && fs.existsSync(f), f || 'RUN_DIR 없음')) return
  const exp = JSON.parse(fs.readFileSync(f, 'utf8'))
  const b = await L.connect(sc, { name: exp.name })
  await L.sleep(2500)
  await b.syncInventory()
  const s = (await b.cmd('/soulstest ring show', 'RINGS ')).kv || {}
  const carried = s.inv && s.inv !== '-' ? s.inv.split(',').length : 0
  sc.check(`restart: same rings worn (${exp.r1}, ${exp.r2}) and shown as marked copies in craft slots 1 and 3`, s.r1 === exp.r1 && s.r2 === exp.r2 &&
    s.s1 === exp.r1 + '*' && s.s3 === exp.r2 + '*' && s.s0 === '-' && s.s2 === '-' && s.s4 === '-', JSON.stringify(s))
  sc.check('restart: carried rings unchanged, no strays, nothing on the ground', carried === exp.carried && Number(s.strays) === 0 && Number(s.ground) === 0,
    `carried ${carried} (was ${exp.carried}) strays=${s.strays} ground=${s.ground}`)
  sc.check('restart: client sees the rings in slots 1 and 3', b.ringAt(1) === exp.r1 && b.ringAt(3) === exp.r2, `1=${b.ringAt(1)} 3=${b.ringAt(3)}`)
  sc.check('restart: effect as before (regen)', s.regen === exp.regen, `${s.regen} (was ${exp.regen})`)
  sc.check('no kick after restart', !b.kick, b.kick || '')
})
