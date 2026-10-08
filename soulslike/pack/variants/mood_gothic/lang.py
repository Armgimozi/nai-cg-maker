"""
mood_gothic 의 글꼴 정의와 언어 덧입힘.

글꼴
  minecraft:default   앞에 TTF 둘 (본문 로마자, 본문 한글) 을 끼워 바닐라 화면·채팅·설명 칸·개수까지 명조로. 그 뒤에
                      제목 글꼴 둘의 개인 영역 (창 제목을 언어 파일만으로 제목 글꼴로 그리려고), 장식 글자 (금실), 자리 맞춤
                      빈칸. 기본 팩의 공급자 (YOU DIED 그림 글자와 띠) 는 그 뒤에 그대로.
  souls:gothic_title  제목 (Marcellus SC + 송명). 플러그인 사본이 아이템 이름·휴식 창 제목에 입힌다. 금실·빈칸도 들어 있다.
  souls:gothic_lore   설명 (본문 글꼴을 한 단 작게): 조용한 톤, 줄 사이가 넉넉해 보이게.

언어 (assets/minecraft/lang, assets/souls/lang 의 ko_kr·en_us 에 덧쓴다)
  창 제목 (일시 정지, 제작, 상자, 설정 …) 을 제목 글꼴의 개인 영역 글자로. 일시 정지 제목 밑에는 금실 (글 폭을 이 글꼴의
  진행 폭으로 재서 금실을 제목 가운데에 맞추고 전체 진행 폭은 제목 폭 그대로 둔다).
  휴식 창 제목 (souls.bonfire.test-name, 제목 글꼴) 밑에도 금실.
  수치 칸의 이름 (souls.gothic.stat.*, 플러그인 사본이 쓴다): 이름 + 그 언어의 이름 열 폭까지 채우는 빈칸 한 글자.
  값은 플러그인이 오른쪽에 맞춘다 (값 글자의 진행 폭과 빈칸 글자를 layout 으로 넘긴다).
"""
import json
import os

ORN_FILE = "souls:font/gothic_orn.png"

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
DIVIDED = ("menu.game",)          # 제목 밑 금실

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


