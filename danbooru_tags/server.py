"""Flask 웹 서버 (BYO-key).

API 키는 요청 헤더(X-Anthropic-Key / X-NAI-Token)로 받는다. 헤더가 없으면
서버 기본값(config)으로 폴백 → 로컬은 그대로, 공개 배포 시엔 각자 키 입력.

  GET  /              -> web/index.html
  GET  /<file>        -> web/ 정적 파일
  POST /api/suggest   -> 장면 → 태그(검증)
  POST /api/compose   -> 기존 프롬프트(+참고글/URL/이미지) → 재구성
  POST /api/generate  -> NovelAI 생성
  POST /api/inpaint   -> NovelAI 인페인트(infill)
"""

from __future__ import annotations

import base64
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from .client import SuggestClient
from .nai import NovelAIClient
from .tagdb import TagDB

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _split_dataurl(s: str) -> tuple[str, str]:
    """data URL → (base64, media_type). 아니면 (원문, image/png)."""
    if s and s.startswith("data:"):
        head, _, b64 = s.partition(",")
        m = re.search(r"data:([^;]+)", head)
        return b64, (m.group(1) if m else "image/png")
    return (s or ""), "image/png"


def _detect_media_type(b64: str, fallback: str = "image/png") -> str:
    """선언된 MIME 을 믿지 않고 실제 바이트(매직넘버)로 이미지 타입 판별.

    Anthropic 비전 API 는 선언 타입과 실제 바이트가 다르면 400 을 낸다."""
    try:
        head = base64.b64decode(b64[:16])  # 16 base64 chars → 12 bytes
    except Exception:  # noqa: BLE001
        return fallback
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF8"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return fallback


_FETCH_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
}


_URL_CACHE: dict[str, tuple[float, str]] = {}
_URL_CACHE_TTL = 600.0  # 10분


def _fetch_url_text(url: str) -> str:
    """URL 본문을 받아 태그를 대충 제거한 텍스트로(참고용).

    같은 URL 을 짧은 시간에 여러 번(예: 연속 시퀀스의 프레임마다) 요청하면
    대상 사이트가 429 로 막으므로, 성공 결과를 TTL(10분) 동안 캐시해 1회만 받는다.
    봇 차단을 줄이려 브라우저 비슷한 헤더를 보내고, 429(요청 과다)는
    Retry-After(최대 5초)만큼 기다려 한 번 더 시도한다.
    """
    now = time.time()
    hit = _URL_CACHE.get(url)
    if hit is not None and now - hit[0] < _URL_CACHE_TTL:
        return hit[1]

    headers = dict(_FETCH_HEADERS)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme and parts.netloc:
        headers["Referer"] = f"{parts.scheme}://{parts.netloc}/"

    html = ""
    for attempt in range(2):
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                ra = (e.headers.get("Retry-After") if e.headers else None) or ""
                time.sleep(min(float(ra) if ra.isdigit() else 1.2, 5.0))
                continue
            raise
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    result = text.strip()[:6000]
    _URL_CACHE[url] = (now, result)
    return result


def _validate(data: dict, db: TagDB) -> dict:
    out: list[dict] = []
    seen: set[str] = set()
    verified = 0
    for item in data.get("tags", []):
        raw = (item.get("tag") or "").strip()
        if not raw:
            continue
        rating = item.get("rating", "general")
        m = db.lookup(raw)
        if m:
            if m.tag in seen:
                continue
            seen.add(m.tag)
            verified += 1
            out.append({"tag": m.tag, "category": m.category, "count": m.count,
                        "rating": rating, "status": "verified", "matched_as": m.matched_as})
        else:
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"tag": raw, "category": item.get("category", "other"),
                        "count": 0, "rating": rating, "status": "unverified", "matched_as": None})
    return {"interpretation": data.get("interpretation", ""), "tags": out,
            "stats": {"total": len(out), "verified": verified}}


