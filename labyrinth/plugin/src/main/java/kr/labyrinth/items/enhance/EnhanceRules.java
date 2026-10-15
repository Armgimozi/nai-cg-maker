package kr.labyrinth.items.enhance;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.EnhanceDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.items.ItemRolls;
import org.bukkit.configuration.ConfigurationSection;

/**
 * 장비 강화 규칙 (GDD §11.13) — 순수 로직, 단위 테스트 대상. 수치 원본은 config.yml {@code enhance:}.
 * <ul>
 *   <li>대상: 미궁 무기·방어구·방패 (장신구·바닐라 장비 제외). 단계 0 ~ max_level(기본 10).</li>
 *   <li>확률은 <b>목표 단계</b> 기준(chances[목표−1]). 기본 +1~+4 확정, +5 90% … +10 20%.</li>
 *   <li>실패: 재료(골드·강화석·장비 재료)는 사라진다. 현재 단계 ≥ downgrade_from(기본 7)이면 한 단계 하락 —
 *       보호 주문서를 쓰면 하락 대신 주문서만 사라진다. 파괴는 없다.</li>
 *   <li>능력치: 기본 굴림값 × (1 + stat_bonus[단계−1]) — 누적 보너스 목록, 높은 단계일수록 한 단계 상승폭이 커진다
 *       (기본 +1 3% … +10 72%). 무기는 weapon_stats, 방어구·방패는 armor_stats 키만 (정수 스탯은 늘어난 몫을 올림).</li>
 *   <li>골드 = gold_base × (요구 레벨 + gold_level_offset) × 희귀도 배율 × 단계 배율. 강화석 = 장비 층 구간별 1종, 개수는 단계별.</li>
 *   <li>장비 재료 = content/enhance.yml (장비마다 다름, 구간 low/mid/high). 항목이 없는 장비는 강화석·골드만.</li>
 * </ul>
 */
public final class EnhanceRules {

    /** 강화 결과. FAIL = 재료만 잃음, DOWNGRADE = 한 단계 하락, PROTECTED = 하락할 실패를 주문서가 막음. */
    public enum Outcome { SUCCESS, FAIL, DOWNGRADE, PROTECTED }

    /** 장비 층 구간 → 강화석 (maxFloor 이하 장비가 이 돌을 쓴다). */
    public record Stone(String item, int maxFloor) {}

