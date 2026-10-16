package kr.labyrinth.items.blueprint;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

/** 도안 잠금 (0.3.6 Q6): 희귀 이상 장비 레시피만 잠기고, 일반·고급·재료 레시피는 처음부터 안다. */
class BlueprintGateTest {

    static Content content;

    @BeforeAll
    static void load() { content = ContentLoader.load(Path.of("src/main/resources/content")).content(); }

    @Test
    void onlyRareAndAboveGearRecipesAreLocked() {
        int locked = 0, open = 0;
        for (RecipeDef r : content.recipes().values()) {
            ItemDef d = content.item(r.result());
            assertNotNull(d, r.id());
            boolean want = d.isGear() && d.rarity().atLeast(Rarity.RARE);
            assertEquals(want, BlueprintRules.needsBlueprint(content, r), r.id() + " " + d.type() + " " + d.rarity());
            if (want) locked++;
            else open++;
            if (!want) assertTrue(BlueprintRules.canCraft(content, r, true, List.of()), r.id() + " 은 처음부터 만든다");
        }
        assertTrue(locked >= 100, "잠긴 레시피 " + locked);
        assertTrue(open >= 20, "열린 레시피 " + open);
        assertEquals(locked, BlueprintRules.gated(content).size());
    }

    @Test
    void learnedOrDisabledUnlocks() {
        RecipeDef r = BlueprintRules.gated(content).get(0);
        assertFalse(BlueprintRules.canCraft(content, r, true, List.of()));
        assertFalse(BlueprintRules.canCraft(content, r, true, List.of("something_else")));
        assertTrue(BlueprintRules.canCraft(content, r, true, List.of(r.id())));
        assertTrue(BlueprintRules.canCraft(content, r, false, List.of()), "blueprints.enabled: false 면 잠그지 않는다");
    }

    @Test
    void blueprintItemAndLootAreInContent() {
        ItemDef bp = content.item(BlueprintRules.ITEM_ID);
        assertNotNull(bp, "items.yml blueprint");
        assertEquals(ItemType.BLUEPRINT, bp.type());
        assertFalse(bp.isGear());
        assertTrue(BlueprintRules.active(content), "loot.yml 에 도안 항목");
        assertTrue(Content.empty().recipes().isEmpty());
        assertFalse(BlueprintRules.active(Content.empty()), "도안 아이템이 없으면 잠금 꺼짐");
        ContentValidator.Report rep = ContentValidator.validate(content);
        assertEquals(List.of(), rep.errors(), "검사 오류");
    }

    @Test
    void shopSellsOnlyRareAndRotates() {
        List<String> a = BlueprintRules.shopPicks(content, 20_000, 3);
        assertEquals(3, a.size());
        assertEquals(3, a.stream().distinct().count());
        for (String id : a) assertEquals(Rarity.RARE, content.item(content.recipes().get(id).result()).rarity(), id);
        assertEquals(a, BlueprintRules.shopPicks(content, 20_000, 3), "같은 날 같은 목록");
        boolean changed = false;
        for (long d = 20_001; d < 20_008; d++) changed |= !BlueprintRules.shopPicks(content, d, 3).equals(a);
        assertTrue(changed, "날마다 바뀐다");
        for (RecipeDef r : BlueprintRules.shopPool(content)) {
            assertFalse(content.item(r.result()).rarity().atLeast(Rarity.EPIC), r.id());
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    void shopPriceBeatsSellPrice() throws IOException {
        Map<String, Object> cfg = new Yaml().load(Files.readString(Path.of("src/main/resources/config.yml")));
        Map<String, Object> sell = (Map<String, Object>) cfg.get("sell");
        int rareMaterial = ((Map<String, Integer>) sell.get("materials")).get("rare");
        Map<String, Object> bp = (Map<String, Object>) cfg.get("blueprints");
        BlueprintRules.Settings s = new BlueprintRules.Settings((Boolean) bp.get("enabled"), (Integer) bp.get("shop_count"),
                (Integer) bp.get("shop_price_base"), (Integer) bp.get("shop_price_step"));
        assertEquals(BlueprintRules.Settings.DEFAULT, s, "config.yml blueprints = 코드 기본값");
        assertEquals("rare", content.item(BlueprintRules.ITEM_ID).rarity().id(), "팔 때 값 = 재료 희귀 값");
        for (RecipeDef r : BlueprintRules.shopPool(content)) {
            int price = BlueprintRules.shopPrice(content, r, s);
            assertTrue(price > rareMaterial * 4, r.id() + " " + price + " — 사서 되팔기로 골드가 늘지 않는다");
        }
    }
}
