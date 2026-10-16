package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BooleanSupplier;

/**
 * 마을 계획기 (VILLAGE.md §0 지형 존중 규칙 · §4.1). 순수 로직 — 지형은 {@link Terrain} 으로만 본다.
 * survey(자리 고르기)와 build(짓기)가 같은 계획기를 쓴다.
 * <ol>
 *   <li>영역(R+B) 안 물·용암·얼음, 사람이 지은 블록/구조물 → 그 자리 탈락.</li>
 *   <li>조각마다 slack 칸 안에서 위치를 옮겨 보며 단 높이 P(정문 쪽 원래 높이를 가장 무겁게 본 중앙값, 광장 H0 ±6)와
 *       깎기·메우기 양을 계산 → 한 칸이라도 4칸 넘게 깎거나 메우면 그 위치 탈락, 발자국 아래 6칸 동굴이 1/3 넘으면 탈락.
 *       남은 위치 중 변화가 적은 순서로, 다른 조각과 1칸 여유 · (붙지 않은) 길과 1칸 여유를 지키는 첫 위치를 고른다.
 *       장식 조각은 맞는 위치가 하나도 없으면 그 장식만 빼고(skipped) 계속한다 — 건물은 하나라도 없으면 그 자리 탈락.</li>
 *   <li>조각에 붙은 길 끝은 조각을 따라 옮긴다. 길 높이는 양 끝 단 사이를 잇되 지형을 ±2 안에서 따라가고, 이웃 차 ≤ 1.</li>
 *   <li>full 이면 목표 높이장({@link HeightField})까지 계산해 실제 깎기·메우기 총량을 낸다.</li>
 * </ol>
 */
public final class Planner {

    public enum Fail { NONE, RANGE, WATER, STRUCTURE, CAVE, LIMIT, OVERLAP, PATH, LAYOUT }

    public static final int H0_RADIUS = 6;
    public static final int DY_CLAMP = 6;
    public static final int PAD_LIMIT = 4;
    public static final int CAVE_DEPTH = 6;
    public static final int SLACK = 2;
    public static final int SLACK_DECO = 3;
    /** 길 끝이 조각 발자국에서 이 거리(체비셰프) 안이면 그 조각에 붙은 길. */
    public static final int ATTACH = 2;
    /** 길 높이가 직선 보간에서 지형을 따라 벗어날 수 있는 한도. */
    public static final int PATH_FOLLOW = 2;

    public static String label(Fail f) {
        return switch (f) {
            case NONE -> "통과";
            case RANGE -> "조사 범위 밖";
            case WATER -> "물·용암·얼음";
            case STRUCTURE -> "구조물·사람이 지은 블록";
            case CAVE -> "동굴";
            case LIMIT -> "깎기/메우기 한도 초과";
            case OVERLAP -> "겹침(자리 없음)";
            case PATH -> "길 경사";
            case LAYOUT -> "배치 오류";
        };
    }

    /**
     * 마스크 모드 (0.3.6 구역, CONTRACT §2.13): 원 대신 조각·길 상자 + R = 다듬는 칸, + B 더 = 섞는 띠. 얼린 칸은 높이·지형을
     * 바꾸지 않는다 (고정 = 원래 높이, 조각·여유 칸·정문 앞 칸이 올 수 없음, 구역 길은 겉 블록만 · 마을 길·보호 상자 칸은 건너뜀).
     * maxFill = 깎기·메우기 한도 (마을 PAD_LIMIT), foundationDepth = 발자국 아래 동굴 검사·기초 깊이 (마을 CAVE_DEPTH),
     * smallWater = 그 수까지의 물 칸은 막지 않고 메움 (0 = 물이 있으면 그 자리 탈락, 마을과 같음).
     */
    public record Mask(int r, int b, FrozenCells frozen, int maxFill, int foundationDepth, int smallWater) {
        public Mask {
            if (frozen == null) frozen = FrozenCells.empty();
            r = Math.max(1, r);
            b = Math.max(1, b);
            maxFill = Math.max(1, maxFill);
            foundationDepth = Math.max(1, Math.min(16, foundationDepth));
            smallWater = Math.max(0, smallWater);
        }
    }

    private final Layout layout;
    private final Blueprint[] bps;
    /** 안쪽 반경 R (layout radius, 조각이 그보다 멀면 그만큼 넓힘). 마스크 모드 = 조각·길이 닿는 체비셰프 거리. */
    public final int inner;
    public final int blend;
    /** null = 마을(원). */
    public final Mask mask;

    public Planner(Layout layout, Map<String, Blueprint> blueprints) { this(layout, blueprints, null); }

    public Planner(Layout layout, Map<String, Blueprint> blueprints, Mask mask) {
        this.layout = layout;
        this.mask = mask;
        this.bps = new Blueprint[layout.pieces.size()];
        if (layout.paths.size() > 64) throw new IllegalArgumentException("길은 64개까지");
        double far = 0;
        for (Layout.Entry e : layout.pieces) {
            Blueprint bp = blueprints.get(e.piece());
            if (bp == null) throw new IllegalArgumentException("layout 의 조각 '" + e.piece() + "' 청사진 없음");
            bps[e.index()] = bp;
            int[] vd = Rot.dims(bp.w, bp.d, e.front().turns());
            int s = slackOf(e, bp);
            double ex = Math.max(Math.abs(e.atX() - vd[0] / 2), Math.abs(e.atX() - vd[0] / 2 + vd[0] - 1)) + s + 1;
            double ez = Math.max(Math.abs(e.atZ() - vd[1] / 2), Math.abs(e.atZ() - vd[1] / 2 + vd[1] - 1)) + s + 1;
            far = Math.max(far, Math.hypot(ex, ez));
        }
        for (Layout.PathDef p : layout.paths) for (int[] q : p.points()) far = Math.max(far, Math.hypot(q[0], q[1]) + p.width());
        if (mask == null) {
            this.inner = Math.max(layout.radius, (int) Math.ceil(far));
            this.blend = layout.blend;
        } else {
            int cheb = 0;
            for (Layout.Entry e : layout.pieces) {
                Blueprint bp = bps[e.index()];
                int[] vd = Rot.dims(bp.w, bp.d, e.front().turns());
                int s = slackOf(e, bp);
                int x0 = e.atX() - vd[0] / 2, z0 = e.atZ() - vd[1] / 2;
                cheb = Math.max(cheb, Math.max(Math.max(Math.abs(x0 - s), Math.abs(x0 + vd[0] - 1 + s)),
                        Math.max(Math.abs(z0 - s), Math.abs(z0 + vd[1] - 1 + s))) + 1);
            }
            for (Layout.PathDef p : layout.paths) for (int[] q : p.points()) {
                cheb = Math.max(cheb, Math.max(Math.abs(q[0]), Math.abs(q[1])) + p.width() / 2 + 2);
            }
            this.inner = cheb + mask.r();
            this.blend = mask.b();
        }
    }

    private int padLimit() { return mask == null ? PAD_LIMIT : mask.maxFill(); }

    int caveDepth() { return mask == null ? CAVE_DEPTH : mask.foundationDepth(); }

    public Layout layout() { return layout; }

