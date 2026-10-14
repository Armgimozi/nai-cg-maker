package kr.labyrinth.combat;

import java.util.Optional;
import java.util.random.RandomGenerator;
import kr.labyrinth.Services;
import kr.labyrinth.core.Module;
import kr.labyrinth.mobs.CustomMob;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

/**
 * 모든 피해 계산의 단일 경로 (ARCHITECTURE §4 combat): 플레이어→몹, 몹→플레이어, 스킬, 보스 패턴, 지속 피해.
 * 공식 = {@link DamageFormula}. 커스텀 몹·보스는 {@link HealthPool}, 플레이어는 바닐라 체력({@code StatService} HP 계약).
 */
public final class DamageService implements Module {

    private final Services services;
    private final DamageNumbers numbers;
    private final RandomGenerator rng = RandomGenerator.getDefault();
    /** 우리가 직접 바닐라 피해를 줄 때 CombatListener 가 다시 가로채지 않게 하는 표시. */
    private boolean applyingVanilla;

    public DamageService(Services services) {
        this.services = services;
        this.numbers = new DamageNumbers(services);
    }

    @Override
    public String name() { return "combat"; }

    @Override
    public void enable() {
        Bukkit.getPluginManager().registerEvents(new CombatListener(services, this), services.plugin());
    }

    public DamageNumbers numbers() { return numbers; }

    boolean isApplyingVanilla() { return applyingVanilla; }

    /** 엔티티의 자체 HP 풀 (커스텀 몹·보스). 없으면 empty. */
    public Optional<HealthPool> poolOf(Entity e) {
        if (e == null) return Optional.empty();
        Optional<? extends HealthPool> m = services.mobs().byEntity(e);
        if (m.isPresent()) return Optional.of(m.get());
        return services.bosses().byEntity(e).map(b -> (HealthPool) b);
    }

    /** 대상 최대 HP (커스텀 단위). */
    public double maxHp(LivingEntity e) {
        if (e instanceof Player p) return services.stats().maxHp(p);
        return poolOf(e).map(HealthPool::maxHealth).orElseGet(() -> {
            var a = e.getAttribute(org.bukkit.attribute.Attribute.MAX_HEALTH);
            return a == null ? 20.0 : a.getValue();
        });
    }

    /** 피해 처리. ctx 에 결과(finalDamage/dealt/crit/evaded/blocked/killed)가 채워져 돌아온다. */
    public DamageContext deal(DamageContext ctx) {
        LivingEntity target = ctx.target();
        if (target == null || target.isDead() || !target.isValid()) {
            ctx.cancel();
            return ctx;
        }
        Player targetPlayer = target instanceof Player p ? p : null;
        if (targetPlayer != null && (targetPlayer.getGameMode() == GameMode.CREATIVE
                || targetPlayer.getGameMode() == GameMode.SPECTATOR)) {
            ctx.cancel();
            return ctx;
        }
        HealthPool pool = targetPlayer == null ? poolOf(target).orElse(null) : null;
        if (pool != null && (pool.invulnerable() || !pool.isAlive())) {
            ctx.cancel();
            return ctx;
        }

        Player attackerPlayer = ctx.attackerPlayer();
        DerivedStats atk = attackerPlayer != null ? services.stats().get(attackerPlayer) : null;

        // 원피해 결정
        if (ctx.usesAttackPower()) {
            ctx.amount((atk != null ? atk.attackPower() : 1.0) * ctx.attackMultiplier());
        } else if (ctx.isPercent()) {
            ctx.amount(maxHp(target) * ctx.percent());
        }

        // 대상 방어 요소
        double defense = 0, dr = 0, evasion = 0, taken = 0, block = 0;
        if (targetPlayer != null) {
            DerivedStats def = services.stats().get(targetPlayer);
            defense = def.defense();
            dr = def.damageReduction();
            evasion = def.evasion();
            taken = def.damageTaken();
            if (ctx.canBlock() && def.blockChance() > 0 && isFacing(targetPlayer, ctx.attacker()) && holdsShield(targetPlayer)) {
                block = def.blockChance();
            }
        } else if (pool != null) {
            defense = pool.defense();
            dr = pool.damageReduction();
            evasion = pool.evasion();
            taken = pool.damageTaken();
        }

        DamageFormula.Input in = new DamageFormula.Input(ctx.amount(), ctx.isSkill(),
                atk != null ? atk.damageMult() : 0, atk != null ? atk.skillDamage() : 0,
                atk != null ? atk.critChance() : 0, atk != null ? atk.critDamage() : 1.5, ctx.canCrit() && atk != null,
                evasion, ctx.canEvade(), defense, ctx.ignoresDefense(), dr, taken, block, ctx.canBlock());
        DamageFormula.Output out = DamageFormula.compute(in, rng);
        ctx.result(out.damage(), out.crit(), out.evaded(), out.blocked());

        if (out.evaded()) {
            if (ctx.showNumber()) numbers.show(target, 0, DamageNumbers.Kind.EVADE);
            return ctx;
        }

        double dealt;
        boolean killed;
        if (pool != null) {
            dealt = pool.applyDamage(out.damage(), ctx);
            killed = !pool.isAlive();
            if (pool instanceof CustomMob mob && attackerPlayer != null && dealt > 0) {
                mob.addThreat(attackerPlayer, dealt * ctx.threatMultiplier());
            }
        } else if (targetPlayer != null) {
            double before = services.stats().currentHp(targetPlayer);
            killed = applyToPlayer(targetPlayer, out.damage(), ctx.attacker());
            dealt = Math.min(before, out.damage());
        } else {
            double before = target.getHealth();
            applyVanilla(target, out.damage(), ctx.attacker());
            dealt = Math.min(before, out.damage());
            killed = target.isDead();
        }
        ctx.applied(dealt, killed);

        if (ctx.knockbackStrength() > 0 && ctx.attacker() != null && !killed) knockback(target, ctx.attacker(), ctx.knockbackStrength());
        if (atk != null && ctx.applyLifesteal() && atk.lifesteal() > 0 && dealt > 0) {
            services.stats().heal(attackerPlayer, dealt * atk.lifesteal());
        }
        if (ctx.showNumber()) {
            DamageNumbers.Kind kind = out.blocked() ? DamageNumbers.Kind.BLOCK
                    : targetPlayer != null ? DamageNumbers.Kind.PLAYER_HURT
                    : out.crit() ? DamageNumbers.Kind.CRIT
                    : ctx.type() == DamageType.TRUE ? DamageNumbers.Kind.TRUE : DamageNumbers.Kind.DAMAGE;
            numbers.show(target, out.damage(), kind);
        }
        if (targetPlayer != null) services.hud().refresh(targetPlayer);
        return ctx;
    }

