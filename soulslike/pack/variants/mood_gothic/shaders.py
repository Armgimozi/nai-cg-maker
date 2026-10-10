"""
mood_gothic 의 셰이더 (바닐라 1.21.11 그대로에 덩이를 더한다).

  rendertype_text_intensity.vsh  TTF 글자 (이 시안의 본문·제목 글꼴) 는 이 셰이더로 그려진다.
                                 1) 바닐라가 정한 글자색을 팔레트로: 흰 글 → 뼈빛, §7 → 흐린 옛 금빛, 꺼진 단추 → 재, §8 → 어두운 양피지,
                                    §e → 바랜 양피지. 2) 그림자 (어두운 글자 사본, 바닐라는 1 GUI 픽셀 오른쪽 아래) → 먹빛,
                                    반 픽셀만 내려 가는 획 둘레에 붙는 그늘로. 3) 기본 팩 HUD 의 표식 색 글 (보스 이름) 을 옮기는 덩이
                                    (hud.py 의 rendertype_text.vsh 와 같은 셈. 보스 이름도 이제 TTF 라 여기서도 옮겨야 한다).
  gui.vsh / gui.fsh              GUI 채우기. 바닐라 두 가지 색만 알아보고 바꾼다:
                                 소지품·상자 창 뒤의 반투명 검정 (0xC0101010 → 0xD0101010) → 가장자리가 짙게 닫히는 비네트,
                                 위 가운데에 촛불 기운. 사망 화면의 붉은 막 (0x60500000 → 0xA0803030) → 붉은 기 없이 검게 닫히는
                                 비네트 (아래쪽에만 마른 핏빛 한 줌). 그 밖의 채우기는 그대로.
  post_effect/blur.json          게임 중 메뉴 (일시 정지, 휴식 창, 설정) 뒤의 흐림. 바닐라 여섯 번 흐림 뒤에 한 번 더:
                                 souls:post/gothic_menu (색을 빼고 어둡게, 무거운 비네트, 위에서 내려오는 촛불 기운).
"""
import json
import os

from palette import c

HUD_VSH_MARK = "    ivec3 mark = ivec3(Color.rgb * 255.0 + 0.5);"


def _vec3(name):
    r, g, b, _ = c(name)
    return f"vec3({r / 255:.4f}, {g / 255:.4f}, {b / 255:.4f})"


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _hud_block(base_vsh):
    """기본 팩 rendertype_text.vsh 의 HUD 표식 덩이 (main 안, 'ivec3 mark' 부터 main 의 끝 직전까지)."""
    i = base_vsh.index(HUD_VSH_MARK)
    j = base_vsh.rindex("}")
    return base_vsh[i:j].rstrip() + "\n"


def text_intensity_vsh(base_text_vsh, st):
    hud = _hud_block(base_text_vsh)
    return f"""#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV2;

uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;

// Block Soul, UI mood variant "gothic" (pack/variants/mood_gothic/shaders.py).
// Vanilla 1.21.11 rendertype_text_intensity.vsh (TrueType glyphs) plus:
//  * GUI text in vanilla colours -> palette: white -> bone, grey (section 7) -> dim old gold, disabled -> ash,
//    dark grey -> dark parchment, yellow -> faded parchment.
//  * text shadows (dark copies) -> warm ink, moved back half a GUI pixel so they hug the thin serif strokes.
//  * the base pack's HUD marker block (pack/hud.py), so marker-coloured TrueType text (boss name) is placed as before.
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = Color * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;

    if (ProjMat[3][3] == 1.0) {{
        ivec3 rgb = ivec3(Color.rgb * 255.0 + 0.5);
        bool marker = rgb.r == 254 && rgb.g == 253 && rgb.b >= 1 && rgb.b <= 6;
        int hi = max(rgb.r, max(rgb.g, rgb.b));
        vec3 ink = Color.rgb;
        if (rgb == ivec3(255, 255, 255)) ink = {_vec3(st.TEXT)};
        else if (rgb == ivec3(170, 170, 170)) ink = {_vec3(st.TEXT_GREY)};
        else if (rgb == ivec3(160, 160, 160)) ink = {_vec3(st.TEXT_OFF)};
        else if (rgb == ivec3(85, 85, 85)) ink = {_vec3(st.TEXT_DARK)};
        else if (rgb == ivec3(255, 255, 85)) ink = {_vec3(st.TEXT_YELLOW)};
        if (!marker && hi <= 70 && hi > 0) {{
            // shadow: warm ink, half a pixel closer to its glyph
            vertexColor = vec4({_vec3("ink0")}, Color.a * {st.SHADOW_ALPHA:.3f}) * texelFetch(Sampler2, UV2 / 16, 0);
            gl_Position.x -= 0.5 * ProjMat[0][0];
            gl_Position.y -= 0.5 * ProjMat[1][1];
        }} else if (!marker) {{
            vertexColor = vec4(ink, Color.a) * texelFetch(Sampler2, UV2 / 16, 0);
        }}
    }}

{hud}}}
"""


