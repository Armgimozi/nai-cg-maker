package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.DamageType;
import org.junit.jupiter.api.Test;

/** 0.3.6.1 통합: 마법탄의 고유 효과도 화살처럼 쏜 무기로 — 쏘고 나서 단도로 바꿔 쥐어도 지팡이 고유 효과. */
class BoltUniqueTest {

    private static DamageContext bolt(String staff) {
        return DamageContext.basic(null, null, 1.0, DamageType.MAGIC).kind(DamageKind.MAGIC).weaponHit(14)
                .firedWith(staff).casterBolt();
    }

    @Test
    void aBoltUsesTheStaffsUniqueNotTheWeaponHeldAtImpact() {
        DamageContext bolt = bolt("frostheart_staff");
        assertEquals("frostheart_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), "moss_dirk"), "쏜 뒤 단도로 바꿈 → 지팡이");
        assertEquals("frostheart_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), "frostheart_staff"), "그대로 지팡이");
        assertEquals("frostheart_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), null), "쏜 뒤 맨손");
        assertNull(UniqueEffectService.uniqueWeaponId(DamageContext.basic(null, null, 1.0, DamageType.MAGIC).firedWith("").firedWith(), "moss_dirk"));
    }

    /** 검토 반영: 처치 효과(death_burst 종류 · siphon 재사용 대기)와 sanctify 회복량도 쏜 지팡이 기준. */
    @Test
    void killAndHealEffectsUseTheFiringStaff() {
        DamageContext bolt = bolt("mycelium_staff");
        assertEquals(DamageKind.MAGIC, UniqueEffectService.hitKind(bolt, DamageKind.PHYSICAL), "칼로 바꿔도 death_burst 는 마법 (지능)");
        assertEquals(14, UniqueEffectService.hitW(bolt, 40), 1e-9, "sanctify W = 지팡이 W");
        assertEquals("mycelium_staff", UniqueEffectService.uniqueWeaponId(bolt.firedWith(), "iron_sword"), "siphon 은 지팡이 스킬 대기를 줄임");

        DamageContext melee = DamageContext.basic(null, null, 1.0, DamageType.MELEE);
        assertEquals(DamageKind.PHYSICAL, UniqueEffectService.hitKind(melee, DamageKind.PHYSICAL), "근접 = 든 무기");
        assertEquals(40, UniqueEffectService.hitW(melee, 40), 1e-9, "근접 = 든 무기 W");
        assertEquals("iron_sword", UniqueEffectService.uniqueWeaponId(melee.firedWith(), "iron_sword"));
    }

    /** onKill · sanctify 가 다시 '지금 든 무기' 를 직접 읽지 않게 (화살·마법탄이면 바꿔 쥔 무기가 섞임). */
    @Test
    void killAndSanctifyBodiesGoThroughTheDamageContext() throws Exception {
        String src = Files.readString(Path.of("src/main/java/kr/labyrinth/items/unique/UniqueEffectService.java"));
        for (String head : new String[] {"private void onKill(", "private void sanctify("}) {
            int at = src.indexOf(head);
            assertTrue(at >= 0, head);
            int end = src.indexOf("\n    }\n", at);
            String body = src.substring(at, end);
            assertTrue(body.contains("DamageContext ctx"), head + " 이 피해 문맥을 받음");
            assertFalse(body.contains("weaponKind(p)"), head + " 에 든 무기 종류");
            assertFalse(body.contains("st.weaponDamage()"), head + " 에 든 무기 W");
            assertFalse(body.contains("reduceCooldowns(p, w.id()"), head + " 에 든 무기 id");
        }
    }
}
