// 스토어 그림(아이콘·썸네일)용 3D 층 렌더러(브라우저 쪽). render3d.js(Playwright)가 이 페이지를 열고
// window.store.load(scene) → window.store.render(layer) 로 층마다 투명 배경 PNG 를 받습니다.
//
// 장면(scene.json)
//   size   : [W, H]
//   camera : { eye:[x,y,z], target:[x,y,z], fov: 도(세로), up?:[0,1,0] }
//   light  : { sun:[방향](빛이 오는 쪽), sunColor, sunIntensity, hemiSky, hemiGround, hemiIntensity,
//              rims:[{ dir, color, intensity }], shadowCenter:[x,y,z], shadowBox: 반 크기 }
//   rim    : { color:[r,g,b], power, strength } — rim:true 인 물체에 프레넬 테두리 빛(전설 등급 느낌)
//   objects: [{ tag, rim?(true 또는 세기 숫자), castShadow?, parts?, rocks?, shards?, ribbons?, quads? }]
//     parts  : model_preview 덤프(mock.luau)의 파트 그대로 {c,s,p,m,z,col,t,mat} — 명소 모형을 진짜 빌더 결과로 그림
//              (모양·재질 규칙은 tools/world_preview/scene.js 와 같음. 재질 무늬는 textures.js 를 그대로 씀)
//     rocks  : [{ p, size:[x,y,z], rot:[rx,ry,rz](도), col, mat?, seed, points? }] 무작위 점 볼록 껍질(각진 바위)
//     shards : [{ p, len, radius, rot, col, seed, emissive? }] 길쭉한 결정(볼록 껍질, 면마다 평평)
//     ribbons: [{ points:[[x,y,z]...], normal?: "out"|"up", width:[...], color:[r,g,b], alpha:[...] }] 띠(점마다 폭·투명도)
//     quads  : [{ image:"/file/절대경로.png", p, size:[w,d], rotY, color?, opacity? }] 땅에 눕힌 그림(마법진·금 등)
//   layers : [{ name, draw:[tag], occlude?:[tag], shadow?:[tag], exposure? }]
//     draw = 그림, occlude = 깊이만(보이지 않지만 뒤를 가림), shadow = 그림자만 드리움. 배경은 늘 투명
import * as THREE from "three";
import { ConvexGeometry } from "three/addons/geometries/ConvexGeometry.js";
import { buildMaterialTextures, PART_MATERIALS } from "/wp/textures.js";
import { PERTURB_GLSL, TRIPLANAR_GLSL } from "/wp/terrain.js";

const canvas = document.getElementById("view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NoToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setClearColor(0x000000, 0);

const scene = new THREE.Scene();
let camera = null;
let textures = null;
let rimSpec = { color: [0.47, 1, 0.92], power: 2.5, strength: 0 };
const objects = []; // { tag, mesh, material, castShadow }

const srgb = (rgb) => new THREE.Color().setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
const v3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);

// 결정적 난수(같은 seed → 같은 모양)
function rng(seed) {
  let s = (seed * 2654435761) >>> 0 || 1;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return (s >>> 0) / 4294967296;
  };
}

// 기본 도형(크기 1): scene.js 의 GEOMETRY 와 같은 규칙 -----------------------------------
function convexFaces(vertices, faces) {
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
  g.computeVertexNormals();
  return g;
}
const p3 = (x, y, z) => new THREE.Vector3(x, y, z);
const GEOMETRY = {
  Block: new THREE.BoxGeometry(1, 1, 1),
  Ball: new THREE.SphereGeometry(0.5, 64, 40),
  Cylinder: new THREE.CylinderGeometry(0.5, 0.5, 1, 64, 1).rotateZ(-Math.PI / 2),
  Wedge: convexFaces(
    [p3(-0.5, -0.5, -0.5), p3(0.5, -0.5, -0.5), p3(-0.5, -0.5, 0.5), p3(0.5, -0.5, 0.5), p3(-0.5, 0.5, 0.5), p3(0.5, 0.5, 0.5)],
    [[0, 1, 3, 2], [2, 3, 5, 4], [0, 2, 4], [1, 3, 5], [0, 1, 5, 4]],
  ),
  CornerWedge: convexFaces(
    [p3(0.5, 0.5, -0.5), p3(0.5, -0.5, 0.5), p3(0.5, -0.5, -0.5), p3(-0.5, -0.5, 0.5), p3(-0.5, -0.5, -0.5)],
    [[1, 2, 4, 3], [0, 2, 1], [0, 4, 2], [0, 1, 3], [0, 3, 4]],
  ),
};

