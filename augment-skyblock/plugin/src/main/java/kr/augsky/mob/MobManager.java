package kr.augsky.mob;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.skill.Combat;
import kr.augsky.skill.HitEffects;
import kr.augsky.skill.Mechanics;
import kr.augsky.skill.SkillContext;
import kr.augsky.skill.SkillDef;
import kr.augsky.skill.Targets;
import kr.augsky.util.Fx;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.block.Block;
import org.bukkit.entity.AbstractSkeleton;
import org.bukkit.entity.Ageable;
import org.bukkit.entity.Creeper;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Marker;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Phantom;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.Slime;
import org.bukkit.entity.Zombie;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.entity.EntityTransformEvent;
import org.bukkit.event.entity.SlimeSplitEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.event.world.EntitiesUnloadEvent;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.LeatherArmorMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/** 커스텀 몬스터: 소환, 능력 사용, 보스바, 드롭, 자연 스폰 교체, 균열 스폰. 보스 둥지는 Lairs, 보스 모델은 Rigs. */
public final class MobManager implements Listener {
    private final AugSky plugin;
    private final MobRegistry registry;
    private final Map<UUID, Active> active = new HashMap<>();
    private final Map<UUID, String> riftMarkers = new HashMap<>();
    private final Lairs lairs;
    private final Rigs rigs;
    private int tick;

    static final class Active {
        final MobDef def;
        final LivingEntity entity;
        final Map<Integer, Long> readyAt = new HashMap<>();
        final Set<Integer> phases = new HashSet<>();
        final Map<UUID, Double> contributors = new HashMap<>();
        BossBar bar;
        final Set<UUID> viewers = new HashSet<>();
        Location home;
        long lastHurtByPlayer;

        Active(MobDef def, LivingEntity entity) {
            this.def = def;
            this.entity = entity;
        }
    }

