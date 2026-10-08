/* PC(Windows/맥/리눅스)용 유니티 빌드 진단 — "이 게임을 모바일로 바꿀 수 있나?"
 *
 * 실행은 못 하지만 파일을 읽어서 변환 가능성을 알려 준다.
 *   - 유니티 버전 · 빌드 대상: globalgamemanagers 등 SerializedFile 헤더, data.unity3d 의 UnityFS 헤더
 *     (형식은 UnityPy files/SerializedFile.py · files/BundleFile.py 와 같다)
 *   - 스크립트 백엔드: Mono(Managed/Assembly-CSharp.dll) / IL2CPP(GameAssembly.dll + il2cpp_data)
 *   - 렌더 파이프라인·입력·사운드 미들웨어·네이티브 플러그인 등 모바일 변환을 막는 요소
 * 파일 앞부분 몇 KB 만 읽으므로 큰 게임도 금방 끝난다.
 */

export const BUILD_TARGETS = {
  2: "macOS", 4: "macOS", 27: "macOS", 5: "Windows 32비트", 19: "Windows 64비트",
  17: "Linux", 24: "Linux 64비트", 25: "Linux", 13: "Android", 9: "iOS", 20: "WebGL",
};

const latin1 = new TextDecoder("latin1");

/** 항목의 앞부분 n 바이트만 읽는다(zip 압축 항목은 스트림을 중간에 끊는다). */
export async function readHead(entry, n = 4096) {
  const body = await entry.open();
  if (body instanceof Blob) return new Uint8Array(await body.slice(0, n).arrayBuffer());
  const reader = body.getReader();
  const chunks = [];
  let got = 0;
  while (got < n) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.byteLength;
  }
  reader.cancel().catch(() => {});
  const out = new Uint8Array(Math.min(n, got));
  let p = 0;
  for (const c of chunks) {
    const take = Math.min(c.byteLength, out.length - p);
    out.set(c.subarray(0, take), p);
    p += take;
    if (p >= out.length) break;
  }
  return out;
}

function cString(u8, p, max = 64) {
  const end = u8.indexOf(0, p);
  if (end < 0 || end - p > max) return null;
  return { text: latin1.decode(u8.subarray(p, end)), next: end + 1 };
}

/** 버전 문자열 정리: 번들은 '6000.0.65f1\n2' 처럼 뒤에 붙는 값이 있다 */
const cleanVersion = (v) => v.split("\n")[0].trim();

const VERSION_RE = /^(\d{1,4})\.(\d{1,2})\.(\d{1,3})([abfpx]\d+)?/;
const validVersion = (v) => VERSION_RE.test(v) && !/^0\.0\.0/.test(v); // 번들은 '0.0.0' 으로 버전을 지울 수 있다

/**
 * SerializedFile(globalgamemanagers, level0, *.assets) 헤더.
 * 앞 16바이트는 항상 빅엔디언: metadataSize, fileSize, formatVersion(@8), dataOffset.
 * 형식 9~21: @16 엔디언 바이트, 메타데이터 @20.  형식 22+: 48바이트 헤더(@16 u64 metadataSize, @24 u64 fileSize,
 * @32 u64 dataOffset, @40 엔디언 바이트), 메타데이터 @48. 메타데이터: 유니티 버전 C 문자열, int32 빌드 대상, u8 typetree 여부.
 * (Unity UnityDataTools SerializedFileDetector, UnityPy SerializedFile 참고)
 */
export function parseSerializedHeader(u8) {
  if (!u8 || u8.length < 24) return null;
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const version = dv.getUint32(8);
  if (version < 9 || version > 64) return null; // 9 미만(유니티 3.x 이하)은 메타데이터가 파일 끝에 있음 → 생략
  let p, bigEndian, dataOffset;
  if (version >= 22) {
    if (u8.length < 52) return null;
    dataOffset = Number(dv.getBigUint64(32));
    bigEndian = u8[40] !== 0;
    p = 48;
  } else {
    dataOffset = dv.getUint32(12);
    bigEndian = u8[16] !== 0;
    p = 20;
  }
  const s = cString(u8, p);
  if (!s || !validVersion(cleanVersion(s.text))) return null;
  let targetPlatform = null, enableTypeTree = version < 13 ? true : null, metaStart = s.next; // 13 미만은 typetree 가 항상 있음
  if (s.next + 4 <= u8.length) { targetPlatform = dv.getInt32(s.next, !bigEndian); metaStart += 4; }
  if (version >= 13 && metaStart < u8.length) { enableTypeTree = u8[metaStart] !== 0; metaStart += 1; }
  return { formatVersion: version, unityVersion: cleanVersion(s.text), targetPlatform, bigEndian, dataOffset, enableTypeTree, metaStart };
}

/** 메타데이터의 타입·오브젝트 표를 읽는다(UnityPy SerializedType / ObjectReader 와 같은 순서). 실패하면 null. */
export function parseObjectTable(u8) {
  const h = parseSerializedHeader(u8);
  if (!h || h.metaStart == null) return null;
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const le = !h.bigEndian;
  const v = h.formatVersion;
  let p = h.metaStart;
  const need = (n) => { if (p + n > u8.length) throw new RangeError("eof"); };
  const i32 = () => { need(4); const x = dv.getInt32(p, le); p += 4; return x; };
  const u32 = () => { need(4); const x = dv.getUint32(p, le); p += 4; return x; };
  const i16 = () => { need(2); const x = dv.getInt16(p, le); p += 2; return x; };
  const i64 = () => { need(8); const x = Number(dv.getBigInt64(p, le)); p += 8; return x; };
  const skip = (n) => { need(n); p += n; };
  const align = () => { p = (p + 3) & ~3; };
  try {
    const typeCount = i32();
    if (typeCount < 0 || typeCount > 100000) return null;
    const types = [];
    for (let i = 0; i < typeCount; i++) {
      const classID = i32();
      if (v >= 16) skip(1); // isStrippedType
      let scriptTypeIndex = -1;
      if (v >= 17) scriptTypeIndex = i16();
      if (v >= 13) {
        if ((v < 16 && classID < 0) || (v >= 16 && classID === 114)) skip(16); // scriptID
        skip(16); // oldTypeHash
      }
      if (h.enableTypeTree) {
        if (v >= 23) { skip(16); skip(u32()); } // contentHash, 직렬화된 typetree('mhtt' 블롭) 크기만큼 건너뜀
        else if (v >= 12 || v === 10) { const nodes = i32(); const strSize = i32(); skip(nodes * (v >= 19 ? 32 : 24) + strSize); }
        else return null; // 아주 오래된 형식은 생략
        if (v >= 21) { const deps = i32(); skip(deps * 4); }
      }
      types.push({ classID, scriptTypeIndex });
    }
    let bigID = 0;
    if (v >= 7 && v < 14) bigID = i32();
    const count = i32();
    if (count < 0 || count > 2000000) return null;
    const objects = [];
    for (let i = 0; i < count; i++) {
      let pathID;
      if (bigID) pathID = i64();
      else if (v < 14) pathID = i32();
      else { align(); pathID = i64(); }
      const start = (v >= 22 ? i64() : u32()) + h.dataOffset;
      const size = u32();
      const typeID = i32();
      let classID;
      if (v < 16) { classID = dv.getUint16(p, le); skip(2); } else classID = types[typeID]?.classID;
      if (v < 11) skip(2);
      if (v >= 11 && v < 17) skip(2);
      if (v === 15 || v === 16) skip(1);
      objects.push({ pathID, start, size, classID });
    }
    return { header: h, types, objects };
  } catch {
    return null;
  }
}

