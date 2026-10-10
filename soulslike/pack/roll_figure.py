"""
구르기 대역 (DESIGN.md 3.3 "보이는 모습"). gen_pack.py 가 icons 다음에 부른다.

구르는 동안 플러그인(combat/Tumble)은 진짜 몸을 감추고(투명) 그 자리에 관절이 있는 사람 꼴의 대역을 띄운다. 대역은 부위마다
따로 된 표시 물체 (ItemDisplay) 열하나 (머리, 가슴, 배, 윗팔·아랫팔 둘씩, 허벅지·정강이 둘씩) 와 든 것 (주손, 왼손) 이고,
부위의 아이템 모형은 그 관절을 원점에 두고 그렸다. 플러그인은 열쇠 자세마다 부위의 자리와 방향 (변환의 이동과 왼쪽 회전) 을
보내고 클라이언트가 틱 사이를 보간한다. 열쇠 자세는 여기서 뼈대 (부위 길이와 관절 자리) 를 따라 정방향으로 셈해
플러그인 자원 roll_anim.yml 로 쓴다 (anim_table). 모양 (팩) 과 움직임 (플러그인) 이 같은 뼈대에서 나온다.

  움직임 (사용자가 고른 본보기, dist/screenshots/reference/: 등 뒤에서 본 빠른 어깨 구르기, 약 0.55초. 2026-10-08 비평 반영)
    달리던 걸음 (0틱, 띄울 때): 앞으로 35°, 왼쪽 (먼저 닿는 쪽) 으로 15° 기울고 왼발이 앞, 무기 든 팔이 몸 앞을 가로지른다
    뛰어들기 (2틱): 배 45°·가슴 70° 로 숙이고 엉덩이 10, 뒷발 (오른발) 은 펴서 발끝으로 땅을 박차고 앞발은 굽힌다.
                    왼팔은 앞쪽 바깥 땅을 짚으러 뻗고 턱을 당기기 시작한다. 몸이 진짜 몸보다 4~5 픽셀 앞으로 나간다 (힘껏 뛰어든다)
    어깨 닿기 (3틱): 왼팔·왼어깨가 먼저 땅에 닿고, 머리는 오른쪽으로 돌려 숙인다 (등 뒤에서는 뒤통수와 정수리만)
    등으로 넘기 (4~5틱): 몸통이 비스듬한 축 (KEYS 의 axis: 구르는 축을 왼쪽 뒤로 45° 돌린다) 으로 굴러 왼어깨 → 등 → 오른엉덩이
                    차례로 땅을 짚는다. 등뼈는 땅에서 55° 를 넘지 않고 (물구나무를 서지 않는다) 엉덩이는 13 아래, 다리는 무릎을
                    90° 넘게 굽힌 채 비스듬히 넘어온다 (곧게 서지 않는다). 등이 등 뒤 카메라를 본다
    딛기 (6틱): 무릎을 당겨 발을 엉덩이 바로 앞에 딛는다
    쪼그리기 (7틱): 가슴을 앞으로 40° 숙인 깊은 쪼그림 (엉덩이 8)
    일어서기 (8~10틱): 반쯤 일어서며 한 발이 앞으로 나가 걸음으로 이어진다
    달리는 걸음 (11틱): 진짜 몸이 돌아오는 때의 자세 (한 발 앞, 무기 든 팔은 바닐라가 든 것을 쥐는 각)
    무기 든 팔 (오른팔) 은 처음부터 끝까지 옆으로 벌린 채 무기를 쥔다. 왼손잡이는 플러그인이 좌우를 뒤집는다.

  souls:roll_belly, roll_chest   몸통 아래·위 (8×6×4, 배 관절 = 엉덩이 가운데, 가슴 관절 = 허리). 등을 말 수 있게 둘로 나눴다
  souls:roll_uarm, roll_farm     윗팔 (어깨 관절은 팔 위 끝에서 2 아래, 바닐라와 같다), 아랫팔 (팔꿈치)
  souls:roll_thigh, roll_shin    허벅지 (엉덩이 관절), 정강이와 신 (무릎)
  souls:roll_head                그 사람의 머리 (바닐라 player_head 특수 모형 + 이 팩의 바탕 모형 souls:item/roll_head). fixed 자세가
                                 해골의 목을 원점에 두고 얼굴을 앞으로 돌린다
  souls:roll_helm                투구를 썼을 때 머리에 씌우는 껍데기 (머리와 같은 fixed 자세, 색 하나로 물든다)
  든 것                          진짜 아이템을 그대로 THIRDPERSON_RIGHTHAND / LEFTHAND 자세로 그 아랫팔 끝에 둔다. 바닐라가 손에 든 것을
                                 그리는 자리 (ItemInHandLayer: 팔 끝 앞 모서리, 팔 축에서 X 로 -90° 돌리고 Y 로 180°) 를 그대로 옮겼다
                                 (손 부위 hand_r·hand_l 의 방향 = 아랫팔 방향 · Rx(90°): ItemDisplay 의 Y 180° 와 합쳐 바닐라와 같다)

색 (물들이기)
  몸의 재료는 뼈 계열 네 단 (팔레트) 으로만 찍은 밝은 그림이고, 면마다 tintindex 가 있다:
  0 몸통, 1 소매 (윗팔), 2 손 (아랫팔), 3 바지, 4 신. 아이템 정의의 tints 가 custom_model_data 의 colors[0..4] 를 곱한다.
  플러그인이 그 사람 스킨에서 고른 색 (갑옷을 입었으면 갑옷 색) 을 보낸다. 없으면 정의의 기본색 (팔레트).
  스킨이 없는 오프라인 접속은 바닐라 기본 스킨 18 개 가운데 UUID 로 고른 것을 쓰므로, 그 18 개의 색 표를 클라이언트
  jar 에서 미리 뽑아 플러그인 자원 roll_skins.yml 로 둔다 (skin_table; jar 가 없으면 있던 표를 그대로 둔다).

공간
  대역 공간 D (픽셀): 원점은 발밑 땅, +Y 위, +Z 앞 (구르는 쪽), +X 그 사람의 왼쪽. 부위마다 관절이 원점인 자기 공간에서 그리고
  (서 있을 때 축이 D 와 같다), 열쇠 자세는 부위의 관절 자리와 방향을 D 로 준다. 플러그인은 그 위에 구르는 쪽 Y 회전을 걸고
  탑승 자리 (몸 상자 꼭대기) 만큼 내리며, 픽셀에 0.9375/16 을 곱해 블록으로 (바닐라가 플레이어를 0.9375 배로 그린다).
  ItemDisplay 는 아이템을 그리기 전에 Y 축으로 180° 돌리므로 아이템 모형 공간 (x, y, z) = (8 - dx, 8 + dy, 8 - dz):
  아이템 공간의 앞은 -Z (북쪽) 다 [확인 (클라): dist/screenshots/roll/].
  바닐라 해골 모형 (player_head 특수 모형) 은 아이템 공간 (4..12, 0..8, 4..12) 에 그려지고 얼굴이 +Z (남쪽) 를 본다
  (SkullSpecialRenderer: (0.5, 0, 0.5) 로 옮기고 (-1,-1,1) 로 뒤집은 뒤 머리를 Y 로 180° 돌린다. 합치면 X 축 180° 회전이라 얼굴은
  +Z, 거울상 아님) [확인 (클라): /soulstest tumble]. 그래서 머리 자세는 Y 로 180° 돌려 얼굴을 앞 (-Z) 으로 보내고 목을 원점으로 올린다.

손에 든 것 감추기 (wrap_item_definitions)
  구르는 동안 플러그인은 진짜 몸 (투명) 이 든 아이템의 사본에 custom_model_data 깃발 0 을 켜서 그 사람 화면과 보는 사람에게만
  보낸다 (sendEquipmentChange). 이 팩의 souls 아이템 정의는 모두 그 깃발이 켜지면 손·머리 자세 (3인칭, 1인칭) 에서 아무것도 그리지
  않는다 (든 것은 대역의 손에 따로 그린다). 단축 슬롯(gui)·땅·액자는 그대로라 슬롯 그림이 사라지지 않고, 아이템 종류와 이름이 같아
  바닐라가 이름을 다시 띄우지도 않는다 (공기를 보내면 둘 다 일어난다 [확인 (클라)]). 갑옷 칸은 공기를 보낸다.
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
HIDE_FLAG = 0                      # custom_model_data 깃발 번호 (플러그인 Tumble.HIDE_FLAG 와 같다)
# 3인칭 손·머리 (투명한 몸에 떠 보인다) 와 1인칭 손 (구르는 동안 무기를 거두었다가 끝나면 다시 든다: 바닐라의 바꿔 들기
# 몸짓이 구르기 시작에 내리고 끝에 올린다. 1인칭을 그대로 두면 사본이 바뀔 때마다 두 번 내렸다 올렸다)
HIDDEN_CONTEXTS = ["thirdperson_righthand", "thirdperson_lefthand", "firstperson_righthand", "firstperson_lefthand", "head"]

# 대역 크기: 플레이어 모형과 같은 픽셀 크기 (바닐라는 플레이어를 0.9375 배로 그린다). 플러그인은 이 값을 roll_anim.yml 에서 읽는다
SCALE = 0.9375

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
TEX_ID = {k: f"{NS}:item/roll_{k}" for k in (*TEXTURES, "px")}


# ─────────────────────────── 부위 모형 ───────────────────────────
# 상자는 부위 공간 D (관절이 원점, 픽셀) 의 (x0, x1, y0, y1, z0, z1). 이웃 부위와 맞닿는 곳은 조금 겹치고 굵기를 0.05~0.1 달리해
# 굽혔을 때 틈이 덜 보이고 겹친 면이 깜빡이지 않게 했다. sole: 그 면 (D 방향 이름) 을 밑창 그림으로.

class Shape:
    def __init__(self, x0, x1, y0, y1, z0, z1, tex, tint, sole=None):
        self.lo = np.array([x0, y0, z0], float)
        self.hi = np.array([x1, y1, z1], float)
        self.tex, self.tint, self.sole = tex, tint, sole


T_TORSO, T_SLEEVE, T_HAND, T_LEGS, T_BOOTS = 0, 1, 2, 3, 4

SHAPES = {
    # 배: 엉덩이 가운데에서 허리까지
    "belly": [Shape(-4.0, 4.0, 0.0, 6.0, -2.0, 2.0, "cloth", T_TORSO)],
    # 가슴: 허리에서 목까지 (배 속으로 1 내려 등을 말 때 틈을 가린다)
    "chest": [Shape(-4.1, 4.1, -1.0, 6.0, -2.1, 2.1, "cloth", T_TORSO)],
    # 윗팔: 어깨 관절은 팔 위 끝에서 2 아래 (바닐라 팔과 같다)
    "uarm": [Shape(-2.0, 2.0, -4.0, 2.0, -2.0, 2.0, "sleeve", T_SLEEVE)],
    # 아랫팔 (손): 팔꿈치에서 6 (윗팔 속으로 1 올라간다: 마디 사이 보간에서 팔꿈치가 벌어지지 않게)
    "farm": [Shape(-1.95, 1.95, -6.0, 1.0, -1.95, 1.95, "hand", T_HAND)],
    # 허벅지: 엉덩이 관절에서 6 (배 속으로 1. 배와 면이 겹치지 않게 0.05 가늘다)
    "thigh": [Shape(-1.95, 1.95, -6.0, 1.0, -1.95, 1.95, "trousers", T_LEGS)],
    # 정강이 2 (바지, 허벅지 속으로 1) + 신 4 (스킨의 다리 아래 4줄이 신)
    "shin": [Shape(-1.9, 1.9, -2.0, 1.0, -1.9, 1.9, "trousers", T_LEGS),
             Shape(-2.05, 2.05, -6.0, -2.0, -2.05, 2.05, "boot", T_BOOTS, sole="down")],
}
BODY_MODELS = tuple(SHAPES)

# ─────────────────────────── 뼈대 ───────────────────────────
HIP_Y = 12.0          # 서 있을 때 엉덩이 높이 (바닐라 다리 12)
BELLY_H = 6.0         # 엉덩이 → 허리
CHEST_H = 6.0         # 허리 → 목
SHOULDER = (6.0, 4.0)  # 허리에서 어깨 관절: 옆 6 (팔 한가운데), 위 4
UARM = 4.0            # 어깨 → 팔꿈치
FARM = 6.0            # 팔꿈치 → 팔 끝
HAND_FWD = 2.0        # 든 것의 자리: 팔 끝의 앞 모서리 (바닐라 ItemInHandLayer: 팔 관절에서 (∓1, 10, -2) 모형 픽셀)
HIP_X = 2.0           # 엉덩이 관절의 옆 자리
THIGH = 6.0           # 엉덩이 → 무릎
SHIN = 6.0            # 무릎 → 발바닥

# 플러그인에 보내는 부위 차례 (roll_anim.yml 의 parts). hand_* 는 든 것의 자리
PARTS = ("belly", "chest", "head", "uarm_r", "farm_r", "uarm_l", "farm_l",
         "thigh_r", "shin_r", "thigh_l", "shin_l", "hand_r", "hand_l")
MODEL_OF = {"belly": "belly", "chest": "chest", "head": "head", "uarm_r": "uarm", "uarm_l": "uarm", "farm_r": "farm",
            "farm_l": "farm", "thigh_r": "thigh", "thigh_l": "thigh", "shin_r": "shin", "shin_l": "shin"}


def _rx(deg):
    t = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])


def _ry(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])


def _rz(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])


# ─────────────────────────── 열쇠 자세 ───────────────────────────
# 각 (도) 의 뜻. 몸통 방향 = Ry(axis) · Rx(pitch) · Ry(twist - axis) · Rz(bank): pitch 는 앞으로 구른 각 (0·360 이면 곧게 선다) 이고
# 그 축은 옆 축 (X) 을 axis 만큼 Y 로 돌린 것이다 (axis 45 면 왼쪽 뒤 - 오른쪽 앞의 비스듬한 축: 몸이 앞으로 구르면서 왼쪽으로 넘어가
# 왼어깨에서 오른엉덩이로 비스듬히 구르고, 거꾸로 선 동안 등이 등 뒤 카메라를 본다. pitch 0·360 에서는 axis 가 아무것도 바꾸지 않는다).
# twist 는 몸을 Y 로 돌린 각 (- 면 왼어깨가 앞으로), bank 는 옆으로 기운 각 (+ 면 위가 오른쪽으로). spine: 가슴을 배에 대해 앞으로 만 각
# (등이 둥글어진다). neck: 머리를 숙인 각 (- 면 든다), turn: 머리를 돌린 각 (- 면 오른쪽으로).
# 팔 (flex 앞으로 든 각, abd 옆으로 벌린 각, elbow 팔꿈치를 굽힌 각, roll 아랫팔을 제 축으로 돌린 각 (+ 면 오른손의 날이 왼쪽으로)):
# 어깨 회전 = Rz(벌림) · Rx(-flex), 팔꿈치 Rx(-elbow) · Ry(∓roll).
# 다리 (flex 허벅지를 앞으로 든 각 (몸통 기준이라 몸을 숙이면 그만큼 더 든다), abd 벌린 각, knee 무릎을 굽힌 각):
# 엉덩이 회전 = Rz(벌림) · Rx(-flex), 무릎 Rx(knee).
# t: 그 자세에 닿는 구르기 틱 (0 은 처음 띄울 때). z: 엉덩이의 앞뒤 자리 (픽셀, 진짜 몸의 발밑 기준), x: 옆 자리.
# 높이는 정하지 않는다: 가장 낮은 점이 땅 (y = lift) 에 닿게 내린다 (_ground).
# 오른팔이 무기를 든 팔이다 (오른손잡이). 왼손잡이는 플러그인이 X 를 뒤집고 좌우 부위를 바꾼다.
# 2026-10-08 비평 반영: 예전 판은 엉덩이가 15~20 까지 올라 몸이 거꾸로 곧게 섰고 (옆에서 물구나무), 뛰어들기가 납작한 널빤지,
# 등으로 누웠다가 한 틱에 벌떡 섰다. 이 판은 엉덩이가 13 을 넘지 않고 등뼈가 땅에서 55° 안이며, 착지 뒤 세 틱에 걸쳐 일어선다.
KEYS = [
    # 달리던 걸음 (띄울 때 생성 패킷에 실린다): 앞으로 35°, 왼쪽으로 15° 기울고 왼발 앞, 무기 든 팔이 몸 앞을 가로지른다
    dict(t=0, axis=20, pitch=38, twist=-5, bank=0, spine=8, neck=-10, turn=0,
         arm_r=(50, -25, 45, 80), arm_l=(30, 12, 30, 0), leg_r=(20, 4, 35), leg_l=(65, 4, 30), z=0.0),
    # 뛰어들기: 배 45°·가슴 70°, 엉덩이 10. 뒷발은 펴서 발끝으로 박차고 앞발은 굽힌다. 왼팔은 앞쪽 바깥 땅으로, 무기 든 팔은 옆으로
    dict(t=2, axis=35, pitch=55, twist=-15, bank=10, spine=25, neck=30, turn=-30,
         arm_r=(30, 75, 30, 80), arm_l=(110, 35, 10, 0), leg_r=(25, 6, 5), leg_l=(90, 6, 100), z=4.0),
    # 어깨 닿기: 왼팔과 왼어깨가 땅에 닿는다. 머리는 숙여 오른쪽으로 돌린다 (얼굴이 등 뒤 카메라를 보지 않게). 다리는 굽혀 땅을 떠난다
    dict(t=3, axis=45, pitch=150, twist=20, bank=40, spine=50, neck=40, turn=-80,
         arm_r=(40, 85, 30, 80), arm_l=(100, 40, 60, 0), leg_r=(60, 10, 100), leg_l=(90, 8, 110), z=5.0),
    # 등으로 넘기: 왼어깨 → 등. 방패 든 왼팔은 가슴에 붙이고, 다리는 굽힌 채 비스듬히 넘어온다
    dict(t=4, axis=45, pitch=225, twist=20, bank=40, spine=50, neck=40, turn=-70,
         arm_r=(50, 85, 25, 80), arm_l=(60, -30, 130, 0), leg_r=(100, 15, 100), leg_l=(90, 8, 110), z=3.0),
    # 오른엉덩이로 넘어가며 다리가 앞으로 내려온다
    dict(t=5, axis=45, pitch=285, twist=15, bank=30, spine=45, neck=40, turn=-30,
         arm_r=(50, 75, 25, 80), arm_l=(60, -30, 130, 0), leg_r=(115, 10, 120), leg_l=(110, 8, 120), z=2.0),
    # 딛기: 무릎을 당겨 발을 엉덩이 바로 앞에 딛는다 (정강이가 거의 선다)
    dict(t=6, axis=45, pitch=335, twist=5, bank=15, spine=35, neck=10, turn=-10,
         arm_r=(40, 50, 35, 70), arm_l=(50, -10, 60, 0), leg_r=(75, 6, 150), leg_l=(70, 6, 145), z=1.0),
    # 쪼그리기: 가슴을 앞으로 40° 숙인 깊은 쪼그림
    dict(t=7, axis=30, pitch=395, twist=0, bank=4, spine=10, neck=-12, turn=0,
         arm_r=(35, 40, 35, 60), arm_l=(40, 0, 50, 0), leg_r=(105, 5, 130), leg_l=(100, 5, 125), z=0.0),
    # 반쯤 일어서며 왼발이 앞으로
    dict(t=8, axis=15, pitch=387, twist=0, bank=0, spine=8, neck=-10, turn=0,
         arm_r=(28, 28, 30, 45), arm_l=(30, 5, 40, 0), leg_r=(45, 4, 80), leg_l=(75, 4, 80), z=0.0),
    # 일어서며 걸음으로 이어진다. 무기를 바닐라의 든 자세로 돌린다
    dict(t=9, axis=0, pitch=372, twist=0, bank=0, spine=5, neck=-6, turn=0,
         arm_r=(24, 15, 20, 25), arm_l=(0, 5, 30, 0), leg_r=(10, 3, 40), leg_l=(55, 3, 45), z=0.0),
    dict(t=10, axis=0, pitch=368, twist=0, bank=0, spine=3, neck=-4, turn=0,
         arm_r=(20, 8, 10, 8), arm_l=(-15, 4, 20, 0), leg_r=(-15, 2, 45), leg_l=(40, 2, 25), z=0.0),
    # 진짜 몸이 돌아오는 때: 달리는 걸음 (왼발 앞, 오른발은 뒤로 들린다), 무기 든 팔은 바닐라가 든 것을 쥐는 각 (앞으로 18°)
    dict(t=11, axis=0, pitch=366, twist=0, bank=0, spine=2, neck=-2, turn=0,
         arm_r=(18, 4, 0, 0), arm_l=(-22, 3, 10, 0), leg_r=(-25, 1, 60), leg_l=(30, 1, 15), z=0.0),
]
# 처음 보간을 보내는 틱 (anim_table). F 는 틱 사이에 와서 대역의 생성 패킷은 곧바로 나가고, 1틱 (그다음 틱의 처음) 에 보낸 자세는
# 그 틱 끝에 나간다. 클라이언트가 대역을 처음 그리기 전에 그것이 닿으면 첫 그림이 곧바로 그 자세 (보간 없이) 다: 0·2틱 자세가
# 둘 다 몸을 숙인 자세라 어느 쪽이든 이어 보인다. 예전 (2) 에는 첫 자세가 2틱 동안 멈춰 섰다 (비평: 늦게 시작하고 멈칫한다)
FIRST_SEND = 1
LIFT = 0.2   # 가장 낮은 점을 땅에서 띄우는 몫 (보간 중 마디 사이에서 땅에 묻히지 않게)


def _arm(side, flex, abd, elbow, roll=0.0):
    s = 1 if side == "l" else -1
    return _rz(s * abd) @ _rx(-flex), _rx(-elbow) @ _ry(-s * roll)


def _leg(side, flex, abd, knee):
    s = 1 if side == "l" else -1
    return _rz(s * abd) @ _rx(-flex), _rx(knee)


def fk(k, root=None):
    """열쇠 자세 → {부위: (관절 자리 (D 픽셀), 회전 행렬)}. root 는 엉덩이 자리 (없으면 (x, HIP_Y, z))."""
    psi = k.get("axis", 0.0)
    R0 = _ry(psi) @ _rx(k["pitch"]) @ _ry(k["twist"] - psi) @ _rz(k["bank"])
    P0 = np.array(root if root is not None else (k.get("x", 0.0), HIP_Y, k["z"]), float)
    out = {"belly": (P0, R0)}
    Rc = R0 @ _rx(k["spine"])
    Pc = P0 + R0 @ np.array([0.0, BELLY_H, 0.0])
    out["chest"] = (Pc, Rc)
    out["head"] = (Pc + Rc @ np.array([0.0, CHEST_H, 0.0]), Rc @ _ry(k["turn"]) @ _rx(k["neck"]))
    for side, sx in (("r", -1.0), ("l", 1.0)):
        sh, el = _arm(side, *k["arm_" + side])
        Pu = Pc + Rc @ np.array([sx * SHOULDER[0], SHOULDER[1], 0.0])
        Ru = Rc @ sh
        Pf = Pu + Ru @ np.array([0.0, -UARM, 0.0])
        Rf = Ru @ el
        out["uarm_" + side] = (Pu, Ru)
        out["farm_" + side] = (Pf, Rf)
        out["hand_" + side] = (Pf + Rf @ np.array([0.0, -FARM, HAND_FWD]), Rf @ _rx(90))
        hp, kn = _leg(side, *k["leg_" + side])
        Pt = P0 + R0 @ np.array([sx * HIP_X, 0.0, 0.0])
        Rt = R0 @ hp
        out["thigh_" + side] = (Pt, Rt)
        out["shin_" + side] = (Pt + Rt @ np.array([0.0, -THIGH, 0.0]), Rt @ kn)
    return out


def _corners(sh):
    return np.array([[x, y, z] for x in (sh.lo[0], sh.hi[0]) for y in (sh.lo[1], sh.hi[1]) for z in (sh.lo[2], sh.hi[2])])


def _points(frame):
    """자세의 몸 꼭짓점 (D): 부위 상자와 머리 (8×8×8, 목에서 위로)."""
    pts = []
    for part, (P, R) in frame.items():
        if part == "head":
            pts += [P + R @ np.array([x, y, z]) for x in (-4, 4) for y in (0, 8) for z in (-4, 4)]
        elif part in MODEL_OF:
            for sh in SHAPES[MODEL_OF[part]]:
                pts += [P + R @ p for p in _corners(sh)]
    return np.array(pts)


def _face_samples(lo, hi, step):
    """상자 (lo..hi) 겉면 위의 점들 (step 픽셀 격자, 모서리 포함)."""
    axes = [np.linspace(lo[i], hi[i], max(2, int(math.ceil((hi[i] - lo[i]) / step)) + 1)) for i in range(3)]
    out = []
    for i in range(3):
        j, k = [a for a in range(3) if a != i]
        gj, gk = np.meshgrid(axes[j], axes[k], indexing="ij")
        for v in (lo[i], hi[i]):
            pts = np.zeros((gj.size, 3))
            pts[:, i] = v
            pts[:, j] = gj.ravel()
            pts[:, k] = gk.ravel()
            out.append(pts)
    return np.concatenate(out)


def _samples(frame, step=1.0):
    """자세의 몸 겉면 점들 (D): 꼭짓점만 보면 화면을 가로지르는 큰 면이나 카메라를 품은 상자를 놓친다 [확인 (클라)]."""
    pts = []
    for part, (P, R) in frame.items():
        if part == "head":
            boxes = [(np.array([-4.5, -0.5, -4.5]), np.array([4.5, 8.5, 4.5]))]   # 모자 겹 (0.5) 까지
        elif part in MODEL_OF:
            boxes = [(sh.lo, sh.hi) for sh in SHAPES[MODEL_OF[part]]]
        else:
            continue
        for lo, hi in boxes:
            pts.append(P + _face_samples(lo, hi, step) @ R.T)
    return np.concatenate(pts)


def _ground(k):
    """가장 낮은 점이 y = LIFT 에 닿게 엉덩이 높이를 고친 자세."""
    f = fk(k)
    dy = LIFT - _points(f)[:, 1].min()
    P0 = f["belly"][0] + np.array([0.0, dy, 0.0])
    return fk(k, root=P0)


def frames():
    """[(닿는 틱, {부위: (자리, 회전)})] 열쇠 자세 차례로."""
    return [(k["t"], _ground(k)) for k in KEYS]


def quat(R):
    """회전 행렬 → 사원수 (x, y, z, w)."""
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    q = np.array([x, y, z, w])
    return q / np.linalg.norm(q)


def _angle(q1, q2):
    return math.degrees(2 * math.acos(min(1.0, abs(float(q1 @ q2)))))


def check_steps(fs=None, limit=150.0):
    """마디 사이에 부위가 limit 도 넘게 돌면 멈춘다 (클라이언트는 가까운 쪽으로 구면 보간하므로 180° 에 가까우면 거꾸로 돈다)."""
    fs = fs or frames()
    worst = 0.0
    for (_, a), (t, b) in zip(fs, fs[1:]):
        for part in PARTS:
            d = _angle(quat(a[part][1]), quat(b[part][1]))
            worst = max(worst, d)
            if d > limit:
                raise ValueError(f"구르기 대역 {part}: {t}틱 마디에 {d:.0f}° 돈다 (≤ {limit:.0f}°)")
    return worst


def _slerp(q1, q2, a):
    d = float(q1 @ q2)
    if d < 0:
        q2, d = -q2, -d
    if d > 0.9995:
        q = q1 + (q2 - q1) * a
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - a) * th) * q1 + math.sin(a * th) * q2) / math.sin(th)


def _qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def between(fa, fb, a):
    """클라이언트의 보간과 같게: 부위마다 자리는 직선, 방향은 구면 보간."""
    return {p: (fa[p][0] + (fb[p][0] - fa[p][0]) * a, _qmat(_slerp(quat(fa[p][1]), quat(fb[p][1]), a))) for p in fa}


# ─────────────────────────── 1인칭에서 감추기 (표시 알파와 아이템 셰이더) ───────────────────────────
# 서버는 그 사람이 1인칭인지 F5 인지 모른다. 그래서 내려다보는 각으로 대역을 감추면 (예전 판: 35° 넘게 내려다보면 감추고 덜 내려다보면
# F5 카메라 쪽으로 줄여 물렸다) F5 로 내려다볼 때 아무것도 보이지 않았다 (사용자: "3인칭에서 아래를 보면 아예 안 보임").
# 1인칭과 F5 를 가르는 것은 카메라 자리뿐이고, 그것을 아는 것은 클라이언트다. 그래서 클라이언트의 아이템 셰이더가 가른다:
#   - 그 사람 화면에만 보이는 벌 (own) 의 모든 그림 (몸 부위, 머리, 투구, 손에 든 souls 아이템) 은 표시 알파 (MARK_HI - k,
#     k = 0..MARK_CLASSES-1) 로 칠한 그림을 쓴다. 다른 그림에는 없는 알파다 (바닐라·이 팩의 아이템·블록 그림 240~249 는 비었다
#     [확인 (클라이언트 jar, 팩)]. 250~252 는 발광 알파라 피했다).
#   - 셰이더 (assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull: 아이템 아틀라스의 아이템 모형은 모두 이것으로
#     그린다 [확인 (클라이언트 코드: BlockModelWrapper)]) 는 표시 알파의 조각이 카메라에서 반지름 r_k = MARK_R0 + k·MARK_STEP 블록
#     안에 있으면 버리고, 아니면 불투명하게 그린다.
#   - k 는 그 그림이 그리는 점이 1인칭 카메라 (발 위 EYES 의 어느 높이) 에서 가장 멀어지는 거리 + MARK_MARGIN 으로 고른다 (모든 열쇠
#     자세와 그 사이 보간, 왼손잡이 거울). 1인칭 카메라는 대역 바로 곁이므로 모든 조각이 r 안에 있어 하나도 그려지지 않는다. F5
#     카메라는 눈에서 4 블록 떨어져 있어 (벽에 막히지 않으면) 어느 조각도 r 안에 들지 않는다: 그림이 그대로다.
#   - 바닐라 머리 (player_head 특수 모형) 는 엔티티 셰이더로 스킨을 그려 표시할 수 없다. 그래서 own 벌의 머리는 스킨 픽셀 384 개
#     (여섯 면 × 8×8, 덧옷 층을 겹친 색) 를 면마다 물들인 픽셀 머리 (souls:roll_headpx) 다. 다른 사람에게 보이는 벌 (seen) 은
#     예전처럼 바닐라 머리 (그 사람 프로필) 와 진짜 아이템 그대로다 (표시하지 않는다).
# 셰이더를 못 쓰는 클라이언트 (셰이더 팩을 켠 Iris 등) 는 1인칭에서 대역이 보인다 (예전 판에서 35° 를 넘게 내려다보지 않을 때와 같다).
MARK_FLAG = 1          # custom_model_data 깃발: own 벌이 손에 든 souls 아이템 (플러그인 Tumble.MARK_FLAG 와 같다)
CEILING = "lime_stained_glass"   # 기어가기 막힘 블록 (플러그인 Roll.CEILING 과 같다): 팩이 모형을 비운다
MARK_HI = 249          # 표시 알파: MARK_HI - k
MARK_CLASSES = 10      # k = 0..9 (알파 249..240)
MARK_R0 = 0.4          # k 번째 반지름 (블록) = MARK_R0 + k · MARK_STEP
MARK_STEP = 0.35
MARK_MARGIN = 0.12     # 반지름에 더하는 여유 (블록): 표면 표본 (1 픽셀 격자) 사이, 보간 표본 (1/4 틱) 사이
# 1인칭 카메라 높이 (발 위, 블록): 서기 1.62, 웅크리기 1.27, 기어가기 0.4. 카메라 높이는 자세가 바뀌면 틱마다 남은 몫의 반씩 옮겨 가므로
# 그 사이 값도 본다. 카메라는 그 사람 몸 상자 한가운데 위 (대역 공간 x = z = 0) 다
EYES = (0.4, 0.5, 0.62, 0.75, 0.9, 1.05, 1.2, 1.27, 1.4, 1.52, 1.62)
PX = 16 / SCALE        # 대역 공간 D 의 1 블록 (픽셀)
# 반지름을 함께 고르는 부위 묶음 (같은 그림을 쓰는 부위끼리)
GROUPS = {"head": ("head",), "torso": ("belly", "chest"), "arm": ("uarm_r", "farm_r", "uarm_l", "farm_l"),
          "leg": ("thigh_r", "shin_r", "thigh_l", "shin_l")}
TEX_GROUP = {"cloth": "torso", "sleeve": "arm", "hand": "arm", "trousers": "leg", "boot": "leg", "sole": "leg", "helm": "head",
             "px": "head"}
HEAD_BOX = (np.array([-4.7, -0.7, -4.7]), np.array([4.7, 8.7, 4.7]))   # 머리 (목에서 위로 8) + 모자 겹 0.5 + 투구 껍데기 0.6


def anim_samples(fs=None, steps=4):
    """열쇠 자세와 그 사이 보간 (1/steps 틱 마디): 클라이언트가 그리는 모든 자세를 덮는다."""
    fs = fs or frames()
    out = []
    for (_, fa), (_, fb) in zip(fs, fs[1:]):
        out += [between(fa, fb, a) for a in np.arange(steps) / steps]
    out.append(fs[-1][1])
    return out


def part_surface(frame, part, step=1.0):
    """부위의 겉면 점 (D 픽셀)."""
    P, R = frame[part]
    if part == "head":
        boxes = [HEAD_BOX]
    else:
        boxes = [(sh.lo, sh.hi) for sh in SHAPES[MODEL_OF[part]]]
    return np.concatenate([P + _face_samples(lo, hi, step) @ R.T for lo, hi in boxes])


def eye_reach(pts):
    """점들 (D 픽셀) 이 1인칭 카메라 (EYES 의 어느 높이) 에서 가장 멀어지는 거리 (블록)."""
    best = 0.0
    for e in EYES:
        d = np.linalg.norm(pts - np.array([0.0, e * PX, 0.0]), axis=1).max() / PX
        best = max(best, float(d))
    return best


def group_reach(seq=None):
    """부위 묶음마다 가장 먼 거리 (블록)."""
    seq = seq or anim_samples()
    out = {}
    for g, parts in GROUPS.items():
        out[g] = max(eye_reach(np.concatenate([part_surface(f, p) for p in parts])) for f in seq)
    return out


# ── 틱마다 부위마다의 반지름 (그 사람 화면의 벌: 물들이는 색에 실어 보낸다) ──
# 위의 표시 알파 반지름은 그림 하나에 하나라 모든 자세·모든 눈 높이 (EYES) 의 가장 먼 거리다 (머리 2.5, 팔 2.15 블록). F5 카메라가
# 벽·바닥에 막혀 눈 가까이 당겨지면 (올려다보기, 등 뒤의 턱) 그 반지름 안에 든 대역이 잘려 사라졌다 (2026-10-08 비평). 그래서
# 플러그인이 열쇠 자세를 보낼 때마다 own 벌의 부위마다 그 자세에 맞는 반지름을 물들이는 색 (custom_model_data colors) 의 낮은 비트에
# 실어 보낸다 (Tumble). 셰이더 (꼭짓점 셰이더) 가 그 값을 읽는다: 색마다 R·G·B 의 낮은 두 비트 = 6 비트 code, 반지름 = code ×
# CODE_STEP 블록 (code 1..62. 0 과 63 (물들이지 않은 흰 면: 손에 든 souls 아이템) 은 표시 알파 반지름으로 돌아간다). 색은 채널마다
# 3/255 안에서만 바뀐다.
# 표 (roll_anim.yml radius): 열쇠 자세 j 를 보낸 때부터 다음 자세를 보낼 때까지 (그 사이 보간 포함) 부위의 겉면이 1인칭 카메라에서
# 가장 멀어지는 거리 (블록). 카메라 높이는 그 사람 클라이언트의 자세를 따른다:
#   stand  기어가기 막힘이 없다: 서기 1.62 (이어 구르기에서 아직 올라오는 1.45, 1.5 높이 틈에 갇혀 웅크린 1.27 까지)
#   duck   막힘을 duck 틱 깔았다: 아래 눈 높이 모형 (eye_height) 의 그 틱 앞뒤 EYE_WINDOW 틱 + stand 의 높이 (막힘이 늦게 듣거나 일찍
#          걷혀도 (Roll 이 카메라·바닥을 보고 일찍 거둔다) 눈 높이는 그 사이에 있고, 거리는 눈 높이에 대해 볼록이라 두 끝만 보면 된다)
# 플러그인은 반지름에 RADIUS_MARGIN 과 벽 때문에 옆으로 옮긴 몫을 더해 code 로 올림한다.
CODE_STEP = 0.05
CODE_CLEAR = 0xFCFCFC    # 색에서 code 비트를 비운다
EYE_WINDOW = 1.0
RADIUS_MARGIN = 0.1
STAND_EYES = (1.27, 1.45, 1.62)


def eye_height(s, duck):
    """
    기어가기 막힘을 duck 틱 동안 깐 구르기에서 그 사람 1인칭 카메라 높이 (발 위, 블록). s 는 대역의 시계 (열쇠 자세 t 에 닿는 때가
    s = t, 서버 n 틱에 보낸 것이 클라이언트에서 s = n 에 보간을 시작한다). 클라이언트 [확인 (클라이언트 코드: Camera.tick, LocalPlayer)]:
    막힘과 대역은 함께 닿고 다음 틱 (s = 1) 의 플레이어 틱에서 자세가 기어가기 (눈 0.4) 로 바뀐다. 카메라 틱은 플레이어 틱보다 먼저라
    그다음 틱 (s = 2) 부터 눈 높이가 틱마다 남은 몫의 반씩 옮겨 가고, 그리는 높이는 틱 사이를 잇는다. 막힘을 걷는 서버 duck 틱의 것은
    s = duck 에 서기로 바뀌어 s = duck + 1 부터 올라온다. 실제 클라이언트에서 잰 값 (1인칭 89° 바닥 텍셀 간격) 은 이 모형보다 0.5 틱쯤
    앞선다: EYE_WINDOW 가 덮는다.
    """
    vals = [1.62]
    q = 1.62
    for n in range(1, int(math.ceil(s)) + 2):
        target = 0.4 if 1 <= n - 1 < duck else 1.62
        q += (target - q) * 0.5
        vals.append(q)
    if s <= 1:
        return 1.62
    n = int(math.floor(s))
    return vals[n - 1] + (vals[n] - vals[n - 1]) * (s - n)


def _send_ticks(fs):
    """열쇠 자세마다 보내는 서버 틱 (anim_table 과 같다)."""
    out, prev = [], None
    for t, _ in fs:
        out.append(0 if prev is None else max(prev, FIRST_SEND))
        prev = t
    return out


def _segment(fs, j, steps=8):
    """자세 j 를 보낸 때부터 보이는 자세들: 앞 자세에서 j 까지의 보간 (j = 0 은 처음 자세)."""
    if j == 0:
        return [fs[0][1]]
    return [between(fs[j - 1][1], fs[j][1], a) for a in np.linspace(0.0, 1.0, steps + 1)]


def _reach_from(pts, eyes):
    return max(float(np.linalg.norm(pts - np.array([0.0, e * PX, 0.0]), axis=1).max()) / PX for e in eyes)


def radius_table(duck, fs=None):
    """{"stand": [[부위마다 반지름] 자세마다], "duck": ...} (블록, PARTS 차례. hand_r·hand_l 은 손 관절까지의 거리: 손에 든 것은
    표시 알파 반지름을 쓰므로 플러그인은 쓰지 않는다)."""
    fs = fs or frames()
    send = _send_ticks(fs)
    out = {"stand": [], "duck": []}
    for j in range(len(fs)):
        lo = send[j]
        hi = send[j + 1] if j + 1 < len(fs) else fs[j][0] + 1
        seg = _segment(fs, j)
        span = np.linspace(lo - EYE_WINDOW, hi + EYE_WINDOW, 25)
        duck_eyes = sorted(set(STAND_EYES) | {round(eye_height(s, duck), 4) for s in span})
        for mode, eyes in (("stand", STAND_EYES), ("duck", duck_eyes)):
            row = []
            for part in PARTS:
                if part.startswith("hand"):
                    pts_list = [f[part][0][None, :] for f in seg]
                else:
                    pts_list = [part_surface(f, part) for f in seg]
                row.append(max(_reach_from(p, eyes) for p in pts_list))
            out[mode].append(row)
    return out


def side_table(fs=None):
    """자세마다 대역 몸 (손에 든 것은 빼고) 의 옆 끝 [가장 오른쪽 x, 가장 왼쪽 x] (블록, 대역 공간 +X = 그 사람의 왼쪽): 그 자세로
    가는 보간과 다음 자세로 가는 보간을 모두 덮는다. 플러그인이 구르는 길 옆의 벽을 보고 반대 어깨로 구르거나 옆으로 옮긴다 (Tumble)."""
    fs = fs or frames()
    body = [p for p in PARTS if not p.startswith("hand")]
    out = []
    for j in range(len(fs)):
        segs = _segment(fs, j) + (_segment(fs, j + 1) if j + 1 < len(fs) else [])
        xs = np.concatenate([np.concatenate([part_surface(f, p) for p in body])[:, 0] for f in segs]) / PX
        out.append([float(xs.min()), float(xs.max())])
    return out


def config_duck(path):
    """플러그인 config.yml 의 combat.roll.tumble.duck (못 읽으면 5)."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return int(cfg["combat"]["roll"]["tumble"]["duck"])
    except Exception as ex:  # noqa: BLE001
        print("config.yml 의 combat.roll.tumble.duck 을 읽지 못해 5 로 셈한다:", ex)
        return 5


