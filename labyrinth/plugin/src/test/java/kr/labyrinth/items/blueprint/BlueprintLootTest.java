package kr.labyrinth.items.blueprint;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 도안 루팅 (0.3.6 Q6).
 * <ul>
 *   <li>층마다 정예 · 보스 · 미로 금·철 상자 · 보물방 · 금고·미믹 · 특별 시련 표에 도안 항목이 하나씩 (단계 = 층).</li>
 *   <li>도안이 필요한 레시피는 모두 나오는 곳이 2종류 이상 (상인 핀 = 희귀만).</li>
 *   <li>굴림: 이웃 단계 2 : 7 : 1, Drop.recipe 에 레시피, 빌드 편향.</li>
 *   <li>기대 회차 (DropRateWindowTest 와 같은 1회 모형 — 보통·솔로·LUK 0·층 끝까지): 빌드에 맞는 원하는 도안 하나를 그 단계 층에서
 *       얻기까지. 장비 드롭 창(몬스터·상자 1~5.5 · 정예·시련·금고 2.5~9)과 비슷하게 12회 이하, 가운데값 4~8회
 *       (지금 6.2회 — 희귀 7.0 · 영웅 5.8 · 전설 4.4, tools/gen_036_blueprints.py CHANCE).</li>
 * </ul>
 */
class BlueprintLootTest {

    static Content content;

    static final double[] MIMIC = {0, 0.04, 0.055, 0.07, 0.085, 0.10, 0.115, 0.13, 0.145, 0.16, 0.175};
    static final double TREASURE_CHESTS = 2.7, VAULT = 2.25;
    static final double SPECIAL_Q = 0.30 / (1 - Math.pow(0.70, 4)), SPECIAL_C = 0.65;
    static final double BIAS = 0.65;

    @BeforeAll
    static void load() { content = ContentLoader.load(Path.of("src/main/resources/content")).content(); }

    /** 층 f 에서 도안 항목을 가져야 하는 표 → 종류. */
    static Map<String, String> homes(int f) {
        Map<String, String> out = new TreeMap<>();
        for (MobDef m : content.mobs().values()) if (m.floor() == f && m.isElite() && m.drops() != null) out.put(m.drops(), "elite");
        for (BossDef b : content.bosses().values()) if (b.floor() == f && b.drops() != null) out.put(b.drops(), "boss");
        out.put("maze_chest_gold_f" + f, "maze_gold");
        out.put("maze_chest_iron_f" + f, "maze_iron");
        out.put("treasure_floor_" + f, "treasure");
        out.put(String.format("hoard_f%02d", f), "hoard");
        out.put(String.format("special_trial_f%02d", f), "special");
        return out;
    }

    static List<LootTable.Entry> bpEntries(LootTable t) {
        List<LootTable.Entry> out = new ArrayList<>();
        for (LootTable.Entry e : t.entries()) if (e.kind() == LootTable.Kind.BLUEPRINT) out.add(e);
        for (LootTable.Entry e : t.guaranteed()) if (e.kind() == LootTable.Kind.BLUEPRINT) out.add(e);
        return out;
    }

    @Test
    void everyHomeTableHasOneEntryOfItsFloor() {
        for (int f : content.floors().keySet()) {
            for (var h : homes(f).entrySet()) {
                LootTable t = content.lootTable(h.getKey());
                assertNotNull(t, h.getKey());
                List<LootTable.Entry> es = bpEntries(t);
                assertEquals(1, es.size(), h.getKey() + " 도안 항목 수");
                assertEquals(f, es.get(0).floor(), h.getKey() + " 단계");
                assertTrue(es.get(0).chance() > 0 && es.get(0).chance() <= 1, h.getKey());
            }
        }
    }

