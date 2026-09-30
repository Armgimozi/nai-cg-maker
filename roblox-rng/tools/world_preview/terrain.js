// 맵 미리보기: Roblox 지형(Terrain) 그리기 — 매끈한 땅 표면 + 재질 섞임, 물(깊이 색·하늘 반사·물결), 풀 장식.
// 입력: terrain_grid.mjs 가 읽은 덤프 격자(기둥마다 땅 높이·재질·물 윗면), textures.js 의 재질 층.
//
// 땅: 표본(기둥 가운데)을 꼭짓점으로 한 높이 격자 삼각형. 법선은 이웃 높이 차로 매끈하게(Roblox 매끈한 지형처럼 각지지 않게).
//   재질: 기둥마다 재질 번호를 담은 작은 텍스처(4 스터드 = 1 텍셀)를 셰이더가 읽어서, 둘레 네 기둥 재질을 쌍선형 무게로 섞음.
//   위치를 잡음으로 조금 흔들고(경계가 격자 계단이 아니라 구불구불) 재질 무늬 높이(A)로 경계를 가름(Roblox 재질 섞임처럼
//   풀이 모래 쪽으로 삐죽삐죽). 같은 위치는 어느 삼각형에서 봐도 같은 값이라 삼각형 모양 조각이 안 생김.
//   텍스처는 월드 좌표 삼면 투영(가파른 비탈도 늘어나지 않게). 풀 재질은 가파르면 흙빛(Roblox 풀 옆면 무늬 흉내).
//   한계: 기둥마다 맨 위 표면 하나라서 동굴·아치·튀어나온 절벽 밑면은 안 그려짐
// 물: 물 윗면 높이에 평면. 장면(물 빼고)을 먼저 색·깊이 텍스처로 그려 두고(scene.js), 물 셰이더가 화면 위치마다
//   "물 표면 → 그 뒤 물체(모래 바닥, 기둥 ...)" 까지 시선이 물속을 지나는 길이로 색을 정함:
//   바닥색 × 투과율(채널마다 다름: 빨강이 먼저 빠져서 얕은 물 = 모래가 비치는 청록) + 물빛(Terrain.WaterColor) 산란
//   + 프레넬 하늘 반사(WaterReflectance) + 해 반짝임 + 물결 법선(WaterWaveSize) + 살짝 굴절(물결 따라 바닥이 일렁임).
//   얕은 물 = 바닥이 비치는 밝은 청록, 깊은 물 = 물빛 + 반사. 색은 실제 깊이에서만 나옴(동심원 띠 없음).
//   WaterTransparency 가 클수록 깊이 비침(1 이면 거의 맑음).
//   거품: Roblox 지형 물에는 물가 거품이 없음. opts.foam 일 때만 얕은 곳에 흰 거품(비교용)
// 풀 장식: Terrain.Decoration = true 이면 Grass 재질(LeafyGrass 등 다른 재질은 X, Roblox 와 같음) 위에 가는 풀잎.
//   길이 ≈ GrassLength × 1.3 스터드, 끝이 밝고 뿌리는 땅색. 카메라 가까이만(60~100 스터드에서 짧아지며 사라짐)

import * as THREE from "three";
import { TERRAIN_MATERIALS } from "./textures.js";

const MAX_MATERIALS = 32;
const NO_MATERIAL = 255;

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

