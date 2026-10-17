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
 * 번들 콘텐츠를 그대로 쓴다 — 신화 레시피·{@code blueprint_of} 는 tools/gen_037_mythic.py 가 넣는다 (CR37: 옛 6 = 넬카르 한 자루마다
 * 20% + 대장간, 새 6 = 대장간만, 도안은 8·9·10층 보스 · 특별 시련 · 금고·미믹). 데이터 묶음 D 가 들어오기 전에 쓰던 명세 꼴 덧붙이기는 뺐다
 * (옛 숫자를 시험이 따로 들고 있으면 데이터와 어긋난다). {@code blueprint_of} 가 없으면 바로 멈춘다.
 */
final class MythicFixture {

    static final Path CONTENT = Path.of("src/main/resources/content");

    private static Content cached;

    private MythicFixture() {}

    /** 신화 레시피·blueprint_of 가 있는 콘텐츠 (번들). */
    static synchronized Content content() {
        if (cached == null) {
            Content bundled = parse(raw());
            if (!hasBlueprintOf(bundled)) throw new IllegalStateException("번들 loot.yml 에 blueprint_of 가 없음 — gen_035_content.py 를 돌릴 것");
            cached = bundled;
        }
        return cached;
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
}
