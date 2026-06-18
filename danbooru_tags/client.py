"""Claude API 호출.

  suggest()  : 구상한 장면 → Danbooru 태그 후보 (server 에서 TagDB 로 검증)
  compose()  : 기존 태그 + 장면 → 베이스/캐릭터/네거티브 프롬프트로 재구성

structured outputs(output_config.format)로 JSON 을 보장받고, 동일 입력에 대한
응답을 cache/ 에 저장해 재사용한다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import anthropic

# ── 태그 후보 스키마(suggest) ─────────────────────────────
# structured outputs 제약상 모든 객체는 additionalProperties:false 와
# required 를 명시해야 한다(maxItems 등은 미지원).
SCHEMA = {
    "type": "object",
    "properties": {
        "interpretation": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["general", "character", "copyright",
                                 "artist", "meta", "other"],
                    },
                    "rating": {
                        "type": "string",
                        "enum": ["general", "sensitive", "questionable", "explicit"],
                    },
                },
                "required": ["tag", "category", "rating"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["interpretation", "tags"],
    "additionalProperties": False,
}

# ── 프롬프트 재구성 스키마(compose) ───────────────────────
COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "base_prompt": {"type": "string"},
        "character_prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["label", "prompt"],
                "additionalProperties": False,
            },
        },
        "negative_prompt": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["base_prompt", "character_prompts", "negative_prompt", "note"],
    "additionalProperties": False,
}

# ── 사전 의미검색 스키마(dict_search) ─────────────────────
# 한글 개념 → 그 뜻을 가진 실제 Danbooru 태그 + 한/영 뜻풀이.
DICT_SCHEMA = {
    "type": "object",
    "properties": {
        "interpretation": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "ko": {"type": "string"},
                    "en": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["general", "character", "copyright",
                                 "artist", "meta", "other"],
                    },
                    "rating": {
                        "type": "string",
                        "enum": ["general", "sensitive", "questionable", "explicit"],
                    },
                },
                "required": ["tag", "ko", "en", "category", "rating"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["interpretation", "tags"],
    "additionalProperties": False,
}

# ── 태그 뜻풀이 스키마(explain) ───────────────────────────
EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "ko": {"type": "string"},
        "en": {"type": "string"},
        "related": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ko", "en", "related"],
    "additionalProperties": False,
}


def _system_prompt(max_tags: int) -> str:
    return f"""\
You are an expert image-board tagger. You convert a described scene into \
Danbooru tags for anime / illustration image generation.

The user describes a scene in natural language (usually Korean). Output the \
Danbooru tags that best capture that scene.

Tag rules:
- Real Danbooru conventions only: all lowercase, words joined by underscores, \
English. e.g. 1girl, solo, looking_at_viewer, long_hair, blue_eyes, \
school_uniform, pleated_skirt, cherry_blossoms, from_side, cowboy_shot, \
depth_of_field, sunlight, wind.
- Use canonical Danbooru spellings that actually exist on the site. Never \
invent tags and never output sentences or phrases.
- When characters are present, always include the count tag(s): 1girl, 2girls, \
1boy, multiple_girls, etc., plus `solo` when there is exactly one character.
- Cover the facets the scene implies: subject & count, body / pose, facial \
expression, eyes, hair (length / color / style), clothing & accessories, \
actions, framing & composition (cowboy_shot, upper_body, from_above, ...), \
where the subject looks, setting / background, time of day, weather, \
lighting / mood, and notable objects.
- Return only the most relevant tags, at most {max_tags}, ordered from most to \
least important.
- If a specific character or series is clearly named, include the character \
tag and the copyright tag in their Danbooru forms.

For every tag also provide:
- category: one of general, character, copyright, artist, meta, other.
- rating: your best estimate of the content rating the tag implies — one of \
general, sensitive, questionable, explicit. Use `general` for ordinary tags; \
only escalate for genuinely suggestive or explicit ones.

Also return "interpretation": one or two sentences in Korean summarizing how \
you understood the scene, so the user can confirm.

Return strictly the JSON defined by the schema, nothing else."""


def _compose_system_prompt() -> str:
    return """\
You are an expert prompt engineer for NovelAI anime image generation \
(Danbooru-tag based, v4 / v4.5).

You are given an EXISTING prompt set — base prompt, character prompt(s), and \
negative prompt — that establishes the foundation: character identity, outfit, \
art style, and quality. You are also given a DESIRED SCENE in natural language \
(usually Korean), and optionally extra Danbooru tags to weave in.

Rewrite the prompt set so the image depicts the DESIRED SCENE, while \
PRESERVING the identity and style defined by the existing prompts — keep the \
character's name tag, hair, eyes, defining features, art-style and quality \
tags. Change pose, expression, framing / composition, background, time, \
weather, lighting and mood to fit the desired scene (and change outfit only if \
the scene calls for it).