// 기둥 재질 텍스처: 지형 경계 상자 전체, 텍셀 하나 = 기둥 하나(4 스터드, 아주 크면 8/16). 값 = 재질 번호(없으면 255)
function materialIndexTexture(grid) {
  const [minX, , minZ, maxX, , maxZ] = grid.bounds;
  let step = 4;
  while ((maxX - minX) / step > 2048 || (maxZ - minZ) / step > 2048) step *= 2;
  const w = Math.max(1, Math.ceil((maxX - minX) / step));
  const h = Math.max(1, Math.ceil((maxZ - minZ) / step));
  const ox = minX + 2; // 텍셀 (0, 0) 가운데 = 첫 기둥 가운데
  const oz = minZ + 2;
  const data = new Uint8Array(w * h).fill(NO_MATERIAL);
  // coarse(32 스터드 표본): 가장 가까운 표본
  const c = grid.coarse;
  const nearest = (xs, v) => {
    let best = 0;
    for (let i = 1; i < xs.length; i++) if (Math.abs(xs[i] - v) < Math.abs(xs[best] - v)) best = i;
    return best;
  };
  const ci = new Int32Array(w);
  for (let u = 0; u < w; u++) ci[u] = nearest(c.xs, ox + u * step);
  for (let v = 0; v < h; v++) {
    const j = nearest(c.zs, oz + v * step);
    for (let u = 0; u < w; u++) {
      const k = j * c.nx + ci[u];
      if (!Number.isNaN(c.h[k])) data[v * w + u] = c.m[k];
    }
  }
  // 자세한 타일: 표본 간격(dump step) 칸을 그 표본 재질로
  const ts = grid.raw.step || 4;
  for (const g of grid.tiles.values()) {
    for (let j = 0; j < g.nz; j++) {
      for (let i = 0; i < g.nx; i++) {
        const k = j * g.nx + i;
        const value = Number.isNaN(g.h[k]) ? NO_MATERIAL : g.m[k];
        const u0 = Math.round((g.xs[i] - ox) / step);
        const v0 = Math.round((g.zs[j] - oz) / step);
        const span = Math.max(1, Math.round(ts / step));
        for (let dv = 0; dv < span; dv++) {
          for (let du = 0; du < span; du++) {
            const u = u0 + du;
            const v = v0 + dv;
            if (u >= 0 && u < w && v >= 0 && v < h) data[v * w + u] = value;
          }
        }
      }
    }
  }
  // 빈 텍셀(지형 없음)을 이웃 재질로 몇 칸 메움: 물가·섬 끝 삼각형이 빈 칸을 읽어도 색이 있게
  for (let pass = 0; pass < 3; pass++) {
    const copy = data.slice();
    for (let v = 0; v < h; v++) {
      for (let u = 0; u < w; u++) {
        if (copy[v * w + u] !== NO_MATERIAL) continue;
        for (const [du, dv] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const uu = u + du;
          const vv = v + dv;
          if (uu >= 0 && uu < w && vv >= 0 && vv < h && copy[vv * w + uu] !== NO_MATERIAL) {
            data[v * w + u] = copy[vv * w + uu];
            break;
          }
        }
      }
    }
  }
  const texture = new THREE.DataTexture(data, w, h, THREE.RedFormat, THREE.UnsignedByteType);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.generateMipmaps = false;
  texture.colorSpace = THREE.NoColorSpace;
  texture.needsUpdate = true;
  return { texture, origin: new THREE.Vector2(ox, oz), step, size: new THREE.Vector2(w, h) };
}

// 재질 점검용 가짜 색(선형): 이름별로 뚜렷하게
const DEBUG_COLORS = {
  Grass: [0.1, 0.8, 0.1],
  LeafyGrass: [0.0, 0.35, 0.9],
  Sand: [1.0, 0.85, 0.2],
  Rock: [0.5, 0.5, 0.5],
  Slate: [0.25, 0.25, 0.35],
  Basalt: [0.05, 0.05, 0.05],
  Ground: [0.55, 0.3, 0.1],
  Mud: [0.3, 0.15, 0.05],
  Salt: [1.0, 1.0, 1.0],
  Pavement: [0.8, 0.2, 0.9],
  Cobblestone: [0.9, 0.4, 0.1],
  Brick: [0.9, 0.05, 0.05],
  WoodPlanks: [0.6, 0.45, 0.25],
  Limestone: [0.95, 0.9, 0.7],
  Sandstone: [0.8, 0.5, 0.3],
  Snow: [0.8, 0.95, 1.0],
};

