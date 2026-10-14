package kr.labyrinth.mobs.npc;

import com.destroystokyo.paper.SkinParts;
import io.papermc.paper.datacomponent.item.ResolvableProfile;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.mobs.NpcService;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Mannequin;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.event.world.WorldLoadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.profile.PlayerTextures;
import org.bukkit.scheduler.BukkitTask;

/**
 * NPC (npcs.yml): {@code Mannequin} + 자체 스킨(ResolvableProfile SkinPatch body = {@code labyrinth:entity/npc/<skin>}),
 * 가까운 플레이어 바라보기, 우클릭 → 역할별 GUI. 위치는 관리자만 정한다(/labadmin setnpc) — 블록은 바꾸지 않는다.
 * <p>
 * 배치 위치는 {@code plugins/Labyrinth/npcs-placed.yml} 에 저장하고, 엔티티는 비영속(청크 언로드 시 사라짐)으로 두었다가
 * 청크가 로드되어 있으면 다시 세운다 → 월드 파일에 중복 NPC 가 쌓이지 않는다.
 */
public final class NpcServiceImpl implements NpcService, Listener {

    private record Placement(String world, double x, double y, double z, float yaw) {
        Location toLocation() {
            World w = Bukkit.getWorld(world);
            return w == null ? null : new Location(w, x, y, z, yaw, 0);
        }
    }

    private final Services services;
    private final File file;
    private final Map<String, Placement> placements = new LinkedHashMap<>();
    private final Map<String, Mannequin> live = new HashMap<>();
    private final Map<UUID, String> byEntity = new HashMap<>();
    private final Map<UUID, Entity> temporaries = new HashMap<>();
    private final Map<UUID, Map<String, Integer>> dialogueIndex = new HashMap<>();
    private final Map<UUID, Long> lastClick = new HashMap<>();
    private BukkitTask task;
    private long tick;

    public NpcServiceImpl(Services services) {
        this.services = services;
        this.file = new File(services.plugin().getDataFolder(), "npcs-placed.yml");
    }

