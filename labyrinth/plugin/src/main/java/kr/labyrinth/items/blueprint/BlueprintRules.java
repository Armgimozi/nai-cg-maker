package kr.labyrinth.items.blueprint;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import java.util.random.RandomGenerator;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.stats.Stat;

/**
 * 도안 규칙 — 순수 로직 (0.3.6 Q6, 단위 테스트 대상).
 * <ul>
 *   <li>희귀 이상 장비(무기·방어구·방패·장신구) 레시피는 도안을 배워야 만든다. 일반·고급 장비와 재료 레시피는 처음부터 안다.</li>
 *   <li>루팅 {@code {blueprint: 단계, chance}}: 도안이 필요한 레시피 중 하나. 레시피마다 무게 = 결과 장비 단계가
 *       그 단계보다 하나 아래 2 · 같음 7 · 하나 위 1 (장비 단계 풀과 같은 몫). 그 밖의 단계는 나오지 않는다.</li>
 *   <li>빌드 편향 (loot.yml own_build_bias): 그 확률로 '요구치 1위 능력치가 줍는 사람 능력치 상위 2개 안' 인 장비의 도안만.
 *       요구치가 없는 장비(장신구)는 누구에게나 맞는 것으로 친다.</li>
 *   <li>상인 핀: 날마다 바뀌는 희귀 도안 몇 개 (영웅 이상은 팔지 않는다). 날짜만으로 정해서 모두 같은 목록을 본다.</li>
 * </ul>
 */
public final class BlueprintRules {

    /** items.yml 의 도안 아이템 id (하나 — 가르치는 레시피는 아이템 PDC). */
    public static final String ITEM_ID = "blueprint";
    /** 이 희귀도 이상 장비는 도안이 필요하다. */
    public static final Rarity MIN_RARITY = Rarity.RARE;
    /** 이웃 단계 몫: 하나 아래 · 같음 · 하나 위 (장비 풀 band_tNN 과 같은 2 : 7 : 1). */
    public static final int W_BELOW = 2, W_SAME = 7, W_ABOVE = 1;
    /** 빌드 편향이 보는 줍는 사람 능력치 개수 (LootRoller.BUILD_TOP 과 같음). */
    public static final int BUILD_TOP = 2;

    private BlueprintRules() {}

    /** 이 장비를 만들려면 도안이 필요한가. */
    public static boolean needsBlueprint(ItemDef result) {
        return result != null && result.isGear() && result.rarity() != null && result.rarity().atLeast(MIN_RARITY);
    }

    public static boolean needsBlueprint(Content c, RecipeDef r) {
        return r != null && c != null && needsBlueprint(c.item(r.result()));
    }

    /**
     * 만들 수 있는가 (도안 기준만 — 재료·골드는 RecipeCheck).
     * @param enabled config blueprints.enabled (false 면 도안 없이 모두 만든다)
     */
    public static boolean canCraft(Content c, RecipeDef r, boolean enabled, Collection<String> learned) {
        if (!enabled || !needsBlueprint(c, r)) return true;
        return learned != null && learned.contains(r.id());
    }

    /** 도안이 쓰일 수 있는 콘텐츠인가: blueprint 아이템이 있고 loot.yml 에 도안 항목이 하나라도 있다. */
    public static boolean active(Content c) {
        if (c == null || c.item(ITEM_ID) == null) return false;
        for (kr.labyrinth.content.LootTable t : c.lootTables().values()) {
            for (kr.labyrinth.content.LootTable.Entry e : t.entries()) if (e.kind() == kr.labyrinth.content.LootTable.Kind.BLUEPRINT) return true;
            for (kr.labyrinth.content.LootTable.Entry e : t.guaranteed()) if (e.kind() == kr.labyrinth.content.LootTable.Kind.BLUEPRINT) return true;
        }
        return false;
    }

    /** 도안이 필요한 레시피 모두 (id 순). */
    public static List<RecipeDef> gated(Content c) {
        List<RecipeDef> out = new ArrayList<>();
        for (RecipeDef r : c.recipes().values()) if (needsBlueprint(c, r)) out.add(r);
        out.sort(Comparator.comparing(RecipeDef::id));
        return out;
    }

    /** 레시피 결과 장비의 단계 (숨김, 0 = 모름). */
    public static int tierOf(Content c, RecipeDef r) {
        ItemDef d = r == null ? null : c.item(r.result());
        return d == null ? 0 : d.tier();
    }

    /** 단계 t 의 도안 뽑기 후보 하나 (레시피 · 결과 장비 · 무게). */
    public record Candidate(RecipeDef recipe, ItemDef result, int weight) {}

    /** 단계 t 루팅의 후보 (무게 0 은 뺌). */
    public static List<Candidate> candidates(Content c, int tier) {
        List<Candidate> out = new ArrayList<>();
        for (RecipeDef r : gated(c)) {
            ItemDef d = c.item(r.result());
            int w = weight(tier, d.tier());
            if (w > 0) out.add(new Candidate(r, d, w));
        }
        return out;
    }

