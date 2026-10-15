package kr.labyrinth.items.enhance;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.EnhanceDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.treasure.ChestTier;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비별 강화 재료 (content/enhance.yml, GDD §11.13): 번들 파일 검사 · 재료가 '그 장비를 얻는 곳'과 이어지는지
 * (제작 재료 / 나오는 곳 드롭, 그 층에서 얻을 수 있음) · 같은 층 구성 겹침 없음 · 구간별 비용 구성 · 전부 아니면 아무것도 소모 · 읽기 경고.
 */
class EnhanceMaterialsTest {

    static final Path CONTENT = Path.of("src/main/resources/content");
    static Content content;
    static EnhanceRules rules;
    static Map<String, Object> rawEnhance;

    @BeforeAll
    static void load() {
        ContentLoader.Result r = ContentLoader.load(CONTENT);
        assertTrue(r.problems().isEmpty(), () -> "콘텐츠 문제: " + r.problems());
        content = r.content();
        rules = new EnhanceRules(EnhanceRules.Config.DEFAULT);
        rawEnhance = ContentLoader.toPlain(YamlConfiguration.loadConfiguration(CONTENT.resolve("enhance.yml").toFile()));
    }

    // ── 번들 enhance.yml ──────────────────────────────────────────────────

    @Test
    void bundledFileIsOptionalAndLoaded() {
        assertTrue(ContentParser.FILES.contains("enhance.yml"));
        assertTrue(ContentParser.OPTIONAL_FILES.contains("enhance.yml"), "예전 서버에 파일이 없어도 문제 없음");
        EnhanceDef t = content.enhance();
        assertTrue(t.loaded());
        assertEquals(EnhanceDef.DEFAULT_BANDS, t.bands(), "low +1~+3 · mid +4~+6 · high +7~+10");
        assertEquals(List.of(), t.warnings(), "번들 enhance.yml 은 경고 없이 읽혀야 한다 (없는 장비·재료·구간)");
    }

    @Test
    void everyMaterialExistsAndEveryGearIsCovered() {
        @SuppressWarnings("unchecked")
        Map<String, Object> items = (Map<String, Object>) rawEnhance.get("items");
        assertNotNull(items);
        int skipped = 0;
        List<String> skippedIds = new ArrayList<>();
        for (Map.Entry<String, Object> e : items.entrySet()) {
            @SuppressWarnings("unchecked")
            Map<String, Object> bands = (Map<String, Object>) e.getValue();
            for (String band : List.of("low", "mid", "high")) assertTrue(bands.containsKey(band), e.getKey() + " 에 " + band + " 구간");
            for (Object b : bands.values()) {
                @SuppressWarnings("unchecked")
                Map<String, Object> mats = (Map<String, Object>) b;
                for (String m : mats.keySet()) {
                    ItemDef md = content.item(m);
                    assertNotNull(md, e.getKey() + ": 없는 재료 " + m);
                    assertEquals(ItemType.MATERIAL, md.type(), e.getKey() + ": " + m + " 은 재료가 아님");
                    assertFalse(m.endsWith("_enhance_stone"), e.getKey() + ": 강화석은 config.yml stones 가 맡는다");
                }
            }
            if (content.item(e.getKey()) == null) {
                skipped++;
                skippedIds.add(e.getKey());
            } else {
                assertTrue(EnhanceRules.enhanceable(content.item(e.getKey())), e.getKey() + " 은 강화할 수 없는 물건");
            }
        }
        System.out.println("ENHANCE enhance.yml 장비 " + items.size() + "개");
        assertEquals(0, skipped, "items.yml 에 없는 장비: " + skippedIds);
        for (ItemDef d : content.items().values()) {
            if (EnhanceRules.enhanceable(d)) assertTrue(content.enhance().has(d.id()),
                    d.id() + " 의 강화 재료가 없다 — python3 tools/gen_enhance.py 로 다시 만들 것");
        }
    }