/** GraphicsDeviceType (UnityCsReference GraphicsEnums.cs) */
export const GRAPHICS_APIS = {
  0: "OpenGL2", 1: "Direct3D9", 2: "Direct3D11", 4: "Null", 8: "OpenGLES2", 11: "OpenGLES3", 16: "Metal",
  17: "OpenGLCore", 18: "Direct3D12", 21: "Vulkan", 28: "WebGPU",
};

// 실제 PC/모바일 빌드에 나올 수 있는 값만(0 OpenGL2·4 Null 은 쓰레기 값과 구분이 안 돼 제외)
const VALID_GFX = new Set([1, 2, 8, 11, 16, 17, 18, 21, 28]);

/**
 * BuildSettings(ClassID 141).m_GraphicsAPIs 읽기. 이 목록에 있는 API 용 셰이더만 빌드에 들어 있다.
 * m_Version(=유니티 버전, 길이 붙은 4바이트 정렬 문자열)을 찾아 그 뒤를 버전별 순서대로 읽는다:
 *   2020~2022: m_Version, m_GraphicsAPIs  |  6000.x: m_Version, m_AuthToken, m_GraphicsAPIs
 *   5.6~2019: m_Version, m_AuthToken, runtimeClassHashes(map<int,Hash128>), scriptHashes(map<Hash128,Hash128>), m_GraphicsAPIs
 * 못 찾으면 객체 끝 64바이트 안에서 [개수][값…] 모양을 찾는다(6000.7 은 뒤에 필드가 더 붙음).
 */
export function readGraphicsAPIs(u8) {
  const t = parseObjectTable(u8);
  const bs = t?.objects.find((o) => o.classID === 141);
  if (!bs || bs.start < 0 || bs.start + bs.size > u8.length || bs.size < 8) return null;
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const le = !t.header.bigEndian;
  const objEnd = bs.start + bs.size;
  const vectorAt = (at) => {
    if (at < bs.start || at + 4 > objEnd) return null;
    const n = dv.getInt32(at, le);
    if (n < 1 || n > 8 || at + 4 + 4 * n > objEnd) return null;
    const vals = [];
    for (let k = 0; k < n; k++) vals.push(dv.getInt32(at + 4 + 4 * k, le));
    return vals.every((x) => VALID_GFX.has(x)) ? vals : null;
  };
  const enc = new TextEncoder().encode(t.header.unityVersion);
  const skipStr = (x) => (x + 4 + dv.getInt32(x, le) + 3) & ~3;
  const skipMaps = (x) => { const a = dv.getInt32(x, le); x += 4 + a * 20; const b = dv.getInt32(x, le); return x + 4 + b * 32; };
  for (let q = bs.start; q + 4 + enc.length <= objEnd; q += 4) {
    if (dv.getInt32(q, le) !== enc.length || !enc.every((c, k) => u8[q + 4 + k] === c)) continue;
    const afterVer = (q + 4 + enc.length + 3) & ~3;
    const cands = [() => afterVer, () => skipStr(afterVer), () => skipMaps(skipStr(afterVer))];
    for (const c of cands) {
      let at;
      try { at = c(); } catch { continue; }
      const v = vectorAt(at);
      if (v) return v;
    }
  }
  // 대비책: 객체 끝에 딱 맞는 vector 를 긴 것부터 찾는다. 6000.7 은 뒤에 같은 길이의 m_GraphicsAPIUGKFlags 가 붙으므로
  // [n][n 개 API][n][n 개 플래그] 꼴이면 앞쪽을 쓴다.
  for (let n = 8; n >= 1; n--) {
    const pair = objEnd - 8 - 8 * n;
    if (pair >= bs.start && dv.getInt32(objEnd - 4 - 4 * n, le) === n) {
      const v = vectorAt(pair);
      if (v && v.length === n) return v;
    }
  }
  for (let n = 8; n >= 1; n--) {
    const v = vectorAt(objEnd - 4 - 4 * n);
    if (v && v.length === n) return v;
  }
  return null;
}

/** PE 헤더의 Machine 값 → x86 | x64 | arm64 (Unity 의 StandaloneWindows64 는 x64·ARM64 둘 다 포함) */
export function peArch(u8) {
  if (!u8 || u8.length < 0x40 || u8[0] !== 0x4d || u8[1] !== 0x5a) return null;
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const pe = dv.getUint32(0x3c, true);
  if (pe + 6 > u8.length || dv.getUint32(pe, true) !== 0x4550) return null;
  return { 0x14c: "x86", 0x8664: "x64", 0xaa64: "arm64" }[dv.getUint16(pe + 4, true)] || null;
}

/** exe / UnityPlayer.dll 의 버전 리소스(UTF-16)에서 유니티 버전 찾기 — 헤더로 못 읽을 때만. */
export function versionFromPE(u8) {
  const text = new TextDecoder("utf-16le").decode(u8.subarray(0, u8.length - (u8.length % 2)));
  const m = /Unity Version\u0000+(\d{1,4}\.\d{1,2}\.\d{1,3}[abfp]\d+)/.exec(text) ||
    /ProductVersion\u0000+(\d{1,4}\.\d{1,2}\.\d{1,3}[abfp]\d+)/.exec(text);
  return m ? m[1] : null;
}

