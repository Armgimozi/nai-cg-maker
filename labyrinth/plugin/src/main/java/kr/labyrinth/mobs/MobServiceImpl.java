package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import kr.labyrinth.event.MobKillEvent;
import net.kyori.adventure.util.TriState;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Ageable;
import org.bukkit.entity.Bat;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Panda;
import org.bukkit.entity.Player;
import org.bukkit.entity.Slime;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityPortalEvent;
import org.bukkit.event.entity.EntityTargetEvent;
import org.bukkit.event.entity.EntityTransformEvent;
import org.bukkit.event.entity.SlimeSplitEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.scheduler.BukkitTask;

/**
 * {@link MobService} 실제 구현: 스폰(투명·무음 베이스 + 모델 리그 + HP 풀), 틱(하나의 반복 작업), AI·스킬, 사망 보상
 * (경험치·골드 = LevelService/PlayerData, 아이템 = LootService), {@link MobKillEvent}, 재시작 청소(PDC 태그 + EntityJanitor).
 */
public final class MobServiceImpl implements MobService, Listener {

    /** 눈 레이어가 투명화를 무시하고 보이는 바닐라 몹 → 같은 체형의 다른 히트박스로 대체 (type, scale 배율). */
    private record BaseSub(EntityType type, double scale) {}

    private static final Map<String, BaseSub> SUBSTITUTES = Map.of(
            "SPIDER", new BaseSub(EntityType.PANDA, 1.0),
            "CAVE_SPIDER", new BaseSub(EntityType.PANDA, 0.55),
            "ENDERMAN", new BaseSub(EntityType.HUSK, 1.3),
            "PHANTOM", new BaseSub(EntityType.BAT, 1.4),
            "VEX", new BaseSub(EntityType.BAT, 0.9),
            "SLIME", new BaseSub(EntityType.SLIME, 2.0));

    private final Services services;
    private final MobFx fx;
    private final Map<UUID, LabMob> byUuid = new HashMap<>();
    private final Map<UUID, LabMob> mobs = new LinkedHashMap<>();
    private BukkitTask task;
    private long tick;

    public MobServiceImpl(Services services) {
        this.services = services;
        this.fx = new MobFx(services);
    }

