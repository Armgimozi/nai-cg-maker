"""
팩의 셰이더 (DESIGN.md 10.8). 모두 바닐라 1.21.11 jar 의 원본에 덩이를 더한 것이고 ASCII 만 쓴다 (주석까지). gen_pack.py 가 부른다.

  rendertype_text.vsh   hud.py 의 HUD 덩이 (표식 색 글자를 화면 가장자리로) + GUI 글자 덩이:
                        1) 바닐라가 정한 글자색을 팔레트로 (흰 글 → 뼈빛, §7 → 흐린 옛 금빛, 꺼진 단추 → 재 …, TEXT_*).
                        2) 그림자 사본 (글자색 × 0.25, 바닐라는 1 GUI 픽셀 오른쪽 아래) → 반 픽셀만 오른쪽 아래, 먹빛.
                           조각 셰이더에 "그림자" 라고 알린다 (soulsShadow): 우리 글자면 덮임을 2.5 텍셀 넓게 흐려 먹 테두리로.
  rendertype_text.fsh   GUI 글자·HUD 그림 글자를 화면 픽셀이 덮는 텍셀 넓이만큼 섞어 읽는다 (area filter, 넓이 평균).
                        우리 글자 텍셀 (B = 1, 알파 0, fonts.py) 은 덮임 R 을 흰 글자로, 그 밖 (HUD 그림) 은 알파를 곱한 평균 색.
                        텍셀 하나가 화면 픽셀 정수 개에 꼭 맞으면 NEAREST 와 같다. 세상 안 글자 (팻말, 이름표) 는 우리 글자만
                        쌍선형으로 읽는다. 우리 글자는 알파가 0 이라 이 셰이더가 없으면 보이지 않는다 (글꼴의 일부).
  rendertype_text_see_through.fsh  벽 너머 이름표: 우리 글자 텍셀을 흰 글자로 (없으면 벽 너머 이름이 사라진다).
  gui.vsh / gui.fsh     GUI 채우기. 바닐라 색 몇 가지만 알아보고 바꾼다: 창 뒤 반투명 검정 → 가장자리가 짙게 닫히는 비네트와
                        위에서 내려오는 촛불 기운, 사망 화면의 붉은 막 → 검게 닫히는 비네트 (아래에만 마른 핏빛),
                        채팅 줄 바탕 → 오른쪽으로 녹아 사라지는 먹, 시스템 알림 막대 → 청동, 불투명 순백 줄 (발전 과제
                        잇는 줄, 고른 탭 밑줄, 초점 테) → 바랜 양피지 (GUI_WHITE, 2026-10-08 비평: UI 에서 순백은 이것뿐).
  position_tex_color.*  GUI 그림 (창, 단추, 단축 슬롯 …): 텍셀 넓이 평균으로 읽는다 (2 배 그림이 GUI 배율 3 에서도 고르게,
                        uidraw.py). 게임 화면 비네트 (화면 전체 네모) 는 늘 VIGNETTE_MIN 이상 짙게.
  post_effect/blur.json 게임 중 메뉴 뒤의 흐림 (바닐라 여섯 번) 뒤에 souls:post/menu_dim (색을 빼고 어둡게, 무거운 비네트,
                        위에서 촛불). textures/misc/vignette.png 는 게임 화면 비네트의 세기 (회색, 바닐라처럼).
이 밖의 셰이더는 구르기 대역의 아이템 셰이더 (roll_figure.py) 뿐이다. make_dist 와 봇 join 이 목록 (ALLOWED) 밖의 셰이더를 막는다.
"""
import json
import os

import hud
from palette import c

VIGNETTE_MIN = 0.80
SHADOW_ALPHA = 0.80
TEXT_GAMMA = 0.86               # 덮임 ** GAMMA (1 보다 작으면 가는 획이 조금 짙게. 밝은 글을 어두운 바탕에 섞으면 가늘어 보인다)
# 바닐라가 정한 글자색 → 팔레트
TEXT = "bone2"                  # 흰 글 (단추, 화면 제목, 채팅, 개수)
TEXT_GREY = "parch2"            # §7 (#AAAAAA): 창 제목·부제 → 흐린 옛 금빛
TEXT_OFF = "ash3"               # 꺼진 단추 (#A0A0A0)
TEXT_DARK = "parch0"            # §8 (#555555)
TEXT_TITLE = "parch2"           # 바닐라 창 제목 (#404040)
TEXT_YELLOW = "parch3"          # §e (들어옴/나감 알림), 발전 과제 알림의 노랑 (#FFFF00)·도전 과제의 분홍 (#FF88FF)
TEXT_HOVER = "glim0"            # 가리킨 단추 글 (#FFFFA0)
GUI_WHITE = "parch2"            # 바닐라 코드가 순백 (#FFFFFF, 불투명) 으로 긋는 GUI 줄