function shapeOf(part) {
  if (part.c === "WedgePart" || part.s === "PartType.Wedge" || part.s === "Wedge") return "Wedge";
  if (part.c === "CornerWedgePart" || part.s === "PartType.CornerWedge" || part.s === "CornerWedge") return "CornerWedge";
  const s = String(part.s || "Block").replace("PartType.", "");
  return GEOMETRY[s] ? s : "Block";
}

function partMatrix(part, shape) {
  const [px, py, pz] = part.p;
  const m = part.m;
  let [sx, sy, sz] = part.z;
  if (shape === "Ball") {
    const d = Math.min(sx, sy, sz);
    sx = sy = sz = d;
  } else if (shape === "Cylinder") {
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

// 재질: MeshStandardMaterial + (재질 무늬) + (프레넬 테두리 빛) ---------------------------------
function standard(matName, { alpha = 1, rim = false, flat = false, scaleFromMatrix = true } = {}) {
  const spec = PART_MATERIALS[matName] || PART_MATERIALS.Plastic;
  const material = new THREE.MeshStandardMaterial({
    roughness: spec.rough,
    metalness: spec.metal ?? 0,
    transparent: alpha < 0.999,
    opacity: alpha,
    depthWrite: alpha > 0.5,
    flatShading: flat,
  });
  const textured = spec.layer !== "flat";
  if (!textured && !rim) return material;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uRimColor = { value: srgb(rimSpec.color) };
    shader.uniforms.uRimPow = { value: rimSpec.power };
    shader.uniforms.uRimStrength = { value: typeof rim === "number" ? rim : rim ? rimSpec.strength : 0 };
    let head = "#include <common>\nuniform vec3 uRimColor;\nuniform float uRimPow;\nuniform float uRimStrength;";
    if (textured) {
      Object.assign(shader.uniforms, {
        uTexArr: { value: textures.texture },
        uTexLayer: { value: textures.layers[spec.layer] },
        uTexTile: { value: spec.tile },
        uTexGain: { value: textures.gain[spec.layer] },
        uTexBump: { value: spec.bump },
      });
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nvarying vec3 vTexPos;\nvarying vec3 vTexNrm;")
        .replace(
          "#include <begin_vertex>",
          `#include <begin_vertex>
vec3 texScale = vec3( ${scaleFromMatrix ? "length( modelMatrix[ 0 ].xyz ), length( modelMatrix[ 1 ].xyz ), length( modelMatrix[ 2 ].xyz )" : "1.0"} );
vTexPos = position * texScale;
vTexNrm = normal / texScale;`,
        );
      head += `
uniform highp sampler2DArray uTexArr;
uniform float uTexLayer;
uniform float uTexTile;
uniform float uTexGain;
uniform float uTexBump;
varying vec3 vTexPos;
varying vec3 vTexNrm;
${TRIPLANAR_GLSL}
${PERTURB_GLSL}`;
      shader.fragmentShader = shader.fragmentShader
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
    }
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", head)
      .replace(
        "#include <opaque_fragment>",
        `float rimF = 1.0 - clamp( dot( normal, normalize( vViewPosition ) ), 0.0, 1.0 );
outgoingLight += uRimColor * pow( rimF, uRimPow ) * uRimStrength;
#include <opaque_fragment>`,
      );
  };
  material.customProgramCacheKey = () => `store|${textured ? spec.layer : "flat"}|${rim}|${scaleFromMatrix}`;
  return material;
}

function neonMaterial(rgb, alpha = 1) {
  const c = srgb(rgb).multiplyScalar(1.15);
  return new THREE.MeshBasicMaterial({ color: c, transparent: alpha < 0.999, opacity: alpha, depthWrite: alpha > 0.5 });
}

// 물체 만들기 ----------------------------------------------------------------------------
function addMesh(tag, mesh, castShadow = true) {
  mesh.castShadow = castShadow;
  mesh.receiveShadow = true;
  mesh.frustumCulled = false;
  scene.add(mesh);
  objects.push({ tag, mesh, material: mesh.material, castShadow });
}

function buildParts(obj) {
  for (const part of obj.parts) {
    if (part.t >= 0.999) continue;
    const shape = shapeOf(part);
    const mat = String(part.mat || "Plastic").replace("Material.", "");
    const alpha = 1 - (mat === "ForceField" ? Math.max(part.t, 0.6) : part.t);
    let material;
    if (mat === "Neon") material = neonMaterial(part.col, alpha);
    else {
      material = standard(mat, { alpha, rim: obj.rim || false });
      material.color = srgb(part.col);
    }
    const mesh = new THREE.Mesh(GEOMETRY[shape], material);
    mesh.matrixAutoUpdate = false;
    mesh.matrix.copy(partMatrix(part, shape));
    addMesh(obj.tag, mesh, obj.castShadow !== false && alpha > 0.5 && mat !== "Neon");
  }
}

function euler(rot = [0, 0, 0]) {
  const d = Math.PI / 180;
  return new THREE.Euler(rot[0] * d, rot[1] * d, rot[2] * d, "YXZ");
}

// 각진 바위: 찌그러진 공 위 무작위 점 → 볼록 껍질
function rockGeometry(seed, count = 14) {
  const r = rng(seed);
  const pts = [];
  for (let i = 0; i < count; i++) {
    const u = r() * 2 - 1;
    const a = r() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const k = 0.75 + r() * 0.25;
    pts.push(new THREE.Vector3(Math.cos(a) * s * k, u * k, Math.sin(a) * s * k).multiplyScalar(0.5));
  }
  // 바닥은 평평하게(땅에 앉게)
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2 + r();
    pts.push(new THREE.Vector3(Math.cos(a) * 0.42, -0.5, Math.sin(a) * 0.42));
  }
  return new ConvexGeometry(pts);
}

