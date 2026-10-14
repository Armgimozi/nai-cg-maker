package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import kr.labyrinth.content.Params;
import org.junit.jupiter.api.Test;

class PatternSchedulerTest {

    private static Params p(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return Params.of(m);
    }

    private static Map<String, Params> grove() {
        Map<String, Params> m = new HashMap<>();
        m.put("vine_lash", p("cooldown", 6, "damage", 1.3));
        m.put("root_snare", p("cooldown", 11));
        m.put("rampage_charge", p("cooldown", 16));
        m.put("silk_tether", p("interval", 20));
        m.put("rising_flood", p("stages", 3));
        return m;
    }

    @Test
    void classifiesPatternKindsPerGdd83() {
        assertEquals(PatternScheduler.Kind.COOLDOWN, PatternScheduler.kindOf(p("cooldown", 5)));
        assertEquals(PatternScheduler.Kind.INTERVAL, PatternScheduler.kindOf(p("interval", 20)));
        assertEquals(PatternScheduler.Kind.SYSTEM, PatternScheduler.kindOf(p("stages", 3)));
        // cooldown 이 interval 보다 우선
        assertEquals(PatternScheduler.Kind.COOLDOWN, PatternScheduler.kindOf(p("cooldown", 5, "interval", 20)));
    }

    @Test
    void firstUseWaitsHalfCooldownThenPicksReady() {
        PatternScheduler s = new PatternScheduler(new Random(1));
        s.setPhase(List.of("vine_lash"), grove(), 0);
        assertNull(s.next(0, null));
        assertNull(s.next(59, null)); // 6초 쿨다운의 절반 = 60틱
        assertEquals("vine_lash", s.next(60, null));
        // 바로 다시 못 씀 (쿨다운 120틱)
        assertNull(s.next(100, null));
        assertEquals("vine_lash", s.next(180, null));
    }

    @Test
    void enforcesMinimumGapBetweenPatterns() {
        PatternScheduler s = new PatternScheduler(new Random(2));
        Map<String, Params> m = new HashMap<>();
        m.put("a", p("cooldown", 1, "first_delay", 0));
        m.put("b", p("cooldown", 1, "first_delay", 0));
        s.setPhase(List.of("a", "b"), m, 0);
        String first = s.next(0, null);
        assertNotNull(first);
        assertNull(s.next(PatternScheduler.MIN_GAP_TICKS - 1, null), "1.2초 간격 안에는 다음 패턴 없음");
        String second = s.next(PatternScheduler.MIN_GAP_TICKS, null);
        assertNotNull(second);
        assertNotEquals(first, second, "직전 패턴과 다른 것 우선");
    }

    @Test
    void prefersDifferentPatternThanLastWhenSeveralReady() {
        for (int seed = 0; seed < 50; seed++) {
            PatternScheduler s = new PatternScheduler(new Random(seed));
            Map<String, Params> m = new HashMap<>();
            m.put("a", p("cooldown", 0.1, "first_delay", 0));
            m.put("b", p("cooldown", 0.1, "first_delay", 0));
            m.put("c", p("cooldown", 0.1, "first_delay", 0));
            s.setPhase(List.of("a", "b", "c"), m, 0);
            String prev = s.next(0, null);
            long t = 0;
            for (int i = 0; i < 20; i++) {
                t += PatternScheduler.MIN_GAP_TICKS;
                String k = s.next(t, null);
                assertNotNull(k);
                assertNotEquals(prev, k);
                prev = k;
            }
        }
    }

