package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * 시드 미로 결과 (순수 데이터, Bukkit 무관). n×n 셀 격자. 셀 인덱스 = z*n + x (z=0 이 입구 쪽, z=n-1 이 보스 쪽).
 * types[c] == null 이면 쓰지 않는 셀(잘라 냄). east[c] = (x,z)↔(x+1,z) 통로, south[c] = (x,z)↔(x,z+1) 통로.
 * 방향 번호 d: 0=북(−z) 1=동(+x) 2=남(+z) 3=서(−x), 출구 비트 = 1 &lt;&lt; d.
 */
public final class MazePlan {

    public static final int NORTH = 0, EAST = 1, SOUTH = 2, WEST = 3;

    private final int n;
    private final RoomType[] types;
    private final boolean[] east;
    private final boolean[] south;
    private final int start;
    private final int bossAttach;
    private final HallStyle[] styles;
    private final boolean[] secret;
    private final long seed;
    private final int initialDeadEnds;
    private final int attempt;
    private final List<Integer> mainPath;
    private final int[] dist;
    private final int[] pathIndex;

    MazePlan(int n, RoomType[] types, boolean[] east, boolean[] south, int start, int bossAttach) {
        this(n, types, east, south, start, bossAttach, null, null, 0L, 0, 0);
    }

    MazePlan(int n, RoomType[] types, boolean[] east, boolean[] south, int start, int bossAttach, HallStyle[] styles,
             boolean[] secret, long seed, int initialDeadEnds, int attempt) {
        this.n = n;
        this.types = types;
        this.east = east;
        this.south = south;
        this.start = start;
        this.bossAttach = bossAttach;
        this.styles = styles == null ? new HallStyle[n * n] : styles;
        this.secret = secret == null ? new boolean[n * n] : secret;
        this.seed = seed;
        this.initialDeadEnds = initialDeadEnds;
        this.attempt = attempt;
        this.mainPath = Collections.unmodifiableList(path(start, bossAttach));
        this.dist = distances(start);
        this.pathIndex = new int[n * n];
        Arrays.fill(pathIndex, -1);
        for (int i = 0; i < mainPath.size(); i++) pathIndex[mainPath.get(i)] = i;
    }

    public int size() { return n; }
    public int cellCount() { return n * n; }
    public int x(int c) { return c % n; }
    public int z(int c) { return c / n; }
    public int index(int x, int z) { return z * n + x; }
    public boolean used(int c) { return c >= 0 && c < n * n && types[c] != null; }
    public RoomType type(int c) { return types[c]; }
    public int start() { return start; }
    /** 보스방 복도가 이어지는 마지막 줄(z = n-1) 셀 — 시작에서 BFS 로 가장 먼 마지막 줄 셀. */
    public int bossAttach() { return bossAttach; }
    /** 시작 → 보스 연결 셀까지 최단 경로 (양 끝 포함). */
    public List<Integer> mainPath() { return mainPath; }
    /** 주 경로에서 몇 번째 셀인가 (주 경로 밖이면 -1). */
    public int pathIndex(int c) { return c >= 0 && c < n * n ? pathIndex[c] : -1; }
    public boolean onMainPath(int c) { return pathIndex(c) >= 0; }
    /** 시작 셀에서 걸어서 몇 칸 (닿지 않으면 -1). */
    public int distance(int c) { return c >= 0 && c < n * n ? dist[c] : -1; }
    /** 복도 셀 모양 (방·빈 셀은 null). */
    public HallStyle style(int c) { return used(c) ? styles[c] : null; }
    /** 비밀 통로(금 간 벽 + 숨은 방)가 있는 막다른 복도 셀인가. */
    public boolean secret(int c) { return used(c) && secret[c]; }
    public long seed() { return seed; }
    /** 정리하기 전 막다른 길 수 (시작·보스 연결 제외). */
    public int initialDeadEnds() { return initialDeadEnds; }
    /** 주 경로 길이 조건 때문에 다시 만든 횟수 (0 = 첫 시도). */
    public int attempt() { return attempt; }

    public boolean openEast(int c) { return x(c) < n - 1 && east[c] && used(c) && used(c + 1); }
    public boolean openSouth(int c) { return z(c) < n - 1 && south[c] && used(c) && used(c + n); }
    public boolean openWest(int c) { return x(c) > 0 && openEast(c - 1); }
    public boolean openNorth(int c) { return z(c) > 0 && openSouth(c - n); }

    public boolean open(int c, int dir) {
        return switch (dir) {
            case NORTH -> openNorth(c);
            case EAST -> openEast(c);
            case SOUTH -> openSouth(c);
            default -> openWest(c);
        };
    }

    /** 이웃 셀 (격자 밖이면 -1). */
    public int step(int c, int dir) {
        int x = x(c), z = z(c);
        return switch (dir) {
            case NORTH -> z > 0 ? c - n : -1;
            case EAST -> x < n - 1 ? c + 1 : -1;
            case SOUTH -> z < n - 1 ? c + n : -1;
            default -> x > 0 ? c - 1 : -1;
        };
    }

