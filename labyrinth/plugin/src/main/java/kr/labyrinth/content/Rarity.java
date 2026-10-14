package kr.labyrinth.content;

import java.util.Locale;

/** 희귀도 (ARCHITECTURE §5). 순서 = 등급 순. */
public enum Rarity {
    COMMON("common", "일반", "#e8e8e8"),
    UNCOMMON("uncommon", "고급", "#5fd35f"),
    RARE("rare", "희귀", "#4f9bff"),
    EPIC("epic", "영웅", "#b45cff"),
    LEGENDARY("legendary", "전설", "#ffb52e"),
    MYTHIC("mythic", "신화", "#ff3b3b");

    private final String id;
    private final String displayName;
    private final String color;

    Rarity(String id, String displayName, String color) {
        this.id = id;
        this.displayName = displayName;
        this.color = color;
    }

    public String id() { return id; }
    public String displayName() { return displayName; }
    /** MiniMessage 에 바로 쓰는 #RRGGBB. */
    public String color() { return color; }
    public boolean atLeast(Rarity other) { return ordinal() >= other.ordinal(); }

    /** id(대소문자 무시)로 찾기. 없으면 null. */
    public static Rarity byId(String id) {
        if (id == null) return null;
        String k = id.trim().toLowerCase(Locale.ROOT);
        for (Rarity r : values()) if (r.id.equals(k)) return r;
        return null;
    }
}
