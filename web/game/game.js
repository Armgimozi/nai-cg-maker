/* 별빛 소녀 컬렉션 — 클라이언트.
   모든 판정은 서버가 한다. 여기서는 서버가 돌려준 상태를 그리고,
   뽑기·전투 결과를 연출로 재생하기만 한다. */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const num = n => (n ?? 0).toLocaleString('ko-KR');
const sleep = ms => new Promise(r => setTimeout(r, ms));

const PID_KEY = 'starlight.pid';
let CAT = null;   // 카탈로그(정적 데이터)
let ST = null;    // 내 상태
let CH = {};      // id → 캐릭터
let banner = null;
let dexFilter = 'all';

/* ─────────────────────────────────────────── 통신 */
async function api(path, body) {
  const res = await fetch('/api/game' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Player': localStorage.getItem(PID_KEY) || '',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = {};
  try { data = await res.json(); } catch (_) { /* 빈 응답 */ }
  if (!res.ok) {
    const err = new Error(data.error || `요청 실패 (${res.status})`);
    err.code = data.code; err.data = data;
    throw err;
  }
  return data;
}

function toast(msg, bad) {
  const el = document.createElement('div');
  el.className = 'toast' + (bad ? ' bad' : '');
  el.textContent = msg;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), 2600);
}

/* ─────────────────────────────────────────── 초상화 */
/* SVG 그라디언트 id 는 문서 전체에서 유일해야 한다. 같은 캐릭터가 여러 곳에
   그려질 때 id 가 겹치면 브라우저가 첫 번째(숨겨진 탭 안일 수도 있는) 정의를
   집어 색이 통째로 빠지는 문제가 있었다. 인스턴스마다 새 id 를 발급한다. */
let svgSeq = 0;
function svgPortrait(c) {
  const [a, b] = c.palette;
  const k = 'p' + (++svgSeq);
  const init = (c.name || '?').slice(0, 1);
  const el = (CAT.elements[c.element] || {}).color || '#fff';
  return `<svg class="portrait" viewBox="0 0 90 120" preserveAspectRatio="xMidYMid slice">
    <defs>
      <linearGradient id="g${k}" x1="0" y1="0" x2="0.4" y2="1">
        <stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/>
      </linearGradient>
      <radialGradient id="r${k}" cx="50%" cy="26%" r="60%">
        <stop offset="0" stop-color="#fff" stop-opacity=".6"/>
        <stop offset="1" stop-color="#fff" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="s${k}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#2a2448" stop-opacity=".72"/>
        <stop offset="1" stop-color="#0d0b1e" stop-opacity=".92"/>
      </linearGradient>
    </defs>
    <rect width="90" height="120" fill="url(#g${k})"/>
    <rect width="90" height="120" fill="url(#r${k})"/>
    <text x="45" y="52" text-anchor="middle" font-size="42" font-weight="800"
          fill="#fff" opacity=".22" font-family="sans-serif">${init}</text>
    <g fill="url(#s${k})">
      <path d="M45 84c-14 0-24 8-28 20-1 4-2 9-2 16h60c0-7-1-12-2-16-4-12-14-20-28-20z"/>
      <ellipse cx="45" cy="70" rx="11" ry="13"/>
      <path d="M31 72c-3-16 4-26 14-26s17 10 14 26c-1-9-5-14-14-14s-13 5-14 14z"/>
      <path d="M30 66c-4 6-5 14-4 22l4-1zM60 66c4 6 5 14 4 22l-4-1z"/>
    </g>
    <circle cx="76" cy="14" r="5.5" fill="${el}" opacity=".92"/>
  </svg>`;
}
function portrait(c) {
  return c.art
    ? `<img class="portrait" src="${c.art}" alt="${c.name}" loading="lazy">`
    : svgPortrait(c);
}
function stars(n) { return '★'.repeat(n); }
function rarityClass(r) { return 'r' + r; }

