package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.map.MapBuilder.Isle;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Chest;
import org.bukkit.block.CreatureSpawner;
import org.bukkit.block.spawner.SpawnRule;
import org.bukkit.block.spawner.SpawnerEntry;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntitySnapshot;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Piglin;
import org.bukkit.entity.PiglinBrute;
import org.bukkit.entity.Strider;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.loot.LootTables;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

import static org.bukkit.Material.*;

/**
 * 하늘 네더의 섬 12종과 징검다리. 하늘에서는 못 구하거나 아주 조금만 나는 네더 재료(고대 잔해, 위더 해골, 금 블록,
 * 우는 흑요석, 석영, 발광석, 네더 사마귀 …)가 섬마다 난다. 이름표 없이 블록과 생물군계(안개 색)만 보고 알아본다.
 */
final class NetherKinds extends IsleTools {
    /** 섬과 함께 놓는 주민(피글린, 스트라이더). 다시 지을 때 이 표시로 지운다 (MAP_PART 는 적으로 치지 않아서 쓰지 않는다) */
    static final String RESIDENT = "augsky_nether_resident";
    private static final BlockFace[] SIX = {BlockFace.UP, BlockFace.DOWN, BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST};

    NetherKinds(AugSky plugin, World world) {
        super(plugin, world);
    }

    void build(Isle is, Random r) {
        begin(is, r, is.y(), NetherMap.depth(is));
        switch (is.kind()) {
            case "n_hub" -> hub();
            case "n_quartz" -> quartz();
            case "n_glow" -> glow();
            case "n_crimson" -> crimson();
            case "n_warped" -> warped();
            case "n_soul" -> soul();
            case "n_delta" -> delta();
            case "n_fortress" -> fortress();
            case "n_bastion" -> bastion();
            case "n_ruin_portal" -> ruinPortal();
            case "n_lava" -> lava();
            case "n_debris" -> debris();
            case "n_stone" -> stone();
            default -> throw new IllegalArgumentException("알 수 없는 네더 섬 종류: " + is.kind());
        }
        settleGravity(is, y, d);
    }

