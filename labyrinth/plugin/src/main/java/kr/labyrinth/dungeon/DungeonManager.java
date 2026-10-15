package kr.labyrinth.dungeon;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.dungeon.gen.BlockPlacer;
import kr.labyrinth.dungeon.rooms.Room;
import kr.labyrinth.party.Party;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockFadeEvent;
import org.bukkit.event.block.BlockFormEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockGrowEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.BlockSpreadEvent;
import org.bukkit.event.block.LeavesDecayEvent;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.entity.ProjectileHitEvent;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * DungeonService 구현: 공허 월드, 인스턴스(Run) 관리, 입장 절차, 사망·재접속·퇴장, 블록 보호(미궁 월드만).
 * 모든 리스너는 미궁 월드 여부를 먼저 확인한다 (ARCHITECTURE §7).
 */
public final class DungeonManager implements DungeonService, Listener {

    private final Services services;
    private DungeonConfig config = DungeonConfig.defaults();
    private LabyrinthWorld labWorld;
    private InstanceAllocator allocator;
    private BlockPlacer placer;
    private final Map<String, Run> runs = new LinkedHashMap<>();
    private final Map<UUID, Run> byPlayer = new ConcurrentHashMap<>();
    private final Set<Particle> badParticles = ConcurrentHashMap.newKeySet();
    private final Map<UUID, Long> enterCooldown = new HashMap<>();
    private BukkitTask ticker;
    private long tick;
    private int runSeq;

    public DungeonManager(Services services) {
        this.services = services;
    }

    // ── 수명 ──────────────────────────────────────────────────────────────

