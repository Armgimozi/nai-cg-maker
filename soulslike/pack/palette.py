"""
식은 가마 팔레트 (DESIGN.md 10.1). 모든 그림과 글자색은 여기서만 고른다.

  계열마다 어두움 → 밝음 순서로 3~4색. 이름은 계열 + 번호: "rust0" (가장 어두운 녹슨 철) ... "rust3".
  c("blood2") 는 (r, g, b, 255). 플러그인 hud/Glyphs 의 글자색 상수도 같은 값을 쓴다 (java_hex).

빛 허용
  불씨 계열의 밝은 색(채도가 SAT_MAX 를 넘는다)과 발광 알파(250~252)는 GLOW 에 든 그림에만 쓴다.
  artlint 가 그림 경로를 보고 판단한다 (is_glow_path).

채도
  여기서 채도는 (가장 큰 채널 − 가장 작은 채널) / 255, 즉 HSV 의 S×V 다.
  아주 어두운 핏빛은 S 만 보면 높지만 눈에는 탁한 색이라, 밝기까지 곱한 값으로 잰다.
  이렇게 재면 표의 색 가운데 SAT_MAX 를 넘는 것은 불씨의 밝은 세 색과 생피의 밝은 두 색뿐이다.

생피
  사망 화면 제목 "YOU DIED" 를 새빨갛게 띄우려고 (사용자 결정 3) 10.1 표에 한 계열을 더했다 (한 곳 전용).
  그 제목 그림(VIVID)에만 쓴다. 다른 그림에 나오면 artlint 오류 (restricted).
"""
import colorsys

FAMILIES = {
    "rust":   ["#2b2622", "#4a3f36", "#6e5a48", "#8c7259"],   # 녹슨 철: 막대 테, 쇠 장비, 표식
    "bronze": ["#3a2e1e", "#5c4628", "#7d6034", "#9e7c44"],   # 그을린 청동: 자세 막대, 장식, "쓰러뜨렸다"
    "parch":  ["#6b5f4a", "#8f8164", "#b3a37f", "#d1c3a0"],   # 바랜 양피지: 이름, 설명, 소울 숫자, 창 글
    "blood":  ["#3d0f0c", "#5e1611", "#7d1f17", "#a8301f"],   # 마른 핏빛: 체력, 쳐낼 수 없는 예고
    "ash":    ["#1c1b1a", "#3a3836", "#5c5955", "#858079"],   # 재: 바탕, 수치, 회색 알림
    "moss":   ["#2e3322", "#48502f", "#646d3e"],              # 이끼: 스태미나 채움, 독
    "bone":   ["#8a8270", "#b0a68e", "#d6cbb0", "#e8dcc0"],   # 뼈: 해골, 마지막 4틱 섬광
    "ember":  ["#7a2e10", "#b04a17", "#d9772a", "#f0b060"],   # 불씨 (빛 허용): 화톳불, 소울, 쳐낼 수 있는 예고
    # 생피: 사망 화면 제목 "YOU DIED" 전용 (사용자 결정 3, 10.1 표의 "한 곳 전용" 줄). 마른 핏빛보다 붉고 진하다.
    # 다른 그림에는 쓰지 않는다. artlint 가 경로로 막는다 (RESTRICTED).
    "gore":   ["#3b0605", "#6e0b08", "#a3110c", "#cc2418"],
}
KO = {"rust": "녹슨 철", "bronze": "그을린 청동", "parch": "바랜 양피지", "blood": "마른 핏빛",
      "ash": "재", "moss": "이끼", "bone": "뼈", "ember": "불씨", "gore": "생피 (사망 제목 전용)"}

SAT_MAX = 0.55            # 이보다 채도가 높으면 빛 허용 그림에만
BLUE_HUE = (200, 300)     # 파랑~보라 (도)
BLUE_VALUE_MAX = 0.5      # 그 색상에서 이보다 밝으면 안 된다
GLOW_ALPHA = (250, 251, 252)   # 발광 픽셀 표시 (셰이더용, M0 에는 셰이더가 없다)

# 빛을 허용하는 그림 (경로의 조각 이름). 10.7: 화톳불 불꽃과 검의 잔불, 혈흔의 소울, 소울 표식,
# 적·보스 기술 예고 (장판, 반짝임, 두르크의 달아오른 핵), 쳐내기 섬광
GLOW = ("bonfire", "bloodstain", "soul_mark", "telegraph", "warn", "glint", "durk_core", "parry_flash")

# 쓰는 곳이 정해진 계열: 계열 → 그 색을 쓸 수 있는 그림 (경로 조각). 여기 든 그림은 채도 제한도 받지 않는다.
VIVID = ("you_died",)
RESTRICTED = {"gore": VIVID}


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