    @Test
    void weightsBiasSelection() {
        PatternScheduler s = new PatternScheduler(new Random(42));
        Map<String, Params> m = new HashMap<>();
        m.put("heavy", p("cooldown", 0.05, "first_delay", 0, "weight", 9));
        m.put("light", p("cooldown", 0.05, "first_delay", 0, "weight", 1));
        m.put("filler", p("cooldown", 0.05, "first_delay", 0, "weight", 1));
        s.setPhase(List.of("heavy", "light", "filler"), m, 0);
        int heavy = 0, total = 0;
        long t = 0;
        for (int i = 0; i < 3000; i++) {
            String k = s.next(t, null);
            if (k != null) {
                total++;
                if (k.equals("heavy")) heavy++;
            }
            t += PatternScheduler.MIN_GAP_TICKS;
        }
        // 직전과 다른 것 우선 규칙 때문에 heavy 는 최대 절반 가까이 — 그래도 균등(1/3)보다 확실히 많아야 한다
        assertTrue(heavy > total * 0.4, "heavy=" + heavy + "/" + total);
    }

    @Test
    void usablePredicateFiltersPatterns() {
        PatternScheduler s = new PatternScheduler(new Random(3));
        Map<String, Params> m = new HashMap<>();
        m.put("adds", p("cooldown", 1, "first_delay", 0));
        m.put("slam", p("cooldown", 1, "first_delay", 0));
        s.setPhase(List.of("adds", "slam"), m, 0);
        assertEquals("slam", s.next(0, k -> !k.equals("adds")));
        assertNull(s.next(PatternScheduler.MIN_GAP_TICKS, k -> false));
    }

    @Test
    void intervalPatternsRunOnTheirOwnTimer() {
        PatternScheduler s = new PatternScheduler(new Random(4));
        s.setPhase(List.of("vine_lash", "silk_tether"), grove(), 0);
        assertTrue(s.dueIntervals(199).isEmpty()); // 첫 실행 = 간격의 절반(10초)
        assertEquals(List.of("silk_tether"), s.dueIntervals(200));
        assertTrue(s.dueIntervals(399).isEmpty());
        assertEquals(List.of("silk_tether"), s.dueIntervals(600));
        // interval 패턴은 쿨다운 선택에 끼지 않는다
        for (long t = 0; t < 2000; t += 30) {
            String k = s.next(t, null);
            if (k != null) assertEquals("vine_lash", k);
        }
    }

    @Test
    void systemsListedAndPhaseSwapKeepsCooldowns() {
        PatternScheduler s = new PatternScheduler(new Random(5));
        s.setPhase(List.of("vine_lash", "rising_flood"), grove(), 0);
        assertEquals(List.of("rising_flood"), s.systems());
        assertEquals("vine_lash", s.next(60, null));
        long readyAt = s.entry("vine_lash").readyAt();
        s.setPhase(List.of("vine_lash", "root_snare"), grove(), 100);
        assertEquals(readyAt, s.entry("vine_lash").readyAt(), "남아 있는 패턴은 쿨다운 유지");
        assertTrue(s.systems().isEmpty());
        assertFalse(s.active("rising_flood"));
        assertTrue(s.active("root_snare"));
        // 새로 들어온 패턴도 첫 사용은 절반 쿨다운 뒤
        assertTrue(s.entry("root_snare").readyAt() >= 100 + 100);
    }

    @Test
    void cooldownMultiplierShortensCooldowns() {
        PatternScheduler s = new PatternScheduler(new Random(6));
        s.setCooldownMult(0.5);
        Map<String, Params> m = new HashMap<>();
        m.put("x", p("cooldown", 10, "first_delay", 0));
        s.setPhase(List.of("x"), m, 0);
        assertEquals("x", s.next(0, null));
        assertEquals(100, s.entry("x").readyAt()); // 200틱 × 0.5
    }

    @Test
    void busyUntilDelaysNextPattern() {
        PatternScheduler s = new PatternScheduler(new Random(7));
        Map<String, Params> m = new HashMap<>();
        m.put("x", p("cooldown", 0.1, "first_delay", 0));
        m.put("y", p("cooldown", 0.1, "first_delay", 0));
        s.setPhase(List.of("x", "y"), m, 0);
        assertNotNull(s.next(0, null));
        s.busyUntil(100);
        assertNull(s.next(100 + PatternScheduler.MIN_GAP_TICKS - 1, null));
        assertNotNull(s.next(100 + PatternScheduler.MIN_GAP_TICKS, null));
    }
}
