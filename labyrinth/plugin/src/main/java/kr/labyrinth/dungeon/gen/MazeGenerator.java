package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.content.Params;

/**
 * 시드 기반 미로 (순수 로직 — 단위 테스트 대상). GDD §5.4.
 * <ol>
 *   <li>n×n 셀 전체에 "자라는 나무"(growing tree) 신장 트리 — 깊이 우선(긴 구불길)에 {@code branch} 확률로 아무 칸에서나
 *       가지를 쳐 갈림길·막다른 길을 만든다. 모든 셀이 연결됨</li>
 *   <li>시작 = 첫 줄 중 마지막 줄까지 가장 먼 셀</li>
 *   <li>나무의 막다른 길 중 {@code dead_end_keep} 비율만 남기고 나머지는 이웃과 이어 고리로 만들거나(braid) 가지째 잘라 낸다</li>
 *   <li>남은 닫힌 벽의 {@code loop_chance} 비율을 뚫어 고리(돌아가는 다른 길)를 만든다 — 시작에서의 거리가 비슷한 두 길을 잇는
 *       벽부터. 바로 옆 칸끼리의 작은 고리, 남길 막다른 길, 주 경로를 {@code min_path} 아래로 줄이는 지름길은 뺀다</li>
 *   <li>보스 연결 = 마지막 줄 중 시작에서 BFS 로 가장 먼 셀</li>
 *   <li>방 배정 — 휴식방 1개는 주 경로 가운데쯤, 보물방은 곁길 우선, 나머지는 무작위. 막다른 길 끝은 되도록 복도로 둔다
 *       (보물 상자·함정·비밀 통로 자리)</li>
 *   <li>막다른 길 일부({@code secret_ratio})는 끝 벽이 금 간 벽 → 숨은 방 (비밀 통로)</li>
 *   <li>복도 셀마다 모양({@link HallStyle}) — 출구 수·방향과 {@code twist} 확률로 꺾인 복도·좁은 통로·광장·계단·기둥 숲</li>
 *   <li>주 경로(시작→보스 최단)가 격자 한 변의 {@code min_path}(기본 2.2)배보다 짧거나, 쓰는 셀이 70% 미만이거나, 고리가 없으면
 *       다른 시드 오프셋으로 다시</li>
 * </ol>
 */
public final class MazeGenerator {

    /** floors.yml {@code maze:} — 층별 미로 복잡도. 모르는 키는 기본값. */
    public record Settings(double deadEndKeep, double loopChance, double branch, double braid, double twist,
                           double secretRatio, int secretMax, double minPath) {
        public Settings {
            deadEndKeep = clamp01(deadEndKeep);
            loopChance = clamp01(loopChance);
            branch = clamp01(branch);
            braid = clamp01(braid);
            twist = clamp01(twist);
            secretRatio = clamp01(secretRatio);
            secretMax = Math.max(0, secretMax);
            minPath = Double.isNaN(minPath) ? 0 : Math.max(0, Math.min(4.0, minPath));
        }

        public static final Settings DEFAULT = new Settings(0.4, 0.22, 0.3, 0.5, 0.5, 0.3, 2, 2.2);

        public static Settings of(Params p) {
            if (p == null || p.isEmpty()) return DEFAULT;
            Settings d = DEFAULT;
            return new Settings(p.dbl("dead_end_keep", d.deadEndKeep), p.dbl("loop_chance", d.loopChance),
                    p.dbl("branch", d.branch), p.dbl("braid", d.braid), p.dbl("twist", d.twist),
                    p.dbl("secret_ratio", d.secretRatio), p.integer("secret_max", d.secretMax), p.dbl("min_path", d.minPath));
        }

        private static double clamp01(double v) { return Double.isNaN(v) ? 0 : Math.max(0, Math.min(1, v)); }
    }

    /** 방 종류 배정 우선순위 — 셀이 모자라면 뒤(전투방)부터 줄인다. */
    private static final RoomType[] ORDER = {RoomType.REST, RoomType.GIMMICK, RoomType.TREASURE, RoomType.ELITE, RoomType.COMBAT};

    /** 고리를 뚫을 때 두 셀 사이 기존 거리의 최소값 (이보다 가까우면 2×2 네모 고리라 재미없음). */
    static final int MIN_LOOP_SPAN = 5;
    static final int ATTEMPTS = 48;

