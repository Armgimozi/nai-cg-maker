package kr.labyrinth.dungeon.gen;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;

/**
 * 층 설계 (순수 로직 — 단위 테스트 대상): 시드 미로({@link MazeGenerator}) → 타일 지도({@link FloorLayout}).
 * <p>
 * 셀 하나 = {@value #PITCH}×{@value #PITCH} 타일. 방 셀은 내부 19×19(로컬 3~21), 벽은 로컬 2·22, 출입구는 벽 가운데 3칸(로컬 11~13).
 * 복도 셀은 {@link HallStyle} 모양대로 — 셀 경계의 출입구는 언제나 가운데 3칸(로컬 11~13)이라 어떤 모양끼리도 이어진다
 * (액체 층이면 곧은·꺾인 통로 양옆 도랑 1칸씩). 모양은 북쪽 기준으로 정의하고 셀 중심(12,12)으로 돌려 놓는다.
 * 보스 투기장은 마지막 줄의 보스 연결 셀에서 남쪽(+z)으로 복도 {@value #BOSS_CORRIDOR} 칸 뒤에 원형으로 붙는다.
 */
public final class FloorGenerator {

    public static final int PITCH = 24;
    public static final int ROOM_MIN = 3;
    public static final int ROOM_MAX = 21;
    public static final int LANE_MIN = 11;
    public static final int LANE_MAX = 13;
    public static final int BOSS_CORRIDOR = 10;
    /** 투기장이 격자 밖으로 나가도 되게 x 쪽 여백. */
    public static final int MARGIN_X = 26;
    public static final int MARGIN_Z = 2;
    /** 계단 복도 단상 최대 높이. */
    public static final int MAX_RISE = 3;

    /** 층 설계 입력 (floors.yml + bosses.yml arena 에서 뽑은 값). */
    public record Params(int cells, Map<String, Integer> rooms, int roomHeight, int hallHeight, boolean liquid,
                         int arenaRadius, int arenaHeight, int arenaCorridorLength, int arenaCorridorWidth,
                         MazeGenerator.Settings maze) {
        public Params {
            roomHeight = clamp(roomHeight, 4, 12);
            hallHeight = clamp(hallHeight, 3, roomHeight);
            arenaRadius = clamp(arenaRadius, 8, 22);
            arenaHeight = clamp(arenaHeight, 6, 20);
            arenaCorridorLength = clamp(arenaCorridorLength, 0, 120);
            arenaCorridorWidth = clamp(arenaCorridorWidth <= 0 ? 7 : arenaCorridorWidth, 3, 11);
            if (maze == null) maze = MazeGenerator.Settings.DEFAULT;
        }

        public Params(int cells, Map<String, Integer> rooms, int roomHeight, int hallHeight, boolean liquid,
                      int arenaRadius, int arenaHeight, int arenaCorridorLength, int arenaCorridorWidth) {
            this(cells, rooms, roomHeight, hallHeight, liquid, arenaRadius, arenaHeight, arenaCorridorLength, arenaCorridorWidth,
                    MazeGenerator.Settings.DEFAULT);
        }
    }

    private FloorGenerator() {}

    public static FloorLayout generate(Params p, long seed) {
        MazePlan plan = MazeGenerator.generate(p.cells(), seed, p.rooms(), p.maze());
        return layout(plan, p);
    }

