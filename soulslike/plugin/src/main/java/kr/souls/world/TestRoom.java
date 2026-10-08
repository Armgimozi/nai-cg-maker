package kr.souls.world;

import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.type.Campfire;
import org.bukkit.block.data.type.Lantern;
import org.bukkit.block.data.type.Slab;

/**
 * M0 시험 방. 코드로 짓는다 (지도 빌더가 생기기 전의 작은 판). 접속하면 여기 선다.
 * 25×25 바닥 (구르기 길이를 재는 3칸 길 포함), 그 북쪽의 반 블록 판석 길 (온 블록이 아닌 바닥에서 구르기의 방벽 높이를 보는 곳),
 * 낮은 벽, 벽 기둥 위 랜턴, 북서쪽 모서리의 6칸 높이 턱 (낙하 피해는 구르기로 피하지 못하는지 보는 곳, 사다리로 오른다),
 * 첫 자리 동쪽 6칸의 시험 방 화톳불 (켜진 캠프파이어, 판 3: bonfire/TestBonfire 가 우클릭을 받아 휴식 창, 4.1).
 * 같은 무늬를 늘어놓지 않게 블록은 위치 해시로 섞는다 (8.4). 빛은 랜턴과 화톳불만 쓴다.
 */
public final class TestRoom {
    /** 방 모양을 바꾸면 올린다. 시작할 때 세계에 적힌 판보다 크면 지우고 다시 짓는다 (3: 시험 방 화톳불). */
    public static final int VERSION = 3;
    /** 바닥 반지름 (가운데에서 벽 안쪽까지) */
    static final int HALF = 12;

    private TestRoom() {}

    /** 처음 서는 자리: 남쪽 벽 앞, 북쪽(-z)을 본다. */
    public static Location spawn(World w, int cx, int cy, int cz) {
        return new Location(w, cx + 0.5, cy + 1, cz + 10.5, 180f, 0f);
    }

    /** 턱 위 (낙하 시험 자리). 방 가운데(남동쪽)를 본다: 앞으로 걸으면 6칸 아래 바닥으로 떨어진다. */
    public static Location ledge(World w, int cx, int cy, int cz) {
        return new Location(w, cx - 9.5, cy + 7, cz - 9.5, -45f, 0f);
    }

    /** 구르기 길의 시작 칸 (동쪽 +x 로 구른다). */
    public static Location lane(World w, int cx, int cy, int cz) {
        return new Location(w, cx - 9.5, cy + 1, cz + 7.5, -90f, 0f);
    }

    /** 판석 길의 시작 칸 (바닥 위 아래 반 블록, 동쪽 +x 로 구른다). */
    public static Location slab(World w, int cx, int cy, int cz) {
        return new Location(w, cx - 9.5, cy + 1.5, cz + 3.5, -90f, 0f);
    }

    /** 시험 방 화톳불 블록 (첫 자리 동쪽 6칸, 구르기 길 z 6..8 과 판석 길 z 2..4 밖). */
    public static Location bonfire(World w, int cx, int cy, int cz) {
        return new Location(w, cx + 6, cy + 1, cz + 10);
    }