/* 캐릭터 카드(도감/편성 공용) */
function unitCard(c, entry, opts = {}) {
  const owned = !!entry;
  const el = (CAT.elements[c.element] || {}).color || '#fff';
  return `<div class="unit ${rarityClass(c.rarity)} ${owned ? '' : 'locked'}"
               data-char="${c.id}">
    ${portrait(c)}
    ${owned ? `<span class="lv">Lv.${entry.level}</span>` : ''}
    <span class="el" style="background:${el}">${c.element[0]}</span>
    <span class="stars">${stars(c.rarity)}${
      owned && entry.ascend ? ` +${entry.ascend}` : ''}</span>
    <span class="nm">${owned ? c.name : '???'}</span>
  </div>`;
}

/* ─────────────────────────────────────────── 부팅 */
async function boot() {
  CAT = await api('/catalog');
  CAT.characters.forEach(c => { CH[c.id] = c; });
  const pid = localStorage.getItem(PID_KEY) || '';
  ST = await api('/session', { pid });
  localStorage.setItem(PID_KEY, ST.pid);
  banner = CAT.banners[0];
  renderAll();
  setInterval(tickStamina, 1000);
}

function apply(res) {
  if (res && res.state) ST = res.state;
  renderAll();
}

function renderAll() {
  renderWallet();
  renderHome();
  renderGacha();
  renderBattleList();
  renderDex();
  renderShop();
}

/* ─────────────────────────────────────────── 상단바 */
function renderWallet() {
  const c = ST.currency;
  $('#curStardust').innerHTML = `✦ <b>${num(c.stardust)}</b>`;
  $('#curEssence').innerHTML = `◆ <b>${num(c.essence)}</b>`;
  $('#curGold').innerHTML = `◎ <b>${num(c.gold)}</b>`;
  $('#curStamina').innerHTML = `⚡ <b>${ST.stamina.value}/${ST.stamina.max}</b>`;
  $('#playerName').textContent = ST.name;
  $('#avatar').textContent = (ST.name || '별').slice(0, 1);
  $('#playerPower').textContent = `전투력 ${num(ST.team_power)}`;
}

let staminaLeft = 0;
function tickStamina() {
  if (!ST) return;
  if (ST.stamina.value >= ST.stamina.max) return;
  staminaLeft = Math.max(0, staminaLeft - 1);
  if (staminaLeft <= 0) {
    ST.stamina.value = Math.min(ST.stamina.max, ST.stamina.value + 1);
    staminaLeft = CAT.limits.regen_sec;
    renderWallet();
  }
}

/* ─────────────────────────────────────────── 홈 */
function renderHome() {
  const feature = CH[banner ? banner.art_hint : 'seraphine'] || CAT.characters[0];
  const art = $('#heroArt');
  if (feature.art) { art.style.backgroundImage = `url(${feature.art})`; }
  else { art.innerHTML = svgPortrait(feature); art.style.opacity = .32; }
  $('#heroQuote').textContent = feature.quote;

  // 출석
  const lg = ST.login;
  $('#streakLabel').textContent = `${lg.streak}일 연속`;
  $('#loginRow').innerHTML = lg.rewards.map(r => {
    const label = r.ticket ? `🎟${r.ticket}` : r.gold ? `◎${r.gold / 1000}k` : `✦${r.stardust}`;
    const cls = r.day < lg.day || (r.day === lg.day && lg.claimed) ? 'done'
      : r.day === lg.day ? 'now' : '';
    return `<div class="lday ${cls}"><b>${r.day}</b>${label}</div>`;
  }).join('');
  const btn = $('#loginClaim');
  btn.disabled = lg.claimed;
  btn.textContent = lg.claimed ? '오늘 출석 완료' : `${lg.day}일차 보상 받기`;

  // 미션
  $('#missionList').innerHTML = ST.missions.map(m => `
    <div class="mission">
      <div class="mtext">
        <b>${m.name}</b>
        <div class="bar"><i style="width:${m.progress / m.goal * 100}%"></i></div>
        <span class="sub" style="margin:0">${m.progress}/${m.goal} · 보상 ✦${m.reward}</span>
      </div>
      <button class="btn ${m.complete && !m.claimed ? 'primary' : ''}"
              data-mission="${m.id}" ${m.complete && !m.claimed ? '' : 'disabled'}>
        ${m.claimed ? '완료' : '받기'}</button>
    </div>`).join('');

  renderTeam('#teamRow');
  renderTeam('#teamRow2');
  $('#teamPower').textContent = num(ST.team_power);
  $('#teamPower2').textContent = num(ST.team_power);
  $('#pidHint').textContent = `플레이어 ID: ${ST.pid.slice(0, 8)}… (이 브라우저에 저장됨)`;
}

