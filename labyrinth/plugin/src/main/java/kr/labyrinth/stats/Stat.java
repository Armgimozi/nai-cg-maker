package kr.labyrinth.stats;

import java.util.Locale;

/** 기본 스탯 6종 (ARCHITECTURE §4, GDD §3). */
public enum Stat {
    STR("힘", "#ff7a59"),
    DEX("민첩", "#7fe07f"),
    INT("지능", "#6fa8ff"),
    VIT("체력", "#ff5f7a"),
    WIS("정신", "#c79bff"),
    LUK("행운", "#ffd84f");

    private final String displayName;
    private final String color;

    Stat(String displayName, String color) {
        this.displayName = displayName;
        this.color = color;
    }

    public String displayName() { return displayName; }
    public String color() { return color; }
    /** YAML/스탯 블록 키 (대문자 그대로: STR …). */
    public String key() { return name(); }

    public static Stat byKey(String key) {
        if (key == null) return null;
        String k = key.trim().toUpperCase(Locale.ROOT);
        for (Stat s : values()) if (s.name().equals(k)) return s;
        // 한국어 이름 허용 (명령어용)
        for (Stat s : values()) if (s.displayName.equals(key.trim())) return s;
        return null;
    }
}
