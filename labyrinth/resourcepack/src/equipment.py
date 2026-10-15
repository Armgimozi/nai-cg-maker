"""Equipment-layer textures (64×32 humanoid / humanoid_leggings) for every armour set.

Original designs per set silhouette (`sets.<id>.look`: heavy | light | cloth), coloured from the
set's chest piece (GDD §14.7).  The head region stays empty: helmets are 3D item models.

바닐라 갑옷은 몸에 1px(레깅스 0.5px) 부풀린 고정 상자라 모양은 못 바꾼다 → 그림으로 부피를 낸다:
판금 테두리의 밝은 모서리·어두운 아랫면, 겹친 판(라메), 판 아래 드리운 그림자, 리벳·끈·버클,
팔 윗면·윗팔까지 덮는 견갑, 고르짓(목깃), 레깅스의 벨트·태싯(허리 늘어뜨림판), 두꺼운 손목·장화 커프.
경갑은 누빔 패딩 위 가죽 겹, 천옷은 어깨 망토·누빔·주름으로 넉넉하게 보이게 한다.
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
LIMB_FF = {'outer': 0.06, 'front': 0.0, 'back': -0.05, 'inner': -0.12}
# 둘레 좌표 시작 열 (면을 넘어 이어지는 주름·누빔 무늬용): 몸통 = 오른쪽→앞→왼쪽→뒤, 팔다리 = 바깥→앞→안→뒤
BODY_X0, ARM_X0, LEG_X0 = 16, 40, 0


def shade(ramp, v):
    """ramp 를 연속으로 읽되 반 칸 단위로 끊는다 (픽셀아트처럼 또렷하되 6단보다 두 배 촘촘한 명암)."""
    t = max(0.0, min(1.0, v)) * (len(ramp) - 1)
    t = round(t * 2) / 2
    k = min(int(t), len(ramp) - 2)
    return mix(ramp[k], ramp[k + 1], t - k)


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


def _mail(lk, i, j, base=0.26):
    """사슬 갑옷: 엇갈린 고리 무늬 (판 사이로 보이는 밑받침)."""
    return lk.main, base + (0.12 if (i + j % 2) % 2 == 0 else -0.05)


def _channel(u):
    """세로 누빔 골 (갬비슨): 땀 한 줄 + 부푼 두 줄."""
    return (-0.14, 0.1, 0.03)[u % 3]


def _fold(u):
    """천 주름: 밝은 등 → 중간 → 깊은 골 (4칸 주기 = 팔다리 한 면에 골 하나)."""
    return (0.05, 0.05, 0.0, -0.13)[u % 4]


def paint_set(look, look_kind: str, seed: int):
    """Returns (humanoid_img, leggings_img)."""
    hum = Painter(look, seed)
    leg = Painter(look, seed + 1)
    kind = look_kind if look_kind in ('heavy', 'light', 'cloth') else 'heavy'
    {'heavy': _heavy, 'light': _light, 'cloth': _cloth}[kind](hum, leg, look)
    _style_touches(hum, leg, look, kind)
    _trims(hum, leg, look, kind, look.level)
    return hum.img, leg.img


# ───────────────────────────── 중갑 (판금) ─────────────────────────────

def _heavy(hum: Painter, leg: Painter, lk):
    """판 하나하나를 크게: 밝은 윗테 → 아래로 어두워지는 둥근 면 → 판 아래 짙은 그림자.
    판 사이로는 어두운 사슬이 비쳐 겹이 진다 (견갑 아래, 허벅지)."""
    M, G, O = lk.main, lk.grip, lk.orn

    def n_(i, j, salt):
        return _noise(lk, i, j, salt, 0.05)

    def rivet_or(rivets, i, j, base):
        if (i, j) in rivets:
            return O, 0.9
        if (i, j - 1) in rivets:
            return M, base - 0.24                                            # 리벳 아래 그림자
        return M, base

    def body(name):
        def fn(i, j, w, h):
            n = n_(i, j, len(name))
            if name == 'top':
                return M, 0.66 + n
            if name == 'bottom':
                return (M, 0.14) if _ring(i, j, w, h) else None              # 열린 아랫단 (두께가 보이게)
            ff = BODY_FF[name]
            mid = (w - 1) / 2
            dx = abs(i - mid) / mid
            if j == 0:
                return M, 0.9 + ff                                           # 고르짓 테
            if j == 1:
                return M, 0.64 + ff + (0.06 if dx < 0.5 else 0)              # 고르짓 판
            if j == 2:
                return M, 0.1                                                # 고르짓 아래 그림자
            if j <= 7:
                v = (0.76, 0.7, 0.63, 0.56, 0.48)[j - 3] + ff + n            # 위가 밝고 아래로 둥글게 어두워짐
                if name in ('front', 'back'):
                    v += 0.1 * (1 - dx * dx) - 0.08 * dx * dx                # 불룩한 면 (가장자리 어둡게)
                if name == 'front':
                    if j <= 6 and i == 3:
                        v += 0.12                                            # 가운데 능선 (빛 받는 쪽)
                    elif j <= 6 and i == 4:
                        v -= 0.04
                    return rivet_or({(1, 3), (6, 3)}, i, j, v)
                if name == 'back':
                    if i in (3, 4):
                        return M, v - 0.2 + (0.06 if i == 3 else 0)          # 등뼈 골
                    return rivet_or({(1, 3), (6, 3)}, i, j, v)
                if i in (1, 2) and j >= 4:                                   # 옆구리 버클 끈
                    if j == 5:
                        return O, 0.84 if i == 1 else 0.6
                    return G, 0.5 if i == 1 else 0.34
                return M, v - 0.04
            if j == 8:
                return M, 0.08                                               # 흉갑 아래 깊은 그림자
            if j == 9:
                return rivet_or({(0, 9), (w - 1, 9)} if name in ('front', 'back') else set(), i, j,
                                0.66 + ff + n)                               # 허리 라메
            if j == 10:
                return M, 0.44 + ff + n
            if name == 'front' and i in (3, 4):
                return O, 0.88 if i == 3 else 0.62                           # 버클
            return G, 0.34 + n                                               # 벨트

        return fn

    hum.faces(BODY, body)

    def arm(name):
        def fn(i, j, w, h):
            n = n_(i, j, 40 + len(name))
            if name == 'top':
                # 견갑 윗면 (i=0 = 바깥 모서리, j=0 = 뒤): 둥근 돔
                if i == 0:
                    return M, 0.86
                return M, 0.92 - 0.1 * (abs(i - 1.6) + abs(j - 1.5)) + n
            if name == 'bottom':
                return (M, 0.22) if _ring(i, j, w, h) else None              # 열린 손목 (두꺼운 관처럼)
            ff = LIMB_FF[name]
            if j == 0:
                return M, 0.9 + ff * 0.5                                     # 견갑 테
            if j <= 4:
                v = (0.78, 0.68, 0.58, 0.44)[j - 1] + ff + n                 # 견갑 돔 → 어두운 아랫면
                if name == 'outer' and i in (1, 2) and j <= 2:
                    v += 0.1
                return M, v
            if j == 5:
                return M, 0.06                                               # 견갑 아래 그림자
            if j == 6:
                return _mail(lk, i, j, 0.22)                                 # 사슬 소매
            if j == 7:
                return M, 0.82 + ff                                          # 완갑 윗테
            if j in (8, 9):
                v = 0.62 + ff + n - (0.08 if j == 9 else 0)
                if name == 'outer' and i == 1:
                    v += 0.14                                                # 완갑 능선
                return M, v
            if j == 10:
                return M, 0.84 + ff                                          # 건틀릿 커프 벌어진 테
            return M, 0.28 + ff                                              # 커프 아랫면

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
                return M, 0.9 + ff * 0.5                                     # 장화 윗테 (두껍게)
            if j == 8:
                return M, 0.62 + ff + n
            if j == 9:
                return M, 0.1                                                # 커프 아래 그림자
            if j == 10:
                if name == 'front':
                    return M, 0.84 if i in (1, 2) else 0.64                  # 앞코 캡
                return M, 0.6 + ff + n
            if name == 'front':
                return M, 0.52 if i in (1, 2) else 0.3
            return G, 0.2                                                    # 밑창 테

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
            return M, 0.76 if name in ('front', 'back') else 0.5             # 태싯 고리

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
                return G, 0.3                                                # 벨트 밑
            if name == 'inner' and j <= 6:
                return _mail(lk, i, j, 0.22)
            if j <= 3:
                return M, (0.84, 0.66, 0.52)[j - 1] + ff + n                 # 태싯: 윗테 → 아랫면
            if j == 4:
                return M, 0.08                                               # 태싯 그림자
            if j == 5:
                return _mail(lk, i, j, 0.22)                                 # 허벅지 사슬
            if j == 6:
                if name == 'front':
                    return M, (0.56, 0.96, 0.84, 0.5)[i]                     # 무릎 덮개 돔
                if name == 'outer':
                    return M, 0.74 + n                                       # 무릎 날개
                return _mail(lk, i, j, 0.22)
            if j == 7:
                return M, 0.16                                               # 무릎 아래
            v = 0.56 + ff + n - 0.03 * (j - 8)
            if name == 'front' and i == 1:
                v += 0.14                                                    # 정강이 능선
            return M, v

        return fn

    leg.faces(LEG, legs)


# ───────────────────────────── 경갑 (가죽 + 누빔) ─────────────────────────────

def _light(hum: Painter, leg: Painter, lk):
    """매끈한 가죽 판 + 그 밑으로 드러나는 연한 누빔 패딩 (옆구리·허리 치마), 두 겹 어깨 패드,
    말린 깃·팔목·접어 내린 장화 목, 떠 있는 사선 끈."""
    M, G, O = lk.main, lk.grip, lk.orn
    strap = O if lk.level >= 2 else G
    L = lk.pal.light
    pad = [shade(M, 0.2), mix(shade(M, 0.45), L, 0.3), mix(shade(M, 0.65), L, 0.45), mix(shade(M, 0.85), L, 0.5),
           lighten(L, 0.15)]                                                 # 누빔 천: 가죽 색을 팔레트 밝은 색 쪽으로

    def n_(i, j, salt):
        return _noise(lk, i, j, salt, 0.06)

    def body(name):
        def fn(i, j, w, h):
            if name == 'top':
                return M, 0.6
            if name == 'bottom':
                return (G, 0.2) if _ring(i, j, w, h) else None
            n = n_(i, j, len(name))
            ff = BODY_FF[name]
            u = BODY[name][0] - BODY_X0 + i
            if name in ('front', 'back') and 1 <= j <= 9:                    # 어깨→허리 사선 끈
                d = (i - j * 0.66) - (1 if name == 'front' else 5)
                if abs(d) < 0.8:
                    if name == 'front' and j == 5:
                        return O, 0.88                                       # 끈 버클
                    return strap, 0.92 if d < 0 else 0.7
                if 0.8 <= d < 1.6:
                    return M, 0.14                                           # 끈 그림자 (끈이 떠 보이게)
            if j == 0:
                return M, 0.86 + ff                                          # 말린 깃
            if j == 1:
                return M, 0.2                                                # 깃 아래
            if j <= 7:
                if name in ('left', 'right'):                                # 옆구리: 누빔 패딩이 드러남
                    return pad, 0.55 + _channel(u) + n
                mid = (w - 1) / 2
                dx = abs(i - mid) / mid
                v = (0.74, 0.7, 0.65, 0.6, 0.55, 0.5)[j - 2] + ff + n + 0.08 * (1 - dx * dx) - 0.08 * dx * dx
                if name == 'front' and i in (3, 4) and j <= 6:               # 앞섶 끈 엮음
                    return (G, 0.92) if (i == 3) == (j % 2 == 0) else (M, 0.24)
                if name == 'back' and 2 <= i <= 5 and 3 <= j <= 6:           # 등: 가죽 테 안쪽 누빔 패드
                    return pad, 0.56 + _channel(u) - 0.04 * (j - 3)
                if name == 'back' and 1 <= i <= 6 and (j == 2 or i in (1, 6)) and j <= 7:
                    return M, v + 0.14                                       # 패드 둘레 가죽 테
                return M, v
            if j == 8:
                return M, 0.12                                               # 가죽 판 아래 그림자
            if j == 9:
                return G, 0.84 + ff                                          # 벨트 윗테
            if j == 10:
                if name == 'front' and i in (2, 3):
                    return O, 0.88 if i == 2 else 0.62
                return G, 0.6 + n
            return pad, 0.5 + _channel(u)                                    # 누빔 치마 윗단

        return fn

    hum.faces(BODY, body)

    def arm(name):
        def fn(i, j, w, h):
            n = n_(i, j, 40 + len(name))
            if name == 'top':
                if i == 0:
                    return M, 0.86
                return M, 0.8 - 0.06 * (abs(i - 1.6) + abs(j - 1.5)) + n
            if name == 'bottom':
                return (G, 0.2) if _ring(i, j, w, h) else None
            ff = LIMB_FF[name]
            outer = name == 'outer'
            if j == 0:
                return M, 0.86 + ff * 0.5                                    # 어깨 패드 테
            if j == 1:
                return M, 0.68 + ff + n
            if j == 2:
                return (M, 0.5 + n) if outer else (M, 0.16)                  # 윗겹 아랫면 / 패드 밑
            if j <= 4 and outer:
                return (M, 0.72 + n) if j == 3 else (M, 0.42)                # 아래 겹 패드
            if j < 7:
                return None                                                  # 드러난 윗팔
            if j == 7:
                return M, 0.86 + ff * 0.5                                    # 팔목 보호대 말린 테
            if j == 8:
                return M, 0.36 + ff
            if j in (9, 10):
                if name == 'front' and i in (1, 2):
                    return (G, 0.92) if (i - 1) == (j - 9) else (G, 0.5)     # X 끈
                return M, 0.62 + ff + n - 0.06 * (j - 9)
            return strap, 0.76                                               # 손목 커프

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
                return M, 0.88 + ff * 0.5                                    # 접어 내린 장화 목
            if j == 8:
                return M, 0.64 + ff + n
            if j == 9:
                return M, 0.14                                               # 접힌 단 그림자
            if j == 10:
                if name == 'front' and i in (1, 2):
                    return O, 0.88 if i == 1 else 0.62                       # 발등 버클
                if name in ('front', 'outer'):
                    return G, 0.84
                return M, 0.54 + ff + n
            if name == 'front' and i in (1, 2):
                return M, 0.62
            return G, 0.14

        return fn

    hum.faces(LEG, boot)

    def belt(name):
        def fn(i, j, w, h):
            if name in ('top', 'bottom') or j < 9:
                return None
            u = BODY[name][0] - BODY_X0 + i
            if j == 9:
                return G, 0.84
            if j == 10:
                if name == 'front' and i in (3, 4):
                    return O, 0.88 if i == 3 else 0.62
                return G, 0.6
            return pad, 0.5 + _channel(u)

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
                return G, 0.3
            if name == 'outer' and j <= 4:                                   # 허벅지 가죽 덧판
                return M, (0.8, 0.66, 0.54, 0.12)[j - 1] + (n if j < 4 else 0)
            if name == 'front' and j == 2:
                return (O, 0.88) if i == 1 else (strap, 0.86)                # 허벅지 끈
            if name == 'front' and j == 3:
                return M, 0.2
            if name == 'front' and j == 5:
                return M, (0.64, 0.88, 0.8, 0.6)[i]                          # 무릎 패드
            if name == 'front' and j == 6:
                return M, 0.5
            if j == 7 and name in ('front', 'outer'):
                return M, 0.16
            return pad, 0.48 + ff + _channel(u) + n                          # 누빔 바지

        return fn

    leg.faces(LEG, legs)


# ───────────────────────────── 천옷 (로브) ─────────────────────────────

def _cloth(hum: Painter, leg: Painter, lk):
    """어깨를 덮는 망토(수놓은 단 + 부드러운 그늘), 주름 잡혀 부푼 소매, 접어 올린 넓은 소맷부리,
    굵은 허리띠와 매듭, 주름 잡힌 치마·앞뒤로 늘어진 로브 자락."""
    M, G, O = lk.main, lk.grip, lk.orn                                       # 천은 잡음 없이 주름만

    def body(name):
        def fn(i, j, w, h):
            if name == 'top':
                return M, 0.66
            if name == 'bottom':
                return (M, 0.14) if _ring(i, j, w, h) else None
            ff = BODY_FF[name]
            u = BODY[name][0] - BODY_X0 + i
            if j == 0:
                return O, 0.64                                               # 목깃
            if j <= 2:
                return M, 0.74 + ff + _fold(u) * 0.8 - 0.05 * (j - 1)        # 어깨 망토
            if j == 3:
                return O, 0.74 if u % 2 == 0 else 0.62                       # 망토 수놓은 단
            if j == 4:
                return M, 0.22                                               # 망토 아래 그늘
            if name == 'front' and i in (3, 4):
                return O, 0.7 + (0.14 if j % 2 == 0 else 0)                  # 수놓은 가운데 판
            if name == 'front' and i in (5, 6) and 7 <= j <= 8:
                return O, (0.86, 0.66)[j - 7] if i == 5 else (0.66, 0.5)[j - 7]   # 띠 매듭 고리
            if name == 'front' and i == 6 and j in (9, 10):
                return G, 0.9 - 0.12 * (j - 9)                               # 늘어진 띠 끝
            if j <= 6:
                return M, 0.58 + ff + _fold(u) - 0.04 * (j - 5)              # 가슴 주름
            if j == 7:
                return G, 0.86                                               # 허리띠 (두껍게)
            if j == 8:
                return G, 0.6
            if j <= 10:
                return M, 0.56 + ff + _fold(u) - 0.05 * (j - 9)              # 치마 주름
            return O, 0.56                                                   # 아랫단

        return fn

    hum.faces(BODY, body)

    def arm(name):
        def fn(i, j, w, h):
            if name == 'top':
                return M, 0.76 + _fold(i + j) * 0.6
            if name == 'bottom':
                return (M, 0.1) if _ring(i, j, w, h) else None               # 넓은 소매 안쪽
            u = ARM[name][0] - ARM_X0 + i
            ff = LIMB_FF[name]
            if j == 0:
                return M, 0.82 + ff * 0.5                                    # 어깨 위 망토
            if j <= 2:
                return M, 0.72 + ff + _fold(u) * 0.8 - 0.05 * (j - 1)
            if j == 3:
                return O, 0.74 if u % 2 == 0 else 0.62                       # 망토 단
            if j == 4:
                return M, 0.22
            if j <= 8:
                return M, (0.66, 0.62, 0.56, 0.5)[j - 5] + ff + _fold(u)     # 소매 주름 (아래로 그늘)
            if j == 9:
                return M, 0.84 + ff * 0.5                                    # 접어 올린 소맷부리
            if j == 10:
                return O, 0.68
            return M, 0.1                                                    # 소매 안감 그늘

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
                return M, 0.62 + ff - 0.08 * (j - 8)
            if j == 10:
                return (G, 0.8) if (i + (name == 'back')) % 3 == 0 else (M, 0.5 + ff)   # 감은 천
            if name == 'front' and i in (1, 2):
                return M, 0.58
            return G, 0.16

        return fn

    hum.faces(LEG, boot)

    def skirt(name):
        def fn(i, j, w, h):
            if name in ('top', 'bottom') or j < 7:
                return None
            u = BODY[name][0] - BODY_X0 + i
            if j in (7, h - 1):
                return O, 0.62
            return M, 0.54 + _fold(u)

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
                return G, 0.3
            if name in ('front', 'back') and j <= 6:                         # 앞·뒤로 늘어진 로브 자락
                if j == 5:
                    return O, 0.68 if i % 2 == 0 else 0.58
                if j == 6:
                    return M, 0.26
                return M, 0.66 + ff + _fold(u) - 0.04 * j
            if name == 'outer' and i == 1:
                return O, 0.64                                               # 옆선 띠
            v = 0.5 + ff + _fold(u) * 0.7
            if j == 7:
                v += 0.08                                                    # 무릎 아래 주름
            elif j == 8:
                v -= 0.06
            return M, v

        return fn

    leg.faces(LEG, legs)


# ───────────────────────────── 재질 손질 ─────────────────────────────

def _lum(c):
    return (c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11) / 255


def _style_touches(hum: Painter, leg: Painter, lk, kind):
    """중갑 재질의 버릇: 녹(녹슨 철) · 녹청(구리) · 달아오른 틈(흑철) · 결정 면(수정) · 리벳 줄(태엽)."""
    style = lk.style
    if kind != 'heavy' or style not in ('rusted_iron', 'copper', 'dark_iron', 'crystal', 'clockwork'):
        return
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
                    pt.put(x, y, mix(c, shade(lk.accent, 0.4), 0.55))
                elif style == 'crystal' and _lum(c) > _lum(shade(lk.main, 0.6)) and r < 0.12:
                    pt.put(x, y, shade(lk.accent, 0.85))
    if style == 'clockwork':
        rv = shade(lk.orn, 0.85)
        for name in ('front', 'back'):
            x0, y0, w, _ = BODY[name]
            for i in range(1, w - 1, 2):
                hum.put(x0 + i, y0 + 10, rv)                                 # 허리 라메 리벳 줄
        x0, y0, w, _ = ARM['outer']
        for i in (0, w - 1):
            hum.put(x0 + i, y0 + 2, rv)                                      # 견갑 리벳


GLOW_ALPHA = 252   # emissive marker (owner's pack convention; fullbright once a core shader is added)

# 등급 장식이 앉을 자리 (모양별): 가슴 보석 윗줄, 레깅스 테 줄, 빛나는 이음매 줄
GEM_ROW = {'heavy': 4, 'light': 3, 'cloth': 1}
LEG_RIM_ROW = {'heavy': 1, 'light': 3, 'cloth': 5}
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
        # 레깅스 테 + 장화 윗테
        for name in ('front', 'outer', 'back'):
            row(leg, LEG[name], LEG_RIM_ROW[kind], trim, trim_lo if kind != 'heavy' else None)
            row(hum, LEG[name], 7, trim_hi if name == 'front' else trim)
    if lvl >= 3:
        if kind == 'heavy':
            for name in ('outer', 'front', 'back'):
                row(hum, ARM[name], 2, trim_lo)                              # 견갑 라메 끝 금박
            row(hum, BODY['front'], 7, trim, trim_lo)                        # 흉갑 말린 테 금박
            row(hum, BODY['back'], 7, trim_lo)
        elif kind == 'light':
            for j in range(2, 7, 2):
                solid(hum, fx, fy + j, trim)                                 # 박음질을 금실로
                solid(hum, fx + fw - 1, fy + j, trim)
            for name in ('outer', 'front', 'back'):
                row(hum, ARM[name], 7, trim_lo)
        else:
            for name in ('front', 'back'):
                x0, y0, w, h = BODY[name]
                for i in range(1, w, 3):
                    solid(hum, x0 + i, y0 + 3, gem)                          # 망토 단 보석 점
            for name in ('outer', 'front', 'back'):
                x0, y0, w, h = ARM[name]
                solid(hum, x0 + 1, y0 + 3, gem)
    if lvl >= 4:
        # 빛나는 이음매 — 부피를 만드는 판 아래 그림자 줄은 가운데 두 칸만 빛내고 나머지는 어둡게 둔다
        for name in ('front', 'back'):
            x0, y0, w, h = BODY[name]
            for i in (3, 4):
                glow_px(hum, x0 + i, y0 + seams['body'], glow)
        j0, j1 = GLOW_FLANK[kind]
        for j in range(j0, j1 + 1):
            if kind != 'cloth':
                glow_px(hum, fx + 1, fy + j, glow)                           # 가슴 옆선
                glow_px(hum, fx + fw - 2, fy + j, glow)
            elif j % 2 == 0:
                glow_px(hum, fx + 3, fy + j, glow)                           # 수놓은 가운데 판 실
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