    @Test
    void everyLockedRecipeHasTwoKindsOfSources() {
        Map<String, Set<String>> kinds = new HashMap<>();
        for (LootTable t : content.lootTables().values()) {
            String kind = null;
            for (int f : content.floors().keySet()) if (homes(f).containsKey(t.id())) kind = homes(f).get(t.id());
            for (LootTable.Entry e : bpEntries(t)) {
                for (BlueprintRules.Candidate c : BlueprintRules.candidates(content, e.floor())) {
                    kinds.computeIfAbsent(c.recipe().id(), k -> new TreeSet<>()).add(kind == null ? t.id() : kind);
                }
            }
        }
        for (RecipeDef r : BlueprintRules.shopPool(content)) kinds.computeIfAbsent(r.id(), k -> new TreeSet<>()).add("shop");
        List<String> poor = new ArrayList<>();
        for (RecipeDef r : BlueprintRules.gated(content)) {
            Set<String> k = kinds.getOrDefault(r.id(), Set.of());
            if (k.size() < 2) poor.add(r.id() + " " + k);
        }
        assertEquals(List.of(), poor, "나오는 곳이 2종류보다 적은 도안");
    }

    @Test
    void rollGivesBlueprintsOfNeighbouringTiers() {
        LootRoller roller = new LootRoller(content, new Random(17));
        Map<Integer, Integer> byTier = new TreeMap<>();
        int n = 0;
        for (int i = 0; i < 6000; i++) {
            for (LootRoller.Drop d : roller.roll("floor05_boss", new LootRoller.Request("normal", 1.0, 0, null))) {
                if (d.recipe() == null) continue;
                assertEquals(BlueprintRules.ITEM_ID, d.itemId());
                RecipeDef r = content.recipes().get(d.recipe());
                assertNotNull(r, d.recipe());
                assertTrue(BlueprintRules.needsBlueprint(content, r), d.recipe());
                byTier.merge(BlueprintRules.tierOf(content, r), 1, Integer::sum);
                n++;
            }
        }
        assertEquals(Set.of(4, 5, 6), byTier.keySet(), "이웃 단계만");
        // 무게 × 레시피 수 대로 (단계 4 : 5 : 6 = 2·n4 : 7·n5 : 1·n6)
        double w4 = 2.0 * count(4), w5 = 7.0 * count(5), w6 = 1.0 * count(6), tot = w4 + w5 + w6;
        assertEquals(w5 / tot, byTier.get(5) / (double) n, 0.04);
        assertEquals(w4 / tot, byTier.get(4) / (double) n, 0.04);
        assertEquals(0.40, n / 6000.0, 0.03, "보스 도안 확률");
    }

    @Test
    void buildBiasPrefersOwnBuildButAccessoriesFitEveryone() {
        Map<Stat, Integer> archer = new EnumMap<>(Stat.class);
        archer.put(Stat.DEX, 40);
        archer.put(Stat.LUK, 30);
        archer.put(Stat.STR, 5);
        List<Stat> top = kr.labyrinth.content.StatRequirement.top(archer, BlueprintRules.BUILD_TOP);
        Random rng = new Random(3);
        int fit = 0, total = 0, acc = 0;
        for (int i = 0; i < 4000; i++) {
            String rid = BlueprintRules.pick(content, 6, archer, 1.0, rng);
            ItemDef d = content.item(content.recipes().get(rid).result());
            total++;
            if (BlueprintRules.fits(d, top)) fit++;
            if (d.requirement().isEmpty()) acc++;
        }
        assertEquals(total, fit, "편향 1.0 = 빌드에 맞는 것만");
        assertTrue(acc > 0, "요구치 없는 장신구도 나온다");
    }

    static int count(int tier) {
        int n = 0;
        for (RecipeDef r : BlueprintRules.gated(content)) if (BlueprintRules.tierOf(content, r) == tier) n++;
        return n;
    }

    // ── 기대 회차 ─────────────────────────────────────────────

    /** 층 f 1회에 표 종류마다 굴리는 횟수 (DropRateWindowTest 와 같은 수). */
    static double runs(int f, String kind) {
        double wood = f <= 3 ? 3.3 : 4.4, iron = f <= 3 ? 1.3 : 2.3, gold = f <= 3 ? 0.6 : 1.2, secret = f <= 3 ? 1.0 : 2.0;
        return switch (kind) {
            case "elite" -> 1.0; // 정예 표 각각 (9·10층은 정예 2 를 표 수로 나눔 — 아래에서)
            case "boss" -> 1.0;
            case "maze_gold" -> gold + secret + VAULT;
            case "maze_iron" -> iron;
            case "treasure" -> content.floor(f).rooms().getOrDefault("treasure", 1) * TREASURE_CHESTS;
            case "hoard" -> VAULT + (wood + iron) * MIMIC[f];
            case "special" -> SPECIAL_Q * SPECIAL_C;
            default -> 0;
        };
    }

