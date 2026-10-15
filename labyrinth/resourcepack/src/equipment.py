"""Equipment-layer textures (64×32 humanoid / humanoid_leggings) for every armour set.

Original designs per set silhouette (`sets.<id>.look`: heavy | light | cloth), coloured from the
set's chest piece (GDD §14.7).  The head region stays empty: helmets are 3D item models.

바닐라 갑옷은 몸에 1px(레깅스 0.5px) 부풀린 고정 상자라 모양은 못 바꾼다 → 그림으로 부피를 낸다:
판금 테두리의 밝은 모서리·아래로 어두워지는 둥근 면, 겹친 판(라메), 리벳·끈·버클,
팔 윗면·윗팔까지 덮는 견갑, 고르짓(목깃), 레깅스의 벨트·태싯(허리 늘어뜨림판), 두꺼운 손목·장화 커프.
경갑은 누빔 패딩 위 가죽 겹, 천옷은 어깨 망토·누빔·주름으로 넉넉하게 보이게 한다.

명암 규칙 (옆모습이 줄무늬가 되지 않게):
  · 판 아래 드리운 깊은 그림자는 정면에만 둔다. 옆·뒤·안쪽 면은 중간 어둠(≈0.3)으로 낮춘다.
  · 겹 사이는 "앞 판의 어두운 아랫단 → 다음 판의 밝은 윗테" 한 번의 단차로 읽히게 하고, 따로 검은 줄을 넣지 않는다.
  · 색은 세트 팔레트의 중간 구간(≈0.3~0.6)이 주색이다. 위쪽(≥0.75)은 1px 테·수놓은 단에만 쓴다.
  · 어깨 윗면·견갑 윗줄은 3D 어깨 장식이 덮는 자리라 돔 밝기를 낮춰 둔다 (겹쳐 보이지 않게).
  · 같은 평면에 겹치는 띠(어깨·가랑이·엉덩이)는 _seams 가 같은 색으로 맞춘다 (z-fighting 깜빡임 방지).

몸과 따로 노는 껍데기로 읽히게 (갑옷 상자는 몸에서 1px 뿐이라, 빈 텍셀 하나로도 피부가 비쳐 "몸에 그린 그림"이 된다):
  · `_cover` — 각 층이 맡은 면은 모두 불투명하게 채운다. 흉갑 = 몸통·두 팔 6면 전부(소매·아랫단 밑면까지),
    레깅스 = 허리띠 줄 + 두 다리 전부(밑면까지), 장화 = 종아리 아래 5줄 + 밑창.  디자인이 비워 둔 자리
    (경갑의 드러난 윗팔, 열린 아랫단·손목 속)는 세트 팔레트의 밑받침(사슬·누빔 갬비슨·안감)으로 메운다.
  · `_shell_rims` — 면마다 바깥 테두리 1px 를 살짝 어둡게 해 두꺼운 껍데기의 모서리처럼 보이게 한다 (발광 텍셀 제외).
  · `_seams` — 서 있을 때 같은 평면에서 겹치는 상자 면(어깨의 팔·몸통 2px, 장화 가랑이, 레깅스 엉덩이 줄)을
    실제 기하로 찾아 겹치는 텍셀을 한 색으로 맞춘다 → z-fighting 깜빡임이 없다.  그 색은 묶음의 어두운 쪽이라
    팔과 몸통 사이에 주름(그늘)이 생겨 팔이 따로 붙은 껍데기로 읽힌다 (발광 텍셀이 끼면 그 빛을 따른다).
"""
from __future__ import annotations

from PIL import Image

from .util import h2, lighten, mix

# (x, y, w, h) regions of the vanilla-compatible 64×32 humanoid armour UV layout
BODY = {'top': (20, 16, 8, 4), 'bottom': (28, 16, 8, 4), 'right': (16, 20, 4, 12), 'front': (20, 20, 8, 12),
        'left': (28, 20, 4, 12), 'back': (32, 20, 8, 12)}
ARM = {'top': (44, 16, 4, 4), 'bottom': (48, 16, 4, 4), 'outer': (40, 20, 4, 12), 'front': (44, 20, 4, 12),
       'inner': (48, 20, 4, 12), 'back': (52, 20, 4, 12)}
LEG = {'top': (4, 16, 4, 4), 'bottom': (8, 16, 4, 4), 'outer': (0, 20, 4, 12), 'front': (4, 20, 4, 12),
       'inner': (8, 20, 4, 12), 'back': (12, 20, 4, 12)}

# 면별 명암 (원통처럼: 바깥면 밝게, 몸쪽 안면 어둡게) — 게임 조명 위에 얹는 그림 속 음영
BODY_FF = {'front': 0.0, 'back': -0.03, 'left': -0.07, 'right': -0.07}
LIMB_FF = {'outer': 0.04, 'front': 0.0, 'back': -0.05, 'inner': -0.1}
# 둘레 좌표 시작 열 (면을 넘어 이어지는 주름·누빔 무늬용): 몸통 = 오른쪽→앞→왼쪽→뒤, 팔다리 = 바깥→앞→안→뒤
BODY_X0, ARM_X0, LEG_X0 = 16, 40, 0


def shade(ramp, v):
    """ramp 를 연속으로 읽되 반 칸 단위로 끊는다 (픽셀아트처럼 또렷하되 6단보다 두 배 촘촘한 명암)."""
    t = max(0.0, min(1.0, v)) * (len(ramp) - 1)
    t = round(t * 2) / 2
    k = min(int(t), len(ramp) - 2)
    return mix(ramp[k], ramp[k + 1], t - k)


def _under(name, deep, mid=0.3):
    """판 아래 그늘: 정면만 깊게, 옆·뒤·안쪽 면은 중간 어둠 (옆모습이 사다리처럼 보이지 않게)."""
    return deep if name == 'front' else mid


class Painter:
    def __init__(self, look, seed):
        self.img = Image.new('RGBA', (64, 32), (0, 0, 0, 0))
        self.px = self.img.load()
        self.look = look
        self.seed = seed & 0xFFFF

    def put(self, x, y, c):
        if 0 <= x < 64 and 0 <= y < 32:
            self.px[x, y] = (c[0], c[1], c[2], 255)

    def clear(self, x, y):
        self.px[x, y] = (0, 0, 0, 0)

    def face(self, rect, fn):
        x0, y0, w, h = rect
        for j in range(h):
            for i in range(w):
                r = fn(i, j, w, h)
                if r is None:
                    continue
                if isinstance(r, tuple) and len(r) == 2:
                    ramp, v = r
                    self.put(x0 + i, y0 + j, shade(ramp, v))
                else:
                    self.put(x0 + i, y0 + j, r)

    def faces(self, rects, make):
        for name, rect in rects.items():
            self.face(rect, make(name))


def _noise(lk, i, j, salt, amp=0.12):
    return (h2(i + salt * 13, j + salt * 7, lk.seed) - 0.5) * amp


def _ring(i, j, w, h):
    return i in (0, w - 1) or j in (0, h - 1)


def _channel(u):
    """세로 누빔 골 (갬비슨): 땀 한 줄 + 부푼 두 줄."""
    return (-0.1, 0.08, 0.02)[u % 3]


def _fold(u):
    """천 주름: 밝은 등 → 중간 → 깊은 골 (4칸 주기 = 팔다리 한 면에 골 하나)."""
    return (0.05, 0.05, 0.0, -0.12)[u % 4]


def paint_set(look, look_kind: str, seed: int, set_id: str | None = None):
    """Returns (humanoid_img, leggings_img).  set_id: sets with their own motif (SET_MOTIFS) get it painted on top
    of the look's base design (before the gap filling, so they stay gap-free like every other set)."""
    hum = Painter(look, seed)
    leg = Painter(look, seed + 1)
    kind = look_kind if look_kind in ('heavy', 'light', 'cloth') else 'heavy'
    {'heavy': _heavy, 'light': _light, 'cloth': _cloth}[kind](hum, leg, look)
    _style_touches(hum, leg, look, kind, SET_CRACK.get(set_id))
    _trims(hum, leg, look, kind, look.level)
    if set_id in SET_MOTIFS:
        SET_MOTIFS[set_id](hum, leg, look)
    _cover(hum, leg, look, kind)
    _shell_rims(hum, leg)
    _seams(hum, leg)
    return hum.img, leg.img


