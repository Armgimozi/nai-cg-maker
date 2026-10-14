package kr.labyrinth.content;

import java.util.Locale;

public enum ItemType {
    WEAPON, ARMOR, ACCESSORY, MATERIAL, CONSUMABLE, KEY;

    public String id() { return name().toLowerCase(Locale.ROOT); }

    public boolean isGear() { return this == WEAPON || this == ARMOR || this == ACCESSORY; }

    public static ItemType byId(String id) {
        if (id == null) return null;
        try { return valueOf(id.trim().toUpperCase(Locale.ROOT)); } catch (IllegalArgumentException e) { return null; }
    }
}
