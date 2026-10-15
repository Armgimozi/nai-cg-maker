package kr.labyrinth.dungeon.treasure;

import java.util.function.Predicate;

/**
 * 미로 보물 상자 등급 (GDD §5.6). 루팅 테이블 = 층별 {@code maze_chest_<id>_f<층>} (없으면 구간 {@code maze_chest_<id>_<층 구간>})
 * + 철·금은 {@code maze_enhance_<id>_t<강화석 등급>} (loot.yml). 장비(그 층 gear_fNN_common)는 층별 표에만 있다.
 */
public enum ChestTier {
    WOOD("wood", "나무 상자", "<#c8a070>"),
    IRON("iron", "철 상자", "<#d8dde6>"),
    GOLD("gold", "금 상자", "<#ffd36b>");

    private final String id;
    private final String displayName;
    private final String color;

    ChestTier(String id, String displayName, String color) {
        this.id = id;
        this.displayName = displayName;
        this.color = color;
    }

    public String id() { return id; }
    public String displayName() { return displayName; }
    public String color() { return color; }

    /** 한 단계 위 (금은 그대로) — 미믹을 물리치면 상자가 한 단계 좋아진다. */
    public ChestTier up() { return this == WOOD ? IRON : GOLD; }

    /** 층 구간 (1 = 1~3층, 2 = 4~6층, 3 = 7~9층, 4 = 10층). */
    public static int bracket(int floor) {
        if (floor <= 3) return 1;
        if (floor <= 6) return 2;
        if (floor <= 9) return 3;
        return 4;
    }

    /** 구간 루팅 테이블 id ({@code maze_chest_<id>_<구간>}). bracketOverride > 0 이면 그 구간. */
    public String table(int floor, int bracketOverride) {
        return "maze_chest_" + id + "_" + (bracketOverride > 0 ? bracketOverride : bracket(floor));
    }

    /** 층별 루팅 테이블 id ({@code maze_chest_<id>_f<층>}). */
    public String floorTable(int floor) {
        return "maze_chest_" + id + "_f" + floor;
    }

    /**
     * 실제로 굴릴 테이블. floors.yml {@code chests.bracket} 강제(bracketOverride > 0)면 구간 테이블,
     * 아니면 층별 테이블이 있으면 그것, 없으면 구간 테이블 (예전 loot.yml 호환). 검사기도 같은 규칙으로 확인한다.
     *
     * @param exists 루팅 테이블 id 가 loot.yml 에 있는가
     */
    public String table(int floor, int bracketOverride, Predicate<String> exists) {
        if (bracketOverride <= 0) {
            String own = floorTable(floor);
            if (exists.test(own)) return own;
        }
        return table(floor, bracketOverride);
    }

    /** 강화석 등급 (1 = 1~3층 하급, 2 = 4~7층 상급, 3 = 8~10층 최상급 — config enhance.stones 구간, 상자 구간과 다르다). */
    public static int stoneTier(int floor) {
        if (floor <= 3) return 1;
        if (floor <= 7) return 2;
        return 3;
    }

    /** 강화석 루팅 테이블 id ({@code maze_enhance_<id>_t<등급>}, 상자 한 번에 한 번만 굴린다). 나무 상자는 없음(null). */
    public String enhanceTable(int floor) {
        return this == WOOD ? null : "maze_enhance_" + id + "_t" + stoneTier(floor);
    }
}
