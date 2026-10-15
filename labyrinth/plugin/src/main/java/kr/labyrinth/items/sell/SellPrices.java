package kr.labyrinth.items.sell;

import java.util.Collection;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.items.enhance.EnhanceRules;
import org.bukkit.configuration.ConfigurationSection;

/**
 * 떠돌이 상인 핀에게 파는 값 (순수 계산 — 서버 없이 단위 테스트). 설정은 config.yml {@code sell:}, 없으면 {@link Config#DEFAULT}.
 * <ul>
 *   <li>재료: 희귀도 표 × (1 + material_floor_bonus × 층) — 층은 items.yml floor (정수·강화석 등 층 없는 재료는 0)</li>
 *   <li>장비(무기·방어구·방패·장신구): 희귀도 표 × (1 + gear_floor_bonus × 층) × (1 + enhance_bonus × 강화 단계)</li>
 *   <li>소모품: 핀이 파는 것이면 산 값 × consumable_shop_ratio, 아니면 재료 표</li>
 *   <li>핀이 파는 물건은 무엇이든 산 값 × shop_item_cap 이하, 그리고 언제나 산 값보다 1 G 이상 싸다 (사서 되팔아 버는 일 없음)</li>
 *   <li>팔 수 없음: 열쇠류(type: key — 금고 열쇠·직업 문장), 시작 지급품(sources 에 starter), 전직의 두루마리, unsellable 목록</li>
 * </ul>
 */
public final class SellPrices {

    /** 언제나 팔 수 없는 아이템 (설정 unsellable 을 비워도). 전직의 두루마리 = 사서 되팔기 · 직업 변경 제한 우회 방지. */
    public static final Set<String> ALWAYS_UNSELLABLE = Set.of("class_change_scroll");

    /** 팔 수 없는 까닭 (NONE = 팔 수 있음). */
    public enum Block {
        NONE(""),
        DISABLED("지금은 상인이 물건을 사지 않습니다."),
        NOT_LABYRINTH("미궁 아이템만 팔 수 있습니다."),
        KEY("열쇠·문장 같은 물건은 팔 수 없습니다."),
        STARTER("시작 지급품은 팔 수 없습니다."),
        LISTED("이 물건은 상인이 사지 않습니다."),
        NO_PRICE("값을 매길 수 없는 물건입니다.");

        private final String message;

        Block(String message) { this.message = message; }

        /** 플레이어에게 보여 줄 한국어 문장. */
        public String message() { return message; }
    }

    /** 한 개 값. block 이 NONE 이 아니면 unit = 0. */
    public record Quote(int unit, Block block) {
        public boolean sellable() { return block == Block.NONE && unit > 0; }

        static Quote no(Block b) { return new Quote(0, b); }
    }

