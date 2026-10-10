"""
아이템 그림·모형·정의와 입자 그림 (DESIGN.md 10.6, 10.7). gen_pack.py 가 gui_skin 다음에 부른다.

M0 에서 만드는 것
  souls:master_key   만능 열쇠 (9.5, 도적의 시작 아이템). 손으로 찍은 16px 쇠 열쇠: 왼쪽 아래 청동 고리, 비스듬한 자루, 오른쪽 위
                     이빨. 평면 아이템 (item/generated).
  souls:ring_*       반지 (9.4, content/rings.yml 의 model). 지금은 시험 반지 셋 (RING_ART): 같은 꼴의 고딕 반지 (둥근 테 위에
                     물림쇠로 감싼 깎은 마름모 돌) 에 테와 돌의 색만 다르다. 인벤토리 반지 칸 바탕에 흐리게 비치는 반지 그림
                     (RING_PLACEHOLDER, gui_skin 이 그린다) 은 고른 시안의 팔각 테와 마름모 돌이고 반지를 끼면 반지 그림이 다 덮는다
                     (바닐라 클라이언트는 2×2 칸에 빈 칸 그림을 주지 않아 바탕에 그렸다. ring_cover 가 덮는지 본다).
  souls:test_guard   시험 막기·휘두름 도구의 맞춤 모형 (13.4 의 6, 8). 손으로 찍은 16px 쇠 버클러 하나.
                     items/test_guard.json 이 using_item 으로 평소 모형과 막는 모형을 가른다 (바닐라 방패와 같은 꼴, 10.6).
                     그림은 assets/souls/textures/item/ 에 둔다. 1.21.11 은 items 아틀라스가 이름공간마다 textures/item
                     폴더를 읽으므로 아틀라스 파일 없이 souls:item/test_guard 로 부른다. 이것이 M0 의 items 아틀라스 점검이다.
  poof 입자          바닐라 poof (몹이 죽을 때, 사망 화면 뒤에서 내 몸이 사라질 때) 는 흰 뭉게구름 여덟 장(generic_7..0)이라
                     사망 화면의 붉은 덧칠 밑에서 큰 연보라 덩어리로 보였다. 재 부스러기 몇 점(souls:poof_7..0)으로 바꾼다.
                     generic_*.png 는 연기·먼지·구름이 함께 쓰므로 고치지 않고 particles/poof.json 만 덮어쓴다.

무기·방패·병·방어구의 모형은 M1 부터 wkit 으로 만든다 (그때 ITEM_ART 에 아이콘이 더해진다).
"""
import json
import os

from PIL import Image

from palette import c

NS = "souls"


