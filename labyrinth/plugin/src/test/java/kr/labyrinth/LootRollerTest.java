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
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.loot.LootRoller;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 루팅 확률 공식·독립 판정·확정 지급·min_difficulty·직업 편향 (GDD §11.10) · 장비 획득처 검사기 경고. */
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
            List<LootRoller.Drop> d = roller.roll("floor01_boss", new LootRoller.Request("easy", 0.01, 0, "guardian"));
            assertTrue(d.stream().anyMatch(x -> x.itemId().equals("warden_heartwood")));
            LootRoller.Drop moss = d.stream().filter(x -> x.itemId().equals("moss_fiber")).findFirst().orElseThrow();
            assertTrue(moss.amount() >= 4 && moss.amount() <= 6, "amount [4,6]: " + moss.amount());
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
    void classBiasPrefersOwnClass() {
        // 1층 공용 무기 묶음(gear_f01_common 의 one_of, 6종 × 2단계): 광전사에 어울리는 무기(대검) 비율이 1/6 보다 훨씬 높아야 함
        LootRoller roller = new LootRoller(content, new Random(9));
        int weapons = 0;
        int own = 0;
        for (int i = 0; i < 3000; i++) {
            for (LootRoller.Drop d : roller.roll("gear_f01_common", new LootRoller.Request("normal", 100.0, 0, "berserker"))) {
                ItemDef def = content.item(d.itemId());
                if (def.isWeapon()) {
                    weapons++;
                    if (def.suitedFor("berserker")) own++;
                }
            }
        }
        double ratio = own / (double) weapons;
        // 기대값 ≈ 0.65 + 0.35 × (2/12) ≈ 0.71
        assertTrue(ratio > 0.55 && ratio < 0.9, "직업 편향 비율 " + ratio);
    }

    @Test
    void validatorWarnsWhenGearHomesGetMixed() {
        // 지금 콘텐츠: 장비 획득처 경고 0
        List<String> now = ContentValidator.validate(content).warnings().stream()
                .filter(x -> x.contains("rarity_pool") || x.contains("장비") || x.contains("획득처") || x.contains("sources")).toList();
        assertEquals(List.of(), now);

        Map<String, LootTable> tables = new HashMap<>(content.lootTables());
        // (a) rarity_pool · (b) 1층 몹이 2층 무기 · (c) 1층 정예 방패가 보스에서도(3곳) · (d) 수련생 장비가 몹에서
        tables.put("moss_crawler", with(tables.get("moss_crawler"),
                new LootTable.Entry(LootTable.Kind.RARITY_POOL, null, Rarity.COMMON, 1, List.of(), null, 0.01, IntRange.ONE, null),
                item("minewarden_mace"), item("novice_cap")));
        tables.put("floor01_boss", with(tables.get("floor01_boss"), item("oak_round_shield")));
        Content c = content;
        Content mixed = new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(tables), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
        List<String> w = ContentValidator.validate(mixed).warnings();
        String all = String.join("\n", w);
        assertTrue(all.contains("loot.moss_crawler: rarity_pool 항목 1개"), all);
        assertTrue(all.contains("loot.moss_crawler: 지하 1층 표인데 다른 층 장비") && all.contains("minewarden_mace(2층)"), all);
        assertTrue(all.contains("items.oak_round_shield: 획득처가 3곳 (정예·보스·제작)"), all);
        assertTrue(all.contains("items.oak_round_shield: sources [elite, craft] 가 실제 획득처 [boss, craft, elite] 와 다름"), all);
        assertTrue(all.contains("items.novice_cap: 시작 지급 장비인데 몬스터·상자에서도 나옴"), all);
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
