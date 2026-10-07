"""
구르기 대역 (DESIGN.md 3.3 "보이는 모습"). gen_pack.py 가 icons 다음에 부른다.

구르는 동안 플러그인(combat/Tumble)은 진짜 몸을 감추고(투명) 그 자리에 대역을 띄운다. 대역은 플레이어 모형과 같은 비례
(머리 8, 몸통 8×12×4, 팔·다리 4×12×4 를 무릎·팔꿈치·허리에서 둘로 나눈 상자) 를 22.5° 마디로 굽힌 아이템 모형이고,
자세가 셋이다. 플러그인이 틱에 맞춰 아이템 모형을 바꾸고 (같은 틱에 변환도) 웅크린 자세를 옆 축으로 돌린다.

  souls:roll_dive   뛰어드는 자세 (0~1틱, 변환 각 START_ANGLE): 무릎을 굽혀 몸을 앞으로 눕히고 두 팔을 앞아래로 뻗어 머리를
                    그 사이로 넣는다
  souls:roll_tuck   웅크린 공 (2~7틱): 등을 말고 무릎을 가슴에, 정수리를 아래로 박아 얼굴은 무릎 쪽 (안쪽), 두 팔꿈치가 머리 옆
                    앞에서 정강이를 감싼다. 옆모습이 가장 둥근 각을 골랐다 (TUCK)
  souls:roll_rise   일어서는 자세 (8~10틱): 깊이 쪼그린 채 몸통을 숙이고 머리를 들어 앞을 본다 (키 1.32 블록)

  souls:roll_head_<자세>  그 사람의 머리 (바닐라 player_head 특수 모형 + 이 팩의 바탕 모형 souls:item/roll_head_<자세>).
                    fixed 자세 (ItemDisplay 의 FIXED) 의 회전·이동으로 머리를 그 자세의 목에 둔다. 자세가 아이템 공간 안에서
                    먼저 걸리므로 대역 전체가 돌 때 머리도 같은 중심으로 돈다 (변환의 이동은 직선 보간이라, 이동으로 옮기면
                    회전 마디 사이에서 머리가 중심 쪽으로 꺾인다)
  souls:roll_helm_<자세>  투구를 썼을 때 머리에 씌우는 껍데기 (머리와 같은 fixed 자세, 색 하나로 물든다)

색 (물들이기)
  몸의 재료는 뼈 계열 네 단 (팔레트) 으로만 찍은 밝은 그림이고, 면마다 tintindex 가 있다:
  0 몸통, 1 소매 (윗팔), 2 손 (아랫팔), 3 바지, 4 신. 아이템 정의의 tints 가 custom_model_data 의 colors[0..4] 를 곱한다.
  플러그인이 그 사람 스킨에서 고른 색 (갑옷을 입었으면 갑옷 색) 을 보낸다. 없으면 정의의 기본색 (팔레트).
  스킨이 없는 오프라인 접속은 바닐라 기본 스킨 18 개 가운데 UUID 로 고른 것을 쓰므로, 그 18 개의 색 표를 클라이언트
  jar 에서 미리 뽑아 플러그인 자원 roll_skins.yml 로 둔다 (skin_table; jar 가 없으면 있던 표를 그대로 둔다).

아이템 공간의 앞은 -Z (북쪽) 다. ItemDisplay 는 아이템을 그리기 전에 Y 축으로 180° 돌려 그리므로, 플러그인 변환 공간에서는
+Z 가 앞이 된다 [확인 (클라): dist/screenshots/roll/].
바닐라 해골 모형 (player_head 특수 모형) 은 아이템 공간 (4..12, 0..8, 4..12) 에 그려지고 얼굴이 +Z (남쪽) 를 본다
(SkullSpecialRenderer: (0.5, 0, 0.5) 로 옮기고 (-1,-1,1) 로 뒤집은 뒤 머리를 Y 로 180° 돌린다. 모형 공간의 얼굴은 -Z.
합치면 X 축 180° 회전이라 얼굴은 +Z, 거울상 아님) [확인 (클라): /soulstest tumble]. 그래서 머리 자세는 먼저 Y 로 180° 돌려
얼굴을 앞 (-Z) 으로 보내고 숙인다.

손에 든 것 감추기 (wrap_item_definitions)
  구르는 동안 플러그인은 손에 든 아이템의 사본에 custom_model_data 깃발 0 을 켜서 그 사람 화면과 보는 사람에게만 보낸다
  (sendEquipmentChange). 이 팩의 souls 아이템 정의는 모두 그 깃발이 켜지면 손·머리 자세 (3인칭, 1인칭) 에서 아무것도 그리지
  않는다. 단축 슬롯(gui)·땅·액자는 그대로라 슬롯 그림이 사라지지 않고, 아이템 종류와 이름이 같아 바닐라가 이름을 다시
  띄우지도 않는다 (공기를 보내면 둘 다 일어난다 [확인 (클라)]). 갑옷 칸은 공기를 보낸다 (그 칸은 이름을 띄우지 않는다).
  이 깃발 0 은 구르기 전용이다 (아이템이 다른 일로 custom_model_data 를 쓰면 깃발 1 부터 쓴다).

회전 자세 감추기 (riptide)
  combat.roll.visual: spin 은 바닐라 급류 회전 (startRiptideAttack) 이다. 몸에 감기는 흰 소용돌이
  (minecraft:textures/entity/trident_riptide.png, 클라이언트 SpinAttackEffectLayer) 를 투명한 그림으로 덮어 몸만 돈다.
  이 게임에는 삼지창이 없어 다른 데서 보이지 않는다.
"""
import io
import json
import math
import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw

from palette import c

NS = "souls"
POSES = ("dive", "tuck", "rise")
HIDE_FLAG = 0                      # custom_model_data 깃발 번호 (플러그인 Tumble.HIDE_FLAG 와 같다)
# 3인칭 손·머리 (투명한 몸에 떠 보인다) 와 1인칭 손 (구르는 동안 무기를 거두었다가 끝나면 다시 든다: 바닐라의 바꿔 들기
# 몸짓이 구르기 시작에 내리고 끝에 올린다. 1인칭을 그대로 두면 사본이 바뀔 때마다 두 번 내렸다 올렸다)
HIDDEN_CONTEXTS = ["thirdperson_righthand", "thirdperson_lefthand", "firstperson_righthand", "firstperson_lefthand", "head"]

# 대역 크기: 플레이어 모형과 같은 픽셀 크기 (바닐라는 플레이어를 0.9375 배로 그린다). 플러그인 tumble.scale 과 같다
SCALE = 0.9375
# 공 반지름 (픽셀, 회전 중심에서 웅크린 몸 바깥까지). 플러그인 tumble.pivot = PIVOT_PX × SCALE / 16 블록
PIVOT_PX = 6.8
# 뛰어드는 자세가 걸리는 각 (플러그인 tumble.start-angle). 그 자세는 이 각만큼 앞으로 돌린 변환에서 바로 서 보이게 만든다
START_ANGLE = 45.0

