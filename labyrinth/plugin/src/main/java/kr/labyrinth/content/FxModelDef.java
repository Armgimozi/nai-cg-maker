package kr.labyrinth.content;

import java.util.List;

/** fx.yml models — 이펙트 아이템 모델 (labyrinth:fx/&lt;id&gt;). size 는 px [w,h,d]. */
public record FxModelDef(String id, String style, String motif, String shape, List<String> palette, boolean animated,
                         int frames, int frametime, List<Integer> size, boolean flat, boolean glow, String billboard) {}