// 결정: 육각(또는 5각) 기둥 + 양 끝 뾰족(수정 결정처럼 긴 면이 보임). 위 끝이 더 김
function shardGeometry(seed, sides = 6) {
  const r = rng(seed);
  const pts = [p3((r() - 0.5) * 0.08, 0.5, (r() - 0.5) * 0.08), p3((r() - 0.5) * 0.12, -0.5, (r() - 0.5) * 0.12)];
  const top = 0.12 + r() * 0.12;
  const bottom = -0.22 - r() * 0.1;
  for (let i = 0; i < sides; i++) {
    const a = (i / sides) * Math.PI * 2 + (r() - 0.5) * 0.3;
    const k = 0.4 + r() * 0.12;
    pts.push(p3(Math.cos(a) * k * 0.5, top + (r() - 0.5) * 0.08, Math.sin(a) * k * 0.5));
    pts.push(p3(Math.cos(a) * k * 0.46, bottom + (r() - 0.5) * 0.06, Math.sin(a) * k * 0.46));
  }
  return new ConvexGeometry(pts);
}

function buildRocks(obj) {
  for (const rock of obj.rocks) {
    const material = standard(rock.mat || "Slate", { rim: obj.rim || false, flat: true });
    material.color = srgb(rock.col || [0.6, 0.6, 0.64]);
    const mesh = new THREE.Mesh(rockGeometry(rock.seed || 1, rock.points || 14), material);
    mesh.position.copy(v3(rock.p));
    mesh.rotation.copy(euler(rock.rot));
    mesh.scale.copy(v3(rock.size));
    addMesh(obj.tag, mesh, obj.castShadow !== false);
  }
}

