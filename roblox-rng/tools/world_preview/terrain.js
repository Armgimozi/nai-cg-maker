// 맵 미리보기: Roblox 지형(Terrain) 그리기 — 매끈한 땅 표면 + 재질 섞임, 물(깊이 색·하늘 반사·물결), 풀 장식.
// 입력: terrain_grid.mjs 가 읽은 덤프 격자(기둥마다 땅 높이·재질·물 윗면), textures.js 의 재질 층.
//
// 땅: 표본(기둥 가운데)을 꼭짓점으로 한 높이 격자 삼각형. 법선은 이웃 높이 차로 매끈하게(Roblox 매끈한 지형처럼 각지지 않게).
//   재질은 삼각형 세 꼭짓점 재질을 무게 중심 좌표로 섞고 잡음으로 경계를 흐트러뜨림(Roblox 도 재질 경계가 한 복셀쯤 섞임).
//   텍스처는 월드 좌표 삼면 투영(가파른 비탈도 늘어나지 않게). 풀 재질은 가파르면 흙빛.
//   한계: 기둥마다 맨 위 표면 하나라서 동굴·아치·튀어나온 절벽 밑면은 안 그려짐
// 물: 물 윗면 높이에 평면. 물 깊이(물 윗면 - 땅 높이)를 꼭짓점마다 넣고, 셰이더가 시선 방향 물속 길이로
//   투과(밑바닥이 비침)·물빛(Terrain.WaterColor)·프레넬 하늘 반사(WaterReflectance)·해 반짝임·물결(WaterWaveSize)을 계산.
//   얕은 물 = 모래가 비쳐서 밝은 청록, 깊은 물 = 물빛 + 반사. 색은 실제 깊이에서만 나옴(동심원 띠 없음)
//   거품: Roblox 물에는 없음. opts.foam 일 때만 얕은 곳에 흰 거품(비교용)
// 풀 장식: Terrain.Decoration = true 이면 Grass 재질 위에 풀잎 다발(카메라 둘레만, 시점마다 새로). 길이 GrassLength

import * as THREE from "three";
import { TERRAIN_MATERIALS } from "./textures.js";

const MAX_MATERIALS = 32;

function srgb(rgb) {
  return new THREE.Color().setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
}

// 셰이더 조각 ---------------------------------------------------------------------------
export const PERTURB_GLSL = `
vec3 texPerturb( vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float faceDir ) {
  vec3 vSigmaX = normalize( dFdx( surf_pos.xyz ) );
  vec3 vSigmaY = normalize( dFdy( surf_pos.xyz ) );
  vec3 R1 = cross( vSigmaY, surf_norm );
  vec3 R2 = cross( surf_norm, vSigmaX );
  float fDet = dot( vSigmaX, R1 ) * faceDir;
  vec3 vGrad = sign( fDet ) * ( dHdxy.x * R1 + dHdxy.y * R2 );
  return normalize( abs( fDet ) * surf_norm - vGrad );
}
`;

// 삼면 투영 한 층 표본(무게 bw, 작은 무게 면은 건너뜀)
export const TRIPLANAR_GLSL = `
vec4 triSample( float layer, float tile, vec3 p, vec3 bw ) {
  vec4 c = vec4( 0.0 );
  float total = 0.0;
  if ( bw.x > 0.03 ) { c += bw.x * texture( uTexArr, vec3( p.zy / tile, layer ) ); total += bw.x; }
  if ( bw.y > 0.03 ) { c += bw.y * texture( uTexArr, vec3( p.xz / tile, layer ) ); total += bw.y; }
  if ( bw.z > 0.03 ) { c += bw.z * texture( uTexArr, vec3( p.xy / tile, layer ) ); total += bw.z; }
  return c / max( total, 1e-4 );
}
`;

