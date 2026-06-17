"""설정 로딩.

config.json 을 찾아 읽되, 없으면 기본값으로 동작한다. 탐색 순서:
  1) 환경변수 DANBOORU_TAG_CONFIG 가 가리키는 경로
  2) 현재 작업 디렉터리의 config.json
  3) 패키지 상위 폴더의 config.json
API 키는 config 의 "api_key" 보다 환경변수 ANTHROPIC_API_KEY 를 우선한다
(키를 코드/설정에 하드코딩하지 않는 것을 권장).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULTS = {
    "model": "claude-opus-4-8",
    "max_tokens": 4000,
    "max_tags": 40,      # 한 번에 추천받을 최대 태그 수(프롬프트로 강제)
    "host": "127.0.0.1",
    "port": 8765,
    # NovelAI 이미지 생성(v4.5)
    "nai_model": "nai-diffusion-4-5-full",
    "nai_width": 832,
    "nai_height": 1216,
    "nai_steps": 28,
    "nai_scale": 5,
    "nai_sampler": "k_euler_ancestral",
    "nai_noise_schedule": "karras",
    "nai_cfg_rescale": 0,
}


def _candidate_paths(explicit: str | None) -> list[Path]:
    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit))
    env = os.environ.get("DANBOORU_TAG_CONFIG")
    if env:
        paths.append(Path(env))
    paths.append(Path.cwd() / "config.json")
    paths.append(Path(__file__).resolve().parent.parent / "config.json")
    return paths


def load_config(explicit: str | None = None) -> dict:
    for p in _candidate_paths(explicit):
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                user = json.load(f)
            cfg = {**_DEFAULTS, **user}
            cfg["_path"] = str(p)
            return cfg
    # config.json 이 없어도 기본값으로 동작(키는 환경변수 사용)
    cfg = dict(_DEFAULTS)
    cfg["_path"] = None
    return cfg


def resolve_api_key(cfg: dict) -> str | None:
    """환경변수 우선, 없으면 config 의 api_key. 둘 다 없으면 None."""
    return os.environ.get("ANTHROPIC_API_KEY") or (cfg.get("api_key") or None)


def resolve_nai_token(cfg: dict) -> str | None:
    """NovelAI 토큰: 환경변수 NAI_API_TOKEN 우선, 없으면 config 의 nai_token."""
    return os.environ.get("NAI_API_TOKEN") or (cfg.get("nai_token") or None)