    /** 루팅 단계 t 에서 결과 장비 단계 s 의 무게. */
    public static int weight(int tier, int resultTier) {
        int d = resultTier - tier;
        return d == 0 ? W_SAME : d == -1 ? W_BELOW : d == 1 ? W_ABOVE : 0;
    }

    /** 후보가 줍는 사람 빌드에 맞는가 — 요구치 1위 능력치가 상위 능력치 안이거나, 요구치가 없는 장비. */
    public static boolean fits(ItemDef d, List<Stat> top) {
        Stat primary = d.requirement().primary();
        return primary == null || top.contains(primary);
    }

    /**
     * 도안 하나 뽑기. @return 레시피 id (후보가 없으면 null)
     * @param stats 줍는 사람 요구치 판정 능력치 (null = 편향 없음)
     */
    public static String pick(Content c, int tier, Map<Stat, Integer> stats, double bias, RandomGenerator rng) {
        List<Candidate> all = candidates(c, tier);
        if (all.isEmpty()) return null;
        List<Candidate> pool = all;
        if (stats != null && rng.nextDouble() < bias) {
            List<Stat> top = StatRequirement.top(stats, BUILD_TOP);
            if (!top.isEmpty()) {
                List<Candidate> own = new ArrayList<>();
                for (Candidate x : all) if (fits(x.result(), top)) own.add(x);
                if (!own.isEmpty()) pool = own;
            }
        }
        int total = 0;
        for (Candidate x : pool) total += x.weight();
        int r = rng.nextInt(total);
        for (Candidate x : pool) {
            if (r < x.weight()) return x.recipe().id();
            r -= x.weight();
        }
        return pool.get(pool.size() - 1).recipe().id();
    }

    /** 편향 없이 단계 t 도안 하나가 그 레시피일 확률. */
    public static double chanceOf(Content c, int tier, String recipeId) {
        int total = 0, mine = 0;
        for (Candidate x : candidates(c, tier)) {
            total += x.weight();
            if (x.recipe().id().equals(recipeId)) mine = x.weight();
        }
        return total == 0 ? 0 : (double) mine / total;
    }

    /** 이 장비를 만드는 도안이 필요한 레시피 (없으면 null). 레시피 id = 결과 id 가 보통이지만 결과로 찾는다. */
    public static RecipeDef recipeFor(Content c, String itemId) {
        if (itemId == null) return null;
        RecipeDef same = c.recipes().get(itemId);
        if (same != null && itemId.equals(same.result()) && needsBlueprint(c, same)) return same;
        for (RecipeDef r : c.recipes().values()) if (itemId.equals(r.result()) && needsBlueprint(c, r)) return r;
        return null;
    }

    /**
     * 0.3.6 첫 접속 (옛 플레이어 보호): 이미 가진 희귀 이상 장비의 도안은 배운 것으로 친다.
     * @param owned 가방·엔더 상자·장신구 칸의 미궁 아이템 id
     * @return 배울 레시피 id (id 순)
     */
    public static Set<String> grandfather(Content c, Collection<String> owned) {
        Set<String> out = new java.util.TreeSet<>();
        if (owned == null) return out;
        for (String id : new LinkedHashSet<>(owned)) {
            RecipeDef r = recipeFor(c, id);
            if (r != null) out.add(r.id());
        }
        return out;
    }

    // ── 상인 ─────────────────────────────────────────────

    /** config.yml {@code blueprints:} (없으면 기본값). */
    public record Settings(boolean enabled, int shopCount, int shopBase, int shopPerTier) {
        public static final Settings DEFAULT = new Settings(true, 3, 200, 40);

        public Settings {
            shopCount = Math.max(0, Math.min(7, shopCount));
            shopBase = Math.max(1, shopBase);
            shopPerTier = Math.max(0, shopPerTier);
        }
    }

    /** 상인이 파는 도안 = 희귀 장비 레시피만 (영웅 이상은 드롭으로만). */
    public static List<RecipeDef> shopPool(Content c) {
        List<RecipeDef> out = new ArrayList<>();
        for (RecipeDef r : gated(c)) if (c.item(r.result()).rarity() == Rarity.RARE) out.add(r);
        return out;
    }

    /** 그날(epochDay) 상인이 파는 도안 count 개 — 날짜만으로 정한다 (서버 모두 같은 목록). */
    public static List<String> shopPicks(Content c, long epochDay, int count) {
        List<RecipeDef> pool = new ArrayList<>(shopPool(c));
        SplittableRandom rng = new SplittableRandom(epochDay * 0x9E3779B97F4A7C15L + 0x51ED);
        List<String> out = new ArrayList<>();
        for (int i = 0; i < count && !pool.isEmpty(); i++) out.add(pool.remove(rng.nextInt(pool.size())).id());
        return out;
    }

    /** 상인 값 = 기본 + 단계 × 단계 값 (팔 때 값보다 언제나 비싸다 — 사서 되팔기로 골드가 늘지 않게). */
    public static int shopPrice(Content c, RecipeDef r, Settings s) {
        return s.shopBase() + s.shopPerTier() * Math.max(0, tierOf(c, r));
    }
}
