package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/** loot.yml 테이블. 해석 = GDD §11.10. */
public record LootTable(String id, int rolls, List<Entry> entries, List<Entry> guaranteed, IntRange gold) {

    /**
     * 항목 종류. PICK (0.3.5, gear_spec §4.2) = chance 를 넘으면 하위 테이블 중 하나를 무게대로 골라 굴린다 —
     * 층마다 이웃 단계 풀(band_tNN_*)을 2 : 7 : 1 로 섞을 때 쓴다.
     * BLUEPRINT (0.3.6 Q6) = {@code {blueprint: 단계, chance}} — 도안이 필요한 레시피(희귀 이상 장비) 중 하나의 도안.
     * 단계 = {@link Entry#floor()}, 이웃 단계를 장비 풀처럼 2 : 7 : 1 로 섞는다 (items/blueprint/BlueprintRules).
     */
    public enum Kind { ITEM, RARITY_POOL, ONE_OF, TABLE, PICK, BLUEPRINT }

    /** PICK 의 하위 테이블 하나 (weight 기본 1). */
    public record Pick(String table, int weight) {}

    /**
     * 항목. kind 에 따라 item / rarityPool(+floor) / oneOf / table / pick 중 하나가 채워진다.
     * amount 기본 [1,1], chance 기본 1.0, minDifficulty 는 null 가능.
     */
    public record Entry(Kind kind, String item, Rarity rarityPool, int floor, List<String> oneOf, String table,
                        double chance, IntRange amount, String minDifficulty, List<Pick> pick) {

        public Entry {
            pick = pick == null ? List.of() : List.copyOf(pick);
        }

        /** PICK 이 없는 항목 (0.3.4 까지의 꼴). */
        public Entry(Kind kind, String item, Rarity rarityPool, int floor, List<String> oneOf, String table,
                     double chance, IntRange amount, String minDifficulty) {
            this(kind, item, rarityPool, floor, oneOf, table, chance, amount, minDifficulty, List.of());
        }

        /** PICK 무게 합 (0 이하 무게는 빼고). */
        public int pickWeight() {
            int w = 0;
            for (Pick p : pick) w += Math.max(0, p.weight());
            return w;
        }
    }

    /**
     * loot.yml settings. rarityWeight: 난이도 → (희귀도 id → 배율).
     * ownBuildBias (0.3.5): 장비를 one_of 로 고를 때 이 확률로 '요구치 1위 능력치가 줍는 사람 능력치 상위 2개 안' 인 후보만
     * (예전 own_class_bias 는 같은 값으로 읽는다).
     */
    public record Settings(double ownBuildBias, double luckPerPoint, double partyBonusPerMember, double maxChance,
                           Map<String, Map<String, Double>> rarityWeight, Rarity announceRarity) {

        public static final Settings DEFAULT = new Settings(0.65, 0.005, 0.05, 1.0, Map.of(), Rarity.LEGENDARY);

        public double rarityWeight(String difficulty, Rarity rarity) {
            Map<String, Double> m = rarityWeight.get(difficulty);
            if (m == null || rarity == null) return 1.0;
            return m.getOrDefault(rarity.id(), 1.0);
        }
    }
}
