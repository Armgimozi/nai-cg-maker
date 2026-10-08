#!/usr/bin/env python3
"""
픽셀 명조 시안 (mood_pixelserif) 빌드: 지금 팩 위에 이 시안만 덮어 따로 팩과 jar 를 만든다. 공유 코드 (gen_pack.py,
gui_skin.py, hud.py) 와 저장소의 pack.zip 은 건드리지 않는다.

  python3 pack/variants/mood_pixelserif/build.py --out <폴더> [--jar <Soulslike.jar>] [--base-pack <팩 폴더 또는 zip>]

  --jar        바탕 플러그인 jar (기본 plugin/build/libs/Soulslike.jar). 그 안의 pack.zip 이 바탕 팩이다 (--base-pack 이 없으면)
  --out        결과 폴더: pack/ (팩 폴더), pack.zip, Soulslike.jar (pack.zip 만 바꾼 jar 사본), preview_*.png

덮는 것 (시안의 말씨는 serif.py·ornaments.py 머리말)
  1. 글꼴   assets/souls/font/pixel_serif.zip (unihex, 2배 밀도 1비트): 본문 (나눔명조 Regular + EB Garamond) 과 제목
            (나눔명조 Bold + Cinzel, 개인 영역 U+E400..). minecraft:default·uniform 맨 앞에 넣어 바닐라 글꼴보다 먼저 쓴다.
            빈칸 " " 는 GUI 3 (바닐라 4: 작은 명조에 맞춘다). 제목 밑줄 그림 글자와 자리 빈칸 (U+E380..) 도 default 에.
  2. 언어   제목 글을 제목 글자로: 창 이름 (container.*), 게임 메뉴 (menu.game), 휴식 창 이름 (souls.bonfire.test-name),
            무기 이름 (souls.weapon.*.name). 게임 메뉴·휴식 창 이름 밑에는 가운데 무늬 밑줄 (§1 = 장식 색, 셰이더가 흰색으로).
  3. 셰이더 rendertype_text(.vsh, _intensity.vsh): GUI 글의 바닐라 색을 다크 소울 색으로 (흰 → 뼈빛, 회색 → 흐린 뼈빛,
            §6 → 옅은 금빛, §e → 양피지, 창 이름의 진회색 → 흐린 뼈빛, §1 → 장식 그대로 + 그림자 없음).
            HUD 표식 색 블록 (hud.py) 은 그대로 두고 그 밖의 글에만.
  4. 그림   설명 칸 (이름 밑줄·귀 꾸밈·깊어지는 바탕), 창 셋 (귀 꾸밈·관·가운데 무늬 나눔줄), 가리킨 단추 꾸밈, 비네트.
  5. 저작권 FONT_LICENSES.txt (팩 뿌리): 굽은 글꼴의 출처와 OFL 1.1 원문 셋.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(PACK_DIR)
for p in (HERE, PACK_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
from PIL import Image  # noqa: E402

import ornaments  # noqa: E402
import serif  # noqa: E402
import hud  # noqa: E402  (HUD 표식 색만 읽는다)
from palette import c  # noqa: E402

NS = "souls"
FONT_ID = f"{NS}:font/pixel_serif.zip"
SPACE_ADV = 3                         # " " 진행 폭 (GUI)
TITLE_PUA = 0xE400                    # 제목 글자 (개인 영역)
TITLE_TRACK = 2                       # 제목 로마자 글자 사이를 그림 칸 2 (GUI 1) 더 띄운다 (로마 비문 대문자)
RULE_CHAR = ""                  # 제목 밑줄 그림 글자
RULE_ASCENT = -6                      # 밑줄 위 = 줄 위 + 7 - ascent = 줄 위 + 13 (휴식 창 제목 옆 "!" 단추 아래)
SPACE_PUA = 0xE390                    # 자리 빈칸 ±1..±128 (E390..E39F)
SPACE_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)
ORN_COLOR = "§1"                 # 장식 색 표시 (§1 진한 파랑: 셰이더가 흰색으로, 그림자는 지운다)
TITLE_COLOR = "§6"               # 제목 색 표시 (§6 금색: 셰이더가 옅은 금빛으로)

TITLE_KEYS_MC = ("container.barrel", "container.chest", "container.chestDouble", "container.crafting",
                 "container.enderchest", "container.inventory", "menu.game")
RULED_KEYS = ("menu.game", "souls.bonfire.test-name")


def vanilla_lang(lang):
    """바닐라 언어 파일 (en_us 는 클라이언트 jar, 나머지는 에셋)."""
    home = os.environ.get("SOULS_CLIENT_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "souls-client")
    if lang == "en_us":
        with zipfile.ZipFile(os.path.join(home, "versions", "1.21.11.jar")) as z:
            return json.loads(z.read("assets/minecraft/lang/en_us.json"))
    idx = json.load(open(os.path.join(home, "assets", "indexes", "29.json")))["objects"]
    h = idx[f"minecraft/lang/{lang}.json"]["hash"]
    return json.load(open(os.path.join(home, "assets", "objects", h[:2], h), encoding="utf-8"))


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def zip_dir(folder):
    files = []
    for base, dirs, names in os.walk(folder):
        dirs.sort()
        for n in names:
            full = os.path.join(base, n)
            files.append((os.path.relpath(full, folder).replace(os.sep, "/"), full))
    files.sort()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for arc, full in files:
            zi = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                z.writestr(zi, fh.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


# ─────────────────────────── 글 ───────────────────────────

def split_codes(s):
    """글을 (조각, 글자인가) 로: § 꼴 표시와 %s·%1$s 자리 값은 그대로 둔다."""
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "§" and i + 1 < len(s):
            out.append((s[i:i + 2], False))
            i += 2
        elif ch == "%":
            j = i + 1
            while j < len(s) and (s[j].isdigit() or s[j] == "$"):
                j += 1
            j = min(j + 1, len(s))
            out.append((s[i:j], False))
            i = j
        else:
            out.append((ch, ch != " "))
            i += 1
    return out


class Titles:
    """제목 글자 표: 글자 → 개인 영역 문자 (제목 글자꼴로 굽는다)."""

    def __init__(self, face):
        self.face, self.map, self.glyphs, self.overrides, self.adv = face, {}, {}, [], {}
        self.next = TITLE_PUA

    def char(self, ch):
        if ch not in self.map:
            cp = self.next
            img = self.face.glyph(ch)
            if img is None:
                return ch
            self.next += 1
            self.map[ch] = chr(cp)
            self.glyphs[cp] = img
            self.adv[cp] = serif.advance(img)
            if not serif.is_hangul(ch):
                # 로마자 제목은 글자 사이를 넓힌다: 칸의 오른쪽 끝을 잉크보다 TITLE_TRACK 칸 밖으로 (진행 폭이 GUI 1 늘어난다).
                # size_overrides 의 범위는 from < to 여야 해서 바로 뒤 문자 하나를 비워 두고 둘을 한 범위로 준다
                self.next += 1
                self.overrides.append({"from": chr(cp), "to": chr(cp + 1), "left": 0,
                                       "right": img.width - 1 + TITLE_TRACK})
                self.adv[cp] = (img.width + TITLE_TRACK) // 2 + 1
        return self.map[ch]

    def convert(self, s):
        return "".join(self.char(t) if is_char else t for t, is_char in split_codes(s))

    def width(self, s):
        """제목 글의 진행 폭 (GUI). 꼴 표시는 0, 빈칸은 SPACE_ADV."""
        w = 0
        for t, is_char in split_codes(s):
            if not is_char:
                w += SPACE_ADV if t == " " else 0
                continue
            w += self.adv.get(ord(t), 5)
        return w


def spaces(n):
    """GUI n 픽셀을 미는 자리 빈칸 글자열 (2의 거듭제곱 조합)."""
    out = []
    sign = 1 if n >= 0 else -1
    n = abs(n)
    for k, step in reversed(list(enumerate(SPACE_STEPS))):
        while n >= step:
            out.append(chr(SPACE_PUA + (0 if sign > 0 else 8) + k))
            n -= step
    return "".join(out)


def ruled(title_pua, width, rule_adv, rule_w):
    """제목 뒤에 밑줄을 가운데에 그리고 제목 끝으로 돌아온다 (글 전체의 진행 폭은 제목 폭 그대로)."""
    m1 = -((width + rule_w) // 2)
    m2 = width - (width + m1 + rule_adv)
    return title_pua + ORN_COLOR + spaces(m1) + RULE_CHAR + spaces(m2)


# ─────────────────────────── 셰이더 ───────────────────────────

def _v(rgb):
    return "vec3(%.4f, %.4f, %.4f)" % tuple(v / 255 for v in rgb)


def _shadow(rgb):
    return tuple(int(v * 0.25) for v in rgb)


# 바닐라 글 색 → 시안 색 (그림자는 바닐라처럼 글 색 × 0.25 라 짝으로 함께 바꾼다)
REMAP = [
    ((255, 255, 255), c("bone2")[:3]),      # 흰 글 (단추, 채팅, 개수, 메뉴 제목) → 뼈빛
    ((224, 224, 224), c("bone2")[:3]),      # 입력 칸 글
    ((170, 170, 170), c("bone1")[:3]),      # §7 회색 (사망 화면 단추 글) → 흐린 뼈빛
    ((160, 160, 160), c("ash3")[:3]),       # 꺼진 단추 글
    ((64, 64, 64), c("bone1")[:3]),         # 창 이름의 바닐라 진회색 (판이 검어 보이지 않는다) → 흐린 뼈빛
    ((255, 170, 0), c("glim0")[:3]),        # §6 금색 (제목) → 옅은 금빛
    ((255, 255, 85), c("parch3")[:3]),      # §e 노랑 → 양피지
    ((85, 85, 85), c("ash2")[:3]),          # §8
]

SHADER_BLOCK = """
    // Square Soul pixel-serif variant (pack/variants/mood_pixelserif/build.py): GUI text colours -> Dark Souls palette.
    // Vanilla colours (and their x0.25 shadows) become bone / dim bone / pale gold; the ornament marker colour
    // (dark blue, set by the language files around title rules) draws the ornament's own colours and drops its shadow.
    if (ProjMat[3][3] == 1.0{guard}) {{
        ivec3 rgb8 = ivec3(Color.rgb * 255.0 + 0.5);
        vec3 col = Color.rgb;
        float alpha = Color.a;
{cases}
        if (rgb8 == ivec3(0, 0, 170)) col = vec3(1.0);
        else if (rgb8 == ivec3(0, 0, 42)) alpha = 0.0;
        vertexColor = vec4(col, alpha) * texelFetch(Sampler2, UV2 / 16, 0);
    }}
