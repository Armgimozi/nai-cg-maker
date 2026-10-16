package kr.labyrinth.village;

import com.destroystokyo.paper.event.entity.PreCreatureSpawnEvent;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Teleports;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.WorldBorder;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Boss;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.Tameable;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityTransformEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerPortalEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * 야생 막기 (config wild, 0.3.5.1) — 마을이 있는 주 월드에서만, 마을 기능이 켜져 있을 때만 (VillageService 가 소유).
 * <ul>
 *   <li>월드 경계: 마을 둘레 정사각형 ({@link WildBorder}) 을 주 월드의 바닐라 WorldBorder 로. 우리가 정한 것은
 *       plugins/Labyrinth/wild-border.yml 에 적고, 끌 때는 아직 우리 것일 때만 되돌린다 (관리자의 /worldborder 는 건드리지 않음).
 *       경계 밖에서 발견된 플레이어(접속·리스폰·월드 이동·순간이동·차원문으로 돌아옴·2초마다)는 광장으로.</li>
 *   <li>스폰: 이벤트로만 막는다 ({@link WildSpawns}) — 게임 규칙은 바꾸지 않아, 끄면 바로 바닐라. 켤 때·청크를 불러올 때
 *       바닐라 적대 몹을 치운다 (동물은 그대로). 미궁 월드·네더·엔드·플러그인 엔티티는 건드리지 않는다.</li>
 *   <li>네더·엔드: 막지 않는다 (바닐라 그대로). 차원문·엔드 출구·리스폰으로 주 월드에 돌아올 때 경계 밖이면 광장으로만 옮긴다.</li>
 * </ul>
 */
final class WildService implements Listener {

    private final VillageModule module;
    private final VillageService village;
    private final Map<UUID, Long> lastNote = new HashMap<>();
    private BukkitTask task;
    private WildBorder.Square target;
    /** 마지막 경계 판정 (정보·자가 진단). */
    private WildBorder.Action lastAction = WildBorder.Action.NONE;
    private long blockedSpawns, blockedTransforms, removedExisting, movedPlayers;
    /** 자가 진단이 한 틱 안에서 시험 몹을 들이는 동안 — 정보의 '막은 스폰' 수에 더하지 않음. */
    private boolean selfTest;

    WildService(VillageModule module, VillageService village) {
        this.module = module;
        this.village = village;
    }

    private Services services() { return module.services(); }

    void enable() {
        Bukkit.getPluginManager().registerEvents(this, module.plugin());
        task = Bukkit.getScheduler().runTaskTimer(module.plugin(), this::tick, 40L, 40L);
    }

    void disable() {
        HandlerList.unregisterAll(this);
        if (task != null) task.cancel();
        task = null;
    }

    // ── 상태 ─────────────────────────────────────────────────────────────

    Settings.Wild cfg() { return services().settings().wild(); }

    /** 마을 메타데이터가 있는 주 월드가 있을 때만. */
    boolean active() { return village.meta() != null && village.world() != null; }

    private World main() { return village.world(); }

    private boolean isMain(World w) { return w != null && w.equals(main()); }

    private boolean labyrinth(World w) {
        try {
            return w != null && services().dungeon().isLabyrinthWorld(w);
        } catch (Throwable t) {
            return false;
        }
    }

    Settings.Wild.Spawns spawnMode() { return active() ? cfg().spawns() : Settings.Wild.Spawns.NONE; }

    /** 경계 밖 플레이어를 광장으로 옮기나 (wild.border 켬 — 바닐라 경계가 우리 것이든 관리자 것이든). */
    boolean enforceBorder() { return active() && cfg().border(); }

    /** 관리자 + 크리에이티브·관전 = 경계 검사를 받지 않음 (지형 손보기·점검). */
    static boolean bypass(Player p) {
        return p.hasPermission(CommandService.PERM_ADMIN) && (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR);
    }

    WildBorder.Square target() {
        if (!active()) return null;
        if (target == null) target = WildBorder.compute(village.meta(), cfg().borderMargin());
        return target;
    }

    WildBorder.Square current() {
        WorldBorder b = main().getWorldBorder();
        Location c = b.getCenter();
        return new WildBorder.Square(c.getX(), c.getZ(), b.getSize(), b.getWarningDistance());
    }

    WildBorder.Action lastAction() { return lastAction; }

    private static boolean insideBorder(Location l) {
        return l != null && l.getWorld() != null && l.getWorld().getWorldBorder().isInside(l);
    }

    /** 광장 (마을 스폰 마커). */
    private Location plaza() { return village.spawn(); }

