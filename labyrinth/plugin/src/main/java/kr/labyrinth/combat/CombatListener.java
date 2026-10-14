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
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.AbstractArrow;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDamageEvent.DamageCause;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.persistence.PersistentDataType;

/**
 * 바닐라 전투 이벤트 → {@link DamageService} 연결.
 * <ul>
 *   <li>플레이어 근접/화살 → 커스텀 몹·보스: 바닐라 피해 취소, 공격력 × 공격 쿨다운(또는 활 당김) 배율로 계산</li>
 *   <li>커스텀 몹의 바닐라 공격 → 플레이어: 취소하고 몹 damage 로 계산</li>
 *   <li>커스텀 몹이 받는 그 밖의 바닐라 피해(낙하·불 등): 취소 (자체 HP 풀)</li>
 *   <li>그 외 플레이어가 받는 바닐라 피해: 'HP 20 기준 비율'로 환산 (config combat.scale_vanilla_damage)</li>
 * </ul>
 * 플레이어끼리의 피해는 건드리지 않는다 (PvP 모듈 담당).
 */
final class CombatListener implements Listener {

    /** 비율 환산하지 않는 원인 (즉사·명령 등). */
    private static final Set<DamageCause> NO_SCALE = EnumSet.of(DamageCause.KILL, DamageCause.VOID,
            DamageCause.SUICIDE, DamageCause.CUSTOM, DamageCause.WORLD_BORDER);

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
                if (damager instanceof Projectile proj) {
                    Float force = proj.getPersistentDataContainer().get(Keys.ARROW_FORCE, PersistentDataType.FLOAT);
                    double mult = force == null ? 0.6 : Math.max(0.1, force);
                    if (be.isCritical()) mult *= 1.25;
                    damage.deal(DamageContext.attack(player, target, mult, DamageType.RANGED));
                    if (proj instanceof AbstractArrow) proj.remove();
                } else if (be.getCause() == DamageCause.ENTITY_ATTACK || be.getCause() == DamageCause.ENTITY_SWEEP_ATTACK) {
                    float cd = preAttackCooldown.getOrDefault(player.getUniqueId(), 1f);
                    double mult = 0.2 + cd * cd * 0.8;
                    if (be.getCause() == DamageCause.ENTITY_SWEEP_ATTACK) mult *= 0.35;
                    if (be.isCritical()) mult *= 1.2;
                    damage.deal(DamageContext.attack(player, target, mult, DamageType.MELEE));
                }
                return;
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
                if (source instanceof Player) return; // PvP 는 pvp 모듈 담당
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
}