    static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    public static FloorLayout layout(MazePlan plan, Params p) {
        int n = plan.size();
        int r = p.arenaRadius();
        int width = MARGIN_X * 2 + n * PITCH;
        int arenaCz = MARGIN_Z + n * PITCH + BOSS_CORRIDOR + r;
        int depth = arenaCz + r + 2 + (p.arenaCorridorLength() > 0 ? p.arenaCorridorLength() + 2 : 0) + 2;
        Grid g = new Grid(width, depth);

        List<FloorLayout.RoomInfo> rooms = new ArrayList<>();
        List<List<Integer>> doorLists = new ArrayList<>();
        int[] roomOfCell = new int[n * n];
        java.util.Arrays.fill(roomOfCell, -1);
        int startRoom = -1;
        Extras extras = new Extras();

        // 1. 셀 내부
        for (int c = 0; c < n * n; c++) {
            if (!plan.used(c)) continue;
            int bx = MARGIN_X + plan.x(c) * PITCH, bz = MARGIN_Z + plan.z(c) * PITCH;
            RoomType t = plan.type(c);
            if (t.isRoom()) {
                int idx = rooms.size();
                roomOfCell[c] = idx;
                if (t == RoomType.START) startRoom = idx;
                g.fill(bx + ROOM_MIN, bz + ROOM_MIN, bx + ROOM_MAX, bz + ROOM_MAX, FloorLayout.FLOOR, idx, p.roomHeight());
                rooms.add(new FloorLayout.RoomInfo(idx, t, c, bx + ROOM_MIN, bz + ROOM_MIN, bx + ROOM_MAX, bz + ROOM_MAX,
                        bx + 12, bz + 12, p.roomHeight(), null));
                doorLists.add(new ArrayList<>());
            } else {
                hall(g, p, plan, c, bx, bz, extras);
            }
        }

        // 2. 셀 사이 통로 (A 로컬 22..23 + B 로컬 0..2)
        for (int c = 0; c < n * n; c++) {
            if (!plan.used(c)) continue;
            int bx = MARGIN_X + plan.x(c) * PITCH, bz = MARGIN_Z + plan.z(c) * PITCH;
            if (plan.openEast(c)) {
                for (int lx = 22; lx <= PITCH + 2; lx++) {
                    for (int lz = LANE_MIN; lz <= LANE_MAX; lz++) passage(g, p, rooms, doorLists, roomOfCell, c, c + 1, lx, bx + lx, bz + lz);
                }
            }
            if (plan.openSouth(c)) {
                for (int lz = 22; lz <= PITCH + 2; lz++) {
                    for (int lx = LANE_MIN; lx <= LANE_MAX; lx++) passage(g, p, rooms, doorLists, roomOfCell, c, c + n, lz, bx + lx, bz + lz);
                }
            }
        }

        // 3. 보스 복도 + 원형 투기장 (+ 추격 복도)
        int attach = plan.bossAttach();
        int ax = MARGIN_X + plan.x(attach) * PITCH, az = MARGIN_Z + plan.z(attach) * PITCH;
        int bossIdx = rooms.size();
        List<Integer> bossDoors = new ArrayList<>();
        int corridorStart = az + PITCH;
        int corridorEnd = corridorStart + BOSS_CORRIDOR - 1;
        for (int z = corridorStart; z <= corridorEnd; z++) {
            for (int x = ax + LANE_MIN; x <= ax + LANE_MAX; x++) {
                if (z == corridorEnd) {
                    g.set(x, z, FloorLayout.DOOR, bossIdx, p.hallHeight());
                    bossDoors.add(FloorLayout.pack(x, z));
                } else {
                    g.set(x, z, FloorLayout.FLOOR, -1, p.hallHeight());
                }
            }
        }
        int cx = ax + 12, cz = corridorEnd + 1 + r;
        for (int z = cz - r; z <= cz + r; z++) {
            for (int x = cx - r; x <= cx + r; x++) {
                int dx = x - cx, dz = z - cz;
                if (dx * dx + dz * dz <= r * r + r) g.set(x, z, FloorLayout.FLOOR, bossIdx, p.arenaHeight());
            }
        }
        // 투기장 입구와 원 사이 틈 메우기 (원 꼭대기와 문 줄 사이)
        for (int z = corridorEnd + 1; z <= cz - r + 1; z++) {
            for (int x = ax + LANE_MIN; x <= ax + LANE_MAX; x++) {
                if (g.kind(x, z) == FloorLayout.VOID) g.set(x, z, FloorLayout.FLOOR, bossIdx, p.arenaHeight());
            }
        }
        if (p.arenaCorridorLength() > 0) {
            int half = p.arenaCorridorWidth() / 2;
            int ch = Math.min(p.arenaHeight(), 10);
            for (int z = cz + r - 1; z <= cz + r + p.arenaCorridorLength(); z++) {
                for (int x = cx - half; x <= cx + half; x++) {
                    if (g.kind(x, z) == FloorLayout.VOID) g.set(x, z, FloorLayout.FLOOR, bossIdx, ch);
                }
            }
        }
        int minZ = cz - r, maxZ = cz + r + (p.arenaCorridorLength() > 0 ? p.arenaCorridorLength() : 0);
        rooms.add(new FloorLayout.RoomInfo(bossIdx, RoomType.BOSS, -1, cx - r, minZ, cx + r, maxZ, cx, cz, p.arenaHeight(), null));
        doorLists.add(bossDoors);

        // 문 목록 확정
        List<FloorLayout.RoomInfo> finalRooms = new ArrayList<>(rooms.size());
        for (int i = 0; i < rooms.size(); i++) {
            FloorLayout.RoomInfo ri = rooms.get(i);
            int[] doors = doorLists.get(i).stream().mapToInt(Integer::intValue).toArray();
            finalRooms.add(new FloorLayout.RoomInfo(ri.index(), ri.type(), ri.cell(), ri.minX(), ri.minZ(), ri.maxX(), ri.maxZ(),
                    ri.centerX(), ri.centerZ(), ri.height(), doors));
        }
        FloorLayout.Arena arena = new FloorLayout.Arena(cx, cz, r, p.arenaHeight(), p.arenaCorridorLength(), p.arenaCorridorWidth());
        int[] hallTiles = hallTiles(g, n, extras.secrets);
        int[] lights = extras.lights.stream().mapToInt(Integer::intValue).toArray();
        return new FloorLayout(width, depth, g.kind, g.region, g.height, g.elev, g.facing, finalRooms, startRoom, bossIdx, arena, plan,
                extras.deadEnds, extras.secrets, hallTiles, lights);
    }

