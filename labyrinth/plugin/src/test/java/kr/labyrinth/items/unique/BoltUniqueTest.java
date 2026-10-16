package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.DamageType;
import org.junit.jupiter.api.Test;

/** 0.3.6.1 통합: 마법탄의 고유 효과도 화살처럼 쏜 무기로 — 쏘고 나서 단도로 바꿔 쥐어도 지팡이 고유 효과. */
class BoltUniqueTest {

    @Test
    void aBoltUsesTheStaffsUniqueNotTheWeaponHeldAtImpact() {
        DamageContext bolt = DamageContext.basic(null, null, 1.0, DamageType.MAGIC).kind(DamageKind.MAGIC).weaponHit(14)
                .firedWith("frostheart_staff").casterBolt();
        assertEquals("frostheart_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), "moss_dirk"), "쏜 뒤 단도로 바꿈 → 지팡이");
        assertEquals("frostheart_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), "frostheart_staff"), "그대로 지팡이");
        assertEquals("frostheart_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), null), "쏜 뒤 맨손");
        assertNull(UniqueEffectService.uniqueWeaponId(DamageContext.basic(null, null, 1.0, DamageType.MAGIC).firedWith("").firedWith(), "moss_dirk"));
    }
}