# 일어서기 자세의 머리 가운데가 회전 중심에서 앞으로 몇 픽셀인가
RISE_HEAD_F = 0.0
# 뛰어들기 자세의 엉덩이가 회전 중심에서 몇 픽셀 뒤인가 (발은 그 아래, 머리와 팔은 앞으로 뻗는다)
DIVE_HIP_F = -4.0

# 물들이는 칸: (이름, tintindex, 기본색 (팔레트, 스킨 색이 없을 때))
TINTS = [("torso", 0, "rust2"), ("sleeve", 1, "rust2"), ("hand", 2, "bone0"), ("legs", 3, "rust1"), ("boots", 4, "rust0")]
HELM_DEFAULT = "ash3"


# ─────────────────────────── 재료: 손으로 찍은 16×16 칸 (뼈 계열만, 물들일 바탕) ───────────────────────────
# 물들이기는 곱하기라 바탕은 밝아야 스킨 색이 산다. 뼈 네 단 (0.54 / 0.69 / 0.84 / 0.91) 으로 주름과 닳은 곳을 찍는다.
# 1픽셀 줄무늬는 크게 그려지면 띠로 보여 (예전 망토) 주름은 2~3픽셀 넓이로, 고르지 않게.

INK = {"a": "bone3", "b": "bone2", "c": "bone1", "d": "bone0"}


def _mat(rows):
    if len(rows) != 16 or any(len(r) != 16 for r in rows):
        raise ValueError("16×16 이어야 한다")
    img = Image.new("RGBA", (16, 16))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[x, y] = c(INK[ch])
    return img


# 몸통: 거친 천. 비스듬한 주름 두셋 (넓게), 아래로 처진 자락, 닳아 밝은 어깨
CLOTH = _mat([
    "aaaabbbbbbbaaaab",
    "aabbbbbccbbbbabb",
    "abbbbbccbbbbbbbb",
    "bbbbbccbbbbbbbcb",
    "bbbbccbbbbbbbccb",
    "bbbccbbbbbbbccbb",
    "bbbcbbbbbbbccbbb",
    "bbbbbbbbbbccbbbb",
    "bbbbbbbbbbcbbbbb",
    "cbbbbbbbbbbbbbbc",
    "ccbbbbbbbbbbbbcc",
    "bccbbbbcbbbbbccb",
    "bbccbbccbbbbccbb",
    "bbbcccdcbbbccbbb",
    "cbbbccccbbccbbbc",
    "ccbbbbcccccbbbcc",
])

# 소매: 굵은 가로 접힘 (팔꿈치 쪽) 과 세로 박음질
SLEEVE = _mat([
    "aaaaabbbbaaaabbb",
    "abbbbbbbbbbbbbba",
    "bbbbbbcbbbbbbbbb",
    "bbbbbbcbbbbbbbbb",
    "ccbbbbbbbbbbbccb",
    "bcccbbbbbbbcccbb",
    "bbbccccbbcccbbbb",
    "bbbbbbccccbbbbbb",
    "bbbbbbbbcbbbbbbb",
    "bbbbbbbbcbbbbbbb",
    "bbbccbbbbbbbbbbb",
    "bbcccccbbbbbccbb",
    "bbbbbcccccccccbb",
    "bbbbbbbbbbbbbbbb",
    "cbbbbbbbbbbbbbbc",
    "ccbbbbbbbbbbbccc",
])

# 손 (아랫팔): 맨살이거나 장갑. 거의 고르고 마디 자국 몇 개
HAND = _mat([
    "aaaaaaaabaaaaaaa",
    "aaaaaaaaaaaaaaba",
    "abaaaaaaaaaaaaaa",
    "aaaaaabaaaaaaaaa",
    "aaaaaaaaaaaaaaaa",
    "aaaaaaaaaaabaaaa",
    "aabaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaa",
    "aaaaabaaaaaaaaab",
    "aaaaaaaaabaaaaaa",
    "baaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaabaa",
    "aaabbaaaaaaaaaaa",
    "aaaaaaaaabbaaaaa",
    "abaaaaaaaaaaaaaa",
    "bbaaaaaaaaaaaabb",
])

# 바지: 무릎 쪽 넓은 주름과 솔기 (세로 2픽셀)
TROUSERS = _mat([
    "abbbbbbcbbbbbbba",
    "bbbbbbbcbbbbbbbb",
    "bbbbbbbbbbbbbbbb",
    "bbbccbbbbbbccbbb",
    "bbbbcccbbbcccbbb",
    "bbbbbbccbccbbbbb",
    "bbbbbbbcbbbbbbbb",
    "cbbbbbbbbbbbbbbc",
    "bbbbbbbcbbbbbbbb",
    "bbbbbbbcbbbbbbbb",
    "bbccbbbbbbbbbbbb",
    "bbbcccbbbbbbccbb",
    "bbbbbccbbbbccbbb",
    "bbbbbbbbbbbbbbbb",
    "cbbbbbbcbbbbbbbc",
    "ccbbbbbcbbbbbbcc",
])

# 신 (가죽): 발목 주름과 긁힌 코, 밑은 어둡다
BOOT = _mat([
    "bbbbbbbbbbbbbbbb",
    "bccbbbbbbbbbbccb",
    "bbcccbbbbbbcccbb",
    "bbbbbbbbbbbbbbbb",
    "bbbbbbbbbbbbbbbb",
    "bbbbbbbbbbbbabbb",
    "bbbbabbbbbbbbbbb",
    "bbbbbbbbbbbbbbbb",
    "cbbbbbbbbbbbbbbc",
    "bbbbbbbbbbabbbbb",
    "bbbbbbbbbbbbbbbb",
    "bbbccbbbbbbbbbbb",
    "bbbbccbbbbbbccbb",
    "cbbbbbbbbbbbbbbc",
    "ccccccccccccccccc"[:16],
    "cdcccccdccccccdc",
])

# 신 밑창
SOLE = _mat([
    "dddddddddddddddd",
    "ddcdddddddddcddd",
    "dddddddddddddddd",
    "ddddddcddddddddd",
    "dcdddddddddddddd",
    "dddddddddcdddddd",
    "dddddddddddddddc",
    "ddddcddddddddddd",
    "dddddddddddcdddd",
    "dddddddddddddddd",
    "dcdddddddddddddd",
    "ddddddddcddddddd",
    "dddddddddddddcdd",
    "dddcdddddddddddd",
    "dddddddddddddddd",
    "ddddddcddddddddd",
])

# 투구 껍데기: 판을 이은 줄과 징 몇 개, 이마 띠
HELM = _mat([
    "aaaabbbbbbbbaaaa",
    "abbbbbbcbbbbbbba",
    "bbbbbbbcbbbbbbbb",
    "bbabbbbcbbbbabbb",
    "bbbbbbbcbbbbbbbb",
    "bbbbbbbcbbbbbbbb",
    "bbbbbbbbbbbbbbbb",
    "ccbbbbbbbbbbbbcc",
    "bbbbbbbcbbbbbbbb",
    "bbbbbbbcbbbbbbbb",
    "babbbbbcbbbbbbab",
    "bbbbbbbcbbbbbbbb",
    "bbbbbbbbbbbbbbbb",
    "cccccccccccccccc",
    "bcbbbabbbbabbbcb",
    "cccccccccccccccc",
])