    // ── 복도 셀 ───────────────────────────────────────────────────────────

    /** 다음 담당용 목록 모음 (생성 중). */
    private static final class Extras {
        final List<FloorLayout.DeadEnd> deadEnds = new ArrayList<>();
        final List<FloorLayout.SecretRoom> secrets = new ArrayList<>();
        final List<Integer> lights = new ArrayList<>();
    }

    private static void hall(Grid g, Params p, MazePlan plan, int c, int bx, int bz, Extras ex) {
        int exits = plan.exits(c);
        HallStyle style = plan.style(c);
        if (style == null) style = Integer.bitCount(exits) <= 1 ? HallStyle.NOOK : HallStyle.CROSS;
        SplittableRandom rng = new SplittableRandom(plan.seed() * 0x9E3779B97F4A7C15L + c * 1_000_003L + 17);
        int h = p.hallHeight();
        int deg = Integer.bitCount(exits);
        switch (style) {
            case BENT -> {
                if (deg == 2 && (exits == 0b0101 || exits == 0b1010)) {
                    Painter pt = new Painter(g, bx, bz, (exits & 1) != 0 ? 0 : 1);
                    int a = 5 + rng.nextInt(3), b = 24 - a, hx = rng.nextBoolean() ? 5 : 19;
                    int[][] pts = {{12, 0}, {12, a}, {hx, a}, {hx, b}, {12, b}, {12, 24}};
                    pt.path(pts, 1, h);
                    if (p.liquid()) pt.pathGutters(pts, 1, h);
                } else if (deg == 2) {
                    Painter pt = new Painter(g, bx, bz, cornerRotation(exits));
                    int[][] pts = rng.nextBoolean()
                            ? new int[][] {{12, 0}, {12, 6}, {18, 6}, {18, 12}, {24, 12}}
                            : new int[][] {{12, 0}, {12, 18}, {18, 18}, {18, 12}, {24, 12}};
                    pt.path(pts, 1, h);
                    if (p.liquid()) pt.pathGutters(pts, 1, h);
                } else {
                    cross(g, p, exits, bx, bz);
                }
            }
            case NARROW -> {
                Painter pt = new Painter(g, bx, bz, 0);
                int nh = Math.max(3, h - 1);
                pt.rect(12, 12, 12, 12, FloorLayout.FLOOR, nh, 0);
                for (int d = 0; d < 4; d++) {
                    if ((exits & (1 << d)) == 0) continue;
                    switch (d) {
                        case 0 -> { pt.rect(11, 0, 13, 2, FloorLayout.FLOOR, h, 0); pt.rect(12, 3, 12, 12, FloorLayout.FLOOR, nh, 0); }
                        case 1 -> { pt.rect(21, 11, 24, 13, FloorLayout.FLOOR, h, 0); pt.rect(12, 12, 20, 12, FloorLayout.FLOOR, nh, 0); }
                        case 2 -> { pt.rect(11, 21, 13, 24, FloorLayout.FLOOR, h, 0); pt.rect(12, 12, 12, 20, FloorLayout.FLOOR, nh, 0); }
                        default -> { pt.rect(0, 11, 2, 13, FloorLayout.FLOOR, h, 0); pt.rect(3, 12, 12, 12, FloorLayout.FLOOR, nh, 0); }
                    }
                }
                ex.lights.add(pt.tile(12, 12));
            }
            case PLAZA -> {
                Painter pt = new Painter(g, bx, bz, 0);
                int ph = Math.min(p.roomHeight(), h + 2);
                pt.rect(6, 6, 18, 18, FloorLayout.FLOOR, ph, 0);
                arms(pt, exits, h, 5, 19);
                if (rng.nextBoolean()) {
                    pt.carve(11, 11, 13, 13);
                } else {
                    for (int[] q : new int[][] {{9, 9}, {15, 9}, {9, 15}, {15, 15}}) pt.carve(q[0], q[1], q[0], q[1]);
                }
                for (int[] q : new int[][] {{12, 8}, {8, 12}, {16, 12}, {12, 16}}) ex.lights.add(pt.tile(q[0], q[1]));
            }
            case PILLARS -> {
                Painter pt = new Painter(g, bx, bz, 0);
                pt.rect(4, 4, 20, 20, FloorLayout.FLOOR, Math.min(p.roomHeight(), h + 1), 0);
                arms(pt, exits, h, 3, 21);
                int[] at = {6, 9, 12, 15, 18};
                for (int px : at) for (int pz : at) if (rng.nextDouble() < 0.85) pt.carve(px, pz, px, pz);
                for (int[] q : new int[][] {{7, 7}, {17, 7}, {7, 17}, {17, 17}}) ex.lights.add(pt.tile(q[0], q[1]));
            }
            case STAIRS -> {
                if (deg == 2 && (exits == 0b0101 || exits == 0b1010)) {
                    Painter pt = new Painter(g, bx, bz, (exits & 1) != 0 ? 0 : 1);
                    int rise = 1 + rng.nextInt(MAX_RISE);
                    for (int z = 0; z <= 24; z++) {
                        int e;
                        byte k = FloorLayout.FLOOR;
                        int dir = 0;
                        if (z < 5 || z >= 19) {
                            e = 0;
                        } else if (z < 5 + rise) {
                            e = z - 5;
                            k = FloorLayout.STAIR;
                            dir = MazePlan.SOUTH;
                        } else if (z <= 18 - rise) {
                            e = rise;
                        } else {
                            e = 18 - z;
                            k = FloorLayout.STAIR;
                            dir = MazePlan.NORTH;
                        }
                        for (int x = LANE_MIN; x <= LANE_MAX; x++) pt.set(x, z, k, h, e, dir);
                    }
                    ex.lights.add(pt.tile(12, 12));
                } else {
                    cross(g, p, exits, bx, bz);
                }
            }
            case WARREN -> warren(new Painter(g, bx, bz, 0), c, exits, h, rng, ex);
            case NOOK -> {
                Painter pt = new Painter(g, bx, bz, Integer.numberOfTrailingZeros(Math.max(1, exits)));
                int v = rng.nextInt(100);
                int[][] pts;
                int tx, tz;
                if (v < 35) {
                    pts = new int[][] {{12, 0}, {12, 11}};
                    tx = 12;
                    tz = 12;
                } else if (v < 70) {
                    int hx = rng.nextBoolean() ? 6 : 18;
                    pts = new int[][] {{12, 0}, {12, 6}, {hx, 6}, {hx, 14}};
                    tx = hx;
                    tz = 15;
                } else {
                    pts = new int[][] {{12, 0}, {12, 17}};
                    tx = 12;
                    tz = 18;
                }
                pt.path(pts, 1, h);
                pt.rect(tx - 2, tz - 2, tx + 2, tz + 2, FloorLayout.FLOOR, h, 0);
                if (p.liquid()) pt.pathGutters(pts, 1, h);
                int[] dv = pt.dirVector(MazePlan.NORTH);
                ex.deadEnds.add(new FloorLayout.DeadEnd(c, pt.wx(tx, tz), pt.wz(tx, tz), dv[0], dv[1], -1, false));
                ex.lights.add(pt.tile(tx, tz));
            }
            case SECRET -> {
                Painter pt = new Painter(g, bx, bz, Integer.numberOfTrailingZeros(Math.max(1, exits)));
                int[][] pts = {{12, 0}, {12, 8}};
                pt.path(pts, 1, h);
                if (p.liquid()) pt.pathGutters(pts, 1, h);
                pt.rect(11, 9, 13, 9, FloorLayout.SECRET, h, 0);
                pt.rect(8, 10, 16, 18, FloorLayout.FLOOR, h, 0);
                int[] wall = {pt.tile(11, 9), pt.tile(12, 9), pt.tile(13, 9)};
                int x0 = Math.min(pt.wx(8, 10), pt.wx(16, 18)), x1 = Math.max(pt.wx(8, 10), pt.wx(16, 18));
                int z0 = Math.min(pt.wz(8, 10), pt.wz(16, 18)), z1 = Math.max(pt.wz(8, 10), pt.wz(16, 18));
                int idx = ex.secrets.size();
                int deIdx = ex.deadEnds.size();
                int[] dv = pt.dirVector(MazePlan.NORTH);
                ex.deadEnds.add(new FloorLayout.DeadEnd(c, pt.wx(12, 8), pt.wz(12, 8), dv[0], dv[1], idx, false));
                ex.secrets.add(new FloorLayout.SecretRoom(idx, c, x0, z0, x1, z1, pt.wx(12, 14), pt.wz(12, 14), h, wall, deIdx));
                ex.lights.add(pt.tile(12, 14));
            }
            default -> cross(g, p, exits, bx, bz);
        }
    }

