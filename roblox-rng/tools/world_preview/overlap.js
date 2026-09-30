// 맵 미리보기: 풍경(Scenery) 파트가 게임 공간을 막는지 검사하는 겹침 보고서(텍스트).
// 사용법(roblox-rng 폴더에서, 보통은 preview.sh 가 부름): node tools/world_preview/overlap.js <dump.json> <보고서.txt>
//
// 검사 대상: 덤프에서 출처(o)가 "Scenery" 인 파트(Scenery 가 만든 모든 파트 + 지형 채우기).
// 발자국(XZ): 파트 모양의 바닥 투영. 상자·쐐기는 8 꼭짓점을 XZ 로 내린 볼록 껍질(Y 축으로만 돈 상자면 정확한 OBB),
//   Ball 과 세운 Cylinder 는 원. 구역과의 교차는 볼록 다각형/원 분리축 검사(SAT)라서 돌아간 사각형도 정확함.
// 구역
//   부지    : Parks/PlotN/Border (부지 바닥 + 둘레 띠)
//   간판    : 부지 입구(둘레 띠 앞 가장자리)에서 광장 쪽으로 깊이 8, 폭 30 (부지 좌표 x ±15)
//   길      : Parks/PlotN/Path 에 사방 +2 여유
//   광장    : 원점에서 반지름 50 이내
//   스폰    : SpawnLocation 에 사방 +2 여유
//   World   : 광장 둘레 나무·가로등·지구본 등 World 파트와 3D 로 겹침(발자국 교차 + 높이 범위 교차)
// 예외(바닥류): 파트의 가장 높은 점 y <= 0.2 이고 가로/세로 중 긴 쪽 >= 16 스터드인 파트(섬 바닥, 모래사장, 물 등)는
//   아무것도 막지 않으므로 구역 검사에서 뺌. 대신 "같은 높이 면 깜빡임(z-fighting)" 검사만 함:
//   윗면이 기존 바닥면(Baseplate 0, 길 0.2, 둘레 띠 0.4, 부지 0.6, 계단 0.5, 광장 1 ...)과 0.02 이내로 같은 높이이면서 겹치면 경고.
// 파트끼리 z-fighting: 위를 보는 평평한 윗면 두 개(하나는 Scenery)가 0.02 이내 같은 높이로 겹침. 무늬 없는 재질 + 같은 색은 뺌
// 지형(Terrain)이 있으면(덤프 terrain, terrain_grid.mjs 로 높이를 읽음) 추가 검사. 지형 자체는 바닥류라 구역 검사에서 빠짐:
//   지형이 바닥면을 뚫음 : World/Parks 의 낮고 평평한 면(부지·둘레 띠·길·광장 ...; 바닥류 제외) 안쪽 4 스터드 간격 점에서
//                         지형 윗면이 그 면보다 0.05 넘게 높으면(잔디가 부지 위로 솟음)
//   지형과 z-fighting    : 위를 보는 평평한 파트 윗면(모든 출처)이 지형 윗면과 0.03 이내로 같은 높이인 점이 발자국의 25% 이상
//   떠 있음(Scenery)     : 서로 닿은 Scenery 파트 덩어리(경계 상자 0.15 이내) 중 땅에 닿은 파트(바닥이 발자국 밑 지형
//                         최고점 + 1 이하)도, 물 위 파트도, 다른 출처 파트(부지·길 ...)에 닿은 파트도 없는 덩어리
//                         → 나무·바위·벤치가 통째로 공중에(나뭇잎·차양처럼 기둥에 붙은 파트는 기둥과 한 덩어리라 안 나옴)
//   묻힘(Scenery)        : 파트 윗면이 발자국 밑 지형(가장 낮은 곳)보다 아래 = 완전히 땅속(안 보임)
//                         + "많이 묻힘": 키의 70% 넘게 땅속(바위처럼 일부러 묻은 것일 수 있어 참고용)

const fs = require("fs");
const path = require("path");


const GROUND_TOP = 0.2;
const GROUND_SPAN = 16;
const SIGN_HALF = 15;
const SIGN_DEPTH = 8;
const PATH_MARGIN = 2;
const SPAWN_MARGIN = 2;
const PLAZA_RADIUS = 50;
const ZFIGHT = 0.02;

