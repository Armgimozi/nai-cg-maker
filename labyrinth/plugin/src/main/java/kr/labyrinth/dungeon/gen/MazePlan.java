package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * 시드 미로 결과 (순수 데이터, Bukkit 무관). n×n 셀 격자. 셀 인덱스 = z*n + x (z=0 이 입구 쪽, z=n-1 이 보스 쪽).
 * types[c] == null 이면 쓰지 않는 셀(가지치기됨). east[c] = (x,z)↔(x+1,z) 통로, south[c] = (x,z)↔(x,z+1) 통로.
 */
public final class MazePlan {

    private final int n;
    private final RoomType[] types;
    private final boolean[] east;
    private final boolean[] south;
    private final int start;
    private final int bossAttach;
    private final List<Integer> mainPath;

    MazePlan(int n, RoomType[] types, boolean[] east, boolean[] south, int start, int bossAttach) {
        this.n = n;
        this.types = types;
        this.east = east;
        this.south = south;
        this.start = start;
        this.bossAttach = bossAttach;
        this.mainPath = Collections.unmodifiableList(path(start, bossAttach));
    }

    public int size() { return n; }
    public int cellCount() { return n * n; }
    public int x(int c) { return c % n; }
    public int z(int c) { return c / n; }
    public int index(int x, int z) { return z * n + x; }
    public boolean used(int c) { return c >= 0 && c < n * n && types[c] != null; }
    public RoomType type(int c) { return types[c]; }
    public int start() { return start; }
    /** 보스방 복도가 이어지는 마지막 줄(z = n-1) 셀. */
    public int bossAttach() { return bossAttach; }
    /** 시작 → 보스 연결 셀까지 최단 경로 (양 끝 포함). */
    public List<Integer> mainPath() { return mainPath; }

    public boolean openEast(int c) { return x(c) < n - 1 && east[c] && used(c) && used(c + 1); }
    public boolean openSouth(int c) { return z(c) < n - 1 && south[c] && used(c) && used(c + n); }
    public boolean openWest(int c) { return x(c) > 0 && openEast(c - 1); }
    public boolean openNorth(int c) { return z(c) > 0 && openSouth(c - n); }

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
            for (int nb : neighbors(c)) {
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

    /** start 에서 도달 가능한 사용 셀 수. */
    public int reachableFromStart() {
        boolean[] seen = new boolean[n * n];
        ArrayDeque<Integer> q = new ArrayDeque<>();
        q.add(start);
        seen[start] = true;
        int k = 0;
        while (!q.isEmpty()) {
            int c = q.poll();
            k++;
            for (int nb : neighbors(c)) {
                if (!seen[nb]) {
                    seen[nb] = true;
                    q.add(nb);
                }
            }
        }
        return k;
    }

    /** 디버그용 ASCII 지도. */
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
                    case COMBAT -> 'c';
                    case ELITE -> 'E';
                    case TREASURE -> 'T';
                    case GIMMICK -> 'G';
                    case REST -> 'R';
                    case BOSS -> 'B';
                    case HALL -> c == bossAttach ? 'b' : '+';
                };
                row.append(ch).append(openEast(c) ? '-' : ' ');
                below.append(openSouth(c) ? '|' : ' ').append(' ');
            }
            sb.append(row).append('\n').append(below).append('\n');
        }
        return sb.toString();
    }
}