function buildShards(obj) {
  for (const shard of obj.shards) {
    let material;
    if (shard.emissive) {
      material = new THREE.MeshBasicMaterial({ color: srgb(shard.col) });
    } else {
      material = standard(shard.mat || "SmoothPlastic", { rim: obj.rim ?? true, flat: true });
      material.color = srgb(shard.col);
      material.roughness = shard.rough ?? 0.35;
    }
    const mesh = new THREE.Mesh(shardGeometry(shard.seed || 1, shard.sides || 5), material);
    mesh.position.copy(v3(shard.p));
    mesh.rotation.copy(euler(shard.rot));
    const w = shard.radius * 2;
    mesh.scale.set(w, shard.len, w * (shard.flat ?? 0.8));
    addMesh(obj.tag, mesh, obj.castShadow === true);
  }
}

// 띠: 점마다 옆 방향 = 진행 방향 × (바깥 또는 위), 폭·투명도는 점마다
function buildRibbons(obj) {
  for (const rb of obj.ribbons) {
    const pts = rb.points.map(v3);
    const n = pts.length;
    const pos = [];
    const col = [];
    const idx = [];
    const c = srgb(rb.color || [1, 1, 1]);
    for (let i = 0; i < n; i++) {
      const prev = pts[Math.max(0, i - 1)];
      const next = pts[Math.min(n - 1, i + 1)];
      const tan = new THREE.Vector3().subVectors(next, prev).normalize();
      let side;
      if (rb.normal === "up") side = new THREE.Vector3(0, 1, 0);
      else {
        const out = new THREE.Vector3(pts[i].x, 0, pts[i].z).normalize();
        side = new THREE.Vector3().crossVectors(tan, out).normalize();
      }
      const w = (rb.width[i] ?? rb.width[rb.width.length - 1]) / 2;
      const a = rb.alpha[i] ?? rb.alpha[rb.alpha.length - 1];
      const p = pts[i];
      pos.push(p.x + side.x * w, p.y + side.y * w, p.z + side.z * w, p.x - side.x * w, p.y - side.y * w, p.z - side.z * w);
      col.push(c.r, c.g, c.b, a, c.r, c.g, c.b, a);
      if (i + 1 < n) {
        const k = i * 2;
        idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 4));
    g.setIndex(idx);
    const material = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    addMesh(obj.tag, new THREE.Mesh(g, material), false);
  }
}

