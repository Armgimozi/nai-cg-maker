package kr.labyrinth.homes.rules;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import kr.labyrinth.homes.PlotGeom;

/**
 * 집터 색인 (0.3.7) — 청크 → 그 청크에 걸친 집터들. 순수 (서버 없이 시험). 소유: 묶음 B.
 * <p>
 * 조회 한 번 = 해시 1번 + 상자 몇 번 비교 (집터 하나는 청크 ≤ 4개, 청크 하나에 집터 ≤ 4개). 구역 집터 + convert 집터를 같이 담는다.
 * 만든 뒤에는 바꾸지 않는다 (바뀌면 새로 만들어 통째로 바꿔 끼움 — 여러 스레드가 읽어도 안전).
 */
public final class PlotIndex {

    public static final PlotIndex EMPTY = new PlotIndex(List.of());

    private final Map<Long, PlotGeom[]> byChunk;
    private final List<PlotGeom> all;
    private final Map<String, PlotGeom> byId;
    private final Map<Integer, PlotGeom> byKey;

    public PlotIndex(Collection<PlotGeom> plots) {
        List<PlotGeom> sorted = new ArrayList<>();
        Map<String, PlotGeom> ids = new LinkedHashMap<>();
        Map<Integer, PlotGeom> keys = new HashMap<>();
        if (plots != null) for (PlotGeom p : plots) {
            if (p == null) continue;
            String id = norm(p.id());
            if (ids.containsKey(id) || keys.containsKey(p.key())) continue; // 같은 id·key 는 처음 것만
            ids.put(id, p);
            keys.put(p.key(), p);
            sorted.add(p);
        }
        sorted.sort(Comparator.comparingInt(PlotGeom::key));
        Map<Long, List<PlotGeom>> tmp = new HashMap<>();
        for (PlotGeom p : sorted) {
            for (int cx = p.x0() >> 4; cx <= p.x1() >> 4; cx++) {
                for (int cz = p.z0() >> 4; cz <= p.z1() >> 4; cz++) tmp.computeIfAbsent(chunkKey(cx, cz), k -> new ArrayList<>()).add(p);
            }
        }
        Map<Long, PlotGeom[]> out = new HashMap<>();
        for (Map.Entry<Long, List<PlotGeom>> e : tmp.entrySet()) out.put(e.getKey(), e.getValue().toArray(new PlotGeom[0]));
        this.byChunk = out;
        this.all = List.copyOf(sorted);
        this.byId = ids;
        this.byKey = keys;
    }

    public static long chunkKey(int cx, int cz) { return ((long) cx << 32) ^ (cz & 0xffffffffL); }

    private static String norm(String id) { return id == null ? "" : id.trim().toLowerCase(Locale.ROOT); }

    /** (x, y, z) 가 들어 있는 집터 (높이 창 안), 없으면 null. */
    public PlotGeom at(int x, int y, int z) {
        PlotGeom[] list = byChunk.get(chunkKey(x >> 4, z >> 4));
        if (list == null) return null;
        for (PlotGeom p : list) if (p.contains(x, y, z)) return p;
        return null;
    }

    /** 열 (x, z) 의 집터 (높이 무관), 없으면 null. */
    public PlotGeom column(int x, int z) {
        PlotGeom[] list = byChunk.get(chunkKey(x >> 4, z >> 4));
        if (list == null) return null;
        for (PlotGeom p : list) if (p.containsColumn(x, z)) return p;
        return null;
    }

    /** 이 청크에 집터가 걸쳐 있나 (잦은 이벤트를 빨리 끝내는 데 씀). */
    public boolean chunkHasPlot(int cx, int cz) { return byChunk.containsKey(chunkKey(cx, cz)); }

    /** 블록 (x, z) 의 청크에 집터가 걸쳐 있나. */
    public boolean near(int x, int z) { return byChunk.containsKey(chunkKey(x >> 4, z >> 4)); }

    public PlotGeom byId(String id) { return byId.get(norm(id)); }

    public PlotGeom byKey(int key) { return byKey.get(key); }

    /** 번호 차례 (구역 1..10, 그다음 c1, c2 …). */
    public List<PlotGeom> all() { return all; }

    public int size() { return all.size(); }

    public boolean isEmpty() { return all.isEmpty(); }

    /** 열 상자 [x0..x1]×[z0..z1] · 높이 [y0..y1] 와 겹치는 집터 (없으면 null) — convert 검사. */
    public PlotGeom overlapping(int x0, int z0, int x1, int z1, int y0, int y1) {
        for (PlotGeom p : all) {
            if (p.x1() < x0 || p.x0() > x1 || p.z1() < z0 || p.z0() > z1) continue;
            if (p.yMax() < y0 || p.yMin() > y1) continue;
            return p;
        }
        return null;
    }

    /** 걸친 청크 수 (자가 진단). */
    public int chunks() { return byChunk.size(); }
}