    void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 1L, 1L);
    }

    void stop() {
        if (task != null) task.cancel();
        task = null;
        for (LabMob m : new ArrayList<>(mobs.values())) m.remove();
        mobs.clear();
        byUuid.clear();
        fx.shutdown();
        HandlerList.unregisterAll(this);
    }

    MobFx fx() { return fx; }

    long now() { return tick; }

    // ── MobService ───────────────────────────────────────────────────────

    @Override
    public CustomMob spawn(String mobId, Location loc, InstanceContext ctx) {
        MobDef def = services.content().mob(mobId);
        boolean elite = false;
        if (def != null && "normal".equals(def.rank()) && ctx != null && !"adhoc".equals(ctx.id())) {
            double chance = services.plugin().getConfig().getDouble("mobs.elite_variant_chance", 0.06);
            elite = ThreadLocalRandom.current().nextDouble() < chance;
        }
        return spawn(mobId, loc, ctx, elite);
    }

    @Override
    public CustomMob spawn(String mobId, Location loc, InstanceContext ctx, boolean eliteVariant) {
        MobDef def = services.content().mob(mobId);
        if (def == null || loc == null || loc.getWorld() == null) {
            Log.warn("[몹] 스폰 실패: 정의 없음 또는 위치 오류 (" + mobId + ")");
            return null;
        }
        try {
            return doSpawn(def, loc, ctx, eliteVariant);
        } catch (Throwable t) {
            Log.error("[몹] 스폰 오류 (" + mobId + ")", t);
            return null;
        }
    }

    @Override
    public CustomMob spawnDef(MobDef def, Location loc, InstanceContext ctx) {
        if (def == null || loc == null || loc.getWorld() == null) {
            Log.warn("[몹] 스폰 실패: 정의 없음 또는 위치 오류 (" + (def == null ? "null" : def.id()) + ")");
            return null;
        }
        try {
            return doSpawn(def, loc, ctx, false);
        } catch (Throwable t) {
            Log.error("[몹] 스폰 오류 (" + def.id() + ")", t);
            return null;
        }
    }

    private LabMob doSpawn(MobDef def, Location loc, InstanceContext ctxIn, boolean eliteVariant) {
        InstanceContext ctx = ctxIn != null ? ctxIn
                : InstanceContext.adhoc(Math.max(1, def.floor()), 1, services.settings().difficulty(), services.settings().party());
        boolean elite = eliteVariant && !def.isElite();
        MobStats stats = MobStats.compute(def.hp(), def.damage(), def.defense(), def.xp(), def.scale(),
                ctx.hpMultiplier(), ctx.damageMultiplier(), elite);

        String baseName = def.base() == null ? "HUSK" : def.base().toUpperCase(Locale.ROOT);
        BaseSub sub = SUBSTITUTES.get(baseName);
        EntityType type;
        double hitScale = 1.0;
        if (sub != null) {
            type = sub.type();
            hitScale = sub.scale();
        } else {
            try {
                type = EntityType.valueOf(baseName);
            } catch (IllegalArgumentException e) {
                type = EntityType.HUSK;
            }
        }
        Class<? extends Entity> cls = type.getEntityClass();
        if (cls == null || !Mob.class.isAssignableFrom(cls)) cls = org.bukkit.entity.Husk.class;
        @SuppressWarnings("unchecked")
        Class<? extends Mob> mobCls = (Class<? extends Mob>) cls;
        final double attrScale = Math.max(0.0625, Math.min(16, stats.scale() * hitScale));
        final boolean flying = def.flying() || type == EntityType.BAT || type == EntityType.BLAZE || type == EntityType.ALLAY;
        final boolean turret = "turret".equals(def.ai());
        Location at = loc.clone();
        Mob e = loc.getWorld().spawn(at, mobCls, false, ent -> {
            ent.setPersistent(false);
            ent.setRemoveWhenFarAway(false);
            ent.setInvisible(true);
            ent.setSilent(true);
            ent.setCanPickupItems(false);
            ent.setCustomNameVisible(false);
            ent.setDespawnInPeacefulOverride(TriState.FALSE);
            if (ent.getEquipment() != null) ent.getEquipment().clear();
            if (ent instanceof Ageable a) a.setAdult();
            if (ent instanceof Slime s) s.setSize(1);
            if (ent instanceof Bat b) b.setAwake(true); // 매달려 쉬는 박쥐는 움직이지 않는다
            if (ent instanceof Panda p) {
                p.setMainGene(Panda.Gene.NORMAL);
                p.setHiddenGene(Panda.Gene.NORMAL);
            }
            attr(ent, Attribute.MAX_HEALTH, 100);
            ent.setHealth(100);
            attr(ent, Attribute.MOVEMENT_SPEED, Math.max(0.01, def.speed()));
            attr(ent, Attribute.FLYING_SPEED, Math.max(0.01, def.speed()));
            attr(ent, Attribute.SCALE, attrScale);
            attr(ent, Attribute.FOLLOW_RANGE, 48);
            attr(ent, Attribute.KNOCKBACK_RESISTANCE, def.isElite() || elite ? 0.6 : 0.3);
            attr(ent, Attribute.ATTACK_DAMAGE, 0);
            if (flying) ent.setGravity(false);
            if (flying || turret) ent.setAware(false);
            Keys.tagTransient(ent, Keys.MOB, def.id());
            if (!"adhoc".equals(ctx.id())) ent.getPersistentDataContainer().set(Keys.INSTANCE, PersistentDataType.STRING, ctx.id());
        });
        Bukkit.getMobGoals().removeAllGoals(e);

        List<MobDef.MobSkillDef> skills = new ArrayList<>(def.skills());
        if (elite) {
            MobDef.MobSkillDef extra = EliteVariants.pick(def, e.getUniqueId().getMostSignificantBits());
            if (extra != null) skills.add(extra);
        }
        double yawOffset = services.plugin().getConfig().getDouble("mobs.model_yaw_offset", 0.0);
        ModelRig rig = new ModelRig(def.id(), def.model(), stats.scale(), yawOffset);
        rig.spawn(e.getLocation(), e.getHeight(), "mob:" + def.id());
        LabMob mob = new LabMob(services, this, def, stats, ctx, elite, List.copyOf(skills), e, rig, flying);
        if (elite || def.isElite()) rig.setGlow(elite ? Color.fromRGB(255, 196, 64) : Color.fromRGB(255, 150, 40));
        register(mob);
        MobSkills.initCooldowns(mob, tick);
        MobSkills.onSpawn(mob);
        mob.refreshNameplate();
        rig.animate(mob.bodyYaw, mob.animState(tick), 1);
        if (!mob.ambushing) {
            MobFx.particle(org.bukkit.Particle.POOF, e.getLocation().add(0, e.getHeight() / 2, 0), 8, 0.3, 0.3, 0.3, 0.02);
            if (elite || def.isElite()) MobFx.dust(e.getLocation().add(0, e.getHeight(), 0), Color.fromRGB(255, 196, 64), 1.5f, 12, 0.5);
        }
        return mob;
    }

    private static void attr(LivingEntity e, Attribute a, double v) {
        AttributeInstance inst = e.getAttribute(a);
        if (inst != null) inst.setBaseValue(v);
    }

    @Override
    public Optional<CustomMob> byEntity(Entity entity) {
        if (entity == null) return Optional.empty();
        LabMob m = byUuid.get(entity.getUniqueId());
        return m == null || m.isDead() ? Optional.empty() : Optional.of(m);
    }

    Optional<LabMob> byUuid(UUID id) {
        return Optional.ofNullable(byUuid.get(id));
    }

    @Override
    public Collection<CustomMob> alive(String instanceId) {
        List<CustomMob> out = new ArrayList<>();
        for (LabMob m : mobs.values()) {
            if (!m.isAlive()) continue;
            if (instanceId == null || (m.ctx != null && instanceId.equals(m.ctx.id()))) out.add(m);
        }
        return out;
    }

    @Override
    public void removeAll(String instanceId) {
        for (LabMob m : new ArrayList<>(mobs.values())) {
            if (instanceId == null || (m.ctx != null && instanceId.equals(m.ctx.id()))) m.remove();
        }
    }

    // ── 내부 ─────────────────────────────────────────────────────────────

    private void register(LabMob m) {
        mobs.put(m.entity.getUniqueId(), m);
        byUuid.put(m.entity.getUniqueId(), m);
        for (UUID u : m.rig.entityIds()) byUuid.put(u, m);
    }

    void unregister(LabMob m) {
        mobs.remove(m.entity.getUniqueId());
        byUuid.values().removeIf(x -> x == m);
    }

    private void tickAll() {
        tick++;
        for (LabMob m : new ArrayList<>(mobs.values())) {
            try {
                m.tick(tick);
            } catch (Throwable t) {
                Log.error("[몹] 틱 오류 (" + m.id() + ")", t);
            }
        }
        if (tick % 100 == 0) fx.sweep();
    }

    /** 0 = 아주 가까움(≤20), 1 = 가까움(≤32), 2 = 멀음(≤56), 3 = 아무도 없음. */
    int lod(Location loc) {
        double best = Double.MAX_VALUE;
        for (Player p : loc.getWorld().getPlayers()) {
            if (p.getGameMode() == GameMode.SPECTATOR && !p.isOp()) continue;
            best = Math.min(best, p.getLocation().distanceSquared(loc));
        }
        if (best <= 20 * 20) return 0;
        if (best <= 32 * 32) return 1;
        if (best <= 56 * 56) return 2;
        return 3;
    }

    /** player 를 노리는 몹 수 (exclude 제외) — 떼 AI 분산용. */
    int targetCount(UUID player, LabMob exclude) {
        int n = 0;
        for (LabMob m : mobs.values()) if (m != exclude && m.isAlive() && player.equals(m.targetId)) n++;
        return n;
    }

    List<LabMob> mobsNear(Location c, double r) {
        List<LabMob> out = new ArrayList<>();
        for (LabMob m : mobs.values()) {
            if (!m.isAlive() || m.location().getWorld() != c.getWorld()) continue;
            if (m.location().distanceSquared(c) <= r * r) out.add(m);
        }
        return out;
    }

    /** 사망 보상: 경험치·골드(각자), 개인 루팅, MobKillEvent. 모두 몹의 보상 배율(rewardMult)을 곱한다. */
    void reward(LabMob m, Player killer, Location at) {
        InstanceContext ctx = m.ctx;
        List<Player> participants = new ArrayList<>();
        if (ctx != null && !"adhoc".equals(ctx.id())) {
            participants.addAll(ctx.onlineMembers());
        } else {
            for (UUID u : m.threat.snapshot().keySet()) {
                Player p = Bukkit.getPlayer(u);
                if (p != null && p.getWorld() == at.getWorld() && p.getLocation().distanceSquared(at) <= 64 * 64) participants.add(p);
            }
        }
        if (killer != null && !participants.contains(killer) && killer.getWorld() == at.getWorld()) participants.add(killer);
        participants.removeIf(p -> !p.isOnline());

        // 솔로·2인 전투방은 몹 수를 줄인 만큼 한 마리당 보상을 올린다 (웨이브별 원래 수 ÷ 실제 수, 기본 1)
        double rewardMult = m.rewardMult;
        double xpMult = (ctx != null ? ctx.xpMultiplier() : 1.0) * rewardMult;
        double goldMult = (ctx != null ? ctx.goldMultiplier() : 1.0) * rewardMult;
        for (Player p : participants) {
            try {
                long xp = services.levels().reward(p, m.stats.xp() * xpMult);
                long gold = 0;
                if (m.def.gold() != null && m.def.gold().max() > 0) {
                    double g = m.def.gold().roll(ThreadLocalRandom.current()) * m.stats.goldMultiplier() * goldMult
                            * (1.0 + services.stats().get(p).goldBonus());
                    gold = Math.max(0, Math.round(g));
                    if (gold > 0) services.data().get(p).addGold(gold);
                }
                if (xp > 0 || gold > 0) {
                    services.hud().actionBar(p, Text.mm("<gray>" + Text.strip(m.def.name()) + " 처치</gray>  <green>+" + Text.num(xp)
                            + " XP</green>" + (gold > 0 ? "  <gold>+" + Text.num(gold) + " G</gold>" : "")), 40);
                    services.hud().refresh(p);
                }
            } catch (Throwable t) {
                Log.error("[몹] 보상 지급 오류", t);
            }
        }
        if (m.def.drops() != null && !m.def.drops().isBlank() && !participants.isEmpty()) {
            String source = m.def.isElite() || m.eliteVariant ? "elite" : "drop";
            try {
                services.loot().drop(m.def.drops(), participants, at, ctx, source, rewardMult);
                if (m.eliteVariant) services.loot().drop(m.def.drops(), participants, at, ctx, source, rewardMult);
            } catch (Throwable t) {
                Log.error("[몹] 루팅 오류 (" + m.def.drops() + ")", t);
            }
        }
        try {
            Bukkit.getPluginManager().callEvent(new MobKillEvent(m, killer, participants, false));
        } catch (Throwable t) {
            Log.error("[몹] MobKillEvent 처리 오류", t);
        }
    }

    /** 근처 몹 제거 (관리자). @return 제거 수 */
    int removeNear(Location c, double r) {
        int n = 0;
        for (LabMob m : new ArrayList<>(mobs.values())) {
            if (m.location().getWorld() == c.getWorld() && m.location().distanceSquared(c) <= r * r) {
                m.remove();
                n++;
            }
        }
        return n;
    }

    int count() { return mobs.size(); }

    // ── 바닐라 동작 차단 (베이스 엔티티) ─────────────────────────────────

    private boolean isBase(Entity e) {
        LabMob m = byUuid.get(e.getUniqueId());
        return m != null && m.entity.getUniqueId().equals(e.getUniqueId());
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onTransform(EntityTransformEvent e) {
        if (isBase(e.getEntity())) e.setCancelled(true); // 허스크 → 좀비 변환 등
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCombust(EntityCombustEvent e) {
        if (isBase(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onTarget(EntityTargetEvent e) {
        if (isBase(e.getEntity())) e.setCancelled(true); // 대상은 위협 표가 정한다
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onChangeBlock(EntityChangeBlockEvent e) {
        if (isBase(e.getEntity())) e.setCancelled(true); // 블록은 절대 바꾸지 않는다
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onSplit(SlimeSplitEvent e) {
        if (isBase(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onPortal(EntityPortalEvent e) {
        if (isBase(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteract(PlayerInteractEntityEvent e) {
        if (isBase(e.getRightClicked())) e.setCancelled(true); // 판다·늑대 먹이 주기 등 방지
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(EntityDeathEvent e) {
        // 정상 경로는 remove() — 여기 오는 건 공허·/kill 같은 예외. 바닐라 드롭 제거 후 조용히 정리.
        LabMob m = byUuid.get(e.getEntity().getUniqueId());
        if (m == null || !m.entity.getUniqueId().equals(e.getEntity().getUniqueId())) return;
        e.getDrops().clear();
        e.setDroppedExp(0);
        Bukkit.getScheduler().runTask(services.plugin(), m::remove);
    }

    /** 다른 월드가 내려갈 때 등 — 유효하지 않은 몹 정리 (reload 시). */
    void purgeInvalid() {
        for (LabMob m : new ArrayList<>(mobs.values())) if (!m.entity.isValid() && !m.isDead()) m.remove();
    }
}