    public MobManager(AugSky plugin, MobRegistry registry) {
        this.plugin = plugin;
        this.registry = registry;
        this.lairs = new Lairs(plugin, this);
        this.rigs = new Rigs(plugin);
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 20, 5);
    }

    public MobRegistry registry() {
        return registry;
    }

    public Lairs lairs() {
        return lairs;
    }

    public Rigs rigs() {
        return rigs;
    }

    /** 제단 보호처럼 보스 둥지의 블록을 지킨다. */
    public boolean isLairGuarded(Location l) {
        return lairs.isGuarded(l);
    }

    /** 플레이어에게 마지막으로 맞은 뒤 지난 시간(ms). 기록이 없으면 아주 큰 값. */
    long sinceHurtByPlayer(LivingEntity boss) {
        Active a = active.get(boss.getUniqueId());
        return a == null || a.lastHurtByPlayer == 0 ? Long.MAX_VALUE : System.currentTimeMillis() - a.lastHurtByPlayer;
    }

    /** 싸움이 끝났을 때(둥지로 돌아가 다 회복했을 때) 기여도와 단계 기록을 지운다. */
    void resetFight(LivingEntity boss) {
        Active a = active.get(boss.getUniqueId());
        if (a == null) return;
        a.contributors.clear();
        a.phases.clear();
        a.readyAt.clear();
    }

    private static ThreadLocalRandom rnd() {
        return ThreadLocalRandom.current();
    }

    // ------------------------------------------------------------------ 소환

    public LivingEntity spawn(String id, Location at, boolean minion) {
        MobDef def = registry.get(id);
        if (def == null || at.getWorld() == null) return null;
        Class<? extends Entity> cls = def.type().getEntityClass();
        if (cls == null || !LivingEntity.class.isAssignableFrom(cls)) return null;
        Entity e = at.getWorld().spawnEntity(at, def.type(), CreatureSpawnEvent.SpawnReason.CUSTOM, en -> {
            if (en instanceof LivingEntity le) setup(def, le, minion);
        });
        if (!(e instanceof LivingEntity le)) return null;
        Active a = track(def, le);
        a.home = at.clone();
        if (rigs.has(def.id())) {
            if (le.getEquipment() != null) le.getEquipment().clear();
            rigs.attach(le, def.id());
        }
        if (def.boss()) le.getWorld().strikeLightningEffect(at);
        trigger(a, "on_spawn", null);
        return le;
    }

    private void setup(MobDef def, LivingEntity le, boolean minion) {
        le.getPersistentDataContainer().set(Keys.MOB, PersistentDataType.STRING, def.id());
        le.customName(Text.mm(def.name()));
        le.setCustomNameVisible(def.boss());
        attr(le, Attribute.MAX_HEALTH, def.health());
        le.setHealth(def.health());
        if (def.damage() >= 0) attr(le, Attribute.ATTACK_DAMAGE, def.damage());
        if (def.speed() >= 0) attr(le, Attribute.MOVEMENT_SPEED, def.speed());
        if (def.speed() >= 0 && def.type() == EntityType.PHANTOM) attr(le, Attribute.FLYING_SPEED, def.speed());
        attr(le, Attribute.ARMOR, def.armor());
        attr(le, Attribute.SCALE, def.scale());
        attr(le, Attribute.KNOCKBACK_RESISTANCE, def.knockbackResistance());
        attr(le, Attribute.FOLLOW_RANGE, def.followRange());
        if (def.boss()) {
            le.addScoreboardTag(Targets.BOSS_TAG);
            le.setRemoveWhenFarAway(false);
            le.setPersistent(true);
        } else {
            le.setRemoveWhenFarAway(true);
        }
        if (minion) le.addScoreboardTag("augsky_minion");
        if (def.glowing()) le.setGlowing(true);
        if (le instanceof Zombie z) {
            z.setShouldBurnInDay(def.burnInDay());
            if (def.baby()) z.setBaby();
            else z.setAdult();
        } else if (le instanceof Ageable ag) {
            if (def.baby()) ag.setBaby();
            else ag.setAdult();
        }
        if (le instanceof AbstractSkeleton s) s.setShouldBurnInDay(def.burnInDay());
        if (le instanceof Phantom ph) {
            ph.setShouldBurnInDay(def.burnInDay());
            if (def.size() > 0) ph.setSize(def.size());
        }
        if (le instanceof Slime sl && def.size() > 0) {
            sl.setSize(def.size());
            attr(le, Attribute.MAX_HEALTH, def.health());
            le.setHealth(def.health());
        }
        if (le instanceof Creeper c) {
            c.setExplosionRadius(Math.max(1, def.size() > 0 ? def.size() : 3));
        }
        EntityEquipment eq = le.getEquipment();
        if (eq != null) {
            eq.clear();
            for (Map.Entry<String, String> en : def.equipment().entrySet()) {
                EquipmentSlot slot = slot(en.getKey());
                ItemStack it = equip(en.getValue());
                if (slot == null || it == null) continue;
                eq.setItem(slot, it);
                eq.setDropChance(slot, 0f);
            }
        }
        for (MobDef.Potion p : def.effects()) {
            PotionEffectType t = HitEffects.potion(p.effect());
            if (t != null) le.addPotionEffect(new PotionEffect(t, PotionEffect.INFINITE_DURATION, p.amplifier(), false, false));
        }
    }

    private static void attr(LivingEntity le, Attribute a, double v) {
        AttributeInstance i = le.getAttribute(a);
        if (i != null) i.setBaseValue(v);
    }

    private static EquipmentSlot slot(String s) {
        return switch (s.toLowerCase()) {
            case "mainhand", "hand", "weapon" -> EquipmentSlot.HAND;
            case "offhand" -> EquipmentSlot.OFF_HAND;
            case "head", "helmet" -> EquipmentSlot.HEAD;
            case "chest", "chestplate" -> EquipmentSlot.CHEST;
            case "legs", "leggings" -> EquipmentSlot.LEGS;
            case "feet", "boots" -> EquipmentSlot.FEET;
            default -> null;
        };
    }

    /** "LEATHER_CHESTPLATE:#5a8f3a" 는 염색 가죽. 나머지는 아이템 문자열. */
    private ItemStack equip(String spec) {
        String[] parts = spec.split(":");
        if (parts.length == 2 && parts[1].startsWith("#")) {
            Material m = Material.matchMaterial(parts[0]);
            if (m == null) return null;
            ItemStack it = new ItemStack(m);
            if (it.getItemMeta() instanceof LeatherArmorMeta lm) {
                Color c = Fx.color(parts[1]);
                lm.setColor(c);
                it.setItemMeta(lm);
            }
            return it;
        }
        return plugin.items().spec(spec, 1);
    }

    private Active track(MobDef def, LivingEntity le) {
        Active a = active.get(le.getUniqueId());
        if (a != null) return a;
        a = new Active(def, le);
        active.put(le.getUniqueId(), a);
        if (def.boss()) {
            a.bar = BossBar.bossBar(Text.mm(def.name()), 1f, color(def.bossColor()), BossBar.Overlay.NOTCHED_10);
        }
        return a;
    }

    private static BossBar.Color color(String s) {
        try {
            return BossBar.Color.valueOf(s.toUpperCase());
        } catch (Exception e) {
            return BossBar.Color.RED;
        }
    }

    public String idOf(Entity e) {
        return e == null ? null : e.getPersistentDataContainer().get(Keys.MOB, PersistentDataType.STRING);
    }

    // ------------------------------------------------------------------ 주기 처리

    private void tick() {
        tick++;
        // 능력이 부하를 소환하면 active 에 새 항목이 들어오므로 복사본을 돈다
        for (Active a : new ArrayList<>(active.values())) {
            LivingEntity e = a.entity;
            if (!e.isValid() || e.isDead()) {
                hideBar(a);
                active.remove(e.getUniqueId());
                continue;
            }
            if (a.bar != null) updateBar(a);
            LivingEntity target = target(a);
            if (a.def.boss() && a.home != null) {
                if (e.getLocation().getY() < a.home.getY() - 25) {
                    e.teleport(a.home);
                    e.getWorld().spawnParticle(Particle.REVERSE_PORTAL, a.home, 60, 0.5, 1, 0.5, 0.1);
                }
            }
            double hpRatio = e.getHealth() / Combat.maxHealth(e);
            for (int i = 0; i < a.def.abilities().size(); i++) {
                MobDef.Ability ab = a.def.abilities().get(i);
                if (ab.trigger().equals("hp_below") && hpRatio <= ab.threshold() && a.phases.add(i)) {
                    cast(a, ab, target);
                }
            }
            if (target == null) continue;
            double dist = target.getLocation().distance(e.getLocation());
            long now = System.currentTimeMillis();
            for (int i = 0; i < a.def.abilities().size(); i++) {
                MobDef.Ability ab = a.def.abilities().get(i);
                if (!ab.trigger().equals("timer")) continue;
                if (dist > ab.range()) continue;
                Long ready = a.readyAt.get(i);
                if (ready != null && now < ready) continue;
                // 처음 마주쳤을 때 모든 능력이 한 번에 터지지 않도록 시작 시간을 흩어 둔다
                if (ready == null) {
                    a.readyAt.put(i, now + (long) (rnd().nextDouble(0.3, 1.0) * ab.cooldown() * 1000));
                    continue;
                }
                double cdMul = a.def.boss() && hpRatio < 0.5 ? 0.7 : 1.0;
                a.readyAt.put(i, now + (long) (ab.cooldown() * cdMul * 1000));
                if (rnd().nextDouble() < ab.chance()) {
                    cast(a, ab, target);
                    break;
                }
            }
        }
        if (tick % 8 == 0) riftTick();
    }

    private LivingEntity target(Active a) {
        LivingEntity e = a.entity;
        if (e instanceof Mob m) {
            LivingEntity t = m.getTarget();
            if (t != null && t.isValid() && !t.isDead() && Targets.isEnemy(e, t)) return t;
            if (a.def.boss() || !a.def.abilities().isEmpty()) {
                Player best = null;
                double bd = (a.def.boss() ? 32 : 16);
                bd *= bd;
                for (Player p : e.getWorld().getPlayers()) {
                    if (!Targets.isEnemy(e, p)) continue;
                    double d = p.getLocation().distanceSquared(e.getLocation());
                    if (d < bd) {
                        bd = d;
                        best = p;
                    }
                }
                if (best != null && (a.def.boss() || e.hasLineOfSight(best))) m.setTarget(best);
                return best;
            }
        }
        return null;
    }

    private void cast(Active a, MobDef.Ability ab, LivingEntity target) {
        SkillDef s = plugin.skills().get(ab.skill());
        if (s == null) return;
        SkillContext ctx = new SkillContext(plugin, a.entity, target, a.def.skillPower());
        rigs.swing(a.entity.getUniqueId());
        s.cast(ctx);
    }

    private void trigger(Active a, String trigger, LivingEntity target) {
        long now = System.currentTimeMillis();
        for (int i = 0; i < a.def.abilities().size(); i++) {
            MobDef.Ability ab = a.def.abilities().get(i);
            if (!ab.trigger().equals(trigger)) continue;
            Long ready = a.readyAt.get(i);
            if (ready != null && now < ready) continue;
            if (rnd().nextDouble() >= ab.chance()) continue;
            a.readyAt.put(i, now + (long) (ab.cooldown() * 1000));
            cast(a, ab, target);
        }
    }

    private void updateBar(Active a) {
        float prog = (float) Math.max(0, Math.min(1, a.entity.getHealth() / Combat.maxHealth(a.entity)));
        a.bar.progress(prog);
        Set<UUID> now = new HashSet<>();
        for (Player p : a.entity.getWorld().getPlayers()) {
            if (p.getLocation().distanceSquared(a.entity.getLocation()) <= 48 * 48) now.add(p.getUniqueId());
        }
        for (UUID id : now) {
            if (a.viewers.add(id)) {
                Player p = Bukkit.getPlayer(id);
                if (p != null) p.showBossBar(a.bar);
            }
        }
        for (UUID id : new HashSet<>(a.viewers)) {
            if (!now.contains(id)) {
                a.viewers.remove(id);
                Player p = Bukkit.getPlayer(id);
                if (p != null) p.hideBossBar(a.bar);
            }
        }
    }

    private void hideBar(Active a) {
        if (a.bar == null) return;
        for (UUID id : a.viewers) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) p.hideBossBar(a.bar);
        }
        a.viewers.clear();
    }

    // ------------------------------------------------------------------ 균열

    private void riftTick() {
        if (!plugin.getConfig().getBoolean("mobs.rift-spawning", true)) return;
        for (Map.Entry<UUID, String> en : new HashMap<>(riftMarkers).entrySet()) {
            Entity marker = Bukkit.getEntity(en.getKey());
            if (marker == null || !marker.isValid()) {
                riftMarkers.remove(en.getKey());
                continue;
            }
            MobDef.Rift rift = registry.rifts().get(en.getValue());
            if (rift == null || rift.mobs().isEmpty()) continue;
            Location c = marker.getLocation();
            marker.getWorld().spawnParticle(Particle.REVERSE_PORTAL, c.clone().add(0, 1, 0), 20, 1.5, 1, 1.5, 0.02);
            boolean near = false;
            for (Player p : c.getWorld().getPlayers()) {
                if (p.getGameMode() == GameMode.SPECTATOR) continue;
                if (p.getLocation().distanceSquared(c) < 40 * 40) {
                    near = true;
                    break;
                }
            }
            if (!near) continue;
            long alive = 0;
            for (Active a : active.values()) {
                if (rift.id().equals(a.entity.getPersistentDataContainer().get(Keys.RIFT_MOB, PersistentDataType.STRING))
                        && a.entity.getWorld().equals(c.getWorld())) alive++;
            }
            if (alive >= rift.maxAlive()) continue;
            // interval 초마다 한 마리 꼴로 (riftTick 은 2초 간격)
            if (rnd().nextDouble() > 2.0 / Math.max(2.0, rift.interval())) continue;
            Location spot = findSpot(c, rift.radius());
            if (spot == null) continue;
            String id = rift.mobs().get(rnd().nextInt(rift.mobs().size()));
            LivingEntity le = spawn(id, spot, false);
            if (le != null) {
                le.getPersistentDataContainer().set(Keys.RIFT_MOB, PersistentDataType.STRING, rift.id());
                spot.getWorld().spawnParticle(Particle.PORTAL, spot.clone().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.4);
            }
        }
    }

    private Location findSpot(Location c, double radius) {
        World w = c.getWorld();
        for (int tries = 0; tries < 12; tries++) {
            double a = rnd().nextDouble(Math.PI * 2), d = 2 + rnd().nextDouble() * radius;
            int x = (int) Math.floor(c.getX() + Math.cos(a) * d), z = (int) Math.floor(c.getZ() + Math.sin(a) * d);
            for (int y = c.getBlockY() + 6; y >= c.getBlockY() - 8; y--) {
                Block b = w.getBlockAt(x, y, z);
                if (!b.getType().isSolid()) continue;
                if (b.getRelative(0, 1, 0).isPassable() && b.getRelative(0, 2, 0).isPassable()
                        && !b.getRelative(0, 1, 0).isLiquid()) {
                    Location spot = new Location(w, x + 0.5, y + 1, z + 0.5);
                    boolean tooClose = false;
                    for (Player p : w.getPlayers()) if (p.getLocation().distanceSquared(spot) < 5 * 5) tooClose = true;
                    if (!tooClose) return spot;
                }
                break;
            }
        }
        return null;
    }

    public void scanLoaded() {
        for (World w : Bukkit.getWorlds()) for (Entity e : w.getEntities()) onLoaded(e);
    }

    private void onLoaded(Entity e) {
        if (e instanceof Marker mk) {
            String r = e.getPersistentDataContainer().get(Keys.RIFT, PersistentDataType.STRING);
            if (r != null) riftMarkers.put(e.getUniqueId(), r);
            lairs.seen(mk);
            return;
        }
        // 보스 모델 조각과 둥지 시계는 저장하지 않는다. 주인 없이 남은 것(플러그인 다시 읽기 등)만 지운다
        String rigOwner = e.getPersistentDataContainer().get(Keys.RIG, PersistentDataType.STRING);
        if (rigOwner != null) {
            if (!rigs.isLive(rigOwner)) e.remove();
            return;
        }
        if (e.getPersistentDataContainer().has(Keys.LAIR_TEXT) && !lairs.ownsClock(e.getUniqueId())) {
            e.remove();
            return;
        }
        if (e.getScoreboardTags().contains(Mechanics.FX_TAG)) {
            e.remove();
            return;
        }
        if (e instanceof Mob m && e.getScoreboardTags().contains(HitEffects.STUN_TAG)) {
            m.setAI(true);
            e.removeScoreboardTag(HitEffects.STUN_TAG);
        }
        if (e instanceof LivingEntity le) {
            MobDef def = registry.get(idOf(e));
            if (def != null) {
                Active a = track(def, le);
                if (a.home == null) a.home = le.getLocation();
                if (rigs.has(def.id())) rigs.attach(le, def.id());
            }
        }
    }

    @EventHandler
    public void onEntitiesLoad(EntitiesLoadEvent e) {
        for (Entity en : e.getEntities()) onLoaded(en);
    }

    @EventHandler
    public void onEntitiesUnload(EntitiesUnloadEvent e) {
        for (Entity en : e.getEntities()) {
            riftMarkers.remove(en.getUniqueId());
            Active a = active.remove(en.getUniqueId());
            if (a != null) hideBar(a);
            rigs.detach(en.getUniqueId());
        }
    }

    public Location riftCenter(String riftId, World w) {
        for (Map.Entry<UUID, String> en : riftMarkers.entrySet()) {
            if (!en.getValue().equals(riftId)) continue;
            Entity m = Bukkit.getEntity(en.getKey());
            if (m != null && (w == null || m.getWorld().equals(w))) return m.getLocation();
        }
        return null;
    }

    // ------------------------------------------------------------------ 이벤트

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onNaturalSpawn(CreatureSpawnEvent e) {
        if (e.getSpawnReason() != CreatureSpawnEvent.SpawnReason.NATURAL) return;
        if (!plugin.getConfig().getBoolean("mobs.natural-replace", true)) return;
        LivingEntity le = e.getEntity();
        String world = le.getWorld().getName();
        List<MobDef> defs = new ArrayList<>(registry.all().values());
        Collections.shuffle(defs);
        for (MobDef def : defs) {
            MobDef.Natural n = def.natural();
            if (n == null || !n.replace().contains(le.getType())) continue;
            if (!n.worlds().isEmpty() && !n.worlds().contains(world)) continue;
            if (rnd().nextDouble() >= n.chance()) continue;
            e.setCancelled(true);
            Location at = le.getLocation();
            Bukkit.getScheduler().runTask(plugin, () -> spawn(def.id(), at, false));
            return;
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamage(EntityDamageByEntityEvent e) {
        // 몬스터가 때릴 때
        Entity d = e.getDamager();
        if (d instanceof Projectile pr && pr.getShooter() instanceof Entity s) d = s;
        Active atk = active.get(d.getUniqueId());
        if (atk != null) rigs.swing(atk.entity.getUniqueId());
        if (atk != null && e.getEntity() instanceof LivingEntity victim && !Combat.inSkill()) {
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (atk.entity.isValid()) trigger(atk, "on_hit", victim);
            });
        }
        // 몬스터가 맞을 때
        Active vic = active.get(e.getEntity().getUniqueId());
        if (vic != null) {
            rigs.hurt(vic.entity.getUniqueId());
            Player p = d instanceof Player pl ? pl : null;
            if (p != null) {
                vic.contributors.merge(p.getUniqueId(), e.getFinalDamage(), Double::sum);
                vic.lastHurtByPlayer = System.currentTimeMillis();
            }
            LivingEntity src = d instanceof LivingEntity l ? l : null;
            if (src != null && !Combat.inSkill()) {
                Bukkit.getScheduler().runTask(plugin, () -> {
                    if (vic.entity.isValid()) trigger(vic, "on_hurt", src);
                });
            }
        }
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onDeath(EntityDeathEvent e) {
        LivingEntity dead = e.getEntity();
        Active a = active.remove(dead.getUniqueId());
        MobDef def = a != null ? a.def : registry.get(idOf(dead));
        if (def == null) return;
        if (a != null) {
            hideBar(a);
            trigger(a, "on_death", dead.getKiller());
        }
        if (!def.vanillaDrops()) e.getDrops().clear();
        e.setDroppedExp(dead.getKiller() != null ? def.xp() : 0);
        if (dead.getScoreboardTags().contains("augsky_minion")) {
            e.getDrops().clear();
            e.setDroppedExp(def.xp() / 4);
            return;
        }
        rigs.shatter(dead.getUniqueId());
        if (def.boss()) {
            bossLoot(def, a, dead);
            lairs.onBossDeath(dead);
            e.getDrops().clear();
            return;
        }
        Player killer = dead.getKiller();
        Location dropAt = dead.getLocation();
        // 공허 위에서 죽으면 아이템이 떨어지지 않게 처치한 사람 발밑에 떨군다
        if (killer != null && overVoid(dropAt)) {
            dropAt = killer.getLocation();
            List<ItemStack> moved = new ArrayList<>(e.getDrops());
            e.getDrops().clear();
            for (ItemStack it : moved) killer.getWorld().dropItem(dropAt, it);
        }
        for (MobDef.Drop dr : def.drops()) {
            if (rnd().nextDouble() >= dr.chance()) continue;
            int amt = dr.min() + (dr.max() > dr.min() ? rnd().nextInt(dr.max() - dr.min() + 1) : 0);
            ItemStack it = plugin.items().spec(dr.item(), amt);
            if (it == null) continue;
            if (killer != null && overVoid(dead.getLocation())) killer.getWorld().dropItem(killer.getLocation(), it);
            else e.getDrops().add(it);
        }
    }

    private static boolean overVoid(Location l) {
        World w = l.getWorld();
        for (int y = l.getBlockY(); y > l.getBlockY() - 12 && y > w.getMinHeight(); y--) {
            if (w.getBlockAt(l.getBlockX(), y, l.getBlockZ()).getType().isSolid()) return false;
        }
        return true;
    }

    /** 보스 보상은 기여한 모든 플레이어에게 각자 굴려서 준다 (협동용). */
    private void bossLoot(MobDef def, Active a, LivingEntity dead) {
        Bukkit.broadcast(Text.mm("<#ffcc55>✦ " + def.name() + "<gray>이(가) 쓰러졌습니다!"));
        dead.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, dead.getLocation().add(0, 1, 0), 120, 1, 1.5, 1, 0.5);
        Fx.sound(dead.getLocation(), "ui.toast.challenge_complete", 1.5f, 1f);
        Set<UUID> who = new HashSet<>();
        if (a != null) {
            double total = a.contributors.values().stream().mapToDouble(Double::doubleValue).sum();
            for (Map.Entry<UUID, Double> en : a.contributors.entrySet()) {
                if (total <= 0 || en.getValue() / total >= 0.03) who.add(en.getKey());
            }
        }
        if (dead.getKiller() != null) who.add(dead.getKiller().getUniqueId());
        for (UUID id : who) {
            Player p = Bukkit.getPlayer(id);
            if (p == null) continue;
            List<String> got = new ArrayList<>();
            for (MobDef.Drop dr : def.drops()) {
                if (rnd().nextDouble() >= dr.chance()) continue;
                int amt = dr.min() + (dr.max() > dr.min() ? rnd().nextInt(dr.max() - dr.min() + 1) : 0);
                ItemStack it = plugin.items().spec(dr.item(), amt);
                if (it == null) continue;
                Items.give(p, it);
                got.add(it.hasItemMeta() && it.getItemMeta().hasDisplayName()
                        ? net.kyori.adventure.text.minimessage.MiniMessage.miniMessage().serialize(it.getItemMeta().displayName())
                        + (it.getAmount() > 1 ? " <gray>×" + it.getAmount() : "")
                        : "<white>" + it.getType().name().toLowerCase() + " <gray>×" + it.getAmount());
            }
            p.giveExp(def.xp());
            p.sendMessage(Text.mm("<#ffcc55>✦ 보상: " + (got.isEmpty() ? "<gray>없음" : String.join("<gray>, ", got))));
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent e) {
        if (idOf(e.getEntity()) != null) e.blockList().clear();
    }

    @EventHandler(ignoreCancelled = true)
    public void onChangeBlock(EntityChangeBlockEvent e) {
        if (idOf(e.getEntity()) != null) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent e) {
        Entity src = e.getIgnitingEntity();
        if (src instanceof Projectile pr && pr.getShooter() instanceof Entity s) src = s;
        if (src != null && idOf(src) != null) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onCombust(EntityCombustEvent e) {
        // 햇빛에 타지 않게 설정한 몬스터가 다른 경로로 불붙는 경우는 그대로 둔다
        if (e.getClass() != EntityCombustEvent.class) return;
        MobDef def = registry.get(idOf(e.getEntity()));
        if (def != null && !def.burnInDay() && e.getEntity().getFireTicks() <= 0
                && e.getEntity().getWorld().isDayTime() && e.getEntity().getLocation().getBlock().getLightFromSky() > 10) {
            e.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onSplit(SlimeSplitEvent e) {
        if (idOf(e.getEntity()) != null) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onTransform(EntityTransformEvent e) {
        if (idOf(e.getEntity()) != null) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onEnvDamage(EntityDamageEvent e) {
        // 보스가 공허로 떨어지면 피해 대신 원래 자리로 돌아간다
        if (e.getCause() != EntityDamageEvent.DamageCause.VOID) return;
        Active a = active.get(e.getEntity().getUniqueId());
        if (a != null && a.def.boss() && a.home != null) {
            e.setCancelled(true);
            e.getEntity().teleport(a.home);
        }
    }

    public void removeBars() {
        for (Active a : active.values()) hideBar(a);
        rigs.removeAll();
        lairs.removeClocks();
    }

    public int activeCount() {
        return active.size();
    }
}
