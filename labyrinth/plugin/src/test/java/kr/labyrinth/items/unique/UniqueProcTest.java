package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.UUID;
import java.util.random.RandomGenerator;
import kr.labyrinth.classes.EffectStack;
import kr.labyrinth.classes.LabyrinthStatusEffectService;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageFormula;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.UniqueCatalog;
import kr.labyrinth.content.UniqueDef;
import org.junit.jupiter.api.Test;

/**
 * 고유 효과 순수 로직 (unique_spec §7 폭주 방지 · §9.8, pvp_spec §11·§15, review2 C4): N번째 · 첫 타 창 · 재발동 · 중첩 상한 ·
 * PvP 3중첩·×0.5 · 기절 그대로 · 지속 피해는 회피(구르기 포함)할 수 없음.
 */
class UniqueProcTest {

    static final UUID A = UUID.randomUUID();
    static final UUID B = UUID.randomUUID();
    static final UUID T1 = UUID.randomUUID();
    static final UUID T2 = UUID.randomUUID();

    @Test
    void nthAttackCountsBasicHits() {
        UniqueProcs p = new UniqueProcs();
        assertFalse(p.nth(A, "flurry", 4));
        assertFalse(p.nth(A, "flurry", 4));
        assertFalse(p.nth(A, "flurry", 4));
        assertTrue(p.nth(A, "flurry", 4));
        for (int i = 0; i < 3; i++) assertFalse(p.nth(A, "flurry", 4));
        assertTrue(p.nth(A, "flurry", 4));
        // 사람마다 · 효과마다 따로
        assertFalse(p.nth(B, "flurry", 4));
        assertFalse(p.nth(A, "bash_stun", 2));
        assertTrue(p.nth(A, "bash_stun", 2));
    }

    @Test
    void firstStrikeWindowIsTenSecondsAndBossesThirty() {
        UniqueProcs p = new UniqueProcs();
        long t = 1_000_000;
        assertTrue(p.firstHit(A, T1, false, 10, t), "처음 때림");
        assertFalse(p.firstHit(A, T1, false, 10, t + 2_000), "2초 뒤 다시");
        assertFalse(p.firstHit(A, T1, false, 10, t + 11_000), "계속 때리면 창이 다시 열리지 않음");
        assertTrue(p.firstHit(A, T1, false, 10, t + 22_000), "10초 넘게 안 때림");
        assertTrue(p.firstHit(A, T2, false, 10, t + 22_000), "다른 적은 따로");
        // 보스: 계속 때려도 30초에 한 번
        assertTrue(p.firstHit(A, B, true, 10, t));
        assertFalse(p.firstHit(A, B, true, 10, t + 20_000));
        assertTrue(p.firstHit(A, B, true, 10, t + 30_000));
    }

    @Test
    void internalCooldownsByScope() {
        UniqueProcs p = new UniqueProcs();
        long t = 5_000;
        double chain = UniqueCatalog.get("chain_spark").icd();
        assertTrue(p.ready(A, "chain_spark", null, chain, t));
        assertFalse(p.ready(A, "chain_spark", null, chain, t + 299));
        assertTrue(p.ready(A, "chain_spark", null, chain, t + 300), "연쇄 번개 0.3초");
        double sanct = UniqueCatalog.get("sanctify").icd();
        assertTrue(p.ready(A, "sanctify", null, sanct, t));
        assertFalse(p.ready(A, "sanctify", null, sanct, t + 200));
        assertTrue(p.ready(A, "sanctify", null, sanct, t + 250), "축성 0.25초");
        // 대상마다 (찢는 치명 0.4초): 다른 대상은 바로
        assertTrue(p.ready(A, "rend", T1, 0.4, t));
        assertTrue(p.ready(A, "rend", T2, 0.4, t));
        assertFalse(p.ready(A, "rend", T1, 0.4, t + 100));
        // 재발동 없음
        assertTrue(p.ready(A, "cleave", null, 0, t));
        assertTrue(p.ready(A, "cleave", null, 0, t));
    }