    /**
     * 미로 굴: 셀을 3×3 작은 칸(중심 로컬 4·12·20)으로 나눠 작은 신장 트리(+ 가끔 고리 하나)로 잇는다. 셀 출구는 가운데 줄 작은 칸에서
     * 나간다. 출구 없는 잎 작은 칸은 짧은 막다른 길 (minor).
     */
    private static void warren(Painter pt, int c, int exits, int h, SplittableRandom rng, Extras ex) {
        int[] at = {4, 12, 20};
        boolean[] seen = new boolean[9];
        int[] deg = new int[9];
        java.util.ArrayDeque<Integer> stack = new java.util.ArrayDeque<>();
        int first = 4;
        stack.push(first);
        seen[first] = true;
        List<int[]> edges = new ArrayList<>();
        while (!stack.isEmpty()) {
            int s = stack.peek();
            int sx = s % 3, sz = s / 3;
            int[] cand = new int[4];
            int k = 0;
            if (sx > 0 && !seen[s - 1]) cand[k++] = s - 1;
            if (sx < 2 && !seen[s + 1]) cand[k++] = s + 1;
            if (sz > 0 && !seen[s - 3]) cand[k++] = s - 3;
            if (sz < 2 && !seen[s + 3]) cand[k++] = s + 3;
            if (k == 0) {
                stack.pop();
                continue;
            }
            int o = cand[rng.nextInt(k)];
            seen[o] = true;
            edges.add(new int[] {s, o});
            stack.push(o);
        }
        if (rng.nextDouble() < 0.4) {
            // 고리 하나 (바깥 테두리 두 칸 사이)
            int[][] extra = {{0, 1}, {1, 2}, {6, 7}, {7, 8}, {0, 3}, {3, 6}, {2, 5}, {5, 8}};
            for (int tries = 0; tries < 8; tries++) {
                int[] e = extra[rng.nextInt(extra.length)];
                boolean dup = false;
                for (int[] q : edges) if ((q[0] == e[0] && q[1] == e[1]) || (q[0] == e[1] && q[1] == e[0])) dup = true;
                if (!dup) {
                    edges.add(e);
                    break;
                }
            }
        }
        for (int s = 0; s < 9; s++) pt.rect(at[s % 3] - 1, at[s / 3] - 1, at[s % 3] + 1, at[s / 3] + 1, FloorLayout.FLOOR, h, 0);
        for (int[] e : edges) {
            int ax = at[e[0] % 3], az = at[e[0] / 3], bx = at[e[1] % 3], bz = at[e[1] / 3];
            pt.path(new int[][] {{ax, az}, {bx, bz}}, 1, h);
            deg[e[0]]++;
            deg[e[1]]++;
        }
        int[][] ports = {{1, 12, 0}, {5, 24, 12}, {7, 12, 24}, {3, 0, 12}};  // 출구 방향별 (작은 칸, 끝 x, 끝 z)
        for (int d = 0; d < 4; d++) {
            if ((exits & (1 << d)) == 0) continue;
            int s = ports[d][0];
            pt.path(new int[][] {{at[s % 3], at[s / 3]}, {ports[d][1], ports[d][2]}}, 1, h);
            deg[s]++;
        }
        for (int s = 0; s < 9; s++) {
            if (deg[s] != 1) continue;
            int nbX = 0, nbZ = 0;
            for (int[] e : edges) {
                int o = e[0] == s ? e[1] : e[1] == s ? e[0] : -1;
                if (o < 0) continue;
                nbX = Integer.signum(o % 3 - s % 3);
                nbZ = Integer.signum(o / 3 - s / 3);
            }
            ex.deadEnds.add(new FloorLayout.DeadEnd(c, pt.wx(at[s % 3], at[s / 3]), pt.wz(at[s % 3], at[s / 3]), nbX, nbZ, -1, true));
        }
        ex.lights.add(pt.tile(12, 12));
    }