TEXTURES = {"cloth": CLOTH, "sleeve": SLEEVE, "hand": HAND, "trousers": TROUSERS, "boot": BOOT, "sole": SOLE,
            "helm": HELM}
TEX_ID = {k: f"{NS}:item/roll_{k}" for k in TEXTURES}


# ─────────────────────────── 상자와 자세 ───────────────────────────
# 설계 좌표 (픽셀): 원점 = 회전 중심 (공 가운데), y 위, f 앞 (아이템 공간 -Z), x 옆. 상자의 길이 축은 pitch 각 (위(+y)에서
# 앞(+f)으로 잰 각, 22.5° 마디) 을 따라 joint 에서 뻗는다. 아이템 모형 요소는 한 축으로 -45~45° 만 돌 수 있어
# 90° 를 넘는 몫은 상자의 y·f 길이를 바꿔 (눕혀) 채운다.

class Box:
    def __init__(self, name, tex, tint, w, length, t, joint, pitch, x=0.0, sole=None):
        if abs(pitch / 22.5 - round(pitch / 22.5)) > 1e-6:
            raise ValueError(f"{name}: 각은 22.5° 마디여야 한다 ({pitch})")
        self.name, self.tex, self.tint = name, tex, tint
        self.w, self.length, self.t = w, length, t
        self.pitch = pitch
        self.x = x
        self.sole = sole     # 이 면 (설계 방향 "end": 길이 축의 끝) 을 밑창 그림으로
        a = math.radians(pitch)
        self.dir = np.array([math.cos(a), math.sin(a)])      # (y, f)
        self.joint = np.array(joint, float)
        self.center = self.joint + self.dir * (length / 2)

    @property
    def end(self):
        return self.joint + self.dir * self.length

    def element(self):
        """아이템 모형 요소 하나 (JSON). 아이템 공간: x = 8 + x, y = 8 + y, z = 8 - f."""
        p = ((self.pitch + 90) % 180) - 90               # 상자는 앞뒤가 같다: -90..90
        if p == -90:
            p = 90
        if abs(p) <= 45:
            ext_y, ext_f, rest = self.length, self.t, p
        else:
            ext_y, ext_f = self.t, self.length
            rest = p - 90 if p > 0 else p + 90
        cy, cf = self.center
        cx, cyi, cz = 8 + self.x, 8 + cy, 8 - cf
        fr = [cx - self.w / 2, cyi - ext_y / 2, cz - ext_f / 2]
        to = [cx + self.w / 2, cyi + ext_y / 2, cz + ext_f / 2]
        faces = {}
        sizes = {"north": (self.w, ext_y), "south": (self.w, ext_y), "east": (ext_f, ext_y), "west": (ext_f, ext_y),
                 "up": (self.w, ext_f), "down": (self.w, ext_f)}
        # 같은 그림이 여러 상자에 같은 자리로 찍히지 않게 상자 이름으로 uv 를 비낀다
        seed = sum(ord(ch) * (i + 1) for i, ch in enumerate(self.name))
        for k, (fname, (du, dv)) in enumerate(sizes.items()):
            u0 = (seed * 5 + k * 7) % max(1, int(16 - du) + 1)
            v0 = (seed * 3 + k * 11) % max(1, int(16 - dv) + 1)
            tex = self.tex
            if self.sole is not None and fname == self._end_face(rest):
                tex = self.sole
            faces[fname] = {"uv": [_r(u0), _r(v0), _r(u0 + du), _r(v0 + dv)], "texture": "#" + tex, "tintindex": self.tint}
        el = {"from": [_r(v) for v in fr], "to": [_r(v) for v in to], "faces": faces}
        if rest:
            # 마인크래프트 요소 회전 (X 축 +각: +Y → +Z). 설계의 +각은 +y → +f (= -Z) 라 부호가 반대다
            el["rotation"] = {"origin": [_r(cx), _r(cyi), _r(cz)], "axis": "x", "angle": -rest}
        return el

    def _end_face(self, rest):
        """길이 축의 끝 (joint 반대쪽) 이 닿는 면 이름."""
        p = ((self.pitch % 360) + 360) % 360
        # 길이 축 방향이 위/아래/앞/뒤 가운데 어디에 가장 가까운가 (돌리기 전 상자 기준)
        dirs = {"up": 0, "north": 90, "down": 180, "south": 270}
        return min(dirs, key=lambda k: min(abs(p - dirs[k] - rest), 360 - abs(p - dirs[k] - rest)))


def _r(v):
    return round(float(v), 3)


class Pose:
    """한 자세: 상자들과 머리 (가운데, 숙인 각). head_pitch 는 정수리 방향 (위에서 앞으로 잰 각)."""

    def __init__(self, name, boxes, head_center, head_pitch, head_scale=1.0, frame=0.0):
        self.name, self.boxes = name, boxes
        self.head_center = np.array(head_center, float)
        self.head_pitch = head_pitch
        self.head_scale = head_scale
        self.frame = frame     # 이 자세를 그리는 변환 각 (뛰어들기는 START_ANGLE). 설계는 바로 선 모습으로 하고 여기서 되돌린다


def _rot2(v, deg):
    """(y, f) 를 앞으로 deg 돌린다 (위 → 앞)."""
    a = math.radians(deg)
    y, f = v
    return np.array([y * math.cos(a) - f * math.sin(a), y * math.sin(a) + f * math.cos(a)])


def _limbs(spec):
    """[(이름, 그림, tint, w, 길이, t, 각, x, 이어 붙을 상자 이름 또는 (y, f), 밑창)] → Box 목록 (앞 상자의 끝에 잇는다)."""
    out = {}
    for name, tex, tint, w, length, t, pitch, x, at, sole in spec:
        joint = out[at].end if isinstance(at, str) else at
        out[name] = Box(name, tex, tint, w, length, t, joint, pitch, x, sole)
    return list(out.values())


T_TORSO, T_SLEEVE, T_HAND, T_LEGS, T_BOOTS = 0, 1, 2, 3, 4