C = {f"{fam}{i}": hexc(h) for fam, hs in FAMILIES.items() for i, h in enumerate(hs)}
BY_RGB = {v[:3]: k for k, v in C.items()}


def c(name, a=255):
    """팔레트 이름 → RGBA. 없는 이름이면 바로 멈춘다 (팔레트 밖 색을 쓰지 못하게)."""
    if name not in C:
        raise KeyError(f"팔레트에 없는 색: {name}")
    return C[name][:3] + (a,)


def family(name):
    return name.rstrip("0123456789")


def name_of(rgb):
    """RGB(A) → 팔레트 이름. 팔레트 밖이면 None."""
    return BY_RGB.get(tuple(rgb[:3]))


def java_hex(name):
    """플러그인 글자색 상수용 0xRRGGBB 문자열."""
    r, g, b, _ = c(name)
    return f"0x{r:02x}{g:02x}{b:02x}"


# ─────────────────────────── 색 재기 ───────────────────────────

def chroma(rgb):
    return (max(rgb[:3]) - min(rgb[:3])) / 255.0


def value(rgb):
    return max(rgb[:3]) / 255.0


def hue(rgb):
    h, _, _ = colorsys.rgb_to_hsv(*(v / 255.0 for v in rgb[:3]))
    return h * 360.0


def luma(rgb):
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0


def too_saturated(rgb):
    return chroma(rgb) > SAT_MAX


def blue_glow(rgb):
    """파랑~보라 색상이면서 밝은 색 (빛 번짐처럼 보인다)."""
    return chroma(rgb) > 0.04 and BLUE_HUE[0] <= hue(rgb) <= BLUE_HUE[1] and value(rgb) > BLUE_VALUE_MAX


def is_glow_path(path):
    p = path.replace("\\", "/").lower()
    return any(g in p for g in GLOW)


def is_vivid_path(path):
    p = path.replace("\\", "/").lower()
    return any(g in p for g in VIVID)


def family_allowed(name, path):
    """RESTRICTED 계열의 색이면 정해진 그림에서만 참."""
    allow = RESTRICTED.get(family(name))
    if allow is None:
        return True
    p = path.replace("\\", "/").lower()
    return any(g in p for g in allow)


def nearest(rgb, families=None):
    """가장 가까운 팔레트 이름 (families 를 주면 그 계열 안에서만)."""
    best, bd = None, 1e18
    for k, v in C.items():
        if families and family(k) not in families:
            continue
        d = sum((a - b) ** 2 for a, b in zip(rgb[:3], v[:3]))
        if d < bd:
            best, bd = k, d
    return best


def _by_luma(fam, rgb):
    """그 계열에서 밝기가 가장 가까운 색."""
    names = [f"{fam}{i}" for i in range(len(FAMILIES[fam]))]
    return min(names, key=lambda n: abs(luma(C[n]) - luma(rgb)))


# ─────────────────────────── 옛 그림 옮기기 ───────────────────────────

def remap(rgb):
    """
    skyblock 그림을 다시 쓸 때 옛 색을 이 팔레트로 옮긴다 (10.7).
      청록·남색 → 바랜 은(재)과 그을린 쇠(녹슨 철), 보라·자홍 → 재와 수의 천(양피지),
      하얀 노랑 용암 → 탁한 불씨, 나머지는 색상이 가까운 계열에서 밝기로 고른다.
    돌려준 색으로 artlint 를 지날 때까지 손본다. 알파는 그대로 둔다.
    """
    a = rgb[3] if len(rgb) > 3 else 255
    h, ch, v = hue(rgb), chroma(rgb), value(rgb)
    if ch < 0.10:
        fam = "bone" if v > 0.78 else "ash"
    elif 160 <= h < 260:
        fam = "ash" if v > 0.45 else "rust"
    elif 260 <= h < 340:
        fam = "parch" if v > 0.6 else "ash"
    elif 30 <= h < 70 and v > 0.85:
        return c("ember2" if ch > 0.3 else "ember3", a)
    elif h >= 340 or h < 20:
        fam = "blood"
    elif h < 45:
        fam = "ember" if ch > 0.4 and v > 0.5 else "bronze"
    elif h < 70:
        fam = "bronze" if ch > 0.25 else "parch"
    else:
        fam = "moss"
    return c(_by_luma(fam, rgb), a)


if __name__ == "__main__":
    for fam, hs in FAMILIES.items():
        row = []
        for i, h in enumerate(hs):
            rgb = hexc(h)
            tag = ""
            if fam in RESTRICTED:
                tag = " (" + ", ".join(RESTRICTED[fam]) + " 전용)"
            elif too_saturated(rgb):
                tag = " (빛 허용)"
            row.append(f"{fam}{i} {h} 채도 {chroma(rgb):.2f}{tag}")
        print(f"{KO[fam]}: " + ", ".join(row))
