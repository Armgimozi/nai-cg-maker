package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Random;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.loot.LootRoller;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 루팅 확률 공식·독립 판정·확정 지급·min_difficulty·직업 편향 (GDD §11.10). */
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
        // one_of 묶음 + rarity_pool: 6종 무기 중 광전사 추천 무기(대검) 비율이 1/6 보다 훨씬 높아야 함
        LootRoller roller = new LootRoller(content, new Random(9));
        int weapons = 0;
        int own = 0;
        for (int i = 0; i < 3000; i++) {
            for (LootRoller.Drop d : roller.roll("floor01_boss", new LootRoller.Request("normal", 100.0, 0, "berserker"))) {
                ItemDef def = content.item(d.itemId());
                if (def.isWeapon()) {
                    weapons++;
                    if (def.suitedFor("berserker")) own++;
                }
            }
        }
        double ratio = own / (double) weapons;
        // 기대값 ≈ 0.65 + 0.35 × (1/6) ≈ 0.71 (풀 후보 구성에 따라 약간 다름)
        assertTrue(ratio > 0.55 && ratio < 0.9, "직업 편향 비율 " + ratio);
    }

    @Test
    void unknownTableIsEmpty() {
        assertTrue(new LootRoller(content, new Random(1)).roll("no_such_table", normal()).isEmpty());
    }
}
