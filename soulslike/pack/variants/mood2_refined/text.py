"""
mood2_refined 의 글 (글꼴 파일·공급자·글꼴 셰이더).

삐뚤빼뚤 고치기 (1차 시안의 사용자 평 "글자가 좀 삐뚤빼뚤하네")
  원인 셋 (시뮬레이션과 실제 클라이언트로 확인, exp/):
    1. 힌팅 명령을 지운 TTF 는 FreeType 이 자동 힌팅 (보통 모드) 으로 그린다. 글자마다 획이 다르게 격자에 붙어 굵기가 들쭉날쭉.
    2. oversample 4 로 그린 그림을 GUI 배율 3 에서 가장 가까운 텍셀로 집으면 4 텍셀 → 3 화면 픽셀이 고르지 않게 줄어든다
       (어떤 줄은 1 픽셀, 어떤 줄은 2 픽셀).
    3. 1차 시안의 쌍선형 보간은 2 를 흐리게만 했다 (글자 자리마다 다른 흐림).
  고친 것:
    - 글꼴에 아무 일도 하지 않는 prep 을 넣어 자동 힌팅을 막는다 (fonts.py). 윤곽 그대로.
    - oversample 12: 마인크래프트는 글자를 12배로 그리고 글자 자리·진행 폭을 1/12 GUI 픽셀 단위로 둔다. GUI 배율 2·3·4 (와 1·6)
      에서 화면 픽셀 경계가 늘 텍셀 경계와 겹친다 (12 가 2·3·4 로 나뉜다).
    - 글꼴 셰이더 (rendertype_text_intensity.fsh) 가 화면 픽셀이 덮는 텍셀을 정확한 면적으로 평균한다 (박스 필터,
      souls_box). 배율 4 는 3×3, 3 은 4×4, 2 는 6×6 텍셀의 평균 = 그 배율로 직접 그린 안티에일리어싱 글자. 바탕선은 모든
      글자에서 같은 텍셀 줄이라 (줄 위 + 7) 어느 배율에서도 한 줄로 평평하다.
  같은 박스 필터를 그림 글자 (rendertype_text.fsh: HUD 막대·소울 상자·사망 띠, 4배 그림) 와 GUI 그림 (position_tex_color.fsh:
  창·단추·단축 슬롯, 4배 그림) 에도 쓴다. 1배 그림 (바닐라 글꼴, 아이템) 은 정렬된 자리에서 가장 가까운 텍셀과 똑같다.

글자색 (rendertype_text_intensity.vsh)
  바닐라 흰 글 → 뼈빛, §7 → 바랜 양피지빛, 창 제목 (0x404040) → 밝은 양피지빛, 꺼진 단추 → 재, §8 → 어두운 양피지,
  §e → 옛 금빛. 그림자 (바닐라: 글자색 × 0.25, 1 GUI 픽셀 오른쪽 아래) → 따뜻한 먹, 1/2 GUI 픽셀로 당긴다 (1/12 의 배수라
  텍셀 정렬이 그대로). 기본 팩 HUD 의 표식 색 덩이 (보스 이름) 를 그대로 품는다.
"""
import json
import os

import fonts
import palette
import style

# ─────────────────────────── 글꼴 파일 ───────────────────────────

TITLE_KEYS_KR = ("menu.game", "container.crafting", "container.inventory", "container.chest", "container.chestDouble",
                 "container.barrel", "container.enderchest", "options.title", "menu.options")


def _rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _wj(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=True, indent=2)
        f.write("\n")


def vanilla_ko(key_list):
    """클라이언트 에셋의 바닐라 ko_kr 값 (창 제목의 한글을 개인 영역에 이어 두려고). 없으면 빈 표."""
    import glob
    root = os.path.join(os.path.expanduser("~"), ".cache", "souls-client", "assets")
    for idx in sorted(glob.glob(os.path.join(root, "indexes", "*.json"))):
        obj = _rj(idx)["objects"].get("minecraft/lang/ko_kr.json")
        if obj:
            h = obj["hash"]
            d = _rj(os.path.join(root, "objects", h[:2], h))
            return {k: d[k] for k in key_list if k in d}
    return {}