    /**
     * config.yml enhance 스냅샷. 리스트는 목표 단계 1..maxLevel 순 (모자라면 마지막 값으로 채움).
     * statBonus = 단계별 <b>누적</b> 능력치 보너스 (+1 0.03 … +10 0.72 → 배율 1 + 값).
     */
    public record Config(boolean enabled, int maxLevel, List<Double> chances, int downgradeFrom, List<Double> statBonus,
                         Set<String> weaponStats, Set<String> armorStats, double goldBase, int goldLevelOffset,
                         Map<Rarity, Double> goldRarity, List<Double> goldSteps, List<Integer> stoneCounts,
                         List<Stone> stones, String protectionItem, int broadcastFrom, int glintFrom, int glowInterval,
                         boolean craftDiscount) {

        /** 설정 파일이 없거나 비었을 때의 기본값 (config.yml 기본값과 같다). */
        public static final Config DEFAULT = new Config(true, 10,
                List.of(1.0, 1.0, 1.0, 1.0, 0.90, 0.80, 0.65, 0.50, 0.35, 0.20), 7, defaultStatBonus(),
                Set.of("damage"), Set.of("defense", "hp"), 3.0, 4, defaultRarity(),
                List.of(1.0, 1.2, 1.4, 1.7, 2.0, 2.4, 2.9, 3.5, 4.2, 5.0), List.of(1, 1, 1, 1, 2, 2, 2, 3, 3, 4),
                List.of(new Stone("lesser_enhance_stone", 3), new Stone("greater_enhance_stone", 7),
                        new Stone("supreme_enhance_stone", 10)),
                "enhance_protection_scroll", 8, 7, 10, true);

        /** 기본 누적 보너스: 한 단계 상승폭 3·3·4·4·5·6·8·10·13·16 % → +10 = ×1.72. */
        public static List<Double> defaultStatBonus() {
            return List.of(0.03, 0.06, 0.10, 0.14, 0.19, 0.25, 0.33, 0.43, 0.56, 0.72);
        }

        private static Map<Rarity, Double> defaultRarity() {
            Map<Rarity, Double> m = new EnumMap<>(Rarity.class);
            m.put(Rarity.COMMON, 1.0);
            m.put(Rarity.UNCOMMON, 1.15);
            m.put(Rarity.RARE, 1.35);
            m.put(Rarity.EPIC, 1.6);
            m.put(Rarity.LEGENDARY, 2.0);
            m.put(Rarity.MYTHIC, 2.6);
            return Map.copyOf(m);
        }

        /**
         * config.yml 의 {@code enhance:} 섹션 (null 이면 기본값). 빠진 키는 기본값.
         * 예전 키 {@code stat_per_level}(단계마다 같은 %)은 읽지 않는다 — {@code stat_bonus} 가 없으면 기본 곡선.
         */
        public static Config from(ConfigurationSection s) {
            if (s == null) return DEFAULT;
            Config d = DEFAULT;
            int max = Math.max(1, Math.min(20, s.getInt("max_level", d.maxLevel)));
            List<Double> chances = doubles(s, "chances", d.chances);
            List<Double> steps = doubles(s, "gold_steps", d.goldSteps);
            List<Double> bonus = cumulative(doubles(s, "stat_bonus", d.statBonus));
            List<Integer> counts = s.isList("stone_counts") ? s.getIntegerList("stone_counts") : d.stoneCounts;
            if (counts.isEmpty()) counts = d.stoneCounts;
            Map<Rarity, Double> rar = new EnumMap<>(Rarity.class);
            rar.putAll(d.goldRarity);
            ConfigurationSection rs = s.getConfigurationSection("gold_rarity");
            if (rs != null) {
                for (String k : rs.getKeys(false)) {
                    Rarity r = Rarity.byId(k);
                    if (r != null) rar.put(r, Math.max(0, rs.getDouble(k)));
                }
            }
            List<Stone> stones = new ArrayList<>();
            for (Map<?, ?> m : s.getMapList("stones")) {
                Object item = m.get("item");
                Object mf = m.get("max_floor");
                if (item == null) continue;
                int maxFloor = mf instanceof Number n ? n.intValue() : 10;
                stones.add(new Stone(String.valueOf(item), maxFloor));
            }
            if (stones.isEmpty()) stones = new ArrayList<>(d.stones);
            stones.sort((a, b) -> Integer.compare(a.maxFloor(), b.maxFloor()));
            return new Config(s.getBoolean("enabled", d.enabled), max, List.copyOf(chances),
                    Math.max(0, s.getInt("downgrade_from", d.downgradeFrom)), bonus,
                    keys(s, "weapon_stats", d.weaponStats), keys(s, "armor_stats", d.armorStats),
                    Math.max(0, s.getDouble("gold_base", d.goldBase)), s.getInt("gold_level_offset", d.goldLevelOffset),
                    Map.copyOf(rar), List.copyOf(steps), List.copyOf(counts), List.copyOf(stones),
                    s.getString("protection_item", d.protectionItem), s.getInt("broadcast_from", d.broadcastFrom),
                    s.getInt("glint_from", d.glintFrom), Math.max(0, s.getInt("glow_interval", d.glowInterval)),
                    s.getBoolean("craft_discount", d.craftDiscount));
        }

        private static List<Double> doubles(ConfigurationSection s, String key, List<Double> def) {
            if (!s.isList(key)) return def;
            List<Double> out = new ArrayList<>();
            for (Object o : s.getList(key, List.of())) if (o instanceof Number n) out.add(n.doubleValue());
            return out.isEmpty() ? def : out;
        }

        /** 누적 보너스는 줄지 않게 (음수·역전은 앞 값으로). */
        private static List<Double> cumulative(List<Double> in) {
            List<Double> out = new ArrayList<>();
            double prev = 0;
            for (double v : in) {
                prev = Math.max(prev, v);
                out.add(prev);
            }
            return List.copyOf(out);
        }

        private static Set<String> keys(ConfigurationSection s, String key, Set<String> def) {
            if (!s.isList(key)) return def;
            return Set.copyOf(new LinkedHashSet<>(s.getStringList(key)));
        }
    }

    private final Config c;

    public EnhanceRules(Config config) { this.c = config == null ? Config.DEFAULT : config; }

    public Config config() { return c; }

    public int maxLevel() { return c.maxLevel(); }

    private static <T> T at(List<T> list, int target, T fallback) {
        if (list == null || list.isEmpty()) return fallback;
        int i = Math.max(0, Math.min(list.size() - 1, target - 1));
        return list.get(i);
    }

    // ── 대상 ──────────────────────────────────────────────────────────────