# ───────────────────────────── 중갑 (판금) ─────────────────────────────

def _heavy(hum: Painter, leg: Painter, lk):
    """판 하나하나를 크게: 밝은 윗테 → 아래로 어두워지는 둥근 면 → 다음 판의 밝은 윗테.
    정면에서만 판 아래 그림자를 깊게 드리워 두께를 보이고, 판 사이로 사슬이 비친다 (견갑 아래, 허벅지)."""
    M, G, O = lk.main, lk.grip, lk.orn

    def n_(i, j, salt):
        return _noise(lk, i, j, salt, 0.05)

    def rivet_or(rivets, i, j, base):
        if (i, j) in rivets:
            return O, 0.9
        if (i, j - 1) in rivets:
            return M, base - 0.2                                             # 리벳 아래 그림자
        return M, base

    def body(name):
        def fn(i, j, w, h):
            n = n_(i, j, len(name))
            if name == 'top':
                return M, 0.56 + n
            if name == 'bottom':
                return (M, 0.18) if _ring(i, j, w, h) else None              # 열린 아랫단 (두께가 보이게)
            ff = BODY_FF[name]
            front = name == 'front'
            mid = (w - 1) / 2
            dx = abs(i - mid) / mid
            if j == 0:
                return M, (0.8 if front else 0.7) + ff                       # 고르짓 테
            if j == 1:
                return M, 0.56 + ff + (0.06 if dx < 0.5 else 0)              # 고르짓 판
            if j == 2:
                return M, _under(name, 0.12, 0.34)                           # 고르짓 아래 그늘
            if j <= 7:
                v = (0.56, 0.5, 0.46, 0.42, 0.36)[j - 3] + ff + n            # 위가 밝고 아래로 둥글게 어두워짐
                if name in ('front', 'back'):
                    v += 0.08 * (1 - dx * dx) - 0.08 * dx * dx               # 불룩한 면 (가장자리 어둡게)
                if front:
                    if j <= 6 and i == 3:
                        v += 0.12                                            # 가운데 능선 (빛 받는 쪽)
                    elif j <= 6 and i == 4:
                        v -= 0.04
                    return M, v
                if name == 'back':
                    if i in (3, 4):
                        return M, v - 0.16 + (0.06 if i == 3 else 0)         # 등뼈 골
                    return rivet_or({(2, 3), (5, 3)}, i, j, v)
                if i in (1, 2) and j >= 4:                                   # 옆구리 버클 끈
                    if j == 5:
                        return O, 0.84 if i == 1 else 0.6
                    return G, 0.5 if i == 1 else 0.34
                return M, v - 0.04
            if j == 8:
                return M, _under(name, 0.1, 0.32)                            # 흉갑 아래 그늘
            if j == 9:
                return rivet_or({(2, 9), (5, 9)} if name == 'back' else set(), i, j, 0.62 + ff + n)   # 허리 라메
            if j == 10:
                return M, 0.44 + ff + n
            if front and i in (3, 4):
                return O, 0.88 if i == 3 else 0.62                           # 버클
            return G, 0.36 + n                                               # 벨트

        return fn

    hum.faces(BODY, body)

    def arm(name):
        def fn(i, j, w, h):
            n = n_(i, j, 40 + len(name))
            if name == 'top':
                # 견갑 윗면 (i=0 = 바깥 모서리, j=0 = 뒤): 3D 견갑이 덮는 자리라 돔을 낮게
                if i == 0:
                    return M, 0.66
                return M, 0.66 - 0.08 * (abs(i - 1.6) + abs(j - 1.5)) + n
            if name == 'bottom':
                return (M, 0.18) if _ring(i, j, w, h) else None              # 열린 손목 (두꺼운 관처럼)
            ff = LIMB_FF[name]
            if j == 0:
                return M, 0.7 + ff * 0.5                                     # 견갑 테
            if j <= 4:
                v = (0.64, 0.58, 0.52, 0.46)[j - 1] + ff + n                 # 견갑 한 장: 둥글게 아래로 어두워짐
                if name == 'outer' and i in (1, 2) and j <= 2:
                    v += 0.06                                                # 바깥 볼록면 하이라이트
                return M, v
            if j == 5:
                return M, _under(name, 0.1, 0.36)                            # 견갑 아래 그늘
            if j == 6:
                return M, 0.4 + ff * 0.5                                     # 사슬 소매 (평평한 중간 어둠)
            if j == 7:
                return M, 0.68 + ff                                          # 완갑 윗테
            if j in (8, 9):
                v = 0.6 + ff + n - (0.08 if j == 9 else 0)
                if name == 'outer' and i == 1:
                    v += 0.1                                                 # 완갑 능선
                return M, v
            if j == 10:
                return M, 0.6 + ff                                           # 건틀릿 커프 벌어진 테
            return M, _under(name, 0.3, 0.48) + ff                           # 커프 아랫면

        return fn

    hum.faces(ARM, arm)

    def boot(name):
        def fn(i, j, w, h):
            if name == 'top':
                return None
            if name == 'bottom':
                return G, 0.12                                               # 밑창
            if j < 7:
                return None
            n = n_(i, j, 70 + len(name))
            ff = LIMB_FF[name]
            if j == 7:
                return M, 0.76 + ff * 0.5                                    # 장화 윗테 (두껍게)
            if j == 8:
                return M, 0.62 + ff + n
            if j == 9:
                return M, _under(name, 0.2, 0.48) + ff                       # 커프 아래 그늘 (정면만 깊게)
            if j == 10:
                if name == 'front':
                    return M, 0.62 if i >= 1 else 0.5                        # 앞코 캡 (가랑이 쪽 두 열은 같은 색)
                return M, 0.5 + ff + n
            if name == 'front':
                return M, 0.46 if i >= 1 else 0.34
            return M, 0.42 + ff                                              # 밑창 테

        return fn

    hum.faces(LEG, boot)

    def belt(name):
        def fn(i, j, w, h):
            if name in ('top', 'bottom') or j < 9:
                return None
            if j == 9:
                return G, 0.56
            if j == 10:
                if name == 'front' and i in (3, 4):
                    return O, 0.88 if i == 3 else 0.62
                return G, 0.38
            return M, 0.66                                                   # 태싯 고리 (다리 0행과 같은 색)

        return fn

    leg.faces(BODY, belt)

    def legs(name):
        def fn(i, j, w, h):
            if name == 'bottom':
                return None
            if name == 'top':
                return G, 0.3
            n = n_(i, j, 100 + len(name))
            ff = LIMB_FF[name]
            if j == 0:
                return M, 0.66                                               # 태싯 윗테 = 허리 고리
            if name == 'inner':
                return M, 0.44 + ff + n - 0.02 * j                           # 안쪽: 민판
            if j <= 3:
                return M, (0.58, 0.52, 0.46)[j - 1] + ff + n                 # 태싯: 둥글게 어두워지는 면
            if j == 4:
                return M, _under(name, 0.12, 0.36)                           # 태싯 아래 그늘
            if j == 5:
                return M, 0.44 + ff                                          # 허벅지 사슬 (평평한 중간 어둠)
            if j == 6:
                if name == 'front':
                    return M, (0.54, 0.86, 0.76, 0.5)[i]                     # 무릎 덮개 돔
                if name == 'outer':
                    return M, 0.6 + n                                        # 무릎 날개
                return M, 0.46 + ff + n
            if j == 7:
                return M, _under(name, 0.24, 0.42)                           # 무릎 아래
            v = 0.54 + ff + n - 0.03 * (j - 8)
            if name == 'front' and i == 1:
                v += 0.12                                                    # 정강이 능선
            return M, v

        return fn

    leg.faces(LEG, legs)


