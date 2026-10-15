package kr.labyrinth.dungeon.treasure;

/** 미로 보물 상자 등급 (GDD §5.6). 루팅 테이블 = {@code maze_chest_<id>_<층 구간>} + 철·금은 {@code maze_enhance_<id>_t<강화석 등급>} (loot.yml). */
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

    /** 루팅 테이블 id. bracketOverride > 0 이면 그 구간. */
    public String table(int floor, int bracketOverride) {
        return "maze_chest_" + id + "_" + (bracketOverride > 0 ? bracketOverride : bracket(floor));
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