CORE = "assets/minecraft/shaders/core/"
# 팩에 들어가는 셰이더 전부 (make_dist·봇 join 이 같은 목록을 본다, 10.8). 구르기 대역의 둘은 roll_figure.py 가 쓴다
TEXT_SHADERS = (CORE + "rendertype_text.vsh", CORE + "rendertype_text.fsh", CORE + "rendertype_text_see_through.fsh")
GUI_SHADERS = (CORE + "gui.vsh", CORE + "gui.fsh", CORE + "position_tex_color.vsh", CORE + "position_tex_color.fsh",
               "assets/souls/shaders/post/menu_dim.fsh")
ROLL_SHADERS = (CORE + "rendertype_item_entity_translucent_cull.vsh", CORE + "rendertype_item_entity_translucent_cull.fsh")
ALLOWED = TEXT_SHADERS + GUI_SHADERS + ROLL_SHADERS


def vec3(name):
    r, g, b, _ = c(name)
    return f"vec3({r / 255:.4f}, {g / 255:.4f}, {b / 255:.4f})"


def write(path, text):
    assert all(ord(ch) < 128 for ch in text), f"{path}: 셰이더에는 ASCII 만"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)


# GUI 글자 덩이 (rendertype_text.vsh 의 texCoord0 = UV0; 바로 뒤). HUD 덩이가 그 뒤에서 표식 색 글자를 다시 칠한다.
TEXT_VSH_BLOCK = """
    // Block Soul (pack/shaders.py): GUI text colours and shadows.
    soulsShadow = 0.0;
    soulsDeathT = 1.0e6;
    soulsVeil = vec2(0.0);
    if (ProjMat[3][3] == 1.0) {
        ivec3 rgbi = ivec3(Color.rgb * 255.0 + 0.5);
        bool hudMark = rgbi.r == 254 && rgbi.g == 253 && rgbi.b >= 1 && rgbi.b <= 7;
        int hiC = max(rgbi.r, max(rgbi.g, rgbi.b));
        vec4 light = texelFetch(Sampler2, UV2 / 16, 0);
        bool deathMain = rgbi.r == DEATH_R && rgbi.g >= DEATH_G0 && rgbi.g <= DEATH_G0 + 93;
        bool deathShadow = rgbi.r == DEATH_SHADOW_R && rgbi.g >= DEATH_G0 && rgbi.g <= DEATH_G0 + 93;
        if (deathMain || deathShadow) {
            // fading YOU DIED (death screen message line, pack/hud.py): the colour carries the game time of death
            // t = (g - G0) * 256 + b (game time % 24000); ticks since death -> the fragment shader fades band and letters in
            float t0 = float((rgbi.g - DEATH_G0) * 256 + rgbi.b);
            float dt = GameTime * 24000.0 - t0;
            if (dt < -12000.0) dt += 24000.0;
            else if (dt > 12000.0) dt -= 24000.0;
            // only a few ticks of latency can make dt negative; beyond that (or long after death) show at once
            soulsDeathT = (dt < -DEATH_EARLY || dt > DEATH_WAIT) ? 1.0e6 : dt;
            // the button veil's shape is set from the GUI position: x from the screen centre, y from the top of the
            // death screen's two buttons (vanilla: GUI height / 4 + VEIL_BTN)
            float guiW = ceil(2.0 / ProjMat[0][0] - 0.01);
            float guiH = ceil(-2.0 / ProjMat[1][1] - 0.01);
            vec2 at = (ModelViewMat * vec4(Position, 1.0)).xy;
            soulsVeil = vec2(at.x - guiW * 0.5, at.y - (floor(guiH * 0.25) + VEIL_BTN));
            if (deathShadow) {
                // like the death screen title's shadow (2x: 2 GUI px, see below -0.5): 1.5 GUI px right and down, ink
                soulsShadow = 1.0;
                vertexColor = vec4(INK, Color.a * SHADOW_A) * light;
                gl_Position.x += 0.5 * ProjMat[0][0];
                gl_Position.y += 0.5 * ProjMat[1][1];
            } else {
                vertexColor = vec4(TEXT_WHITE, Color.a) * light;
            }
        } else if ((!hudMark && hiC <= 63 && hiC > 0) || (hudMark && rgbi.b == 5)) {
            // shadow copy (text colour x 0.25, drawn 1 GUI px right and down): half a pixel instead, warm ink halo
            soulsShadow = 1.0;
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
            else if (rgbi == ivec3(255, 255, 0) || rgbi == ivec3(255, 136, 255)) ink = TEXT_YELLOW;
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
in float soulsShadow;
in float soulsGui;
in float soulsDeathT;
in vec2 soulsVeil;

out vec4 fragColor;

// Block Soul (pack/shaders.py): vanilla rendertype_text.fsh, but GUI glyphs are
// read with an area (box) filter over the texels the screen pixel covers. Our pre-rasterised serif glyphs
// (pack/fonts.py: 4 texels per GUI pixel, coverage in R, B = 1 and alpha 0 as the marker) come out
// identical at every position on GUI scales 2, 3 and 4; pixel art at 1 texel per GUI pixel is unchanged.
bool mine(vec4 t) {
    return abs(t.b * 255.0 - 1.0) < 0.5 && t.a * 255.0 < 1.5;
}

// the YOU DIED band (pack/hud.py death_band): an alpha map whose texels are all RGB (0, 0, 2), painted ink here.
// Its soft tails are kept (no 0.1 cut) and the vanilla shadow copy is not drawn (the band would double up).
bool band(vec4 t) {
    return t.r * 255.0 < 0.5 && t.g * 255.0 < 0.5 && abs(t.b * 255.0 - 2.0) < 0.5;
}

// the death screen button veil (pack/hud.py death_veil): an opaque plate of RGB (0, 0, 3); its shape is computed here
bool veil(vec4 t) {
    return t.r * 255.0 < 0.5 && t.g * 255.0 < 0.5 && abs(t.b * 255.0 - 3.0) < 0.5;
}

void main() {
    vec2 size = vec2(textureSize(Sampler0, 0));
    vec2 t = texCoord0 * size;
    ivec2 hiT = ivec2(size) - 1;
    vec4 centre = texelFetch(Sampler0, clamp(ivec2(floor(t)), ivec2(0), hiT), 0);
    bool ours = mine(centre);
    bool isBand = band(centre);
    bool isVeil = veil(centre);
    vec4 color;
    if (soulsGui > 0.5) {
        if ((isBand || isVeil) && soulsShadow > 0.5) {
            discard;
        }
        if (isVeil && soulsDeathT > 1.0e5) {
            // no death clock (not the fading line, or too long after death): the buttons stay clear
            discard;
        }
        vec2 fp = clamp(vec2(abs(dFdx(t).x) + abs(dFdy(t).x), abs(dFdx(t).y) + abs(dFdy(t).y)), vec2(0.001), vec2(6.0));
        // shadow of our glyphs: the same coverage box-blurred over 2.5 more texels (a soft ink halo)
        vec2 fq = (ours && soulsShadow > 0.5) ? fp + vec2(2.5) : fp;
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
            cov = soulsShadow > 0.5 ? min(1.0, cov * 2.2) : pow(cov, GAMMA);
            color = vec4(1.0, 1.0, 1.0, cov);
        } else if (isVeil) {
            // flat over the buttons (x within VEIL_FLAT of the centre, y over the button block and VEIL_PAD more),
            // smoothstep to nothing out to VEIL_HALF across and over VEIL_SOFT above and below
            float vx = 1.0 - smoothstep(VEIL_FLAT, VEIL_HALF, abs(soulsVeil.x));
            float d = max(-VEIL_PAD - soulsVeil.y, soulsVeil.y - (VEIL_BLOCK + VEIL_PAD));
            float vy = 1.0 - smoothstep(0.0, VEIL_SOFT, d);
            color = vec4(BAND_INK, VEIL_A * vx * vy);
        } else if (isBand) {
            color = vec4(BAND_INK, prem.a / (fp.x * fp.y));
        } else {
            prem /= fp.x * fp.y;
            color = prem.a > 0.0 ? vec4(prem.rgb / prem.a, prem.a) : vec4(0.0);
            if (color.a < 0.1) color.a = 0.0;
        }
        color *= vertexColor * ColorModulator;
        if (soulsDeathT < 1.0e5) {
            // fading YOU DIED: the band first, the letters out of it, then the veil lifts off the buttons
            // (ticks since death, see rendertype_text.vsh)
            color.a *= isVeil ? 1.0 - smoothstep(VEIL_T0, VEIL_T1, soulsDeathT)
                     : isBand ? smoothstep(DEATH_BAND_T0, DEATH_BAND_T1, soulsDeathT)
                              : smoothstep(DEATH_LETTERS_T0, DEATH_LETTERS_T1, soulsDeathT);
        }
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

// Block Soul (pack/shaders.py): vanilla rendertype_text_see_through.fsh; our glyph texels (B = 1, alpha 0) carry
// their coverage in R (pack/fonts.py).
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



GUI_VSH = """#version 330