# ───────────────────────────── 경갑 (가죽 + 누빔) ─────────────────────────────

def _light(hum: Painter, leg: Painter, lk):
    """매끈한 가죽 판 + 그 밑으로 드러나는 누빔 패딩 (옆구리·허리 치마), 두 겹 어깨 패드,
    말린 깃·팔목·접어 내린 장화 목, 떠 있는 사선 끈.  가죽은 팔레트 중간색(≈0.4)이 주색 — 어두운 세트는 어둡게."""
    M, G, O = lk.main, lk.grip, lk.orn
    strap = O if lk.level >= 2 else G
    L = lk.pal.light
    pad = [shade(M, 0.12), mix(shade(M, 0.3), L, 0.1), mix(shade(M, 0.48), L, 0.12), mix(shade(M, 0.66), L, 0.15),
           mix(shade(M, 0.84), L, 0.18)]                                     # 누빔 천: 가죽 색에 밝은 색을 살짝만

    def n_(i, j, salt):
        return _noise(lk, i, j, salt, 0.06)

    def body(name):
        def fn(i, j, w, h):
            if name == 'top':
                return M, 0.5
            if name == 'bottom':
                return (G, 0.2) if _ring(i, j, w, h) else None
            n = n_(i, j, len(name))
            ff = BODY_FF[name]
            front = name == 'front'
            u = BODY[name][0] - BODY_X0 + i
            if name in ('front', 'back') and 1 <= j <= 9:                    # 어깨→허리 사선 끈
                d = (i - j * 0.66) - (1 if front else 5)
                if abs(d) < 0.8:
                    if front and j == 5:
                        return O, 0.88                                       # 끈 버클
                    return strap, 0.86 if d < 0 else 0.66
                if 0.8 <= d < 1.6:
                    return M, _under(name, 0.14, 0.26)                       # 끈 그림자 (끈이 떠 보이게)
            if j == 0:
                return M, (0.44 if front else 0.4) + ff                      # 말린 깃 (등급 1 이상은 금속 테가 덮음)
            if j == 1:
                return M, _under(name, 0.18, 0.3)                            # 깃 아래
            if j <= 7:
                if name in ('left', 'right'):                                # 옆구리: 누빔 패딩이 드러남
                    return pad, 0.36 + _channel(u) + n
                mid = (w - 1) / 2
                dx = abs(i - mid) / mid
                grad = (0.46, 0.42, 0.4, 0.36, 0.32, 0.28) if front else (0.42, 0.4, 0.38, 0.34, 0.32, 0.28)
                v = grad[j - 2] + ff + n + 0.06 * (1 - dx * dx) - 0.08 * dx * dx
                if front and i in (3, 4) and j <= 6:                         # 앞섶 끈 엮음
                    return (G, 0.9) if (i == 3) == (j % 2 == 0) else (M, 0.22)
                if name == 'back' and i in (3, 4) and 3 <= j <= 5:           # 등: 가죽 사이로 드러난 2×3 누빔 패드
                    return pad, 0.38 + (0.04 if i == 3 else -0.02) - 0.04 * (j - 3)
                return M, v
            if j == 8:
                return M, _under(name, 0.12, 0.3)                            # 가죽 판 아래 그늘
            if j == 9:
                return G, 0.8 + ff                                           # 벨트 윗테
            if j == 10:
                if front and i in (2, 3):
                    return O, 0.88 if i == 2 else 0.62
                return G, 0.56 + n
            return pad, 0.32 + _channel(u)                                   # 누빔 치마 윗단

        return fn

    hum.faces(BODY, body)

    def arm(name):
        def fn(i, j, w, h):
            n = n_(i, j, 40 + len(name))
            if name == 'top':
                # 어깨 패드 윗면: 3D 어깨 장식이 덮는 자리라 낮게
                if i == 0:
                    return M, 0.64
                return M, 0.58 - 0.05 * (abs(i - 1.6) + abs(j - 1.5)) + n
            if name == 'bottom':
                return (G, 0.2) if _ring(i, j, w, h) else None
            ff = LIMB_FF[name]
            outer = name == 'outer'
            if j == 0:
                return M, 0.5 + ff * 0.5                                     # 어깨 패드 테
            if j == 1:
                return M, 0.42 + ff + n
            if j == 2:
                return (M, 0.4 + n) if outer else (M, _under(name, 0.16, 0.32))    # 윗겹 아랫면 / 패드 밑
            if j <= 4 and outer:
                return (M, 0.54 + n) if j == 3 else (M, 0.42)                # 아래 겹 패드
            if j < 7:
                return None                                                  # 드러난 윗팔
            if j == 7:
                return M, 0.52 + ff * 0.5                                    # 팔목 보호대 말린 테
            if j == 8:
                return M, 0.42 + ff + n
            if j in (9, 10):
                if name == 'front' and i in (1, 2):
                    return (G, 0.9) if (i - 1) == (j - 9) else (G, 0.5)      # X 끈
                return M, 0.4 + ff + n - 0.04 * (j - 9)
            return (strap, 0.5) if name in ('outer', 'front') else (G, 0.5)  # 손목 커프 (끈 버클은 바깥·앞)

        return fn

    hum.faces(ARM, arm)

    def boot(name):
        def fn(i, j, w, h):
            if name == 'top':
                return None
            if name == 'bottom':
                return G, 0.12
            if j < 7:
                return None
            n = n_(i, j, 70 + len(name))
            ff = LIMB_FF[name]
            if j == 7:
                return M, 0.7 + ff * 0.5                                     # 접어 내린 장화 목
            if j == 8:
                return M, 0.56 + ff + n
            if j == 9:
                return M, _under(name, 0.16, 0.42)                           # 접힌 단 그림자
            if j == 10:
                if name == 'front' and i == 1:
                    return O, 0.86                                           # 발등 버클
                if name in ('front', 'outer'):
                    return G, 0.78                                           # 발등 끈
                return M, 0.48 + ff + n
            if name == 'front':
                return (M, 0.56) if i >= 1 else (G, 0.3)                     # 앞코
            return M, 0.4 + ff                                               # 밑창 테

        return fn

    hum.faces(LEG, boot)

    def belt(name):
        def fn(i, j, w, h):
            if name in ('top', 'bottom') or j < 9:
                return None
            if j == 9:
                return G, 0.84
            if j == 10:
                if name == 'front' and i in (3, 4):
                    return O, 0.88 if i == 3 else 0.62
                return G, 0.6
            return pad, 0.4                                                  # 누빔 치마 윗단 (다리 0행과 같은 색)

        return fn

    leg.faces(BODY, belt)

    def legs(name):
        def fn(i, j, w, h):
            if name == 'bottom':
                return None
            if name == 'top':
                return G, 0.4
            n = n_(i, j, 100 + len(name))
            ff = LIMB_FF[name]
            u = LEG[name][0] - LEG_X0 + i
            if j == 0:
                return pad, 0.4                                              # 허리 = 치마 윗단
            if name == 'outer' and j <= 4:                                   # 허벅지 가죽 덧판
                return M, (0.6, 0.54, 0.48, 0.4)[j - 1] + (n if j < 4 else 0)
            if name == 'front' and j == 2:
                return (O, 0.88) if i == 1 else (strap, 0.84)                # 허벅지 끈
            if name == 'front' and j == 3:
                return M, 0.2
            if name == 'front' and j == 5:
                return M, (0.56, 0.8, 0.7, 0.5)[i]                           # 무릎 패드
            if name == 'front' and j == 6:
                return M, 0.44
            if j == 7 and name in ('front', 'outer'):
                return M, _under(name, 0.18, 0.34)
            return pad, 0.38 + ff + _channel(u) + n                          # 누빔 바지

        return fn

    leg.faces(LEG, legs)


