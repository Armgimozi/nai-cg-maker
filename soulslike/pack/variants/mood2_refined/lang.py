"""
mood2_refined 언어 파일 덧입히기 (팩 안 JSON 만. 글은 그대로, 장식 글자와 글꼴 거울만 더한다).

  설명 칸 이름 밑 선  souls.weapon.class.* (무기 설명의 첫 줄) 앞에 선 그림 (ITEM, 4배, 52 + 52 GUI) 과 그 폭만큼 되돌아가는 빈칸.
                      선은 이름 줄과 첫 줄 사이 틈에 그려지고 줄의 진행 폭은 그대로다
  가운데 제목 밑 선   일시 정지 제목 (menu.game) 과 휴식 창 제목 (souls.bonfire.test-name) 밑에 TITLE 선 (60 + 60 GUI, 가운데
                      마름모와 덩굴, 양 끝으로 사라진다). [제목][빈칸 -(w+S)/2][선][빈칸 (w-S)/2] 라 전체 폭은 w 그대로
  창 제목 글꼴        en_us 의 창 제목 → 개인 영역의 Cinzel (로마 비문 대문자), ko_kr 의 창 제목 → 개인 영역의 굵은 명조
  빈칸 글자           U+E200+k 는 -k/4, U+E600+k 는 +k/4 GUI 픽셀 (1/4 은 1/12 의 배수라 뒤 글자의 텍셀 정렬이 그대로)
"""
import json
import os

import ornament as orn
import style
import text as textmod
from ornament import Canvas, RES

NEG0, POS0 = 0xE200, 0xE600
TITLE_L, TITLE_R = "", ""
ITEM_L, ITEM_R = "", ""
NEG1 = ""                      # -1 (그림 글자 조각 사이: 진행 폭은 그림 폭 + 1)
TITLE_HALF, ITEM_HALF = 60, 52       # GUI 픽셀 (조각 하나, 4배 그림은 256 텍셀 안)
TITLE_TOP = 9                        # 가운데 제목 밑 선 그림의 위 = 제목 줄 위 + 9 (선은 그 아래 7 텍셀 = + 10.75)
ITEM_H, ITEM_ASCENT = 13, 12         # 설명 칸 선: 그림 위 = 줄 위 - 5 (ascent ≤ 높이라 아래를 비운 키 큰 그림), 선은 텍셀 11
                                     # (= 첫 줄 위 - 2.25, 이름 줄과의 틈)

VANILLA_EN = {"menu.game": "Game Menu"}
TITLE_KEYS = ("menu.game", "container.crafting", "container.inventory", "container.chest", "container.chestDouble",
              "container.barrel", "container.enderchest")


def _rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _wj(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(d.items())), f, ensure_ascii=True, indent=2)
        f.write("\n")


def space(px):
    q = int(round(px * 4))
    out, base, q = "", (NEG0 if q < 0 else POS0), abs(q)
    while q > 0:
        k = min(q, 1023)
        out += chr(base + k)
        q -= k
    return out


def space_provider():
    adv = {}
    for k in range(1, 1024):
        adv[chr(NEG0 + k)] = -k / 4
        adv[chr(POS0 + k)] = k / 4
    adv[NEG1] = -1
    return {"type": "space", "advances": adv}


# ─────────────────────────── 선 그림 ───────────────────────────

def title_rule_halves():
    """가운데 제목 밑 선 (폭 2 × 60 GUI): 줄은 텍셀 7, 가운데에 마름모 (반 대각선 4) 와 양옆 밝은 날개, 양 끝으로 사라진다."""
    W = TITLE_HALF * RES
    full = Canvas(2 * W, 4 * RES)
    y = 7
    full.hline(0, 2 * W - 1, y, orn.GOLD, fade=(W - 30, W - 30))
    cx = W - 1
    for s in (-1, 1):
        for i in range(6, 26):
            full.put(cx + s * i, y, (orn.GOLD_PALE[0], 255 * (1 - (i - 6) / 20) ** 0.7))
        full.lozenge(cx + s * 30, y, 1, edge=orn.GOLD_PALE, core=None, hi=None)
    full.lozenge(cx, y, 4)
    img = full.image()
    left, right = img.crop((0, 0, W, img.height)), img.crop((W, 0, 2 * W, img.height))
    return _mark_width(left), _mark_width(right)


