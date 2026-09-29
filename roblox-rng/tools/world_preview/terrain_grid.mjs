// 지형 덤프(dump.terrain) 읽기: 격자 두 벌(coarse 32 스터드 + 자세한 타일 4 스터드)을 한 곳에서 묻게 해 줌.
// scene.js(브라우저)와 overlap.js(노드)가 같이 씁니다. 덤프 형식은 tools/roblox_mock.luau 의 Mock.terrainDumpJson 주석 참고.
//   기둥 값은 1/8 스터드 정수(없으면 null) → 여기서 스터드 실수(없으면 NaN)로 바꿈
//   표본 위치 = 기둥 가운데(4·vx + 2). 타일 (cx, cz) 는 x ∈ [32·cx + 2, 32·cx + 34] 를 덮음(끝 표본은 이웃 청크의 첫 기둥)

function decode(list) {
  const out = new Float32Array(list.length);
  for (let i = 0; i < list.length; i++) out[i] = list[i] === null ? NaN : list[i] / 8;
  return out;
}

function makeGrid(raw) {
  return {
    xs: raw.xs,
    zs: raw.zs,
    nx: raw.xs.length,
    nz: raw.zs.length,
    h: decode(raw.h),
    w: decode(raw.w),
    b: decode(raw.b),
    m: Int16Array.from(raw.m),
  };
}

// 정렬된 표본 좌표 목록에서 x 가 들어가는 칸 i (xs[i] <= x < xs[i+1]) 와 칸 안 비율
function locate(xs, x) {
  const n = xs.length;
  if (n < 2) return null;
  if (x < xs[0] || x > xs[n - 1]) return null;
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  const span = xs[lo + 1] - xs[lo];
  return { i: lo, t: span > 0 ? (x - xs[lo]) / span : 0 };
}

export function makeTerrainGrid(t) {
  if (!t) return null;
  const coarse = makeGrid(t.coarse);
  coarse.cx0 = t.coarse.cx0;
  coarse.cz0 = t.coarse.cz0;
  const tiles = new Map();
  for (const raw of t.tiles) {
    const g = makeGrid(raw);
    g.cx = raw.cx;
    g.cz = raw.cz;
    tiles.set(`${raw.cx},${raw.cz}`, g);
  }
  const materials = t.materials;

  // (x, z) 를 덮는 격자와 칸 위치
  function cellAt(x, z) {
    const cx = Math.floor((x - 2) / 32);
    const cz = Math.floor((z - 2) / 32);
    const tile = tiles.get(`${cx},${cz}`);
    if (tile) {
      const a = locate(tile.xs, x);
      const b = locate(tile.zs, z);
      if (a && b) return { g: tile, a, b };
    }
    const a = locate(coarse.xs, x);
    const b = locate(coarse.zs, z);
    if (a && b) return { g: coarse, a, b };
    return null;
  }

  // 쌍선형 보간. 네 모서리 중 없는 값(NaN)이 있으면 가장 가까운 있는 값, 다 없으면 NaN
  function bilinear(field, x, z) {
    const c = cellAt(x, z);
    if (!c) return NaN;
    const { g, a, b } = c;
    const i0 = b.i * g.nx + a.i;
    const v00 = g[field][i0];
    const v10 = g[field][i0 + 1];
    const v01 = g[field][i0 + g.nx];
    const v11 = g[field][i0 + g.nx + 1];
    if (!Number.isNaN(v00) && !Number.isNaN(v10) && !Number.isNaN(v01) && !Number.isNaN(v11)) {
      return (v00 * (1 - a.t) + v10 * a.t) * (1 - b.t) + (v01 * (1 - a.t) + v11 * a.t) * b.t;
    }
    const corners = [
      [v00, a.t * a.t + b.t * b.t],
      [v10, (1 - a.t) ** 2 + b.t * b.t],
      [v01, a.t * a.t + (1 - b.t) ** 2],
      [v11, (1 - a.t) ** 2 + (1 - b.t) ** 2],
    ].filter((p) => !Number.isNaN(p[0]));
    if (corners.length === 0) return NaN;
    corners.sort((p, q) => p[1] - q[1]);
    return corners[0][0];
  }

  // 가장 가까운 표본의 재질 이름(없으면 null)
  function materialAt(x, z) {
    const c = cellAt(x, z);
    if (!c) return null;
    const { g, a, b } = c;
    const i = (b.i + (b.t > 0.5 ? 1 : 0)) * g.nx + a.i + (a.t > 0.5 ? 1 : 0);
    if (Number.isNaN(g.h[i])) return null;
    return materials[g.m[i]];
  }

  // (x, z) 둘레 네 표본 중 재질 name 의 무게(쌍선형)
  function materialWeight(x, z, name) {
    const c = cellAt(x, z);
    if (!c) return 0;
    const { g, a, b } = c;
    const i0 = b.i * g.nx + a.i;
    const is = (i) => (!Number.isNaN(g.h[i]) && materials[g.m[i]] === name ? 1 : 0);
    return (is(i0) * (1 - a.t) + is(i0 + 1) * a.t) * (1 - b.t) + (is(i0 + g.nx) * (1 - a.t) + is(i0 + g.nx + 1) * a.t) * b.t;
  }

  // 모든 표본 돌기(격자, 번호, x, z) — 타일에 덮인 coarse 표본도 포함
  function forEachSample(fn) {
    for (const g of [coarse, ...tiles.values()]) {
      for (let j = 0; j < g.nz; j++) for (let i = 0; i < g.nx; i++) fn(g, j * g.nx + i, g.xs[i], g.zs[j]);
    }
  }

  const bounds = t.bounds; // [minX, minY, minZ, maxX, maxY, maxZ] 스터드
  return {
    raw: t,
    coarse,
    tiles,
    materials,
    bounds,
    // 땅 윗면 높이(NaN = 지형 없음)
    heightAt: (x, z) => bilinear("h", x, z),
    // 물 윗면(NaN = 물 없음)
    waterAt: (x, z) => bilinear("w", x, z),
    materialAt,
    materialWeight,
    forEachSample,
    hasTile: (cx, cz) => tiles.has(`${cx},${cz}`),
  };
}
