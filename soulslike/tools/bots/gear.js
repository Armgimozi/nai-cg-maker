// 장비에는 능력치 보정도 요구 능력치도 없다 (DECISIONS 2026-10-10, DESIGN 9.1·9.2·9.7, 3.5). 봇은 빈털터리 (곤봉 + 판자 방패) 로 태어난다.
//   설명 칸: 무기·활·패링 단검은 "공격력, 무게" 한 줄, 방패는 "물리 컷률, 무게" (Phys. Negation), 촉매는 "술법 위력, 무게". 보정·필요 능력치 줄, 흡수·안정성
//            줄이 없다 (번역 열쇠와 받은 팩의 ko_kr·en_us 로 그린 글). 반지는 효과 줄과 설명뿐이고 무게가 없는 반지에는 무게 줄도 없다.
//   패링 (F): 왼손 물건의 분류로 창이 정해진다 (combat.parry.windows, 설명 칸에 없다). 패링 단검 9, 소형 방패 7 (판자·버클러 모두),
//            중형 방패 5, 왼손 단검 4. 대형 방패·대검·빈 왼손은 패링하지 못한다 (PARRY_NONE why=cannot: F 는 아무것도 하지 않는다).
//            패링 반지 (+2틱) 가 더해진다. 연달아 누르면 잠긴다 (PARRY_LOCKED, 놓친 뒤 12틱).
//   패링 단검은 왼손 무기: 막기 성분이 없고 (막지 않는다), 왼손에 들면 주손 곤봉의 막기 성분도 떼어진다 (우클릭은 왼손에 든 것을 쓴다).
//   다른 무기 (단검) 도 왼손에 들면 막기 성분이 떼어진다 (왼손 무기의 우클릭은 왼손 공격, M1).
//   왼손을 비우면 양손 잡기 (주무기로 막는다: 곤봉에 막기 성분, 근력 ×1.5).
//   예전 판의 무기 (설명 칸에 옛 줄이 구워진 것) 는 창 (엔더 상자) 을 열 때, 땅에서 주울 때, /souls reload 때 지금 판으로 바뀐다 (WEAPON_REFRESH).
//   반지 설명 칸: 효과 줄과 설명 사이에 무기처럼 실선 (ring.rule.<id>).
//   껍데기 (DECISIONS 2026-10-11 바닐라 쥐는 법, weapons/SPEC.md 1.3): 방패는 바닐라 방패 (minecraft:shield, 막기 성분은 빈 감소표·지연 0,
//            내구도·마법부여·수리 성분을 뗐다), 창·미늘창은 바닐라 돌창 (#minecraft:spears 라 3인칭 창 팔 자세. 창의 찌르기·돌진·사거리·
//            내구도·공격 속성 성분을 모두 뗐다), 나머지 무기·촉매는 부싯돌, 활은 바닐라 활. 예전 판의 부싯돌 방패는 접속할 때
//            바닐라 방패로 바뀐다 (WEAPON_REFRESH where=join). 인벤토리에서 웅크리고 누른 방패는 바닐라 방패처럼 빈 왼손 칸으로 간다.
'use strict'
const L = require('./lib')

const HANGUL = /[가-힣]/

/** 마지막으로 칸에 들어온 souls 무기 id 의 아이템 (item_name 의 souls.weapon.<id>.name). */
function lastItem (b, from, nameKey) {
  return b.p.slots.slice(from).reverse().find((x) => x.name && L.translateKeys(x.name)[0] === nameKey) || null
}

async function waitItem (b, from, nameKey, ms = 3000) {
  const end = Date.now() + ms
  for (;;) {
    const it = lastItem(b, from, nameKey)
    if (it || Date.now() > end) return it
    await L.sleep(100)
  }
}

/** 손 칸 (36 단축 1, 45 왼손) 아이템의 성분 종류 목록. */
function comps (b, slot) {
  const it = b.bot.inventory.slots[slot]
  return it && Array.isArray(it.components) ? it.components.map((c) => c.type) : []
}

/** 칸 아이템이 바닐라 기본 성분에서 뗀 성분 종류 목록 (슬롯 패킷의 removeComponents). */
function removed (b, slot) {
  const it = b.bot.inventory.slots[slot]
  return it && Array.isArray(it.removedComponents) ? it.removedComponents.map((c) => (typeof c === 'string' ? c : c.type)) : []
}

function compData (b, slot, type) {
  const it = b.bot.inventory.slots[slot]
  const c = it && Array.isArray(it.components) ? it.components.find((x) => x.type === type) : null
  return c ? c.data : null
}

