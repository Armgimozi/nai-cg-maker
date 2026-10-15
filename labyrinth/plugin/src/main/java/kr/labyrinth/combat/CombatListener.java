package kr.labyrinth.combat;

import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import java.util.EnumSet;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.mobs.CustomMob;
import kr.labyrinth.pvp.PvpSources;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.AbstractArrow;
import org.bukkit.entity.Arrow;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.SpectralArrow;
import org.bukkit.entity.Trident;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDamageEvent.DamageCause;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.potion.PotionType;

/**
 * 바닐라 전투 이벤트 → {@link DamageService} 연결.
 * <ul>
 *   <li>플레이어 근접 / 화살·삼지창 → 커스텀 몹·보스: 바닐라 피해 취소, 공격력 × 공격 쿨다운(또는 활 당김) 배율로 계산.
 *       눈덩이·알 같은 그 밖의 투사체는 피해 없음</li>
 *   <li>미궁 무기 근접 / 미궁 활 화살 → 미궁 밖 바닐라 적대 몹({@code services.targets().isEnemy}): 위와 같은 공식 (스킬과 같은 단위).
 *       바닐라 무기는 바닐라 피해 그대로</li>
 *   <li>커스텀 몹의 바닐라 공격 → 플레이어: 취소하고 몹 damage 로 계산</li>
 *   <li>플레이어(또는 그가 쏜 것·불붙인 TNT·깨뜨린 엔드 수정·길들인 동물, {@link PvpSources}) → 다른 플레이어 = PvP:
 *       {@code services.targets().isEnemy} 가 아니면(같은 파티·안전지대·PvP 꺼짐) 취소. 근접·화살·삼지창은 몹 상대와 같은 공식으로
 *       DamageService 에 넘기고(미궁 스탯·방어·치명타·피해 숫자 — 플레이어끼리 배율·한 방 상한은 pvp 훅), 바닐라가 하던
 *       넉백·발화(화염·화염 화살)·물약 화살 효과를 다시 건다. 그 밖(폭발·물약·눈덩이·늑대 등)은 바닐라 피해 → 아래 비율 환산
 *       → pvp 리스너가 배율·상한</li>
 *   <li>커스텀 몹이 받는 그 밖의 바닐라 피해(낙하·불 등): 취소 (자체 HP 풀)</li>
 *   <li>그 외 플레이어가 받는 바닐라 피해: 'HP 20 기준 비율'로 환산 (config combat.scale_vanilla_damage)</li>
 * </ul>
 */
final class CombatListener implements Listener {

    /** 비율 환산하지 않는 원인 (즉사·명령 등). */
    private static final Set<DamageCause> NO_SCALE = EnumSet.of(DamageCause.KILL, DamageCause.VOID,
            DamageCause.SUICIDE, DamageCause.CUSTOM, DamageCause.WORLD_BORDER);

    /** 던진 삼지창의 바닐라 피해. 손을 떠난 뒤라 지금 든 무기 대신 이 값 × 주스탯 배율로 친다. */
    static final double THROWN_TRIDENT_DAMAGE = 8.0;

    private final Services services;
    private final DamageService damage;
    private final Map<UUID, Float> preAttackCooldown = new ConcurrentHashMap<>();

    CombatListener(Services services, DamageService damage) {
        this.services = services;
        this.damage = damage;
    }

