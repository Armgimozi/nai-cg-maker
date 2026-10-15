package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.treasure.ChestTier;
import kr.labyrinth.items.loot.LootRoller;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비 획득처 구조 (loot.yml · recipes.yml · items.yml sources). 장비 하나는 자기 층에만 속하고 집은 최대 2곳 —
 * 몬스터·상자(그 층 gear_fNN_common) · 정예 · 보스(그 보스 고유) · 대장간 · 칭호 보상 · 시작 지급.
 * 루팅 테이블을 직접 펼쳐 다시 계산하므로 items.yml sources(툴팁·도감 표시)가 실제와 어긋나면 깨진다.
 */
class LootHomesTest {

    static Content content;
    static final List<String> STARTER = List.of("novice_cap", "novice_tunic", "novice_trousers", "novice_boots");

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    /** 테이블 펼침 (하위 테이블 포함) — 나올 수 있는 아이템 id 전부. */
    private static Set<String> expand(String tableId, Set<String> seen) {
        Set<String> out = new HashSet<>();
        LootTable t = content.lootTable(tableId);
        if (t == null || !seen.add(tableId)) return out;
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> out.add(e.item());
                case ONE_OF -> out.addAll(e.oneOf());
                case TABLE -> out.addAll(expand(e.table(), new HashSet<>(seen)));
                case RARITY_POOL -> { }
            }
        }
        return out;
    }

    private static String mazeTable(ChestTier tier, int floor) {
        return "maze_chest_" + tier.id() + "_f" + floor;
    }

    /** 층에 묶인 테이블 → (집, 층). 집 = common(몬스터·상자) | elite | boss. */
    private record Labeled(String table, String home, int floor) {}

    private static List<Labeled> labeledTables() {
        List<Labeled> out = new ArrayList<>();
        for (MobDef m : content.mobs().values()) {
            if (m.drops() != null) out.add(new Labeled(m.drops(), m.isElite() ? "elite" : "common", m.floor()));
        }
        for (BossDef b : content.bosses().values()) out.add(new Labeled(b.drops(), "boss", b.floor()));
        for (int f = 1; f <= content.maxFloor(); f++) {
            out.add(new Labeled("treasure_floor_" + f, "common", f));
            out.add(new Labeled("gimmick_floor_" + f, "common", f));
            for (ChestTier tier : ChestTier.values()) out.add(new Labeled(mazeTable(tier, f), "common", f));
        }
        return out;
    }

    private static final Map<String, Set<String>> TAGS = Map.of(
            "common", Set.of("drop", "chest"), "elite", Set.of("elite"), "boss", Set.of("boss"),
            "craft", Set.of("craft"), "reward", Set.of("reward"), "shop", Set.of("shop"), "starter", Set.of("starter"));

    @Test
    void noRarityPoolLeft() {
        for (LootTable t : content.lootTables().values()) {
            for (LootTable.Entry e : t.entries()) assertFalse(e.kind() == LootTable.Kind.RARITY_POOL, t.id() + " 에 rarity_pool");
            for (LootTable.Entry e : t.guaranteed()) assertFalse(e.kind() == LootTable.Kind.RARITY_POOL, t.id() + " 에 rarity_pool");
        }
    }

    @Test
    void everyGearHasOneOrTwoHomesOnItsOwnFloor() {
        Map<String, Set<String>> homes = new HashMap<>();
        Map<String, Set<Integer>> floors = new HashMap<>();
        for (Labeled l : labeledTables()) {
            assertNotNull(content.lootTable(l.table()), "없는 테이블 " + l.table());
            for (String id : expand(l.table(), new HashSet<>())) {
                ItemDef d = content.item(id);
                if (d == null || !d.isGear()) continue;
                homes.computeIfAbsent(id, k -> new TreeSet<>()).add(l.home());
                floors.computeIfAbsent(id, k -> new TreeSet<>()).add(l.floor());
            }
        }
        for (RecipeDef r : content.recipes().values()) homes.computeIfAbsent(r.result(), k -> new TreeSet<>()).add("craft");
        for (AchievementDef a : content.achievements().values()) {
            for (String id : a.rewardItems().keySet()) homes.computeIfAbsent(id, k -> new TreeSet<>()).add("reward");
        }
        for (NpcDef n : content.npcs().values()) {
            for (NpcDef.ShopEntry s : n.shop()) homes.computeIfAbsent(s.item(), k -> new TreeSet<>()).add("shop");
        }
        for (String id : STARTER) homes.computeIfAbsent(id, k -> new TreeSet<>()).add("starter");

        int gear = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isGear()) continue;
            gear++;
            Set<String> h = homes.getOrDefault(d.id(), Set.of());
            assertTrue(h.size() >= 1 && h.size() <= 2, d.id() + " 획득처 " + h);
            Set<Integer> fl = floors.getOrDefault(d.id(), Set.of());
            assertTrue(fl.isEmpty() || fl.equals(Set.of(d.floor())), d.id() + " (floor " + d.floor() + ") 이 다른 층에서 나옴: " + fl);
            Set<String> tags = new TreeSet<>();
            for (String x : h) tags.addAll(TAGS.get(x));
            assertEquals(tags, new TreeSet<>(d.sources()), d.id() + " 의 items.yml sources 가 실제 획득처와 다름");
            assertFalse(d.pool(), d.id() + " pool 은 false (rarity_pool 을 쓰지 않음)");
        }
        assertTrue(gear >= 250, "장비 수 " + gear);
    }

    @Test
    void bossGearComesOnlyFromItsOwnFloorBoss() {
        // 툴팁·도감은 content.bossOfFloor(floor) 로 '보스 ○○(N층)' 을 적는다 → 보스 장비는 그 층 보스 테이블에서만 나와야 한다
        for (ItemDef d : content.items().values()) {
            if (!d.isGear() || !d.sources().contains("boss")) continue;
            BossDef b = content.bossOfFloor(d.floor());
            assertNotNull(b, d.id());
            assertTrue(expand(b.drops(), new HashSet<>()).contains(d.id()), d.id() + " 이 " + b.drops() + " 에 없음");
            for (Labeled l : labeledTables()) {
                if (l.table().equals(b.drops())) continue;
                assertFalse(expand(l.table(), new HashSet<>()).contains(d.id()), d.id() + " 이 " + l.table() + " 에서도 나옴");
            }
        }
    }

    @Test
    void gearLevelReqFitsItsFloorRange() {
        // 그 층 장비(보스 장비 포함)는 그 층 레벨 구간 최대값 안에서 낄 수 있어야 한다 — 다음 층 레벨이 돼야 끼는 장비 금지
        for (ItemDef d : content.items().values()) {
            if (!d.isGear() || d.floor() <= 0) continue;
            int max = content.floor(d.floor()).levelRange().max();
            assertTrue(d.levelReq() <= max, d.id() + " level_req " + d.levelReq() + " > " + d.floor() + "층 구간 최대 " + max);
        }
        for (RecipeDef r : content.recipes().values()) {
            ItemDef res = content.item(r.result());
            if (res.isGear()) assertEquals(res.levelReq(), r.levelReq(), r.id() + " 레시피 level_req 가 장비와 다름");
        }
    }

    @Test
    void starterKitNeverDropsOrCrafts() {
        Set<String> anywhere = new HashSet<>();
        for (String t : content.lootTables().keySet()) anywhere.addAll(expand(t, new HashSet<>()));
        for (RecipeDef r : content.recipes().values()) {
            anywhere.add(r.result());
            anywhere.addAll(r.materials().keySet());
        }
        for (String id : STARTER) {
            ItemDef d = content.item(id);
            assertNotNull(d, id);
            assertEquals(List.of("starter"), d.sources(), id);
            assertEquals(1, d.levelReq(), id);
            assertEquals("novice", d.setBonus(), id);
            assertFalse(anywhere.contains(id), id + " 이 루팅·레시피에 있음");
        }
        assertEquals(new LinkedHashSet<>(STARTER), new LinkedHashSet<>(content.sets().get("novice").pieces()));
    }

    @Test
    void perFloorMazeChestTablesExistAndBracketTablesHaveNoGear() {
        for (int f = 1; f <= content.maxFloor(); f++) {
            for (ChestTier tier : ChestTier.values()) {
                assertNotNull(content.lootTable(mazeTable(tier, f)), mazeTable(tier, f));
                for (String id : expand(mazeTable(tier, f), new HashSet<>())) {
                    ItemDef d = content.item(id);
                    if (d.isGear()) assertEquals(f, d.floor(), mazeTable(tier, f) + " → " + id);
                }
            }
        }
        for (int bracket = 1; bracket <= 4; bracket++) {
            for (ChestTier tier : ChestTier.values()) {
                String id = tier.table(1, bracket);
                assertNotNull(content.lootTable(id), id);
                for (String item : expand(id, new HashSet<>())) assertFalse(content.item(item).isGear(), id + " 에 장비 " + item);
            }
        }
    }

    @Test
    void bossCoresForgeOnlyTheirOwnBossGear() {
        // 보스 핵 = 그 보스 확정 드롭 중 그 층 영웅 이상 재료
        Map<String, Integer> cores = new HashMap<>();
        for (BossDef b : content.bosses().values()) {
            for (LootTable.Entry e : content.lootTable(b.drops()).guaranteed()) {
                ItemDef d = content.item(e.item());
                if (d != null && !d.isGear() && d.floor() == b.floor() && d.rarity().ordinal() >= kr.labyrinth.content.Rarity.EPIC.ordinal()) {
                    cores.put(d.id(), b.floor());
                }
            }
        }
        assertEquals(10, cores.size(), "보스 핵 " + cores);
        Set<String> used = new HashSet<>();
        for (RecipeDef r : content.recipes().values()) {
            ItemDef res = content.item(r.result());
            for (String m : r.materials().keySet()) {
                ItemDef mat = content.item(m);
                if (mat.floor() > 0 && res.floor() > 0) assertEquals(res.floor(), mat.floor(), r.id() + " 이 다른 층 재료 " + m + " 를 씀");
                if (cores.containsKey(m)) {
                    used.add(m);
                    assertTrue(res.sources().contains("boss"), r.id() + " 은 보스 장비가 아닌데 핵 " + m + " 를 씀");
                }
            }
        }
        // 영웅 이상 보스 무기는 제작법이 없어(획득처 1곳) 10층 핵처럼 레시피에 안 쓰이는 핵도 있다 — 그 보스 장비 +9·+10 강화 재료로는 쓰인다
        for (ItemDef d : content.items().values()) {
            if (!d.isGear()) continue;
            for (int t = 1; t <= 10; t++) {
                for (var c : content.enhance().costs(d.id(), t)) if (cores.containsKey(c.item())) used.add(c.item());
            }
        }
        assertEquals(cores.keySet(), used, "쓰이지 않는 보스 핵");
    }

    @Test
    void floorOneBossAlwaysGivesOneUniquePiece() {
        Set<String> unique = Set.of("grove_warden_maul", "grove_rootstring_bow", "grove_heartwood_staff", "grove_mossguard_helm");
        LootRoller roller = new LootRoller(content, new Random(5));
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 400; i++) {
            int pieces = 0;
            boolean core = false;
            for (LootRoller.Drop d : roller.roll("floor01_boss", new LootRoller.Request("normal", 1.0, 0, i % 2 == 0 ? "hunter" : null))) {
                if (unique.contains(d.itemId())) {
                    pieces++;
                    seen.add(d.itemId());
                }
                if (d.itemId().equals("warden_heartwood")) core = true;
            }
            assertEquals(1, pieces, "1층 보스 고유 장비는 처치마다 정확히 1개");
            assertTrue(core, "보스 핵 확정");
        }
        assertEquals(unique, seen, "4종 모두 나올 수 있음");
    }
}