def _body(hip, belly, chest, thigh, shin, foot, uarm, farm, shoulder_back=1.0, shoulder_down=1.0):
    """
    플레이어 비례의 몸. hip = 엉덩이 관절 (y, f). 각은 모두 위(+y)에서 앞(+f)으로.
    belly·chest: 몸통 아래·위 (8×6×4). thigh·shin: 다리 (4×6×4, 4×3×4) 다음 신 (4×4×4, 밑창). 왼·오른 다리 각을 따로
    주려면 (왼, 오른) 짝. uarm·farm: 윗팔 (소매) 과 아랫팔 (손). 어깨는 가슴 끝에서 shoulder_down 만큼 아래 (가슴 축을 따라),
    shoulder_back 만큼 등 쪽.
    """
    def pair(v):
        return v if isinstance(v, tuple) else (v, v)

    spec = [
        ("belly", "cloth", T_TORSO, 8.0, 6.0, 4.0, belly, 0.0, hip, None),
        ("chest", "cloth", T_TORSO, 8.1, 6.0, 4.1, chest, 0.0, "belly", None),
    ]
    th, sh, ft = pair(thigh), pair(shin), pair(foot)
    for i, sx in enumerate((-1, 1)):
        side = "lr"[i]
        spec += [
            (f"thigh_{side}", "trousers", T_LEGS, 3.9, 6.0, 3.9, th[i], sx * 2.0, hip, None),
            (f"shin_{side}", "trousers", T_LEGS, 3.8, 3.0, 3.8, sh[i], sx * 2.0, f"thigh_{side}", None),
            (f"foot_{side}", "boot", T_BOOTS, 4.1, 4.0, 4.1, ft[i], sx * 2.0, f"shin_{side}", "sole"),
        ]
    boxes = _limbs(spec)
    chest_box = next(b for b in boxes if b.name == "chest")
    back = np.array([math.sin(math.radians(chest)), -math.cos(math.radians(chest))])
    sj = chest_box.end - chest_box.dir * shoulder_down + back * shoulder_back
    ua, fa = pair(uarm), pair(farm)
    arm = []
    for i, sx in enumerate((-1, 1)):
        side = "lr"[i]
        arm += [
            (f"uarm_{side}", "sleeve", T_SLEEVE, 4.0, 6.0, 4.0, ua[i], sx * 6.0, tuple(sj), None),
            (f"farm_{side}", "hand", T_HAND, 3.9, 6.0, 3.9, fa[i], sx * 6.0, f"uarm_{side}", None),
        ]
    boxes += _limbs(arm)
    return boxes, chest_box


def _head_on(chest_box, head_pitch, lift=0.5, scale=1.0):
    """목 (가슴 끝) 에 머리를 단다: 머리 가운데 = 목 + 정수리 방향 × (4 + lift) (머리 크기에 맞춘다)."""
    a = math.radians(head_pitch)
    crown = np.array([math.cos(a), math.sin(a)])
    return chest_box.end + crown * (4.0 * scale + lift)


def _outline(pose):
    """자세의 옆모습 꼭짓점들 (y, f): 상자 넷씩과 머리 넷."""
    pts = [p for b in pose.boxes for p in _box_corners_2d(b)]
    a = math.radians(pose.head_pitch)
    up, fw = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    h = 4.0 * pose.head_scale
    pts += [pose.head_center + up * su * h + fw * sf * h for su in (-1, 1) for sf in (-1, 1)]
    return np.array(pts)


def _shift(pose, d):
    d = np.array(d, float)
    boxes = [Box(b.name, b.tex, b.tint, b.w, b.length, b.t, b.joint + d, b.pitch, b.x, b.sole) for b in pose.boxes]
    return Pose(pose.name, boxes, pose.head_center + d, pose.head_pitch, pose.head_scale, pose.frame)


def ball_center(pose):
    """옆모습을 감싸는 가장 작은 원의 가운데와 반지름 (0.25 픽셀 격자로 찾는다)."""
    pts = _outline(pose)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    best = None
    for y in np.arange(lo[0], hi[0], 0.25):
        for f in np.arange(lo[1], hi[1], 0.25):
            r = np.sqrt(((pts - (y, f)) ** 2).sum(axis=1)).max()
            if best is None or r < best[0]:
                best = (r, np.array([y, f]))
    return best[1], best[0]


# 웅크린 공의 각 (배, 가슴, 허벅지, 정강이, 신, 머리 정수리, 윗팔, 아랫팔). 옆모습이 가장 둥근 것 (도는 동안 땅에서 회전 중심까지
# 거리가 가장 덜 바뀌는 것) 을 22.5° 마디 가운데서 골랐다: 등을 말고 (배 -22.5, 가슴 67.5), 무릎을 가슴에, 정수리를 아래로
# 박고 (얼굴은 무릎 쪽), 두 팔꿈치를 머리 옆 앞으로 내밀어 정강이를 감싼다 (옆에서 보면 앞 테가 머리가 아니라 팔)
TUCK = (-22.5, 67.5, 45.0, 202.5, 225.0, 157.5, 135.0, 202.5)


def pose_tuck():
    """
    웅크린 공 (구르기 2~7틱, 변환 각이 그대로 돈 각). 쪼그려 앉아 등을 말고 턱을 가슴에 붙인 모습: 옆에서 보면 바깥 테가
    정수리·뒤통수 (앞) → 등 (위) → 엉덩이 (뒤) → 신 (아래). 얼굴은 무릎을 내려다보고 (안쪽), 두 팔이 정강이를 감싼다.
    앞으로 돌면 뒤통수·목덜미 → 등 → 엉덩이 → 발 차례로 땅에 닿는다. 회전 중심은 옆모습을 감싸는 원의 가운데.
    """
    boxes, chest = _body(hip=(0.0, 0.0), belly=TUCK[0], chest=TUCK[1],
                         thigh=TUCK[2], shin=TUCK[3], foot=TUCK[4],
                         uarm=TUCK[6], farm=TUCK[7], shoulder_back=0.5, shoulder_down=1.5)
    hp = TUCK[5]
    pose = Pose("tuck", boxes, _head_on(chest, hp, lift=-0.5), hp)
    ctr, _ = ball_center(pose)
    return _shift(pose, -ctr)


def pose_dive():
    """
    뛰어들기 (0틱~첫 마디). 무릎을 굽혀 몸통을 앞으로 눕히고 (배 67.5°, 가슴 90°) 두 팔을 앞아래로 뻗고, 머리는 그 사이로 숙인다
    (정수리가 앞아래). 설계는 땅에 선 모습 (발이 -PIVOT_PX) 이고, START_ANGLE 로 돈 변환에서 이렇게 보이게 되돌린다 (_settle).
    """
    boxes, chest = _body(hip=(0.0, DIVE_HIP_F), belly=67.5, chest=90.0,
                         thigh=157.5, shin=202.5, foot=180.0,
                         uarm=157.5, farm=157.5, shoulder_back=0.5, shoulder_down=1.5)
    hp = 135.0
    return Pose("dive", boxes, _head_on(chest, hp, lift=-0.5), hp, frame=START_ANGLE)


