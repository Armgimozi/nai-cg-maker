package kr.augsky.mob;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.skill.Combat;
import kr.augsky.skill.Targets;
import kr.augsky.util.Fx;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Marker;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.persistence.PersistentDataType;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 보스 둥지. 보스는 소환하지 않고 처음부터 둥지를 지킨다.
 * 쓰러지면 정해진 시간 뒤 다시 깨어나고, 둥지에서 멀어지면 돌아가며, 아무도 없으면 체력을 회복한다.
 * 둥지 기록(어느 보스, 언제 다시 깨어나는지)은 월드 폴더의 augsky-lairs.yml 에 남는다.
 * 둥지 보스는 디스크에 저장하지 않는다(청크가 내려가면 사라지고, 누군가 다가오면 다시 나타난다).
 */
public final class Lairs {
    public static final String FILE = "augsky-lairs.yml";

    public static final class Lair {
        final UUID id;
        final String boss;
        final String world;
        final double x, y, z;
        long respawnAt;
        int kills;

        Lair(UUID id, String boss, String world, double x, double y, double z) {
            this.id = id;
            this.boss = boss;
            this.world = world;
            this.x = x;
            this.y = y;
            this.z = z;
        }

        public Location location() {
            World w = Bukkit.getWorld(world);
            return w == null ? null : new Location(w, x, y, z);
        }

        public String boss() {
            return boss;
        }

        public long respawnAt() {
            return respawnAt;
        }
    }

    private final AugSky plugin;
    private final MobManager mobs;
    private final Map<String, Map<UUID, Lair>> registry = new HashMap<>();
    /** 둥지 id → 지금 둥지를 지키는 보스 */
    private final Map<UUID, UUID> guardian = new HashMap<>();
    private final Map<UUID, UUID> clock = new HashMap<>();
    private final Map<UUID, Integer> idle = new HashMap<>();

