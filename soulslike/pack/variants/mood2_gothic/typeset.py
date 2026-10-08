"""
mood2_gothic 의 글꼴 정의: fonts.py 로 그린 그림 글자를 공급자로 엮는다.

  minecraft:default   [빈칸][본문 로마자][본문 한글][제목 로마자 개인 영역][제목 한글 개인 영역][장식][자리 맞춤 빈칸]
                      그 뒤에 기본 팩의 공급자 (YOU DIED, 사망 띠) 와 바닐라 (팩이 쌓는다). 바닐라 화면·채팅·설명 칸·개수까지
                      우리 명조·가라몽으로 그려진다. 개인 영역은 언어 파일이 창 제목 (일시 정지, 제작, 상자 …) 을 제목 글꼴로
                      쓰는 길 (언어 문자열은 글꼴을 고를 수 없다).
  souls:gothic_title  [빈칸][제목 로마자][제목 한글][장식][빈칸] → minecraft:default. 플러그인 사본이 아이템 이름·보스 이름·
                      휴식 창 제목에 입힌다.

Measure 는 클라이언트와 같은 진행 폭으로 글 폭을 잰다 (제목 밑 금실 가운데 맞춤, 수치 칸 열 맞춤).
"""
import json
import os

import fonts
from fonts import K, Face, Role


def strip_fmt(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "§" and i + 1 < len(s):
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


class MappedRole(Role):
    """개인 영역 글자 → 원 글자를 그린다 (창 제목용)."""

    def add_mapped(self, mapping):
        for pua, src in mapping.items():
            if pua in self.glyphs:
                continue
            if src == " ":
                continue
            before = dict(self.glyphs)
            self.add(src)
            if src in self.glyphs and src not in before:
                self.glyphs[pua] = self.glyphs.pop(src)
            elif src in self.glyphs:
                self.glyphs[pua] = dict(self.glyphs[src])


class Spaces:
    """자리 맞춤 빈칸: 같은 폭이면 한 글자를 다시 쓴다 (정수 GUI 픽셀)."""

    def __init__(self, start):
        self.next = start
        self.by_adv = {}

    def get(self, adv):
        adv = int(round(adv))
        if adv not in self.by_adv:
            self.by_adv[adv] = chr(self.next)
            self.next += 1
        return self.by_adv[adv]

    def advances(self):
        return {ch: adv for adv, ch in self.by_adv.items()}


class Measure:
    """글 진행 폭 (GUI 픽셀): roles 차례대로 처음 가진 것의 폭. extra = {글자: 폭} (빈칸·장식)."""

    def __init__(self, roles, extra=None):
        self.roles = roles
        self.extra = extra or {}

    def width(self, text):
        w = 0
        for ch in strip_fmt(text):
            if ch in self.extra:
                w += self.extra[ch]
                continue
            for r in self.roles:
                a = r.advance(ch)
                if a is not None:
                    w += a
                    break
            else:
                raise KeyError(f"글꼴에 없는 글자 {ch!r} ({text})")
        return w


def make_roles(st, title_chars_kr, title_chars_la=None):
    """본문·제목 역할을 만들고 글자를 그린다."""
    body_la = Role("body_la", [Face(st.BODY_LA[0], st.BODY_LA[1], st.BODY_LA[2])], space=st.BODY_SPACE)
    body_la.add(fonts.latin_set())
    body_kr = Role("body_kr", [Face(st.BODY_KR[0], st.BODY_KR[1], st.BODY_KR[2])], space=st.BODY_SPACE)
    body_kr.add([ch for ch in fonts.hangul_set() if ch not in body_la.glyphs])
    title_la = MappedRole("title_la", [Face(st.TITLE_LA[0], st.TITLE_LA[1], st.TITLE_LA[2])], track=st.TITLE_TRACK,
                          space=st.TITLE_SPACE)
    title_la.add(title_chars_la or [chr(c) for c in range(0x21, 0x7F)] + list("·’‘“”—–…"))
    title_kr = MappedRole("title_kr", [Face(st.TITLE_KR[0], st.TITLE_KR[1], st.TITLE_KR[2])], space=st.TITLE_SPACE)
    title_kr.add([ch for ch in title_chars_kr if ch not in title_la.glyphs])
    return {"body_la": body_la, "body_kr": body_kr, "title_la": title_la, "title_kr": title_kr}


def pua_roles(st, title_kr_syllables):
    """창 제목용 개인 영역 역할 둘 (기본 글꼴 안): 제목 로마자 (ASCII 순서), 제목 한글 (음절 차례)."""
    la_map = {chr(st.PUA_TITLE_LA + i): chr(0x20 + i) for i in range(0x7F - 0x20)}
    kr_map = {chr(st.PUA_TITLE_KR + i): ch for i, ch in enumerate(title_kr_syllables)}
    la = MappedRole("pua_la", [Face(st.TITLE_LA[0], st.TITLE_LA[1], st.TITLE_LA[2])], track=st.TITLE_TRACK,
                    space=st.TITLE_SPACE)
    la.add_mapped(la_map)
    kr = MappedRole("pua_kr", [Face(st.TITLE_KR[0], st.TITLE_KR[1], st.TITLE_KR[2])], space=st.TITLE_SPACE)
    kr.add_mapped(kr_map)
    return la, kr, la_map, kr_map


def write_atlas(pack, role, fname):
    img, prov, advs, over = fonts.atlas(role)
    path = os.path.join(pack, "assets", "souls", "textures", "font", fname + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    prov["file"] = f"souls:font/{fname}.png"
    if over:
        print(f"  {fname}: 진행 폭이 바뀐 글자 {len(over)}개 {over[:6]}")
    return prov, os.path.getsize(path)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=1)
        f.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
