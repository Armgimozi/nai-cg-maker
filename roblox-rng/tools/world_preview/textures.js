// 맵 미리보기: Roblox 기본 재질 텍스처 흉내(절차적으로 만든 무늬, 이미지 파일·에셋 없음).
// 한 장(512x512)이 재질 한 칸(타일, 스터드 단위 크기는 PART_MATERIALS / TERRAIN_MATERIALS 에)이고,
// 모두 한 DataArrayTexture 의 층(layer)으로 넣습니다.
//   RGB = 밝기 무늬(회색에 가까움, 층마다 평균 밝기로 나눠 쓰도록 gain 을 줌) → 셰이더에서 Part.Color / 지형 재질 색에 곱함
//   A   = 높이(요철). 셰이더가 화면 미분으로 법선을 살짝 기울임(범프)
//   "noise" 층만 예외: R,G,B,A 가 서로 다른 크기의 매끈한 잡음(큰 얼룩, 물결, 섞임 경계에 씀)
// Roblox 와 똑같은 그림은 아니고, 거리·크기감(판자 폭, 벽돌 크기, 조약돌 크기)과 밝기 변화 정도를 맞춘 것.

const N = 512;

// 잡음 ------------------------------------------------------------------------------
function hash(ix, iy, seed) {
  let h = Math.imul(ix | 0, 0x27d4eb2d) ^ Math.imul(iy | 0, 0x165667b1) ^ Math.imul(seed | 0, 0x9e3779b1);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
const mod = (a, n) => ((a % n) + n) % n;
const smooth = (t) => t * t * (3 - 2 * t);
const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
const smoothstep = (a, b, x) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

// 이어지는(타일) 값 잡음: u, v ∈ [0,1), 격자 칸 수 px × py
function vnoise(u, v, px, py, seed) {
  const x = u * px;
  const y = v * py;
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = smooth(x - ix);
  const fy = smooth(y - iy);
  const x0 = mod(ix, px);
  const x1 = mod(ix + 1, px);
  const y0 = mod(iy, py);
  const y1 = mod(iy + 1, py);
  const a = hash(x0, y0, seed);
  const b = hash(x1, y0, seed);
  const c = hash(x0, y1, seed);
  const d = hash(x1, y1, seed);
  return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy;
}
function fbm(u, v, period, octaves, seed, persistence = 0.5) {
  let sum = 0;
  let amp = 1;
  let norm = 0;
  let p = period;
  for (let o = 0; o < octaves; o++) {
    sum += amp * vnoise(u, v, p, p, seed + o * 17);
    norm += amp;
    amp *= persistence;
    p *= 2;
  }
  return sum / norm;
}
// 이어지는 보로노이: cells × cells 칸, 칸마다 점 하나. f1, f2 = 가까운 두 점까지 거리(타일 = 1), id = 가장 가까운 칸
function voronoi(u, v, cells, seed, jitter = 0.85, stretchY = 1) {
  const x = u * cells;
  const y = v * cells;
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  let f1 = 9;
  let f2 = 9;
  let id = 0;
  let px = 0;
  let py = 0;
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      const cx = ix + dx;
      const cy = iy + dy;
      const wx = mod(cx, cells);
      const wy = mod(cy, cells);
      const sx = cx + 0.5 + (hash(wx, wy, seed) - 0.5) * jitter;
      const sy = cy + 0.5 + (hash(wx, wy, seed + 1) - 0.5) * jitter;
      const ddx = sx - x;
      const ddy = (sy - y) * stretchY;
      const d = Math.sqrt(ddx * ddx + ddy * ddy);
      if (d < f1) {
        f2 = f1;
        f1 = d;
        id = wy * cells + wx;
        px = ddx;
        py = ddy;
      } else if (d < f2) {
        f2 = d;
      }
    }
  }
  return { f1: f1 / cells, f2: f2 / cells, id, dx: px, dy: py };
}
const white = (i, seed) => hash(i, i * 7 + 3, seed);