    /** 지운 뒤 짓는다. 돌려주는 값은 놓은 블록 수. */
    public static int build(World w, int cx, int cy, int cz) {
        Builder b = new Builder(w, cx, cy, cz);
        int r = HALF + 2;
        b.fill(-r, -2, -r, r, 9, r, Material.AIR);

        // 바닥 아래 받침과 바닥
        for (int x = -HALF - 1; x <= HALF + 1; x++) {
            for (int z = -HALF - 1; z <= HALF + 1; z++) {
                b.set(x, -1, z, b.pick(x, -1, z, Material.COBBLED_DEEPSLATE, 80, Material.DEEPSLATE, 20));
                b.set(x, 0, z, floor(b, x, z));
            }
        }

        // 구르기 길: z = 6..8, x = -10..10. 2칸마다 양쪽 가장자리에 눈금, 시작 칸은 조각 심층암
        for (int x = -10; x <= 10; x++) {
            for (int z = 6; z <= 8; z++) {
                Material m = Material.POLISHED_DEEPSLATE;
                if (z != 7 && (x + 10) % 2 == 0) m = Material.DEEPSLATE_BRICKS;
                if (x == -10 && z == 7) m = Material.CHISELED_DEEPSLATE;
                b.set(x, 0, z, m);
            }
        }

        // 판석 길: z = 2..4, x = -10..10, 바닥 위에 아래 반 블록 (발 높이의 소수 자리 0.5). 깨진 판석과 섞는다
        for (int x = -10; x <= 10; x++) {
            for (int z = 2; z <= 4; z++) {
                BlockData slab = b.pick(x, 1, z, Material.DEEPSLATE_TILE_SLAB, 65, Material.POLISHED_DEEPSLATE_SLAB, 35).createBlockData();
                ((Slab) slab).setType(Slab.Type.BOTTOM);
                b.set(x, 1, z, slab);
            }
        }

        // 벽: 높이 3, 군데군데 한 칸 더 높거나 이가 빠진다
        int w0 = HALF + 1;
        for (int i = -w0; i <= w0; i++) {
            wallColumn(b, i, -w0);
            wallColumn(b, i, w0);
            wallColumn(b, -w0, i);
            wallColumn(b, w0, i);
        }

        // 벽 안쪽 기둥 위 랜턴 (기둥 높이는 1~2칸으로 고르지 않게)
        int[] at = {-8, 0, 8};
        for (int p : at) {
            post(b, p, -HALF);
            post(b, p, HALF);
            post(b, -HALF, p);
            post(b, HALF, p);
        }

        // 북서쪽 턱: x -12..-7, z -12..-7, 6칸 높이. 동쪽 면에 사다리
        for (int x = -HALF; x <= -7; x++) {
            for (int z = -HALF; z <= -7; z++) {
                for (int y = 1; y <= 6; y++) {
                    boolean edge = x == -7 || z == -7;
                    Material m = edge ? b.pick(x, y, z, Material.DEEPSLATE_BRICKS, 70, Material.CRACKED_DEEPSLATE_BRICKS, 30)
                            : Material.COBBLED_DEEPSLATE;
                    if (y == 6) m = b.pick(x, y, z, Material.DEEPSLATE_TILES, 75, Material.CRACKED_DEEPSLATE_TILES, 25);
                    b.set(x, y, z, m);
                }
            }
        }
        for (int y = 1; y <= 6; y++) {
            BlockData ladder = Material.LADDER.createBlockData();
            ((Directional) ladder).setFacing(BlockFace.EAST);
            b.set(-6, y, -10, ladder);
        }
        lantern(b, -11, 7, -11);

        // 시험 방 화톳불: 켜진 캠프파이어 하나 (꽂힌 검·앉는 자리는 지도의 진짜 화톳불이 생기는 M2 에)
        BlockData fire = Material.CAMPFIRE.createBlockData();
        ((Campfire) fire).setLit(true);
        ((Campfire) fire).setSignalFire(false);
        ((Campfire) fire).setFacing(BlockFace.WEST);
        b.set(6, 1, 10, fire);
        return b.count;
    }

    private static Material floor(Builder b, int x, int z) {
        int h = b.hash(x, 0, z) % 100;
        if (h < 58) return Material.DEEPSLATE_TILES;
        if (h < 74) return Material.CRACKED_DEEPSLATE_TILES;
        if (h < 90) return Material.POLISHED_DEEPSLATE;
        return Material.COBBLED_DEEPSLATE;
    }

    private static void wallColumn(Builder b, int x, int z) {
        int h = b.hash(x, 7, z) % 100;
        int top = h < 12 ? 4 : h < 22 ? 2 : 3;
        for (int y = 1; y <= top; y++) {
            b.set(x, y, z, b.pick(x, y, z, Material.DEEPSLATE_BRICKS, 72, Material.CRACKED_DEEPSLATE_BRICKS, 28));
        }
    }

    private static void post(Builder b, int x, int z) {
        int h = b.hash(x, 3, z) % 2 == 0 ? 1 : 2;
        for (int y = 1; y <= h; y++) b.set(x, y, z, Material.DEEPSLATE_BRICK_WALL);
        lantern(b, x, h + 1, z);
    }

    private static void lantern(Builder b, int x, int y, int z) {
        BlockData l = Material.LANTERN.createBlockData();
        ((Lantern) l).setHanging(false);
        b.set(x, y, z, l);
    }

    /** 가운데 기준 좌표로 놓는 작은 도우미. 물리 갱신 없이 놓는다 (8.10). */
    static final class Builder {
        final World w;
        final int cx, cy, cz;
        int count;

        Builder(World w, int cx, int cy, int cz) {
            this.w = w;
            this.cx = cx;
            this.cy = cy;
            this.cz = cz;
        }

        void set(int x, int y, int z, Material m) {
            set(x, y, z, m.createBlockData());
        }

        void set(int x, int y, int z, BlockData bd) {
            w.getBlockAt(cx + x, cy + y, cz + z).setBlockData(bd, false);
            count++;
        }

        void fill(int x0, int y0, int z0, int x1, int y1, int z1, Material m) {
            BlockData bd = m.createBlockData();
            for (int x = x0; x <= x1; x++)
                for (int y = y0; y <= y1; y++)
                    for (int z = z0; z <= z1; z++)
                        w.getBlockAt(cx + x, cy + y, cz + z).setBlockData(bd, false);
        }

        /** 위치 해시 (0 이상). 지을 때마다 같은 모양이 나온다. */
        int hash(int x, int y, int z) {
            int h = x * 73856093 ^ y * 19349663 ^ z * 83492791 ^ 0x5f3759df;
            h ^= h >>> 13;
            h *= 0x5bd1e995;
            h ^= h >>> 15;
            return h & 0x7fffffff;
        }

        Material pick(int x, int y, int z, Material a, int wa, Material b, int wb) {
            return hash(x, y, z) % (wa + wb) < wa ? a : b;
        }
    }
}