    // ── 켜기 · 다시 읽기 ─────────────────────────────────────────────────

    /** 켤 때 · village apply · labadmin reload · 마을 메타데이터가 바뀔 때. */
    void refresh(String why) {
        if (!active()) return;
        Settings.Wild w = cfg();
        target = WildBorder.compute(village.meta(), w.borderMargin());
        String border;
        try {
            border = applyBorder(w, false);
        } catch (Throwable t) {
            Log.error("[야생] 월드 경계 적용 실패", t);
            border = "오류";
        }
        int removed = 0;
        if (w.spawns() != Settings.Wild.Spawns.NONE) {
            try {
                removed = sweep(main().getEntities());
            } catch (Throwable t) {
                Log.error("[야생] 적대 몹 정리 실패", t);
            }
        }
        Log.info("[야생] " + why + " — 경계 " + border + " · 스폰 막기 " + w.spawns().id()
                + (removed > 0 ? " (있던 적대 몹 " + removed + "마리 치움)" : ""));
        for (Player p : Bukkit.getOnlinePlayers()) check(p);
    }

    // ── 월드 경계 ────────────────────────────────────────────────────────

    private File recordFile() { return new File(module.plugin().getDataFolder(), "wild-border.yml"); }

    WildBorder.Record loadRecord() {
        File f = recordFile();
        if (!f.isFile()) return null;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        if (!main().getUID().toString().equals(y.getString("world_uid", ""))) return null; // 다른 월드의 기록
        if (!y.isConfigurationSection("ours") || !y.isConfigurationSection("previous")) return null;
        return new WildBorder.Record(square(y, "ours"), square(y, "previous"));
    }

    private static WildBorder.Square square(YamlConfiguration y, String k) {
        return new WildBorder.Square(y.getDouble(k + ".x"), y.getDouble(k + ".z"), y.getDouble(k + ".size", WildBorder.VANILLA_SIZE),
                y.getInt(k + ".warning", WildBorder.VANILLA_WARNING));
    }