    public void start() {
        load();
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 20L, 2L);
    }

    public void stop() {
        if (task != null) task.cancel();
        task = null;
        for (Mannequin m : live.values()) m.remove();
        live.clear();
        for (Entity e : temporaries.values()) e.remove();
        temporaries.clear();
        byEntity.clear();
        HandlerList.unregisterAll(this);
    }

    /** reload 후: 이름·스킨·대사가 바뀌었을 수 있으니 다시 세운다. */
    public void respawnAll() {
        for (Mannequin m : live.values()) {
            byEntity.remove(m.getUniqueId());
            m.remove();
        }
        live.clear();
        for (String id : placements.keySet()) ensureSpawned(id);
    }

    // ── 저장 ─────────────────────────────────────────────────────────────

    private void load() {
        placements.clear();
        if (!file.exists()) return;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file);
        ConfigurationSection s = y.getConfigurationSection("npcs");
        if (s == null) return;
        for (String id : s.getKeys(false)) {
            ConfigurationSection c = s.getConfigurationSection(id);
            if (c == null) continue;
            placements.put(id, new Placement(c.getString("world", "world"), c.getDouble("x"), c.getDouble("y"), c.getDouble("z"),
                    (float) c.getDouble("yaw")));
        }
        Log.info("NPC 배치 " + placements.size() + "개 불러옴");
    }

    private void save() {
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 — 관리자가 /labadmin setnpc 로 세운 NPC 위치 (직접 고치지 말 것)"));
        for (Map.Entry<String, Placement> e : placements.entrySet()) {
            String p = "npcs." + e.getKey() + ".";
            Placement pl = e.getValue();
            y.set(p + "world", pl.world());
            y.set(p + "x", pl.x());
            y.set(p + "y", pl.y());
            y.set(p + "z", pl.z());
            y.set(p + "yaw", (double) pl.yaw());
        }
        try {
            file.getParentFile().mkdirs();
            y.save(file);
        } catch (IOException ex) {
            Log.error("npcs-placed.yml 저장 실패", ex);
        }
    }

    public Map<String, Location> placed() {
        Map<String, Location> out = new LinkedHashMap<>();
        for (Map.Entry<String, Placement> e : placements.entrySet()) out.put(e.getKey(), e.getValue().toLocation());
        return out;
    }

    // ── NpcService ───────────────────────────────────────────────────────

    @Override
    public Entity place(String npcId, Location loc) {
        NpcDef def = services.content().npcs().get(npcId);
        if (def == null || loc == null || loc.getWorld() == null) return null;
        Mannequin old = live.remove(npcId);
        if (old != null) {
            byEntity.remove(old.getUniqueId());
            old.remove();
        }
        placements.put(npcId, new Placement(loc.getWorld().getName(), loc.getX(), loc.getY(), loc.getZ(), loc.getYaw()));
        save();
        return ensureSpawned(npcId);
    }

    @Override
    public boolean remove(String npcId) {
        Mannequin m = live.remove(npcId);
        if (m != null) {
            byEntity.remove(m.getUniqueId());
            m.remove();
        }
        boolean had = placements.remove(npcId) != null;
        if (had) save();
        return had || m != null;
    }

    @Override
    public Optional<String> npcIdOf(Entity entity) {
        if (entity == null) return Optional.empty();
        return Optional.ofNullable(byEntity.get(entity.getUniqueId()));
    }

    @Override
    public Entity spawnTemporary(String npcId, Location loc) {
        NpcDef def = services.content().npcs().get(npcId);
        if (def == null || loc == null || loc.getWorld() == null) return null;
        Mannequin m = spawnEntity(def, loc, true);
        if (m != null) temporaries.put(m.getUniqueId(), m);
        return m;
    }

    /** 임시 NPC 제거 (휴식방 정리 등). */
    public void removeTemporary(Entity e) {
        if (e == null) return;
        temporaries.remove(e.getUniqueId());
        byEntity.remove(e.getUniqueId());
        e.remove();
    }

    @Override
    public void interact(Player player, String npcId) {
        NpcDef def = services.content().npcs().get(npcId);
        if (def == null) return;
        long now = System.currentTimeMillis();
        Long last = lastClick.get(player.getUniqueId());
        if (last != null && now - last < 450) return;
        lastClick.put(player.getUniqueId(), now);
        String role = def.role() == null ? "lore" : def.role();
        boolean menuRole = !role.equals("lore");
        String line = nextLine(player, def, menuRole);
        if (line != null) {
            player.sendMessage(Text.mm(def.name() + " <dark_gray>»</dark_gray> " + line));
        }
        try {
            player.playSound(player.getLocation(), "minecraft:entity.item.pickup", 0.5f, 1.6f);
        } catch (Throwable ignored) {
            // 사운드 키 오류 무시
        }
        try {
            switch (role) {
                case "entrance" -> services.menus().openEntrance(player);
                case "blacksmith" -> services.crafting().openBlacksmith(player);
                case "class_master" -> services.menus().openClass(player);
                case "title_keeper" -> services.menus().openTitles(player);
                case "merchant" -> new ShopMenu(services, def).open(player);
                default -> { }
            }
        } catch (Throwable t) {
            Log.error("NPC 메뉴 열기 오류 (" + npcId + ")", t);
            Text.error(player, "메뉴를 여는 중 오류가 발생했습니다.");
        }
    }

    /** 대사 순환: 메뉴 NPC 는 무작위 한 줄, 이야기 NPC 는 차례대로. */
    private String nextLine(Player p, NpcDef def, boolean random) {
        List<String> lines = def.dialogue();
        if (lines == null || lines.isEmpty()) return null;
        if (random) return lines.get(java.util.concurrent.ThreadLocalRandom.current().nextInt(lines.size()));
        Map<String, Integer> idx = dialogueIndex.computeIfAbsent(p.getUniqueId(), k -> new HashMap<>());
        int i = idx.getOrDefault(def.id(), 0);
        idx.put(def.id(), (i + 1) % lines.size());
        String prefix = lines.size() > 1 ? "<dark_gray>(" + (i + 1) + "/" + lines.size() + ")</dark_gray> " : "";
        return prefix + lines.get(i % lines.size());
    }

    // ── 엔티티 ───────────────────────────────────────────────────────────

    private Mannequin ensureSpawned(String id) {
        Mannequin cur = live.get(id);
        if (cur != null && cur.isValid()) return cur;
        if (cur != null) {
            byEntity.remove(cur.getUniqueId());
            live.remove(id);
        }
        Placement pl = placements.get(id);
        NpcDef def = services.content().npcs().get(id);
        if (pl == null || def == null) return null;
        Location loc = pl.toLocation();
        if (loc == null || !loc.getWorld().isChunkLoaded(loc.getBlockX() >> 4, loc.getBlockZ() >> 4)) return null;
        Mannequin m = spawnEntity(def, loc, false);
        if (m != null) live.put(id, m);
        return m;
    }

    private Mannequin spawnEntity(NpcDef def, Location loc, boolean temporary) {
        try {
            Mannequin m = loc.getWorld().spawn(loc, Mannequin.class, e -> {
                e.setPersistent(false);
                e.setImmovable(true);
                e.setInvulnerable(true);
                e.setSilent(true);
                e.setRemoveWhenFarAway(false);
                e.setCollidable(false);
                e.customName(Text.mm(def.name()));
                e.setCustomNameVisible(true);
                e.setDescription(def.nameplate() != null && !def.nameplate().isBlank()
                        ? Text.mm(def.nameplate()) : net.kyori.adventure.text.Component.empty());
                String skin = def.skin() == null || def.skin().isBlank() ? def.id() : def.skin();
                e.setProfile(ResolvableProfile.resolvableProfile()
                        .skinPatch(sp -> sp.body(Key.key(Keys.NS, "entity/npc/" + skin)).model(PlayerTextures.SkinModel.CLASSIC))
                        .build());
                e.setSkinParts(SkinParts.allParts());
                e.getPersistentDataContainer().set(Keys.NPC, PersistentDataType.STRING, def.id());
                if (temporary) Keys.tagTransient(e, Keys.FX, "npc:" + def.id());
            });
            byEntity.put(m.getUniqueId(), def.id());
            return m;
        } catch (Throwable t) {
            Log.error("NPC 생성 실패 (" + def.id() + ")", t);
            return null;
        }
    }

    private void tickAll() {
        tick++;
        if (tick % 10 == 0) for (String id : placements.keySet()) ensureSpawned(id);
        List<Mannequin> all = new ArrayList<>(live.values());
        for (Entity e : temporaries.values()) if (e instanceof Mannequin m) all.add(m);
        for (Mannequin m : all) {
            if (!m.isValid()) continue;
            lookAtNearest(m);
        }
        if (tick % 600 == 0) temporaries.values().removeIf(e -> !e.isValid());
    }

    /** 가까운 플레이어(8블록)를 부드럽게 바라본다. 없으면 원래 방향으로. */
    private void lookAtNearest(Mannequin m) {
        Location loc = m.getLocation();
        Player best = null;
        double bestD = 64;
        for (Player p : loc.getWorld().getPlayers()) {
            if (p.getGameMode() == GameMode.SPECTATOR) continue;
            double d = p.getLocation().distanceSquared(loc);
            if (d < bestD) {
                bestD = d;
                best = p;
            }
        }
        float targetYaw, targetPitch;
        if (best != null) {
            Location eye = loc.clone().add(0, 1.62, 0);
            Location to = best.getEyeLocation();
            double dx = to.getX() - eye.getX(), dz = to.getZ() - eye.getZ(), dy = to.getY() - eye.getY();
            targetYaw = (float) Math.toDegrees(Math.atan2(-dx, dz));
            targetPitch = (float) Math.max(-35, Math.min(35, -Math.toDegrees(Math.atan2(dy, Math.sqrt(dx * dx + dz * dz)))));
        } else {
            String id = byEntity.get(m.getUniqueId());
            Placement pl = id == null ? null : placements.get(id);
            targetYaw = pl != null ? pl.yaw() : loc.getYaw();
            targetPitch = 0;
        }
        float dyaw = wrap(targetYaw - loc.getYaw());
        float dpitch = targetPitch - loc.getPitch();
        if (Math.abs(dyaw) < 0.5f && Math.abs(dpitch) < 0.5f) return;
        float ny = loc.getYaw() + Math.max(-14f, Math.min(14f, dyaw));
        float np = loc.getPitch() + Math.max(-8f, Math.min(8f, dpitch));
        m.setRotation(ny, np);
    }

    private static float wrap(float d) {
        d %= 360f;
        if (d > 180f) d -= 360f;
        if (d <= -180f) d += 360f;
        return d;
    }

    // ── 이벤트 ───────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEntityEvent e) {
        String id = byEntity.get(e.getRightClicked().getUniqueId());
        if (id == null) return;
        e.setCancelled(true);
        if (e.getHand() != EquipmentSlot.HAND) return;
        interact(e.getPlayer(), id);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteractAt(PlayerInteractAtEntityEvent e) {
        if (byEntity.containsKey(e.getRightClicked().getUniqueId())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onDamage(EntityDamageEvent e) {
        if (byEntity.containsKey(e.getEntity().getUniqueId())) {
            e.setCancelled(true);
            if (e instanceof org.bukkit.event.entity.EntityDamageByEntityEvent be && be.getDamager() instanceof Player p) {
                String id = byEntity.get(e.getEntity().getUniqueId());
                if (id != null) interact(p, id); // 좌클릭도 대화로
            }
        }
    }

    @EventHandler
    public void onEntitiesLoad(EntitiesLoadEvent e) {
        // 이전 버전/비정상 종료로 남은 NPC 엔티티 정리 (지금 관리 중인 것 제외)
        for (Entity en : e.getEntities()) {
            if (en.getPersistentDataContainer().has(Keys.NPC) && !byEntity.containsKey(en.getUniqueId())) en.remove();
        }
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            for (String id : placements.keySet()) ensureSpawned(id);
        });
    }

    @EventHandler
    public void onWorldLoad(WorldLoadEvent e) {
        for (String id : placements.keySet()) ensureSpawned(id);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        dialogueIndex.remove(e.getPlayer().getUniqueId());
        lastClick.remove(e.getPlayer().getUniqueId());
    }

    /** 스폰 연출용 입자 (명령 피드백). */
    public static void sparkle(Location l) {
        if (l.getWorld() != null) l.getWorld().spawnParticle(Particle.END_ROD, l.clone().add(0, 1, 0), 20, 0.3, 0.6, 0.3, 0.02);
    }
}