// 파트 기하 -------------------------------------------------------------------
const col = (m, i) => [m[i], m[3 + i], m[6 + i]]; // 회전 행렬 열(i = 0:X, 1:Y, 2:Z 축)

function effectiveSize(part) {
  let [x, y, z] = part.z;
  if (part.s === "Ball") x = y = z = Math.min(x, y, z);
  if (part.s === "Cylinder") y = z = Math.min(y, z);
  return [x, y, z];
}

function corners(part) {
  const [sx, sy, sz] = effectiveSize(part).map((v) => v / 2);
  const m = part.m;
  const out = [];
  for (const a of [-1, 1])
    for (const b of [-1, 1])
      for (const c of [-1, 1]) {
        const lx = a * sx, ly = b * sy, lz = c * sz;
        out.push([
          part.p[0] + m[0] * lx + m[1] * ly + m[2] * lz,
          part.p[1] + m[3] * lx + m[4] * ly + m[5] * lz,
          part.p[2] + m[6] * lx + m[7] * ly + m[8] * lz,
        ]);
      }
  return out;
}

function verticalRange(part) {
  const [sx, sy, sz] = effectiveSize(part);
  if (part.s === "Ball") return [part.p[1] - sx / 2, part.p[1] + sx / 2];
  if (part.s === "Cylinder") {
    // 축(X) 방향 반길이 * |축.y| + 반지름 * sqrt(1 - 축.y^2)
    const ay = Math.abs(part.m[3]);
    const h = (sx / 2) * ay + (sy / 2) * Math.sqrt(Math.max(0, 1 - ay * ay));
    return [part.p[1] - h, part.p[1] + h];
  }
  const ys = corners(part).map((c) => c[1]);
  return [Math.min(...ys), Math.max(...ys)];
}

function hull(points) {
  const pts = points.map((p) => [p[0], p[1]]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 1e-9) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 1e-9) upper.pop();
    upper.push(p);
  }
  upper.pop();
  lower.pop();
  return lower.concat(upper);
}

// 발자국: { kind: "circle", c: [x, z], r } 또는 { kind: "poly", pts: [[x, z], ...] }
function footprint(part) {
  const [sx, sy] = effectiveSize(part);
  if (part.s === "Ball") return { kind: "circle", c: [part.p[0], part.p[2]], r: sx / 2 };
  if (part.s === "Cylinder" && Math.abs(part.m[3]) > 0.999) {
    return { kind: "circle", c: [part.p[0], part.p[2]], r: sy / 2 };
  }
  return { kind: "poly", pts: hull(corners(part).map((c) => [c[0], c[2]])) };
}

function horizontalSpan(fp) {
  if (fp.kind === "circle") return fp.r * 2;
  const xs = fp.pts.map((p) => p[0]);
  const zs = fp.pts.map((p) => p[1]);
  return Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs));
}

// 교차 검사(볼록) -------------------------------------------------------------------
function project(pts, ax) {
  let lo = Infinity, hi = -Infinity;
  for (const p of pts) {
    const d = p[0] * ax[0] + p[1] * ax[1];
    lo = Math.min(lo, d);
    hi = Math.max(hi, d);
  }
  return [lo, hi];
}
function axesOf(pts) {
  const out = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len > 1e-9) out.push([-(b[1] - a[1]) / len, (b[0] - a[0]) / len]);
  }
  return out;
}
const EPS = 1e-3; // 딱 맞닿은 것은 겹침 아님
function polyPoly(a, b) {
  for (const ax of [...axesOf(a), ...axesOf(b)]) {
    const [a0, a1] = project(a, ax);
    const [b0, b1] = project(b, ax);
    if (a1 <= b0 + EPS || b1 <= a0 + EPS) return false;
  }
  return true;
}
function circlePoly(c, r, pts) {
  // 원 중심이 다각형 안(모든 변에 대해 같은 쪽)이거나, 변까지 거리 < r
  let pos = 0, neg = 0;
  let best = Infinity;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const ex = b[0] - a[0], ez = b[1] - a[1];
    const crossv = ex * (c[1] - a[1]) - ez * (c[0] - a[0]);
    if (crossv > 0) pos++;
    else if (crossv < 0) neg++;
    const t = Math.max(0, Math.min(1, ((c[0] - a[0]) * ex + (c[1] - a[1]) * ez) / (ex * ex + ez * ez || 1)));
    best = Math.min(best, Math.hypot(a[0] + ex * t - c[0], a[1] + ez * t - c[1]));
  }
  return pos === 0 || neg === 0 || best < r - EPS;
}
function intersects(a, b) {
  if (a.kind === "circle" && b.kind === "circle") return Math.hypot(a.c[0] - b.c[0], a.c[1] - b.c[1]) < a.r + b.r - EPS;
  if (a.kind === "circle") return circlePoly(a.c, a.r, b.pts);
  if (b.kind === "circle") return circlePoly(b.c, b.r, a.pts);
  return polyPoly(a.pts, b.pts);
}