// 층 생성기: (u, v, i) → [r, g, b, h]. i = 픽셀 번호(흰 잡음용) ----------------------------
const GEN = {
  flat: () => [1, 1, 1, 0.5],
  plastic: (u, v) => {
    const n = fbm(u, v, 16, 3, 11);
    return g3(1 - 0.035 * n, 0.5 + 0.2 * n);
  },
  grass: (u, v, i) => {
    const n1 = fbm(u, v, 8, 4, 21);
    const n2 = fbm(u, v, 3, 3, 23);
    const blade = vnoise(u, v, 160, 40, 25) * 0.6 + vnoise(u, v, 40, 160, 27) * 0.4;
    const speck = white(i, 29);
    const l = 0.72 + 0.26 * n1 + 0.22 * (blade - 0.5) + 0.08 * (speck - 0.5);
    const shift = (n2 - 0.5) * 0.22;
    return [l * (1 + shift), l, l * (1 - shift * 1.3), clamp01(0.3 + 0.5 * blade + 0.3 * (n1 - 0.5))];
  },
  leafygrass: (u, v, i) => {
    const base = GEN.grass(u, v, i);
    const c = voronoi(u, v, 22, 31, 0.9);
    const leaf = smoothstep(0.012, 0.004, c.f1);
    const k = 1 + 0.16 * leaf - 0.1 * smoothstep(0.004, 0.0, c.f2 - c.f1);
    return [base[0] * k, base[1] * k, base[2] * k, clamp01(base[3] * 0.6 + leaf * 0.5)];
  },
  sand: (u, v, i) => {
    const n = fbm(u, v, 6, 3, 41);
    const grain = white(i, 43);
    const ripple = Math.sin(2 * Math.PI * (v * 7 + 0.7 * fbm(u, v, 3, 2, 45)));
    const l = 0.9 + 0.1 * (n - 0.5) + 0.1 * (grain - 0.5) + 0.035 * ripple;
    return [l * 1.01, l, l * 0.98, clamp01(0.5 + 0.25 * ripple + 0.25 * (grain - 0.5))];
  },
  ground: (u, v, i) => {
    const n = fbm(u, v, 5, 5, 51);
    const p = voronoi(u, v, 18, 53, 0.9);
    const pebble = smoothstep(0.018, 0.01, p.f1) * (0.6 + 0.4 * hash(p.id, 1, 55));
    const l = 0.78 + 0.3 * (n - 0.5) + 0.14 * pebble + 0.06 * (white(i, 57) - 0.5);
    return [l * 1.03, l, l * 0.95, clamp01(0.4 + 0.3 * (n - 0.5) + 0.5 * pebble)];
  },
  mud: (u, v) => {
    const n = fbm(u, v, 4, 4, 61);
    const wet = smoothstep(0.45, 0.7, fbm(u, v, 3, 3, 63));
    const l = 0.86 + 0.2 * (n - 0.5) - 0.12 * wet;
    return g3(l, clamp01(0.5 + 0.3 * (n - 0.5) - 0.3 * wet));
  },
  rock: (u, v, i) => {
    const c = voronoi(u, v, 5, 71, 0.9);
    const tone = hash(c.id, 3, 73);
    const facet = (c.dx * 0.8 + c.dy * 0.6) * 0.35; // 칸 안에서 기울어진 면처럼 밝기 변화
    const crack = smoothstep(0.012, 0.0, c.f2 - c.f1);
    const n = fbm(u, v, 12, 4, 75);
    const l = 0.8 + 0.18 * (tone - 0.5) + facet + 0.16 * (n - 0.5) - 0.28 * crack + 0.04 * (white(i, 77) - 0.5);
    return g3(l, clamp01(0.55 + 0.4 * Math.min(1, (c.f2 - c.f1) * 12) - 0.3 + 0.3 * n));
  },
  slate: (u, v, i) => {
    const warp = fbm(u, v, 4, 3, 81);
    const layer = (v * 7 + 0.35 * warp) % 1;
    const band = Math.floor(v * 7 + 0.35 * warp);
    const tone = hash(mod(band, 7), 5, 83);
    const c = voronoi(u, v, 6, 85, 0.9, 0.35);
    const crack = smoothstep(0.008, 0.0, c.f2 - c.f1) + smoothstep(0.06, 0.0, layer) * 0.8;
    const n = fbm(u, v, 16, 3, 87);
    const l = 0.84 + 0.16 * (tone - 0.5) + 0.12 * (n - 0.5) - 0.3 * Math.min(1, crack) + 0.03 * (white(i, 89) - 0.5);
    return [l * 0.98, l, l * 1.03, clamp01(0.4 + 0.4 * layer - 0.4 * Math.min(1, crack) + 0.15 * n)];
  },
  basalt: (u, v) => {
    const c = voronoi(u, v, 7, 91, 0.6);
    const edge = smoothstep(0.01, 0.0, c.f2 - c.f1);
    const n = fbm(u, v, 16, 3, 93);
    const l = 0.88 + 0.12 * (hash(c.id, 7, 95) - 0.5) + 0.1 * (n - 0.5) - 0.4 * edge;
    return g3(l, clamp01(0.7 - 0.6 * edge + 0.1 * n));
  },
  snow: (u, v, i) => {
    const n = fbm(u, v, 8, 4, 101);
    const sparkle = white(i, 103) > 0.996 ? 0.08 : 0;
    return g3(0.95 + 0.06 * (n - 0.5) + sparkle, 0.5 + 0.3 * (n - 0.5));
  },
  ice: (u, v) => {
    const n = fbm(u, v, 5, 4, 111);
    const c = voronoi(u, v, 4, 113, 0.9);
    const crack = smoothstep(0.004, 0.0, c.f2 - c.f1);
    return g3(0.94 + 0.06 * (n - 0.5) + 0.06 * crack, 0.5 + 0.2 * n - 0.2 * crack);
  },
  salt: (u, v, i) => {
    const c = voronoi(u, v, 9, 121, 0.8);
    const edge = smoothstep(0.008, 0.0, c.f2 - c.f1);
    const n = fbm(u, v, 16, 3, 123);
    const l = 0.96 + 0.05 * (n - 0.5) - 0.18 * edge + 0.05 * (white(i, 125) - 0.5);
    return g3(l, clamp01(0.6 - 0.5 * edge + 0.1 * n));
  },
  limestone: (u, v, i) => {
    const n = fbm(u, v, 4, 5, 131);
    const pore = white(i, 133) > 0.992 ? -0.25 : 0;
    const blotch = smoothstep(0.55, 0.7, fbm(u, v, 6, 3, 135));
    const l = 0.93 + 0.1 * (n - 0.5) + pore - 0.08 * blotch;
    return g3(l, clamp01(0.5 + 0.25 * (n - 0.5) + pore));
  },
  sandstone: (u, v) => {
    const warp = fbm(u, v, 3, 3, 141);
    const s = Math.sin(2 * Math.PI * (v * 9 + 0.5 * warp));
    const n = fbm(u, v, 16, 3, 143);
    const l = 0.88 + 0.08 * s + 0.08 * (n - 0.5);
    return [l * 1.02, l, l * 0.97, clamp01(0.5 + 0.3 * s + 0.1 * n)];
  },
  // 네모 판(한 층 = 2x2 판). 이음매 + 판마다 조금 다른 밝기 + 잔 점
  pavement: (u, v, i) => {
    const su = u * 2;
    const sv = v * 2;
    const cu = Math.floor(su);
    const cv = Math.floor(sv);
    const fu = su - cu;
    const fv = sv - cv;
    const seam = Math.min(fu, 1 - fu, fv, 1 - fv);
    const groove = smoothstep(0.012, 0.004, seam);
    const tone = hash(cu, cv, 151);
    const n = fbm(u, v, 8, 4, 153);
    const speck = white(i, 155);
    const l = 0.93 + 0.08 * (tone - 0.5) + 0.08 * (n - 0.5) + 0.07 * (speck - 0.5) - 0.3 * groove;
    return g3(l, clamp01(0.75 - 0.7 * groove + 0.1 * (n - 0.5)));
  },
  cobblestone: (u, v, i) => {
    const c = voronoi(u, v, 7, 161, 0.75);
    const gap = c.f2 - c.f1;
    const mortar = smoothstep(0.016, 0.006, gap);
    const dome = smoothstep(0.0, 0.05, gap);
    const tone = hash(c.id, 9, 163);
    const n = fbm(u, v, 16, 3, 165);
    const l = (0.84 + 0.22 * (tone - 0.5) + 0.1 * (n - 0.5) + 0.05 * (white(i, 167) - 0.5)) * (1 - 0.45 * mortar);
    return g3(l, clamp01(0.15 + 0.8 * dome * (1 - mortar) + 0.05 * n));
  },
  // 벽돌: 한 층 = 8줄, 줄마다 벽돌 4장(엇갈림)
  brick: (u, v, i) => {
    const rows = 8;
    const sv = v * rows;
    const row = Math.floor(sv);
    const fv = sv - row;
    const su = u * 4 + (row % 2) * 0.5;
    const col = Math.floor(su);
    const fu = su - col;
    const mortarV = smoothstep(0.1, 0.05, Math.min(fv, 1 - fv));
    const mortarU = smoothstep(0.05, 0.025, Math.min(fu, 1 - fu));
    const mortar = Math.max(mortarV, mortarU);
    const tone = hash(mod(col, 4), row, 171);
    const n = fbm(u, v, 16, 3, 173);
    const l = (0.9 + 0.16 * (tone - 0.5) + 0.1 * (n - 0.5) + 0.05 * (white(i, 175) - 0.5)) * (1 - 0.35 * mortar);
    return g3(l, clamp01(0.85 - 0.75 * mortar + 0.08 * n));
  },
  // 판자: 한 층 = 8장(u 방향으로 긴 판), 판마다 이음매 1~2 곳, 판 사이 틈
  woodplanks: (u, v) => {
    const planks = 8;
    const sv = v * planks;
    const row = Math.floor(sv);
    const fv = sv - row;
    const offset = hash(row, 1, 181);
    const su = u * 2 + offset;
    const seg = Math.floor(su);
    const fu = su - seg;
    const gapV = smoothstep(0.06, 0.02, Math.min(fv, 1 - fv));
    const gapU = smoothstep(0.012, 0.004, Math.min(fu, 1 - fu));
    const gap = Math.max(gapV, gapU);
    const tone = hash(row, mod(seg, 2), 183);
    const grain = vnoise(u + offset, v, 6, 256, 185) * 0.6 + vnoise(u + offset, v, 24, 512, 187) * 0.4;
    const knot = smoothstep(0.02, 0.0, voronoi(u, v, 5, 189, 0.9).f1) * (hash(row, 3, 191) > 0.6 ? 1 : 0);
    const l = (0.86 + 0.18 * (tone - 0.5) + 0.14 * (grain - 0.5) - 0.12 * knot) * (1 - 0.5 * gap);
    return [l * 1.02, l, l * 0.96, clamp01(0.8 - 0.8 * gap + 0.1 * (grain - 0.5))];
  },
  wood: (u, v) => {
    const warp = fbm(u, v, 3, 3, 191);
    const rings = Math.sin(2 * Math.PI * (v * 10 + 1.4 * warp + 0.2 * Math.sin(2 * Math.PI * u)));
    const fine = vnoise(u, v, 8, 256, 193);
    const l = 0.88 + 0.08 * rings + 0.08 * (fine - 0.5);
    return [l * 1.02, l, l * 0.96, clamp01(0.5 + 0.2 * rings + 0.2 * (fine - 0.5))];
  },
  concrete: (u, v, i) => {
    const n = fbm(u, v, 8, 4, 201);
    const blotch = fbm(u, v, 3, 3, 203);
    const speck = white(i, 205);
    const dot = speck > 0.97 ? -0.12 : speck < 0.02 ? 0.06 : 0;
    const l = 0.93 + 0.07 * (n - 0.5) + 0.07 * (blotch - 0.5) + dot + 0.04 * (speck - 0.5);
    return g3(l, clamp01(0.5 + 0.2 * (n - 0.5) + dot));
  },
  asphalt: (u, v, i) => {
    const n = fbm(u, v, 6, 3, 211);
    const speck = white(i, 213);
    const l = 0.86 + 0.06 * (n - 0.5) + 0.22 * (speck - 0.5);
    return g3(l, clamp01(0.5 + 0.4 * (speck - 0.5)));
  },
  granite: (u, v, i) => {
    const a = vnoise(u, v, 96, 96, 221);
    const b = vnoise(u, v, 180, 180, 223);
    const dark = smoothstep(0.62, 0.7, a);
    const light = smoothstep(0.65, 0.75, b);
    const l = 0.9 - 0.35 * dark + 0.12 * light + 0.05 * (white(i, 225) - 0.5);
    return g3(l, clamp01(0.5 - 0.2 * dark + 0.1 * light));
  },
  marble: (u, v) => {
    const t = fbm(u, v, 3, 5, 231);
    const vein = Math.abs(Math.sin(2 * Math.PI * (u * 2 + v + 2.5 * t)));
    const thin = Math.pow(1 - vein, 10);
    const cloud = fbm(u, v, 5, 4, 233);
    const l = 0.97 - 0.3 * thin - 0.06 * (cloud - 0.5);
    return g3(l, 0.5 - 0.1 * thin);
  },
  metal: (u, v) => {
    const streak = vnoise(u, v, 4, 320, 241) * 0.6 + vnoise(u, v, 16, 640, 243) * 0.4;
    const n = fbm(u, v, 4, 3, 245);
    return g3(0.9 + 0.08 * (streak - 0.5) + 0.05 * (n - 0.5), 0.5 + 0.1 * (streak - 0.5));
  },
  diamondplate: (u, v) => {
    const k = 8;
    const su = u * k;
    const sv = v * k;
    const cu = Math.floor(su);
    const cv = Math.floor(sv);
    const fu = su - cu - 0.5;
    const fv = sv - cv - 0.5;
    // 칸마다 45도 / -45도 로 번갈아 누운 길쭉한 마름모
    const s = (cu + cv) % 2 === 0 ? 1 : -1;
    const a = (fu + s * fv) / Math.SQRT2;
    const b = (fu - s * fv) / Math.SQRT2;
    const d = Math.abs(a) / 0.34 + Math.abs(b) / 0.09;
    const bump = smoothstep(1.05, 0.8, d);
    return g3(0.86 + 0.14 * bump, 0.3 + 0.7 * bump);
  },
  corroded: (u, v, i) => {
    const t = fbm(u, v, 5, 5, 251);
    const rust = smoothstep(0.48, 0.62, t);
    const n = fbm(u, v, 20, 3, 253);
    const l = 0.82 + 0.12 * (n - 0.5) + 0.05 * (white(i, 255) - 0.5);
    return [l * (1 + 0.22 * rust), l * (1 - 0.08 * rust), l * (1 - 0.3 * rust), clamp01(0.5 + 0.3 * (n - 0.5) + 0.2 * rust)];
  },
  foil: (u, v) => {
    const c = voronoi(u, v, 12, 261, 0.95);
    const facet = 0.9 + 0.2 * (hash(c.id, 11, 263) - 0.5) + (c.dx - c.dy) * 0.25;
    return g3(facet, clamp01(0.5 + (c.dx + c.dy) * 0.4));
  },
  fabric: (u, v) => {
    const k = 24;
    const su = u * k;
    const sv = v * k;
    const iu = Math.floor(su);
    const iv = Math.floor(sv);
    const warpOnTop = (iu + iv) % 2 === 0;
    const fu = su - iu;
    const fv = sv - iv;
    const thread = warpOnTop ? Math.sin(Math.PI * fu) : Math.sin(Math.PI * fv);
    const n = fbm(u, v, 32, 2, 271);
    return g3(0.8 + 0.2 * thread + 0.05 * (n - 0.5), 0.3 + 0.6 * thread);
  },
  pebble: (u, v) => {
    const c = voronoi(u, v, 12, 281, 0.8);
    const gap = c.f2 - c.f1;
    const dark = smoothstep(0.012, 0.004, gap);
    const tone = hash(c.id, 13, 283);
    const l = (0.84 + 0.25 * (tone - 0.5)) * (1 - 0.5 * dark);
    return g3(l, clamp01(smoothstep(0.0, 0.03, gap) - 0.6 * dark));
  },
  crackedlava: (u, v) => {
    const c = voronoi(u, v, 6, 291, 0.85);
    const crack = smoothstep(0.02, 0.004, c.f2 - c.f1);
    const n = fbm(u, v, 10, 4, 293);
    const l = 0.36 + 0.14 * (n - 0.5) + 0.64 * crack;
    return g3(l, clamp01(0.7 - 0.6 * crack + 0.1 * n));
  },
  noise: (u, v) => [fbm(u, v, 4, 5, 301), fbm(u, v, 8, 5, 303), fbm(u, v, 16, 4, 305, 0.6), fbm(u, v, 5, 4, 307, 0.55)],
};
function g3(l, h) {
  return [l, l, l, h];
}