    /** 기본 십자 복도: 가운데 3×3 + 출구마다 곧은 팔 (액체 층이면 팔 양옆 도랑). */
    private static void cross(Grid g, Params p, int exits, int bx, int bz) {
        g.fill(bx + LANE_MIN, bz + LANE_MIN, bx + LANE_MAX, bz + LANE_MAX, FloorLayout.FLOOR, -1, p.hallHeight());
        if ((exits & 2) != 0) arm(g, p, bx + LANE_MAX + 1, bz + LANE_MIN, bx + PITCH - 1, bz + LANE_MAX, true);
        if ((exits & 8) != 0) arm(g, p, bx, bz + LANE_MIN, bx + LANE_MIN - 1, bz + LANE_MAX, true);
        if ((exits & 4) != 0) arm(g, p, bx + LANE_MIN, bz + LANE_MAX + 1, bx + LANE_MAX, bz + PITCH - 1, false);
        if ((exits & 1) != 0) arm(g, p, bx + LANE_MIN, bz, bx + LANE_MAX, bz + LANE_MIN - 1, false);
    }

    /** 광장·기둥 숲의 출구 팔 (안쪽 경계 lo/hi 까지). */
    private static void arms(Painter pt, int exits, int h, int lo, int hi) {
        if ((exits & 1) != 0) pt.rect(11, 0, 13, lo, FloorLayout.FLOOR, h, 0);
        if ((exits & 2) != 0) pt.rect(hi, 11, 24, 13, FloorLayout.FLOOR, h, 0);
        if ((exits & 4) != 0) pt.rect(11, hi, 13, 24, FloorLayout.FLOOR, h, 0);
        if ((exits & 8) != 0) pt.rect(0, 11, lo, 13, FloorLayout.FLOOR, h, 0);
    }

