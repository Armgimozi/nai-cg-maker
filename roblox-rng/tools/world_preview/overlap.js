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

const fs = require("fs");

const [dumpPath, outPath] = process.argv.slice(2);
if (!dumpPath) {
  console.error("사용법: node overlap.js <dump.json> [보고서.txt]");
  process.exit(2);
}
const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));

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
      if (top <= 2.05) flatTops.push({ name: part.path, y: top, fp: footprint(part) });
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
lines.push(`[요약] 겹친 파트 ${hits.length}개${kinds ? ` (${kinds})` : ""}, z-fighting 위험 ${zfights.length}개`);
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
if (scenery.length === 0) lines.push("Scenery 파트가 없습니다(풍경 모듈이 없거나 아무것도 만들지 않음).");
const text = lines.join("\n") + "\n";
if (outPath) fs.writeFileSync(outPath, text);
console.log(`[overlap] Scenery 파트 ${scenery.length}개, 겹침 ${hits.length}개${kinds ? ` (${kinds})` : ""}, z-fighting ${zfights.length}개${outPath ? ` → ${outPath}` : ""}`);