// Part.Material → 층, 한 층의 크기(스터드), 범프 세기, 거칠기, 금속성 ----------------------------
export const PART_MATERIALS = {
  SmoothPlastic: { layer: "flat", tile: 8, bump: 0, rough: 0.45 },
  Plastic: { layer: "plastic", tile: 4, bump: 0.3, rough: 0.62 },
  Wood: { layer: "wood", tile: 6, bump: 0.8, rough: 0.75 },
  WoodPlanks: { layer: "woodplanks", tile: 8, bump: 1.4, rough: 0.78 },
  Marble: { layer: "marble", tile: 12, bump: 0.2, rough: 0.3 },
  Basalt: { layer: "basalt", tile: 8, bump: 1.4, rough: 0.85 },
  Slate: { layer: "slate", tile: 8, bump: 1.5, rough: 0.85 },
  CrackedLava: { layer: "crackedlava", tile: 8, bump: 1.4, rough: 0.8 },
  Concrete: { layer: "concrete", tile: 8, bump: 0.6, rough: 0.9 },
  Limestone: { layer: "limestone", tile: 8, bump: 0.8, rough: 0.9 },
  Granite: { layer: "granite", tile: 6, bump: 0.5, rough: 0.6 },
  Pavement: { layer: "pavement", tile: 8, bump: 1.2, rough: 0.9 },
  Brick: { layer: "brick", tile: 6, bump: 1.6, rough: 0.88 },
  Pebble: { layer: "pebble", tile: 6, bump: 1.6, rough: 0.85 },
  Cobblestone: { layer: "cobblestone", tile: 6, bump: 1.8, rough: 0.85 },
  Rock: { layer: "rock", tile: 8, bump: 1.6, rough: 0.9 },
  Sandstone: { layer: "sandstone", tile: 8, bump: 0.8, rough: 0.9 },
  CorrodedMetal: { layer: "corroded", tile: 6, bump: 0.8, rough: 0.75, metal: 0.2 },
  DiamondPlate: { layer: "diamondplate", tile: 4, bump: 1.6, rough: 0.4, metal: 0.35 },
  Foil: { layer: "foil", tile: 4, bump: 1.0, rough: 0.28, metal: 0.45 },
  Metal: { layer: "metal", tile: 4, bump: 0.3, rough: 0.38, metal: 0.35 },
  Grass: { layer: "grass", tile: 6, bump: 0.9, rough: 0.95 },
  LeafyGrass: { layer: "leafygrass", tile: 6, bump: 0.9, rough: 0.95 },
  Sand: { layer: "sand", tile: 6, bump: 0.6, rough: 0.95 },
  Fabric: { layer: "fabric", tile: 3, bump: 0.8, rough: 0.95 },
  Snow: { layer: "snow", tile: 8, bump: 0.4, rough: 0.8 },
  Mud: { layer: "mud", tile: 8, bump: 0.6, rough: 0.7 },
  Ground: { layer: "ground", tile: 6, bump: 0.9, rough: 0.95 },
  Asphalt: { layer: "asphalt", tile: 6, bump: 0.5, rough: 0.92 },
  Salt: { layer: "salt", tile: 6, bump: 0.8, rough: 0.9 },
  Ice: { layer: "ice", tile: 8, bump: 0.3, rough: 0.15 },
  Glacier: { layer: "ice", tile: 8, bump: 0.3, rough: 0.2 },
  Glass: { layer: "flat", tile: 8, bump: 0, rough: 0.06 },
  ForceField: { layer: "flat", tile: 8, bump: 0, rough: 0.5 },
  Water: { layer: "flat", tile: 8, bump: 0, rough: 0.1 },
};

