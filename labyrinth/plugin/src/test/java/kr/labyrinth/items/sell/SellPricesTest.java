package kr.labyrinth.items.sell;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.enhance.EnhanceRules;
import kr.labyrinth.items.sell.SellPrices.Block;
import kr.labyrinth.items.sell.SellPrices.Config;
import kr.labyrinth.items.sell.SellPrices.Quote;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 판매가 (config.yml sell:): 공식 · 핀이 파는 값보다 언제나 싸게 · 팔 수 없는 물건 · 두 번 확인 · config 기본값. */
class SellPricesTest {

    static Content content;
    static SellPrices prices;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        prices = new SellPrices(Config.DEFAULT, SellPrices.buyPrices(content.npcs().values()), List.of());
    }

    private static ItemDef item(String id) {
        ItemDef d = content.item(id);
        assertNotNull(d, id);
        return d;
    }

    /** 기존 정의를 바탕으로 종류·희귀도·층·획득처만 바꾼 가짜 아이템. */
    private static ItemDef fake(ItemDef base, String id, ItemType type, Rarity rarity, int floor, List<String> sources) {
        return new ItemDef(id, base.name(), type, base.weaponType(), base.armorSlot(), base.armorSet(), rarity, base.levelReq(),
                base.classes(), base.stats(), base.setBonus(), base.aura(), base.weaponSkills(), floor, base.pool(), sources,
                base.use(), base.model(), base.texture(), base.lore(), base.raw());
    }

    // ── config ───────────────────────────────────────────────────────────

    @Test
    void bundledConfigMatchesCodeDefaults() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertNotNull(y.getConfigurationSection("sell"), "config.yml 에 sell: 이 있어야 함");
        assertEquals(Config.DEFAULT, Config.from(y.getConfigurationSection("sell")));
        assertEquals(Config.DEFAULT, Config.from(null));
    }

    @Test
    void partialConfigKeepsOtherDefaults() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("sell:\n  materials: {rare: 20}\n  confirm_rarity: legendary\n  unsellable: []\n  consumable_shop_ratio: 7\n");
        Config c = Config.from(y.getConfigurationSection("sell"));
        assertEquals(20, c.materials().get(Rarity.RARE));
        assertEquals(2, c.materials().get(Rarity.COMMON));
        assertEquals(Config.DEFAULT.gear(), c.gear());
        assertEquals(Rarity.LEGENDARY, c.confirmRarity());
        assertEquals(1.0, c.consumableShopRatio(), 1e-9, "비율은 1 을 넘지 않는다");
        assertTrue(c.unsellable().isEmpty());
        // 설정 목록을 비워도 전직의 두루마리는 팔 수 없다
        SellPrices p = new SellPrices(c, SellPrices.buyPrices(content.npcs().values()), List.of());
        assertEquals(Block.LISTED, p.quote(item("class_change_scroll"), 0).block());
    }

    // ── 공식 ─────────────────────────────────────────────────────────────

    @Test
    void materialPriceUsesRarityAndFloor() {
        ItemDef plate = item("verdigris_plate"); // 희귀 · 4층
        assertEquals(ItemType.MATERIAL, plate.type());
        assertEquals(Math.round(15 * (1 + 0.15 * plate.floor())), prices.quote(plate, 0).unit());
        ItemDef silk = item("spider_silk"); // 일반 · 2층 → 2 × 1.3 = 2.6 → 3
        assertEquals(Math.round(2 * (1 + 0.15 * silk.floor())), prices.quote(silk, 0).unit());
        ItemDef essence = item("labyrinth_essence"); // 층 없음 → 표 그대로
        assertEquals(0, essence.floor());
        assertEquals(Config.DEFAULT.materials().get(essence.rarity()), prices.quote(essence, 0).unit());
    }

    @Test
    void gearPriceUsesFloorAndEnhancement() {
        ItemDef gear = null;
        for (ItemDef d : content.items().values()) {
            if (d.isWeapon() && d.rarity() == Rarity.LEGENDARY && !d.sources().contains("starter")) {
                gear = d;
                break;
            }
        }
        assertNotNull(gear);
        int floor = EnhanceRules.gearFloor(gear);
        assertEquals(Math.round(400 * (1 + 0.1 * floor)), prices.quote(gear, 0).unit());
        assertEquals(Math.round(400 * (1 + 0.1 * floor) * (1 + 0.25 * 3)), prices.quote(gear, 3).unit());
        assertTrue(prices.quote(gear, 10).unit() > prices.quote(gear, 9).unit());
        // 장신구·방패도 장비 표
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.ACCESSORY && !d.sources().contains("starter")) {
                assertEquals(Math.round(Config.DEFAULT.gear().get(d.rarity()) * (1 + 0.1 * EnhanceRules.gearFloor(d))),
                        prices.quote(d, 0).unit(), d.id());
            }
        }
    }

    @Test
    void consumablesSoldByMerchantPayQuarterOfBuyPrice() {
        // 번들 상점 기준: 20 G → 5, 60 G → 15, 150 G → 37 (37.5 내림), 100 G → 25
        for (String id : List.of("minor_healing_potion", "healing_potion", "greater_healing_potion", "return_scroll")) {
            ItemDef d = item(id);
            assertEquals(ItemType.CONSUMABLE, d.type(), id);
            int buy = prices.buyPrice(id);
            assertTrue(buy > 0, id + " 는 핀이 판다");
            assertEquals((int) Math.floor(buy * 0.25), prices.quote(d, 0).unit(), id);
        }
        assertEquals(37, new SellPrices(Config.DEFAULT, Map.of("greater_healing_potion", 150), List.of())
                .quote(item("greater_healing_potion"), 0).unit(), "25% 는 내림");
        // 핀이 안 파는 소모품 = 재료 표
        ItemDef elixir = item("elixir_of_renewal");
        assertEquals(0, prices.buyPrice(elixir.id()));
        assertEquals(Config.DEFAULT.materials().get(elixir.rarity()), prices.quote(elixir, 0).unit());
    }

    @Test
    void merchantMaterialIsCappedBelowBuyPrice() {
        // 강화석은 재료 표 값이 이미 산 값의 절반보다 낮다 → 재료 표 그대로
        ItemDef stone = item("lesser_enhance_stone");
        int buy = prices.buyPrice(stone.id());
        assertTrue(buy > 0);
        long table = Math.round(Config.DEFAULT.materials().get(stone.rarity()) * (1 + 0.15 * stone.floor()));
        assertTrue(table <= buy / 2);
        assertEquals(table, prices.quote(stone, 0).unit());
        // 값싼 가짜 상점 장비 (신화 장비를 핀이 50 G 에 판다면) → 산 값 × 0.5 로 잘림, 강화해도 산 값을 넘지 않음
        ItemDef base = content.items().values().stream().filter(ItemDef::isWeapon).findFirst().orElseThrow();
        ItemDef cheap = fake(base, "cheap_mythic", ItemType.WEAPON, Rarity.MYTHIC, 10, List.of("shop"));
        SellPrices p = new SellPrices(Config.DEFAULT, Map.of("cheap_mythic", 50), List.of());
        for (int enh = 0; enh <= 10; enh++) assertEquals(25, p.quote(cheap, enh).unit());
        // 산 값 1 G 짜리는 팔 수 없다 (언제나 1 G 이상 싸야 하니 0)
        SellPrices one = new SellPrices(Config.DEFAULT, Map.of("cheap_mythic", 1), List.of());
        assertEquals(Block.NO_PRICE, one.quote(cheap, 0).block());
    }

    /** 핀이 파는 모든 물건 — 어떤 강화 단계로 되팔아도 산 값보다 싸다 (사서 되팔아 골드를 불릴 수 없음). */
    @Test
    void sellPriceIsAlwaysBelowEveryShopPrice() {
        int checked = 0;
        for (NpcDef npc : content.npcs().values()) {
            if (!"merchant".equals(npc.role())) continue;
            for (NpcDef.ShopEntry e : npc.shop()) {
                ItemDef def = item(e.item());
                for (int enh = 0; enh <= 10; enh++) {
                    Quote q = prices.quote(def, enh);
                    if (!q.sellable()) continue;
                    assertTrue(q.unit() < e.price(), e.item() + " +" + enh + ": 판매 " + q.unit() + " ≥ 구매 " + e.price());
                    checked++;
                }
            }
        }
        assertTrue(checked > 0, "번들 상점에 되팔 수 있는 물건이 하나는 있어야 함");
        // 설정을 아무리 높여도 마찬가지
        YamlConfiguration y = new YamlConfiguration();
        try {
            y.loadFromString("sell:\n  materials: {common: 99999, uncommon: 99999, rare: 99999, epic: 99999}\n"
                    + "  consumable_shop_ratio: 1.0\n  shop_item_cap: 1.0\n");
        } catch (Exception ex) {
            throw new AssertionError(ex);
        }
        SellPrices greedy = new SellPrices(Config.from(y.getConfigurationSection("sell")),
                SellPrices.buyPrices(content.npcs().values()), List.of());
        for (NpcDef npc : content.npcs().values()) {
            if (!"merchant".equals(npc.role())) continue;
            for (NpcDef.ShopEntry e : npc.shop()) {
                Quote q = greedy.quote(item(e.item()), 0);
                if (q.sellable()) assertTrue(q.unit() < e.price(), e.item());
            }
        }
    }

    @Test
    void buyPricesTakeCheapestMerchantAndIgnoreOtherRoles() {
        NpcDef a = new NpcDef("a", "A", "", "a", "merchant", "overworld", 0, List.of(),
                List.of(new NpcDef.ShopEntry("x", 50, 1), new NpcDef.ShopEntry("y", 0, 1)), null, null);
        NpcDef b = new NpcDef("b", "B", "", "b", "merchant", "overworld", 0, List.of(),
                List.of(new NpcDef.ShopEntry("x", 30, 1)), null, null);
        NpcDef smith = new NpcDef("c", "C", "", "c", "blacksmith", "overworld", 0, List.of(),
                List.of(new NpcDef.ShopEntry("x", 1, 1)), null, null);
        Map<String, Integer> m = SellPrices.buyPrices(List.of(a, b, smith));
        assertEquals(Map.of("x", 30), m);
    }

    // ── 팔 수 없는 물건 ───────────────────────────────────────────────────

    @Test
    void unsellableItems() {
        assertEquals(Block.NOT_LABYRINTH, prices.quote(null, 0).block());
        assertEquals(Block.KEY, prices.quote(item("vault_key"), 0).block());
        assertEquals(Block.LISTED, prices.quote(item("class_change_scroll"), 0).block());
        int starters = 0, keys = 0;
        for (ItemDef d : content.items().values()) {
            Quote q = prices.quote(d, 0);
            if (d.sources().contains("starter")) {
                assertEquals(Block.STARTER, q.block(), d.id());
                starters++;
            }
            if (d.type() == ItemType.KEY) {
                assertEquals(Block.KEY, q.block(), d.id());
                keys++;
            }
            assertTrue(q.unit() >= 0, d.id());
            assertEquals(q.block() == Block.NONE, q.sellable(), d.id());
        }
        assertTrue(starters >= 4, "수련생 장비(시작 지급)");
        assertTrue(keys >= 7, "직업 문장 6 + 금고 열쇠");
        // 바뀐 전직 아이템(class_change.item)·설정 목록도 막힌다
        SellPrices extra = new SellPrices(Config.DEFAULT, Map.of(), List.of("spider_silk"));
        assertEquals(Block.LISTED, extra.quote(item("spider_silk"), 0).block());
        // 꺼 두면 아무것도 안 산다
        Config off = new Config(false, Config.DEFAULT_MATERIALS, 0.15, Config.DEFAULT_GEAR, 0.1, 0.25, 0.25, 0.5,
                Rarity.EPIC, 1, Set.of());
        assertEquals(Block.DISABLED, new SellPrices(off, Map.of(), List.of()).quote(item("spider_silk"), 0).block());
    }

    @Test
    void ordinaryLootIsSellable() {
        // 몬스터·상자·보스·대장간 장비와 재료는 전부 팔 수 있다 (시작 지급·열쇠·전직 제외)
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.KEY || d.sources().contains("starter") || SellPrices.ALWAYS_UNSELLABLE.contains(d.id())) continue;
            assertTrue(prices.quote(d, 0).sellable(), d.id() + " 를 팔 수 있어야 함");
        }
    }

    // ── 두 번 확인 ───────────────────────────────────────────────────────

    @Test
    void epicOrEnhancedNeedsSecondConfirm() {
        ItemDef epicMat = item("warden_heartwood");
        assertEquals(Rarity.EPIC, epicMat.rarity());
        assertTrue(prices.risky(epicMat, 0));
        ItemDef rare = content.items().values().stream().filter(d -> d.isGear() && d.rarity() == Rarity.RARE).findFirst().orElseThrow();
        assertFalse(prices.risky(rare, 0));
        assertTrue(prices.risky(rare, 1), "+1 이상 강화 장비");
        assertFalse(prices.risky(item("spider_silk"), 0));
        assertFalse(prices.risky(null, 5));
        Config noEnh = new Config(true, Config.DEFAULT_MATERIALS, 0.15, Config.DEFAULT_GEAR, 0.1, 0.25, 0.25, 0.5,
                Rarity.LEGENDARY, 0, Set.of());
        SellPrices p = new SellPrices(noEnh, Map.of(), List.of());
        assertFalse(p.risky(rare, 7));
        assertFalse(p.risky(epicMat, 0));
    }

    @Test
    void tableLoreMentionsEveryRarity() {
        List<String> lines = new ArrayList<>(prices.tableLore());
        String all = String.join("\n", lines);
        for (Rarity r : Rarity.values()) assertTrue(all.contains(r.displayName()), r.id());
        assertTrue(all.contains("15%") && all.contains("10%") && all.contains("25%"));
        assertEquals("12.5%", SellPrices.pct(0.125));
    }
}
