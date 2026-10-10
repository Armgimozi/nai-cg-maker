/* Electron app.asar 리더 — zip.js 처럼 목록만 읽고 각 파일은 Blob 조각으로 연다.
 *
 * 구조(little-endian)
 *   0  u32 4                 ┐ 크기 pickle
 *   4  u32 headerSize        ┘ (= 아래 헤더 pickle 의 바이트 수)
 *   8  u32 payloadSize       ┐ 헤더 pickle
 *   12 u32 jsonLength        │
 *   16 JSON 문자열(+4바이트 정렬) ┘
 *   8 + headerSize 부터 파일 내용이 이어진다. 각 파일의 offset 은 여기 기준(문자열).
 *
 * JSON: { files: { 이름: { files:{…} } | { size, offset, unpacked?, executable?, integrity? } | { link } } }
 * unpacked 파일은 asar 밖의 app.asar.unpacked/ 폴더에 있다 → unpacked 콜백으로 찾는다.
 */

export class AsarError extends Error {}

/** 앞 16바이트만 보고 asar 인지 판단 */
export async function isAsar(blob) {
  if (!blob || blob.size < 24) return false;
  const dv = new DataView(await blob.slice(0, 17).arrayBuffer());
  const headerSize = dv.getUint32(4, true);
  const payload = dv.getUint32(8, true);
  const jsonLen = dv.getUint32(12, true);
  return dv.getUint32(0, true) === 4 && payload + 4 === headerSize && jsonLen <= payload - 4 &&
    8 + headerSize <= blob.size && dv.getUint8(16) === 0x7b; // '{'
}

/**
 * @param {Blob} blob app.asar
 * @param {(path:string)=>({size:number, open:()=>Promise<Blob|ReadableStream>})|null} [unpacked]
 *        asar 안에 없는(unpacked) 파일을 asar.unpacked 폴더에서 찾아 주는 함수
 * @returns {Promise<{path:string,size:number,open:()=>Promise<Blob|ReadableStream>}[]>}
 *          배열의 missingUnpacked 속성 = 못 찾은 unpacked 파일 경로들
 */
export async function readAsar(blob, unpacked) {
  if (!(await isAsar(blob))) throw new AsarError("asar 파일이 아니거나 손상되었습니다.");
  const dv = new DataView(await blob.slice(0, 16).arrayBuffer());
  const headerSize = dv.getUint32(4, true);
  const jsonLen = dv.getUint32(12, true);
  let header;
  try {
    header = JSON.parse(await blob.slice(16, 16 + jsonLen).text());
  } catch {
    throw new AsarError("asar 목록(JSON)을 읽지 못했습니다.");
  }
  const base = 8 + headerSize;
  const out = [];
  out.missingUnpacked = []; // asar 밖(app.asar.unpacked)에 있어야 하는데 못 찾은 파일
  const walk = (node, prefix, depth) => {
    if (!node || typeof node.files !== "object" || depth > 64) return;
    for (const [name, child] of Object.entries(node.files)) {
      if (!name || name === "." || name === ".." || /[\\/]/.test(name)) continue;
      const path = prefix ? `${prefix}/${name}` : name;
      if (child && typeof child.files === "object") { walk(child, path, depth + 1); continue; }
      if (!child || child.link != null) continue; // 심볼릭 링크는 건너뛴다(게임 실행에 필요 없음)
      const size = Number(child.size) || 0;
      if (child.unpacked) {
        const u = unpacked?.(path);
        if (u) out.push({ path, size: u.size, open: u.open });
        else out.missingUnpacked.push(path);
        continue;
      }
      const start = base + Number(child.offset || 0);
      if (!Number.isFinite(start) || start + size > blob.size) continue; // 잘린 파일
      out.push({ path, size, open: async () => blob.slice(start, start + size) });
    }
  };
  walk(header, "", 0);
  return out;
}