// 지형 재질 → 층, 크기(스터드), 범프. grassy = 가파른 비탈에서 흙빛으로(Roblox 풀 지형의 옆면처럼)
export const TERRAIN_MATERIALS = {
  Grass: { layer: "grass", tile: 12, bump: 0.8, grassy: 1 },
  LeafyGrass: { layer: "leafygrass", tile: 12, bump: 0.8, grassy: 1 },
  Sand: { layer: "sand", tile: 10, bump: 0.5 },
  Rock: { layer: "rock", tile: 20, bump: 1.5 },
  Slate: { layer: "slate", tile: 16, bump: 1.5 },
  Basalt: { layer: "basalt", tile: 12, bump: 1.4 },
  Ground: { layer: "ground", tile: 10, bump: 0.9 },
  Mud: { layer: "mud", tile: 12, bump: 0.6 },
  Snow: { layer: "snow", tile: 16, bump: 0.4 },
  Ice: { layer: "ice", tile: 16, bump: 0.3 },
  Glacier: { layer: "ice", tile: 16, bump: 0.3 },
  Salt: { layer: "salt", tile: 12, bump: 0.8 },
  Limestone: { layer: "limestone", tile: 14, bump: 0.8 },
  Sandstone: { layer: "sandstone", tile: 16, bump: 0.8 },
  Pavement: { layer: "pavement", tile: 12, bump: 1.2 },
  Cobblestone: { layer: "cobblestone", tile: 10, bump: 1.8 },
  Brick: { layer: "brick", tile: 8, bump: 1.6 },
  WoodPlanks: { layer: "woodplanks", tile: 8, bump: 1.4 },
  Asphalt: { layer: "asphalt", tile: 8, bump: 0.5 },
  Concrete: { layer: "concrete", tile: 10, bump: 0.6 },
  Granite: { layer: "granite", tile: 8, bump: 0.5 },
  CrackedLava: { layer: "crackedlava", tile: 16, bump: 1.4 },
};