def mark_class(reach):
    """가장 먼 거리 (블록) → 반지름 마디 k. 마디를 넘으면 ValueError (셰이더 표를 늘린다)."""
    k = int(math.ceil((reach + MARK_MARGIN - MARK_R0) / MARK_STEP - 1e-9))
    k = max(0, k)
    if k >= MARK_CLASSES:
        raise ValueError(f"구르기 대역 표시: 거리 {reach:.2f} 블록이 셰이더 반지름 표 ({MARK_R0 + (MARK_CLASSES - 1) * MARK_STEP:.2f}) 를 넘는다")
    return k


def mark_radius(k):
    return MARK_R0 + k * MARK_STEP


def marked_image(img, k):
    """그림의 보이는 픽셀 (알파 > 0) 의 알파를 표시 알파 MARK_HI - k 로 (색은 그대로)."""
    a = np.array(img.convert("RGBA"))
    a[..., 3] = np.where(a[..., 3] > 0, MARK_HI - k, 0)
    return Image.fromarray(a, "RGBA")


# 셰이더: 바닐라 1.21.11 rendertype_item_entity_translucent_cull 에 표시 알파 한 덩이를 더했다 (ASCII 만: 드라이버마다 주석의 글자를 다르게 본다)
ITEM_VSH = """#version 330

// Block Soul (pack/roll_figure.py). Vanilla 1.21.11 rendertype_item_entity_translucent_cull.vsh plus:
// soulsRel: the camera-relative position, for the roll stand-in marker test in the fragment shader;
// soulsCode / soulsIn: the radius the plugin codes into the low two bits of each tint channel (R, G, B -> 6 bits,
// radius = code * %(cstep).2f blocks, codes 1..62; 0 and 63 = no code) and whether this vertex lies inside it.

#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in vec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler2;


out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;
out vec2 texCoord1;
out vec2 texCoord2;
out vec3 soulsRel;
out float soulsIn;
flat out float soulsCode;

void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, Color) * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;
    texCoord1 = UV1;
    texCoord2 = UV2;
    soulsRel = Position;
    ivec3 bits = ivec3(Color.rgb * 255.0 + 0.5) & 3;
    int code = bits.r | (bits.g << 2) | (bits.b << 4);
    soulsCode = float(code);
    soulsIn = (code > 0 && code < 63 && length(Position) < float(code) * %(cstep).4f) ? 1.0 : 0.0;
}
""" % {"cstep": CODE_STEP}