// Can't moj_import in things used during startup, when resource packs don't exist.
// This is a copy of dynamicimports.glsl and projection.glsl
layout(std140) uniform DynamicTransforms {
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
};
layout(std140) uniform Projection {
    mat4 ProjMat;
};

in vec3 Position;
in vec4 Color;

out vec4 vertexColor;
out vec3 soulsFill;
out float soulsX;

// Block Soul (pack/shaders.py): vanilla gui.vsh plus flags for a few vanilla fills:
// container screen dim (0xC0101010..0xD0101010) -> 1, death screen red wash (0x60500000 / 0xA0803030) -> 2,
// chat line backdrop (black, translucent) -> 3; the chat "system message" bar (0xD0D0D0) becomes bronze;
// opaque pure white lines (advancement connectors, the selected tab underline, focus outlines) become pale parchment.
void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    vertexColor = Color;
    ivec4 c = ivec4(Color * 255.0 + 0.5);
    float mode = 0.0;
    if (c.rgb == ivec3(16, 16, 16) && (c.a == 192 || c.a == 208)) mode = 1.0;
    else if (c == ivec4(80, 0, 0, 96) || c == ivec4(128, 48, 48, 160)) mode = 2.0;
    else if (c.rgb == ivec3(208, 208, 208)) vertexColor = vec4(BRONZE, Color.a * 0.85);
    else if (c == ivec4(255, 255, 255, 255)) vertexColor = vec4(PARCH, 1.0);
    else if (c.rgb == ivec3(0, 0, 0) && c.a > 0 && c.a < 200) mode = 3.0;
    soulsFill = vec3(gl_Position.xy / gl_Position.w, mode);
    soulsX = (gl_Position.x / gl_Position.w + 1.0) / ProjMat[0][0];
}
"""

GUI_FSH = """#version 330

