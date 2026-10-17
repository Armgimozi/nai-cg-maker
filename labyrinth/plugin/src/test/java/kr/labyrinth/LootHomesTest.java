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
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.treasure.ChestTier;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비 획득처 구조 (0.3.5 — loot.yml · recipes.yml · items.yml sources). 장비는 단계(tier, 숨김)를 갖고, 보스가 아닌 장비는
 * 레벨 창이 겹치는 이웃 층 셋(tier−1·tier·tier+1)이 단계 풀 band_tNN_* 를 PICK 2 : 7 : 1 로 나눠 준다.
 * 집(종류) = 몬스터·상자(mix_fNN_drop) · 정예 · 보스(그 보스 고유) · 시련방 · 특별 시련 · 금고·미믹 · 대장간 · 상인 · 칭호 보상 · 시작 지급.
 * 루팅 테이블을 직접 펼쳐 다시 계산하므로 items.yml sources(툴팁·도감 표시)가 실제와 어긋나면 깨진다.
 */
class LootHomesTest {

    static Content content;
    static final List<String> STARTER = List.of("novice_cap", "novice_tunic", "novice_trousers", "novice_boots");

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    /** 테이블 펼침 (하위 테이블 · PICK 의 하위 표 전부) — 나올 수 있는 아이템 id 전부. */
    static Set<String> expand(String tableId, Set<String> seen) {
        Set<String> out = new HashSet<>();
        LootTable t = content.lootTable(tableId);
        if (t == null || !seen.add(tableId)) return out;
        for (LootTable.Entry e : all(t)) {
            switch (e.kind()) {
                case ITEM -> out.add(e.item());
                case ONE_OF -> out.addAll(e.oneOf());
                case TABLE -> out.addAll(expand(e.table(), new HashSet<>(seen)));
                case PICK -> { for (LootTable.Pick p : e.pick()) out.addAll(expand(p.table(), new HashSet<>(seen))); }
                case RARITY_POOL -> { }
            }
        }
        return out;
    }

    /** 그 표에서 닿는 하위 표 전부 (자기 포함). */
    static Set<String> reach(String tableId, Set<String> seen) {
        LootTable t = content.lootTable(tableId);
        if (t == null || !seen.add(tableId)) return seen;
        for (LootTable.Entry e : all(t)) {
            if (e.kind() == LootTable.Kind.TABLE) reach(e.table(), seen);
            if (e.kind() == LootTable.Kind.PICK) for (LootTable.Pick p : e.pick()) reach(p.table(), seen);
        }
        return seen;
    }

    static List<LootTable.Entry> all(LootTable t) {
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        return all;
    }

    private static String mazeTable(ChestTier tier, int floor) {
        return "maze_chest_" + tier.id() + "_f" + floor;
    }

    /** 층에 묶인 표 → (꼬리표, 층). 꼬리표 = items.yml sources 값 (drop · chest · elite · boss · trial · special · hoard). */
    record Labeled(String table, String tag, int floor) {}

    static List<Labeled> labeledTables() {
        List<Labeled> out = new ArrayList<>();
        for (MobDef m : content.mobs().values()) {
            if (m.drops() != null) out.add(new Labeled(m.drops(), m.isElite() ? "elite" : "drop", m.floor()));
        }
        for (BossDef b : content.bosses().values()) out.add(new Labeled(b.drops(), "boss", b.floor()));
        for (int f = 1; f <= content.maxFloor(); f++) {
            out.add(new Labeled("treasure_floor_" + f, "chest", f));
            out.add(new Labeled("gimmick_floor_" + f, "trial", f));
            out.add(new Labeled(String.format("special_trial_f%02d", f), "special", f));
            out.add(new Labeled(String.format("hoard_f%02d", f), "hoard", f));
            for (ChestTier tier : ChestTier.values()) out.add(new Labeled(mazeTable(tier, f), "chest", f));
        }
        return out;
    }

    /** 꼬리표 → 종류 (drop·chest 는 '몬스터·상자' 한 종류). */
    static String kind(String tag) {
        return tag.equals("drop") || tag.equals("chest") ? "common" : tag;
    }

    /** 장비 id → 실제 꼬리표 (루팅 · 레시피 · 칭호 · 상인 · 시작 지급). */
    static Map<String, Set<String>> actualTags() {
        Map<String, Set<String>> tags = new HashMap<>();
        for (Labeled l : labeledTables()) {
            assertNotNull(content.lootTable(l.table()), "없는 테이블 " + l.table());
            for (String id : expand(l.table(), new HashSet<>())) tags.computeIfAbsent(id, k -> new TreeSet<>()).add(l.tag());
        }
        for (RecipeDef r : content.recipes().values()) tags.computeIfAbsent(r.result(), k -> new TreeSet<>()).add("craft");
        for (AchievementDef a : content.achievements().values()) {
            for (String id : a.rewardItems().keySet()) tags.computeIfAbsent(id, k -> new TreeSet<>()).add("reward");
        }
        for (NpcDef n : content.npcs().values()) {
            for (NpcDef.ShopEntry s : n.shop()) tags.computeIfAbsent(s.item(), k -> new TreeSet<>()).add("shop");
        }
        for (String id : STARTER) tags.computeIfAbsent(id, k -> new TreeSet<>()).add("starter");
        return tags;
    }

