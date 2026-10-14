package kr.labyrinth.combat;

import java.util.Locale;

/** 피해 유형 (GDD §15.4). TRUE = 지속 피해·_pct 피해: 방어 무시. */
public enum DamageType {
    MELEE, RANGED, MAGIC, TRUE;

    public static DamageType byId(String id, DamageType def) {
        if (id == null) return def;
        try { return valueOf(id.trim().toUpperCase(Locale.ROOT)); } catch (IllegalArgumentException e) { return def; }
    }
}