function terrainMaterial(grid, tex, debug) {
  const debugColors = grid.materials.map((name, i) => {
    const c = DEBUG_COLORS[name] || [((i * 97) % 255) / 255, ((i * 57) % 255) / 255, ((i * 31) % 255) / 255];
    return new THREE.Vector3(...c);
  });
  while (debugColors.length < MAX_MATERIALS) debugColors.push(new THREE.Vector3(1, 0, 1));
  debugColors.length = MAX_MATERIALS;
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
  const mat = materialIndexTexture(grid);
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
      uMatTex: { value: mat.texture },
      uMatOrigin: { value: mat.origin },
      uMatStep: { value: mat.step },
      uMatSize: { value: mat.size },
      uDebug: { value: debug ? 1 : 0 },
      uDebugColor: { value: debugColors },
    });
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
varying vec3 vTPos;
varying vec3 vTNrm;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
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
uniform sampler2D uMatTex;
uniform vec2 uMatOrigin;
uniform float uMatStep;
uniform vec2 uMatSize;
uniform float uDebug;
uniform vec3 uDebugColor[${MAX_MATERIALS}];
varying vec3 vTPos;
varying vec3 vTNrm;
${TRIPLANAR_GLSL}
${PERTURB_GLSL}
int matAt( ivec2 c ) {
  c = clamp( c, ivec2( 0 ), ivec2( uMatSize ) - 1 );
  return int( texelFetch( uMatTex, c, 0 ).r * 255.0 + 0.5 );
}`,
      )
      .replace(
        "#include <map_fragment>",
        `
vec3 tN = normalize( vTNrm );
vec3 bw = pow( abs( tN ), vec3( 4.0 ) );
bw /= ( bw.x + bw.y + bw.z );
// 재질 경계: 위치를 두 크기 잡음으로 흔든 뒤 둘레 네 기둥 재질을 쌍선형으로
vec2 q = vTPos.xz;
vec2 warp = vec2(
  texture( uTexArr, vec3( q / 31.0, uNoiseLayer ) ).g,
  texture( uTexArr, vec3( q / 31.0 + vec2( 0.43, 0.17 ), uNoiseLayer ) ).g ) - 0.5;
warp += 0.6 * ( vec2(
  texture( uTexArr, vec3( q / 9.0, uNoiseLayer ) ).b,
  texture( uTexArr, vec3( q / 9.0 + vec2( 0.61, 0.29 ), uNoiseLayer ) ).b ) - 0.5 );
vec2 f = ( q + warp * 4.5 - uMatOrigin ) / uMatStep;
vec2 fl = floor( f );
vec2 ft = f - fl;
ivec2 c0 = ivec2( fl );
int mk[ 4 ];
float wk[ 4 ];
mk[ 0 ] = matAt( c0 );
mk[ 1 ] = matAt( c0 + ivec2( 1, 0 ) );
mk[ 2 ] = matAt( c0 + ivec2( 0, 1 ) );
mk[ 3 ] = matAt( c0 + ivec2( 1, 1 ) );
wk[ 0 ] = ( 1.0 - ft.x ) * ( 1.0 - ft.y );
wk[ 1 ] = ft.x * ( 1.0 - ft.y );
wk[ 2 ] = ( 1.0 - ft.x ) * ft.y;
wk[ 3 ] = ft.x * ft.y;
for ( int a = 0; a < 4; a++ ) {
  if ( mk[ a ] >= ${NO_MATERIAL} || mk[ a ] >= ${MAX_MATERIALS} ) wk[ a ] = 0.0;
}
for ( int a = 1; a < 4; a++ ) {
  for ( int b = 0; b < a; b++ ) {
    if ( wk[ a ] > 0.0 && wk[ b ] > 0.0 && mk[ a ] == mk[ b ] ) {
      wk[ b ] += wk[ a ];
      wk[ a ] = 0.0;
    }
  }
}
float wsum = wk[ 0 ] + wk[ 1 ] + wk[ 2 ] + wk[ 3 ];
vec4 smp[ 4 ];
float sc[ 4 ];
float scTotal = 0.0;
for ( int a = 0; a < 4; a++ ) {
  sc[ a ] = 0.0;
  smp[ a ] = vec4( 0.5 );
  if ( wk[ a ] <= 0.0 ) continue;
  float w = wk[ a ] / max( wsum, 1e-4 );
  int m = mk[ a ];
  smp[ a ] = triSample( uLayer[ m ], uTile[ m ], vTPos, bw );
  // 무늬 높이가 높은 재질이 경계에서 이김(0.5 무게 근처에서만 영향)
  float s = w + 1.4 * ( smp[ a ].a - 0.5 ) * w * ( 1.0 - w );
  s = max( s, 0.0 );
  sc[ a ] = s * s * s;
  scTotal += sc[ a ];
}
vec3 albedo = vec3( 0.0 );
float texHeight = 0.0;
float texBump = 0.0;
if ( scTotal <= 0.0 ) {
  albedo = vec3( 0.45, 0.42, 0.36 );
} else {
  for ( int a = 0; a < 4; a++ ) {
    if ( sc[ a ] <= 0.0 ) continue;
    float w = sc[ a ] / scTotal;
    int m = mk[ a ];
    vec3 c = smp[ a ].rgb * uGain[ m ] * uColor[ m ];
    float steep = smoothstep( 0.8, 0.5, tN.y ) * uGrassy[ m ];
    c *= mix( vec3( 1.0 ), vec3( 0.8, 0.7, 0.52 ), steep );
    albedo += w * c;
    texHeight += w * smp[ a ].a;
    texBump += w * uBump[ m ];
  }
}
vec4 macro = texture( uTexArr, vec3( vTPos.xz / 97.0, uNoiseLayer ) );
vec4 macro2 = texture( uTexArr, vec3( vTPos.xz / 331.0, uNoiseLayer ) );
albedo *= 0.9 + 0.16 * macro.r + 0.1 * ( macro2.g - 0.5 );
if ( uDebug > 0.5 ) {
  // 재질 점검용 가짜 색(TERRAIN_DEBUG=1): 가장 무게가 큰 재질 하나
  int best = 0;
  for ( int a = 1; a < 4; a++ ) if ( sc[ a ] > sc[ best ] ) best = a;
  albedo = scTotal > 0.0 ? uDebugColor[ mk[ best ] ] : vec3( 1.0, 0.0, 1.0 );
  texBump = 0.0;
}
diffuseColor.rgb *= albedo;
`,
      )
      .replace(
        "#include <normal_fragment_maps>",
        `#include <normal_fragment_maps>