def strip_fmt(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "§" and i + 1 < len(s):
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def title_hangul(st):
    """창 제목에 나오는 한글 음절 → 개인 영역 글자 (U+F200 부터 차례로). 휴식 창 제목은 제목 글꼴 자체라 필요 없다."""
    syl = []
    for langs in TITLE_KEYS.values():
        for ch in strip_fmt(langs["ko_kr"]):
            if 0xAC00 <= ord(ch) <= 0xD7A3 and ch not in syl:
                syl.append(ch)
    return {chr(st.PUA_TITLE_KR + i): ch for i, ch in enumerate(syl)}


def title_latin(st):
    return {chr(st.PUA_TITLE_LA + i): chr(0x20 + i) for i in range(0x7F - 0x20)}


class Spaces:
    """기본 글꼴 (과 제목 글꼴) 의 자리 맞춤 빈칸: 같은 폭이면 한 글자를 다시 쓴다."""

    def __init__(self, start):
        self.next = start
        self.by_adv = {}

    def get(self, adv):
        adv = round(adv * 4) / 4.0
        if adv not in self.by_adv:
            self.by_adv[adv] = chr(self.next)
            self.next += 1
        return self.by_adv[adv]

    def provider(self):
        return {"type": "space", "advances": {ch: adv for adv, ch in sorted(self.by_adv.items(), key=lambda t: t[1])}}


class Measure:
    """글 진행 폭 (GUI 픽셀): 공급자 차례대로 처음 가진 글꼴의 폭."""

    def __init__(self, metrics, extra=None):
        self.metrics = metrics
        self.extra = extra or {}

    def width(self, text):
        w = 0.0
        for ch in strip_fmt(text):
            if ch in self.extra:
                w += self.extra[ch]
                continue
            for m in self.metrics:
                a = m.advance(ch)
                if a is not None:
                    w += a
                    break
            else:
                raise KeyError(f"글꼴에 없는 글자 {ch!r} ({text})")
        return w


def divider_glyph_advance(img_w, scale=2):
    """비트맵 공급자의 진행 폭 (클라이언트와 같은 식): 오른쪽 끝 불투명 열 + 1 을 줄여 반올림하고 + 1."""
    return int(0.5 + img_w / scale) + 1


def with_divider(title, width, orn_char, orn_vis, orn_adv, spaces):
    """
    제목 글 뒤에 금실을 붙인다. 진행 폭은 제목 폭 그대로라 바닐라가 제목을 가운데에 맞추고, 금실은 제목 가운데 밑에 온다.
    펜: 제목 끝 W → W/2 - D/2 (금실 시작) → 금실 진행 A → 다시 W.
    """
    s1 = spaces.get(-(width + orn_vis) / 2.0)
    s2 = spaces.get(width / 2.0 + orn_vis / 2.0 - orn_adv)
    return title + s1 + orn_char + s2


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ttf(name, size, shift_y, oversample):
    return {"type": "ttf", "file": f"souls:gothic/{name}.ttf", "size": size, "oversample": oversample,
            "shift": [0.0, shift_y]}


def build(pack, st, metrics, orn):
    """
    metrics: {"body": [Metrics...], "title": [...], "title_pua": [...]} (fonts.Metrics), orn: {"char", "vis", "adv", "provider"}.
    돌려주는 값: 플러그인 사본에 넘길 layout (값 글자 폭, 빈칸 글자).
    """
    spaces = Spaces(st.PUA_SPACE)
    body = Measure(metrics["body"])
    title_pua = Measure(metrics["title_pua"])
    title = Measure(metrics["title"])
    la_map = {v: k for k, v in title_latin(st).items()}
    kr_map = {v: k for k, v in title_hangul(st).items()}

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
            s = to_pua(langs[lang])
            if key in DIVIDED:
                s = with_divider(s, title_pua.width(s), orn["char"], orn["vis"], orn["adv"], spaces)
            data[key] = s
        write_json(path, dict(sorted(data.items())))

        spath = os.path.join(souls_lang, lang + ".json")
        sdata = read_json(spath)
        i = 0 if lang == "ko_kr" else 1
        widths = {k: body.width(v[i]) for k, v in STAT_LABELS.items()}
        col = max(widths.values()) + st.LABEL_GAP
        col = round(col * 4) / 4.0
        for k, v in STAT_LABELS.items():
            sdata["souls.gothic.stat." + k] = v[i] + spaces.get(col - widths[k])
        name = sdata["souls.bonfire.test-name"]
        sdata["souls.bonfire.test-name"] = with_divider(name, title.width(name), orn["char"], orn["vis"], orn["adv"],
                                                        spaces)
        write_json(spath, dict(sorted(sdata.items())))
        report[lang] = {"label_col": col}

    # 플러그인이 값을 오른쪽에 맞출 빈칸 (2 의 거듭제곱과 1/4 단위)
    pads = {}
    for adv in (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64):
        pads[spaces.get(adv)] = adv
    gap = spaces.get(st.COL_GAP)
    values = {ch: body.width(ch) for ch in VALUE_CHARS}

    # 글꼴 정의
    fdir = os.path.join(pack, "assets", "minecraft", "font")
    base = read_json(os.path.join(fdir, "default.json"))
    providers = [ttf(n, s, y, st.OVERSAMPLE) for n, s, y in st.BODY]
    providers += [ttf(n, s, y, st.OVERSAMPLE) for n, s, y in st.TITLE]
    providers += [orn["provider"], spaces.provider()]
    write_json(os.path.join(fdir, "default.json"), {"providers": providers + base["providers"]})
    sdir = os.path.join(pack, "assets", "souls", "font")
    write_json(os.path.join(sdir, "gothic_title.json"), {"providers": [ttf(n, s, y, st.OVERSAMPLE) for n, s, y in st.TITLE]
                                                         + [orn["provider"], spaces.provider(),
                                                            {"type": "reference", "id": "minecraft:default"}]})
    write_json(os.path.join(sdir, "gothic_lore.json"), {"providers": [ttf(n, s, y, st.OVERSAMPLE) for n, s, y in st.LORE]
                                                        + [{"type": "reference", "id": "minecraft:default"}]})
    report["spaces"] = len(spaces.by_adv)
    layout = {"values": values, "pads": pads, "gap": gap, "value_col": st.VALUE_COL}
    return layout, report