GUI_VSH_T = """#version 330

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
out vec3 gothicVignette;
out float gothicX;

// Block Soul, UI mood variant "gothic": vanilla gui.vsh plus flags for a few vanilla fills
// (container screen dim 0xC0101010..0xD0101010 -> 1, death screen red wash 0x60500000..0xA0803030 -> 2).
void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    vertexColor = Color;
    ivec4 c = ivec4(Color * 255.0 + 0.5);
    float mode = 0.0;
    if (c.rgb == ivec3(16, 16, 16) && (c.a == 192 || c.a == 208)) mode = 1.0;
    else if (c == ivec4(80, 0, 0, 96) || c == ivec4(128, 48, 48, 160)) mode = 2.0;
    else if (c.rgb == ivec3(208, 208, 208)) vertexColor = vec4(BRONZE, Color.a * 0.85);   // chat system-message bar (0xD0D0D0)
    else if (c.rgb == ivec3(0, 0, 0) && c.a > 0 && c.a < 200) mode = 3.0;                 // chat line backdrop
    gothicVignette = vec3(gl_Position.xy / gl_Position.w, mode);
    gothicX = (gl_Position.x / gl_Position.w + 1.0) / ProjMat[0][0];   // GUI pixels from the left edge
}
"""


def gui_vsh():
    return GUI_VSH_T.replace("BRONZE", _vec3("bronze2"))


def gui_fsh():
    return f"""#version 330

// Can't moj_import in things used during startup, when resource packs don't exist.
// This is a copy of dynamicimports.glsl
layout(std140) uniform DynamicTransforms {{
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
}};

in vec4 vertexColor;
in vec3 gothicVignette;
in float gothicX;

out vec4 fragColor;

// Block Soul, UI mood variant "gothic": the flagged fills become vignettes (see gui.vsh).
void main() {{
    vec4 color = vertexColor;
    if (gothicVignette.z > 2.5) {{
        // chat: warm ink that dissolves to the right instead of a hard black box
        color = vec4({_vec3("ink0")}, color.a * 1.25 * (1.0 - smoothstep(150.0, 330.0, gothicX)));
    }} else if (gothicVignette.z > 0.5) {{
        vec2 p = gothicVignette.xy;
        float r = length(p * vec2(0.86, 1.0));
        vec3 ink = {_vec3("ink0")};
        if (gothicVignette.z < 1.5) {{
            float a = mix(0.66, 0.97, smoothstep(0.30, 1.30, r));
            float candle = 1.0 - smoothstep(0.0, 1.0, length((p - vec2(0.0, 1.10)) * vec2(0.75, 1.45)));
            color = vec4(mix(ink, {_vec3("bronze1")}, 0.22 * candle), a - 0.10 * candle);
        }} else {{
            float a = mix(0.46, 0.95, smoothstep(0.25, 1.30, r));
            float low = smoothstep(0.1, -1.0, p.y);
            color = vec4(mix(ink, {_vec3("blood0")}, 0.55 * low), a);
        }}
    }}
    if (color.a == 0.0) {{
        discard;
    }}
    fragColor = color * ColorModulator;
}}
"""


