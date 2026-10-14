package kr.labyrinth.classes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

/** 직업 순수 로직: 마나·쿨다운·상태이상 중첩·버프 합산·보호막. */
class ClassLogicTest {

    private static final double EPS = 1e-6;

    // ── 마나 ──────────────────────────────────────────────────────────────

    @Test
    void manaRegeneratesOverTimeAndCaps() {
        ManaPool m = new ManaPool(10, 0);
        // 재생 2.4/초 (비전술사 mana_regen 2.4 + WIS 0) → 5초 후 22
        assertEquals(22.0, m.current(100, 2.4, 5000), EPS);
        // 상한
        assertEquals(100.0, m.current(100, 2.4, 1_000_000), EPS);
    }

    @Test
    void manaRegenScalesWithWis() {
        // StatCalculator: mana_regen = 직업 + WIS × 0.05. WIS 20 → +1/초
        ManaPool low = new ManaPool(0, 0);
        ManaPool high = new ManaPool(0, 0);
        double base = 1.6;
        assertEquals(16.0, low.current(200, base, 10_000), EPS);
        assertEquals(26.0, high.current(200, base + 20 * 0.05, 10_000), EPS);
    }

    @Test
    void manaSpendFailsWhenInsufficientAndDoesNotChange() {
        ManaPool m = new ManaPool(15, 0);
        assertFalse(m.spend(20, 100, 0, 0));
        assertEquals(15.0, m.current(100, 0, 0), EPS);
        assertTrue(m.spend(15, 100, 0, 0));
        assertEquals(0.0, m.current(100, 0, 0), EPS);
        m.restore(500, 100, 0, 0);
        assertEquals(100.0, m.current(100, 0, 0), EPS);
    }

    @Test
    void manaClampsWhenMaxDrops() {
        ManaPool m = new ManaPool(120, 0);
        assertEquals(80.0, m.current(80, 1, 0), EPS); // 장비를 벗어 최대 MP 가 줄면 잘린다
    }

    // ── 쿨다운 ────────────────────────────────────────────────────────────

    @Test
    void cooldownReductionShortensCooldown() {
        assertEquals(6.0, CooldownTracker.effective(6.0, 0), EPS);
        assertEquals(3.6, CooldownTracker.effective(6.0, 0.4), EPS);
    }

    @Test
    void cooldownAdvancesAndReportsReady() {
        CooldownTracker t = new CooldownTracker();
        t.start("shield_bash", 6.0);
        assertFalse(t.ready("shield_bash"));
        assertNull(t.advance(5.0, 1.0));
        assertEquals(1.0, t.remaining("shield_bash"), EPS);
        assertEquals("shield_bash", t.advance(1.0, 1.0));
        assertTrue(t.ready("shield_bash"));
        assertEquals(0.0, t.remaining("unknown"), EPS);
    }

    @Test
    void cooldownSlowMakesItTickSlower() {
        CooldownTracker t = new CooldownTracker();
        t.start("a", 10);
        t.advance(10, 0.7); // cooldown_slow 0.3 → 7초만 흐름
        assertEquals(3.0, t.remaining("a"), EPS);
        t.set("a", 1.5);
        assertEquals(1.5, t.remaining("a"), EPS);
        t.reset("a");
        assertTrue(t.isEmpty());
    }

    // ── 상태이상 중첩 ─────────────────────────────────────────────────────

    @Test
    void frostStacksToFiveAndSignalsMax() {
        EffectStack s = new EffectStack();
        UUID src = UUID.randomUUID();
        for (int i = 1; i <= 4; i++) {
            EffectStack.Applied a = s.apply("frost", 1, 1, 6000, src, 0, 5);
            assertFalse(a.reachedMax());
            assertEquals(i, s.stacks("frost", 0));
        }
        assertTrue(s.apply("frost", 1, 1, 6000, src, 0, 5).reachedMax());
        assertEquals(5, s.stacks("frost", 0));
        // 상한 넘게 쌓아도 5, 다시 '도달' 신호는 없음
        assertFalse(s.apply("frost", 1, 2, 6000, src, 100, 5).reachedMax());
        assertEquals(5, s.stacks("frost", 100));
    }

    @Test
    void multiStackApplicationAndRefreshDuration() {
        EffectStack s = new EffectStack();
        s.apply("infection", 1, 2, 8000, null, 0, 5);
        assertEquals(2, s.stacks("infection", 0));
        s.apply("infection", 1, 1, 8000, null, 5000, 5);
        // 중첩형은 지속시간이 새로 갱신된다
        assertTrue(s.has("infection", 12_000));
        assertFalse(s.has("infection", 13_001));
    }

