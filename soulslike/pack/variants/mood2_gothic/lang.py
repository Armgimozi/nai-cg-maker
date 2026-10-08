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
    "menu.options": {"ko_kr": "설정", "en_us": "Options"},
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


def build(pack, st, meas):
    """언어 파일 덧입힘. 돌려주는 값: 플러그인 사본에 넘길 layout (값 글자 폭, 빈칸 글자)."""
    la_map = {v: k for k, v in meas["la_map"].items()}
    kr_map = {v: k for k, v in meas["kr_map"].items()}
    spaces = meas["spaces"]

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
    for lang in ("ko_kr", "en_us"):
        path = os.path.join(mc_lang, lang + ".json")
        data = read_json(path) if os.path.exists(path) else {}
        for key, langs in TITLE_KEYS.items():
            data[key] = to_pua(langs[lang])
        typeset.write_json(path, dict(sorted(data.items())))

        spath = os.path.join(souls_lang, lang + ".json")
        sdata = read_json(spath)
        i = 0 if lang == "ko_kr" else 1
        widths = {k: meas["body"].width(v[i]) for k, v in STAT_LABELS.items()}
        col = max(widths.values()) + st.LABEL_GAP
        for k, v in STAT_LABELS.items():
            sdata["souls.gothic.stat." + k] = v[i] + spaces.get(col - widths[k])
        typeset.write_json(spath, dict(sorted(sdata.items())))
        report[lang] = {"label_col": col}
    pads = {}
    for adv in (1, 2, 4, 8, 16, 32, 64):
        pads[spaces.get(adv)] = adv
    gap = spaces.get(st.COL_GAP)
    values = {ch: meas["body"].width(ch) for ch in VALUE_CHARS}
    print("  언어:", report)
    return {"values": values, "pads": pads, "gap": gap, "value_col": st.VALUE_COL}