    @Test
    void stackCapsAndPvpThree() {
        assertEquals(5, UniqueProcs.maxStacks(5, false));
        assertEquals(3, UniqueProcs.maxStacks(5, true), "플레이어 대상 3중첩");
        UniqueProcs p = new UniqueProcs();
        long t = 0;
        for (int i = 0; i < 8; i++) p.addShred(T1, 0.08, 5, 5, t + i);
        assertEquals(5, p.shredStacks(T1, t + 10));
        assertEquals(0.40, p.shred(T1, t + 10), 1e-9, "5 × 8% = 40% (상한)");
        for (int i = 0; i < 8; i++) p.addShred(T2, 0.08, UniqueProcs.maxStacks(5, true), 5, t + i);
        assertEquals(3, p.shredStacks(T2, t + 10));
        assertEquals(0.24, p.shred(T2, t + 10), 1e-9);
        assertEquals(0, p.shred(T2, t + 8 + 5_000), 1e-9, "5초 지나면 사라짐");
        assertEquals(1, p.addShred(T2, 0.04, 3, 5, t + 9_000), "다시 1부터");
        assertEquals(0.4, UniqueProcs.shredOf(9, 0.08), 1e-9);
        // 출혈·독 중첩 층 (상태이상 쪽): 따로 쌓이고 중첩 수만큼 피해
        assertEquals("bleed_stack", EffectStack.stackLayer("bleed"));
        assertEquals("poison_stack", EffectStack.stackLayer("poison"));
        assertNull(EffectStack.stackLayer("burn"));
        assertEquals(EffectStack.Rule.STACKS, EffectStack.rule("bleed_stack"));
        assertTrue(EffectStack.dotScalesWithStacks("bleed_stack"));
        assertTrue(EffectStack.DOT.contains("poison_stack") && EffectStack.CLEANSABLE.contains("bleed_stack"));
        EffectStack s = new EffectStack();
        for (int i = 0; i < 5; i++) s.apply("bleed_stack", 2.0, 1, 4000, null, i, 3);
        assertEquals(3, s.stacks("bleed_stack", 10));
        assertEquals(EffectStack.Rule.REFRESH, EffectStack.rule("bleed"), "일반 출혈은 예전처럼");
    }

    @Test
    void stunStaysStunForPlayersAndBossesGetVulnerable() {
        // pvp_spec §11: 기절을 느려짐으로 바꾸지 않는다 — 시간만 PvP 상태이상 규칙이 줄인다
        assertEquals("stun", UniqueProcs.stunEffect(false));
        assertEquals("vulnerable", UniqueProcs.stunEffect(true));
        UniqueProcs p = new UniqueProcs();
        assertTrue(p.stunReady(T1, 0));
        assertFalse(p.stunReady(T1, 5_999), "같은 적 6초 면역");
        assertTrue(p.stunReady(T1, 6_000));
        assertEquals(1.0, UniqueProcs.IMBUE_FREEZE, 1e-9, "고유 효과 서리 5중첩 빙결 1초");
    }

    @Test
    void pvpHalvesBonusesAndExtraDamage() {
        assertEquals(0.5, UniqueProcs.pvp(true), 1e-9);
        assertEquals(1.0, UniqueProcs.pvp(false), 1e-9);
        // 마무리: HP 30% 이하 +25% · 보스 60% · 플레이어 ×0.5
        assertEquals(0.25, UniqueProcs.executeBonus(0.30, 0.3, 0.25, false, false), 1e-9);
        assertEquals(0.0, UniqueProcs.executeBonus(0.31, 0.3, 0.25, false, false), 1e-9);
        assertEquals(0.15, UniqueProcs.executeBonus(0.10, 0.3, 0.25, true, false), 1e-9);
        assertEquals(0.125, UniqueProcs.executeBonus(0.10, 0.3, 0.25, false, true), 1e-9);
        // 약점 파고들기: 2개면 1.6배
        assertEquals(0, UniqueProcs.exploitBonus(0, 0.15, false), 1e-9);
        assertEquals(0.15, UniqueProcs.exploitBonus(1, 0.15, false), 1e-9);
        assertEquals(0.24, UniqueProcs.exploitBonus(3, 0.15, false), 1e-9);
        assertEquals(0.12, UniqueProcs.exploitBonus(2, 0.15, true), 1e-9);
        // 광기: 잃은 HP 10% 마다
        assertEquals(0.0, UniqueProcs.berserkBonus(0.95, 0.025, false), 1e-9);
        assertEquals(0.175, UniqueProcs.berserkBonus(0.25, 0.025, false), 1e-9);
        assertEquals(0.25, UniqueProcs.berserkBonus(0.0, 0.025, false), 1e-9);
        // 관통: 꿰뚫을 때마다 −20%
        assertEquals(0.8, UniqueProcs.pierceMult(1), 1e-9);
        assertEquals(0.6, UniqueProcs.pierceMult(2), 1e-9);
    }

    @Test
    void backstabIsTheRearCone() {
        // 대상이 +z 를 본다: 공격자가 −z 쪽(뒤)이면 등 뒤, 옆(±x)·앞은 아님
        assertTrue(UniqueProcs.behind(0, 1, 0, -1));
        assertTrue(UniqueProcs.behind(0, 1, 0.5, -1));
        assertFalse(UniqueProcs.behind(0, 1, 1, 0), "옆");
        assertFalse(UniqueProcs.behind(0, 1, 0, 1), "앞");
        assertFalse(UniqueProcs.behind(0, 0, 0, -1), "방향 없음");
    }

