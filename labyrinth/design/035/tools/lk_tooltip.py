#!/usr/bin/env python3
"""TASK B — 겉모습 툴팁 줄 만들기 + 폭 검사 (ItemTooltip.width 와 같은 근사: 한글 9 · ASCII 6 · 공백 4 · 그 밖 8 px, 한 줄 330px)."""
import re

import lk_core as K

MAX_PX = 330
COLORS = {"heavy": "#b8c4d6", "light": "#c9a46a", "cloth": "#b99cff"}
NAMES = {"defense_pct": "방어", "damage_reduction": "받는 피해", "move_speed": "이동 속도", "evasion": "회피",
         "cooldown_pct": "재사용 대기", "crit_chance": "치명", "attack_speed": "공격 속도", "skill_damage": "스킬 피해",
         "mana_regen_pct": "MP 재생", "hp_pct": "최대 HP"}
# 좋은 쪽 부호: 받는 피해·재사용 대기는 줄어드는 것이 좋다
GOOD_WHEN_NEG = {"damage_reduction", "cooldown_pct"}
PCTP = {"evasion", "crit_chance"}          # %p 로 쓰는 키 (더하는 확률)


def width(mm):
    w = 0
    for ch in re.sub(r"<[^>]+>", "", mm):
        if ch == " ":
            w += 4
        elif 0xAC00 <= ord(ch) <= 0xD7A3:
            w += 9
        elif ord(ch) < 128:
            w += 6
        else:
            w += 8
    return w


def fmt(v):
    a = abs(v) * 100
    s = f"{a:.2f}".rstrip("0").rstrip(".")
    return s


def cell(k, v):
    shown = -v if k == "damage_reduction" else v      # 받는 피해 감소 +0.5% → '받는 피해 −0.5%'
    sign = "+" if shown > 0 else "−"
    unit = "%p" if k in PCTP else "%"
    return f"{NAMES[k]} {sign}{fmt(shown)}{unit}"


def is_good(k, v):
    if k == "damage_reduction":
        return v > 0
    if k in GOOD_WHEN_NEG:
        return v < 0
    return v > 0


def piece_lines(look):
    """부위 툴팁 두 줄: '판금 ▲ …' / '     ▼ …'."""
    lk = K.LOOKS[look]
    pro = [cell(k, v) for k, v in lk["piece"].items() if is_good(k, v)]
    con = [cell(k, v) for k, v in lk["piece"].items() if not is_good(k, v)]
    c = COLORS[look]
    a = f"<{c}>{lk['name']}</{c}> <#9be89b>▲ " + " · ".join(pro)
    b = f"<{c}>    </{c}><#ff9a8a>▼ " + " · ".join(con)
    return [a, b]


FULL_TEXT = {
    "heavy": lambda f: f"밀려남 −{fmt(f['knockback_resist'])}% · 기절·속박·빙결 −{fmt(f['cc_resist'])}% (보스 제외)",
    "light": lambda f: f"웅크리기 두 번 → {('%g' % f['distance'])}칸 구르며 피함 ({('%g' % f['cooldown'])}초)",
    "cloth": lambda f: f"받는 피해 {fmt(f['absorb'])}%를 MP로 받음 (MP 1 = 피해 {('%g' % f['damage_per_mp'])})",
}


def full_line(look, active=None):
    lk = K.LOOKS[look]
    f = lk["full"]
    c = COLORS[look] if active is not False else "#6a6a7a"
    return f"<{c}>{lk['name']} 4부위 · {f['name']}</{c}><gray>: {FULL_TEXT[look](f)}"


def all_lines():
    out = {}
    for look in ("heavy", "light", "cloth"):
        ls = piece_lines(look) + [full_line(look)]
        out[look] = [(l, width(l)) for l in ls]
    return out


if __name__ == "__main__":
    for look, ls in all_lines().items():
        for l, w in ls:
            print(f"{w:4d}px {'OK ' if w <= MAX_PX else 'OVER'} {re.sub(r'<[^>]+>', '', l)}")
