/* 스트리밍 ZIP 리더 — 파일 전체를 메모리에 올리지 않는다.
 *
 * 중앙 디렉터리만 읽어 목록을 만들고, 각 항목은 필요할 때 Blob 조각을 잘라
 *   - 저장(Stored)  → 그 Blob 조각 그대로(복사 0)
 *   - 압축(Deflate) → DecompressionStream('deflate-raw') 스트림
 * 으로 연다. 수백 MB 짜리 게임 zip 도 폰에서 다룰 수 있게 하려는 것.
 *
 * 지원: ZIP64, 앞에 데이터가 붙은 zip(자동 압축풀림 exe 등), UTF-8 플래그 /
 *       Info-ZIP 유니코드 경로, 플래그 없는 한국어(CP949)·일본어(Shift_JIS) 파일명.
 * 미지원: 암호 zip, Deflate64/BZip2/LZMA/Zstd 압축, 분할 zip.
 */

export class ZipError extends Error {}

const SIG_EOCD = 0x06054b50;
const SIG_EOCD64_LOC = 0x07064b50;
const SIG_EOCD64 = 0x06064b50;
const SIG_CEN = 0x02014b50;
const SIG_LOC = 0x04034b50;

const METHOD_NAMES = { 9: "Deflate64", 12: "BZip2", 14: "LZMA", 93: "Zstandard", 95: "XZ", 98: "PPMd", 99: "AES 암호화" };

async function bytes(blob, start, end) {
  return new Uint8Array(await blob.slice(start, end).arrayBuffer());
}

function u64(dv, off) {
  const v = dv.getBigUint64(off, true);
  if (v > BigInt(Number.MAX_SAFE_INTEGER)) throw new ZipError("ZIP64 값이 너무 큽니다.");
  return Number(v);
}

/** 파일 끝에서 EOCD(+ZIP64) 레코드를 찾아 중앙 디렉터리 위치를 돌려준다. */
async function locateCentralDirectory(blob) {
  const size = blob.size;
  if (size < 22) throw new ZipError("zip 파일이 아니거나 비어 있습니다.");
  const tailLen = Math.min(size, 22 + 0xffff + 20);
  const tailStart = size - tailLen;
  const tail = await bytes(blob, tailStart, size);
  const dv = new DataView(tail.buffer);
  let at = -1;
  for (let i = tail.length - 22; i >= 0; i--) {
    if (dv.getUint32(i, true) === SIG_EOCD) { at = i; break; }
  }
  if (at < 0) throw new ZipError("zip 파일이 아니거나 손상되었습니다. (7z·rar 는 지원하지 않아요 — zip 으로 다시 압축해 주세요)");
  if (dv.getUint16(at + 4, true) !== 0 || dv.getUint16(at + 6, true) !== 0) {
    throw new ZipError("분할 압축(.z01 등)된 zip 은 지원하지 않습니다. 하나의 zip 으로 다시 압축해 주세요.");
  }
  let count = dv.getUint16(at + 10, true);
  let cdSize = dv.getUint32(at + 12, true);
  let cdOffset = dv.getUint32(at + 16, true);
  const eocdAbs = tailStart + at;

  // ZIP64: EOCD 바로 앞 20바이트에 locator 가 있으면 64비트 값을 쓴다.
  if (at >= 20 && dv.getUint32(at - 20, true) === SIG_EOCD64_LOC) {
    const rec64Off = u64(dv, at - 20 + 8);
    const rec = await bytes(blob, rec64Off, rec64Off + 56);
    const d64 = new DataView(rec.buffer);
    if (d64.getUint32(0, true) === SIG_EOCD64) {
      count = u64(d64, 32);
      cdSize = u64(d64, 40);
      cdOffset = u64(d64, 48);
      // 앞붙은 데이터 보정은 ZIP64 레코드 위치 기준
      const delta = rec64Off - cdSize - cdOffset;
      return { count, cdSize, cdOffset: cdOffset + Math.max(0, delta), delta: Math.max(0, delta) };
    }
  }
  // 자동 압축풀림 exe 처럼 앞에 데이터가 붙어 있으면 오프셋이 그만큼 밀린다.
  const delta = Math.max(0, eocdAbs - cdSize - cdOffset);
  return { count, cdSize, cdOffset: cdOffset + delta, delta };
}

const utf8Fatal = new TextDecoder("utf-8", { fatal: true });

function fatalDecoder(label) {
  try { return new TextDecoder(label, { fatal: true }); } catch { return null; }
}

/** 플래그 없는 파일명들을 한 번에 보고 인코딩을 고른다(한 zip 안에서는 보통 하나로 통일됨). */
function pickLegacyDecoder(rawNames) {
  const nonAscii = rawNames.filter((b) => b.some((x) => x > 0x7f));
  if (!nonAscii.length) return utf8Fatal;
  const lang = (globalThis.navigator?.language || "ko").toLowerCase();
  const order = lang.startsWith("ja")
    ? ["utf-8", "shift_jis", "euc-kr", "gbk"]
    : lang.startsWith("zh") ? ["utf-8", "gbk", "big5", "euc-kr", "shift_jis"]
      : ["utf-8", "euc-kr", "shift_jis", "gbk"];
  for (const label of order) {
    const dec = fatalDecoder(label);
    if (!dec) continue;
    try { nonAscii.forEach((b) => dec.decode(b)); return dec; } catch { /* 다음 후보 */ }
  }
  return new TextDecoder("windows-1252");
}

