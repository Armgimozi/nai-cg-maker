package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.MineDef;

/**
 * 광산 PvP 안전 구역 (0.3.7 주인 결정 "광산 PvP 키자" — 승강기·관리소 둘레는 싸울 수 없음). 순수 (서버 없이 시험).
 * <p>
 * 층마다 사각형 하나: 승강기 홀 + 북쪽 벽감(1층 관리소가 있는 곳)의 블록 상자 x [승강기 −5, +5] · z [승강기 −7, +4] 를
 * {@code mine.pvp.safe_margin}(기본 3) 칸 넓힌 것. 높이는 그 층 상자 전체. 기본값이면 광산 월드 블록 x −8..8 · z −10..7
 * (실수 좌표 x ∈ [−8, 9) · z ∈ [−10, 8)) 로 6층이 모두 같다. 둘레 3칸에 드는 곳은 홀에서 나가는 갱도 입구 세 곳뿐이고
 * 바로 그 밖(x ±9 · z 8)부터 PvP 구역이다.
 * <ul>
 *   <li>값은 tools/mine/levels.py {@code plan()} 과 같다: 홀 {@code rect(C-5, C-4, C+5, C+4)} · 벽감 {@code rect(C-1, C-7, C+1, C-5)}.</li>
 *   <li>관리소(office 마커)가 홀 상자 밖에 있으면 그 둘레(±1 + 여유)를 같은 층에 따로 더한다. 지금 청사진은 1층 벽감 안이라 층마다 하나.</li>
 *   <li>층 상자 밖(층 사이 틈 · 떨어지는 중)은 PvP 구역이 아니다 (0.5초마다 승강장으로 옮겨짐).</li>
 *   <li>lift 마커가 없는 층은 (0, 0) 을 승강기로 본다 ({@code MineLevel.landing} 기본 자리와 같음 — 내리는 자리가 PvP 구역이 되지 않게).</li>
 * </ul>
 * PvP 판정({@code PvpRules.canPlayersFight})은 때리는 쪽이나 맞는 쪽 하나라도 안전 구역이면 적이 아니다. 그래서 홀 안이나 입구 3칸
 * 안에 서 있으면 어떤 것으로도 맞지 않고, 홀 문턱 밖에서 기다리는 사람도 근접 거리로는 홀 안을 때리지 못한다.
 */
public final class MineSafeZones {

    /** 홀 반폭 (x: 승강기 ±5). */
    public static final int HALL_HALF_X = 5;
    /** 승강기에서 북쪽 벽감 끝까지 (z: 승강기 −7). */
    public static final int HALL_NORTH = 7;
    /** 승강기에서 홀 남쪽 벽 안쪽까지 (z: 승강기 +4). */
    public static final int HALL_SOUTH = 4;
    /** 관리소 둘레 (여유 앞). */
    public static final int OFFICE_HALF = 1;
    /** {@code mine.pvp.safe_margin} 기본 · 범위. */
    public static final int DEFAULT_MARGIN = 3;
    public static final int MAX_MARGIN = 16;

    /** 블록 칸 (x, z) 하나 — 마커 자리. */
    public record Cell(int x, int z) {}

    /**
     * 층 하나의 재료. y 범위 = [yMin, yMax) (실수 좌표, {@code MineLevel.containsY} 와 같음).
     *
     * @param lift    승강기 블록 (없으면 null → (0, 0))
     * @param offices 관리소 블록들 (없으면 빈 목록)
     */
    public record Level(int n, double yMin, double yMax, Cell lift, List<Cell> offices) {
        public Level {
            offices = offices == null ? List.of() : List.copyOf(offices);
        }

        /** mine.yml 층 정의 + 청사진 (청사진이 없으면 마커 없음). */
        public static Level of(MineDef.Level def, MineBlueprint bp) {
            List<Integer> b = def.box();
            double y0 = b.size() == 6 ? b.get(1) : def.floorY() - 4;
            double y1 = b.size() == 6 ? b.get(4) + 1 : def.floorY() + 16;
            Cell lift = null;
            List<Cell> offices = new ArrayList<>();
            if (bp != null) {
                MineBlueprint.Marker m = bp.marker("lift");
                if (m != null) lift = new Cell(m.bx(), m.bz());
                for (MineBlueprint.Marker o : bp.markers(MineNames.MARKER_OFFICE)) offices.add(new Cell(o.bx(), o.bz()));
            }
            return new Level(def.n(), y0, y1, lift, offices);
        }

