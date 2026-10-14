package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 번들된 content/*.yml 이 전부 로드되고 교차참조 검사를 통과하는지. */
class ContentLoadingTest {

    static ContentLoader.Result result;

    @BeforeAll
    static void load() {
        result = ContentLoader.load(Path.of("src/main/resources/content"));
    }

    @Test
    void parsesWithoutProblems() {
        assertTrue(result.problems().isEmpty(), () -> "파싱 문제:\n" + String.join("\n", result.problems()));
    }

    @Test
    void validatesCrossReferences() {
        ContentValidator.Report r = ContentValidator.validate(result.content());
        r.warnings().forEach(w -> System.out.println("[경고] " + w));
        assertTrue(r.ok(), () -> "검증 오류 " + r.errors().size() + "개:\n" + String.join("\n", r.errors()));
    }

    @Test
    void loadsEveryContentFile() {
        Content c = result.content();
        assertEquals(6, c.classes().size());
        assertTrue(c.items().size() > 100);
        assertFalse(c.sets().isEmpty());
        assertTrue(c.mobs().size() >= 40);
        assertEquals(10, c.bosses().size());
        assertEquals(10, c.floors().size());
        assertTrue(c.lootTables().size() > 50);
        assertFalse(c.recipes().isEmpty());
        assertFalse(c.achievements().isEmpty());
        assertFalse(c.npcs().isEmpty());
        assertFalse(c.auras().isEmpty());
        assertFalse(c.fxModels().isEmpty());
        assertFalse(c.arenas().isEmpty());
    }

    @Test
    void typedFieldsAreReadCorrectly() {
        Content c = result.content();
        ClassDef guardian = c.classDef("guardian");
        assertNotNull(guardian);
        assertEquals("수호기사", guardian.name());
        assertTrue(guardian.baseStat(Stat.VIT) > 0);
        assertEquals(4, guardian.skills().size());
        assertNotNull(guardian.skillByInput("SWAP"));

        ItemDef potion = c.item("minor_healing_potion");
        assertNotNull(potion);
        assertEquals("heal", potion.use().str("action"));

        BossDef b1 = c.bossOfFloor(1);
        assertNotNull(b1);
        assertEquals(1, b1.phaseAt(1.0));
        assertEquals(b1.phases().size(), b1.phaseAt(0.01));
        assertFalse(b1.rotation().isEmpty());

        LootTable t = c.lootTable("floor01_boss");
        assertNotNull(t);
        assertFalse(t.guaranteed().isEmpty());
        assertTrue(c.lootSettings().rarityWeight("nightmare", Rarity.LEGENDARY) > 1.0);
        assertEquals(1.0, c.lootSettings().rarityWeight("normal", Rarity.LEGENDARY));
    }
}
