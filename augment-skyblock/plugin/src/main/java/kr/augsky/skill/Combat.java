package kr.augsky.skill;

import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.damage.DamageSource;
import org.bukkit.damage.DamageType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/** 스킬/증강이 주는 피해와 회복. 스킬 피해 중에는 증강의 '공격 시' 효과가 다시 터지지 않게 막는다. */
public final class Combat {
    private static int depth = 0;
    /** 플레이어가 다른 플레이어에게 주는 스킬·증강 피해 배율 (config pvp.skill-damage). 몬스터 기준 수치라 그대로면 한 방에 끝나기 쉽다 */
    private static double pvpScale = 0.5;

    private Combat() {}

    public static void setPvpScale(double scale) { pvpScale = Math.max(0, scale); }

    public static boolean inSkill() { return depth > 0; }

    public static double damage(SkillContext ctx, LivingEntity target, double amount, boolean magic) {
        return damage(ctx.caster, target, amount, magic, ctx);
    }

    public static double damage(LivingEntity source, LivingEntity target, double amount, boolean magic, SkillContext ctx) {
        if (amount <= 0 || target == null || target.isDead() || !target.isValid()) return 0;
        if (source instanceof Player && target instanceof Player && source != target) amount *= pvpScale;
        if (amount <= 0) return 0;
        double before = target.getHealth() + target.getAbsorptionAmount();
        target.setNoDamageTicks(0);
        depth++;
        try {
            if (source == null || !source.isValid()) {
                target.damage(amount);
            } else if (magic) {
                target.damage(amount, DamageSource.builder(DamageType.INDIRECT_MAGIC)
                        .withCausingEntity(source).withDirectEntity(source).build());
            } else {
                target.damage(amount, source);
            }
        } finally {
            depth--;
        }
        double after = target.isDead() ? 0 : target.getHealth() + target.getAbsorptionAmount();
        double dealt = Math.max(0, before - after);
        if (ctx != null) ctx.lastDamage = dealt;
        return dealt;
    }

    public static double maxHealth(LivingEntity e) {
        AttributeInstance a = e.getAttribute(Attribute.MAX_HEALTH);
        return a == null ? 20 : a.getValue();
    }

    public static void heal(LivingEntity e, double amount) {
        if (e == null || e.isDead() || amount <= 0) return;
        e.setHealth(Math.min(maxHealth(e), e.getHealth() + amount));
    }
}
