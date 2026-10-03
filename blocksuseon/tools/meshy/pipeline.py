#!/usr/bin/env python3
"""Meshy -> Roblox pipeline (proxy injects both API keys; never send keys).

    python3 pipeline.py specs.json manifest.json [--only key1,key2] [--workers 4]

specs.json: [{"key": "wolf", "kind": "beast"|"weapon", "prompt": "...", "texture_prompt": "...",
              "polycount": 6000, "skin": true,
              "preview_task_id": "(optional: reuse a SUCCEEDED preview)", "refine_task_id": "(optional: reuse, no credits)"}]
Per spec: T2 preview (5 cr, ~10 s) -> refine PBR 2k (10 cr, ~65 s) -> GLB -> [autoskin.py for quadrupeds]
-> Open Cloud Model upload (~15 s) -> manifest entry {assetId, meshy ids, tris, bbox, weapon guard/tip}.
Keys already in manifest with an assetId are skipped (idempotent).
"""
import json, os, struct, subprocess, sys, threading, time, urllib.error, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
MESHY = "https://api.meshy.ai/openapi/"
ASSETS = "https://apis.roblox.com/assets/v1"
CREATOR = "2038945024"
lock = threading.Lock()


def http(url, body=None, ct=None, method=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"Content-Type": ct or "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data is not None else "GET"))
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r), r.headers
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:800]
            if e.code == 429 or e.code >= 500:
                time.sleep(int(e.headers.get("Retry-After") or 5) * (attempt + 1))
                continue
            raise RuntimeError(f"{e.code} {url}: {msg}")
    raise RuntimeError(f"retries exhausted {url}")


def meshy_run(body, label):
    tid = http(MESHY + "v2/text-to-3d", body)[0]["result"]
    while True:
        t, h = http(MESHY + "v2/text-to-3d/" + tid)
        if t["status"] in ("SUCCEEDED", "FAILED", "CANCELED"):
            break
        time.sleep(int(h.get("Retry-After") or 5))
    if t["status"] != "SUCCEEDED":
        raise RuntimeError(f"{label} {tid} {t['status']} {t.get('task_error')}")
    return t


