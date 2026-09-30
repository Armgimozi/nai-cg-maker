#!/usr/bin/env python3
"""UI 미리보기(mockup/index.html) 만들기 — 로블록스에 올리기 전에 브라우저로 보는 화면 시안.

    python3 mockup/build.py          # art/png + src/shared 를 읽어 mockup/index.html 을 새로 씀
    node mockup/shoot.js             # (선택) index.html -> screen*.png(도감 전체·대륙 탭은 PC + 휴대폰 3-2·4-2), overview.png

- 그림: art/png/*.png 를 base64 data URI 로 넣음 -> index.html 한 파일만 있으면 어디서나 열림.
- 데이터: src/shared/Landmarks.luau (등급/대륙/명소), Config.luau (별/수입/업그레이드) 를 읽어서 넣음.
  -> 명소나 밸런스 값을 바꾸고 다시 돌리면 미리보기도 같이 바뀜.
- 글꼴: Google Fonts 에서 Fredoka One, Luckiest Guy(라틴) + Noto Sans KR(쓰는 글자만 subset)을
  받아 mockup/fonts/ 에 캐시하고 base64 로 넣음. 네트워크가 막혀 있으면 글꼴 없이(로컬 대체 글꼴) 만듦.
  한글 굵기(KR_WEIGHT): 로블록스는 글꼴에 없는 한글을 대체 글꼴(Noto Sans CJK)로 그리는데, 게임이 쓰는
  Enum.Font.FredokaOne / LuckiestGuy 는 둘 다 Regular(400) 로 등록된 글꼴이라 한글도 Regular 로 봄.
- 3D 배치 모드 배경(mockup/bg/edit_*.jpg + .json): mockup/edit_backdrops.sh 가 맵 미리보기 도구로 진짜 월드 +
  진짜 ParkEdit 를 그린 그림. 있으면 window.BACKDROPS 로 넣음(없으면 6번대 화면에 "배경 없음" 표시).
- 표준 라이브러리만 씀.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ART = ROOT / "art" / "png"
SHARED = ROOT / "src" / "shared"
SRC = HERE / "src"
FONTS = HERE / "fonts"
BACKDROPS = HERE / "bg"
OUT = HERE / "index.html"

# 한글 대체 글꼴 굵기. FontFace 굵기(FredokaOne/LuckiestGuy = Regular)를 따름 -> 400
KR_WEIGHT = 400

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


# --- Luau 데이터 읽기 ---------------------------------------------------------

def rgb(text: str) -> list[int]:
    return [int(v) for v in re.findall(r"\d+", text)]


def parse_landmarks() -> dict:
    text = (SHARED / "Landmarks.luau").read_text(encoding="utf-8")

    tiers = []
    for m in re.finditer(
        r'\{\s*Rank\s*=\s*(\d+),\s*Name\s*=\s*"([^"]+)",\s*MinOneIn\s*=\s*(\d+),\s*Color\s*=\s*Color3\.fromRGB\(([^)]*)\)',
        text,
    ):
        tiers.append({"Rank": int(m[1]), "Name": m[2], "MinOneIn": int(m[3]), "Color": rgb(m[4])})

    block = re.search(r"Landmarks\.Regions\s*=\s*\{(.*?)\}\s*::", text, re.S)
    if not block:
        raise SystemExit("Landmarks.Regions 를 찾지 못했어요")
    regions = []
    for m in re.finditer(
        r'\{\s*Id\s*=\s*"(\w+)",\s*Name\s*=\s*"([^"]+)",.*?Color\s*=\s*Color3\.fromRGB\(([^)]*)\)', block[1]
    ):
        regions.append({"Id": m[1], "Name": m[2], "Color": rgb(m[3])})

    world = re.search(r"Landmarks\.WorldRegion\s*=\s*\{(.*?)\}\s*::", text, re.S)
    world_region = None
    if world:
        wid = re.search(r'Id\s*=\s*"(\w+)"', world[1])
        wname = re.search(r'Name\s*=\s*"([^"]+)"', world[1])
        wcolor = re.search(r"Color3\.fromRGB\(([^)]*)\)", world[1])
        if wid and wname and wcolor:
            world_region = {"Id": wid[1], "Name": wname[1], "Color": rgb(wcolor[1])}

    landmarks = []
    pattern = re.compile(
        r'^\s*\{\s*"(\w+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\d+),\s*"(\w+)",\s*"(\w+)",\s*'
        r"rgb\(([^)]*)\),\s*rgb\(([^)]*)\),\s*rgb\(([^)]*)\),\s*M\.(\w+)\s*\}",
        re.M,
    )
    for m in pattern.finditer(text):
        landmarks.append(
            {
                "Id": m[1],
                "Name": m[2],
                "Subtitle": m[3],
                "OneIn": int(m[4]),
                "Region": m[5],
                "Shape": m[6],
                "Primary": rgb(m[7]),
                "Secondary": rgb(m[8]),
                "Accent": rgb(m[9]),
                "Material": m[10],
            }
        )
    if len(tiers) < 3 or len(regions) < 2 or len(landmarks) < 5:
        raise SystemExit(f"Landmarks.luau 를 읽지 못했어요 (tiers={len(tiers)} regions={len(regions)} landmarks={len(landmarks)})")
    return {"Tiers": tiers, "Regions": regions, "WorldRegion": world_region, "List": landmarks}


def parse_config() -> dict:
    text = (SHARED / "Config.luau").read_text(encoding="utf-8")

    def number(name: str) -> float:
        m = re.search(rf"\b{name}\s*=\s*([\d.]+)", text)
        if not m:
            raise SystemExit(f"Config.{name} 를 찾지 못했어요")
        value = float(m[1])
        return int(value) if value.is_integer() else value

    def numbers(name: str) -> list:
        m = re.search(rf"\b{name}\s*=\s*\{{([^}}]*)\}}", text)
        if not m:
            raise SystemExit(f"Config.{name} 를 찾지 못했어요")
        return [float(v) if "." in v else int(v) for v in re.findall(r"[\d.]+", m[1])]

    upgrades = []
    section = text[text.index("Upgrades") :]
    for chunk in re.split(r"\n\s*\{\s*\n", section)[1:]:
        fields = {}
        for key in ("Id", "Name"):
            m = re.search(rf'\b{key}\s*=\s*"([^"]+)"', chunk)
            if m:
                fields[key] = m[1]
        for key in ("BasePrice", "Growth", "MaxLevel", "PerLevel"):
            m = re.search(rf"\b{key}\s*=\s*([\d.]+)", chunk)
            if m:
                value = float(m[1])
                fields[key] = int(value) if value.is_integer() and key != "PerLevel" else value
        if "Id" in fields and "BasePrice" in fields:
            upgrades.append(fields)
    if len(upgrades) < 1:
        raise SystemExit("Config.Upgrades 를 읽지 못했어요")

    # 환생 단계 (HUD 의 환생 "!" 배지 = 다음 단계 조건을 채웠는지). 없으면 빈 목록
    rebirths = []
    block = re.search(r"\bREBIRTHS\s*=\s*\{(.*?)\n\s*\}", text, re.S)
    for m in re.finditer(r"\{\s*Coins\s*=\s*(\d+),\s*Landmarks\s*=\s*\{([^}]*)\}\s*\}", block[1] if block else ""):
        rebirths.append({"Coins": int(m[1]), "Landmarks": re.findall(r'"(\w+)"', m[2])})
    growth = re.search(r"\bREBIRTH_COIN_GROWTH\s*=\s*([\d.]+)", text)

    return {
        "ROLL_COOLDOWN": number("ROLL_COOLDOWN"),
        "BASE_LUCK": number("BASE_LUCK"),
        "ANNOUNCE_ONE_IN": number("ANNOUNCE_ONE_IN"),
        "DISCOVERY_BONUS_MULT": number("DISCOVERY_BONUS_MULT"),
        "BASE_SLOTS": number("BASE_SLOTS"),
        "PARK_GRID": number("PARK_GRID"),
        "TIER_INCOME": numbers("TIER_INCOME"),
        "STAR_THRESHOLDS": numbers("STAR_THRESHOLDS"),
        "STAR_INCOME_BONUS": number("STAR_INCOME_BONUS"),
        "REBIRTH_LUCK_MULT": number("REBIRTH_LUCK_MULT"),
        "STAMP_MAX_RANK": number("STAMP_MAX_RANK"),
        "REGION_LUCK_BONUS": number("REGION_LUCK_BONUS"),
        "Upgrades": upgrades,
        "REBIRTHS": rebirths,
        "REBIRTH_COIN_GROWTH": float(growth[1]) if growth else 4,
    }


# --- 그림 -------------------------------------------------------------------

def load_art() -> dict[str, str]:
    art = {}
    for path in sorted(ART.glob("*.png")):
        art[path.stem] = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    if not art:
        raise SystemExit(f"{ART} 에 PNG 가 없어요")
    return art


def load_backdrops() -> dict[str, dict]:
    """mockup/bg/<이름>.jpg + <이름>.json -> { 이름: { image: data URI, info: hook 값 } }"""
    result = {}
    for path in sorted(BACKDROPS.glob("*.jpg")) if BACKDROPS.is_dir() else []:
        info_path = path.with_suffix(".json")
        info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.is_file() else None
        result[path.stem] = {
            "image": "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii"),
            "info": info,
        }
    return result


# --- 글꼴 -------------------------------------------------------------------

def _ssl_context() -> ssl.SSLContext:
    for candidate in (os.environ.get("SSL_CERT_FILE"), os.environ.get("REQUESTS_CA_BUNDLE"), "/root/.ccr/ca-bundle.crt"):
        if candidate and Path(candidate).is_file():
            return ssl.create_default_context(cafile=candidate)
    return ssl.create_default_context()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=20, context=_ssl_context()) as response:
        return response.read()


def font_url(css: str, block_hint: str | None) -> str:
    """css2 응답에서 woff2 주소 하나. block_hint 가 있으면 그 주석(/* latin */ 등) 블록에서."""
    if block_hint:
        m = re.search(rf"/\*\s*{block_hint}\s*\*/\s*@font-face\s*\{{(.*?)\}}", css, re.S)
        if m:
            css = m[1]
    m = re.search(r"url\((https://[^)]+)\)", css)
    if not m:
        raise ValueError("글꼴 주소 없음")
    return m[1]


def cached_font(name: str, css_url: str, block_hint: str | None) -> bytes | None:
    FONTS.mkdir(exist_ok=True)
    path = FONTS / f"{name}.woff2"
    if path.is_file() and path.stat().st_size > 0:
        return path.read_bytes()
    try:
        css = fetch(css_url).decode("utf-8")
        data = fetch(font_url(css, block_hint))
    except Exception as error:  # 네트워크가 막혀 있어도 미리보기는 만든다
        print(f"  ! 글꼴 {name} 을(를) 받지 못해 대체 글꼴을 씀: {error}", file=sys.stderr)
        return None
    path.write_bytes(data)
    return data


def korean_chars(*texts: str) -> str:
    chars = set("★☆×·")
    for text in texts:
        for ch in text:
            if ord(ch) > 0x7F and not (0xD800 <= ord(ch) <= 0xDFFF) and ch not in " ":
                chars.add(ch)
    return "".join(sorted(chars))


def load_fonts(text_for_subset: str) -> dict[str, str]:
    fonts = {}
    base = "https://fonts.googleapis.com/css2?display=block&family="
    fredoka = cached_font("FredokaOne-latin", base + "Fredoka+One", "latin")
    lucky = cached_font("LuckiestGuy-latin", base + "Luckiest+Guy", "latin")
    chars = korean_chars(text_for_subset)
    digest = hashlib.sha1(chars.encode("utf-8")).hexdigest()[:10]
    kr_name = f"NotoSansKR-{KR_WEIGHT}-{digest}"
    # 글자나 굵기가 바뀌면 새 subset (이전 subset 파일은 지움)
    for old in FONTS.glob("NotoSansKR-*.woff2") if FONTS.is_dir() else []:
        if old.stem != kr_name:
            old.unlink()
    korean = cached_font(
        kr_name,
        base + f"Noto+Sans+KR:wght@{KR_WEIGHT}&text=" + urllib.parse.quote(chars),
        None,
    )
    for key, data in (("fredoka", fredoka), ("lucky", lucky), ("korean", korean)):
        if data:
            fonts[key] = "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")
    return fonts


def font_css(fonts: dict[str, str]) -> str:
    rules = []
    if "fredoka" in fonts:
        rules.append(f"@font-face{{font-family:'Fredoka One';src:url({fonts['fredoka']}) format('woff2');font-display:block}}")
    if "lucky" in fonts:
        rules.append(f"@font-face{{font-family:'Luckiest Guy';src:url({fonts['lucky']}) format('woff2');font-display:block}}")
    if "korean" in fonts:
        # 굵기 지정 없이(=400) 등록 -> 화면 글자(font-weight 기본값)와 그대로 맞음, 가짜 굵게 없음
        rules.append(f"@font-face{{font-family:'KR Fallback';src:url({fonts['korean']}) format('woff2');font-display:block}}")
    return "\n".join(rules)


# --- 조립 -------------------------------------------------------------------

def main() -> None:
    page = (SRC / "page.html").read_text(encoding="utf-8")
    css = (SRC / "app.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")

    data = {"Landmarks": parse_landmarks(), "Config": parse_config()}
    art = load_art()
    subset_source = page + js + json.dumps(data, ensure_ascii=False)
    fonts = load_fonts(subset_source)
    backdrops = load_backdrops()

    payload = (
        "window.ART = " + json.dumps(art) + ";\n"
        + "window.GAME = " + json.dumps(data, ensure_ascii=False) + ";\n"
        + "window.FONTS_EMBEDDED = " + json.dumps(sorted(fonts)) + ";\n"
        + "window.BACKDROPS = " + json.dumps(backdrops, ensure_ascii=False) + ";\n"
    )
    html = (
        page.replace("/*FONTS*/", font_css(fonts))
        .replace("/*CSS*/", css)
        .replace("/*DATA*/", payload)
        .replace("/*APP*/", js)
    )
    OUT.write_text(html, encoding="utf-8")
    size = OUT.stat().st_size
    shown = OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT
    print(
        f"{shown}  {size / 1024:.0f} KB  "
        f"(그림 {len(art)}개, 배치 모드 배경 {len(backdrops)}개, 명소 {len(data['Landmarks']['List'])}개, 대륙 {len(data['Landmarks']['Regions'])}개, "
        f"글꼴 {', '.join(sorted(fonts)) or '없음(대체 글꼴)'})"
    )


if __name__ == "__main__":
    main()
