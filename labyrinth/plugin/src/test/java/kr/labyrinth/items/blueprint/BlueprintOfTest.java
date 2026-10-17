package kr.labyrinth.items.blueprint;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 신화 도안 루팅 {@code {blueprint_of: [레시피 id…], chance}} (0.3.7 myth-037).
 * <ul>
 *   <li>파싱: 목록 · chance · amount · min_difficulty, 빈 목록은 문제로 알리고 뺀다.</li>
 *   <li>검사기: 없는 레시피 · 도안이 필요 없는 레시피 · 빈 목록 = 오류, 신화가 아닌 레시피 · 겹친 id = 경고,
 *       신화 레시피에 blueprint_of 출처가 없으면 오류, 신화 무기 sources [boss, craft] 는 통과.</li>
 *   <li>굴림: 목록 안에서만 · 빌드 편향 0.65 (맞는 것 쪽으로) · 확률 식은 일반 도안과 같다.</li>
 *   <li>일반 {@code {blueprint: N}} 뽑기 10만 번에 신화 0 · active() 가 blueprint_of 만 있어도 켜진다.</li>
 * </ul>
 * 콘텐츠 = {@link MythicFixture} (D 데이터 전에는 번들에 명세 꼴을 덧붙인 것, 뒤에는 번들 그대로).
 */
class BlueprintOfTest {

    static Content content;
    static List<String> mythics;

    @BeforeAll
    static void load() {
        content = MythicFixture.content();
        mythics = new ArrayList<>();
        for (String id : MythicFixture.mythicWeapons(content)) if (BlueprintRules.recipeFor(content, id) != null) mythics.add(id);
        assertTrue(mythics.size() >= 6, "신화 레시피 " + mythics);
    }

    private static Map<String, Object> entry(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    @Test
    void parsesBlueprintOfEntries() {
        List<Object> entries = new ArrayList<>();
        entries.add(entry("blueprint_of", List.of("celestial_oathkeeper", "tempest_bow"), "chance", 0.05));
        entries.add(entry("blueprint_of", List.of("eclipse_blade"), "chance", 0.1, "amount", 2, "min_difficulty", "hard"));
        entries.add(entry("blueprint_of", List.of(), "chance", 0.1));
        entries.add(entry("blueprint_of", null, "chance", 0.1));
        entries.add(entry("blueprint", 10, "chance", 0.4));
        Map<String, Object> t = entry("rolls", 1, "entries", entries);
        ContentParser parser = new ContentParser();
        Content c = parser.parse(Map.of("loot.yml", Map.of("tables", Map.of("t", t))));
        List<LootTable.Entry> es = c.lootTable("t").entries();
        assertEquals(3, es.size(), es.toString());
        LootTable.Entry a = es.get(0), b = es.get(1), bp = es.get(2);
        assertEquals(LootTable.Kind.BLUEPRINT_OF, a.kind());
        assertEquals(List.of("celestial_oathkeeper", "tempest_bow"), a.oneOf());
        assertEquals(0.05, a.chance(), 1e-12);
        assertEquals(0, a.floor());
        assertEquals(IntRange.ONE, a.amount());
        assertNull(a.minDifficulty());
        assertEquals(LootTable.Kind.BLUEPRINT_OF, b.kind());
        assertEquals(new IntRange(2, 2), b.amount());
        assertEquals("hard", b.minDifficulty());
        assertEquals(LootTable.Kind.BLUEPRINT, bp.kind(), "blueprint 와 blueprint_of 는 다른 항목");
        assertEquals(10, bp.floor());
        long empty = parser.problems().stream().filter(p -> p.contains("blueprint_of 가 비어 있음")).count();
        assertEquals(2, empty, parser.problems().toString());
    }

    // ── 검사기 ──────────────────────────────────────────────

    private static Content withTables(Content c, Map<String, LootTable> extra) {
        Map<String, LootTable> tables = new HashMap<>(c.lootTables());
        tables.putAll(extra);
        return new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(tables), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces(), c.enhance(), c.mine());
    }

    static LootTable.Entry of(double chance, List<String> ids) {
        return new LootTable.Entry(LootTable.Kind.BLUEPRINT_OF, null, null, 0, ids, null, chance, IntRange.ONE, null);
    }

