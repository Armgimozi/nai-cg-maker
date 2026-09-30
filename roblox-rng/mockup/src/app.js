'use strict';
// 랜드마크 RNG UI 미리보기.
// src/client/Ui.luau · Hud.luau · Panels.luau 의 크기/위치/색을 그대로 옮긴 작은 "로블록스 GUI 흉내" 입니다.
//  - UDim2(scale, offset) + AnchorPoint + Rotation -> CSS left/top/width/height + transform
//  - UIScale(Ui.autoScale) -> transform: scale() (AnchorPoint 기준)
//  - UIStroke(Border) -> box-shadow (테두리 바깥쪽), UIStroke(Contextual, 글자) -> -webkit-text-stroke + paint-order
//  - 9-slice 스킨(ScaleType.Slice, SliceCenter = 여백..256-여백, SliceScale) -> canvas 에 9조각으로 다시 그림 (paintSkins)
//  - ImageColor3(곱하기) -> SVG feColorMatrix 필터, ImageTransparency -> opacity
//  - TextScaled + UITextSizeConstraint -> 상자에 맞을 때까지 글자 크기를 줄임(최대값까지)
// ImageIds 가 모두 채워졌다고 가정(그림 버전). ViewportFrame(명소 3D 모형)은 "3D 모형 자리"로 대신 그립니다.
(function () {
  const GAME = window.GAME;
  const ART = window.ART;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const SHOT_MODE = /[?&]shot=1/.test(location.search);

  // --- Ui.luau 상수 -------------------------------------------------------------
  const GUI_INSET = 58; // 로블록스 기본 상단바 (ScreenGui.IgnoreGuiInset = false)
  // Ui.autoScale 배율: clamp(min(화면 가로/1280, 화면 세로/720), 0.55, 0.9) — 화면(카메라 ViewportSize) 전체 기준
  const uiScaleFor = (w, h) => Math.min(0.9, Math.max(0.55, Math.min(w / 1280, h / 720)));
  // 지금 그리는 화면 (newScreen 이 정함). 1280x720 -> 배율 0.9
  //   inset: 로블록스 상단바 높이(ScreenGui 는 그 아래에서 시작), touch: 터치 전용 기기(Ui.touchOnly — 조이스틱·점프 버튼이 뜨고 키캡은 안 보임)
  //   menu: 이 화면에서 잡은 메뉴 배치(layoutMenu 결과, 위 가운데 묶음이 비켜 갈 때 씀)
  const view = { w: 1280, h: 720, scale: uiScaleFor(1280, 720), inset: GUI_INSET, touch: false, menu: null };
  const SHADOW_DEPTH = 6;
  const BUTTON_CORNER = 14;
  // Ui.SKINS: 그림 속 바깥 모서리 반지름 / SliceCenter 여백 (SliceCenter = 여백..256-여백)
  const SKIN_SIZE = 256;
  const SKINS = {
    button_face: { radius: 50, margin: 64 },
    button_shadow: { radius: 50, margin: 64 },
    panel_paper: { radius: 46, margin: 64 },
    pill: { radius: 64, margin: 64 },
    tag: { radius: 44, margin: 46 },
  };
  const DEFAULT_SKIN = { radius: 50, margin: 64 };
  const skinSpec = (name) => SKINS[name] || DEFAULT_SKIN;
  const PILL_ART_OPACITY = 0.62;
  // Ui.ribbon 치수: 판 높이 50 기준, k = 판 높이/50 으로 늘이고 줄임. 꼬리 그림(ribbon_tail_l/r, 56x50)은 판 양 끝 뒤에
  const RIBBON_BASE_HEIGHT = 50;
  const RIBBON_TAIL = { w: 56, h: 50, left: -36, top: 17 }; // 오른쪽 꼬리는 왼쪽을 뒤집은 자리
  const RIBBON_SHADE = 9;
  const RIBBON_CORNER = 12;
  const CLOSE_ART_SIZE = 60;
  const RIBBON_HEIGHT = 50; // Ui.window 제목 리본 판 높이
  const BODY_TOP = 45; // Ui.window: 창 위 끝에서 본문까지
  // ?tails=frame: 꼬리 그림(ImageIds.ribbon_tail_l/r)이 아직 비어 있을 때의 둥근 네모 Frame 꼬리로 그림
  const TAIL_ART = !/[?&]tails=frame/.test(location.search);
  const CHIP_PAD = 0.42;
  const CHIP_ICON_PAD = 0.12;

  const WHITE = [255, 255, 255];
  const Theme = {
    Ink: [30, 27, 46],
    Cream: [255, 244, 220],
    Paper: [255, 230, 176],
    PaperDark: [222, 178, 104],
  };
  const COLORS = {
    Sky: { Face: [57, 160, 255], Shadow: [31, 111, 204] },
    Grass: { Face: [76, 217, 100], Shadow: [46, 158, 69] },
    Sun: { Face: [255, 197, 61], Shadow: [217, 144, 15] },
    Coral: { Face: [255, 94, 91], Shadow: [201, 58, 56] },
    Grape: { Face: [155, 107, 255], Shadow: [106, 69, 201] },
    Gray: { Face: [172, 170, 190], Shadow: [116, 112, 138] },
  };
  // Ui.colorPair: 색 이름 또는 [r, g, b](그림자 = Ink 쪽으로 35%) 또는 { Face, Shadow }
  const colorPair = (name) =>
    Array.isArray(name) ? { Face: name, Shadow: lerp(name, Theme.Ink, 0.35) } : name && name.Face ? name : COLORS[name] || COLORS.Gray;

  // Hud.luau / Panels.luau 상수
  const INCOME_GREEN = [150, 255, 150];
  const ODDS_COLOR = [120, 112, 150];
  const FEATURED_BG = [255, 218, 128];
  const DIM_CHIP = [172, 170, 190];

  // --- 색 도우미 ----------------------------------------------------------------
  const lerp = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
  const css = (c, alpha = 1) => {
    const [r, g, b] = c.map((v) => Math.round(v));
    return alpha >= 1 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${+alpha.toFixed(3)})`;
  };
  const hex = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  const escapeHtml = (s) =>
    String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  // 로블록스 RichText <font color> -> span, 공백 두 칸 유지
  const rich = (s) =>
    s.replace(/<font color="(#[0-9a-f]{6})">/gi, '<span style="color:$1">').replace(/<\/font>/g, '</span>').replace(/ {2}/g, '  ');

  // ImageColor3 = 곱하기 색. 같은 색은 필터 하나를 같이 씀
  const filters = new Map();
  function tintFilter(color) {
    const key = hex(color);
    if (!filters.has(key)) {
      const id = 'tint' + filters.size;
      const root = document.getElementById('filters');
      const filter = document.createElementNS(SVG_NS, 'filter');
      filter.setAttribute('id', id);
      filter.setAttribute('color-interpolation-filters', 'sRGB');
      filter.setAttribute('x', '-5%');
      filter.setAttribute('y', '-5%');
      filter.setAttribute('width', '110%');
      filter.setAttribute('height', '110%');
      const matrix = document.createElementNS(SVG_NS, 'feColorMatrix');
      matrix.setAttribute('type', 'matrix');
      const [r, g, b] = color.map((v) => (v / 255).toFixed(4));
      matrix.setAttribute('values', `${r} 0 0 0 0  0 ${g} 0 0 0  0 0 ${b} 0 0  0 0 0 1 0`);
      filter.appendChild(matrix);
      root.appendChild(filter);
      filters.set(key, id);
    }
    return `url(#${filters.get(key)})`;
  }
  function applyLook(element, color, transparency = 0) {
    const isWhite = !color || (color[0] >= 255 && color[1] >= 255 && color[2] >= 255);
    element.style.filter = isWhite ? '' : tintFilter(color);
    if (transparency) element.style.opacity = String(1 - transparency);
  }

  // --- 게임 데이터 (build.py 가 Landmarks.luau / Config.luau 에서 읽어 넣음) --------
  const Config = GAME.Config;
  const Tiers = GAME.Landmarks.Tiers;
  function tierFor(oneIn) {
    for (let i = Tiers.length - 1; i >= 0; i--) if (oneIn >= Tiers[i].MinOneIn) return Tiers[i];
    return Tiers[0];
  }
  const Regions = GAME.Landmarks.Regions;
  const RegionById = {};
  Regions.forEach((r) => (RegionById[r.Id] = r));
  if (GAME.Landmarks.WorldRegion) RegionById[GAME.Landmarks.WorldRegion.Id] = GAME.Landmarks.WorldRegion;
  const List = GAME.Landmarks.List.map((l) => ({ ...l, Tier: tierFor(l.OneIn) })).sort((a, b) => a.OneIn - b.OneIn);
  const RarestFirst = [...List].reverse();
  const ById = {};
  List.forEach((l) => (ById[l.Id] = l));
  const ByRegion = {};
  Object.keys(RegionById).forEach((id) => (ByRegion[id] = []));
  List.forEach((l) => ByRegion[l.Region] && ByRegion[l.Region].push(l));

  // --- PlayerState.luau (읽기 함수만) ------------------------------------------------
  const UpgradesById = {};
  Config.Upgrades.forEach((u) => (UpgradesById[u.Id] = u));
  const upgradeLevel = (s, id) => s.Upgrades[id] || 0;
  function upgradePrice(id, level) {
    const u = UpgradesById[id];
    if (!u || level >= u.MaxLevel) return null;
    return Math.floor(u.BasePrice * Math.pow(u.Growth, level));
  }
  // PlayerState.isDiscovered: 역대 발견(Discovered — 자동 발견 포함) 또는 지금 보유. 도감·대륙 도장은 이것 기준
  const isDiscovered = (s, id) => !!(s.Discovered && s.Discovered[id]) || (s.Inventory[id] || 0) > 0;
  const countsForStamp = (l) => l.Tier.Rank <= Config.STAMP_MAX_RANK;
  function regionProgress(s, regionId) {
    let found = 0;
    let required = 0;
    for (const l of ByRegion[regionId] || []) {
      if (countsForStamp(l)) {
        required += 1;
        if (isDiscovered(s, l.Id)) found += 1;
      }
    }
    return [found, required];
  }
  const completedRegions = (s) =>
    Regions.filter((r) => {
      const [found, required] = regionProgress(s, r.Id);
      return required > 0 && found >= required;
    }).map((r) => r.Id);
  function luck(s) {
    const globe = UpgradesById.Globe;
    return (
      Config.BASE_LUCK *
      (1 + globe.PerLevel * upgradeLevel(s, 'Globe')) *
      (1 + Config.REGION_LUCK_BONUS * completedRegions(s).length) *
      Math.pow(Config.REBIRTH_LUCK_MULT, rebirthsOf(s))
    );
  }
  const slots = (s) => Config.BASE_SLOTS + UpgradesById.Park.PerLevel * upgradeLevel(s, 'Park');
  // PlayerState.stars: 가챠 중복처럼 처음 발견 = 별 0, 또 뽑을 때마다 +1 (STAR_THRESHOLDS = 2,3,4,5,6 -> 6번째 = ★5)
  const MAX_STARS = Config.STAR_THRESHOLDS.length;
  function stars(count) {
    let n = 0;
    Config.STAR_THRESHOLDS.forEach((threshold, i) => {
      if (count >= threshold) n = i + 1;
    });
    return n;
  }
  // PlayerState.slotCell: 칸 번호(1..) -> [row(1 = 입구 쪽 줄), column(1 = 입구에서 공원 안쪽을 볼 때 왼쪽 끝)].
  // 입구 쪽 줄부터, 한 줄 안에서는 가운데에 가까운 칸부터(가운데 오른쪽 -> 가운데 왼쪽 -> …)
  const GRID = Config.PARK_GRID || 6;
  const MAX_SLOTS = GRID * GRID;
  const SLOT_CELLS = (() => {
    const middle = (GRID + 1) / 2;
    const columns = Array.from({ length: GRID }, (_, i) => i + 1).sort((a, b) => {
      const da = Math.abs(a - middle);
      const db = Math.abs(b - middle);
      return da !== db ? da - db : a - b;
    });
    const cells = [];
    for (let row = 1; row <= GRID; row++) for (const c of columns) cells.push([row, GRID + 1 - c]);
    return cells;
  })();
  // PlayerState.parkSlots: [칸마다 명소 Id(0번 = 1번 칸, 빈 칸 null), 열린 칸 수]
  // 자동 배치(Settings.AutoPark 가 false 가 아님) = 희귀한 순서로 1번 칸부터, 직접 배치 = Display(보유·안 겹침·열린 칸만)
  function parkSlots(s) {
    const unlocked = Math.max(0, Math.min(slots(s), MAX_SLOTS));
    const result = new Array(unlocked).fill(null);
    if (!s.Settings || s.Settings.AutoPark !== false) {
      let i = 0;
      for (const l of RarestFirst) {
        if (i >= unlocked) break;
        if ((s.Inventory[l.Id] || 0) > 0) result[i++] = l.Id;
      }
    } else {
      const seen = new Set();
      const display = s.Display || [];
      for (let i = 0; i < unlocked; i++) {
        const id = display[i];
        if (typeof id === 'string' && !seen.has(id) && ById[id] && (s.Inventory[id] || 0) > 0) {
          seen.add(id);
          result[i] = id;
        }
      }
    }
    return [result, unlocked];
  }
  const park = (s) => parkSlots(s)[0].filter(Boolean);
  // PlayerState.setDisplay: 칸 하나에 명소 놓기(이미 다른 칸이면 자리 바꿈) / null = 빼기. 자동 배치 중이면 지금 배치에서 시작.
  // expected(선택) = 요청한 쪽이 본 그 칸의 명소 Id("" = 빈 칸) — 지금 보이는 것과 다르면 거절("stale")
  function setDisplay(s, slot, id, expected) {
    const [current, unlocked] = parkSlots(s);
    if (!Number.isInteger(slot) || slot < 1 || slot > unlocked) return false;
    if (id != null && !(ById[id] && (s.Inventory[id] || 0) > 0)) return false;
    if (expected != null && (current[slot - 1] || '') !== expected) return false;
    const display = current.map((v) => v || '');
    if (id) {
      const from = display.indexOf(id);
      if (from >= 0 && from !== slot - 1) display[from] = display[slot - 1] || '';
    }
    while (display.length < slot) display.push('');
    display[slot - 1] = id || '';
    while (display.length && display[display.length - 1] === '') display.pop();
    s.Display = display;
    s.Settings = { ...s.Settings, AutoPark: false };
    return true;
  }
  // PlayerState.betterHidden: 직접 배치 중 전시 칸의 가장 약한 명소보다 수입이 큰, 전시 안 된 보유 명소(희귀한 순서).
  // 전시가 하나도 없으면 수입이 있는 보유 명소 전부, 자동 배치면 [] — HUD [공원] 버튼 숫자 배지
  function betterHidden(s) {
    if (!s.Settings || s.Settings.AutoPark !== false) return [];
    const [ids, unlocked] = parkSlots(s);
    if (unlocked <= 0) return [];
    const shown = new Set(ids.filter(Boolean));
    let weakest = null;
    for (const id of shown) {
      const v = landmarkIncome(ById[id], s.Inventory[id] || 0);
      weakest = weakest == null ? v : Math.min(weakest, v);
    }
    const floor = weakest ?? 0;
    return RarestFirst.filter((l) => (s.Inventory[l.Id] || 0) > 0 && !shown.has(l.Id) && landmarkIncome(l, s.Inventory[l.Id]) > floor).map((l) => l.Id);
  }
  // PlayerState.missedByFullPark: 직접 배치 중 이번 판에 처음 얻은(보유 1개) 명소가 빈 칸이 없어 전시 못 됨 -> "공원 꽉 참" 알림
  function missedByFullPark(s, id) {
    if (!s.Settings || s.Settings.AutoPark !== false || (s.Inventory[id] || 0) !== 1) return false;
    const [ids, unlocked] = parkSlots(s);
    for (let slot = 1; slot <= unlocked; slot++) if (!ids[slot - 1] || ids[slot - 1] === id) return false;
    return true;
  }

  // PlayerState.landmarkIncome: 보유(1개 이상)면 등급 수입 × (1 + 별 보너스 × 별). 처음 발견(☆0) = 등급 수입 그대로
  function landmarkIncome(l, count) {
    if (!(count > 0)) return 0;
    return (Config.TIER_INCOME[l.Tier.Rank - 1] || 0) * (1 + Config.STAR_INCOME_BONUS * stars(count));
  }
  function incomePerSecond(s) {
    let total = 0;
    for (const id of park(s)) total += landmarkIncome(ById[id], s.Inventory[id]);
    return total * (1 + UpgradesById.Ticket.PerLevel * upgradeLevel(s, 'Ticket'));
  }
  const discoveryBonus = (l) => Math.ceil(Config.DISCOVERY_BONUS_MULT * Math.pow(l.OneIn, 0.5));
  // PlayerState.rebirthRequirement / Perks.rebirthCheck (HUD 환생 버튼의 "!" 배지)
  const rebirthsOf = (s) => Math.max(0, Math.floor(s.Rebirths || 0));
  function rebirthRequirement(rebirths) {
    const steps = Config.REBIRTHS || [];
    if (!steps.length) return null;
    const n = rebirths + 1;
    const step = steps[Math.min(n, steps.length) - 1];
    const coins = n > steps.length ? step.Coins * Math.pow(Config.REBIRTH_COIN_GROWTH, n - steps.length) : step.Coins;
    return { Coins: coins, Landmarks: step.Landmarks };
  }
  function rebirthReady(s, coins) {
    const need = rebirthRequirement(rebirthsOf(s));
    if (!need) return false;
    const missing = need.Landmarks.filter((id) => ById[id] && (s.Inventory[id] || 0) <= 0);
    return missing.length === 0 && Math.floor(coins) >= need.Coins;
  }

  // --- Format.luau ------------------------------------------------------------------
  function commas(n) {
    const negative = n < 0;
    const digits = String(Math.floor(Math.abs(n)));
    const out = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return negative ? '-' + out : out;
  }
  function short(n) {
    for (const [unit, suffix] of [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']]) {
      if (n >= unit) {
        const value = n / unit;
        const text = value >= 100 ? String(Math.floor(value)) : (Math.floor(value * 10) / 10).toFixed(1).replace(/\.0$/, '');
        return text + suffix;
      }
    }
    return commas(n);
  }
  const oneIn = (n) => '1 in ' + commas(n); // Format.oneIn: 항상 콤마 자연수
  const multiplier = (x) => 'x' + x.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
  const times = (x) => '×' + multiplier(x).slice(1); // Ui.times
  // Hud.luau incomeText
  const incomeText = (income) =>
    income < 100 ? (Math.floor(income * 10) / 10).toFixed(1).replace(/\.0$/, '') : short(income);
  // Ui.starsRich
  function starsRich(count, max = 5, emptyColor = [226, 212, 182]) {
    const filled = Math.max(0, Math.min(max, Math.floor(count)));
    return `<span style="color:${hex(COLORS.Sun.Face)}">${'★'.repeat(filled)}</span><span style="color:${hex(emptyColor)}">${'★'.repeat(max - filled)}</span>`;
  }
  // Hud starUpText: 별 상승 딱지 = 채운 별(금색) + 빈 별 + "+1", 별이 가득 차면(★5) "MAX"
  function starUpText(count) {
    const n = Math.max(1, Math.min(MAX_STARS, Math.floor(count)));
    return starsRich(n, MAX_STARS) + (n >= MAX_STARS ? ' MAX' : ' +1');
  }
  const starUpPlain = (count) => {
    const n = Math.max(1, Math.min(MAX_STARS, Math.floor(count)));
    return '★'.repeat(n) + '☆'.repeat(MAX_STARS - n) + (n >= MAX_STARS ? ' MAX' : ' +1');
  };

  // --- 로블록스 GuiObject 흉내 ----------------------------------------------------------
  const ud = (scale, offset) => {
    if (!scale) return `${offset}px`;
    if (!offset) return `${scale * 100}%`;
    return `calc(${scale * 100}% + ${offset}px)`;
  };

  // o: { pos:[sx,ox,sy,oy], size:[sx,ox,sy,oy], anchor:[ax,ay], rot, z, bg, bgT, corner(px|'round'),
  //      stroke:[color, thickness, transparency], clip, flow(UIListLayout/UIGridLayout 자식), autoW, uiScale, visible, name }
  function gui(parent, o = {}) {
    const d = document.createElement('div');
    d.className = 'g' + (o.cls ? ' ' + o.cls : '');
    if (o.name) d.dataset.name = o.name;
    const s = d.style;
    const size = o.size || [0, 0, 0, 0];
    if (o.flow) d.classList.add('flow');
    else {
      const p = o.pos || [0, 0, 0, 0];
      s.left = ud(p[0], p[1]);
      s.top = ud(p[2], p[3]);
    }
    if (o.autoW) {
      d.classList.add('auto-w');
      if (size[1]) s.minWidth = size[1] + 'px';
    } else s.width = ud(size[0], size[1]);
    s.height = ud(size[2], size[3]);
    const a = o.anchor || [0, 0];
    const transform = [];
    if (a[0] || a[1]) transform.push(`translate(${-a[0] * 100}%, ${-a[1] * 100}%)`);
    if (o.uiScale && o.uiScale !== 1) {
      s.transformOrigin = `${a[0] * 100}% ${a[1] * 100}%`;
      transform.push(`scale(${o.uiScale})`);
    }
    if (o.rot) transform.push(`rotate(${o.rot}deg)`);
    if (transform.length) s.transform = transform.join(' ');
    s.zIndex = String(o.z ?? 1);
    if (o.bg) s.backgroundColor = css(o.bg, 1 - (o.bgT || 0));
    if (o.corner != null) s.borderRadius = o.corner === 'round' ? '9999px' : o.corner + 'px';
    if (o.stroke) stroke(d, ...o.stroke);
    if (o.clip) s.overflow = 'hidden';
    if (o.visible === false) s.display = 'none';
    if (parent) parent.appendChild(d);
    return d;
  }

  // UIStroke (Border): 바깥쪽 테두리
  function stroke(d, color = Theme.Ink, thickness = 3, transparency = 0) {
    d.style.boxShadow = `0 0 0 ${thickness}px ${css(color, 1 - transparency)}`;
  }

  // Ui.list
  function list(el, dir, gap, hAlign = 'left', vAlign = 'center') {
    const map = { left: 'flex-start', center: 'center', right: 'flex-end', top: 'flex-start', bottom: 'flex-end' };
    el.style.display = 'flex';
    el.style.flexDirection = dir === 'h' ? 'row' : 'column';
    el.style.gap = gap + 'px';
    if (dir === 'h') {
      el.style.justifyContent = map[hAlign];
      el.style.alignItems = map[vAlign];
    } else {
      el.style.alignItems = map[hAlign];
      el.style.justifyContent = map[vAlign];
    }
  }

  // UIGridLayout (FillDirectionMaxCells + HorizontalAlignment)
  function gridLayout(el, cellW, cellH, gap, maxCells, align, width) {
    const fit = Math.max(1, Math.floor((width + gap) / (cellW + gap)));
    el.style.display = 'grid';
    el.style.gridTemplateColumns = `repeat(${Math.min(fit, maxCells)}, ${cellW}px)`;
    el.style.gridAutoRows = cellH + 'px';
    el.style.gap = gap + 'px';
    el.style.justifyContent = align === 'center' ? 'center' : 'start';
    el.style.alignContent = 'start';
  }

  function sliceScale(name, radius, height) {
    const spec = skinSpec(name);
    let scale = radius / spec.radius;
    if (height != null) scale = Math.min(scale, height / 2 / spec.margin);
    return scale;
  }

  // Ui.skin / Ui.box: 9-slice 그림을 대상 맨 뒤(ZIndex 0)에 깔고 대상의 바탕·테두리는 끔
  // o: { radius, height, scale(SliceScale 직접), centerColor(늘어나는 가운데 조각을 덮는 평면 색), color, transparency }
  function skin(target, name, o = {}) {
    target.style.backgroundColor = 'transparent';
    target.style.boxShadow = 'none';
    const img = document.createElement('div');
    img.className = 'skin';
    img.dataset.skin = name;
    if (o.radius != null || o.scale != null) {
      // border-image 는 조각 사이에 가는 틈(이음새)이 생겨서, 화면을 다 만든 뒤 paintSkins 가 canvas 로 다시 그림
      const margin = skinSpec(name).margin;
      const scale = o.scale ?? sliceScale(name, o.radius, o.height);
      const w = margin * scale;
      img.dataset.slice = String(w);
      img.dataset.margin = String(margin);
      img.dataset.scale = String(scale);
      if (o.centerColor) img.dataset.center = css(o.centerColor);
      img.style.borderImage = `url(${ART[name]}) ${margin} fill / ${+w.toFixed(3)}px stretch`;
    } else {
      img.classList.add('stretch');
      img.style.backgroundImage = `url(${ART[name]})`;
    }
    applyLook(img, o.color, o.transparency || 0);
    target.insertBefore(img, target.firstChild);
    return img;
  }

  // 9-slice 를 canvas 한 장에 그림 (SliceCenter 여백..256-여백, 모서리 = 여백 x SliceScale).
  // 조각 경계를 정수 픽셀에 맞춰서 이음새가 없음. 물들이기(ImageColor3)는 부모 div 의 SVG 필터가 그대로 맡음.
  // data-center: Ui 의 CenterColor (가운데 조각 위 평면 Frame) — 물들이지 않는 종이에만 씀
  const imageCache = {};
  function loadImage(name) {
    if (!imageCache[name]) {
      imageCache[name] = new Promise((resolve) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => resolve(null);
        image.src = ART[name];
      });
    }
    return imageCache[name];
  }
  async function paintSkins(root) {
    const OVERSAMPLE = 2;
    for (const el of root.querySelectorAll('.skin[data-slice]')) {
      const image = await loadImage(el.dataset.skin);
      const width = el.clientWidth;
      const height = el.clientHeight;
      if (!image || !width || !height) continue;
      const cw = Math.max(1, Math.round(width * OVERSAMPLE));
      const ch = Math.max(1, Math.round(height * OVERSAMPLE));
      let border = Number(el.dataset.slice) * OVERSAMPLE;
      border *= Math.min(1, cw / (2 * border), ch / (2 * border)); // CSS/로블록스처럼 너무 크면 줄임
      const b = Math.round(border);
      const size = image.naturalWidth;
      const margin = (size * Number(el.dataset.margin || 64)) / SKIN_SIZE;
      const src = [0, margin, size - margin, size];
      const xs = [0, b, cw - b, cw];
      const ys = [0, b, ch - b, ch];
      const canvas = document.createElement('canvas');
      canvas.width = cw;
      canvas.height = ch;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      for (let j = 0; j < 3; j++) {
        for (let i = 0; i < 3; i++) {
          const dw = xs[i + 1] - xs[i];
          const dh = ys[j + 1] - ys[j];
          if (dw <= 0 || dh <= 0) continue;
          ctx.drawImage(image, src[i], src[j], src[i + 1] - src[i], src[j + 1] - src[j], xs[i], ys[j], dw, dh);
        }
      }
      if (el.dataset.center && cw > 2 * b && ch > 2 * b) {
        ctx.fillStyle = el.dataset.center;
        ctx.fillRect(b, b, cw - 2 * b, ch - 2 * b);
      }
      canvas.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;display:block';
      el.style.borderImage = 'none';
      el.appendChild(canvas);
    }
  }

  // Ui.label: TextScaled + 최대 크기, 기본 FredokaOne / Ink 글자 / 가운데 정렬
  function label(parent, o, max = 28) {
    const d = gui(parent, o);
    d.classList.add('lbl');
    if (o.font === 'title') d.classList.add('title');
    const span = document.createElement('span');
    if (o.rich != null) span.innerHTML = rich(o.rich);
    else span.textContent = o.text ?? '';
    d.appendChild(span);
    const xa = o.xAlign || 'center';
    d.style.justifyContent = { left: 'flex-start', right: 'flex-end', center: 'center' }[xa];
    d.style.textAlign = xa;
    d.style.color = css(o.color || Theme.Ink, 1 - (o.textT || 0));
    if (o.wrap) {
      // TextScaled = false + TextWrapped + TextTruncate: 글자 크기 고정, 길면 두 줄(넘치면 …)
      d.classList.add('wrap2');
      span.style.fontSize = (o.textSize ?? max) + 'px';
      span.style.setProperty('--lines', String(o.lines || 2));
    } else if (o.scaled === false) {
      d.classList.add('nowrap');
      span.style.fontSize = Math.min(o.textSize ?? 14, max) + 'px';
    } else d.dataset.fit = String(max);
    if (o.yAlign) d.style.alignItems = { top: 'flex-start', bottom: 'flex-end', center: 'center' }[o.yAlign];
    if (o.outline) outline(d, o.outline, o.outlineColor);
    return d;
  }
  // Ui.outline (UIStroke Contextual): 글자 바깥쪽 테두리
  function outline(d, thickness = 2, color = Theme.Ink) {
    d.classList.add('stroked');
    d.style.setProperty('--sw', thickness * 2 + 'px');
    d.style.setProperty('--sc', css(color));
  }

  // 그림이 없는 아이콘(plane, ticket)은 게임에서 3D 미니 모형 -> 비슷한 모양으로 대신 그림
  const svgUri = (body) =>
    'data:image/svg+xml;utf8,' + encodeURIComponent(`<svg xmlns="${SVG_NS}" viewBox="0 0 100 100">${body}</svg>`);
  const ICON3D = {
    plane: svgUri(`<g transform="rotate(-14 50 58)">
      <path d="M44 53 L58 53 L68 28 L59 28 Z" fill="#2a78d0"/>
      <path d="M13 57 L26 57 L22 30 L13 30 Z" fill="#ff5e5b"/>
      <rect x="11" y="50" width="72" height="17" rx="8.5" fill="#f4f6fb"/>
      <rect x="11" y="59" width="72" height="8" rx="4" fill="#d9dfeb"/>
      <circle cx="83" cy="58.5" r="8.5" fill="#f4f6fb"/>
      <rect x="71" y="50.5" width="10" height="5" rx="1.5" fill="#263e8c"/>
      <path d="M40 61 L61 61 L50 90 L33 90 Z" fill="#39a0ff"/>
      <path d="M9 58 L27 58 L23 67 L7 67 Z" fill="#39a0ff"/></g>`),
    ticket: svgUri(`<g transform="rotate(-12 50 50)">
      <rect x="10" y="30" width="60" height="40" rx="3" fill="#ff5e5b"/>
      <rect x="10" y="64" width="60" height="6" rx="2" fill="#d94b48"/>
      <rect x="72" y="30" width="19" height="40" rx="3" fill="#ffc53d"/>
      <rect x="72" y="64" width="19" height="6" rx="2" fill="#dba42c"/>
      <rect x="19" y="44" width="42" height="12" rx="2" fill="#fff4dc"/></g>`),
    // Icons.BUILDERS.podium: 1·2·3등 시상대(왼쪽 Sky 2등 · 가운데 Sun 1등 · 오른쪽 Coral 3등) + 1등 위 작은 금색 별
    podium: svgUri(`<g stroke="#1e1b2e" stroke-width="3" stroke-linejoin="round">
      <rect x="4" y="50" width="31" height="45" rx="3" fill="#39a0ff"/>
      <rect x="34.5" y="34" width="31" height="61" rx="3" fill="#ffc53d"/>
      <rect x="65" y="63" width="31" height="32" rx="3" fill="#ff5e5b"/>
      <path d="M50 2 L53.76 11.82 L64.27 12.36 L56.09 18.98 L58.82 29.14 L50 23.4 L41.18 29.14 L43.91 18.98 L35.73 12.36 L46.24 11.82 Z" fill="#ffce40"/></g>
      <g fill="#ffffff" opacity="0.4"><rect x="8" y="54" width="23" height="5" rx="2"/><rect x="38.5" y="38" width="23" height="5" rx="2"/><rect x="69" y="67" width="23" height="5" rx="2"/></g>`),
    // Icons.BUILDERS.arrange: 잔디 판 위 2×2 칸 — 세 칸에 색 블록(미니 명소), 앞 오른쪽은 빈 칸 초록 "+"
    arrange: svgUri(`<rect x="4" y="34" width="92" height="60" rx="10" fill="#60c45a" stroke="#1e1b2e" stroke-width="3"/>
      <g fill="#fff4dc" stroke="#1e1b2e" stroke-width="2"><rect x="11" y="40" width="37" height="22" rx="4"/><rect x="52" y="40" width="37" height="22" rx="4"/>
      <rect x="11" y="66" width="37" height="22" rx="4"/><rect x="52" y="66" width="37" height="22" rx="4"/></g>
      <g stroke="#1e1b2e" stroke-width="2.5" stroke-linejoin="round"><rect x="19" y="24" width="21" height="31" rx="3" fill="#39a0ff"/>
      <rect x="60" y="8" width="21" height="47" rx="3" fill="#ffc53d"/><rect x="19" y="60" width="21" height="22" rx="3" fill="#ff5e5b"/></g>
      <path d="M70.5 70 v14 M63.5 77 h14" stroke="#2e9e45" stroke-width="5" stroke-linecap="round"/>`),
    // Icons.BUILDERS.crate(배치 모드 [보관]): 뚜껑이 뒤로 열린 나무 상자 + 안에서 나온 파란 탑(금색 꼭지)
    crate: svgUri(`<g stroke="#1e1b2e" stroke-width="3" stroke-linejoin="round">
      <path d="M14 30 L86 30 L80 8 L20 8 Z" fill="#c8894f"/>
      <rect x="38" y="16" width="16" height="26" rx="2" fill="#39a0ff"/><rect x="42" y="8" width="8" height="8" rx="1" fill="#ffc53d"/>
      <rect x="10" y="38" width="80" height="54" rx="4" fill="#c8894f"/></g>
      <g fill="#8a5a33"><rect x="10" y="50" width="80" height="6"/><rect x="10" y="72" width="80" height="6"/><rect x="12" y="40" width="7" height="50"/><rect x="81" y="40" width="7" height="50"/></g>`),
    // Icons.BUILDERS.camera(배치 모드 [시점]): 사진기 — 몸통 + 금속 띠 + 렌즈 + 뷰파인더 + 빨간 셔터 단추
    camera: svgUri(`<g stroke="#1e1b2e" stroke-width="3" stroke-linejoin="round">
      <rect x="24" y="18" width="24" height="14" rx="3" fill="#3a3a48"/><rect x="66" y="18" width="12" height="10" rx="3" fill="#ff5e5b"/>
      <rect x="8" y="28" width="84" height="56" rx="8" fill="#3a3a48"/><rect x="8" y="46" width="84" height="14" fill="#b9c0cc"/>
      <circle cx="54" cy="56" r="20" fill="#b9c0cc"/><circle cx="54" cy="56" r="11" fill="#39a0ff"/></g>
      <circle cx="50" cy="52" r="4" fill="#ffffff" opacity="0.7"/>`),
    // Icons.BUILDERS.rebirth: 금색 고리 화살표 2개(100°~, 280°~ 각 4조각 + 화살촉) + 가운데 초록 위 화살표
    rebirth: svgUri(`<g fill="none" stroke="#ffc53d" stroke-width="11">
      <path d="M 53 16.1 A 34 34 0 0 0 19.2 64.4"/><path d="M 47 83.9 A 34 34 0 0 0 80.8 35.6"/></g>
      <path d="M 5.4 70.8 L 33 58 L 27.5 82.2 Z" fill="#ffc53d"/>
      <path d="M 94.6 29.2 L 67 42 L 72.5 17.8 Z" fill="#ffc53d"/>
      <rect x="45.1" y="49.5" width="9.8" height="16.6" fill="#60c45a"/>
      <path d="M 36.6 50 L 63.4 50 L 50 33.9 Z" fill="#60c45a"/>`),
  };

  // Icons.view: 그림 아이콘 (ScaleType.Fit)
  function iconView(parent, name, o = {}) {
    const d = gui(parent, { ...o, size: o.size || [1, 0, 1, 0] });
    d.classList.add('icon');
    d.dataset.icon = name;
    const img = document.createElement('img');
    img.alt = '';
    img.src = ART[name] || ICON3D[name] || ART.star;
    if (!ART[name]) d.dataset.fallback3d = '1';
    applyLook(img, o.color, o.transparency || 0);
    d.appendChild(img);
    return d;
  }

  // Ui.keyCap
  function keyCap(parent, key, o = {}) {
    const size = o.size || 26;
    const cap = gui(parent, {
      name: 'Key' + key,
      anchor: o.anchor || [0.5, 0.5],
      pos: o.pos || [0, 0, 0, 0],
      size: [0, size, 0, size],
      bg: Theme.Cream,
      rot: o.rot ?? -8,
      z: o.z ?? 7,
      corner: 7,
      stroke: [Theme.Ink, 2.5],
      visible: !view.touch, // UserInputService.KeyboardEnabled
    });
    label(cap, { name: 'Key', text: key, size: [1, 0, 1, 0], z: 2 }, Math.floor(size * 0.72));
    return cap;
  }

  // Ui.chunkyButton (스킨 버전: button_shadow / button_face 를 색으로 물들임)
  function chunkyButton(parent, o) {
    const height = o.size[3];
    const faceHeight = Math.max(12, height - SHADOW_DEPTH);
    const round = o.round === true;
    const vertical = o.vertical === true;
    const iconSize = o.iconSize || Math.floor(faceHeight * (vertical ? 0.58 : 0.8));
    const skinRadius = round ? faceHeight / 2 : o.cornerRadius || BUTTON_CORNER;
    const pair = colorPair(o.color || 'Sky');
    const root = gui(parent, {
      name: o.name || 'Button',
      pos: o.pos,
      size: o.size,
      anchor: o.anchor,
      z: o.z,
      flow: o.flow,
      visible: o.visible,
    });
    const shadow = gui(root, { name: 'Shadow', pos: [0, 0, 0, SHADOW_DEPTH], size: [1, 0, 1, -SHADOW_DEPTH], z: 1 });
    skin(shadow, 'button_shadow', { radius: skinRadius, height: faceHeight, color: pair.Shadow });
    const face = gui(root, { name: 'Face', size: [1, 0, 1, -SHADOW_DEPTH], z: 2 });
    skin(face, 'button_face', { radius: skinRadius, height: faceHeight, color: pair.Face });

    const text = o.text || '';
    let icon = null;
    let labelPos = [0, 8, 0, 4];
    let labelSize = [1, -16, 1, -8];
    if (o.icon && text === '') {
      icon = iconView(face, o.icon, { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [0, iconSize, 0, iconSize], z: 3 });
    } else if (o.icon && vertical) {
      icon = iconView(face, o.icon, { anchor: [0.5, 0], pos: [0.5, 0, 0, 3], size: [0, iconSize, 0, iconSize], z: 3 });
      labelPos = [0, 4, 0, iconSize + 2];
      labelSize = [1, -8, 1, -(iconSize + 6)];
    } else if (o.icon) {
      icon = iconView(face, o.icon, { anchor: [0, 0.5], pos: [0, 6, 0.5, 0], size: [0, iconSize, 0, iconSize], z: 3 });
      labelPos = [0, iconSize + 8, 0, 4];
      labelSize = [1, -(iconSize + 16), 1, -8];
    }
    const lbl = label(
      face,
      { name: 'Label', text, color: WHITE, z: 4, pos: o.labelPos || labelPos, size: o.labelSize || labelSize, outline: o.outlineThickness || 2.5 },
      o.textSize || 26
    );
    return { root, face, shadow, label: lbl, icon };
  }

  // Ui.faceGradient (UIGradient Rotation 90 = 위에서 아래): 위 = 면 색 lerp 흰색 0.32, 50%..100% = 면 색
  const faceGradient = (color) =>
    `linear-gradient(to bottom, ${css(lerp(color, WHITE, 0.32))} 0%, ${css(color)} 50%, ${css(color)} 100%)`;

  // Ui.ribbon: 코드로 그린 이름판(그림자 색 Plate + 아래 RIBBON_SHADE 만큼 짧은 앞면 Face(faceGradient) + 반투명 흰 광택 줄 +
  // Ink 테두리 3(UIStroke Border = 판 바깥쪽)) 양 끝 뒤(ZIndex 1)에 V 꼬리 그림 ribbon_tail_l/r(56:50, 늘이지 않음, ImageColor3 = 앞면 색).
  // 치수는 판 높이 50 기준이고 k = 판 높이/50 으로 늘이고 줄임. 꼬리 그림이 없으면 둥근 네모 Frame 꼬리(그림의 꼬리 몸통 자리 x 3..54, y 5..41).
  // o: { name, anchor, pos, size([0, 가로, 0, 판 높이]), z, visible, maxText, outline, text, face, shadow }
  function uiRibbon(parent, o) {
    const size = o.size;
    const k = size[3] / RIBBON_BASE_HEIGHT;
    const root = gui(parent, {
      name: o.name || 'Ribbon',
      anchor: o.anchor || [0.5, 0.5],
      pos: o.pos || [0, 0, 0, 0],
      size,
      z: o.z || 1,
      visible: o.visible,
    });
    // 꼬리 (판 뒤). 오른쪽은 왼쪽을 정확히 뒤집은 자리(Ui.ribbon 과 같게 먼저 정수로 반올림)
    const tails = [];
    const R = Math.round;
    const tailW = R(RIBBON_TAIL.w * k), tailH = R(RIBBON_TAIL.h * k);
    const tailLeft = R(RIBBON_TAIL.left * k), tailTop = R(RIBBON_TAIL.top * k);
    const bodyX = R(3 * k), bodyY = R(5 * k), bodyW = R(51 * k), bodyH = R(36 * k);
    for (const side of ['l', 'r']) {
      const art = TAIL_ART ? ART['ribbon_tail_' + side] : null;
      const [x, w, y, h] = art ? [tailLeft, tailW, tailTop, tailH] : [tailLeft + bodyX, bodyW, tailTop + bodyY, bodyH];
      const pos = side === 'l' ? [0, x, 0, y] : [1, -(x + w), 0, y];
      let tail;
      if (art) {
        tail = gui(root, { name: 'Tail', pos, size: [0, w, 0, h], z: 1 });
        tail.classList.add('tail-art');
        const img = document.createElement('img');
        img.alt = '';
        img.src = art; // ScaleType.Stretch
        applyLook(img, o.face); // 회색 그림 x 앞면 색
        tail.appendChild(img);
      } else {
        tail = gui(root, {
          name: 'Tail',
          pos,
          size: [0, w, 0, h],
          bg: o.shadow,
          z: 1,
          corner: 8 * k,
          stroke: [Theme.Ink, 3],
        });
        tail.dataset.fallback = '1';
      }
      tail.dataset.side = side;
      tails.push(tail);
    }
    // 판: 그림자 색 바탕 위에 아래 RIBBON_SHADE 만큼 짧은 앞면
    const plate = gui(root, { name: 'Plate', size: [1, 0, 1, 0], bg: o.shadow, z: 2, corner: RIBBON_CORNER * k, stroke: [Theme.Ink, 3] });
    const face = gui(plate, { name: 'Face', size: [1, 0, 1, -RIBBON_SHADE * k], z: 1, corner: RIBBON_CORNER * k });
    face.style.background = faceGradient(o.face);
    gui(plate, { name: 'Gloss', pos: [0, 10 * k, 0, 5 * k], size: [1, -20 * k, 0, 3 * k], bg: WHITE, bgT: 0.45, z: 2, corner: 'round' });
    const title = label(
      plate,
      { name: 'Title', pos: [0, 12 * k, 0, 3 * k], size: [1, -24 * k, 1, -(RIBBON_SHADE + 5) * k], text: o.text || '', color: WHITE, z: 3, outline: o.outline ?? 3 },
      o.maxText ?? 30
    );
    root.dataset.outline = String(o.outline ?? 3);
    return { root, plate, face, title, tails };
  }

  // Ui.window
  function uiWindow(parent, o) {
    const root = gui(parent, {
      name: o.name || 'Window',
      size: o.size || [0, 720, 0, 480],
      pos: o.pos || [0.5, 0, 0.5, 0],
      anchor: o.anchor || [0.5, 0.5],
      z: o.z || 1,
      uiScale: o.uiScale,
    });
    const lip = gui(root, { name: 'Lip', pos: [0, 0, 0, 8], size: [1, 0, 1, 0], bg: Theme.PaperDark, z: 1, corner: 18, stroke: [Theme.Ink, 4] });
    skin(lip, 'panel_paper', { radius: 18, color: Theme.PaperDark });
    const panel = gui(root, { name: 'Panel', size: [1, 0, 1, 0], bg: Theme.Cream, z: 2, corner: 18, stroke: [Theme.Ink, 4] });
    // 안쪽 종이 테두리(Inner)는 그림에 들어 있어서 숨김. 늘어나는 가운데 조각은 크림색 평면으로 덮음(CenterColor)
    skin(panel, 'panel_paper', { radius: 18, centerColor: Theme.Cream });

    // 리본 제목(Ui.ribbon): 판 가운데가 창 위 끝에서 4px 아래, 판 높이 50
    const pair = colorPair(o.color || 'Sky');
    const ribbon = uiRibbon(root, {
      name: 'Ribbon',
      anchor: [0.5, 0.5],
      pos: [0.5, 0, 0, 4],
      size: [0, o.ribbonWidth || 340, 0, RIBBON_HEIGHT],
      z: 3,
      maxText: 30,
      outline: 3,
      text: o.title || '',
      face: pair.Face,
      shadow: pair.Shadow,
    });

    // 닫기: close.png(빨간 동그라미 + X 완성 그림)를 그대로 ImageButton 으로
    const close = iconView(root, 'close', { name: 'Close', anchor: [0.5, 0.5], pos: [1, -8, 0, 8], size: [0, CLOSE_ART_SIZE, 0, CLOSE_ART_SIZE], z: 4 });
    const top = BODY_TOP;
    const body = gui(panel, { name: 'Body', pos: [0, 18, 0, top], size: [1, -36, 1, -(top + 16)] });
    return { root, panel, body, ribbon: ribbon.root, title: ribbon.title, close };
  }

  // Ui.pill
  function pill(parent, o) {
    const size = o.size || [0, 200, 0, 40];
    const height = size[3];
    const autoWidth = o.autoWidth === true;
    const iconSize = o.iconSize || Math.floor(height * 1.3);
    const iconCenter = Math.floor(iconSize * 0.28);
    const leftPad = o.icon ? iconCenter + Math.ceil(iconSize / 2) + 6 : 16;
    const padRight = o.padRight || 16;
    const root = gui(parent, { ...o, size: autoWidth ? [0, 0, 0, height] : size, autoW: autoWidth });
    root.classList.add('pill');
    // Ui.box("pill"): 그림(이미 반투명 Ink + 광택)은 물들이지 않음(ImageColor = 흰색). 그림 몸통 불투명도(62%)보다
    // 더 투명하게 해 달라고 할 때만 그만큼 더 투명하게 (코인 0.2, 보너스 0.3 -> 둘 다 그림 그대로)
    const transparency = o.bgT ?? 0.3;
    skin(root, 'pill', { radius: height / 2, height, color: WHITE, transparency: Math.max(0, 1 - (1 - transparency) / PILL_ART_OPACITY) });
    let lbl;
    const common = {
      name: 'Label',
      text: o.text || '',
      color: o.textColor || WHITE,
      xAlign: o.xAlign || 'left',
      z: 2,
      outline: 2.5,
    };
    if (autoWidth) {
      root.style.paddingLeft = leftPad + 'px';
      root.style.paddingRight = padRight + 'px';
      lbl = label(root, { ...common, flow: true, autoW: true, size: [0, 0, 1, 0], scaled: false, textSize: o.textSize || 20 }, o.maxTextSize || 30);
    } else {
      lbl = label(root, { ...common, pos: [0, leftPad, 0, 0], size: [1, -(leftPad + padRight), 1, 0] }, o.maxTextSize || 30);
    }
    let icon = null;
    if (o.icon) {
      icon = iconView(root, o.icon, { anchor: [0.5, 0.5], pos: [0, iconCenter, 0.5, 0], size: [0, iconSize, 0, iconSize], z: 3 });
    }
    return { root, label: lbl, icon };
  }

  // Ui.chip (스킨 버전: tag 그림을 바탕색으로 물들임)
  function chip(parent, o) {
    const height = o.height || 28;
    const background = Array.isArray(o.color) ? o.color : colorPair(o.color || 'Sky').Face;
    const iconName = o.icon;
    const iconOnly = !!iconName && o.iconOnly === true;
    const root = gui(parent, { ...o, size: [0, o.minWidth || 0, 0, height], autoW: true });
    root.classList.add('chip');
    skin(root, 'tag', { radius: o.cornerRadius ?? height / 2, height, color: background });
    const pad = Math.floor(height * CHIP_PAD);
    const iconPad = Math.floor(height * CHIP_ICON_PAD);
    root.style.paddingLeft = (iconName ? iconPad : pad) + 'px';
    root.style.paddingRight = (iconOnly ? iconPad : pad) + 'px';
    let icon = null;
    if (iconName) {
      root.style.gap = Math.floor(height * 0.14) + 'px';
      const iconSize = o.iconSize || Math.floor(height * 1.2);
      icon = iconView(root, iconName, { flow: true, size: [0, iconSize, 0, iconSize], z: 3, transparency: o.iconTransparency || 0 });
    }
    const lbl = label(
      root,
      {
        name: 'Label',
        flow: true,
        autoW: true,
        size: [0, 0, 1, 0],
        text: o.text || '',
        rich: o.rich,
        font: o.font,
        color: o.textColor || WHITE,
        scaled: false,
        textSize: o.textSize || Math.floor(height * 0.62),
        z: 2,
        outline: o.outline === false ? 0 : o.outlineThickness || 2,
        visible: !iconOnly,
      },
      100
    );
    return { root, label: lbl, icon };
  }

  // 명소 3D 모형(ViewportFrame) 자리
  function placeholder3d(parent, landmark, px) {
    const box = document.createElement('div');
    box.className = 'ph3d';
    const initial = document.createElement('div');
    initial.className = 'ini';
    initial.textContent = Array.from(landmark.Name)[0];
    initial.style.fontSize = Math.round(px * 0.42) + 'px';
    initial.style.color = css(lerp(landmark.Tier.Color, Theme.Ink, 0.42), 0.75);
    const caption = document.createElement('div');
    caption.className = 'cap';
    caption.textContent = '3D 모형 자리';
    caption.style.fontSize = Math.max(8, Math.round(px * 0.12)) + 'px';
    box.append(initial, caption);
    parent.appendChild(box);
    return box;
  }

  // Panels.photo: 등급 색을 옅게 깐 사진 칸 + 썸네일
  function photo(parent, landmark, pos, size, radius, innerPx) {
    const frame = gui(parent, {
      name: 'Photo',
      pos,
      size,
      bg: lerp(landmark.Tier.Color, WHITE, 0.62),
      corner: radius,
      stroke: [Theme.Ink, 2],
    });
    const view = gui(frame, { name: 'Thumb', pos: [0, 2, 0, 2], size: [1, -4, 1, -4] });
    placeholder3d(view, landmark, innerPx);
    return frame;
  }

  // --- 화면(ScreenGui) ------------------------------------------------------------
  function anchorBox(screenGui, name, anchor, pos, size, z) {
    return gui(screenGui, { name, anchor, pos, size, z: z || 1, uiScale: view.scale });
  }

  // Hud: 왼쪽 위 스탯
  const STATS_POS = [14, 12];
  const STATS_SIZE = [420, 112];
  const STATS_RESERVE = 400; // 윗줄(코인 알약 + 수입 칩, 긴 "+999.9K/s" 기준)이 차지하는 폭 — 위 가운데 묶음이 비켜 감
  function buildStats(screenGui, state) {
    const COIN_PILL = [230, 52];
    const container = anchorBox(screenGui, 'Stats', [0, 0], [0, STATS_POS[0], 0, STATS_POS[1]], [0, STATS_SIZE[0], 0, STATS_SIZE[1]]);
    pill(container, {
      name: 'Coins',
      pos: [0, 20, 0, 6],
      size: [0, COIN_PILL[0], 0, COIN_PILL[1]],
      icon: 'coin',
      iconSize: 68,
      maxTextSize: 36,
      bgT: 0.2,
      text: commas(state.Coins),
    });
    chip(container, {
      name: 'Income',
      color: Theme.Ink,
      textColor: INCOME_GREEN,
      icon: 'arrow_up',
      height: 30,
      textSize: 18,
      anchor: [0, 0.5],
      pos: [0, 20 + COIN_PILL[0] + 8, 0, 6 + COIN_PILL[1] / 2],
      text: '+' + incomeText(state.Income) + '/s',
    });
    const chips = gui(container, { name: 'Chips', pos: [0, 24, 0, 70], size: [0, 380, 0, 36] });
    list(chips, 'h', 12);
    chip(chips, { name: 'Rolls', flow: true, color: 'Sky', icon: 'dice', height: 30, textSize: 18, text: commas(state.Rolls) });
    chip(chips, { name: 'Luck', flow: true, color: 'Grape', icon: 'clover', height: 30, textSize: 18, text: times(state.Luck) });
    // (LayoutOrder 3: 부스트 타이머 딱지 — 부스트가 있을 때만. 이 예시 상태엔 없음)
    const rebirths = rebirthsOf(state);
    chip(chips, { name: 'Rebirths', flow: true, color: 'Coral', icon: 'rebirth', height: 30, textSize: 18, text: commas(rebirths), visible: rebirths > 0 });
  }

  // Hud: 왼쪽 메뉴 버튼 (3개 + 공원). PC 는 세로 한 줄로 왼쪽 가운데, 화면이 낮으면 여러 열로 접음 (Hud.layoutMenu)
  // (여권은 도감의 대륙 탭으로 합침 — 도장 수 배지는 도감 버튼에)
  const MENU = [
    { Id: 'Collection', Text: '도감', Color: 'Sky', Icon: 'album', Badge: true },
    { Id: 'Upgrade', Text: '강화', Color: 'Sun', Icon: 'hammer' },
    { Id: 'Rebirth', Text: '환생', Color: 'Coral', Icon: 'rebirth', Badge: true },
  ];
  const MENU_BUTTON = [84, 90];
  const MENU_GAP = 12; // 버튼 사이 (배율 1)
  const MENU_X = 14; // 메뉴 왼쪽 끝 (화면 px)
  const MENU_DROP = 16; // 메뉴 묶음 가운데 = 화면 가운데 + 이 값 (화면 px)
  const MENU_EDGE = 14; // 화면 아래 끝과 띄울 거리
  const MENU_CLEAR = 6; // 스탯·굴리기 줄과 띄울 거리
  const STATS_BOTTOM = 106; // 스탯 묶음 안에서 칩 줄 아래 끝 (칩 아이콘 포함, 배율 1)
  const ROLL_BUTTON = [270, 90];
  const AUTO_BUTTON = [140, 76];
  const ROLL_BAR = [ROLL_BUTTON[0] + 2 * (AUTO_BUTTON[0] + 16), 100]; // 굴리기 줄 묶음 (배율 1)
  const ROLL_BAR_BOTTOM = 14;

  // count 개를 columns 열로(왼쪽 → 오른쪽, 위 → 아래) 놓을 때 묶음 크기 (배율 1)
  function menuBlock(count, columns) {
    const rows = Math.ceil(count / columns);
    return [columns * MENU_BUTTON[0] + (columns - 1) * MENU_GAP, rows * MENU_BUTTON[1] + (rows - 1) * MENU_GAP];
  }
  // 로블록스 기본 터치 조작 자리 (ScreenGui 좌표, 화면 px). guiW x guiH = ScreenGui 크기, screenH = 상단바 포함 화면 높이
  //   점프: TouchGui 와 같은 계산 (짧은 쪽 500 이하 = 70px 을 (1,-95,1,-90), 아니면 120px 을 (1,-170,1,-210))
  //   조이스틱: 화면 왼쪽 1/3 · 아래 절반 (dynamic thumbstick 이 주로 잡히는 곳)
  function jumpRect(guiW, guiH) {
    const small = Math.min(guiW, guiH) <= 500;
    const size = small ? 70 : 120;
    const left = guiW - (small ? 95 : 170);
    const top = guiH - (small ? 90 : 210);
    return { left, top, right: left + size, bottom: top + size };
  }
  function thumbRect(guiW, guiH, screenH) {
    return { left: 0, top: screenH / 2 - (screenH - guiH), right: guiW / 3, bottom: guiH };
  }

  // Hud.layoutMenu: 버튼 묶음을 "스탯 칩 줄 아래 ~ 아래쪽 장애물 위" 띠에 넣음. 1열 → 2열(2줄) → 가로 한 줄 순서로(줄 수가 같은 배치는 건너뜀)
  // 처음 들어가는 배치를 쓰고, 띠 안에서 묶음 가운데를 기본 자리(화면 가운데 + 16)에 가장 가깝게 둠.
  // 아래쪽 장애물: 화면 아래 끝(여백 14) / 묶음이 가로로 닿으면 굴리기 줄 / 터치 전용 기기면 조이스틱 자리.
  // 아무 배치도 안 들어가면 가로 한 줄을 스탯 바로 아래에(fits = false).
  function layoutMenu(count, guiW, guiH, screenH, scale, touch) {
    const top = STATS_POS[1] + STATS_BOTTOM * scale + MENU_CLEAR;
    const center = guiH / 2 + MENU_DROP;
    const rollLeft = (guiW - ROLL_BAR[0] * scale) / 2;
    const rollTop = guiH - ROLL_BAR_BOTTOM - ROLL_BAR[1] * scale;
    const thumbTop = thumbRect(guiW, guiH, screenH).top;
    let place = null;
    let rows = 0;
    for (let columns = 1; columns <= count; columns++) {
      if (Math.ceil(count / columns) === rows) continue; // 줄 수가 같은 배치는 건너뜀 (4개: 1·2·4열)
      rows = Math.ceil(count / columns);
      const block = menuBlock(count, columns).map((v) => v * scale);
      let bottom = guiH - MENU_EDGE;
      if (MENU_X + block[0] + MENU_CLEAR > rollLeft) bottom = Math.min(bottom, rollTop - MENU_CLEAR);
      if (touch) bottom = Math.min(bottom, thumbTop);
      const preferred = center - block[1] / 2;
      const y = Math.min(Math.max(preferred, top), Math.max(top, bottom - block[1]));
      const fits = top + block[1] <= bottom;
      place = { columns, rows, width: block[0], height: block[1], top: y, shift: y - preferred, fits };
      if (fits) break;
    }
    return place;
  }
  const menuName = (place) => (place.rows === 1 ? '가로 한 줄' : place.columns === 1 ? '세로 한 줄' : `${place.columns}열 ${place.rows}줄`);
  // 화면 w x h (상단바 inset 포함)에서 잡히는 메뉴 배치 이름
  const menuNote = (w, h, touch, inset = GUI_INSET) =>
    menuName(layoutMenu(MENU.length + 1, w, h - inset, h, uiScaleFor(w, h), touch));

  // plot = 내 공원 부지가 있음(서버가 부지 모델에 OwnerUserId 를 붙임) -> [공원] 버튼에 더 좋은 명소 수 배지(광장에 있을 때).
  // 배치 버튼은 없음: 내 공원에서 내 명소·빈 받침대를 직접 누르면 3D 배치 모드(ParkEdit)
  function buildMenu(screenGui, state, location, plot = true) {
    const count = MENU.length + 1;
    const place = layoutMenu(count, view.w, view.h - view.inset, view.h, view.scale, view.touch);
    view.menu = place;
    const block = menuBlock(count, place.columns);
    const container = anchorBox(screenGui, 'Menu', [0, 0.5], [0, MENU_X, 0.5, MENU_DROP + place.shift], [0, block[0] + 8, 0, block[1]]);
    // Hud.placeMenu: 버튼마다 칸 자리. 오른쪽 위 배지가 있는 버튼은 ZIndex 2 — 여러 열일 때 배지가 옆 버튼에 가리지 않게
    const cell = (order, badge) => {
      const column = (order - 1) % place.columns;
      const row = Math.floor((order - 1) / place.columns);
      return { pos: [0, column * (MENU_BUTTON[0] + MENU_GAP), 0, row * (MENU_BUTTON[1] + MENU_GAP)], z: badge ? 2 : 1 };
    };
    MENU.forEach((entry, index) => {
      const button = chunkyButton(container, {
        name: entry.Id,
        ...cell(index + 1, entry.Badge),
        size: [0, MENU_BUTTON[0], 0, MENU_BUTTON[1]],
        color: entry.Color,
        icon: entry.Icon,
        iconSize: 58,
        vertical: true,
        text: entry.Text,
        textSize: 18,
      });
      if (entry.Id === 'Collection') {
        // 대륙 도장 수 [여권] "1/5" 배지 (도감 대륙 탭에서 모은 도장 — 여권 아이콘 = 도감 [전체] 머리 줄 도장 딱지와 같은 그림)
        const stamps = completedRegions(state).length;
        chip(button.face, {
          name: 'Stamps',
          color: Theme.Ink,
          icon: 'passport',
          iconSize: 28,
          height: 24,
          textSize: 15,
          anchor: [0.5, 0.5],
          pos: [1, -6, 0, 2],
          rot: 8,
          z: 6,
          text: `${stamps}/${Regions.length}`,
          textColor: stamps > 0 ? COLORS.Sun.Face : WHITE,
        });
      } else if (entry.Id === 'Rebirth') {
        // 환생할 수 있으면(코인 + 요구 명소) "!" 배지가 통통 뜀
        chip(button.face, {
          name: 'Ready',
          color: 'Sun',
          text: '!',
          font: 'title',
          height: 28,
          textSize: 20,
          anchor: [0.5, 0.5],
          pos: [1, -6, 0, 2],
          rot: 10,
          z: 6,
          visible: rebirthReady(state, state.Coins),
        });
      }
    });
    const inPark = location === 'Park';
    const teleport = chunkyButton(container, {
      name: 'Teleport',
      ...cell(count, true),
      size: [0, MENU_BUTTON[0], 0, MENU_BUTTON[1]],
      color: 'Grass',
      icon: inPark ? 'plaza' : 'park',
      iconSize: 58,
      vertical: true,
      text: inPark ? '광장' : '공원',
      textSize: 18,
    });
    // Hud BetterBadge: 직접 배치 중 더 좋은데 전시 안 된 명소 수(PlayerState.betterHidden, 도장 배지와 같은 모양) —
    // 내 부지가 있고 버튼이 [공원](광장에 있음)일 때만, 0 이면 숨김
    countBadge(teleport.face, plot && !inPark ? betterHidden(state).length : 0);
  }

  // Hud [공원] 버튼 배지: 버튼 오른쪽 위 Ink 딱지 + Sun 숫자(도감 도장 "1/5" 배지와 같은 모양), 0 이면 숨김
  function countBadge(face, count, pos = [1, -6, 0, 2]) {
    return chip(face, {
      name: 'Better',
      color: Theme.Ink,
      height: 24,
      textSize: 15,
      anchor: [0.5, 0.5],
      pos,
      rot: 8,
      z: 6,
      text: String(count),
      textColor: COLORS.Sun.Face,
      visible: count > 0,
    });
  }

  // 로블록스 기본 터치 조작(터치 전용 기기만): 오른쪽 아래 점프 버튼 + 왼쪽 아래 조이스틱 자리(흐리게, 게임 UI 가 아님)
  function touchControls(screenGui) {
    const guiH = view.h - view.inset;
    const thumb = thumbRect(view.w, guiH, view.h);
    const zone = gui(screenGui, {
      name: 'ThumbZone',
      cls: 'thumb-zone',
      pos: [0, thumb.left, 0, thumb.top],
      size: [0, thumb.right - thumb.left, 0, thumb.bottom - thumb.top],
      z: 0,
    });
    zone.insertAdjacentHTML('beforeend', '<i></i><span>조이스틱</span>');
    const jump = jumpRect(view.w, guiH);
    gui(screenGui, {
      name: 'Jump',
      cls: 'rbx-jump',
      pos: [0, jump.left, 0, jump.top],
      size: [0, jump.right - jump.left, 0, jump.bottom - jump.top],
      z: 0,
    });
  }

  // Hud: 굴리기 + 자동
  function buildRollBar(screenGui, opts) {
    const ROLL = ROLL_BUTTON;
    const AUTO = AUTO_BUTTON;
    const container = anchorBox(screenGui, 'RollBar', [0.5, 1], [0.5, 0, 1, -ROLL_BAR_BOTTOM], [0, ROLL_BAR[0], 0, ROLL_BAR[1]]);
    const roll = chunkyButton(container, {
      name: 'Roll',
      pos: [0.5, -ROLL[0] / 2, 1, -ROLL[1]],
      size: [0, ROLL[0], 0, ROLL[1]],
      color: 'Grass',
      icon: 'globe',
      iconSize: 70,
      text: '굴리기',
      textSize: 40,
      outlineThickness: 3,
      labelPos: [0, 82, 0, 2],
      labelSize: [1, -94, 1, -22],
    });
    keyCap(roll.face, 'R', { pos: [0, 4, 0, 4] });
    const track = gui(roll.face, {
      name: 'Cooldown',
      anchor: [0, 1],
      pos: [0, 84, 1, -9],
      size: [1, -100, 0, 10],
      bg: Theme.Ink,
      bgT: 0.5,
      z: 5,
      corner: 'round',
    });
    gui(track, { name: 'Fill', size: [opts.cooldown ?? 1, 0, 1, 0], bg: WHITE, z: 6, corner: 'round' });

    const auto = chunkyButton(container, {
      name: 'Auto',
      pos: [0.5, ROLL[0] / 2 + 16, 1, -(ROLL[1] + AUTO[1]) / 2],
      size: [0, AUTO[0], 0, AUTO[1]],
      color: opts.auto ? 'Sun' : 'Gray',
      icon: 'auto',
      iconSize: 46,
      text: 'AUTO',
      textSize: 24,
    });
    keyCap(auto.face, 'T', { pos: [0, 4, 0, 4] });
    chip(auto.face, {
      name: 'On',
      color: 'Coral',
      text: 'ON',
      height: 24,
      textSize: 16,
      anchor: [0.5, 0.5],
      pos: [1, -10, 0, 2],
      rot: 12,
      z: 6,
      visible: !!opts.auto,
    });
  }

  function buildHud(screenGui, state, opts = {}) {
    if (view.touch) touchControls(screenGui);
    buildStats(screenGui, state);
    buildMenu(screenGui, state, opts.location || 'Plaza', opts.plot !== false);
    buildRollBar(screenGui, opts);
  }

  // Hud.placeTop: 위 가운데 묶음 자리. 기본은 화면 가운데, 왼쪽 위 스탯(윗줄)과 겹치면 안 겹칠 만큼 오른쪽으로 비키고,
  // 그래도 화면 오른쪽 끝을 넘으면(아주 좁은 화면) 가운데로 두고 스탯 아래로 내림. width = ScreenGui 가로(화면 px)
  // 메뉴(layoutMenu 결과)가 가로로 접혀 이 묶음 높이 안에 들어오면 메뉴 오른쪽 끝·아래 끝도 함께 비켜 감
  const TOP_WIDTH = 600;
  const TOP_HEIGHT = 380;
  const TOP_Y = 10;
  const TOP_GAP = 12;
  function placeTop(width, scale, menu) {
    const half = (TOP_WIDTH * scale) / 2;
    let reserve = STATS_POS[0] + STATS_RESERVE * scale;
    if (menu && menu.top < TOP_Y + TOP_HEIGHT * scale) reserve = Math.max(reserve, MENU_X + menu.width);
    const center = Math.max(width / 2, reserve + TOP_GAP + half);
    if (center + half <= width - STATS_POS[0]) return { pos: [0, center, 0, TOP_Y], center, top: TOP_Y, below: false, reserve };
    let below = STATS_POS[1] + STATS_SIZE[1] * scale;
    if (menu && MENU_X + menu.width > width / 2 - half) below = Math.max(below, menu.top + menu.height);
    const top = below + TOP_GAP;
    return { pos: [0.5, 0, 0, top], center: width / 2, top, below: true, reserve };
  }

  // Hud.news: 신문 띠 한 줄 / Hud.toast: 그 아래 알림 딱지 [아이콘][짧은 글자] (toasts: [{ text, icon, color }])
  function buildNews(screenGui, items, toasts = []) {
    // Hud.buildNotices: [서버 행운 띠(켜졌을 때만)] [뉴스 속보 600x118] [알림] 을 위에서부터 쌓는 "Top" 묶음
    const place = placeTop(view.w, view.scale, view.menu);
    const top = anchorBox(screenGui, 'Top', [0.5, 0], place.pos, [0, TOP_WIDTH, 0, TOP_HEIGHT], 9);
    list(top, 'v', 6, 'center', 'top');
    // 속보 수만큼만 높이(AutomaticSize Y) — 속보가 없으면 알림이 맨 위에 뜸
    const newsHeight = items.length ? items.length * 54 + (items.length - 1) * 8 : 0;
    const news = gui(top, { name: 'News', flow: true, size: [0, TOP_WIDTH, 0, newsHeight] });
    list(news, 'v', 8, 'center', 'top');
    for (const item of items) {
      const landmark = ById[item.LandmarkId];
      const tier = landmark.Tier;
      const row = gui(news, { name: 'NewsItem', flow: true, size: [1, 0, 0, 54] });
      const slide = gui(row, { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [1, 0, 1, 0] });
      const bar = gui(slide, { pos: [0, 56, 0, 4], size: [1, -56, 1, -8], bg: Theme.Cream, z: 1, corner: 10, stroke: [Theme.Ink, 3] });
      skin(bar, 'panel_paper', { radius: 10, height: 46, centerColor: Theme.Cream });
      label(
        bar,
        {
          pos: [0, 66, 0, 5],
          size: [1, -66 - 130, 1, -10],
          xAlign: 'left',
          rich: `${escapeHtml(item.Name)} · <font color="${hex(lerp(tier.Color, Theme.Ink, 0.35))}">${escapeHtml(landmark.Name)}</font> · <font color="${hex(ODDS_COLOR)}">${oneIn(landmark.OneIn)}</font>`,
        },
        22
      );
      chip(bar, {
        name: 'Rolls',
        color: 'Sky',
        icon: 'dice',
        text: '#' + commas(item.Rolls),
        height: 28,
        textSize: 16,
        anchor: [1, 0.5],
        pos: [1, -10, 0.5, 0],
        z: 2,
      });
      const stamp = gui(slide, {
        anchor: [0, 0.5],
        pos: [0, 0, 0.5, 0],
        size: [0, 112, 0, 46],
        bg: COLORS.Coral.Face,
        rot: -6,
        z: 2,
        corner: 10,
        stroke: [Theme.Ink, 3],
      });
      skin(stamp, 'tag', { radius: 10, height: 46, color: COLORS.Coral.Face });
      gui(stamp, { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [1, -10, 1, -10], corner: 7, stroke: [WHITE, 2, 0.25] });
      label(stamp, { pos: [0, 8, 0, 6], size: [1, -16, 1, -12], font: 'title', text: '속보', color: WHITE, z: 2, outline: 2.5 }, 26);
    }
    const notices = gui(top, { name: 'Notices', flow: true, size: [0, 600, 0, 200] });
    list(notices, 'v', 8, 'center', 'top');
    for (const t of toasts) {
      const toast = chip(notices, { name: t.name || 'Toast', flow: true, color: t.color, text: t.text, icon: t.icon, iconSize: 48, height: 40, textSize: 22, strokeThickness: 3 });
      // 누를 수 있는 알림(도장): 끝에 "가기" 화살표(arrow_up 을 오른쪽으로 돌림)
      if (t.go) iconView(toast.root, 'arrow_up', { name: 'Go', flow: true, size: [0, 30, 0, 30], rot: 90, z: 3 });
    }
  }

  // Hud.reveal: 결과 공개 순간 (지역에 착지 + 명소 공개 + 딱지)
  function buildReveal(screenGui, landmark, info) {
    const VIEW_SIZE = 230;
    const tier = landmark.Tier;
    const region = RegionById[landmark.Region] || Regions[0];
    const container = anchorBox(screenGui, 'Reveal', [0.5, 0.5], [0.5, 0, 0.45, 0], [0, 700, 0, 500], 8);
    const inner = gui(container, { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [1, 0, 1, 0] });

    const regionTag = gui(inner, { name: 'Region', anchor: [0.5, 0], pos: [0.5, 0, 0, 0], size: [0, 280, 0, 48], z: 4, corner: 'round' });
    skin(regionTag, 'tag', { radius: 24, height: 48, color: region.Color });
    label(regionTag, { pos: [0, 12, 0, 4], size: [1, -24, 1, -8], text: region.Name, color: WHITE, z: 2, outline: 3 }, 34);

    const centerY = 62 + VIEW_SIZE / 2;
    const burst = gui(inner, { name: 'Burst', anchor: [0.5, 0.5], pos: [0.5, 0, 0, centerY], size: [0, 500, 0, 500], z: 1, rot: info.burstRotation || 0 });
    skin(burst, 'sunburst', { color: tier.Color });

    const disc = gui(inner, {
      name: 'Disc',
      anchor: [0.5, 0.5],
      pos: [0.5, 0, 0, centerY],
      size: [0, VIEW_SIZE, 0, VIEW_SIZE],
      bg: lerp(tier.Color, WHITE, 0.6),
      z: 2,
      corner: 'round',
      stroke: [Theme.Ink, 5],
    });
    gui(disc, { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [1, -18, 1, -18], corner: 'round', stroke: [WHITE, 3, 0.15] });
    const view = gui(inner, { name: 'ResultView', anchor: [0.5, 0.5], pos: [0.5, 0, 0, centerY], size: [0, VIEW_SIZE - 16, 0, VIEW_SIZE - 16], z: 3 });
    const ph = placeholder3d(view, landmark, VIEW_SIZE - 16);
    ph.style.borderRadius = '50%';
    ph.style.inset = '14px';

    // 등급 리본(Ui.ribbon 250x44): 판 가운데가 둥근 판 아래 끝보다 6 위. showRibbon: 앞면 = 등급 색, 그림자 = 등급 색 lerp Ink 0.35
    uiRibbon(inner, {
      name: 'TierRibbon',
      anchor: [0.5, 0.5],
      pos: [0.5, 0, 0, centerY + VIEW_SIZE / 2 - 6],
      size: [0, 250, 0, 44],
      z: 4,
      maxText: 26,
      outline: 2.5,
      text: tier.Name,
      face: tier.Color,
      shadow: lerp(tier.Color, Theme.Ink, 0.35),
    });

    const nameTop = centerY + VIEW_SIZE / 2 + 34;
    label(inner, { name: 'Name', pos: [0, 0, 0, nameTop], size: [1, 0, 0, 66], font: 'title', text: landmark.Name, color: tier.Color, z: 4, outline: 4 }, 62);
    label(inner, { name: 'Odds', pos: [0, 0, 0, nameTop + 66], size: [1, 0, 0, 30], font: 'title', text: oneIn(landmark.OneIn), color: WHITE, z: 4, outline: 2.5 }, 28);

    const tagRow = gui(inner, { name: 'Tags', pos: [0, 0, 0, nameTop + 104], size: [1, 0, 0, 36], z: 4 });
    list(tagRow, 'h', 14, 'center');
    chip(tagRow, { name: 'New', flow: true, color: 'Coral', text: 'NEW', font: 'title', height: 32, textSize: 22, visible: info.IsNew });
    chip(tagRow, { name: 'StarUp', flow: true, color: 'Grape', font: 'title', height: 32, textSize: 21, rich: starUpText(info.Stars), visible: info.StarUp });
    pill(tagRow, {
      name: 'Bonus',
      flow: true,
      autoWidth: true,
      size: [0, 0, 0, 32],
      icon: 'coin',
      iconSize: 44,
      textSize: 21,
      textColor: COLORS.Sun.Face,
      text: '+' + commas(info.Bonus),
      visible: info.Bonus > 0,
    });
  }

  // --- Panels -------------------------------------------------------------------
  const HEADER_HEIGHT = 50;
  // 도감 대륙 탭(Panels TAB_*): [전체] + 대륙마다 하나(여권을 합침). 탭 = 세로 통통 버튼(왼쪽 메뉴 버튼처럼 아이콘 위 · 이름 아래,
  // 앞면 68 + 그림자 6), 대륙 아이콘 = 도장 그림. 여섯 개가 본문 폭을 똑같이 나눔(휴대폰 배율 0.55 에서도 앞면 약 63×37px, 글자 10px)
  // 아이콘(도장 그림은 둘레에 빈 곳이 있어 앞면 위 끝에 붙여 크게) 위 3, 이름 칸은 아이콘 아래 LABEL_Y 부터(아이콘 그림 아래 빈 곳과 조금 겹침)
  const TAB = { HEIGHT: 74, GAP: 6, SPACING: 8, ICON: 44, LABEL_Y: 37, LABEL_H: 20, TEXT: 19, STRIP: 5, STRIP_X: 14, STRIP_BOTTOM: 4, CHECK: 22 };
  const COLLECTION_TOP = TAB.HEIGHT + TAB.GAP + HEADER_HEIGHT;
  // 창 높이: 기본 500, 도감은 탭 줄 때문에 조금 더 높게(아래로 늘림). 작은 화면에서는 창이 화면 안에 들어오게(Panels.openOffset)
  const VIEWS = {
    Collection: { Title: '도감', Color: 'Sky', Top: COLLECTION_TOP, Height: 530 },
    Upgrade: { Title: '강화', Color: 'Sun', Top: 4 },
  };
  const WINDOW_SIZE = [760, 500];
  const BODY_WIDTH = WINDOW_SIZE[0] - 36; // Ui.window 본문 = 창 가로 - 좌우 18
  const OPEN_OFFSET = -30;
  const PAD_X = 6;
  const PAD_RIGHT = 14;
  const PAD_Y = 6;
  const REGION_BONUS = Math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5);
  const gridHeight = (count, columns, cellHeight, gap) => {
    const rows = Math.ceil(count / columns);
    return rows <= 0 ? 0 : rows * (cellHeight + gap) - gap;
  };
  const COLLECTION = { CELL: [128, 184], GAP: 12, COLS: 5 };

  function headerChip(parent, icon, color, text, iconTransparency, name) {
    return chip(parent, { name, flow: true, color, icon, iconSize: 44, height: 34, textSize: 21, text, iconTransparency });
  }
  function chipRow(header) {
    const row = gui(header, { name: 'Chips', pos: [0, 10, 0, 0], size: [1, -200, 1, -6] });
    list(row, 'h', 14);
    return row;
  }

  // ScrollingFrame: 캔버스를 scrollY 만큼 올려 그리고, 넘치면 오른쪽에 스크롤 막대
  function scroller(body, top, canvasHeight, scrollY, bodyHeight) {
    const frame = gui(body, { name: 'Scroller', pos: [0, 0, 0, top], size: [1, 0, 1, -top], clip: true });
    const canvas = gui(frame, { name: 'Canvas', pos: [0, 0, 0, -scrollY], size: [1, 0, 0, canvasHeight] });
    const content = gui(canvas, { name: 'Content', pos: [0, PAD_X, 0, PAD_Y], size: [1, -(PAD_X + PAD_RIGHT), 1, -2 * PAD_Y] });
    const visible = bodyHeight - top;
    if (canvasHeight > visible + 0.5) {
      const thumb = (visible * visible) / canvasHeight;
      const y = (scrollY / (canvasHeight - visible)) * (visible - thumb);
      const bar = document.createElement('div');
      bar.className = 'scrollbar';
      bar.style.top = y + 'px';
      bar.style.height = thumb + 'px';
      frame.appendChild(bar);
    }
    return content;
  }

  // 등급 색 띠 + 확률 (위쪽 모서리만 둥글게) — 아는 카드·모르는 카드 같이
  function oddsBand(card, landmark) {
    const tier = landmark.Tier;
    const band = gui(card, { name: 'Band', size: [1, 0, 0, 26], bg: tier.Color, corner: 12 });
    gui(band, { pos: [0, 0, 1, -12], size: [1, 0, 0, 12], bg: tier.Color });
    gui(band, { pos: [0, 0, 1, 0], size: [1, 0, 0, 3], bg: Theme.Ink });
    label(band, { pos: [0, 4, 0, 4], size: [1, -8, 1, -7], text: oneIn(landmark.OneIn), color: WHITE, z: 2, outline: 1.5 }, 15);
  }

  // Panels.collectionCard: 발견한 명소. 지금 없으면(환생 전에 발견·자동 발견) 사진이 어둡고 개수·별 줄이 없음
  function collectionCard(parent, landmark, count, featured, shown) {
    const card = gui(parent, { name: landmark.Id, flow: true, size: [0, COLLECTION.CELL[0], 0, COLLECTION.CELL[1]], bg: featured ? FEATURED_BG : Theme.Paper, corner: 12, stroke: [Theme.Ink, 3] });
    oddsBand(card, landmark);
    const picture = photo(card, landmark, [0, 7, 0, 33], [1, -14, 0, 84], 8, 80);
    if (count <= 0) gui(picture, { name: 'Dim', size: [1, 0, 1, 0], bg: Theme.Ink, bgT: 0.45, z: 2, corner: 8 });
    label(card, { pos: [0, 6, 0, 122], size: [1, -12, 0, 24], text: landmark.Name }, 19);
    label(card, { name: 'Stars', pos: [0, 6, 0, 149], size: [1, -12, 0, 24], rich: count > 0 ? starsRich(stars(count), MAX_STARS) : '', outline: 2 }, 22);
    chip(card, { name: 'Count', color: Theme.Ink, height: 22, textSize: 14, outline: false, anchor: [1, 0], pos: [1, -3, 0, 29], z: 3, text: '×' + commas(count), visible: count > 0 });
    chip(card, { name: 'Featured', color: 'Coral', text: '대표', height: 28, textSize: 17, cornerRadius: 7, rot: -14, pos: [0, -8, 0, 22], z: 4, visible: featured });
    if (shown) chip(card, { name: 'Shown', color: 'Grass', icon: 'park', iconOnly: true, iconSize: 30, height: 24, pos: [0, 3, 0, 94], z: 3 });
  }

  // Panels.unknownCard: 대륙 탭의 아직 못 찾은 명소 — 어두운 카드(아는 카드와 같은 자리: 확률 띠 · 사진 칸 · 이름 줄) + 사진 칸에 자물쇠,
  // 이름 대신 "?" 셋. 도장에 안 세는 명소(불가사의보다 희귀 — 보너스 수집)는 자물쇠 대신 전설 도장 그림(stamp_legend). 3D 모형은 만들지 않음(가볍게)
  const UNKNOWN_BG = [58, 53, 80];
  function unknownCard(parent, landmark) {
    const card = gui(parent, { name: landmark.Id, flow: true, size: [0, COLLECTION.CELL[0], 0, COLLECTION.CELL[1]], bg: UNKNOWN_BG, corner: 12, stroke: [Theme.Ink, 3] });
    card.dataset.unknown = '1';
    oddsBand(card, landmark);
    const hole = gui(card, { name: 'Photo', pos: [0, 7, 0, 33], size: [1, -14, 0, 84], bg: Theme.Ink, corner: 8, stroke: [Theme.Ink, 2] });
    const bonus = !countsForStamp(landmark);
    iconView(hole, bonus ? 'stamp_legend' : 'lock', { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [0, bonus ? 66 : 58, 0, bonus ? 66 : 58], transparency: bonus ? 0.2 : 0.1 });
    label(card, { pos: [0, 6, 0, 124], size: [1, -12, 0, 24], text: '???', color: Theme.Paper, textT: 0.45 }, 20);
  }

  // 탭 목록: [전체](도감 아이콘, Sky) + 대륙(도장 그림, 대륙 색)
  function collectionTabs() {
    return [
      { Id: 'All', Name: '전체', Icon: 'album', Color: COLORS.Sky.Face },
      ...Regions.map((r) => ({ Id: r.Id, Name: r.Name, Icon: 'stamp_' + r.Id.toLowerCase(), Color: r.Color, Region: r })),
    ];
  }
  // Panels.tabWidth: 여섯 탭이 본문 폭을 똑같이 나눔(탭 사이 SPACING)
  const tabWidth = (count) => Math.floor((BODY_WIDTH - TAB.SPACING * (count - 1)) / count);
  // Panels.tabPair: 고른 탭 = 탭 색 그대로, 다른 탭 = 크림 쪽으로 옅게(그림자도 옅게) — 고른 탭이 한눈에. 글자는 모두 흰 글자 + Ink 테두리
  const tabPair = (color, selected) =>
    selected ? { Face: color, Shadow: lerp(color, Theme.Ink, 0.35) } : { Face: lerp(color, Theme.Cream, 0.5), Shadow: lerp(color, Theme.Cream, 0.15) };

  function buildTabs(body, state, selected) {
    const tabs = collectionTabs();
    const width = tabWidth(tabs.length);
    const row = gui(body, { name: 'Tabs', size: [1, 0, 0, TAB.HEIGHT] });
    list(row, 'h', TAB.SPACING, 'center', 'top');
    const completed = new Set(completedRegions(state));
    tabs.forEach((tab) => {
      const on = tab.Id === selected;
      const button = chunkyButton(row, {
        name: 'Tab' + tab.Id,
        flow: true,
        size: [0, width, 0, TAB.HEIGHT],
        color: tabPair(tab.Color, on),
        icon: tab.Icon,
        iconSize: TAB.ICON,
        vertical: true,
        text: tab.Name,
        textSize: TAB.TEXT,
        labelPos: [0, 4, 0, TAB.LABEL_Y],
        labelSize: [1, -8, 0, TAB.LABEL_H],
      });
      button.root.dataset.selected = on ? '1' : '';
      if (!tab.Region) return;
      // 도장을 받은 대륙: 도장 그림 오른쪽 위에 작은 체크 동그라미(앞면 안)
      if (completed.has(tab.Id)) {
        const mark = gui(button.face, { name: 'Stamped', anchor: [0.5, 0.5], pos: [0.5, TAB.ICON / 2 - 3, 0, 13], size: [0, TAB.CHECK, 0, TAB.CHECK], bg: Theme.Cream, corner: 'round', stroke: [Theme.Ink, 2], rot: 8, z: 6 });
        iconView(mark, 'check', { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [0.95, 0, 0.95, 0], z: 7 });
        return;
      }
      // 아직이면 앞면 아래 끝에 가는 발견 막대(어두운 홈 + 대륙 색, PlayerState.regionProgress) — 어느 대륙이 도장에 가까운지 한눈에
      const [found, required] = regionProgress(state, tab.Id);
      const track = gui(button.face, { name: 'Strip', pos: [0, TAB.STRIP_X, 1, -(TAB.STRIP + TAB.STRIP_BOTTOM)], size: [1, -2 * TAB.STRIP_X, 0, TAB.STRIP], bg: Theme.Ink, bgT: 0.25, corner: 'round', z: 5 });
      gui(track, { name: 'Fill', size: [required > 0 ? Math.min(1, found / required) : 0, 0, 1, 0], bg: lerp(tab.Color, WHITE, 0.35), corner: 'round', z: 6 });
    });
    return row;
  }

  // [전체] 머리 줄: [도감 23/150] [여권 = 도장 1/5] [클로버 +25%] …… [자동]
  function buildAllHeader(body, state, shownCount) {
    const header = gui(body, { name: 'CollectionHeader', pos: [0, 0, 0, TAB.HEIGHT + TAB.GAP], size: [1, 0, 0, HEADER_HEIGHT] });
    const chips = chipRow(header);
    headerChip(chips, 'album', Theme.Ink, `${shownCount}/${List.length}`, 0, 'Count');
    const stamps = completedRegions(state).length;
    headerChip(chips, 'passport', Theme.Ink, `${stamps}/${Regions.length}`, 0, 'Stamps');
    // 도장이 없으면 회색 "+25%"(도장 하나에 이만큼 — 대륙 탭의 회색 +25% 와 같은 뜻), 있으면 초록 합
    headerChip(chips, 'clover', stamps > 0 ? COLORS.Grass.Face : DIM_CHIP, `+${Math.max(stamps, 1) * REGION_BONUS}%`, stamps > 0 ? 0 : 0.45, 'StampBonus');
    const auto = chunkyButton(header, {
      name: 'AutoFeature',
      anchor: [1, 0],
      pos: [1, -8, 0, -4],
      size: [0, 136, 0, 50],
      color: state.Settings.AutoFeature ? 'Grass' : 'Gray',
      icon: 'star',
      iconSize: 36,
      text: '자동',
      textSize: 22,
    });
    chip(auto.face, { name: 'On', color: 'Coral', text: 'ON', height: 22, textSize: 15, anchor: [0.5, 0.5], pos: [1, -6, 1, -4], rot: 12, z: 6, visible: state.Settings.AutoFeature });
  }

  // 대륙 머리 줄: [도장(찍힘/흐림)]==== 발견 막대 "found/required" ====[체크] …… [클로버 +25%(받음 초록 / 아직 회색)]
  // 도장 조건 = 불가사의 등급까지(PlayerState.regionProgress), 그보다 희귀한 카드는 보이지만 막대 숫자에서 빠짐
  const STAMP_SIZE = 70;
  const BAR_HEIGHT = 34;
  const BAR_LEFT = 86; // 도장 오른쪽
  const BAR_RIGHT = 150; // 오른쪽 +25% 딱지 자리
  function buildRegionHeader(body, state, region) {
    const header = gui(body, { name: 'RegionHeader', pos: [0, 0, 0, TAB.HEIGHT + TAB.GAP], size: [1, 0, 0, HEADER_HEIGHT] });
    header.dataset.region = region.Id;
    const [found, required] = regionProgress(state, region.Id);
    const complete = required > 0 && found >= required;
    // 도장: 다 모으면 진하게 찍힘, 아니면 회색으로 물들이고 흐리게(Panels.paintStamp — 여권과 같은 모양)
    const stamp = gui(header, { name: 'Stamp', anchor: [0.5, 0.5], pos: [0, STAMP_SIZE / 2 + 2, 0.5, 0], size: [0, STAMP_SIZE, 0, STAMP_SIZE], rot: -12, z: 5 });
    iconView(stamp, 'stamp_' + region.Id.toLowerCase(), {
      anchor: [0.5, 0.5],
      pos: [0.5, 0, 0.5, 0],
      size: [1.12, 0, 1.12, 0],
      z: 2,
      color: complete ? null : [150, 146, 160],
      transparency: complete ? 0 : 0.4,
    });
    // 발견 막대(대륙 색) + "찾은 수/필요 수", 다 모으면 오른쪽 끝에 체크
    const bar = gui(header, { name: 'Progress', anchor: [0, 0.5], pos: [0, BAR_LEFT, 0.5, 0], size: [1, -(BAR_LEFT + BAR_RIGHT), 0, BAR_HEIGHT], bg: Theme.Cream, corner: 'round', stroke: [Theme.Ink, 3] });
    gui(bar, { name: 'Fill', size: [required > 0 ? found / required : 0, 0, 1, 0], bg: region.Color, corner: 'round' });
    label(bar, { name: 'Count', pos: [0, 30, 0, 3], size: [1, -60, 1, -6], text: `${found}/${required}`, color: WHITE, z: 3, outline: 2.5 }, 24);
    if (complete) {
      const check = gui(bar, { name: 'Check', anchor: [0.5, 0.5], pos: [1, -2, 0.5, 0], size: [0, 40, 0, 40], bg: Theme.Cream, corner: 'round', stroke: [Theme.Ink, 3], z: 4 });
      iconView(check, 'check', { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [0.95, 0, 0.95, 0], z: 5 });
    }
    // 도장 행운 +25%: 받았으면 초록, 아직이면 회색 + 흐린 아이콘
    const bonus = headerChip(header, 'clover', complete ? COLORS.Grass.Face : DIM_CHIP, `+${REGION_BONUS}%`, complete ? 0 : 0.45, 'Bonus');
    bonus.root.classList.remove('flow');
    Object.assign(bonus.root.style, { position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)' });
    return { found, required, complete };
  }

  // 도감 창: 위 대륙 탭 + 머리 줄 + 카드 격자. tab = 'All' | 대륙 Id
  //   전체 = 발견한 명소(Discovered 기준)만 희귀한 순서, 대륙 = 그 대륙 명소 전부(흔한 순서, 못 찾은 것은 어두운 자물쇠 카드)
  function buildCollection(body, bodyHeight, state, scrollY, tab = 'All') {
    buildTabs(body, state, tab);
    const inPark = new Set(park(state));
    const known = RarestFirst.filter((l) => isDiscovered(state, l.Id));
    let cards;
    if (tab === 'All') {
      buildAllHeader(body, state, known.length);
      cards = known;
    } else {
      buildRegionHeader(body, state, RegionById[tab]);
      cards = ByRegion[tab];
    }
    const canvas = gridHeight(cards.length, COLLECTION.COLS, COLLECTION.CELL[1], COLLECTION.GAP) + PAD_Y * 2;
    // scrollY = 'bottom' 이면 맨 아래까지 내린 모습
    const maxScroll = Math.max(0, canvas - (bodyHeight - VIEWS.Collection.Top));
    const content = scroller(body, VIEWS.Collection.Top, canvas, scrollY === 'bottom' ? maxScroll : Math.min(scrollY, maxScroll), bodyHeight);
    gridLayout(content, COLLECTION.CELL[0], COLLECTION.CELL[1], COLLECTION.GAP, COLLECTION.COLS, 'center', BODY_WIDTH - PAD_X - PAD_RIGHT);
    for (const landmark of cards) {
      if (isDiscovered(state, landmark.Id)) {
        collectionCard(content, landmark, state.Inventory[landmark.Id] || 0, state.Featured === landmark.Id, inPark.has(landmark.Id));
      } else unknownCard(content, landmark);
    }
    if (!known.length && tab === 'All') iconView(body, 'globe', { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, COLLECTION_TOP / 2], size: [0, 150, 0, 150], transparency: 0.2 });
  }

  // Panels.valueText / stepText
  const trim = (v) => v.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
  function valueText(upgrade, level) {
    if (upgrade.Id === 'Agency') return trim(Config.ROLL_COOLDOWN * (1 - upgrade.PerLevel * level)) + '초';
    if (upgrade.Id === 'Park') return `${Math.floor(Config.BASE_SLOTS + upgrade.PerLevel * level + 0.5)}칸`;
    return times(1 + upgrade.PerLevel * level);
  }
  function stepText(upgrade) {
    if (upgrade.Id === 'Park') return `+${upgrade.PerLevel}칸`;
    const percent = Math.floor(upgrade.PerLevel * 100 + 0.5);
    return (upgrade.Id === 'Agency' ? '-' : '+') + percent + '%';
  }
  const UPGRADE_ICON = { Globe: 'globe', Agency: 'plane', Park: 'park', Ticket: 'ticket' };

  function buildUpgrade(body, bodyHeight, state) {
    const ROW = 80;
    const GAP = 10;
    const canvas = Config.Upgrades.length * (ROW + GAP) - GAP + PAD_Y * 2;
    const content = scroller(body, VIEWS.Upgrade.Top, canvas, 0, bodyHeight);
    list(content, 'v', GAP, 'center', 'top');
    for (const upgrade of Config.Upgrades) {
      const level = upgradeLevel(state, upgrade.Id);
      const price = upgradePrice(upgrade.Id, level);
      const row = gui(content, { name: upgrade.Id, flow: true, size: [1, 0, 0, ROW], bg: Theme.Paper, corner: 14, stroke: [Theme.Ink, 3] });
      const disc = gui(row, { anchor: [0, 0.5], pos: [0, 12, 0.5, 0], size: [0, 62, 0, 62], bg: Theme.Cream, corner: 'round', stroke: [Theme.Ink, 3] });
      iconView(disc, UPGRADE_ICON[upgrade.Id] || 'star', { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [0.86, 0, 0.86, 0] });

      const head = gui(row, { pos: [0, 88, 0, 6], size: [1, -290, 0, 32] });
      list(head, 'h', 10);
      label(head, { flow: true, autoW: true, size: [0, 0, 1, 0], scaled: false, textSize: 25, text: upgrade.Name }, 100);
      chip(head, { name: 'Level', flow: true, color: Theme.Ink, height: 24, textSize: 15, outline: false, text: 'Lv ' + level });

      const effects = gui(row, { pos: [0, 92, 0, 42], size: [1, -290, 0, 30] });
      list(effects, 'h', 12);
      chip(effects, { name: 'Value', flow: true, color: Theme.Cream, textColor: Theme.Ink, outline: false, height: 26, textSize: 17, text: valueText(upgrade, level) });
      chip(effects, {
        name: 'Step',
        flow: true,
        color: price != null ? COLORS.Grass.Face : COLORS.Grape.Face,
        icon: price != null ? 'arrow_up' : null, // MAX 는 화살표 없이 (Ui.showChipIcon(false): 왼쪽 여백도 글자 딱지와 같게)
        iconSize: 30,
        height: 26,
        textSize: 17,
        text: price != null ? stepText(upgrade) : 'MAX',
      });

      const buyColor = price == null ? 'Grape' : state.Coins >= price ? 'Sun' : 'Gray';
      chunkyButton(row, {
        name: 'Buy',
        anchor: [1, 0.5],
        pos: [1, -14, 0.5, 0],
        size: [0, 176, 0, 62],
        color: buyColor,
        icon: price != null ? 'coin' : null,
        iconSize: 44,
        textSize: 26,
        text: price != null ? commas(price) : 'MAX',
      });
    }
  }

  // --- 3D 배치 모드 (ParkEdit.luau + Shared/ParkGrid.luau) ---------------------------------------
  // 부지 좌표: 중앙 바닥 = 원점, -Z = 입구(광장 쪽), 입구에서 안쪽(+Z)을 보면 오른쪽이 -X. 칸 간격 12, 받침대 10×0.6
  const PG = { SPACING: 12, FRONT_MARGIN: 6, PLOT_W: 76, PLOT_D: 80, BASE_TOP: 0.6, PED: 10, PED_H: 0.6 };
  PG.PITCH = (55 * Math.PI) / 180; // ParkGrid.TOP_PITCH
  PG.FIT_HEIGHT = 12; // ParkGrid.TOP_FIT_HEIGHT
  const FIRST_ROW_Z = -PG.PLOT_D / 2 + PG.FRONT_MARGIN + PG.SPACING / 2;
  // ParkGrid.slotOffset: 칸 가운데 (x, z)
  function slotOffset(slot) {
    const [row, column] = SLOT_CELLS[slot - 1];
    return [((GRID + 1) / 2 - column) * PG.SPACING, FIRST_ROW_Z + (row - 1) * PG.SPACING];
  }
  // ParkGrid.topFitPoints(rows): 앞 rows 줄의 받침대 네 귀퉁이 + 앞·뒷줄 명소 꼭대기
  const fitPoints = (rows) => {
    const half = ((GRID - 1) / 2) * PG.SPACING;
    const edge = half + PG.PED / 2;
    const front = FIRST_ROW_Z - PG.PED / 2;
    const back = FIRST_ROW_Z + (rows - 1) * PG.SPACING;
    const tall = PG.BASE_TOP + PG.PED_H + PG.FIT_HEIGHT;
    const pts = [];
    for (const x of [-edge, edge]) pts.push([x, PG.BASE_TOP, front], [x, PG.BASE_TOP, back + PG.PED / 2]);
    for (const x of [-edge, edge]) pts.push([x, tall, FIRST_ROW_Z], [x, tall, back]); // 앞줄 양끝 명소가 옆으로 삐져나가지 않게
    return pts;
  };
  // ParkGrid.topRows: 열린 칸이 있는 줄 + 잠긴 줄 하나(어디가 늘어날지), 최대 GRID
  const topRows = (unlocked) => Math.min(GRID, Math.max(1, Math.ceil(Math.max(unlocked, 0) / GRID) + 1));
  // ParkGrid.project: 카메라(바라보는 곳 tx/tz, 거리 d)로 본 점의 화면 위치(-1..1, 오른쪽·위 +). 카메라 뒤면 null
  function camProject(p, cam) {
    const s = Math.sin(PG.PITCH);
    const c = Math.cos(PG.PITCH);
    const vx = p[0] - cam.tx;
    const vy = p[1] - (PG.BASE_TOP + s * cam.d);
    const vz = p[2] - (cam.tz - c * cam.d);
    const depth = -vy * s + vz * c;
    if (depth <= 0.1) return null;
    const t = Math.tan((cam.fov * Math.PI) / 360);
    return [-vx / (depth * t * cam.aspect), (vy * c + vz * s) / (depth * t)];
  }
  // ParkGrid.topView: HUD 가 가리지 않은 영역(비율 left/right/top/bottom)에 앞 rows 줄이 딱 들어오는 거리 + 바라보는 곳
  function topView(o) {
    const rows = Math.min(GRID, Math.max(1, Math.floor(o.rows || GRID)));
    const FIT_POINTS = fitPoints(rows);
    const cam = { aspect: Math.max(o.aspect, 0.2), fov: Math.min(110, Math.max(20, o.fov || 70)), tx: 0, tz: 0, d: 0 };
    const clampM = (v) => Math.min(0.45, Math.max(0, v || 0));
    const left = -1 + 2 * clampM(o.left);
    const right = 1 - 2 * clampM(o.right);
    const bottom = -1 + 2 * clampM(o.bottom);
    const top = 1 - 2 * clampM(o.top);
    const t = Math.tan((cam.fov * Math.PI) / 360);
    const s = Math.sin(PG.PITCH);
    function aim(d) {
      let tx = 0;
      let tz = FIRST_ROW_Z + ((rows - 1) * PG.SPACING) / 2;
      let width = 0;
      let height = 0;
      let ok = true;
      for (let i = 0; i < 8; i++) {
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        ok = true;
        for (const p of FIT_POINTS) {
          const q = camProject(p, { ...cam, tx, tz, d });
          if (!q) { ok = false; break; }
          minX = Math.min(minX, q[0]); maxX = Math.max(maxX, q[0]);
          minY = Math.min(minY, q[1]); maxY = Math.max(maxY, q[1]);
        }
        if (!ok) break;
        width = maxX - minX;
        height = maxY - minY;
        tx += ((left + right) / 2 - (minX + maxX) / 2) * d * t * cam.aspect;
        tz -= ((bottom + top) / 2 - (minY + maxY) / 2) * d * t / s;
      }
      return { tx, tz, width, height, ok };
    }
    let low = 30;
    let high = 500;
    for (let i = 0; i < 30; i++) {
      const mid = (low + high) / 2;
      const r = aim(mid);
      if (r.ok && r.width <= right - left && r.height <= top - bottom) high = mid;
      else low = mid;
    }
    const r = aim(high);
    return { ...cam, tx: r.tx, tz: r.tz, d: high, rows, region: { left, right, top, bottom } };
  }
  // ParkEdit.topCFrame 과 같은 여백: 위 = 상단바 + 10px, 아래 = 보관함 띠(+ 딱지 줄) 위 끝 + 8px, 옆 3%.
  // 시야각 = ParkEdit.EDIT_FOV(40도, 기본 70 보다 좁혀 원근을 줄임)
  const EDIT_FOV = 40;
  function editCamera(bar, state) {
    const h = view.h;
    return topView({
      rows: topRows(parkSlots(state)[1]),
      aspect: view.w / h,
      fov: EDIT_FOV,
      top: (view.inset + 10) / h,
      bottom: (h - (bar.top + view.inset) + 8) / h,
      left: 0.03,
      right: 0.03,
    });
  }
  // 3D 배치 모드 배경: mockup/edit_backdrops.sh 가 맵 미리보기 도구로 그린 진짜 장면(진짜 ParkService 부지 + 진짜 ParkEdit —
  // 빛나는 판·들고 있는 반투명 복사본·Highlight 강조까지). window.BACKDROPS[이름] = { image, info(hook 값) }
  const backdropFor = (name) => (window.BACKDROPS || {})[name] || null;

  // ParkEdit 아래 띠(보관함) — 치수는 ParkEdit.luau 와 같음(설계 px, Ui.autoScale)
  const EDIT = { BAR_H: 132, BAR_BOTTOM: 12, BAR_EDGE: 16, BAR_MAX_W: 1180, PAD: 10, BUTTON: [92, 108], BUTTON_GAP: 8, CARD: [96, 104], CARD_GAP: 10, CHIP_ROW: 30, JUMP: { small: 100, large: 180 } };
  // ParkEdit.layoutBar: 아래 가운데, 터치 전용 기기는 오른쪽 아래 점프 버튼 자리를 비움. 반환은 이 ScreenGui 좌표(화면 px)
  function editBarLayout() {
    const guiW = view.w;
    const guiH = view.h - view.inset;
    const scale = view.scale;
    const left = EDIT.BAR_EDGE;
    let right = guiW - EDIT.BAR_EDGE;
    if (view.touch) right -= Math.min(view.w, view.h) <= 500 ? EDIT.JUMP.small : EDIT.JUMP.large;
    const width = Math.min(Math.max(right - left, 200), EDIT.BAR_MAX_W * scale);
    const center = Math.min(Math.max(guiW / 2, left + width / 2), right - width / 2);
    return { center, width, bottom: guiH - EDIT.BAR_BOTTOM, top: guiH - EDIT.BAR_BOTTOM - (EDIT.BAR_H + EDIT.CHIP_ROW) * scale };
  }
  // opts: { held: 들고 있는 명소 Id, heldFromStorage: 보관함 카드에서 집음 }
  function buildEditBar(screenGui, state, opts = {}) {
    const layout = editBarLayout();
    const scale = view.scale;
    const bar = anchorBox(screenGui, 'ParkEditBar', [0.5, 1], [0, layout.center, 0, layout.bottom], [0, layout.width / scale, 0, EDIT.BAR_H], 3);
    const tray = gui(bar, { name: 'Tray', size: [1, 0, 1, 0], bg: Theme.Cream, corner: 18, stroke: [Theme.Ink, 4], z: 1 });
    skin(tray, 'panel_paper', { radius: 18, height: EDIT.BAR_H, centerColor: Theme.Cream });
    const [ids, unlocked] = parkSlots(state);
    const heldShown = !!opts.held && ids.includes(opts.held);
    const barButton = (name, icon, text, color, x, anchorRight) =>
      chunkyButton(tray, {
        name,
        anchor: [anchorRight ? 1 : 0, 0.5],
        pos: anchorRight ? [1, -x, 0.5, 0] : [0, x, 0.5, 0],
        size: [0, EDIT.BUTTON[0], 0, EDIT.BUTTON[1]],
        color,
        icon,
        iconSize: 54,
        vertical: true,
        text,
        textSize: 20,
        z: 3,
      });
    barButton('Store', 'crate', '보관', heldShown ? 'Coral' : 'Gray', EDIT.PAD, false);
    const on = state.Settings.AutoPark !== false;
    const auto = barButton('AutoPark', 'podium', '자동', on ? 'Grass' : 'Gray', EDIT.PAD + EDIT.BUTTON[0] + EDIT.BUTTON_GAP, false);
    chip(auto.face, { name: 'On', color: 'Coral', text: 'ON', height: 22, textSize: 15, anchor: [0.5, 0.5], pos: [1, -8, 0, 2], rot: 12, z: 6, visible: on });
    barButton('Done', 'check', '완료', 'Grass', EDIT.PAD, true);
    barButton('View', 'camera', '시점', 'Sky', EDIT.PAD + EDIT.BUTTON[0] + EDIT.BUTTON_GAP, true);

    const side = EDIT.PAD + 2 * (EDIT.BUTTON[0] + EDIT.BUTTON_GAP) + 4;
    const storage = gui(tray, { name: 'Storage', pos: [0, side, 0, 4], size: [1, -side * 2, 1, -8], clip: true, z: 2 });
    storage.style.paddingLeft = EDIT.PAD + 'px';
    list(storage, 'h', EDIT.CARD_GAP, 'left', 'center');
    const shown = new Set(ids.filter(Boolean));
    const better = new Set(betterHidden(state));
    const cards = RarestFirst.filter((l) => (state.Inventory[l.Id] || 0) > 0 && !shown.has(l.Id));
    for (const landmark of cards) {
      const picked = opts.heldFromStorage && opts.held === landmark.Id;
      const card = gui(storage, {
        name: landmark.Id,
        flow: true,
        size: [0, EDIT.CARD[0], 0, EDIT.CARD[1]],
        bg: picked ? FEATURED_BG : Theme.Paper,
        corner: 12,
        stroke: picked ? [COLORS.Sun.Face, 4] : [Theme.Ink, 3],
        uiScale: picked ? 1.08 : 1,
      });
      card.dataset.card = '1';
      card.style.flexShrink = '0';
      photo(card, landmark, [0, 5, 0, 5], [1, -10, 0, EDIT.CARD[1] - 34], 8, EDIT.CARD[1] - 40);
      label(card, { name: 'Stars', anchor: [0.5, 1], pos: [0.5, 0, 1, -4], size: [1, -8, 0, 22], rich: starsRich(stars(state.Inventory[landmark.Id]), Config.STAR_THRESHOLDS.length), outline: 2 }, 19);
      if (better.has(landmark.Id))
        chip(card, { name: 'Better', color: 'Sun', icon: 'arrow_up', iconOnly: true, iconSize: 30, height: 24, strokeThickness: 2, anchor: [0.5, 0.5], pos: [1, -8, 0, 6], rot: 8, z: 4 });
    }
    if (!cards.length) {
      const empty = gui(tray, { name: 'Empty', pos: [0, side, 0, 0], size: [1, -side * 2, 1, 0], z: 2 });
      iconView(empty, 'globe', { anchor: [1, 0.5], pos: [0.5, -4, 0.5, 0], size: [0, 78, 0, 78], transparency: 0.2, z: 3 });
      chip(empty, { name: 'Roll', color: 'Grass', text: '굴리기', height: 32, textSize: 20, anchor: [0, 0.5], pos: [0.5, 4, 0.5, 0], z: 3 });
    }
    const chips = gui(bar, { name: 'Chips', pos: [0, side + 6, 0, -EDIT.CHIP_ROW + 8], size: [1, -(side + 6) * 2, 0, EDIT.CHIP_ROW], z: 4 });
    list(chips, 'h', 10);
    chip(chips, { name: 'Shown', flow: true, color: Theme.Ink, icon: 'park', iconSize: 38, height: 30, textSize: 19, text: `${shown.size}/${unlocked}` });
    chip(chips, { name: 'Income', flow: true, color: 'Grass', icon: 'coin', iconSize: 38, height: 30, textSize: 19, text: '+' + incomeText(incomePerSecond(state)) + '/s' });
    return { bar, layout };
  }

  // 화면 이름표(ParkEdit setTag — ScreenGui, 띠보다 아래 층): 들고 있는 명소 / 가리키는 명소의 등급 색 이름 딱지 + 별.
  // 자리 = hook 이 읽은 진짜 ParkEdit 값(extra.Tag: 아래 가운데, ScreenGui px — 화면 안·띠 위로 가둔 뒤)
  function editTag(screenGui, state, info) {
    const t = info.Tag;
    if (!t || !t.Id) return;
    const landmark = ById[t.Id];
    const holder = gui(screenGui, { name: 'ParkEditTag', anchor: [0.5, 1], pos: [0, t.X, 0, t.Y], size: [0, 240, 0, 58], z: 2, uiScale: view.scale });
    const name = chip(holder, { name: 'Name', color: landmark.Tier.Color, text: landmark.Name, height: 30, textSize: 19, anchor: [0.5, 0], pos: [0.5, 0, 0, 0], z: 2 });
    name.root.dataset.held = '1';
    label(holder, { name: 'Stars', anchor: [0.5, 0], pos: [0.5, 0, 0, 32], size: [0, 140, 0, 24], rich: starsRich(stars(state.Inventory[t.Id]), Config.STAR_THRESHOLDS.length), outline: 2, z: 2 }, 20);
  }

  // 3D 배치 모드 화면 하나: 진짜 장면 그림(배경 — 칸 이름표 BillboardGui 는 배치 모드 동안 꺼짐) + HUD(위쪽 코인·스탯만 —
  // 메뉴·굴리기 줄은 숨김) + 화면 이름표 + 보관함 띠. opts.backdrop = 배경 이름(edit_pc ...)
  function buildEditScreen(root, id, state, opts = {}) {
    const screenGui = newScreen(root, id, { width: opts.width, height: opts.height, touch: opts.touch, world: false });
    const layout = editBarLayout();
    const cam = editCamera(layout, state);
    const screen = screenGui.parentElement;
    const backdrop = backdropFor(opts.backdrop);
    if (backdrop) {
      screen.insertAdjacentHTML('afterbegin', `<img class="world" alt="" src="${backdrop.image}">`);
      screen.dataset.backdrop = opts.backdrop;
    } else {
      screen.insertAdjacentHTML('afterbegin', `<div class="world no-backdrop">배경 없음 — mockup/edit_backdrops.sh 로 ${escapeHtml(opts.backdrop || '')} 를 그린 뒤 build.py</div>`);
    }
    screen.dataset.cam = JSON.stringify({ tx: cam.tx, tz: cam.tz, d: cam.d, aspect: cam.aspect, fov: cam.fov, rows: cam.rows });
    buildStats(screenGui, state);
    buildEditBar(screenGui, state, opts);
    if (backdrop) editTag(screenGui, state, backdrop.info);
    if (opts.toasts) buildNews(screenGui, [], opts.toasts);
    return { screenGui, cam, layout };
  }

  // Panels.openOffset: 기본 창(500) 가운데 = 화면 가운데 + OPEN_OFFSET(아래 굴리기 줄을 덜 가리게 조금 위), 더 높은 창(도감)은
  // 위 끝을 기본 창 위 끝에 맞추고 아래로 늘림(위 알림 줄이 제목 리본에 안 겹치게). 창(배율 적용 + 아래 두께 8)이 화면(ScreenGui)
  // 위아래를 넘으면 넘지 않는 쪽으로 옮김 — 휴대폰(배율 0.55)에서 창 위 끝이 상단바 밑으로 안 들어가게. 화면보다 크면 가운데
  function openOffset(windowHeight) {
    const guiH = view.h - view.inset;
    const half = ((windowHeight + 8) * view.scale) / 2;
    if (half * 2 > guiH) return 0;
    const top = guiH / 2 + OPEN_OFFSET - ((WINDOW_SIZE[1] + 8) * view.scale) / 2;
    return Math.min(Math.max(top + half, half), guiH - half) - guiH / 2;
  }

  function buildPanel(screenGui, name, state, opts = {}) {
    const spec = VIEWS[name]; // (지역 이름을 view 로 두면 화면 배율 view.scale 을 가려서 창이 배율 없이 그려짐)
    const height = opts.windowHeight || spec.Height || WINDOW_SIZE[1];
    const win = uiWindow(screenGui, {
      name: 'Window',
      anchor: opts.anchor || [0.5, 0.5],
      pos: opts.pos || [0.5, 0, 0.5, openOffset(height)],
      size: [0, WINDOW_SIZE[0], 0, height],
      color: spec.Color,
      title: spec.Title,
      ribbonWidth: 220,
      z: 5,
      uiScale: view.scale,
    });
    const top = BODY_TOP;
    const bodyHeight = height - (top + 16);
    if (name === 'Collection') buildCollection(win.body, bodyHeight, state, opts.scrollY || 0, opts.tab || 'All');
    else buildUpgrade(win.body, bodyHeight, state);
    return win;
  }

  // --- 월드 배경 (게임 화면 뒤: 하늘 + 잔디 + 광장 지구본 + 공원 윤곽) -------------------------
  function worldSvg() {
    const tree = (x, y, s, c = '#4fb257') =>
      `<rect x="${x - 3 * s}" y="${y - 10 * s}" width="${6 * s}" height="${12 * s}" fill="#8a6446"/>` +
      `<circle cx="${x}" cy="${y - 20 * s}" r="${14 * s}" fill="${c}"/><circle cx="${x - 8 * s}" cy="${y - 14 * s}" r="${9 * s}" fill="${c}"/>` +
      `<circle cx="${x + 9 * s}" cy="${y - 13 * s}" r="${9 * s}" fill="${c}"/>`;
    const cloud = (x, y, s) =>
      `<g fill="#ffffff" opacity="0.85"><ellipse cx="${x}" cy="${y}" rx="${46 * s}" ry="${16 * s}"/>` +
      `<circle cx="${x - 16 * s}" cy="${y - 10 * s}" r="${17 * s}"/><circle cx="${x + 12 * s}" cy="${y - 14 * s}" r="${22 * s}"/></g>`;
    const plot = (points, fill) => `<polygon points="${points}" fill="${fill}"/>`;
    return `<svg class="world" viewBox="0 0 1280 720" preserveAspectRatio="xMidYMax slice" xmlns="${SVG_NS}" aria-hidden="true">
      <defs>
        <linearGradient id="w-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#4fb0f2"/><stop offset="0.55" stop-color="#a9dcfb"/><stop offset="1" stop-color="#dcf2ff"/>
        </linearGradient>
        <linearGradient id="w-grass" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#94d983"/><stop offset="1" stop-color="#58b554"/>
        </linearGradient>
        <radialGradient id="w-globe" cx="0.36" cy="0.32" r="0.75">
          <stop offset="0" stop-color="#86c9ff"/><stop offset="1" stop-color="#2f7fd6"/>
        </radialGradient>
        <radialGradient id="w-plaza" cx="0.5" cy="0.45" r="0.6">
          <stop offset="0" stop-color="#ece6d6"/><stop offset="1" stop-color="#d6cdb8"/>
        </radialGradient>
      </defs>
      <rect width="1280" height="720" fill="url(#w-sky)"/>
      ${cloud(210, 150, 1.2)}${cloud(1010, 120, 1.4)}${cloud(760, 205, 0.8)}${cloud(1180, 250, 0.7)}
      <path d="M0 440 C120 392 260 404 380 420 C520 380 650 398 780 414 C930 378 1100 396 1280 426 L1280 720 L0 720 Z" fill="#b5e0a6"/>
      <path d="M0 466 C300 448 980 448 1280 466 L1280 720 L0 720 Z" fill="url(#w-grass)"/>
      ${plot('70,500 330,488 360,560 40,578', '#7fcb74')}${plot('950,488 1210,500 1240,578 920,560', '#7fcb74')}
      <g opacity="0.55">
        <rect x="96" y="470" width="16" height="44" fill="#c9b79a"/><polygon points="92,470 116,470 104,452" fill="#b0584e"/>
        <polygon points="160,520 196,520 178,488" fill="#d9bb7a"/>
        <path d="M232 522 v-30 h40 v30 h-10 v-16 a10 10 0 0 0 -20 0 v16 z" fill="#d8ccb2"/>
        <rect x="300" y="498" width="10" height="26" fill="#9aa0b4"/><rect x="296" y="492" width="18" height="8" fill="#9aa0b4"/>
        <polygon points="1000,516 1040,516 1020,480" fill="#d9bb7a"/>
        <rect x="1070" y="470" width="12" height="48" fill="#b98b5a"/><polygon points="1064,472 1088,472 1076,448" fill="#6a8f5a"/>
        <path d="M1120 520 q20 -40 40 0 z" fill="#f2efe6"/><rect x="1136" y="482" width="8" height="10" fill="#e3c887"/>
        <rect x="1180" y="492" width="22" height="30" fill="#cfa46f"/>
      </g>
      ${tree(40, 470, 1.3)}${tree(400, 462, 1)}${tree(880, 462, 1)}${tree(1245, 470, 1.3, '#46a651')}${tree(520, 452, 0.7, '#5bbd62')}${tree(760, 452, 0.7, '#5bbd62')}
      <ellipse cx="640" cy="590" rx="600" ry="150" fill="url(#w-plaza)"/>
      <ellipse cx="640" cy="590" rx="600" ry="150" fill="none" stroke="#c6bca5" stroke-width="3"/>
      <ellipse cx="640" cy="585" rx="420" ry="102" fill="none" stroke="#cbc1ab" stroke-width="2" stroke-dasharray="14 10"/>
      <ellipse cx="640" cy="470" rx="130" ry="26" fill="#cbc2ae"/>
      <path d="M560 468 L720 468 L700 430 L580 430 Z" fill="#d9d1bf"/>
      <rect x="612" y="372" width="56" height="60" fill="#e4ddcc"/>
      <rect x="600" y="364" width="80" height="12" rx="3" fill="#cfc7b3"/>
      <path d="M 552 280 A 88 88 0 0 0 728 280" fill="none" stroke="#e1a92c" stroke-width="9" stroke-linecap="round"/>
      <circle cx="640" cy="276" r="80" fill="url(#w-globe)"/>
      <path d="M598 240 q18 -22 44 -10 q14 10 4 26 q-12 16 -30 10 q-22 -6 -18 -26z M660 290 q16 -8 28 6 q6 18 -10 28 q-18 6 -24 -10 q-2 -14 6 -24z M588 300 q12 -6 18 6 q2 14 -10 16 q-12 0 -8 -22z" fill="#58c46a"/>
      <ellipse cx="612" cy="236" rx="18" ry="10" fill="#ffffff" opacity="0.35"/>
      <rect x="636" y="352" width="8" height="14" fill="#e1a92c"/>
      <g transform="translate(640 572) scale(0.78)">
        <ellipse cx="0" cy="8" rx="46" ry="10" fill="#000" opacity="0.12"/>
        <rect x="-26" y="-58" width="24" height="60" rx="4" fill="#3f8f4b"/><rect x="2" y="-58" width="24" height="60" rx="4" fill="#3f8f4b"/>
        <rect x="-28" y="-122" width="56" height="66" rx="6" fill="#2f6fc2"/>
        <rect x="-50" y="-120" width="21" height="60" rx="5" fill="#f2c98a"/><rect x="29" y="-120" width="21" height="60" rx="5" fill="#f2c98a"/>
        <rect x="-19" y="-160" width="38" height="36" rx="9" fill="#f2c98a"/>
        <rect x="-21" y="-164" width="42" height="18" rx="8" fill="#6b4a33"/>
      </g>
    </svg>`;
  }

  // 화면 하나 (로블록스 창 크기 width x height, 기본 1280x720). 이 화면을 그리는 동안 view(크기·자동 배율)를 이 화면에 맞춤
  function newScreen(parent, id, opts = {}) {
    view.w = opts.width || 1280;
    view.h = opts.height || 720;
    view.scale = uiScaleFor(view.w, view.h);
    view.inset = opts.topbar === false ? 0 : GUI_INSET;
    view.touch = !!opts.touch;
    view.menu = null;
    const screen = document.createElement('div');
    screen.className = 'screen';
    screen.id = id;
    screen.style.width = view.w + 'px';
    screen.style.height = view.h + 'px';
    if (opts.world !== false) screen.insertAdjacentHTML('beforeend', worldSvg());
    else screen.style.background = opts.background || '#8fb4c9';
    if (opts.topbar !== false) {
      screen.insertAdjacentHTML(
        'beforeend',
        '<div class="topbar" aria-hidden="true"><div class="rbx-btn" style="left:12px"><i></i></div><div class="rbx-btn chat" style="left:64px"><i></i></div></div>'
      );
    }
    const screenGui = document.createElement('div');
    screenGui.className = 'gui';
    if (opts.topbar === false) screenGui.style.top = '0';
    screen.appendChild(screenGui);
    parent.appendChild(screen);
    return screenGui;
  }

  // --- 예시 상태 (PlayerState Snapshot 모양) ---------------------------------------
  const STATE = {
    Rolls: 3214,
    Coins: 4832,
    Inventory: {
      clocktower: 1020, lighthouse: 690, windmill: 410, fountain: 300, arc: 170,
      bigben: 98, sungnyemun: 71, pisa: 44, liberty: 31, namsan: 18,
      eiffel: 9, colosseum: 6, tajmahal: 3, angkor: 2,
      sphinx: 12, pyramid: 4, greatwall: 4, alexandria: 1, machupicchu: 1,
      harbourbridge: 520, skytower: 60, apostles: 7,
    },
    Featured: 'alexandria',
    Upgrades: { Globe: 4, Agency: 10, Park: 2, Ticket: 4 },
    Settings: { AutoFeature: true },
  };
  function withDerived(s) {
    s.Luck = luck(s);
    s.Income = incomePerSecond(s);
    return s;
  }
  withDerived(STATE);

  // 굴림 결과(RollResponse)를 PlayerState.applyRoll 과 같은 규칙으로 만듦 -> 게임에서 실제로 나올 수 있는 조합만.
  // 처음 발견 = NEW + 발견 보너스(별 딱지 없음), 이미 가진 명소를 또 찾아 별이 오르면(2~6번째) = "★★☆☆☆ +1" 만(보너스 없음).
  // (환생 전 상태라 Discovered = 보유 기록과 같음)
  function rollResult(s, landmarkId) {
    const before = s.Inventory[landmarkId] || 0;
    const after = before + 1;
    const isNew = before === 0;
    return {
      IsNew: isNew,
      StarUp: before > 0 && stars(after) > stars(before),
      Stars: stars(after),
      Bonus: isNew ? discoveryBonus(ById[landmarkId]) : 0,
    };
  }
  // 연출 중 HUD 는 굴리기 "전" 숫자 (init.client: 연출이 끝난 뒤에 applyState)
  function stateWithout(s, landmarkId) {
    const inventory = { ...s.Inventory };
    delete inventory[landmarkId];
    return withDerived({ ...s, Inventory: inventory, Featured: s.Featured === landmarkId ? null : s.Featured });
  }

  // 6번 공원 배치: 자동 배치에서 시작해 좋아하는 도시 명소(이름이 긴 플린더스 스트리트 역)를 1번 칸(입구 정면)에, 대표 알렉산드리아 등대를
  // 2번 칸에 놓은 직접 배치(열린 12칸이 다 참). 그 두 칸에 있던 더 희귀한 명소들이 전시에서 빠져서 [공원] 버튼에 숫자 배지가 뜸
  const PARK_FAVORITE = 'flindersst';
  const PARK_STATE = withDerived({ ...STATE, Inventory: { ...STATE.Inventory, [PARK_FAVORITE]: 35 }, Settings: { ...STATE.Settings, AutoPark: true }, Display: [] });
  const AUTO_FRONT = parkSlots(STATE)[0][0];
  const AUTO_SECOND = parkSlots(STATE)[0][1];
  setDisplay(PARK_STATE, 1, PARK_FAVORITE);
  setDisplay(PARK_STATE, 2, 'alexandria', AUTO_SECOND); // 칸에 보이던 명소(expected)를 같이 보냄
  withDerived(PARK_STATE);
  // 6번 3D 배치 모드: 1번 칸 명소를 집어 5번 칸(명소 있음 = 자리 바꿈) 위를 가리킴 / 6-4번: 보관함 첫 카드를 집어 3번 칸 위
  const EDIT_TARGET = 5;
  const EDIT_PHONE_TARGET = 3;
  const EDIT_STORAGE_PICK = betterHidden(PARK_STATE)[0];
  // 6-2번: 같은 공원(꽉 참)에서 자동 굴림으로 에베레스트산을 처음 얻음 -> 빈 칸이 없어 전시 안 됨 -> 연출 뒤 "공원 꽉 참" + 배지 +1
  const FULL_FIND = 'everest';
  const PARK_FULL_STATE = withDerived({ ...PARK_STATE, Inventory: { ...PARK_STATE.Inventory, [FULL_FIND]: 1 }, Rolls: PARK_STATE.Rolls + 1 });
  // 6-3번(3D 배치 모드, 빈 보관함): 환생 직후 — 보유 명소·업그레이드 초기화, 공원은 자동 배치로 돌아감(AutoPark = true), 가진 명소 없음
  const REBORN_STATE = withDerived({
    ...STATE,
    Coins: 0,
    Inventory: {},
    Featured: null,
    Upgrades: { Globe: 0, Agency: 0, Park: 0, Ticket: 0 },
    Rebirths: 1,
    Settings: { ...STATE.Settings, AutoPark: true },
    Display: [],
  });
  const TOAST_AUTO_OFF = { text: '자동 꺼짐', icon: 'podium', color: Theme.Ink };
  const TOAST_PARK_FULL = { text: '공원 꽉 참', icon: 'park', color: COLORS.Sun.Face };

  // 2번: 타지마할을 처음 발견 / 2-2번: 앙코르와트를 또 찾아 별이 오름 (2번째 -> 3번째 = ★2)
  const NEW_FIND = 'tajmahal';
  const STAR_FIND = 'angkor';
  const STATE_BEFORE_NEW = stateWithout(STATE, NEW_FIND);
  const REVEAL_NEW = { ...rollResult(STATE_BEFORE_NEW, NEW_FIND), burstRotation: 8 };
  const REVEAL_STAR = { ...rollResult(STATE, STAR_FIND), burstRotation: 20 };

  // 속보는 서버가 OneIn >= ANNOUNCE_ONE_IN 일 때만 보냄 -> 그 조건을 만족하는 명소로
  const NEWS_LANDMARK = ['pyramid', ...List.map((l) => l.Id)]
    .map((id) => ById[id])
    .find((l) => l && l.OneIn >= Config.ANNOUNCE_ONE_IN);
  const NEWS = [{ Name: 'YLTH', LandmarkId: NEWS_LANDMARK.Id, Rolls: 57 }];

  // 3·4번 도감: 1번 상태(자동 배치) + 오세아니아 도장 조건 명소(불가사의 등급까지)를 모두 가짐 -> 도장 1/5, 행운 +25%.
  // 아시아는 아직 몇 개만(흐린 도장 + 회색 +25% + 못 찾은 칸은 어두운 자물쇠 카드)
  const STAMP_REGION = 'Oceania';
  const PARTIAL_REGION = 'Asia';
  const COLLECTION_STATE = { ...STATE, Inventory: { ...STATE.Inventory } };
  for (const l of ByRegion[STAMP_REGION]) {
    if (countsForStamp(l) && !(COLLECTION_STATE.Inventory[l.Id] > 0)) COLLECTION_STATE.Inventory[l.Id] = l.OneIn < 1000 ? 3 : 1;
  }
  withDerived(COLLECTION_STATE);
  const TOAST_STAMP = { name: 'StampToast', text: `도장 +${REGION_BONUS}%`, icon: 'stamp_' + STAMP_REGION.toLowerCase(), color: RegionById[STAMP_REGION].Color, go: true };

  // --- 화면 목록 -------------------------------------------------------------------
  // 받침에 맞는 조사: 을/를
  const eul = (word) => {
    const code = word.charCodeAt(word.length - 1) - 0xac00;
    return word + (code >= 0 && code < 11172 && code % 28 !== 0 ? '을' : '를');
  };
  // 다음 환생 조건 글자: "코인 5,000 + 에펠탑·자유의 여신상"
  function rebirthNeedText() {
    const need = rebirthRequirement(rebirthsOf(STATE));
    if (!need) return '환생 조건';
    const names = need.Landmarks.map((id) => (ById[id] ? ById[id].Name : id)).join('·');
    return `코인 ${commas(need.Coins)}${names ? ' + ' + names : ''}`;
  }
  const newFind = ById[NEW_FIND];
  const starFind = ById[STAR_FIND];
  const newsLandmark = ById[NEWS[0].LandmarkId];
  const SHOTS = [
    {
      id: 'screen1',
      title: '기본 화면',
      note:
        `왼쪽 위: 코인 알약 + 초당 수입 칩, 아래 주사위(굴림 수) · 클로버(행운) 칩(환생 수 · 부스트 시간 칩은 해당될 때만). ` +
        `왼쪽: 도감/강화/환생/공원 버튼 네 개뿐(배치 버튼 없음 — 내 공원에서 내 명소·빈 받침대를 직접 톡 누르면 3D 배치 모드, 6번. 직접 배치 중 더 좋은 명소가 숨으면 [공원] 에 숫자 배지, 6-2 — 여기는 자동 배치라 없음)(PC 는 세로 한 줄, 화면이 낮으면 접힘 — 1-2~1-4; 도감 배지 = 도장 받은 대륙 수 / ${Regions.length}(여권은 도감 대륙 탭으로 합침); 환생 버튼의 "!" 배지는 ` +
        `${rebirthNeedText()}을 채우면 뜸 — 이 예시는 ${commas(STATE.Coins)} 코인이라 아직 안 뜸). ` +
        '환생 버튼 아이콘은 그림 파일이 없어 게임에서 3D 미니 모형으로 나옴(여기선 비슷한 모양으로 대신 그림). ' +
        '상점 버튼(오른쪽)은 Robux 상품 번호가 모두 0 이라 지금 코드로는 안 나옴. ' +
        `아래 가운데: 굴리기(R) + 자동(T, 꺼짐 = 회색). 위 가운데: 다른 사람이 ${eul(newsLandmark.Name)} 찾았을 때 뜨는 서버 전체 속보 띠 ` +
        `(속보는 1 in ${commas(Config.ANNOUNCE_ONE_IN)} 이상만, 7초 뒤 사라짐).`,
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false, location: 'Plaza' });
        buildNews(screenGui, NEWS);
      },
    },
    {
      id: 'screen1t',
      title: '기본 화면 — 4:3 태블릿 1024×768',
      extra: '1-2',
      note:
        `같은 화면을 터치 태블릿 1024×768 에서(자동 배율 ${uiScaleFor(1024, 768).toFixed(2)}). 흐린 점선 = 로블록스 조이스틱 자리(왼쪽 1/3 · 아래 절반), ` +
        `오른쪽 아래 동그라미 = 점프 버튼(게임 UI 가 아님), 키보드가 없어 R/T 키캡은 안 보임. 메뉴는 세로 한 줄이면 조이스틱 자리에 걸려서 ` +
        `${menuNote(1024, 768, true)}로 접혀 스탯과 조이스틱 자리 사이에 들어감(Hud.layoutMenu). 속보 띠는 가운데에 두면 왼쪽 위 스탯과 부딪혀서 ` +
        '부딪히지 않을 만큼만 오른쪽으로 비켜 섬(Hud.placeTop).',
      build(root) {
        const screenGui = newScreen(root, this.id, { width: 1024, height: 768, touch: true });
        buildHud(screenGui, STATE, { auto: false, location: 'Plaza' });
        buildNews(screenGui, NEWS);
      },
    },
    {
      id: 'screen1p',
      title: '기본 화면 — 휴대폰 667×375',
      extra: '1-3',
      note:
        `같은 화면을 휴대폰 가로 667×375 에서(자동 배율 최소값 ${uiScaleFor(667, 375).toFixed(2)}). 세로 한 줄(${Math.round(menuBlock(MENU.length + 1, 1)[1] * uiScaleFor(667, 375))}px)은 ` +
        `화면에 안 들어가서 메뉴가 ${menuNote(667, 375, true)}로 접혀 스탯 칩 줄 바로 아래, 조이스틱 자리(흐린 점선) 위에 놓임 — 버튼 크기는 그대로(앞면 ${Math.round(84 * uiScaleFor(667, 375))}px). ` +
        '속보 띠는 스탯과 메뉴 줄 오른쪽으로 비켜 섬.',
      build(root) {
        const screenGui = newScreen(root, this.id, { width: 667, height: 375, touch: true });
        buildHud(screenGui, STATE, { auto: false, location: 'Plaza' });
        buildNews(screenGui, NEWS);
      },
    },
    {
      id: 'screen1w',
      title: '기본 화면 — 휴대폰 844×390',
      extra: '1-4',
      note:
        `요즘 휴대폰 가로 844×390(자동 배율 ${uiScaleFor(844, 390).toFixed(2)}). 1-3 과 같은 규칙으로 메뉴가 ${menuNote(844, 390, true)}.`,
      build(root) {
        const screenGui = newScreen(root, this.id, { width: 844, height: 390, touch: true });
        buildHud(screenGui, STATE, { auto: false, location: 'Plaza' });
        buildNews(screenGui, NEWS);
      },
    },
    {
      id: 'screen2',
      title: '명소 공개 — 처음 발견',
      note:
        `${eul(newFind.Name)} 처음 찾은 순간: 뒤에 등급 색 햇살(sunburst), 대륙 딱지(${RegionById[newFind.Region].Name}), 등급 리본(${newFind.Tier.Name}), LuckiestGuy 이름 + 확률, ` +
        `아래 딱지 줄 = NEW + 발견 보너스 코인 +${commas(REVEAL_NEW.Bonus)}(실제 계산값). 처음 발견에는 별 딱지가 안 붙습니다(별 0 = ☆☆☆☆☆). ` +
        `연출이 끝나기 전까지 왼쪽 위 숫자는 굴리기 전 값이라 수입이 +${incomeText(STATE_BEFORE_NEW.Income)}/s 로 보임.`,
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE_BEFORE_NEW, { auto: false });
        buildReveal(screenGui, newFind, REVEAL_NEW);
      },
    },
    {
      id: 'screen2b',
      title: '명소 공개 — 별 오름',
      extra: '2-2',
      note:
        `이미 가진 ${eul(starFind.Name)} ${commas(STATE.Inventory[STAR_FIND] + 1)}번째로 찾아 별이 ${REVEAL_STAR.Stars}개가 된 순간(가챠 중복): 딱지 줄에는 보라 "${starUpPlain(REVEAL_STAR.Stars)}" 하나만(보너스 코인 없음, 퐁 튀어나오며 딩). ` +
        `★${MAX_STARS}(6번째 발견)이 되면 "+1" 대신 "MAX", 그 뒤 재발견은 딱지 줄 자체가 안 나옵니다. AUTO 중 별 상승은 알림 줄에도 결과 딱지 + "★+1" 이 2.5초 남음.`,
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false });
        buildReveal(screenGui, starFind, REVEAL_STAR);
      },
    },
    {
      id: 'screen3',
      title: '도감 — 전체 탭',
      note:
        `위 탭 줄: [전체] + 대륙 ${Regions.length}개(${Regions.map((r) => r.Name).join(' · ')}) — 여권 창을 도감에 합침. 탭 = 통통 버튼(대륙 = 도장 그림 + 짧은 이름), ` +
        '고른 탭은 제 색 그대로, 나머지는 옅은 색(글자는 모두 흰 글자 + Ink 테두리). 도장이 아직인 대륙 탭은 앞면 아래 끝에 가는 발견 막대(예전 여권처럼 어느 대륙이 도장에 가까운지 한눈에), ' +
        '도장을 받은 대륙 탭은 막대 대신 도장 그림 오른쪽 위에 작은 체크(앞면 안). ' +
        '전체 탭 = 예전 도감 그대로: 발견한 명소를 희귀한 순서로(위 띠 = 등급 색 + 확률), 왼쪽 위 빨간 "대표" 도장, 사진 왼쪽 아래 초록 칩 = 공원에 전시 중, 오른쪽 위 ×N = 발견 횟수, 아래 별 5칸. ' +
        `머리 줄: 발견 수 / 전체, 여권 아이콘 = 받은 도장 수 / ${Regions.length}, 클로버 = 도장 행운(도장마다 +${REGION_BONUS}%, 없으면 회색), 오른쪽 [자동](자동 대표 지정) — 배치 버튼은 없음(공원에서 직접 누름). ` +
        '[자동]의 ON 딱지는 버튼 오른쪽 아래(위에 두면 바로 위 탭 줄을 가림). ' +
        '도감이 열려 있을 때 도장을 받으면 알림 없이 그 대륙 탭 체크가 톡 튀어나옴(알림 줄이 탭 줄·제목 리본을 가리지 않게 — 알림은 4-3).',
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, COLLECTION_STATE, { auto: false });
        buildPanel(screenGui, 'Collection', COLLECTION_STATE, { tab: 'All' });
      },
    },
    {
      id: 'screen4',
      title: `도감 — 대륙 탭(${RegionById[PARTIAL_REGION].Name}, 도장 아직)`,
      note:
        `대륙 탭 = 그 대륙 명소만, 흔한 순서(여권 한 쪽과 같음). 발견한 명소는 전체 탭과 같은 카드(같은 카드를 옮겨 씀 — 3D 사진을 다시 만들지 않음), ` +
        '못 찾은 명소는 어두운 카드 + 확률 띠 + 자물쇠. 머리 줄: 도장(아직이면 회색으로 물들이고 40% 투명 — 크림 바탕에서도 테두리가 보임) + 발견 막대(대륙 색) "찾은 수/필요 수" + 클로버 +' +
        `${REGION_BONUS}%(받으면 초록, 아직 회색). 도장 조건은 ${Tiers[Config.STAMP_MAX_RANK - 1].Name}(${Config.STAMP_MAX_RANK}등급)까지만 셈 — 더 희귀한 카드는 보이지만 막대 숫자에서 빠짐. ` +
        `${RegionById[PARTIAL_REGION].Name} ${regionProgress(COLLECTION_STATE, PARTIAL_REGION).join('/')}.`,
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, COLLECTION_STATE, { auto: false });
        buildPanel(screenGui, 'Collection', COLLECTION_STATE, { tab: PARTIAL_REGION });
      },
    },
    {
      id: 'screen3p',
      title: '도감 — 휴대폰 667×375, 전체 탭(도장 없음 · 직접 배치)',
      extra: '3-2',
      note:
        `가장 작은 배율 ${uiScaleFor(667, 375).toFixed(2)}: 창 ${Math.round(WINDOW_SIZE[0] * uiScaleFor(667, 375))}×${Math.round(VIEWS.Collection.Height * uiScaleFor(667, 375))}px, ` +
        `탭 앞면 ${Math.round((TAB.HEIGHT - 6) * uiScaleFor(667, 375))}px 높이(머리 줄 [자동] 앞면 ${Math.round(44 * uiScaleFor(667, 375))}px 보다 큼), 탭 글자 ${Math.round(TAB.TEXT * uiScaleFor(667, 375))}px(메뉴 버튼 글자와 같음). ` +
        `6-2 와 같은 공원(직접 배치, 꽉 참): 도장이 아직 없어 도장 행운 딱지는 회색 "+${REGION_BONUS}%"(도장 하나에 이만큼 — 대륙 탭의 회색 +${REGION_BONUS}% 와 같은 뜻, "+0%" 아님), ` +
        `[자동] ${PARK_FULL_STATE.Settings.AutoFeature ? '켜짐(오른쪽 아래 ON 딱지 — 탭 줄을 가리지 않음)' : '꺼짐(회색)'}. 더 좋은데 전시 안 된 명소 수 ${betterHidden(PARK_FULL_STATE).length} 은 창 뒤 메뉴 [공원] 버튼 배지(광장에 있을 때).`,
      build(root) {
        const screenGui = newScreen(root, this.id, { width: 667, height: 375, touch: true });
        buildHud(screenGui, PARK_FULL_STATE, { auto: false });
        buildPanel(screenGui, 'Collection', PARK_FULL_STATE, { tab: 'All' });
      },
    },
    {
      id: 'screen4p',
      title: `도감 — 휴대폰 667×375, ${RegionById[STAMP_REGION].Name} 탭(도장 받음)`,
      extra: '4-2',
      note:
        `다 모은 대륙: 도장이 진하게 찍히고 막대가 꽉 차 오른쪽 끝에 체크, +${REGION_BONUS}% 클로버가 초록. 탭 줄의 ${RegionById[STAMP_REGION].Name} 탭은 발견 막대 대신 작은 체크. ` +
        `맨 아래까지 내린 모습: 도장에 안 세는 ${Tiers[Config.STAMP_MAX_RANK].Name}·${Tiers[Config.STAMP_MAX_RANK + 1].Name} 등급(보너스 수집)은 못 찾았어도 자물쇠 대신 전설 도장 그림 — 막대가 다 찼는데 "덜 모은" 것처럼 보이지 않게. ` +
        `도장 알림(4-3)을 누르거나, 알림을 놓쳤어도 도장을 받은 뒤 처음 도감을 열면 이 탭으로 한 번 열리고 도장이 크게 떴다가 쾅 찍힘. 도감 메뉴 버튼 배지 = [여권] 받은 도장 수.`,
      build(root) {
        const screenGui = newScreen(root, this.id, { width: 667, height: 375, touch: true });
        buildHud(screenGui, COLLECTION_STATE, { auto: false });
        buildPanel(screenGui, 'Collection', COLLECTION_STATE, { tab: STAMP_REGION, scrollY: 'bottom' });
      },
    },
    {
      id: 'screen4s',
      title: `도장 받은 순간 — 휴대폰 667×375(${RegionById[STAMP_REGION].Name})`,
      extra: '4-3',
      note:
        `대륙 도장을 새로 받으면(굴림 연출이 끝난 뒤 · 자동 발견 포함) 행운 소리 + 대륙 색 알림 [도장 그림] "도장 +${REGION_BONUS}%" [→](5초, Hud.stampEarned) — 끝의 화살표 = 누를 수 있는 알림(도감 +N 같은 다른 알림에는 없음). ` +
        '알림 위에서 눌렀다 알림 안에서 떼면(버튼처럼 — 알림에서 시작한 끌기는 안 열림) 알림은 바로 쪼그라들어 사라지고 도감이 그 대륙 탭(4-2)으로 열림(배치 모드면 먼저 나감). ' +
        '도감을 메뉴로 열어도 도장 알림은 치움. 도감이 이미 열려 있으면 알림 대신 그 대륙 탭 체크가 톡. 도감 버튼 배지 [여권] 1/5 도 같이 오름.',
      build(root) {
        const screenGui = newScreen(root, this.id, { width: 667, height: 375, touch: true });
        buildHud(screenGui, COLLECTION_STATE, { auto: false });
        buildNews(screenGui, [], [TOAST_STAMP]);
      },
    },
    {
      id: 'screen6',
      title: '3D 배치 모드 — 명소를 집어 옮기는 중',
      note:
        `배치 버튼 없이 <b>내 공원에서 내 명소를 톡</b>(끌기 = 화면 돌리기는 아님, 남의 공원은 아무 일 없음, 마우스로 가리키면 옅은 흰 강조 + 손가락 커서) 누르면 그 명소를 든 채로, 빈 받침대를 누르면 그 칸을 채울 준비(칸이 초록으로 숨 쉬고 보관함 카드를 누르면 바로 그 칸으로)로 들어감. 창 없이 <b>내 공원 위 3/4 시점</b>(55도, ParkGrid.topView 가 상단바 아래 ~ 띠 위에 열린 줄 + 잠긴 줄 하나를 딱 맞춤 — 칸이 늘면 멀어짐, 휠로 조금 가까이/멀리)으로 카메라가 날아가고 ` +
        `왼쪽 메뉴·상점·굴리기 줄은 숨김(건설 모드). ${ById[PARK_FAVORITE].Name}을 1번 칸(입구 정면)에서 집어 든 상태: 원래 자리는 빈 받침대 + 흰 판, 반투명 복사본(노란 강조 + 흰 테두리, 머리 위 이름 + 별)이 ` +
        `가리키는 ${EDIT_TARGET}번 칸 위에 떠서 살짝 오르내리며 돎 — 놓을 수 있는 칸이 숨 쉬듯 빛남(빈 칸 초록 · 명소 칸 = 자리 바꿈 노랑), 잠긴 칸은 흐린 빨강. ` +
        `여기서 누르면 자리 바꿈(상대가 1번 칸으로 폴짝), 같은 칸 · Esc/Q · 오른쪽 클릭 · 부지 밖 = 내려놓기. 자동 배치 중 첫 편집이라 위에 "자동 꺼짐". ` +
        `아래 띠: [보관](상자 — 들고 있는 전시 명소를 보관함으로, Coral) [자동](시상대) | 보관함 = 전시 안 된 명소(희귀한 순서, 노란 위 화살표 = 전시 칸의 가장 약한 명소보다 좋음 ${betterHidden(PARK_STATE).length}개) | [시점](사진기 — 평소 카메라) [완료]. ` +
        '명소 모형은 여기선 등급 색 상자로 대신 그림(게임에서는 3D 미니어처).',
      build(root) {
        buildEditScreen(root, this.id, PARK_STATE, { backdrop: 'edit_pc', held: PARK_FAVORITE, toasts: [TOAST_AUTO_OFF] });
      },
    },
    {
      id: 'screen6b',
      title: '공원 꽉 참 — 직접 배치 중 더 좋은 명소를 얻음',
      extra: '6-2',
      note:
        `6번 공원(직접 배치, 12칸 꽉 참)에서 자동 굴림으로 ${ById[FULL_FIND].Name}(${ById[FULL_FIND].Tier.Name})을 처음 얻은 뒤: 빈 칸이 없어 전시되지 않았고 ` +
        `연출이 끝나면 노란 알림 [공원] "공원 꽉 참"(PlayerState.missedByFullPark = ${missedByFullPark(PARK_FULL_STATE, FULL_FIND)}). 전시 중인 가장 약한 명소보다 수입이 커서 ` +
        `왼쪽 메뉴 [공원] 배지가 ${betterHidden(PARK_STATE).length} → ${betterHidden(PARK_FULL_STATE).length}(도감 도장 배지와 같은 모양, 광장에 있을 때만 — 공원에 있으면 버튼이 [광장]이라 숨김). ` +
        '자동 배치 중이면 알림·배지 없음(자동 배치가 알아서 채움). 환생하면 자동 배치로 돌아감. [공원] 으로 가서 명소를 톡 누르면 6번 3D 배치 모드(보관함 카드에 노란 위 화살표).',
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, PARK_FULL_STATE, { auto: true, location: 'Plaza' });
        buildNews(screenGui, [], [TOAST_PARK_FULL]);
      },
    },
    {
      id: 'screen6c',
      title: '3D 배치 모드 — 휴대폰 844×390, 빈 보관함(환생 직후)',
      extra: '6-3',
      note:
        `환생 직후(자동 배치, 열린 칸 ${slots(REBORN_STATE)}개 = 옅은 초록 판, 나머지는 흐린 잠긴 칸). 보관함이 비어서 도감처럼 도는 지구본 + "굴리기" 딱지. ` +
        `터치 전용 기기라 띠는 오른쪽 아래 점프 버튼 자리를 비움(위에서 보기에서는 이동을 꺼서 조이스틱·점프 버튼이 안 나오지만 [시점] 으로 평소 카메라를 쓰면 다시 나옴). ` +
        `자동 배율 ${uiScaleFor(844, 390).toFixed(2)}: 띠 버튼 앞면 ${EDIT.BUTTON[0]}×${EDIT.BUTTON[1] - 6} → ${Math.round(EDIT.BUTTON[0] * uiScaleFor(844, 390))}×${Math.round((EDIT.BUTTON[1] - 6) * uiScaleFor(844, 390))}px. 가리키는 1번 칸 = 초록 강조.`,
      build(root) {
        buildEditScreen(root, this.id, REBORN_STATE, { backdrop: 'edit_phone844', width: 844, height: 390, touch: true });
      },
    },
    {
      id: 'screen6p',
      title: '3D 배치 모드 — 휴대폰 667×375, 보관함에서 집음',
      extra: '6-4',
      note:
        `가장 작은 배율 ${uiScaleFor(667, 375).toFixed(2)}. 보관함 카드(${ById[EDIT_STORAGE_PICK].Name})를 톡 눌러 집은 상태 — 그 카드는 노란 바탕 + 굵은 Sun 테두리 + 1.08배, ` +
        `복사본은 가리키는 ${EDIT_PHONE_TARGET}번 칸(명소 있음) 위: 톡 누르면 바꿔 넣기(원래 명소는 보관함으로 톡 튀며 사라짐). [보관] 은 보관함에서 집은 것이라 회색. ` +
        `띠 버튼 앞면 ${Math.round(EDIT.BUTTON[0] * uiScaleFor(667, 375))}×${Math.round((EDIT.BUTTON[1] - 6) * uiScaleFor(667, 375))}px · 카드 ${Math.round(EDIT.CARD[0] * uiScaleFor(667, 375))}×${Math.round(EDIT.CARD[1] * uiScaleFor(667, 375))}px(40px 이상), 보관함은 가로 스크롤. ` +
        '작은 화면에서도 띠 위 영역에 열린 줄 + 잠긴 줄 하나가 딱 들어오도록 같은 계산식으로 카메라 거리를 잡음.',
      build(root) {
        buildEditScreen(root, this.id, PARK_STATE, { backdrop: 'edit_phone667', width: 667, height: 375, touch: true, held: EDIT_STORAGE_PICK, heldFromStorage: true });
      },
    },
    {
      id: 'screen5',
      title: '강화',
      note:
        '업그레이드 4줄: 아이콘 · 이름 + Lv · 지금 값 · 한 번 살 때 바뀌는 양 · 가격 버튼. 살 수 있음 = 노랑, 코인 부족 = 회색, 최대 레벨 = 보라 MAX. ' +
        '<b>참고:</b> 여행사(비행기)·입장료(표) 아이콘(과 HUD 의 환생 아이콘)은 그림 파일이 없어서 게임에서는 3D 미니 모형으로 나옴 — 여기선 비슷한 모양으로 대신 그림.',
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false });
        buildPanel(screenGui, 'Upgrade', STATE);
      },
    },
  ];

  // --- TextScaled 흉내: 상자에 맞는 가장 큰 글자 크기(최대값 이하) ---------------------------
  function fitAll(root) {
    root.querySelectorAll('[data-fit]').forEach((d) => {
      const span = d.querySelector(':scope > span');
      if (!span) return;
      const max = Number(d.dataset.fit);
      const width = d.clientWidth;
      const height = d.clientHeight;
      if (!width || !height) return;
      let lo = 1;
      let hi = max;
      let best = 1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        span.style.fontSize = mid + 'px';
        if (span.scrollWidth <= width + 0.5 && span.offsetWidth <= width + 0.5 && span.offsetHeight <= height + 0.5) {
          best = mid;
          lo = mid + 1;
        } else hi = mid - 1;
      }
      span.style.fontSize = best + 'px';
    });
  }

  function fitFrames() {
    document.querySelectorAll('.frame-wrap').forEach((wrap) => {
      const screen = wrap.firstElementChild;
      const scale = SHOT_MODE ? 1 : Math.min(1, wrap.clientWidth / screen.offsetWidth);
      screen.style.transform = scale < 1 ? `scale(${scale})` : '';
      wrap.style.height = screen.offsetHeight * scale + 'px';
    });
  }

  // 꼬리 그림에서 실제로 칠해진 부분(알파 > 0.03)의 범위 (그림 크기 대비 0..1). main 이 checks 전에 채움
  const TAIL_BOX = {};
  async function measureTailArt() {
    for (const side of ['l', 'r']) {
      const image = ART['ribbon_tail_' + side] ? await loadImage('ribbon_tail_' + side) : null;
      if (!image) continue;
      const w = image.naturalWidth;
      const h = image.naturalHeight;
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(image, 0, 0);
      const data = ctx.getImageData(0, 0, w, h).data;
      let x0 = w;
      let y0 = h;
      let x1 = -1;
      let y1 = -1;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          if (data[(y * w + x) * 4 + 3] > 8) {
            x0 = Math.min(x0, x);
            x1 = Math.max(x1, x);
            y0 = Math.min(y0, y);
            y1 = Math.max(y1, y);
          }
        }
      }
      if (x1 >= 0) TAIL_BOX[side] = { left: x0 / w, top: y0 / h, right: (x1 + 1) / w, bottom: (y1 + 1) / h };
    }
  }

  // --- 고친 점 확인: 다 그린 화면에서 실제 위치·크기를 재서 확인 (게임 코드와 같은 계산식) ----------------------
  // screen 안 좌표(화면 px, 배율 적용 뒤)
  const rectIn = (el, screen) => {
    const r = el.getBoundingClientRect();
    const s = screen.getBoundingClientRect();
    const k = s.width / screen.offsetWidth;
    return { left: (r.left - s.left) / k, right: (r.right - s.left) / k, top: (r.top - s.top) / k, bottom: (r.bottom - s.top) / k };
  };
  const overlap = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5;
  const verdict = (good) => (good ? '<b>OK</b>' : '<b class="bad">문제</b>');

  // 여러 화면 크기(상단바 포함 화면 px) — 휴대폰·태블릿은 터치 전용(조이스틱·점프 버튼), 나머지는 PC
  const SCREEN_SIZES = [
    [1920, 1080, false], [1366, 768, false], [1280, 720, false], [1024, 768, false],
    [1180, 820, true], [1133, 744, true], [1024, 768, true],
    [932, 430, true], [844, 390, true], [667, 375, true], [568, 320, true],
  ];
  const DRAWN_HUD = ['screen1', 'screen1t', 'screen1p', 'screen1w'];

  // 계산식만으로 메뉴 배치를 확인 (ScreenGui 좌표, 화면 px): 스탯 칩 줄 / 굴리기·자동 버튼 / (터치) 조이스틱 자리·점프 버튼 / 화면 밖
  function menuVerdict(w, h, touch, inset) {
    const guiH = h - inset;
    const scale = uiScaleFor(w, h);
    const count = MENU.length + 1;
    const place = layoutMenu(count, w, guiH, h, scale, touch);
    const menu = { left: MENU_X, right: MENU_X + place.width, top: place.top, bottom: place.top + place.height };
    const stats = { left: STATS_POS[0], right: STATS_POS[0] + STATS_SIZE[0] * scale, top: STATS_POS[1], bottom: STATS_POS[1] + STATS_BOTTOM * scale };
    const rollBottom = guiH - ROLL_BAR_BOTTOM;
    const roll = { left: w / 2 - (ROLL_BUTTON[0] / 2) * scale, right: w / 2 + (ROLL_BUTTON[0] / 2 + 16 + AUTO_BUTTON[0]) * scale, top: rollBottom - ROLL_BUTTON[1] * scale, bottom: rollBottom };
    const hits = [];
    if (overlap(menu, stats)) hits.push('스탯');
    if (overlap(menu, roll)) hits.push('굴리기');
    if (touch && overlap(menu, thumbRect(w, guiH, h))) hits.push('조이스틱');
    if (touch && overlap(menu, jumpRect(w, guiH))) hits.push('점프');
    if (menu.top < 0 || menu.bottom > guiH) hits.push('화면 밖');
    return { place, hits, good: !hits.length };
  }

  function checks() {
    const items = [];
    // 0) 왼쪽 메뉴: 그린 화면은 실제로 재고(배지 포함), 다른 화면 크기는 같은 계산식(layoutMenu)으로
    {
      const drawn = [];
      for (const id of DRAWN_HUD) {
        const scr = document.getElementById(id);
        const menuEl = scr && scr.querySelector('[data-name="Menu"]');
        if (!menuEl) continue;
        const parts = Array.from(menuEl.querySelectorAll(':scope > .g, [data-name="Stamps"], [data-name="Ready"]')).filter((el) => el.offsetParent !== null);
        const obstacles = [
          ...['Coins', 'Income', 'Rolls', 'Luck', 'Rebirths'].map((n) => [n, scr.querySelector(`[data-name="Stats"] [data-name="${n}"]`)]),
          ['굴리기', scr.querySelector('[data-name="RollBar"] > [data-name="Roll"]')],
          ['자동', scr.querySelector('[data-name="RollBar"] > [data-name="Auto"]')],
          ['속보', scr.querySelector('[data-name="NewsItem"]')],
          ['조이스틱', scr.querySelector('[data-name="ThumbZone"]')],
          ['점프', scr.querySelector('[data-name="Jump"]')],
        ].filter(([, el]) => el && el.offsetParent !== null);
        const hit = new Set();
        for (const part of parts) {
          const r = rectIn(part, scr);
          for (const [name, el] of obstacles) if (overlap(r, rectIn(el, scr))) hit.add(name);
        }
        const box = parts.map((el) => rectIn(el, scr)).reduce((a, b) => ({ left: Math.min(a.left, b.left), right: Math.max(a.right, b.right), top: Math.min(a.top, b.top), bottom: Math.max(a.bottom, b.bottom) }));
        const guiTop = scr.offsetHeight - scr.querySelector('.gui').offsetHeight;
        drawn.push(
          `${scr.offsetWidth}×${scr.offsetHeight} ${verdict(!hit.size)} ${menuNote(scr.offsetWidth, scr.offsetHeight, id !== 'screen1')} ` +
            `x ${Math.round(box.left)}~${Math.round(box.right)}, y ${Math.round(box.top + guiTop)}~${Math.round(box.bottom + guiTop)}` +
            (hit.size ? ` (겹침: ${[...hit].join(', ')})` : '')
        );
      }
      const computed = [];
      for (const [w, h, touch] of SCREEN_SIZES) {
        for (const inset of touch ? [58, 36] : [58]) {
          const v = menuVerdict(w, h, touch, inset);
          const moved = v.place.columns === 1 && Math.abs(v.place.shift) > 0.01 ? `, ${Math.round(v.place.shift)}px 옮김` : '';
          computed.push(`${w}×${h}${touch ? ' 터치' : ' PC'}${inset !== 58 ? ' 상단바 36' : ''} ${verdict(v.good)} ${menuName(v.place)}${moved}` + (v.hits.length ? ` (겹침: ${v.hits.join(', ')})` : ''));
        }
      }
      items.push(
        `<b>왼쪽 메뉴 vs 스탯·굴리기·조이스틱·점프</b>: 세로 한 줄 → 2열(2줄) → 가로 한 줄 중 스탯 칩 줄 아래~아래쪽 장애물 위 띠에 처음 들어가는 배치(Hud.layoutMenu). ` +
          `그린 화면(버튼 + 배지 실제 크기) — ${drawn.join(' / ')}. 계산식 — ${computed.join(' · ')}.`
      );
    }

    // 1) 위 가운데 묶음(속보 띠) vs 왼쪽 위 스탯: 그린 화면은 실제로 재고, 다른 화면 크기는 같은 계산식(placeTop)으로
    const drawn = [];
    let incomeDesign = null; // 수입 칩 오른쪽 끝(스탯 묶음 기준, 배율 1)
    for (const id of DRAWN_HUD) {
      const scr = document.getElementById(id);
      const newsItem = scr && scr.querySelector('[data-name="NewsItem"]');
      if (!newsItem) continue;
      const bar = rectIn(newsItem, scr);
      const stats = ['Coins', 'Income', 'Rolls', 'Luck'].map((n) => scr.querySelector(`[data-name="Stats"] [data-name="${n}"]`)).filter(Boolean);
      const hit = stats.filter((el) => overlap(rectIn(el, scr), bar)).map((el) => el.dataset.name);
      const income = rectIn(scr.querySelector('[data-name="Income"]'), scr);
      const w = scr.offsetWidth;
      const scale = uiScaleFor(w, scr.offsetHeight);
      if (id === 'screen1') incomeDesign = (income.right - STATS_POS[0]) / scale;
      drawn.push(`${w}×${scr.offsetHeight} ${verdict(!hit.length)} 속보 띠 x ${Math.round(bar.left)}~${Math.round(bar.right)}, 수입 칩 오른쪽 끝 ${Math.round(income.right)}` + (hit.length ? ` (겹침: ${hit.join(', ')})` : ''));
    }
    const computed = SCREEN_SIZES.filter(([w, h, touch]) => touch || !SCREEN_SIZES.some(([w2, h2, t2]) => t2 && w2 === w && h2 === h)).map(([w, h, touch]) => {
      const scale = uiScaleFor(w, h);
      const menu = layoutMenu(MENU.length + 1, w, h - GUI_INSET, h, scale, touch);
      const place = placeTop(w, scale, menu);
      const statsRight = place.reserve; // 가장 긴 수입 글자 기준(+ 가로로 접힌 메뉴 끝)
      const left = place.center - (TOP_WIDTH * scale) / 2;
      const right = place.center + (TOP_WIDTH * scale) / 2;
      const good = place.below || (left >= statsRight && right <= w);
      const where = place.below ? '스탯·메뉴 아래로 내림' : `x ${Math.round(left)}~${Math.round(right)} (스탯${statsRight > STATS_POS[0] + STATS_RESERVE * scale + 0.5 ? '·메뉴' : ''} 끝 ${Math.round(statsRight)})`;
      return `${w}×${h}${touch ? ' 터치' : ''}(배율 ${scale.toFixed(2)}) ${verdict(good)} ${where}`;
    });
    items.push(
      `<b>속보 띠 vs 초당 수입 칩</b>: 속보 묶음 폭 ${TOP_WIDTH}, 가운데가 기본이고 스탯 윗줄(${STATS_RESERVE}×배율)과 겹치면 오른쪽으로 비킴(Hud.placeTop). ` +
        `그린 화면 — ${drawn.join(' / ')}. 계산식 — ${computed.join(' · ')}.` +
        (incomeDesign ? ` (지금 수입 칩 폭 기준 오른쪽 끝 ${incomeDesign.toFixed(0)} ≤ 예약 ${STATS_RESERVE})` : '')
    );

    // 2) 제목 리본(Ui.ribbon): 제목 글자(+ 글자 테두리)가 앞면(Face = 판 - 아래 그림자 띠) 안에 들어가는지,
    //    꼬리(그림에서 실제로 칠해진 부분)·판 테두리가 창 본문 / 닫기 버튼 / 명소 이름과 겹치지 않는지
    const ribbonChecks = [
      { what: '도감 창', id: 'screen3', sel: '[data-name="Ribbon"]' },
      { what: '도감 대륙 탭', id: 'screen4', sel: '[data-name="Ribbon"]' },
      { what: '강화 창', id: 'screen5', sel: '[data-name="Ribbon"]' },
      { what: '등급(처음 발견)', id: 'screen2', sel: '[data-name="TierRibbon"]' },
      { what: '등급(별 오름)', id: 'screen2b', sel: '[data-name="TierRibbon"]' },
    ].map((c) => {
      const scr = document.getElementById(c.id);
      const ribbon = scr && scr.querySelector(c.sel);
      const plate = ribbon && ribbon.querySelector(':scope > [data-name="Plate"]');
      const face = plate && plate.querySelector(':scope > [data-name="Face"]');
      const title = plate && plate.querySelector(':scope > [data-name="Title"]');
      const span = title && title.querySelector(':scope > span');
      if (!span || !face) return `${c.what}: 못 찾음`;
      const plateBox = rectIn(plate, scr);
      const px = (plateBox.right - plateBox.left) / plate.offsetWidth; // 화면 px / 설계 px (UIScale)
      const k = plate.offsetHeight / RIBBON_BASE_HEIGHT;
      const edge = 3 * px; // 판·Frame 꼬리 UIStroke(Border) 3 = 바깥쪽
      const plateOuter = { left: plateBox.left - edge, right: plateBox.right + edge, top: plateBox.top - edge, bottom: plateBox.bottom + edge };
      // 글자 + 글자 테두리(Contextual)가 앞면 안에
      const f = rectIn(face, scr);
      const t = rectIn(span, scr);
      const o = Number(ribbon.dataset.outline || 3) * px;
      const room = Math.min(t.top - o - f.top, f.bottom - (t.bottom + o), t.left - o - f.left, f.right - (t.right + o)) / px;
      const fontSize = parseFloat(span.style.fontSize) || 0;
      const textOk = room >= -0.5;
      // 꼬리: 그림이면 알파가 있는 부분(TAIL_BOX), Frame 꼬리면 테두리까지
      const tailEls = Array.from(ribbon.querySelectorAll(':scope > [data-name="Tail"]'));
      const tails = tailEls.map((el) => {
        const r = rectIn(el, scr);
        if (el.dataset.fallback) return { left: r.left - edge, right: r.right + edge, top: r.top - edge, bottom: r.bottom + edge };
        const b = TAIL_BOX[el.dataset.side] || { left: 0, top: 0, right: 1, bottom: 1 };
        const w = r.right - r.left;
        const h = r.bottom - r.top;
        return { left: r.left + b.left * w, right: r.left + b.right * w, top: r.top + b.top * h, bottom: r.top + b.bottom * h };
      });
      const tailBottom = Math.max(...tails.map((r) => r.bottom));
      const tailOut = (plateBox.left - Math.min(...tails.map((r) => r.left))) / px; // 판 왼쪽 끝 밖으로 나온 꼬리 길이
      const drawn = tailEls.some((el) => el.dataset.fallback) ? 'Frame 꼬리' : '꼬리 그림';
      // 그림이 없을 때(ImageIds.ribbon_tail_* 가 비어 있음)의 Frame 꼬리 아래 끝: 판 위 + (Top 17 + 5 + 36)k + 테두리 3
      const frameTailBottom = plateBox.top + (RIBBON_TAIL.top + 5 + 36) * k * px + edge;
      const parts = [];
      const hits = [];
      let clear = [];
      if (c.sel.includes('TierRibbon')) {
        const nameSpan = ribbon.parentElement.querySelector(':scope > [data-name="Name"] > span');
        const nameLabel = nameSpan && nameSpan.parentElement;
        const n = rectIn(nameSpan, scr);
        const no = parseFloat(nameLabel.style.getPropertyValue('--sw') || '0') / 2 * px;
        const name = { left: n.left - no, right: n.right + no, top: n.top - no, bottom: n.bottom + no };
        if (overlap(plateOuter, name)) hits.push('판-이름');
        tails.forEach((r) => overlap(r, name) && hits.push('꼬리-이름'));
        const gap = (name.top - Math.max(tailBottom, plateOuter.bottom)) / px;
        const side = Math.min(...tails.map((r) => Math.max(r.left - name.right, name.left - r.right))) / px;
        clear.push(`이름(${nameSpan.textContent}) 글자 위 끝까지 ${gap.toFixed(1)}px` + (gap < 0 ? `(대신 꼬리와 옆으로 ${side.toFixed(1)}px 떨어짐)` : ''));
        clear.push(`Frame 꼬리일 때 이름까지 ${((name.top - frameTailBottom) / px).toFixed(1)}px`);
      } else {
        const win = ribbon.parentElement;
        const body = rectIn(win.querySelector('[data-name="Body"]'), scr);
        const close = rectIn(win.querySelector(':scope > [data-name="Close"]'), scr);
        tails.forEach((r) => overlap(r, body) && hits.push('꼬리-본문'));
        if (overlap(plateOuter, body)) hits.push('판-본문');
        tails.forEach((r) => overlap(r, close) && hits.push('꼬리-닫기'));
        if (overlap(plateOuter, close)) hits.push('판-닫기');
        clear.push(`본문 위 끝(BODY_TOP ${BODY_TOP})까지 ${((body.top - tailBottom) / px).toFixed(1)}px`);
        clear.push(`닫기 버튼까지 ${((close.left - Math.max(...tails.map((r) => r.right))) / px).toFixed(1)}px`);
        clear.push(`Frame 꼬리일 때 본문까지 ${((body.top - frameTailBottom) / px).toFixed(1)}px`);
      }
      parts.push(`글자 ${fontSize}px(테두리 포함 앞면 안 여유 ${room.toFixed(1)}px)`);
      parts.push(`판 끝 밖으로 나온 꼬리(${drawn}) ${tailOut.toFixed(1)}px`);
      parts.push(...clear);
      return `${c.what} ${verdict(textOk && !hits.length)} ${parts.join(', ')}` + (hits.length ? ` (겹침: ${[...new Set(hits)].join(', ')})` : '');
    });
    items.push(
      `<b>제목 리본(Ui.ribbon)</b>: 판 높이 50 기준 k 배(창 50 → k 1, 등급 44 → k 0.88), 앞면 = 판 - 아래 ${RIBBON_SHADE}k, 꼬리 ${RIBBON_TAIL.w}×${RIBBON_TAIL.h}k 를 x ${RIBBON_TAIL.left}k(오른쪽은 좌우 뒤집은 자리), y +${RIBBON_TAIL.top}k 에. ` +
        `${ribbonChecks.join(' / ')}.`
    );

    // 3) 알약: 물들이지 않음
    const pills = Array.from(document.querySelectorAll('.skin[data-skin="pill"]'));
    const tinted = pills.filter((el) => el.style.filter);
    items.push(`<b>알약(코인·보너스)</b> ${verdict(pills.length > 0 && !tinted.length)}: pill.png 를 물들이지 않음(ImageColor 흰색, 그림 자체의 반투명 Ink + 광택) — 알약 ${pills.length}개 중 물들인 것 ${tinted.length}개.`);

    // 4) 닫기 버튼: 그림 한 장
    const closes = Array.from(document.querySelectorAll('[data-name="Close"]'));
    const doubled = closes.filter((el) => el.querySelector('.skin'));
    items.push(`<b>닫기 버튼</b> ${verdict(closes.length > 0 && !doubled.length)}: close.png 한 장(${CLOSE_ART_SIZE}px, 통통 버튼 없음) — 창 ${closes.length}개 중 빨간 판이 겹친 것 ${doubled.length}개.`);

    // 5) 딱지 캡슐: 보이는 모서리 반지름 = 보이는 높이의 절반
    const tag = SKINS.tag;
    const chipSkins = Array.from(document.querySelectorAll('.chip > .skin[data-skin="tag"]'));
    let capsules = 0;
    let worst = 0;
    const custom = [];
    for (const el of chipSkins) {
      const scale = Number(el.dataset.scale);
      const h = parseFloat(el.parentElement.style.height); // 숨긴 딱지도 크기는 그대로
      const radius = tag.radius * scale;
      const half = h / 2 - (tag.margin - tag.radius) * scale;
      if (Math.abs(radius - half) <= 0.5) capsules += 1;
      else custom.push(el.parentElement.dataset.name || '?');
      worst = Math.max(worst, Math.abs(radius - half));
    }
    items.push(
      `<b>딱지(tag.png) 캡슐</b>: 반지름 44 · SliceCenter 46..210 → 모서리 조각 = 높이/2 일 때 끝이 반원. 딱지 ${chipSkins.length}개 중 반원 끝 ${capsules}개` +
        (custom.length ? ` (나머지는 일부러 모서리를 준 것: ${[...new Set(custom)].join(', ')})` : '') + '.'
    );

    // 6) 종이 가운데 / MAX 칸
    const paper = document.querySelector('#screen3 [data-name="Panel"] > .skin');
    const stretch = paper ? (paper.offsetWidth - 2 * Number(paper.dataset.slice)) / (SKIN_SIZE - 2 * SKINS.panel_paper.margin) : 0;
    items.push(
      `<b>창 종이</b> ${verdict(!!(paper && paper.dataset.center))}: 가운데 조각(가로 ${stretch.toFixed(1)}배로 늘어나는 부분)을 크림색 평면으로 덮어 점무늬 얼룩 없음(Ui.skin CenterColor). 테두리·바느질선은 그림 그대로.`
    );
    const maxSteps = Array.from(document.querySelectorAll('#screen5 [data-name="Step"]')).filter((el) => el.textContent.includes('MAX'));
    const arrows = maxSteps.filter((el) => el.querySelector('.icon'));
    items.push(`<b>강화 MAX 칸</b> ${verdict(!arrows.length)}: 최대 레벨 줄 ${maxSteps.length}개, 위 화살표가 남은 것 ${arrows.length}개(Ui.showChipIcon).`);

    // 7) 3D 배치 모드: 맞출 줄(열린 줄 + 잠긴 줄 하나)이 상단바 아래 ~ 띠 위(카메라 계산 = ParkGrid.topView), 띠가 화면·스탯·점프 버튼과 안 겹침,
    //    휴대폰 누르는 크기(버튼 앞면·카드 40px 이상), HUD 메뉴·굴리기 줄 없음
    {
      const parts = [];
      let good = true;
      for (const id of ['screen6', 'screen6c', 'screen6p']) {
        const scr = document.getElementById(id);
        const bar = scr && scr.querySelector('[data-name="ParkEditBar"]');
        if (!bar || !scr.dataset.cam) {
          parts.push(`${id}: 못 찾음`);
          good = false;
          continue;
        }
        const w = scr.offsetWidth;
        const h = scr.offsetHeight;
        const cam = JSON.parse(scr.dataset.cam);
        const b = rectIn(bar, scr);
        const tray = rectIn(bar.querySelector('[data-name="Tray"]'), scr);
        const chipsRow = rectIn(bar.querySelector('[data-name="Chips"]'), scr);
        const barTop = Math.min(tray.top, chipsRow.top);
        let minY = Infinity, maxY = -Infinity, minX = Infinity, maxX = -Infinity;
        for (let slot = 1; slot <= cam.rows * GRID; slot++) {
          const [x, z] = slotOffset(slot);
          for (const [dx, dz] of [[-5, -5], [5, -5], [-5, 5], [5, 5]]) {
            const q = camProject([x + dx, PG.BASE_TOP, z + dz], cam);
            const px = [((q[0] + 1) / 2) * w, ((1 - q[1]) / 2) * h];
            minX = Math.min(minX, px[0]); maxX = Math.max(maxX, px[0]);
            minY = Math.min(minY, px[1]); maxY = Math.max(maxY, px[1]);
          }
        }
        const inset = GUI_INSET;
        const fits = minX >= 0 && maxX <= w && minY >= inset && maxY <= barTop;
        const onScreen = b.left >= 0 && b.right <= w + 0.5 && b.bottom <= h + 0.5;
        const stats = scr.querySelector('[data-name="Stats"]');
        const clearStats = !stats || !overlap(rectIn(stats, scr), b);
        const touch = id !== 'screen6';
        const jump = jumpRect(w, h - inset);
        const jumpBox = { left: jump.left, right: jump.right, top: jump.top + inset, bottom: jump.bottom + inset };
        const clearJump = !touch || !overlap(b, jumpBox);
        const faces = Array.from(bar.querySelectorAll('[data-name="Face"]')).map((f) => rectIn(f, scr));
        const minFace = Math.min(...faces.map((f) => Math.min(f.right - f.left, f.bottom - f.top)));
        const cards = Array.from(bar.querySelectorAll('[data-card]')).map((c) => rectIn(c, scr));
        const minCard = cards.length ? Math.min(...cards.map((c) => Math.min(c.right - c.left, c.bottom - c.top))) : null;
        const noHud = !scr.querySelector('[data-name="Menu"]') && !scr.querySelector('[data-name="RollBar"]');
        const big = minFace >= 40 && (minCard == null || minCard >= 40);
        const ok = fits && onScreen && clearStats && clearJump && noHud && big;
        good = good && ok;
        parts.push(
          `${w}×${h} ${verdict(ok)} 앞 ${cam.rows}줄 세로 ${minY.toFixed(0)}~${maxY.toFixed(0)}px(띠 위 끝 ${barTop.toFixed(0)}) · 카메라 거리 ${cam.d.toFixed(0)} · 버튼 앞면 최소 ${minFace.toFixed(0)}px` +
            (minCard != null ? ` · 카드 ${minCard.toFixed(0)}px(${cards.length}장)` : ' · 빈 보관함') +
            (fits ? '' : ' (격자가 가려짐)') + (onScreen ? '' : ' (띠가 화면 밖)') + (clearStats ? '' : ' (스탯과 겹침)') + (clearJump ? '' : ' (점프 버튼과 겹침)') + (noHud ? '' : ' (메뉴·굴리기 줄이 남음)')
        );
      }
      items.push(
        `<b>3D 배치 모드</b> ${verdict(good)}: 맞출 줄(열린 줄 + 잠긴 줄 하나, ParkGrid.topRows)의 받침대 네 귀퉁이가 상단바 아래 ~ 보관함 띠 위에 들어옴(ParkGrid.topView 와 같은 식), 띠가 화면 안 · 스탯/점프 버튼과 안 겹침, ` +
          `왼쪽 메뉴·굴리기 줄 숨김, 띠 버튼·카드는 40px 이상 — ${parts.join(' / ')}.`
      );
    }

    // 7-2) 배경 그림(진짜 장면)이 이 목업과 같은 상태·같은 카메라·같은 띠 자리인지: hook 값(extra) vs 목업 계산
    {
      const cases = [
        { id: 'screen6', state: PARK_STATE, held: PARK_FAVORITE, target: EDIT_TARGET },
        { id: 'screen6c', state: REBORN_STATE, held: null, target: null },
        { id: 'screen6p', state: PARK_STATE, held: EDIT_STORAGE_PICK, target: EDIT_PHONE_TARGET },
      ];
      const parts = [];
      let good = true;
      for (const c of cases) {
        const scr = document.getElementById(c.id);
        const name = scr && scr.dataset.backdrop;
        const backdrop = name && backdropFor(name);
        if (!backdrop || !backdrop.info) {
          parts.push(`${c.id}: 배경 없음`);
          good = false;
          continue;
        }
        const info = backdrop.info;
        const [ids, unlocked] = parkSlots(c.state);
        const shown = new Set(ids.filter(Boolean));
        const storage = RarestFirst.filter((l) => (c.state.Inventory[l.Id] || 0) > 0 && !shown.has(l.Id)).map((l) => l.Id);
        const sameSlots = info.Unlocked === unlocked && JSON.stringify(info.Slots || []) === JSON.stringify(ids.map((v) => v || ''));
        const sameStorage = JSON.stringify(info.Storage || []) === JSON.stringify(storage);
        const sameHeld = (info.Held ? info.Held.Id : null) === c.held && (info.Target || null) === c.target;
        const cam = JSON.parse(scr.dataset.cam);
        const s = Math.sin(PG.PITCH);
        const co = Math.cos(PG.PITCH);
        const eye = [cam.tx, PG.BASE_TOP + s * cam.d, cam.tz - co * cam.d];
        const camGap = Math.hypot(...eye.map((v, i) => v - info.LocalEye[i]));
        const bar = scr.querySelector('[data-name="ParkEditBar"]');
        const tray = rectIn(bar.querySelector('[data-name="Tray"]'), scr);
        const barGap = Math.max(Math.abs(tray.left - info.Bar.Left), Math.abs(tray.top - GUI_INSET - info.Bar.Top), Math.abs(tray.right - tray.left - info.Bar.Width));
        const ok = sameSlots && sameStorage && sameHeld && camGap < 0.5 && barGap < 1.5 && info.Screen.W === scr.offsetWidth && info.Screen.H === scr.offsetHeight;
        good = good && ok;
        parts.push(
          `${c.id} ${verdict(ok)} ${name}: 칸 ${sameSlots ? '같음' : '다름'} · 보관함 ${sameStorage ? '같음' : '다름'} · 든 명소 ${sameHeld ? '같음' : '다름'} · ` +
            `카메라 차이 ${camGap.toFixed(2)} 스터드 · 띠 자리 차이 ${barGap.toFixed(1)}px`
        );
      }
      items.push(
        `<b>3D 배치 모드 배경 = 진짜 장면</b> ${verdict(good)}: 6번대 배경은 mockup/edit_backdrops.sh 가 가짜 Roblox 에서 진짜 ParkService 부지 + 진짜 ParkEdit(클릭으로 집기, 마우스/손가락으로 가리키기)를 돌려 three.js 로 그린 그림. ` +
          `그 장면의 칸 배치·보관함·든 명소·카메라(ParkEdit.topCFrame)·띠 자리가 이 목업 계산(ParkGrid.topView 흉내)과 같은지 — ${parts.join(' / ')}.`
      );
    }

    // 8) [공원] 버튼 배지 = PlayerState.betterHidden 수 (직접 배치 화면만), 자동 배치 화면엔 없음. [배치] 버튼은 어디에도 없음
    {
      const expect = { screen1: betterHidden(STATE).length, screen3: betterHidden(COLLECTION_STATE).length, screen3p: betterHidden(PARK_FULL_STATE).length, screen6b: betterHidden(PARK_FULL_STATE).length };
      const found = Object.entries(expect).map(([id, n]) => {
        const scr = document.getElementById(id);
        const badge = scr && scr.querySelector('[data-name="Menu"] [data-name="Teleport"] [data-name="Better"]');
        const shown = badge && badge.style.display !== 'none' ? Number(badge.textContent) : 0;
        return { id, n, shown, ok: shown === n };
      });
      const arrange = document.querySelectorAll('[data-name="Arrange"]').length;
      items.push(
        `<b>[공원] 버튼 배지 · [배치] 버튼 없음</b> ${verdict(found.every((f) => f.ok) && arrange === 0)}: 직접 배치 중 전시 칸의 가장 약한 명소보다 수입이 큰, 전시 안 된 명소 수(0 이면 숨김) — ` +
          found.map((f) => `${f.id} ${f.shown}${f.ok ? '' : `(기대 ${f.n})`}`).join(' · ') + ` · [배치] 버튼 ${arrange}개.`
      );
    }

    // 도감 대륙 탭: 탭 글자가 줄지 않고 들어감(TextScaled 최대값 그대로), 휴대폰에서 탭 앞면 크기, 창이 화면(상단바 아래) 안,
    // 보이는 카드 수(전체 = 발견한 명소, 대륙 = 그 대륙 명소 전부)와 대륙 머리 줄 숫자 = regionProgress
    {
      const parts = [];
      let good = true;
      const collectionShots = [['screen3', 'All', COLLECTION_STATE], ['screen4', PARTIAL_REGION, COLLECTION_STATE], ['screen3p', 'All', PARK_FULL_STATE], ['screen4p', STAMP_REGION, COLLECTION_STATE]];
      for (const [id, tab, shotState] of collectionShots) {
        const scr = document.getElementById(id);
        const win = scr && scr.querySelector('[data-name="Window"]');
        const row = win && win.querySelector('[data-name="Tabs"]');
        if (!row) {
          parts.push(`${id}: 못 찾음`);
          good = false;
          continue;
        }
        const scale = uiScaleFor(scr.offsetWidth, scr.offsetHeight);
        const labels = Array.from(row.querySelectorAll('[data-name="Face"] > [data-name="Label"] > span'));
        const sizes = labels.map((span) => parseFloat(span.style.fontSize) || 0);
        const smallest = Math.min(...sizes);
        const face = rectIn(row.querySelector('[data-name="Face"]'), scr);
        const guiTop = scr.offsetHeight - scr.querySelector('.gui').offsetHeight;
        const box = rectIn(win.querySelector('[data-name="Panel"]'), scr);
        const inside = box.top >= guiTop - 0.5 && box.bottom <= scr.offsetHeight + 0.5;
        const cards = win.querySelectorAll('[data-name="Content"] > .g').length;
        const want = tab === 'All' ? List.filter((l) => isDiscovered(shotState, l.Id)).length : ByRegion[tab].length;
        let numbers = '';
        let numbersOk = true;
        if (tab !== 'All') {
          const [found, required] = regionProgress(shotState, tab);
          const shown = win.querySelector('[data-name="RegionHeader"] [data-name="Count"]').textContent;
          numbersOk = shown === `${found}/${required}`;
          numbers = ` · 막대 ${shown}`;
        }
        // 대륙 탭: 도장 아직 = 발견 막대(채움 = regionProgress, 글자 아래 끝보다 아래), 받음 = 막대 없이 체크(앞면 안)
        const done = new Set(completedRegions(shotState));
        let stripsOk = true;
        let tabBits = [];
        for (const region of Regions) {
          const button = row.querySelector(`[data-name="Tab${region.Id}"]`);
          const faceRect = rectIn(button.querySelector('[data-name="Face"]'), scr);
          const strip = button.querySelector('[data-name="Strip"]');
          const mark = button.querySelector('[data-name="Stamped"]');
          if (done.has(region.Id)) {
            const r = mark && rectIn(mark, scr);
            const within = r && r.left >= faceRect.left - 0.5 && r.right <= faceRect.right + 0.5 && r.top >= faceRect.top - 0.5 && r.bottom <= faceRect.bottom + 0.5;
            stripsOk = stripsOk && !strip && !!within;
            tabBits.push(`${region.Name} 체크${within ? '' : '(앞면 밖)'}`);
          } else {
            const [found, required] = regionProgress(shotState, region.Id);
            const fill = strip && strip.querySelector('[data-name="Fill"]');
            const width = (r) => r.right - r.left;
            const ratio = fill ? width(rectIn(fill, scr)) / width(rectIn(strip, scr)) : -1;
            const text = rectIn(button.querySelector('[data-name="Label"] > span'), scr);
            const clear = strip && text.bottom <= rectIn(strip, scr).top + 0.5;
            const right = !mark && Math.abs(ratio - found / required) < 0.02 && clear;
            stripsOk = stripsOk && right;
            tabBits.push(`${region.Name} 막대 ${found}/${required}${clear ? '' : '(글자와 겹침)'}`);
          }
        }
        // 머리 줄 버튼 배지(ON)가 탭 줄을 가리지 않음
        const tabRect = rectIn(row, scr);
        const badges = Array.from(win.querySelectorAll('[data-name="CollectionHeader"] [data-name="On"], [data-name="CollectionHeader"] [data-name="Better"]')).filter((el) => el.offsetParent !== null);
        const badgeHit = badges.some((el) => rectIn(el, scr).top < tabRect.bottom - 0.5);
        const ok = labels.length === Regions.length + 1 && smallest >= TAB.TEXT - 0.01 && inside && cards === want && numbersOk && stripsOk && !badgeHit;
        good = good && ok;
        parts.push(
          `${id}(${tab === 'All' ? '전체' : RegionById[tab].Name}) ${verdict(ok)} 탭 ${labels.length}개 글자 ${smallest}px(화면 ${(smallest * scale).toFixed(1)}px) · ` +
            `탭 앞면 ${Math.round(face.right - face.left)}×${Math.round(face.bottom - face.top)}px · 창 ${inside ? '화면 안' : '화면 밖으로 나감'} · 카드 ${cards}/${want}${numbers} · ` +
            `${tabBits.join(', ')} · 머리 줄 배지 ${badges.length}개 ${badgeHit ? '탭 줄을 가림' : '탭 줄 안 가림'}`
        );
      }
      items.push(`<b>도감 대륙 탭</b> ${verdict(good)}: ` + parts.join(' / ') + '.');
    }

    const section = document.getElementById('findings');
    if (section) {
      section.innerHTML =
        '<h2>고친 점 확인 <span class="sub">(게임 코드와 같은 크기·계산식으로 그린 뒤 재어 봄)</span></h2><ol>' +
        items.map((t) => `<li>${t}</li>`).join('') +
        '</ol>';
    }
    return items;
  }

  async function main() {
    const shots = document.getElementById('shots');
    if (SHOT_MODE) document.body.classList.add('shot-mode');
    // 글꼴을 못 넣었으면(네트워크 없음) 로컬 대체 글꼴을 굵게
    if (!(window.FONTS_EMBEDDED || []).includes('fredoka')) document.body.classList.add('no-webfonts');
    SHOTS.forEach((shot) => {
      const section = document.createElement('section');
      section.className = 'shot';
      const number = shot.extra || String(SHOTS.filter((s) => !s.extra).indexOf(shot) + 1);
      section.innerHTML = `<h2><span class="num">${number}.</span>${escapeHtml(shot.title)}</h2><p class="note">${shot.note}</p>`;
      const wrap = document.createElement('div');
      wrap.className = 'frame-wrap';
      section.appendChild(wrap);
      shots.appendChild(section);
      shot.build(wrap);
    });

    try {
      await Promise.all(
        ['20px "Fredoka One"', '20px "Luckiest Guy"', '20px "KR Fallback"'].map((f) => document.fonts.load(f, '가A★'))
      );
      await document.fonts.ready;
    } catch (e) {
      /* 글꼴이 없어도 대체 글꼴로 계속 */
    }
    await Promise.all(
      Array.from(document.images).map((img) => (img.complete ? null : new Promise((r) => (img.onload = img.onerror = r))))
    );
    fitAll(document);
    await paintSkins(document);
    fitFrames();
    try {
      await measureTailArt();
    } catch (e) {
      console.warn('measureTailArt', e);
    }
    let found = [];
    try {
      found = checks();
    } catch (e) {
      console.warn('checks', e);
      found = ['checks 실패: ' + e];
    }
    window.addEventListener('resize', fitFrames);
    window.__MOCKUP = { STATE, SHOTS: SHOTS.map((s) => s.id), fonts: window.FONTS_EMBEDDED, findings: found };
    window.__MOCKUP_READY = true;
  }

  main();
})();