function terrainMaterial(grid, tex) {
  const layer = new Array(MAX_MATERIALS).fill(0);
  const tile = new Array(MAX_MATERIALS).fill(8);
  const gain = new Array(MAX_MATERIALS).fill(1);
  const bump = new Array(MAX_MATERIALS).fill(0);
  const grassy = new Array(MAX_MATERIALS).fill(0);
  const color = Array.from({ length: MAX_MATERIALS }, () => new THREE.Vector3(0.5, 0.5, 0.5));
  grid.materials.forEach((name, i) => {
    if (i >= MAX_MATERIALS) return;
    const spec = TERRAIN_MATERIALS[name] || TERRAIN_MATERIALS.Ground;
    layer[i] = tex.layers[spec.layer];
    tile[i] = spec.tile;
    gain[i] = tex.gain[spec.layer];
    bump[i] = spec.bump;
    grassy[i] = spec.grassy || 0;
    const rgb = grid.raw.colors[name];
    if (rgb) {
      const c = srgb(rgb);
      color[i].set(c.r, c.g, c.b);
    }
  });
  const material = new THREE.MeshStandardMaterial({ roughness: 0.92, metalness: 0 });
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, {
      uTexArr: { value: tex.texture },
      uNoiseLayer: { value: tex.layers.noise },
      uLayer: { value: layer },
      uTile: { value: tile },
      uGain: { value: gain },
      uBump: { value: bump },
      uGrassy: { value: grassy },
      uColor: { value: color },
    });
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
attribute vec3 tmat;
attribute vec3 tbary;
varying vec3 vTMat;
varying vec3 vTBary;
varying vec3 vTPos;
varying vec3 vTNrm;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
vTMat = tmat;
vTBary = tbary;
vTPos = position;
vTNrm = normal;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
uniform highp sampler2DArray uTexArr;
uniform float uNoiseLayer;
uniform float uLayer[${MAX_MATERIALS}];
uniform float uTile[${MAX_MATERIALS}];
uniform float uGain[${MAX_MATERIALS}];
uniform float uBump[${MAX_MATERIALS}];
uniform float uGrassy[${MAX_MATERIALS}];
uniform vec3 uColor[${MAX_MATERIALS}];
varying vec3 vTMat;
varying vec3 vTBary;
varying vec3 vTPos;
varying vec3 vTNrm;
${TRIPLANAR_GLSL}
${PERTURB_GLSL}`,
      )
      .replace(
        "#include <map_fragment>",
        `
vec3 tN = normalize( vTNrm );
vec3 bw = pow( abs( tN ), vec3( 4.0 ) );
bw /= ( bw.x + bw.y + bw.z );
ivec3 mi = ivec3( vTMat + 0.5 );
vec3 wts = vTBary;
if ( mi.x == mi.y && mi.y == mi.z ) {
  wts = vec3( 1.0, 0.0, 0.0 );
} else {
  // 섞임 경계를 잡음으로 흐트러뜨림
  vec3 jitter = vec3(
    texture( uTexArr, vec3( vTPos.xz / 11.0, uNoiseLayer ) ).g,
    texture( uTexArr, vec3( vTPos.xz / 11.0 + vec2( 0.37, 0.11 ), uNoiseLayer ) ).g,
    texture( uTexArr, vec3( vTPos.xz / 11.0 + vec2( 0.71, 0.53 ), uNoiseLayer ) ).g ) - 0.5;
  wts = max( vTBary + jitter * 0.8, vec3( 0.001 ) );
  wts = wts * wts * wts;
  wts /= ( wts.x + wts.y + wts.z );
}
vec3 albedo = vec3( 0.0 );
float texHeight = 0.0;
float texBump = 0.0;
for ( int k = 0; k < 3; k++ ) {
  float w = wts[ k ];
  if ( w < 0.01 ) continue;
  int m = mi[ k ];
  vec4 s = triSample( uLayer[ m ], uTile[ m ], vTPos, bw );
  vec3 c = s.rgb * uGain[ m ] * uColor[ m ];
  float steep = smoothstep( 0.8, 0.5, tN.y ) * uGrassy[ m ];
  c *= mix( vec3( 1.0 ), vec3( 0.8, 0.7, 0.52 ), steep );
  albedo += w * c;
  texHeight += w * s.a;
  texBump += w * uBump[ m ];
}
vec4 macro = texture( uTexArr, vec3( vTPos.xz / 97.0, uNoiseLayer ) );
vec4 macro2 = texture( uTexArr, vec3( vTPos.xz / 331.0, uNoiseLayer ) );
albedo *= 0.88 + 0.2 * macro.r + 0.1 * ( macro2.g - 0.5 );
diffuseColor.rgb *= albedo;
`,
      )
      .replace(
        "#include <normal_fragment_maps>",
        `#include <normal_fragment_maps>
