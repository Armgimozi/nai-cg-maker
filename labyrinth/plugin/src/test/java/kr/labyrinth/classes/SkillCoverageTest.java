package kr.labyrinth.classes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.classes.skills.SkillRegistry;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** classes.yml 의 모든 직업 스킬에 Java 구현이 있고, 입력 키 4개가 직업마다 겹치지 않는지. */
class SkillCoverageTest {

    @Test
    void everyClassSkillHasImplementation() {
        Content content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        SkillRegistry registry = new SkillRegistry();
        List<String> missing = new ArrayList<>();
        int total = 0;
        for (ClassDef c : content.classes().values()) {
            for (ClassDef.SkillDef s : c.skills()) {
                total++;
                if (registry.get(s.id()) == null) missing.add(c.id() + "/" + s.id());
            }
        }
        assertTrue(missing.isEmpty(), () -> "구현 없는 스킬: " + missing);
        assertEquals(24, total);
        assertEquals(24, registry.all().size());
    }

    @Test
    void inputsAreUniquePerClass() {
        Content content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        for (ClassDef c : content.classes().values()) {
            for (String in : List.of("SWAP", "SNEAK_SWAP", "DROP", "SNEAK_DROP")) {
                long n = c.skills().stream().filter(s -> s.input().equalsIgnoreCase(in)).count();
                assertEquals(1, n, c.id() + " 의 " + in + " 스킬 수");
            }
        }
    }
}
