"""
아이템 그림·모형·정의와 입자 그림 (DESIGN.md 10.6, 10.7). gen_pack.py 가 gui_skin 다음에 부른다.

M0 에서 만드는 것
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

# 막는 모형: 평소 모형을 부모로 두고 손 자세만 바꾼다 (왼손 값은 비워 두면 클라이언트가 오른손 값을 거울로 쓴다).
# 1인칭: 바닐라가 막는 몸짓(BLOCK) 으로 아이템을 이미 정면으로 세운 뒤라, 평면 아이템 기본값(-90, 25)에서
#   위로 (y), 가운데 쪽으로 (z) 옮기고 기울기를 줄였다. 판이 조준점 바로 아래, 가운데에서 조금 오른쪽에 선다.
# 3인칭: 들어 올린 팔 앞에서 판이 앞을 보게 90° 돌렸다. 값은 실제 클라이언트 화면을 보며 맞췄다 (13.4 의 6).
GUARD_BLOCKING_DISPLAY = {
    "firstperson_righthand": {"rotation": [0, -90, 15], "translation": [1.13, 4.5, 4.5], "scale": [0.6, 0.6, 0.6]},
    "thirdperson_righthand": {"rotation": [0, 90, 0], "translation": [1, 4, 2.5], "scale": [0.75, 0.75, 0.75]},
}


def build_items(out):
    for name, (rows, ink) in ITEM_ART.items():
        _png(_img(rows, ink), os.path.join(out, "assets", NS, "textures", "item", name + ".png"))
    # 시험 도구: 평소 / 막는 중 (using_item)
    models = os.path.join(out, "assets", NS, "models", "item")
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