function renderTeam(sel) {
  const el = $(sel);
  if (!el) return;
  const cells = [];
  for (let i = 0; i < 4; i++) {
    const cid = ST.team[i];
    if (!cid) { cells.push('<div class="slot">비어 있음</div>'); continue; }
    cells.push(unitCard(CH[cid], ST.roster[cid]));
  }
  el.innerHTML = cells.join('');
}

/* ─────────────────────────────────────────── 소환 */
function renderGacha() {
  $('#bannerTabs').innerHTML = CAT.banners.map(b =>
    `<button class="chip ${b.id === banner.id ? 'on' : ''}" data-banner="${b.id}">${b.name}</button>`
  ).join('');

  const feature = CH[banner.art_hint];
  const up = banner.pickup5.map(id => CH[id].name).join(', ');
  $('#bannerBox').innerHTML = `
    <div class="bg" ${feature.art ? `style="background-image:url(${feature.art})"` : ''}>
      ${feature.art ? '' : `<div style="opacity:.35;height:100%">${svgPortrait(feature)}</div>`}
    </div>
    ${banner.kind === 'limited' ? '<span class="badge">픽업</span>' : ''}
    <div class="txt"><h2>${banner.name}</h2>
      <p>${banner.subtitle}${up ? ` · ${up} 확정 천장 있음` : ''}</p></div>`;

  const pity = ST.pity[banner.pity_key] || { c5: 0, c4: 0, g5: false };
  const left5 = 90 - pity.c5;
  $('#pityBox').innerHTML = `
    <div class="pcell ${pity.c5 >= 74 ? 'warn' : ''}"><b>${pity.c5}</b>5★ 천장까지 ${left5}회</div>
    <div class="pcell"><b>${pity.c4}</b>4★ 보장까지 ${10 - pity.c4}회</div>
    <div class="pcell ${pity.g5 ? 'warn' : ''}"><b>${pity.g5 ? '확정' : '50%'}</b>다음 5★ 픽업</div>`;

  const cost = CAT.costs;
  const sd = ST.currency.stardust, tk = ST.currency.ticket;
  $('#pull1').innerHTML = `1회 소환<small>✦ ${num(cost.pull)}</small>`;
  $('#pull10').innerHTML = `10연 소환<small>✦ ${num(cost.pull10)} · 4★ 이상 보장</small>`;
  $('#pull1').disabled = sd < cost.pull;
  $('#pull10').disabled = sd < cost.pull10;
  $('#pullTicket1').innerHTML = `🎟 1회<small>소환권 ${tk}장 보유</small>`;
  $('#pullTicket10').innerHTML = `🎟 10연<small>소환권 10장 필요</small>`;
  $('#pullTicket1').disabled = tk < 1;
  $('#pullTicket10').disabled = tk < 10;

  $('#pullTotal').textContent = `누적 ${num(ST.pulls.total)}회`;
  $('#historyList').innerHTML = [...ST.history].reverse().slice(0, 60).map(h =>
    `<span class="hitem ${rarityClass(h.rarity)}">${CH[h.char].name}${
      h.pickup ? ' ⭐' : ''}</span>`).join('') || '<span class="hint">아직 기록이 없습니다.</span>';
}

async function doPull(count, ticket) {
  try {
    const res = await api('/pull', { banner: banner.id, count, ticket });
    ST = res.state;
    renderWallet();
    await playPull(res.results, count);
    renderAll();
  } catch (e) {
    if (e.code === 'no_stardust') {
      toast(`별가루가 ${num(e.data.need)} 부족합니다.`, true);
      showTab('shop');
    } else toast(e.message, true);
  }
}

