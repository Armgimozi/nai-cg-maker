"""Meshy text-to-3D 로 무기·아티팩트를 생성한다 (preview → refine → GLB 다운로드).

  python roblox_items/tools/meshy_generate.py --out <원본저장폴더> [--only iron_longsword,dagger]

- 인증: 환경변수 MESHY_API_KEY (없으면 프록시가 주입하는 환경에서만 동작)
- 진행 상황/태스크 ID 는 roblox_items/tools/meshy_jobs.json 에 기록 → 재실행 시 이어서 진행
- 비용: meshy-7.1 기준 preview 20 + refine 10 = 모델당 30 크레딧
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://api.meshy.ai/openapi/v2/text-to-3d"
HERE = Path(__file__).resolve().parent
JOBS = HERE / "meshy_jobs.json"
_LOCK = threading.Lock()

STYLE = ("semi-realistic fantasy RPG game asset, PBR materials, "
         "single isolated object, no stand, no base, no background props")

ITEMS = {
    # ── 무기 ──
    "iron_longsword": ("weapon",
        "A straight iron longsword: double-edged steel blade with a central fuller "
        "and slight wear, simple dark iron cross-guard, leather-wrapped grip, "
        "round iron pommel. No scabbard."),
    "battle_axe": ("weapon",
        "A battle axe made as ONE solid connected object: a broad single-bladed forged "
        "steel axe head with a curved cutting edge, firmly mounted on the top end of a "
        "straight long oak handle (the blade is attached to the handle, nothing "
        "floating), leather grip wrap near the bottom, iron butt cap. Full length, upright."),
    "spear": ("weapon",
        "A long infantry spear: straight ash-wood shaft, leaf-shaped steel "
        "spearhead on an iron socket bound with leather cord, small iron butt spike."),
    "longbow": ("weapon",
        "A recurve longbow of dark polished wood with a leather-wrapped grip in the "
        "middle, carved horn tips, a taut bowstring. No arrows, no quiver."),
    "mage_staff": ("weapon",
        "A long slender wizard staff: a tall thin straight dark-wood pole, about twelve "
        "times longer than it is wide; at the top end twisted wooden branches cradle a "
        "glowing blue crystal; silver bands and a leather wrap at the middle grip. "
        "Full-length staff, upright."),
    "dagger": ("weapon",
        "A steel dagger: short double-edged blade, small curved bronze cross-guard, "
        "dark leather grip, bronze pommel. No sheath."),
    # ── 아티팩트 ──
    "guardian_amulet": ("artifact",
        "A magical amulet: ornate silver medallion pendant with a large faceted blue "
        "sapphire in the center and engraved runes around the rim, with a small "
        "silver bail loop on top. Flat pendant, no long chain."),
    "flame_ring": ("artifact",
        "A magical gold ring set with a large glowing red ruby cut in the shape of a "
        "flame, ornate engraved band. Chunky ring, clearly readable shape."),
    "ancient_runestone": ("artifact",
        "A small upright standing runestone monolith: rough grey granite stone whose "
        "front face is deeply carved with large glowing cyan runic symbols that emit "
        "light, chipped edges, a little moss at the base. Only the stone itself, no "
        "hands, no characters."),
    "arcane_orb": ("artifact",
        "An arcane orb: swirling purple crystal sphere held by an ornate bronze claw "
        "cradle with a short bronze base."),
    "chalice_of_life": ("artifact",
        "A holy golden chalice: ornate goblet engraved with leaves and vines, green "
        "emerald gems set around the cup, sturdy stem and round foot."),
}


def _session() -> requests.Session:
    s = requests.Session()
    key = os.environ.get("MESHY_API_KEY")
    if key:
        s.headers["Authorization"] = f"Bearer {key}"
    s.headers["Content-Type"] = "application/json"
    return s


def _load_jobs() -> dict:
    return json.loads(JOBS.read_text("utf-8")) if JOBS.exists() else {}


def _save_jobs(jobs: dict) -> None:
    with _LOCK:
        JOBS.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), "utf-8")


def _post(s, body) -> str:
    for attempt in range(6):
        r = s.post(API, json=body, timeout=60)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["result"]
    raise RuntimeError("rate limited")


def _wait(s, task_id: str, label: str) -> dict:
    while True:
        r = s.get(f"{API}/{task_id}", timeout=60)
        if r.status_code >= 500 or r.status_code == 429:
            time.sleep(10)
            continue
        r.raise_for_status()
        t = r.json()
        st = t.get("status")
        if st == "SUCCEEDED":
            return t
        if st in ("FAILED", "CANCELED"):
            raise RuntimeError(f"{label}: {st} {t.get('task_error')}")
        time.sleep(8)


def run_item(name: str, out: Path, jobs: dict) -> None:
    kind, desc = ITEMS[name]
    s = _session()
    job = jobs.setdefault(name, {"kind": kind})
    prompt = f"{desc} {STYLE}"[:800]
    job["prompt"] = prompt

    if not job.get("preview_id"):
        job["preview_id"] = _post(s, {
            "mode": "preview", "prompt": prompt, "ai_model": "meshy-7.1",
            "should_remesh": True, "topology": "triangle",
            "target_polycount": 12000, "target_formats": ["glb"],
        })
        _save_jobs(jobs)
        print(f"[{name}] preview 시작 {job['preview_id']}", flush=True)
    _wait(s, job["preview_id"], f"{name} preview")
    print(f"[{name}] preview 완료", flush=True)

    if not job.get("refine_id"):
        job["refine_id"] = _post(s, {
            "mode": "refine", "preview_task_id": job["preview_id"],
            "enable_pbr": True, "texture_resolution": "2k",
            "target_formats": ["glb"],
        })
        _save_jobs(jobs)
        print(f"[{name}] refine 시작 {job['refine_id']}", flush=True)
    t = _wait(s, job["refine_id"], f"{name} refine")
    job["credits"] = t.get("consumed_credits")
    _save_jobs(jobs)

    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    glb = t["model_urls"]["glb"]
    (d / "model.glb").write_bytes(requests.get(glb, timeout=300).content)
    if t.get("thumbnail_url"):
        (d / "thumb.png").write_bytes(requests.get(t["thumbnail_url"], timeout=120).content)
    (d / "task.json").write_text(json.dumps(t, ensure_ascii=False, indent=2), "utf-8")
    print(f"[{name}] 다운로드 완료 → {d}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    names = [n for n in (a.only.split(",") if a.only else ITEMS) if n]
    jobs = _load_jobs()
    errors = []

    def go(n):
        try:
            run_item(n, out, jobs)
        except Exception as e:  # noqa: BLE001
            errors.append((n, repr(e)))
            print(f"[{n}] 실패: {e!r}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(go, names))
    _save_jobs(jobs)
    print("끝. 실패:", errors or "없음")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
