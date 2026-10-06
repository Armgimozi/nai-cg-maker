package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.map.MapBuilder.Isle;
import kr.augsky.util.Text;
import org.bukkit.Axis;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Chest;
import org.bukkit.block.CreatureSpawner;
import org.bukkit.block.data.Orientable;
import org.bukkit.block.spawner.SpawnRule;
import org.bukkit.block.spawner.SpawnerEntry;
import org.bukkit.block.data.type.Beehive;
import org.bukkit.block.data.type.Campfire;
import org.bukkit.block.data.type.CaveVinesPlant;
import org.bukkit.command.CommandSender;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.EnchantmentStorageMeta;
import org.bukkit.loot.LootTable;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * /증강관리 섬검사, /증강관리 네더 검사: 지은 맵의 섬마다 있어야 할 블록과 동물이 있는지 센다.
 * 청크를 붙잡아 두고 엔티티가 다 불려 올 때까지(5초) 기다린 뒤 센다.
 */
final class IslandCheck {
    /** 섬 종류마다 있어야 할 것. "A+B>=n" 은 블록 수, "@종류=n" 은 엔티티 수. */
    private static final Map<String, String> NEED = Map.ofEntries(
            Map.entry("start", "CRAFTING_TABLE=0"),
            Map.entry("altar", "@INTERACTION=1 @BLOCK_DISPLAY=1"),
            Map.entry("woods", "OAK_LOG>=3"),
            Map.entry("mine", "COAL_ORE+IRON_ORE>=10 GOLD_ORE>=1 RAIL>=3 @CHEST_MINECART=1 LAVA>=1"),
            Map.entry("ranch", "@PIG=1 @CHICKEN=3 OAK_FENCE>=20 HAY_BLOCK>=1"),
            Map.entry("farm", "WHEAT>=3 CARROTS>=3 POTATOES>=3 BEETROOTS>=3 WATER>=4 COMPOSTER=1 CARVED_PUMPKIN=1"),
            Map.entry("pumpkin", "PUMPKIN>=5 ATTACHED_PUMPKIN_STEM>=5"),
            Map.entry("pond", "WATER>=12 CLAY>=10 SUGAR_CANE>=4 LILY_PAD>=2"),
            Map.entry("meadow", "BEE_NEST=1"),
            Map.entry("mushroom", "MUSHROOM_STEM>=3 RED_MUSHROOM_BLOCK>=5 BROWN_MUSHROOM_BLOCK>=5 @MOOSHROOM=1"),
            Map.entry("desert", "SAND>=30 CACTUS>=3 SUGAR_CANE>=3 WATER>=4 JUNGLE_LOG>=4 @RABBIT=2"),
            Map.entry("spider_den", "SPAWNER=1 COBWEB>=10 CHEST=1"),
            Map.entry("taiga", "SPRUCE_LOG>=8 SWEET_BERRY_BUSH>=3"),
            Map.entry("frozen_lake", "ICE>=20 WATER>=20 @SNOW_GOLEM=1 BARREL=1"),
            Map.entry("frost_mine", "LAPIS_ORE>=8 DIAMOND_ORE>=2 BLUE_ICE>=4"),
            Map.entry("icespike", "PACKED_ICE>=150 BLUE_ICE>=3"),
            Map.entry("igloo", "BREWING_STAND=1 LADDER>=4 CHEST=1"),
            Map.entry("basalt", "BASALT>=40 MAGMA_BLOCK>=8 LAVA>=3"),
            Map.entry("crimson", "CRIMSON_STEM>=4 NETHER_WART_BLOCK>=10 SHROOMLIGHT>=1 WEEPING_VINES+WEEPING_VINES_PLANT>=2"),
            Map.entry("warped", "WARPED_STEM>=4 WARPED_WART_BLOCK>=10"),
            Map.entry("soul_valley", "BONE_BLOCK>=24 NETHER_WART>=4 SOUL_SAND>=10 SOUL_FIRE>=2"),
            Map.entry("fortress", "SPAWNER=1 NETHER_BRICKS>=60 CHEST=1 NETHER_WART>=4"),
            Map.entry("volcano", "OBSIDIAN>=10 CRYING_OBSIDIAN>=2 LAVA>=10 POINTED_DRIPSTONE=2 CAULDRON+LAVA_CAULDRON=1"),
            Map.entry("nether_vein", "NETHER_QUARTZ_ORE>=15 NETHER_GOLD_ORE>=8 GLOWSTONE>=14 FIRE>=3"),
            Map.entry("chorus", "CHORUS_PLANT>=8 END_STONE>=200"),
            Map.entry("geode", "AMETHYST_BLOCK>=20 BUDDING_AMETHYST>=3 CALCITE>=30 AMETHYST_CLUSTER>=3"),
            Map.entry("obsidian_spire", "OBSIDIAN>=100 CRYING_OBSIDIAN>=3 END_ROD=1 IRON_BARS>=8"),
            Map.entry("purpur_ruin", "PURPUR_BLOCK>=40 END_ROD>=4 CHEST=1"),
            Map.entry("beach", "SAND>=30 GRAVEL>=6 @TURTLE=2 TURTLE_EGG=2 STRIPPED_OAK_LOG=4"),
            Map.entry("lagoon", "WATER>=60 KELP+KELP_PLANT>=4 SEA_PICKLE>=3 "
                    + "TUBE_CORAL_BLOCK+BRAIN_CORAL_BLOCK+BUBBLE_CORAL_BLOCK+FIRE_CORAL_BLOCK+HORN_CORAL_BLOCK>=8"),
            Map.entry("copper_cove", "COPPER_ORE>=25 EXPOSED_COPPER+WEATHERED_COPPER+OXIDIZED_COPPER+OXIDIZED_CUT_COPPER>=6 LIGHTNING_ROD=1"),
            Map.entry("prismarine_ruin", "PRISMARINE+PRISMARINE_BRICKS+DARK_PRISMARINE>=150 SEA_LANTERN=4 WET_SPONGE=1 CHEST=1"),
            Map.entry("shipwreck", "SPRUCE_PLANKS>=20 WHITE_WOOL>=5 CHEST=2"),
            Map.entry("jungle", "JUNGLE_LOG>=4 COCOA>=1 MELON>=2 BAMBOO>=4 VINE>=8 @PARROT=1"),
            Map.entry("swamp", "MUD>=5 LILY_PAD>=4 BLUE_ORCHID>=3 WATER_CAULDRON=1 @FROG=2"),
            Map.entry("badlands", "GOLD_ORE>=10 RED_SAND>=20 CACTUS>=2"),
            Map.entry("savanna", "ACACIA_LOG>=4 @COW=2 @ARMADILLO=1"),
            Map.entry("lush_cave", "MOSS_BLOCK>=30 AZALEA+FLOWERING_AZALEA>=2 SPORE_BLOSSOM=1 CLAY>=4"),
            Map.entry("mountain", "EMERALD_ORE>=4 IRON_ORE>=10 GRANITE>=10 WATER>=1 @LLAMA=2"),
            Map.entry("deep_mine", "DEEPSLATE_REDSTONE_ORE>=15 DEEPSLATE_DIAMOND_ORE>=2 POINTED_DRIPSTONE>=4"),
            Map.entry("dark_forest", "DARK_OAK_LOG>=8 RED_MUSHROOM_BLOCK+BROWN_MUSHROOM_BLOCK>=5"),
            Map.entry("cherry", "CHERRY_LOG>=4 PINK_PETALS>=6"),
            Map.entry("ruin", "STONE_BRICKS+MOSSY_STONE_BRICKS+CRACKED_STONE_BRICKS+CHISELED_STONE_BRICKS>=40 CHEST=1"),
            Map.entry("stone", "FIRE=0 CHORUS_FLOWER=0 CHEST=0"),
            // 하늘 네더
            Map.entry("n_hub", "OBSIDIAN>=14 NETHER_PORTAL=6 RESPAWN_ANCHOR=1 CHEST=1 SOUL_LANTERN=4 CRYING_OBSIDIAN>=4"),
            Map.entry("n_quartz", "NETHER_QUARTZ_ORE>=60 NETHER_GOLD_ORE>=12 FIRE>=2"),
            Map.entry("n_glow", "GLOWSTONE>=60"),
            Map.entry("n_crimson", "CRIMSON_STEM>=8 NETHER_WART_BLOCK>=20 SHROOMLIGHT>=3 WEEPING_VINES+WEEPING_VINES_PLANT>=4"),
            Map.entry("n_warped", "WARPED_STEM>=8 WARPED_WART_BLOCK>=20 TWISTING_VINES+TWISTING_VINES_PLANT>=3 NETHER_SPROUTS>=4"),
            Map.entry("n_soul", "SOUL_SAND>=40 SOUL_SOIL>=60 NETHER_WART>=16 BONE_BLOCK>=40 SOUL_FIRE>=3"),
            Map.entry("n_delta", "BASALT>=60 MAGMA_BLOCK>=12 LAVA>=4 ANCIENT_DEBRIS=3"),
            Map.entry("n_fortress", "NETHER_BRICKS>=300 SPAWNER=2 CHEST=2 NETHER_WART>=9 NETHER_BRICK_FENCE>=24 NETHER_BRICK_STAIRS>=3"),
            Map.entry("n_bastion", "GOLD_BLOCK>=10 GILDED_BLACKSTONE>=12 POLISHED_BLACKSTONE_BRICKS+CRACKED_POLISHED_BLACKSTONE_BRICKS>=180 "
                    + "CHAIN>=6 CHEST=3 @PIGLIN>=4 @PIGLIN_BRUTE=1"),
            Map.entry("n_ruin_portal", "CRYING_OBSIDIAN>=12 OBSIDIAN>=6 GOLD_BLOCK>=2 CHEST=1 LAVA>=2"),
            Map.entry("n_lava", "LAVA>=60 MAGMA_BLOCK>=10 @STRIDER>=1"),
            Map.entry("n_debris", "ANCIENT_DEBRIS>=24 BLACKSTONE+BASALT>=1200 MAGMA_BLOCK>=20 CHEST=0"),
            Map.entry("n_stone", "CHEST=0 SPAWNER=0")
    );