// 파트 좌표계 안의 사각형(x0..x1, z0..z1) -> 월드 XZ 다각형
function localRect(part, x0, x1, z0, z1) {
  const r = col(part.m, 0), f = col(part.m, 2);
  return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]].map(([x, z]) => [
    part.p[0] + r[0] * x + f[0] * z,
    part.p[2] + r[2] * x + f[2] * z,
  ]);
}

// 구역 --------------------------------------------------------------------------
async function main() {
const [dumpPath, outPath] = process.argv.slice(2);
if (!dumpPath) {
  console.error("사용법: node overlap.js <dump.json> [보고서.txt]");
  process.exit(2);
}
const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));
const { makeTerrainGrid } = await import(path.join(__dirname, "terrain_grid.mjs"));
const terrain = makeTerrainGrid(dump.terrain);
const zones = [];
const flatTops = []; // 기존 바닥면: { name, y, fp }
for (const part of dump.parts) {
  const plot = part.path.match(/^Parks\/Plot(\d+)\/(Border|Path|Base)$/);
  if (plot) {
    const [, index, kind] = plot;
    const hx = part.z[0] / 2, hz = part.z[2] / 2;
    if (kind === "Border") {
      zones.push({ kind: "부지", name: `부지 ${index}(바닥+둘레 띠)`, fp: { kind: "poly", pts: localRect(part, -hx, hx, -hz, hz) } });
      zones.push({
        kind: "간판",
        name: `부지 ${index} 입구 앞 간판 자리(30x8)`,
        fp: { kind: "poly", pts: localRect(part, -SIGN_HALF, SIGN_HALF, -hz - SIGN_DEPTH, -hz) },
      });
    } else if (kind === "Path") {
      const m = PATH_MARGIN;
      zones.push({ kind: "길", name: `부지 ${index} 길(+${m})`, fp: { kind: "poly", pts: localRect(part, -hx - m, hx + m, -hz - m, hz + m) } });
    }
  }
  if (part.c === "SpawnLocation") {
    const hx = part.z[0] / 2 + SPAWN_MARGIN, hz = part.z[2] / 2 + SPAWN_MARGIN;
    zones.push({ kind: "스폰", name: `스폰(${part.path}, +${SPAWN_MARGIN})`, fp: { kind: "poly", pts: localRect(part, -hx, hx, -hz, hz) } });
  }
  if (part.o !== "Scenery" && part.o !== "Players") {
    const up = Math.abs(part.m[4]) > 0.999 || (part.s === "Cylinder" && Math.abs(part.m[3]) > 0.999);
    if (up && part.s !== "Ball" && part.s !== "Wedge" && part.s !== "CornerWedge") {
      const [, top] = verticalRange(part);
      if (top <= 2.05) flatTops.push({ name: part.path, y: top, fp: footprint(part), part });
    }
  }
}
zones.push({ kind: "광장", name: `광장(반지름 ${PLAZA_RADIUS})`, fp: { kind: "circle", c: [0, 0], r: PLAZA_RADIUS } });

const worldParts = dump.parts
  .filter((p) => p.o === "World" && p.t < 1)
  .map((p) => ({ part: p, fp: footprint(p), yr: verticalRange(p) }))
  .filter((w) => !(w.yr[1] <= GROUND_TOP + 1e-3 && horizontalSpan(w.fp) >= GROUND_SPAN));

