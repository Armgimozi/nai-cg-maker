package kr.souls.item;

import kr.souls.TestFiles;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 장비에는 능력치 보정도 요구 능력치도 없다 (DECISIONS 2026-10-10, DESIGN 9.1·9.2·9.7). weapons.yml 의 값과 설명 칸의 수치 한 줄
 * (item/StatTable.cells: 제 값 하나와 무게).
 */
class PlainGearTest {
    private Weapons weapons;

    @BeforeEach
    void load() {
        weapons = new Weapons(Logger.getLogger("test"));
        weapons.load(TestFiles.yaml("content/weapons.yml"));
    }

    private static List<String> names(Weapons.Def d) {
        return StatTable.cells(d).stream().map(c -> c[0]).toList();
    }

    @Test
    void noScalingOrRequirementKeysInData() {
        var y = TestFiles.yaml("content/weapons.yml");
        for (String id : y.getKeys(false)) {
            for (String k : Weapons.LEGACY) assertFalse(y.contains(id + "." + k), id + "." + k);
        }
    }

    /** 무기·활·패링 단검: 공격력과 무게 한 줄. 방패: 막기와 무게. 촉매: 술법 세기와 무게. 다른 칸은 없다. */
    @Test
    void tooltipShowsOneValueAndWeight() {
        for (Weapons.Def d : weapons.all().values()) {
            List<String> n = names(d);
            assertEquals(2, n.size(), d.id() + " " + n);
            assertEquals("weight", n.get(1), d.id());
            String want = d.shield() ? "guard" : d.catalyst() ? "spell" : "attack";
            assertEquals(want, n.get(0), d.id());
        }
        assertEquals(List.of("62", "3.0"), StatTable.cells(weapons.get("redin_guard_sword")).stream().map(c -> c[1]).toList());
        assertEquals(List.of("guard", "weight"), names(weapons.get("redin_guard_shield")));
        assertEquals(List.of("spell", "weight"), names(weapons.get("kiln_pot")));
        assertEquals(List.of("attack", "weight"), names(weapons.get("parrying_dagger")));
    }

    /** 방패는 막기 하나와 분류 (작은·중형·대형). 패링 창은 데이터에 없다 (분류마다 config, 설명 칸에 보이지 않는다). */
    @Test
    void shieldsHaveOneGuardAndAClass() {
        Set<String> classes = Set.of("small_shield", "medium_shield", "greatshield");
        int shields = 0;
        for (Weapons.Def d : weapons.all().values()) {
            if (!Weapons.BLOCK.equals(d.use())) continue;
            shields++;
            assertTrue(d.guard() > 0 && d.guard() <= 100, d.id());
            assertTrue(classes.contains(d.cls()), d.id() + " " + d.cls());
            assertEquals(Weapons.OFF, d.hand(), d.id());
        }
        assertEquals(4, shields);
        assertEquals(60, weapons.get("plank_shield").guard());
        assertEquals(70, weapons.get("pilgrim_buckler").guard());
        assertEquals(90, weapons.get("redin_guard_shield").guard());
        assertEquals(100, weapons.get("volk_greatshield").guard());
        assertEquals("medium_shield", weapons.get("redin_guard_shield").cls());
    }

    /** 패링 단검은 왼손 무기: 공격력이 있고, 막지 않는다 (use: none), 방패가 아니다. */
    @Test
    void parryingDaggerIsAnOffhandWeapon() {
        Weapons.Def d = weapons.get("parrying_dagger");
        assertEquals(Weapons.OFF, d.hand());
        assertEquals(Weapons.NONE, d.use());
        assertTrue(d.attack() > 0);
        assertFalse(d.shield());
        assertFalse(kr.souls.progression.Stats.isMelee(d), "주손 근접 무기가 아니다 (공격력 셈은 주무기만)");
    }

    /** 촉매마다 제 술법 세기 (둘 다 100 에서 시작). */
    @Test
    void catalystsHaveSpellPower() {
        for (Weapons.Def d : weapons.all().values()) {
            if (!d.catalyst()) continue;
            assertEquals(100, d.spell(), d.id());
            assertEquals(0, d.attack(), d.id());
        }
    }
}