// Can't moj_import in things used during startup, when resource packs don't exist.
// This is a copy of dynamicimports.glsl
layout(std140) uniform DynamicTransforms {
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
};

in vec4 vertexColor;
in vec3 soulsFill;
in float soulsX;

out vec4 fragColor;

// Block Soul (pack/shaders.py): the flagged fills become deep vignettes with a little candle light from above (see gui.vsh).
void main() {
    vec4 color = vertexColor;
    if (soulsFill.z > 2.5) {
        // chat: warm ink that dissolves to the right instead of a hard black box
        color = vec4(INK, min(0.82, color.a * 1.5) * (1.0 - smoothstep(140.0, 330.0, soulsX)));
    } else if (soulsFill.z > 0.5) {
        vec2 p = soulsFill.xy;
        float r = length(p * vec2(0.86, 1.0));
        if (soulsFill.z < 1.5) {
            float a = mix(0.70, 0.98, smoothstep(0.25, 1.30, r));
            float candle = 1.0 - smoothstep(0.0, 1.0, length((p - vec2(0.0, 1.15)) * vec2(0.70, 1.40)));
            color = vec4(mix(INK, BRONZE1, 0.30 * candle), a - 0.12 * candle);
        } else {
            float a = mix(0.50, 0.97, smoothstep(0.20, 1.30, r));
            float low = smoothstep(0.1, -1.0, p.y);
            color = vec4(mix(INK, BLOOD, 0.55 * low), a);
        }
    }
    if (color.a == 0.0) {
        discard;
    }
    fragColor = color * ColorModulator;
}
"""

PTC_VSH = """#version 330

// Can't moj_import in things used during startup, when resource packs don't exist.
// This is a copy of dynamicimports.glsl and projection.glsl
layout(std140) uniform DynamicTransforms {
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
};
layout(std140) uniform Projection {
    mat4 ProjMat;
};