async function playPull(results, count) {
  const ov = $('#pullOverlay'), box = $('#pullCards');
  box.className = 'pull-cards' + (count === 1 ? ' single' : '');
  box.innerHTML = '';
  $('#pullDone').hidden = true;
  $('#pullSkip').hidden = count === 1;
  ov.hidden = false;

  let cancelled = false;
  $('#pullSkip').onclick = () => { cancelled = true; };

  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    const c = CH[r.char];
    const tag = r.new ? '<span class="tag new">NEW</span>'
      : r.pickup ? '<span class="tag">PICK</span>'
        : r.shards ? `<span class="tag">조각+${r.shards}</span>`
          : `<span class="tag">성흔 ${r.ascend}</span>`;
    const div = document.createElement('div');
    div.className = `pcard ${rarityClass(r.rarity)}`;
    div.innerHTML = `${portrait(c)}${r.rarity >= 4 || r.new ? tag : ''}
      <span class="nm">${stars(r.rarity)} ${c.name}</span>`;
    box.append(div);
    if (!cancelled) await sleep(r.rarity === 5 ? 420 : r.rarity === 4 ? 180 : 90);
  }
  $('#pullSkip').hidden = true;
  $('#pullDone').hidden = false;
  await new Promise(res => { $('#pullDone').onclick = res; });
  ov.hidden = true;
}

/* ─────────────────────────────────────────── 전투 */
function renderBattleList() {
  const byCh = {};
  CAT.stages.forEach(s => (byCh[s.chapter] ||= []).push(s));
  const out = [];
  for (const [chId, list] of Object.entries(byCh)) {
    const el = list[0].element;
    const color = (CAT.elements[el] || {}).color;
    out.push(`<div class="chapter"><h2>
      <span style="color:${color}">◆</span> ${chId}장 · ${list[0].chapter_name}</h2>`);
    list.forEach((s, i) => {
      const rec = ST.stages[s.key] || {};
      const prev = i === 0 ? null : list[i - 1];
      const prevCleared = i === 0
        ? (chId === '1' || (ST.stages[`${+chId - 1}-6`] || {}).cleared)
        : (ST.stages[prev.key] || {}).cleared;
      const locked = !prevCleared && !rec.cleared;
      out.push(`<div class="stage ${s.boss ? 'boss' : ''} ${rec.cleared ? 'cleared' : ''}
                     ${locked ? 'locked' : ''}" data-stage="${locked ? '' : s.key}">
        <div class="no">${s.boss ? 'BOSS' : `${s.chapter}-${s.stage}`}</div>
        <div class="info"><b>${s.name}</b>
          <span>⚡${s.stamina} · ◎${num(s.reward.gold)}${
            rec.cleared ? '' : ` · 최초 ✦${s.reward.stardust_first}`}</span></div>
        <div class="btn ${locked ? '' : 'primary'}" style="padding:8px 14px;font-size:12px">
          ${locked ? '잠김' : rec.cleared ? '재도전' : '도전'}</div>
      </div>`);
    });
    out.push('</div>');
  }
  $('#chapterList').innerHTML = out.join('');
}

async function doBattle(key) {
  try {
    const res = await api('/battle', { stage: key });
    ST = res.state;
    renderWallet();
    await playBattle(res.battle, res.rewards, res.stage);
    renderAll();
  } catch (e) {
    if (e.code === 'no_stamina') { toast('스태미나가 부족합니다.', true); showTab('shop'); }
    else toast(e.message, true);
  }
}