ITEM_FSH = """#version 330

// Block Soul (pack/roll_figure.py). Vanilla 1.21.11 rendertype_item_entity_translucent_cull.fsh plus one block:
// texels whose alpha (read at mip level 0) is a roll stand-in marker (%(lo)d..%(hi)d) belong to the copy of the roll
// stand-in that only the rolling player sees. If the plugin coded a radius into the tint (soulsCode 1..62, see the .vsh),
// a triangle is dropped when all three of its corners lie inside that radius around the camera (soulsIn interpolates to 1);
// otherwise the whole triangle is drawn opaque. The radius is the farthest that part gets from the player's first-person
// camera while that pose is shown, so in first person every corner is inside and nothing of the stand-in is drawn; the
// third-person camera is 4 blocks away and draws all of it. Without a code (held items: untinted, code 63) the marker
// k = %(hi)d - alpha gives a fixed radius r = %(r0).2f + k * %(step).2f blocks tested per fragment.
// No other texture in the item and block atlases uses these alphas.

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;
in vec2 texCoord1;
in vec3 soulsRel;
in float soulsIn;
flat in float soulsCode;

out vec4 fragColor;

void main() {
    vec4 tex = texture(Sampler0, texCoord0);
    float mark = floor(textureLod(Sampler0, texCoord0, 0.0).a * 255.0 + 0.5);
    if (mark >= %(lo)d.0 && mark <= %(hi)d.0) {
        if (soulsCode > 0.5 && soulsCode < 62.5) {
            if (soulsIn > 0.999) {
                discard;
            }
        } else if (length(soulsRel) < %(r0).4f + (%(hi)d.0 - mark) * %(step).4f) {
            discard;
        }
        tex.a = 1.0;
    }
    vec4 color = tex * vertexColor * ColorModulator;
    if (color.a < 0.1) {
        discard;
    }
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}
""" % {"lo": MARK_HI - MARK_CLASSES + 1, "hi": MARK_HI, "r0": MARK_R0, "step": MARK_STEP}


