package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 화살 피해 = 쏜 활 — 고유 효과도 쏜 활로. 쏘고 나서 단도로 바꿔 쥐면 예전에는 날아가던 화살에 단도의
 * 고유 효과(이끼 그늘 등 찌르기 +10% 등)가 붙었다 (라이브: 회랑 장궁 화살 21.22 → 23.34).
 */
class ArrowUniqueTest {

    @Test
    void anArrowUsesTheBowsUniqueNotTheWeaponHeldAtImpact() {
        assertEquals("corridor_longbow", UniqueEffectService.uniqueWeaponId("corridor_longbow", "moss_dirk"), "쏜 뒤 단도로 바꿈 → 활");
        assertEquals("corridor_longbow", UniqueEffectService.uniqueWeaponId("corridor_longbow", "corridor_longbow"), "그대로 활");
        assertEquals("corridor_longbow", UniqueEffectService.uniqueWeaponId("corridor_longbow", null), "쏜 뒤 맨손");
        assertNull(UniqueEffectService.uniqueWeaponId("", "moss_dirk"), "미궁 활이 아닌 것으로 쏜 화살 = 고유 효과 없음");
        assertEquals("moss_dirk", UniqueEffectService.uniqueWeaponId(null, "moss_dirk"), "근접·화살 아님 = 지금 든 무기");
        assertNull(UniqueEffectService.uniqueWeaponId(null, null));
    }

    @Test
    void damageContextCarriesTheFiringBow() {
        DamageContext melee = DamageContext.raw(null, null, 10, DamageType.MELEE);
        assertNull(melee.firedWith(), "근접은 비어 있음");
        assertEquals("corridor_longbow", DamageContext.raw(null, null, 10, DamageType.RANGED).firedWith("corridor_longbow").firedWith());
        assertEquals("", DamageContext.raw(null, null, 10, DamageType.RANGED).firedWith(null).firedWith(), "기록 없는 활 = 빈 칸");
    }
}
