package kr.souls.combat;

import io.papermc.paper.event.entity.EntityPushedByEntityAttackEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.souls.Souls;
import org.bukkit.damage.DamageSource;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EvokerFangs;
import org.bukkit.entity.LightningStrike;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.entity.Tameable;
import org.bukkit.entity.ThrownPotion;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.AreaEffectCloudApplyEvent;
import org.bukkit.event.entity.EntityCombustByEntityEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityTargetEvent;
import org.bukkit.event.entity.PotionSplashEvent;
import org.bukkit.event.entity.ProjectileHitEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.projectiles.ProjectileSource;

import java.util.ArrayList;
import java.util.List;

/**
 * PvP 를 끈 세계에서 플레이어 → 플레이어를 막는 곳 (5.7). 넷을 모두 켜 둔다:
 * <ol>
 *   <li>바닐라 규칙 pvp=false (WorldService 가 세계 설정을 따라 건다): 바닐라는 원인이 다른 플레이어거나 그가 쏜 화살이면 이벤트 없이
 *       피해를 버린다 [확인 (서버 코드): ServerPlayer.hurtServer 의 canHarmPlayer]. 그래서 근접·투사체 막기는 그보다 앞선 이벤트
 *       (PrePlayerAttackEntityEvent, ProjectileHitEvent) 에서 시험 줄을 낸다.</li>
 *   <li>피해 이벤트 (가장 낮은 단계): 때린 것을 사람으로 되짚어 (플레이어, 쏜 사람, 잔류 구름·TNT 의 주인, 길들인 짐승의 주인, 소환사
 *       송곳니의 주인, 번개를 부른 사람, 마지막으로 DamageSource 의 원인) 다른 플레이어면 취소한다. 가시도 같다.</li>
 *   <li>피해가 없는 길: 밀림 (폭발·바람 돌격 포함), 불붙이기, 낚싯대 끌기, 투척 물약 (해로운 것만 세기 0), 잔류 물약 구름.
 *       Paper 1.21.11 은 투척·잔류 물약에 PvP 를 보지 않는다 [확인 (서버 코드), 검토 T8].</li>
 *   <li>플러그인의 길: Targets.isEnemy, skill/Combat.damage (Pvp.allowed 를 본다).</li>
 * </ol>
 * 출신을 고르지 않은 사람은 적·다른 플레이어 누구에게도 맞지 않는다 (적은 그를 노리지 않는다, 5.10).
 * 시험 줄: PVP_BLOCK path=&lt;melee|projectile|potion|cloud|knockback|combust|fish|thorns|tnt|tamed|other&gt; from= to=
 */
public final class PvpGuard implements Listener {
    private final Souls plugin;

    public PvpGuard(Souls plugin) {
        this.plugin = plugin;
    }

    /** 때린 것을 사람으로 되짚는다 (없으면 null). */
    public static Player trace(Entity damager, DamageSource src) {
        if (damager instanceof Player p) return p;
        if (damager instanceof Projectile pr && pr.getShooter() instanceof Player p) return p;
        if (damager instanceof AreaEffectCloud c && c.getSource() instanceof Player p) return p;
        if (damager instanceof TNTPrimed t && t.getSource() instanceof Player p) return p;
        if (damager instanceof Tameable t && t.getOwner() instanceof Player p) return p;
        if (damager instanceof EvokerFangs f && f.getOwner() instanceof Player p) return p;
        if (damager instanceof LightningStrike l && l.getCausingPlayer() != null) return l.getCausingPlayer();
        if (src != null && src.getCausingEntity() instanceof Player p) return p;
        return null;
    }

    private static String path(Entity damager, EntityDamageEvent.DamageCause cause) {
        if (cause == EntityDamageEvent.DamageCause.THORNS) return "thorns";
        if (damager instanceof Player) return "melee";
        if (damager instanceof ThrownPotion) return "potion";
        if (damager instanceof Projectile) return "projectile";
        if (damager instanceof AreaEffectCloud) return "cloud";
        if (damager instanceof TNTPrimed) return "tnt";
        if (damager instanceof Tameable) return "tamed";
        return "other";
    }