def write_shader(out):
    folder = os.path.join(out, "assets", "minecraft", "shaders", "core")
    os.makedirs(folder, exist_ok=True)
    for ext, text in (("vsh", ITEM_VSH), ("fsh", ITEM_FSH)):
        with open(os.path.join(folder, f"rendertype_item_entity_translucent_cull.{ext}"), "w", encoding="ascii", newline="\n") as f:
            f.write(text)


# ── own 벌의 머리: 스킨 픽셀 머리 ──
# 해골 상자 (아이템 공간 (4..12, 0..8, 4..12), 얼굴 +Z) 의 여섯 면을 8×8 픽셀 사각형 384 개로 나누고 사각형마다 tintindex
# (면 차례 HEAD_FACES × 64 + 줄 × 8 + 칸) 를 준다. 아이템 정의의 tints 가 custom_model_data colors[0..383] 을 흰 바탕에 곱한다.
# 면의 픽셀 차례는 _face_grid (밖에서 볼 때 u 오른쪽, v 아래) 와 스킨의 머리 칸 (덧옷 층은 u + 32) 이다: 미리보기 head_faces 와 같고,
# 바닐라 해골과 견주어 맞췄다 [확인 (클라): /soulstest tumble ... own].
HEAD_FACES = ("south", "north", "east", "west", "up", "down")      # 플러그인 SkinTint.HEAD_FACES 와 같은 차례
HEAD_REGION = {"south": (8, 8), "north": (24, 8), "east": (16, 8), "west": (0, 8), "up": (8, 0), "down": (16, 0)}
HEAD_PIXELS = len(HEAD_FACES) * 64


