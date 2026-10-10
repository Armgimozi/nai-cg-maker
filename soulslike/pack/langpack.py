#!/usr/bin/env python3
"""
게임 안 문구를 리소스팩 언어 파일로 옮긴다 (DESIGN.md 10.3, 10.9, 12.5). gen_pack.py 가 부르고, tools/langcheck.py 와
tools/textlint.py 도 같은 읽개를 쓴다 (플러그인의 kr.souls.Lang 과 같은 규칙).

  원본  plugin/src/main/resources/lang/ko.yml (한국어, 원본)  lang/en.yml (영어, 따로 쓴 것). 열쇠가 같다.
  결과  assets/souls/lang/ko_kr.json, en_us.json      열쇠 앞에 souls. , 꼴 태그를 뗀 글, 자리는 %1$s
        assets/minecraft/lang/<언어>.json               vanilla.* 묶음 (사망 화면 단추 같은 바닐라 열쇠). ko_kr 은 한국어,
                                                        나머지 모든 언어는 영어 (아래)

YAML 한 줄의 꼴: "<#b3a37f>소울 <souls> · 레벨 <level>"
  - 맨 앞의 꼴 태그 (<#rrggbb>, 이름 색 <gray>, 꾸밈 <bold> <!italic>, 글꼴 <font:souls:title>) 가 그 열쇠의 꼴이다. 플러그인이
    번역 글에 입힌다. 글꼴 태그는 제목 글꼴 (무기·보스·화톳불 이름, fonts.py) 을 고른다.
    언어 파일에는 꼴을 뗀 글만 들어간다. 꼴은 열쇠마다 하나이고, 두 언어의 꼴이 같아야 한다.
  - 그 뒤의 <이름> 은 자리다. 번역 인수의 차례는 한국어 원본에 처음 나오는 차례다 (영어는 차례를 바꿔도 된다: %2$s).
  - 목록은 줄마다 열쇠.1, 열쇠.2 ... (아이템 설명). 두 언어의 줄 수가 같아야 한다.
  - % 는 %% 로 바꾼다 (마인크래프트 번역 형식).
바닐라 열쇠 (vanilla.*): 클라이언트는 en_us 를 읽고 고른 언어를 그 위에 읽는다. 고른 언어의 바닐라 파일이 팩의 en_us 를
  덮으므로 (fr_fr 이면 "Réapparaître"), ko_kr 이 아닌 바닐라의 모든 언어에 영어 글을 쓴다. 꼴은 이름 색·꾸밈만 되고
  (언어 파일은 Component 가 아니라 글이라 § 코드로 바꾼다), 16진 색은 쓸 수 없다.
"""
import os
import re

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LANG_DIR = os.path.join(ROOT, "plugin", "src", "main", "resources", "lang")
LANGS = ("ko", "en")
PACK_CODE = {"ko": "ko_kr", "en": "en_us"}
PREFIX = "souls."
VANILLA = "vanilla."

TAG = re.compile(r"<([^<>]+)>")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
FONT = re.compile(r"^font:[a-z0-9_.-]+:[a-z0-9_./-]+$")   # Java Lang.FONT 와 같다
SLOT = re.compile(r"^[a-z][a-z0-9_-]*$")
LEGACY = {
    "black": "0", "dark_blue": "1", "dark_green": "2", "dark_aqua": "3", "dark_red": "4", "dark_purple": "5",
    "gold": "6", "gray": "7", "dark_gray": "8", "blue": "9", "green": "a",
    "aqua": "b", "red": "c", "light_purple": "d", "yellow": "e", "white": "f",
}
DECORATIONS = {"obfuscated": "k", "bold": "l", "strikethrough": "m", "underlined": "n", "italic": "o"}
# MiniMessage 의 태그 이름 (줄임말과 다른 철자 포함). 꼴로 읽지 않는 것 (<i>, <br>, <reset>, <grey> …) 이 맨 앞이나 글 가운데에
# 있으면 자리로 읽혀 클라이언트에 빈칸이 나오므로 자리 이름으로 쓰지 못한다
RESERVED = {
    "color", "colour", "c", "grey", "dark_grey", "b", "i", "em", "u", "underline", "st", "obf", "reset", "pre",
    "newline", "br", "click", "hover", "key", "lang", "tr", "translate", "lang_or", "tr_or", "translate_or",
    "insert", "insertion", "font", "gradient", "rainbow", "transition", "selector", "sel", "score", "nbt", "data",
    "pride", "shadow", "sprite", "head", "keybind",
} | set(LEGACY) | set(DECORATIONS)