def create_app(cfg: dict, db: TagDB, default_api_key: str | None = None,
               default_nai_token: str | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)

    def suggest_client() -> SuggestClient | None:
        key = request.headers.get("X-Anthropic-Key") or default_api_key
        return SuggestClient(cfg, api_key=key) if key else None

    def nai_client() -> NovelAIClient | None:
        tok = request.headers.get("X-NAI-Token") or default_nai_token
        return NovelAIClient(tok, cfg) if tok else None

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/<path:fname>")
    def static_files(fname: str):
        return send_from_directory(WEB_DIR, fname)

    @app.post("/api/suggest")
    def suggest():
        client = suggest_client()
        if client is None:
            return jsonify({"error": "Anthropic API 키가 필요합니다. 설정에서 키를 입력하세요."}), 400
        scene = ((request.get_json(silent=True) or {}).get("scene") or "").strip()
        if not scene:
            return jsonify({"error": "장면 설명을 입력해주세요."}), 400
        try:
            data, meta = client.suggest(scene)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500
        result = _validate(data, db)
        result["meta"] = meta
        return jsonify(result)

    @app.post("/api/compose")
    def compose():
        client = suggest_client()
        if client is None:
            return jsonify({"error": "Anthropic API 키가 필요합니다. 설정에서 키를 입력하세요."}), 400
        body = request.get_json(silent=True) or {}
        scene = (body.get("scene") or "").strip()
        base = (body.get("base_prompt") or "").strip()
        chars = [str(c).strip() for c in (body.get("character_prompts") or []) if str(c).strip()]
        neg = (body.get("negative_prompt") or "").strip()
        tags = [str(t).strip() for t in (body.get("tags") or []) if str(t).strip()]

        # 참고 정보: 텍스트 그대로 + (URL 이면) 본문을 받아 덧붙임
        ref_text = (body.get("reference_text") or "").strip()
        ref_url = (body.get("reference_url") or "").strip()
        if ref_url:
            try:
                ref_text = (ref_text + "\n\n" + _fetch_url_text(ref_url)).strip()
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    msg = ("참고 URL 사이트가 요청을 일시 차단했습니다(429 Too Many Requests). "
                           "잠시 후 다시 시도하거나, 페이지 내용을 복사해 '참고 정보' 칸에 "
                           "직접 붙여넣으세요.")
                elif e.code in (401, 403):
                    msg = (f"참고 URL 접근이 거부됐습니다(HTTP {e.code}). 로그인/쿠키가 필요한 "
                           "페이지일 수 있습니다. 내용을 복사해 '참고 정보' 칸에 직접 붙여넣으세요.")
                else:
                    msg = f"참고 URL 을 불러오지 못했습니다: HTTP {e.code} {e.reason}"
                return jsonify({"error": msg}), 400
            except Exception as e:  # noqa: BLE001
                return jsonify({"error": f"참고 URL 을 불러오지 못했습니다: {e}"}), 400

        img_b64, img_mt = _split_dataurl(body.get("image") or "")
        if img_b64:
            img_mt = _detect_media_type(img_b64, img_mt)  # 실제 바이트로 타입 보정
        else:
            img_b64 = None

        if not (scene or base or chars or tags or ref_text or img_b64):
            return jsonify({"error": "장면이나 기존 프롬프트를 입력해주세요."}), 400
        try:
            data, meta = client.compose(scene, base, chars, neg, tags,
                                        reference_text=ref_text, image_b64=img_b64,
                                        image_media_type=img_mt)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500
        data["meta"] = meta
        return jsonify(data)

    def _gen_args(body: dict):
        base = (body.get("base_prompt") or "").strip()
        chars = [str(c).strip() for c in (body.get("character_prompts") or []) if str(c).strip()]
        neg = (body.get("negative_prompt") or "").strip()
        seed = body.get("seed")
        width = body.get("width") or None
        height = body.get("height") or None
        settings = body.get("settings") or {}
        refs = []
        for r in (body.get("references") or []):
            img, _ = _split_dataurl(r.get("image") or "")
            if img:
                refs.append({
                    "image": img,
                    "mode": "precise" if r.get("mode") == "precise" else "vibe",
                    "strength": r.get("strength", 0.6),
                    "info_extracted": r.get("info_extracted", 1.0),
                    "ref_type": r.get("ref_type", "character"),
                    "fidelity": r.get("fidelity", 1.0),
                })
        return base, chars, neg, seed, width, height, settings, refs

    @app.post("/api/generate")
    def generate():
        nai = nai_client()
        if nai is None:
            return jsonify({"error": "NovelAI 토큰이 필요합니다. 설정에서 토큰을 입력하세요."}), 400
        body = request.get_json(silent=True) or {}
        base, chars, neg, seed, width, height, settings, refs = _gen_args(body)
        if not base and not chars:
            return jsonify({"error": "프롬프트가 비어 있습니다."}), 400
        try:
            png, used = nai.generate(base, chars, neg, seed=seed, width=width,
                                     height=height, settings=settings, references=refs)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
        return jsonify({"image": "data:image/png;base64," + base64.b64encode(png).decode(),
                        "seed": used})

    @app.post("/api/inpaint")
    def inpaint():
        nai = nai_client()
        if nai is None:
            return jsonify({"error": "NovelAI 토큰이 필요합니다. 설정에서 토큰을 입력하세요."}), 400
        body = request.get_json(silent=True) or {}
        base, chars, neg, seed, width, height, settings, refs = _gen_args(body)
        image, _ = _split_dataurl(body.get("image") or "")
        mask, _ = _split_dataurl(body.get("mask") or "")
        if not image or not mask:
            return jsonify({"error": "원본 이미지와 마스크가 필요합니다."}), 400
        try:
            png, used = nai.inpaint(base, chars, neg, image, mask, seed=seed,
                                    width=width, height=height,
                                    settings=settings, references=refs)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
        return jsonify({"image": "data:image/png;base64," + base64.b64encode(png).decode(),
                        "seed": used})

    return app