    /** 처음부터 아는 레시피 하나 (일반·고급 장비 또는 재료). */
    static String openRecipe() {
        for (RecipeDef r : content.recipes().values()) if (!BlueprintRules.needsBlueprint(content, r)) return r.id();
        throw new AssertionError("처음부터 아는 레시피가 없음");
    }

    /** 신화가 아닌 도안 레시피 하나. */
    static String rareRecipe() {
        return BlueprintRules.drawable(content).get(0).id();
    }

    @Test
    void fixtureValidatesWithoutNewProblems() {
        ContentValidator.Report r = ContentValidator.validate(content);
        assertTrue(r.ok(), String.join("\n", r.errors()));
        List<String> mythicWarn = new ArrayList<>();
        for (String w : r.warnings()) {
            if (w.contains("blueprint_of") || w.contains("신화")) mythicWarn.add(w);
            for (String id : mythics) if (w.startsWith("items." + id + ":") || w.startsWith("recipes." + id + ":")) mythicWarn.add(w);
        }
        assertEquals(List.of(), mythicWarn, "신화 무기 sources [boss, craft] · 8·9·10층 보스 · blueprint_of 는 경고 없이 통과");
    }

    @Test
    void validatorChecksBlueprintOf() {
        String open = openRecipe(), rare = rareRecipe(), myth = mythics.get(0);
        Map<String, LootTable> m = new HashMap<>();
        m.put("t_bp", new LootTable("t_bp", 1, List.of(
                of(0.1, List.of("no_such_recipe")),
                of(0.1, List.of(open)),
                of(0.1, List.of()),
                of(0.1, List.of(rare)),
                of(0.1, List.of(myth, myth)),
                of(1.5, List.of(myth))), List.of(), IntRange.ZERO));
        ContentValidator.Report r = ContentValidator.validate(withTables(content, m));
        String errors = String.join("\n", r.errors()), warnings = String.join("\n", r.warnings());
        assertTrue(errors.contains("loot.t_bp.blueprint_of: 없는 레시피 'no_such_recipe'"), errors);
        assertTrue(errors.contains("loot.t_bp.blueprint_of: 도안이 필요 없는 레시피 '" + open + "'"), errors);
        assertTrue(errors.contains("loot.t_bp: blueprint_of 비어 있음"), errors);
        assertTrue(errors.contains("loot.t_bp: chance 는 0~1: 1.5"), errors);
        assertEquals(4, r.errors().size() - ContentValidator.validate(content).errors().size(), errors);
        assertTrue(warnings.contains("loot.t_bp.blueprint_of: 신화가 아닌 레시피 '" + rare + "'"), warnings);
        assertTrue(warnings.contains("loot.t_bp.blueprint_of: 같은 레시피가 두 번: " + myth), warnings);
    }

    @Test
    void mythicRecipeNeedsABlueprintOfSource() {
        // blueprint_of 를 모두 지운 콘텐츠 (chance 0 만 남긴 표 하나 — 0 은 출처로 치지 않는다)
        Map<String, LootTable> stripped = new HashMap<>();
        for (LootTable t : content.lootTables().values()) {
            List<LootTable.Entry> es = new ArrayList<>(), gs = new ArrayList<>();
            for (LootTable.Entry e : t.entries()) if (e.kind() != LootTable.Kind.BLUEPRINT_OF) es.add(e);
            for (LootTable.Entry e : t.guaranteed()) if (e.kind() != LootTable.Kind.BLUEPRINT_OF) gs.add(e);
            stripped.put(t.id(), new LootTable(t.id(), t.rolls(), es, gs, t.gold()));
        }
        stripped.put("t_zero", new LootTable("t_zero", 1, List.of(of(0.0, mythics)), List.of(), IntRange.ZERO));
        Content none = withTables(content, stripped);
        List<String> errors = ContentValidator.validate(none).errors();
        for (String id : mythics) {
            RecipeDef r = BlueprintRules.recipeFor(content, id);
            assertTrue(errors.contains("recipes." + r.id() + ": 신화 레시피인데 loot.yml blueprint_of 출처가 없음 — 도안을 얻을 곳이 없어 만들 수 없다"),
                    String.join("\n", errors));
        }
        assertFalse(String.join("\n", ContentValidator.validate(content).errors()).contains("blueprint_of 출처가 없음"));
    }

