package kr.labyrinth.village;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Hanging;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockFertilizeEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockPistonExtendEvent;
import org.bukkit.event.block.BlockPistonRetractEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.BlockSpreadEvent;
import org.bukkit.event.block.LeavesDecayEvent;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.hanging.HangingBreakByEntityEvent;
import org.bukkit.event.hanging.HangingPlaceEvent;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.world.StructureGrowEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.scheduler.BukkitTask;

/**
 * 실행 중 마을 (VILLAGE.md §4.3): 주 월드 폴더의 labyrinth-village.yml 을 읽어
 * 월드 적용(NPC·입구·처음 보는 플레이어 텔레포트) · 보호 · 적대 몹 스폰 막기 · 우클릭 메뉴 · 파티클 연출 · /미궁 마을.
 * 야생 막기(월드 경계·마을 월드 스폰, config wild)는 {@link WildService} 가 맡는다 (0.3.5.1).
 * 메타데이터가 없으면 조용히 꺼진다 (로그 1줄).
 */
public final class VillageService implements Listener {

    private static volatile VillageService instance;

    /** 켜져 있으면 서비스, 아니면 null. */
    public static VillageService get() { return instance; }

    /** 이 서버 주 월드에 마을이 있는가. */
    public static boolean present() {
        VillageService s = instance;
        return s != null && s.meta != null;
    }

    /** /미궁 마을 · 메인 메뉴 "마을" 버튼. */
    public static void teleportCommand(Player p) {
        VillageService s = instance;
        if (s == null || s.meta == null) {
            Text.error(p, "이 월드에는 마을이 없습니다 (서버팩의 world 폴더를 쓰세요)");
            return;
        }
        s.teleport(p);
    }

    static final String EXT_SEEN = "village.world";

    private final VillageModule module;
    private VillageMeta meta;
    private World world;
    private final Map<Long, List<VillageMeta.Box>> boxes = new HashMap<>();
    private final Map<String, String> interact = new HashMap<>();
    private final Map<UUID, Long> lastClick = new HashMap<>();
    private final Map<UUID, Long> lastWarn = new HashMap<>();
    private final java.util.Set<String> badFx = new java.util.HashSet<>();
    private BukkitTask fx;
    private long tick;
    private WildService wild;

    VillageService(VillageModule module) { this.module = module; }

    private Services services() { return module.services(); }

    void enable() {
        instance = this;
        load();
        Bukkit.getPluginManager().registerEvents(this, module.plugin());
        fx = Bukkit.getScheduler().runTaskTimer(module.plugin(), this::ambient, 40L, 10L);
        wild = new WildService(module, this);
        wild.enable();
        if (meta != null) Bukkit.getScheduler().runTask(module.plugin(), () -> {
            if (!applyIfNew(false)) wild.refresh("시작");
        });
    }

    void disable() {
        HandlerList.unregisterAll(this);
        if (wild != null) wild.disable();
        if (fx != null) fx.cancel();
        if (instance == this) instance = null;
    }

    /** 야생 막기 (월드 경계 · 스폰). */
    WildService wild() { return wild; }

    // ── 메타데이터 ───────────────────────────────────────────────────────

    static File metaFile(World w) { return new File(w.getWorldFolder(), VillageMeta.FILE); }

    private File appliedFile() { return new File(module.plugin().getDataFolder(), "village-applied.yml"); }

