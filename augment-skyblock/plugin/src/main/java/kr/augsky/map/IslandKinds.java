package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.map.MapBuilder.Isle;
import kr.augsky.map.MapBuilder.Region;
import org.bukkit.DyeColor;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.block.Biome;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Animals;
import org.bukkit.entity.Armadillo;
import org.bukkit.entity.Bee;
import org.bukkit.entity.Chicken;
import org.bukkit.entity.Cow;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Frog;
import org.bukkit.entity.Llama;
import org.bukkit.entity.MushroomCow;
import org.bukkit.entity.Parrot;
import org.bukkit.entity.Pig;
import org.bukkit.entity.Rabbit;
import org.bukkit.entity.Sheep;
import org.bukkit.entity.Snowman;
import org.bukkit.entity.Turtle;
import org.bukkit.entity.minecart.StorageMinecart;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.EnchantmentStorageMeta;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;
import java.util.function.Predicate;

/**
 * 자원 섬 41종과 징검다리 바위. 섬마다 모습(블록, 식물, 동물, 생물군계의 하늘과 풀 색)과 나는 재료가 다르다.
 * 이름표가 없으니 모습만 보고 무슨 섬인지 알 수 있어야 한다.
 */
final class IslandKinds extends IsleTools {
    static final List<String> KINDS = List.of(
            "woods", "mine", "ranch", "farm", "pumpkin", "pond", "meadow", "mushroom", "desert", "spider_den",
            "taiga", "frozen_lake", "frost_mine", "icespike", "igloo",
            "basalt", "crimson", "warped", "soul_valley", "fortress", "volcano", "nether_vein",
            "chorus", "geode", "obsidian_spire", "purpur_ruin",
            "beach", "lagoon", "copper_cove", "prismarine_ruin", "shipwreck",
            "jungle", "swamp", "badlands", "savanna", "lush_cave", "mountain", "deep_mine", "dark_forest", "cherry", "ruin",
            "stone");

    IslandKinds(AugSky plugin, org.bukkit.World world) {
        super(plugin, world);
    }

    /** 섬을 짓는 높이. 늪은 슬라임이 나오는 높이(51~69)에 맞춘다. */
    static int buildY(Isle is) {
        return is.kind().equals("swamp") ? Math.max(52, Math.min(is.y(), 66)) : is.y();
    }

    /** 섬 밑동 깊이. */
    static int depth(Isle is) {
        return Math.max(4, (int) (is.r() * 1.1));
    }

    void build(Isle is, Random r) {
        begin(is, r, buildY(is), depth(is));
        switch (is.kind()) {
            case "woods" -> woods();
            case "mine" -> mine();
            case "ranch" -> ranch();
            case "farm" -> farm();
            case "pumpkin" -> pumpkin();
            case "pond" -> pond();
            case "meadow" -> meadow();
            case "mushroom" -> mushroom();
            case "desert" -> desert();
            case "spider_den" -> spiderDen();
            case "taiga" -> taiga();
            case "frozen_lake" -> frozenLake();
            case "frost_mine" -> frostMine();
            case "icespike" -> iceSpike();
            case "igloo" -> igloo();
            case "basalt" -> basalt();
            case "crimson" -> crimson();
            case "warped" -> warped();
            case "soul_valley" -> soulValley();
            case "fortress" -> fortress();
            case "volcano" -> volcano();
            case "nether_vein" -> netherVein();
            case "chorus" -> chorus();
            case "geode" -> geode();
            case "obsidian_spire" -> obsidianSpire();
            case "purpur_ruin" -> purpurRuin();
            case "beach" -> beach();
            case "lagoon" -> lagoon();
            case "copper_cove" -> copperCove();
            case "prismarine_ruin" -> prismarineRuin();
            case "shipwreck" -> shipwreck();
            case "jungle" -> jungle();
            case "swamp" -> swamp();
            case "badlands" -> badlands();
            case "savanna" -> savanna();
            case "lush_cave" -> lushCave();
            case "mountain" -> mountain();
            case "deep_mine" -> deepMine();
            case "dark_forest" -> darkForest();
            case "cherry" -> cherry();
            case "ruin" -> ruin();
            case "stone" -> stone();
            default -> throw new IllegalArgumentException("알 수 없는 섬 종류: " + is.kind());
        }
    }

    /** 섬에 칠할 생물군계 (하늘·풀·물 색, 눈과 비, 나오는 몹이 바뀐다). null 이면 칠하지 않는다. */
    static Biome biome(Isle is) {
        return switch (is.kind()) {
            case "woods" -> Biome.FOREST;
            case "meadow" -> Biome.FLOWER_FOREST;
            case "mushroom" -> Biome.MUSHROOM_FIELDS;
            case "desert" -> Biome.DESERT;
            case "spider_den", "dark_forest" -> Biome.DARK_FOREST;
            case "mine", "ranch", "farm", "pumpkin", "pond", "ruin" -> Biome.PLAINS;
            case "taiga" -> Biome.SNOWY_TAIGA;
            case "frozen_lake", "frost_mine", "igloo", "rift_frost", "lair_frost" -> Biome.SNOWY_PLAINS;
            case "icespike" -> Biome.ICE_SPIKES;
            case "basalt" -> Biome.BASALT_DELTAS;
            case "crimson", "rift_flame", "lair_flame" -> Biome.CRIMSON_FOREST;
            case "warped" -> Biome.WARPED_FOREST;
            case "soul_valley" -> Biome.SOUL_SAND_VALLEY;
            case "fortress", "volcano", "nether_vein" -> Biome.NETHER_WASTES;
            case "chorus", "obsidian_spire", "purpur_ruin", "rift_void", "lair_void", "end" -> Biome.THE_END;
            case "geode" -> is.region() == Region.VOID ? Biome.THE_END : Biome.PLAINS;
            case "beach" -> Biome.BEACH;
            case "lagoon" -> Biome.WARM_OCEAN;
            case "copper_cove" -> Biome.LUKEWARM_OCEAN;
            case "prismarine_ruin", "shipwreck" -> Biome.OCEAN;
            case "jungle" -> Biome.JUNGLE;
            case "swamp" -> Biome.SWAMP;
            case "badlands" -> Biome.BADLANDS;
            case "savanna" -> Biome.SAVANNA;
            case "lush_cave" -> Biome.LUSH_CAVES;
            case "mountain" -> Biome.WINDSWEPT_HILLS;
            case "deep_mine" -> Biome.DRIPSTONE_CAVES;
            case "cherry" -> Biome.CHERRY_GROVE;
            default -> null; // 시작 섬, 제단, 징검다리
        };
    }

    /** 섬 종류의 생물군계를 칠한다. */
    void paintBiome(Isle is) {
        paintBiome(is, biome(is), buildY(is));
    }

    void settleGravity(Isle is) {
        settleGravity(is, buildY(is), depth(is));
    }

    // ------------------------------------------------------------------ 작은 도우미

    private boolean fixed() {
        return is.seed() < 100;
    }

    /** 꽃과 풀. 처음엔 종류마다 하나씩, 그다음은 아무거나. */
    private void flowers(int n, Predicate<int[]> skip, Material... kinds) {
        List<int[]> spots = tiles(0);
        int placed = 0;
        while (placed < n && !spots.isEmpty()) {
            int[] p = take(spots);
            if (type(p[0], y, p[1]) != Material.GRASS_BLOCK || !air(p[0], y + 1, p[1])) continue;
            if (skip != null && skip.test(p)) continue;
            set(p[0], y + 1, p[1], placed < kinds.length ? kinds[placed] : kinds[r.nextInt(kinds.length)]);
            placed++;
        }
    }