    /** 공격 직전의 쿨다운 (데미지 이벤트 시점엔 이미 0 으로 리셋되어 있음). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPreAttack(PrePlayerAttackEntityEvent e) {
        preAttackCooldown.put(e.getPlayer().getUniqueId(), e.getPlayer().getAttackCooldown());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { preAttackCooldown.remove(e.getPlayer().getUniqueId()); }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onShoot(EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof Player p) || !(e.getProjectile() instanceof Projectile proj)) return;
        proj.getPersistentDataContainer().set(Keys.ARROW_FORCE, PersistentDataType.FLOAT, e.getForce());
        ItemDef bow = services.items().heldWeapon(p);
        if (bow != null) proj.getPersistentDataContainer().set(Keys.ARROW_WEAPON, PersistentDataType.STRING, bow.id());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (damage.isApplyingVanilla()) return;
        Entity victim = e.getEntity();
        Optional<HealthPool> victimPool = damage.poolOf(victim);

        if (e instanceof EntityDamageByEntityEvent be) {
            Entity damager = be.getDamager();
            LivingEntity source = damager instanceof Projectile proj && proj.getShooter() instanceof LivingEntity sh ? sh
                    : damager instanceof LivingEntity le ? le : null;

            // 플레이어 → 커스텀 몹
            if (source instanceof Player player && victimPool.isPresent() && victim instanceof LivingEntity target) {
                e.setCancelled(true);
                if (!services.targets().isEnemy(player, target)) return;
                if (damager instanceof AbstractArrow arrow) {
                    damage.deal(DamageContext.attack(player, target, rangedMult(player, arrow, be.isCritical()), DamageType.RANGED));
                    if (!(arrow instanceof Trident)) arrow.remove(); // 삼지창은 지우면 잃어버린다 — 바닐라처럼 튕겨 떨어지게
                } else if (isMelee(be, damager, player)) {
                    damage.deal(DamageContext.attack(player, target, meleeMult(player, be), DamageType.MELEE));
                }
                return;
            }
            // 플레이어 → 미궁 밖 바닐라 적대 몹: 미궁 무기 평타·미궁 활 화살은 스킬과 같은 미궁 공격력으로 (바닐라 무기는 바닐라 피해 그대로).
            // 바닐라 몹이라 DamageService 가 바닐라 피해로 넣으면서(applyVanilla) 기본 넉백도 바닐라가 붙인다
            if (source instanceof Player player && victimPool.isEmpty() && victim instanceof LivingEntity target && !(victim instanceof Player)) {
                boolean melee = isMelee(be, damager, player) && services.items().heldWeapon(player) != null;
                AbstractArrow arrow = !melee && damager instanceof AbstractArrow a && !(a instanceof Trident) && firedFromLabyrinthBow(a) ? a : null;
                if ((melee || arrow != null) && services.targets().isEnemy(player, target)) {
                    e.setCancelled(true);
                    if (melee) {
                        damage.deal(DamageContext.attack(player, target, meleeMult(player, be), DamageType.MELEE));
                    } else {
                        damage.deal(DamageContext.attack(player, target, rangedMult(player, arrow, be.isCritical()), DamageType.RANGED));
                        arrow.remove();
                    }
                    return;
                }
            }
            // 커스텀 몹 → 플레이어
            if (victim instanceof Player player && source != null) {
                Optional<HealthPool> attackerPool = damage.poolOf(source);
                if (attackerPool.isPresent()) {
                    e.setCancelled(true);
                    if (attackerPool.get() instanceof CustomMob mob && mob.isAlive()) {
                        DamageType type = damager instanceof Projectile ? DamageType.RANGED : DamageType.MELEE;
                        damage.deal(DamageContext.raw(source, player, mob.damage(), type).source("basic_attack"));
                    }
                    if (damager instanceof Projectile proj && proj instanceof AbstractArrow) proj.remove();
                    return;
                }
            }
            // 플레이어 → 다른 플레이어 (PvP: 같은 파티원끼리는 어디서든 피해 없음)
            if (victim instanceof Player vp) {
                Player culprit = PvpSources.playerBehind(damager, e.getDamageSource());
                if (culprit != null && !culprit.equals(vp)) {
                    if (!services.targets().isEnemy(culprit, vp)) {
                        e.setCancelled(true);
                        if (damager instanceof AbstractArrow arrow && !(arrow instanceof Trident)) arrow.remove();
                        return;
                    }
                    if (isMelee(be, damager, culprit)) {
                        e.setCancelled(true);
                        pvpMelee(culprit, vp, be);
                        return;
                    }
                    if (damager instanceof AbstractArrow arrow && culprit.equals(arrow.getShooter())) {
                        e.setCancelled(true);
                        pvpArrow(culprit, vp, arrow, be.isCritical());
                        return;
                    }
                    // 그 밖(폭발·물약·눈덩이·늑대 등)은 바닐라 피해 그대로 → 아래 비율 환산, 배율·상한은 pvp 리스너
                }
            }
        }

        // 커스텀 몹의 그 밖의 바닐라 피해는 무시 (자체 HP 풀)
        if (victimPool.isPresent()) {
            if (e.getCause() != DamageCause.VOID && e.getCause() != DamageCause.KILL) e.setCancelled(true);
            return;
        }
        // 플레이어가 받는 바닐라 피해 비율 환산
        if (victim instanceof Player p && services.settings().combat().scaleVanillaDamage() && !NO_SCALE.contains(e.getCause())) {
            var mh = p.getAttribute(Attribute.MAX_HEALTH);
            double vanillaMax = mh == null ? 20.0 : mh.getValue();
            if (vanillaMax > 20.0) e.setDamage(e.getDamage() * vanillaMax / 20.0);
        }
    }

    // ── 배율 (몹 상대·PvP 공통) ────────────────────────────────────────────

    /** 미궁 활로 쏜 화살인가 (쏠 때 든 미궁 무기 id 가 붙고, 그 무기가 활). */
    private boolean firedFromLabyrinthBow(AbstractArrow arrow) {
        String id = arrow.getPersistentDataContainer().get(Keys.ARROW_WEAPON, PersistentDataType.STRING);
        ItemDef def = id == null ? null : services.content().item(id);
        return def != null && def.isWeapon() && "bow".equals(def.weaponType());
    }

    private static boolean isMelee(EntityDamageByEntityEvent be, Entity damager, Player attacker) {
        return attacker.equals(damager) && (be.getCause() == DamageCause.ENTITY_ATTACK || be.getCause() == DamageCause.ENTITY_SWEEP_ATTACK);
    }

    /** 근접: 공격 게이지(0.2 + 0.8 × 충전²) · 휩쓸기 ×0.35 · 점프 치명타 ×1.2. */
    private double meleeMult(Player p, EntityDamageByEntityEvent be) {
        float cd = preAttackCooldown.getOrDefault(p.getUniqueId(), 1f);
        double mult = 0.2 + cd * cd * 0.8;
        if (be.getCause() == DamageCause.ENTITY_SWEEP_ATTACK) mult *= 0.35;
        if (be.isCritical()) mult *= 1.2;
        return mult;
    }