def path_of(lang):
    return os.path.join(LANG_DIR, lang + ".yml")


class Table(dict):
    """{점으로 이은 열쇠: 글 또는 [글...]}. bad 는 글이 아닌 값 [(열쇠, 무엇이 틀렸나)] (problems 가 오류로 낸다)."""
    def __init__(self, *a):
        super().__init__(*a)
        self.bad = []


def flatten(node, key="", out=None):
    """YAML 트리 → Table. 따옴표 없는 Yes·No·off·12 는 YAML 이 참거짓·수로 읽으므로 (Java 는 "true") 글이 아니면 bad 에 둔다."""
    out = Table() if out is None else out

    def text(v, where):
        if not isinstance(v, str):
            out.bad.append((where, f"글이 아니다 ({type(v).__name__} {v!r}). 따옴표로 묶는다"))
            return "" if v is None else str(v)
        return v
    if isinstance(node, dict):
        for k, v in node.items():
            flatten(v, f"{key}.{k}" if key else str(k), out)
    elif isinstance(node, list):
        out[key] = [text(v, f"{key}[{i}]") for i, v in enumerate(node)]
    else:
        out[key] = text(node, key)
    return out


def load(lang, path=None):
    with open(path or path_of(lang), encoding="utf-8") as f:
        return flatten(yaml.safe_load(f) or {})


def lines(table):
    """목록을 줄 열쇠로 편다: {열쇠.1: 글, ...}. 차례는 YAML 그대로."""
    out = {}
    for k, v in table.items():
        if isinstance(v, list):
            for i, line in enumerate(v, 1):
                out[f"{k}.{i}"] = line
        else:
            out[k] = v
    return out


def is_style_tag(t):
    neg = t.startswith("!")
    n = t[1:] if neg else t
    if HEX.match(n) or n in LEGACY or FONT.match(n):
        return not neg
    return n in DECORATIONS


def split_style(s):
    """'<#b3a37f>소울 <n>' → ('<#b3a37f>', '소울 <n>'). Java Lang.splitStyle 과 같다."""
    at = 0
    while at < len(s) and s[at] == "<":
        end = s.find(">", at)
        if end < 0 or not is_style_tag(s[at + 1:end]):
            break
        at = end + 1
    return s[:at], s[at:]


def slots(text):
    out = []
    for m in TAG.finditer(text):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def mc_format(text, order):
    """자리 → %n$s (n 은 한국어 원본의 차례), % → %%. Java Lang.mcFormat 과 같다."""
    out, at = [], 0
    for m in TAG.finditer(text):
        out.append(text[at:m.start()].replace("%", "%%"))
        name = m.group(1)
        out.append(f"%{order.index(name) + 1}$s" if name in order else m.group(0).replace("%", "%%"))
        at = m.end()
    out.append(text[at:].replace("%", "%%"))
    return "".join(out)


def legacy_prefix(tags):
    """바닐라 열쇠의 꼴 → § 코드. 16진 색처럼 바꿀 수 없으면 None."""
    out = []
    for t in TAG.findall(tags):
        n = t.lstrip("!")
        if t.startswith("!"):
            continue          # 바닐라 글은 꾸밈 없이 시작한다
        if n in LEGACY:
            out.append("§" + LEGACY[n])
        elif n in DECORATIONS:
            out.append("§" + DECORATIONS[n])
        else:
            return None
    return "".join(out)