in vec3 Position;
in vec2 UV0;
in vec4 Color;

uniform sampler2D Sampler0;

out vec2 texCoord0;
out vec4 vertexColor;
out float soulsGui;

// Block Soul (pack/shaders.py): vanilla position_tex_color.vsh plus
//  * a flag for GUI quads (orthographic): the fragment shader reads their texture with an area filter;
//  * the in-game vignette (the only full-screen GUI quad with texture 0..1 on the screen corners, drawn in a grey below
//    white) is kept at least VIGNETTE_MIN strong, so the corners always close in (misc/vignette.png gives the shape);
//  * no slot highlight on the three erased slots of the player inventory (its 2x2 crafting grid is two ring slots now:
//    only the left column is drawn, DESIGN 9.4). The client still hovers the right column and the result slot. The two
//    highlight sprites (container/slot_highlight_back, _front, 24x24 drawn as one quad) carry an invisible mark in each
//    corner texel (alpha 1, a different ash colour per corner, pack/gui_skin.py HIGHLIGHT_MARKS). A vertex reads the texel
//    half a texel inside each diagonal of its UV; the mark it finds tells which corner it is, hence the quad origin. If
//    that origin is an erased slot (slot - 4) of a 176x166 screen centred like the inventory (recipe book shut, or open
//    and pushed right), the vertex goes off screen, so the whole quad is dropped.
//    The test only knows positions, not screens, so another screen loses the highlight on a slot that lands exactly on an
//    erased one (DESIGN 9.4 known limit 2): the hopper (176x133) fifth slot (116,20) at even scaled GUI heights, the
//    shulker box (176x167) slots (116,18) and (116,36) at odd scaled heights, and the donkey, mule and llama chest
//    slots (116,18) and (116,36). Chests, barrels, ender chests (168 tall) and the furnace result (116,35) never land.

bool soulsMark(vec2 uv, ivec3 rgb) {
    ivec4 t = ivec4(textureLod(Sampler0, uv, 0.0) * 255.0 + 0.5);
    return t.a == 1 && t.rgb == rgb;
}

bool soulsErasedSlot(vec2 o) {
    vec2 screen = ceil(vec2(2.0 / ProjMat[0][0], -2.0 / ProjMat[1][1]) - 0.01);
    float top = floor((screen.y - 166.0) / 2.0);
    for (int k = 0; k < 2; k++) {
        float left = floor((screen.x - 176.0) / 2.0);
        if (k == 1) {
            if (screen.x < 379.0) break;
            left = 177.0 + floor((screen.x - 376.0) / 2.0);
        }
        vec2 p = o - vec2(left, top);
ERASED_TESTS
    }
    return false;
}

void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
    if (ProjMat[3][3] == 1.0) {
        vec2 h = 0.5 / vec2(textureSize(Sampler0, 0));
        vec2 at = (ModelViewMat * vec4(Position, 1.0)).xy;
        vec2 o = vec2(-1000.0);
        if (soulsMark(UV0 + vec2(h.x, h.y), MARK_TL)) o = at;
        else if (soulsMark(UV0 + vec2(-h.x, h.y), MARK_TR)) o = at - vec2(24.0, 0.0);
        else if (soulsMark(UV0 + vec2(h.x, -h.y), MARK_BL)) o = at - vec2(0.0, 24.0);
        else if (soulsMark(UV0 + vec2(-h.x, -h.y), MARK_BR)) o = at - vec2(24.0, 24.0);
        if (o.x > -999.0 && soulsErasedSlot(o)) {
            gl_Position = vec4(3.0, 3.0, 0.0, 1.0);
        }
    }

    texCoord0 = UV0;
    vertexColor = Color;
    soulsGui = ProjMat[3][3] == 1.0 ? 1.0 : 0.0;
    if (ProjMat[3][3] == 1.0 && Color.a > 0.999 && Color.r < 0.999 && Color.r == Color.g && Color.g == Color.b) {
        vec2 screen = vec2(2.0 / ProjMat[0][0], -2.0 / ProjMat[1][1]);
        vec2 at = (ModelViewMat * vec4(Position, 1.0)).xy;
        bool cornerX = (abs(at.x) < 0.01 && UV0.x == 0.0) || (abs(at.x - screen.x) < 0.51 && UV0.x == 1.0);
        bool cornerY = (abs(at.y) < 0.01 && UV0.y == 0.0) || (abs(at.y - screen.y) < 0.51 && UV0.y == 1.0);
        if (cornerX && cornerY) {
            vertexColor.rgb = vec3(mix(VIGNETTE_MIN, 1.0, Color.r));
        }
    }
}
"""

PTC_FSH = """#version 330

