package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.Tier;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameRule;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Chest;
import org.bukkit.block.CreatureSpawner;
import org.bukkit.block.data.Ageable;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.type.EndPortalFrame;
import org.bukkit.entity.Animals;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Interaction;
import org.bukkit.entity.Marker;
import org.bukkit.entity.TextDisplay;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.function.Consumer;

/**
 * 맵 전체를 짓는다. 빈 공허 월드에서 /증강관리 맵생성 을 한 번 실행하면 된다.
 * 배포용 맵 파일은 이 코드로 지은 월드를 그대로 묶은 것이다.
 *
 * 반지름 약 380m. 가운데 시작의 섬 둘레는 초원, 서쪽은 서리, 동북쪽은 화염, 북서쪽은 공허, 남쪽은 바다 지역이다.
 * 제단(실버 16, 골드 9, 프리즘 5)은 한 번 쓰면 힘을 잃고, 각 지역 끝의 둥지에는 보스가 산다.
 * 같은 시드로 지으면 언제나 같은 맵이 나온다.
 */
public final class MapBuilder {
    public record Place(String name, int x, int y, int z) {}

    /** 큰 장소. 안내판과 /증강 제단 에서 쓴다. 제단 위치는 AltarService 기록을 쓴다. */
    public static final List<Place> PLACES = List.of(
            new Place("시작의 섬", 0, 64, 0),
            new Place("서리 지역", -170, 62, 50),
            new Place("화염 지역", 150, 58, -110),
            new Place("공허 지역", -150, 92, -200),
            new Place("바다 지역", 20, 60, 190),
            new Place("서리 균열", -205, 62, 62),
            new Place("화염 균열", 196, 58, -134),
            new Place("공허 균열", -206, 98, -246),
            new Place("서리 군주의 둥지", -262, 62, 80),
            new Place("화염 거신의 둥지", 246, 56, -170),
            new Place("공허 군주의 둥지", -246, 104, -302),
            new Place("끝의 섬", 300, 72, 196)
    );

    public enum Region { PLAINS, FROST, FLAME, VOID, OCEAN, WILD }

    /** 지을 섬 하나. */
    record Isle(String kind, int x, int y, int z, double r, Region region, Tier tier, long seed) {}

    private static final long SEED = 20261005L;

    private final AugSky plugin;
    private World w;

    public MapBuilder(AugSky plugin) {
        this.plugin = plugin;
    }

    public static Place place(String name) {
        for (Place p : PLACES) if (p.name().equals(name)) return p;
        return null;
    }

    /** 지역: 가운데는 초원, 바깥은 방향에 따라 나뉜다. */
    public static Region region(double x, double z) {
        double r = Math.hypot(x, z);
        if (r < 105) return Region.PLAINS;
        double b = Math.toDegrees(Math.atan2(x, -z));
        if (b < 0) b += 360;
        if (b >= 300) return Region.VOID;
        if (b >= 222) return Region.FROST;
        if (b >= 140) return Region.OCEAN;
        if (b >= 30 && b < 125) return Region.FLAME;
        return Region.WILD;
    }

    private static int baseY(Region g, double x, double z, Random rnd) {
        double r = Math.hypot(x, z);
        return switch (g) {
            case PLAINS -> 64 + rnd.nextInt(9) - 4;
            case FROST -> 62 + rnd.nextInt(9) - 4;
            case FLAME -> 57 + rnd.nextInt(9) - 4;
            case VOID -> (int) (66 + Math.min(34, (r - 105) * 0.16)) + rnd.nextInt(7) - 3;
            case OCEAN -> 60 + rnd.nextInt(5) - 2;
            case WILD -> 68 + rnd.nextInt(11) - 5;
        };
    }

    // ------------------------------------------------------------------ 배치

    /** 섬 목록을 만든다. 제단과 둥지를 먼저 놓고, 남은 자리에 자원 섬을 흩뿌린다. */
    public static List<Isle> plan() {
        Random rnd = new Random(SEED);
        List<Isle> out = new ArrayList<>();
        out.add(new Isle("start", 0, 64, 0, 6, Region.PLAINS, null, 1));
        out.add(new Isle("sand", -36, 62, 30, 4.4, Region.PLAINS, null, 11));
        out.add(new Isle("forest", 14, 67, -44, 5.6, Region.PLAINS, null, 12));

        for (String n : List.of("서리", "화염", "공허")) {
            Place lair = place(switch (n) {
                case "서리" -> "서리 군주의 둥지";
                case "화염" -> "화염 거신의 둥지";
                default -> "공허 군주의 둥지";
            });
            Place rift = place(n + " 균열");
            String id = switch (n) {
                case "서리" -> "frost";
                case "화염" -> "flame";
                default -> "void";
            };
            out.add(new Isle("lair_" + id, lair.x(), lair.y(), lair.z(), 18, region(lair.x(), lair.z()), null, 40 + out.size()));
            out.add(new Isle("rift_" + id, rift.x(), rift.y(), rift.z(), 11, region(rift.x(), rift.z()), null, 50 + out.size()));
        }
        Place end = place("끝의 섬");
        out.add(new Isle("end", end.x(), end.y(), end.z(), 7.5, Region.OCEAN, null, 77));

        // 제단: 실버는 가까운 곳 사방에, 골드는 중간, 프리즘은 맵 끝자락에
        altarRing(out, rnd, Tier.SILVER, 16, new double[]{48, 82, 118, 150}, 11);
        altarRing(out, rnd, Tier.GOLD, 9, new double[]{175, 215, 250}, 31);
        altarRing(out, rnd, Tier.PRISM, 5, new double[]{300, 335}, 47);

        // 자원 섬: 안쪽일수록 촘촘하게
        scatter(out, rnd, 30, 110, 14, 30);
        scatter(out, rnd, 110, 230, 18, 36);
        scatter(out, rnd, 230, 365, 14, 40);
        return out;
    }

    private static void altarRing(List<Isle> out, Random rnd, Tier tier, int count, double[] radii, double offsetDeg) {
        for (int i = 0; i < count; i++) {
            for (int tries = 0; tries < 40; tries++) {
                double a = Math.toRadians(offsetDeg + i * 360.0 / count + rnd.nextDouble(-7, 7) + tries * 3);
                double r = radii[i % radii.length] + rnd.nextDouble(-8, 8);
                int x = (int) Math.round(Math.sin(a) * r), z = (int) Math.round(-Math.cos(a) * r);
                if (!free(out, x, z, 7, 26)) continue;
                Region g = region(x, z);
                out.add(new Isle("altar", x, baseY(g, x, z, rnd), z, 7, g, tier, 100 + out.size()));
                break;
            }
        }
    }