    private MazeGenerator() {}

    /** 기본 설정(구 호출 호환). */
    public static MazePlan generate(int cells, long seed, Map<String, Integer> roomCounts) {
        return generate(cells, seed, roomCounts, Settings.DEFAULT);
    }

    public static MazePlan generate(int cells, long seed, Map<String, Integer> roomCounts, Settings s) {
        int n = Math.max(3, Math.min(16, cells));
        int need = (int) Math.ceil(s.minPath() * n);
        MazePlan best = null;
        double bestScore = -1;
        for (int attempt = 0; attempt < ATTEMPTS; attempt++) {
            MazePlan p = attempt(n, seed + attempt * 0x9E3779B97F4A7C15L, roomCounts, s, attempt);
            boolean longPath = p.mainPath().size() >= need;
            // 격자가 너무 비거나(70% 미만) 고리가 하나도 없으면 미로답지 않으니 다시
            boolean full = p.usedCount() >= Math.ceil(0.7 * n * n);
            boolean loops = p.loopCount() >= 1 || s.loopChance() <= 0;
            if (longPath && full && loops) return p;
            double score = (longPath ? 2 : 0) + (full ? 1 : 0) + (loops ? 1 : 0) + p.mainPath().size() / 1000.0;
            if (score > bestScore) {
                best = p;
                bestScore = score;
            }
        }
        return best;
    }

