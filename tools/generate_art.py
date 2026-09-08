"""캐릭터 아트 일괄 생성 — NovelAI → web/game/art/

  python tools/generate_art.py                  # 아직 없는 캐릭터의 기본 그림
  python tools/generate_art.py --force          # 전부 다시 생성
  python tools/generate_art.py --only seraphine kaguya
  python tools/generate_art.py --expressions    # 표정 차분(눈 감음 등) 생성
  python tools/generate_art.py --expressions --variants blink
  python tools/generate_art.py --keep-metadata  # 메타데이터를 남긴다(기본은 제거)

토큰: 환경변수 NAI_API_TOKEN 또는 config.json 의 nai_token.

표정 차분
  기본 그림과 **같은 시드**로 프롬프트 끝에 표정 태그만 덧붙여 재생성한다.
  같은 시드면 구도·인물이 거의 그대로 유지되고 표정만 바뀌므로, 인페인트로
  얼굴을 마스킹하는 것보다 안정적이다. 기본 그림을 뽑을 때 쓴 시드는
  web/game/art/manifest.json 에 기록되며 차분 생성 때 그대로 재사용된다.
  게임 클라이언트는 blink 차분이 있으면 눈 깜빡임 연출에 자동으로 쓴다.

메타데이터
  저장 전에 기본적으로 두 가지를 제거한다.
    1) PNG 텍스트 청크(tEXt/iTXt) — 프롬프트·시드·"Software: NovelAI" 가 들어있다.
       Pillow 로 다시 저장하면서 pnginfo 를 넘기지 않으면 사라진다.
    2) 알파 채널 LSB 스테가노그래피(스텔스 워터마크) — 알파 채널을 버리고
       RGB 로 변환하면 사라진다.
  메타데이터 제거가 이용약관·저작권 문제를 해결해주지는 않는다. 상업적으로
  배포할 계획이라면 NovelAI 구독 약관을 먼저 확인할 것.
"""

from __future__ import annotations

import argparse
import io
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from danbooru_tags.config import load_config, resolve_nai_token  # noqa: E402
from danbooru_tags.nai import NovelAIClient  # noqa: E402
from gacha import art  # noqa: E402
from gacha.content import CHARACTERS, NAI_NEGATIVE  # noqa: E402

OUT = art.ART_DIR
SEED_MAX = 2 ** 32 - 1


def strip_metadata(raw: bytes) -> bytes:
    """PNG 텍스트 청크와 알파채널 스텔스 워터마크를 제거한 PNG 바이트."""
    try:
        from PIL import Image
    except ImportError:
        print("  ! Pillow 가 없어 메타데이터를 제거하지 못했습니다 "
              "(pip install Pillow)", file=sys.stderr)
        return raw
    with Image.open(io.BytesIO(raw)) as im:
        # 알파 채널을 버리면 LSB 에 숨겨진 데이터도 함께 사라진다.
        rgb = im.convert("RGB")
        buf = io.BytesIO()
        # pnginfo 를 넘기지 않으므로 tEXt/iTXt 청크가 재작성되지 않는다.
        rgb.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _jobs(args, manifest: dict) -> list[tuple[dict, str]]:
    """(캐릭터, variant) 목록. variant 가 "" 면 기본 그림."""
    chars = [c for c in CHARACTERS if args.only is None or c["id"] in args.only]
    variants = [""] if not args.expressions else list(
        args.variants or art.EXPRESSIONS.keys())
    jobs = []
    for c in chars:
        for v in variants:
            if v and not manifest.get(c["id"], {}).get("seed"):
                print(f"  · {c['name']}: 기본 그림이 없어 차분을 건너뜁니다 "
                      f"(먼저 기본 그림을 생성하세요)")
                break
            if args.force or art.art_file(c["id"], v) is None:
                jobs.append((c, v))
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser(description="캐릭터 아트 생성")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 생성")
    ap.add_argument("--only", nargs="*", default=None, help="특정 캐릭터 id 만")
    ap.add_argument("--expressions", action="store_true",
                    help="기본 그림 대신 표정 차분을 생성(같은 시드 재사용)")
    ap.add_argument("--variants", nargs="*", default=None,
                    choices=list(art.EXPRESSIONS),
                    help="생성할 차분 종류 (기본: 전부)")
    ap.add_argument("--seed", type=int, default=None,
                    help="기준 시드(캐릭터마다 +1). 미지정 시 무작위")
    ap.add_argument("--keep-metadata", action="store_true",
                    help="메타데이터를 지우지 않고 원본 그대로 저장")
    ap.add_argument("--width", type=int, default=832)
    ap.add_argument("--height", type=int, default=1216)
    ap.add_argument("--delay", type=float, default=2.0, help="요청 간 대기(초)")
    args = ap.parse_args()

    cfg = load_config()
    token = resolve_nai_token(cfg)
    if not token:
        print("NAI_API_TOKEN 환경변수나 config.json 의 nai_token 이 필요합니다.",
              file=sys.stderr)
        return 1

    client = NovelAIClient(token, cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = art.load_manifest()

    jobs = _jobs(args, manifest)
    if not jobs:
        print("생성할 대상이 없습니다. (--force 로 전부 다시 생성)")
        return 0

    kind = "표정 차분" if args.expressions else "기본 그림"
    print(f"{kind} {len(jobs)}장 생성 · 모델 {client.model} · "
          f"{args.width}x{args.height} · "
          f"메타데이터 {'유지' if args.keep_metadata else '제거'}")

    fails = 0
    for i, (c, variant) in enumerate(jobs, 1):
        label = f"{c['name']}" + (f" [{variant}]" if variant else "")
        # 차분은 기본 그림과 같은 시드를 써야 같은 인물이 나온다.
        if variant:
            seed = manifest[c["id"]]["seed"]
        elif args.seed is not None:
            seed = args.seed + i
        else:
            seed = random.randint(0, SEED_MAX)

        print(f"[{i}/{len(jobs)}] {label} (seed {seed}) …", flush=True)
        try:
            raw, used_seed = client.generate(
                art.build_prompt(c, variant), [], NAI_NEGATIVE, seed=seed,
                width=args.width, height=args.height)
        except Exception as e:  # noqa: BLE001
            print(f"  ! 실패: {e}", file=sys.stderr)
            fails += 1
            continue

        if not args.keep_metadata:
            raw = strip_metadata(raw)
        stem = f"{c['id']}@{variant}" if variant else c["id"]
        path = OUT / f"{stem}.png"
        path.write_bytes(raw)

        if not variant:
            rec = manifest.setdefault(c["id"], {})
            rec["seed"] = used_seed
            rec["prompt"] = art.build_prompt(c)
            art.save_manifest(manifest)

        print(f"  → {path.relative_to(ROOT)}  ({len(raw) // 1024}KB)")
        if i < len(jobs):
            time.sleep(args.delay)

    if not args.expressions and not fails:
        print("\n다음 단계: 눈 깜빡임용 표정 차분을 만들려면\n"
              "    python tools/generate_art.py --expressions --variants blink")
    print(f"완료. 실패 {fails}건." if fails else "완료.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
