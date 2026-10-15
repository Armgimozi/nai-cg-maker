package kr.labyrinth.combat;

import java.util.Locale;

/**
 * 피해 종류 (0.3.5) — 어떤 스탯이 피해를 키우는가. {@link DamageType} 는 '어떻게 맞았나'(근접·원거리·마법·고정)로 남는다.
 * <ul>
 *   <li>PHYSICAL = × (1 + 0.01 × 힘)</li>
 *   <li>MAGIC = × (1 + 0.01 × 지능)</li>
 *   <li>HYBRID = × (1 + 0.01 × (힘 + 지능) / 2)</li>
 *   <li>FIXED = 스탯을 타지 않음 (최대 HP 비율·되돌림)</li>
 * </ul>
 */
public enum DamageKind {
    PHYSICAL, MAGIC, HYBRID, FIXED;

    /** 피해 유형의 기본 종류: 근접·원거리 → 물리, 마법 → 마법, 고정 → 고정. */
    public static DamageKind of(DamageType type) {
        if (type == null) return PHYSICAL;
        return switch (type) {
            case MELEE, RANGED -> PHYSICAL;
            case MAGIC -> MAGIC;
            case TRUE -> FIXED;
        };
    }

    public static DamageKind byId(String id, DamageKind def) {
        if (id == null || id.isBlank()) return def;
        try {
            return valueOf(id.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return def;
        }
    }

    /** 툴팁·화면 글 ("물리" · "마법" · "혼합" · "고정"). */
    public String displayName() {
        return switch (this) {
            case PHYSICAL -> "물리";
            case MAGIC -> "마법";
            case HYBRID -> "혼합";
            case FIXED -> "고정";
        };
    }
}