    /** 층 f 1회의 기대 도안 장 수. */
    static double blueprintsPerRun(int f) {
        Map<String, String> h = homes(f);
        long elites = h.values().stream().filter("elite"::equals).count();
        double eliteN = f >= 9 ? 2.0 : 1.0;
        double tot = 0;
        for (var e : h.entrySet()) {
            LootTable t = content.lootTable(e.getKey());
            double n = e.getValue().equals("elite") ? eliteN / elites : runs(f, e.getValue());
            for (LootTable.Entry x : bpEntries(t)) tot += n * Math.max(1, t.rolls()) * Math.min(1, x.chance());
        }
        return tot;
    }

    /** 도안 한 장이 그 레시피일 확률 — 줍는 사람 상위 2개 = 그 장비 요구 위 두 능력치 (장신구는 힘·민첩 빌드로 본다). */
    static double pickP(int tier, RecipeDef target) {
        ItemDef td = content.item(target.result());
        List<Stat> top = new ArrayList<>();
        for (var e : td.requirement().ordered()) if (top.size() < BlueprintRules.BUILD_TOP) top.add(e.getKey());
        if (top.isEmpty()) top = List.of(Stat.STR, Stat.DEX);
        double all = 0, fit = 0, w = 0;
        for (BlueprintRules.Candidate c : BlueprintRules.candidates(content, tier)) {
            all += c.weight();
            if (BlueprintRules.fits(c.result(), top)) fit += c.weight();
            if (c.recipe().id().equals(target.id())) w = c.weight();
        }
        if (all == 0) return 0;
        return fit == 0 ? w / all : BIAS * w / fit + (1 - BIAS) * w / all;
    }

    @Test
    void wantedBlueprintTakesAboutAsLongAsAWantedDrop() {
        List<Double> all = new ArrayList<>();
        Map<Rarity, List<Double>> byRarity = new EnumMap<>(Rarity.class);
        List<String> off = new ArrayList<>();
        StringBuilder table = new StringBuilder();
        for (int f : content.floors().keySet()) {
            double per = blueprintsPerRun(f);
            table.append(String.format("층 %d: 1회 도안 %.2f장%n", f, per));
            assertTrue(per >= 1.5 && per <= 4.0, f + "층 1회 도안 " + per);
        }
        for (RecipeDef r : BlueprintRules.gated(content)) {
            int t = BlueprintRules.tierOf(content, r);
            double p = blueprintsPerRun(t) * pickP(t, r);
            double runs = 1 / Math.min(0.999, p);
            all.add(runs);
            byRarity.computeIfAbsent(content.item(r.result()).rarity(), k -> new ArrayList<>()).add(runs);
            if (runs < 1 || runs > 12) off.add(r.id() + String.format(" %.1f회", runs));
        }
        assertEquals(List.of(), off, "기대 회차가 창 밖");
        double med = median(all);
        System.out.println("[도안] " + table.toString().replace(System.lineSeparator(), " · ") + "가운데값 " + String.format("%.2f", med)
                + "회 · 가장 긴 것 " + String.format("%.2f", all.stream().mapToDouble(Double::doubleValue).max().orElse(0))
                + "회 · 희귀도별 " + medians(byRarity));
        assertTrue(med >= 4 && med <= 8, "가운데값 " + med);
    }

    static String medians(Map<Rarity, List<Double>> m) {
        StringBuilder sb = new StringBuilder();
        m.forEach((k, v) -> sb.append(k.id()).append('=').append(String.format("%.1f", median(v))).append(' '));
        return sb.toString().trim();
    }

    static double median(List<Double> xs) {
        List<Double> s = new ArrayList<>(xs);
        s.sort(Double::compare);
        int n = s.size();
        return n % 2 == 1 ? s.get(n / 2) : (s.get(n / 2 - 1) + s.get(n / 2)) / 2;
    }
}
