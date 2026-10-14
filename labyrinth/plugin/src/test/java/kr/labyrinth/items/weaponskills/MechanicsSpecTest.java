package kr.labyrinth.items.weaponskills;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec.Effect;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec.Part;
import org.junit.jupiter.api.Test;

/** 조합형 무기 스킬(id: mechanics, GDD §17.5) 파서·검사기와 items.yml 카탈로그. */
class MechanicsSpecTest {

    @Test
    void shorthandEffectsNormalize() {
        List<String> problems = new ArrayList<>();
        Effect d = MechanicsSpec.normalizeEffect(Map.of("damage", 1.5, "magic", true), "t", problems);
        assertEquals("damage", d.type());
        assertEquals(1.5, d.amount(0));
        assertTrue(d.p().bool("magic", false));
        Effect a = MechanicsSpec.normalizeEffect(Map.of("absorption", Map.of("amount", 0.2, "seconds", 6)), "t", problems);
        assertEquals("absorption", a.type());
        assertEquals(0.2, a.amount(0));
        assertEquals(6, a.p().dbl("seconds", 0));
        Effect full = MechanicsSpec.normalizeEffect(Map.of("type", "slow", "amount", 2), "t", problems);
        assertEquals("slow", full.type());
        assertEquals(2, full.amount(0));
        Effect bare = MechanicsSpec.normalizeEffect("cleanse", "t", problems);
        assertEquals("cleanse", bare.type());
        assertTrue(problems.isEmpty(), problems.toString());
    }

    @Test
    void nestedPartsParse() {
        Object raw = List.of(
                Map.of("type", "leap", "upward", 1.0, "land", List.of(
                        Map.of("type", "nova", "radius", 4, "effects", List.of(Map.of("damage", 2.0), Map.of("launch", 0.5))))),
                Map.of("type", "projectile", "speed", 1.2, "effects", List.of(Map.of("damage", 1.0)),
                        "explode", Map.of("radius", 2.5, "display", "ember_burst", "effects", List.of(Map.of("ignite", 3)))),
                Map.of("type", "delay", "ticks", 10),
                Map.of("type", "repeat", "times", 3, "interval", 4, "mechanics", List.of(
                        Map.of("type", "cone", "range", 3, "angle", 90, "particle", "DUST:#ff0000:1.2",
                                "effects", List.of(Map.of("damage", 0.6))))));
        MechanicsSpec.Result r = MechanicsSpec.parse(raw);
        assertTrue(r.ok(), r.problems().toString());
        assertEquals(4, r.parts().size());
        Part leap = r.parts().getFirst();
        assertEquals("nova", leap.child("land").getFirst().type());
        assertEquals(2, leap.child("land").getFirst().effects().size());
        Part proj = r.parts().get(1);
        Part explode = proj.child("explode").getFirst();
        assertEquals("nova", explode.type());
        assertEquals("origin", explode.str("at", null));
        assertEquals("ignite", explode.effects().getFirst().type());
        assertTrue(r.displays().contains("ember_burst"));
        assertTrue(r.particles().contains("DUST"));
        assertEquals(7, r.partCount());
        assertEquals(7, MechanicsSpec.flatten(r.parts()).size());
    }

    @Test
    void problemsAreReported() {
        Object raw = List.of(
                Map.of("type", "teleportz"),
                Map.of("type", "nova", "radius", 99, "effects", List.of(Map.of("damage", 1))),
                Map.of("type", "cone"),
                Map.of("type", "repeat", "times", 0),
                Map.of("type", "nova", "at", "moon", "effects", List.of(Map.of("explodez", 1))),
                Map.of("type", "zone", "effects", List.of(Map.of("effect", Map.of("id", "nope")))),
                Map.of("type", "self", "effects", List.of(Map.of("buff", Map.of("stats", Map.of("flying", 1))))),
                Map.of("type", "beam", "particle", "DUST::", "effects", List.of(Map.of("damage", 50))));
        MechanicsSpec.Result r = MechanicsSpec.parse(raw);
        assertFalse(r.ok());
        String all = String.join("\n", r.problems());
        assertTrue(all.contains("teleportz"), all);
        assertTrue(all.contains("radius"), all);
        assertTrue(all.contains("effects 가 없음"), all);
        assertTrue(all.contains("repeat"), all);
        assertTrue(all.contains("at 은"), all);
        assertTrue(all.contains("explodez"), all);
        assertTrue(all.contains("nope"), all);
        assertTrue(all.contains("flying"), all);
        assertTrue(all.contains("입자 표기"), all);
        assertTrue(all.contains("0~30"), all);
        assertFalse(MechanicsSpec.parse(List.of()).ok());
        assertFalse(MechanicsSpec.parse("cone").ok());
    }

    @Test
    void depthIsLimited() {
        Object raw = List.of(Map.of("type", "particle", "particle", "CRIT"));
        for (int i = 0; i < 9; i++) raw = List.of(Map.of("type", "repeat", "times", 1, "mechanics", raw));
        assertFalse(MechanicsSpec.parse(raw).ok());
    }

    /** items.yml 의 모든 조합형 스킬이 문법·fx·입자 이름까지 유효하고, 상위 무기마다 고유한 스킬 묶음을 가진다. */
    @Test
    void contentCatalogValid() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        int mech = 0;
        Set<String> names = new HashSet<>();
        for (ItemDef d : c.items().values()) {
            if (d.isWeapon() && d.rarity().atLeast(Rarity.EPIC)) {
                assertFalse(d.weaponSkills().isEmpty(), "상위 무기에 무기 스킬 없음: " + d.id());
                assertTrue(d.weaponSkills().stream().anyMatch(s -> s.id().equals("mechanics")),
                        "상위 무기에 고유(조합형) 스킬 없음: " + d.id());
            }
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                if (!s.id().equals("mechanics")) continue;
                mech++;
                assertTrue(names.add(s.name()), "조합형 스킬 이름 중복: " + s.name());
                MechanicsSpec.Result r = MechanicsSpec.parse(s.params().get("mechanics"));
                assertTrue(r.ok(), d.id() + " " + s.input() + ": " + r.problems());
                for (String fx : r.displays()) assertTrue(c.fxModels().containsKey(fx), d.id() + " 없는 fx: " + fx);
                for (String pn : r.particles()) assertTrue(MechanicsEngine.knownParticle(pn), d.id() + " 없는 입자: " + pn);
                assertTrue(s.cooldown() > 0, d.id() + " cooldown");
                assertFalse(s.description().isBlank(), d.id() + " description");
            }
        }
        assertTrue(mech >= 70, "조합형 스킬 수 " + mech);
    }
}