normal = texPerturb( - vViewPosition, normal, vec2( dFdx( texHeight ), dFdy( texHeight ) ) * texBump, faceDirection );`,
      );
  };
  material.customProgramCacheKey = () => "terrain-solid";
  return material;
}

function waterMaterial(tex, env, props) {
  const uniforms = THREE.UniformsUtils.merge([
    THREE.UniformsLib.fog,
    {
      uTexArr: { value: null },
      uNoiseLayer: { value: 0 },
      uWaterColor: { value: new THREE.Color() },
      uTransparency: { value: 0.3 },
      uReflectance: { value: 1 },
      uWaveSize: { value: 0.15 },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uSunColor: { value: new THREE.Color(1, 1, 1) },
      uAmbient: { value: new THREE.Color(0.5, 0.5, 0.5) },
      uZenith: { value: new THREE.Color() },
      uHorizon: { value: new THREE.Color() },
      uFoam: { value: 0 },
    },
  ]);
  uniforms.uTexArr.value = tex.texture;
  uniforms.uNoiseLayer.value = tex.layers.noise;
  uniforms.uWaterColor.value = srgb(props.WaterColor || [12 / 255, 84 / 255, 92 / 255]);
  uniforms.uTransparency.value = props.WaterTransparency ?? 0.3;
  uniforms.uReflectance.value = props.WaterReflectance ?? 1;
  uniforms.uWaveSize.value = props.WaterWaveSize ?? 0.15;
  uniforms.uSunDir.value.copy(env.sunDir);
  uniforms.uSunColor.value.copy(env.sunColor);
  uniforms.uAmbient.value.copy(env.ambient);
  uniforms.uZenith.value.copy(env.zenith);
  uniforms.uHorizon.value.copy(env.horizon);
  uniforms.uFoam.value = env.foam ? 1 : 0;
  return new THREE.ShaderMaterial({
    uniforms,
    transparent: true,
    depthWrite: false,
    fog: true,
    vertexShader: `
