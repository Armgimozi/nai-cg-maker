package kr.labyrinth.items.blueprint;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

/**
 * 주인 결정 (0.3.6): 대장간 목록에는 기본 레시피와 배운 도안의 레시피만 나온다.
 * 못 배운 도안 레시피를 잠긴 회색 줄("도안 필요")로 보여 주지 않고, "배운 것만" 거르개도 두지 않는다.
 */
class BlueprintHiddenTest {

    @Test
    void blacksmithHidesUnlearnedRecipes() throws Exception {
        String src = Files.readString(Path.of("src/main/java/kr/labyrinth/items/crafting/BlacksmithMenu.java"));
        assertTrue(src.contains("if (viewer != null && !crafting.blueprintOk(viewer, r)) continue;"), "못 배운 레시피는 목록에서 빠져야 한다");
        assertFalse(src.contains("도안 필요"), "잠긴 줄을 그리지 않는다");
        assertFalse(src.contains("learnedOnly"), "'배운 것만' 거르개는 없다");
    }
}
