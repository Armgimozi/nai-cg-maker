package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.Tier;
import kr.augsky.util.Text;
import org.bukkit.Color;
import org.bukkit.GameRule;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Chest;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.type.EndPortalFrame;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Interaction;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Marker;
import org.bukkit.entity.TextDisplay;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * 맵 전체를 짓는다. 빈 공허 월드에서 /증강관리 맵생성 을 한 번 실행하면 된다.
 * 배포용 맵 파일은 이 코드로 지은 월드를 그대로 묶은 것이다.
 */
public final class MapBuilder {
    public record Place(String name, int x, int y, int z) {}

    /** 맵의 주요 장소. 안내판과 /증강 제단 에서도 쓴다. */
    public static final List<Place> PLACES = List.of(
            new Place("시작의 섬", 0, 64, 0),
            new Place("모래섬", -38, 62, 30),
            new Place("숲의 섬", 12, 67, -48),
            new Place("실버 제단", 42, 66, -6),
            new Place("골드 제단", -20, 74, -96),
            new Place("프리즘 제단", 132, 92, 118),
            new Place("서리 균열", -124, 60, 52),
            new Place("화염 균열", 104, 56, -124),
            new Place("공허 균열", -164, 100, -172),
            new Place("끝의 섬", 230, 70, -30)
    );

    private final AugSky plugin;
    private World w;

    public MapBuilder(AugSky plugin) {
        this.plugin = plugin;
    }

    public static Place place(String name) {
        for (Place p : PLACES) if (p.name().equals(name)) return p;
        return null;
    }

    public void buildAll(World world) {
        this.w = world;
        long t0 = System.currentTimeMillis();
        clearParts();
        startIsland(place("시작의 섬"));
        sandIsland(place("모래섬"));
        forestIsland(place("숲의 섬"));
        altarIsland(place("실버 제단"), Tier.SILVER, 7, 11);
        altarIsland(place("골드 제단"), Tier.GOLD, 8, 22);
        altarIsland(place("프리즘 제단"), Tier.PRISM, 9, 33);
        riftIsland(place("서리 균열"), "frost", 44);
        riftIsland(place("화염 균열"), "flame", 55);
        riftIsland(place("공허 균열"), "void", 66);
        endIsland(place("끝의 섬"));
        signs();
        w.setSpawnLocation(0, 65, 0);
        w.setGameRule(GameRule.SPAWN_RADIUS, 0);
        w.setGameRule(GameRule.SPAWN_CHUNK_RADIUS, 2);
        w.setTime(1000);
        plugin.altars().scanLoaded();
        plugin.mobs().scanLoaded();
        plugin.getLogger().info("맵 생성 완료 (" + (System.currentTimeMillis() - t0) + "ms)");
    }

    private void clearParts() {
        for (Place p : PLACES) {
            Location c = new Location(w, p.x(), p.y(), p.z());
            c.getChunk().load();
            for (Entity e : w.getNearbyEntities(c, 40, 60, 40)) {
                if (e.getPersistentDataContainer().has(Keys.MAP_PART)) e.remove();
            }
        }
    }

    // ------------------------------------------------------------------ 블록 도우미

    private void set(int x, int y, int z, Material m) {
        w.getBlockAt(x, y, z).setType(m, false);
    }

    /** 위는 넓고 아래로 갈수록 좁아지는 떠 있는 섬. */
    private void blob(int cx, int cy, int cz, double r, int depth, Material top, Material mid, Material bottom,
                      long seed, Material[] ores, double oreChance) {
        Random rnd = new Random(seed);
        double[] ph = {rnd.nextDouble() * 6.28, rnd.nextDouble() * 6.28, rnd.nextDouble() * 6.28};
        int R = (int) Math.ceil(r * 1.25) + 1;
        for (int dy = 0; dy <= depth; dy++) {
            double f = 1 - Math.pow((double) dy / (depth + 1), 1.4);
            for (int x = -R; x <= R; x++) {
                for (int z = -R; z <= R; z++) {
                    double ang = Math.atan2(z, x);
                    double wob = 1 + 0.12 * Math.sin(ang * 3 + ph[0]) + 0.08 * Math.sin(ang * 5 + ph[1])
                            + 0.05 * Math.sin(ang * 7 + ph[2]);
                    double rr = r * f * wob;
                    if (dy > 0) rr -= rnd.nextDouble() * 0.6;
                    if (x * x + z * z > rr * rr) continue;
                    Material m = dy == 0 ? top : dy <= 2 ? mid : bottom;
                    if (dy > 2 && ores != null && rnd.nextDouble() < oreChance) m = ores[rnd.nextInt(ores.length)];
                    set(cx + x, cy - dy, cz + z, m);
                }
            }
        }
    }