    private void block(String path, Player from, Player to) {
        plugin.test(to, "PVP_BLOCK path=" + path + " from=" + (from == null ? "-" : from.getName()) + " to=" + to.getName()
                + " why=" + (plugin.pvp().enabled() ? String.valueOf(plugin.pvp().protectedWhy(to)) : "off") + " t=" + plugin.ticker().now());
    }

    private boolean denied(Player from, Player to) {
        return from != null && !from.equals(to) && !plugin.pvp().allowed(from, to);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDamage(EntityDamageByEntityEvent e) {
        if (!(e.getEntity() instanceof Player v)) return;
        Player from = trace(e.getDamager(), e.getDamageSource());
        if (denied(from, v)) {
            e.setCancelled(true);
            block(path(e.getDamager(), e.getCause()), from, v);
            return;
        }
        // 출신을 고르지 않은 사람은 적에게도 맞지 않는다
        if (from == null && !plugin.profiles().of(v).born() && e.getDamager() != v) {
            e.setCancelled(true);
            plugin.test(v, "UNBORN_SAFE from=" + e.getDamager().getType().key().value() + " t=" + plugin.ticker().now());
        }
    }

    @EventHandler(priority = EventPriority.LOW)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        if (e.isCancelled() || !(e.getAttacked() instanceof Player v)) return;
        if (denied(e.getPlayer(), v)) {
            e.setCancelled(true);
            block("melee", e.getPlayer(), v);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onProjectile(ProjectileHitEvent e) {
        if (!(e.getHitEntity() instanceof Player v)) return;
        ProjectileSource s = e.getEntity().getShooter();
        if (s instanceof Player from && denied(from, v)) {
            e.setCancelled(true);
            block(e.getEntity() instanceof ThrownPotion ? "potion" : "projectile", from, v);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onSplash(PotionSplashEvent e) {
        if (!(e.getPotion().getShooter() instanceof Player from) || !harmful(e.getPotion().getEffects())) return;
        for (LivingEntity le : new ArrayList<>(e.getAffectedEntities())) {
            if (le instanceof Player v && denied(from, v)) {
                e.setIntensity(v, 0);
                block("potion", from, v);
            }
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onCloud(AreaEffectCloudApplyEvent e) {
        AreaEffectCloud c = e.getEntity();
        if (!(c.getSource() instanceof Player from)) return;
        List<PotionEffect> effects = new ArrayList<>(c.getCustomEffects());
        if (c.getBasePotionType() != null) effects.addAll(c.getBasePotionType().getPotionEffects());
        if (!harmful(effects)) return;
        e.getAffectedEntities().removeIf(le -> {
            if (le instanceof Player v && denied(from, v)) {
                block("cloud", from, v);
                return true;
            }
            return false;
        });
    }

    private static boolean harmful(java.util.Collection<PotionEffect> effects) {
        for (PotionEffect pe : effects) if (pe.getType().getCategory() == PotionEffectType.Category.HARMFUL) return true;
        return false;
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPushed(EntityPushedByEntityAttackEvent e) {
        if (!(e.getEntity() instanceof Player v)) return;
        Player from = trace(e.getPushedBy(), null);
        if (denied(from, v)) {
            e.setCancelled(true);
            block("knockback", from, v);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onCombust(EntityCombustByEntityEvent e) {
        if (!(e.getEntity() instanceof Player v)) return;
        Player from = trace(e.getCombuster(), null);
        if (denied(from, v)) {
            e.setCancelled(true);
            block("combust", from, v);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFish(PlayerFishEvent e) {
        if (e.getState() == PlayerFishEvent.State.CAUGHT_ENTITY && e.getCaught() instanceof Player v && denied(e.getPlayer(), v)) {
            e.setCancelled(true);
            block("fish", e.getPlayer(), v);
        }
    }

    /** 적은 출신이 없는 사람을 노리지 않는다. */
    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onTarget(EntityTargetEvent e) {
        if (e.getTarget() instanceof Player v && !plugin.profiles().of(v).born()) e.setCancelled(true);
    }
}
