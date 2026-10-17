package kr.labyrinth.core;

import io.papermc.paper.event.entity.EntityPortalReadyEvent;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.BooleanSupplier;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.PortalType;
import org.bukkit.World;
import org.bukkit.World.Environment;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Marker;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPortalEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerPortalEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.PortalCreateEvent;
import org.bukkit.plugin.RegisteredListener;

/**
 * 네더 막기 (0.3.7, 서버장 결정 "네더 막아") — config.yml {@code wild.nether} (키가 없으면 false = 막음). 모든 월드에 쓰인다
 * (마을이 없는 월드도). 규칙은 {@link NetherRule}.
 * <ul>
 *   <li>네더가 아닌 월드에서 흑요석 틀에 불을 붙여도 네더 차원문이 열리지 않는다 ({@link PortalCreateEvent} FIRE).</li>
 *   <li>네더로 가는 차원문 지나가기를 막는다: {@link EntityPortalReadyEvent} (플레이어·몹·물건·탈것 모두, 가장 먼저) →
 *       {@link PlayerPortalEvent} · {@link EntityPortalEvent} (한 번 더). 네더 안에 새 짝이 생기는 것도 막는다.</li>
 *   <li>네더에서 나가기는 늘 된다. 돌아오는 짝을 다른 규칙(집터 — {@code homes.rules.CrossZoneListener})이 막아 못 나오면
 *       광장(마을이 없으면 그 월드 스폰)으로 옮긴다. 네더에서 접속하면 돌아가는 길을 한 줄 알려 준다.</li>
 *   <li>엔드 차원문·엔드 관문은 건드리지 않는다.</li>
 *   <li>관리자(labyrinth.admin)가 크리에이티브일 때는 지나간다 — 지형 잠금 ({@code homes.rules.Guard#bypass}) 과 같은 예외.
 *       그때 액션바에 "관리자라 지나갑니다" 를 띄워, 시험할 때 헷갈리지 않게 한다.</li>
 * </ul>
 * 안내는 액션바 (HUD 위 2.5초), 한 사람에게 1초에 한 번.
 */
public final class NetherLock implements Module, Listener {

    static final String CLOSED = "네더는 닫혀 있습니다.";
    static final String NO_PORTAL = "네더는 닫혀 있어 차원문이 열리지 않습니다.";
    static final String ADMIN = "관리자(크리에이티브)라 지나갑니다. 다른 사람은 막힙니다.";
    static final String ADMIN_OPEN = "관리자(크리에이티브)라 문이 열립니다. 다른 사람은 막힙니다.";

    private static volatile NetherLock instance;

    private final Services services;
    private final BooleanSupplier openFlag;
    private final Map<UUID, Long> lastNote = new HashMap<>();
    private boolean quiet; // 자가 진단 중 — 세지도 알리지도 않음
    long blockedTravel, blockedCreate, sentHome;

    public NetherLock(Services services) { this(services, () -> services.settings().netherOpen()); }

    /** 시험용 — services 없이 (차원문 이벤트 처리만, 스케줄러를 쓰는 접속 안내·광장 보내기는 안 됨). */
    NetherLock(Services services, BooleanSupplier openFlag) {
        this.services = services;
        this.openFlag = openFlag;
    }

    @Override
    public String name() { return "nether"; }