    private void disc(int cx, int y, int cz, double r, Material m) {
        int R = (int) Math.ceil(r);
        for (int x = -R; x <= R; x++)
            for (int z = -R; z <= R; z++)
                if (x * x + z * z <= r * r + 0.5) set(cx + x, y, cz + z, m);
    }

    private void column(int x, int y, int z, int h, Material m) {
        for (int i = 0; i < h; i++) set(x, y + i, z, m);
    }

    private Inventory chest(int x, int y, int z, BlockFace facing) {
        Block b = w.getBlockAt(x, y, z);
        b.setType(Material.CHEST, false);
        if (b.getBlockData() instanceof Directional d) {
            d.setFacing(facing);
            b.setBlockData(d, false);
        }
        Chest c = (Chest) b.getState();
        return c.getBlockInventory();
    }

    private void tree(int x, int y, int z, TreeType type) {
        if (!w.generateTree(new Location(w, x, y, z), type)) {
            // 공간이 모자라 실패하면 묘목이라도 심어 둔다
            set(x, y, z, Material.OAK_SAPLING);
        }
    }

    private <T extends Entity> T tag(T e) {
        e.getPersistentDataContainer().set(Keys.MAP_PART, PersistentDataType.BYTE, (byte) 1);
        e.setPersistent(true);
        return e;
    }

    private TextDisplay text(double x, double y, double z, String mm, float scale) {
        return tag(w.spawn(new Location(w, x, y, z), TextDisplay.class, t -> {
            t.text(Text.mm(mm));
            t.setBillboard(Display.Billboard.CENTER);
            t.setBackgroundColor(Color.fromARGB(110, 10, 10, 20));
            t.setShadowed(true);
            t.setAlignment(TextDisplay.TextAlignment.CENTER);
            t.setViewRange(3f);
            t.setBrightness(new Display.Brightness(15, 15));
            t.setTransformation(new Transformation(new Vector3f(), new AxisAngle4f(), new Vector3f(scale, scale, scale), new AxisAngle4f()));
        }));
    }

    private BlockDisplay beam(double x, double y, double z, Material glass, String beamTag) {
        return tag(w.spawn(new Location(w, x, y, z), BlockDisplay.class, b -> {
            b.setBlock(glass.createBlockData());
            b.setTransformation(new Transformation(new Vector3f(-0.3f, 0, -0.3f), new AxisAngle4f(),
                    new Vector3f(0.6f, 220f, 0.6f), new AxisAngle4f()));
            b.setBrightness(new Display.Brightness(15, 15));
            b.setViewRange(8f);
            if (beamTag != null) b.getPersistentDataContainer().set(Keys.BEAM, PersistentDataType.STRING, beamTag);
        }));
    }

    private BlockDisplay crystal(double x, double y, double z, Material m, float size) {
        return tag(w.spawn(new Location(w, x, y, z), BlockDisplay.class, b -> {
            b.setBlock(m.createBlockData());
            // 정육면체를 꼭짓점이 위로 오게 세운 '보석' 모양
            AxisAngle4f rot = new AxisAngle4f((float) Math.toRadians(54.7), 1, 0, 1);
            b.setTransformation(new Transformation(new Vector3f(0, 0, 0), rot, new Vector3f(size, size, size), new AxisAngle4f()));
            b.setBrightness(new Display.Brightness(15, 15));
            b.setViewRange(4f);
        }));
    }