async function buildQuads(obj) {
  const loader = new THREE.TextureLoader();
  for (const q of obj.quads) {
    const tex = await loader.loadAsync(q.image);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 16;
    const material = new THREE.MeshBasicMaterial({
      map: tex,
      color: srgb(q.color || [1, 1, 1]),
      transparent: true,
      opacity: q.opacity ?? 1,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const g = new THREE.PlaneGeometry(q.size[0], q.size[1]).rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(g, material);
    mesh.position.copy(v3(q.p));
    mesh.rotation.y = ((q.rotY || 0) * Math.PI) / 180;
    mesh.renderOrder = q.order ?? 1;
    addMesh(obj.tag, mesh, false);
  }
}

// 빛 ----------------------------------------------------------------------------------
let sun = null;
function setupLight(L = {}) {
  const sunDir = v3(L.sun || [-0.45, 0.8, -0.55]).normalize();
  sun = new THREE.DirectionalLight(srgb(L.sunColor || [1, 0.97, 0.9]), (L.sunIntensity ?? 1.1) * Math.PI);
  const center = v3(L.shadowCenter || [0, 8, 0]);
  sun.position.copy(center).addScaledVector(sunDir, 200);
  sun.target.position.copy(center);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  sun.shadow.bias = -0.0005;
  sun.shadow.normalBias = 0.04;
  sun.shadow.radius = 4;
  const half = L.shadowBox ?? 30;
  Object.assign(sun.shadow.camera, { left: -half, right: half, top: half, bottom: -half, near: 1, far: 500 });
  sun.shadow.camera.updateProjectionMatrix();
  scene.add(sun, sun.target);
  scene.add(
    new THREE.HemisphereLight(
      srgb(L.hemiSky || [0.85, 0.92, 1]),
      srgb(L.hemiGround || [0.55, 0.62, 0.5]),
      (L.hemiIntensity ?? 0.75) * Math.PI,
    ),
  );
  for (const rim of L.rims || []) {
    const light = new THREE.DirectionalLight(srgb(rim.color), rim.intensity * Math.PI);
    light.position.copy(center).addScaledVector(v3(rim.dir).normalize(), 200);
    light.target.position.copy(center);
    scene.add(light, light.target);
  }
}

// 층 그리기 -------------------------------------------------------------------------------
const depthOnly = new THREE.MeshBasicMaterial({ colorWrite: false });
const shadowOnly = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false });
let layers = [];

async function load(spec) {
  textures = buildMaterialTextures(THREE);
  if (spec.rim) rimSpec = { ...rimSpec, ...spec.rim };
  const [W, H] = spec.size || [1024, 1024];
  renderer.setSize(W, H, false);
  const cam = spec.camera;
  camera = new THREE.PerspectiveCamera(cam.fov || 35, W / H, 0.1, 3000);
  camera.position.copy(v3(cam.eye));
  camera.up.copy(v3(cam.up || [0, 1, 0]));
  camera.lookAt(v3(cam.target));
  if (cam.shift) {
    // 화면에서 물체를 옮김(원근 기울임 없이): 화면 폭·높이 비율만큼
    camera.setViewOffset(W, H, -cam.shift[0] * W, -cam.shift[1] * H, W, H);
  }
  camera.updateProjectionMatrix();
  setupLight(spec.light);
  for (const obj of spec.objects) {
    if (obj.parts) buildParts(obj);
    if (obj.rocks) buildRocks(obj);
    if (obj.shards) buildShards(obj);
    if (obj.ribbons) buildRibbons(obj);
    if (obj.quads) await buildQuads(obj);
  }
  layers = spec.layers;
  return { objects: objects.length, layers: layers.map((l) => l.name) };
}

function render(name) {
  const layer = layers.find((l) => l.name === name);
  if (!layer) throw new Error("no layer " + name);
  const draw = new Set(layer.draw || []);
  const occlude = new Set(layer.occlude || []);
  const shadow = new Set(layer.shadow || []);
  for (const o of objects) {
    const m = o.mesh;
    if (draw.has(o.tag)) {
      m.visible = true;
      m.material = o.material;
      m.castShadow = o.castShadow;
    } else if (occlude.has(o.tag)) {
      m.visible = true;
      m.material = depthOnly;
      m.castShadow = o.castShadow;
    } else if (shadow.has(o.tag)) {
      m.visible = true;
      m.material = shadowOnly;
      m.castShadow = o.castShadow;
    } else {
      m.visible = false;
    }
  }
  renderer.shadowMap.needsUpdate = true;
  renderer.render(scene, camera);
  return canvas.toDataURL("image/png");
}

// 화면 좌표(픽셀)로 3D 점 투영: 합성(파이썬)에서 빛 중심·마법진 위치를 맞출 때
function project(points) {
  const [W, H] = [canvas.width, canvas.height];
  return points.map((p) => {
    const v = v3(p).project(camera);
    return [((v.x + 1) / 2) * W, ((1 - v.y) / 2) * H, v.z];
  });
}

window.store = { load, render, project };
window.storeReady = true;
