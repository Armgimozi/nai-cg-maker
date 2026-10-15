package kr.labyrinth.dungeon.treasure;

/** 미로 보물 상자 등급 (GDD §5.6). 루팅 테이블 = {@code maze_chest_<id>_<층 구간>} (loot.yml). */
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
}
