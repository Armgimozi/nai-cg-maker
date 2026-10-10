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

    /** 무기·활·패링 단검: 공격력과 무게 한 줄. 방패: 막기와 무게. 촉매: 술법 위력과 무게. 다른 칸은 없다. */
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

    /** 촉매마다 제 술법 위력 (둘 다 100 에서 시작). 촉매는 왼손에 든다 (우클릭 = 왼손에 든 것, DECISIONS 2026-10-10). */
    @Test
    void catalystsHaveSpellPower() {
        int n = 0;
        for (Weapons.Def d : weapons.all().values()) {
            if (!d.catalyst()) continue;
            n++;
            assertEquals(100, d.spell(), d.id());
            assertEquals(0, d.attack(), d.id());
            assertEquals(Weapons.OFF, d.hand(), d.id());
        }
        assertEquals(2, n);
    }

    /**
     * 보정 등급이 없으니 같은 분류에서 무게만 무겁고 공격력이 같으면 늘 손해다: 같은 분류의 더 무거운 무기는 공격력이 6~12% 높다
     * (검토 same-class-dominated-weapons). 보스 무기 (×1.25) 와 빈털터리의 곤봉 (시작 무기라 찾은 메이스보다 못한 것이 다크 소울답다) 은 따로.
     */
    @Test
    void heavierSameClassHitsHarder() {
        String[][] pairs = {{"volk_longsword", "redin_guard_sword"}, {"sellsword_axe", "levy_hatchet"}};
        for (String[] pr : pairs) {
            Weapons.Def heavy = weapons.get(pr[0]), light = weapons.get(pr[1]);
            assertEquals(heavy.cls(), light.cls(), pr[0]);
            assertTrue(heavy.weight() > light.weight(), pr[0]);
            double gain = (double) heavy.attack() / light.attack() - 1;
            assertTrue(gain >= 0.06 && gain <= 0.12, pr[0] + " 은 " + pr[1] + " 보다 +" + Math.round(gain * 100) + "%");
        }
        assertTrue(weapons.get("penitent_mace").attack() > weapons.get("gaoler_club").attack(), "찾은 메이스가 시작 곤봉보다 세다");
    }

    /**
     * 예전 판 (v4, 커밋 3e894c0) 의 weapons.yml 을 되살려 써도 방패는 방패로, 촉매는 촉매로 남는다 (검토 legacy-weapons-yml-no-fallback):
     * 막기가 없으면 흡수 absorb 를 막기로, 옛 분류 shield 는 medium_shield, 술법 위력이 없는 촉매는 100.
     */
    @Test
    void legacyWeaponsFileDegradesGracefully() {
        Weapons old = new Weapons(Logger.getLogger("test"));
        old.load(org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(new java.io.File("src/test/resources/legacy/weapons-3e894c0.yml")));
        assertEquals(60, old.get("plank_shield").guard());
        assertTrue(old.get("plank_shield").shield());
        assertEquals(100, old.get("redin_guard_shield").guard());
        assertEquals("medium_shield", old.get("redin_guard_shield").cls());
        assertEquals(100, old.get("volk_greatshield").guard());
        assertEquals(100, old.get("kiln_pot").spell());
        assertEquals(List.of("guard", "weight"), names(old.get("redin_guard_shield")));
        assertEquals(List.of("spell", "weight"), names(old.get("kiln_pot")));
        assertEquals(List.of("attack", "weight"), names(old.get("redin_guard_sword")));
    }
}
