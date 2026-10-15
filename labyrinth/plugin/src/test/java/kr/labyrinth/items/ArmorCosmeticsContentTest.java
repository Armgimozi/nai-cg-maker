package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.SortedSet;
import java.util.TreeSet;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** 장식이 생길 수 있는 세트 = 상의가 있는 세트 전부 (리소스팩 armor_pieces.set_specs 와 같은 규칙). */
class ArmorCosmeticsContentTest {

    @Test
    void everyArmourSetHasAChestPieceAndAPieceLook() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        SortedSet<String> chest = ArmorCosmetics.chestSets(c.items().values());
        SortedSet<String> all = new TreeSet<>();
        for (ItemDef d : c.items().values()) if (d.armorSet() != null && !d.armorSet().isBlank()) all.add(d.armorSet());
        assertEquals(all, chest, "상의 없는 세트는 장식이 안 생긴다");
        assertTrue(chest.size() >= 20, "세트 20종: " + chest);
        for (String set : chest) {
            assertTrue(set.matches("[a-z0-9_]+"), "리소스 경로로 쓰는 세트 id: " + set);
            for (ArmorPieceLayout.Part part : ArmorPieceLayout.Part.values()) {
                assertTrue(ArmorPieceLayout.modelPath(set, part).matches("armor_piece/[a-z0-9_]+/[a-z_]+"));
            }
        }
    }
}
