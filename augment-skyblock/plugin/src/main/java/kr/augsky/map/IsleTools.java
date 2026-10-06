package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.map.MapBuilder.Isle;
import org.bukkit.Chunk;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.Ageable;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.MultipleFacing;
import org.bukkit.block.data.Waterlogged;
import org.bukkit.block.data.type.Fence;
import org.bukkit.block.data.type.Gate;
import org.bukkit.block.data.type.GlassPane;
import org.bukkit.entity.LivingEntity;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;
import java.util.function.Consumer;

/**
 * 섬 하나를 짓는 동안의 상태(자리, 높이, 깊이, 난수)와 섬 짓기 도우미. 하늘 섬(IslandKinds)과 하늘 네더 섬(NetherKinds)이 같이 쓴다.
 * IslandKinds 에서 그대로 옮겨 왔다 (난수를 쓰는 순서가 같아야 같은 맵이 나온다).
 */
abstract class IsleTools extends MapTools {
    static final int[][] FOUR = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
    static final BlockFace[] SIDES = {BlockFace.EAST, BlockFace.WEST, BlockFace.SOUTH, BlockFace.NORTH};

    // 지금 짓는 섬
    Isle is;
    int x, y, z, d;
    double rad;
    Random r;
    /** 일부러 흘러내리게 둔 용암·물 (가장자리 메우기에서 건드리지 않는다) */
    final Set<Long> flows = new HashSet<>();

    IsleTools(AugSky plugin, World world) {
        super(plugin);
        this.w = world;
    }

    /** 섬 하나를 짓기 시작한다: 지금 짓는 섬의 자리, 높이 y, 밑동 깊이, 난수를 정해 둔다. */
    void begin(Isle is, Random r, int y, int depth) {
        this.is = is;
        this.x = is.x();
        this.y = y;
        this.z = is.z();
        this.rad = is.r();
        this.d = depth;
        this.r = r;
    }

    /** 윗면 칸: 섬 높이에 단단한 블록이 있고 바로 위가 비었다. */
    boolean tile(int px, int pz) {
        return solid(px, y, pz) && air(px, y + 1, pz);
    }

    /** 섬 윗면 칸 목록. inset 칸 둘레까지 모두 섬 윗면인 칸만 (가장자리에서 떨어뜨린다). */
    List<int[]> tiles(int inset) {
        List<int[]> out = new ArrayList<>();
        int R = (int) Math.ceil(rad * 1.3) + 1;
        for (int dx = -R; dx <= R; dx++) {
            for (int dz = -R; dz <= R; dz++) {
                int px = x + dx, pz = z + dz;
                if (!tile(px, pz)) continue;
                boolean ok = true;
                for (int a = -inset; a <= inset && ok; a++)
                    for (int b = -inset; b <= inset && ok; b++)
                        if (!solid(px + a, y, pz + b)) ok = false;
                if (ok) out.add(new int[]{px, pz});
            }
        }
        return out;
    }

    int[] take(List<int[]> l) {
        return l.isEmpty() ? null : l.remove(r.nextInt(l.size()));
    }

    /** 아직 비어 있는 윗면 칸 하나. */
    int[] takeFree(List<int[]> l) {
        while (!l.isEmpty()) {
            int[] p = take(l);
            if (tile(p[0], p[1])) return p;
        }
        return null;
    }

    double dist(int px, int pz) {
        return Math.hypot(px - x, pz - z);
    }

    /** 시작 섬 쪽 방향 (x 나 z 축 하나로 맞춘다). */
    int[] toSpawn() {
        if (Math.abs(x) >= Math.abs(z)) return new int[]{x > 0 ? -1 : 1, 0};
        return new int[]{0, z > 0 ? -1 : 1};
    }

    /** u 에 수직인 양의 축. */
    static int[] side(int[] u) {
        return u[0] != 0 ? new int[]{0, 1} : new int[]{1, 0};
    }

    /** 가운데에서 u 쪽으로 섬 윗면이 이어지는 마지막 칸까지의 거리. */
    int edge(int[] u) {
        int t = 0;
        while (t < 40 && solid(x + u[0] * (t + 1), y, z + u[1] * (t + 1))) t++;
        return t;
    }