def glb_stats(path):
    b = open(path, "rb").read()
    jl = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jl])
    off = 20 + jl
    binc = b[off + 8:off + 8 + struct.unpack("<I", b[off:off + 4])[0]]
    pr = j["meshes"][0]["primitives"][0]
    a = j["accessors"][pr["attributes"]["POSITION"]]
    bv = j["bufferViews"][a["bufferView"]]
    st, o = bv.get("byteStride", 12), bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    V = [struct.unpack_from("<3f", binc, o + i * st) for i in range(a["count"])]
    tris = sum((j["accessors"][p["indices"]]["count"] // 3) for m in j["meshes"] for p in m["primitives"])
    return V, tris, a["min"], a["max"]


def weapon_axis(V, lo, hi):
    """Long axis must be Y (Meshy normalises longest side to 1). Finds the guard (widest slice) and tip end."""
    n = 40
    widths = []
    for i in range(n):
        y0 = lo[1] + (hi[1] - lo[1]) * i / n
        sl = [v for v in V if y0 <= v[1] < y0 + (hi[1] - lo[1]) / n]
        widths.append(max((v[0] for v in sl), default=0) - min((v[0] for v in sl), default=0))
    gi = max(range(n), key=lambda i: widths[i])
    guard_y = lo[1] + (hi[1] - lo[1]) * (gi + 0.5) / n
    tip_up = (hi[1] - guard_y) > (guard_y - lo[1])  # blade is the longer side of the guard
    return {"guardY": round(guard_y, 4), "tipDir": 1 if tip_up else -1}


def upload_model(path, name):
    bd = uuid.uuid4().hex
    meta = {"assetType": "Model", "displayName": name[:50], "description": "blocksuseon meshy",
            "creationContext": {"creator": {"userId": CREATOR}}}
    body = b"".join([
        f"--{bd}\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n{json.dumps(meta)}\r\n".encode(),
        f"--{bd}\r\nContent-Disposition: form-data; name=\"fileContent\"; filename=\"{os.path.basename(path)}\"\r\n"
        f"Content-Type: model/gltf-binary\r\n\r\n".encode(),
        open(path, "rb").read(), f"\r\n--{bd}--\r\n".encode()])
    op = http(f"{ASSETS}/assets", raw=body, ct=f"multipart/form-data; boundary={bd}", method="POST")[0]
    for _ in range(150):
        if op.get("done"):
            break
        time.sleep(2)
        op = http(f"{ASSETS}/{op['path']}")[0]
    r = op.get("response") or {}
    if not r.get("assetId"):
        raise RuntimeError(f"upload failed {op}")
    return r["assetId"], (r.get("moderationResult") or {}).get("moderationState")


def build(spec, outdir):
    key = spec["key"]
    t0 = time.time()
    if spec.get("refine_task_id"):
        ref = http(MESHY + "v2/text-to-3d/" + spec["refine_task_id"])[0]
        prev_id = ref.get("preceding_task_id")
    else:
        prev = {"id": spec["preview_task_id"]} if spec.get("preview_task_id") else meshy_run({"mode": "preview", "model_type": "smart-topology", "ai_model": "meshy-t2",
                          "target_polycount": spec.get("polycount", 5000), "prompt": spec["prompt"],
                          "target_formats": ["glb"], "moderation": True}, key + " preview")
        prev_id = prev["id"]
        ref = meshy_run({"mode": "refine", "preview_task_id": prev_id, "enable_pbr": True, "texture_resolution": "2k",
                         "texture_prompt": spec.get("texture_prompt", ""), "target_formats": ["glb"],
                         "moderation": True}, key + " refine")
    glb = os.path.join(outdir, key + ".glb")
    with urllib.request.urlopen(ref["model_urls"]["glb"], timeout=300) as r, open(glb, "wb") as f:
        f.write(r.read())
    with urllib.request.urlopen(ref["thumbnail_url"], timeout=120) as r, open(os.path.join(outdir, key + ".png"), "wb") as f:
        f.write(r.read())
    V, tris, lo, hi = glb_stats(glb)
    entry = {"kind": spec["kind"], "meshyPreview": prev_id, "meshyRefine": ref["id"], "tris": tris,
             "bbox": [round(hi[i] - lo[i], 4) for i in range(3)]}
    up = glb
    if spec.get("skin"):
        up = os.path.join(outdir, key + "_skinned.glb")
        subprocess.run([sys.executable, os.path.join(HERE, "autoskin.py"), glb, up], check=True, capture_output=True)
        entry["bones"] = True
    if spec["kind"] == "weapon":
        entry.update(weapon_axis(V, lo, hi))
    entry["assetId"], entry["moderation"] = upload_model(up, "bs_" + key)
    entry["seconds"] = round(time.time() - t0)
    return key, entry


def main():
    specs = json.load(open(sys.argv[1]))
    mpath = sys.argv[2]
    only = None
    workers = 4
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    outdir = os.path.join(os.path.dirname(os.path.abspath(mpath)), "models")
    os.makedirs(outdir, exist_ok=True)
    todo = [s for s in specs if (not only or s["key"] in only) and not manifest.get(s["key"], {}).get("assetId")]
    with ThreadPoolExecutor(max_workers=workers) as ex:  # Meshy Pro queue = 10 concurrent tasks
        for fut in [ex.submit(build, s, outdir) for s in todo]:
            try:
                key, entry = fut.result()
            except Exception as e:  # keep going; report at end
                print("FAILED", e, file=sys.stderr)
                continue
            with lock:
                manifest[key] = entry
                json.dump(manifest, open(mpath, "w"), indent=1, ensure_ascii=False)
            print(key, json.dumps(entry, ensure_ascii=False))


if __name__ == "__main__":
    main()