"""


def shader_block(guard):
    lines = []
    for i, (src, dst) in enumerate(REMAP):
        kw = "if" if i == 0 else "else if"
        lines.append(f"        {kw} (rgb8 == ivec3{src}) col = {_v(dst)};")
        lines.append(f"        else if (rgb8 == ivec3{_shadow(src)}) col = {_v(_shadow(dst))};")
    return SHADER_BLOCK.format(guard=guard, cases="\n".join(lines))


def patch_shader(src, guard):
    """main() 의 마지막 } 앞에 한 덩이를 넣는다."""
    i = src.rstrip().rfind("}")
    return src[:i] + shader_block(guard) + src[i:]


def vanilla_shader(name):
    home = os.environ.get("SOULS_CLIENT_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "souls-client")
    with zipfile.ZipFile(os.path.join(home, "versions", "1.21.11.jar")) as z:
        return z.read(f"assets/minecraft/shaders/core/{name}").decode("ascii")


# ─────────────────────────── 빌드 ───────────────────────────

def build(base_pack, out):
    pack = os.path.join(out, "pack")
    if os.path.exists(pack):
        shutil.rmtree(pack)
    if os.path.isdir(base_pack):
        shutil.copytree(base_pack, pack)
    else:
        with zipfile.ZipFile(base_pack) as z:
            z.extractall(pack)
    A = os.path.join(pack, "assets")

    # 1. 글자
    body = serif.body_face()
    glyphs = {}
    chars = serif.ksx1001_hangul() + serif.COMPAT_JAMO + serif.LATIN
    for ch in chars:
        img = body.glyph(ch)
        if img is not None:
            glyphs[ord(ch)] = img
    titles = Titles(serif.title_face())

    # 2. 언어 (제목 글자를 먼저 모아야 글꼴을 쓸 수 있다)
    rule = ornaments.title_rule()
    rule_h = rule.height
    assert rule_h % 2 == 0 and rule.width % 2 == 0, "제목 밑줄은 2배 밀도라 폭·높이가 짝수여야 한다"
    rule_w = rule.width // 2                               # GUI 폭
    rule_adv = int(0.5 + rule.width * 0.5) + 1             # bitmap 진행 폭
    for lang in ("ko_kr", "en_us"):
        van = vanilla_lang(lang)
        mc_path = os.path.join(A, "minecraft", "lang", lang + ".json")
        mc = read_json(mc_path) if os.path.exists(mc_path) else {}
        for key in TITLE_KEYS_MC:
            text = mc.get(key, van.get(key, ""))
            text = text.replace("§7", "")
            pua = titles.convert(text)
            if key in RULED_KEYS:
                mc[key] = TITLE_COLOR + ruled(pua, titles.width(pua), rule_adv, rule_w)
            else:
                mc[key] = TITLE_COLOR + pua
        write_json(mc_path, dict(sorted(mc.items())))
        sp = os.path.join(A, NS, "lang", lang + ".json")
        sl = read_json(sp)
        for key, text in list(sl.items()):
            if key.startswith("souls.weapon.") and key.endswith(".name"):
                sl[key] = titles.convert(text)
            elif key in RULED_KEYS:
                pua = titles.convert(text)
                sl[key] = TITLE_COLOR + ruled(pua, titles.width(pua), rule_adv, rule_w)
        write_json(sp, sl)

    glyphs.update(titles.glyphs)
    hexdata = serif.hex_zip(glyphs)
    fpath = os.path.join(A, NS, "font", "pixel_serif.zip")
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "wb") as f:
        f.write(hexdata)
    rule.save(os.path.join(A, NS, "textures", "font", "title_rule.png"))

    space_adv = {" ": SPACE_ADV}
    for k, step in enumerate(SPACE_STEPS):
        space_adv[chr(SPACE_PUA + k)] = step
        space_adv[chr(SPACE_PUA + 8 + k)] = -step
    ours = [
        {"type": "space", "advances": space_adv},
        {"type": "unihex", "hex_file": FONT_ID, "size_overrides": titles.overrides},
        {"type": "bitmap", "file": f"{NS}:font/title_rule.png", "height": rule_h // 2, "ascent": RULE_ASCENT,
         "chars": [RULE_CHAR]},
    ]
    for name in ("default", "uniform"):
        p = os.path.join(A, "minecraft", "font", name + ".json")
        d = read_json(p) if os.path.exists(p) else {"providers": []}
        d["providers"] = ours + d["providers"]
        write_json(p, d)

    # 3. 셰이더
    m = hud.MARK_LEFT
    # HUD 표식 색 (hud.py 셰이더 덩이의 mark) 은 건드리지 않는다
    guard = f" && !(mark.r == {m[0]} && mark.g == {m[1]} && mark.b >= {m[2]} && mark.b <= {hud.MARK_HIDDEN[2]})"
    sdir = os.path.join(A, "minecraft", "shaders", "core")
    tp = os.path.join(sdir, "rendertype_text.vsh")
    src = open(tp, encoding="ascii").read() if os.path.exists(tp) else vanilla_shader("rendertype_text.vsh")
    with open(tp, "w", encoding="ascii", newline="\n") as f:
        f.write(patch_shader(src, guard))
    with open(os.path.join(sdir, "rendertype_text_intensity.vsh"), "w", encoding="ascii", newline="\n") as f:
        f.write(patch_shader(vanilla_shader("rendertype_text_intensity.vsh"), ""))

    # 4. 그림
    gui = os.path.join(A, "minecraft", "textures", "gui")
    tbg, tfr = ornaments.tooltip()
    for img, n in ((tbg, "background"), (tfr, "frame")):
        img.save(os.path.join(gui, "sprites", "tooltip", n + ".png"))
        write_json(os.path.join(gui, "sprites", "tooltip", n + ".png.mcmeta"), {"gui": {"scaling": ornaments.TIP_SCALING[n]}})
    for name in ("inventory", "crafting_table", "generic_54"):
        ornaments.container(name).save(os.path.join(gui, "container", name + ".png"))
    ornaments.button("highlighted").save(os.path.join(gui, "sprites", "widget", "button_highlighted.png"))
    # 게임 중 창 뒤의 검정 (바탕 팩 120): 세상이 더 깊이 가라앉는다
    Image.new("RGBA", (16, 16), c(ornaments.INK, 150)).save(os.path.join(gui, "inworld_menu_background.png"))
    vp = os.path.join(A, "minecraft", "textures", "misc", "vignette.png")
    os.makedirs(os.path.dirname(vp), exist_ok=True)
    ornaments.vignette().save(vp)
    write_json(vp + ".mcmeta", {"texture": {"blur": True}})
    # HUD 소울 수 숫자: 같은 진행 폭 (7) 의 2배 밀도 세리프 숫자로 (hud.json 의 높이 8 은 그대로, 그림만 16 줄)
    ornaments.hud_digits().save(os.path.join(A, NS, "textures", "font", "hud_digits.png"))

    # 5. 저작권
    parts = ["Square Soul resource pack - pixel serif font (assets/souls/font/pixel_serif.zip)",
             "",
             "The 1-bit glyphs in pixel_serif.zip are a Modified Version (rasterised bitmap font) of the fonts below,",
             "distributed under the SIL Open Font License 1.1. It is not named after any Reserved Font Name.",
             ""]
    for key in ("nanummyeongjo", "ebgaramond", "cinzel"):
        parts.append(f"- {serif.CREDITS[key]}")
    for key in ("nanummyeongjo", "ebgaramond", "cinzel"):
        parts += ["", "=" * 78, f"{key}", "=" * 78, serif.license_text(key).strip()]
    with open(os.path.join(pack, "FONT_LICENSES.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")
    return pack, titles


def jar_with_pack(base_jar, pack_zip_bytes, out_jar):
    with zipfile.ZipFile(base_jar) as zin, zipfile.ZipFile(out_jar, "w") as zout:
        for item in zin.infolist():
            data = pack_zip_bytes if item.filename == "pack.zip" else zin.read(item.filename)
            zout.writestr(item, data)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--jar", default=os.path.join(ROOT, "plugin", "build", "libs", "Soulslike.jar"))
    ap.add_argument("--base-pack")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    base = a.base_pack
    base_bytes = None
    if not base:
        with zipfile.ZipFile(a.jar) as z:
            base_bytes = z.read("pack.zip")
        base = os.path.join(a.out, "base_pack.zip")
        with open(base, "wb") as f:
            f.write(base_bytes)
    pack, titles = build(base, a.out)
    data = zip_dir(pack)
    with open(os.path.join(a.out, "pack.zip"), "wb") as f:
        f.write(data)
    jar_with_pack(a.jar, data, os.path.join(a.out, "Soulslike.jar"))
    ornaments.preview(os.path.join(a.out, "preview_ornaments.png"), pack)
    before = len(base_bytes) if base_bytes is not None else os.path.getsize(base)
    print(f"제목 글자 {len(titles.map)}개, 팩 {len(data):,} 바이트 (바탕 {before:,}, +{len(data) - before:,}), "
          f"sha1 {hashlib.sha1(data).hexdigest()}")
    print("  →", os.path.join(a.out, "Soulslike.jar"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
