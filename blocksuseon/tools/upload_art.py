#!/usr/bin/env python3
"""art/out 의 PNG 를 Roblox 이미지 에셋으로 올리고 src/client/Art.luau 를 만든다.

    python3 tools/upload_art.py            # 바뀐 그림만 올리고 Art.luau 갱신
    python3 tools/upload_art.py --dry-run  # 올리지 않고 무엇이 바뀌었는지만

이미 올린 그림은 art/uploaded.json 에 해시와 에셋 ID 로 기억해 두고 다시 올리지 않는다.
API 키는 ROBLOX_API_KEY (asset:read, asset:write 권한). 프록시가 넣어 주는 환경이면 비워 둔다.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

CREATOR_USER_ID = os.environ.get("ROBLOX_CREATOR_USER_ID", "2038945024")
OUT = "art/out"
CACHE = "art/uploaded.json"
TARGET = "src/client/Art.luau"
API = "https://apis.roblox.com/assets/v1"


def headers(extra=None):
    h = dict(extra or {})
    if os.environ.get("ROBLOX_API_KEY"):
        h["x-api-key"] = os.environ["ROBLOX_API_KEY"]
    return h


def request(url, data=None, content_type=None, method=None):
    h = headers({"Content-Type": content_type} if content_type else None)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def upload(name, path):
    boundary = uuid.uuid4().hex
    meta = {
        "assetType": "Image",
        "displayName": f"blocksuseon_{name}",
        "description": "블록수선전 UI",
        "creationContext": {"creator": {"userId": CREATOR_USER_ID}},
    }
    body = b"".join(
        [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"request\"\r\n"
            f"Content-Type: application/json\r\n\r\n{json.dumps(meta)}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"fileContent\"; filename=\"{name}.png\"\r\n"
            f"Content-Type: image/png\r\n\r\n".encode(),
            open(path, "rb").read(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    operation = request(f"{API}/assets", body, f"multipart/form-data; boundary={boundary}", "POST")
    for _ in range(60):
        if operation.get("done"):
            break
        time.sleep(2)
        operation = request(f"{API}/{operation['path']}")
    response = operation.get("response") or {}
    asset_id = response.get("assetId")
    if not asset_id:
        raise RuntimeError(f"{name}: 업로드 실패 {operation}")
    state = (response.get("moderationResult") or {}).get("moderationState")
    if state != "Approved":
        print(f"  ! {name}: 검수 상태 {state} (승인 전에는 게임에서 안 보일 수 있다)")
    return asset_id


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def lua_string(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_luau(manifest, glyphs, ids):
    lines = [
        "-- 자동 생성: tools/upload_art.py. 손으로 고치지 말 것.",
        "-- 그림 원본은 art/assets.html, 글자는 tools/build_glyphs.mjs.",
        "",
        "return {",
        "\timages = {",
    ]
    for name, info in sorted(manifest.items()):
        slice_ = ""
        if info.get("slice"):
            l, t, r, b = [int(v) for v in info["slice"].split(",")]
            slice_ = f", slice = Rect.new({l}, {t}, {r}, {b})"
        lines.append(
            f'\t\t{name} = {{ id = "rbxassetid://{ids[info["file"]]}", '
            f'size = Vector2.new({info["width"]}, {info["height"]}){slice_} }},'
        )
    lines += ["\t},", "\tfonts = {"]
    for name, font in sorted(glyphs.items()):
        pages = ", ".join(f'"rbxassetid://{ids[f]}"' for f in font["pages"])
        lines.append(f"\t\t{name} = {{")
        lines.append(f"\t\t\tsize = {font['size']},")
        lines.append(f"\t\t\tpad = {font['pad']},")
        lines.append(f"\t\t\tlineHeight = {font['lineHeight']},")
        lines.append(f"\t\t\tpages = {{ {pages} }},")
        lines.append("\t\t\t-- 글자 = { 페이지, x, y, 너비, 높이, 전진폭 }")
        lines.append("\t\t\tglyphs = {")
        for ch, (page, x, y, w, h, adv) in sorted(font["glyphs"].items()):
            lines.append(f"\t\t\t\t[{lua_string(ch)}] = {{ {page + 1}, {x}, {y}, {w}, {h}, {adv} }},")
        lines += ["\t\t\t},", "\t\t},"]
    lines += ["\t},", "}", ""]
    open(TARGET, "w", encoding="utf-8").write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = json.load(open(f"{OUT}/manifest.json"))
    glyphs = json.load(open(f"{OUT}/glyphs.json"))
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    files = [info["file"] for info in manifest.values()]
    for font in glyphs.values():
        files += font["pages"]

    ids = {}
    for file in files:
        path = f"{OUT}/{file}"
        digest = sha256(path)
        cached = cache.get(file)
        if cached and cached["sha256"] == digest:
            ids[file] = cached["assetId"]
            continue
        name = file.removesuffix(".png")
        if args.dry_run:
            print(f"  바뀜: {file}")
            ids[file] = (cached or {}).get("assetId", "0")
            continue
        try:
            ids[file] = upload(name, path)
        except urllib.error.HTTPError as error:
            print(f"{file}: {error.code} {error.read().decode(errors='replace')}", file=sys.stderr)
            return 1
        cache[file] = {"sha256": digest, "assetId": ids[file]}
        json.dump(cache, open(CACHE, "w"), indent=2, ensure_ascii=False)
        print(f"  올림: {file} → {ids[file]}")

    if not args.dry_run:
        write_luau(manifest, glyphs, ids)
        print(f"{TARGET} 갱신 (그림 {len(manifest)}개, 글꼴 {len(glyphs)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
