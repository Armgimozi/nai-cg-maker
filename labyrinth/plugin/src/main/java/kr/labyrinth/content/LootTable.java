package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/** loot.yml 테이블. 해석 = GDD §11.10. */
public record LootTable(String id, int rolls, List<Entry> entries, List<Entry> guaranteed, IntRange gold) {

    public enum Kind { ITEM, RARITY_POOL, ONE_OF, TABLE }

    /**
     * 항목. kind 에 따라 item / rarityPool(+floor) / oneOf / table 중 하나가 채워진다.
     * amount 기본 [1,1], chance 기본 1.0, minDifficulty 는 null 가능.
     */
    public record Entry(Kind kind, String item, Rarity rarityPool, int floor, List<String> oneOf, String table,
                        double chance, IntRange amount, String minDifficulty) {}

    /** loot.yml settings. rarityWeight: 난이도 → (희귀도 id → 배율). */
    public record Settings(double ownClassBias, double luckPerPoint, double partyBonusPerMember, double maxChance,
                           Map<String, Map<String, Double>> rarityWeight, Rarity announceRarity) {

        public static final Settings DEFAULT = new Settings(0.65, 0.005, 0.05, 1.0, Map.of(), Rarity.LEGENDARY);

        public double rarityWeight(String difficulty, Rarity rarity) {
            Map<String, Double> m = rarityWeight.get(difficulty);
            if (m == null || rarity == null) return 1.0;
            return m.getOrDefault(rarity.id(), 1.0);
        }
    }
}
