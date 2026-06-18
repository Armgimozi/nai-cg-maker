"""NovelAI 이미지 생성 API (Diffusion v4.5) 호출.

  generate() : 베이스/캐릭터/네거티브 프롬프트 → 이미지(PNG bytes)
  inpaint()  : 위 + 원본이미지 + 마스크(흰색=재생성) → infill 결과

설정(settings)과 캐릭터 레퍼런스(references)를 함께 받는다. 레퍼런스는 두 방식:
  · vibe transfer  : /ai/encode-vibe 로 먼저 인코딩(vibe 토큰)한 뒤
                     reference_image_multiple 로 보낸다(raw 이미지는 거부됨).
  · precise reference(V4.5) : 원본 이미지를 director_reference_images 로 그대로
                     보낸다(인코딩 불필요). 유형(캐릭터/스타일/둘다)·Strength·
                     Fidelity 를 director_reference_* 로 전달. 생성당 +5 Anlas.
둘은 한 생성에 함께 못 쓰므로 ref 의 mode 로 구분하고 precise 가 있으면 우선한다.
응답은 PNG 가 든 ZIP.
"""

from __future__ import annotations

import base64
import io
import json
import random
import urllib.error
import urllib.request
import zipfile

API_URL = "https://image.novelai.net/ai/generate-image"
ENCODE_VIBE_URL = "https://image.novelai.net/ai/encode-vibe"
_SEED_MAX = 2 ** 32 - 1
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _char_captions(prompts: list[str]) -> list[dict]:
    return [{"char_caption": p, "centers": [{"x": 0.5, "y": 0.5}]}
            for p in prompts if p.strip()]


# Precise Reference(=director reference) 유형 → API caption 값
_REF_CAPTION = {"character": "character", "style": "style", "both": "character&style"}


def _split_refs(references) -> tuple[list, list]:
    """references → (vibe, precise). vibe transfer 와 precise reference 는
    NAI 상 한 생성에 같이 못 쓰므로, precise 가 하나라도 있으면 precise 만
    쓰고 vibe 는 버린다(precise 우선)."""
    vibe, precise = [], []
    for r in references or []:
        if not r.get("image"):
            continue
        (precise if r.get("mode") == "precise" else vibe).append(r)
    return ([], precise) if precise else (vibe, [])


# Precise Reference(director) 이미지가 들어갈 수 있는 캔버스(NAI 가 받는 3종)
_DIRECTOR_CANVASES = [(1024, 1536), (1536, 1024), (1472, 1472)]


