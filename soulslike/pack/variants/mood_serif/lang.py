"""
mood_serif 언어 파일 덧입히기 (팩 안 JSON 만 바꾼다. 글은 그대로, 장식 글자만 더한다).

  설명 칸  souls.weapon.class.* (무기 설명의 첫 줄) 앞에 이름 밑 실선 (art.SEP_ITEM) 과 그 폭만큼 되돌아가는 빈칸.
           실선은 첫 줄 위의 틈 (이름 줄과 첫 줄 사이) 에 그려지고 줄의 진행 폭은 그대로라 설명 칸 폭이 바뀌지 않는다
  제목     가운데 맞춘 제목 밑에 실선 (art.SEP_TITLE): 일시 정지 menu.game, 휴식 창 souls.bonfire.test-name.
           [제목][빈칸 -(w+S)/2][실선][빈칸 (w-S)/2] (w 는 제목 글의 폭, S 는 실선 진행 폭) 이라 전체 폭은 w 그대로
           (바닐라가 가운데에 맞추는 폭, 휴식 창 제목 옆 단추 자리가 그대로다). w 는 TTF 의 글자 폭으로 셈한다 (measure)
  영어 창 제목  en_us 의 창 제목 (menu.game, container.*) 을 개인 영역의 Cinzel 그림으로 (로마 비문 대문자)
"""
import json
import os

from fontTools.ttLib import TTFont

import art
import style

VANILLA_KO = {"menu.game": "게임 메뉴"}
VANILLA_EN = {"menu.game": "Game Menu"}
CINZEL_TITLES = ("menu.game", "container.crafting", "container.inventory", "container.chest", "container.chestDouble",
                 "container.barrel", "container.enderchest")


def _rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _wj(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(d.items())), f, ensure_ascii=True, indent=2)
        f.write("\n")


class Measure:
    """글꼴 공급자 차례대로 글자 폭 (GUI 픽셀) 을 셈한다. FreeType 은 size × oversample 픽셀 em 에서 힌팅한 진행 폭 (정수
    픽셀) 을 주고 마인크래프트는 그것을 oversample 로 나눈다."""

    def __init__(self, pack, providers, spaces):
        self.fonts = []
        for p in providers:
            name = p["file"].split(":", 1)[1]
            f = TTFont(os.path.join(pack, "assets", "souls", "font", name))
            ppem = round(p["size"] * p["oversample"])
            self.fonts.append((f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm, ppem, p["oversample"]))
        self.spaces = spaces

    def char(self, ch):
        if ch in self.spaces:
            return self.spaces[ch]
        for cmap, hmtx, upm, ppem, ov in self.fonts:
            g = cmap.get(ord(ch))
            if g is not None:
                return round(hmtx[g][0] * ppem / upm) / ov
        return 0.0

    def width(self, text):
        out, i = 0.0, 0
        while i < len(text):
            if text[i] == "§" and i + 1 < len(text):
                i += 2
                continue
            out += self.char(text[i])
            i += 1
        return out


def centred_rule(text, w, ink="\u00a7r"):
    """ink: 실선 앞의 § 코드. 그림 글자는 글자색이 곱해지므로 흰색 (바닐라 기본 = §r, 플러그인 색 글 = §f) 으로 되돌린다."""
    s = art.sep_advance(art.SEP_TITLE_W)
    return text + ink + art.space(-(w + s) / 2) + art.SEP_TITLE + art.space((w - s) / 2)


def item_rule(text):
    """첫 줄은 회색 (#858079) 이라 실선 앞에서 §f (흰색 = 그림 색 그대로), 글 앞에서 §r (줄의 색으로)."""
    s = art.sep_advance(art.SEP_ITEM_W)
    return "\u00a7f" + art.SEP_ITEM + art.space(-s) + "\u00a7r" + text


def build(pack, info):
    spaces = {" ": style.SPACE}
    body = Measure(pack, info["providers_body"] + [style.ttf("title_la", style.TITLE[0][1], style.TITLE[0][2])], spaces)
    title = Measure(pack, info["providers_title"], spaces)
    pua = info["pua"]
    report = {}
    # 1. 게임 문구 (souls)
    for lang in ("ko_kr", "en_us"):
        path = os.path.join(pack, "assets", "souls", "lang", lang + ".json")
        d = _rj(path)
        for k in list(d):
            if k.startswith("souls.weapon.class."):
                d[k] = item_rule(d[k])
        k = "souls.bonfire.test-name"
        w = title.width(d[k])
        d[k] = centred_rule(d[k], w, "\u00a7f")
        report[f"{lang} {k}"] = w
        _wj(path, d)
    # 2. 바닐라 (minecraft): 일시 정지 제목 밑 실선, 영어 창 제목은 Cinzel
    for lang, base in (("ko_kr", VANILLA_KO), ("en_us", VANILLA_EN)):
        path = os.path.join(pack, "assets", "minecraft", "lang", lang + ".json")
        d = _rj(path)
        for k, v in base.items():
            d.setdefault(k, v)
        if lang == "en_us":
            for k in CINZEL_TITLES:
                if k in d:
                    d[k] = to_pua(d[k], pua)
        w = body.width(d["menu.game"])
        report[f"{lang} menu.game"] = w
        # 일시 정지 제목은 §7 (셰이더가 흐린 옛 금빛으로), 실선 앞에서 §r
        d["menu.game"] = centred_rule("\u00a77" + d["menu.game"], w)
        _wj(path, d)
    for k, w in report.items():
        print(f"  제목 폭 {k}: {w:.2f}")
    return report


def to_pua(text, pua):
    """§ 코드는 두고 ASCII 글자를 개인 영역 Cinzel 로. 영어 제목은 대문자로 (Cinzel 소문자는 작은 대문자라 그대로도 된다)."""
    out, i = "", 0
    while i < len(text):
        if text[i] == "§" and i + 1 < len(text):
            out += text[i:i + 2]
            i += 2
            continue
        out += pua.get(text[i], text[i])
        i += 1
    return out
