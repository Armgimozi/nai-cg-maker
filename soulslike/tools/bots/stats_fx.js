// 능력치 여섯이 바꾸는 둘씩을 실제 값으로 잰다 (5.2, 5.8, 3.2, 3.7, 10.2). 봇은 빈털터리 (모두 10, 레벨 1) 로 태어나고,
// 능력치는 시험 명령 (/soulstest stat, 레벨업과 같은 AttributeApplier·Load·Stamina.grow 길) 으로 바꾼다. 값마다 5.2 표의
// 10 / 20 / 30 / 40 / 60 / 99 를 그대로 견준다 (곡선 자체는 JUnit StatCurvesTest 가 본다. 여기서는 게임 안에 실제로 걸리는지).
//   체력  최대 HP: 서버 (INFO maxhp) 와 클라이언트가 받은 속성 (max_health 값, souls:lvl_vig 수정자 하나), 하트는 늘 10 (scale 20),
//         HUD HP 막대 길이 (최대 HP × 0.17). 방어력: STATS def = 20 + 0.4 × 레벨 + 체력 몫, 적의 한 대가 실제로 그만큼 준다.
//   정신  최대 마나 (STATS mana, HUD 마나 막대 길이 = × 0.8), 기억 칸. 마법 저항: STATS mres, 술 피해 (souls:magic) 가 그만큼 준다.
//   기력  최대 스태미나 (STAMINA max, HUD 막대 × 0.65), 회복: 스태미나를 비운 뒤 두 번 읽어 틱당 회복을 잰다 (2.2 × 기력 배율 × 무게).
//   근력  공격력 (STATS atk: 곤봉 C 한손, 왼손을 비우면 양손 ×1.5), 장비 무게 한도 (LOAD cap) 와 단계 (무기를 잔뜩 들면 무거움 →
//         근력을 올리면 보통: 걷기 속성 ×0.92 → ×1.00, 스태미나 회복 ×0.85 → ×0.95, 구르기 종류, "짐이 가벼워졌다" 알림).
//   민첩  이동 속도: 클라이언트가 받은 movement_speed 값 (souls:lvl_dex 수정자 하나). 공격 속도: STATS aspd (그 무기의 민첩 보정 계수 ×
//         공격 속도 몫) 가 서버의 attack_speed 속성에 걸린다: 든 무기 분류의 기본 (20 / 한 주기 틱, souls:weapon_speed) × aspd
//         (souls:lvl_dex). 곤봉 (망치, 18틱) 은 1.111, 단도 (10틱) 는 2.0.
//   근력  적을 치는 다리 (3.7): 시험 좀비를 곤봉으로 치면 PVE_HIT dealt = 공격력 × (0.2 + 0.8 × 대기²) × 0.09, 근력 40 이 10 보다 세다.
//   지능  상태 이상 저항: 해로운 효과 길이 (독 200틱 → × (1 − 저항), 10틱 밑이면 걸리지 않는다), 불붙음, 실제 투척 물약 (POTION_SPLASH).
//         술 세기: 쇠단지 (지능 C, 필요 지능 12) 를 들면 STATS spell (술은 M5. 지금은 이 배율이 API 값이다).
// 끝에 모두 10 으로 되돌리고 속성이 처음 값인지 (수정자가 쌓이지 않았는지) 본다.
'use strict'
const L = require('./lib')

const PTS = [10, 20, 30, 40, 60, 99]
// 5.2 의 표 (config.yml 기본값)
const T = {
  maxhp: [400, 670, 905, 1105, 1305, 1500],
  vigDef: [16, 26, 33, 38, 42, 46],
  mana: [60, 95, 125, 145, 170, 200],
  magDef: [12, 26, 36, 44, 52, 58],
  slots: [1, 3, 5, 5, 5, 5],
  stamina: [100, 130, 150, 165, 180, 200],
  regen: [1.0, 1.15, 1.24, 1.30, 1.36, 1.40],
  cap: [40, 54, 66, 76, 88, 100],
  scaling: [0.13, 0.35, 0.52, 0.68, 0.80, 1.0],
  move: [0, 0.05, 0.08, 0.10, 0.12, 0.13],
  aspd: [0, 0.10, 0.17, 0.22, 0.26, 0.30],
  resist: [0, 0.10, 0.18, 0.24, 0.30, 0.35]
}
const level = (v) => 1 + (v - 10) // 나머지 다섯이 10 일 때
const hudLen = (max, px) => Math.max(24, Math.min(190, Math.round(max * px)))