    @Override
    public void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        instance = this;
        Log.info("[네더] " + (open() ? "열림 (config wild.nether: true)" : "막음 — 네더로 가는 차원문이 열리지 않습니다 (다시 열기: config wild.nether: true)"));
    }

    @Override
    public void reload() {
        Log.info("[네더] " + (open() ? "열림 (config wild.nether: true)" : "막음 (config wild.nether: false)"));
    }

    @Override
    public void disable() {
        HandlerList.unregisterAll(this);
        if (instance == this) instance = null;
        lastNote.clear();
    }

    /** 지금 네더 차원문을 쓸 수 있나 (모듈이 안 켜졌으면 config 를 그대로 — 그것도 없으면 막힘). */
    public static boolean isOpen() {
        NetherLock l = instance;
        if (l != null) return l.open();
        try {
            return Services.get().settings().netherOpen();
        } catch (RuntimeException e) {
            return false;
        }
    }

    boolean open() { return openFlag.getAsBoolean(); }

    /** 지형 잠금과 같은 관리자 예외 (labyrinth.admin + 크리에이티브). */
    static boolean bypass(Player p) {
        return p != null && p.hasPermission(CommandService.PERM_ADMIN) && p.getGameMode() == GameMode.CREATIVE;
    }

    private static Environment env(World w) { return w == null ? null : w.getEnvironment(); }

    private static Environment env(Location l) { return l == null ? null : env(l.getWorld()); }

    // ── 차원문 만들기 ────────────────────────────────────────────────────

    /** 흑요석 틀에 불 (네더가 아닌 월드) · 네더 안에 새 짝 → 취소. 집터 규칙(LOW)보다 먼저라 글이 겹치지 않는다. */
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCreate(PortalCreateEvent e) {
        if (!NetherRule.blocksCreate(open(), e.getReason(), env(e.getWorld()))) return;
        Entity by = e.getEntity();
        if (bypassRide(by)) {
            notePlayers(by, e.getReason() == PortalCreateEvent.CreateReason.FIRE ? ADMIN_OPEN : ADMIN);
            return;
        }
        e.setCancelled(true);
        if (quiet) return;
        blockedCreate++;
        notePlayers(by, e.getReason() == PortalCreateEvent.CreateReason.FIRE ? NO_PORTAL : CLOSED);
    }

    /**
     * 네더에서 나오는 길에 오버월드 쪽 짝을 다른 규칙이 막았다 (집터 밖 · 남의 집) → 그대로 두면 네더에 갇히므로 다음 틱에 광장으로.
     * 네더가 열려 있을 때는 예전대로 (집터 규칙의 "/미궁 마을" 안내만).
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onCreateDenied(PortalCreateEvent e) {
        if (!e.isCancelled() || quiet || open() || e.getReason() != PortalCreateEvent.CreateReason.NETHER_PAIR) return;
        World target = e.getWorld();
        if (target == null || target.getEnvironment() == Environment.NETHER) return;
        for (Player p : players(e.getEntity())) {
            if (p.getWorld().getEnvironment() != Environment.NETHER) continue;
            UUID id = p.getUniqueId();
            Bukkit.getScheduler().runTaskLater(services.plugin(), () -> sendHome(Bukkit.getPlayer(id), target), 1L);
        }
    }

    private void sendHome(Player p, World target) {
        if (p == null || !p.isOnline() || p.getWorld().getEnvironment() != Environment.NETHER) return; // 그새 나갔음
        kr.labyrinth.village.VillageService v = kr.labyrinth.village.VillageService.get();
        Location plaza = v == null ? null : v.spawn();
        Location to = plaza != null ? plaza : target.getSpawnLocation();
        p.setFallDistance(0);
        if (!Teleports.to(p, to)) return;
        sentHome++;
        Text.send(p, "<gray>여기에는 돌아오는 차원문을 만들 수 없어 " + (plaza != null ? "광장" : "스폰") + "으로 옮겼습니다.");
    }

    // ── 지나가기 ─────────────────────────────────────────────────────────

    /** 네더 차원문에 충분히 서 있었다 (플레이어·몹·물건·탈것, Paper) — 가장 먼저 막는다. 취소하면 차원문 기다림이 처음으로. */
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onReady(EntityPortalReadyEvent e) {
        Entity en = e.getEntity();
        if (!NetherRule.blocksTravel(open(), NetherRule.of(e.getPortalType()), env(en.getWorld()), env(e.getTargetWorld()))) return;
        if (e.getTargetWorld() == null) return; // 갈 곳이 없는 문 (네더를 끈 서버) — 어차피 안 감
        travelDenied(e, en);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onPlayerPortal(PlayerPortalEvent e) {
        if (!NetherRule.blocksTravel(open(), NetherRule.of(e.getCause()), env(e.getFrom()), env(e.getTo()))) return;
        travelDenied(e, e.getPlayer());
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onEntityPortal(EntityPortalEvent e) {
        if (!NetherRule.blocksTravel(open(), NetherRule.of(e.getPortalType()), env(e.getFrom()), env(e.getTo()))) return;
        travelDenied(e, e.getEntity());
    }

    private void travelDenied(org.bukkit.event.Cancellable e, Entity en) {
        if (bypassRide(en)) {
            notePlayers(en, ADMIN);
            return;
        }
        e.setCancelled(true);
        if (quiet) return;
        blockedTravel++;
        notePlayers(en, CLOSED);
    }

    // ── 네더에서 접속 ────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        if (open() || p.getWorld().getEnvironment() != Environment.NETHER) return;
        UUID id = p.getUniqueId();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            Player q = Bukkit.getPlayer(id);
            if (q == null || !q.isOnline() || q.getWorld().getEnvironment() != Environment.NETHER || open()) return;
            boolean tp = services.plugin().getConfig().getBoolean("village.teleport_command", true)
                    && kr.labyrinth.village.VillageService.present();
            Text.send(q, "<gray>네더로 가는 길은 닫혔습니다. 여기 차원문으로 돌아갈 수 있습니다."
                    + (tp ? " <white>/미궁 마을</white> 도 됩니다." : ""));
        }, 40L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { lastNote.remove(e.getPlayer().getUniqueId()); }

    // ── 안내 ─────────────────────────────────────────────────────────────

    /** 이 엔티티가 플레이어면 그 사람, 탈것이면 탄 사람들 (여러 겹). */
    static List<Player> players(Entity en) {
        List<Player> out = new ArrayList<>();
        collect(en, out, 0);
        return out;
    }

    private static void collect(Entity en, List<Player> out, int depth) {
        if (en == null || depth > 8) return;
        if (en instanceof Player p) out.add(p);
        for (Entity r : en.getPassengers()) collect(r, out, depth + 1);
    }

    /** 지나가는 것이 관리자 예외인가 — 플레이어 자신, 또는 탈것에 탄 사람 중 하나 (보트에 같이 탄 친구도 함께 지나간다). */
    static boolean bypassRide(Entity en) {
        for (Player p : players(en)) if (bypass(p)) return true;
        return false;
    }

    private void notePlayers(Entity en, String msg) {
        if (quiet) return;
        for (Player p : players(en)) note(p, msg);
    }

    private void note(Player p, String msg) {
        long now = System.currentTimeMillis();
        Long last = lastNote.get(p.getUniqueId());
        if (last != null && now - last < 1000) return;
        lastNote.put(p.getUniqueId(), now);
        net.kyori.adventure.text.Component line = Text.mm("<#ff9b6b>" + msg);
        if (services != null) {
            services.hud().actionBar(p, line, 50); // HUD 줄 위에 2.5초 (그냥 보내면 HP 줄이 바로 덮음)
            return;
        }
        p.sendActionBar(line); // 시험 (services 없음)
    }

    // ── 상태 · 자가 진단 ─────────────────────────────────────────────────

    /** "네더: 막음 (wild.nether: false) · 막은 횟수 지나가기 n · 문 열기 n · 광장으로 n". */
    public static String statusLine() {
        NetherLock l = instance;
        boolean open = isOpen();
        String s = "네더: " + (open ? "열림 (wild.nether: true)" : "막음 (wild.nether: false)") + " · 엔드: 열림";
        if (l != null && !open) s += " · 막은 횟수 지나가기 " + l.blockedTravel + " · 문 열기 " + l.blockedCreate + " · 광장으로 " + l.sentHome;
        return s;
    }

    /**
     * "[네더 막기 자가 진단] 결과: 예외 0 · 네더=막음 · rules=ok(n/n) · live=ok(n/n) · listeners=ok(5/5) · 네더 월드=world_nether".
     * live = 이 리스너에 실제 이벤트를 만들어 넣어 본다 (주 월드·네더 월드 · 잠깐 만든 표지 엔티티 하나, 끝나면 지움).
     */
    public static String selfTestLine() {
        NetherLock l = instance;
        if (l == null) return "[네더 막기 자가 진단] 결과: 예외 1 · 모듈이 안 켜짐 · 네더=" + (isOpen() ? "열림" : "막음");
        return l.selfTest();
    }

    String selfTest() {
        int errors = 0;
        boolean open = open();
        StringBuilder sb = new StringBuilder(" · 네더=").append(open ? "열림" : "막음");
        try {
            int[] r = NetherRule.selfCheck();
            sb.append(" · rules=").append(r[0] == r[1] ? "ok" : "FAIL").append('(').append(r[0]).append('/').append(r[1]).append(')');
        } catch (Throwable t) {
            errors++;
            sb.append(" · rules=예외");
        }
        World main = Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0);
        World nether = null, end = null;
        for (World w : Bukkit.getWorlds()) {
            if (nether == null && w.getEnvironment() == Environment.NETHER) nether = w;
            if (end == null && w.getEnvironment() == Environment.THE_END) end = w;
        }
        try {
            int[] r = live(main, nether, end, open);
            sb.append(" · live=").append(r[0] == r[1] ? "ok" : "FAIL").append('(').append(r[0]).append('/').append(r[1]).append(')');
        } catch (Throwable t) {
            errors++;
            sb.append(" · live=예외 ").append(t.getClass().getSimpleName());
        }
        int reg = 0;
        HandlerList[] lists = {PortalCreateEvent.getHandlerList(), PlayerPortalEvent.getHandlerList(), EntityPortalEvent.getHandlerList(),
                EntityPortalReadyEvent.getHandlerList(), PlayerJoinEvent.getHandlerList()};
        for (HandlerList hl : lists) {
            for (RegisteredListener rl : hl.getRegisteredListeners()) {
                if (rl.getListener() == this) {
                    reg++;
                    break;
                }
            }
        }
        sb.append(" · listeners=").append(reg == lists.length ? "ok" : "FAIL").append('(').append(reg).append('/').append(lists.length).append(')');
        sb.append(" · 네더 월드=").append(nether == null ? "없음 (server.properties allow-nether=false)" : nether.getName());
        return "[네더 막기 자가 진단] 결과: 예외 " + errors + sb;
    }

    /** 이 리스너에 이벤트를 직접 넣어 본다 → [맞음, 전체]. 막혀야 할 것은 open 이면 안 막혀야 한다. */
    private int[] live(World main, World nether, World end, boolean open) {
        int ok = 0, n = 0;
        if (main == null) return new int[] {0, 1};
        quiet = true;
        Marker m = null;
        try {
            // 문 열기: 주 월드 불 → 막힘 · 네더 쪽 불 → 됨 · 네더 안 새 짝 → 막힘 · 주 월드 짝 → 됨 · 엔드 발판 → 됨
            n++;
            if (create(main, PortalCreateEvent.CreateReason.FIRE) == !open) ok++;
            n++;
            if (!create(main, PortalCreateEvent.CreateReason.NETHER_PAIR)) ok++;
            if (nether != null) {
                n++;
                if (!create(nether, PortalCreateEvent.CreateReason.FIRE)) ok++;
                n++;
                if (create(nether, PortalCreateEvent.CreateReason.NETHER_PAIR) == !open) ok++;
            }
            if (end != null) {
                n++;
                if (!create(end, PortalCreateEvent.CreateReason.END_PLATFORM)) ok++;
            }
            // 지나가기 (표지 엔티티 하나 — 주 월드 스폰에 잠깐)
            Location at = main.getSpawnLocation();
            m = main.spawn(at, Marker.class);
            Location toNether = nether == null ? null : new Location(nether, at.getX() / 8, 64, at.getZ() / 8);
            n++;
            if (travel(m, at, toNether, PortalType.NETHER) == !open) ok++; // 주 월드 → 네더 (네더 월드가 없으면 갈 곳 모름 = 네더로 봄)
            if (nether != null) {
                n++;
                if (!travel(m, toNether, at, PortalType.NETHER)) ok++; // 네더 → 주 월드
                n++;
                EntityPortalReadyEvent ready = new EntityPortalReadyEvent(m, nether, PortalType.NETHER);
                onReady(ready);
                if (ready.isCancelled() == !open) ok++;
            }
            if (end != null) {
                n++;
                if (!travel(m, at, new Location(end, 100, 50, 0), PortalType.ENDER)) ok++; // 엔드는 그대로
            }
        } finally {
            quiet = false;
            if (m != null) m.remove();
        }
        return new int[] {ok, n};
    }

    private boolean create(World w, PortalCreateEvent.CreateReason reason) {
        PortalCreateEvent e = new PortalCreateEvent(new ArrayList<>(), w, null, reason);
        onCreate(e);
        return e.isCancelled();
    }

    private boolean travel(Entity en, Location from, Location to, PortalType type) {
        EntityPortalEvent e = new EntityPortalEvent(en, from, to, 128, true, 16, type);
        onEntityPortal(e);
        return e.isCancelled();
    }
}
