package kr.souls;

import org.bukkit.plugin.Plugin;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Proxy;
import java.util.List;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/** M1 P1-0: Ticker 의 빈 자리 (M1_PLAN 0.6). 묶음이 into 를 어떤 차례로 불러도 자리의 차례대로 돈다. */
class TickerSlotTest {
    private static Ticker ticker() {
        Plugin p = (Plugin) Proxy.newProxyInstance(Plugin.class.getClassLoader(), new Class<?>[] {Plugin.class}, (o, m, a) -> switch (m.getName()) {
            case "getLogger" -> Logger.getAnonymousLogger();
            case "hashCode" -> 1;
            case "equals" -> o == a[0];
            default -> null;
        });
        return new Ticker(p);
    }

    /** Souls.onEnable 과 같은 차례로 자리를 둔다. */
    private static Ticker planOrder() {
        Ticker t = ticker();
        Ticker.Task noop = now -> {};
        t.add("load", noop);
        t.add("stamina", noop);
        t.slot("input");
        t.slot("moves");
        t.add("roll", noop);
        t.add("tap", noop);
        t.slot("brains");
        t.slot("queue");
        t.slot("poise");
        t.slot("lock");
        t.add("hud", noop);
        t.add("titles", noop);
        t.add("rings", noop);
        return t;
    }

    @Test
    void emptySlotsKeepThePlanOrder() {
        assertEquals(List.of("load", "stamina", "input", "moves", "roll", "tap", "brains", "queue", "poise", "lock", "hud", "titles", "rings"),
                planOrder().order());
    }

    @Test
    void intoFillsSlotsWhateverTheCallOrder() {
        Ticker t = planOrder();
        Ticker.Task noop = now -> {};
        // 늦게 끝난 묶음이 먼저 부르더라도
        t.into("lock", "lockon", noop);
        t.into("brains", "dojo", noop);
        t.into("input", "router", noop);
        t.into("brains", "brain", noop);
        t.into("moves", "runner", noop);
        assertEquals(List.of("load", "stamina", "input", "input/router", "moves", "moves/runner", "roll", "tap", "brains", "brains/dojo",
                "brains/brain", "queue", "poise", "lock", "lock/lockon", "hud", "titles", "rings"), t.order());
        // 같은 이름은 바꾼다
        t.into("brains", "dojo", noop);
        assertEquals(18, t.order().size());
        assertThrows(IllegalArgumentException.class, () -> t.into("nope", "x", noop));
    }

    @Test
    void runsInSlotOrder() throws Exception {
        Ticker t = planOrder();
        StringBuilder ran = new StringBuilder();
        t.into("queue", "q", now -> ran.append("q"));
        t.into("brains", "b", now -> ran.append("b"));
        t.into("input", "i", now -> ran.append("i"));
        var run = Ticker.class.getDeclaredMethod("run");
        run.setAccessible(true);
        run.invoke(t);
        assertEquals("ibq", ran.toString());
        assertEquals(1, t.now());
    }
}
