package kr.labyrinth.items.loot;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.random.RandomGenerator;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.stats.Stat;

/**
 * loot.yml 테이블 굴림 — 순수 로직 (GDD §11.10, 단위 테스트 대상).
 * <ul>
 *   <li>rolls 번 굴림. 한 번 굴릴 때 entries 각 항목이 독립적으로 자기 확률 판정(여러 개 동시 가능). guaranteed 는 항상 1번.</li>
 *   <li>최종 확률 = min(max_chance, chance × dropMultiplier × (1 + LUK × luck_per_point) × rarity_weight[난이도][희귀도]).
 *       chance ≥ 1 항목은 배율 무관. rarity_weight 는 장비 항목(장비 item · rarity_pool · one_of)에만, one_of 는 후보 최고 희귀도.</li>
 *   <li>PICK (0.3.5): chance 를 넘으면 무게대로 하위 테이블 하나를 골라 통째로 굴린다 (장비 항목이 아니라 rarity_weight 없음).</li>
 *   <li>빌드 편향 own_build_bias (0.3.5): rarity_pool·one_of 로 장비를 고를 때 그 확률로 '요구치 1위 능력치가 줍는 사람
 *       능력치(기본 + 분배 + 칭호) 상위 2개 안' 인 후보만 (없으면 전체). items.yml classes 는 보지 않는다.</li>
 *   <li>min_difficulty 미만 난이도면 그 항목은 판정하지 않는다. table·pick 항목은 하위 테이블을 굴린다(깊이 제한 6).</li>
 * </ul>
 */
public final class LootRoller {

    /** 굴림 결과 한 줄. */
    public record Drop(String itemId, int amount) {}

    /**
     * @param difficultyId   서버/인스턴스 난이도 id
     * @param dropMultiplier 난이도 drop × 파티 보상 배율 (InstanceContext.dropMultiplier)
     * @param luck           루팅한 사람 LUK
     * @param stats          루팅한 사람 요구치 판정 능력치 (직업 기본 + 분배 + 칭호 — StatService.requirementStats, null = 편향 없음)
     */
    public record Request(String difficultyId, double dropMultiplier, int luck, Map<Stat, Integer> stats) {}

    private static final int MAX_DEPTH = 6;
    /** 빌드 편향이 보는 줍는 사람 능력치 개수. */
    public static final int BUILD_TOP = 2;

    private final Content content;
    private final RandomGenerator rng;

    public LootRoller(Content content, RandomGenerator rng) {
        this.content = content;
        this.rng = rng;
    }

    /** 최종 확률 (GDD §11.10). */
    public static double effectiveChance(LootTable.Settings s, double chance, double dropMultiplier, int luck,
                                         double rarityWeight) {
        if (chance >= 1.0) return 1.0;
        if (chance <= 0) return 0;
        double v = chance * Math.max(0, dropMultiplier) * (1.0 + Math.max(0, luck) * s.luckPerPoint()) * rarityWeight;
        return Math.max(0, Math.min(s.maxChance(), Math.min(1.0, v)));
    }

    public List<Drop> roll(String tableId, Request req) {
        List<Drop> out = new ArrayList<>();
        LootTable t = content.lootTable(tableId);
        if (t != null) roll(t, req, out, 0);
        return out;
    }

    private void roll(LootTable t, Request req, List<Drop> out, int depth) {
        if (depth > MAX_DEPTH) return;
        for (LootTable.Entry g : t.guaranteed()) resolve(g, req, out, depth, true);
        int rolls = Math.max(1, t.rolls());
        for (int i = 0; i < rolls; i++) {
            for (LootTable.Entry e : t.entries()) resolve(e, req, out, depth, false);
        }
    }

