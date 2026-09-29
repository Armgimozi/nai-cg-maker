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
//   * Highlight(덤프 hl): 대상 파트 실루엣을 채우기(FillColor·FillTransparency) + 바깥 테두리(OutlineColor, 2px)로.
//     AlwaysOnTop 은 가려진 곳까지, Occluded 는 보이는 곳만(다른 파트가 앞을 가리면 빠짐)
// 안 그리는 것: BillboardGui(이름표), 파티클, 빛(PointLight), 텍스처/Decal, MeshPart 실제 모양(상자로 대신)

import * as THREE from "three";

// 그림 크기: 기본 1280x720, preview.resize(w, h) 로 바꿈(배치 모드 목업의 휴대폰 화면 등)
let W = 1280;
let H = 720;
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
const ROUGH = {
  SmoothPlastic: 0.5,
  Plastic: 0.68,
  Glass: 0.08,
  Ice: 0.2,
  Glacier: 0.25,
  Marble: 0.45,
  Foil: 0.3,
  Metal: 0.4,
  DiamondPlate: 0.45,
  CorrodedMetal: 0.8,
  Wood: 0.8,
  WoodPlanks: 0.8,
  Water: 0.1,
};
const METAL = { Metal: 0.3, Foil: 0.4, DiamondPlate: 0.3, CorrodedMetal: 0.15 };
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
    material = new THREE.MeshStandardMaterial({
      roughness: ROUGH[mat] ?? 0.9,
      metalness: METAL[mat] ?? 0,
      transparent,
      opacity: alpha,
      depthWrite: alpha > 0.5,
    });
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