# ───────────────────────────── 천옷 (로브) ─────────────────────────────

def _cloth(hum: Painter, leg: Painter, lk):
    """어깨를 덮는 망토(로브보다 한 단계 밝게 + 수놓은 단), 주름 잡혀 부푼 소매, 접어 올린 넓은 소맷부리,
    굵은 허리띠와 매듭, 주름 잡힌 치마·앞뒤로 늘어진 로브 자락.  로브 몸판(≈0.4)이 세트의 주색."""
    M, G, O = lk.main, lk.grip, lk.orn                                       # 천은 잡음 없이 주름만

    def body(name):
        def fn(i, j, w, h):
            if name == 'top':
                return M, 0.5
            if name == 'bottom':
                return (M, 0.12) if _ring(i, j, w, h) else None
            ff = BODY_FF[name]
            u = BODY[name][0] - BODY_X0 + i
            front = name == 'front'
            if j == 0:
                return O, 0.7 if front else 0.62                             # 목깃
            if front and i in (3, 4):
                return O, 0.7 + (0.14 if j % 2 == 0 else 0)                  # 수놓은 가운데 판
            if j <= 2:
                return M, 0.56 + ff + _fold(u) * 0.6 - 0.04 * (j - 1)        # 어깨 망토 (로브보다 한 단계 밝게)
            if j == 3:
                return O, 0.72 if u % 2 == 0 else 0.6                        # 망토 수놓은 단 (1px)
            if j == 4 and front:
                return M, 0.2                                                # 망토 아래 그늘 (정면만)
            if front and i == 5 and 7 <= j <= 8:
                return O, (0.86, 0.62)[j - 7]                                # 띠 매듭
            if front and i == 5 and j in (9, 10):
                return G, 0.9 - 0.14 * (j - 9)                               # 늘어진 띠 끝
            if j <= 6:
                return M, 0.48 + ff + _fold(u) - 0.04 * (j - 4)              # 가슴 주름
            if j == 7:
                return G, 0.86                                               # 허리띠 (두껍게)
            if j == 8:
                return G, 0.7
            if j == 9:
                return M, 0.46 + ff + _fold(u)                               # 치마 주름
            return O, 0.6 if j == 10 else 0.48                               # 수놓은 넓은 아랫단 (두 줄)

        return fn

    hum.faces(BODY, body)

    def arm(name):
        def fn(i, j, w, h):
            if name == 'top':
                return M, 0.54 + _fold(i + j) * 0.4                          # 3D 망토가 덮는 자리 — 망토와 같은 밝기
            if name == 'bottom':
                return (M, 0.12) if _ring(i, j, w, h) else None              # 넓은 소매 안쪽
            u = ARM[name][0] - ARM_X0 + i + 1                                # 몸쪽 열(앞 3열·뒤 0열)이 주름의 밝은 등이 되게
            ff = LIMB_FF[name]
            if j == 0:
                return M, 0.56 + ff * 0.5                                    # 어깨 위 망토 테
            if j <= 2:
                return M, 0.56 + ff + _fold(u) * 0.6 - 0.04 * (j - 1)
            if j == 3:
                return O, 0.72 if u % 2 == 0 else 0.6                        # 망토 단 (1px)
            if j == 4 and name == 'front':
                return M, 0.2                                                # 망토 아래 그늘 (정면만)
            if j <= 8:
                return M, (0.5, 0.48, 0.46, 0.44, 0.4)[j - 4] + ff + _fold(u)     # 부푼 소매 주름 (아래로 그늘)
            if j == 9:
                return M, 0.56 + ff * 0.5                                    # 접어 올린 넓은 소맷부리
            if j == 10:
                return O, 0.62                                               # 소맷부리 수놓은 단 (두 줄)
            return (M, 0.2) if name == 'front' else (O, 0.5)                 # 정면은 소매 안감 그늘

        return fn

    hum.faces(ARM, arm)

    def boot(name):
        def fn(i, j, w, h):
            if name == 'top':
                return None
            if name == 'bottom':
                return G, 0.14
            if j < 7:
                return None
            ff = LIMB_FF[name]
            if j == 7:
                return O, 0.64                                               # 신 목 띠
            if j in (8, 9):
                return M, 0.5 + ff - 0.06 * (j - 8)
            if j == 10:
                return (G, 0.8) if (i + (name == 'back')) % 3 == 0 else (M, 0.44 + ff)   # 감은 천
            if name == 'front':
                return (M, 0.5) if i >= 1 else (G, 0.28)
            return M, 0.36 + ff

        return fn

    hum.faces(LEG, boot)

    def skirt(name):
        def fn(i, j, w, h):
            if name in ('top', 'bottom') or j < 7:
                return None
            u = BODY[name][0] - BODY_X0 + i
            if j == 7:
                return O, 0.62                                               # 치마 허리 단
            if j == h - 1:
                return M, 0.46                                               # 치마 아랫단 (다리 0행과 같은 색)
            return M, 0.46 + _fold(u)

        return fn

    leg.faces(BODY, skirt)

    def legs(name):
        def fn(i, j, w, h):
            if name == 'bottom':
                return None
            if name == 'top':
                return M, 0.4
            ff = LIMB_FF[name]
            u = LEG[name][0] - LEG_X0 + i
            if j == 0:
                return M, 0.46                                               # 치마 아랫단과 겹치는 줄
            if name in ('front', 'back') and j <= 6:                         # 앞·뒤로 늘어진 로브 자락
                if j == 5:
                    return O, 0.68 if i % 2 == 0 else 0.58
                if j == 6:
                    return M, _under(name, 0.24, 0.34)
                return M, 0.52 + ff + _fold(u) - 0.03 * j
            if name == 'outer' and i == 1:
                return O, 0.62                                               # 옆선 띠
            v = 0.42 + ff + _fold(u) * 0.7
            if j == 7:
                v += 0.06                                                    # 무릎 아래 주름
            elif j == 8:
                v -= 0.06
            return M, v

        return fn

    leg.faces(LEG, legs)


# ───────────────────────────── 재질 손질 ─────────────────────────────

def _lum(c):
    return (c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11) / 255


def _style_touches(hum: Painter, leg: Painter, lk, kind, crack=None):
    """중갑 재질의 버릇: 녹(녹슨 철) · 녹청(구리) · 달아오른 틈(흑철, crack = 틈 색을 세트가 정함) · 결정 면(수정) ·
    리벳 줄(태엽) · 포자 점(뼈: 어두운 틈 텍셀 12% 를 연분홍 포자로)."""
    style = lk.style
    if kind != 'heavy' or style not in ('rusted_iron', 'copper', 'dark_iron', 'crystal', 'clockwork', 'bone'):
        return
    spore = mix(shade(lk.accent, 0.85), (255, 214, 236), 0.45)
    dark_cut = _lum(shade(lk.main, 0.16)) + 0.01                             # 이보다 어두우면 틈·그림자
    for pt, salt in ((hum, 3), (leg, 5)):
        for y in range(16, 32):
            for x in range(64):
                c = pt.px[x, y]
                if not c[3]:
                    continue
                r = h2(x * 7 + salt, y * 3, lk.seed)
                dark = _lum(c) <= dark_cut
                if style == 'rusted_iron' and (r < 0.05 or (dark and r < 0.45)):
                    pt.put(x, y, mix(c, lk.rust, 0.45))
                elif style == 'copper' and (dark or r < 0.06):
                    pt.put(x, y, mix(c, lk.patina, 0.5 if dark else 0.35))
                elif style == 'dark_iron' and dark and r < 0.55:
                    pt.put(x, y, mix(c, crack or shade(lk.accent, 0.4), 0.55))
                elif style == 'bone' and dark and r < 0.12:
                    pt.put(x, y, spore)
                elif style == 'crystal' and _lum(c) > _lum(shade(lk.main, 0.6)) and r < 0.12:
                    pt.put(x, y, shade(lk.accent, 0.85))
    if style == 'clockwork':
        rv = shade(lk.orn, 0.85)
        for name in ('front', 'back'):
            x0, y0, w, _ = BODY[name]
            for i in range(2, w - 2, 2):
                hum.put(x0 + i, y0 + 10, rv)                                 # 허리 라메 리벳 줄
        x0, y0, w, _ = ARM['outer']
        for i in (0, w - 1):
            hum.put(x0 + i, y0 + 3, rv)                                      # 견갑 리벳