def pose_rise():
    """
    일어서기 (rise-at~reveal). 깊이 쪼그린 채 (허벅지 수평) 오른발을 조금 앞에 딛고, 몸통을 숙인 채 (배 45°, 가슴 67.5°) 머리를 들어
    앞을 본다. 두 손은 무릎 앞. 키 약 1.32 블록 (웅크린 공 0.9 블록과 선 몸 1.8 블록 사이). 머리 가운데가 회전 중심 (곧 진짜 몸이 설
    자리) 위 RISE_HEAD_F 에 오게 옮긴다: 진짜 몸이 돌아올 때 머리가 앞뒤로 튀지 않고, 1인칭 눈 (1.62) 아래 5 픽셀 남짓, 바로 밑이라
    앞을 볼 때 화면에 들지 않는다 (더 크게 세웠더니 1인칭 화면 아래에 머리 꼭대기가 걸렸다 [확인 (클라)]).
    """
    boxes, chest = _body(hip=(0.0, 0.0), belly=45.0, chest=67.5,
                         thigh=(90.0, 90.0), shin=(180.0, 202.5), foot=(180.0, 180.0),
                         uarm=(180.0, 157.5), farm=(135.0, 135.0), shoulder_back=0.3, shoulder_down=1.0)
    hp = 22.5
    pose = Pose("rise", boxes, _head_on(chest, hp, lift=0.0), hp)
    return _shift(pose, (0.0, RISE_HEAD_F - pose.head_center[1]))


def poses():
    return {"dive": pose_dive(), "tuck": pose_tuck(), "rise": pose_rise()}


def _ground(pose):
    """자세의 가장 낮은 점 (설계 y, 머리 포함) 을 -PIVOT_PX 에 맞추도록 내릴 몫. 웅크린 공은 돌므로 맞추지 않는다."""
    lo = min(min(_box_corners_2d(b)[:, 0]) for b in pose.boxes)
    return -PIVOT_PX - lo


def _box_corners_2d(b):
    d = b.dir
    n = np.array([-d[1], d[0]])
    pts = []
    for s in (0, 1):
        for k in (-1, 1):
            pts.append(b.joint + d * b.length * s + n * (b.t / 2) * k)
    return np.array(pts)


def _settle(pose):
    """선 자세 (dive, rise): 발을 땅 (-PIVOT_PX) 에 내리고, 그 자세의 변환 각 (frame) 만큼 되돌린다."""
    if pose.name == "tuck":
        return pose
    dy = _ground(pose)
    moved = []
    for b in pose.boxes:
        nb = Box(b.name, b.tex, b.tint, b.w, b.length, b.t, _rot2(b.joint + np.array([dy, 0.0]), -pose.frame),
                 b.pitch - pose.frame, b.x, b.sole)
        moved.append(nb)
    hc = _rot2(pose.head_center + np.array([dy, 0.0]), -pose.frame)
    return Pose(pose.name, moved, hc, pose.head_pitch - pose.frame, pose.head_scale, pose.frame)


# ─────────────────────────── 모형 쓰기 ───────────────────────────

def body_model(pose):
    pose = _settle(pose)
    return {
        "textures": {**{k: TEX_ID[k] for k in TEXTURES if k != "helm"}, "particle": TEX_ID["cloth"]},
        "elements": [b.element() for b in pose.boxes],
    }


def head_display(pose):
    """souls:item/roll_head_<자세> 의 fixed 자세: 해골 (가운데가 아이템 가운데보다 4 아래, 얼굴 +Z) 을 그 자세의 목에."""
    pose = _settle(pose)
    # 아이템 자세 회전 (XYZ 오일러, 벡터에는 Z → Y → X 차례로): Y 180° 로 얼굴을 앞 (-Z) 으로, 그다음 X 로 숙인다.
    # 설계의 숙임 (위 → 앞 = +Y → -Z) 은 마인크래프트 X 축의 음의 각이다
    pitch = -pose.head_pitch
    a = math.radians(pitch)
    s = pose.head_scale
    # 자세의 회전은 아이템 가운데를 축으로, 이동은 회전 뒤에 더한다: 가운데 c = (0,-4,0) → t + R·c
    cy, cz = -4.0 * s * math.cos(a), -4.0 * s * math.sin(a)
    yc, fc = pose.head_center
    tx, ty, tz = 0.0, yc - cy, -fc - cz
    return {"rotation": [round(pitch, 3), 180.0, 0.0], "translation": [round(tx, 3), round(ty, 3), round(tz, 3)],
            "scale": [s, s, s]}


