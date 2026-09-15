"""Flask 웹 서버 (BYO-key).

API 키는 요청 헤더(X-Anthropic-Key / X-NAI-Token)로 받는다. 헤더가 없으면
서버 기본값(config)으로 폴백 → 로컬은 그대로, 공개 배포 시엔 각자 키 입력.

  GET  /              -> web/index.html
  GET  /<file>        -> web/ 정적 파일
  POST /api/suggest   -> 장면 → 태그(검증)
  POST /api/compose   -> 기존 프롬프트(+참고글/URL/이미지) → 재구성
  POST /api/style/artists -> 작가(artist) 태그 검색/인기순 (그림체 실험실)
  POST /api/generate  -> NovelAI 생성
  POST /api/inpaint   -> NovelAI 인페인트(infill)

위키(사람·AI 공용 · 읽기는 키 없이 공개):
  GET    /api/wiki                -> 문서 목록(JSON)
  GET    /api/wiki/search?q=      -> 키워드 검색(JSON)
  GET    /api/wiki/<slug>         -> 문서 1개(JSON)
  PUT    /api/wiki/<slug>         -> 만들기/고치기 {title, content, tags, props}
                                    (slug 의 / 는 폴더 · props 는 YAML 줄 문자열 또는 {키:값}, 그대로 보존)
  DELETE /api/wiki/<slug>         -> 삭제
  GET    /api/wiki/export         -> 전체 백업(JSON)   / POST /api/wiki/import -> 복원
  GET    /wiki/<slug>.md          -> 마크다운 원문(text/markdown)
  GET    /llms.txt  /llms-full.txt-> LLM 용 목차 / 전체 원문(llmstxt.org 관례)
  편집은 WIKI_TOKEN(또는 config wiki_token)이 설정돼 있으면 X-Wiki-Token 헤더 필요.
  /api/suggest, /api/compose 에 wiki_pages:[slug,...] 를 주면 그 문서를 Claude 가 맥락으로 읽는다.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from .client import SuggestClient
from .config import resolve_wiki_dir, resolve_wiki_token
from .nai import NovelAIClient, image_media_type
from .tagdb import TagDB
from .wiki import WikiError, WikiStore, normalize_slug

# PWA: .webmanifest 가 octet-stream 으로 나가지 않도록 MIME 등록(특히 Windows).
mimetypes.add_type("application/manifest+json", ".webmanifest")

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


def _validate_dict(data: dict, db: TagDB) -> dict:
    """사전 의미검색 결과 검증: 실제 태그면 CSV 의 정식명/카테고리/post 수로 보정하고,
    LLM 이 준 한/영 뜻풀이(ko/en)는 그대로 보존한다. _validate 의 사전판."""
    out: list[dict] = []
    seen: set[str] = set()
    verified = 0
    for item in data.get("tags", []):
        raw = (item.get("tag") or "").strip()
        if not raw:
            continue
        ko = (item.get("ko") or "").strip()
        en = (item.get("en") or "").strip()
        rating = item.get("rating", "general")
        m = db.lookup(raw)
        if m:
            if m.tag in seen:
                continue
            seen.add(m.tag)
            verified += 1
            out.append({"tag": m.tag, "category": m.category, "count": m.count,
                        "rating": rating, "status": "verified",
                        "matched_as": m.matched_as, "ko": ko, "en": en})
        else:
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"tag": raw, "category": item.get("category", "other"),
                        "count": 0, "rating": rating, "status": "unverified",
                        "matched_as": None, "ko": ko, "en": en})
    return {"interpretation": data.get("interpretation", ""), "tags": out,
            "stats": {"total": len(out), "verified": verified}}


def _image_response(raw: bytes, seed: int):
    """생성 결과 바이트 → JSON 응답. 이미지가 아니면 원인을 그대로 보여준다.

    NovelAI 가 200 으로 이미지가 아닌 걸 돌려주면(모델/파라미터 문제 등) 예전엔
    화면에 깨진 이미지만 떴다. 여기서 걸러 읽을 수 있는 오류로 바꾼다."""
    mt = image_media_type(raw)
    if not mt:
        return jsonify({"error": _why_not_image(raw)}), 502
    return jsonify({"image": f"data:{mt};base64," + base64.b64encode(raw).decode(),
                    "seed": seed})


def _why_not_image(raw: bytes) -> str:
    """이미지가 아닌 응답의 원인을 사람이 읽을 수 있게 정리."""
    head = raw[:400].decode("utf-8", "replace").strip().replace("\n", " ")
    low = head.lower()
    size = f"{len(raw):,}바이트"
    if not raw:
        return "NovelAI 가 빈 응답을 보냈습니다. 잠시 후 다시 시도해 보세요."
    if "<html" in low or "<!doctype" in low or "cloudflare" in low or "just a moment" in low:
        return ("NovelAI 가 이미지 대신 웹페이지(봇 차단 화면)를 보냈습니다. 클라우드 서버 "
                "IP 가 막힌 경우가 많습니다 — 내 PC 에서 `python run.py` 로 실행하거나 "
                f"`start-phone.bat`(터널)로 접속해 보세요. ({size}: {head[:160]})")
    try:
        msg = json.loads(head).get("message") or json.loads(head).get("error")
        if msg:
            return f"NovelAI 오류: {msg}"
    except Exception:  # noqa: BLE001  (JSON 이 아니거나 잘렸으면 원문을 그대로 보여준다)
        pass
    return ("NovelAI 가 이미지가 아닌 응답을 보냈습니다. ⚙ 설정에서 모델을 바꿔 "
            f"다시 시도해 보세요. ({size}: {head[:200]})")


def create_app(cfg: dict, db: TagDB, default_api_key: str | None = None,
               default_nai_token: str | None = None,
               wiki: WikiStore | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False   # 위키 속성(props)은 파일에 적힌 순서대로 보여줘야 한다
    wiki = wiki or WikiStore(resolve_wiki_dir(cfg))
    wiki_token = resolve_wiki_token(cfg)

    def suggest_client() -> SuggestClient | None:
        key = request.headers.get("X-Anthropic-Key") or default_api_key
        return SuggestClient(cfg, api_key=key) if key else None

    def nai_client() -> NovelAIClient | None:
        tok = request.headers.get("X-NAI-Token") or default_nai_token
        return NovelAIClient(tok, cfg) if tok else None

    def wiki_context(body: dict) -> str:
        """요청의 wiki_pages:[slug...] → Claude 에 붙일 위키 본문(없으면 빈 문자열)."""
        slugs = [str(s).strip() for s in (body.get("wiki_pages") or []) if str(s).strip()]
        return wiki.context_for_ai(slugs[:20]) if slugs else ""

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    # ── 위키: LLM 용 평문(llmstxt.org 관례) · 마크다운 원문 ──
    # 정적 파일 라우트(/<path:fname>)보다 구체적이므로 Werkzeug 가 이쪽을 먼저 고른다.
    @app.get("/llms.txt")
    def llms_txt():
        return Response(wiki.llms_index(request.url_root), mimetype="text/plain")

    @app.get("/llms-full.txt")
    def llms_full_txt():
        return Response(wiki.llms_full(), mimetype="text/plain")

    @app.get("/wiki/<path:slug>.md")
    def wiki_raw(slug: str):
        try:
            page = wiki.get(slug)
        except WikiError as e:
            return Response(str(e), status=400, mimetype="text/plain")
        if page is None:
            return Response("문서가 없습니다.", status=404, mimetype="text/plain")
        return Response(page.to_markdown(), mimetype="text/markdown")

    @app.get("/<path:fname>")
    def static_files(fname: str):
        return send_from_directory(WEB_DIR, fname)

    # ── 위키 JSON API ──
    def wiki_write_denied():
        """편집 토큰이 설정돼 있는데 헤더가 다르면 403 응답, 아니면 None."""
        if wiki_token and request.headers.get("X-Wiki-Token") != wiki_token:
            return jsonify({"error": "위키 편집 토큰이 필요합니다. 🔑 API 키 칸에서 위키 편집 토큰을 입력하세요."}), 403
        return None

    @app.get("/api/wiki")
    def wiki_list():
        return jsonify({"pages": [p.to_dict(with_content=False) for p in wiki.list()],
                        "folders": wiki.folders(),
                        "writable": not wiki_token or request.headers.get("X-Wiki-Token") == wiki_token,
                        "protected": bool(wiki_token)})

    @app.get("/api/wiki/search")
    def wiki_search():
        q = (request.args.get("q") or "").strip()
        try:
            limit = max(1, min(int(request.args.get("limit") or 30), 100))
        except ValueError:
            limit = 30
        return jsonify({"query": q, "results": wiki.search(q, limit=limit) if q else []})

    @app.get("/api/wiki/export")
    def wiki_export():
        return jsonify(wiki.export_all())

    @app.post("/api/wiki/import")
    def wiki_import():
        denied = wiki_write_denied()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(wiki.import_all(body, overwrite=bool(body.get("overwrite"))))
        except WikiError as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/wiki/<path:slug>")
    def wiki_get(slug: str):
        try:
            page = wiki.get(slug)
        except WikiError as e:
            return jsonify({"error": str(e)}), 400
        if page is None:
            return jsonify({"error": "문서가 없습니다."}), 404
        return jsonify(page.to_dict())

    @app.put("/api/wiki/<path:slug>")
    def wiki_put(slug: str):
        denied = wiki_write_denied()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        tags = body.get("tags") or []
        if isinstance(tags, str):
            tags = [t for t in re.split(r"[,\n]", tags)]
        try:
            created = not wiki.exists(slug)
            page = wiki.put(slug, body.get("title") or "", body.get("content") or "", tags,
                            props=body.get("props"))
            # rename: 새 slug 를 주면 옮긴다
            new_slug = (body.get("rename_to") or "").strip()
            if new_slug and normalize_slug(new_slug) != page.slug:
                page = wiki.rename(page.slug, normalize_slug(new_slug))
        except WikiError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(page.to_dict()), (201 if created else 200)

    @app.delete("/api/wiki/<path:slug>")
    def wiki_delete(slug: str):
        denied = wiki_write_denied()
        if denied:
            return denied
        try:
            ok = wiki.delete(slug)
        except WikiError as e:
            return jsonify({"error": str(e)}), 400
        if not ok:
            return jsonify({"error": "문서가 없습니다."}), 404
        return jsonify({"deleted": slug})

    @app.post("/api/suggest")
    def suggest():
        client = suggest_client()
        if client is None:
            return jsonify({"error": "Anthropic API 키가 필요합니다. 설정에서 키를 입력하세요."}), 400
        body = request.get_json(silent=True) or {}
        scene = (body.get("scene") or "").strip()
        if not scene:
            return jsonify({"error": "장면 설명을 입력해주세요."}), 400
        try:
            data, meta = client.suggest(scene, wiki_text=wiki_context(body))
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500
        result = _validate(data, db)
        result["meta"] = meta
        return jsonify(result)

    @app.post("/api/dict/lookup")
    def dict_lookup():
        """직접 조회: CSV 만으로 태그명/별칭 부분일치 검색. API 키 불필요(무료·즉시).

        category 를 주면 그 카테고리(artist 등)로만 좁힌다."""
        body = request.get_json(silent=True) or {}
        q = (body.get("query") or "").strip()
        cat = (body.get("category") or "").strip() or None
        if not q:
            return jsonify({"query": q, "tags": []})
        matches = db.search(q, limit=60, category=cat)
        tags = [{"tag": m.tag, "category": m.category, "count": m.count,
                 "rating": None, "status": "verified", "matched_as": m.matched_as}
                for m in matches]
        return jsonify({"query": q, "tags": tags, "stats": {"total": len(tags)}})

    @app.post("/api/style/artists")
    def style_artists():
        """그림체 실험실용 작가 태그 목록.

        query 가 있으면 작가 태그 중에서 부분일치 검색, 없으면 인기(post 수)
        상위 목록. CSV 만 쓰므로 키·비용이 들지 않는다."""
        body = request.get_json(silent=True) or {}
        q = (body.get("query") or "").strip()
        try:
            limit = int(body.get("limit") or 60)
        except (TypeError, ValueError):
            limit = 60
        limit = max(1, min(limit, 300))
        matches = (db.search(q, limit=limit, category="artist") if q
                   else db.top("artist", limit=limit))
        tags = [{"tag": m.tag, "count": m.count, "matched_as": m.matched_as}
                for m in matches]
        return jsonify({"query": q, "tags": tags, "stats": {"total": len(tags)}})

    @app.post("/api/dict/search")
    def dict_search():
        """AI 의미검색: 한글 개념 → 실제 Danbooru 태그(한/영 뜻풀이). Claude 사용."""
        client = suggest_client()
        if client is None:
            return jsonify({"error": "Anthropic API 키가 필요합니다. 설정에서 키를 입력하세요."}), 400
        q = ((request.get_json(silent=True) or {}).get("query") or "").strip()
        if not q:
            return jsonify({"error": "찾을 내용을 입력해주세요."}), 400
        try:
            data, meta = client.dict_search(q)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500
        result = _validate_dict(data, db)
        result["meta"] = meta
        return jsonify(result)

    @app.post("/api/dict/explain")
    def dict_explain():
        """태그 1개의 한글 뜻풀이 + 관련 태그(직접 조회 결과에서 '뜻 보기'). Claude 사용."""
        client = suggest_client()
        if client is None:
            return jsonify({"error": "Anthropic API 키가 필요합니다. 설정에서 키를 입력하세요."}), 400
        tag = ((request.get_json(silent=True) or {}).get("tag") or "").strip()
        if not tag:
            return jsonify({"error": "태그가 필요합니다."}), 400
        m = db.lookup(tag)
        canon = m.tag if m else tag
        try:
            data, meta = client.explain(canon, db.aliases_of(canon))
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500
        data["tag"] = canon
        data["count"] = m.count if m else 0
        data["category"] = m.category if m else "other"
        data["meta"] = meta
        return jsonify(data)

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

        # 연속 시퀀스: 전체 프레임 장면들 + 현재 프레임 인덱스(맥락 파악용)
        seq = [str(s).strip() for s in (body.get("sequence_scenes") or []) if str(s).strip()]
        frame_index = body.get("frame_index")
        if not isinstance(frame_index, int):
            frame_index = None
        try:
            data, meta = client.compose(scene, base, chars, neg, tags,
                                        reference_text=ref_text, image_b64=img_b64,
                                        image_media_type=img_mt,
                                        sequence=seq, frame_index=frame_index,
                                        wiki_text=wiki_context(body))
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
        return _image_response(png, used)

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
        return _image_response(png, used)

    return app
