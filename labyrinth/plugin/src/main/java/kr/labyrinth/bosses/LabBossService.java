package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.bosses.impl.Floor01Boss;
import kr.labyrinth.bosses.impl.Floor02Boss;
import kr.labyrinth.bosses.impl.Floor03Boss;
import kr.labyrinth.bosses.impl.Floor04Boss;
import kr.labyrinth.bosses.impl.Floor05Boss;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerToggleSneakEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * BossService 구현: 층 → 보스 구현 등록부, 매 틱 한 번 모든 보스 진행, 엔티티 → 핸들 조회(히트박스·리그·기믹 오브젝트),
 * 웅크리기·바닐라 피해(용암) 이벤트를 해당 아레나의 보스에 전달.
 * <p>
 * <b>새 층 보스 추가</b>(floors 6~10 담당): {@code impl/FloorNNBoss extends Boss} 를 만들고 생성자 {@code (Boss.Init)} 를 두고,
 * 아래 {@link #registerDefaults()} 에 {@code register(NN, FloorNNBoss::new)} 한 줄을 넣으면 된다.
 */
public final class LabBossService implements BossService, Listener {

    /** 보스 구현 생성기. */
    @FunctionalInterface
    public interface BossFactory {
        Boss create(Boss.Init init);
    }

    private final Services services;
    private final Map<Integer, BossFactory> factories = new TreeMap<>();
    private final Map<UUID, Boss> bosses = new LinkedHashMap<>();
    private final Map<UUID, BossHandle> byEntity = new HashMap<>();
    private BukkitTask task;
    private long tick;

    public LabBossService(Services services) {
        this.services = services;
        registerDefaults();
    }

    private void registerDefaults() {
        register(1, Floor01Boss::new);
        register(2, Floor02Boss::new);
        register(3, Floor03Boss::new);
        register(4, Floor04Boss::new);
        register(5, Floor05Boss::new);
    }

    public void register(int floor, BossFactory factory) { factories.put(floor, factory); }

    public Collection<Integer> implementedFloors() { return factories.keySet(); }

    void start() {
        services.plugin().getServer().getPluginManager().registerEvents(this, services.plugin());
        task = services.plugin().getServer().getScheduler().runTaskTimer(services.plugin(), this::tickAll, 1L, 1L);
    }

    void stop() {
        if (task != null) task.cancel();
        task = null;
        HandlerList.unregisterAll(this);
        for (Boss b : new ArrayList<>(bosses.values())) {
            try {
                b.end();
            } catch (Throwable t) {
                Log.error("보스 종료 오류", t);
            }
        }
        bosses.clear();
        byEntity.clear();
    }

    long now() { return tick; }

    private void tickAll() {
        tick++;
        for (Boss b : new ArrayList<>(bosses.values())) {
            try {
                b.tick(tick);
            } catch (Throwable t) {
                Log.error("보스 틱 오류 (" + b.id() + ")", t);
            }
        }
        if (tick % 20 == 0) {
            for (Boss b : bosses.values()) for (UUID u : b.entityIds()) byEntity.putIfAbsent(u, b);
        }
    }

    // ── BossService ──────────────────────────────────────────────────────

    @Override
    public BossHandle spawnBoss(int floor, Location arenaCenter, InstanceContext ctx) {
        return spawn(floor, arenaCenter, ctx, false);
    }

    /** adhoc = 관리자 소환 (블록 설치 없이 디스플레이로 대체, 보상은 위협 표 기준). */
    public Boss spawn(int floor, Location center, InstanceContext ctx, boolean adhoc) {
        if (center == null || center.getWorld() == null) return null;
        BossFactory f = factories.get(floor);
        BossDef def = bossDef(floor);
        if (f == null || def == null) {
            Log.warn("지하 " + floor + "층 보스 구현 또는 bosses.yml 정의가 없습니다" + (f == null ? " (구현 없음)" : " (정의 없음)"));
            return null;
        }
        InstanceContext c = ctx != null ? ctx
                : InstanceContext.adhoc(floor, 1, services.settings().difficulty(), services.settings().party());
        boolean isAdhoc = adhoc || ctx == null || "adhoc".equals(c.id());
        Boss b;
        try {
            b = f.create(new Boss.Init(services, this, def, center, c, isAdhoc));
        } catch (Throwable t) {
            Log.error("보스 생성 실패 (지하 " + floor + "층)", t);
            return null;
        }
        bosses.put(b.entity().getUniqueId(), b);
        for (UUID u : b.entityIds()) byEntity.put(u, b);
        try {
            b.start();
        } catch (Throwable t) {
            Log.error("보스 시작 오류 (지하 " + floor + "층)", t);
        }
        return b;
    }

    /** floors.yml 의 boss → bosses.yml, 없으면 floor 값이 같은 보스. */
    public BossDef bossDef(int floor) {
        BossDef byFloor = services.content().bossOfFloor(floor);
        if (byFloor != null) return byFloor;
        for (BossDef d : services.content().bosses().values()) if (d.floor() == floor) return d;
        return null;
    }

    @Override
    public Optional<BossHandle> byEntity(Entity entity) {
        if (entity == null) return Optional.empty();
        BossHandle h = byEntity.get(entity.getUniqueId());
        if (h == null) return Optional.empty();
        if (h instanceof Boss b && !b.isAlive()) return Optional.empty();
        if (h instanceof ObjectTarget o && !o.isAlive()) return Optional.empty();
        return Optional.of(h);
    }

    @Override
    public Collection<BossHandle> active() {
        List<BossHandle> out = new ArrayList<>();
        for (Boss b : bosses.values()) if (b.isAlive()) out.add(b);
        return out;
    }

    @Override
    public void endAll(String instanceId) {
        for (Boss b : new ArrayList<>(bosses.values())) {
            InstanceContext c = b.instance();
            if (instanceId == null || (c != null && instanceId.equals(c.id()))) b.end();
        }
    }

    void unregister(Boss b) {
        bosses.remove(b.entity().getUniqueId());
        byEntity.values().removeIf(h -> h == b || (h instanceof ObjectTarget o && o.owner() == b));
    }

    void registerObject(ObjectTarget o) { byEntity.put(o.entity().getUniqueId(), o); }

    void unregisterObject(ObjectTarget o) { byEntity.remove(o.entity().getUniqueId()); }

    /** 이 위치를 아레나로 가진 살아 있는 보스. */
    public Boss bossAt(Location l) {
        for (Boss b : bosses.values()) {
            if (!b.isAlive() || l.getWorld() != b.center().getWorld()) continue;
            Location c = b.center();
            if (Math.hypot(l.getX() - c.getX(), l.getZ() - c.getZ()) <= b.arenaRadius() + 4 && Math.abs(l.getY() - c.getY()) < 20) return b;
        }
        return null;
    }

    public List<Boss> bosses() { return new ArrayList<>(bosses.values()); }

    // ── 이벤트 ───────────────────────────────────────────────────────────

    @EventHandler(ignoreCancelled = true)
    public void onSneak(PlayerToggleSneakEvent e) {
        if (!e.isSneaking() || bosses.isEmpty()) return;
        Boss b = bossAt(e.getPlayer().getLocation());
        if (b == null) return;
        try {
            b.onSneak(e.getPlayer());
        } catch (Throwable t) {
            Log.error("보스 웅크리기 처리 오류", t);
        }
    }

    /** 아레나 안 플레이어의 바닐라 피해 (용암 해자 등) — CombatListener(HIGH) 보다 먼저. */
    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onVanillaDamage(EntityDamageEvent e) {
        if (bosses.isEmpty() || !(e.getEntity() instanceof Player p)) return;
        if (e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK || e.getCause() == EntityDamageEvent.DamageCause.PROJECTILE) return;
        Boss b = bossAt(p.getLocation());
        if (b == null) return;
        try {
            b.onPlayerVanillaDamage(p, e);
        } catch (Throwable t) {
            Log.error("보스 바닐라 피해 처리 오류", t);
        }
    }
}