    private void snowLayer() {
        int R = (int) Math.ceil(rad * 1.3);
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                int ty = top(x + dx, z + dz, y);
                if (ty == Integer.MIN_VALUE || !air(x + dx, ty + 1, z + dz)) continue;
                Material t = type(x + dx, ty, z + dz);
                if (t == Material.SNOW_BLOCK || t == Material.PODZOL) set(x + dx, ty + 1, z + dz, Material.SNOW);
            }
    }

    private void animals(int px, int py, int pz, Class<? extends Animals> cls, int n) {
        for (int i = 0; i < n; i++) mob(px + 0.5 + (i % 2), py, pz + 0.5 + (i / 2), cls, null);
    }

    /** 야자수: 정글 원목 4칸, 꼭대기에 잎 십자(팔 길이 2, 끝이 한 칸 처진다)와 맨 위 잎 하나. */
    private void palm(int px, int pz) {
        column(px, y + 1, pz, 4, Material.JUNGLE_LOG);
        String leaf = "jungle_leaves[persistent=true]";
        int ty = y + 4;
        for (int[] f : FOUR) {
            set(px + f[0], ty, pz + f[1], leaf);
            set(px + 2 * f[0], ty - 1, pz + 2 * f[1], leaf);
        }
        set(px, ty + 1, pz, leaf);
    }

    /** 덩굴 박(호박·수박)과 붙은 줄기: 열매 옆 칸을 경작지로 만들고 열매 쪽을 보는 줄기를 놓는다. */
    private int gourds(List<int[]> spots, Material fruit, String stem, int want) {
        int n = 0;
        for (int k = 0; k < 40 && n < want; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int s = r.nextInt(4);
            for (int i = 0; i < 4; i++) {
                int[] f = FOUR[(s + i) % 4];
                int qx = p[0] + f[0], qz = p[1] + f[1];
                if (!tile(qx, qz)) continue;
                set(p[0], y + 1, p[1], fruit);
                set(qx, y, qz, "farmland[moisture=0]");
                set(qx, y + 1, qz, stem + "[facing=" + face(new int[]{-f[0], -f[1]}) + "]");
                spots.removeIf(q -> Math.abs(q[0] - qx) <= 1 && Math.abs(q[1] - qz) <= 1);
                n++;
                break;
            }
        }
        return n;
    }

    // ------------------------------------------------------------------ 굴

    /** 굴 틀: 벽 속 기둥, 들보, 벽 광석, 레일, 틀마다 사슬에 매단 등(없으면 null), 틀이 시작하는 칸. */
    private record Frame(Material post, Material beam, Material[] ores, boolean rail, String lamp, int start) {}

    /** 판 굴. 칸 (t, s) 는 가운데 + u·t + v·s. mouth 는 굴이 바깥으로 열린 t. */
    private record Bore(int ox, int oz, int[] u, int[] v, int mouth) {
        int x(int t, int s) {
            return ox + u[0] * t + v[0] * s;
        }

        int z(int t, int s) {
            return oz + u[1] * t + v[1] * s;
        }
    }

    /**
     * 시작 섬 쪽으로 굴을 판다. 바닥 높이 floor, 안쪽 높이 h, 너비 width, from 칸에서 시작해 바닥이 끊기는 곳(섬 옆면)까지.
     * frame 이 있으면 3칸마다 벽 속 기둥 두 개와 들보(들보 칸은 한 칸 낮아진다), 벽 블록 25% 는 광석.
     */
    private Bore tunnel(int floor, int h, int width, int from, Frame frame) {
        int[] u = toSpawn(), v = side(u);
        int t = from, R = (int) Math.ceil(rad * 1.3) + 2;
        for (; t <= R; t++) {
            boolean floored = true;
            for (int s = 0; s < width; s++) {
                if (!solid(x + u[0] * t + v[0] * s, floor, z + u[1] * t + v[1] * s)) floored = false;
            }
            if (!floored) break;
            for (int s = 0; s < width; s++)
                for (int k = 1; k <= h; k++) set(x + u[0] * t + v[0] * s, floor + k, z + u[1] * t + v[1] * s, Material.AIR);
            if (frame == null) continue;
            for (int s : new int[]{-1, width}) {
                for (int k = 1; k <= h; k++) {
                    int wx = x + u[0] * t + v[0] * s, wz = z + u[1] * t + v[1] * s;
                    if (solid(wx, floor + k, wz) && r.nextDouble() < 0.25) set(wx, floor + k, wz, frame.ores()[r.nextInt(frame.ores().length)]);
                }
            }
        }
        Bore b = new Bore(x, z, u, v, t);
        if (frame == null) return b;
        String shape = u[0] != 0 ? "east_west" : "north_south";
        for (int tt = from; tt < b.mouth(); tt++) {
            if (frame.rail()) set(b.x(tt, 0), floor + 1, b.z(tt, 0), "rail[shape=" + shape + "]");
            if (tt < frame.start() || (tt - frame.start()) % 3 != 0 || tt >= b.mouth() - 1) continue;
            for (int s : new int[]{-1, width}) {
                if (!solid(b.x(tt, s), floor + 1, b.z(tt, s))) continue;
                for (int k = 1; k < h; k++) set(b.x(tt, s), floor + k, b.z(tt, s), frame.post());
            }
            for (int s = -1; s <= width; s++) set(b.x(tt, s), floor + h, b.z(tt, s), frame.beam());
            if (frame.lamp() != null && tt + 1 < b.mouth()) {
                // 레일 없는 칸에 사슬과 등을 단다 (레일 칸은 걸어 다닐 수 있게 비운다)
                set(b.x(tt + 1, 1), floor + h, b.z(tt + 1, 1), Material.CHAIN);
                set(b.x(tt + 1, 1), floor + h - 1, b.z(tt + 1, 1), frame.lamp() + "[hanging=true]");
            }
        }
        return b;
    }

    // ------------------------------------------------------------------ 보물 상자

    private static final Object[] MINE_LOOT = {"TORCH*8", 8, "COAL*6", 8, "BREAD*3", 6, "RAW_IRON*3", 6, "RAW_GOLD*2", 4,
            "RAIL*8", 3, "item:shard*2", 2};
    private static final Object[] SPIDER_LOOT = {"STRING*6", 10, "SPIDER_EYE*2", 8, "BONE*5", 6, "ARROW*8", 5, "COBWEB*2", 3,
            "item:shard*2", 3, "GOLDEN_APPLE", 1, "NAME_TAG", 1};
    private static final Object[] IGLOO_LOOT = {"SNOWBALL*8", 8, "PACKED_ICE*4", 6, "LAPIS_LAZULI*6", 6, "item:essence_frost*2", 5,
            "item:shard*2", 3, "GOLDEN_APPLE", 2, "DIAMOND", 1, "item:ticket_silver", 1};
    private static final Object[] FORTRESS_LOOT = {"GOLD_INGOT*3", 8, "IRON_INGOT*4", 6, "NETHER_WART*4", 6, "item:essence_flame*2", 5,
            "SADDLE", 3, "OBSIDIAN*2", 3, "item:shard*3", 3, "DIAMOND", 2, "GOLDEN_APPLE", 1};
    private static final Object[] PURPUR_LOOT = {"ENDER_PEARL*3", 8, "item:essence_void*2", 6, "CHORUS_FRUIT*6", 5,
            "PHANTOM_MEMBRANE*2", 4, "END_ROD*2", 4, "DIAMOND*2", 3, "item:shard*3", 3, "item:ticket_silver", 1};
    private static final Object[] OCEAN_RUIN_LOOT = {"PRISMARINE_SHARD*8", 8, "PRISMARINE_CRYSTALS*6", 6, "NAUTILUS_SHELL", 5,
            "LAPIS_LAZULI*6", 4, "GOLD_INGOT*2", 4, "item:shard*2", 3, "SPONGE", 2, "DIAMOND", 2};
    private static final Object[] SHIP_SUPPLY_LOOT = {"WHEAT*6", 6, "CARROT*4", 6, "POTATO*4", 6, "PAPER*6", 5, "COAL*6", 5,
            "LEATHER*3", 4, "PHANTOM_MEMBRANE*2", 3, "PUMPKIN_PIE*2", 3, "BOOK*2", 2};
    private static final Object[] SHIP_TREASURE_LOOT = {"IRON_INGOT*5", 8, "GOLD_INGOT*3", 6, "EMERALD*3", 5, "NAUTILUS_SHELL", 4,
            "item:shard*3", 3, "DIAMOND", 2, "item:ticket_silver", 1};
    private static final Object[] RUIN_LOOT = {"BONE*6", 6, "IRON_INGOT*3", 6, "GOLD_INGOT*3", 5, "BOOK*3", 5, "PHANTOM_MEMBRANE*2", 4,
            "item:shard*3", 4, "HONEYCOMB*3", 3, "GOLDEN_APPLE", 2, "DIAMOND", 2, "NAME_TAG", 1, "item:ticket_silver", 1};

    private static ItemStack silkPickaxe() {
        ItemStack it = new ItemStack(Material.IRON_PICKAXE);
        it.addEnchantment(Enchantment.SILK_TOUCH, 1);
        return it;
    }

    private static ItemStack silkBook() {
        ItemStack it = new ItemStack(Material.ENCHANTED_BOOK);
        it.editMeta(EnchantmentStorageMeta.class, m -> m.addStoredEnchant(Enchantment.SILK_TOUCH, 1, true));
        return it;
    }

    // ------------------------------------------------------------------ 초원 (기본 재료)

    /** 숲: 참나무·자작나무 원목. */
    private void woods() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        if (fixed()) {
            // 시작 섬 옆 숲엔 자작나무를 늘 둔다 (자작나무 원목이 드는 조합법이 있다)
            tree(x - 2, y + 1, z + 1, TreeType.TREE, Material.OAK_SAPLING);
            tree(x + 2, y + 1, z - 2, TreeType.BIRCH, Material.BIRCH_SAPLING);
            if (tile(x - 1, z - 3)) tree(x - 1, y + 1, z - 3, TreeType.BIRCH, Material.BIRCH_SAPLING);
        } else {
            List<int[]> spots = tiles(2);
            int n = rad > 7 ? 3 : 2;
            for (int i = 0; i < n; i++) {
                boolean oak = i % 2 == 0;
                grow(spots, i == 0 && rad > 7.5 ? TreeType.BIG_TREE : oak ? TreeType.TREE : TreeType.BIRCH,
                        oak ? Material.OAK_SAPLING : Material.BIRCH_SAPLING);
            }
        }
        // 쓰러진 통나무와 그 옆의 버섯
        int off = (int) (rad * 0.55);
        for (int sideZ : new int[]{off, -off}) {
            boolean ok = true;
            for (int i = -1; i <= 2; i++) if (!tile(x + i, z + sideZ)) ok = false;
            if (!ok) continue;
            for (int i = -1; i <= 2; i++) set(x + i, y + 1, z + sideZ, "oak_log[axis=x]");
            // 햇빛 아래 통나무 위의 버섯은 옆 블록이 바뀌면 떨어져 나가서, 통나무 옆 회백토 위에 둔다
            int mz = z + sideZ - Integer.signum(sideZ);
            if (tile(x, mz) && air(x, y + 1, mz)) {
                set(x, y, mz, Material.PODZOL);
                set(x, y + 1, mz, Material.BROWN_MUSHROOM);
            }
            break;
        }
        flowers((int) (rad * 2.2), null, Material.POPPY, Material.DANDELION, Material.LILY_OF_THE_VALLEY,
                Material.SHORT_GRASS, Material.SHORT_GRASS, Material.SHORT_GRASS);
    }

    private static final Material[] MINE_ORES = {Material.COAL_ORE, Material.COAL_ORE, Material.COAL_ORE, Material.COAL_ORE,
            Material.COAL_ORE, Material.IRON_ORE, Material.IRON_ORE, Material.IRON_ORE, Material.IRON_ORE, Material.COPPER_ORE,
            Material.GOLD_ORE};

    /** 광산: 석탄·철·구리·금. 시작 섬 쪽에서 들어가는 갱도 끝에 용암 한 칸과 상자 광차. */
    private void mine() {
        long sd = is.seed();
        blob(x, y, z, rad, d + 2, sd, (dx, dy, dz, rim, pr) -> {
            if (dy == 0) {
                if (rim) return Material.STONE;
                double p = patch(x + dx, z + dz, sd, 2);
                return p < 0.20 ? Material.COARSE_DIRT : p < 0.35 ? Material.GRAVEL : Material.STONE;
            }
            return dy <= 2 && pr.nextDouble() < 0.3 ? Material.ANDESITE : Material.STONE;
        }, MINE_ORES, 0.15);
        Bore b = tunnel(y - 4, 3, 2, -3, new Frame(Material.OAK_FENCE, Material.OAK_PLANKS, MINE_ORES, true, null, 3));
        // 망루: 2×2 수직 갱 위에 울타리 기둥 네 개, 반 블록 지붕, 사슬에 매단 랜턴
        for (int a = 0; a <= 1; a++) for (int c = 0; c <= 1; c++) for (int k = 0; k < 3; k++) set(x + a, y - k, z + c, Material.AIR);
        for (int[] c : new int[][]{{-1, -1}, {2, -1}, {-1, 2}, {2, 2}}) column(x + c[0], y + 1, z + c[1], 4, Material.OAK_FENCE);
        for (int a = -1; a <= 2; a++) for (int c = -1; c <= 2; c++) set(x + a, y + 5, z + c, Material.OAK_SLAB);
        column(x, y + 2, z, 3, Material.CHAIN);
        set(x, y + 1, z, "lantern[hanging=true]");
        // 갱도 끝: 바닥에 묻힌 용암 한 칸(두 번째 조약돌 생성기용), 그 앞 레일 위 상자 광차, 옆에 랜턴
        int fl = y - 4, lx = b.x(-3, 0), lz = b.z(-3, 0);
        for (int[] n : new int[][]{{b.x(-4, 0), b.z(-4, 0)}, {b.x(-3, -1), b.z(-3, -1)}}) {
            if (!solid(n[0], fl, n[1])) set(n[0], fl, n[1], Material.STONE);
        }
        set(lx, fl - 1, lz, Material.STONE);
        set(lx, fl + 1, lz, Material.AIR);
        set(lx, fl, lz, Material.LAVA);
        set(b.x(-3, 1), fl + 1, b.z(-3, 1), Material.LANTERN);
        StorageMinecart cart = tag(w.spawn(new Location(w, b.x(-2, 0) + 0.5, fl + 1, b.z(-2, 0) + 0.5), StorageMinecart.class));
        loot(cart.getInventory(), 4, MINE_LOOT);
    }

    /** 목장: 소·양·돼지·닭, 건초. 가죽과 양털, 깃털. */
    private void ranch() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        int[] u = toSpawn();
        // 우리 x-4..x+2, z-2..z+2. 문은 시작 섬 쪽
        int gx = u[0] < 0 ? x - 4 : u[0] > 0 ? x + 2 : x - 1, gz = u[1] < 0 ? z - 2 : u[1] > 0 ? z + 2 : z;
        for (int i = x - 4; i <= x + 2; i++) {
            for (int j = z - 2; j <= z + 2; j++) {
                if (i != x - 4 && i != x + 2 && j != z - 2 && j != z + 2) continue;
                if (!tile(i, j)) continue;
                if (i == gx && j == gz) set(i, y + 1, j, "oak_fence_gate[facing=" + (u[0] != 0 ? "east" : "south") + "]");
                else set(i, y + 1, j, Material.OAK_FENCE);
            }
        }
        set(x - 3, y + 1, z - 1, Material.HAY_BLOCK);
        if (fixed()) set(x + 1, y + 1, z + 1, Material.HAY_BLOCK);
        set(x + 1, y + 1, z - 1, "water_cauldron[level=3]");
        int cows = fixed() ? 3 : 2;
        animals(x - 2, y + 1, z - 1, Cow.class, cows);
        mob(x - 2.5, y + 1, z + 1.5, Sheep.class, null);
        mob(x - 0.5, y + 1, z + 1.5, Sheep.class, fixed() ? null : s -> s.setColor(DyeColor.BLACK));
        if (fixed()) mob(x - 1.5, y + 1, z + 0.5, Sheep.class, null);
        mob(x + 0.5, y + 1, z + 0.5, Pig.class, null);
        // 닭장: 울타리 고리 두 칸 높이, 반 블록 지붕, 남쪽에 문
        for (int i = x + 3; i <= x + 5; i++) {
            for (int j = z - 1; j <= z + 1; j++) {
                if (i == x + 4 && j == z) continue;
                for (int k = 1; k <= 2; k++) {
                    if (i == x + 4 && j == z + 1) set(i, y + k, j, k == 1 ? data("oak_fence_gate[facing=south]") : Material.OAK_FENCE.createBlockData());
                    else set(i, y + k, j, Material.OAK_FENCE);
                }
                set(i, y + 3, j, Material.OAK_SLAB);
            }
        }
        set(x + 4, y + 3, z, Material.OAK_SLAB);
        animals(x + 4, y + 1, z, Chicken.class, 1);
        mob(x + 4.3, y + 1, z + 0.3, Chicken.class, null);
        mob(x + 4.7, y + 1, z + 0.7, Chicken.class, null);
    }

    /** 밭: 밀·당근·감자·비트를 처음 얻는 곳. */
    private void farm() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        Material[] crops = {Material.WHEAT, Material.CARROTS, Material.POTATOES, Material.BEETROOTS};
        int row = 0;
        for (int dz = -3; dz <= 3; dz++) {
            for (int dx = -3; dx <= 3; dx++) {
                if (!tile(x + dx, z + dz)) continue;
                if (dz == 0) {
                    set(x + dx, y, z, Material.WATER);
                    continue;
                }
                set(x + dx, y, z + dz, "farmland[moisture=7]");
                ripe(x + dx, y + 1, z + dz, crops[row % 4]);
            }
            if (dz != 0) row++;
        }
        set(x + 4, y + 1, z, Material.COMPOSTER);
        // 허수아비
        column(x - 4, y + 1, z, 2, Material.OAK_FENCE);
        set(x - 4, y + 3, z, Material.HAY_BLOCK);
        set(x - 4, y + 4, z, "carved_pumpkin[facing=east]");
    }

    /** 호박밭: 줄기가 붙은 호박 (줄기가 남아 다시 열린다). */
    private void pumpkin() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        List<int[]> spots = tiles(1);
        gourds(spots, Material.PUMPKIN, "attached_pumpkin_stem", 5 + r.nextInt(3));
        int[] p = takeFree(spots);
        if (p != null) set(p[0], y + 1, p[1], "jack_o_lantern[facing=south]");
        p = takeFree(spots);
        if (p != null) set(p[0], y + 1, p[1], Material.HAY_BLOCK);
    }

    /** 연못: 점토, 모래, 사탕수수, 연잎, 작은 선착장. 낚시하기 좋다. */
    private void pond() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.CLAY, Material.STONE, is.seed(), null, 0);
        double pr = Math.max(2, rad * 0.45);
        int R = (int) Math.ceil(pr) + 1;
        List<int[]> shore = new ArrayList<>();
        for (int dx = -R; dx <= R; dx++) {
            for (int dz = -R; dz <= R; dz++) {
                double dd = dx * dx + dz * dz;
                if (dd <= pr * pr + 0.5) {
                    set(x + dx, y, z + dz, Material.WATER);
                    set(x + dx, y - 1, z + dz, Material.WATER);
                    set(x + dx, y - 2, z + dz, Material.CLAY);
                } else if (dd <= (pr + 1) * (pr + 1) + 0.5 && solid(x + dx, y, z + dz)) {
                    set(x + dx, y, z + dz, Material.SAND);
                    shore.add(new int[]{x + dx, z + dz});
                }
            }
        }
        // 물가 모래에 사탕수수
        int canes = 4 + r.nextInt(3);
        for (int k = 0; k < 30 && canes > 0; k++) {
            int[] p = takeFree(shore);
            if (p == null) break;
            boolean wet = false;
            for (int[] f : FOUR) if (type(p[0] + f[0], y, p[1] + f[1]) == Material.WATER) wet = true;
            if (!wet) continue;
            column(p[0], y + 1, p[1], 2 + r.nextInt(2), Material.SUGAR_CANE);
            canes--;
        }
        // 선착장: 가장자리에서 물 위로 반 블록 세 칸, 물속 울타리 기둥 두 개
        int k = (int) Math.floor(Math.sqrt(pr * pr + 0.5));
        for (int i = 0; i < 3; i++) set(x + k - i, y, z, "oak_slab[type=top,waterlogged=true]");
        set(x + k, y - 1, z, "oak_fence[waterlogged=true]");
        set(x + k - 2, y - 1, z, "oak_fence[waterlogged=true]");
        set(x - 1, y + 1, z + 1, Material.LILY_PAD);
        set(x, y + 1, z - 2, Material.LILY_PAD);
    }

    /** 꽃밭: 꽃 열한 가지, 벌집(벌집 조각)과 벌. 연기 나는 모닥불이 벌을 얌전하게 한다. */
    private void meadow() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        // 손으로 지은 자작나무: 줄기 다섯 칸, 둘레 잎
        column(x + 2, y + 1, z, 5, Material.BIRCH_LOG);
        for (int a = -2; a <= 2; a++)
            for (int b = -2; b <= 2; b++)
                for (int c = -2; c <= 2; c++)
                    if (a * a + b * b + c * c <= 4 && !(a == 0 && c == 0 && b <= 0))
                        set(x + 2 + a, y + 5 + b, z + c, "birch_leaves[persistent=true]");
        set(x + 2, y + 3, z + 1, "bee_nest[facing=south,honey_level=5]");
        set(x + 2, y + 2, z + 1, Material.AIR);
        set(x + 2, y + 1, z + 1, "campfire[lit=true,signal_fire=false]");
        Location hive = new Location(w, x + 2, y + 3, z + 1);
        for (int i = 0; i < 3; i++) mob(x + 2.5, y + 3, z + 2.5, Bee.class, b -> b.setHive(hive));
        flowers((int) (rad * 4), p -> Math.abs(p[0] - (x + 2)) <= 1 && Math.abs(p[1] - (z + 1)) <= 1,
                Material.POPPY, Material.DANDELION, Material.CORNFLOWER, Material.ALLIUM, Material.AZURE_BLUET,
                Material.RED_TULIP, Material.ORANGE_TULIP, Material.WHITE_TULIP, Material.PINK_TULIP,
                Material.OXEYE_DAISY, Material.LILY_OF_THE_VALLEY);
        List<int[]> spots = tiles(1);
        Material[] bushes = {Material.LILAC, r.nextBoolean() ? Material.ROSE_BUSH : Material.PEONY};
        for (Material m : bushes) {
            int[] p = takeFree(spots);
            if (p != null && air(p[0], y + 2, p[1])) tall(p[0], p[1], m);
        }
    }

    /** 버섯 섬: 큰 버섯, 균사체, 무시룸. 몬스터가 나오지 않는다. */
    private void mushroom() {
        blob(x, y, z, rad, d, Material.MYCELIUM, Material.DIRT, Material.STONE, is.seed(), null, 0);
        List<int[]> spots = tiles(1);
        grow(spots, TreeType.RED_MUSHROOM, Material.RED_MUSHROOM);
        grow(spots, TreeType.BROWN_MUSHROOM, Material.BROWN_MUSHROOM);
        for (int i = 0; i < 4; i++) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y + 1, p[1], i < 2 ? Material.RED_MUSHROOM : Material.BROWN_MUSHROOM);
        }
        int[] p = takeFree(spots);
        if (p != null) mob(p[0] + 0.5, y + 1, p[1] + 0.5, MushroomCow.class, null);
    }

    /** 사막: 모래(유리), 선인장, 오아시스의 사탕수수, 야자수. */
    private void desert() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> dy == 0 && !rim ? Material.SAND : Material.SANDSTONE, null, 0);
        // 오아시스: 3×3 물
        int ox = x - 1, oz = z + 1;
        for (int a = -1; a <= 1; a++)
            for (int c = -1; c <= 1; c++) {
                set(ox + a, y, oz + c, Material.WATER);
                set(ox + a, y - 1, oz + c, Material.SANDSTONE);
            }
        palm(ox + 3, oz - 1);
        int canes = 3 + r.nextInt(2);
        for (int[] c : new int[][]{{-2, -1}, {-2, 1}, {2, 1}, {-1, 2}, {1, 2}, {0, -2}}) {
            if (canes == 0) break;
            int px = ox + c[0], pz = oz + c[1];
            if (!tile(px, pz) || type(px, y, pz) != Material.SAND) continue;
            column(px, y + 1, pz, 2 + r.nextInt(2), Material.SUGAR_CANE);
            canes--;
        }
        List<int[]> spots = tiles(1);
        int cacti = 3 + r.nextInt(2);
        for (int k = 0; k < 40 && cacti > 0; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (type(p[0], y, p[1]) != Material.SAND) continue;
            int h = 2 + r.nextInt(2);
            boolean clear = true;
            for (int i = 1; i <= h && clear; i++)
                for (int[] f : FOUR) if (!air(p[0] + f[0], y + i, p[1] + f[1])) clear = false;
            if (!clear) continue;
            column(p[0], y + 1, p[1], h, Material.CACTUS);
            // 옆에 무엇이 놓이면 선인장이 부서지므로 둘레를 비워 둔다
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 1 && Math.abs(q[1] - p[1]) <= 1);
            cacti--;
        }
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(spots);
            if (p != null && type(p[0], y, p[1]) == Material.SAND) set(p[0], y + 1, p[1], Material.DEAD_BUSH);
        }
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p != null) mob(p[0] + 0.5, y + 1, p[1] + 0.5, Rabbit.class, b -> b.setRabbitType(Rabbit.Type.GOLD));
        }
    }

    /** 거미굴: 이끼 낀 돌 둥지 속 거미 생성기, 거미줄. 실과 거미 눈. */
    private void spiderDen() {
        long sd = is.seed();
        blob(x, y, z, rad, d, sd, (dx, dy, dz, rim, pr) -> {
            if (dy > 0) return dy <= 2 ? Material.COBBLESTONE : Material.STONE;
            double p = patch(x + dx, z + dz, sd, 2);
            return p < 0.3 ? Material.COARSE_DIRT : p < 0.4 ? Material.MOSSY_COBBLESTONE : Material.GRASS_BLOCK;
        }, null, 0);
        List<int[]> inside = new ArrayList<>();
        for (int dx = -4; dx <= 4; dx++)
            for (int dz = -4; dz <= 4; dz++)
                for (int dy = 1; dy <= 3; dy++) {
                    double dd = Math.sqrt(dx * dx + dy * dy + dz * dz);
                    if (dd > 3.5) continue;
                    if (dd > 2.5) set(x + dx, y + dy, z + dz, r.nextDouble() < 0.6 ? Material.COBBLESTONE : Material.MOSSY_COBBLESTONE);
                    else {
                        set(x + dx, y + dy, z + dz, Material.AIR);
                        inside.add(new int[]{x + dx, y + dy, z + dz});
                    }
                }
        // 입구 두 개를 직각으로 내서 안을 어둡게 둔다
        for (int k = 2; k <= 3; k++)
            for (int h = 1; h <= 2; h++) {
                set(x + k, y + h, z, Material.AIR);
                set(x, y + h, z + k, Material.AIR);
            }
        spawner(x, y + 1, z, EntityType.SPIDER);
        loot(chest(x - 1, y + 1, z - 1, BlockFace.SOUTH), 4 + r.nextInt(2), SPIDER_LOOT);
        int webs = 10;
        while (webs > 0 && !inside.isEmpty()) {
            int[] c = inside.remove(r.nextInt(inside.size()));
            if (!air(c[0], c[1], c[2])) continue;
            if (c[1] == y + 1 && ((c[0] > x && c[2] == z) || (c[0] == x && c[2] > z))) continue;
            set(c[0], c[1], c[2], Material.COBWEB);
            webs--;
        }
        int outer = 6;
        for (int dx = -2; dx <= 2 && outer > 0; dx++)
            for (int dz = -2; dz <= 2 && outer > 0; dz++)
                if ((dx + dz) % 2 == 0 && solid(x + dx, y + 3, z + dz) && air(x + dx, y + 4, z + dz)) {
                    set(x + dx, y + 4, z + dz, Material.COBWEB);
                    outer--;
                }
        for (int[] p : tiles(1)) {
            if (dist(p[0], p[1]) > Math.max(4.5, rad * 0.6) && tile(p[0], p[1])) {
                column(p[0], y + 1, p[1], 2, Material.DARK_OAK_LOG);
                break;
            }
        }
    }

    // ------------------------------------------------------------------ 서리

    /** 가문비 숲: 가문비나무, 달콤한 열매, 고사리. 눈이 내린다. */
    private void taiga() {
        long sd = is.seed();
        blob(x, y, z, rad, d, sd, (dx, dy, dz, rim, pr) -> dy == 0
                ? (patch(x + dx, z + dz, sd, 2) < 0.25 ? Material.PODZOL : Material.SNOW_BLOCK)
                : dy <= 2 ? Material.DIRT : Material.STONE, null, 0);
        List<int[]> spots = tiles(2);
        for (int i = 0; i < 3; i++) {
            if (i == 0 && rad > 8) {
                int[] p = takeFree(spots);
                if (p != null && tile(p[0] + 1, p[1]) && tile(p[0], p[1] + 1) && tile(p[0] + 1, p[1] + 1)) {
                    for (int a = 0; a <= 1; a++) for (int b = 0; b <= 1; b++) set(p[0] + a, y, p[1] + b, Material.PODZOL);
                    if (grow(p[0], p[1], TreeType.MEGA_REDWOOD)) {
                        spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 3 && Math.abs(q[1] - p[1]) <= 3);
                        continue;
                    }
                }
            }
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], Material.PODZOL);
            if (!grow(p[0], p[1], i % 2 == 0 ? TreeType.TALL_REDWOOD : TreeType.REDWOOD)
                    && !grow(p[0], p[1], TreeType.REDWOOD)) set(p[0], y + 1, p[1], Material.SPRUCE_SAPLING);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 2 && Math.abs(q[1] - p[1]) <= 2);
        }
        List<int[]> ground = tiles(1);
        for (int i = 0; i < 7; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            set(p[0], y, p[1], Material.PODZOL);
            if (i < 3) set(p[0], y + 1, p[1], "sweet_berry_bush[age=3]");
            else if (r.nextBoolean() && air(p[0], y + 2, p[1])) tall(p[0], p[1], Material.LARGE_FERN);
            else set(p[0], y + 1, p[1], Material.FERN);
        }
        boulder(ground, Material.MOSSY_COBBLESTONE);
        snowLayer();
    }

    /** 얼음 호수: 얼음 밑 물, 얼음낚시 구멍, 눈사람. */
    private void frozenLake() {
        blob(x, y, z, rad, d, Material.SNOW_BLOCK, Material.STONE, Material.STONE, is.seed(), null, 0);
        disc(x, y, z, rad * 0.6, Material.ICE);
        disc(x, y - 1, z, rad * 0.55, Material.WATER);
        disc(x, y - 2, z, rad * 0.55, Material.WATER);
        disc(x, y - 3, z, rad * 0.55, Material.STONE);
        // 얼음낚시 구멍: 가장자리 얼음 한 칸을 물로, 옆 눈 위에 열린 뚜껑문과 통
        int k = (int) Math.floor(Math.sqrt(rad * 0.6 * rad * 0.6 + 0.5));
        set(x + k, y, z, Material.WATER);
        set(x + k, y - 1, z, Material.WATER);
        if (tile(x + k + 1, z)) set(x + k + 1, y + 1, z, "spruce_trapdoor[open=true,facing=east,half=bottom]");
        if (tile(x + k + 1, z + 1)) set(x + k + 1, y + 1, z + 1, Material.BARREL);
        List<int[]> shore = tiles(1);
        shore.removeIf(p -> type(p[0], y, p[1]) != Material.SNOW_BLOCK);
        int[] p = takeFree(shore);
        if (p != null) mob(p[0] + 0.5, y + 1, p[1] + 0.5, Snowman.class, null);
        int n = 2 + r.nextInt(2);
        for (int i = 0; i < n; i++) {
            int[] q = takeFree(shore);
            if (q == null) break;
            set(q[0], y, q[1], Material.PODZOL);
            if (!grow(q[0], q[1], TreeType.REDWOOD)) set(q[0], y + 1, q[1], Material.SPRUCE_SAPLING);
            shore.removeIf(o -> Math.abs(o[0] - q[0]) <= 2 && Math.abs(o[1] - q[1]) <= 2);
        }
    }

    private static final Material[] FROST_ORES = {Material.LAPIS_ORE, Material.LAPIS_ORE, Material.LAPIS_ORE, Material.LAPIS_ORE,
            Material.LAPIS_ORE, Material.LAPIS_ORE, Material.LAPIS_ORE, Material.IRON_ORE, Material.IRON_ORE, Material.IRON_ORE,
            Material.IRON_ORE, Material.IRON_ORE, Material.COAL_ORE, Material.COAL_ORE, Material.COAL_ORE, Material.COAL_ORE,
            Material.COAL_ORE, Material.DIAMOND_ORE, Material.DIAMOND_ORE, Material.DIAMOND_ORE};

    /** 서리 광산: 청금석·다이아몬드. 영혼 등이 달린 가문비나무 갱도. */
    private void frostMine() {
        blob(x, y, z, rad, d + 2, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return pr.nextDouble() < 0.7 ? Material.SNOW_BLOCK : Material.STONE;
            if (dy <= 2) return pr.nextDouble() < 0.15 ? Material.PACKED_ICE : Material.STONE;
            return Material.STONE;
        }, FROST_ORES, 0.13);
        tunnel(y - 4, 3, 2, -2, new Frame(Material.SPRUCE_FENCE, Material.SPRUCE_PLANKS, FROST_ORES, true, "soul_lantern", 1));
        List<int[]> spots = tiles(2);
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            spike(p[0], y + 1, p[1], 3 + r.nextInt(2), Material.BLUE_ICE, null);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 3 && Math.abs(q[1] - p[1]) <= 3);
        }
    }

    /** 얼음 가시: 높이 솟은 단단한 얼음과 푸른 얼음. */
    private void iceSpike() {
        blob(x, y, z, rad, d, Material.SNOW_BLOCK, Material.PACKED_ICE, Material.PACKED_ICE, is.seed(),
                new Material[]{Material.BLUE_ICE}, 0.08);
        spike(x, y + 1, z, 10 + r.nextInt(6), Material.PACKED_ICE, Material.BLUE_ICE);
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> dist(p[0], p[1]) < 3);
        int n = 2 + r.nextInt(2);
        for (int i = 0; i < n; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            spike(p[0], y + 1, p[1], 3 + r.nextInt(4), r.nextBoolean() ? Material.PACKED_ICE : Material.BLUE_ICE, null);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 3 && Math.abs(q[1] - p[1]) <= 3);
        }
    }

    /** 이글루: 눈 집 바닥 뚜껑문 아래 지하실. 상자에 섬세한 손길 곡괭이. */
    private void igloo() {
        blob(x, y, z, rad, d + 5, Material.SNOW_BLOCK, Material.PACKED_ICE, Material.STONE, is.seed(), null, 0);
        for (int dx = -3; dx <= 3; dx++)
            for (int dy = 0; dy <= 3; dy++)
                for (int dz = -3; dz <= 3; dz++) {
                    double dd = Math.sqrt(dx * dx + dy * dy * 1.6 + dz * dz);
                    if (dd <= 3.2 && dd > 2.2) set(x + dx, y + 1 + dy, z + dz, Material.SNOW_BLOCK);
                }
        set(x, y + 1, z + 3, Material.AIR);
        set(x, y + 2, z + 3, Material.AIR);
        set(x + 2, y + 1, z, "furnace[facing=west]");
        set(x - 2, y + 1, z, Material.CRAFTING_TABLE);
        set(x - 1, y + 1, z - 1, Material.LANTERN);
        // 지하실: 돌벽돌 상자 속 3×3×3 방, 사다리로 내려간다
        for (int a = -2; a <= 2; a++)
            for (int c = -2; c <= 2; c++)
                for (int yy = y - 6; yy <= y - 2; yy++) {
                    boolean shell = Math.abs(a) == 2 || Math.abs(c) == 2 || yy == y - 6 || yy == y - 2;
                    set(x + a, yy, z + c, shell ? Material.STONE_BRICKS : Material.AIR);
                }
        set(x, y, z - 1, "spruce_trapdoor[half=top,facing=south]");
        for (int yy = y - 5; yy <= y - 1; yy++) set(x, yy, z - 1, "ladder[facing=south]");
        set(x - 1, y - 5, z + 1, Material.BREWING_STAND);
        set(x + 1, y - 5, z + 1, Material.CAULDRON);
        set(x + 1, y - 5, z - 1, Material.LANTERN);
        loot(chest(x - 1, y - 5, z - 1, BlockFace.SOUTH), 4, IGLOO_LOOT, silkPickaxe());
    }

    // ------------------------------------------------------------------ 화염

    /** 현무암 삼각주: 현무암 기둥, 마그마로 둘러싼 용암. */
    private void basalt() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) ->
                dy == 0 && pr.nextDouble() < 0.7 ? Material.BASALT : Material.BLACKSTONE, new Material[]{Material.MAGMA_BLOCK}, 0.12);
        List<int[]> spots = tiles(2);
        int pools = 3 + r.nextInt(2);
        for (int k = 0; k < 30 && pools > 0; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], Material.LAVA);
            for (int[] f : FOUR) set(p[0] + f[0], y, p[1] + f[1], Material.MAGMA_BLOCK);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 1 && Math.abs(q[1] - p[1]) <= 1);
            pools--;
        }
        int cols = 5 + r.nextInt(3);
        for (int i = 0; i < cols; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            for (int k = 1; k <= 2 + r.nextInt(6); k++) set(p[0], y + k, p[1], "basalt[axis=y]");
        }
    }

    /** 진홍 숲: 진홍 버섯나무, 네더 사마귀 블록, 버섯불, 늘어진 덩굴. */
    private void crimson() {
        blob(x, y, z, rad, d, Material.CRIMSON_NYLIUM, Material.NETHERRACK, Material.NETHERRACK, is.seed(),
                new Material[]{Material.NETHER_WART_BLOCK}, 0.10);
        List<int[]> spots = tiles(2);
        int n = rad > 7.5 ? 2 : 1;
        for (int i = 0; i < n; i++) grow(spots, TreeType.CRIMSON_FUNGUS, Material.CRIMSON_FUNGUS);
        List<int[]> ground = tiles(1);
        for (int i = 0; i < 7; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            set(p[0], y + 1, p[1], i < 4 ? Material.CRIMSON_ROOTS : Material.CRIMSON_FUNGUS);
        }
        int[] p = takeFree(ground);
        if (p != null) set(p[0], y, p[1], Material.SHROOMLIGHT);
        List<int[]> eaves = eaves();
        int strands = 2 + r.nextInt(3);
        for (int i = 0; i < strands; i++) {
            int[] e = take(eaves);
            if (e == null) break;
            hang(e[0], y - 1, e[1], 3 + r.nextInt(3), "weeping_vines_plant", "weeping_vines");
        }
    }

    /** 뒤틀린 숲: 뒤틀린 버섯나무, 뿌리, 꼬인 덩굴. */
    private void warped() {
        blob(x, y, z, rad, d, Material.WARPED_NYLIUM, Material.NETHERRACK, Material.NETHERRACK, is.seed(), null, 0);
        grow(tiles(2), TreeType.WARPED_FUNGUS, Material.WARPED_FUNGUS);
        List<int[]> ground = tiles(1);
        for (int i = 0; i < 9; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            if (i < 3) set(p[0], y + 1, p[1], Material.WARPED_ROOTS);
            else if (i < 7) set(p[0], y + 1, p[1], Material.NETHER_SPROUTS);
            else {
                int h = 2 + r.nextInt(2);
                for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], k == h ? "twisting_vines" : "twisting_vines_plant");
            }
        }
    }

    /** 영혼 골짜기: 거대한 갈비뼈(뼈 블록), 영혼 모래의 네더 사마귀, 영혼 불. */
    private void soulValley() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return pr.nextDouble() < 0.6 ? Material.SOUL_SOIL : Material.SOUL_SAND;
            if (dy <= 2) return Material.SOUL_SAND;
            return pr.nextBoolean() ? Material.BLACKSTONE : Material.BASALT;
        }, null, 0);
        boolean alongX = r.nextBoolean();
        int arches = 3 + r.nextInt(2);
        int lampAt = r.nextInt(arches);
        for (int i = 0; i < arches; i++) {
            int a = (i - (arches - 1) / 2) * 2;
            int h = 4 + r.nextInt(3);
            for (int sgn : new int[]{-1, 1}) {
                int bx = alongX ? x + a : x + 2 * sgn, bz = alongX ? z + 2 * sgn : z + a;
                for (int k = 1; k <= h; k++) set(bx, y + k, bz, "bone_block[axis=y]");
                int cx = alongX ? x + a : x + sgn, cz = alongX ? z + sgn : z + a;
                set(cx, y + h + 1, cz, "bone_block[axis=" + (alongX ? "z" : "x") + "]");
            }
            int tx = alongX ? x + a : x, tz = alongX ? z : z + a;
            set(tx, y + h + 2, tz, "bone_block[axis=" + (alongX ? "z" : "x") + "]");
            if (i == lampAt) {
                set(tx, y + h + 1, tz, Material.CHAIN);
                set(tx, y + h, tz, "soul_lantern[hanging=true]");
            }
        }
        List<int[]> spots = tiles(1);
        int warts = 4, fires = 2;
        for (int k = 0; k < 60 && (warts > 0 || fires > 0); k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (warts > 0) {
                set(p[0], y, p[1], Material.SOUL_SAND);
                set(p[0], y + 1, p[1], "nether_wart[age=3]");
                warts--;
            } else if (type(p[0], y, p[1]) == Material.SOUL_SOIL) {
                set(p[0], y + 1, p[1], Material.SOUL_FIRE);
                fires--;
            }
        }
    }

    /** 블레이즈 요새: 네더 벽돌 방과 블레이즈 생성기, 끊어진 다리, 네더 사마귀. */
    private void fortress() {
        blob(x, y, z, rad, d, Material.NETHER_BRICKS, Material.NETHERRACK, Material.BLACKSTONE, is.seed(), null, 0);
        for (int dx = -2; dx <= 2; dx++)
            for (int dz = -2; dz <= 2; dz++) {
                boolean edge = Math.abs(dx) == 2 || Math.abs(dz) == 2;
                if (edge && (dx + dz) % 2 == 0) column(x + dx, y + 1, z + dz, 3, Material.NETHER_BRICK_FENCE);
                set(x + dx, y + 4, z + dz, Material.NETHER_BRICKS);
            }
        spawner(x, y + 1, z, EntityType.BLAZE);
        loot(chest(x + 1, y + 1, z + 1, BlockFace.SOUTH), 4 + r.nextInt(3), FORTRESS_LOOT);
        // 시작 섬 반대쪽으로 끊어진 다리
        int[] u = toSpawn(), a = {-u[0], -u[1]}, v = side(u);
        int e = edge(a), len = 6 + r.nextInt(3);
        for (int t = e + 1; t <= e + len; t++) {
            boolean ragged = t > e + len - 2;
            for (int s = -1; s <= 1; s++) {
                if (ragged && r.nextBoolean()) continue;
                int bx = x + a[0] * t + v[0] * s, bz = z + a[1] * t + v[1] * s;
                set(bx, y, bz, Material.NETHER_BRICKS);
                if (s != 0 && !(ragged && r.nextBoolean())) set(bx, y + 1, bz, Material.NETHER_BRICK_FENCE);
            }
        }
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> Math.abs(p[0] - x) <= 3 && Math.abs(p[1] - z) <= 3);
        for (int k = 0; k < 20; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (!tile(p[0] + 1, p[1]) || !tile(p[0], p[1] + 1) || !tile(p[0] + 1, p[1] + 1)) continue;
            for (int i = 0; i <= 1; i++)
                for (int j = 0; j <= 1; j++) {
                    set(p[0] + i, y, p[1] + j, Material.SOUL_SAND);
                    set(p[0] + i, y + 1, p[1] + j, "nether_wart[age=3]");
                }
            break;
        }
    }

    /** 화산: 마그마와 흑요석 원뿔, 꼭대기 용암 호수. 속 동굴의 뾰족한 점적석이 가마솥에 용암을 떨군다. */
    private void volcano() {
        blob(x, y, z, rad, d, Material.BLACKSTONE, Material.BASALT, Material.BLACKSTONE, is.seed(), new Material[]{Material.OBSIDIAN}, 0.12);
        int H = 6 + r.nextInt(3);
        double base = rad * 0.8;
        for (int k = 0; k < H; k++) {
            double lr = base - (base - 2.5) * k / (H - 1);
            int R = (int) Math.ceil(lr);
            for (int dx = -R; dx <= R; dx++)
                for (int dz = -R; dz <= R; dz++) {
                    if (dx * dx + dz * dz > lr * lr + 0.5) continue;
                    double p = r.nextDouble();
                    set(x + dx, y + 1 + k, z + dz, p < 0.5 ? Material.BLACKSTONE : p < 0.8 ? Material.BASALT
                            : p < 0.9 ? Material.MAGMA_BLOCK : Material.OBSIDIAN);
                }
        }
        int Y = y + H;
        // 분화구: 3×3 용암, 둘레 흑요석 고리, 우는 흑요석 두 개
        List<int[]> ring = new ArrayList<>();
        for (int dx = -2; dx <= 2; dx++)
            for (int dz = -2; dz <= 2; dz++) {
                if (Math.abs(dx) <= 1 && Math.abs(dz) <= 1) {
                    set(x + dx, Y, z + dz, Material.LAVA);
                    set(x + dx, Y - 1, z + dz, Material.BASALT);
                } else if (dx * dx + dz * dz <= 6.75) {
                    set(x + dx, Y, z + dz, Material.OBSIDIAN);
                    ring.add(new int[]{x + dx, z + dz});
                }
            }
        for (int i = 0; i < 2; i++) {
            int[] p = take(ring);
            set(p[0], Y, p[1], Material.CRYING_OBSIDIAN);
        }
        // 속 동굴: 분화구 바닥에 매달린 점적석 아래 가마솥 (용암이 조금씩 고인다)
        for (int dx = -1; dx <= 1; dx++)
            for (int dz = -1; dz <= 1; dz++)
                for (int yy = y + 1; yy <= Y - 2; yy++) set(x + dx, yy, z + dz, Material.AIR);
        set(x, Y - 2, z, "pointed_dripstone[vertical_direction=down,thickness=frustum]");
        set(x, Y - 3, z, "pointed_dripstone[vertical_direction=down,thickness=tip]");
        set(x, y + 1, z, Material.CAULDRON);
        int[] u = toSpawn();
        for (int t = 2; t <= (int) Math.ceil(base) + 1; t++)
            for (int k = 1; k <= 2; k++) set(x + u[0] * t, y + k, z + u[1] * t, Material.AIR);
        // 시작 섬 반대쪽 가장자리에서 용암이 흘러내린다
        fall(new int[]{-u[0], -u[1]}, Material.LAVA);
    }

    /** 네더 광맥: 석영과 네더 금. 속 동굴 천장에 발광석이 매달려 있다. */
    private void netherVein() {
        blob(x, y, z, rad, d, Material.NETHERRACK, Material.NETHERRACK, Material.NETHERRACK, is.seed(),
                new Material[]{Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE,
                        Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE,
                        Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE,
                        Material.NETHER_QUARTZ_ORE, Material.NETHER_QUARTZ_ORE, Material.NETHER_GOLD_ORE,
                        Material.NETHER_GOLD_ORE, Material.NETHER_GOLD_ORE, Material.NETHER_GOLD_ORE, Material.NETHER_GOLD_ORE,
                        Material.NETHER_GOLD_ORE, Material.NETHER_GOLD_ORE, Material.GILDED_BLACKSTONE, Material.GILDED_BLACKSTONE},
                0.18);
        // 속 동굴: 5×5×3, 바닥 y-5
        for (int dx = -2; dx <= 2; dx++)
            for (int dz = -2; dz <= 2; dz++) {
                for (int yy = y - 4; yy <= y - 2; yy++) set(x + dx, yy, z + dz, Material.AIR);
                set(x + dx, y - 5, z + dz, Material.NETHERRACK);
            }
        Bore b = tunnel(y - 5, 2, 2, 0, null);
        Set<Long> path = new HashSet<>();
        for (int t = -3; t < b.mouth(); t++) for (int s = 0; s <= 1; s++) path.add(key(b.x(t, s), 0, b.z(t, s)));
        // 천장 발광석 덩어리 (굴이 지나는 줄은 비운다)
        List<int[]> ceil = new ArrayList<>();
        for (int dx = -2; dx <= 2; dx++)
            for (int dz = -2; dz <= 2; dz++)
                if (!path.contains(key(x + dx, 0, z + dz))) ceil.add(new int[]{x + dx, z + dz});
        int glow = 12 + r.nextInt(3);
        while (glow > 0 && !ceil.isEmpty()) {
            int[] c = take(ceil);
            int n = Math.min(glow, 2 + r.nextInt(3));
            for (int i = 0; i < n; i++) {
                int[] f = i == 0 ? new int[]{0, 0} : FOUR[r.nextInt(4)];
                int gx = c[0] + f[0], gz = c[1] + f[1];
                if (path.contains(key(gx, 0, gz)) || Math.abs(gx - x) > 2 || Math.abs(gz - z) > 2) continue;
                if (type(gx, y - 2, gz) == Material.GLOWSTONE) continue;
                set(gx, y - 2, gz, Material.GLOWSTONE);
                glow--;
                if (glow > 0 && r.nextBoolean() && air(gx, y - 3, gz)) {
                    set(gx, y - 3, gz, Material.GLOWSTONE);
                    glow--;
                }
            }
        }
        // 동굴 벽에 드러난 석영
        int quartz = 3 + r.nextInt(2);
        for (int k = 0; k < 40 && quartz > 0; k++) {
            int[] f = FOUR[r.nextInt(4)];
            int along = r.nextInt(5) - 2;
            int qx = f[0] != 0 ? x + 3 * f[0] : x + along, qz = f[1] != 0 ? z + 3 * f[1] : z + along;
            int qy = y - 4 + r.nextInt(3);
            if (type(qx, qy, qz) != Material.NETHERRACK) continue;
            set(qx, qy, qz, Material.NETHER_QUARTZ_ORE);
            quartz--;
        }
        // 밑면 장식 발광석 두 덩이
        List<int[]> under = new ArrayList<>();
        int R = (int) Math.ceil(rad);
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                int by = bottom(x + dx, z + dz);
                if (by != Integer.MIN_VALUE && by < y - 3) under.add(new int[]{x + dx, by, z + dz});
            }
        for (int i = 0; i < 2 && !under.isEmpty(); i++) {
            int[] c = under.remove(r.nextInt(under.size()));
            int n = 2 + r.nextInt(2);
            for (int k = 0; k < n; k++) set(c[0] + (k == 2 ? 1 : 0), c[1] - 1 - (k == 1 ? 1 : 0), c[2], Material.GLOWSTONE);
        }
        // 윗면: 꺼지지 않는 불, 드러난 석영
        List<int[]> spots = tiles(2);
        int fires = 3 + r.nextInt(2);
        for (int i = 0; i < fires + 3; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (i < fires) set(p[0], y + 1, p[1], Material.FIRE);
            else set(p[0], y, p[1], Material.NETHER_QUARTZ_ORE);
        }
    }

    // ------------------------------------------------------------------ 공허

    /** 코러스 숲: 엔드 돌 위 코러스 나무 (코러스 열매). */
    private void chorus() {
        blob(x, y, z, rad, d, Material.END_STONE, Material.END_STONE, Material.END_STONE, is.seed(), new Material[]{Material.OBSIDIAN}, 0.04);
        List<int[]> spots = tiles(1);
        int n = 3 + r.nextInt(3);
        for (int i = 0; i < n; i++) grow(spots, TreeType.CHORUS_PLANT, Material.CHORUS_FLOWER);
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y + 1, p[1], Material.CHORUS_FLOWER);
        }
    }

    /** 자수정 정동: 위가 열린 자수정 그릇, 싹트는 자수정과 송이. */
    private void geode() {
        blob(x, y, z, rad, d, Material.CALCITE, Material.SMOOTH_BASALT, Material.SMOOTH_BASALT, is.seed(), null, 0);
        int cy = y - 1;
        List<int[]> walls = new ArrayList<>();
        for (int dx = -5; dx <= 5; dx++)
            for (int dz = -5; dz <= 5; dz++)
                for (int dy = -5; dy <= 1; dy++) {
                    double dd = Math.sqrt(dx * dx + dy * dy + dz * dz);
                    if (dd > 4.2) continue;
                    int px = x + dx, py = cy + dy, pz = z + dz;
                    if (dd > 3.6) set(px, py, pz, Material.SMOOTH_BASALT);
                    else if (dd > 3.0) set(px, py, pz, Material.CALCITE);
                    else if (dd > 2.4) {
                        set(px, py, pz, r.nextInt(5) == 0 ? Material.BUDDING_AMETHYST : Material.AMETHYST_BLOCK);
                        walls.add(new int[]{px, py, pz});
                    } else set(px, py, pz, Material.AIR);
                }
        // 자수정 송이: 벽에서 빈 쪽을 보게
        int clusters = 4 + r.nextInt(3), buds = 2 + r.nextInt(2);
        BlockFace[] faces = {BlockFace.UP, BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST, BlockFace.DOWN};
        for (int k = 0; k < 200 && (clusters > 0 || buds > 0) && !walls.isEmpty(); k++) {
            int[] c = walls.remove(r.nextInt(walls.size()));
            for (BlockFace f : faces) {
                int ax = c[0] + f.getModX(), ay = c[1] + f.getModY(), az = c[2] + f.getModZ();
                if (!air(ax, ay, az) || ay > y) continue;
                String what = clusters > 0 ? "amethyst_cluster" : "large_amethyst_bud";
                set(ax, ay, az, what + "[facing=" + f.name().toLowerCase(Locale.ROOT) + "]");
                if (clusters > 0) clusters--;
                else buds--;
                break;
            }
        }
    }

    /** 흑요석 첨탑: 우는 흑요석이 박힌 기둥, 꼭대기 쇠창살 우리 속 엔드 막대기. */
    private void obsidianSpire() {
        blob(x, y, z, rad, d, Material.END_STONE, Material.OBSIDIAN, Material.END_STONE, is.seed(), null, 0);
        int H = 12 + r.nextInt(7);
        for (int dx = -1; dx <= 1; dx++) for (int dz = -1; dz <= 1; dz++) column(x + dx, y + 1, z + dz, H, Material.OBSIDIAN);
        int cry = 3 + r.nextInt(2);
        for (int i = 0; i < cry; i++) {
            int[] f = FOUR[r.nextInt(4)];
            int along = r.nextInt(3) - 1;
            int px = f[0] != 0 ? x + f[0] : x + along, pz = f[1] != 0 ? z + f[1] : z + along;
            int py = y + 2 + r.nextInt(H - 2);
            if (type(px, py, pz) == Material.CRYING_OBSIDIAN) {
                i--;
                continue;
            }
            set(px, py, pz, Material.CRYING_OBSIDIAN);
        }
        int top = y + H;
        for (int k = 1; k <= 2; k++)
            for (int dx = -1; dx <= 1; dx++)
                for (int dz = -1; dz <= 1; dz++)
                    if (dx != 0 || dz != 0) set(x + dx, top + k, z + dz, Material.IRON_BARS);
        set(x, top + 1, z, "end_rod[facing=up]");
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> Math.abs(p[0] - x) <= 2 && Math.abs(p[1] - z) <= 2);
        int rubble = 4 + r.nextInt(3);
        for (int i = 0; i < rubble; i++) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y + 1, p[1], Material.OBSIDIAN);
        }
    }

    /** 퍼퍼 폐허: 무너진 퍼퍼 탑, 자홍색 창, 엔드 막대기. 상자에 엔더 진주. */
    private void purpurRuin() {
        blob(x, y, z, rad, d, Material.END_STONE_BRICKS, Material.END_STONE, Material.END_STONE, is.seed(), null, 0);
        int H = 6 + r.nextInt(3);
        int[] u = toSpawn();
        for (int dx = -2; dx <= 2; dx++)
            for (int dz = -2; dz <= 2; dz++) {
                boolean corner = Math.abs(dx) == 2 && Math.abs(dz) == 2;
                if (Math.abs(dx) != 2 && Math.abs(dz) != 2) continue;
                // 문: 시작 섬 쪽 벽 가운데
                boolean door = dx == 2 * u[0] && dz == 2 * u[1];
                boolean window = !corner && (Math.abs(dx) == 2 ? Math.abs(dz) == 1 : Math.abs(dx) == 1);
                for (int k = 1; k <= H; k++) {
                    if (door && k <= 2) continue;
                    if (window && k == 3) {
                        set(x + dx, y + k, z + dz, Material.MAGENTA_STAINED_GLASS);
                        continue;
                    }
                    if (!corner && r.nextDouble() < 0.2) continue;
                    set(x + dx, y + k, z + dz, corner ? Material.PURPUR_PILLAR : Material.PURPUR_BLOCK);
                }
                // 무너진 꼭대기: 반 블록과 계단이 듬성듬성
                if (corner) set(x + dx, y + H + 1, z + dz, "end_rod[facing=up]");
                else if (r.nextBoolean()) {
                    set(x + dx, y + H + 1, z + dz, r.nextBoolean() ? data("purpur_slab[type=bottom]")
                            : data("purpur_stairs[facing=" + face(new int[]{Integer.signum(dx), Integer.signum(dz)}) + "]"));
                }
            }
        loot(chest(x - 1, y + 1, z - 1, BlockFace.SOUTH), 4 + r.nextInt(3), PURPUR_LOOT);
    }

    // ------------------------------------------------------------------ 바다

    /** 해변: 모래와 자갈(부싯돌), 물웅덩이의 해초, 떠밀려 온 나무, 거북과 거북알. */
    private void beach() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> dy == 0 && !rim ? Material.SAND : Material.SANDSTONE, null, 0);
        int[] a = FOUR[r.nextInt(4)], v = side(a);
        int e = edge(a);
        for (int t = 0; t <= e; t++)
            for (int s = -1; s <= 1; s++) {
                int px = x + a[0] * t + v[0] * s, pz = z + a[1] * t + v[1] * s;
                if (type(px, y, pz) == Material.SAND) set(px, y, pz, Material.GRAVEL);
            }
        // 물웅덩이 2×3: 자갈 반대쪽
        int ox = x - a[0] * 3 - v[0], oz = z - a[1] * 3 - v[1];
        List<int[]> pool = new ArrayList<>();
        for (int i = 0; i < 2; i++) for (int j = 0; j < 3; j++) pool.add(new int[]{ox + v[0] * i + a[0] * j, oz + v[1] * i + a[1] * j});
        boolean ok = true;
        for (int[] p : pool) for (int[] f : FOUR) if (!solid(p[0] + f[0], y, p[1] + f[1])) ok = false;
        if (ok) {
            for (int i = 0; i < pool.size(); i++) {
                int[] p = pool.get(i);
                set(p[0], y - 1, p[1], Material.SANDSTONE);
                set(p[0], y, p[1], i % 3 == 1 ? Material.SEAGRASS : Material.WATER);
            }
            int canes = 3;
            for (int[] p : pool) {
                for (int[] f : FOUR) {
                    int qx = p[0] + f[0], qz = p[1] + f[1];
                    if (canes > 0 && type(qx, y, qz) == Material.SAND && tile(qx, qz)) {
                        column(qx, y + 1, qz, 2 + r.nextInt(2), Material.SUGAR_CANE);
                        canes--;
                    }
                }
            }
        }
        List<int[]> spots = tiles(1);
        // 떠밀려 온 나무 (껍질 벗긴 참나무 4칸)
        for (int k = 0; k < 20; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            boolean row = true;
            for (int i = 1; i <= 3; i++) if (!tile(p[0] + i, p[1])) row = false;
            if (!row) continue;
            for (int i = 0; i <= 3; i++) set(p[0] + i, y + 1, p[1], "stripped_oak_log[axis=x]");
            break;
        }
        int eggs = 2;
        for (int k = 0; k < 30 && eggs > 0; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (type(p[0], y, p[1]) != Material.SAND) continue;
            set(p[0], y + 1, p[1], "turtle_egg[eggs=3]");
            eggs--;
        }
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p != null) mob(p[0] + 0.5, y + 1, p[1] + 0.5, Turtle.class, null);
        }
    }

    private static final Material[] CORAL_BLOCKS = {Material.TUBE_CORAL_BLOCK, Material.BRAIN_CORAL_BLOCK,
            Material.BUBBLE_CORAL_BLOCK, Material.FIRE_CORAL_BLOCK, Material.HORN_CORAL_BLOCK};
    private static final String[] CORALS = {"tube_coral", "brain_coral", "bubble_coral", "fire_coral", "horn_coral",
            "tube_coral_fan", "brain_coral_fan", "bubble_coral_fan", "fire_coral_fan", "horn_coral_fan"};

    /** 산호 석호: 산호초, 해초, 바다 피클, 켈프. 가운데 탁 트인 물에서 보물 낚시. */
    private void lagoon() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return rim ? Material.SANDSTONE : Material.SAND;
            if (dy <= 2) return Material.SANDSTONE;
            return pr.nextDouble() < 0.7 ? Material.SANDSTONE : Material.PRISMARINE;
        }, null, 0);
        double pr = rad * 0.6;
        int R = (int) Math.ceil(pr);
        List<int[]> floor = new ArrayList<>();
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                if (dx * dx + dz * dz > pr * pr + 0.5) continue;
                for (int k = 0; k <= 2; k++) set(x + dx, y - k, z + dz, Material.WATER);
                set(x + dx, y - 3, z + dz, r.nextDouble() < 0.6 ? CORAL_BLOCKS[r.nextInt(5)] : Material.SAND);
                floor.add(new int[]{x + dx, z + dz});
            }
        // 켈프는 가운데 5×5 밖에만 (트인 물이어야 보물이 낚인다)
        List<int[]> outer = new ArrayList<>(floor);
        outer.removeIf(p -> Math.abs(p[0] - x) <= 2 && Math.abs(p[1] - z) <= 2);
        for (int i = 0; i < 3 && !outer.isEmpty(); i++) {
            int[] p = take(outer);
            floor.removeIf(q -> q[0] == p[0] && q[1] == p[1]);
            set(p[0], y - 2, p[1], Material.KELP_PLANT);
            set(p[0], y - 1, p[1], Material.KELP_PLANT);
            set(p[0], y, p[1], Material.KELP);
        }
        int corals = 6 + r.nextInt(3);
        for (int i = 0; i < corals + 9 && !floor.isEmpty(); i++) {
            int[] p = take(floor);
            if (!air(p[0], y - 2, p[1]) && type(p[0], y - 2, p[1]) != Material.WATER) continue;
            if (i < corals) set(p[0], y - 2, p[1], CORALS[r.nextInt(CORALS.length)] + "[waterlogged=true]");
            else if (i < corals + 6) set(p[0], y - 2, p[1], Material.SEAGRASS);
            else set(p[0], y - 2, p[1], "sea_pickle[pickles=4,waterlogged=true]");
        }
        // 가장자리 모래톱에 야자수
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> dist(p[0], p[1]) < pr + 1.5);
        int[] p = takeFree(spots);
        if (p != null) palm(p[0], p[1]);
    }

    private static final Material[] COPPERS = {Material.COPPER_ORE, Material.COPPER_ORE, Material.EXPOSED_COPPER,
            Material.WEATHERED_COPPER, Material.WEATHERED_COPPER, Material.OXIDIZED_COPPER, Material.OXIDIZED_COPPER,
            Material.OXIDIZED_CUT_COPPER};

    /** 구리 해안: 구리 광석, 녹슨 구리 바위 기둥과 피뢰침. */
    private void copperCove() {
        blob(x, y, z, rad, d + 1, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy > 0 || rim) return Material.STONE;
            return pr.nextDouble() < 0.7 ? Material.SAND : Material.GRAVEL;
        }, new Material[]{Material.COPPER_ORE, Material.COPPER_ORE, Material.COPPER_ORE, Material.COPPER_ORE,
                Material.COPPER_ORE, Material.COPPER_ORE, Material.IRON_ORE}, 0.20);
        // 바다 쪽으로 열린 듯한 2×4 물웅덩이 (둘레는 돌)
        List<int[]> spots = tiles(2);
        for (int k = 0; k < 30; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            boolean ok = true;
            for (int i = -1; i <= 2 && ok; i++)
                for (int j = -1; j <= 4 && ok; j++) if (!solid(p[0] + i, y, p[1] + j) || !solid(p[0] + i, y - 1, p[1] + j)) ok = false;
            if (!ok) continue;
            for (int i = -1; i <= 2; i++)
                for (int j = -1; j <= 4; j++) {
                    boolean in = i >= 0 && i <= 1 && j >= 0 && j <= 3;
                    if (in) {
                        set(p[0] + i, y, p[1] + j, Material.WATER);
                        set(p[0] + i, y - 1, p[1] + j, Material.WATER);
                        set(p[0] + i, y - 2, p[1] + j, Material.STONE);
                    } else set(p[0] + i, y, p[1] + j, Material.STONE);
                }
            spots.removeIf(q -> q[0] >= p[0] - 2 && q[0] <= p[0] + 3 && q[1] >= p[1] - 2 && q[1] <= p[1] + 5);
            break;
        }
        int stacks = 2 + r.nextInt(2), best = -1;
        int[] tallest = null;
        for (int i = 0; i < stacks; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (!tile(p[0] + 1, p[1]) || !tile(p[0], p[1] + 1) || !tile(p[0] + 1, p[1] + 1)) {
                i--;
                continue;
            }
            int h = 4 + r.nextInt(5);
            for (int k = 1; k <= h; k++) {
                int w2 = k <= 2 ? 1 : 0;
                for (int a = 0; a <= w2; a++) for (int b = 0; b <= w2; b++) set(p[0] + a, y + k, p[1] + b, COPPERS[r.nextInt(COPPERS.length)]);
            }
            if (h > best) {
                best = h;
                tallest = p;
            }
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 2 && Math.abs(q[1] - p[1]) <= 2);
        }
        if (tallest != null) set(tallest[0], y + best + 1, tallest[1], "lightning_rod[facing=up]");
    }

    /** 해저 유적: 프리즈머린 기둥과 아치, 바다 랜턴, 물에 잠긴 구덩이의 젖은 스펀지. */
    private void prismarineRuin() {
        blob(x, y, z, rad, d, Material.PRISMARINE_BRICKS, Material.PRISMARINE, Material.DARK_PRISMARINE, is.seed(), null, 0);
        // 물에 잠긴 3×3×3 구덩이
        for (int dx = -1; dx <= 1; dx++)
            for (int dz = -1; dz <= 1; dz++) {
                for (int k = 0; k <= 2; k++) set(x + dx, y - k, z + dz, Material.WATER);
                set(x + dx, y - 3, z + dz, Material.DARK_PRISMARINE);
            }
        set(x, y - 3, z, Material.WET_SPONGE);
        for (int[] c : new int[][]{{1, 1}, {-1, -1}}) {
            set(x + c[0], y - 2, z + c[1], Material.KELP_PLANT);
            set(x + c[0], y - 1, z + c[1], Material.KELP_PLANT);
            set(x + c[0], y, z + c[1], Material.KELP);
        }
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> Math.abs(p[0] - x) <= 2 && Math.abs(p[1] - z) <= 2);
        // 아치: 짙은 프리즈머린 기둥 둘과 들보
        for (int k = 0; k < 30; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (!tile(p[0] + 3, p[1]) || !air(p[0] + 1, y + 1, p[1]) || !air(p[0] + 2, y + 1, p[1])) continue;
            column(p[0], y + 1, p[1], 3, Material.DARK_PRISMARINE);
            column(p[0] + 3, y + 1, p[1], 3, Material.DARK_PRISMARINE);
            for (int i = 0; i <= 3; i++) set(p[0] + i, y + 4, p[1], Material.DARK_PRISMARINE);
            spots.removeIf(q -> q[0] >= p[0] - 1 && q[0] <= p[0] + 4 && Math.abs(q[1] - p[1]) <= 1);
            break;
        }
        int cols = 4 + r.nextInt(3);
        for (int i = 0; i < cols; i++) {
            int[] p = takeFree(spots);
            if (p != null) column(p[0], y + 1, p[1], 2 + r.nextInt(4), Material.PRISMARINE_BRICKS);
        }
        for (int i = 0; i < 4; i++) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y, p[1], Material.SEA_LANTERN);
        }
        int[] p = takeFree(spots);
        if (p == null) p = new int[]{x + 2, z + 2};
        loot(chest(p[0], y + 1, p[1], BlockFace.SOUTH), 4 + r.nextInt(2), OCEAN_RUIN_LOOT, new ItemStack(Material.NAUTILUS_SHELL));
    }

    /** 난파선: 가문비나무 선체, 부러진 돛대와 돛. 뱃머리와 고물의 상자. */
    private void shipwreck() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> dy == 0 && !rim ? Material.SAND : Material.SANDSTONE, null, 0);
        int[] toS = toSpawn(), u = {-toS[0], -toS[1]}, v = side(u);
        int L = 9 + r.nextInt(3), t0 = -(L / 2), t1 = t0 + L - 1;
        for (int t = t0; t <= t1; t++) {
            // 뱃머리 세 칸은 한 칸 높고 폭이 5 → 3 → 1 로 좁아진다
            int half = t == t1 ? 0 : t == t1 - 1 ? 1 : 2;
            int top = t >= t1 - 2 ? 3 : 2;
            for (int s = -half; s <= half; s++) {
                int px = x + u[0] * t + v[0] * s, pz = z + u[1] * t + v[1] * s;
                set(px, y, pz, Material.SPRUCE_PLANKS);
                boolean wall = Math.abs(s) == half || t == t0;
                for (int k = 1; k <= top; k++) set(px, y + k, pz, wall ? Material.SPRUCE_PLANKS : Material.AIR);
            }
        }
        // 가운데 삼분의 일 위 갑판 (구멍 두 개)
        int m0 = t0 + L / 3, m1 = t0 + 2 * L / 3 - 1;
        int hole1 = m0 + r.nextInt(Math.max(1, m1 - m0 + 1)), hole2 = r.nextInt(3) - 1;
        for (int t = m0; t <= m1; t++)
            for (int s = -1; s <= 1; s++) {
                if ((t == hole1 && s == hole2) || (t == m1 && s == -hole2)) continue;
                set(x + u[0] * t + v[0] * s, y + 2, z + u[1] * t + v[1] * s, Material.OAK_PLANKS);
            }
        // 부러진 돛대, 활대, 한 칸 빠진 돛
        column(x, y + 1, z, 5, Material.SPRUCE_LOG);
        for (int s = -1; s <= 1; s++) if (s != 0) set(x + v[0] * s, y + 4, z + v[1] * s, Material.SPRUCE_FENCE);
        int missing = r.nextInt(6);
        for (int s = -1, i = 0; s <= 1; s++)
            for (int k = 3; k <= 4; k++, i++)
                if (i != missing) set(x + u[0] + v[0] * s, y + k, z + u[1] + v[1] * s, Material.WHITE_WOOL);
        // 바닥에 스며든 물
        int wet = 2 + r.nextInt(2);
        for (int i = 0; i < wet; i++) {
            int t = t0 + 1 + r.nextInt(Math.max(1, L - 4)), s = r.nextInt(3) - 1;
            if (t == 0 && s == 0) continue;
            set(x + u[0] * t + v[0] * s, y, z + u[1] * t + v[1] * s, Material.WATER);
        }
        int bt = t1 - 2, st = t0 + 1;
        loot(chest(x + u[0] * bt, y + 1, z + u[1] * bt, BlockFace.valueOf(face(new int[]{-u[0], -u[1]}).toUpperCase(Locale.ROOT))),
                5, SHIP_SUPPLY_LOOT);
        loot(chest(x + u[0] * st, y + 1, z + u[1] * st, BlockFace.valueOf(face(u).toUpperCase(Locale.ROOT))),
                4, SHIP_TREASURE_LOOT, new ItemStack(Material.NAUTILUS_SHELL), silkBook());
    }

    // ------------------------------------------------------------------ 야생

    /** 정글: 코코아가 달린 정글나무, 대나무, 수박, 덩굴, 앵무새. */
    private void jungle() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        int tx = x, tz = z;
        boolean grown = grow(x, z, TreeType.COCOA_TREE);
        List<int[]> around = tiles(2);
        for (int k = 0; k < 5 && !grown; k++) {
            int[] p = takeFree(around);
            if (p == null) break;
            if (grow(p[0], p[1], TreeType.COCOA_TREE)) {
                tx = p[0];
                tz = p[1];
                grown = true;
            }
        }
        if (!grown) set(x, y + 1, z, Material.JUNGLE_SAPLING);
        // 코코아 열매가 꼭 두 개는 달리게 (나무 모양은 그때그때 달라서 줄기 둘레 빈칸·덩굴·잎 자리를 찾는다)
        int pods = 0;
        for (int k = 2; k <= 9 && pods < 2; k++) {
            if (type(tx, y + k, tz) != Material.JUNGLE_LOG) continue;
            for (int[] f : FOUR) {
                Material at = type(tx + f[0], y + k, tz + f[1]);
                if (!at.isAir() && at != Material.VINE && at != Material.JUNGLE_LEAVES) continue;
                set(tx + f[0], y + k, tz + f[1], "cocoa[age=2,facing=" + face(new int[]{-f[0], -f[1]}) + "]");
                pods++;
                break;
            }
        }
        List<int[]> spots = tiles(1);
        int ox = tx, oz = tz;
        spots.removeIf(p -> Math.abs(p[0] - ox) <= 2 && Math.abs(p[1] - oz) <= 2);
        for (int i = 0; i < 2; i++) grow(spots, TreeType.JUNGLE_BUSH, null);
        gourds(spots, Material.MELON, "attached_melon_stem", 2);
        int bamboo = 4 + r.nextInt(3);
        for (int i = 0; i < bamboo; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int h = 2 + r.nextInt(5);
            for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], "bamboo[age=0,leaves=" + (k == h ? "large" : k == h - 1 ? "small" : "none") + "]");
        }
        // 섬 옆면에 늘어진 덩굴
        List<int[]> eaves = eaves();
        int vines = 8 + r.nextInt(5);
        for (int k = 0; k < 60 && vines > 0 && !eaves.isEmpty(); k++) {
            int[] e = take(eaves);
            for (int[] f : FOUR) {
                int vx = e[0] + f[0], vz = e[1] + f[1];
                if (!air(vx, y, vz) || !air(vx, y - 1, vz)) continue;
                vine(vx, y, vz, new int[]{-f[0], -f[1]}, 2 + r.nextInt(3));
                vines--;
                break;
            }
        }
        int[] p = takeFree(spots);
        if (p != null) mob(p[0] + 0.5, y + 1, p[1] + 0.5, Parrot.class, null);
    }

    /** 마녀의 늪: 진흙과 물웅덩이, 수련잎, 파란 난초, 다리 달린 오두막, 개구리. 밤엔 슬라임. */
    private void swamp() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return pr.nextDouble() < 0.75 ? Material.GRASS_BLOCK : Material.MUD;
            if (dy <= 2) return pr.nextBoolean() ? Material.MUD : Material.DIRT;
            return pr.nextDouble() < 0.3 ? Material.CLAY : Material.STONE;
        }, null, 0);
        long sd = is.seed();
        // 물웅덩이: 가장자리가 아닌 윗면의 약 30% (둘레가 모두 섬 윗면이라 물이 새지 않는다)
        List<int[]> water = tiles(1);
        water.removeIf(p -> patch(p[0], p[1], sd, 2) >= 0.3 || Math.abs(p[0] - x) <= 3 && p[1] - z >= -3 && p[1] - z <= 2);
        for (int[] p : water) {
            set(p[0], y - 1, p[1], Material.MUD);
            set(p[0], y, p[1], Material.WATER);
        }
        for (int i = 0; i < 4 && !water.isEmpty(); i++) {
            int[] p = take(water);
            set(p[0], y + 1, p[1], Material.LILY_PAD);
        }
        // 오두막: 네 다리 위 5×4 바닥
        for (int[] c : new int[][]{{-2, -2}, {2, -2}, {-2, 1}, {2, 1}}) column(x + c[0], y + 1, z + c[1], 2, Material.SPRUCE_LOG);
        for (int a = -2; a <= 2; a++)
            for (int c = -2; c <= 1; c++) {
                set(x + a, y + 3, z + c, Material.SPRUCE_PLANKS);
                boolean wall = Math.abs(a) == 2 || c == -2 || c == 1;
                for (int k = 4; k <= 5; k++) set(x + a, y + k, z + c, wall ? Material.SPRUCE_PLANKS : Material.AIR);
            }
        set(x, y + 4, z + 1, Material.AIR);
        set(x, y + 5, z + 1, Material.AIR);
        set(x + 2, y + 5, z - 1, Material.AIR);
        for (int a = -2; a <= 2; a++) {
            set(x + a, y + 6, z - 2, "spruce_stairs[facing=south]");
            set(x + a, y + 6, z + 1, "spruce_stairs[facing=north]");
            for (int c = -1; c <= 0; c++) set(x + a, y + 6, z + c, Material.SPRUCE_SLAB);
        }
        set(x - 1, y + 4, z - 1, "water_cauldron[level=3]");
        set(x + 1, y + 4, z - 1, Material.CRAFTING_TABLE);
        set(x + 1, y + 4, z, Material.POTTED_RED_MUSHROOM);
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> Math.abs(p[0] - x) <= 3 && p[1] - z >= -3 && p[1] - z <= 2);
        for (int i = 0; i < 2; i++) grow(spots, TreeType.SWAMP, Material.OAK_SAPLING);
        List<int[]> grass = new ArrayList<>(spots);
        grass.removeIf(p -> type(p[0], y, p[1]) != Material.GRASS_BLOCK);
        for (int i = 0; i < 3 && !grass.isEmpty(); i++) {
            int[] p = takeFree(grass);
            if (p != null) set(p[0], y + 1, p[1], Material.BLUE_ORCHID);
        }
        // 개구리는 물웅덩이 옆 빈 땅에 (자리가 모자라면 오두막 밑)
        List<int[]> ground = tiles(1);
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(ground);
            if (p == null) p = new int[]{x + i, z};
            mob(p[0] + 0.5, y + 1, p[1] + 0.5, Frog.class, null);
        }
    }

    private static final Material[] BANDS = {Material.ORANGE_TERRACOTTA, Material.TERRACOTTA, Material.YELLOW_TERRACOTTA,
            Material.WHITE_TERRACOTTA, Material.RED_TERRACOTTA, Material.BROWN_TERRACOTTA, Material.LIGHT_GRAY_TERRACOTTA,
            Material.ORANGE_TERRACOTTA};

    /** 붉은 협곡: 줄무늬 테라코타, 금광석, 붉은 모래, 낡은 갱도 틀. */
    private void badlands() {
        long sd = is.seed();
        blob(x, y, z, rad, d + 2, sd, (dx, dy, dz, rim, pr) -> dy == 0 ? (rim ? Material.RED_SANDSTONE : Material.RED_SAND)
                        : BANDS[Math.floorMod(y - dy + (int) sd, 8)],
                new Material[]{Material.GOLD_ORE, Material.GOLD_ORE, Material.GOLD_ORE, Material.GOLD_ORE, Material.GOLD_ORE,
                        Material.GOLD_ORE, Material.GOLD_ORE, Material.IRON_ORE, Material.IRON_ORE, Material.REDSTONE_ORE}, 0.10);
        List<int[]> spots = tiles(1);
        int hoodoos = 1 + r.nextInt(2);
        for (int i = 0; i < hoodoos; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int h = 4 + r.nextInt(3);
            for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], k == h ? Material.RED_SANDSTONE : BANDS[Math.floorMod(y + k + (int) sd, 8)]);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 1 && Math.abs(q[1] - p[1]) <= 1);
        }
        int cacti = 2;
        for (int k = 0; k < 40 && cacti > 0; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (type(p[0], y, p[1]) != Material.RED_SAND) continue;
            boolean clear = true;
            for (int i = 1; i <= 2; i++) for (int[] f : FOUR) if (!air(p[0] + f[0], y + i, p[1] + f[1])) clear = false;
            if (!clear) continue;
            column(p[0], y + 1, p[1], 2, Material.CACTUS);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 1 && Math.abs(q[1] - p[1]) <= 1);
            cacti--;
        }
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y + 1, p[1], Material.DEAD_BUSH);
        }
        // 가장자리의 낡은 갱도 틀
        int[] u = FOUR[r.nextInt(4)], v = side(u);
        int t = Math.max(1, edge(u) - 1);
        int fx = x + u[0] * t, fz = z + u[1] * t;
        for (int s : new int[]{-1, 2}) if (tile(fx + v[0] * s, fz + v[1] * s)) column(fx + v[0] * s, y + 1, fz + v[1] * s, 2, Material.OAK_FENCE);
        for (int s = -1; s <= 2; s++) set(fx + v[0] * s, y + 3, fz + v[1] * s, Material.OAK_PLANKS);
        String shape = u[0] != 0 ? "east_west" : "north_south";
        for (int k = 0; k <= 1; k++) set(fx - u[0] * k, y + 1, fz - u[1] * k, "rail[shape=" + shape + "]");
    }

    /** 사바나: 아카시아나무, 마른 흙, 소와 아르마딜로. */
    private void savanna() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> dy == 0
                ? (pr.nextDouble() < 0.75 ? Material.GRASS_BLOCK : Material.COARSE_DIRT)
                : dy <= 2 ? Material.DIRT : Material.STONE, null, 0);
        List<int[]> spots = tiles(2);
        int n = 1 + r.nextInt(2);
        for (int i = 0; i < n; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], Material.GRASS_BLOCK);
            if (!grow(p[0], p[1], TreeType.ACACIA)) set(p[0], y + 1, p[1], Material.ACACIA_SAPLING);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 3 && Math.abs(q[1] - p[1]) <= 3);
        }
        List<int[]> ground = tiles(0);
        for (int i = 0; i < (int) (rad * 1.5); i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            if (type(p[0], y, p[1]) != Material.GRASS_BLOCK) continue;
            if (i % 3 == 0 && air(p[0], y + 2, p[1])) tall(p[0], p[1], Material.TALL_GRASS);
            else set(p[0], y + 1, p[1], Material.SHORT_GRASS);
        }
        List<int[]> spots2 = tiles(1);
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(spots2);
            if (p == null) break;
            if (i < 2) mob(p[0] + 0.5, y + 1, p[1] + 0.5, Cow.class, null);
            else mob(p[0] + 0.5, y + 1, p[1] + 0.5, Armadillo.class, null);
        }
    }

    /** 이끼 동굴: 속이 빈 섬에 이끼, 진달래, 빛나는 동굴 덩굴(발광 열매), 포자꽃, 큰 흘림잎. */
    private void lushCave() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return Material.MOSS_BLOCK;
            if (dy <= 2) return pr.nextBoolean() ? Material.ROOTED_DIRT : Material.DIRT;
            return pr.nextDouble() < 0.8 ? Material.STONE : Material.CLAY;
        }, null, 0);
        int cy = y - 3;
        List<int[]> floor = new ArrayList<>(), ceil = new ArrayList<>();
        for (int dx = -4; dx <= 4; dx++)
            for (int dz = -4; dz <= 4; dz++)
                for (int dy = -2; dy <= 2; dy++) {
                    double e = (dx / 3.5) * (dx / 3.5) + (dy / 2.0) * (dy / 2.0) + (dz / 3.5) * (dz / 3.5);
                    if (e <= 1 && cy + dy < y) set(x + dx, cy + dy, z + dz, Material.AIR);
                }
        tunnel(y - 5, 2, 2, 0, null);
        for (int dx = -4; dx <= 4; dx++)
            for (int dz = -4; dz <= 4; dz++)
                for (int yy = cy - 3; yy <= y - 1; yy++) {
                    int px = x + dx, pz = z + dz;
                    if (!air(px, yy, pz)) continue;
                    if (solid(px, yy - 1, pz) && dx * dx + dz * dz <= 12) {
                        set(px, yy - 1, pz, Material.MOSS_BLOCK);
                        floor.add(new int[]{px, yy, pz});
                    }
                    if (solid(px, yy + 1, pz) && yy + 1 < y + 1 && dx * dx + dz * dz <= 9) ceil.add(new int[]{px, yy, pz});
                }
        // 2×2 물웅덩이 (바닥 점토)와 큰 흘림잎
        int[][] around = {{-1, 0}, {-1, 1}, {2, 0}, {2, 1}, {0, -1}, {1, -1}, {0, 2}, {1, 2}};
        for (int[] f : floor) {
            int fx = f[0], fy = f[1] - 1, fz = f[2];
            boolean ok = true;
            for (int a = 0; a <= 1 && ok; a++)
                for (int c = 0; c <= 1 && ok; c++)
                    if (type(fx + a, fy, fz + c) != Material.MOSS_BLOCK || !air(fx + a, fy + 1, fz + c)) ok = false;
            for (int[] n : around) if (!solid(fx + n[0], fy, fz + n[1])) ok = false;
            if (!ok) continue;
            for (int a = 0; a <= 1; a++)
                for (int c = 0; c <= 1; c++) {
                    set(fx + a, fy - 1, fz + c, Material.CLAY);
                    set(fx + a, fy, fz + c, Material.WATER);
                }
            set(fx, fy, fz, "big_dripleaf[waterlogged=true,facing=north]");
            break;
        }
        int bushes = 3;
        for (int k = 0; k < floor.size() && k < 80; k++) {
            int[] f = floor.get(r.nextInt(floor.size()));
            if (!air(f[0], f[1], f[2]) || type(f[0], f[1] - 1, f[2]) != Material.MOSS_BLOCK) continue;
            if (bushes > 0) {
                set(f[0], f[1], f[2], bushes == 3 ? Material.AZALEA : Material.FLOWERING_AZALEA);
                bushes--;
            } else if (r.nextBoolean()) set(f[0], f[1], f[2], Material.MOSS_CARPET);
        }
        int vines = 3 + r.nextInt(2);
        boolean blossom = false;
        for (int k = 0; k < 60 && (vines > 0 || !blossom) && !ceil.isEmpty(); k++) {
            int[] c = ceil.remove(r.nextInt(ceil.size()));
            if (!air(c[0], c[1], c[2])) continue;
            if (!blossom) {
                set(c[0], c[1], c[2], Material.SPORE_BLOSSOM);
                blossom = true;
            } else {
                hang(c[0], c[1], c[2], 2 + r.nextInt(2), "cave_vines_plant[berries=true]", "cave_vines[berries=true]");
                vines--;
            }
        }
        List<int[]> spots = tiles(2);
        if (!grow(spots, TreeType.AZALEA, Material.AZALEA)) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y + 1, p[1], Material.AZALEA);
        }
        // 밖에서도 알아보게: 윗면 이끼 카펫, 가장자리 밑에 늘어진 빛나는 동굴 덩굴
        for (int i = 0; i < (int) (rad * 1.2); i++) {
            int[] p = takeFree(spots);
            if (p != null) set(p[0], y + 1, p[1], Material.MOSS_CARPET);
        }
        List<int[]> eaves = eaves();
        for (int i = 0; i < 4 && !eaves.isEmpty(); i++) {
            int[] e = take(eaves);
            hang(e[0], y - 1, e[1], 2 + r.nextInt(3), "cave_vines_plant[berries=true]", "cave_vines[berries=true]");
        }
        List<int[]> under = new ArrayList<>();
        int R = (int) Math.ceil(rad);
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                int by = bottom(x + dx, z + dz);
                if (by != Integer.MIN_VALUE && by < y - 2) under.add(new int[]{x + dx, by - 1, z + dz});
            }
        int roots = 6 + r.nextInt(3);
        for (int i = 0; i < roots && !under.isEmpty(); i++) {
            int[] c = under.remove(r.nextInt(under.size()));
            set(c[0], c[1], c[2], Material.HANGING_ROOTS);
        }
    }

    private static final Material[] MOUNTAIN_ORES = {Material.IRON_ORE, Material.IRON_ORE, Material.IRON_ORE, Material.IRON_ORE,
            Material.COAL_ORE, Material.COAL_ORE, Material.COAL_ORE, Material.EMERALD_ORE, Material.EMERALD_ORE, Material.COPPER_ORE};

    /** 산봉우리: 눈 덮인 봉우리, 띠 진 화강암·섬록암·안산암, 에메랄드, 폭포, 라마. */
    private void mountain() {
        Material[] band = {Material.ANDESITE, Material.GRANITE, Material.DIORITE};
        blob(x, y, z, rad, d + 3, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return Math.hypot(dx, dz) > rad * 0.55 ? Material.GRASS_BLOCK : Material.STONE;
            int yy = y - dy;
            // 세 층에 한 층꼴로 다른 돌 띠
            return Math.floorMod(yy, 3) == 0 ? band[Math.floorMod(Math.floorDiv(yy, 3), 3)] : Material.STONE;
        }, MOUNTAIN_ORES, 0.10);
        int h = 10 + r.nextInt(5);
        spike(x, y + 1, z, h, Material.STONE, null);
        for (int k = h - 2; k < h; k++)
            for (int dx = -2; dx <= 2; dx++)
                for (int dz = -2; dz <= 2; dz++)
                    if (type(x + dx, y + 1 + k, z + dz) == Material.STONE) set(x + dx, y + 1 + k, z + dz, Material.SNOW_BLOCK);
        int[] f = FOUR[r.nextInt(4)];
        spike(x + 3 * f[0] + f[1], y + 1, z + 3 * f[1] + f[0], 4 + r.nextInt(3), Material.GRANITE, null);
        int[] u = toSpawn();
        fall(new int[]{-u[0], -u[1]}, Material.WATER);
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> dist(p[0], p[1]) < 3);
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p != null) mob(p[0] + 0.5, y + 1, p[1] + 0.5, Llama.class, null);
        }
    }

    private static final Material[] DEEP_ORES = {Material.DEEPSLATE_REDSTONE_ORE, Material.DEEPSLATE_REDSTONE_ORE,
            Material.DEEPSLATE_REDSTONE_ORE, Material.DEEPSLATE_REDSTONE_ORE, Material.DEEPSLATE_REDSTONE_ORE,
            Material.DEEPSLATE_REDSTONE_ORE, Material.DEEPSLATE_REDSTONE_ORE, Material.DEEPSLATE_REDSTONE_ORE,
            Material.DEEPSLATE_REDSTONE_ORE, Material.DEEPSLATE_IRON_ORE, Material.DEEPSLATE_IRON_ORE, Material.DEEPSLATE_IRON_ORE,
            Material.DEEPSLATE_IRON_ORE, Material.DEEPSLATE_GOLD_ORE, Material.DEEPSLATE_GOLD_ORE, Material.DEEPSLATE_GOLD_ORE,
            Material.DEEPSLATE_DIAMOND_ORE, Material.DEEPSLATE_DIAMOND_ORE, Material.DEEPSLATE_LAPIS_ORE, Material.DEEPSLATE_LAPIS_ORE};

    /** 심층 광산: 심층암, 레드스톤·다이아몬드. 갱도 천장의 뾰족한 점적석은 물 덕분에 다시 자란다. */
    private void deepMine() {
        blob(x, y, z, rad, d + 3, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) {
                double p = pr.nextDouble();
                return p < 0.6 ? Material.DEEPSLATE : p < 0.85 ? Material.COBBLED_DEEPSLATE : Material.TUFF;
            }
            if (dy <= 2) return Material.DEEPSLATE;
            return Math.floorMod(y - dy, 3) == 0 ? Material.TUFF : Material.DEEPSLATE;
        }, DEEP_ORES, 0.14);
        Bore b = tunnel(y - 5, 3, 2, -2, new Frame(Material.DEEPSLATE_BRICK_WALL, Material.DEEPSLATE_BRICKS, DEEP_ORES, true, "lantern", 1));
        // 손 닿는 천장의 점적석 네 개. 그중 하나는 위에 점적석 블록과 물이 있어서 다시 자란다
        int drips = 0;
        boolean grows = false;
        for (int t = -1; t < b.mouth() - 1 && drips < 4; t++) {
            int s = (t & 1) == 0 ? 0 : 1;
            int px = b.x(t, s), pz = b.z(t, s);
            if (!air(px, y - 2, pz) || !solid(px, y - 1, pz)) continue;
            if (!grows) {
                boolean held = true;
                for (int[] f : FOUR) if (!solid(px + f[0], y, pz + f[1])) held = false;
                if (!held) continue;
                set(px, y - 1, pz, Material.DRIPSTONE_BLOCK);
                set(px, y + 1, pz, Material.AIR);
                set(px, y, pz, Material.WATER);
                grows = true;
            }
            set(px, y - 2, pz, "pointed_dripstone[vertical_direction=down,thickness=tip]");
            drips++;
            t++;
        }
        // 밑면: 점적석 고드름과 점적석 블록 (보기용)
        List<int[]> under = new ArrayList<>();
        int R = (int) Math.ceil(rad);
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                int by = bottom(x + dx, z + dz);
                if (by != Integer.MIN_VALUE && by < y - 3) under.add(new int[]{x + dx, by, z + dz});
            }
        int n = 8 + r.nextInt(5);
        String[][] shapes = {{"tip"}, {"frustum", "tip"}, {"base", "frustum", "tip"}};
        for (int i = 0; i < n && !under.isEmpty(); i++) {
            int[] c = under.remove(r.nextInt(under.size()));
            set(c[0], c[1], c[2], Material.DRIPSTONE_BLOCK);
            String[] sh = shapes[r.nextInt(3)];
            for (int k = 0; k < sh.length; k++)
                set(c[0], c[1] - 1 - k, c[2], "pointed_dripstone[vertical_direction=down,thickness=" + sh[k] + "]");
        }
    }

    /** 어두운 숲: 짙은 참나무, 큰 버섯, 두 칸 꽃, 이끼 바위. */
    private void darkForest() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        List<int[]> spots = tiles(2);
        for (int i = 0; i < 2; i++) {
            boolean done = false;
            for (int k = 0; k < 8 && !done; k++) {
                int[] p = takeFree(spots);
                if (p == null) break;
                if (!tile(p[0] + 1, p[1]) || !tile(p[0], p[1] + 1) || !tile(p[0] + 1, p[1] + 1)) continue;
                if (grow(p[0], p[1], TreeType.DARK_OAK)) {
                    spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 3 && Math.abs(q[1] - p[1]) <= 3);
                    done = true;
                } else if (k == 7) {
                    for (int a = 0; a <= 1; a++) for (int c = 0; c <= 1; c++) set(p[0] + a, y + 1, p[1] + c, Material.DARK_OAK_SAPLING);
                }
            }
        }
        grow(spots, TreeType.RED_MUSHROOM, Material.RED_MUSHROOM);
        grow(spots, TreeType.BROWN_MUSHROOM, Material.BROWN_MUSHROOM);
        for (Material m : new Material[]{Material.ROSE_BUSH, Material.LILAC}) {
            int[] p = takeFree(spots);
            if (p != null && air(p[0], y + 2, p[1])) tall(p[0], p[1], m);
        }
        boulder(spots, Material.MOSSY_COBBLESTONE);
    }

    /** 벚꽃: 벚나무, 분홍 꽃잎, 돌 등롱. */
    private void cherry() {
        blob(x, y, z, rad, d, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, is.seed(), null, 0);
        List<int[]> spots = tiles(2);
        int n = 1 + r.nextInt(2);
        for (int i = 0; i < n; i++) grow(spots, TreeType.CHERRY, Material.CHERRY_SAPLING);
        List<int[]> ground = tiles(1);
        int[] lamp = takeFree(ground);
        if (lamp != null) {
            column(lamp[0], y + 1, lamp[1], 2, Material.STONE_BRICK_WALL);
            set(lamp[0], y + 3, lamp[1], Material.LANTERN);
        }
        int petals = 8 + r.nextInt(5);
        String[] dirs = {"north", "east", "south", "west"};
        for (int i = 0; i < petals; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            if (type(p[0], y, p[1]) != Material.GRASS_BLOCK) continue;
            set(p[0], y + 1, p[1], "pink_petals[flower_amount=" + (1 + r.nextInt(4)) + ",facing=" + dirs[r.nextInt(4)] + "]");
        }
    }

    /** 옛 폐허: 이끼 낀 돌벽돌 벽, 깎은 돌벽돌 아치, 덩굴. */
    private void ruin() {
        blob(x, y, z, rad, d, Material.MOSSY_STONE_BRICKS, Material.STONE_BRICKS, Material.STONE, is.seed(), null, 0);
        Material[] bricks = {Material.STONE_BRICKS, Material.MOSSY_STONE_BRICKS, Material.CRACKED_STONE_BRICKS};
        int[] archSide = FOUR[r.nextInt(4)];
        List<int[]> faces = new ArrayList<>();
        for (int dx = -3; dx <= 3; dx++)
            for (int dz = -3; dz <= 3; dz++) {
                if (Math.abs(dx) != 3 && Math.abs(dz) != 3) continue;
                boolean arch = archSide[0] != 0 ? dx == 3 * archSide[0] && Math.abs(dz) <= 1 : dz == 3 * archSide[1] && Math.abs(dx) <= 1;
                if (arch) {
                    boolean mid = archSide[0] != 0 ? dz == 0 : dx == 0;
                    if (!mid) column(x + dx, y + 1, z + dz, 3, Material.CHISELED_STONE_BRICKS);
                    set(x + dx, y + 4, z + dz, Material.CHISELED_STONE_BRICKS);
                    continue;
                }
                if (r.nextDouble() < 0.3) continue;
                int h = 2 + r.nextInt(3);
                for (int k = 1; k <= h; k++) set(x + dx, y + k, z + dz, bricks[r.nextInt(3)]);
                faces.add(new int[]{x + dx, z + dz, h, Integer.signum(dx) * (Math.abs(dx) == 3 ? 1 : 0), Integer.signum(dz) * (Math.abs(dz) == 3 ? 1 : 0)});
            }
        // 바깥쪽 벽면의 덩굴
        int vines = 4 + r.nextInt(3);
        for (int k = 0; k < 40 && vines > 0 && !faces.isEmpty(); k++) {
            int[] f = faces.remove(r.nextInt(faces.size()));
            int[] out = f[3] != 0 ? new int[]{f[3], 0} : new int[]{0, f[4]};
            int vx = f[0] + out[0], vz = f[1] + out[1];
            if (!air(vx, y + f[2], vz)) continue;
            vine(vx, y + f[2], vz, new int[]{-out[0], -out[1]}, f[2]);
            vines--;
        }
        loot(chest(x, y + 1, z + 1, BlockFace.SOUTH), 4 + r.nextInt(3), RUIN_LOOT);
    }

    // ------------------------------------------------------------------ 징검다리

    /** 징검다리 바위: 긴 다리 가운데 쉬어 갈 작은 바위. 지역의 흙과 장식 하나. */
    private void stone() {
        Material top, mid;
        switch (is.region()) {
            case FROST -> { top = Material.SNOW_BLOCK; mid = Material.STONE; }
            case FLAME -> { top = Material.NETHERRACK; mid = Material.BLACKSTONE; }
            case VOID -> { top = Material.END_STONE; mid = Material.END_STONE; }
            case OCEAN -> { top = Material.SAND; mid = Material.SANDSTONE; }
            default -> { top = Material.GRASS_BLOCK; mid = Material.DIRT; }
        }
        Material t0 = top, m0 = mid;
        blob(x, y, z, rad, 3, is.seed(), (dx, dy, dz, rim, pr) ->
                dy > 0 ? m0 : t0 == Material.SAND && rim ? Material.SANDSTONE : t0, null, 0);
        switch (is.region()) {
            case PLAINS -> set(x, y + 1, z, r.nextBoolean() ? data("oak_leaves[persistent=true]") : Material.POPPY.createBlockData());
            case FROST -> set(x, y + 1, z, Material.ICE);
            case FLAME -> column(x, y + 1, z, 1 + r.nextInt(2), Material.BASALT);
            case VOID -> set(x, y + 1, z, Material.END_STONE_BRICKS);
            case OCEAN -> set(x, y + 1, z, Material.DEAD_BUSH);
            case WILD -> {
                set(x, y + 1, z, Material.MOSSY_COBBLESTONE);
                set(x + 1, y + 1, z, Material.MOSSY_COBBLESTONE);
            }
        }
    }
}