// Highlight ------------------------------------------------------------------------------
// 강조마다: 가림 판정용 가면(흰 = 대상이 보이는 곳)을 따로 그린 뒤, 화면 전체 사각형으로 채우기 + 테두리를 얹음
const highlights = [];
const maskBlack = new THREE.MeshBasicMaterial({ color: 0x000000 });
const maskWhite = (top) =>
  new THREE.MeshBasicMaterial({
    color: 0xffffff,
    depthTest: !top,
    depthWrite: false,
    depthFunc: THREE.LessEqualDepth,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
let maskTarget = null;
const overlayCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const overlayMaterial = new THREE.ShaderMaterial({
  transparent: true,
  depthTest: false,
  depthWrite: false,
  uniforms: {
    mask: { value: null },
    texel: { value: new THREE.Vector2(1 / 1280, 1 / 720) },
    fill: { value: new THREE.Color() },
    fillAlpha: { value: 0.5 },
    outline: { value: new THREE.Color() },
    outlineAlpha: { value: 1 },
  },
  vertexShader: `
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: `
    uniform sampler2D mask; uniform vec2 texel; uniform vec3 fill; uniform float fillAlpha;
    uniform vec3 outline; uniform float outlineAlpha;
    varying vec2 vUv;
    void main() {
      float inside = texture2D(mask, vUv).r;
      if (inside > 0.5) {
        gl_FragColor = vec4(fill, fillAlpha);
      } else {
        float near = 0.0;
        for (int x = -2; x <= 2; x++) {
          for (int y = -2; y <= 2; y++) {
            if (x * x + y * y <= 5) near = max(near, texture2D(mask, vUv + vec2(float(x), float(y)) * texel).r);
          }
        }
        if (near < 0.5) discard;
        gl_FragColor = vec4(outline, outlineAlpha);
      }
      #include <colorspace_fragment>
    }`,
});
const overlayQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), overlayMaterial);
overlayQuad.frustumCulled = false;
const overlayScene = new THREE.Scene();
overlayScene.add(overlayQuad);

function buildHighlights(list, parts) {
  for (const h of list || []) {
    const group = new THREE.Group();
    const material = maskWhite(h.top);
    for (const index of h.parts) {
      const part = parts[index];
      if (!part) continue;
      const shape = GEOMETRY[part.s] ? part.s : "Block";
      const mesh = new THREE.Mesh(GEOMETRY[shape], material);
      mesh.matrixAutoUpdate = false;
      mesh.matrix.copy(partMatrix(part, shape));
      mesh.frustumCulled = false;
      group.add(mesh);
    }
    group.visible = false;
    group.renderOrder = 10;
    scene.add(group);
    highlights.push({ h, group });
  }
}

function drawHighlights(cam) {
  if (!highlights.length) return;
  if (!maskTarget || maskTarget.width !== W || maskTarget.height !== H) {
    if (maskTarget) maskTarget.dispose();
    maskTarget = new THREE.WebGLRenderTarget(W, H);
  }
  const fog = scene.fog;
  const background = scene.background;
  scene.fog = null;
  scene.background = new THREE.Color(0x000000);
  renderer.autoClear = false;
  for (const { h, group } of highlights) {
    renderer.setRenderTarget(maskTarget);
    renderer.setClearColor(0x000000, 1);
    renderer.clear(true, true, true);
    if (!h.top) {
      // 가림 판정: 장면 전체를 검정으로(깊이만) 그린 뒤 대상을 흰색으로(같은 깊이 이하만)
      scene.overrideMaterial = maskBlack;
      renderer.render(scene, cam);
      scene.overrideMaterial = null;
    }
    const hidden = [];
    scene.children.forEach((child) => {
      if (child !== group && child.visible) {
        hidden.push(child);
        child.visible = false;
      }
    });
    group.visible = true;
    renderer.render(scene, cam);
    group.visible = false;
    hidden.forEach((child) => (child.visible = true));
    renderer.setRenderTarget(null);
    overlayMaterial.uniforms.mask.value = maskTarget.texture;
    overlayMaterial.uniforms.texel.value.set(1 / W, 1 / H);
    overlayMaterial.uniforms.fill.value.copy(srgb(h.fill));
    overlayMaterial.uniforms.fillAlpha.value = 1 - h.ft;
    overlayMaterial.uniforms.outline.value.copy(srgb(h.outline));
    overlayMaterial.uniforms.outlineAlpha.value = 1 - h.ot;
    renderer.render(overlayScene, overlayCamera);
  }
  renderer.autoClear = true;
  scene.fog = fog;
  scene.background = background;
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

const VIEWS = {
  overview: () => {
    // 남동쪽(+X, +Z) 30도 위에서: 600x600 바닥 네 모서리와 그 바깥 허공이 다 들어오는 거리
    const cam = new THREE.PerspectiveCamera(40, W / H, 1, 20000);
    cam.position.set(467, 470, 667);
    cam.lookAt(20, -40, 60);
    return { cam, shadowCenter: v3(0, 0, 0), shadowHalf: 360, fog: 0.35 };
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
  top: () => {
    const half = 450;
    const cam = new THREE.OrthographicCamera((-half * W) / H, (half * W) / H, half, -half, 1, 5000);
    cam.position.set(0, 1500, 0);
    cam.up.set(0, 0, -1); // 화면 위 = -Z(스폰에서 지구본 쪽)
    cam.lookAt(0, 0, 0);
    return { cam, shadowCenter: v3(0, 0, 0), shadowHalf: 460, fog: 0 };
  },
};

async function load() {
  const res = await fetch("/dump.json");
  dump = await res.json();
  setupLighting(dump.lighting || {});
  buildParts(dump.parts);
  buildHighlights(dump.hl, dump.parts);
  await document.fonts.load('40px "Fredoka One"').catch(() => {});
  await document.fonts.load('40px "Luckiest Guy"').catch(() => {});
  for (const record of dump.gui || []) await drawGui(record);
  return { ...info, sun: sunDir.toArray().map((v) => +v.toFixed(3)), fog: fogDensity };
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

// hook 시점: world.luau hook 이 돌려준 카메라(extra.Camera = { Position, Look, Up, Fov } — 로블록스 CurrentCamera 그대로)
function hookView() {
  const c = dump.extra && dump.extra.Camera;
  if (!c) throw new Error("덤프에 extra.Camera 가 없습니다(hook=... 로 world.luau 를 돌렸나요?)");
  const cam = new THREE.PerspectiveCamera(c.Fov || 70, W / H, 0.3, 20000);
  cam.position.set(...c.Position);
  cam.up.set(...(c.Up || [0, 1, 0]));
  cam.lookAt(c.Position[0] + c.Look[0], c.Position[1] + c.Look[1], c.Position[2] + c.Look[2]);
  // 그림자: 카메라가 보는 바닥 근처
  const t = c.Position[1] / Math.max(0.05, -c.Look[1]);
  const center = v3(c.Position[0] + c.Look[0] * t, 0, c.Position[2] + c.Look[2] * t);
  return { cam, shadowCenter: center, shadowHalf: Math.max(80, t * 1.1), fog: 1 };
}

function resize(w, h) {
  W = w;
  H = h;
  renderer.setSize(W, H, false);
}

// format: "png"(기본) | "jpeg" (quality 0..1)
function render(name, format = "png", quality = 0.9) {
  const view = name === "hook" ? hookView() : name.startsWith("cam:") ? customView(name) : VIEWS[name]();
  aimShadow(view.shadowCenter, view.shadowHalf);
  if (scene.fog && scene.fog.isFogExp2) scene.fog.density = fogDensity * view.fog;
  renderer.render(scene, view.cam);
  drawHighlights(view.cam);
  return format === "jpeg" ? canvas.toDataURL("image/jpeg", quality) : canvas.toDataURL("image/png");
}

window.preview = { load, render, resize, views: Object.keys(VIEWS) };
window.previewReady = true;
