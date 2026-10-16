package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * 마커 회전·월드 좌표 + 계획 → 메타데이터 (순수 함수). 마커 pos 의 y 는 발이 놓이는 칸(보통 floor_y + 1).
 * NPC·스폰·입구 위치 = 그 칸 가운데 (x + 0.5, Y, z + 0.5), yaw = face 를 조각 회전만큼 돌린 방향.
 */
public final class Markers {

    /** 월드에 놓인 마커. pos = 월드 [x, y, z] 들. */
    public record Placed(Blueprint.Marker marker, Plan.Placed piece, List<int[]> pos, Dir face) {
        public int[] first() { return pos.isEmpty() ? null : pos.get(0); }
    }

    /** 이름 붙은 서 있을 자리 마커 (vlib POINT_MARKERS) → 메타 points. 0.3.6 mine_exit = 광산에서 마을로 나오는 자리. */
    public static final java.util.Set<String> POINT_TYPES = java.util.Set.of(kr.labyrinth.mine.MineNames.MARKER_EXIT);

    private Markers() {}

    /** 정방향 조각 좌표 [x, y, z] → 월드 [x, y, z]. */
    public static int[] world(Plan.Placed pl, int[] pos) {
        int[] xz = pl.world(pos[0], pos[2]);
        return new int[] {xz[0], pl.worldY(pos[1]), xz[1]};
    }

    public static Dir face(Plan.Placed pl, String face) { return Dir.face(face).rotate(pl.turns); }

    public static List<Placed> all(Plan plan) {
        List<Placed> out = new ArrayList<>();
        for (Plan.Placed pl : plan.pieces) {
            for (Blueprint.Marker m : pl.bp.markers) {
                List<int[]> ws = new ArrayList<>();
                for (int[] p : m.pos()) ws.add(world(pl, p));
                out.add(new Placed(m, pl, ws, face(pl, m.face())));
            }
        }
        return out;
    }

    private static VillageMeta.Pos pos(int[] w, Dir face) {
        return new VillageMeta.Pos(w[0] + 0.5, w[1], w[2] + 0.5, face.yaw());
    }

    /** 계획(full) → labyrinth-village.yml 내용 (terrain 포함). */
    public static VillageMeta meta(Plan plan, Layout layout) {
        VillageMeta m = new VillageMeta();
        m.name = layout.name;
        m.rotation = Rot.of(plan.turns).name();
        m.radius = plan.inner > 0 ? plan.inner : layout.radius;
        m.blend = plan.blend > 0 ? plan.blend : layout.blend;
        m.center = new int[] {plan.cx, plan.h0, plan.cz};
        for (Placed mk : all(plan)) {
            int[] w = mk.first();
            if (w == null) continue;
            switch (mk.marker().type()) {
                case "spawn" -> { if (m.spawn == null) m.spawn = pos(w, mk.face()); }
                case "entrance" -> { if (m.entrance == null) m.entrance = pos(w, mk.face()); }
                case "npc" -> { if (mk.marker().id() != null) m.npcs.put(mk.marker().id(), pos(w, mk.face())); }
                case "interact" -> {
                    String action = mk.marker().action() == null ? "main" : mk.marker().action();
                    for (int[] q : mk.pos()) m.interact.put(VillageMeta.key(q[0], q[1], q[2]), action);
                }
                case "ambient" -> m.ambient.add(new VillageMeta.Ambient(w[0], w[1], w[2], mk.marker().fx() == null ? "magic" : mk.marker().fx()));
                default -> {
                    if (POINT_TYPES.contains(mk.marker().type())) m.points.putIfAbsent(mk.marker().type(), pos(w, mk.face()));
                }
            }
        }
        if (m.spawn == null && !plan.pieces.isEmpty()) {
            Plan.Placed first = plan.pieces.get(0);
            int[] a = first.anchor();
            m.spawn = new VillageMeta.Pos(a[0] + 0.5, first.floor + 1, a[1] + 0.5, first.front().yaw());
        }
        for (Plan.Placed pl : plan.pieces) {
            int y0 = Math.min(pl.minY(), pl.floor - plan.caveDepth - 1) - 1;
            m.protect.add(new VillageMeta.Box(pl.x0 - 1, y0, pl.z0 - 1, pl.x0 + pl.w2, pl.maxY() + 1, pl.z0 + pl.d2));
            m.pieces.add(new VillageMeta.PieceRec(pl.index(), pl.bp.id, pl.turns, pl.x0, pl.z0, pl.floor, pl.dx, pl.dz));
        }
        for (Plan.PathPlan pp : plan.paths) {
            m.paths.add(new VillageMeta.PathRec(pp.def.index(), pp.def.width(), pp.def.style(), pp.points, pp.attachA, pp.attachB, pp.cells));
            m.protect.addAll(pathBoxes(pp.cells));
        }
        if (plan.field != null) m.terrain = VillageMeta.terrainOf(plan);
        return m;
    }

    /** 길 칸 → 상자들 (z 줄마다 이어진 x 구간 하나씩, 높이 y−2 .. y+3). */
    static List<VillageMeta.Box> pathBoxes(List<int[]> cells) {
        Map<Integer, TreeMap<Integer, Integer>> rows = new TreeMap<>();
        for (int[] c : cells) rows.computeIfAbsent(c[1], k -> new TreeMap<>()).put(c[0], c[2]);
        List<VillageMeta.Box> out = new ArrayList<>();
        for (Map.Entry<Integer, TreeMap<Integer, Integer>> row : rows.entrySet()) {
            int z = row.getKey();
            Integer start = null, prev = null;
            int lo = Integer.MAX_VALUE, hi = Integer.MIN_VALUE;
            for (Map.Entry<Integer, Integer> e : row.getValue().entrySet()) {
                int x = e.getKey(), y = e.getValue();
                if (start != null && x != prev + 1) {
                    out.add(new VillageMeta.Box(start, lo - 2, z, prev, hi + 3, z));
                    start = null;
                    lo = Integer.MAX_VALUE;
                    hi = Integer.MIN_VALUE;
                }
                if (start == null) start = x;
                prev = x;
                lo = Math.min(lo, y);
                hi = Math.max(hi, y);
            }
            if (start != null) out.add(new VillageMeta.Box(start, lo - 2, z, prev, hi + 3, z));
        }
        return out;
    }

    /** 메타데이터의 조각 기록 → 놓인 조각 (청사진 필요). 청사진이 없으면 null. */
    public static Plan.Placed placed(VillageMeta.PieceRec r, Layout layout, Map<String, Blueprint> bps) {
        Blueprint bp = bps.get(r.piece());
        if (bp == null) return null;
        Layout.Entry e = r.index() >= 0 && r.index() < layout.pieces.size() && layout.pieces.get(r.index()).piece().equals(r.piece())
                ? layout.pieces.get(r.index()) : new Layout.Entry(r.index(), r.piece(), 0, 0, Dir.NORTH, null, null);
        Plan.Placed pl = new Plan.Placed(e, bp, r.turns(), r.x0(), r.z0());
        pl.floor = r.floor();
        pl.dx = r.dx();
        pl.dz = r.dz();
        return pl;
    }

    /** 메타데이터의 길 기록 → PathPlan (겹침 검사용). */
    public static Plan.PathPlan path(VillageMeta.PathRec r) {
        Layout.PathDef def = new Layout.PathDef(r.index(), r.points(), r.width(), r.style());
        Plan.PathPlan pp = new Plan.PathPlan(def, new ArrayList<>(r.points()));
        pp.attachA = r.attachA();
        pp.attachB = r.attachB();
        pp.cells.addAll(r.cells());
        return pp;
    }
}