def menu_fsh():
    return f"""#version 330

uniform sampler2D InSampler;

layout(std140) uniform SamplerInfo {{
    vec2 OutSize;
    vec2 InSize;
}};

in vec2 texCoord;

out vec4 fragColor;

// Block Soul, UI mood variant "gothic": after the vanilla menu blur, drain the colour, darken,
// close in with a heavy vignette and let a little warm candle light fall from above.
void main() {{
    vec3 c = texture(InSampler, texCoord).rgb;
    vec2 p = texCoord * 2.0 - 1.0;
    float aspect = OutSize.x / max(OutSize.y, 1.0);
    float r = length(vec2(p.x * min(aspect, 1.9) / 1.6, p.y));
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    vec3 col = mix(c, vec3(lum) * {_vec3("bone1")} * 1.6, 0.45);
    col *= mix(0.62, 0.10, smoothstep(0.20, 1.25, r));
    float candle = 1.0 - smoothstep(0.0, 1.0, length((p - vec2(0.0, 1.15)) * vec2(0.65, 1.35)));
    col += {_vec3("bronze1")} * 0.16 * candle;
    fragColor = vec4(col, 1.0);
}}
"""


def blur_json(vanilla_blur):
    """바닐라 blur.json 의 마지막 흐림을 swap 으로 내고, gothic_menu 한 번으로 main 에 쓴다."""
    data = json.loads(vanilla_blur)
    passes = data["passes"]
    assert passes[-1]["output"] == "minecraft:main"
    passes[-1]["output"] = "swap"
    passes.append({
        "vertex_shader": "minecraft:core/screenquad",
        "fragment_shader": "souls:post/gothic_menu",
        "inputs": [{"sampler_name": "In", "target": "swap", "bilinear": False}],
        "output": "minecraft:main",
    })
    return json.dumps(data, indent=2) + "\n"


TEXT_INTENSITY_FSH = """#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;

out vec4 fragColor;

// Block Soul, UI mood variant "gothic": vanilla rendertype_text_intensity.fsh, but the TrueType glyph atlas is read
// bilinearly (the atlas is drawn 4 texels per GUI pixel; at GUI scale 3 and 2 nearest sampling dropped whole texel rows
// of the thin serif strokes).
float glyph(vec2 uv) {
    vec2 size = vec2(textureSize(Sampler0, 0));
    vec2 p = uv * size - 0.5;
    vec2 f = p - floor(p);
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
    if (color.a < 0.04) {
        discard;
    }
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}
"""


POSITION_TEX_COLOR_VSH = """#version 330

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

out vec2 texCoord0;
out vec4 vertexColor;

// Block Soul, UI mood variant "gothic": vanilla position_tex_color.vsh plus one check.
// The in-game vignette is the only full-screen GUI quad (texture 0..1 on the screen corners) drawn in a grey
// below white at full alpha (its strength follows how dark the player's spot is). Keep it at least VIGNETTE_MIN
// so the corners always close in (misc/vignette.png gives the shape).
void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    texCoord0 = UV0;
    vertexColor = Color;
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


def build(pack, st, vanilla_blur):
    core = os.path.join(pack, "assets", "minecraft", "shaders", "core")
    with open(os.path.join(core, "rendertype_text.vsh"), encoding="utf-8") as f:
        base_text = f.read()
    _write(os.path.join(core, "rendertype_text_intensity.vsh"), text_intensity_vsh(base_text, st))
    _write(os.path.join(core, "rendertype_text_intensity.fsh"), TEXT_INTENSITY_FSH)
    _write(os.path.join(core, "gui.vsh"), gui_vsh())
    _write(os.path.join(core, "position_tex_color.vsh"),
           POSITION_TEX_COLOR_VSH.replace("VIGNETTE_MIN", f"{st.VIGNETTE_MIN:.3f}"))
    _write(os.path.join(core, "gui.fsh"), gui_fsh())
    _write(os.path.join(pack, "assets", "souls", "shaders", "post", "gothic_menu.fsh"), menu_fsh())
    _write(os.path.join(pack, "assets", "minecraft", "post_effect", "blur.json"), blur_json(vanilla_blur))