    /** 화살: 활 당김 세기(없으면 0.6) · 치명 화살 ×1.25. 삼지창: 바닐라 던지기 피해 8 × 주스탯 배율. */
    private double rangedMult(Player p, AbstractArrow arrow, boolean critical) {
        if (arrow instanceof Trident) {
            double weapon = services.stats().get(p).weaponDamage();
            return weapon > 0 ? THROWN_TRIDENT_DAMAGE / weapon : 1.0;
        }
        Float force = arrow.getPersistentDataContainer().get(Keys.ARROW_FORCE, PersistentDataType.FLOAT);
        double mult = force == null ? 0.6 : Math.max(0.1, force);
        if (critical) mult *= 1.25;
        return mult;
    }

    // ── PvP: 몹 상대와 같은 공식 + 바닐라 부가 효과 ─────────────────────────

    private void pvpMelee(Player attacker, Player victim, EntityDamageByEntityEvent be) {
        float cd = preAttackCooldown.getOrDefault(attacker.getUniqueId(), 1f);
        ItemStack weapon = attacker.getInventory().getItemInMainHand();
        boolean sweep = be.getCause() == DamageCause.ENTITY_SWEEP_ATTACK;
        // 바닐라 넉백: 맞으면 기본 0.4, 꽉 찬 공격의 달리기 +1·밀치기 레벨당 +1 (×0.5) → DamageService 단위(0.4 = 1)
        double kb = sweep ? 1.0 : 1.0 + 1.25 * ((cd > 0.9f && attacker.isSprinting() ? 1 : 0) + level(weapon, Enchantment.KNOCKBACK));
        DamageContext ctx = damage.deal(DamageContext.attack(attacker, victim, meleeMult(attacker, be), DamageType.MELEE)
                .knockback(kb * (1.0 - knockbackResistance(victim))));
        if (landed(ctx) && !sweep) {
            int fire = level(weapon, Enchantment.FIRE_ASPECT);
            if (fire > 0) igniteLater(victim, fire * 80);
        }
    }

    private void pvpArrow(Player shooter, Player victim, AbstractArrow arrow, boolean critical) {
        int punch = 0;
        try {
            punch = level(arrow.getWeapon(), Enchantment.PUNCH);
        } catch (Throwable ignored) {
            // 쏜 무기 정보가 없는 투사체
        }
        double kb = arrow instanceof Trident ? 1.0 : 0.6 + 1.5 * punch;
        DamageContext ctx = damage.deal(DamageContext.attack(shooter, victim, rangedMult(shooter, arrow, critical), DamageType.RANGED)
                .knockback(kb * (1.0 - knockbackResistance(victim))));
        if (landed(ctx)) {
            if (arrow.getFireTicks() > 0) igniteLater(victim, 100);
            if (arrow instanceof Arrow tipped) applyTipped(tipped, victim);
            if (arrow instanceof SpectralArrow) victim.addPotionEffect(new PotionEffect(PotionEffectType.GLOWING, 200, 0));
        }
        if (!(arrow instanceof Trident)) arrow.remove();
    }

    /** 물약 화살: 기본 물약 효과는 바닐라처럼 지속시간 1/8, 직접 넣은 효과는 그대로. */
    private static void applyTipped(Arrow arrow, LivingEntity victim) {
        PotionType base = arrow.getBasePotionType();
        if (base != null) {
            for (PotionEffect pe : base.getPotionEffects()) {
                victim.addPotionEffect(new PotionEffect(pe.getType(), Math.max(1, pe.getDuration() / 8), pe.getAmplifier(),
                        pe.isAmbient(), pe.hasParticles()));
            }
        }
        if (arrow.hasCustomEffects()) for (PotionEffect pe : arrow.getCustomEffects()) victim.addPotionEffect(pe);
    }

    /**
     * 다음 틱에 불붙이기. 바닐라는 화살 피해가 실패(우리가 취소)하면 맞기 전 불 상태로 되돌리므로 이벤트 안에서 붙이면 지워진다.
     */
    private void igniteLater(LivingEntity victim, int ticks) {
        org.bukkit.Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (!victim.isValid() || victim.isDead() || victim instanceof Player p && p.getGameMode().isInvulnerable()) return;
            victim.setFireTicks(Math.max(victim.getFireTicks(), ticks));
        });
    }

    private static boolean landed(DamageContext ctx) {
        return !ctx.cancelled() && !ctx.evaded() && ctx.finalDamage() > 0;
    }

    private static int level(ItemStack it, Enchantment ench) {
        return it == null || it.getType().isAir() ? 0 : it.getEnchantmentLevel(ench);
    }

    private static double knockbackResistance(LivingEntity e) {
        AttributeInstance a = e.getAttribute(Attribute.KNOCKBACK_RESISTANCE);
        return a == null ? 0 : Math.max(0, Math.min(1, a.getValue()));
    }
}
