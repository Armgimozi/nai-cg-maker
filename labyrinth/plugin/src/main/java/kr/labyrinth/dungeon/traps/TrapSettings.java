package kr.labyrinth.dungeon.traps;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.Params;

/**
 * floors.yml 층별 {@code traps:} (GDD §5.5).
 * density = 복도 셀 하나당 함정 수 (0 = 없음), types = 이 층에서 쓰는 종류(3~4종), mark = 함정 칸 바닥에 까는 "살짝 다른" 블록
 * (생략하면 층 바닥 첫 블록 — 티가 안 남), spacing = 함정끼리 최소 거리(타일, 체비셰프).
 */
public record TrapSettings(double density, List<TrapType> types, String mark, int spacing) {

    public static final TrapSettings NONE = new TrapSettings(0, List.of(), null, 7);

    public TrapSettings {
        density = Math.max(0, Math.min(1.5, density));
        types = List.copyOf(types);
        spacing = Math.max(4, Math.min(20, spacing));
    }

    public static TrapSettings of(Params p) {
        if (p == null || p.isEmpty()) return NONE;
        List<TrapType> types = new ArrayList<>();
        for (String s : p.strings("types")) {
            TrapType t = TrapType.byId(s);
            if (t != null && !types.contains(t)) types.add(t);
        }
        return new TrapSettings(p.dbl("density", 0.25), types, p.str("mark", null), p.integer("spacing", 7));
    }
}
