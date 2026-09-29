// 맵 미리보기 3단계(브라우저 쪽): world.luau 덤프(JSON)를 three.js 장면으로 만들고 시점별로 그림.
// render.js(Playwright)가 이 페이지를 열고 window.preview.load() → window.preview.render(view) 를 부릅니다.
//
// Roblox 규칙(맞춰 둔 것)
//   * 좌표: 오른손, Y 위. CFrame 은 행 우선 3x3 회전 m[0..8] + 위치. LookVector = -Z(세 번째 열의 반대)
//   * Block: 상자 Size. Ball: 지름 = Size 의 가장 작은 값(Roblox 는 Ball 을 균일 크기로 맞춤. 가짜 환경이 비균일 Ball 을 경고)
//   * Cylinder: 길이 축 = 로컬 X(Size.X), 지름 = min(Size.Y, Size.Z)
//   * Wedge(WedgePart 또는 Shape=Wedge): 로컬 YZ 단면 꼭짓점 (y,z) = (-h/2,-d/2), (-h/2,+d/2), (+h/2,+d/2).
//     바닥 전체 + 뒤(+Z) 면 전체, 경사면은 -Z 아래 모서리에서 +Z 위 모서리로(경사면이 -Z·위를 봄)
//   * CornerWedge(CornerWedgePart 또는 Shape=CornerWedge): 바닥 사각형 + 꼭대기 점 (+X/2, +Y/2, -Z/2) 하나인 뿔.
//     세로 삼각형 면 둘(+X 면, -Z 면) + 경사면 둘(+Z·위, -X·위를 봄).
//     근거: Roblox 엔지니어 Stravant 의 roblox-geometry 모듈(getGeometry 의 CornerWedge 꼭짓점 표)과 같은 모양.
//   * 색: Roblox Color3 는 sRGB 값 → SRGBColorSpace 로 넣어 선형 공간에서 조명, 출력도 sRGB(톤 매핑 없음)
//   * Transparency 1 은 안 그림. Neon 은 빛을 받지 않는 원래 색(조금 밝게). SmoothPlastic 은 살짝 광택
//   * 해: ClockTime·GeographicLatitude 로 계산(G3D/Roblox 식 근사: +X 에서 떠서 -X 로 짐, 정오에는 +Z 쪽으로 위도만큼 기움)
//   * 안개: Atmosphere Density/Haze 로 FogExp2 근사(1000 스터드에서 약 45% 흐려짐 @ Density 0.3)
//   * 재질 무늬: Roblox 기본 재질(WoodPlanks 판자, Brick 벽돌, Cobblestone 조약돌 ...)을 절차적 텍스처로 흉내(textures.js).
//     파트 좌표계 삼면 투영, 스터드 단위 크기로 반복, 무늬 밝기 × Part.Color (Roblox 처럼 재질 무늬를 색으로 물들임) + 살짝 요철
//   * 지형: Terrain 복셀 → 매끈한 땅 + 재질 섞임 + 물(깊이 색·반사) + 풀 장식(terrain.js)
//     물이 있으면 두 번 그림: ① 물 빼고 장면 전체를 색·깊이 텍스처로 ② 그 텍스처를 화면에 옮기고 물 표면을 그 위에
//     (물 셰이더가 물 뒤 바닥의 색·거리를 읽어서 깊이만큼 물빛·투과를 정함)
//     물 앞의 투명 파트(유리 등, 깊이를 안 씀)는 물에 덮여 보일 수 있음
// 안 그리는 것: BillboardGui(이름표), 파티클, 빛(PointLight), Decal/Texture/SurfaceAppearance, MeshPart 실제 모양(상자로 대신),
//   MaterialVariant(기본 재질만), 물 파트(Material=Water 인 Part)의 물 효과, 물속 시점, 지형 동굴·튀어나온 절벽 밑면

import * as THREE from "three";
import { buildMaterialTextures, PART_MATERIALS } from "./textures.js";
import { buildTerrain, PERTURB_GLSL, TRIPLANAR_GLSL } from "./terrain.js";
import { makeTerrainGrid } from "./terrain_grid.mjs";