    /** 강화할 수 있는 장비인가 — 미궁 무기·방어구·방패만 (장신구 제외, 바닐라 아이템은 정의가 없어 null). */
    public static boolean enhanceable(ItemDef def) {
        return def != null && (def.type() == ItemType.WEAPON || def.type() == ItemType.ARMOR);
    }

    /** 이 장비에서 강화 배율이 곱해지는 스탯 키. */
    public Set<String> scaledKeys(ItemDef def) {
        if (!enhanceable(def)) return Set.of();
        return def.isWeapon() ? c.weaponStats() : c.armorStats();
    }

    // ── 확률 · 결과 ───────────────────────────────────────────────────────

    /** 목표 단계(현재 + 1)의 성공 확률 0~1. 최대 단계 이상이면 0. */
    public double chance(int target) {
        if (target < 1 || target > c.maxLevel()) return 0;
        return Math.max(0, Math.min(1, at(c.chances(), target, 0.0)));
    }

    /** 현재 단계에서 실패하면 하락하는가. */
    public boolean downgradesOnFail(int level) {
        return c.downgradeFrom() > 0 && level >= c.downgradeFrom() && level > 0;
    }

    /**
     * 한 번 강화 판정.
     * @param level   현재 단계
     * @param roll    [0, 1) 난수 — roll &lt; 확률 이면 성공
     * @param protect 보호 주문서를 쓰는가 (가지고 있고 켜 둠)
     */
    public Outcome resolve(int level, double roll, boolean protect) {
        int target = level + 1;
        if (roll < chance(target)) return Outcome.SUCCESS;
        if (!downgradesOnFail(level)) return Outcome.FAIL;
        return protect ? Outcome.PROTECTED : Outcome.DOWNGRADE;
    }

    /** 결과 뒤 단계. */
    public static int levelAfter(int level, Outcome o) {
        return switch (o) {
            case SUCCESS -> level + 1;
            case DOWNGRADE -> Math.max(0, level - 1);
            case FAIL, PROTECTED -> level;
        };
    }

    /** 보호 주문서가 사라지는 결과인가 (하락을 막았을 때만). */
    public static boolean consumesProtection(Outcome o) { return o == Outcome.PROTECTED; }

    // ── 비용 ──────────────────────────────────────────────────────────────

    /** 목표 단계로 가는 강화석 개수. */
    public int stoneCount(int target) {
        return Math.max(0, at(c.stoneCounts(), target, 1));
    }

    /** 장비 층 (items.yml floor, 없으면 요구 레벨로 추정: 5레벨당 1층). */
    public static int gearFloor(ItemDef def) {
        if (def.floor() > 0) return def.floor();
        return Math.max(1, Math.min(10, (int) Math.ceil(Math.max(1, def.levelReq()) / 5.0)));
    }

    /** 이 장비가 쓰는 강화석 id (층 구간). 구간을 넘으면 마지막 돌. */
    public String stoneFor(ItemDef def) {
        int f = gearFloor(def);
        for (Stone s : c.stones()) if (f <= s.maxFloor()) return s.item();
        return c.stones().isEmpty() ? null : c.stones().get(c.stones().size() - 1).item();
    }

    /** 목표 단계로 가는 골드 (할인 전). */
    public long baseGold(ItemDef def, int target) {
        double rar = c.goldRarity().getOrDefault(def.rarity(), 1.0);
        double v = c.goldBase() * Math.max(1, def.levelReq() + c.goldLevelOffset()) * rar * at(c.goldSteps(), target, 1.0);
        return Math.max(1, Math.round(v));
    }

    /** 할인(craft_discount, 상한 30%) 적용 골드. */
    public long gold(ItemDef def, int target, double discount) {
        long base = baseGold(def, target);
        if (!c.craftDiscount()) return base;
        double d = Math.max(0, Math.min(0.30, discount));
        return Math.max(1, Math.round(base * (1.0 - d)));
    }

    /**
     * 목표 단계 한 번 시도 비용: 골드(할인 적용) + 강화석 + 그 장비의 재료(enhance.yml, 없으면 강화석만).
     * 같은 id 는 한 줄로 합친다(강화석이 재료 목록에 또 있어도). 강화석 줄이 맨 앞.
     */
    public EnhanceCost cost(ItemDef def, int target, double discount, EnhanceDef table) {
        Map<String, EnhanceCost.Line> lines = new LinkedHashMap<>();
        String stone = stoneFor(def);
        int stones = stoneCount(target);
        if (stone != null && stones > 0) lines.put(stone, new EnhanceCost.Line(stone, stones, true));
        if (table != null) {
            for (EnhanceDef.Cost m : table.costs(def.id(), target)) {
                lines.merge(m.item(), new EnhanceCost.Line(m.item(), m.amount(), false),
                        (a, b) -> new EnhanceCost.Line(a.item(), a.amount() + b.amount(), a.stone()));
            }
        }
        return new EnhanceCost(gold(def, target, discount), List.copyOf(lines.values()));
    }