/** UnityFS/UnityWeb/UnityRaw 번들(data.unity3d) 헤더 → { unityVersion } */
export function parseBundleHeader(u8) {
  const sig = cString(u8, 0, 16);
  if (!sig || !/^Unity(FS|Web|Raw)$/.test(sig.text)) return null;
  const player = cString(u8, sig.next + 4);
  const engine = player && cString(u8, player.next);
  if (!engine || !validVersion(cleanVersion(engine.text))) return null;
  return { unityVersion: cleanVersion(engine.text), bundle: sig.text };
}

const dirname = (p) => { const i = p.lastIndexOf("/"); return i < 0 ? "" : p.slice(0, i); };
const basename = (p) => p.slice(p.lastIndexOf("/") + 1);

// 여러 플랫폼 빌드가 함께 든 zip 이면 Windows(에뮬레이터로 돌릴 수 있음) → Linux → 맥 순, 같으면 얕은 경로
const PLATFORM_RANK = { windows: 0, linux: 1, mac: 2, unknown: 3 };
const better = (a, b) => !b || PLATFORM_RANK[a.platform] < PLATFORM_RANK[b.platform] ||
  (PLATFORM_RANK[a.platform] === PLATFORM_RANK[b.platform] && a.dataDir.length < b.dataDir.length);

/** 데이터 폴더(*_Data 또는 *.app/Contents/Resources/Data)와 플랫폼을 찾는다. */
function locate(paths) {
  let best = null;
  for (const p of paths) {
    let m = /^(.*?)([^/]+)_Data\/(globalgamemanagers|data\.unity3d|mainData|resources\.assets|level0)$/i.exec(p);
    if (m) {
      const root = m[1].replace(/\/$/, "");
      const dataDir = `${m[1]}${m[2]}_Data`;
      const isWin = paths.some((x) => dirname(x) === root && /^(UnityPlayer\.dll|.+\.exe)$/i.test(basename(x)));
      const isLinux = paths.some((x) => dirname(x) === root && /(\.x86(_64)?|UnityPlayer\.so)$/i.test(basename(x)));
      const cand = { root, dataDir, name: m[2], platform: isWin ? "windows" : isLinux ? "linux" : "unknown" };
      if (better(cand, best)) best = cand;
      continue;
    }
    m = /^(.*?)([^/]+)\.app\/Contents\/Resources\/Data\/(globalgamemanagers|data\.unity3d|mainData)$/i.exec(p);
    if (m) {
      const cand = { root: `${m[1]}${m[2]}.app/Contents`, dataDir: `${m[1]}${m[2]}.app/Contents/Resources/Data`, name: m[2], platform: "mac" };
      if (better(cand, best)) best = cand;
    }
  }
  return best;
}

const FEATURES = [
  // [어셈블리 이름(.dll 제외), 키, 이름, 심각도(block|warn|info), 설명]
  [/^Unity\.RenderPipelines\.HighDefinition\.Runtime$/i, "hdrp", "HDRP(고사양 렌더 파이프라인)", "block",
    "HDRP 는 모바일·WebGL 을 지원하지 않아요. 변환하려면 URP/기본 파이프라인으로 바꾸고 셰이더·조명을 다시 잡아야 합니다."],
  [/^Unity\.RenderPipelines\.(Universal|Lightweight)\.Runtime$/i, "urp", "URP/LWRP", "info", "URP 는 모바일·WebGL 을 지원합니다."],
  [/^Unity\.2D\./i, "2d", "2D 패키지", "info", "2D 게임으로 보입니다(폰에서 가벼운 편)."],
  [/^Unity\.InputSystem$/i, "inputsystem", "새 Input System", "info", "터치 입력을 붙이기 쉬운 편입니다."],
  [/^(Unity\.Addressables|Unity\.ResourceManager)$/i, "addressables", "Addressables", "warn", "콘텐츠 번들이 PC용으로 만들어져 있어 다시 빌드해야 합니다."],
  [/^(com\.rlabrecque\.steamworks\.net|Steamworks\.NET|Facepunch\.Steamworks.*)$/i, "steam", "Steamworks", "warn", "스팀 기능(업적·클라우드 저장)은 모바일에서 빼야 합니다."],
  [/^FMODUnity/i, "fmod", "FMOD 사운드", "warn", "FMOD 모바일용 라이브러리로 바꿔야 합니다(라이선스 확인 필요)."],
  [/^AK\.Wwise\./i, "wwise", "Wwise 사운드", "warn", "Wwise 모바일 SDK 가 필요합니다."],
  [/^Cri(Mw|Ware)/i, "cri", "CRIWARE", "warn", "CRIWARE 모바일 라이브러리가 필요합니다."],
  [/^Rewired_Core$/i, "rewired", "Rewired 입력", "info", "Rewired 는 터치 컨트롤을 지원합니다."],
  [/^(Elringus\.Naninovel|Naninovel|Fungus|Utage)/i, "vn", "비주얼노벨 엔진", "info", "대화형 게임이라 조작 변환이 비교적 쉽습니다."],
];

// ScriptingAssemblies.json 이 없는 IL2CPP 빌드: global-metadata.dat 에서 "<어셈블리>.dll\0" 로 찾는다
// (그냥 이름만 찾으면 InternalsVisibleTo 문자열 때문에 HDRP 등이 잘못 잡힌다)
const IL2CPP_NEEDLES = [
  "Unity.RenderPipelines.HighDefinition.Runtime", "Unity.RenderPipelines.Universal.Runtime", "Unity.2D.Animation.Runtime",
  "Unity.2D.SpriteShape.Runtime", "Unity.2D.Tilemap.Extras", "Unity.InputSystem", "Unity.ResourceManager", "Unity.Addressables",
  "com.rlabrecque.steamworks.net", "Facepunch.Steamworks.Win64", "FMODUnity", "AK.Wwise.Unity.API", "CriMw.CriWare.Runtime",
  "Rewired_Core", "Elringus.Naninovel.Runtime", "Unity.RenderPipelines.Lightweight.Runtime",
];

/** 바이트 배열에서 ASCII 바이트열 찾기(큰 파일을 문자열로 바꾸지 않으려고) */
function bytesInclude(hay, needle) {
  const n = new TextEncoder().encode(needle);
  for (let i = hay.indexOf(n[0]); i >= 0 && i <= hay.length - n.length; i = hay.indexOf(n[0], i + 1)) {
    let k = 1;
    while (k < n.length && hay[i + k] === n[k]) k++;
    if (k === n.length) return true;
  }
  return false;
}