def helm_model(pose):
    """투구 껍데기: 해골 상자 (4..12, 0..8, 4..12) 를 0.6 두껍게 감싸고 얼굴 (+Z) 은 이마 띠만. 머리와 같은 fixed 자세."""
    lo, hi, th = 3.4, 12.6, 0.6
    els = []

    def add(fr, to):
        faces = {}
        for k, fname in enumerate(("north", "south", "east", "west", "up", "down")):
            du = {"north": to[0] - fr[0], "south": to[0] - fr[0], "east": to[2] - fr[2], "west": to[2] - fr[2],
                  "up": to[0] - fr[0], "down": to[0] - fr[0]}[fname]
            dv = {"north": to[1] - fr[1], "south": to[1] - fr[1], "east": to[1] - fr[1], "west": to[1] - fr[1],
                  "up": to[2] - fr[2], "down": to[2] - fr[2]}[fname]
            u0, v0 = (k * 3) % max(1, int(16 - du) + 1), (k * 5) % max(1, int(16 - dv) + 1)
            faces[fname] = {"uv": [_r(u0), _r(v0), _r(u0 + du), _r(v0 + dv)], "texture": "#helm", "tintindex": 0}
        els.append({"from": [_r(v) for v in fr], "to": [_r(v) for v in to], "faces": faces})

    add([lo, 8.0, lo], [hi, 8.0 + th, hi])            # 정수리
    add([lo, 1.5, lo], [hi, 8.0, lo + th])            # 뒤통수 (-Z: 얼굴 반대)
    add([lo, 1.5, lo + th], [lo + th, 8.0, hi])       # 옆
    add([hi - th, 1.5, lo + th], [hi, 8.0, hi])       # 옆
    add([lo + th, 5.6, hi - th], [hi - th, 8.0, hi])  # 이마 띠
    return {"textures": {"helm": TEX_ID["helm"], "particle": TEX_ID["helm"]}, "elements": els,
            "display": {"fixed": head_display(pose)}}


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def build(out):
    assets = os.path.join(out, "assets", NS)
    for k, img in TEXTURES.items():
        p = os.path.join(assets, "textures", "item", f"roll_{k}.png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        img.save(p)
    tints = [{"type": "minecraft:custom_model_data", "index": i, "default": _int(c(col))} for _, i, col in TINTS]
    for name, pose in poses().items():
        _json(os.path.join(assets, "models", "item", f"roll_{name}.json"), body_model(pose))
        _json(os.path.join(assets, "items", f"roll_{name}.json"),
              {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_{name}", "tints": tints}})
        # 머리: 바닐라 player_head 특수 모형 (아이템의 profile 성분으로 스킨을 고른다) + 자세만 바꾼 바탕 모형
        _json(os.path.join(assets, "models", "item", f"roll_head_{name}.json"),
              {"parent": "minecraft:item/template_skull", "display": {"fixed": head_display(pose)}})
        _json(os.path.join(assets, "items", f"roll_head_{name}.json"),
              {"model": {"type": "minecraft:special", "base": f"{NS}:item/roll_head_{name}",
                         "model": {"type": "minecraft:player_head"}}})
        _json(os.path.join(assets, "models", "item", f"roll_helm_{name}.json"), helm_model(pose))
        _json(os.path.join(assets, "items", f"roll_helm_{name}.json"),
              {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_helm_{name}",
                         "tints": [{"type": "minecraft:custom_model_data", "index": 0, "default": _int(c(HELM_DEFAULT))}]}})
    # 급류 회전의 흰 소용돌이를 투명하게 (combat.roll.visual: spin)
    tex = os.path.join(out, "assets", "minecraft", "textures", "entity", "trident_riptide.png")
    os.makedirs(os.path.dirname(tex), exist_ok=True)
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(tex)


def _int(rgba):
    return (rgba[0] << 16) | (rgba[1] << 8) | rgba[2]


OWN = tuple(f"roll_{k}{p}.json" for k in ("", "head_", "helm_") for p in POSES)


def wrap_item_definitions(out):
    """
    assets/souls/items/*.json 을 모두 감싼다: custom_model_data 깃발 HIDE_FLAG 가 켜지면 손·머리 자세 (HIDDEN_CONTEXTS) 에서 비운다.
    대역 모형 (OWN) 은 감싸지 않는다. gen_pack 이 다른 아이템 정의를 다 쓴 뒤에 부른다.
    """
    folder = os.path.join(out, "assets", NS, "items")
    n = 0
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json") or name in OWN:
            continue
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        inner = data["model"]
        data["model"] = {
            "type": "minecraft:condition", "property": "minecraft:custom_model_data", "index": HIDE_FLAG,
            "on_false": inner,
            "on_true": {"type": "minecraft:select", "property": "minecraft:display_context",
                        "cases": [{"when": HIDDEN_CONTEXTS, "model": {"type": "minecraft:empty"}}],
                        "fallback": inner},
        }
        _json(path, data)
        n += 1
    return n


# ─────────────────────────── 스킨 색 표 (기본 스킨 18 개) ───────────────────────────
# 플러그인 combat/SkinTint 와 같은 셈: 칸마다 (덧옷 층 픽셀이 불투명하면 그것이 위) 불투명 픽셀을 채널마다 8 단위로 묶어 가장
# 많은 묶음의 평균, 채도 × 0.8, 너무 어두우면 밝기를 MIN_VALUE 까지 (심층암 바닥과 갈리게).
# 칸은 그 부위를 네 옆면으로 두른 띠 (앞만 보면 노어처럼 앞섶이 열린 겉옷은 속옷 색이 나온다. 3인칭에서 보이는 것은 대개 등과
# 옆이다): 몸통 (16,20)-(40,32), 오른팔 (40,20)-(56,32) (slim 은 (40,20)-(54,32)) 의 위 6줄 = 소매, 아래 6줄 = 손,
# 오른다리 (0,20)-(16,32) 의 위 8줄 = 바지, 아래 4줄 = 신. 덧옷 층은 같은 자리에서 16 아래 (y + 16). 64×32 옛 스킨은 덧옷 없음.

REGIONS = [(16, 20, 40, 32), (40, 20, 56, 26), (40, 26, 56, 32), (0, 20, 16, 28), (0, 28, 16, 32)]
SAT_SCALE = 0.8
MIN_VALUE = 77                     # 밝기 (0~255) 바닥
DEFAULT_SKINS = [f"{m}/{n}" for m in ("slim", "wide") for n in ("alex", "ari", "efe", "kai", "makena", "noor", "steve", "sunny", "zuri")]


def skin_colors(img, slim=False):
    """64×64 (또는 64×32) 스킨 → 다섯 칸의 색 [0xRRGGBB 또는 None, ...] (플러그인 SkinTint.colors 와 같은 셈)."""
    a = np.array(img.convert("RGBA")).astype(int)
    h = a.shape[0]
    out = []
    for x0, y0, x1, y1 in REGIONS:
        if slim and x0 == 40:
            x1 = 54
        px = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                p = a[y, x]
                if h >= 64 and a[y + 16, x][3] >= 128:
                    p = a[y + 16, x]
                if p[3] >= 128:
                    px.append(tuple(int(v) for v in p[:3]))
        out.append(_mode_color(px))
    return _fill(out)


def _mode_color(px):
    if not px:
        return None
    groups = {}
    for p in px:
        groups.setdefault((p[0] >> 3, p[1] >> 3, p[2] >> 3), []).append(p)
    best = max(groups.values(), key=len)        # 같은 수면 먼저 나온 묶음 (dict 는 넣은 차례) — 플러그인도 같다
    r, g, b = (sum(p[i] for p in best) // len(best) for i in range(3))
    return _grade((r << 16) | (g << 8) | b)


def _grade(rgb):
    """채도 × 0.8 (채널마다 가장 밝은 채널 쪽으로 2/10 당긴다, 반올림), 밝기가 MIN_VALUE 보다 낮으면 끌어올린다 (정수 셈,
    플러그인 SkinTint.grade 와 같은 값)."""
    r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    mx = max(r, g, b)
    r, g, b = (v + ((mx - v) * 2 + 5) // 10 for v in (r, g, b))
    if mx < MIN_VALUE:
        if mx == 0:
            r = g = b = MIN_VALUE
        else:
            r, g, b = ((v * MIN_VALUE + mx // 2) // mx for v in (r, g, b))
    return (r << 16) | (g << 8) | b


def _fill(cols):
    """빈 칸 (투명) 은 가장 가까운 칸 색 (앞 칸 먼저). 모두 비면 None."""
    if all(v is None for v in cols):
        return None
    out = list(cols)
    for k, v in enumerate(cols):
        if v is not None:
            continue
        for d in range(1, len(cols)):
            if k - d >= 0 and cols[k - d] is not None:
                out[k] = cols[k - d]
                break
            if k + d < len(cols) and cols[k + d] is not None:
                out[k] = cols[k + d]
                break
    return out


def skin_table(jar, path):
    """클라이언트 jar 의 기본 스킨 18 개 → 플러그인 자원 (YAML). jar 가 없으면 아무것도 하지 않는다 (있던 표를 쓴다)."""
    if not jar or not os.path.exists(jar):
        return False
    lines = ["# 바닐라 기본 스킨 18 개의 구르기 대역 색 (pack/roll_figure.py skin_table 이 클라이언트 jar 에서 뽑는다. 손대지 않는다).",
             "# 차례는 클라이언트 DefaultPlayerSkin 표 (UUID.hashCode() 를 18 로 나눈 나머지, floorMod). 색은 몸통, 윗팔, 손, 바지, 신",
             "skins:"]
    with zipfile.ZipFile(jar) as z:
        for name in DEFAULT_SKINS:
            img = Image.open(io.BytesIO(z.read(f"assets/minecraft/textures/entity/player/{name}.png")))
            cols = skin_colors(img, slim=name.startswith("slim/"))
            lines.append(f"  - [{', '.join(repr('%06x' % v) for v in cols)}]   # {name}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return True


# ─────────────────────────── 미리보기 ───────────────────────────
# 요소의 면을 텍셀마다 작은 사각형으로 나눠 먼 것부터 그리는 정사영. 머리는 8×8×8 상자에 스킨 (없으면 팔레트 색 얼굴).
# 아이템 공간 → (자세) → ItemDisplay 의 Y 180° → 플러그인 변환 (구르는 쪽 Y, 옆 축 X 로 θ). 바닥은 회전 중심 PIVOT_PX 아래.

_FACE_N = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


def _rx(deg):
    t = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])


def _ry(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])


def _rz(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])


def _face_grid(fr, to, fname):
    """면 위 텍셀 격자: (원점, u 축, v 축, 너비, 높이) — 텍스처 u 는 오른쪽, v 는 아래 (밖에서 볼 때)."""
    x0, y0, z0 = fr
    x1, y1, z1 = to
    if fname == "north":
        return np.array([x1, y1, z0]), np.array([-1, 0, 0]), np.array([0, -1, 0]), x1 - x0, y1 - y0
    if fname == "south":
        return np.array([x0, y1, z1]), np.array([1, 0, 0]), np.array([0, -1, 0]), x1 - x0, y1 - y0
    if fname == "east":
        return np.array([x1, y1, z1]), np.array([0, 0, -1]), np.array([0, -1, 0]), z1 - z0, y1 - y0
    if fname == "west":
        return np.array([x0, y1, z0]), np.array([0, 0, 1]), np.array([0, -1, 0]), z1 - z0, y1 - y0
    if fname == "up":
        return np.array([x0, y1, z0]), np.array([1, 0, 0]), np.array([0, 0, 1]), x1 - x0, z1 - z0
    return np.array([x0, y0, z1]), np.array([1, 0, 0]), np.array([0, 0, -1]), x1 - x0, z1 - z0


def _quads(origin, uax, vax, w, h, sample, step=1.0):
    """면을 step 픽셀 칸으로 나눈 사각형들 (아이템 공간 픽셀) 과 색. sample(u, v) → RGBA."""
    out = []
    nu, nv = max(1, int(math.ceil(w / step - 1e-6))), max(1, int(math.ceil(h / step - 1e-6)))
    for i in range(nu):
        for j in range(nv):
            u0, u1 = i * w / nu, (i + 1) * w / nu
            v0, v1 = j * h / nv, (j + 1) * h / nv
            q = [origin + uax * u0 + vax * v0, origin + uax * u1 + vax * v0, origin + uax * u1 + vax * v1,
                 origin + uax * u0 + vax * v1]
            out.append((q, sample((u0 + u1) / 2, (v0 + v1) / 2)))
    return out


def model_faces(model, tint_colors, textures=None):
    """아이템 모형 JSON (elements) → [(꼭짓점 4개 (아이템 픽셀, 가운데 원점), 법선, RGBA)]."""
    textures = textures or {}
    out = []
    for el in model["elements"]:
        fr, to = np.array(el["from"], float), np.array(el["to"], float)
        rot = el.get("rotation")
        R, org = np.eye(3), np.zeros(3)
        if rot:
            R = {"x": _rx, "y": _ry, "z": _rz}[rot["axis"]](rot["angle"])
            org = np.array(rot["origin"], float)
        for fname, face in el["faces"].items():
            key = face["texture"].lstrip("#")
            tex = textures.get(key) or TEXTURES[key]
            arr = np.array(tex.convert("RGBA"))
            u0, v0, u1, v1 = face["uv"]
            tint = tint_colors[face.get("tintindex", -1)] if face.get("tintindex", -1) >= 0 else None
            origin, uax, vax, w, h = _face_grid(fr, to, fname)

            def sample(u, v, arr=arr, u0=u0, v0=v0, u1=u1, v1=v1, w=w, h=h, tint=tint):
                tu = int(min(15, max(0, math.floor(u0 + (u1 - u0) * u / max(w, 1e-6)))))
                tv = int(min(15, max(0, math.floor(v0 + (v1 - v0) * v / max(h, 1e-6)))))
                p = arr[tv, tu].astype(float)
                if tint is not None:
                    p[:3] = p[:3] * np.array(tint) / 255.0
                return p
            n = R @ np.array(_FACE_N[fname], float)
            for q, col in _quads(origin, uax, vax, w, h, sample):
                qq = [R @ (p - org) + org - 8.0 for p in q]
                out.append((qq, n, col))
    return out


def _skin_faces(skin):
    """머리 여섯 면 그림 (8×8). 해골 모형 면 이름 (모형 공간): 얼굴 north, 뒤통수 south, 오른쪽 west, 왼쪽 east."""
    if skin is None:
        face = Image.new("RGBA", (8, 8), c("bone1"))
        for x in (1, 2, 5, 6):
            face.putpixel((x, 4), c("ash0"))
        for x in range(8):
            for y in (0, 1):
                face.putpixel((x, y), c("rust1"))
        hair = Image.new("RGBA", (8, 8), c("rust1"))
        return {"north": face, "south": hair, "east": hair, "west": hair, "up": hair, "down": Image.new("RGBA", (8, 8), c("bone1"))}
    reg = {"up": (8, 0), "down": (16, 0), "west": (0, 8), "north": (8, 8), "east": (16, 8), "south": (24, 8)}
    return {f: skin.crop((u, v, u + 8, v + 8)).convert("RGBA") for f, (u, v) in reg.items()}


def head_faces(display, skin):
    """해골 상자 → 아이템 공간 면들. 모형 공간 (y 아래, 얼굴 -Z) 의 머리를 X 로 180° 돌린 것이 아이템 공간 (얼굴 +Z, 위 +Y)."""
    tex = _skin_faces(skin)
    rx, ry, rz = display["rotation"]
    R = _rx(rx) @ _ry(ry) @ _rz(rz)
    s = display["scale"][0]
    t = np.array(display["translation"], float)
    out = []
    # 모형 공간 상자 (-4..4, -8..0, -4..4) 의 면 (모형 공간 법선과 텍스처 방향) → 아이템 공간: (x, y, z) → (x, -y, -z), + (0,0,0)
    # 아이템 공간에서 해골은 (4..12, 0..8, 4..12) = 가운데 원점으로 (-4..4, -8..0, -4..4)
    fr, to = np.array([-4.0, -8.0, -4.0]), np.array([4.0, 0.0, 4.0])
    # 아이템 공간 면 이름 → 모형 공간 면 (X 180°: 위↔아래, 앞(+Z)↔모형 north)
    names = {"south": "north", "north": "south", "east": "east", "west": "west", "up": "up", "down": "down"}
    for fname in _FACE_N:
        img = np.array(tex[names[fname]])
        origin, uax, vax, w, h = _face_grid(fr, to, fname)

        # 스킨의 면 그림은 밖에서 볼 때 그대로다 (얼굴은 왼쪽 가장자리가 그 사람의 오른쪽, 옆얼굴은 얼굴 쪽 가장자리가
        # 얼굴 그림과 맞닿는다): 요소 면의 uv 방향과 같아 뒤집지 않는다
        def sample(u, v, img=img):
            uu = int(min(7, max(0, math.floor(u))))
            vv = int(min(7, max(0, math.floor(v))))
            return img[vv, uu].astype(float)
        n = R @ np.array(_FACE_N[fname], float)
        for q, col in _quads(origin, uax, vax, w, h, sample):
            out.append(([R @ (p * s) + t for p in q], n, col))
    return out


# 보는 쪽: 화면 오른쪽, 위, 깊이 (멀수록 큼) 를 플러그인 공간 축으로
_VIEWS = {
    "back": (np.array([-1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1]), 18),    # 3인칭 등 뒤 (F5 한 번)
    "side": (np.array([0, 0, 1]), np.array([0, 1, 0]), np.array([1, 0, 0]), 0),      # 왼쪽에서 (구르는 쪽이 화면 오른쪽)
    "front": (np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, -1]), 12),   # 앞에서 (F5 두 번)
}


def render_view(faces, angle, view, size=200, k=6.0, tilt_axis=0.0):
    """faces 는 아이템 공간 (가운데 원점, 픽셀). angle: 구르기 변환 각. 바닥은 회전 중심에서 PIVOT_PX 아래."""
    right, up, depth, tilt = _VIEWS[view]
    # 플러그인 변환: Rz(t)·Rx(θ)·Rz(-t) (어깨 쪽으로 기운 축) 다음 ItemDisplay 의 Y 180°
    spin = _rz(tilt_axis) @ _rx(angle) @ _rz(-tilt_axis) @ _ry(180)
    t = math.radians(tilt)
    up2 = up * math.cos(t) - depth * math.sin(t)
    depth2 = depth * math.cos(t) + up * math.sin(t)
    light = np.array([0.3, 1.0, -0.4])
    light = light / np.linalg.norm(light)
    img = Image.new("RGBA", (size, size), (44, 41, 46, 255))
    d = ImageDraw.Draw(img)
    cy = size * 0.55
    gy = cy + (PIVOT_PX * (up2 @ np.array([0, 1, 0]))) * k
    d.rectangle((0, gy, size, size), fill=(34, 31, 36, 255))
    items = []
    for quad, n, col in faces:
        if col[3] < 128:
            continue
        nw = spin @ n
        if nw @ depth2 >= 0:
            continue
        pts = [spin @ q for q in quad]
        sc = [(size / 2 + (p @ right) * k, cy - (p @ up2) * k) for p in pts]
        z = sum(p @ depth2 for p in pts) / 4
        b = 0.55 + 0.45 * max(0.0, float(nw @ light))
        items.append((z, sc, tuple(int(v * b) for v in col[:3]) + (255,)))
    items.sort(key=lambda x: -x[0])
    for _, sc, col in items:
        d.polygon(sc, fill=col)
    return img


def figure_faces(pose, skin=None, colors=None, helm=None):
    cols = colors or [c(col)[:3] for _, _, col in TINTS]
    cols = [((v >> 16) & 255, (v >> 8) & 255, v & 255) if isinstance(v, int) else tuple(v[:3]) for v in cols]
    faces = model_faces(body_model(pose), cols)
    disp = head_display(pose)
    faces += head_faces(disp, skin)
    if helm is not None:
        hm = helm_model(pose)
        hcol = [((helm >> 16) & 255, (helm >> 8) & 255, helm & 255)]
        R = _rx(disp["rotation"][0]) @ _ry(disp["rotation"][1])
        tt = np.array(disp["translation"], float)
        for q, n, col in model_faces(hm, hcol):
            faces.append(([R @ (p * disp["scale"][0]) + tt for p in q], R @ n, col))
    return faces


def preview(path, skin=None, colors=None, tilt_axis=0.0):
    """
    웅크린 공을 뒤 (F5), 옆, 앞에서 45° 마다, 그리고 뛰어들기·일어서기를 옆과 뒤에서. 바닥은 회전 중심에서 PIVOT_PX 아래.
    skin 이 없으면 팔레트 기본색과 그림 얼굴.
    """
    from mc3d import contact_sheet
    ps = poses()
    tuck = figure_faces(ps["tuck"], skin, colors)
    imgs, labels = [], []
    for view in ("back", "side", "front"):
        for deg in range(0, 360, 45):
            imgs.append(render_view(tuck, deg, view, tilt_axis=tilt_axis))
            labels.append(f"tuck {view} {deg}")
    for name, ang in (("dive", START_ANGLE), ("rise", 0.0)):
        f = figure_faces(ps[name], skin, colors)
        for view in ("side", "back", "front"):
            imgs.append(render_view(f, ang, view))
            labels.append(f"{name} {view}")
    imgs.append(render_view(figure_faces(ps["tuck"], skin, colors, helm=0x858079), 0, "side"))
    labels.append("tuck side helm")
    imgs.append(render_view(figure_faces(ps["tuck"], skin, colors, helm=0x858079), 0, "front"))
    labels.append("tuck front helm")
    sheet = contact_sheet(imgs, labels, cols=8, cell=200)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)
    return path