        boolean containsY(double y) { return y >= yMin && y < yMax; }
    }

    /** 실수 좌표 사각형 x ∈ [x0, x1) · z ∈ [z0, z1) (블록 칸 x0..x1−1 · z0..z1−1), 그 층 높이 전체. */
    public record Rect(int level, int x0, int x1, int z0, int z1) {
        public boolean contains(double x, double z) { return x >= x0 && x < x1 && z >= z0 && z < z1; }

        boolean containsBlock(int bx, int bz) { return bx >= x0 && bx < x1 && bz >= z0 && bz < z1; }

        /** "x −8..8 · z −10..7" (블록). */
        public String blocks() { return "x " + x0 + ".." + (x1 - 1) + " · z " + z0 + ".." + (z1 - 1); }
    }

    private final List<Level> levels;
    private final List<Rect> rects;
    private final int margin;

    private MineSafeZones(List<Level> levels, List<Rect> rects, int margin) {
        this.levels = List.copyOf(levels);
        this.rects = List.copyOf(rects);
        this.margin = margin;
    }

    public static final MineSafeZones EMPTY = new MineSafeZones(List.of(), List.of(), DEFAULT_MARGIN);

    public static int clampMargin(int m) { return Math.max(0, Math.min(MAX_MARGIN, m)); }

    /** 층마다 승강기 홀 사각형 (+ 홀 밖 관리소). margin 은 0 ~ 16 으로 자른다. */
    public static MineSafeZones of(List<Level> levels, int margin) {
        int m = clampMargin(margin);
        List<Rect> out = new ArrayList<>();
        for (Level l : levels) {
            Cell c = l.lift() == null ? new Cell(0, 0) : l.lift();
            Rect hall = new Rect(l.n(), c.x() - HALL_HALF_X - m, c.x() + HALL_HALF_X + m + 1, c.z() - HALL_NORTH - m, c.z() + HALL_SOUTH + m + 1);
            out.add(hall);
            // 홀 상자(여유 앞) 밖에 놓인 관리소만 따로 — 지금 청사진은 1층 벽감 안이라 더하지 않는다
            Rect core = new Rect(l.n(), c.x() - HALL_HALF_X, c.x() + HALL_HALF_X + 1, c.z() - HALL_NORTH, c.z() + HALL_SOUTH + 1);
            for (Cell o : l.offices()) {
                if (core.containsBlock(o.x(), o.z())) continue;
                int r = OFFICE_HALF + m;
                out.add(new Rect(l.n(), o.x() - r, o.x() + r + 1, o.z() - r, o.z() + r + 1));
            }
        }
        return new MineSafeZones(levels, out, m);
    }

    /** 그 자리가 안전한가 (PvP 아님): 어느 층 상자에도 없거나, 그 층의 안전 사각형 안. */
    public boolean safe(double x, double y, double z) {
        Level at = levelAt(y);
        if (at == null) return true;
        for (Rect r : rects) if (r.level() == at.n() && r.contains(x, z)) return true;
        return false;
    }

    /** 그 자리가 PvP 구역인가 (= 층 상자 안 · 안전 사각형 밖). 광산 PvP 켜짐 여부는 부르는 쪽이 본다. */
    public boolean pvpGround(double x, double y, double z) { return !safe(x, y, z); }

    Level levelAt(double y) {
        for (Level l : levels) if (l.containsY(y)) return l;
        return null;
    }

    public List<Rect> rects() { return rects; }

    /** 안전 구역이 있는 층 수 (자가 진단 safe_zones=6/6). */
    public int count() {
        int n = 0;
        for (Level l : levels) {
            for (Rect r : rects) {
                if (r.level() == l.n()) {
                    n++;
                    break;
                }
            }
        }
        return n;
    }

    public int levels() { return levels.size(); }

    public int margin() { return margin; }
}