    /**
     * config.yml {@code sell:}. 표에 빠진 희귀도는 기본값, 음수·이상한 값은 0 쪽으로 자른다.
     * @param confirmRarity 이 희귀도 이상은 [판매] 를 한 번 더 눌러야 한다
     * @param confirmEnhance 강화 단계가 이 값 이상이면 한 번 더 (0 = 강화로는 묻지 않음)
     */
    public record Config(boolean enabled, Map<Rarity, Integer> materials, double materialFloorBonus,
                         Map<Rarity, Integer> gear, double gearFloorBonus, double enhanceBonus,
                         double consumableShopRatio, double shopItemCap, Rarity confirmRarity, int confirmEnhance,
                         Set<String> unsellable) {

        public static final Map<Rarity, Integer> DEFAULT_MATERIALS = table(2, 5, 15, 40, 120, 300);
        public static final Map<Rarity, Integer> DEFAULT_GEAR = table(10, 25, 60, 150, 400, 1000);

        /** 코드 기본값 (= jar 의 config.yml sell:). 기존 서버 config.yml 에 sell 키가 없어도 이 값으로 판다. */
        public static final Config DEFAULT = new Config(true, DEFAULT_MATERIALS, 0.15, DEFAULT_GEAR, 0.10, 0.25, 0.25, 0.5,
                Rarity.EPIC, 1, ALWAYS_UNSELLABLE);

        /** {@code sell: false} — 판매 끔 (값은 기본값 그대로). */
        public static final Config DISABLED = DEFAULT.withEnabled(false);

        public Config {
            materials = Collections.unmodifiableMap(new EnumMap<>(materials));
            gear = Collections.unmodifiableMap(new EnumMap<>(gear));
            materialFloorBonus = Math.max(0, materialFloorBonus);
            gearFloorBonus = Math.max(0, gearFloorBonus);
            enhanceBonus = Math.max(0, enhanceBonus);
            consumableShopRatio = Math.max(0, Math.min(1, consumableShopRatio));
            shopItemCap = Math.max(0, Math.min(1, shopItemCap));
            if (confirmRarity == null) confirmRarity = Rarity.EPIC;
            confirmEnhance = Math.max(0, confirmEnhance);
            unsellable = Set.copyOf(unsellable == null ? Set.of() : unsellable);
        }

        static Map<Rarity, Integer> table(int... v) {
            Map<Rarity, Integer> m = new EnumMap<>(Rarity.class);
            for (Rarity r : Rarity.values()) m.put(r, v[r.ordinal()]);
            return m;
        }

        /** 같은 값에 켜기만 바꾼 것. */
        public Config withEnabled(boolean on) {
            return new Config(on, materials, materialFloorBonus, gear, gearFloorBonus, enhanceBonus, consumableShopRatio,
                    shopItemCap, confirmRarity, confirmEnhance, unsellable);
        }

        /**
         * config.yml 의 {@code sell} 값 그대로 (getConfig().get("sell")). 다른 섹션처럼 {@code sell: false} 는 끔,
         * {@code sell: true}·키 없음 = 기본값, 섹션이면 {@link #from}.
         */
        public static Config of(Object raw) {
            if (raw instanceof ConfigurationSection s) return from(s);
            if (Boolean.FALSE.equals(raw)) return DISABLED;
            if (raw instanceof String str && "false".equalsIgnoreCase(str.trim())) return DISABLED;
            return DEFAULT;
        }

        /** 섹션이 없으면(null) 기본값. */
        public static Config from(ConfigurationSection s) {
            if (s == null) return DEFAULT;
            Rarity confirm = Rarity.byId(s.getString("confirm_rarity", DEFAULT.confirmRarity().id()));
            Set<String> blocked = new LinkedHashSet<>();
            if (s.isList("unsellable")) {
                for (String id : s.getStringList("unsellable")) if (id != null && !id.isBlank()) blocked.add(id.trim().toLowerCase(Locale.ROOT));
            } else {
                blocked.addAll(DEFAULT.unsellable());
            }
            return new Config(s.getBoolean("enabled", DEFAULT.enabled()),
                    readTable(s.getConfigurationSection("materials"), DEFAULT_MATERIALS),
                    s.getDouble("material_floor_bonus", DEFAULT.materialFloorBonus()),
                    readTable(s.getConfigurationSection("gear"), DEFAULT_GEAR),
                    s.getDouble("gear_floor_bonus", DEFAULT.gearFloorBonus()),
                    s.getDouble("enhance_bonus", DEFAULT.enhanceBonus()),
                    s.getDouble("consumable_shop_ratio", DEFAULT.consumableShopRatio()),
                    s.getDouble("shop_item_cap", DEFAULT.shopItemCap()),
                    confirm == null ? DEFAULT.confirmRarity() : confirm,
                    s.getInt("confirm_enhance", DEFAULT.confirmEnhance()),
                    blocked);
        }

        private static Map<Rarity, Integer> readTable(ConfigurationSection t, Map<Rarity, Integer> def) {
            Map<Rarity, Integer> m = new EnumMap<>(def);
            if (t == null) return m;
            for (Rarity r : Rarity.values()) {
                if (t.contains(r.id())) m.put(r, Math.max(0, t.getInt(r.id(), def.get(r))));
            }
            return m;
        }
    }

    private final Config config;
    /** 핀(상인)이 파는 값 — 아이템 id → 가장 싼 값. */
    private final Map<String, Integer> buyPrices;
    private final Set<String> blocked;

    /**
     * @param buyPrices 상인 구매가 ({@link #buyPrices(Collection)})
     * @param extraBlocked 더 막을 id (예: config class_change.item — 설정으로 바뀐 전직 아이템)
     */
    public SellPrices(Config config, Map<String, Integer> buyPrices, Collection<String> extraBlocked) {
        this.config = config == null ? Config.DEFAULT : config;
        this.buyPrices = Map.copyOf(buyPrices == null ? Map.of() : buyPrices);
        Set<String> b = new LinkedHashSet<>(ALWAYS_UNSELLABLE);
        b.addAll(this.config.unsellable());
        if (extraBlocked != null) for (String id : extraBlocked) if (id != null && !id.isBlank()) b.add(id);
        this.blocked = Set.copyOf(b);
    }

    public Config config() { return config; }

    /** 상인(role: merchant)들의 shop 에서 아이템별 가장 싼 구매가 (가격 0 이하 줄은 무시). */
    public static Map<String, Integer> buyPrices(Collection<NpcDef> npcs) {
        Map<String, Integer> out = new HashMap<>();
        if (npcs == null) return out;
        for (NpcDef n : npcs) {
            if (n == null || !"merchant".equals(n.role()) || n.shop() == null) continue;
            for (NpcDef.ShopEntry e : n.shop()) {
                if (e == null || e.item() == null || e.price() <= 0) continue;
                out.merge(e.item(), e.price(), Math::min);
            }
        }
        return out;
    }