    @Test
    void bandsFollowTheRules() {
        Set<String> cores = cores();
        assertEquals(10, cores.size(), "보스 핵 10종: " + cores);
        // 층별 high 단계 재료 종류 수: 일반 장비 최대 / 보스 장비 최소
        Map<Integer, int[]> normalKinds = new HashMap<>(), bossKinds = new HashMap<>();
        for (ItemDef d : content.items().values()) {
            if (!EnhanceRules.enhanceable(d)) continue;
            EnhanceDef t = content.enhance();
            List<EnhanceDef.Cost> low = t.costs(d.id(), 1), mid = t.costs(d.id(), 5), high = t.costs(d.id(), 10);
            assertEquals(1, low.size(), d.id() + " low = 주 재료 1종");
            assertEquals(2, mid.size(), d.id() + " mid = 주 재료 + 보조");
            assertEquals(3, high.size(), d.id() + " high = 주 재료 + 보조 + 귀한 재료/보스 핵");
            assertEquals(low.get(0).item(), mid.get(0).item(), d.id() + " mid 는 low 재료를 이어 쓴다");
            assertEquals(mid.get(0).item(), high.get(0).item(), d.id());
            assertEquals(mid.get(1).item(), high.get(1).item(), d.id() + " high 는 mid 보조를 이어 쓴다");
            // 단계 안에서 개수는 줄지 않는다 — 보스 장비의 귀한 재료가 보스 핵으로 바뀌는 단계(+9)만 예외
            for (int tg = 2; tg <= 10; tg++) {
                if (t.band(tg) != t.band(tg - 1)) continue;
                Map<String, Integer> a = asMap(t.costs(d.id(), tg - 1)), b = asMap(t.costs(d.id(), tg));
                boolean coreArrives = a.keySet().stream().noneMatch(cores::contains) && b.keySet().stream().anyMatch(cores::contains);
                for (var e : a.entrySet()) {
                    if (coreArrives && !b.containsKey(e.getKey())) continue;
                    assertTrue(b.getOrDefault(e.getKey(), 0) >= e.getValue(), d.id() + " +" + tg + " " + e.getKey());
                }
            }
            // 보스 고유 장비(·보스가 주는 칭호 보상) = +9·+10 에만 그 층 보스의 핵. 나머지 장비는 보스 핵을 쓰지 않는다.
            boolean bossGear = d.sources().contains("boss") || d.sources().contains("reward");
            String core = coreOf(d.floor());
            for (int tg = 1; tg <= 10; tg++) {
                Set<String> at = asMap(t.costs(d.id(), tg)).keySet();
                boolean has = at.stream().anyMatch(cores::contains);
                if (bossGear && tg >= 9) assertTrue(at.contains(core), d.id() + " +" + tg + " 에 " + d.floor() + "층 보스 핵 " + core);
                else assertFalse(has, d.id() + " +" + tg + " 에 보스 핵 " + at);
            }
            int[] kinds = (bossGear ? bossKinds : normalKinds).computeIfAbsent(d.floor(),
                    k -> new int[] {bossGear ? 99 : 0, bossGear ? 99 : 0, bossGear ? 99 : 0, bossGear ? 99 : 0});
            for (int tg = 7; tg <= 10; tg++) {
                int n = t.costs(d.id(), tg).size();
                kinds[tg - 7] = bossGear ? Math.min(kinds[tg - 7], n) : Math.max(kinds[tg - 7], n);
            }
        }
        // 보스 고유 장비가 같은 층 일반 장비보다 싼 high 단계가 없다 (+7·+8 은 귀한 재료, +9·+10 은 보스 핵 — 언제나 3종)
        assertEquals(10, bossKinds.size(), "층마다 보스 장비");
        for (var e : bossKinds.entrySet()) {
            int[] normal = normalKinds.get(e.getKey());
            assertNotNull(normal, e.getKey() + "층 일반 장비");
            for (int k = 0; k < 4; k++) {
                assertTrue(e.getValue()[k] >= normal[k], e.getKey() + "층 +" + (k + 7) + ": 보스 장비 재료 " + e.getValue()[k]
                        + "종 < 일반 장비 " + normal[k] + "종");
            }
        }
    }

