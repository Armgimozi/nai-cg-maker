package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 가진 방어구의 스탯 줄 이름 옮기기 (look_spec §3.3, 깃발 ITEM_COMBAT_VER 35): PDC 키만 바꾸고 값·순서는 그대로. */
class ArmorRenameMigrationTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    static Map<String, Double> rolls(Object... kv) {
        Map<String, Double> m = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put((String) kv[i], ((Number) kv[i + 1]).doubleValue());
        return m;
    }

    @Test
    void renamesOnlyTheOldKeyKeepingValues() {
        ItemDef chest = content.item("rimefang_chest");
        Map<String, Double> old = rolls("defense", 9, "DEX", 4, "LUK", 3, "crit_chance", 0.021);
        Map<String, Double> now = ItemMigration035.migrate(chest, old);
        assertEquals(rolls("defense", 9, "DEX", 4, "STR", 3, "crit_chance", 0.021), now);
        assertEquals(List.of("defense", "DEX", "STR", "crit_chance"), List.copyOf(now.keySet()), "줄 순서 그대로");
        // 이미 옮긴 것·다른 세트는 그대로
        assertEquals(now, ItemMigration035.migrate(chest, now));
        Map<String, Double> pit = rolls("defense", 3, "VIT", 2, "hp", 10);
        assertEquals(pit, ItemMigration035.migrate(content.item("pit_foreman_chest"), pit));
    }

    @Test
    void everyMigratedSetHasNoOldLineLeft() {
        ItemMigration035.ARMOR_RENAME.forEach((set, ren) -> {
            for (String id : content.sets().get(set).pieces()) {
                ItemDef d = content.item(id);
                Map<String, Double> old = new LinkedHashMap<>();
                d.stats().forEach((k, r) -> {
                    String back = ren.entrySet().stream().filter(e -> e.getValue().equals(k)).map(Map.Entry::getKey).findFirst().orElse(k);
                    old.put(back, r.min());
                });
                Map<String, Double> now = ItemMigration035.migrate(d, old);
                assertEquals(d.stats().keySet(), now.keySet(), id + " 옮긴 뒤 키 = 지금 정의");
            }
        });
    }
}
