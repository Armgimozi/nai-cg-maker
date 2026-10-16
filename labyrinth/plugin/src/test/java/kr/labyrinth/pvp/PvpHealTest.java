package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.UUID;
import kr.labyrinth.combat.HealKind;
import org.junit.jupiter.api.Test;

/** PvP 전투 중 회복·보호막 (pvp_spec §8) — {@link PvpDamage} · {@link PvpFights} 순수 부분. */
class PvpHealTest {

    static final PvpConfig C = PvpConfig.DEFAULT;
    static final double HP = 662;
    static final int LV = 20;
    static final double POOL = HP / (HP + 840);

    @Test
    void skillHealSplitsPctAndFlat() {
        // 치유 스킬 = (비율 몫 + 치유력 몫 × HP비) × 0.6
        double got = PvpDamage.healAmount(C, 100, 50, HealKind.SKILL, true, 5, HP, LV);
        assertEquals((100 + 50 * POOL) * 0.6, got, 1e-9);
    }

    @Test
    void potionLifestealRegen() {
        assertEquals(400 * 0.36, PvpDamage.healAmount(C, 400, 0, HealKind.POTION, true, 0, HP, LV), 1e-9, "물약 × 0.36");
        assertEquals(30 * 0.5 * POOL, PvpDamage.healAmount(C, 0, 30, HealKind.LIFESTEAL, true, 0, HP, LV), 1e-9, "흡혈 × 0.5 × HP비");
        assertEquals(10 * 0.6 * POOL, PvpDamage.healAmount(C, 0, 10, HealKind.REGEN, true, 0, HP, LV), 1e-9, "재생 × 0.6 × HP비");
        assertEquals(0.36 * 0.6, PvpDamage.healFactor(C, HealKind.POTION, true, 0) * 0.6, 1e-9);
    }

    @Test
    void outOfCombatUnchanged() {
        assertEquals(150, PvpDamage.healAmount(C, 100, 50, HealKind.SKILL, false, 0, HP, LV), 1e-9);
        assertEquals(400, PvpDamage.healAmount(C, 400, 0, HealKind.POTION, false, 0, HP, LV), 1e-9);
        assertEquals(1.0, PvpDamage.shieldFactor(C, false, 0), 1e-9);
        PvpConfig off = C.withEnabled(false);
        assertEquals(1.0, PvpDamage.healFactor(off, HealKind.SKILL, true, 0), 1e-9, "PvP 꺼짐이면 그대로");
    }

    @Test
    void longFightReducesHealingAndShields() {
        assertEquals(0.6 * 0.5, PvpDamage.healFactor(C, HealKind.SKILL, true, 40), 1e-9);
        assertEquals(0.6 * 0.1, PvpDamage.healFactor(C, HealKind.OTHER, true, 90), 1e-9);
        assertEquals(0.8, PvpDamage.shieldFactor(C, true, 10), 1e-9);
        assertEquals(0.8 * 0.5, PvpDamage.shieldFactor(C, true, 40), 1e-9);
    }

    @Test
    void flatHealByPoolSwitch() {
        PvpConfig noPool = new PvpConfig(true, 1.0, C.levelCurve(), C.bufferHp(), C.defenseWeight(), C.resilience(),
                C.critDamageScale(), C.maxHitRatio(), C.classDamage(), C.combatSeconds(), C.healing(), C.potion(), C.lifesteal(),
                C.shield(), false, C.longFight(), C.cc(), true, 8, true);
        assertEquals(1.0, PvpDamage.flatHealFactor(noPool, true, HP, LV), 1e-9);
        assertEquals(POOL, PvpDamage.flatHealFactor(C, true, HP, LV), 1e-9);
    }

    /** 'PvP 전투 중' = 마지막 PvP 피해에서 8초 안. 끊기면 긴 싸움 시간이 0 부터. */
    @Test
    void combatWindow() {
        PvpFights f = new PvpFights();
        UUID u = UUID.randomUUID();
        assertFalse(f.inCombat(u, 0, 8));
        f.mark(u, 1000, 8);
        assertTrue(f.inCombat(u, 8999, 8));
        f.mark(u, 6000, 8);
        f.mark(u, 13_000, 8);
        assertEquals(12.0, f.seconds(u, 13_000, 8), 1e-9, "이어진 전투");
        assertFalse(f.inCombat(u, 21_001, 8));
        assertEquals(0, f.seconds(u, 21_001, 8), 1e-9);
        f.mark(u, 30_000, 8);
        assertEquals(0, f.seconds(u, 30_000, 8), 1e-9, "8초 넘게 조용했으면 새 전투");
        f.prune(50_000, 8);
        assertFalse(f.inCombat(u, 30_001, 8), "지운 뒤에는 기록 없음");
    }
}