def headpx_model():
    fr, to = np.array([4.0, 0.0, 4.0]), np.array([12.0, 8.0, 12.0])
    els = []
    for f, fname in enumerate(HEAD_FACES):
        origin, uax, vax, _, _ = _face_grid(fr, to, fname)
        for j in range(8):
            for i in range(8):
                a = origin + uax * i + vax * j
                b = origin + uax * (i + 1) + vax * (j + 1)
                els.append({"from": [_r(v) for v in np.minimum(a, b)], "to": [_r(v) for v in np.maximum(a, b)],
                            "faces": {fname: {"uv": [0, 0, 1, 1], "texture": "#px", "tintindex": f * 64 + j * 8 + i}}})
    return {"textures": {"px": TEX_ID["px"] + "_m", "particle": TEX_ID["px"] + "_m"}, "elements": els,
            "display": {"fixed": HEAD_FIXED}}


def head_pixels(skin):
    """스킨 (64×64 또는 64×32) → 머리 픽셀 384 색 (0xRRGGBB, HEAD_FACES 차례). 덧옷 층은 알파만큼 겹친다 (플러그인 SkinTint.head 와 같은 셈).
    skin 이 None 이면 팔레트 얼굴 (미리보기의 기본 머리)."""
    if skin is None:
        faces = _skin_faces(None)
        names = {"south": "north", "north": "south", "east": "east", "west": "west", "up": "up", "down": "down"}
        return [_int(faces[names[f]].getpixel((i, j))) for f in HEAD_FACES for j in range(8) for i in range(8)]
    a = np.array(skin.convert("RGBA")).astype(int)
    out = []
    for fname in HEAD_FACES:
        u0, v0 = HEAD_REGION[fname]
        for j in range(8):
            for i in range(8):
                b, h = a[v0 + j, u0 + i], a[v0 + j, u0 + 32 + i]
                al = h[3]
                rgb = [(int(h[c]) * al + int(b[c]) * (255 - al) + 127) // 255 for c in range(3)]
                out.append((rgb[0] << 16) | (rgb[1] << 8) | rgb[2])
    return out


# ── own 벌이 손에 든 souls 아이템: 표시한 모형 ──
# 아이템 정의 (assets/souls/items) 를 감쌀 때 (wrap_item_definitions) custom_model_data 깃발 MARK_FLAG 가 켜지면 같은 모형의 표시판
# (souls:item/<이름>_m) 으로 그린다. 표시판은 면마다 그 면의 점이 1인칭 카메라에서 가장 멀어지는 거리로 마디 k 를 골라 그 마디의 그림
# (<그림>_m<k>) 을 쓴다: 긴 무기의 날 끝은 큰 반지름, 손잡이는 작은 반지름이라 F5 카메라가 가까워도 (벽) 덜 사라진다.
# 점의 자리: 대역의 손 부위 (hand_r, hand_l) 자세 · ItemDisplay 의 Y 180° · 모형의 thirdperson_righthand (왼손은 바닐라처럼 거울) 변환.
# 두 손, 두 자세 (오른손·왼손 변환) 를 모두 본다 (왼손잡이는 거울이라 거리가 같다).
_VANILLA_DISPLAY = {   # 바닐라 부모 모형의 thirdperson_righthand (클라이언트 jar 를 못 읽을 때)
    "minecraft:item/generated": {"rotation": [0, 0, 0], "translation": [0, 3, 1], "scale": [0.55, 0.55, 0.55]},
    "minecraft:item/handheld": {"rotation": [0, -90, 55], "translation": [0, 4.0, 0.5], "scale": [0.85, 0.85, 0.85]},
}


def _ref(ref):
    ns, _, path = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
    return ns, path


class _Models:
    """팩 폴더의 souls 모형과 클라이언트 jar 의 바닐라 모형을 읽는다 (부모 사슬)."""

    def __init__(self, out):
        self.out = out
        jar = client_jar()
        self.zip = zipfile.ZipFile(jar) if jar else None

    def raw(self, ref):
        ns, path = _ref(ref)
        p = os.path.join(self.out, "assets", ns, "models", *path.split("/")) + ".json"
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        if ns == "minecraft" and self.zip is not None:
            try:
                return json.loads(self.zip.read(f"assets/minecraft/models/{path}.json"))
            except KeyError:
                return None
        return None

    def resolved(self, ref):
        """(textures, elements, display thirdperson_righthand, thirdperson_lefthand, generated 인가)."""
        tex, els, disp_r, disp_l, gen = {}, None, None, None, False
        seen = 0
        while ref and seen < 16:
            seen += 1
            if ref in ("builtin/generated", "minecraft:builtin/generated"):
                gen = True
                break
            m = self.raw(ref)
            if m is None:
                if ref in _VANILLA_DISPLAY and disp_r is None:
                    disp_r = _VANILLA_DISPLAY[ref]
                if ref in ("minecraft:item/generated", "item/generated", "minecraft:item/handheld", "item/handheld"):
                    gen = True
                break
            for k, v in m.get("textures", {}).items():
                tex.setdefault(k, v)
            if els is None and "elements" in m:
                els = m["elements"]
            d = m.get("display", {})
            if disp_r is None and "thirdperson_righthand" in d:
                disp_r = d["thirdperson_righthand"]
            if disp_l is None and "thirdperson_lefthand" in d:
                disp_l = d["thirdperson_lefthand"]
            ref = m.get("parent")
        return tex, els, disp_r, disp_l, gen

    def texture(self, ref):
        ns, path = _ref(ref)
        p = os.path.join(self.out, "assets", ns, "textures", *path.split("/")) + ".png"
        if os.path.exists(p):
            return Image.open(p).convert("RGBA")
        if ns == "minecraft" and self.zip is not None:
            try:
                return Image.open(io.BytesIO(self.zip.read(f"assets/minecraft/textures/{path}.png"))).convert("RGBA")
            except KeyError:
                return None
        return None


def _display_matrix(d, left):
    """모형의 thirdperson 변환 → (회전 행렬, 이동 (픽셀), 크기). left 면 바닐라 ItemTransform.apply 처럼 거울."""
    d = d or {"rotation": [0, 0, 0], "translation": [0, 0, 0], "scale": [1, 1, 1]}
    rx, ry, rz = (float(v) for v in d.get("rotation", [0, 0, 0]))
    tx, ty, tz = (float(v) for v in d.get("translation", [0, 0, 0]))
    s = np.array([float(v) for v in d.get("scale", [1, 1, 1])])
    if left:
        ry, rz, tx = -ry, -rz, -tx
    return _rx(rx) @ _ry(ry) @ _rz(rz), np.array([tx, ty, tz]), s


def _element_faces(els):
    """모형 요소 → [(요소 번호, 면 이름, 꼭짓점 (모형 픽셀 0..16))] (요소 회전 반영)."""
    out = []
    for n, el in enumerate(els):
        fr, to = np.array(el["from"], float), np.array(el["to"], float)
        rot = el.get("rotation")
        R, org = np.eye(3), np.zeros(3)
        if rot:
            R = {"x": _rx, "y": _ry, "z": _rz}[rot["axis"]](float(rot["angle"]))
            org = np.array(rot["origin"], float)
        for fname in el.get("faces", {}):
            o, ua, va, w, h = _face_grid(fr, to, fname)
            corners = [o, o + ua * w, o + va * h, o + ua * w + va * h, o + ua * w / 2 + va * h / 2]
            out.append((n, fname, np.array([R @ (p - org) + org for p in corners])))
    return out


def _hand_points(pts, frames_, disp_r, disp_l):
    """모형 픽셀 점 (N×3) → 모든 자세·두 손·두 변환의 D 점들 (M×3)."""
    y180 = _ry(180)
    v = pts - 8.0
    out = []
    for left in (False, True):
        d = disp_l if (left and disp_l is not None) else disp_r
        Rd, td, sd = _display_matrix(d, left and disp_l is None)
        local = (v * sd) @ Rd.T + td          # 아이템 공간 (가운데 원점, 픽셀)
        local = local @ y180.T
        for f in frames_:
            for hand in ("hand_r", "hand_l"):
                P, R = f[hand]
                out.append(P + local @ R.T)
    return np.concatenate(out)


def mark_item_model(models, ref, made, seq):
    """souls 모형 ref 의 표시판 souls:item/<이름>_m 을 쓰고 그 ref 를 돌려준다. 못 만들면 None (own 벌에서 그 아이템은 비운다)."""
    if ref in made:
        return made[ref]
    made[ref] = None
    ns, path = _ref(ref)
    m = models.raw(ref) if ns == NS else None
    if m is None:
        return None
    tex, els, disp_r, disp_l, gen = models.resolved(ref)

    def tex_ref(key):
        r = tex.get(key)
        while isinstance(r, str) and r.startswith("#"):
            r = tex.get(r[1:])
        return r
    new = json.loads(json.dumps(m))
    new_tex = dict(m.get("textures", {}))
    want = {}                                  # 표시 그림 열쇠 → (바탕 그림 ref, 마디)
    if els:
        new_els = json.loads(json.dumps(els))
        for n, fname, corners in _element_faces(els):
            k = mark_class(eye_reach(_hand_points(corners, seq, disp_r, disp_l)))
            face = new_els[n]["faces"][fname]
            key = face["texture"].lstrip("#")
            base = tex_ref(key)
            if base is None:
                return None
            want[f"{key}_m{k}"] = (base, k)
            face["texture"] = f"#{key}_m{k}"
        new["elements"] = new_els
    elif gen:
        # 그려 낸 납작한 모형 (layer0, layer1 ..): 16×16 판 전체로 한 마디
        sq = np.array([[x, y, z] for x in (0.0, 16.0) for y in (0.0, 16.0) for z in (7.5, 8.5)])
        k = mark_class(eye_reach(_hand_points(sq, seq, disp_r, disp_l)))
        for key in sorted(kk for kk in tex if kk.startswith("layer")):
            base = tex_ref(key)
            if base is None:
                return None
            want[f"{key}_m{k}"] = (base, k)
            new_tex[key] = f"#{key}_m{k}"
    else:
        return None
    for mk, (base, k) in want.items():
        img = models.texture(base)
        if img is None:
            return None
        bns, bpath = _ref(base)
        name = ("" if bns == NS else bns + "_") + bpath.split("/")[-1] + f"_m{k}"
        dst = os.path.join(models.out, "assets", NS, "textures", "item", name + ".png")
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            marked_image(img, k).save(dst)
        new_tex[mk] = f"{NS}:item/{name}"
    new["textures"] = new_tex
    leaf = path.split("/")[-1] + "_m"
    _json(os.path.join(models.out, "assets", NS, "models", "item", leaf + ".json"), new)
    made[ref] = f"{NS}:item/{leaf}"
    return made[ref]


def _mark_tree(node, models, made, seq):
    """아이템 정의의 모형 나무 → 표시판 나무 (모형 잎은 표시 모형으로, 못 만드는 잎과 특수 모형은 비운다)."""
    if isinstance(node, list):
        return [_mark_tree(x, models, made, seq) for x in node]
    if not isinstance(node, dict):
        return node
    t = node.get("type", "").replace("minecraft:", "")
    if t == "model":
        ref = mark_item_model(models, node["model"], made, seq)
        if ref is None:
            return {"type": "minecraft:empty"}
        # 물들이지 않는다: 셰이더가 물들이는 색의 낮은 비트를 반지름 code 로 읽으므로 (radius_table), 표시판은 흰 면 (code 63:
        # 표시 알파 반지름) 이어야 한다
        out = {k: v for k, v in node.items() if k != "tints"}
        out["model"] = ref
        return out
    if t == "special":
        return {"type": "minecraft:empty"}
    return {k: (_mark_tree(v, models, made, seq) if isinstance(v, (dict, list)) else v) for k, v in node.items()}


def anim_table(path, duck=None):
    """
    플러그인 자원 roll_anim.yml: 열쇠 자세마다 보낼 틱 (닿는 틱 - 보간 틱), 보간 틱, 부위마다 [x, y, z, qx, qy, qz, qw].
    그리고 1인칭 반지름 표 (radius: 자세마다 부위마다, 위 "틱마다 부위마다의 반지름") 와 옆 끝 표 (side). duck 은 기어가기 막힘의 틱
    수 (없으면 path 옆 config.yml 의 combat.roll.tumble.duck): 플러그인은 설정의 duck 이 표의 것과 다르면 반지름 표를 쓰지 않는다.
    """
    fs = frames()
    check_steps(fs)
    if duck is None:
        duck = config_duck(os.path.join(os.path.dirname(os.path.abspath(path)), "config.yml"))
    radius = radius_table(duck, fs)
    side = side_table(fs)
    lines = ["# 구르기 대역의 열쇠 자세 (pack/roll_figure.py anim_table 이 뼈대에서 셈해 쓴다. 손대지 않는다).",
             "# 자리는 대역 공간 D 의 픽셀 (원점 발밑 땅, +Y 위, +Z 구르는 쪽, +X 그 사람의 왼쪽), 회전은 사원수 x y z w.",
             "# 플러그인 (combat/Tumble) 이 구르는 쪽 Y 회전을 걸고 탑승 자리만큼 내려 tick 틱에 dur 틱 보간으로 보낸다.",
             "# hand_r, hand_l 은 든 것의 자리 (THIRDPERSON_RIGHTHAND / LEFTHAND). 오른손잡이 기준 (왼손잡이는 플러그인이 뒤집는다).",
             "# 1인칭에서 감추는 것은 팩의 표시 알파와 아이템 셰이더가 한다 (자세와 상관없이 모두에게 같은 대역).",
             f"scale: {SCALE}",
             "parts: [" + ", ".join(PARTS) + "]",
             "frames:"]
    prev = None
    for t, f in fs:
        # 처음 자세는 띄울 때 (0틱) 그대로. 다음부터는 앞 자세에 닿은 틱에 보내 이 자세에 닿을 때까지 보간한다. 다만 FIRST_SEND 틱
        # 전에는 보내지 않는다: 띄운 다음 틱 (1틱) 에 바꾸면 생성 패킷과 한 번에 나가 보간 없이 처음 자세가 바뀐다
        send = 0 if prev is None else max(prev, FIRST_SEND)
        dur = 0 if prev is None else t - send
        if prev is not None and dur < 1:
            raise ValueError(f"구르기 대역: {t}틱 자세는 {FIRST_SEND}틱 뒤에 닿아야 한다")
        rows = []
        for part in PARTS:
            P, R = f[part]
            q = quat(R)
            rows.append("[" + ", ".join(_fmt(v) for v in (*P, *q)) + "]")
        lines.append(f"  - tick: {send}")
        lines.append(f"    dur: {dur}")
        lines.append("    p:")
        lines += [f"      - {r}   # {part}" for r, part in zip(rows, PARTS)]
        prev = t
    lines += ["# 1인칭 반지름 (블록): 자세마다 (그 자세를 보낸 때부터 다음 자세를 보낼 때까지) 부위마다 (parts 차례) 그 사람 1인칭 카메라에서",
              "# 겉면이 가장 멀어지는 거리. stand 는 기어가기 막힘이 없을 때, crawl 은 막힘을 duck 틱 깔았을 때. 플러그인이 margin 과 옆으로",
              "# 옮긴 몫을 더해 code-step 으로 올림한 code 를 own 벌의 물들이는 색의 낮은 비트에 실어 보낸다 (팩의 아이템 셰이더가 읽는다).",
              "radius:",
              f"  duck: {duck}",
              f"  code-step: {CODE_STEP}",
              f"  margin: {RADIUS_MARGIN}"]
    for mode, key in (("stand", "stand"), ("duck", "crawl")):
        lines.append(f"  {key}:")
        lines += ["    - [" + ", ".join(f"{v:.3f}" for v in row) + "]" for row in radius[mode]]
    lines += ["# 옆 끝 (블록, 자세마다 [가장 오른쪽 x, 가장 왼쪽 x], 대역 공간 +X = 그 사람의 왼쪽. 그 자세로 가는 보간과 다음 보간을 덮는다)",
              "side:"]
    lines += ["  - [" + ", ".join(f"{v:.3f}" for v in row) + "]" for row in side]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def _fmt(v):
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ─────────────────────────── 모형 쓰기 ───────────────────────────

def _r(v):
    return round(float(v), 3)


# D 방향 → 아이템 공간 면 이름 (아이템 = (8 - dx, 8 + dy, 8 - dz): 앞 (+Z) 은 북, 그 사람의 왼쪽 (+X) 은 서)
_D_FACE = {"front": "north", "back": "south", "left": "west", "right": "east", "up": "up", "down": "down"}


def part_model(name):
    """부위의 아이템 모형: 상자를 아이템 공간으로 (관절 = 아이템 가운데 (8, 8, 8))."""
    els = []
    for i, sh in enumerate(SHAPES[name]):
        fr = [8 - sh.hi[0], 8 + sh.lo[1], 8 - sh.hi[2]]
        to = [8 - sh.lo[0], 8 + sh.hi[1], 8 - sh.lo[2]]
        w, h, d = (to[k] - fr[k] for k in range(3))
        sizes = {"north": (w, h), "south": (w, h), "east": (d, h), "west": (d, h), "up": (w, d), "down": (w, d)}
        seed = sum(ord(ch) * (j + 1) for j, ch in enumerate(name)) + i * 13
        faces = {}
        for k, (fname, (du, dv)) in enumerate(sizes.items()):
            # 같은 그림이 여러 부위에 같은 자리로 찍히지 않게 부위 이름으로 uv 를 비낀다
            u0 = (seed * 5 + k * 7) % max(1, int(16 - du) + 1)
            v0 = (seed * 3 + k * 11) % max(1, int(16 - dv) + 1)
            tex = "sole" if sh.sole is not None and fname == _D_FACE[sh.sole] else sh.tex
            faces[fname] = {"uv": [_r(u0), _r(v0), _r(u0 + du), _r(v0 + dv)], "texture": "#" + tex, "tintindex": sh.tint}
        els.append({"from": [_r(v) for v in fr], "to": [_r(v) for v in to], "faces": faces})
    return {"textures": {**{k: TEX_ID[k] for k in TEXTURES if k != "helm"}, "particle": TEX_ID["cloth"]}, "elements": els}


# 머리: 해골 (아이템 공간 (4..12, 0..8, 4..12), 얼굴 +Z) 을 Y 로 180° 돌려 얼굴을 앞 (-Z) 으로, 목 (해골 밑 가운데, 가운데에서 8 아래)
# 을 아이템 가운데로 올린다. 자세 회전은 아이템 가운데를 축으로, 이동은 회전 뒤에 더한다
HEAD_FIXED = {"rotation": [0.0, 180.0, 0.0], "translation": [0.0, 8.0, 0.0], "scale": [1.0, 1.0, 1.0]}


def helm_model():
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
            "display": {"fixed": HEAD_FIXED}}


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def build(out):
    assets = os.path.join(out, "assets", NS)
    check_steps()
    # 1인칭에서 감추는 반지름 (부위 묶음마다, 위 "1인칭에서 감추기")
    reach = group_reach()
    klass = {g: mark_class(r) for g, r in reach.items()}
    for k, img in TEXTURES.items():
        p = os.path.join(assets, "textures", "item", f"roll_{k}.png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        img.save(p)
        marked_image(img, klass[TEX_GROUP[k]]).save(os.path.join(assets, "textures", "item", f"roll_{k}_m.png"))
    # 픽셀 머리의 바탕: 흰 칸 (물들이는 색이 그대로 나오게. artlint 의 팔레트 검사에서 뺀다: palette.TINT_BASE)
    marked_image(Image.new("RGBA", (16, 16), (255, 255, 255, 255)), klass["head"]).save(
        os.path.join(assets, "textures", "item", "roll_px_m.png"))
    # 기본색은 낮은 비트를 비운다 (code 0: 플러그인이 색을 못 보내면 셰이더가 표시 알파 반지름으로 돌아간다, radius_table)
    tints = [{"type": "minecraft:custom_model_data", "index": i, "default": _int(c(col)) & CODE_CLEAR} for _, i, col in TINTS]
    for name in BODY_MODELS:
        model = part_model(name)
        _json(os.path.join(assets, "models", "item", f"roll_{name}.json"), model)
        _json(os.path.join(assets, "items", f"roll_{name}.json"),
              {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_{name}", "tints": tints}})
        # own 벌 (그 사람 화면) 의 표시판: 같은 모형, 표시 알파 그림
        marked = dict(model, textures={k: v + "_m" for k, v in model["textures"].items()})
        _json(os.path.join(assets, "models", "item", f"roll_{name}_m.json"), marked)
        _json(os.path.join(assets, "items", f"roll_{name}_m.json"),
              {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_{name}_m", "tints": tints}})
    # 머리 (seen 벌): 바닐라 player_head 특수 모형 (아이템의 profile 성분으로 스킨을 고른다) + 자세만 바꾼 바탕 모형
    _json(os.path.join(assets, "models", "item", "roll_head.json"),
          {"parent": "minecraft:item/template_skull", "display": {"fixed": HEAD_FIXED}})
    _json(os.path.join(assets, "items", "roll_head.json"),
          {"model": {"type": "minecraft:special", "base": f"{NS}:item/roll_head", "model": {"type": "minecraft:player_head"}}})
    # 머리 (own 벌): 스킨 픽셀 머리 (색 384 개)
    _json(os.path.join(assets, "models", "item", "roll_headpx.json"), headpx_model())
    _json(os.path.join(assets, "items", "roll_headpx.json"),
          {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_headpx",
                     "tints": [{"type": "minecraft:custom_model_data", "index": i, "default": v & CODE_CLEAR}
                               for i, v in enumerate(head_pixels(None))]}})
    helm = helm_model()
    helm_tint = [{"type": "minecraft:custom_model_data", "index": 0, "default": _int(c(HELM_DEFAULT)) & CODE_CLEAR}]
    _json(os.path.join(assets, "models", "item", "roll_helm.json"), helm)
    _json(os.path.join(assets, "items", "roll_helm.json"),
          {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_helm", "tints": helm_tint}})
    _json(os.path.join(assets, "models", "item", "roll_helm_m.json"),
          dict(helm, textures={k: v + "_m" for k, v in helm["textures"].items()}))
    _json(os.path.join(assets, "items", "roll_helm_m.json"),
          {"model": {"type": "minecraft:model", "model": f"{NS}:item/roll_helm_m", "tints": helm_tint}})
    write_shader(out)
    # 기어가기 막힘 (플러그인 Roll.CEILING): 구르는 동안 그 사람 화면에만 머리 위에 까는 라임 색유리. 블록 모형을 비워 보이지 않게 한다.
    # 바닐라 TransparentBlock 이라 3인칭 카메라가 지나간다 (방벽은 카메라를 막았다). 이 게임의 세계는 라임 색유리를 쓰지 않는다
    _json(os.path.join(out, "assets", "minecraft", "blockstates", f"{CEILING}.json"),
          {"variants": {"": {"model": f"{NS}:block/roll_ceiling"}}})
    _json(os.path.join(assets, "models", "block", "roll_ceiling.json"),
          {"textures": {"particle": f"minecraft:block/{CEILING}"}, "elements": []})
    # 급류 회전의 흰 소용돌이를 투명하게 (combat.roll.visual: spin)
    tex = os.path.join(out, "assets", "minecraft", "textures", "entity", "trident_riptide.png")
    os.makedirs(os.path.dirname(tex), exist_ok=True)
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(tex)
    return {g: (round(r, 2), klass[g], round(mark_radius(klass[g]), 2)) for g, r in reach.items()}


def _int(rgba):
    return (rgba[0] << 16) | (rgba[1] << 8) | rgba[2]


OWN = tuple(f"roll_{k}.json" for k in (*BODY_MODELS, *(m + "_m" for m in BODY_MODELS), "head", "headpx", "helm", "helm_m"))


def wrap_item_definitions(out):
    """
    assets/souls/items/*.json 을 모두 감싼다 (대역 모형 OWN 은 빼고). gen_pack 이 다른 아이템 정의를 다 쓴 뒤에 부른다.
      - custom_model_data 깃발 MARK_FLAG 가 켜지면 표시판 (own 벌이 손에 든 것: 위 "1인칭에서 감추기") 으로 그린다.
      - 아니고 깃발 HIDE_FLAG 가 켜지면 손·머리 자세 (HIDDEN_CONTEXTS) 에서 비운다 (진짜 몸이 든 것).
    돌려주는 값: (감싼 정의 수, 표시판을 만든 모형 수).
    """
    folder = os.path.join(out, "assets", NS, "items")
    models = _Models(out)
    made = {}
    seq = anim_samples()
    n = 0
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json") or name in OWN:
            continue
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        inner = data["model"]
        hide = {
            "type": "minecraft:condition", "property": "minecraft:custom_model_data", "index": HIDE_FLAG,
            "on_false": inner,
            "on_true": {"type": "minecraft:select", "property": "minecraft:display_context",
                        "cases": [{"when": HIDDEN_CONTEXTS, "model": {"type": "minecraft:empty"}}],
                        "fallback": inner},
        }
        data["model"] = {
            "type": "minecraft:condition", "property": "minecraft:custom_model_data", "index": MARK_FLAG,
            "on_false": hide,
            "on_true": _mark_tree(inner, models, made, seq),
        }
        _json(path, data)
        n += 1
    return n, sum(1 for v in made.values() if v)


# ─────────────────────────── 스킨 색 표 (기본 스킨 18 개) ───────────────────────────
# 플러그인 combat/SkinTint 와 같은 셈: 칸마다 (덧옷 층 픽셀이 불투명하면 그것이 위) 불투명 픽셀을 채널마다 8 단위로 묶어 가장
# 많은 묶음의 평균, 너무 어두우면 밝기를 MIN_VALUE 까지 (심층암 바닥과 갈리게), 물들이는 바탕이 어둡게 하는 몫을 되돌린다 (_lift).
# 칸은 그 부위를 네 옆면으로 두른 띠 (앞만 보면 노어처럼 앞섶이 열린 겉옷은 속옷 색이 나온다. 3인칭에서 보이는 것은 대개 등과
# 옆이다): 몸통 (16,20)-(40,32), 오른팔 (40,20)-(56,32) (slim 은 (40,20)-(54,32)) 의 위 6줄 = 소매, 아래 6줄 = 손,
# 오른다리 (0,20)-(16,32) 의 위 8줄 = 바지, 아래 4줄 = 신. 덧옷 층은 같은 자리에서 16 아래 (y + 16). 64×32 옛 스킨은 덧옷 없음.

REGIONS = [(16, 20, 40, 32), (40, 20, 56, 26), (40, 26, 56, 32), (0, 20, 16, 28), (0, 28, 16, 32)]
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
    return _lift(_floor((r << 16) | (g << 8) | b))


def _lift(rgb):
    """물들이는 바탕 (뼈 계열, 밝은 칸 bone2 = 0.84) 이 곱해 어두워지는 몫을 되돌린다: 채널마다 × 100/84 (255 에서 멈춘다). 스킨에서
    고른 색은 채도를 그대로 둔다 (2026-10-08 비평: 대역의 옷이 진짜 몸보다 절반쯤 어둡고 칙칙해 바뀌는 때에 튀었다). 플러그인
    SkinTint.lift 와 같은 정수 셈."""
    return sum(min(255, (((rgb >> sh) & 255) * 100 + 42) // 84) << sh for sh in (16, 8, 0))


def _floor(rgb):
    """밝기가 MIN_VALUE 보다 낮으면 끌어올린다 (정수 셈, 플러그인 SkinTint.floor 와 같은 값)."""
    r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    mx = max(r, g, b)
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
             "# heads: 그 사람 화면의 대역 (own) 이 쓰는 픽셀 머리의 색 384 개 (여섯 면 × 8×8, 덧옷 층을 겹친 색) 를 6 자리 16진수로 이은 줄",
             "skins:"]
    heads = []
    with zipfile.ZipFile(jar) as z:
        for name in DEFAULT_SKINS:
            img = Image.open(io.BytesIO(z.read(f"assets/minecraft/textures/entity/player/{name}.png")))
            cols = skin_colors(img, slim=name.startswith("slim/"))
            lines.append(f"  - [{', '.join(repr('%06x' % v) for v in cols)}]   # {name}")
            heads.append(f"  - '{''.join('%06x' % v for v in head_pixels(img))}'   # {name}")
    lines += ["heads:"] + heads
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return True


# ─────────────────────────── 미리보기 그리기 도구 ───────────────────────────
_FACE_N = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}



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



# ─────────────────────────── 미리보기 ───────────────────────────
# 부위 모형 (아이템 JSON) 을 다시 읽어 아이템 공간 → ItemDisplay 의 Y 180° → 열쇠 자세 (부위 회전, 관절 자리) 로 D 에 놓고,
# 면을 텍셀마다 작은 사각형으로 나눠 먼 것부터 그리는 정사영. 머리는 8×8×8 상자에 스킨 (없으면 팔레트 색 얼굴).
# 오른손의 든 것은 바닐라 handheld 의 thirdperson_righthand 자세로 잡은 칼 (미리보기만, 막대 하나).

def _stick(a, b, col, w=0.6):
    """a → b 막대 (네 옆면)."""
    d = b - a
    n = np.cross(d, [0.0, 1.0, 0.0])
    if np.linalg.norm(n) < 1e-6:
        n = np.cross(d, [1.0, 0.0, 0.0])
    n = n / np.linalg.norm(n) * w
    m = np.cross(d / np.linalg.norm(d), n)
    out = []
    for e1, e2 in ((n, m), (m, -n), (-n, -m), (-m, n)):
        q = [a + e1, b + e1, b + e2, a + e2]
        nn = (e1 + e2) / np.linalg.norm(e1 + e2)
        out.append((q, nn, np.array(col, float)))
    return out


# 바닐라 item/handheld 의 thirdperson_righthand: 회전 (0, -90, 55), 이동 (0, 4, 0.5), 크기 0.85. 칼 그림은 왼쪽 아래 손잡이 → 오른쪽 위 끝
_HANDHELD = (_rx(0) @ _ry(-90) @ _rz(55), np.array([0.0, 4.0, 0.5]), 0.85)


def figure_faces(frame, skin=None, colors=None, helm=None, sword=True):
    cols = colors or [c(col)[:3] for _, _, col in TINTS]
    cols = [((v >> 16) & 255, (v >> 8) & 255, v & 255) if isinstance(v, int) else tuple(v[:3]) for v in cols]
    y180 = _ry(180)
    cache = {}
    out = []

    def place(faces, P, R):
        for q, n, col in faces:
            out.append(([P + R @ (y180 @ p) for p in q], R @ (y180 @ n), col))

    for part, (P, R) in frame.items():
        if part in MODEL_OF and part != "head":
            name = MODEL_OF[part]
            if name not in cache:
                cache[name] = model_faces(part_model(name), cols)
            place(cache[name], P, R)
        elif part == "head":
            place(head_faces(HEAD_FIXED, skin), P, R)
            if helm is not None:
                hcol = [((helm >> 16) & 255, (helm >> 8) & 255, helm & 255)]
                Rf = _rx(HEAD_FIXED["rotation"][0]) @ _ry(HEAD_FIXED["rotation"][1])
                tt = np.array(HEAD_FIXED["translation"], float)
                place([([Rf @ p + tt for p in q], Rf @ n, col) for q, n, col in model_faces(helm_model(), hcol)], P, R)
        elif part == "hand_r" and sword:
            Rh, th, sh = _HANDHELD
            grip, tip = (th + Rh @ (sh * np.array(v)) for v in ((-5.0, -5.0, 0.0), (7.0, 7.0, 0.0)))
            for q, n, col in _stick(grip, tip, (150, 156, 170, 255), w=0.9):
                out.append(([P + R @ (y180 @ p) for p in q], R @ (y180 @ n), col))
    return out


# 보는 쪽: (보는 방향 (카메라 → 대역), 내려다보는 각). back = F5 등 뒤, side = 그 사람의 오른쪽에서 (구르는 쪽이 화면 오른쪽),
# front = 앞에서 (F5 두 번)
_VIEWS = {"back": ((0.0, 0.0, 1.0), 16.0), "side": ((1.0, 0.0, 0.0), 6.0), "front": ((0.0, 0.0, -1.0), 16.0)}


def render(faces, view, size=180, k=4.2, center=(0.0, 11.0, 0.0)):
    d0, elev = _VIEWS[view]
    e = math.radians(elev)
    d0, u0 = np.array(d0), np.array([0.0, 1.0, 0.0])
    d = d0 * math.cos(e) - u0 * math.sin(e)
    u = u0 * math.cos(e) + d0 * math.sin(e)
    r = np.cross(d, u)
    ctr = np.array(center)
    img = Image.new("RGBA", (size, size), (44, 41, 46, 255))
    dr = ImageDraw.Draw(img)

    def pr(p):
        v = p - ctr
        return size / 2 + (v @ r) * k, size * 0.55 - (v @ u) * k

    g = [np.array([x, 0.0, z]) for x, z in ((-40, -40), (40, -40), (40, 40), (-40, 40))]
    dr.polygon([pr(p) for p in g], fill=(34, 31, 36, 255))
    for zz in range(-40, 41, 8):
        dr.line([pr(np.array([-40.0, 0.0, zz])), pr(np.array([40.0, 0.0, zz]))], fill=(40, 37, 42, 255))
    light = np.array([0.3, 1.0, -0.4])
    light = light / np.linalg.norm(light)
    items = []
    for quad, n, col in faces:
        if col[3] < 128 or n @ d >= 0:
            continue
        b = 0.55 + 0.45 * max(0.0, float(n @ light))
        items.append((sum(p @ d for p in quad) / 4, [pr(p) for p in quad], tuple(int(v * b) for v in col[:3]) + (255,)))
    items.sort(key=lambda x: -x[0])
    for _, sc, col in items:
        dr.polygon(sc, fill=col)
    return img


def preview(path, skin=None, colors=None, mids=False, views=("back", "side", "front")):
    """열쇠 자세마다 (mids 면 사이 보간 자세도) 등 뒤·옆·앞에서. skin 이 없으면 팔레트 기본색과 그림 얼굴."""
    from mc3d import contact_sheet
    fs = frames()
    seq = []
    for i, (t, f) in enumerate(fs):
        if mids and i:
            seq.append((f"{(fs[i - 1][0] + t) / 2:g}", between(fs[i - 1][1], f, 0.5)))
        seq.append((f"{t}", f))
    imgs, labels = [], []
    for view in views:
        for lab, f in seq:
            imgs.append(render(figure_faces(f, skin, colors), view))
            labels.append(f"t{lab} {view}")
    imgs.append(render(figure_faces(fs[0][1], skin, colors, helm=0x858079), "front"))
    labels.append("helm front")
    sheet = contact_sheet(imgs, labels, cols=len(seq), cell=180)
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
    jar = client_jar()
    who = os.environ.get("SKIN", "wide/noor")
    if jar:
        skin = _skin_from_jar(jar, who)
        cols = skin_colors(skin, slim=who.startswith("slim/"))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview", "roll_figure.png")
    views = tuple(os.environ.get("VIEWS", "back side front").split())
    print(preview(out, skin, cols, mids=os.environ.get("MIDS") == "1", views=views))
    print("가장 큰 마디 회전 %.0f°" % check_steps())
