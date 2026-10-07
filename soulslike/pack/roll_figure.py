"""
구르기 대역 (DESIGN.md 3.3 "보이는 모습"). gen_pack.py 가 icons 다음에 부른다.

구르는 동안 플러그인(combat/Tumble)은 진짜 몸을 감추고(투명) 그 자리에 몸을 웅크린 대역을 띄워 앞으로 한 바퀴 돌린다.
대역은 ItemDisplay 둘이다. 둘 다 같은 변환(구르는 쪽으로 돌리고, 옆 축으로 θ)을 받아 한 덩이로 돈다.

  souls:roll_body   웅크린 몸 (복셀 모형, wkit.part). 망토 덮인 등, 접은 다리, 정강이를 감싼 두 팔, 장화, 등을 가로지른
                    멜빵과 청동 고리. 회전 중심 = 모형 (8,8,8) = 공의 가운데. 1 복셀 = 스킨 1픽셀 (1/16 블록)
  souls:roll_head   그 사람의 머리 (바닐라 player_head 특수 모형 + 이 팩의 바탕 모형 souls:item/roll_head).
                    fixed 자세 (ItemDisplay 의 FIXED) 의 translation·rotation 으로 머리를 공의 앞 위에, 얼굴을 무릎 쪽으로
                    숙여 둔다. 자세가 아이템 공간 안에서 먼저 걸리므로 대역 전체가 돌 때 머리도 같은 중심으로 돈다
                    (변환의 이동은 직선으로 보간되므로 머리를 이동으로 옮기면 90° 마디마다 안쪽으로 꺾인다)

아이템 공간의 앞은 -Z (북쪽) 다. ItemDisplay 는 아이템을 그리기 전에 Y 축으로 180° 돌려 그리므로, 플러그인 변환 공간에서는
+Z 가 앞이 된다 [확인 (클라): dist/screenshots/roll/].

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
import json
import math
import os

import numpy as np
from PIL import Image

from palette import c
from wkit import Mat, part

NS = "souls"
BODY = "item/roll_body"
HEAD = "item/roll_head"
HIDE_FLAG = 0                      # custom_model_data 깃발 번호 (플러그인 Tumble.HIDE_FLAG 와 같다)
# 3인칭 손·머리 (투명한 몸에 떠 보인다) 와 1인칭 손 (구르는 동안 무기를 거두었다가 끝나면 다시 든다: 바닐라의 바꿔 들기
# 몸짓이 구르기 시작에 내리고 끝에 올린다. 1인칭을 그대로 두면 사본이 바뀔 때마다 두 번 내렸다 올렸다)
HIDDEN_CONTEXTS = ["thirdperson_righthand", "thirdperson_lefthand", "firstperson_righthand", "firstperson_lefthand", "head"]

# 머리 놓기 (아이템 공간, 픽셀). 머리 가운데를 공의 앞 위 (위 HEAD_Y, 앞 HEAD_F) 에, 얼굴을 HEAD_PITCH 도 숙인다.
# 바닐라 해골 모형은 아이템 공간 (4..12, 0..8, 4..12) 에 그려진다: 가운데가 아이템 가운데 (8,8,8) 보다 4 아래
HEAD_Y, HEAD_F, HEAD_PITCH = 2.4, 2.8, 48.0
HEAD_SCALE = 0.88
# 해골 모형의 얼굴이 아이템 공간에서 어느 쪽을 보는가 (+1: +Z 남쪽, -1: -Z 북쪽). 앞(-Z)을 보게 Y 로 돌린다
SKULL_FACE = -1


# ─────────────────────────── 재료: 손으로 찍은 16×16 칸 ───────────────────────────

class PaintMat(Mat):
    """기호 그림 16줄 (팔레트 이름만). 복셀 면마다 이 칸의 한 픽셀을 쓴다 (1 복셀 = 1 픽셀)."""

    def __init__(self, rows, ink):
        super().__init__(["#000000"], style="flat")
        if len(rows) != 16 or any(len(r) != 16 for r in rows):
            raise ValueError("16×16 이어야 한다")
        self.rows, self.ink = rows, ink

    def cell(self, frame=0, frames=1):
        img = Image.new("RGBA", (16, 16))
        px = img.load()
        for y, row in enumerate(self.rows):
            for x, ch in enumerate(row):
                px[x, y] = c(self.ink[ch])
        return img


# 망토: 거친 모직 (중간 재색). 세로 주름 (어두운 줄) 이 고르지 않게 끊기고, 닳아 밝은 자리 몇 곳, 기운 자리 하나 (녹슨 갈색).
# 어두운 방에서도 바닥 (심층암) 과 갈리게 재 0~1 이 아니라 1~3 을 쓴다
CLOAK = PaintMat([
    "aaaabaaaaaabaaaa",
    "aaaabaaacaabaaaa",
    "aacabaaaaaaabaaa",
    "aaaabaaaaaaabaaa",
    "aaaaabaaaacabaaa",
    "aaaaabaaaaaabaaa",
    "abaaabaaaaaaabaa",
    "abaaaaaaaaaaabaa",
    "abaaaabaarraabaa",
    "aaaaaabaarraaaac",
    "aacaaabaaaaaaaaa",
    "aaaaaabaaaaabaaa",
    "aaaaaaabaaaaabaa",
    "aabaaaabaaaaabaa",
    "aabaaaaaacaaabaa",
    "aaaaaaabaaaaaaaa",
], {"a": "ash2", "b": "ash1", "c": "ash3", "r": "rust1"})

# 망토 자락·깃·두건: 망토보다 한 단 어둡고, 해진 올이 밝게 몇 점
HEM = PaintMat([
    "bbbbcbbbbbbbbbbb",
    "bbbbbbbbbcbbbbbb",
    "bcbbbbbbbbbbbdbb",
    "bbbbbbbbbbbbbbbb",
    "bbbbbbcbbbbbbbbb",
    "bbbdbbbbbbbbcbbb",
    "bbcbbbbbbbbbbbbb",
    "bbbbbbbbbbcbbbbb",
    "bbbbbcbbbbbbbdbb",
    "bbbbbbbbbbbbbbcb",
    "bcbbbbbbbbbbbbbb",
    "bbbbbbbcbbbbbbbb",
    "bbbbdbbbbbbbcbbb",
    "bbbcbbbbbbbbbbbb",
    "bbbbbbbbbcbbbbbb",
    "bbbbbbbbbbbbbbbc",
], {"b": "ash1", "c": "ash2", "d": "ash0"})

# 바지: 녹슨 갈색 천에 박음질 (세로 점선) 과 해진 무릎 (재)
CLOTH = PaintMat([
    "rrrrrrrsrrrrrrrr",
    "rrrrrrrrrrrrrrrr",
    "rrrrrrrsrrrrrqrr",
    "rrqrrrrrrrrrrrrr",
    "rrrrrrrsrrrrrrrr",
    "rrrrrrrrrrrrrrrr",
    "rrrrrrrsrrqrrrrr",
    "rrrrrrrrrrrrrrrr",
    "rrrrqrrsrrrrrrrr",
    "rrrrrrrrrrrrrrqr",
    "rrrrrrrsrrrrrrrr",
    "rqrrrrrrrrrrrrrr",
    "rrrrrrrsrrrrqrrr",
    "rrrrrrrrrrrrrrrr",
    "rrrrrrrsrrrrrrrr",
    "rrrrrqrrrrrrrrrr",
], {"r": "rust1", "s": "rust0", "q": "ash2"})

# 가죽 (장화·멜빵·끈): 주름 (어두움) 과 닳아 번들거리는 곳 (밝음)
LEATHER = PaintMat([
    "llllllmlllllllll",
    "llklllllllllllkl",
    "llllllllllmlllll",
    "lllllkllllllllll",
    "mlllllllllllklll",
    "llllllllmlllllll",
    "lllklllllllllllm",
    "llllllllllklllll",
    "lllllmllllllllll",
    "lklllllllllllkll",
    "lllllllklllmllll",
    "llllmlllllllllll",
    "llllllllllllllkl",
    "lklllllmllllllll",
    "llllllllllkllllm",
    "lllmllllllllllll",
], {"l": "rust2", "k": "rust1", "m": "rust3"})

# 장갑: 그을린 청동빛 가죽. 공의 앞에서 손이 보여야 도는 것이 읽힌다
GLOVE = PaintMat([
    "gggggggggghggggg",
    "gggjgggggggggggg",
    "gggggggghggggggg",
    "gggggjgggggggjgg",
    "ghgggggggggggggg",
    "gggggggggjgggggg",
    "gggggghggggggggg",
    "gggjggggggggghgg",
    "gggggggggggggggg",
    "ggggggjgggghgggg",
    "ghgggggggggggggg",
    "gggggggggjgggggg",
    "gggghggggggggggg",
    "gggggggggggjgggg",
    "gjgggggghggggggg",
    "gggggggggggggggg",
], {"g": "bronze2", "j": "bronze1", "h": "bronze3"})

# 발싸개: 정강이부터 발까지 감은 바랜 아마포 (순례자의 발). 공에서 가장 밝은 곳이라, 등 뒤에서 보면 발이 아래에서 나와
# 위로 넘어가는 것으로 앞구르기가 읽힌다. 감은 결 (비스듬한 어두운 줄) 과 흙때
WRAP = PaintMat([
    "wwwwvwwwwwwwwvww",
    "wwwvwwwwwxwwvwww",
    "wwvwwwwwwwwvwwww",
    "wvwwwwwwwwvwwwww",
    "vwwwwxwwwvwwwwwv",
    "wwwwwwwwvwwwwwvw",
    "wwwwwwwvwwwwwvww",
    "wwwwwwvwwwwwvwww",
    "wwxwwvwwwwwvwwww",
    "wwwwvwwwwwvwwwxw",
    "wwwvwwwwwvwwwwww",
    "wwvwwwwwvwwwwwww",
    "wvwwwwwvwwwwxwww",
    "vwwwwwvwwwwwwwwv",
    "wwwxwvwwwwwwwwvw",
    "wwwwvwwwwwwwwvww",
], {"w": "bone1", "v": "bone0", "x": "parch1"})

# 장화 밑창: 거의 검은 재에 박힌 돌가루
SOLE = PaintMat([
    "ssssssssssssssss",
    "sssstsssssssssss",
    "ssssssssssstssss",
    "ssssssssssssssss",
    "stssssssssssssss",
    "sssssssstsssssss",
    "ssssssssssssssts",
    "ssssssssssssssss",
    "sssstsssssssssss",
    "ssssssssssstssss",
    "ssssssssssssssss",
    "sstsssssssssssss",
    "ssssssssstssssss",
    "ssssssssssssssss",
    "ssssstssssssssts",
    "ssssssssssssssss",
], {"s": "rust0", "t": "ash0"})

# 등에 묶은 담요 말이: 바랜 양피지빛 모포. 둘둘 만 결 (가로 어두운 줄) 이 고르지 않다
ROLL = PaintMat([
    "pppppppppppppppp",
    "pppqppppppppqppp",
    "oooooooooooooooo",
    "pppppppppqpppppp",
    "pqpppppppppppppp",
    "pppppppppppppppp",
    "ooooooooooooooop",
    "ppppqppppppppppp",
    "pppppppppppqpppp",
    "pppppppppppppppp",
    "poooooooooooooo0",
    "pppppppppqpppppp",
    "pppqpppppppppppp",
    "pppppppppppppppp",
    "oooooooooooooooo",
    "ppppppppqppppppp",
], {"p": "parch0", "q": "parch1", "o": "rust2", "0": "ash2"})

# 청동 고리: 그을려 어둡고 테만 조금 밝다
BRONZE = PaintMat([
    "nnnnnnnnnnnnnnnn",
    "nNnnnnnnnnnnNnnn",
    "nnnnnonnnnnnnnnn",
    "nnnnnnnnnnnonnnn",
    "nonnnnnnNnnnnnnn",
    "nnnnnnnnnnnnnnon",
    "nnnNnnnnnnonnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnonnnnnNnn",
    "nNnnnnnnnnnnnnnn",
    "nnnnnonnnnnnnnnn",
    "nnnnnnnnnnNnnnon",
    "nnonnnnnnnnnnnnn",
    "nnnnnnnNnnnnnnnn",
    "nnnnnnnnnnnnonnn",
    "nnnnNnnnnnnnnnnn",
], {"n": "bronze2", "N": "bronze3", "o": "bronze1"})

MATS = {"cloak": CLOAK, "hem": HEM, "cloth": CLOTH, "leather": LEATHER, "glove": GLOVE, "sole": SOLE,
        "roll": ROLL, "bronze": BRONZE, "wrap": WRAP}


# ─────────────────────────── 모양 ───────────────────────────
# 설계 좌표 (복셀, 공 가운데 = 회전 중심 = 원점). X 오른쪽, Y 위, F 앞 (= -Z). 공 반지름은 약 8 (0.5 블록).
# 대칭 몸에 일부러 어긋남을 둔다: 왼팔이 조금 더 높이 감고, 담요 말이는 오른쪽으로 비어져 나왔고, 망토 자락 한쪽이 해졌다.

def _limb(fig, pts, rx, r, mat, steps=None, only_empty=False):
    """점들 (x, y, f) 을 잇는 굵은 선. 단면은 X 로 rx, Y·F 로 r 인 타원."""
    pts = np.array(pts, dtype=float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = float(seg.sum()) or 1.0
    n = steps or int(total * 3) + 2
    acc = np.concatenate([[0], np.cumsum(seg)])
    X, Y, F = fig._X, fig._Y, -fig._Z
    mask = np.zeros(X.shape, dtype=bool)
    for i in range(n + 1):
        d = total * i / n
        j = min(len(seg) - 1, int(np.searchsorted(acc, d, side="right") - 1))
        t = (d - acc[j]) / (seg[j] or 1)
        p = pts[j] + (pts[j + 1] - pts[j]) * t
        rr = r(i / n) if callable(r) else r
        rrx = rx(i / n) if callable(rx) else rx
        mask |= ((X - p[0]) / rrx) ** 2 + ((Y - p[1]) / rr) ** 2 + ((F - p[2]) / rr) ** 2 <= 1.0
    if only_empty:
        mask &= fig.grid == 0
    fig.grid[mask] = fig._id(mat)
    return mask


def _fill(fig, fn, mat):
    m = np.asarray(fn(fig._X, fig._Y, -fig._Z), dtype=bool)
    fig.grid[m] = fig._id(mat)
    return m


def _clear(fig, fn):
    fig.grid[np.asarray(fn(fig._X, fig._Y, -fig._Z), dtype=bool)] = 0


def _in_head(X, Y, F, pad=0.3):
    """머리 상자 안 (머리는 팩의 player_head 가 그린다)."""
    hp = math.radians(HEAD_PITCH)
    ca, sa = math.cos(hp), math.sin(hp)
    dy, df = Y - HEAD_Y, F - HEAD_F
    ly = dy * ca + df * sa
    lf = -dy * sa + df * ca
    h = 4.0 * HEAD_SCALE + pad
    return (np.abs(X) < h) & (np.abs(ly) < h) & (np.abs(lf) < h)


def body():
    fig = part(MATS, size=32, vox=1.0, seed=7)
    cid = fig._id

    # 등 (망토로 덮였다): 목덜미 (머리 뒤 위) 에서 등을 둥글게 지나 엉덩이 (뒤 아래) 까지
    arc = []
    for k in range(9):
        a = math.radians(-20 - 140 * k / 8)          # 위(0°)에서 뒤로 돌아 내려간다
        rad = 3.9 + 0.4 * math.sin(math.pi * k / 8)
        arc.append((0.0, rad * math.cos(a) - 0.2, rad * math.sin(a) - 0.6))
    _limb(fig, arc, rx=lambda t: 4.6 - 0.5 * t, r=lambda t: 2.7 + 0.3 * math.sin(math.pi * t), mat="cloak")

    # 허벅지 (엉덩이 → 무릎, 가슴 앞으로 접었다) 와 정강이 (무릎 → 발목, 아래로)
    for sx, lift in ((-1, 0.0), (1, 0.5)):
        _limb(fig, [(sx * 2.1, -3.8, -2.2), (sx * 2.2, -1.2 + lift, 2.6), (sx * 2.2, -0.2 + lift, 4.8)], rx=2.0, r=2.05, mat="cloth")
        # 정강이: 무릎 아래부터 발싸개
        _limb(fig, [(sx * 2.2, -0.4 + lift, 5.0), (sx * 2.0, -3.0, 4.7), (sx * 2.0, -4.3, 3.7)], rx=1.9, r=1.85, mat="wrap")
        # 발: 발목에서 발끝 (앞 아래), 조금 크게
        _limb(fig, [(sx * 2.05, -4.3, 2.8), (sx * 2.2, -5.5, 5.0)], rx=2.25, r=1.85, mat="wrap")
        # 무릎 바로 밑 감은 끝을 묶은 가죽끈
        _fill(fig, lambda X, Y, F, sx=sx, lift=lift: (fig.grid == cid("wrap")) & (np.abs(X - sx * 2.1) < 2.6)
              & (np.abs(Y - (-1.6 + lift * 0.5)) < 0.55) & (F > 3.5), "leather")
    # 밑창: 발의 가장 아래 두 줄
    _fill(fig, lambda X, Y, F: (fig.grid == cid("wrap")) & (Y - 0.35 * (F - 4.0) < -6.4) & (F > 1.5), "sole")

    # 팔: 어깨 → 팔꿈치 (옆) → 손목. 소매는 망토. 장갑은 정강이 앞을 감싼다. 왼팔이 조금 높다
    for sx, hy in ((-1, 0.7), (1, -0.3)):
        _limb(fig, [(sx * 4.6, 2.2, 0.0), (sx * 5.2, -0.2 + hy, 1.8), (sx * 4.3, -1.5 + hy, 4.8)], rx=1.75, r=1.75, mat="cloak")
        _limb(fig, [(sx * 3.7, -1.8 + hy, 5.6), (sx * 1.2, -2.0 + hy, 6.3)], rx=1.6, r=1.5, mat="glove")

    # 망토 자락: 엉덩이 뒤아래로 늘어진 두툼한 천. 아래 끝은 고르지 않게 해졌다
    _limb(fig, [(0.0, -5.0, -2.6), (0.0, -6.0, -0.4)], rx=4.3, r=1.6, mat="hem", only_empty=True)
    _clear(fig, lambda X, Y, F: (fig.grid == cid("hem")) & (Y < -6.8) & (X > 1.0) & (X < 3.4))
    _clear(fig, lambda X, Y, F: (fig.grid == cid("hem")) & (Y < -7.2) & (X < -2.6))

    # 두건 (벗어 내린 것): 목덜미 뒤, 머리 아래쪽을 받친다
    _limb(fig, [(-3.4, 4.6, -1.6), (0.0, 5.3, -2.6), (3.4, 4.6, -1.6)], rx=1.6, r=1.6, mat="hem")

    # 허리띠: 엉덩이 위를 두른 가죽 띠 (등뼈에 거의 수직인 판), 왼쪽 허리에 청동 고리
    _fill(fig, lambda X, Y, F: (fig.grid == cid("cloak")) & (np.abs(X) < 4.5)
          & (np.abs((Y + 3.3) * 0.55 - (F + 4.3) * 0.84) < 0.75), "leather")
    _limb(fig, [(-2.4, -3.9, -6.6), (-3.2, -3.7, -6.3)], rx=0.9, r=1.0, mat="bronze")

    # 담요 말이: 등 한가운데에 가로로 묶었다 (밝은 띠라 공이 도는 것이 등 뒤에서도 읽힌다). 오른쪽 끝이 조금 비어져 나왔다
    _limb(fig, [(-4.6, 0.9, -6.3), (5.4, 1.2, -6.1)], rx=1.7, r=1.7, mat="roll")
    for x0 in (-2.4, 2.8):   # 묶은 끈 둘
        _fill(fig, lambda X, Y, F, x0=x0: (fig.grid == cid("roll")) & (np.abs(X - x0) < 0.6), "leather")

    # 머리 자리 비우기: 머리(따로 그린다)가 몸 안으로 파묻히지 않게, 옷이 얼굴 위로 비죽 나오지 않게
    _clear(fig, _in_head)
    return fig


def head_display():
    """souls:item/roll_head 의 fixed 자세: 해골 (가운데가 아이템 가운데보다 4 아래) 을 공의 앞 위로, 얼굴을 숙여."""
    # 아이템 자세 회전 (XYZ 오일러): 먼저 얼굴을 앞(-Z)으로 (SKULL_FACE 가 +1 이면 Y 180°), 그다음 X 로 숙인다.
    # 자세의 회전은 아이템 가운데를 축으로, 이동은 회전 뒤에 더한다: 가운데 c = (0,-4,0) → t + R·c
    yaw = 180.0 if SKULL_FACE > 0 else 0.0
    pitch = -HEAD_PITCH            # 얼굴(-Z) 을 아래로: X 축으로 음의 각
    a = math.radians(pitch)
    s = HEAD_SCALE
    # R = Rx(pitch)·Ry(yaw) 를 (0, -4s, 0) 에 걸면 Ry 는 Y 축 위의 점을 바꾸지 않는다
    cy, cf = -4.0 * s * math.cos(a), -4.0 * s * math.sin(a)   # 회전된 가운데 (Y, Z 성분. Z 는 아이템 공간)
    # 목표: 아이템 공간 (0, HEAD_Y, -HEAD_F)
    tx, ty, tz = 0.0, HEAD_Y - cy, -HEAD_F - cf
    return {"rotation": [round(pitch, 3), yaw, 0], "translation": [round(tx, 3), round(ty, 3), round(tz, 3)],
            "scale": [s, s, s]}


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def build(out):
    assets = os.path.join(out, "assets", NS)
    model = body().build(BODY, assets)
    # 머리: 바닐라 player_head 특수 모형 (아이템의 profile 성분으로 스킨을 고른다) + 자세만 바꾼 바탕 모형
    _json(os.path.join(assets, "models", HEAD + ".json"), {
        "parent": "minecraft:item/template_skull",
        "display": {"fixed": head_display()},
    })
    _json(os.path.join(assets, "items", "roll_head.json"), {
        "model": {"type": "minecraft:special", "base": f"{NS}:{HEAD}", "model": {"type": "minecraft:player_head"}},
    })
    # 급류 회전의 흰 소용돌이를 투명하게 (combat.roll.visual: spin)
    tex = os.path.join(out, "assets", "minecraft", "textures", "entity", "trident_riptide.png")
    os.makedirs(os.path.dirname(tex), exist_ok=True)
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(tex)
    return model


def wrap_item_definitions(out):
    """
    assets/souls/items/*.json 을 모두 감싼다: custom_model_data 깃발 HIDE_FLAG 가 켜지면 손·머리 자세 (HIDDEN_CONTEXTS) 에서 비운다.
    대역 모형(roll_body, roll_head) 은 감싸지 않는다. gen_pack 이 다른 아이템 정의를 다 쓴 뒤에 부른다.
    """
    folder = os.path.join(out, "assets", NS, "items")
    n = 0
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json") or name in ("roll_body.json", "roll_head.json"):
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


# ─────────────────────────── 미리보기 ───────────────────────────
# 복셀 면을 하나씩 그리는 작은 정사영 그리기 (먼 면부터). 머리는 8×8×8 상자에 스킨 (없으면 팔레트 색 얼굴).
# 바닥 선은 회전 중심에서 pivot (0.5 블록 = 8 복셀) 아래. 플러그인 공간: +Z 가 구르는 쪽.

_AXES = [((1, 0, 0), "east"), ((-1, 0, 0), "west"), ((0, 1, 0), "up"), ((0, -1, 0), "down"),
         ((0, 0, 1), "south"), ((0, 0, -1), "north")]


def _skin_faces(skin):
    """머리 여섯 면 그림 (8×8). 바닐라 머리 모형과 같은 자리에서 자른다. 얼굴은 북쪽 (-Z)."""
    if skin is None:
        face = Image.new("RGBA", (8, 8), c("bone0"))
        for x in (1, 2, 5, 6):
            face.putpixel((x, 4), c("ash0"))
        for x in range(8):
            for y in (0, 1):
                face.putpixel((x, y), c("rust1"))
        hair = Image.new("RGBA", (8, 8), c("rust1"))
        return {"north": face, "south": hair, "east": hair, "west": hair, "up": hair, "down": Image.new("RGBA", (8, 8), c("bone0"))}
    reg = {"up": (8, 0), "down": (16, 0), "west": (0, 8), "north": (8, 8), "east": (16, 8), "south": (24, 8)}
    return {f: skin.crop((u, v, u + 8, v + 8)).convert("RGBA") for f, (u, v) in reg.items()}


def _faces(fig, skin):
    """(꼭짓점 4개 (아이템 공간 픽셀), 바깥 법선, 색) 목록: 몸 복셀 면과 머리 면."""
    out = []
    g = fig.grid
    occ = g > 0
    W, H, D = g.shape
    cells = {i + 1: np.array(fig.mats[n].cell()) for i, n in enumerate(fig.names)}
    for (dx, dy, dz), name in _AXES:
        nb = np.zeros_like(occ)
        src = occ[max(0, dx):W + min(0, dx), max(0, dy):H + min(0, dy), max(0, dz):D + min(0, dz)]
        nb[max(0, -dx):W - max(0, dx), max(0, -dy):H - max(0, dy), max(0, -dz):D - max(0, dz)] = src
        for i, j, k in np.argwhere(occ & ~nb):
            cx, cy, cz = i + 0.5 - fig.CX, j + 0.5 - fig.CY, k + 0.5 - fig.CZ
            u, v = {"east": (k, j), "west": (k, j), "up": (i, k), "down": (i, k), "south": (i, j), "north": (i, j)}[name]
            col = cells[g[i, j, k]][(15 - v) % 16, u % 16]
            out.append((_quad((cx, cy, cz), (dx, dy, dz)), np.array((dx, dy, dz), float), col))
    # 머리: 아이템 공간 (-4..4, -8..0, -4..4) 의 8×8×8 상자 → fixed 자세
    hm = _head_matrix()
    tex = _skin_faces(skin)
    for (dx, dy, dz), name in _AXES:
        img = np.array(tex[name])
        for a in range(8):
            for b in range(8):
                # 면 위의 칸 (a 가로, b 세로 위에서 아래로)
                if name in ("north", "south"):
                    x = (3.5 - a) if name == "north" else (a - 3.5)
                    p = (x, -0.5 - b, 4.0 * dz)
                elif name in ("east", "west"):
                    z = (a - 3.5) if name == "east" else (3.5 - a)
                    p = (4.0 * dx, -0.5 - b, z)
                else:
                    p = (a - 3.5, -4.0 + 4.0 * dy, (b - 3.5) if name == "up" else (3.5 - b))
                quad = _quad(p, (dx, dy, dz), on_surface=True)
                quad = [(hm[:3, :3] @ (np.array(q) / 16.0) + hm[:3, 3]) * 16.0 for q in quad]
                n = hm[:3, :3] @ np.array((dx, dy, dz), float)
                out.append((quad, n / np.linalg.norm(n), img[b, a]))
    return out


def _quad(center, normal, on_surface=False):
    """복셀 면 (가운데가 center 인 복셀의 normal 쪽 면, on_surface 면 center 가 이미 면 위) 의 네 꼭짓점."""
    c0 = np.array(center, float) + (0 if on_surface else 0.5) * np.array(normal, float)
    ax = [i for i in range(3) if normal[i] == 0]
    e1, e2 = np.zeros(3), np.zeros(3)
    e1[ax[0]], e2[ax[1]] = 0.5, 0.5
    return [c0 - e1 - e2, c0 + e1 - e2, c0 + e1 + e2, c0 - e1 + e2]


def _rx(deg):
    t = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])


def _ry(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])


# 보는 쪽: 화면 오른쪽, 위, 깊이 (멀수록 큼) 를 플러그인 공간 축으로
_VIEWS = {
    "back": (np.array([-1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1]), 18),    # 3인칭 등 뒤 (F5 한 번)
    "side": (np.array([0, 0, 1]), np.array([0, 1, 0]), np.array([1, 0, 0]), 0),      # 왼쪽에서 (구르는 쪽이 화면 오른쪽)
    "front": (np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, -1]), 12),   # 앞에서 (F5 두 번)
}


def render_view(faces, angle, view, size=200, k=9.0, pivot=8.0):
    right, up, depth, tilt = _VIEWS[view]
    spin = _rx(angle) @ _ry(180)                  # 아이템 공간 → 플러그인 공간 (ItemDisplay 의 Y 180°, 그다음 구르기)
    t = math.radians(tilt)                         # 카메라가 위에서 내려다본다
    up2 = up * math.cos(t) - depth * math.sin(t)
    depth2 = depth * math.cos(t) + up * math.sin(t)
    light = np.array([0.2, 1.0, -0.5])
    light = light / np.linalg.norm(light)
    img = Image.new("RGBA", (size, size), (44, 41, 46, 255))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    # 바닥 (회전 중심 아래 pivot)
    gy = size * 0.55 + (pivot * (up2 @ np.array([0, 1, 0]))) * k
    d.rectangle((0, gy, size, size), fill=(34, 31, 36, 255))
    items = []
    for quad, n, col in faces:
        nw = spin @ n
        if nw @ depth2 >= 0:
            continue
        pts = [spin @ q for q in quad]
        sc = [(size / 2 + (p @ right) * k, size * 0.55 - (p @ up2) * k) for p in pts]
        z = sum(p @ depth2 for p in pts) / 4
        b = 0.5 + 0.5 * max(0.0, float(nw @ light))
        items.append((z, sc, tuple(int(v * b) for v in col[:3]) + (255,)))
    items.sort(key=lambda x: -x[0])
    for _, sc, col in items:
        d.polygon(sc, fill=col)
    return img


def preview(path, skin=None, model=None, fig=None):
    """뒤 (F5), 옆, 앞에서 본 대역을 45° 마다. 바닥은 회전 중심에서 0.5 블록 아래."""
    from mc3d import contact_sheet
    fig = fig or body()
    faces = _faces(fig, skin)
    imgs, labels = [], []
    for view in ("back", "side", "front"):
        for deg in range(0, 360, 45):
            imgs.append(render_view(faces, deg, view))
            labels.append(f"{view} {deg}")
    sheet = contact_sheet(imgs, labels, cols=8, cell=200)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)
    return path


def _head_matrix():
    """fixed 자세를 행렬로 (블록 단위, 아이템 가운데 원점)."""
    from mc3d import _rot_matrix
    d = head_display()
    rx, ry, rz = d["rotation"]
    r = _rot_matrix("x", rx) @ _rot_matrix("y", ry) @ _rot_matrix("z", rz)
    m = np.eye(4)
    m[:3, :3] = r * d["scale"][0]
    m[:3, 3] = np.array(d["translation"]) / 16.0
    return m


if __name__ == "__main__":
    import io
    import sys
    import zipfile
    skin = None
    jar = os.environ.get("SOULS_CLIENT_JAR")
    if jar and os.path.exists(jar):
        with zipfile.ZipFile(jar) as z:
            skin = Image.open(io.BytesIO(z.read("assets/minecraft/textures/entity/player/wide/steve.png"))).convert("RGBA")
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview", "roll_figure.png")
    print(preview(out, skin))
