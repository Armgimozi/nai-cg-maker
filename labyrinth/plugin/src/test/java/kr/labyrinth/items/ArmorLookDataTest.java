package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 방어구 겉모습 데이터 (look_spec §1.1·§8, review2 A5): 모든 방어구가 겉모습을 갖고, 평상복은 수련생·길잡이뿐. */
class ArmorLookDataTest {

    static Content content;

    /** 세트 없는 투구 (look_spec §1.1 — review2 A5: 이끼 투구 = 판금). */
    static final Map<String, ArmorLook> HELMS = Map.of("grove_mossguard_helm", ArmorLook.HEAVY,
            "silkqueen_veil", ArmorLook.LIGHT, "mycelking_spore_crown", ArmorLook.CLOTH,
            "osric_sluice_helm", ArmorLook.HEAVY, "nightmare_crown", ArmorLook.ANY);

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void everyArmourHasALook() {
        int n = 0;
        for (ItemDef d : content.items().values()) {
            if (d.type() != ItemType.ARMOR) {
                assertEquals(null, d.armorLook(), d.id() + " 방어구가 아닌데 겉모습");
                continue;
            }
            n++;
            ArmorLook l = d.armorLook();
            assertNotNull(l, d.id());
            if (d.isShield()) {
                assertEquals(ArmorLook.HEAVY, l, d.id() + " 방패 = 판금");
                assertFalse(d.raw().has("look"), d.id() + " 방패에는 look 을 적지 않는다");
                continue;
            }
            ItemSetDef set = d.setBonus() == null ? null : content.sets().get(d.setBonus());
            if (set == null) {
                assertEquals(HELMS.get(d.id()), l, d.id() + " 세트 없는 투구의 look");
                assertTrue(d.raw().has("look"), d.id() + " 세트 없는 투구는 look 을 적는다");
            } else {
                assertFalse(d.raw().has("look"), d.id() + " 세트 부위는 세트 look 을 쓴다");
                assertEquals(set.lookEffects() ? ArmorLook.byId(set.look()) : ArmorLook.PLAIN, l, d.id());
            }
        }
        assertTrue(n >= 95, "방어구 " + n);
        assertEquals(HELMS.keySet(), setless(), "세트 없는 투구 목록");
    }

    static Set<String> setless() {
        Set<String> out = new TreeSet<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.ARMOR && !d.isShield() && (d.setBonus() == null || !content.sets().containsKey(d.setBonus()))) out.add(d.id());
        }
        return out;
    }

    @Test
    void setLooksAndPlainSets() {
        Set<String> plain = new TreeSet<>();
        for (ItemSetDef s : content.sets().values()) {
            ArmorLook l = ArmorLook.byId(s.look());
            assertTrue(l != null && l.real(), "sets." + s.id() + " look = " + s.look());
            if (!s.lookEffects()) plain.add(s.id());
        }
        assertEquals(Set.of("novice", "wayfarer"), plain, "look_effects: false 는 수련생·길잡이뿐");
        for (String id : content.sets().get("novice").pieces()) assertEquals(ArmorLook.PLAIN, content.item(id).armorLook(), id);
        // 시작 지급은 모두 평상복 (1층 솔로는 바뀌지 않음)
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.ARMOR && d.sources().contains("starter")) assertEquals(ArmorLook.PLAIN, d.armorLook(), d.id());
        }
    }

    @Test
    void validatorHasNoLookErrorsOrWarnings() {
        ContentValidator.Report r = ContentValidator.validate(content);
        for (String e : r.errors()) assertFalse(e.contains("look"), e);
        for (String w : r.warnings()) {
            assertFalse(w.contains("look") || w.contains("요구 합") || w.contains("요구 나눔") || w.contains("가장 큰 요구")
                    || w.contains("requires_any") || w.contains("요구 능력치 "), w);
        }
    }
}
