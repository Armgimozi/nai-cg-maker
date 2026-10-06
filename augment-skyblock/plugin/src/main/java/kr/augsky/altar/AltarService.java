package kr.augsky.altar;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.PlayerData;
import kr.augsky.augment.Tier;
import kr.augsky.util.Fx;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.block.Block;
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
import org.bukkit.util.Transformation;
import org.joml.Vector3f;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 제단: 맵 곳곳의 상호작용 엔티티. 누르면 제단 화면을 연다.
 * 제단은 일회용이다 (config altar.single-use: global = 한 명이 쓰면 사라짐, player = 사람마다 한 번, off = 무제한).
 * 어디에 어떤 제단이 있는지는 월드 폴더의 augsky-altars.yml 에 기록해 두고, 맵과 함께 배포된다.
 * 하늘 네더의 제단은 그 월드 폴더에 따로 기록하고, 남은 수는 하늘과 합쳐 센다 (realm).
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

    private final AugSky plugin;
    private final Map<UUID, Tier> loaded = new HashMap<>();
    /** 제단(상호작용 엔티티) → 그 제단의 보석 (사람마다 한 번 모드에서 쓴 사람에게만 감춘다) */
    private final Map<UUID, UUID> crystals = new HashMap<>();
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

    /** 허문 제단을 기록에서 뺀다 (같은 자리에 다시 세울 때. 안 빼면 옛 제단이 남은 수에 그대로 남는다). */
    public void forget(UUID id, World w) {
        loaded.remove(id);
        guarded.remove(id);
        crystals.remove(id);
        if (reg(w).remove(id) != null) save(w);
    }

    /** 이 월드 하나의 제단 기록 (맵생성 전 확인용). 플레이어에게 보여 줄 수는 realm 으로 센다. */
    public List<Info> all(World w) {
        return new ArrayList<>(reg(w).values());
    }

    /**
     * w 와 함께 세는 월드들: 하늘(home)과, 하늘이 서버의 첫 월드면 그 하늘 네더.
     * 제단은 두 월드에 흩어져 있어도 한 맵이라 남은 수는 합쳐서 보여 준다.
     */
    public List<World> realm(World w) {
        World home = plugin.home(w);
        List<World> out = new ArrayList<>(List.of(home));
        World sky = plugin.nether() == null ? null : plugin.nether().world();
        if (sky != null && !sky.equals(home) && home.equals(Bukkit.getWorlds().get(0))) out.add(sky);
        return out;
    }

    /** 이 플레이어가 아직 쓸 수 있는 그 등급 제단 수, 하늘과 하늘 네더를 합쳐서 (/증강 제단, 위치는 알려 주지 않는다). */
    public int usableCount(Player p, Tier t) {
        PlayerData d = plugin.augments().data(p);
        int n = 0;
        for (World w : realm(p.getWorld())) for (Info i : reg(w).values()) if (i.tier() == t && usable(i, d)) n++;
        return n;
    }

    /** 아직 힘이 남은 그 등급 제단 수, w 가 속한 하늘과 하늘 네더를 합쳐서. */
    public int remaining(World w, Tier tier) {
        int n = 0;
        for (World rw : realm(w)) for (Info i : reg(rw).values()) if (i.tier() == tier && !i.used()) n++;
        return n;
    }

    /** 제단 기록이 있는 월드 (엔티티가 불려 있지 않아도 찾게 near 의 하늘과 하늘 네더를 다 본다). */
    private World worldOf(UUID altarId, World near) {
        Entity en = Bukkit.getEntity(altarId);
        if (en != null) return en.getWorld();
        for (World w : realm(near)) if (reg(w).containsKey(altarId)) return w;
        return near;
    }

    /** 제물을 받기 직전에 다시 확인한다 (두 사람이 같은 제단 창을 동시에 연 경우). */
    public boolean isUsable(UUID altarId, Player p) {
        if (altarId == null) return true;
        PlayerData d = plugin.augments().data(p);
        return switch (mode()) {
            case GLOBAL -> {
                Entity en = Bukkit.getEntity(altarId);
                if (en != null && en.getPersistentDataContainer().has(Keys.USED)) yield false;
                Info i = reg(worldOf(altarId, p.getWorld())).get(altarId);
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
        // 예전 맵의 빛기둥과 안내 글자는 보이는 대로 지운다
        if (e instanceof BlockDisplay && pdc.has(Keys.BEAM)) {
            e.remove();
            return;
        }
        if (e instanceof TextDisplay && pdc.has(Keys.MAP_PART)) {
            e.remove();
            return;
        }
        if (e instanceof BlockDisplay bd && pdc.has(Keys.MAP_PART) && bd.getViewRange() > 1f) bd.setViewRange(1f);
        String of = pdc.get(Keys.ALTAR_OF, PersistentDataType.STRING);
        if (e instanceof BlockDisplay && of != null) {
            try {
                crystals.put(UUID.fromString(of), e.getUniqueId());
            } catch (IllegalArgumentException ignored) {
            }
        }
        if (e instanceof Interaction) {
            Tier t = Tier.parse(pdc.get(Keys.ALTAR, PersistentDataType.STRING));
            if (t != null) {
                guarded.put(e.getUniqueId(), e.getLocation());
                if (!pdc.has(Keys.USED)) loaded.put(e.getUniqueId(), t);
                // 예전 맵처럼 기록이 없는 제단도 처음 보이면 기록해 둔다
                Map<UUID, Info> m = reg(e.getWorld());
                Info known = m.get(e.getUniqueId());
                if (mode() == Mode.GLOBAL && (pdc.has(Keys.USED) || known != null && known.used())) {
                    // 쓴 기록은 있는데 엔티티 표시가 저장되기 전에 서버가 꺼진 경우나 예전 판에서 쓴 제단: 다시 힘을 다한 모습으로
                    Bukkit.getScheduler().runTask(plugin, () -> {
                        if (e.isValid()) markUsed(e, t);
                    });
                }
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
            loaded.remove(en.getUniqueId());
            crystals.remove(en.getUniqueId());
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
        // 서버가 갑자기 꺼지면 엔티티의 표시(USED)는 저장되지 않았을 수 있으므로 월드 폴더의 기록도 본다
        boolean used = !isUsable(en.getUniqueId(), p);
        if (used) {
            en.getWorld().spawnParticle(Particle.SMOKE, en.getLocation().add(0, 1.5, 0), 20, 0.4, 0.4, 0.4, 0.01);
            Fx.sound(en.getLocation(), "block.beacon.deactivate", 0.6f, 1.6f);
            p.sendMessage(Text.mm(mode == Mode.GLOBAL
                    ? "<gray>이 " + t.korean + " 제단은 이미 힘을 다했습니다. 다른 제단을 찾아보세요."
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
            if (en != null) dimFor(p, en);
            return;
        }
        Tier tier = null;
        World w = worldOf(altarId, p.getWorld());
        Map<UUID, Info> m = reg(w);
        Info old = m.get(altarId);
        if (old != null) {
            tier = old.tier();
            m.put(altarId, new Info(old.id(), old.tier(), old.world(), old.x(), old.y(), old.z(), true));
            save(w);
        }
        if (en != null) {
            if (tier == null) tier = Tier.parse(en.getPersistentDataContainer().get(Keys.ALTAR, PersistentDataType.STRING));
            markUsed(en, tier);
            Location c = en.getLocation();
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

    /**
     * 힘을 다한 제단의 모습 (서버 전체에서 한 번 모드): 표시를 남기고, 보석은 어두운 유리가 되어 받침대로 가라앉고,
     * 등불(가운데 단과 네 기둥 꼭대기)은 착색 유리로, 기둥 위 랜턴·엔드 막대기는 없앤다. 글자는 띄우지 않는다.
     */
    private void markUsed(Entity en, Tier tier) {
        en.getPersistentDataContainer().set(Keys.USED, PersistentDataType.BYTE, (byte) 1);
        loaded.remove(en.getUniqueId());
        String id = en.getUniqueId().toString();
        Location c = en.getLocation();
        for (Entity part : c.getWorld().getNearbyEntities(c, 6, 12, 6)) {
            String of = part.getPersistentDataContainer().get(Keys.ALTAR_OF, PersistentDataType.STRING);
            if (!id.equals(of) || !(part instanceof BlockDisplay bd)) continue;
            bd.setBlock(Material.TINTED_GLASS.createBlockData());
            bd.setBrightness(null);
            bd.setInterpolationDelay(0);
            bd.setInterpolationDuration(20);
            Transformation tr = bd.getTransformation();
            bd.setTransformation(new Transformation(new Vector3f(0, -0.9f, 0), tr.getLeftRotation(), tr.getScale(), tr.getRightRotation()));
        }
        World w = c.getWorld();
        for (Lamp l : lamps(c)) {
            Block b = w.getBlockAt(l.x(), l.y(), l.z());
            if (l.light() && (b.getType() == Material.SEA_LANTERN || b.getType() == Material.GLOWSTONE)) b.setType(Material.TINTED_GLASS, false);
            if (!l.light() && (b.getType() == Material.END_ROD || b.getType() == Material.LANTERN)) b.setType(Material.AIR, false);
        }
    }

    /** 제단의 등불 자리: 가운데 단과 네 기둥 꼭대기(light), 그 위 랜턴·엔드 막대기. */
    private record Lamp(int x, int y, int z, boolean light) {}

    private static List<Lamp> lamps(Location hit) {
        int bx = hit.getBlockX(), by = hit.getBlockY() - 2, bz = hit.getBlockZ();
        List<Lamp> out = new ArrayList<>();
        out.add(new Lamp(bx, by + 1, bz, true));
        for (int[] c : new int[][]{{3, 3}, {-3, 3}, {3, -3}, {-3, -3}}) {
            out.add(new Lamp(bx + c[0], by + 4, bz + c[1], true));
            out.add(new Lamp(bx + c[0], by + 5, bz + c[1], false));
        }
        return out;
    }

    /** 사람마다 한 번 모드: 이 제단을 쓴 사람에게만 보석을 감추고 등불을 꺼진 모습으로 보낸다. */
    private void dimFor(Player p, Entity altar) {
        UUID cid = crystals.get(altar.getUniqueId());
        Entity crystal = cid == null ? null : Bukkit.getEntity(cid);
        if (crystal != null && p.canSee(crystal)) p.hideEntity(plugin, crystal);
        World w = altar.getWorld();
        for (Lamp l : lamps(altar.getLocation())) {
            Material m = w.getBlockAt(l.x(), l.y(), l.z()).getType();
            Location at = new Location(w, l.x(), l.y(), l.z());
            if (l.light() && (m == Material.SEA_LANTERN || m == Material.GLOWSTONE)) p.sendBlockChange(at, Material.TINTED_GLASS.createBlockData());
            if (!l.light() && (m == Material.END_ROD || m == Material.LANTERN)) p.sendBlockChange(at, Material.AIR.createBlockData());
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
        // 보스 둥지 결투장: 부술 수 없으니 놓지도 못하게 (놓은 블록이 영영 남지 않게)
        if (plugin.mobs() != null && plugin.mobs().isLairGuarded(e.getBlock().getLocation())) {
            e.setCancelled(true);
            e.getPlayer().sendActionBar(Text.mm("<#ff7070>보스 둥지에는 블록을 놓을 수 없습니다"));
            return;
        }
        // 제단 바닥 위쪽 공간은 비워 둔다 (기둥 가림 방지). 가장자리 다리 연결은 허용
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

    /** 엔드 수정은 블록이 아니라 엔티티라서 따로 막는다 (둥지 흑요석에 놓고 터뜨리면 보스를 공짜로 깎는다). */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPlaceEntity(org.bukkit.event.entity.EntityPlaceEvent e) {
        if (e.getEntityType() != org.bukkit.entity.EntityType.END_CRYSTAL || e.getPlayer() != null && bypass(e.getPlayer())) return;
        if (plugin.mobs() != null && plugin.mobs().isLairGuarded(e.getEntity().getLocation())) {
            e.setCancelled(true);
            if (e.getPlayer() != null) e.getPlayer().sendActionBar(Text.mm("<#ff7070>보스 둥지에는 블록을 놓을 수 없습니다"));
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
        if (tick % 2 != 0) return;
        boolean perPlayer = mode() == Mode.PLAYER;
        // 사람마다 한 번 모드: 5초마다 쓴 사람에게 꺼진 모습을 다시 보낸다 (청크를 다시 받으면 원래대로 보이므로)
        boolean refresh = perPlayer && tick % 10 == 0;
        for (Map.Entry<UUID, Tier> en : new HashMap<>(loaded).entrySet()) {
            Entity e = Bukkit.getEntity(en.getKey());
            if (e == null || !e.isValid()) {
                loaded.remove(en.getKey());
                continue;
            }
            Location c = e.getLocation().add(0, 1.2, 0);
            String id = en.getKey().toString();
            Particle part = switch (en.getValue()) {
                case SILVER -> Particle.END_ROD;
                case GOLD -> Particle.WAX_ON;
                case PRISM -> Particle.GLOW;
            };
            for (Player p : e.getWorld().getPlayers()) {
                if (p.getLocation().distanceSquared(c) >= 48 * 48) continue;
                if (perPlayer && plugin.augments().data(p).usedAltars.contains(id)) {
                    if (refresh) dimFor(p, e);
                    continue;
                }
                p.spawnParticle(part, c, 6, 0.8, 0.8, 0.8, 0.01);
                if (en.getValue() == Tier.PRISM) p.spawnParticle(Particle.END_ROD, c, 3, 1.2, 1.2, 1.2, 0.02);
            }
        }
    }
}
