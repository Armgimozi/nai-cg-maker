package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.List;
import org.bukkit.PortalType;
import org.bukkit.World.Environment;
import org.bukkit.event.player.PlayerTeleportEvent.TeleportCause;
import org.bukkit.event.world.PortalCreateEvent.CreateReason;

/**
 * 네더 막기 (0.3.7, 서버장 결정 "네더 막아") — 어느 차원문·어느 쪽이 막히나. 순수 ({@link NetherLock} 이 이벤트에 쓴다).
 * <ul>
 *   <li>들어가기만 막는다: 네더가 아닌 월드(오버월드·엔드·미궁·광산)에서 네더로 가는 네더 차원문.</li>
 *   <li>나가기는 늘 된다: 네더에서 나가는 차원문, 네더 쪽에서 불로 여는 차원문, 오버월드 쪽에 생기는 돌아오는 짝.</li>
 *   <li>엔드 차원문·엔드 관문·엔드 발판은 건드리지 않는다.</li>
 *   <li>{@code open} (config wild.nether: true) 이면 아무것도 막지 않는다.</li>
 * </ul>
 * 관리자 예외(크리에이티브)는 이 규칙 밖 — 리스너가 사람마다 본다.
 */
public final class NetherRule {

    private NetherRule() {}

    /** 차원문 종류. */
    public enum Portal { NETHER, END, OTHER }

    public static Portal of(TeleportCause c) {
        if (c == null) return Portal.OTHER;
        return switch (c) {
            case NETHER_PORTAL -> Portal.NETHER;
            case END_PORTAL, END_GATEWAY -> Portal.END;
            default -> Portal.OTHER;
        };
    }

    public static Portal of(PortalType t) {
        if (t == null) return Portal.OTHER;
        return switch (t) {
            case NETHER -> Portal.NETHER;
            case ENDER, END_GATEWAY -> Portal.END;
            default -> Portal.OTHER;
        };
    }

    /**
     * 차원문으로 지나가기를 막나.
     *
     * @param from 지금 있는 월드 (null = 모름 → 막지 않음)
     * @param to   갈 월드 (null = 이벤트가 안 알려 줌 → 바닐라대로 네더로 간다고 봄)
     */
    public static boolean blocksTravel(boolean open, Portal portal, Environment from, Environment to) {
        if (open || portal != Portal.NETHER || from == null) return false;
        if (from == Environment.NETHER) return false; // 네더에서 나가기는 늘 됨
        return to == null || to == Environment.NETHER;
    }

    /**
     * 차원문이 생기는 것을 막나.
     * FIRE = 흑요석 틀에 불 (네더가 아닌 월드면 네더로 가는 문) · NETHER_PAIR = 지나간 쪽에 게임이 만드는 짝
     * (네더 안에 생기면 누가 네더로 들어가는 중) · END_PLATFORM = 엔드 발판 (그대로).
     */
    public static boolean blocksCreate(boolean open, CreateReason reason, Environment world) {
        if (open || reason == null || world == null) return false;
        return switch (reason) {
            case FIRE -> world != Environment.NETHER;
            case NETHER_PAIR -> world == Environment.NETHER;
            default -> false;
        };
    }

    // ── 자가 진단 표 (단위 시험과 /labadmin plot selftest 가 같이 본다) ─────

    record Travel(boolean open, Portal portal, Environment from, Environment to, boolean blocked) {}

    record Create(boolean open, CreateReason reason, Environment world, boolean blocked) {}

    static List<Travel> travelTable() {
        Environment O = Environment.NORMAL, N = Environment.NETHER, E = Environment.THE_END, C = Environment.CUSTOM;
        List<Travel> t = new ArrayList<>();
        t.add(new Travel(false, Portal.NETHER, O, N, true));    // 오버월드 → 네더
        t.add(new Travel(false, Portal.NETHER, O, null, true)); // 갈 곳을 모름 = 바닐라 = 네더
        t.add(new Travel(false, Portal.NETHER, C, N, true));    // 미궁·광산 같은 다른 월드 → 네더
        t.add(new Travel(false, Portal.NETHER, E, N, true));    // 엔드에 만든 네더 차원문
        t.add(new Travel(false, Portal.NETHER, N, O, false));   // 네더 → 오버월드 (집으로)
        t.add(new Travel(false, Portal.NETHER, N, null, false));
        t.add(new Travel(false, Portal.NETHER, O, O, false));   // 다른 플러그인이 오버월드로 돌린 문
        t.add(new Travel(false, Portal.END, O, E, false));      // 엔드 차원문
        t.add(new Travel(false, Portal.END, E, O, false));      // 엔드에서 돌아옴
        t.add(new Travel(false, Portal.END, N, E, false));
        t.add(new Travel(false, Portal.OTHER, O, N, false));    // 명령·플러그인 순간이동은 이 규칙 밖
        t.add(new Travel(false, Portal.NETHER, null, N, false));
        t.add(new Travel(true, Portal.NETHER, O, N, false));    // wild.nether: true
        t.add(new Travel(true, Portal.NETHER, N, O, false));
        return t;
    }

    static List<Create> createTable() {
        Environment O = Environment.NORMAL, N = Environment.NETHER, E = Environment.THE_END, C = Environment.CUSTOM;
        List<Create> t = new ArrayList<>();
        t.add(new Create(false, CreateReason.FIRE, O, true));          // 오버월드 흑요석 틀에 불
        t.add(new Create(false, CreateReason.FIRE, C, true));
        t.add(new Create(false, CreateReason.FIRE, E, true));
        t.add(new Create(false, CreateReason.FIRE, N, false));         // 네더 쪽 틀 = 돌아가는 문
        t.add(new Create(false, CreateReason.NETHER_PAIR, N, true));   // 네더 안에 새 짝 = 들어가는 중
        t.add(new Create(false, CreateReason.NETHER_PAIR, O, false));  // 오버월드에 돌아오는 짝
        t.add(new Create(false, CreateReason.NETHER_PAIR, C, false));
        t.add(new Create(false, CreateReason.END_PLATFORM, E, false)); // 엔드 발판
        t.add(new Create(false, CreateReason.END_PLATFORM, O, false));
        t.add(new Create(false, null, O, false));
        t.add(new Create(false, CreateReason.FIRE, null, false));
        t.add(new Create(true, CreateReason.FIRE, O, false));
        t.add(new Create(true, CreateReason.NETHER_PAIR, N, false));
        return t;
    }

    /** 표대로 나오나 → [맞음, 전체]. */
    public static int[] selfCheck() {
        int ok = 0, n = 0;
        for (Travel c : travelTable()) {
            n++;
            if (blocksTravel(c.open(), c.portal(), c.from(), c.to()) == c.blocked()) ok++;
        }
        for (Create c : createTable()) {
            n++;
            if (blocksCreate(c.open(), c.reason(), c.world()) == c.blocked()) ok++;
        }
        for (TeleportCause c : TeleportCause.values()) {
            n++;
            Portal want = c == TeleportCause.NETHER_PORTAL ? Portal.NETHER
                    : c == TeleportCause.END_PORTAL || c == TeleportCause.END_GATEWAY ? Portal.END : Portal.OTHER;
            if (of(c) == want) ok++;
        }
        for (PortalType p : PortalType.values()) {
            n++;
            Portal want = p == PortalType.NETHER ? Portal.NETHER : p == PortalType.ENDER || p == PortalType.END_GATEWAY ? Portal.END : Portal.OTHER;
            if (of(p) == want) ok++;
        }
        return new int[] {ok, n};
    }
}