    public Blueprint blueprint(int entryIndex) { return bps[entryIndex]; }

    /** 계획에 필요한 지형 반경 R + B. */
    public int reach() { return inner + blend; }

    /** 조사(스냅샷) 반경: R + B + 이웃 칸 1 + 나무가 띠 밖으로 뻗은 부분. */
    public int scanReach() { return reach() + 14; }

    public static int slackOf(Layout.Entry e, Blueprint bp) {
        if (e.slack() != null) return Math.max(0, e.slack());
        if (bp.slack != null) return Math.max(0, bp.slack);
        return bp.deco ? SLACK_DECO : SLACK;
    }

    // ── 자리별 지형 묶음 (회전 4방향이 같이 씀) ─────────────────────────────

    /** 한 중심 자리의 영역 격자 + 위험 검사 결과. */
    public static final class Ctx {
        public final int cx, cz, reach, gn, gx0, gz0;
        final int[] ground, holes, flags;
        /** 마스크 모드: 조각(slack 포함)·길 칸까지 거리 (원 모드 = null) · 얼린 칸. */
        double[] dist0;
        boolean[] frozen;
        Fail fail = Fail.NONE;
        String reason = "";
        int h0, logs;
        String biome = "?";

        Ctx(int cx, int cz, int reach) {
            this.cx = cx;
            this.cz = cz;
            this.reach = reach;
            this.gn = 2 * reach + 3; // 영역 + 이웃 한 칸
            this.gx0 = cx - reach - 1;
            this.gz0 = cz - reach - 1;
            int n = gn * gn;
            ground = new int[n];
            holes = new int[n];
            flags = new int[n];
        }

        boolean in(int x, int z) {
            int lx = x - gx0, lz = z - gz0;
            return lx >= 0 && lz >= 0 && lx < gn && lz < gn;
        }

        int idx(int x, int z) { return (z - gz0) * gn + (x - gx0); }

        int g(int x, int z) { return ground[idx(x, z)]; }

        boolean frozenAt(int x, int z) { return frozen != null && in(x, z) && frozen[idx(x, z)]; }

        public Fail fail() { return fail; }

        public String reason() { return reason; }
    }

    public Ctx context(Terrain t, int cx, int cz) {
        if (mask != null) return maskContext(t, cx, cz);
        int reach = reach();
        Ctx c = new Ctx(cx, cz, reach);
        double bestWater = Double.MAX_VALUE, bestStruct = Double.MAX_VALUE;
        String waterWhy = null, structWhy = null;
        List<Integer> h0s = new ArrayList<>();
        for (int lz = 0; lz < c.gn; lz++) {
            for (int lx = 0; lx < c.gn; lx++) {
                int x = c.gx0 + lx, z = c.gz0 + lz, i = lz * c.gn + lx;
                double d = Math.hypot(x - cx, z - cz);
                if (!t.has(x, z)) {
                    if (d <= reach + 1) {
                        c.fail = Fail.RANGE;
                        c.reason = "지형 조사 범위 밖 (" + x + ", " + z + ")";
                        return c;
                    }
                    continue;
                }
                c.ground[i] = t.ground(x, z);
                c.holes[i] = t.holes(x, z);
                c.flags[i] = t.flags(x, z);
                if (d > reach) continue;
                if ((c.flags[i] & Terrain.WATER) != 0 && d < bestWater) {
                    bestWater = d;
                    waterWhy = (t.note(x, z) == null ? "물" : t.note(x, z)) + " (" + x + ", " + z + ")";
                }
                if ((c.flags[i] & Terrain.UNNATURAL) != 0 && d < bestStruct) {
                    bestStruct = d;
                    structWhy = (t.note(x, z) == null ? "비자연 블록" : t.note(x, z)) + " (" + x + ", " + z + ")";
                }
                c.logs += t.logs(x, z);
                if (d <= H0_RADIUS) h0s.add(c.ground[i]);
            }
        }
        c.biome = t.biome(cx, cz);
        h0s.sort(null);
        c.h0 = h0s.isEmpty() ? 64 : h0s.get(h0s.size() / 2);
        if (structWhy != null) {
            c.fail = Fail.STRUCTURE;
            c.reason = "마을 영역(R+B=" + reach + ") 안에 " + structWhy;
        } else if (waterWhy != null) {
            c.fail = Fail.WATER;
            c.reason = "마을 영역(R+B=" + reach + ") 안에 " + waterWhy;
        }
        return c;
    }


    /** 조각 기준 자리(slack 만큼 넓힘)·길 칸 (중심 기준 상대 좌표 → 월드). 마스크 모드 영역의 씨앗. */
    private List<int[]> coreCells(int cx, int cz) {
        List<int[]> out = new ArrayList<>();
        for (Layout.Entry e : layout.pieces) {
            Blueprint bp = bps[e.index()];
            int[] vd = Rot.dims(bp.w, bp.d, e.front().turns());
            int s = slackOf(e, bp);
            int x0 = e.atX() - vd[0] / 2, z0 = e.atZ() - vd[1] / 2;
            for (int z = z0 - s; z < z0 + vd[1] + s; z++) for (int x = x0 - s; x < x0 + vd[0] + s; x++) out.add(new int[] {cx + x, cz + z});
        }
        for (Layout.PathDef p : layout.paths) {
            List<int[]> pts = new ArrayList<>();
            for (int[] q : p.points()) pts.add(new int[] {cx + q[0], cz + q[1]});
            for (PathRaster.Cell c : PathRaster.cells(pts, p.width())) out.add(new int[] {c.x(), c.z()});
        }
        return out;
    }

    /** 격자 칸마다 seeds 까지 유클리드 거리 (cap 넘으면 cap + 1). */
    static double[] distanceField(int gx0, int gz0, int gn, List<int[]> seeds, int cap) {
        double[] d = new double[gn * gn];
        java.util.Arrays.fill(d, cap + 1);
        for (int[] s : seeds) {
            int lx = s[0] - gx0, lz = s[1] - gz0;
            for (int dz = -cap; dz <= cap; dz++) {
                int z = lz + dz;
                if (z < 0 || z >= gn) continue;
                for (int dx = -cap; dx <= cap; dx++) {
                    int x = lx + dx;
                    if (x < 0 || x >= gn) continue;
                    double v = Math.hypot(dx, dz);
                    int i = z * gn + x;
                    if (v < d[i]) d[i] = v;
                }
            }
        }
        return d;
    }

