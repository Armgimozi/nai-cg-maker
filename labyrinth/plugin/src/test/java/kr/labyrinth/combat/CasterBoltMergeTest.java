package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import org.bukkit.Color;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 통합 (c0361 마법탄 + bow-fix-0361 활): 마법탄도 화살처럼 쏜 무기로 세고, 활 규칙(직접 치면 절반 · 쏜 뒤 바꿈 0.2초)과
 * 같은 공격 시계를 써도 서로 막거나 끼어들지 않는다.
 */
class CasterBoltMergeTest {

    private static final long TOL = 50;
    private static final long NOCK = Math.round(CombatMath.BOW_NOCK * 1000);
    private static final WeaponAttack STAFF = new WeaponAttack(WeaponAttack.Style.CASTER, 0.9, DamageKind.MAGIC, 1.05);
    private static final WeaponAttack BOW = new WeaponAttack(WeaponAttack.Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0);
    private static final WeaponAttack DIRK = new WeaponAttack(WeaponAttack.Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0);

    @Test
    void boltCarriesTheStaffThatCastIt() {
        CasterBolts.Shot shot = new CasterBolts.Shot("frostheart_staff", 14.0, DamageKind.MAGIC, Color.fromRGB(0x88ccff));
        DamageContext c = CasterBolts.context(null, null, shot);
        assertEquals("frostheart_staff", c.firedWith(), "고유 효과·덧 피해 = 쏜 지팡이 (날아가는 사이 단도로 바꿔도)");
        assertTrue(c.hasWeaponHit());
        assertEquals(14.0, c.weaponHit(), 1e-9, "한 방 W = 쏜 순간의 지팡이");
        assertEquals(DamageKind.MAGIC, c.kind());
        assertEquals(DamageType.MAGIC, c.type());
        assertTrue(c.isCasterBolt());
        assertFalse(c.isSkill());
        assertNull(c.sourceId(), "기본 공격 (고유 효과 '기본 공격' 발동)");
        assertEquals(DamageContext.Base.PER_HIT, c.base());
        // 무기 없이 쏜 것으로 기록된 마법탄 (있을 수 없지만): 고유 효과 없음 — 화살의 "" 와 같은 뜻
        assertEquals("", CasterBolts.context(null, null, new CasterBolts.Shot("", 3.0, DamageKind.MAGIC, Color.WHITE)).firedWith());
    }

    @Test
    void bowMeleeHalfIsOnlyForBows() {
        assertEquals(0.5, BowMelee.mult(BOW, 0.5), 1e-9);
        assertEquals(1.0, BowMelee.mult(STAFF, 0.5), 1e-9, "지팡이 마법탄·휘두르기에는 활 절반이 붙지 않는다");
        assertEquals(1.0, BowMelee.mult(DIRK, 0.5), 1e-9);
    }

    @Test
    void afterAShotTheStaffWaitsLikeAnyOtherWeapon() {
        double as = 0, min = CombatMath.MIN_INTERVAL;
        long staff = Math.round(CombatMath.cycle(STAFF, as, min) * 1000);
        long full = Math.round(CombatMath.bowDraw(BOW.interval(), as, min) * 1000);
        AttackTiming t = new AttackTiming();
        long shotAt = 10_000;
        t.shot(shotAt, full, full, TOL, NOCK);
        t.swap(shotAt, staff, AttackClock.SWAP_DELAY_FRACTION);
        long wait = t.nextReady() - shotAt;
        assertEquals(Math.max(NOCK, Math.round(staff * 0.5)), wait, "쏜 뒤 지팡이 = max(다시 메기기, 지팡이 간격 × 0.5)");
        assertNotEquals(AttackTiming.Result.ACCEPT, t.click(shotAt + wait - 2 * TOL, staff, TOL, 0, AttackTiming.AIR, "staff"));
        assertEquals(AttackTiming.Result.ACCEPT, t.click(shotAt + wait, staff, TOL, 0, AttackTiming.AIR, "staff"));
    }

    @Test
    void afterABoltTheBowDrawCountsFromTheStaffInterval() {
        double as = 0, min = CombatMath.MIN_INTERVAL;
        long staff = Math.round(CombatMath.cycle(STAFF, as, min) * 1000);
        long bowCycle = Math.round(CombatMath.cycle(BOW, as, min) * 1000);
        long full = Math.round(CombatMath.bowDraw(BOW.interval(), as, min) * 1000);
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1_000, staff, TOL, 500, AttackTiming.AIR, "staff"));
        t.swap(1_050, bowCycle, AttackClock.SWAP_DELAY_FRACTION, full);
        assertEquals(1_000 + staff, t.nextReady(), "마법탄 한 발 = 근접 한 대처럼 그 간격을 쓴다");
        assertEquals(1_000 + staff - TOL - 1_050, t.drawBlockedMs(1_050, TOL), "그동안 활에 하얀 막대");
    }

    @Test
    void aRememberedBoltIsDroppedWhenSwappingToTheBow() {
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1_000, 900, TOL, 500, AttackTiming.AIR, "staff"));
        assertEquals(AttackTiming.Result.BUFFER, t.click(1_600, 900, TOL, 500, AttackTiming.AIR, "staff"));
        t.swap(1_650, 1_150, AttackClock.SWAP_DELAY_FRACTION, 1_000);
        assertFalse(t.hasBuffer(), "활로 바꾸면 기억한 마법탄은 버린다 (활이 마법탄을 쏘지 않게)");
    }
}
