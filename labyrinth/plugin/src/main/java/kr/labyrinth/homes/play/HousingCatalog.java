package kr.labyrinth.homes.play;

import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 관리인 [자재] 탭 목록 (0.3.7, {@code content/housing.yml} — tools/gen_037_housing.py 생성물). 순수 (읽기는 글 → 목록).
 * <p>
 * 팔면 안 되는 것은 {@link #banReason} 가 막는다 (생성기 {@code ban_reason} 과 같은 규칙, review R5): 금속(주괴·조각·블록·광석·원석,
 * 구리는 이름에 copper 가 든 것 모두) · 녹이면 조각이 나오는 도구·갑옷 · 무기·갑옷 · 허용 목록 밖 도구 · 폭발물 · 레드스톤 장치 ·
 * 엔더·셜커 · 알 · 청금석·석영·흑요석 · 모루·마법 부여대·양조대. 사장님이 housing.yml 에 적어도 건너뛰고 로그에 남긴다.
 * 값 = 묶음 값 × {@code homes.shop_price_multiplier} (반올림, 최소 1G). 되팔기는 없다 (바닐라는 SellPrices 가 거절).
 */
public final class HousingCatalog {

    /** 한 줄: 바닐라 id (minecraft: 없이) · 한 번에 사는 개수 · 그 묶음 값 · 설명. */
    public record Entry(String id, String tab, int bundle, int price, String note) {
        public double unit() { return price / (double) bundle; }
    }

    public record Tab(String id, String name, String icon, List<Entry> items) {
        public Tab {
            items = List.copyOf(items);
        }
    }

    /** 건축 도구 허용 목록 (돌 도끼는 무기라 뺌 — review R5). */
    public static final Set<String> TOOLS = Set.of("wooden_hoe", "stone_hoe", "stone_shovel", "stone_pickaxe", "shears");

    private static final Set<String> BANNED_EXACT = Set.of(
            "tnt", "tnt_minecart", "flint_and_steel", "fire_charge", "lava_bucket", "wind_charge",
            "piston", "sticky_piston", "dispenser", "dropper", "crafter", "observer",
            "rail", "powered_rail", "detector_rail", "activator_rail",
            "minecart", "chest_minecart", "furnace_minecart", "hopper_minecart", "command_block_minecart",
            "redstone", "redstone_torch", "redstone_wall_torch", "repeater", "comparator", "redstone_block",
            "ender_pearl", "ender_eye", "ender_chest", "end_crystal", "respawn_anchor",
            "beacon", "spawner", "trial_spawner", "vault", "command_block", "chain_command_block", "repeating_command_block",
            "structure_block", "structure_void", "jigsaw", "barrier", "light",
            "anvil", "chipped_anvil", "damaged_anvil", "enchanting_table", "brewing_stand",
            "bow", "crossbow", "arrow", "trident", "mace",
            "egg", "blue_egg", "brown_egg", "turtle_egg", "sniffer_egg", "dragon_egg",
            "elytra", "gilded_blackstone", "ancient_debris", "raw_iron", "raw_gold", "raw_iron_block", "raw_gold_block",
            "iron_ingot", "iron_nugget", "iron_block", "iron_ore", "deepslate_iron_ore",
            "gold_ingot", "gold_nugget", "gold_block", "gold_ore", "deepslate_gold_ore", "nether_gold_ore");
    private static final String[] BANNED_WORDS = {"copper", "gold", "diamond", "emerald", "netherite", "lapis", "quartz", "obsidian", "shulker"};
    private static final String[] TOOL_SUFFIX = {"_pickaxe", "_shovel", "_hoe", "_axe"};
    private static final String[] WEAPON_SUFFIX = {"_sword", "_axe", "_spear"};
    private static final String[] ARMOR_SUFFIX = {"_helmet", "_chestplate", "_leggings", "_boots", "_horse_armor", "_nautilus_armor"};
    private static final String[] SMELT_METALS = {"iron_", "golden_", "copper_", "chainmail_"};