    /**
     * 마스크 모드 지형 묶음: 영역 = 조각(slack 포함)·길 칸에서 R+B 안. 그 안에 지형이 없으면 RANGE, 얼리지 않은 칸의 물·비자연 블록은
     * WATER·STRUCTURE (작은 물은 smallWater 칸까지 봐줌), 기준 높이 H0 = 조각 자리 땅 높이의 가운데 값.
     */
    private Ctx maskContext(Terrain t, int cx, int cz) {
        int reach = reach();
        Ctx c = new Ctx(cx, cz, reach);
        int n = c.gn * c.gn;
        List<int[]> core = coreCells(cx, cz);
        c.dist0 = distanceField(c.gx0, c.gz0, c.gn, core, mask.r() + mask.b() + 1);
        c.frozen = new boolean[n];
        String waterWhy = null, structWhy = null;
        int water = 0;
        List<Integer> h0s = new ArrayList<>();
        java.util.Set<Long> coreSet = new java.util.HashSet<>();
        for (int[] q : core) coreSet.add(PathRaster.key(q[0], q[1]));
        for (int lz = 0; lz < c.gn; lz++) {
            for (int lx = 0; lx < c.gn; lx++) {
                int x = c.gx0 + lx, z = c.gz0 + lz, i = lz * c.gn + lx;
                c.frozen[i] = mask.frozen().frozen(x, z);
                if (!t.has(x, z)) {
                    if (c.dist0[i] <= mask.r() + mask.b() + 1) {
                        c.fail = Fail.RANGE;
                        c.reason = "지형 조사 범위 밖 (" + x + ", " + z + ")";
                        return c;
                    }
                    continue;
                }
                c.ground[i] = t.ground(x, z);
                c.holes[i] = t.holes(x, z);
                c.flags[i] = t.flags(x, z);
                if (c.dist0[i] > mask.r() + mask.b() || c.frozen[i]) continue;
                if ((c.flags[i] & Terrain.WATER) != 0) {
                    water++;
                    if (waterWhy == null) waterWhy = (t.note(x, z) == null ? "물" : t.note(x, z)) + " (" + x + ", " + z + ")";
                }
                if ((c.flags[i] & Terrain.UNNATURAL) != 0 && structWhy == null) {
                    structWhy = (t.note(x, z) == null ? "비자연 블록" : t.note(x, z)) + " (" + x + ", " + z + ")";
                }
                c.logs += t.logs(x, z);
                if (coreSet.contains(PathRaster.key(x, z))) h0s.add(c.ground[i]);
            }
        }
        c.biome = t.biome(cx, cz);
        h0s.sort(null);
        c.h0 = h0s.isEmpty() ? 64 : h0s.get(h0s.size() / 2);
        if (structWhy != null) {
            c.fail = Fail.STRUCTURE;
            c.reason = "구역 영역(조각·길 + " + (mask.r() + mask.b()) + "칸) 안에 " + structWhy;
        } else if (waterWhy != null && water > mask.smallWater()) {
            c.fail = Fail.WATER;
            c.reason = "구역 영역(조각·길 + " + (mask.r() + mask.b()) + "칸) 안에 " + waterWhy + (water > 1 ? " 외 " + (water - 1) + "칸" : "");
        }
        return c;
    }

    public Plan plan(Terrain t, int cx, int cz, int turns, boolean full) {
        return plan(context(t, cx, cz), turns, full);
    }

    // ── 계획 ─────────────────────────────────────────────────────────────

    /** 조각별 계산용 상대 칸 목록 (회전 후 상자 기준). */
    private static final class Shape {
        int[] occ;     // (rz << 16 | rx) 대신 쌍 배열: occ[2k], occ[2k+1]
        int[] margin;
        int[] weight;  // occ 칸 가중치 (정문 쪽 무겁게)
        int ax, az;    // anchor 상대
        int fx, fz;    // 정문 앞 상대
    }

    private static Shape shape(Plan.Placed pl) {
        Shape s = new Shape();
        List<Integer> occ = new ArrayList<>(), margin = new ArrayList<>();
        int[] a = Rot.inBox(pl.bp.anchorX, pl.bp.anchorZ, pl.bp.w, pl.bp.d, pl.turns);
        int[] f = Rot.inBox(pl.bp.anchorX, Plan.Placed.doorZ(pl.bp), pl.bp.w, pl.bp.d, pl.turns);
        s.ax = a[0];
        s.az = a[1];
        s.fx = f[0];
        s.fz = f[1];
        List<Integer> wts = new ArrayList<>();
        for (int rz = -1; rz <= pl.d2; rz++) {
            for (int rx = -1; rx <= pl.w2; rx++) {
                boolean in = rx >= 0 && rz >= 0 && rx < pl.w2 && rz < pl.d2 && pl.occ[rz * pl.w2 + rx];
                if (in) {
                    occ.add(rx);
                    occ.add(rz);
                    int cheb = Math.max(Math.abs(rx - s.ax), Math.abs(rz - s.az));
                    wts.add(cheb <= 1 ? 4 : cheb <= 3 ? 2 : 1);
                    continue;
                }
                boolean near = false;
                for (int dz = -1; dz <= 1 && !near; dz++) {
                    for (int dx = -1; dx <= 1 && !near; dx++) {
                        int qx = rx + dx, qz = rz + dz;
                        near = qx >= 0 && qz >= 0 && qx < pl.w2 && qz < pl.d2 && pl.occ[qz * pl.w2 + qx];
                    }
                }
                if (near || (rx == s.fx && rz == s.fz)) {
                    margin.add(rx);
                    margin.add(rz);
                }
            }
        }
        s.occ = occ.stream().mapToInt(Integer::intValue).toArray();
        s.margin = margin.stream().mapToInt(Integer::intValue).toArray();
        s.weight = wts.stream().mapToInt(Integer::intValue).toArray();
        return s;
    }

    /** 한 위치(오프셋)의 평가. */
    private record Option(int dx, int dz, int floor, double cost, int caveVol, Fail fail, String why) {}

