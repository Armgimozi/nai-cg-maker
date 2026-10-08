"""
mood2_gothic 의 셰이더 (바닐라 1.21.11 셰이더에 덩이를 더한다. 기본 팩의 HUD 덩이 (pack/hud.py) 는 그대로 둔다).

  rendertype_text.vsh   기본 팩 HUD 셰이더 + GUI 글자 덩이:
                        1) 바닐라가 정한 글자색을 팔레트로 (흰 글 → 뼈빛, §7 → 흐린 옛 금빛, 꺼진 단추 → 재 …).
                        2) 그림자 사본 (글자색 × 0.25, 바닐라는 1 GUI 픽셀 오른쪽 아래) → 반 픽셀만 오른쪽 아래, 먹빛.
                           조각 셰이더에 "그림자" 라고 알린다 (gothicShadow): 우리 글자면 덮임을 2.5 텍셀 넓게 흐려 먹 테두리로.
  rendertype_text.fsh   GUI 글자·HUD 그림 글자를 화면 픽셀이 덮는 텍셀 넓이만큼 섞어 읽는다 (area filter, 넓이 평균).
                        우리 글자 텍셀 (B = 1, 알파 0, fonts.py) 은 덮임 R 을 흰 글자로, 그 밖 (바닐라 픽셀 글꼴,
                        HUD 그림) 은 알파를 곱한 평균 색. 텍셀 하나가 화면 픽셀 정수 개에 꼭 맞으면 NEAREST 와 같다.
                        세상 안 글자 (팻말, 이름표) 는 바닐라대로 (우리 글자만 쌍선형).
  rendertype_text_see_through.fsh  벽 너머 이름표: 우리 글자 텍셀을 흰 글자로.
  gui.vsh / gui.fsh     GUI 채우기. 바닐라 색 몇 가지만 알아보고 바꾼다: 창 뒤 반투명 검정 → 가장자리가 짙게 닫히는 비네트와
                        위에서 내려오는 촛불 기운, 사망 화면의 붉은 막 → 검게 닫히는 비네트 (아래에만 마른 핏빛),
                        채팅 줄 바탕 → 오른쪽으로 녹아 사라지는 먹, 시스템 알림 막대 → 청동.
  position_tex_color.*  GUI 그림 (창, 단추, 단축 슬롯 …): 텍셀 넓이 평균으로 읽는다 (2 배 그림이 GUI 배율 3 에서도 고르게).
                        게임 화면 비네트 (화면 전체 네모) 는 늘 VIGNETTE_MIN 이상 짙게.
  post_effect/blur.json 게임 중 메뉴 뒤의 흐림 뒤에 souls:post/gothic_menu (색을 빼고 어둡게, 무거운 비네트, 위에서 촛불).
"""
import json
import os

from palette import c

VIGNETTE_MIN = 0.80
SHADOW_ALPHA = 0.80


def vec3(name):
    r, g, b, _ = c(name)
    return f"vec3({r / 255:.4f}, {g / 255:.4f}, {b / 255:.4f})"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)