    /** 북+동 모양을 돌려 맞출 회전 수. */
    private static int cornerRotation(int exits) {
        for (int r = 0; r < 4; r++) if (exits == ((1 << r) | (1 << ((r + 1) % 4)))) return r;
        return 0;
    }

    /** 복도 팔 (horizontal = x 방향). 액체 층이면 양옆 도랑. */
    private static void arm(Grid g, Params p, int x0, int z0, int x1, int z1, boolean horizontal) {
        g.fill(x0, z0, x1, z1, FloorLayout.FLOOR, -1, p.hallHeight());
        if (!p.liquid()) return;
        if (horizontal) {
            for (int x = x0; x <= x1; x++) {
                g.setIfVoid(x, z0 - 1, FloorLayout.GUTTER, -1, p.hallHeight());
                g.setIfVoid(x, z1 + 1, FloorLayout.GUTTER, -1, p.hallHeight());
            }
        } else {
            for (int z = z0; z <= z1; z++) {
                g.setIfVoid(x0 - 1, z, FloorLayout.GUTTER, -1, p.hallHeight());
                g.setIfVoid(x1 + 1, z, FloorLayout.GUTTER, -1, p.hallHeight());
            }
        }
    }

    /** 통로 타일 하나: A 의 벽선(22)·B 의 벽선(PITCH+2) 이 방이면 그 방의 출입구. */
    private static void passage(Grid g, Params p, List<FloorLayout.RoomInfo> rooms, List<List<Integer>> doorLists,
                                int[] roomOfCell, int a, int b, int local, int x, int z) {
        int ra = roomOfCell[a], rb = roomOfCell[b];
        if (local == 22 && ra >= 0) {
            g.set(x, z, FloorLayout.DOOR, ra, p.hallHeight());
            doorLists.get(ra).add(FloorLayout.pack(x, z));
        } else if (local == PITCH + 2 && rb >= 0) {
            g.set(x, z, FloorLayout.DOOR, rb, p.hallHeight());
            doorLists.get(rb).add(FloorLayout.pack(x, z));
        } else if (g.kind(x, z) != FloorLayout.FLOOR || g.region(x, z) < 0) {
            g.set(x, z, FloorLayout.FLOOR, -1, p.hallHeight());
        }
    }