    public Plan plan(Ctx c, int turns, boolean full) {
        Plan p = new Plan(c.cx, c.cz, turns);
        p.inner = inner;
        p.blend = blend;
        p.h0 = c.h0;
        p.logs = c.logs;
        p.biome = c.biome;
        p.gx0 = c.gx0;
        p.gz0 = c.gz0;
        p.gn = c.gn;
        p.ground = c.ground;
        p.caveDepth = caveDepth();
        if (mask != null) {
            p.frozen = c.frozen;
            p.maskR = mask.r();
            p.maskB = mask.b();
        }
        if (c.fail != Fail.NONE) {
            p.fail = c.fail;
            p.reason = c.reason;
            return p;
        }
        int tr = Math.floorMod(turns, 4);
        // 1. 기준 자리 (layout 위치, 회전 적용)
        Shape[] shapes = new Shape[bps.length];
        for (Layout.Entry e : layout.pieces) {
            Blueprint bp = bps[e.index()];
            int pt = e.front().turns();
            int[] vd = Rot.dims(bp.w, bp.d, pt);
            int vx0 = e.atX() - vd[0] / 2, vz0 = e.atZ() - vd[1] / 2;
            int[] a = Rot.around(vx0, vz0, tr), b = Rot.around(vx0 + vd[0] - 1, vz0 + vd[1] - 1, tr);
            Plan.Placed pl = new Plan.Placed(e, bp, pt + tr, c.cx + Math.min(a[0], b[0]), c.cz + Math.min(a[1], b[1]));
            p.pieces.add(pl);
            shapes[e.index()] = shape(pl);
        }
        for (Layout.PathDef def : layout.paths) {
            List<int[]> pts = new ArrayList<>();
            for (int[] q : def.points()) {
                int[] r = Rot.around(q[0], q[1], tr);
                pts.add(new int[] {c.cx + r[0], c.cz + r[1]});
            }
            Plan.PathPlan pp = new Plan.PathPlan(def, pts);
            pp.attachA = attach(p.pieces, pts.get(0));
            pp.attachB = attach(p.pieces, pts.get(pts.size() - 1));
            p.paths.add(pp);
        }
        // 2. 조각 하나씩 (layout 순서) slack 안에서 자리 고르기
        int[] own = new int[c.gn * c.gn];
        Arrays.fill(own, -1);
        int[] doorOwn = new int[c.gn * c.gn];
        Arrays.fill(doorOwn, -1);
        long[] pathMask = new long[c.gn * c.gn];
        List<List<PathRaster.Cell>> raw = new ArrayList<>();
        for (Plan.PathPlan pp : p.paths) {
            List<PathRaster.Cell> cells = PathRaster.cells(pp.points, pp.def.width());
            raw.add(cells);
            mark(c, pathMask, cells, pp.def.index(), true);
        }
        long cave = 0;
        boolean[] placed = new boolean[bps.length];
        List<Plan.Placed> dropped = new ArrayList<>();
        for (Plan.Placed pl : p.pieces) {
            Shape s = shapes[pl.index()];
            int slack = slackOf(pl.entry, pl.bp);
            List<Option> options = new ArrayList<>();
            Option zero = null;
            for (int dz = -slack; dz <= slack; dz++) {
                for (int dx = -slack; dx <= slack; dx++) {
                    Option o = evaluate(c, p, placed, pl, s, dx, dz);
                    if (dx == 0 && dz == 0) zero = o;
                    if (o.fail() == Fail.NONE) options.add(o);
                }
            }
            options.sort((x, y) -> Double.compare(x.cost() + 0.3 * (Math.abs(x.dx()) + Math.abs(x.dz())),
                    y.cost() + 0.3 * (Math.abs(y.dx()) + Math.abs(y.dz()))));
            Option chosen = null;
            for (Option o : options) {
                if (clear(c, p, pl, s, o.dx(), o.dz(), own, doorOwn, pathMask)) {
                    chosen = o;
                    break;
                }
            }
            if (chosen == null && pl.bp.deco) {
                // 장식은 지형에 안 맞거나(한도·동굴) 자리가 없으면 억지로 끼우지 않고 그 장식만 뺀다 (§0)
                p.skipped.add(pl.bp.id + "#" + pl.index() + " (" + (options.isEmpty() ? Planner.label(zero.fail()) : Planner.label(Fail.OVERLAP)) + ")");
                for (Plan.PathPlan pp : p.paths) {
                    if (pp.attachA == pl.index()) pp.attachA = -1;
                    if (pp.attachB == pl.index()) pp.attachB = -1;
                }
                dropped.add(pl);
                continue;
            }
            if (chosen == null) {
                if (options.isEmpty()) {
                    p.fail = zero.fail();
                    p.reason = zero.why();
                } else {
                    p.fail = Fail.OVERLAP;
                    p.reason = pl.bp.id + ": slack " + slack + "칸 안에 다른 조각·길과 1칸 여유를 지키는 자리가 없음";
                }
                return p;
            }
            pl.dx = chosen.dx();
            pl.dz = chosen.dz();
            pl.x0 += chosen.dx();
            pl.z0 += chosen.dz();
            pl.floor = chosen.floor();
            placed[pl.index()] = true;
            cave += chosen.caveVol();
            for (int k = 0; k < s.occ.length; k += 2) own[c.idx(pl.x0 + s.occ[k], pl.z0 + s.occ[k + 1])] = pl.index();
            if (pl.bp.door) doorOwn[c.idx(pl.x0 + s.fx, pl.z0 + s.fz)] = pl.index();
            for (Plan.PathPlan pp : p.paths) {
                if (!pp.attached(pl.index()) || (chosen.dx() == 0 && chosen.dz() == 0)) continue;
                moveEnds(pp, pl.index(), chosen.dx(), chosen.dz());
                mark(c, pathMask, raw.get(pp.def.index()), pp.def.index(), false);
                List<PathRaster.Cell> cells = PathRaster.cells(pp.points, pp.def.width());
                raw.set(pp.def.index(), cells);
                mark(c, pathMask, cells, pp.def.index(), true);
            }
        }
        p.caveFill = cave;
        p.pieces.removeAll(dropped);
        // 3. 짓기 전 겹침 최종 검사 (모든 쌍)
        List<String> ov = overlaps(p.pieces, p.paths);
        if (!ov.isEmpty()) {
            p.fail = Fail.OVERLAP;
            p.reason = ov.get(0) + (ov.size() > 1 ? " 외 " + (ov.size() - 1) + "건" : "");
            return p;
        }
        // 4. 길 높이
        int[] pathH = new int[c.gn * c.gn];
        Arrays.fill(pathH, HeightField.NONE);
        for (Plan.PathPlan pp : p.paths) pathHeights(c, p, pp, raw.get(pp.def.index()), pathH);
        if (mask != null) {
            String why = frozenPaths(c, p, pathH);
            if (why != null) {
                p.fail = Fail.PATH;
                p.reason = why;
                return p;
            }
        }
        int steep = 0;
        for (Plan.PathPlan pp : p.paths) {
            for (int[] cell : pp.cells) {
                for (int[] d : new int[][] {{1, 0}, {0, 1}}) {
                    int nx = cell[0] + d[0], nz = cell[1] + d[1];
                    if (!c.in(nx, nz)) continue;
                    int h = pathH[c.idx(nx, nz)];
                    if (h != HeightField.NONE && Math.abs(h - cell[2]) > 1) steep++;
                }
            }
        }
        p.steepPaths = steep;
        if (steep > 0) {
            p.fail = Fail.PATH;
            p.reason = "길 높이 차가 1 을 넘는 칸 " + steep + "곳 (양 끝 단 높이 차가 길 길이보다 큼)";
            return p;
        }
        // 5. 고정 높이 격자
        int n = c.gn * c.gn;
        int[] fixedH = new int[n];
        byte[] src = new byte[n];
        Arrays.fill(fixedH, HeightField.NONE);
        if (mask != null) {
            for (int i = 0; i < n; i++) {
                if (!c.frozen[i] || c.dist0[i] > mask.r() + mask.b() + 1) continue;
                fixedH[i] = c.ground[i];
                src[i] = 6;
            }
        }
        for (Layout.Terrace tc : layout.terraces) {
            int vx0 = tc.atX() - tc.w() / 2, vz0 = tc.atZ() - tc.d() / 2;
            for (int vz = vz0; vz < vz0 + tc.d(); vz++) {
                for (int vx = vx0; vx < vx0 + tc.w(); vx++) {
                    int[] r = Rot.around(vx, vz, tr);
                    int x = c.cx + r[0], z = c.cz + r[1];
                    if (!c.in(x, z)) continue;
                    fixedH[c.idx(x, z)] = c.h0 + tc.dy();
                    src[c.idx(x, z)] = 1;
                }
            }
        }
        for (Plan.Placed pl : p.pieces) {
            Shape s = shapes[pl.index()];
            for (int k = 0; k < s.margin.length; k += 2) {
                int i = c.idx(pl.x0 + s.margin[k], pl.z0 + s.margin[k + 1]);
                if (src[i] < 2 || fixedH[i] == HeightField.NONE) fixedH[i] = pl.floor;
                else if (src[i] == 2) fixedH[i] = Math.min(fixedH[i], pl.floor);
                if (src[i] < 2) src[i] = 2;
            }
        }
        for (int i = 0; i < n; i++) {
            if (pathH[i] != HeightField.NONE && src[i] <= 2) {
                fixedH[i] = pathH[i];
                src[i] = 3;
            }
        }
        if (mask != null) for (int i = 0; i < n; i++) if (src[i] == 6) fixedH[i] = c.ground[i];
        for (Plan.Placed pl : p.pieces) {
            Shape s = shapes[pl.index()];
            if (pl.bp.door) {
                int fi = c.idx(pl.x0 + s.fx, pl.z0 + s.fz);
                if (src[fi] < 5) {
                    fixedH[fi] = pl.floor;
                    src[fi] = 4;
                }
            }
            for (int k = 0; k < s.occ.length; k += 2) {
                int i = c.idx(pl.x0 + s.occ[k], pl.z0 + s.occ[k + 1]);
                fixedH[i] = pl.floor;
                src[i] = 5;
            }
        }
        p.fixedH = fixedH;
        p.fixedSrc = src;
        long pad = 0;
        for (int i = 0; i < n; i++) if (fixedH[i] != HeightField.NONE && src[i] != 6) pad += Math.abs(fixedH[i] - c.ground[i]);
        p.padCost = pad;
        // 6. 목표 높이장
        if (full) {
            if (mask == null) {
                p.field = HeightField.compute(c.gn, c.gn, c.reach + 1, c.reach + 1, inner, blend, c.ground, fixedH);
            } else {
                // 거리 = 고정 칸(조각·여유·정문 앞·길, 얼린 칸 제외)까지 — R 안은 다듬고 R~R+B 는 원래 높이로 섞는다
                List<int[]> seeds = new ArrayList<>();
                for (int i = 0; i < n; i++) if (src[i] != 0 && src[i] != 6) seeds.add(new int[] {c.gx0 + i % c.gn, c.gz0 + i / c.gn});
                p.dist = distanceField(c.gx0, c.gz0, c.gn, seeds, mask.r() + mask.b() + 1);
                p.field = HeightField.compute(c.gn, c.gn, p.dist, mask.r(), mask.b(), c.ground, fixedH);
            }
            p.cut = p.field.cut();
            p.fill = p.field.fill();
        }
        return p;
    }