def problems(tables):
    """
    두 언어의 짝이 맞는지. tables = {"ko": load("ko"), "en": load("en")}. 돌려주는 값: [(열쇠, 무엇이 틀렸나)].
    열쇠·줄 수·꼴·자리가 같아야 하고, 꼴 태그는 맨 앞에만, 자리 이름은 소문자 이름 (MiniMessage 태그 이름은 안 된다),
    바닐라 열쇠는 이름 색만, 값은 모두 글.
    """
    out = []
    ko, en = tables["ko"], tables["en"]
    for lang in LANGS:
        for k, why in getattr(tables[lang], "bad", []):
            out.append((k, f"{lang}.yml: {why}"))
    for k in sorted(set(ko) - set(en)):
        out.append((k, "en.yml 에 없다"))
    for k in sorted(set(en) - set(ko)):
        out.append((k, "ko.yml 에 없다"))
    for k in sorted(set(ko) & set(en)):
        a, b = ko[k], en[k]
        if isinstance(a, list) != isinstance(b, list):
            out.append((k, "한쪽만 목록이다"))
            continue
        if isinstance(a, list) and len(a) != len(b):
            out.append((k, f"줄 수가 다르다 (ko {len(a)}, en {len(b)})"))
            continue
    la, lb = lines(ko), lines(en)
    for k in sorted(set(la) & set(lb)):
        (ta, xa), (tb, xb) = split_style(la[k]), split_style(lb[k])
        if ta != tb:
            out.append((k, f"꼴이 다르다 (ko {ta or '없음'}, en {tb or '없음'})"))
        sa, sb = slots(xa), slots(xb)
        if sorted(sa) != sorted(sb):
            out.append((k, f"자리가 다르다 (ko {sa}, en {sb})"))
        for lang, x in (("ko", xa), ("en", xb)):
            for name in slots(x):
                if is_style_tag(name):
                    out.append((k, f"{lang}: 글 가운데의 꼴 태그 <{name}> (꼴은 맨 앞에 하나. 섞어야 하면 열쇠를 나눈다)"))
                elif name.lstrip("!") in RESERVED:
                    out.append((k, f"{lang}: <{name}> 은 MiniMessage 태그 이름이라 자리로 쓸 수 없다 (꼴은 맨 앞의 색·"
                                   f"<bold> 같은 것만, 줄바꿈은 목록으로)"))
                elif not SLOT.match(name):
                    out.append((k, f"{lang}: 자리 이름 <{name}> 은 소문자·숫자·_·- 만"))
        if k.startswith(VANILLA):
            if legacy_prefix(ta) is None:
                out.append((k, f"바닐라 열쇠는 이름 색·꾸밈만 쓸 수 있다: {ta}"))
            if sa:
                out.append((k, "바닐라 열쇠에 자리를 쓰지 않는다 (바닐라 인수 차례를 따로 맞춰야 한다)"))
    return out


def build(tables, vanilla_langs, typeset=None):
    """
    팩 언어 파일 → {팩 안 경로: {열쇠: 글}}. vanilla_langs 는 바닐라의 모든 언어 코드 (gen_pack.LANGS).
    바닐라 열쇠는 ko_kr 에 한국어, 나머지에 영어. 다른 바닐라 열쇠(사망 화면 제목처럼 그림 글자)는 gen_pack 이 더한다.
    typeset (typeset.Typeset, 팩 글꼴을 읽은 것) 을 주면 창 제목을 제목 글자로, 제목 밑 금실, 수치 이름의 열 맞춤 빈칸을
    짠다 (gen_pack 은 막 만든 팩으로, langcheck 는 검사하는 팩으로 같은 셈을 한다).
    """
    ko = lines(tables["ko"])
    files = {}
    for lang in LANGS:
        table = lines(tables[lang])
        data = {}
        for k, v in table.items():
            if k.startswith(VANILLA):
                continue
            order = slots(split_style(ko.get(k, v))[1])
            data[PREFIX + k] = mc_format(split_style(v)[1], order)
        files[f"assets/souls/lang/{PACK_CODE[lang]}.json"] = dict(sorted(data.items()))
    vanilla = {}
    for lang in LANGS:
        vanilla[lang] = {}
        for k, v in lines(tables[lang]).items():
            if k.startswith(VANILLA):
                tags, text = split_style(v)
                vanilla[lang][k[len(VANILLA):]] = (legacy_prefix(tags) or "") + text.replace("%", "%%")
    for code in vanilla_langs:
        files[f"assets/minecraft/lang/{code}.json"] = dict(vanilla["ko" if code == "ko_kr" else "en"])
    if typeset is not None:
        typeset.apply(files, ko)
    return files


def load_all():
    return {lang: load(lang) for lang in LANGS}