// 검사 ------------------------------------------------------------------------------
const scenery = dump.parts.filter((p) => p.o === "Scenery");
const fmt = (v) => (Math.round(v * 10) / 10).toString();
const describe = (p) =>
  `${p.path} [${p.c}${p.s && p.c === "Part" ? "/" + p.s : ""}] 위치 (${fmt(p.p[0])}, ${fmt(p.p[1])}, ${fmt(p.p[2])}) 크기 ${p.z.map(fmt).join("x")}`;

const hits = [];
const zfights = [];
let groundCount = 0;
const byKind = {};
for (const part of scenery) {
  const fp = footprint(part);
  const yr = verticalRange(part);
  const ground = yr[1] <= GROUND_TOP + 1e-3 && horizontalSpan(fp) >= GROUND_SPAN;
  if (ground) {
    groundCount++;
    for (const t of flatTops) {
      if (Math.abs(t.y - yr[1]) < ZFIGHT && intersects(fp, t.fp)) {
        zfights.push(`${describe(part)}\n      윗면 y=${fmt(yr[1])} 이 ${t.name} 윗면(y=${fmt(t.y)})과 같은 높이`);
      }
    }
    continue;
  }
  const found = [];
  for (const z of zones) {
    if (intersects(fp, z.fp)) {
      found.push(z.name);
      byKind[z.kind] = (byKind[z.kind] || 0) + 1;
    }
  }
  for (const w of worldParts) {
    if (yr[0] < w.yr[1] - EPS && w.yr[0] < yr[1] - EPS && intersects(fp, w.fp)) {
      found.push(`World 물체 ${w.part.path}`);
      byKind.World = (byKind.World || 0) + 1;
    }
  }
  if (found.length > 0) hits.push(`${describe(part)}\n      → ${found.join(", ")}`);
}

// 파트끼리 같은 높이 윗면(z-fighting): 위를 보는 평평한 윗면 둘이 0.02 이내 같은 높이 + 발자국 겹침, 둘 중 하나는 Scenery.
// 무늬 없는 재질(SmoothPlastic/Neon/Glass/ForceField)이고 색까지 같으면 겹쳐도 티가 안 나므로 뺌.
// 무늬 있는 재질(Concrete, Grass ...)은 색이 같아도 파트마다 무늬 방향·위치가 달라서 카메라가 움직이면 번갈아 보임
const PLAIN = new Set(["SmoothPlastic", "Neon", "Glass", "ForceField"]);
const pairZfights = [];
{
  const tops = dump.parts
    .filter((p) => p.t < 0.999 && p.o !== "Players")
    .filter((p) => (Math.abs(p.m[4]) > 0.999 && p.s !== "Ball" && p.s !== "Wedge" && p.s !== "CornerWedge") || (p.s === "Cylinder" && Math.abs(p.m[3]) > 0.999))
    .map((p) => ({ p, fp: footprint(p), top: verticalRange(p)[1] }));
  const CELL = 16;
  const grid = new Map();
  tops.forEach((e, i) => {
    const pts = e.fp.kind === "circle" ? [[e.fp.c[0] - e.fp.r, e.fp.c[1] - e.fp.r], [e.fp.c[0] + e.fp.r, e.fp.c[1] + e.fp.r]] : e.fp.pts;
    const xs = pts.map((q) => q[0]);
    const zs = pts.map((q) => q[1]);
    e.box = [Math.min(...xs), Math.min(...zs), Math.max(...xs), Math.max(...zs)];
    if (e.box[2] - e.box[0] > 600 || e.box[3] - e.box[1] > 600) return; // 아주 큰 바닥은 아래에서 따로
    for (let cx = Math.floor(e.box[0] / CELL); cx <= Math.floor(e.box[2] / CELL); cx++)
      for (let cz = Math.floor(e.box[1] / CELL); cz <= Math.floor(e.box[3] / CELL); cz++) {
        const k = `${cx},${cz}`;
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k).push(i);
      }
  });
  const hugeTops = tops.map((e, i) => i).filter((i) => tops[i].box[2] - tops[i].box[0] > 600 || tops[i].box[3] - tops[i].box[1] > 600);
  const same = (a, b) =>
    a.mat === b.mat && PLAIN.has(a.mat) && a.col.every((v, k) => Math.abs(v - b.col[k]) < 0.004);
  const seenPair = new Set();
  tops.forEach((a, i) => {
    if (a.p.o !== "Scenery") return;
    const cand = new Set(hugeTops);
    for (let cx = Math.floor(a.box[0] / CELL); cx <= Math.floor(a.box[2] / CELL); cx++)
      for (let cz = Math.floor(a.box[1] / CELL); cz <= Math.floor(a.box[3] / CELL); cz++)
        for (const j of grid.get(`${cx},${cz}`) || []) cand.add(j);
    for (const j of cand) {
      if (j === i) continue;
      const b = tops[j];
      const key = i < j ? `${i}|${j}` : `${j}|${i}`;
      if (seenPair.has(key)) continue;
      seenPair.add(key);
      if (Math.abs(a.top - b.top) >= ZFIGHT - 1e-6 || same(a.p, b.p) || !intersects(a.fp, b.fp)) continue;
      // 이미 위(바닥류 검사)에서 보고한 Scenery 바닥 vs 기존 바닥은 빼고
      if (b.p.o !== "Scenery" && zfights.some((z) => z.startsWith(describe(a.p)) && z.includes(b.p.path))) continue;
      pairZfights.push(`${describe(a.p)} [${a.p.mat}]\n      ↔ ${describe(b.p)} [${b.p.mat}] 윗면 y=${a.top.toFixed(2)} / ${b.top.toFixed(2)}`);
    }
  });
}

