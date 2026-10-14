package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.List;

/**
 * 한 층의 타일 지도 (순수 데이터). 타일 (x, z) = 층 원점 기준 블록 좌표. 각 타일은 종류·영역(방 번호, 복도 -1)·내부 높이·바닥 높이를 갖는다.
 * 벽은 저장하지 않는다 — "열린 타일과 맞닿은 빈 타일" 이 벽 기둥이 된다 (FloorBuilder).
 * <p>
 * <b>높이</b>: 바닥 블록 y = y0 + {@link #elevation}, 걸어 다니는 공간 = 그 위 {@link #height} 칸, 천장 = y0 + 높이 + 내부 높이 + 1.
 * 방·문·도랑은 언제나 높이 0. 복도의 계단 셀만 1~3 칸 올라간다 ({@link #STAIR} 타일: 바닥 블록 위에 계단 블록).
 * <p>
 * <b>다음 담당(함정·보물 상자·비밀 통로 내용물)이 쓰는 목록</b>: {@link #deadEnds()} 막다른 길 끝 칸, {@link #hallTiles()} 복도 칸,
 * {@link #secretRooms()} 비밀방, {@link #mainPathCells()} 주 경로 셀, {@link #rooms()} 방별 정보 (+ {@link #onMainPath}, {@link #distance}).
 */
public final class FloorLayout {

    public static final byte VOID = 0;
    /** 걸을 수 있는 바닥. */
    public static final byte FLOOR = 1;
    /** 방 출입구 (잠그면 문 블록으로 막힘). region = 그 방. */
    public static final byte DOOR = 2;
    /** 액체 도랑 (난간 아래 물/용암). */
    public static final byte GUTTER = 3;
    /** 계단 (바닥 블록 y0+높이, 그 위에 계단 블록 — {@link #stairFacing} 쪽으로 올라감). */
    public static final byte STAIR = 4;
    /** 금 간 벽 (비밀 통로). 바닥 위 내부 높이만큼 벽 블록 — 열면 공기가 되어 걸을 수 있다. */
    public static final byte SECRET = 5;

    /** 방 하나 (시작·전투·…·보스). doors = 출입구 타일 (packed x<<16|z). cell = 미로 셀 (보스방 -1). */
    public record RoomInfo(int index, RoomType type, int cell, int minX, int minZ, int maxX, int maxZ,
                           int centerX, int centerZ, int height, int[] doors) {
        public int width() { return maxX - minX + 1; }
        public int depth() { return maxZ - minZ + 1; }
    }

    /** 보스 투기장 (원형). corridorLength > 0 이면 중심에서 +z 쪽으로 추격 복도가 이어진다. */
    public record Arena(int centerX, int centerZ, int radius, int height, int corridorLength, int corridorWidth) {}

    /**
     * 막다른 길 끝 (출구 1개인 복도 셀). (tipX, tipZ) = 끝 칸 (걸을 수 있고 높이 0, 상자 하나 놓을 자리),
     * (dirX, dirZ) = 끝에서 복도 쪽(플레이어가 오는 쪽)으로의 단위 방향 — 상자는 이쪽을 바라보게.
     * secret ≥ 0 이면 이 끝이 {@link #secretRooms()} 의 그 비밀방으로 가는 금 간 벽 바로 앞.
     * minor = 미로 굴({@link HallStyle#WARREN}) 셀 안의 짧은 막다른 길 (미로 전체의 막다른 길은 false — 큰 보상 자리).
     */
    public record DeadEnd(int cell, int tipX, int tipZ, int dirX, int dirZ, int secret, boolean minor) {}

    /**
     * 비밀방 (금 간 벽 뒤의 숨은 작은 방, 복도 영역 -1). wall = 금 간 벽 타일 (packed), 안쪽 = minX..maxX × minZ..maxZ (모두 FLOOR, 높이 0),
     * (centerX, centerZ) = 가운데 (금 상자 자리), deadEnd = 금 간 벽 앞 막다른 길 번호.
     */
    public record SecretRoom(int index, int cell, int minX, int minZ, int maxX, int maxZ, int centerX, int centerZ,
                             int height, int[] wall, int deadEnd) {
        public boolean contains(int x, int z) { return x >= minX && x <= maxX && z >= minZ && z <= maxZ; }
    }

