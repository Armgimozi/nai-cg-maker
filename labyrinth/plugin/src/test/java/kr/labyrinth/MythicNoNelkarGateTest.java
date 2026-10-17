package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * CR37 주인 결정 — 넬카르(10층 보스)를 못 잡는 조도 신화 12 를 모두 만든다. 새 신화 6 은 도안을 배워 대장간에서만 만든다.
 * <ul>
 *   <li>새 신화 6 은 어느 루팅 표에서도 나오지 않는다 (중첩 표 · pick · one_of · rarity_pool 까지 펼쳐서).</li>
 *   <li>신화 레시피 재료는 모두 넬카르 표 밖에서 얻는다 — 다른 루팅 표 · 광산 · 그런 재료로 만드는 레시피(제련).</li>
 *   <li>신화 도안 12 는 모두 넬카르 표 밖에도 나온다.</li>
 * </ul>
 * "넬카르 표 밖" = 넬카르 표와, 넬카르 표만 부르는 하위 표를 뺀 모든 표.
 */
class MythicNoNelkarGateTest {

    static Content content;
    static String nelkar;
    static List<String> mythics;
    /** 넬카르를 안 잡아도 굴리는 표 (넬카르 표 · 넬카르 표만 부르는 하위 표 제외). */
    static Set<String> outside;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        nelkar = content.bossOfFloor(10).drops();
        mythics = new ArrayList<>();
        for (ItemDef d : content.items().values()) if (d.isWeapon() && d.rarity() == Rarity.MYTHIC) mythics.add(d.id());
        assertEquals(12, mythics.size(), "신화 무기 12");
        // 하위 표를 부르는 쪽: 아무도 부르지 않는 표가 뿌리 (몹 · 보스 · 상자 · 시련 · 금고). 넬카르 뿌리는 뺀다.
        Map<String, Set<String>> calledBy = new HashMap<>();
        for (LootTable t : content.lootTables().values()) {
            for (String sub : subTables(t)) calledBy.computeIfAbsent(sub, k -> new HashSet<>()).add(t.id());
        }
        outside = new TreeSet<>();
        List<String> todo = new ArrayList<>();
        for (String id : content.lootTables().keySet()) if (!calledBy.containsKey(id) && !id.equals(nelkar)) todo.add(id);
        while (!todo.isEmpty()) {
            String id = todo.remove(todo.size() - 1);
            if (!outside.add(id)) continue;
            todo.addAll(subTables(content.lootTable(id)));
        }
        assertTrue(!outside.contains(nelkar), "넬카르 표는 밖이 아님");
        assertTrue(outside.containsAll(List.of("floor08_boss", "floor09_boss", "special_trial_f10", "hoard_f10")), "8·9층 보스 · 10층 특별 시련 · 금고");
    }

    private static List<String> subTables(LootTable t) {
        List<String> out = new ArrayList<>();
        if (t == null) return out;
        for (LootTable.Entry e : all(t)) {
            if (e.kind() == LootTable.Kind.TABLE && e.table() != null) out.add(e.table());
            if (e.kind() == LootTable.Kind.PICK) for (LootTable.Pick p : e.pick()) out.add(p.table());
        }
        return out;
    }

    private static List<LootTable.Entry> all(LootTable t) {
        List<LootTable.Entry> es = new ArrayList<>(t.entries());
        es.addAll(t.guaranteed());
        return es;
    }

    /** 표 하나가 바로 주는 아이템 (하위 표는 따로 — outside 가 이미 펼쳐 둠). rarity_pool 은 그 단계·희귀도 후보. */
    private static Set<String> itemsOf(LootTable t) {
        Set<String> out = new HashSet<>();
        for (LootTable.Entry e : all(t)) {
            switch (e.kind()) {
                case ITEM -> out.add(e.item());
                case ONE_OF -> out.addAll(e.oneOf());
                case RARITY_POOL -> { for (ItemDef d : content.poolCandidates(e.floor(), e.rarityPool())) out.add(d.id()); }
                default -> { }
            }
        }
        return out;
    }

    @Test
    void newSixDropFromNoTable() {
        List<String> newSix = mythics.stream().filter(id -> content.item(id).sources().equals(List.of("craft"))).toList();
        assertEquals(6, newSix.size(), "새 신화 6 = 대장간만 " + newSix);
        assertEquals(Set.of("mountainheart_maul", "hightide_scythe", "comet_longbow", "wisp_lantern", "daybreak_bell", "waning_moon_sickle"),
                new TreeSet<>(newSix));
        Map<String, List<String>> found = new TreeMap<>();
        for (LootTable t : content.lootTables().values()) {
            for (String id : itemsOf(t)) if (newSix.contains(id)) found.computeIfAbsent(id, k -> new ArrayList<>()).add(t.id());
        }
        assertEquals(Map.of(), found, "새 신화가 루팅 표에 있음 (도안 제작만이어야 함)");
        for (String id : newSix) assertTrue(content.recipes().containsKey(id), id + " 레시피 (유일한 길)");
    }

    @Test
    void noMythicRecipeNeedsANelkarOnlyMaterial() {
        // 넬카르 밖에서 얻는 재료: 밖 표가 주는 것 + 광산 + 그런 재료만으로 만드는 레시피 결과 (제련 주괴 · 정수 정제)
        Set<String> got = new HashSet<>();
        for (String id : outside) got.addAll(itemsOf(content.lootTable(id)));
        for (ItemDef d : content.items().values()) if (d.isMineMaterial() && d.sources().contains("mine")) got.add(d.id());
        for (boolean grew = true; grew; ) {
            grew = false;
            for (RecipeDef r : content.recipes().values()) {
                ItemDef res = content.item(r.result());
                if (res == null || res.isGear() || got.contains(r.result()) || r.materials().isEmpty()) continue;
                if (got.containsAll(r.materials().keySet())) grew |= got.add(r.result());
            }
        }
        Map<String, List<String>> gated = new TreeMap<>();
        for (String id : mythics) {
            RecipeDef r = content.recipes().get(id);
            assertNotNull(r, id + " 레시피");
            for (String m : r.materials().keySet()) if (!got.contains(m)) gated.computeIfAbsent(id, k -> new ArrayList<>()).add(m);
        }
        assertEquals(Map.of(), gated, "넬카르만 주는 재료가 든 신화 레시피");
        assertTrue(!got.contains("abyssal_heart_fragment"), "심연 심장 파편은 넬카르만 (이 시험이 넬카르 표를 제대로 뺐는지)");
    }

    @Test
    void everyMythicBlueprintDropsOutsideNelkar() {
        Map<String, Set<String>> where = new TreeMap<>();
        for (String id : outside) {
            for (LootTable.Entry e : all(content.lootTable(id))) {
                if (e.kind() != LootTable.Kind.BLUEPRINT_OF || e.chance() <= 0) continue;
                for (String r : e.oneOf()) where.computeIfAbsent(r, k -> new TreeSet<>()).add(id);
            }
        }
        for (String id : mythics) {
            Set<String> w = where.getOrDefault(id, Set.of());
            assertTrue(w.contains("floor08_boss") || w.contains("floor09_boss"), id + " 신화 도안이 8·9층 보스에 없음: " + w);
            assertTrue(w.stream().anyMatch(t -> t.startsWith("special_trial_f")), id + " 신화 도안이 특별 시련에 없음: " + w);
        }
    }
}