def _img(rows, ink):
    """기호 그림 → RGBA ('.' 은 투명)."""
    img = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        if len(row) != len(rows[0]):
            raise ValueError(f"줄 길이가 다르다: {y} 줄")
        for x, ch in enumerate(row):
            if ch != ".":
                px[x, y] = c(ink[ch])
    return img


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def _png(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


# ─────────────────────────── 아이템 그림 (16px) ───────────────────────────

# 쇠 버클러: 둥근 판에 청동 돋을새김 하나. 빛은 왼쪽 위 (S), 오른쪽 아래는 그늘 (r, q).
# 못 둘 (왼쪽 위, 왼쪽 아래) 은 모양이 다르고, 가운데 왼쪽으로 긁힌 금 (x), 오른쪽 아래 테가 녹슬어 떨어져 나갔다.
ITEM_ART = {
    # 만능 열쇠: 녹슨 쇠 자루가 왼쪽 아래 청동 고리에서 오른쪽 위로 비스듬히 오르고, 끝 오른쪽 아래로 이빨 둘. 빛은 왼쪽 위 (S).
    # 고리는 둥글지 않고 오른쪽 아래가 눌렸다 (오래 쥔 손), 이빨은 크기가 다르다
    "master_key": (
        [
            "................",
            "...........K....",
            "..........KSK...",
            ".........KSRKK..",
            "........KSRKRrK.",
            ".......KSRK.KrK.",
            "......KSRK...K..",
            ".....KSRK.......",
            "..KKKSRK........",
            ".KbBnKK.........",
            "KbK..KnK........",
            "KBK...bK........",
            "KnK..KoK........",
            ".KboooK.........",
            "..KKKK..........",
            "................",
        ],
        {"K": "ash0", "S": "rust3", "R": "rust2", "r": "rust1", "b": "bronze1", "B": "bronze3", "n": "bronze2", "o": "bronze0"},
    ),
    "test_guard": (
        [
            "................",
            ".....KKKKKK.....",
            "...KKSSSSSSKK...",
            "..KSSRRRRRRrKK..",
            "..KSRRSRRRRRrK..",
            ".KSRRRRRRRRRRrK.",
            ".KSRRRRbbbRRRrK.",
            ".KSRxRbBnnoRRrK.",
            ".KSRRxbnnnoRrrK.",
            ".KSRRRboooRRrrK.",
            ".KSRRRRRRRRrrqK.",
            "..KRSRRRRRrrqK..",
            "..KrRRRRqrrqqK..",
            "...KKrrrqqqKK...",
            ".....KKK.KKK....",
            "................",
        ],
        {"K": "ash0", "S": "rust3", "R": "rust2", "r": "rust1", "q": "rust0", "x": "ash2",
         "b": "bronze1", "B": "bronze3", "n": "bronze2", "o": "bronze0"},
    ),
}

# 반지 (9.4). 꼴은 하나 (RING_SHAPE), 색만 다르다. 기호: 테 금속은 반지마다 (H 밝음, M 가운데, L 어두움, D 그늘), P 물림쇠,
# S·s 돌 (밝음·어두움). 테는 바깥 지름 10 (x 3..12, y 5..14), 굵기 2 의 둥근 고리 (속 구멍 지름 약 5). 빛은 왼쪽 위: 바깥 면은
# 왼쪽 위가 밝고 오른쪽 아래가 꺼지며, 속 면은 거꾸로 (위 테의 아랫면은 그늘, 아래 테의 윗면은 빛을 받는다). 돌은 위 가운데
# 다섯 칸 너비의 깎은 마름모 (x 5..9, y 1..4, 가운데 x 7) 를 물림쇠가 감싼다: 사용자가 고른 시안 (dist/screenshots/ring_slots/
# ring_B_1080.png) 그대로 테의 가운데 (x 7.5) 보다 반 칸 왼쪽이다. 먹 테두리는 두지 않는다 (칸 바닥이 먹이라 보이지 않고 반지만
# 작아진다).
RING_SHAPE = [
    "................",
    ".......P........",
    "......PSP.......",
    ".....PSsSP......",
    "......PsP.......",
    ".....HHHHHM.....",
    "....HHLLLLMM....",
    "...HHLL..LLLL...",
    "...HLL....MML...",
    "...HL......ML...",
    "...ML......HD...",
    "...MLL....HHD...",
    "...MMMM..HHDD...",
    "....LLMHHHDD....",
    ".....LLDDDD.....",
    "................",
]
# 반지 칸 바탕의 흐린 반지 (gui_skin 이 2×2 의 왼쪽 위·왼쪽 아래 칸 바탕에 한 색 윤곽으로 그린다. 갑옷 칸의 빈 칸 그림과 같은 말씨):
# 고른 시안 (ring_B_1080.png) 의 점 그대로. 모서리를 두 번 꺾은 팔각 테 (곧은 옆은 네 줄) 위에 깎은 마름모 돌. 옛 그림 (모서리를 한
# 번 꺾은 네모진 테 위에 속이 빈 4×4 고리) 은 둥근 몸에 고리를 단 꼴이라 반지가 아니라 마개 단 병 (에스트 병) 으로 읽혔다 (검토
# ring-placeholder-shape). 모든 반지 그림이 이 점들을 불투명하게 덮어야 한다 (ring_cover)
RING_PLACEHOLDER = [
    "................",
    ".......o........",
    "......o.o.......",
    ".....o.o.o......",
    "......o.o.......",
    "......oooo......",
    ".....o....o.....",
    "....o......o....",
    "...o........o...",
    "...o........o...",
    "...o........o...",
    "...o........o...",
    "....o......o....",
    ".....o....o.....",
    "......oooo......",
    "................",
]
# 반지마다 (모형 이름 → 테 금속 H M L D, 물림쇠 P, 돌 S s). 스태미나는 이끼빛 돌 (스태미나 막대의 계열) 에 청동 테, 강인도는 뼈빛 돌에
# 녹슨 쇠 테, 쳐내기는 마른 핏빛 돌에 어두운 쇠 테
RING_INKS = {
    "ring_test_stamina": {"H": "bronze3", "M": "bronze2", "L": "bronze1", "D": "bronze0", "P": "bronze1", "S": "moss2", "s": "moss1"},
    "ring_test_poise": {"H": "rust3", "M": "rust2", "L": "rust1", "D": "rust0", "P": "bronze2", "S": "bone2", "s": "bone0"},
    "ring_test_parry": {"H": "ash3", "M": "rust2", "L": "rust1", "D": "rust0", "P": "bronze2", "S": "blood3", "s": "blood1"},
}
RING_ART = {name: (RING_SHAPE, dict(ink, K="ash0")) for name, ink in RING_INKS.items()}


def ring_cover():
    """반지 그림마다 바탕의 흐린 반지 (RING_PLACEHOLDER) 를 덮지 못하는 점 [(모형, x, y)]. 비어 있어야 한다."""
    bad = []
    for name, (rows, _) in RING_ART.items():
        for y, row in enumerate(RING_PLACEHOLDER):
            for x, ch in enumerate(row):
                if ch != "." and rows[y][x] == ".":
                    bad.append((name, x, y))
    return bad


# 막는 모형: 평소 모형을 부모로 두고 손 자세만 바꾼다 (왼손 값은 비워 두면 클라이언트가 오른손 값을 거울로 쓴다).
# 1인칭: 바닐라가 막는 몸짓(BLOCK) 으로 아이템을 이미 정면으로 세운 뒤라, 평면 아이템 기본값(-90, 25)에서
#   위로 (y), 가운데 쪽으로 (z) 옮기고 기울기를 줄였다. 판이 조준점 바로 아래, 가운데에서 조금 오른쪽에 선다.
# 3인칭: 들어 올린 팔 앞에서 판이 앞을 보게 90° 돌렸다. 값은 실제 클라이언트 화면을 보며 맞췄다 (13.4 의 6).
GUARD_BLOCKING_DISPLAY = {
    "firstperson_righthand": {"rotation": [0, -90, 15], "translation": [1.13, 4.5, 4.5], "scale": [0.6, 0.6, 0.6]},
    "thirdperson_righthand": {"rotation": [0, 90, 0], "translation": [1, 4, 2.5], "scale": [0.75, 0.75, 0.75]},
}


def build_items(out):
    bad = ring_cover()
    if bad:
        raise ValueError(f"반지 그림이 반지 칸 바탕의 흐린 반지를 덮지 못한다: {bad[:6]}")
    for name, (rows, ink) in list(ITEM_ART.items()) + list(RING_ART.items()):
        _png(_img(rows, ink), os.path.join(out, "assets", NS, "textures", "item", name + ".png"))
    models = os.path.join(out, "assets", NS, "models", "item")
    # 반지: 평면 아이템 하나씩 (souls:<모형 이름>, 플러그인 Rings.make 의 item_model)
    for name in RING_ART:
        _json(os.path.join(models, name + ".json"), {
            "parent": "minecraft:item/generated",
            "textures": {"layer0": f"{NS}:item/{name}"},
        })
        _json(os.path.join(out, "assets", NS, "items", name + ".json"), {
            "model": {"type": "minecraft:model", "model": f"{NS}:item/{name}"},
        })
    # 만능 열쇠: 평면 아이템 하나
    _json(os.path.join(models, "master_key.json"), {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": f"{NS}:item/master_key"},
    })
    _json(os.path.join(out, "assets", NS, "items", "master_key.json"), {
        "model": {"type": "minecraft:model", "model": f"{NS}:item/master_key"},
    })
    # 시험 도구: 평소 / 막는 중 (using_item)
    _json(os.path.join(models, "test_guard.json"), {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": f"{NS}:item/test_guard"},
    })
    _json(os.path.join(models, "test_guard_blocking.json"), {
        "parent": f"{NS}:item/test_guard",
        "display": GUARD_BLOCKING_DISPLAY,
    })
    _json(os.path.join(out, "assets", NS, "items", "test_guard.json"), {
        "model": {
            "type": "minecraft:condition",
            "property": "minecraft:using_item",
            "on_false": {"type": "minecraft:model", "model": f"{NS}:item/test_guard"},
            "on_true": {"type": "minecraft:model", "model": f"{NS}:item/test_guard_blocking"},
        }
    })


# ─────────────────────────── 입자: 재 부스러기 ───────────────────────────

# 8×8 여덟 장. 바닐라 poof 는 처음에 가장 큰 그림(generic_7)에서 작은 그림(generic_0)으로 넘어간다.
# 그래서 poof_7 이 가장 넓게 흩어진 부스러기, poof_0 이 마지막 한 점. 부스러기마다 자리를 손으로 골랐다.
# a 밝은 재, b 어두운 재 (바닐라가 0.7~1.0 회색을 곱한다)
POOF = {
    7: ["........",
        "..a.....",
        ".....b..",
        ".bb.....",
        "......a.",
        "...ab...",
        "........",
        ".a......"],
    6: ["........",
        "...a....",
        ".....b..",
        "..b.....",
        "......a.",
        "...ab...",
        "........",
        "........"],
    5: ["........",
        "........",
        "...a.b..",
        "..b.....",
        ".....a..",
        "...b....",
        "........",
        "........"],
    4: ["........",
        "........",
        "....b...",
        "..a.....",
        ".....a..",
        "...b....",
        "........",
        "........"],
    3: ["........",
        "........",
        "........",
        "..ab....",
        ".....a..",
        "........",
        "........",
        "........"],
    2: ["........",
        "........",
        "........",
        "...a....",
        "....b...",
        "........",
        "........",
        "........"],
    1: ["........",
        "........",
        "........",
        "...ab...",
        "........",
        "........",
        "........",
        "........"],
    0: ["........",
        "........",
        "........",
        "....a...",
        "........",
        "........",
        "........",
        "........"],
}
POOF_INK = {"a": "ash3", "b": "ash2"}


def build_particles(out):
    for i, rows in POOF.items():
        _png(_img(rows, POOF_INK), os.path.join(out, "assets", NS, "textures", "particle", f"poof_{i}.png"))
    _json(os.path.join(out, "assets", "minecraft", "particles", "poof.json"),
          {"textures": [f"{NS}:poof_{i}" for i in range(7, -1, -1)]})


def build(out):
    build_items(out)
    build_particles(out)
