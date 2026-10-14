package kr.labyrinth.mobs;

/**
 * 몹 한 마리의 최종 수치 (난이도·파티 배율·정예 변종 적용 후). Bukkit 무관 — 단위 테스트 대상.
 * <p>
 * 정예 변종(일반 몹이 확률/명령으로 강화되어 나온 것): HP ×{@link #ELITE_HP}, 피해 ×{@link #ELITE_DAMAGE},
 * 방어 ×{@link #ELITE_DEFENSE}, 경험치 ×{@link #ELITE_XP}, 골드 ×{@link #ELITE_GOLD}, 모델 크기 ×{@link #ELITE_SCALE}
 * + 추가 스킬 1개 + 발광. (mobs.yml 의 rank: elite 몹은 이미 정예 수치가 들어 있으므로 배율을 다시 곱하지 않는다.)
 */
public record MobStats(double maxHp, double damage, double defense, double xp, double goldMultiplier, double scale) {

    public static final double ELITE_HP = 3.0;
    public static final double ELITE_DAMAGE = 1.35;
    public static final double ELITE_DEFENSE = 1.25;
    public static final double ELITE_XP = 3.0;
    public static final double ELITE_GOLD = 2.5;
    public static final double ELITE_SCALE = 1.15;

    /**
     * @param baseHp       YAML hp
     * @param baseDamage   YAML damage
     * @param baseDefense  YAML defense
     * @param baseXp       YAML xp
     * @param baseScale    YAML scale
     * @param hpMult       InstanceContext.hpMultiplier()
     * @param dmgMult      InstanceContext.damageMultiplier()
     * @param eliteVariant 정예 변종 여부
     */
    public static MobStats compute(double baseHp, double baseDamage, double baseDefense, double baseXp, double baseScale,
                                   double hpMult, double dmgMult, boolean eliteVariant) {
        double hp = Math.max(1, baseHp) * Math.max(0.01, hpMult);
        double dmg = Math.max(0, baseDamage) * Math.max(0, dmgMult);
        double def = Math.max(0, baseDefense);
        double xp = Math.max(0, baseXp);
        double gold = 1.0;
        double scale = baseScale <= 0 ? 1.0 : baseScale;
        if (eliteVariant) {
            hp *= ELITE_HP;
            dmg *= ELITE_DAMAGE;
            def *= ELITE_DEFENSE;
            xp *= ELITE_XP;
            gold *= ELITE_GOLD;
            scale *= ELITE_SCALE;
        }
        return new MobStats(Math.max(1, Math.round(hp)), dmg, def, xp, gold, scale);
    }
}
