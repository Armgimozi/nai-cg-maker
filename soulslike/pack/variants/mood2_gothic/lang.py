"""
mood2_gothic 의 언어 덧입힘 (assets/minecraft/lang, assets/souls/lang 의 ko_kr·en_us 에 덧쓴다).

  창 제목 (일시 정지, 제작, 상자 …): 제목 글꼴의 개인 영역 글자로 (언어 문자열은 글꼴을 고를 수 없어 기본 글꼴 안의 개인 영역).
  제목 밑 금실: 일시 정지 제목과 휴식 창 제목 밑에 (글 폭을 클라이언트와 같은 진행 폭으로 재서 가운데에 맞추고, 진행 폭은
                제목 폭 그대로 둔다).
  수치 칸 이름 (souls.gothic.stat.*, 플러그인 사본이 쓴다): 이름 + 그 언어의 이름 열 폭까지 채우는 빈칸 한 글자.
"""
import json
import os
import re

import typeset

# 창 제목: 열쇠 → 언어별 글 (꼴 기호 §7 은 앞에 그대로 둔다)
TITLE_KEYS = {
    "menu.game": {"ko_kr": "게임 메뉴", "en_us": "Game Menu"},
    "container.crafting": {"ko_kr": "§7제작", "en_us": "§7Crafting"},
    "container.inventory": {"ko_kr": "§7보관함", "en_us": "§7Inventory"},
    "container.chest": {"ko_kr": "§7상자", "en_us": "§7Chest"},
    "container.chestDouble": {"ko_kr": "§7큰 상자", "en_us": "§7Large Chest"},
    "container.barrel": {"ko_kr": "§7통", "en_us": "§7Barrel"},
    "container.enderchest": {"ko_kr": "§7엔더 상자", "en_us": "§7Ender Chest"},
}
DIVIDED = ("menu.game",)

# 수치 칸 이름 (플러그인 사본 java_hook 이 같은 열쇠를 쓴다)
STAT_LABELS = {
    "attack": ("공격력", "Attack"),
    "weight": ("무게", "Weight"),
    "bonus_str": ("근력 보정", "Str Bonus"),
    "bonus_dex": ("기량 보정", "Dex Bonus"),
    "bonus_att": ("기억 보정", "Att Bonus"),
    "need_str": ("필요 근력", "Req. Str"),
    "need_dex": ("필요 기량", "Req. Dex"),
    "need_att": ("필요 기억", "Req. Att"),
    "absorb": ("물리 흡수", "Absorption"),
    "stability": ("안정성", "Stability"),
}
VALUE_CHARS = "0123456789.-%SABCDE"


def window_title_syllables():
    syl = []
    for langs in TITLE_KEYS.values():
        for ch in typeset.strip_fmt(langs["ko_kr"]):
            if 0xAC00 <= ord(ch) <= 0xD7A3 and ch not in syl:
                syl.append(ch)
    return syl


def title_text(src_plugin):
    """제목 글꼴로 쓰일 글 (무기 이름, 보스 이름, 휴식 창 제목, 창 제목) 의 한국어 원문을 모은다."""
    path = os.path.join(src_plugin, "src", "main", "resources", "lang", "ko.yml")
    out = []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
                section = line.split(":")[0]
            if section == "weapon" and re.match(r'^    name: "', line):
                out.append(line)
            if section == "boss" and re.match(r'^    name: "', line):
                out.append(line)
            if section == "bonfire" and re.match(r'^  test-name: "', line):
                out.append(line)
    out += [v["ko_kr"] for v in TITLE_KEYS.values()]
    return "".join(out)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _adv(img, scale):
    import numpy as np
    a = np.asarray(img)[..., 3]
    cols = np.nonzero(a.max(0) > 0)[0]
    w = int(cols[-1]) + 1 if len(cols) else 0
    return int(0.5 + w * scale) + 1


def with_divider(title, width, orn_char, orn_vis, orn_adv, spaces):
    """
    제목 글 뒤에 금실을 붙인다. 진행 폭은 제목 폭 그대로라 바닐라가 제목을 가운데에 맞추고, 금실은 제목 가운데 밑에 온다.
    펜: 제목 끝 W → W/2 - D/2 (금실 시작) → 금실 진행 A → 다시 W.
    """
    s1 = spaces.get(-(width + orn_vis) / 2.0)
    back = -(width + orn_vis) / 2.0
    s2 = spaces.get(-(back + orn_adv))
    return title + s1 + orn_char + s2