normal = texPerturb( - vViewPosition, normal, vec2( dFdx( texHeight ), dFdy( texHeight ) ) * texBump, faceDirection );`,
      );
  };
  material.customProgramCacheKey = () => "terrain-solid-v3";
  return material;
}

// 물: 장면 색·깊이 텍스처(물 빼고 먼저 그린 것)를 읽어 물속 길이로 색을 정함. 결과는 불투명(바닥색이 이미 들어 있음)
function waterMaterial(tex, env, props) {
  const uniforms = THREE.UniformsUtils.merge([
    THREE.UniformsLib.fog,
    {
      uTexArr: { value: null },
      uNoiseLayer: { value: 0 },
      uSceneColor: { value: null },
      uSceneDepth: { value: null },
      uResolution: { value: new THREE.Vector2(1, 1) },
      uProjInv: { value: new THREE.Matrix4() },
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
    fog: true,
    vertexShader: `
attribute float depth;
varying float vDepth;
varying vec3 vWorld;
varying vec3 vView;
#include <fog_pars_vertex>
void main() {
  vDepth = depth;
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  vWorld = wp.xyz;
  vec4 mvPosition = viewMatrix * wp;
  vView = mvPosition.xyz;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`,
    fragmentShader: `
uniform highp sampler2DArray uTexArr;
uniform float uNoiseLayer;
uniform sampler2D uSceneColor;
uniform sampler2D uSceneDepth;
uniform vec2 uResolution;
uniform mat4 uProjInv;
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
varying vec3 vView;
#include <common>
#include <fog_pars_fragment>

vec3 skyColor( vec3 d ) {
  vec3 c = mix( uHorizon, uZenith, pow( max( d.y, 0.0 ), 0.55 ) );
  float s = max( dot( d, normalize( uSunDir ) ), 0.0 );
  return c + vec3( 1.0, 0.95, 0.85 ) * pow( s, 12.0 ) * 0.12;
}
float waveH( vec2 p ) {
  float h = texture( uTexArr, vec3( p / 43.0, uNoiseLayer ) ).b * 0.5;
  h += texture( uTexArr, vec3( mat2( 0.8, -0.6, 0.6, 0.8 ) * p / 17.0, uNoiseLayer ) ).a * 0.32;
  h += texture( uTexArr, vec3( mat2( 0.6, 0.8, -0.8, 0.6 ) * p / 7.0, uNoiseLayer ) ).b * 0.18;
  return h;
}
// 화면 위치 uv 의 장면 점까지 거리(원근: 눈에서의 거리, 직교: 시선 방향 깊이). 하늘이면 아주 큼
float sceneDistance( vec2 uv ) {
  float d = texture( uSceneDepth, uv ).r;
  if ( d >= 0.99999 ) return 1e6;
  vec4 p = uProjInv * vec4( uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0 );
  p.xyz /= p.w;
  return isOrthographic ? - p.z : length( p.xyz );
}
void main() {
  if ( vDepth < 0.0 ) discard; // 물가 너머(땅이 물 윗면보다 높음)
  vec2 uv = gl_FragCoord.xy / uResolution;
  float sceneD = texture( uSceneDepth, uv ).r;
  if ( gl_FragCoord.z > sceneD + 1e-6 ) discard; // 물 앞에 있는 것(부두 바닥, 땅)에 가려짐
  float surfDist = isOrthographic ? - vView.z : length( vView );
  vec3 V = isOrthographic ? normalize( vec3( viewMatrix[ 0 ][ 2 ], viewMatrix[ 1 ][ 2 ], viewMatrix[ 2 ][ 2 ] ) ) : normalize( cameraPosition - vWorld );

  // 물결 법선
  float e = 0.35;
  float h0 = waveH( vWorld.xz );
  float hx = waveH( vWorld.xz + vec2( e, 0.0 ) );
  float hz = waveH( vWorld.xz + vec2( 0.0, e ) );
  float amp = uWaveSize * 9.0;
  vec3 N = normalize( vec3( - ( hx - h0 ) / e * amp, 1.0, - ( hz - h0 ) / e * amp ) );

  // 굴절: 물결 따라 바닥 표본 위치를 살짝 옮김(옮긴 곳이 물 앞 물체면 원래 자리)
  float path = max( sceneDistance( uv ) - surfDist, 0.0 );
  vec2 uv2 = uv + N.xz * 0.018 * clamp( path / 6.0, 0.0, 1.0 ) * ( isOrthographic ? 0.3 : 1.0 );
  float path2 = sceneDistance( uv2 ) - surfDist;
  if ( path2 > 0.0 ) {
    uv = uv2;
    path = path2;
  }
  vec3 bottom = texture( uSceneColor, uv ).rgb;

  float cosV = clamp( dot( N, V ), 0.0, 1.0 );
  float F = ( 0.02 + 0.98 * pow( 1.0 - cosV, 5.0 ) ) * uReflectance;
  vec3 R = reflect( - V, N );
  R.y = abs( R.y );
  vec3 refl = skyColor( R );
  vec3 L = normalize( uSunDir );
  float sd = max( dot( R, L ), 0.0 );
  vec3 spec = uSunColor * ( pow( sd, 500.0 ) * 1.3 + pow( sd, 60.0 ) * 0.08 ) * uReflectance;

  // 물속: 빛이 지나는 길이 path 만큼 채널별로 줄어듦(물빛이 약한 채널일수록 빨리). 줄어든 만큼 물빛 산란
  // 채널별 흡수: 물빛에서 약한 채널(보통 빨강)일수록 빨리 → 얕은 물도 바닥이 청록으로 물듦
  float ext = 0.35 * ( 1.0 - uTransparency ) + 0.03;
  vec3 wcn = uWaterColor / max( max( uWaterColor.r, max( uWaterColor.g, uWaterColor.b ) ), 1e-3 );
  vec3 k = ext * ( 0.4 + 1.6 * ( 1.0 - wcn ) );
  vec3 T = exp( - path * k );
  vec3 body = uWaterColor * ( uAmbient + uSunColor * max( L.y, 0.0 ) * 0.55 );
  // 물가 한 뼘: 물이 얇아지며 반사도 사라짐(땅과 맞닿은 곳이 번쩍이지 않게)
  float edge = smoothstep( 0.0, 0.35, vDepth );
  F *= edge;
  spec *= edge;
  vec3 trans = T * ( 1.0 - F );
  vec3 own = body * ( 1.0 - T ) * ( 1.0 - F ) + refl * F + spec;
  if ( uFoam > 0.5 ) {
    float n = texture( uTexArr, vec3( vWorld.xz / 7.0, uNoiseLayer ) ).g;
    float foam = smoothstep( 1.4, 0.2, vDepth ) * smoothstep( 0.35, 0.6, n + 0.3 * smoothstep( 0.8, 0.1, vDepth ) ) * edge;
    vec3 white = vec3( 0.95 ) * ( uAmbient + uSunColor * max( L.y, 0.0 ) * 0.6 );
    own = mix( own, white, foam );
    trans *= 1.0 - foam;
  }
  // 안개: 바닥색(장면 텍스처)에는 이미 들어 있음. 물이 더한 빛만 물 표면 거리로 흐리게
  float fogF = 0.0;
  #ifdef USE_FOG
    #ifdef FOG_EXP2
      fogF = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
    #else
      fogF = smoothstep( fogNear, fogFar, vFogDepth );
    #endif
    vec3 color = bottom * trans + own * ( 1.0 - fogF ) + fogColor * fogF * ( 1.0 - trans );
  #else
    vec3 color = bottom * trans + own;
  #endif
  gl_FragColor = vec4( color, 1.0 );
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
      for (const [k, p] of [
        [a, pa],
        [b, pb],
        [c, pc],
      ]) {
        pos.push(p[0], p[1], p[2]);
        nrm.push(normals[k * 3], normals[k * 3 + 1], normals[k * 3 + 2]);
      }
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
        // 물: 한 모서리라도 물이 있으면 칸 전체에 물 평면(없는 모서리는 있는 값 중 가장 높은 것).
        // depth = 물 윗면 - 땅(음수면 땅이 더 높음 → 셰이더가 물가 선을 그 사이 0 인 곳으로 자름)
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
    const mesh = new THREE.Mesh(geometry, terrainMaterial(grid, tex, env.debug));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
    group.add(mesh);
  }
  let water = null;
  if (wpos.length > 0) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(wpos, 3));
    geometry.setAttribute("depth", new THREE.Float32BufferAttribute(wdepth, 1));
    water = new THREE.Mesh(geometry, waterMaterial(tex, env, grid.raw.props || {}));
    water.frustumCulled = false;
  }

  // 물 셰이더에 장면 텍스처 연결(scene.js 가 시점마다 부름)
  function setWaterInputs(target, camera, width, height) {
    if (!water) return;
    const u = water.material.uniforms;
    u.uSceneColor.value = target.texture;
    u.uSceneDepth.value = target.depthTexture;
    u.uResolution.value.set(width, height);
    u.uProjInv.value.copy(camera.projectionMatrixInverse);
  }

  // 풀 장식 ---------------------------------------------------------------------------
  const props = grid.raw.props || {};
  const grassIndex = grid.materials.indexOf("Grass");
  let grassMesh = null;
  const grassColor = srgb(grid.raw.colors.Grass || [0.42, 0.5, 0.25]);
  // 풀잎 다발 하나: 가는 잎 5장(키 1, 조금씩 기울고 휨). 뿌리는 땅색에 가깝고 끝으로 갈수록 밝게
  const tuft = (() => {
    const p = [];
    const c = [];
    let s = 7;
    const r = () => {
      s = (Math.imul(s, 1103515245) + 12345) >>> 0;
      return s / 4294967296;
    };
    for (let k = 0; k < 5; k++) {
      const a = r() * Math.PI * 2;
      const ca = Math.cos(a);
      const sa = Math.sin(a);
      const ox = (r() - 0.5) * 0.5;
      const oz = (r() - 0.5) * 0.5;
      const tall = 0.65 + 0.35 * r();
      const lean = 0.25 + 0.35 * r();
      const width = 0.06 + 0.03 * r();
      // 두 마디 잎(아래 사각형 + 위 삼각형)
      const base = [
        [-width, 0, 0],
        [width, 0, 0],
        [-width * 0.7, tall * 0.55, lean * 0.35],
        [width * 0.7, tall * 0.55, lean * 0.35],
        [0, tall, lean],
      ];
      const shade = [0.86, 0.86, 1.02, 1.02, 1.22];
      const world = base.map(([x, y, z]) => [ox + x * ca - z * sa, y, oz + x * sa + z * ca]);
      // 삼각형마다 앞뒤 두 번(감는 방향 반대): 한쪽 면만 그리는 재질이라 뒷면 법선이 뒤집혀 어두워지지 않음
      for (const [i0, i1, i2] of [
        [0, 1, 3],
        [0, 3, 2],
        [2, 3, 4],
        [0, 3, 1],
        [0, 2, 3],
        [2, 4, 3],
      ]) {
        for (const i of [i0, i1, i2]) {
          p.push(...world[i]);
          c.push(shade[i], shade[i], shade[i] * 0.96);
        }
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(c, 3));
    // 법선은 모두 위: 땅과 똑같이 빛을 받음(잎 앞뒤로 밝기가 튀지 않게)
    g.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(p.length).fill(0).map((_, n) => (n % 3 === 1 ? 1 : 0)), 3));
    return g;
  })();
  const grassMaterial = new THREE.MeshLambertMaterial({ vertexColors: true });

  // 카메라 앞(시야 안) 가까운 풀 재질 위에 다발. 25 스터드 너머는 드문드문 + 넓게, 60~100 에서 짧아지며 사라짐
  function updateGrass(camera, scene) {
    if (grassMesh) {
      scene.remove(grassMesh);
      grassMesh.dispose();
      grassMesh = null;
    }
    if (!props.Decoration || grassIndex < 0) return 0;
    if (camera.isOrthographicCamera) return 0;
    const eye = camera.position;
    const ground = grid.heightAt(eye.x, eye.z);
    const FAR = 100;
    if (!Number.isNaN(ground) && eye.y - ground > FAR) return 0;
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    if (forward.lengthSq() > 1e-6) forward.normalize();
    const center = eye.clone().addScaledVector(forward, FAR * 0.5);
    const radius = FAR * 0.75;
    const spacing = 0.42;
    const length = 1.3 * (props.GrassLength ?? 0.7);
    const items = [];
    let seed = 1;
    const rand = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed / 4294967296;
    };
    const probe = new THREE.Vector3();
    for (let z = center.z - radius; z < center.z + radius; z += spacing) {
      for (let x = center.x - radius; x < center.x + radius; x += spacing) {
        const px = x + (rand() - 0.5) * spacing;
        const pz = z + (rand() - 0.5) * spacing;
        const r1 = rand();
        const r2 = rand();
        const r3 = rand();
        const keep = rand();
        const d = Math.hypot(px - eye.x, pz - eye.z);
        if (d > FAR) continue;
        const density = Math.min(1, (25 / Math.max(d, 1)) ** 2);
        if (keep > density) continue;
        const h = grid.heightAt(px, pz);
        if (Number.isNaN(h)) continue;
        probe.set(px, h + 0.5, pz).project(camera);
        if (probe.z > 1 || Math.abs(probe.x) > 1.08 || Math.abs(probe.y) > 1.08) continue;
        if (grid.materialWeight(px, pz, "Grass") < 0.55) continue;
        const w = grid.waterAt(px, pz);
        if (!Number.isNaN(w) && w > h - 0.2) continue;
        const slope =
          Math.abs(grid.heightAt(px + 1, pz) - grid.heightAt(px - 1, pz)) +
          Math.abs(grid.heightAt(px, pz + 1) - grid.heightAt(px, pz - 1));
        if (!(slope < 1.6)) continue;
        const fade = Math.min(1, Math.max(0, (FAR - d) / (FAR * 0.4)));
        const len = length * (0.7 + 0.45 * r2) * (0.35 + 0.65 * fade);
        const widen = 1 / Math.sqrt(density);
        items.push([px, h - 0.04, pz, r1 * Math.PI * 2, len, widen, 0.9 + 0.2 * r3]);
      }
    }
    if (items.length === 0) return 0;
    grassMesh = new THREE.InstancedMesh(tuft, grassMaterial, items.length);
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    items.forEach(([x, y, z, yaw, len, widen, tone], n) => {
      q.setFromAxisAngle(up, yaw);
      s.set(widen, len, widen);
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

  return { group, water, stats, updateGrass, setWaterInputs };
}
