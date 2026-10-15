package kr.labyrinth.items.weaponskills;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** GDD §17.2 의 17개 무기 스킬 id 가 전부 구현돼 있고, items.yml 의 모든 weapon_skills 가 구현을 찾는다. */
class WeaponSkillCoverageTest {

    static final Set<String> CATALOG = Set.of("slash_wave", "dash_strike", "leap_slam", "nova", "fissure", "missile", "beam",
            "chain_bolt", "rain_zone", "whirlwind", "shadow_step", "empower", "sanctuary", "mend", "riposte", "vortex",
            "blade_orbit");

    static Map<String, WeaponSkill> registry() {
        Map<String, WeaponSkill> r = new HashMap<>();
        ProjectileSkills.register(r);
        MovementSkills.register(r);
        AreaSkills.register(r);
        SupportSkills.register(r);
        MechanicsEngine.register(r);
        return r;
    }

    @Test
    void catalogFullyImplemented() {
        Set<String> want = new TreeSet<>(CATALOG);
        want.add("mechanics"); // 조합형 (GDD §17.5)
        assertEquals(want, new TreeSet<>(registry().keySet()));
    }

    @Test
    void everyContentSkillHasImplementation() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        Map<String, WeaponSkill> r = registry();
        int n = 0;
        for (ItemDef d : c.items().values()) {
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                assertTrue(r.containsKey(s.id()), d.id() + " → " + s.id());
                assertTrue(Set.of("LEFT", "RIGHT", "SNEAK_LEFT", "SNEAK_RIGHT").contains(s.input()), d.id() + " input " + s.input());
                if (d.isRanged()) assertTrue(!s.input().equals("RIGHT"), "활(당겨 쏘기)은 RIGHT 스킬 금지: " + d.id());
                n++;
            }
        }
        assertTrue(n >= 40, "무기 스킬 수 " + n);
    }
}
