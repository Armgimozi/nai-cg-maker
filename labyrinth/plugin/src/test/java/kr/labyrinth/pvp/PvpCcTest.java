package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** 플레이어가 건 상태이상 규칙 (pvp_spec §9.1·§9.2·§9.3) — 순수. */
class PvpCcTest {

    static final PvpConfig.CcConfig CC = PvpConfig.DEFAULT.cc();

    /** 기절은 기절 그대로 — 1초 → 0.8 → 0.4 → 0.2 → 면역 (같은 분류 8초 안). */
    @Test
    void stunDiminishes() {
        PvpCc cc = new PvpCc();
        long t = 1_000_000;
        assertEquals(0.8, cc.duration(CC, "stun", 1.0, t), 1e-9);
        assertEquals(0.4, cc.duration(CC, "stun", 1.0, t + 1000), 1e-9);
        assertEquals(0.2, cc.duration(CC, "stun", 1.0, t + 2000), 1e-9);
        assertEquals(0.0, cc.duration(CC, "stun", 1.0, t + 3000), 1e-9, "네 번째부터 면역");
        assertEquals(0.0, cc.duration(CC, "stun", 1.0, t + 4000), 1e-9);
    }

    @Test
    void windowResets() {
        PvpCc cc = new PvpCc();
        long t = 5_000_000;
        cc.duration(CC, "root", 2.0, t);
        assertEquals(0.75, cc.duration(CC, "root", 2.0, t + 7000), 1e-9, "8초 안: 둘째 50%");
        assertEquals(1.5, cc.duration(CC, "root", 2.0, t + 7000 + 8001), 1e-9, "8초 동안 안 맞으면 처음으로");
    }

    @Test
    void capsPerKind() {
        PvpCc cc = new PvpCc();
        long t = 0;
        assertEquals(1.5, cc.duration(CC, "frozen", 4.0, t), 1e-9, "빙결 4초 → 1.5초 (상한)");
        assertEquals(1.5, cc.duration(CC, "root", 2.5, t), 1e-9, "속박 2.5 → 1.5 (덫)");
        assertEquals(1.5, cc.duration(CC, "blind", 3.0, t), 1e-9, "실명 3 → 1.5");
        assertEquals(1.5, cc.duration(CC, "silence", 2.0, t), 1e-9);
        assertEquals(3.0, cc.duration(CC, "slow", 4.0, t), 1e-9, "둔화 상한 3초");
        assertEquals(2.0, cc.duration(CC, "cooldown_slow", 4.0, t), 1e-9, "재사용 둔화 4 → 2초");
        assertEquals(0.5, PvpCc.slowPotency(CC, 0.85), 1e-9, "둔화 세기 상한 50%");
        assertEquals(0.35, PvpCc.slowPotency(CC, 0.35), 1e-9);
    }

    /** 둔화·재사용 둔화는 줄어듦 없음. 지속 피해 등 표에 없는 효과는 그대로. */
    @Test
    void slowAndOthersDoNotDiminish() {
        PvpCc cc = new PvpCc();
        for (int i = 0; i < 6; i++) assertEquals(0.8, cc.duration(CC, "slow", 0.8, i * 500L), 1e-9);
        assertEquals(6.0, cc.duration(CC, "bleed", 6.0, 0), 1e-9);
        assertEquals(10.0, cc.duration(CC, "mark", 10.0, 0), 1e-9);
    }