    static String face(int[] u) {
        if (u[0] > 0) return "east";
        if (u[0] < 0) return "west";
        return u[1] > 0 ? "south" : "north";
    }

    static String low(Material m) {
        return m.name().toLowerCase(Locale.ROOT);
    }

    /** 덩어리 무늬용 0~1 값. cell 칸 크기 덩어리마다 같은 값이 나온다. */
    static double patch(int wx, int wz, long seed, int cell) {
        long h = seed * 0x9E3779B97F4A7C15L + Math.floorDiv(wx, cell) * 0xC2B2AE3D27D4EB4FL + Math.floorDiv(wz, cell) * 0x165667B19E3779F9L;
        h ^= h >>> 31;
        h *= 0xBF58476D1CE4E5B9L;
        h ^= h >>> 29;
        h *= 0x94D049BB133111EBL;
        h ^= h >>> 32;
        return (h >>> 11) * 0x1.0p-53;
    }

    /** 블록 자리 하나를 수 하나로 (집합에 넣으려고). */
    static long key(int x, int y, int z) {
        return ((long) x & 0x3FFFFFF) | (((long) z & 0x3FFFFFF) << 26) | (((long) y & 0xFFF) << 52);
    }

    /** 흐르게 둘 물·용암 (폭포). 물리를 켜고 놓는다. */
    void flow(int px, int py, int pz, Material m) {
        w.getBlockAt(px, py, pz).setType(m, true);
        flows.add(key(px, py, pz));
    }

    /** 가장자리의 섬 윗면 한 칸을 파서 폭포를 놓는다 (u 쪽 끝). */
    void fall(int[] u, Material fluid) {
        int t = edge(u);
        int px = x + u[0] * t, pz = z + u[1] * t;
        set(px, y + 1, pz, Material.AIR);
        flow(px, y, pz, fluid);
    }

    boolean grow(int px, int pz, TreeType t) {
        return w.generateTree(new Location(w, px, y + 1, pz), t);
    }