    private static void scatter(List<Isle> out, Random rnd, double rMin, double rMax, int count, double gap) {
        int placed = 0;
        for (int tries = 0; tries < 4000 && placed < count; tries++) {
            double a = rnd.nextDouble(Math.PI * 2);
            double r = Math.sqrt(rnd.nextDouble(rMin * rMin, rMax * rMax));
            int x = (int) Math.round(Math.sin(a) * r), z = (int) Math.round(-Math.cos(a) * r);
            double size = 4.5 + rnd.nextDouble() * 4.5;
            if (!free(out, x, z, size, gap)) continue;
            Region g = region(x, z);
            String kind = pickKind(g, rnd);
            out.add(new Isle(kind, x, baseY(g, x, z, rnd), z, size, g, null, 1000 + out.size()));
            placed++;
        }
    }

    private static boolean free(List<Isle> out, int x, int z, double r, double gap) {
        for (Isle i : out) {
            double d = Math.hypot(i.x() - x, i.z() - z);
            if (d < i.r() + r + gap * 0.5) return false;
        }
        return true;
    }

    private static String pickKind(Region g, Random rnd) {
        String[] kinds = switch (g) {
            case PLAINS -> new String[]{"oak", "birch", "meadow", "farm", "pumpkin", "quarry", "pond", "pasture", "mushroom", "sandy"};
            case FROST -> new String[]{"spruce", "icespike", "frozen_lake", "frost_quarry", "igloo"};
            case FLAME -> new String[]{"basalt", "crimson", "warped", "soul_valley", "fortress", "obsidian"};
            case VOID -> new String[]{"chorus", "geode", "obsidian_spire", "purpur_ruin", "end_rock"};
            case OCEAN -> new String[]{"reef", "prismarine_ruin", "beach", "copper", "clay_bank"};
            case WILD -> new String[]{"mountain", "dark_forest", "jungle", "cherry", "savanna", "ruin"};
        };
        return kinds[rnd.nextInt(kinds.length)];
    }

    // ------------------------------------------------------------------ 짓기

    /** 맵 전체를 짓는다. 서버가 멈추지 않도록 한 틱에 섬 하나씩 짓고, 다 지으면 done 을 부른다. */
    public void buildAll(World world, Consumer<String> progress, Runnable done) {
        this.w = world;
        long t0 = System.currentTimeMillis();
        List<Isle> isles = plan();
        clearParts(isles);
        plugin.altars().clearRegistry(world);
        plugin.mobs().lairs().clearRegistry(world);
        new BukkitRunnable() {
            int i = 0;

            @Override
            public void run() {
                long until = System.currentTimeMillis() + 40;
                while (i < isles.size() && System.currentTimeMillis() < until) {
                    Isle is = isles.get(i++);
                    try {
                        build(is);
                    } catch (RuntimeException ex) {
                        plugin.getLogger().warning("섬 " + is.kind() + " (" + is.x() + ", " + is.z() + ") 짓기 실패: " + ex);
                    }
                    if (i % 10 == 0 && progress != null) progress.accept("섬 " + i + " / " + isles.size());
                }
                if (i < isles.size()) return;
                cancel();
                signs(isles);
                w.setSpawnLocation(0, 65, 0);
                w.setGameRule(GameRule.SPAWN_RADIUS, 0);
                w.setGameRule(GameRule.SPAWN_CHUNK_RADIUS, 2);
                w.setTime(1000);
                plugin.altars().scanLoaded();
                plugin.mobs().scanLoaded();
                plugin.getLogger().info("맵 생성 완료: 섬 " + isles.size() + "개 (" + (System.currentTimeMillis() - t0) + "ms)");
                if (done != null) done.run();
            }
        }.runTaskTimer(plugin, 1, 1);
    }

    private void clearParts(List<Isle> isles) {
        for (Isle is : isles) {
            Location c = new Location(w, is.x(), is.y(), is.z());
            c.getChunk().load();
            double r = is.r() + 12;
            for (Entity e : w.getNearbyEntities(c, r, 80, r)) {
                if (e.getPersistentDataContainer().has(Keys.MAP_PART)) e.remove();
            }
        }
    }

    private void build(Isle is) {
        Random r = new Random(SEED ^ is.seed() * 31);
        int x = is.x(), y = is.y(), z = is.z();
        switch (is.kind()) {
            case "start" -> startIsland(x, y, z);
            case "sand" -> sandIsland(x, y, z);
            case "forest" -> forestIsland(x, y, z);
            case "altar" -> altarIsland(is, r);
            case "end" -> endIsland(x, y, z);
            default -> {
                if (is.kind().startsWith("lair_")) lairIsland(is, r);
                else if (is.kind().startsWith("rift_")) riftIsland(is, r);
                else resourceIsland(is, r);
            }
        }
    }

    // ------------------------------------------------------------------ 블록 도우미

    private void set(int x, int y, int z, Material m) {
        w.getBlockAt(x, y, z).setType(m, false);
    }

    private void set(int x, int y, int z, BlockData d) {
        w.getBlockAt(x, y, z).setBlockData(d, false);
    }

    private boolean air(int x, int y, int z) {
        return w.getBlockAt(x, y, z).getType().isAir();
    }