def write_fonts(pack):
    """TTF 넷 + 사용 허락 글. 돌려주는 값: info (파일, 개인 영역 표, 공급자)."""
    extra = fonts.lang_chars(pack)
    titles_kr = vanilla_ko(TITLE_KEYS_KR)
    pack_ko = os.path.join(pack, "assets", "minecraft", "lang", "ko_kr.json")
    if os.path.exists(pack_ko):
        d = _rj(pack_ko)
        titles_kr.update({k: d[k] for k in TITLE_KEYS_KR if k in d})
    kr_title_chars = sorted({c for v in titles_kr.values() for c in v if 0xAC00 <= ord(c) <= 0xD7A3})
    sets = {"latin": fonts.latin_set(), "hangul": fonts.hangul_set(extra)}
    info = {"files": {}, "pua_la": {}, "pua_kr": {}, "titles_kr": titles_kr}
    font_dir = os.path.join(pack, "assets", "souls", "font")
    for name, (key, wght, which, family, sty) in style.FILES.items():
        mirror = None
        if name == "title_la":
            mirror = {style.PUA_TITLE_LA: [chr(c) for c in range(0x20, 0x7F)]}
        elif name == "title_kr":
            mirror = {style.PUA_TITLE_KR: kr_title_chars}
        path, size, n, pua = fonts.make(key, wght, sets[which], os.path.join(font_dir, name + ".ttf"), family, sty,
                                        pua_mirror=mirror)
        info["files"][name] = {"path": path, "bytes": size, "glyphs": n, "key": key}
        if name == "title_la":
            info["pua_la"] = pua
        elif name == "title_kr":
            info["pua_kr"] = pua
        print(f"  글꼴 {name}: {fonts.SOURCES[key][2]} wght {wght}, 글자 {n}, {size:,} 바이트")
    lic_dir = os.path.join(font_dir, "licenses")
    os.makedirs(lic_dir, exist_ok=True)
    notice = ["Block Soul resource pack - fonts (pack/variants/mood2_refined)", "",
              "The TrueType fonts in assets/souls/font/ are subsets of the following fonts, licensed under the",
              "SIL Open Font License, Version 1.1. They were renamed (\"Souls Refined ...\") because they are modified",
              "(subset, fixed weight, layout tables removed).", ""]
    for key in sorted({v[0] for v in style.FILES.values()}):
        text = fonts.licence_text(key)
        fname = "ofl-" + fonts.SOURCES[key][2].lower().replace(" ", "-") + ".txt"
        with open(os.path.join(lic_dir, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        notice.append(f"  {fonts.SOURCES[key][2]}: {text.splitlines()[0].strip()} -> assets/souls/font/licenses/{fname}")
    with open(os.path.join(pack, "FONTS-OFL.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(notice) + "\n")
    info["providers_body"] = [ttf(n, s, y) for n, s, y in style.BODY]
    info["providers_title"] = [ttf(n, s, y) for n, s, y in style.TITLE]
    return info


def ttf(name, size, shift_y, skip=""):
    p = {"type": "ttf", "file": f"souls:{name}.ttf", "size": size, "oversample": style.OVERSAMPLE, "shift": [0.0, shift_y]}
    if skip:
        p["skip"] = skip
    return p


def write_font_defs(pack, info, extra_default=()):
    """minecraft:default (와 uniform) 에 [그림 글자 extra_default, 빈칸, 본문 TTF, 개인 영역 제목 TTF] 를 덧붙이고 souls:title 을 쓴다."""
    space = {"type": "space", "advances": {" ": style.SPACE}}
    add = list(extra_default) + [space] + info["providers_body"] + [
        ttf("title_la", style.TITLE[0][1], style.TITLE[0][2]), ttf("title_kr", style.TITLE[1][1], style.TITLE[1][2])]
    for name in ("default", "uniform"):
        p = os.path.join(pack, "assets", "minecraft", "font", name + ".json")
        d = _rj(p) if os.path.exists(p) else {"providers": []}
        d["providers"] += add
        _wj(p, d)
    _wj(os.path.join(pack, "assets", "souls", "font", "title.json"),
        {"providers": [space] + info["providers_title"] + [{"type": "reference", "id": "minecraft:default"}]})


class Measure:
    """글꼴 공급자 차례대로 글자 폭 (GUI 픽셀) 을 셈한다 (진행 폭: FreeType 의 12배 진행 폭을 정수로 / 12)."""

    def __init__(self, pack, providers, spaces=None):
        from fontTools.ttLib import TTFont
        self.fonts = []
        for p in providers:
            name = p["file"].split(":", 1)[1]
            f = TTFont(os.path.join(pack, "assets", "souls", "font", name))
            ppem = round(p["size"] * p["oversample"])
            self.fonts.append((f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm, ppem, p["oversample"]))
        self.spaces = spaces or {" ": style.SPACE}

    def char(self, ch):
        if ch in self.spaces:
            return self.spaces[ch]
        for cmap, hmtx, upm, ppem, ov in self.fonts:
            g = cmap.get(ord(ch))
            if g is not None:
                return round(hmtx[g][0] * ppem / upm) / ov
        return 0.0

    def width(self, text):
        out, i = 0.0, 0
        while i < len(text):
            if text[i] == "§" and i + 1 < len(text):
                i += 2
                continue
            out += self.char(text[i])
            i += 1
        return out


# ─────────────────────────── 셰이더 ───────────────────────────

BOX = """
// mood2_refined: exact area (box) filter. The screen pixel's footprint in texel space comes from the UV derivatives;
// every texel it touches is weighted by the overlapped area (premultiplied by alpha). With glyphs oversampled 12x
// and art at 4 texels per GUI pixel, pixel edges fall on texel edges at GUI scale 2, 3 and 4, so this is the exact
// antialiased image at that scale: flat baselines, the same stroke weight everywhere. At 1 texel per pixel it is the
// nearest texel.
vec4 souls_box(sampler2D tex, vec2 uv) {
    vec2 size = vec2(textureSize(tex, 0));
    vec2 p = uv * size;
    vec2 fw = clamp(abs(dFdx(p)) + abs(dFdy(p)), vec2(0.001), vec2(12.0));
    vec2 lo = p - 0.5 * fw;
    vec2 hi = p + 0.5 * fw;
    ivec2 i0 = ivec2(floor(lo + 0.002));
    ivec2 i1 = ivec2(ceil(hi - 0.002));
    i1 = max(i1, i0 + 1);
    ivec2 top = ivec2(size) - 1;
    vec4 acc = vec4(0.0);
    float area = 0.0;
    for (int y = i0.y; y < i1.y; y++) {
        float wy = clamp(min(hi.y, float(y + 1)) - max(lo.y, float(y)), 0.0, 1.0);
        for (int x = i0.x; x < i1.x; x++) {
            float wx = clamp(min(hi.x, float(x + 1)) - max(lo.x, float(x)), 0.0, 1.0);
            vec4 t = texelFetch(tex, clamp(ivec2(x, y), ivec2(0), top), 0);
            float w = wx * wy;
            acc += vec4(t.rgb * t.a, t.a) * w;
            area += w;
        }
    }
    acc /= max(area, 1e-6);
    if (acc.a > 0.0) acc.rgb /= acc.a;
    return acc;
}
"""

TEXT_FSH = """#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;

out vec4 fragColor;
{box}
void main() {{
    vec4 color = {sample} * vertexColor * ColorModulator;
    if (color.a < {cut}) {{
        discard;
    }}
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}}
"""

GUI_FSH = """#version 330

// Block Soul mood2_refined: vanilla position_tex_color.fsh with the box filter (4x GUI art stays even at GUI scale 3).
// Can't moj_import in things used during startup, when resource packs don't exist.
layout(std140) uniform DynamicTransforms {{
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
}};

uniform sampler2D Sampler0;

in vec2 texCoord0;
in vec4 vertexColor;

out vec4 fragColor;
{box}
void main() {{
    vec4 color = souls_box(Sampler0, texCoord0) * vertexColor;
    if (color.a == 0.0) {{
        discard;
    }}
    fragColor = color * ColorModulator;
}}
"""


def _rgb(name):
    r, g, b, _ = palette.c(name)
    return r, g, b


def _v3(rgb):
    return "vec3(%.4f, %.4f, %.4f)" % tuple(v / 255.0 for v in rgb)


REMAP = [
    ((255, 255, 255), style.TEXT),
    ((224, 224, 224), style.TEXT),
    ((170, 170, 170), style.TEXT_GREY),
    ((160, 160, 160), style.TEXT_OFF),
    ((64, 64, 64), style.TEXT_TITLE),
    ((85, 85, 85), style.TEXT_DARK),
    ((255, 255, 85), style.TEXT_GOLD),
]
PLUGIN_INKS = ["parch3", "parch2", "parch1", "parch0", "ash3", "bronze3", "bone2", "bone3", "blood3"]


def remap_block():
    sh = palette.c(style.SHADOW[0])
    sh_a = style.SHADOW[1] / 255.0
    lines = [
        "    // mood2_refined: vanilla text colours -> Dark Souls text colours; softer, closer drop shadow",
        "    if (!(mark.r == 254 && mark.g == 253) && ProjMat[3][3] == 1.0) {",
        "        bool shadow = false;",
        "        vec3 ink = Color.rgb;",
    ]
    for src, dst in REMAP:
        lines.append(f"        if (all(equal(mark, ivec3({src[0]}, {src[1]}, {src[2]})))) ink = {_v3(_rgb(dst))};")
    shadows = {tuple(int(v * 0.25) for v in src) for src, _ in REMAP}
    shadows |= {tuple(int(v * 0.25) for v in _rgb(n)) for n in PLUGIN_INKS}
    for s in sorted(shadows):
        lines.append(f"        if (all(equal(mark, ivec3({s[0]}, {s[1]}, {s[2]})))) shadow = true;")
    lines += [
        "        if (shadow) {",
        "            // pull the shadow back half a GUI pixel (vanilla offsets it by one); 1/2 is a multiple of 1/12",
        "            gl_Position.x -= 0.5 * ProjMat[0][0];",
        "            gl_Position.y -= 0.5 * ProjMat[1][1];",
        f"            ink = {_v3(sh[:3])};",
        "        }",
        f"        float a = shadow ? Color.a * {sh_a:.4f} : Color.a;",
        "        vertexColor = vec4(ink, a) * texelFetch(Sampler2, UV2 / 16, 0);",
        "    }",
        "    // the boss name's shadow (HUD marker b 5) also hugs its glyphs: half a GUI pixel instead of one",
        "    if (mark.r == 254 && mark.g == 253 && mark.b == 5 && ProjMat[3][3] == 1.0) {",
        "        gl_Position.x -= 0.5 * ProjMat[0][0];",
        "        gl_Position.y -= 0.5 * ProjMat[1][1];",
        "    }",
    ]
    return "\n".join(lines) + "\n"


def write_shaders(pack):
    core = os.path.join(pack, "assets", "minecraft", "shaders", "core")
    with open(os.path.join(core, "rendertype_text.vsh"), encoding="ascii") as f:
        base_vsh = f.read()
    head, tail = base_vsh.rsplit("}", 1)
    assert "ivec3 mark" in head, "rendertype_text.vsh 에 HUD 표식 덩이가 없다 (hud.py 가 바뀌었다)"
    vsh = head + remap_block() + "}" + tail
    vsh = vsh.replace("// Block Soul HUD (pack/hud.py).",
                      "// Block Soul HUD (pack/hud.py) + mood2_refined text colours (pack/variants/mood2_refined/text.py).", 1)
    files = {
        "rendertype_text_intensity.vsh": vsh,
        "rendertype_text_intensity.fsh": TEXT_FSH.format(
            box=BOX, sample=f"vec4(pow(souls_box(Sampler0, texCoord0).r, {style.COVERAGE_GAMMA:.3f}))", cut="0.01"),
        "rendertype_text.fsh": TEXT_FSH.format(box=BOX, sample="souls_box(Sampler0, texCoord0)", cut="0.01"),
        "position_tex_color.fsh": GUI_FSH.format(box=BOX),
    }
    for name, src in files.items():
        with open(os.path.join(core, name), "w", encoding="ascii", newline="\n") as f:
            f.write(src)