    /**
     * 다시 지을 때 섬 자리(밑동과 매달린 것부터 윗면 위 24칸까지)를 통째로 비운다: 예전 상자·버섯나무·덩굴과 플레이어가 지은 것.
     * 남겨 두면 밑에 매달린 발광석이나 덩굴 자리가 달라져 처음 지은 모습과 어긋난다.
     */
    void clear(Isle is) {
        int R = (int) Math.ceil(is.r() * 1.3) + 2, lo = is.y() - NetherMap.checkDepth(is) - 8;
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                if (dx * dx + dz * dz > R * R) continue;
                for (int yy = lo; yy <= is.y() + 24; yy++) {
                    Block b = w.getBlockAt(is.x() + dx, yy, is.z() + dz);
                    if (!b.getType().isAir()) b.setType(AIR, false);
                }
            }
    }

    /** 다시 지을 때 예전 주민을 지운다 (엔티티가 다 불려 온 뒤에 부른다). */
    void clearResidents(Isle is) {
        Location c = new Location(w, is.x() + 0.5, is.y(), is.z() + 0.5);
        double R = is.r() * 1.3 + 16;
        for (Entity e : w.getNearbyEntities(c, R, 64, R)) if (e.getScoreboardTags().contains(RESIDENT)) e.remove();
    }

    // ------------------------------------------------------------------ 도우미

    private <T extends LivingEntity> T resident(double px, double py, double pz, Class<T> cls) {
        return mob(px, py, pz, cls, e -> e.addScoreboardTag(RESIDENT));
    }

    /** 섬 가운데 + u·a + v·b 칸. */
    private int ax(int[] u, int[] v, int a, int b) {
        return x + u[0] * a + v[0] * b;
    }

    private int az(int[] u, int[] v, int a, int b) {
        return z + u[1] * a + v[1] * b;
    }

    private void setAt(int[] u, int[] v, int a, int b, int py, Material m) {
        set(ax(u, v, a, b), py, az(u, v, a, b), m);
    }

    private void setAt(int[] u, int[] v, int a, int b, int py, String state) {
        set(ax(u, v, a, b), py, az(u, v, a, b), state);
    }

    private static BlockFace facing(int[] u) {
        if (u[0] > 0) return BlockFace.EAST;
        if (u[0] < 0) return BlockFace.WEST;
        return u[1] > 0 ? BlockFace.SOUTH : BlockFace.NORTH;
    }

    /** 바닐라 전리품 표를 단 상자. 처음 여는 사람이 굴린다 (짓는 때에 미리 굴리지 않는다). */
    private void lootChest(int px, int py, int pz, BlockFace f, LootTables table) {
        chest(px, py, pz, f);
        if (w.getBlockAt(px, py, pz).getState() instanceof Chest c) {
            c.setLootTable(table.getLootTable(), r.nextLong());
            c.update(true, false);
        }
    }

    /**
     * 빛과 상관없이 몹을 내는 생성기. 위더 해골은 원래 어두워야(밝기 7 이하) 나오는데,
     * 방에 횃불 하나만 달아도 아무 말 없이 멈춰 버려서 하나뿐인 위더 해골 머리 나는 곳이 막힌다.
     */
    private void freeSpawner(int px, int py, int pz, EntityType type) {
        Block b = w.getBlockAt(px, py, pz);
        b.setType(SPAWNER, false);
        if (!(b.getState() instanceof CreatureSpawner cs)) return;
        // id 만 넣어야 바닐라 생성기처럼 장비(돌 검)를 쥐여 준다
        EntitySnapshot snap = Bukkit.getEntityFactory().createEntitySnapshot("{id:\"" + type.getKey() + "\"}");
        SpawnerEntry entry = new SpawnerEntry(snap, 1, new SpawnRule(0, 15, 0, 15));
        cs.setSpawnedEntity(entry);
        cs.setPotentialSpawns(List.of(entry));
        cs.update(true, false);
    }

    /**
     * 버섯나무 한 그루 (IsleTools.grow 와 같고 난수만 다르다). 월드의 난수 대신 섬 시드와 자리로 키워서
     * 다시 지어도 같은 모양이 난다. 섬의 난수 r 은 건드리지 않는다.
     */
    private void fungus(List<int[]> spots, TreeType t, Material sapling) {
        int[] last = null;
        for (int k = 0; k < 6; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            last = p;
            Random tr = new Random(is.seed() * 31 + p[0] * 7919L + p[1]);
            if (w.generateTree(new Location(w, p[0], y + 1, p[1]), tr, t)) {
                spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 2 && Math.abs(q[1] - p[1]) <= 2);
                return;
            }
        }
        if (last != null) set(last[0], y + 1, last[1], sapling);
    }

    /** 사방(위아래 포함)이 단단한 블록으로 막힌 자리 (용암 옆이나 겉면은 안 된다). */
    private boolean enclosed(int px, int py, int pz) {
        Material self = type(px, py, pz);
        if (!self.isSolid() || self == ANCIENT_DEBRIS) return false;
        for (BlockFace f : SIX) {
            if (!type(px + f.getModX(), py + f.getModY(), pz + f.getModZ()).isSolid()) return false;
        }
        return true;
    }

    /** 섬 속(윗면에서 dy0~dy1 아래)에 사방이 막힌 블록 n 개를 1~maxCluster 개 덩어리로 숨긴다. 놓은 수를 돌려준다. */
    private int hide(Material m, int n, int dy0, int dy1, int maxCluster) {
        int placed = 0;
        for (int tries = 0; tries < 3000 && placed < n; tries++) {
            int dy = dy0 + r.nextInt(dy1 - dy0 + 1);
            double f = 1 - Math.pow((double) dy / (d + 1), 1.4);
            double rr = Math.max(1, rad * f * 0.6);
            int px = x + (int) Math.round((r.nextDouble() * 2 - 1) * rr), pz = z + (int) Math.round((r.nextDouble() * 2 - 1) * rr);
            int py = y - dy, size = 1 + r.nextInt(maxCluster);
            for (int k = 0; k < size && placed < n; k++) {
                int qx = px + (k == 1 ? 1 : 0), qy = py - (k == 2 ? 1 : 0);
                if (!enclosed(qx, qy, pz)) continue;
                set(qx, qy, pz, m);
                placed++;
            }
        }
        return placed;
    }

    /** 옆이나 아래가 빈 블록 (섬 겉면). */
    private boolean exposed(int px, int py, int pz) {
        for (int[] f : FOUR) if (air(px + f[0], py, pz + f[1])) return true;
        return air(px, py - 1, pz);
    }

    /** 윗면 칸에 용암 한 칸, 둘레 네 칸은 마그마. */
    private int pools(List<int[]> spots, int n) {
        int made = 0;
        for (int k = 0; k < 40 && made < n; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], LAVA);
            for (int[] f : FOUR) set(p[0] + f[0], y, p[1] + f[1], MAGMA_BLOCK);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 1 && Math.abs(q[1] - p[1]) <= 1);
            made++;
        }
        return made;
    }

    private void fires(List<int[]> spots, int n, Material on, Material fire) {
        for (int k = 0; k < 60 && n > 0; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (type(p[0], y, p[1]) != on) continue;
            set(p[0], y + 1, p[1], fire);
            n--;
        }
    }

    // ------------------------------------------------------------------ 쉼터

    /** 쉼터: 하늘에서 오는 네더 문이 열리는 곳. 흑암 벽돌 마당, 켜진 문, 영혼 등 기둥, 리스폰 정박기, 부싯돌 상자. */
    private void hub() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) {
                double dd = Math.sqrt(dx * dx + dz * dz);
                if (dd > 5.5) return BLACKSTONE;
                return Math.round(dd) == 3 ? CRACKED_POLISHED_BLACKSTONE_BRICKS : POLISHED_BLACKSTONE_BRICKS;
            }
            if (dy <= 2) return BLACKSTONE;
            return pr.nextDouble() < 0.7 ? NETHERRACK : BASALT;
        }, null, 0);
        for (int sx : new int[]{-5, 5})
            for (int sz : new int[]{-5, 5}) {
                int px = x + sx, pz = z + sz;
                if (air(px, y, pz)) set(px, y, pz, BLACKSTONE);
                column(px, y + 1, pz, 3, POLISHED_BLACKSTONE);
                set(px, y + 4, pz, CHISELED_POLISHED_BLACKSTONE);
                set(px, y + 5, pz, SOUL_LANTERN);
            }
        for (int sx : new int[]{-3, 3}) for (int sz : new int[]{-3, 3}) set(x + sx, y, z + sz, CRYING_OBSIDIAN);
        // 문틀 4×5 (x 축). 안쪽은 비워 두고 문 블록은 맨 마지막에 물리 없이 놓는다 (틀이 다 서기 전에 놓으면 꺼진다)
        for (int fx = -2; fx <= 1; fx++)
            for (int fy = 1; fy <= 5; fy++) set(x + fx, y + fy, z, fx == -2 || fx == 1 || fy == 1 || fy == 5 ? OBSIDIAN : AIR);
        set(x + 3, y + 1, z - 3, "respawn_anchor[charges=0]");
        Inventory inv = chest(x - 3, y + 1, z + 3, BlockFace.NORTH);
        inv.addItem(new ItemStack(FLINT_AND_STEEL), new ItemStack(BLACKSTONE, 32), new ItemStack(BREAD, 4));
        for (int fx = -1; fx <= 0; fx++) for (int fy = 2; fy <= 4; fy++) set(x + fx, y + fy, z, "nether_portal[axis=x]");
    }

    // ------------------------------------------------------------------ 기본 섬

    /** 석영 절벽: 하얀 석영이 점점이 박힌 네더랙 절벽과 가시. 네더 금도 섞여 있다. */
    private void quartz() {
        Material[] ores = new Material[13];
        for (int i = 0; i < ores.length; i++) ores[i] = i < 10 ? NETHER_QUARTZ_ORE : NETHER_GOLD_ORE;
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) ->
                dy <= 2 || pr.nextBoolean() ? NETHERRACK : BLACKSTONE, ores, 0.22);
        // 절벽 겉면의 1/4 은 석영 (멀리서도 흰 점이 보이게)
        int R = (int) Math.ceil(rad * 1.3) + 1;
        for (int dy = 1; dy <= d; dy++)
            for (int dx = -R; dx <= R; dx++)
                for (int dz = -R; dz <= R; dz++) {
                    int px = x + dx, py = y - dy, pz = z + dz;
                    Material m = type(px, py, pz);
                    if ((m == NETHERRACK || m == BLACKSTONE) && exposed(px, py, pz) && r.nextDouble() < 0.25) set(px, py, pz, NETHER_QUARTZ_ORE);
                }
        List<int[]> spots = tiles(1);
        int n = 6 + r.nextInt(3);
        for (int i = 0; i < n; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], NETHER_QUARTZ_ORE);
        }
        List<int[]> big = tiles(2);
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(big);
            if (p == null) break;
            int h = 4 + r.nextInt(4);
            spike(p[0], y + 1, p[1], h, NETHERRACK, null);
            for (int k = 1; k <= h; k++)
                for (int dx = -2; dx <= 2; dx++)
                    for (int dz = -2; dz <= 2; dz++)
                        if (type(p[0] + dx, y + k, p[1] + dz) == NETHERRACK && r.nextDouble() < 0.4) set(p[0] + dx, y + k, p[1] + dz, NETHER_QUARTZ_ORE);
            big.removeIf(q -> Math.abs(q[0] - p[0]) <= 3 && Math.abs(q[1] - p[1]) <= 3);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 2 && Math.abs(q[1] - p[1]) <= 2);
        }
        fires(spots, 2, NETHERRACK, FIRE);
    }

    /** 발광석 처마: 네더랙 섬 밑에 발광석이 주렁주렁 매달려 아래에서 빛난다. */
    private void glow() {
        blob(x, y, z, rad, d, NETHERRACK, NETHERRACK, NETHERRACK, is.seed(), null, 0);
        List<int[]> under = new ArrayList<>();
        int R = (int) Math.ceil(rad * 1.3) + 1;
        for (int dx = -R; dx <= R; dx++)
            for (int dz = -R; dz <= R; dz++) {
                int by = bottom(x + dx, z + dz);
                if (by != Integer.MIN_VALUE) under.add(new int[]{x + dx, by, z + dz});
            }
        int left = 64;
        while (left > 0 && !under.isEmpty()) {
            int[] c = under.remove(r.nextInt(under.size()));
            int gx = c[0], gy = c[1] - 1, gz = c[2];
            if (!air(gx, gy, gz)) continue;
            int len = 2 + r.nextInt(5);
            for (int k = 0; k < len && left > 0; k++, gy--) {
                if (air(gx, gy, gz)) {
                    set(gx, gy, gz, GLOWSTONE);
                    left--;
                }
                // 한 칸 옆으로 비틀며 내려간다
                if (r.nextDouble() < 0.35 && left > 0) {
                    int[] f = FOUR[r.nextInt(4)];
                    gx += f[0];
                    gz += f[1];
                    if (air(gx, gy, gz)) {
                        set(gx, gy, gz, GLOWSTONE);
                        left--;
                    }
                }
            }
        }
        List<int[]> spots = tiles(1);
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], GLOWSTONE);
        }
    }

    /** 진홍 숲: 진홍 버섯나무 셋, 네더 사마귀 블록, 버섯불, 늘어진 덩굴. 피글린이 사는 생물군계. */
    private void crimson() {
        blob(x, y, z, rad, d, CRIMSON_NYLIUM, NETHERRACK, NETHERRACK, is.seed(), new Material[]{NETHER_WART_BLOCK}, 0.08);
        List<int[]> spots = tiles(2);
        for (int i = 0; i < 3; i++) fungus(spots, TreeType.CRIMSON_FUNGUS, CRIMSON_FUNGUS);
        List<int[]> ground = tiles(1);
        for (int i = 0; i < 10; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            set(p[0], y + 1, p[1], i < 6 ? CRIMSON_ROOTS : CRIMSON_FUNGUS);
        }
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            set(p[0], y, p[1], SHROOMLIGHT);
        }
        List<int[]> eaves = eaves();
        int strands = 4 + r.nextInt(3);
        for (int i = 0; i < strands; i++) {
            int[] e = take(eaves);
            if (e == null) break;
            hang(e[0], y - 1, e[1], 3 + r.nextInt(4), "weeping_vines_plant", "weeping_vines");
        }
    }

    /** 뒤틀린 숲: 뒤틀린 버섯나무 셋, 뿌리, 싹, 꼬인 덩굴, 버섯불. 엔더맨이 나오는 생물군계. */
    private void warped() {
        blob(x, y, z, rad, d, WARPED_NYLIUM, NETHERRACK, NETHERRACK, is.seed(), new Material[]{WARPED_WART_BLOCK}, 0.06);
        List<int[]> spots = tiles(2);
        for (int i = 0; i < 3; i++) fungus(spots, TreeType.WARPED_FUNGUS, WARPED_FUNGUS);
        List<int[]> ground = tiles(1);
        for (int i = 0; i < 15; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            if (i < 6) set(p[0], y + 1, p[1], WARPED_ROOTS);
            else if (i < 12) set(p[0], y + 1, p[1], NETHER_SPROUTS);
            else {
                int h = 2 + r.nextInt(3);
                for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], k == h ? "twisting_vines" : "twisting_vines_plant");
            }
        }
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(ground);
            if (p == null) break;
            set(p[0], y, p[1], SHROOMLIGHT);
        }
    }

    /** 영혼 골짜기: 큰 갈비뼈 아치, 영혼 모래 밭의 네더 사마귀, 영혼 불, 현무암 기둥. */
    private void soul() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return pr.nextDouble() < 0.6 ? SOUL_SOIL : SOUL_SAND;
            if (dy <= 2) return SOUL_SAND;
            return pr.nextBoolean() ? BLACKSTONE : BASALT;
        }, null, 0);
        boolean alongX = r.nextBoolean();
        String cross = "bone_block[axis=" + (alongX ? "z" : "x") + "]";
        int arches = 4 + r.nextInt(2), tallH = 0, lx = x, lz = z;
        for (int i = 0; i < arches; i++) {
            int a = (i - (arches - 1) / 2) * 2;
            int h = 5 + r.nextInt(3);
            for (int sgn : new int[]{-1, 1}) {
                int bx = alongX ? x + a : x + 2 * sgn, bz = alongX ? z + 2 * sgn : z + a;
                for (int k = 1; k <= h; k++) set(bx, y + k, bz, "bone_block[axis=y]");
                set(alongX ? x + a : x + sgn, y + h + 1, alongX ? z + sgn : z + a, cross);
            }
            int tx = alongX ? x + a : x, tz = alongX ? z : z + a;
            set(tx, y + h + 2, tz, cross);
            if (h > tallH) {
                tallH = h;
                lx = tx;
                lz = tz;
            }
        }
        // 가장 높은 아치 밑에 사슬로 매단 영혼 등
        set(lx, y + tallH + 1, lz, CHAIN);
        set(lx, y + tallH, lz, "soul_lantern[hanging=true]");
        // 네더 사마귀 밭 둘 (4×2, 영혼 모래)
        List<int[]> spots = tiles(1);
        spots.removeIf(p -> alongX ? Math.abs(p[1] - z) <= 2 && Math.abs(p[0] - x) <= 5 : Math.abs(p[0] - x) <= 2 && Math.abs(p[1] - z) <= 5);
        int[] ages = {3, 3, 2, 1};
        int plots = 0;
        for (int k = 0; k < 120 && plots < 2; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            boolean ok = true;
            for (int i = 0; i < 4 && ok; i++) for (int j = 0; j < 2 && ok; j++) if (!tile(p[0] + i, p[1] + j)) ok = false;
            if (!ok) continue;
            int n = 0;
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 2; j++) {
                    set(p[0] + i, y, p[1] + j, SOUL_SAND);
                    set(p[0] + i, y + 1, p[1] + j, "nether_wart[age=" + ages[n++ % ages.length] + "]");
                }
            spots.removeIf(q -> q[0] >= p[0] - 1 && q[0] <= p[0] + 4 && q[1] >= p[1] - 1 && q[1] <= p[1] + 2);
            plots++;
        }
        fires(spots, 3, SOUL_SOIL, SOUL_FIRE);
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int h = 3 + r.nextInt(4);
            for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], "basalt[axis=y]");
        }
    }

    /** 삼각주: 현무암과 흑암, 마그마로 둘러싼 용암 웅덩이, 현무암 기둥과 가시. 속 깊이 고대 잔해 셋. */
    private void delta() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return pr.nextDouble() < 0.55 ? BASALT : BLACKSTONE;
            if (dy <= 2) return BLACKSTONE;
            return pr.nextBoolean() ? BASALT : BLACKSTONE;
        }, new Material[]{MAGMA_BLOCK}, 0.10);
        List<int[]> spots = tiles(2);
        pools(spots, 4 + r.nextInt(2));
        int cols = 6 + r.nextInt(4);
        for (int i = 0; i < cols; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int h = 2 + r.nextInt(6);
            for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], "basalt[axis=y]");
        }
        for (int i = 0; i < 2; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            spike(p[0], y + 1, p[1], 4 + r.nextInt(3), BASALT, null);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 2 && Math.abs(q[1] - p[1]) <= 2);
        }
        hide(ANCIENT_DEBRIS, 3, 5, d - 2, 1);
    }

    // ------------------------------------------------------------------ 다음 단계

    /**
     * 네더 요새 한 토막: 네더 벽돌 마당, 어두운 방의 위더 해골 생성기, 높은 단의 블레이즈 생성기(17칸 떨어뜨려
     * 한쪽만 깨어나게), 영혼 모래의 네더 사마귀, 끊어진 다리 둘, 바닐라 요새 상자 둘.
     */
    private void fortress() {
        blob(x, y, z, rad, d, NETHERRACK, NETHERRACK, BLACKSTONE, is.seed(), new Material[]{NETHER_QUARTZ_ORE}, 0.04);
        int[] u = toSpawn(), v = side(u);
        // 마당 (공중에 걸쳐도 깐다). 생성기 둘레 4칸 안에 나온 몹이 설 수 있게 방 뒤까지 넓힌다
        for (int a = -13; a <= 10; a++)
            for (int b = -6; b <= 6; b++) {
                setAt(u, v, a, b, y, NETHER_BRICKS);
                for (int k = 1; k <= 7; k++) setAt(u, v, a, b, y + k, AIR);
            }
        // 방: 벽 a -11~-5, b -4~4, 안 높이 4. 마당 쪽 문, 양옆 울타리 창
        for (int a = -11; a <= -5; a++)
            for (int b = -4; b <= 4; b++) {
                boolean wall = a == -11 || a == -5 || Math.abs(b) == 4;
                for (int k = 1; k <= 4; k++) setAt(u, v, a, b, y + k, wall ? NETHER_BRICKS : AIR);
                setAt(u, v, a, b, y + 5, NETHER_BRICKS);
            }
        setAt(u, v, -5, 0, y + 1, AIR);
        setAt(u, v, -5, 0, y + 2, AIR);
        for (int b : new int[]{-4, 4}) setAt(u, v, -8, b, y + 3, NETHER_BRICK_FENCE);
        freeSpawner(ax(u, v, -8, 0), y + 1, az(u, v, -8, 0), EntityType.WITHER_SKELETON);
        lootChest(ax(u, v, -10, 3), y + 1, az(u, v, -10, 3), facing(u), LootTables.NETHER_BRIDGE);
        // 블레이즈 단: a 5~10, b -4~4, 윗면 y+3. 네 귀퉁이와 가운데 기둥, 울타리 난간, 옆 계단
        for (int a = 5; a <= 10; a++)
            for (int b = -4; b <= 4; b++) {
                setAt(u, v, a, b, y + 3, NETHER_BRICKS);
                boolean edge = a == 5 || a == 10 || Math.abs(b) == 4;
                if (edge) setAt(u, v, a, b, y + 4, NETHER_BRICK_FENCE);
                if ((a == 5 || a == 10 || a == 7) && Math.abs(b) == 4) {
                    setAt(u, v, a, b, y + 1, NETHER_BRICKS);
                    setAt(u, v, a, b, y + 2, NETHER_BRICKS);
                }
            }
        String stair = "nether_brick_stairs[facing=" + face(u) + "]";
        for (int k = 0; k < 3; k++) {
            for (int f = 1; f <= k; f++) setAt(u, v, 5 + k, 5, y + f, NETHER_BRICKS);
            setAt(u, v, 5 + k, 5, y + 1 + k, stair);
        }
        setAt(u, v, 7, 4, y + 4, AIR);
        freeSpawner(ax(u, v, 9, 0), y + 4, az(u, v, 9, 0), EntityType.BLAZE);
        lootChest(ax(u, v, 4, 5), y + 1, az(u, v, 4, 5), facing(new int[]{-v[0], -v[1]}), LootTables.NETHER_BRIDGE);
        // 네더 사마귀 밭 3×3
        for (int a = 1; a <= 3; a++)
            for (int b = -5; b <= -3; b++) {
                setAt(u, v, a, b, y, SOUL_SAND);
                setAt(u, v, a, b, y + 1, "nether_wart[age=3]");
            }
        // 끊어진 다리 둘 (±v 쪽). 4칸마다 아래로 늘어진 받침
        for (int sgn : new int[]{-1, 1}) {
            int len = 10 + r.nextInt(5);
            for (int t = 7; t < 7 + len; t++) {
                boolean ragged = t >= 7 + len - 3;
                int b = sgn * t;
                for (int a = -1; a <= 1; a++) {
                    if (ragged && r.nextDouble() < 0.4) continue;
                    setAt(u, v, a, b, y, NETHER_BRICKS);
                    if (a != 0 && !(ragged && r.nextBoolean())) setAt(u, v, a, b, y + 1, NETHER_BRICK_FENCE);
                }
                if ((t - 7) % 4 == 2) {
                    int h = 6 + r.nextInt(5), bx = ax(u, v, 0, b), bz = az(u, v, 0, b);
                    for (int k = 1; k <= h && air(bx, y - k, bz); k++) set(bx, y - k, bz, NETHER_BRICKS);
                }
            }
        }
        // 마당 네 귀퉁이 기둥
        for (int a : new int[]{-13, 10})
            for (int b : new int[]{-6, 6}) {
                int bx = ax(u, v, a, b), bz = az(u, v, a, b);
                for (int k = 1; k <= 12; k++) if (air(bx, y - k, bz)) set(bx, y - k, bz, NETHER_BRICKS);
            }
    }

    private Material brick() {
        double p = r.nextDouble();
        return p < 0.60 ? POLISHED_BLACKSTONE_BRICKS : p < 0.85 ? CRACKED_POLISHED_BLACKSTONE_BRICKS : p < 0.93 ? GILDED_BLACKSTONE : BLACKSTONE;
    }

    /**
     * 보루 잔해: 무너진 흑암 벽돌 담, 현무암 망루, 금 블록 단 위의 보물 상자(바닐라 보루 보물 표: 네더라이트 강화 견본),
     * 담 안쪽 상자 둘, 피글린 다섯과 피글린 야수 하나. 쉼터 쪽으로 문이 나 있다.
     */
    private void bastion() {
        Material[] ores = {GILDED_BLACKSTONE, GILDED_BLACKSTONE, GILDED_BLACKSTONE, GILDED_BLACKSTONE, GILDED_BLACKSTONE,
                NETHER_GOLD_ORE, NETHER_GOLD_ORE, NETHER_GOLD_ORE, NETHER_GOLD_ORE};
        long ps = is.seed();
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return patch(x + dx, z + dz, ps, 3) < 0.3 ? POLISHED_BLACKSTONE : BLACKSTONE;
            return dy <= 2 ? BLACKSTONE : BASALT;
        }, ores, 0.09);
        int[] u = toSpawn(), v = side(u);
        for (int a = -6; a <= 6; a++)
            for (int b = -6; b <= 6; b++) {
                setAt(u, v, a, b, y, POLISHED_BLACKSTONE_BRICKS);
                for (int k = 1; k <= 12; k++) setAt(u, v, a, b, y + k, AIR);
            }
        // 담: |a| = 7 또는 |b| = 7. 높이 6~9, 1/4 은 1~3 칸만 남았다. 귀퉁이는 망루, a = 7 쪽 가운데 세 칸은 문
        int[][] hts = new int[15][15];
        List<int[]> walls = new ArrayList<>();
        for (int a = -7; a <= 7; a++)
            for (int b = -7; b <= 7; b++) {
                if (Math.abs(a) != 7 && Math.abs(b) != 7) continue;
                boolean corner = Math.abs(a) == 7 && Math.abs(b) == 7, gate = a == 7 && Math.abs(b) <= 1;
                int h = corner ? 10 + r.nextInt(3) : 6 + (int) (patch(ax(u, v, a, b), az(u, v, a, b), ps + 1, 2) * 4);
                if (!corner && !gate && r.nextDouble() < 0.25) h = 1 + r.nextInt(3);
                setAt(u, v, a, b, y, POLISHED_BLACKSTONE_BRICKS);
                for (int k = 1; k <= h; k++) {
                    if (gate && k <= 3) setAt(u, v, a, b, y + k, AIR);
                    else setAt(u, v, a, b, y + k, corner ? POLISHED_BASALT : brick());
                }
                for (int k = h + 1; k <= 12; k++) setAt(u, v, a, b, y + k, AIR);
                hts[a + 7][b + 7] = h;
                if (!corner && !gate) walls.add(new int[]{a, b, h});
            }
        // 담에 박힌 금 블록 셋
        for (int k = 0, n = 0; k < 60 && n < 3; k++) {
            int[] wv = walls.get(r.nextInt(walls.size()));
            if (wv[2] < 4) continue;
            setAt(u, v, wv[0], wv[1], y + 2 + r.nextInt(3), GOLD_BLOCK);
            n++;
        }
        // 담 꼭대기에서 안쪽으로 늘어진 사슬 넷
        for (int k = 0, n = 0; k < 80 && n < 4; k++) {
            int[] wv = walls.get(r.nextInt(walls.size()));
            if (wv[2] < 6 || Math.abs(wv[0]) == 7 && Math.abs(wv[1]) >= 5 || Math.abs(wv[1]) == 7 && Math.abs(wv[0]) >= 5) continue;
            int ia = wv[0] - Integer.signum(wv[0]) * (Math.abs(wv[0]) == 7 ? 1 : 0), ib = wv[1] - Integer.signum(wv[1]) * (Math.abs(wv[1]) == 7 ? 1 : 0);
            if (!air(ax(u, v, ia, ib), y + wv[2], az(u, v, ia, ib))) continue;
            setAt(u, v, ia, ib, y + wv[2], POLISHED_BLACKSTONE_BRICKS);
            int len = 2 + r.nextInt(2);
            for (int c = 1; c <= len; c++) setAt(u, v, ia, ib, y + wv[2] - c, CHAIN);
            n++;
        }
        // 가운데 단: 흑암 테두리, 금 블록 3×3, 그 위 귀퉁이 금박 흑암과 가운데 보물 상자
        for (int a = -2; a <= 2; a++)
            for (int b = -2; b <= 2; b++) setAt(u, v, a, b, y + 1, Math.abs(a) <= 1 && Math.abs(b) <= 1 ? GOLD_BLOCK : POLISHED_BLACKSTONE);
        for (int a : new int[]{-1, 1}) for (int b : new int[]{-1, 1}) setAt(u, v, a, b, y + 2, GILDED_BLACKSTONE);
        lootChest(x, y + 2, z, facing(u), LootTables.BASTION_TREASURE);
        int[][] magma = {{3, 0}, {-3, 0}, {0, 3}, {0, -3}, {2, 2}, {2, -2}, {-2, 2}, {-2, -2}};
        for (int[] m : magma) setAt(u, v, m[0], m[1], y, MAGMA_BLOCK);
        for (int a : new int[]{-5, 5}) lootChest(ax(u, v, a, -6), y + 1, az(u, v, a, -6), facing(v), LootTables.BASTION_OTHER);
        int[][] folk = {{4, 2}, {-4, 2}, {4, -2}, {-4, -2}, {2, 4}};
        for (int[] f : folk) resident(ax(u, v, f[0], f[1]) + 0.5, y + 1, az(u, v, f[0], f[1]) + 0.5, Piglin.class);
        resident(ax(u, v, -2, 4) + 0.5, y + 1, az(u, v, -2, 4) + 0.5, PiglinBrute.class);
    }

    /** 무너진 문: 우는 흑요석이 섞인 부서진 네더 문틀(빈 칸 셋), 흩어진 흑요석, 반쯤 묻힌 금 블록, 무너진 문 상자. */
    private void ruinPortal() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) return pr.nextDouble() < 0.7 ? NETHERRACK : BLACKSTONE;
            return dy <= 2 ? NETHERRACK : BLACKSTONE;
        }, null, 0);
        int[] al = r.nextBoolean() ? new int[]{1, 0} : new int[]{0, 1};
        List<int[]> frame = new ArrayList<>();
        for (int i = 0; i < 4; i++) for (int j = 0; j < 5; j++) if (i == 0 || i == 3 || j == 0 || j == 4) frame.add(new int[]{i, j});
        for (int k = 0; k < 3; k++) frame.remove(r.nextInt(frame.size()));
        List<int[]> crying = new ArrayList<>(frame);
        for (int k = 0; k < frame.size() - 6; k++) crying.remove(r.nextInt(crying.size()));
        for (int[] f : frame) {
            int px = x + al[0] * (f[0] - 1), pz = z + al[1] * (f[0] - 1);
            set(px, y + 1 + f[1], pz, crying.contains(f) ? CRYING_OBSIDIAN : OBSIDIAN);
        }
        List<int[]> spots = tiles(1);
        // 문틀 자리와 그 앞뒤 한 칸은 비워 둔다
        spots.removeIf(q -> Math.abs(q[0] - x) <= (al[0] == 1 ? 3 : 1) && Math.abs(q[1] - z) <= (al[1] == 1 ? 3 : 1));
        int rubble = 0;
        for (int k = 0; k < 80 && rubble < 9; k++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            if (dist(p[0], p[1]) > 5) continue;
            set(p[0], y + 1, p[1], rubble < 4 ? CRYING_OBSIDIAN : OBSIDIAN);
            rubble++;
        }
        for (int i = 0; i < 4; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            set(p[0], y, p[1], i < 2 ? CRYING_OBSIDIAN : GOLD_BLOCK);
            spots.removeIf(q -> Math.abs(q[0] - p[0]) <= 1 && Math.abs(q[1] - p[1]) <= 1);
        }
        pools(spots, 2);
        fires(spots, 2, NETHERRACK, FIRE);
        int[] p = takeFree(spots);
        if (p != null) lootChest(p[0], y + 1, p[1], facing(toSpawn()), LootTables.RUINED_PORTAL);
    }

    /** 용암 호수: 마그마 바닥의 두 칸 깊이 용암 호수와 스트라이더 둘. */
    private void lava() {
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) ->
                dy <= 2 ? NETHERRACK : pr.nextBoolean() ? BLACKSTONE : BASALT, null, 0);
        double lr = 5.5;
        for (int dx = -7; dx <= 7; dx++)
            for (int dz = -7; dz <= 7; dz++) {
                double dd = Math.sqrt(dx * dx + dz * dz);
                if (dd <= lr) {
                    set(x + dx, y, z + dz, LAVA);
                    set(x + dx, y - 1, z + dz, LAVA);
                    set(x + dx, y - 2, z + dz, MAGMA_BLOCK);
                } else if (dd <= lr + 1) set(x + dx, y, z + dz, MAGMA_BLOCK);
            }
        List<int[]> spots = tiles(1);
        spots.removeIf(q -> dist(q[0], q[1]) <= lr + 1.5);
        for (int i = 0; i < 3; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int h = 2 + r.nextInt(4);
            for (int k = 1; k <= h; k++) set(p[0], y + k, p[1], "basalt[axis=y]");
        }
        resident(x + 2.5, y + 1, z + 0.5, Strider.class);
        resident(x - 1.5, y + 1, z - 1.5, Strider.class);
    }

    // ------------------------------------------------------------------ 먼 섬

    /** 검은 바위: 흑암과 현무암의 큰 섬, 현무암 기둥 왕관, 마그마 금. 속 깊이 고대 잔해 24개 (보이는 광석은 없다). */
    private void debris() {
        long ps = is.seed();
        blob(x, y, z, rad, d, is.seed(), (dx, dy, dz, rim, pr) -> {
            if (dy == 0) {
                if (patch(x + dx, z + dz, ps, 3) < 0.15) return POLISHED_BLACKSTONE;
                return pr.nextDouble() < 0.7 ? BLACKSTONE : BASALT;
            }
            if (dy <= 2) return BLACKSTONE;
            double p = pr.nextDouble();
            return p < 0.5 ? BLACKSTONE : p < 0.9 ? BASALT : MAGMA_BLOCK;
        }, null, 0);
        int cols = 10 + r.nextInt(3);
        for (int i = 0; i < cols; i++) {
            double a = i * Math.PI * 2 / cols + r.nextDouble() * 0.3, dd = rad - 2;
            int px = x + (int) Math.round(Math.cos(a) * dd), pz = z + (int) Math.round(Math.sin(a) * dd);
            if (!tile(px, pz)) continue;
            int h = 3 + r.nextInt(6);
            for (int k = 1; k < h; k++) set(px, y + k, pz, "basalt[axis=y]");
            set(px, y + h, pz, "polished_basalt[axis=y]");
        }
        List<int[]> spots = tiles(1);
        for (int i = 0; i < 6; i++) {
            int[] p = takeFree(spots);
            if (p == null) break;
            int[] f = FOUR[r.nextInt(4)];
            int len = 3 + r.nextInt(3);
            for (int k = 0; k < len; k++) if (tile(p[0] + f[0] * k, p[1] + f[1] * k)) set(p[0] + f[0] * k, y, p[1] + f[1] * k, MAGMA_BLOCK);
        }
        hide(ANCIENT_DEBRIS, 24, 10, 18, 3);
    }

    /** 징검다리 바위. */
    private void stone() {
        blob(x, y, z, rad, 3, is.seed(), (dx, dy, dz, rim, pr) -> dy > 0 ? BLACKSTONE : NETHERRACK, null, 0);
        column(x, y + 1, z, 1 + r.nextInt(2), BASALT);
    }
}