# GUI 글자 덩이 (rendertype_text.vsh 의 texCoord0 = UV0; 바로 뒤). 기본 팩 HUD 덩이가 그 뒤에서 표식 색 글자를 다시 칠한다.
TEXT_VSH_BLOCK = """
    // Square Soul mood2_gothic (pack/variants/mood2_gothic/shaders.py): GUI text colours and shadows.
    gothicShadow = 0.0;
    if (ProjMat[3][3] == 1.0) {
        ivec3 rgbi = ivec3(Color.rgb * 255.0 + 0.5);
        bool hudMark = rgbi.r == 254 && rgbi.g == 253 && rgbi.b >= 1 && rgbi.b <= 6;
        int hiC = max(rgbi.r, max(rgbi.g, rgbi.b));
        vec4 light = texelFetch(Sampler2, UV2 / 16, 0);
        if ((!hudMark && hiC <= 63 && hiC > 0) || (hudMark && rgbi.b == 5)) {
            // shadow copy (text colour x 0.25, drawn 1 GUI px right and down): half a pixel instead, warm ink halo
            gothicShadow = 1.0;
            if (!hudMark) vertexColor = vec4(INK, Color.a * SHADOW_A) * light;
            gl_Position.x -= 0.5 * ProjMat[0][0];
            gl_Position.y -= 0.5 * ProjMat[1][1];
        } else if (!hudMark) {
            vec3 ink = Color.rgb;
            if (rgbi == ivec3(255, 255, 255)) ink = TEXT_WHITE;
            else if (rgbi == ivec3(170, 170, 170)) ink = TEXT_GREY;
            else if (rgbi == ivec3(160, 160, 160)) ink = TEXT_OFF;
            else if (rgbi == ivec3(224, 224, 224)) ink = TEXT_WHITE;
            else if (rgbi == ivec3(85, 85, 85)) ink = TEXT_DARK;
            else if (rgbi == ivec3(64, 64, 64)) ink = TEXT_TITLE;
            else if (rgbi == ivec3(255, 255, 85)) ink = TEXT_YELLOW;
            else if (rgbi == ivec3(255, 255, 160)) ink = TEXT_HOVER;
            vertexColor = vec4(ink, Color.a) * light;
        }
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
in float gothicShadow;
in float gothicGui;

out vec4 fragColor;

// Square Soul mood2_gothic (pack/variants/mood2_gothic/shaders.py): vanilla rendertype_text.fsh, but GUI glyphs are
// read with an area (box) filter over the texels the screen pixel covers. Our pre-rasterised serif glyphs
// (fonts.py: 4 texels per GUI pixel, coverage in R, B = 1 and alpha 0 as the marker) come out
// identical at every position on GUI scales 2, 3 and 4; pixel art at 1 texel per GUI pixel is unchanged.
bool mine(vec4 t) {
    return abs(t.b * 255.0 - 1.0) < 0.5 && t.a * 255.0 < 1.5;
}

void main() {
    vec2 size = vec2(textureSize(Sampler0, 0));
    vec2 t = texCoord0 * size;
    ivec2 hiT = ivec2(size) - 1;
    vec4 centre = texelFetch(Sampler0, clamp(ivec2(floor(t)), ivec2(0), hiT), 0);
    bool ours = mine(centre);
    vec4 color;
    if (gothicGui > 0.5) {
        vec2 fp = clamp(vec2(abs(dFdx(t).x) + abs(dFdy(t).x), abs(dFdx(t).y) + abs(dFdy(t).y)), vec2(0.001), vec2(6.0));
        // shadow of our glyphs: the same coverage box-blurred over 2.5 more texels (a soft ink halo)
        vec2 fq = (ours && gothicShadow > 0.5) ? fp + vec2(2.5) : fp;
        vec2 lo = t - 0.5 * fq;
        vec2 hi = t + 0.5 * fq;
        ivec2 i0 = ivec2(floor(lo));
        ivec2 i1 = ivec2(ceil(hi)) - 1;
        float cov = 0.0;
        vec4 prem = vec4(0.0);
        for (int y = i0.y; y <= i1.y; y++) {
            float wy = min(hi.y, float(y + 1)) - max(lo.y, float(y));
            if (wy <= 0.0) continue;
            for (int x = i0.x; x <= i1.x; x++) {
                float wx = min(hi.x, float(x + 1)) - max(lo.x, float(x));
                if (wx <= 0.0) continue;
                vec4 s = texelFetch(Sampler0, clamp(ivec2(x, y), ivec2(0), hiT), 0);
                float w = wx * wy;
                if (ours) {
                    cov += w * (mine(s) ? s.r : 0.0);
                } else {
                    prem += w * vec4(s.rgb * s.a, s.a);
                }
            }
        }
        if (ours) {
            cov = clamp(cov / (fq.x * fq.y), 0.0, 1.0);
            cov = gothicShadow > 0.5 ? min(1.0, cov * 2.2) : pow(cov, GAMMA);
            color = vec4(1.0, 1.0, 1.0, cov);
        } else {
            prem /= fp.x * fp.y;
            color = prem.a > 0.0 ? vec4(prem.rgb / prem.a, prem.a) : vec4(0.0);
            if (color.a < 0.1) color.a = 0.0;
        }
        color *= vertexColor * ColorModulator;
        if (color.a < 0.004) {
            discard;
        }
    } else {
        if (ours) {
            // world text (signs, name tags): bilinear coverage
            vec2 p = t - 0.5;
            ivec2 b = ivec2(floor(p));
            vec2 f = p - vec2(b);
            float c00 = texelFetch(Sampler0, clamp(b, ivec2(0), hiT), 0).r;
            float c10 = texelFetch(Sampler0, clamp(b + ivec2(1, 0), ivec2(0), hiT), 0).r;
            float c01 = texelFetch(Sampler0, clamp(b + ivec2(0, 1), ivec2(0), hiT), 0).r;
            float c11 = texelFetch(Sampler0, clamp(b + ivec2(1, 1), ivec2(0), hiT), 0).r;
            float cov = mix(mix(c00, c10, f.x), mix(c01, c11, f.x), f.y);
            color = vec4(1.0, 1.0, 1.0, cov) * vertexColor * ColorModulator;
        } else {
            color = texture(Sampler0, texCoord0) * vertexColor * ColorModulator;
        }
        if (color.a < 0.1) {
            discard;
        }
    }
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}
"""

