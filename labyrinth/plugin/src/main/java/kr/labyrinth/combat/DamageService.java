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
    /**
     * 피해 적용 직전 가로채기 (items: 무기 스킬 보호막·방어 자세·무적 → 천 마나 보호막 → 자동 부활). 순서 값이 작은 것부터,
     * 같으면 등록 순서대로 ({@link #ORDER_MANA_SHIELD} · {@link #ORDER_LAST}).
     */
    private final java.util.List<Ordered> interceptors = new java.util.concurrent.CopyOnWriteArrayList<>();
    private record Ordered(int order, DamageInterceptor interceptor) {}

    /** 천 4부위 마나 보호막 — 무적·보호막 가로채기 뒤, 자동 부활 앞 (review2 C3: 무적이면 MP 가 안 빠지고, 막을 수 있으면 부활하지 않게). */
    public static final int ORDER_MANA_SHIELD = 50;
    /** 마지막 (자동 부활 — 남은 피해가 HP 를 넘을 때만). */
    public static final int ORDER_LAST = 100;

    private final List<Hook> hooks = new CopyOnWriteArrayList<>();

    /**
     * 피해 파이프라인 훅 (classes: 상태이상·보호막·피해 분담·직업 패시브, pvp: 파티 규칙·플레이어끼리 피해 배율). 등록 순서대로 호출되며
     * 훅의 예외는 로그만 남기고 무시된다. 훅 안에서 {@link #deal} 을 다시 부를 수 있다(재귀 방지는 훅 책임).
     */
    public interface Hook {
        /** 이 피해를 아예 막을지 (false = 취소, 숫자도 안 뜸). 예: pvp — 같은 파티원끼리의 피해(늦게 도착한 지속 피해 등). */
        default boolean allow(DamageContext ctx) { return true; }

        /** 원피해가 정해진 직후(방어·치명타 계산 전). {@code ctx.amount(..)}·{@code threat(..)}·{@code critBonus(..)} 조정 가능. */
        default void before(DamageContext ctx) {}

        /** 최종 피해가 대상에게 적용되기 직전 (회피되지 않았을 때). 보호막 흡수·피해 분담 후 남은 피해를 돌려준다. */
        default double absorb(DamageContext ctx, double damage) { return damage; }

        /** 적용 후 (dealt/killed/crit 확정). 적중 시 효과·자원 회복 등. */
        default void after(DamageContext ctx) {}

        /** 회피됐을 때 (after 대신 — 피해 없음). 예: 고유 효과 흘려치기. 회피할 수 없는 피해(지속 피해·패턴)는 여기 오지 않는다. */
        default void evaded(DamageContext ctx) {}
    }

    public void addHook(Hook hook) { hooks.add(java.util.Objects.requireNonNull(hook)); }

    public void removeHook(Hook hook) { hooks.remove(hook); }

    public DamageService(Services services) {
        this.services = services;
        this.numbers = new DamageNumbers(services);
    }

    @Override
    public String name() { return "combat"; }

    private AttackClock clock;
    private CombatListener listener;

    @Override
    public void enable() {
        clock = new AttackClock(services);
        clock.start();
        listener = new CombatListener(services, this, clock);
        Bukkit.getPluginManager().registerEvents(listener, services.plugin());
    }

    @Override
    public void disable() {
        if (clock != null) clock.stop();
        if (listener != null) org.bukkit.event.HandlerList.unregisterAll(listener);
    }

    /**
     * 서버가 잰 활 당김 세기 0~1 (combat_spec §2.5) — 화살 피해·무기 스킬 '웅크리고 당겨 쏘기' 위력이 같은 값을 쓴다.
     * @param vanillaForce 이벤트의 바닐라 세기 (당긴 시간을 못 읽을 때만 씀)
     */
    public double bowForce(Player p, double vanillaForce) {
        return clock == null ? Math.max(0, Math.min(1, vanillaForce)) : clock.bowForce(p, vanillaForce);
    }

    public DamageNumbers numbers() { return numbers; }

    /** 피해 적용 직전 가로채기 등록 ({@link DamageInterceptor}, 순서 0). */
    public void addInterceptor(DamageInterceptor i) { addInterceptor(i, 0); }

    /** 순서를 정해 등록 — 작은 값이 먼저 (같으면 등록 순서). */
    public synchronized void addInterceptor(DamageInterceptor i, int order) {
        java.util.Objects.requireNonNull(i);
        int at = interceptors.size();
        for (int k = 0; k < interceptors.size(); k++) {
            if (interceptors.get(k).order() > order) {
                at = k;
                break;
            }
        }
        interceptors.add(at, new Ordered(order, i));
    }

    public void removeInterceptor(DamageInterceptor i) { interceptors.removeIf(o -> o.interceptor() == i); }

    /** 지금 우리가 직접 바닐라 피해(사망 처리 등)를 주는 중인가 — 다른 리스너가 그 피해를 다시 가로채지 않게. */
    public boolean isApplyingVanilla() { return applyingVanilla; }

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
        // 광산 월드 안 플레이어는 피해 0 (0.3.6 — 스킬·지속 피해·PvP 모두. EntityDamageEvent 취소만으로는 setHealth 길이 남음)
        if (targetPlayer != null && kr.labyrinth.mine.MineSafety.protects(services.mine(), targetPlayer)) {
            ctx.cancel();
            return ctx;
        }
        HealthPool pool = targetPlayer == null ? poolOf(target).orElse(null) : null;
        if (pool != null && (pool.invulnerable() || !pool.isAlive())) {
            ctx.cancel();
            return ctx;
        }
        for (Hook h : hooks) {
            boolean ok;
            try {
                ok = h.allow(ctx);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("피해 훅(allow) 오류", t);
                ok = true;
            }
            if (!ok) {
                ctx.cancel();
                return ctx;
            }
        }

        Player attackerPlayer = ctx.attackerPlayer();
        DerivedStats atk = attackerPlayer != null ? services.stats().get(attackerPlayer) : null;

        // 원피해 결정 (0.3.5): 기준(기본 공격 = 무기 한 방 W, 스킬 = 스킬 위력 SP) × 피해 종류의 스탯 배율 × 배율
        if (ctx.usesAttackPower()) {
            ctx.kind(resolveKind(ctx, atk));
            ctx.amount(rawAmount(atk, ctx.base(), ctx.kind(), ctx.attackMultiplier()));
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
            // 가죽 4부위 구르기: 구르는 동안 피할 수 있는 공격은 모두 회피 (지속 피해·보스 패턴은 원래 못 피함)
            if (ctx.canEvade() && services.looks().tumbling(targetPlayer)) evasion = 1.0;
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

        // 고유 효과 갑옷 부수기: 쌓인 만큼 대상 방어를 깎는다 (상한 40%, 누가 때려도 — 파티 전원)
        double shred = services.unique().defenseShred(target);
        if (shred > 0) defense *= 1.0 - Math.min(0.4, shred);
        // PvP: 방어 대신 강인함(defenseScale 0) · 치명 추가 피해 × 0.6 (pvp 훅이 before() 에서 정함)
        defense *= ctx.defenseScale();
        double critDamage = DamageFormula.scaledCritDamage((atk != null ? atk.critDamage() : 1.5) + ctx.critDamageAdd(),
                ctx.critDamageScale());
        DamageFormula.Input in = new DamageFormula.Input(ctx.amount(), ctx.isSkill(),
                atk != null ? atk.damageMult() : 0, atk != null ? atk.skillDamage() : 0,
                (atk != null ? atk.critChance() : 0) + ctx.critBonus(), critDamage,
                ctx.canCrit() && atk != null,
                evasion, ctx.canEvade(), defense, ctx.ignoresDefense(), dr, taken, block, ctx.canBlock());
        DamageFormula.Output out = DamageFormula.compute(in, rng);
        ctx.result(out.damage(), out.crit(), out.evaded(), out.blocked());

        if (out.evaded()) {
            if (ctx.showNumber()) numbers.show(target, 0, DamageNumbers.Kind.EVADE);
            for (Hook h : hooks) {
                try {
                    h.evaded(ctx);
                } catch (Throwable t) {
                    kr.labyrinth.core.Log.error("피해 훅(evaded) 오류", t);
                }
            }
            return ctx;
        }

        double finalDamage = out.damage();
        // 훅 (classes: 상태이상·보호막·피해 분담, pvp: 플레이어끼리 한 방 상한)
        for (Hook h : hooks) {
            try {
                finalDamage = Math.max(0, h.absorb(ctx, finalDamage));
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("피해 훅(absorb) 오류", t);
            }
        }
        // 가로채기 (items: 무기 스킬 보호막·방어 자세·무적·자동 부활)
        if (!interceptors.isEmpty() && finalDamage > 0) {
            for (Ordered o : interceptors) {
                try {
                    finalDamage = Math.max(0, o.interceptor().intercept(ctx, finalDamage));
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
            // 미궁 밖 바닐라 몹: 바닐라 무적 시간(10틱)이 빠른 무기의 다음 타격을 막지 않게 (공격 간격은 공격하는 쪽 시계가 지킨다)
            if (attackerPlayer != null && !target.isDead()) target.setNoDamageTicks(0);
            dealt = Math.min(before, finalDamage);
            killed = target.isDead();
        }
        ctx.applied(dealt, killed);

        if (ctx.knockbackStrength() > 0 && ctx.attacker() != null && !killed) knockback(target, ctx.attacker(), ctx.knockbackStrength());
        if (atk != null && ctx.applyLifesteal() && atk.lifesteal() > 0 && dealt > 0) {
            lifesteal(attackerPlayer, target, dealt * atk.lifesteal(), false);
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
                    : ctx.type() == DamageType.TRUE ? DamageNumbers.Kind.TRUE
                    : ctx.effectiveKind() == DamageKind.MAGIC ? DamageNumbers.Kind.MAGIC : DamageNumbers.Kind.DAMAGE;
            numbers.show(target, finalDamage, kind);
        }
        if (targetPlayer != null) services.hud().refresh(targetPlayer);
        return ctx;
    }

    /** 피해 종류: 정해 둔 값 → 기본 공격이면 손에 든 무기의 종류 → 유형의 기본값. */
    static DamageKind resolveKind(DamageContext ctx, DerivedStats atk) {
        if (ctx.kind() != null) return ctx.kind();
        if (atk != null && ctx.base() == DamageContext.Base.PER_HIT && !ctx.isSkill()) return atk.weaponKind();
        return DamageKind.of(ctx.type());
    }

    /**
     * 플레이어 공격의 원피해 (방어·치명 전) = 기준 × 피해 종류의 배율 × 배율 × (마법이면 1 + 마법 피해 가산).
     * 공격자 능력치가 없으면 배율 그대로 (예전과 같음).
     */
    public static double rawAmount(DerivedStats atk, DamageContext.Base base, DamageKind kind, double multiplier) {
        if (atk == null) return multiplier;
        double b = base == DamageContext.Base.SKILL ? atk.skillPower() : atk.weaponDamage();
        double magic = kind == DamageKind.MAGIC ? atk.magicDamage() : kind == DamageKind.HYBRID ? 0.5 * atk.magicDamage() : 0;
        return b * atk.power(kind) * multiplier * Math.max(0.1, 1.0 + magic);
    }

    /** 치유 (커스텀 HP 단위, 출처 = {@link HealKind#OTHER}, 전부 '최대 HP 비율' 몫). 플레이어·커스텀 몹 공통. @return 실제 회복량 */
    public double heal(LivingEntity target, double amount, boolean showNumber) {
        return heal(target, amount, 0, HealKind.OTHER, showNumber);
    }

    /**
     * 치유 (pvp_spec §8). pctAmount = 최대 HP 비율로 정한 몫, flatAmount = 고정량 몫(치유력·흡혈·재생).
     * 대상이 PvP 전투 중인 플레이어면 (pct + flat × HP÷PvP 체력) × 출처 배율 × 긴 싸움, 아니면 둘을 더한 그대로.
     * @return 실제 회복량
     */
    public double heal(LivingEntity target, double pctAmount, double flatAmount, HealKind kind, boolean showNumber) {
        return applyHeal(target, healAmount(target, pctAmount, flatAmount, kind), showNumber);
    }

    /** {@link #heal(LivingEntity, double, double, HealKind, boolean)} 가 실제로 넣을 양 (넣지는 않음 — 넘친 치유 계산 등). */
    public double healAmount(LivingEntity target, double pctAmount, double flatAmount, HealKind kind) {
        double pct = Math.max(0, pctAmount), flat = Math.max(0, flatAmount);
        if (target instanceof Player p) {
            kr.labyrinth.pvp.PvpState pvp = services.targets().pvp();
            return (pct + flat * pvp.flatHealFactor(p)) * pvp.healFactor(p, kind == null ? HealKind.OTHER : kind);
        }
        return pct + flat;
    }

    /** 흡혈: 플레이어를 때려 얻은 것은 {@link HealKind#LIFESTEAL}, 몹을 때려 얻은 것은 고정량 회복. @return 실제 회복량 */
    public double lifesteal(Player attacker, LivingEntity victim, double amount, boolean showNumber) {
        if (attacker == null || amount <= 0) return 0;
        return heal(attacker, 0, amount, victim instanceof Player ? HealKind.LIFESTEAL : HealKind.OTHER, showNumber);
    }

    /** 이미 정해진 양을 그대로 넣는다 (PvP 배율 없음 — {@link #healAmount} 로 구한 값). @return 실제 회복량 */
    public double applyHeal(LivingEntity target, double amount, boolean showNumber) {
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
        if (kr.labyrinth.mine.MineSafety.protects(services.mine(), p)) return false; // 광산 (0.3.6) — deal 에서 이미 막지만 한 번 더
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

    /**
     * 플레이어가 밀려나는 세기 배율 = 1 − 밀려남 저항 (힘 + 판금 4부위 버팀 + 넉백 면역, 바닐라 속성 값). 보스가 민 것·플레이어가 아닌 대상은 1.
     * 몬스터 스킬·상태이상 밀쳐내기·무기 스킬 밀어내기·함정이 같은 값을 쓴다 (look_spec §1.3).
     */
    public double knockbackScale(LivingEntity target, LivingEntity from) {
        if (!(target instanceof Player p)) return 1.0;
        boolean boss = from != null && services.bosses().byEntity(from).isPresent();
        var a = p.getAttribute(org.bukkit.attribute.Attribute.KNOCKBACK_RESISTANCE);
        double resist = a == null ? services.stats().get(p).knockbackResistance() : a.getValue();
        return CrowdControl.knockback(1.0, Math.max(0, Math.min(1, resist)), boss);
    }

    private void knockback(LivingEntity target, LivingEntity from, double strength) {
        strength *= knockbackScale(target, from);
        if (strength <= 1e-6) return;
        Vector dir = target.getLocation().toVector().subtract(from.getLocation().toVector()).setY(0);
        if (dir.lengthSquared() < 1e-6) return;
        dir.normalize().multiply(0.4 * strength).setY(Math.min(0.5, 0.15 + 0.1 * strength));
        target.setVelocity(target.getVelocity().add(dir));
    }
}
