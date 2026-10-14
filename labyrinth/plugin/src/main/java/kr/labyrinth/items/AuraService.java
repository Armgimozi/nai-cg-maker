package kr.labyrinth.items;

import io.papermc.paper.event.player.PlayerArmSwingEvent;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.content.AuraDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Log;
import kr.labyrinth.items.weaponskills.Fx;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * 전설·신화 무기 아우라 (GDD §11.5). 무기를 주손에 든 동안:
 * <ul>
 *   <li>입자: fx.yml particles 를 pattern(orbit·spiral·rise·fall·swirl·burst·trail)대로 interval 틱마다</li>
 *   <li>링: 발밑(ring_height) 수평 ItemDisplay(labyrinth:fx/&lt;ring_model&gt;) 를 ring_spin 도/틱 회전 (ring_step = 1초마다 30° 끊어서)</li>
 *   <li>신화: secondary_model 을 반대 방향 회전(ring) 또는 등 뒤에 붙임(back)</li>
 *   <li>LOD: 보는 사람이 24칸 밖이면 입자 절반, 48칸 밖이면 입자 없음(링만). 같은 월드에 아우라 6개 이상이면 입자 간격 2배.</li>
 *   <li>투명(그림자 잠행)·관전 중에는 숨김. 무기를 내려놓거나 나가면 디스플레이 즉시 제거.</li>
 * </ul>
 */
public final class AuraService implements Listener {

    private static final double LOD_HALF = 24 * 24;
    private static final double LOD_NONE = 48 * 48;

    private final Services services;
    private final Map<UUID, State> states = new ConcurrentHashMap<>();
    private BukkitTask task;
    private long tick;

    private static final class State {
        final String auraId;
        ItemDisplay ring;
        ItemDisplay secondary;
        float angle;
        float angle2;
        Location lastPos;

        State(String auraId) { this.auraId = auraId; }

        void remove() {
            if (ring != null && ring.isValid()) ring.remove();
            if (secondary != null && secondary.isValid()) secondary.remove();
            ring = null;
            secondary = null;
        }
    }

    public AuraService(Services services) { this.services = services; }

