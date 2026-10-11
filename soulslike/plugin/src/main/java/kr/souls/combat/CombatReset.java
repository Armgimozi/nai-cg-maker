package kr.souls.combat;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiConsumer;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * 전투 상태를 거두는 한 곳 (M1_PLAN 0.8, R33). 묶음마다 자기 파일에서 {@link #register} 로 거둘 일을 걸고, DeathFlow·나가기·다른
 * 세계로 가기·플러그인 끄기·접속은 여기서만 부른다. P1-0 뒤로는 아무도 DeathFlow 를 고치지 않는다.
 * <ul>
 *   <li>QUIT: 나갈 때 (HIGHEST: Stamina 가 MONITOR 에서 CombatState 를 지우기 전, 바닐라가 플레이어 파일을 쓰기 전).</li>
 *   <li>DEATH: 죽는 순간 (DeathFlow.onDeath, 세계와 상관없이).</li>
 *   <li>WORLD: 다른 세계에 닿은 뒤 (PlayerChangedWorldEvent).</li>
 *   <li>DISABLE: 플러그인을 끌 때, 접속 중인 사람마다 (서버가 플레이어 파일을 쓰기 전).</li>
 *   <li>JOIN: 들어올 때 (LOWEST). 서버가 거두지 못하고 꺼졌을 때 플레이어 파일에 남은 값 (걷기 속도는 플레이어 파일에 저장된다,
 *       PS 의 S4) 을 바로잡는다. 거둘 것이 없으면 아무것도 하지 않게 쓴다.</li>
 * </ul>
 * 걸린 일은 건 차례대로 돈다. 한 일이 터져도 나머지는 돈다 (처음 몇 번만 기록). 같은 이름으로 다시 걸면 바꾼다 (/souls reload 뒤에도 둘이 되지 않는다).
 */
public final class CombatReset implements Listener {
    /** 왜 거두는가. */
    public enum Why { QUIT, DEATH, WORLD, DISABLE, JOIN }

    private static final Map<String, BiConsumer<Player, Why>> HANDLERS = new LinkedHashMap<>();
    private static final Map<String, Integer> ERRORS = new LinkedHashMap<>();
    private static Logger log = Logger.getLogger("Soulslike");
    /** 거둘 때마다 부른다 (시험 줄 RESET why= ran= owners=, Souls.test). Souls 가 끼운다 */
    private static BiConsumer<Player, String> trace = (p, s) -> {};

    public CombatReset(Logger logger, BiConsumer<Player, String> traceLine) {
        log = logger;
        trace = traceLine == null ? (p, s) -> {} : traceLine;
    }

    /** owner (묶음·체계 이름) 의 거둘 일을 건다. 같은 owner 면 바꾼다. */
    public static synchronized void register(String owner, BiConsumer<Player, Why> fn) {
        if (owner == null || fn == null) throw new IllegalArgumentException("owner/fn");
        HANDLERS.put(owner, fn);
    }

    /** owner 의 일을 뗀다 (없으면 아무것도 하지 않는다). */
    public static synchronized void unregister(String owner) {
        HANDLERS.remove(owner);
    }

    /** 걸린 이름들 (건 차례). */
    public static synchronized List<String> owners() {
        return Collections.unmodifiableList(new ArrayList<>(HANDLERS.keySet()));
    }

    /** 이 사람을 지금 거둔다. 돈 일의 수. */
    public static int fire(Player p, Why why) {
        if (p == null || why == null) return 0;
        List<Map.Entry<String, BiConsumer<Player, Why>>> list;
        synchronized (CombatReset.class) {
            list = new ArrayList<>(HANDLERS.entrySet());
        }
        int ran = 0;
        for (var e : list) {
            try {
                e.getValue().accept(p, why);
                ran++;
            } catch (Throwable t) {
                int n = ERRORS.merge(e.getKey(), 1, Integer::sum);
                if (n <= 5) log.log(Level.SEVERE, "CombatReset " + e.getKey() + " (" + why + ") 오류", t);
            }
        }
        StringBuilder names = new StringBuilder();
        for (var e : list) names.append(names.length() == 0 ? "" : ",").append(e.getKey());
        trace.accept(p, "RESET why=" + why + " ran=" + ran + " owners=" + (names.length() == 0 ? "-" : names)); // lang-machine
        return ran;
    }

    /** 접속 중인 모든 사람을 거둔다 (플러그인 끄기). */
    public static void fireAll(Why why) {
        for (Player p : Bukkit.getOnlinePlayers()) fire(p, why);
    }

    /** 플러그인을 끈 뒤 (다시 켜면 새로 건다). */
    public static synchronized void clear() {
        HANDLERS.clear();
        ERRORS.clear();
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onQuit(PlayerQuitEvent e) {
        fire(e.getPlayer(), Why.QUIT);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) {
        fire(e.getPlayer(), Why.WORLD);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onJoin(PlayerJoinEvent e) {
        fire(e.getPlayer(), Why.JOIN);
    }
}