def _prep_director_image(b64: str) -> str:
    """Precise Reference 이미지를 NAI 인코더가 받는 캔버스로 맞춰 RGB PNG base64 로.

    NAI 는 director reference 를 1024x1536 / 1536x1024 / 1472x1472 로만 받는다
    (그 외 크기·알파 채널이면 'Error encoding v4 director references' 400). 원본
    비율에 가장 가까운 캔버스를 골라 비율 유지로 축소한 뒤 검은 여백으로 채운다.
    """
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Precise Reference 에는 Pillow 가 필요합니다 "
                           "(requirements 의 Pillow 설치).") from e
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    w, h = im.size
    ar = w / h if h else 1.0
    tw, th = min(_DIRECTOR_CANVASES, key=lambda c: abs(c[0] / c[1] - ar))
    scale = min(tw / w, th / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    canvas = Image.new("RGB", (tw, th), (0, 0, 0))
    canvas.paste(im.resize((nw, nh), Image.LANCZOS), ((tw - nw) // 2, (th - nh) // 2))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode()


class NovelAIClient:
    def __init__(self, token: str, cfg: dict):
        self.token = token
        self.model = cfg.get("nai_model", "nai-diffusion-4-5-full")
        self.width = int(cfg.get("nai_width", 832))
        self.height = int(cfg.get("nai_height", 1216))
        self.steps = int(cfg.get("nai_steps", 28))
        self.scale = cfg.get("nai_scale", 5)
        self.sampler = cfg.get("nai_sampler", "k_euler_ancestral")
        self.noise_schedule = cfg.get("nai_noise_schedule", "karras")
        self.cfg_rescale = cfg.get("nai_cfg_rescale", 0)

    def _headers(self, accept: str) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": accept,
            "User-Agent": _UA,
            "Origin": "https://novelai.net",
            "Referer": "https://novelai.net/",
        }

    def _http(self, url: str, body: dict, accept: str, timeout: int = 180) -> bytes:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=self._headers(accept))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            hint = {
                401: "토큰이 올바르지 않습니다.",
                402: "Anlas 가 부족하거나 구독이 필요합니다.",
                403: "접근 거부(토큰/요청 헤더 확인).",
                429: "요청이 많습니다. 잠시 후 다시.",
            }.get(e.code, "")
            raise RuntimeError(f"NovelAI {e.code} {hint} {detail}".strip())
        except urllib.error.URLError as e:
            raise RuntimeError(f"NovelAI 연결 실패: {e.reason}")

    def _encode_vibe(self, image_b64: str, info_extracted, model: str) -> str:
        """참조 이미지를 v4 vibe 토큰으로 인코딩 → base64 문자열 반환."""
        raw = self._http(ENCODE_VIBE_URL, {
            "image": image_b64,
            "information_extracted": float(info_extracted),
            "model": model,
        }, accept="application/json,application/octet-stream", timeout=120)
        return base64.b64encode(raw).decode()

    def _encode_refs(self, references, model: str) -> list[dict]:
        vibes = []
        for r in references or []:
            img = r.get("image")
            if not img:
                continue
            enc = self._encode_vibe(img, r.get("info_extracted", 1.0), model)
            vibes.append({"image": enc, "strength": float(r.get("strength", 0.6))})
        return vibes

    def _params(self, base, chars, negative, seed, width, height,
                settings=None, vibes=None, directors=None, extra=None) -> dict:
        s = settings or {}
        params = {
            "params_version": 3,
            "width": width,
            "height": height,
            "scale": float(s.get("scale", self.scale)),
            "sampler": s.get("sampler") or self.sampler,
            "steps": int(s.get("steps", self.steps)),
            "n_samples": 1,
            "ucPreset": 0,
            "qualityToggle": True,
            "autoSmea": False,
            "dynamic_thresholding": False,
            "controlnet_strength": 1,
            "legacy": False,
            "add_original_image": True,
            "cfg_rescale": float(s.get("cfg_rescale", self.cfg_rescale)),
            "noise_schedule": s.get("noise_schedule") or self.noise_schedule,
            "legacy_v3_extend": False,
            "seed": seed,
            "negative_prompt": negative,
            "characterPrompts": [
                {"prompt": p, "uc": "", "center": {"x": 0.5, "y": 0.5}, "enabled": True}
                for p in chars if p.strip()
            ],
            "v4_prompt": {
                "caption": {"base_caption": base, "char_captions": _char_captions(chars)},
                "use_coords": False,
                "use_order": True,
            },
            "v4_negative_prompt": {
                "caption": {"base_caption": negative, "char_captions": []},
                "legacy_uc": False,
            },
        }
        vibes = vibes or []
        if vibes:
            # vibe 토큰은 information_extracted 가 이미 반영되어 있으므로 강도만 전달
            params["reference_image_multiple"] = [v["image"] for v in vibes]
            params["reference_strength_multiple"] = [v["strength"] for v in vibes]
            params["normalize_reference_strength_multiple"] = True
        else:
            params["reference_image_multiple"] = []
            params["reference_information_extracted_multiple"] = []
            params["reference_strength_multiple"] = []

        # Precise Reference(V4.5): 원본 이미지를 그대로(인코딩 없이) 보낸다.
        # Strength=강도, Fidelity=정밀도(secondary 는 1-fidelity 로 반전 전달).
        directors = directors or []
        if directors:
            params["director_reference_images"] = [_prep_director_image(d["image"]) for d in directors]
            params["director_reference_descriptions"] = [
                {"use_coords": False, "use_order": False, "legacy_uc": False,
                 "caption": {"base_caption": _REF_CAPTION.get(d.get("ref_type", "character"),
                                                              "character"),
                             "char_captions": []}}
                for d in directors]
            params["director_reference_strength_values"] = [
                float(d.get("strength", 1.0)) for d in directors]
            params["director_reference_secondary_strength_values"] = [
                round(1.0 - float(d.get("fidelity", 1.0)), 4) for d in directors]
            params["director_reference_information_extracted"] = [
                float(d.get("info_extracted", 1.0)) for d in directors]

        if extra:
            params.update(extra)
        return params

    def generate(self, base, chars, negative, *, seed=None, width=None,
                 height=None, settings=None, references=None) -> tuple[bytes, int]:
        seed = random.randint(0, _SEED_MAX) if seed is None else int(seed)
        w, h = width or self.width, height or self.height
        model = (settings or {}).get("model") or self.model
        vibe_refs, precise_refs = _split_refs(references)
        vibes = self._encode_refs(vibe_refs, model)
        body = {
            "input": base,
            "model": model,
            "action": "generate",
            "parameters": self._params(base, chars, negative, seed, w, h,
                                       settings, vibes, precise_refs),
        }
        return self._unzip(self._http(API_URL, body, "application/x-zip-compressed,application/json")), seed

    def inpaint(self, base, chars, negative, image_b64, mask_b64, *, seed=None,
                width=None, height=None, settings=None, references=None) -> tuple[bytes, int]:
        seed = random.randint(0, _SEED_MAX) if seed is None else int(seed)
        w, h = width or self.width, height or self.height
        model = (settings or {}).get("model") or self.model
        vibe_refs, precise_refs = _split_refs(references)
        vibes = self._encode_refs(vibe_refs, model)
        inpaint_model = model if model.endswith("-inpainting") else f"{model}-inpainting"
        extra = {"image": image_b64, "mask": mask_b64, "add_original_image": True}
        body = {
            "input": base,
            "model": inpaint_model,
            "action": "infill",
            "parameters": self._params(base, chars, negative, seed, w, h,
                                       settings, vibes, precise_refs, extra),
        }
        return self._unzip(self._http(API_URL, body, "application/x-zip-compressed,application/json")), seed

    @staticmethod
    def _unzip(raw: bytes) -> bytes:
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
            return zf.read(zf.namelist()[0])
        except zipfile.BadZipFile:
            return raw
