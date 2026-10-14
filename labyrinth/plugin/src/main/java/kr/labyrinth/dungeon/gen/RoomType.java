package kr.labyrinth.dungeon.gen;

/** 미로 셀/방 종류 (GDD §5.2). HALL = 방이 아닌 복도 셀. */
public enum RoomType {
    START("start", "시작의 방"),
    COMBAT("combat", "전투의 방"),
    ELITE("elite", "정예의 방"),
    TREASURE("treasure", "보물의 방"),
    GIMMICK("gimmick", "시련의 방"),
    REST("rest", "휴식의 방"),
    BOSS("boss", "수호자의 방"),
    HALL("hall", "복도");

    private final String key;
    private final String displayName;

    RoomType(String key, String displayName) {
        this.key = key;
        this.displayName = displayName;
    }

    /** floors.yml rooms 의 키. */
    public String key() { return key; }

    public String displayName() { return displayName; }

    public boolean isRoom() { return this != HALL; }

    public static RoomType byKey(String key) {
        for (RoomType t : values()) if (t.key.equals(key)) return t;
        return null;
    }
}