def item_rule_halves():
    """설명 칸 이름 밑 선 (폭 2 × 52 GUI): 줄은 텍셀 11, 왼쪽 끝 작은 마름모와 밝은 날개, 오른쪽으로 사라진다."""
    W = ITEM_HALF * RES
    full = Canvas(2 * W, ITEM_H * RES)
    y = 11
    full.hline(5, 2 * W - 1, y, orn.GOLD, fade=(0, 2 * W - 40))
    for i in range(5, 22):
        full.put(i, y, (orn.GOLD_PALE[0], 255 * (1 - (i - 5) / 17) ** 0.7))
    full.lozenge(2, y, 2)
    img = full.image()
    left, right = img.crop((0, 0, W, img.height)), img.crop((W, 0, 2 * W, img.height))
    return _mark_width(left), _mark_width(right)


def _mark_width(img):
    """진행 폭을 그림 폭 + 1 로 고정: 맨 오른쪽 열 맨 아래에 알파 1 점 (셰이더가 버린다)."""
    px = img.load()
    if px[img.width - 1, img.height - 1][3] == 0:
        px[img.width - 1, img.height - 1] = (12, 11, 10, 1)
    return img


def write_art(pack):
    d = os.path.join(pack, "assets", "souls", "textures", "font")
    os.makedirs(d, exist_ok=True)
    tl, tr = title_rule_halves()
    il, ir = item_rule_halves()
    sheet = lambda a, b: _join(a, b)  # noqa: E731
    sheet(tl, tr).save(os.path.join(d, "refined_rule_title.png"))
    sheet(il, ir).save(os.path.join(d, "refined_rule_item.png"))
    return [
        {"type": "bitmap", "file": "souls:font/refined_rule_title.png", "height": 4, "ascent": 7 - TITLE_TOP,
         "chars": [TITLE_L + TITLE_R]},
        {"type": "bitmap", "file": "souls:font/refined_rule_item.png", "height": ITEM_H, "ascent": ITEM_ASCENT,
         "chars": [ITEM_L + ITEM_R]},
        space_provider(),
    ]


def _join(a, b):
    from PIL import Image
    out = Image.new("RGBA", (a.width + b.width, a.height), (0, 0, 0, 0))
    out.paste(a, (0, 0))
    out.paste(b, (a.width, 0))
    return out


def title_adv():
    return 2 * (TITLE_HALF + 1) - 1


def item_adv():
    return 2 * (ITEM_HALF + 1) - 1


def centred_rule(txt, w, ink="§r"):
    s = title_adv()
    first = space(-(w + s) / 2)
    first_px = -round((w + s) / 2 * 4) / 4
    return txt + ink + first + TITLE_L + NEG1 + TITLE_R + space(-(first_px + s))


def item_rule(txt):
    return "§f" + ITEM_L + NEG1 + ITEM_R + space(-item_adv()) + "§r" + txt


def to_pua(txt, pua):
    out, i = "", 0
    while i < len(txt):
        if txt[i] == "§" and i + 1 < len(txt):
            out += txt[i:i + 2]
            i += 2
            continue
        out += pua.get(txt[i], txt[i])
        i += 1
    return out


def build(pack, info):
    """언어 파일을 고치고, minecraft:default 에 더할 공급자 (선 그림, 빈칸) 를 돌려준다."""
    providers = write_art(pack)
    body = textmod.Measure(pack, info["providers_body"]
                           + [textmod.ttf("title_la", style.TITLE[0][1], 0.0), textmod.ttf("title_kr", style.TITLE[1][1], 0.0)])
    title = textmod.Measure(pack, info["providers_title"])
    report = {}
    for lang in ("ko_kr", "en_us"):
        path = os.path.join(pack, "assets", "souls", "lang", lang + ".json")
        d = _rj(path)
        for k in list(d):
            if k.startswith("souls.weapon.class."):
                d[k] = item_rule(d[k])
        k = "souls.bonfire.test-name"
        if k in d:
            w = title.width(d[k])
            report[f"{lang} {k}"] = w
            d[k] = centred_rule(d[k], w, "§f")
        _wj(path, d)
    for lang in ("ko_kr", "en_us"):
        path = os.path.join(pack, "assets", "minecraft", "lang", lang + ".json")
        d = _rj(path) if os.path.exists(path) else {}
        if lang == "ko_kr":
            for k, v in info["titles_kr"].items():
                d.setdefault(k, v)
            pua = info["pua_kr"]
        else:
            for k, v in VANILLA_EN.items():
                d.setdefault(k, v)
            pua = info["pua_la"]
        for k in TITLE_KEYS:
            if k in d:
                d[k] = to_pua(d[k], pua)
        if "menu.game" in d:
            w = body.width(d["menu.game"])
            report[f"{lang} menu.game"] = w
            d["menu.game"] = centred_rule("§7" + d["menu.game"], w)
        _wj(path, d)
    for k, w in report.items():
        print(f"  제목 폭 {k}: {w:.2f}")
    return providers
