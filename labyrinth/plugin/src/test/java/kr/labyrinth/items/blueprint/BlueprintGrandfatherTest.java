package kr.labyrinth.items.blueprint;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6 첫 접속 보호 (Q6): 이미 가진 희귀 이상 장비(만들 수 있는 것)의 도안만 배운 것으로 친다.
 * 일반·고급 장비 · 재료 · 레시피가 없는 장비(보스 고유 무기 등)는 아무것도 배우지 않는다.
 */
class BlueprintGrandfatherTest {

    static Content content;

    @BeforeAll
    static void load() { content = ContentLoader.load(Path.of("src/main/resources/content")).content(); }

    @Test
    void ownedRareGearTeachesItsRecipe() {
        List<RecipeDef> gated = BlueprintRules.gated(content);
        RecipeDef a = gated.get(0), b = gated.get(gated.size() - 1);
        Set<String> got = BlueprintRules.grandfather(content, List.of(a.result(), b.result(), a.result()));
        assertEquals(Set.of(a.id(), b.id()), got);
    }

    @Test
    void commonGearMaterialsAndUncraftableGearTeachNothing() {
        List<String> owned = new ArrayList<>();
        for (RecipeDef r : content.recipes().values()) {
            ItemDef d = content.item(r.result());
            if (!d.isGear() || !d.rarity().atLeast(Rarity.RARE)) owned.add(d.id());
        }
        int noRecipe = 0;
        for (ItemDef d : content.items().values()) {
            if (d.isGear() && d.rarity().atLeast(Rarity.RARE) && BlueprintRules.recipeFor(content, d.id()) == null) {
                owned.add(d.id());
                noRecipe++;
            }
            if (!d.isGear()) owned.add(d.id());
        }
        assertTrue(noRecipe > 0, "레시피 없는 희귀 이상 장비가 있어야 시험이 뜻이 있다");
        owned.add("no_such_item");
        assertEquals(Set.of(), BlueprintRules.grandfather(content, owned));
        assertEquals(Set.of(), BlueprintRules.grandfather(content, null));
    }

    @Test
    void everyGatedRecipeCanBeGrandfathered() {
        List<String> all = new ArrayList<>();
        for (RecipeDef r : BlueprintRules.gated(content)) all.add(r.result());
        assertEquals(BlueprintRules.gated(content).size(), BlueprintRules.grandfather(content, all).size());
    }
}