/** 클라이언트가 받은 속성 (lib Bot.attr: 바탕값과 수정자로 셈한 값). */
const attr = (b, name) => b.attr(name)
function mods (a, idPart) {
  if (!a || !Array.isArray(a.modifiers)) return []
  return a.modifiers.filter((m) => m.id.includes(idPart))
}
/** 서버 쪽 속성 (/soulstest attr): {max_health, movement_speed, attack_speed, mods: {이름: [열쇠…]}} */
async function srvAttr (b) {
  const r = await b.cmd('/soulstest attr', 'ATTRS ')
  if (!r.kv) return null
  const out = { line: r.line, mods: {} }
  for (const n of ['max_health', 'movement_speed', 'attack_speed']) {
    out[n] = L.num(r.kv[n])
    const m = r.kv[n + '_mods']
    out.mods[n] = !m || m === '-' ? [] : m.split(',').map((x) => x.replace(/:[-0-9.]+$/, ''))
  }
  return out
}
const count = (arr, k) => arr.filter((x) => x === k).length

async function waitAttr (b, name, pred, ms = 2500) {
  const end = Date.now() + ms
  for (;;) {
    const a = attr(b, name)
    if (a && pred(a.value)) return a
    if (Date.now() > end) return a
    await L.sleep(50)
  }
}