async function playBattle(b, rewards, stage) {
  const ov = $('#battleOverlay');
  const allies = b.units.filter(u => u.side === 'ally');
  const foes = b.units.filter(u => u.side === 'enemy');
  const cell = (u, foe) => `<div class="bunit" id="bu_${u.uid}">
      <div class="bn">
        ${u.portrait && CH[u.portrait]
          ? `<span class="bface">${portrait(CH[u.portrait])}</span>` : ''}
        <span>${u.name}</span></div>
      <div class="hpbar ${foe ? 'foe' : ''}"><i style="width:100%"></i>
        <span class="sh" style="transform:scaleX(0)"></span></div>
    </div>`;
  $('#bAllies').innerHTML = allies.map(u => cell(u, false)).join('');
  $('#bEnemies').innerHTML = foes.map(u => cell(u, true)).join('');
  $('#bLog').innerHTML = '';
  $('#bDone').hidden = true;
  $('#bSkip').hidden = false;
  ov.hidden = false;

  let fast = false;
  $('#bSkip').onclick = () => { fast = true; };

  for (const e of b.log) {
    if (e.text) {
      const line = document.createElement('div');
      if (e.kind === 'end') line.className = b.win ? 'win' : 'lose';
      line.textContent = e.text;
      $('#bLog').append(line);
      $('#bLog').scrollTop = $('#bLog').scrollHeight;
    }
    (e.state || []).forEach(s => {
      const el = $('#bu_' + s.uid);
      if (!el) return;
      el.querySelector('.hpbar i').style.width = (s.hp / s.max * 100) + '%';
      el.querySelector('.sh').style.transform =
        `scaleX(${Math.min(1, s.shield / s.max)})`;
      el.classList.toggle('dead', s.hp <= 0);
    });
    if (e.tgt) {
      const el = $('#bu_' + e.tgt);
      if (el) { el.classList.add('hit'); setTimeout(() => el.classList.remove('hit'), 250); }
    }
    if (!fast) await sleep(e.kind === 'skill' ? 380 : 240);
  }

  if (rewards.length) {
    const line = document.createElement('div');
    line.className = 'win';
    line.textContent = '보상 ' + rewards.map(r =>
      (r.kind === 'gold' ? '◎' : '✦') + num(r.amount) +
      (r.reason ? `(${r.reason})` : '')).join(' · ');
    $('#bLog').append(line);
    $('#bLog').scrollTop = $('#bLog').scrollHeight;
  }
  $('#bSkip').hidden = true;
  $('#bDone').hidden = false;
  await new Promise(res => { $('#bDone').onclick = res; });
  ov.hidden = true;
}

/* ─────────────────────────────────────────── 도감 */
function renderDex() {
  const owned = Object.keys(ST.roster).length;
  $('#dexCount').textContent = `수집 ${owned} / ${CAT.characters.length}명`;
  const list = CAT.characters.filter(c => {
    if (dexFilter === 'all') return true;
    if (dexFilter === 'owned') return !!ST.roster[c.id];
    return String(c.rarity) === dexFilter;
  }).sort((a, b) => b.rarity - a.rarity ||
    (!!ST.roster[b.id]) - (!!ST.roster[a.id]) || a.name.localeCompare(b.name));
  $('#dexGrid').innerHTML = list.map(c => unitCard(c, ST.roster[c.id])).join('');
}

function openChar(cid) {
  const c = CH[cid], e = ST.roster[cid];
  const el = CAT.elements[c.element] || {};
  const inTeam = ST.team.includes(cid);
  const s = e ? e.stats : c.base;
  const rows = [['체력', s.hp], ['공격력', s.atk], ['방어력', s.def], ['속도', s.spd]];
  showModal(`
    <h2>${stars(c.rarity)} ${c.name}</h2>
    <div class="role">${c.title} · <span style="color:${el.color}">${c.element}</span> · ${c.role}
      ${e ? ` · Lv.${e.level}/${e.cap}${e.ascend ? ` · 성흔 ${e.ascend}` : ''}` : ''}</div>
    <div class="detail">
      <div class="pic">${portrait(c)}</div>
      <div style="flex:1">
        ${rows.map(([k, v]) => `<div class="stat"><span>${k}</span><b>${num(v)}</b></div>`).join('')}
        ${e ? `<div class="stat"><span>전투력</span><b>${num(e.power)}</b></div>` : ''}
      </div>
    </div>
    <div class="skill"><b>${c.skill.name}</b>${c.skill.desc}</div>
    <div class="quote">"${c.quote}"</div>
    ${e ? `
      <div class="row-btns">
        <button class="btn primary" style="flex:1" id="mLv"
          ${e.level >= e.cap || ST.currency.gold < e.cost ? 'disabled' : ''}>
          레벨업 ◎${num(e.cost)}</button>
        <button class="btn" style="flex:1" id="mLv10"
          ${e.level >= e.cap ? 'disabled' : ''}>10회 레벨업</button>
      </div>
      <button class="btn wide ${inTeam ? '' : 'primary'}" style="margin-top:8px" id="mTeam">
        ${inTeam ? '편성에서 빼기' : '편성에 넣기'}</button>
      ${e.shards ? `<p class="hint">보유 조각 ${e.shards}개 (성흔 최대치 도달분)</p>` : ''}`
      : '<p class="hint">아직 만나지 못한 소녀입니다. 소환에서 만나보세요.</p>'}`);

  if (!e) return;
  $('#mLv').onclick = async () => {
    try { apply(await api('/levelup', { char: cid, times: 1 })); closeModal(); openChar(cid); }
    catch (err) { toast(err.message, true); }
  };
  $('#mLv10').onclick = async () => {
    try {
      const r = await api('/levelup', { char: cid, times: 10 });
      toast(`${r.levels}레벨 상승 (◎${num(r.gold_spent)} 사용)`);
      apply(r); closeModal(); openChar(cid);
    } catch (err) { toast(err.message, true); }
  };
  $('#mTeam').onclick = async () => {
    let team = [...ST.team];
    if (inTeam) team = team.filter(x => x !== cid);
    else if (team.length >= 4) { toast('편성은 최대 4명입니다.', true); return; }
    else team.push(cid);
    apply(await api('/team', { team }));
    closeModal();
  };
}

