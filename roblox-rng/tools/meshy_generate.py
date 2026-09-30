#!/usr/bin/env python3
"""Meshy text-to-3D 로 명소 미니어처(로우폴리 + 텍스처)를 만들어 내려받습니다.

흐름(명소마다): preview(smart-topology, 삼각형 ~3000) → refine(텍스처) → GLB·미리보기 PNG 다운로드
결과: art/meshy/<id>/model.glb, art/meshy/<id>/thumb.png, art/meshy/manifest.json

사용법:
  python3 tools/meshy_generate.py --jobs tools/meshy_jobs.json --only eiffel,tajmahal
  python3 tools/meshy_generate.py --jobs tools/meshy_jobs.json --dry-run

API 키: 이 환경에서는 프록시가 api.meshy.ai 요청에 Authorization 헤더를 자동으로 붙입니다.
환경 변수 MESHY_API_KEY 가 있으면 그 값을 직접 씁니다. 다운로드 주소(assets.meshy.ai)에는 키를 보내지 않습니다.
표준 라이브러리만 사용합니다.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.meshy.ai/openapi"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "art" / "meshy"
MANIFEST = OUT_DIR / "manifest.json"

STYLE_PREFIX = (
    "Stylized low-poly tabletop miniature of {name}: {features}. "
    "Chunky simplified shapes, few large forms, no tiny details, sits on a small round stone base, "
    "centered single object, no text, game asset"
)
TEXTURE_SUFFIX = (
    "hand-painted stylized game texture, bright saturated colors, soft simple shading, clean surfaces, "
    "no text, no logos"
)


def api(method: str, path: str, body: dict | None = None, retries: int = 5) -> dict:
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("MESHY_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    for attempt in range(retries):
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as err:
            text = err.read().decode(errors="replace")
            if err.code == 429 and attempt < retries - 1:
                wait = float(err.headers.get("retry-after") or 2 ** (attempt + 1))
                time.sleep(wait)
                continue
            if err.code >= 500 and method == "GET" and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"{method} {path} -> HTTP {err.code}: {text[:400]}") from None
        except urllib.error.URLError as err:
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"{method} {path} -> {err}") from None
    raise RuntimeError("unreachable")


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url)  # 서명된 주소: 키를 보내지 않음
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    dest.write_bytes(payload)
    return len(payload)


def wait_task(task_id: str, label: str, timeout: float = 900) -> dict:
    deadline = time.time() + timeout
    last = -1
    while time.time() < deadline:
        task = api("GET", f"/v2/text-to-3d/{task_id}")
        status = task.get("status")
        progress = task.get("progress", 0)
        if progress != last:
            print(f"  [{label}] {status} {progress}%", flush=True)
            last = progress
        if status == "SUCCEEDED":
            return task
        if status in ("FAILED", "CANCELED"):
            error = task.get("task_error") or {}
            raise RuntimeError(f"{label} {status}: {error}")
        time.sleep(6)
    raise RuntimeError(f"{label} timeout")


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def save_manifest(manifest: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


def run_job(job: dict, polycount: int) -> dict:
    lid = job["id"]
    prompt = STYLE_PREFIX.format(name=job["name"], features=job["features"])[:600]
    texture_prompt = f"{job.get('colors', '')}, {TEXTURE_SUFFIX}".strip(", ")[:600]
    result = {"id": lid, "prompt": prompt, "texture_prompt": texture_prompt}

    preview_id = api(
        "POST",
        "/v2/text-to-3d",
        {
            "mode": "preview",
            "prompt": prompt,
            "model_type": "smart-topology",
            "ai_model": "meshy-t2",
            "target_polycount": polycount,
            "target_formats": ["glb"],
            "alpha_thumbnail": True,
        },
    )["result"]
    result["preview_task"] = preview_id
    preview = wait_task(preview_id, f"{lid} preview")
    result["preview_credits"] = preview.get("consumed_credits")

    refine_id = api(
        "POST",
        "/v2/text-to-3d",
        {
            "mode": "refine",
            "preview_task_id": preview_id,
            "texture_prompt": texture_prompt,
            "texture_resolution": "2k",
            "enable_pbr": False,
            "target_formats": ["glb"],
            "alpha_thumbnail": True,
        },
    )["result"]
    result["refine_task"] = refine_id
    refined = wait_task(refine_id, f"{lid} refine")
    result["refine_credits"] = refined.get("consumed_credits")

    folder = OUT_DIR / lid
    glb_url = (refined.get("model_urls") or {}).get("glb")
    thumb_url = refined.get("alpha_thumbnail_url") or refined.get("thumbnail_url")
    if not glb_url:
        raise RuntimeError(f"{lid}: GLB 주소가 없음")
    result["glb_bytes"] = download(glb_url, folder / "model.glb")
    if thumb_url:
        result["thumb_bytes"] = download(thumb_url, folder / "thumb.png")
    result["status"] = "done"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", required=True, help="JSON 목록: [{id, name, features, colors}]")
    parser.add_argument("--only", help="쉼표로 구분한 id 만")
    parser.add_argument("--polycount", type=int, default=3000)
    parser.add_argument("--parallel", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="이미 만든 것도 다시 생성(크레딧 사용)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = json.loads(Path(args.jobs).read_text())
    if args.only:
        wanted = set(args.only.split(","))
        jobs = [job for job in jobs if job["id"] in wanted]
    manifest = load_manifest()
    todo = [job for job in jobs if args.force or manifest.get(job["id"], {}).get("status") != "done"]

    balance = api("GET", "/v1/balance").get("balance")
    print(f"크레딧 잔액 {balance} · 생성 대상 {len(todo)}개 · 예상 {len(todo) * 15} 크레딧")
    if args.dry_run:
        for job in todo:
            print(" -", job["id"], "|", STYLE_PREFIX.format(name=job["name"], features=job["features"])[:120], "...")
        return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(run_job, job, args.polycount): job for job in todo}
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            try:
                manifest[job["id"]] = future.result()
                print(f"✓ {job['id']} 완료", flush=True)
            except Exception as err:  # noqa: BLE001 — 한 명소 실패가 전체를 멈추지 않게
                manifest[job["id"]] = {"id": job["id"], "status": "failed", "error": str(err)}
                print(f"✗ {job['id']} 실패: {err}", flush=True)
            save_manifest(manifest)

    after = api("GET", "/v1/balance").get("balance")
    print(f"크레딧 잔액 {balance} → {after} (사용 {balance - after})")
    failed = [k for k, v in manifest.items() if v.get("status") == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
