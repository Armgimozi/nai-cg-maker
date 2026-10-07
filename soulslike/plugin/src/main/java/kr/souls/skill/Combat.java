package kr.souls.skill;

import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.damage.DamageSource;
import org.bukkit.damage.DamageType;
import org.bukkit.entity.LivingEntity;

/**
 * 스킬이 주는 피해와 회복. 스킬 피해 중에는 '공격 시' 효과가 다시 터지지 않게 막는다.
 * 모든 피해는 minecraft:generic + 원인 물체로 보낸다 (3.9). generic 은 #bypasses_armor, #no_knockback 에 들어 있어
 * 바닐라 방어구와 밀림이 덧붙지 않는다. INDIRECT_MAGIC(밀림이 붙는다), MOB_ATTACK(바닐라 방패가 한 번 더 깎는다)은 쓰지 않는다.
 * 적 → 플레이어 피해는 M1 에서 IncomingHitQueue 를 지나게 바꾸고, 적은 가상 체력을 쓴다.
 */
public final class Combat {
    private static int depth = 0;

    private Combat() {}

    public static boolean inSkill() { return depth > 0; }

    public static double damage(SkillContext ctx, LivingEntity target, double amount, boolean magic) {
        return damage(ctx.caster, target, amount, magic, ctx);
    }

    /** magic 은 예전 스킬 글과 맞추려고 남겨 둔 표시다. 피해 종류는 늘 generic 이다. */
    public static double damage(LivingEntity source, LivingEntity target, double amount, boolean magic, SkillContext ctx) {
        if (amount <= 0 || target == null || target.isDead() || !target.isValid()) return 0;
        double before = target.getHealth() + target.getAbsorptionAmount();
        target.setNoDamageTicks(0);
        depth++;
        try {
            target.damage(amount, source(DamageType.GENERIC, source));
        } finally {
            depth--;
        }
        double after = target.isDead() ? 0 : target.getHealth() + target.getAbsorptionAmount();
        double dealt = Math.max(0, before - after);
        if (ctx != null) ctx.lastDamage = dealt;
        return dealt;
    }

    /** 피해 종류 + 원인 물체. 원인이 없거나 사라졌으면 원인 없이 보낸다. */
    public static DamageSource source(DamageType type, LivingEntity cause) {
        DamageSource.Builder b = DamageSource.builder(type);
        if (cause != null && cause.isValid()) b.withCausingEntity(cause).withDirectEntity(cause);
        return b.build();
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