function cleanPath(name) {
  let p = name.replace(/\\/g, "/").replace(/^\.?\/+/, "");
  if (p.split("/").some((s) => s === "..")) return null; // 경로 탈출 항목은 버린다
  return p;
}

/**
 * zip(Blob/File)의 항목 목록을 읽는다.
 * @returns {Promise<Array<{path:string,size:number,compressedSize:number,method:number,dir:boolean,encrypted:boolean,open:()=>Promise<Blob|ReadableStream>}>>}
 */
export async function readZip(blob) {
  const { count, cdSize, cdOffset, delta } = await locateCentralDirectory(blob);
  const cd = await bytes(blob, cdOffset, cdOffset + cdSize);
  const dv = new DataView(cd.buffer);
  const raw = [];
  let p = 0;
  for (let n = 0; n < count && p + 46 <= cd.length; n++) {
    if (dv.getUint32(p, true) !== SIG_CEN) throw new ZipError("zip 중앙 디렉터리가 손상되었습니다.");
    const flags = dv.getUint16(p + 8, true);
    const method = dv.getUint16(p + 10, true);
    let compressedSize = dv.getUint32(p + 20, true);
    let size = dv.getUint32(p + 24, true);
    const nameLen = dv.getUint16(p + 28, true);
    const extraLen = dv.getUint16(p + 30, true);
    const commentLen = dv.getUint16(p + 32, true);
    let localOffset = dv.getUint32(p + 42, true);
    const nameBytes = cd.subarray(p + 46, p + 46 + nameLen);
    let unicodeName = null;

    let e = p + 46 + nameLen;
    const extraEnd = e + extraLen;
    while (e + 4 <= extraEnd) {
      const id = dv.getUint16(e, true);
      const len = dv.getUint16(e + 2, true);
      let q = e + 4;
      if (id === 0x0001) { // ZIP64 확장: 0xFFFFFFFF 인 값만 순서대로 들어 있다
        if (size === 0xffffffff && q + 8 <= e + 4 + len) { size = u64(dv, q); q += 8; }
        if (compressedSize === 0xffffffff && q + 8 <= e + 4 + len) { compressedSize = u64(dv, q); q += 8; }
        if (localOffset === 0xffffffff && q + 8 <= e + 4 + len) { localOffset = u64(dv, q); q += 8; }
      } else if (id === 0x7075 && len > 5) { // Info-ZIP 유니코드 경로
        try { unicodeName = utf8Fatal.decode(cd.subarray(e + 9, e + 4 + len)); } catch { /* 무시 */ }
      }
      e += 4 + len;
    }
    raw.push({ flags, method, compressedSize, size, localOffset: localOffset + delta, nameBytes, unicodeName });
    p = extraEnd + commentLen;
  }

  const legacy = pickLegacyDecoder(raw.filter((r) => !(r.flags & 0x800) && !r.unicodeName).map((r) => r.nameBytes));
  const utf8 = new TextDecoder("utf-8");

  const out = [];
  for (const r of raw) {
    let name = r.unicodeName;
    if (!name) {
      if (r.flags & 0x800) name = utf8.decode(r.nameBytes);
      else { try { name = legacy.decode(r.nameBytes); } catch { name = utf8.decode(r.nameBytes); } }
    }
    const path = cleanPath(name);
    if (path === null || path === "") continue;
    const dir = path.endsWith("/");
    out.push({
      path: dir ? path.slice(0, -1) : path,
      dir,
      size: r.size,
      compressedSize: r.compressedSize,
      method: r.method,
      encrypted: !!(r.flags & 0x1),
      open: () => openEntry(blob, r, path),
    });
  }
  return out;
}

async function openEntry(blob, r, path) {
  if (r.flags & 0x1) throw new ZipError(`암호가 걸린 zip 은 지원하지 않습니다: ${path}`);
  const head = await bytes(blob, r.localOffset, r.localOffset + 30);
  const dv = new DataView(head.buffer);
  if (dv.getUint32(0, true) !== SIG_LOC) throw new ZipError(`zip 항목이 손상되었습니다: ${path}`);
  const start = r.localOffset + 30 + dv.getUint16(26, true) + dv.getUint16(28, true);
  const part = blob.slice(start, start + r.compressedSize);
  if (r.method === 0) return part;
  if (r.method === 8) {
    if (typeof DecompressionStream === "undefined") {
      throw new ZipError("이 브라우저는 압축 해제(DecompressionStream)를 지원하지 않습니다. Chrome/Safari 를 최신으로 업데이트해 주세요.");
    }
    return part.stream().pipeThrough(new DecompressionStream("deflate-raw"));
  }
  const m = METHOD_NAMES[r.method] || `방식 ${r.method}`;
  throw new ZipError(`지원하지 않는 압축 방식(${m})입니다: ${path}\n일반 zip(Deflate)으로 다시 압축해 주세요.`);
}
