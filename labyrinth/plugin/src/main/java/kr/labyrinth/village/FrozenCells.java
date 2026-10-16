package kr.labyrinth.village;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 얼린 칸 (0.3.6 구역, CONTRACT §2.13 3번 · review_plots R7) — 구역 계획기가 높이·지형을 바꾸지 않는 열. 순수 데이터.
 * <ul>
 *   <li>{@link Kind#PROTECT}: 마을(과 먼저 지은 구역)의 보호 상자 안 — 겉 블록도 그대로.</li>
 *   <li>{@link Kind#PATH}: 마을(·구역) 길 칸 — 겉 블록도 그대로 (구역 길은 이 칸을 건너뛴다). 그 길 높이를 기억해 이음(junction)을 본다.</li>
 *   <li>{@link Kind#TRIM}: 마을(·구역)이 다듬은 칸 (meta.terrain.changed) — 깎기·메우기·나무 치우기 없음. 구역 길은 겉 블록만 길 블록으로.</li>
 * </ul>
 * 비자연 검사·지문 검사도 이 칸은 보지 않는다 (마을이 놓은 블록이 있으니).
 */
public final class FrozenCells {

    public enum Kind { NONE, TRIM, PATH, PROTECT }

    private final Map<Long, Kind> cells = new HashMap<>();
    private final Map<Long, Integer> pathY = new HashMap<>();

    public static FrozenCells empty() { return new FrozenCells(); }

    /** 마을 메타 + 먼저 지은 구역 메타들. */
    public static FrozenCells of(VillageMeta village, List<VillageMeta> others) {
        FrozenCells f = new FrozenCells();
        if (village != null) f.add(village);
        if (others != null) for (VillageMeta m : others) if (m != null) f.add(m);
        return f;
    }

    /** 메타 하나의 다듬은 칸 · 길 칸 · 보호 상자 (xz) 를 더한다 (강한 쪽이 이김: PROTECT > PATH > TRIM). */
    public FrozenCells add(VillageMeta m) {
        VillageMeta.TerrainRec t = m.terrain;
        if (t != null) {
            for (int z = t.z0(); z < t.z0() + t.n(); z++) {
                for (int x = t.x0(); x < t.x0() + t.n(); x++) if (t.changed(x, z)) put(x, z, Kind.TRIM);
            }
        }
        for (VillageMeta.PathRec p : m.paths) {
            for (int[] c : p.cells()) {
                put(c[0], c[1], Kind.PATH);
                pathY.putIfAbsent(PathRaster.key(c[0], c[1]), c[2]);
            }
        }
        for (VillageMeta.Box b : m.protect) {
            for (int z = Math.min(b.z0(), b.z1()); z <= Math.max(b.z0(), b.z1()); z++) {
                for (int x = Math.min(b.x0(), b.x1()); x <= Math.max(b.x0(), b.x1()); x++) put(x, z, Kind.PROTECT);
            }
        }
        return this;
    }

    public FrozenCells put(int x, int z, Kind k) {
        long key = PathRaster.key(x, z);
        Kind old = cells.get(key);
        if (old == null || old.ordinal() < k.ordinal()) cells.put(key, k);
        return this;
    }

    public Kind kind(int x, int z) { return cells.getOrDefault(PathRaster.key(x, z), Kind.NONE); }

    public boolean frozen(int x, int z) { return cells.containsKey(PathRaster.key(x, z)); }

    /** 겉 블록도 그대로 둘 칸 (보호 상자 · 길). */
    public boolean untouchable(int x, int z) {
        Kind k = kind(x, z);
        return k == Kind.PROTECT || k == Kind.PATH;
    }

    /** 마을(·구역) 길 칸 높이 (없으면 null). */
    public Integer pathY(int x, int z) { return pathY.get(PathRaster.key(x, z)); }

    public int size() { return cells.size(); }
}