    /** 자리까지 기억해 둘 블록 (특별 검사용). */
    private static final Set<Material> KEEP = EnumSet.of(Material.BEE_NEST, Material.GLOWSTONE, Material.DRIPSTONE_BLOCK,
            Material.CHEST, Material.SPAWNER, Material.CAVE_VINES, Material.CAVE_VINES_PLANT, Material.LILAC,
            Material.ROSE_BUSH, Material.PEONY, Material.ANCIENT_DEBRIS);
    private static final BlockFace[] SIX = {BlockFace.UP, BlockFace.DOWN, BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST};
    private static final Material[] FLOWERS = {Material.POPPY, Material.DANDELION, Material.CORNFLOWER, Material.ALLIUM,
            Material.AZURE_BLUET, Material.RED_TULIP, Material.ORANGE_TULIP, Material.WHITE_TULIP, Material.PINK_TULIP,
            Material.OXEYE_DAISY, Material.LILY_OF_THE_VALLEY, Material.BLUE_ORCHID};
    private static final Material[] TERRACOTTA = {Material.TERRACOTTA, Material.ORANGE_TERRACOTTA, Material.YELLOW_TERRACOTTA,
            Material.WHITE_TERRACOTTA, Material.RED_TERRACOTTA, Material.BROWN_TERRACOTTA, Material.LIGHT_GRAY_TERRACOTTA};