    public void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 1L, 1L);
    }

    public void stop() {
        if (task != null) task.cancel();
        HandlerList.unregisterAll(this);
        states.values().forEach(State::remove);
        states.clear();
    }

    /** 콘텐츠 reload 후: 디스플레이를 새 정의로 다시 만든다. */
    public void reload() {
        states.values().forEach(State::remove);
        states.clear();
    }

    private AuraDef auraOf(Player p) {
        if (p.getGameMode() == GameMode.SPECTATOR || p.isDead() || p.isInvisible()
                || p.hasPotionEffect(PotionEffectType.INVISIBILITY)) return null;
        ItemDef def = services.items().heldWeapon(p);
        if (def == null || def.aura() == null) return null;
        return services.content().auras().get(def.aura());
    }

    private void tickAll() {
        tick++;
        Map<World, Integer> perWorld = new java.util.HashMap<>();
        for (State s : states.values()) {
            if (s.lastPos != null && s.lastPos.getWorld() != null) perWorld.merge(s.lastPos.getWorld(), 1, Integer::sum);
        }
        for (Player p : Bukkit.getOnlinePlayers()) {
            try {
                tickPlayer(p, perWorld.getOrDefault(p.getWorld(), 0) >= 6);
            } catch (Throwable t) {
                Log.error("아우라 오류: " + p.getName(), t);
                State s = states.remove(p.getUniqueId());
                if (s != null) s.remove();
            }
        }
    }

    private void tickPlayer(Player p, boolean crowded) {
        AuraDef aura = auraOf(p);
        State s = states.get(p.getUniqueId());
        if (aura == null) {
            if (s != null) {
                s.remove();
                states.remove(p.getUniqueId());
            }
            return;
        }
        if (s == null || !s.auraId.equals(aura.id())) {
            if (s != null) s.remove();
            s = new State(aura.id());
            states.put(p.getUniqueId(), s);
        }
        Location feet = p.getLocation();
        updateRing(p, aura, s, feet);

        int interval = Math.max(1, aura.interval()) * (crowded ? 2 : 1);
        if (tick % interval == 0) emitParticles(p, aura, s, feet);
        s.lastPos = feet.clone();
    }

    private void updateRing(Player p, AuraDef aura, State s, Location feet) {
        float scale = (float) (aura.ringScale() <= 0 ? 1.0 : aura.ringScale());
        if (aura.ringModel() != null && Fx.exists(services, aura.ringModel())) {
            Location at = feet.clone().add(0, aura.ringHeight(), 0);
            at.setYaw(0);
            at.setPitch(0);
            if (s.ring == null || !s.ring.isValid() || !s.ring.getWorld().equals(p.getWorld())) {
                if (s.ring != null) s.ring.remove();
                s.ring = Fx.spawn(services, at, aura.ringModel(), scale, 0);
            } else {
                s.ring.teleport(at);
            }
            if (aura.ringStep()) {
                if (tick % 20 == 0) {
                    s.angle += 30f;
                    Fx.transform(s.ring, (float) Math.toRadians(s.angle), scale, scale, scale, 3);
                }
            } else if (tick % 2 == 0) {
                s.angle += (float) (aura.ringSpin() * 2);
                Fx.transform(s.ring, (float) Math.toRadians(s.angle), scale, scale, scale, 2);
            }
        }
        if (aura.secondaryModel() != null && Fx.exists(services, aura.secondaryModel())) {
            boolean back = "back".equalsIgnoreCase(aura.secondaryMode());
            Location at;
            if (back) {
                Vector dir = new Vector(-Math.sin(Math.toRadians(p.getBodyYaw())), 0, Math.cos(Math.toRadians(p.getBodyYaw())));
                at = feet.clone().add(0, 1.25, 0).subtract(dir.multiply(0.35));
                at.setYaw(p.getBodyYaw());
                at.setPitch(0);
            } else {
                at = feet.clone().add(0, aura.ringHeight() + 0.03, 0);
                at.setYaw(0);
                at.setPitch(0);
            }
            if (s.secondary == null || !s.secondary.isValid() || !s.secondary.getWorld().equals(p.getWorld())) {
                if (s.secondary != null) s.secondary.remove();
                s.secondary = Fx.spawn(services, at, aura.secondaryModel(), back ? 1f : scale * 1.15f, 0);
            } else {
                s.secondary.teleport(at);
            }
            if (!back && tick % 2 == 0) {
                double spin = aura.secondarySpin() == 0 ? -aura.ringSpin() : aura.secondarySpin();
                s.angle2 += (float) (spin * 2);
                Fx.transform(s.secondary, (float) Math.toRadians(s.angle2), scale * 1.15f, scale * 1.15f, scale * 1.15f, 2);
            }
        }
    }

    private void emitParticles(Player owner, AuraDef aura, State s, Location feet) {
        List<Player> near = new ArrayList<>();
        List<Player> far = new ArrayList<>();
        for (Player v : owner.getWorld().getPlayers()) {
            double d = v.getLocation().distanceSquared(feet);
            if (d <= LOD_HALF) near.add(v);
            else if (d <= LOD_NONE) far.add(v);
        }
        if (near.isEmpty() && far.isEmpty()) return;
        ThreadLocalRandom r = ThreadLocalRandom.current();
        for (Params pp : aura.particles()) {
            if (pp.has("chance") && r.nextDouble() >= pp.dbl("chance", 1)) continue;
            Particle type = particle(pp.str("type"));
            if (type == null) continue;
            int count = Math.max(1, pp.integer("count", 1));
            double radius = pp.dbl("radius", 0.6);
            double height = pp.dbl("height", 1.0);
            double speed = pp.dbl("speed", 0.0);
            String pattern = pp.str("pattern", "orbit");
            Object data = data(type, pp);
            if (data == NO_DATA) continue;
            for (int i = 0; i < count; i++) {
                boolean farOk = i % 2 == 0;
                List<Player> rec = farOk ? concat(near, far) : near;
                if (rec.isEmpty()) continue;
                spawnPattern(type, data, pattern, feet, s, radius, height, speed, i, count, rec, r);
            }
        }
    }

    private static final Object NO_DATA = new Object();

    private void spawnPattern(Particle type, Object data, String pattern, Location feet, State s, double radius, double height,
                              double speed, int i, int count, List<Player> rec, ThreadLocalRandom r) {
        double phase = tick * 0.15 + i * Math.PI * 2 / count;
        Location at;
        Vector motion = null;
        switch (pattern) {
            case "spiral" -> {
                double y = (tick * 0.06 + i * 0.5) % 2.0;
                double a = tick * 0.35 + i * Math.PI;
                at = feet.clone().add(Math.cos(a) * radius, y, Math.sin(a) * radius);
            }
            case "rise" -> {
                double a = r.nextDouble(Math.PI * 2);
                double d = Math.sqrt(r.nextDouble()) * radius;
                at = feet.clone().add(Math.cos(a) * d, height * r.nextDouble(0.3, 1.0), Math.sin(a) * d);
                motion = new Vector(0, 1, 0);
            }
            case "fall" -> {
                double a = r.nextDouble(Math.PI * 2);
                double d = Math.sqrt(r.nextDouble()) * radius;
                at = feet.clone().add(Math.cos(a) * d, height, Math.sin(a) * d);
                motion = new Vector(0, -1, 0);
            }
            case "swirl" -> {
                double a = tick * 0.6 + i * Math.PI * 2 / count;
                at = feet.clone().add(Math.cos(a) * radius * 0.5, height + Math.sin(tick * 0.2) * 0.2, Math.sin(a) * radius * 0.5);
            }
            case "burst" -> {
                at = feet.clone().add(0, height, 0);
                motion = new Vector(r.nextDouble(-1, 1), r.nextDouble(-0.2, 1), r.nextDouble(-1, 1)).normalize();
            }
            case "trail" -> {
                if (s.lastPos == null || s.lastPos.distanceSquared(feet) < 0.01) return;
                at = s.lastPos.clone().add(r.nextDouble(-radius, radius) * 0.5, height, r.nextDouble(-radius, radius) * 0.5);
            }
            default -> at = feet.clone().add(Math.cos(phase) * radius, height, Math.sin(phase) * radius); // orbit
        }
        var b = type.builder().location(at).receivers(rec);
        if (motion != null && speed > 0 && data == null) {
            b.count(0).offset(motion.getX(), motion.getY(), motion.getZ()).speed(speed);
        } else {
            b.count(1).offset(0.02, 0.02, 0.02).speed(speed);
        }
        if (data != null) b.data(data);
        b.spawn();
    }

    private static List<Player> concat(List<Player> a, List<Player> b) {
        if (b.isEmpty()) return a;
        List<Player> out = new ArrayList<>(a.size() + b.size());
        out.addAll(a);
        out.addAll(b);
        return out;
    }

    static Particle particle(String name) {
        if (name == null) return null;
        try {
            return Particle.valueOf(name.trim().toUpperCase(java.util.Locale.ROOT));
        } catch (IllegalArgumentException e) {
            Log.warnOnce("aura-particle-" + name, "[아우라] 알 수 없는 입자: " + name);
            return null;
        }
    }

    private Object data(Particle type, Params pp) {
        Class<?> dt = type.getDataType();
        if (dt == Void.class) return null;
        float size = (float) pp.dbl("size", 1.0);
        Color color = Fx.parseColor(pp.str("color"), Color.WHITE);
        if (dt == Particle.DustOptions.class) return new Particle.DustOptions(color, size);
        if (dt == Particle.DustTransition.class) {
            return new Particle.DustTransition(color, Fx.parseColor(pp.str("color_to"), color), size);
        }
        if (dt == Color.class) return color;
        if (dt == Float.class) return 0f;
        if (dt == Integer.class) return 0;
        Log.warnOnce("aura-data-" + type, "[아우라] 데이터가 필요한 입자는 지원하지 않음: " + type);
        return NO_DATA;
    }

    // ── 휘두르기 입자 · 정리 ──────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwing(PlayerArmSwingEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        AuraDef aura = auraOf(e.getPlayer());
        if (aura == null || aura.swing() == null || aura.swing().isEmpty()) return;
        Params sw = aura.swing();
        Particle type = particle(sw.str("type"));
        if (type == null) return;
        Object data = data(type, sw);
        if (data == NO_DATA) return;
        Player p = e.getPlayer();
        Location at = p.getEyeLocation().add(p.getEyeLocation().getDirection().multiply(1.2)).subtract(0, 0.3, 0);
        var b = type.builder().location(at).count(Math.max(1, sw.integer("count", 6))).offset(0.4, 0.3, 0.4)
                .speed(sw.dbl("speed", 0.05)).receivers(48, true);
        if (data != null) b.data(data);
        b.spawn();
    }

    private void clear(Player p) {
        State s = states.remove(p.getUniqueId());
        if (s != null) s.remove();
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { clear(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) { clear(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) { clear(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        if (e.getFrom().getWorld() != e.getTo().getWorld() || e.getFrom().distanceSquared(e.getTo()) > 32 * 32) clear(e.getPlayer());
    }
}