SEE_THROUGH_FSH = """#version 330

#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in vec4 vertexColor;
in vec2 texCoord0;

out vec4 fragColor;

// Square Soul mood2_gothic: vanilla rendertype_text_see_through.fsh; our glyph texels (B = 1, alpha 0) carry
// their coverage in R (pack/variants/mood2_gothic/fonts.py).
void main() {
    vec4 t = texture(Sampler0, texCoord0);
    if (abs(t.b * 255.0 - 1.0) < 0.5 && t.a * 255.0 < 1.5) t = vec4(1.0, 1.0, 1.0, t.r);
    vec4 color = t * vertexColor;
    if (color.a < 0.1) {
        discard;
    }
    fragColor = color * ColorModulator;
}
"""


def text_vsh(base_vsh, st):
    s = base_vsh
    assert "out vec2 texCoord0;\n" in s and "    texCoord0 = UV0;\n" in s, "기본 팩 rendertype_text.vsh 가 바뀌었다"
    s = s.replace("out vec2 texCoord0;\n", "out vec2 texCoord0;\nout float gothicShadow;\nout float gothicGui;\n", 1)
    block = TEXT_VSH_BLOCK
    for k, v in (("TEXT_WHITE", vec3(st.TEXT)), ("TEXT_GREY", vec3(st.TEXT_GREY)), ("TEXT_OFF", vec3(st.TEXT_OFF)),
                 ("TEXT_DARK", vec3(st.TEXT_DARK)), ("TEXT_TITLE", vec3(st.TEXT_TITLE)),
                 ("TEXT_YELLOW", vec3(st.TEXT_YELLOW)), ("TEXT_HOVER", vec3(st.TEXT_HOVER)),
                 ("INK", vec3("ink0")), ("SHADOW_A", f"{SHADOW_ALPHA:.3f}")):
        block = block.replace(k, v)
    block = "    gothicGui = ProjMat[3][3] == 1.0 ? 1.0 : 0.0;\n" + block
    s = s.replace("    texCoord0 = UV0;\n", "    texCoord0 = UV0;\n" + block, 1)
    return s


def build_text(pack, st):
    core = os.path.join(pack, "assets", "minecraft", "shaders", "core")
    with open(os.path.join(core, "rendertype_text.vsh"), encoding="utf-8") as f:
        base = f.read()
    write(os.path.join(core, "rendertype_text.vsh"), text_vsh(base, st))
    write(os.path.join(core, "rendertype_text.fsh"), TEXT_FSH.replace("GAMMA", f"{st.TEXT_GAMMA:.3f}"))
    write(os.path.join(core, "rendertype_text_see_through.fsh"), SEE_THROUGH_FSH)
