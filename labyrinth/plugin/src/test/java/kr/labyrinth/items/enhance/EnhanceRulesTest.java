package kr.labyrinth.items.enhance;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.ItemRolls;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.items.enhance.EnhanceRules.Outcome;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 강화 규칙 (GDD §11.13): 확률·하락·보호·스탯 배율·비용·강화석 구간 + 번들 콘텐츠·config 기본값. */
class EnhanceRulesTest {

    static Content content;
    static EnhanceRules rules;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        rules = new EnhanceRules(EnhanceRules.Config.DEFAULT);
    }

    @Test
    void configYmlMatchesBuiltInDefaults() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertNotNull(y.getConfigurationSection("enhance"), "config.yml 에 enhance: 블록");
        assertEquals(EnhanceRules.Config.DEFAULT, EnhanceRules.Config.from(y.getConfigurationSection("enhance")));
        assertEquals(EnhanceRules.Config.DEFAULT, EnhanceRules.Config.from(null));
        // 일부만 고친 설정: 나머지는 기본값
        YamlConfiguration part = new YamlConfiguration();
        part.set("chances", List.of(0.5));
        part.set("downgrade_from", 0);
        EnhanceRules.Config c = EnhanceRules.Config.from(part);
        EnhanceRules r = new EnhanceRules(c);
        assertEquals(0.5, r.chance(1), 1e-9);
        assertEquals(0.5, r.chance(10), 1e-9, "모자란 목록은 마지막 값");
        assertFalse(r.downgradesOnFail(9), "0 = 하락 없음");
        assertEquals(EnhanceRules.Config.DEFAULT.stones(), c.stones());
    }

    @Test
    void spicyChances() {
        for (int t = 1; t <= 4; t++) assertEquals(1.0, rules.chance(t), 1e-9, "+" + t + " 확정");
        double[] expect = {0.90, 0.80, 0.65, 0.50, 0.35, 0.20};
        for (int i = 0; i < expect.length; i++) assertEquals(expect[i], rules.chance(5 + i), 1e-9);
        assertEquals(0, rules.chance(11), 1e-9, "최대 단계 너머는 0");
        assertEquals(0, rules.chance(0), 1e-9);
        for (int t = 2; t <= 10; t++) assertTrue(rules.chance(t) <= rules.chance(t - 1), "확률은 줄기만 한다");
    }

    @Test
    void failureDowngradesOnlyFromPlusSeven() {
        // +1~+4 는 roll 이 무엇이든 성공
        for (int lv = 0; lv < 4; lv++) assertEquals(Outcome.SUCCESS, rules.resolve(lv, 0.9999, false));
        // +4 → +5, +6 → +7 실패: 재료만 잃고 단계 유지
        assertEquals(Outcome.FAIL, rules.resolve(4, 0.95, false));
        assertEquals(Outcome.FAIL, rules.resolve(6, 0.99, true), "하락이 없는 실패에는 주문서를 쓰지 않는다");
        // +7 이상에서 실패: 한 단계 하락, 보호 주문서면 유지
        assertEquals(Outcome.DOWNGRADE, rules.resolve(7, 0.6, false));
        assertEquals(Outcome.PROTECTED, rules.resolve(7, 0.6, true));
        assertEquals(Outcome.SUCCESS, rules.resolve(7, 0.49, false));
        assertEquals(Outcome.DOWNGRADE, rules.resolve(9, 0.2, false), "roll == 확률 이면 실패");
        assertEquals(8, EnhanceRules.levelAfter(9, Outcome.DOWNGRADE));
        assertEquals(9, EnhanceRules.levelAfter(9, Outcome.PROTECTED));
        assertEquals(9, EnhanceRules.levelAfter(9, Outcome.FAIL));
        assertEquals(10, EnhanceRules.levelAfter(9, Outcome.SUCCESS));
        assertTrue(EnhanceRules.consumesProtection(Outcome.PROTECTED));
        for (Outcome o : new Outcome[] {Outcome.SUCCESS, Outcome.FAIL, Outcome.DOWNGRADE}) {
            assertFalse(EnhanceRules.consumesProtection(o), o + " 에는 주문서가 남는다");
        }
        assertFalse(rules.downgradesOnFail(6));
        assertTrue(rules.downgradesOnFail(7));
    }

    @Test
    void observedSuccessRateMatchesChance() {
        SplittableRandom rng = new SplittableRandom(7);
        for (int lv : new int[] {4, 6, 7, 9}) {
            int ok = 0, n = 200_000;
            for (int i = 0; i < n; i++) if (rules.resolve(lv, rng.nextDouble(), false) == Outcome.SUCCESS) ok++;
            assertEquals(rules.chance(lv + 1), ok / (double) n, 0.005, "+" + (lv + 1));
        }
    }

    /** 0 → +10 까지 평균 시도 수 (시뮬레이션). 보호 주문서를 쓰면 줄고, +7 까지는 하락 없이 금방. */
    @Test
    void protectionShortensTheClimb() {
        SplittableRandom rng = new SplittableRandom(11);
        double plain = climb(rng, false, 10), guarded = climb(rng, true, 10), toSeven = climb(rng, false, 7);
        assertTrue(guarded < plain, "보호 " + guarded + " < 그냥 " + plain);
        assertTrue(toSeven < 12, "+7 까지 평균 " + toSeven + "회");
        assertTrue(plain > 40, "+10 은 매운 맛: 평균 " + plain + "회");
    }

    private static double climb(SplittableRandom rng, boolean protect, int goal) {
        long total = 0;
        int runs = 4000;
        for (int r = 0; r < runs; r++) {
            int lv = 0;
            while (lv < goal) {
                lv = EnhanceRules.levelAfter(lv, rules.resolve(lv, rng.nextDouble(), protect));
                total++;
            }
        }
        return total / (double) runs;
    }

    @Test
    void statMultiplierIsSixPercentPerLevel() {
        assertEquals(1.0, rules.multiplier(0), 1e-9);
        assertEquals(1.06, rules.multiplier(1), 1e-9);
        assertEquals(1.6, rules.multiplier(10), 1e-9);
        assertEquals(1.6, rules.multiplier(15), 1e-9, "최대 단계로 자름");

        ItemDef sword = content.item("ember_greatsword");
        Map<String, Double> base = Map.of("damage", 40.0, "STR", 7.0, "crit_chance", 0.05);
        Map<String, Double> plus10 = rules.apply(sword, base, 10);
        assertEquals(64.0, plus10.get("damage"), 1e-9, "피해 40 × 1.6");
        assertEquals(7.0, plus10.get("STR"), 1e-9, "부가 스탯은 그대로");
        assertEquals(0.05, plus10.get("crit_chance"), 1e-9);
        assertEquals(43.0, rules.apply(sword, base, 1).get("damage"), 1e-9, "40 + 2.4 → 늘어난 몫 올림 = 43");
        Map<String, Double> low = Map.of("damage", 7.0);
        for (int lv = 1; lv <= 10; lv++) {
            assertTrue(rules.apply(sword, low, lv).get("damage") > 7.0, "낮은 무기도 +" + lv + " 효과가 보인다");
            if (lv > 1) assertTrue(rules.apply(sword, low, lv).get("damage") >= rules.apply(sword, low, lv - 1).get("damage"));
        }
        assertEquals(12.0, rules.apply(sword, low, 10).get("damage"), 1e-9, "7 + ⌈4.2⌉");
        assertEquals(base, rules.apply(sword, base, 0));
        assertEquals(Map.of("damage", 24.0), rules.bonus(sword, base, 10));

        ItemDef armor = firstOf(ItemType.ARMOR, false);
        Map<String, Double> ab = Map.of("defense", 20.0, "hp", 50.0, "VIT", 3.0);
        Map<String, Double> a7 = rules.apply(armor, ab, 7);
        assertEquals(29.0, a7.get("defense"), 1e-9, "20 + ⌈8.4⌉");
        assertEquals(71.0, a7.get("hp"), 1e-9, "50 × 1.42");
        assertEquals(3.0, a7.get("VIT"), 1e-9);
        ItemDef shield = firstOf(ItemType.ARMOR, true);
        assertEquals(32.0, rules.apply(shield, Map.of("defense", 20.0), 10).get("defense"), 1e-9, "방패도 방어 배율");
    }

    @Test
    void targetsAreWeaponsArmorAndShieldsOnly() {
        int weapons = 0, armor = 0;
        for (ItemDef d : content.items().values()) {
            boolean e = EnhanceRules.enhanceable(d);
            assertEquals(d.type() == ItemType.WEAPON || d.type() == ItemType.ARMOR, e, d.id());
            if (e && d.isWeapon()) weapons++;
            if (e && !d.isWeapon()) armor++;
            if (d.type() == ItemType.ACCESSORY) assertFalse(e, "장신구 제외: " + d.id());
        }
        assertTrue(weapons >= 60 && armor >= 60);
        assertFalse(EnhanceRules.enhanceable(null), "바닐라 아이템(정의 없음)은 강화 불가");
    }

    @Test
    void stoneTierFollowsGearFloor() {
        for (ItemDef d : content.items().values()) {
            if (!EnhanceRules.enhanceable(d)) continue;
            int f = EnhanceRules.gearFloor(d);
            String want = f <= 3 ? "lesser_enhance_stone" : f <= 7 ? "greater_enhance_stone" : "supreme_enhance_stone";
            assertEquals(want, rules.stoneFor(d), d.id() + " (층 " + f + ")");
        }
        int[] counts = {1, 1, 1, 1, 2, 2, 2, 3, 3, 4};
        for (int t = 1; t <= 10; t++) assertEquals(counts[t - 1], rules.stoneCount(t), "+" + t);
    }

    @Test
    void goldScalesWithLevelRarityAndStep() {
        ItemDef t1 = content.item("corridor_guard_longsword");
        if (t1 == null) t1 = cheapestWeapon();
        long first = rules.baseGold(t1, 1);
        assertEquals(Math.round(3.0 * (t1.levelReq() + 4) * rarity(t1.rarity())), first);
        for (int t = 2; t <= 10; t++) assertTrue(rules.baseGold(t1, t) > rules.baseGold(t1, t - 1), "단계가 높을수록 비싸다");
        ItemDef ember = content.item("ember_greatsword");
        assertTrue(rules.baseGold(ember, 5) > rules.baseGold(t1, 5), "레벨·등급이 높을수록 비싸다");
        assertEquals(Math.round(rules.baseGold(ember, 9) * 0.7), rules.gold(ember, 9, 0.95), "할인은 최대 30%");
        assertEquals(rules.baseGold(ember, 9), rules.gold(ember, 9, 0));
    }

    @Test
    void bundledContentHasStonesDropsAndShop() {
        for (EnhanceRules.Stone s : rules.config().stones()) {
            ItemDef d = content.item(s.item());
            assertNotNull(d, s.item());
            assertEquals(ItemType.MATERIAL, d.type());
            assertEquals("icon", d.model().str("shape", "icon"), "재료는 2D 아이콘");
        }
        ItemDef scroll = content.item(rules.config().protectionItem());
        assertNotNull(scroll);
        assertEquals(ItemType.MATERIAL, scroll.type());
        // 몹·보스·상자 테이블이 전부 enhance_* 하위 테이블을 굴린다
        for (var m : content.mobs().values()) {
            if (m.drops() == null) continue;
            assertTrue(refsEnhance(content.lootTable(m.drops())), m.id() + " 드롭에 강화석 없음");
        }
        for (var b : content.bosses().values()) assertTrue(refsEnhance(content.lootTable(b.drops())), b.id());
        for (int f = 1; f <= 10; f++) {
            assertTrue(refsEnhance(content.lootTable("treasure_floor_" + f)), "treasure_floor_" + f);
            assertTrue(refsEnhance(content.lootTable("gimmick_floor_" + f)), "gimmick_floor_" + f);
        }
        boolean sold = false;
        for (NpcDef n : content.npcs().values()) {
            if (n.shop() == null) continue;
            for (NpcDef.ShopEntry e : n.shop()) sold |= "lesser_enhance_stone".equals(e.item());
        }
        assertTrue(sold, "떠돌이 상인이 하급 강화석을 판다");
        assertTrue(content.achievements().values().stream().anyMatch(a -> "ENHANCE".equals(a.conditionType())
                && a.condition().bool("server_first", false) && a.condition().integer("level", 0) == 10), "최초 +10 칭호");
    }

    @Test
    void tooltipShowsLevelNextChanceAndBonus() {
        ItemDef ember = content.item("ember_greatsword");
        Map<String, Double> base = ItemRolls.midpoint(ember);
        List<String> l0 = Enhancement.tooltip(content, ember, 0);
        assertTrue(l0.get(0).contains("+0"));
        assertTrue(String.join("\n", l0).contains("100%"));
        List<String> l7 = Enhancement.tooltip(content, ember, 7);
        String t7 = String.join("\n", l7);
        assertTrue(t7.contains("+7") && t7.contains("50%") && t7.contains("+6 으로 내려감"), t7);
        assertTrue(t7.contains(content.item(rules.stoneFor(ember)).name()));
        assertTrue(String.join("\n", Enhancement.tooltip(content, ember, 10)).contains("최대"));
        assertTrue(Enhancement.tooltip(content, firstOf(ItemType.ACCESSORY, false), 3).isEmpty(), "장신구는 강화 줄 없음");

        List<String> lines = ItemTooltip.lines(content, ember, base, rules.bonus(ember, base, 7), l7);
        String all = String.join("\n", lines);
        double plus = rules.bonus(ember, base, 7).get("damage");
        assertTrue(all.contains("(" + ItemTooltip.formatStat("damage", plus) + ")"), all);
        assertTrue(all.contains("⚒ 강화 +7"));
    }

    @Test
    void namePrefixShinesFromSeven() {
        assertEquals("", rules.namePrefix(0));
        assertTrue(rules.namePrefix(3).contains("+3"));
        assertFalse(rules.shines(6));
        assertTrue(rules.shines(7));
        assertTrue(rules.radiant(10));
        assertFalse(rules.radiant(9));
        assertTrue(rules.nameColor(Rarity.RARE, 7)[0].startsWith("<gradient:"));
        assertEquals("<" + Rarity.RARE.color() + ">", rules.nameColor(Rarity.RARE, 6)[0]);
    }

    // ── 도우미 ────────────────────────────────────────────────────────────

    private static boolean refsEnhance(LootTable t) {
        if (t == null) return false;
        for (List<LootTable.Entry> list : List.of(t.entries(), t.guaranteed())) {
            for (LootTable.Entry e : list) {
                if (e.kind() == LootTable.Kind.TABLE && e.table() != null && e.table().startsWith("enhance_")) return true;
            }
        }
        return false;
    }

    private static ItemDef firstOf(ItemType type, boolean shield) {
        return content.items().values().stream().filter(d -> d.type() == type && d.isShield() == shield).findFirst().orElseThrow();
    }

    private static ItemDef cheapestWeapon() {
        return content.items().values().stream().filter(ItemDef::isWeapon)
                .min((a, b) -> Integer.compare(a.levelReq(), b.levelReq())).orElseThrow();
    }

    private static double rarity(Rarity r) {
        return EnhanceRules.Config.DEFAULT.goldRarity().getOrDefault(r, 1.0);
    }
}
