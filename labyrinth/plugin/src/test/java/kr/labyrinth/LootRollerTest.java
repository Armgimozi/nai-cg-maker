package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 루팅 확률 공식·독립 판정·확정 지급·min_difficulty·빌드 편향(own_build_bias)·PICK (GDD §11.10, gear_spec §4.2)
 * · 장비 획득처 검사기 경고. (gear_spec §12 의 PickEntryTest 가 여기 있다.)
 */
class LootRollerTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    private static LootRoller.Request normal() { return new LootRoller.Request("normal", 1.0, 0, null); }

    @Test
    void effectiveChanceFormula() {
        LootTable.Settings s = new LootTable.Settings(0.65, 0.005, 0.05, 1.0, java.util.Map.of(), Rarity.LEGENDARY);
        assertEquals(0.1 * 1.3 * 1.05 * 1.2, LootRoller.effectiveChance(s, 0.1, 1.3, 10, 1.2), 1e-12);
        assertEquals(1.0, LootRoller.effectiveChance(s, 1.0, 0.5, 0, 0.5), 1e-12, "chance 1.0 은 배율 무관");
        assertEquals(1.0, LootRoller.effectiveChance(s, 0.9, 3.0, 100, 1.0), 1e-12, "1 을 넘지 않음");
        assertEquals(0.0, LootRoller.effectiveChance(s, 0.0, 3.0, 100, 1.0), 1e-12);
        LootTable.Settings capped = new LootTable.Settings(0.65, 0.005, 0.05, 0.5, java.util.Map.of(), Rarity.LEGENDARY);
        assertEquals(0.5, LootRoller.effectiveChance(capped, 0.4, 2.0, 0, 1.0), 1e-12, "max_chance 상한");
    }

    @Test
    void independentEntryFrequencies() {
        LootTable t = content.lootTable("potions_t1");
        LootRoller roller = new LootRoller(content, new Random(7));
        int n = 20000, heal = 0, mana = 0, both = 0;
        for (int i = 0; i < n; i++) {
            List<LootRoller.Drop> d = roller.roll(t.id(), normal());
            boolean h = d.stream().anyMatch(x -> x.itemId().equals("minor_healing_potion"));
            boolean m = d.stream().anyMatch(x -> x.itemId().equals("minor_mana_potion"));
            if (h) heal++;
            if (m) mana++;
            if (h && m) both++;
        }
        assertEquals(0.65, heal / (double) n, 0.02);
        assertEquals(0.5, mana / (double) n, 0.02);
        assertEquals(0.65 * 0.5, both / (double) n, 0.02, "항목은 서로 독립 판정");
    }

    @Test
    void dropMultiplierRaisesFrequency() {
        LootRoller roller = new LootRoller(content, new Random(11));
        int n = 20000, base = 0, boosted = 0;
        for (int i = 0; i < n; i++) {
            if (!roller.roll("potions_t1", normal()).isEmpty()) base++;
        }
        for (int i = 0; i < n; i++) {
            if (roller.roll("potions_t1", new LootRoller.Request("normal", 1.0, 200, null)).stream()
                    .anyMatch(x -> x.itemId().equals("minor_mana_potion"))) boosted++;
        }
        // LUK 200 → ×2 → 0.5 → 1.0
        assertEquals(n, boosted);
        assertTrue(base < n);
    }

    @Test
    void guaranteedAlwaysDrops() {
        LootRoller roller = new LootRoller(content, new Random(3));
        for (int i = 0; i < 500; i++) {
            List<LootRoller.Drop> d = roller.roll("floor01_boss", new LootRoller.Request("easy", 0.01, 0, null));
            assertTrue(d.stream().anyMatch(x -> x.itemId().equals("warden_heartwood")));
            LootRoller.Drop moss = d.stream().filter(x -> x.itemId().equals("moss_fiber")).findFirst().orElseThrow();
            // 0.3.6 몹 주제 드롭 (drops_spec): 1층 보스 이끼 섬유 [6,9]
            assertTrue(moss.amount() >= 6 && moss.amount() <= 9, "amount [6,9]: " + moss.amount());
        }
    }

    @Test
    void minDifficultyGatesMythic() {
        LootRoller roller = new LootRoller(content, new Random(5));
        for (int i = 0; i < 4000; i++) {
            for (LootRoller.Drop d : roller.roll("floor10_boss", new LootRoller.Request("normal", 50.0, 0, null))) {
                ItemDef def = content.item(d.itemId());
                assertFalse(def.rarity() == Rarity.MYTHIC, "보통 난이도에서 신화가 나오면 안 됨: " + d.itemId());
            }
        }
        boolean mythic = false;
        for (int i = 0; i < 400 && !mythic; i++) {
            for (LootRoller.Drop d : roller.roll("floor10_boss", new LootRoller.Request("hard", 50.0, 0, null))) {
                if (content.item(d.itemId()).rarity() == Rarity.MYTHIC) mythic = true;
            }
        }
        assertTrue(mythic, "어려움 + 큰 배율이면 신화가 나와야 함");
    }

    @Test
    void buildBiasPrefersOwnBuild() {
        // 1단계 몬스터·상자 풀(band_t01_drop, one_of chance 1.0): 힘·체력 빌드가 주우면 요구치 1위가 힘·체력인 무기 비율이
        // 0.65 + 0.35 × (맞는 수 / 전체) — items.yml classes 는 보지 않는다
        LootTable t = content.lootTable("band_t01_drop");
        List<String> pool = t.entries().get(0).oneOf();
        Map<Stat, Integer> build = Map.of(Stat.STR, 30, Stat.VIT, 20, Stat.DEX, 5);
        List<Stat> top = StatRequirement.top(build, 2);
        assertEquals(List.of(Stat.STR, Stat.VIT), top);
        long fit = pool.stream().filter(id -> LootRoller.fitsBuild(content.item(id), top)).count();
        assertTrue(fit > 0 && fit < pool.size(), "맞는 무기 " + fit + " / " + pool.size());
        LootRoller roller = new LootRoller(content, new Random(9));
        int n = 20000, own = 0;
        for (int i = 0; i < n; i++) {
            for (LootRoller.Drop d : roller.roll(t.id(), new LootRoller.Request("normal", 1.0, 0, build))) {
                if (LootRoller.fitsBuild(content.item(d.itemId()), top)) own++;
            }
        }
        double want = 0.65 + 0.35 * fit / pool.size();
        assertEquals(want, own / (double) n, 0.02, "빌드 편향 비율");
        // 능력치를 모르면 편향 없음
        int plain = 0;
        for (int i = 0; i < n; i++) {
            for (LootRoller.Drop d : roller.roll(t.id(), normal())) if (LootRoller.fitsBuild(content.item(d.itemId()), top)) plain++;
        }
        assertEquals(fit / (double) pool.size(), plain / (double) n, 0.02);
        // 요구 없는 장비(Lv1)는 어느 빌드에도 '맞는' 쪽이 아니다
        assertFalse(LootRoller.fitsBuild(content.item("corridor_longsword"), top));
    }

    // ── PICK (gear_spec §4.2 · §12 PickEntryTest) ───────────────────────────

    private static Content withTables(Map<String, LootTable> extra) {
        Map<String, LootTable> tables = new HashMap<>(content.lootTables());
        tables.putAll(extra);
        Content c = content;
        return new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(tables), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
    }

    private static LootTable single(String id, String item) {
        return new LootTable(id, 1, List.of(new LootTable.Entry(LootTable.Kind.ITEM, item, null, 0, List.of(), null, 1.0, IntRange.ONE, null)),
                List.of(), IntRange.ZERO);
    }

    private static LootTable.Entry pick(double chance, Object... tw) {
        List<LootTable.Pick> p = new ArrayList<>();
        for (int i = 0; i < tw.length; i += 2) p.add(new LootTable.Pick((String) tw[i], (Integer) tw[i + 1]));
        return new LootTable.Entry(LootTable.Kind.PICK, null, null, 0, List.of(), null, chance, IntRange.ONE, null, p);
    }

    private static Map<String, LootTable> abc(LootTable.Entry entry, boolean guaranteed) {
        Map<String, LootTable> m = new HashMap<>();
        m.put("t_a", single("t_a", "minor_healing_potion"));
        m.put("t_b", single("t_b", "minor_mana_potion"));
        m.put("t_c", single("t_c", "return_scroll"));
        m.put("t_pick", new LootTable("t_pick", 1, guaranteed ? List.of() : List.of(entry), guaranteed ? List.of(entry) : List.of(),
                IntRange.ZERO));
        return m;
    }

    @Test
    void pickFollowsWeights() {
        Content c = withTables(abc(pick(1.0, "t_a", 7, "t_b", 2, "t_c", 1), false));
        LootRoller roller = new LootRoller(c, new Random(21));
        Map<String, Integer> got = new HashMap<>();
        int n = 10000;
        for (int i = 0; i < n; i++) {
            List<LootRoller.Drop> d = roller.roll("t_pick", normal());
            assertEquals(1, d.size(), "PICK 은 하위 표 하나만");
            got.merge(d.get(0).itemId(), 1, Integer::sum);
        }
        assertEquals(0.7, got.getOrDefault("minor_healing_potion", 0) / (double) n, 0.02);
        assertEquals(0.2, got.getOrDefault("minor_mana_potion", 0) / (double) n, 0.02);
        assertEquals(0.1, got.getOrDefault("return_scroll", 0) / (double) n, 0.02);
    }

    @Test
    void pickChanceZeroNeverAndGuaranteedAlways() {
        LootRoller never = new LootRoller(withTables(abc(pick(0.0, "t_a", 1, "t_b", 1), false)), new Random(4));
        for (int i = 0; i < 2000; i++) assertTrue(never.roll("t_pick", normal()).isEmpty());
        LootRoller always = new LootRoller(withTables(abc(pick(0.0, "t_a", 1, "t_b", 1), true)), new Random(4));
        for (int i = 0; i < 2000; i++) assertEquals(1, always.roll("t_pick", new LootRoller.Request("easy", 0.0, 0, null)).size());
        // 무게 0 인 표는 뽑히지 않는다
        LootRoller zero = new LootRoller(withTables(abc(pick(1.0, "t_a", 0, "t_b", 3), false)), new Random(8));
        for (int i = 0; i < 2000; i++) assertEquals("minor_mana_potion", zero.roll("t_pick", normal()).get(0).itemId());
    }

    @Test
    void validatorChecksPick() {
        Map<String, LootTable> m = abc(pick(1.0, "t_a", 1, "t_missing", 1, "t_b", 0), false);
        m.put("t_loop", new LootTable("t_loop", 1, List.of(pick(1.0, "t_loop2", 1)), List.of(), IntRange.ZERO));
        m.put("t_loop2", new LootTable("t_loop2", 1, List.of(pick(1.0, "t_loop", 1)), List.of(), IntRange.ZERO));
        String errors = String.join("\n", ContentValidator.validate(withTables(m)).errors());
        assertTrue(errors.contains("loot.t_pick.pick: 없는 루팅 테이블 't_missing'"), errors);
        assertTrue(errors.contains("weight 는 1 이상: t_b 0"), errors);
        assertTrue(errors.contains("loot.t_loop: table 참조가 순환함"), errors);
        // 번들 데이터의 PICK 은 모두 올바르다
        assertTrue(ContentValidator.validate(content).errors().stream().noneMatch(e -> e.contains(".pick")),
                ContentValidator.validate(content).errors().toString());
        long picks = content.lootTables().values().stream()
                .flatMap(t -> java.util.stream.Stream.concat(t.entries().stream(), t.guaranteed().stream()))
                .filter(e -> e.kind() == LootTable.Kind.PICK).count();
        assertEquals(50, picks, "PICK 항목 (층마다 mix · 시련방 · 정예 · 금고 · 특별 시련)");
    }

    @Test
    void validatorWarnsWhenGearHomesGetMixed() {
        // 지금 콘텐츠: 장비 획득처 경고 0
        List<String> now = ContentValidator.validate(content).warnings().stream()
                .filter(x -> x.contains("rarity_pool") || x.contains("장비") || x.contains("획득처") || x.contains("sources")).toList();
        assertEquals(List.of(), now);

        Map<String, LootTable> tables = new HashMap<>(content.lootTables());
        // (a) rarity_pool · (b) 1층 몹이 3단계 무기(레벨 창 밖 — 1층은 단계 1·2) · (c) 1단계 정예 방패가 보스에서도(종류 3개)
        // · (d) 수련생 장비가 몹에서
        tables.put("moss_crawler", with(tables.get("moss_crawler"),
                new LootTable.Entry(LootTable.Kind.RARITY_POOL, null, Rarity.COMMON, 1, List.of(), null, 0.01, IntRange.ONE, null),
                item("capsplitter_cleaver"), item("minewarden_mace"), item("novice_cap")));
        tables.put("floor01_boss", with(tables.get("floor01_boss"), item("oak_round_shield")));
        Content c = content;
        Content mixed = new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(tables), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
        List<String> w = ContentValidator.validate(mixed).warnings();
        String all = String.join("\n", w);
        assertTrue(all.contains("loot.moss_crawler: rarity_pool 항목 1개"), all);
        assertTrue(all.contains("loot.moss_crawler: 지하 1층 표인데 레벨 창 밖 장비 1종") && all.contains("capsplitter_cleaver(단계 3)"), all);
        assertFalse(all.contains("minewarden_mace(단계 2)"), "이웃 단계는 레벨 창 안");
        assertTrue(all.contains("items.oak_round_shield: 획득처 종류가 3개 (정예·보스·대장간)"), all);
        assertTrue(all.contains("items.oak_round_shield: sources [elite, craft] 가 실제 획득처 [boss, craft, elite] 와 다름"), all);
        assertTrue(all.contains("items.novice_cap: 시작 지급 장비인데 몬스터·상자에서도 나옴"), all);

        // (e) 일반 몹 drops 를 보스 표로 — 한 표를 몹·보스가 같이 쓰면 두 집이 모두 잡힌다 (나중에 묶은 보스만 남지 않게)
        Map<String, MobDef> mobs = new HashMap<>(c.mobs());
        MobDef m = mobs.get("capcap");
        mobs.put("capcap", new MobDef(m.id(), m.name(), m.description(), m.floor(), m.rank(), m.base(), m.scale(), m.hp(), m.damage(),
                m.defense(), m.speed(), m.xp(), m.gold(), m.ai(), m.skills(), "floor03_boss", m.flying(), m.sounds(), m.model(), m.raw()));
        Content shared = new Content(c.classes(), c.items(), c.sets(), Map.copyOf(mobs), c.bosses(), c.floors(), c.lootTables(), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
        String sw = String.join("\n", ContentValidator.validate(shared).warnings());
        assertTrue(sw.contains("items.mycelking_spore_crown: 획득처 종류가 3개 (몬스터·상자·보스·대장간)"), sw);
        assertTrue(sw.contains("items.mycelking_spore_crown: sources [boss, craft] 가 실제 획득처 [boss, craft, drop] 와 다름"), sw);
        assertTrue(sw.contains("items.mycelking_guard_blade: sources [boss] 가 실제 획득처 [boss, drop] 와 다름"), sw);
        assertTrue(sw.contains("items.mycelking_guard_blade: 영웅 이상 무기인데 획득처 종류가 2개 (몬스터·상자·보스)"), sw);
    }

    private static LootTable.Entry item(String id) {
        return new LootTable.Entry(LootTable.Kind.ITEM, id, null, 0, List.of(), null, 0.01, IntRange.ONE, null);
    }

    private static LootTable with(LootTable t, LootTable.Entry... extra) {
        List<LootTable.Entry> entries = new ArrayList<>(t.entries());
        entries.addAll(List.of(extra));
        return new LootTable(t.id(), t.rolls(), entries, t.guaranteed(), t.gold());
    }

    @Test
    void unknownTableIsEmpty() {
        assertTrue(new LootRoller(content, new Random(1)).roll("no_such_table", normal()).isEmpty());
    }
}
