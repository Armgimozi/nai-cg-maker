package kr.labyrinth.items.blueprint;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 신화 도안 시험용 콘텐츠 (0.3.7 myth-037).
 * <p>
 * 번들 콘텐츠에 신화 레시피·{@code blueprint_of} 가 이미 있으면(데이터 묶음 D 가 들어온 뒤) 그대로 쓴다. 없으면 같은 원시 YAML 을
 * 읽어 명세(final_spec §4·§5) 꼴대로 덧붙인다 — 신화 무기 sources [boss, craft], 레시피(id = 결과 id), 10층 보스 one_of 0.08 ·
 * 9·8층 보스 0.015 · 0.012, blueprint_of 보스 0.05 / 0.006 · 특별 시련 0.10 / 0.02 · 금고 0.008 / 0.001. 그래서 두 경우 모두
 * 같은 시험이 돈다.
 */
final class MythicFixture {

    static final Path CONTENT = Path.of("src/main/resources/content");

    /** 신화마다 8·9층 중 나오는 층 (명세 home_floor — 10층만인 것은 없음). 새 신화는 D 데이터가 들어온 뒤에만 있다. */
    static final Map<String, Integer> HOME = Map.ofEntries(
            Map.entry("celestial_oathkeeper", 9), Map.entry("mountainheart_maul", 8),
            Map.entry("bloodmoon_reaver", 8), Map.entry("hightide_scythe", 9),
            Map.entry("tempest_bow", 9), Map.entry("comet_longbow", 8),
            Map.entry("wisp_lantern", 8),
            Map.entry("seraph_scepter", 8), Map.entry("daybreak_bell", 9),
            Map.entry("eclipse_blade", 8), Map.entry("waning_moon_sickle", 9));

    private static Content cached;
    private static boolean real;

    private MythicFixture() {}

    /** 신화 레시피·blueprint_of 가 있는 콘텐츠. */
    static synchronized Content content() {
        if (cached == null) cached = build();
        return cached;
    }

    /** 번들 콘텐츠를 그대로 쓰는가 (D 데이터가 들어왔다). */
    static boolean isReal() {
        content();
        return real;
    }

    /** 신화 무기 id (items.yml 순서). */
    static List<String> mythicWeapons(Content c) {
        List<String> out = new ArrayList<>();
        for (ItemDef d : c.items().values()) if (d.isWeapon() && d.rarity() == Rarity.MYTHIC) out.add(d.id());
        return out;
    }

    static boolean hasBlueprintOf(Content c) {
        for (LootTable t : c.lootTables().values()) {
            for (LootTable.Entry e : t.entries()) if (e.kind() == LootTable.Kind.BLUEPRINT_OF) return true;
            for (LootTable.Entry e : t.guaranteed()) if (e.kind() == LootTable.Kind.BLUEPRINT_OF) return true;
        }
        return false;
    }

    private static Content build() {
        Map<String, Map<String, Object>> raw = raw();
        Content bundled = parse(raw);
        if (hasBlueprintOf(bundled)) {
            real = true;
            return bundled;
        }
        real = false;
        List<String> all = mythicWeapons(bundled);
        Map<String, Object> items = sub(raw.get("items.yml"), "items");
        Map<String, Object> recipes = sub(raw.computeIfAbsent("recipes.yml", k -> new LinkedHashMap<>()), "recipes");
        for (String id : all) {
            sub(items, id).put("sources", new ArrayList<>(List.of("boss", "craft")));
            boolean melee = "melee".equals(String.valueOf(sub(sub(items, id), "attack").get("style")));
            Map<String, Object> mats = new LinkedHashMap<>();
            mats.put("abyssal_heart_fragment", 50);
            mats.put("gatekeeper_rune", 60);
            mats.put("primordial_essence", 80);
            mats.put("abyss_ichor", 200);
            mats.put(melee ? "abyss_scale" : "sculk_tendril", 150);
            mats.put("orichalcum_ingot", 60);
            mats.put("dragonblood_stone", 10);
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("result", id);
            r.put("category", "weapon");
            r.put("station", "blacksmith");
            r.put("level_req", 48);
            r.put("gold", 400000);
            r.put("materials", mats);
            recipes.put(id, r);
        }
        List<String> f9 = new ArrayList<>(), f8 = new ArrayList<>();
        for (String id : all) {
            Integer h = HOME.get(id);
            if (h != null && h == 9) f9.add(id);
            if (h != null && h == 8) f8.add(id);
        }
        Map<String, Object> tables = sub(raw.get("loot.yml"), "tables");
        // 10층: 지금 신화 one_of 줄을 모두 0.08 로 바꾼다
        List<Object> e10 = entries(tables, "floor10_boss");
        e10.removeIf(o -> o instanceof Map<?, ?> m && m.get("one_of") instanceof List<?> l && l.stream().anyMatch(all::contains));
        e10.add(line("one_of", all, 0.08));
        e10.add(line("blueprint_of", all, 0.05));
        entries(tables, "floor09_boss").add(line("one_of", f9, 0.015));
        entries(tables, "floor09_boss").add(line("blueprint_of", f9, 0.006));
        entries(tables, "floor08_boss").add(line("one_of", f8, 0.012));
        entries(tables, "floor08_boss").add(line("blueprint_of", f8, 0.006));
        entries(tables, "special_trial_f10").add(line("blueprint_of", all, 0.10));
        entries(tables, "special_trial_f09").add(line("blueprint_of", f9, 0.02));
        entries(tables, "special_trial_f08").add(line("blueprint_of", f8, 0.02));
        entries(tables, "hoard_f10").add(line("blueprint_of", all, 0.008));
        entries(tables, "hoard_f09").add(line("blueprint_of", f9, 0.001));
        entries(tables, "hoard_f08").add(line("blueprint_of", f8, 0.001));
        return parse(raw);
    }

    /** 번들 content/*.yml 원시 트리 (고칠 수 있는 Map/List). */
    static Map<String, Map<String, Object>> raw() {
        Map<String, Map<String, Object>> raw = new LinkedHashMap<>();
        for (String file : ContentParser.FILES) {
            Path p = CONTENT.resolve(file);
            if (!Files.exists(p)) continue;
            try {
                YamlConfiguration yc = new YamlConfiguration();
                yc.loadFromString(Files.readString(p, StandardCharsets.UTF_8));
                raw.put(file, ContentLoader.toPlain(yc));
            } catch (IOException | org.bukkit.configuration.InvalidConfigurationException e) {
                throw new IllegalStateException(file, e);
            }
        }
        return raw;
    }

    static Content parse(Map<String, Map<String, Object>> raw) {
        ContentParser parser = new ContentParser();
        Content c = parser.parse(raw);
        if (!parser.problems().isEmpty()) throw new IllegalStateException(String.join("\n", parser.problems()));
        return c;
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> sub(Map<String, Object> m, String key) {
        return (Map<String, Object>) m.computeIfAbsent(key, k -> new LinkedHashMap<>());
    }

    @SuppressWarnings("unchecked")
    static List<Object> entries(Map<String, Object> tables, String table) {
        Map<String, Object> t = sub(tables, table);
        Object e = t.get("entries");
        if (!(e instanceof List<?>)) {
            e = new ArrayList<>();
            t.put("entries", e);
        }
        return (List<Object>) e;
    }

    static Map<String, Object> line(String key, List<String> ids, double chance) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(key, new ArrayList<>(ids));
        m.put("chance", chance);
        return m;
    }
}