    void enable() {
        config = DungeonConfig.load(services.plugin());
        labWorld = new LabyrinthWorld(services.plugin(), services.settings().worldName());
        labWorld.loadOrCreate(config.resetWorldOnStartup());
        allocator = new InstanceAllocator(config.maxInstances() + 256);
        for (int s : labWorld.dirtySlots()) allocator.reserve(s);
        placer = new BlockPlacer(services.plugin(), config.blocksPerTick());
        placer.start();
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        ticker = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 2L, 2L);
        if (labWorld.world() == null) Log.warn("미궁 월드를 만들지 못했습니다 — 입장이 불가능합니다.");
        else Log.info("미궁 월드 준비: " + labWorld.world().getName() + (labWorld.dirtySlots().isEmpty() ? ""
                : " (정리 안 된 슬롯 " + labWorld.dirtySlots().size() + "개 건너뜀)"));
        // 미궁 월드에 남아 있던 플레이어 (리로드 등)
        for (Player p : Bukkit.getOnlinePlayers()) if (isLabyrinthWorld(p.getWorld())) recoverStranded(p);
    }

    void reload() {
        config = DungeonConfig.load(services.plugin());
        if (placer != null) placer.budget(config.blocksPerTick());
    }

    void disable() {
        SelfTest.abort();
        if (ticker != null) ticker.cancel();
        HandlerList.unregisterAll(this);
        for (Run r : new ArrayList<>(runs.values())) {
            for (UUID u : r.members()) {
                Player p = Bukkit.getPlayer(u);
                if (p != null && p.isOnline() && r.isMember(u)) {
                    r.restore(p);
                    Text.send(p, "<gray>서버 정비로 미궁에서 귀환했습니다.");
                }
            }
            r.destroyFloors(true, () -> {});
            if (labWorld != null) labWorld.markClean(r.slot());
        }
        runs.clear();
        byPlayer.clear();
        if (placer != null) placer.stop();
    }

    private void tickAll() {
        tick += 2;
        for (Run r : new ArrayList<>(runs.values())) {
            try {
                r.tick(tick);
            } catch (Throwable t) {
                Log.error("인스턴스 틱 오류 (" + r.id() + ")", t);
            }
        }
    }

    // ── 접근자 ────────────────────────────────────────────────────────────

    public Services services() { return services; }
    public DungeonConfig config() { return config; }
    public BlockPlacer placer() { return placer; }

    @Override
    public World world() { return labWorld == null ? null : labWorld.world(); }

    @Override
    public boolean isLabyrinthWorld(World w) {
        return w != null && w.getName().equals(services.settings().worldName());
    }

    @Override
    public Optional<InstanceContext> currentInstance(Player player) {
        Run r = byPlayer.get(player.getUniqueId());
        if (r == null || r.current() == null) return Optional.empty();
        return Optional.of(r.current().ctx());
    }

    @Override
    public Collection<InstanceContext> instances() {
        List<InstanceContext> out = new ArrayList<>();
        for (Run r : runs.values()) if (r.current() != null) out.add(r.current().ctx());
        return out;
    }

    public Collection<Run> runs() { return runs.values(); }

    public Run runOf(Player p) { return byPlayer.get(p.getUniqueId()); }

    void unbind(UUID u) { byPlayer.remove(u); }

    /** 쓰러짐 = 인스턴스의 사망자 목록 기준 (게임 모드만 보면 관전으로 구경하는 관리자도 쓰러진 것으로 보임). */
    @Override
    public boolean isDowned(Player player) {
        Run r = byPlayer.get(player.getUniqueId());
        if (r == null) return DungeonService.super.isDowned(player);
        return r.state(player.getUniqueId()) == Run.MemberState.DEAD && isLabyrinthWorld(player.getWorld());
    }

    /** 사제 부활의 성가 등: 인스턴스 사망자 목록·전멸 판정까지 함께 갱신하고 서바이벌로 일으킨다. */
    @Override
    public boolean revive(Player player, Location at, double hpRatio) {
        Run r = byPlayer.get(player.getUniqueId());
        if (r == null) return DungeonService.super.revive(player, at, hpRatio);
        if (r.ending() || !isDowned(player)) return false;
        r.revive(player, at, Math.max(0.05, Math.min(1.0, hpRatio)));
        return true;
    }

    // ── 관리자 자가 진단(SelfTest) 전용: 임시 슬롯 (인스턴스 목록에 안 들어감) ──
    int allocateTestSlot() {
        if (allocator == null || labWorld == null) return -1;
        int s = allocator.allocate();
        if (s >= 0) labWorld.markDirty(s);
        return s;
    }

    void releaseTestSlot(int s) {
        if (s < 0) return;
        allocator.release(s);
        labWorld.markClean(s);
    }

    int nextRunSeq() { return ++runSeq; }

    Particle particle(String name) {
        if (name == null || name.isBlank()) return null;
        try {
            Particle p = Particle.valueOf(name.trim().toUpperCase(java.util.Locale.ROOT));
            if (badParticles.contains(p) || p.getDataType() != Void.class) return null;
            return p;
        } catch (IllegalArgumentException e) {
            Log.warnOnce("particle:" + name, "[미궁] floors.yml ambient 의 알 수 없는 입자: " + name);
            return null;
        }
    }

    void disableParticle(Particle p) { badParticles.add(p); }

    // ── 입장 ──────────────────────────────────────────────────────────────

    @Override
    public boolean enter(Player leader, int floor) { return enter(leader, floor, false); }

    private boolean enter(Player leader, int floor, boolean admin) {
        Settings s = services.settings();
        if (!s.isDifficultySet()) {
            Text.error(leader, "아직 서버 난이도가 정해지지 않았습니다.");
            if (kr.labyrinth.core.ServerSetup.canSetDifficulty(leader)) services.menus().openSetup(leader);
            return false;
        }
        if (world() == null) {
            Text.error(leader, "미궁 월드가 준비되지 않았습니다. 관리자에게 문의하세요.");
            return false;
        }
        long now = System.currentTimeMillis();
        if (now - enterCooldown.getOrDefault(leader.getUniqueId(), 0L) < 2000) return false;
        enterCooldown.put(leader.getUniqueId(), now);
        if (byPlayer.containsKey(leader.getUniqueId())) {
            Text.error(leader, "이미 미궁 공략 중입니다. <white>/미궁 퇴장</white> 으로 먼저 나오세요.");
            return false;
        }
        Optional<Party> party = services.party().partyOf(leader);
        if (!admin && party.isPresent() && !party.get().isLeader(leader.getUniqueId())) {
            Text.error(leader, "파티 입장은 파티장만 시작할 수 있습니다.");
            return false;
        }
        List<Player> members = admin ? new ArrayList<>(List.of(leader)) : new ArrayList<>(services.party().onlineMembers(leader));
        if (!members.contains(leader)) members.add(0, leader);
        int maxFloor = services.content().maxFloor();
        if (floor < 1 || floor > maxFloor || services.content().floor(floor) == null) {
            Text.error(leader, "지하 1~" + maxFloor + "층 중에서 고르세요.");
            return false;
        }
        // 파티원 전원: 다른 인스턴스 X, 입구 근처, 해금층
        Location gather = entranceLocation();
        double radius = s.entrance().radius();
        int minUnlocked = Integer.MAX_VALUE;
        String lowest = null;
        List<String> problems = new ArrayList<>();
        for (Player m : members) {
            if (byPlayer.containsKey(m.getUniqueId())) problems.add(m.getName() + " (이미 미궁 안)");
            else if (isLabyrinthWorld(m.getWorld())) problems.add(m.getName() + " (미궁 월드에 있음)");
            else if (m.isDead()) problems.add(m.getName() + " (사망 상태)");
            if (config.requireNearEntrance() && !admin) {
                Location ref = gather != null ? gather : leader.getLocation();
                if (!m.getWorld().equals(ref.getWorld()) || m.getLocation().distanceSquared(ref) > radius * radius) {
                    problems.add(m.getName() + " (" + (gather != null ? "입구" : "파티장") + "에서 " + (int) radius + "칸 밖)");
                }
            }
            int u = services.data().get(m).unlockedFloor();
            if (u < minUnlocked) {
                minUnlocked = u;
                lowest = m.getName();
            }
        }
        if (!problems.isEmpty()) {
            Text.error(leader, "입장할 수 없습니다: <white>" + Text.escape(String.join(", ", problems)));
            return false;
        }
        if (floor > minUnlocked && !admin) {
            Text.error(leader, "지하 " + floor + "층은 아직 잠겨 있습니다. " + (members.size() > 1
                    ? "파티원 중 최소 해금층은 <white>" + minUnlocked + "층</white> (" + Text.escape(lowest) + ")"
                    : "지금은 <white>" + minUnlocked + "층</white>까지 들어갈 수 있습니다."));
            return false;
        }
        if (members.size() > s.party().maxSize()) {
            Text.error(leader, "파티 인원이 최대 " + s.party().maxSize() + "명을 넘습니다.");
            return false;
        }
        int slot = allocator.allocate();
        if (slot < 0 || slot >= config.maxInstances() + 256) {
            Text.error(leader, "지금은 미궁이 가득 찼습니다. 잠시 뒤에 다시 시도하세요.");
            return false;
        }
        if (runs.size() >= config.maxInstances()) {
            allocator.release(slot);
            Text.error(leader, "동시에 열 수 있는 미궁 수(" + config.maxInstances() + ")를 넘었습니다. 잠시 뒤에 다시 시도하세요.");
            return false;
        }
        FloorDef def = services.content().floor(floor);
        Difficulty diff = s.difficulty();
        List<UUID> ids = new ArrayList<>();
        for (Player m : members) ids.add(m.getUniqueId());
        String id = "r" + (++runSeq) + "s" + slot;
        Run run = new Run(this, id, slot, diff, s.party(), ids, admin);
        runs.put(id, run);
        for (UUID u : ids) byPlayer.put(u, run);
        labWorld.markDirty(slot);
        for (Player m : members) {
            Text.send(m, "<gradient:#c9a2ff:#7fd8ff>미궁 라비린스</gradient> <gray>지하 <white>" + floor + "층</white> 입장 준비 중... (난이도 "
                    + diff.name() + ", " + members.size() + "명)");
        }
        run.begin(floor, members);
        return true;
    }

    /** 입구 위치 (config entrance, 없으면 null). */
    public Location entranceLocation() {
        Settings.Entrance e = services.settings().entrance();
        return e.isSet() ? e.toLocation() : null;
    }

    /** 귀환 위치가 없을 때: 입구 → 메인 월드 스폰. */
    Location fallbackReturn(Player p) {
        Location e = entranceLocation();
        if (e != null) return e;
        try {
            Object raw = services.data().get(p).ext().get("dungeon.return");
            Location l = raw == null ? null : deserialize(String.valueOf(raw));
            if (l != null && !isLabyrinthWorld(l.getWorld())) return l;
        } catch (Throwable ignored) {
            // 잘못된 기록
        }
        World main = Bukkit.getWorlds().get(0);
        return main.getSpawnLocation();
    }

    @Override
    public void leave(Player player) {
        Run r = byPlayer.get(player.getUniqueId());
        if (r != null) {
            r.leave(player, false);
            Text.send(player, "<gray>미궁에서 귀환했습니다.");
            return;
        }
        if (isLabyrinthWorld(player.getWorld())) {
            recoverStranded(player);
            Text.send(player, "<gray>미궁 밖으로 나왔습니다.");
            return;
        }
        Text.error(player, "미궁 안에 있지 않습니다.");
    }

    @Override
    public void endInstance(String instanceId) {
        Run target = runs.get(instanceId);
        if (target == null) {
            for (Run r : runs.values()) {
                if (r.current() != null && r.current().ctx().id().equals(instanceId)) target = r;
            }
        }
        if (target != null) target.end(false, "<gray>관리자가 미궁 공략을 종료했습니다.");
    }

    /** Run 종료 후 정리 (블록·슬롯). */
    void finish(Run run, boolean sync) {
        if (!runs.containsKey(run.id())) return;
        runs.remove(run.id());
        for (UUID u : run.members()) if (byPlayer.get(u) == run) byPlayer.remove(u);
        run.destroyFloors(sync, () -> {
            allocator.release(run.slot());
            labWorld.markClean(run.slot());
        });
    }

    /** 인스턴스 없이 미궁 월드에 있는 플레이어 → 원래 자리로. */
    void recoverStranded(Player p) {
        PlayerData d = services.data().get(p);
        Object gm = d.ext().remove("dungeon.gamemode");
        Object back = d.ext().remove("dungeon.return");
        d.markDirty();
        GameMode mode = GameMode.SURVIVAL;
        if (gm != null) {
            try {
                mode = GameMode.valueOf(String.valueOf(gm));
            } catch (IllegalArgumentException ignored) {
                // 기본값
            }
        }
        if (p.getGameMode() == GameMode.SPECTATOR || gm != null) p.setGameMode(mode);
        Location to = back == null ? null : deserialize(String.valueOf(back));
        if (to == null || isLabyrinthWorld(to.getWorld())) to = fallbackReturn(p);
        p.setFallDistance(0);
        p.teleport(to);
    }

    static String serialize(Location l) {
        return l.getWorld().getName() + "," + l.getX() + "," + l.getY() + "," + l.getZ() + "," + l.getYaw() + "," + l.getPitch();
    }

    static Location deserialize(String s) {
        try {
            String[] a = s.split(",");
            World w = Bukkit.getWorld(a[0]);
            if (w == null) return null;
            return new Location(w, Double.parseDouble(a[1]), Double.parseDouble(a[2]), Double.parseDouble(a[3]),
                    Float.parseFloat(a[4]), Float.parseFloat(a[5]));
        } catch (Exception e) {
            return null;
        }
    }

    /** 관리자 테스트: 혼자, 해금·입구 거리 무시하고 층 입장 (/labadmin tpfloor). */
    public boolean adminEnter(Player p, int floor) {
        enterCooldown.remove(p.getUniqueId());
        return enter(p, floor, true);
    }

    // ── 이벤트 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent e) {
        Player p = e.getPlayer();
        if (!isLabyrinthWorld(p.getWorld())) return;
        Run r = byPlayer.get(p.getUniqueId());
        if (r == null || !r.isAlive(p) || r.ending()) {
            e.setKeepInventory(true);
            e.getDrops().clear();
            e.setKeepLevel(true);
            e.setDroppedExp(0);
            return;
        }
        e.setCancelled(true);
        services.stats().setHp(p, services.stats().maxHp(p));
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (p.isOnline() && r.isAlive(p) && !r.ending()) r.onMemberDeath(p);
        });
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onRespawn(PlayerRespawnEvent e) {
        Player p = e.getPlayer();
        if (!isLabyrinthWorld(p.getWorld()) && !isLabyrinthWorld(e.getRespawnLocation().getWorld())) return;
        Run r = byPlayer.get(p.getUniqueId());
        if (r == null) e.setRespawnLocation(fallbackReturn(p));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        Run r = byPlayer.get(p.getUniqueId());
        if (r == null) return;
        for (Player o : r.onlineMembers()) {
            if (!o.equals(p)) Text.send(o, "<gray>" + Text.escape(p.getName()) + " 님의 연결이 끊겼습니다. (다시 접속하면 합류)");
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Run r = byPlayer.get(p.getUniqueId());
        if (r != null && r.isMember(p.getUniqueId()) && !r.ending()) {
            Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
                if (!p.isOnline()) return;
                if (isLabyrinthWorld(p.getWorld())) {
                    r.rejoin(p);
                    Text.send(p, "<gray>미궁 공략에 다시 합류했습니다.");
                } else {
                    r.leave(p, true);
                }
            }, 5L);
            return;
        }
        if (isLabyrinthWorld(p.getWorld())) {
            Bukkit.getScheduler().runTask(services.plugin(), () -> {
                if (p.isOnline() && isLabyrinthWorld(p.getWorld()) && !byPlayer.containsKey(p.getUniqueId())) {
                    recoverStranded(p);
                    Text.send(p, "<gray>진행 중이던 미궁이 닫혀 입구로 돌아왔습니다.");
                }
            });
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        Player p = e.getPlayer();
        if (e.getTo() == null) return;
        boolean toLab = isLabyrinthWorld(e.getTo().getWorld());
        boolean fromLab = isLabyrinthWorld(e.getFrom().getWorld());
        Run r = byPlayer.get(p.getUniqueId());
        // 미궁 밖으로 다른 방법(명령/진주 등)으로 나가면 공략에서 이탈 처리
        if (fromLab && !toLab && r != null && r.isMember(p.getUniqueId()) && !r.ending()) {
            Bukkit.getScheduler().runTask(services.plugin(), () -> {
                if (byPlayer.get(p.getUniqueId()) == r) r.leave(p, false);
            });
        }
        // 관전자가 관전 메뉴로 다른 곳에 가는 것 방지
        if (toLab && r != null && e.getCause() == PlayerTeleportEvent.TeleportCause.SPECTATE) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        Block b = e.getClickedBlock();
        if (b == null || !isLabyrinthWorld(b.getWorld())) return;
        Player p = e.getPlayer();
        Run r = byPlayer.get(p.getUniqueId());
        if (r == null || r.current() == null || !r.isAlive(p)) {
            if (p.getGameMode() != GameMode.CREATIVE) e.setCancelled(true);
            return;
        }
        FloorState fs = r.floorOf(p);
        if (fs == null) fs = r.current();
        boolean offHand = e.getHand() == org.bukkit.inventory.EquipmentSlot.OFF_HAND;
        // 금 간 벽 (비밀 통로): 우클릭하거나 때리면 무너진다
        if (!offHand && (e.getAction() == Action.LEFT_CLICK_BLOCK || e.getAction() == Action.RIGHT_CLICK_BLOCK)
                && fs.secrets().tryOpen(p, b)) {
            e.setCancelled(true);
            return;
        }
        // 미로 보물 상자·금고 문 (개인 루팅·열쇠)
        if (offHand ? fs.treasures().owns(b) : fs.treasures().onInteract(p, b, e.getAction())) {
            e.setCancelled(true);
            return;
        }
        for (Room room : fs.rooms()) {
            if (offHand) {
                // 보조손 이벤트는 처리하지 않고 막기만 (주 손에서 이미 처리 — 두 번 눌림 방지)
                if (room.containsBlock(b) && b.getType().isInteractable()) e.setCancelled(true);
                continue;
            }
            if (!room.containsBlock(b)) continue;
            if (room.onInteract(p, b, e.getAction())) {
                e.setCancelled(true);
                return;
            }
        }
        // 그 밖의 미궁 블록 상호작용(상자·문·레버·모루 등)은 막는다 (아이템 사용은 허용)
        if (e.getAction() == Action.RIGHT_CLICK_BLOCK && b.getType().isInteractable() && p.getGameMode() != GameMode.CREATIVE) {
            e.setUseInteractedBlock(org.bukkit.event.Event.Result.DENY);
        }
        if (e.getAction() == Action.PHYSICAL) e.setCancelled(true);
    }

    /** 지도(빈 지도·지도)를 들고 우클릭 → 탐험 지도. */
    @EventHandler(priority = EventPriority.LOW)
    public void onMapItem(PlayerInteractEvent e) {
        if (e.getHand() != org.bukkit.inventory.EquipmentSlot.HAND) return;
        if (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        org.bukkit.inventory.ItemStack it = e.getItem();
        if (it == null || (it.getType() != org.bukkit.Material.MAP && it.getType() != org.bukkit.Material.FILLED_MAP)) return;
        if (!isLabyrinthWorld(e.getPlayer().getWorld()) || !byPlayer.containsKey(e.getPlayer().getUniqueId())) return;
        if (showMap(e.getPlayer())) e.setCancelled(true);
    }

    @Override
    public boolean showMap(Player p) {
        Run r = byPlayer.get(p.getUniqueId());
        FloorState fs = r == null ? null : r.floorOf(p);
        if (fs == null && r != null) fs = r.current();
        if (fs == null || !fs.ready()) {
            Text.error(p, "탐험 지도는 미궁 안에서만 볼 수 있습니다.");
            return false;
        }
        ExplorationMap.show(fs, p);
        return true;
    }

    @EventHandler(ignoreCancelled = true)
    public void onProjectile(ProjectileHitEvent e) {
        Block b = e.getHitBlock();
        if (b == null || !isLabyrinthWorld(b.getWorld())) return;
        Projectile proj = e.getEntity();
        if (!(proj.getShooter() instanceof Player p)) return;
        Run r = byPlayer.get(p.getUniqueId());
        if (r == null || r.current() == null) return;
        if (r.current().secrets().tryOpen(p, b)) return;
        for (Room room : r.current().rooms()) {
            if (room.containsBlock(b)) {
                room.onProjectileHit(p, b);
                break;
            }
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent e) {
        if (isLabyrinthWorld(e.getBlock().getWorld()) && !(e.getPlayer().getGameMode() == GameMode.CREATIVE
                && e.getPlayer().hasPermission(CommandService.PERM_ADMIN) && !byPlayer.containsKey(e.getPlayer().getUniqueId()))) {
            e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) {
        if (isLabyrinthWorld(e.getBlock().getWorld()) && !(e.getPlayer().getGameMode() == GameMode.CREATIVE
                && e.getPlayer().hasPermission(CommandService.PERM_ADMIN) && !byPlayer.containsKey(e.getPlayer().getUniqueId()))) {
            e.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onBucket(PlayerBucketEmptyEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onBucketFill(PlayerBucketFillEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onFlow(BlockFromToEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onBurn(BlockBurnEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onSpread(BlockSpreadEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onFade(BlockFadeEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onForm(BlockFormEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onGrow(BlockGrowEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onDecay(LeavesDecayEvent e) { if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true); }

    @EventHandler(ignoreCancelled = true)
    public void onEntityBlock(EntityChangeBlockEvent e) {
        if (isLabyrinthWorld(e.getBlock().getWorld())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent e) { if (isLabyrinthWorld(e.getLocation().getWorld())) e.blockList().clear(); }

    @EventHandler(ignoreCancelled = true)
    public void onSpawn(CreatureSpawnEvent e) {
        if (!isLabyrinthWorld(e.getLocation().getWorld())) return;
        switch (e.getSpawnReason()) {
            case NATURAL, SPAWNER, PATROL, REINFORCEMENTS, VILLAGE_INVASION, TRAP, JOCKEY, MOUNT, CHUNK_GEN, RAID, NETHER_PORTAL,
                 ENDER_PEARL, SILVERFISH_BLOCK, LIGHTNING -> e.setCancelled(true);
            default -> { }
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onCampfire(EntityDamageEvent e) {
        if (e.getCause() == EntityDamageEvent.DamageCause.CAMPFIRE && isLabyrinthWorld(e.getEntity().getWorld())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onSpectatorCommand(PlayerCommandPreprocessEvent e) {
        // 관전 중 /spectate 류로 다른 인스턴스를 엿보는 것 방지는 SPECTATE 텔레포트 취소로 처리. 여기선 안내만.
        Player p = e.getPlayer();
        if (!isLabyrinthWorld(p.getWorld())) return;
        String msg = e.getMessage().toLowerCase(java.util.Locale.ROOT);
        if ((msg.startsWith("/spawn") || msg.startsWith("/home")) && byPlayer.containsKey(p.getUniqueId())) {
            Text.send(p, "<gray>미궁에서 나가려면 <white>/미궁 퇴장</white> 을 쓰세요. (진행이 사라집니다)");
        }
    }

    public Map<String, Run> runMap() { return runs; }
}