    @Test
    void leechCapPerSecondAndMomentumDecay() {
        UniqueProcs p = new UniqueProcs();
        assertEquals(10, p.leechAllowed(A, 10, 30, 0), 1e-9);
        assertEquals(20, p.leechAllowed(A, 25, 30, 500), 1e-9, "1초 안 상한 30");
        assertEquals(0, p.leechAllowed(A, 5, 30, 900), 1e-9);
        assertEquals(5, p.leechAllowed(A, 5, 30, 1_000), 1e-9, "새 1초 창");
        assertEquals(1, p.momentum(A, 5, 3, 0));
        assertEquals(2, p.momentum(A, 5, 3, 500));
        for (int i = 0; i < 10; i++) p.momentum(A, 5, 3, 600 + i);
        assertEquals(5, p.momentum(A, 5, 3, 1_000), "5중첩 상한");
        assertEquals(1, p.momentum(A, 5, 3, 4_100), "3초 쉬면 사라짐");
    }

    @Test
    void armedNextAttackIsConsumedOnce() {
        UniqueProcs p = new UniqueProcs();
        p.arm(A, "bloodrush", 0.6, 10, 0);
        assertTrue(p.armed(A, "bloodrush", 100));
        UniqueProcs.Armed a = p.consume(A, "bloodrush", 100);
        assertNotNull(a);
        assertEquals(0.6, a.pct(), 1e-9);
        assertNull(p.consume(A, "bloodrush", 200), "한 번만");
        p.arm(A, "counterstep", 0.3, 3, 0);
        assertNull(p.consume(A, "counterstep", 3_001), "창이 지남");
    }

    @Test
    void wardAuraNeedsRecentCombatAndKeepsItsPeriod() {
        UniqueProcs p = new UniqueProcs();
        assertFalse(p.inCombat(A, UniqueProcs.WARD_COMBAT, 0));
        p.markCombat(A, 1_000);
        assertTrue(p.inCombat(A, UniqueProcs.WARD_COMBAT, 5_900));
        assertFalse(p.inCombat(A, UniqueProcs.WARD_COMBAT, 6_100), "최근 5초");
        assertTrue(p.auraDue(A, 8, 0));
        assertFalse(p.auraDue(A, 8, 7_999));
        assertTrue(p.auraDue(A, 8, 8_000));
    }

    @Test
    void imbueChanceIsStoredNotRemultiplied() {
        // §9.8: 확률은 무기마다 저장 — 서비스는 u.num("chance") 를 그대로 쓴다
        UniqueDef frost = UniqueData.all().get("frostbone_longbow").def();
        assertEquals(0.38, frost.num("chance"), 1e-9);
        assertEquals(UniqueCatalog.imbueChance(1.3), frost.num("chance"), 1e-9);
        assertEquals(0.25, UniqueCatalog.imbueChance(0.67), 1e-9);
        assertEquals(0.18, UniqueCatalog.imbueChance(0.47), 1e-9);
    }

    @Test
    void dotTicksCannotBeEvaded() {
        // review2 C4: 지속 피해 틱은 canEvade=false — 회피 100% (구르기 중)여도 맞는다
        DamageContext dot = LabyrinthStatusEffectService.dotContext(null, null, 12, "bleed_stack");
        assertFalse(dot.canEvade());
        assertFalse(dot.canCrit());
        assertEquals(DamageType.TRUE, dot.type());
        assertEquals("effect:bleed_stack", dot.sourceId());
        assertFalse(dot.isBasicAttack(), "지속 피해는 고유 효과를 켜지 않는다");
        var out = DamageFormula.compute(new DamageFormula.Input(12, false, 0, 0, 0, 1.5, false, 1.0, dot.canEvade(), 0, true, 0, 0,
                0, false), fixed(0.0));
        assertFalse(out.evaded());
        assertEquals(12, out.damage(), 1e-9);
    }

    @Test
    void uniqueDamageIsNotABasicAttack() {
        // 폭주 방지: 고유 효과가 낸 피해(source unique:*)·스킬은 기본 공격이 아니다
        DamageContext extra = DamageContext.raw(null, null, 10, DamageType.MELEE).source("unique:cleave");
        assertFalse(extra.isBasicAttack());
        DamageContext crit = DamageContext.raw(null, null, 10, DamageType.MELEE).critDamageAdd(0.2).critDamageAdd(0.25);
        assertEquals(0.45, crit.critDamageAdd(), 1e-9, "피 냄새 치명 피해 가산은 쌓인다");
    }

    private static RandomGenerator fixed(double v) {
        return new RandomGenerator() {
            @Override
            public long nextLong() { return 0; }

            @Override
            public double nextDouble() { return v; }
        };
    }
}