    /**
     * 마스크 모드 길: 얼린 칸 위 길 칸은 원래 높이 그대로 (TRIM = 겉 블록만 깖), 마을 길·보호 상자 칸(PATH·PROTECT)은 구역 길에서 뺀다.
     * 마을 길 칸에 닿는 구역 길 칸은 그 마을 길 높이와 1 이하로 이어져야 한다 (이음, CONTRACT checks junction).
     * @return 실패 이유 (null = 통과)
     */
    private String frozenPaths(Ctx c, Plan p, int[] pathH) {
        FrozenCells fz = mask.frozen();
        for (Plan.PathPlan pp : p.paths) {
            List<int[]> keep = new ArrayList<>();
            for (int[] cell : pp.cells) {
                int x = cell[0], z = cell[1];
                FrozenCells.Kind k = fz.kind(x, z);
                int i = c.idx(x, z);
                if (k == FrozenCells.Kind.PATH || k == FrozenCells.Kind.PROTECT) {
                    pathH[i] = HeightField.NONE;
                    continue;
                }
                if (k == FrozenCells.Kind.TRIM) {
                    pathH[i] = c.ground[i];
                    keep.add(new int[] {x, z, c.ground[i]});
                    continue;
                }
                keep.add(cell);
            }
            pp.cells.clear();
            pp.cells.addAll(keep);
        }
        p.junctions = 0;
        for (Plan.PathPlan pp : p.paths) {
            for (int[] cell : pp.cells) {
                for (int[] d : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
                    Integer vy = fz.pathY(cell[0] + d[0], cell[1] + d[1]);
                    if (vy == null) continue;
                    p.junctions++;
                    if (Math.abs(vy - cell[2]) > 1) {
                        return "구역 길 #" + pp.def.index() + " 이 마을 길과 만나는 칸 (" + cell[0] + ", " + cell[1] + ") 높이 차 "
                                + Math.abs(vy - cell[2]) + " (이음은 1 이하)";
                    }
                }
            }
        }
        return null;
    }

    /** 길 끝 e 가 붙은 조각 (발자국까지 체비셰프 거리 ≤ ATTACH 중 가장 가까운 것, 같으면 장식이 아닌 쪽), 없으면 −1. */
    private static int attach(List<Plan.Placed> pieces, int[] e) {
        int best = -1, bestD = Integer.MAX_VALUE;
        for (Plan.Placed pl : pieces) {
            int d = Integer.MAX_VALUE;
            for (int rz = 0; rz < pl.d2; rz++) {
                for (int rx = 0; rx < pl.w2; rx++) {
                    if (!pl.occ[rz * pl.w2 + rx]) continue;
                    d = Math.min(d, Math.max(Math.abs(pl.x0 + rx - e[0]), Math.abs(pl.z0 + rz - e[1])));
                }
            }
            int score = d * 2 + (pl.bp.deco ? 1 : 0);
            if (d <= ATTACH && score < bestD) {
                bestD = score;
                best = pl.index();
            }
        }
        return best;
    }

    private static void moveEnds(Plan.PathPlan pp, int piece, int dx, int dz) {
        if (pp.attachA == piece) {
            int[] q = pp.points.get(0);
            pp.points.set(0, new int[] {q[0] + dx, q[1] + dz});
        }
        if (pp.attachB == piece) {
            int last = pp.points.size() - 1;
            int[] q = pp.points.get(last);
            pp.points.set(last, new int[] {q[0] + dx, q[1] + dz});
        }
    }

    private static void mark(Ctx c, long[] mask, List<PathRaster.Cell> cells, int bit, boolean on) {
        for (PathRaster.Cell cell : cells) {
            if (!c.in(cell.x(), cell.z())) continue;
            int i = c.idx(cell.x(), cell.z());
            if (on) mask[i] |= 1L << bit;
            else mask[i] &= ~(1L << bit);
        }
    }