    /** 치유 (커스텀 HP 단위). 플레이어·커스텀 몹 공통. @return 실제 회복량 */
    public double heal(LivingEntity target, double amount, boolean showNumber) {
        if (target == null || target.isDead() || amount <= 0) return 0;
        double healed;
        if (target instanceof Player p) {
            healed = services.stats().heal(p, amount);
            services.hud().refresh(p);
        } else {
            healed = poolOf(target).map(pool -> pool.heal(amount)).orElse(0.0);
        }
        if (showNumber && healed >= 1) numbers.show(target, healed, DamageNumbers.Kind.HEAL);
        return healed;
    }

    /** 플레이어에게 커스텀 HP 단위 피해를 바닐라 체력으로 적용. @return 사망했으면 true */
    private boolean applyToPlayer(Player p, double amount, LivingEntity attacker) {
        double vanilla = amount * services.stats().hpRatio(p);
        if (vanilla <= 0) return false;
        if (p.getHealth() - vanilla <= 0.0001) {
            applyVanilla(p, p.getHealth() + 1000.0, attacker); // 사망·부활 토템·사망 메시지는 바닐라 경로로
            return p.isDead();
        }
        p.setHealth(p.getHealth() - vanilla);
        p.playHurtAnimation(attacker == null ? 0f : yawTo(p, attacker));
        p.getWorld().playSound(p.getLocation(), Sound.ENTITY_PLAYER_HURT, 0.8f, 1.0f);
        return false;
    }

    private void applyVanilla(LivingEntity target, double amount, LivingEntity attacker) {
        applyingVanilla = true;
        try {
            if (attacker != null) target.damage(amount, attacker);
            else target.damage(amount);
        } finally {
            applyingVanilla = false;
        }
    }

    private static float yawTo(LivingEntity target, LivingEntity from) {
        Vector d = from.getLocation().toVector().subtract(target.getLocation().toVector());
        float yaw = (float) Math.toDegrees(Math.atan2(-d.getX(), d.getZ()));
        return yaw - target.getLocation().getYaw();
    }

    private boolean holdsShield(Player p) {
        ItemStack off = p.getInventory().getItemInOffHand();
        return off.getType() != Material.AIR && services.items().defOf(off).map(d -> d.isShield()).orElse(false);
    }

    /** 대상이 공격자를 정면 120° 안에서 보고 있는가 (방패 막기). */
    static boolean isFacing(LivingEntity target, LivingEntity attacker) {
        if (attacker == null) return false;
        Vector look = target.getLocation().getDirection().setY(0);
        Vector to = attacker.getLocation().toVector().subtract(target.getLocation().toVector()).setY(0);
        if (look.lengthSquared() < 1e-6 || to.lengthSquared() < 1e-6) return true;
        return look.normalize().dot(to.normalize()) >= Math.cos(Math.toRadians(60));
    }

    private static void knockback(LivingEntity target, LivingEntity from, double strength) {
        Vector dir = target.getLocation().toVector().subtract(from.getLocation().toVector()).setY(0);
        if (dir.lengthSquared() < 1e-6) return;
        dir.normalize().multiply(0.4 * strength).setY(Math.min(0.5, 0.15 + 0.1 * strength));
        target.setVelocity(target.getVelocity().add(dir));
    }
}
