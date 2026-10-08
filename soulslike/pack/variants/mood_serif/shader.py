"""
mood_serif 글꼴 셰이더. TTF 글자 (와 유니폰트) 는 rendertype_text_intensity 로 그려진다 (GUI 는 pipeline/gui_text_intensity,
같은 셰이더 파일).

vsh  = 이 팩의 rendertype_text.vsh (hud.py: HUD 표식 색의 글자를 옮기는 덩이) 를 그대로 베끼고 한 덩이를 더한다:
       바닐라가 정한 글자색을 다크 소울의 글자색으로 바꾼다 (style.py). 흰 글 → 뼈빛, §7 → 흐린 옛 금빛, 꺼진 단추 → 재,
       §e → 옛 금빛. 그림자 (바닐라는 글자색 × 0.25 를 1 GUI 픽셀 오른쪽 아래에 그린다) 는 먹빛 반투명으로 바꾸고
       0.5 GUI 픽셀 안쪽으로 당긴다 (GUI 배율 4 에서 4 화면 픽셀 어긋난 두 겹 글씨가 마인크래프트 티였다).
       보스 이름 (표식 색 b 4) 은 hud.py 처럼 옮기고 색을 준다. 소울 숫자는 그림 글자라 여기를 지나지 않는다.
fsh  = 글리프 아틀라스를 손으로 쌍선형 보간한다. 바닐라는 가장 가까운 텍셀을 집어 GUI 배율 3·2 에서 획 굵기가 들쭉날쭉했다.
       oversample 4 의 글리프가 배율 4 에서는 한 텍셀 = 한 화면 픽셀 (텍셀 가운데를 집으므로 그대로), 배율 3·2 에서는 부드럽게
       줄어든다.
"""
import os

import palette
import style


def _rgb(name):
    r, g, b, _ = palette.c(name)
    return r, g, b


def _v3(rgb):
    return "vec3(%.4f, %.4f, %.4f)" % tuple(v / 255.0 for v in rgb)


# 바닐라 글자색 → 시안 글자색. 왼쪽은 바닐라가 쓰는 값 그대로 (0..255)
REMAP = [
    ((255, 255, 255), style.TEXT),      # 기본 흰 글, §f
    ((224, 224, 224), style.TEXT),      # 입력 칸 글 (0xE0E0E0)
    ((170, 170, 170), style.TEXT_GREY),  # §7: 창 제목, 사망 화면 단추 (lang 이 § 코드로 준다)
    ((160, 160, 160), style.TEXT_OFF),   # 꺼진 단추
    ((64, 64, 64), style.TEXT_GREY),     # 바닐라 창 제목 기본 (0x404040, 밝은 판 위의 글이라 어두운 판에서는 흐린 금빛으로)
    ((85, 85, 85), style.TEXT_DARK),     # §8
    ((255, 255, 85), "bronze3"),         # §e (들어옴·나감 알림): 옛 금빛
]
# 플러그인이 언어 파일 꼴로 주는 글자색 (lang/*.yml). 색은 그대로 두고 그림자만 바꾼다
PLUGIN_INKS = ["parch3", "parch2", "parch1", "parch0", "ash3", "bronze3", "bone2", "bone3", "blood3"]


def _shadow(rgb):
    return tuple(int(v * 0.25) for v in rgb)


def remap_block():
    sh = palette.c(style.SHADOW[0])
    sh_a = style.SHADOW[1] / 255.0
    lines = [
        "    // mood_serif: vanilla text colours -> Dark Souls text colours, softer and closer drop shadow",
        "    if (!(mark.r == 254 && mark.g == 253)) {",
        "        bool shadow = false;",
        "        vec3 ink = Color.rgb;",
    ]
    for src, dst in REMAP:
        lines.append(f"        if (all(equal(mark, ivec3({src[0]}, {src[1]}, {src[2]})))) ink = {_v3(_rgb(dst))};")
    shadows = set()
    for src, _ in REMAP:
        shadows.add(_shadow(src))
    for name in PLUGIN_INKS:
        shadows.add(_shadow(_rgb(name)))
    for s in sorted(shadows):
        lines.append(f"        if (all(equal(mark, ivec3({s[0]}, {s[1]}, {s[2]})))) shadow = true;")
    lines += [
        "        if (shadow && ProjMat[3][3] == 1.0) {",
        "            // pull the shadow half a GUI pixel back towards its glyph (vanilla offsets it by one)",
        "            gl_Position.x -= 0.5 * ProjMat[0][0];",
        "            gl_Position.y -= 0.5 * ProjMat[1][1];",
        f"            ink = {_v3(sh[:3])};",
        "        }",
        f"        float a = shadow ? Color.a * {sh_a:.4f} : Color.a;",
        "        vertexColor = vec4(ink, a) * texelFetch(Sampler2, UV2 / 16, 0);",
        "    }",
    ]
    return "\n".join(lines) + "\n"


FSH = """#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;

out vec4 fragColor;

// mood_serif: hand-made bilinear sampling of the glyph atlas (vanilla picks the nearest texel, which made the
// oversampled TrueType glyphs ragged at GUI scale 3 and 2).
float glyph(vec2 uv) {
    vec2 size = vec2(textureSize(Sampler0, 0));
    vec2 p = uv * size - 0.5;
    vec2 f = fract(p);
    ivec2 i = ivec2(floor(p));
    ivec2 hi = ivec2(size) - 1;
    float a = texelFetch(Sampler0, clamp(i, ivec2(0), hi), 0).r;
    float b = texelFetch(Sampler0, clamp(i + ivec2(1, 0), ivec2(0), hi), 0).r;
    float c = texelFetch(Sampler0, clamp(i + ivec2(0, 1), ivec2(0), hi), 0).r;
    float d = texelFetch(Sampler0, clamp(i + ivec2(1, 1), ivec2(0), hi), 0).r;
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
    vec4 color = vec4(glyph(texCoord0)) * vertexColor * ColorModulator;
    if (color.a < 0.1) {
        discard;
    }
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}
"""


def build(pack):
    core = os.path.join(pack, "assets", "minecraft", "shaders", "core")
    with open(os.path.join(core, "rendertype_text.vsh"), encoding="ascii") as f:
        text = f.read()
    # HUD 덩이의 끝 (main 의 마지막 닫는 괄호) 앞에 색 바꾸기 덩이를 넣는다. mark 는 HUD 덩이가 이미 셈했다
    head, tail = text.rsplit("}", 1)
    assert "ivec3 mark" in head, "rendertype_text.vsh 에 HUD 표식 덩이가 없다 (hud.py 가 바뀌었다)"
    out = head + remap_block() + "}" + tail
    out = out.replace("// Square Soul HUD (pack/hud.py).",
                      "// Square Soul HUD (pack/hud.py) + mood_serif text colours (pack/variants/mood_serif/shader.py).", 1)
    with open(os.path.join(core, "rendertype_text_intensity.vsh"), "w", encoding="ascii", newline="\n") as f:
        f.write(out)
    with open(os.path.join(core, "rendertype_text_intensity.fsh"), "w", encoding="ascii", newline="\n") as f:
        f.write(FSH)
