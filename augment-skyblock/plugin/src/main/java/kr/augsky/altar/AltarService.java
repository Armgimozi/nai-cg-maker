package kr.augsky.altar;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.PlayerData;
import kr.augsky.augment.Tier;
import kr.augsky.map.MapBuilder;
import kr.augsky.util.Fx;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Interaction;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.event.world.EntitiesUnloadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.persistence.PersistentDataType;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 제단: 맵 곳곳의 상호작용 엔티티. 누르면 제단 화면을 연다.
 * 제단은 일회용이다 (config altar.single-use: global = 한 명이 쓰면 사라짐, player = 사람마다 한 번, off = 무제한).
 * 어디에 어떤 제단이 있는지는 월드 폴더의 augsky-altars.yml 에 기록해 두고, 맵과 함께 배포된다.
 */
public final class AltarService implements Listener {
    public enum Mode { GLOBAL, PLAYER, OFF }

    public record Info(UUID id, Tier tier, String world, double x, double y, double z, boolean used) {
        public Location location() {
            World w = Bukkit.getWorld(world);
            return w == null ? null : new Location(w, x, y, z);
        }
    }

    private static final String FILE = "augsky-altars.yml";
    private static final Material[] RAINBOW = {
            Material.RED_STAINED_GLASS, Material.ORANGE_STAINED_GLASS, Material.YELLOW_STAINED_GLASS,
            Material.LIME_STAINED_GLASS, Material.LIGHT_BLUE_STAINED_GLASS, Material.BLUE_STAINED_GLASS,
            Material.PURPLE_STAINED_GLASS, Material.MAGENTA_STAINED_GLASS
    };

    private final AugSky plugin;
    private final Set<UUID> beams = new HashSet<>();
    private final Map<UUID, Tier> loaded = new HashMap<>();
    /** 블록 보호 범위의 중심 (제단) */
    private final Map<UUID, Location> guarded = new HashMap<>();
    /** 월드 이름 → (제단 UUID → 정보) */
    private final Map<String, Map<UUID, Info>> registry = new HashMap<>();
    private int tick;

