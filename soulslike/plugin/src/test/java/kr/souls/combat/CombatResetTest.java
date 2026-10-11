package kr.souls.combat;

import org.bukkit.entity.Player;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1-0 계약: CombatReset 은 건 차례대로 모두 부르고, 한 일이 터져도 나머지를 부르며, 같은 이름은 바꾼다. */
class CombatResetTest {
    private final List<String> trace = new ArrayList<>();

    static Player fakePlayer() {
        return (Player) Proxy.newProxyInstance(Player.class.getClassLoader(), new Class<?>[] {Player.class}, (o, m, a) -> switch (m.getName()) {
            case "getName" -> "Tester";
            case "hashCode" -> 7;
            case "equals" -> o == a[0];
            case "toString" -> "Tester";
            default -> null;
        });
    }

    @BeforeEach
    void setUp() {
        CombatReset.clear();
        Logger quiet = Logger.getAnonymousLogger();
        quiet.setLevel(Level.OFF);
        new CombatReset(quiet, (p, line) -> trace.add(line));
    }

    @AfterEach
    void tearDown() {
        CombatReset.clear();
    }

    @Test
    void firesInOrderWithReason() {
        List<String> seen = new ArrayList<>();
        CombatReset.register("a", (p, why) -> seen.add("a:" + why));
        CombatReset.register("b", (p, why) -> seen.add("b:" + why));
        Player p = fakePlayer();
        assertEquals(2, CombatReset.fire(p, CombatReset.Why.DEATH));
        assertEquals(List.of("a:DEATH", "b:DEATH"), seen);
        assertEquals(List.of("a", "b"), CombatReset.owners());
        assertEquals(List.of("RESET why=DEATH ran=2 owners=a,b"), trace);
    }

    @Test
    void sameOwnerReplaces() {
        List<String> seen = new ArrayList<>();
        CombatReset.register("a", (p, why) -> seen.add("old"));
        CombatReset.register("a", (p, why) -> seen.add("new"));
        CombatReset.fire(fakePlayer(), CombatReset.Why.QUIT);
        assertEquals(List.of("new"), seen, "/souls reload 뒤에 다시 걸어도 한 번만");
    }

    @Test
    void oneFailureDoesNotStopOthers() {
        List<String> seen = new ArrayList<>();
        CombatReset.register("boom", (p, why) -> {
            throw new IllegalStateException("x");
        });
        CombatReset.register("after", (p, why) -> seen.add("after"));
        assertEquals(1, CombatReset.fire(fakePlayer(), CombatReset.Why.WORLD));
        assertEquals(List.of("after"), seen);
        assertTrue(trace.get(0).contains("ran=1"));
    }

    @Test
    void unregisterAndNulls() {
        CombatReset.register("a", (p, why) -> {});
        CombatReset.unregister("a");
        assertEquals(List.of(), CombatReset.owners());
        assertEquals(0, CombatReset.fire(null, CombatReset.Why.DISABLE));
        assertEquals(0, CombatReset.fire(fakePlayer(), null));
    }

    @Test
    void allReasons() {
        assertEquals(List.of("QUIT", "DEATH", "WORLD", "DISABLE", "JOIN"),
                java.util.Arrays.stream(CombatReset.Why.values()).map(Enum::name).toList());
    }
}