    /** 함정 자리 후보: 격자 안 평평한 복도 바닥 (비밀방·문 근처 제외). */
    private static int[] hallTiles(Grid g, int n, List<FloorLayout.SecretRoom> secrets) {
        List<Integer> out = new ArrayList<>();
        int gridMaxZ = MARGIN_Z + n * PITCH, gridMaxX = MARGIN_X + n * PITCH;
        for (int z = MARGIN_Z; z < gridMaxZ; z++) {
            for (int x = MARGIN_X; x < gridMaxX; x++) {
                if (g.kind(x, z) != FloorLayout.FLOOR || g.region(x, z) >= 0) continue;
                boolean bad = false;
                for (FloorLayout.SecretRoom s : secrets) if (s.contains(x, z)) bad = true;
                for (int dz = -2; dz <= 2 && !bad; dz++) {
                    for (int dx = -2; dx <= 2; dx++) {
                        if (g.kind(x + dx, z + dz) == FloorLayout.DOOR) {
                            bad = true;
                            break;
                        }
                    }
                }
                if (!bad) out.add(FloorLayout.pack(x, z));
            }
        }
        return out.stream().mapToInt(Integer::intValue).toArray();
    }

    /**
     * 셀 하나를 북쪽 기준(정준) 좌표로 칠하는 붓. 정준 좌표 0..24 (24 = 다음 셀 첫 칸) 를 셀 중심 (12,12) 으로 rot×90° 돌려
     * 이 셀(로컬 0..23) 안만 칠한다. 회전: (x, z) → (24 − z, x) — 북 → 동 → 남 → 서.
     */
    private static final class Painter {
        final Grid g;
        final int bx, bz, rot;

        Painter(Grid g, int bx, int bz, int rot) {
            this.g = g;
            this.bx = bx;
            this.bz = bz;
            this.rot = ((rot % 4) + 4) % 4;
        }

        int lx(int x, int z) {
            return switch (rot) {
                case 1 -> 24 - z;
                case 2 -> 24 - x;
                case 3 -> z;
                default -> x;
            };
        }

        int lz(int x, int z) {
            return switch (rot) {
                case 1 -> x;
                case 2 -> 24 - z;
                case 3 -> 24 - x;
                default -> z;
            };
        }

        int wx(int x, int z) { return bx + Math.min(23, lx(x, z)); }
        int wz(int x, int z) { return bz + Math.min(23, lz(x, z)); }
        int tile(int x, int z) { return FloorLayout.pack(wx(x, z), wz(x, z)); }

        /** 정준 방향 → 실제 방향 단위 벡터. */
        int[] dirVector(int canonical) {
            return switch ((canonical + rot) % 4) {
                case 0 -> new int[] {0, -1};
                case 1 -> new int[] {1, 0};
                case 2 -> new int[] {0, 1};
                default -> new int[] {-1, 0};
            };
        }