const lines = [];
lines.push("맵 미리보기 겹침 보고서");
const meta = dump.meta || {};
lines.push(
  `풍경: ${meta.scenery ? meta.sceneryCall : "없음"}${meta.variant ? `, 변형 ${meta.variant}` : ""}${meta.variantField ? ` (Config.${meta.variantField})` : ""}`,
);
lines.push(`Scenery 파트 ${scenery.length}개 (바닥류 예외 ${groundCount}개), 검사 구역 ${zones.length}개`);
lines.push("");
lines.push("규칙: 발자국(XZ 투영 볼록 껍질, 공·세운 원기둥은 원)이 구역과 겹치면 보고.");
lines.push(`  바닥류 예외 = 가장 높은 점 y <= ${GROUND_TOP} 이고 가로/세로 중 긴 쪽 >= ${GROUND_SPAN} 스터드(섬 바닥·모래사장·물 등).`);
lines.push(`  구역: 부지(바닥+둘레 띠), 입구 앞 간판 자리 ${SIGN_HALF * 2}x${SIGN_DEPTH}, 길 +${PATH_MARGIN}, 광장 r<=${PLAZA_RADIUS}, 스폰 +${SPAWN_MARGIN}, World 파트(3D).`);
lines.push("");
const kinds = Object.entries(byKind).map(([k, n]) => `${k} ${n}`).join(", ");
lines.push(`[요약] 겹친 파트 ${hits.length}개${kinds ? ` (${kinds})` : ""}, z-fighting 위험 ${zfights.length}개, 파트끼리 같은 높이 윗면 ${pairZfights.length}쌍`);
lines.push("");
if (hits.length > 0) {
  lines.push("[겹침]");
  hits.forEach((h) => lines.push("  " + h));
  lines.push("");
}
if (zfights.length > 0) {
  lines.push("[z-fighting 위험: 같은 높이 바닥면]");
  zfights.forEach((h) => lines.push("  " + h));
  lines.push("");
}
if (pairZfights.length > 0) {
  lines.push("[파트끼리 z-fighting 위험: 겹친 두 윗면이 같은 높이(무늬 있는 재질이거나 색이 다름)]");
  pairZfights.slice(0, 80).forEach((h) => lines.push("  " + h));
  if (pairZfights.length > 80) lines.push(`  ... 외 ${pairZfights.length - 80}쌍`);
  lines.push("");
}
if (scenery.length === 0) lines.push("Scenery 파트가 없습니다(풍경 모듈이 없거나 아무것도 만들지 않음).");
let terrainSummary = "";
if (terrain) {
  const t = terrainChecks(terrain, dump.parts, scenery, flatTops, describe, fmt);
  lines.push(...t.lines);
  terrainSummary = `, 지형: 뚫음 ${t.counts.intrude} / z-fighting ${t.counts.zfight} / 떠 있음 ${t.counts.floating} / 묻힘 ${t.counts.buried}(많이 ${t.counts.mostly})`;
}
const text = lines.join("\n") + "\n";
if (outPath) fs.writeFileSync(outPath, text);
console.log(
  `[overlap] Scenery 파트 ${scenery.length}개, 겹침 ${hits.length}개${kinds ? ` (${kinds})` : ""}, z-fighting ${zfights.length}개, 파트끼리 같은 높이 ${pairZfights.length}쌍${terrainSummary}${outPath ? ` → ${outPath}` : ""}`,
);
}