    /**
     * 사장님 규칙: 장비 재료는 그 장비를 얻는 곳과 이어진다.
     * 제작법이 있으면 그 제작 재료(low·mid = 레시피에서 가장 많이 드는 두 재료), 없으면 그 장비를 주는 루팅 테이블의 드롭.
     * 귀한 재료는 레시피 · 나오는 곳 드롭 · 그것을 대장간에서 정제한 정수 안에서만. 모두 그 장비 층에서 얻을 수 있다.
     */
    @Test
    void materialsComeFromWhereTheItemComesFrom() {
        Map<String, RecipeDef> recipeOf = new HashMap<>();
        for (RecipeDef r : content.recipes().values()) recipeOf.putIfAbsent(r.result(), r);
        int crafted = 0, dropped = 0, mostUsedFirst = 0;
        for (ItemDef d : content.items().values()) {
            if (!EnhanceRules.enhanceable(d)) continue;
            EnhanceDef t = content.enhance();
            Set<String> used = new LinkedHashSet<>();
            for (int tg = 1; tg <= 10; tg++) used.addAll(asMap(t.costs(d.id(), tg)).keySet());
            String p = t.costs(d.id(), 1).get(0).item(), s = t.costs(d.id(), 5).get(1).item();
            Set<String> home = homeMaterials(d);
            Set<String> allowed = new HashSet<>(home);
            RecipeDef r = recipeOf.get(d.id());
            if (r != null) {
                crafted++;
                allowed.addAll(r.materials().keySet());
                // low · mid = 레시피의 두 주 재료 (같은 레시피 장비끼리 겹치지 않게 순서는 바뀔 수 있다)
                assertTrue(r.materials().containsKey(p) && r.materials().containsKey(s), d.id() + " P·S 는 제작 재료: " + p + ", " + s);
                int pc = r.materials().get(p), sc = r.materials().get(s);
                for (var e : r.materials().entrySet()) {
                    if (e.getKey().equals(p) || e.getKey().equals(s)) continue;
                    assertTrue(Math.min(pc, sc) >= e.getValue(), d.id() + " P·S 는 레시피에서 가장 많이 드는 두 재료 (" + e + ")");
                }
                int top = r.materials().values().stream().mapToInt(Integer::intValue).max().orElse(0);
                if (pc == top) mostUsedFirst++;
            } else {
                dropped++;
                assertTrue(home.contains(p) && home.contains(s), d.id() + " P·S 는 그 장비가 나오는 곳의 드롭: " + p + ", " + s + " / " + home);
            }
            allowed.addAll(refinedFrom(allowed));
            Set<String> floorMats = floorMaterials(d.floor());
            Set<String> obtainable = new HashSet<>(floorMats);
            obtainable.addAll(refinedFrom(floorMats));
            for (String m : used) {
                if (cores().contains(m)) continue; // 보스 핵은 bandsFollowTheRules 가 본다
                assertTrue(allowed.contains(m), d.id() + " 의 " + m + " 는 제작 재료도 나오는 곳 드롭도 아니다 (" + allowed + ")");
                assertTrue(obtainable.contains(m), d.id() + " 의 " + m + " 는 " + d.floor() + "층에서 얻을 수 없다");
            }
        }
        System.out.println("ENHANCE 제작 재료 " + crafted + "종 (주 재료 = 가장 많이 드는 재료 " + mostUsedFirst + "종) · 드롭 재료 " + dropped + "종");
        assertTrue(crafted > 150 && dropped > 30, crafted + " / " + dropped);
        assertTrue(mostUsedFirst * 3 >= crafted * 2, "제작 장비 대부분은 레시피에서 가장 많이 드는 재료가 주 재료: " + mostUsedFirst + "/" + crafted);
    }