def build(pack, st, meas):
    """
    언어 파일 덧입힘과 장식 글자 (제목 밑 금실, 설명 칸 실선). 돌려주는 값: (layout (플러그인 사본의 수치 열),
    기본 글꼴에 더할 공급자, 제목 글꼴에 더할 공급자).
    """
    import art_gui
    la_map = {v: k for k, v in meas["la_map"].items()}
    kr_map = {v: k for k, v in meas["kr_map"].items()}
    spaces = meas["spaces"]
    fdir = os.path.join(pack, "assets", "souls", "textures", "font")
    os.makedirs(fdir, exist_ok=True)

    # 제목 밑 금실 (기본 글꼴·제목 글꼴 모두): GUI 120×5, 글자 위가 줄 위 + 11
    div = art_gui.title_divider(120).image()
    div.save(os.path.join(fdir, "gothic_divider.png"))
    orn = chr(st.PUA_ORN)
    orn_vis = div.width / art_gui.ORN_S
    orn_adv = _adv(div, 1.0 / art_gui.ORN_S)
    div_prov = {"type": "bitmap", "file": "souls:font/gothic_divider.png", "height": div.height // art_gui.ORN_S,
                "ascent": -4, "chars": [orn]}

    def to_pua(s):
        out, i = [], 0
        while i < len(s):
            ch = s[i]
            if ch == "§" and i + 1 < len(s):
                out.append(s[i:i + 2])
                i += 2
                continue
            out.append(kr_map.get(ch) or la_map.get(ch) or ch)
            i += 1
        return "".join(out)

    mc_lang = os.path.join(pack, "assets", "minecraft", "lang")
    souls_lang = os.path.join(pack, "assets", "souls", "lang")
    report = {}
    rules = []
    for lang in ("ko_kr", "en_us"):
        path = os.path.join(mc_lang, lang + ".json")
        data = read_json(path) if os.path.exists(path) else {}
        for key, langs in TITLE_KEYS.items():
            v = to_pua(langs[lang])
            if key in DIVIDED:
                v = with_divider(v, meas["pua"].width(v), orn, orn_vis, orn_adv, spaces)
            data[key] = v
        typeset.write_json(path, dict(sorted(data.items())))

        spath = os.path.join(souls_lang, lang + ".json")
        sdata = read_json(spath)
        i = 0 if lang == "ko_kr" else 1
        widths = {k: meas["body"].width(v[i]) for k, v in STAT_LABELS.items()}
        col = max(widths.values()) + st.LABEL_GAP
        for k, v in STAT_LABELS.items():
            sdata["souls.gothic.stat." + k] = v[i] + spaces.get(col - widths[k])
        name = sdata["souls.bonfire.test-name"]
        sdata["souls.bonfire.test-name"] = with_divider(name, meas["title"].width(name), orn, orn_vis, orn_adv, spaces)
        # 수치와 설명 사이 실선: 이 언어의 수치 칸 폭 (두 칸 + 열 간격) 만큼
        block = 2 * (col + st.VALUE_COL) + st.COL_GAP
        rule_ch = chr(st.PUA_ORN + 1 + i)
        # 글자 그림 하나는 텍셀 256 을 넘을 수 없다 (클라이언트 글꼴 아틀라스 한 장이 256×256: 넘으면 빈 네모로 보인다)
        rimg = art_gui.lore_rule(min(block, 124)).image()
        rimg.save(os.path.join(fdir, f"gothic_rule_{lang}.png"))
        rules.append({"type": "bitmap", "file": f"souls:font/gothic_rule_{lang}.png", "height": rimg.height // art_gui.ORN_S,
                      "ascent": 3, "chars": [rule_ch]})
        sdata["souls.gothic.lore-rule"] = rule_ch
        typeset.write_json(spath, dict(sorted(sdata.items())))
        report[lang] = {"label_col": col, "rule": block}
    pads = {}
    for adv in (1, 2, 4, 8, 16, 32, 64):
        pads[spaces.get(adv)] = adv
    gap = spaces.get(st.COL_GAP)
    values = {ch: meas["body"].width(ch) for ch in VALUE_CHARS}
    print("  언어:", report)
    layout = {"values": values, "pads": pads, "gap": gap, "value_col": st.VALUE_COL}
    return layout, [div_prov] + rules, [div_prov]