// Can't moj_import in things used during startup, when resource packs don't exist.
// This is a copy of dynamicimports.glsl
layout(std140) uniform DynamicTransforms {
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
};

uniform sampler2D Sampler0;

in vec2 texCoord0;
in vec4 vertexColor;
in float soulsGui;

out vec4 fragColor;

// Block Soul (pack/shaders.py): vanilla position_tex_color.fsh, but GUI sprites are read with an area (box) filter over the
// texels the screen pixel covers. Our UI art is drawn at 2 texels per GUI pixel; at GUI scale 3 a texel is 1.5 screen
// pixels and nearest sampling made lines 1 or 2 pixels thick by position. 1:1 art is unchanged.
void main() {
    vec4 color;
    vec2 size = vec2(textureSize(Sampler0, 0));
    vec2 t = texCoord0 * size;
    vec2 fp = clamp(vec2(abs(dFdx(t).x) + abs(dFdy(t).x), abs(dFdx(t).y) + abs(dFdy(t).y)), vec2(0.001), vec2(4.0));
    // one texel per screen pixel (items from the GUI item atlas, 2x art at GUI scale 2, 1x art at scale 1): plain nearest
    // like vanilla, so a quad that is not texel-aligned never bleeds a neighbouring atlas cell into its edge
    bool oneToOne = all(greaterThan(fp, vec2(0.99))) && all(lessThan(fp, vec2(1.01)));
    if (soulsGui > 0.5 && !oneToOne) {
        vec2 lo = t - 0.5 * fp;
        vec2 hi = t + 0.5 * fp;
        ivec2 i0 = ivec2(floor(lo));
        ivec2 i1 = ivec2(ceil(hi)) - 1;
        ivec2 hiT = ivec2(size) - 1;
        vec4 prem = vec4(0.0);
        for (int y = i0.y; y <= i1.y; y++) {
            float wy = min(hi.y, float(y + 1)) - max(lo.y, float(y));
            if (wy <= 0.0) continue;
            for (int x = i0.x; x <= i1.x; x++) {
                float wx = min(hi.x, float(x + 1)) - max(lo.x, float(x));
                if (wx <= 0.0) continue;
                vec4 s = texelFetch(Sampler0, clamp(ivec2(x, y), ivec2(0), hiT), 0);
                prem += wx * wy * vec4(s.rgb * s.a, s.a);
            }
        }
        prem /= fp.x * fp.y;
        color = prem.a > 0.0 ? vec4(prem.rgb / prem.a, prem.a) : vec4(0.0);
        color *= vertexColor;
    } else {
        color = texture(Sampler0, texCoord0) * vertexColor;
    }
    if (color.a == 0.0) {
        discard;
    }
    fragColor = color * ColorModulator;
}
"""



def ptc_vsh():
    """GUI 그림 꼭짓점 셰이더: 표식 색 (gui_skin.HIGHLIGHT_MARKS) 과 지운 칸 (gui_skin.CONTAINER_LAYOUTS 인벤토리의 erased) 을 채운다."""
    import gui_skin
    marks = {}
    for (x, y), name in gui_skin.HIGHLIGHT_MARKS.items():
        r, g, b, _ = c(name)
        key = ("T" if y == 0 else "B") + ("L" if x == 0 else "R")
        marks["MARK_" + key] = f"ivec3({r}, {g}, {b})"
    tests = []
    for x, y, w, h in gui_skin.CONTAINER_LAYOUTS["inventory"]["erased"]:
        # 바닐라 칸 상자 (x, y) 의 칸 자리는 (x + 1, y + 1), 가리킴 그림은 칸 자리 - 4 에서 24×24
        ox, oy = x + 1 - 4, y + 1 - 4
        tests.append(f"        if (all(lessThan(abs(p - vec2({ox:.1f}, {oy:.1f})), vec2(0.01)))) return true;")
    out = PTC_VSH.replace("VIGNETTE_MIN", f"{VIGNETTE_MIN:.3f}").replace("ERASED_TESTS", "\n".join(tests))
    for k, v in marks.items():
        out = out.replace(k, v)
    return out


def menu_fsh():
    return f"""#version 330

