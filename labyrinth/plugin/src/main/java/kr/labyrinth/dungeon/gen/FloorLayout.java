package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.List;

/**
 * 한 층의 타일 지도 (순수 데이터). 타일 (x, z) = 층 원점 기준 블록 좌표. 각 타일은 종류·영역(방 번호, 복도 -1)·내부 높이를 갖는다.
 * 벽은 저장하지 않는다 — "열린 타일과 맞닿은 빈 타일" 이 벽 기둥이 된다 (FloorBuilder).
 */
public final class FloorLayout {

    public static final byte VOID = 0;
    /** 걸을 수 있는 바닥. */
    public static final byte FLOOR = 1;
    /** 방 출입구 (잠그면 문 블록으로 막힘). region = 그 방. */
    public static final byte DOOR = 2;
    /** 액체 도랑 (난간 아래 물/용암). */
    public static final byte GUTTER = 3;

    /** 방 하나 (시작·전투·…·보스). doors = 출입구 타일 (packed x<<16|z). */
    public record RoomInfo(int index, RoomType type, int cell, int minX, int minZ, int maxX, int maxZ,
                           int centerX, int centerZ, int height, int[] doors) {
        public int width() { return maxX - minX + 1; }
        public int depth() { return maxZ - minZ + 1; }
    }

    /** 보스 투기장 (원형). corridorLength > 0 이면 중심에서 +z 쪽으로 추격 복도가 이어진다. */
    public record Arena(int centerX, int centerZ, int radius, int height, int corridorLength, int corridorWidth, int rimRadius) {
        public Arena(int centerX, int centerZ, int radius, int height, int corridorLength, int corridorWidth) {
            this(centerX, centerZ, radius, height, corridorLength, corridorWidth, 0);
        }

        /** 가장자리 단 중심 z (rimRadius 0 이면 의미 없음). */
        public int rimCenterZ() { return centerZ + FloorGenerator.rimCenterOffset(radius, corridorLength, rimRadius); }

        /** 가장자리 단(낭떠러지 포함) 바깥 반경. 0 = 없음. */
        public int rimOuter() { return rimRadius > 0 ? rimRadius + FloorGenerator.RIM_MOAT : 0; }

        /** 투기장 전체(원 + 추격 복도 + 가장자리 단)의 가장 남쪽 z. */
        public int maxZ() { return rimRadius > 0 ? rimCenterZ() + rimOuter() : centerZ + radius + corridorLength; }
    }

    private final int width;
    private final int depth;
    private final byte[] kind;
    private final short[] region;
    private final byte[] height;
    private final List<RoomInfo> rooms;
    private final int startRoom;
    private final int bossRoom;
    private final Arena arena;
    private final MazePlan plan;

    FloorLayout(int width, int depth, byte[] kind, short[] region, byte[] height, List<RoomInfo> rooms,
                int startRoom, int bossRoom, Arena arena, MazePlan plan) {
        this.width = width;
        this.depth = depth;
        this.kind = kind;
        this.region = region;
        this.height = height;
        this.rooms = List.copyOf(rooms);
        this.startRoom = startRoom;
        this.bossRoom = bossRoom;
        this.arena = arena;
        this.plan = plan;
    }

    public int width() { return width; }
    public int depth() { return depth; }
    public List<RoomInfo> rooms() { return rooms; }
    public RoomInfo room(int index) { return rooms.get(index); }
    public RoomInfo startRoom() { return rooms.get(startRoom); }
    public RoomInfo bossRoom() { return rooms.get(bossRoom); }
    public Arena arena() { return arena; }
    public MazePlan plan() { return plan; }

    public boolean inside(int x, int z) { return x >= 0 && z >= 0 && x < width && z < depth; }

    public byte kind(int x, int z) { return inside(x, z) ? kind[z * width + x] : VOID; }

    /** 방 번호 (복도·빈칸은 -1). */
    public int region(int x, int z) { return inside(x, z) ? region[z * width + x] : -1; }

    /** 바닥 위 빈 공간 높이 (열린 타일만 의미 있음). */
    public int height(int x, int z) { return inside(x, z) ? height[z * width + x] : 0; }

    public boolean open(int x, int z) {
        byte k = kind(x, z);
        return k == FLOOR || k == DOOR || k == GUTTER;
    }

    public boolean walkable(int x, int z) {
        byte k = kind(x, z);
        return k == FLOOR || k == DOOR;
    }

    /** 방 내부(출입구 제외)인가. */
    public boolean interior(int x, int z, int roomIndex) {
        return kind(x, z) == FLOOR && region(x, z) == roomIndex;
    }

    public static int pack(int x, int z) { return (x << 16) | (z & 0xFFFF); }
    public static int unpackX(int p) { return p >> 16; }
    public static int unpackZ(int p) { return (short) (p & 0xFFFF); }

    /** 시작방 중심에서 걸어서 닿는 타일 수 (출입구 포함). */
    public boolean[] reachable() {
        boolean[] seen = new boolean[width * depth];
        RoomInfo s = startRoom();
        ArrayDeque<int[]> q = new ArrayDeque<>();
        q.add(new int[] {s.centerX(), s.centerZ()});
        seen[s.centerZ() * width + s.centerX()] = true;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        while (!q.isEmpty()) {
            int[] t = q.poll();
            for (int[] d : dirs) {
                int nx = t[0] + d[0], nz = t[1] + d[1];
                if (!walkable(nx, nz)) continue;
                int i = nz * width + nx;
                if (seen[i]) continue;
                seen[i] = true;
                q.add(new int[] {nx, nz});
            }
        }
        return seen;
    }

    public boolean isReachable(boolean[] reach, int x, int z) {
        return inside(x, z) && reach[z * width + x];
    }
}
