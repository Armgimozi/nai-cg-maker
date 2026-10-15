package kr.labyrinth.dungeon.gen;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 층 설계 (순수 로직 — 단위 테스트 대상): 시드 미로({@link MazeGenerator}) → 타일 지도({@link FloorLayout}).
 * <p>
 * 셀 하나 = {@value #PITCH}×{@value #PITCH} 타일. 방 셀은 내부 19×19(로컬 3~21), 벽은 로컬 2·22, 출입구는 벽 가운데 3칸(로컬 11~13).
 * 복도 셀은 가운데 3칸 폭 통로가 열린 방향으로 뻗는다(액체 층이면 양옆 도랑 1칸씩).
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
    /** 심연의 가장자리(추격 복도 끝 원형 단) 바깥 낭떠러지 폭 — 생성기는 바닥으로 깔고, 보스가 전투 중 비운다(10층). */
    public static final int RIM_MOAT = 3;

    /** 층 설계 입력 (floors.yml + bosses.yml arena 에서 뽑은 값). */
    public record Params(int cells, Map<String, Integer> rooms, int roomHeight, int hallHeight, boolean liquid,
                         int arenaRadius, int arenaHeight, int arenaCorridorLength, int arenaCorridorWidth, int arenaRimRadius) {
        /** 가장자리 단 없는 투기장 (1~9층). */
        public Params(int cells, Map<String, Integer> rooms, int roomHeight, int hallHeight, boolean liquid,
                      int arenaRadius, int arenaHeight, int arenaCorridorLength, int arenaCorridorWidth) {
            this(cells, rooms, roomHeight, hallHeight, liquid, arenaRadius, arenaHeight, arenaCorridorLength, arenaCorridorWidth, 0);
        }

        public Params {
            roomHeight = clamp(roomHeight, 4, 12);
            hallHeight = clamp(hallHeight, 3, roomHeight);
            arenaRadius = clamp(arenaRadius, 8, 22);
            arenaHeight = clamp(arenaHeight, 6, 20);
            arenaCorridorLength = clamp(arenaCorridorLength, 0, 120);
            arenaCorridorWidth = clamp(arenaCorridorWidth <= 0 ? 7 : arenaCorridorWidth, 3, 11);
            arenaRimRadius = arenaCorridorLength > 0 && arenaRimRadius > 0 ? clamp(arenaRimRadius, 6, 18) : 0;
        }

        /** 가장자리 단(낭떠러지 포함) 바깥 반경. 0 = 없음. */
        public int rimOuter() { return arenaRimRadius > 0 ? arenaRimRadius + RIM_MOAT : 0; }
    }

    /**
     * 심연의 가장자리 단 중심의 z 오프셋 (투기장 중심 기준, +z). 추격 복도 끝 줄이 단 북쪽 가장자리와 겹친다.
     * 보스 구현(10층)도 같은 식으로 단 위치를 계산한다 — 관리자 소환처럼 레이아웃이 없을 때도.
     */
    public static int rimCenterOffset(int arenaRadius, int corridorLength, int rimRadius) {
        return arenaRadius + corridorLength + rimRadius + RIM_MOAT - 1;
    }

    private FloorGenerator() {}

    public static FloorLayout generate(Params p, long seed) {
        MazePlan plan = MazeGenerator.generate(p.cells(), seed, p.rooms());
        return layout(plan, p);
    }

    static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    public static FloorLayout layout(MazePlan plan, Params p) {
        int n = plan.size();
        int r = p.arenaRadius();
        int width = MARGIN_X * 2 + n * PITCH;
        int arenaCz = MARGIN_Z + n * PITCH + BOSS_CORRIDOR + r;
        int depth = arenaCz + r + 2 + (p.arenaCorridorLength() > 0 ? p.arenaCorridorLength() + 2 : 0) + 2 + p.rimOuter() * 2;
        Grid g = new Grid(width, depth);

        List<FloorLayout.RoomInfo> rooms = new ArrayList<>();
        List<List<Integer>> doorLists = new ArrayList<>();
        int[] roomOfCell = new int[n * n];
        java.util.Arrays.fill(roomOfCell, -1);
        int startRoom = -1;

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
                g.fill(bx + LANE_MIN, bz + LANE_MIN, bx + LANE_MAX, bz + LANE_MAX, FloorLayout.FLOOR, -1, p.hallHeight());
                boolean south = plan.openSouth(c) || c == plan.bossAttach();
                if (plan.openEast(c)) arm(g, p, bx + LANE_MAX + 1, bz + LANE_MIN, bx + PITCH - 1, bz + LANE_MAX, true);
                if (plan.openWest(c)) arm(g, p, bx, bz + LANE_MIN, bx + LANE_MIN - 1, bz + LANE_MAX, true);
                if (south) arm(g, p, bx + LANE_MIN, bz + LANE_MAX + 1, bx + LANE_MAX, bz + PITCH - 1, false);
                if (plan.openNorth(c)) arm(g, p, bx + LANE_MIN, bz, bx + LANE_MAX, bz + LANE_MIN - 1, false);
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
        // 심연의 가장자리 (10층): 추격 복도 끝의 원형 단. 바깥 RIM_MOAT 칸은 보스가 전투 중 비워 낭떠러지가 된다.
        int rimR = p.rimOuter();
        int maxZ = cz + r + (p.arenaCorridorLength() > 0 ? p.arenaCorridorLength() : 0);
        if (rimR > 0) {
            int rcz = cz + rimCenterOffset(r, p.arenaCorridorLength(), p.arenaRimRadius());
            for (int z = rcz - rimR; z <= rcz + rimR; z++) {
                for (int x = cx - rimR; x <= cx + rimR; x++) {
                    int dx = x - cx, dz = z - rcz;
                    if (dx * dx + dz * dz <= rimR * rimR + rimR) g.set(x, z, FloorLayout.FLOOR, bossIdx, p.arenaHeight());
                }
            }
            maxZ = rcz + rimR;
        }
        int minZ = cz - r;
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
        FloorLayout.Arena arena = new FloorLayout.Arena(cx, cz, r, p.arenaHeight(), p.arenaCorridorLength(), p.arenaCorridorWidth(),
                p.arenaRimRadius());
        return new FloorLayout(width, depth, g.kind, g.region, g.height, finalRooms, startRoom, bossIdx, arena, plan);
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

    /** 가변 타일 격자 (빌드 중에만). */
    private static final class Grid {
        final int w, d;
        final byte[] kind;
        final short[] region;
        final byte[] height;

        Grid(int w, int d) {
            this.w = w;
            this.d = d;
            kind = new byte[w * d];
            region = new short[w * d];
            height = new byte[w * d];
            java.util.Arrays.fill(region, (short) -1);
        }

        boolean in(int x, int z) { return x >= 0 && z >= 0 && x < w && z < d; }

        byte kind(int x, int z) { return in(x, z) ? kind[z * w + x] : FloorLayout.VOID; }

        int region(int x, int z) { return in(x, z) ? region[z * w + x] : -1; }

        void set(int x, int z, byte k, int r, int h) {
            if (!in(x, z)) return;
            int i = z * w + x;
            kind[i] = k;
            region[i] = (short) r;
            height[i] = (byte) h;
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
