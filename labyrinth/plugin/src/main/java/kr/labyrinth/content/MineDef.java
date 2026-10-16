package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 광산 설계 데이터 (content/mine.yml, 0.3.6 — 자동 갱신 파일). 원본 계약: tools/data/036/mine.json ({@code levels}·{@code ores}·{@code gems}
 * 를 그대로 옮김, Q1 tools/mine/gen_mine.py). 손잡이(재생 분·fx·안전)는 config.yml {@code mine:} 에 있다 (R §3-16).
 * <p>
 * 층 6개는 모두 처음부터 열려 있고 레벨 조건이 없다. 층마다 광석·보석이 섞여 있다 ({@link Level#oreWeights()}).
 * 광석·보석 종류마다 바닐라 블록이 하나씩, 12개 모두 다르다 ({@link #byBlock}). mine.yml 이 없으면 {@link #EMPTY} (광산 꺼짐).
 */
public record MineDef(List<Level> levels, Map<String, Node> ores, Map<String, Node> gems) {

    public static final MineDef EMPTY = new MineDef(List.of(), Map.of(), Map.of());

    /** 광석 또는 보석 하나. tier = 단단함 등급 (곡괭이 tier + 1 까지 캠 — 한 단계 위는 느림, 0.3.6.1). gem·ingot 은 광석만, nodeModel 은 보석만. */
    public record Node(String id, String kind, String name, int tier, String block, double baseSeconds, String gem, String ingot,
                       String nodeModel, String color) {
        public boolean isOre() { return "ore".equals(kind); }
        public boolean isGem() { return "gem".equals(kind); }
    }

    /**
     * 층 하나. box = [x0, y0, z0, x1, y1, z1] (광산 월드). biomeY = [아래, 위] (4칸 단위). lift = [x, y, z], landing = [x, y, z, yaw].
     * 이름에 층 번호 글자를 넣지 않는다 (주인 결정 4) — 화면에는 name 만.
     */
    public record Level(int n, String id, String name, int depthM, int floorY, List<Integer> box, String biome, List<Integer> biomeY,
                        String depletedBlock, String titleColor, String regenFx, String atmosphere, Map<String, Integer> oreWeights,
                        Map<String, Integer> veinBlocks, Map<String, Integer> gemWeights, List<String> gemNodes, int regenMinutesDefault,
                        int gemNodeRegenMinutesDefault, List<Double> lift, List<Double> landing, boolean office) {}

    public MineDef {
        levels = levels == null ? List.of() : List.copyOf(levels);
        ores = ores == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(ores));
        gems = gems == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(gems));
    }

    public boolean isEmpty() { return levels.isEmpty(); }

    /** 층 n (1부터). 없으면 null. */
    public Level level(int n) {
        for (Level l : levels) if (l.n() == n) return l;
        return null;
    }

    /** 광석 또는 보석 id → 정의. */
    public Node node(String id) {
        if (id == null) return null;
        Node o = ores.get(id);
        return o != null ? o : gems.get(id);
    }

    /** 바닐라 블록 키(minecraft:…) → 그 블록을 쓰는 광석·보석. */
    public Node byBlock(String blockKey) {
        if (blockKey == null) return null;
        for (Node n : ores.values()) if (blockKey.equals(n.block())) return n;
        for (Node n : gems.values()) if (blockKey.equals(n.block())) return n;
        return null;
    }

    /** mine.yml 루트 → MineDef. 문제는 problem(id, 글) 로 알린다 (예외 없음). */
    public static MineDef parse(Params root, java.util.function.BiConsumer<String, String> problem) {
        if (root == null || root.isEmpty()) return EMPTY;
        Map<String, Node> ores = new LinkedHashMap<>();
        root.sub("ores").children().forEach((id, p) -> ores.put(id, node(id, "ore", p)));
        Map<String, Node> gems = new LinkedHashMap<>();
        root.sub("gems").children().forEach((id, p) -> gems.put(id, node(id, "gem", p)));
        List<Level> levels = new ArrayList<>();
        for (Params p : root.maps("levels")) {
            levels.add(new Level(p.integer("n", levels.size() + 1), p.str("id", "L" + (levels.size() + 1)), p.str("name", ""),
                    p.integer("depth_m", 0), p.integer("floor_y", 0), ints(p, "box"), p.str("biome", "minecraft:dripstone_caves"),
                    ints(p, "biome_y"), p.str("depleted_block", "minecraft:cobblestone"), p.str("title_color", "#ffffff"),
                    p.str("regen_fx", "WAX_ON"), p.str("atmosphere", ""), intMap(p.sub("ore_weights")), intMap(p.sub("vein_blocks")),
                    intMap(p.sub("gem_weights")), p.strings("gem_nodes"), p.integer("regen_minutes_default", 10),
                    p.integer("gem_node_regen_minutes_default", 30), p.doubles("lift"), p.doubles("landing"), p.bool("office", false)));
        }
        MineDef d = new MineDef(levels, ores, gems);
        // 가벼운 검사 (자세한 맞대기는 ContentValidator — Q1·Q3)
        java.util.Set<String> blocks = new java.util.HashSet<>();
        for (Node n : ores.values()) if (!blocks.add(n.block())) problem.accept(n.id(), "블록이 다른 광석·보석과 같음: " + n.block());
        for (Node n : gems.values()) if (!blocks.add(n.block())) problem.accept(n.id(), "블록이 다른 광석·보석과 같음: " + n.block());
        for (int i = 0; i < levels.size(); i++) {
            Level l = levels.get(i);
            if (l.n() != i + 1) problem.accept("levels[" + i + "]", "층 번호가 1부터 차례가 아님: " + l.n());
            for (String o : l.oreWeights().keySet()) if (!ores.containsKey(o)) problem.accept(l.id(), "모르는 광석: " + o);
            for (String g : l.gemNodes()) if (!gems.containsKey(g)) problem.accept(l.id(), "모르는 보석 노드: " + g);
            if (blocks.contains(l.depletedBlock())) problem.accept(l.id(), "빈 광맥 블록이 광석·보석 블록과 같음: " + l.depletedBlock());
        }
        return d;
    }

    private static Node node(String id, String kind, Params p) {
        return new Node(id, kind, p.str("name", id), p.integer("tier", 0), p.str("block", ""), p.dbl("base_seconds", 2.5),
                p.str("gem"), p.str("ingot"), p.str("node_model"), p.str("color", "#ffffff"));
    }

    private static List<Integer> ints(Params p, String key) {
        List<Integer> out = new ArrayList<>();
        for (Double v : p.doubles(key)) out.add((int) Math.round(v));
        return List.copyOf(out);
    }

    private static Map<String, Integer> intMap(Params p) {
        Map<String, Integer> out = new LinkedHashMap<>();
        for (String k : p.keys()) out.put(k, p.integer(k, 0));
        return Collections.unmodifiableMap(out);
    }
}