    private void resolve(LootTable.Entry e, Request req, List<Drop> out, int depth, boolean guaranteed) {
        if (e.minDifficulty() != null && Difficulty.rank(req.difficultyId()) < Difficulty.rank(e.minDifficulty())) return;
        LootTable.Settings s = content.lootSettings();
        switch (e.kind()) {
            case ITEM -> {
                ItemDef def = content.item(e.item());
                if (def == null) return;
                double w = def.isGear() ? s.rarityWeight(req.difficultyId(), def.rarity()) : 1.0;
                if (guaranteed || pass(s, e.chance(), req, w)) out.add(new Drop(def.id(), amount(e)));
            }
            case RARITY_POOL -> {
                List<ItemDef> cands = content.poolCandidates(e.floor(), e.rarityPool());
                if (cands.isEmpty()) return;
                double w = s.rarityWeight(req.difficultyId(), e.rarityPool());
                if (guaranteed || pass(s, e.chance(), req, w)) {
                    ItemDef pick = pick(cands, req.stats(), s.ownBuildBias());
                    if (pick != null) out.add(new Drop(pick.id(), amount(e)));
                }
            }
            case ONE_OF -> {
                List<ItemDef> cands = new ArrayList<>();
                Rarity best = null;
                for (String id : e.oneOf()) {
                    ItemDef d = content.item(id);
                    if (d == null) continue;
                    cands.add(d);
                    if (best == null || d.rarity().ordinal() > best.ordinal()) best = d.rarity();
                }
                if (cands.isEmpty()) return;
                boolean gear = cands.stream().anyMatch(ItemDef::isGear);
                double w = gear ? s.rarityWeight(req.difficultyId(), best) : 1.0;
                if (guaranteed || pass(s, e.chance(), req, w)) {
                    ItemDef pick = gear ? pick(cands, req.stats(), s.ownBuildBias()) : cands.get(rng.nextInt(cands.size()));
                    if (pick != null) out.add(new Drop(pick.id(), amount(e)));
                }
            }
            case TABLE -> {
                LootTable sub = content.lootTable(e.table());
                if (sub == null) return;
                if (guaranteed || pass(s, e.chance(), req, 1.0)) roll(sub, req, out, depth + 1);
            }
            case PICK -> {
                if (!guaranteed && !pass(s, e.chance(), req, 1.0)) return;
                LootTable sub = content.lootTable(choose(e.pick()));
                if (sub != null) roll(sub, req, out, depth + 1);
            }
        }
    }

    /** 무게대로 하위 테이블 하나 (무게 0 이하는 빼고, 모두 0 이면 null). */
    String choose(List<LootTable.Pick> picks) {
        int total = 0;
        for (LootTable.Pick p : picks) total += Math.max(0, p.weight());
        if (total <= 0) return null;
        int r = rng.nextInt(total);
        for (LootTable.Pick p : picks) {
            int w = Math.max(0, p.weight());
            if (r < w) return p.table();
            r -= w;
        }
        return null;
    }

    private boolean pass(LootTable.Settings s, double chance, Request req, double rarityWeight) {
        double p = effectiveChance(s, chance, req.dropMultiplier(), req.luck(), rarityWeight);
        return p >= 1.0 || rng.nextDouble() < p;
    }

    private int amount(LootTable.Entry e) {
        return e.amount() == null ? 1 : Math.max(1, e.amount().roll(rng));
    }

    /** 그 후보가 줍는 사람 빌드에 맞는가: 요구치 1위 능력치가 줍는 사람 능력치 상위 {@value #BUILD_TOP}개 안. */
    public static boolean fitsBuild(ItemDef d, List<Stat> top) {
        Stat primary = d.requirement().primary();
        return primary != null && top.contains(primary);
    }

    /** 빌드 편향 선택 (bias 확률로 줍는 사람 빌드에 맞는 후보만, 없으면 전체). 착용 제한은 없다. */
    ItemDef pick(List<ItemDef> cands, Map<Stat, Integer> stats, double bias) {
        if (cands.isEmpty()) return null;
        List<ItemDef> pool = cands;
        if (rng.nextDouble() < bias) {
            List<Stat> top = StatRequirement.top(stats, BUILD_TOP);
            List<ItemDef> own = new ArrayList<>();
            if (!top.isEmpty()) for (ItemDef d : cands) if (fitsBuild(d, top)) own.add(d);
            if (!own.isEmpty()) pool = own;
        }
        return pool.get(rng.nextInt(pool.size()));
    }
}