const W = 1280;
const H = 720;
const canvas = document.getElementById("view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setSize(W, H, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NoToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
let dump = null;
let fogDensity = 0.00077;
const info = { parts: 0, drawn: 0, groups: 0, gui: 0 };
let textures = null; // buildMaterialTextures 결과
let grid = null; // 지형 격자(terrain_grid.mjs) 또는 null
let terrain = null; // buildTerrain 결과 또는 null
const waterScene = new THREE.Scene(); // 물 표면만(장면 텍스처를 읽음)
let sceneTarget = null; // 물 빼고 그린 장면(선형 색 + 깊이)
let composite = null; // 장면 텍스처를 화면에 옮기는 사각형
let options = {}; // render.js 가 넘김: { foam, gap }
let frame = { radius: 300 }; // 섬(땅) 반지름 — overview/top 시점 거리

function srgb(rgb) {
  return new THREE.Color().setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
}

// 기본 도형(크기 1) -------------------------------------------------------------
function convexGeometry(vertices, faces) {
  // faces: 꼭짓점 번호 목록(볼록 다각형). 바깥을 보도록 도형 중심 기준으로 방향을 맞춤
  const center = new THREE.Vector3();
  vertices.forEach((v) => center.add(v));
  center.divideScalar(vertices.length);
  const pos = [];
  for (const face of faces) {
    for (let i = 1; i + 1 < face.length; i++) {
      let a = vertices[face[0]];
      let b = vertices[face[i]];
      let c = vertices[face[i + 1]];
      const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a));
      const mid = new THREE.Vector3().add(a).add(b).add(c).divideScalar(3).sub(center);
      if (n.dot(mid) < 0) [b, c] = [c, b];
      pos.push(a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals(); // 인덱스 없는 삼각형이라 면마다 평평한 법선
  return g;
}

const v3 = (x, y, z) => new THREE.Vector3(x, y, z);
const GEOMETRY = {
  Block: new THREE.BoxGeometry(1, 1, 1),
  Ball: new THREE.SphereGeometry(0.5, 40, 24),
  // CylinderGeometry 는 Y 축 → Z 축으로 -90도 돌려 X 축 원기둥으로
  Cylinder: new THREE.CylinderGeometry(0.5, 0.5, 1, 40, 1).rotateZ(-Math.PI / 2),
  // 아주 큰 공·원기둥(섬 바닥, 바다 띠, 언덕)은 Roblox 에서 매끈하게 보이므로 면을 더 잘게
  BallHi: new THREE.SphereGeometry(0.5, 128, 64),
  CylinderHi: new THREE.CylinderGeometry(0.5, 0.5, 1, 256, 1).rotateZ(-Math.PI / 2),
  Wedge: convexGeometry(
    [
      v3(-0.5, -0.5, -0.5), // 0 바닥 앞(-Z) 왼
      v3(0.5, -0.5, -0.5), // 1 바닥 앞 오른
      v3(-0.5, -0.5, 0.5), // 2 바닥 뒤(+Z) 왼
      v3(0.5, -0.5, 0.5), // 3 바닥 뒤 오른
      v3(-0.5, 0.5, 0.5), // 4 위 뒤 왼
      v3(0.5, 0.5, 0.5), // 5 위 뒤 오른
    ],
    [
      [0, 1, 3, 2], // 바닥
      [2, 3, 5, 4], // 뒤(+Z)
      [0, 2, 4], // 왼(-X)
      [1, 3, 5], // 오른(+X)
      [0, 1, 5, 4], // 경사면
    ],
  ),
  CornerWedge: convexGeometry(
    [
      v3(0.5, 0.5, -0.5), // 0 꼭대기
      v3(0.5, -0.5, 0.5), // 1
      v3(0.5, -0.5, -0.5), // 2
      v3(-0.5, -0.5, 0.5), // 3
      v3(-0.5, -0.5, -0.5), // 4
    ],
    [
      [1, 2, 4, 3], // 바닥
      [0, 2, 1], // +X 면
      [0, 4, 2], // -Z 면
      [0, 1, 3], // 경사(+Z·위)
      [0, 3, 4], // 경사(-X·위)
    ],
  ),
};

// 재질 ----------------------------------------------------------------------------
// Neon 은 빛을 안 받는 원래 색. 나머지는 MeshStandardMaterial + 재질 무늬(층이 flat 이면 무늬 없음)
function texturePart(material, spec) {
  const layer = textures.layers[spec.layer];
  const gain = textures.gain[spec.layer];
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, {
      uTexArr: { value: textures.texture },
      uTexLayer: { value: layer },
      uTexTile: { value: spec.tile },
      uTexGain: { value: gain },
      uTexBump: { value: spec.bump },
    });
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vTexPos;\nvarying vec3 vTexNrm;")
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
vec3 texScale = vec3( 1.0 );
#ifdef USE_INSTANCING
texScale = vec3( length( instanceMatrix[ 0 ].xyz ), length( instanceMatrix[ 1 ].xyz ), length( instanceMatrix[ 2 ].xyz ) );
#endif
vTexPos = position * texScale;
vTexNrm = normal / texScale;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
uniform highp sampler2DArray uTexArr;
uniform float uTexLayer;
uniform float uTexTile;
uniform float uTexGain;
uniform float uTexBump;
varying vec3 vTexPos;
varying vec3 vTexNrm;
${TRIPLANAR_GLSL}
${PERTURB_GLSL}`,
      )
      .replace(
        "#include <map_fragment>",
        `vec3 tN = normalize( vTexNrm );
vec3 bw = pow( abs( tN ), vec3( 8.0 ) );
bw /= ( bw.x + bw.y + bw.z );
vec4 ts = triSample( uTexLayer, uTexTile, vTexPos, bw );
diffuseColor.rgb *= ts.rgb * uTexGain;
float texHeight = ts.a;`,
      )
      .replace(
        "#include <normal_fragment_maps>",
        `#include <normal_fragment_maps>
normal = texPerturb( - vViewPosition, normal, vec2( dFdx( texHeight ), dFdy( texHeight ) ) * uTexBump, faceDirection );`,
      );
  };
  material.customProgramCacheKey = () => "part-textured";
}

const materialCache = new Map();
function materialFor(mat, transparency, neon) {
  const alpha = 1 - transparency;
  const key = `${mat}|${alpha.toFixed(2)}|${neon}`;
  if (materialCache.has(key)) return materialCache.get(key);
  let material;
  const transparent = alpha < 0.999;
  if (neon) {
    material = new THREE.MeshBasicMaterial({ transparent, opacity: alpha });
  } else {
    const spec = PART_MATERIALS[mat] || PART_MATERIALS.Plastic;
    material = new THREE.MeshStandardMaterial({
      roughness: spec.rough,
      metalness: spec.metal ?? 0,
      transparent,
      opacity: alpha,
      depthWrite: alpha > 0.5,
    });
    if (spec.layer !== "flat") texturePart(material, spec);
  }
  materialCache.set(key, material);
  return material;
}

// 파트 -> 인스턴스 행렬 ---------------------------------------------------------------
function partMatrix(part, shape) {
  const [px, py, pz] = part.p;
  const m = part.m;
  let [sx, sy, sz] = part.z;
  if (shape === "Ball" || shape === "BallHi") {
    const d = Math.min(sx, sy, sz);
    sx = sy = sz = d;
  } else if (shape === "Cylinder" || shape === "CylinderHi") {
    const d = Math.min(sy, sz);
    sy = sz = d;
  }
  return new THREE.Matrix4().set(
    m[0] * sx, m[1] * sy, m[2] * sz, px,
    m[3] * sx, m[4] * sy, m[5] * sz, py,
    m[6] * sx, m[7] * sy, m[8] * sz, pz,
    0, 0, 0, 1,
  );
}

function buildParts(parts) {
  const groups = new Map();
  for (const part of parts) {
    info.parts++;
    if (part.t >= 0.999) continue;
    let shape = GEOMETRY[part.s] ? part.s : "Block";
    if (shape === "Ball" && Math.min(...part.z) > 60) shape = "BallHi";
    if (shape === "Cylinder" && Math.min(part.z[1], part.z[2]) > 60) shape = "CylinderHi";
    const neon = part.mat === "Neon";
    let t = part.t;
    if (part.mat === "ForceField") t = Math.max(t, 0.6);
    const key = `${shape}|${part.mat}|${t.toFixed(2)}|${part.cs}`;
    if (!groups.has(key)) groups.set(key, { shape, mat: part.mat, t, neon, cs: part.cs, items: [] });
    groups.get(key).items.push(part);
  }
  for (const g of groups.values()) {
    const mesh = new THREE.InstancedMesh(GEOMETRY[g.shape], materialFor(g.mat, g.t, g.neon), g.items.length);
    g.items.forEach((part, i) => {
      mesh.setMatrixAt(i, partMatrix(part, g.shape));
      const c = srgb(part.col);
      if (g.neon) c.multiplyScalar(1.15);
      mesh.setColorAt(i, c);
      info.drawn++;
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.instanceColor.needsUpdate = true;
    mesh.castShadow = g.cs && g.t < 0.5 && !g.neon;
    mesh.receiveShadow = !g.neon;
    mesh.frustumCulled = false;
    scene.add(mesh);
    info.groups++;
  }
}

// SurfaceGui 간판: GUI 상자들을 캔버스에 그려서 면에 붙임 --------------------------------
const images = new Map();
function loadImage(name) {
  if (images.has(name)) return images.get(name);
  const p = new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = `/art/png/${name}.png`;
  });
  images.set(name, p);
  return p;
}

function css(rgb, alpha = 1) {
  const c = rgb.map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255));
  return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
}

function tinted(img, rgb) {
  const c = document.createElement("canvas");
  c.width = img.width;
  c.height = img.height;
  const x = c.getContext("2d");
  x.drawImage(img, 0, 0);
  if (rgb[0] < 0.999 || rgb[1] < 0.999 || rgb[2] < 0.999) {
    x.globalCompositeOperation = "multiply";
    x.fillStyle = css(rgb);
    x.fillRect(0, 0, c.width, c.height);
    x.globalCompositeOperation = "destination-in";
    x.drawImage(img, 0, 0);
  }
  return c;
}

function drawImageNode(ctx, node, img) {
  const im = node.image;
  const src = tinted(img, im.color);
  const { x, y, w, h } = node;
  ctx.globalAlpha = 1 - (im.t || 0);
  if (im.scale === "Slice" && im.slice) {
    const [x0, y0, x1, y1] = im.slice;
    const s = im.sliceScale || 1;
    const sw = src.width;
    const sh = src.height;
    const L = x0 * s, T = y0 * s, R = (sw - x1) * s, B = (sh - y1) * s;
    const cols = [[0, x0, x, L], [x0, x1 - x0, x + L, w - L - R], [x1, sw - x1, x + w - R, R]];
    const rows = [[0, y0, y, T], [y0, y1 - y0, y + T, h - T - B], [y1, sh - y1, y + h - B, B]];
    for (const [sx, sW, dx, dW] of cols) {
      for (const [sy, sH, dy, dH] of rows) {
        if (sW > 0 && sH > 0 && dW > 0 && dH > 0) ctx.drawImage(src, sx, sy, sW, sH, dx, dy, dW, dH);
      }
    }
  } else if (im.scale === "Fit") {
    const k = Math.min(w / src.width, h / src.height);
    const dw = src.width * k;
    const dh = src.height * k;
    ctx.drawImage(src, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
  } else {
    ctx.drawImage(src, x, y, w, h);
  }
  ctx.globalAlpha = 1;
}

const FONT_FAMILY = {
  FredokaOne: '"Fredoka One", "WenQuanYi Zen Hei", sans-serif',
  LuckiestGuy: '"Luckiest Guy", "WenQuanYi Zen Hei", sans-serif',
};

// RichText: <font color="#rrggbb">...</font> 만 색으로, 나머지 태그는 지움
function textRuns(text, color) {
  if (!text.rich) return [{ s: text.s, color }];
  const runs = [];
  const re = /<font\s+color="#([0-9a-fA-F]{6})">(.*?)<\/font>/g;
  let last = 0;
  let m;
  while ((m = re.exec(text.rich))) {
    if (m.index > last) runs.push({ s: text.rich.slice(last, m.index), color });
    const hex = m[1];
    runs.push({ s: m[2], color: [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) });
    last = re.lastIndex;
  }
  if (last < text.rich.length) runs.push({ s: text.rich.slice(last), color });
  return runs.map((r) => ({ s: r.s.replace(/<[^>]*>/g, ""), color: r.color }));
}

function drawText(ctx, node) {
  const t = node.text;
  const pad = t.pad || [0, 0, 0, 0];
  const x = node.x + pad[0];
  const y = node.y + pad[1];
  const w = node.w - pad[0] - pad[2];
  const h = node.h - pad[1] - pad[3];
  if (w <= 0 || h <= 0) return;
  const family = FONT_FAMILY[t.font] || '"WenQuanYi Zen Hei", sans-serif';
  const runs = textRuns(t, t.color);
  const whole = runs.map((r) => r.s).join("");
  let size = t.size;
  if (t.scaled) {
    size = Math.min(100, Math.floor(h));
    while (size > 4) {
      ctx.font = `${size}px ${family}`;
      if (ctx.measureText(whole).width <= w) break;
      size -= 1;
    }
  }
  ctx.font = `${size}px ${family}`;
  ctx.textBaseline = "middle";
  const total = ctx.measureText(whole).width;
  let cx = x + (w - total) / 2;
  if (t.xa === "Left") cx = x;
  else if (t.xa === "Right") cx = x + w - total;
  let cy = y + h / 2;
  if (t.ya === "Top") cy = y + size / 2;
  else if (t.ya === "Bottom") cy = y + h - size / 2;
  ctx.globalAlpha = 1 - (t.t || 0);
  for (const run of runs) {
    if (t.stroke) {
      ctx.lineJoin = "round";
      ctx.lineWidth = t.stroke.w * 2;
      ctx.strokeStyle = css(t.stroke.color);
      ctx.strokeText(run.s, cx, cy);
    }
    ctx.fillStyle = css(run.color);
    ctx.fillText(run.s, cx, cy);
    cx += ctx.measureText(run.s).width;
  }
  ctx.globalAlpha = 1;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, Math.max(0, Math.min(r || 0, w / 2, h / 2)));
}

async function drawGui(record) {
  const scale = Math.min(1, 2048 / Math.max(record.cw, record.ch));
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(record.cw * scale));
  c.height = Math.max(1, Math.round(record.ch * scale));
  const ctx = c.getContext("2d");
  ctx.scale(scale, scale);
  for (const node of record.nodes) {
    const img = node.image ? await loadImage(node.image.name) : null;
    ctx.save();
    if (node.rot) {
      ctx.translate(node.x + node.w / 2, node.y + node.h / 2);
      ctx.rotate((node.rot * Math.PI) / 180);
      ctx.translate(-(node.x + node.w / 2), -(node.y + node.h / 2));
    }
    const r = node.corner || 0;
    if (node.stroke && (node.bg || img)) {
      // UIStroke(Border): 상자 바깥으로 두께만큼
      const s = node.stroke.w;
      roundRect(ctx, node.x - s, node.y - s, node.w + s * 2, node.h + s * 2, r + s);
      ctx.fillStyle = css(node.stroke.color, 1 - (node.stroke.t || 0));
      ctx.fill();
    }
    if (node.bg) {
      roundRect(ctx, node.x, node.y, node.w, node.h, r);
      let fill = css(node.bg, 1 - node.bgT);
      if (node.gradient) {
        const a = (node.gradient.rot * Math.PI) / 180;
        const cx = node.x + node.w / 2;
        const cy = node.y + node.h / 2;
        const dx = (Math.cos(a) * node.w) / 2;
        const dy = (Math.sin(a) * node.h) / 2;
        const grad = ctx.createLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy);
        const mul = (k) => node.bg.map((v, i) => v * node.gradient[k][i]);
        grad.addColorStop(0, css(mul("from"), 1 - node.bgT));
        grad.addColorStop(1, css(mul("to"), 1 - node.bgT));
        fill = grad;
      }
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (img) drawImageNode(ctx, node, img);
    if (node.text) drawText(ctx, node);
    ctx.restore();
  }
  const texture = new THREE.CanvasTexture(c);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  const material = record.lit
    ? new THREE.MeshStandardMaterial({ map: texture, transparent: true, roughness: 0.8 })
    : new THREE.MeshBasicMaterial({ map: texture, transparent: true });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(record.w, record.h), material);
  const right = v3(...record.right);
  const up = v3(...record.up);
  const normal = v3(...record.normal);
  mesh.matrixAutoUpdate = false;
  mesh.matrix.makeBasis(right, up, normal);
  mesh.matrix.setPosition(v3(...record.center).addScaledVector(normal, 0.03));
  scene.add(mesh);
  info.gui++;
}

// 하늘·해·안개 -------------------------------------------------------------------------
function sunDirection(clockTime, latitude) {
  const a = (2 * Math.PI * clockTime) / 24;
  const x = Math.sin(a);
  const y = -Math.cos(a);
  const lat = (latitude * Math.PI) / 180;
  return v3(x, y * Math.cos(lat), y * Math.sin(lat)).normalize();
}

const SKY_ZENITH = [0.33, 0.6, 0.93];
const SKY_HORIZON = [0.77, 0.87, 0.97];
const VOID = [0.6, 0.66, 0.73]; // 지평선 아래(섬 밖 허공): Atmosphere 가 있는 Roblox 하늘 아래쪽처럼 흐린 회청색

function makeSky(sun) {
  const material = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      zenith: { value: srgb(SKY_ZENITH) },
      horizon: { value: srgb(SKY_HORIZON) },
      below: { value: srgb(VOID) },
      sunDir: { value: sun },
    },
    vertexShader: `
      varying vec3 vDir;
      void main() {
        vDir = normalize(position);
        vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        gl_Position = p.xyww;
      }`,
    fragmentShader: `
      uniform vec3 zenith; uniform vec3 horizon; uniform vec3 below; uniform vec3 sunDir;
      varying vec3 vDir;
      void main() {
        vec3 d = normalize(vDir);
        vec3 c;
        if (d.y >= 0.0) c = mix(horizon, zenith, pow(d.y, 0.55));
        else c = mix(horizon, below, clamp(-d.y * 30.0, 0.0, 1.0));
        float s = max(dot(d, normalize(sunDir)), 0.0);
        c += vec3(1.0, 0.95, 0.85) * (pow(s, 900.0) * 3.0 + pow(s, 12.0) * 0.12);
        gl_FragColor = vec4(c, 1.0);
        #include <colorspace_fragment>
      }`,
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(9000, 48, 24), material);
  sky.renderOrder = -1;
  sky.frustumCulled = false;
  return sky;
}

let sun = null;
let sunDir = null;
let lightEnv = null; // 물 셰이더가 쓰는 해·하늘 값(선형 색)

function setupLighting(lighting) {
  const clock = lighting.ClockTime ?? 14;
  const lat = lighting.GeographicLatitude ?? 41.733;
  sunDir = sunDirection(clock, lat);
  const brightness = lighting.Brightness ?? 2;
  const outdoor = lighting.OutdoorAmbient ?? [0.5, 0.5, 0.5];
  const ambientLevel = (outdoor[0] + outdoor[1] + outdoor[2]) / 3;

  // 세기 단위: three.js 물리 기반(흰 면이 빛을 정면으로 받으면 intensity / π)
  const sunUp = Math.max(0, sunDir.y);
  sun = new THREE.DirectionalLight(srgb([1, 0.97, 0.9]), Math.PI * 0.55 * brightness * Math.min(1, sunUp * 4));
  sun.castShadow = sunUp > 0.02;
  sun.shadow.mapSize.set(4096, 4096);
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.35;
  sun.shadow.radius = 3;
  scene.add(sun);
  scene.add(sun.target);

  // 해가 비치는 윗면이 대략 원래 색(×1.0), 그늘은 ×0.65 정도가 되도록 맞춘 값
  const hemi = new THREE.HemisphereLight(
    srgb([0.85, 0.9, 1.0]),
    srgb([0.62, 0.6, 0.55]),
    Math.PI * (0.3 + 0.45 * ambientLevel),
  );
  scene.add(hemi);

  scene.add(makeSky(sunDir));
  lightEnv = {
    sunDir: sunDir.clone(),
    sunColor: srgb([1, 0.97, 0.9]).multiplyScalar(sun.intensity / Math.PI),
    ambient: srgb([0.85, 0.9, 1.0]).multiplyScalar(hemi.intensity / Math.PI),
    zenith: srgb(SKY_ZENITH),
    horizon: srgb(SKY_HORIZON),
  };

  const atmosphere = lighting.Atmosphere;
  if (atmosphere) {
    fogDensity = 0.00257 * atmosphere.Density * (1 + 0.1 * (atmosphere.Haze || 0));
    const hazeTint = atmosphere.Color || [0.78, 0.78, 0.78];
    const fogColor = SKY_HORIZON.map((v, i) => v * 0.85 + hazeTint[i] * 0.15);
    scene.fog = new THREE.FogExp2(srgb(fogColor), fogDensity);
  } else if (lighting.FogEnd && lighting.FogEnd < 10000) {
    scene.fog = new THREE.Fog(srgb(lighting.FogColor || [0.75, 0.75, 0.75]), lighting.FogStart || 0, lighting.FogEnd);
  }
}

function aimShadow(center, halfSize) {
  if (!sun) return;
  sun.position.copy(center).addScaledVector(sunDir, 2000);
  sun.target.position.copy(center);
  sun.target.updateMatrixWorld();
  const cam = sun.shadow.camera;
  cam.left = -halfSize;
  cam.right = halfSize;
  cam.top = halfSize;
  cam.bottom = -halfSize;
  cam.near = 100;
  cam.far = 4000;
  cam.updateProjectionMatrix();
  sun.shadow.needsUpdate = true;
}

// 시점 --------------------------------------------------------------------------------
// edge: 1번 부지(스폰 정면 왼쪽, 247.5도) 뒤쪽 울타리 바로 안(마지막 전시 줄 뒤, 중심에서 194)에 서서
// 바깥(지평선)을 약 7도 내려다봄. 눈높이 6.5(캐릭터 머리 + 카메라가 살짝 위)
function edgeView() {
  const a = (247.5 * Math.PI) / 180;
  const d = v3(Math.cos(a), 0, Math.sin(a));
  const eye = d.clone().multiplyScalar(194).setY(6.5);
  const target = d.clone().multiplyScalar(420).setY(-21);
  return { eye, target };
}

// 지형 물가 찾기: 방향 angle(도)로 광장에서 바깥으로 가며 땅 → 물로 바뀌는 첫 곳의 거리(없으면 null)
function shoreDistance(angle) {
  if (!grid) return null;
  const a = (angle * Math.PI) / 180;
  let wasLand = false;
  for (let r = 120; r < 1400; r += 2) {
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r;
    const h = grid.heightAt(x, z);
    const w = grid.waterAt(x, z);
    const land = !Number.isNaN(h) && (Number.isNaN(w) || h > w);
    if (land) wasLand = true;
    else if (wasLand && !Number.isNaN(w)) return r;
  }
  return null;
}

// 땅 높이(지형이 없거나 더 낮으면 0 — 섬 바닥 파트 윗면)
function groundY(x, z) {
  const h = grid ? grid.heightAt(x, z) : NaN;
  if (Number.isNaN(h)) return 0;
  const w = grid.waterAt(x, z);
  return Number.isNaN(w) ? h : Math.max(h, w);
}

const BEACH_ANGLES = [202.5, 157.5, 112.5, 67.5, 22.5, 337.5, 292.5, 247.5]; // 부지 사이 틈 방향(물가가 트인 곳)

const VIEWS = {
  overview: () => {
    // 남동쪽(+X, +Z) 30도 위에서: 섬 전체와 둘레 바다가 들어오는 거리(섬이 크면 그만큼 멀리)
    const k = frame.radius / 300;
    const cam = new THREE.PerspectiveCamera(40, W / H, 1, 20000);
    cam.position.set(467 * k, 470 * k, 667 * k);
    cam.lookAt(20 * k, -40 * k, 60 * k);
    return { cam, shadowCenter: v3(0, 0, 0), shadowHalf: frame.radius * 1.2, fog: 0.35 };
  },
  spawn: () => {
    const cam = new THREE.PerspectiveCamera(70, W / H, 0.3, 20000);
    cam.position.set(0, 4.5, 10);
    cam.lookAt(0, 11, -26); // 지구본 꼭대기까지 들어오게 약 10도 올려 봄
    return { cam, shadowCenter: v3(0, 0, -90), shadowHalf: 230, fog: 1 };
  },
  edge: () => {
    const { eye, target } = edgeView();
    const cam = new THREE.PerspectiveCamera(70, W / H, 0.3, 20000);
    cam.position.copy(eye);
    cam.lookAt(target);
    const center = eye.clone().lerp(target, 0.4).setY(0);
    return { cam, shadowCenter: center, shadowHalf: 220, fog: 1 };
  },
  // 모래사장 눈높이: 물가에서 14 스터드 안쪽에 서서 물가를 따라(바다 쪽으로 25도) 봄
  beach: () => {
    let angle = BEACH_ANGLES[0];
    let shore = null;
    for (const a of BEACH_ANGLES) {
      shore = shoreDistance(a);
      if (shore) {
        angle = a;
        break;
      }
    }
    if (!shore) shore = 250; // 지형 물이 없음: 예전 섬 바닥(반지름 250) 가장자리
    const a = (angle * Math.PI) / 180;
    const radial = v3(Math.cos(a), 0, Math.sin(a));
    const tangent = v3(-Math.sin(a), 0, Math.cos(a));
    const eye = radial.clone().multiplyScalar(shore - 14);
    eye.y = groundY(eye.x, eye.z) + 5.5;
    const dir = tangent.clone().multiplyScalar(Math.cos(0.44)).addScaledVector(radial, Math.sin(0.44));
    const target = eye.clone().addScaledVector(dir, 60);
    target.y = eye.y - 4;
    const cam = new THREE.PerspectiveCamera(70, W / H, 0.3, 20000);
    cam.position.copy(eye);
    cam.lookAt(target);
    return { cam, shadowCenter: eye.clone().addScaledVector(dir, 50).setY(0), shadowHalf: 130, fog: 1 };
  },
  // 부지 사이 틈 정원 하나를 25 스터드 떨어진 3/4 시점(광장 쪽 옆에서 30도 내려다봄). 틈 번호 = options.gap(1~8)
  closeup: () => {
    const gap = Math.min(8, Math.max(1, Math.round(options.gap || 2)));
    const g = ((247.5 + 22.5 + 45 * (gap - 1)) * Math.PI) / 180;
    const radial = v3(Math.cos(g), 0, Math.sin(g));
    const target = radial.clone().multiplyScalar(165);
    target.y = groundY(target.x, target.z) + 2;
    const back = radial.clone().negate().applyAxisAngle(v3(0, 1, 0), (35 * Math.PI) / 180);
    const el = (30 * Math.PI) / 180;
    const eye = target.clone().addScaledVector(back, 25 * Math.cos(el));
    eye.y += 25 * Math.sin(el);
    const cam = new THREE.PerspectiveCamera(60, W / H, 0.3, 20000);
    cam.position.copy(eye);
    cam.lookAt(target);
    return { cam, shadowCenter: target.clone().setY(0), shadowHalf: 90, fog: 1 };
  },
  // 도구 점검용 작은 장면(test_scene.luau) 전용 시점: 재질 견본 줄, 물가(현무암 바위), 언덕·쐐기 절벽
  samples: () => customView("cam:-30,40,110:-30,0,20:55"),
  shore: () => customView("cam:120,10,80:100,-4,20:60"),
  hill: () => customView("cam:0,60,-200:0,-4,-110:55"),
  top: () => {
    const half = Math.max(450, frame.radius * 1.15);
    const cam = new THREE.OrthographicCamera((-half * W) / H, (half * W) / H, half, -half, 1, 5000);
    cam.position.set(0, 1500, 0);
    cam.up.set(0, 0, -1); // 화면 위 = -Z(스폰에서 지구본 쪽)
    cam.lookAt(0, 0, 0);
    return { cam, shadowCenter: v3(0, 0, 0), shadowHalf: half + 10, fog: 0 };
  },
};

// 섬 크기(overview/top 시점 거리): 광장(원점)에서 사방으로 나가며 처음 물이 되는 거리 중 가장 먼 것 + 40.
// 먼 작은 섬은 빼고 본섬만. 원점에 땅이 없거나 지형이 없으면 300(예전 600x600 바닥 기준)
function computeFrame() {
  let radius = 0;
  if (grid) {
    const h0 = grid.heightAt(0, 0);
    const w0 = grid.waterAt(0, 0);
    if (!Number.isNaN(h0) && (Number.isNaN(w0) || h0 > w0)) {
      for (let angle = 0; angle < 360; angle += 3) {
        const a = (angle * Math.PI) / 180;
        for (let r = 0; r < 2000; r += 2) {
          const x = Math.cos(a) * r;
          const z = Math.sin(a) * r;
          const h = grid.heightAt(x, z);
          const w = grid.waterAt(x, z);
          if (Number.isNaN(h) || (!Number.isNaN(w) && w >= h)) {
            radius = Math.max(radius, r);
            break;
          }
        }
      }
    }
  }
  frame = { radius: radius > 0 ? Math.max(120, radius + 40) : 300 };
}

async function load(opts = {}) {
  options = opts || {};
  const res = await fetch("/dump.json");
  dump = await res.json();
  const started = performance.now();
  textures = buildMaterialTextures(THREE);
  const textureMs = performance.now() - started;
  setupLighting(dump.lighting || {});
  grid = makeTerrainGrid(dump.terrain);
  let terrainStats = null;
  if (grid) {
    terrain = buildTerrain(grid, textures, { ...lightEnv, foam: !!options.foam, debug: !!options.debug });
    scene.add(terrain.group);
    if (terrain.water) {
      waterScene.add(terrain.water);
      setupWaterPass();
    }
    terrainStats = { ...terrain.stats, decoration: !!(dump.terrain.props || {}).Decoration };
  }
  computeFrame();
  if (dump.meta && dump.meta.test) window.preview.views = TEST_VIEWS;
  buildParts(dump.parts);
  await document.fonts.load('40px "Fredoka One"').catch(() => {});
  await document.fonts.load('40px "Luckiest Guy"').catch(() => {});
  for (const record of dump.gui || []) await drawGui(record);
  return {
    ...info,
    sun: sunDir.toArray().map((v) => +v.toFixed(3)),
    fog: fogDensity,
    terrain: terrainStats,
    frame: Math.round(frame.radius),
    textureMs: Math.round(textureMs),
  };
}

// 임의 시점: "cam:x,y,z:tx,ty,tz[:fov]" (예: cam:0,60,120:0,0,0:50) — 특정 자리를 자세히 볼 때
function customView(name) {
  const [, eye, target, fov] = name.split(":");
  const e = eye.split(",").map(Number);
  const t = target.split(",").map(Number);
  const cam = new THREE.PerspectiveCamera(Number(fov) || 60, W / H, 0.3, 20000);
  cam.position.set(e[0], e[1], e[2]);
  cam.lookAt(t[0], t[1], t[2]);
  const center = v3(t[0], 0, t[2]);
  return { cam, shadowCenter: center, shadowHalf: Math.max(60, cam.position.distanceTo(center) * 1.2), fog: 1 };
}

// 물 그리기 준비: 장면 텍스처(선형 반정밀 색 + 깊이, 4x 다중 표본)와 화면 옮기기 사각형
function setupWaterPass() {
  const depthTexture = new THREE.DepthTexture(W, H);
  depthTexture.type = THREE.UnsignedIntType;
  sceneTarget = new THREE.WebGLRenderTarget(W, H, {
    type: THREE.HalfFloatType,
    samples: 4,
    depthBuffer: true,
    depthTexture,
  });
  sceneTarget.texture.colorSpace = THREE.LinearSRGBColorSpace;
  const quad = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.ShaderMaterial({
      uniforms: { tScene: { value: sceneTarget.texture } },
      depthTest: false,
      depthWrite: false,
      vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4( position.xy, 0.0, 1.0 ); }`,
      fragmentShader: `uniform sampler2D tScene; varying vec2 vUv;
void main() { gl_FragColor = vec4( texture( tScene, vUv ).rgb, 1.0 ); 
#include <colorspace_fragment>
}`,
    }),
  );
  quad.frustumCulled = false;
  const quadScene = new THREE.Scene();
  quadScene.add(quad);
  composite = { scene: quadScene, camera: new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1) };
  waterScene.fog = scene.fog;
}

