"""캐릭터 아트 자산 해석.

에셋은 `web/game/art/` 에 둔다.
  <id>.png          기본 그림
  <id>@blink.png    눈 감은 차분  (눈 깜빡임용)
  <id>@smile.png    웃는 차분     (스킬 발동·획득 연출용)
  <id>@blush.png    부끄러운 차분

파일이 없으면 클라이언트가 캐릭터 팔레트로 SVG 플레이스홀더를 그리므로,
아트가 하나도 없어도 게임은 정상적으로 돌아간다.
에셋은 tools/generate_art.py 로 NovelAI 에서 뽑는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from .content import CHARACTERS, NAI_NEGATIVE

ART_DIR = Path(__file__).resolve().parent.parent / "web" / "game" / "art"
MANIFEST = ART_DIR / "manifest.json"
EXTS = (".webp", ".png", ".jpg", ".jpeg")

# 게임 화면 톤을 통일하기 위해 모든 캐릭터 프롬프트에 붙는 공통 꼬리표.
# 상업 배포를 고려해 특정 작가(artist:) 태그는 일부러 넣지 않는다.
STYLE_SUFFIX = ("upper body, looking at viewer, simple gradient background, "
                "soft rim light, anime style, highly detailed, "
                "official character art")

# 표정 차분. 기본 그림과 "같은 시드"로 태그만 바꿔 재생성하면 거의 같은 그림에
# 표정만 달라진다 — 인페인트로 얼굴을 마스킹하는 것보다 안정적이고 간단하다.
EXPRESSIONS = {
    "blink": "closed eyes",
    "smile": "smile, happy, open mouth",
    "blush": "blush, embarrassed, wavy mouth",
}


def art_file(cid: str, variant: str = "") -> Path | None:
    stem = f"{cid}@{variant}" if variant else cid
    for ext in EXTS:
        p = ART_DIR / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


def art_url(cid: str, variant: str = "") -> str | None:
    p = art_file(cid, variant)
    return f"/game/art/{p.name}" if p else None


def art_variants(cid: str) -> dict[str, str]:
    """존재하는 아트만 담은 {variant: url}. 기본 그림은 'base' 키."""
    out = {}
    base = art_url(cid)
    if base:
        out["base"] = base
    for v in EXPRESSIONS:
        u = art_url(cid, v)
        if u:
            out[v] = u
    return out


def build_prompt(char: dict, variant: str = "") -> str:
    tail = EXPRESSIONS.get(variant, "")
    return f"{char['prompt']}, {STYLE_SUFFIX}" + (f", {tail}" if tail else "")


def load_manifest() -> dict:
    """생성 기록(캐릭터별 시드). 표정 차분을 같은 시드로 뽑기 위해 쓴다."""
    if MANIFEST.is_file():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def save_manifest(data: dict) -> None:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def all_prompts() -> list[dict]:
    return [{"id": c["id"], "name": c["name"], "rarity": c["rarity"],
             "prompt": build_prompt(c), "negative": NAI_NEGATIVE}
            for c in CHARACTERS]