    @Test
    void blueprintOfSourcesListsTablesWithAChance() {
        // 검사기·도감이 같이 쓰는 출처 표 (FX37 — ContentValidator 에서 BlueprintRules 로 옮김): 확률 0 은 출처가 아니다
        Map<String, java.util.Set<String>> src = BlueprintRules.blueprintOfSources(content);
        for (String id : mythics) {
            RecipeDef r = BlueprintRules.recipeFor(content, id);
            assertFalse(src.getOrDefault(r.id(), java.util.Set.of()).isEmpty(), r.id() + " 출처 없음");
        }
        Map<String, LootTable> zero = new HashMap<>();
        zero.put("t_zero", new LootTable("t_zero", 1, List.of(of(0.0, mythics)), List.of(), IntRange.ZERO));
        assertFalse(BlueprintRules.blueprintOfSources(withTables(content, zero)).values().stream().anyMatch(t -> t.contains("t_zero")));
        assertTrue(BlueprintRules.blueprintOfSources(null).isEmpty());
    }

    @Test
    void onlyMythicWeaponsMayComeFromBossAndCraft() {
        // 신화 무기: [boss, craft] 통과 (fixtureValidatesWithoutNewProblems). 그런데 신화를 특별 시련 상자에 넣으면 경고
        String myth = mythics.get(0);
        LootTable sp = content.lootTable("special_trial_f10");
        List<LootTable.Entry> es = new ArrayList<>(sp.entries());
        es.add(new LootTable.Entry(LootTable.Kind.ITEM, myth, null, 0, List.of(), null, 0.01, IntRange.ONE, null));
        String w = String.join("\n", ContentValidator.validate(withTables(content,
                Map.of(sp.id(), new LootTable(sp.id(), sp.rolls(), es, sp.guaranteed(), sp.gold())))).warnings());
        assertTrue(w.contains("items." + myth + ": 신화 무기인데 획득처가 보스·특별 시련·대장간 — 보스, 보스·대장간, 또는 대장간이어야 함"), w);
        // 7층 보스(창 밖 — 신화는 8·9·10층 보스만)
        LootTable b7 = content.lootTable("floor07_boss");
        List<LootTable.Entry> e7 = new ArrayList<>(b7.entries());
        e7.add(new LootTable.Entry(LootTable.Kind.ONE_OF, null, null, 0, List.of(myth), null, 0.01, IntRange.ONE, null));
        String w7 = String.join("\n", ContentValidator.validate(withTables(content,
                Map.of(b7.id(), new LootTable(b7.id(), b7.rolls(), e7, b7.guaranteed(), b7.gold())))).warnings());
        assertTrue(w7.contains("loot.floor07_boss: 지하 7층 표인데 레벨 창 밖 장비 1종 (예: " + myth + "(단계 10))"), w7);
        assertFalse(w7.contains("floor08_boss") || w7.contains("floor09_boss"), w7);
        // 영웅·전설 무기는 보스 + 대장간이면 여전히 경고 (보스 고유 전설 무기에 레시피를 붙여 본다)
        String legend = null;
        for (ItemDef d : content.items().values()) {
            if (d.isWeapon() && d.rarity() == Rarity.LEGENDARY && d.sources().equals(List.of("boss")) && d.tier() == 10) legend = d.id();
        }
        assertNotNull(legend);
        Map<String, RecipeDef> rs = new HashMap<>(content.recipes());
        RecipeDef any = BlueprintRules.recipeFor(content, myth);
        rs.put(legend, new RecipeDef(legend, legend, "weapon", "blacksmith", any.materials(), 1000, 48, 1));
        Content c = content;
        Content lc = new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), c.lootTables(), c.lootSettings(),
                Map.copyOf(rs), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces(), c.enhance(), c.mine());
        String wl = String.join("\n", ContentValidator.validate(lc).warnings());
        assertTrue(wl.contains("items." + legend + ": 영웅 이상 무기인데 획득처 종류가 2개 (보스·대장간) — 1개여야 함"), wl);
    }

    // ── 굴림 ────────────────────────────────────────────────

    static Map<Stat, Integer> build(Stat a, Stat b) {
        Map<Stat, Integer> m = new EnumMap<>(Stat.class);
        for (Stat s : Stat.values()) m.put(s, 5);
        m.put(a, 60);
        m.put(b, 40);
        return m;
    }

    @Test
    void pickOfStaysInsideTheListWithBuildBias() {
        Map<Stat, Integer> str = build(Stat.STR, Stat.VIT);
        List<Stat> top = StatRequirement.top(str, BlueprintRules.BUILD_TOP);
        int fit = 0;
        for (String id : mythics) if (BlueprintRules.fits(content.item(id), top)) fit++;
        assertTrue(fit > 0 && fit < mythics.size(), "힘·체력 빌드에 맞는 신화 " + fit + " / " + mythics.size());
        Random rng = new Random(37);
        int n = 60_000, gotFit = 0;
        Map<String, Integer> by = new HashMap<>();
        for (int i = 0; i < n; i++) {
            String rid = BlueprintRules.pickOf(content, mythics, str, 0.65, rng);
            assertTrue(mythics.contains(rid), rid);
            by.merge(rid, 1, Integer::sum);
            if (BlueprintRules.fits(content.item(content.recipes().get(rid).result()), top)) gotFit++;
        }
        double want = 0.65 + 0.35 * fit / mythics.size();
        assertEquals(want, gotFit / (double) n, 0.01, "빌드에 맞는 몫 = 편향 + (1 − 편향) × 맞는 비율");
        for (String id : mythics) {
            double p = BlueprintRules.chanceOf(content, mythics, id, top, 0.65);
            assertEquals(p, by.getOrDefault(id, 0) / (double) n, 0.006, id);
        }
        double sum = 0;
        for (String id : mythics) sum += BlueprintRules.chanceOf(content, mythics, id, top, 0.65);
        assertEquals(1.0, sum, 1e-9);
        // 편향 없음 (stats null) = 똑같은 몫, 목록 밖·없는 id 는 뽑히지 않음
        Set<String> seen = new HashSet<>();
        List<String> withJunk = new ArrayList<>(mythics);
        withJunk.add("no_such_recipe");
        withJunk.add(openRecipe());
        for (int i = 0; i < 5000; i++) seen.add(BlueprintRules.pickOf(content, withJunk, null, 0.65, rng));
        assertEquals(new HashSet<>(mythics), seen);
        assertNull(BlueprintRules.pickOf(content, List.of("no_such_recipe"), str, 0.65, rng));
        assertEquals(0.0, BlueprintRules.chanceOf(content, mythics, "no_such_recipe", top, 0.65));
    }

    @Test
    void rollerUsesTheBlueprintChanceFormula() {
        List<String> two = mythics.subList(0, 2);
        Map<String, LootTable> m = new HashMap<>();
        m.put("t_of", new LootTable("t_of", 1, List.of(of(0.2, two)), List.of(), IntRange.ZERO));
        m.put("t_hard", new LootTable("t_hard", 1, List.of(new LootTable.Entry(LootTable.Kind.BLUEPRINT_OF, null, null, 0, two, null,
                1.0, new IntRange(2, 2), "hard")), List.of(), IntRange.ZERO));
        m.put("t_sure", new LootTable("t_sure", 1, List.of(), List.of(of(0.0, two)), IntRange.ZERO));
        Content c = withTables(content, m);
        LootRoller roller = new LootRoller(c, new Random(5));
        int n = 40_000, plain = 0, boosted = 0;
        for (int i = 0; i < n; i++) {
            for (LootRoller.Drop d : roller.roll("t_of", new LootRoller.Request("normal", 1.0, 0, null))) {
                assertEquals(BlueprintRules.ITEM_ID, d.itemId());
                assertEquals(1, d.amount());
                assertTrue(two.contains(d.recipe()), d.recipe());
                plain++;
            }
            boosted += roller.roll("t_of", new LootRoller.Request("normal", 1.5, 40, null)).size();
        }
        LootTable.Settings s = c.lootSettings();
        assertEquals(0.2, plain / (double) n, 0.008);
        assertEquals(LootRoller.effectiveChance(s, 0.2, 1.5, 40, 1.0), boosted / (double) n, 0.01, "난이도·파티 배율 × LUK, rarity_weight 없음");
        assertTrue(roller.roll("t_hard", new LootRoller.Request("normal", 1.0, 0, null)).isEmpty(), "min_difficulty");
        List<LootRoller.Drop> hard = roller.roll("t_hard", new LootRoller.Request("hard", 1.0, 0, null));
        assertEquals(1, hard.size());
        assertEquals(2, hard.get(0).amount(), "amount");
        assertEquals(1, roller.roll("t_sure", new LootRoller.Request("easy", 0.0, 0, null)).size(), "guaranteed 는 항상");
    }

    @Test
    void regularBlueprintsNeverTeachMythics() {
        for (int t = 1; t <= 10; t++) {
            for (BlueprintRules.Candidate x : BlueprintRules.candidates(content, t)) {
                assertFalse(BlueprintRules.isMythic(content, x.recipe()), t + "단계 후보에 신화 " + x.recipe().id());
            }
        }
        for (String id : mythics) assertEquals(0.0, BlueprintRules.chanceOf(content, 10, BlueprintRules.recipeFor(content, id).id()));
        Random rng = new Random(91);
        Map<Stat, Integer> str = build(Stat.STR, Stat.VIT);
        for (int i = 0; i < 100_000; i++) {
            String rid = BlueprintRules.pick(content, 9 + (i & 1), (i & 2) == 0 ? null : str, 0.65, rng);
            assertNotNull(rid);
            assertFalse(BlueprintRules.isMythic(content, content.recipes().get(rid)), rid);
        }
        // 신화 레시피는 여전히 도안이 필요하다 (gated 에는 있고 drawable 에는 없다)
        for (String id : mythics) {
            RecipeDef r = BlueprintRules.recipeFor(content, id);
            assertTrue(BlueprintRules.gated(content).contains(r));
            assertFalse(BlueprintRules.drawable(content).contains(r));
            assertFalse(BlueprintRules.canCraft(content, r, true, List.of()));
            assertTrue(BlueprintRules.canCraft(content, r, true, List.of(r.id())));
            assertFalse(BlueprintRules.shopPool(content).contains(r), "상인은 신화 도안을 팔지 않는다");
        }
        // 10층 보스 표 전체를 굴려도 일반 도안 항목에서는 신화가 나오지 않는다 (신화 도안은 blueprint_of 몫만)
        int myth = 0, bps = 0;
        Map<String, LootTable> only = new HashMap<>();
        LootTable b10 = content.lootTable("floor10_boss");
        List<LootTable.Entry> plain = new ArrayList<>();
        for (LootTable.Entry e : b10.entries()) if (e.kind() == LootTable.Kind.BLUEPRINT) plain.add(e);
        assertFalse(plain.isEmpty());
        only.put("t_b10_plain", new LootTable("t_b10_plain", 1, plain, List.of(), IntRange.ZERO));
        LootRoller pr = new LootRoller(withTables(content, only), new Random(13));
        for (int i = 0; i < 20_000; i++) {
            for (LootRoller.Drop d : pr.roll("t_b10_plain", new LootRoller.Request("nightmare", 2.0, 100, str))) {
                bps++;
                if (BlueprintRules.isMythic(content, content.recipes().get(d.recipe()))) myth++;
            }
        }
        assertTrue(bps > 1000, "일반 도안 " + bps);
        assertEquals(0, myth);
    }

    @Test
    void activeCountsBlueprintOf() {
        assertTrue(BlueprintRules.active(content));
        // blueprint 항목을 모두 빼고 blueprint_of 하나만 남겨도 켜진다
        Map<String, LootTable> only = new LinkedHashMap<>();
        only.put("t", new LootTable("t", 1, List.of(of(0.1, mythics)), List.of(), IntRange.ZERO));
        Content c = content;
        Content one = new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(only), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces(), c.enhance(), c.mine());
        assertTrue(BlueprintRules.active(one));
        Content none = new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.of(), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces(), c.enhance(), c.mine());
        assertFalse(BlueprintRules.active(none));
        assertTrue(BlueprintRules.isBlueprintEntry(of(0.1, mythics)));
    }
}