    void load() {
        world = Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0);
        meta = null;
        boxes.clear();
        interact.clear();
        if (world == null) return;
        File f = metaFile(world);
        if (!f.isFile()) {
            Log.info("[마을] 주 월드에 마을 메타데이터(" + VillageMeta.FILE + ")가 없습니다 — 마을 기능 꺼짐 (서버팩의 world 폴더를 쓰면 켜집니다)");
            return;
        }
        try {
            setMeta(VillageMeta.load(f), false);
            Log.info("[마을] " + meta.name + " — 중심 (" + meta.center[0] + ", " + meta.center[2] + "), 조각 " + meta.pieces.size()
                    + "개, NPC " + meta.npcs.size() + "명, 보호 상자 " + meta.protect.size() + "개");
        } catch (Exception e) {
            Log.error("[마을] " + f + " 읽기 실패 — 마을 기능 꺼짐", e);
        }
    }

    /** 새 메타데이터 적용 (build 직후). */
    void setMeta(VillageMeta m, boolean log) {
        meta = m;
        boxes.clear();
        interact.clear();
        for (VillageMeta.Box b : m.protect) {
            for (int cx = b.x0() >> 4; cx <= b.x1() >> 4; cx++) {
                for (int cz = b.z0() >> 4; cz <= b.z1() >> 4; cz++) boxes.computeIfAbsent(Scan.key(cx, cz), k -> new ArrayList<>()).add(b);
            }
        }
        interact.putAll(m.interact);
        if (log) Log.info("[마을] 메타데이터 갱신: 보호 상자 " + m.protect.size() + "개");
        if (log && wild != null) wild.refresh("마을 메타데이터 갱신");
    }

    public VillageMeta meta() { return meta; }

    public World world() { return world; }

    /** 적용 열쇠: 월드 UID + 빌드 id. */
    String applyKey() { return world.getUID() + ":" + meta.villageKey(); }

    String appliedKey() {
        File f = appliedFile();
        if (!f.isFile()) return "";
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        return y.getString("world_uid", "") + ":" + y.getString("build_id", "");
    }

    /** 이 월드를 처음 켰거나 world 폴더가 바뀌었으면 적용. @return 적용했는가 */
    boolean applyIfNew(boolean force) {
        if (meta == null || world == null) return false;
        if (!force && applyKey().equals(appliedKey())) return false;
        apply();
        return true;
    }

    /** NPC 배치 · 입구 설정 · 예전 석문 기록 버리기 · 적용 기록 (VILLAGE.md §4.3). */
    void apply() {
        Services s = services();
        int npcs = 0;
        for (Map.Entry<String, VillageMeta.Pos> e : meta.npcs.entrySet()) {
            try {
                if (s.npcs().place(e.getKey(), loc(e.getValue())) != null || s.content().npcs().containsKey(e.getKey())) npcs++;
            } catch (Throwable t) {
                Log.error("[마을] NPC 배치 실패 (" + e.getKey() + ")", t);
            }
        }
        int forgot = module.forgetOldEntrance();
        VillageMeta.Pos en = meta.entrance;
        if (en != null) {
            s.updateConfig(c -> {
                c.set("entrance.mode", "village");
                c.set("entrance.world", world.getName());
                c.set("entrance.x", en.x());
                c.set("entrance.y", en.y());
                c.set("entrance.z", en.z());
                c.set("entrance.yaw", (double) en.yaw());
                c.set("entrance.pitch", 0.0);
            });
        }
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 — 마을을 적용한 월드 (UID 가 바뀌면 NPC·입구를 다시 적용). 직접 고치지 마세요."));
        y.set("world_uid", world.getUID().toString());
        y.set("build_id", meta.villageKey());
        y.set("village", meta.name);
        y.set("applied_at", java.time.Instant.now().toString());
        try {
            module.plugin().getDataFolder().mkdirs();
            y.save(appliedFile());
        } catch (IOException e) {
            Log.warn("[마을] village-applied.yml 저장 실패: " + e.getMessage());
        }
        for (Player p : Bukkit.getOnlinePlayers()) markSeen(p);
        Log.info("[마을] 월드 적용: NPC " + npcs + "/" + meta.npcs.size() + " · 입구 " + (en == null ? "없음" : "마을 게이트")
                + (forgot > 0 ? " · 예전 석문 기록 " + forgot + "칸 버림(entrance.yml.old)" : ""));
        if (wild != null) wild.refresh("마을 적용");
    }

    Location loc(VillageMeta.Pos p) { return new Location(world, p.x(), p.y(), p.z(), p.yaw(), 0f); }

    public Location spawn() { return meta == null || meta.spawn == null ? null : loc(meta.spawn); }

    private void markSeen(Player p) {
        PlayerData d = services().data().get(p);
        d.ext().put(EXT_SEEN, applyKey());
        d.markDirty();
    }

    // ── 플레이어 ─────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        if (meta == null) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> checkFirstSeen(p), 5L);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorldChange(PlayerChangedWorldEvent e) {
        if (meta == null || !e.getPlayer().getWorld().equals(world)) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> checkFirstSeen(p), 2L);
    }

    /** 이 마을 월드를 처음 보는 기존 플레이어 → 광장으로 (예전 월드 좌표에 서 있다 땅속에 끼는 것 방지). */
    private void checkFirstSeen(Player p) {
        if (meta == null || !p.isOnline()) return;
        if (services().dungeon().isInLabyrinth(p)) return; // 미궁에서 나올 때 다시 확인
        PlayerData d = services().data().get(p);
        String key = applyKey();
        if (key.equals(String.valueOf(d.ext().get(EXT_SEEN)))) return;
        boolean veteran = p.hasPlayedBefore();
        markSeen(p);
        if (!veteran || !p.getWorld().equals(world)) return;
        Location to = spawn();
        if (to == null) return;
        p.setFallDistance(0);
        kr.labyrinth.core.Teleports.to(p, to);
        Text.send(p, "<#ffd36b>" + Text.escape(meta.name) + "</#ffd36b><gray> 이(가) 생겨 광장으로 옮겼습니다. <white>/미궁 마을</white> 로 언제든 돌아올 수 있습니다.");
    }

    /** /미궁 마을. */
    void teleport(Player p) {
        if (!module.teleportCommand() && !p.hasPermission(CommandService.PERM_ADMIN)) {
            Text.error(p, "이 서버에서는 마을 텔레포트를 쓰지 않습니다. (config village.teleport_command)");
            return;
        }
        if (services().dungeon().isInLabyrinth(p) || services().dungeon().currentInstance(p).isPresent()) {
            Text.error(p, "미궁 안에서는 쓸 수 없습니다. 먼저 <white>/미궁 귀환</white>");
            return;
        }
        Location to = spawn();
        if (to == null) {
            Text.error(p, "마을 스폰 위치가 없습니다.");
            return;
        }
        p.setFallDistance(0);
        kr.labyrinth.core.Teleports.to(p, to);
        p.playSound(to, Sound.ENTITY_ENDERMAN_TELEPORT, 0.6f, 1.3f);
        to.getWorld().spawnParticle(Particle.PORTAL, to.clone().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.3);
        Text.send(p, "<#ffd36b>" + Text.escape(meta.name) + "</#ffd36b> <gray>광장으로 왔습니다.");
    }

    // ── 보호 ─────────────────────────────────────────────────────────────

    /** (x, y, z) 가 보호 상자 안인가. */
    public boolean isProtected(Block b) {
        return meta != null && b.getWorld().equals(world) && isProtected(b.getX(), b.getY(), b.getZ());
    }

    boolean isProtected(int x, int y, int z) {
        List<VillageMeta.Box> list = boxes.get(Scan.key(x >> 4, z >> 4));
        if (list == null) return false;
        for (VillageMeta.Box bx : list) if (bx.contains(x, y, z)) return true;
        return false;
    }

    private boolean bypass(Player p) {
        return p.hasPermission(CommandService.PERM_ADMIN) && p.getGameMode() == GameMode.CREATIVE;
    }

    private void warn(Player p) {
        long now = System.currentTimeMillis();
        Long last = lastWarn.get(p.getUniqueId());
        if (last != null && now - last < 2000) return;
        lastWarn.put(p.getUniqueId(), now);
        Text.error(p, "마을은 부수거나 바꿀 수 없습니다.");
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent e) {
        if (!isProtected(e.getBlock()) || bypass(e.getPlayer())) return;
        e.setCancelled(true);
        warn(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) {
        if (!isProtected(e.getBlock()) || bypass(e.getPlayer())) return;
        e.setCancelled(true);
        warn(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBucket(PlayerBucketEmptyEvent e) {
        if (!isProtected(e.getBlock()) || bypass(e.getPlayer())) return;
        e.setCancelled(true);
        warn(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBucketFill(PlayerBucketFillEvent e) {
        if (!isProtected(e.getBlock()) || bypass(e.getPlayer())) return;
        e.setCancelled(true);
        warn(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onHangingPlace(HangingPlaceEvent e) {
        if (!isProtected(e.getBlock()) || (e.getPlayer() != null && bypass(e.getPlayer()))) return;
        e.setCancelled(true);
        if (e.getPlayer() != null) warn(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onHangingBreak(HangingBreakByEntityEvent e) {
        if (!isProtected(e.getEntity().getLocation().getBlock())) return;
        if (e.getRemover() instanceof Player p && bypass(p)) return;
        e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent e) {
        if (meta != null && e.getLocation().getWorld().equals(world)) e.blockList().removeIf(this::isProtected);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent e) {
        if (meta != null && e.getBlock().getWorld().equals(world)) e.blockList().removeIf(this::isProtected);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBurn(BlockBurnEvent e) { if (isProtected(e.getBlock())) e.setCancelled(true); }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent e) {
        if (!isProtected(e.getBlock())) return;
        if (e.getPlayer() != null && bypass(e.getPlayer())) return;
        e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSpread(BlockSpreadEvent e) {
        if (e.getNewState().getType() == Material.FIRE && isProtected(e.getBlock())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPistonExtend(BlockPistonExtendEvent e) {
        if (meta == null || !e.getBlock().getWorld().equals(world)) return;
        if (isProtected(e.getBlock().getRelative(e.getDirection()))) e.setCancelled(true);
        for (Block b : e.getBlocks()) {
            if (isProtected(b) || isProtected(b.getRelative(e.getDirection()))) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPistonRetract(BlockPistonRetractEvent e) {
        if (meta == null || !e.getBlock().getWorld().equals(world)) return;
        for (Block b : e.getBlocks()) {
            if (isProtected(b)) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onEntityBlock(EntityChangeBlockEvent e) {
        if (!isProtected(e.getBlock())) return;
        if (e.getEntity() instanceof Player p && bypass(p)) return;
        e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onFlow(BlockFromToEvent e) {
        if (meta == null || !e.getBlock().getWorld().equals(world)) return;
        boolean from = isProtected(e.getBlock()), to = isProtected(e.getToBlock());
        if (from != to) e.setCancelled(true); // 분수 물이 상자 밖으로 / 바깥 물이 마을 안으로
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onGrow(StructureGrowEvent e) {
        if (meta == null || !e.getWorld().equals(world)) return;
        for (org.bukkit.block.BlockState s : e.getBlocks()) {
            if (isProtected(s.getX(), s.getY(), s.getZ())) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onFertilize(BlockFertilizeEvent e) {
        if (!isProtected(e.getBlock())) return;
        if (e.getPlayer() != null && bypass(e.getPlayer())) return;
        e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDecay(LeavesDecayEvent e) { if (isProtected(e.getBlock())) e.setCancelled(true); }

    // ── 몹 ───────────────────────────────────────────────────────────────

    /**
     * 예전 마을 둘레 적대 막기 (village.block_mob_spawns) — 마을 중심 반경 radius+8 안의 적대 NATURAL·PATROL·REINFORCEMENTS.
     * 0.3.5.1 부터는 wild.spawns(마을 월드 전체)가 이것을 덮는다. wild.spawns: none 이면 이것만 남는다.
     */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSpawn(CreatureSpawnEvent e) {
        if (meta == null || !module.blockMobSpawns() || !WildSpawns.oldVillageBlock(e.getSpawnReason(), e.getEntity() instanceof Enemy)) return;
        if (WildService.pluginTagged(e.getEntity())) return; // 플러그인 몹은 건드리지 않음
        Location l = e.getLocation();
        if (!l.getWorld().equals(world)) return;
        double dx = l.getX() - meta.center[0], dz = l.getZ() - meta.center[2], rr = meta.radius + 8;
        if (dx * dx + dz * dz <= rr * rr) e.setCancelled(true);
    }

    // ── 상호작용 ─────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        if (meta == null || e.getClickedBlock() == null) return;
        Block b = e.getClickedBlock();
        if (!b.getWorld().equals(world)) return;
        Player p = e.getPlayer();
        if (e.getAction() == Action.RIGHT_CLICK_BLOCK) {
            String action = interact.get(VillageMeta.key(b.getX(), b.getY(), b.getZ()));
            if (action != null && !(bypass(p) && p.isSneaking())) {
                e.setCancelled(true);
                if (e.getHand() == EquipmentSlot.HAND) openMenu(p, action);
                return;
            }
        }
        if (!isProtected(b) || bypass(p)) return;
        if (e.getAction() == Action.PHYSICAL) {
            if (b.getType() == Material.FARMLAND || b.getType() == Material.TURTLE_EGG) e.setCancelled(true);
            return;
        }
        if (e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        if (!allowedUse(b.getType())) e.setUseInteractedBlock(Event.Result.DENY);
        ItemStack item = e.getItem();
        if (item != null && changesBlocks(item.getType())) e.setUseItemInHand(Event.Result.DENY);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        Entity en = e.getRightClicked();
        if (!(en instanceof Hanging) && en.getType() != org.bukkit.entity.EntityType.ARMOR_STAND) return;
        if (isProtected(en.getLocation().getBlock()) && !bypass(e.getPlayer())) e.setCancelled(true);
    }

    /** 마을 안에서 그대로 쓸 수 있는 블록: 문·다락문·울타리 문·종·작업대·침대. */
    static boolean allowedUse(Material m) {
        String n = m.name();
        return n.endsWith("_DOOR") || n.endsWith("_TRAPDOOR") || n.endsWith("_FENCE_GATE") || n.endsWith("_BED")
                || m == Material.BELL || m == Material.CRAFTING_TABLE;
    }

    /** 블록을 바꾸는 손 도구 (괭이·삽·도끼·가위·뼛가루·밀랍·부싯돌·양동이·염료 등). */
    static boolean changesBlocks(Material m) {
        String n = m.name();
        return n.endsWith("_HOE") || n.endsWith("_SHOVEL") || n.endsWith("_AXE") || n.endsWith("BUCKET") || n.endsWith("_DYE")
                || m == Material.SHEARS || m == Material.BRUSH || m == Material.BONE_MEAL || m == Material.HONEYCOMB
                || m == Material.FLINT_AND_STEEL || m == Material.FIRE_CHARGE || m == Material.POTION || m == Material.INK_SAC
                || m == Material.GLOW_INK_SAC || m == Material.ARMOR_STAND || m == Material.END_CRYSTAL;
    }

    private void openMenu(Player p, String action) {
        long now = System.currentTimeMillis();
        Long last = lastClick.get(p.getUniqueId());
        if (last != null && now - last < 400) return;
        lastClick.put(p.getUniqueId(), now);
        Services s = services();
        try {
            switch (action.toLowerCase(Locale.ROOT)) {
                case "entrance" -> s.menus().openEntrance(p);
                case "blacksmith" -> s.menus().openBlacksmith(p);
                case "class" -> s.menus().openClass(p);
                case "titles" -> s.menus().openTitles(p);
                case "merchant" -> s.menus().openMerchant(p);
                case kr.labyrinth.mine.MineNames.INTERACT_LIFT -> s.mine().openLift(p);
                case kr.labyrinth.mine.MineNames.INTERACT_OFFICE -> s.mine().openOffice(p);
                case kr.labyrinth.mine.MineNames.INTERACT_SMELTER -> s.crafting().openSmelter(p);
                case kr.labyrinth.mine.MineNames.INTERACT_INFO -> s.mine().openInfo(p);
                default -> s.menus().openMain(p);
            }
            p.playSound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 0.6f, 1.4f);
        } catch (Throwable t) {
            Log.error("[마을] 메뉴 열기 오류 (" + action + ")", t);
            Text.error(p, "메뉴를 여는 중 오류가 발생했습니다.");
        }
    }

    // ── 연출 ─────────────────────────────────────────────────────────────

    private void ambient() {
        if (meta == null || world == null || meta.ambient.isEmpty()) return;
        tick++;
        List<Player> players = world.getPlayers();
        if (players.isEmpty()) return;
        for (VillageMeta.Ambient a : meta.ambient) {
            if (badFx.contains(a.fx()) || !world.isChunkLoaded(a.x() >> 4, a.z() >> 4)) continue;
            Location l = new Location(world, a.x() + 0.5, a.y() + 0.5, a.z() + 0.5);
            boolean near = false;
            for (Player p : players) {
                if (p.getLocation().distanceSquared(l) < 40 * 40) {
                    near = true;
                    break;
                }
            }
            if (!near) continue;
            try {
                switch (a.fx()) {
                    case "portal" -> {
                        world.spawnParticle(Particle.REVERSE_PORTAL, l, 14, 0.8, 1.1, 0.8, 0.02);
                        world.spawnParticle(Particle.PORTAL, l, 10, 0.6, 0.9, 0.6, 0.4);
                        if (tick % 4 == 0) world.spawnParticle(Particle.SOUL, l, 1, 0.6, 0.4, 0.6, 0.01);
                    }
                    case "embers" -> {
                        world.spawnParticle(Particle.SMALL_FLAME, l, 2, 0.3, 0.2, 0.3, 0.01);
                        world.spawnParticle(Particle.SMOKE, l.clone().add(0, 0.4, 0), 2, 0.2, 0.2, 0.2, 0.01);
                        if (tick % 3 == 0) world.spawnParticle(Particle.LAVA, l, 1, 0.2, 0.1, 0.2, 0);
                    }
                    case "fountain" -> {
                        world.spawnParticle(Particle.SPLASH, l, 10, 0.5, 0.2, 0.5, 0.05);
                        world.spawnParticle(Particle.FALLING_WATER, l.clone().add(0, 0.6, 0), 3, 0.4, 0.2, 0.4, 0);
                    }
                    case "smoke" -> {
                        world.spawnParticle(Particle.CAMPFIRE_COSY_SMOKE, l, 0, 0, 0.06, 0, 1);
                        if (tick % 2 == 0) world.spawnParticle(Particle.LARGE_SMOKE, l, 1, 0.2, 0.2, 0.2, 0.01);
                    }
                    default -> {
                        world.spawnParticle(Particle.ENCHANT, l, 8, 0.6, 0.6, 0.6, 0.6);
                        world.spawnParticle(Particle.GLOW, l, 2, 0.5, 0.5, 0.5, 0.01);
                        if (tick % 3 == 0) world.spawnParticle(Particle.END_ROD, l, 1, 0.4, 0.6, 0.4, 0.01);
                    }
                }
            } catch (Throwable t) {
                badFx.add(a.fx());
                Log.warn("[마을] 연출 '" + a.fx() + "' 파티클 오류 — 끔: " + t.getMessage());
            }
        }
    }
}