uniform sampler2D InSampler;

layout(std140) uniform SamplerInfo {{
    vec2 OutSize;
    vec2 InSize;
}};

in vec2 texCoord;

out vec4 fragColor;

// Block Soul (pack/shaders.py): after the vanilla menu blur, drain the colour, darken, close in with a heavy vignette and
// let a little warm candle light fall from above.
void main() {{
    vec3 c = texture(InSampler, texCoord).rgb;
    vec2 p = texCoord * 2.0 - 1.0;
    float aspect = OutSize.x / max(OutSize.y, 1.0);
    float r = length(vec2(p.x * min(aspect, 1.9) / 1.6, p.y));
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    vec3 col = mix(c, vec3(lum) * {vec3("bone1")} * 1.5, 0.5);
    col *= mix(0.55, 0.08, smoothstep(0.15, 1.25, r));
    float candle = 1.0 - smoothstep(0.0, 1.0, length((p - vec2(0.0, 1.15)) * vec2(0.65, 1.35)));
    col += {vec3("bronze1")} * 0.18 * candle;
    fragColor = vec4(col, 1.0);
}}
"""




def text_vsh():
    """hud.py 의 HUD 셰이더 (바닐라 rendertype_text.vsh + HUD 덩이) 에 GUI 글자 덩이를 더한다."""
    s = hud.hud_shader()
    assert "out vec2 texCoord0;\n" in s and "    texCoord0 = UV0;\n" in s, "hud.py 의 HUD 셰이더 꼴이 바뀌었다"
    s = s.replace("out vec2 texCoord0;\n",
                  "out vec2 texCoord0;\nout float soulsShadow;\nout float soulsGui;\nout float soulsDeathT;\n"
                  "out vec2 soulsVeil;\n", 1)
    # 서서히 나타나는 YOU DIED (5.6) 가 GameTime (globals.glsl) 을 읽는다
    imp = "#moj_import <minecraft:projection.glsl>\n"
    assert imp in s, "hud.py 의 HUD 셰이더 꼴이 바뀌었다 (projection import)"
    s = s.replace(imp, imp + "#moj_import <minecraft:globals.glsl>\n", 1)
    block = TEXT_VSH_BLOCK
    for k, v in (("DEATH_SHADOW_R", str(hud.DEATH_MARK_SHADOW_R)), ("DEATH_R", str(hud.DEATH_MARK_R)),
                 ("DEATH_G0", str(hud.DEATH_MARK_G0)), ("DEATH_WAIT", f"{hud.DEATH_FADE_WAIT:.1f}"),
                 ("DEATH_EARLY", f"{hud.DEATH_FADE_EARLY:.1f}"), ("VEIL_BTN", f"{hud.DEATH_VEIL_BUTTONS[0]:.1f}"),
                 ("TEXT_WHITE", vec3(TEXT)), ("TEXT_GREY", vec3(TEXT_GREY)), ("TEXT_OFF", vec3(TEXT_OFF)),
                 ("TEXT_DARK", vec3(TEXT_DARK)), ("TEXT_TITLE", vec3(TEXT_TITLE)),
                 ("TEXT_YELLOW", vec3(TEXT_YELLOW)), ("TEXT_HOVER", vec3(TEXT_HOVER)),
                 ("INK", vec3("ink0")), ("SHADOW_A", f"{SHADOW_ALPHA:.3f}")):
        block = block.replace(k, v)
    block = "    soulsGui = ProjMat[3][3] == 1.0 ? 1.0 : 0.0;\n" + block
    return s.replace("    texCoord0 = UV0;\n", "    texCoord0 = UV0;\n" + block, 1)


def text_fsh():
    """글자 넓이 평균 + YOU DIED 띠 (알파 지도를 먹으로) + 서서히 나타나는 YOU DIED (hud.DEATH_FADE_*) + 단추 가림막 (hud.DEATH_VEIL_*)."""
    s = TEXT_FSH.replace("GAMMA", f"{TEXT_GAMMA:.3f}").replace("BAND_INK", vec3("ink0"))
    for k, v in (("DEATH_BAND_T0", hud.DEATH_FADE_BAND[0]), ("DEATH_BAND_T1", hud.DEATH_FADE_BAND[1]),
                 ("DEATH_LETTERS_T0", hud.DEATH_FADE_LETTERS[0]), ("DEATH_LETTERS_T1", hud.DEATH_FADE_LETTERS[1]),
                 ("VEIL_T0", hud.DEATH_VEIL_LIFT[0]), ("VEIL_T1", hud.DEATH_VEIL_LIFT[1]),
                 ("VEIL_FLAT", hud.DEATH_VEIL_FLAT), ("VEIL_HALF", hud.DEATH_VEIL_HALF),
                 ("VEIL_PAD", hud.DEATH_VEIL_PAD), ("VEIL_SOFT", hud.DEATH_VEIL_SOFT),
                 ("VEIL_BLOCK", hud.DEATH_VEIL_BUTTONS[1])):
        s = s.replace(k, f"{v:.1f}")
    s = s.replace("VEIL_A", f"{hud.DEATH_VEIL_ALPHA:.3f}")
    return s


def blur_json():
    """
    바닐라 1.21.11 post_effect/blur.json (가로·세로 box_blur 세 번, 반지름은 게임이 설정 값으로 채운다) 의 마지막 흐림을
    souls_blur 로 내고, menu_dim 한 번으로 main 에 쓴다.
    """
    def blur(src, dst, d):
        return {"vertex_shader": "minecraft:core/screenquad", "fragment_shader": "minecraft:post/box_blur",
                "inputs": [{"sampler_name": "In", "target": src, "bilinear": True}], "output": dst,
                "uniforms": {"BlurConfig": [{"name": "BlurDir", "type": "vec2", "value": d},
                                            {"name": "Radius", "type": "float", "value": 0.0}]}}
    passes = []
    for _ in range(3):
        passes += [blur("minecraft:main", "swap", [1.0, 0.0]), blur("swap", "minecraft:main", [0.0, 1.0])]
    passes[-1]["output"] = "souls_blur"
    passes.append({"vertex_shader": "minecraft:core/screenquad", "fragment_shader": "souls:post/menu_dim",
                   "inputs": [{"sampler_name": "In", "target": "souls_blur", "bilinear": False}],
                   "output": "minecraft:main"})
    return json.dumps({"targets": {"swap": {}, "souls_blur": {}}, "passes": passes}, indent=2) + "\n"


def vignette_png(path):
    """게임 화면 비네트 (256×256 회색, 흰 = 어둡게): 바닐라보다 넓고 무겁게, 가운데는 비운다."""
    import numpy as np
    from PIL import Image
    n = 256
    yy, xx = np.mgrid[0:n, 0:n]
    p = (np.stack([xx, yy], -1) + 0.5) / n * 2 - 1
    r = np.sqrt((p[..., 0] * 0.92) ** 2 + p[..., 1] ** 2)
    v = np.clip((r - 0.32) / (1.20 - 0.32), 0, 1)
    v = v * v * (3 - 2 * v)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.clip(np.rint(v * 255), 0, 255).astype(np.uint8), "L").convert("RGB").save(path)


def build(out):
    """셰이더·흐림 효과·비네트 그림을 쓴다. 쓴 셰이더 경로 목록 (팩 안) 을 돌려준다."""
    core = os.path.join(out, "assets", "minecraft", "shaders", "core")
    write(os.path.join(core, "rendertype_text.vsh"), text_vsh())
    write(os.path.join(core, "rendertype_text.fsh"), text_fsh())
    write(os.path.join(core, "rendertype_text_see_through.fsh"), SEE_THROUGH_FSH)
    write(os.path.join(core, "gui.vsh"), GUI_VSH.replace("BRONZE", vec3("bronze2")).replace("PARCH", vec3(GUI_WHITE)))
    write(os.path.join(core, "gui.fsh"), GUI_FSH.replace("BRONZE1", vec3("bronze1")).replace("BLOOD", vec3("blood0"))
          .replace("INK", vec3("ink0")))
    write(os.path.join(core, "position_tex_color.vsh"), ptc_vsh())
    write(os.path.join(core, "position_tex_color.fsh"), PTC_FSH)
    write(os.path.join(out, "assets", "souls", "shaders", "post", "menu_dim.fsh"), menu_fsh())
    blur = os.path.join(out, "assets", "minecraft", "post_effect", "blur.json")
    os.makedirs(os.path.dirname(blur), exist_ok=True)
    with open(blur, "w", encoding="utf-8", newline="\n") as f:
        f.write(blur_json())
    vignette_png(os.path.join(out, "assets", "minecraft", "textures", "misc", "vignette.png"))
    return list(TEXT_SHADERS + GUI_SHADERS)

