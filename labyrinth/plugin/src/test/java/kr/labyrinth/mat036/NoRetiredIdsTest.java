package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import org.junit.jupiter.api.Test;

/** 옛 광물 재료 8개 (+ 배포 전 잿불 가죽) 가 content 어디에도 없고, 새 id 33개는 모두 있다 (계약 §2.10 · §0 결정 4). */
class NoRetiredIdsTest {

    /** 아이템 id 를 적는 파일 (items.yml 은 키·획득처로 따로 본다 — 텍스처 모양 이름 rusted_iron 등은 아이템 id 가 아님). */
    static final List<String> FILES = List.of("loot.yml", "recipes.yml", "npcs.yml", "enhance.yml", "bosses.yml", "floors.yml", "titles.yml");

    @Test
    void retiredIdsAreGoneEverywhere() {
        List<String> left = new ArrayList<>();
        for (String f : FILES) {
            String text = Mat036.text(f);
            for (String id : Mat036.RETIRED) {
                if (Pattern.compile("(?<![a-z0-9_])" + id + "(?![a-z0-9_])").matcher(text).find()) left.add(f + ": " + id);
            }
        }
        assertEquals(List.of(), left, "옛 id 가 남음");
        Content c = Mat036.content();
        for (String id : Mat036.RETIRED) assertFalse(c.items().containsKey(id), id);
        for (var r : c.recipes().values()) for (String id : Mat036.RETIRED) assertFalse(r.materials().containsKey(id) || r.result().equals(id), r.id());
        for (var n : c.npcs().values()) for (var e : n.shop()) assertFalse(Mat036.RETIRED.contains(e.item()), n.id() + " 상점 " + e.item());
    }

    @Test
    void droppedNamesStayDropped() {
        // 주인 결정 1: 별철·흑요석 금속·보석은 없다 (아이템 id·이름)
        for (var d : Mat036.content().items().values()) {
            for (String w : List.of("starmetal", "obsidian")) assertFalse(d.id().contains(w), d.id());
            for (String w : List.of("별철", "흑요석")) assertFalse(d.name().contains(w), d.id() + " " + d.name());
        }
    }

    @Test
    void allNewIdsExist() {
        Content c = Mat036.content();
        List<String> ids = Mat036.json("materials.json").strings("new_ids");
        assertEquals(33, ids.size());
        Params items = Mat036.json("materials.json").sub("items");
        for (String id : ids) {
            assertNotNull(c.item(id), id);
            assertEquals(items.sub(id).str("name"), c.item(id).name(), id);
            assertEquals(items.sub(id).str("rarity"), c.item(id).rarity().id(), id);
        }
        assertTrue(c.recipes().size() >= 204, "레시피 187 → 204: " + c.recipes().size());
    }
}