    Lairs(AugSky plugin, MobManager mobs) {
        this.plugin = plugin;
        this.mobs = mobs;
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 40, 20);
    }

    // ------------------------------------------------------------------ 설정

    private int respawnMinutes() {
        return Math.max(0, plugin.getConfig().getInt("bosses.respawn-minutes", 30));
    }

    private double leash() {
        return plugin.getConfig().getDouble("bosses.leash", 22);
    }

    public double arena() {
        return plugin.getConfig().getDouble("bosses.arena-radius", 17);
    }

    // ------------------------------------------------------------------ 기록

    private Map<UUID, Lair> reg(World w) {
        return registry.computeIfAbsent(w.getName(), k -> load(w));
    }

    private Map<UUID, Lair> load(World w) {
        Map<UUID, Lair> m = new LinkedHashMap<>();
        File f = new File(w.getWorldFolder(), FILE);
        if (!f.exists()) return m;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        ConfigurationSection sec = y.getConfigurationSection("lairs");
        if (sec == null) return m;
        for (String k : sec.getKeys(false)) {
            ConfigurationSection a = sec.getConfigurationSection(k);
            if (a == null || a.getString("boss") == null) continue;
            try {
                UUID id = UUID.fromString(k);
                Lair l = new Lair(id, a.getString("boss"), w.getName(), a.getDouble("x"), a.getDouble("y"), a.getDouble("z"));
                l.respawnAt = a.getLong("respawn-at");
                l.kills = a.getInt("kills");
                m.put(id, l);
            } catch (IllegalArgumentException ignored) {
            }
        }
        return m;
    }

    private void save(World w) {
        YamlConfiguration y = new YamlConfiguration();
        for (Lair l : reg(w).values()) {
            String p = "lairs." + l.id;
            y.set(p + ".boss", l.boss);
            y.set(p + ".x", l.x);
            y.set(p + ".y", l.y);
            y.set(p + ".z", l.z);
            y.set(p + ".respawn-at", l.respawnAt);
            y.set(p + ".kills", l.kills);
        }
        try {
            y.save(new File(w.getWorldFolder(), FILE));
        } catch (IOException e) {
            plugin.getLogger().warning("둥지 기록 저장 실패: " + e.getMessage());
        }
    }

    /** 맵을 지을 때 둥지 마커를 만든다. */
    public Marker create(Location at, String bossId) {
        Marker mk = at.getWorld().spawn(at, Marker.class, m -> {
            m.getPersistentDataContainer().set(Keys.LAIR, PersistentDataType.STRING, bossId);
            m.getPersistentDataContainer().set(Keys.MAP_PART, PersistentDataType.BYTE, (byte) 1);
        });
        reg(at.getWorld()).put(mk.getUniqueId(), new Lair(mk.getUniqueId(), bossId, at.getWorld().getName(), at.getX(), at.getY(), at.getZ()));
        save(at.getWorld());
        return mk;
    }

    public void clearRegistry(World w) {
        for (UUID id : new ArrayList<>(reg(w).keySet())) {
            UUID b = guardian.remove(id);
            if (b != null) {
                Entity e = Bukkit.getEntity(b);
                if (e != null) e.remove();
            }
            UUID c = clock.remove(id);
            if (c != null) {
                Entity e = Bukkit.getEntity(c);
                if (e != null) e.remove();
            }
        }
        reg(w).clear();
        save(w);
    }

    public List<Lair> all(World w) {
        return new ArrayList<>(reg(w).values());
    }

    public boolean isGuarded(Location l) {
        double r = arena();
        for (Lair lair : reg(l.getWorld()).values()) {
            double dx = l.getX() - lair.x, dz = l.getZ() - lair.z, dy = l.getY() - lair.y;
            if (dx * dx + dz * dz <= r * r && dy > -14 && dy < 30) return true;
        }
        return false;
    }

    /** 둥지 마커가 처음 보일 때 (예전 맵처럼 기록이 없으면 기록한다). */
    void seen(Marker m) {
        String boss = m.getPersistentDataContainer().get(Keys.LAIR, PersistentDataType.STRING);
        if (boss == null) return;
        Map<UUID, Lair> r = reg(m.getWorld());
        if (!r.containsKey(m.getUniqueId())) {
            Location l = m.getLocation();
            r.put(m.getUniqueId(), new Lair(m.getUniqueId(), boss, l.getWorld().getName(), l.getX(), l.getY(), l.getZ()));
            save(m.getWorld());
        }
    }

    // ------------------------------------------------------------------ 보스가 쓰러질 때

    void onBossDeath(LivingEntity dead) {
        String lairId = dead.getPersistentDataContainer().get(Keys.LAIR, PersistentDataType.STRING);
        if (lairId == null) return;
        UUID id;
        try {
            id = UUID.fromString(lairId);
        } catch (IllegalArgumentException e) {
            return;
        }
        guardian.remove(id);
        Lair l = reg(dead.getWorld()).get(id);
        if (l == null) return;
        int min = respawnMinutes();
        l.respawnAt = System.currentTimeMillis() + min * 60_000L;
        l.kills++;
        save(dead.getWorld());
        MobDef def = mobs.registry().get(l.boss);
        String name = def == null ? l.boss : def.name();
        Bukkit.broadcast(Text.mm("<gray>" + name + "<gray>은(는) " + min + "분 뒤 둥지에서 다시 깨어납니다."));
    }

    // ------------------------------------------------------------------ 주기 처리 (1초)

    private void tick() {
        long now = System.currentTimeMillis();
        for (World w : Bukkit.getWorlds()) {
            for (Lair l : reg(w).values()) {
                if (!w.isChunkLoaded(((int) Math.floor(l.x)) >> 4, ((int) Math.floor(l.z)) >> 4)) {
                    forget(l);
                    continue;
                }
                Location home = new Location(w, l.x, l.y, l.z);
                LivingEntity boss = current(l);
                boolean near = playerNear(home, 72);
                if (boss != null) {
                    removeClock(l);
                    guard(l, boss, home);
                    continue;
                }
                if (now < l.respawnAt) {
                    if (near) showClock(l, home, l.respawnAt - now);
                    else removeClock(l);
                    continue;
                }
                removeClock(l);
                if (near) wake(l, home, l.respawnAt > 0);
            }
        }
    }

    private LivingEntity current(Lair l) {
        UUID b = guardian.get(l.id);
        if (b == null) return null;
        Entity e = Bukkit.getEntity(b);
        if (e instanceof LivingEntity le && le.isValid() && !le.isDead()) return le;
        guardian.remove(l.id);
        return null;
    }

    private void forget(Lair l) {
        UUID b = guardian.remove(l.id);
        if (b != null) {
            Entity e = Bukkit.getEntity(b);
            if (e != null) e.remove();
        }
        clock.remove(l.id);
        idle.remove(l.id);
    }

    private static boolean playerNear(Location c, double r) {
        for (Player p : c.getWorld().getPlayers()) {
            if (p.getGameMode() == GameMode.SPECTATOR) continue;
            if (p.getLocation().distanceSquared(c) <= r * r) return true;
        }
        return false;
    }

    private void wake(Lair l, Location home, boolean dramatic) {
        // 혹시 같은 둥지의 보스가 이미 있으면 (청크를 다시 읽은 경우 등) 그 보스를 쓴다
        for (Entity e : home.getWorld().getNearbyEntities(home, 40, 30, 40)) {
            if (e instanceof LivingEntity le && !le.isDead()
                    && l.id.toString().equals(e.getPersistentDataContainer().get(Keys.LAIR, PersistentDataType.STRING))) {
                guardian.put(l.id, le.getUniqueId());
                return;
            }
        }
        Location at = home.clone().add(0, 0.1, 0);
        at.setYaw((float) (Math.random() * 360));
        LivingEntity le = mobs.spawn(l.boss, at, false);
        if (le == null) return;
        le.setPersistent(false);
        le.getPersistentDataContainer().set(Keys.LAIR, PersistentDataType.STRING, l.id.toString());
        guardian.put(l.id, le.getUniqueId());
        if (l.respawnAt != 0) {
            l.respawnAt = 0;
            save(home.getWorld());
        }
        if (dramatic) {
            MobDef def = mobs.registry().get(l.boss);
            home.getWorld().spawnParticle(Particle.EXPLOSION_EMITTER, home, 1);
            Fx.sound(home, "entity.wither.spawn", 1.5f, 0.8f);
            Bukkit.broadcast(Text.mm("<#ff7070>☠ " + (def == null ? l.boss : def.name()) + "<gray>이(가) 둥지에서 다시 깨어났습니다!"));
        }
    }

    /** 둥지 지키기: 너무 멀리 가면 돌아오고, 싸울 상대가 없으면 둥지로 돌아가 체력을 회복한다. */
    private void guard(Lair l, LivingEntity boss, Location home) {
        Location b = boss.getLocation();
        double dx = b.getX() - home.getX(), dz = b.getZ() - home.getZ();
        double far = Math.sqrt(dx * dx + dz * dz);
        boolean fighting = false;
        double r = arena() + 10;
        for (Player p : home.getWorld().getPlayers()) {
            if (!Targets.isEnemy(boss, p)) continue;
            if (p.getLocation().distanceSquared(home) <= r * r) {
                fighting = true;
                break;
            }
        }
        if (far > leash() || b.getY() < home.getY() - 12) {
            home.getWorld().spawnParticle(Particle.REVERSE_PORTAL, b.clone().add(0, 1, 0), 60, 0.6, 1.5, 0.6, 0.1);
            Location to = home.clone();
            to.setYaw(b.getYaw());
            boss.teleport(to);
            if (boss instanceof Mob m) m.setTarget(null);
            Fx.sound(home, "entity.enderman.teleport", 1f, 0.6f);
            return;
        }
        if (fighting) {
            idle.remove(l.id);
            return;
        }
        int t = idle.merge(l.id, 1, Integer::sum);
        if (boss instanceof Mob m) {
            m.setTarget(null);
            if (far > 3) m.getPathfinder().moveTo(home, 1.0);
        }
        if (t >= 8) {
            double max = Combat.maxHealth(boss);
            if (boss.getHealth() < max) {
                boss.setHealth(Math.min(max, boss.getHealth() + max * 0.1));
                home.getWorld().spawnParticle(Particle.HEART, boss.getLocation().add(0, boss.getHeight() * 0.8, 0), 2, 0.6, 0.6, 0.6, 0);
            } else {
                mobs.resetFight(boss);
            }
        }
    }

    private void showClock(Lair l, Location home, long left) {
        MobDef def = mobs.registry().get(l.boss);
        long s = left / 1000;
        String text = (def == null ? l.boss : def.name()) + "\n<gray>다시 깨어나기까지 <white>"
                + (s / 60) + ":" + String.format("%02d", s % 60);
        TextDisplay td = null;
        UUID c = clock.get(l.id);
        if (c != null && Bukkit.getEntity(c) instanceof TextDisplay t && t.isValid()) td = t;
        if (td == null) {
            Location at = home.clone().add(0, 4.5, 0);
            td = home.getWorld().spawn(at, TextDisplay.class, t -> {
                t.setPersistent(false);
                t.setBillboard(Display.Billboard.CENTER);
                t.setBackgroundColor(org.bukkit.Color.fromARGB(110, 10, 6, 20));
                t.setShadowed(true);
                t.setTransformation(new org.bukkit.util.Transformation(new org.joml.Vector3f(), new org.joml.Quaternionf(),
                        new org.joml.Vector3f(1.6f), new org.joml.Quaternionf()));
                t.getPersistentDataContainer().set(Keys.LAIR_TEXT, PersistentDataType.STRING, l.id.toString());
            });
            clock.put(l.id, td.getUniqueId());
        }
        td.text(Text.mm(text));
        home.getWorld().spawnParticle(Particle.SOUL, home.clone().add(0, 0.5, 0), 3, 1.2, 0.2, 1.2, 0.01);
    }

    private void removeClock(Lair l) {
        UUID c = clock.remove(l.id);
        if (c == null) return;
        Entity e = Bukkit.getEntity(c);
        if (e != null) e.remove();
    }

    /** /증강 제단 처럼 둥지 상태를 알려 준다. */
    public List<String> describe(Player p) {
        List<String> out = new ArrayList<>();
        long now = System.currentTimeMillis();
        Location pl = p.getLocation();
        for (Lair l : reg(p.getWorld()).values()) {
            MobDef def = mobs.registry().get(l.boss);
            String name = def == null ? l.boss : def.name();
            int dist = (int) Math.hypot(l.x - pl.getX(), l.z - pl.getZ());
            String state = now < l.respawnAt ? "<gray>잠듦 (" + ((l.respawnAt - now) / 60000 + 1) + "분 뒤)" : "<#ff7070>깨어 있음";
            int dx = (int) Math.round(l.x - pl.getX()), dz = (int) Math.round(l.z - pl.getZ());
            out.add(name + " <dark_gray>— " + state + " <dark_gray>· <white>" + kr.augsky.map.MapBuilder.dir(dx, dz) + " " + dist + "m <dark_gray>("
                    + (int) l.x + ", " + (int) l.y + ", " + (int) l.z + ")");
        }
        return out;
    }
}