    /**
     * 이미 놓인 조각 j 와 길로 이어진 경우, 그 길이 걸어서 이을 수 있는 단 높이 범위 [P_j − L, P_j + L]
     * (L = 두 발자국 밖 길 칸 사이 거리). @return {lo, hi, 길 순번} (제약 없으면 lo = MIN)
     */
    private int[] linkRange(Plan p, boolean[] placed, Plan.Placed pl, int dx, int dz) {
        int lo = Integer.MIN_VALUE, hi = Integer.MAX_VALUE, which = -1;
        for (Plan.PathPlan pp : p.paths) {
            if (!pp.attached(pl.index())) continue;
            int other = pp.attachA == pl.index() ? pp.attachB : pp.attachA;
            if (other < 0 || other == pl.index() || !placed[other]) continue;
            Plan.Placed j = p.piece(other);
            List<int[]> pts = new ArrayList<>(pp.points);
            if (pp.attachA == pl.index()) pts.set(0, new int[] {pts.get(0)[0] + dx, pts.get(0)[1] + dz});
            if (pp.attachB == pl.index()) {
                int last = pts.size() - 1;
                pts.set(last, new int[] {pts.get(last)[0] + dx, pts.get(last)[1] + dz});
            }
            double tMin = Double.MAX_VALUE, tMax = -1;
            for (PathRaster.Cell cell : PathRaster.cells(pts, pp.def.width())) {
                if (pl.occupies(cell.x() - dx, cell.z() - dz) || j.occupies(cell.x(), cell.z())) continue;
                tMin = Math.min(tMin, cell.t());
                tMax = Math.max(tMax, cell.t());
            }
            int len = tMax < 0 ? 0 : (int) Math.floor(tMax - tMin + 1e-6);
            if (j.floor - len > lo) {
                lo = j.floor - len;
                which = pp.def.index();
            }
            if (j.floor + len < hi) {
                hi = j.floor + len;
                which = pp.def.index();
            }
        }
        return new int[] {lo, hi, which};
    }

    /** 한 오프셋 평가: 단 높이 P, 변화량, 한도·동굴 검사, 이미 놓인 조각과 길로 이을 수 있는 높이. */
    private Option evaluate(Ctx c, Plan p, boolean[] placed, Plan.Placed pl, Shape s, int dx, int dz) {
        int bx = pl.x0 + dx, bz = pl.z0 + dz;
        int minG = Integer.MAX_VALUE, maxG = Integer.MIN_VALUE;
        double limit = c.reach - 1;
        int padLimit = padLimit(), caveDepth = caveDepth();
        if (mask != null && pl.bp.door) {
            int fx = bx + s.fx, fz = bz + s.fz;
            if (!c.in(fx, fz) || c.frozenAt(fx, fz)) {
                return new Option(dx, dz, 0, 0, 0, Fail.RANGE, pl.bp.id + ": 정문 앞 칸이 마을(얼린 칸) 위");
            }
        }
        for (int pass = 0; pass < 2; pass++) {
            int[] cells = pass == 0 ? s.occ : s.margin;
            for (int k = 0; k < cells.length; k += 2) {
                int x = bx + cells[k], z = bz + cells[k + 1];
                if (mask != null) {
                    if (!c.in(x, z) || c.dist0[c.idx(x, z)] > mask.r() + mask.b()) {
                        return new Option(dx, dz, 0, 0, 0, Fail.RANGE, pl.bp.id + ": 구역 영역 밖으로 나감");
                    }
                    if (c.frozen[c.idx(x, z)]) {
                        return new Option(dx, dz, 0, 0, 0, Fail.RANGE, pl.bp.id + ": 마을(얼린 칸)에 닿음 (" + x + ", " + z + ")");
                    }
                } else if (Math.hypot(x - c.cx, z - c.cz) > limit || !c.in(x, z)) {
                    return new Option(dx, dz, 0, 0, 0, Fail.RANGE, pl.bp.id + ": 마을 영역 밖으로 나감");
                }
                int g = c.g(x, z);
                minG = Math.min(minG, g);
                maxG = Math.max(maxG, g);
            }
        }
        int lo = maxG - padLimit, hi = minG + padLimit;
        int[] link = linkRange(p, placed, pl, dx, dz);
        int floor;
        if (pl.entry.dy() != null) {
            floor = c.h0 + pl.entry.dy();
        } else {
            // 가중 중앙값 (높이 범위가 좁아 히스토그램)
            int span = maxG - minG + 1;
            long[] hist = new long[span];
            long total = 0;
            for (int k = 0, w = 0; k < s.occ.length; k += 2, w++) {
                int g = c.g(bx + s.occ[k], bz + s.occ[k + 1]);
                hist[g - minG] += s.weight[w];
                total += s.weight[w];
            }
            long acc = 0;
            int med = minG;
            for (int v = 0; v < span; v++) {
                acc += hist[v];
                if (acc * 2 >= total) {
                    med = minG + v;
                    break;
                }
            }
            floor = Math.max(Math.max(lo, link[0]), Math.min(Math.min(hi, link[1]), med));
            floor = Math.max(c.h0 - DY_CLAMP, Math.min(c.h0 + DY_CLAMP, floor));
        }
        if (floor < lo || floor > hi) {
            String why = lo > hi
                    ? pl.bp.id + ": 자리 높이 차 " + (maxG - minG) + "칸 — 깎기/메우기가 " + padLimit + "칸을 넘음"
                    : pl.bp.id + ": 단 높이 " + floor + " 에서 깎기/메우기가 " + padLimit + "칸을 넘음 (기준 H0 " + c.h0 + ")";
            return new Option(dx, dz, floor, 0, 0, Fail.LIMIT, why);
        }
        if (floor < link[0] || floor > link[1]) {
            return new Option(dx, dz, floor, 0, 0, Fail.PATH, pl.bp.id + ": 길 #" + link[2] + " 이 짧아 이웃 조각과의 단 높이 차를 걸어서 이을 수 없음");
        }
        double cost = 0;
        int caveVol = 0, caveCols = 0;
        for (int pass = 0; pass < 2; pass++) {
            int[] cells = pass == 0 ? s.occ : s.margin;
            for (int k = 0; k < cells.length; k += 2) {
                int x = bx + cells[k], z = bz + cells[k + 1];
                int i = c.idx(x, z);
                int g = c.ground[i];
                cost += Math.abs(floor - g);
                if (pass == 1) continue;
                int bits = c.holes[i];
                if (bits == 0) continue;
                int kmin = Math.max(1, g - floor + 1), kmax = Math.min(16, g - floor + caveDepth);
                int vol = 0;
                for (int kk = kmin; kk <= kmax; kk++) if ((bits & (1 << (kk - 1))) != 0) vol++;
                if (vol > 0) {
                    caveVol += vol;
                    caveCols++;
                }
            }
        }
        int occCols = s.occ.length / 2;
        if (caveCols * 3 > occCols) {
            return new Option(dx, dz, floor, cost, caveVol, Fail.CAVE,
                    pl.bp.id + ": 발자국 아래 " + caveDepth + "칸 안에 동굴 (" + caveCols + "/" + occCols + "열)");
        }
        return new Option(dx, dz, floor, cost + 0.5 * caveVol, caveVol, Fail.NONE, "");
    }