    @Test
    void slowTakesMaxPotencyAndLongerDuration() {
        EffectStack s = new EffectStack();
        s.apply("slow", 0.3, 1, 4000, null, 0, 1);
        s.apply("slow", 0.2, 1, 1000, null, 0, 1);
        assertEquals(0.3, s.value("slow", 500), EPS);
        assertTrue(s.has("slow", 3500)); // 짧은 새 효과가 긴 기존 효과를 줄이지 않는다
        s.apply("slow", 0.5, 1, 1000, null, 3600, 1);
        assertEquals(0.5, s.value("slow", 3700), EPS);
    }

    @Test
    void dotRefreshKeepsStrongerSource() {
        EffectStack s = new EffectStack();
        UUID weak = UUID.randomUUID();
        UUID strong = UUID.randomUUID();
        s.apply("bleed", 30, 1, 4000, strong, 0, 1);
        s.apply("bleed", 10, 1, 6000, weak, 1000, 1);
        EffectStack.Entry e = s.get("bleed", 1000);
        assertEquals(30, e.value, EPS);
        assertEquals(strong, e.source);
        assertTrue(s.has("bleed", 6500)); // 지속시간은 긴 쪽으로
    }

    @Test
    void cleanseRemovesHarmfulButNotStun() {
        EffectStack s = new EffectStack();
        s.apply("poison", 5, 1, 5000, null, 0, 1);
        s.apply("frost", 1, 3, 6000, null, 0, 5);
        s.apply("stun", 1, 1, 1000, null, 0, 1);
        List<String> removed = s.cleanse();
        assertTrue(removed.contains("poison"));
        assertTrue(removed.contains("frost"));
        assertTrue(s.has("stun", 0));
        assertEquals(0, s.stacks("frost", 0));
    }

    @Test
    void instantEffectsAreNotStoredAndExpiryWorks() {
        EffectStack s = new EffectStack();
        assertNull(s.apply("knockback", 1, 1, 0, null, 0, 1).entry());
        assertTrue(s.isEmpty());
        s.apply("root", 1, 1, 2000, null, 0, 1);
        assertEquals(1, s.expire(2000).size());
        assertTrue(s.isEmpty());
    }

    // ── 버프 ──────────────────────────────────────────────────────────────

    @Test
    void sameSourceBuffRefreshesDifferentSourcesSum() {
        BuffSet b = new BuffSet();
        b.put("sacred_ward", Map.of("damage", 0.10), 6000);
        b.put("sacred_ward", Map.of("damage", 0.10), 8000); // 다시 걸면 갱신(합산 아님)
        assertEquals(0.10, b.total("damage_mult", 0), EPS);
        b.put("blood_frenzy", Map.of("damage", 0.20, "lifesteal", 0.10), 4000);
        assertEquals(0.30, b.total("damage_mult", 0), EPS);
        assertEquals(0.10, b.total("lifesteal", 0), EPS);
        // blood_frenzy 만료 후
        assertEquals(0.10, b.total("damage_mult", 5000), EPS);
        assertTrue(b.expire(5000));
        assertTrue(b.has("sacred_ward", 7999));
        assertFalse(b.has("sacred_ward", 8000));
    }

    @Test
    void buffKeysMapToStatBlockKeys() {
        assertEquals("damage_mult", BuffSet.statKey("damage"));
        assertEquals("evasion", BuffSet.statKey("evasion"));
    }

    // ── 보호막 ────────────────────────────────────────────────────────────

    @Test
    void shieldAbsorbsSoonestExpiringFirst() {
        ShieldPool p = new ShieldPool();
        p.add("sacred_ward", 50, 6000);
        p.add("guardian_oath", 30, 3000);
        assertEquals(0.0, p.absorb(40, 0), EPS);   // oath 30 먼저 소진, ward 10 사용
        assertEquals(40.0, p.total(0), EPS);
        assertEquals(10.0, p.absorb(50, 0), EPS);  // 남은 40 흡수, 10 통과
        assertTrue(p.isEmpty());
    }

    @Test
    void shieldSameSourceKeepsLargerAndStackingCaps() {
        ShieldPool p = new ShieldPool();
        p.add("a", 20, 1000);
        p.add("a", 10, 2000);
        assertEquals(20.0, p.total(0), EPS);
        assertEquals(0.0, p.total(2000), EPS);
        p.addStacking("grace", 8, 15, 5000);
        p.addStacking("grace", 8, 15, 5000);
        assertEquals(15.0, p.total(3000) - 0, EPS); // a 만료 후 grace 만 (상한 15)
    }

    @Test
    void bloodrageBonusCurve() {
        assertEquals(0.0, ClassPassives.bloodrageBonus(0.8, 0.5, 0.25), EPS);
        assertEquals(0.0, ClassPassives.bloodrageBonus(0.5, 0.5, 0.25), EPS);
        assertEquals(0.125, ClassPassives.bloodrageBonus(0.25, 0.5, 0.25), EPS);
        assertEquals(0.25, ClassPassives.bloodrageBonus(0.0, 0.5, 0.25), EPS);
    }
}