    /** 기절·빙결이 끝난 뒤 2초 안 기절·빙결 = 0. 속박은 다른 분류라 무관. */
    @Test
    void controlImmunityAfterEnd() {
        PvpCc cc = new PvpCc();
        long t = 10_000;
        assertEquals(0.8, cc.duration(CC, "stun", 1.0, t), 1e-9);
        cc.onControlEnd(CC, t + 800);
        assertTrue(cc.controlImmune(t + 2000));
        assertEquals(0.0, cc.duration(CC, "frozen", 4.0, t + 1500), 1e-9, "면역 중 빙결 0");
        assertEquals(1.5, cc.duration(CC, "root", 2.0, t + 1500), 1e-9, "속박은 면역과 무관");
        assertFalse(cc.controlImmune(t + 2801));
        // 면역이 끝나면 다시 걸린다 — 단 줄어듦 횟수는 이어진다 (기절 → 면역 중 빙결 → 세 번째 = 25% → 0.8 × 0.25)
        assertEquals(0.2, cc.duration(CC, "stun", 1.0, t + 3000), 1e-9);
    }

    /** 규칙상 최악의 행동 불가: 빙결 1.5 → 2초 면역 → 기절 0.4(50%) → 2초 면역 → 기절 0.2 → 면역. */
    @Test
    void worstControlChain() {
        PvpCc cc = new PvpCc();
        long t = 0;
        assertEquals(1.5, cc.duration(CC, "frozen", 4.0, t), 1e-9);
        cc.onControlEnd(CC, t + 1500);
        assertEquals(0.4, cc.duration(CC, "stun", 1.0, t + 3500), 1e-9);
        cc.onControlEnd(CC, t + 3900);
        assertEquals(0.2, cc.duration(CC, "stun", 1.0, t + 5900), 1e-9);
        cc.onControlEnd(CC, t + 6100);
        assertEquals(0.0, cc.duration(CC, "stun", 1.0, t + 8100), 1e-9, "네 번째 = 면역");
    }

    /** 0.2초보다 짧으면 걸지 않지만 횟수는 센다 (낙뢰 0.5초 기절 연쇄). */
    @Test
    void shortOnesAreDroppedButCounted() {
        PvpCc cc = new PvpCc();
        assertEquals(0.4, cc.duration(CC, "stun", 0.5, 0), 1e-9);
        assertEquals(0.2, cc.duration(CC, "stun", 0.5, 100), 1e-9, "0.5 × 0.8 × 50% = 0.2 — 아직 걸림");
        assertEquals(0.0, cc.duration(CC, "stun", 0.5, 200), 1e-9, "0.1 → 안 걸림 (§9.3 정동 낙하 0.4 → 0.2 → 안 걸림)");
        assertEquals(3, cc.hits(CC, PvpConfig.CcConfig.CONTROL, 200));
    }

    @Test
    void tinyDroppedButCounted() {
        PvpCc cc = new PvpCc();
        assertEquals(0.0, cc.duration(CC, "blind", 0.2, 0), 1e-9, "0.2 × 0.7 = 0.14 → 걸지 않음");
        assertEquals(1, cc.hits(CC, "blind", 0), "그래도 횟수는 셈");
        assertEquals(0.75, cc.duration(CC, "blind", 3.0, 100), 1e-9, "둘째 = 50%");
    }

    /** 정신(WIS) 감소가 PvP 배율 앞 — 상한보다 먼저 줄인다 (LabyrinthStatusEffectService.apply 의 순서). */
    @Test
    void wisdomBeforePvpRules() {
        double wis = 0.3;
        PvpCc cc = new PvpCc();
        assertEquals(2.0 * (1 - wis) * 0.8, cc.duration(CC, "root", 2.0 * (1 - wis), 0), 1e-9);
        // PvP 를 먼저 했다면 min(1.5, 1.6) × 0.7 = 1.05 — 다른 값
        assertTrue(Math.abs(cc.duration(CC, "root", 2.0 * (1 - wis), 20_000) - 1.05) > 1e-3);
    }

    @Test
    void idleAfterWindowAndImmunity() {
        PvpCc cc = new PvpCc();
        cc.duration(CC, "stun", 1.0, 0);
        cc.onControlEnd(CC, 800);
        assertFalse(cc.idle(CC, 2000));
        assertTrue(cc.idle(CC, 8001));
    }
}
