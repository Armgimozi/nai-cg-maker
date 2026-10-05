package kr.augsky.skill;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.util.Text;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.IronGolem;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.Tameable;
import org.bukkit.entity.Zombie;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityTargetLivingEntityEvent;
import org.bukkit.persistence.PersistentDataType;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/** 플레이어 스킬로 소환한 아군. 일정 시간 뒤 사라지고, 주인의 적을 공격한다. */
public final class Allies implements Listener {
    private final AugSky plugin;
    private final Map<UUID, Long> expire = new HashMap<>();
    private final Map<UUID, UUID> owner = new HashMap<>();

    public Allies(AugSky plugin) {
        this.plugin = plugin;
        plugin.getServer().getScheduler().runTaskTimer(plugin, this::tick, 20, 10);
    }

    public void summon(SkillContext ctx, Location at, String type, String name, double seconds, double health, double damage) {
        EntityType et;
        try {
            et = EntityType.valueOf(type.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            plugin.getLogger().warning("소환할 수 없는 엔티티: " + type);
            return;
        }
        if (et.getEntityClass() == null || !LivingEntity.class.isAssignableFrom(et.getEntityClass())) return;
        Player p = ctx.caster instanceof Player pl ? pl : null;
        Entity e = at.getWorld().spawnEntity(at, et, CreatureSpawnEvent.SpawnReason.CUSTOM, ent -> {
            ent.getPersistentDataContainer().set(Keys.ALLY, PersistentDataType.STRING,
                    p == null ? "" : p.getUniqueId().toString());
            ent.setPersistent(false);
            if (name != null) {
                ent.customName(Text.mm(name));
                ent.setCustomNameVisible(true);
            }
            if (ent instanceof LivingEntity le) {
                le.setRemoveWhenFarAway(true);
                if (health > 0) {
                    AttributeInstance a = le.getAttribute(Attribute.MAX_HEALTH);
                    if (a != null) {
                        a.setBaseValue(health);
                        le.setHealth(health);
                    }
                }
                if (damage > 0) {
                    AttributeInstance a = le.getAttribute(Attribute.ATTACK_DAMAGE);
                    if (a != null) a.setBaseValue(damage);
                }
            }
            if (ent instanceof Tameable t && p != null) {
                t.setOwner(p);
                t.setTamed(true);
            }
            if (ent instanceof IronGolem g) g.setPlayerCreated(true);
            if (ent instanceof Zombie z) {
                z.setShouldBurnInDay(false);
                z.setAdult();
            }
        });
        expire.put(e.getUniqueId(), System.currentTimeMillis() + (long) (seconds * 1000));
        if (p != null) owner.put(e.getUniqueId(), p.getUniqueId());
    }

    private void tick() {
        long now = System.currentTimeMillis();
        Iterator<Map.Entry<UUID, Long>> it = expire.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<UUID, Long> en = it.next();
            Entity e = plugin.getServer().getEntity(en.getKey());
            if (e == null || !e.isValid()) {
                it.remove();
                owner.remove(en.getKey());
                continue;
            }
            if (now >= en.getValue()) {
                e.getWorld().spawnParticle(Particle.POOF, e.getLocation().add(0, 0.5, 0), 12, 0.3, 0.3, 0.3, 0.02);
                e.remove();
                it.remove();
                owner.remove(en.getKey());
                continue;
            }
            if (e instanceof Mob m) {
                LivingEntity t = m.getTarget();
                if (t == null || !t.isValid() || !Targets.isEnemy(m, t)) {
                    LivingEntity best = null;
                    double bd = 16 * 16;
                    for (LivingEntity c : Targets.enemiesNear(m, m.getLocation(), 16)) {
                        double d = c.getLocation().distanceSquared(m.getLocation());
                        if (d < bd) {
                            bd = d;
                            best = c;
                        }
                    }
                    m.setTarget(best);
                    if (best == null) followOwner(m);
                }
            }
        }
    }

    private void followOwner(Mob m) {
        UUID o = owner.get(m.getUniqueId());
        if (o == null) return;
        Player p = plugin.getServer().getPlayer(o);
        if (p == null || !p.getWorld().equals(m.getWorld())) return;
        if (p.getLocation().distanceSquared(m.getLocation()) > 25 * 25) m.teleport(p.getLocation());
        else if (p.getLocation().distanceSquared(m.getLocation()) > 6 * 6) m.getPathfinder().moveTo(p.getLocation(), 1.2);
    }

    @EventHandler(ignoreCancelled = true)
    public void onTarget(EntityTargetLivingEntityEvent e) {
        if (Targets.isAlly(e.getEntity()) && e.getTarget() != null && !Targets.isEnemy((LivingEntity) e.getEntity(), e.getTarget())) {
            e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onAllyHit(EntityDamageByEntityEvent e) {
        Entity d = e.getDamager();
        if (d instanceof org.bukkit.entity.Projectile pr && pr.getShooter() instanceof Entity s) d = s;
        if (Targets.isAlly(d) && (e.getEntity() instanceof Player || Targets.isAlly(e.getEntity()))) e.setCancelled(true);
        if (d instanceof Player && Targets.isAlly(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler
    public void onDeath(EntityDeathEvent e) {
        if (Targets.isAlly(e.getEntity())) {
            e.getDrops().clear();
            e.setDroppedExp(0);
        }
    }

    public void removeAll() {
        for (UUID id : expire.keySet()) {
            Entity e = plugin.getServer().getEntity(id);
            if (e != null) e.remove();
        }
        expire.clear();
        owner.clear();
    }
}