    private void interaction(double x, double y, double z, float width, float height, org.bukkit.NamespacedKey key, String value) {
        tag(w.spawn(new Location(w, x, y, z), Interaction.class, i -> {
            i.setInteractionWidth(width);
            i.setInteractionHeight(height);
            i.setResponsive(true);
            i.getPersistentDataContainer().set(key, PersistentDataType.STRING, value);
        }));
    }

    private void item(double x, double y, double z, ItemStack stack, float scale) {
        tag(w.spawn(new Location(w, x, y, z), ItemDisplay.class, d -> {
            d.setItemStack(stack);
            d.setBillboard(Display.Billboard.VERTICAL);
            d.setBrightness(new Display.Brightness(15, 15));
            d.setTransformation(new Transformation(new Vector3f(), new AxisAngle4f(), new Vector3f(scale, scale, scale), new AxisAngle4f()));
        }));
    }

    // ------------------------------------------------------------------ 섬들

    private void startIsland(Place p) {
        int cx = p.x(), y = p.y(), cz = p.z();
        // 고전 스카이블럭처럼 L 자 모양 흙섬. 친구들과 쓰기 좋게 조금 넓혔다
        for (int x = -4; x <= 4; x++) {
            for (int z = -4; z <= 6; z++) {
                boolean in = (z <= 1) || (x <= 0);
                if (!in) continue;
                set(cx + x, y, cz + z, Material.GRASS_BLOCK);
                set(cx + x, y - 1, cz + z, Material.DIRT);
                set(cx + x, y - 2, cz + z, Material.DIRT);
                if (Math.abs(x) <= 2 && z >= -2 && z <= 0) set(cx + x, y - 3, cz + z, Material.DIRT);
            }
        }
        set(cx, y - 3, cz - 1, Material.BEDROCK);
        tree(cx + 3, y + 1, cz - 3, TreeType.TREE);
        Inventory inv = chest(cx - 3, y + 1, cz - 3, BlockFace.SOUTH);
        inv.addItem(new ItemStack(Material.LAVA_BUCKET), new ItemStack(Material.ICE, 2),
                new ItemStack(Material.OAK_SAPLING, 2), new ItemStack(Material.MELON_SLICE),
                new ItemStack(Material.PUMPKIN_SEEDS), new ItemStack(Material.SUGAR_CANE),
                new ItemStack(Material.CACTUS), new ItemStack(Material.RED_MUSHROOM),
                new ItemStack(Material.BROWN_MUSHROOM), new ItemStack(Material.WHEAT_SEEDS, 4),
                new ItemStack(Material.BONE_MEAL, 4), new ItemStack(Material.BREAD, 8),
                new ItemStack(Material.TORCH, 4), plugin.items().guideBook());
        set(cx - 2, y + 1, cz - 3, Material.CRAFTING_TABLE);
    }

    private void sandIsland(Place p) {
        blob(p.x(), p.y(), p.z(), 4.2, 5, Material.SAND, Material.SAND, Material.SANDSTONE, 11, null, 0);
        set(p.x() + 1, p.y() + 1, p.z() + 1, Material.CACTUS);
        set(p.x() + 1, p.y() + 2, p.z() + 1, Material.CACTUS);
        Inventory inv = chest(p.x() - 1, p.y() + 1, p.z() - 1, BlockFace.EAST);
        inv.addItem(new ItemStack(Material.OBSIDIAN, 10), new ItemStack(Material.SUGAR_CANE, 2),
                new ItemStack(Material.CACTUS, 2), new ItemStack(Material.SAND, 16), new ItemStack(Material.SWEET_BERRIES, 3),
                plugin.items().create("shard", 3));
    }

    private void forestIsland(Place p) {
        blob(p.x(), p.y(), p.z(), 5.5, 6, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, 12,
                new Material[]{Material.COAL_ORE, Material.IRON_ORE}, 0.08);
        tree(p.x() - 2, p.y() + 1, p.z() + 1, TreeType.TREE);
        tree(p.x() + 2, p.y() + 1, p.z() - 2, TreeType.BIRCH);
        set(p.x() + 2, p.y() + 1, p.z() + 2, Material.SHORT_GRASS);
        set(p.x(), p.y() + 1, p.z() - 3, Material.POPPY);
        set(p.x() - 3, p.y() + 1, p.z() - 1, Material.DANDELION);
    }