    @Test
    void noTwoItemsOnAFloorShareTheSameMaterials() {
        Map<String, String> seen = new HashMap<>();
        List<String> same = new ArrayList<>();
        for (ItemDef d : content.items().values()) {
            if (!EnhanceRules.enhanceable(d)) continue;
            String other = seen.putIfAbsent(d.floor() + "|" + recipe(content.enhance(), d.id()), d.id());
            if (other != null) same.add(other + " = " + d.id());
        }
        System.out.println("ENHANCE 같은 층에서 강화 재료 구성(개수까지)이 똑같은 장비 " + same.size() + "쌍");
        assertEquals(List.of(), same, "같은 층 장비끼리 강화 재료 구성이 똑같다");
    }

    // ── 루팅 펼치기 (LootHomesTest 와 같은 방식) ─────────────────────────────

    private static Set<String> cores() {
        Set<String> cores = new HashSet<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.MATERIAL && d.sources().equals(List.of("boss"))) cores.add(d.id());
        }
        return cores;
    }

    private static String coreOf(int floor) {
        BossDef b = content.bossOfFloor(floor);
        assertNotNull(b, floor + "층 보스");
        for (LootTable.Entry e : content.lootTable(b.drops()).guaranteed()) {
            if (e.kind() == LootTable.Kind.ITEM && cores().contains(e.item())) return e.item();
        }
        throw new AssertionError(floor + "층 보스 확정 드롭에 핵이 없다");
    }

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

    /** 그 층 1회 클리어가 굴리는 테이블 → 집(common | elite | boss). */
    private static Map<String, String> floorRoots(int floor) {
        Map<String, String> out = new LinkedHashMap<>();
        for (MobDef m : content.mobs().values()) {
            if (m.floor() == floor && m.drops() != null) out.put(m.drops(), m.isElite() ? "elite" : "common");
        }
        BossDef b = content.bossOfFloor(floor);
        if (b != null) out.put(b.drops(), "boss");
        out.put("treasure_floor_" + floor, "common");
        out.put("gimmick_floor_" + floor, "common");
        for (ChestTier tier : ChestTier.values()) out.put("maze_chest_" + tier.id() + "_f" + floor, "common");
        return out;
    }

    private static Set<String> materialsOf(Iterable<String> tables) {
        Set<String> out = new HashSet<>();
        for (String t : tables) {
            for (String id : expand(t, new HashSet<>())) {
                ItemDef d = content.item(id);
                if (d != null && d.type() == ItemType.MATERIAL) out.add(id);
            }
        }
        return out;
    }

    private static Set<String> floorMaterials(int floor) {
        return materialsOf(floorRoots(floor).keySet());
    }

    /** 장비가 나오는 곳의 드롭 재료. 시작 지급 = 1층 몬스터·상자, 칭호 보상 = 그 층 보스, 대장간에서만 = 없음. */
    private static Set<String> homeMaterials(ItemDef d) {
        Map<String, String> roots = floorRoots(d.floor());
        List<String> homes = new ArrayList<>();
        for (String t : roots.keySet()) if (expand(t, new HashSet<>()).contains(d.id())) homes.add(t);
        if (homes.isEmpty() && d.sources().contains("reward")) homes.add(content.bossOfFloor(d.floor()).drops());
        if (homes.isEmpty() && d.sources().contains("starter")) {
            for (var e : floorRoots(1).entrySet()) if (e.getValue().equals("common")) homes.add(e.getKey());
        }
        assertFalse(homes.isEmpty() && !d.sources().equals(List.of("craft")), d.id() + " 이 나오는 곳이 없다 " + d.sources());
        return materialsOf(homes);
    }

    /** 대장간에서 have 의 재료만으로 정제할 수 있는 재료 (정수 5:1 — 재료 1종짜리 material 레시피). */
    private static Set<String> refinedFrom(Set<String> have) {
        Set<String> out = new HashSet<>();
        for (RecipeDef r : content.recipes().values()) {
            ItemDef res = content.item(r.result());
            if (res != null && res.type() == ItemType.MATERIAL && !r.materials().isEmpty() && have.containsAll(r.materials().keySet())) {
                out.add(r.result());
            }
        }
        return out;
    }

    private static String recipe(EnhanceDef t, String id) {
        StringBuilder sb = new StringBuilder();
        for (int tg = 1; tg <= 10; tg++) sb.append(tg).append(asMap(t.costs(id, tg))).append(';');
        return sb.toString();
    }

    private static Map<String, Integer> asMap(List<EnhanceDef.Cost> cs) {
        Map<String, Integer> m = new LinkedHashMap<>();
        for (EnhanceDef.Cost c : cs) m.merge(c.item(), c.amount(), Integer::sum);
        return m;
    }

    // ── 비용 구성 ─────────────────────────────────────────────────────────

    @Test
    void costIsStonesPlusBandMaterials() {
        ItemDef sword = content.item("corridor_longsword");
        assertNotNull(sword);
        EnhanceDef table = new EnhanceDef(true, EnhanceDef.DEFAULT_BANDS, Map.of(sword.id(), Map.of(
                "low", List.of(new EnhanceDef.Material("beetle_shell", List.of(2, 2, 3))),
                "mid", List.of(new EnhanceDef.Material("beetle_shell", List.of(3, 3, 4)), new EnhanceDef.Material("alpha_moss_crest", List.of(1))),
                "high", List.of(new EnhanceDef.Material("beetle_shell", List.of(4, 4, 5, 6)), new EnhanceDef.Material("alpha_moss_crest", List.of(1, 2)),
                        new EnhanceDef.Material("warden_heartwood", List.of(0, 0, 1, 1))))), List.of());
        String stone = rules.stoneFor(sword);
        int[][] want = { // 목표 단계 → {주 재료, 보조, 핵}
                {}, {2, 0, 0}, {2, 0, 0}, {3, 0, 0}, {3, 1, 0}, {3, 1, 0}, {4, 1, 0}, {4, 1, 0}, {4, 2, 0}, {5, 2, 1}, {6, 2, 1}};
        for (int tg = 1; tg <= 10; tg++) {
            EnhanceCost c = rules.cost(sword, tg, 0, table);
            assertEquals(rules.gold(sword, tg, 0), c.gold(), "+" + tg + " 골드");
            assertEquals(new EnhanceCost.Line(stone, rules.stoneCount(tg), true), c.lines().get(0), "+" + tg + " 강화석이 맨 앞");
            assertEquals(new EnhanceCost.Line(stone, rules.stoneCount(tg), true), c.stone());
            Map<String, Integer> m = new HashMap<>();
            for (EnhanceCost.Line l : c.materials()) m.put(l.item(), l.amount());
            assertEquals(want[tg][0], m.getOrDefault("beetle_shell", 0), "+" + tg + " 주 재료");
            assertEquals(want[tg][1], m.getOrDefault("alpha_moss_crest", 0), "+" + tg + " 보조 (모자란 목록은 마지막 값)");
            assertEquals(want[tg][2], m.getOrDefault("warden_heartwood", 0), "+" + tg + " 핵 (0 = 그 단계엔 없음)");
            assertEquals(1 + (want[tg][1] > 0 ? 1 : 0) + (want[tg][2] > 0 ? 1 : 0), m.size(), "+" + tg + " 개수 0 인 줄은 빠진다");
        }
        // max_level 을 올렸을 때 마지막 구간 너머는 마지막 값
        assertEquals(List.of(new EnhanceDef.Cost("beetle_shell", 6), new EnhanceDef.Cost("alpha_moss_crest", 2),
                new EnhanceDef.Cost("warden_heartwood", 1)), table.costs(sword.id(), 14));
        assertTrue(table.costs(sword.id(), 0).isEmpty());
        // 할인은 골드에만
        assertEquals(rules.gold(sword, 9, 0.2), rules.cost(sword, 9, 0.2, table).gold());
    }

    @Test
    void missingEntryFallsBackToStonesOnly() {
        ItemDef sword = content.item("corridor_longsword");
        for (EnhanceDef t : new EnhanceDef[] {EnhanceDef.EMPTY, null}) {
            EnhanceCost c = rules.cost(sword, 8, 0, t);
            assertEquals(1, c.lines().size(), "강화석만");
            assertTrue(c.materials().isEmpty());
            assertEquals(rules.stoneCount(8), c.stone().amount());
        }
        assertFalse(EnhanceDef.EMPTY.loaded());
        assertTrue(Content.empty().enhance().items().isEmpty());
    }

    @Test
    void sameItemAsStoneIsMergedIntoOneLine() {
        ItemDef sword = content.item("corridor_longsword");
        String stone = rules.stoneFor(sword);
        EnhanceDef table = new EnhanceDef(true, EnhanceDef.DEFAULT_BANDS, Map.of(sword.id(), Map.of(
                "low", List.of(new EnhanceDef.Material(stone, List.of(2)), new EnhanceDef.Material("moss_fiber", List.of(1))))), List.of());
        EnhanceCost c = rules.cost(sword, 1, 0, table);
        assertEquals(2, c.lines().size());
        assertEquals(new EnhanceCost.Line(stone, rules.stoneCount(1) + 2, true), c.lines().get(0), "강화석 줄로 합쳐 한 번에 확인");
        // 가진 강화석이 합친 개수보다 적으면 모자람
        assertEquals(List.of(c.lines().get(0)), c.missing(id -> id.equals(stone) ? 2 : 99));
    }

    // ── 전부 아니면 아무것도 ──────────────────────────────────────────────

    @Test
    void payTakesEverythingOrNothing() {
        EnhanceCost cost = new EnhanceCost(500, List.of(new EnhanceCost.Line("greater_enhance_stone", 2, true),
                new EnhanceCost.Line("slag_ingot", 5, false), new EnhanceCost.Line("executioner_edge", 1, false)));
        // 재료 하나가 모자람 → 골드도 재료도 그대로
        Map<String, Long> bag = bag(1000, 2, 5, 0);
        Map<String, Long> before = new HashMap<>(bag);
        EnhanceCost.Purse p = EnhanceCost.mapPurse(bag);
        assertFalse(cost.affordable(p));
        assertFalse(cost.pay(p));
        assertEquals(before, bag, "하나라도 모자라면 아무것도 안 가져감");
        assertEquals(List.of(cost.lines().get(2)), cost.missing(p::count));
        // 골드가 모자람 → 그대로
        bag = bag(499, 9, 9, 9);
        before = new HashMap<>(bag);
        assertFalse(cost.pay(EnhanceCost.mapPurse(bag)));
        assertEquals(before, bag);
        // 강화석이 모자람 → 그대로
        bag = bag(9999, 1, 9, 9);
        before = new HashMap<>(bag);
        assertFalse(cost.pay(EnhanceCost.mapPurse(bag)));
        assertEquals(before, bag);
        // 전부 있음 → 정확히 그만큼만
        bag = bag(800, 3, 5, 2);
        assertTrue(cost.pay(EnhanceCost.mapPurse(bag)));
        assertEquals(bag(300, 1, 0, 1), bag);
        // 골드 빼기가 실패하는 주머니(다른 곳에서 먼저 씀)라면 재료는 손대지 않는다
        Map<String, Long> racy = bag(800, 3, 5, 2);
        EnhanceCost.Purse inner = EnhanceCost.mapPurse(racy);
        EnhanceCost.Purse failingGold = new EnhanceCost.Purse() {
            @Override public long gold() { return inner.gold(); }
            @Override public int count(String item) { return inner.count(item); }
            @Override public boolean takeGold(long amount) { return false; }
            @Override public void take(String item, int amount) { inner.take(item, amount); }
        };
        assertFalse(cost.pay(failingGold));
        assertEquals(bag(800, 3, 5, 2), racy);
        // 확인 줄: 보유/필요
        List<EnhanceCost.Check> checks = cost.check(EnhanceCost.mapPurse(bag(0, 2, 1, 7))::count);
        assertTrue(checks.get(0).ok());
        assertFalse(checks.get(1).ok());
        assertEquals(1, checks.get(1).have());
        assertTrue(checks.get(2).ok());
    }

    private static Map<String, Long> bag(long gold, long stones, long slag, long edge) {
        Map<String, Long> m = new HashMap<>();
        m.put("$gold", gold);
        m.put("greater_enhance_stone", stones);
        m.put("slag_ingot", slag);
        m.put("executioner_edge", edge);
        return m;
    }

    // ── 읽기 경고 ─────────────────────────────────────────────────────────

    @Test
    void parserWarnsAndSkipsBadLines() {
        Map<String, Map<String, Object>> raw = rawContent();
        Map<String, Object> items = new LinkedHashMap<>();
        items.put("corridor_longsword", Map.of(
                "low", new LinkedHashMap<>(Map.of("beetle_shell", 2, "no_such_material", 3)),
                "mid", Map.of("beetle_shell", List.of(3, 3, 4), "corridor_longbow", 1),
                "sideways", Map.of("beetle_shell", 1),
                "high", Map.of("beetle_shell", "많이")));
        items.put("future_blade", Map.of("low", Map.of("beetle_shell", 2)));
        items.put("moss_fiber", Map.of("low", Map.of("beetle_shell", 2)));
        raw.put("enhance.yml", Map.of("version", 1, "items", items));
        ContentParser parser = new ContentParser();
        Content c = parser.parse(raw);
        assertTrue(parser.problems().isEmpty(), "강화 재료 오류는 콘텐츠 문제가 아니라 경고: " + parser.problems());
        EnhanceDef t = c.enhance();
        String w = String.join("\n", t.warnings());
        assertTrue(w.contains("no_such_material"), w);
        assertTrue(w.contains("corridor_longbow") && w.contains("재료(material)가 아니라"), w);
        assertTrue(w.contains("sideways"), w);
        assertTrue(w.contains("high.beetle_shell"), w);
        assertTrue(w.contains("moss_fiber: 무기·방어구·방패만"), w);
        assertTrue(w.contains("items.yml 에 없는 장비 1개") && w.contains("future_blade"), w);
        assertEquals(List.of(new EnhanceDef.Cost("beetle_shell", 2)), t.costs("corridor_longsword", 1), "틀린 줄만 빠진다");
        assertEquals(List.of(new EnhanceDef.Cost("beetle_shell", 3)), t.costs("corridor_longsword", 4));
        assertTrue(t.costs("corridor_longsword", 8).isEmpty());
        assertFalse(t.has("future_blade"));
        assertFalse(t.has("moss_fiber"));

        // 파일이 없으면 문제 없이 EMPTY (예전 서버)
        raw.remove("enhance.yml");
        ContentParser p2 = new ContentParser();
        Content c2 = p2.parse(raw);
        assertTrue(p2.problems().isEmpty(), p2.problems().toString());
        assertFalse(c2.enhance().loaded());
        assertTrue(c2.enhance().costs("corridor_longsword", 5).isEmpty());
    }

    @Test
    void customBandsAreRead() {
        Map<String, Map<String, Object>> raw = rawContent();
        raw.put("enhance.yml", Map.of("version", 1,
                "bands", new LinkedHashMap<>(Map.of("early", List.of(1, 5), "late", List.of(6, 10), "broken", List.of(3))),
                "items", Map.of("corridor_longsword", Map.of("early", Map.of("beetle_shell", List.of(1, 2)), "late", Map.of("moss_fiber", 4)))));
        ContentParser parser = new ContentParser();
        EnhanceDef t = parser.parse(raw).enhance();
        assertEquals(2, t.bands().size());
        assertTrue(String.join("\n", t.warnings()).contains("bands.broken"));
        assertEquals(List.of(new EnhanceDef.Cost("beetle_shell", 2)), t.costs("corridor_longsword", 5), "모자란 목록은 마지막 값");
        assertEquals(List.of(new EnhanceDef.Cost("moss_fiber", 4)), t.costs("corridor_longsword", 6));
    }

    private static Map<String, Map<String, Object>> rawContent() {
        Map<String, Map<String, Object>> raw = new HashMap<>();
        for (String f : ContentParser.FILES) {
            File file = CONTENT.resolve(f).toFile();
            if (!file.exists() || f.equals("enhance.yml")) continue;
            raw.put(f, ContentLoader.toPlain(YamlConfiguration.loadConfiguration(file)));
        }
        return raw;
    }
}