    /** 핀이 이 아이템을 파는 값 (안 팔면 0). */
    public int buyPrice(String itemId) { return buyPrices.getOrDefault(itemId, 0); }

    /** 이 아이템 한 개의 판매가. def 가 null 이면 미궁 아이템이 아님. */
    public Quote quote(ItemDef def, int enhanceLevel) {
        if (!config.enabled()) return Quote.no(Block.DISABLED);
        if (def == null) return Quote.no(Block.NOT_LABYRINTH);
        if (def.type() == ItemType.KEY) return Quote.no(Block.KEY);
        if (def.sources().contains("starter")) return Quote.no(Block.STARTER);
        if (blocked.contains(def.id())) return Quote.no(Block.LISTED);
        Rarity r = def.rarity() == null ? Rarity.COMMON : def.rarity();
        int buy = buyPrice(def.id());
        double value;
        if (def.isGear()) {
            int floor = Math.max(1, Math.min(10, EnhanceRules.gearFloor(def)));
            int enh = Math.max(0, enhanceLevel);
            value = config.gear().getOrDefault(r, 0) * (1 + config.gearFloorBonus() * floor) * (1 + config.enhanceBonus() * enh);
        } else if (def.type() == ItemType.CONSUMABLE && buy > 0) {
            value = Math.floor(buy * config.consumableShopRatio());
        } else {
            value = config.materials().getOrDefault(r, 0) * (1 + config.materialFloorBonus() * materialFloor(def));
        }
        long unit = Math.round(value);
        if (buy > 0) {
            // 핀이 파는 물건: 산 값의 일정 비율 이하, 그리고 언제나 산 값보다 싸게 (사서 되팔기로 골드가 늘지 않게)
            if (def.type() != ItemType.CONSUMABLE) unit = Math.min(unit, (long) Math.floor(buy * config.shopItemCap()));
            unit = Math.min(unit, buy - 1L);
        }
        if (unit <= 0) return Quote.no(Block.NO_PRICE);
        return new Quote((int) Math.min(Integer.MAX_VALUE, unit), Block.NONE);
    }

    /** [판매] 를 한 번 더 눌러야 하는 물건인가 (영웅 이상 · 강화 +1 이상 — 기본값). */
    public boolean risky(ItemDef def, int enhanceLevel) {
        if (def == null) return false;
        Rarity r = def.rarity() == null ? Rarity.COMMON : def.rarity();
        if (r.atLeast(config.confirmRarity())) return true;
        return config.confirmEnhance() > 0 && enhanceLevel >= config.confirmEnhance();
    }

    /** 재료·층 없는 소모품의 층 (0~10). */
    static int materialFloor(ItemDef def) { return Math.max(0, Math.min(10, def.floor())); }

    /** 판매 창 '가격표' 설명 줄 (MiniMessage). */
    public List<String> tableLore() {
        Config c = config;
        return List.of(
                "<gray>재료 <dark_gray>(× 1 + " + pct(c.materialFloorBonus()) + " × 층)",
                "<white>" + row(c.materials()),
                "<gray>장비 <dark_gray>(× 1 + " + pct(c.gearFloorBonus()) + " × 층 · × 1 + " + pct(c.enhanceBonus()) + " × 강화)",
                "<white>" + row(c.gear()),
                "<gray>소모품: 핀이 파는 것은 산 값의 <white>" + pct(c.consumableShopRatio()) + "</white>, 그 밖은 재료 값",
                "<gray>핀이 파는 물건은 언제나 산 값보다 쌉니다.",
                "",
                "<#ff8a8a>팔 수 없음: <gray>시작 지급품 · 열쇠·문장 · 전직의 두루마리",
                "<gray>" + c.confirmRarity().displayName() + " 이상" + (c.confirmEnhance() > 0 ? " · 강화 +" + c.confirmEnhance() + " 이상" : "")
                        + " 은 <white>두 번</white> 눌러야 팝니다.");
    }

    private static String row(Map<Rarity, Integer> t) {
        StringBuilder sb = new StringBuilder();
        for (Rarity r : Rarity.values()) {
            if (sb.length() > 0) sb.append(" <dark_gray>·</dark_gray> ");
            sb.append("<").append(r.color()).append(">").append(r.displayName()).append("</").append(r.color()).append("> ")
                    .append(t.getOrDefault(r, 0));
        }
        return sb.append(" G").toString();
    }

    static String pct(double v) {
        double p = v * 100;
        return (Math.abs(p - Math.rint(p)) < 1e-9 ? String.valueOf((long) Math.rint(p)) : String.format(Locale.ROOT, "%.1f", p)) + "%";
    }
}