L.run('stats_fx', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(400)
  await b.ground(3000)
  const stat = (id, v) => b.cmd(`/soulstest stat ${id} ${v}`, 'STAT ')
  const stats = () => b.cmd('/soulstest stats', 'STATS ')
  const s0 = await stats()
  if (!sc.checkCmd('starts as deprived, all 10', s0, (r) => r.kv.origin === 'deprived' && r.kv.level === '1' && r.kv.weapon === 'gaoler_club')) return
  const a0 = attr(b, 'max_health'); const m0 = attr(b, 'movement_speed'); const as0 = attr(b, 'attack_speed')
  sc.note(`처음 속성: max_health ${a0 && a0.value} movement_speed ${m0 && m0.value} attack_speed ${as0 && as0.value}, 받은 속성 ${Object.keys(b.bot.entity.attributes || {}).join(',')}`)

  // ── 체력: 최대 HP + 방어력 ──
  for (let i = 0; i < PTS.length; i++) {
    const v = PTS[i]
    await stat('vig', v)
    const info = await b.cmd('/soulstest info', 'INFO ')
    const want = T.maxhp[i]
    const sa = await srvAttr(b)
    sc.check(`vigor ${v}: max HP ${want} (server attribute with one souls:lvl_vig modifier, INFO maxhp)`, info.kv && L.num(info.kv.maxhp) === want &&
      sa && Math.abs(sa.max_health - want) < 0.01 && count(sa.mods.max_health, 'souls:lvl_vig') === 1 && sa.mods.max_health.length === 1,
      `${info.kv && info.kv.maxhp} | ${sa ? sa.line : '-'}`)
    // 하트는 늘 10개: 서버가 클라이언트에 보내는 max_health 는 하트 배율 (scale 20) 로 바꿔 넣은 값이다 (Paper 의 health scale)
    const ca = await waitAttr(b, 'max_health', (x) => Math.abs(x - 20) < 0.01)
    const hh = b.lastHealth()
    sc.check(`vigor ${v}: client still sees 10 hearts (max_health 20, scale 20, health <= 20)`, info.kv.scale === '20' && ca && Math.abs(ca.value - 20) < 0.01 &&
      hh && hh.health <= 20.001, `client max_health ${ca && ca.value}, health ${hh && hh.health}`)
    const st = await stats()
    const def = 20 + 0.4 * level(v) + T.vigDef[i]
    sc.check(`vigor ${v}: defense 20 + 0.4 x level ${level(v)} + ${T.vigDef[i]} = ${def.toFixed(1)}`, st.kv && Math.abs(L.num(st.kv.def) - def) < 0.05, st.line || '')
    const hud = await b.cmd('/soulstest hud', 'HUD ')
    const len = hud.kv ? L.num(hud.kv.hp.split('/')[1]) : NaN
    sc.check(`vigor ${v}: HUD HP bar ${hudLen(want, 0.17)} px long`, Math.abs(len - hudLen(want, 0.17)) <= 1, hud.line || '')
    if (v === 10 || v === 40) {
      await b.cmd('/soulstest heal', 'HEAL')
      const from = b.sys.length
      const h = await b.cmd('/soulstest hit 200 def', 'HIT ')
      const d = b.tLines('DEF ', from)[0]
      const dealt = 200 * 200 / (200 + def)
      sc.check(`vigor ${v}: an enemy hit of 200 deals ${dealt.toFixed(1)} (reduced by defense ${def.toFixed(1)})`, d && Math.abs(L.num(d.kv.def) - def) < 0.05 &&
        h.kv && Math.abs(L.num(h.kv.dealt) - dealt) < 0.05, (d ? d.line : 'DEF 없음') + ' | ' + (h.line || ''))
    }
  }
  await stat('vig', 10)
  await b.cmd('/soulstest heal', 'HEAL')

  // ── 정신: 최대 마나 + 마법 저항 ──
  for (let i = 0; i < PTS.length; i++) {
    const v = PTS[i]
    await stat('mnd', v)
    const st = await stats()
    const mres = 20 + 0.4 * level(v) + T.magDef[i]
    sc.check(`mind ${v}: max mana ${T.mana[i]}, magic resistance ${mres.toFixed(1)}, memory slots ${T.slots[i]}`, st.kv && L.num(st.kv.mana) === T.mana[i] &&
      Math.abs(L.num(st.kv.mres) - mres) < 0.05 && L.num(st.kv.slots) === T.slots[i], st.line || '')
    const hud = await b.cmd('/soulstest hud', 'HUD ')
    const len = hud.kv ? L.num(hud.kv.fp.split('/')[1]) : NaN
    sc.check(`mind ${v}: HUD mana bar ${hudLen(T.mana[i], 0.8)} px long`, Math.abs(len - hudLen(T.mana[i], 0.8)) <= 1, hud.line || '')
    if (v === 10 || v === 40) {
      await b.cmd('/soulstest heal', 'HEAL')
      const from = b.sys.length
      const h = await b.cmd('/soulstest hit 200 type=magic def', 'HIT ')
      const d = b.tLines('DEF ', from)[0]
      const dealt = 200 * 200 / (200 + mres)
      sc.check(`mind ${v}: a magic hit of 200 (souls:magic) deals ${dealt.toFixed(1)}`, d && d.kv.kind === 'magic' && Math.abs(L.num(d.kv.def) - mres) < 0.05 &&
        h.kv && Math.abs(L.num(h.kv.dealt) - dealt) < 0.05, (d ? d.line : 'DEF 없음') + ' | ' + (h.line || ''))
    }
  }
  await stat('mnd', 10)

  // ── 기력: 최대 스태미나 + 회복 ──
  const regenRate = async () => {
    await b.cmd('/soulstest stamina set 5', 'STAMINA')
    await L.sleep(800) // 회복 지연 12틱 뒤
    const r1 = await b.cmd('/soulstest stamina', 'STAMINA')
    await L.sleep(500)
    const r2 = await b.cmd('/soulstest stamina', 'STAMINA')
    if (!r1.kv || !r2.kv) return NaN
    const dt = L.num(r2.kv.t) - L.num(r1.kv.t)
    return dt > 0 ? (L.num(r2.kv.cur) - L.num(r1.kv.cur)) / dt : NaN
  }
  for (let i = 0; i < PTS.length; i++) {
    const v = PTS[i]
    await stat('end', v)
    const sm = await b.cmd('/soulstest stamina', 'STAMINA')
    sc.check(`endurance ${v}: max stamina ${T.stamina[i]}`, sm.kv && L.num(sm.kv.max) === T.stamina[i], sm.line || '')
    const st = await stats()
    sc.check(`endurance ${v}: regen ${(44 * T.regen[i]).toFixed(1)}/s (x${T.regen[i]})`, st.kv && Math.abs(L.num(st.kv.regen) - 44 * T.regen[i]) < 0.06, st.line || '')
    const hud = await b.cmd('/soulstest hud', 'HUD ')
    const len = hud.kv ? L.num(hud.kv.st.split('/')[1]) : NaN
    sc.check(`endurance ${v}: HUD stamina bar ${hudLen(T.stamina[i], 0.65)} px long`, Math.abs(len - hudLen(T.stamina[i], 0.65)) <= 1, hud.line || '')
    if (v === 10 || v === 40 || v === 99) {
      const rate = await regenRate()
      const want = 2.2 * T.regen[i]
      sc.check(`endurance ${v}: measured regen ${want.toFixed(3)} per tick`, Math.abs(rate - want) < 0.01, `잰 값 ${rate.toFixed(4)}/틱`)
    }
  }
  await stat('end', 10)
  await b.cmd('/soulstest heal', 'HEAL')

  // ── 근력: 공격력 + 장비 무게 ──
  for (let i = 0; i < PTS.length; i++) {
    const v = PTS[i]
    await stat('str', v)
    const st = await stats()
    const ar = 74 * (1 + 0.8 * T.scaling[i])
    sc.check(`strength ${v}: club (str C, one hand) attack ${ar.toFixed(1)}, load limit ${T.cap[i]}`, st.kv && st.kv.twohand === 'false' &&
      Math.abs(L.num(st.kv.atk) - ar) <= 0.51 && st.kv.load.split('/')[1] === T.cap[i].toFixed(1), st.line || '')
  }
  await stat('str', 10)
  // 적을 치는 다리 (3.7, 검토 stat-values-without-effect): 곤봉 한 손, 시험 좀비 (움직이지 않는다) 를 대기가 다 찬 뒤 친다
  {
    await b.cmd('/soulstest foehp clear', 'FOEHP ')
    await b.cmd('/soulstest foehp spawn', 'FOEHP ', 1500)
    const hits = []
    for (const sv of [10, 40]) {
      await stat('str', sv)
      await b.cmd('/soulstest foehp clear', 'FOEHP ')
      await b.cmd('/soulstest foehp spawn', 'FOEHP ', 1500)
      await L.sleep(400)
      const z = Object.values(b.bot.entities).filter((e) => e.name === 'zombie').sort((x, y) => x.position.distanceTo(b.bot.entity.position) - y.position.distanceTo(b.bot.entity.position))[0]
      const from = b.sys.length
      if (z) {
        await b.bot.lookAt(z.position.offset(0, 1.4, 0), true)
        await L.sleep(1300) // 곤봉 (망치) 한 주기 18틱 = 0.9초: 대기가 다 찬다
        b.bot.attack(z)
      }
      const h = await b.waitT('PVE_HIT ', 2000, from)
      const ar = 74 * (1 + 0.8 * T.scaling[PTS.indexOf(sv)])
      const cd = h ? L.num(h.kv.cd) : NaN
      const want = ar * (0.2 + 0.8 * cd * cd) * 0.09
      sc.check(`strength ${sv}: hitting a foe with the club deals attack ${ar.toFixed(1)} x (0.2 + 0.8 cd^2) x 0.09 = ${want.toFixed(2)} (PVE_HIT)`,
        h && h.kv.weapon === 'gaoler_club' && Math.abs(L.num(h.kv.ar) - ar) <= 0.51 && Math.abs(L.num(h.kv.dealt) - want) < 0.05 && cd > 0.9, h ? h.line : (z ? '줄 없음' : '좀비 없음'))
      if (h) hits.push(L.num(h.kv.dealt) / Math.max(0.01, 0.2 + 0.8 * cd * cd))
    }
    sc.check('strength 40 hits foes harder than strength 10 (x1.40, attack rating)', hits.length === 2 && Math.abs(hits[1] / hits[0] - (1 + 0.8 * 0.68) / (1 + 0.8 * 0.13)) < 0.02,
      hits.map((x) => x.toFixed(2)).join(' -> '))
    await b.cmd('/soulstest foehp clear', 'FOEHP ')
    await stat('str', 10)
  }
  // 양손 (왼손을 비운다): 근력 ×1.5 = 15
  await b.cmd('/item replace entity @s weapon.offhand with air', null, 1200)
  await L.sleep(400)
  const two = await stats()
  const ar2 = 74 * (1 + 0.8 * (0.13 + 5 * 0.022))
  sc.check(`two-handed (empty off hand): strength 10 counts as 15, attack ${ar2.toFixed(1)}`, two.kv && two.kv.twohand === 'true' && Math.abs(L.num(two.kv.atk) - ar2) <= 0.51, two.line || '')
  // 무게: 단축 슬롯을 무기로 채운다 (39.5 + 곤봉 칸)
  await b.cmd('/soulstest give all', 'GIVE')
  await L.sleep(800)
  const lh = await b.cmd('/soulstest load', 'LOAD ')
  sc.checkCmd('strength 10, hotbar of weapons: heavy', lh, (r) => r.kv.tier === 'heavy' && r.kv.roll === 'heavy')
  const mvH = await waitAttr(b, 'movement_speed', (x) => Math.abs(x - 0.092) < 1e-4)
  sc.check('heavy: client movement speed x0.92 (0.092, souls:load modifier)', mvH && Math.abs(mvH.value - 0.092) < 1e-4 && mods(mvH, 'load').length === 1,
    mvH ? `${mvH.value} ${JSON.stringify(mvH.modifiers)}` : '-')
  const rH = await regenRate()
  sc.check('heavy: measured stamina regen x0.85 (1.870 per tick)', Math.abs(rH - 2.2 * 0.85) < 0.01, `잰 값 ${rH.toFixed(4)}/틱`)
  const sub0 = b.p.subtitles.length
  await stat('str', 40)
  const lm = await b.cmd('/soulstest load', 'LOAD ')
  sc.checkCmd('strength 40 (limit 76): the same load is medium (penalty reduced)', lm, (r) => r.kv.tier === 'medium' && r.kv.roll === 'medium' && r.kv.cap === '76.0')
  const mvM = await waitAttr(b, 'movement_speed', (x) => Math.abs(x - 0.1) < 1e-4)
  sc.check('medium: walking speed back to 0.100 (no souls:load modifier)', mvM && Math.abs(mvM.value - 0.1) < 1e-4 && mods(mvM, 'load').length === 0,
    mvM ? `${mvM.value} ${JSON.stringify(mvM.modifiers)}` : '-')
  const lt = b.p.subtitles.slice(sub0).filter((m) => L.translateKeys(m.raw).includes('souls.burden.medium'))
  sc.check('tier change is announced once, saying what changed (subtitle souls.burden.medium)', lt.length === 1, b.p.subtitles.slice(sub0).map((m) => L.translateKeys(m.raw).join('+')).join(' | ') || '부제목 없음')
  const rM = await regenRate()
  sc.check('medium: measured stamina regen x0.95 (2.090 per tick)', Math.abs(rM - 2.2 * 0.95) < 0.01, `잰 값 ${rM.toFixed(4)}/틱`)
  await b.cmd('/clear @s', null, 1500)
  await b.cmd('/soulstest give gaoler_club main', 'GIVE')
  await b.cmd('/soulstest give plank_shield off', 'GIVE')
  await stat('str', 10)
  await L.sleep(600)

  // ── 민첩: 이동 속도 + 공격 속도 ──
  const asBase = attr(b, 'attack_speed')
  for (let i = 0; i < PTS.length; i++) {
    const v = PTS[i]
    await stat('dex', v)
    const want = 0.1 * (1 + T.move[i])
    const mv = await waitAttr(b, 'movement_speed', (x) => Math.abs(x - want) < 1e-5)
    sc.check(`dexterity ${v}: client movement speed ${want.toFixed(4)} (+${Math.round(T.move[i] * 100)}%, ${T.move[i] ? 'one' : 'no'} souls:lvl_dex modifier)`,
      mv && Math.abs(mv.value - want) < 1e-5 && mods(mv, 'lvl_dex').length === (T.move[i] ? 1 : 0), mv ? `${mv.value} ${JSON.stringify(mv.modifiers)}` : '-')
    const st = await stats()
    const aspd = 1 + T.aspd[i] * 0.4
    sc.check(`dexterity ${v}: attack speed x${aspd.toFixed(3)} with the club (dex E 0.4)`, st.kv && Math.abs(L.num(st.kv.aspd) - aspd) < 1e-3 &&
      Math.abs(L.num(st.kv.move) - T.move[i]) < 1e-6, st.line || '')
    const sa = await srvAttr(b)
    const want2 = 20 / 18 * aspd
    sc.check(`dexterity ${v}: server attack_speed ${want2.toFixed(3)} (club base 20/18 x ${aspd.toFixed(3)})`, sa && Math.abs(sa.attack_speed - want2) < 1e-3 &&
      count(sa.mods.attack_speed, 'souls:weapon_speed') === 1 && count(sa.mods.attack_speed, 'souls:lvl_dex') === (T.aspd[i] ? 1 : 0), sa ? sa.line : '-')
  }
  await b.cmd('/soulstest give alley_dagger main', 'GIVE')
  await L.sleep(300)
  const dg = await stats()
  sc.check('dexterity 99: attack speed x1.36 with the dagger (dex A 1.2)', dg.kv && dg.kv.weapon === 'alley_dagger' && Math.abs(L.num(dg.kv.aspd) - 1.36) < 1e-3, dg.line || '')
  await L.sleep(400)
  const saD = await srvAttr(b)
  sc.check('dexterity 99 with the dagger: attack_speed 2.0 x 1.36 = 2.72 (souls:weapon_speed + souls:lvl_dex)', saD && Math.abs(saD.attack_speed - 2.72) < 1e-3 &&
    count(saD.mods.attack_speed, 'souls:weapon_speed') === 1 && count(saD.mods.attack_speed, 'souls:lvl_dex') === 1,
    saD ? `server attack_speed ${saD.attack_speed} mods ${saD.mods.attack_speed.join(',') || '-'}; client ${asBase ? asBase.value : '기본값 (받지 않음)'}` : '-')
  await b.cmd('/soulstest give gaoler_club main', 'GIVE')
  await stat('dex', 10)

  // ── 지능: 상태 이상 저항 + 술 세기 ──
  await b.cmd('/soulstest give kiln_pot inv', 'GIVE')
  await L.sleep(300)
  for (let i = 0; i < PTS.length; i++) {
    const v = PTS[i]
    await stat('int', v)
    const want = Math.round(200 * (1 - T.resist[i]))
    const from = b.sys.length
    const ef = await b.cmd('/soulstest effect poison 200', 'EFFECT ')
    const ail = b.tLines('AILMENT ', from)[0]
    sc.check(`intelligence ${v}: poison 200 ticks -> ${want} (resist ${Math.round(T.resist[i] * 100)}%)`, ef.kv && Math.abs(L.num(ef.kv.have) - want) <= 1 &&
      (T.resist[i] === 0 ? !ail : ail && L.num(ail.kv.to) === want), (ail ? ail.line + ' | ' : '') + (ef.line || ''))
    const st = await stats()
    const sp = 100 * (1 + 0.8 * T.scaling[i]) * (v < 12 ? 0.6 : 1)
    sc.check(`intelligence ${v}: spell power ${sp.toFixed(1)} with the kiln pot (int C${v < 12 ? ', below 12 needed: -40%' : ''})`, st.kv && st.kv.catalyst === 'kiln_pot' &&
      Math.abs(L.num(st.kv.spell) - sp) <= 0.51 && Math.abs(L.num(st.kv.ailment) - T.resist[i]) < 1e-3, st.line || '')
    await b.cmd('/effect clear @s', null, 1000)
  }
  // 지능 99: 아주 짧은 효과는 털어 낸다 (12틱 × 0.65 = 8 < 10)
  {
    const from = b.sys.length
    const ef = await b.cmd('/soulstest effect slowness 12', 'EFFECT ')
    const ail = b.tLines('AILMENT ', from)[0]
    sc.check('intelligence 99: a 12-tick slowness is shaken off (under 10 ticks)', ef.kv && L.num(ef.kv.have) === 0 && ail && ail.kv.to === '0', (ail ? ail.line : '') + ' | ' + (ef.line || ''))
  }
  // 불붙음과 실제 투척 물약 (지능 40)
  await stat('int', 40)
  {
    let from = b.sys.length
    const bu = await b.cmd('/soulstest burn 100', 'BURN ')
    const ail = b.tLines('AILMENT ', from)[0]
    sc.check('intelligence 40: burning 100 ticks -> 76', bu.kv && L.num(bu.kv.fire) === 76 && ail && ail.kv.type === 'fire', (ail ? ail.line : '') + ' | ' + (bu.line || ''))
    await b.cmd('/soulstest heal', 'HEAL')
    await b.cmd('/effect clear @s', null, 1000)
    from = b.sys.length
    await b.cmd(`/soulstest pvpshoot ${b.name} potion`, 'PVPSHOOT ')
    const sp = await b.waitT('AILMENT ', 3000, from)
    sc.check('intelligence 40: a thrown poison potion is shortened too (cause potion_splash, x0.76)', sp && sp.kv.type === 'poison' && sp.kv.cause === 'potion_splash' &&
      Math.abs(L.num(sp.kv.to) - Math.round(L.num(sp.kv.from) * 0.76)) <= 1, sp ? sp.line : '줄 없음')
    await L.sleep(300)
    await b.cmd('/effect clear @s', null, 1000)
  }
  await stat('int', 10)
  await b.cmd('/soulstest heal', 'HEAL')

  // ── 되돌린 뒤: 수정자가 쌓이지 않았다 ──
  for (const id of ['vig', 'mnd', 'end', 'str', 'dex', 'int']) await stat(id, 10)
  await L.sleep(500)
  const sa = await srvAttr(b)
  const mv = attr(b, 'movement_speed')
  sc.check('all back to 10 with the club: attack_speed 1.111 with one souls:weapon_speed and no souls:lvl_dex', sa && Math.abs(sa.attack_speed - 20 / 18) < 1e-3 &&
    count(sa.mods.attack_speed, 'souls:weapon_speed') === 1 && count(sa.mods.attack_speed, 'souls:lvl_dex') === 0, sa ? sa.line : '-')
  sc.check('all back to 10: server max_health 400 with one souls:lvl_vig, movement 0.100 with no souls modifier (server and client)', sa &&
    Math.abs(sa.max_health - 400) < 0.01 && sa.mods.max_health.join(',') === 'souls:lvl_vig' && Math.abs(sa.movement_speed - 0.1) < 1e-5 &&
    !sa.mods.movement_speed.some((k) => k.startsWith('souls:')) && mv && Math.abs(mv.value - 0.1) < 1e-5 && !mods(mv, 'souls').length,
    `${sa ? sa.line : '-'} / client ${mv && mv.value}`)
  const sEnd = await stats()
  sc.check('level back to 1', sEnd.kv && sEnd.kv.level === '1', sEnd.line || '')
  sc.check('no kick during stats scenario', !b.kick, b.kick || '')
})
