#!/usr/bin/env python3
"""art/png/*.png 를 Roblox Open Cloud Assets API 로 올리고 src/shared/ImageIds.luau 를 채운다.

    python3 tools/upload_images.py --dry-run        # 무엇을 올릴지 보기만 (네트워크 없음)
    python3 tools/upload_images.py                  # 바뀐 그림만 올리고 ImageIds.luau 갱신
    python3 tools/upload_images.py --only coin dice # 일부만
    python3 tools/upload_images.py some/dir         # 다른 폴더

- 표준 라이브러리만 씀(urllib, uuid). Python 3.8+.
- 인증: 환경변수 ROBLOX_API_KEY 가 있으면 `x-api-key` 헤더로 보냄. 없으면 키 헤더 없이 보냄
  (프록시가 apis.roblox.com 요청에 키를 대신 붙여 주는 환경용).
- assetType 은 기본 "Image". Image 에셋 Id 는 ImageLabel.Image 에 바로 쓸 수 있다.
  ("Decal" 로 올리면 돌아오는 Id 가 데칼 Id 라서 ImageLabel 에 안 나옴 -> 안의 Image Id 를 따로 찾아야 함.)
- tools/.image_upload_cache.json 에 파일 SHA-256 -> 에셋 Id 를 적어 두고, 내용이 같은 그림은 다시 올리지 않음.
- 검수(moderation)에서 거절된 그림은 자동으로 다시 올리지 않음(같은 그림을 반복해서 올리면 계정 제재 위험).
  고친 뒤 파일이 바뀌면 SHA 가 달라져 새로 올라감. 그대로 다시 올리려면 --force.
- 비용 안전장치: creationContext.expectedPrice = 0 (요금이 붙으면 올리지 않고 400 으로 실패).

API: POST https://apis.roblox.com/assets/v1/assets (multipart: request=JSON, fileContent=PNG)
     GET  https://apis.roblox.com/assets/v1/operations/{operationId}
     GET  https://apis.roblox.com/assets/v1/assets/{assetId}   (검수 상태 다시 확인)
필요 권한: API 키에 "Assets" API 의 Read + Write (OAuth 로는 asset:read + asset:write).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import email.utils
import gzip
import hashlib
import json
import os
import re
import struct
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "art" / "png"
DEFAULT_OUT = ROOT / "src" / "shared" / "ImageIds.luau"
DEFAULT_CACHE = ROOT / "tools" / ".image_upload_cache.json"
DEFAULT_USER_ID = 2038945024

API = "https://apis.roblox.com"
CREATE_URL = API + "/assets/v1/assets"
OPERATION_URL = API + "/assets/v1/operations/{}"
ASSET_URL = API + "/assets/v1/assets/{}"
# 문서화된 Open Cloud 레퍼런스에는 없지만 도구들(rocas 등)이 쓰는 경로. Decal -> Image Id 찾기에만 씀.
DELIVERY_URL = API + "/asset-delivery-api/v1/assetId/{}"

MAX_BYTES = 20 * 1024 * 1024  # 요청 1번에 20 MB (usage-assets 문서)
MAX_SIDE = 8000  # "8000x8000 보다 작아야 함"
MAX_DISPLAY_NAME = 50
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
USER_AGENT = "LandmarkRNG-upload_images/1.0 (+python urllib)"

# 레이트 리밋(문서): Create Asset 120/분, Get Operation 300/분 (API 키 주인 단위). 여유 있게 벌림.
MIN_GAP = {"POST": 0.6, "GET": 0.25}
_last_call = {"POST": 0.0, "GET": 0.0}

CACHE_VERSION = 1


# --------------------------------------------------------------------------- 출력


def _cell_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _cell_width(text))


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [_cell_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _cell_width(cell))
    # 마지막 칸(메모)은 채우지 않음
    def line(cells: list[str]) -> str:
        return "  ".join(_pad(c, widths[i]) if i < len(cells) - 1 else c for i, c in enumerate(cells)).rstrip()

    print(line(headers))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(line(row))


def log(msg: str) -> None:
    print(msg, flush=True)


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------- HTTP


class ApiError(Exception):
    def __init__(self, status: int, body: bytes | str, url: str):
        self.status = status
        self.body = body if isinstance(body, str) else body.decode("utf-8", "replace")
        self.url = url
        super().__init__(f"HTTP {status} {url}: {self.message}")

    @property
    def message(self) -> str:
        try:
            data = json.loads(self.body)
        except (ValueError, TypeError):
            return self.body.strip()[:300]
        if isinstance(data, dict):
            if data.get("message"):
                return str(data["message"])
            errs = data.get("errors")
            if isinstance(errs, list) and errs and isinstance(errs[0], dict):
                return str(errs[0].get("message", errs[0]))
        return self.body.strip()[:300]


def api_key_headers() -> dict[str, str]:
    key = os.environ.get("ROBLOX_API_KEY", "").strip()
    return {"x-api-key": key} if key else {}


def _wait_from_headers(headers, attempt: int) -> float:
    """429 때 기다릴 초. retry-after(초 또는 HTTP 날짜) -> x-ratelimit-reset -> 지수 백오프."""
    retry_after = headers.get("retry-after") if headers is not None else None
    if retry_after:
        try:
            return max(0.5, float(retry_after))
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(retry_after)
                return max(0.5, when.timestamp() - time.time())
            except (TypeError, ValueError):
                pass
    reset = headers.get("x-ratelimit-reset") if headers is not None else None
    if reset:
        try:
            return max(0.5, float(str(reset).split(",")[0].strip()))
        except ValueError:
            pass
    return float(min(60, 2 ** attempt))


def http(
    method: str,
    url: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    *,
    auth: bool = True,
    retry_errors: bool = True,
    max_attempts: int = 6,
) -> tuple[int, bytes]:
    """요청 1번. 429 는 항상 기다렸다 다시 시도. retry_errors 면 5xx/네트워크 오류도 재시도(POST 는 끔)."""
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if auth:
        hdrs.update(api_key_headers())
    if headers:
        hdrs.update(headers)
    kind = "POST" if method == "POST" else "GET"

    for attempt in range(max_attempts):
        gap = MIN_GAP[kind] - (time.monotonic() - _last_call[kind])
        if gap > 0:
            time.sleep(gap)
        _last_call[kind] = time.monotonic()

        req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            data = err.read()
            last = attempt == max_attempts - 1
            if err.code == 429 and not last:
                wait = _wait_from_headers(err.headers, attempt)
                log(f"    (너무 빠름 429 - {wait:.1f}초 기다렸다 다시 시도)")
                time.sleep(wait)
                continue
            if retry_errors and err.code in (500, 502, 503, 504) and not last:
                time.sleep(min(30, 2 ** attempt))
                continue
            raise ApiError(err.code, data, url) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            if retry_errors and attempt < max_attempts - 1:
                time.sleep(min(30, 2 ** attempt))
                continue
            reason = getattr(err, "reason", err)
            raise ApiError(0, f"연결 실패: {reason}", url) from None
    raise ApiError(0, "재시도 횟수 초과", url)


def http_json(method: str, url: str, **kw) -> dict:
    _, data = http(method, url, **kw)
    try:
        parsed = json.loads(data.decode("utf-8"))
    except ValueError:
        raise ApiError(200, data, url) from None
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def build_multipart(request_json: str, filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    """curl --form 'request=...' --form 'fileContent=@file;type=image/png' 과 같은 본문."""
    boundary = "----LandmarkRNG" + uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="request"\r\n'
        "\r\n"
    ).encode("utf-8") + request_json.encode("utf-8") + b"\r\n"
    file_head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="fileContent"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n"
        "\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + file_head + content + tail, f"multipart/form-data; boundary={boundary}"


# --------------------------------------------------------------------------- Open Cloud


def norm_enum(value, *prefixes: str) -> str:
    """'ASSET_TYPE_DECAL' / 'Decal' -> 'decal', 'MODERATION_STATE_APPROVED' / 'Approved' -> 'approved'."""
    text = str(value or "").strip().lower()
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text


def operation_id_of(resp: dict) -> str | None:
    if resp.get("operationId"):
        return str(resp["operationId"])
    path = str(resp.get("path") or "")
    if path.startswith("operations/"):
        return path.split("/", 1)[1]
    return None


def create_asset(name: str, filename: str, content: bytes, user_id: int, asset_type: str) -> dict:
    request = {
        "assetType": asset_type,
        "displayName": name[:MAX_DISPLAY_NAME],
        "description": f"Landmark RNG UI image: {name}",
        "creationContext": {
            "creator": {"userId": str(user_id)},
            "expectedPrice": 0,
        },
    }
    body, ctype = build_multipart(json.dumps(request), filename, content, "image/png")
    # POST 는 5xx/연결 오류에 재시도하지 않음(이미 올라갔는데 또 올리는 일 방지). 429 는 거절된 요청이라 안전.
    return http_json("POST", CREATE_URL, body=body, headers={"Content-Type": ctype}, retry_errors=False)


def asset_fields(asset: dict) -> dict:
    asset_id = asset.get("assetId")
    if not asset_id:
        path = str(asset.get("path") or "")
        if path.startswith("assets/"):
            asset_id = path.split("/")[1]
    return {
        "assetId": str(asset_id) if asset_id else None,
        "returnedType": norm_enum(asset.get("assetType"), "asset_type_"),
        "moderation": norm_enum((asset.get("moderationResult") or {}).get("moderationState"), "moderation_state_"),
    }


def extract_image_id(blob: bytes) -> str | None:
    """Decal 본체(rbxmx XML 또는 rbxm)에서 Texture 이미지 Id 를 꺼냄."""
    if blob[:2] == b"\x1f\x8b":
        try:
            blob = gzip.decompress(blob)
        except OSError:
            pass
    text = blob.decode("latin-1")
    m = re.search(r'<Content\s+name="Texture">\s*<url>([^<]*)</url>', text, re.I)
    candidates = [m.group(1)] if m else []
    candidates.append(text)
    for chunk in candidates:
        found = re.search(r"(?:rbxassetid://|[?&]id=)(\d+)", chunk, re.I)
        if found:
            return found.group(1)
    return None


def resolve_decal_image_id(decal_id: str, attempts: int = 4) -> str | None:
    """Decal Id -> 안에 든 Image Id (최선 노력; 공식 레퍼런스에 없는 경로라 실패할 수 있음)."""
    last = None
    for i in range(attempts):
        try:
            info = http_json("GET", DELIVERY_URL.format(decal_id))
            location = info.get("location")
            if not location and isinstance(info.get("locations"), list):
                location = next((x.get("location") for x in info["locations"] if isinstance(x, dict) and x.get("location")), None)
            if location:
                # CDN 주소에는 키를 보내지 않음
                _, blob = http("GET", location, auth=False, headers={"Accept": "*/*"})
                image_id = extract_image_id(blob)
                if image_id:
                    return image_id
        except ApiError as err:
            last = err
        time.sleep(2 + i * 2)
    if last:
        log(f"    Decal {decal_id} 의 Image Id 를 못 찾음: {last.message}")
    return None


# --------------------------------------------------------------------------- 파일 / 캐시


def png_size(content: bytes) -> tuple[int, int]:
    if content[:8] != PNG_SIGNATURE or content[12:16] != b"IHDR":
        raise ValueError("PNG 파일이 아님")
    return struct.unpack(">II", content[16:24])


def human_size(n: int) -> str:
    return f"{n / 1024:.1f}KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f}MB"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data
    except FileNotFoundError:
        pass
    except ValueError:
        log(f"경고: {rel(path)} 를 읽을 수 없어 빈 캐시로 시작합니다(파일은 덮어씀).")
    return {"version": CACHE_VERSION, "entries": {}}


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", "utf-8")
    os.replace(tmp, path)


class Item:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem
        self.content = b""
        self.sha = ""
        self.size = 0
        self.dims = (0, 0)
        self.status = ""  # CACHED / UPLOADED / PENDING / REJECTED / FAILED / SKIPPED / DRY-RUN
        self.note = ""
        self.entry: dict | None = None  # 캐시 항목 (cache["entries"][sha])

    @property
    def image_id(self) -> str | None:
        return (self.entry or {}).get("imageId")

    @property
    def moderation(self) -> str:
        return (self.entry or {}).get("moderation") or ""


def entry_matches(entry: dict, user_id: int, asset_type: str) -> bool:
    return str(entry.get("userId")) == str(user_id) and entry.get("assetType") == asset_type


# --------------------------------------------------------------------------- ImageIds.luau

LINE_RE = re.compile(
    r'^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*"(?P<val>[^"\n]*)"[ \t]*,?[ \t]*(?P<comment>--.*)?$'
)
OPEN_RE = re.compile(r"^\s*(return\s*\{|local\s+[A-Za-z_]\w*\s*(:[^=]*)?=\s*\{)\s*(--.*)?$")

FRESH_HEADER = """--!strict
-- 그림 에셋 Id 표 (이름 -> "rbxassetid://<숫자>"). tools/upload_images.py 가 채웁니다(손으로 넣어도 됨).
-- 빈 문자열이면 코드로 그린 기본 모양을 씁니다.
"""


def luau_value(image_id: str | None) -> str:
    return f"rbxassetid://{image_id}" if image_id else ""


def _find_table(lines: list[str]) -> tuple[int, int] | None:
    start = next((i for i, l in enumerate(lines) if OPEN_RE.match(l)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() in ("}", "})")), None)
    return (start, end) if end is not None else None


def update_luau(text: str | None, values: dict[str, str], rewrite: bool) -> tuple[str, list[str]]:
    """values: 이름 -> "rbxassetid://.." 또는 "" (바꿀 것만). 반환: (새 본문, 바뀐 설명 목록)."""
    changes: list[str] = []
    if text is None:
        body = [f'\t{k} = "{values[k]}",' for k in sorted(values)]
        changes += [f"+ {k} = \"{values[k]}\"" for k in sorted(values)]
        return FRESH_HEADER + "\nlocal ImageIds: { [string]: string } = {\n" + "\n".join(body) + "\n}\n\nreturn ImageIds\n", changes

    lines = text.split("\n")
    span = _find_table(lines)
    if span is None:
        raise ValueError("ImageIds.luau 에서 표(`return {` 또는 `local X = {` ... `}`)를 찾지 못함")
    start, end = span

    existing: dict[str, str] = {}
    for i in range(start + 1, end):
        m = LINE_RE.match(lines[i])
        if m:
            existing[m.group("key")] = m.group("val")

    if rewrite:
        merged = dict(existing)
        merged.update(values)
        for k in sorted(merged):
            if existing.get(k) != merged[k]:
                changes.append(f"{'~' if k in existing else '+'} {k} = \"{merged[k]}\"")
        body = [f'\t{k} = "{merged[k]}",' for k in sorted(merged)]
        return "\n".join(lines[: start + 1] + body + lines[end:]), changes

    seen: set[str] = set()
    for i in range(start + 1, end):
        m = LINE_RE.match(lines[i])
        if not m:
            continue
        key = m.group("key")
        seen.add(key)
        if key in values and m.group("val") != values[key]:
            comment = m.group("comment")
            lines[i] = f'{m.group("indent")}{key} = "{values[key]}",' + (f" {comment}" if comment else "")
            changes.append(f"~ {key} = \"{values[key]}\"")
    missing = sorted(k for k in values if k not in seen)
    if missing:
        indent = "\t"
        for i in range(start + 1, end):
            m = LINE_RE.match(lines[i])
            if m:
                indent = m.group("indent")
                break
        extra = [f"{indent}-- upload_images.py 가 추가 (art/png 에만 있던 이름)"]
        extra += [f'{indent}{k} = "{values[k]}",' for k in missing]
        lines[end:end] = extra
        changes += [f"+ {k} = \"{values[k]}\"" for k in missing]
    return "\n".join(lines), changes


# --------------------------------------------------------------------------- 메인 흐름


def collect(dir_path: Path, only: list[str] | None) -> list[Item]:
    files = sorted(p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    if only:
        wanted = set(only)
        unknown = wanted - {p.stem for p in files}
        if unknown:
            log(f"경고: {rel(dir_path)} 에 없는 이름: {', '.join(sorted(unknown))}")
        files = [p for p in files if p.stem in wanted]
    items = []
    for p in files:
        item = Item(p)
        items.append(item)
        if not NAME_RE.match(item.name):
            item.status, item.note = "SKIPPED", "파일 이름은 영문/숫자/_ 만 (Luau 키로 씀)"
            continue
        item.content = p.read_bytes()
        item.size = len(item.content)
        item.sha = hashlib.sha256(item.content).hexdigest()
        try:
            item.dims = png_size(item.content)
        except ValueError as err:
            item.status, item.note = "SKIPPED", str(err)
            continue
        if item.size > MAX_BYTES:
            item.status, item.note = "SKIPPED", "20MB 넘음"
        elif max(item.dims) >= MAX_SIDE:
            item.status, item.note = "SKIPPED", "8000px 보다 작아야 함"
    return items


def refresh_moderation(item: Item) -> None:
    """검수 중이던 항목의 상태를 다시 확인."""
    try:
        info = asset_fields(http_json("GET", ASSET_URL.format(item.entry["assetId"])))
    except ApiError as err:
        item.note = f"검수 상태 확인 실패: {err.message}"
        return
    if info["moderation"]:
        item.entry["moderation"] = info["moderation"]
        item.entry["checkedAt"] = now_iso()


def finish_operation(item: Item, op: dict, asset_type: str) -> None:
    entry = item.entry
    if op.get("error"):
        err = op["error"]
        entry["error"] = str(err.get("message") if isinstance(err, dict) else err)
        entry.pop("operationId", None)
        item.status, item.note = "FAILED", entry["error"]
        return
    info = asset_fields(op.get("response") or {})
    if not info["assetId"]:
        item.status, item.note = "FAILED", "operation 이 끝났는데 assetId 가 없음"
        return
    entry.pop("operationId", None)
    entry.pop("error", None)
    entry["assetId"] = info["assetId"]
    entry["returnedType"] = info["returnedType"] or asset_type.lower()
    entry["moderation"] = info["moderation"] or "unknown"
    entry["uploadedAt"] = now_iso()
    if entry["returnedType"] == "decal":
        image_id = resolve_decal_image_id(info["assetId"])
        entry["imageId"] = image_id
        if not image_id:
            item.status = "FAILED"
            item.note = f"Decal {info['assetId']} 로 올라감 - ImageLabel 용 Image Id 를 못 찾음 (--asset-type Image 로 다시)"
            return
    else:
        entry["imageId"] = info["assetId"]
    item.status = "REJECTED" if entry["moderation"] == "rejected" else "UPLOADED"


def poll_pending(pending: list[Item], asset_type: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    delay = 1.0
    while pending:
        time.sleep(delay)
        still = []
        for item in pending:
            try:
                op = http_json("GET", OPERATION_URL.format(item.entry["operationId"]))
            except ApiError as err:
                if err.status == 404:
                    item.entry.pop("operationId", None)
                    item.status, item.note = "FAILED", "operation 을 찾을 수 없음(만료?) - 다시 실행하면 새로 올림"
                    continue
                item.note = f"확인 실패: {err.message}"
                still.append(item)
                continue
            if op.get("done"):
                finish_operation(item, op, asset_type)
            else:
                still.append(item)
        pending = still
        if pending and time.monotonic() + delay > deadline:
            for item in pending:
                item.status = "PENDING"
                item.note = "아직 처리 중 - 잠시 뒤 다시 실행하면 이어서 확인(다시 올리지 않음)"
            return
        delay = min(delay * 1.6, 8.0)


def network_phase(args, cache: dict, cache_path: Path, to_upload: list[Item], to_resume: list[Item], to_refresh: list[Item]) -> None:
    entries: dict = cache["entries"]
    # 2) 검수 중이던 것 상태 갱신
    for item in to_refresh:
        refresh_moderation(item)
        if item.moderation == "rejected":
            item.status, item.note = "REJECTED", "검수 거절됨(확인 결과)"
    # 3) 새로 올리기 (전부 먼저 보내고, 4) 에서 한꺼번에 기다림)
    for n, item in enumerate(to_upload, 1):
        log(f"  올리는 중 [{n}/{len(to_upload)}] {item.name} ({human_size(item.size)})")
        try:
            resp = create_asset(item.name, item.path.name, item.content, args.user_id, args.asset_type)
        except ApiError as err:
            item.status, item.note = "FAILED", f"HTTP {err.status}: {err.message}"
            if err.status in (401, 403):
                log("  권한 오류 - API 키에 Assets(Read+Write) 권한이 있는지, 키 주인이 --user-id 와 같은지 확인하세요. 중단합니다.")
                break
            continue
        item.entry = {
            "names": [item.name],
            "file": rel(item.path),
            "userId": str(args.user_id),
            "assetType": args.asset_type,
            "sha256": item.sha,
            "submittedAt": now_iso(),
        }
        entries[item.sha] = item.entry
        if resp.get("done"):
            finish_operation(item, resp, args.asset_type)
        else:
            op_id = operation_id_of(resp)
            if not op_id:
                item.status, item.note = "FAILED", f"operation Id 가 없는 응답: {json.dumps(resp)[:200]}"
                del entries[item.sha]
                continue
            item.entry["operationId"] = op_id
            item.status = "PENDING"
            to_resume.append(item)
        save_cache(cache_path, cache)  # 중간에 끊겨도 같은 그림을 두 번 올리지 않게 바로 저장
    for item in to_upload:
        if not item.status:
            item.status, item.note = "FAILED", "권한 오류로 중단 - 올리지 않음"
    # 4) operation 기다리기
    if to_resume:
        log(f"  처리 기다리는 중 ({len(to_resume)}개, 최대 {args.timeout:.0f}초)")
        poll_pending(to_resume, args.asset_type, args.timeout)
    save_cache(cache_path, cache)


def run(args: argparse.Namespace) -> int:
    src_dir = Path(args.dir).resolve()
    out_path = Path(args.out).resolve()
    cache_path = Path(args.cache).resolve()
    if not src_dir.is_dir():
        log(f"폴더가 없음: {src_dir}")
        return 2

    items = collect(src_dir, args.only)
    if not items:
        log(f"{rel(src_dir)} 에 PNG 가 없습니다.")
        return 1

    cache = load_cache(cache_path)
    entries: dict = cache["entries"]
    key_mode = "ROBLOX_API_KEY 환경변수" if api_key_headers() else "키 헤더 없음(프록시가 붙여 주는 환경 가정)"
    log(f"폴더 {rel(src_dir)} · PNG {len(items)}개 · creator userId {args.user_id} · assetType {args.asset_type} · {key_mode}")
    if args.dry_run:
        log("--dry-run: 네트워크 요청 없음, 파일 안 씀")

    # 1) 캐시 확인
    to_upload: list[Item] = []
    to_resume: list[Item] = []
    to_refresh: list[Item] = []
    first_by_sha: dict[str, Item] = {}
    dupes: list[tuple[Item, Item]] = []  # (같은 내용의 두 번째 파일, 첫 번째 파일)
    for item in items:
        if item.status == "SKIPPED":
            continue
        if item.sha in first_by_sha:
            dupes.append((item, first_by_sha[item.sha]))
            continue
        first_by_sha[item.sha] = item
        entry = entries.get(item.sha)
        if entry is not None and not entry_matches(entry, args.user_id, args.asset_type):
            entry = None  # 다른 계정/타입으로 올린 기록 -> 새로 올림 (기록은 새 결과로 덮어씀)
        if entry is not None and not args.force:
            item.entry = entry
            names = set(entry.get("names") or [])
            if item.name not in names:
                entry["names"] = sorted(names | {item.name})
            if entry.get("operationId") and not entry.get("assetId"):
                item.status, item.note = "PENDING", "지난번 업로드 이어서 확인"
                to_resume.append(item)
                continue
            if entry.get("imageId"):
                if entry.get("moderation") == "rejected":
                    item.status, item.note = "REJECTED", "검수 거절 - 그림을 고치거나 --force"
                else:
                    item.status = "CACHED"
                    if entry.get("moderation") in ("reviewing", "unknown", ""):
                        to_refresh.append(item)
                continue
        to_upload.append(item)

    if args.dry_run:
        for item in to_upload:
            item.status, item.note = "DRY-RUN", "올릴 예정"
        for item in to_resume:
            item.note = "operation 이어서 확인 예정"
        for item in to_refresh:
            item.note = "검수 상태 다시 확인 예정"
    else:
        try:
            network_phase(args, cache, cache_path, to_upload, to_resume, to_refresh)
        finally:
            save_cache(cache_path, cache)

    # 같은 내용의 파일은 한 번만 올리고 같은 Id 를 씀
    for item, first in dupes:
        item.entry, item.status = first.entry, first.status
        item.note = f"{first.name} 와 같은 그림"
        if item.entry is not None:
            item.entry["names"] = sorted(set(item.entry.get("names") or []) | {item.name})

    # 5) ImageIds.luau
    values: dict[str, str] = {}
    for item in items:
        if item.status in ("CACHED", "UPLOADED") and item.image_id:
            values[item.name] = luau_value(item.image_id)
        elif item.status == "REJECTED":
            values[item.name] = ""  # 거절된 그림은 빈칸 -> 코드로 그린 기본 모양 사용
    try:
        old_text = out_path.read_text("utf-8")
    except FileNotFoundError:
        old_text = None
    new_text, changes = update_luau(old_text, values, args.rewrite)
    wrote = False
    if new_text != old_text and not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(new_text, "utf-8")
        wrote = True

    # 6) 표
    print()
    rows = []
    for item in items:
        size = f"{item.dims[0]}x{item.dims[1]} {human_size(item.size)}" if item.dims[0] else "-"
        asset_id = (item.entry or {}).get("imageId") or (item.entry or {}).get("assetId") or "-"
        mod = {"approved": "승인", "reviewing": "검수 중", "rejected": "거절", "unknown": "?"}.get(item.moderation, item.moderation or "-")
        rows.append([item.name, size, item.status, asset_id, mod, item.note])
    print_table(["이름", "크기", "결과", "Image Id", "검수", "메모"], rows)

    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    print()
    log("합계: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if old_text is not None:
        existing_keys = {m.group("key") for m in (LINE_RE.match(l) for l in old_text.split("\n")) if m}
        no_png = sorted(existing_keys - {i.name for i in items}) if not args.only else []
        if no_png:
            log(f"그림 파일이 없는 키(그대로 둠): {', '.join(no_png)}")
    if changes:
        verb = "바꿀 예정" if args.dry_run else ("바꿈" if wrote else "변경 없음")
        log(f"{rel(out_path)} {verb}: {len(changes)}줄")
        for c in changes[:60]:
            log(f"    {c}")
    else:
        log(f"{rel(out_path)}: 바뀐 줄 없음")
    if any(i.moderation in ("reviewing", "unknown") for i in items if i.entry):
        log("검수 중인 그림은 승인되기 전까지 게임에서 안 보일 수 있습니다. 나중에 다시 실행하면 상태를 확인합니다.")
    if args.dry_run:
        return 0
    failed = [i for i in items if i.status in ("FAILED", "PENDING")]
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description="PNG 를 Roblox Open Cloud 로 올리고 src/shared/ImageIds.luau 를 채웁니다.")
    p.add_argument("dir", nargs="?", default=str(DEFAULT_DIR), help=f"PNG 폴더 (기본 {rel(DEFAULT_DIR)})")
    p.add_argument("--dry-run", action="store_true", help="올리지 않고 할 일만 보여 줌 (네트워크 없음)")
    p.add_argument("--user-id", type=int, default=DEFAULT_USER_ID, help=f"에셋 주인 Roblox userId (기본 {DEFAULT_USER_ID})")
    p.add_argument("--asset-type", choices=["Image", "Decal"], default="Image",
                   help="기본 Image (ImageLabel 에 바로 쓰는 Id). Decal 은 Image Id 를 따로 찾아야 해서 비추천")
    p.add_argument("--only", nargs="+", metavar="NAME", help="이 이름들만 (확장자 없이)")
    p.add_argument("--force", action="store_true", help="캐시를 무시하고 다시 올림 (새 Id 가 생김)")
    p.add_argument("--rewrite", action="store_true", help="ImageIds.luau 표 안을 키 이름 순으로 새로 씀 (묶음 주석은 사라짐)")
    p.add_argument("--timeout", type=float, default=120.0, help="업로드 처리 기다리는 최대 초 (기본 120)")
    p.add_argument("--out", default=str(DEFAULT_OUT), help=f"Luau 표 파일 (기본 {rel(DEFAULT_OUT)})")
    p.add_argument("--cache", default=str(DEFAULT_CACHE), help=f"캐시 파일 (기본 {rel(DEFAULT_CACHE)})")
    args = p.parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        log("\n중단됨. 이미 보낸 업로드는 캐시에 적혀 있어 다시 실행하면 이어서 확인합니다.")
        return 130
    except ValueError as err:
        log(f"오류: {err}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