    private final AugSky plugin;
    private final World w;

    IslandCheck(AugSky plugin, World w) {
        this.plugin = plugin;
        this.w = w;
    }

    private static int radius(Isle is) {
        return (int) Math.ceil(is.r() * 1.3) + 3;
    }

    void run(List<Isle> isles, CommandSender to) {
        Set<Long> held = new HashSet<>();
        for (Isle is : isles) {
            int R = radius(is) + 1;
            for (int qx = (is.x() - R) >> 4; qx <= (is.x() + R) >> 4; qx++)
                for (int qz = (is.z() - R) >> 4; qz <= (is.z() + R) >> 4; qz++) {
                    if (!held.add(((long) qx << 32) | (qz & 0xffffffffL))) continue;
                    w.getChunkAt(qx, qz);
                    w.addPluginChunkTicket(qx, qz, plugin);
                }
        }
        to.sendMessage(Text.mm("<gray>섬 검사: 청크 " + held.size() + "개를 불러 두고 엔티티가 다 불려 올 때까지 5초 기다립니다..."));
        // 결과는 5초 뒤에 나오므로 RCON 처럼 그사이 끊기는 곳에서 불러도 볼 수 있게 서버 기록에도 남긴다
        boolean player = to instanceof Player;
        // 엔티티는 청크와 따로(비동기로) 불려 온다
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            int failed = 0;
            for (Isle is : isles) {
                List<String> fails = check(is);
                if (fails.isEmpty()) continue;
                failed++;
                for (String f : fails) {
                    String line = "FAIL " + is.kind() + " (" + is.x() + ", " + is.z() + "): " + f;
                    if (player) to.sendMessage(Text.mm("<#ff7070>" + line));
                    plugin.getLogger().warning(line);
                }
            }
            String done = "섬 검사: " + isles.size() + "곳, 실패 " + failed;
            if (player) to.sendMessage(Text.mm((failed == 0 ? "<#7cff8c>" : "<#ff7070>") + done));
            plugin.getLogger().info(done);
            for (long k : held) w.removePluginChunkTicket((int) (k >> 32), (int) k, plugin);
        }, 100);
    }

    private List<String> check(Isle is) {
        List<String> fails = new ArrayList<>();
        boolean nether = NetherMap.isNether(is.kind());
        int depth = nether ? NetherMap.checkDepth(is) : IslandKinds.depth(is);
        int y = IslandKinds.buildY(is), R = radius(is), lo = y - (depth + 6), hi = y + 24;
        Map<Material, Integer> n = new EnumMap<>(Material.class);
        Map<Material, List<Block>> at = new EnumMap<>(Material.class);
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                if (dx * dx + dz * dz > R * R) continue;
                for (int yy = lo; yy <= hi; yy++) {
                    Block b = w.getBlockAt(is.x() + dx, yy, is.z() + dz);
                    Material m = b.getType();
                    if (m.isAir()) continue;
                    n.merge(m, 1, Integer::sum);
                    if (KEEP.contains(m)) at.computeIfAbsent(m, k -> new ArrayList<>()).add(b);
                    if ((m == Material.SAND || m == Material.RED_SAND || m == Material.GRAVEL)) {
                        Block below = b.getRelative(BlockFace.DOWN);
                        if (below.getType().isAir() || below.isLiquid()) fails.add(m + " 아래가 비었음 (" + b.getX() + ", " + yy + ", " + b.getZ() + ")");
                    }
                }
            }
        Map<EntityType, Integer> e = new EnumMap<>(EntityType.class);
        Location c = new Location(w, is.x() + 0.5, (lo + hi) / 2.0, is.z() + 0.5);
        for (Entity en : w.getNearbyEntities(c, R, (hi - lo) / 2.0 + 1, R)) {
            double dx = en.getX() - c.getX(), dz = en.getZ() - c.getZ();
            if (dx * dx + dz * dz > R * R) continue;
            e.merge(en.getType(), 1, Integer::sum);
            if (en instanceof TextDisplay) fails.add("글자 표시가 남아 있음");
            if (en instanceof BlockDisplay && en.getPersistentDataContainer().has(Keys.BEAM)) fails.add("빛기둥이 남아 있음");
        }
        String need = NEED.get(is.kind());
        if (need != null) {
            for (String tok : need.split(" ")) {
                String op = tok.contains(">=") ? ">=" : tok.contains("<=") ? "<=" : "=";
                String[] kv = tok.split(op);
                int want = Integer.parseInt(kv[1]), have = 0;
                for (String name : kv[0].split("\\+")) {
                    have += name.startsWith("@") ? e.getOrDefault(EntityType.valueOf(name.substring(1)), 0)
                            : n.getOrDefault(Material.valueOf(name), 0);
                }
                boolean ok = switch (op) {
                    case ">=" -> have >= want;
                    case "<=" -> have <= want;
                    default -> have == want;
                };
                if (!ok) fails.add(kv[0] + " " + have + " (" + op + want + ")");
            }
        }
        special(is, y, n, at, e, fails);
        Biome b = nether ? NetherMap.biome(is.kind()) : IslandKinds.biome(is);
        if (b != null) {
            int edge = (int) Math.ceil(is.r() * 1.3) + 3;
            int[][] pts = {{0, 0}, {edge, 0}, {-edge, 0}, {0, edge}, {0, -edge}};
            for (int[] p : pts) {
                Biome got = w.getBiome(is.x() + p[0], y, is.z() + p[1]);
                if (!b.equals(got)) fails.add("생물군계 " + got.getKey().getKey() + " (" + p[0] + ", " + p[1] + ")");
            }
        }
        return fails;
    }

    /** 수로 못 세는 것들. */
    private void special(Isle is, int y, Map<Material, Integer> n, Map<Material, List<Block>> at, Map<EntityType, Integer> e, List<String> fails) {
        boolean fixed = is.seed() < 100;
        switch (is.kind()) {
            case "start" -> {
                Block b = w.getBlockAt(is.x() - 3, y + 1, is.z() - 3);
                Map<Material, Integer> want = Map.of(Material.LAVA_BUCKET, 1, Material.ICE, 2, Material.OAK_SAPLING, 1,
                        Material.WHEAT_SEEDS, 3, Material.BONE_MEAL, 3, Material.TORCH, 4);
                Map<Material, Integer> got = new EnumMap<>(Material.class);
                if (b.getState() instanceof Chest ch) {
                    for (ItemStack it : ch.getBlockInventory().getContents()) if (it != null) got.merge(it.getType(), it.getAmount(), Integer::sum);
                }
                if (!got.equals(want)) fails.add("시작 상자 " + got);
                if (n.getOrDefault(Material.OAK_LOG, 0) < 3 && n.getOrDefault(Material.OAK_SAPLING, 0) == 0) fails.add("나무 없음");
            }
            case "woods" -> {
                if (fixed && n.getOrDefault(Material.BIRCH_LOG, 0) < 3) fails.add("BIRCH_LOG " + n.getOrDefault(Material.BIRCH_LOG, 0) + " (>=3)");
            }
            case "ranch" -> {
                int cows = e.getOrDefault(EntityType.COW, 0), sheep = e.getOrDefault(EntityType.SHEEP, 0), want = fixed ? 3 : 2;
                if (cows != want || sheep != want) fails.add("소 " + cows + ", 양 " + sheep + " (" + want + ")");
            }
            case "meadow" -> {
                // 벌은 벌집에 들어가 있을 수도 있다
                int bees = e.getOrDefault(EntityType.BEE, 0);
                for (Block nest : at.getOrDefault(Material.BEE_NEST, List.of()))
                    if (nest.getState() instanceof org.bukkit.block.Beehive hive) bees += hive.getEntityCount();
                if (bees < 3) fails.add("벌 " + bees + " (>=3)");
                boolean ok = false;
                for (Block nest : at.getOrDefault(Material.BEE_NEST, List.of())) {
                    Block fire = nest.getRelative(0, -2, 0);
                    if (nest.getBlockData() instanceof Beehive h && h.getHoneyLevel() == 5
                            && fire.getBlockData() instanceof Campfire cf && cf.isLit()) ok = true;
                }
                if (!ok) fails.add("꿀 가득한 벌집 아래 피운 모닥불 없음");
                int species = 0;
                for (Material f : FLOWERS) if (n.getOrDefault(f, 0) > 0) species++;
                if (species < 8) fails.add("꽃 " + species + "종 (>=8)");
                int tall = 0;
                for (Material m : new Material[]{Material.LILAC, Material.ROSE_BUSH, Material.PEONY}) tall += n.getOrDefault(m, 0) / 2;
                if (tall < 2) fails.add("두 칸 꽃 " + tall + " (>=2)");
            }
            case "spider_den", "fortress" -> {
                EntityType want = is.kind().equals("fortress") ? EntityType.BLAZE : EntityType.SPIDER;
                for (Block s : at.getOrDefault(Material.SPAWNER, List.of()))
                    if (!(s.getState() instanceof CreatureSpawner cs) || cs.getSpawnedType() != want) fails.add("생성기 종류");
            }
            case "igloo" -> {
                if (!chestHas(at, it -> it.getType() == Material.IRON_PICKAXE && it.getEnchantmentLevel(Enchantment.SILK_TOUCH) == 1))
                    fails.add("섬세한 손길 곡괭이 없음");
            }
            case "prismarine_ruin" -> {
                if (!chestHas(at, it -> it.getType() == Material.NAUTILUS_SHELL)) fails.add("앵무조개 껍데기 없음");
            }
            case "shipwreck" -> {
                boolean ok = false;
                for (Block b : at.getOrDefault(Material.CHEST, List.of())) {
                    if (!(b.getState() instanceof Chest ch)) continue;
                    Inventory inv = ch.getBlockInventory();
                    if (inv.contains(Material.NAUTILUS_SHELL) && has(inv, IslandCheck::silkBook)) ok = true;
                }
                if (!ok) fails.add("고물 상자에 앵무조개·섬세한 손길 책 없음");
            }
            case "nether_vein" -> {
                int held = 0;
                for (Block g : at.getOrDefault(Material.GLOWSTONE, List.of())) {
                    for (int k = 1; k <= 4; k++) {
                        Material m = g.getRelative(0, -k, 0).getType();
                        if (m.isSolid() && m != Material.GLOWSTONE) {
                            held++;
                            break;
                        }
                    }
                }
                if (held < 10) fails.add("바닥 위 발광석 " + held + " (>=10)");
            }
            case "n_hub" -> {
                int portal = 0;
                for (int dx = -1; dx <= 0; dx++)
                    for (int dy = 2; dy <= 4; dy++) {
                        Block p = w.getBlockAt(is.x() + dx, y + dy, is.z());
                        if (p.getType() == Material.NETHER_PORTAL && p.getBlockData() instanceof Orientable o && o.getAxis() == Axis.X) portal++;
                    }
                if (portal != 6) fails.add("쉼터 문 " + portal + "/6");
                if (!(w.getBlockAt(is.x() - 3, y + 1, is.z() + 3).getState() instanceof Chest)) fails.add("쉼터 상자 없음");
            }
            case "n_fortress" -> {
                Set<EntityType> types = EnumSet.noneOf(EntityType.class);
                for (Block s : at.getOrDefault(Material.SPAWNER, List.of())) {
                    if (!(s.getState() instanceof CreatureSpawner cs)) continue;
                    types.add(cs.getSpawnedType());
                    // 빛과 상관없이 나와야 한다 (방에 횃불을 달아도 위더 해골이 계속 나오게)
                    List<SpawnerEntry> pot = cs.getPotentialSpawns();
                    SpawnRule rule = pot.isEmpty() ? null : pot.get(0).getSpawnRule();
                    if (rule == null || rule.getMaxBlockLight() < 15) fails.add("생성기가 빛에 따라 멈춤 (" + cs.getSpawnedType() + ")");
                }
                if (!types.equals(EnumSet.of(EntityType.WITHER_SKELETON, EntityType.BLAZE))) fails.add("생성기 종류 " + types);
                lootTables(at, fails, Map.of("nether_bridge", 2));
            }
            case "n_bastion" -> lootTables(at, fails, Map.of("bastion_treasure", 1, "bastion_other", 2));
            case "n_ruin_portal" -> lootTables(at, fails, Map.of("ruined_portal", 1));
            case "n_delta", "n_debris" -> {
                int min = is.kind().equals("n_debris") ? 10 : 5;
                for (Block d : at.getOrDefault(Material.ANCIENT_DEBRIS, List.of())) {
                    if (y - d.getY() < min) fails.add("고대 잔해가 얕음 (" + d.getX() + ", " + d.getY() + ", " + d.getZ() + ")");
                    for (BlockFace f : SIX) {
                        if (d.getRelative(f).getType().isSolid()) continue;
                        fails.add("드러난 고대 잔해 (" + d.getX() + ", " + d.getY() + ", " + d.getZ() + ")");
                        break;
                    }
                }
            }
            case "lagoon" -> {
                for (int dx = -2; dx <= 2; dx++)
                    for (int dz = -2; dz <= 2; dz++)
                        for (int yy = y - 1; yy <= y; yy++)
                            if (w.getBlockAt(is.x() + dx, yy, is.z() + dz).getType() != Material.WATER) {
                                fails.add("가운데 물이 트여 있지 않음 (" + dx + ", " + (yy - y) + ", " + dz + ")");
                                return;
                            }
            }
            case "badlands" -> {
                int colours = 0;
                for (Material m : TERRACOTTA) if (n.getOrDefault(m, 0) > 0) colours++;
                if (colours < 5) fails.add("테라코타 " + colours + "색 (>=5)");
            }
            case "lush_cave" -> {
                int berries = 0;
                for (Material m : new Material[]{Material.CAVE_VINES, Material.CAVE_VINES_PLANT})
                    for (Block b : at.getOrDefault(m, List.of()))
                        if (b.getBlockData() instanceof CaveVinesPlant cv && cv.isBerries()) berries++;
                if (berries < 3) fails.add("열매 달린 동굴 덩굴 " + berries + " (>=3)");
            }
            case "deep_mine" -> {
                boolean ok = false;
                for (Block b : at.getOrDefault(Material.DRIPSTONE_BLOCK, List.of()))
                    if (b.getRelative(BlockFace.UP).getType() == Material.WATER && b.getRelative(BlockFace.DOWN).getType() == Material.POINTED_DRIPSTONE) ok = true;
                if (!ok) fails.add("물 아래 점적석 블록에 매달린 점적석 없음");
            }
            default -> {
            }
        }
    }

    /**
     * 바닐라 전리품 표를 단 상자 수. 열어 본 상자는 표가 없어져 셀 수 없으니(내용을 보면 그때 굴려진다) 넘어간다.
     * 아무도 안 연 섬이면 표마다 수가 정확히 맞아야 한다.
     */
    private static void lootTables(Map<Material, List<Block>> at, List<String> fails, Map<String, Integer> want) {
        Map<String, Integer> got = new TreeMap<>();
        int opened = 0;
        for (Block b : at.getOrDefault(Material.CHEST, List.of())) {
            if (!(b.getState() instanceof Chest ch)) continue;
            LootTable t = ch.getLootTable();
            if (t == null) opened++;
            else got.merge(t.getKey().getKey().replace("chests/", ""), 1, Integer::sum);
        }
        for (Map.Entry<String, Integer> en : got.entrySet()) {
            if (en.getValue() > want.getOrDefault(en.getKey(), 0)) fails.add("상자 전리품 표 " + got + " (" + want + ")");
        }
        if (opened == 0 && !got.equals(new TreeMap<>(want))) fails.add("상자 전리품 표 " + got + " (" + want + ")");
    }

    private static boolean silkBook(ItemStack it) {
        return it.getType() == Material.ENCHANTED_BOOK && it.getItemMeta() instanceof EnchantmentStorageMeta m
                && m.hasStoredEnchant(Enchantment.SILK_TOUCH);
    }

    private static boolean has(Inventory inv, java.util.function.Predicate<ItemStack> p) {
        for (ItemStack it : inv.getContents()) if (it != null && p.test(it)) return true;
        return false;
    }

    private static boolean chestHas(Map<Material, List<Block>> at, java.util.function.Predicate<ItemStack> p) {
        for (Block b : at.getOrDefault(Material.CHEST, List.of()))
            if (b.getState() instanceof Chest ch && has(ch.getBlockInventory(), p)) return true;
        return false;
    }
}