    public static final HousingCatalog EMPTY = new HousingCatalog(List.of(), 0, List.of(), 0, 0);

    private final List<Tab> tabs;
    private final int declared;
    private final List<String> problems;
    private final int banned;
    private final int unknown;

    private HousingCatalog(List<Tab> tabs, int declared, List<String> problems, int banned, int unknown) {
        this.tabs = List.copyOf(tabs);
        this.declared = declared;
        this.problems = List.copyOf(problems);
        this.banned = banned;
        this.unknown = unknown;
    }

    public List<Tab> tabs() { return tabs; }

    /** 파는 가짓수 (건너뛴 것 빼고). */
    public int size() {
        int n = 0;
        for (Tab t : tabs) n += t.items().size();
        return n;
    }

    /** 파일의 count (모르면 0). */
    public int declared() { return declared; }

    /** 금지라서 건너뛴 줄 수. */
    public int banned() { return banned; }

    /** 모르는 아이템이라 건너뛴 줄 수. */
    public int unknown() { return unknown; }

    /** 읽으며 건너뛴 줄 설명 (로그용). */
    public List<String> problems() { return problems; }

    public Entry find(String id) {
        String k = norm(id);
        for (Tab t : tabs) for (Entry e : t.items()) if (e.id().equals(k)) return e;
        return null;
    }

    /** 배율을 곱한 묶음 값 (반올림, 최소 1G). 배율은 HomesConfig 가 0.1 이상으로 자른다 (R16). */
    public static long price(Entry e, double multiplier) {
        double m = Double.isNaN(multiplier) ? 1 : Math.max(0.1, multiplier);
        return Math.max(1, Math.round(e.price() * m));
    }

    /** n 묶음 중 given 개만 줬을 때 돌려줄 골드 (못 준 몫, 내림 — 낸 값을 넘지 않음). */
    public static long refund(long paid, int bundles, int bundle, int given) {
        int total = Math.max(1, bundles * bundle);
        if (given >= total) return 0;
        if (given <= 0) return paid;
        long kept = (paid * given + total - 1) / total; // 준 몫은 올림해 받음
        return Math.max(0, paid - kept);
    }

    // ── 금지 규칙 (생성기와 같음) ─────────────────────────────────────────

    /** 팔면 안 되는 이유 (팔아도 되면 null). */
    public static String banReason(String rawId) {
        String i = norm(rawId);
        if (BANNED_EXACT.contains(i)) return "금지 목록";
        if (startsWithAny(i, SMELT_METALS) && (endsWithAny(i, TOOL_SUFFIX) || endsWithAny(i, WEAPON_SUFFIX) || endsWithAny(i, ARMOR_SUFFIX))) {
            return "녹이면 조각이 나옴";
        }
        for (String w : BANNED_WORDS) if (i.contains(w)) return "금지 재료 (" + w + ")";
        if (endsWithAny(i, ARMOR_SUFFIX) || i.equals("turtle_helmet") || i.equals("wolf_armor")) return "갑옷";
        if (i.endsWith("_sword") || i.endsWith("_spear") || i.endsWith("_arrow")) return "무기";
        if (endsWithAny(i, TOOL_SUFFIX) || Set.of("shears", "brush", "fishing_rod", "carrot_on_a_stick", "warped_fungus_on_a_stick").contains(i)) {
            if (TOOLS.contains(i)) return null;
            return i.endsWith("_axe") ? "무기" : "도구 (허용 목록 밖)";
        }
        if (i.endsWith("_spawn_egg")) return "알";
        if (i.endsWith("_bucket") && !i.equals("water_bucket")) return "양동이 (물 양동이만)";
        return null;
    }

    /** 녹이면 조각(쇠·금·구리 조각)이 나오는 도구·갑옷인가 (HousingCatalogTest 가 보는 규칙). */
    public static boolean smeltsToNuggets(String rawId) {
        String i = norm(rawId);
        return startsWithAny(i, SMELT_METALS) && (endsWithAny(i, TOOL_SUFFIX) || endsWithAny(i, WEAPON_SUFFIX) || endsWithAny(i, ARMOR_SUFFIX));
    }