    /** 1칸 여유 검사: 놓인 조각, 붙지 않은 길, 그리고 이 조각에 붙은 길을 옮겼을 때 다른 조각. */
    private boolean clear(Ctx c, Plan p, Plan.Placed pl, Shape s, int dx, int dz, int[] own, int[] doorOwn, long[] pathMask) {
        long attachedMask = 0;
        for (Plan.PathPlan pp : p.paths) if (pp.attached(pl.index())) attachedMask |= 1L << pp.def.index();
        int bx = pl.x0 + dx, bz = pl.z0 + dz;
        for (int k = 0; k < s.occ.length; k += 2) {
            int x = bx + s.occ[k], z = bz + s.occ[k + 1];
            for (int qz = -1; qz <= 1; qz++) {
                for (int qx = -1; qx <= 1; qx++) {
                    if (!c.in(x + qx, z + qz)) return false;
                    int i = c.idx(x + qx, z + qz);
                    if (own[i] >= 0 && own[i] != pl.index()) return false;
                    if (doorOwn[i] >= 0 && doorOwn[i] != pl.index()) return false; // 다른 조각 정문 앞 칸
                    if ((pathMask[i] & ~attachedMask) != 0) return false;
                }
            }
        }
        if (pl.bp.door) { // 이 조각 정문 앞 칸 둘레에 다른 조각 없음
            for (int qz = -1; qz <= 1; qz++) {
                for (int qx = -1; qx <= 1; qx++) {
                    int x = bx + s.fx + qx, z = bz + s.fz + qz;
                    if (!c.in(x, z)) return false;
                    int o = own[c.idx(x, z)];
                    if (o >= 0 && o != pl.index()) return false;
                }
            }
        }
        if (attachedMask == 0) return true;
        for (Plan.PathPlan pp : p.paths) {
            if (!pp.attached(pl.index())) continue;
            List<int[]> pts = new ArrayList<>(pp.points);
            if (pp.attachA == pl.index()) pts.set(0, new int[] {pts.get(0)[0] + dx, pts.get(0)[1] + dz});
            if (pp.attachB == pl.index()) {
                int last = pts.size() - 1;
                pts.set(last, new int[] {pts.get(last)[0] + dx, pts.get(last)[1] + dz});
            }
            for (PathRaster.Cell cell : PathRaster.cells(pts, pp.def.width())) {
                for (int qz = -1; qz <= 1; qz++) {
                    for (int qx = -1; qx <= 1; qx++) {
                        if (!c.in(cell.x() + qx, cell.z() + qz)) continue;
                        int o = own[c.idx(cell.x() + qx, cell.z() + qz)];
                        if (o >= 0 && !pp.attached(o)) return false;
                    }
                }
            }
        }
        return true;
    }

    /**
     * 길 높이: 양 끝 높이 사이 직선 보간을 기준으로 지형을 ±PATH_FOLLOW 안에서 따라가고, 중심선 1칸마다 차 ≤ 1.
     * 끝 높이는 조각 발자국 바로 밖 첫/마지막 길 칸에 고정한다 (발자국과 길 사이 턱이 생기지 않게).
     */
    private void pathHeights(Ctx c, Plan p, Plan.PathPlan pp, List<PathRaster.Cell> cells, int[] pathH) {
        double len = PathRaster.length(pp.points);
        int hA = endHeight(c, p, pp, pp.points.get(0), pp.attachA, pathH);
        int hB = endHeight(c, p, pp, pp.points.get(pp.points.size() - 1), pp.attachB, pathH);
        List<PathRaster.Cell> out = new ArrayList<>();
        double tA = Double.MAX_VALUE, tB = -1;
        for (PathRaster.Cell cell : cells) {
            boolean inPiece = false;
            for (Plan.Placed pl : p.pieces) {
                if (pl.occupies(cell.x(), cell.z())) {
                    inPiece = true;
                    break;
                }
            }
            if (inPiece || !c.in(cell.x(), cell.z())) continue; // 조각 발자국 안 칸은 건너뜀 (§3)
            out.add(cell);
            tA = Math.min(tA, cell.t());
            tB = Math.max(tB, cell.t());
        }
        if (out.isEmpty()) return;
        int k = Math.max(1, (int) Math.ceil(len));
        int[] s = new int[k + 1];
        boolean[] pin = new boolean[k + 1];
        double off = pp.def.width() % 2 == 1 ? 0.5 : 0.0;
        double span = Math.max(1e-9, tB - tA);
        for (int i = 0; i <= k; i++) {
            double t = len * i / k;
            if (t <= tA + 1e-6) {
                s[i] = hA;
                pin[i] = true;
                continue;
            }
            if (t >= tB - 1e-6) {
                s[i] = hB;
                pin[i] = true;
                continue;
            }
            double lin = hA + (hB - hA) * (t - tA) / span;
            int[] q = pointAt(pp.points, t, off);
            int g = c.in(q[0], q[1]) ? c.g(q[0], q[1]) : (int) Math.round(lin);
            int li = (int) Math.floor(lin + 0.5);
            s[i] = Math.max(li - pp.def.follow(), Math.min(li + pp.def.follow(), g));
        }
        for (int pass = 0; pass < 12; pass++) {
            boolean any = false;
            for (int i = 1; i <= k; i++) {
                if (pin[i]) continue;
                int v = Math.max(s[i - 1] - 1, Math.min(s[i - 1] + 1, s[i]));
                if (v != s[i]) { s[i] = v; any = true; }
            }
            for (int i = k - 1; i >= 0; i--) {
                if (pin[i]) continue;
                int v = Math.max(s[i + 1] - 1, Math.min(s[i + 1] + 1, s[i]));
                if (v != s[i]) { s[i] = v; any = true; }
            }
            if (!any) break;
        }
        for (PathRaster.Cell cell : out) {
            int i = c.idx(cell.x(), cell.z());
            int si = len <= 0 ? 0 : (int) Math.max(0, Math.min(k, Math.round(cell.t() / len * k)));
            if (pathH[i] == HeightField.NONE) pathH[i] = s[si];
            pp.cells.add(new int[] {cell.x(), cell.z(), pathH[i]});
        }
    }

