package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.UniqueCatalog;
import kr.labyrinth.content.UniqueDef;
import org.junit.jupiter.api.Test;

/**
 * 빠른 무기·느린 무기가 같은 값을 받게 (unique_spec §9.1·§9.2·§9.8): 간격 보정 g · 대장간 × 0.8 · 신화 강도 0.5~0.8 ·
 * 선제·추격·흘려치기의 pct = 기준값 × 강도 × 획득처 보정 × g (상한에서 자른 뒤).
 */
class UniqueFairnessTest {

    private static WeaponAttack melee(double iv) { return new WeaponAttack(WeaponAttack.Style.MELEE, iv, DamageKind.PHYSICAL, 1.0); }

    @Test
    void intervalFactorG() {
        assertEquals(1.00, UniqueCatalog.g(melee(0.67)), 0.005, "장검 0.67초 = 1");
        assertEquals(1.60, UniqueCatalog.g(melee(0.45)), 0.01, "단검 0.45초");
        assertEquals(0.67, UniqueCatalog.g(melee(1.0)), 0.01, "대검 1.0초");
        assertEquals(0.56, UniqueCatalog.g(new WeaponAttack(WeaponAttack.Style.RANGED, 1.25, DamageKind.PHYSICAL, 1.0)), 0.01,
                "장궁 1.25초");
        // 데이터에 적힌 g 와 같은 식
        for (UniqueData.Entry e : UniqueData.all().values()) {
            assertEquals(e.g(), UniqueCatalog.g(e.attack()), 0.002, e.weaponId());
        }
    }

    @Test
    void forgeOnlyWeaponsGetEightyPercent() {
        for (UniqueData.Entry e : UniqueData.all().values()) {
            double want = e.sourceKinds().equals(List.of("F")) ? 0.8 : 1.0;
            assertEquals(want, e.sourceFactor(), 1e-9, e.weaponId() + " " + e.sourceKinds());
        }
    }

    @Test
    void mythicStrengthIsLow() {
        int n = 0;
        for (UniqueData.Entry e : UniqueData.all().values()) {
            if (!e.rarity().equals("mythic")) continue;
            n++;
            assertTrue(e.strength() >= 0.5 - 1e-9 && e.strength() <= 0.8 + 1e-9, e.weaponId() + " 강도 " + e.strength());
        }
        assertEquals(6, n);
        for (UniqueData.Entry e : UniqueData.all().values()) {
            assertTrue(e.strength() >= 0.4 - 1e-9 && e.strength() <= 2.8 + 1e-9, e.weaponId() + " 강도 " + e.strength());
        }
    }

    @Test
    void hitBonusEffectsScaleWithG() {
        int n = 0;
        for (UniqueData.Entry e : UniqueData.all().values()) {
            UniqueDef u = e.def();
            if (u.effect().basis() != UniqueCatalog.Basis.WG) continue;
            n++;
            UniqueCatalog.Param p = u.effect().param("pct");
            double want = Math.min(p.ref() * e.strength(), p.hi()) * e.sourceFactor() * e.g();
            assertEquals(want, u.num("pct"), 0.0051, e.weaponId() + " " + u.id());
        }
        assertTrue(n >= 15, "선제·추격·흘려치기 무기 " + n);
    }
}
