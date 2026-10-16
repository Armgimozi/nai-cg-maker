package kr.labyrinth.content;

import java.util.Locale;

/**
 * items.yml {@code type}. 0.3.6: {@link #TOOL} = 광산 곡괭이 (장비 아님 — 능력치·강화·요구 능력치·판매 없음, 한 칸에 1개,
 * {@code tool: {kind, tier, speed, bonus}} 는 {@link ToolSpec}). 계약: tools/data/036/mine.json · design/036/CONTRACT.md.
 */
public enum ItemType {
    WEAPON, ARMOR, ACCESSORY, MATERIAL, CONSUMABLE, KEY, TOOL;

    public String id() { return name().toLowerCase(Locale.ROOT); }

    public boolean isGear() { return this == WEAPON || this == ARMOR || this == ACCESSORY; }

    /** 광산 도구 (곡괭이). 장비가 아니다 ({@link #isGear()} = false). */
    public boolean isTool() { return this == TOOL; }

    public static ItemType byId(String id) {
        if (id == null) return null;
        try { return valueOf(id.trim().toUpperCase(Locale.ROOT)); } catch (IllegalArgumentException e) { return null; }
    }
}