    private void saveRecord(WildBorder.Record r) {
        File f = recordFile();
        if (r == null) {
            if (f.isFile() && !f.delete()) Log.warn("[야생] " + f.getName() + " 지우기 실패");
            return;
        }
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 — 플러그인이 정한 바닐라 월드 경계 (config wild.border). 직접 고치지 마세요.",
                "ours = 플러그인이 놓은 경계, previous = 그 전 경계 (wild.border: false 로 끄면, 경계가 아직 ours 일 때만 previous 로 되돌림)"));
        y.set("world_uid", main().getUID().toString());
        y.set("world", main().getName());
        put(y, "ours", r.ours());
        put(y, "previous", r.previous());
        y.set("saved_at", java.time.Instant.now().toString());
        try {
            module.plugin().getDataFolder().mkdirs();
            y.save(f);
        } catch (IOException e) {
            Log.warn("[야생] " + f.getName() + " 저장 실패: " + e.getMessage());
        }
    }

    private static void put(YamlConfiguration y, String k, WildBorder.Square s) {
        y.set(k + ".x", s.x());
        y.set(k + ".z", s.z());
        y.set(k + ".size", s.size());
        y.set(k + ".warning", s.warning());
    }

    private void set(WildBorder.Square s) {
        WorldBorder b = main().getWorldBorder();
        b.setCenter(s.x(), s.z());
        b.setSize(s.size());
        b.setWarningDistance(s.warning());
    }

    /** @return 로그용 한 마디 */
    String applyBorder(Settings.Wild w, boolean force) {
        WildBorder.Square cur = current(), tgt = target();
        WildBorder.Record rec = loadRecord();
        WildBorder.Decision d = force ? WildBorder.force(cur, tgt, rec) : WildBorder.decide(w.border(), cur, tgt, rec);
        lastAction = d.action();
        switch (d.action()) {
            case APPLY, RESTORE -> set(d.set());
            default -> { }
        }
        if (d.record() == null ? rec != null : !d.record().equals(rec)) saveRecord(d.record());
        return switch (d.action()) {
            case APPLY -> "정함: " + WildBorder.describe(tgt) + " (마을 가장자리 + " + w.borderMargin() + "칸)";
            case RESTORE -> "끔 — 예전 경계로 되돌림: " + WildBorder.describe(d.set());
            case FORGET -> "끔 — 지금 경계(" + WildBorder.describe(cur) + ")는 관리자가 바꾼 것이라 그대로 둠";
            case ADMIN -> {
                Log.warn("[야생] 관리자가 정한 월드 경계(" + WildBorder.describe(cur) + ")가 있어 그대로 둡니다 — 마을 경계("
                        + WildBorder.describe(tgt) + ")로 바꾸려면 labadmin wild border apply");
                yield "관리자 경계 그대로: " + WildBorder.describe(cur);
            }
            case NONE -> w.border() ? "그대로: " + WildBorder.describe(cur) : "끔";
        };
    }

    // ── 플레이어 ─────────────────────────────────────────────────────────

    private static final String MOVED = "<gray>마을 경계 밖이라 광장으로 옮겼습니다.";

    private void note(Player p, String mm) {
        long now = System.currentTimeMillis();
        Long last = lastNote.get(p.getUniqueId());
        if (last != null && now - last < 3000) return;
        lastNote.put(p.getUniqueId(), now);
        Text.send(p, mm);
    }

    /** 주 월드 경계 밖이면 광장으로. @return 옮겼는가 */
    boolean check(Player p) {
        if (!enforceBorder() || !p.isOnline() || p.isDead() || !isMain(p.getWorld()) || bypass(p)) return false;
        if (insideBorder(p.getLocation())) return false;
        Location to = plaza();
        if (to == null || !insideBorder(to)) return false;
        p.setFallDistance(0);
        if (!Teleports.to(p, to)) return false;
        movedPlayers++;
        note(p, MOVED);
        return true;
    }

    /** 2초마다 — 주 월드 플레이어만, isInside 한 번. */
    private void tick() {
        if (!enforceBorder()) return;
        for (Player p : main().getPlayers()) check(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        if (!enforceBorder()) return;
        Player p = e.getPlayer();
        // 마을의 '처음 보는 월드' 텔레포트(5틱)보다 뒤에
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> check(p), 8L);
    }

    /** 네더·엔드·미궁에서 주 월드로 돌아옴 (차원문·엔드 출구·귀환) — 경계 밖이면 광장. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorldChange(PlayerChangedWorldEvent e) {
        if (!enforceBorder() || !isMain(e.getPlayer().getWorld())) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> check(p), 2L);
    }

    /** 침대·리스폰 정박기·엔드 출구가 주 월드 경계 밖 → 광장 (미궁 월드는 dungeon 이 정한다). */
    @EventHandler(priority = EventPriority.HIGH)
    public void onRespawn(PlayerRespawnEvent e) {
        if (!enforceBorder()) return;
        Player p = e.getPlayer();
        Location to = e.getRespawnLocation();
        if (to == null || !isMain(to.getWorld()) || insideBorder(to) || labyrinth(p.getWorld()) || bypass(p)) return;
        Location plaza = plaza();
        if (plaza == null || !insideBorder(plaza)) return;
        e.setRespawnLocation(plaza);
        movedPlayers++;
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> {
            if (p.isOnline()) note(p, "<gray>다시 태어날 자리가 마을 경계 밖이라 광장에서 일어났습니다.");
        }, 2L);
    }

    /** 주 월드 경계 밖으로 가는 순간이동 → 광장으로 (미궁에서 돌아올 때의 예전 자리 포함). */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        redirect(e);
    }

    /** 네더·엔드에서 주 월드로 나오는 차원문 (PlayerPortalEvent 는 PlayerTeleportEvent 와 핸들러 목록이 따로다). 막지는 않는다. */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onPortal(PlayerPortalEvent e) {
        redirect(e);
    }

    private void redirect(PlayerTeleportEvent e) {
        if (!enforceBorder()) return;
        Location to = e.getTo();
        if (to == null || !isMain(to.getWorld()) || insideBorder(to) || bypass(e.getPlayer())) return;
        Location plaza = plaza();
        if (plaza == null || !insideBorder(plaza)) return;
        e.setTo(plaza);
        movedPlayers++;
        note(e.getPlayer(), MOVED);
    }

    // ── 스폰 ─────────────────────────────────────────────────────────────

    /** 이 플러그인이 태그한 엔티티 (몬스터·보스·NPC·디스플레이·피해 숫자 …) — 키 이름공간 labyrinth. */
    static boolean pluginTagged(Entity e) {
        for (NamespacedKey k : e.getPersistentDataContainer().getKeys()) if (Keys.NS.equals(k.getNamespace())) return true;
        return false;
    }

    /** Paper 가 몹을 만들기 전에 (자연 스폰·생성기) — 싸게 막는다. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPreSpawn(PreCreatureSpawnEvent e) {
        Settings.Wild.Spawns mode = spawnMode();
        if (mode == Settings.Wild.Spawns.NONE || !isMain(e.getSpawnLocation().getWorld())) return;
        Class<? extends Entity> c = e.getType().getEntityClass();
        if (c == null) return;
        if (!WildSpawns.blockSpawn(mode, e.getReason(), Mob.class.isAssignableFrom(c), Enemy.class.isAssignableFrom(c))) return;
        e.setCancelled(true);
        blockedSpawns++;
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSpawn(CreatureSpawnEvent e) {
        Settings.Wild.Spawns mode = spawnMode();
        if (mode == Settings.Wild.Spawns.NONE) return;
        LivingEntity en = e.getEntity();
        if (!isMain(e.getLocation().getWorld()) || pluginTagged(en)) return;
        if (!WildSpawns.blockSpawn(mode, e.getSpawnReason(), en instanceof Mob, en instanceof Enemy)) return;
        e.setCancelled(true);
        if (!selfTest) blockedSpawns++;
        dropRiders(en);
    }

    /**
     * 막은 몹과 함께 막 생긴 탈것·기수 (닭 기수의 닭 …) 도 치운다 — 막은 몹이 없으면 혼자 남는다.
     * 막 생긴(40틱 안) 사라지는 몹이고, 플레이어가 타지 않았고, 스폰 이유가 바닐라·탈것·기수일 때만.
     */
    private void dropRiders(LivingEntity en) {
        List<Entity> around = new ArrayList<>(en.getPassengers());
        if (en.getVehicle() != null) around.add(en.getVehicle());
        if (around.isEmpty()) return;
        Bukkit.getScheduler().runTask(module.plugin(), () -> {
            for (Entity o : around) {
                if (!(o instanceof Mob m) || !m.isValid() || pluginTagged(m) || m.getTicksLived() > 40 || !m.getRemoveWhenFarAway()) continue;
                if (withPlayer(m) || !m.getPassengers().isEmpty()) continue;
                CreatureSpawnEvent.SpawnReason r = m.getEntitySpawnReason();
                if (WildSpawns.rule(r).wild() || r == CreatureSpawnEvent.SpawnReason.MOUNT || r == CreatureSpawnEvent.SpawnReason.JOCKEY) {
                    m.remove();
                    blockedSpawns++;
                }
            }
        });
    }

    /** 자연 변신(번개·익사·얼음·좀비화·감염)으로 범위 안의 몹이 생기려 하면 변신을 막는다 — 원래 몹은 그대로. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onTransform(EntityTransformEvent e) {
        Settings.Wild.Spawns mode = spawnMode();
        if (mode == Settings.Wild.Spawns.NONE || !isMain(e.getEntity().getWorld()) || pluginTagged(e.getEntity())) return;
        for (Entity t : e.getTransformedEntities()) {
            if (WildSpawns.blockTransform(mode, e.getTransformReason(), t instanceof Mob, t instanceof Enemy)) {
                e.setCancelled(true);
                if (!selfTest) blockedTransforms++;
                return;
            }
        }
    }

    /** 청크의 엔티티를 불러올 때 — 바닐라 적대 몹 치우기 (다음 틱에, 불러오는 도중에는 지우지 않음). */
    @EventHandler(priority = EventPriority.NORMAL)
    public void onEntitiesLoad(EntitiesLoadEvent e) {
        if (spawnMode() == Settings.Wild.Spawns.NONE || !isMain(e.getWorld())) return;
        List<Entity> mobs = new ArrayList<>();
        for (Entity x : e.getEntities()) if (x instanceof Mob && x instanceof Enemy) mobs.add(x);
        if (mobs.isEmpty()) return;
        Bukkit.getScheduler().runTask(module.plugin(), () -> sweep(mobs));
    }

    private static boolean withPlayer(Entity m) {
        for (Entity p : m.getPassengers()) if (p instanceof Player) return true;
        Entity v = m.getVehicle();
        if (v == null) return false;
        if (v instanceof Player) return true;
        for (Entity p : v.getPassengers()) if (p instanceof Player) return true;
        return false;
    }

    /** 이미 있던 바닐라 적대 몹 치우기 (주 월드만). @return 치운 수 */
    int sweep(Collection<? extends Entity> list) { return sweep(list, true); }

    /** @param count 정보의 '치운 적대 몹' 수에 더하나 (자가 진단은 더하지 않음) */
    int sweep(Collection<? extends Entity> list, boolean count) {
        Settings.Wild.Spawns mode = spawnMode();
        if (mode == Settings.Wild.Spawns.NONE) return 0;
        int n = 0;
        for (Entity e : List.copyOf(list)) {
            if (!(e instanceof Mob m) || !m.isValid() || !isMain(m.getWorld())) continue;
            if (WildSpawns.removeExisting(mode, existing(m))) {
                m.remove();
                n++;
            }
        }
        if (count) removedExisting += n;
        return n;
    }

    static WildSpawns.Existing existing(Mob m) {
        return new WildSpawns.Existing(m instanceof Enemy, m instanceof Boss, m.customName() != null,
                m instanceof Tameable t && t.isTamed(), m.isLeashed(), !m.getRemoveWhenFarAway(), pluginTagged(m), withPlayer(m),
                m.getEntitySpawnReason());
    }

    // ── 정보 ─────────────────────────────────────────────────────────────

    /** 한 줄 요약 (labadmin village info). */
    String summary() {
        Settings.Wild w = cfg();
        WildBorder.Square cur = current();
        return "경계 " + (w.border() ? WildBorder.describe(cur) + (cur.same(target()) ? "" : " (마을 경계와 다름)") : "끔")
                + " · 스폰 막기 " + w.spawns().id();
    }

    void info(CommandSender s) {
        Text.send(s, "<gold>야생 막기</gold> <gray>(config wild)");
        if (!active()) {
            s.sendMessage(Text.mm(" <gray>이 월드에는 마을이 없어 꺼져 있습니다 <dark_gray>(마을이 있는 world 폴더에서만 켜짐)"));
            return;
        }
        Settings.Wild w = cfg();
        WildBorder.Square cur = current(), tgt = target();
        String state = switch (lastAction) {
            case ADMIN -> "<#ff9a4d>관리자 경계 그대로 (labadmin wild border apply 로 마을 경계)";
            case FORGET, RESTORE -> "<gray>꺼서 되돌림";
            default -> cur.same(tgt) ? "<#7fe07f>마을 경계" : w.border() ? "<#ff9a4d>마을 경계와 다름" : "<gray>꺼짐";
        };
        s.sendMessage(Text.mm(" <gray>월드 경계: <white>" + (w.border() ? "켬" : "끔") + "</white> · 지금 <white>"
                + Text.escape(WildBorder.describe(cur)) + "</white> · 경고 " + cur.warning() + "칸 · " + state));
        s.sendMessage(Text.mm(" <gray>마을 경계: <white>" + Text.escape(WildBorder.describe(tgt)) + "</white> (마을 가장자리 + "
                + w.borderMargin() + "칸, 보호 상자 " + village.meta().protect.size() + "개 포함)"));
        s.sendMessage(Text.mm(" <gray>스폰 막기: <white>" + w.spawns().id() + "</white> " + switch (w.spawns()) {
            case ALL -> "(적대 몹 + 동물 — 있던 동물은 그대로)";
            case MONSTERS -> "(적대 몹만)";
            case NONE -> "(막지 않음" + (module.blockMobSpawns() ? " — village.block_mob_spawns 로 마을 둘레 적대만)" : ")");
        } + " · 막은 스폰 " + blockedSpawns + " · 막은 변신 " + blockedTransforms + " · 치운 적대 몹 " + removedExisting));
        s.sendMessage(Text.mm(" <gray>네더·엔드: <white>열림</white> (막지 않음) · 경계 밖이라 광장으로 옮긴 횟수 " + movedPlayers));
    }

    /** /labadmin wild border apply — 관리자 경계가 있어도 마을 경계로 덮어쓰기. */
    void forceBorder(CommandSender s) {
        if (!active()) {
            Text.error(s, "이 월드에는 마을이 없습니다.");
            return;
        }
        target = WildBorder.compute(village.meta(), cfg().borderMargin());
        String r = applyBorder(cfg(), true);
        Log.info("[야생] 관리자 명령 — 경계 " + r);
        Text.send(s, "<green>월드 경계를 마을 경계로 정했습니다</green> <gray>(" + Text.escape(WildBorder.describe(target)) + ")"
                + (cfg().border() ? "" : " <#ff9a4d>· config wild.border 가 false 라 다음 시작·reload 때 되돌립니다"));
        for (Player p : Bukkit.getOnlinePlayers()) check(p);
    }

    /** 자가 진단 시험 몹은 정보의 수에 넣지 않는다 (한 틱 안에서 켜고 끈다). */
    void selfTest(boolean on) { selfTest = on; }

    /** 자가 진단의 번개 시험으로 막은 변신 하나를 수에서 뺀다. */
    void uncountTransform() { if (blockedTransforms > 0) blockedTransforms--; }
}