        void set(int x, int z, byte k, int h, int e, int dirCanonical) {
            int x2 = lx(x, z), z2 = lz(x, z);
            if (x2 < 0 || z2 < 0 || x2 > 23 || z2 > 23) return;
            g.setFull(bx + x2, bz + z2, k, -1, h, e, (dirCanonical + rot) % 4);
        }

        void rect(int x0, int z0, int x1, int z1, byte k, int h, int e) {
            for (int z = Math.min(z0, z1); z <= Math.max(z0, z1); z++)
                for (int x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) set(x, z, k, h, e, 0);
        }

        /** 기둥 (빈 타일 → 벽 기둥이 된다). */
        void carve(int x0, int z0, int x1, int z1) {
            for (int z = z0; z <= z1; z++) {
                for (int x = x0; x <= x1; x++) {
                    int x2 = lx(x, z), z2 = lz(x, z);
                    if (x2 < 0 || z2 < 0 || x2 > 23 || z2 > 23) continue;
                    g.set(bx + x2, bz + z2, FloorLayout.VOID, -1, 0);
                }
            }
        }

        void path(int[][] pts, int half, int h) {
            for (int i = 0; i + 1 < pts.length; i++) {
                int[] a = pts[i], b = pts[i + 1];
                rect(Math.min(a[0], b[0]) - half, Math.min(a[1], b[1]) - half, Math.max(a[0], b[0]) + half,
                        Math.max(a[1], b[1]) + half, FloorLayout.FLOOR, h, 0);
            }
        }

        /** 통로 양옆 도랑 (빈 타일에만, 이 셀 안만). */
        void pathGutters(int[][] pts, int half, int h) {
            for (int i = 0; i + 1 < pts.length; i++) {
                int[] a = pts[i], b = pts[i + 1];
                if (a[1] == b[1]) {
                    for (int x = Math.min(a[0], b[0]) - half; x <= Math.max(a[0], b[0]) + half; x++) {
                        gutter(x, a[1] - half - 1, h);
                        gutter(x, a[1] + half + 1, h);
                    }
                } else {
                    for (int z = Math.min(a[1], b[1]) - half; z <= Math.max(a[1], b[1]) + half; z++) {
                        gutter(a[0] - half - 1, z, h);
                        gutter(a[0] + half + 1, z, h);
                    }
                }
            }
        }

        private void gutter(int x, int z, int h) {
            int x2 = lx(x, z), z2 = lz(x, z);
            if (x2 < 0 || z2 < 0 || x2 > 23 || z2 > 23) return;
            g.setIfVoid(bx + x2, bz + z2, FloorLayout.GUTTER, -1, h);
        }
    }

    /** 가변 타일 격자 (빌드 중에만). */
    private static final class Grid {
        final int w, d;
        final byte[] kind;
        final short[] region;
        final byte[] height;
        final byte[] elev;
        final byte[] facing;

        Grid(int w, int d) {
            this.w = w;
            this.d = d;
            kind = new byte[w * d];
            region = new short[w * d];
            height = new byte[w * d];
            elev = new byte[w * d];
            facing = new byte[w * d];
            java.util.Arrays.fill(region, (short) -1);
        }

        boolean in(int x, int z) { return x >= 0 && z >= 0 && x < w && z < d; }

        byte kind(int x, int z) { return in(x, z) ? kind[z * w + x] : FloorLayout.VOID; }

        int region(int x, int z) { return in(x, z) ? region[z * w + x] : -1; }

        void set(int x, int z, byte k, int r, int h) { setFull(x, z, k, r, h, 0, 0); }

        void setFull(int x, int z, byte k, int r, int h, int e, int f) {
            if (!in(x, z)) return;
            int i = z * w + x;
            kind[i] = k;
            region[i] = (short) r;
            height[i] = (byte) h;
            elev[i] = (byte) e;
            facing[i] = (byte) f;
        }

        void setIfVoid(int x, int z, byte k, int r, int h) {
            if (kind(x, z) == FloorLayout.VOID) set(x, z, k, r, h);
        }

        void fill(int x0, int z0, int x1, int z1, byte k, int r, int h) {
            for (int z = Math.min(z0, z1); z <= Math.max(z0, z1); z++)
                for (int x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) set(x, z, k, r, h);
        }
    }
}