    // ── 읽기 ─────────────────────────────────────────────────────────────

    /** housing.yml 글 → 목록. knownItem = 그 id 가 이 서버에 있는 아이템인가 (모르면 건너뜀). */
    public static HousingCatalog parse(String yamlText, Predicate<String> knownItem) {
        YamlConfiguration y = new YamlConfiguration();
        try {
            y.loadFromString(yamlText == null ? "" : yamlText);
        } catch (Exception e) {
            return new HousingCatalog(List.of(), 0, List.of("housing.yml 읽기 실패: " + e.getMessage()), 0, 0);
        }
        List<String> problems = new ArrayList<>();
        List<Tab> tabs = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        int banned = 0, unknown = 0;
        for (Map<?, ?> tm : y.getMapList("tabs")) {
            String tid = str(tm.get("id"), "tab" + tabs.size());
            String name = str(tm.get("name"), tid);
            String icon = norm(str(tm.get("icon"), "chest"));
            List<Entry> items = new ArrayList<>();
            Object raw = tm.get("items");
            if (raw instanceof List<?> list) {
                for (Object o : list) {
                    if (!(o instanceof Map<?, ?> im)) continue;
                    String id = norm(str(im.get("id"), ""));
                    if (id.isEmpty()) continue;
                    String why = banReason(id);
                    if (why != null) {
                        banned++;
                        problems.add(id + ": 팔 수 없는 아이템 (" + why + ") — 건너뜀");
                        continue;
                    }
                    if (knownItem != null && !knownItem.test(id)) {
                        unknown++;
                        problems.add(id + ": 모르는 아이템 — 건너뜀");
                        continue;
                    }
                    if (!seen.add(id)) {
                        problems.add(id + ": 두 번 나옴 — 뒤의 것은 건너뜀");
                        continue;
                    }
                    int bundle = Math.max(1, Math.min(64, num(im.get("bundle"), 1)));
                    int price = Math.max(1, num(im.get("price"), 1));
                    items.add(new Entry(id, tid, bundle, price, str(im.get("note"), "")));
                }
            }
            tabs.add(new Tab(tid, name, icon, items));
        }
        return new HousingCatalog(tabs, y.getInt("count", 0), problems, banned, unknown);
    }

    /** 데이터 폴더 content/housing.yml (없으면 jar 기본). */
    public static HousingCatalog load(File dataFolder, java.util.function.Function<String, InputStream> resource, Predicate<String> knownItem) {
        String text = null;
        try {
            File f = new File(new File(dataFolder, "content"), "housing.yml");
            if (f.isFile()) text = Files.readString(f.toPath(), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            // jar 기본으로
        }
        if (text == null && resource != null) {
            try (InputStream in = resource.apply("content/housing.yml")) {
                if (in != null) text = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            } catch (Exception ignored) {
                // 없음
            }
        }
        return text == null ? EMPTY : parse(text, knownItem);
    }

    static String norm(String id) {
        if (id == null) return "";
        String k = id.trim().toLowerCase(Locale.ROOT);
        return k.startsWith("minecraft:") ? k.substring("minecraft:".length()) : k;
    }

    private static String str(Object o, String def) { return o == null ? def : String.valueOf(o); }

    private static int num(Object o, int def) {
        if (o instanceof Number n) return n.intValue();
        try {
            return o == null ? def : Integer.parseInt(String.valueOf(o).trim());
        } catch (NumberFormatException e) {
            return def;
        }
    }

    private static boolean startsWithAny(String s, String[] p) {
        for (String x : p) if (s.startsWith(x)) return true;
        return false;
    }

    private static boolean endsWithAny(String s, String[] p) {
        for (String x : p) if (s.endsWith(x)) return true;
        return false;
    }
}