    private void altarIsland(Place p, Tier tier, double radius, long seed) {
        Material top = tier == Tier.PRISM ? Material.MOSS_BLOCK : Material.GRASS_BLOCK;
        Material bottom = tier == Tier.PRISM ? Material.CALCITE : Material.STONE;
        blob(p.x(), p.y(), p.z(), radius, (int) (radius * 1.1), top, Material.DIRT, bottom, seed, null, 0);
        altarStructure(w, p.x(), p.y(), p.z(), tier);
    }

    /** 제단 구조물만 짓는다. /증강관리 제단 으로 원하는 곳에 새 제단을 세울 때도 쓴다. */
    public void altarStructure(World world, int cx, int y, int cz, Tier tier) {
        this.w = world;
        Material floorA, floorB, pillar, cap, glass, core;
        switch (tier) {
            case SILVER -> {
                floorA = Material.POLISHED_DIORITE; floorB = Material.SMOOTH_QUARTZ;
                pillar = Material.QUARTZ_PILLAR; cap = Material.SEA_LANTERN;
                glass = Material.WHITE_STAINED_GLASS; core = Material.IRON_BLOCK;
            }
            case GOLD -> {
                floorA = Material.SMOOTH_SANDSTONE; floorB = Material.CHISELED_SANDSTONE;
                pillar = Material.CUT_SANDSTONE; cap = Material.GLOWSTONE;
                glass = Material.YELLOW_STAINED_GLASS; core = Material.GOLD_BLOCK;
            }
            default -> {
                floorA = Material.PURPUR_BLOCK; floorB = Material.PRISMARINE_BRICKS;
                pillar = Material.PURPUR_PILLAR; cap = Material.SEA_LANTERN;
                glass = Material.MAGENTA_STAINED_GLASS; core = Material.AMETHYST_BLOCK;
            }
        }
        Location c0 = new Location(w, cx + 0.5, y + 2, cz + 0.5);
        for (Entity e : w.getNearbyEntities(c0, 4, 8, 4)) {
            if (e.getPersistentDataContainer().has(Keys.MAP_PART)) e.remove();
        }
        // 제단 바닥: 두 가지 블록으로 동심원 무늬
        for (int x = -4; x <= 4; x++) {
            for (int z = -4; z <= 4; z++) {
                double d = Math.sqrt(x * x + z * z);
                if (d > 4.3) continue;
                set(cx + x, y, cz + z, ((int) Math.round(d)) % 2 == 0 ? floorA : floorB);
                for (int h = 1; h <= 6; h++) set(cx + x, y + h, cz + z, Material.AIR);
            }
        }
        // 가운데 단
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++) set(cx + x, y + 1, cz + z, floorB);
        set(cx, y + 1, cz, cap);
        // 네 기둥
        int[][] corners = {{3, 3}, {-3, 3}, {3, -3}, {-3, -3}};
        for (int[] c : corners) {
            column(cx + c[0], y + 1, cz + c[1], 3, pillar);
            set(cx + c[0], y + 4, cz + c[1], cap);
            if (tier == Tier.PRISM) set(cx + c[0], y + 5, cz + c[1], Material.END_ROD);
            if (tier == Tier.GOLD) set(cx + c[0], y + 5, cz + c[1], Material.LANTERN);
        }
        // 떠 있는 보석, 빛기둥, 이름표, 클릭 판정
        crystal(cx + 0.5, y + 3.0, cz + 0.5, core, 0.9f);
        beam(cx + 0.5, y + 5.2, cz + 0.5, glass, tier == Tier.PRISM ? "prism" : tier.name().toLowerCase());
        String label = tier.wrap("✦ " + tier.korean + " 제단 ✦") + "\n<gray>우클릭해서 증강 얻기";
        text(cx + 0.5, y + 5.0, cz + 0.5, label, 1.4f);
        interaction(cx + 0.5, y + 2.0, cz + 0.5, 2.2f, 2.6f, Keys.ALTAR, tier.name());
        plugin.altars().scanLoaded();
    }

    private void riftIsland(Place p, String rift, long seed) {
        int cx = p.x(), y = p.y(), cz = p.z();
        Material top, mid, bottom, deco, glow;
        Material[] ores;
        String title;
        Material stone;
        switch (rift) {
            case "frost" -> {
                top = Material.SNOW_BLOCK; mid = Material.PACKED_ICE; bottom = Material.STONE;
                deco = Material.BLUE_ICE; glow = Material.SEA_LANTERN; stone = Material.PACKED_ICE;
                ores = new Material[]{Material.IRON_ORE, Material.COAL_ORE, Material.LAPIS_ORE, Material.DIAMOND_ORE};
                title = "<#9ad8ff>❄ 서리 균열 ❄";
            }
            case "flame" -> {
                top = Material.NETHERRACK; mid = Material.MAGMA_BLOCK; bottom = Material.BLACKSTONE;
                deco = Material.BASALT; glow = Material.SHROOMLIGHT; stone = Material.MAGMA_BLOCK;
                ores = new Material[]{Material.NETHER_GOLD_ORE, Material.NETHER_QUARTZ_ORE, Material.GOLD_ORE, Material.REDSTONE_ORE};
                title = "<#ff8a3d>🔥 화염 균열 🔥";
            }
            default -> {
                top = Material.END_STONE; mid = Material.END_STONE; bottom = Material.OBSIDIAN;
                deco = Material.CRYING_OBSIDIAN; glow = Material.END_ROD; stone = Material.PURPUR_BLOCK;
                ores = new Material[]{Material.DIAMOND_ORE, Material.EMERALD_ORE, Material.GOLD_ORE, Material.IRON_ORE};
                title = "<#c86bff>✧ 공허 균열 ✧";
            }
        }
        blob(cx, y, cz, 12, 11, top, mid, bottom, seed, ores, 0.05);
        Random r = new Random(seed * 7);
        // 장식 기둥 몇 개
        for (int i = 0; i < 7; i++) {
            double a = r.nextDouble() * Math.PI * 2, d = 5 + r.nextDouble() * 5;
            int x = cx + (int) Math.round(Math.cos(a) * d), z = cz + (int) Math.round(Math.sin(a) * d);
            int h = 2 + r.nextInt(4);
            column(x, y + 1, z, h, deco);
            if (r.nextBoolean()) set(x, y + 1 + h, z, glow);
        }
        // 균열 표식(보이지 않는 마커) — 이 주변에 몬스터가 나온다
        tag(w.spawn(new Location(w, cx + 0.5, y + 1, cz + 0.5), Marker.class, m ->
                m.getPersistentDataContainer().set(Keys.RIFT, PersistentDataType.STRING, rift)));
        crystal(cx + 0.5, y + 4.5, cz + 0.5, rift.equals("frost") ? Material.BLUE_ICE : rift.equals("flame") ? Material.MAGMA_BLOCK : Material.CRYING_OBSIDIAN, 1.4f);
        text(cx + 0.5, y + 7.5, cz + 0.5, title + "\n<gray>균열의 몬스터가 쏟아져 나온다", 1.6f);
        // 보스 소환대
        int px = cx + 7, pz = cz;
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++) set(px + x, y, pz + z, Material.POLISHED_BLACKSTONE_BRICKS);
        set(px, y + 1, pz, Material.LODESTONE);
        set(px - 1, y + 1, pz - 1, Material.SOUL_LANTERN);
        set(px + 1, y + 1, pz + 1, Material.SOUL_LANTERN);
        var mobs = plugin.mobs().registry();
        var rd = mobs.rifts().get(rift);
        String bossName = "보스";
        String stoneName = "소환석";
        if (rd != null) {
            var bd = mobs.get(rd.boss());
            if (bd != null) bossName = bd.name();
            var sd = plugin.items().def(rd.summonItem());
            if (sd != null) stoneName = sd.name();
            ItemStack st = plugin.items().create(rd.summonItem(), 1);
            if (st != null) item(px + 0.5, y + 2.6, pz + 0.5, st, 0.8f);
        }
        text(px + 0.5, y + 3.4, pz + 0.5, bossName + " <gray>소환대\n<white>" + stoneName + "<gray>을 들고 우클릭", 1.0f);
        interaction(px + 0.5, y + 1, pz + 0.5, 1.4f, 1.6f, Keys.PEDESTAL, rift);
        // 보급 상자
        Inventory inv = chest(cx - 6, y + 1, cz + 3, BlockFace.EAST);
        inv.addItem(plugin.items().create("shard", 4), new ItemStack(stone, 8), new ItemStack(Material.TORCH, 8));
    }

    /** 균열 표식과 소환대만 세운다 (/증강관리 균열). */
    public void riftMarker(World world, Location at, String rift) {
        this.w = world;
        tag(w.spawn(at.clone(), Marker.class, m ->
                m.getPersistentDataContainer().set(Keys.RIFT, PersistentDataType.STRING, rift)));
        interaction(at.getBlockX() + 3.5, at.getBlockY(), at.getBlockZ() + 0.5, 1.4f, 1.6f, Keys.PEDESTAL, rift);
        set(at.getBlockX() + 3, at.getBlockY(), at.getBlockZ(), Material.LODESTONE);
        plugin.mobs().scanLoaded();
    }

    private void endIsland(Place p) {
        int cx = p.x(), y = p.y(), cz = p.z();
        blob(cx, y, cz, 7, 7, Material.END_STONE, Material.END_STONE, Material.END_STONE, 77, null, 0);
        // 엔드 포탈 틀 12개. 눈은 직접 채워야 한다
        for (int i = -1; i <= 1; i++) {
            frame(cx + i, y + 1, cz - 2, BlockFace.SOUTH);
            frame(cx + i, y + 1, cz + 2, BlockFace.NORTH);
            frame(cx - 2, y + 1, cz + i, BlockFace.EAST);
            frame(cx + 2, y + 1, cz + i, BlockFace.WEST);
        }
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++) set(cx + x, y, cz + z, Material.AIR);
        text(cx + 0.5, y + 4, cz + 0.5, "<#d9f99d>끝의 섬\n<gray>엔더의 눈 12개로 문을 열어라", 1.2f);
    }

    private void frame(int x, int y, int z, BlockFace facing) {
        Block b = w.getBlockAt(x, y, z);
        b.setType(Material.END_PORTAL_FRAME, false);
        if (b.getBlockData() instanceof EndPortalFrame f) {
            f.setFacing(facing);
            f.setEye(false);
            b.setBlockData(f, false);
        }
    }

    private void signs() {
        Place s = place("시작의 섬");
        text(s.x() + 0.5, s.y() + 8, s.z() + 0.5,
                "<gradient:#ff6b9d:#ffd36b:#6bffb0:#6bc8ff:#c86bff><b>증강 스카이블럭</b></gradient>\n<gray>빛기둥을 따라 제단을 찾아가세요", 2.0f);
        List<String> lines = new ArrayList<>();
        for (String n : List.of("실버 제단", "골드 제단", "프리즘 제단", "서리 균열", "화염 균열", "공허 균열")) {
            Place p = place(n);
            int dist = (int) Math.round(Math.hypot(p.x() - s.x(), p.z() - s.z()));
            lines.add("<white>" + n + " <gray>" + dir(p.x() - s.x(), p.z() - s.z()) + " " + dist + "m");
        }
        text(s.x() - 3.5, s.y() + 3.2, s.z() + 4.5, String.join("\n", lines), 0.9f);
    }

    public static String dir(int dx, int dz) {
        double a = Math.toDegrees(Math.atan2(dx, -dz));
        if (a < 0) a += 360;
        String[] names = {"북쪽", "북동쪽", "동쪽", "남동쪽", "남쪽", "남서쪽", "서쪽", "북서쪽"};
        return names[(int) Math.round(a / 45) % 8];
    }
}