    public AltarService(AugSky plugin) {
        this.plugin = plugin;
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 40, 10);
    }

    public Mode mode() {
        String s = plugin.getConfig().getString("altar.single-use", "global").toLowerCase(Locale.ROOT);
        return switch (s) {
            case "player", "per-player", "사람마다" -> Mode.PLAYER;
            case "off", "false", "none", "무제한" -> Mode.OFF;
            default -> Mode.GLOBAL;
        };
    }

    // ------------------------------------------------------------------ 기록 (월드 폴더)

    private Map<UUID, Info> reg(World w) {
        return registry.computeIfAbsent(w.getName(), k -> load(w));
    }

    private Map<UUID, Info> load(World w) {
        Map<UUID, Info> m = new LinkedHashMap<>();
        File f = new File(w.getWorldFolder(), FILE);
        if (!f.exists()) return m;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        ConfigurationSection sec = y.getConfigurationSection("altars");
        if (sec == null) return m;
        for (String k : sec.getKeys(false)) {
            ConfigurationSection a = sec.getConfigurationSection(k);
            Tier t = a == null ? null : Tier.parse(a.getString("tier"));
            if (t == null) continue;
            try {
                UUID id = UUID.fromString(k);
                m.put(id, new Info(id, t, w.getName(), a.getDouble("x"), a.getDouble("y"), a.getDouble("z"), a.getBoolean("used")));
            } catch (IllegalArgumentException ignored) {
            }
        }
        return m;
    }

    private void save(World w) {
        Map<UUID, Info> m = reg(w);
        YamlConfiguration y = new YamlConfiguration();
        for (Info i : m.values()) {
            String p = "altars." + i.id();
            y.set(p + ".tier", i.tier().name());
            y.set(p + ".x", i.x());
            y.set(p + ".y", i.y());
            y.set(p + ".z", i.z());
            y.set(p + ".used", i.used());
        }
        try {
            y.save(new File(w.getWorldFolder(), FILE));
        } catch (IOException e) {
            plugin.getLogger().warning("제단 기록 저장 실패: " + e.getMessage());
        }
    }

    public void register(UUID id, Tier tier, Location at) {
        reg(at.getWorld()).put(id, new Info(id, tier, at.getWorld().getName(), at.getX(), at.getY(), at.getZ(), false));
        save(at.getWorld());
    }

    public void clearRegistry(World w) {
        reg(w).clear();
        save(w);
    }

    public List<Info> all(World w) {
        return new ArrayList<>(reg(w).values());
    }

    /** 이 플레이어가 아직 쓸 수 있는, 가까운 순서의 제단. */
    public List<Info> nearestUsable(Player p, Tier tier, int n) {
        Location l = p.getLocation();
        PlayerData d = plugin.augments().data(p);
        List<Info> out = new ArrayList<>();
        for (Info i : reg(p.getWorld()).values()) {
            if (tier != null && i.tier() != tier) continue;
            if (!usable(i, d)) continue;
            out.add(i);
        }
        out.sort(Comparator.comparingDouble(i -> Math.hypot(i.x() - l.getX(), i.z() - l.getZ())));
        return out.size() > n ? out.subList(0, n) : out;
    }

    public int remaining(World w, Tier tier) {
        int n = 0;
        for (Info i : reg(w).values()) if (i.tier() == tier && !i.used()) n++;
        return n;
    }

    /** 제물을 받기 직전에 다시 확인한다 (두 사람이 같은 제단 창을 동시에 연 경우). */
    public boolean isUsable(UUID altarId, Player p) {
        if (altarId == null) return true;
        PlayerData d = plugin.augments().data(p);
        return switch (mode()) {
            case GLOBAL -> {
                Entity en = Bukkit.getEntity(altarId);
                if (en != null && en.getPersistentDataContainer().has(Keys.USED)) yield false;
                Info i = reg(p.getWorld()).get(altarId);
                yield i == null || !i.used();
            }
            case PLAYER -> !d.usedAltars.contains(altarId.toString());
            case OFF -> true;
        };
    }

    private boolean usable(Info i, PlayerData d) {
        return switch (mode()) {
            case GLOBAL -> !i.used();
            case PLAYER -> !d.usedAltars.contains(i.id().toString());
            case OFF -> true;
        };
    }

    // ------------------------------------------------------------------ 엔티티 추적

    public void scanLoaded() {
        for (World w : Bukkit.getWorlds()) for (Entity e : w.getEntities()) track(e);
    }

    private void track(Entity e) {
        var pdc = e.getPersistentDataContainer();
        if (e instanceof BlockDisplay && "prism".equals(pdc.get(Keys.BEAM, PersistentDataType.STRING))) beams.add(e.getUniqueId());
        if (e instanceof Interaction) {
            Tier t = Tier.parse(pdc.get(Keys.ALTAR, PersistentDataType.STRING));
            if (t != null) {
                guarded.put(e.getUniqueId(), e.getLocation());
                if (!pdc.has(Keys.USED)) loaded.put(e.getUniqueId(), t);
                // 예전 맵처럼 기록이 없는 제단도 처음 보이면 기록해 둔다
                Map<UUID, Info> m = reg(e.getWorld());
                if (!m.containsKey(e.getUniqueId())) {
                    Location l = e.getLocation();
                    m.put(e.getUniqueId(), new Info(e.getUniqueId(), t, l.getWorld().getName(), l.getX(), l.getY(), l.getZ(), pdc.has(Keys.USED)));
                    save(e.getWorld());
                }
            }
        }
    }

    @EventHandler
    public void onLoad(EntitiesLoadEvent e) {
        for (Entity en : e.getEntities()) track(en);
    }

    @EventHandler
    public void onUnload(EntitiesUnloadEvent e) {
        for (Entity en : e.getEntities()) {
            beams.remove(en.getUniqueId());
            loaded.remove(en.getUniqueId());
            guarded.remove(en.getUniqueId());
        }
    }

    // ------------------------------------------------------------------ 사용

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Entity en = e.getRightClicked();
        if (!(en instanceof Interaction)) return;
        var pdc = en.getPersistentDataContainer();
        Tier t = Tier.parse(pdc.get(Keys.ALTAR, PersistentDataType.STRING));
        if (t == null) return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        plugin.weaponListener().suppress(p, 6);
        PlayerData d = plugin.augments().data(p);
        // 고르다 만 선택지가 있으면 어느 제단에서든 이어서 고른다
        if (d.hasOffer()) {
            plugin.menus().openChoice(p);
            return;
        }
        Mode mode = mode();
        boolean used = switch (mode) {
            case GLOBAL -> pdc.has(Keys.USED);
            case PLAYER -> d.usedAltars.contains(en.getUniqueId().toString());
            case OFF -> false;
        };
        if (used) {
            en.getWorld().spawnParticle(Particle.SMOKE, en.getLocation().add(0, 1.5, 0), 20, 0.4, 0.4, 0.4, 0.01);
            Fx.sound(en.getLocation(), "block.beacon.deactivate", 0.6f, 1.6f);
            p.sendMessage(Text.mm(mode == Mode.GLOBAL
                    ? "<gray>이 " + t.korean + " 제단은 이미 힘을 다했습니다. <white>/증강 제단<gray> 으로 남은 제단을 찾아보세요."
                    : "<gray>이 제단에서는 이미 증강을 받았습니다. 다른 " + t.korean + " 제단을 찾아보세요."));
            return;
        }
        plugin.menus().claim(p, t, en.getUniqueId());
    }

    /** 증강권: 손에 들고 우클릭하면 어디서든 그 등급 증강을 고른다. */
    @EventHandler(priority = EventPriority.HIGH)
    public void onUseTicket(org.bukkit.event.player.PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        var a = e.getAction();
        if (a != org.bukkit.event.block.Action.RIGHT_CLICK_AIR && a != org.bukkit.event.block.Action.RIGHT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        String id = kr.augsky.util.Items.tag(p.getInventory().getItemInMainHand(), Keys.ITEM);
        if (id == null || !id.startsWith("ticket_")) return;
        Tier t = Tier.parse(id.substring("ticket_".length()));
        if (t == null) return;
        e.setCancelled(true);
        PlayerData d = plugin.augments().data(p);
        if (d.hasOffer()) {
            plugin.menus().openChoice(p);
            return;
        }
        if (plugin.menus().claim(p, t, null)) plugin.augments().useTicket(p, t);
    }

    /** 제단의 힘을 쓴다. 제물을 낸 직후(선택지가 열릴 때) 부른다. */
    public void consume(UUID altarId, Player p) {
        Mode mode = mode();
        if (mode == Mode.OFF || altarId == null) return;
        Entity en = Bukkit.getEntity(altarId);
        if (mode == Mode.PLAYER) {
            PlayerData d = plugin.augments().data(p);
            d.usedAltars.add(altarId.toString());
            plugin.augments().store().save(d);
            return;
        }
        Tier tier = null;
        World w = en != null ? en.getWorld() : p.getWorld();
        Map<UUID, Info> m = reg(w);
        Info old = m.get(altarId);
        if (old != null) {
            tier = old.tier();
            m.put(altarId, new Info(old.id(), old.tier(), old.world(), old.x(), old.y(), old.z(), true));
            save(w);
        }
        if (en != null) {
            en.getPersistentDataContainer().set(Keys.USED, PersistentDataType.BYTE, (byte) 1);
            if (tier == null) tier = Tier.parse(en.getPersistentDataContainer().get(Keys.ALTAR, PersistentDataType.STRING));
            loaded.remove(altarId);
            Location c = en.getLocation();
            for (Entity part : c.getWorld().getNearbyEntities(c, 6, 12, 6)) {
                String of = part.getPersistentDataContainer().get(Keys.ALTAR_OF, PersistentDataType.STRING);
                if (!altarId.toString().equals(of)) continue;
                if (part instanceof BlockDisplay bd) {
                    if (bd.getPersistentDataContainer().has(Keys.BEAM)) {
                        beams.remove(bd.getUniqueId());
                        bd.remove();
                    } else {
                        bd.setBlock(Material.TINTED_GLASS.createBlockData());
                        bd.setBrightness(null);
                    }
                } else if (part instanceof TextDisplay td) {
                    td.text(Text.mm("<dark_gray>힘을 다한 " + (tier == null ? "" : tier.korean + " ") + "제단"));
                }
            }
            c.getWorld().spawnParticle(Particle.FLASH, c.clone().add(0, 2, 0), 1);
            c.getWorld().spawnParticle(Particle.END_ROD, c.clone().add(0, 2, 0), 60, 0.6, 1.5, 0.6, 0.1);
            Fx.sound(c, "block.beacon.deactivate", 1f, 0.8f);
        }
        if (tier != null) {
            int left = remaining(w, tier);
            Bukkit.broadcast(Text.mm("<gray>✦ " + p.getName() + "님이 " + tier.label() + " <gray>제단의 힘을 깨웠습니다. <dark_gray>(남은 "
                    + tier.korean + " 제단 " + left + "곳)"));
        }
    }

    /** 제단을 좌클릭해도 아무 일 없게. */
    @EventHandler(ignoreCancelled = true)
    public void onHit(EntityDamageByEntityEvent e) {
        if (e.getEntity() instanceof Interaction i && i.getPersistentDataContainer().has(Keys.ALTAR)) {
            e.setCancelled(true);
            if (e.getDamager() instanceof Player p) {
                Tier t = Tier.parse(i.getPersistentDataContainer().get(Keys.ALTAR, PersistentDataType.STRING));
                if (t != null) p.sendActionBar(Text.mm(t.wrap(t.korean + " 제단") + " <gray>— 우클릭해서 사용"));
            }
        }
    }

    // ------------------------------------------------------------------ 블록 보호

    public boolean isGuarded(Location l) {
        for (Location c : guarded.values()) {
            if (!c.getWorld().equals(l.getWorld())) continue;
            double dx = l.getBlockX() + 0.5 - c.getX(), dz = l.getBlockZ() + 0.5 - c.getZ();
            double dy = l.getBlockY() - c.getY();
            if (dx * dx + dz * dz <= 5.2 * 5.2 && dy >= -3 && dy <= 7) return true;
        }
        return plugin.mobs() != null && plugin.mobs().isLairGuarded(l);
    }

    private boolean bypass(Player p) {
        return p.getGameMode() == org.bukkit.GameMode.CREATIVE && p.hasPermission("augsky.admin");
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBreak(org.bukkit.event.block.BlockBreakEvent e) {
        if (!bypass(e.getPlayer()) && isGuarded(e.getBlock().getLocation())) {
            e.setCancelled(true);
            e.getPlayer().sendActionBar(Text.mm("<#ff7070>이곳은 부술 수 없습니다"));
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPlace(org.bukkit.event.block.BlockPlaceEvent e) {
        if (bypass(e.getPlayer())) return;
        // 제단 바닥 위쪽 공간은 비워 둔다 (기둥/빛기둥 가림 방지). 가장자리 다리 연결은 허용
        Location c = e.getBlock().getLocation();
        for (Location g : guarded.values()) {
            if (!g.getWorld().equals(c.getWorld())) continue;
            double dx = c.getBlockX() + 0.5 - g.getX(), dz = c.getBlockZ() + 0.5 - g.getZ();
            if (dx * dx + dz * dz <= 4.4 * 4.4 && c.getBlockY() >= g.getBlockY() - 1 && c.getBlockY() <= g.getBlockY() + 8) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onExplode(org.bukkit.event.entity.EntityExplodeEvent e) {
        e.blockList().removeIf(b -> isGuarded(b.getLocation()));
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockExplode(org.bukkit.event.block.BlockExplodeEvent e) {
        e.blockList().removeIf(b -> isGuarded(b.getLocation()));
    }

    // ------------------------------------------------------------------ 연출

    private void tick() {
        tick++;
        Iterator<UUID> it = beams.iterator();
        Material glass = RAINBOW[tick % RAINBOW.length];
        while (it.hasNext()) {
            Entity e = Bukkit.getEntity(it.next());
            if (!(e instanceof BlockDisplay bd) || !e.isValid()) {
                it.remove();
                continue;
            }
            bd.setBlock(glass.createBlockData());
        }
        if (tick % 2 != 0) return;
        for (Map.Entry<UUID, Tier> en : new HashMap<>(loaded).entrySet()) {
            Entity e = Bukkit.getEntity(en.getKey());
            if (e == null || !e.isValid()) {
                loaded.remove(en.getKey());
                continue;
            }
            Location c = e.getLocation().add(0, 1.2, 0);
            boolean near = false;
            for (Player p : e.getWorld().getPlayers()) {
                if (p.getLocation().distanceSquared(c) < 48 * 48) {
                    near = true;
                    break;
                }
            }
            if (!near) continue;
            Particle part = switch (en.getValue()) {
                case SILVER -> Particle.END_ROD;
                case GOLD -> Particle.WAX_ON;
                case PRISM -> Particle.GLOW;
            };
            e.getWorld().spawnParticle(part, c, 6, 0.8, 0.8, 0.8, 0.01);
            if (en.getValue() == Tier.PRISM) e.getWorld().spawnParticle(Particle.END_ROD, c, 3, 1.2, 1.2, 1.2, 0.02);
        }
    }

    /** /증강 제단 에 쓸 안내 문구. */
    public List<String> describeNearest(Player p) {
        List<String> out = new ArrayList<>();
        Location l = p.getLocation();
        for (Tier t : Tier.values()) {
            List<Info> list = nearestUsable(p, t, 3);
            int left = mode() == Mode.GLOBAL ? remaining(p.getWorld(), t) : -1;
            out.add(t.wrap(t.korean + " 제단") + (left >= 0 ? " <dark_gray>(남은 " + left + "곳)" : ""));
            if (list.isEmpty()) out.add("  <gray>남은 제단이 없습니다");
            for (Info i : list) {
                int dx = (int) Math.round(i.x() - l.getX()), dz = (int) Math.round(i.z() - l.getZ());
                out.add("  <white>" + MapBuilder.dir(dx, dz) + " " + (int) Math.round(Math.hypot(dx, dz)) + "m <dark_gray>("
                        + (int) i.x() + ", " + (int) i.y() + ", " + (int) i.z() + ")");
            }
        }
        return out;
    }
}