// 유니티가 직접 넣는 파일(플러그인이 아님)
const SYSTEM_FILE = /^(UnityPlayer|GameAssembly|UnityCrashHandler(32|64)?|baselib|WinPixEventRuntime|D3D12Core|d3d12SDKLayers|mono-2\.0-bdwgc|MonoPosixHelper|libmonobdwgc-2\.0|libMonoPosixHelper|ScreenSelector|lib_burst_generated)\.(dll|exe|so|dylib|bundle)$/i;

async function readText(entry, max = 1 << 20) {
  if (!entry || entry.size > max) return null;
  return new TextDecoder().decode(await readHead(entry, entry.size));
}

/**
 * PC 빌드 진단.
 * @param {Array<{path:string,size:number,open:Function}>} entries
 * @returns {Promise<object|null>} 유니티 PC 빌드가 아니면 null
 */
export async function inspectPcBuild(entries) {
  const paths = entries.map((e) => e.path);
  const loc = locate(paths);
  if (!loc) return null;
  const byPath = new Map(entries.map((e) => [e.path, e]));
  const inData = (rel) => byPath.get(`${loc.dataDir}/${rel}`);
  const under = (dir) => entries.filter((e) => e.path.startsWith(dir + "/"));
  const atRoot = (name) => byPath.get(loc.root ? `${loc.root}/${name}` : name);

  // 1) 유니티 버전 · 빌드 대상 · 그래픽 API
  let unityVersion = null, targetPlatform = null, versionSource = null, graphicsAPIs = null;
  const ggm = inData("globalgamemanagers") || inData("mainData");
  if (ggm && ggm.size <= 32 << 20) {
    try {
      const bytes = await readHead(ggm, ggm.size);
      const h = parseSerializedHeader(bytes);
      if (h) {
        unityVersion = h.unityVersion; targetPlatform = h.targetPlatform; versionSource = basename(ggm.path);
        graphicsAPIs = readGraphicsAPIs(bytes);
      }
    } catch { /* 다음 후보 */ }
  }
  for (const name of ["level0", "sharedassets0.assets", "resources.assets"]) {
    if (unityVersion) break;
    const e = inData(name);
    if (!e) continue;
    try {
      const h = parseSerializedHeader(await readHead(e, 1024));
      if (h) { unityVersion = h.unityVersion; targetPlatform = h.targetPlatform; versionSource = name; }
    } catch { /* 다음 후보 */ }
  }
  if (!unityVersion && inData("data.unity3d")) {
    try {
      const h = parseBundleHeader(await readHead(inData("data.unity3d"), 512));
      if (h) { unityVersion = h.unityVersion; versionSource = "data.unity3d"; }
    } catch { /* 무시 */ }
  }
  if (!unityVersion && loc.platform === "windows") { // 실행 파일의 버전 리소스
    const exe = atRoot(`${loc.name}.exe`);
    if (exe && exe.size <= 8 << 20) {
      try { unityVersion = versionFromPE(await readHead(exe, exe.size)); if (unityVersion) versionSource = basename(exe.path); } catch { /* 무시 */ }
    }
  }

  // 2) 스크립트 백엔드 (IL2CPP 를 먼저 본다 — IL2CPP 빌드에도 백업용 Managed 폴더가 딸려 오는 경우가 있음)
  const rootFiles = entries.filter((e) => dirname(e.path) === loc.root).map((e) => basename(e.path));
  const il2cpp = rootFiles.some((n) => /^GameAssembly\.(dll|so|dylib)$/i.test(n)) ||
    entries.some((e) => e.path.startsWith(`${loc.dataDir}/il2cpp_data/`)) ||
    entries.some((e) => /\/Frameworks\/GameAssembly\.dylib$/i.test(e.path));
  const managed = under(`${loc.dataDir}/Managed`).filter((e) => /\.dll$/i.test(e.path));
  const mono = !il2cpp && (managed.length > 0 || entries.some((e) => /(^|\/)(MonoBleedingEdge|Mono)\//.test(e.path)));
  const backend = il2cpp ? "il2cpp" : mono ? "mono" : "unknown";
  // 게임 코드 크기: Assembly-CSharp* + 엔진·표준 라이브러리·흔한 패키지가 아닌 DLL(asmdef 로 나눈 게임 코드)
  const NOT_GAME = /^(UnityEngine|UnityEditor|Unity\.|System|mscorlib|netstandard|Mono\.|Microsoft\.|Newtonsoft|Cinemachine|DOTween|DemiLib|Boo\.|UnityScript|nunit|com\.unity\.|Rewired|FMOD|AK\.|Cri|Steamworks|Facepunch|com\.rlabrecque|Purchasing|Google\.|Firebase|Sirenix|Elringus|Fungus|Utage|Spine|TextMeshPro|ICSharpCode|Ionic|websocket|NativeGallery|LeanTween|Zenject|UniRx|UniTask)/i;
  const scriptBytes = il2cpp ? 0 : managed
    .filter((e) => /\/Assembly-CSharp(-firstpass)?\.dll$/i.test(e.path) || !NOT_GAME.test(basename(e.path)))
    .reduce((s, e) => s + e.size, 0);
  let metadataEncrypted = false;
  const meta = il2cpp ? inData("il2cpp_data/Metadata/global-metadata.dat") : null;
  if (il2cpp) {
    if (!meta) metadataEncrypted = true; // 메타데이터가 실행 파일에 숨겨져 있거나 보호된 빌드
    else {
      try {
        const b = await readHead(meta, 8);
        metadataEncrypted = new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(0, true) !== 0xfab11baf;
      } catch { /* 무시 */ }
    }
  }
  // IL2CPP 빌드인데 실수로 딸려 온 백업 폴더(<이름>_BackUpThisFolder_ButDontShipItWithYourGame/Managed)엔 C# 코드가 그대로 있다
  const backupManaged = il2cpp && entries.some((e) => /_BackUpThisFolder_ButDontShipItWithYourGame\/Managed\/Assembly-CSharp\.dll$/i.test(e.path));
  // 실행 파일 CPU 종류(Windows)
  let arch = null;
  if (loc.platform === "windows") {
    const exe = atRoot(`${loc.name}.exe`);
    if (exe) { try { arch = peArch(await readHead(exe, 4096)); } catch { /* 무시 */ } }
  }

  // 3) 쓰인 어셈블리 → 특징 (ScriptingAssemblies.json 이 Mono·IL2CPP 모두 정확, 없으면 Managed 폴더)
  let assemblies = [];
  try {
    const json = await readText(inData("ScriptingAssemblies.json"), 4 << 20);
    if (json) assemblies = (JSON.parse(json).names || []).map((n) => String(n).replace(/\.dll$/i, ""));
  } catch { /* 무시 */ }
  if (!assemblies.length) assemblies = managed.map((e) => basename(e.path).replace(/\.dll$/i, ""));
  if (!assemblies.length && meta && !metadataEncrypted && meta.size <= 64 << 20) {
    try {
      const bytes = await readHead(meta, meta.size);
      assemblies = IL2CPP_NEEDLES.filter((n) => bytesInclude(bytes, `${n}.dll\0`));
    } catch { /* 무시 */ }
  }
  const features = [];
  const seen = new Set();
  const addFeature = (key, name, level, note) => { if (!seen.has(key)) { seen.add(key); features.push({ key, name, level, note }); } };
  for (const a of assemblies) for (const [re, key, name, level, note] of FEATURES) if (re.test(a)) addFeature(key, name, level, note);
  if (under(`${loc.dataDir}/StreamingAssets/aa`).length) {
    addFeature("addressables", "Addressables", "warn", "콘텐츠 번들이 PC용으로 만들어져 있어 다시 빌드해야 합니다.");
  }
  if (metadataEncrypted) addFeature("encrypted", "보호된 메타데이터", "block", "IL2CPP 메타데이터가 없거나 암호화·난독화돼 있어(보호된 빌드) 분석 도구가 거의 통하지 않습니다.");

  // 4) 네이티브 플러그인(PC 전용 → 모바일용이 따로 있어야 함)
  const nativePlugins = entries
    .filter((e) => ((e.path.startsWith(`${loc.dataDir}/Plugins/`) ||
        (loc.platform === "mac" && e.path.toLowerCase().startsWith(`${loc.root}/plugins/`.toLowerCase()))) &&
        /\.(dll|so|dylib|bundle)$/i.test(e.path)) ||
      (dirname(e.path) === loc.root && /\.(dll|so)$/i.test(e.path)))
    .map((e) => basename(e.path))
    .filter((n) => !SYSTEM_FILE.test(n));
  const uniquePlugins = [...new Set(nativePlugins)];
  const burst = entries.some((e) => /lib_burst_generated\.(dll|so|dylib|bundle)$/i.test(e.path));
  if (uniquePlugins.some((n) => /^(lib)?steam_api(64)?\./i.test(n))) addFeature("steam", "Steamworks", "warn", "스팀 기능(업적·클라우드 저장)은 모바일에서 빼야 합니다.");

  // 5) 그 밖
  let company = "", product = "";
  try {
    const info = await readText(inData("app.info"), 64 << 10);
    if (info) [company = "", product = ""] = info.split(/\r?\n/).map((x) => x.trim());
  } catch { /* 무시 */ }
  const total = entries.reduce((s, e) => s + (e.size || 0), 0);
  const streaming = under(`${loc.dataDir}/StreamingAssets`);
  const videos = streaming.filter((e) => /\.(mp4|webm|mov|usm|avi)$/i.test(e.path)).length;
  const modded = entries.some((e) => /(^|\/)(BepInEx|MelonLoader)\//i.test(e.path));
  const gfxNames = graphicsAPIs ? graphicsAPIs.map((x) => GRAPHICS_APIS[x]) : null;

  const report = {
    platform: loc.platform,
    gameName: product || loc.name,
    gameFolder: loc.name,
    productName: product,
    company,
    unityVersion,
    versionSource,
    targetPlatform,
    targetName: targetPlatform != null ? BUILD_TARGETS[targetPlatform] || `BuildTarget ${targetPlatform}` : null,
    backend,
    metadataEncrypted,
    scriptBytes,
    assemblyCount: assemblies.length,
    features,
    nativePlugins: uniquePlugins,
    burst,
    videos,
    modded,
    graphicsAPIs: gfxNames,
    // OpenGL ES 셰이더가 있으면 모바일용. 데스크톱 Vulkan/OpenGL 은 'Direct3D 외'일 뿐 폰에서 그대로 된다는 보장은 없다.
    mobileShaders: graphicsAPIs ? graphicsAPIs.some((x) => x === 8 || x === 11) : null,
    nonD3DShaders: graphicsAPIs ? graphicsAPIs.some((x) => x === 8 || x === 11 || x === 16 || x === 17 || x === 21) : null,
    arch,
    backupManaged,
    totalBytes: total,
    fileCount: entries.length,
  };
  report.routes = recommend(report);
  return report;
}

function scriptSize(bytes) {
  if (!bytes) return null;
  if (bytes < 400 << 10) return "small";
  if (bytes < 3 << 20) return "medium";
  return "large";
}

/** "6000.1.3f1" → [6000, 1] */
function major(v) {
  const m = /^(\d+)\.(\d+)/.exec(v || "");
  return m ? [+m[1], +m[2]] : null;
}

const LINKS = {
  unityArchive: ["유니티 에디터 버전 보관소", "https://unity.com/releases/editor/archive"],
  unityHub: ["Unity Hub 내려받기", "https://unity.com/download"],
  assetripper: ["AssetRipper", "https://assetripper.com/download.html"],
  ilspy: ["ILSpy(코드 미리보기)", "https://github.com/icsharpcode/ILSpy/releases"],
  winlator: ["Winlator 공식 배포처", "https://github.com/brunodev85/winlator/releases"],
  gamenative: ["GameNative(대안)", "https://github.com/utkarshdalal/GameNative"],
  unify: ["unify(셰이더 문제 실험 기록)", "https://github.com/0xf4b1/unify"],
};

/**
 * 진단 결과로 변환 경로별 가능성을 매긴다. odds: good | possible | hard | no
 * 근거: 유니티 공식 문서, AssetRipper/Winlator/Box64 저장소, 데이터 이식 실험(unify) 등 — README 참고.
 */
export function recommend(r) {
  const routes = [];
  const has = (k) => r.features.some((f) => f.key === k);
  const size = scriptSize(r.scriptBytes);
  const ver = major(r.unityVersion);
  const dx12Default = ver && (ver[0] > 6000 || (ver[0] === 6000 && ver[1] >= 1));
  const sameVer = r.unityVersion ? `같은 유니티 버전(${r.unityVersion})` : "게임과 같은 유니티 버전";

  // 1) 원본 프로젝트로 다시 빌드 — 개발자만 가능하지만 가장 확실
  const noArm64 = ver && (ver[0] < 2017 || (ver[0] === 2017 && !/^2017\.4\.(1[6-9]|[2-9]\d)/.test(r.unityVersion)) || (ver[0] === 2018 && ver[1] < 2));
  const apkNote = noArm64
    ? `앱(APK)이 필요하면 주의: 유니티 ${r.unityVersion} 에는 안드로이드 ARM64 옵션이 없어(2017.4.16·2018.2 부터 지원) 32비트 APK 만 나오고, 갤럭시 S24 이후 같은 64비트 전용 폰에는 설치되지 않습니다. 복원한 프로젝트가 이 버전에서 돌아가면 2017.4 LTS 최신 또는 2018.4 이상으로 올린 뒤 IL2CPP·ARM64, Target API 24 이상으로 빌드하세요.`
    : "앱(APK)으로 만들 땐 Scripting Backend 를 IL2CPP·ARM64 로 바꾸고 Target API 를 24 이상으로 하세요 — Mono 는 32비트 전용이라 갤럭시 S24 이후 폰에는 설치되지 않습니다.";
  const source = {
    key: "source",
    title: "개발자가 원본 프로젝트로 다시 빌드",
    odds: has("hdrp") ? "possible" : "good",
    summary: "가장 확실하고 정식인 방법입니다. 원본 프로젝트(Assets·ProjectSettings 폴더)가 있으면 유니티 에디터에서 빌드 대상만 " +
      "WebGL(→ UniPlay) 또는 Android 로 바꾸고, 터치 조작·화면 비율·성능을 손보면 됩니다. 게임 파일(.exe)만 있는 사람은 할 수 없으니 개발자에게 요청해 보세요.",
    steps: [
      `Unity Hub 로 ${sameVer}(가능하면 같은 계열의 보안 패치 버전)을 설치하고 'WebGL Build Support'(또는 'Android Build Support') 모듈을 추가합니다. 모듈은 Hub 로 설치한 에디터에만 추가할 수 있고, 수익 20만 달러 미만이면 Unity Personal(무료)로 충분합니다.`,
      "File → Build Settings(Unity 6 은 Build Profiles)에서 WebGL 로 전환합니다. 압축은 Gzip 또는 끄기 — UniPlay 가 알아서 풉니다.",
      "Player Settings 에서 Development Build 를 끄고(2022 이상은 메모리 증가 방식 Geometric 권장), 폰용으로 텍스처 크기·품질을 낮춥니다.",
      "마우스로만 하는 게임은 기본 설정(터치→마우스 변환)으로 대개 바로 됩니다. 키보드 게임은 WebGL 이면 UniPlay 가상 패드를 쓰고, 앱으로 만들 땐 게임 안에 터치 버튼을 추가합니다(새 Input System 을 쓰는 게임이면 On-Screen 컨트롤로 간단히).",
      "UI 는 Canvas Scaler 를 'Scale With Screen Size' 로 바꾸고 버튼을 손가락 크기로 키웁니다.",
      "빌드 폴더(index.html + Build)를 zip 으로 묶어 UniPlay 에 넣으면 끝. Android 앱으로 만들 땐 IL2CPP + ARM64, Target API 24 이상으로 빌드합니다.",
      "Windows 전용 DLL(스팀 등), C# 스레드, 소켓 통신은 WebGL 에서 안 되니 빼거나 바꿔야 합니다. 모바일 브라우저 공식 지원은 Unity 6 부터이고, 그 전 버전도 대개 돌아가지만 보장되지 않습니다.",
    ],
    links: [LINKS.unityHub, LINKS.unityArchive],
  };
  if (has("hdrp")) {
    source.summary += " 단, 이 게임은 HDRP 를 써서 WebGL/Android 로 바로 빌드되지 않습니다 — URP 로 전환(Render Pipeline Converter)하고 재질·조명을 다시 잡아야 합니다.";
    source.steps.splice(1, 0, "HDRP 는 모바일·WebGL 을 지원하지 않으니 먼저 URP 로 전환하고 재질·조명·후처리를 다시 맞춥니다.");
  }
  if (ver && (ver[0] < 2021 || (ver[0] === 2021 && ver[1] < 2))) {
    source.steps.push(`유니티 ${r.unityVersion} 의 WebGL 빌드는 텍스처가 PC용(DXT) 압축뿐이라 폰에서 메모리를 많이 먹습니다. 가능하면 2021.2 이상(공식 모바일 지원은 Unity 6)으로 올려 ASTC 로 빌드하세요.`);
  }
  if (noArm64) source.steps.push(`유니티 ${r.unityVersion} 은 안드로이드 ARM64 빌드를 지원하지 않아 64비트 전용 폰용 앱을 만들 수 없습니다. 앱이 필요하면 프로젝트를 2018.4 이상으로 올리거나, WebGL(UniPlay)로 빌드하세요.`);
  routes.push(source);

  // 2) 에뮬레이터로 PC판 그대로
  const emu = {
    key: "emulate",
    title: "폰에서 Windows 에뮬레이터로 그대로 실행",
    odds: "possible",
    summary: "",
    steps: [
      "이 방법은 '모바일 버전'을 만드는 게 아니라 PC판을 폰에서 흉내 내어 돌립니다. 안드로이드만 되고 아이폰은 안 됩니다.",
      "폰 칩을 확인하세요(설정 → 휴대전화 정보, 또는 CPU-Z). 스냅드래곤(Adreno GPU)이 가장 잘 되고, 엑시노스·디멘시티(Xclipse/Mali)는 실험적인 경로라 게임마다 차이가 큽니다(가벼운 2D 는 대체로 OK). 갤럭시는 S23·S25 시리즈(FE 제외)와 S24/S26 Ultra 가 스냅드래곤, 한국판 S24/S24+·S26/S26+ 와 FE 모델은 엑시노스입니다. RAM 8GB 이상 권장.",
      "Winlator 를 공식 GitHub 배포처에서만 받아 설치합니다(비슷한 이름의 가짜 앱 주의). 처음 실행 때 설정이 몇 분 걸립니다.",
      "압축을 푼 게임 폴더 전체(.exe, UnityPlayer.dll, _Data 폴더 등)를 폰의 Download 폴더에 넣습니다. Winlator 안에서는 D: 드라이브입니다.",
      "컨테이너를 만듭니다: 화면 1280×720, 그래픽 드라이버는 스냅드래곤이면 Turnip / 그 외 Vortek, DX 래퍼 DXVK, Box64 프리셋 'Stability'.",
      "컨테이너를 실행해 D: 의 게임 .exe 를 열고, 되면 바로가기를 만듭니다. 바로가기 실행 인수에 -force-gfx-direct 를 넣으면 유니티 게임이 더 안정적입니다.",
      "기본 터치는 노트북 터치패드처럼 동작합니다. 키보드가 필요한 게임은 Input Controls 에서 버튼 배치를 만듭니다.",
      "안 되면 한 번에 하나씩: Box64 프리셋을 Stability → Conservative → Intermediate 순으로, 더 오래된 DXVK(1.10.x), 그래도 안 되면 GameNative 같은 다른 앱을 시도합니다.",
      "세이브는 컨테이너 안에 저장되니 컨테이너를 지우기 전에 백업하세요.",
    ],
    links: [LINKS.winlator, LINKS.gamenative],
  };
  if (emu.steps.length) {
  // 실행이 안 될 때 원인을 볼 수 있는 로그 위치(유니티 버전·app.info 의 회사·제품 이름으로)
  const lowDir = `C:\\users\\(사용자)\\AppData\\LocalLow\\${r.company || "<회사>"}\\${r.productName || "<게임 이름>"}`;
  const logPath = !ver || ver[0] >= 2018 ? `${lowDir}\\Player.log`
    : ver[0] === 2017 && ver[1] >= 2 ? `${lowDir}\\output_log.txt` : `게임 폴더의 ${r.gameFolder || "<게임>"}_Data\\output_log.txt`;
  emu.steps.splice(8, 0, `켜지지 않으면 컨테이너 안의 ${logPath} 에 원인이 적혀 있습니다.`);
  const g = r.graphicsAPIs || [];
  emu.steps.splice(8, 0, g.includes("Vulkan") || g.includes("OpenGLCore")
    ? `이 빌드에는 ${g.filter((x) => x === "Vulkan" || x === "OpenGLCore").join("·")} 도 들어 있어 실행 인수 ${g.includes("Vulkan") ? "-force-vulkan" : "-force-glcore"} 도 시도해 볼 수 있습니다.`
    : "-force-glcore·-force-vulkan 실행 인수는 이 빌드에 그 셰이더가 없어 실패하니 쓰지 마세요.");
  }
  if (emu.steps.length && (r.arch === "x86" || (r.targetPlatform === 5 && !r.arch))) emu.steps.splice(4, 0, "이 게임은 32비트 Windows 빌드입니다. Winlator 는 32비트도 기본으로(WoW64) 돌리니 그대로 실행하면 됩니다.");
  if (r.arch === "arm64") {
    emu.odds = "hard";
    emu.summary = "ARM64 용 Windows 빌드라 x86 에뮬레이터(Winlator 의 Box64)가 다루는 형식이 아닙니다. 같은 게임의 일반(x64) Windows 버전을 구해 시도하세요.";
  }
  if (r.platform === "mac" || r.platform === "linux") {
    emu.odds = "no";
    emu.summary = `${r.platform === "mac" ? "맥" : "리눅스"}용 빌드라 Windows 에뮬레이터로 돌릴 수 없습니다. 같은 게임의 Windows 버전이 있으면 그 zip 을 넣어 다시 진단해 보세요.`;
    emu.steps = [];
    emu.links = [];
  } else {
    const gfx = r.graphicsAPIs || [];
    const dx12Only = gfx.length > 0 && gfx.includes("Direct3D12") && !gfx.includes("Direct3D11");
    const heavy = has("hdrp") || r.totalBytes > 4 * 1024 ** 3 || dx12Only;
    if (heavy) emu.odds = "hard";
    let gfxNote = "";
    if (dx12Only) gfxNote = " 이 빌드는 DirectX 12 전용이라 폰에서는 더 무겁고 덜 안정적인 경로(VKD3D)를 탑니다.";
    else if (gfx[0] === "Direct3D12" && gfx.includes("Direct3D11")) gfxNote = " DirectX 12 가 기본이지만 DX11 도 들어 있으니, 안 되면 실행 인수에 -force-d3d11 을 넣어 보세요.";
    else if (!gfx.length && dx12Default) gfxNote = " 유니티 6.1 이상은 기본이 DirectX 12 라 더 무겁습니다 — 안 되면 실행 인수에 -force-d3d11 을 시도해 보세요(빌드에 DX11 이 있을 때만 효과).";
    emu.summary = "변환 없이 Winlator(Wine + Box64)로 PC판을 그대로 돌립니다. Mono·IL2CPP 모두 가능하고, 가벼운 2D 게임·비주얼노벨은 " +
      "스냅드래곤 폰에서 잘 되는 편입니다. 3D 게임은 폰 성능에 따라 잘 되기도 하고 아예 안 켜지기도 합니다." +
      (has("2d") && !heavy ? " 이 게임은 2D 로 보여 가벼운 편입니다." : "") +
      (has("hdrp") || r.totalBytes > 4 * 1024 ** 3 ? " 이 게임은 용량이 크거나 고사양 그래픽(HDRP)을 써서 폰에서는 무거울 가능성이 큽니다." : "") +
      gfxNote +
      (r.nativePlugins.some((n) => /^(lib)?steam_api/i.test(n)) ? " 스팀 DRM 이 걸린 게임은 스팀 없이 켜지지 않을 수 있습니다." : "");
  }
  routes.push(emu);

  // 3) 디컴파일 후 다시 빌드
  if (r.backend === "il2cpp" && r.backupManaged) {
    routes.push({
      key: "decompile",
      title: "디컴파일 후 다시 빌드 (PC + 유니티 경험 필요)",
      odds: "hard",
      summary: "IL2CPP 빌드지만, 실수로 함께 들어간 백업 폴더(…_BackUpThisFolder_ButDontShipItWithYourGame/Managed)에 C# 코드 DLL 이 남아 있습니다. " +
        "그 DLL 로 게임 코드를 복원할 수는 있지만, AssetRipper 가 이 구조를 바로 프로젝트로 만들어 주지는 않아 Mono 빌드보다 손이 더 많이 갑니다.",
      steps: [
        "ILSpy 로 백업 폴더의 Assembly-CSharp.dll 을 열어 코드가 온전한지 확인합니다.",
        "AssetRipper 로 그림·소리·장면을 프로젝트로 내보내고, 스크립트는 백업 DLL 을 디컴파일한 코드로 채웁니다.",
        `${sameVer}으로 열어 컴파일 오류를 고치고, 셰이더를 다시 지정한 뒤 WebGL/Android 로 빌드합니다. ${apkNote}`,
        "결과물은 개인적으로만 쓰세요. 남의 게임을 변환해 배포하면 저작권 침해입니다.",
      ],
      links: [LINKS.ilspy, LINKS.assetripper, LINKS.unityArchive],
    });
  } else if (r.backend === "il2cpp") {
    routes.push({
      key: "decompile",
      title: "디컴파일 후 다시 빌드",
      odds: "no",
      summary: "IL2CPP 빌드라 게임 코드가 PC용 기계어(GameAssembly)로 바뀌어 있습니다. AssetRipper 로 그림·소리·장면은 꺼낼 수 있지만 " +
        "스크립트는 이름만 있고 내용이 빈 껍데기라, 게임 로직을 처음부터 다시 짜야 합니다. 사실상 새로 만드는 일입니다.",
      steps: [],
      links: [LINKS.assetripper],
    });
  } else if (r.backend === "mono") {
    const pipelineHeavy = has("hdrp") || has("urp");
    const tooNew = ver && (ver[0] > 6000 || (ver[0] === 6000 && ver[1] >= 5)); // AssetRipper 는 6000.4 까지 지원(2026-10 기준)
    const odds = !pipelineHeavy && !tooNew && (size === "small" || size === "medium") && !r.nativePlugins.length ? "possible" : "hard";
    routes.push({
      key: "decompile",
      title: "디컴파일 후 다시 빌드 (PC + 유니티 경험 필요)",
      odds,
      summary: "Mono 빌드라 C# 코드가 남아 있어, AssetRipper 로 유니티 프로젝트(장면·프리팹·그림·소리·C# 스크립트)를 복원할 수 있습니다. " +
        "하지만 복원된 코드에는 컴파일 오류가 많고, 커스텀 셰이더는 빈 대체 셰이더로 나와 손으로 고쳐야 합니다. " +
        (odds === "possible"
          ? `이 게임은 스크립트 규모가 ${size === "small" ? "작고" : "중간 정도이고"} 기본 렌더 파이프라인이라 유니티를 다뤄 본 사람이면 ${size === "small" ? "몇 시간~며칠" : "며칠"}에 해 볼 만합니다.`
          : `이 게임은 ${[has("hdrp") && "HDRP", has("urp") && "URP 패키지", size === "large" && "큰 스크립트", !size && "크기를 알 수 없는 스크립트", r.nativePlugins.length && "네이티브 플러그인", tooNew && "AssetRipper 가 아직 지원하지 않는 최신 유니티 버전"].filter(Boolean).join("·")} 때문에 며칠~몇 주의 작업이 필요하고 중간에 포기하는 경우가 많습니다.`),
      steps: [
        "PC 에서 AssetRipper(무료)를 실행하고 File → Open Folder 로 게임 폴더 전체를 엽니다(브라우저 창으로 설정 화면이 열립니다).",
        "설정: Script Export Format = Decompilation(또는 Hybrid), Script Content Level = Level 2, Shader Export Format = Dummy. 그다음 Export → Unity Project.",
        `Unity Hub 로 ${sameVer}을 정확히 맞춰 설치합니다(보관소에서 받기). WebGL 또는 Android 빌드 모듈도 함께.`,
        "내보낸 프로젝트를 열면 안전 모드로 컴파일 오류가 납니다. 게임이 쓰던 패키지(TextMeshPro, Input System 등)를 설치하고 오류를 하나씩 고칩니다.",
        "단색·불투명하게(더미 셰이더) 또는 분홍색으로 보이는 재질은 실제 셰이더(Sprites/Default, Standard, URP/Lit 등)로 다시 지정합니다.",
        "에디터에서 끝까지 플레이해 보고, Windows 전용 DLL(스팀 등)은 빼거나 막습니다.",
        `WebGL 로 빌드해 zip 으로 UniPlay 에 넣거나(키 조작은 UniPlay 가상 패드로), Android 로 빌드합니다. ${apkNote}`,
        "결과물은 개인적으로만 쓰세요. 남의 게임을 변환해 배포하면 저작권 침해입니다.",
      ],
      links: [LINKS.assetripper, LINKS.unityArchive, LINKS.ilspy],
    });
  }

  // 4) 데이터 이식(같은 버전 안드로이드 플레이어에 _Data 넣기) — 자주 묻지만 안 되는 방법
  routes.push({
    key: "dataswap",
    title: "데이터만 안드로이드 플레이어에 옮겨 넣기",
    odds: "no",
    summary: r.backend === "il2cpp"
      ? "IL2CPP 빌드는 코드가 PC용 기계어라 옮길 수 없습니다."
      : "같은 버전의 유니티 안드로이드 앱에 데이터 폴더만 바꿔 넣는 방법이 가끔 거론되지만, 공개된 성공 사례가 거의 없습니다. " +
        (r.mobileShaders
          ? `이 빌드에는 ${r.graphicsAPIs.filter((g) => /OpenGLES/.test(g)).join("·")} 셰이더가 들어 있어 셰이더 문제는 덜하지만, `
          : r.nonD3DShaders
            ? `이 빌드의 ${r.graphicsAPIs.filter((g) => /Vulkan|OpenGLCore|Metal/.test(g)).join("·")} 셰이더는 데스크톱용이라 폰에서 그대로 된다는 보장이 없고, `
            : r.graphicsAPIs
              ? `이 빌드의 셰이더는 ${r.graphicsAPIs.join("·")} 전용이라(모바일용 셰이더 없음) 폰에서는 화면이 분홍/검정으로 깨지고, `
              : `${r.platform === "mac" ? "맥 빌드의 셰이더는 Metal/OpenGL" : r.platform === "linux" ? "리눅스 빌드의 셰이더는 데스크톱 OpenGL/Vulkan" : "Windows 빌드의 셰이더는 보통 Direct3D"} 전용이라 폰에서는 화면이 깨지기 쉽고, `) +
        "안드로이드 Mono 는 32비트 전용이라 갤럭시 S24 이후·픽셀 7 이후 같은 64비트 전용 폰에는 설치조차 안 되며, " +
        "유니티 버전이 정확히 같아야 하고 네이티브 플러그인·에셋 번들도 다시 만들어야 합니다. 결국 '디컴파일 후 다시 빌드'와 같은 작업이 됩니다.",
    steps: [],
    links: r.backend === "il2cpp" ? [] : [LINKS.unify],
  });

  return routes;
}
