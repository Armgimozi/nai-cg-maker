'use strict';
// 랜드마크 RNG UI 미리보기.
// src/client/Ui.luau · Hud.luau · Panels.luau 의 크기/위치/색을 그대로 옮긴 작은 "로블록스 GUI 흉내" 입니다.
//  - UDim2(scale, offset) + AnchorPoint + Rotation -> CSS left/top/width/height + transform
//  - UIScale(Ui.autoScale) -> transform: scale() (AnchorPoint 기준)
//  - UIStroke(Border) -> box-shadow (테두리 바깥쪽), UIStroke(Contextual, 글자) -> -webkit-text-stroke + paint-order
//  - 9-slice 스킨(ScaleType.Slice, SliceCenter 64..192, SliceScale) -> border-image 64 fill / (64*SliceScale)px
//  - ImageColor3(곱하기) -> SVG feColorMatrix 필터, ImageTransparency -> opacity
//  - TextScaled + UITextSizeConstraint -> 상자에 맞을 때까지 글자 크기를 줄임(최대값까지)
// ImageIds 가 모두 채워졌다고 가정(그림 버전). ViewportFrame(명소 3D 모형)은 "3D 모형 자리"로 대신 그립니다.
(function () {
  const GAME = window.GAME;
  const ART = window.ART;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const SHOT_MODE = /[?&]shot=1/.test(location.search);

  // --- Ui.luau 상수 -------------------------------------------------------------
  const UI_SCALE = 0.9; // Ui.autoScale: clamp(min(1280/1280, 720/720), 0.55, 0.9) -> 0.9
  const GUI_INSET = 58; // 로블록스 기본 상단바 (ScreenGui.IgnoreGuiInset = false)
  const SCREEN_W = 1280;
  const SCREEN_H = 720 - GUI_INSET;
  const SHADOW_DEPTH = 6;
  const BUTTON_CORNER = 14;
  const SLICE_MARGIN = 64;
  const SKIN_RADIUS = 50;
  const RIBBON_HEIGHT = 54;

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
  const colorPair = (name) => COLORS[name] || COLORS.Gray;

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
  const countsForStamp = (l) => l.Tier.Rank <= Config.STAMP_MAX_RANK;
  function regionProgress(s, regionId) {
    let found = 0;
    let required = 0;
    for (const l of ByRegion[regionId] || []) {
      if (countsForStamp(l)) {
        required += 1;
        if ((s.Inventory[l.Id] || 0) > 0) found += 1;
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
      (1 + Config.REGION_LUCK_BONUS * completedRegions(s).length)
    );
  }
  const slots = (s) => Config.BASE_SLOTS + UpgradesById.Park.PerLevel * upgradeLevel(s, 'Park');
  function stars(count) {
    let n = 0;
    Config.STAR_THRESHOLDS.forEach((threshold, i) => {
      if (count >= threshold) n = i + 1;
    });
    return n;
  }
  function park(s) {
    const result = [];
    for (const l of RarestFirst) {
      if (result.length >= slots(s)) break;
      if ((s.Inventory[l.Id] || 0) > 0) result.push(l.Id);
    }
    return result;
  }
  function landmarkIncome(l, count) {
    const n = stars(count);
    if (n === 0) return 0;
    return (Config.TIER_INCOME[l.Tier.Rank - 1] || 0) * (1 + Config.STAR_INCOME_BONUS * (n - 1));
  }
  function incomePerSecond(s) {
    let total = 0;
    for (const id of park(s)) total += landmarkIncome(ById[id], s.Inventory[id]);
    return total * (1 + UpgradesById.Ticket.PerLevel * upgradeLevel(s, 'Ticket'));
  }
  const discoveryBonus = (l) => Math.ceil(Config.DISCOVERY_BONUS_MULT * Math.pow(l.OneIn, 0.5));

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
  const oneIn = (n) => '1 in ' + (n >= 1e6 ? short(n) : commas(n));
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

  function sliceScale(radius, height) {
    let scale = radius / SKIN_RADIUS;
    if (height != null) scale = Math.min(scale, height / 2 / SLICE_MARGIN);
    return scale;
  }

  // Ui.skin / Ui.box: 9-slice 그림을 대상 맨 뒤(ZIndex 0)에 깔고 대상의 바탕·테두리는 끔
  function skin(target, name, o = {}) {
    target.style.backgroundColor = 'transparent';
    target.style.boxShadow = 'none';
    const img = document.createElement('div');
    img.className = 'skin';
    img.dataset.skin = name;
    if (o.radius != null) {
      // border-image 는 조각 사이에 가는 틈(이음새)이 생겨서, 화면을 다 만든 뒤 paintSkins 가 canvas 로 다시 그림
      const w = SLICE_MARGIN * sliceScale(o.radius, o.height);
      img.dataset.slice = String(w);
      img.style.borderImage = `url(${ART[name]}) 64 fill / ${+w.toFixed(3)}px stretch`;
    } else {
      img.classList.add('stretch');
      img.style.backgroundImage = `url(${ART[name]})`;
    }
    applyLook(img, o.color, o.transparency || 0);
    target.insertBefore(img, target.firstChild);
    return img;
  }

  // 9-slice 를 canvas 한 장에 그림 (SliceCenter 64..192 / 256, 모서리 = 64 x SliceScale).
  // 조각 경계를 정수 픽셀에 맞춰서 이음새가 없음. 물들이기(ImageColor3)는 부모 div 의 SVG 필터가 그대로 맡음.
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
      const margin = (size * SLICE_MARGIN) / 256;
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
    if (o.scaled === false) {
      d.classList.add('nowrap');
      span.style.fontSize = Math.min(o.textSize ?? 14, max) + 'px';
    } else d.dataset.fit = String(max);
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
    // Icons.BUILDERS.rebirth: 금색 고리 화살표 2개(100°~, 280°~ 각 4조각 + 화살촉) + 가운데 초록 위 화살표
    rebirth: svgUri(`<g stroke-linecap="butt" fill="none">
      <path d="M 52.9 16.1 A 34 34 0 0 0 19.2 64.4" stroke="#ffc53d" stroke-width="11"/>
      <path d="M 47.1 83.9 A 34 34 0 0 0 80.8 35.6" stroke="#ffc53d" stroke-width="11"/></g>
      <path d="M 12.8 51.1 L 38.7 78.9 L 20.6 63.2 Z" fill="#ffc53d"/>
      <path d="M 87.2 48.9 L 61.3 21.1 L 79.4 36.8 Z" fill="#ffc53d"/>
      <path d="M 12.8 51.1 L 38.7 78.9 L 25.6 58.2 Z" fill="#d9a22e"/>
      <path d="M 87.2 48.9 L 61.3 21.1 L 74.4 41.8 Z" fill="#d9a22e"/>
      <rect x="45.3" y="50" width="9.4" height="16" fill="#60c45a"/>
      <path d="M 37.2 50.5 L 62.8 50.5 L 50 34 Z" fill="#60c45a"/>`),
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
    skin(panel, 'panel_paper', { radius: 18 }); // 안쪽 종이 테두리(Inner)는 그림에 들어 있어서 숨김

    const ribbon = gui(root, {
      name: 'Ribbon',
      anchor: [0.5, 0.5],
      pos: [0.5, 0, 0, 4],
      size: [0, o.ribbonWidth || 340, 0, RIBBON_HEIGHT],
      z: 3,
    });
    const main = gui(ribbon, { name: 'Main', size: [1, 0, 1, 0], z: 2, corner: 12 });
    skin(main, 'ribbon', { radius: 14, height: RIBBON_HEIGHT, color: colorPair(o.color || 'Sky').Face }); // 꼬리 Frame 은 숨김
    const title = label(main, { name: 'Title', pos: [0, 14, 0, 5], size: [1, -28, 1, -10], text: o.title || '', color: WHITE, z: 3, outline: 3 }, 32);

    const close = chunkyButton(root, {
      name: 'Close',
      color: 'Coral',
      round: true,
      anchor: [0.5, 0.5],
      pos: [1, -8, 0, 8],
      size: [0, 52, 0, 58],
      text: '',
      icon: 'close',
      iconSize: 34,
      textSize: 30,
      outlineThickness: 3,
      z: 4,
    });
    const top = RIBBON_HEIGHT / 2 + 4 + 14;
    const body = gui(panel, { name: 'Body', pos: [0, 18, 0, top], size: [1, -36, 1, -(top + 16)] });
    return { root, panel, body, ribbon, title, close };
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
    // Ui.box("pill", { Color = Theme.Ink, Transparency = 0.3 }) -> 그림(이미 Ink 색)에 Ink 를 한 번 더 곱함
    skin(root, 'pill', { radius: height / 2, height, color: Theme.Ink, transparency: o.bgT ?? 0.3 });
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
    const pad = Math.floor(height * 0.42);
    const iconPad = Math.floor(height * 0.12);
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
    return gui(screenGui, { name, anchor, pos, size, z: z || 1, uiScale: UI_SCALE });
  }

  // Hud: 왼쪽 위 스탯
  function buildStats(screenGui, state) {
    const COIN_PILL = [230, 52];
    const container = anchorBox(screenGui, 'Stats', [0, 0], [0, 14, 0, 12], [0, 420, 0, 112]);
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
  }

  // Hud: 왼쪽 메뉴 버튼 4개
  const MENU = [
    { Id: 'Collection', Text: '도감', Color: 'Sky', Icon: 'album' },
    { Id: 'Passport', Text: '여권', Color: 'Grape', Icon: 'passport' },
    { Id: 'Upgrade', Text: '강화', Color: 'Sun', Icon: 'hammer' },
  ];
  function buildMenu(screenGui, state, location) {
    const count = MENU.length + 1;
    const gap = 12;
    const container = anchorBox(screenGui, 'Menu', [0, 0.5], [0, 14, 0.5, 16], [0, 84 + 8, 0, count * 90 + (count - 1) * gap]);
    list(container, 'v', gap);
    for (const entry of MENU) {
      const button = chunkyButton(container, {
        name: entry.Id,
        flow: true,
        size: [0, 84, 0, 90],
        color: entry.Color,
        icon: entry.Icon,
        iconSize: 58,
        vertical: true,
        text: entry.Text,
        textSize: 18,
      });
      if (entry.Id === 'Passport') {
        const stamps = completedRegions(state).length;
        chip(button.face, {
          name: 'Stamps',
          color: Theme.Ink,
          height: 24,
          textSize: 15,
          anchor: [0.5, 0.5],
          pos: [1, -6, 0, 2],
          rot: 8,
          z: 6,
          text: `${stamps}/${Regions.length}`,
          textColor: stamps > 0 ? COLORS.Sun.Face : WHITE,
        });
      }
    }
    const inPark = location === 'Park';
    chunkyButton(container, {
      name: 'Teleport',
      flow: true,
      size: [0, 84, 0, 90],
      color: 'Grass',
      icon: inPark ? 'plaza' : 'park',
      iconSize: 58,
      vertical: true,
      text: inPark ? '광장' : '공원',
      textSize: 18,
    });
  }

  // Hud: 굴리기 + 자동
  function buildRollBar(screenGui, opts) {
    const ROLL = [270, 90];
    const AUTO = [140, 76];
    const width = ROLL[0] + 2 * (AUTO[0] + 16);
    const container = anchorBox(screenGui, 'RollBar', [0.5, 1], [0.5, 0, 1, -14], [0, width, 0, 100]);
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
    buildStats(screenGui, state);
    buildMenu(screenGui, state, opts.location || 'Plaza');
    buildRollBar(screenGui, opts);
  }

  // Hud.news: 신문 띠 한 줄
  function buildNews(screenGui, items) {
    const news = anchorBox(screenGui, 'News', [0.5, 0], [0.5, 0, 0, 10], [0, 720, 0, 118], 9);
    list(news, 'v', 8, 'center', 'top');
    for (const item of items) {
      const landmark = ById[item.LandmarkId];
      const tier = landmark.Tier;
      const row = gui(news, { name: 'NewsItem', flow: true, size: [1, 0, 0, 54] });
      const slide = gui(row, { anchor: [0.5, 0.5], pos: [0.5, 0, 0.5, 0], size: [1, 0, 1, 0] });
      const bar = gui(slide, { pos: [0, 56, 0, 4], size: [1, -56, 1, -8], bg: Theme.Cream, z: 1, corner: 10, stroke: [Theme.Ink, 3] });
      skin(bar, 'panel_paper', { radius: 10, height: 46 });
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

    const ribbon = gui(inner, { name: 'TierRibbon', anchor: [0.5, 0.5], pos: [0.5, 0, 0, centerY + VIEW_SIZE / 2], size: [0, 250, 0, 44], z: 4 });
    const ribbonMain = gui(ribbon, { size: [1, 0, 1, 0], z: 2, corner: 10 });
    skin(ribbonMain, 'ribbon', { radius: 12, height: 44, color: tier.Color });
    label(ribbonMain, { pos: [0, 10, 0, 4], size: [1, -20, 1, -8], text: tier.Name, color: WHITE, z: 3, outline: 2.5 }, 28);

    const nameTop = centerY + VIEW_SIZE / 2 + 28;
    label(inner, { name: 'Name', pos: [0, 0, 0, nameTop], size: [1, 0, 0, 66], font: 'title', text: landmark.Name, color: tier.Color, z: 4, outline: 4 }, 62);
    label(inner, { name: 'Odds', pos: [0, 0, 0, nameTop + 66], size: [1, 0, 0, 30], font: 'title', text: oneIn(landmark.OneIn), color: WHITE, z: 4, outline: 2.5 }, 28);

    const tagRow = gui(inner, { name: 'Tags', pos: [0, 0, 0, nameTop + 104], size: [1, 0, 0, 36], z: 4 });
    list(tagRow, 'h', 14, 'center');
    chip(tagRow, { name: 'New', flow: true, color: 'Coral', text: 'NEW', font: 'title', height: 32, textSize: 22, visible: info.IsNew });
    chip(tagRow, { name: 'StarUp', flow: true, color: 'Grape', font: 'title', height: 32, textSize: 21, text: `★${info.Stars} UP`, visible: info.StarUp });
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
  const VIEWS = {
    Collection: { Title: '도감', Color: 'Sky', Top: HEADER_HEIGHT },
    Passport: { Title: '여권', Color: 'Grape', Top: HEADER_HEIGHT },
    Upgrade: { Title: '강화', Color: 'Sun', Top: 4 },
  };
  const WINDOW_SIZE = [760, 500];
  const OPEN_OFFSET = -30;
  const PAD_X = 6;
  const PAD_RIGHT = 14;
  const PAD_Y = 6;
  const REGION_BONUS = Math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5);
  const gridHeight = (count, columns, cellHeight, gap) => {
    const rows = Math.ceil(count / columns);
    return rows <= 0 ? 0 : rows * (cellHeight + gap) - gap;
  };

  function headerChip(parent, icon, color, text, iconTransparency) {
    return chip(parent, { flow: true, color, icon, iconSize: 44, height: 34, textSize: 21, text, iconTransparency });
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

  function collectionCard(parent, landmark, count, featured, shown) {
    const tier = landmark.Tier;
    const card = gui(parent, { name: landmark.Id, flow: true, size: [0, 128, 0, 184], bg: featured ? FEATURED_BG : Theme.Paper, corner: 12, stroke: [Theme.Ink, 3] });
    const band = gui(card, { name: 'Band', size: [1, 0, 0, 26], bg: tier.Color, corner: 12 });
    gui(band, { pos: [0, 0, 1, -12], size: [1, 0, 0, 12], bg: tier.Color });
    gui(band, { pos: [0, 0, 1, 0], size: [1, 0, 0, 3], bg: Theme.Ink });
    label(band, { pos: [0, 8, 0, 4], size: [1, -16, 1, -7], text: oneIn(landmark.OneIn), color: WHITE, z: 2, outline: 1.5 }, 15);
    photo(card, landmark, [0, 7, 0, 33], [1, -14, 0, 84], 8, 80);
    label(card, { pos: [0, 6, 0, 122], size: [1, -12, 0, 24], text: landmark.Name }, 19);
    label(card, { pos: [0, 6, 0, 149], size: [1, -12, 0, 24], rich: starsRich(stars(count), Config.STAR_THRESHOLDS.length), outline: 2 }, 22);
    chip(card, { name: 'Count', color: Theme.Ink, height: 22, textSize: 14, outline: false, anchor: [1, 0], pos: [1, -3, 0, 29], z: 3, text: '×' + commas(count) });
    chip(card, { name: 'Featured', color: 'Coral', text: '대표', height: 28, textSize: 17, cornerRadius: 7, rot: -14, pos: [0, -8, 0, 22], z: 4, visible: featured });
    if (shown) chip(card, { name: 'Shown', color: 'Grass', icon: 'park', iconOnly: true, iconSize: 30, height: 24, pos: [0, 3, 0, 94], z: 3 });
  }

  function buildCollection(body, bodyHeight, state, scrollY) {
    const COLS = 5;
    const CELL = [128, 184];
    const GAP = 12;
    const header = gui(body, { name: 'CollectionHeader', size: [1, 0, 0, HEADER_HEIGHT] });
    const chips = chipRow(header);
    const owned = RarestFirst.filter((l) => (state.Inventory[l.Id] || 0) > 0);
    headerChip(chips, 'album', Theme.Ink, `${owned.length}/${List.length}`);
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
    chip(auto.face, { name: 'On', color: 'Coral', text: 'ON', height: 22, textSize: 15, anchor: [0.5, 0.5], pos: [1, -8, 0, 2], rot: 12, z: 6, visible: state.Settings.AutoFeature });

    const inPark = new Set(park(state));
    const canvas = gridHeight(owned.length, COLS, CELL[1], GAP) + PAD_Y * 2;
    const content = scroller(body, VIEWS.Collection.Top, canvas, scrollY, bodyHeight);
    gridLayout(content, CELL[0], CELL[1], GAP, COLS, 'center', WINDOW_SIZE[0] - 36 - PAD_X - PAD_RIGHT);
    for (const landmark of owned) {
      collectionCard(content, landmark, state.Inventory[landmark.Id], state.Featured === landmark.Id, inPark.has(landmark.Id));
    }
  }

  const PASSPORT = { CELL: [104, 124], GAP: 8, COLS: 6, HEADER: 98, SECTION_PAD: 14, SECTION_GAP: 16 };
  function passportCanvasHeight() {
    let total = 0;
    Regions.forEach((region, i) => {
      const n = ByRegion[region.Id].length;
      total += PASSPORT.HEADER + gridHeight(n, PASSPORT.COLS, PASSPORT.CELL[1], PASSPORT.GAP) + PASSPORT.SECTION_PAD;
      if (i > 0) total += PASSPORT.SECTION_GAP;
    });
    return total + PAD_Y * 2;
  }

  function passportCard(parent, landmark, known) {
    const tier = landmark.Tier;
    const card = gui(parent, { name: landmark.Id, flow: true, size: [0, PASSPORT.CELL[0], 0, PASSPORT.CELL[1]], bg: known ? Theme.Cream : Theme.Ink, corner: 10, stroke: [Theme.Ink, 2.5] });
    if (known) {
      photo(card, landmark, [0, 5, 0, 5], [1, -10, 0, 68], 7, 64);
      label(card, { pos: [0, 4, 0, 77], size: [1, -8, 0, 20], text: landmark.Name }, 16);
      label(card, { pos: [0, 4, 0, 99], size: [1, -8, 0, 17], text: oneIn(landmark.OneIn), color: lerp(tier.Color, Theme.Ink, 0.45) }, 14);
    } else {
      // 그림이 있으면 자물쇠 그림, 없으면 "?" (Panels.passportCard)
      iconView(card, 'lock', { anchor: [0.5, 0], pos: [0.5, 0, 0, 14], size: [0, 56, 0, 56], transparency: 0.15 });
      label(card, { pos: [0, 4, 0, 90], size: [1, -8, 0, 20], text: oneIn(landmark.OneIn), color: tier.Color }, 16);
    }
  }

  function buildPassportSections(content, state) {
    list(content, 'v', PASSPORT.SECTION_GAP, 'left', 'top');
    for (const region of Regions) {
      const landmarks = ByRegion[region.Id];
      const height = PASSPORT.HEADER + gridHeight(landmarks.length, PASSPORT.COLS, PASSPORT.CELL[1], PASSPORT.GAP) + PASSPORT.SECTION_PAD;
      const section = gui(content, { name: region.Id, flow: true, size: [1, 0, 0, height], bg: Theme.Paper, corner: 14, stroke: [Theme.Ink, 3] });
      const [found, required] = regionProgress(state, region.Id);
      const complete = required > 0 && found >= required;
      label(
        section,
        {
          pos: [0, PASSPORT.SECTION_PAD, 0, 8],
          size: [0.6, 0, 0, 34],
          xAlign: 'left',
          rich: `${region.Name}  <font color="${hex(lerp(region.Color, Theme.Ink, 0.3))}">${found}/${required}</font>`,
        },
        28
      );
      const track = gui(section, { pos: [0, PASSPORT.SECTION_PAD, 0, 46], size: [0.5, 0, 0, 14], bg: Theme.Cream, corner: 'round', stroke: [Theme.Ink, 2] });
      gui(track, { size: [required > 0 ? found / required : 0, 0, 1, 0], bg: region.Color, corner: 'round' });
      chip(section, {
        name: 'Bonus',
        color: complete ? COLORS.Grass.Face : DIM_CHIP,
        icon: 'clover',
        iconSize: 32,
        text: `+${REGION_BONUS}%`,
        height: 26,
        textSize: 16,
        pos: [0, PASSPORT.SECTION_PAD + 2, 0, 66],
        iconTransparency: complete ? 0 : 0.45,
      });
      // 도장 그림: 다 모으면 진하게, 아니면 회색으로 물들이고 흐리게
      const stamp = gui(section, { name: 'Stamp', anchor: [1, 0], pos: [1, -18, 0, 6], size: [0, 88, 0, 88], rot: -12, z: 2 });
      iconView(stamp, 'stamp_' + region.Id.toLowerCase(), {
        anchor: [0.5, 0.5],
        pos: [0.5, 0, 0.5, 0],
        size: [1.12, 0, 1.12, 0],
        z: 2,
        color: complete ? null : [150, 146, 160],
        transparency: complete ? 0 : 0.75,
      });
      const grid = gui(section, {
        pos: [0, PASSPORT.SECTION_PAD, 0, PASSPORT.HEADER],
        size: [1, -PASSPORT.SECTION_PAD * 2, 1, -(PASSPORT.HEADER + PASSPORT.SECTION_PAD)],
      });
      gridLayout(grid, PASSPORT.CELL[0], PASSPORT.CELL[1], PASSPORT.GAP, PASSPORT.COLS, 'left', WINDOW_SIZE[0] - 36 - PAD_X - PAD_RIGHT - PASSPORT.SECTION_PAD * 2);
      landmarks.forEach((landmark) => passportCard(grid, landmark, (state.Inventory[landmark.Id] || 0) > 0));
    }
  }

  function buildPassport(body, bodyHeight, state, scrollY) {
    const header = gui(body, { name: 'PassportHeader', size: [1, 0, 0, HEADER_HEIGHT] });
    const chips = chipRow(header);
    const stamps = completedRegions(state).length;
    headerChip(chips, 'passport', Theme.Ink, `${stamps}/${Regions.length}`);
    headerChip(chips, 'clover', stamps > 0 ? COLORS.Grass.Face : DIM_CHIP, `+${stamps * REGION_BONUS}%`, stamps > 0 ? 0 : 0.45);
    const content = scroller(body, VIEWS.Passport.Top, passportCanvasHeight(), scrollY, bodyHeight);
    buildPassportSections(content, state);
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
        icon: 'arrow_up',
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

  function buildPanel(screenGui, name, state, opts = {}) {
    const view = VIEWS[name];
    const height = opts.windowHeight || WINDOW_SIZE[1];
    const win = uiWindow(screenGui, {
      name: 'Window',
      anchor: opts.anchor || [0.5, 0.5],
      pos: opts.pos || [0.5, 0, 0.5, OPEN_OFFSET],
      size: [0, WINDOW_SIZE[0], 0, height],
      color: view.Color,
      title: view.Title,
      ribbonWidth: 220,
      z: 5,
      uiScale: UI_SCALE,
    });
    const top = RIBBON_HEIGHT / 2 + 4 + 14;
    const bodyHeight = height - (top + 16);
    if (name === 'Collection') buildCollection(win.body, bodyHeight, state, opts.scrollY || 0);
    else if (name === 'Passport') buildPassport(win.body, bodyHeight, state, opts.scrollY || 0);
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
    return `<svg class="world" viewBox="0 0 1280 720" xmlns="${SVG_NS}" aria-hidden="true">
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

  function newScreen(parent, id, opts = {}) {
    const screen = document.createElement('div');
    screen.className = 'screen';
    screen.id = id;
    if (opts.height) screen.style.height = opts.height + 'px';
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
    if (opts.topbar === false) {
      screenGui.style.top = '0';
      screenGui.style.height = (opts.height || 720) + 'px';
    }
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
  // 처음 발견 = NEW + 발견 보너스(★UP 없음), 이미 가진 명소를 또 찾아 별이 오르면 = ★N UP 만(보너스 없음).
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

  // 2번: 타지마할을 처음 발견 / 2-2번: 에펠탑을 또 찾아 별이 오름 (9번째 -> 10번째 = ★3)
  const NEW_FIND = 'tajmahal';
  const STAR_FIND = 'eiffel';
  const STATE_BEFORE_NEW = stateWithout(STATE, NEW_FIND);
  const REVEAL_NEW = { ...rollResult(STATE_BEFORE_NEW, NEW_FIND), burstRotation: 8 };
  const REVEAL_STAR = { ...rollResult(STATE, STAR_FIND), burstRotation: 20 };

  // 속보는 서버가 OneIn >= ANNOUNCE_ONE_IN 일 때만 보냄 -> 그 조건을 만족하는 명소로
  const NEWS_LANDMARK = ['pyramid', ...List.map((l) => l.Id)]
    .map((id) => ById[id])
    .find((l) => l && l.OneIn >= Config.ANNOUNCE_ONE_IN);
  const NEWS = [{ Name: 'YLTH', LandmarkId: NEWS_LANDMARK.Id, Rolls: 57 }];

  // 여권 창: 아프리카(도장 완성) 칸이 보이도록 스크롤한 위치
  function passportScrollTo(regionId) {
    let y = PAD_Y;
    for (const region of Regions) {
      if (region.Id === regionId) return Math.max(0, y - 8);
      y += PASSPORT.HEADER + gridHeight(ByRegion[region.Id].length, PASSPORT.COLS, PASSPORT.CELL[1], PASSPORT.GAP) + PASSPORT.SECTION_PAD + PASSPORT.SECTION_GAP;
    }
    return 0;
  }

  // --- 화면 목록 -------------------------------------------------------------------
  // 받침에 맞는 조사: 을/를
  const eul = (word) => {
    const code = word.charCodeAt(word.length - 1) - 0xac00;
    return word + (code >= 0 && code < 11172 && code % 28 !== 0 ? '을' : '를');
  };
  const newFind = ById[NEW_FIND];
  const starFind = ById[STAR_FIND];
  const newsLandmark = ById[NEWS[0].LandmarkId];
  const completeRegion = completedRegions(STATE)[0];
  const SHOTS = [
    {
      id: 'screen1',
      title: '기본 화면',
      note:
        `왼쪽 위: 코인 알약 + 초당 수입 칩, 아래 주사위(굴림 수) · 클로버(행운) 칩. 왼쪽: 도감/여권/강화/공원 버튼(여권 배지 = 도장 받은 대륙 수 / ${Regions.length}). ` +
        `아래 가운데: 굴리기(R) + 자동(T, 꺼짐 = 회색). 위 가운데: 다른 사람이 ${eul(newsLandmark.Name)} 찾았을 때 뜨는 서버 전체 속보 띠 ` +
        `(속보는 1 in ${commas(Config.ANNOUNCE_ONE_IN)} 이상만, 7초 뒤 사라짐).`,
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false, location: 'Plaza' });
        buildNews(screenGui, NEWS);
      },
    },
    {
      id: 'screen2',
      title: '명소 공개 — 처음 발견',
      note:
        `${eul(newFind.Name)} 처음 찾은 순간: 뒤에 등급 색 햇살(sunburst), 대륙 딱지(${RegionById[newFind.Region].Name}), 등급 리본(${newFind.Tier.Name}), LuckiestGuy 이름 + 확률, ` +
        `아래 딱지 줄 = NEW + 발견 보너스 코인 +${commas(REVEAL_NEW.Bonus)}(실제 계산값). 처음 발견에는 ★UP 딱지가 안 붙습니다. ` +
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
        `이미 가진 ${eul(starFind.Name)} ${commas(STATE.Inventory[STAR_FIND] + 1)}번째로 찾아 별이 ${REVEAL_STAR.Stars}개가 된 순간: 딱지 줄에는 보라 "★${REVEAL_STAR.Stars} UP" 하나만(보너스 코인 없음). ` +
        '별이 오르지 않는 평범한 재발견이면 딱지 줄 자체가 안 나옵니다.',
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false });
        buildReveal(screenGui, starFind, REVEAL_STAR);
      },
    },
    {
      id: 'screen3',
      title: '도감',
      note:
        '가진 명소를 희귀한 순서로(위 띠 = 등급 색 + 확률). 왼쪽 위 빨간 "대표" 도장, 사진 왼쪽 아래 초록 칩 = 공원에 전시 중, 오른쪽 위 ×N = 발견 횟수, 아래 별(★1~5). ' +
        '머리 줄: 발견 수 / 전체, 오른쪽 "자동"(더 희귀한 명소를 찾으면 자동으로 대표 지정, 켜짐 = 초록 + ON).',
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false });
        buildPanel(screenGui, 'Collection', STATE);
      },
    },
    {
      id: 'screen4',
      title: '여권',
      note:
        `대륙 ${Regions.length}개(${Regions.map((r) => r.Name).join(' · ')})가 한 쪽씩. 창을 ${RegionById[completeRegion]?.Name || ''} 쪽까지 스크롤한 모습(처음 열면 ${Regions[0].Name}부터). ` +
        `다 모은 대륙은 도장이 진하게 찍히고 +${REGION_BONUS}% 칩이 초록, 나머지는 흐린 도장 + 회색 칩. ` +
        `도장 조건은 ${Tiers[Config.STAMP_MAX_RANK - 1].Name}(${Config.STAMP_MAX_RANK}등급)까지만 셈 — 그보다 희귀한 카드는 보이지만 "찾은 수/필요 수"에서 빠짐. 못 찾은 칸은 어두운 카드 + 자물쇠. ` +
        `${ById.earth ? ById.earth.Name + '는 대륙 밖 특별 명소라 여권에 없음.' : ''}`,
      build(root) {
        const screenGui = newScreen(root, this.id);
        buildHud(screenGui, STATE, { auto: false });
        buildPanel(screenGui, 'Passport', STATE, { scrollY: passportScrollTo(completeRegion || Regions[0].Id) });
      },
    },
    {
      id: 'screen4b',
      title: '여권 — 스크롤 내용 전체',
      extra: '4-2',
      note: '위 여권 창 안에서 스크롤되는 내용 전체를 한 번에 펼친 참고용 그림(게임 화면이 아님). 크기·배율은 창과 같음.',
      build(root) {
        const canvas = passportCanvasHeight();
        const top = RIBBON_HEIGHT / 2 + 4 + 14;
        const windowHeight = top + HEADER_HEIGHT + canvas + 16;
        const screenHeight = Math.ceil(windowHeight * UI_SCALE + 70);
        const screenGui = newScreen(root, this.id, { height: screenHeight, world: false, topbar: false, background: '#7fa9c2' });
        buildPanel(screenGui, 'Passport', STATE, { anchor: [0.5, 0], pos: [0.5, 0, 0, 40], windowHeight, scrollY: 0 });
      },
    },
    {
      id: 'screen5',
      title: '강화',
      note:
        '업그레이드 4줄: 아이콘 · 이름 + Lv · 지금 값 · 한 번 살 때 바뀌는 양 · 가격 버튼. 살 수 있음 = 노랑, 코인 부족 = 회색, 최대 레벨 = 보라 MAX. ' +
        '<b>참고:</b> 여행사(비행기)·입장료(표) 아이콘은 그림 파일이 없어서 게임에서는 3D 미니 모형으로 나옴 — 여기선 비슷한 모양으로 대신 그림.',
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
      const scale = SHOT_MODE ? 1 : Math.min(1, wrap.clientWidth / 1280);
      screen.style.transform = scale < 1 ? `scale(${scale})` : '';
      wrap.style.height = screen.offsetHeight * scale + 'px';
    });
  }

  // --- 미리보기에서 드러난 점 (게임 코드 그대로 그렸을 때 생기는 문제) ---------------------------
  const rectIn = (el, screen) => {
    const r = el.getBoundingClientRect();
    const s = screen.getBoundingClientRect();
    const k = s.width / 1280;
    return { left: (r.left - s.left) / k, right: (r.right - s.left) / k, top: (r.top - s.top) / k, bottom: (r.bottom - s.top) / k };
  };
  async function ribbonBand() {
    // ribbon.png 가운데 세로줄에서 띠(Ink 테두리 포함)의 위/아래 끝
    const image = await loadImage('ribbon');
    if (!image) return null;
    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(image, 0, 0);
    const x = Math.floor(image.naturalWidth / 2);
    const column = ctx.getImageData(x, 0, 1, image.naturalHeight).data;
    let top = -1;
    let bottom = -1;
    for (let y = 0; y < image.naturalHeight; y++) {
      if (column[y * 4 + 3] > 200) {
        if (top < 0) top = y;
        bottom = y;
      }
    }
    return top < 0 ? null : { top, bottom: bottom + 1, size: image.naturalHeight };
  }
  // 9-slice 세로 위치: 그림 속 y -> 화면 y (모서리 = 64 x scale, 가운데는 늘임)
  function sliceMapY(y, height, scale, size) {
    const m = (size * SLICE_MARGIN) / 256;
    const c = SLICE_MARGIN * scale;
    if (y <= m) return (y / m) * c;
    if (y >= size - m) return height - ((size - y) / m) * c;
    return c + ((y - m) / (size - 2 * m)) * (height - 2 * c);
  }

  async function findings() {
    const items = [];
    // 1) 속보 띠 vs 초당 수입 칩
    const s1 = document.getElementById('screen1');
    const income = s1 && s1.querySelector('[data-name="Income"]');
    const newsItem = s1 && s1.querySelector('[data-name="NewsItem"]');
    if (income && newsItem) {
      const a = rectIn(income, s1);
      const b = rectIn(newsItem, s1);
      const dx = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const dy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (dx > 0 && dy > 0) {
        items.push(
          `<b>속보 띠가 초당 수입 칩을 가림</b> (1번 화면): 1280×720 에서 속보 띠 왼쪽 끝이 수입 칩과 가로 약 ${Math.round(dx)}px 겹칩니다. ` +
            `속보 띠는 화면 가운데 기준 폭 720(×0.9), 스탯 묶음은 왼쪽 위 폭 420(×0.9)이라 화면 가로가 좁으면(1280px, 4:3 태블릿 등) 부딪힘. 1920×1080 에서는 안 겹침.`
        );
      }
    }
    // 2) 리본 제목: 띠보다 글자가 크고 아래로 처짐
    const band = await ribbonBand();
    if (band) {
      const cases = [
        { what: '창 제목 리본(Ui.window)', height: RIBBON_HEIGHT, radius: 14, labelTop: 5, labelBottom: RIBBON_HEIGHT - 5, sel: '#screen3 [data-name="Title"]' },
        { what: '명소 공개 등급 리본(Hud)', height: 44, radius: 12, labelTop: 4, labelBottom: 40, sel: '#screen2 [data-name="TierRibbon"] .lbl' },
      ];
      const parts = [];
      for (const c of cases) {
        const scale = sliceScale(c.radius, c.height);
        const top = sliceMapY(band.top, c.height, scale, band.size);
        const bottom = sliceMapY(band.bottom, c.height, scale, band.size);
        const labelEl = document.querySelector(c.sel);
        const span = labelEl && labelEl.querySelector(':scope > span');
        const fontSize = span ? parseFloat(span.style.fontSize) : NaN;
        const drop = (c.labelTop + c.labelBottom) / 2 - (top + bottom) / 2;
        if (fontSize > (bottom - top) * 0.9 || Math.abs(drop) > 3) {
          parts.push(
            `${c.what}: 틀 높이 ${c.height}px 중 그려지는 띠는 약 ${Math.round(bottom - top)}px(SliceScale ${scale.toFixed(2)}), 글자는 ${Math.round(fontSize)}px, 글자 중심이 띠 중심보다 ${Math.round(drop)}px 아래`
          );
        }
      }
      if (parts.length) {
        items.push(
          `<b>리본 제목 글자가 리본 띠보다 크고 아래로 처짐</b>: ${parts.join(' / ')}. ` +
            `ribbon.png 는 띠가 그림 위쪽(y ${band.top}~${band.bottom} / ${band.size})에만 있어서, 모서리 반지름으로 SliceScale 을 정하면 띠가 얇아짐 ` +
            `(art/README 권장: SliceScale = 높이/256, 글자 상자도 띠 위치에 맞춰 올리기).`
        );
      }
    }
    // 3) 알약 두 번 물들이기
    items.push(
      '<b>알약(코인 알약·보너스 알약)이 거의 검정</b>: pill.png 는 이미 Ink 색인데 Ui.box 가 ImageColor3 = Ink 를 한 번 더 곱해서 ' +
        '반투명 거의-검정이 되고 위쪽 광택 줄이 사라짐(art/README: pill 은 물들이지 않음). 미리보기도 코드대로 곱해서 그렸습니다.'
    );
    // 4) 닫기 버튼: Round 인데 스킨 모서리가 높이 제한에 걸려 둥근 네모 + close.png(완성된 빨간 버튼)를 또 얹음
    const closeFace = 58 - SHADOW_DEPTH;
    const closeRadius = SKIN_RADIUS * sliceScale(closeFace / 2, closeFace);
    items.push(
      `<b>창 닫기 버튼이 동그랗지 않고 빨간 원이 두 겹</b>: Round 버튼(앞면 ${closeFace}px)인데 Ui.sliceScale 이 모서리 조각을 높이의 절반(64px 조각 기준)으로 묶어서 ` +
        `그림 속 둥근 모서리(약 ${SKIN_RADIUS}px)가 화면에서 약 ${closeRadius.toFixed(0)}px 로만 둥글어짐 → 둥근 네모. ` +
        '그 위에 close.png(이미 빨간 동그라미 + X 인 완성 버튼 그림, art/README: ImageButton 으로 바로 쓰는 그림)를 34px 로 또 얹어서 빨간 원 안에 빨간 원이 보임.'
    );
    // 5) 종이 결 늘어남
    const stretch = (WINDOW_SIZE[0] - 2 * SLICE_MARGIN * sliceScale(18)) / 128;
    items.push(
      `<b>(작은 것)</b> 창 종이(panel_paper) 가운데 조각이 가로 약 ${stretch.toFixed(1)}배로 늘어나 종이 점무늬가 가로로 긴 얼룩처럼 보임(9-slice 가운데는 늘이기만 됨).`
    );
    items.push(
      '<b>(작은 것)</b> 색 딱지(Ui.chip, tag.png)는 DESIGN 의 "캡슐"이 아니라 끝이 덜 둥근 네모로 나옴: tag.png 의 모서리 반지름은 약 44px 인데 ' +
        `코드는 모든 스킨을 ${SKIN_RADIUS}px 로 보고 높이 제한까지 걸려서, 높이 30px 딱지의 끝 반지름이 약 10px(반원이면 15px).`
    );
    const section = document.getElementById('findings');
    if (section) {
      section.innerHTML =
        '<h2>미리보기에서 드러난 점 <span class="sub">(게임 코드 그대로 그렸을 때)</span></h2><ol>' +
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
    let found = [];
    try {
      found = await findings();
    } catch (e) {
      console.warn('findings', e);
    }
    window.addEventListener('resize', fitFrames);
    window.__MOCKUP = { STATE, SHOTS: SHOTS.map((s) => s.id), fonts: window.FONTS_EMBEDDED, findings: found };
    window.__MOCKUP_READY = true;
  }

  main();
})();
