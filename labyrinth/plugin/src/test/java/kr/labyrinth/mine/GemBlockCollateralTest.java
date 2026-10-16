package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.Gson;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import kr.labyrinth.content.MineDef;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 주인 결정 ("삐쭉 튀어나온 부분이 별로 … 광석 블록 텍스쳐를 네모난걸 새로"): 보석 6종은 팩이 그림을 바꾼 바닐라 블록 하나씩.
 * 팩이 그 블록의 모습을 바꾸므로 그 블록은 이 팩의 다른 세계 어디에도 없어야 한다 — 미궁 층(floors.yml)·마을과 구역 조각(resources/village/**)·
 * 광산 청사진 장식·코드가 직접 놓는 블록(Material). 12개는 서로 다르고 빈 광맥 블록과도 다르다 (계약 §3.3).
 */
class GemBlockCollateralTest {

    static final Path RES = Path.of("src/main/resources");
    static final Path JAVA = Path.of("src/main/java");

    @Test
    void gemBlocksMatchContractAndContent() throws IOException {
        MineDef mine = MineTestData.mine();
        assertEquals(6, MineNames.GEM_BLOCKS.size());
        for (MineDef.Node g : mine.gems().values()) assertEquals(MineNames.GEM_BLOCKS.get(g.id()), g.block(), g.id() + " mine.json");
        MineDef shipped = new kr.labyrinth.content.ContentParser().parseMine(yaml(RES.resolve("content/mine.yml")));
        for (MineDef.Node g : shipped.gems().values()) {
            assertEquals(MineNames.GEM_BLOCKS.get(g.id()), g.block(), g.id() + " content/mine.yml");
            assertFalse(MineNames.GEM_BLOCKS_036.containsValue(g.block()), g.id() + " 가 0.3.6 블록을 그대로 씀");
            assertTrue(g.nodeModel() == null || g.nodeModel().isBlank(), g.id() + " 결정 모델(node_model)이 남음");
        }
        Set<String> all = new HashSet<>();
        for (MineDef.Node n : mine.ores().values()) all.add(n.block());
        all.addAll(MineNames.GEM_BLOCKS.values());
        assertEquals(12, all.size(), "광석·보석 블록 12개가 모두 다름");
        for (MineDef.Level l : mine.levels()) assertFalse(all.contains(l.depletedBlock()), l.id() + " 빈 광맥 블록");
        @SuppressWarnings("unchecked")
        Map<String, Object> vis = new Gson().fromJson(Files.readString(Path.of("../tools/data/036/visual.json"), StandardCharsets.UTF_8), Map.class);
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> vg = (Map<String, Map<String, Object>>) ((Map<String, Object>) vis.get("blocks")).get("gems");
        for (var e : MineNames.GEM_BLOCKS.entrySet()) {
            assertEquals(e.getValue(), vg.get(e.getKey()).get("block"), e.getKey() + " visual.json (팩 그림)");
            assertEquals("labyrinth:block/mine/gem_" + e.getKey(), vg.get(e.getKey()).get("model"), e.getKey() + " 팩 모델");
        }
        assertFalse(vis.containsKey("gem_nodes"), "보석 결정 모델 표가 남음");
    }

    @Test
    void noCollateralInThePacksOwnWorlds() throws IOException {
        Set<String> names = new HashSet<>();
        for (String b : MineNames.GEM_BLOCKS.values()) names.add(b.substring(b.indexOf(':') + 1));
        Pattern word = Pattern.compile("(?<![a-z0-9_])(" + String.join("|", names) + ")(?![a-z0-9_])", Pattern.CASE_INSENSITIVE);
        List<String> hits = new ArrayList<>();
        int scanned = 0;
        // 미궁 층 팔레트·기믹 블록
        scanned += scan(RES.resolve("content/floors.yml"), word, hits);
        // 마을 조각 · 구역 조각 (0.3.6.1 광산 마을 조각도 여기 들어온다) · 배치
        try (Stream<Path> s = Files.walk(RES.resolve("village"))) {
            for (Path p : s.filter(Files::isRegularFile).toList()) scanned += scan(p, word, hits);
        }
        // 광산 청사진: 논리 글자(@vein/@gem)가 아닌 팔레트 칸
        for (int n = 1; n <= 6; n++) {
            Path p = RES.resolve(MineNames.blueprintPath(n));
            @SuppressWarnings("unchecked")
            Map<String, Object> bp = new Gson().fromJson(Files.readString(p, StandardCharsets.UTF_8), Map.class);
            @SuppressWarnings("unchecked")
            Map<String, String> pal = (Map<String, String>) bp.get("palette");
            for (String v : pal.values()) if (!v.startsWith("@") && word.matcher(v).find()) hits.add(p + ": " + v);
            scanned++;
        }
        // 코드가 직접 놓는 블록 (Material.INFESTED_…) — 광산 이름표·시험 고리 말고는 없어야 함
        Pattern mat = Pattern.compile("Material\\.(" + String.join("|", names.stream().map(x -> x.toUpperCase(Locale.ROOT)).toList()) + ")\\b");
        try (Stream<Path> s = Files.walk(JAVA)) {
            for (Path p : s.filter(x -> x.toString().endsWith(".java")).toList()) {
                if (p.endsWith("MineTestHook.java")) continue;
                Matcher m = mat.matcher(Files.readString(p, StandardCharsets.UTF_8));
                while (m.find()) hits.add(p + ": " + m.group());
                scanned++;
            }
        }
        assertTrue(scanned > 50, "검사한 파일 " + scanned);
        assertTrue(hits.isEmpty(), "보석 블록이 다른 세계에도 쓰임 (팩이 그 모습까지 바꿈): " + hits);
    }

    static int scan(Path p, Pattern word, List<String> hits) throws IOException {
        if (!Files.isRegularFile(p)) return 0;
        Matcher m = word.matcher(Files.readString(p, StandardCharsets.UTF_8));
        while (m.find()) hits.add(p + ": " + m.group(1));
        return 1;
    }

    @SuppressWarnings("unchecked")
    static kr.labyrinth.content.Params yaml(Path p) throws IOException {
        Object o = new org.yaml.snakeyaml.Yaml().load(Files.readString(p, StandardCharsets.UTF_8));
        return kr.labyrinth.content.Params.of((Map<String, Object>) o);
    }
}
