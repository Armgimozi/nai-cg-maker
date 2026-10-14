package kr.labyrinth.combat;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.CopyOnWriteArrayList;
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
    /** 피해 적용 직전 가로채기 (items: 무기 스킬 보호막·방어 자세·무적, 자동 부활). */
    private final java.util.List<DamageInterceptor> interceptors = new java.util.concurrent.CopyOnWriteArrayList<>();

    private final List<Hook> hooks = new CopyOnWriteArrayList<>();

    /**
     * 피해 파이프라인 훅 (classes: 상태이상·보호막·피해 분담·직업 패시브, pvp: 매치 규칙 등). 등록 순서대로 호출되며
     * 훅의 예외는 로그만 남기고 무시된다. 훅 안에서 {@link #deal} 을 다시 부를 수 있다(재귀 방지는 훅 책임).
     */
    public interface Hook {
        /** 원피해가 정해진 직후(방어·치명타 계산 전). {@code ctx.amount(..)}·{@code threat(..)}·{@code critBonus(..)} 조정 가능. */
        default void before(DamageContext ctx) {}

        /** 최종 피해가 대상에게 적용되기 직전 (회피되지 않았을 때). 보호막 흡수·피해 분담 후 남은 피해를 돌려준다. */
        default double absorb(DamageContext ctx, double damage) { return damage; }

        /** 적용 후 (dealt/killed/crit 확정). 적중 시 효과·자원 회복 등. */
        default void after(DamageContext ctx) {}
    }

    public void addHook(Hook hook) { hooks.add(java.util.Objects.requireNonNull(hook)); }

    public void removeHook(Hook hook) { hooks.remove(hook); }

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

    /** 피해 적용 직전 가로채기 등록 ({@link DamageInterceptor}). */
    public void addInterceptor(DamageInterceptor i) { interceptors.add(i); }

    public void removeInterceptor(DamageInterceptor i) { interceptors.remove(i); }

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
        for (Hook h : hooks) {
            try {
                h.before(ctx);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("피해 훅(before) 오류", t);
            }
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
                (atk != null ? atk.critChance() : 0) + ctx.critBonus(), atk != null ? atk.critDamage() : 1.5,
                ctx.canCrit() && atk != null,
                evasion, ctx.canEvade(), defense, ctx.ignoresDefense(), dr, taken, block, ctx.canBlock());
        DamageFormula.Output out = DamageFormula.compute(in, rng);
        ctx.result(out.damage(), out.crit(), out.evaded(), out.blocked());

        if (out.evaded()) {
            if (ctx.showNumber()) numbers.show(target, 0, DamageNumbers.Kind.EVADE);
            return ctx;
        }

        double finalDamage = out.damage();
        // 훅 (classes: 상태이상·보호막·피해 분담, pvp: 매치 규칙)
        for (Hook h : hooks) {
            try {
                finalDamage = Math.max(0, h.absorb(ctx, finalDamage));
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("피해 훅(absorb) 오류", t);
            }
        }
        // 가로채기 (items: 무기 스킬 보호막·방어 자세·무적·자동 부활)
        if (!interceptors.isEmpty() && finalDamage > 0) {
            for (DamageInterceptor i : interceptors) {
                try {
                    finalDamage = Math.max(0, i.intercept(ctx, finalDamage));
                } catch (Throwable t) {
                    kr.labyrinth.core.Log.error("DamageInterceptor 오류", t);
                }
                if (finalDamage <= 0) break;
            }
        }
        boolean fullyAbsorbed = finalDamage <= 0 && out.damage() > 0;
        if (finalDamage != out.damage()) ctx.result(finalDamage, out.crit(), false, out.blocked() || fullyAbsorbed);

        double dealt;
        boolean killed;
        if (fullyAbsorbed) {
            dealt = 0;
            killed = false;
        } else if (pool != null) {
            dealt = pool.applyDamage(finalDamage, ctx);
            killed = !pool.isAlive();
            if (pool instanceof CustomMob mob && attackerPlayer != null && dealt > 0) {
                mob.addThreat(attackerPlayer, dealt * ctx.threatMultiplier());
            }
        } else if (targetPlayer != null) {
            double before = services.stats().currentHp(targetPlayer);
            killed = applyToPlayer(targetPlayer, finalDamage, ctx.attacker());
            dealt = Math.min(before, finalDamage);
        } else {
            double before = target.getHealth();
            applyVanilla(target, finalDamage, ctx.attacker());
            dealt = Math.min(before, finalDamage);
            killed = target.isDead();
        }
        ctx.applied(dealt, killed);

        if (ctx.knockbackStrength() > 0 && ctx.attacker() != null && !killed) knockback(target, ctx.attacker(), ctx.knockbackStrength());
        if (atk != null && ctx.applyLifesteal() && atk.lifesteal() > 0 && dealt > 0) {
            services.stats().heal(attackerPlayer, dealt * atk.lifesteal());
        }
        for (Hook h : hooks) {
            try {
                h.after(ctx);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("피해 훅(after) 오류", t);
            }
        }
        if (ctx.showNumber()) {
            DamageNumbers.Kind kind = out.blocked() || fullyAbsorbed ? DamageNumbers.Kind.BLOCK
                    : targetPlayer != null ? DamageNumbers.Kind.PLAYER_HURT
                    : out.crit() ? DamageNumbers.Kind.CRIT
                    : ctx.type() == DamageType.TRUE ? DamageNumbers.Kind.TRUE : DamageNumbers.Kind.DAMAGE;
            numbers.show(target, finalDamage, kind);
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
