package kr.labyrinth.items.enhance;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.EnhanceDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.ContentLoader;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비별 강화 재료 (content/enhance.yml, GDD §11.13): 번들 파일 검사 · 구간별 비용 구성 · 전부 아니면 아무것도 소모 · 읽기 경고.
 * <p>
 * 루팅 재구성으로 들어올 새 장비(다른 작업 묶음)는 이 브랜치 items.yml 에 아직 없을 수 있다 — 그런 항목은 개수만 세고 건너뛴다.
 * 재료는 반드시 지금 items.yml 에 있어야 한다.
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
        for (String w : t.warnings()) {
            assertTrue(w.startsWith("items.yml 에 없는 장비"), "재료·구간 경고가 없어야 함: " + w);
        }
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
        System.out.println("ENHANCE enhance.yml 장비 " + items.size() + "개 중 items.yml 에 아직 없는 장비 " + skipped + "개 건너뜀"
                + (skippedIds.isEmpty() ? "" : " (예: " + skippedIds.subList(0, Math.min(5, skippedIds.size())) + ")"));
        assertTrue(skipped <= 45, "items.yml 에 없는 장비가 너무 많다 (오타?): " + skippedIds);
        for (ItemDef d : content.items().values()) {
            if (EnhanceRules.enhanceable(d)) assertTrue(content.enhance().has(d.id()),
                    d.id() + " 의 강화 재료가 없다 — python3 tools/gen_enhance.py 로 다시 만들 것");
        }
    }

    @Test
    void bandsFollowTheRules() {
        Set<String> cores = new HashSet<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.MATERIAL && d.sources().equals(List.of("boss"))) cores.add(d.id());
        }
        assertEquals(10, cores.size(), "보스 핵 10종: " + cores);
        Map<String, String> seen = new HashMap<>();
        // 같은 주 재료(= 같은 층·같은 단단/부드러움) · 같은 종류 묶음별 high 단계 재료 종류 수: 일반 장비 최대 / 보스 장비 최소
        Map<String, int[]> normalKinds = new HashMap<>(), bossKinds = new HashMap<>();
        for (ItemDef d : content.items().values()) {
            if (!EnhanceRules.enhanceable(d)) continue;
            EnhanceDef t = content.enhance();
            List<EnhanceDef.Cost> low = t.costs(d.id(), 1), mid = t.costs(d.id(), 5), high = t.costs(d.id(), 10);
            assertEquals(1, low.size(), d.id() + " low = 주 재료 1종");
            assertEquals(2, mid.size(), d.id() + " mid = 주 재료 + 보조");
            assertEquals(3, high.size(), d.id() + " high = 주 재료 + 보조 + 희귀/보스 핵");
            assertEquals(low.get(0).item(), mid.get(0).item(), d.id() + " mid 는 low 재료를 이어 쓴다");
            assertEquals(mid.get(0).item(), high.get(0).item(), d.id());
            assertEquals(mid.get(1).item(), high.get(1).item(), d.id() + " high 는 mid 보조를 이어 쓴다");
            // 단계 안에서 개수는 줄지 않는다 — 보스 장비의 희귀 재료가 보스 핵으로 바뀌는 단계(+9)만 예외
            for (int tg = 2; tg <= 10; tg++) {
                if (t.band(tg) != t.band(tg - 1)) continue;
                Map<String, Integer> a = asMap(t.costs(d.id(), tg - 1)), b = asMap(t.costs(d.id(), tg));
                boolean coreArrives = a.keySet().stream().noneMatch(cores::contains) && b.keySet().stream().anyMatch(cores::contains);
                for (var e : a.entrySet()) {
                    if (coreArrives && !b.containsKey(e.getKey())) continue;
                    assertTrue(b.getOrDefault(e.getKey(), 0) >= e.getValue(), d.id() + " +" + tg + " " + e.getKey());
                }
            }
            // 보스 고유 장비 = high 에 보스 핵. 보스가 주지 않는 장비는 보스 핵을 쓰지 않는다.
            // (루팅 재구성 전 items.yml 은 보스 장비가 정예에서도 나와 sources 가 넓다 — 그래서 한쪽씩만 본다)
            boolean bossOnly = d.sources().contains("boss") && !d.sources().contains("drop") && !d.sources().contains("chest")
                    && !d.sources().contains("elite");
            boolean usesCore = high.stream().anyMatch(c -> cores.contains(c.item()));
            if (bossOnly) assertTrue(usesCore, d.id() + " 은 보스 고유 장비인데 high 에 보스 핵이 없다");
            if (usesCore) assertTrue(d.sources().contains("boss"), d.id() + " 은 보스가 주지 않는데 보스 핵을 쓴다 " + d.sources());
            for (int tg = 1; tg <= 6; tg++) {
                for (EnhanceDef.Cost c : t.costs(d.id(), tg)) assertFalse(cores.contains(c.item()), d.id() + " +" + tg + " 에 보스 핵");
            }
            String kind = d.isWeapon() ? d.weaponType() : d.armorSlot();
            int[] kinds = (usesCore ? bossKinds : normalKinds).computeIfAbsent(low.get(0).item() + "|" + kind,
                    k -> new int[] {usesCore ? 99 : 0, usesCore ? 99 : 0, usesCore ? 99 : 0, usesCore ? 99 : 0});
            for (int tg = 7; tg <= 10; tg++) {
                int n = t.costs(d.id(), tg).size();
                kinds[tg - 7] = usesCore ? Math.min(kinds[tg - 7], n) : Math.max(kinds[tg - 7], n);
            }
            // 같은 층 재료 · 같은 종류 안에서 구성이 겹치지 않는다
            String key = low.get(0).item() + "|" + kind + "|" + recipe(t, d.id());
            String other = seen.put(key, d.id());
            assertNull(other, d.id() + " 와 " + other + " 의 강화 재료 구성이 똑같다 (같은 종류)");
        }
        // 보스 고유 장비가 같은 층·같은 종류 일반 장비보다 싼 high 단계가 없다 (+7·+8 은 희귀 재료, +9·+10 은 보스 핵 — 언제나 3종)
        int compared = 0;
        for (var e : bossKinds.entrySet()) {
            int[] normal = normalKinds.get(e.getKey());
            if (normal == null) continue;
            compared++;
            for (int k = 0; k < 4; k++) {
                assertTrue(e.getValue()[k] >= normal[k], e.getKey() + " +" + (k + 7) + ": 보스 장비 재료 " + e.getValue()[k]
                        + "종 < 일반 장비 " + normal[k] + "종");
            }
        }
        assertTrue(compared > 0, "비교할 보스 장비 묶음이 없다");
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
