package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.papermc.paper.event.entity.EntityPortalReadyEvent;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.PortalType;
import org.bukkit.World;
import org.bukkit.World.Environment;
import org.bukkit.entity.Boat;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.entity.EntityPortalEvent;
import org.bukkit.event.player.PlayerPortalEvent;
import org.bukkit.event.player.PlayerTeleportEvent.TeleportCause;
import org.bukkit.event.world.PortalCreateEvent;
import org.bukkit.event.world.PortalCreateEvent.CreateReason;
import org.junit.jupiter.api.Test;

/**
 * 네더 막기 리스너 (0.3.7): 실제 이벤트 객체로 — 들어가기 막음 (플레이어·물건·보트에 탄 사람) · 나가기·엔드 그대로 · 크리에이티브 관리자 ·
 * wild.nether: true · 안내 1초에 한 번 · 리스너 차례 (집터 규칙 LOW 보다 먼저 = LOWEST).
 */
class NetherLockTest {

    static final World OVER = world("world", Environment.NORMAL);
    static final World NETHER = world("world_nether", Environment.NETHER);
    static final World END = world("world_the_end", Environment.THE_END);
    static final World MINE = world("labyrinth_mine", Environment.CUSTOM);

    static World world(String name, Environment env) {
        return (World) Proxy.newProxyInstance(World.class.getClassLoader(), new Class<?>[] {World.class}, (self, m, a) -> switch (m.getName()) {
            case "getEnvironment" -> env;
            case "getName" -> name;
            case "toString" -> name;
            case "hashCode" -> System.identityHashCode(self);
            case "equals" -> self == a[0];
            default -> zero(m);
        });
    }

    /** 가짜 플레이어 — 받은 액션바 글은 bars 에. */
    static final class Fake {
        final UUID id = UUID.randomUUID();
        final List<Object> bars = new ArrayList<>();
        boolean admin;
        GameMode mode = GameMode.SURVIVAL;
        World world = OVER;
        final Player player;

        Fake() {
            player = (Player) Proxy.newProxyInstance(Player.class.getClassLoader(), new Class<?>[] {Player.class}, (self, m, a) -> switch (m.getName()) {
                case "getUniqueId" -> id;
                case "hasPermission" -> admin;
                case "getGameMode" -> mode;
                case "getWorld" -> world;
                case "getPassengers" -> List.of();
                case "sendActionBar" -> {
                    bars.add(a[0]);
                    yield null;
                }
                case "hashCode" -> System.identityHashCode(self);
                case "equals" -> self == a[0];
                case "toString" -> "Fake";
                default -> zero(m);
            });
        }
    }

