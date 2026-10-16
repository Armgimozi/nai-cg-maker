package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.Gson;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.ToolSpec;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * Q0 계약 (tools/data/036/mine.json · materials.json) 을 Java 뼈대가 그대로 읽는가 — MineDef·ToolSpec·MineNames 가 계약과 같은 모양·이름인지.
 * 계약을 고치면 이 시험이 Java 쪽도 맞추라고 알린다.
 */
class MineContractTest {

    static Params mineJson;
    static Params matJson;
    static MineDef mine;
    static List<String> problems;

    @SuppressWarnings("unchecked")
    static Params read(String name) throws IOException {
        String text = Files.readString(Path.of("../tools/data/036/" + name), StandardCharsets.UTF_8);
        return Params.of(new Gson().fromJson(text, Map.class));
    }

    @BeforeAll
    static void load() throws IOException {
        mineJson = read("mine.json");
        matJson = read("materials.json");
        ContentParser p = new ContentParser();
        mine = p.parseMine(mineJson);
        problems = p.problems();
    }

    @Test
    void parsesSixMixedLevelsWithoutProblems() {
        assertTrue(problems.isEmpty(), () -> String.join("\n", problems));
        assertEquals(6, mine.levels().size());
        assertEquals(6, mine.ores().size());
        assertEquals(6, mine.gems().size());
        for (int n = 1; n <= 6; n++) {
            MineDef.Level l = mine.level(n);
            assertNotNull(l);
            assertTrue(l.oreWeights().size() >= 3, "섞인 층: " + l.id());
            assertEquals(100, l.oreWeights().values().stream().mapToInt(Integer::intValue).sum(), l.id());
            assertFalse(l.name().matches(".*\\d.*"), "층 이름에 숫자 없음: " + l.name());
            assertEquals(6, l.box().size());
            assertEquals(2, l.biomeY().size());
        }
        assertTrue(mine.level(1).office(), "관리소 = 맨 위층 승강기 홀");
        assertEquals(6, mine.level(6).oreWeights().size(), "가장 깊은 층에 모든 광석");
    }

    @Test
    void blocksAreUniquePerOreAndGem() {
        Set<String> seen = new HashSet<>();
        for (MineDef.Node n : mine.ores().values()) assertTrue(seen.add(n.block()), n.id());
        for (MineDef.Node n : mine.gems().values()) assertTrue(seen.add(n.block()), n.id());
        assertEquals(12, seen.size());
        for (MineDef.Node n : mine.ores().values()) assertEquals(n.id(), mine.byBlock(n.block()).id());
        assertNull(mine.byBlock("minecraft:redstone_ore"));
        for (MineDef.Level l : mine.levels()) assertNull(mine.byBlock(l.depletedBlock()), "빈 광맥 블록 ≠ 광석: " + l.id());
    }

    @Test
    void pickaxesFollowTierRuleWithoutLevelGate() {
        Map<String, Params> items = matJson.sub("items").children();
        int prevTier = 0;
        for (String id : List.of("copper_pickaxe", "iron_pickaxe", "silver_pickaxe", "gold_pickaxe", "mithril_pickaxe", "orichalcum_pickaxe")) {
            Params it = items.get(id);
            assertNotNull(it, id);
            assertEquals("tool", it.str("type"));
            assertFalse(it.has("level_req"), "레벨 조건 없음: " + id);
            ToolSpec t = ToolSpec.parse(it.sub("tool"));
            assertNotNull(t);
            assertEquals(prevTier + 1, t.tier());
            prevTier = t.tier();
            for (MineDef.Node n : mine.ores().values()) {
                assertEquals(n.tier() <= t.tier() + 1, t.canMine(n.tier()), id + " → " + n.id());
                if (t.canMine(n.tier())) assertTrue(t.seconds(n.baseSeconds(), n.tier()) >= 1.0, id + " " + n.id());
            }
        }
        // 좋은 곡괭이일수록 모든 광석에서 빠르다
        ToolSpec iron = ToolSpec.parse(items.get("iron_pickaxe").sub("tool"));
        ToolSpec ori = ToolSpec.parse(items.get("orichalcum_pickaxe").sub("tool"));
        MineDef.Node copper = mine.ores().get("copper_ore");
        assertTrue(ori.seconds(copper.baseSeconds(), 1) < iron.seconds(copper.baseSeconds(), 1));
    }

    @Test
    void namesMatchContract() {
        Params names = mineJson.sub("names");
        assertEquals(Set.copyOf(MineNames.INTERACTS), names.sub("interact").keys());
        assertEquals(Set.of(MineNames.ROLE_MINER, MineNames.ROLE_SMELTER), names.sub("npc_roles").keys());
        // 계약 §0 (기력 없음 · 광맥 공유): 개인 광맥·기력 ext 는 계약에서도 코드에서도 빠졌다
        assertEquals(new HashSet<>(MineNames.EXT_KEYS), names.sub("ext").keys());
        for (String gone : MineNames.EXT_REMOVED_036) {
            assertFalse(MineNames.EXT_KEYS.contains(gone), gone);
            assertFalse(names.sub("ext").keys().contains(gone), gone);
        }
        assertEquals(MineNames.WORLD, mineJson.sub("world").str("name"));
        assertEquals(MineNames.TOO_WEAK, mineJson.sub("rules").str("too_weak_actionbar"));
    }
}