Output three parts:
- base_prompt: quality boosters first (masterpiece, best quality, very \
aesthetic, absurdres), then character-count tag(s) (1girl, 2girls, ...), \
composition / framing, setting / background, time & weather, lighting / mood. \
Scene-level and shared tags ONLY — no per-character appearance.
- character_prompts: one entry per character. `label` is a short id (e.g. \
"1girl" or the character name). `prompt` carries that character's appearance \
(hair, eyes), outfit, accessories, expression, pose / action.
- negative_prompt: keep the user's existing negatives, plus a solid anime \
baseline (lowres, worst quality, low quality, bad anatomy, bad hands, missing \
fingers, extra digits, jpeg artifacts, signature, watermark, blurry) and \
anything to exclude for THIS scene.

Rules:
- If a field is empty, build it sensibly from the scene and any extra tags.
- Real Danbooru conventions: lowercase, underscores, English, comma-separated.
- Keep character attributes out of base_prompt; keep scene/background/quality \
out of character_prompts. Preserve the number of characters from the existing \
character prompts unless the scene clearly changes it.

Also return "note": one short Korean sentence on what you changed / kept. \
Return strictly the JSON defined by the schema, nothing else."""


def _dict_system_prompt(max_tags: int) -> str:
    return f"""\
You are a Danbooru tag DICTIONARY for anime / illustration image prompting.

The user looks up a concept in Korean — a feature, pose, expression, hairstyle, \
clothing, accessory, body part, composition, camera angle, background, lighting, \
mood, action, or object — and wants to know which REAL Danbooru tags express it. \
The query may be a single word or a short phrase, and may be vague or in romaji.

Return the canonical Danbooru tags that MEAN what the user is looking for, like \
dictionary entries:
- Lead with the most direct match, then add close variants / synonyms and \
closely related tags the user would likely also want. e.g. for "양갈래(twintails)": \
twintails, low_twintails, short_twintails, twin_braids; for "뒤돌아보는": \
looking_back, looking_at_viewer, from_behind.
- Real Danbooru conventions ONLY: all lowercase, words joined by underscores, \
English. Use canonical spellings that actually exist on Danbooru. Never invent \
tags and never output sentences or phrases as a tag.
- Order from the most direct match to looser / related ones.
- Return at most {max_tags} tags. Prefer quality and relevance over quantity.

For every tag provide:
- tag: the canonical Danbooru tag (English, lowercase, underscores).
- ko: a SHORT Korean gloss — what the tag depicts (ideally under ~18 chars).
- en: a short English gloss.
- category: one of general, character, copyright, artist, meta, other.
- rating: your best estimate of the content rating the tag implies — one of \
general, sensitive, questionable, explicit. Use general for ordinary tags; only \
escalate for genuinely suggestive or explicit ones.

Also return "interpretation": one short Korean sentence stating what you \
understood the user is looking for.

Return strictly the JSON defined by the schema, nothing else."""


def _explain_system_prompt() -> str:
    return """\
You are a Danbooru tag dictionary. You are given ONE canonical Danbooru tag \
(and its known aliases). Explain it for a Korean user who writes prompts for \
anime image generation.

Return:
- ko: one or two Korean sentences — what this tag depicts and when to use it. \
Be concrete and practical.
- en: a short English gloss of the tag.
- related: up to 6 REAL canonical Danbooru tags commonly used together with it \
or that are close variants (lowercase, underscores, English). Only real tags; \
no phrases. Omit the tag itself.

