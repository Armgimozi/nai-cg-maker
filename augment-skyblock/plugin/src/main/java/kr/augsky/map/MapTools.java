package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Chest;
import org.bukkit.block.CreatureSpawner;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.inventory.Inventory;
import org.bukkit.persistence.PersistentDataType;

import java.util.Random;

/** 섬을 짓는 블록 도우미. MapBuilder(시작 섬, 제단, 균열, 둥지)와 IslandKinds(자원 섬)가 같이 쓴다. */
abstract class MapTools {
    final AugSky plugin;
    World w;

    MapTools(AugSky plugin) {
        this.plugin = plugin;
    }

    /** 섬 블록 하나를 고른다. dy 는 윗면에서 내려간 깊이, rim 은 윗면 가장자리 한 줄. */
    interface Pick {
        Material at(int dx, int dy, int dz, boolean rim, Random r);
    }

    static BlockData data(String state) {
        return Bukkit.createBlockData(state.indexOf(':') < 0 ? "minecraft:" + state : state);
    }

    void set(int x, int y, int z, Material m) {
        w.getBlockAt(x, y, z).setType(m, false);
    }

    void set(int x, int y, int z, BlockData d) {
        w.getBlockAt(x, y, z).setBlockData(d, false);
    }

    /** 블록 상태 글자로 놓는다. 예) "oak_leaves[persistent=true]" */
    void set(int x, int y, int z, String state) {
        set(x, y, z, data(state));
    }

    Material type(int x, int y, int z) {
        return w.getBlockAt(x, y, z).getType();
    }

    boolean air(int x, int y, int z) {
        return type(x, y, z).isAir();
    }

    boolean solid(int x, int y, int z) {
        return type(x, y, z).isSolid();
    }

    /** 섬 윗면의 높이 (없으면 Integer.MIN_VALUE). */
    int top(int x, int z, int fromY) {
        for (int y = fromY + 12; y > fromY - 20; y--) {
            Material m = type(x, y, z);
            if (!m.isAir() && m.isSolid()) return y;
        }
        return Integer.MIN_VALUE;
    }

    /** 위는 넓고 아래로 갈수록 좁아지는 떠 있는 섬. */
    void blob(int cx, int cy, int cz, double r, int depth, Material top, Material mid, Material bottom,
              long seed, Material[] ores, double oreChance) {
        blob(cx, cy, cz, r, depth, seed, (dx, dy, dz, rim, rnd) -> dy == 0 ? top : dy <= 2 ? mid : bottom, ores, oreChance);
    }

    void blob(int cx, int cy, int cz, double r, int depth, long seed, Pick pick, Material[] ores, double oreChance) {
        Random rnd = new Random(seed);
        // 블록 고르기는 따로 굴린다 (섞는 블록이 바뀌어도 섬 모양은 그대로)
        Random pr = new Random(seed * 31 + 7);
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
                    double dd = x * x + z * z;
                    if (dd > rr * rr) continue;
                    boolean rim = dy == 0 && dd > (rr - 1.2) * (rr - 1.2);
                    Material m = pick.at(x, dy, z, rim, pr);
                    if (dy > 2 && ores != null && rnd.nextDouble() < oreChance) m = ores[rnd.nextInt(ores.length)];
                    set(cx + x, cy - dy, cz + z, m);
                }
            }
        }
    }

    void disc(int cx, int y, int cz, double r, Material m) {
        int R = (int) Math.ceil(r);
        for (int x = -R; x <= R; x++)
            for (int z = -R; z <= R; z++)
                if (x * x + z * z <= r * r + 0.5) set(cx + x, y, cz + z, m);
    }

    void column(int x, int y, int z, int h, Material m) {
        for (int i = 0; i < h; i++) set(x, y + i, z, m);
    }

    /** 뾰족한 가시: 아래가 굵고 위로 갈수록 가늘다. */
    void spike(int x, int y, int z, int h, Material m, Material tip) {
        for (int i = 0; i < h; i++) {
            double rr = Math.max(0, 1.6 * (1 - (double) i / h));
            int R = (int) Math.ceil(rr);
            for (int dx = -R; dx <= R; dx++)
                for (int dz = -R; dz <= R; dz++)
                    if (dx * dx + dz * dz <= rr * rr + 0.3) set(x + dx, y + i, z + dz, m);
        }
        if (tip != null) set(x, y + h, z, tip);
    }

    Inventory chest(int x, int y, int z, BlockFace facing) {
        Block b = w.getBlockAt(x, y, z);
        b.setType(Material.CHEST, false);
        if (b.getBlockData() instanceof Directional d) {
            d.setFacing(facing);
            b.setBlockData(d, false);
        }
        Chest c = (Chest) b.getState();
        return c.getBlockInventory();
    }

    void spawner(int x, int y, int z, EntityType type) {
        Block b = w.getBlockAt(x, y, z);
        b.setType(Material.SPAWNER, false);
        if (b.getState() instanceof CreatureSpawner cs) {
            cs.setSpawnedType(type);
            cs.update(true, false);
        }
    }

    boolean tree(int x, int y, int z, TreeType type, Material fallback) {
        if (w.generateTree(new Location(w, x, y, z), type)) return true;
        // 공간이 모자라 실패하면 묘목이라도 심어 둔다
        if (fallback != null) set(x, y, z, fallback);
        return false;
    }

    <T extends Entity> T tag(T e) {
        e.getPersistentDataContainer().set(Keys.MAP_PART, PersistentDataType.BYTE, (byte) 1);
        e.setPersistent(true);
        return e;
    }
}
