#version 150

#moj_import <minecraft:fog.glsl>

uniform sampler2D Sampler0;

uniform vec4 ColorModulator;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;

in float vertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;
in vec4 rawColor;
in vec2 texCoord1;

out vec4 fragColor;

void main() {
    // augsky: texels with alpha 252/251/250 ignore lighting and shading (weapon auras, glowing edges,
    // boss glow parts). 252 = opaque, 251 = 75%, 250 = 50%
    vec4 augTex = texture(Sampler0, texCoord0);
    float augMark = floor(augTex.a * 255.0 + 0.5);
    if (augMark >= 249.5 && augMark <= 252.5) {
        vec4 glow = vec4(augTex.rgb, 1.0) * rawColor * ColorModulator;
        glow.a = augMark > 251.5 ? 1.0 : (augMark > 250.5 ? 0.75 : 0.5);
        fragColor = linear_fog(glow, vertexDistance, FogStart, FogEnd, FogColor);
        return;
    }
    vec4 color = texture(Sampler0, texCoord0) * vertexColor * ColorModulator;
    if (color.a < 0.1) {
        discard;
    }
    fragColor = linear_fog(color, vertexDistance, FogStart, FogEnd, FogColor);
}