// 모든 층을 만들어 DataArrayTexture 로 ------------------------------------------------------
export function buildMaterialTextures(THREE) {
  const names = Object.keys(GEN);
  const data = new Uint8Array(N * N * 4 * names.length);
  const gain = {};
  const layers = {};
  const rgb = new Float32Array(N * N * 3);
  const hgt = new Float32Array(N * N);
  names.forEach((name, layer) => {
    layers[name] = layer;
    const gen = GEN[name];
    let maxV = 0;
    let sum = 0;
    for (let y = 0; y < N; y++) {
      const v = (y + 0.5) / N;
      for (let x = 0; x < N; x++) {
        const i = y * N + x;
        const px = gen((x + 0.5) / N, v, i);
        rgb[i * 3] = px[0];
        rgb[i * 3 + 1] = px[1];
        rgb[i * 3 + 2] = px[2];
        hgt[i] = px[3];
        maxV = Math.max(maxV, px[0], px[1], px[2]);
      }
    }
    const raw = name === "noise";
    const scale = raw ? 1 : 1 / Math.max(maxV, 1e-6);
    const base = layer * N * N * 4;
    for (let i = 0; i < N * N; i++) {
      const r = clamp01(rgb[i * 3] * scale);
      const g = clamp01(rgb[i * 3 + 1] * scale);
      const b = clamp01(rgb[i * 3 + 2] * scale);
      sum += 0.2126 * r + 0.7152 * g + 0.0722 * b;
      data[base + i * 4] = Math.round(r * 255);
      data[base + i * 4 + 1] = Math.round(g * 255);
      data[base + i * 4 + 2] = Math.round(b * 255);
      data[base + i * 4 + 3] = Math.round(clamp01(hgt[i]) * 255);
    }
    gain[name] = raw ? 1 : (N * N) / Math.max(sum, 1e-6);
  });
  const texture = new THREE.DataArrayTexture(data, N, N, names.length);
  texture.format = THREE.RGBAFormat;
  texture.type = THREE.UnsignedByteType;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.anisotropy = 8;
  texture.colorSpace = THREE.NoColorSpace;
  texture.needsUpdate = true;
  return { texture, layers, gain, count: names.length };
}