attribute float depth;
varying float vDepth;
varying vec3 vWorld;
#include <fog_pars_vertex>
void main() {
  vDepth = depth;
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  vWorld = wp.xyz;
  vec4 mvPosition = viewMatrix * wp;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`,
    fragmentShader: `
uniform highp sampler2DArray uTexArr;
uniform float uNoiseLayer;
uniform vec3 uWaterColor;
uniform float uTransparency;
uniform float uReflectance;
uniform float uWaveSize;
uniform vec3 uSunDir;
uniform vec3 uSunColor;
uniform vec3 uAmbient;
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform float uFoam;
varying float vDepth;
varying vec3 vWorld;
#include <common>
#include <fog_pars_fragment>

vec3 skyColor( vec3 d ) {
  vec3 c = mix( uHorizon, uZenith, pow( max( d.y, 0.0 ), 0.55 ) );
  float s = max( dot( d, normalize( uSunDir ) ), 0.0 );
  return c + vec3( 1.0, 0.95, 0.85 ) * pow( s, 12.0 ) * 0.12;
}
float waveH( vec2 p ) {
  float h = texture( uTexArr, vec3( p / 43.0, uNoiseLayer ) ).b * 0.55;
  h += texture( uTexArr, vec3( mat2( 0.8, -0.6, 0.6, 0.8 ) * p / 17.0, uNoiseLayer ) ).a * 0.3;
  h += texture( uTexArr, vec3( mat2( 0.6, 0.8, -0.8, 0.6 ) * p / 6.5, uNoiseLayer ) ).b * 0.15;
  return h;
}
void main() {
  if ( vDepth <= 0.01 ) discard;
  vec3 V = normalize( cameraPosition - vWorld );
  float e = 0.35;
  float h0 = waveH( vWorld.xz );
  float hx = waveH( vWorld.xz + vec2( e, 0.0 ) );
  float hz = waveH( vWorld.xz + vec2( 0.0, e ) );
  float amp = uWaveSize * 9.0;
  vec3 N = normalize( vec3( -( hx - h0 ) / e * amp, 1.0, -( hz - h0 ) / e * amp ) );
  float cosV = clamp( dot( N, V ), 0.0, 1.0 );
  float F = ( 0.02 + 0.98 * pow( 1.0 - cosV, 5.0 ) ) * uReflectance;
  vec3 R = reflect( -V, N );
  R.y = abs( R.y );
  vec3 refl = skyColor( R );
  vec3 L = normalize( uSunDir );
  float sd = max( dot( R, L ), 0.0 );
  vec3 spec = uSunColor * ( pow( sd, 600.0 ) * 5.0 + pow( sd, 60.0 ) * 0.18 ) * uReflectance;
  // 물속 빛: 물빛(WaterColor) 을 하늘빛 + 햇빛으로
  vec3 body = uWaterColor * ( uAmbient + uSunColor * max( L.y, 0.0 ) * 0.55 );
  // 시선이 물속을 지나는 길이(굴절) → 투과율
  float sinI2 = 1.0 - cosV * cosV;
  float cosT = sqrt( max( 1.0 - sinI2 / 1.77, 0.05 ) );
  float path = vDepth / cosT;
  float k = 0.35 * ( 1.0 - uTransparency ) + 0.03;
  float T = exp( -path * k );
  vec3 color = body * ( 1.0 - T ) * ( 1.0 - F ) + refl * F + spec;
  float alpha = 1.0 - T * ( 1.0 - F );
  if ( uFoam > 0.5 ) {
    float n = texture( uTexArr, vec3( vWorld.xz / 7.0, uNoiseLayer ) ).g;
    float foam = smoothstep( 1.4, 0.2, vDepth ) * smoothstep( 0.35, 0.6, n + 0.3 * smoothstep( 0.8, 0.1, vDepth ) );
    color = mix( color, vec3( 0.95 ) * ( uAmbient + uSunColor * max( L.y, 0.0 ) * 0.6 ), foam );
    alpha = max( alpha, foam * 0.9 );
  }
  gl_FragColor = vec4( color / max( alpha, 1e-3 ), alpha );
  #include <fog_fragment>
  #include <colorspace_fragment>
}`,
  });
}

// 격자 → 삼각형 ----------------------------------------------------------------------------
function upward(ax, ay, az, bx, by, bz, cx, cy, cz) {
  // (b - a) x (c - a) 의 y 성분 > 0 이면 위를 봄
  return (bz - az) * (cx - ax) - (bx - ax) * (cz - az) > 0;
}

export function buildTerrain(grid, tex, env) {
  const stats = { triangles: 0, waterTriangles: 0, tiles: grid.tiles.size };
  const pos = [];
  const nrm = [];
  const tmat = [];
  const tbary = [];
  const wpos = [];
  const wdepth = [];

  // 표본마다 법선(이웃 높이 차) — 타일/coarse 경계에서도 같은 값이 되도록 heightAt 으로
  function normalsOf(g) {
    const out = new Float32Array(g.nx * g.nz * 3);
    const e = 2;
    for (let j = 0; j < g.nz; j++) {
      for (let i = 0; i < g.nx; i++) {
        const x = g.xs[i];
        const z = g.zs[j];
        const h = g.h[j * g.nx + i];
        let hx0 = grid.heightAt(x - e, z);
        let hx1 = grid.heightAt(x + e, z);
        let hz0 = grid.heightAt(x, z - e);
        let hz1 = grid.heightAt(x, z + e);
        if (Number.isNaN(hx0)) hx0 = h;
        if (Number.isNaN(hx1)) hx1 = h;
        if (Number.isNaN(hz0)) hz0 = h;
        if (Number.isNaN(hz1)) hz1 = h;
        const v = new THREE.Vector3(-(hx1 - hx0) / (2 * e), 1, -(hz1 - hz0) / (2 * e)).normalize();
        out.set([v.x, v.y, v.z], (j * g.nx + i) * 3);
      }
    }
    return out;
  }

  function addGrid(g, skip) {
    const normals = normalsOf(g);
    const P = (k) => [g.xs[k % g.nx], g.h[k], g.zs[Math.floor(k / g.nx)]];
    const tri = (a, b, c) => {
      let [pa, pb, pc] = [P(a), P(b), P(c)];
      if (!upward(...pa, ...pb, ...pc)) {
        [b, c] = [c, b];
        [pb, pc] = [pc, pb];
      }
      const mats = [g.m[a], g.m[b], g.m[c]];
      [
        [a, pa, [1, 0, 0]],
        [b, pb, [0, 1, 0]],
        [c, pc, [0, 0, 1]],
      ].forEach(([k, p, bary]) => {
        pos.push(p[0], p[1], p[2]);
        nrm.push(normals[k * 3], normals[k * 3 + 1], normals[k * 3 + 2]);
        tmat.push(mats[0], mats[1], mats[2]);
        tbary.push(bary[0], bary[1], bary[2]);
      });
      stats.triangles++;
    };
    for (let j = 0; j < g.nz - 1; j++) {
      for (let i = 0; i < g.nx - 1; i++) {
        if (skip && skip(i, j)) continue;
        const k00 = j * g.nx + i;
        const k10 = k00 + 1;
        const k01 = k00 + g.nx;
        const k11 = k01 + 1;
        const valid = [k00, k10, k01, k11].filter((k) => !Number.isNaN(g.h[k]));
        if (valid.length === 4) {
          if (Math.abs(g.h[k00] - g.h[k11]) <= Math.abs(g.h[k10] - g.h[k01])) {
            tri(k00, k01, k11);
            tri(k00, k11, k10);
          } else {
            tri(k00, k01, k10);
            tri(k10, k01, k11);
          }
        } else if (valid.length === 3) {
          tri(valid[0], valid[1], valid[2]);
        }
        // 물: 한 모서리라도 물이 있으면 칸 전체에 물 평면(없는 모서리는 있는 값 중 가장 높은 것)
        const ks = [k00, k10, k11, k01];
        const ws = ks.map((k) => g.w[k]);
        const present = ws.filter((w) => !Number.isNaN(w));
        if (present.length > 0) {
          const top = Math.max(...present);
          const quad = ks.map((k, n) => {
            const w = Number.isNaN(ws[n]) ? top : ws[n];
            let depth;
            if (!Number.isNaN(g.h[k])) depth = w - g.h[k];
            else if (!Number.isNaN(g.b[k])) depth = w - g.b[k];
            else depth = 60;
            return [g.xs[k % g.nx], w, g.zs[Math.floor(k / g.nx)], depth];
          });
          for (const [a, b, c] of [
            [0, 3, 2],
            [0, 2, 1],
          ]) {
            for (const n of [a, b, c]) {
              wpos.push(quad[n][0], quad[n][1], quad[n][2]);
              wdepth.push(quad[n][3]);
            }
            stats.waterTriangles++;
          }
        }
      }
    }
  }

  const coarse = grid.coarse;
  addGrid(coarse, (i, j) => grid.hasTile(coarse.cx0 + i, coarse.cz0 + j));
  for (const tile of grid.tiles.values()) addGrid(tile, null);

  const group = new THREE.Group();
  if (pos.length > 0) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    geometry.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3));
    geometry.setAttribute("tmat", new THREE.Float32BufferAttribute(tmat, 3));
    geometry.setAttribute("tbary", new THREE.Float32BufferAttribute(tbary, 3));
    const mesh = new THREE.Mesh(geometry, terrainMaterial(grid, tex));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
    group.add(mesh);
  }
  if (wpos.length > 0) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(wpos, 3));
    geometry.setAttribute("depth", new THREE.Float32BufferAttribute(wdepth, 1));
    const mesh = new THREE.Mesh(geometry, waterMaterial(tex, env, grid.raw.props || {}));
    mesh.frustumCulled = false;
    mesh.renderOrder = 1;
    group.add(mesh);
  }

  // 풀 장식 ---------------------------------------------------------------------------
  const props = grid.raw.props || {};
  const grassIndex = grid.materials.indexOf("Grass");
  let grassMesh = null;
  const grassColor = srgb(grid.raw.colors.Grass || [0.42, 0.5, 0.25]);
  const tuft = (() => {
    const p = [];
    const c = [];
    for (let k = 0; k < 3; k++) {
      const a = (k / 3) * Math.PI + 0.3;
      const ca = Math.cos(a);
      const sa = Math.sin(a);
      const lean = 0.18 * (k - 1);
      // 잎 하나 = 아래 두 점 + 위 한 점(조금 기울게)
      const blade = [
        [-0.09, 0, 0],
        [0.09, 0, 0],
        [lean, 1, 0.12],
      ];
      for (const [x, y, z] of blade) {
        p.push(x * ca - z * sa, y, x * sa + z * ca);
        const shade = 0.62 + 0.5 * y;
        c.push(shade, shade, shade);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(c, 3));
    g.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(p.length).fill(0).map((_, n) => (n % 3 === 1 ? 1 : 0)), 3));
    return g;
  })();
  const grassMaterial = new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide });

  // 카메라가 땅 가까이 있으면 카메라 앞 둘레(반지름 radius)에 풀 다발. Roblox 도 풀 장식은 가까운 곳만 그림
  function updateGrass(camera, scene) {
    if (grassMesh) {
      scene.remove(grassMesh);
      grassMesh.dispose();
      grassMesh = null;
    }
    if (!props.Decoration || grassIndex < 0) return 0;
    const eye = camera.position;
    const ground = grid.heightAt(eye.x, eye.z);
    if (!Number.isNaN(ground) && eye.y - ground > 120) return 0;
    if (camera.isOrthographicCamera) return 0;
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    if (forward.lengthSq() > 1e-6) forward.normalize();
    const center = eye.clone().addScaledVector(forward, 45);
    const radius = 75;
    const spacing = 0.85;
    const length = 2.4 * (props.GrassLength ?? 0.7);
    const items = [];
    let seed = 1;
    const rand = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed / 4294967296;
    };
    for (let z = center.z - radius; z < center.z + radius; z += spacing) {
      for (let x = center.x - radius; x < center.x + radius; x += spacing) {
        const px = x + (rand() - 0.5) * spacing;
        const pz = z + (rand() - 0.5) * spacing;
        const r1 = rand();
        const r2 = rand();
        const r3 = rand();
        if ((px - center.x) ** 2 + (pz - center.z) ** 2 > radius * radius) continue;
        if (grid.materialWeight(px, pz, "Grass") < 0.6) continue;
        const h = grid.heightAt(px, pz);
        if (Number.isNaN(h)) continue;
        const w = grid.waterAt(px, pz);
        if (!Number.isNaN(w) && w > h - 0.2) continue;
        const slope = Math.abs(grid.heightAt(px + 1, pz) - grid.heightAt(px - 1, pz)) + Math.abs(grid.heightAt(px, pz + 1) - grid.heightAt(px, pz - 1));
        if (!(slope < 1.6)) continue;
        items.push([px, h - 0.05, pz, r1 * Math.PI * 2, length * (0.65 + 0.5 * r2), 0.86 + 0.28 * r3]);
      }
    }
    if (items.length === 0) return 0;
    grassMesh = new THREE.InstancedMesh(tuft, grassMaterial, items.length);
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    items.forEach(([x, y, z, yaw, len, tone], n) => {
      q.setFromAxisAngle(up, yaw);
      s.set(len * 0.9, len, len * 0.9);
      m.compose(new THREE.Vector3(x, y, z), q, s);
      grassMesh.setMatrixAt(n, m);
      grassMesh.setColorAt(n, grassColor.clone().multiplyScalar(tone));
    });
    grassMesh.instanceMatrix.needsUpdate = true;
    grassMesh.instanceColor.needsUpdate = true;
    grassMesh.receiveShadow = true;
    grassMesh.castShadow = false;
    grassMesh.frustumCulled = false;
    scene.add(grassMesh);
    return items.length;
  }

  return { group, stats, updateGrass };
}