    private static MazePlan attempt(int n, long seed, Map<String, Integer> roomCounts, Settings s, int attempt) {
        SplittableRandom rng = new SplittableRandom(seed);
        int total = n * n;
        Graph g = new Graph(n);
        int start = rng.nextInt(n);                       // 나무 뿌리 (x, 0) — 실제 시작은 2단계에서 다시 고른다

        // 1. 자라는 나무
        boolean[] seen = new boolean[total];
        List<Integer> active = new ArrayList<>();
        active.add(start);
        seen[start] = true;
        int[] nb = new int[4];
        while (!active.isEmpty()) {
            int idx = rng.nextDouble() < s.branch() ? rng.nextInt(active.size()) : active.size() - 1;
            int c = active.get(idx);
            int k = 0;
            for (int d = 0; d < 4; d++) {
                int o = g.step(c, d);
                if (o >= 0 && !seen[o]) nb[k++] = o;
            }
            if (k == 0) {
                active.remove(idx);
                continue;
            }
            int next = nb[rng.nextInt(k)];
            g.open(c, next);
            seen[next] = true;
            active.add(next);
        }

        // 2. 시작 = 첫 줄 중 마지막 줄까지 가장 멀리 가는 셀 (주 경로를 길게)
        start = bestStart(g, rng);
        int need = (int) Math.ceil(s.minPath() * n);

        // 3. 막다른 길: dead_end_keep 비율만 남기고(남길 칸은 고리로도 건드리지 않음) 나머지는 이웃과 잇거나(braid) 가지째 잘라 냄
        List<Integer> dead = new ArrayList<>();
        int boss = farthestInLastRow(g, start, rng);
        for (int c = 0; c < total; c++) if (c != start && c != boss && g.degree(c) == 1) dead.add(c);
        int initialDeadEnds = dead.size();
        shuffle(dead, rng);
        int keepCount = (int) Math.round(dead.size() * s.deadEndKeep());
        Set<Integer> kept = new HashSet<>(dead.subList(0, keepCount));
        for (int i = keepCount; i < dead.size(); i++) {
            int c = dead.get(i);
            if (!g.used[c] || g.degree(c) != 1) continue;
            boolean tryBraid = rng.nextDouble() < s.braid();
            // 끝 칸부터 한 칸씩: 이웃과 이을 수 있으면(braid) 고리로, 아니면 잘라 내고 다음 칸에서 다시 — 긴 가지째 사라져
            // 격자가 텅 비지 않게 한다
            int cur = c;
            while (cur >= 0 && cur != start && cur != boss && !kept.contains(cur) && g.used[cur] && g.degree(cur) <= 1) {
                if ((tryBraid || cur != c) && braid(g, cur, kept, start, need, rng)) break;
                int only = -1;
                for (int o : g.neighbors(cur)) only = o;
                g.remove(cur);
                cur = only;
            }
        }

        // 4. 고리 — 남은 닫힌 벽의 loop_chance 비율. 바로 옆끼리의 작은 고리·남길 막다른 길·주 경로를 min_path 아래로 줄이는 지름길은 뺀다
        List<int[]> walls = new ArrayList<>();
        for (int c = 0; c < total; c++) {
            if (g.x(c) < n - 1 && !g.east[c] && g.used[c] && g.used[c + 1]) walls.add(new int[] {c, c + 1});
            if (g.z(c) < n - 1 && !g.south[c] && g.used[c] && g.used[c + n]) walls.add(new int[] {c, c + n});
        }
        shuffle(walls, rng);
        // 시작에서의 거리 차가 작은 벽부터 (나란한 두 길을 잇는 고리 — 주 경로를 줄이지 않고 갈림길만 만든다)
        int[] d0 = g.distances(start);
        List<int[]> keyed = new ArrayList<>();
        for (int[] w : walls) keyed.add(new int[] {w[0], w[1], Math.abs(d0[w[0]] - d0[w[1]]) + rng.nextInt(4)});
        keyed.sort((a, b) -> Integer.compare(a[2], b[2]));
        // 남은 벽의 loop_chance 비율만큼 뚫는다 (조건에 안 맞는 벽은 건너뛰고 다음 벽)
        int target = (int) Math.round(keyed.size() * s.loopChance());
        int opened = 0;
        for (int[] w : keyed) {
            if (opened >= target) break;
            if (kept.contains(w[0]) || kept.contains(w[1])) continue;
            int d = g.distance(w[0], w[1]);
            if (d < MIN_LOOP_SPAN) continue;
            g.open(w[0], w[1]);
            if (farthestDistance(g, start) + 1 < need) g.set(w[0], w[1], false);
            else opened++;
        }
        boss = farthestInLastRow(g, start, rng);

        // 5. 방 배정
        RoomType[] types = new RoomType[total];
        for (int c = 0; c < total; c++) types[c] = g.used[c] ? RoomType.HALL : null;
        types[start] = RoomType.START;
        List<Integer> path = g.path(start, boss);
        Set<Integer> onPath = new HashSet<>(path);
        Set<Integer> deadSet = new HashSet<>();
        for (int c = 0; c < total; c++) if (g.used[c] && c != start && c != boss && g.degree(c) == 1) deadSet.add(c);

        List<RoomType> wanted = new ArrayList<>();
        for (RoomType t : ORDER) {
            int cnt = Math.max(0, roomCounts.getOrDefault(t.key(), 0));
            for (int i = 0; i < cnt; i++) wanted.add(t);
        }
        int cap = g.usedCount() - 2;
        while (wanted.size() > cap) wanted.remove(wanted.size() - 1);

        Set<Integer> taken = new HashSet<>();
        taken.add(start);
        taken.add(boss);
        // 휴식방 하나: 주 경로 가운데 1/3 쯤 (GDD §5.2 — 주 경로 위 휴식방 최소 1개)
        if (wanted.contains(RoomType.REST) && path.size() > 2) {
            int lo = Math.max(1, path.size() / 3), hi = Math.max(lo, Math.min(path.size() - 2, (path.size() * 2) / 3));
            int at = path.get(lo + rng.nextInt(hi - lo + 1));
            types[at] = RoomType.REST;
            taken.add(at);
            wanted.remove(RoomType.REST);
        }
        List<Integer> free = new ArrayList<>();
        for (int c = 0; c < total; c++) if (g.used[c] && !taken.contains(c)) free.add(c);
        shuffle(free, rng);
        // 시작방 바로 옆·막다른 길 끝은 뒤로 (입장 직후 연속 전투 방지, 막다른 길은 상자·함정 자리)
        final int st = start;
        free.sort((a, b) -> Integer.compare(rank(g, a, st, deadSet), rank(g, b, st, deadSet)));
        for (RoomType t : wanted) {
            int pick = -1;
            if (t == RoomType.TREASURE) {
                // 보물방은 곁길 우선 — 둘러보는 보람
                for (int c : free) {
                    if (!onPath.contains(c) && !deadSet.contains(c)) {
                        pick = c;
                        break;
                    }
                }
            }
            if (pick < 0 && !free.isEmpty()) pick = free.get(0);
            if (pick < 0) break;
            free.remove((Integer) pick);
            types[pick] = t;
        }

        MazePlan tmp = new MazePlan(n, types, g.east, g.south, start, boss, null, null, seed, initialDeadEnds, attempt);
        // 6. 비밀 통로 — 남은 막다른 복도 끝
        List<Integer> deadHalls = tmp.deadEnds();
        boolean[] secret = new boolean[total];
        if (!deadHalls.isEmpty() && s.secretMax() > 0 && s.secretRatio() > 0) {
            int want = Math.min(s.secretMax(), Math.max(1, (int) Math.round(deadHalls.size() * s.secretRatio())));
            List<Integer> cand = new ArrayList<>(deadHalls);
            shuffle(cand, rng);
            for (int i = 0; i < want && i < cand.size(); i++) secret[cand.get(i)] = true;
        }
        // 7. 복도 모양
        HallStyle[] styles = new HallStyle[total];
        for (int c = 0; c < total; c++) {
            if (types[c] != RoomType.HALL) continue;
            styles[c] = style(tmp, c, secret[c], s.twist(), rng);
        }
        return new MazePlan(n, types, g.east, g.south, start, boss, styles, secret, seed, initialDeadEnds, attempt);
    }