    /** 나무 한 그루: 빈 윗면 칸 몇 곳에 심어 보고, 다 안 되면 묘목. 심은 둘레는 목록에서 뺀다. */
    boolean grow(List<int[]> spots, TreeType t, Material sapling) {
        int[] last = null;
        for (int k = 0; k < 6; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            last = p;
            if (grow(p[0], p[1], t)) {
                spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 2 && Math.abs(q[1] - p[1]) <= 2);
                return true;
            }
        }
        if (last != null && sapling != null) set(last[0], y + 1, last[1], sapling);
        return false;
    }

    void ripe(int px, int py, int pz, Material crop) {
        BlockData b = crop.createBlockData();
        if (b instanceof Ageable ag) ag.setAge(ag.getMaximumAge());
        set(px, py, pz, b);
    }

    /** 두 칸짜리 꽃·풀. */
    void tall(int px, int pz, Material m) {
        set(px, y + 1, pz, low(m) + "[half=lower]");
        set(px, y + 2, pz, low(m) + "[half=upper]");
    }

    /** 덩굴: 단단한 면 옆 빈칸에 그 면 쪽으로 붙이고, 아래 칸은 같은 면으로 늘어뜨린다. */
    void vine(int vx, int vy, int vz, int[] toward, int len) {
        if (!solid(vx + toward[0], vy, vz + toward[1])) return;
        for (int i = 0; i < len && air(vx, vy - i, vz); i++) set(vx, vy - i, vz, "vine[" + face(toward) + "=true]");
    }

    /** 위 블록에 매달린 줄기 (늘어진 덩굴, 동굴 덩굴, 점적석). 끝 칸은 tip. */
    void hang(int hx, int hy, int hz, int len, String plant, String tip) {
        if (!solid(hx, hy + 1, hz)) return;
        int n = 0;
        while (n < len && air(hx, hy - n, hz)) n++;
        for (int i = 0; i < n; i++) set(hx, hy - i, hz, i == n - 1 ? tip : plant);
    }

    /** 섬 밑면: 이 기둥에서 가장 아래 단단한 블록의 높이. */
    int bottom(int px, int pz) {
        for (int yy = y - d - 6; yy <= y; yy++) if (solid(px, yy, pz)) return yy;
        return Integer.MIN_VALUE;
    }

    /** 가장자리 아래로 늘어뜨릴 자리: 윗면 바로 밑이 빈 칸 (가장자리 처마). */
    List<int[]> eaves() {
        List<int[]> out = new ArrayList<>();
        int R = (int) Math.ceil(rad * 1.3) + 1;
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++)
                if (solid(x + dx, y, z + dz) && air(x + dx, y - 1, z + dz)) out.add(new int[]{x + dx, z + dz});
        return out;
    }

    <T extends LivingEntity> T mob(double px, double py, double pz, Class<T> cls, Consumer<T> setup) {
        return w.spawn(new Location(w, px, py, pz), cls, e -> {
            e.setPersistent(true);
            e.setRemoveWhenFarAway(false);
            if (setup != null) setup.accept(e);
        });
    }

    void boulder(List<int[]> spots, Material m) {
        for (int k = 0; k < 8; k++) {
            int[] p = takeFree(spots);
            if (p == null) return;
            if (!tile(p[0] + 1, p[1]) || !tile(p[0], p[1] + 1) || !tile(p[0] + 1, p[1] + 1)) continue;
            for (int a = 0; a <= 1; a++) for (int b = 0; b <= 1; b++) column(p[0] + a, y + 1, p[1] + b, 2, m);
            return;
        }
    }

    /** table: ("재료*개수", 가중치) 쌍. 굴린 것은 빈 칸에 넣고(서로 덮어쓰지 않게), always 는 굴린 뒤에 꼭 넣는다. */
    void loot(Inventory inv, int rolls, Object[] table, ItemStack... always) {
        int total = 0;
        for (int i = 1; i < table.length; i += 2) total += (Integer) table[i];
        for (int k = 0; k < rolls; k++) {
            int pick = r.nextInt(total);
            for (int i = 0; i < table.length; i += 2) {
                pick -= (Integer) table[i + 1];
                if (pick >= 0) continue;
                String[] parts = ((String) table[i]).split("\\*");
                ItemStack it = plugin.items().spec(parts[0], parts.length > 1 ? Integer.parseInt(parts[1]) : 1);
                if (it != null) put(inv, it);
                break;
            }
        }
        for (ItemStack it : always) inv.addItem(it);
    }

    void put(Inventory inv, ItemStack it) {
        for (int k = 0; k < 20; k++) {
            int slot = r.nextInt(inv.getSize());
            if (inv.getItem(slot) == null) {
                inv.setItem(slot, it);
                return;
            }
        }
        inv.addItem(it);
    }

    // ------------------------------------------------------------------ 마무리: 생물군계, 떨어지는 블록, 새는 물

    /** 섬 둘레 땅·하늘에 생물군계 b 를 칠한다 (cy 는 섬 높이). 청크를 불러와 칠하고, 접속한 사람에게 다시 보낸다. */
    void paintBiome(Isle is, Biome b, int cy) {
        if (b == null) return;
        int cx = is.x(), cz = is.z(), y0 = cy - 28, y1 = cy + 36;
        int R = (int) Math.ceil(is.r() * 1.3) + 6;
        List<Chunk> chunks = new ArrayList<>();
        for (int qx = (cx - R) >> 4; qx <= (cx + R) >> 4; qx++)
            for (int qz = (cz - R) >> 4; qz <= (cz + R) >> 4; qz++) {
                chunks.add(w.getChunkAt(qx, qz));
                w.addPluginChunkTicket(qx, qz, plugin);
            }
        int cells = 0, changed = 0, missed = 0;
        for (int bx = Math.floorDiv(cx - R, 4) * 4; bx <= cx + R; bx += 4)
            for (int bz = Math.floorDiv(cz - R, 4) * 4; bz <= cz + R; bz += 4) {
                if ((bx + 2 - cx) * (bx + 2 - cx) + (bz + 2 - cz) * (bz + 2 - cz) > R * R) continue;
                for (int by = Math.floorDiv(y0, 4) * 4; by <= y1; by += 4) {
                    cells++;
                    if (b.equals(w.getBiome(bx, by, bz))) continue;
                    w.setBiome(bx, by, bz, b);
                    if (b.equals(w.getBiome(bx, by, bz))) changed++;
                    else missed++;
                }
            }
        if (missed > 0) plugin.getLogger().warning("생물군계 칠하기: " + is.kind() + " (" + cx + ", " + cz + ") " + missed + "/" + cells + "칸이 칠해지지 않았습니다");
        for (Chunk c : chunks) {
            if (changed > 0) w.refreshChunk(c.getX(), c.getZ());
            w.removePluginChunkTicket(c.getX(), c.getZ(), plugin);
        }
    }

    static boolean gravity(Material m) {
        return m == Material.SAND || m == Material.SUSPICIOUS_SAND || m == Material.RED_SAND || m == Material.GRAVEL
                || m == Material.SUSPICIOUS_GRAVEL || m.name().endsWith("_CONCRETE_POWDER");
    }

    static boolean wet(BlockData b) {
        Material m = b.getMaterial();
        if (m == Material.WATER || m == Material.LAVA || m == Material.KELP || m == Material.KELP_PLANT
                || m == Material.SEAGRASS || m == Material.TALL_SEAGRASS) return true;
        return b instanceof Waterlogged wl && wl.isWaterlogged();
    }

    /**
     * 짓고 난 섬 정리. 아래가 빈 모래·자갈은 굳은 블록으로 바꾸고(밟으면 무너져 공허로 떨어지므로),
     * 울타리를 이어 붙이고, 옆이나 아래가 빈 물·용암은 둘레를 막는다 (일부러 흘린 폭포는 빼고).
     */
    void settleGravity(Isle is, int cy, int depth) {
        int cx = is.x(), cz = is.z();
        int R = (int) Math.ceil(is.r() * 1.3) + 3, lo = cy - (depth + 6), hi = cy + 24;
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++)
                for (int yy = lo; yy <= hi; yy++) {
                    Block b = w.getBlockAt(cx + dx, yy, cz + dz);
                    Material m = b.getType();
                    if (m.isAir()) continue;
                    if (gravity(m)) {
                        Block below = b.getRelative(BlockFace.DOWN);
                        if (below.getType().isAir() || below.isLiquid() || below.isReplaceable()) {
                            b.setType(m == Material.SAND || m == Material.SUSPICIOUS_SAND ? Material.SANDSTONE
                                    : m == Material.RED_SAND ? Material.RED_SANDSTONE : Material.STONE, false);
                        }
                        continue;
                    }
                    BlockData bd = b.getBlockData();
                    if (bd instanceof Fence || bd instanceof GlassPane) connect(b, (MultipleFacing) bd);
                    if (!wet(bd) || flows.contains(key(b.getX(), yy, b.getZ()))) continue;
                    for (BlockFace f : new BlockFace[]{BlockFace.DOWN, BlockFace.EAST, BlockFace.WEST, BlockFace.SOUTH, BlockFace.NORTH}) {
                        Block n = b.getRelative(f);
                        if (n.getType().isAir()) n.setType(seal(b), false);
                    }
                }
    }

    /** 울타리·창살을 옆 울타리, 문, 꽉 찬 블록과 잇는다 (물리 없이 놓으면 기둥만 남아 동물이 틈으로 빠져나간다). */
    static void connect(Block b, MultipleFacing mf) {
        boolean changed = false;
        for (BlockFace f : SIDES) {
            Block n = b.getRelative(f);
            BlockData nd = n.getBlockData();
            // 울타리 문은 문이 가로지르는 방향으로만 잇는다
            boolean link = nd instanceof Fence || nd instanceof GlassPane || n.getType().isOccluding()
                    || nd instanceof Gate g && (g.getFacing().getModX() != 0) != (f.getModX() != 0);
            if (mf.hasFace(f) != link) {
                mf.setFace(f, link);
                changed = true;
            }
        }
        if (changed) b.setBlockData(mf, false);
    }

    /** 새는 물을 막을 블록: 바로 아래 블록(굳은 것), 없으면 돌 (네더에서는 흑암). */
    static Material seal(Block water) {
        Material below = water.getRelative(BlockFace.DOWN).getType();
        if (below.isSolid() && !gravity(below) && below.isBlock() && below != Material.SPAWNER) return below;
        return water.getWorld().getEnvironment() == World.Environment.NETHER ? Material.BLACKSTONE : Material.STONE;
    }
}
