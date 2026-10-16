package kr.labyrinth.mine;

import com.google.gson.Gson;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.ToolSpec;

/** 광산 시험 공용: 계약 mine.json · content/mine.yml 과 같은 MineDef · 계약 곡괭이 6 · jar 청사진 6. */
final class MineTestData {

    private MineTestData() {}

    private static Params mineJson;
    private static MineDef mine;
    private static Map<String, ToolSpec> pickaxes;
    private static final Map<Integer, MineBlueprint> blueprints = new LinkedHashMap<>();

    @SuppressWarnings("unchecked")
    static synchronized Params mineJson() {
        if (mineJson == null) {
            try {
                String text = Files.readString(Path.of("../tools/data/036/mine.json"), StandardCharsets.UTF_8);
                mineJson = Params.of(new Gson().fromJson(text, Map.class));
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return mineJson;
    }

    static synchronized MineDef mine() {
        if (mine == null) mine = new ContentParser().parseMine(mineJson());
        return mine;
    }

    /** 계약 곡괭이 id → ToolSpec (tier · speed · bonus — Q3 items.yml tool 과 같은 값). */
    static synchronized Map<String, ToolSpec> pickaxes() {
        if (pickaxes == null) {
            Map<String, ToolSpec> out = new LinkedHashMap<>();
            Params all = mineJson().sub("pickaxes");
            for (String id : all.keys()) {
                Params p = all.sub(id);
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("kind", ToolSpec.PICKAXE);
                m.put("tier", p.integer("tier", 0));
                m.put("speed", p.sub("speed").asMap());
                m.put("bonus", p.dbl("bonus", 0));
                out.put(id, ToolSpec.parse(Params.of(m)));
            }
            pickaxes = out;
        }
        return pickaxes;
    }

    static synchronized MineBlueprint blueprint(int n) {
        return blueprints.computeIfAbsent(n, k -> {
            try {
                return MineBlueprint.parse(Files.readString(Path.of("src/main/resources/" + MineNames.blueprintPath(k)), StandardCharsets.UTF_8));
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        });
    }

    /** 시험용 단단함 (블록마다 다르게 — 초가 단단함과 무관한지 보려고). */
    static double hardness(String block) {
        return switch (block) {
            case "minecraft:ancient_debris" -> 30.0;
            case "minecraft:deepslate_diamond_ore", "minecraft:deepslate_lapis_ore" -> 4.5;
            case "minecraft:calcite" -> 0.75;
            case "minecraft:sea_lantern", "minecraft:glowstone" -> 0.3;
            case "minecraft:magma_block" -> 0.5;
            // 0.3.6.1 보석 블록 (좀벌레 돌 = 바탕 블록 단단함 ÷ 2)
            case "minecraft:infested_stone_bricks", "minecraft:infested_mossy_stone_bricks", "minecraft:infested_chiseled_stone_bricks",
                 "minecraft:infested_cracked_stone_bricks" -> 0.75;
            case "minecraft:infested_cobblestone" -> 1.0;
            case "minecraft:infested_deepslate" -> 1.5;
            default -> 3.0;
        };
    }
}
