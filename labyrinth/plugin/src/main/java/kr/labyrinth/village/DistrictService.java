package kr.labyrinth.village;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.mine.MineLinks;
import kr.labyrinth.mine.MineNames;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * 실행 중 구역 (0.3.6.1 광산 마을, CONTRACT §2.13): 주 월드 폴더의 {@code labyrinth-district-<id>.yml} 을 읽어
 * 마을 보호·우클릭·연출·스폰 막기·야생 경계에 더하고({@link VillageService#rebuildIndex}), 광산 승강장을 {@link MineLinks} 에 알린다.
 * <ul>
 *   <li>시작 5초 뒤 한 번 ({@link #scheduleStartup}, {@link DistrictPolicy#onStart}): 기록이 없으면 저절로 짓기, building 이면 백업으로 되돌린 뒤 처음부터.</li>
 *   <li>NPC (광부 브론·제련공 이그나): 기존 NPC 체계({@code npcs().place})로 세운다. 적용 열쇠 = {@code village-applied.yml}
 *       {@code districts.<id>} (월드 UID + 구역 build_id). npcs.yml 을 고쳐 정의가 없으면 세우지 않고, 숙소 관리소 표지판·제련소
 *       우클릭 칸이 같은 메뉴를 연다.</li>
 *   <li>모든 자리가 막히면 {@code plugins/Labyrinth/village/district-<id>-blocked.txt} 를 남기고 관리자가 들어올 때 하루 한 번 알린다.</li>
 * </ul>
 */
final class DistrictService implements Listener {

    static final long STARTUP_TICKS = 100L; // 5초
    static final String NOTICE_FILE = "district-notice.yml";

    private final VillageModule module;
    private final VillageService village;
    private final Map<String, DistrictMeta> metas = new LinkedHashMap<>();
    private BukkitTask startupTask, guardTask;
    private int startupTries;
    /** 자리 검사를 통과한 뒤 블록을 쓰기 시작할 때까지 잠깐 켜 두는 보호 상자 (기록 파일 없이 — 짓기 직전 몇 초, 0.3.6.1). */
    private VillageMeta.Box pending;

    /** 광산 마을을 짓지 못한 이유 (district-&lt;id&gt;-blocked.txt 의 '이유:' 줄 · 관리자 안내 글이 이것으로 갈린다). */
    enum Blocked {
        PLAYER_MADE("player_made", "그 자리에 사람이 만든 것이 있어 아무것도 바꾸지 않았습니다",
                "방해물을 치웠으면 서버를 다시 켜면 다시 살펴봅니다 (또는 /labadmin village district build %s)."),
        NOT_SHIPPED("not_shipped", "이 월드는 서버팩 월드가 아니어서 저절로 짓지 않았습니다",
                "이 월드는 켤 때 저절로 짓지 않습니다 — 위 미리 보기로 자리를 확인한 뒤 직접 지으세요."),
        BORDER("border", "그 자리가 월드 경계(/worldborder) 밖이라 아무것도 바꾸지 않았습니다",
                "경계를 넓혔으면 서버를 다시 켜면 다시 살펴봅니다 (또는 /labadmin village district build %s)."),
        BACKUP("backup", "짓다가 멈춘 광산 마을을 되돌릴 백업 파일이 없거나 깨졌습니다",
                "지은 블록을 그대로 두고 기록만 지우려면: /labadmin village district remove %s force");

        final String code, notice, last;

        Blocked(String code, String notice, String last) {
            this.code = code;
            this.notice = notice;
            this.last = last;
        }

        static Blocked parse(String code) {
            for (Blocked b : values()) if (b.code.equals(code)) return b;
            return PLAYER_MADE;
        }
    }

    DistrictService(VillageModule module, VillageService village) {
        this.module = module;
        this.village = village;
    }

    void enable() {
        Bukkit.getPluginManager().registerEvents(this, module.plugin());
        MineLinks.setDistrict(this::mineLink);
        load(false);
        guardTask = Bukkit.getScheduler().runTaskTimer(module.plugin(), this::guard, 40L, 10L);
    }

    void disable() {
        HandlerList.unregisterAll(this);
        if (startupTask != null) startupTask.cancel();
        if (guardTask != null) guardTask.cancel();
        MineLinks.setDistrict(null);
    }

    DistrictLibrary library() { return module.districts(); }

    World world() { return village.world(); }

    static File metaFile(World w, String id) { return new File(w.getWorldFolder(), DistrictMeta.fileName(id)); }

    static File backupFile(World w, String id) { return new File(w.getWorldFolder(), DistrictMeta.backupName(id)); }

    File blockedFile(String id) { return new File(new File(module.plugin().getDataFolder(), "village"), "district-" + id + "-blocked.txt"); }

    // ── 기록 ─────────────────────────────────────────────────────────────

    /** 기록 다시 읽기 → 마을 색인(보호·우클릭) 다시 · refresh 면 야생 경계도. */
    void load(boolean refresh) {
        metas.clear();
        World w = world();
        if (w != null) {
            Set<String> ids = new LinkedHashSet<>();
            if (library() != null) ids.addAll(library().ids());
            ids.add("mine");
            for (String id : ids) {
                File f = metaFile(w, id);
                if (!f.isFile()) continue;
                try {
                    DistrictMeta d = DistrictMeta.load(f);
                    if (d.id == null || d.id.isBlank()) d.id = id;
                    metas.put(id, d);
                } catch (Exception e) {
                    Log.error("[광산 마을] " + f + " 읽기 실패 — 이 구역은 없는 것으로 봅니다", e);
                }
            }
        }
        village.rebuildIndex();
        for (DistrictMeta d : metas.values()) {
            Log.info("[광산 마을] " + d.name + " — " + d.state.key() + " · 자리 " + d.site + " · 조각 " + d.meta.pieces.size() + " · 보호 상자 "
                    + d.meta.protect.size());
        }
        if (refresh && village.wild() != null) village.wild().refresh("광산 마을");
    }

    DistrictMeta get(String id) { return metas.get(id); }

    /** 지어짐·짓는 중 (보호가 살아 있는) 구역. */
    List<DistrictMeta> active() {
        List<DistrictMeta> out = new ArrayList<>();
        for (DistrictMeta d : metas.values()) if (d.active()) out.add(d);
        return out;
    }

    /** 다른 구역(지어짐)의 메타 — 얼린 칸에 더한다. */
    List<VillageMeta> othersBuilt(String exceptId) {
        List<VillageMeta> out = new ArrayList<>();
        for (DistrictMeta d : metas.values()) if (d.active() && !d.id.equals(exceptId)) out.add(d.meta);
        return out;
    }

    String villageBuildId() { return village.meta() == null ? "" : village.meta().buildId; }

    /** 이 월드의 마을이 배포 월드인가 (지문에 그 build_id 가 있다). */
    boolean shipped(DistrictLibrary.Entry e) {
        VillageMeta v = village.meta();
        return e != null && e.fp() != null && v != null && e.fp().forBuild(v.buildId) != null;
    }

    // ── 시작 ─────────────────────────────────────────────────────────────

    void scheduleStartup() {
        if (startupTask != null) startupTask.cancel();
        startupTask = Bukkit.getScheduler().runTaskLater(module.plugin(), this::startup, STARTUP_TICKS);
    }

    private void startup() {
        startupTask = null;
        DistrictLibrary lib = library();
        if (lib == null || village.world() == null) return;
        if (VillageJob.running() != null) {
            // 다른 마을 작업 중 — 30초 뒤 다시 (최대 20번)
            if (startupTries++ < 20) startupTask = Bukkit.getScheduler().runTaskLater(module.plugin(), this::startup, 600L);
            return;
        }
        var cfg = module.districtConfig();
        for (DistrictLibrary.Entry e : lib.districts) {
            DistrictMeta d = metas.get(e.id());
            boolean auto = cfg.autoBuild() && module.mineEnabled();
            DistrictPolicy.Startup s = DistrictPolicy.onStart(d == null ? null : d.state, village.meta() != null, auto, shipped(e));
            switch (s) {
                case RECOVER -> {
                    Log.info("[광산 마을] 지난번에 짓다가 멈췄습니다 — 백업으로 되돌린 뒤 처음부터 다시 짓습니다");
                    DistrictJob.recover(module, this, e, auto && shipped(e)).start();
                    return; // 한 번에 하나
                }
                case AUTO_BUILD -> {
                    if (!e.ok()) {
                        Log.warn("[광산 마을] 청사진 문제로 짓지 않습니다: " + String.join(" · ", e.problems()));
                        continue;
                    }
                    Log.info("[광산 마을] 처음 켰습니다 — 마을 옆에 광산 마을을 짓습니다 (자리 " + String.join(" → ", cfg.sites()) + ")");
                    DistrictJob.auto(module, this, e, cfg.sites()).start();
                    return;
                }
                case UNKNOWN_WORLD -> {
                    String why = "이 월드는 서버팩 월드가 아니어서(마을이 다름) 광산 마을을 저절로 짓지 않았습니다. "
                            + "자리를 확인한 뒤 지으려면: /labadmin village district preview " + e.id() + " → build " + e.id();
                    Log.info("[광산 마을] " + why);
                    writeBlocked(e.id(), Blocked.NOT_SHIPPED, List.of(why), List.of());
                }
                case NO_VILLAGE, NONE -> {
                    if (d != null && d.built()) applyNpcs(false);
                }
            }
        }
    }

    // ── NPC ──────────────────────────────────────────────────────────────

    private String applyKey(DistrictMeta d) { return world().getUID() + ":" + d.meta.buildId; }

    /** 지은 구역 NPC 세우기 (적용 열쇠가 다르거나 force). @return 세운 수 */
    int applyNpcs(boolean force) {
        World w = world();
        if (w == null) return 0;
        File f = village.appliedFile();
        YamlConfiguration y = f.isFile() ? YamlConfiguration.loadConfiguration(f) : new YamlConfiguration();
        int placed = 0;
        boolean dirty = false;
        for (DistrictMeta d : metas.values()) {
            if (!d.built()) continue;
            String key = applyKey(d);
            if (!force && key.equals(y.getString("districts." + d.id, ""))) continue;
            placed += placeNpcs(d);
            y.set("districts." + d.id, key);
            dirty = true;
        }
        if (dirty) {
            try {
                module.plugin().getDataFolder().mkdirs();
                y.save(f);
            } catch (IOException e) {
                Log.warn("[광산 마을] village-applied.yml 저장 실패: " + e.getMessage());
            }
        }
        return placed;
    }

    int placeNpcs(DistrictMeta d) {
        int n = 0;
        var s = module.services();
        for (Map.Entry<String, VillageMeta.Pos> e : d.meta.npcs.entrySet()) {
            String id = e.getKey();
            if (!s.content().npcs().containsKey(id)) {
                Log.warn("[광산 마을] NPC '" + id + "' 가 npcs.yml 에 없어 세우지 않았습니다 — 숙소 '광산 관리소' 표지판·제련소를 우클릭하면 같은 메뉴가 열립니다");
                continue;
            }
            try {
                s.npcs().place(id, village.loc(e.getValue())); // 청크가 안 불려 있으면 자리만 저장되고, 청크가 불릴 때 선다
                n++;
            } catch (Throwable t) {
                Log.error("[광산 마을] NPC 배치 실패 (" + id + ")", t);
            }
        }
        Log.info("[광산 마을] NPC " + n + "/" + d.meta.npcs.size() + " 세움");
        return n;
    }

    /** 구역 NPC 치우기 (지울 때) — 다른 곳으로 옮겨 둔 NPC 는 그대로. */
    void removeNpcs(DistrictMeta d) {
        var s = module.services();
        Map<String, Location> placed = s.npcs() instanceof kr.labyrinth.mobs.npc.NpcServiceImpl impl ? impl.placed() : Map.of();
        for (Map.Entry<String, VillageMeta.Pos> e : d.meta.npcs.entrySet()) {
            Location at = placed.get(e.getKey());
            Location want = village.loc(e.getValue());
            if (at != null && at.getWorld() != null && at.getWorld().equals(want.getWorld()) && at.distanceSquared(want) > 9) continue;
            try {
                s.npcs().remove(e.getKey());
            } catch (Throwable t) {
                Log.error("[광산 마을] NPC 치우기 실패 (" + e.getKey() + ")", t);
            }
        }
        File f = village.appliedFile();
        if (f.isFile()) {
            YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
            y.set("districts." + d.id, null);
            try {
                y.save(f);
            } catch (IOException ignored) {
                // 다음 적용 때 다시
            }
        }
    }

    // ── 광산 잇기 ─────────────────────────────────────────────────────────

    /** MineLinks 가 묻는다: 지은 광산 마을의 승강장 (내리는 자리 + 승강기 칸). */
    private MineLinks.District mineLink() {
        DistrictMeta d = metas.get("mine");
        World w = world();
        if (d == null || !d.built() || w == null) return null;
        VillageMeta.Pos ex = d.meta.points.get(MineNames.MARKER_EXIT);
        List<Location> lifts = new ArrayList<>();
        for (Map.Entry<String, String> e : d.meta.interact.entrySet()) {
            if (!MineNames.INTERACT_LIFT.equals(e.getValue())) continue;
            String[] p = e.getKey().split(",");
            try {
                lifts.add(new Location(w, Integer.parseInt(p[0]) + 0.5, Integer.parseInt(p[1]), Integer.parseInt(p[2]) + 0.5));
            } catch (RuntimeException ignored) {
                // 형식 오류 칸은 건너뜀
            }
        }
        Location exit = ex != null ? village.loc(ex) : lifts.isEmpty() ? null : lifts.get(0);
        return exit == null ? null : new MineLinks.District(exit, List.copyOf(lifts));
    }

    // ── 짓는 동안 사람 밀어내기 ───────────────────────────────────────────

    /** 짓는 중(building) 구역 상자 안의 플레이어는 마을 광장으로 (관리자 크리에이티브는 그대로). */
    private void guard() {
        World w = world();
        if (w == null) return;
        for (DistrictMeta d : metas.values()) {
            if (d.state != DistrictMeta.State.BUILDING) continue;
            // 실제로 블록을 쓰거나 되돌리는 동안만 (짓기가 멈춘 채 남은 기록이면 밀어내지 않는다 — 보호만)
            if (!(VillageJob.running() instanceof DistrictJob j) || !j.busy(d.id)) continue;
            boolean restoring = j.restoring();
            int[] b = bounds(d.meta.protect, 2);
            if (b == null) continue;
            for (Player p : w.getPlayers()) {
                Location l = p.getLocation();
                if (l.getX() < b[0] || l.getX() > b[2] + 1 || l.getZ() < b[1] || l.getZ() > b[3] + 1) continue;
                if (p.hasPermission(CommandService.PERM_ADMIN) && (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR)) continue;
                evict(p, d, restoring);
            }
        }
    }

    void evict(Player p, DistrictMeta d, boolean restoring) {
        Location to = village.spawn();
        if (to == null) return;
        p.setFallDistance(0);
        kr.labyrinth.core.Teleports.to(p, to);
        Text.send(p, "<#e8c58a>" + Text.escape(d.name) + "</#e8c58a><gray>" + objectParticle(d.name) + (restoring ? " 되돌리는" : " 짓는")
                + " 중이라 광장으로 옮겼습니다. 잠시 뒤에 가 보세요.");
    }

    /** 을/를 (마지막 글자 받침). */
    static String objectParticle(String word) {
        if (word == null || word.isEmpty()) return "을";
        char c = word.charAt(word.length() - 1);
        if (c < 0xAC00 || c > 0xD7A3) return "을(를)";
        return (c - 0xAC00) % 28 == 0 ? "를" : "을";
    }

    // ── 짓기 직전 보호 · 경계 ─────────────────────────────────────────────

    /** 짓기 직전 잠깐 보호 (null = 끔). 마을 색인(놓기·부수기 막기)에만 더하고 경계·안전지대에는 넣지 않는다. */
    void setPending(VillageMeta.Box b) {
        pending = b;
        village.rebuildIndex();
    }

    VillageMeta.Box pending() { return pending; }

    /**
     * 지은 뒤에도 승강장·나가는 자리·길·건물이 월드 경계 안인가 (null = 됨, 아니면 이유).
     * 플러그인이 정하는 경계(wild.border)는 구역을 넣어 넓어지니 늘 된다 — 관리자가 /worldborder 로 정한 경계일 때만 본다.
     */
    String outsideBorder(VillageMeta m) {
        World w = world();
        if (w == null || m == null) return null;
        WildService ws = village.wild();
        if (ws != null && ws.borderOurs()) return null;
        org.bukkit.WorldBorder wb = w.getWorldBorder();
        WildBorder.Square s = new WildBorder.Square(wb.getCenter().getX(), wb.getCenter().getZ(), wb.getSize(), wb.getWarningDistance());
        if (s.vanillaDefault()) return null;
        for (VillageMeta.Pos p : m.points.values()) {
            if (!s.contains(p.x(), p.z())) return "월드 경계 밖 — 관리자가 정한 경계(" + WildBorder.describe(s) + ") 밖에 승강장 앞 자리 ("
                    + (int) Math.floor(p.x()) + ", " + (int) Math.floor(p.z()) + ")";
        }
        for (String k : m.interact.keySet()) {
            String[] a = k.split(",");
            try {
                int x = Integer.parseInt(a[0]), z = Integer.parseInt(a[2]);
                if (!s.containsBlocks(x, z, x, z)) return "월드 경계 밖 — 관리자가 정한 경계(" + WildBorder.describe(s) + ") 밖에 우클릭 칸 (" + x + ", " + z + ")";
            } catch (RuntimeException ignored) {
                // 형식 오류 칸은 건너뜀
            }
        }
        for (VillageMeta.Box b : m.protect) {
            if (!s.containsBlocks(b.x0(), b.z0(), b.x1(), b.z1())) {
                return "월드 경계 밖 — 관리자가 정한 경계(" + WildBorder.describe(s) + ") 밖에 광산 마을 상자 (x " + b.x0() + "~" + b.x1() + ", z "
                        + b.z0() + "~" + b.z1() + ")";
            }
        }
        return null;
    }

    // ── 접속 ─────────────────────────────────────────────────────────────

    /** 지은 광산 마을 블록 안에 끼어 접속한 플레이어 (짓기 전에 그 자리에서 나갔던 사람) → 승강장 앞(경계 안이면) 또는 광장. */
    private void unstuck(Player p) {
        World w = world();
        if (w == null || !p.isOnline() || !p.getWorld().equals(w) || p.getGameMode() == GameMode.SPECTATOR) return;
        Location l = p.getLocation();
        for (DistrictMeta d : metas.values()) {
            if (!d.built()) continue;
            int[] b = bounds(d.meta.protect, 1);
            if (b == null || l.getX() < b[0] || l.getX() > b[2] + 1 || l.getZ() < b[1] || l.getZ() > b[3] + 1) continue;
            org.bukkit.block.Block feet = l.getBlock(), head = feet.getRelative(0, 1, 0);
            if (feet.isPassable() && head.isPassable()) return;
            VillageMeta.Pos ex = d.meta.points.get(MineNames.MARKER_EXIT);
            Location to = ex != null ? village.loc(ex) : null;
            boolean lift = to != null && w.getWorldBorder().isInside(to);
            if (!lift) to = village.spawn();
            if (to == null) return;
            p.setFallDistance(0);
            kr.labyrinth.core.Teleports.to(p, to);
            Text.send(p, "<#e8c58a>" + Text.escape(d.name) + "</#e8c58a><gray>이 생긴 자리에 끼어 있어 " + (lift ? "승강장 앞" : "광장") + "으로 옮겼습니다.");
            return;
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoinUnstuck(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> unstuck(p), 6L);
    }

    static int[] bounds(List<VillageMeta.Box> boxes, int pad) {
        if (boxes == null || boxes.isEmpty()) return null;
        int x0 = Integer.MAX_VALUE, z0 = Integer.MAX_VALUE, x1 = Integer.MIN_VALUE, z1 = Integer.MIN_VALUE;
        for (VillageMeta.Box b : boxes) {
            x0 = Math.min(x0, b.x0());
            z0 = Math.min(z0, b.z0());
            x1 = Math.max(x1, b.x1());
            z1 = Math.max(z1, b.z1());
        }
        return new int[] {x0 - pad, z0 - pad, x1 + pad, z1 + pad};
    }

    // ── 막혔을 때 ─────────────────────────────────────────────────────────

    /** district-<id>-blocked.txt (사람이 읽는 글). 둘째 줄 '이유: … [코드]' 로 관리자 안내 글이 갈린다. */
    void writeBlocked(String id, Blocked reason, List<String> head, List<String> lines) {
        File f = blockedFile(id);
        List<String> out = new ArrayList<>();
        out.add("미궁 라비린스 — 광산 마을을 짓지 않았습니다 (" + java.time.LocalDateTime.now().withNano(0) + ")");
        out.add("이유: " + reason.notice + " [" + reason.code + "]");
        out.add("");
        out.addAll(head);
        if (!lines.isEmpty()) {
            out.add("");
            out.add("막힌 이유 (사람이 만든 것으로 보이면 아무것도 바꾸지 않습니다 · 좌표 = x y z):");
            out.addAll(lines);
        }
        out.add("");
        out.add("광산은 그대로 쓸 수 있습니다: /미궁 광산 또는 메인 메뉴 '광산' → 얕은 갱도의 광산 관리소 (곡괭이·제련·팔기).");
        if (reason != Blocked.BACKUP) {
            out.add("다른 자리에 지으려면: 게임 안에서 그 자리(큰길에서 이어질 곳)에 서서");
            out.add("  /labadmin village district preview " + id + " here [north|east|south|west]   (미리 보기 — 아무것도 바꾸지 않음)");
            out.add("  /labadmin village district build " + id + " here [north|east|south|west]");
        }
        out.add(String.format(reason.last, id));
        try {
            f.getParentFile().mkdirs();
            Files.write(f.toPath(), out, StandardCharsets.UTF_8);
        } catch (IOException e) {
            Log.warn("[광산 마을] " + f + " 쓰기 실패: " + e.getMessage());
        }
        if (module.districtConfig().notifyAdmins()) {
            for (Player p : Bukkit.getOnlinePlayers()) if (p.hasPermission(CommandService.PERM_ADMIN)) noticeAdmin(p, id, true);
        }
    }

    void clearBlocked(String id) {
        File f = blockedFile(id);
        if (f.isFile() && !f.delete()) Log.warn("[광산 마을] " + f + " 를 지우지 못했습니다");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        if (!p.hasPermission(CommandService.PERM_ADMIN) || !module.districtConfig().notifyAdmins()) return;
        Bukkit.getScheduler().runTaskLater(module.plugin(), () -> {
            if (!p.isOnline() || library() == null) return;
            for (String id : library().ids()) noticeAdmin(p, id, false);
        }, 60L);
    }

    /** 막힘 안내 (하루 한 번 — plugins/Labyrinth/village/district-notice.yml). */
    void noticeAdmin(Player p, String id, boolean now) {
        File f = blockedFile(id);
        if (!f.isFile()) return;
        File nf = new File(new File(module.plugin().getDataFolder(), "village"), NOTICE_FILE);
        YamlConfiguration y = nf.isFile() ? YamlConfiguration.loadConfiguration(nf) : new YamlConfiguration();
        long today = LocalDate.now(ZoneId.systemDefault()).toEpochDay();
        String key = id + "." + p.getUniqueId();
        if (!now && !DistrictPolicy.notifyToday(y.getLong(key, Long.MIN_VALUE), today)) return;
        Blocked reason = blockedReason(f);
        y.set(key, today);
        try {
            nf.getParentFile().mkdirs();
            y.save(nf);
        } catch (IOException ignored) {
            // 안내는 다음에 다시
        }
        Text.send(p, "<#e8c58a>[광산 마을]</#e8c58a> <gray>" + (reason == Blocked.BACKUP ? "" : "마을 옆에 짓지 못했습니다 — ")
                + reason.notice + ". 광산은 <white>/미궁 광산</white> 으로 그대로 됩니다.");
        Text.send(p, "<gray>  자세히: <white>plugins/Labyrinth/village/" + f.getName() + "</white> · <white>/labadmin village district info</white>");
    }

    /** 막힘 파일의 '이유: … [코드]' (없으면 사람이 만든 것 — 0.3.6.1 첫 판 파일). */
    static Blocked blockedReason(File f) {
        try {
            for (String line : Files.readAllLines(f.toPath(), StandardCharsets.UTF_8)) {
                if (!line.startsWith("이유:")) continue;
                int a = line.lastIndexOf('['), b = line.lastIndexOf(']');
                if (a >= 0 && b > a) return Blocked.parse(line.substring(a + 1, b));
            }
        } catch (IOException ignored) {
            // 아래 기본값
        }
        return Blocked.PLAYER_MADE;
    }

    // ── 기록만 지우기 (백업이 없을 때) ─────────────────────────────────────

    /** remove … force: 블록은 그대로 두고 기록만 removed 로 (백업이 없거나 깨져 되돌릴 수 없을 때). */
    void forget(CommandSender s, String id) {
        DistrictMeta d = metas.get(id);
        if (d == null) {
            Text.error(s, "지은 기록이 없습니다");
            return;
        }
        if (VillageJob.running() instanceof DistrictJob) {
            Text.error(s, "광산 마을 작업이 진행 중입니다 — 끝난 뒤에 하세요");
            return;
        }
        removeNpcs(d);
        d.state = DistrictMeta.State.REMOVED;
        try {
            d.save(metaFile(world(), id));
        } catch (Exception e) {
            Text.error(s, "기록을 쓰지 못했습니다: " + Text.escape(String.valueOf(e)));
            return;
        }
        load(true);
        clearBlocked(id);
        Text.send(s, "<#7fe07f><b>광산 마을 기록을 지웠습니다</b></#7fe07f> <gray>(state: removed · 블록은 그대로 — 보호·NPC·승강장은 꺼짐)");
        Text.send(s, "<gray>  남은 블록은 직접 치워야 합니다. 다 치운 뒤 다시 지으려면 <white>/labadmin village district build " + Text.escape(id) + "</white>");
        Log.info("[광산 마을] 기록만 지움 (remove force) — 블록은 그대로");
    }

    // ── 정보 ─────────────────────────────────────────────────────────────

    void info(CommandSender s, String id) {
        DistrictLibrary.Entry e = library() == null ? null : library().get(id);
        DistrictMeta d = metas.get(id);
        var cfg = module.districtConfig();
        Text.send(s, "<gold>광산 마을</gold> <gray>(" + Text.escape(id) + ")");
        if (e == null) {
            s.sendMessage(Text.mm(" <gray>청사진: <#ff6b6b>없음"));
        } else {
            s.sendMessage(Text.mm(" <gray>청사진: 조각 " + e.layout().pieces.size() + " · 길 " + e.layout().paths.size() + " · 자리 "
                    + String.join("·", e.layout().siteIds()) + " · 지문 " + (e.fp() == null ? "<#ff9a4d>없음" : "있음")
                    + " · 이 월드 " + (shipped(e) ? "<#7fe07f>서버팩 월드" : "<#ff9a4d>서버팩 월드 아님")
                    + (e.ok() ? "" : " <#ff6b6b>· 문제 " + Text.escape(String.join(" · ", e.problems())))));
        }
        s.sendMessage(Text.mm(" <gray>설정: 자동 짓기 <white>" + (cfg.autoBuild() ? "켬" : "끔") + "</white> · 자리 <white>" + String.join(" → ", cfg.sites())
                + "</white> · 틱당 블록 <white>" + DistrictJob.blocksPerTick(cfg.blocksPerTick()) + (DistrictJob.blocksPerTick(cfg.blocksPerTick()) != cfg.blocksPerTick() ? " (설정 " + cfg.blocksPerTick() + " → 최소 " + DistrictJob.MIN_BLOCKS_PER_TICK + ")" : "")
                + "</white> · 관리자 안내 <white>" + (cfg.notifyAdmins() ? "켬" : "끔")));
        if (d == null) {
            File bf = blockedFile(id);
            s.sendMessage(Text.mm(" <gray>상태: <white>아직 없음</white>" + (bf.isFile() ? " <#ff9a4d>· 막힘 기록 plugins/Labyrinth/village/" + bf.getName() : "")));
            return;
        }
        s.sendMessage(Text.mm(" <gray>상태: <white>" + switch (d.state) {
            case BUILT -> "<#7fe07f>지어짐";
            case BUILDING -> VillageJob.running() instanceof DistrictJob ? "<#ff9a4d>짓는 중" : "<#ff9a4d>짓다가 멈춤 (다음 시작 때 백업으로 되돌림 · 백업이 없으면 remove " + Text.escape(id) + " force)";
            case REMOVED -> "지움 (저절로 다시 짓지 않음)";
        } + "</white> · 자리 <white>" + Text.escape(d.site) + "</white> · 지은 때 " + Text.escape(d.meta.builtAt)));
        s.sendMessage(Text.mm(" <gray>중심 (" + d.meta.center[0] + ", " + d.meta.center[2] + ") · 조각 " + d.meta.pieces.size() + " · 길 " + d.meta.paths.size()
                + " · 보호 상자 " + d.meta.protect.size() + " · 우클릭 " + d.meta.interact.size() + " · NPC " + d.meta.npcs.size()
                + " · 백업 " + (backupFile(world(), id).isFile() ? "<white>" + DistrictMeta.backupName(id) + "</white>" : "<#ff9a4d>없음")));
    }
}