// 지형 검사 ---------------------------------------------------------------------------------
function pointInFootprint(fp, x, z) {
  if (fp.kind === "circle") return Math.hypot(x - fp.c[0], z - fp.c[1]) <= fp.r;
  let pos = 0, neg = 0;
  const pts = fp.pts;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const c = (b[0] - a[0]) * (z - a[1]) - (b[1] - a[1]) * (x - a[0]);
    if (c > 1e-9) pos++;
    else if (c < -1e-9) neg++;
  }
  return pos === 0 || neg === 0;
}

function footprintBox(fp) {
  if (fp.kind === "circle") return [fp.c[0] - fp.r, fp.c[1] - fp.r, fp.c[0] + fp.r, fp.c[1] + fp.r];
  const xs = fp.pts.map((p) => p[0]);
  const zs = fp.pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...zs), Math.max(...xs), Math.max(...zs)];
}

// 발자국 안 표본 점(간격 step, 작은 발자국은 3x3 이상) + 꼭짓점(다각형) — 가장자리까지 보도록 조금 안쪽으로
function samplePoints(fp, maxStep = 4) {
  const [x0, z0, x1, z1] = footprintBox(fp);
  const step = Math.max(0.25, Math.min(maxStep, (x1 - x0) / 3, (z1 - z0) / 3));
  const out = [];
  for (let z = z0 + step / 2; z < z1; z += step) {
    for (let x = x0 + step / 2; x < x1; x += step) if (pointInFootprint(fp, x, z)) out.push([x, z]);
  }
  if (fp.kind === "circle") out.push([fp.c[0], fp.c[1]]);
  else {
    const cx = fp.pts.reduce((a, p) => a + p[0], 0) / fp.pts.length;
    const cz = fp.pts.reduce((a, p) => a + p[1], 0) / fp.pts.length;
    out.push([cx, cz]);
    for (const p of fp.pts) out.push([p[0] + (cx - p[0]) * 0.05, p[1] + (cz - p[1]) * 0.05]);
  }
  return out;
}