L.run('gear', async (sc) => {
  const b = await L.connect(sc)
  await L.sleep(1500)
  await b.cmd('/souls tp room', null, 1200)
  await L.sleep(400)
  await b.ground(3000)
  const t0 = Date.now()
  while (!b.p.packChecks.length && Date.now() - t0 < 6000) await L.sleep(100)
  const got = b.p.packChecks.length ? await b.p.packChecks[0] : null
  const T = got && got.ok ? (() => { const z = L.readZip(got.buf); return { en: L.langTable(z, 'en_us'), ko: L.langTable(z, 'ko_kr') } })() : null
  sc.check('resource pack downloaded (to read the tooltips in Korean and English)', !!T, got ? (got.error || '') : '팩 없음')

  // ── 설명 칸 ──
  const CASES = [
    // [id, 첫 칸 열쇠, 첫 칸 값, 무게, 한국어 이름, 영어 이름]
    ['redin_guard_sword', 'attack', '62', '3.0', '공격력', 'Attack'],
    ['gaoler_greatsword', 'attack', '92', '9.0', '공격력', 'Attack'],
    ['wall_shortbow', 'attack', '45', '2.0', '공격력', 'Attack'],
    ['parrying_dagger', 'attack', '40', '0.5', '공격력', 'Attack'],
    ['plank_shield', 'guard', '60', '1.0', '물리 컷률', 'Phys. Negation'],
    ['redin_guard_shield', 'guard', '90', '4.0', '물리 컷률', 'Phys. Negation'],
    ['volk_greatshield', 'guard', '100', '14.0', '물리 컷률', 'Phys. Negation'],
    ['kiln_pot', 'spell', '100', '1.5', '술법 위력', 'Spell Power'],
    ['pilgrim_handbell', 'spell', '100', '2.0', '술법 위력', 'Spell Power']
  ]
  const DEAD = ['bonus_str', 'bonus_dex', 'bonus_int', 'need_str', 'need_dex', 'need_int', 'absorb', 'stability']
  for (const [id, first, value, weight, ko, en] of CASES) {
    const from = b.p.slots.length
    await b.cmd(`/soulstest give ${id} inv`, 'GIVE')
    const it = await waitItem(b, from, `souls.weapon.${id}.name`)
    if (!sc.check(`${id}: item arrives`, !!it, '칸 패킷 없음')) continue
    const statLines = it.lore.filter((l) => L.translateKeys(l).some((k) => k.startsWith('souls.weapon.stat.')))
    const keys = statLines.flatMap((l) => L.translateKeys(l))
    sc.check(`${id}: exactly one stat row, ${first} + weight`, statLines.length === 1 && keys.join(',') === `souls.weapon.stat.${first},souls.weapon.stat.weight`,
      keys.join(',') || '수치 줄 없음')
    sc.check(`${id}: no scaling, requirement, absorption or stability rows`, !it.lore.some((l) => L.translateKeys(l).some((k) => DEAD.some((d) => k.endsWith('.' + d)))),
      it.lore.map((l) => L.translateKeys(l).join('+')).join(' | '))
    if (T && statLines.length) {
      const k = L.render(statLines[0], T.ko).replace(/[-]/g, ' ').replace(/\s+/g, ' ').trim()
      const e = L.render(statLines[0], T.en).replace(/[-]/g, ' ').replace(/\s+/g, ' ').trim()
      sc.check(`${id}: Korean row reads "${ko} ${value} 무게 ${weight}"`, k === `${ko} ${value} 무게 ${weight}`, JSON.stringify(k))
      sc.check(`${id}: English row reads "${en} ${value} Weight ${weight}"`, e === `${en} ${value} Weight ${weight}` && !HANGUL.test(e), JSON.stringify(e))
    }
  }
  await b.cmd('/clear @s', null, 1500)
  await b.cmd('/soulstest give gaoler_club main', 'GIVE')
  await b.cmd('/soulstest give plank_shield off', 'GIVE')
  await L.sleep(500)

  // 반지: 효과 줄과 설명뿐, 무게가 없으면 무게 줄도 없다
  {
    const from = b.p.slots.length
    await b.cmd('/soulstest ring give test_parry', 'RING_GIVE')
    const it = await waitItem(b, from, 'souls.ring.test_parry.name')
    const keys = it ? it.lore.flatMap((l) => L.translateKeys(l)) : []
    sc.check('ring tooltip: effect line, pending note, rule and lore only (no weight row for a weightless ring)', it && keys.includes('souls.ring.effect.parry-window') &&
      !keys.includes('souls.ring.weight') && !keys.some((k) => k.startsWith('souls.weapon.stat.')), keys.join(','))
    // 고리만 있는 효과는 따로 줄을 내지 않고 효과 줄 끝에 "(미적용)" (레벨 업 설명 칸과 같은 꼬리, 검토 not-yet-active-wording-split)
    const first = it && it.lore[0] ? L.translateKeys(it.lore[0]) : []
    sc.check('ring tooltip: the pending tail sits on the effect line (ring.effect.pending inside line 1)', first.includes('souls.ring.effect.parry-window') &&
      first.includes('souls.ring.effect.pending') && it.lore.filter((l) => L.translateKeys(l).includes('souls.ring.effect.pending')).length === 1, first.join(','))
    const rule = it ? it.lore.findIndex((l) => L.translateKeys(l).includes('souls.ring.rule.test_parry')) : -1
    const loreAt = it ? it.lore.findIndex((l) => L.translateKeys(l).some((k) => k.startsWith('souls.ring.test_parry.lore'))) : -1
    sc.check('ring tooltip: a rule line (ring.rule.<id>, like weapons) sits right above the lore', rule > 0 && loreAt === rule + 1, `rule ${rule}, lore ${loreAt}`)
    if (T && rule > 0) sc.check('the pack builds the ring rule in both languages', !!T.ko['souls.ring.rule.test_parry'] && !!T.en['souls.ring.rule.test_parry'])
    if (T && it) {
      const k = L.render(it.lore[0], T.ko)
      sc.check('ring effect line says 패링 판정 +0.1초 (미적용) (not 쳐내기, not 패링 창)', /^패링 판정 \+0\.1초 \(미적용\)$/.test(k) && !/쳐내기|패링 창/.test(k), JSON.stringify(k))
      const lore = it.lore.filter((l) => L.translateKeys(l).some((x) => x.startsWith('souls.ring.test_parry.lore'))).map((l) => L.render(l, T.ko))
      sc.check('test ring lore is the [시험용] marker, not a developer note', lore.join('|') === '[시험용]', JSON.stringify(lore))
      sc.check('test ring name says 패링', L.render(it.name, T.ko) === '시험 반지: 패링', JSON.stringify(L.render(it.name, T.ko)))
    }
  }

  // ── 껍데기: 방패 = 바닐라 방패, 창·미늘창 = 바닐라 돌창, 나머지 = 부싯돌 (바닐라 쥐는 법, SPEC 1.3) ──
  {
    await b.cmd('/clear @s', null, 1200)
    await b.cmd('/soulstest give redin_guard_shield off', 'GIVE')
    await b.cmd('/soulstest give redin_spear main', 'GIVE')
    await L.sleep(800)
    const off = b.bot.inventory.slots[45]
    const main = b.bot.inventory.slots[36]
    sc.check('shield shell is the vanilla shield (minecraft:shield)', off && off.name === 'shield', off ? off.name : '없음')
    const ba = compData(b, 45, 'blocks_attacks')
    const baj = JSON.stringify(ba || {})
    sc.check('the shield blocks with the plugin guard: empty damage reductions, no block delay, #bypasses_shield', !!ba &&
      Array.isArray(ba.damageReductions) && ba.damageReductions.length === 0 && Number(ba.blockDelaySeconds) === 0 && /bypasses_shield/.test(baj),
      baj.slice(0, 300))
    const rs = removed(b, 45)
    sc.check('the shield shell drops durability and repair (max_damage, damage, repairable removed; never enchantable)',
      ['max_damage', 'damage', 'repairable'].every((t) => rs.includes(t)) && !comps(b, 45).includes('enchantable'), rs.join(','))
    sc.check('the shield keeps our name (item_name souls.weapon.redin_guard_shield.name, no base_color)', comps(b, 45).includes('item_name') &&
      !comps(b, 45).includes('base_color') && JSON.stringify(compData(b, 45, 'item_name') || '').includes('souls.weapon.redin_guard_shield.name'),
      comps(b, 45).join(','))
    sc.check('spear shell is a vanilla spear (stone_spear, #minecraft:spears)', main && main.name === 'stone_spear', main ? main.name : '없음')
    const rm = removed(b, 36)
    // M1 P1a: attack_range 와 swing_animation 은 우리 값으로 덮는다 (사거리 = 분류의 사거리, hitbox_margin 0. 창은 찌르기, Q6)
    const SPEAR_DROP = ['kinetic_weapon', 'piercing_weapon', 'minimum_attack_charge', 'damage_type', 'weapon', 'max_damage', 'damage',
      'enchantable', 'repairable']
    sc.check('the spear shell drops the vanilla spear components (stab, charge, durability, enchanting)', SPEAR_DROP.every((t) => rm.includes(t)),
      'removed ' + rm.join(','))
    const sar = compData(b, 36, 'attack_range')
    sc.check('the spear carries our attack_range (class reach 4.2, hitbox margin 0; P1a)', !!sar && Math.abs(sar.maxRange - 4.2) < 1e-3 &&
      Math.abs(sar.hitboxMargin) < 1e-6 && Math.abs(sar.minRange || 0) < 1e-6, JSON.stringify(sar))
    const swing = JSON.stringify(compData(b, 36, 'swing_animation') || '')
    const attrs = compData(b, 36, 'attribute_modifiers')
    const attrsJ = JSON.stringify(attrs || '')
    sc.check('the spear shell takes our stab swing (P1a, Q6) and the flint attributes (no spear attack damage/speed modifiers)',
      /stab/i.test(swing) && !rm.includes('swing_animation') && !/attack_damage|attack_speed|spear/i.test(attrsJ),
      `swing ${swing.slice(0, 120)} attrs ${attrsJ.slice(0, 160)} comps ${comps(b, 36).join(',')}`)
    await b.cmd('/soulstest give hrolf_halberd main', 'GIVE')
    await b.cmd('/soulstest give gaoler_club inv', 'GIVE')
    await L.sleep(600)
    const hal = b.bot.inventory.slots[36]
    sc.check('halberds use the spear shell too', hal && hal.name === 'stone_spear', hal ? hal.name : '없음')
    const club = b.bot.inventory.slots.find((it, i) => i >= 9 && i < 45 && it && JSON.stringify(it.components || []).includes('souls.weapon.gaoler_club.name'))
    sc.check('other weapons stay on the flint shell (gaoler_club)', club && club.name === 'flint', club ? club.name : '없음')
    // 인벤토리에서 웅크리고 누르면 바닐라 방패처럼 빈 왼손 칸으로 (equippable 을 남겼다, S8)
    await b.cmd('/item replace entity @s weapon.offhand with air', null, 800)
    await b.cmd('/soulstest give plank_shield inv', 'GIVE')
    await L.sleep(600)
    const at = b.bot.inventory.slots.findIndex((it, i) => i >= 9 && i < 45 && it && it.name === 'shield')
    if (sc.check('plank shield lands in the inventory', at >= 9, String(at))) {
      await b.bot.clickWindow(at, 0, 1).catch(() => {})
      await L.sleep(800)
      const o = b.bot.inventory.slots[45]
      sc.check('shift-click moves the shield to the empty off hand (like a vanilla shield)', o && o.name === 'shield' &&
        JSON.stringify(o.components || []).includes('souls.weapon.plank_shield.name') && !b.bot.inventory.slots[at], o ? o.name : '왼손 빔')
    }
    await b.cmd('/clear @s', null, 1200)
    await b.cmd('/soulstest give gaoler_club main', 'GIVE')
    await b.cmd('/soulstest give plank_shield off', 'GIVE')
    await L.sleep(500)
  }

  // ── 모루·제작대에 들어가지 않는다, 붙은 마법부여·깃발은 지운다 (검토 P0-5: 돌창 껍데기는 #minecraft:spears 라 모루가 화염·밀치기 책을
  //    붙일 수 있고, 방패 껍데기는 깃발을 받으면 이름이 바닐라 "빨간 방패" 가 된다) ──
  {
    const Item = require('prismarine-item')(b.bot.registry)
    // 열린 창 (windowId) 의 칸을 날 window_click 으로 누른다 (lib.rawClick 은 인벤토리 창 0 만): 서버가 그 창을 다시 보낸다
    const winClick = async (win, slot) => {
      b.bot._client.write('window_click', { windowId: win.id, stateId: -1, slot, mouseButton: 0, mode: 0, changedSlots: [], cursorItem: Item.toNotch(null) })
      await L.sleep(300)
    }
    const openMenu = async (kind) => {
      const opened = new Promise((resolve) => b.bot.once('windowOpen', (w) => resolve(w)))
      await b.cmd(`/soulstest menu ${kind}`, 'MENU')
      return Promise.race([opened, L.sleep(3000).then(() => null)])
    }
    // 단축 칸 0·1 의 것을 작업 창의 두 재료 칸에 (단축 칸 0 = 창 칸 first, 1 = first+1)
    const twoIn = async (win, hot0, a, c) => {
      await winClick(win, hot0); await winClick(win, a)
      await winClick(win, hot0 + 1); await winClick(win, c)
      await L.sleep(500)
    }
    const name = (it) => (it ? it.name + ' ' + JSON.stringify(it.components || []).slice(0, 160) : '빔')
    const cases = [
      // [창, 결과 칸, 단축 칸 0 의 창 칸, 재료 칸 둘, 주손 명령, 단축 칸 1 명령, souls 무기인가, 설명]
      ['anvil', 2, 30, [0, 1], '/soulstest give redin_spear main', 'minecraft:enchanted_book[stored_enchantments={"minecraft:fire_aspect":2}]', true,
        'an anvil gives no result for a souls spear + fire aspect book (WEAPON_CRAFT_DENY where=anvil)'],
      ['anvil', 2, 30, [0, 1], '/item replace entity @s hotbar.0 with minecraft:iron_sword', 'minecraft:enchanted_book[stored_enchantments={"minecraft:sharpness":1}]', false,
        'control: the same anvil does give a result for a vanilla iron sword + sharpness book'],
      ['crafting', 0, 37, [1, 2], '/soulstest give redin_guard_shield main', 'minecraft:red_banner', true,
        'a crafting table gives no result for a souls shield + banner (WEAPON_CRAFT_DENY where=craft)'],
      ['crafting', 0, 37, [1, 2], '/item replace entity @s hotbar.0 with minecraft:shield', 'minecraft:red_banner', false,
        'control: the same crafting table does decorate a vanilla shield with a banner']
    ]
    for (const [kind, out, hot0, [a, c], give, second, ours, what] of cases) {
      await b.cmd('/clear @s', null, 1000)
      await b.cmd(give, ours ? 'GIVE' : null, 800)
      await b.cmd(`/item replace entity @s hotbar.1 with ${second}`, null, 800)
      const from = b.sys.length
      const win = await openMenu(kind)
      if (!sc.check(`${kind} window opens (/soulstest menu ${kind})`, !!win, '창 없음')) continue
      await twoIn(win, hot0, a, c)
      const res = win.slots[out]
      const deny = b.tLines('WEAPON_CRAFT_DENY', from).map((x) => x.line)
      if (ours) {
        sc.check(what, !res && deny.some((l) => l.includes(`where=${kind === 'anvil' ? 'anvil' : 'craft'}`)),
          `결과 ${name(res)} | 재료 ${name(win.slots[a])} / ${name(win.slots[c])} | ${deny.join(' | ') || '거절 줄 없음'}`)
      } else {
        sc.check(what, !!res && !deny.length, `결과 ${name(res)} | ${deny.join(' | ')}`)
      }
      b.bot.closeWindow(win)
      await L.sleep(500)
    }
    // 이미 붙은 마법부여·깃발 색 (다른 세계·예전 판에서): /souls reload 가 다시 만든다. 이름은 우리 것 그대로
    await b.cmd('/clear @s', null, 1000)
    await b.cmd('/soulstest give redin_spear main', 'GIVE')
    await b.cmd('/soulstest give plank_shield off', 'GIVE')
    await L.sleep(400)
    await b.cmd('/item modify entity @s weapon.mainhand {function:"minecraft:set_enchantments",enchantments:{"minecraft:fire_aspect":2}}', null, 1000)
    await b.cmd('/item modify entity @s weapon.offhand {function:"minecraft:set_components",components:{"minecraft:base_color":"red"}}', null, 1000)
    await L.sleep(400)
    sc.check('setup: the spear carries fire aspect and the shield a red base colour', comps(b, 36).includes('enchantments') && comps(b, 45).includes('base_color'),
      comps(b, 36).join(',') + ' | ' + comps(b, 45).join(','))
    let from = b.sys.length
    await b.cmd('/souls reload', null, 4000)
    let r = await b.waitT('WEAPON_REFRESH', 4000, from)
    sc.check('/souls reload rebuilds the enchanted spear and the banner-coloured shield (WEAPON_REFRESH n=2 where=reload)', r && r.kv.n === '2' && r.kv.where === 'reload',
      r ? r.line : '줄 없음')
    await L.sleep(500)
    sc.check('the rebuilt spear has no enchantments and keeps its item_name', !comps(b, 36).includes('enchantments') &&
      JSON.stringify(compData(b, 36, 'item_name') || '').includes('souls.weapon.redin_spear.name'), comps(b, 36).join(','))
    sc.check('the rebuilt shield has no base colour and keeps its item_name (not the vanilla "Red Shield")', !comps(b, 45).includes('base_color') &&
      JSON.stringify(compData(b, 45, 'item_name') || '').includes('souls.weapon.plank_shield.name'), comps(b, 45).join(','))
    // 껍데기 성분 종류가 지금 판과 다른 것 (마인크래프트 판이 바뀌어 돌창에 새 기본 성분이 생긴 경우, 예전 판에 남은 성분): 설명 칸·종류가
    // 같아도 다시 만든다. 지금 판의 창에 우리가 붙이지 않는 성분 (glider) 하나를 더해 본다
    await b.cmd('/item modify entity @s weapon.mainhand {function:"minecraft:set_components",components:{"minecraft:glider":{}}}', null, 1000)
    await L.sleep(300)
    sc.check('setup: the current spear now carries one extra component (glider)', comps(b, 36).includes('glider'), comps(b, 36).join(','))
    from = b.sys.length
    await b.cmd('/souls reload', null, 4000)
    r = await b.waitT('WEAPON_REFRESH', 4000, from)
    sc.check('a spear whose component set differs from the current build is rebuilt on reload (WEAPON_REFRESH n=1)', r && r.kv.n === '1' && r.kv.where === 'reload',
      r ? r.line : '줄 없음')
    await L.sleep(500)
    const rm = removed(b, 36)
    sc.check('after the rebuild the extra component is gone and the spear components stay removed', !comps(b, 36).includes('glider') &&
      ['kinetic_weapon', 'piercing_weapon'].every((t) => rm.includes(t)) && comps(b, 36).includes('attack_range'), comps(b, 36).join(',') + ' | removed ' + rm.join(','))
    from = b.sys.length
    await b.cmd('/souls reload', null, 4000)
    await L.sleep(600)
    sc.check('current spear and shield are not rebuilt again (no WEAPON_REFRESH on the next reload)', !b.tLines('WEAPON_REFRESH', from).length,
      b.tLines('WEAPON_REFRESH', from).map((x) => x.line).join(' | '))
    await b.cmd('/clear @s', null, 1200)
    await b.cmd('/soulstest give gaoler_club main', 'GIVE')
    await b.cmd('/soulstest give plank_shield off', 'GIVE')
    await L.sleep(500)
  }

  // ── 패링 판정: 왼손 물건의 분류마다 ──
  const press = async (sneak = false) => {
    if (sneak) { b.input({ shift: true }); await L.sleep(250) }
    const from = b.sys.length
    b.swap()
    const r = await b.waitT('PARRY', 2000, from)
    if (sneak) b.input({})
    await L.sleep(800) // 연타 잠금 (놓친 뒤 12틱) 밖으로
    return r
  }
  const OFF = [
    ['parrying_dagger', 'parrying_dagger', 9],
    ['plank_shield', 'small_shield', 7],
    ['pilgrim_buckler', 'small_shield', 7],
    ['redin_guard_shield', 'medium_shield', 5],
    ['alley_dagger', 'dagger', 4],
    ['volk_greatshield', 'greatshield', 0],
    ['gaoler_greatsword', 'greatsword', 0]
  ]
  for (const [id, cls, w] of OFF) {
    await b.cmd(`/soulstest give ${id} off`, 'GIVE')
    await L.sleep(300)
    if (id === 'alley_dagger') {
      // 왼손에 든 무기는 막지 않는다 (막기 성분이 떼어진다: 왼손 무기의 우클릭은 왼손 공격, 검토 offhand-guard-weapons-still-block)
      await L.sleep(400)
      sc.check('a dagger in the off hand has no blocks_attacks (an off-hand weapon does not guard, like the parrying dagger)',
        !comps(b, 45).includes('blocks_attacks') && comps(b, 45).includes('item_model') && !comps(b, 36).includes('blocks_attacks'),
        `main ${comps(b, 36).join(',')} / off ${comps(b, 45).join(',')}`)
    }
    const r = await press()
    if (w > 0) {
      sc.check(`F with ${id} in the off hand: parry window ${w} ticks (class ${cls})`, r && r.line.startsWith('[T] PARRY ') && r.kv.item === id &&
        r.kv.class === cls && r.kv.base === String(w) && r.kv.window === String(w) && r.kv.ring === '0', r ? r.line : '줄 없음')
    } else {
      sc.check(`F with ${id} in the off hand: cannot parry, F does nothing (PARRY_NONE)`, r && r.line.startsWith('[T] PARRY_NONE') && r.kv.item === id &&
        r.kv.class === cls && r.kv.why === 'cannot', r ? r.line : '줄 없음')
    }
  }
  await b.cmd('/item replace entity @s weapon.offhand with air', null, 1200)
  await L.sleep(300)
  {
    const r = await press()
    sc.check('F with an empty off hand: no parry (combat.parry.empty 0)', r && r.line.startsWith('[T] PARRY_NONE') && r.kv.class === 'empty' && r.kv.why === 'cannot', r ? r.line : '줄 없음')
  }
  // 패링 반지 +2틱
  await b.cmd('/soulstest give plank_shield off', 'GIVE')
  await b.cmd('/soulstest ring equip 1 test_parry', 'RING_SET')
  await L.sleep(300)
  {
    const r = await press()
    sc.check('parry ring adds 2 ticks (small shield 7 -> 9)', r && r.line.startsWith('[T] PARRY ') && r.kv.ring === '2' && r.kv.window === '9', r ? r.line : '줄 없음')
  }
  await b.cmd('/soulstest ring equip 1 none', 'RING_SET')
  // 연타 잠금: 놓친 패링 뒤 12틱 안의 F 는 창을 열지 않는다
  {
    let from = b.sys.length
    b.swap()
    await L.sleep(150)
    b.swap()
    await L.sleep(500)
    const lines = b.tLines('PARRY', from)
    sc.check('pressing F again within 12 ticks is locked (PARRY then PARRY_LOCKED)', lines.length === 2 && lines[0].line.startsWith('[T] PARRY ') &&
      lines[1].line.startsWith('[T] PARRY_LOCKED') && L.num(lines[1].kv.since) < 12 && lines[1].kv.lock === '12', lines.map((x) => x.line).join(' | '))
    await L.sleep(800)
    from = b.sys.length
  }

  // ── 패링 단검은 막지 않고, 왼손에 무엇이든 있으면 주무기도 막지 않는다 ──
  await b.cmd('/soulstest give parrying_dagger off', 'GIVE')
  await L.sleep(700)
  sc.check('parrying dagger in the off hand has no blocks_attacks (it does not guard)', !comps(b, 45).includes('blocks_attacks') && comps(b, 45).includes('item_model'), comps(b, 45).join(','))
  sc.check('with the parrying dagger in the off hand the club does not guard either (right click is the left hand)', !comps(b, 36).includes('blocks_attacks'), comps(b, 36).join(','))
  const one = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('off-hand dagger: one-handed (strength not x1.5)', one.kv && one.kv.twohand === 'false' && one.kv.weapon === 'gaoler_club', one.line || '')
  await b.cmd('/item replace entity @s weapon.offhand with air', null, 1200)
  await L.sleep(700)
  sc.check('empty off hand: the club guards (two-handed guard)', comps(b, 36).includes('blocks_attacks'), comps(b, 36).join(','))
  const two = await b.cmd('/soulstest stats', 'STATS ')
  sc.check('empty off hand: two-handed, strength 10 counts as 15 (club 74 x 1.19 = 88.1)', two.kv && two.kv.twohand === 'true' &&
    Math.abs(L.num(two.kv.atk) - 74 * 1.19) <= 0.51, two.line || '')
  await b.cmd('/soulstest give plank_shield off', 'GIVE')
  await L.sleep(700)
  sc.check('shield back in the off hand: the club stops guarding', !comps(b, 36).includes('blocks_attacks') && comps(b, 45).includes('blocks_attacks'),
    `main ${comps(b, 36).join(',')} / off ${comps(b, 45).join(',')}`)

  // ── 예전 판의 무기를 지금 판으로 (검토 stale-weapons-outside-inventory) ──
  // 옛 판처럼 설명 칸에 옛 줄 ("Str Bonus C") 이 구워진 무기를 만든다: 바닐라 /item modify 로 설명을 갈아 끼운다
  const STALE = '{function:"minecraft:set_lore",lore:["Str Bonus C"],mode:"replace_all"}'
  const fresh = (it) => {
    const j = JSON.stringify((it && it.components) || [])
    return j.includes('souls.weapon.stat.attack') && !j.includes('Str Bonus C')
  }
  const at = b.bot.entity.position.floored()
  const cx = at.x + 2, cy = at.y, cz = at.z
  const staleChest = async () => {
    await b.cmd('/soulstest give redin_guard_sword main', 'GIVE')
    await L.sleep(300)
    await b.cmd(`/setblock ${cx} ${cy} ${cz} minecraft:chest`, null, 1000)
    await b.cmd(`/item replace block ${cx} ${cy} ${cz} container.0 from entity @s weapon.mainhand`, null, 1000)
    const m = await b.cmd(`/item modify block ${cx} ${cy} ${cz} container.0 ${STALE}`, null, 1000)
    await b.cmd('/clear @s', null, 1200)
    return m
  }
  {
    // 창 (souls 세계는 상자 블록을 열지 못하게 막으므로 엔더 상자 창: /soulstest enderchest) 을 열면 그 칸이 바뀐다
    await b.cmd('/soulstest give redin_guard_sword main', 'GIVE')
    await L.sleep(300)
    await b.cmd('/item replace entity @s enderchest.0 from entity @s weapon.mainhand', null, 1000)
    const m = await b.cmd(`/item modify entity @s enderchest.0 ${STALE}`, null, 1000)
    await b.cmd('/clear @s', null, 1200)
    const from = b.sys.length
    let win = null
    const opened = new Promise((resolve) => b.bot.once('windowOpen', (w) => resolve(w)))
    await b.cmd('/soulstest enderchest', 'ENDERCHEST')
    win = await Promise.race([opened, L.sleep(3000).then(() => null)])
    const r = await b.waitT('WEAPON_REFRESH', 3000, from)
    sc.check('opening a container (ender chest) rebuilds a stale weapon inside (WEAPON_REFRESH n=1 where=container)', r && r.kv.n === '1' && r.kv.where === 'container',
      (r ? r.line : '줄 없음') + ' | modify: ' + (m.line || '-'))
    sc.check('the ender chest copy now has the one-row stat table, not the old row', win && fresh(win.slots[0]),
      win && win.slots[0] ? JSON.stringify(win.slots[0].components).slice(0, 300) : '칸 없음')
    if (win) b.bot.closeWindow(win)
    await L.sleep(400)
    await b.cmd('/item replace entity @s enderchest.0 with minecraft:air', null, 1000)
  }
  {
    // 땅에서 주우면 다음 틱에 바뀐다 (상자를 부숴 옛 무기를 떨군다)
    await staleChest()
    const from = b.sys.length
    const slots = b.p.slots.length
    await b.cmd(`/setblock ${cx} ${cy} ${cz} minecraft:air destroy`, null, 1000)
    await L.sleep(300)
    await b.cmd(`/tp @s ${cx + 0.5} ${cy} ${cz + 0.5}`, null, 1500)
    const r = await b.waitT('WEAPON_REFRESH', 5000, from)
    sc.check('picking a stale weapon up from the ground rebuilds it (WEAPON_REFRESH n=1 where=pickup)', r && r.kv.n === '1' && r.kv.where === 'pickup', r ? r.line : '줄 없음')
    await L.sleep(400)
    const it = lastItem(b, slots, 'souls.weapon.redin_guard_sword.name')
    sc.check('the picked-up sword shows the one-row stat table', it && it.lore.some((l) => L.translateKeys(l).includes('souls.weapon.stat.attack')) &&
      !it.lore.some((l) => L.render(l, {}).includes('Str Bonus C')), it ? it.lore.map((l) => L.translateKeys(l).join('+') || L.render(l, {})).join(' | ') : '칸 없음')
    await b.cmd('/kill @e[type=item,distance=..6]', null, 800)
  }
  {
    // /souls reload: 든 무기도 새 값으로
    await b.cmd('/clear @s', null, 1200)
    await b.cmd('/soulstest give redin_guard_sword main', 'GIVE')
    await L.sleep(300)
    await b.cmd(`/item modify entity @s weapon.mainhand ${STALE}`, null, 1000)
    const from = b.sys.length
    await b.cmd('/souls reload', null, 4000)
    const r = await b.waitT('WEAPON_REFRESH', 4000, from)
    sc.check('/souls reload rebuilds a stale weapon in the inventory (WEAPON_REFRESH n=1 where=reload)', r && r.kv.n === '1' && r.kv.where === 'reload', r ? r.line : '줄 없음')
    const after = b.sys.length
    await b.cmd('/souls reload', null, 4000)
    await L.sleep(500)
    sc.check('a current weapon is not rebuilt again (no WEAPON_REFRESH on the second reload)', !b.tLines('WEAPON_REFRESH', after).length, b.tLines('WEAPON_REFRESH', after).map((x) => x.line).join(' | '))
  }
  {
    // 예전 판의 부싯돌 방패 (껍데기를 바닐라 방패로 바꾸기 전) 는 다시 들어올 때 바닐라 방패로 바뀐다
    await b.cmd('/clear @s', null, 1200)
    const m = await b.cmd('/item replace entity @s weapon.offhand with minecraft:flint[custom_data={PublicBukkitValues:{"souls:weapon":"plank_shield"}},' +
      'item_model="souls:plank_shield"]', null, 1200)
    await L.sleep(400)
    const before = b.bot.inventory.slots[45]
    sc.check('an old flint plank shield sits in the off hand before rejoining', before && before.name === 'flint', (before ? before.name : '없음') + ' | ' + (m.line || ''))
    await b.quit()
    await L.sleep(1500)
    const b2 = await L.connect(sc)
    const r = await b2.waitT('WEAPON_REFRESH', 6000, 0)
    sc.check('rejoining rebuilds the flint shield (WEAPON_REFRESH n=1 where=join)', r && r.kv.n === '1' && r.kv.where === 'join', r ? r.line : '줄 없음')
    await L.sleep(600)
    const after = b2.bot.inventory.slots[45]
    sc.check('the off hand now holds a vanilla-shield-shelled plank shield with the guard', after && after.name === 'shield' &&
      JSON.stringify(after.components || []).includes('souls.weapon.plank_shield.name') && (after.components || []).some((c) => c.type === 'blocks_attacks'),
      after ? after.name + ' ' + (after.components || []).map((c) => c.type).join(',') : '없음')
    // 빈털터리의 시작 장비로 되돌린다 (뒤 시나리오)
    await b2.cmd('/clear @s', null, 1200)
    await b2.cmd('/soulstest give gaoler_club main', 'GIVE')
    await b2.cmd('/soulstest give plank_shield off', 'GIVE')
    sc.check('no kick after rejoining', !b2.kick, b2.kick || '')
  }
  sc.check('no kick during gear scenario', !b.kick, b.kick || '')
})
