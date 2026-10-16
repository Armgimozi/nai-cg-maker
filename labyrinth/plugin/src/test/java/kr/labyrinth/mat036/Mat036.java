package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.Gson;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;

/** 0.3.6 Q3 시험 공용 — 번들 content + 계약 JSON (tools/data/036). */
final class Mat036 {

    static final Path CONTENT = Path.of("src/main/resources/content");
    static final List<String> METALS = List.of("copper", "iron", "silver", "gold", "mithril", "orichalcum");
    static final List<String> GEMS = List.of("quartz", "garnet", "moonstone", "topaz", "sapphire", "dragonblood_stone");
    static final List<String> RETIRED = List.of("rusted_iron", "slag_ingot", "ember_shard", "rime_crystal", "amethyst_shard",
            "prism_dust", "brass_gear", "mainspring", "cinder_hide");

    private static Content content;
    private static final Map<String, Params> json = new java.util.HashMap<>();

    private Mat036() {}

    static synchronized Content content() {
        if (content == null) {
            ContentLoader.Result r = ContentLoader.load(CONTENT);
            assertTrue(r.problems().isEmpty(), () -> "콘텐츠 문제: " + r.problems());
            content = r.content();
        }
        return content;
    }

    @SuppressWarnings("unchecked")
    static synchronized Params json(String name) {
        return json.computeIfAbsent(name, n -> {
            try {
                String text = Files.readString(Path.of("../tools/data/036/" + n), StandardCharsets.UTF_8);
                return Params.of(new Gson().fromJson(text, Map.class));
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        });
    }

    static String text(String file) {
        try {
            return Files.readString(CONTENT.resolve(file), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** 테이블 하나 펼치기 (하위 테이블 · one_of · pick 포함). */
    static Set<String> expand(Content c, String tableId, Set<String> seen) {
        Set<String> out = new HashSet<>();
        LootTable t = c.lootTable(tableId);
        if (t == null || !seen.add(tableId)) return out;
        List<LootTable.Entry> all = new java.util.ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> out.add(e.item());
                case ONE_OF -> out.addAll(e.oneOf());
                case TABLE -> out.addAll(expand(c, e.table(), new HashSet<>(seen)));
                case PICK -> { for (LootTable.Pick pk : e.pick()) out.addAll(expand(c, pk.table(), new HashSet<>(seen))); }
                case RARITY_POOL -> { }
            }
        }
        return out;
    }

    /** 테이블 자기 칸만 (하위 테이블은 펼치지 않음). */
    static Set<String> own(Content c, String tableId) {
        Set<String> out = new HashSet<>();
        LootTable t = c.lootTable(tableId);
        if (t == null) return out;
        List<LootTable.Entry> all = new java.util.ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            if (e.kind() == LootTable.Kind.ITEM) out.add(e.item());
            else if (e.kind() == LootTable.Kind.ONE_OF) out.addAll(e.oneOf());
        }
        return out;
    }
}