    private int endHeight(Ctx c, Plan p, Plan.PathPlan pp, int[] e, int attached, int[] pathH) {
        if (attached >= 0) return p.piece(attached).floor;
        int best = HeightField.NONE, bestD = Integer.MAX_VALUE;
        for (int dz = -1; dz <= 1; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                if (!c.in(e[0] + dx, e[1] + dz)) continue;
                int h = pathH[c.idx(e[0] + dx, e[1] + dz)];
                int d = Math.abs(dx) + Math.abs(dz);
                if (h != HeightField.NONE && d < bestD) {
                    best = h;
                    bestD = d;
                }
            }
        }
        if (best != HeightField.NONE) return best;
        int g = c.in(e[0], e[1]) ? c.g(e[0], e[1]) : c.h0;
        return Math.max(c.h0 - DY_CLAMP, Math.min(c.h0 + DY_CLAMP, g));
    }

    /** 꺾은선 위 거리 t 지점의 칸. */
    private static int[] pointAt(List<int[]> pts, double t, double off) {
        double acc = 0;
        for (int i = 1; i < pts.size(); i++) {
            double ax = pts.get(i - 1)[0] + off, az = pts.get(i - 1)[1] + off, bx = pts.get(i)[0] + off, bz = pts.get(i)[1] + off;
            double l = Math.hypot(bx - ax, bz - az);
            if (acc + l >= t || i == pts.size() - 1) {
                double u = l <= 0 ? 0 : Math.max(0, Math.min(1, (t - acc) / l));
                return new int[] {(int) Math.floor(ax + u * (bx - ax)), (int) Math.floor(az + u * (bz - az))};
            }
            acc += l;
        }
        return pts.get(0).clone();
    }

    // ── 겹침 검사 (계획기 · 자가 진단 공용) ────────────────────────────────

    /**
     * 조각끼리 1칸 여유(발자국 사이 빈칸 ≥ 1), 정문 앞 칸 둘레에 다른 조각 없음,
     * 길(원래 폭 그대로, 발자국 안 칸 포함)과 붙지 않은 조각 1칸 여유.
     * @return 위반 설명 (비어 있으면 통과)
     */
    public static List<String> overlaps(List<Plan.Placed> pieces, List<Plan.PathPlan> paths) {
        List<String> out = new ArrayList<>();
        for (int i = 0; i < pieces.size(); i++) {
            Plan.Placed a = pieces.get(i);
            for (int j = i + 1; j < pieces.size(); j++) {
                Plan.Placed b = pieces.get(j);
                if (a.x0 - 1 > b.x0 + b.w2 - 1 || b.x0 - 1 > a.x0 + a.w2 - 1 || a.z0 - 1 > b.z0 + b.d2 - 1 || b.z0 - 1 > a.z0 + a.d2 - 1) continue;
                if (touches(a, b)) out.add("조각 " + a.bp.id + " 와 " + b.bp.id + " 가 겹치거나 붙음");
            }
        }
        for (Plan.Placed a : pieces) {
            if (!a.bp.door) continue;
            int[] f = a.doorFront();
            for (Plan.Placed b : pieces) {
                if (b == a) continue;
                boolean hit = false;
                for (int qz = -1; qz <= 1 && !hit; qz++) for (int qx = -1; qx <= 1 && !hit; qx++) hit = b.occupies(f[0] + qx, f[1] + qz);
                if (hit) out.add("조각 " + a.bp.id + " 정문 앞 칸에 " + b.bp.id + " 가 닿음");
            }
        }
        for (Plan.PathPlan pp : paths) {
            List<PathRaster.Cell> cells = PathRaster.cells(pp.points, pp.def.width());
            for (Plan.Placed pl : pieces) {
                if (pp.attached(pl.index())) continue;
                boolean hit = false;
                for (PathRaster.Cell cell : cells) {
                    for (int qz = -1; qz <= 1 && !hit; qz++) {
                        for (int qx = -1; qx <= 1 && !hit; qx++) hit = pl.occupies(cell.x() + qx, cell.z() + qz);
                    }
                    if (hit) break;
                }
                if (hit) out.add("길 #" + pp.def.index() + " 이 조각 " + pl.bp.id + " 에 겹치거나 붙음");
            }
        }
        return out;
    }

    private static boolean touches(Plan.Placed a, Plan.Placed b) {
        for (int rz = 0; rz < a.d2; rz++) {
            for (int rx = 0; rx < a.w2; rx++) {
                if (!a.occ[rz * a.w2 + rx]) continue;
                for (int qz = -1; qz <= 1; qz++) {
                    for (int qx = -1; qx <= 1; qx++) if (b.occupies(a.x0 + rx + qx, a.z0 + rz + qz)) return true;
                }
            }
        }
        return false;
    }

    // ── survey ───────────────────────────────────────────────────────────

    /** 후보 하나 (가벼운 기록 — 격자 배열은 들고 있지 않음). */
    public record Candidate(int cx, int cz, int turns, double score) {}

    public record SurveyResult(List<Plan> best, Map<Fail, Integer> rejects, int centers, int plans) {}

    /**
     * 중심 (ox, oz) 둘레 반경 radius 안 step 칸 간격 후보 × 회전 4방향. 빠른 계획(단 변화량)으로 거른 뒤
     * 상위 몇 곳은 목표 높이장까지 계산해 실제 깎기·메우기 총량으로 순위를 매긴다. 서로 16칸 안의 자리는 하나만.
     */
    public SurveyResult survey(Terrain t, int ox, int oz, int radius, int step, int top, AtomicInteger progress,
                               BooleanSupplier cancelled) {
        List<int[]> centers = new ArrayList<>();
        int steps = radius / step;
        for (int j = -steps; j <= steps; j++) {
            for (int i = -steps; i <= steps; i++) {
                if (i * i + j * j > steps * steps) continue;
                centers.add(new int[] {ox + i * step, oz + j * step});
            }
        }
        Map<Fail, Integer> rejects = new ConcurrentHashMap<>();
        List<Candidate> cands = java.util.Collections.synchronizedList(new ArrayList<>());
        AtomicInteger plans = new AtomicInteger();
        ForkJoinPool pool = new ForkJoinPool(Math.max(1, Runtime.getRuntime().availableProcessors() / 2));
        try {
            pool.submit(() -> centers.parallelStream().forEach(cc -> {
                if (cancelled.getAsBoolean()) return;
                Ctx ctx = context(t, cc[0], cc[1]);
                if (ctx.fail != Fail.NONE) {
                    rejects.merge(ctx.fail, 4, Integer::sum);
                } else {
                    for (int tr = 0; tr < 4; tr++) {
                        Plan pl = plan(ctx, tr, false);
                        plans.incrementAndGet();
                        if (pl.ok()) cands.add(new Candidate(cc[0], cc[1], tr, pl.score()));
                        else rejects.merge(pl.fail, 1, Integer::sum);
                    }
                }
                if (progress != null) progress.incrementAndGet();
            })).get();
            List<Candidate> sorted = new ArrayList<>(cands);
            sorted.sort((a, b) -> Double.compare(a.score(), b.score()));
            List<Candidate> shortlist = new ArrayList<>();
            for (Candidate cd : sorted) {
                if (shortlist.size() >= Math.max(top * 6, 24)) break;
                shortlist.add(cd);
            }
            List<Plan> full = pool.submit(() -> shortlist.parallelStream()
                    .map(cd -> plan(t, cd.cx(), cd.cz(), cd.turns(), true)).filter(Plan::ok).toList()).get();
            List<Plan> ranked = new ArrayList<>(full);
            ranked.sort((a, b) -> Double.compare(a.score(), b.score()));
            List<Plan> best = new ArrayList<>();
            for (Plan pl : ranked) {
                boolean near = false;
                for (Plan b : best) if (Math.hypot(b.cx - pl.cx, b.cz - pl.cz) < 16) near = true;
                if (near) continue;
                best.add(pl);
                if (best.size() >= top) break;
            }
            Map<Fail, Integer> rj = new EnumMap<>(Fail.class);
            rj.putAll(rejects);
            return new SurveyResult(best, rj, centers.size(), plans.get());
        } catch (Exception e) {
            throw new IllegalStateException("survey 계산 실패: " + e.getMessage(), e);
        } finally {
            pool.shutdown();
        }
    }

    /** 이 자리에서 회전 4방향 중 가장 좋은 full 계획 (모두 실패면 회전 0 의 실패 계획). */
    public Plan bestRotation(Terrain t, int cx, int cz) {
        Ctx ctx = context(t, cx, cz);
        Plan best = null, first = null;
        for (int tr = 0; tr < 4; tr++) {
            Plan pl = plan(ctx, tr, true);
            if (first == null) first = pl;
            if (pl.ok() && (best == null || pl.score() < best.score())) best = pl;
        }
        return best != null ? best : first;
    }
}