    private static int rank(Graph g, int c, int start, Set<Integer> dead) {
        int r = 0;
        if (dead.contains(c)) r += 2;
        if (g.connected(c, start)) r += 1;
        return r;
    }

    /** 막다른 길 c 를 이웃과 이어 고리로 (남기기로 한 막다른 길과는 잇지 않음, 주 경로가 need 아래로 줄면 취소). */
    private static boolean braid(Graph g, int c, Set<Integer> kept, int start, int need, SplittableRandom rng) {
        List<Integer> cand = new ArrayList<>();
        for (int d = 0; d < 4; d++) {
            int o = g.step(c, d);
            if (o < 0 || !g.used[o] || g.connected(c, o) || kept.contains(o)) continue;
            if (g.distance(c, o) < MIN_LOOP_SPAN - 1) continue;
            cand.add(o);
        }
        shuffle(cand, rng);
        for (int o : cand) {
            g.open(c, o);
            if (farthestDistance(g, start) + 1 >= need) return true;
            g.set(c, o, false);
        }
        return false;
    }

    /** 첫 줄 셀 중 마지막 줄까지 BFS 거리가 가장 먼 셀. */
    private static int bestStart(Graph g, SplittableRandom rng) {
        int best = 0, bestD = -1;
        for (int x = 0; x < g.n; x++) {
            int d = farthestDistance(g, x);
            if (d > bestD || (d == bestD && rng.nextBoolean())) {
                best = x;
                bestD = d;
            }
        }
        return best;
    }

    /** from 에서 마지막 줄 사용 셀까지 BFS 거리 최댓값. */
    private static int farthestDistance(Graph g, int from) {
        int n = g.n;
        int[] dist = g.distances(from);
        int best = -1;
        for (int x = 0; x < n; x++) best = Math.max(best, dist[(n - 1) * n + x]);
        return best;
    }

    private static int farthestInLastRow(Graph g, int start, SplittableRandom rng) {
        int n = g.n;
        int[] dist = g.distances(start);
        int best = -1, bestD = -1;
        for (int x = 0; x < n; x++) {
            int c = (n - 1) * n + x;
            if (!g.used[c] || dist[c] < 0) continue;
            if (dist[c] > bestD || (dist[c] == bestD && rng.nextBoolean())) {
                best = c;
                bestD = dist[c];
            }
        }
        return best < 0 ? (n - 1) * n + rng.nextInt(n) : best;
    }

    /** 출구 방향·수에 맞는 복도 모양. */
    private static HallStyle style(MazePlan plan, int c, boolean secret, double twist, SplittableRandom rng) {
        int exits = plan.exits(c);
        int deg = Integer.bitCount(exits);
        if (deg <= 1) return secret ? HallStyle.SECRET : HallStyle.NOOK;
        boolean twisted = rng.nextDouble() < twist;
        if (deg == 2) {
            boolean straight = exits == 0b0101 || exits == 0b1010;
            if (!twisted) return HallStyle.CROSS;
            if (straight) return pick(rng, new HallStyle[] {HallStyle.BENT, HallStyle.STAIRS, HallStyle.NARROW, HallStyle.PILLARS,
                    HallStyle.WARREN}, new int[] {25, 24, 13, 13, 25});
            return pick(rng, new HallStyle[] {HallStyle.BENT, HallStyle.NARROW, HallStyle.PILLARS, HallStyle.WARREN},
                    new int[] {45, 15, 13, 27});
        }
        if (!twisted && rng.nextDouble() > 0.3) return HallStyle.CROSS;
        return pick(rng, new HallStyle[] {HallStyle.PLAZA, HallStyle.PILLARS, HallStyle.WARREN}, new int[] {45, 22, 33});
    }