function terrainChecks(grid, parts, scenery, flatTops, describe, fmt) {
  const lines = [];
  const counts = { intrude: 0, zfight: 0, floating: 0, buried: 0, mostly: 0 };
  const groundLike = (p, fp, yr) => yr[1] <= GROUND_TOP + 1e-3 && horizontalSpan(fp) >= GROUND_SPAN;

  // 1) 지형이 World/Parks 바닥면을 뚫음 / 2) 지형과 같은 높이(z-fighting) — 모든 출처의 위를 보는 평평한 파트
  const intrude = [];
  const zfight = [];
  const upright = (p) => Math.abs(p.m[4]) > 0.999 || (p.s === "Cylinder" && Math.abs(p.m[3]) > 0.999);
  for (const part of parts) {
    if (part.t >= 0.999 || !upright(part) || part.s === "Ball" || part.s === "Wedge" || part.s === "CornerWedge") continue;
    const fp = footprint(part);
    const yr = verticalRange(part);
    const top = yr[1];
    const pts = samplePoints(fp);
    let same = 0, n = 0, above = 0, worst = 0, wx = 0, wz = 0;
    for (const [x, z] of pts) {
      const h = grid.heightAt(x, z);
      if (Number.isNaN(h)) continue;
      n++;
      if (Math.abs(h - top) < 0.03) same++;
      if (h > top + 0.05) {
        above++;
        if (h - top > worst) [worst, wx, wz] = [h - top, x, z];
      }
    }
    if (n === 0) continue;
    if (same >= Math.max(2, n * 0.25)) {
      zfight.push(`${describe(part)}\n      윗면 y=${top.toFixed(2)} 이 지형 윗면과 같은 높이(표본 ${same}/${n})`);
    }
    if (part.o !== "Scenery" && part.o !== "Players" && top <= 2.05 && !groundLike(part, fp, yr) && above > 0) {
      intrude.push(
        `${describe(part)}\n      지형이 윗면(y=${fmt(top)})보다 최대 ${fmt(worst)} 높음(표본 ${above}/${n}, 예: (${fmt(wx)}, ${fmt(wz)}))`,
      );
    }
  }
  counts.intrude = intrude.length;
  counts.zfight = zfight.length;

  // 3) 떠 있음 / 4) 묻힘 — Scenery 파트
  // 떠 있음은 "덩어리" 단위: 서로 닿거나 겹친 Scenery 파트(월드 축 경계 상자가 0.15 이내)끼리 한 덩어리로 묶고,
  // 덩어리 안에 땅에 닿은 파트(바닥이 발자국 밑 지형 최고점 + 1 이하), 물 위 파트, Scenery 가 아닌 파트에 닿은 파트가
  // 하나도 없으면 공중에 뜬 덩어리. 나뭇잎·차양처럼 옆으로 붙은 파트는 기둥과 한 덩어리라 안 나옴
  const TOUCH = 0.15;
  const aabb = (p) => {
    const [sx, sy, sz] = effectiveSize(p).map((v) => v / 2);
    const m = p.m;
    const ex = Math.abs(m[0]) * sx + Math.abs(m[1]) * sy + Math.abs(m[2]) * sz;
    const ey = Math.abs(m[3]) * sx + Math.abs(m[4]) * sy + Math.abs(m[5]) * sz;
    const ez = Math.abs(m[6]) * sx + Math.abs(m[7]) * sy + Math.abs(m[8]) * sz;
    return [p.p[0] - ex, p.p[1] - ey, p.p[2] - ez, p.p[0] + ex, p.p[1] + ey, p.p[2] + ez];
  };
  const touch = (a, b) =>
    a[0] <= b[3] + TOUCH && b[0] <= a[3] + TOUCH && a[1] <= b[4] + TOUCH && b[1] <= a[4] + TOUCH && a[2] <= b[5] + TOUCH && b[2] <= a[5] + TOUCH;
  const solid = parts.filter((p) => p.t < 0.999 || p.cc).map((p) => ({ p, box: aabb(p) }));
  const CELL = 16;
  const buckets = new Map();
  const bigOnes = [];
  solid.forEach((e, index) => {
    const b = e.box;
    if (b[3] - b[0] > 400 || b[5] - b[2] > 400) {
      bigOnes.push(index);
      return;
    }
    for (let cx = Math.floor(b[0] / CELL); cx <= Math.floor(b[3] / CELL); cx++)
      for (let cz = Math.floor(b[2] / CELL); cz <= Math.floor(b[5] / CELL); cz++) {
        const key = `${cx},${cz}`;
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push(index);
      }
  });
  const neighbours = (index) => {
    const b = solid[index].box;
    const out = new Set(bigOnes);
    for (let cx = Math.floor(b[0] / CELL); cx <= Math.floor(b[3] / CELL); cx++)
      for (let cz = Math.floor(b[2] / CELL); cz <= Math.floor(b[5] / CELL); cz++)
        for (const j of buckets.get(`${cx},${cz}`) || []) out.add(j);
    out.delete(index);
    return [...out].filter((j) => touch(b, solid[j].box));
  };
  // 덩어리 묶기(Scenery 파트끼리) + 땅/물/다른 출처 파트에 닿았는지
  const parent = solid.map((_, i) => i);
  const find = (i) => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  const grounded = new Map(); // 대표 번호 → true
  const info = new Map(); // Scenery 파트 번호 → { gmin, gmax, wet, n }
  solid.forEach((e, i) => {
    if (e.p.o !== "Scenery") return;
    const fp = footprint(e.p);
    const pts = samplePoints(fp, 2);
    let gmin = Infinity, gmax = -Infinity, wet = false, n = 0;
    for (const [x, z] of pts) {
      const h = grid.heightAt(x, z);
      if (Number.isNaN(h)) continue;
      n++;
      gmin = Math.min(gmin, h);
      gmax = Math.max(gmax, h);
      const w = grid.waterAt(x, z);
      if (!Number.isNaN(w) && w > h + 0.05) wet = true;
    }
    info.set(i, { gmin, gmax, wet, n, fp, yr: verticalRange(e.p) });
    for (const j of neighbours(i)) {
      if (solid[j].p.o === "Scenery") parent[find(i)] = find(j);
    }
  });
  solid.forEach((e, i) => {
    if (e.p.o !== "Scenery") return;
    const d = info.get(i);
    let ok = d.n === 0 || d.wet || d.yr[0] <= d.gmax + 1;
    if (!ok) ok = neighbours(i).some((j) => solid[j].p.o !== "Scenery");
    if (ok) grounded.set(find(i), true);
  });

  const floatingGroups = new Map();
  const buried = [];
  const mostly = [];
  solid.forEach((e, i) => {
    const part = e.p;
    if (part.o !== "Scenery" || part.t >= 0.999) return;
    const d = info.get(i);
    if (groundLike(part, d.fp, d.yr) || d.n === 0) return;
    const [y0, y1] = d.yr;
    if (y1 < d.gmin - 0.05) {
      buried.push(`${describe(part)}\n      윗면 y=${y1.toFixed(2)} < 지형 ${d.gmin.toFixed(2)}(완전히 땅속)`);
      return;
    }
    const height = y1 - y0;
    if (height > 0.2 && d.gmin - y0 > height * 0.7) {
      mostly.push(`${describe(part)}\n      키 ${fmt(height)} 중 ${fmt(d.gmin - y0)} 이상 땅속(지형 ${fmt(d.gmin)}~${fmt(d.gmax)})`);
    }
    const root = find(i);
    if (!grounded.get(root)) {
      if (!floatingGroups.has(root)) floatingGroups.set(root, []);
      floatingGroups.get(root).push({ part, gap: y0 - d.gmax, y0, gmax: d.gmax });
    }
  });
  const floating = [];
  for (const members of floatingGroups.values()) {
    members.sort((a, b) => a.y0 - b.y0);
    const low = members[0];
    floating.push(
      `${describe(low.part)}${members.length > 1 ? ` 외 ${members.length - 1}개 한 덩어리` : ""}\n      ` +
        `가장 낮은 바닥 y=${fmt(low.y0)} 이 지형(가장 높은 곳 ${fmt(low.gmax)})보다 ${fmt(low.gap)} 위, 땅·다른 파트에 안 닿음`,
    );
  }
  counts.floating = floating.length;
  counts.buried = buried.length;
  counts.mostly = mostly.length;

  lines.push("");
  lines.push("[지형 검사] (지형 윗면 = 덤프의 4 스터드 기둥 높이를 쌍선형 보간)");
  lines.push(
    `  지형이 바닥면을 뚫음 ${intrude.length}개, 지형과 z-fighting ${zfight.length}개, 떠 있는 Scenery 덩어리 ${floating.length}개, ` +
      `완전히 묻힌 Scenery 파트 ${buried.length}개, 많이 묻힘(참고) ${mostly.length}개`,
  );
  const section = (title, list, limit = 60) => {
    if (list.length === 0) return;
    lines.push("");
    lines.push(title);
    list.slice(0, limit).forEach((h) => lines.push("  " + h));
    if (list.length > limit) lines.push(`  ... 외 ${list.length - limit}개`);
  };
  section("[지형이 바닥면을 뚫음: 부지·길·광장 윗면보다 지형이 높음]", intrude);
  section("[지형과 z-fighting: 파트 윗면이 지형 윗면과 같은 높이]", zfight);
  section("[떠 있음: 땅·물·다른 파트에 안 닿은 덩어리(가장 낮은 파트)]", floating);
  section("[완전히 묻힘: 땅속이라 안 보임]", buried);
  section("[많이 묻힘(참고, 일부러 묻은 바위 등이면 괜찮음)]", mostly, 30);
  return { lines, counts };
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
