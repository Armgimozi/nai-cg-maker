package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;

/**
 * 시드 기반 미로 (순수 로직 — 단위 테스트 대상).
 * <ol>
 *   <li>n×n 셀 전체에 무작위 DFS 신장 트리 → 모든 셀이 연결됨</li>
 *   <li>시작(첫 줄)·보스 연결(마지막 줄)을 정하고, 나머지 셀 중 무작위로 방 종류 배정 (floors.yml rooms 개수 그대로)</li>
 *   <li>방이 없는 막다른 복도 셀을 반복해서 잘라냄 → 방만 잇는 나무 (잎을 지워도 연결은 유지)</li>
 *   <li>남은 이웃 셀 사이에 약간의 고리 통로 추가 (길 다양화)</li>
 *   <li>시작→보스 주 경로 위에 휴식방이 최소 1개 오게 보정 (GDD §5.2)</li>
 * </ol>
 */
public final class MazeGenerator {

    /** 방 종류 배정 우선순위 — 셀이 모자라면 뒤(전투방)부터 줄인다. */
    private static final RoomType[] ORDER = {RoomType.REST, RoomType.GIMMICK, RoomType.TREASURE, RoomType.ELITE, RoomType.COMBAT};

    public static final double LOOP_CHANCE = 0.10;

    private MazeGenerator() {}

    public static MazePlan generate(int cells, long seed, Map<String, Integer> roomCounts) {
        int n = Math.max(3, Math.min(16, cells));
        SplittableRandom rng = new SplittableRandom(seed);
        int total = n * n;
        boolean[] east = new boolean[total];
        boolean[] south = new boolean[total];

        int start = rng.nextInt(n);                       // (x, 0)
        int boss = (n - 1) * n + rng.nextInt(n);          // (x, n-1)

        // 1. 신장 트리 (반복 DFS)
        boolean[] seen = new boolean[total];
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(start);
        seen[start] = true;
        int[] nb = new int[4];
        while (!stack.isEmpty()) {
            int c = stack.peek();
            int x = c % n, z = c / n, k = 0;
            if (x < n - 1 && !seen[c + 1]) nb[k++] = c + 1;
            if (x > 0 && !seen[c - 1]) nb[k++] = c - 1;
            if (z < n - 1 && !seen[c + n]) nb[k++] = c + n;
            if (z > 0 && !seen[c - n]) nb[k++] = c - n;
            if (k == 0) {
                stack.pop();
                continue;
            }
            int next = nb[rng.nextInt(k)];
            open(east, south, n, c, next);
            seen[next] = true;
            stack.push(next);
        }

        // 2. 방 배정
        RoomType[] types = new RoomType[total];
        java.util.Arrays.fill(types, RoomType.HALL);
        types[start] = RoomType.START;
        List<RoomType> wanted = new ArrayList<>();
        for (RoomType t : ORDER) {
            int c = Math.max(0, roomCounts.getOrDefault(t.key(), 0));
            for (int i = 0; i < c; i++) wanted.add(t);
        }
        int cap = total - 2;
        while (wanted.size() > cap) wanted.remove(wanted.size() - 1);
        List<Integer> cand = new ArrayList<>();
        for (int c = 0; c < total; c++) if (c != start && c != boss) cand.add(c);
        shuffle(cand, rng);
        // 시작방 바로 옆은 되도록 비워 둔다(입장 직후 연속 전투 방지): 이웃을 뒤로 보냄
        cand.sort((a, b) -> Boolean.compare(adjacent(n, a, start), adjacent(n, b, start)));
        for (int i = 0; i < wanted.size(); i++) types[cand.get(i)] = wanted.get(i);

        // 3. 가지치기
        boolean[] used = new boolean[total];
        java.util.Arrays.fill(used, true);
        prune(types, used, east, south, n, boss);

        // 4. 고리 통로
        for (int c = 0; c < total; c++) {
            if (!used[c]) continue;
            int x = c % n, z = c / n;
            if (x < n - 1 && used[c + 1] && !east[c] && rng.nextDouble() < LOOP_CHANCE) east[c] = true;
            if (z < n - 1 && used[c + n] && !south[c] && rng.nextDouble() < LOOP_CHANCE) south[c] = true;
        }

        RoomType[] finalTypes = new RoomType[total];
        for (int c = 0; c < total; c++) finalTypes[c] = used[c] ? types[c] : null;
        MazePlan plan = new MazePlan(n, finalTypes, east, south, start, boss);

        // 5. 주 경로 휴식방 보정
        if (plan.count(RoomType.REST) > 0) {
            List<Integer> path = plan.mainPath();
            boolean restOnPath = false;
            for (int i = 1; i < path.size() - 1; i++) if (finalTypes[path.get(i)] == RoomType.REST) restOnPath = true;
            if (!restOnPath && path.size() > 2) {
                int mid = path.get(Math.max(1, Math.min(path.size() - 2, path.size() / 2)));
                int other = -1;
                for (int c = 0; c < total; c++) if (finalTypes[c] == RoomType.REST) { other = c; break; }
                if (finalTypes[mid] == RoomType.HALL) {
                    finalTypes[mid] = RoomType.REST;
                    finalTypes[other] = RoomType.HALL;
                    boolean[] used2 = new boolean[total];
                    for (int c = 0; c < total; c++) used2[c] = finalTypes[c] != null;
                    prune(finalTypes, used2, east, south, n, boss);
                    for (int c = 0; c < total; c++) if (!used2[c]) finalTypes[c] = null;
                } else {
                    finalTypes[other] = finalTypes[mid];
                    finalTypes[mid] = RoomType.REST;
                }
                plan = new MazePlan(n, finalTypes, east, south, start, boss);
            }
        }
        return plan;
    }

    private static void prune(RoomType[] types, boolean[] used, boolean[] east, boolean[] south, int n, int boss) {
        int total = n * n;
        boolean changed = true;
        while (changed) {
            changed = false;
            for (int c = 0; c < total; c++) {
                if (!used[c] || types[c] != RoomType.HALL || c == boss) continue;
                if (degree(used, east, south, n, c) <= 1) {
                    used[c] = false;
                    int x = c % n, z = c / n;
                    east[c] = false;
                    south[c] = false;
                    if (x > 0) east[c - 1] = false;
                    if (z > 0) south[c - n] = false;
                    changed = true;
                }
            }
        }
    }

    private static int degree(boolean[] used, boolean[] east, boolean[] south, int n, int c) {
        int x = c % n, z = c / n, d = 0;
        if (x < n - 1 && east[c] && used[c + 1]) d++;
        if (x > 0 && east[c - 1] && used[c - 1]) d++;
        if (z < n - 1 && south[c] && used[c + n]) d++;
        if (z > 0 && south[c - n] && used[c - n]) d++;
        return d;
    }

    private static void open(boolean[] east, boolean[] south, int n, int a, int b) {
        int lo = Math.min(a, b), hi = Math.max(a, b);
        if (hi - lo == 1) east[lo] = true;
        else south[lo] = true;
    }

    private static boolean adjacent(int n, int a, int b) {
        int ax = a % n, az = a / n, bx = b % n, bz = b / n;
        return Math.abs(ax - bx) + Math.abs(az - bz) == 1;
    }

    private static void shuffle(List<Integer> list, SplittableRandom rng) {
        for (int i = list.size() - 1; i > 0; i--) {
            int j = rng.nextInt(i + 1);
            Integer t = list.get(i);
            list.set(i, list.get(j));
            list.set(j, t);
        }
    }
}