def client_jar():
    """바닐라 클라이언트 jar (기본 스킨). SOULS_CLIENT_JAR, 없으면 점검 틀이 받아 둔 곳 (tools/client). 없으면 None."""
    for p in (os.environ.get("SOULS_CLIENT_JAR"), os.path.expanduser("~/.cache/souls-client/versions/1.21.11.jar")):
        if p and os.path.exists(p):
            return p
    return None


def preview_default(path, who="wide/noor"):
    """gen_pack 의 미리보기: 클라이언트 jar 가 있으면 그 기본 스킨 (점검 틀의 Tester 는 노어) 으로, 없으면 팔레트 기본색으로."""
    jar = client_jar()
    skin = _skin_from_jar(jar, who) if jar else None
    return preview(path, skin, skin_colors(skin, slim=who.startswith("slim/")) if skin else None)


def _skin_from_jar(jar, name="wide/steve"):
    with zipfile.ZipFile(jar) as z:
        return Image.open(io.BytesIO(z.read(f"assets/minecraft/textures/entity/player/{name}.png"))).convert("RGBA")


if __name__ == "__main__":
    import sys
    skin, cols = None, None
    jar = os.environ.get("SOULS_CLIENT_JAR")
    who = os.environ.get("SKIN", "wide/noor")
    if jar and os.path.exists(jar):
        skin = _skin_from_jar(jar, who)
        cols = skin_colors(skin, slim=who.startswith("slim/"))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview", "roll_figure.png")
    print(preview(out, skin, cols, tilt_axis=float(os.environ.get("TILT", "0"))))