    // ── 능력치 ────────────────────────────────────────────────────────────

    /** 단계 배율 = 1 + 누적 보너스 (기본 +1 ×1.03 · +5 ×1.19 · +8 ×1.43 · +10 ×1.72). 0 이하 = 1, 최대 단계로 자름. */
    public double multiplier(int level) {
        int lv = Math.max(0, Math.min(c.maxLevel(), level));
        if (lv == 0) return 1.0;
        return 1.0 + at(c.statBonus(), lv, 0.0);
    }

    /** level → level+1 한 단계에서 늘어나는 배율 몫 (기본 +9 → +10 = 0.16). 최대 단계면 0. */
    public double stepGain(int level) {
        if (level >= c.maxLevel()) return 0;
        return multiplier(level + 1) - multiplier(level);
    }

    /**
     * 기본 굴림값에 강화 배율을 곱한 스탯 (대상 키만). 단계 0 이면 그대로.
     * 정수 키(피해·방어·HP)는 늘어난 몫을 <b>올림</b> — 피해 7 짜리 장비도 +1 부터 눈에 보이게 +1.
     */
    public Map<String, Double> apply(ItemDef def, Map<String, Double> base, int level) {
        if (level <= 0 || base.isEmpty() || !enhanceable(def)) return base;
        Set<String> keys = scaledKeys(def);
        double m = multiplier(level);
        Map<String, Double> out = new LinkedHashMap<>(base);
        for (String k : keys) {
            Double v = out.get(k);
            if (v == null || v <= 0) continue;
            double plus = v * (m - 1.0);
            if (ItemRolls.INT_KEYS.contains(k)) plus = Math.ceil(plus - 1e-9);
            out.put(k, ItemRolls.round(k, v + plus));
        }
        return out;
    }

    /** 강화로 늘어난 몫 (키 → 증가량). 툴팁 "(+12)" 표시용. */
    public Map<String, Double> bonus(ItemDef def, Map<String, Double> base, int level) {
        Map<String, Double> out = new LinkedHashMap<>();
        if (level <= 0) return out;
        Map<String, Double> eff = apply(def, base, level);
        for (String k : scaledKeys(def)) {
            Double b = base.get(k);
            Double e = eff.get(k);
            if (b != null && e != null && Math.abs(e - b) > 1e-9) out.put(k, ItemRolls.round(k, e - b));
        }
        return out;
    }

    // ── 표시 ──────────────────────────────────────────────────────────────

    /** 반짝임(인챈트 광택)·이름 색이 붙는 단계인가. */
    public boolean shines(int level) { return level > 0 && level >= c.glintFrom(); }

    /** 최대 단계(특별한 빛)인가. */
    public boolean radiant(int level) { return level >= c.maxLevel(); }

    /** 이름 앞 "+7 " 접두어 (MiniMessage, 0 이면 빈 문자열). */
    public String namePrefix(int level) {
        if (level <= 0) return "";
        String t = "+" + level + " ";
        if (radiant(level)) return "<gradient:#ff8a3d:#ffd36b:#fff4d6><b>" + t + "</b></gradient>";
        if (shines(level)) return "<#ffd36b><b>" + t + "</b></#ffd36b>";
        return "<white>" + t + "</white>";
    }

    /** 이름 본문 색 (MiniMessage 여는 태그 + 닫는 태그). +7 부터 희귀도 색 → 금빛 그라데이션. */
    public String[] nameColor(Rarity r, int level) {
        if (radiant(level)) return new String[] {"<gradient:" + r.color() + ":#ffd36b:#fff4d6>", "</gradient>"};
        if (shines(level)) return new String[] {"<gradient:" + r.color() + ":#ffe9a8>", "</gradient>"};
        return new String[] {"<" + r.color() + ">", "</" + r.color() + ">"};
    }

    /** 확률 표시 ("65%", "100%"). */
    public static String pct(double p) {
        double v = p * 100;
        if (Math.abs(v - Math.rint(v)) < 1e-9) return (long) Math.rint(v) + "%";
        return String.format(Locale.ROOT, "%.1f%%", v);
    }
}