function render(name) {
  const view = name.startsWith("cam:") ? customView(name) : VIEWS[name]();
  view.cam.updateMatrixWorld();
  if (terrain) terrain.updateGrass(view.cam, scene);
  aimShadow(view.shadowCenter, view.shadowHalf);
  if (scene.fog && scene.fog.isFogExp2) scene.fog.density = fogDensity * view.fog;
  if (sceneTarget) {
    // ① 물 빼고 장면 → 텍스처 ② 화면으로 옮김 ③ 물(텍스처를 읽어 바닥색·물속 길이 계산)
    renderer.setRenderTarget(sceneTarget);
    renderer.render(scene, view.cam);
    renderer.setRenderTarget(null);
    terrain.setWaterInputs(sceneTarget, view.cam, W, H);
    renderer.render(composite.scene, composite.camera);
    renderer.autoClear = false;
    renderer.clearDepth();
    renderer.render(waterScene, view.cam);
    renderer.autoClear = true;
  } else {
    renderer.render(scene, view.cam);
  }
  return canvas.toDataURL("image/png");
}

// 기본 시점 목록: 게임 맵은 overview/spawn/edge/beach/closeup/top, 점검 장면(meta.test)은 overview/samples/shore/hill/top
const GAME_VIEWS = ["overview", "spawn", "edge", "beach", "closeup", "top"];
const TEST_VIEWS = ["overview", "samples", "shore", "hill", "top"];
window.preview = { load, render, views: GAME_VIEWS };
window.previewReady = true;
