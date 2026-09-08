"""캐릭터 아트 자산 해석.

에셋은 `web/game/art/<id>.webp|png|jpg` 에 둔다. 파일이 없으면 클라이언트가
캐릭터 팔레트로 SVG 플레이스홀더를 그리므로, 아트가 하나도 없어도 게임은
정상적으로 돌아간다. 에셋은 tools/generate_art.py 로 NovelAI 에서 뽑는다.
"""

from __future__ import annotations

from pathlib import Path

from .content import CHARACTERS, NAI_NEGATIVE

ART_DIR = Path(__file__).resolve().parent.parent / "web" / "game" / "art"
EXTS = (".webp", ".png", ".jpg", ".jpeg")

# 게임 화면 톤을 통일하기 위해 모든 캐릭터 프롬프트에 붙는 공통 꼬리표.
# 상업 배포를 고려해 특정 작가(artist:) 태그는 일부러 넣지 않는다.
STYLE_SUFFIX = ("upper body, looking at viewer, simple gradient background, "
                "soft rim light, anime style, highly detailed, "
                "official character art")


def art_file(cid: str) -> Path | None:
    for ext in EXTS:
        p = ART_DIR / f"{cid}{ext}"
        if p.is_file():
            return p
    return None


def art_url(cid: str) -> str | None:
    p = art_file(cid)
    return f"/game/art/{p.name}" if p else None


def build_prompt(char: dict) -> str:
    return f"{char['prompt']}, {STYLE_SUFFIX}"


def all_prompts() -> list[dict]:
    return [{"id": c["id"], "name": c["name"], "rarity": c["rarity"],
             "prompt": build_prompt(c), "negative": NAI_NEGATIVE}
            for c in CHARACTERS]