    private static HallStyle pick(SplittableRandom rng, HallStyle[] opts, int[] weights) {
        int sum = 0;
        for (int w : weights) sum += w;
        int r = rng.nextInt(sum);
        for (int i = 0; i < opts.length; i++) {
            r -= weights[i];
            if (r < 0) return opts[i];
        }
        return opts[opts.length - 1];
    }

    private static <T> void shuffle(List<T> list, SplittableRandom rng) {
        for (int i = list.size() - 1; i > 0; i--) {
            int j = rng.nextInt(i + 1);
            T t = list.get(i);
            list.set(i, list.get(j));
            list.set(j, t);
        }
    }

    /** 생성 중 가변 격자 그래프. 방향 d: 0=북(−z) 1=동(+x) 2=남(+z) 3=서(−x). */
    private static final class Graph {
        final int n;
        final boolean[] east, south, used;

        Graph(int n) {
            this.n = n;
            east = new boolean[n * n];
            south = new boolean[n * n];
            used = new boolean[n * n];
            Arrays.fill(used, true);
        }

        int x(int c) { return c % n; }
        int z(int c) { return c / n; }

        int step(int c, int d) {
            int x = x(c), z = z(c);
            return switch (d) {
                case 0 -> z > 0 ? c - n : -1;
                case 1 -> x < n - 1 ? c + 1 : -1;
                case 2 -> z < n - 1 ? c + n : -1;
                default -> x > 0 ? c - 1 : -1;
            };
        }

        void open(int a, int b) { set(a, b, true); }

        void set(int a, int b, boolean v) {
            int lo = Math.min(a, b), hi = Math.max(a, b);
            if (hi - lo == 1) east[lo] = v;
            else south[lo] = v;
        }

        boolean connected(int a, int b) {
            if (a == b || !used[a] || !used[b]) return false;
            int lo = Math.min(a, b), hi = Math.max(a, b);
            if (hi - lo == 1 && x(hi) == x(lo) + 1) return east[lo];
            if (hi - lo == n) return south[lo];
            return false;
        }

        List<Integer> neighbors(int c) {
            List<Integer> out = new ArrayList<>(4);
            if (!used[c]) return out;
            for (int d = 0; d < 4; d++) {
                int o = step(c, d);
                if (o >= 0 && connected(c, o)) out.add(o);
            }
            return out;
        }

        int degree(int c) { return neighbors(c).size(); }

        void remove(int c) {
            for (int d = 0; d < 4; d++) {
                int o = step(c, d);
                if (o >= 0) set(c, o, false);
            }
            used[c] = false;
        }

        int usedCount() {
            int k = 0;
            for (boolean u : used) if (u) k++;
            return k;
        }

        int[] distances(int from) {
            int[] dist = new int[n * n];
            Arrays.fill(dist, -1);
            ArrayDeque<Integer> q = new ArrayDeque<>();
            q.add(from);
            dist[from] = 0;
            while (!q.isEmpty()) {
                int c = q.poll();
                for (int o : neighbors(c)) {
                    if (dist[o] < 0) {
                        dist[o] = dist[c] + 1;
                        q.add(o);
                    }
                }
            }
            return dist;
        }

        int distance(int a, int b) {
            int d = distances(a)[b];
            return d < 0 ? Integer.MAX_VALUE : d;
        }

        List<Integer> path(int from, int to) {
            int[] prev = new int[n * n];
            Arrays.fill(prev, -2);
            ArrayDeque<Integer> q = new ArrayDeque<>();
            q.add(from);
            prev[from] = -1;
            while (!q.isEmpty()) {
                int c = q.poll();
                if (c == to) break;
                for (int o : neighbors(c)) {
                    if (prev[o] == -2) {
                        prev[o] = c;
                        q.add(o);
                    }
                }
            }
            List<Integer> out = new ArrayList<>();
            if (prev[to] == -2) return out;
            for (int c = to; c != -1; c = prev[c]) out.add(0, c);
            return out;
        }
    }
}
