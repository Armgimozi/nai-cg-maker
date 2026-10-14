package kr.labyrinth.pvp;

import org.bukkit.configuration.ConfigurationSection;

/**
 * config.yml {@code pvp:} 블록 (GDD §18). 규칙 자체는 {@link PvpRules}.
 *
 * @param enabled          플레이어끼리 싸울 수 있는가 (false = 같은 파티가 아니어도 서로 피해 없음)
 * @param damageMultiplier 플레이어 → 다른 플레이어 피해 배율 (몹 상대 공식 그대로면 고레벨에서 너무 세서)
 * @param maxHitRatio      한 번의 피해 상한 = 맞는 사람 최대 HP × 이 값 (1 이상 = 상한 없음)
 * @param safeZoneVillage  마을(labyrinth-village.yml) 안은 PvP 금지
 * @param safeZoneMargin   마을 반경에 더하는 여유 칸
 * @param partyNameColor   파티원 이름표를 초록색으로 (보는 사람 기준)
 */
public record PvpConfig(boolean enabled, double damageMultiplier, double maxHitRatio, boolean safeZoneVillage,
                        int safeZoneMargin, boolean partyNameColor) {

    /** pvp 모듈이 켜지기 전 / 설정이 없을 때: 플레이어끼리 싸우지 않는다. */
    public static final PvpConfig OFF = new PvpConfig(false, 1.0, 1.0, false, 0, false);

    /** 기본값 (config.yml 에 키가 없을 때). 근거는 config.yml 주석. */
    public static final PvpConfig DEFAULT = new PvpConfig(true, 0.7, 0.35, true, 8, true);

    public static PvpConfig from(ConfigurationSection s) {
        if (s == null) return DEFAULT;
        return new PvpConfig(
                s.getBoolean("enabled", DEFAULT.enabled),
                clamp(s.getDouble("damage_multiplier", DEFAULT.damageMultiplier), 0.0, 5.0),
                clamp(s.getDouble("max_hit_ratio", DEFAULT.maxHitRatio), 0.05, 1.0),
                s.getBoolean("safe_zone_village", DEFAULT.safeZoneVillage),
                (int) clamp(s.getInt("safe_zone_margin", DEFAULT.safeZoneMargin), 0, 256),
                s.getBoolean("party_name_color", DEFAULT.partyNameColor));
    }

    /** 플레이어끼리 피해 한 건 조정: 배율 → 상한(최대 HP × maxHitRatio). 둘 다 같은 단위(커스텀 HP 또는 바닐라 체력). */
    public double adjust(double damage, double victimMaxHp) {
        double d = Math.max(0, damage) * damageMultiplier;
        if (maxHitRatio < 1.0 && victimMaxHp > 0) d = Math.min(d, victimMaxHp * maxHitRatio);
        return d;
    }

    private static double clamp(double v, double min, double max) {
        return Double.isNaN(v) ? min : Math.max(min, Math.min(max, v));
    }
}