    @Test
    void noRarityPoolLeft() {
        for (LootTable t : content.lootTables().values()) {
            for (LootTable.Entry e : t.entries()) assertFalse(e.kind() == LootTable.Kind.RARITY_POOL, t.id() + " 에 rarity_pool");
            for (LootTable.Entry e : t.guaranteed()) assertFalse(e.kind() == LootTable.Kind.RARITY_POOL, t.id() + " 에 rarity_pool");
        }
    }

    @Test
    void expandFollowsPick() {
        // mix_f03_drop 은 PICK 하나뿐 — 펼치면 band_t02·03·04_drop 의 장비가 모두 나온다
        Set<String> mix = expand("mix_f03_drop", new HashSet<>());
        for (String band : List.of("band_t02_drop", "band_t03_drop", "band_t04_drop")) {
            Set<String> b = expand(band, new HashSet<>());
            assertFalse(b.isEmpty(), band);
            assertTrue(mix.containsAll(b), "mix_f03_drop 펼침에 " + band + " 가 빠짐");
        }
        assertTrue(reach("maze_chest_wood_f3", new HashSet<>()).contains("band_t04_drop"));
    }

    @Test
    void everyGearHasOneOrTwoHomes() {
        Map<String, Set<String>> tags = actualTags();
        int gear = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isGear()) continue;
            gear++;
            Set<String> t = tags.getOrDefault(d.id(), Set.of());
            Set<String> kinds = new TreeSet<>();
            for (String x : t) kinds.add(kind(x));
            assertTrue(kinds.size() >= 1 && kinds.size() <= 2, d.id() + " 획득처 종류 " + kinds);
            if (d.isWeapon() && d.rarity() == Rarity.MYTHIC) {
                // 0.3.7 CR37: 옛 6 = 넬카르 + 대장간 (신화 도안), 새 6 = 대장간만 (도안 제작)
                assertTrue(kinds.equals(new TreeSet<>(List.of("boss", "craft"))) || kinds.equals(new TreeSet<>(List.of("craft"))),
                        d.id() + " 신화 획득처 종류 " + kinds);
            } else if (d.isWeapon() && d.rarity().atLeast(Rarity.EPIC)) {
                assertEquals(1, kinds.size(), d.id() + " 영웅 이상 무기 획득처 종류 " + kinds);
            }
            assertEquals(t, new TreeSet<>(d.sources()), d.id() + " 의 items.yml sources 가 실제 획득처와 다름");
            assertFalse(d.pool(), d.id() + " pool 은 false (rarity_pool 을 쓰지 않음)");
        }
        assertTrue(gear >= 380, "장비 수 " + gear);
    }

    @Test
    void gearComesFromItsTierWindowOnly() {
        // 보스가 아닌 장비는 tier−1·tier·tier+1 층 표에서만, 그리고 그 셋 중 둘 이상에서 (1·10 단계는 하나도 됨)
        Map<String, Set<Integer>> floors = new HashMap<>();
        for (Labeled l : labeledTables()) {
            if (l.tag().equals("boss")) continue;
            for (String id : expand(l.table(), new HashSet<>())) {
                ItemDef d = content.item(id);
                if (d != null && d.isGear()) floors.computeIfAbsent(id, k -> new TreeSet<>()).add(l.floor());
            }
        }
        int checked = 0;
        for (var e : floors.entrySet()) {
            ItemDef d = content.item(e.getKey());
            int t = d.tier();
            for (int f : e.getValue()) assertTrue(Math.abs(f - t) <= 1, d.id() + " (단계 " + t + ") 이 " + f + "층 표에서 나옴: " + e.getValue());
            int need = t == 1 || t == content.maxFloor() ? 1 : 2;
            assertTrue(e.getValue().size() >= need, d.id() + " (단계 " + t + ") 을 주는 층이 " + e.getValue());
            checked++;
        }
        assertTrue(checked >= 200, "층 표에서 나오는 장비 " + checked);
    }

    @Test
    void bossGearComesOnlyFromItsBoss() {
        // 툴팁·도감은 content.bossOfFloor(tier) 로 '보스 ○○' 를 적는다 → 보스 장비는 그 보스 표에서만 나와야 한다
        int n = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isGear() || !d.sources().contains("boss")) continue;
            BossDef b = content.bossOfFloor(d.tier());
            assertNotNull(b, d.id());
            assertTrue(expand(b.drops(), new HashSet<>()).contains(d.id()), d.id() + " 이 " + b.drops() + " 에 없음");
            // 0.3.7: 신화 무기는 그 단계(10층) 보스 + 아래 두 층 보스(8·9층)가 나눠 준다 — 10층 넬카르 표에는 12개 모두
            Set<String> home = new HashSet<>(Set.of(b.drops()));
            if (d.isWeapon() && d.rarity() == Rarity.MYTHIC) {
                for (int f = d.tier() - 2; f < d.tier(); f++) home.add(content.bossOfFloor(f).drops());
            }
            for (Labeled l : labeledTables()) {
                if (home.contains(l.table())) continue;
                assertFalse(expand(l.table(), new HashSet<>()).contains(d.id()), d.id() + " 이 " + l.table() + " 에서도 나옴");
            }
            n++;
        }
        assertTrue(n >= 40, "보스 장비 " + n);
    }

    @Test
    void bandPoolsShared() {
        // band_tNN_* 는 둘 이상의 층이 부른다 (1·10 단계는 하나도 됨) — 층 표 → PICK → 단계 풀
        Map<String, Set<Integer>> callers = new HashMap<>();
        for (Labeled l : labeledTables()) {
            for (String t : reach(l.table(), new HashSet<>())) {
                if (t.startsWith("band_t")) callers.computeIfAbsent(t, k -> new TreeSet<>()).add(l.floor());
            }
        }
        int bands = 0;
        for (String id : content.lootTables().keySet()) {
            if (!id.startsWith("band_t")) continue;
            bands++;
            int tier = Integer.parseInt(id.substring(6, 8));
            Set<Integer> fl = callers.getOrDefault(id, Set.of());
            int need = tier == 1 || tier == content.maxFloor() ? 1 : 2;
            assertTrue(fl.size() >= need, id + " 을 부르는 층 " + fl);
            for (int f : fl) assertTrue(Math.abs(f - tier) <= 1, id + " 을 " + f + "층이 부름");
        }
        assertEquals(50, bands, "단계 풀 (10단계 × drop·trial·special·hoard·elite)");
    }

    @Test
    void gearLevelReqFitsItsTier() {
        for (ItemDef d : content.items().values()) {
            if (!d.isGear() || d.tier() <= 0) continue;
            assertTrue(d.levelReq() <= 5 * d.tier(), d.id() + " level_req " + d.levelReq() + " > 5 × 단계 " + d.tier());
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
    void perFloorMazeChestTablesHaveNoDirectGear() {
        // 미로 상자 장비는 mix_fNN_drop 으로만 (직접 one_of·item 금지) · 묶음(bracket) 표에는 장비가 없다
        for (int f = 1; f <= content.maxFloor(); f++) {
            for (ChestTier tier : ChestTier.values()) {
                LootTable t = content.lootTable(mazeTable(tier, f));
                assertNotNull(t, mazeTable(tier, f));
                for (LootTable.Entry e : all(t)) {
                    List<String> ids = e.kind() == LootTable.Kind.ITEM ? List.of(e.item())
                            : e.kind() == LootTable.Kind.ONE_OF ? e.oneOf() : List.of();
                    for (String id : ids) assertFalse(content.item(id).isGear(), mazeTable(tier, f) + " 에 장비 직접 " + id);
                    if (e.kind() == LootTable.Kind.TABLE && e.table().startsWith("mix_")) {
                        assertEquals(String.format("mix_f%02d_drop", f), e.table(), mazeTable(tier, f));
                    }
                }
                assertTrue(reach(mazeTable(tier, f), new HashSet<>()).contains(String.format("mix_f%02d_drop", f)),
                        mazeTable(tier, f) + " 이 mix_f" + f + "_drop 을 부르지 않음");
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
                if (d != null && !d.isGear() && d.floor() == b.floor() && d.rarity().ordinal() >= Rarity.EPIC.ordinal()) {
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
                if (mat.floor() > 0 && res.tier() > 0) assertEquals(res.tier(), mat.floor(), r.id() + " 이 다른 층 재료 " + m + " 를 씀");
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
        Map<Stat, Integer> archer = Map.of(Stat.DEX, 20, Stat.STR, 12, Stat.VIT, 8);
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 400; i++) {
            int pieces = 0;
            boolean core = false;
            for (LootRoller.Drop d : roller.roll("floor01_boss", new LootRoller.Request("normal", 1.0, 0, i % 2 == 0 ? archer : null))) {
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