    private final int width;
    private final int depth;
    private final byte[] kind;
    private final short[] region;
    private final byte[] height;
    private final byte[] elev;
    private final byte[] facing;
    private final List<RoomInfo> rooms;
    private final int startRoom;
    private final int bossRoom;
    private final Arena arena;
    private final MazePlan plan;
    private final List<DeadEnd> deadEnds;
    private final List<SecretRoom> secretRooms;
    private final int[] hallTiles;
    private final int[] hallLights;
    private final int maxTop;

    FloorLayout(int width, int depth, byte[] kind, short[] region, byte[] height, byte[] elev, byte[] facing, List<RoomInfo> rooms,
                int startRoom, int bossRoom, Arena arena, MazePlan plan, List<DeadEnd> deadEnds, List<SecretRoom> secretRooms,
                int[] hallTiles, int[] hallLights) {
        this.width = width;
        this.depth = depth;
        this.kind = kind;
        this.region = region;
        this.height = height;
        this.elev = elev;
        this.facing = facing;
        this.rooms = List.copyOf(rooms);
        this.startRoom = startRoom;
        this.bossRoom = bossRoom;
        this.arena = arena;
        this.plan = plan;
        this.deadEnds = List.copyOf(deadEnds);
        this.secretRooms = List.copyOf(secretRooms);
        this.hallTiles = hallTiles;
        this.hallLights = hallLights;
        int top = 0;
        for (int i = 0; i < kind.length; i++) if (kind[i] != VOID) top = Math.max(top, elev[i] + height[i]);
        this.maxTop = top + 1;
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

    /** 바닥 블록 높이 (y0 기준, 0~3). 계단 복도만 0 이 아니다. */
    public int elevation(int x, int z) { return inside(x, z) ? elev[z * width + x] : 0; }

    /** 계단 타일이 올라가는 방향 (0=북 1=동 2=남 3=서), 계단이 아니면 -1. */
    public int stairFacing(int x, int z) { return kind(x, z) == STAIR ? facing[z * width + x] : -1; }

    /** 서 있을 때 발 높이 (y0 기준): 평지 = 높이+1, 계단 = 높이+1.5. 몹·함정 소환 위치용. */
    public double standHeight(int x, int z) { return elevation(x, z) + (kind(x, z) == STAIR ? 1.5 : 1.0); }

    /** 이 층에서 가장 높은 천장 (y0 기준). */
    public int maxTop() { return maxTop; }

    public boolean open(int x, int z) {
        byte k = kind(x, z);
        return k == FLOOR || k == DOOR || k == GUTTER || k == STAIR || k == SECRET;
    }

    public boolean walkable(int x, int z) {
        byte k = kind(x, z);
        return k == FLOOR || k == DOOR || k == STAIR;
    }

    /** 방 내부(출입구 제외)인가. */
    public boolean interior(int x, int z, int roomIndex) {
        return kind(x, z) == FLOOR && region(x, z) == roomIndex;
    }

    // ── 미로 셀 ↔ 타일 ────────────────────────────────────────────────────

    /** 타일이 속한 미로 셀 (격자 밖 — 여백·보스 복도·투기장 — 이면 -1). */
    public int cellAt(int x, int z) {
        int lx = x - FloorGenerator.MARGIN_X, lz = z - FloorGenerator.MARGIN_Z;
        if (lx < 0 || lz < 0) return -1;
        int cx = lx / FloorGenerator.PITCH, cz = lz / FloorGenerator.PITCH;
        int n = plan.size();
        if (cx >= n || cz >= n) return -1;
        return cz * n + cx;
    }

    /** 셀의 북서쪽 모서리 타일 x (셀은 PITCH×PITCH). */
    public int cellMinX(int cell) { return FloorGenerator.MARGIN_X + plan.x(cell) * FloorGenerator.PITCH; }

    public int cellMinZ(int cell) { return FloorGenerator.MARGIN_Z + plan.z(cell) * FloorGenerator.PITCH; }

    /** 보스 복도·투기장 쪽(격자 남쪽 바깥)인가. */
    public boolean beyondGrid(int z) { return z >= FloorGenerator.MARGIN_Z + plan.size() * FloorGenerator.PITCH; }

    /** 복도 셀 모양 (방·빈 셀은 null). */
    public HallStyle hallStyle(int cell) { return plan.style(cell); }

    /** 시작 → 보스 연결 셀 주 경로 (셀 번호, 양 끝 포함). */
    public List<Integer> mainPathCells() { return plan.mainPath(); }

    public boolean onMainPath(int cell) { return plan.onMainPath(cell); }

    /** 시작 셀에서 셀 몇 칸 떨어졌나 (깊이 — 보상 가중용). */
    public int distance(int cell) { return plan.distance(cell); }

    // ── 다음 담당용 목록 ──────────────────────────────────────────────────

    public List<DeadEnd> deadEnds() { return deadEnds; }

    public List<SecretRoom> secretRooms() { return secretRooms; }

    /** 금 간 벽 타일이면 그 비밀방 번호, 아니면 -1. */
    public int secretWallAt(int x, int z) {
        if (kind(x, z) != SECRET) return -1;
        int p = pack(x, z);
        for (SecretRoom s : secretRooms) for (int w : s.wall()) if (w == p) return s.index();
        return -1;
    }

    /** 비밀방 안쪽 타일이면 그 번호, 아니면 -1. */
    public int secretRoomAt(int x, int z) {
        for (SecretRoom s : secretRooms) if (s.contains(x, z)) return s.index();
        return -1;
    }

    /**
     * 복도 칸 (packed) — 함정 놓을 자리 후보. 미로 격자 안의 평평한 복도 바닥(FLOOR, 영역 -1)만: 계단·문·도랑·비밀방·
     * 문 2칸 이내·보스 복도는 뺐다. 높이 0 이 아닌 칸(계단 단상)도 있으니 {@link #elevation} 을 볼 것.
     */
    public int[] hallTiles() { return hallTiles.clone(); }

    /** 복도 조명 자리 (packed) — FloorBuilder 가 천장에 단다. */
    public int[] hallLights() { return hallLights.clone(); }

    public static int pack(int x, int z) { return (x << 16) | (z & 0xFFFF); }
    public static int unpackX(int p) { return p >> 16; }
    public static int unpackZ(int p) { return (short) (p & 0xFFFF); }

    // ── 걷기 판정 ─────────────────────────────────────────────────────────

    /**
     * 이웃 타일 a → b 로 걸어갈 수 있나 (높이 차 반영). 평지끼리 = 같은 높이, 평지↔계단 = 계단 높이 = 평지 높이 또는 평지 높이−1,
     * 계단끼리 = 높이 차 1 이하. openSecrets 면 금 간 벽도 지나갈 수 있다고 본다(열린 뒤).
     */
    public boolean canStep(int ax, int az, int bx, int bz, boolean openSecrets) {
        if (!passable(bx, bz, openSecrets) || !passable(ax, az, openSecrets)) return false;
        int ea = elevation(ax, az), eb = elevation(bx, bz);
        boolean sa = kind(ax, az) == STAIR, sb = kind(bx, bz) == STAIR;
        if (!sa && !sb) return ea == eb;
        if (sa && sb) return Math.abs(ea - eb) <= 1;
        int flat = sa ? eb : ea, stair = sa ? ea : eb;
        return stair == flat || stair == flat - 1;
    }

    private boolean passable(int x, int z, boolean openSecrets) {
        return walkable(x, z) || (openSecrets && kind(x, z) == SECRET);
    }

    /** 시작방 중심에서 걸어서 닿는 타일 (출입구 포함, 금 간 벽은 막힘). */
    public boolean[] reachable() { return reachable(false); }

    public boolean[] reachable(boolean openSecrets) {
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
                if (!inside(nx, nz) || !canStep(t[0], t[1], nx, nz, openSecrets)) continue;
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