    /** 열린 출구 비트 (1&lt;&lt;방향). 보스 연결 셀은 남쪽(보스 복도) 포함. */
    public int exits(int c) {
        if (!used(c)) return 0;
        int m = 0;
        for (int d = 0; d < 4; d++) if (open(c, d)) m |= 1 << d;
        if (c == bossAttach) m |= 1 << SOUTH;
        return m;
    }

    /** 열린 통로로 이어진 이웃 셀. */
    public List<Integer> neighbors(int c) {
        List<Integer> out = new ArrayList<>(4);
        if (openEast(c)) out.add(c + 1);
        if (openWest(c)) out.add(c - 1);
        if (openSouth(c)) out.add(c + n);
        if (openNorth(c)) out.add(c - n);
        return out;
    }

    public int degree(int c) { return neighbors(c).size(); }

    /** 사용 중인 셀 수. */
    public int usedCount() {
        int k = 0;
        for (RoomType t : types) if (t != null) k++;
        return k;
    }

    public int count(RoomType t) {
        int k = 0;
        for (RoomType x : types) if (x == t) k++;
        return k;
    }

    /** 열린 통로 수. */
    public int edgeCount() {
        int k = 0;
        for (int c = 0; c < n * n; c++) {
            if (openEast(c)) k++;
            if (openSouth(c)) k++;
        }
        return k;
    }

    /** 고리 수 = 통로 − (셀 − 1). 0 이면 나무(갈림길로 돌아오는 길 없음). */
    public int loopCount() { return edgeCount() - (usedCount() - 1); }

    /** 막다른 복도 셀 (출구 1개, 시작·보스 연결 제외) — 보물 상자·함정·비밀 통로 자리. */
    public List<Integer> deadEnds() {
        List<Integer> out = new ArrayList<>();
        for (int c = 0; c < n * n; c++) {
            if (used(c) && types[c] == RoomType.HALL && c != bossAttach && c != start && degree(c) == 1) out.add(c);
        }
        return out;
    }

    /** BFS 최단 경로 (도달 불가면 빈 목록). */
    public List<Integer> path(int from, int to) {
        int[] prev = new int[n * n];
        Arrays.fill(prev, -2);
        ArrayDeque<Integer> q = new ArrayDeque<>();
        q.add(from);
        prev[from] = -1;
        while (!q.isEmpty()) {
            int c = q.poll();
            if (c == to) break;
            // 방향 순서 북·동·남·서 고정 (생성기와 같은 최단 경로를 고르도록)
            for (int d = 0; d < 4; d++) {
                if (!open(c, d)) continue;
                int nb = step(c, d);
                if (prev[nb] == -2) {
                    prev[nb] = c;
                    q.add(nb);
                }
            }
        }
        if (prev[to] == -2) return List.of();
        List<Integer> out = new ArrayList<>();
        for (int c = to; c != -1; c = prev[c]) out.add(c);
        Collections.reverse(out);
        return out;
    }

    private int[] distances(int from) {
        int[] d = new int[n * n];
        Arrays.fill(d, -1);
        ArrayDeque<Integer> q = new ArrayDeque<>();
        q.add(from);
        d[from] = 0;
        while (!q.isEmpty()) {
            int c = q.poll();
            for (int nb : neighbors(c)) {
                if (d[nb] < 0) {
                    d[nb] = d[c] + 1;
                    q.add(nb);
                }
            }
        }
        return d;
    }

    /** start 에서 도달 가능한 사용 셀 수. */
    public int reachableFromStart() {
        int k = 0;
        for (int c = 0; c < n * n; c++) if (used(c) && dist[c] >= 0) k++;
        return k;
    }

    /** 디버그용 ASCII 지도. 소문자 = 복도 모양 (+ 기본, b 꺾임, n 좁음, p 광장, s 계단, i 기둥, w 미로 굴, d 막다른 길, ? 비밀). */
    public String ascii() {
        StringBuilder sb = new StringBuilder();
        for (int z = 0; z < n; z++) {
            StringBuilder row = new StringBuilder();
            StringBuilder below = new StringBuilder();
            for (int x = 0; x < n; x++) {
                int c = index(x, z);
                RoomType t = types[c];
                char ch = t == null ? ' ' : switch (t) {
                    case START -> 'S';
                    case COMBAT -> 'C';
                    case ELITE -> 'E';
                    case TREASURE -> 'T';
                    case GIMMICK -> 'G';
                    case REST -> 'R';
                    case BOSS -> 'B';
                    case HALL -> c == bossAttach ? 'X' : hallChar(styles[c]);
                };
                row.append(ch).append(openEast(c) ? '-' : ' ');
                below.append(openSouth(c) || (c == bossAttach) ? '|' : ' ').append(' ');
            }
            sb.append(row).append('\n').append(below).append('\n');
        }
        return sb.toString();
    }

    private static char hallChar(HallStyle s) {
        if (s == null) return '+';
        return switch (s) {
            case CROSS -> '+';
            case BENT -> 'b';
            case NARROW -> 'n';
            case PLAZA -> 'p';
            case STAIRS -> 's';
            case PILLARS -> 'i';
            case WARREN -> 'w';
            case NOOK -> 'd';
            case SECRET -> '?';
        };
    }
}
