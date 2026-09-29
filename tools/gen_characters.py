"""NAI 로 캐릭터 일러스트 일괄 생성 → game/assets/illust/<id>.png

NAI 는 **일러스트만** 만든다(도트 스프라이트는 직접 제작). 게임의 상세 화면에서
보여 줄 캐릭터 일러스트를 characters.json 의 prompt 로 생성한다.

    python tools/gen_characters.py                 # 일러스트가 없는 캐릭터만 생성
    python tools/gen_characters.py --only draconia # 특정 캐릭터만
    python tools/gen_characters.py --dry-run       # 프롬프트만 출력(Anlas 소모 없음)
    python tools/gen_characters.py --force --seed 1234
    python tools/gen_characters.py --max-height 1024 --webp

프롬프트 = style.prefix + 캐릭터 prompt. 네거티브 = style.negative.
style.reference 에 이미지 경로를 두면 Precise Reference(style) 로 그림체를 통일한다
(생성당 +5 Anlas). 모델/해상도/스텝은 config.json 의 nai_* 값을 따른다.

토큰: 환경변수 NAI_API_TOKEN 또는 config.json 의 nai_token.
원본 렌더는 cache/nai_illust_raw/ 에도 보관(깃 제외 · Godot 밖)해 재처리에 쓴다.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from danbooru_tags.config import load_config, resolve_nai_token  # noqa: E402
from danbooru_tags.nai import NovelAIClient  # noqa: E402

GAME = ROOT / "game"
DATA = GAME / "data" / "characters.json"
OUT = GAME / "assets" / "illust"
RAW = ROOT / "cache" / "nai_illust_raw"   # 깃 제외(cache/) · Godot 프로젝트 밖


def build_prompt(style: dict, ch: dict) -> str:
    parts = [style.get("prefix", "").strip(), ch.get("prompt", "").strip()]
    return ", ".join(p for p in parts if p)


def _references(style: dict) -> list[dict]:
    ref = style.get("reference") or ""
    if not ref:
        return []
    p = (GAME / ref) if not Path(ref).is_absolute() else Path(ref)
    if not p.is_file():
        print(f"! style.reference 파일이 없어 무시합니다: {p}")
        return []
    return [{"image": base64.b64encode(p.read_bytes()).decode(), "mode": "precise",
             "ref_type": "style", "strength": 1.0, "fidelity": 1.0}]


def postprocess(png: bytes, max_height: int, webp: bool) -> tuple[bytes, str]:
    """모바일용으로 축소(긴 변 기준)하고 PNG/WebP 로 인코딩."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if max_height and im.height > max_height:
        w = round(im.width * max_height / im.height)
        im = im.resize((w, max_height), Image.LANCZOS)
    out = io.BytesIO()
    if webp:
        im.save(out, "WEBP", quality=88, method=6)
        return out.getvalue(), "webp"
    im.save(out, "PNG", optimize=True)
    return out.getvalue(), "png"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None, help="이 id 들만 생성")
    ap.add_argument("--force", action="store_true", help="이미 있는 일러스트도 다시 생성")
    ap.add_argument("--dry-run", action="store_true", help="프롬프트만 출력하고 생성하지 않음")
    ap.add_argument("--seed", type=int, default=None, help="모든 캐릭터에 같은 시드(구도 통일)")
    ap.add_argument("--max-height", type=int, default=1216, help="저장 시 최대 세로 픽셀(0=원본)")
    ap.add_argument("--webp", action="store_true", help="PNG 대신 WebP 로 저장(용량 절감)")
    ap.add_argument("--sleep", type=float, default=1.5, help="요청 사이 대기(초) — 429 방지")
    args = ap.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    style = data.get("style", {})
    negative = style.get("negative", "")
    chars = data["characters"]
    if args.only:
        wanted = set(args.only)
        chars = [c for c in chars if c["id"] in wanted]
        missing = wanted - {c["id"] for c in chars}
        if missing:
            print(f"! 없는 id: {', '.join(sorted(missing))}")

    OUT.mkdir(parents=True, exist_ok=True)
    ext = "webp" if args.webp else "png"

    todo = []
    for ch in chars:
        dst = OUT / f"{ch['id']}.{ext}"
        other = OUT / f"{ch['id']}.{'png' if ext == 'webp' else 'webp'}"
        if (dst.exists() or other.exists()) and not args.force:
            continue
        todo.append(ch)
    if not todo:
        print("생성할 캐릭터가 없습니다(모두 있음). --force 로 다시 생성할 수 있습니다.")
        return

    print(f"대상 {len(todo)}명 / 네거티브: {negative[:60]}...")
    for ch in todo:
        print(f"  [{ch['id']}] {build_prompt(style, ch)}")
    if args.dry_run:
        return

    cfg = load_config()
    token = resolve_nai_token(cfg)
    if not token:
        sys.exit("NAI 토큰이 없습니다. NAI_API_TOKEN 환경변수 또는 config.json 의 nai_token 을 설정하세요.")
    client = NovelAIClient(token, cfg)
    refs = _references(style)
    if refs:
        print("Precise Reference(style) 적용 — 생성당 +5 Anlas")

    RAW.mkdir(parents=True, exist_ok=True)
    ok = 0
    for i, ch in enumerate(todo, 1):
        cid = ch["id"]
        prompt = build_prompt(style, ch)
        print(f"({i}/{len(todo)}) {cid} 생성 중...", end=" ", flush=True)
        try:
            png, seed = client.generate(prompt, [], negative, seed=args.seed, references=refs)
        except Exception as e:  # noqa: BLE001
            print(f"실패: {e}")
            continue
        (RAW / f"{cid}_{seed}.png").write_bytes(png)
        blob, used_ext = postprocess(png, args.max_height, args.webp)
        dst = OUT / f"{cid}.{used_ext}"
        dst.write_bytes(blob)
        ok += 1
        print(f"완료 (seed {seed}, {len(blob) // 1024} KB) → {dst.relative_to(ROOT)}")
        if i < len(todo) and args.sleep > 0:
            time.sleep(args.sleep)
    print(f"끝: 성공 {ok} / {len(todo)}. 원본은 {RAW.relative_to(ROOT)} 에 보관됨.")


if __name__ == "__main__":
    main()