/* ─────────────────────────────────────────── 상점 */
function renderShop() {
  const sh = CAT.shop;
  $('#staminaBtn').innerHTML =
    `⚡ +${sh.stamina_amount} 충전 <small style="opacity:.7">◆${sh.stamina_cost}</small>`;
  $('#staminaBtn').disabled = ST.currency.essence < sh.stamina_cost;

  const mp = sh.monthly;
  const active = ST.shop.monthly_until * 1000 > Date.now();
  const rows = [`
    <div class="pkg hot">
      <div class="gem" style="background:linear-gradient(150deg,#ffd873,#e0a028)">🌙</div>
      <div class="pinfo"><b>${mp.name}</b><span>${mp.desc}</span></div>
      <button class="buy" data-pkg="${mp.id}">
        ${active ? '연장' : ''} ₩${num(mp.price_krw)}</button>
    </div>`];

  sh.packages.forEach(p => {
    const first = !(ST.shop.purchased[p.id] > 0);
    const total = (p.essence + p.bonus) * (first ? sh.first_purchase_mult : 1);
    rows.push(`<div class="pkg ${p.tag ? 'hot' : ''}">
      ${p.tag ? `<span class="tagline">${p.tag}</span>` : ''}
      <div class="gem">◆</div>
      <div class="pinfo">
        <b>${p.name} ◆${num(total)}${first ? '<span class="first">첫 구매 2배</span>' : ''}</b>
        <span>기본 ${num(p.essence)}${p.bonus ? ` + 보너스 ${num(p.bonus)}` : ''}</span>
      </div>
      <button class="buy" data-pkg="${p.id}">₩${num(p.price_krw)}</button>
    </div>`);
  });
  $('#shopList').innerHTML = rows.join('');
  $('#spentHint').textContent =
    `모의 결제 누적: ₩${num(ST.shop.spent_krw)} — 실제로 청구되지 않은 금액입니다.`;
}

/* ─────────────────────────────────────────── 모달 */
function showModal(html) { $('#modalBody').innerHTML = html; $('#modal').hidden = false; }
function closeModal() { $('#modal').hidden = true; }

function showRates() {
  const d = banner.disclosure;
  showModal(`
    <h2>확률 공시</h2>
    <div class="role">${banner.name}</div>
    <p class="hint" style="margin-top:0">기본 확률 (천장·보장 적용 전)</p>
    <table class="rate-table">${d.rows.map(r =>
      `<tr><td>${r.label}</td><td>${r.rate}</td></tr>`).join('')}</table>
    <p class="hint">종합 확률 (천장·보장까지 반영한 실제 기댓값)</p>
    <table class="rate-table">${d.effective.map(r =>
      `<tr><td>${r.label}</td><td>${r.rate}</td></tr>`).join('')}</table>
    <p class="hint"><b>${d.expected}</b></p>
    <ul class="rate-note">${d.notes.map(n => `<li>${n}</li>`).join('')}</ul>`);
}