    static <T extends Entity> T entity(Class<T> type, World w, List<Entity> riders) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, (self, m, a) -> switch (m.getName()) {
            case "getWorld" -> w;
            case "getPassengers" -> riders;
            case "hashCode" -> System.identityHashCode(self);
            case "equals" -> self == a[0];
            case "toString" -> type.getSimpleName();
            default -> zero(m);
        }));
    }

    static Object zero(Method m) {
        Class<?> r = m.getReturnType();
        if (r == boolean.class) return false;
        if (r == int.class) return 0;
        if (r == long.class) return 0L;
        if (r == double.class) return 0d;
        if (r == float.class) return 0f;
        if (r == short.class) return (short) 0;
        if (r == byte.class) return (byte) 0;
        if (r == char.class) return (char) 0;
        return null;
    }

    static Location at(World w) { return new Location(w, 10, 70, 10); }

    static boolean playerPortal(NetherLock l, Fake f, World from, World to, TeleportCause cause) {
        f.world = from;
        PlayerPortalEvent e = new PlayerPortalEvent(f.player, at(from), to == null ? null : at(to), cause);
        l.onPlayerPortal(e);
        return e.isCancelled();
    }

    static boolean entityPortal(NetherLock l, Entity en, World from, World to, PortalType type) {
        EntityPortalEvent e = new EntityPortalEvent(en, at(from), to == null ? null : at(to), 128, true, 16, type);
        l.onEntityPortal(e);
        return e.isCancelled();
    }

    static boolean create(NetherLock l, World w, Entity by, CreateReason r) {
        PortalCreateEvent e = new PortalCreateEvent(new ArrayList<>(), w, by, r);
        l.onCreate(e);
        return e.isCancelled();
    }

    static NetherLock closed() { return new NetherLock(null, () -> false); }

    @Test
    void playerCannotEnterButCanLeave() {
        NetherLock l = closed();
        Fake f = new Fake();
        assertTrue(playerPortal(l, f, OVER, NETHER, TeleportCause.NETHER_PORTAL), "오버월드 → 네더 막힘");
        assertTrue(playerPortal(l, f, MINE, NETHER, TeleportCause.NETHER_PORTAL), "다른 월드 → 네더 막힘");
        assertFalse(playerPortal(l, f, NETHER, OVER, TeleportCause.NETHER_PORTAL), "네더 → 오버월드 됨 (이미 네더에 있던 사람)");
        assertFalse(playerPortal(l, f, OVER, END, TeleportCause.END_PORTAL), "엔드 차원문 그대로");
        assertFalse(playerPortal(l, f, END, OVER, TeleportCause.END_PORTAL), "엔드에서 돌아옴 그대로");
        assertEquals(2, l.blockedTravel);
        assertEquals(1, f.bars.size(), "안내는 1초에 한 번");
    }

    @Test
    void readyEventIsTheFirstGate() {
        NetherLock l = closed();
        Fake f = new Fake();
        EntityPortalReadyEvent in = new EntityPortalReadyEvent(f.player, NETHER, PortalType.NETHER);
        l.onReady(in);
        assertTrue(in.isCancelled(), "네더로 갈 준비 = 취소 (차원문 기다림이 처음으로)");
        f.world = NETHER;
        EntityPortalReadyEvent out = new EntityPortalReadyEvent(f.player, OVER, PortalType.NETHER);
        l.onReady(out);
        assertFalse(out.isCancelled(), "네더에서 나가기");
        f.world = OVER;
        EntityPortalReadyEvent none = new EntityPortalReadyEvent(f.player, null, PortalType.NETHER);
        l.onReady(none);
        assertFalse(none.isCancelled(), "갈 곳이 없는 문 (네더를 끈 서버) 은 건드리지 않음");
    }

    @Test
    void itemsMobsAndVehiclesWithRiders() {
        NetherLock l = closed();
        Item item = entity(Item.class, OVER, List.of());
        assertTrue(entityPortal(l, item, OVER, NETHER, PortalType.NETHER), "던진 물건");
        assertFalse(entityPortal(l, item, NETHER, OVER, PortalType.NETHER), "네더에서 나오는 물건");
        assertFalse(entityPortal(l, item, OVER, END, PortalType.ENDER), "엔드 차원문");
        Fake rider = new Fake();
        Boat boat = entity(Boat.class, OVER, List.of(rider.player));
        assertTrue(entityPortal(l, boat, OVER, NETHER, PortalType.NETHER), "사람이 탄 보트");
        assertEquals(1, rider.bars.size(), "탄 사람에게 안내");
        Fake inner = new Fake();
        Boat outer = entity(Boat.class, OVER, List.of(entity(Boat.class, OVER, List.of(inner.player))));
        assertEquals(List.of(inner.player), NetherLock.players(outer), "여러 겹 탄 사람");
    }

    @Test
    void portalCreation() {
        NetherLock l = closed();
        Fake f = new Fake();
        assertTrue(create(l, OVER, f.player, CreateReason.FIRE), "오버월드 흑요석 틀에 불");
        assertTrue(create(l, MINE, null, CreateReason.FIRE), "발사기·불 번짐 (사람 없음)");
        assertFalse(create(l, NETHER, f.player, CreateReason.FIRE), "네더 쪽 틀 = 돌아가는 문");
        assertTrue(create(l, NETHER, f.player, CreateReason.NETHER_PAIR), "네더 안에 새 짝");
        assertFalse(create(l, OVER, f.player, CreateReason.NETHER_PAIR), "오버월드에 돌아오는 짝");
        assertFalse(create(l, END, null, CreateReason.END_PLATFORM), "엔드 발판");
        assertEquals(3, l.blockedCreate);
        assertEquals(1, f.bars.size());
    }

    @Test
    void creativeAdminPassesLikeTheTerrainLock() {
        NetherLock l = closed();
        Fake admin = new Fake();
        admin.admin = true;
        admin.mode = GameMode.CREATIVE;
        assertFalse(playerPortal(l, admin, OVER, NETHER, TeleportCause.NETHER_PORTAL), "크리에이티브 관리자는 지나감");
        assertFalse(create(l, OVER, admin.player, CreateReason.FIRE));
        assertEquals(1, admin.bars.size(), "관리자라 지나간다는 안내 (1초에 한 번)");
        Fake friend = new Fake();
        Boat boat = entity(Boat.class, OVER, List.of(admin.player, friend.player));
        assertFalse(entityPortal(l, boat, OVER, NETHER, PortalType.NETHER), "관리자가 탄 보트");
        Fake survival = new Fake();
        survival.admin = true; // 관리자여도 서바이벌이면 막힘
        assertTrue(playerPortal(l, survival, OVER, NETHER, TeleportCause.NETHER_PORTAL));
        Fake creative = new Fake();
        creative.mode = GameMode.CREATIVE; // 크리에이티브여도 관리자가 아니면 막힘
        assertTrue(playerPortal(l, creative, OVER, NETHER, TeleportCause.NETHER_PORTAL));
        assertEquals(0, l.blockedCreate);
        assertEquals(2, l.blockedTravel);
    }

    @Test
    void openSwitchTurnsItAllOff() {
        AtomicBoolean open = new AtomicBoolean(true);
        NetherLock l = new NetherLock(null, open::get);
        Fake f = new Fake();
        assertFalse(playerPortal(l, f, OVER, NETHER, TeleportCause.NETHER_PORTAL));
        assertFalse(create(l, OVER, f.player, CreateReason.FIRE));
        assertFalse(create(l, NETHER, f.player, CreateReason.NETHER_PAIR));
        assertTrue(f.bars.isEmpty());
        open.set(false); // /labadmin reload 로 바꾼 것처럼
        assertTrue(playerPortal(l, f, OVER, NETHER, TeleportCause.NETHER_PORTAL));
    }

    @Test
    void blockingHandlersRunFirstAndSkipCancelled() {
        Map<String, List<EventHandler>> h = new HashMap<>();
        for (Method m : NetherLock.class.getDeclaredMethods()) {
            EventHandler a = m.getAnnotation(EventHandler.class);
            if (a != null) h.computeIfAbsent(m.getParameterTypes()[0].getSimpleName(), k -> new ArrayList<>()).add(a);
        }
        for (String ev : List.of("PortalCreateEvent", "PlayerPortalEvent", "EntityPortalEvent", "EntityPortalReadyEvent")) {
            assertTrue(h.containsKey(ev), ev);
            assertTrue(h.get(ev).stream().anyMatch(a -> a.priority() == EventPriority.LOWEST && a.ignoreCancelled()), ev + " LOWEST");
        }
        assertTrue(h.get("PortalCreateEvent").stream().anyMatch(a -> a.priority() == EventPriority.MONITOR && !a.ignoreCancelled()),
                "막힌 돌아오는 짝을 보는 MONITOR");
        assertTrue(h.containsKey("PlayerJoinEvent"), "네더에서 접속하면 안내");
    }
}