    /** 섬 윗면의 높이 (없으면 Integer.MIN_VALUE). */
    private int top(int x, int z, int fromY) {
        for (int y = fromY + 12; y > fromY - 20; y--) {
            Material m = w.getBlockAt(x, y, z).getType();
            if (!m.isAir() && m.isSolid()) return y;
        }
        return Integer.MIN_VALUE;
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

    /** 뾰족한 가시: 아래가 굵고 위로 갈수록 가늘다. */
    private void spike(int x, int y, int z, int h, Material m, Material tip) {
        for (int i = 0; i < h; i++) {
            double rr = Math.max(0, 1.6 * (1 - (double) i / h));
            int R = (int) Math.ceil(rr);
            for (int dx = -R; dx <= R; dx++)
                for (int dz = -R; dz <= R; dz++)
                    if (dx * dx + dz * dz <= rr * rr + 0.3) set(x + dx, y + i, z + dz, m);
        }
        if (tip != null) set(x, y + h, z, tip);
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

    private void spawner(int x, int y, int z, EntityType type) {
        Block b = w.getBlockAt(x, y, z);
        b.setType(Material.SPAWNER, false);
        if (b.getState() instanceof CreatureSpawner cs) {
            cs.setSpawnedType(type);
            cs.update(true, false);
        }
    }

    private void tree(int x, int y, int z, TreeType type, Material fallback) {
        if (!w.generateTree(new Location(w, x, y, z), type) && fallback != null) {
            // 공간이 모자라 실패하면 묘목이라도 심어 둔다
            set(x, y, z, fallback);
        }
    }

    private void crop(int x, int y, int z, Material m) {
        set(x, y - 1, z, Material.FARMLAND);
        BlockData d = m.createBlockData();
        if (d instanceof Ageable ag) ag.setAge(ag.getMaximumAge());
        set(x, y, z, d);
    }

    private void animals(int x, int y, int z, Class<? extends Animals> cls, int n) {
        for (int i = 0; i < n; i++) {
            w.spawn(new Location(w, x + 0.5 + (i % 2), y, z + 0.5 + (i / 2)), cls, a -> {
                a.setPersistent(true);
                a.setRemoveWhenFarAway(false);
            });
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

    private Interaction interaction(double x, double y, double z, float width, float height, org.bukkit.NamespacedKey key, String value) {
        return tag(w.spawn(new Location(w, x, y, z), Interaction.class, i -> {
            i.setInteractionWidth(width);
            i.setInteractionHeight(height);
            i.setResponsive(true);
            i.getPersistentDataContainer().set(key, PersistentDataType.STRING, value);
        }));
    }

    // ------------------------------------------------------------------ 보물 상자

    private void loot(Inventory inv, Random r, int rolls, Object... table) {
        // table: (ItemStack 또는 "item:id*n" 문자열, 가중치) 쌍
        int total = 0;
        for (int i = 1; i < table.length; i += 2) total += (Integer) table[i];
        for (int k = 0; k < rolls; k++) {
            int pick = r.nextInt(total);
            for (int i = 0; i < table.length; i += 2) {
                pick -= (Integer) table[i + 1];
                if (pick >= 0) continue;
                ItemStack it = table[i] instanceof ItemStack s ? s.clone() : spec((String) table[i]);
                if (it != null) inv.setItem(r.nextInt(inv.getSize()), it);
                break;
            }
        }
    }

    private ItemStack spec(String s) {
        String[] parts = s.split("\\*");
        int n = parts.length > 1 ? Integer.parseInt(parts[1]) : 1;
        return plugin.items().spec(parts[0], n);
    }

    private void treasure(int x, int y, int z, Random r, Region g) {
        Inventory inv = chest(x, y, z, BlockFace.values()[r.nextInt(4)]);
        loot(inv, r, 3 + r.nextInt(3),
                "item:shard*2", 10, "item:shard*4", 4, "IRON_INGOT*4", 8, "GOLD_INGOT*3", 5, "DIAMOND*1", 3,
                "BREAD*4", 6, "TORCH*8", 5, "ENDER_PEARL*2", 2, "item:ticket_silver", 1,
                g == Region.FROST ? "item:essence_frost*2" : g == Region.FLAME ? "item:essence_flame*2" : g == Region.VOID ? "item:essence_void*2" : "BONE*6", 4,
                g == Region.OCEAN ? "NAUTILUS_SHELL*1" : "FEATHER*4", 3);
    }

    // ------------------------------------------------------------------ 시작 근처

    private void startIsland(int cx, int y, int cz) {
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
        tree(cx + 3, y + 1, cz - 3, TreeType.TREE, Material.OAK_SAPLING);
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

    private void sandIsland(int x, int y, int z) {
        blob(x, y, z, 4.2, 5, Material.SAND, Material.SAND, Material.SANDSTONE, 11, null, 0);
        set(x + 1, y + 1, z + 1, Material.CACTUS);
        set(x + 1, y + 2, z + 1, Material.CACTUS);
        Inventory inv = chest(x - 1, y + 1, z - 1, BlockFace.EAST);
        inv.addItem(new ItemStack(Material.OBSIDIAN, 10), new ItemStack(Material.SUGAR_CANE, 2),
                new ItemStack(Material.CACTUS, 2), new ItemStack(Material.SAND, 16), new ItemStack(Material.SWEET_BERRIES, 3),
                plugin.items().create("shard", 3));
    }

    private void forestIsland(int x, int y, int z) {
        blob(x, y, z, 5.5, 6, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, 12,
                new Material[]{Material.COAL_ORE, Material.IRON_ORE}, 0.08);
        tree(x - 2, y + 1, z + 1, TreeType.TREE, Material.OAK_SAPLING);
        tree(x + 2, y + 1, z - 2, TreeType.BIRCH, Material.BIRCH_SAPLING);
        set(x + 2, y + 1, z + 2, Material.SHORT_GRASS);
        set(x, y + 1, z - 3, Material.POPPY);
        set(x - 3, y + 1, z - 1, Material.DANDELION);
    }

    // ------------------------------------------------------------------ 자원 섬

    private record Ground(Material top, Material mid, Material bottom, Material[] ores, double oreChance) {}

    private static Ground ground(Region g) {
        return switch (g) {
            case PLAINS -> new Ground(Material.GRASS_BLOCK, Material.DIRT, Material.STONE,
                    new Material[]{Material.COAL_ORE, Material.IRON_ORE, Material.COPPER_ORE}, 0.05);
            case FROST -> new Ground(Material.SNOW_BLOCK, Material.PACKED_ICE, Material.STONE,
                    new Material[]{Material.IRON_ORE, Material.LAPIS_ORE, Material.COAL_ORE, Material.DIAMOND_ORE}, 0.05);
            case FLAME -> new Ground(Material.NETHERRACK, Material.NETHERRACK, Material.BLACKSTONE,
                    new Material[]{Material.NETHER_GOLD_ORE, Material.NETHER_QUARTZ_ORE, Material.GILDED_BLACKSTONE}, 0.07);
            case VOID -> new Ground(Material.END_STONE, Material.END_STONE, Material.OBSIDIAN,
                    new Material[]{Material.DIAMOND_ORE, Material.EMERALD_ORE, Material.GOLD_ORE}, 0.03);
            case OCEAN -> new Ground(Material.SAND, Material.SANDSTONE, Material.PRISMARINE,
                    new Material[]{Material.COPPER_ORE, Material.CLAY, Material.LAPIS_ORE}, 0.06);
            case WILD -> new Ground(Material.GRASS_BLOCK, Material.COARSE_DIRT, Material.ANDESITE,
                    new Material[]{Material.IRON_ORE, Material.GOLD_ORE, Material.REDSTONE_ORE, Material.COAL_ORE}, 0.06);
        };
    }

    private void resourceIsland(Isle is, Random r) {
        int x = is.x(), y = is.y(), z = is.z();
        double rad = is.r();
        int depth = (int) Math.max(4, rad * 1.1);
        Ground g = ground(is.region());
        long seed = is.seed();
        switch (is.kind()) {
            // ---- 초원
            case "oak" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                trees(x, y, z, rad, r, TreeType.TREE, TreeType.BIG_TREE, Material.OAK_SAPLING);
                flowers(x, y, z, rad, r, Material.POPPY, Material.DANDELION, Material.SHORT_GRASS);
            }
            case "birch" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                trees(x, y, z, rad, r, TreeType.BIRCH, TreeType.TALL_BIRCH, Material.BIRCH_SAPLING);
                flowers(x, y, z, rad, r, Material.LILY_OF_THE_VALLEY, Material.OXEYE_DAISY, Material.SHORT_GRASS);
            }
            case "meadow" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, null, 0);
                flowers(x, y, z, rad, r, Material.CORNFLOWER, Material.ALLIUM, Material.AZURE_BLUET, Material.RED_TULIP,
                        Material.ORANGE_TULIP, Material.PINK_TULIP, Material.SHORT_GRASS, Material.SHORT_GRASS);
                set(x, y + 1, z, Material.BEE_NEST);
                animals(x + 2, y + 1, z, org.bukkit.entity.Sheep.class, 2);
            }
            case "farm" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, null, 0);
                Material[] crops = {Material.WHEAT, Material.CARROTS, Material.POTATOES, Material.BEETROOTS};
                for (int dx = -3; dx <= 3; dx++) {
                    for (int dz = -3; dz <= 3; dz++) {
                        if (top(x + dx, z + dz, y) != y) continue;
                        if (dx == 0 && dz == 0) set(x, y, z, Material.WATER);
                        else crop(x + dx, y + 1, z + dz, crops[Math.floorMod(dx + 3, 4)]);
                    }
                }
                set(x + 4, y + 1, z, Material.COMPOSTER);
                animals(x - 4, y + 1, z - 1, org.bukkit.entity.Chicken.class, 3);
            }
            case "pumpkin" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, null, 0);
                for (int i = 0; i < 9; i++) {
                    int dx = r.nextInt(7) - 3, dz = r.nextInt(7) - 3;
                    if (top(x + dx, z + dz, y) == y) set(x + dx, y + 1, z + dz, r.nextBoolean() ? Material.PUMPKIN : Material.MELON);
                }
                set(x, y + 1, z, Material.HAY_BLOCK);
                set(x, y + 2, z, Material.CARVED_PUMPKIN);
            }
            case "quarry" -> {
                blob(x, y, z, rad, depth + 2, Material.STONE, Material.STONE, Material.STONE, seed,
                        new Material[]{Material.COAL_ORE, Material.IRON_ORE, Material.COPPER_ORE, Material.GOLD_ORE, Material.REDSTONE_ORE}, 0.12);
                for (int i = 0; i < 4; i++) column(x + r.nextInt(5) - 2, y + 1, z + r.nextInt(5) - 2, 1 + r.nextInt(3),
                        r.nextBoolean() ? Material.COBBLESTONE : Material.MOSSY_COBBLESTONE);
                set(x + 2, y + 1, z + 2, Material.TORCH);
            }
            case "pond" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.CLAY, Material.STONE, seed, null, 0);
                disc(x, y, z, Math.max(1.5, rad * 0.45), Material.WATER);
                disc(x, y - 1, z, Math.max(1.5, rad * 0.45), Material.CLAY);
                int pr = (int) Math.ceil(Math.max(1.5, rad * 0.45)) + 1;
                for (int i = 0; i < 4; i++) {
                    int dx = i < 2 ? (i == 0 ? pr : -pr) : 0, dz = i >= 2 ? (i == 2 ? pr : -pr) : 0;
                    if (top(x + dx, z + dz, y) == y) {
                        set(x + dx, y, z + dz, Material.SAND);
                        column(x + dx, y + 1, z + dz, 2, Material.SUGAR_CANE);
                    }
                }
                set(x, y + 1, z, Material.LILY_PAD);
            }
            case "pasture" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, null, 0);
                flowers(x, y, z, rad, r, Material.SHORT_GRASS, Material.SHORT_GRASS, Material.DANDELION);
                animals(x - 1, y + 1, z - 1, org.bukkit.entity.Cow.class, 2);
                animals(x + 1, y + 1, z + 1, org.bukkit.entity.Sheep.class, 2);
                animals(x - 2, y + 1, z + 2, org.bukkit.entity.Pig.class, 1);
            }
            case "mushroom" -> {
                blob(x, y, z, rad, depth, Material.MYCELIUM, Material.DIRT, Material.STONE, seed, null, 0);
                tree(x - 1, y + 1, z - 1, TreeType.RED_MUSHROOM, Material.RED_MUSHROOM);
                tree(x + 2, y + 1, z + 2, TreeType.BROWN_MUSHROOM, Material.BROWN_MUSHROOM);
                animals(x + 2, y + 1, z - 2, org.bukkit.entity.MushroomCow.class, 1);
            }
            case "sandy" -> {
                blob(x, y, z, rad, depth, Material.SAND, Material.SANDSTONE, Material.SANDSTONE, seed, null, 0);
                for (int i = 0; i < 3; i++) {
                    int dx = r.nextInt(5) - 2, dz = r.nextInt(5) - 2;
                    if (top(x + dx, z + dz, y) == y) column(x + dx, y + 1, z + dz, 1 + r.nextInt(3), Material.CACTUS);
                }
                set(x, y + 1, z, Material.DEAD_BUSH);
            }
            // ---- 서리
            case "spruce" -> {
                blob(x, y, z, rad, depth, Material.SNOW_BLOCK, Material.DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                for (int i = 0; i < 3; i++) {
                    int dx = r.nextInt(5) - 2, dz = r.nextInt(5) - 2;
                    set(x + dx * 2, y, z + dz * 2, Material.PODZOL);
                    tree(x + dx * 2, y + 1, z + dz * 2, i == 0 ? TreeType.TALL_REDWOOD : TreeType.REDWOOD, Material.SPRUCE_SAPLING);
                }
                snowLayer(x, y, z, rad);
            }
            case "icespike" -> {
                blob(x, y, z, rad, depth, Material.SNOW_BLOCK, Material.PACKED_ICE, Material.PACKED_ICE, seed, g.ores(), g.oreChance());
                spike(x, y + 1, z, 8 + r.nextInt(6), Material.PACKED_ICE, Material.BLUE_ICE);
                spike(x + 3, y + 1, z - 2, 4 + r.nextInt(3), Material.PACKED_ICE, null);
                spike(x - 3, y + 1, z + 2, 3 + r.nextInt(3), Material.BLUE_ICE, null);
            }
            case "frozen_lake" -> {
                blob(x, y, z, rad, depth, Material.SNOW_BLOCK, Material.STONE, Material.STONE, seed, g.ores(), g.oreChance());
                disc(x, y, z, rad * 0.6, Material.ICE);
                disc(x, y - 1, z, rad * 0.5, Material.WATER);
                set(x + (int) (rad * 0.7), y + 1, z, Material.SPRUCE_SAPLING);
            }
            case "frost_quarry" -> {
                blob(x, y, z, rad, depth + 2, Material.SNOW_BLOCK, Material.STONE, Material.STONE, seed,
                        new Material[]{Material.IRON_ORE, Material.LAPIS_ORE, Material.DIAMOND_ORE, Material.COAL_ORE}, 0.13);
                spike(x + 2, y + 1, z + 1, 3, Material.BLUE_ICE, null);
                set(x - 2, y + 1, z, Material.LANTERN);
            }
            case "igloo" -> {
                blob(x, y, z, rad, depth, Material.SNOW_BLOCK, Material.PACKED_ICE, Material.STONE, seed, g.ores(), g.oreChance());
                for (int dx = -3; dx <= 3; dx++)
                    for (int dy = 0; dy <= 3; dy++)
                        for (int dz = -3; dz <= 3; dz++) {
                            double d = Math.sqrt(dx * dx + dy * dy * 1.6 + dz * dz);
                            if (d <= 3.2 && d > 2.2) set(x + dx, y + 1 + dy, z + dz, Material.SNOW_BLOCK);
                        }
                set(x, y + 1, z + 3, Material.AIR);
                set(x, y + 2, z + 3, Material.AIR);
                set(x - 1, y + 2, z, Material.LANTERN);
                treasure(x + 1, y + 1, z - 1, r, Region.FROST);
            }
            // ---- 화염
            case "basalt" -> {
                blob(x, y, z, rad, depth, Material.BASALT, Material.BLACKSTONE, Material.BLACKSTONE, seed, g.ores(), g.oreChance());
                for (int i = 0; i < 5; i++) column(x + r.nextInt(7) - 3, y + 1, z + r.nextInt(7) - 3, 2 + r.nextInt(5), Material.BASALT);
                set(x, y, z, Material.MAGMA_BLOCK);
                set(x + 1, y, z, Material.MAGMA_BLOCK);
            }
            case "crimson" -> {
                blob(x, y, z, rad, depth, Material.CRIMSON_NYLIUM, Material.NETHERRACK, Material.NETHERRACK, seed, g.ores(), g.oreChance());
                tree(x, y + 1, z, TreeType.CRIMSON_FUNGUS, Material.CRIMSON_FUNGUS);
                set(x + 3, y + 1, z + 1, Material.CRIMSON_ROOTS);
                set(x - 2, y + 1, z - 2, Material.CRIMSON_FUNGUS);
                set(x + 1, y - 1, z - 3, Material.SHROOMLIGHT);
            }
            case "warped" -> {
                blob(x, y, z, rad, depth, Material.WARPED_NYLIUM, Material.NETHERRACK, Material.NETHERRACK, seed, g.ores(), g.oreChance());
                tree(x, y + 1, z, TreeType.WARPED_FUNGUS, Material.WARPED_FUNGUS);
                set(x - 3, y + 1, z, Material.WARPED_ROOTS);
                set(x + 2, y + 1, z + 2, Material.TWISTING_VINES);
            }
            case "soul_valley" -> {
                blob(x, y, z, rad, depth, Material.SOUL_SOIL, Material.SOUL_SAND, Material.BLACKSTONE, seed, g.ores(), g.oreChance());
                for (int i = 0; i < 3; i++) column(x + r.nextInt(7) - 3, y + 1, z + r.nextInt(7) - 3, 2 + r.nextInt(3), Material.BONE_BLOCK);
                set(x, y, z, Material.SOUL_SAND);
                set(x, y + 1, z, Material.NETHER_WART);
                set(x + 1, y, z, Material.SOUL_SAND);
                set(x + 1, y + 1, z, Material.NETHER_WART);
                set(x - 2, y + 1, z + 2, Material.SOUL_LANTERN);
            }
            case "fortress" -> {
                blob(x, y, z, rad, depth, Material.NETHER_BRICKS, Material.NETHERRACK, Material.BLACKSTONE, seed, g.ores(), g.oreChance());
                for (int dx = -2; dx <= 2; dx++)
                    for (int dz = -2; dz <= 2; dz++) {
                        boolean edge = Math.abs(dx) == 2 || Math.abs(dz) == 2;
                        if (edge && (dx + dz) % 2 == 0) column(x + dx, y + 1, z + dz, 3, Material.NETHER_BRICK_FENCE);
                        set(x + dx, y + 4, z + dz, Material.NETHER_BRICKS);
                    }
                spawner(x, y + 1, z, EntityType.BLAZE);
                treasure(x + 1, y + 1, z + 1, r, Region.FLAME);
                text(x + 0.5, y + 6, z + 0.5, "<#ff8a3d>블레이즈 요새\n<gray>블레이즈 막대를 얻는 곳", 0.9f);
            }
            case "obsidian" -> {
                blob(x, y, z, rad, depth, Material.BLACKSTONE, Material.OBSIDIAN, Material.OBSIDIAN, seed, g.ores(), g.oreChance());
                spike(x, y + 1, z, 5 + r.nextInt(4), Material.OBSIDIAN, Material.CRYING_OBSIDIAN);
                set(x + 2, y + 1, z, Material.MAGMA_BLOCK);
            }
            // ---- 공허
            case "chorus" -> {
                blob(x, y, z, rad, depth, Material.END_STONE, Material.END_STONE, Material.OBSIDIAN, seed, g.ores(), g.oreChance());
                for (int i = 0; i < 3; i++) {
                    int dx = r.nextInt(7) - 3, dz = r.nextInt(7) - 3;
                    if (top(x + dx, z + dz, y) == y) tree(x + dx, y + 1, z + dz, TreeType.CHORUS_PLANT, Material.CHORUS_FLOWER);
                }
            }
            case "geode" -> {
                blob(x, y, z, rad, depth, Material.END_STONE, Material.CALCITE, Material.SMOOTH_BASALT, seed, null, 0);
                for (int dx = -3; dx <= 3; dx++)
                    for (int dy = -3; dy <= 3; dy++)
                        for (int dz = -3; dz <= 3; dz++) {
                            double d = Math.sqrt(dx * dx + dy * dy + dz * dz);
                            if (d > 3.3) continue;
                            int yy = y - 4 + dy;
                            if (d > 2.4) set(x + dx, yy, z + dz, r.nextInt(6) == 0 ? Material.BUDDING_AMETHYST : Material.AMETHYST_BLOCK);
                            else set(x + dx, yy, z + dz, Material.AIR);
                        }
                set(x, y - 7 + 1, z, Material.AMETHYST_CLUSTER);
                for (int i = 0; i < 4; i++) set(x + r.nextInt(5) - 2, y + 1, z + r.nextInt(5) - 2, Material.AMETHYST_CLUSTER);
                set(x, y, z, Material.AMETHYST_BLOCK);
            }
            case "obsidian_spire" -> {
                blob(x, y, z, rad, depth, Material.END_STONE, Material.OBSIDIAN, Material.OBSIDIAN, seed, g.ores(), g.oreChance());
                spike(x, y + 1, z, 10 + r.nextInt(6), Material.OBSIDIAN, Material.END_ROD);
                set(x + 2, y + 1, z - 1, Material.CRYING_OBSIDIAN);
            }
            case "purpur_ruin" -> {
                blob(x, y, z, rad, depth, Material.END_STONE_BRICKS, Material.END_STONE, Material.OBSIDIAN, seed, g.ores(), g.oreChance());
                for (int[] c : new int[][]{{2, 2}, {-2, 2}, {2, -2}, {-2, -2}}) {
                    column(x + c[0], y + 1, z + c[1], 1 + r.nextInt(4), Material.PURPUR_PILLAR);
                }
                set(x, y + 1, z + 3, Material.END_ROD);
                treasure(x, y + 1, z, r, Region.VOID);
            }
            case "end_rock" -> {
                blob(x, y, z, rad, depth, Material.END_STONE, Material.END_STONE, Material.END_STONE, seed, g.ores(), g.oreChance());
                set(x, y + 1, z, Material.CHORUS_FLOWER);
            }
            // ---- 바다
            case "reef" -> {
                blob(x, y, z, rad, depth, Material.SAND, Material.SAND, Material.PRISMARINE, seed, g.ores(), g.oreChance());
                double pr = Math.max(2, rad * 0.55);
                for (int dx = (int) -pr; dx <= pr; dx++)
                    for (int dz = (int) -pr; dz <= pr; dz++) {
                        if (dx * dx + dz * dz > pr * pr) continue;
                        set(x + dx, y, z + dz, Material.WATER);
                        set(x + dx, y - 1, z + dz, Material.WATER);
                        Material[] coral = {Material.TUBE_CORAL_BLOCK, Material.BRAIN_CORAL_BLOCK, Material.BUBBLE_CORAL_BLOCK,
                                Material.FIRE_CORAL_BLOCK, Material.HORN_CORAL_BLOCK, Material.SAND, Material.SAND};
                        set(x + dx, y - 2, z + dz, coral[r.nextInt(coral.length)]);
                    }
                set(x, y - 1, z, Material.KELP_PLANT);
                set(x, y, z, Material.KELP);
                set(x + 1, y - 1, z, Material.SEA_PICKLE);
            }
            case "prismarine_ruin" -> {
                blob(x, y, z, rad, depth, Material.PRISMARINE_BRICKS, Material.PRISMARINE, Material.DARK_PRISMARINE, seed, g.ores(), g.oreChance());
                for (int[] c : new int[][]{{3, 0}, {-3, 0}, {0, 3}, {0, -3}}) {
                    column(x + c[0], y + 1, z + c[1], 2 + r.nextInt(3), Material.PRISMARINE_BRICKS);
                }
                set(x, y, z, Material.SEA_LANTERN);
                set(x + 1, y, z + 1, Material.WET_SPONGE);
                treasure(x - 1, y + 1, z - 1, r, Region.OCEAN);
            }
            case "beach" -> {
                blob(x, y, z, rad, depth, Material.SAND, Material.SANDSTONE, Material.SANDSTONE, seed, g.ores(), g.oreChance());
                disc(x + 1, y, z + 1, Math.max(1.5, rad * 0.35), Material.WATER);
                for (int i = 0; i < 3; i++) column(x - 2, y + 1, z - 1 + i, 2 + i % 2, Material.SUGAR_CANE);
                set(x + 3, y + 1, z - 2, Material.TURTLE_EGG);
            }
            case "copper" -> {
                blob(x, y, z, rad, depth + 1, Material.SAND, Material.STONE, Material.STONE, seed,
                        new Material[]{Material.COPPER_ORE, Material.COPPER_ORE, Material.IRON_ORE}, 0.18);
                column(x, y + 1, z, 3, Material.CUT_COPPER);
                set(x, y + 4, z, Material.LIGHTNING_ROD);
            }
            case "clay_bank" -> {
                blob(x, y, z, rad, depth, Material.SAND, Material.CLAY, Material.CLAY, seed, g.ores(), g.oreChance());
                disc(x, y, z, Math.max(1.5, rad * 0.4), Material.WATER);
                set(x + (int) rad - 1, y + 1, z, Material.SUGAR_CANE);
            }
            // ---- 야생
            case "mountain" -> {
                blob(x, y, z, rad, depth + 3, Material.STONE, Material.ANDESITE, Material.STONE, seed, g.ores(), 0.1);
                spike(x, y + 1, z, 6 + r.nextInt(5), Material.STONE, Material.SNOW_BLOCK);
                spike(x + 3, y + 1, z + 2, 3 + r.nextInt(3), Material.GRANITE, null);
            }
            case "dark_forest" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                tree(x, y + 1, z, TreeType.DARK_OAK, Material.DARK_OAK_SAPLING);
                tree(x + 3, y + 1, z - 3, TreeType.TREE, Material.OAK_SAPLING);
                set(x - 3, y + 1, z + 2, Material.RED_MUSHROOM);
            }
            case "jungle" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                tree(x, y + 1, z, TreeType.COCOA_TREE, Material.JUNGLE_SAPLING);
                tree(x - 3, y + 1, z + 2, TreeType.JUNGLE_BUSH, null);
                column(x + 3, y + 1, z + 1, 4, Material.BAMBOO);
                set(x + 2, y + 1, z - 3, Material.MELON);
            }
            case "cherry" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                tree(x, y + 1, z, TreeType.CHERRY, Material.CHERRY_SAPLING);
                flowers(x, y, z, rad, r, Material.PINK_PETALS, Material.PINK_TULIP, Material.SHORT_GRASS);
            }
            case "savanna" -> {
                blob(x, y, z, rad, depth, Material.GRASS_BLOCK, Material.COARSE_DIRT, Material.STONE, seed, g.ores(), g.oreChance());
                tree(x, y + 1, z, TreeType.ACACIA, Material.ACACIA_SAPLING);
                animals(x + 2, y + 1, z + 2, org.bukkit.entity.Cow.class, 1);
                flowers(x, y, z, rad, r, Material.SHORT_GRASS, Material.SHORT_GRASS, Material.DANDELION);
            }
            default -> { // ruin
                blob(x, y, z, rad, depth, Material.MOSSY_STONE_BRICKS, Material.STONE_BRICKS, Material.STONE, seed, g.ores(), g.oreChance());
                for (int[] c : new int[][]{{2, 2}, {-2, 2}, {2, -2}, {-2, -2}}) {
                    column(x + c[0], y + 1, z + c[1], 1 + r.nextInt(3), r.nextBoolean() ? Material.CRACKED_STONE_BRICKS : Material.MOSSY_COBBLESTONE);
                }
                treasure(x, y + 1, z, r, Region.WILD);
            }
        }
        // 섬 열 개 중 하나 꼴로 작은 보물 상자
        if (!is.kind().equals("ruin") && !is.kind().equals("igloo") && !is.kind().equals("purpur_ruin")
                && !is.kind().equals("prismarine_ruin") && !is.kind().equals("fortress") && r.nextInt(8) == 0) {
            int dx = r.nextInt(5) - 2, dz = r.nextInt(5) - 2;
            int ty = top(x + dx, z + dz, y);
            if (ty != Integer.MIN_VALUE && air(x + dx, ty + 1, z + dz)) treasure(x + dx, ty + 1, z + dz, r, is.region());
        }
    }

    private void trees(int x, int y, int z, double rad, Random r, TreeType a, TreeType b, Material sapling) {
        int n = rad > 7 ? 3 : 2;
        for (int i = 0; i < n; i++) {
            double ang = r.nextDouble(Math.PI * 2), d = r.nextDouble(rad * 0.55);
            int tx = x + (int) Math.round(Math.cos(ang) * d), tz = z + (int) Math.round(Math.sin(ang) * d);
            if (top(tx, tz, y) != y) continue;
            tree(tx, y + 1, tz, i == 0 && rad > 7 ? b : a, sapling);
        }
    }

    private void flowers(int x, int y, int z, double rad, Random r, Material... kinds) {
        int n = (int) (rad * 2.2);
        for (int i = 0; i < n; i++) {
            int dx = (int) Math.round(r.nextGaussian() * rad * 0.45), dz = (int) Math.round(r.nextGaussian() * rad * 0.45);
            if (top(x + dx, z + dz, y) != y || !air(x + dx, y + 1, z + dz)) continue;
            Material t = w.getBlockAt(x + dx, y, z + dz).getType();
            if (t != Material.GRASS_BLOCK) continue;
            set(x + dx, y + 1, z + dz, kinds[r.nextInt(kinds.length)]);
        }
    }

    private void snowLayer(int x, int y, int z, double rad) {
        int R = (int) Math.ceil(rad * 1.3);
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                int ty = top(x + dx, z + dz, y);
                if (ty == Integer.MIN_VALUE || !air(x + dx, ty + 1, z + dz)) continue;
                Material t = w.getBlockAt(x + dx, ty, z + dz).getType();
                if (t == Material.SNOW_BLOCK || t == Material.PODZOL) set(x + dx, ty + 1, z + dz, Material.SNOW);
            }
    }

    // ------------------------------------------------------------------ 제단

    private void altarIsland(Isle is, Random r) {
        Ground g = ground(is.region());
        Material top = is.tier() == Tier.PRISM ? (is.region() == Region.VOID ? Material.END_STONE_BRICKS : Material.MOSS_BLOCK) : g.top();
        Material mid = is.region() == Region.PLAINS || is.region() == Region.WILD ? Material.DIRT : g.mid();
        Material bottom = is.tier() == Tier.PRISM ? Material.CALCITE : g.bottom();
        blob(is.x(), is.y(), is.z(), is.r(), (int) (is.r() * 1.1), top, mid, bottom, is.seed(), null, 0);
        altarStructure(w, is.x(), is.y(), is.z(), is.tier());
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
        // 클릭 판정을 먼저 세우고, 나머지 장식에 이 제단의 id 를 붙인다 (제단을 쓰면 장식이 바뀐다)
        Interaction hit = interaction(cx + 0.5, y + 2.0, cz + 0.5, 2.2f, 2.6f, Keys.ALTAR, tier.name());
        String of = hit.getUniqueId().toString();
        BlockDisplay cr = crystal(cx + 0.5, y + 3.0, cz + 0.5, core, 0.9f);
        BlockDisplay bm = beam(cx + 0.5, y + 5.2, cz + 0.5, glass, tier == Tier.PRISM ? "prism" : tier.name().toLowerCase());
        String label = tier.wrap("✦ " + tier.korean + " 제단 ✦") + "\n<gray>우클릭해서 증강 고르기\n<dark_gray>한 번 쓰면 힘을 잃습니다";
        TextDisplay tx = text(cx + 0.5, y + 5.0, cz + 0.5, label, 1.4f);
        for (Entity e : List.of(cr, bm, tx)) e.getPersistentDataContainer().set(Keys.ALTAR_OF, PersistentDataType.STRING, of);
        plugin.altars().register(hit.getUniqueId(), tier, hit.getLocation());
    }

    // ------------------------------------------------------------------ 균열과 둥지

    private record Theme(Material top, Material mid, Material bottom, Material deco, Material glow, Material floorA,
                         Material floorB, Material pillar, Material[] ores, String title, String boss, Material core) {}

    private static Theme theme(String id) {
        return switch (id) {
            case "frost" -> new Theme(Material.SNOW_BLOCK, Material.PACKED_ICE, Material.STONE, Material.BLUE_ICE,
                    Material.SEA_LANTERN, Material.PACKED_ICE, Material.POLISHED_DIORITE, Material.BLUE_ICE,
                    new Material[]{Material.IRON_ORE, Material.COAL_ORE, Material.LAPIS_ORE, Material.DIAMOND_ORE},
                    "<#9ad8ff>❄ 서리 균열 ❄", "frost_tyrant", Material.BLUE_ICE);
            case "flame" -> new Theme(Material.NETHERRACK, Material.MAGMA_BLOCK, Material.BLACKSTONE, Material.BASALT,
                    Material.SHROOMLIGHT, Material.POLISHED_BLACKSTONE_BRICKS, Material.GILDED_BLACKSTONE, Material.BASALT,
                    new Material[]{Material.NETHER_GOLD_ORE, Material.NETHER_QUARTZ_ORE, Material.GOLD_ORE, Material.REDSTONE_ORE},
                    "<#ff8a3d>🔥 화염 균열 🔥", "inferno_colossus", Material.MAGMA_BLOCK);
            default -> new Theme(Material.END_STONE, Material.END_STONE, Material.OBSIDIAN, Material.CRYING_OBSIDIAN,
                    Material.END_ROD, Material.PURPUR_BLOCK, Material.END_STONE_BRICKS, Material.OBSIDIAN,
                    new Material[]{Material.DIAMOND_ORE, Material.EMERALD_ORE, Material.GOLD_ORE, Material.IRON_ORE},
                    "<#c86bff>✧ 공허 균열 ✧", "void_sovereign", Material.CRYING_OBSIDIAN);
        };
    }

    /** 균열 섬: 둥지로 가는 길목. 균열의 몬스터가 계속 나오고 정수를 떨군다. */
    private void riftIsland(Isle is, Random r) {
        String id = is.kind().substring("rift_".length());
        Theme t = theme(id);
        int cx = is.x(), y = is.y(), cz = is.z();
        blob(cx, y, cz, is.r(), 11, t.top(), t.mid(), t.bottom(), is.seed(), t.ores(), 0.05);
        for (int i = 0; i < 7; i++) {
            double a = r.nextDouble() * Math.PI * 2, d = 5 + r.nextDouble() * 5;
            int x = cx + (int) Math.round(Math.cos(a) * d), z = cz + (int) Math.round(Math.sin(a) * d);
            int h = 2 + r.nextInt(4);
            column(x, y + 1, z, h, t.deco());
            if (r.nextBoolean()) set(x, y + 1 + h, z, t.glow());
        }
        riftMarker(w, new Location(w, cx + 0.5, y + 1, cz + 0.5), id);
        crystal(cx + 0.5, y + 4.5, cz + 0.5, t.core(), 1.4f);
        var bd = plugin.mobs().registry().get(t.boss());
        text(cx + 0.5, y + 7.5, cz + 0.5, t.title() + "\n<gray>균열의 몬스터가 쏟아져 나온다\n<dark_gray>이 너머에 "
                + (bd == null ? "보스" : Text.strip(bd.name())) + "의 둥지가 있다", 1.6f);
        Inventory inv = chest(cx - 6, y + 1, cz + 3, BlockFace.EAST);
        inv.addItem(plugin.items().create("shard", 4), new ItemStack(t.top(), 8), new ItemStack(Material.TORCH, 8));
    }

    /** 균열 표식만 세운다 (/증강관리 균열). */
    public void riftMarker(World world, Location at, String rift) {
        this.w = world;
        tag(w.spawn(at.clone(), Marker.class, m ->
                m.getPersistentDataContainer().set(Keys.RIFT, PersistentDataType.STRING, rift)));
        plugin.mobs().scanLoaded();
    }

    /** 둥지 표식만 세운다 (/증강관리 둥지). 보스는 누군가 다가오면 나타난다. */
    public void lairMarker(World world, Location at, String bossId) {
        plugin.mobs().lairs().create(at, bossId);
    }

    /** 보스 둥지: 넓고 평평한 결투장. 보스는 처음부터 여기를 지킨다. */
    private void lairIsland(Isle is, Random r) {
        String id = is.kind().substring("lair_".length());
        Theme t = theme(id);
        int cx = is.x(), y = is.y(), cz = is.z();
        double rad = is.r();
        blob(cx, y, cz, rad, 16, t.top(), t.mid(), t.bottom(), is.seed(), t.ores(), 0.03);
        // 결투장 바닥: 동심원 무늬, 위쪽은 비운다
        double arena = rad - 3.5;
        int A = (int) Math.ceil(arena);
        for (int x = -A; x <= A; x++)
            for (int z = -A; z <= A; z++) {
                double d = Math.sqrt(x * x + z * z);
                if (d > arena) continue;
                int ring = (int) Math.round(d);
                set(cx + x, y, cz + z, ring % 3 == 0 ? t.floorB() : t.floorA());
                for (int h = 1; h <= 14; h++) set(cx + x, y + h, cz + z, Material.AIR);
            }
        disc(cx, y, cz, 2.2, t.floorB());
        set(cx, y, cz, t.glow() == Material.END_ROD ? Material.CRYING_OBSIDIAN : t.glow());
        // 둘레의 큰 기둥 여덟 개 (입구 쪽 두 칸은 비운다)
        double toCenter = Math.atan2(-cz, -cx);
        for (int i = 0; i < 8; i++) {
            double a = i * Math.PI / 4 + Math.PI / 8;
            double diff = Math.abs(Math.atan2(Math.sin(a - toCenter), Math.cos(a - toCenter)));
            if (diff < 0.5) continue;
            int px = cx + (int) Math.round(Math.cos(a) * (arena + 0.5)), pz = cz + (int) Math.round(Math.sin(a) * (arena + 0.5));
            int h = 7 + r.nextInt(6);
            switch (id) {
                case "frost" -> spike(px, y + 1, pz, h + 3, Material.PACKED_ICE, Material.BLUE_ICE);
                case "flame" -> {
                    for (int dx = 0; dx <= 1; dx++) for (int dz = 0; dz <= 1; dz++) column(px + dx, y + 1, pz + dz, h, Material.BASALT);
                    set(px, y + 1 + h, pz, Material.NETHERRACK);
                    set(px, y + 2 + h, pz, Material.FIRE);
                    set(px + 1, y + 1 + h, pz + 1, Material.SHROOMLIGHT);
                }
                default -> {
                    spike(px, y + 1, pz, h + 2, Material.OBSIDIAN, Material.END_ROD);
                    set(px, y + 3, pz, Material.CRYING_OBSIDIAN);
                }
            }
        }
        // 입구 표지
        int ex = cx + (int) Math.round(Math.cos(toCenter) * (rad + 1)), ez = cz + (int) Math.round(Math.sin(toCenter) * (rad + 1));
        var bd = plugin.mobs().registry().get(t.boss());
        String bossName = bd == null ? "보스" : bd.name();
        text(cx + 0.5, y + 16, cz + 0.5, bossName + "<gray>의 둥지", 2.4f);
        text(ex + 0.5, y + 3, ez + 0.5, bossName + "\n<gray>이 둥지를 지키고 있다\n<dark_gray>쓰러뜨리면 프리즘 결정과 증강권", 1.0f);
        // 보스가 사는 곳 (보이지 않는 표식)
        lairMarker(w, new Location(w, cx + 0.5, y + 1, cz + 0.5), t.boss());
    }

    private void endIsland(int cx, int y, int cz) {
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

    private void signs(List<Isle> isles) {
        Place s = place("시작의 섬");
        text(s.x() + 0.5, s.y() + 8, s.z() + 0.5,
                "<gradient:#ff6b9d:#ffd36b:#6bffb0:#6bc8ff:#c86bff><b>증강 스카이블럭</b></gradient>\n<gray>하늘로 솟은 빛기둥이 제단입니다", 2.0f);
        // 가장 가까운 실버 제단
        Isle near = null;
        for (Isle is : isles) {
            if (is.tier() != Tier.SILVER) continue;
            if (near == null || Math.hypot(is.x(), is.z()) < Math.hypot(near.x(), near.z())) near = is;
        }
        List<String> lines = new ArrayList<>();
        lines.add("<#cfdbe6>■ <white>흰 빛기둥 <gray>실버 제단 16곳");
        lines.add("<#ffcf40>■ <white>노란 빛기둥 <gray>골드 제단 9곳");
        lines.add("<#c86bff>■ <white>무지개 빛기둥 <gray>프리즘 제단 5곳");
        if (near != null) lines.add("<gray>가장 가까운 실버 제단: " + dir(near.x() - s.x(), near.z() - s.z()) + " "
                + (int) Math.round(Math.hypot(near.x() - s.x(), near.z() - s.z())) + "m");
        lines.add("");
        for (String n : List.of("서리 지역", "화염 지역", "공허 지역", "바다 지역")) {
            Place p = place(n);
            lines.add("<white>" + n + " <gray>" + dir(p.x() - s.x(), p.z() - s.z()));
        }
        lines.add("<dark_gray>/증강 제단 으로 남은 제단 찾기");
        text(s.x() - 3.5, s.y() + 3.4, s.z() + 4.5, String.join("\n", lines), 0.85f);
    }

    public static String dir(int dx, int dz) {
        double a = Math.toDegrees(Math.atan2(dx, -dz));
        if (a < 0) a += 360;
        String[] names = {"북쪽", "북동쪽", "동쪽", "남동쪽", "남쪽", "남서쪽", "서쪽", "북서쪽"};
        return names[(int) Math.round(a / 45) % 8];
    }
}