/* ─────────────────────────────────────────── 탭 */
function showTab(name) {
  $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
  $$('.page').forEach(p => { p.hidden = p.id !== 'page-' + name; });
  window.scrollTo(0, 0);
}

/* ─────────────────────────────────────────── 이벤트 */
document.addEventListener('click', async ev => {
  const t = ev.target;

  const tab = t.closest('#tabs button');
  if (tab) return showTab(tab.dataset.tab);

  const bt = t.closest('[data-banner]');
  if (bt) { banner = CAT.banners.find(b => b.id === bt.dataset.banner); return renderGacha(); }

  const unit = t.closest('[data-char]');
  if (unit) return openChar(unit.dataset.char);

  const stage = t.closest('[data-stage]');
  if (stage && stage.dataset.stage) return doBattle(stage.dataset.stage);

  const chip = t.closest('.filters .chip');
  if (chip) {
    dexFilter = chip.dataset.filter;
    $$('.filters .chip').forEach(c => c.classList.toggle('on', c === chip));
    return renderDex();
  }

  const mission = t.closest('[data-mission]');
  if (mission) {
    try {
      const r = await api('/claim/mission', { id: mission.dataset.mission });
      toast(`✦${num(r.granted.stardust)} 획득`);
      return apply(r);
    } catch (e) { return toast(e.message, true); }
  }

  const pkg = t.closest('[data-pkg]');
  if (pkg) {
    const id = pkg.dataset.pkg;
    const p = CAT.shop.packages.find(x => x.id === id) || CAT.shop.monthly;
    if (!confirm(`[모의 결제] ${p.name} — ₩${num(p.price_krw)}\n`
      + '실제 금액은 청구되지 않습니다. 진행할까요?')) return;
    try {
      const r = await api('/shop/buy', { package: id });
      toast(`◆${num(r.granted.essence)} 지급${r.first ? ' (첫 구매 2배!)' : ''}`);
      return apply(r);
    } catch (e) { return toast(e.message, true); }
  }
});

$('#pull1').onclick = () => doPull(1, false);
$('#pull10').onclick = () => doPull(10, false);
$('#pullTicket1').onclick = () => doPull(1, true);
$('#pullTicket10').onclick = () => doPull(10, true);
$('#showRates').onclick = showRates;
$('#rateBtn').onclick = showRates;
$('#modalClose').onclick = closeModal;
$('#modal').onclick = e => { if (e.target.id === 'modal') closeModal(); };

$('#loginClaim').onclick = async () => {
  try {
    const r = await api('/claim/login', {});
    toast(Object.entries(r.granted).map(([k, v]) =>
      ({ stardust: '✦', gold: '◎', ticket: '🎟' }[k] + num(v))).join(' · ') + ' 획득');
    apply(r);
  } catch (e) { toast(e.message, true); }
};

$('#staminaBtn').onclick = async () => {
  try { apply({ state: await api('/shop/stamina', {}) }); toast('스태미나를 충전했습니다.'); }
  catch (e) { toast(e.message, true); }
};

$('#exBtn').onclick = async () => {
  const amount = parseInt($('#exAmount').value, 10) || 0;
  try {
    apply({ state: await api('/shop/exchange', { amount }) });
    toast(`✦${num(amount)} 로 교환했습니다.`);
  } catch (e) { toast(e.message, true); }
};

$('#profileBtn').onclick = async () => {
  const name = prompt('감독관 이름을 입력하세요 (최대 16자)', ST.name);
  if (name === null) return;
  apply({ state: await api('/profile', { name }) });
};

$('#resetBtn').onclick = async () => {
  if (!confirm('정말 초기화할까요? 보유 캐릭터·재화가 모두 사라집니다.')) return;
  apply({ state: await api('/reset', {}) });
  toast('초기화했습니다.');
};

boot().catch(e => {
  document.body.innerHTML =
    `<div style="padding:40px;text-align:center;color:#ffc7d3">불러오지 못했습니다.<br>${e.message}</div>`;
});