GLOW_ALPHA = 252   # emissive marker (owner's pack convention; fullbright once a core shader is added)

# 등급 장식이 앉을 자리 (모양별): 가슴 보석 윗줄, 레깅스 테 줄, 빛나는 이음매 줄
GEM_ROW = {'heavy': 4, 'light': 3, 'cloth': 1}
LEG_RIM_ROW = {'heavy': 0, 'light': 3, 'cloth': 5}
GLOW_FLANK = {'heavy': (3, 7), 'light': (2, 7), 'cloth': (5, 10)}
GLOW_FOREARM = {'heavy': (8, 9), 'light': (9, 10), 'cloth': (5, 8)}
GLOW_LEG = {'heavy': (1, 3), 'light': (4, 6), 'cloth': (1, 4)}
SEAM_ROWS = {'heavy': {'body': 8, 'arm': 5, 'leg': 4, 'boot': 9},
             'light': {'body': 8, 'arm': 8, 'leg': 4, 'boot': 9},
             'cloth': {'body': 4, 'arm': 4, 'leg': 6, 'boot': 9}}


def _trims(hum: Painter, leg: Painter, lk, kind, lvl):
    """Pass-2 finish (reference look): metal trim edges, set gems and — on legendary/mythic sets —
    glowing seam lines marked with alpha 252."""
    O, A = lk.orn, lk.accent
    trim = shade(O, 0.72)
    trim_hi = shade(O, 0.9)
    trim_lo = shade(O, 0.45)
    gem_hi, gem, gem_lo = shade(A, 0.95), shade(A, 0.75), shade(A, 0.45)
    glow = lighten(shade(A, 0.85), 0.25)
    glow_core = lighten(glow, 0.5)

    def glow_px(pt: Painter, x, y, c):
        if 0 <= x < 64 and 0 <= y < 32 and pt.px[x, y][3]:
            pt.px[x, y] = (c[0], c[1], c[2], GLOW_ALPHA)

    def solid(pt: Painter, x, y, c):
        if 0 <= x < 64 and 0 <= y < 32 and pt.px[x, y][3]:
            pt.put(x, y, c)

    def row(pt: Painter, rect, j, c_even, c_odd=None):
        x0, y0, w, h = rect
        for i in range(w):
            solid(pt, x0 + i, y0 + j, c_even if (i % 2 == 0 or c_odd is None) else c_odd)

    fx, fy, fw, fh = BODY['front']
    bx, by, bw, bh = BODY['back']
    seams = SEAM_ROWS[kind]
    if lvl >= 1:
        # 목깃 테 (앞·뒤·옆) + 어깨 테 (+ 견갑 윗면 바깥 모서리) + 중갑 장화 윗테
        row(hum, BODY['front'], 0, trim_hi, trim)
        for name in ('back', 'left', 'right'):
            row(hum, BODY[name], 0, trim)
        for name in ('outer', 'front', 'back', 'inner'):
            row(hum, ARM[name], 0, trim)
        x0, y0, _, _ = ARM['top']
        for j in range(4):
            solid(hum, x0, y0 + j, trim)
        if kind == 'heavy':
            for name in ('outer', 'front', 'back', 'inner'):
                row(hum, LEG[name], 7, trim)
    if lvl >= 2:
        # 가슴 보석 2×2 + 테
        cx, gy = fx + fw // 2 - 1, fy + GEM_ROW[kind]
        for (dx, dy) in ((-1, 0), (-1, 1), (2, 0), (2, 1), (0, -1), (1, -1), (0, 2), (1, 2)):
            solid(hum, cx + dx, gy + dy, trim)
        for (dx, dy, c) in ((0, 0, gem_hi), (1, 0, gem), (0, 1, gem), (1, 1, gem_lo)):
            solid(hum, cx + dx, gy + dy, c)
        # 레깅스 테 (중갑 = 허리 고리, 경갑·천옷 = 앞·뒤 판 끝만 — 옆모습에 가로줄을 더하지 않게) + 장화 윗테
        if kind == 'heavy':
            for name in ('front', 'back', 'left', 'right'):
                row(leg, BODY[name], 11, trim)
        for name in ('front', 'outer', 'back'):
            if kind == 'heavy' or name != 'outer':
                row(leg, LEG[name], LEG_RIM_ROW[kind], trim, trim_lo if kind != 'heavy' else None)
            row(hum, LEG[name], 7, trim_hi if name == 'front' else trim)
    if lvl >= 3:
        if kind == 'heavy':
            row(hum, ARM['outer'], 4, trim_lo)                               # 견갑 아랫단 금박 (바깥면)
            x0, y0, w, h = BODY['front']
            for i in (3, 4):
                solid(hum, x0 + i, y0 + 7, trim if i == 3 else trim_lo)      # 흉갑 능선 끝 금박
        elif kind == 'light':
            for j in range(2, 7, 2):
                solid(hum, fx + 2, fy + j, trim)                             # 박음질을 금실로
                solid(hum, fx + fw - 3, fy + j, trim)
            row(hum, ARM['outer'], 7, trim_lo)                               # 팔목 보호대 금테 (바깥면)
        else:
            for name in ('front', 'back'):
                x0, y0, w, h = BODY[name]
                for i in range(2, w - 1, 3):
                    solid(hum, x0 + i, y0 + 3, gem)                          # 망토 단 보석 점
            for name in ('outer', 'front', 'back'):
                x0, y0, w, h = ARM[name]
                solid(hum, x0 + 1, y0 + 3, gem)
    if lvl >= 4:
        # 빛나는 이음매 — 판 아래 그늘 줄은 가운데 두 칸만 빛내고 나머지는 어둡게 둔다
        for name in ('front', 'back'):
            x0, y0, w, h = BODY[name]
            for i in (3, 4):
                glow_px(hum, x0 + i, y0 + seams['body'], glow)
        j0, j1 = GLOW_FLANK[kind]
        for j in range(j0, j1 + 1):
            if kind != 'cloth' or j not in (7, 8):
                glow_px(hum, fx + 2, fy + j, glow)                           # 가슴 옆선 (팔과 겹치는 바깥 두 열은 피함)
                glow_px(hum, fx + fw - 3, fy + j, glow)
            glow_px(hum, bx + bw // 2 - 1 + (j % 2), by + j, glow)           # 등줄기 지그재그
        glow_px(hum, fx + fw // 2 - 1, fy + GEM_ROW[kind], glow_core)
        x0, y0, w, h = ARM['outer']
        for i in (1, 2):
            glow_px(hum, x0 + i, y0 + seams['arm'], glow)
        a0, a1 = GLOW_FOREARM[kind]
        for j in range(a0, a1 + 1):
            glow_px(hum, x0 + 1, y0 + j, glow)                               # 팔 바깥 룬 줄
        l0, l1 = GLOW_LEG[kind]
        for name in ('front', 'outer'):
            x0, y0, w, h = LEG[name]
            for j in range(l0, l1 + 1):
                glow_px(leg, x0 + (1 if name == 'front' else 2), y0 + j, glow)
            for i in (1, 2):
                glow_px(hum, x0 + i, y0 + seams['boot'], glow)
    if lvl >= 5:
        # mythic: rune dots ringing the chest + shoulder sigils
        for (dx, dy) in ((2, 8), (5, 8), (3, 10), (4, 10)):
            glow_px(hum, fx + dx, fy + dy, glow_core)
        x0, y0, w, h = ARM['outer']
        for (dx, dy) in ((1, 1), (2, 1), (1, 2), (2, 2)):
            glow_px(hum, x0 + dx, y0 + dy, glow_core)


# ───────────────────────────── 세트 무늬 (0.3.5 새 세트, gear_spec §10) ─────────────────────────────
# 모양(heavy·light·cloth)의 바탕 위에 세트마다 한두 가지 무늬만 얹는다. 등급 보석(가슴 가운데)은 피해서 그린다.
# 몸통 앞·뒤의 바깥 두 열(0·1·6·7)은 서 있을 때 팔 상자와 같은 평면이라 _seams 가 한 색으로 덮는다 → 무늬는 2~5열에.
# 무늬는 _cover 앞이라 빈칸이 생겨도 밑받침이 메운다(피부가 비치지 않음 — validate 가 확인).

def _px(pt: Painter, rects, face, i, j, c):
    x0, y0, w, h = rects[face]
    if 0 <= i < w and 0 <= j < h:
        pt.put(x0 + i, y0 + j, c)


def _tint(pt: Painter, rects, face, i, j, c, k):
    x0, y0, w, h = rects[face]
    if 0 <= i < w and 0 <= j < h:
        old = pt.px[x0 + i, y0 + j]
        if old[3]:
            pt.px[x0 + i, y0 + j] = mix(old, c, k)[:3] + (old[3],)


def _gem_box(lk, kind):
    """가슴 보석 자리 (등급 2 이상): front 의 (i0, j0, i1, j1) 또는 None."""
    if lk.level < 2:
        return None
    gy = GEM_ROW[kind]
    return (2, gy - 1, 5, gy + 2)


def _free(box, i, j):
    return box is None or not (box[0] <= i <= box[2] and box[1] <= j <= box[3])


def _motif_mycel_carapace(hum: Painter, leg: Painter, lk):
    """균사 갑각 (판금): 흉갑 앞뒤를 갑충 등딱지처럼 마디로 나누고 이음매에 흰 균사 실(점선),
    견갑은 버섯 갓(분홍빛 갓 + 아랫단 주름), 각반 무릎에 갓 주름."""
    M, A = lk.main, lk.accent
    seam = shade(M, 0.12)
    thread = mix(shade(M, 0.95), (255, 244, 250), 0.6)
    cap = mix(shade(A, 0.6), (236, 170, 214), 0.3)
    gem = _gem_box(lk, 'heavy')
    for name, rows in (('front', (7,)), ('back', (4, 7))):                     # 등딱지 마디 이음매
        for j in rows:
            for i in range(2, 6):
                if name == 'back' or _free(gem, i, j):
                    _px(hum, BODY, name, i, j, thread if (i + j) % 2 else seam)
    for j in (5, 6):                                                             # 등: 가운데 균사 띠
        _px(hum, BODY, 'back', 3, j, thread)
    for name in ('outer', 'front', 'back', 'inner'):
        for i in range(4):
            for j in range(3):
                _tint(hum, ARM, name, i, j, cap, 0.38)
            _px(hum, ARM, name, i, 3, thread if i % 2 == 0 else seam)           # 갓 아래 주름
    for (i, j) in ((1, 1), (2, 2), (0, 2)):
        _px(hum, ARM, 'top', i, j, thread)                                      # 갓 윗면 포자 점
    for name in ('front', 'outer'):
        for i in range(4):
            _tint(leg, LEG, name, i, 4, cap, 0.45)
            _px(leg, LEG, name, i, 5, thread if i % 2 else seam)                # 무릎 갓 주름


def _motif_sluice_diver(hum: Painter, leg: Painter, lk):
    """수로 잠수부 (가죽): 조끼 앞판 가로 호흡관 끈 3줄 + 구리 버클 2개, 등에 둥근 공기통 자국,
    장화 앞코 물갈퀴(어두운 청록), 앞면에만 밝은 물방울 점."""
    M, G = lk.main, lk.grip
    strap, strap_hi = shade(G, 0.24), shade(G, 0.42)
    copper = mix(shade(lk.orn, 0.75), (196, 120, 60), 0.55)
    teal = mix(shade(M, 0.2), (20, 86, 92), 0.55)
    drop = mix(lk.pal.light, (255, 255, 255), 0.5)
    gem = _gem_box(lk, 'light')
    for j in ((2, 6, 8) if gem is None else (6, 8)):                             # 호흡관 끈 (+ 벨트 = 세 줄)
        for i in range(8):
            _px(hum, BODY, 'front', i, j, strap if (i + j) % 3 else strap_hi)
    for (i, j) in ((2, 6), (5, 8)):
        _px(hum, BODY, 'front', i, j, copper)
    for j in range(12):                                                          # 등: 둥근 공기통 자국
        for i in range(8):
            d = ((i - 3.5) ** 2 + ((j - 5.0) * 0.85) ** 2) ** 0.5
            if abs(d - 1.9) < 0.6:
                _px(hum, BODY, 'back', i, j, shade(M, 0.16) if i + j > 8 else shade(M, 0.66))
    _px(hum, BODY, 'back', 3, 2, copper)                                         # 밸브
    _px(hum, BODY, 'back', 4, 2, copper)
    for name in ('front',):                                                      # 장화 앞코 물갈퀴 3갈래
        for i in range(4):
            _px(hum, LEG, name, i, 11, teal)
            _px(hum, LEG, name, i, 10, teal if i in (0, 3) else shade(M, 0.36))
    _px(hum, LEG, 'bottom', 1, 0, teal)
    _px(hum, LEG, 'bottom', 2, 0, teal)
    for (i, j) in ((2, 7), (5, 7), (3, 1)):                                      # 물방울 (앞면만)
        if _free(gem, i, j):
            _px(hum, BODY, 'front', i, j, drop)


def _motif_cinder_cantor(hum: Painter, leg: Painter, lk):
    """잿불 성가자 (천): 성가복 아랫단 3px 를 숯빛으로 그을리고 그 윗줄에 불티 4개(발광 아님),
    가슴에 금색 악보 줄, 소매 끝은 그을음 그라데이션."""
    soot = (22, 15, 12)
    ember = (255, 150, 52)
    gold, gold_lo = shade(lk.orn, 0.82), shade(lk.orn, 0.5)
    for name in ('front', 'back', 'left', 'right'):
        w = BODY[name][2]
        for j, k in ((9, 0.25), (10, 0.42), (11, 0.6)):
            for i in range(w):
                _tint(hum, BODY, name, i, j, soot, k)
    for name in ('front', 'back'):
        for i in (2, 5):
            _px(hum, BODY, name, i, 9, ember)
    for j in (4, 5, 6):                                                          # 악보 줄: 앞 (가운데 수놓은 판 양옆)·등
        for i in (2, 5):
            _px(hum, BODY, 'front', i, j, gold if j != 5 else gold_lo)
        for i in range(2, 6):
            _px(hum, BODY, 'back', i, j, gold if j != 5 else gold_lo)
    for (i, j) in ((3, 5), (5, 4)):                                              # 음표
        _px(hum, BODY, 'back', i, j, shade(lk.main, 0.1))
    for name in ('outer', 'front', 'back', 'inner'):
        for j, k in ((9, 0.2), (10, 0.36), (11, 0.52)):
            for i in range(4):
                _tint(hum, ARM, name, i, j, soot, k)


def _fur(pt: Painter, rects, faces, j_edge, j_in, c1, c2):
    """2px 털 테두리: 바깥 줄은 꽉, 안쪽 줄은 지그재그 (밝은 두 색 번갈아)."""
    for name in faces:
        w = rects[name][2]
        for i in range(w):
            _px(pt, rects, name, i, j_edge, c1 if i % 2 else c2)
            if i % 2 == 0:
                _px(pt, rects, name, i, j_in, c2 if i % 4 else c1)


def _motif_rime_stalker(hum: Painter, leg: Painter, lk):
    """서리 추적자 (가죽): 목깃·아랫단·소매·장화 목에 흰 털 테두리(지그재그), 등에 늑대 발자국 3개(어두운 청색).
    앞판 사선 가죽끈은 가죽 모양의 바탕 끈이 이미 있다."""
    L = lk.pal.light
    f1, f2 = mix(L, (255, 255, 255), 0.6), mix(L, (214, 230, 244), 0.35)
    paw = mix(shade(lk.main, 0.12), (24, 40, 92), 0.5)
    body = ('front', 'back', 'left', 'right')
    _fur(hum, BODY, body, 0, 1, f1, f2)
    _fur(hum, BODY, body, 11, 10, f1, f2)
    _fur(hum, ARM, ('outer', 'front', 'back', 'inner'), 11, 10, f1, f2)
    _fur(hum, LEG, ('outer', 'front', 'back', 'inner'), 7, 8, f1, f2)           # 장화 털 커프
    for (x, y) in ((2, 2), (3, 5), (2, 8)):
        for (i, j) in ((0, 0), (2, 0), (1, 1), (1, 2)):
            _px(hum, BODY, 'back', x + i, y + j, paw)


def _motif_index_bulwark(hum: Painter, leg: Painter, lk):
    """색인 방벽 (판금, 흑철): 흉갑 앞판을 책 표지처럼 금 테두리 1px, 등판에 색인 룬 글자(3×5 RUNES),
    견갑 아래 책 띠(가죽색 2px). 흑철 틈은 달아오른 빛 대신 남색 (SET_CRACK)."""
    gold, gold_hi = shade(lk.orn, 0.7), shade(lk.orn, 0.92)
    for j in range(2, 10):                                                       # 책 표지 금 테 (보석 = 걸쇠)
        for i in range(2, 6):
            if i in (2, 5) or j in (2, 9):
                _px(hum, BODY, 'front', i, j, gold_hi if j == 2 else gold)
    from .materials import rune_bit
    for gi, x0, y0 in ((2, 2, 2), (5, 3, 7)):                                   # 등판 색인 번호
        for yy in range(5):
            for xx in range(3):
                if rune_bit(gi, xx, yy):
                    _px(hum, BODY, 'back', x0 + xx, y0 + yy, gold)
    strap, strap_hi = shade(lk.grip, 0.38), shade(lk.grip, 0.6)
    for name in ('outer', 'front', 'back', 'inner'):
        for i in range(4):
            _px(hum, ARM, name, i, 4, strap_hi)
            _px(hum, ARM, name, i, 5, strap)


def _motif_clock_astrologer(hum: Painter, leg: Painter, lk):
    """태엽 점성술사 (천, 비단): 예복 앞뒤에 별자리 점(밝은 금)과 잇는 선(어두운 금), 허리띠에 톱니 단추 3개,
    소매 끝에 시계 눈금 줄. 전설이 아니라 발광 없음."""
    star, line = mix(shade(lk.orn, 0.95), (255, 250, 220), 0.4), shade(lk.orn, 0.42)
    for name, stars, lines in (('front', ((2, 4), (5, 6), (2, 9)), ((2, 5), (5, 5))),
                               ('back', ((2, 1), (3, 5), (5, 2), (5, 6), (4, 4)), ((2, 2), (3, 4), (5, 3), (5, 5)))):
        for (i, j) in lines:
            _px(hum, BODY, name, i, j, line)
        for (i, j) in stars:
            _px(hum, BODY, name, i, j, star)
    for i in (2, 5):
        _px(hum, BODY, 'front', i, 7, shade(lk.orn, 0.9))                       # 톱니 단추
        _px(hum, BODY, 'front', i, 8, shade(lk.orn, 0.55))
    _px(hum, BODY, 'back', 3, 7, shade(lk.orn, 0.9))
    for name in ('outer', 'front', 'back', 'inner'):
        for i in range(4):
            _px(hum, ARM, name, i, 10, shade(lk.orn, 0.85) if i % 2 == 0 else shade(lk.main, 0.18))


SET_MOTIFS = {
    'mycel_carapace': _motif_mycel_carapace, 'sluice_diver': _motif_sluice_diver,
    'cinder_cantor': _motif_cinder_cantor, 'rime_stalker': _motif_rime_stalker,
    'index_bulwark': _motif_index_bulwark, 'clock_astrologer': _motif_clock_astrologer,
}
SET_CRACK = {'index_bulwark': (30, 44, 96)}     # 흑철 틈 색 (기본 = 세트 강조색의 달아오른 빛)


# ───────────────────────────── 껍데기: 빈틈 채우기 · 테두리 · 겹치는 면 ─────────────────────────────

BOOT_ROW = 7                                        # 장화는 다리 상자의 7~11행 (위는 레깅스가 보이게 비워 둠)
BAND_ROW = {'heavy': 9, 'light': 9, 'cloth': 7}     # 레깅스 몸통의 허리띠 줄 (그 위는 흉갑 자리라 비움)


def coverage_regions(kind):
    """{(layer, part, face): first_row} — 이 층이 불투명하게 덮어야 하는 면 (layer 'hum' | 'leg')."""
    out = {}
    for f in BODY:
        out[('hum', 'body', f)] = 0
    for f in ARM:
        out[('hum', 'arm', f)] = 0
    for f in ('outer', 'front', 'inner', 'back'):
        out[('hum', 'boot', f)] = BOOT_ROW
    out[('hum', 'boot', 'bottom')] = 0
    for f in ('front', 'back', 'left', 'right'):
        out[('leg', 'body', f)] = BAND_ROW[kind]
    out[('leg', 'body', 'bottom')] = 0
    for f in LEG:
        out[('leg', 'leg', f)] = 0
    return out


def _rect(part, face):
    return {'body': BODY, 'arm': ARM, 'boot': LEG, 'leg': LEG}[part][face]


def _mail_under(lk, i, j, base):
    """사슬 밑받침: 엇갈린 고리 무늬 (판 아래·장갑 속에서만 보이는 어두운 층)."""
    return lk.main, base + (0.08 if (i + j % 2) % 2 == 0 else -0.04)


def _pad_ramp(lk):
    """경갑 누빔 천 (가죽 색을 팔레트 밝은 색 쪽으로) — `_light` 의 패딩과 같은 계열."""
    M, L = lk.main, lk.pal.light
    return [shade(M, 0.12), mix(shade(M, 0.3), L, 0.1), mix(shade(M, 0.48), L, 0.12), mix(shade(M, 0.66), L, 0.15),
            mix(shade(M, 0.84), L, 0.18)]


def _underlayer(lk, kind, layer, part, face, i, j, w, h):
    """디자인이 비워 둔 텍셀을 메우는 밑받침 (세트 팔레트) → (ramp, v)."""
    M, G = lk.main, lk.grip
    n = _noise(lk, i, j, 7 + len(face), 0.05)
    rim = _ring(i, j, w, h)
    if face in ('bottom', 'top'):
        if part == 'arm':                                                    # 손목 속: 장갑 / 소매 안감
            return (G, 0.34 if rim else 0.22) if kind != 'cloth' else (M, 0.16 if rim else 0.1)
        if part == 'body' and layer == 'hum':                                # 흉갑 아랫단 속: 갬비슨 치마 / 안감
            if kind == 'heavy':
                return _mail_under(lk, i, j, 0.18)
            if kind == 'light':
                return _pad_ramp(lk), 0.26 + _channel(i)
            return M, 0.12
        if part == 'body':                                                   # 레깅스 가랑이 밑
            return G, 0.26 if rim else 0.16
        return (G, 0.3) if rim else (G, 0.14)                                # 바짓단 / 밑창 속
    if kind == 'heavy':
        return _mail_under(lk, i, j, 0.26)
    if kind == 'light':
        x0 = _rect(part, face)[0]
        u = x0 - (ARM_X0 if part == 'arm' else LEG_X0 if part in ('leg', 'boot') else BODY_X0) + i
        ff = (LIMB_FF if part != 'body' else BODY_FF).get(face, 0.0)
        top = 0.1 if (part == 'arm' and j == 3 and face != 'outer') else 0     # 어깨 패드 바로 밑은 그늘
        return _pad_ramp(lk), 0.32 + ff + _channel(u) + n - top              # 누빔 갬비슨 소매 (가죽보다 한 단 어둡게)
    return M, 0.46 + _fold(i) - 0.04 * (j % 4)                               # 로브 천


def _cover(hum: Painter, leg: Painter, lk, kind):
    """맡은 면의 빈 텍셀을 모두 밑받침으로 채운다 (피부가 어느 각도에서도 비치지 않게)."""
    for (layer, part, face), row0 in coverage_regions(kind).items():
        pt = hum if layer == 'hum' else leg
        x0, y0, w, h = _rect(part, face)
        for j in range(row0, h):
            for i in range(w):
                if pt.px[x0 + i, y0 + j][3]:
                    continue
                ramp, v = _underlayer(lk, kind, layer, part, face, i, j, w, h)
                pt.put(x0 + i, y0 + j, shade(ramp, v))


def _dim(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k), c[3])


def _shell_rims(hum: Painter, leg: Painter):
    """면 바깥 테두리 1px 를 살짝 어둡게 — 옆면은 좌우·아랫단, 윗단은 조금만 (판의 밝은 테는 살린다)."""
    for (layer, part, face), row0 in coverage_regions('heavy').items():
        if layer == 'leg' and part == 'body' and face != 'bottom':
            continue                                                         # 허리띠 줄은 흉갑 속 — 손대지 않음
        pt = hum if layer == 'hum' else leg
        x0, y0, w, h = _rect(part, face)
        flat = face in ('top', 'bottom')
        for j in range(row0, h):
            for i in range(w):
                c = pt.px[x0 + i, y0 + j]
                if c[3] != 255:
                    continue                                                 # 빈칸·발광(252) 텍셀은 그대로
                if flat:
                    k = 0.86 if _ring(i, j, w, h) else 1.0
                else:
                    k = 1.0
                    if i in (0, w - 1):
                        k = 0.86
                    if j == h - 1:
                        k = min(k, 0.82)
                    elif j == 0 and row0 == 0:
                        k = min(k, 0.93)
                if k < 1.0:
                    pt.px[x0 + i, y0 + j] = _dim(c, k)


# 서 있을 때의 바닐라 갑옷 상자 (월드 px, +X = 왼쪽, +Z = 앞): (layer, part, lo, hi, mirror)
_BOXES = (
    ('hum', 'body', (-5, 11, -3), (5, 25, 3), False),
    ('hum', 'arm', (-9, 11, -3), (-3, 25, 3), False),
    ('hum', 'arm', (3, 11, -3), (9, 25, 3), True),
    ('hum', 'boot', (-4.9, -1, -3), (1.1, 13, 3), False),
    ('hum', 'boot', (-1.1, -1, -3), (4.9, 13, 3), True),
    ('leg', 'body', (-4.5, 11.5, -2.5), (4.5, 24.5, 2.5), False),
    ('leg', 'leg', (-4.4, -0.5, -2.5), (0.6, 12.5, 2.5), False),
    ('leg', 'leg', (-0.6, -0.5, -2.5), (4.4, 12.5, 2.5), True),
)
# 월드 면 → (축, +쪽?, 몸통 면 이름, 팔다리 면 이름(오른쪽 기준))
_WFACE = {'west': (0, False, 'right', 'outer'), 'east': (0, True, 'left', 'inner'),
          'down': (1, False, 'bottom', 'bottom'), 'up': (1, True, 'top', 'top'),
          'north': (2, False, 'back', 'back'), 'south': (2, True, 'front', 'front')}
_SEAM_PRIO = {('hum', 'arm'): 0, ('hum', 'boot'): 1, ('leg', 'leg'): 2, ('hum', 'body'): 3, ('leg', 'body'): 4}


def _texel(box, wface, p):
    """월드 점 p 가 box 의 wface 면에서 찍는 텍셀 (layer, x, y) — 바닐라 UV 방향 (왼쪽 팔다리는 좌우 반전)."""
    layer, part, lo, hi, mirror = box
    ax, side, bname, lname = _WFACE[wface]
    if mirror and wface in ('west', 'east'):
        lname = 'inner' if wface == 'west' else 'outer'
    face = bname if part == 'body' else lname
    x0, y0, w, h = _rect(part, face)
    fx = (p[0] - lo[0]) / (hi[0] - lo[0])
    fy = (hi[1] - p[1]) / (hi[1] - lo[1])
    fz = (p[2] - lo[2]) / (hi[2] - lo[2])
    s, t = {'south': (fx, fy), 'north': (1 - fx, fy), 'west': (fz, fy), 'east': (1 - fz, fy), 'up': (fx, fz),
            'down': (fx, 1 - fz)}[wface]
    if mirror:
        s = 1 - s
    return layer, x0 + min(w - 1, int(s * w)), y0 + min(h - 1, int(t * h)), (abs(s - 0.5) + abs(t - 0.5))


def _seams(hum: Painter, leg: Painter):
    """서 있을 때 같은 평면·같은 방향으로 겹치는 상자 면을 찾아, 겹치는 텍셀 묶음을 한 색으로 맞춘다."""
    px = {'hum': hum.px, 'leg': leg.px}
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    info = {}
    for ia in range(len(_BOXES)):
        for ib in range(ia + 1, len(_BOXES)):
            A, B = _BOXES[ia], _BOXES[ib]
            for wf, (ax, side, _b, _l) in _WFACE.items():
                pa = A[3][ax] if side else A[2][ax]
                pb = B[3][ax] if side else B[2][ax]
                if abs(pa - pb) > 1e-6:
                    continue
                o = [a for a in range(3) if a != ax]
                r = [(max(A[2][a], B[2][a]), min(A[3][a], B[3][a])) for a in o]
                if any(hi - lo <= 1e-6 for lo, hi in r):
                    continue
                n0 = max(1, int((r[0][1] - r[0][0]) / 0.2))
                n1 = max(1, int((r[1][1] - r[1][0]) / 0.2))
                for u in range(n0):
                    for v in range(n1):
                        p = [0.0, 0.0, 0.0]
                        p[ax] = pa
                        p[o[0]] = r[0][0] + (u + 0.5) * (r[0][1] - r[0][0]) / n0
                        p[o[1]] = r[1][0] + (v + 0.5) * (r[1][1] - r[1][0]) / n1
                        ta, tb = _texel(A, wf, p), _texel(B, wf, p)
                        ka, kb = ta[:3], tb[:3]
                        if not px[ka[0]][ka[1], ka[2]][3] or not px[kb[0]][kb[1], kb[2]][3]:
                            continue                                         # 한쪽이 비면 겹쳐 싸우지 않는다
                        info[ka] = min(info.get(ka, (9, 9)), (_SEAM_PRIO[(A[0], A[1])], ta[3]))
                        info[kb] = min(info.get(kb, (9, 9)), (_SEAM_PRIO[(B[0], B[1])], tb[3]))
                        parent[find(ka)] = find(kb)
    groups = {}
    for k in info:
        groups.setdefault(find(k), []).append(k)
    for members in groups.values():
        if len(members) < 2:
            continue
        glow = [k for k in members if px[k[0]][k[1], k[2]][3] == GLOW_ALPHA]
        if glow:
            pick = min(glow, key=lambda k: info[k])                          # 발광 텍셀이 끼면 그 빛을 따른다
        else:                                                                # 아니면 어두운 쪽(30%) 색 = 팔·몸통 사이 주름
            order = sorted(members, key=lambda k: (_lum(px[k[0]][k[1], k[2]]), info[k]))
            pick = order[int(0.3 * (len(order) - 1))]
        c = px[pick[0]][pick[1], pick[2]]
        for k in members:
            px[k[0]][k[1], k[2]] = c