Return strictly the JSON defined by the schema, nothing else."""


def _cache_key(model: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    for part in (model, system, user):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


class SuggestClient:
    def __init__(self, cfg: dict, api_key: str | None = None,
                 cache_dir: str | None = None, use_cache: bool = True):
        self.model = cfg.get("model", "claude-opus-4-8")
        self.max_tokens = cfg.get("max_tokens", 4000)
        self.max_tags = cfg.get("max_tags", 40)
        self.use_cache = use_cache
        self.client = (anthropic.Anthropic(api_key=api_key)
                       if api_key else anthropic.Anthropic())
        base = (Path(cfg["_path"]).resolve().parent if cfg.get("_path")
                else Path(__file__).resolve().parent.parent)
        self.cache_dir = Path(cache_dir) if cache_dir else base / "cache"

    def _call(self, system: str, user_text: str, schema: dict, prefix: str = "",
              image_b64: str | None = None,
              image_media_type: str = "image/png") -> tuple[dict, dict]:
        """공통 API 호출 + 디스크 캐시. (data, meta) 반환.

        image_b64 가 주어지면 비전 입력으로 함께 전달한다(캐시 키에도 반영)."""
        cache_input = user_text
        if image_b64:
            cache_input += "\x00IMG\x00" + hashlib.sha256(image_b64.encode()).hexdigest()
        key = _cache_key(self.model, system, cache_input)
        cache_file = self.cache_dir / f"{prefix}{key}.json"

        if self.use_cache and cache_file.is_file():
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f), {"cached": True, "usage": None}

        content: list[dict] = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": image_media_type, "data": image_b64},
            })
        content.append({"type": "text", "text": user_text})

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )

        if resp.stop_reason == "refusal":
            detail = getattr(resp, "stop_details", None)
            raise RuntimeError(
                "모델이 안전상의 이유로 생성을 거부했습니다"
                + (f" ({detail.explanation})" if detail else "")
                + "."
            )
        if resp.stop_reason == "max_tokens":
            raise RuntimeError(
                "출력이 max_tokens 에 걸려 잘렸습니다. config 의 max_tokens 를 늘려주세요."
            )

        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise RuntimeError("모델 응답에 텍스트 블록이 없습니다.")
        data = json.loads(text)

        if self.use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0),
            "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0),
        }
        return data, {"cached": False, "usage": usage}

    def suggest(self, scene: str) -> tuple[dict, dict]:
        """장면 → 태그 후보. data 는 SCHEMA 형태."""
        system = _system_prompt(self.max_tags)
        return self._call(system, f"장면:\n{scene}", SCHEMA)

    def dict_search(self, query: str) -> tuple[dict, dict]:
        """한글 개념/키워드 → 그 뜻을 가진 실제 Danbooru 태그(한/영 뜻풀이 포함).

        data 는 DICT_SCHEMA 형태. server 에서 TagDB 로 실제 존재 여부를 검증한다."""
        system = _dict_system_prompt(min(self.max_tags, 24))
        return self._call(system, f"찾는 개념:\n{query}", DICT_SCHEMA, prefix="d_")

    def explain(self, tag: str, aliases: list[str] | None = None) -> tuple[dict, dict]:
        """정식 태그 1개 → 한글 뜻풀이 + 관련 태그. data 는 EXPLAIN_SCHEMA 형태."""
        system = _explain_system_prompt()
        al = ", ".join(aliases or []) or "(없음)"
        return self._call(system, f"태그: {tag}\n별칭: {al}", EXPLAIN_SCHEMA, prefix="e_")

    def compose(self, scene: str, base: str = "", chars: list[str] | None = None,
                negative: str = "", tags: list[str] | None = None,
                reference_text: str = "", image_b64: str | None = None,
                image_media_type: str = "image/png",
                sequence: list[str] | None = None,
                frame_index: int | None = None) -> tuple[dict, dict]:
        """기존 프롬프트(베이스/캐릭터/네거티브) + 장면 → 장면에 맞춰 재구성.

        reference_text(정보글 등)·image_b64(참고 이미지)가 있으면 함께 반영.
        sequence(전체 프레임 장면들)+frame_index 가 주어지면, 그 프레임 하나만
        재구성하되 전체 흐름을 맥락으로 파악해 앞뒤가 자연스럽게 이어지게 한다."""
        system = _compose_system_prompt()
        chars = chars or []
        tags = tags or []
        char_block = ("\n".join(f"{i + 1}) {c}" for i, c in enumerate(chars))
                      if chars else "(없음)")
        user = (
            f"원하는 장면:\n{scene or '(없음)'}\n\n"
            f"[기존 베이스 프롬프트]\n{base or '(없음)'}\n\n"
            f"[기존 캐릭터 프롬프트]\n{char_block}\n\n"
            f"[기존 네거티브 프롬프트]\n{negative or '(없음)'}\n\n"
            f"[추가로 반영할 태그]\n{', '.join(tags) or '(없음)'}"
        )
        seq = [str(s).strip() for s in (sequence or []) if str(s).strip()]
        if len(seq) > 1 and frame_index is not None:
            flow = "\n".join(
                f"{i + 1}) {s}" + ("   ← 지금 재구성할 프레임" if i == frame_index else "")
                for i, s in enumerate(seq)
            )
            user += (
                f"\n\n[연속 시퀀스 맥락 — 총 {len(seq)}개 프레임이 이어지는 한 장면]\n"
                f"{flow}\n"
                f"위 전체 흐름을 파악하되, 지금은 {frame_index + 1}번째 프레임 하나만 "
                "재구성하세요. 같은 인물·복장·화풍·장소·시점을 유지하고, 앞 프레임에서 "
                "바뀌는 부분(포즈·표정·시선·동작 등)에 집중해 자연스럽게 이어지게 하세요."
            )
        if reference_text:
            user += (f"\n\n[참고 정보 — 아래 글/설정을 적극 반영하세요]\n"
                     f"{reference_text[:5000]}")
        if image_b64:
            user += ("\n\n[첨부 이미지] 함께 첨부된 이미지를 보고 캐릭터 외형·복장·"
                     "구도·분위기를 프롬프트에 반영하세요.")
        return self._call(system, user, COMPOSE_SCHEMA, prefix="c_",
                          image_b64=image_b64, image_media_type=image_media_type)
